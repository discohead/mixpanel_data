"""Shared fixtures for the 042 auth-redesign live QA module.

Provides:
- Tmp v3 home isolation (so the user's real ~/.mp/ is never touched)
- Helpers to copy the user's existing OAuth tokens into the tmp layout
- Per-mode skip fixtures that gate tests on credential availability

Reference: ~/.claude/plans/design-a-qa-plan-vast-wall.md.
"""

from __future__ import annotations

import json
import os
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

# Where the user's real (legacy v2) OAuth tokens live, if they've logged in.
LEGACY_TOKENS_PATH = Path.home() / ".mp" / "oauth" / "tokens_us.json"
LEGACY_CONFIG_PATH = Path.home() / ".mp" / "config.toml"


# =============================================================================
# Tmp v3 home isolation
# =============================================================================


@pytest.fixture
def tmp_mp_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    """Yield a tmp ``$HOME`` with isolated v3 ``~/.mp/`` and ``MP_CONFIG_PATH``.

    Sets HOME, MP_CONFIG_PATH, MP_OAUTH_STORAGE_DIR; creates ~/.mp/ at
    mode 0o700; yields the tmp HOME path. The dev's real ~/.mp/ is
    completely untouched.

    Yields:
        Path to the tmp $HOME root.
    """
    mp_dir = tmp_path / ".mp"
    mp_dir.mkdir(mode=0o700)
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("MP_CONFIG_PATH", str(mp_dir / "config.toml"))
    monkeypatch.setenv("MP_OAUTH_STORAGE_DIR", str(mp_dir / "oauth"))
    yield tmp_path


# =============================================================================
# Token-copy helper
# =============================================================================


def copy_user_oauth_tokens_to_account(home: Path, account_name: str) -> Path:
    """Copy the user's real ~/.mp/oauth/tokens_us.json into the v3 layout.

    Reads from ``~/.mp/oauth/tokens_us.json`` (the user's actual on-disk
    tokens from their existing v2 OAuth account) and writes them to
    ``<home>/.mp/accounts/<account_name>/tokens.json`` per the new v3 path
    convention. Strips the legacy ``project_id`` field (Phase 4 drops it).

    Args:
        home: The tmp $HOME path (from the ``tmp_mp_home`` fixture).
        account_name: V3 account name to host the tokens under.

    Returns:
        Path to the new tokens.json.

    Raises:
        FileNotFoundError: If the user's legacy tokens file doesn't exist
            (no real OAuth login configured).
    """
    if not LEGACY_TOKENS_PATH.exists():
        raise FileNotFoundError(
            f"User's legacy OAuth tokens not found at {LEGACY_TOKENS_PATH}. "
            "Live OAuth tests require a prior `mp account login NAME`."
        )
    payload: dict[str, Any] = json.loads(LEGACY_TOKENS_PATH.read_text(encoding="utf-8"))
    payload.pop("project_id", None)  # v3 drops this field

    account_dir = home / ".mp" / "accounts" / account_name
    account_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    dst = account_dir / "tokens.json"
    dst.write_text(json.dumps(payload), encoding="utf-8")
    dst.chmod(0o600)
    return dst


def get_user_active_project_id() -> str | None:
    """Read the project ID from the user's real config (v1/v2/v3 tolerant).

    Returns:
        The first project_id we can find, or None.
    """
    if not LEGACY_CONFIG_PATH.exists():
        return None
    try:
        import sys

        if sys.version_info >= (3, 11):
            import tomllib
        else:  # pragma: no cover
            import tomli as tomllib  # type: ignore[import-not-found, unused-ignore]
        raw: dict[str, Any] = tomllib.loads(
            LEGACY_CONFIG_PATH.read_text(encoding="utf-8")
        )
    except Exception:  # noqa: BLE001 - any parse failure → no project
        return None
    # v2 layout
    active = raw.get("active", {})
    pid = active.get("project_id")
    if isinstance(pid, str):
        return pid
    if isinstance(pid, int):
        return str(pid)
    # v3 layout
    pid = active.get("project")
    if isinstance(pid, str):
        return pid
    return None


# =============================================================================
# Per-mode skip fixtures
# =============================================================================


def _oauth_token_is_fresh() -> bool:
    """Check whether the user's OAuth token at ``LEGACY_TOKENS_PATH`` is unexpired.

    Returns:
        ``True`` if the tokens file exists and its ``expires_at`` is in the
        future (with 60s buffer). ``False`` otherwise.
    """
    from datetime import datetime, timedelta, timezone

    if not LEGACY_TOKENS_PATH.exists():
        return False
    try:
        payload: dict[str, Any] = json.loads(
            LEGACY_TOKENS_PATH.read_text(encoding="utf-8")
        )
        expires_raw = payload.get("expires_at")
        if not isinstance(expires_raw, str):
            return False
        expires_at = datetime.fromisoformat(expires_raw)
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        return expires_at > datetime.now(timezone.utc) + timedelta(seconds=60)
    except (json.JSONDecodeError, ValueError, OSError):
        return False


@pytest.fixture
def require_oauth_browser_available() -> None:
    """Skip if the user has no real (and unexpired) OAuth tokens on disk.

    We check both presence AND freshness — an expired token would cause the
    Mixpanel server to return 401 even though our code is sending the right
    bearer, and we'd misread the failure as a code bug.
    """
    if not LEGACY_TOKENS_PATH.exists():
        pytest.skip(
            f"OAuth browser mode requires real tokens at {LEGACY_TOKENS_PATH} "
            "(run `mp account login NAME` first)."
        )
    if not _oauth_token_is_fresh():
        pytest.skip(
            f"OAuth tokens at {LEGACY_TOKENS_PATH} are expired. "
            "Run `mp account login NAME` to refresh, then re-run these tests."
        )


_SA_CHECK_RESULT: tuple[bool, str | None] | None = None
_TOKEN_CHECK_RESULT: tuple[bool, str | None] | None = None


def _probe_sa_credentials() -> tuple[bool, str | None]:
    """One-time live probe: are the MP_LIVE_SA_* creds accepted by Mixpanel?

    Caches the result for the rest of the pytest session.

    Returns:
        ``(True, None)`` if the SA creds authenticate against the events
        endpoint. ``(False, reason)`` otherwise.
    """
    global _SA_CHECK_RESULT
    if _SA_CHECK_RESULT is not None:
        return _SA_CHECK_RESULT
    required = (
        "MP_LIVE_SA_USERNAME",
        "MP_LIVE_SA_SECRET",
        "MP_LIVE_SA_PROJECT_ID",
        "MP_LIVE_SA_REGION",
    )
    missing = [v for v in required if not os.environ.get(v)]
    if missing:
        _SA_CHECK_RESULT = (False, f"missing env vars: {missing}")
        return _SA_CHECK_RESULT
    # Live probe — make a single events() call to confirm Mixpanel accepts.
    import os as _os

    saved_env = {
        k: _os.environ.get(k)
        for k in ("MP_USERNAME", "MP_SECRET", "MP_PROJECT_ID", "MP_REGION")
    }
    try:
        _os.environ["MP_USERNAME"] = _os.environ["MP_LIVE_SA_USERNAME"]
        _os.environ["MP_SECRET"] = _os.environ["MP_LIVE_SA_SECRET"]
        _os.environ["MP_PROJECT_ID"] = _os.environ["MP_LIVE_SA_PROJECT_ID"]
        _os.environ["MP_REGION"] = _os.environ["MP_LIVE_SA_REGION"]
        from mixpanel_headless import Workspace as _Workspace

        ws = _Workspace()
        try:
            ws.events()
            _SA_CHECK_RESULT = (True, None)
        finally:
            ws.close()
    except Exception as exc:  # noqa: BLE001 — capture any auth-related failure
        _SA_CHECK_RESULT = (False, f"Mixpanel rejected credentials: {exc}")
    finally:
        for k, v in saved_env.items():
            if v is None:
                _os.environ.pop(k, None)
            else:
                _os.environ[k] = v
    return _SA_CHECK_RESULT


def _probe_static_token() -> tuple[bool, str | None]:
    """One-time live probe: is MP_LIVE_OAUTH_TOKEN accepted by Mixpanel?

    Returns:
        ``(True, None)`` on success, ``(False, reason)`` otherwise.
    """
    global _TOKEN_CHECK_RESULT
    if _TOKEN_CHECK_RESULT is not None:
        return _TOKEN_CHECK_RESULT
    required = ("MP_LIVE_OAUTH_TOKEN", "MP_LIVE_PROJECT_ID", "MP_LIVE_REGION")
    missing = [v for v in required if not os.environ.get(v)]
    if missing:
        _TOKEN_CHECK_RESULT = (False, f"missing env vars: {missing}")
        return _TOKEN_CHECK_RESULT
    import os as _os

    saved_env = {
        k: _os.environ.get(k) for k in ("MP_OAUTH_TOKEN", "MP_PROJECT_ID", "MP_REGION")
    }
    try:
        _os.environ["MP_OAUTH_TOKEN"] = _os.environ["MP_LIVE_OAUTH_TOKEN"]
        _os.environ["MP_PROJECT_ID"] = _os.environ["MP_LIVE_PROJECT_ID"]
        _os.environ["MP_REGION"] = _os.environ["MP_LIVE_REGION"]
        from mixpanel_headless import Workspace as _Workspace

        ws = _Workspace()
        try:
            ws.events()
            _TOKEN_CHECK_RESULT = (True, None)
        finally:
            ws.close()
    except Exception as exc:  # noqa: BLE001
        _TOKEN_CHECK_RESULT = (False, f"Mixpanel rejected bearer: {exc}")
    finally:
        for k, v in saved_env.items():
            if v is None:
                _os.environ.pop(k, None)
            else:
                _os.environ[k] = v
    return _TOKEN_CHECK_RESULT


@pytest.fixture
def require_sa_env_available() -> None:
    """Skip unless MP_LIVE_SA_* env vars are set AND Mixpanel accepts them.

    The probe runs once per pytest session; subsequent tests reuse the
    cached result.
    """
    ok, reason = _probe_sa_credentials()
    if not ok:
        pytest.skip(f"SA mode unavailable: {reason}")


@pytest.fixture
def require_oauth_token_available() -> None:
    """Skip unless MP_LIVE_OAUTH_TOKEN is set AND Mixpanel accepts it.

    The probe runs once per pytest session; subsequent tests reuse the
    cached result.
    """
    ok, reason = _probe_static_token()
    if not ok:
        pytest.skip(f"OAuth token mode unavailable: {reason}")


@pytest.fixture
def live_sa_creds(require_sa_env_available: None) -> dict[str, str]:
    """Return the SA credentials from ``MP_LIVE_SA_*`` env vars.

    Args:
        require_sa_env_available: Skip-fixture dependency.

    Returns:
        Dict with username / secret / project_id / region keys.
    """
    return {
        "username": os.environ["MP_LIVE_SA_USERNAME"],
        "secret": os.environ["MP_LIVE_SA_SECRET"],
        "project_id": os.environ["MP_LIVE_SA_PROJECT_ID"],
        "region": os.environ["MP_LIVE_SA_REGION"],
    }


@pytest.fixture
def live_oauth_token_creds(
    require_oauth_token_available: None,
) -> dict[str, str]:
    """Return the static OAuth token credentials from ``MP_LIVE_*`` env vars.

    Args:
        require_oauth_token_available: Skip-fixture dependency.

    Returns:
        Dict with token / project_id / region keys.
    """
    return {
        "token": os.environ["MP_LIVE_OAUTH_TOKEN"],
        "project_id": os.environ["MP_LIVE_PROJECT_ID"],
        "region": os.environ["MP_LIVE_REGION"],
    }
