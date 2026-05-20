"""Unit tests for the ``TokenResolver`` protocol and ``OnDiskTokenResolver`` (T010).

Covers:
- ``OnDiskTokenResolver.get_browser_token(name, region)`` reads from
  ``~/.mp/accounts/{name}/tokens.json`` and refreshes if expired.
- ``OnDiskTokenResolver.get_static_token(account)`` reads inline token or
  env var via ``token_env``.
- Raises ``OAuthError`` if env var unset / browser tokens missing or unrefreshable.

Reference: specs/042-auth-architecture-redesign/data-model.md §2, contracts/python-api.md §5.
"""

from __future__ import annotations

import json
import os
import stat
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from pydantic import SecretStr

from mixpanel_headless._internal.auth.account import (
    OAuthTokenAccount,
)
from mixpanel_headless._internal.auth.token_resolver import OnDiskTokenResolver
from mixpanel_headless.exceptions import OAuthError

_REQUIRES_O_NOFOLLOW = pytest.mark.skipif(
    not hasattr(os, "O_NOFOLLOW"),
    reason="O_NOFOLLOW required; Windows is not in scope",
)


@pytest.fixture
def isolated_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Use a tmp directory as ``$HOME`` for isolated ``~/.mp/accounts/`` paths."""
    monkeypatch.setenv("HOME", str(tmp_path))
    return tmp_path


def _write_tokens_file(
    home: Path,
    *,
    name: str,
    access_token: str,
    expires_at: datetime,
    refresh_token: str | None = None,
) -> Path:
    """Write a tokens.json file at ``~/.mp/accounts/{name}/tokens.json`` mode 0o600.

    Args:
        home: Tmp HOME path.
        name: Account name (becomes the dir under accounts/).
        access_token: Access token plaintext to embed.
        expires_at: Expiry datetime (use a past time to simulate expiry).
        refresh_token: Optional refresh token plaintext.

    Returns:
        The path that was written.
    """
    account_dir = home / ".mp" / "accounts" / name
    account_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    path = account_dir / "tokens.json"
    payload: dict[str, object] = {
        "access_token": access_token,
        "expires_at": expires_at.isoformat(),
        "scope": "read:project",
        "token_type": "Bearer",
    }
    if refresh_token is not None:
        payload["refresh_token"] = refresh_token
    path.write_text(json.dumps(payload), encoding="utf-8")
    path.chmod(0o600)
    return path


class TestStaticToken:
    """Coverage for ``get_static_token``: inline + env-var paths."""

    def test_inline_token_returned(self, isolated_home: Path) -> None:
        """Inline ``token`` field is returned verbatim."""
        account = OAuthTokenAccount(
            name="ci", region="us", token=SecretStr("inline-tok-123")
        )
        resolver = OnDiskTokenResolver()
        assert resolver.get_static_token(account) == "inline-tok-123"

    def test_env_var_returned(
        self, isolated_home: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """``token_env`` is read from ``os.environ`` at resolution time."""
        monkeypatch.setenv("MY_OAUTH_TOK", "env-tok-456")
        account = OAuthTokenAccount(name="ci", region="us", token_env="MY_OAUTH_TOK")
        resolver = OnDiskTokenResolver()
        assert resolver.get_static_token(account) == "env-tok-456"

    def test_env_var_missing_raises(
        self, isolated_home: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Missing env var raises ``OAuthError``."""
        monkeypatch.delenv("MY_OAUTH_TOK", raising=False)
        account = OAuthTokenAccount(name="ci", region="us", token_env="MY_OAUTH_TOK")
        resolver = OnDiskTokenResolver()
        with pytest.raises(OAuthError):
            resolver.get_static_token(account)

    def test_env_var_empty_raises(
        self, isolated_home: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Empty env var (e.g. ``MY_OAUTH_TOK=``) raises ``OAuthError``.

        Empty strings are not valid bearers.
        """
        monkeypatch.setenv("MY_OAUTH_TOK", "")
        account = OAuthTokenAccount(name="ci", region="us", token_env="MY_OAUTH_TOK")
        resolver = OnDiskTokenResolver()
        with pytest.raises(OAuthError):
            resolver.get_static_token(account)


class TestBrowserToken:
    """Coverage for ``get_browser_token``: on-disk reads + refresh."""

    def test_unexpired_token_returned(self, isolated_home: Path) -> None:
        """A non-expired token on disk is returned without refresh."""
        future = datetime.now(timezone.utc) + timedelta(hours=1)
        _write_tokens_file(
            isolated_home,
            name="me",
            access_token="brw-tok-fresh",
            expires_at=future,
            refresh_token="ref-1",
        )
        resolver = OnDiskTokenResolver()
        assert resolver.get_browser_token("me", "us") == "brw-tok-fresh"

    def test_missing_tokens_file_raises(self, isolated_home: Path) -> None:
        """Missing tokens.json raises ``OAuthError``."""
        resolver = OnDiskTokenResolver()
        with pytest.raises(OAuthError):
            resolver.get_browser_token("nobody", "us")

    def test_expired_without_refresh_raises(self, isolated_home: Path) -> None:
        """Expired token with no refresh token raises ``OAuthError``."""
        past = datetime.now(timezone.utc) - timedelta(hours=1)
        _write_tokens_file(
            isolated_home,
            name="me",
            access_token="brw-tok-old",
            expires_at=past,
            refresh_token=None,
        )
        resolver = OnDiskTokenResolver()
        with pytest.raises(OAuthError):
            resolver.get_browser_token("me", "us")

    def test_account_dir_is_isolated_per_name(self, isolated_home: Path) -> None:
        """Two accounts get independent token files at distinct dirs."""
        future = datetime.now(timezone.utc) + timedelta(hours=1)
        _write_tokens_file(
            isolated_home, name="alice", access_token="A", expires_at=future
        )
        _write_tokens_file(
            isolated_home, name="bob", access_token="B", expires_at=future
        )
        resolver = OnDiskTokenResolver()
        assert resolver.get_browser_token("alice", "us") == "A"
        assert resolver.get_browser_token("bob", "us") == "B"

    def test_token_within_30s_buffer_treated_as_expired(
        self, isolated_home: Path
    ) -> None:
        """Tokens expiring within the 30s safety buffer must be refreshed.

        The docstring on ``get_browser_token`` promises a 30s safety
        buffer so requests in flight can't be tripped by a token that
        expires between the check and the network call. A token whose
        ``expires_at`` is 20 seconds away must therefore be treated as
        expired (and raise here, since refresh is unimplemented and no
        refresh token is provided).
        """
        soon = datetime.now(timezone.utc) + timedelta(seconds=20)
        _write_tokens_file(
            isolated_home,
            name="me",
            access_token="brw-tok-soon-to-expire",
            expires_at=soon,
            refresh_token=None,
        )
        resolver = OnDiskTokenResolver()
        with pytest.raises(OAuthError):
            resolver.get_browser_token("me", "us")

    def test_token_well_outside_buffer_is_accepted(self, isolated_home: Path) -> None:
        """A token with > 30s remaining is still accepted.

        Boundary check on the buffer: 5 minutes out should comfortably
        pass even with the new safety margin in place.
        """
        future = datetime.now(timezone.utc) + timedelta(minutes=5)
        _write_tokens_file(
            isolated_home,
            name="me",
            access_token="brw-tok-comfortable",
            expires_at=future,
            refresh_token=None,
        )
        resolver = OnDiskTokenResolver()
        assert resolver.get_browser_token("me", "us") == "brw-tok-comfortable"


class TestBrowserTokenRefresh:
    """Coverage for Fix 16: expired-but-refreshable browser tokens auto-refresh."""

    def test_expired_with_refresh_token_calls_oauth_flow(
        self,
        isolated_home: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """An expired token with a refresh token routes through ``OAuthFlow.refresh_tokens``."""
        from mixpanel_headless._internal.auth import flow as flow_mod
        from mixpanel_headless._internal.auth import storage as storage_mod
        from mixpanel_headless._internal.auth.token import OAuthClientInfo, OAuthTokens

        past = datetime.now(timezone.utc) - timedelta(hours=1)
        path = _write_tokens_file(
            isolated_home,
            name="me",
            access_token="brw-tok-old",
            expires_at=past,
            refresh_token="brw-refresh-1",
        )

        # Stub OAuthStorage.load_client_info — return a fake DCR registration.
        def _fake_load_client_info(self: object, *, region: str) -> OAuthClientInfo:
            """Return canned client info regardless of region."""
            return OAuthClientInfo(
                client_id="dcr-client-1",
                region=region,
                redirect_uri="http://localhost:19284/callback",
                scope="read:project",
                created_at=datetime.now(timezone.utc),
            )

        monkeypatch.setattr(
            storage_mod.OAuthStorage, "load_client_info", _fake_load_client_info
        )

        # Stub OAuthFlow.refresh_tokens — capture the call args, return new tokens.
        captured: dict[str, object] = {}
        new_expires = datetime.now(timezone.utc) + timedelta(hours=1)

        def _fake_refresh(
            self: object,
            *,
            tokens: OAuthTokens,
            client_id: str,
            account_name: str | None = None,
        ) -> OAuthTokens:
            """Return refreshed tokens; record the inputs for assertions."""
            captured["client_id"] = client_id
            captured["account_name"] = account_name
            captured["refresh_token_in"] = (
                tokens.refresh_token.get_secret_value()
                if tokens.refresh_token
                else None
            )
            return OAuthTokens(
                access_token=SecretStr("brw-tok-new"),
                refresh_token=SecretStr("brw-refresh-2"),
                expires_at=new_expires,
                scope="read:project",
                token_type="Bearer",
            )

        monkeypatch.setattr(flow_mod.OAuthFlow, "refresh_tokens", _fake_refresh)

        resolver = OnDiskTokenResolver()
        result = resolver.get_browser_token("me", "us")

        assert result == "brw-tok-new"
        assert captured["client_id"] == "dcr-client-1"
        assert captured["refresh_token_in"] == "brw-refresh-1"
        # Per-account file is rewritten with the new payload.
        new_payload = json.loads(path.read_text(encoding="utf-8"))
        assert new_payload["access_token"] == "brw-tok-new"
        assert new_payload["refresh_token"] == "brw-refresh-2"
        assert new_payload["expires_at"] == new_expires.isoformat()
        # File mode preserved at 0o600.
        assert (path.stat().st_mode & 0o777) == 0o600

    def test_refresh_response_without_new_refresh_keeps_existing(
        self,
        isolated_home: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """If the IdP omits a rotated refresh token the existing one is preserved."""
        from mixpanel_headless._internal.auth import flow as flow_mod
        from mixpanel_headless._internal.auth import storage as storage_mod
        from mixpanel_headless._internal.auth.token import OAuthClientInfo, OAuthTokens

        past = datetime.now(timezone.utc) - timedelta(hours=1)
        path = _write_tokens_file(
            isolated_home,
            name="me",
            access_token="brw-tok-old",
            expires_at=past,
            refresh_token="long-lived-refresh",
        )
        monkeypatch.setattr(
            storage_mod.OAuthStorage,
            "load_client_info",
            lambda _self, *, region: OAuthClientInfo(
                client_id="c1",
                region=region,
                redirect_uri="http://localhost:19284/callback",
                scope="read:project",
                created_at=datetime.now(timezone.utc),
            ),
        )
        monkeypatch.setattr(
            flow_mod.OAuthFlow,
            "refresh_tokens",
            lambda _self, *, tokens, client_id, account_name=None: OAuthTokens(  # noqa: ARG005
                access_token=SecretStr("brw-tok-new"),
                refresh_token=None,  # IdP didn't rotate
                expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
                scope="read:project",
                token_type="Bearer",
            ),
        )

        resolver = OnDiskTokenResolver()
        assert resolver.get_browser_token("me", "us") == "brw-tok-new"
        new_payload = json.loads(path.read_text(encoding="utf-8"))
        assert new_payload["refresh_token"] == "long-lived-refresh"

    def test_refresh_without_client_info_raises_oauth_refresh_error(
        self,
        isolated_home: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Missing DCR client info surfaces an actionable ``OAUTH_REFRESH_ERROR``."""
        from mixpanel_headless._internal.auth import storage as storage_mod

        past = datetime.now(timezone.utc) - timedelta(hours=1)
        _write_tokens_file(
            isolated_home,
            name="me",
            access_token="brw-tok-old",
            expires_at=past,
            refresh_token="r1",
        )
        monkeypatch.setattr(
            storage_mod.OAuthStorage,
            "load_client_info",
            lambda _self, *, region: None,  # noqa: ARG005
        )

        resolver = OnDiskTokenResolver()
        with pytest.raises(OAuthError) as exc_info:
            resolver.get_browser_token("me", "us")
        assert exc_info.value.code == "OAUTH_REFRESH_ERROR"


class TestPathLayout:
    """File system layout invariants per contracts/filesystem-layout.md §3."""

    def test_account_dir_path(self, isolated_home: Path) -> None:
        """Resolver computes ``~/.mp/accounts/{name}/tokens.json`` for a given name."""
        future = datetime.now(timezone.utc) + timedelta(hours=1)
        path = _write_tokens_file(
            isolated_home, name="me", access_token="x", expires_at=future
        )
        assert path == isolated_home / ".mp" / "accounts" / "me" / "tokens.json"

    def test_account_dir_permissions(self, isolated_home: Path) -> None:
        """Account dir written with mode 0o700 by helper."""
        future = datetime.now(timezone.utc) + timedelta(hours=1)
        _write_tokens_file(
            isolated_home, name="me", access_token="x", expires_at=future
        )
        d = isolated_home / ".mp" / "accounts" / "me"
        if os.name == "posix":
            assert stat.S_IMODE(d.stat().st_mode) == 0o700


class TestConcurrentRefresh:
    """Two threads racing to refresh the same expired browser token.

    The realistic scenario: an in-process Workspace fans out N parallel API
    calls; each lazily resolves the bearer; they all observe the same
    expired ``tokens.json`` and race ``_refresh_and_persist``. The contract
    we want to lock:

    1. Both callers receive a valid (non-empty) access token.
    2. The on-disk ``tokens.json`` parses cleanly (no torn write).
    3. The IdP is called once-per-thread — there is no single-flight guard
       at this layer (a future enhancement could add one; for now we
       document the actual behaviour).
    """

    def test_two_threads_racing_refresh_both_get_tokens_and_disk_is_valid(
        self, isolated_home: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Two threads race ``_refresh_and_persist``; assert the contract above."""
        import threading

        from mixpanel_headless._internal.auth import flow as flow_mod
        from mixpanel_headless._internal.auth import storage as storage_mod
        from mixpanel_headless._internal.auth.token import (
            OAuthClientInfo,
            OAuthTokens,
        )

        # Seed an expired tokens.json with a refresh token.
        past = datetime.now(timezone.utc) - timedelta(hours=1)
        path = _write_tokens_file(
            isolated_home,
            name="me",
            access_token="expired-tok",
            expires_at=past,
            refresh_token="brw-refresh-1",
        )

        # Stub DCR client info so the resolver doesn't try to read disk.
        monkeypatch.setattr(
            storage_mod.OAuthStorage,
            "load_client_info",
            lambda _self, *, region: OAuthClientInfo(  # noqa: ARG005
                client_id="dcr-client-1",
                region="us",
                redirect_uri="http://localhost:8765/callback",
                scope="read:project",
                created_at=datetime.now(timezone.utc),
            ),
        )

        # Use a Barrier to release both threads into ``refresh_tokens`` at the
        # same instant, maximising the window where they would have collided
        # on a fixed tmp filename. ``atomic_write_bytes`` derives tmp paths
        # from pid+tid so each thread picks a distinct one.
        barrier = threading.Barrier(2)
        gate = threading.Event()
        call_count = 0
        call_lock = threading.Lock()
        new_expires = datetime.now(timezone.utc) + timedelta(hours=1)

        def _fake_refresh(
            self: object,
            *,
            tokens: OAuthTokens,
            client_id: str,  # noqa: ARG001
            account_name: str | None = None,  # noqa: ARG001
        ) -> OAuthTokens:
            """Return refreshed tokens after a controlled barrier sync."""
            nonlocal call_count
            with call_lock:
                call_count += 1
                my_n = call_count
            # Both threads wait at the barrier; the test thread releases
            # them via ``gate.set()`` so they enter the write path together.
            barrier.wait(timeout=2)
            gate.wait(timeout=2)
            return OAuthTokens(
                access_token=SecretStr(f"brw-tok-new-{my_n}"),
                refresh_token=SecretStr(f"brw-refresh-{my_n + 1}"),
                expires_at=new_expires,
                scope="read:project",
                token_type="Bearer",
            )

        monkeypatch.setattr(flow_mod.OAuthFlow, "refresh_tokens", _fake_refresh)

        results: list[str | BaseException] = [None, None]  # type: ignore[list-item]

        def _worker(idx: int) -> None:
            try:
                resolver = OnDiskTokenResolver()
                results[idx] = resolver.get_browser_token("me", "us")
            except BaseException as exc:  # noqa: BLE001 — surface to assertion
                results[idx] = exc

        t1 = threading.Thread(target=_worker, args=(0,))
        t2 = threading.Thread(target=_worker, args=(1,))
        t1.start()
        t2.start()
        # Give both threads time to reach the barrier in the stub.
        gate.set()
        t1.join(timeout=5)
        t2.join(timeout=5)

        # Both calls returned tokens (no exception).
        for r in results:
            assert isinstance(r, str), f"thread raised: {r!r}"
            assert r.startswith("brw-tok-new-")

        # Final on-disk file parses cleanly (no torn / partial write).
        payload = json.loads(path.read_text(encoding="utf-8"))
        assert payload["access_token"].startswith("brw-tok-new-")
        assert payload["refresh_token"].startswith("brw-refresh-")
        # Both threads triggered an IdP call (the resolver does NOT have a
        # single-flight guard; this assertion documents the current behaviour).
        assert call_count == 2


class TestSymlinkRejection:
    """``get_browser_token`` refuses a symlinked ``tokens.json``.

    Regression for the same-UID symlink attack covered by
    ``io_utils.read_credential_bytes``. The error is surfaced through
    the existing ``OAuthError`` translation in
    ``OnDiskTokenResolver.get_browser_token`` so the CLI output stays
    domain-specific.
    """

    @_REQUIRES_O_NOFOLLOW
    def test_symlinked_tokens_raises_oautherror(self, isolated_home: Path) -> None:
        """Symlinked tokens.json yields OAuthError with the symlink path named."""
        account_dir = isolated_home / ".mp" / "accounts" / "personal"
        account_dir.mkdir(parents=True, mode=0o700)
        future = datetime.now(timezone.utc) + timedelta(hours=1)
        attacker = isolated_home / "attacker_tokens.json"
        attacker.write_text(
            json.dumps(
                {
                    "access_token": "stolen-acc",
                    "expires_at": future.isoformat(),
                    "token_type": "Bearer",
                    "scope": "read:project",
                }
            ),
            encoding="utf-8",
        )
        attacker.chmod(0o600)
        (account_dir / "tokens.json").symlink_to(attacker)
        resolver = OnDiskTokenResolver()
        with pytest.raises(OAuthError, match="symlink"):
            resolver.get_browser_token("personal", "us")

    @_REQUIRES_O_NOFOLLOW
    def test_dangling_symlink_tokens_raises_oautherror(
        self, isolated_home: Path
    ) -> None:
        """A dangling symlink at tokens.json raises ``OAuthError``.

        Regression for the ``Path.exists()`` follows-symlink trap:
        without the new ``reject_if_symlink`` probe, a dangling symlink
        would surface as ``OAuthError("No OAuth tokens found... Run `mp
        account login`")`` instead of the symlink-specific message, and
        ``mp login`` would then try to write through the symlink.
        """
        account_dir = isolated_home / ".mp" / "accounts" / "personal"
        account_dir.mkdir(parents=True, mode=0o700)
        (account_dir / "tokens.json").symlink_to(isolated_home / "missing.json")
        resolver = OnDiskTokenResolver()
        with pytest.raises(OAuthError, match="symlink"):
            resolver.get_browser_token("personal", "us")
