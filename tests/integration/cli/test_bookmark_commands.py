"""Integration tests for bookmark CLI commands.

Phase 015: Bookmarks API - Tests for inspect bookmarks, query saved-report, query flows.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from mixpanel_data.cli.main import app
from mixpanel_data.types import BookmarkInfo, FlowsResult, SavedReportResult


class TestInspectBookmarks:
    """Tests for mp inspect bookmarks command."""

    def test_bookmarks_json_format(
        self, cli_runner: CliRunner, mock_workspace: MagicMock
    ) -> None:
        """Test listing bookmarks in JSON format."""
        mock_workspace.list_bookmarks.return_value = [
            BookmarkInfo(
                id=12345,
                name="Weekly Users",
                type="insights",
                project_id=100,
                created="2024-01-01T00:00:00",
                modified="2024-01-15T10:00:00",
            ),
            BookmarkInfo(
                id=12346,
                name="Conversion Funnel",
                type="funnels",
                project_id=100,
                created="2024-01-01T00:00:00",
                modified="2024-01-15T10:00:00",
            ),
        ]

        with patch(
            "mixpanel_data.cli.commands.inspect.get_workspace",
            return_value=mock_workspace,
        ):
            result = cli_runner.invoke(
                app, ["inspect", "bookmarks", "--format", "json"]
            )

        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert len(data) == 2
        assert data[0]["id"] == 12345
        assert data[0]["name"] == "Weekly Users"
        assert data[1]["type"] == "funnels"

    def test_bookmarks_with_type_filter(
        self, cli_runner: CliRunner, mock_workspace: MagicMock
    ) -> None:
        """Test listing bookmarks with type filter."""
        mock_workspace.list_bookmarks.return_value = [
            BookmarkInfo(
                id=12345,
                name="Weekly Users",
                type="insights",
                project_id=100,
                created="2024-01-01T00:00:00",
                modified="2024-01-15T10:00:00",
            ),
        ]

        with patch(
            "mixpanel_data.cli.commands.inspect.get_workspace",
            return_value=mock_workspace,
        ):
            result = cli_runner.invoke(
                app, ["inspect", "bookmarks", "--type", "insights", "--format", "json"]
            )

        assert result.exit_code == 0
        mock_workspace.list_bookmarks.assert_called_once_with(bookmark_type="insights")

    def test_bookmarks_plain_format(
        self, cli_runner: CliRunner, mock_workspace: MagicMock
    ) -> None:
        """Test listing bookmarks in plain format."""
        mock_workspace.list_bookmarks.return_value = [
            BookmarkInfo(
                id=12345,
                name="Weekly Users",
                type="insights",
                project_id=100,
                created="2024-01-01T00:00:00",
                modified="2024-01-15T10:00:00",
            ),
        ]

        with patch(
            "mixpanel_data.cli.commands.inspect.get_workspace",
            return_value=mock_workspace,
        ):
            result = cli_runner.invoke(
                app, ["inspect", "bookmarks", "--format", "plain"]
            )

        assert result.exit_code == 0
        assert "Weekly Users" in result.stdout

    def test_bookmarks_empty_result(
        self, cli_runner: CliRunner, mock_workspace: MagicMock
    ) -> None:
        """Test listing bookmarks with no results."""
        mock_workspace.list_bookmarks.return_value = []

        with patch(
            "mixpanel_data.cli.commands.inspect.get_workspace",
            return_value=mock_workspace,
        ):
            result = cli_runner.invoke(
                app, ["inspect", "bookmarks", "--format", "json"]
            )

        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data == []


class TestQuerySavedReport:
    """Tests for mp query saved-report command."""

    def test_saved_report_json_format(
        self, cli_runner: CliRunner, mock_workspace: MagicMock
    ) -> None:
        """Test querying saved report in JSON format."""
        mock_workspace.query_saved_report.return_value = SavedReportResult(
            bookmark_id=12345,
            computed_at="2024-01-15T10:00:00",
            from_date="2024-01-01",
            to_date="2024-01-14",
            headers=["$event"],
            series={"Page View": {"2024-01-01": 100}},
        )

        with patch(
            "mixpanel_data.cli.commands.query.get_workspace",
            return_value=mock_workspace,
        ):
            result = cli_runner.invoke(
                app, ["query", "saved-report", "12345", "--format", "json"]
            )

        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["bookmark_id"] == 12345
        assert data["report_type"] == "insights"
        mock_workspace.query_saved_report.assert_called_once_with(bookmark_id=12345)

    def test_saved_report_retention_type(
        self, cli_runner: CliRunner, mock_workspace: MagicMock
    ) -> None:
        """Test querying retention saved report."""
        mock_workspace.query_saved_report.return_value = SavedReportResult(
            bookmark_id=12346,
            computed_at="2024-01-15T10:00:00",
            from_date="2024-01-01",
            to_date="2024-01-14",
            headers=["$retention"],
            series={},
        )

        with patch(
            "mixpanel_data.cli.commands.query.get_workspace",
            return_value=mock_workspace,
        ):
            result = cli_runner.invoke(
                app, ["query", "saved-report", "12346", "--format", "json"]
            )

        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["report_type"] == "retention"

    def test_saved_report_funnel_type(
        self, cli_runner: CliRunner, mock_workspace: MagicMock
    ) -> None:
        """Test querying funnel saved report."""
        mock_workspace.query_saved_report.return_value = SavedReportResult(
            bookmark_id=12347,
            computed_at="2024-01-15T10:00:00",
            from_date="2024-01-01",
            to_date="2024-01-14",
            headers=["$funnel"],
            series={},
        )

        with patch(
            "mixpanel_data.cli.commands.query.get_workspace",
            return_value=mock_workspace,
        ):
            result = cli_runner.invoke(
                app, ["query", "saved-report", "12347", "--format", "json"]
            )

        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["report_type"] == "funnel"


class TestQueryFlows:
    """Tests for mp query flows command."""

    def test_flows_json_format(
        self, cli_runner: CliRunner, mock_workspace: MagicMock
    ) -> None:
        """Test querying flows report in JSON format."""
        mock_workspace.query_flows.return_value = FlowsResult(
            bookmark_id=12345,
            computed_at="2024-01-15T10:00:00",
            steps=[
                {"step": 1, "event": "Page View", "count": 1000},
                {"step": 2, "event": "Add to Cart", "count": 500},
            ],
            breakdowns=[{"path": "Page View -> Add to Cart", "count": 500}],
            overall_conversion_rate=0.5,
        )

        with patch(
            "mixpanel_data.cli.commands.query.get_workspace",
            return_value=mock_workspace,
        ):
            result = cli_runner.invoke(
                app, ["query", "flows", "12345", "--format", "json"]
            )

        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["bookmark_id"] == 12345
        assert len(data["steps"]) == 2
        assert data["overall_conversion_rate"] == 0.5
        mock_workspace.query_flows.assert_called_once_with(bookmark_id=12345)

    def test_flows_with_metadata(
        self, cli_runner: CliRunner, mock_workspace: MagicMock
    ) -> None:
        """Test querying flows report with metadata."""
        mock_workspace.query_flows.return_value = FlowsResult(
            bookmark_id=12345,
            computed_at="2024-01-15T10:00:00",
            steps=[],
            breakdowns=[],
            overall_conversion_rate=0.0,
            metadata={"version": "2.0"},
        )

        with patch(
            "mixpanel_data.cli.commands.query.get_workspace",
            return_value=mock_workspace,
        ):
            result = cli_runner.invoke(
                app, ["query", "flows", "12345", "--format", "json"]
            )

        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["metadata"] == {"version": "2.0"}

    def test_flows_plain_format(
        self, cli_runner: CliRunner, mock_workspace: MagicMock
    ) -> None:
        """Test querying flows report in plain format."""
        mock_workspace.query_flows.return_value = FlowsResult(
            bookmark_id=12345,
            computed_at="2024-01-15T10:00:00",
            steps=[{"step": 1, "event": "Page View", "count": 1000}],
            breakdowns=[],
            overall_conversion_rate=0.5,
        )

        with patch(
            "mixpanel_data.cli.commands.query.get_workspace",
            return_value=mock_workspace,
        ):
            result = cli_runner.invoke(
                app, ["query", "flows", "12345", "--format", "plain"]
            )

        assert result.exit_code == 0
        assert "Page View" in result.stdout or "12345" in result.stdout
