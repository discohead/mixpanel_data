"""Tests for browser-auth region cross-check (043 / AIE-114, T022).

When a user runs ``accounts.login(name)`` for an ``oauth_browser``
account, the PKCE flow commits to whichever region the account record
already names. After the callback returns, ``MeService.fetch()``
exposes per-project ``domain`` strings that identify the cluster each
project lives in. If the picked project's domain disagrees with the
auth region, this is a configuration mistake the user must resolve
before any further request can succeed (the bearer is region-bound).

Reference: ``specs/043-frictionless-auth/contracts/error-messages.md``
E-2 (region mismatch on browser auth).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from pydantic import SecretStr

from mixpanel_headless import accounts as accounts_ns
from mixpanel_headless._internal.config import ConfigManager
from mixpanel_headless.exceptions import ConfigError


@pytest.fixture(autouse=True)
def _isolated_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Pin $HOME and ``MP_CONFIG_PATH`` to the test tmpdir."""
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("MP_CONFIG_PATH", str(tmp_path / ".mp" / "config.toml"))


@pytest.fixture
def cm() -> ConfigManager:
    """Fresh ConfigManager rooted at the tmp config path."""
    return ConfigManager()


def _stub_pkce_flow(monkeypatch: pytest.MonkeyPatch) -> None:
    """Patch ``OAuthFlow.login`` to return canned tokens without a real flow."""
    from mixpanel_headless._internal.auth import flow as flow_mod
    from mixpanel_headless._internal.auth.token import OAuthTokens

    def _fake_login(
        self: object,
        project_id: str | None = None,
        *,
        persist: bool = True,
        open_browser: bool = True,
    ) -> OAuthTokens:
        return OAuthTokens(
            access_token=SecretStr("brw-tok"),
            refresh_token=SecretStr("brw-refresh"),
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
            scope="read:project",
            token_type="Bearer",
        )

    monkeypatch.setattr(flow_mod.OAuthFlow, "login", _fake_login)


def _stub_me_with_eu_project(monkeypatch: pytest.MonkeyPatch) -> None:
    """Patch ``MixpanelAPIClient.me`` to return one EU-domain project."""
    from mixpanel_headless._internal import api_client as api_client_mod

    def _fake_me(self: object) -> dict[str, object]:
        return {
            "user_id": 7,
            "user_email": "alice@example.com",
            "projects": {
                "12345": {
                    "name": "Demo",
                    "organization_id": 1,
                    "domain": "eu.mixpanel.com",
                }
            },
        }

    monkeypatch.setattr(api_client_mod.MixpanelAPIClient, "me", _fake_me)


class TestLoginRegionMismatch:
    """``accounts.login()`` enforces auth region == picked project region."""

    def test_us_auth_picking_eu_project_raises_config_error(
        self, cm: ConfigManager, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Auth committed to ``us`` + project domain ``eu.mixpanel.com`` → E-2.

        The wording is asserted against the catalog template — region,
        project ID, name, domain, and the suggested re-run command must
        all appear so the user knows exactly which knob to turn.
        """
        accounts_ns.add("personal", type="oauth_browser", region="us")
        _stub_pkce_flow(monkeypatch)
        _stub_me_with_eu_project(monkeypatch)
        with pytest.raises(ConfigError) as exc_info:
            accounts_ns.login("personal")
        message = exc_info.value.message
        # E-2 catalog wording — placeholders rendered with the test data.
        assert "Region mismatch" in message
        assert "us" in message  # auth_region
        assert "eu" in message  # project_region
        assert "12345" in message  # project_id
        assert "Demo" in message  # project_name
        assert "eu.mixpanel.com" in message  # project_domain
        assert "mp login --region eu" in message

    def test_matching_region_does_not_raise(
        self, cm: ConfigManager, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Auth ``eu`` + project domain ``eu.mixpanel.com`` → success path."""
        from mixpanel_headless._internal import api_client as api_client_mod

        accounts_ns.add("personal", type="oauth_browser", region="eu")
        _stub_pkce_flow(monkeypatch)

        def _fake_me(self: object) -> dict[str, object]:
            return {
                "user_id": 7,
                "user_email": "alice@example.com",
                "projects": {
                    "12345": {
                        "name": "Demo",
                        "organization_id": 1,
                        "domain": "eu.mixpanel.com",
                    }
                },
            }

        monkeypatch.setattr(api_client_mod.MixpanelAPIClient, "me", _fake_me)
        # Should NOT raise.
        result = accounts_ns.login("personal")
        assert result.account_name == "personal"

    def test_project_without_domain_does_not_raise(
        self, cm: ConfigManager, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Missing ``domain`` field → no mismatch detection (back-compat).

        Older ``/me`` responses (and projects in regions Mixpanel hasn't
        annotated) lack ``domain``. The check must skip rather than
        misclassify.
        """
        from mixpanel_headless._internal import api_client as api_client_mod

        accounts_ns.add("personal", type="oauth_browser", region="us")
        _stub_pkce_flow(monkeypatch)

        def _fake_me(self: object) -> dict[str, object]:
            return {
                "user_id": 7,
                "user_email": "alice@example.com",
                "projects": {
                    "12345": {
                        "name": "Demo",
                        "organization_id": 1,
                        # No domain field at all.
                    }
                },
            }

        monkeypatch.setattr(api_client_mod.MixpanelAPIClient, "me", _fake_me)
        result = accounts_ns.login("personal")
        assert result.account_name == "personal"
