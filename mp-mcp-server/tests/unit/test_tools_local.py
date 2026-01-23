"""Tests for local SQL analysis tools.

These tests verify the local SQL tools work correctly with the DuckDB database.
"""

from unittest.mock import MagicMock

import pytest


class TestSqlTool:
    """Tests for the sql tool."""

    def test_sql_executes_query(self, mock_context: MagicMock) -> None:
        """Sql should execute SQL query and return results."""
        from mp_mcp_server.tools.local import sql

        result = sql(mock_context, query="SELECT * FROM events")
        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0]["name"] == "login"

    def test_sql_returns_dict_format(self, mock_context: MagicMock) -> None:
        """Sql should return results as list of dicts."""
        from mp_mcp_server.tools.local import sql

        result = sql(mock_context, query="SELECT COUNT(*) as cnt FROM events")
        assert isinstance(result, list)


class TestSqlScalarTool:
    """Tests for the sql_scalar tool."""

    def test_sql_scalar_returns_single_value(self, mock_context: MagicMock) -> None:
        """sql_scalar should return a single value."""
        from mp_mcp_server.tools.local import sql_scalar

        result = sql_scalar(mock_context, query="SELECT COUNT(*) FROM events")
        assert result == 42


class TestListTablesTool:
    """Tests for the list_tables tool."""

    def test_list_tables_returns_table_info(self, mock_context: MagicMock) -> None:
        """list_tables should return available tables."""
        from mp_mcp_server.tools.local import list_tables

        result = list_tables(mock_context)
        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0]["name"] == "events_jan"


class TestTableSchemaTool:
    """Tests for the table_schema tool."""

    def test_table_schema_returns_columns(self, mock_context: MagicMock) -> None:
        """table_schema should return column definitions."""
        from mp_mcp_server.tools.local import table_schema

        result = table_schema(mock_context, table="events_jan")
        assert isinstance(result, list)
        assert len(result) == 2
        assert result[0]["column"] == "name"


class TestSampleTool:
    """Tests for the sample tool."""

    def test_sample_returns_random_rows(self, mock_context: MagicMock) -> None:
        """Sample should return random rows from table."""
        from mp_mcp_server.tools.local import sample

        result = sample(mock_context, table="events_jan")
        assert isinstance(result, list)
        assert len(result) == 1


class TestSummarizeTool:
    """Tests for the summarize tool."""

    def test_summarize_returns_statistics(self, mock_context: MagicMock) -> None:
        """Summarize should return table statistics."""
        from mp_mcp_server.tools.local import summarize

        result = summarize(mock_context, table="events_jan")
        assert "row_count" in result
        assert result["row_count"] == 1000


class TestEventBreakdownTool:
    """Tests for the event_breakdown tool."""

    def test_event_breakdown_returns_counts(self, mock_context: MagicMock) -> None:
        """event_breakdown should return event counts."""
        from mp_mcp_server.tools.local import event_breakdown

        result = event_breakdown(mock_context, table="events_jan")
        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0]["name"] == "login"


class TestPropertyKeysTool:
    """Tests for the property_keys tool."""

    def test_property_keys_returns_sorted_keys(self, mock_context: MagicMock) -> None:
        """property_keys should return property keys from Workspace method."""
        from mp_mcp_server.tools.local import property_keys

        result = property_keys(mock_context, table="events_jan")
        assert isinstance(result, list)
        assert result == ["browser", "country", "device"]

    def test_property_keys_with_event_filter(self, mock_context: MagicMock) -> None:
        """property_keys should accept optional event filter."""
        from mp_mcp_server.tools.local import property_keys

        result = property_keys(mock_context, table="events_jan", event="login")
        assert isinstance(result, list)


class TestColumnStatsTool:
    """Tests for the column_stats tool."""

    def test_column_stats_returns_statistics(self, mock_context: MagicMock) -> None:
        """column_stats should return column statistics."""
        from mp_mcp_server.tools.local import column_stats

        sql_rows_mock = MagicMock()
        sql_rows_mock.to_dicts.return_value = [
            {
                "count": 1000,
                "distinct_count": 500,
                "min_value": "2024-01-01",
                "max_value": "2024-01-31",
            }
        ]
        mock_context.lifespan_context[
            "workspace"
        ].sql_rows.return_value = sql_rows_mock

        result = column_stats(mock_context, table="events_jan", column="time")
        assert result["count"] == 1000
        assert result["distinct_count"] == 500
        assert result["min_value"] == "2024-01-01"

    def test_column_stats_empty_result(self, mock_context: MagicMock) -> None:
        """column_stats should return structured result for empty tables."""
        from mp_mcp_server.tools.local import column_stats

        sql_rows_mock = MagicMock()
        sql_rows_mock.to_dicts.return_value = []
        mock_context.lifespan_context[
            "workspace"
        ].sql_rows.return_value = sql_rows_mock

        result = column_stats(mock_context, table="events_jan", column="time")
        assert result == {
            "count": 0,
            "distinct_count": 0,
            "min_value": None,
            "max_value": None,
            "note": "Table is empty or column has no values",
        }


class TestDropTableTool:
    """Tests for the drop_table tool."""

    def test_drop_table_removes_table(self, mock_context: MagicMock) -> None:
        """drop_table should remove a table."""
        from mp_mcp_server.tools.local import drop_table

        result = drop_table(mock_context, table="events_jan")
        assert result["success"] is True
        assert "events_jan" in result["message"]


class TestDropAllTablesTool:
    """Tests for the drop_all_tables tool."""

    def test_drop_all_removes_all_tables(self, mock_context: MagicMock) -> None:
        """drop_all_tables should remove all tables."""
        from mp_mcp_server.tools.local import drop_all_tables

        result = drop_all_tables(mock_context)
        assert result["success"] is True


class TestSqlInjectionPrevention:
    """Tests for SQL injection prevention in local tools."""

    def test_validate_table_name_rejects_semicolon(self) -> None:
        """Table names with semicolons should be rejected."""
        from mp_mcp_server.tools.local import _validate_table_name

        with pytest.raises(ValueError, match="Invalid table name"):
            _validate_table_name("events; DROP TABLE users--")

    def test_validate_table_name_rejects_spaces(self) -> None:
        """Table names with spaces should be rejected."""
        from mp_mcp_server.tools.local import _validate_table_name

        with pytest.raises(ValueError, match="Invalid table name"):
            _validate_table_name("events users")

    def test_validate_table_name_rejects_quotes(self) -> None:
        """Table names with quotes should be rejected."""
        from mp_mcp_server.tools.local import _validate_table_name

        with pytest.raises(ValueError, match="Invalid table name"):
            _validate_table_name('events"--')

    def test_validate_table_name_accepts_valid_names(self) -> None:
        """Valid table names should pass validation."""
        from mp_mcp_server.tools.local import _validate_table_name

        # Should not raise
        _validate_table_name("events")
        _validate_table_name("events_jan")
        _validate_table_name("_private_table")
        _validate_table_name("Events2024")

    def test_validate_column_rejects_drop(self) -> None:
        """Column expressions with DROP should be rejected."""
        from mp_mcp_server.tools.local import _validate_column_expression

        with pytest.raises(ValueError, match="DROP"):
            _validate_column_expression("time; DROP TABLE events")

    def test_validate_column_rejects_union(self) -> None:
        """Column expressions with UNION should be rejected."""
        from mp_mcp_server.tools.local import _validate_column_expression

        with pytest.raises(ValueError, match="UNION"):
            _validate_column_expression("id UNION SELECT password FROM users")

    def test_validate_column_rejects_select(self) -> None:
        """Column expressions with SELECT should be rejected."""
        from mp_mcp_server.tools.local import _validate_column_expression

        with pytest.raises(ValueError, match="SELECT"):
            _validate_column_expression("(SELECT secret FROM config)")

    def test_validate_column_rejects_comments(self) -> None:
        """Column expressions with SQL comments should be rejected."""
        from mp_mcp_server.tools.local import _validate_column_expression

        with pytest.raises(ValueError, match="--"):
            _validate_column_expression("time -- ignore rest")

        with pytest.raises(ValueError, match=r"/\*"):
            _validate_column_expression("time /* comment */")

    def test_validate_column_accepts_json_path(self) -> None:
        """Valid JSON path expressions should pass validation."""
        from mp_mcp_server.tools.local import _validate_column_expression

        # These should not raise
        _validate_column_expression("properties->>'$.field'")
        _validate_column_expression("properties->'$.browser'")
        _validate_column_expression("json_extract(properties, '$.name')")

    def test_column_stats_validates_table_name(self, mock_context: MagicMock) -> None:
        """column_stats should reject dangerous table names via ToolError."""
        from fastmcp.exceptions import ToolError

        from mp_mcp_server.tools.local import column_stats

        with pytest.raises(ToolError, match="Invalid table name"):
            column_stats(mock_context, table="events; DROP TABLE--", column="time")

    def test_column_stats_validates_column_expression(
        self, mock_context: MagicMock
    ) -> None:
        """column_stats should reject dangerous column expressions via ToolError."""
        from fastmcp.exceptions import ToolError

        from mp_mcp_server.tools.local import column_stats

        with pytest.raises(ToolError, match="disallowed pattern"):
            column_stats(mock_context, table="events", column="time; DROP TABLE x")

    def test_event_breakdown_validates_table_name(
        self, mock_context: MagicMock
    ) -> None:
        """event_breakdown should reject dangerous table names via ToolError."""
        from fastmcp.exceptions import ToolError

        from mp_mcp_server.tools.local import event_breakdown

        with pytest.raises(ToolError, match="Invalid table name"):
            event_breakdown(mock_context, table='events"; DELETE FROM users;--')
