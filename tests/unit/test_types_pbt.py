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
    ActivityFeedResult,
    BookmarkInfo,
    CohortInfo,
    ColumnStatsResult,
    ColumnSummary,
    EventBreakdownResult,
    EventCountsResult,
    EventStats,
    FetchResult,
    FlowsResult,
    FrequencyResult,
    FunnelInfo,
    FunnelResult,
    FunnelStep,
    JQLResult,
    NumericAverageResult,
    NumericBucketResult,
    NumericSumResult,
    PropertyCountsResult,
    RetentionResult,
    SavedCohort,
    SavedReportResult,
    SegmentationResult,
    SQLResult,
    SummaryResult,
    TopEvent,
    UserEvent,
)

# =============================================================================
# Custom Strategies
# =============================================================================

# Strategy for generating valid date strings (YYYY-MM-DD format)
date_strings = st.dates().map(lambda d: d.strftime("%Y-%m-%d"))

# Strategy for event names (non-empty printable strings)
event_names = st.text(
    alphabet=st.characters(categories=("L", "N", "P", "S")),
    min_size=1,
    max_size=50,
).filter(lambda s: s.strip())

# Strategy for table names (valid identifiers)
table_names = st.text(
    alphabet=st.characters(categories=("L", "N")),
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

# Strategy for datetime values (deterministic for reproducibility)
datetimes = st.datetimes(
    min_value=datetime(2020, 1, 1),
    max_value=datetime(2030, 12, 31),
)


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
        fetched_at=datetimes,
    )
    def test_to_dict_always_json_serializable(
        self,
        table: str,
        rows: int,
        data_type: str,
        duration: float,
        fetched_at: datetime,
    ) -> None:
        """to_dict() output should always be JSON-serializable."""
        result = FetchResult(
            table=table,
            rows=rows,
            type=data_type,  # type: ignore[arg-type]
            duration_seconds=duration,
            date_range=None,
            fetched_at=fetched_at,
        )

        # Should not raise
        data = result.to_dict()
        json_str = json.dumps(data)
        assert isinstance(json_str, str)

    @given(
        table=table_names,
        rows=st.integers(min_value=0, max_value=1000),
        fetched_at=datetimes,
    )
    def test_df_returns_dataframe_with_consistent_length(
        self, table: str, rows: int, fetched_at: datetime
    ) -> None:
        """df property should return DataFrame matching data length."""
        data = [{"col": i} for i in range(rows)]
        result = FetchResult(
            table=table,
            rows=rows,
            type="events",
            duration_seconds=1.0,
            date_range=None,
            fetched_at=fetched_at,
            _data=data,
        )

        df = result.df
        assert len(df) == rows

    @given(table=table_names, fetched_at=datetimes)
    def test_df_cached_returns_same_object(
        self, table: str, fetched_at: datetime
    ) -> None:
        """Repeated df access should return the same cached object."""
        result = FetchResult(
            table=table,
            rows=0,
            type="events",
            duration_seconds=1.0,
            date_range=None,
            fetched_at=fetched_at,
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
                count=max(0, 1000 - i * 100),
                conversion_rate=max(0.0, 1.0 - i * 0.1),
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

    def test_all_types_support_empty_data(self) -> None:
        """All result types should handle empty data gracefully.

        Note: This is a regular unit test, not property-based, because empty data
        is a fixed scenario that doesn't benefit from randomized inputs.
        """
        # Create instances with empty/minimal data
        fetch = FetchResult(
            table="t",
            rows=0,
            type="events",
            duration_seconds=0,
            date_range=None,
            fetched_at=datetime(2024, 1, 1),
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


# =============================================================================
# EventCountsResult Property Tests
# =============================================================================


class TestEventCountsResultProperties:
    """Property-based tests for EventCountsResult."""

    @given(
        events=st.lists(event_names, min_size=1, max_size=5),
        from_date=date_strings,
        to_date=date_strings,
        unit=time_units,
        count_type=st.sampled_from(["general", "unique", "average"]),
    )
    def test_to_dict_always_json_serializable(
        self,
        events: list[str],
        from_date: str,
        to_date: str,
        unit: str,
        count_type: str,
    ) -> None:
        """to_dict() output should always be JSON-serializable."""
        result = EventCountsResult(
            events=events,
            from_date=from_date,
            to_date=to_date,
            unit=unit,  # type: ignore[arg-type]
            type=count_type,  # type: ignore[arg-type]
            series={},
        )

        data = result.to_dict()
        json_str = json.dumps(data)
        assert isinstance(json_str, str)

    @given(
        series=st.dictionaries(
            keys=event_names,
            values=st.dictionaries(
                keys=date_strings,
                values=st.integers(min_value=0, max_value=10000),
                min_size=0,
                max_size=5,
            ),
            min_size=0,
            max_size=3,
        ),
    )
    def test_df_row_count_matches_series_structure(
        self, series: dict[str, dict[str, int]]
    ) -> None:
        """DataFrame row count should equal sum of all date entries."""
        result = EventCountsResult(
            events=list(series.keys()),
            from_date="2024-01-01",
            to_date="2024-01-31",
            unit="day",
            type="general",
            series=series,
        )

        expected_rows = sum(len(dates) for dates in series.values())
        assert len(result.df) == expected_rows

    @given(events=st.lists(event_names, min_size=1, max_size=3))
    def test_df_has_required_columns(self, events: list[str]) -> None:
        """DataFrame should always have date, event, count columns."""
        result = EventCountsResult(
            events=events,
            from_date="2024-01-01",
            to_date="2024-01-31",
            unit="day",
            type="general",
            series={},
        )

        df = result.df
        assert "date" in df.columns
        assert "event" in df.columns
        assert "count" in df.columns


# =============================================================================
# PropertyCountsResult Property Tests
# =============================================================================


class TestPropertyCountsResultProperties:
    """Property-based tests for PropertyCountsResult."""

    @given(
        event=event_names,
        property_name=st.text(min_size=1, max_size=30),
        from_date=date_strings,
        to_date=date_strings,
        unit=time_units,
        count_type=st.sampled_from(["general", "unique", "average"]),
    )
    def test_to_dict_always_json_serializable(
        self,
        event: str,
        property_name: str,
        from_date: str,
        to_date: str,
        unit: str,
        count_type: str,
    ) -> None:
        """to_dict() output should always be JSON-serializable."""
        result = PropertyCountsResult(
            event=event,
            property_name=property_name,
            from_date=from_date,
            to_date=to_date,
            unit=unit,  # type: ignore[arg-type]
            type=count_type,  # type: ignore[arg-type]
            series={},
        )

        data = result.to_dict()
        json_str = json.dumps(data)
        assert isinstance(json_str, str)

    @given(
        series=st.dictionaries(
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
        self, series: dict[str, dict[str, int]]
    ) -> None:
        """DataFrame row count should equal sum of all date entries."""
        result = PropertyCountsResult(
            event="test_event",
            property_name="test_property",
            from_date="2024-01-01",
            to_date="2024-01-31",
            unit="day",
            type="general",
            series=series,
        )

        expected_rows = sum(len(dates) for dates in series.values())
        assert len(result.df) == expected_rows


# =============================================================================
# NumericBucketResult Property Tests
# =============================================================================


class TestNumericBucketResultProperties:
    """Property-based tests for NumericBucketResult."""

    @given(
        event=event_names,
        from_date=date_strings,
        to_date=date_strings,
        property_expr=st.text(min_size=1, max_size=50),
        unit=st.sampled_from(["hour", "day"]),
    )
    def test_to_dict_always_json_serializable(
        self, event: str, from_date: str, to_date: str, property_expr: str, unit: str
    ) -> None:
        """to_dict() output should always be JSON-serializable."""
        result = NumericBucketResult(
            event=event,
            from_date=from_date,
            to_date=to_date,
            property_expr=property_expr,
            unit=unit,  # type: ignore[arg-type]
            series={},
        )

        data = result.to_dict()
        json_str = json.dumps(data)
        assert isinstance(json_str, str)

    @given(
        series=st.dictionaries(
            keys=st.text(min_size=1, max_size=20),  # bucket ranges like "0-10"
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
        self, series: dict[str, dict[str, int]]
    ) -> None:
        """DataFrame row count should equal sum of all date entries."""
        result = NumericBucketResult(
            event="test_event",
            from_date="2024-01-01",
            to_date="2024-01-31",
            property_expr="properties.amount",
            unit="day",
            series=series,
        )

        expected_rows = sum(len(dates) for dates in series.values())
        assert len(result.df) == expected_rows

    def test_df_has_required_columns(self) -> None:
        """DataFrame should always have date, bucket, count columns."""
        result = NumericBucketResult(
            event="test_event",
            from_date="2024-01-01",
            to_date="2024-01-31",
            property_expr="properties.amount",
            unit="day",
            series={},
        )

        df = result.df
        assert "date" in df.columns
        assert "bucket" in df.columns
        assert "count" in df.columns


# =============================================================================
# NumericSumResult Property Tests
# =============================================================================


class TestNumericSumResultProperties:
    """Property-based tests for NumericSumResult."""

    @given(
        event=event_names,
        from_date=date_strings,
        to_date=date_strings,
        property_expr=st.text(min_size=1, max_size=50),
        unit=st.sampled_from(["hour", "day"]),
        results=st.dictionaries(
            keys=date_strings,
            values=st.floats(min_value=-1e6, max_value=1e6, allow_nan=False),
            min_size=0,
            max_size=10,
        ),
    )
    def test_to_dict_always_json_serializable(
        self,
        event: str,
        from_date: str,
        to_date: str,
        property_expr: str,
        unit: str,
        results: dict[str, float],
    ) -> None:
        """to_dict() output should always be JSON-serializable."""
        result = NumericSumResult(
            event=event,
            from_date=from_date,
            to_date=to_date,
            property_expr=property_expr,
            unit=unit,  # type: ignore[arg-type]
            results=results,
        )

        data = result.to_dict()
        json_str = json.dumps(data)
        assert isinstance(json_str, str)

    @given(
        results=st.dictionaries(
            keys=date_strings,
            values=st.floats(min_value=-1e6, max_value=1e6, allow_nan=False),
            min_size=0,
            max_size=10,
        ),
    )
    def test_df_row_count_matches_results(self, results: dict[str, float]) -> None:
        """DataFrame row count should equal number of date entries."""
        result = NumericSumResult(
            event="test_event",
            from_date="2024-01-01",
            to_date="2024-01-31",
            property_expr="properties.amount",
            unit="day",
            results=results,
        )

        assert len(result.df) == len(results)

    def test_df_has_required_columns(self) -> None:
        """DataFrame should always have date, sum columns."""
        result = NumericSumResult(
            event="test_event",
            from_date="2024-01-01",
            to_date="2024-01-31",
            property_expr="properties.amount",
            unit="day",
            results={},
        )

        df = result.df
        assert "date" in df.columns
        assert "sum" in df.columns


# =============================================================================
# NumericAverageResult Property Tests
# =============================================================================


class TestNumericAverageResultProperties:
    """Property-based tests for NumericAverageResult."""

    @given(
        event=event_names,
        from_date=date_strings,
        to_date=date_strings,
        property_expr=st.text(min_size=1, max_size=50),
        unit=st.sampled_from(["hour", "day"]),
        results=st.dictionaries(
            keys=date_strings,
            values=st.floats(min_value=-1e6, max_value=1e6, allow_nan=False),
            min_size=0,
            max_size=10,
        ),
    )
    def test_to_dict_always_json_serializable(
        self,
        event: str,
        from_date: str,
        to_date: str,
        property_expr: str,
        unit: str,
        results: dict[str, float],
    ) -> None:
        """to_dict() output should always be JSON-serializable."""
        result = NumericAverageResult(
            event=event,
            from_date=from_date,
            to_date=to_date,
            property_expr=property_expr,
            unit=unit,  # type: ignore[arg-type]
            results=results,
        )

        data = result.to_dict()
        json_str = json.dumps(data)
        assert isinstance(json_str, str)

    @given(
        results=st.dictionaries(
            keys=date_strings,
            values=st.floats(min_value=-1e6, max_value=1e6, allow_nan=False),
            min_size=0,
            max_size=10,
        ),
    )
    def test_df_row_count_matches_results(self, results: dict[str, float]) -> None:
        """DataFrame row count should equal number of date entries."""
        result = NumericAverageResult(
            event="test_event",
            from_date="2024-01-01",
            to_date="2024-01-31",
            property_expr="properties.amount",
            unit="day",
            results=results,
        )

        assert len(result.df) == len(results)

    def test_df_has_required_columns(self) -> None:
        """DataFrame should always have date, average columns."""
        result = NumericAverageResult(
            event="test_event",
            from_date="2024-01-01",
            to_date="2024-01-31",
            property_expr="properties.amount",
            unit="day",
            results={},
        )

        df = result.df
        assert "date" in df.columns
        assert "average" in df.columns


# =============================================================================
# FrequencyResult Property Tests
# =============================================================================


class TestFrequencyResultProperties:
    """Property-based tests for FrequencyResult."""

    @given(
        event=st.one_of(st.none(), event_names),
        from_date=date_strings,
        to_date=date_strings,
        unit=time_units,
        addiction_unit=st.sampled_from(["hour", "day"]),
    )
    def test_to_dict_always_json_serializable(
        self,
        event: str | None,
        from_date: str,
        to_date: str,
        unit: str,
        addiction_unit: str,
    ) -> None:
        """to_dict() output should always be JSON-serializable."""
        result = FrequencyResult(
            event=event,
            from_date=from_date,
            to_date=to_date,
            unit=unit,  # type: ignore[arg-type]
            addiction_unit=addiction_unit,  # type: ignore[arg-type]
            data={},
        )

        data = result.to_dict()
        json_str = json.dumps(data)
        assert isinstance(json_str, str)

    @given(
        data=st.dictionaries(
            keys=date_strings,
            values=st.lists(
                st.integers(min_value=0, max_value=1000), min_size=1, max_size=10
            ),
            min_size=0,
            max_size=5,
        ),
    )
    def test_df_row_count_matches_data(self, data: dict[str, list[int]]) -> None:
        """DataFrame row count should equal number of date entries."""
        result = FrequencyResult(
            event="test_event",
            from_date="2024-01-01",
            to_date="2024-01-31",
            unit="day",
            addiction_unit="hour",
            data=data,
        )

        assert len(result.df) == len(data)


# =============================================================================
# ActivityFeedResult Property Tests
# =============================================================================


class TestActivityFeedResultProperties:
    """Property-based tests for ActivityFeedResult."""

    @given(
        distinct_ids=st.lists(st.text(min_size=1, max_size=20), min_size=1, max_size=5),
        from_date=st.one_of(st.none(), date_strings),
        to_date=st.one_of(st.none(), date_strings),
        event_count=st.integers(min_value=0, max_value=10),
        event_time=datetimes,
    )
    def test_to_dict_always_json_serializable(
        self,
        distinct_ids: list[str],
        from_date: str | None,
        to_date: str | None,
        event_count: int,
        event_time: datetime,
    ) -> None:
        """to_dict() output should always be JSON-serializable."""
        events = [
            UserEvent(
                event=f"Event_{i}",
                time=event_time,
                properties={"$distinct_id": distinct_ids[0]},
            )
            for i in range(event_count)
        ]

        result = ActivityFeedResult(
            distinct_ids=distinct_ids,
            from_date=from_date,
            to_date=to_date,
            events=events,
        )

        data = result.to_dict()
        json_str = json.dumps(data)
        assert isinstance(json_str, str)
        assert data["event_count"] == event_count

    @given(event_count=st.integers(min_value=0, max_value=20), event_time=datetimes)
    def test_df_row_count_matches_events(
        self, event_count: int, event_time: datetime
    ) -> None:
        """DataFrame row count should equal number of events."""
        events = [
            UserEvent(
                event=f"Event_{i}",
                time=event_time,
                properties={"$distinct_id": "user_1"},
            )
            for i in range(event_count)
        ]

        result = ActivityFeedResult(
            distinct_ids=["user_1"],
            from_date=None,
            to_date=None,
            events=events,
        )

        assert len(result.df) == event_count


# =============================================================================
# SavedReportResult Property Tests
# =============================================================================


class TestSavedReportResultProperties:
    """Property-based tests for SavedReportResult."""

    @given(
        bookmark_id=st.integers(min_value=1, max_value=10_000_000),
        computed_at=st.text(min_size=1, max_size=30),
        from_date=date_strings,
        to_date=date_strings,
    )
    def test_to_dict_always_json_serializable(
        self, bookmark_id: int, computed_at: str, from_date: str, to_date: str
    ) -> None:
        """to_dict() output should always be JSON-serializable."""
        result = SavedReportResult(
            bookmark_id=bookmark_id,
            computed_at=computed_at,
            from_date=from_date,
            to_date=to_date,
            headers=[],
            series={},
        )

        data = result.to_dict()
        json_str = json.dumps(data)
        assert isinstance(json_str, str)

    @given(
        headers=st.lists(st.text(min_size=1, max_size=30), min_size=0, max_size=5),
    )
    def test_report_type_detection(self, headers: list[str]) -> None:
        """report_type should be correctly detected from headers."""
        result = SavedReportResult(
            bookmark_id=1,
            computed_at="2024-01-01T00:00:00",
            from_date="2024-01-01",
            to_date="2024-01-31",
            headers=headers,
            series={},
        )

        report_type = result.report_type
        assert report_type in ("insights", "retention", "funnel")

        # Verify detection logic
        has_retention = any("$retention" in h.lower() for h in headers)
        has_funnel = any("$funnel" in h.lower() for h in headers)

        if has_retention:
            assert report_type == "retention"
        elif has_funnel:
            assert report_type == "funnel"
        else:
            assert report_type == "insights"


# =============================================================================
# FlowsResult Property Tests
# =============================================================================


class TestFlowsResultProperties:
    """Property-based tests for FlowsResult."""

    @given(
        bookmark_id=st.integers(min_value=1, max_value=10_000_000),
        computed_at=st.text(min_size=1, max_size=30),
        overall_conversion_rate=conversion_rates,
        step_count=st.integers(min_value=0, max_value=10),
    )
    def test_to_dict_always_json_serializable(
        self,
        bookmark_id: int,
        computed_at: str,
        overall_conversion_rate: float,
        step_count: int,
    ) -> None:
        """to_dict() output should always be JSON-serializable."""
        steps = [
            {"event": f"Step_{i}", "count": max(0, 100 - i * 10)}
            for i in range(step_count)
        ]

        result = FlowsResult(
            bookmark_id=bookmark_id,
            computed_at=computed_at,
            steps=steps,
            breakdowns=[],
            overall_conversion_rate=overall_conversion_rate,
            metadata={},
        )

        data = result.to_dict()
        json_str = json.dumps(data)
        assert isinstance(json_str, str)
        assert len(data["steps"]) == step_count

    @given(step_count=st.integers(min_value=0, max_value=20))
    def test_df_row_count_matches_steps(self, step_count: int) -> None:
        """DataFrame row count should equal number of steps."""
        steps = [{"event": f"Step_{i}", "count": 100} for i in range(step_count)]

        result = FlowsResult(
            bookmark_id=1,
            computed_at="2024-01-01T00:00:00",
            steps=steps,
            breakdowns=[],
            overall_conversion_rate=0.5,
            metadata={},
        )

        assert len(result.df) == step_count


# =============================================================================
# SummaryResult Property Tests
# =============================================================================


class TestSummaryResultProperties:
    """Property-based tests for SummaryResult."""

    @given(
        table=table_names,
        row_count=st.integers(min_value=0, max_value=10_000_000),
        column_count=st.integers(min_value=0, max_value=10),
    )
    def test_to_dict_always_json_serializable(
        self, table: str, row_count: int, column_count: int
    ) -> None:
        """to_dict() output should always be JSON-serializable."""
        columns = [
            ColumnSummary(
                column_name=f"col_{i}",
                column_type="VARCHAR",
                min=None,
                max=None,
                approx_unique=100,
                avg=None,
                std=None,
                q25=None,
                q50=None,
                q75=None,
                count=row_count,
                null_percentage=0.0,
            )
            for i in range(column_count)
        ]

        result = SummaryResult(
            table=table,
            row_count=row_count,
            columns=columns,
        )

        data = result.to_dict()
        json_str = json.dumps(data)
        assert isinstance(json_str, str)
        assert len(data["columns"]) == column_count

    @given(column_count=st.integers(min_value=0, max_value=20))
    def test_df_row_count_matches_columns(self, column_count: int) -> None:
        """DataFrame row count should equal number of columns."""
        columns = [
            ColumnSummary(
                column_name=f"col_{i}",
                column_type="VARCHAR",
                min=None,
                max=None,
                approx_unique=100,
                avg=None,
                std=None,
                q25=None,
                q50=None,
                q75=None,
                count=100,
                null_percentage=0.0,
            )
            for i in range(column_count)
        ]

        result = SummaryResult(
            table="test_table",
            row_count=100,
            columns=columns,
        )

        assert len(result.df) == column_count


# =============================================================================
# EventBreakdownResult Property Tests
# =============================================================================


class TestEventBreakdownResultProperties:
    """Property-based tests for EventBreakdownResult."""

    @given(
        table=table_names,
        total_events=st.integers(min_value=0, max_value=10_000_000),
        total_users=st.integers(min_value=0, max_value=1_000_000),
        event_count=st.integers(min_value=0, max_value=10),
        timestamp=datetimes,
    )
    def test_to_dict_always_json_serializable(
        self,
        table: str,
        total_events: int,
        total_users: int,
        event_count: int,
        timestamp: datetime,
    ) -> None:
        """to_dict() output should always be JSON-serializable."""
        events = [
            EventStats(
                event_name=f"Event_{i}",
                count=total_events // max(1, event_count),
                unique_users=total_users // max(1, event_count),
                first_seen=timestamp,
                last_seen=timestamp,
                pct_of_total=100.0 / max(1, event_count),
            )
            for i in range(event_count)
        ]

        result = EventBreakdownResult(
            table=table,
            total_events=total_events,
            total_users=total_users,
            date_range=(timestamp, timestamp),
            events=events,
        )

        data = result.to_dict()
        json_str = json.dumps(data)
        assert isinstance(json_str, str)
        assert len(data["events"]) == event_count

    @given(event_count=st.integers(min_value=0, max_value=20), timestamp=datetimes)
    def test_df_row_count_matches_events(
        self, event_count: int, timestamp: datetime
    ) -> None:
        """DataFrame row count should equal number of event types."""
        events = [
            EventStats(
                event_name=f"Event_{i}",
                count=100,
                unique_users=50,
                first_seen=timestamp,
                last_seen=timestamp,
                pct_of_total=10.0,
            )
            for i in range(event_count)
        ]

        result = EventBreakdownResult(
            table="test_table",
            total_events=1000,
            total_users=100,
            date_range=(timestamp, timestamp),
            events=events,
        )

        assert len(result.df) == event_count


# =============================================================================
# ColumnStatsResult Property Tests
# =============================================================================


class TestColumnStatsResultProperties:
    """Property-based tests for ColumnStatsResult."""

    @given(
        table=table_names,
        column=st.text(min_size=1, max_size=30),
        dtype=st.sampled_from(["VARCHAR", "INTEGER", "DOUBLE", "TIMESTAMP", "JSON"]),
        count=st.integers(min_value=0, max_value=10_000_000),
        null_count=st.integers(min_value=0, max_value=10_000_000),
        unique_count=st.integers(min_value=0, max_value=10_000_000),
    )
    def test_to_dict_always_json_serializable(
        self,
        table: str,
        column: str,
        dtype: str,
        count: int,
        null_count: int,
        unique_count: int,
    ) -> None:
        """to_dict() output should always be JSON-serializable."""
        total = count + null_count
        null_pct = (null_count / total * 100) if total > 0 else 0.0
        unique_pct = (unique_count / count * 100) if count > 0 else 0.0

        result = ColumnStatsResult(
            table=table,
            column=column,
            dtype=dtype,
            count=count,
            null_count=null_count,
            null_pct=null_pct,
            unique_count=unique_count,
            unique_pct=unique_pct,
            top_values=[],
        )

        data = result.to_dict()
        json_str = json.dumps(data)
        assert isinstance(json_str, str)

    @given(top_value_count=st.integers(min_value=0, max_value=20))
    def test_df_row_count_matches_top_values(self, top_value_count: int) -> None:
        """DataFrame row count should equal number of top values."""
        top_values = [(f"value_{i}", 100 - i) for i in range(top_value_count)]

        result = ColumnStatsResult(
            table="test_table",
            column="test_column",
            dtype="VARCHAR",
            count=1000,
            null_count=0,
            null_pct=0.0,
            unique_count=100,
            unique_pct=10.0,
            top_values=top_values,
        )

        assert len(result.df) == top_value_count


# =============================================================================
# Helper Type Property Tests
# =============================================================================


class TestHelperTypeProperties:
    """Property-based tests for helper types (no df property)."""

    @given(
        funnel_id=st.integers(min_value=1, max_value=10_000_000),
        name=st.text(min_size=1, max_size=100),
    )
    def test_funnel_info_to_dict_json_serializable(
        self, funnel_id: int, name: str
    ) -> None:
        """FunnelInfo.to_dict() should always be JSON-serializable."""
        result = FunnelInfo(funnel_id=funnel_id, name=name)
        data = result.to_dict()
        json_str = json.dumps(data)
        assert isinstance(json_str, str)

    @given(
        id=st.integers(min_value=1, max_value=10_000_000),
        name=st.text(min_size=1, max_size=100),
        count=st.integers(min_value=0, max_value=10_000_000),
        description=st.text(max_size=200),
        created=st.text(min_size=1, max_size=30),
        is_visible=st.booleans(),
    )
    def test_saved_cohort_to_dict_json_serializable(
        self,
        id: int,
        name: str,
        count: int,
        description: str,
        created: str,
        is_visible: bool,
    ) -> None:
        """SavedCohort.to_dict() should always be JSON-serializable."""
        result = SavedCohort(
            id=id,
            name=name,
            count=count,
            description=description,
            created=created,
            is_visible=is_visible,
        )
        data = result.to_dict()
        json_str = json.dumps(data)
        assert isinstance(json_str, str)

    @given(
        id=st.integers(min_value=1, max_value=10_000_000),
        name=st.text(min_size=1, max_size=100),
        bookmark_type=st.sampled_from(
            ["insights", "funnels", "retention", "flows", "launch-analysis"]
        ),
        project_id=st.integers(min_value=1, max_value=10_000_000),
        created=st.text(min_size=1, max_size=30),
        modified=st.text(min_size=1, max_size=30),
    )
    def test_bookmark_info_to_dict_json_serializable(
        self,
        id: int,
        name: str,
        bookmark_type: str,
        project_id: int,
        created: str,
        modified: str,
    ) -> None:
        """BookmarkInfo.to_dict() should always be JSON-serializable."""
        result = BookmarkInfo(
            id=id,
            name=name,
            type=bookmark_type,  # type: ignore[arg-type]
            project_id=project_id,
            created=created,
            modified=modified,
        )
        data = result.to_dict()
        json_str = json.dumps(data)
        assert isinstance(json_str, str)

    @given(
        event=event_names,
        count=st.integers(min_value=0, max_value=10_000_000),
        percent_change=st.floats(min_value=-1.0, max_value=100.0, allow_nan=False),
    )
    def test_top_event_to_dict_json_serializable(
        self, event: str, count: int, percent_change: float
    ) -> None:
        """TopEvent.to_dict() should always be JSON-serializable."""
        result = TopEvent(event=event, count=count, percent_change=percent_change)
        data = result.to_dict()
        json_str = json.dumps(data)
        assert isinstance(json_str, str)

    @given(
        event=event_names,
        event_time=datetimes,
        properties=st.dictionaries(
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
    )
    def test_user_event_to_dict_json_serializable(
        self, event: str, event_time: datetime, properties: dict[str, object]
    ) -> None:
        """UserEvent.to_dict() should always be JSON-serializable."""
        result = UserEvent(event=event, time=event_time, properties=properties)
        data = result.to_dict()
        json_str = json.dumps(data)
        assert isinstance(json_str, str)


# =============================================================================
# SQLResult Property Tests
# =============================================================================


# Strategy for valid column names (non-empty printable identifiers)
column_names = st.text(
    alphabet=st.characters(categories=("L", "N")),
    min_size=1,
    max_size=30,
).filter(lambda s: s and s[0].isalpha())


class TestSQLResultPBT:
    """Property-based tests for SQLResult."""

    @given(
        columns=st.lists(column_names, min_size=1, max_size=10, unique=True),
        num_rows=st.integers(min_value=0, max_value=20),
    )
    def test_sql_result_len_matches_rows(
        self, columns: list[str], num_rows: int
    ) -> None:
        """len(SQLResult) should always equal len(rows)."""
        # Generate rows matching column count
        rows = [
            tuple(f"val_{i}_{j}" for j in range(len(columns))) for i in range(num_rows)
        ]
        result = SQLResult(columns=columns, rows=rows)
        assert len(result) == num_rows
        assert len(result) == len(result.rows)

    @given(
        columns=st.lists(column_names, min_size=1, max_size=5, unique=True),
        num_rows=st.integers(min_value=0, max_value=10),
    )
    def test_sql_result_to_dicts_has_correct_keys(
        self, columns: list[str], num_rows: int
    ) -> None:
        """to_dicts() should produce dicts with exactly the column names as keys."""
        rows = [
            tuple(f"val_{i}_{j}" for j in range(len(columns))) for i in range(num_rows)
        ]
        result = SQLResult(columns=columns, rows=rows)
        dicts = result.to_dicts()

        assert len(dicts) == num_rows
        for d in dicts:
            assert set(d.keys()) == set(columns)

    @given(
        columns=st.lists(column_names, min_size=1, max_size=5, unique=True),
    )
    def test_sql_result_to_dict_json_serializable(self, columns: list[str]) -> None:
        """SQLResult.to_dict() should always be JSON-serializable."""
        rows = [tuple(f"val_{j}" for j in range(len(columns)))]
        result = SQLResult(columns=columns, rows=rows)
        data = result.to_dict()
        json_str = json.dumps(data)
        assert isinstance(json_str, str)
        assert data["row_count"] == 1
        assert data["columns"] == columns

    @given(
        columns=st.lists(column_names, min_size=1, max_size=5, unique=True),
        num_rows=st.integers(min_value=0, max_value=10),
    )
    def test_sql_result_iter_yields_all_rows(
        self, columns: list[str], num_rows: int
    ) -> None:
        """Iterating SQLResult should yield all rows in order."""
        rows = [tuple(i for _ in range(len(columns))) for i in range(num_rows)]
        result = SQLResult(columns=columns, rows=rows)

        iterated = list(result)
        assert iterated == rows
