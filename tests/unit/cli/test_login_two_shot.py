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
from urllib.parse import urlparse

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
        # Compare hostname rather than substring so a future bug that
        # builds e.g. ``https://eu.mixpanel.com.attacker.example/`` would
        # still trip this test (also keeps CodeQL's
        # ``incomplete-url-substring-sanitization`` rule quiet).
        assert urlparse(payload["authorize_url"]).hostname == "eu.mixpanel.com"


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
        """Bogus placeholder path under accounts_root → ConfigError, exit 1."""
        # Place the bogus path under accounts_root so the path-traversal
        # guard does not fire before the existence check.
        from mixpanel_headless._internal.auth.storage import accounts_root

        accounts_root().mkdir(parents=True, exist_ok=True, mode=0o700)
        bogus = accounts_root() / ".tmp-deadbeef"
        result = runner.invoke(app, ["login", "--resume", str(bogus)])
        assert result.exit_code == 1
        # Rich wraps long error lines, so collapse whitespace before
        # substring matching to avoid coupling the test to terminal width.
        normalized = " ".join(result.output.split())
        assert "does not exist" in normalized

    def test_resume_path_outside_accounts_root_raises(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        """``--resume /tmp/.tmp-foo`` (outside accounts_root) → ConfigError.

        Path-traversal guard: ``--resume`` will rename the placeholder
        into ``accounts_root()``. If a caller hands us an arbitrary
        on-disk path, we'd silently exfiltrate whoever's tokens are
        sitting there. Reject before reading anything.
        """
        # tmp_path/.tmp-foo lives outside ``accounts_root()`` (which is
        # tmp_path/.mp/accounts under the isolated_home fixture).
        outside = tmp_path / ".tmp-foo-outside"
        outside.mkdir(mode=0o700)
        (outside / "tokens.json").write_text("{}", encoding="utf-8")
        result = runner.invoke(app, ["login", "--resume", str(outside)])
        assert result.exit_code == 1
        normalized = " ".join(result.output.split())
        assert "must live under" in normalized

    def test_resume_corrupt_meta_does_not_delete_placeholder(
        self,
        runner: CliRunner,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Corrupt meta.json → loud error, placeholder preserved.

        Previously the silent ``us`` fallback could hand an EU
        placeholder to ``_publish_account_from_tokens``, raise
        ``NeedsRegionSwitchError``, and delete the recoverable
        tokens. Now: corrupt meta raises before any cleanup runs,
        so the user can repair meta.json and retry.
        """
        from mixpanel_headless._internal.auth.inflight import (
            new_placeholder_dir,
        )
        from mixpanel_headless._internal.auth.storage import accounts_root

        accounts_root().mkdir(parents=True, exist_ok=True, mode=0o700)
        placeholder = new_placeholder_dir(accounts_root())
        (placeholder / "tokens.json").write_text(
            json.dumps(
                {
                    "access_token": "ya29.access",
                    "refresh_token": "1//refresh",
                    "expires_at": "2099-01-01T00:00:00+00:00",
                    "scope": "read write",
                    "token_type": "Bearer",
                }
            ),
            encoding="utf-8",
        )
        (placeholder / "meta.json").write_text("not json", encoding="utf-8")

        result = runner.invoke(app, ["login", "--resume", str(placeholder)])
        assert result.exit_code != 0
        # Placeholder must remain on disk so the user can fix meta.json
        # by hand and retry without losing their tokens.
        assert placeholder.exists()
        assert (placeholder / "tokens.json").exists()


class TestPostExchangeFailureSurfacesPlaceholder:
    """Token exchange succeeds + publish fails → envelope carries placeholder.

    Codex review [P2]: when post-exchange publish fails (bad --name,
    project not visible, /me parse error), the OAuth code is consumed
    and re-running --finish would fail at exchange. The user must
    `mp login --resume <PATH>` instead — but they need the path. The
    LoginFinishPublishError wrap surfaces it through a structured JSON
    envelope.
    """

    def test_invalid_name_emits_publish_failure_envelope(
        self,
        runner: CliRunner,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        """Bad --name passes the regex but trips the path-traversal guard."""
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

        result_start = runner.invoke(app, ["login", "--start"])
        assert result_start.exit_code == 0
        state = (
            json.loads(result_start.stdout)["authorize_url"]
            .split("state=")[1]
            .split("&")[0]
        )
        redirect = f"http://localhost:19284/callback?code=foo&state={state}"

        # --name "../escape" fails the account_dir regex AFTER tokens.json
        # is written to the placeholder. The wrap should surface the
        # placeholder path.
        result = runner.invoke(
            app,
            ["login", "--finish", redirect, "--name", "../escape"],
        )
        assert result.exit_code == 1, result.output
        payload = json.loads(result.stdout)
        assert payload["state"] == "error"
        assert payload["error"]["code"] == "LOGIN_FINISH_PUBLISH_FAILED"
        assert payload["error"]["actionable"] is True
        assert payload["error"]["details"]["placeholder_dir"].endswith(
            tuple(
                f"{name}"
                for name in payload["error"]["details"]["placeholder_dir"].split("/")[
                    -1:
                ]
            )
        )
        # Original cause is preserved so consumers can still branch on it.
        assert payload["error"]["details"]["original_code"] == "CONFIG_ERROR"
        # Resume hint with exact command.
        resume_cmd = payload["resume_hint"]["command"]
        assert resume_cmd.startswith("mp login --resume ")
        assert ".tmp-" in resume_cmd

        # Placeholder dir must still exist on disk so --resume actually works.
        placeholder_path = Path(payload["error"]["details"]["placeholder_dir"])
        assert placeholder_path.exists()
        assert (placeholder_path / "tokens.json").exists()

        # Inflight should be cleared (code is consumed; re-running --finish
        # with the same paste would fail at exchange anyway).
        from mixpanel_headless._internal.auth.inflight import inflight_path

        assert not inflight_path().exists()

    def test_project_not_visible_emits_publish_failure_envelope(
        self,
        runner: CliRunner,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """--project ID not in /me → wrapped as LoginFinishPublishError."""
        _stub_dcr(monkeypatch)
        _stub_exchange(monkeypatch)
        _stub_me(
            monkeypatch,
            _me_payload(
                {
                    "100": {
                        "name": "Visible",
                        "organization_id": 1,
                        "domain": "mixpanel.com",
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

        result = runner.invoke(
            app,
            ["login", "--finish", redirect, "--project", "999"],
        )
        assert result.exit_code == 1, result.output
        payload = json.loads(result.stdout)
        assert payload["state"] == "error"
        assert payload["error"]["code"] == "LOGIN_FINISH_PUBLISH_FAILED"
        # Underlying ProjectNotFoundError code is preserved.
        assert payload["error"]["details"]["original_code"] == "PROJECT_NOT_FOUND"
        assert "mp login --resume" in payload["resume_hint"]["command"]


class TestCrossRegionCleansUpPlaceholder:
    """NeedsRegionSwitchError must NOT leave the placeholder on disk.

    Cross-region is fundamental, not transient — re-running --resume
    against the same placeholder hits the exact same error. The CLI
    should clean up the placeholder so the user can `mp login --start
    --region eu` cleanly without orphan dirs.
    """

    def test_cross_region_removes_placeholder(
        self,
        runner: CliRunner,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        """After NEEDS_REGION_SWITCH, ~/.mp/accounts/.tmp-* is gone."""
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

        # No orphan placeholder dirs.
        accounts_dir = tmp_path / ".mp" / "accounts"
        if accounts_dir.exists():
            leftovers = [
                p for p in accounts_dir.iterdir() if p.name.startswith(".tmp-")
            ]
            assert leftovers == [], (
                f"Cross-region failure left orphan placeholder(s): {leftovers}"
            )
