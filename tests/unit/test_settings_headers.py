"""Unit tests for in-memory header attachment (T020a).

FR-014 + FR-052: custom HTTP headers configured in ``[settings].custom_header``
or ``bridge.headers`` attach to the resolved Session in memory at resolution
time. The resolver MUST NOT mutate ``os.environ`` (no implicit env-var
contracts between modules). The API client MUST attach those headers to
every outbound request.

Reference: specs/042-auth-architecture-redesign/contracts/config-schema.md §1.2.
"""

from __future__ import annotations

import json
import os
import stat
from pathlib import Path

import httpx
import pytest
from pydantic import SecretStr

from mixpanel_headless._internal.api_client import MixpanelAPIClient
from mixpanel_headless._internal.auth.account import ServiceAccount
from mixpanel_headless._internal.auth.resolver import resolve_session
from mixpanel_headless._internal.auth.session import Project, Session
from mixpanel_headless._internal.config import ConfigManager


@pytest.fixture(autouse=True)
def _isolated_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Isolate ``$HOME`` so the resolver doesn't pick up the dev's real bridge."""
    monkeypatch.setenv("HOME", str(tmp_path))


@pytest.fixture
def cm_with_account_active(tmp_path: Path) -> ConfigManager:
    """Return a v3 ConfigManager with one SA active on a test project."""
    cm = ConfigManager(config_path=tmp_path / "config.toml")
    cm.add_account(
        "team",
        type="service_account",
        region="us",
        default_project="3713224",
        username="team.sa",
        secret=SecretStr("team-secret"),
    )
    cm.set_active(account="team")
    return cm


class TestSettingsHeaderAttachment:
    """``[settings].custom_header`` becomes ``Session.headers``."""

    def test_session_carries_setting_header(
        self, cm_with_account_active: ConfigManager
    ) -> None:
        """A custom_header in [settings] appears in ``Session.headers``."""
        cm_with_account_active.set_custom_header(name="X-Foo", value="bar")
        s = resolve_session(config=cm_with_account_active)
        assert s.headers == {"X-Foo": "bar"}

    def test_no_setting_header_means_empty_dict(
        self, cm_with_account_active: ConfigManager
    ) -> None:
        """No custom_header → ``Session.headers`` is empty."""
        s = resolve_session(config=cm_with_account_active)
        assert s.headers == {}


class TestNoEnvMutation:
    """Per FR-023: resolver MUST NOT mutate ``os.environ``."""

    def test_settings_header_does_not_set_env_vars(
        self,
        cm_with_account_active: ConfigManager,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Snapshot ``os.environ`` before/after resolve_session — must be identical.

        The legacy v2 code mutated ``MP_CUSTOM_HEADER_NAME`` / ``..._VALUE``
        env vars during resolution; the redesigned resolver attaches headers
        in memory only. We compare the full env snapshot so any leak (added,
        modified, or removed key) trips the test.
        """
        # Pre-clear the dev's shell-leaked MP_CUSTOM_HEADER_* so the snapshot
        # reflects only what the resolver does (not the developer's shell).
        monkeypatch.delenv("MP_CUSTOM_HEADER_NAME", raising=False)
        monkeypatch.delenv("MP_CUSTOM_HEADER_VALUE", raising=False)
        cm_with_account_active.set_custom_header(name="X-Hdr", value="v")
        before = dict(os.environ)
        resolve_session(config=cm_with_account_active)
        after = dict(os.environ)
        assert before == after


class TestBridgeHeaderAttachment:
    """A bridge file's ``headers`` map populates ``Session.headers``."""

    def test_bridge_headers_populate_session(
        self,
        cm_with_account_active: ConfigManager,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """A bridge file with ``headers`` map populates ``Session.headers``."""
        bridge_path = tmp_path / "bridge.json"
        payload = {
            "version": 2,
            "account": {
                "type": "service_account",
                "name": "bridged",
                "region": "us",
                "username": "bridge.user",
                "secret": "bridge-secret",
            },
            "project": "3018488",
            "headers": {"X-Mixpanel-Cluster": "internal-1"},
        }
        bridge_path.write_text(json.dumps(payload), encoding="utf-8")
        bridge_path.chmod(stat.S_IRUSR | stat.S_IWUSR)
        monkeypatch.setenv("MP_AUTH_FILE", str(bridge_path))
        s = resolve_session(config=cm_with_account_active)
        assert s.headers.get("X-Mixpanel-Cluster") == "internal-1"
        assert s.account.name == "bridged"

    def test_bridge_does_not_mutate_environ(
        self,
        cm_with_account_active: ConfigManager,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Resolver loading a bridge file does not mutate ``os.environ``."""
        bridge_path = tmp_path / "bridge.json"
        payload = {
            "version": 2,
            "account": {
                "type": "service_account",
                "name": "bridged",
                "region": "us",
                "username": "bridge.user",
                "secret": "bridge-secret",
            },
            "project": "3018488",
            "headers": {"X-Hdr": "v"},
        }
        bridge_path.write_text(json.dumps(payload), encoding="utf-8")
        bridge_path.chmod(stat.S_IRUSR | stat.S_IWUSR)
        monkeypatch.setenv("MP_AUTH_FILE", str(bridge_path))
        before = dict(os.environ)
        resolve_session(config=cm_with_account_active)
        after = dict(os.environ)
        assert before == after


class TestSessionHeadersOnOutboundRequests:
    """``Session.headers`` MUST ride along on every API request.

    Regression: the v3 ``session=`` constructor path stored ``Session.headers``
    in memory (per FR-014) but never wired them into the underlying
    ``httpx.Client`` defaults. Custom headers from ``[settings].custom_header``
    and ``bridge.headers`` were silently dropped at request time, breaking
    environments that route via ``X-Mixpanel-Cluster`` or similar.
    """

    def test_session_headers_included_in_outbound_request(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """A Session with custom headers attaches them to every request."""
        # Pre-clear any leaked legacy env headers so we observe ONLY the
        # session-attached contribution.
        monkeypatch.delenv("MP_CUSTOM_HEADER_NAME", raising=False)
        monkeypatch.delenv("MP_CUSTOM_HEADER_VALUE", raising=False)

        captured: list[httpx.Headers] = []

        def handler(request: httpx.Request) -> httpx.Response:
            captured.append(request.headers)
            return httpx.Response(200, json={"status": "ok", "results": []})

        session = Session(
            account=ServiceAccount(
                name="team",
                region="us",
                username="team.sa",
                secret=SecretStr("team-secret"),
            ),
            project=Project(id="3713224"),
            headers={"X-Mixpanel-Cluster": "internal-1", "X-Tenant": "acme"},
        )
        transport = httpx.MockTransport(handler)
        client = MixpanelAPIClient(session=session, _transport=transport)
        with client:
            client.app_request("GET", "/dashboards")

        assert captured, "request was not captured"
        assert captured[0].get("X-Mixpanel-Cluster") == "internal-1"
        assert captured[0].get("X-Tenant") == "acme"

    def test_session_headers_take_precedence_over_env_on_collision(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """When env-var header and Session.headers collide, session wins.

        The resolver attaches the env contribution to ``Session.headers`` at
        construction; later Session.headers updates (e.g., from a bridge)
        override it. The client should reflect the final session state, not
        re-read env at request time.
        """
        monkeypatch.setenv("MP_CUSTOM_HEADER_NAME", "X-Cluster")
        monkeypatch.setenv("MP_CUSTOM_HEADER_VALUE", "from-env")

        captured: list[httpx.Headers] = []

        def handler(request: httpx.Request) -> httpx.Response:
            captured.append(request.headers)
            return httpx.Response(200, json={"status": "ok", "results": []})

        session = Session(
            account=ServiceAccount(
                name="team",
                region="us",
                username="team.sa",
                secret=SecretStr("team-secret"),
            ),
            project=Project(id="3713224"),
            headers={"X-Cluster": "from-session"},
        )
        transport = httpx.MockTransport(handler)
        client = MixpanelAPIClient(session=session, _transport=transport)
        with client:
            client.app_request("GET", "/dashboards")

        assert captured[0].get("X-Cluster") == "from-session"
