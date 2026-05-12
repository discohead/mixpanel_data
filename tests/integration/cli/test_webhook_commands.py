# ruff: noqa: ARG001
"""Integration tests for webhook CLI commands."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from mixpanel_headless.cli.main import app


class TestWebhooksList:
    """Tests for mp webhooks list command."""

    def test_list_json(self, cli_runner: CliRunner, mock_workspace: MagicMock) -> None:
        """Test webhooks list in JSON format."""
        with patch(
            "mixpanel_headless.cli.commands.webhooks.get_workspace",
            return_value=mock_workspace,
        ):
            result = cli_runner.invoke(app, ["webhooks", "list", "--format", "json"])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert isinstance(data, list)
        assert data[0]["id"] == "wh-uuid-123"
        assert data[0]["name"] == "Test Webhook"

    def test_list_table_format(
        self, cli_runner: CliRunner, mock_workspace: MagicMock
    ) -> None:
        """Test webhooks list in table format."""
        with patch(
            "mixpanel_headless.cli.commands.webhooks.get_workspace",
            return_value=mock_workspace,
        ):
            result = cli_runner.invoke(app, ["webhooks", "list", "--format", "table"])
        assert result.exit_code == 0
        assert len(result.stdout.strip()) > 0

    def test_list_empty(self, cli_runner: CliRunner, mock_workspace: MagicMock) -> None:
        """Test webhooks list with no results."""
        mock_workspace.list_webhooks.return_value = []
        with patch(
            "mixpanel_headless.cli.commands.webhooks.get_workspace",
            return_value=mock_workspace,
        ):
            result = cli_runner.invoke(app, ["webhooks", "list", "--format", "json"])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data == []


class TestWebhooksCreate:
    """Tests for mp webhooks create command."""

    def test_create_minimal(
        self, cli_runner: CliRunner, mock_workspace: MagicMock
    ) -> None:
        """Test creating a webhook with only required options."""
        with patch(
            "mixpanel_headless.cli.commands.webhooks.get_workspace",
            return_value=mock_workspace,
        ):
            result = cli_runner.invoke(
                app,
                [
                    "webhooks",
                    "create",
                    "--name",
                    "New Hook",
                    "--url",
                    "https://example.com/hook",
                ],
            )
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert "id" in data

    def test_create_all_options(
        self, cli_runner: CliRunner, mock_workspace: MagicMock
    ) -> None:
        """Test creating a webhook with all options."""
        with patch(
            "mixpanel_headless.cli.commands.webhooks.get_workspace",
            return_value=mock_workspace,
        ):
            result = cli_runner.invoke(
                app,
                [
                    "webhooks",
                    "create",
                    "--name",
                    "Secured Hook",
                    "--url",
                    "https://example.com/hook",
                    "--auth-type",
                    "basic",
                    "--username",
                    "user",
                    "--password",
                    "pass",
                ],
            )
        assert result.exit_code == 0
        params = mock_workspace.create_webhook.call_args[0][0]
        assert params.name == "Secured Hook"
        assert params.auth_type == "basic"
        assert params.username == "user"


class TestWebhooksUpdate:
    """Tests for mp webhooks update command."""

    def test_update_name(
        self, cli_runner: CliRunner, mock_workspace: MagicMock
    ) -> None:
        """Test updating a webhook name."""
        with patch(
            "mixpanel_headless.cli.commands.webhooks.get_workspace",
            return_value=mock_workspace,
        ):
            result = cli_runner.invoke(
                app,
                ["webhooks", "update", "wh-uuid-123", "--name", "Renamed"],
            )
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["id"] == "wh-uuid-123"

    def test_update_enabled(
        self, cli_runner: CliRunner, mock_workspace: MagicMock
    ) -> None:
        """Test enabling/disabling a webhook."""
        with patch(
            "mixpanel_headless.cli.commands.webhooks.get_workspace",
            return_value=mock_workspace,
        ):
            result = cli_runner.invoke(
                app,
                ["webhooks", "update", "wh-uuid-123", "--no-enabled"],
            )
        assert result.exit_code == 0
        params = mock_workspace.update_webhook.call_args[0][1]
        assert params.is_enabled is False


class TestWebhooksDelete:
    """Tests for mp webhooks delete command."""

    def test_delete(self, cli_runner: CliRunner, mock_workspace: MagicMock) -> None:
        """Test deleting a webhook."""
        with patch(
            "mixpanel_headless.cli.commands.webhooks.get_workspace",
            return_value=mock_workspace,
        ):
            result = cli_runner.invoke(app, ["webhooks", "delete", "wh-uuid-123"])
        assert result.exit_code == 0
        mock_workspace.delete_webhook.assert_called_once_with("wh-uuid-123")


class TestWebhooksTest:
    """Tests for mp webhooks test command."""

    def test_basic(self, cli_runner: CliRunner, mock_workspace: MagicMock) -> None:
        """Test basic webhook connectivity test."""
        with patch(
            "mixpanel_headless.cli.commands.webhooks.get_workspace",
            return_value=mock_workspace,
        ):
            result = cli_runner.invoke(
                app,
                ["webhooks", "test", "--url", "https://example.com/hook"],
            )
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["success"] is True
        assert data["status_code"] == 200

    def test_with_auth(self, cli_runner: CliRunner, mock_workspace: MagicMock) -> None:
        """Test webhook connectivity test with auth options."""
        with patch(
            "mixpanel_headless.cli.commands.webhooks.get_workspace",
            return_value=mock_workspace,
        ):
            result = cli_runner.invoke(
                app,
                [
                    "webhooks",
                    "test",
                    "--url",
                    "https://example.com/hook",
                    "--auth-type",
                    "basic",
                    "--username",
                    "user",
                    "--password",
                    "pass",
                ],
            )
        assert result.exit_code == 0
        params = mock_workspace.test_webhook.call_args[0][0]
        assert params.auth_type == "basic"


class TestWebhooksInputValidation:
    """Tests for input validation on webhook commands."""

    def test_no_args_shows_help(
        self,
        cli_runner: CliRunner,
        mock_workspace: MagicMock,  # noqa: ARG002
    ) -> None:
        """Test that running webhooks with no args shows help text."""
        result = cli_runner.invoke(app, ["webhooks"])
        combined = result.stdout + (result.output or "")
        assert result.exit_code == 0 or result.exit_code == 2
        assert "webhooks" in combined.lower() or "usage" in combined.lower()
