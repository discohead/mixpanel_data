"""Property-based tests for mixpanel_data result types using Hypothesis.

These tests verify invariants that should hold for all possible inputs,
rather than testing specific examples. This catches edge cases that
example-based tests might miss.

Usage:
    # Run with default profile (100 examples)
    pytest tests/unit/test_types_pbt.py

    # Run with dev profile (10 examples, verbose)
    HYPOTHESIS_PROFILE=dev pytest tests/unit/test_types_pbt.py

    # Run with CI profile (200 examples, deterministic)
    HYPOTHESIS_PROFILE=ci pytest tests/unit/test_types_pbt.py
"""

from __future__ import annotations

import json
from datetime import datetime

from hypothesis import given
from hypothesis import strategies as st

from mixpanel_data.types import (
    CohortInfo,
    FetchResult,
    FunnelResult,
    FunnelStep,
    JQLResult,
    RetentionResult,
    SegmentationResult,
)

# =============================================================================
# Custom Strategies
# =============================================================================

# Strategy for generating valid date strings (YYYY-MM-DD format)
date_strings = st.dates().map(lambda d: d.strftime("%Y-%m-%d"))

# Strategy for event names (non-empty printable strings)
event_names = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N", "P", "S")),
    min_size=1,
    max_size=50,
).filter(lambda s: s.strip())

# Strategy for table names (valid identifiers)
table_names = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N")),
    min_size=1,
    max_size=30,
).filter(lambda s: s and s[0].isalpha())

# Strategy for valid conversion rates (0.0 to 1.0)
conversion_rates = st.floats(min_value=0.0, max_value=1.0, allow_nan=False)

# Strategy for retention percentages (list of 0.0 to 1.0)
retention_lists = st.lists(
    st.floats(min_value=0.0, max_value=1.0, allow_nan=False),
    min_size=0,
    max_size=10,
)

# Strategy for time units
time_units = st.sampled_from(["day", "week", "month"])


# =============================================================================
# FetchResult Property Tests
# =============================================================================


class TestFetchResultProperties:
    """Property-based tests for FetchResult."""

    @given(
        table=table_names,
        rows=st.integers(min_value=0, max_value=10_000_000),
        data_type=st.sampled_from(["events", "profiles"]),
        duration=st.floats(min_value=0.0, max_value=3600.0, allow_nan=False),
    )
    def test_to_dict_always_json_serializable(
        self, table: str, rows: int, data_type: str, duration: float
    ) -> None:
        """to_dict() output should always be JSON-serializable."""
        result = FetchResult(
            table=table,
            rows=rows,
            type=data_type,  # type: ignore[arg-type]
            duration_seconds=duration,
            date_range=None,
            fetched_at=datetime.now(),
        )

        # Should not raise
        data = result.to_dict()
        json_str = json.dumps(data)
        assert isinstance(json_str, str)

    @given(
        table=table_names,
        rows=st.integers(min_value=0, max_value=1000),
    )
    def test_df_returns_dataframe_with_consistent_length(
        self, table: str, rows: int
    ) -> None:
        """df property should return DataFrame matching data length."""
        data = [{"col": i} for i in range(rows)]
        result = FetchResult(
            table=table,
            rows=rows,
            type="events",
            duration_seconds=1.0,
            date_range=None,
            fetched_at=datetime.now(),
            _data=data,
        )

        df = result.df
        assert len(df) == rows

    @given(table=table_names)
    def test_df_cached_returns_same_object(self, table: str) -> None:
        """Repeated df access should return the same cached object."""
        result = FetchResult(
            table=table,
            rows=0,
            type="events",
            duration_seconds=1.0,
            date_range=None,
            fetched_at=datetime.now(),
        )

        df1 = result.df
        df2 = result.df
        assert df1 is df2


# =============================================================================
# SegmentationResult Property Tests
# =============================================================================


class TestSegmentationResultProperties:
    """Property-based tests for SegmentationResult."""

    @given(
        event=event_names,
        from_date=date_strings,
        to_date=date_strings,
        unit=time_units,
        total=st.integers(min_value=0, max_value=10_000_000),
    )
    def test_to_dict_always_json_serializable(
        self, event: str, from_date: str, to_date: str, unit: str, total: int
    ) -> None:
        """to_dict() output should always be JSON-serializable."""
        result = SegmentationResult(
            event=event,
            from_date=from_date,
            to_date=to_date,
            unit=unit,  # type: ignore[arg-type]
            segment_property=None,
            total=total,
            series={},
        )

        data = result.to_dict()
        json_str = json.dumps(data)
        assert isinstance(json_str, str)

    @given(
        event=event_names,
        segments=st.dictionaries(
            keys=st.text(min_size=1, max_size=20),
            values=st.dictionaries(
                keys=date_strings,
                values=st.integers(min_value=0, max_value=10000),
                min_size=0,
                max_size=5,
            ),
            min_size=0,
            max_size=5,
        ),
    )
    def test_df_row_count_matches_series_structure(
        self, event: str, segments: dict[str, dict[str, int]]
    ) -> None:
        """DataFrame row count should equal sum of all date entries."""
        result = SegmentationResult(
            event=event,
            from_date="2024-01-01",
            to_date="2024-01-31",
            unit="day",
            segment_property=None,
            total=0,
            series=segments,
        )

        expected_rows = sum(len(dates) for dates in segments.values())
        assert len(result.df) == expected_rows

    @given(event=event_names)
    def test_df_has_required_columns(self, event: str) -> None:
        """DataFrame should always have date, segment, count columns."""
        result = SegmentationResult(
            event=event,
            from_date="2024-01-01",
            to_date="2024-01-31",
            unit="day",
            segment_property=None,
            total=0,
            series={},
        )

        df = result.df
        assert "date" in df.columns
        assert "segment" in df.columns
        assert "count" in df.columns


# =============================================================================
# FunnelResult Property Tests
# =============================================================================


class TestFunnelResultProperties:
    """Property-based tests for FunnelResult."""

    @given(
        funnel_id=st.integers(min_value=1, max_value=10_000_000),
        funnel_name=st.text(min_size=1, max_size=100),
        conversion_rate=conversion_rates,
        step_count=st.integers(min_value=0, max_value=10),
    )
    def test_to_dict_always_json_serializable(
        self, funnel_id: int, funnel_name: str, conversion_rate: float, step_count: int
    ) -> None:
        """to_dict() output should always be JSON-serializable."""
        steps = [
            FunnelStep(
                event=f"Step {i}",
                count=1000 - i * 100,
                conversion_rate=1.0 - i * 0.1,
            )
            for i in range(step_count)
        ]

        result = FunnelResult(
            funnel_id=funnel_id,
            funnel_name=funnel_name,
            from_date="2024-01-01",
            to_date="2024-01-31",
            conversion_rate=conversion_rate,
            steps=steps,
        )

        data = result.to_dict()
        json_str = json.dumps(data)
        assert isinstance(json_str, str)
        assert len(data["steps"]) == step_count

    @given(step_count=st.integers(min_value=0, max_value=20))
    def test_df_row_count_matches_steps(self, step_count: int) -> None:
        """DataFrame should have one row per funnel step."""
        steps = [
            FunnelStep(event=f"Step {i}", count=100, conversion_rate=0.5)
            for i in range(step_count)
        ]

        result = FunnelResult(
            funnel_id=1,
            funnel_name="Test",
            from_date="2024-01-01",
            to_date="2024-01-31",
            conversion_rate=0.5,
            steps=steps,
        )

        assert len(result.df) == step_count


# =============================================================================
# RetentionResult Property Tests
# =============================================================================


class TestRetentionResultProperties:
    """Property-based tests for RetentionResult."""

    @given(
        born_event=event_names,
        return_event=event_names,
        unit=time_units,
        cohort_count=st.integers(min_value=0, max_value=10),
    )
    def test_to_dict_always_json_serializable(
        self, born_event: str, return_event: str, unit: str, cohort_count: int
    ) -> None:
        """to_dict() output should always be JSON-serializable."""
        cohorts = [
            CohortInfo(
                date=f"2024-01-{i + 1:02d}",
                size=1000 - i * 100,
                retention=[1.0, 0.5, 0.3],
            )
            for i in range(cohort_count)
        ]

        result = RetentionResult(
            born_event=born_event,
            return_event=return_event,
            from_date="2024-01-01",
            to_date="2024-01-31",
            unit=unit,  # type: ignore[arg-type]
            cohorts=cohorts,
        )

        data = result.to_dict()
        json_str = json.dumps(data)
        assert isinstance(json_str, str)

    @given(
        retention=retention_lists,
    )
    def test_cohort_retention_preserved(self, retention: list[float]) -> None:
        """Retention percentages should be preserved through serialization."""
        cohort = CohortInfo(
            date="2024-01-01",
            size=1000,
            retention=retention,
        )

        data = cohort.to_dict()
        assert data["retention"] == retention


# =============================================================================
# JQLResult Property Tests
# =============================================================================


class TestJQLResultProperties:
    """Property-based tests for JQLResult."""

    @given(
        raw_data=st.lists(
            st.dictionaries(
                keys=st.text(min_size=1, max_size=20),
                values=st.one_of(
                    st.integers(),
                    st.floats(allow_nan=False, allow_infinity=False),
                    st.text(max_size=50),
                    st.booleans(),
                    st.none(),
                ),
                min_size=0,
                max_size=5,
            ),
            min_size=0,
            max_size=20,
        )
    )
    def test_to_dict_always_json_serializable(
        self, raw_data: list[dict[str, object]]
    ) -> None:
        """to_dict() output should always be JSON-serializable."""
        result = JQLResult(_raw=raw_data)

        data = result.to_dict()
        json_str = json.dumps(data)
        assert isinstance(json_str, str)
        assert data["row_count"] == len(raw_data)

    @given(
        values=st.lists(st.integers(), min_size=0, max_size=50),
    )
    def test_df_wraps_simple_lists_in_value_column(self, values: list[int]) -> None:
        """Simple lists should be wrapped in 'value' column."""
        result = JQLResult(_raw=values)

        if values:
            df = result.df
            assert "value" in df.columns
            assert len(df) == len(values)

    @given(
        raw_data=st.lists(
            st.dictionaries(
                keys=st.text(min_size=1, max_size=10),
                values=st.integers(),
                min_size=1,
                max_size=3,
            ),
            min_size=1,
            max_size=10,
        )
    )
    def test_df_preserves_dict_structure(self, raw_data: list[dict[str, int]]) -> None:
        """Dict lists should become DataFrame columns."""
        result = JQLResult(_raw=raw_data)

        df = result.df
        assert len(df) == len(raw_data)

        # All keys from first dict should be columns
        for key in raw_data[0]:
            assert key in df.columns


# =============================================================================
# Cross-Type Invariant Tests
# =============================================================================


class TestCrossTypeInvariants:
    """Tests for properties that should hold across all result types."""

    @given(st.integers(min_value=0, max_value=100))
    def test_all_types_support_empty_data(self, _seed: int) -> None:
        """All result types should handle empty data gracefully."""
        # Create instances with empty/minimal data
        fetch = FetchResult(
            table="t",
            rows=0,
            type="events",
            duration_seconds=0,
            date_range=None,
            fetched_at=datetime.now(),
        )
        seg = SegmentationResult(
            event="e",
            from_date="2024-01-01",
            to_date="2024-01-31",
            unit="day",
            segment_property=None,
            total=0,
            series={},
        )
        funnel = FunnelResult(
            funnel_id=1,
            funnel_name="f",
            from_date="2024-01-01",
            to_date="2024-01-31",
            conversion_rate=0,
            steps=[],
        )
        retention = RetentionResult(
            born_event="b",
            return_event="r",
            from_date="2024-01-01",
            to_date="2024-01-31",
            unit="day",
            cohorts=[],
        )
        jql = JQLResult()

        # All should produce valid to_dict output
        all_results = [fetch, seg, funnel, retention, jql]
        for r in all_results:
            data = r.to_dict()  # type: ignore[attr-defined]
            json.dumps(data)  # Should not raise

        # All should produce valid DataFrames
        for r in all_results:
            df = r.df  # type: ignore[attr-defined]
            assert df is not None
            assert len(df) >= 0
