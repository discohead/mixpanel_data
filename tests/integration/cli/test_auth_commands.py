"""Integration tests for auth CLI commands."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest
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
            # --format is a per-command option, so it goes after the command
            result = cli_runner.invoke(app, ["auth", "list", "--format", "json"])

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
            # --format is a per-command option, so it goes after the command
            result = cli_runner.invoke(app, ["auth", "list", "--format", "table"])

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

    def test_show_account_no_default(self, cli_runner: CliRunner) -> None:
        """Test error when no default account is configured."""
        mock_config = MagicMock()
        # Return accounts but none is default
        mock_config.list_accounts.return_value = []

        with patch(
            "mixpanel_data.cli.commands.auth.get_config",
            return_value=mock_config,
        ):
            result = cli_runner.invoke(app, ["auth", "show"])

        assert result.exit_code == 1
        assert "No default account" in result.stderr


class TestAuthAdd:
    """Tests for mp auth add command."""

    def test_add_account_with_env_var_secret(
        self,
        cli_runner: CliRunner,
        mock_config_manager: MagicMock,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test adding account with secret from MP_SECRET env var."""
        monkeypatch.setenv("MP_SECRET", "test_secret")

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

    def test_add_account_with_secret_stdin(
        self,
        cli_runner: CliRunner,
        mock_config_manager: MagicMock,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test adding account with secret from stdin."""
        # Clear MP_SECRET to avoid env var taking precedence
        monkeypatch.delenv("MP_SECRET", raising=False)

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
                    "--project",
                    "12345",
                    "--region",
                    "us",
                    "--secret-stdin",
                ],
                input="stdin_secret\n",
            )

        assert result.exit_code == 0
        mock_config_manager.add_account.assert_called_once_with(
            name="test_account",
            username="test@example.com",
            secret="stdin_secret",
            project_id="12345",
            region="us",
        )

    def test_add_account_missing_username(
        self,
        cli_runner: CliRunner,
        mock_config_manager: MagicMock,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test error when username is missing."""
        # Provide secret via env var so we can test username validation
        monkeypatch.setenv("MP_SECRET", "test_secret")

        with patch(
            "mixpanel_data.cli.commands.auth.get_config",
            return_value=mock_config_manager,
        ):
            result = cli_runner.invoke(
                app,
                ["auth", "add", "test_account", "--project", "12345"],
            )

        # Should fail due to missing username
        assert result.exit_code == 3
        assert "username" in result.stderr.lower() or "Error" in result.stderr

    def test_add_account_secret_stdin_without_pipe_fails(
        self,
        cli_runner: CliRunner,
        mock_config_manager: MagicMock,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test that --secret-stdin fails when stdin is a tty."""
        monkeypatch.delenv("MP_SECRET", raising=False)

        with patch(
            "mixpanel_data.cli.commands.auth.get_config",
            return_value=mock_config_manager,
        ):
            # CliRunner simulates a TTY by default, so --secret-stdin should fail
            result = cli_runner.invoke(
                app,
                [
                    "auth",
                    "add",
                    "test_account",
                    "--username",
                    "test@example.com",
                    "--project",
                    "12345",
                    "--secret-stdin",
                ],
            )

        assert result.exit_code == 3
        assert (
            "requires piped input" in result.stderr or "stdin" in result.stderr.lower()
        )

    def test_add_account_missing_project(
        self,
        cli_runner: CliRunner,
        mock_config_manager: MagicMock,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test error when --project is missing."""
        monkeypatch.setenv("MP_SECRET", "test_secret")

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
                    # No --project
                ],
            )

        assert result.exit_code == 3
        assert "--project is required" in result.stderr

    def test_add_account_invalid_region(
        self,
        cli_runner: CliRunner,
        mock_config_manager: MagicMock,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test error when region is invalid."""
        monkeypatch.setenv("MP_SECRET", "test_secret")

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
                    "--project",
                    "12345",
                    "--region",
                    "invalid",
                ],
            )

        assert result.exit_code == 3
        assert "Invalid region" in result.stderr
        assert "invalid" in result.stderr

    def test_add_account_with_default_flag(
        self,
        cli_runner: CliRunner,
        mock_config_manager: MagicMock,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test adding account with --default flag."""
        monkeypatch.setenv("MP_SECRET", "test_secret")

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
                    "--project",
                    "12345",
                    "--region",
                    "us",
                    "--default",
                ],
            )

        assert result.exit_code == 0
        mock_config_manager.add_account.assert_called_once()
        mock_config_manager.set_default.assert_called_once_with("test_account")
        data = json.loads(result.stdout)
        assert data["is_default"] is True


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

    def test_remove_account_confirmation_decline(
        self, cli_runner: CliRunner, mock_config_manager: MagicMock
    ) -> None:
        """Test that declining confirmation cancels removal."""
        with patch(
            "mixpanel_data.cli.commands.auth.get_config",
            return_value=mock_config_manager,
        ):
            result = cli_runner.invoke(
                app,
                ["auth", "remove", "production"],
                input="n\n",  # Decline confirmation
            )

        assert result.exit_code == 2  # Cancelled
        assert "Cancelled" in result.stderr or "cancelled" in result.stderr.lower()
        mock_config_manager.remove_account.assert_not_called()


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


class TestAuthTest:
    """Tests for mp auth test command."""

    def test_test_account_success(
        self, cli_runner: CliRunner, mock_config_manager: MagicMock
    ) -> None:
        """Test successful credential test."""
        mock_result = {
            "success": True,
            "account": "production",
            "project_id": "12345",
            "region": "us",
            "events_found": 42,
        }

        with (
            patch(
                "mixpanel_data.cli.commands.auth.get_config",
                return_value=mock_config_manager,
            ),
            patch(
                "mixpanel_data.workspace.Workspace.test_credentials",
                return_value=mock_result,
            ) as mock_test_creds,
        ):
            result = cli_runner.invoke(app, ["auth", "test", "production"])

        assert result.exit_code == 0
        mock_test_creds.assert_called_once_with("production")
        data = json.loads(result.stdout)
        assert data["success"] is True
        assert data["account"] == "production"
        assert data["events_found"] == 42

    def test_test_default_account(
        self, cli_runner: CliRunner, mock_config_manager: MagicMock
    ) -> None:
        """Test testing default account when no name specified."""
        mock_result = {
            "success": True,
            "account": "production",
            "project_id": "12345",
            "region": "us",
            "events_found": 10,
        }

        with (
            patch(
                "mixpanel_data.cli.commands.auth.get_config",
                return_value=mock_config_manager,
            ),
            patch(
                "mixpanel_data.workspace.Workspace.test_credentials",
                return_value=mock_result,
            ) as mock_test_creds,
        ):
            result = cli_runner.invoke(app, ["auth", "test"])

        assert result.exit_code == 0
        mock_test_creds.assert_called_once_with(None)
        data = json.loads(result.stdout)
        assert data["success"] is True
