"""Edge-case backstop for the 042 auth redesign (QA).

Hunts for sneaky bugs in the new auth subsystem that the contract tests
don't explicitly cover: boundary conditions, sentinel-vs-None semantics,
malformed on-disk artifacts, partial env-var quads, and CLI exit-code
contracts.

These are pure-unit tests — no live API. They run in milliseconds and
serve as a permanent regression backstop against the bug surface
identified by the QA exploration pass.

Reference: ~/.claude/plans/design-a-qa-plan-vast-wall.md.
"""

from __future__ import annotations

import json
import os
import stat
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pytest
from pydantic import SecretStr, TypeAdapter, ValidationError
from typer.testing import CliRunner

from mixpanel_headless._internal.auth.account import (
    Account,
    OAuthBrowserAccount,
    OAuthTokenAccount,
    ServiceAccount,
)
from mixpanel_headless._internal.auth.bridge import BridgeFile, load_bridge
from mixpanel_headless._internal.auth.resolver import resolve_session
from mixpanel_headless._internal.auth.session import (
    Project,
    Session,
    WorkspaceRef,
)
from mixpanel_headless._internal.auth.token_resolver import OnDiskTokenResolver
from mixpanel_headless._internal.config import ConfigManager
from mixpanel_headless.cli.main import app
from mixpanel_headless.cli.utils import ExitCode
from mixpanel_headless.exceptions import ConfigError, OAuthError

# =============================================================================
# Account name boundary + character tests
# =============================================================================


class TestAccountNameBoundaries:
    """Account name max-length and character whitelist edge cases."""

    def test_account_name_64_chars_passes(self) -> None:
        """Boundary: exactly 64 chars is accepted."""
        sa = ServiceAccount(
            name="a" * 64,
            region="us",
            username="u",
            secret=SecretStr("s"),
        )
        assert len(sa.name) == 64

    def test_account_name_65_chars_fails(self) -> None:
        """Off-by-one boundary: 65 chars is rejected."""
        with pytest.raises(ValidationError):
            ServiceAccount(
                name="a" * 65,
                region="us",
                username="u",
                secret=SecretStr("s"),
            )

    @pytest.mark.parametrize(
        "name",
        [
            "team space",  # space
            "team.dot",  # dot
            "team/slash",  # slash
            "team\nnewline",  # newline
            "team\x00null",  # null byte
            "team\x7fdel",  # DEL char
            "teaméaccent",  # accented char
            "team😀emoji",  # emoji
            "team\ttab",  # tab
        ],
    )
    def test_account_name_rejects_exotic_chars(self, name: str) -> None:
        """Pattern allows only [a-zA-Z0-9_-]; everything else raises."""
        with pytest.raises(ValidationError):
            ServiceAccount(
                name=name,
                region="us",
                username="u",
                secret=SecretStr("s"),
            )


# =============================================================================
# OAuthTokenAccount validator under model_copy
# =============================================================================


class TestOAuthTokenValidatorUnderCopy:
    """Documents Pydantic v2's known limitation: model_copy does NOT re-run validators.

    These tests pin the CURRENT behavior so that if Pydantic ever changes
    (or we override ``model_copy``), we get notified. Account instances
    are intended to be immutable and constructed via ``__init__`` (or
    ``TypeAdapter.validate_python``) for the XOR guarantee to hold.

    Reference: https://docs.pydantic.dev/latest/concepts/serialization/#modelmodel_copy
    """

    def test_model_copy_setting_both_does_not_revalidate(self) -> None:
        """``model_copy(update=...)`` bypasses the XOR validator (Pydantic limitation).

        Caller's responsibility to use ``model_validate`` if they need
        re-validation. Pinning this so a Pydantic upgrade or our own
        override would surface here.
        """
        original = OAuthTokenAccount(
            name="ci", region="us", token=SecretStr("inline-tok")
        )
        # Forcing both fields via copy succeeds in Pydantic v2 by design.
        bad = original.model_copy(update={"token_env": "MY_ENV"}, deep=True)
        # Both fields are now set — the XOR validator never re-fires.
        assert bad.token is not None
        assert bad.token_env == "MY_ENV"

    def test_validate_python_round_trip_enforces_xor(self) -> None:
        """The escape hatch: round-tripping via TypeAdapter re-validates.

        Demonstrates the safe way to "copy with updates" that re-runs
        validators. Use this pattern in production code paths.
        """
        original = OAuthTokenAccount(
            name="ci", region="us", token=SecretStr("inline-tok")
        )
        adapter: TypeAdapter[Account] = TypeAdapter(Account)
        bad_payload = original.model_dump() | {"token_env": "MY_ENV"}
        with pytest.raises(ValidationError):
            adapter.validate_python(bad_payload)


# =============================================================================
# Session.replace sentinel semantics
# =============================================================================


@pytest.fixture
def base_session() -> Session:
    """A Session with all three axes populated for sentinel-semantics tests."""
    return Session(
        account=ServiceAccount(
            name="team",
            region="us",
            username="u",
            secret=SecretStr("s"),
        ),
        project=Project(id="3713224"),
        workspace=WorkspaceRef(id=42),
        headers={"X-Custom": "value"},
    )


class TestSessionReplaceSentinel:
    """workspace=None vs omitted; headers={} vs omitted."""

    def test_workspace_none_clears(self, base_session: Session) -> None:
        """Explicit ``workspace=None`` clears the workspace."""
        s2 = base_session.replace(workspace=None)
        assert s2.workspace is None

    def test_workspace_omitted_preserves(self, base_session: Session) -> None:
        """Omitting workspace= preserves the existing workspace."""
        s2 = base_session.replace()
        assert s2.workspace == base_session.workspace

    def test_headers_empty_dict_clears(self, base_session: Session) -> None:
        """``headers={}`` clears all custom headers."""
        s2 = base_session.replace(headers={})
        assert s2.headers == {}

    def test_headers_omitted_preserves(self, base_session: Session) -> None:
        """Omitting headers= preserves the headers map."""
        s2 = base_session.replace()
        assert s2.headers == {"X-Custom": "value"}

    def test_three_call_chain_distinguishes_clear_from_preserve(
        self, base_session: Session
    ) -> None:
        """Compare three replace() outcomes to verify sentinel discrimination."""
        s_cleared = base_session.replace(workspace=None)
        s_preserved = base_session.replace()
        s_swapped = base_session.replace(workspace=WorkspaceRef(id=99))
        assert s_cleared.workspace is None
        assert s_preserved.workspace == base_session.workspace
        assert s_swapped.workspace is not None
        assert s_swapped.workspace.id == 99


# =============================================================================
# OnDiskTokenResolver — malformed on-disk tokens
# =============================================================================


@pytest.fixture
def isolated_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Tmp $HOME so token resolver writes don't pollute the dev's account dir."""
    monkeypatch.setenv("HOME", str(tmp_path))
    return tmp_path


def _write_tokens(
    home: Path,
    name: str,
    *,
    payload: dict[str, Any],
) -> Path:
    """Write a tokens.json with the supplied payload (no validation).

    Args:
        home: Tmp HOME path.
        name: Account name.
        payload: Raw dict to JSON-encode.

    Returns:
        Path to the written file.
    """
    account_dir = home / ".mp" / "accounts" / name
    account_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    p = account_dir / "tokens.json"
    p.write_text(json.dumps(payload), encoding="utf-8")
    p.chmod(0o600)
    return p


class TestTokenResolverMalformed:
    """OnDiskTokenResolver edge cases for corrupted tokens.json."""

    def test_malformed_expires_at_raises(self, isolated_home: Path) -> None:
        """``expires_at: "not-a-date"`` raises OAuthError."""
        _write_tokens(
            isolated_home,
            "x",
            payload={
                "access_token": "tok",
                "expires_at": "not-a-date",
                "scope": "read",
                "token_type": "Bearer",
            },
        )
        resolver = OnDiskTokenResolver()
        with pytest.raises(OAuthError):
            resolver.get_browser_token("x", "us")

    def test_truncated_json_raises(self, isolated_home: Path) -> None:
        """Truncated JSON raises OAuthError with file path in message."""
        account_dir = isolated_home / ".mp" / "accounts" / "x"
        account_dir.mkdir(parents=True, mode=0o700)
        p = account_dir / "tokens.json"
        p.write_text('{"access_token": "tok"', encoding="utf-8")  # truncated
        p.chmod(0o600)
        resolver = OnDiskTokenResolver()
        with pytest.raises(OAuthError) as excinfo:
            resolver.get_browser_token("x", "us")
        assert str(p) in str(excinfo.value)

    def test_expired_no_refresh_uses_token_error_code(
        self, isolated_home: Path
    ) -> None:
        """Expired + no refresh_token → code OAUTH_TOKEN_ERROR."""
        past = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        _write_tokens(
            isolated_home,
            "x",
            payload={
                "access_token": "tok",
                "expires_at": past,
                "scope": "read",
                "token_type": "Bearer",
            },
        )
        resolver = OnDiskTokenResolver()
        with pytest.raises(OAuthError) as excinfo:
            resolver.get_browser_token("x", "us")
        assert excinfo.value.code == "OAUTH_TOKEN_ERROR"

    def test_expired_with_refresh_uses_refresh_error_code(
        self, isolated_home: Path
    ) -> None:
        """Expired + has refresh_token → code OAUTH_REFRESH_ERROR (refresh deferred)."""
        past = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        _write_tokens(
            isolated_home,
            "x",
            payload={
                "access_token": "tok",
                "refresh_token": "ref",
                "expires_at": past,
                "scope": "read",
                "token_type": "Bearer",
            },
        )
        resolver = OnDiskTokenResolver()
        with pytest.raises(OAuthError) as excinfo:
            resolver.get_browser_token("x", "us")
        assert excinfo.value.code == "OAUTH_REFRESH_ERROR"


# =============================================================================
# Resolver edge cases
# =============================================================================


@pytest.fixture
def empty_cm(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> ConfigManager:
    """Fresh empty ConfigManager + isolated HOME (no accidental bridge load)."""
    monkeypatch.setenv("HOME", str(tmp_path))
    return ConfigManager(config_path=tmp_path / "config.toml")


class TestResolverEdgeCases:
    """Per-axis precedence and env-var parsing corner cases."""

    def test_partial_sa_quad_no_secret_falls_through(
        self,
        empty_cm: ConfigManager,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Missing MP_SECRET → SA quad is incomplete → falls through, raises."""
        monkeypatch.setenv("MP_USERNAME", "u")
        monkeypatch.setenv("MP_PROJECT_ID", "1")
        monkeypatch.setenv("MP_REGION", "us")
        # No MP_SECRET → quad incomplete → no env account → no fallback → raise.
        with pytest.raises(ConfigError):
            resolve_session(config=empty_cm)

    def test_partial_sa_quad_no_username_falls_through(
        self,
        empty_cm: ConfigManager,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Missing MP_USERNAME → SA quad incomplete → falls through."""
        monkeypatch.setenv("MP_SECRET", "s")
        monkeypatch.setenv("MP_PROJECT_ID", "1")
        monkeypatch.setenv("MP_REGION", "us")
        with pytest.raises(ConfigError):
            resolve_session(config=empty_cm)

    @pytest.mark.parametrize("bad_workspace", ["abc", "0", "-1", "1.5"])
    def test_workspace_id_invalid_raises_config_error(
        self,
        empty_cm: ConfigManager,
        monkeypatch: pytest.MonkeyPatch,
        bad_workspace: str,
    ) -> None:
        """MP_WORKSPACE_ID with non-positive-int values raises ConfigError.

        Fix 24 inverted the prior "silently skip" behavior — silent
        downgrades hid typos that left the user wondering why their
        workspace pin was being ignored.
        """
        monkeypatch.setenv("MP_USERNAME", "u")
        monkeypatch.setenv("MP_SECRET", "s")
        monkeypatch.setenv("MP_PROJECT_ID", "1")
        monkeypatch.setenv("MP_REGION", "us")
        monkeypatch.setenv("MP_WORKSPACE_ID", bad_workspace)
        with pytest.raises(ConfigError, match="MP_WORKSPACE_ID"):
            resolve_session(config=empty_cm)

    def test_workspace_id_empty_string_treated_as_unset(
        self,
        empty_cm: ConfigManager,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """An empty MP_WORKSPACE_ID is treated as unset (no error)."""
        monkeypatch.setenv("MP_USERNAME", "u")
        monkeypatch.setenv("MP_SECRET", "s")
        monkeypatch.setenv("MP_PROJECT_ID", "1")
        monkeypatch.setenv("MP_REGION", "us")
        monkeypatch.setenv("MP_WORKSPACE_ID", "")
        s = resolve_session(config=empty_cm)
        assert s.workspace is None


# =============================================================================
# BridgeFile + load_bridge edge cases
# =============================================================================


class TestBridgeEdgeCases:
    """v2 bridge loader robustness."""

    def test_oauth_browser_without_tokens_rejected(self, tmp_path: Path) -> None:
        """oauth_browser bridge missing the `tokens` field fails validation."""
        payload = {
            "version": 2,
            "account": {
                "type": "oauth_browser",
                "name": "personal",
                "region": "us",
            },
            # No tokens.
        }
        with pytest.raises(ValidationError):
            BridgeFile.model_validate(payload)

    @pytest.mark.parametrize("bad_version", [1, 3, "2"])
    def test_version_mismatch_rejected(self, bad_version: object) -> None:
        """version != 2 (Literal[2]) is rejected."""
        payload = {
            "version": bad_version,
            "account": {
                "type": "service_account",
                "name": "team",
                "region": "us",
                "username": "u",
                "secret": "s",
            },
        }
        with pytest.raises(ValidationError):
            BridgeFile.model_validate(payload)

    def test_load_bridge_returns_none_for_missing_path(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """MP_AUTH_FILE pointing at a nonexistent path → load_bridge returns None.

        Note: also need to isolate HOME so the default search paths don't
        find the dev's real bridge file.
        """
        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.setenv("MP_AUTH_FILE", str(tmp_path / "nonexistent.json"))
        # Cwd default search would find a stray mixpanel_auth.json; isolate cwd too.
        monkeypatch.chdir(tmp_path)
        result = load_bridge()
        assert result is None

    def test_load_bridge_malformed_json_raises_with_path(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Corrupted JSON in bridge file → ConfigError mentioning the path."""
        bridge_path = tmp_path / "bridge.json"
        bridge_path.write_text('{"version": 2', encoding="utf-8")  # truncated
        monkeypatch.setenv("MP_AUTH_FILE", str(bridge_path))
        with pytest.raises(ConfigError) as excinfo:
            load_bridge()
        assert str(bridge_path) in str(excinfo.value)


# =============================================================================
# ConfigManager v3 edge cases
# =============================================================================


class TestConfigManagerEdgeCases:
    """Legacy detection + file permissions + idempotency."""

    def test_legacy_v2_config_no_longer_decodes_as_accounts(
        self, tmp_path: Path
    ) -> None:
        """A TOML with an unknown ``config_version`` key yields no accounts.

        ``config_version = 2`` is ignored as an unknown key and
        ``list_accounts`` returns an empty list because the fixture has
        no ``[accounts]`` section.
        """
        p = tmp_path / "config.toml"
        p.write_text("config_version = 2\n", encoding="utf-8")
        cm = ConfigManager(config_path=p)
        assert cm.list_accounts() == []

    @pytest.mark.skipif(os.name != "posix", reason="POSIX permissions test")
    def test_file_permissions_under_loose_umask(self, tmp_path: Path) -> None:
        """A loose umask (0o022) doesn't leak into the written config file.

        Verifies the explicit chmod to 0o600 inside ConfigManager._write_raw.
        """
        old_umask = os.umask(0o022)
        try:
            cm = ConfigManager(config_path=tmp_path / "config.toml")
            cm.add_account(
                "team",
                type="service_account",
                region="us",
                default_project="3713224",
                username="u",
                secret=SecretStr("s"),
            )
            mode = stat.S_IMODE(cm.config_path.stat().st_mode)
            assert mode == 0o600, f"Expected 0o600, got {oct(mode)}"
        finally:
            os.umask(old_umask)

    def test_set_active_idempotent(self, tmp_path: Path) -> None:
        """set_active(account=current) is a no-op (no error)."""
        cm = ConfigManager(config_path=tmp_path / "config.toml")
        cm.add_account(
            "team",
            type="service_account",
            region="us",
            default_project="3713224",
            username="u",
            secret=SecretStr("s"),
        )
        cm.set_active(account="team")
        # Calling again with the same account must not error.
        cm.set_active(account="team")
        assert cm.get_active().account == "team"


# =============================================================================
# Workspace v3 path discrimination
# =============================================================================


# =============================================================================
# CLI exit codes + secret handling
# =============================================================================


@pytest.fixture
def cli_runner() -> CliRunner:
    """A Typer CLI runner for invoking the `mp` app in-process."""
    return CliRunner()


@pytest.fixture(autouse=True)
def _isolated_home_for_cli(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Isolate $HOME, MP_CONFIG_PATH, and MP_OAUTH_STORAGE_DIR for hermetic tests.

    Setting just HOME isn't sufficient: ``OAuthStorage.DEFAULT_STORAGE_DIR``
    used to be a class-level constant captured at import time, and
    ``ConfigManager.DEFAULT_CONFIG_PATH`` had the same shape. Both are now
    lazy after the QA-surfaced fix, but defending in depth here also
    overrides via env var so future regressions can't silently leak the
    dev's real OAuth tokens / config into these tests.
    """
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("MP_CONFIG_PATH", str(tmp_path / ".mp" / "config.toml"))
    # Per Fix 7, MP_OAUTH_STORAGE_DIR names the *root* under which both the
    # OAuth subtree and the per-account subtree live (no longer aliases /oauth).
    monkeypatch.setenv("MP_OAUTH_STORAGE_DIR", str(tmp_path / ".mp"))


class TestCliExitCodes:
    """CLI subcommands return the documented ExitCode constants."""

    def test_account_add_invalid_region_returns_invalid_args(
        self, cli_runner: CliRunner
    ) -> None:
        """``mp account add ... --region magic`` exits ExitCode.INVALID_ARGS."""
        result = cli_runner.invoke(
            app,
            [
                "account",
                "add",
                "team",
                "--type",
                "service_account",
                "--region",
                "magic",
                "--username",
                "u",
            ],
        )
        assert result.exit_code == int(ExitCode.INVALID_ARGS)

    def test_account_add_invalid_type_returns_invalid_args(
        self, cli_runner: CliRunner
    ) -> None:
        """``mp account add ... --type magic`` exits ExitCode.INVALID_ARGS."""
        result = cli_runner.invoke(
            app,
            [
                "account",
                "add",
                "team",
                "--type",
                "magic",
                "--region",
                "us",
                "--username",
                "u",
            ],
        )
        assert result.exit_code == int(ExitCode.INVALID_ARGS)

    def test_account_add_sa_no_secret_returns_invalid_args(
        self, cli_runner: CliRunner
    ) -> None:
        """SA without --secret-stdin and without MP_SECRET env exits INVALID_ARGS."""
        result = cli_runner.invoke(
            app,
            [
                "account",
                "add",
                "team",
                "--type",
                "service_account",
                "--region",
                "us",
                "--username",
                "u",
            ],
        )
        # MP_SECRET is autouse-scrubbed by tests/conftest.py → must fail.
        assert result.exit_code == int(ExitCode.INVALID_ARGS)


class TestSecretLeakage:
    """Secrets must NEVER leak to stdout/stderr in any error path."""

    _SENTINEL = "QASecretValue-MustNotLeak-987654321"

    def test_service_account_secret_not_in_repr(self) -> None:
        """``repr(ServiceAccount)`` redacts the secret."""
        sa = ServiceAccount(
            name="team",
            region="us",
            username="u",
            secret=SecretStr(self._SENTINEL),
        )
        assert self._SENTINEL not in repr(sa)
        assert self._SENTINEL not in str(sa)

    def test_oauth_token_secret_not_in_repr(self) -> None:
        """``repr(OAuthTokenAccount)`` redacts the inline token."""
        a = OAuthTokenAccount(
            name="ci",
            region="us",
            token=SecretStr(self._SENTINEL),
        )
        assert self._SENTINEL not in repr(a)
        assert self._SENTINEL not in str(a)

    def test_session_account_repr_redacts_secret(self) -> None:
        """``repr(Session)`` containing a SA account redacts the secret."""
        s = Session(
            account=ServiceAccount(
                name="team",
                region="us",
                username="u",
                secret=SecretStr(self._SENTINEL),
            ),
            project=Project(id="3713224"),
        )
        assert self._SENTINEL not in repr(s)
        assert self._SENTINEL not in str(s)

    def test_session_to_credentials_oauth_browser_missing_tokens_raises(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """An OAuthBrowserAccount with no on-disk tokens fails fast.

        Constructing a ``MixpanelAPIClient`` with such a session must
        propagate ``OAuthError`` at construction so the user sees an
        actionable "Run mp account login NAME" message instead of a
        confusing 401 later.
        """
        monkeypatch.setenv("HOME", str(tmp_path))
        from mixpanel_headless._internal.api_client import MixpanelAPIClient
        from mixpanel_headless.exceptions import OAuthError

        s = Session(
            account=OAuthBrowserAccount(name="me", region="us"),
            project=Project(id="3713224"),
        )
        # ServiceAccount-only header caching means OAuth construction
        # itself succeeds; the OAuthError surfaces on the first request.
        # Verify that the eager bearer probe (via .current_auth_header)
        # raises immediately.
        client = MixpanelAPIClient(session=s)
        with pytest.raises(OAuthError):
            _ = client.current_auth_header
