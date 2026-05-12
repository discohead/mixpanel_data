# ruff: noqa: ARG001
"""Integration tests for report (bookmark CRUD) CLI commands.

Phase 024: Core entity CRUD — Tests for reports list, create, get,
update, delete, bulk operations, linkage, and history.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from mixpanel_headless.cli.main import app

PATCH_TARGET = "mixpanel_headless.cli.commands.reports.get_workspace"


class TestReportsList:
    """Tests for mp reports list command."""

    def test_list_json(self, cli_runner: CliRunner, mock_workspace: MagicMock) -> None:
        """List reports returns JSON array with id and name."""
        with patch(PATCH_TARGET, return_value=mock_workspace):
            result = cli_runner.invoke(app, ["reports", "list"])

        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["id"] == 1
        assert data[0]["name"] == "Test Report"

    def test_list_by_type(
        self, cli_runner: CliRunner, mock_workspace: MagicMock
    ) -> None:
        """List reports filtered by bookmark type."""
        with patch(PATCH_TARGET, return_value=mock_workspace):
            result = cli_runner.invoke(app, ["reports", "list", "--type", "funnels"])

        assert result.exit_code == 0
        mock_workspace.list_bookmarks_v2.assert_called_once_with(
            bookmark_type="funnels", ids=None
        )

    def test_list_by_ids(
        self, cli_runner: CliRunner, mock_workspace: MagicMock
    ) -> None:
        """List reports filtered by specific IDs."""
        with patch(PATCH_TARGET, return_value=mock_workspace):
            result = cli_runner.invoke(app, ["reports", "list", "--ids", "1,2"])

        assert result.exit_code == 0
        mock_workspace.list_bookmarks_v2.assert_called_once_with(
            bookmark_type=None, ids=[1, 2]
        )


class TestReportsCreate:
    """Tests for mp reports create command."""

    def test_create(self, cli_runner: CliRunner, mock_workspace: MagicMock) -> None:
        """Create a report with name, type, and params."""
        with patch(PATCH_TARGET, return_value=mock_workspace):
            result = cli_runner.invoke(
                app,
                [
                    "reports",
                    "create",
                    "--name",
                    "Funnel",
                    "--type",
                    "funnels",
                    "--params",
                    '{"events":[]}',
                ],
            )

        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["id"] == 1
        mock_workspace.create_bookmark.assert_called_once()

    def test_create_invalid_json(
        self, cli_runner: CliRunner, mock_workspace: MagicMock
    ) -> None:
        """Create with malformed JSON params fails."""
        with patch(PATCH_TARGET, return_value=mock_workspace):
            result = cli_runner.invoke(
                app,
                [
                    "reports",
                    "create",
                    "--name",
                    "X",
                    "--type",
                    "insights",
                    "--params",
                    "{bad",
                ],
            )

        assert result.exit_code != 0


class TestReportsGetUpdateDelete:
    """Tests for mp reports get, update, and delete commands."""

    def test_get(self, cli_runner: CliRunner, mock_workspace: MagicMock) -> None:
        """Get a single report by ID."""
        with patch(PATCH_TARGET, return_value=mock_workspace):
            result = cli_runner.invoke(app, ["reports", "get", "1"])

        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["id"] == 1

    def test_update_name(
        self, cli_runner: CliRunner, mock_workspace: MagicMock
    ) -> None:
        """Update a report name."""
        with patch(PATCH_TARGET, return_value=mock_workspace):
            result = cli_runner.invoke(
                app, ["reports", "update", "1", "--name", "New Name"]
            )

        assert result.exit_code == 0
        mock_workspace.update_bookmark.assert_called_once()

    def test_update_with_params(
        self, cli_runner: CliRunner, mock_workspace: MagicMock
    ) -> None:
        """Update a report with new params JSON."""
        with patch(PATCH_TARGET, return_value=mock_workspace):
            result = cli_runner.invoke(
                app,
                ["reports", "update", "1", "--params", '{"new":true}'],
            )

        assert result.exit_code == 0
        mock_workspace.update_bookmark.assert_called_once()

    def test_delete(self, cli_runner: CliRunner, mock_workspace: MagicMock) -> None:
        """Delete a report by ID."""
        with patch(PATCH_TARGET, return_value=mock_workspace):
            result = cli_runner.invoke(app, ["reports", "delete", "1"])

        assert result.exit_code == 0
        mock_workspace.delete_bookmark.assert_called_once_with(1)


class TestReportsBulk:
    """Tests for mp reports bulk-delete and bulk-update commands."""

    def test_bulk_delete(
        self, cli_runner: CliRunner, mock_workspace: MagicMock
    ) -> None:
        """Bulk delete multiple reports by IDs."""
        with patch(PATCH_TARGET, return_value=mock_workspace):
            result = cli_runner.invoke(app, ["reports", "bulk-delete", "--ids", "1,2"])

        assert result.exit_code == 0
        mock_workspace.bulk_delete_bookmarks.assert_called_once_with([1, 2])

    def test_bulk_update(
        self, cli_runner: CliRunner, mock_workspace: MagicMock
    ) -> None:
        """Bulk update multiple reports."""
        with patch(PATCH_TARGET, return_value=mock_workspace):
            result = cli_runner.invoke(
                app,
                [
                    "reports",
                    "bulk-update",
                    "--entries",
                    '[{"id":1,"name":"Updated"}]',
                ],
            )

        assert result.exit_code == 0
        mock_workspace.bulk_update_bookmarks.assert_called_once()

    def test_bulk_update_invalid_json(
        self, cli_runner: CliRunner, mock_workspace: MagicMock
    ) -> None:
        """Bulk update with malformed JSON fails."""
        with patch(PATCH_TARGET, return_value=mock_workspace):
            result = cli_runner.invoke(
                app,
                ["reports", "bulk-update", "--entries", "not json"],
            )

        assert result.exit_code != 0


class TestReportsLinkageAndHistory:
    """Tests for linked-dashboards, dashboard-ids, and history commands."""

    def test_linked_dashboards(
        self, cli_runner: CliRunner, mock_workspace: MagicMock
    ) -> None:
        """Get dashboard IDs linked to a bookmark."""
        with patch(PATCH_TARGET, return_value=mock_workspace):
            result = cli_runner.invoke(app, ["reports", "linked-dashboards", "1"])

        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data == [10, 20]

    def test_dashboard_ids(
        self, cli_runner: CliRunner, mock_workspace: MagicMock
    ) -> None:
        """Get dashboard IDs containing a bookmark."""
        with patch(PATCH_TARGET, return_value=mock_workspace):
            result = cli_runner.invoke(app, ["reports", "dashboard-ids", "1"])

        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data == [1, 2]

    def test_history(self, cli_runner: CliRunner, mock_workspace: MagicMock) -> None:
        """Get bookmark change history."""
        with patch(PATCH_TARGET, return_value=mock_workspace):
            result = cli_runner.invoke(app, ["reports", "history", "1"])

        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert "results" in data
        assert "pagination" in data

    def test_history_with_pagination(
        self, cli_runner: CliRunner, mock_workspace: MagicMock
    ) -> None:
        """Get bookmark history with cursor and page size options."""
        with patch(PATCH_TARGET, return_value=mock_workspace):
            result = cli_runner.invoke(
                app,
                [
                    "reports",
                    "history",
                    "1",
                    "--cursor",
                    "abc",
                    "--page-size",
                    "10",
                ],
            )

        assert result.exit_code == 0
        mock_workspace.get_bookmark_history.assert_called_once_with(
            1, cursor="abc", page_size=10
        )


class TestReportsInputValidation:
    """Tests for input validation and edge cases."""

    def test_invalid_ids(
        self, cli_runner: CliRunner, mock_workspace: MagicMock
    ) -> None:
        """Non-numeric IDs in list filter cause failure."""
        with patch(PATCH_TARGET, return_value=mock_workspace):
            result = cli_runner.invoke(app, ["reports", "list", "--ids", "abc"])

        assert result.exit_code != 0

    def test_empty_ids_bulk_delete(
        self, cli_runner: CliRunner, mock_workspace: MagicMock
    ) -> None:
        """Empty IDs string for bulk delete causes failure."""
        with patch(PATCH_TARGET, return_value=mock_workspace):
            result = cli_runner.invoke(app, ["reports", "bulk-delete", "--ids", ""])

        assert result.exit_code != 0

    def test_no_args_shows_help(
        self,
        cli_runner: CliRunner,
        mock_workspace: MagicMock,  # noqa: ARG002
    ) -> None:
        """Running reports with no subcommand shows usage help."""
        result = cli_runner.invoke(app, ["reports"])

        assert result.exit_code == 0 or result.exit_code == 2
        assert "Usage" in result.stdout or "Usage" in (result.stderr or "")
