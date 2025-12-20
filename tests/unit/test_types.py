"""Unit tests for mixpanel_data result types."""

from __future__ import annotations

import dataclasses
import json
from datetime import datetime

import pandas as pd
import pytest

from mixpanel_data.types import (
    CohortInfo,
    FetchResult,
    FunnelResult,
    FunnelStep,
    JQLResult,
    RetentionResult,
    SegmentationResult,
)


class TestFetchResult:
    """Tests for FetchResult."""

    def test_basic_creation(self) -> None:
        """Test creating a FetchResult."""
        result = FetchResult(
            table="january_events",
            rows=10000,
            type="events",
            duration_seconds=5.23,
            date_range=("2024-01-01", "2024-01-31"),
            fetched_at=datetime(2024, 1, 31, 12, 0, 0),
        )

        assert result.table == "january_events"
        assert result.rows == 10000
        assert result.type == "events"
        assert result.duration_seconds == 5.23
        assert result.date_range == ("2024-01-01", "2024-01-31")

    def test_immutable(self) -> None:
        """FetchResult should be immutable (frozen)."""
        result = FetchResult(
            table="test",
            rows=100,
            type="events",
            duration_seconds=1.0,
            date_range=None,
            fetched_at=datetime.now(),
        )

        with pytest.raises(dataclasses.FrozenInstanceError):
            result.rows = 200  # type: ignore[misc]

    def test_df_returns_dataframe(self) -> None:
        """df property should return a pandas DataFrame."""
        data = [
            {"event": "Click", "user_id": "123"},
            {"event": "View", "user_id": "456"},
        ]
        result = FetchResult(
            table="test",
            rows=2,
            type="events",
            duration_seconds=1.0,
            date_range=None,
            fetched_at=datetime.now(),
            _data=data,
        )

        df = result.df
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 2
        assert "event" in df.columns

    def test_df_empty_data(self) -> None:
        """df should handle empty data."""
        result = FetchResult(
            table="test",
            rows=0,
            type="events",
            duration_seconds=1.0,
            date_range=None,
            fetched_at=datetime.now(),
        )

        df = result.df
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 0

    def test_df_cached(self) -> None:
        """df should be cached on first access."""
        result = FetchResult(
            table="test",
            rows=0,
            type="events",
            duration_seconds=1.0,
            date_range=None,
            fetched_at=datetime.now(),
        )

        df1 = result.df
        df2 = result.df
        assert df1 is df2  # Same object, not recomputed

    def test_to_dict_serializable(self) -> None:
        """to_dict output should be JSON serializable."""
        result = FetchResult(
            table="january_events",
            rows=10000,
            type="events",
            duration_seconds=5.23,
            date_range=("2024-01-01", "2024-01-31"),
            fetched_at=datetime(2024, 1, 31, 12, 0, 0),
        )

        data = result.to_dict()

        # Should not raise
        json_str = json.dumps(data)
        assert "january_events" in json_str

        # Verify structure
        assert data["table"] == "january_events"
        assert data["rows"] == 10000
        assert data["fetched_at"] == "2024-01-31T12:00:00"

    def test_to_dict_excludes_internal_fields(self) -> None:
        """to_dict should not include internal data fields."""
        result = FetchResult(
            table="test",
            rows=1,
            type="events",
            duration_seconds=1.0,
            date_range=None,
            fetched_at=datetime.now(),
            _data=[{"a": 1}],
        )

        data = result.to_dict()
        assert "_data" not in data
        assert "_df_cache" not in data


class TestSegmentationResult:
    """Tests for SegmentationResult."""

    def test_basic_creation(self) -> None:
        """Test creating a SegmentationResult."""
        result = SegmentationResult(
            event="Purchase",
            from_date="2024-01-01",
            to_date="2024-01-31",
            unit="day",
            segment_property="country",
            total=5000,
            series={
                "US": {"2024-01-01": 100, "2024-01-02": 150},
                "EU": {"2024-01-01": 50, "2024-01-02": 75},
            },
        )

        assert result.event == "Purchase"
        assert result.total == 5000

    def test_df_has_expected_columns(self) -> None:
        """df should have date, segment, count columns."""
        result = SegmentationResult(
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

        df = result.df
        assert "date" in df.columns
        assert "segment" in df.columns
        assert "count" in df.columns
        assert len(df) == 4  # 2 segments × 2 dates

    def test_df_empty_series(self) -> None:
        """df should handle empty series."""
        result = SegmentationResult(
            event="Purchase",
            from_date="2024-01-01",
            to_date="2024-01-31",
            unit="day",
            segment_property=None,
            total=0,
            series={},
        )

        df = result.df
        assert len(df) == 0
        assert "date" in df.columns

    def test_to_dict_serializable(self) -> None:
        """to_dict should be JSON serializable."""
        result = SegmentationResult(
            event="Purchase",
            from_date="2024-01-01",
            to_date="2024-01-31",
            unit="day",
            segment_property="country",
            total=5000,
            series={"US": {"2024-01-01": 100}},
        )

        data = result.to_dict()
        json_str = json.dumps(data)
        assert "Purchase" in json_str


class TestFunnelResult:
    """Tests for FunnelResult and FunnelStep."""

    def test_funnel_step_creation(self) -> None:
        """Test creating a FunnelStep."""
        step = FunnelStep(
            event="Sign Up",
            count=1000,
            conversion_rate=1.0,
        )

        assert step.event == "Sign Up"
        assert step.count == 1000
        assert step.conversion_rate == 1.0

    def test_funnel_result_creation(self) -> None:
        """Test creating a FunnelResult."""
        steps = [
            FunnelStep(event="View", count=1000, conversion_rate=1.0),
            FunnelStep(event="Click", count=500, conversion_rate=0.5),
            FunnelStep(event="Purchase", count=100, conversion_rate=0.2),
        ]

        result = FunnelResult(
            funnel_id=12345,
            funnel_name="Checkout Funnel",
            from_date="2024-01-01",
            to_date="2024-01-31",
            conversion_rate=0.1,
            steps=steps,
        )

        assert result.funnel_id == 12345
        assert result.funnel_name == "Checkout Funnel"
        assert result.conversion_rate == 0.1
        assert len(result.steps) == 3

    def test_steps_iteration(self) -> None:
        """Steps should be iterable."""
        steps = [
            FunnelStep(event="A", count=100, conversion_rate=1.0),
            FunnelStep(event="B", count=50, conversion_rate=0.5),
        ]

        result = FunnelResult(
            funnel_id=1,
            funnel_name="Test",
            from_date="2024-01-01",
            to_date="2024-01-31",
            conversion_rate=0.5,
            steps=steps,
        )

        events = [step.event for step in result.steps]
        assert events == ["A", "B"]

    def test_df_has_expected_columns(self) -> None:
        """df should have step, event, count, conversion_rate columns."""
        steps = [
            FunnelStep(event="View", count=1000, conversion_rate=1.0),
            FunnelStep(event="Click", count=500, conversion_rate=0.5),
        ]

        result = FunnelResult(
            funnel_id=1,
            funnel_name="Test",
            from_date="2024-01-01",
            to_date="2024-01-31",
            conversion_rate=0.5,
            steps=steps,
        )

        df = result.df
        assert "step" in df.columns
        assert "event" in df.columns
        assert "count" in df.columns
        assert "conversion_rate" in df.columns
        assert len(df) == 2

    def test_to_dict_serializable(self) -> None:
        """to_dict should be JSON serializable."""
        steps = [
            FunnelStep(event="View", count=1000, conversion_rate=1.0),
        ]

        result = FunnelResult(
            funnel_id=1,
            funnel_name="Test",
            from_date="2024-01-01",
            to_date="2024-01-31",
            conversion_rate=1.0,
            steps=steps,
        )

        data = result.to_dict()
        json_str = json.dumps(data)
        assert "Test" in json_str
        assert len(data["steps"]) == 1


class TestRetentionResult:
    """Tests for RetentionResult and CohortInfo."""

    def test_cohort_info_creation(self) -> None:
        """Test creating a CohortInfo."""
        cohort = CohortInfo(
            date="2024-01-01",
            size=1000,
            retention=[1.0, 0.5, 0.3, 0.2],
        )

        assert cohort.date == "2024-01-01"
        assert cohort.size == 1000
        assert cohort.retention == [1.0, 0.5, 0.3, 0.2]

    def test_retention_result_creation(self) -> None:
        """Test creating a RetentionResult."""
        cohorts = [
            CohortInfo(date="2024-01-01", size=1000, retention=[1.0, 0.5]),
            CohortInfo(date="2024-01-08", size=800, retention=[1.0, 0.4]),
        ]

        result = RetentionResult(
            born_event="Sign Up",
            return_event="Purchase",
            from_date="2024-01-01",
            to_date="2024-01-31",
            unit="week",
            cohorts=cohorts,
        )

        assert result.born_event == "Sign Up"
        assert result.return_event == "Purchase"
        assert len(result.cohorts) == 2

    def test_df_has_expected_columns(self) -> None:
        """df should have cohort_date, cohort_size, period_N columns."""
        cohorts = [
            CohortInfo(date="2024-01-01", size=1000, retention=[1.0, 0.5, 0.3]),
        ]

        result = RetentionResult(
            born_event="Sign Up",
            return_event="Purchase",
            from_date="2024-01-01",
            to_date="2024-01-31",
            unit="week",
            cohorts=cohorts,
        )

        df = result.df
        assert "cohort_date" in df.columns
        assert "cohort_size" in df.columns
        assert "period_0" in df.columns
        assert "period_1" in df.columns
        assert "period_2" in df.columns

    def test_to_dict_serializable(self) -> None:
        """to_dict should be JSON serializable."""
        cohorts = [
            CohortInfo(date="2024-01-01", size=1000, retention=[1.0, 0.5]),
        ]

        result = RetentionResult(
            born_event="Sign Up",
            return_event="Purchase",
            from_date="2024-01-01",
            to_date="2024-01-31",
            unit="week",
            cohorts=cohorts,
        )

        data = result.to_dict()
        json_str = json.dumps(data)
        assert "Sign Up" in json_str


class TestJQLResult:
    """Tests for JQLResult."""

    def test_basic_creation(self) -> None:
        """Test creating a JQLResult."""
        result = JQLResult(_raw=[{"a": 1}, {"a": 2}])
        assert result.raw == [{"a": 1}, {"a": 2}]

    def test_df_from_dict_list(self) -> None:
        """df should convert list of dicts to DataFrame."""
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

    def test_df_from_simple_list(self) -> None:
        """df should wrap simple lists in 'value' column."""
        result = JQLResult(_raw=[1, 2, 3, 4, 5])

        df = result.df
        assert "value" in df.columns
        assert len(df) == 5

    def test_df_empty(self) -> None:
        """df should handle empty results."""
        result = JQLResult()

        df = result.df
        assert len(df) == 0

    def test_to_dict_serializable(self) -> None:
        """to_dict should be JSON serializable."""
        result = JQLResult(_raw=[{"key": "value"}])

        data = result.to_dict()
        json_str = json.dumps(data)
        assert "value" in json_str
        assert data["row_count"] == 1


class TestResultTypeImmutability:
    """Tests for immutability of all result types."""

    def test_all_result_types_frozen(self) -> None:
        """All result types should be frozen dataclasses."""
        results: list[object] = [
            FetchResult(
                table="t",
                rows=0,
                type="events",
                duration_seconds=0,
                date_range=None,
                fetched_at=datetime.now(),
            ),
            SegmentationResult(
                event="e",
                from_date="2024-01-01",
                to_date="2024-01-31",
                unit="day",
                segment_property=None,
                total=0,
            ),
            FunnelResult(
                funnel_id=1,
                funnel_name="f",
                from_date="2024-01-01",
                to_date="2024-01-31",
                conversion_rate=0,
                steps=[],
            ),
            RetentionResult(
                born_event="b",
                return_event="r",
                from_date="2024-01-01",
                to_date="2024-01-31",
                unit="day",
                cohorts=[],
            ),
            JQLResult(),
            FunnelStep(event="e", count=0, conversion_rate=0),
            CohortInfo(date="2024-01-01", size=0, retention=[]),
        ]

        for result in results:
            # Get any attribute name from the object
            attrs = [a for a in dir(result) if not a.startswith("_")]
            if attrs:
                with pytest.raises((TypeError, dataclasses.FrozenInstanceError)):
                    setattr(result, attrs[0], "modified")
