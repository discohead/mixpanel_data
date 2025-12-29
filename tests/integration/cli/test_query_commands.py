"""Integration tests for query CLI commands."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from mixpanel_data.cli.main import app
from mixpanel_data.types import (
    ActivityFeedResult,
    EventCountsResult,
    FrequencyResult,
    FunnelResult,
    FunnelStep,
    JQLResult,
    NumericAverageResult,
    NumericBucketResult,
    NumericSumResult,
    PropertyCountsResult,
    RetentionResult,
    SavedReportResult,
    SegmentationResult,
    SQLResult,
    UserEvent,
)


class TestQuerySql:
    """Tests for mp query sql command."""

    def test_sql_with_query_argument(
        self, cli_runner: CliRunner, mock_workspace: MagicMock
    ) -> None:
        """Test SQL query with inline argument."""
        mock_workspace.sql_rows.return_value = SQLResult(
            columns=["count"], rows=[(100,)]
        )

        with patch(
            "mixpanel_data.cli.commands.query.get_workspace",
            return_value=mock_workspace,
        ):
            result = cli_runner.invoke(
                app,
                [
                    "query",
                    "sql",
                    "SELECT COUNT(*) as count FROM events",
                    "--format",
                    "json",
                ],
            )

        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data == [{"count": 100}]

    def test_sql_with_file_option(
        self, cli_runner: CliRunner, mock_workspace: MagicMock, tmp_path: Path
    ) -> None:
        """Test SQL query from file."""
        sql_file = tmp_path / "query.sql"
        sql_file.write_text("SELECT * FROM events LIMIT 10")

        mock_workspace.sql_rows.return_value = SQLResult(
            columns=["event"], rows=[("Signup",)]
        )

        with patch(
            "mixpanel_data.cli.commands.query.get_workspace",
            return_value=mock_workspace,
        ):
            result = cli_runner.invoke(
                app,
                ["query", "sql", "--file", str(sql_file), "--format", "json"],
            )

        assert result.exit_code == 0
        mock_workspace.sql_rows.assert_called_once_with("SELECT * FROM events LIMIT 10")

    def test_sql_file_not_found(self, cli_runner: CliRunner) -> None:
        """Test error when SQL file doesn't exist."""
        result = cli_runner.invoke(
            app,
            ["query", "sql", "--file", "/nonexistent/query.sql", "--format", "json"],
        )

        assert result.exit_code == 4  # NOT_FOUND
        assert "File not found" in result.output

    def test_sql_no_query_or_file(self, cli_runner: CliRunner) -> None:
        """Test error when neither query nor file provided."""
        result = cli_runner.invoke(app, ["query", "sql", "--format", "json"])

        assert result.exit_code == 3
        assert "Provide a query or use --file" in result.output

    def test_sql_scalar_mode(
        self, cli_runner: CliRunner, mock_workspace: MagicMock
    ) -> None:
        """Test --scalar flag returns single value."""
        mock_workspace.sql_scalar.return_value = 42

        with patch(
            "mixpanel_data.cli.commands.query.get_workspace",
            return_value=mock_workspace,
        ):
            result = cli_runner.invoke(
                app,
                [
                    "query",
                    "sql",
                    "SELECT COUNT(*) FROM events",
                    "--scalar",
                    "--format",
                    "json",
                ],
            )

        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data == {"value": 42}


class TestQuerySegmentation:
    """Tests for mp query segmentation command."""

    def test_segmentation_happy_path(
        self, cli_runner: CliRunner, mock_workspace: MagicMock
    ) -> None:
        """Test segmentation query with required options."""
        mock_workspace.segmentation.return_value = SegmentationResult(
            event="Signup",
            from_date="2024-01-01",
            to_date="2024-01-31",
            unit="day",
            segment_property=None,
            total=500,
            series={"$overall": {"2024-01-01": 100}},
        )

        with patch(
            "mixpanel_data.cli.commands.query.get_workspace",
            return_value=mock_workspace,
        ):
            result = cli_runner.invoke(
                app,
                [
                    "query",
                    "segmentation",
                    "--event",
                    "Signup",
                    "--from",
                    "2024-01-01",
                    "--to",
                    "2024-01-31",
                    "--format",
                    "json",
                ],
            )

        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["event"] == "Signup"
        assert data["total"] == 500

    def test_segmentation_with_segment_property(
        self, cli_runner: CliRunner, mock_workspace: MagicMock
    ) -> None:
        """Test segmentation with --on option."""
        mock_workspace.segmentation.return_value = SegmentationResult(
            event="Signup",
            from_date="2024-01-01",
            to_date="2024-01-31",
            unit="day",
            segment_property="country",
            total=500,
            series={"US": {"2024-01-01": 50}, "EU": {"2024-01-01": 30}},
        )

        with patch(
            "mixpanel_data.cli.commands.query.get_workspace",
            return_value=mock_workspace,
        ):
            result = cli_runner.invoke(
                app,
                [
                    "query",
                    "segmentation",
                    "--event",
                    "Signup",
                    "--from",
                    "2024-01-01",
                    "--to",
                    "2024-01-31",
                    "--on",
                    "country",
                    "--format",
                    "json",
                ],
            )

        assert result.exit_code == 0
        call_kwargs = mock_workspace.segmentation.call_args.kwargs
        assert call_kwargs["on"] == "country"


class TestQueryFunnel:
    """Tests for mp query funnel command."""

    def test_funnel_happy_path(
        self, cli_runner: CliRunner, mock_workspace: MagicMock
    ) -> None:
        """Test funnel query with required options."""
        mock_workspace.funnel.return_value = FunnelResult(
            funnel_id=123,
            funnel_name="Signup Funnel",
            from_date="2024-01-01",
            to_date="2024-01-31",
            conversion_rate=0.5,
            steps=[
                FunnelStep(
                    event="View Page",
                    count=1000,
                    conversion_rate=1.0,
                ),
                FunnelStep(
                    event="Sign Up",
                    count=500,
                    conversion_rate=0.5,
                ),
            ],
        )

        with patch(
            "mixpanel_data.cli.commands.query.get_workspace",
            return_value=mock_workspace,
        ):
            result = cli_runner.invoke(
                app,
                [
                    "query",
                    "funnel",
                    "123",
                    "--from",
                    "2024-01-01",
                    "--to",
                    "2024-01-31",
                    "--format",
                    "json",
                ],
            )

        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["funnel_id"] == 123
        assert len(data["steps"]) == 2


class TestQueryRetention:
    """Tests for mp query retention command."""

    def test_retention_happy_path(
        self, cli_runner: CliRunner, mock_workspace: MagicMock
    ) -> None:
        """Test retention query with required options."""
        mock_workspace.retention.return_value = RetentionResult(
            born_event="Signup",
            return_event="Login",
            from_date="2024-01-01",
            to_date="2024-01-31",
            unit="day",
            cohorts=[],
        )

        with patch(
            "mixpanel_data.cli.commands.query.get_workspace",
            return_value=mock_workspace,
        ):
            result = cli_runner.invoke(
                app,
                [
                    "query",
                    "retention",
                    "--born",
                    "Signup",
                    "--return",
                    "Login",
                    "--from",
                    "2024-01-01",
                    "--to",
                    "2024-01-31",
                    "--format",
                    "json",
                ],
            )

        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["born_event"] == "Signup"
        assert data["return_event"] == "Login"


class TestQueryJql:
    """Tests for mp query jql command."""

    def test_jql_with_inline_script(
        self, cli_runner: CliRunner, mock_workspace: MagicMock
    ) -> None:
        """Test JQL with inline script."""
        mock_workspace.jql.return_value = JQLResult(_raw=[])

        with patch(
            "mixpanel_data.cli.commands.query.get_workspace",
            return_value=mock_workspace,
        ):
            result = cli_runner.invoke(
                app,
                [
                    "query",
                    "jql",
                    "--script",
                    "function main() { return []; }",
                    "--format",
                    "json",
                ],
            )

        assert result.exit_code == 0

    def test_jql_with_file(
        self, cli_runner: CliRunner, mock_workspace: MagicMock, tmp_path: Path
    ) -> None:
        """Test JQL with script file."""
        jql_file = tmp_path / "query.js"
        jql_file.write_text("function main() { return Events({}); }")

        mock_workspace.jql.return_value = JQLResult(_raw=[{"event": "Test"}])

        with patch(
            "mixpanel_data.cli.commands.query.get_workspace",
            return_value=mock_workspace,
        ):
            result = cli_runner.invoke(
                app,
                ["query", "jql", str(jql_file), "--format", "json"],
            )

        assert result.exit_code == 0

    def test_jql_file_not_found(self, cli_runner: CliRunner) -> None:
        """Test error when JQL file doesn't exist."""
        result = cli_runner.invoke(
            app,
            ["query", "jql", "/nonexistent/query.js", "--format", "json"],
        )

        assert result.exit_code == 4  # NOT_FOUND

    def test_jql_no_script_or_file(self, cli_runner: CliRunner) -> None:
        """Test error when neither script nor file provided."""
        result = cli_runner.invoke(app, ["query", "jql", "--format", "json"])

        assert result.exit_code == 3
        assert "Provide a file or use --script" in result.output

    def test_jql_with_params(
        self, cli_runner: CliRunner, mock_workspace: MagicMock
    ) -> None:
        """Test JQL with parameters."""
        mock_workspace.jql.return_value = JQLResult(_raw=["Signup"])

        with patch(
            "mixpanel_data.cli.commands.query.get_workspace",
            return_value=mock_workspace,
        ):
            result = cli_runner.invoke(
                app,
                [
                    "query",
                    "jql",
                    "--script",
                    "function main() { return params.event; }",
                    "--param",
                    "event=Signup",
                    "--format",
                    "json",
                ],
            )

        assert result.exit_code == 0
        call_kwargs = mock_workspace.jql.call_args.kwargs
        assert call_kwargs["params"] == {"event": "Signup"}

    def test_jql_invalid_param_format(self, cli_runner: CliRunner) -> None:
        """Test error with invalid parameter format."""
        result = cli_runner.invoke(
            app,
            [
                "query",
                "jql",
                "--script",
                "function main() {}",
                "--param",
                "invalid-no-equals",
                "--format",
                "json",
            ],
        )

        assert result.exit_code == 3
        assert "Invalid parameter format" in result.output


class TestQueryEventCounts:
    """Tests for mp query event-counts command."""

    def test_event_counts_happy_path(
        self, cli_runner: CliRunner, mock_workspace: MagicMock
    ) -> None:
        """Test event-counts with required options."""
        mock_workspace.event_counts.return_value = EventCountsResult(
            events=["Signup", "Login"],
            from_date="2024-01-01",
            to_date="2024-01-31",
            type="general",
            unit="day",
            series={"Signup": {"2024-01-01": 100}, "Login": {"2024-01-01": 200}},
        )

        with patch(
            "mixpanel_data.cli.commands.query.get_workspace",
            return_value=mock_workspace,
        ):
            result = cli_runner.invoke(
                app,
                [
                    "query",
                    "event-counts",
                    "--events",
                    "Signup,Login",
                    "--from",
                    "2024-01-01",
                    "--to",
                    "2024-01-31",
                    "--format",
                    "json",
                ],
            )

        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["events"] == ["Signup", "Login"]


class TestQueryPropertyCounts:
    """Tests for mp query property-counts command."""

    def test_property_counts_happy_path(
        self, cli_runner: CliRunner, mock_workspace: MagicMock
    ) -> None:
        """Test property-counts with required options."""
        mock_workspace.property_counts.return_value = PropertyCountsResult(
            event="Signup",
            property_name="country",
            from_date="2024-01-01",
            to_date="2024-01-31",
            type="general",
            unit="day",
            series={"US": {"2024-01-01": 50}},
        )

        with patch(
            "mixpanel_data.cli.commands.query.get_workspace",
            return_value=mock_workspace,
        ):
            result = cli_runner.invoke(
                app,
                [
                    "query",
                    "property-counts",
                    "--event",
                    "Signup",
                    "--property",
                    "country",
                    "--from",
                    "2024-01-01",
                    "--to",
                    "2024-01-31",
                    "--format",
                    "json",
                ],
            )

        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["event"] == "Signup"
        assert data["property_name"] == "country"


class TestQueryActivityFeed:
    """Tests for mp query activity-feed command."""

    def test_activity_feed_happy_path(
        self, cli_runner: CliRunner, mock_workspace: MagicMock
    ) -> None:
        """Test activity-feed with required options."""
        mock_workspace.activity_feed.return_value = ActivityFeedResult(
            distinct_ids=["user1", "user2"],
            from_date=None,
            to_date=None,
            events=[
                UserEvent(
                    event="Login", time=datetime(2024, 1, 1, 10, 0, 0), properties={}
                ),
            ],
        )

        with patch(
            "mixpanel_data.cli.commands.query.get_workspace",
            return_value=mock_workspace,
        ):
            result = cli_runner.invoke(
                app,
                [
                    "query",
                    "activity-feed",
                    "--users",
                    "user1,user2",
                    "--format",
                    "json",
                ],
            )

        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["distinct_ids"] == ["user1", "user2"]


class TestQuerySavedReport:
    """Tests for mp query saved-report command."""

    def test_saved_report_happy_path(
        self, cli_runner: CliRunner, mock_workspace: MagicMock
    ) -> None:
        """Test saved-report with bookmark ID."""
        mock_workspace.query_saved_report.return_value = SavedReportResult(
            bookmark_id=12345,
            computed_at="2024-02-01T00:00:00Z",
            from_date="2024-01-01",
            to_date="2024-01-31",
            headers=["Signup"],
            series={"Signup": {"2024-01-01": 100}},
        )

        with patch(
            "mixpanel_data.cli.commands.query.get_workspace",
            return_value=mock_workspace,
        ):
            result = cli_runner.invoke(
                app,
                ["query", "saved-report", "12345", "--format", "json"],
            )

        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["bookmark_id"] == 12345


class TestQueryFrequency:
    """Tests for mp query frequency command."""

    def test_frequency_happy_path(
        self, cli_runner: CliRunner, mock_workspace: MagicMock
    ) -> None:
        """Test frequency with required options."""
        mock_workspace.frequency.return_value = FrequencyResult(
            event=None,
            from_date="2024-01-01",
            to_date="2024-01-31",
            unit="day",
            addiction_unit="hour",
            data={"2024-01-01": [100, 50, 20]},
        )

        with patch(
            "mixpanel_data.cli.commands.query.get_workspace",
            return_value=mock_workspace,
        ):
            result = cli_runner.invoke(
                app,
                [
                    "query",
                    "frequency",
                    "--from",
                    "2024-01-01",
                    "--to",
                    "2024-01-31",
                    "--format",
                    "json",
                ],
            )

        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert "data" in data


class TestQuerySegmentationNumeric:
    """Tests for mp query segmentation-numeric command."""

    def test_segmentation_numeric_happy_path(
        self, cli_runner: CliRunner, mock_workspace: MagicMock
    ) -> None:
        """Test segmentation-numeric with required options."""
        mock_workspace.segmentation_numeric.return_value = NumericBucketResult(
            event="Purchase",
            from_date="2024-01-01",
            to_date="2024-01-31",
            property_expr="price",
            unit="day",
            series={"0-10": {"2024-01-01": 20}, "10-50": {"2024-01-01": 50}},
        )

        with patch(
            "mixpanel_data.cli.commands.query.get_workspace",
            return_value=mock_workspace,
        ):
            result = cli_runner.invoke(
                app,
                [
                    "query",
                    "segmentation-numeric",
                    "--event",
                    "Purchase",
                    "--on",
                    "price",
                    "--from",
                    "2024-01-01",
                    "--to",
                    "2024-01-31",
                    "--format",
                    "json",
                ],
            )

        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["event"] == "Purchase"
        assert data["property_expr"] == "price"


class TestQuerySegmentationSum:
    """Tests for mp query segmentation-sum command."""

    def test_segmentation_sum_happy_path(
        self, cli_runner: CliRunner, mock_workspace: MagicMock
    ) -> None:
        """Test segmentation-sum with required options."""
        mock_workspace.segmentation_sum.return_value = NumericSumResult(
            event="Purchase",
            from_date="2024-01-01",
            to_date="2024-01-31",
            property_expr="revenue",
            unit="day",
            results={"2024-01-01": 500.25, "2024-01-02": 600.50},
        )

        with patch(
            "mixpanel_data.cli.commands.query.get_workspace",
            return_value=mock_workspace,
        ):
            result = cli_runner.invoke(
                app,
                [
                    "query",
                    "segmentation-sum",
                    "--event",
                    "Purchase",
                    "--on",
                    "revenue",
                    "--from",
                    "2024-01-01",
                    "--to",
                    "2024-01-31",
                    "--format",
                    "json",
                ],
            )

        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["event"] == "Purchase"
        assert data["property_expr"] == "revenue"


class TestQuerySegmentationAverage:
    """Tests for mp query segmentation-average command."""

    def test_segmentation_average_happy_path(
        self, cli_runner: CliRunner, mock_workspace: MagicMock
    ) -> None:
        """Test segmentation-average with required options."""
        mock_workspace.segmentation_average.return_value = NumericAverageResult(
            event="Purchase",
            from_date="2024-01-01",
            to_date="2024-01-31",
            property_expr="price",
            unit="day",
            results={"2024-01-01": 45.50, "2024-01-02": 52.25},
        )

        with patch(
            "mixpanel_data.cli.commands.query.get_workspace",
            return_value=mock_workspace,
        ):
            result = cli_runner.invoke(
                app,
                [
                    "query",
                    "segmentation-average",
                    "--event",
                    "Purchase",
                    "--on",
                    "price",
                    "--from",
                    "2024-01-01",
                    "--to",
                    "2024-01-31",
                    "--format",
                    "json",
                ],
            )

        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["event"] == "Purchase"
        assert data["property_expr"] == "price"
