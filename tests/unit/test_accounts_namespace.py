"""Unit tests for the ``mp.accounts`` public namespace (T030).

The namespace mirrors the spec ``contracts/python-api.md §5``:
``list``, ``add``, ``update``, ``remove``, ``use``, ``show``, ``test``,
``login``, ``logout``, ``token``, ``export_bridge``, ``remove_bridge``.

Tests focus on the wiring + delegation behavior; the underlying
``ConfigManager`` is exercised in ``test_config.py``.

Reference: specs/042-auth-architecture-redesign/contracts/python-api.md §5.
"""

from __future__ import annotations

import contextlib
import json
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest
from pydantic import SecretStr

from mixpanel_headless import accounts as accounts_ns
from mixpanel_headless._internal.config import ConfigManager
from mixpanel_headless._internal.me import MeProjectInfo, MeResponse
from mixpanel_headless.exceptions import (
    AccountInUseError,
    ConfigError,
)
from mixpanel_headless.types import AccountSummary


@pytest.fixture(autouse=True)
def _isolated_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Isolate $HOME so the namespace's default ConfigManager hits tmp paths."""
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("MP_CONFIG_PATH", str(tmp_path / ".mp" / "config.toml"))


@pytest.fixture
def cm() -> ConfigManager:
    """Return a ConfigManager pointing at the tmp config path."""
    return ConfigManager()


class TestAdd:
    """``mp.accounts.add(name, *, type, region, default_project, ...)``."""

    def test_service_account(self, cm: ConfigManager) -> None:
        """Adding a service account writes [accounts.NAME] with default_project."""
        result = accounts_ns.add(
            "team",
            type="service_account",
            region="us",
            default_project="3713224",
            username="u",
            secret=SecretStr("s"),
        )
        assert isinstance(result, AccountSummary)
        assert result.name == "team"
        assert result.type == "service_account"
        assert cm.get_account("team").default_project == "3713224"

    def test_service_account_without_default_project_succeeds(
        self, cm: ConfigManager
    ) -> None:
        """Per 043 FR-001: SA may omit ``default_project`` at add-time.

        Inverts the 042 requirement — a service account can now be
        created without a project, with the user expected to set the
        active project later via ``mp project use ID`` or to rely on
        ``mp project list``'s /me-driven discovery.
        """
        result = accounts_ns.add(
            "team",
            type="service_account",
            region="us",
            username="u",
            secret=SecretStr("s"),
        )
        assert isinstance(result, AccountSummary)
        assert result.name == "team"
        assert result.type == "service_account"
        assert cm.get_account("team").default_project is None

    def test_oauth_browser_without_default_project_ok(self, cm: ConfigManager) -> None:
        """``oauth_browser`` may omit ``default_project`` — backfilled at login."""
        result = accounts_ns.add("personal", type="oauth_browser", region="eu")
        assert result.type == "oauth_browser"
        assert cm.get_account("personal").default_project is None

    def test_oauth_browser_with_default_project_ok(self, cm: ConfigManager) -> None:
        """``oauth_browser`` may also pre-set ``default_project``."""
        result = accounts_ns.add(
            "personal", type="oauth_browser", region="eu", default_project="12345"
        )
        assert result.type == "oauth_browser"
        assert cm.get_account("personal").default_project == "12345"

    def test_oauth_token_inline(self, cm: ConfigManager) -> None:
        """Adding an oauth_token account with inline token + default_project works."""
        result = accounts_ns.add(
            "ci",
            type="oauth_token",
            region="us",
            default_project="3713224",
            token=SecretStr("ey.x"),
        )
        assert result.type == "oauth_token"

    def test_oauth_token_env(self, cm: ConfigManager) -> None:
        """Adding an oauth_token account with token_env + default_project works."""
        result = accounts_ns.add(
            "agent",
            type="oauth_token",
            region="us",
            default_project="3713224",
            token_env="MP_OAUTH_TOKEN",
        )
        assert result.type == "oauth_token"

    def test_oauth_token_without_default_project_succeeds(
        self, cm: ConfigManager
    ) -> None:
        """Per 043 FR-001: oauth_token may omit ``default_project`` at add-time.

        Same relaxation as service_account — the user can configure the
        active project later. The token credential alone is enough to
        register the account.
        """
        result = accounts_ns.add(
            "agent",
            type="oauth_token",
            region="us",
            token=SecretStr("ey.x"),
        )
        assert isinstance(result, AccountSummary)
        assert result.type == "oauth_token"
        assert cm.get_account("agent").default_project is None

    def test_first_account_auto_active(self, cm: ConfigManager) -> None:
        """Per FR-045, the first account auto-promotes to ``[active].account``."""
        accounts_ns.add(
            "first",
            type="service_account",
            region="us",
            default_project="3713224",
            username="u",
            secret=SecretStr("s"),
        )
        assert cm.get_active().account == "first"

    def test_subsequent_account_does_not_auto_active(self, cm: ConfigManager) -> None:
        """A second account does NOT replace the active selection."""
        accounts_ns.add(
            "first",
            type="service_account",
            region="us",
            default_project="3713224",
            username="u",
            secret=SecretStr("s"),
        )
        accounts_ns.add("second", type="oauth_browser", region="us")
        assert cm.get_active().account == "first"

    def test_duplicate_name_raises(self, cm: ConfigManager) -> None:
        """Adding an existing name raises ConfigError."""
        accounts_ns.add(
            "x",
            type="service_account",
            region="us",
            default_project="3713224",
            username="u",
            secret=SecretStr("s"),
        )
        with pytest.raises(ConfigError):
            accounts_ns.add("x", type="oauth_browser", region="us")

    def test_re_add_with_region_none_does_not_probe(self, cm: ConfigManager) -> None:
        """``accounts.add(region=None)`` on a duplicate fails fast — no probe.

        Per 043 plan, ``accounts.add()`` is a pure persistence call. The
        region probe lives in the CLI (``mp account add`` / ``mp login``)
        so a Python-API caller that passes ``region=None`` for an
        existing account hits the duplicate-name (or missing-region)
        error before any HTTP attempt would be made.
        """
        accounts_ns.add(
            "x",
            type="service_account",
            region="us",
            username="u",
            secret=SecretStr("s"),
        )
        # Re-add with region=None must raise — never reach a probe call.
        with pytest.raises(ConfigError):
            accounts_ns.add(
                "x",
                type="service_account",
                region=None,
                username="u",
                secret=SecretStr("s"),
            )
        # First add's region is preserved (no silent rewrite).
        assert cm.get_account("x").region == "us"

    def test_add_sa_without_region_raises_actionable_error(
        self, cm: ConfigManager
    ) -> None:
        """``accounts.add(region=None)`` for SA → ConfigError naming ``mp login``.

        Per 043 plan §"Library-First": probing is a CLI concern; the
        Python API refuses to invent a region. The error message points
        callers at ``mp login`` (the orchestrator) or at supplying
        ``region=`` explicitly.
        """
        with pytest.raises(ConfigError, match="region") as exc_info:
            accounts_ns.add(
                "team",
                type="service_account",
                region=None,
                username="u",
                secret=SecretStr("s"),
            )
        # The error mentions the actionable next step.
        assert (
            "mp login" in exc_info.value.message or "region=" in exc_info.value.message
        )

    def test_add_oauth_token_without_region_raises_actionable_error(
        self, cm: ConfigManager
    ) -> None:
        """Same relaxation refusal for oauth_token."""
        with pytest.raises(ConfigError, match="region"):
            accounts_ns.add(
                "ci",
                type="oauth_token",
                region=None,
                token=SecretStr("ey.x"),
            )


class TestUpdate:
    """``mp.accounts.update(name, ...)`` mutates fields in place."""

    def test_update_default_project(self, cm: ConfigManager) -> None:
        """Updating ``default_project`` rewrites the account block."""
        accounts_ns.add(
            "team",
            type="service_account",
            region="us",
            default_project="3713224",
            username="u",
            secret=SecretStr("s"),
        )
        accounts_ns.update("team", default_project="9999999")
        assert cm.get_account("team").default_project == "9999999"

    def test_update_region(self, cm: ConfigManager) -> None:
        """Updating ``region`` works for any account type."""
        accounts_ns.add("personal", type="oauth_browser", region="us")
        accounts_ns.update("personal", region="eu")
        assert cm.get_account("personal").region == "eu"

    def test_update_missing_account_raises(self, cm: ConfigManager) -> None:
        """Updating a non-existent account raises."""
        with pytest.raises(ConfigError):
            accounts_ns.update("ghost", default_project="1")

    def test_update_type_incompatible_field_raises(self, cm: ConfigManager) -> None:
        """``username=`` on an oauth_browser account raises."""
        accounts_ns.add("personal", type="oauth_browser", region="us")
        with pytest.raises(ConfigError):
            accounts_ns.update("personal", username="bad")


class TestList:
    """``mp.accounts.list()`` returns AccountSummary records."""

    def test_empty(self, cm: ConfigManager) -> None:
        """No accounts → empty list."""
        assert accounts_ns.list() == []

    def test_returns_summaries(self, cm: ConfigManager) -> None:
        """Each entry is an AccountSummary."""
        accounts_ns.add(
            "team",
            type="service_account",
            region="us",
            default_project="3713224",
            username="u",
            secret=SecretStr("s"),
        )
        result = accounts_ns.list()
        assert len(result) == 1
        assert isinstance(result[0], AccountSummary)


class TestUse:
    """``mp.accounts.use(name)`` writes ``[active].account``."""

    def test_use_writes_active_account(self, cm: ConfigManager) -> None:
        """``use(name)`` sets ``[active].account``."""
        accounts_ns.add(
            "first",
            type="service_account",
            region="us",
            default_project="3713224",
            username="u",
            secret=SecretStr("s"),
        )
        accounts_ns.add("second", type="oauth_browser", region="us")
        accounts_ns.use("second")
        assert cm.get_active().account == "second"

    def test_use_clears_prior_workspace(self, cm: ConfigManager) -> None:
        """``accounts.use(NAME)`` drops any prior ``[active].workspace``.

        Workspaces are project-scoped, so a workspace ID set by the prior
        account would resolve to a foreign workspace (or 404) under the new
        account's project. Project itself travels with the account via
        :attr:`Account.default_project` — no separate axis to reset.
        """
        accounts_ns.add(
            "first",
            type="service_account",
            region="us",
            default_project="3713224",
            username="u",
            secret=SecretStr("s"),
        )
        cm.set_active(workspace=42)
        accounts_ns.add(
            "other",
            type="service_account",
            region="us",
            default_project="9999999",
            username="o",
            secret=SecretStr("o"),
        )
        accounts_ns.use("other")
        active = cm.get_active()
        assert active.account == "other"
        assert active.workspace is None
        # Project travels with the account.
        assert cm.get_account("other").default_project == "9999999"


class TestShow:
    """``mp.accounts.show()`` returns the active or named account summary."""

    def test_show_named(self, cm: ConfigManager) -> None:
        """``show(name)`` returns that account's summary."""
        accounts_ns.add(
            "team",
            type="service_account",
            region="us",
            default_project="3713224",
            username="u",
            secret=SecretStr("s"),
        )
        result = accounts_ns.show("team")
        assert result.name == "team"

    def test_show_active_when_no_name(self, cm: ConfigManager) -> None:
        """``show()`` (no arg) returns the active account."""
        accounts_ns.add(
            "team",
            type="service_account",
            region="us",
            default_project="3713224",
            username="u",
            secret=SecretStr("s"),
        )
        result = accounts_ns.show()
        assert result.name == "team"

    def test_show_missing_raises(self, cm: ConfigManager) -> None:
        """``show("ghost")`` raises ConfigError."""
        with pytest.raises(ConfigError):
            accounts_ns.show("ghost")


class TestRemove:
    """``mp.accounts.remove`` mirrors ConfigManager semantics."""

    def test_remove_unused(self, cm: ConfigManager) -> None:
        """An unreferenced account removes cleanly."""
        accounts_ns.add(
            "x",
            type="service_account",
            region="us",
            default_project="3713224",
            username="u",
            secret=SecretStr("s"),
        )
        orphans = accounts_ns.remove("x")
        assert orphans == []
        assert accounts_ns.list() == []

    def test_remove_referenced_without_force(self, cm: ConfigManager) -> None:
        """Without ``force``, removing a referenced account raises."""
        accounts_ns.add(
            "x",
            type="service_account",
            region="us",
            default_project="3713224",
            username="u",
            secret=SecretStr("s"),
        )
        cm.add_target("ecom", account="x", project="3018488")
        with pytest.raises(AccountInUseError):
            accounts_ns.remove("x")


class TestToken:
    """``mp.accounts.token(name)`` returns the bearer for OAuth accounts."""

    def test_token_for_service_account_returns_none(self, cm: ConfigManager) -> None:
        """ServiceAccount has no bearer → returns None or 'N/A'."""
        accounts_ns.add(
            "team",
            type="service_account",
            region="us",
            default_project="3713224",
            username="u",
            secret=SecretStr("s"),
        )
        result = accounts_ns.token("team")
        assert result is None or result == "N/A"

    def test_token_for_oauth_token_inline(self, cm: ConfigManager) -> None:
        """OAuthTokenAccount with inline token returns the plaintext bearer."""
        accounts_ns.add(
            "ci",
            type="oauth_token",
            region="us",
            default_project="3713224",
            token=SecretStr("ey.tok-123"),
        )
        result = accounts_ns.token("ci")
        assert result == "ey.tok-123"


# Cluster C2 (T089 / T090) replaced the Phase-4 stubs with real bridge
# writers. Functional coverage now lives in tests/unit/test_bridge_export.py
# (15 tests across the standalone bridge.export_bridge / remove_bridge
# functions plus the mp.accounts wrappers).


class TestTest:
    """``mp.accounts.test(name)`` runs a real ``/me`` probe and reports outcome."""

    def test_missing_account_returns_not_found(self, cm: ConfigManager) -> None:
        """Unknown account → ``ok=False`` with a helpful error string."""
        result = accounts_ns.test("ghost")
        assert result.ok is False
        assert result.error is not None
        assert "ghost" in result.error.lower() or "not found" in result.error.lower()

    def test_no_active_account_returns_error(self, cm: ConfigManager) -> None:
        """No name + no active account → ``ok=False``."""
        result = accounts_ns.test()
        assert result.ok is False
        assert result.error is not None

    def test_successful_probe_populates_user_and_project_count(
        self, cm: ConfigManager, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Successful ``/me`` probe → ``ok=True`` with user identity + project count."""
        accounts_ns.add(
            "team",
            type="service_account",
            region="us",
            default_project="3713224",
            username="u",
            secret=SecretStr("s"),
        )
        from mixpanel_headless._internal import api_client as api_client_mod

        def _fake_me(self: object) -> dict[str, object]:
            """Return canned /me payload with two projects + a user."""
            return {
                "user_id": 42,
                "user_email": "team@example.com",
                "projects": {
                    "3713224": {"name": "Alpha", "organization_id": 1},
                    "3018488": {"name": "Beta", "organization_id": 1},
                },
            }

        monkeypatch.setattr(api_client_mod.MixpanelAPIClient, "me", _fake_me)
        result = accounts_ns.test("team")
        assert result.ok is True
        assert result.error is None
        assert result.user is not None
        assert result.user.id == 42
        assert result.user.email == "team@example.com"
        assert result.accessible_project_count == 2

    def test_probe_failure_captured_in_error(
        self, cm: ConfigManager, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """When the underlying ``/me`` call raises, the failure is captured (never re-raised)."""
        accounts_ns.add(
            "team",
            type="service_account",
            region="us",
            default_project="3713224",
            username="u",
            secret=SecretStr("s"),
        )
        from mixpanel_headless._internal import api_client as api_client_mod
        from mixpanel_headless.exceptions import AuthenticationError

        def _fail_me(self: object) -> dict[str, object]:
            """Raise a 401 to simulate stale credentials."""
            raise AuthenticationError("invalid credentials")

        monkeypatch.setattr(api_client_mod.MixpanelAPIClient, "me", _fail_me)
        result = accounts_ns.test("team")
        assert result.ok is False
        assert result.error is not None
        assert "invalid credentials" in result.error or "/me" in result.error
        # The structured fields preserve AuthenticationError's code so
        # the plugin's auth_manager.py can dispatch on `result.error_code`
        # instead of substring-matching the human-readable message.
        assert result.error_code == "AUTH_FAILED"

    def test_probe_failure_preserves_structured_error_details(
        self, cm: ConfigManager, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Library-exception details survive the broad-catch into ``error_details``."""
        accounts_ns.add(
            "team",
            type="service_account",
            region="us",
            default_project="3713224",
            username="u",
            secret=SecretStr("s"),
        )
        from mixpanel_headless._internal import api_client as api_client_mod
        from mixpanel_headless.exceptions import RegionProbeNetworkError

        def _fail_me(self: object) -> dict[str, object]:
            """Simulate the all-network-error case bubbling up from a probe."""
            raise RegionProbeNetworkError(
                "Could not reach any Mixpanel region",
                attempts=[
                    ("us", 0, "ConnectError: dns lookup failed"),
                    ("eu", 0, "ConnectError: dns lookup failed"),
                    ("in", 0, "ConnectError: dns lookup failed"),
                ],
            )

        monkeypatch.setattr(api_client_mod.MixpanelAPIClient, "me", _fail_me)
        result = accounts_ns.test("team")
        assert result.ok is False
        assert result.error_code == "OAUTH_NETWORK_UNREACHABLE"
        # Structured details survive — callers can read attempts directly
        # without re-parsing the human-readable error string.
        assert result.error_details is not None
        assert "attempts" in result.error_details

    def test_probe_failure_from_non_library_exception_keeps_structured_fields_none(
        self, cm: ConfigManager, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Non-library exceptions populate ``error`` only; structured fields stay None."""
        accounts_ns.add(
            "team",
            type="service_account",
            region="us",
            default_project="3713224",
            username="u",
            secret=SecretStr("s"),
        )
        from mixpanel_headless._internal import api_client as api_client_mod

        def _fail_me(self: object) -> dict[str, object]:
            """Simulate a programming bug / network OSError leaking through."""
            raise OSError("simulated low-level network failure")

        monkeypatch.setattr(api_client_mod.MixpanelAPIClient, "me", _fail_me)
        result = accounts_ns.test("team")
        assert result.ok is False
        assert result.error_code is None
        assert result.error_details is None

    def test_active_account_used_when_name_omitted(
        self, cm: ConfigManager, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """``test()`` with no name probes the active account."""
        accounts_ns.add(
            "team",
            type="service_account",
            region="us",
            default_project="3713224",
            username="u",
            secret=SecretStr("s"),
        )
        # First-account auto-promote → "team" is now [active].account
        from mixpanel_headless._internal import api_client as api_client_mod

        def _fake_me(self: object) -> dict[str, object]:
            """Minimal /me payload — just enough to succeed."""
            return {"user_id": 1, "user_email": "x@example.com", "projects": {}}

        monkeypatch.setattr(api_client_mod.MixpanelAPIClient, "me", _fake_me)
        result = accounts_ns.test()
        assert result.ok is True
        assert result.account_name == "team"


class TestTestOAuthBrowser:
    """``mp.accounts.test(name)`` against an ``oauth_browser`` account.

    The existing :class:`TestTest` covers ``service_account`` only; OAuth
    browser accounts go through a different code path (``OnDiskTokenResolver``
    materializes the bearer mid-probe, which can fail in distinct ways:
    missing tokens file, expired tokens with no refresh, refresh-revoked).
    All three failure modes MUST report ``ok=False`` with an actionable
    message rather than crashing the caller.
    """

    def _add_oauth_browser_account(self, cm: ConfigManager) -> None:
        """Seed an ``oauth_browser`` account named ``personal`` (region ``us``)."""
        accounts_ns.add(
            "personal",
            type="oauth_browser",
            region="us",
            default_project="3713224",
        )

    def test_oauth_browser_no_tokens_returns_actionable_error(
        self,
        cm: ConfigManager,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        """No tokens.json on disk → ``ok=False`` mentioning login."""
        monkeypatch.setenv("HOME", str(tmp_path))
        self._add_oauth_browser_account(cm)
        result = accounts_ns.test("personal")
        assert result.ok is False
        assert result.error is not None
        assert "login" in result.error.lower() or "personal" in result.error.lower()

    def test_oauth_browser_expired_no_refresh_returns_actionable_error(
        self,
        cm: ConfigManager,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        """Expired tokens with no refresh_token → ``ok=False`` advising re-login."""
        import json as _json
        from datetime import datetime, timedelta, timezone

        monkeypatch.setenv("HOME", str(tmp_path))
        self._add_oauth_browser_account(cm)
        # Hand-write tokens.json with an expired access token and no refresh.
        account_dir = tmp_path / ".mp" / "accounts" / "personal"
        account_dir.mkdir(parents=True)
        past = datetime.now(timezone.utc) - timedelta(hours=1)
        (account_dir / "tokens.json").write_text(
            _json.dumps(
                {
                    "access_token": "expired-tok",
                    "expires_at": past.isoformat(),
                    "token_type": "Bearer",
                    "scope": "read:project",
                }
            ),
            encoding="utf-8",
        )
        result = accounts_ns.test("personal")
        assert result.ok is False
        assert result.error is not None
        assert "login" in result.error.lower() or "refresh" in result.error.lower()

    def test_oauth_browser_refresh_revoked_returns_actionable_error(
        self,
        cm: ConfigManager,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        """IdP returns ``invalid_grant`` → ``ok=False`` mentions re-login.

        This is the path that surfaces when the user revokes the OAuth
        consent in the Mixpanel UI; the on-disk refresh token still exists
        but is permanently dead.
        """
        import json as _json
        from datetime import datetime, timedelta, timezone

        from mixpanel_headless._internal.auth import flow as flow_mod
        from mixpanel_headless._internal.auth import storage as storage_mod
        from mixpanel_headless._internal.auth.token import OAuthClientInfo

        monkeypatch.setenv("HOME", str(tmp_path))
        self._add_oauth_browser_account(cm)
        account_dir = tmp_path / ".mp" / "accounts" / "personal"
        account_dir.mkdir(parents=True)
        past = datetime.now(timezone.utc) - timedelta(hours=1)
        (account_dir / "tokens.json").write_text(
            _json.dumps(
                {
                    "access_token": "expired-tok",
                    "refresh_token": "revoked-refresh",
                    "expires_at": past.isoformat(),
                    "token_type": "Bearer",
                    "scope": "read:project",
                }
            ),
            encoding="utf-8",
        )
        # Stub DCR client info so the refresh path can find a client.
        monkeypatch.setattr(
            storage_mod.OAuthStorage,
            "load_client_info",
            lambda _self, *, region: OAuthClientInfo(  # noqa: ARG005
                client_id="dcr-1",
                region="us",
                redirect_uri="http://localhost:8765/cb",
                scope="read:project",
                created_at=datetime.now(timezone.utc),
            ),
        )
        # Stub refresh_tokens to raise the new OAUTH_REFRESH_REVOKED code.
        from mixpanel_headless.exceptions import OAuthError

        def _revoked(
            self: object,
            *,
            tokens: object,  # noqa: ARG001
            client_id: str,  # noqa: ARG001
            account_name: str | None = None,
        ) -> object:
            raise OAuthError(
                f"Refresh token has been revoked for account {account_name!r}. "
                f"Re-run `mp account login {account_name}`.",
                code="OAUTH_REFRESH_REVOKED",
            )

        monkeypatch.setattr(flow_mod.OAuthFlow, "refresh_tokens", _revoked)

        result = accounts_ns.test("personal")
        assert result.ok is False
        assert result.error is not None
        assert "login" in result.error.lower() or "revoked" in result.error.lower()


class TestLogin:
    """Coverage for Fix 17 — ``mp.accounts.login(name)``."""

    def test_login_rejects_non_oauth_browser_account(self, cm: ConfigManager) -> None:
        """``login`` raises ConfigError for service_account / oauth_token types."""
        accounts_ns.add(
            "team",
            type="service_account",
            region="us",
            default_project="3713224",
            username="u",
            secret=SecretStr("s"),
        )
        with pytest.raises(ConfigError, match="oauth_browser"):
            accounts_ns.login("team")

    def test_login_missing_account_raises(self, cm: ConfigManager) -> None:
        """``login`` raises ConfigError if the account is not configured."""
        with pytest.raises(ConfigError, match="not found"):
            accounts_ns.login("ghost")

    def test_login_persists_tokens_and_backfills_default_project(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        cm: ConfigManager,
    ) -> None:
        """Successful PKCE flow writes per-account tokens.json and backfills default_project."""
        from datetime import datetime, timedelta, timezone

        from mixpanel_headless._internal.auth import flow as flow_mod
        from mixpanel_headless._internal.auth.token import OAuthTokens

        accounts_ns.add("personal", type="oauth_browser", region="us")

        new_expires = datetime.now(timezone.utc) + timedelta(hours=1)
        captured: dict[str, object] = {}

        def _fake_login(
            self: object,
            project_id: str | None = None,
            *,
            persist: bool = True,
            open_browser: bool = True,
        ) -> OAuthTokens:
            """Stub OAuthFlow.login — record kwargs, return tokens."""
            captured["project_id"] = project_id
            captured["persist"] = persist
            captured["open_browser"] = open_browser
            return OAuthTokens(
                access_token=SecretStr("brw-tok-fresh"),
                refresh_token=SecretStr("brw-refresh-fresh"),
                expires_at=new_expires,
                scope="read:project",
                token_type="Bearer",
            )

        monkeypatch.setattr(flow_mod.OAuthFlow, "login", _fake_login)

        # Stub the /me probe to return a single project.
        from mixpanel_headless._internal import api_client as api_client_mod

        def _fake_me(self: object) -> dict[str, object]:
            """Return canned /me payload with one project + a user."""
            return {
                "user_id": 7,
                "user_email": "alice@example.com",
                "projects": {"3713224": {"name": "Demo", "organization_id": 1}},
            }

        monkeypatch.setattr(api_client_mod.MixpanelAPIClient, "me", _fake_me)

        result = accounts_ns.login("personal")

        assert captured["persist"] is False
        assert captured["project_id"] is None  # account had no default_project
        assert captured["open_browser"] is True  # default — interactive login
        # Tokens persisted to per-account v3 path
        tokens_path = tmp_path / ".mp" / "accounts" / "personal" / "tokens.json"
        assert tokens_path.exists()
        payload = json.loads(tokens_path.read_text(encoding="utf-8"))
        assert payload["access_token"] == "brw-tok-fresh"
        assert payload["refresh_token"] == "brw-refresh-fresh"
        # File mode preserved at 0o600.
        assert (tokens_path.stat().st_mode & 0o777) == 0o600
        # default_project backfilled from /me probe
        refreshed = cm.get_account("personal")
        assert refreshed.default_project == "3713224"
        # OAuthLoginResult shape
        assert result.account_name == "personal"
        assert result.user is not None
        assert result.user.email == "alice@example.com"
        assert result.expires_at == new_expires
        assert result.tokens_path == tokens_path

    def test_login_propagates_open_browser_false(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        cm: ConfigManager,
    ) -> None:
        """``accounts.login(name, open_browser=False)`` reaches OAuthFlow.

        Regression: ``open_browser`` was accepted as a kwarg but dropped
        with ``# noqa: ARG001``, so ``mp account login --no-browser``
        still triggered ``webbrowser.open()`` (or failed in headless
        environments before the user could copy the URL).
        """
        from datetime import datetime, timedelta, timezone

        from mixpanel_headless._internal.auth import flow as flow_mod
        from mixpanel_headless._internal.auth.token import OAuthTokens

        accounts_ns.add(
            "personal",
            type="oauth_browser",
            region="us",
            default_project="3713224",
        )

        captured: dict[str, object] = {}

        def _fake_login(
            self: object,
            project_id: str | None = None,
            *,
            persist: bool = True,
            open_browser: bool = True,
        ) -> OAuthTokens:
            """Stub OAuthFlow.login — record open_browser, return tokens."""
            captured["open_browser"] = open_browser
            return OAuthTokens(
                access_token=SecretStr("brw-tok"),
                refresh_token=SecretStr("brw-refresh"),
                expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
                scope="read:project",
                token_type="Bearer",
            )

        monkeypatch.setattr(flow_mod.OAuthFlow, "login", _fake_login)

        from mixpanel_headless._internal import api_client as api_client_mod

        def _fake_me(self: object) -> dict[str, object]:
            """Return a minimal /me payload — login probe path."""
            return {
                "user_id": 1,
                "user_email": "u@example.com",
                "projects": {"3713224": {"name": "Demo", "organization_id": 1}},
            }

        monkeypatch.setattr(api_client_mod.MixpanelAPIClient, "me", _fake_me)

        accounts_ns.login("personal", open_browser=False)

        assert captured["open_browser"] is False


class TestPublicSurface:
    """Lock the ``mp.accounts`` public surface (Claim 6)."""

    def test_login_and_test_are_exported(self) -> None:
        """``login`` and ``test`` belong to ``__all__`` per ``contracts/python-api.md §5``.

        Both are documented public API and called by
        ``mixpanel-plugin/skills/mixpanelyst/scripts/auth_manager.py``.
        Omitting them from ``__all__`` hides them from ``help()``,
        tab-completion, and ``from mixpanel_headless.accounts import *``.
        """
        assert "login" in accounts_ns.__all__
        assert "test" in accounts_ns.__all__

    def test_all_entries_resolve(self) -> None:
        """Every name in ``__all__`` maps to a real attribute on the module."""
        for name in accounts_ns.__all__:
            assert hasattr(accounts_ns, name), f"__all__ lists missing attr {name!r}"


class TestLogoutHonorsStorageOverride:
    """``logout`` must remove tokens from the env-var-overridden path (Claim 3)."""

    def test_logout_uses_account_dir(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        cm: ConfigManager,
    ) -> None:
        """Tokens written under ``MP_OAUTH_STORAGE_DIR`` are deleted by ``logout``.

        Hardcoding ``Path.home() / ".mp" / ...`` would silently bypass the
        env-var override that hermetic tests and custom deployments rely on.
        Verifies the file under the override path is gone after the call.
        """
        storage_root = tmp_path / "custom-storage"
        monkeypatch.setenv("MP_OAUTH_STORAGE_DIR", str(storage_root))

        accounts_ns.add("personal", type="oauth_browser", region="us")

        # Seed tokens.json under the override path the way `mp account login` would.
        tokens_path = storage_root / "accounts" / "personal" / "tokens.json"
        tokens_path.parent.mkdir(parents=True, mode=0o700)
        tokens_path.write_text("{}", encoding="utf-8")
        assert tokens_path.exists()

        accounts_ns.logout("personal")

        assert not tokens_path.exists()
        # The legacy ``$HOME/.mp/`` path must NOT have been touched.
        assert not (tmp_path / ".mp" / "accounts" / "personal" / "tokens.json").exists()


class TestSummaryTableDynamicWidth:
    """``mp account list`` table widens for long names (Claim 9).

    Account names accept up to 64 characters per ``_AccountBase.name``;
    a fixed-width formatter would silently truncate, which makes the
    active-marker column slide left and confuses the eye. The renderer
    must expand to fit the longest entry.
    """

    def test_long_name_is_not_truncated(self, cm: ConfigManager) -> None:
        """A 64-char account name appears verbatim in the rendered table."""
        from mixpanel_headless.cli.commands.account import _format_summary_table

        long_name = "a" * 64
        accounts_ns.add(long_name, type="oauth_browser", region="us")

        rendered = _format_summary_table(accounts_ns.list())

        assert long_name in rendered, (
            "Long account name truncated; column widths must expand to fit."
        )
        # Header still present, and the active marker line follows the row's name.
        first_data_line = rendered.splitlines()[1]
        assert first_data_line.startswith(long_name)


class TestLoginUnifiedActivation:
    """``login_unified`` activates the account directly — no CLI workaround.

    Pre-fix bug (PR-153 Issue 1): the docstring said "Add and activate"
    but the implementation only let ``add()`` auto-activate the FIRST
    account. Subsequent adds and the relogin path left
    ``[active].account`` untouched. The CLI papered over the gap with
    a separate ``accounts.use(...)`` call after the orchestrator
    returned, so library callers — and Cowork's ``auth_manager.py`` —
    silently failed to switch active state. These tests pin the
    library-level promise.
    """

    def _stub_me(
        self, monkeypatch: pytest.MonkeyPatch, payload: dict[str, object]
    ) -> None:
        """Patch ``MixpanelAPIClient.me`` to return ``payload``."""
        from mixpanel_headless._internal import api_client as api_client_mod

        def _fake_me(self: object) -> dict[str, object]:
            return payload

        monkeypatch.setattr(api_client_mod.MixpanelAPIClient, "me", _fake_me)

    def test_new_credential_promotes_to_active(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """First-account creation promotes via ``add()``; this test pins the
        library-level guarantee remains stable even if ``add()``'s first-
        account auto-promotion logic ever changes.
        """
        from mixpanel_headless import session as session_ns

        monkeypatch.setenv("MP_USERNAME", "svc")
        monkeypatch.setenv("MP_SECRET", "secret")
        self._stub_me(
            monkeypatch,
            {
                "user_id": 1,
                "user_email": "svc@example.com",
                "organizations": {"100": {"id": 100, "name": "Acme Corp"}},
                "projects": {"42": {"name": "Demo", "organization_id": 100}},
            },
        )

        summary = accounts_ns.login_unified(
            account_type="service_account",
            region="us",
            name="newbie",
        )
        assert summary.name == "newbie"
        assert session_ns.show().account == "newbie"

    def test_second_credential_account_is_activated(
        self, monkeypatch: pytest.MonkeyPatch, cm: ConfigManager
    ) -> None:
        """Adding a second account via ``login_unified`` activates IT.

        ``add()`` only auto-activates the first account — so without the
        explicit ``use(name)`` at the end of the orchestrator, this
        second account would stay inactive even though the docstring
        promised activation.
        """
        from mixpanel_headless import session as session_ns

        # Pre-existing first account (auto-activated by ``add()``).
        accounts_ns.add(
            "first",
            type="service_account",
            region="us",
            username="u1",
            secret=SecretStr("s1"),
        )
        assert session_ns.show().account == "first"

        # Second account via login_unified must flip [active].account.
        monkeypatch.setenv("MP_USERNAME", "u2")
        monkeypatch.setenv("MP_SECRET", "s2")
        self._stub_me(
            monkeypatch,
            {
                "user_id": 2,
                "user_email": "u2@example.com",
                "organizations": {"200": {"id": 200, "name": "Beta"}},
                "projects": {},
            },
        )
        summary = accounts_ns.login_unified(
            account_type="service_account",
            region="us",
            name="second",
        )
        assert summary.name == "second"
        assert session_ns.show().account == "second", (
            "login_unified() must activate the new account, not just add it."
        )

    def test_relogin_activates_account(
        self, monkeypatch: pytest.MonkeyPatch, cm: ConfigManager
    ) -> None:
        """Re-login on a non-active account flips ``[active].account``.

        Previously the relogin branch returned ``show(name)`` without
        promoting; only the CLI's manual ``accounts_ns.use(...)``
        observed the contract.
        """
        from mixpanel_headless import session as session_ns

        accounts_ns.add(
            "first",
            type="service_account",
            region="us",
            username="u1",
            secret=SecretStr("s1"),
        )
        accounts_ns.add(
            "secondary",
            type="service_account",
            region="us",
            username="u2",
            secret=SecretStr("s2"),
        )
        # ``add()`` auto-activates only the first one; secondary is dormant.
        assert session_ns.show().account == "first"

        monkeypatch.setenv("MP_USERNAME", "u2")
        monkeypatch.setenv("MP_SECRET", "rotated")
        self._stub_me(
            monkeypatch,
            {
                "user_id": 2,
                "user_email": "u2@example.com",
                "organizations": {"200": {"id": 200, "name": "Beta"}},
                "projects": {},
            },
        )
        accounts_ns.login_unified(
            account_type="service_account",
            region="us",
            name="secondary",
        )
        assert session_ns.show().account == "secondary"


class TestLoginUnifiedMeCacheWrite:
    """``login_unified`` persists the ``/me`` response to ``me.json``.

    Pre-fix bug (PR-153 Issue 3): the orchestrator fetched ``/me``
    in-process to resolve the project / derive the name and then
    discarded the response. The python-api.md §1 contract said the
    cache was written; the implementation explicitly did not. The next
    ``MeService`` call paid a redundant network round-trip.
    """

    def _stub_me(
        self, monkeypatch: pytest.MonkeyPatch, payload: dict[str, object]
    ) -> None:
        """Patch ``MixpanelAPIClient.me`` to return ``payload``."""
        from mixpanel_headless._internal import api_client as api_client_mod

        def _fake_me(self: object) -> dict[str, object]:
            return payload

        monkeypatch.setattr(api_client_mod.MixpanelAPIClient, "me", _fake_me)

    def test_credential_path_writes_me_cache(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """SA login persists /me at ``~/.mp/accounts/{name}/me.json``."""
        from mixpanel_headless._internal.auth.storage import account_dir
        from mixpanel_headless._internal.me import MeCache

        monkeypatch.setenv("MP_USERNAME", "svc")
        monkeypatch.setenv("MP_SECRET", "secret")
        self._stub_me(
            monkeypatch,
            {
                "user_id": 9,
                "user_email": "svc@example.com",
                "organizations": {"100": {"id": 100, "name": "Acme"}},
                "projects": {"42": {"name": "Demo", "organization_id": 100}},
            },
        )

        accounts_ns.login_unified(
            account_type="service_account",
            region="us",
            name="acme-sa",
        )
        cache_path = account_dir("acme-sa") / "me.json"
        assert cache_path.exists()
        cached = MeCache(
            account_name="acme-sa", storage_dir=account_dir("acme-sa")
        ).get()
        assert cached is not None
        assert cached.user_email == "svc@example.com"

    def test_relogin_writes_me_cache(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Relogin path also persists /me — pre-fix it skipped the write entirely."""
        from mixpanel_headless._internal.auth.storage import account_dir
        from mixpanel_headless._internal.me import MeCache

        accounts_ns.add(
            "team",
            type="service_account",
            region="us",
            username="u-old",
            secret=SecretStr("old-secret"),
        )
        # Pre-clear any cache the test fixture may have created.
        cache_path = account_dir("team") / "me.json"
        cache_path.unlink(missing_ok=True)

        self._stub_me(
            monkeypatch,
            {
                "user_id": 9,
                "user_email": "team@example.com",
                "organizations": {"100": {"id": 100, "name": "Team"}},
                "projects": {},
            },
        )
        monkeypatch.setenv("MP_USERNAME", "u-new")
        monkeypatch.setenv("MP_SECRET", "new-secret")
        accounts_ns.login_unified(
            account_type="service_account",
            region="us",
            name="team",
        )
        assert cache_path.exists()
        cached = MeCache(account_name="team", storage_dir=account_dir("team")).get()
        assert cached is not None
        assert cached.user_email == "team@example.com"


class TestLoginUnifiedFlagValidation:
    """``login_unified`` rejects mutually-incompatible flag combinations.

    Pre-fix bug (PR-153 Issue 6): combination validation lived in the
    CLI, which reached into ``accounts._detect_login_type`` (a private
    helper) with a ``# noqa: SLF001`` to mirror the orchestrator's
    detection. Library callers got no protection. The fix moves
    validation into ``login_unified`` and surfaces structured
    ``InvalidArgumentError`` so non-CLI callers can dispatch on
    ``violation`` / ``detected_auth_type``.
    """

    def test_service_account_and_token_env_mutually_exclusive(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """``service_account=True`` AND ``token_env=...`` raises on violation='mutually_exclusive'."""
        from mixpanel_headless.exceptions import InvalidArgumentError

        with pytest.raises(InvalidArgumentError) as exc_info:
            accounts_ns.login_unified(service_account=True, token_env="MY_TOKEN")
        assert exc_info.value.violation == "mutually_exclusive"
        assert exc_info.value.detected_auth_type == "service_account"

    def test_no_browser_with_service_account_rejected(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """``no_browser=True`` against detected non-browser type raises."""
        from mixpanel_headless.exceptions import InvalidArgumentError

        with pytest.raises(InvalidArgumentError) as exc_info:
            accounts_ns.login_unified(service_account=True, no_browser=True)
        assert exc_info.value.violation == "no_browser_misuse"
        assert exc_info.value.detected_auth_type == "service_account"

    def test_secret_stdin_with_oauth_token_rejected(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """``secret_stdin=True`` against detected non-SA type raises."""
        from mixpanel_headless.exceptions import InvalidArgumentError

        with pytest.raises(InvalidArgumentError) as exc_info:
            accounts_ns.login_unified(token_env="MY_TOKEN", secret_stdin=True)
        assert exc_info.value.violation == "secret_stdin_misuse"
        assert exc_info.value.detected_auth_type == "oauth_token"

    def test_explicit_account_type_conflict_with_service_account_flag(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """``service_account=True`` while ``account_type="oauth_token"`` is mutually exclusive."""
        from mixpanel_headless.exceptions import InvalidArgumentError

        with pytest.raises(InvalidArgumentError) as exc_info:
            accounts_ns.login_unified(service_account=True, account_type="oauth_token")
        assert exc_info.value.violation == "mutually_exclusive"
        assert exc_info.value.detected_auth_type == "oauth_token"


class TestLoginUnifiedSummaryFields:
    """``login_unified`` populates user_email / project_id / project_name on
    the returned ``AccountSummary``.

    Pre-fix bug (PR-153 Issues 2 + 12): the success line had to do a
    second ``ConfigManager.get_account(name)`` round-trip just to read
    ``default_project``, and even then the project_name and user_email
    weren't available without yet another call. New optional fields
    on ``AccountSummary`` make the orchestrator's /me data flow
    cleanly to the printer.
    """

    def _stub_me(
        self, monkeypatch: pytest.MonkeyPatch, payload: dict[str, object]
    ) -> None:
        """Patch ``MixpanelAPIClient.me`` to return ``payload``."""
        from mixpanel_headless._internal import api_client as api_client_mod

        def _fake_me(self: object) -> dict[str, object]:
            return payload

        monkeypatch.setattr(api_client_mod.MixpanelAPIClient, "me", _fake_me)

    def test_summary_carries_me_derived_fields_on_credential_path(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """SA login populates user_email + project_id + project_name from /me."""
        monkeypatch.setenv("MP_USERNAME", "svc")
        monkeypatch.setenv("MP_SECRET", "secret")
        self._stub_me(
            monkeypatch,
            {
                "user_id": 1,
                "user_email": "svc@example.com",
                "organizations": {"100": {"id": 100, "name": "Acme"}},
                "projects": {"42": {"name": "Acme Demo", "organization_id": 100}},
            },
        )
        summary = accounts_ns.login_unified(
            account_type="service_account",
            region="us",
            name="prod",
            project="42",
        )
        assert summary.user_email == "svc@example.com"
        assert summary.project_id == "42"
        assert summary.project_name == "Acme Demo"

    def test_summary_project_name_none_when_no_project(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Empty /me.projects → ``project_id`` and ``project_name`` both ``None``."""
        monkeypatch.setenv("MP_USERNAME", "svc")
        monkeypatch.setenv("MP_SECRET", "secret")
        self._stub_me(
            monkeypatch,
            {
                "user_id": 1,
                "user_email": "svc@example.com",
                "organizations": {"100": {"id": 100, "name": "Empty"}},
                "projects": {},
            },
        )
        summary = accounts_ns.login_unified(
            account_type="service_account",
            region="us",
            name="emptyacct",
        )
        assert summary.user_email == "svc@example.com"
        assert summary.project_id is None
        assert summary.project_name is None


class TestLoginUnifiedProgressHook:
    """``login_unified`` wraps the ``/me`` fetch in a caller-supplied CM.

    The ``/me`` endpoint can take many seconds when an account spans
    dozens of projects across multiple orgs. The CLI uses this hook to
    show a Rich spinner so the terminal does not appear hung. Library
    callers leave it ``None`` (default) and the orchestrator wraps the
    call in :class:`contextlib.nullcontext`.
    """

    def _stub_me(
        self, monkeypatch: pytest.MonkeyPatch, payload: dict[str, object]
    ) -> None:
        """Patch ``MixpanelAPIClient.me`` to return ``payload``."""
        from mixpanel_headless._internal import api_client as api_client_mod

        def _fake_me(self: object) -> dict[str, object]:
            return payload

        monkeypatch.setattr(api_client_mod.MixpanelAPIClient, "me", _fake_me)

    def _make_tracking_progress(
        self,
    ) -> tuple[
        list[str],
        list[str],
        Callable[[str], contextlib.AbstractContextManager[None]],
    ]:
        """Build a progress factory that records enter/exit ordering.

        Returns:
            Tuple of (messages, events, factory). ``messages`` lists the
            strings the orchestrator passed; ``events`` records
            ``"enter"`` / ``"exit"`` for each CM lifecycle step; the
            factory is the callable to pass as ``progress=``.
        """
        messages: list[str] = []
        events: list[str] = []

        @contextlib.contextmanager
        def _factory(msg: str) -> Iterator[None]:
            """Capture ``msg`` then yield, recording enter/exit events."""
            messages.append(msg)
            events.append("enter")
            try:
                yield
            finally:
                events.append("exit")

        return messages, events, _factory

    def test_progress_wraps_me_on_credential_path(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """SA login: progress CM is entered before /me and exited after.

        Pins the ordering so a future refactor that hoists ``/me`` out
        of the wrapped block (or stops calling progress at all) fails
        loud instead of silently regressing the spinner UX.
        """
        monkeypatch.setenv("MP_USERNAME", "svc")
        monkeypatch.setenv("MP_SECRET", "secret")
        self._stub_me(
            monkeypatch,
            {
                "user_id": 1,
                "user_email": "svc@example.com",
                "organizations": {"100": {"id": 100, "name": "Acme"}},
                "projects": {"42": {"name": "Demo", "organization_id": 100}},
            },
        )
        messages, events, tracker = self._make_tracking_progress()

        # Spy on _fetch_me so we can assert the progress CM is open
        # AT the moment _fetch_me runs, not just before / after the
        # whole orchestrator. The closure-captured `events` list grows
        # to ["enter", "fetch", "exit"] iff the wrap is correct.
        from mixpanel_headless import accounts as accounts_mod

        original_fetch = accounts_mod._fetch_me

        def _spy_fetch(*args: object, **kwargs: object) -> object:
            """Record the call between enter / exit so order can be asserted."""
            events.append("fetch")
            return original_fetch(*args, **kwargs)  # type: ignore[arg-type]

        monkeypatch.setattr(accounts_mod, "_fetch_me", _spy_fetch)

        accounts_ns.login_unified(
            account_type="service_account",
            region="us",
            name="prod",
            project="42",
            progress=tracker,
        )

        assert events == ["enter", "fetch", "exit"], (
            f"progress CM must wrap /me; got events={events!r}"
        )
        assert len(messages) == 1, messages
        assert messages[0], "progress message must be non-empty"
        # No numeric duration in the message; cli-feedback rule from
        # 043 frictionless auth UX iteration.
        assert not any(c.isdigit() for c in messages[0]), messages[0]

    def test_progress_default_is_nullcontext(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """``progress=None`` keeps the legacy silent behavior intact.

        Library callers (Cowork, scripts) must not be forced to thread
        a CM through every login_unified invocation. Default falls back
        to nullcontext so the call still works with no progress UI.
        """
        monkeypatch.setenv("MP_USERNAME", "svc")
        monkeypatch.setenv("MP_SECRET", "secret")
        self._stub_me(
            monkeypatch,
            {
                "user_id": 1,
                "user_email": "svc@example.com",
                "organizations": {"100": {"id": 100, "name": "Acme"}},
                "projects": {"42": {"name": "Demo", "organization_id": 100}},
            },
        )
        summary = accounts_ns.login_unified(
            account_type="service_account",
            region="us",
            name="prod",
            project="42",
            # No progress= → must default to nullcontext, no exception.
        )
        assert summary.name == "prod"

    def test_progress_wraps_me_on_relogin_path(
        self, monkeypatch: pytest.MonkeyPatch, cm: ConfigManager
    ) -> None:
        """Re-login also pays the /me cost, so the spinner must wrap there too.

        Without this guarantee, ``mp login --name existing`` would hang
        silently while refreshing the cache.
        """
        # Pre-existing account so login_unified takes the relogin branch.
        accounts_ns.add(
            "prod",
            type="service_account",
            region="us",
            username="u",
            secret=SecretStr("s"),
        )
        monkeypatch.setenv("MP_USERNAME", "u")
        monkeypatch.setenv("MP_SECRET", "s")
        self._stub_me(
            monkeypatch,
            {
                "user_id": 1,
                "user_email": "u@example.com",
                "organizations": {"100": {"id": 100, "name": "Acme"}},
                "projects": {"42": {"name": "Demo", "organization_id": 100}},
            },
        )
        messages, events, tracker = self._make_tracking_progress()

        from mixpanel_headless import accounts as accounts_mod

        original_fetch = accounts_mod._fetch_me

        def _spy_fetch(*args: object, **kwargs: object) -> object:
            events.append("fetch")
            return original_fetch(*args, **kwargs)  # type: ignore[arg-type]

        monkeypatch.setattr(accounts_mod, "_fetch_me", _spy_fetch)

        accounts_ns.login_unified(
            account_type="service_account",
            region="us",
            name="prod",
            progress=tracker,
        )

        assert events == ["enter", "fetch", "exit"], (
            f"relogin must wrap /me with progress CM; got events={events!r}"
        )
        assert messages and messages[0]


class TestLoginUnifiedPickerSortOrder:
    """``login_unified`` sorts the picker list by (org name, project name).

    With dozens of projects spread across multiple orgs, the previous
    project-name-only sort interleaved orgs (Acme · A, Beta · A, Acme ·
    B, Beta · B, …), making it hard to scan for a known project. Group
    by org first so each org's projects appear as a contiguous,
    alphabetized block.
    """

    def _stub_me(
        self, monkeypatch: pytest.MonkeyPatch, payload: dict[str, object]
    ) -> None:
        """Patch ``MixpanelAPIClient.me`` to return ``payload``."""
        from mixpanel_headless._internal import api_client as api_client_mod

        def _fake_me(self: object) -> dict[str, object]:
            return payload

        monkeypatch.setattr(api_client_mod.MixpanelAPIClient, "me", _fake_me)

    def test_picker_receives_projects_grouped_by_org_name(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Multi-org /me yields a list ordered by (org, project) ascending.

        Project names are deliberately interleaved across orgs so a
        name-only sort would NOT match the org-first expected order:

        Name-only sort would yield:
            alpha (Beta), apple (Charlie), middle (Beta),
            wolf (Acme), yak (Charlie), zebra (Acme)

        Org-then-name sort must yield:
            wolf (Acme), zebra (Acme),
            alpha (Beta), middle (Beta),
            apple (Charlie), yak (Charlie)
        """
        monkeypatch.setenv("MP_USERNAME", "svc")
        monkeypatch.setenv("MP_SECRET", "secret")
        self._stub_me(
            monkeypatch,
            {
                "user_id": 1,
                "user_email": "u@example.com",
                "organizations": {
                    "300": {"id": 300, "name": "Charlie"},
                    "100": {"id": 100, "name": "Acme"},
                    "200": {"id": 200, "name": "Beta"},
                },
                "projects": {
                    "1": {"name": "zebra", "organization_id": 100},
                    "2": {"name": "alpha", "organization_id": 200},
                    "3": {"name": "yak", "organization_id": 300},
                    "4": {"name": "wolf", "organization_id": 100},
                    "5": {"name": "middle", "organization_id": 200},
                    "6": {"name": "apple", "organization_id": 300},
                },
            },
        )

        captured: list[list[str]] = []

        def _picker(
            _me: MeResponse, sorted_projects: list[tuple[str, MeProjectInfo]]
        ) -> str:
            """Capture the names the orchestrator sorted; pick the first."""
            captured.append([info.name for _pid, info in sorted_projects])
            return sorted_projects[0][0]

        accounts_ns.login_unified(
            account_type="service_account",
            region="us",
            name="acct",
            project_picker=_picker,
        )

        assert captured, "picker was not called"
        assert captured[0] == [
            "wolf",
            "zebra",
            "alpha",
            "middle",
            "apple",
            "yak",
        ], (
            f"projects must be grouped by org then sorted by project; "
            f"got {captured[0]!r}"
        )

    def test_picker_sort_is_case_insensitive(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """``"acme"`` and ``"Acme"`` collate together; ditto project names.

        Mixpanel users routinely have orgs and projects with mixed
        casing ("Demo Projects", "demo team"). A case-sensitive sort
        on the raw strings would put "Beta" before "acme" because
        ``"B" (66) < "a" (97)``; lowercasing both keys keeps the
        ordering intuitive.
        """
        monkeypatch.setenv("MP_USERNAME", "svc")
        monkeypatch.setenv("MP_SECRET", "secret")
        # Two orgs ("acme", "Beta") chosen so case-sensitive byte sort
        # disagrees with case-insensitive sort on the org axis. One
        # project per org so the assertion isolates the org-axis sort.
        self._stub_me(
            monkeypatch,
            {
                "user_id": 1,
                "user_email": "u@example.com",
                "organizations": {
                    "100": {"id": 100, "name": "acme"},
                    "200": {"id": 200, "name": "Beta"},
                },
                "projects": {
                    "1": {"name": "betaproj", "organization_id": 200},
                    "2": {"name": "acmeproj", "organization_id": 100},
                },
            },
        )

        captured: list[list[str]] = []

        def _picker(
            _me: MeResponse, sorted_projects: list[tuple[str, MeProjectInfo]]
        ) -> str:
            """Capture the names the orchestrator sorted; pick the first."""
            captured.append([info.name for _pid, info in sorted_projects])
            return sorted_projects[0][0]

        accounts_ns.login_unified(
            account_type="service_account",
            region="us",
            name="acct",
            project_picker=_picker,
        )

        # Case-sensitive byte sort on org name: "Beta" < "acme" → Beta
        # group first → ["betaproj", "acmeproj"]. Case-insensitive:
        # "acme" < "beta" → ["acmeproj", "betaproj"].
        assert captured[0] == ["acmeproj", "betaproj"], captured[0]
