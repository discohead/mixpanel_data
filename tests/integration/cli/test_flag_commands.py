# ruff: noqa: ARG001
"""Integration tests for feature flag CLI commands."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from mixpanel_headless.cli.main import app


class TestFlagsList:
    """Tests for mp flags list command."""

    def test_list_json(self, cli_runner: CliRunner, mock_workspace: MagicMock) -> None:
        """Test flags list in JSON format."""
        with patch(
            "mixpanel_headless.cli.commands.flags.get_workspace",
            return_value=mock_workspace,
        ):
            result = cli_runner.invoke(app, ["flags", "list", "--format", "json"])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert isinstance(data, list)
        assert data[0]["id"] == "abc-123"
        assert data[0]["name"] == "Test Flag"

    def test_list_table_format(
        self, cli_runner: CliRunner, mock_workspace: MagicMock
    ) -> None:
        """Test flags list in table format."""
        with patch(
            "mixpanel_headless.cli.commands.flags.get_workspace",
            return_value=mock_workspace,
        ):
            result = cli_runner.invoke(app, ["flags", "list", "--format", "table"])
        assert result.exit_code == 0
        assert len(result.stdout.strip()) > 0

    def test_list_empty(self, cli_runner: CliRunner, mock_workspace: MagicMock) -> None:
        """Test flags list with no results."""
        mock_workspace.list_feature_flags.return_value = []
        with patch(
            "mixpanel_headless.cli.commands.flags.get_workspace",
            return_value=mock_workspace,
        ):
            result = cli_runner.invoke(app, ["flags", "list", "--format", "json"])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data == []

    def test_list_include_archived(
        self, cli_runner: CliRunner, mock_workspace: MagicMock
    ) -> None:
        """Test flags list with --include-archived flag."""
        with patch(
            "mixpanel_headless.cli.commands.flags.get_workspace",
            return_value=mock_workspace,
        ):
            result = cli_runner.invoke(app, ["flags", "list", "--include-archived"])
        assert result.exit_code == 0
        mock_workspace.list_feature_flags.assert_called_once_with(include_archived=True)


class TestFlagsCreate:
    """Tests for mp flags create command."""

    def test_create_minimal(
        self, cli_runner: CliRunner, mock_workspace: MagicMock
    ) -> None:
        """Test creating a flag with only required options."""
        with patch(
            "mixpanel_headless.cli.commands.flags.get_workspace",
            return_value=mock_workspace,
        ):
            result = cli_runner.invoke(
                app,
                ["flags", "create", "--name", "New Flag", "--key", "new_flag"],
            )
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert "id" in data

    def test_create_all_options(
        self, cli_runner: CliRunner, mock_workspace: MagicMock
    ) -> None:
        """Test creating a flag with all options."""
        with patch(
            "mixpanel_headless.cli.commands.flags.get_workspace",
            return_value=mock_workspace,
        ):
            result = cli_runner.invoke(
                app,
                [
                    "flags",
                    "create",
                    "--name",
                    "Full Flag",
                    "--key",
                    "full_flag",
                    "--description",
                    "A full flag",
                    "--status",
                    "enabled",
                    "--tags",
                    "beta,release",
                    "--serving-method",
                    "server",
                    "--ruleset",
                    '{"variants": []}',
                ],
            )
        assert result.exit_code == 0
        params = mock_workspace.create_feature_flag.call_args[0][0]
        assert params.name == "Full Flag"
        assert params.key == "full_flag"
        assert params.description == "A full flag"
        assert params.tags == ["beta", "release"]

    def test_create_invalid_ruleset_json(
        self, cli_runner: CliRunner, mock_workspace: MagicMock
    ) -> None:
        """Test creating a flag with invalid ruleset JSON fails."""
        with patch(
            "mixpanel_headless.cli.commands.flags.get_workspace",
            return_value=mock_workspace,
        ):
            result = cli_runner.invoke(
                app,
                [
                    "flags",
                    "create",
                    "--name",
                    "Bad",
                    "--key",
                    "bad",
                    "--ruleset",
                    "not json",
                ],
            )
        assert result.exit_code != 0


class TestFlagsGet:
    """Tests for mp flags get command."""

    def test_get(self, cli_runner: CliRunner, mock_workspace: MagicMock) -> None:
        """Test getting a single flag by ID."""
        with patch(
            "mixpanel_headless.cli.commands.flags.get_workspace",
            return_value=mock_workspace,
        ):
            result = cli_runner.invoke(app, ["flags", "get", "abc-123"])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["id"] == "abc-123"
        assert data["key"] == "test_flag"


class TestFlagsUpdate:
    """Tests for mp flags update command."""

    def test_update_all_required(
        self, cli_runner: CliRunner, mock_workspace: MagicMock
    ) -> None:
        """Test updating a flag with all required options."""
        with patch(
            "mixpanel_headless.cli.commands.flags.get_workspace",
            return_value=mock_workspace,
        ):
            result = cli_runner.invoke(
                app,
                [
                    "flags",
                    "update",
                    "abc-123",
                    "--name",
                    "Updated",
                    "--key",
                    "updated_key",
                    "--status",
                    "enabled",
                    "--ruleset",
                    '{"variants": []}',
                ],
            )
        assert result.exit_code == 0
        params = mock_workspace.update_feature_flag.call_args[0][1]
        assert params.name == "Updated"
        assert params.key == "updated_key"

    def test_update_invalid_ruleset(
        self, cli_runner: CliRunner, mock_workspace: MagicMock
    ) -> None:
        """Test updating a flag with invalid ruleset JSON fails."""
        with patch(
            "mixpanel_headless.cli.commands.flags.get_workspace",
            return_value=mock_workspace,
        ):
            result = cli_runner.invoke(
                app,
                [
                    "flags",
                    "update",
                    "abc-123",
                    "--name",
                    "X",
                    "--key",
                    "x",
                    "--status",
                    "enabled",
                    "--ruleset",
                    "bad json",
                ],
            )
        assert result.exit_code != 0

    def test_update_with_optional_fields(
        self, cli_runner: CliRunner, mock_workspace: MagicMock
    ) -> None:
        """Test updating a flag with optional fields."""
        with patch(
            "mixpanel_headless.cli.commands.flags.get_workspace",
            return_value=mock_workspace,
        ):
            result = cli_runner.invoke(
                app,
                [
                    "flags",
                    "update",
                    "abc-123",
                    "--name",
                    "Updated",
                    "--key",
                    "updated_key",
                    "--status",
                    "enabled",
                    "--ruleset",
                    "{}",
                    "--description",
                    "Updated desc",
                    "--tags",
                    "a,b",
                    "--serving-method",
                    "server",
                ],
            )
        assert result.exit_code == 0
        params = mock_workspace.update_feature_flag.call_args[0][1]
        assert params.description == "Updated desc"
        assert params.tags == ["a", "b"]


class TestFlagsDelete:
    """Tests for mp flags delete command."""

    def test_delete(self, cli_runner: CliRunner, mock_workspace: MagicMock) -> None:
        """Test deleting a flag."""
        with patch(
            "mixpanel_headless.cli.commands.flags.get_workspace",
            return_value=mock_workspace,
        ):
            result = cli_runner.invoke(app, ["flags", "delete", "abc-123"])
        assert result.exit_code == 0
        mock_workspace.delete_feature_flag.assert_called_once_with("abc-123")


class TestFlagsArchive:
    """Tests for mp flags archive command."""

    def test_archive(self, cli_runner: CliRunner, mock_workspace: MagicMock) -> None:
        """Test archiving a flag."""
        with patch(
            "mixpanel_headless.cli.commands.flags.get_workspace",
            return_value=mock_workspace,
        ):
            result = cli_runner.invoke(app, ["flags", "archive", "abc-123"])
        assert result.exit_code == 0
        mock_workspace.archive_feature_flag.assert_called_once_with("abc-123")


class TestFlagsRestore:
    """Tests for mp flags restore command."""

    def test_restore(self, cli_runner: CliRunner, mock_workspace: MagicMock) -> None:
        """Test restoring an archived flag."""
        with patch(
            "mixpanel_headless.cli.commands.flags.get_workspace",
            return_value=mock_workspace,
        ):
            result = cli_runner.invoke(app, ["flags", "restore", "abc-123"])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["id"] == "abc-123"


class TestFlagsDuplicate:
    """Tests for mp flags duplicate command."""

    def test_duplicate(self, cli_runner: CliRunner, mock_workspace: MagicMock) -> None:
        """Test duplicating a flag."""
        with patch(
            "mixpanel_headless.cli.commands.flags.get_workspace",
            return_value=mock_workspace,
        ):
            result = cli_runner.invoke(app, ["flags", "duplicate", "abc-123"])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["id"] == "abc-123"


class TestFlagsSetTestUsers:
    """Tests for mp flags set-test-users command."""

    def test_set_test_users(
        self, cli_runner: CliRunner, mock_workspace: MagicMock
    ) -> None:
        """Test setting test users on a flag."""
        with patch(
            "mixpanel_headless.cli.commands.flags.get_workspace",
            return_value=mock_workspace,
        ):
            result = cli_runner.invoke(
                app,
                [
                    "flags",
                    "set-test-users",
                    "abc-123",
                    "--users",
                    '{"on": "user-1", "off": "user-2"}',
                ],
            )
        assert result.exit_code == 0
        mock_workspace.set_flag_test_users.assert_called_once()

    def test_set_test_users_invalid_json(
        self, cli_runner: CliRunner, mock_workspace: MagicMock
    ) -> None:
        """Test set-test-users with invalid JSON fails."""
        with patch(
            "mixpanel_headless.cli.commands.flags.get_workspace",
            return_value=mock_workspace,
        ):
            result = cli_runner.invoke(
                app,
                [
                    "flags",
                    "set-test-users",
                    "abc-123",
                    "--users",
                    "not json",
                ],
            )
        assert result.exit_code != 0


class TestFlagsHistory:
    """Tests for mp flags history command."""

    def test_history(self, cli_runner: CliRunner, mock_workspace: MagicMock) -> None:
        """Test getting flag history."""
        with patch(
            "mixpanel_headless.cli.commands.flags.get_workspace",
            return_value=mock_workspace,
        ):
            result = cli_runner.invoke(app, ["flags", "history", "abc-123"])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert "events" in data
        assert "count" in data

    def test_history_with_pagination(
        self, cli_runner: CliRunner, mock_workspace: MagicMock
    ) -> None:
        """Test getting flag history with pagination options."""
        with patch(
            "mixpanel_headless.cli.commands.flags.get_workspace",
            return_value=mock_workspace,
        ):
            result = cli_runner.invoke(
                app,
                [
                    "flags",
                    "history",
                    "abc-123",
                    "--page",
                    "cursor123",
                    "--page-size",
                    "50",
                ],
            )
        assert result.exit_code == 0
        mock_workspace.get_flag_history.assert_called_once_with(
            "abc-123", page="cursor123", page_size=50
        )


class TestFlagsLimits:
    """Tests for mp flags limits command."""

    def test_limits(self, cli_runner: CliRunner, mock_workspace: MagicMock) -> None:
        """Test getting flag limits."""
        with patch(
            "mixpanel_headless.cli.commands.flags.get_workspace",
            return_value=mock_workspace,
        ):
            result = cli_runner.invoke(app, ["flags", "limits"])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["limit"] == 100
        assert data["current_usage"] == 5
        assert data["contract_status"] == "active"


class TestFlagsInputValidation:
    """Tests for input validation on flag commands."""

    def test_no_args_shows_help(
        self,
        cli_runner: CliRunner,
        mock_workspace: MagicMock,  # noqa: ARG002
    ) -> None:
        """Test that running flags with no args shows help text."""
        result = cli_runner.invoke(app, ["flags"])
        combined = result.stdout + (result.output or "")
        assert result.exit_code == 0 or result.exit_code == 2
        assert "flags" in combined.lower() or "usage" in combined.lower()
