"""Integration tests for flags CLI commands."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from mixpanel_data.cli.main import app
from mixpanel_data.types import (
    FeatureFlagListResult,
    FeatureFlagResult,
)

# =============================================================================
# Fixtures / Helpers
# =============================================================================


SAMPLE_FLAG = FeatureFlagResult(
    id="abc-123-def",
    name="Dark Mode",
    key="dark_mode",
    description="Enable dark mode",
    status="active",
    tags=["ui", "experiment"],
    ruleset={"variants": [{"key": "on", "value": True}]},
    created="2024-01-01T00:00:00Z",
    modified="2024-06-01T00:00:00Z",
    creator_name="Test User",
)

SAMPLE_FLAG_2 = FeatureFlagResult(
    id="xyz-789-uvw",
    name="New Checkout",
    key="new_checkout",
    status="draft",
    tags=[],
    ruleset={},
)


# =============================================================================
# mp flags list
# =============================================================================


class TestFlagsList:
    """Tests for mp flags list command."""

    def test_list_flags_json(
        self, cli_runner: CliRunner, mock_workspace: MagicMock
    ) -> None:
        """Test listing flags in JSON format."""
        mock_workspace.feature_flags.return_value = FeatureFlagListResult(
            flags=[SAMPLE_FLAG, SAMPLE_FLAG_2]
        )

        with patch(
            "mixpanel_data.cli.commands.flags.get_workspace",
            return_value=mock_workspace,
        ):
            result = cli_runner.invoke(app, ["flags", "list", "--format", "json"])

        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert isinstance(data, list)
        assert len(data) == 2
        assert data[0]["name"] == "Dark Mode"

    def test_list_flags_table(
        self, cli_runner: CliRunner, mock_workspace: MagicMock
    ) -> None:
        """Test listing flags in table format."""
        mock_workspace.feature_flags.return_value = FeatureFlagListResult(
            flags=[SAMPLE_FLAG]
        )

        with patch(
            "mixpanel_data.cli.commands.flags.get_workspace",
            return_value=mock_workspace,
        ):
            result = cli_runner.invoke(app, ["flags", "list", "--format", "table"])

        assert result.exit_code == 0
        # Rich table may wrap/truncate "Dark Mode" across cells
        assert "Dark" in result.stdout

    def test_list_flags_empty(
        self, cli_runner: CliRunner, mock_workspace: MagicMock
    ) -> None:
        """Test listing flags when none exist."""
        mock_workspace.feature_flags.return_value = FeatureFlagListResult(flags=[])

        with patch(
            "mixpanel_data.cli.commands.flags.get_workspace",
            return_value=mock_workspace,
        ):
            result = cli_runner.invoke(app, ["flags", "list", "--format", "json"])

        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data == []

    def test_list_flags_include_archived(
        self, cli_runner: CliRunner, mock_workspace: MagicMock
    ) -> None:
        """Test --include-archived flag is passed to workspace."""
        mock_workspace.feature_flags.return_value = FeatureFlagListResult(flags=[])

        with patch(
            "mixpanel_data.cli.commands.flags.get_workspace",
            return_value=mock_workspace,
        ):
            result = cli_runner.invoke(app, ["flags", "list", "--include-archived"])

        assert result.exit_code == 0
        mock_workspace.feature_flags.assert_called_once_with(include_archived=True)

    def test_list_flags_jq_filter(
        self, cli_runner: CliRunner, mock_workspace: MagicMock
    ) -> None:
        """Test --jq filter on list output."""
        mock_workspace.feature_flags.return_value = FeatureFlagListResult(
            flags=[SAMPLE_FLAG, SAMPLE_FLAG_2]
        )

        with patch(
            "mixpanel_data.cli.commands.flags.get_workspace",
            return_value=mock_workspace,
        ):
            result = cli_runner.invoke(
                app,
                ["flags", "list", "--format", "json", "--jq", ".[0].name"],
            )

        assert result.exit_code == 0
        assert "Dark Mode" in result.stdout


# =============================================================================
# mp flags get
# =============================================================================


class TestFlagsGet:
    """Tests for mp flags get command."""

    def test_get_flag_json(
        self, cli_runner: CliRunner, mock_workspace: MagicMock
    ) -> None:
        """Test getting a flag in JSON format."""
        mock_workspace.feature_flag.return_value = SAMPLE_FLAG

        with patch(
            "mixpanel_data.cli.commands.flags.get_workspace",
            return_value=mock_workspace,
        ):
            result = cli_runner.invoke(
                app, ["flags", "get", "abc-123-def", "--format", "json"]
            )

        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["name"] == "Dark Mode"
        assert data["key"] == "dark_mode"
        mock_workspace.feature_flag.assert_called_once_with("abc-123-def")

    def test_get_flag_jq_filter(
        self, cli_runner: CliRunner, mock_workspace: MagicMock
    ) -> None:
        """Test --jq filter on get output."""
        mock_workspace.feature_flag.return_value = SAMPLE_FLAG

        with patch(
            "mixpanel_data.cli.commands.flags.get_workspace",
            return_value=mock_workspace,
        ):
            result = cli_runner.invoke(
                app,
                ["flags", "get", "abc-123-def", "--jq", ".ruleset"],
            )

        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert "variants" in data


# =============================================================================
# mp flags create
# =============================================================================


class TestFlagsCreate:
    """Tests for mp flags create command."""

    def test_create_flag_from_file(
        self,
        cli_runner: CliRunner,
        mock_workspace: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Test creating a flag from a config file."""
        config = {"name": "Test Flag", "key": "test_flag", "ruleset": {}}
        config_file = tmp_path / "flag.json"
        config_file.write_text(json.dumps(config))

        mock_workspace.create_feature_flag.return_value = SAMPLE_FLAG

        with patch(
            "mixpanel_data.cli.commands.flags.get_workspace",
            return_value=mock_workspace,
        ):
            result = cli_runner.invoke(
                app,
                ["flags", "create", "--config-file", str(config_file)],
            )

        assert result.exit_code == 0
        mock_workspace.create_feature_flag.assert_called_once_with(config)

    def test_create_flag_with_overrides(
        self,
        cli_runner: CliRunner,
        mock_workspace: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Test --name and --key override values from config file."""
        config = {"name": "Original", "key": "original"}
        config_file = tmp_path / "flag.json"
        config_file.write_text(json.dumps(config))

        mock_workspace.create_feature_flag.return_value = SAMPLE_FLAG

        with patch(
            "mixpanel_data.cli.commands.flags.get_workspace",
            return_value=mock_workspace,
        ):
            result = cli_runner.invoke(
                app,
                [
                    "flags",
                    "create",
                    "--config-file",
                    str(config_file),
                    "--name",
                    "Overridden",
                    "--key",
                    "overridden_key",
                ],
            )

        assert result.exit_code == 0
        call_args = mock_workspace.create_feature_flag.call_args[0][0]
        assert call_args["name"] == "Overridden"
        assert call_args["key"] == "overridden_key"

    def test_create_flag_config_not_found(self, cli_runner: CliRunner) -> None:
        """Test error when config file doesn't exist."""
        result = cli_runner.invoke(
            app,
            ["flags", "create", "--config-file", "/nonexistent/flag.json"],
        )

        assert result.exit_code == 4
        assert "Config file not found" in result.output

    def test_create_flag_invalid_json(
        self,
        cli_runner: CliRunner,
        tmp_path: Path,
    ) -> None:
        """Test error when config file contains invalid JSON."""
        config_file = tmp_path / "bad.json"
        config_file.write_text("not json {{{")

        result = cli_runner.invoke(
            app,
            ["flags", "create", "--config-file", str(config_file)],
        )

        assert result.exit_code == 3
        assert "Invalid JSON" in result.output

    def test_create_flag_from_stdin(
        self,
        cli_runner: CliRunner,
        mock_workspace: MagicMock,
    ) -> None:
        """Test creating a flag from stdin."""
        config = {"name": "Stdin Flag", "key": "stdin_flag"}
        mock_workspace.create_feature_flag.return_value = SAMPLE_FLAG

        with patch(
            "mixpanel_data.cli.commands.flags.get_workspace",
            return_value=mock_workspace,
        ):
            result = cli_runner.invoke(
                app,
                ["flags", "create", "--config-file", "-"],
                input=json.dumps(config),
            )

        assert result.exit_code == 0
        mock_workspace.create_feature_flag.assert_called_once_with(config)


# =============================================================================
# mp flags update
# =============================================================================


class TestFlagsUpdate:
    """Tests for mp flags update command."""

    def test_update_flag_from_file(
        self,
        cli_runner: CliRunner,
        mock_workspace: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Test updating a flag from a config file."""
        config = {"name": "Updated", "key": "test_flag"}
        config_file = tmp_path / "flag.json"
        config_file.write_text(json.dumps(config))

        mock_workspace.update_feature_flag.return_value = SAMPLE_FLAG

        with patch(
            "mixpanel_data.cli.commands.flags.get_workspace",
            return_value=mock_workspace,
        ):
            result = cli_runner.invoke(
                app,
                [
                    "flags",
                    "update",
                    "abc-123-def",
                    "--config-file",
                    str(config_file),
                ],
            )

        assert result.exit_code == 0
        mock_workspace.update_feature_flag.assert_called_once_with(
            "abc-123-def", config
        )

    def test_update_flag_with_status_override(
        self,
        cli_runner: CliRunner,
        mock_workspace: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Test --status override on update."""
        config = {"name": "Flag", "key": "flag"}
        config_file = tmp_path / "flag.json"
        config_file.write_text(json.dumps(config))

        mock_workspace.update_feature_flag.return_value = SAMPLE_FLAG

        with patch(
            "mixpanel_data.cli.commands.flags.get_workspace",
            return_value=mock_workspace,
        ):
            result = cli_runner.invoke(
                app,
                [
                    "flags",
                    "update",
                    "abc-123-def",
                    "--config-file",
                    str(config_file),
                    "--status",
                    "disabled",
                ],
            )

        assert result.exit_code == 0
        call_args = mock_workspace.update_feature_flag.call_args[0]
        assert call_args[1]["status"] == "disabled"


# =============================================================================
# mp flags delete
# =============================================================================


class TestFlagsDelete:
    """Tests for mp flags delete command."""

    def test_delete_flag(
        self, cli_runner: CliRunner, mock_workspace: MagicMock
    ) -> None:
        """Test deleting a flag."""
        mock_workspace.delete_feature_flag.return_value = {"status": "ok"}

        with patch(
            "mixpanel_data.cli.commands.flags.get_workspace",
            return_value=mock_workspace,
        ):
            result = cli_runner.invoke(app, ["flags", "delete", "abc-123-def"])

        assert result.exit_code == 0
        mock_workspace.delete_feature_flag.assert_called_once_with("abc-123-def")
        assert "deleted" in result.output.lower()


# =============================================================================
# mp flags archive
# =============================================================================


class TestFlagsArchive:
    """Tests for mp flags archive command."""

    def test_archive_flag(
        self, cli_runner: CliRunner, mock_workspace: MagicMock
    ) -> None:
        """Test archiving a flag."""
        mock_workspace.archive_feature_flag.return_value = {"status": "ok"}

        with patch(
            "mixpanel_data.cli.commands.flags.get_workspace",
            return_value=mock_workspace,
        ):
            result = cli_runner.invoke(app, ["flags", "archive", "abc-123-def"])

        assert result.exit_code == 0
        mock_workspace.archive_feature_flag.assert_called_once_with("abc-123-def")
        assert "archived" in result.output.lower()


# =============================================================================
# mp flags restore
# =============================================================================


class TestFlagsRestore:
    """Tests for mp flags restore command."""

    def test_restore_flag(
        self, cli_runner: CliRunner, mock_workspace: MagicMock
    ) -> None:
        """Test restoring a flag."""
        mock_workspace.restore_feature_flag.return_value = {"status": "ok"}

        with patch(
            "mixpanel_data.cli.commands.flags.get_workspace",
            return_value=mock_workspace,
        ):
            result = cli_runner.invoke(app, ["flags", "restore", "abc-123-def"])

        assert result.exit_code == 0
        mock_workspace.restore_feature_flag.assert_called_once_with("abc-123-def")
        assert "restored" in result.output.lower()


# =============================================================================
# Help Text
# =============================================================================


class TestFlagsHelp:
    """Tests for flags command help output."""

    def test_flags_help(self, cli_runner: CliRunner) -> None:
        """Test that mp flags --help renders."""
        result = cli_runner.invoke(app, ["flags", "--help"])

        assert result.exit_code == 0
        assert (
            "feature flags" in result.stdout.lower() or "flags" in result.stdout.lower()
        )

    def test_flags_no_args_shows_help(self, cli_runner: CliRunner) -> None:
        """Test that mp flags with no args shows help text."""
        result = cli_runner.invoke(app, ["flags"])

        # no_args_is_help=True causes Typer to show help and exit with code 0 or 2
        assert result.exit_code in (0, 2)
