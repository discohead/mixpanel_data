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
    CohortInfo,
    EventCountsResult,
    FlowsResult,
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

    def test_sql_scalar_plain_with_jq_errors(
        self, cli_runner: CliRunner, mock_workspace: MagicMock
    ) -> None:
        """Test --scalar --format plain --jq errors instead of silently ignoring."""
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
                    "plain",
                    "--jq",
                    ".value",
                ],
            )

        # Should error, not silently ignore the jq filter
        assert result.exit_code == 3
        assert "json" in result.output.lower()


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

    def test_segmentation_table_format_normalized(
        self, cli_runner: CliRunner, mock_workspace: MagicMock
    ) -> None:
        """Table format should use normalized data with date/segment/count columns."""
        mock_workspace.segmentation.return_value = SegmentationResult(
            event="Purchase",
            from_date="2024-01-01",
            to_date="2024-01-02",
            unit="day",
            segment_property="country",
            total=375,
            series={
                "US": {"2024-01-01": 100, "2024-01-02": 150},
                "EU": {"2024-01-01": 50, "2024-01-02": 75},
            },
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
                    "Purchase",
                    "--from",
                    "2024-01-01",
                    "--to",
                    "2024-01-02",
                    "--on",
                    "country",
                    "--format",
                    "table",
                ],
            )

        assert result.exit_code == 0
        # Table output should contain column headers for normalized data
        assert "DATE" in result.stdout
        assert "SEGMENT" in result.stdout
        assert "COUNT" in result.stdout
        # Should NOT contain the nested series JSON structure
        assert "series" not in result.stdout.lower()

    def test_segmentation_json_format_unchanged(
        self, cli_runner: CliRunner, mock_workspace: MagicMock
    ) -> None:
        """JSON format should still use nested series structure."""
        mock_workspace.segmentation.return_value = SegmentationResult(
            event="Purchase",
            from_date="2024-01-01",
            to_date="2024-01-02",
            unit="day",
            segment_property="country",
            total=375,
            series={
                "US": {"2024-01-01": 100, "2024-01-02": 150},
                "EU": {"2024-01-01": 50, "2024-01-02": 75},
            },
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
                    "Purchase",
                    "--from",
                    "2024-01-01",
                    "--to",
                    "2024-01-02",
                    "--on",
                    "country",
                    "--format",
                    "json",
                ],
            )

        assert result.exit_code == 0
        data = json.loads(result.stdout)
        # JSON format should have nested series structure
        assert "series" in data
        assert isinstance(data["series"], dict)
        assert "US" in data["series"]
        assert "2024-01-01" in data["series"]["US"]

    def test_segmentation_table_without_segments(
        self, cli_runner: CliRunner, mock_workspace: MagicMock
    ) -> None:
        """Table format should work without segmentation (unsegmented query)."""
        mock_workspace.segmentation.return_value = SegmentationResult(
            event="Purchase",
            from_date="2024-01-01",
            to_date="2024-01-02",
            unit="day",
            segment_property=None,
            total=250,
            series={
                "total": {"2024-01-01": 100, "2024-01-02": 150},
            },
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
                    "Purchase",
                    "--from",
                    "2024-01-01",
                    "--to",
                    "2024-01-02",
                    "--format",
                    "table",
                ],
            )

        assert result.exit_code == 0
        # Should still have normalized columns
        assert "DATE" in result.stdout
        assert "SEGMENT" in result.stdout
        assert "COUNT" in result.stdout


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

    def test_funnel_table_format_normalized(
        self, cli_runner: CliRunner, mock_workspace: MagicMock
    ) -> None:
        """Table format should use normalized data with step/event/count/conversion_rate columns."""
        mock_workspace.funnel.return_value = FunnelResult(
            funnel_id=123,
            funnel_name="Signup Funnel",
            from_date="2024-01-01",
            to_date="2024-01-31",
            conversion_rate=0.5,
            steps=[
                FunnelStep(event="View Page", count=1000, conversion_rate=1.0),
                FunnelStep(event="Sign Up", count=500, conversion_rate=0.5),
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
                    "table",
                ],
            )

        assert result.exit_code == 0
        # Table output should contain column headers for normalized data
        assert "STEP" in result.stdout
        assert "EVENT" in result.stdout
        assert "COUNT" in result.stdout
        assert "CONVERSION_RATE" in result.stdout or "CONVERSION RATE" in result.stdout
        # Should NOT contain the nested steps JSON structure
        assert "steps" not in result.stdout.lower()


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

    def test_retention_table_format_normalized(
        self, cli_runner: CliRunner, mock_workspace: MagicMock
    ) -> None:
        """Table format should use normalized data with cohort_date/cohort_size/period_N columns."""
        mock_workspace.retention.return_value = RetentionResult(
            born_event="Signup",
            return_event="Login",
            from_date="2024-01-01",
            to_date="2024-01-31",
            unit="day",
            cohorts=[
                CohortInfo(date="2024-01-01", size=100, retention=[1.0, 0.8, 0.6]),
                CohortInfo(date="2024-01-02", size=150, retention=[1.0, 0.7, 0.5]),
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
                    "table",
                ],
            )

        assert result.exit_code == 0
        # Table output should contain column headers for normalized data
        assert "COHORT_DATE" in result.stdout or "COHORT DATE" in result.stdout
        assert "COHORT_SIZE" in result.stdout or "COHORT SIZE" in result.stdout
        assert (
            "PERIOD " in result.stdout
        )  # period_0, period_1, etc. (Rich formats period_0 as PERIOD 0)
        # Should NOT contain the nested cohorts JSON structure
        assert "cohorts" not in result.stdout.lower()


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

    def test_jql_table_format_groupby_normalized(
        self, cli_runner: CliRunner, mock_workspace: MagicMock
    ) -> None:
        """Table format should use normalized data for groupBy results."""
        # Simulate groupBy result: Events.groupBy(['country'], reducer.count())
        mock_workspace.jql.return_value = JQLResult(
            _raw=[
                {"key": ["US"], "value": 1000},
                {"key": ["EU"], "value": 500},
                {"key": ["Asia"], "value": 300},
            ]
        )

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
                    "table",
                ],
            )

        assert result.exit_code == 0
        # Table output should contain normalized columns from groupBy expansion
        assert "KEY_0" in result.stdout or "KEY 0" in result.stdout
        assert "VALUE" in result.stdout
        # Should NOT contain the nested raw JSON structure
        assert '"key"' not in result.stdout.lower()

    def test_jql_table_format_simple_dicts(
        self, cli_runner: CliRunner, mock_workspace: MagicMock
    ) -> None:
        """Table format should handle simple list of dicts."""
        # Simulate simple dict result from .map()
        mock_workspace.jql.return_value = JQLResult(
            _raw=[
                {"event": "Login", "count": 100},
                {"event": "Signup", "count": 50},
            ]
        )

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
                    "table",
                ],
            )

        assert result.exit_code == 0
        # Table output should contain columns from dict keys
        assert "EVENT" in result.stdout
        assert "COUNT" in result.stdout

    def test_jql_json_format_unchanged(
        self, cli_runner: CliRunner, mock_workspace: MagicMock
    ) -> None:
        """JSON format should still use nested raw structure."""
        mock_workspace.jql.return_value = JQLResult(
            _raw=[{"key": ["US"], "value": 1000}]
        )

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
        data = json.loads(result.stdout)
        # JSON format should preserve raw structure
        assert "raw" in data
        assert data["raw"] == [{"key": ["US"], "value": 1000}]


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

    def test_event_counts_table_format_normalized(
        self, cli_runner: CliRunner, mock_workspace: MagicMock
    ) -> None:
        """Table format should use normalized data with date/event/count columns."""
        mock_workspace.event_counts.return_value = EventCountsResult(
            events=["Login", "Purchase"],
            from_date="2024-01-01",
            to_date="2024-01-02",
            unit="day",
            type="general",
            series={
                "Login": {"2024-01-01": 100, "2024-01-02": 150},
                "Purchase": {"2024-01-01": 50, "2024-01-02": 75},
            },
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
                    "Login,Purchase",
                    "--from",
                    "2024-01-01",
                    "--to",
                    "2024-01-02",
                    "--format",
                    "table",
                ],
            )

        assert result.exit_code == 0
        # Table output should contain column headers for normalized data
        assert "DATE" in result.stdout
        assert "EVENT" in result.stdout
        assert "COUNT" in result.stdout
        # Should NOT contain the nested series JSON structure
        assert "series" not in result.stdout.lower()


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

    def test_property_counts_table_format_normalized(
        self, cli_runner: CliRunner, mock_workspace: MagicMock
    ) -> None:
        """Table format should use normalized data with date/value/count columns."""
        mock_workspace.property_counts.return_value = PropertyCountsResult(
            event="Purchase",
            property_name="country",
            from_date="2024-01-01",
            to_date="2024-01-02",
            unit="day",
            type="general",
            series={
                "US": {"2024-01-01": 100, "2024-01-02": 150},
                "EU": {"2024-01-01": 50, "2024-01-02": 75},
            },
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
                    "Purchase",
                    "--property",
                    "country",
                    "--from",
                    "2024-01-01",
                    "--to",
                    "2024-01-02",
                    "--format",
                    "table",
                ],
            )

        assert result.exit_code == 0
        # Table output should contain column headers for normalized data
        assert "DATE" in result.stdout
        assert "VALUE" in result.stdout
        assert "COUNT" in result.stdout
        # Should NOT contain the nested series JSON structure
        assert "series" not in result.stdout.lower()


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

    def test_activity_feed_table_format_normalized(
        self, cli_runner: CliRunner, mock_workspace: MagicMock
    ) -> None:
        """Table format should use normalized data with event/time/distinct_id columns."""
        mock_workspace.activity_feed.return_value = ActivityFeedResult(
            distinct_ids=["user1"],
            from_date="2024-01-01",
            to_date="2024-01-02",
            events=[
                UserEvent(
                    event="Login",
                    time=datetime(2024, 1, 1, 10, 0, 0),
                    properties={"$distinct_id": "user1", "city": "SF"},
                ),
                UserEvent(
                    event="Purchase",
                    time=datetime(2024, 1, 2, 11, 0, 0),
                    properties={"$distinct_id": "user1", "amount": 50},
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
                    "user1",
                    "--from",
                    "2024-01-01",
                    "--to",
                    "2024-01-02",
                    "--format",
                    "table",
                ],
            )

        assert result.exit_code == 0
        # Table output should contain column headers for normalized data
        assert "EVENT" in result.stdout
        assert "TIME" in result.stdout
        assert "DISTINCT_ID" in result.stdout or "DISTINCT ID" in result.stdout
        # Should NOT contain the nested events JSON structure
        assert '"events"' not in result.stdout.lower()


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

    def test_frequency_table_format_normalized(
        self, cli_runner: CliRunner, mock_workspace: MagicMock
    ) -> None:
        """Table format should use normalized data with date/period_N columns."""
        mock_workspace.frequency.return_value = FrequencyResult(
            event="Login",
            from_date="2024-01-01",
            to_date="2024-01-02",
            unit="day",
            addiction_unit="hour",
            data={
                "2024-01-01": [100, 50, 25],
                "2024-01-02": [120, 60, 30],
            },
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
                    "2024-01-02",
                    "--event",
                    "Login",
                    "--format",
                    "table",
                ],
            )

        assert result.exit_code == 0
        # Table output should contain column headers for normalized data
        assert "DATE" in result.stdout
        assert (
            "PERIOD " in result.stdout
        )  # PERIOD 1, PERIOD 2, etc. (Rich formats period_1 as PERIOD 1)
        # Should NOT contain the nested data JSON structure
        assert '"data"' not in result.stdout.lower()


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

    def test_segmentation_numeric_table_format_normalized(
        self, cli_runner: CliRunner, mock_workspace: MagicMock
    ) -> None:
        """Table format should use normalized data with date/bucket/count columns."""
        mock_workspace.segmentation_numeric.return_value = NumericBucketResult(
            event="Purchase",
            from_date="2024-01-01",
            to_date="2024-01-02",
            property_expr="price",
            unit="day",
            series={
                "0-10": {"2024-01-01": 100, "2024-01-02": 150},
                "10-20": {"2024-01-01": 50, "2024-01-02": 75},
            },
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
                    "2024-01-02",
                    "--format",
                    "table",
                ],
            )

        assert result.exit_code == 0
        # Table output should contain column headers for normalized data
        assert "DATE" in result.stdout
        assert "BUCKET" in result.stdout
        assert "COUNT" in result.stdout
        # Should NOT contain the nested series JSON structure
        assert "series" not in result.stdout.lower()


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

    def test_segmentation_sum_table_format_normalized(
        self, cli_runner: CliRunner, mock_workspace: MagicMock
    ) -> None:
        """Table format should use normalized data with date/sum columns."""
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
                    "table",
                ],
            )

        assert result.exit_code == 0
        # Table output should contain column headers for normalized data
        assert "DATE" in result.stdout
        assert "SUM" in result.stdout
        # Should NOT contain the nested results JSON structure
        assert "results" not in result.stdout.lower()


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

    def test_segmentation_average_table_format_normalized(
        self, cli_runner: CliRunner, mock_workspace: MagicMock
    ) -> None:
        """Table format should use normalized data with date/average columns."""
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
                    "table",
                ],
            )

        assert result.exit_code == 0
        # Table output should contain column headers for normalized data
        assert "DATE" in result.stdout
        assert "AVERAGE" in result.stdout
        # Should NOT contain the nested results JSON structure
        assert "results" not in result.stdout.lower()


class TestQueryFlows:
    """Tests for mp query flows command."""

    def test_flows_happy_path(
        self, cli_runner: CliRunner, mock_workspace: MagicMock
    ) -> None:
        """Test flows query with bookmark ID."""
        mock_workspace.query_flows.return_value = FlowsResult(
            bookmark_id=12345,
            computed_at="2024-02-01T00:00:00Z",
            steps=[{"event": "View Page", "count": 1000}],
            breakdowns=[],
            overall_conversion_rate=0.5,
        )

        with patch(
            "mixpanel_data.cli.commands.query.get_workspace",
            return_value=mock_workspace,
        ):
            result = cli_runner.invoke(
                app,
                ["query", "flows", "12345", "--format", "json"],
            )

        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["bookmark_id"] == 12345

    def test_flows_table_format_normalized(
        self, cli_runner: CliRunner, mock_workspace: MagicMock
    ) -> None:
        """Table format should use normalized data from steps."""
        mock_workspace.query_flows.return_value = FlowsResult(
            bookmark_id=12345,
            computed_at="2024-02-01T00:00:00Z",
            steps=[
                {"event": "View Page", "count": 1000},
                {"event": "Sign Up", "count": 500},
            ],
            breakdowns=[],
            overall_conversion_rate=0.5,
        )

        with patch(
            "mixpanel_data.cli.commands.query.get_workspace",
            return_value=mock_workspace,
        ):
            result = cli_runner.invoke(
                app,
                ["query", "flows", "12345", "--format", "table"],
            )

        assert result.exit_code == 0
        # Table output should contain column headers from steps data
        assert "EVENT" in result.stdout
        assert "COUNT" in result.stdout
        # Should NOT contain the nested steps/breakdowns JSON structure
        assert "steps" not in result.stdout.lower()
