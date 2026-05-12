# ruff: noqa: ARG001
"""Integration tests for dashboard CLI commands."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from mixpanel_headless.cli.main import app


class TestDashboardsList:
    """Tests for mp dashboards list command."""

    def test_list_json(self, cli_runner: CliRunner, mock_workspace: MagicMock) -> None:
        """Test dashboards list in JSON format."""
        with patch(
            "mixpanel_headless.cli.commands.dashboards.get_workspace",
            return_value=mock_workspace,
        ):
            result = cli_runner.invoke(app, ["dashboards", "list", "--format", "json"])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert isinstance(data, list)
        assert data[0]["id"] == 1
        assert data[0]["title"] == "Test Dashboard"

    def test_list_with_ids(
        self, cli_runner: CliRunner, mock_workspace: MagicMock
    ) -> None:
        """Test dashboards list filtered by IDs."""
        with patch(
            "mixpanel_headless.cli.commands.dashboards.get_workspace",
            return_value=mock_workspace,
        ):
            result = cli_runner.invoke(app, ["dashboards", "list", "--ids", "1,2"])
        assert result.exit_code == 0
        mock_workspace.list_dashboards.assert_called_once_with(ids=[1, 2])

    def test_list_table_format(
        self, cli_runner: CliRunner, mock_workspace: MagicMock
    ) -> None:
        """Test dashboards list in table format."""
        with patch(
            "mixpanel_headless.cli.commands.dashboards.get_workspace",
            return_value=mock_workspace,
        ):
            result = cli_runner.invoke(app, ["dashboards", "list", "--format", "table"])
        assert result.exit_code == 0
        assert len(result.stdout.strip()) > 0

    def test_list_csv_format(
        self, cli_runner: CliRunner, mock_workspace: MagicMock
    ) -> None:
        """Test dashboards list in CSV format."""
        with patch(
            "mixpanel_headless.cli.commands.dashboards.get_workspace",
            return_value=mock_workspace,
        ):
            result = cli_runner.invoke(app, ["dashboards", "list", "--format", "csv"])
        assert result.exit_code == 0

    def test_list_empty(self, cli_runner: CliRunner, mock_workspace: MagicMock) -> None:
        """Test dashboards list with no results."""
        mock_workspace.list_dashboards.return_value = []
        with patch(
            "mixpanel_headless.cli.commands.dashboards.get_workspace",
            return_value=mock_workspace,
        ):
            result = cli_runner.invoke(app, ["dashboards", "list", "--format", "json"])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data == []


class TestDashboardsCreate:
    """Tests for mp dashboards create command."""

    def test_create_minimal(
        self, cli_runner: CliRunner, mock_workspace: MagicMock
    ) -> None:
        """Test creating a dashboard with only a title."""
        with patch(
            "mixpanel_headless.cli.commands.dashboards.get_workspace",
            return_value=mock_workspace,
        ):
            result = cli_runner.invoke(app, ["dashboards", "create", "--title", "New"])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert "id" in data

    def test_create_all_options(
        self, cli_runner: CliRunner, mock_workspace: MagicMock
    ) -> None:
        """Test creating a dashboard with all options."""
        with patch(
            "mixpanel_headless.cli.commands.dashboards.get_workspace",
            return_value=mock_workspace,
        ):
            result = cli_runner.invoke(
                app,
                [
                    "dashboards",
                    "create",
                    "--title",
                    "X",
                    "--description",
                    "Y",
                    "--duplicate",
                    "42",
                ],
            )
        assert result.exit_code == 0

    def test_create_private_flag(
        self, cli_runner: CliRunner, mock_workspace: MagicMock
    ) -> None:
        """Test creating a private dashboard sets is_private=True."""
        with patch(
            "mixpanel_headless.cli.commands.dashboards.get_workspace",
            return_value=mock_workspace,
        ):
            result = cli_runner.invoke(
                app, ["dashboards", "create", "--title", "Secret", "--private"]
            )
        assert result.exit_code == 0
        mock_workspace.create_dashboard.assert_called_once()
        params = mock_workspace.create_dashboard.call_args[0][0]
        assert params.is_private is True

    def test_create_no_private_flag(
        self, cli_runner: CliRunner, mock_workspace: MagicMock
    ) -> None:
        """Test creating a non-private dashboard explicitly with --no-private."""
        with patch(
            "mixpanel_headless.cli.commands.dashboards.get_workspace",
            return_value=mock_workspace,
        ):
            result = cli_runner.invoke(
                app,
                ["dashboards", "create", "--title", "Public", "--no-private"],
            )
        assert result.exit_code == 0
        mock_workspace.create_dashboard.assert_called_once()
        params = mock_workspace.create_dashboard.call_args[0][0]
        assert params.is_private is False

    def test_create_with_duplicate(
        self, cli_runner: CliRunner, mock_workspace: MagicMock
    ) -> None:
        """Test creating a dashboard by duplicating an existing one."""
        with patch(
            "mixpanel_headless.cli.commands.dashboards.get_workspace",
            return_value=mock_workspace,
        ):
            result = cli_runner.invoke(
                app,
                ["dashboards", "create", "--title", "Clone", "--duplicate", "42"],
            )
        assert result.exit_code == 0
        params = mock_workspace.create_dashboard.call_args[0][0]
        assert params.duplicate == 42


class TestDashboardsGetUpdateDelete:
    """Tests for mp dashboards get, update, and delete commands."""

    def test_get(self, cli_runner: CliRunner, mock_workspace: MagicMock) -> None:
        """Test getting a single dashboard by ID."""
        with patch(
            "mixpanel_headless.cli.commands.dashboards.get_workspace",
            return_value=mock_workspace,
        ):
            result = cli_runner.invoke(app, ["dashboards", "get", "1"])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["id"] == 1

    def test_update_title(
        self, cli_runner: CliRunner, mock_workspace: MagicMock
    ) -> None:
        """Test updating a dashboard title."""
        with patch(
            "mixpanel_headless.cli.commands.dashboards.get_workspace",
            return_value=mock_workspace,
        ):
            result = cli_runner.invoke(
                app, ["dashboards", "update", "1", "--title", "New"]
            )
        assert result.exit_code == 0

    def test_update_no_private(
        self, cli_runner: CliRunner, mock_workspace: MagicMock
    ) -> None:
        """Test updating a dashboard with --no-private sets is_private=False."""
        with patch(
            "mixpanel_headless.cli.commands.dashboards.get_workspace",
            return_value=mock_workspace,
        ):
            result = cli_runner.invoke(
                app, ["dashboards", "update", "1", "--no-private"]
            )
        assert result.exit_code == 0
        params = mock_workspace.update_dashboard.call_args[0][1]
        assert params.is_private is False

    def test_delete(self, cli_runner: CliRunner, mock_workspace: MagicMock) -> None:
        """Test deleting a dashboard."""
        with patch(
            "mixpanel_headless.cli.commands.dashboards.get_workspace",
            return_value=mock_workspace,
        ):
            result = cli_runner.invoke(app, ["dashboards", "delete", "1"])
        assert result.exit_code == 0


class TestDashboardsBulkDelete:
    """Tests for mp dashboards bulk-delete command."""

    def test_bulk_delete(
        self, cli_runner: CliRunner, mock_workspace: MagicMock
    ) -> None:
        """Test bulk deleting multiple dashboards."""
        with patch(
            "mixpanel_headless.cli.commands.dashboards.get_workspace",
            return_value=mock_workspace,
        ):
            result = cli_runner.invoke(
                app, ["dashboards", "bulk-delete", "--ids", "1,2,3"]
            )
        assert result.exit_code == 0
        mock_workspace.bulk_delete_dashboards.assert_called_once_with([1, 2, 3])

    def test_bulk_delete_single(
        self, cli_runner: CliRunner, mock_workspace: MagicMock
    ) -> None:
        """Test bulk deleting a single dashboard."""
        with patch(
            "mixpanel_headless.cli.commands.dashboards.get_workspace",
            return_value=mock_workspace,
        ):
            result = cli_runner.invoke(
                app, ["dashboards", "bulk-delete", "--ids", "42"]
            )
        assert result.exit_code == 0
        mock_workspace.bulk_delete_dashboards.assert_called_once_with([42])


class TestDashboardsOrganization:
    """Tests for mp dashboards favorite, unfavorite, pin, unpin, remove-report."""

    def test_favorite(self, cli_runner: CliRunner, mock_workspace: MagicMock) -> None:
        """Test favoriting a dashboard."""
        with patch(
            "mixpanel_headless.cli.commands.dashboards.get_workspace",
            return_value=mock_workspace,
        ):
            result = cli_runner.invoke(app, ["dashboards", "favorite", "1"])
        assert result.exit_code == 0

    def test_unfavorite(self, cli_runner: CliRunner, mock_workspace: MagicMock) -> None:
        """Test unfavoriting a dashboard."""
        with patch(
            "mixpanel_headless.cli.commands.dashboards.get_workspace",
            return_value=mock_workspace,
        ):
            result = cli_runner.invoke(app, ["dashboards", "unfavorite", "1"])
        assert result.exit_code == 0

    def test_pin(self, cli_runner: CliRunner, mock_workspace: MagicMock) -> None:
        """Test pinning a dashboard."""
        with patch(
            "mixpanel_headless.cli.commands.dashboards.get_workspace",
            return_value=mock_workspace,
        ):
            result = cli_runner.invoke(app, ["dashboards", "pin", "1"])
        assert result.exit_code == 0

    def test_unpin(self, cli_runner: CliRunner, mock_workspace: MagicMock) -> None:
        """Test unpinning a dashboard."""
        with patch(
            "mixpanel_headless.cli.commands.dashboards.get_workspace",
            return_value=mock_workspace,
        ):
            result = cli_runner.invoke(app, ["dashboards", "unpin", "1"])
        assert result.exit_code == 0

    def test_remove_report(
        self, cli_runner: CliRunner, mock_workspace: MagicMock
    ) -> None:
        """Test removing a report from a dashboard."""
        with patch(
            "mixpanel_headless.cli.commands.dashboards.get_workspace",
            return_value=mock_workspace,
        ):
            result = cli_runner.invoke(app, ["dashboards", "remove-report", "1", "42"])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert isinstance(data, dict)

    def test_add_report(self, cli_runner: CliRunner, mock_workspace: MagicMock) -> None:
        """Test adding a report to a dashboard."""
        with patch(
            "mixpanel_headless.cli.commands.dashboards.get_workspace",
            return_value=mock_workspace,
        ):
            result = cli_runner.invoke(app, ["dashboards", "add-report", "1", "42"])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert isinstance(data, dict)


class TestDashboardsBlueprints:
    """Tests for mp dashboards blueprints and blueprint-create commands."""

    def test_blueprints_list(
        self, cli_runner: CliRunner, mock_workspace: MagicMock
    ) -> None:
        """Test listing blueprint templates."""
        with patch(
            "mixpanel_headless.cli.commands.dashboards.get_workspace",
            return_value=mock_workspace,
        ):
            result = cli_runner.invoke(app, ["dashboards", "blueprints"])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data[0]["title_key"] == "onboarding"

    def test_blueprints_include_reports(
        self, cli_runner: CliRunner, mock_workspace: MagicMock
    ) -> None:
        """Test listing blueprint templates with include-reports flag."""
        with patch(
            "mixpanel_headless.cli.commands.dashboards.get_workspace",
            return_value=mock_workspace,
        ):
            result = cli_runner.invoke(
                app, ["dashboards", "blueprints", "--include-reports"]
            )
        assert result.exit_code == 0
        mock_workspace.list_blueprint_templates.assert_called_once_with(
            include_reports=True
        )

    def test_blueprint_create(
        self, cli_runner: CliRunner, mock_workspace: MagicMock
    ) -> None:
        """Test creating a dashboard from a blueprint template."""
        with patch(
            "mixpanel_headless.cli.commands.dashboards.get_workspace",
            return_value=mock_workspace,
        ):
            result = cli_runner.invoke(
                app, ["dashboards", "blueprint-create", "onboarding"]
            )
        assert result.exit_code == 0


class TestDashboardsAdvanced:
    """Tests for mp dashboards rca, erf, update-report-link, update-text-card."""

    def test_rca(self, cli_runner: CliRunner, mock_workspace: MagicMock) -> None:
        """Test creating an RCA dashboard."""
        with patch(
            "mixpanel_headless.cli.commands.dashboards.get_workspace",
            return_value=mock_workspace,
        ):
            result = cli_runner.invoke(
                app,
                [
                    "dashboards",
                    "rca",
                    "--source-id",
                    "42",
                    "--source-data",
                    '{"type":"anomaly"}',
                ],
            )
        assert result.exit_code == 0

    def test_rca_invalid_json(
        self, cli_runner: CliRunner, mock_workspace: MagicMock
    ) -> None:
        """Test RCA with invalid JSON source data fails."""
        with patch(
            "mixpanel_headless.cli.commands.dashboards.get_workspace",
            return_value=mock_workspace,
        ):
            result = cli_runner.invoke(
                app,
                [
                    "dashboards",
                    "rca",
                    "--source-id",
                    "42",
                    "--source-data",
                    "not json",
                ],
            )
        assert result.exit_code != 0

    def test_erf(self, cli_runner: CliRunner, mock_workspace: MagicMock) -> None:
        """Test getting ERF metrics for a dashboard."""
        with patch(
            "mixpanel_headless.cli.commands.dashboards.get_workspace",
            return_value=mock_workspace,
        ):
            result = cli_runner.invoke(app, ["dashboards", "erf", "1"])
        assert result.exit_code == 0

    def test_update_report_link(
        self, cli_runner: CliRunner, mock_workspace: MagicMock
    ) -> None:
        """Test updating a report link on a dashboard."""
        with patch(
            "mixpanel_headless.cli.commands.dashboards.get_workspace",
            return_value=mock_workspace,
        ):
            result = cli_runner.invoke(
                app,
                [
                    "dashboards",
                    "update-report-link",
                    "1",
                    "42",
                    "--type",
                    "embedded",
                ],
            )
        assert result.exit_code == 0

    def test_update_text_card(
        self, cli_runner: CliRunner, mock_workspace: MagicMock
    ) -> None:
        """Test updating a text card on a dashboard."""
        with patch(
            "mixpanel_headless.cli.commands.dashboards.get_workspace",
            return_value=mock_workspace,
        ):
            result = cli_runner.invoke(
                app,
                [
                    "dashboards",
                    "update-text-card",
                    "1",
                    "99",
                    "--markdown",
                    "# Hi",
                ],
            )
        assert result.exit_code == 0


class TestDashboardsInputValidation:
    """Tests for input validation on dashboard commands."""

    def test_invalid_id_in_ids(
        self, cli_runner: CliRunner, mock_workspace: MagicMock
    ) -> None:
        """Test that non-numeric IDs in --ids cause failure."""
        with patch(
            "mixpanel_headless.cli.commands.dashboards.get_workspace",
            return_value=mock_workspace,
        ):
            result = cli_runner.invoke(app, ["dashboards", "list", "--ids", "1,abc"])
        assert result.exit_code != 0

    def test_empty_string_ids(
        self, cli_runner: CliRunner, mock_workspace: MagicMock
    ) -> None:
        """Test that empty string --ids cause failure."""
        with patch(
            "mixpanel_headless.cli.commands.dashboards.get_workspace",
            return_value=mock_workspace,
        ):
            result = cli_runner.invoke(app, ["dashboards", "bulk-delete", "--ids", ""])
        assert result.exit_code != 0

    def test_no_args_shows_help(
        self,
        cli_runner: CliRunner,
        mock_workspace: MagicMock,  # noqa: ARG002
    ) -> None:
        """Test that running dashboards with no args shows help text."""
        result = cli_runner.invoke(app, ["dashboards"])
        combined = result.stdout + (result.output or "")
        assert result.exit_code == 0 or result.exit_code == 2
        assert "dashboards" in combined.lower() or "usage" in combined.lower()
