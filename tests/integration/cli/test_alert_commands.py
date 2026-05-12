# ruff: noqa: ARG001
"""Integration tests for alert CLI commands."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from mixpanel_headless.cli.main import app


class TestAlertsList:
    """Tests for mp alerts list command."""

    def test_list_json(self, cli_runner: CliRunner, mock_workspace: MagicMock) -> None:
        """Test alerts list in JSON format."""
        with patch(
            "mixpanel_headless.cli.commands.alerts.get_workspace",
            return_value=mock_workspace,
        ):
            result = cli_runner.invoke(app, ["alerts", "list", "--format", "json"])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert isinstance(data, list)
        assert data[0]["id"] == 1
        assert data[0]["name"] == "Test Alert"

    def test_list_empty(self, cli_runner: CliRunner, mock_workspace: MagicMock) -> None:
        """Test alerts list with no results."""
        mock_workspace.list_alerts.return_value = []
        with patch(
            "mixpanel_headless.cli.commands.alerts.get_workspace",
            return_value=mock_workspace,
        ):
            result = cli_runner.invoke(app, ["alerts", "list", "--format", "json"])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data == []

    def test_list_with_bookmark_filter(
        self, cli_runner: CliRunner, mock_workspace: MagicMock
    ) -> None:
        """Test alerts list with --bookmark-id filter."""
        with patch(
            "mixpanel_headless.cli.commands.alerts.get_workspace",
            return_value=mock_workspace,
        ):
            result = cli_runner.invoke(app, ["alerts", "list", "--bookmark-id", "42"])
        assert result.exit_code == 0
        mock_workspace.list_alerts.assert_called_once_with(bookmark_id=42)

    def test_list_with_skip_user_filter(
        self, cli_runner: CliRunner, mock_workspace: MagicMock
    ) -> None:
        """Test alerts list with --skip-user-filter flag."""
        with patch(
            "mixpanel_headless.cli.commands.alerts.get_workspace",
            return_value=mock_workspace,
        ):
            result = cli_runner.invoke(app, ["alerts", "list", "--skip-user-filter"])
        assert result.exit_code == 0
        mock_workspace.list_alerts.assert_called_once_with(skip_user_filter=True)


class TestAlertsCreate:
    """Tests for mp alerts create command."""

    def test_create_minimal(
        self, cli_runner: CliRunner, mock_workspace: MagicMock
    ) -> None:
        """Test creating an alert with required options."""
        with patch(
            "mixpanel_headless.cli.commands.alerts.get_workspace",
            return_value=mock_workspace,
        ):
            result = cli_runner.invoke(
                app,
                [
                    "alerts",
                    "create",
                    "--bookmark-id",
                    "123",
                    "--name",
                    "Test Alert",
                    "--condition",
                    '{"operator": "less_than", "value": 100}',
                    "--frequency",
                    "86400",
                ],
            )
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert "id" in data

    def test_create_invalid_condition_json(
        self, cli_runner: CliRunner, mock_workspace: MagicMock
    ) -> None:
        """Test creating an alert with invalid condition JSON fails."""
        with patch(
            "mixpanel_headless.cli.commands.alerts.get_workspace",
            return_value=mock_workspace,
        ):
            result = cli_runner.invoke(
                app,
                [
                    "alerts",
                    "create",
                    "--bookmark-id",
                    "123",
                    "--name",
                    "Bad",
                    "--condition",
                    "not json",
                    "--frequency",
                    "86400",
                ],
            )
        assert result.exit_code != 0


class TestAlertsGet:
    """Tests for mp alerts get command."""

    def test_get(self, cli_runner: CliRunner, mock_workspace: MagicMock) -> None:
        """Test getting a single alert by ID."""
        with patch(
            "mixpanel_headless.cli.commands.alerts.get_workspace",
            return_value=mock_workspace,
        ):
            result = cli_runner.invoke(app, ["alerts", "get", "1"])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["id"] == 1
        assert data["name"] == "Test Alert"


class TestAlertsUpdate:
    """Tests for mp alerts update command."""

    def test_update_name(
        self, cli_runner: CliRunner, mock_workspace: MagicMock
    ) -> None:
        """Test updating an alert name."""
        with patch(
            "mixpanel_headless.cli.commands.alerts.get_workspace",
            return_value=mock_workspace,
        ):
            result = cli_runner.invoke(
                app,
                ["alerts", "update", "1", "--name", "Renamed"],
            )
        assert result.exit_code == 0
        params = mock_workspace.update_alert.call_args[0][1]
        assert params.name == "Renamed"

    def test_update_invalid_condition_json(
        self, cli_runner: CliRunner, mock_workspace: MagicMock
    ) -> None:
        """Test updating with invalid condition JSON fails."""
        with patch(
            "mixpanel_headless.cli.commands.alerts.get_workspace",
            return_value=mock_workspace,
        ):
            result = cli_runner.invoke(
                app,
                ["alerts", "update", "1", "--condition", "not json"],
            )
        assert result.exit_code != 0


class TestAlertsDelete:
    """Tests for mp alerts delete command."""

    def test_delete(self, cli_runner: CliRunner, mock_workspace: MagicMock) -> None:
        """Test deleting an alert."""
        with patch(
            "mixpanel_headless.cli.commands.alerts.get_workspace",
            return_value=mock_workspace,
        ):
            result = cli_runner.invoke(app, ["alerts", "delete", "1"])
        assert result.exit_code == 0
        mock_workspace.delete_alert.assert_called_once_with(1)


class TestAlertsBulkDelete:
    """Tests for mp alerts bulk-delete command."""

    def test_bulk_delete(
        self, cli_runner: CliRunner, mock_workspace: MagicMock
    ) -> None:
        """Test bulk-deleting alerts."""
        with patch(
            "mixpanel_headless.cli.commands.alerts.get_workspace",
            return_value=mock_workspace,
        ):
            result = cli_runner.invoke(app, ["alerts", "bulk-delete", "--ids", "1,2,3"])
        assert result.exit_code == 0
        mock_workspace.bulk_delete_alerts.assert_called_once_with([1, 2, 3])

    def test_bulk_delete_invalid_ids(
        self, cli_runner: CliRunner, mock_workspace: MagicMock
    ) -> None:
        """Test bulk-delete with invalid IDs fails."""
        with patch(
            "mixpanel_headless.cli.commands.alerts.get_workspace",
            return_value=mock_workspace,
        ):
            result = cli_runner.invoke(
                app, ["alerts", "bulk-delete", "--ids", "1,abc,3"]
            )
        assert result.exit_code != 0

    def test_bulk_delete_empty_ids(
        self, cli_runner: CliRunner, mock_workspace: MagicMock
    ) -> None:
        """Test bulk-delete with empty IDs fails."""
        with patch(
            "mixpanel_headless.cli.commands.alerts.get_workspace",
            return_value=mock_workspace,
        ):
            result = cli_runner.invoke(app, ["alerts", "bulk-delete", "--ids", ","])
        assert result.exit_code != 0


class TestAlertsCount:
    """Tests for mp alerts count command."""

    def test_count(self, cli_runner: CliRunner, mock_workspace: MagicMock) -> None:
        """Test getting alert count."""
        with patch(
            "mixpanel_headless.cli.commands.alerts.get_workspace",
            return_value=mock_workspace,
        ):
            result = cli_runner.invoke(app, ["alerts", "count"])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["anomaly_alerts_count"] == 5
        assert data["alert_limit"] == 100

    def test_count_with_type(
        self, cli_runner: CliRunner, mock_workspace: MagicMock
    ) -> None:
        """Test getting alert count with --type filter."""
        with patch(
            "mixpanel_headless.cli.commands.alerts.get_workspace",
            return_value=mock_workspace,
        ):
            result = cli_runner.invoke(app, ["alerts", "count", "--type", "anomaly"])
        assert result.exit_code == 0
        mock_workspace.get_alert_count.assert_called_once_with(alert_type="anomaly")


class TestAlertsHistory:
    """Tests for mp alerts history command."""

    def test_history(self, cli_runner: CliRunner, mock_workspace: MagicMock) -> None:
        """Test getting alert history."""
        with patch(
            "mixpanel_headless.cli.commands.alerts.get_workspace",
            return_value=mock_workspace,
        ):
            result = cli_runner.invoke(app, ["alerts", "history", "1"])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert "results" in data
        assert "pagination" in data

    def test_history_with_pagination(
        self, cli_runner: CliRunner, mock_workspace: MagicMock
    ) -> None:
        """Test getting alert history with pagination options."""
        with patch(
            "mixpanel_headless.cli.commands.alerts.get_workspace",
            return_value=mock_workspace,
        ):
            result = cli_runner.invoke(
                app,
                [
                    "alerts",
                    "history",
                    "1",
                    "--page-size",
                    "50",
                    "--cursor",
                    "abc123",
                ],
            )
        assert result.exit_code == 0
        mock_workspace.get_alert_history.assert_called_once_with(
            1, page_size=50, next_cursor="abc123"
        )


class TestAlertsTest:
    """Tests for mp alerts test command."""

    def test_test_alert(self, cli_runner: CliRunner, mock_workspace: MagicMock) -> None:
        """Test sending a test alert."""
        with patch(
            "mixpanel_headless.cli.commands.alerts.get_workspace",
            return_value=mock_workspace,
        ):
            result = cli_runner.invoke(
                app,
                [
                    "alerts",
                    "test",
                    "--bookmark-id",
                    "123",
                    "--name",
                    "Test",
                    "--condition",
                    '{"operator": "less_than", "value": 50}',
                    "--frequency",
                    "86400",
                ],
            )
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["status"] == "sent"


class TestAlertsScreenshot:
    """Tests for mp alerts screenshot command."""

    def test_screenshot(self, cli_runner: CliRunner, mock_workspace: MagicMock) -> None:
        """Test getting alert screenshot URL."""
        with patch(
            "mixpanel_headless.cli.commands.alerts.get_workspace",
            return_value=mock_workspace,
        ):
            result = cli_runner.invoke(
                app,
                ["alerts", "screenshot", "--gcs-key", "screenshots/abc.png"],
            )
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert "signed_url" in data


class TestAlertsValidate:
    """Tests for mp alerts validate command."""

    def test_validate(self, cli_runner: CliRunner, mock_workspace: MagicMock) -> None:
        """Test validating alerts for a bookmark."""
        with patch(
            "mixpanel_headless.cli.commands.alerts.get_workspace",
            return_value=mock_workspace,
        ):
            result = cli_runner.invoke(
                app,
                [
                    "alerts",
                    "validate",
                    "--alert-ids",
                    "1,2",
                    "--bookmark-type",
                    "insights",
                    "--bookmark-params",
                    '{"event": "Signup"}',
                ],
            )
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert "invalid_count" in data

    def test_validate_invalid_params_json(
        self, cli_runner: CliRunner, mock_workspace: MagicMock
    ) -> None:
        """Test validate with invalid bookmark-params JSON fails."""
        with patch(
            "mixpanel_headless.cli.commands.alerts.get_workspace",
            return_value=mock_workspace,
        ):
            result = cli_runner.invoke(
                app,
                [
                    "alerts",
                    "validate",
                    "--alert-ids",
                    "1",
                    "--bookmark-type",
                    "insights",
                    "--bookmark-params",
                    "not json",
                ],
            )
        assert result.exit_code != 0


class TestAlertsCreateEdgeCases:
    """Tests for alert create edge cases (JSON error paths)."""

    def test_create_invalid_subscriptions_json(
        self, cli_runner: CliRunner, mock_workspace: MagicMock
    ) -> None:
        """Test creating an alert with invalid subscriptions JSON fails."""
        with patch(
            "mixpanel_headless.cli.commands.alerts.get_workspace",
            return_value=mock_workspace,
        ):
            result = cli_runner.invoke(
                app,
                [
                    "alerts",
                    "create",
                    "--bookmark-id",
                    "123",
                    "--name",
                    "Bad",
                    "--condition",
                    '{"op": "lt"}',
                    "--frequency",
                    "3600",
                    "--subscriptions",
                    "not json",
                ],
            )
        assert result.exit_code != 0

    def test_create_invalid_notification_windows_json(
        self, cli_runner: CliRunner, mock_workspace: MagicMock
    ) -> None:
        """Test creating an alert with invalid notification-windows JSON fails."""
        with patch(
            "mixpanel_headless.cli.commands.alerts.get_workspace",
            return_value=mock_workspace,
        ):
            result = cli_runner.invoke(
                app,
                [
                    "alerts",
                    "create",
                    "--bookmark-id",
                    "123",
                    "--name",
                    "Bad",
                    "--condition",
                    '{"op": "lt"}',
                    "--frequency",
                    "3600",
                    "--notification-windows",
                    "not json",
                ],
            )
        assert result.exit_code != 0

    def test_create_with_subscriptions(
        self, cli_runner: CliRunner, mock_workspace: MagicMock
    ) -> None:
        """Test creating an alert with subscriptions JSON."""
        with patch(
            "mixpanel_headless.cli.commands.alerts.get_workspace",
            return_value=mock_workspace,
        ):
            result = cli_runner.invoke(
                app,
                [
                    "alerts",
                    "create",
                    "--bookmark-id",
                    "123",
                    "--name",
                    "Alert",
                    "--condition",
                    '{"op": "lt"}',
                    "--frequency",
                    "3600",
                    "--subscriptions",
                    '[{"type": "email", "value": "a@b.com"}]',
                ],
            )
        assert result.exit_code == 0

    def test_create_paused(
        self, cli_runner: CliRunner, mock_workspace: MagicMock
    ) -> None:
        """Test creating a paused alert."""
        with patch(
            "mixpanel_headless.cli.commands.alerts.get_workspace",
            return_value=mock_workspace,
        ):
            result = cli_runner.invoke(
                app,
                [
                    "alerts",
                    "create",
                    "--bookmark-id",
                    "123",
                    "--name",
                    "Paused",
                    "--condition",
                    '{"op": "lt"}',
                    "--frequency",
                    "3600",
                    "--paused",
                ],
            )
        assert result.exit_code == 0
        params = mock_workspace.create_alert.call_args[0][0]
        assert params.paused is True


class TestAlertsUpdateEdgeCases:
    """Tests for alert update edge cases."""

    def test_update_multiple_fields(
        self, cli_runner: CliRunner, mock_workspace: MagicMock
    ) -> None:
        """Test updating multiple fields at once."""
        with patch(
            "mixpanel_headless.cli.commands.alerts.get_workspace",
            return_value=mock_workspace,
        ):
            result = cli_runner.invoke(
                app,
                [
                    "alerts",
                    "update",
                    "1",
                    "--name",
                    "New",
                    "--frequency",
                    "7200",
                    "--paused",
                    "--condition",
                    '{"op": "gt"}',
                    "--subscriptions",
                    '[{"type": "slack"}]',
                    "--notification-windows",
                    '{"start": 9, "end": 17}',
                ],
            )
        assert result.exit_code == 0
        params = mock_workspace.update_alert.call_args[0][1]
        assert params.name == "New"
        assert params.frequency == 7200
        assert params.paused is True

    def test_update_invalid_subscriptions_json(
        self, cli_runner: CliRunner, mock_workspace: MagicMock
    ) -> None:
        """Test update with invalid subscriptions JSON fails."""
        with patch(
            "mixpanel_headless.cli.commands.alerts.get_workspace",
            return_value=mock_workspace,
        ):
            result = cli_runner.invoke(
                app,
                ["alerts", "update", "1", "--subscriptions", "not json"],
            )
        assert result.exit_code != 0

    def test_update_invalid_notification_windows_json(
        self, cli_runner: CliRunner, mock_workspace: MagicMock
    ) -> None:
        """Test update with invalid notification-windows JSON fails."""
        with patch(
            "mixpanel_headless.cli.commands.alerts.get_workspace",
            return_value=mock_workspace,
        ):
            result = cli_runner.invoke(
                app,
                ["alerts", "update", "1", "--notification-windows", "not json"],
            )
        assert result.exit_code != 0


class TestAlertsTestEdgeCases:
    """Tests for alert test edge cases."""

    def test_test_invalid_condition_json(
        self, cli_runner: CliRunner, mock_workspace: MagicMock
    ) -> None:
        """Test alert test with invalid condition JSON fails."""
        with patch(
            "mixpanel_headless.cli.commands.alerts.get_workspace",
            return_value=mock_workspace,
        ):
            result = cli_runner.invoke(
                app,
                [
                    "alerts",
                    "test",
                    "--bookmark-id",
                    "123",
                    "--name",
                    "Bad",
                    "--condition",
                    "not json",
                    "--frequency",
                    "3600",
                ],
            )
        assert result.exit_code != 0

    def test_test_with_subscriptions(
        self, cli_runner: CliRunner, mock_workspace: MagicMock
    ) -> None:
        """Test alert test with subscriptions."""
        with patch(
            "mixpanel_headless.cli.commands.alerts.get_workspace",
            return_value=mock_workspace,
        ):
            result = cli_runner.invoke(
                app,
                [
                    "alerts",
                    "test",
                    "--bookmark-id",
                    "123",
                    "--name",
                    "T",
                    "--condition",
                    '{"op": "lt"}',
                    "--frequency",
                    "3600",
                    "--subscriptions",
                    '[{"type": "email"}]',
                ],
            )
        assert result.exit_code == 0


class TestAlertsInputValidation:
    """Tests for input validation on alert commands."""

    def test_no_args_shows_help(
        self,
        cli_runner: CliRunner,
        mock_workspace: MagicMock,  # noqa: ARG002
    ) -> None:
        """Test that running alerts with no args shows help text."""
        result = cli_runner.invoke(app, ["alerts"])
        combined = result.stdout + (result.output or "")
        assert result.exit_code == 0 or result.exit_code == 2
        assert "alerts" in combined.lower() or "usage" in combined.lower()
