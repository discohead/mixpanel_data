"""Property-based tests for CLI formatters using Hypothesis.

These tests verify invariants that should hold for all possible inputs,
catching edge cases that example-based tests might miss.

Properties tested:
- JSON roundtrip: format_json output can be parsed back to original data
- JSONL line validity: each line of format_jsonl output is valid JSON
- CSV parseability: format_csv output can be parsed by csv.reader
"""

from __future__ import annotations

import csv
import io
import json
from typing import Any

from hypothesis import assume, given
from hypothesis import strategies as st

from mixpanel_data.cli.formatters import (
    format_csv,
    format_json,
    format_jsonl,
)

# =============================================================================
# Custom Strategies
# =============================================================================

# Strategy for JSON-serializable primitive values (no datetime/date)
json_primitives = st.one_of(
    st.none(),
    st.booleans(),
    st.integers(),
    st.floats(allow_nan=False, allow_infinity=False),
    st.text(),
)

# Strategy for JSON-serializable values (recursive: primitives, lists, dicts)
json_values: st.SearchStrategy[Any] = st.recursive(
    json_primitives,
    lambda children: st.one_of(
        st.lists(children, max_size=5),
        st.dictionaries(st.text(), children, max_size=5),
    ),
    max_leaves=20,
)

# Strategy for JSON objects (dicts with string keys)
json_objects = st.dictionaries(st.text(), json_values, max_size=10)

# Strategy for lists of JSON objects (common input for formatters)
json_object_lists = st.lists(json_objects, max_size=10)

# Strategy for valid dict keys (non-empty, no problematic characters for CSV)
safe_keys = st.text(
    alphabet=st.characters(
        categories=("L", "N", "P", "S"),
        exclude_characters="\n\r\x00",
    ),
    min_size=1,
    max_size=30,
).filter(lambda s: s.strip())


# =============================================================================
# format_json Property Tests
# =============================================================================


class TestFormatJsonProperties:
    """Property-based tests for format_json function."""

    @given(data=json_objects)
    def test_roundtrip_preserves_dict_data(self, data: dict[str, Any]) -> None:
        """Formatting and parsing a dict should recover the original data.

        This property verifies that format_json produces valid JSON that,
        when parsed, equals the original dict (for JSON-serializable values).

        Args:
            data: A dictionary with string keys and JSON-serializable values.
        """
        formatted = format_json(data)
        parsed = json.loads(formatted)
        assert parsed == data

    @given(data=json_object_lists)
    def test_roundtrip_preserves_list_data(self, data: list[dict[str, Any]]) -> None:
        """Formatting and parsing a list should recover the original data.

        This property verifies that format_json produces valid JSON that,
        when parsed, equals the original list (for JSON-serializable values).

        Args:
            data: A list of dictionaries with JSON-serializable values.
        """
        formatted = format_json(data)
        parsed = json.loads(formatted)
        assert parsed == data

    @given(data=st.one_of(json_objects, json_object_lists))
    def test_output_is_valid_json(self, data: dict[str, Any] | list[Any]) -> None:
        """format_json output should always be valid JSON.

        This property ensures that no input causes format_json to produce
        invalid JSON output.

        Args:
            data: A dict or list to format.
        """
        formatted = format_json(data)
        # Should not raise
        json.loads(formatted)


# =============================================================================
# format_jsonl Property Tests
# =============================================================================


class TestFormatJsonlProperties:
    """Property-based tests for format_jsonl function."""

    @given(data=json_object_lists)
    def test_each_line_is_valid_json(self, data: list[dict[str, Any]]) -> None:
        """Each non-empty line of JSONL output should be valid JSON.

        JSONL format requires exactly one JSON object per line. This property
        verifies that the format is maintained regardless of input content.

        Args:
            data: A list of dictionaries to format as JSONL.
        """
        formatted = format_jsonl(data)

        if not data:
            assert formatted == ""
            return

        lines = formatted.split("\n")
        assert len(lines) == len(data)

        for line in lines:
            # Each line should be valid JSON
            json.loads(line)

    @given(data=json_object_lists)
    def test_roundtrip_preserves_list_items(self, data: list[dict[str, Any]]) -> None:
        """Parsing each JSONL line should recover the original list items.

        This property verifies data integrity through the JSONL format.

        Args:
            data: A list of dictionaries to format as JSONL.
        """
        formatted = format_jsonl(data)

        if not data:
            assert formatted == ""
            return

        lines = formatted.split("\n")
        parsed_items = [json.loads(line) for line in lines]
        assert parsed_items == data

    @given(data=json_objects)
    def test_single_dict_produces_single_line(self, data: dict[str, Any]) -> None:
        """A single dict should produce a single JSON line (no newlines).

        When format_jsonl receives a dict (not a list), it should output
        a single JSON object without trailing newlines.

        Args:
            data: A dictionary to format as JSONL.
        """
        formatted = format_jsonl(data)

        # Should be valid JSON
        parsed = json.loads(formatted)
        assert parsed == data

        # Should not contain newlines (single line)
        assert "\n" not in formatted.strip()


# =============================================================================
# format_csv Property Tests
# =============================================================================


class TestFormatCsvProperties:
    """Property-based tests for format_csv function."""

    @given(
        data=st.lists(
            st.dictionaries(
                safe_keys,
                st.one_of(
                    st.none(),
                    st.booleans(),
                    st.integers(),
                    st.floats(allow_nan=False, allow_infinity=False),
                    st.text().filter(lambda s: "\x00" not in s),
                ),
                min_size=1,
                max_size=5,
            ),
            min_size=1,
            max_size=10,
        )
    )
    def test_output_is_parseable_csv(self, data: list[dict[str, Any]]) -> None:
        """format_csv output should be parseable by Python's csv module.

        This property verifies that the CSV output conforms to the CSV
        format specification and can be read back.

        Args:
            data: A non-empty list of dictionaries to format as CSV.
        """
        # Ensure all dicts have at least one common key
        assume(len(data) > 0)
        assume(all(len(d) > 0 for d in data))

        formatted = format_csv(data)

        # Should be parseable without error
        reader = csv.reader(io.StringIO(formatted))
        rows = list(reader)

        # Should have header + data rows
        assert len(rows) == len(data) + 1

    @given(
        data=st.lists(
            st.dictionaries(
                safe_keys,
                st.one_of(
                    st.none(),
                    st.booleans(),
                    st.integers(),
                    st.text().filter(lambda s: "\x00" not in s),
                ),
                min_size=1,
                max_size=5,
            ),
            min_size=1,
            max_size=10,
        )
    )
    def test_row_count_matches_input_length(self, data: list[dict[str, Any]]) -> None:
        """CSV output should have exactly len(data) + 1 rows (header + data).

        This property verifies that no records are lost or duplicated during
        CSV formatting.

        Args:
            data: A non-empty list of dictionaries to format as CSV.
        """
        assume(len(data) > 0)
        assume(all(len(d) > 0 for d in data))

        formatted = format_csv(data)
        reader = csv.reader(io.StringIO(formatted))
        rows = list(reader)

        # Filter out truly empty rows (no cells at all), but keep rows with empty values
        rows = [r for r in rows if r]

        assert len(rows) == len(data) + 1  # header + data rows

    @given(data=st.just([]))
    def test_empty_list_returns_empty_string(self, data: list[Any]) -> None:
        """An empty list should produce an empty string.

        Args:
            data: An empty list.
        """
        formatted = format_csv(data)
        assert formatted == ""

    @given(
        data=st.lists(
            st.dictionaries(
                safe_keys,
                st.text().filter(lambda s: "\x00" not in s),
                min_size=1,
                max_size=3,
            ),
            min_size=1,
            max_size=5,
        )
    )
    def test_header_matches_first_dict_keys(self, data: list[dict[str, Any]]) -> None:
        """CSV header should contain all keys from the first dict.

        Args:
            data: A non-empty list of dictionaries.
        """
        assume(len(data) > 0)
        assume(len(data[0]) > 0)

        formatted = format_csv(data)
        reader = csv.DictReader(io.StringIO(formatted))
        fieldnames = reader.fieldnames

        assert fieldnames is not None
        assert set(fieldnames) == set(data[0].keys())
