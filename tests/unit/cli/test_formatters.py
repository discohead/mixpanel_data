"""Unit tests for CLI formatters."""

from __future__ import annotations

import csv
import io
import json
from datetime import date, datetime

from rich.table import Table

from mixpanel_data.cli.formatters import (
    format_csv,
    format_json,
    format_jsonl,
    format_plain,
    format_table,
)


class TestFormatJson:
    """Tests for format_json function."""

    def test_format_dict(self) -> None:
        """Test formatting a dictionary as JSON."""
        data = {"name": "test", "count": 123}
        result = format_json(data)

        parsed = json.loads(result)
        assert parsed == data

    def test_format_list(self) -> None:
        """Test formatting a list as JSON."""
        data = [{"a": 1}, {"a": 2}]
        result = format_json(data)

        parsed = json.loads(result)
        assert parsed == data

    def test_format_with_datetime(self) -> None:
        """Test formatting data with datetime values."""
        data = {"timestamp": datetime(2024, 1, 15, 10, 30, 0)}
        result = format_json(data)

        parsed = json.loads(result)
        assert parsed["timestamp"] == "2024-01-15T10:30:00"

    def test_format_with_date(self) -> None:
        """Test formatting data with date values."""
        data = {"date": date(2024, 1, 15)}
        result = format_json(data)

        parsed = json.loads(result)
        assert parsed["date"] == "2024-01-15"

    def test_format_pretty_printed(self) -> None:
        """Test that output is pretty-printed with indentation."""
        data = {"key": "value"}
        result = format_json(data)

        assert "\n" in result
        assert "  " in result  # Indentation

    def test_format_empty_dict(self) -> None:
        """Test formatting an empty dictionary."""
        result = format_json({})
        assert json.loads(result) == {}

    def test_format_empty_list(self) -> None:
        """Test formatting an empty list."""
        result = format_json([])
        assert json.loads(result) == []


class TestFormatJsonl:
    """Tests for format_jsonl function."""

    def test_format_list_as_jsonl(self) -> None:
        """Test formatting a list as JSONL."""
        data = [{"a": 1}, {"b": 2}]
        result = format_jsonl(data)

        lines = result.strip().split("\n")
        assert len(lines) == 2
        assert json.loads(lines[0]) == {"a": 1}
        assert json.loads(lines[1]) == {"b": 2}

    def test_format_single_dict(self) -> None:
        """Test formatting a single dict as JSONL."""
        data = {"name": "test"}
        result = format_jsonl(data)

        assert json.loads(result) == data
        assert "\n" not in result.strip()

    def test_format_with_datetime(self) -> None:
        """Test JSONL with datetime values."""
        data = [{"timestamp": datetime(2024, 1, 15)}]
        result = format_jsonl(data)

        parsed = json.loads(result.strip())
        assert parsed["timestamp"] == "2024-01-15T00:00:00"

    def test_format_empty_list(self) -> None:
        """Test formatting an empty list."""
        result = format_jsonl([])
        assert result == ""


class TestFormatTable:
    """Tests for format_table function."""

    def test_format_list_of_dicts(self) -> None:
        """Test formatting a list of dicts as a table."""
        data = [{"name": "Alice", "age": 30}, {"name": "Bob", "age": 25}]
        table = format_table(data)

        assert isinstance(table, Table)
        assert table.row_count == 2

    def test_format_with_columns(self) -> None:
        """Test formatting with specified columns."""
        data = [{"name": "Alice", "age": 30, "city": "NYC"}]
        table = format_table(data, columns=["name", "age"])

        assert isinstance(table, Table)
        # Column order should match specified columns

    def test_format_single_dict(self) -> None:
        """Test formatting a single dict."""
        data = {"name": "test"}
        table = format_table(data)

        assert isinstance(table, Table)
        assert table.row_count == 1

    def test_format_empty_list(self) -> None:
        """Test formatting an empty list."""
        table = format_table([])

        assert isinstance(table, Table)
        assert table.row_count == 0

    def test_format_list_of_strings(self) -> None:
        """Test formatting a list of strings."""
        data = ["item1", "item2", "item3"]
        table = format_table(data)

        assert isinstance(table, Table)
        assert table.row_count == 3

    def test_format_with_none_values(self) -> None:
        """Test formatting data with None values."""
        data = [{"name": "test", "value": None}]
        table = format_table(data)

        assert isinstance(table, Table)
        assert table.row_count == 1

    def test_format_with_bool_values(self) -> None:
        """Test formatting data with boolean values."""
        data = [{"active": True}, {"active": False}]
        table = format_table(data)

        assert isinstance(table, Table)


class TestFormatCsv:
    """Tests for format_csv function."""

    def test_format_list_of_dicts(self) -> None:
        """Test formatting a list of dicts as CSV."""
        data = [{"name": "Alice", "age": 30}, {"name": "Bob", "age": 25}]
        result = format_csv(data)

        reader = csv.DictReader(io.StringIO(result))
        rows = list(reader)
        assert len(rows) == 2
        assert rows[0]["name"] == "Alice"
        assert rows[0]["age"] == "30"

    def test_format_includes_headers(self) -> None:
        """Test that CSV includes header row."""
        data = [{"name": "test", "count": 1}]
        result = format_csv(data)

        lines = result.strip().split("\n")
        assert len(lines) == 2  # header + 1 data row
        assert "name" in lines[0]
        assert "count" in lines[0]

    def test_format_single_dict(self) -> None:
        """Test formatting a single dict."""
        data = {"name": "test"}
        result = format_csv(data)

        reader = csv.DictReader(io.StringIO(result))
        rows = list(reader)
        assert len(rows) == 1
        assert rows[0]["name"] == "test"

    def test_format_empty_list(self) -> None:
        """Test formatting an empty list."""
        result = format_csv([])
        assert result == ""

    def test_format_with_datetime(self) -> None:
        """Test CSV with datetime values."""
        data = [{"timestamp": datetime(2024, 1, 15, 10, 30)}]
        result = format_csv(data)

        assert "2024-01-15T10:30:00" in result

    def test_format_with_bool(self) -> None:
        """Test CSV with boolean values."""
        data = [{"active": True}]
        result = format_csv(data)

        assert "true" in result

    def test_format_with_nested_data(self) -> None:
        """Test CSV with nested dict/list values."""
        data = [{"nested": {"key": "value"}}]
        result = format_csv(data)

        # Nested data should be JSON-encoded (CSV escapes quotes as double quotes)
        assert "key" in result and "value" in result

    def test_format_list_of_strings(self) -> None:
        """Test formatting a list of strings."""
        data = ["item1", "item2"]
        result = format_csv(data)

        assert "value" in result  # header
        assert "item1" in result
        assert "item2" in result


class TestFormatPlain:
    """Tests for format_plain function."""

    def test_format_list_of_strings(self) -> None:
        """Test formatting a list of strings."""
        data = ["item1", "item2", "item3"]
        result = format_plain(data)

        lines = result.strip().split("\n")
        assert lines == ["item1", "item2", "item3"]

    def test_format_list_of_dicts_with_name(self) -> None:
        """Test formatting a list of dicts with 'name' key."""
        data = [{"name": "Alice"}, {"name": "Bob"}]
        result = format_plain(data)

        lines = result.strip().split("\n")
        assert lines == ["Alice", "Bob"]

    def test_format_list_of_dicts_with_event(self) -> None:
        """Test formatting a list of dicts with 'event' key."""
        data = [{"event": "Signup"}, {"event": "Purchase"}]
        result = format_plain(data)

        lines = result.strip().split("\n")
        assert lines == ["Signup", "Purchase"]

    def test_format_single_dict_with_name(self) -> None:
        """Test formatting a single dict with 'name' key."""
        data = {"name": "test", "count": 123}
        result = format_plain(data)

        assert result == "test"

    def test_format_single_dict_without_common_keys(self) -> None:
        """Test formatting a dict without common keys."""
        data = {"foo": "bar", "baz": 123}
        result = format_plain(data)

        # Should format as key=value pairs
        assert "foo=bar" in result
        assert "baz=123" in result

    def test_format_empty_list(self) -> None:
        """Test formatting an empty list."""
        result = format_plain([])
        assert result == ""

    def test_format_list_with_empty_dict(self) -> None:
        """Test formatting a list with an empty dict."""
        data = [{}]
        result = format_plain(data)

        assert result == ""
