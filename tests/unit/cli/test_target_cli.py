"""Smoke tests for the ``mp target`` CLI command group.

Verifies that each subcommand (``add`` / ``use`` / ``list`` / ``show`` /
``remove``) round-trips through the underlying ``mixpanel_headless.targets``
namespace and that the on-disk ``[active]`` block reflects the applied
target's three axes.

Reference: specs/042-auth-architecture-redesign/contracts/cli-commands.md §6.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import SecretStr
from typer.testing import CliRunner

from mixpanel_headless import accounts as accounts_ns
from mixpanel_headless._internal.config import ConfigManager
from mixpanel_headless.cli.main import app


@pytest.fixture(autouse=True)
def _isolated_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Isolate $HOME and MP_CONFIG_PATH for hermetic CLI tests."""
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("MP_CONFIG_PATH", str(tmp_path / ".mp" / "config.toml"))


@pytest.fixture
def runner() -> CliRunner:
    """Return a fresh CliRunner for each test."""
    return CliRunner()


@pytest.fixture
def seeded_account() -> ConfigManager:
    """Add a service-account so target add/use have a real referent."""
    accounts_ns.add(
        "team",
        type="service_account",
        region="us",
        default_project="3713224",
        username="u",
        secret=SecretStr("s"),
    )
    return ConfigManager()


class TestTargetAdd:
    """``mp target add`` writes a new ``[targets.NAME]`` block."""

    def test_add_with_workspace(
        self, runner: CliRunner, seeded_account: ConfigManager
    ) -> None:
        """``add NAME --account A --project P --workspace W`` succeeds."""
        result = runner.invoke(
            app,
            [
                "target",
                "add",
                "ecom",
                "--account",
                "team",
                "--project",
                "3018488",
                "--workspace",
                "42",
            ],
        )
        assert result.exit_code == 0, result.output
        target = seeded_account.get_target("ecom")
        assert target.account == "team"
        assert target.project == "3018488"
        assert target.workspace == 42

    def test_add_without_workspace(
        self, runner: CliRunner, seeded_account: ConfigManager
    ) -> None:
        """``add NAME --account A --project P`` defaults workspace to None."""
        result = runner.invoke(
            app,
            [
                "target",
                "add",
                "ecom",
                "--account",
                "team",
                "--project",
                "3018488",
            ],
        )
        assert result.exit_code == 0, result.output
        target = seeded_account.get_target("ecom")
        assert target.workspace is None

    def test_add_missing_account_fails(
        self, runner: CliRunner, seeded_account: ConfigManager
    ) -> None:
        """Referencing a non-existent account exits non-zero."""
        result = runner.invoke(
            app,
            [
                "target",
                "add",
                "ecom",
                "--account",
                "nope",
                "--project",
                "3018488",
            ],
        )
        assert result.exit_code != 0


class TestTargetUse:
    """``mp target use NAME`` writes ``[active]`` axes atomically."""

    def test_use_writes_active(
        self, runner: CliRunner, seeded_account: ConfigManager
    ) -> None:
        """``use ecom`` sets account / workspace / account.default_project."""
        runner.invoke(
            app,
            [
                "target",
                "add",
                "ecom",
                "--account",
                "team",
                "--project",
                "3018488",
                "--workspace",
                "42",
            ],
        )
        result = runner.invoke(app, ["target", "use", "ecom"])
        assert result.exit_code == 0, result.output
        active = seeded_account.get_active()
        assert active.account == "team"
        assert active.workspace == 42
        # apply_target also syncs the account's default_project.
        account = seeded_account.get_account("team")
        assert account.default_project == "3018488"

    def test_use_missing_target_fails(
        self, runner: CliRunner, seeded_account: ConfigManager
    ) -> None:
        """Applying a non-existent target exits non-zero."""
        result = runner.invoke(app, ["target", "use", "nope"])
        assert result.exit_code != 0


class TestTargetList:
    """``mp target list`` returns table / json output."""

    def test_list_empty_table(
        self, runner: CliRunner, seeded_account: ConfigManager
    ) -> None:
        """Empty list under default (table) format prints an empty marker."""
        result = runner.invoke(app, ["target", "list"])
        assert result.exit_code == 0, result.output
        assert "no targets" in result.output

    def test_list_json(self, runner: CliRunner, seeded_account: ConfigManager) -> None:
        """``list --format json`` emits a parseable JSON array."""
        runner.invoke(
            app,
            [
                "target",
                "add",
                "ecom",
                "--account",
                "team",
                "--project",
                "3018488",
            ],
        )
        result = runner.invoke(app, ["target", "list", "--format", "json"])
        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)
        assert isinstance(payload, list)
        assert payload[0]["name"] == "ecom"
        assert payload[0]["account"] == "team"
        assert payload[0]["project"] == "3018488"


class TestTargetShow:
    """``mp target show NAME`` returns the named target."""

    def test_show_json(self, runner: CliRunner, seeded_account: ConfigManager) -> None:
        """``show ecom --format json`` emits a single JSON object."""
        runner.invoke(
            app,
            [
                "target",
                "add",
                "ecom",
                "--account",
                "team",
                "--project",
                "3018488",
            ],
        )
        result = runner.invoke(app, ["target", "show", "ecom", "--format", "json"])
        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)
        assert payload["name"] == "ecom"
        assert payload["project"] == "3018488"

    def test_show_missing_fails(
        self, runner: CliRunner, seeded_account: ConfigManager
    ) -> None:
        """Showing a non-existent target exits non-zero."""
        result = runner.invoke(app, ["target", "show", "nope"])
        assert result.exit_code != 0


class TestTargetRemove:
    """``mp target remove NAME`` deletes the target block."""

    def test_remove_with_yes(
        self, runner: CliRunner, seeded_account: ConfigManager
    ) -> None:
        """``remove ecom --yes`` skips the prompt and deletes."""
        runner.invoke(
            app,
            [
                "target",
                "add",
                "ecom",
                "--account",
                "team",
                "--project",
                "3018488",
            ],
        )
        result = runner.invoke(app, ["target", "remove", "ecom", "--yes"])
        assert result.exit_code == 0, result.output
        assert seeded_account.list_targets() == []
