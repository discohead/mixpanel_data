"""Two-shot OAuth login state — on-disk inflight session and placeholder helpers.

This module persists the small bit of state that needs to survive the
``mp login --start`` / ``mp login --finish`` boundary:

1. ``inflight.json`` at ``~/.mp/oauth/inflight.json`` carries the PKCE
   verifier, OAuth state, registered ``client_id``, redirect URI, and
   region for at most :data:`INFLIGHT_TTL_SECONDS` (10 minutes). Without
   this, every ``--finish`` would have to re-run PKCE — defeating the
   "give me a URL, finish later" model the two-shot flow exists to enable.

2. Placeholder dir helpers (``new_placeholder_dir``,
   ``read_tokens_from_placeholder``, ``cache_me_in_placeholder``,
   ``load_cached_me_from_placeholder``, ``save_placeholder_meta``,
   ``read_placeholder_meta``) operate on the ``~/.mp/accounts/.tmp-{nonce}``
   scratch dirs the new-account flow uses between token exchange and the
   atomic publish. The same machinery powers ``mp login --resume`` for
   post-publish-failure recovery.

Mirrors :func:`bridge._read_browser_tokens` for the on-disk token shape so
the two readers stay in lockstep.
"""

from __future__ import annotations

import json
import logging
import os
import secrets
import socket
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

from pydantic import SecretStr

from mixpanel_headless._internal.auth.callback_server import CALLBACK_PORTS
from mixpanel_headless._internal.auth.storage import _storage_root
from mixpanel_headless._internal.auth.token import OAuthTokens
from mixpanel_headless._internal.io_utils import atomic_write_bytes
from mixpanel_headless.exceptions import OAuthError

logger = logging.getLogger(__name__)

INFLIGHT_TTL_SECONDS = 600
"""Inflight verifier lifetime in seconds (10 minutes).

Matches typical OAuth code-grant expiry windows. Long enough that a user
can switch tabs, paste the URL into their host browser, complete login,
and copy the redirect URL back without rushing; short enough that a
forgotten ``--start`` doesn't leave the verifier readable for hours."""

INFLIGHT_SCHEMA_VERSION = 1
"""Schema version for the on-disk ``inflight.json``.

Bumped only when a non-additive change to :class:`InflightSession`
breaks readers compiled against the older schema. Add fields without
bumping; remove or rename fields with a bump."""

PLACEHOLDER_META_SCHEMA_VERSION = 1
"""Schema version for ``meta.json`` written into placeholder dirs.

Same additive-vs-breaking discipline as :data:`INFLIGHT_SCHEMA_VERSION`."""


def inflight_path() -> Path:
    """Return the inflight file location, honoring ``MP_OAUTH_STORAGE_DIR``.

    Resolved at every call so test isolation via env var monkeypatching
    takes effect — a module-level constant captured at import time would
    silently leak the developer's real ``~/.mp/`` into hermetic tests.

    Returns:
        ``$MP_OAUTH_STORAGE_DIR/oauth/inflight.json`` if set,
        else ``$HOME/.mp/oauth/inflight.json``.
    """
    return _storage_root() / "oauth" / "inflight.json"


@dataclass(frozen=True)
class InflightSession:
    """On-disk state carried across the ``--start`` / ``--finish`` boundary.

    Frozen so accidental field mutation between read and use is a TypeError
    rather than a silent bug. ``pkce_verifier`` is a single-use secret —
    treat it like a refresh token (0o600 file, never logged under -v, no
    persistence beyond ``INFLIGHT_TTL_SECONDS``).

    Attributes:
        schema_version: :data:`INFLIGHT_SCHEMA_VERSION` (1).
        region: Region committed at ``--start`` time. ``--finish`` cannot
            switch regions; the Mixpanel auth endpoint is region-bound.
        client_id: DCR client ID for ``region``. Cached by
            :func:`ensure_client_registered`; the same client_id is reused
            on subsequent ``--start`` invocations within the same region.
        redirect_uri: Loopback URL the browser will be redirected to. The
            URL is registered with the IdP as part of DCR; ``--finish``
            re-uses it verbatim during code exchange.
        pkce_verifier: 43-128 char URL-safe base64 verifier. Sent to the
            token endpoint at ``--finish`` time. Single-use.
        state: 32-byte URL-safe base64 CSRF token. Compared against the
            pasted redirect URL's ``state`` parameter at ``--finish`` —
            mismatch raises ``OAUTH_STATE_MISMATCH``.
        created_at: Unix timestamp when ``--start`` ran. Diagnostic only.
        expires_at: ``created_at + INFLIGHT_TTL_SECONDS``. Files past
            this timestamp are rejected with ``OAUTH_INFLIGHT_EXPIRED``.
    """

    schema_version: int
    region: str
    client_id: str
    redirect_uri: str
    pkce_verifier: str
    state: str
    created_at: int
    expires_at: int


def save_inflight(session: InflightSession) -> None:
    """Atomically write ``session`` to the inflight file path with mode 0o600.

    Creates the parent directory (typically ``~/.mp/oauth/``) at 0o700 if
    missing. A second ``--start`` silently clobbers the prior inflight
    (single-user CLI; concurrent logins are not a supported use case).

    Args:
        session: The inflight state to persist.

    Raises:
        OSError: If the parent directory cannot be created or the write
            fails (disk full, permission denied).
    """
    path = inflight_path()
    old_umask = os.umask(0o077)
    try:
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    finally:
        os.umask(old_umask)
    payload = json.dumps(asdict(session), indent=2).encode("utf-8")
    atomic_write_bytes(path, payload)


def load_inflight() -> InflightSession:
    """Read and validate the inflight session from disk.

    Returns:
        The parsed :class:`InflightSession`.

    Raises:
        OAuthError: ``OAUTH_INFLIGHT_MISSING`` when no file exists,
            ``OAUTH_INFLIGHT_EXPIRED`` when ``expires_at < now()``,
            ``OAUTH_INFLIGHT_CORRUPT`` on JSON parse / missing-key /
            type-mismatch failures.
    """
    path = inflight_path()
    if not path.exists():
        raise OAuthError(
            f"No inflight session at {path}. Run `mp login --start` first.",
            code="OAUTH_INFLIGHT_MISSING",
            details={"path": str(path)},
        )
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise OAuthError(
            f"Inflight session at {path} could not be parsed: {exc}",
            code="OAUTH_INFLIGHT_CORRUPT",
            details={"path": str(path)},
        ) from exc
    if not isinstance(raw, dict):
        raise OAuthError(
            f"Inflight session at {path} is not a JSON object.",
            code="OAUTH_INFLIGHT_CORRUPT",
            details={"path": str(path)},
        )
    required = (
        "schema_version",
        "region",
        "client_id",
        "redirect_uri",
        "pkce_verifier",
        "state",
        "created_at",
        "expires_at",
    )
    missing = [k for k in required if k not in raw]
    if missing:
        raise OAuthError(
            f"Inflight session at {path} is missing required keys: {missing}.",
            code="OAUTH_INFLIGHT_CORRUPT",
            details={"path": str(path), "missing": missing},
        )
    try:
        session = InflightSession(
            schema_version=int(raw["schema_version"]),
            region=str(raw["region"]),
            client_id=str(raw["client_id"]),
            redirect_uri=str(raw["redirect_uri"]),
            pkce_verifier=str(raw["pkce_verifier"]),
            state=str(raw["state"]),
            created_at=int(raw["created_at"]),
            expires_at=int(raw["expires_at"]),
        )
    except (TypeError, ValueError) as exc:
        raise OAuthError(
            f"Inflight session at {path} has invalid field types: {exc}",
            code="OAUTH_INFLIGHT_CORRUPT",
            details={"path": str(path)},
        ) from exc
    if session.expires_at < int(time.time()):
        expired_at = datetime.fromtimestamp(session.expires_at, tz=timezone.utc)
        raise OAuthError(
            f"Inflight session at {path} expired at "
            f"{expired_at.isoformat()}. "
            f"Re-run `mp login --start`.",
            code="OAUTH_INFLIGHT_EXPIRED",
            details={"path": str(path), "expires_at": session.expires_at},
        )
    return session


def clear_inflight() -> None:
    """Remove the inflight file if present. Idempotent.

    Called on ``--finish`` success to prevent a stale verifier from being
    re-used. Failures are logged at WARNING but do not raise — the file's
    job is done either way.
    """
    path = inflight_path()
    try:
        path.unlink(missing_ok=True)
    except OSError as exc:
        logger.warning("Could not remove inflight file %s: %s", path, exc)


def find_available_callback_port() -> int:
    """Probe :data:`CALLBACK_PORTS` for a port not currently in use.

    Same selection logic as :func:`flow._find_available_port` but exposed
    here so :func:`accounts.login_unified_start` can build the
    ``redirect_uri`` without depending on the OAuthFlow class. The
    callback server is NOT started in the two-shot flow — the port is
    reserved purely so the registered ``redirect_uri`` matches what the
    same-machine flow would use, keeping the cached DCR client compatible
    across both paths.

    Returns:
        An available port from :data:`CALLBACK_PORTS`.

    Raises:
        OAuthError: ``OAUTH_PORT_ERROR`` when every candidate port is busy.
    """
    for port in CALLBACK_PORTS:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as test_sock:
                test_sock.bind(("127.0.0.1", port))
            return port
        except OSError:
            continue
    raise OAuthError(
        f"All OAuth callback ports ({CALLBACK_PORTS}) are busy.",
        code="OAUTH_PORT_ERROR",
    )


def new_placeholder_dir(accounts_root_dir: Path) -> Path:
    """Create a fresh ``.tmp-{nonce}/`` directory under ``accounts_root_dir``.

    Mode 0o700 on both the leaf and any newly-created parent. Mirrors the
    pattern in :func:`accounts._login_unified_new_browser` so the two
    flows produce structurally identical placeholder dirs (key precondition
    for ``mp login --resume``).

    Args:
        accounts_root_dir: Typically ``accounts_root()`` (i.e.
            ``~/.mp/accounts/``).

    Returns:
        Absolute path to the newly-created ``.tmp-{nonce}`` directory.
    """
    nonce = secrets.token_hex(4)
    old_umask = os.umask(0o077)
    try:
        accounts_root_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        placeholder_dir = accounts_root_dir / f".tmp-{nonce}"
        placeholder_dir.mkdir(mode=0o700)
    finally:
        os.umask(old_umask)
    return placeholder_dir


def read_tokens_from_placeholder(placeholder_dir: Path) -> OAuthTokens:
    """Reconstruct :class:`OAuthTokens` from ``placeholder_dir/tokens.json``.

    Mirror of :func:`bridge._read_browser_tokens` — the two paths must
    accept the exact same on-disk shape so a ``mp login --finish`` write
    is readable by ``mp account export-bridge`` and vice versa.

    Args:
        placeholder_dir: A ``.tmp-{nonce}/`` directory containing
            ``tokens.json`` (the canonical shape produced by
            :func:`token_payload_bytes`).

    Returns:
        The parsed :class:`OAuthTokens`.

    Raises:
        OAuthError: ``OAUTH_TOKEN_ERROR`` when the file is missing,
            unparseable, or missing required fields.
    """
    path = placeholder_dir / "tokens.json"
    if not path.exists():
        raise OAuthError(
            f"No tokens.json in placeholder {placeholder_dir}.",
            code="OAUTH_TOKEN_ERROR",
            details={"placeholder_dir": str(placeholder_dir)},
        )
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise OAuthError(
            f"Could not read tokens.json at {path}: {exc}",
            code="OAUTH_TOKEN_ERROR",
            details={"path": str(path)},
        ) from exc
    expires_raw = payload.get("expires_at")
    if not isinstance(expires_raw, str) or not expires_raw:
        raise OAuthError(
            f"tokens.json at {path} is missing `expires_at`.",
            code="OAUTH_TOKEN_ERROR",
            details={"path": str(path)},
        )
    try:
        expires_at = datetime.fromisoformat(expires_raw)
    except ValueError as exc:
        raise OAuthError(
            f"tokens.json at {path} has an invalid `expires_at`.",
            code="OAUTH_TOKEN_ERROR",
            details={"path": str(path)},
        ) from exc
    access_token = payload.get("access_token")
    if not isinstance(access_token, str) or not access_token:
        raise OAuthError(
            f"tokens.json at {path} is missing `access_token`.",
            code="OAUTH_TOKEN_ERROR",
            details={"path": str(path)},
        )
    refresh_raw = payload.get("refresh_token")
    refresh_token = (
        SecretStr(refresh_raw) if isinstance(refresh_raw, str) and refresh_raw else None
    )
    return OAuthTokens(
        access_token=SecretStr(access_token),
        refresh_token=refresh_token,
        expires_at=expires_at,
        scope=str(payload.get("scope", "")),
        token_type=str(payload.get("token_type", "Bearer")),
    )


def save_placeholder_meta(placeholder_dir: Path, *, region: str) -> None:
    """Persist non-credential metadata (region, schema) into the placeholder.

    The metadata file lets ``mp login --resume`` recover region without
    falling back to "read whichever client_X.json exists" — the prior
    prototype's hack didn't survive multi-region setups (a user with both
    ``client_us.json`` and ``client_eu.json`` would have ``--resume``
    pick the wrong region on the wrong placeholder).

    Args:
        placeholder_dir: Target ``.tmp-{nonce}`` directory. Caller must
            ensure it exists with mode 0o700.
        region: The region the inflight session was bound to.
    """
    meta = {
        "schema_version": PLACEHOLDER_META_SCHEMA_VERSION,
        "region": region,
        "created_at": int(time.time()),
    }
    atomic_write_bytes(
        placeholder_dir / "meta.json",
        json.dumps(meta, indent=2).encode("utf-8"),
    )


def read_placeholder_meta(placeholder_dir: Path) -> dict[str, object] | None:
    """Read ``placeholder_dir/meta.json`` if present.

    Args:
        placeholder_dir: Placeholder dir to inspect.

    Returns:
        Parsed dict on success, ``None`` if the file is absent (older
        placeholder dirs predating this helper) or contains invalid JSON.
        Callers handle ``None`` by falling back to a region default.
    """
    path = placeholder_dir / "meta.json"
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("Could not read placeholder meta at %s: %s", path, exc)
        return None
    if not isinstance(data, dict):
        return None
    return data


def cache_me_in_placeholder(placeholder_dir: Path, me_resp: object) -> None:
    """Cache the ``/me`` response in ``placeholder_dir/me.json``.

    Lets ``--resume`` skip the slow ``/me`` round-trip when the cache
    is still fresh (per :func:`load_cached_me_from_placeholder`'s TTL).
    The on-disk shape matches what :class:`MeCache` writes so a future
    refactor could share a single reader.

    Args:
        placeholder_dir: Target placeholder dir.
        me_resp: A :class:`MeResponse`. Typed as ``object`` to avoid a
            top-level import cycle (``me.py`` imports
            :func:`atomic_write_bytes` from ``io_utils.py``, which imports
            ``ConfigError`` from ``exceptions.py``; pulling
            ``MeResponse`` here at module load time is fine but dragging
            it into the public type would force every importer of
            ``inflight`` to also import the ``/me`` model).
    """
    from mixpanel_headless._internal.me import MeResponse

    if not isinstance(me_resp, MeResponse):  # defensive — public surface
        raise TypeError(f"Expected MeResponse, got {type(me_resp).__name__}")
    data = me_resp.model_dump(mode="json")
    data["cached_at"] = time.time()
    atomic_write_bytes(
        placeholder_dir / "me.json",
        json.dumps(data, indent=2, default=str).encode("utf-8"),
    )


def load_cached_me_from_placeholder(placeholder_dir: Path) -> object | None:
    """Return the cached :class:`MeResponse` if fresh, else ``None``.

    Freshness is defined as ``cached_at`` within :data:`INFLIGHT_TTL_SECONDS`
    of the current time. Stale or absent caches return ``None`` so the
    caller falls back to a fresh ``/me`` fetch — better to pay the round-
    trip than to publish an account against project metadata that drifted
    while the user was choosing.

    Args:
        placeholder_dir: Placeholder dir to inspect.

    Returns:
        :class:`MeResponse` if the cache is present and fresh, ``None``
        otherwise. Returns the model untyped to mirror
        :func:`cache_me_in_placeholder`'s parameter shape.
    """
    from mixpanel_headless._internal.me import MeResponse

    path = placeholder_dir / "me.json"
    if not path.exists():
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("Could not read cached me.json at %s: %s", path, exc)
        return None
    if not isinstance(raw, dict):
        return None
    cached_at = raw.get("cached_at")
    if isinstance(cached_at, (int, float)):
        age = time.time() - cached_at
        if age > INFLIGHT_TTL_SECONDS:
            return None
    try:
        return MeResponse.model_validate(raw)
    except Exception as exc:  # noqa: BLE001 — pydantic.ValidationError + friends
        logger.warning("Cached me.json at %s failed model validation: %s", path, exc)
        return None
