"""Tests for improved JQLResult DataFrame conversion.

These tests demonstrate handling of common JQL result structures:
- groupBy with key/value structure
- Multi-level grouping
- Multiple reducers
- Single reduce results
"""

import pandas as pd
import pytest

from mixpanel_headless.types import JQLResult


class TestJQLResultGroupByStructure:
    """Tests for groupBy results with {key: [...], value: X} structure."""

    def test_single_key_groupby(self) -> None:
        """groupBy with single key should expand to column."""
        # Common pattern: .groupBy(['properties.country'], reducer)
        result = JQLResult(
            _raw=[
                {"key": ["US"], "value": 100},
                {"key": ["UK"], "value": 50},
                {"key": ["CA"], "value": 75},
            ]
        )

        df = result.df
        assert "key_0" in df.columns
        assert "value" in df.columns
        assert len(df) == 3
        assert df["value"].tolist() == [100, 50, 75]

    def test_multi_key_groupby(self) -> None:
        """groupBy with multiple keys should expand to separate columns."""
        # Common pattern: .groupBy(['properties.country', 'properties.browser'], reducer)
        result = JQLResult(
            _raw=[
                {"key": ["US", "Chrome"], "value": 100},
                {"key": ["US", "Firefox"], "value": 50},
                {"key": ["UK", "Chrome"], "value": 75},
            ]
        )

        df = result.df
        # Should have key_0, key_1 columns (or similar naming)
        key_columns = [col for col in df.columns if col.startswith("key")]
        assert len(key_columns) >= 2
        assert "value" in df.columns
        assert len(df) == 3

    def test_groupby_with_multiple_reducers(self) -> None:
        """groupBy with multiple reducers should expand value array."""
        # Common pattern: .groupBy([...], [reducer.count(), reducer.sum(), reducer.avg()])
        result = JQLResult(
            _raw=[
                {"key": ["US"], "value": [100, 5000, 50.0]},
                {"key": ["UK"], "value": [50, 2500, 50.0]},
            ]
        )

        df = result.df
        assert len(df) == 2
        # Value array should be expanded to value_0, value_1, value_2
        # OR detected as count/sum/avg if possible
        value_columns = [col for col in df.columns if "value" in col.lower()]
        assert len(value_columns) >= 3

    def test_groupby_with_named_reducers(self) -> None:
        """Test handling when reducers have semantic meaning."""
        # After .map() to rename: {country: "US", count: 100, total_revenue: 5000}
        result = JQLResult(
            _raw=[
                {"country": "US", "count": 100, "total_revenue": 5000, "avg": 50.0},
                {"country": "UK", "count": 50, "total_revenue": 2500, "avg": 50.0},
            ]
        )

        df = result.df
        # Already in good shape, should preserve columns
        assert "country" in df.columns
        assert "count" in df.columns
        assert "total_revenue" in df.columns
        assert "avg" in df.columns

    def test_groupby_preserves_additional_fields(self) -> None:
        """groupBy expansion should preserve fields added by .map()."""
        # Common pattern: groupBy result with .map() adding readable names
        result = JQLResult(
            _raw=[
                {"key": ["US"], "value": 100, "country_name": "United States"},
                {"key": ["UK"], "value": 50, "country_name": "United Kingdom"},
                {"key": ["CA"], "value": 75, "country_name": "Canada"},
            ]
        )

        df = result.df
        assert "key_0" in df.columns
        assert "value" in df.columns
        assert "country_name" in df.columns  # MUST be preserved
        assert df["country_name"].tolist() == [
            "United States",
            "United Kingdom",
            "Canada",
        ]


class TestJQLResultReduceStructure:
    """Tests for reduce() results."""

    def test_single_scalar_reduce(self) -> None:
        """reduce() returning single value should be wrapped sensibly."""
        # Common pattern: .reduce(mixpanel.reducer.count())
        result = JQLResult(_raw=[42])

        df = result.df
        assert len(df) == 1
        # Should have a sensible column name, e.g. "value" or "result"
        assert "value" in df.columns or "result" in df.columns

    def test_object_reduce(self) -> None:
        """reduce() returning object should expand to columns."""
        # Common pattern: .reduce(mixpanel.reducer.numeric_summary())
        result = JQLResult(
            _raw=[
                {
                    "count": 221,
                    "sum": 32624,
                    "sum_squares": 9199564,
                    "avg": 147.62,
                    "stddev": 140.84,
                }
            ]
        )

        df = result.df
        assert "count" in df.columns
        assert "sum" in df.columns
        assert "avg" in df.columns
        assert "stddev" in df.columns

    def test_percentiles_reduce(self) -> None:
        """reduce() with percentiles should handle nested structure."""
        # Common pattern: .reduce(mixpanel.reducer.numeric_percentiles())
        result = JQLResult(
            _raw=[
                [
                    {"percentile": 50, "value": 118},
                    {"percentile": 90, "value": 356},
                    {"percentile": 95, "value": 468},
                    {"percentile": 99, "value": 732},
                ]
            ]
        )

        df = result.df
        # Nested percentile structures should be flattened to one row per entry
        assert len(df) == 4


class TestJQLResultEdgeCases:
    """Tests for edge cases and special structures."""

    def test_empty_result(self) -> None:
        """Empty JQL result should return empty DataFrame."""
        result = JQLResult(_raw=[])

        df = result.df
        assert len(df) == 0
        assert isinstance(df, pd.DataFrame)

    def test_mixed_structure_not_detected_as_groupby(self) -> None:
        """Mixed structures should not be detected as groupBy."""
        # First element looks like groupBy, second doesn't
        result = JQLResult(
            _raw=[
                {"key": ["US"], "value": 100},
                {"country": "UK", "count": 50},  # Different structure
            ]
        )

        # Should fall back to safe wrapping, not crash
        df = result.df
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 2

    def test_mixed_structure_fallback(self) -> None:
        """Mixed structures should fall back gracefully."""
        # Sometimes JQL can return heterogeneous results
        result = JQLResult(_raw=[{"a": 1}, {"b": 2}, "string", 42])

        df = result.df
        # Should not crash and should preserve all data
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 4  # All items should be in DataFrame
        assert "value" in df.columns  # Should fall back to value column

    def test_inconsistent_value_types_raises_error(self) -> None:
        """Mixed scalar/array values should raise descriptive error."""
        # Some rows have scalar values, others have arrays
        result = JQLResult(
            _raw=[
                {"key": ["US"], "value": 100},
                {"key": ["UK"], "value": [50, 2500]},
            ]
        )

        with pytest.raises(ValueError, match="Inconsistent value types"):
            _ = result.df

    def test_deeply_nested_values(self) -> None:
        """Deeply nested values should be preserved."""
        result = JQLResult(
            _raw=[
                {
                    "key": ["US"],
                    "value": {
                        "distribution": {"event1": 10, "event2": 20},
                        "total": 30,
                    },
                }
            ]
        )

        df = result.df
        # Nested objects should be preserved (not flattened too aggressively)
        assert len(df) == 1


class TestJQLResultBackwardCompatibility:
    """Ensure improvements don't break existing behavior."""

    def test_simple_dict_list_still_works(self) -> None:
        """Original behavior for simple dict lists should be preserved."""
        result = JQLResult(
            _raw=[
                {"name": "Alice", "count": 10},
                {"name": "Bob", "count": 20},
            ]
        )

        df = result.df
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 2
        assert "name" in df.columns
        assert "count" in df.columns

    def test_simple_list_wrapping_still_works(self) -> None:
        """Original wrapping behavior for simple lists should be preserved."""
        result = JQLResult(_raw=[1, 2, 3, 4, 5])

        df = result.df
        assert "value" in df.columns
        assert len(df) == 5

    def test_df_caching_still_works(self) -> None:
        """DataFrame caching should still work after improvements."""
        result = JQLResult(_raw=[{"key": ["US"], "value": 100}])

        df1 = result.df
        df2 = result.df
        assert df1 is df2  # Same object, cached
