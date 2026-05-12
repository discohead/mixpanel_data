"""CLI tests for ``mp account export-bridge`` / ``remove-bridge`` and ``mp session --bridge``.

Reference:
    specs/042-auth-architecture-redesign/contracts/cli-commands.md §3.10–§3.11, §7
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from typer.testing import CliRunner

from mixpanel_headless.cli.main import app


@pytest.fixture(autouse=True)
def _isolated_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Isolate $HOME / MP_CONFIG_PATH / MP_AUTH_FILE for hermetic CLI runs."""
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("MP_CONFIG_PATH", str(tmp_path / ".mp" / "config.toml"))
    monkeypatch.delenv("MP_AUTH_FILE", raising=False)


@pytest.fixture
def runner() -> CliRunner:
    """Typer test runner."""
    return CliRunner()


def _seed_browser_tokens(home: Path, name: str) -> None:
    """Write a fake on-disk tokens.json for an oauth_browser account."""
    account_dir = home / ".mp" / "accounts" / name
    account_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    tokens_path = account_dir / "tokens.json"
    expires_at = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
    tokens_path.write_text(
        json.dumps(
            {
                "access_token": f"acc-{name}",
                "refresh_token": "ref",
                "expires_at": expires_at,
                "scope": "read",
                "token_type": "Bearer",
            }
        ),
        encoding="utf-8",
    )
    tokens_path.chmod(0o600)


class TestExportBridgeCli:
    """``mp account export-bridge`` writes a bridge file at the requested path."""

    def test_service_account_export_happy_path(
        self,
        runner: CliRunner,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """SA account exports successfully (exit 0, file written)."""
        monkeypatch.setenv("MP_SECRET", "supersecret")
        runner.invoke(
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
                "--project",
                "3713224",
            ],
        )
        out = tmp_path / "bridge.json"
        result = runner.invoke(
            app, ["account", "export-bridge", "--to", str(out), "--account", "team"]
        )
        assert result.exit_code == 0, result.output
        assert out.exists()
        # Contains the secret inline by design (B3 — Cowork crosses a trust boundary)
        bridge_payload = json.loads(out.read_text(encoding="utf-8"))
        assert bridge_payload["version"] == 2
        assert bridge_payload["account"]["name"] == "team"
        # Secret must NOT leak to stdout/stderr
        assert "supersecret" not in result.output

    def test_oauth_browser_without_tokens_exits_nonzero(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        """Exporting oauth_browser without on-disk tokens exits non-zero."""
        runner.invoke(
            app,
            ["account", "add", "personal", "--type", "oauth_browser", "--region", "us"],
        )
        out = tmp_path / "bridge.json"
        result = runner.invoke(
            app,
            ["account", "export-bridge", "--to", str(out), "--account", "personal"],
        )
        assert result.exit_code != 0, result.output
        assert not out.exists()

    def test_oauth_browser_with_tokens_embeds_them(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        """Tokens at ``~/.mp/accounts/{name}/tokens.json`` get embedded."""
        runner.invoke(
            app,
            ["account", "add", "personal", "--type", "oauth_browser", "--region", "us"],
        )
        _seed_browser_tokens(tmp_path, "personal")
        out = tmp_path / "bridge.json"
        result = runner.invoke(
            app,
            ["account", "export-bridge", "--to", str(out), "--account", "personal"],
        )
        assert result.exit_code == 0, result.output
        bridge = json.loads(out.read_text(encoding="utf-8"))
        assert bridge["tokens"]["access_token"] == "acc-personal"

    def test_pinned_project_and_workspace_round_trip(
        self,
        runner: CliRunner,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """``--project`` and ``--workspace`` propagate into the bridge file."""
        monkeypatch.setenv("MP_SECRET", "s")
        runner.invoke(
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
                "--project",
                "3713224",
            ],
        )
        out = tmp_path / "bridge.json"
        result = runner.invoke(
            app,
            [
                "account",
                "export-bridge",
                "--to",
                str(out),
                "--account",
                "team",
                "--project",
                "3018488",
                "--workspace",
                "3448414",
            ],
        )
        assert result.exit_code == 0, result.output
        bridge = json.loads(out.read_text(encoding="utf-8"))
        assert bridge["project"] == "3018488"
        assert bridge["workspace"] == 3448414


class TestRemoveBridgeCli:
    """``mp account remove-bridge`` deletes the bridge file (or no-ops)."""

    def test_remove_existing_bridge(self, runner: CliRunner, tmp_path: Path) -> None:
        """Removing an existing bridge exits 0 and deletes the file."""
        target = tmp_path / "bridge.json"
        target.write_text("{}", encoding="utf-8")
        result = runner.invoke(app, ["account", "remove-bridge", "--at", str(target)])
        assert result.exit_code == 0, result.output
        assert not target.exists()

    def test_remove_already_absent_exits_zero(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        """Removing a non-existent bridge still exits 0 (idempotent)."""
        target = tmp_path / "nope.json"
        result = runner.invoke(app, ["account", "remove-bridge", "--at", str(target)])
        assert result.exit_code == 0, result.output


class TestSessionBridgeFlag:
    """``mp session --bridge`` shows bridge file source."""

    def test_session_bridge_with_no_bridge_present(self, runner: CliRunner) -> None:
        """``mp session --bridge`` when no bridge exists prints 'no bridge'."""
        result = runner.invoke(app, ["session", "--bridge"])
        # Exit cleanly even when no bridge is found.
        assert result.exit_code == 0, result.output
        assert "bridge" in result.output.lower()

    def test_session_bridge_with_bridge_present(
        self,
        runner: CliRunner,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """``mp session --bridge`` reflects the bridge file when MP_AUTH_FILE is set."""
        bridge_path = tmp_path / "bridge.json"
        bridge_path.write_text(
            json.dumps(
                {
                    "version": 2,
                    "account": {
                        "type": "service_account",
                        "name": "personal",
                        "region": "us",
                        "username": "u",
                        "secret": "s",
                    },
                    "project": "3713224",
                    "workspace": 3448413,
                    "headers": {"X-Mixpanel-Cluster": "internal-1"},
                }
            ),
            encoding="utf-8",
        )
        bridge_path.chmod(0o600)
        monkeypatch.setenv("MP_AUTH_FILE", str(bridge_path))
        result = runner.invoke(app, ["session", "--bridge"])
        assert result.exit_code == 0, result.output
        assert "personal" in result.output
        assert "3713224" in result.output
        assert "3448413" in result.output
        assert "X-Mixpanel-Cluster" in result.output
