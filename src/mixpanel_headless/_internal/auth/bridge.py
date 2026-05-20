"""Auth bridge for Claude Cowork credential transfer (042 redesign — v2 schema).

The bridge is a JSON credential file that lets ``mixpanel_headless``
authenticate inside a Claude Cowork VM by reading credentials a host
process exported. It embeds a full :class:`Account` discriminated-union
record (with secrets inline by design — Cowork crosses a trust
boundary), optional project / workspace pinning, and a custom-headers
map. Loaded as a synthetic config source by
:func:`~mixpanel_headless._internal.auth.resolver.resolve_session`; the
writer side (Cluster C2 of the 042 plan — :func:`export_bridge` /
:func:`remove_bridge`) lives at the bottom of this module.

Bridge file search order (first existing file wins):
    1. Argument ``path`` to :func:`load_bridge` (if not None).
    2. ``MP_AUTH_FILE`` env var (if set).
    3. ``~/.claude/mixpanel/auth.json`` (default Cowork location).
    4. ``<cwd>/mixpanel_auth.json`` (workspace-mount fallback).

Reference: ``specs/042-auth-architecture-redesign/contracts/config-schema.md`` §2.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Annotated, Any, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    PositiveInt,
    SecretStr,
    TypeAdapter,
    ValidationError,
    model_validator,
)

from mixpanel_headless._internal.auth.account import (
    Account,
    OAuthBrowserAccount,
    OAuthTokenAccount,
    ServiceAccount,
    TokenResolver,
)
from mixpanel_headless._internal.auth.storage import account_dir
from mixpanel_headless._internal.auth.token import OAuthTokens
from mixpanel_headless._internal.io_utils import (
    atomic_write_bytes,
    read_credential_text,
)
from mixpanel_headless.exceptions import ConfigError, OAuthError

logger = logging.getLogger(__name__)


class BridgeFile(BaseModel):
    """Cowork credential bridge file — v2 schema.

    Embeds a full :class:`~mixpanel_headless._internal.auth.account.Account`
    record (with secrets inline) plus optional project / workspace pinning
    and a custom-headers map.

    Example:
        ```json
        {
          "version": 2,
          "account": {"type": "oauth_browser", "name": "personal", "region": "us"},
          "tokens": {"access_token": "...", "refresh_token": "...",
                     "expires_at": "2026-04-22T12:00:00Z",
                     "token_type": "Bearer", "scope": "read"},
          "project": "3713224",
          "workspace": 3448413,
          "headers": {"X-Mixpanel-Cluster": "internal-1"}
        }
        ```
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    version: Literal[2] = 2
    """Bridge schema version — always ``2``."""

    account: Account
    """Full Account discriminated-union record (with secrets inline by design)."""

    tokens: OAuthTokens | None = None
    """OAuth tokens — required iff ``account.type == "oauth_browser"``."""

    project: Annotated[str | None, Field(default=None, pattern=r"^\d+$")] = None
    """Optional pinned project ID (numeric string)."""

    workspace: PositiveInt | None = None
    """Optional pinned workspace ID."""

    headers: dict[str, str] = Field(default_factory=dict)
    """Custom HTTP headers attached to outbound requests at resolution time."""

    @model_validator(mode="after")
    def _validate_oauth_browser_has_tokens(self) -> BridgeFile:
        """Enforce that ``oauth_browser`` accounts include their tokens.

        Returns:
            The validated instance.

        Raises:
            ValueError: If ``account.type == "oauth_browser"`` and ``tokens``
                is missing.
        """
        if self.account.type == "oauth_browser" and self.tokens is None:
            raise ValueError("BridgeFile with oauth_browser account requires `tokens`.")
        return self


def default_bridge_search_paths() -> tuple[Path, ...]:
    """Return the default bridge file paths consulted in priority order.

    Returns:
        Tuple of candidate paths (default Cowork location first, then
        a ``mixpanel_auth.json`` in the current working directory). The
        ``MP_AUTH_FILE`` env var, if set, is consulted by callers BEFORE
        any default path.
    """
    return (
        Path.home() / ".claude" / "mixpanel" / "auth.json",
        Path.cwd() / "mixpanel_auth.json",
    )


_bridge_adapter: TypeAdapter[BridgeFile] = TypeAdapter(BridgeFile)


def load_bridge(path: Path | None = None) -> BridgeFile | None:
    """Load and validate a v2 bridge file from disk.

    Resolves the path in this order:

    1. Argument ``path`` (if not None).
    2. ``$MP_AUTH_FILE`` env var (if set).
    3. Default search paths (``~/.claude/mixpanel/auth.json``, then
       ``<cwd>/mixpanel_auth.json``) — first existing file wins.

    Args:
        path: Optional explicit bridge path.

    Returns:
        The parsed :class:`BridgeFile`, or ``None`` if no candidate
        path exists.

    Raises:
        ConfigError: If a candidate file exists but is malformed or fails
            schema validation.
    """
    candidates: list[Path] = []
    if path is not None:
        candidates.append(path)
    elif "MP_AUTH_FILE" in os.environ and os.environ["MP_AUTH_FILE"]:
        candidates.append(Path(os.environ["MP_AUTH_FILE"]))
    else:
        candidates.extend(default_bridge_search_paths())

    for candidate in candidates:
        if not candidate.exists():
            continue
        try:
            payload = json.loads(read_credential_text(candidate))
        except (OSError, json.JSONDecodeError) as exc:
            raise ConfigError(
                f"Could not read bridge file at {candidate}: {exc}",
                details={"path": str(candidate)},
            ) from exc
        try:
            return _bridge_adapter.validate_python(payload)
        except ValidationError as exc:
            raise ConfigError(
                f"Invalid bridge file at {candidate}: "
                f"{exc.errors(include_url=False)[0]['msg']}",
                details={"path": str(candidate)},
            ) from exc
    return None


def _read_browser_tokens(name: str) -> OAuthTokens:
    """Load on-disk OAuth tokens for an oauth_browser account.

    Reads from ``~/.mp/accounts/{name}/tokens.json`` directly (no refresh
    attempt — the bridge is a snapshot of whatever is currently on disk;
    if the bridge holder needs a refresh they can run
    ``mp account login NAME`` first). Tokens are wrapped in
    :class:`OAuthTokens` so the bridge file embeds them in the same
    Pydantic shape the resolver consumes on load.

    Args:
        name: Account name (used to locate the per-account tokens file).

    Returns:
        :class:`OAuthTokens` parsed from the on-disk payload.

    Raises:
        OAuthError: Tokens file missing, malformed, or missing required
            fields. The caller surfaces this verbatim — no retry / no
            refresh attempt.
    """
    path = account_dir(name) / "tokens.json"
    if not path.exists():
        raise OAuthError(
            f"No OAuth tokens found for account '{name}' at {path}. "
            f"Run `mp account login {name}` before exporting a bridge.",
            code="OAUTH_TOKEN_ERROR",
            details={"account_name": name, "path": str(path)},
        )
    try:
        payload = json.loads(read_credential_text(path))
    except (OSError, json.JSONDecodeError) as exc:
        raise OAuthError(
            f"Could not read OAuth tokens for account '{name}' from {path}: {exc}",
            code="OAUTH_TOKEN_ERROR",
            details={"account_name": name, "path": str(path)},
        ) from exc
    expires_raw = payload.get("expires_at")
    if not isinstance(expires_raw, str) or not expires_raw:
        raise OAuthError(
            f"OAuth tokens for account '{name}' are missing `expires_at`.",
            code="OAUTH_TOKEN_ERROR",
            details={"account_name": name, "path": str(path)},
        )
    try:
        expires_at = datetime.fromisoformat(expires_raw)
    except ValueError as exc:
        raise OAuthError(
            f"OAuth tokens for account '{name}' have an invalid `expires_at` value.",
            code="OAUTH_TOKEN_ERROR",
            details={"account_name": name, "path": str(path)},
        ) from exc
    access_token = payload.get("access_token")
    if not isinstance(access_token, str) or not access_token:
        raise OAuthError(
            f"OAuth tokens for account '{name}' are missing `access_token`.",
            code="OAUTH_TOKEN_ERROR",
            details={"account_name": name, "path": str(path)},
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


def _serialize_bridge(bridge: BridgeFile) -> bytes:
    """Serialize ``bridge`` to UTF-8 JSON bytes with secrets unwrapped.

    Pydantic ``SecretStr`` round-trips as ``"**********"`` by default; for
    a bridge file we MUST emit the actual secret values inline (B3 — the
    bridge crosses a trust boundary by design). Uses ``model_dump`` with
    ``warnings=False`` then walks the result to unwrap secret strings.

    Args:
        bridge: Validated bridge model.

    Returns:
        UTF-8 encoded JSON bytes ready for atomic write.
    """
    payload = bridge.model_dump(mode="json", exclude_none=True)
    # Pydantic redacts SecretStr by default in mode="json"; reach back to
    # the original bridge instance for the raw secret values so the bridge
    # actually carries usable credentials.
    account_payload: dict[str, Any] = payload.get("account", {})
    raw_account = bridge.account
    if isinstance(raw_account, ServiceAccount):
        account_payload["secret"] = raw_account.secret.get_secret_value()
    elif isinstance(raw_account, OAuthTokenAccount) and raw_account.token is not None:
        account_payload["token"] = raw_account.token.get_secret_value()
    if bridge.tokens is not None:
        tokens_payload: dict[str, Any] = payload.get("tokens", {})
        tokens_payload["access_token"] = bridge.tokens.access_token.get_secret_value()
        if bridge.tokens.refresh_token is not None:
            tokens_payload["refresh_token"] = (
                bridge.tokens.refresh_token.get_secret_value()
            )
        payload["tokens"] = tokens_payload
    payload["account"] = account_payload
    return json.dumps(payload, indent=2, sort_keys=True).encode("utf-8")


def export_bridge(
    account: Account,
    *,
    to: Path,
    project: str | None = None,
    workspace: int | None = None,
    headers: dict[str, str] | None = None,
    token_resolver: TokenResolver | None = None,  # noqa: ARG001 — kept for signature parity (uses on-disk reader directly)
) -> Path:
    """Write a v2 bridge file at ``to`` embedding ``account``'s full record.

    For ``oauth_browser`` accounts, reads the current on-disk tokens via
    :func:`_read_browser_tokens` and embeds them under ``tokens``; the
    bridge consumer then has everything it needs to authenticate without
    re-running the PKCE flow. For ``service_account`` and ``oauth_token``
    the secrets travel inline with the account record (B3).

    Atomic on-disk write per :func:`atomic_write_bytes` — the bridge
    consumer never observes a half-written file.

    Args:
        account: Account to embed (full record, secrets inline by design).
        to: Destination path for the bridge file.
        project: Optional pinned project ID (must match ``^\\d+$``).
        workspace: Optional pinned workspace ID (positive int).
        headers: Optional custom HTTP headers map.
        token_resolver: Reserved for future per-account refresh hooks; the
            current implementation reads tokens directly from
            ``~/.mp/accounts/{name}/tokens.json``. Accepted for signature
            parity with the contract.

    Returns:
        The path that was written (same as ``to``).

    Raises:
        OAuthError: ``account.type == "oauth_browser"`` but on-disk tokens
            are missing / malformed.
        ConfigError: ``BridgeFile`` validation fails (bad project format,
            etc.).
    """
    tokens: OAuthTokens | None = None
    if isinstance(account, OAuthBrowserAccount):
        tokens = _read_browser_tokens(account.name)
    bridge = BridgeFile(
        version=2,
        account=account,
        tokens=tokens,
        project=project,
        workspace=workspace,
        headers=headers or {},
    )
    parent = to.parent
    if not parent.exists():
        parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    atomic_write_bytes(to, _serialize_bridge(bridge), mode=0o600)
    return to


def remove_bridge(*, at: Path | None = None) -> bool:
    """Delete the bridge file at ``at`` (or the resolved default path).

    Resolves the path the same way :func:`load_bridge` does:

    1. ``at`` argument (if not None).
    2. ``$MP_AUTH_FILE`` env var (if set).
    3. First existing default search path.

    Idempotent — returns ``False`` if no bridge file exists at the
    resolved path; the caller can still treat that as "removed" per the
    contract (``mp account remove-bridge`` exits 0 in both cases).

    Args:
        at: Optional explicit bridge path.

    Returns:
        ``True`` if a file was deleted; ``False`` if none was found.
    """
    if at is not None:
        target: Path | None = at
    elif os.environ.get("MP_AUTH_FILE"):
        target = Path(os.environ["MP_AUTH_FILE"])
    else:
        target = next((p for p in default_bridge_search_paths() if p.exists()), None)
    if target is None or not target.exists():
        return False
    target.unlink()
    return True


__all__ = [
    "BridgeFile",
    "default_bridge_search_paths",
    "export_bridge",
    "load_bridge",
    "remove_bridge",
]
