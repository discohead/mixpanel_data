"""CLI tests for the ``mp login --start`` / ``--finish`` / ``--resume`` flow.

Mirrors the patterns in ``tests/unit/cli/test_login_cli.py`` (CliRunner
with ``--isolated_home``, ``MixpanelAPIClient.me`` monkeypatched, no
respx). Covers the §9 envelope shapes, the mutual-exclusion rules, the
``NeedsRegionSwitchError`` exit-6 path, and a happy-path two-shot
sequence (start → finish) with mocked OAuth.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest
from pydantic import SecretStr
from typer.testing import CliRunner

from mixpanel_headless._internal.auth.token import OAuthTokens
from mixpanel_headless.cli.main import app


@pytest.fixture(autouse=True)
def _isolated_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Pin $HOME, MP_CONFIG_PATH, MP_OAUTH_STORAGE_DIR for hermetic tests."""
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("MP_CONFIG_PATH", str(tmp_path / ".mp" / "config.toml"))
    monkeypatch.setenv("MP_OAUTH_STORAGE_DIR", str(tmp_path / ".mp"))


@pytest.fixture
def runner() -> CliRunner:
    """A Typer CliRunner."""
    return CliRunner()


def _stub_dcr(
    monkeypatch: pytest.MonkeyPatch, *, client_id: str = "test_client_xyz"
) -> None:
    """Patch ``ensure_client_registered`` to return a canned client info."""
    from mixpanel_headless._internal.auth import client_registration
    from mixpanel_headless._internal.auth.token import OAuthClientInfo

    def _fake(
        http_client: Any, region: str, redirect_uri: str, storage: Any
    ) -> OAuthClientInfo:
        """Inner stub returning a constant client info."""
        del http_client, storage
        return OAuthClientInfo(
            client_id=client_id,
            region=region,
            redirect_uri=redirect_uri,
            scope="read",
            created_at=datetime.now(timezone.utc),
        )

    monkeypatch.setattr(client_registration, "ensure_client_registered", _fake)
    # OAuthFlow imports the same symbol from client_registration; patch
    # the rebound name there too so test imports don't bypass the stub.
    from mixpanel_headless._internal.auth import flow as flow_mod

    monkeypatch.setattr(flow_mod, "ensure_client_registered", _fake, raising=False)


def _stub_me(monkeypatch: pytest.MonkeyPatch, payload: dict[str, object]) -> None:
    """Patch ``MixpanelAPIClient.me`` to return a canned /me payload."""
    from mixpanel_headless._internal import api_client as api_client_mod

    def _fake_me(self: object) -> dict[str, object]:
        """Inner stub returning the canned /me payload."""
        return payload

    monkeypatch.setattr(api_client_mod.MixpanelAPIClient, "me", _fake_me)


def _stub_exchange(monkeypatch: pytest.MonkeyPatch) -> None:
    """Patch ``OAuthFlow.exchange_code`` to return a canned token set."""
    from mixpanel_headless._internal.auth import flow as flow_mod

    def _fake(
        self: Any,
        *,
        code: str,
        verifier: str,
        client_id: str,
        redirect_uri: str,
    ) -> OAuthTokens:
        """Inner stub returning constant tokens (long-lived expires_at)."""
        del self, code, verifier, client_id, redirect_uri
        return OAuthTokens(
            access_token=SecretStr("access_xyz"),
            refresh_token=SecretStr("refresh_abc"),
            expires_at=datetime(2099, 1, 1, tzinfo=timezone.utc),
            scope="read",
            token_type="Bearer",
        )

    # exchange_code accepts kwargs in the orchestrator; tests pass them positionally
    # via the OAuthFlow.exchange_code signature. Patch as a method.
    monkeypatch.setattr(flow_mod.OAuthFlow, "exchange_code", _fake)


def _me_payload(projects: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Build a /me JSON payload with the user / org / project shape."""
    org_ids = {p["organization_id"] for p in projects.values()}
    return {
        "user_id": 42,
        "user_email": "test@example.com",
        "user_name": "Test User",
        "organizations": {
            str(oid): {"id": oid, "name": f"Org {oid}", "role": "admin"}
            for oid in org_ids
        },
        "projects": projects,
        "workspaces": {},
    }


class TestStartFlag:
    """``mp login --start`` emits the documented JSON envelope."""

    def test_start_emits_json_envelope(
        self, runner: CliRunner, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Single-line JSON envelope on stdout, exit 0."""
        _stub_dcr(monkeypatch)
        result = runner.invoke(app, ["login", "--start"])
        assert result.exit_code == 0, result.output
        payload = json.loads(result.stdout)
        assert payload["schema_version"] == 1
        assert payload["state"] == "ok"
        assert payload["region"] == "us"
        assert "authorize_url" in payload
        assert payload["authorize_url"].startswith(
            "https://mixpanel.com/oauth/authorize/"
        )
        assert "redirect_uri" in payload
        assert "expires_at" in payload
        assert payload["expires_at"] > 0
        assert "inflight_path" in payload

    def test_start_with_eu_region(
        self, runner: CliRunner, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """``--region eu`` produces an eu-cluster authorize URL."""
        _stub_dcr(monkeypatch)
        result = runner.invoke(app, ["login", "--start", "--region", "eu"])
        assert result.exit_code == 0, result.output
        payload = json.loads(result.stdout)
        assert payload["region"] == "eu"
        assert "eu.mixpanel.com" in payload["authorize_url"]


class TestFinishHappyPath:
    """``mp login --finish URL`` against a single-project /me publishes."""

    def test_finish_publishes_account_with_auto_pick(
        self,
        runner: CliRunner,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        """Two-shot --start → --finish writes a usable account + emits envelope."""
        _stub_dcr(monkeypatch)
        _stub_exchange(monkeypatch)
        _stub_me(
            monkeypatch,
            _me_payload(
                {
                    "100": {
                        "name": "Test Project",
                        "organization_id": 1,
                        "domain": "mixpanel.com",
                        "is_demo": False,
                        "has_integrated": True,
                    },
                }
            ),
        )

        # First, --start to create the inflight.
        result_start = runner.invoke(app, ["login", "--start"])
        assert result_start.exit_code == 0, result_start.output
        start_payload = json.loads(result_start.stdout)
        state = start_payload["authorize_url"].split("state=")[1].split("&")[0]

        # Build the redirect URL that --finish will accept.
        redirect_url = (
            f"http://localhost:19284/callback?code=auth_code_xyz&state={state}"
        )

        # --finish completes the flow.
        result_finish = runner.invoke(app, ["login", "--finish", redirect_url])
        assert result_finish.exit_code == 0, result_finish.output
        payload = json.loads(result_finish.stdout)
        assert payload["state"] == "ok"
        assert payload["account"]["type"] == "oauth_browser"
        assert payload["project"]["id"] == "100"
        assert payload["project_pick"]["method"] == "sole_survivor"
        # auto_picked is True because there's no explicit project AND no picker.
        assert payload["project_pick"]["auto_picked"] is True
        # next[] reuses _PROJECT_NEXT verbatim.
        assert payload["next"][0]["command"] == "mp project list"


class TestFinishStateMismatch:
    """A pasted URL with the wrong state → OAUTH_STATE_MISMATCH, exit 2."""

    def test_state_mismatch_raises(
        self, runner: CliRunner, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Pasted URL with a forged state → AUTH_ERROR exit 2."""
        _stub_dcr(monkeypatch)
        result_start = runner.invoke(app, ["login", "--start"])
        assert result_start.exit_code == 0, result_start.output

        # Pass a redirect URL with a state that doesn't match the inflight.
        bad_url = "http://localhost:19284/callback?code=foo&state=wrong_state"
        result = runner.invoke(app, ["login", "--finish", bad_url])
        assert result.exit_code == 2  # AUTH_ERROR
        assert (
            "State mismatch" in result.output or "OAUTH_STATE_MISMATCH" in result.output
        )


class TestFinishMissingInflight:
    """``--finish`` without prior ``--start`` → OAUTH_INFLIGHT_MISSING."""

    def test_no_inflight_raises(self, runner: CliRunner) -> None:
        """No prior --start → OAUTH_INFLIGHT_MISSING, exit 2."""
        result = runner.invoke(
            app,
            ["login", "--finish", "http://localhost:19284/callback?code=x&state=y"],
        )
        assert result.exit_code == 2  # AUTH_ERROR
        assert (
            "OAUTH_INFLIGHT_MISSING" in result.output
            or "inflight" in result.output.lower()
        )


class TestCrossRegionExit6:
    """``/me`` returns only-EU projects with US auth → exit 6 + JSON envelope."""

    def test_cross_region_exits_6_with_envelope(
        self,
        runner: CliRunner,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """US auth + only-EU /me → exit 6 + state:error envelope."""
        _stub_dcr(monkeypatch)
        _stub_exchange(monkeypatch)
        _stub_me(
            monkeypatch,
            _me_payload(
                {
                    "100": {
                        "name": "EU Project",
                        "organization_id": 1,
                        "domain": "eu.mixpanel.com",
                        "is_demo": False,
                        "has_integrated": True,
                    },
                }
            ),
        )

        result_start = runner.invoke(app, ["login", "--start"])
        assert result_start.exit_code == 0
        state = (
            json.loads(result_start.stdout)["authorize_url"]
            .split("state=")[1]
            .split("&")[0]
        )
        redirect = f"http://localhost:19284/callback?code=foo&state={state}"

        result = runner.invoke(app, ["login", "--finish", redirect])
        assert result.exit_code == 6  # NEEDS_SELECTION
        payload = json.loads(result.stdout)
        assert payload["state"] == "error"
        assert payload["error"]["code"] == "NEEDS_REGION_SWITCH"
        assert payload["error"]["actionable"] is True
        assert payload["error"]["details"]["auth_region"] == "us"
        cross = payload["error"]["details"]["cross_region_projects"]
        assert any(p["domain"] == "eu.mixpanel.com" for p in cross)


class TestFlagMutex:
    """Mutually-exclusive flag combinations exit 3 (INVALID_ARGS)."""

    def test_start_and_finish_together(self, runner: CliRunner) -> None:
        """``--start`` + ``--finish`` rejected as mutually exclusive."""
        result = runner.invoke(
            app,
            ["login", "--start", "--finish", "http://x?code=a&state=b"],
        )
        assert result.exit_code == 3
        assert "mutually exclusive" in result.output

    def test_start_and_service_account(self, runner: CliRunner) -> None:
        """Two-shot flags are oauth_browser-only — SA flag rejected."""
        result = runner.invoke(app, ["login", "--start", "--service-account"])
        assert result.exit_code == 3
        # Rich wraps long lines; assert on a fragment that survives wrapping.
        assert "--service-account" in result.output
        assert "oauth_browser-only" in result.output

    def test_start_and_name(self, runner: CliRunner) -> None:
        """``--start`` + ``--name`` rejected (name is a finish-time decision)."""
        result = runner.invoke(app, ["login", "--start", "--name", "foo"])
        assert result.exit_code == 3
        assert "--start cannot accept" in result.output


class TestResumeMissing:
    """``--resume`` on a non-existent placeholder → ConfigError, exit 1."""

    def test_resume_missing_path_raises(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        """Bogus placeholder path → ConfigError, exit 1."""
        bogus = tmp_path / ".tmp-deadbeef"
        result = runner.invoke(app, ["login", "--resume", str(bogus)])
        assert result.exit_code == 1
        assert "does not exist" in result.output
