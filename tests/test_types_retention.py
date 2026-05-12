"""Unit tests for retention query types.

Tests cover:
    T004: RetentionEvent — construction, defaults, immutability, field preservation,
          filters handling.
    T005: RetentionQueryResult — construction, defaults, immutability, .df columns/
          shape/caching, .average field, .to_dict(), empty cohorts edge case.
    T006: RetentionMathType — valid values accepted, invalid rejected at
          validation layer.
"""

from __future__ import annotations

from typing import Any

import pytest

from mixpanel_headless.types import Filter, RetentionEvent, RetentionQueryResult

# =============================================================================
# T004: RetentionEvent
# =============================================================================


class TestRetentionEventConstruction:
    """Tests for RetentionEvent construction and defaults."""

    def test_construct_with_event_only(self) -> None:
        """RetentionEvent with just an event name uses correct defaults."""
        e = RetentionEvent("Signup")
        assert e.event == "Signup"
        assert e.filters is None
        assert e.filters_combinator == "all"

    def test_construct_with_all_fields(self) -> None:
        """RetentionEvent with all fields preserves them."""
        f = Filter.equals("country", "US")
        e = RetentionEvent("Signup", filters=[f], filters_combinator="any")
        assert e.event == "Signup"
        assert e.filters is not None
        assert len(e.filters) == 1
        assert e.filters_combinator == "any"

    def test_default_filters_is_none(self) -> None:
        """Default filters is None, not an empty list."""
        e = RetentionEvent("Login")
        assert e.filters is None

    def test_default_filters_combinator_is_all(self) -> None:
        """Default filters_combinator is 'all'."""
        e = RetentionEvent("Login")
        assert e.filters_combinator == "all"

    def test_event_field_preserved(self) -> None:
        """Event name is preserved exactly as given."""
        e = RetentionEvent("My Custom Event 🎉")
        assert e.event == "My Custom Event 🎉"

    def test_filters_list_preserved(self) -> None:
        """Filters list contents are preserved."""
        f1 = Filter.equals("country", "US")
        f2 = Filter.equals("platform", "iOS")
        e = RetentionEvent("Signup", filters=[f1, f2])
        assert e.filters is not None
        assert len(e.filters) == 2


class TestRetentionEventImmutability:
    """Tests for RetentionEvent frozen dataclass immutability."""

    def test_cannot_set_event(self) -> None:
        """Setting event on a frozen instance must raise."""
        e = RetentionEvent("Signup")
        with pytest.raises(AttributeError):
            e.event = "Login"  # type: ignore[misc]

    def test_cannot_set_filters(self) -> None:
        """Setting filters on a frozen instance must raise."""
        e = RetentionEvent("Signup")
        with pytest.raises(AttributeError):
            e.filters = []  # type: ignore[misc]

    def test_cannot_set_filters_combinator(self) -> None:
        """Setting filters_combinator on a frozen instance must raise."""
        e = RetentionEvent("Signup")
        with pytest.raises(AttributeError):
            e.filters_combinator = "any"  # type: ignore[misc]


# =============================================================================
# T005: RetentionQueryResult
# =============================================================================


def _make_result(**overrides: Any) -> RetentionQueryResult:
    """Build a default-valid RetentionQueryResult for testing.

    Args:
        **overrides: Field overrides.

    Returns:
        RetentionQueryResult instance.
    """
    defaults: dict[str, Any] = {
        "computed_at": "2025-01-15T12:00:00",
        "from_date": "2025-01-01",
        "to_date": "2025-01-31",
        "cohorts": {
            "2025-01-01": {
                "first": 100,
                "counts": [100, 50, 25],
                "rates": [1.0, 0.5, 0.25],
            },
            "2025-01-02": {
                "first": 80,
                "counts": [80, 40, 20],
                "rates": [1.0, 0.5, 0.25],
            },
        },
        "average": {"first": 90, "counts": [90, 45, 22], "rates": [1.0, 0.5, 0.244]},
        "params": {"sections": {}, "displayOptions": {}},
        "meta": {"sampling_factor": 1.0},
    }
    defaults.update(overrides)
    return RetentionQueryResult(**defaults)


class TestRetentionQueryResultConstruction:
    """Tests for RetentionQueryResult construction and defaults."""

    def test_construct_with_all_fields(self) -> None:
        """All fields are preserved after construction."""
        r = _make_result()
        assert r.computed_at == "2025-01-15T12:00:00"
        assert r.from_date == "2025-01-01"
        assert r.to_date == "2025-01-31"
        assert len(r.cohorts) == 2
        assert r.average["first"] == 90
        assert "sections" in r.params
        assert r.meta["sampling_factor"] == 1.0

    def test_default_cohorts_is_empty_dict(self) -> None:
        """Default cohorts is an empty dict."""
        r = RetentionQueryResult(
            computed_at="",
            from_date="",
            to_date="",
        )
        assert r.cohorts == {}

    def test_default_average_is_empty_dict(self) -> None:
        """Default average is an empty dict."""
        r = RetentionQueryResult(
            computed_at="",
            from_date="",
            to_date="",
        )
        assert r.average == {}

    def test_default_params_is_empty_dict(self) -> None:
        """Default params is an empty dict."""
        r = RetentionQueryResult(
            computed_at="",
            from_date="",
            to_date="",
        )
        assert r.params == {}

    def test_default_meta_is_empty_dict(self) -> None:
        """Default meta is an empty dict."""
        r = RetentionQueryResult(
            computed_at="",
            from_date="",
            to_date="",
        )
        assert r.meta == {}


class TestRetentionQueryResultImmutability:
    """Tests for RetentionQueryResult frozen dataclass immutability."""

    def test_cannot_set_computed_at(self) -> None:
        """Setting computed_at on a frozen instance must raise."""
        r = _make_result()
        with pytest.raises(AttributeError):
            r.computed_at = "new"  # type: ignore[misc]

    def test_cannot_set_cohorts(self) -> None:
        """Setting cohorts on a frozen instance must raise."""
        r = _make_result()
        with pytest.raises(AttributeError):
            r.cohorts = {}  # type: ignore[misc]


class TestRetentionQueryResultDataFrame:
    """Tests for RetentionQueryResult.df property."""

    def test_df_columns(self) -> None:
        """DataFrame must have columns: cohort_date, bucket, count, rate."""
        r = _make_result()
        df = r.df
        assert list(df.columns) == ["cohort_date", "bucket", "count", "rate"]

    def test_df_shape(self) -> None:
        """DataFrame row count = sum of bucket counts across cohorts."""
        r = _make_result()
        df = r.df
        # 2 cohorts × 3 buckets each = 6 rows
        assert len(df) == 6

    def test_df_caching(self) -> None:
        """Accessing .df twice returns the same DataFrame object."""
        r = _make_result()
        df1 = r.df
        df2 = r.df
        assert df1 is df2

    def test_df_values_correct(self) -> None:
        """DataFrame values match the cohort data."""
        r = _make_result()
        df = r.df
        # First cohort, bucket 0
        row = df[(df["cohort_date"] == "2025-01-01") & (df["bucket"] == 0)]
        assert len(row) == 1
        assert row.iloc[0]["count"] == 100
        assert row.iloc[0]["rate"] == 1.0

    def test_df_bucket_indices(self) -> None:
        """Buckets are 0-indexed integers."""
        r = _make_result()
        df = r.df
        buckets = sorted(df["bucket"].unique())
        assert buckets == [0, 1, 2]

    def test_empty_cohorts_produces_empty_df(self) -> None:
        """Empty cohorts dict produces an empty DataFrame with correct columns."""
        r = _make_result(cohorts={})
        df = r.df
        assert len(df) == 0
        assert list(df.columns) == ["cohort_date", "bucket", "count", "rate"]

    def test_rates_shorter_than_counts_uses_zero(self) -> None:
        """When rates has fewer entries than counts, missing rates default to 0.0."""
        r = _make_result(
            cohorts={
                "2025-01-01": {
                    "first": 100,
                    "counts": [100, 50, 25],
                    "rates": [1.0],  # Only 1 rate for 3 counts
                },
            }
        )
        df = r.df
        assert len(df) == 3
        # First bucket has the rate
        assert df.iloc[0]["rate"] == 1.0
        # Remaining buckets fall back to 0.0
        assert df.iloc[1]["rate"] == 0.0
        assert df.iloc[2]["rate"] == 0.0

    def test_rates_empty_all_default_to_zero(self) -> None:
        """When rates is empty, all rate values default to 0.0."""
        r = _make_result(
            cohorts={
                "2025-01-01": {
                    "first": 50,
                    "counts": [50, 25],
                    "rates": [],
                },
            }
        )
        df = r.df
        assert len(df) == 2
        assert df.iloc[0]["rate"] == 0.0
        assert df.iloc[1]["rate"] == 0.0


class TestRetentionQueryResultDataFrameSegmented:
    """Tests for RetentionQueryResult.df with segmented data."""

    def test_df_with_segments_has_segment_column(self) -> None:
        """When segments populated, df has 5 columns including segment."""
        r = _make_result(
            segments={
                "iOS": {
                    "2025-01-01": {
                        "first": 60,
                        "counts": [60, 30],
                        "rates": [1.0, 0.5],
                    },
                },
                "Android": {
                    "2025-01-01": {
                        "first": 40,
                        "counts": [40, 20],
                        "rates": [1.0, 0.5],
                    },
                },
            }
        )
        df = r.df
        assert list(df.columns) == ["segment", "cohort_date", "bucket", "count", "rate"]

    def test_df_with_segments_row_count(self) -> None:
        """Segmented df has correct number of rows."""
        r = _make_result(
            segments={
                "iOS": {
                    "2025-01-01": {
                        "first": 60,
                        "counts": [60, 30],
                        "rates": [1.0, 0.5],
                    },
                },
                "Android": {
                    "2025-01-01": {
                        "first": 40,
                        "counts": [40, 20],
                        "rates": [1.0, 0.5],
                    },
                },
            }
        )
        df = r.df
        # 2 segments × 1 cohort × 2 buckets = 4 rows
        assert len(df) == 4

    def test_df_with_segments_values_correct(self) -> None:
        """Segmented df values match segment cohort data."""
        r = _make_result(
            segments={
                "iOS": {
                    "2025-01-01": {
                        "first": 60,
                        "counts": [60, 30],
                        "rates": [1.0, 0.5],
                    },
                },
            }
        )
        df = r.df
        row = df[(df["segment"] == "iOS") & (df["bucket"] == 0)]
        assert len(row) == 1
        assert row.iloc[0]["count"] == 60
        assert row.iloc[0]["rate"] == 1.0

    def test_df_without_segments_no_segment_column(self) -> None:
        """Without segments, df has 4 columns (backward compat)."""
        r = _make_result()
        df = r.df
        assert list(df.columns) == ["cohort_date", "bucket", "count", "rate"]


class TestRetentionQueryResultToDict:
    """Tests for RetentionQueryResult.to_dict() serialization."""

    def test_to_dict_returns_dict(self) -> None:
        """to_dict() returns a plain dict."""
        r = _make_result()
        d = r.to_dict()
        assert isinstance(d, dict)

    def test_to_dict_contains_all_fields(self) -> None:
        """to_dict() includes all public fields."""
        r = _make_result()
        d = r.to_dict()
        assert "computed_at" in d
        assert "from_date" in d
        assert "to_date" in d
        assert "cohorts" in d
        assert "average" in d
        assert "params" in d
        assert "meta" in d

    def test_to_dict_includes_segments_when_present(self) -> None:
        """to_dict() includes segments and segment_averages when non-empty."""
        r = _make_result(
            segments={
                "iOS": {
                    "2025-01-01": {
                        "first": 60,
                        "counts": [60, 30],
                        "rates": [1.0, 0.5],
                    },
                },
            },
            segment_averages={
                "iOS": {"first": 60, "counts": [60, 30], "rates": [1.0, 0.5]},
            },
        )
        d = r.to_dict()
        assert "segments" in d
        assert "segment_averages" in d
        assert d["segments"]["iOS"]["2025-01-01"]["first"] == 60

    def test_to_dict_excludes_segments_when_empty(self) -> None:
        """to_dict() omits segments and segment_averages when empty."""
        r = _make_result()
        d = r.to_dict()
        assert "segments" not in d
        assert "segment_averages" not in d


class TestRetentionQueryResultAverage:
    """Tests for RetentionQueryResult.average field."""

    def test_average_is_preserved(self) -> None:
        """Average dict is preserved as-is."""
        avg = {"first": 90, "counts": [90, 45], "rates": [1.0, 0.5]}
        r = _make_result(average=avg)
        assert r.average == avg

    def test_average_empty_dict_when_no_data(self) -> None:
        """Average defaults to empty dict."""
        r = RetentionQueryResult(
            computed_at="",
            from_date="",
            to_date="",
        )
        assert r.average == {}


# =============================================================================
# T006: RetentionMathType
# =============================================================================


class TestRetentionMathType:
    """Tests for RetentionMathType type alias validation.

    RetentionMathType is a Literal type alias, so validation happens
    at the validation layer (validate_retention_args), not at construction.
    These tests verify the enum constants that back the type.
    """

    def test_valid_values_in_enum(self) -> None:
        """VALID_MATH_RETENTION contains retention_rate and unique."""
        from mixpanel_headless._internal.bookmark_enums import VALID_MATH_RETENTION

        assert "retention_rate" in VALID_MATH_RETENTION
        assert "unique" in VALID_MATH_RETENTION

    def test_insights_math_not_in_retention(self) -> None:
        """Insights-only math types are not in VALID_MATH_RETENTION."""
        from mixpanel_headless._internal.bookmark_enums import VALID_MATH_RETENTION

        assert "dau" not in VALID_MATH_RETENTION
        assert "wau" not in VALID_MATH_RETENTION
        assert "mau" not in VALID_MATH_RETENTION
        assert "histogram" not in VALID_MATH_RETENTION

    def test_retention_math_is_subset_of_all_math(self) -> None:
        """VALID_MATH_RETENTION must be a subset of VALID_MATH_TYPES."""
        from mixpanel_headless._internal.bookmark_enums import (
            VALID_MATH_RETENTION,
            VALID_MATH_TYPES,
        )

        assert VALID_MATH_RETENTION.issubset(VALID_MATH_TYPES)
