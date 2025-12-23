"""Integration tests for auth CLI commands."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from mixpanel_data.cli.main import app


class TestAuthList:
    """Tests for mp auth list command."""

    def test_list_accounts_json_format(
        self, cli_runner: CliRunner, mock_config_manager: MagicMock
    ) -> None:
        """Test listing accounts in JSON format."""
        with patch(
            "mixpanel_data.cli.commands.auth.get_config",
            return_value=mock_config_manager,
        ):
            # --format is a global option, so it goes before the subcommand
            result = cli_runner.invoke(app, ["--format", "json", "auth", "list"])

        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert isinstance(data, list)
        assert len(data) == 2
        assert data[0]["name"] == "production"
        assert data[0]["is_default"] is True

    def test_list_accounts_table_format(
        self, cli_runner: CliRunner, mock_config_manager: MagicMock
    ) -> None:
        """Test listing accounts in table format."""
        with patch(
            "mixpanel_data.cli.commands.auth.get_config",
            return_value=mock_config_manager,
        ):
            # --format is a global option, so it goes before the subcommand
            result = cli_runner.invoke(app, ["--format", "table", "auth", "list"])

        assert result.exit_code == 0
        assert "production" in result.stdout
        assert "staging" in result.stdout


class TestAuthShow:
    """Tests for mp auth show command."""

    def test_show_account(
        self, cli_runner: CliRunner, mock_config_manager: MagicMock
    ) -> None:
        """Test showing account details."""
        with patch(
            "mixpanel_data.cli.commands.auth.get_config",
            return_value=mock_config_manager,
        ):
            result = cli_runner.invoke(app, ["auth", "show", "production"])

        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["name"] == "production"
        assert data["secret"] == "********"  # Secret should be redacted

    def test_show_default_account(
        self, cli_runner: CliRunner, mock_config_manager: MagicMock
    ) -> None:
        """Test showing default account when no name specified."""
        with patch(
            "mixpanel_data.cli.commands.auth.get_config",
            return_value=mock_config_manager,
        ):
            result = cli_runner.invoke(app, ["auth", "show"])

        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["name"] == "production"


class TestAuthAdd:
    """Tests for mp auth add command."""

    def test_add_account_with_options(
        self, cli_runner: CliRunner, mock_config_manager: MagicMock
    ) -> None:
        """Test adding account with all options."""
        with patch(
            "mixpanel_data.cli.commands.auth.get_config",
            return_value=mock_config_manager,
        ):
            result = cli_runner.invoke(
                app,
                [
                    "auth",
                    "add",
                    "test_account",
                    "--username",
                    "test@example.com",
                    "--secret",
                    "test_secret",
                    "--project",
                    "12345",
                    "--region",
                    "us",
                ],
            )

        assert result.exit_code == 0
        mock_config_manager.add_account.assert_called_once_with(
            name="test_account",
            username="test@example.com",
            secret="test_secret",
            project_id="12345",
            region="us",
        )

    def test_add_account_missing_required(
        self, cli_runner: CliRunner, mock_config_manager: MagicMock
    ) -> None:
        """Test error when required options are missing."""
        with patch(
            "mixpanel_data.cli.commands.auth.get_config",
            return_value=mock_config_manager,
        ):
            result = cli_runner.invoke(app, ["auth", "add", "test_account"])

        assert result.exit_code == 3
        assert "username" in result.stderr.lower() or "Error" in result.stderr


class TestAuthRemove:
    """Tests for mp auth remove command."""

    def test_remove_account_with_force(
        self, cli_runner: CliRunner, mock_config_manager: MagicMock
    ) -> None:
        """Test removing account with --force flag."""
        with patch(
            "mixpanel_data.cli.commands.auth.get_config",
            return_value=mock_config_manager,
        ):
            result = cli_runner.invoke(app, ["auth", "remove", "production", "--force"])

        assert result.exit_code == 0
        mock_config_manager.remove_account.assert_called_once_with("production")


class TestAuthSwitch:
    """Tests for mp auth switch command."""

    def test_switch_default_account(
        self, cli_runner: CliRunner, mock_config_manager: MagicMock
    ) -> None:
        """Test switching default account."""
        with patch(
            "mixpanel_data.cli.commands.auth.get_config",
            return_value=mock_config_manager,
        ):
            result = cli_runner.invoke(app, ["auth", "switch", "staging"])

        assert result.exit_code == 0
        mock_config_manager.set_default.assert_called_once_with("staging")
        data = json.loads(result.stdout)
        assert data["default"] == "staging"
