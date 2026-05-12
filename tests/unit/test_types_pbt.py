"""Property-based tests for mixpanel_headless result types using Hypothesis.

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

import dataclasses
import datetime
import json
from datetime import datetime as dt_datetime
from pathlib import Path
from typing import get_args

import pandas as pd
import pytest
from hypothesis import given
from hypothesis import strategies as st

from mixpanel_headless._internal.bookmark_enums import VALID_FREQUENCY_FILTER_OPERATORS
from mixpanel_headless._literal_types import MathType, TimeComparisonUnit
from mixpanel_headless.types import (
    ActivityFeedResult,
    BookmarkInfo,
    CohortInfo,
    DailyCount,
    DailyCountsResult,
    EngagementBucket,
    EngagementDistributionResult,
    EventCountsResult,
    FlowsResult,
    FrequencyBreakdown,
    FrequencyFilter,
    FrequencyResult,
    FunnelInfo,
    FunnelResult,
    FunnelResultStep,
    JQLResult,
    Metric,
    NumericAverageResult,
    NumericBucketResult,
    NumericPropertySummaryResult,
    NumericSumResult,
    PropertyCountsResult,
    PropertyCoverage,
    PropertyCoverageResult,
    PropertyDistributionResult,
    PropertyValueCount,
    ResultWithDataFrame,
    RetentionResult,
    SavedCohort,
    SavedReportResult,
    SegmentationResult,
    TimeComparison,
    TopEvent,
    UserEvent,
)

# =============================================================================
# Custom Strategies
# =============================================================================

# Strategy for generating valid date strings (YYYY-MM-DD format).
# Constrained to 4-digit years (1000-9999) to match _DATE_RE regex.
date_strings = st.dates(
    min_value=datetime.date(1000, 1, 1),
    max_value=datetime.date(9999, 12, 31),
).map(lambda d: d.strftime("%Y-%m-%d"))

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
    min_value=dt_datetime(2020, 1, 1),
    max_value=dt_datetime(2030, 12, 31),
)


# =============================================================================
# ResultWithDataFrame Property Tests
# =============================================================================


class TestResultWithDataFrameProperties:
    """Property-based tests for ResultWithDataFrame base class.

    These tests verify invariants that should hold for all types inheriting from
    ResultWithDataFrame, ensuring the base class implementation is robust.
    """

    @given(
        num_rows=st.integers(min_value=0, max_value=50),
        num_cols=st.integers(min_value=1, max_value=10),
    )
    def test_to_table_dict_always_returns_list(
        self, num_rows: int, num_cols: int
    ) -> None:
        """to_table_dict() should always return a list, never None or other type."""

        @dataclasses.dataclass(frozen=True)
        class TestResult(ResultWithDataFrame):
            @property
            def df(self) -> pd.DataFrame:
                if self._df_cache is not None:
                    return self._df_cache

                data = {f"col_{i}": list(range(num_rows)) for i in range(num_cols)}
                result_df = pd.DataFrame(data)
                object.__setattr__(self, "_df_cache", result_df)
                return result_df

        result = TestResult()
        table_dict = result.to_table_dict()

        assert isinstance(table_dict, list)

    @given(
        num_rows=st.integers(min_value=1, max_value=50),
        num_cols=st.integers(min_value=1, max_value=10),
    )
    def test_all_elements_are_dicts(self, num_rows: int, num_cols: int) -> None:
        """Every element in to_table_dict() output should be a dict."""

        @dataclasses.dataclass(frozen=True)
        class TestResult(ResultWithDataFrame):
            @property
            def df(self) -> pd.DataFrame:
                data = {f"col_{i}": list(range(num_rows)) for i in range(num_cols)}
                return pd.DataFrame(data)

        result = TestResult()
        table_dict = result.to_table_dict()

        assert all(isinstance(row, dict) for row in table_dict)

    def test_empty_dataframe_returns_empty_list(self) -> None:
        """to_table_dict() should return empty list for empty DataFrame."""

        @dataclasses.dataclass(frozen=True)
        class EmptyResult(ResultWithDataFrame):
            @property
            def df(self) -> pd.DataFrame:
                return pd.DataFrame()

        result = EmptyResult()
        table_dict = result.to_table_dict()

        assert table_dict == []
        assert isinstance(table_dict, list)

    @given(
        num_rows=st.integers(min_value=0, max_value=50),
        num_cols=st.integers(min_value=1, max_value=10),
    )
    def test_row_count_matches_dataframe(self, num_rows: int, num_cols: int) -> None:
        """Length of to_table_dict() should equal number of DataFrame rows."""

        @dataclasses.dataclass(frozen=True)
        class TestResult(ResultWithDataFrame):
            @property
            def df(self) -> pd.DataFrame:
                data = {f"col_{i}": list(range(num_rows)) for i in range(num_cols)}
                return pd.DataFrame(data)

        result = TestResult()
        table_dict = result.to_table_dict()

        assert len(table_dict) == num_rows
        assert len(table_dict) == len(result.df)

    @given(
        num_rows=st.integers(min_value=1, max_value=20),
        col_names=st.lists(
            st.text(
                alphabet=st.characters(categories=("L", "N")),
                min_size=1,
                max_size=15,
            ).filter(lambda s: s and s[0].isalpha()),
            min_size=1,
            max_size=8,
            unique=True,
        ),
    )
    def test_column_names_become_dict_keys(
        self, num_rows: int, col_names: list[str]
    ) -> None:
        """All DataFrame column names should appear as keys in output dicts."""

        @dataclasses.dataclass(frozen=True)
        class TestResult(ResultWithDataFrame):
            @property
            def df(self) -> pd.DataFrame:
                data = {col: list(range(num_rows)) for col in col_names}
                return pd.DataFrame(data)

        result = TestResult()
        table_dict = result.to_table_dict()

        if table_dict:  # Only check if non-empty
            for row in table_dict:
                assert set(row.keys()) == set(col_names)

    @given(
        num_rows=st.integers(min_value=0, max_value=30),
        num_cols=st.integers(min_value=1, max_value=8),
    )
    def test_output_is_json_serializable(self, num_rows: int, num_cols: int) -> None:
        """to_table_dict() output should always be JSON-serializable."""

        @dataclasses.dataclass(frozen=True)
        class TestResult(ResultWithDataFrame):
            @property
            def df(self) -> pd.DataFrame:
                data = {f"col_{i}": list(range(num_rows)) for i in range(num_cols)}
                return pd.DataFrame(data)

        result = TestResult()
        table_dict = result.to_table_dict()

        # Should not raise
        json_str = json.dumps(table_dict)
        assert isinstance(json_str, str)

        # Should round-trip correctly
        parsed = json.loads(json_str)
        assert isinstance(parsed, list)
        assert len(parsed) == num_rows

    @given(
        num_rows=st.integers(min_value=1, max_value=20),
        num_cols=st.integers(min_value=1, max_value=5),
    )
    def test_deterministic_conversion(self, num_rows: int, num_cols: int) -> None:
        """Same DataFrame should always produce identical output."""

        @dataclasses.dataclass(frozen=True)
        class TestResult(ResultWithDataFrame):
            data: dict[str, list[int]] = dataclasses.field(default_factory=dict)

            @property
            def df(self) -> pd.DataFrame:
                if self._df_cache is not None:
                    return self._df_cache

                result_df = pd.DataFrame(self.data)
                object.__setattr__(self, "_df_cache", result_df)
                return result_df

        data = {f"col_{i}": list(range(num_rows)) for i in range(num_cols)}

        result1 = TestResult(data=data)
        result2 = TestResult(data=data)

        table_dict1 = result1.to_table_dict()
        table_dict2 = result2.to_table_dict()

        assert table_dict1 == table_dict2

    @given(
        values=st.lists(
            st.one_of(
                st.integers(min_value=-1000, max_value=1000),
                st.floats(min_value=-1e6, max_value=1e6, allow_nan=False),
                st.text(max_size=20),
                st.booleans(),
            ),
            min_size=0,
            max_size=20,
        )
    )
    def test_handles_various_data_types(self, values: list[object]) -> None:
        """Should handle DataFrames with various column types."""

        @dataclasses.dataclass(frozen=True)
        class TestResult(ResultWithDataFrame):
            @property
            def df(self) -> pd.DataFrame:
                if not values:
                    return pd.DataFrame()
                return pd.DataFrame({"value": values})

        result = TestResult()
        table_dict = result.to_table_dict()

        assert len(table_dict) == len(values)
        # Should still be JSON-serializable
        json.dumps(table_dict)


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
            FunnelResultStep(
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
            FunnelResultStep(event=f"Step {i}", count=100, conversion_rate=0.5)
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

# Custom strategies for JQL result structures


@st.composite
def groupby_structure(draw: st.DrawFn) -> list[dict[str, object]]:
    """Generate JQL groupBy result structure: {key: [...], value: X}."""
    num_results = draw(st.integers(min_value=1, max_value=20))
    key_count = draw(st.integers(min_value=1, max_value=4))

    # Decide if values are scalars or arrays (multiple reducers)
    use_array_values = draw(st.booleans())

    results = []
    for _ in range(num_results):
        key = [
            draw(
                st.one_of(
                    st.text(min_size=1, max_size=10),
                    st.integers(),
                )
            )
            for _ in range(key_count)
        ]

        if use_array_values:
            # Multiple reducers: value is array
            reducer_count = draw(st.integers(min_value=2, max_value=5))
            value = [
                draw(
                    st.one_of(
                        st.integers(),
                        st.floats(allow_nan=False, allow_infinity=False),
                    )
                )
                for _ in range(reducer_count)
            ]
        else:
            # Single reducer: value is scalar
            value = draw(
                st.one_of(
                    st.integers(),
                    st.floats(allow_nan=False, allow_infinity=False),
                )
            )

        results.append({"key": key, "value": value})

    return results


@st.composite
def nested_percentile_structure(draw: st.DrawFn) -> list[list[dict[str, object]]]:
    """Generate nested percentile structure: [[{percentile: X, value: Y}, ...]]."""
    percentile_count = draw(st.integers(min_value=1, max_value=10))

    percentiles: list[dict[str, object]] = []
    for _ in range(percentile_count):
        percentile_value: dict[str, object] = {
            "percentile": draw(st.integers(min_value=1, max_value=100)),
            "value": draw(
                st.one_of(
                    st.integers(),
                    st.floats(allow_nan=False, allow_infinity=False),
                )
            ),
        }
        percentiles.append(percentile_value)

    return [percentiles]


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

    @given(
        raw_data=st.one_of(
            st.lists(st.integers(), min_size=1, max_size=20),
            st.lists(
                st.dictionaries(
                    keys=st.text(min_size=1, max_size=10),
                    values=st.integers(),
                    min_size=1,
                    max_size=3,
                ),
                min_size=1,
                max_size=20,
            ),
            groupby_structure(),
        )
    )
    def test_deterministic_dataframe_conversion(self, raw_data: list[object]) -> None:
        """Same input should always produce structurally identical DataFrames.

        This is a critical property: the conversion should be deterministic,
        not relying on dictionary ordering, hash randomness, or other
        non-deterministic factors.
        """
        # Create two separate JQLResult objects with same data
        result1 = JQLResult(_raw=raw_data)
        result2 = JQLResult(_raw=raw_data)

        df1 = result1.df
        df2 = result2.df

        # Should have same columns in same order
        assert list(df1.columns) == list(df2.columns)

        # Should have same shape
        assert df1.shape == df2.shape

        # Should have same values (using pandas testing utility)
        pd.testing.assert_frame_equal(df1, df2)

    @given(
        raw_data=st.one_of(
            st.lists(st.integers(), min_size=0, max_size=20),
            st.lists(
                st.dictionaries(
                    keys=st.text(min_size=1, max_size=10),
                    values=st.integers(),
                    min_size=1,
                    max_size=3,
                ),
                min_size=0,
                max_size=20,
            ),
            groupby_structure(),
            nested_percentile_structure(),
        )
    )
    def test_df_never_crashes_on_valid_jql_output(self, raw_data: list[object]) -> None:
        """DataFrame conversion should never crash on valid JQL output."""
        result = JQLResult(_raw=raw_data)

        # Should always succeed
        df = result.df

        # Should always return a DataFrame
        assert isinstance(df, pd.DataFrame)

        # Row count should match input length (or flattened length for nested)
        if raw_data and isinstance(raw_data[0], list):
            # Nested structure gets flattened; each element of the inner list should
            # correspond to one row in the DataFrame.
            assert len(df) == len(raw_data[0])
        else:
            assert len(df) == len(raw_data)

    @given(
        raw_data=st.one_of(
            st.lists(st.integers(), min_size=1, max_size=10),
            groupby_structure(),
        )
    )
    def test_df_caching_works_for_all_structures(self, raw_data: list[object]) -> None:
        """DataFrame should be cached regardless of structure."""
        result = JQLResult(_raw=raw_data)

        df1 = result.df
        df2 = result.df

        # Same object, not recomputed
        assert df1 is df2

    @given(
        key_count=st.integers(min_value=1, max_value=5),
        row_count=st.integers(min_value=1, max_value=20),
    )
    def test_groupby_key_expansion_is_consistent(
        self, key_count: int, row_count: int
    ) -> None:
        """All rows should have same number of key columns."""
        # Create groupBy structure with varying key values
        raw_data = [
            {"key": [f"val{i}_{j}" for i in range(key_count)], "value": j}
            for j in range(row_count)
        ]

        result = JQLResult(_raw=raw_data)
        df = result.df

        # Should have exactly key_count key columns
        key_columns = [col for col in df.columns if col.startswith("key_")]
        assert len(key_columns) == key_count

        # All rows should have values for all key columns
        for col in key_columns:
            assert df[col].notna().all()

    @given(
        reducer_count=st.integers(min_value=2, max_value=6),
        row_count=st.integers(min_value=1, max_value=20),
    )
    def test_multiple_reducer_expansion_is_consistent(
        self, reducer_count: int, row_count: int
    ) -> None:
        """All rows should have same number of value columns for multiple reducers."""
        # Create groupBy with multiple reducers
        raw_data = [
            {"key": [f"group{i}"], "value": [i * j for j in range(reducer_count)]}
            for i in range(row_count)
        ]

        result = JQLResult(_raw=raw_data)
        df = result.df

        # Should have exactly reducer_count value columns
        value_columns = [col for col in df.columns if col.startswith("value_")]
        assert len(value_columns) == reducer_count

        # All rows should have values for all value columns
        for col in value_columns:
            assert df[col].notna().all()

    @given(
        num_rows=st.integers(min_value=2, max_value=10),
    )
    def test_heterogeneous_value_types_raise_error(self, num_rows: int) -> None:
        """Heterogeneous value types (mixed scalar/array) should raise ValueError.

        This test generates groupBy structures where some rows have scalar values
        and others have array values, which should be detected and rejected.
        """
        import pytest

        # Create data with GUARANTEED heterogeneity: first row scalar, rest arrays
        raw_data = [{"key": ["key0"], "value": 42}]  # First row: scalar
        for i in range(1, num_rows):
            raw_data.append({"key": [f"key{i}"], "value": [1, 2, 3]})  # Rest: arrays

        result = JQLResult(_raw=raw_data)

        with pytest.raises(ValueError, match="Inconsistent value types"):
            _ = result.df


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
        all_results = [seg, funnel, retention, jql]
        for r in all_results:
            data = r.to_dict()  # type: ignore[attr-defined]
            json.dumps(data)  # Should not raise

        # All should produce valid DataFrames
        for r in all_results:
            df = r.df
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
        event_time: dt_datetime,
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
        self, event_count: int, event_time: dt_datetime
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
        assert report_type in ("insights", "retention", "funnel", "flows")

        # Verify detection logic
        has_retention = any("$retention" in h.lower() for h in headers)
        has_funnel = any("$funnel" in h.lower() for h in headers)
        has_flows = any("$flows" in h.lower() for h in headers)

        if has_retention:
            assert report_type == "retention"
        elif has_funnel:
            assert report_type == "funnel"
        elif has_flows:
            assert report_type == "flows"
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
        self, event: str, event_time: dt_datetime, properties: dict[str, object]
    ) -> None:
        """UserEvent.to_dict() should always be JSON-serializable."""
        result = UserEvent(event=event, time=event_time, properties=properties)
        data = result.to_dict()
        json_str = json.dumps(data)
        assert isinstance(json_str, str)


# =============================================================================
# PropertyValueCount Property Tests
# =============================================================================


# Strategy for property values (mixed types that can appear in Mixpanel)
property_values = st.one_of(
    st.text(min_size=0, max_size=50),
    st.integers(min_value=-1_000_000, max_value=1_000_000),
    st.floats(min_value=-1e6, max_value=1e6, allow_nan=False, allow_infinity=False),
    st.booleans(),
    st.none(),
)

# Strategy for percentages (0.0 to 100.0)
percentages = st.floats(min_value=0.0, max_value=100.0, allow_nan=False)

# Strategy for property names
property_names = st.text(
    alphabet=st.characters(categories=("L", "N", "P")),
    min_size=1,
    max_size=50,
).filter(lambda s: s.strip())


class TestPropertyValueCountProperties:
    """Property-based tests for PropertyValueCount."""

    @given(
        value=property_values,
        count=st.integers(min_value=0, max_value=10_000_000),
        percentage=percentages,
    )
    def test_to_dict_always_json_serializable(
        self, value: str | int | float | bool | None, count: int, percentage: float
    ) -> None:
        """to_dict() output should always be JSON-serializable."""
        result = PropertyValueCount(value=value, count=count, percentage=percentage)

        data = result.to_dict()
        json_str = json.dumps(data)
        assert isinstance(json_str, str)
        assert data["count"] == count

    @given(
        count=st.integers(min_value=0, max_value=10_000_000),
        percentage=percentages,
    )
    def test_immutable(self, count: int, percentage: float) -> None:
        """PropertyValueCount should be immutable (frozen dataclass)."""
        result = PropertyValueCount(value="test", count=count, percentage=percentage)

        import pytest

        with pytest.raises(dataclasses.FrozenInstanceError):
            result.count = 999  # type: ignore[misc]


# =============================================================================
# PropertyDistributionResult Property Tests
# =============================================================================


class TestPropertyDistributionResultProperties:
    """Property-based tests for PropertyDistributionResult."""

    @given(
        event=event_names,
        property_name=property_names,
        from_date=date_strings,
        to_date=date_strings,
        total_count=st.integers(min_value=0, max_value=10_000_000),
        value_count=st.integers(min_value=0, max_value=20),
    )
    def test_to_dict_always_json_serializable(
        self,
        event: str,
        property_name: str,
        from_date: str,
        to_date: str,
        total_count: int,
        value_count: int,
    ) -> None:
        """to_dict() output should always be JSON-serializable."""
        values = tuple(
            PropertyValueCount(
                value=f"value_{i}",
                count=total_count // max(1, value_count),
                percentage=100.0 / max(1, value_count),
            )
            for i in range(value_count)
        )

        result = PropertyDistributionResult(
            event=event,
            property_name=property_name,
            from_date=from_date,
            to_date=to_date,
            total_count=total_count,
            values=values,
        )

        data = result.to_dict()
        json_str = json.dumps(data)
        assert isinstance(json_str, str)
        assert len(data["values"]) == value_count

    @given(value_count=st.integers(min_value=0, max_value=30))
    def test_df_row_count_matches_values(self, value_count: int) -> None:
        """DataFrame row count should equal number of values."""
        values = tuple(
            PropertyValueCount(value=f"value_{i}", count=100, percentage=10.0)
            for i in range(value_count)
        )

        result = PropertyDistributionResult(
            event="test_event",
            property_name="test_property",
            from_date="2024-01-01",
            to_date="2024-01-31",
            total_count=1000,
            values=values,
        )

        assert len(result.df) == value_count

    @given(event=event_names, property_name=property_names)
    def test_df_has_required_columns(self, event: str, property_name: str) -> None:
        """DataFrame should always have value, count, percentage columns."""
        result = PropertyDistributionResult(
            event=event,
            property_name=property_name,
            from_date="2024-01-01",
            to_date="2024-01-31",
            total_count=0,
            values=(),
        )

        df = result.df
        assert "value" in df.columns
        assert "count" in df.columns
        assert "percentage" in df.columns

    @given(event=event_names, property_name=property_names)
    def test_df_cached_returns_same_object(
        self, event: str, property_name: str
    ) -> None:
        """Repeated df access should return the same cached object."""
        result = PropertyDistributionResult(
            event=event,
            property_name=property_name,
            from_date="2024-01-01",
            to_date="2024-01-31",
            total_count=0,
            values=(),
        )

        df1 = result.df
        df2 = result.df
        assert df1 is df2


# =============================================================================
# NumericPropertySummaryResult Property Tests
# =============================================================================


class TestNumericPropertySummaryResultProperties:
    """Property-based tests for NumericPropertySummaryResult."""

    @given(
        event=event_names,
        property_name=property_names,
        from_date=date_strings,
        to_date=date_strings,
        count=st.integers(min_value=0, max_value=10_000_000),
        min_val=st.floats(min_value=-1e9, max_value=1e9, allow_nan=False),
        max_val=st.floats(min_value=-1e9, max_value=1e9, allow_nan=False),
        sum_val=st.floats(min_value=-1e12, max_value=1e12, allow_nan=False),
        avg_val=st.floats(min_value=-1e9, max_value=1e9, allow_nan=False),
        stddev_val=st.floats(min_value=0, max_value=1e9, allow_nan=False),
    )
    def test_to_dict_always_json_serializable(
        self,
        event: str,
        property_name: str,
        from_date: str,
        to_date: str,
        count: int,
        min_val: float,
        max_val: float,
        sum_val: float,
        avg_val: float,
        stddev_val: float,
    ) -> None:
        """to_dict() output should always be JSON-serializable."""
        result = NumericPropertySummaryResult(
            event=event,
            property_name=property_name,
            from_date=from_date,
            to_date=to_date,
            count=count,
            min=min_val,
            max=max_val,
            sum=sum_val,
            avg=avg_val,
            stddev=stddev_val,
            percentiles={25: 10.0, 50: 50.0, 75: 90.0},
        )

        data = result.to_dict()
        json_str = json.dumps(data)
        assert isinstance(json_str, str)
        assert data["count"] == count

    @given(
        percentile_keys=st.lists(
            st.integers(min_value=1, max_value=99),
            min_size=0,
            max_size=10,
            unique=True,
        ),
    )
    def test_percentiles_preserved(self, percentile_keys: list[int]) -> None:
        """Percentiles should be preserved through serialization."""
        percentiles = {k: float(k) for k in percentile_keys}

        result = NumericPropertySummaryResult(
            event="test_event",
            property_name="test_property",
            from_date="2024-01-01",
            to_date="2024-01-31",
            count=1000,
            min=0.0,
            max=100.0,
            sum=50000.0,
            avg=50.0,
            stddev=25.0,
            percentiles=percentiles,
        )

        data = result.to_dict()
        # Keys become strings in JSON
        assert len(data["percentiles"]) == len(percentile_keys)


# =============================================================================
# DailyCount and DailyCountsResult Property Tests
# =============================================================================


class TestDailyCountProperties:
    """Property-based tests for DailyCount."""

    @given(
        date=date_strings,
        event=event_names,
        count=st.integers(min_value=0, max_value=10_000_000),
    )
    def test_to_dict_always_json_serializable(
        self, date: str, event: str, count: int
    ) -> None:
        """to_dict() output should always be JSON-serializable."""
        result = DailyCount(date=date, event=event, count=count)

        data = result.to_dict()
        json_str = json.dumps(data)
        assert isinstance(json_str, str)
        assert data["count"] == count


class TestDailyCountsResultProperties:
    """Property-based tests for DailyCountsResult."""

    @given(
        from_date=date_strings,
        to_date=date_strings,
        events=st.one_of(st.none(), st.lists(event_names, min_size=1, max_size=5)),
        count_count=st.integers(min_value=0, max_value=20),
    )
    def test_to_dict_always_json_serializable(
        self,
        from_date: str,
        to_date: str,
        events: list[str] | None,
        count_count: int,
    ) -> None:
        """to_dict() output should always be JSON-serializable."""
        counts = tuple(
            DailyCount(
                date=f"2024-01-{(i % 28) + 1:02d}", event=f"Event_{i}", count=100
            )
            for i in range(count_count)
        )

        result = DailyCountsResult(
            from_date=from_date,
            to_date=to_date,
            events=tuple(events) if events else None,
            counts=counts,
        )

        data = result.to_dict()
        json_str = json.dumps(data)
        assert isinstance(json_str, str)
        assert len(data["counts"]) == count_count

    @given(count_count=st.integers(min_value=0, max_value=30))
    def test_df_row_count_matches_counts(self, count_count: int) -> None:
        """DataFrame row count should equal number of counts."""
        counts = tuple(
            DailyCount(date=f"2024-01-{(i % 28) + 1:02d}", event="TestEvent", count=100)
            for i in range(count_count)
        )

        result = DailyCountsResult(
            from_date="2024-01-01",
            to_date="2024-01-31",
            events=None,
            counts=counts,
        )

        assert len(result.df) == count_count

    def test_df_has_required_columns(self) -> None:
        """DataFrame should always have date, event, count columns."""
        result = DailyCountsResult(
            from_date="2024-01-01",
            to_date="2024-01-31",
            events=None,
            counts=(),
        )

        df = result.df
        assert "date" in df.columns
        assert "event" in df.columns
        assert "count" in df.columns

    @given(from_date=date_strings, to_date=date_strings)
    def test_df_cached_returns_same_object(self, from_date: str, to_date: str) -> None:
        """Repeated df access should return the same cached object."""
        result = DailyCountsResult(
            from_date=from_date,
            to_date=to_date,
            events=None,
            counts=(),
        )

        df1 = result.df
        df2 = result.df
        assert df1 is df2


# =============================================================================
# EngagementBucket and EngagementDistributionResult Property Tests
# =============================================================================


class TestEngagementBucketProperties:
    """Property-based tests for EngagementBucket."""

    @given(
        bucket_min=st.integers(min_value=0, max_value=10000),
        bucket_label=st.text(min_size=1, max_size=20),
        user_count=st.integers(min_value=0, max_value=10_000_000),
        percentage=percentages,
    )
    def test_to_dict_always_json_serializable(
        self, bucket_min: int, bucket_label: str, user_count: int, percentage: float
    ) -> None:
        """to_dict() output should always be JSON-serializable."""
        result = EngagementBucket(
            bucket_min=bucket_min,
            bucket_label=bucket_label,
            user_count=user_count,
            percentage=percentage,
        )

        data = result.to_dict()
        json_str = json.dumps(data)
        assert isinstance(json_str, str)
        assert data["user_count"] == user_count


class TestEngagementDistributionResultProperties:
    """Property-based tests for EngagementDistributionResult."""

    @given(
        from_date=date_strings,
        to_date=date_strings,
        events=st.one_of(st.none(), st.lists(event_names, min_size=1, max_size=5)),
        total_users=st.integers(min_value=0, max_value=10_000_000),
        bucket_count=st.integers(min_value=0, max_value=10),
    )
    def test_to_dict_always_json_serializable(
        self,
        from_date: str,
        to_date: str,
        events: list[str] | None,
        total_users: int,
        bucket_count: int,
    ) -> None:
        """to_dict() output should always be JSON-serializable."""
        buckets = tuple(
            EngagementBucket(
                bucket_min=i * 10,
                bucket_label=f"{i * 10}-{(i + 1) * 10}",
                user_count=total_users // max(1, bucket_count),
                percentage=100.0 / max(1, bucket_count),
            )
            for i in range(bucket_count)
        )

        result = EngagementDistributionResult(
            from_date=from_date,
            to_date=to_date,
            events=tuple(events) if events else None,
            total_users=total_users,
            buckets=buckets,
        )

        data = result.to_dict()
        json_str = json.dumps(data)
        assert isinstance(json_str, str)
        assert len(data["buckets"]) == bucket_count

    @given(bucket_count=st.integers(min_value=0, max_value=20))
    def test_df_row_count_matches_buckets(self, bucket_count: int) -> None:
        """DataFrame row count should equal number of buckets."""
        buckets = tuple(
            EngagementBucket(
                bucket_min=i * 10,
                bucket_label=f"{i * 10}+",
                user_count=100,
                percentage=10.0,
            )
            for i in range(bucket_count)
        )

        result = EngagementDistributionResult(
            from_date="2024-01-01",
            to_date="2024-01-31",
            events=None,
            total_users=1000,
            buckets=buckets,
        )

        assert len(result.df) == bucket_count

    def test_df_has_required_columns(self) -> None:
        """DataFrame should have bucket_min, bucket_label, user_count, percentage."""
        result = EngagementDistributionResult(
            from_date="2024-01-01",
            to_date="2024-01-31",
            events=None,
            total_users=0,
            buckets=(),
        )

        df = result.df
        assert "bucket_min" in df.columns
        assert "bucket_label" in df.columns
        assert "user_count" in df.columns
        assert "percentage" in df.columns

    @given(from_date=date_strings, to_date=date_strings)
    def test_df_cached_returns_same_object(self, from_date: str, to_date: str) -> None:
        """Repeated df access should return the same cached object."""
        result = EngagementDistributionResult(
            from_date=from_date,
            to_date=to_date,
            events=None,
            total_users=0,
            buckets=(),
        )

        df1 = result.df
        df2 = result.df
        assert df1 is df2


# =============================================================================
# PropertyCoverage and PropertyCoverageResult Property Tests
# =============================================================================


class TestPropertyCoverageProperties:
    """Property-based tests for PropertyCoverage."""

    @given(
        property_name=property_names,
        defined_count=st.integers(min_value=0, max_value=10_000_000),
        null_count=st.integers(min_value=0, max_value=10_000_000),
        coverage_percentage=percentages,
    )
    def test_to_dict_always_json_serializable(
        self,
        property_name: str,
        defined_count: int,
        null_count: int,
        coverage_percentage: float,
    ) -> None:
        """to_dict() output should always be JSON-serializable."""
        result = PropertyCoverage(
            property=property_name,
            defined_count=defined_count,
            null_count=null_count,
            coverage_percentage=coverage_percentage,
        )

        data = result.to_dict()
        json_str = json.dumps(data)
        assert isinstance(json_str, str)
        assert data["defined_count"] == defined_count


class TestPropertyCoverageResultProperties:
    """Property-based tests for PropertyCoverageResult."""

    @given(
        event=event_names,
        from_date=date_strings,
        to_date=date_strings,
        total_events=st.integers(min_value=0, max_value=10_000_000),
        coverage_count=st.integers(min_value=0, max_value=10),
    )
    def test_to_dict_always_json_serializable(
        self,
        event: str,
        from_date: str,
        to_date: str,
        total_events: int,
        coverage_count: int,
    ) -> None:
        """to_dict() output should always be JSON-serializable."""
        coverage = tuple(
            PropertyCoverage(
                property=f"prop_{i}",
                defined_count=total_events // 2,
                null_count=total_events // 2,
                coverage_percentage=50.0,
            )
            for i in range(coverage_count)
        )

        result = PropertyCoverageResult(
            event=event,
            from_date=from_date,
            to_date=to_date,
            total_events=total_events,
            coverage=coverage,
        )

        data = result.to_dict()
        json_str = json.dumps(data)
        assert isinstance(json_str, str)
        assert len(data["coverage"]) == coverage_count

    @given(coverage_count=st.integers(min_value=0, max_value=20))
    def test_df_row_count_matches_coverage(self, coverage_count: int) -> None:
        """DataFrame row count should equal number of coverage entries."""
        coverage = tuple(
            PropertyCoverage(
                property=f"prop_{i}",
                defined_count=500,
                null_count=500,
                coverage_percentage=50.0,
            )
            for i in range(coverage_count)
        )

        result = PropertyCoverageResult(
            event="test_event",
            from_date="2024-01-01",
            to_date="2024-01-31",
            total_events=1000,
            coverage=coverage,
        )

        assert len(result.df) == coverage_count

    def test_df_has_required_columns(self) -> None:
        """DataFrame should have property, defined_count, null_count, coverage_pct."""
        result = PropertyCoverageResult(
            event="test_event",
            from_date="2024-01-01",
            to_date="2024-01-31",
            total_events=0,
            coverage=(),
        )

        df = result.df
        assert "property" in df.columns
        assert "defined_count" in df.columns
        assert "null_count" in df.columns
        assert "coverage_percentage" in df.columns

    @given(event=event_names)
    def test_df_cached_returns_same_object(self, event: str) -> None:
        """Repeated df access should return the same cached object."""
        result = PropertyCoverageResult(
            event=event,
            from_date="2024-01-01",
            to_date="2024-01-31",
            total_events=0,
            coverage=(),
        )

        df1 = result.df
        df2 = result.df
        assert df1 is df2


# =============================================================================
# OAuth Types PBT (Phase 023)
# =============================================================================


class TestPkceChallengePBT:
    """Property-based tests for PKCE challenge generation."""

    @given(st.integers(min_value=1, max_value=50))
    def test_verifier_always_86_chars(self, _n: int) -> None:
        """Every generated PKCE challenge has a 86-char verifier."""
        from mixpanel_headless._internal.auth.pkce import PkceChallenge

        challenge = PkceChallenge.generate()
        assert len(challenge.verifier) == 86

    @given(st.integers(min_value=1, max_value=50))
    def test_challenge_always_43_chars(self, _n: int) -> None:
        """Every generated PKCE challenge has a 43-char SHA-256 hash."""
        from mixpanel_headless._internal.auth.pkce import PkceChallenge

        challenge = PkceChallenge.generate()
        assert len(challenge.challenge) == 43

    @given(st.integers(min_value=1, max_value=50))
    def test_verifier_is_base64url(self, _n: int) -> None:
        """Verifier only contains base64url characters (no padding)."""
        import re

        from mixpanel_headless._internal.auth.pkce import PkceChallenge

        challenge = PkceChallenge.generate()
        assert re.match(r"^[A-Za-z0-9_-]+$", challenge.verifier)

    @given(st.integers(min_value=1, max_value=50))
    def test_challenge_is_sha256_of_verifier(self, _n: int) -> None:
        """Challenge is always SHA-256(verifier) in base64url no-pad."""
        import base64
        import hashlib

        from mixpanel_headless._internal.auth.pkce import PkceChallenge

        pair = PkceChallenge.generate()
        expected = (
            base64.urlsafe_b64encode(
                hashlib.sha256(pair.verifier.encode("ascii")).digest()
            )
            .rstrip(b"=")
            .decode("ascii")
        )
        assert pair.challenge == expected

    @given(st.integers(min_value=1, max_value=20))
    def test_each_generation_unique(self, _n: int) -> None:
        """Two consecutive generations produce different verifiers."""
        from mixpanel_headless._internal.auth.pkce import PkceChallenge

        a = PkceChallenge.generate()
        b = PkceChallenge.generate()
        assert a.verifier != b.verifier


class TestOAuthTokensRoundTripPBT:
    """Property-based tests for OAuthTokens JSON round-trip via storage."""

    @given(
        scope=st.text(
            alphabet=st.characters(whitelist_categories=("L", "Zs")),
            min_size=1,
            max_size=200,
        ),
        expires_in=st.integers(min_value=60, max_value=86400),
    )
    def test_from_token_response_round_trip(self, scope: str, expires_in: int) -> None:
        """from_token_response always produces a valid OAuthTokens."""
        from mixpanel_headless._internal.auth.token import OAuthTokens

        data = {
            "access_token": "test_access_token",
            "refresh_token": "test_refresh_token",
            "expires_in": expires_in,
            "scope": scope,
            "token_type": "Bearer",
        }
        tokens = OAuthTokens.from_token_response(data)

        assert tokens.access_token.get_secret_value() == "test_access_token"
        assert tokens.scope == scope
        assert tokens.token_type == "Bearer"

    @given(buffer_seconds=st.integers(min_value=31, max_value=100000))
    def test_not_expired_when_far_future(self, buffer_seconds: int) -> None:
        """Tokens with expires_at far in the future are never expired."""
        from mixpanel_headless._internal.auth.token import OAuthTokens

        tokens = OAuthTokens.from_token_response(
            {
                "access_token": "tok",
                "expires_in": buffer_seconds,
                "scope": "all",
                "token_type": "Bearer",
            }
        )
        assert not tokens.is_expired()

    @given(seconds_past=st.integers(min_value=0, max_value=100000))
    def test_expired_when_in_past(self, seconds_past: int) -> None:
        """Tokens with expires_at in the past are always expired."""
        from datetime import timedelta, timezone

        from pydantic import SecretStr

        from mixpanel_headless._internal.auth.token import OAuthTokens

        now = dt_datetime.now(timezone.utc)
        tokens = OAuthTokens(
            access_token=SecretStr("tok"),
            expires_at=now - timedelta(seconds=seconds_past),
            scope="all",
            token_type="Bearer",
        )
        assert tokens.is_expired()

    @given(
        access_token=st.text(
            min_size=1,
            max_size=500,
            alphabet=st.characters(whitelist_categories=("L", "N", "P")),
        ),
        scope=st.text(min_size=1, max_size=200),
        expires_in=st.integers(min_value=31, max_value=86400),
    )
    def test_storage_save_load_round_trip(
        self,
        access_token: str,
        scope: str,
        expires_in: int,
    ) -> None:
        """OAuthStorage save/load round-trips preserve all token fields.

        Verifies that saving tokens to disk and loading them back yields
        identical access_token and scope values.

        Args:
            access_token: Randomly generated access token string.
            scope: Randomly generated scope string.
            expires_in: Token lifetime in seconds (>30 to avoid expiry edge case).
        """
        import tempfile

        from mixpanel_headless._internal.auth.storage import OAuthStorage
        from mixpanel_headless._internal.auth.token import OAuthTokens

        tokens = OAuthTokens.from_token_response(
            {
                "access_token": access_token,
                "expires_in": expires_in,
                "scope": scope,
                "token_type": "Bearer",
            },
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            storage = OAuthStorage(storage_dir=Path(tmpdir))
            storage.save_tokens(tokens, region="us")
            loaded = storage.load_tokens(region="us")

        assert loaded is not None
        assert loaded.access_token.get_secret_value() == access_token
        assert loaded.scope == scope


# =============================================================================
# TimeComparison Property Tests (Phase 040)
# =============================================================================

# Strategies for TimeComparison
time_comparison_units = st.sampled_from(list(get_args(TimeComparisonUnit)))


class TestTimeComparisonProperties:
    """Property-based tests for TimeComparison factory methods and validation."""

    @given(unit=time_comparison_units)
    def test_relative_factory_always_valid(self, unit: str) -> None:
        """TimeComparison.relative() with any valid unit never raises."""
        tc = TimeComparison.relative(unit)  # type: ignore[arg-type]
        assert tc.type == "relative"
        assert tc.unit == unit
        assert tc.date is None

    @given(date=date_strings)
    def test_absolute_start_factory_always_valid(self, date: str) -> None:
        """TimeComparison.absolute_start() with YYYY-MM-DD date never raises."""
        tc = TimeComparison.absolute_start(date)
        assert tc.type == "absolute-start"
        assert tc.date == date
        assert tc.unit is None

    @given(date=date_strings)
    def test_absolute_end_factory_always_valid(self, date: str) -> None:
        """TimeComparison.absolute_end() with YYYY-MM-DD date never raises."""
        tc = TimeComparison.absolute_end(date)
        assert tc.type == "absolute-end"
        assert tc.date == date
        assert tc.unit is None

    @given(unit=time_comparison_units, date=date_strings)
    def test_relative_with_date_raises(self, unit: str, date: str) -> None:
        """TC1: type='relative' with date set always raises ValueError."""
        with pytest.raises(ValueError, match="does not accept date"):
            TimeComparison(type="relative", unit=unit, date=date)  # type: ignore[arg-type]

    @given(
        tc_type=st.sampled_from(["absolute-start", "absolute-end"]),
        unit=time_comparison_units,
        date=date_strings,
    )
    def test_absolute_with_unit_raises(
        self, tc_type: str, unit: str, date: str
    ) -> None:
        """TC2: absolute types with unit set always raises ValueError."""
        with pytest.raises(ValueError, match="does not accept unit"):
            TimeComparison(type=tc_type, unit=unit, date=date)  # type: ignore[arg-type]

    def test_relative_without_unit_raises(self) -> None:
        """TC1: type='relative' without unit always raises ValueError."""
        with pytest.raises(ValueError, match="requires unit"):
            TimeComparison(type="relative")

    @given(tc_type=st.sampled_from(["absolute-start", "absolute-end"]))
    def test_absolute_without_date_raises(self, tc_type: str) -> None:
        """TC2: absolute types without date always raises ValueError."""
        with pytest.raises(ValueError, match="requires date"):
            TimeComparison(type=tc_type)  # type: ignore[arg-type]

    @given(
        tc_type=st.sampled_from(["absolute-start", "absolute-end"]),
        bad_date=st.text(min_size=1, max_size=20).filter(
            lambda s: not __import__("re").match(r"^\d{4}-\d{2}-\d{2}$", s)
        ),
    )
    def test_absolute_with_bad_date_format_raises(
        self, tc_type: str, bad_date: str
    ) -> None:
        """TC3: absolute types with non-YYYY-MM-DD date always raises ValueError."""
        with pytest.raises(ValueError, match="YYYY-MM-DD"):
            TimeComparison(type=tc_type, date=bad_date)  # type: ignore[arg-type]

    @given(unit=time_comparison_units)
    def test_relative_is_frozen(self, unit: str) -> None:
        """TimeComparison instances are immutable (frozen dataclass)."""
        tc = TimeComparison.relative(unit)  # type: ignore[arg-type]
        with pytest.raises(dataclasses.FrozenInstanceError):
            tc.unit = "day"  # type: ignore[misc]


# =============================================================================
# FrequencyBreakdown Property Tests (Phase 040)
# =============================================================================


class TestFrequencyBreakdownProperties:
    """Property-based tests for FrequencyBreakdown construction and validation."""

    @given(
        event=event_names,
        bucket_size=st.integers(min_value=1, max_value=1000),
        bucket_max=st.integers(min_value=2, max_value=10000),
    )
    def test_valid_construction_never_raises(
        self, event: str, bucket_size: int, bucket_max: int
    ) -> None:
        """Valid FrequencyBreakdown construction never raises.

        Uses bucket_min=0 (default) and ensures bucket_max > 0.
        """
        fb = FrequencyBreakdown(
            event=event, bucket_size=bucket_size, bucket_min=0, bucket_max=bucket_max
        )
        assert fb.event == event
        assert fb.bucket_size == bucket_size
        assert fb.bucket_min < fb.bucket_max

    @given(
        event=event_names,
        bucket_min=st.integers(min_value=0, max_value=100),
        gap=st.integers(min_value=1, max_value=1000),
    )
    def test_bucket_min_always_less_than_max(
        self, event: str, bucket_min: int, gap: int
    ) -> None:
        """For any valid FrequencyBreakdown, bucket_min < bucket_max holds."""
        bucket_max = bucket_min + gap
        fb = FrequencyBreakdown(
            event=event, bucket_min=bucket_min, bucket_max=bucket_max
        )
        assert fb.bucket_min < fb.bucket_max

    @given(
        bad_event=st.just(""),
        bucket_size=st.integers(min_value=1, max_value=100),
    )
    def test_empty_event_raises(self, bad_event: str, bucket_size: int) -> None:
        """FB1: empty event name always raises ValueError."""
        with pytest.raises(ValueError, match="non-empty"):
            FrequencyBreakdown(event=bad_event, bucket_size=bucket_size)

    @given(
        event=event_names,
        bad_size=st.integers(min_value=-100, max_value=0),
    )
    def test_non_positive_bucket_size_raises(self, event: str, bad_size: int) -> None:
        """FB2: non-positive bucket_size always raises ValueError."""
        with pytest.raises(ValueError, match="bucket_size must be positive"):
            FrequencyBreakdown(event=event, bucket_size=bad_size)

    @given(
        event=event_names,
        same_val=st.integers(min_value=0, max_value=1000),
    )
    def test_bucket_min_equals_max_raises(self, event: str, same_val: int) -> None:
        """FB3: bucket_min == bucket_max always raises ValueError."""
        with pytest.raises(ValueError, match="less than bucket_max"):
            FrequencyBreakdown(event=event, bucket_min=same_val, bucket_max=same_val)

    @given(
        event=event_names,
        bad_min=st.integers(min_value=-1000, max_value=-1),
    )
    def test_negative_bucket_min_raises(self, event: str, bad_min: int) -> None:
        """FB4: negative bucket_min always raises ValueError."""
        with pytest.raises(ValueError, match="non-negative"):
            FrequencyBreakdown(event=event, bucket_min=bad_min, bucket_max=bad_min + 10)

    @given(event=event_names)
    def test_frozen_instance(self, event: str) -> None:
        """FrequencyBreakdown instances are immutable (frozen dataclass)."""
        fb = FrequencyBreakdown(event=event)
        with pytest.raises(dataclasses.FrozenInstanceError):
            fb.event = "other"  # type: ignore[misc]


# =============================================================================
# FrequencyFilter Property Tests (Phase 040)
# =============================================================================

valid_ff_operators = st.sampled_from(sorted(VALID_FREQUENCY_FILTER_OPERATORS))


class TestFrequencyFilterProperties:
    """Property-based tests for FrequencyFilter construction and validation."""

    @given(
        event=event_names,
        operator=valid_ff_operators,
        value=st.integers(min_value=0, max_value=10000),
    )
    def test_valid_construction_never_raises(
        self, event: str, operator: str, value: int
    ) -> None:
        """Valid FrequencyFilter construction (no date range) never raises."""
        ff = FrequencyFilter(event=event, operator=operator, value=value)  # type: ignore[arg-type]
        assert ff.event == event
        assert ff.operator == operator
        assert ff.value == value
        assert ff.date_range_value is None
        assert ff.date_range_unit is None

    @given(
        event=event_names,
        operator=valid_ff_operators,
        value=st.integers(min_value=0, max_value=10000),
        dr_value=st.integers(min_value=1, max_value=365),
        dr_unit=st.sampled_from(["day", "week", "month"]),
    )
    def test_valid_with_date_range_never_raises(
        self, event: str, operator: str, value: int, dr_value: int, dr_unit: str
    ) -> None:
        """Valid FrequencyFilter with date range pair never raises."""
        ff = FrequencyFilter(
            event=event,
            operator=operator,  # type: ignore[arg-type]
            value=value,
            date_range_value=dr_value,
            date_range_unit=dr_unit,  # type: ignore[arg-type]
        )
        assert ff.date_range_value == dr_value
        assert ff.date_range_unit == dr_unit

    @given(
        event=event_names,
        bad_op=st.text(min_size=1, max_size=30).filter(
            lambda s: s not in VALID_FREQUENCY_FILTER_OPERATORS
        ),
        value=st.integers(min_value=0, max_value=100),
    )
    def test_invalid_operator_raises(self, event: str, bad_op: str, value: int) -> None:
        """FF2: invalid operator always raises ValueError."""
        with pytest.raises(ValueError, match="operator must be one of"):
            FrequencyFilter(event=event, operator=bad_op, value=value)  # type: ignore[arg-type]

    @given(
        event=event_names,
        operator=valid_ff_operators,
        bad_value=st.integers(min_value=-10000, max_value=-1),
    )
    def test_negative_value_raises(
        self, event: str, operator: str, bad_value: int
    ) -> None:
        """FF3: negative value always raises ValueError."""
        with pytest.raises(ValueError, match="non-negative"):
            FrequencyFilter(event=event, operator=operator, value=bad_value)  # type: ignore[arg-type]

    @given(
        event=event_names,
        operator=valid_ff_operators,
        value=st.integers(min_value=0, max_value=100),
        dr_value=st.integers(min_value=1, max_value=365),
    )
    def test_date_range_value_without_unit_raises(
        self, event: str, operator: str, value: int, dr_value: int
    ) -> None:
        """FF4: date_range_value without date_range_unit always raises."""
        with pytest.raises(ValueError, match="both be set or both be None"):
            FrequencyFilter(
                event=event,
                operator=operator,  # type: ignore[arg-type]
                value=value,
                date_range_value=dr_value,
                date_range_unit=None,
            )

    @given(
        event=event_names,
        operator=valid_ff_operators,
        value=st.integers(min_value=0, max_value=100),
        dr_unit=st.sampled_from(["day", "week", "month"]),
    )
    def test_date_range_unit_without_value_raises(
        self, event: str, operator: str, value: int, dr_unit: str
    ) -> None:
        """FF4: date_range_unit without date_range_value always raises."""
        with pytest.raises(ValueError, match="both be set or both be None"):
            FrequencyFilter(
                event=event,
                operator=operator,  # type: ignore[arg-type]
                value=value,
                date_range_value=None,
                date_range_unit=dr_unit,  # type: ignore[arg-type]
            )

    @given(
        event=event_names,
        operator=valid_ff_operators,
        value=st.integers(min_value=0, max_value=100),
        bad_dr_value=st.integers(min_value=-100, max_value=0),
        dr_unit=st.sampled_from(["day", "week", "month"]),
    )
    def test_non_positive_date_range_value_raises(
        self, event: str, operator: str, value: int, bad_dr_value: int, dr_unit: str
    ) -> None:
        """FF5: non-positive date_range_value always raises ValueError."""
        with pytest.raises(ValueError, match="positive when set"):
            FrequencyFilter(
                event=event,
                operator=operator,  # type: ignore[arg-type]
                value=value,
                date_range_value=bad_dr_value,
                date_range_unit=dr_unit,  # type: ignore[arg-type]
            )

    @given(
        bad_event=st.just(""),
        operator=valid_ff_operators,
        value=st.integers(min_value=0, max_value=100),
    )
    def test_empty_event_raises(
        self, bad_event: str, operator: str, value: int
    ) -> None:
        """FF1: empty event name always raises ValueError."""
        with pytest.raises(ValueError, match="non-empty"):
            FrequencyFilter(event=bad_event, operator=operator, value=value)  # type: ignore[arg-type]

    @given(event=event_names)
    def test_frozen_instance(self, event: str) -> None:
        """FrequencyFilter instances are immutable (frozen dataclass)."""
        ff = FrequencyFilter(event=event, value=1)
        with pytest.raises(dataclasses.FrozenInstanceError):
            ff.value = 99  # type: ignore[misc]


# =============================================================================
# MathType / Metric Exhaustive Property Tests (Phase 040)
# =============================================================================

# Math types that require a property argument
_MATH_REQUIRING_PROPERTY: frozenset[str] = frozenset(
    {
        "average",
        "median",
        "min",
        "max",
        "p25",
        "p75",
        "p90",
        "p99",
        "percentile",
        "histogram",
        "unique_values",
        "most_frequent",
        "first_value",
        "multi_attribution",
        "numeric_summary",
    }
)

# All 22 MathType values from the Literal definition
_ALL_MATH_TYPES: tuple[str, ...] = get_args(MathType)


class TestMathTypeMetricProperties:
    """Property-based tests verifying all MathType values are accepted by Metric."""

    @given(math=st.sampled_from(_ALL_MATH_TYPES))
    def test_all_math_types_accepted_by_metric(self, math: str) -> None:
        """Every MathType value produces a valid Metric when property requirements are met.

        For math types requiring a property, passes property="test_prop".
        For math="percentile", also passes percentile_value=50.
        """
        kwargs: dict[str, object] = {"event": "TestEvent", "math": math}
        if math in _MATH_REQUIRING_PROPERTY:
            kwargs["property"] = "test_prop"
        if math == "percentile":
            kwargs["percentile_value"] = 50
        m = Metric(**kwargs)  # type: ignore[arg-type]
        assert m.math == math
        assert m.event == "TestEvent"

    @given(
        math=st.sampled_from(
            [m for m in _ALL_MATH_TYPES if m in _MATH_REQUIRING_PROPERTY]
        )
    )
    def test_property_required_math_without_property_raises(self, math: str) -> None:
        """Math types requiring a property raise ValueError when property is None."""
        kwargs: dict[str, object] = {"event": "TestEvent", "math": math}
        if math == "percentile":
            kwargs["percentile_value"] = 50
        with pytest.raises(ValueError, match="requires a property"):
            Metric(**kwargs)  # type: ignore[arg-type]

    @given(
        math=st.sampled_from(
            [m for m in _ALL_MATH_TYPES if m not in _MATH_REQUIRING_PROPERTY]
        )
    )
    def test_non_property_math_without_property_succeeds(self, math: str) -> None:
        """Math types not requiring a property succeed without one."""
        m = Metric(event="TestEvent", math=math)  # type: ignore[arg-type]
        assert m.math == math
        assert m.property is None

    def test_percentile_without_value_raises(self) -> None:
        """math='percentile' without percentile_value raises ValueError."""
        with pytest.raises(ValueError, match="percentile_value"):
            Metric(event="TestEvent", math="percentile", property="amount")

    def test_math_type_count_is_22(self) -> None:
        """Verify MathType has exactly 22 values (guard against drift)."""
        assert len(_ALL_MATH_TYPES) == 22
