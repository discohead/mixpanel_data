"""Unit tests for mixpanel_data result types."""

from __future__ import annotations

import dataclasses
import json
from datetime import datetime

import pandas as pd
import pytest

from mixpanel_data.types import (
    CohortInfo,
    EventCountsResult,
    FetchResult,
    FunnelInfo,
    FunnelResult,
    FunnelStep,
    JQLResult,
    PropertyCountsResult,
    ResultWithDataFrame,
    RetentionResult,
    SavedCohort,
    SegmentationResult,
    TableMetadata,
    TopEvent,
)


class TestResultWithDataFrame:
    """Tests for ResultWithDataFrame base class."""

    def test_base_class_requires_df_property_implementation(self) -> None:
        """Subclasses must implement df property or raise NotImplementedError."""

        # Create a minimal subclass without implementing df
        @dataclasses.dataclass(frozen=True)
        class MinimalResult(ResultWithDataFrame):
            value: int

        result = MinimalResult(value=42)

        with pytest.raises(NotImplementedError, match="must implement df property"):
            _ = result.df

    def test_to_table_dict_with_implemented_df(self) -> None:
        """to_table_dict should use df property to create list of dicts."""

        # Create a subclass with proper df implementation
        @dataclasses.dataclass(frozen=True)
        class TestResult(ResultWithDataFrame):
            data: dict[str, int] = dataclasses.field(default_factory=dict)

            @property
            def df(self) -> pd.DataFrame:
                if self._df_cache is not None:
                    return self._df_cache

                rows = [{"key": k, "value": v} for k, v in self.data.items()]
                result_df = pd.DataFrame(rows)
                object.__setattr__(self, "_df_cache", result_df)
                return result_df

        result = TestResult(data={"a": 1, "b": 2, "c": 3})
        table_dict = result.to_table_dict()

        assert isinstance(table_dict, list)
        assert len(table_dict) == 3
        assert all(isinstance(item, dict) for item in table_dict)
        assert all("key" in item and "value" in item for item in table_dict)

        # Verify specific values
        assert {"key": "a", "value": 1} in table_dict
        assert {"key": "b", "value": 2} in table_dict
        assert {"key": "c", "value": 3} in table_dict

    def test_to_table_dict_empty_dataframe(self) -> None:
        """to_table_dict should return empty list for empty DataFrame."""

        @dataclasses.dataclass(frozen=True)
        class EmptyResult(ResultWithDataFrame):
            @property
            def df(self) -> pd.DataFrame:
                return pd.DataFrame()

        result = EmptyResult()
        table_dict = result.to_table_dict()

        assert isinstance(table_dict, list)
        assert len(table_dict) == 0

    def test_to_table_dict_json_serializable(self) -> None:
        """to_table_dict output should be JSON serializable."""

        @dataclasses.dataclass(frozen=True)
        class SerializableResult(ResultWithDataFrame):
            @property
            def df(self) -> pd.DataFrame:
                return pd.DataFrame(
                    [
                        {"date": "2024-01-01", "count": 100},
                        {"date": "2024-01-02", "count": 200},
                    ]
                )

        result = SerializableResult()
        table_dict = result.to_table_dict()
        json_str = json.dumps(table_dict)

        assert isinstance(json_str, str)
        parsed = json.loads(json_str)
        assert isinstance(parsed, list)
        assert len(parsed) == 2
        assert parsed[0]["date"] == "2024-01-01"
        assert parsed[0]["count"] == 100

    def test_df_caching_works(self) -> None:
        """df should be cached in _df_cache after first access."""

        @dataclasses.dataclass(frozen=True)
        class CachedResult(ResultWithDataFrame):
            compute_count: int = dataclasses.field(default=0, init=False, repr=False)

            @property
            def df(self) -> pd.DataFrame:
                if self._df_cache is not None:
                    return self._df_cache

                # Increment counter to track how many times df is computed
                object.__setattr__(self, "compute_count", self.compute_count + 1)

                result_df = pd.DataFrame([{"value": 42}])
                object.__setattr__(self, "_df_cache", result_df)
                return result_df

        result = CachedResult()

        # First access computes df
        df1 = result.df
        assert result.compute_count == 1

        # Second access uses cache
        df2 = result.df
        assert result.compute_count == 1  # Not incremented
        assert df1 is df2  # Same object

    def test_multiple_result_types_can_inherit(self) -> None:
        """Multiple result types can inherit from ResultWithDataFrame."""

        @dataclasses.dataclass(frozen=True)
        class ResultTypeA(ResultWithDataFrame):
            value_a: str

            @property
            def df(self) -> pd.DataFrame:
                return pd.DataFrame([{"type": "A", "value": self.value_a}])

        @dataclasses.dataclass(frozen=True)
        class ResultTypeB(ResultWithDataFrame):
            value_b: int

            @property
            def df(self) -> pd.DataFrame:
                return pd.DataFrame([{"type": "B", "value": self.value_b}])

        result_a = ResultTypeA(value_a="test")
        result_b = ResultTypeB(value_b=123)

        table_a = result_a.to_table_dict()
        table_b = result_b.to_table_dict()

        assert table_a == [{"type": "A", "value": "test"}]
        assert table_b == [{"type": "B", "value": 123}]


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

    def test_df_cached(self) -> None:
        """df should be cached on first access."""
        result = SegmentationResult(
            event="Purchase",
            from_date="2024-01-01",
            to_date="2024-01-31",
            unit="day",
            segment_property=None,
            total=0,
            series={},
        )

        df1 = result.df
        df2 = result.df
        assert df1 is df2  # Same object, not recomputed

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

    def test_df_cached(self) -> None:
        """df should be cached on first access."""
        steps = [FunnelStep(event="View", count=1000, conversion_rate=1.0)]
        result = FunnelResult(
            funnel_id=1,
            funnel_name="Test",
            from_date="2024-01-01",
            to_date="2024-01-31",
            conversion_rate=1.0,
            steps=steps,
        )

        df1 = result.df
        df2 = result.df
        assert df1 is df2  # Same object, not recomputed

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

    def test_df_cached(self) -> None:
        """df should be cached on first access."""
        cohorts = [CohortInfo(date="2024-01-01", size=1000, retention=[1.0, 0.5])]
        result = RetentionResult(
            born_event="Sign Up",
            return_event="Purchase",
            from_date="2024-01-01",
            to_date="2024-01-31",
            unit="week",
            cohorts=cohorts,
        )

        df1 = result.df
        df2 = result.df
        assert df1 is df2  # Same object, not recomputed

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

    def test_df_cached(self) -> None:
        """df should be cached on first access."""
        result = JQLResult(_raw=[{"a": 1}, {"a": 2}])

        df1 = result.df
        df2 = result.df
        assert df1 is df2  # Same object, not recomputed

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


# =============================================================================
# Discovery Types Tests
# =============================================================================


class TestFunnelInfo:
    """Tests for FunnelInfo."""

    def test_basic_creation(self) -> None:
        """Test creating a FunnelInfo."""
        info = FunnelInfo(funnel_id=12345, name="Checkout Funnel")

        assert info.funnel_id == 12345
        assert info.name == "Checkout Funnel"

    def test_immutable(self) -> None:
        """FunnelInfo should be immutable (frozen)."""
        info = FunnelInfo(funnel_id=12345, name="Checkout Funnel")

        with pytest.raises(dataclasses.FrozenInstanceError):
            info.name = "Modified"  # type: ignore[misc]

    def test_to_dict_serializable(self) -> None:
        """to_dict output should be JSON serializable."""
        info = FunnelInfo(funnel_id=12345, name="Checkout Funnel")

        data = info.to_dict()
        json_str = json.dumps(data)

        assert "12345" in json_str
        assert "Checkout Funnel" in json_str
        assert data["funnel_id"] == 12345
        assert data["name"] == "Checkout Funnel"


class TestSavedCohort:
    """Tests for SavedCohort."""

    def test_basic_creation(self) -> None:
        """Test creating a SavedCohort."""
        cohort = SavedCohort(
            id=456,
            name="Power Users",
            count=1500,
            description="Users with 10+ purchases",
            created="2024-01-15 10:30:00",
            is_visible=True,
        )

        assert cohort.id == 456
        assert cohort.name == "Power Users"
        assert cohort.count == 1500
        assert cohort.description == "Users with 10+ purchases"
        assert cohort.created == "2024-01-15 10:30:00"
        assert cohort.is_visible is True

    def test_immutable(self) -> None:
        """SavedCohort should be immutable (frozen)."""
        cohort = SavedCohort(
            id=456,
            name="Power Users",
            count=1500,
            description="",
            created="2024-01-15 10:30:00",
            is_visible=True,
        )

        with pytest.raises(dataclasses.FrozenInstanceError):
            cohort.count = 2000  # type: ignore[misc]

    def test_to_dict_serializable(self) -> None:
        """to_dict output should be JSON serializable."""
        cohort = SavedCohort(
            id=456,
            name="Power Users",
            count=1500,
            description="Users with 10+ purchases",
            created="2024-01-15 10:30:00",
            is_visible=True,
        )

        data = cohort.to_dict()
        json_str = json.dumps(data)

        assert "Power Users" in json_str
        assert data["id"] == 456
        assert data["count"] == 1500
        assert data["is_visible"] is True


class TestTopEvent:
    """Tests for TopEvent."""

    def test_basic_creation(self) -> None:
        """Test creating a TopEvent."""
        event = TopEvent(
            event="Sign Up",
            count=1500,
            percent_change=0.25,
        )

        assert event.event == "Sign Up"
        assert event.count == 1500
        assert event.percent_change == 0.25

    def test_negative_percent_change(self) -> None:
        """TopEvent should accept negative percent_change."""
        event = TopEvent(
            event="Purchase",
            count=500,
            percent_change=-0.15,
        )

        assert event.percent_change == -0.15

    def test_immutable(self) -> None:
        """TopEvent should be immutable (frozen)."""
        event = TopEvent(event="Test", count=100, percent_change=0.0)

        with pytest.raises(dataclasses.FrozenInstanceError):
            event.count = 200  # type: ignore[misc]

    def test_to_dict_serializable(self) -> None:
        """to_dict output should be JSON serializable."""
        event = TopEvent(
            event="Sign Up",
            count=1500,
            percent_change=0.25,
        )

        data = event.to_dict()
        json_str = json.dumps(data)

        assert "Sign Up" in json_str
        assert data["count"] == 1500
        assert data["percent_change"] == 0.25


class TestEventCountsResult:
    """Tests for EventCountsResult."""

    def test_basic_creation(self) -> None:
        """Test creating an EventCountsResult."""
        result = EventCountsResult(
            events=["Sign Up", "Purchase"],
            from_date="2024-01-01",
            to_date="2024-01-31",
            unit="day",
            type="general",
            series={
                "Sign Up": {"2024-01-01": 100, "2024-01-02": 150},
                "Purchase": {"2024-01-01": 50, "2024-01-02": 75},
            },
        )

        assert result.events == ["Sign Up", "Purchase"]
        assert result.from_date == "2024-01-01"
        assert result.unit == "day"
        assert result.type == "general"

    def test_df_has_expected_columns(self) -> None:
        """df should have date, event, count columns."""
        result = EventCountsResult(
            events=["Sign Up", "Purchase"],
            from_date="2024-01-01",
            to_date="2024-01-02",
            unit="day",
            type="general",
            series={
                "Sign Up": {"2024-01-01": 100, "2024-01-02": 150},
                "Purchase": {"2024-01-01": 50, "2024-01-02": 75},
            },
        )

        df = result.df
        assert "date" in df.columns
        assert "event" in df.columns
        assert "count" in df.columns
        assert len(df) == 4  # 2 events × 2 dates

    def test_df_empty_series(self) -> None:
        """df should handle empty series."""
        result = EventCountsResult(
            events=[],
            from_date="2024-01-01",
            to_date="2024-01-31",
            unit="day",
            type="general",
            series={},
        )

        df = result.df
        assert len(df) == 0
        assert "date" in df.columns

    def test_df_cached(self) -> None:
        """df should be cached on first access."""
        result = EventCountsResult(
            events=["Test"],
            from_date="2024-01-01",
            to_date="2024-01-01",
            unit="day",
            type="general",
            series={"Test": {"2024-01-01": 100}},
        )

        df1 = result.df
        df2 = result.df
        assert df1 is df2

    def test_immutable(self) -> None:
        """EventCountsResult should be immutable (frozen)."""
        result = EventCountsResult(
            events=["Test"],
            from_date="2024-01-01",
            to_date="2024-01-01",
            unit="day",
            type="general",
            series={},
        )

        with pytest.raises(dataclasses.FrozenInstanceError):
            result.events = ["Modified"]  # type: ignore[misc]

    def test_to_dict_serializable(self) -> None:
        """to_dict output should be JSON serializable."""
        result = EventCountsResult(
            events=["Sign Up"],
            from_date="2024-01-01",
            to_date="2024-01-31",
            unit="day",
            type="general",
            series={"Sign Up": {"2024-01-01": 100}},
        )

        data = result.to_dict()
        json_str = json.dumps(data)

        assert "Sign Up" in json_str
        assert data["unit"] == "day"
        assert data["type"] == "general"


class TestPropertyCountsResult:
    """Tests for PropertyCountsResult."""

    def test_basic_creation(self) -> None:
        """Test creating a PropertyCountsResult."""
        result = PropertyCountsResult(
            event="Purchase",
            property_name="country",
            from_date="2024-01-01",
            to_date="2024-01-31",
            unit="day",
            type="general",
            series={
                "US": {"2024-01-01": 100, "2024-01-02": 150},
                "CA": {"2024-01-01": 50, "2024-01-02": 75},
            },
        )

        assert result.event == "Purchase"
        assert result.property_name == "country"
        assert result.from_date == "2024-01-01"

    def test_df_has_expected_columns(self) -> None:
        """df should have date, value, count columns."""
        result = PropertyCountsResult(
            event="Purchase",
            property_name="country",
            from_date="2024-01-01",
            to_date="2024-01-02",
            unit="day",
            type="general",
            series={
                "US": {"2024-01-01": 100, "2024-01-02": 150},
                "CA": {"2024-01-01": 50, "2024-01-02": 75},
            },
        )

        df = result.df
        assert "date" in df.columns
        assert "value" in df.columns
        assert "count" in df.columns
        assert len(df) == 4  # 2 values × 2 dates

    def test_df_empty_series(self) -> None:
        """df should handle empty series."""
        result = PropertyCountsResult(
            event="Purchase",
            property_name="country",
            from_date="2024-01-01",
            to_date="2024-01-31",
            unit="day",
            type="general",
            series={},
        )

        df = result.df
        assert len(df) == 0
        assert "date" in df.columns

    def test_df_cached(self) -> None:
        """df should be cached on first access."""
        result = PropertyCountsResult(
            event="Purchase",
            property_name="country",
            from_date="2024-01-01",
            to_date="2024-01-01",
            unit="day",
            type="general",
            series={"US": {"2024-01-01": 100}},
        )

        df1 = result.df
        df2 = result.df
        assert df1 is df2

    def test_immutable(self) -> None:
        """PropertyCountsResult should be immutable (frozen)."""
        result = PropertyCountsResult(
            event="Purchase",
            property_name="country",
            from_date="2024-01-01",
            to_date="2024-01-01",
            unit="day",
            type="general",
            series={},
        )

        with pytest.raises(dataclasses.FrozenInstanceError):
            result.event = "Modified"  # type: ignore[misc]

    def test_to_dict_serializable(self) -> None:
        """to_dict output should be JSON serializable."""
        result = PropertyCountsResult(
            event="Purchase",
            property_name="country",
            from_date="2024-01-01",
            to_date="2024-01-31",
            unit="day",
            type="general",
            series={"US": {"2024-01-01": 100}},
        )

        data = result.to_dict()
        json_str = json.dumps(data)

        assert "Purchase" in json_str
        assert data["property_name"] == "country"


class TestTableMetadata:
    """Tests for TableMetadata."""

    def test_basic_creation(self) -> None:
        """Test creating a TableMetadata with minimal fields."""
        metadata = TableMetadata(
            type="profiles",
            fetched_at=datetime(2024, 1, 15, 12, 0, 0),
        )

        assert metadata.type == "profiles"
        assert metadata.fetched_at == datetime(2024, 1, 15, 12, 0, 0)
        assert metadata.from_date is None
        assert metadata.to_date is None
        assert metadata.filter_events is None
        assert metadata.filter_where is None

    def test_with_cohort_id(self) -> None:
        """Test creating TableMetadata with cohort_id filter."""
        metadata = TableMetadata(
            type="profiles",
            fetched_at=datetime(2024, 1, 15, 12, 0, 0),
            filter_cohort_id="cohort_12345",
        )

        assert metadata.filter_cohort_id == "cohort_12345"

    def test_with_output_properties(self) -> None:
        """Test creating TableMetadata with output_properties filter."""
        metadata = TableMetadata(
            type="profiles",
            fetched_at=datetime(2024, 1, 15, 12, 0, 0),
            filter_output_properties=["$email", "$name", "plan"],
        )

        assert metadata.filter_output_properties == ["$email", "$name", "plan"]

    def test_with_all_filters(self) -> None:
        """Test creating TableMetadata with all filter fields."""
        metadata = TableMetadata(
            type="events",
            fetched_at=datetime(2024, 1, 15, 12, 0, 0),
            from_date="2024-01-01",
            to_date="2024-01-31",
            filter_events=["Purchase", "Signup"],
            filter_where='properties["plan"] == "premium"',
            filter_cohort_id="cohort_abc",
            filter_output_properties=["$email"],
        )

        assert metadata.filter_events == ["Purchase", "Signup"]
        assert metadata.filter_where == 'properties["plan"] == "premium"'
        assert metadata.filter_cohort_id == "cohort_abc"
        assert metadata.filter_output_properties == ["$email"]

    def test_to_dict_includes_new_fields(self) -> None:
        """to_dict should include filter_cohort_id and filter_output_properties."""
        metadata = TableMetadata(
            type="profiles",
            fetched_at=datetime(2024, 1, 15, 12, 0, 0),
            filter_cohort_id="cohort_123",
            filter_output_properties=["$email", "$name"],
        )

        data = metadata.to_dict()

        assert data["filter_cohort_id"] == "cohort_123"
        assert data["filter_output_properties"] == ["$email", "$name"]

    def test_to_dict_serializable(self) -> None:
        """to_dict output should be JSON serializable."""
        metadata = TableMetadata(
            type="profiles",
            fetched_at=datetime(2024, 1, 15, 12, 0, 0),
            filter_cohort_id="cohort_123",
            filter_output_properties=["$email"],
        )

        data = metadata.to_dict()
        json_str = json.dumps(data)

        assert "cohort_123" in json_str
        assert "$email" in json_str

    def test_immutable(self) -> None:
        """TableMetadata should be immutable (frozen)."""
        metadata = TableMetadata(
            type="profiles",
            fetched_at=datetime(2024, 1, 15, 12, 0, 0),
        )

        with pytest.raises(dataclasses.FrozenInstanceError):
            metadata.type = "events"  # type: ignore[misc]


# =============================================================================
# SQLResult Tests
# =============================================================================


class TestSQLResult:
    """Tests for SQLResult dataclass."""

    def test_basic_creation(self) -> None:
        """Test creating an SQLResult with columns and rows."""
        from mixpanel_data.types import SQLResult

        result = SQLResult(
            columns=["name", "age"],
            rows=[("Alice", 30), ("Bob", 25)],
        )

        assert result.columns == ["name", "age"]
        assert result.rows == [("Alice", 30), ("Bob", 25)]

    def test_immutable(self) -> None:
        """SQLResult should be immutable (frozen)."""
        from mixpanel_data.types import SQLResult

        result = SQLResult(columns=["x"], rows=[(1,)])

        with pytest.raises(dataclasses.FrozenInstanceError):
            result.columns = ["y"]  # type: ignore[misc]

    def test_len_returns_row_count(self) -> None:
        """len(SQLResult) should return number of rows."""
        from mixpanel_data.types import SQLResult

        result = SQLResult(
            columns=["a", "b"],
            rows=[(1, 2), (3, 4), (5, 6)],
        )

        assert len(result) == 3

    def test_iter_yields_rows(self) -> None:
        """Iterating SQLResult should yield row tuples."""
        from mixpanel_data.types import SQLResult

        result = SQLResult(
            columns=["x", "y"],
            rows=[(1, 2), (3, 4)],
        )

        rows = list(result)
        assert rows == [(1, 2), (3, 4)]

    def test_to_dicts_converts_rows_to_list_of_dicts(self) -> None:
        """to_dicts() should convert rows to list of dicts with column keys."""
        from mixpanel_data.types import SQLResult

        result = SQLResult(
            columns=["name", "count"],
            rows=[("Alice", 10), ("Bob", 20)],
        )

        dicts = result.to_dicts()

        assert dicts == [
            {"name": "Alice", "count": 10},
            {"name": "Bob", "count": 20},
        ]

    def test_to_dicts_empty_result(self) -> None:
        """to_dicts() should return empty list for empty result."""
        from mixpanel_data.types import SQLResult

        result = SQLResult(columns=["x", "y"], rows=[])

        assert result.to_dicts() == []

    def test_to_dicts_single_column(self) -> None:
        """to_dicts() should work with single column."""
        from mixpanel_data.types import SQLResult

        result = SQLResult(columns=["value"], rows=[(1,), (2,), (3,)])

        dicts = result.to_dicts()

        assert dicts == [{"value": 1}, {"value": 2}, {"value": 3}]

    def test_to_dict_serializable(self) -> None:
        """to_dict() should be JSON serializable."""
        from mixpanel_data.types import SQLResult

        result = SQLResult(
            columns=["event", "count"],
            rows=[("Signup", 100), ("Login", 200)],
        )

        data = result.to_dict()
        json_str = json.dumps(data)

        assert "columns" in json_str
        assert "rows" in json_str
        assert data["columns"] == ["event", "count"]
        assert data["rows"] == [["Signup", 100], ["Login", 200]]
        assert data["row_count"] == 2

    def test_empty_columns_and_rows(self) -> None:
        """SQLResult should handle empty columns and rows."""
        from mixpanel_data.types import SQLResult

        result = SQLResult(columns=[], rows=[])

        assert len(result) == 0
        assert result.to_dicts() == []


# =============================================================================
# JQL Discovery Types Tests (Phase 016)
# =============================================================================


class TestPropertyValueCount:
    """Tests for PropertyValueCount."""

    def test_basic_creation(self) -> None:
        """Test creating a PropertyValueCount."""
        from mixpanel_data.types import PropertyValueCount

        pvc = PropertyValueCount(value="US", count=1000, percentage=45.2)

        assert pvc.value == "US"
        assert pvc.count == 1000
        assert pvc.percentage == 45.2

    def test_with_none_value(self) -> None:
        """Test PropertyValueCount with None value."""
        from mixpanel_data.types import PropertyValueCount

        pvc = PropertyValueCount(value=None, count=50, percentage=2.5)

        assert pvc.value is None
        assert pvc.count == 50

    def test_with_numeric_value(self) -> None:
        """Test PropertyValueCount with numeric value."""
        from mixpanel_data.types import PropertyValueCount

        pvc = PropertyValueCount(value=42, count=100, percentage=10.0)

        assert pvc.value == 42

    def test_immutable(self) -> None:
        """PropertyValueCount should be immutable (frozen)."""
        from mixpanel_data.types import PropertyValueCount

        pvc = PropertyValueCount(value="US", count=1000, percentage=45.2)

        with pytest.raises(dataclasses.FrozenInstanceError):
            pvc.count = 2000  # type: ignore[misc]

    def test_to_dict_serializable(self) -> None:
        """to_dict output should be JSON serializable."""
        from mixpanel_data.types import PropertyValueCount

        pvc = PropertyValueCount(value="US", count=1000, percentage=45.2)

        data = pvc.to_dict()
        json_str = json.dumps(data)

        assert "US" in json_str
        assert data["count"] == 1000
        assert data["percentage"] == 45.2


class TestPropertyDistributionResult:
    """Tests for PropertyDistributionResult."""

    def test_basic_creation(self) -> None:
        """Test creating a PropertyDistributionResult."""
        from mixpanel_data.types import PropertyDistributionResult, PropertyValueCount

        values = (
            PropertyValueCount(value="US", count=1000, percentage=50.0),
            PropertyValueCount(value="UK", count=500, percentage=25.0),
            PropertyValueCount(value="DE", count=500, percentage=25.0),
        )
        result = PropertyDistributionResult(
            event="Purchase",
            property_name="country",
            from_date="2024-01-01",
            to_date="2024-01-31",
            total_count=2000,
            values=values,
        )

        assert result.event == "Purchase"
        assert result.property_name == "country"
        assert result.total_count == 2000
        assert len(result.values) == 3

    def test_empty_values(self) -> None:
        """Test PropertyDistributionResult with empty values."""
        from mixpanel_data.types import PropertyDistributionResult

        result = PropertyDistributionResult(
            event="Purchase",
            property_name="country",
            from_date="2024-01-01",
            to_date="2024-01-31",
            total_count=0,
            values=(),
        )

        assert result.total_count == 0
        assert len(result.values) == 0

    def test_immutable(self) -> None:
        """PropertyDistributionResult should be immutable (frozen)."""
        from mixpanel_data.types import PropertyDistributionResult

        result = PropertyDistributionResult(
            event="Purchase",
            property_name="country",
            from_date="2024-01-01",
            to_date="2024-01-31",
            total_count=100,
            values=(),
        )

        with pytest.raises(dataclasses.FrozenInstanceError):
            result.total_count = 200  # type: ignore[misc]

    def test_df_has_expected_columns(self) -> None:
        """df should have value, count, percentage columns."""
        from mixpanel_data.types import PropertyDistributionResult, PropertyValueCount

        values = (
            PropertyValueCount(value="US", count=1000, percentage=50.0),
            PropertyValueCount(value="UK", count=500, percentage=25.0),
        )
        result = PropertyDistributionResult(
            event="Purchase",
            property_name="country",
            from_date="2024-01-01",
            to_date="2024-01-31",
            total_count=1500,
            values=values,
        )

        df = result.df
        assert "value" in df.columns
        assert "count" in df.columns
        assert "percentage" in df.columns
        assert len(df) == 2

    def test_df_empty_values(self) -> None:
        """df should handle empty values."""
        from mixpanel_data.types import PropertyDistributionResult

        result = PropertyDistributionResult(
            event="Purchase",
            property_name="country",
            from_date="2024-01-01",
            to_date="2024-01-31",
            total_count=0,
            values=(),
        )

        df = result.df
        assert len(df) == 0
        assert "value" in df.columns

    def test_df_cached(self) -> None:
        """df should be cached on first access."""
        from mixpanel_data.types import PropertyDistributionResult

        result = PropertyDistributionResult(
            event="Purchase",
            property_name="country",
            from_date="2024-01-01",
            to_date="2024-01-31",
            total_count=0,
            values=(),
        )

        df1 = result.df
        df2 = result.df
        assert df1 is df2

    def test_to_dict_serializable(self) -> None:
        """to_dict output should be JSON serializable."""
        from mixpanel_data.types import PropertyDistributionResult, PropertyValueCount

        values = (PropertyValueCount(value="US", count=1000, percentage=100.0),)
        result = PropertyDistributionResult(
            event="Purchase",
            property_name="country",
            from_date="2024-01-01",
            to_date="2024-01-31",
            total_count=1000,
            values=values,
        )

        data = result.to_dict()
        json_str = json.dumps(data)

        assert "Purchase" in json_str
        assert data["property_name"] == "country"
        assert len(data["values"]) == 1


class TestNumericPropertySummaryResult:
    """Tests for NumericPropertySummaryResult."""

    def test_basic_creation(self) -> None:
        """Test creating a NumericPropertySummaryResult."""
        from mixpanel_data.types import NumericPropertySummaryResult

        result = NumericPropertySummaryResult(
            event="Purchase",
            property_name="amount",
            from_date="2024-01-01",
            to_date="2024-01-31",
            count=10000,
            min=1.0,
            max=9999.0,
            sum=1562300.0,
            avg=156.23,
            stddev=234.56,
            percentiles={
                25: 45.0,
                50: 98.0,
                75: 189.0,
                90: 356.0,
                95: 567.0,
                99: 1234.0,
            },
        )

        assert result.event == "Purchase"
        assert result.property_name == "amount"
        assert result.count == 10000
        assert result.min == 1.0
        assert result.max == 9999.0
        assert result.avg == 156.23
        assert result.percentiles[50] == 98.0

    def test_immutable(self) -> None:
        """NumericPropertySummaryResult should be immutable (frozen)."""
        from mixpanel_data.types import NumericPropertySummaryResult

        result = NumericPropertySummaryResult(
            event="Purchase",
            property_name="amount",
            from_date="2024-01-01",
            to_date="2024-01-31",
            count=100,
            min=1.0,
            max=100.0,
            sum=5000.0,
            avg=50.0,
            stddev=10.0,
            percentiles={},
        )

        with pytest.raises(dataclasses.FrozenInstanceError):
            result.count = 200  # type: ignore[misc]

    def test_to_dict_serializable(self) -> None:
        """to_dict output should be JSON serializable."""
        from mixpanel_data.types import NumericPropertySummaryResult

        result = NumericPropertySummaryResult(
            event="Purchase",
            property_name="amount",
            from_date="2024-01-01",
            to_date="2024-01-31",
            count=1000,
            min=1.0,
            max=1000.0,
            sum=50000.0,
            avg=50.0,
            stddev=25.0,
            percentiles={50: 45.0, 90: 200.0},
        )

        data = result.to_dict()
        json_str = json.dumps(data)

        assert "Purchase" in json_str
        assert data["property_name"] == "amount"
        assert data["min"] == 1.0
        assert data["percentiles"]["50"] == 45.0


class TestDailyCount:
    """Tests for DailyCount."""

    def test_basic_creation(self) -> None:
        """Test creating a DailyCount."""
        from mixpanel_data.types import DailyCount

        dc = DailyCount(date="2024-01-01", event="Purchase", count=523)

        assert dc.date == "2024-01-01"
        assert dc.event == "Purchase"
        assert dc.count == 523

    def test_immutable(self) -> None:
        """DailyCount should be immutable (frozen)."""
        from mixpanel_data.types import DailyCount

        dc = DailyCount(date="2024-01-01", event="Purchase", count=100)

        with pytest.raises(dataclasses.FrozenInstanceError):
            dc.count = 200  # type: ignore[misc]

    def test_to_dict_serializable(self) -> None:
        """to_dict output should be JSON serializable."""
        from mixpanel_data.types import DailyCount

        dc = DailyCount(date="2024-01-01", event="Purchase", count=523)

        data = dc.to_dict()
        json_str = json.dumps(data)

        assert "2024-01-01" in json_str
        assert data["event"] == "Purchase"
        assert data["count"] == 523


class TestDailyCountsResult:
    """Tests for DailyCountsResult."""

    def test_basic_creation(self) -> None:
        """Test creating a DailyCountsResult."""
        from mixpanel_data.types import DailyCount, DailyCountsResult

        counts = (
            DailyCount(date="2024-01-01", event="Purchase", count=523),
            DailyCount(date="2024-01-01", event="Signup", count=89),
            DailyCount(date="2024-01-02", event="Purchase", count=612),
        )
        result = DailyCountsResult(
            from_date="2024-01-01",
            to_date="2024-01-02",
            events=("Purchase", "Signup"),
            counts=counts,
        )

        assert result.from_date == "2024-01-01"
        assert result.events == ("Purchase", "Signup")
        assert len(result.counts) == 3

    def test_with_none_events(self) -> None:
        """Test DailyCountsResult with None events (all events)."""
        from mixpanel_data.types import DailyCountsResult

        result = DailyCountsResult(
            from_date="2024-01-01",
            to_date="2024-01-31",
            events=None,
            counts=(),
        )

        assert result.events is None

    def test_immutable(self) -> None:
        """DailyCountsResult should be immutable (frozen)."""
        from mixpanel_data.types import DailyCountsResult

        result = DailyCountsResult(
            from_date="2024-01-01",
            to_date="2024-01-31",
            events=None,
            counts=(),
        )

        with pytest.raises(dataclasses.FrozenInstanceError):
            result.from_date = "2024-02-01"  # type: ignore[misc]

    def test_df_has_expected_columns(self) -> None:
        """df should have date, event, count columns."""
        from mixpanel_data.types import DailyCount, DailyCountsResult

        counts = (
            DailyCount(date="2024-01-01", event="Purchase", count=100),
            DailyCount(date="2024-01-02", event="Purchase", count=150),
        )
        result = DailyCountsResult(
            from_date="2024-01-01",
            to_date="2024-01-02",
            events=("Purchase",),
            counts=counts,
        )

        df = result.df
        assert "date" in df.columns
        assert "event" in df.columns
        assert "count" in df.columns
        assert len(df) == 2

    def test_df_cached(self) -> None:
        """df should be cached on first access."""
        from mixpanel_data.types import DailyCountsResult

        result = DailyCountsResult(
            from_date="2024-01-01",
            to_date="2024-01-31",
            events=None,
            counts=(),
        )

        df1 = result.df
        df2 = result.df
        assert df1 is df2

    def test_to_dict_serializable(self) -> None:
        """to_dict output should be JSON serializable."""
        from mixpanel_data.types import DailyCount, DailyCountsResult

        counts = (DailyCount(date="2024-01-01", event="Purchase", count=100),)
        result = DailyCountsResult(
            from_date="2024-01-01",
            to_date="2024-01-31",
            events=("Purchase",),
            counts=counts,
        )

        data = result.to_dict()
        json_str = json.dumps(data)

        assert "2024-01-01" in json_str
        assert len(data["counts"]) == 1


class TestEngagementBucket:
    """Tests for EngagementBucket."""

    def test_basic_creation(self) -> None:
        """Test creating an EngagementBucket."""
        from mixpanel_data.types import EngagementBucket

        bucket = EngagementBucket(
            bucket_min=1,
            bucket_label="1",
            user_count=5234,
            percentage=35.2,
        )

        assert bucket.bucket_min == 1
        assert bucket.bucket_label == "1"
        assert bucket.user_count == 5234
        assert bucket.percentage == 35.2

    def test_with_range_label(self) -> None:
        """Test EngagementBucket with range label."""
        from mixpanel_data.types import EngagementBucket

        bucket = EngagementBucket(
            bucket_min=2,
            bucket_label="2-5",
            user_count=4521,
            percentage=30.4,
        )

        assert bucket.bucket_label == "2-5"

    def test_immutable(self) -> None:
        """EngagementBucket should be immutable (frozen)."""
        from mixpanel_data.types import EngagementBucket

        bucket = EngagementBucket(
            bucket_min=1,
            bucket_label="1",
            user_count=100,
            percentage=10.0,
        )

        with pytest.raises(dataclasses.FrozenInstanceError):
            bucket.user_count = 200  # type: ignore[misc]

    def test_to_dict_serializable(self) -> None:
        """to_dict output should be JSON serializable."""
        from mixpanel_data.types import EngagementBucket

        bucket = EngagementBucket(
            bucket_min=1,
            bucket_label="1",
            user_count=5234,
            percentage=35.2,
        )

        data = bucket.to_dict()
        json_str = json.dumps(data)

        assert data["bucket_min"] == 1
        assert data["user_count"] == 5234
        assert "35.2" in json_str


class TestEngagementDistributionResult:
    """Tests for EngagementDistributionResult."""

    def test_basic_creation(self) -> None:
        """Test creating an EngagementDistributionResult."""
        from mixpanel_data.types import EngagementBucket, EngagementDistributionResult

        buckets = (
            EngagementBucket(
                bucket_min=1, bucket_label="1", user_count=5234, percentage=35.2
            ),
            EngagementBucket(
                bucket_min=2, bucket_label="2-5", user_count=4521, percentage=30.4
            ),
        )
        result = EngagementDistributionResult(
            from_date="2024-01-01",
            to_date="2024-01-31",
            events=None,
            total_users=14876,
            buckets=buckets,
        )

        assert result.from_date == "2024-01-01"
        assert result.total_users == 14876
        assert len(result.buckets) == 2

    def test_with_filtered_events(self) -> None:
        """Test EngagementDistributionResult with filtered events."""
        from mixpanel_data.types import EngagementDistributionResult

        result = EngagementDistributionResult(
            from_date="2024-01-01",
            to_date="2024-01-31",
            events=("Purchase", "Signup"),
            total_users=1000,
            buckets=(),
        )

        assert result.events == ("Purchase", "Signup")

    def test_immutable(self) -> None:
        """EngagementDistributionResult should be immutable (frozen)."""
        from mixpanel_data.types import EngagementDistributionResult

        result = EngagementDistributionResult(
            from_date="2024-01-01",
            to_date="2024-01-31",
            events=None,
            total_users=1000,
            buckets=(),
        )

        with pytest.raises(dataclasses.FrozenInstanceError):
            result.total_users = 2000  # type: ignore[misc]

    def test_df_has_expected_columns(self) -> None:
        """df should have bucket_min, bucket_label, user_count, percentage columns."""
        from mixpanel_data.types import EngagementBucket, EngagementDistributionResult

        buckets = (
            EngagementBucket(
                bucket_min=1, bucket_label="1", user_count=100, percentage=50.0
            ),
            EngagementBucket(
                bucket_min=2, bucket_label="2-5", user_count=100, percentage=50.0
            ),
        )
        result = EngagementDistributionResult(
            from_date="2024-01-01",
            to_date="2024-01-31",
            events=None,
            total_users=200,
            buckets=buckets,
        )

        df = result.df
        assert "bucket_min" in df.columns
        assert "bucket_label" in df.columns
        assert "user_count" in df.columns
        assert "percentage" in df.columns
        assert len(df) == 2

    def test_df_cached(self) -> None:
        """df should be cached on first access."""
        from mixpanel_data.types import EngagementDistributionResult

        result = EngagementDistributionResult(
            from_date="2024-01-01",
            to_date="2024-01-31",
            events=None,
            total_users=0,
            buckets=(),
        )

        df1 = result.df
        df2 = result.df
        assert df1 is df2

    def test_to_dict_serializable(self) -> None:
        """to_dict output should be JSON serializable."""
        from mixpanel_data.types import EngagementBucket, EngagementDistributionResult

        buckets = (
            EngagementBucket(
                bucket_min=1, bucket_label="1", user_count=100, percentage=100.0
            ),
        )
        result = EngagementDistributionResult(
            from_date="2024-01-01",
            to_date="2024-01-31",
            events=None,
            total_users=100,
            buckets=buckets,
        )

        data = result.to_dict()
        json_str = json.dumps(data)

        assert data["total_users"] == 100
        assert len(data["buckets"]) == 1
        assert "2024-01-01" in json_str


class TestPropertyCoverage:
    """Tests for PropertyCoverage."""

    def test_basic_creation(self) -> None:
        """Test creating a PropertyCoverage."""
        from mixpanel_data.types import PropertyCoverage

        cov = PropertyCoverage(
            property="coupon_code",
            defined_count=2345,
            null_count=7655,
            coverage_percentage=23.45,
        )

        assert cov.property == "coupon_code"
        assert cov.defined_count == 2345
        assert cov.null_count == 7655
        assert cov.coverage_percentage == 23.45

    def test_full_coverage(self) -> None:
        """Test PropertyCoverage with 100% coverage."""
        from mixpanel_data.types import PropertyCoverage

        cov = PropertyCoverage(
            property="distinct_id",
            defined_count=10000,
            null_count=0,
            coverage_percentage=100.0,
        )

        assert cov.null_count == 0
        assert cov.coverage_percentage == 100.0

    def test_immutable(self) -> None:
        """PropertyCoverage should be immutable (frozen)."""
        from mixpanel_data.types import PropertyCoverage

        cov = PropertyCoverage(
            property="test",
            defined_count=100,
            null_count=0,
            coverage_percentage=100.0,
        )

        with pytest.raises(dataclasses.FrozenInstanceError):
            cov.defined_count = 200  # type: ignore[misc]

    def test_to_dict_serializable(self) -> None:
        """to_dict output should be JSON serializable."""
        from mixpanel_data.types import PropertyCoverage

        cov = PropertyCoverage(
            property="coupon_code",
            defined_count=2345,
            null_count=7655,
            coverage_percentage=23.45,
        )

        data = cov.to_dict()
        json_str = json.dumps(data)

        assert "coupon_code" in json_str
        assert data["defined_count"] == 2345


class TestPropertyCoverageResult:
    """Tests for PropertyCoverageResult."""

    def test_basic_creation(self) -> None:
        """Test creating a PropertyCoverageResult."""
        from mixpanel_data.types import PropertyCoverage, PropertyCoverageResult

        coverage = (
            PropertyCoverage("coupon_code", 2345, 7655, 23.45),
            PropertyCoverage("referrer", 8901, 1099, 89.01),
            PropertyCoverage("utm_source", 6789, 3211, 67.89),
        )
        result = PropertyCoverageResult(
            event="Purchase",
            from_date="2024-01-01",
            to_date="2024-01-31",
            total_events=10000,
            coverage=coverage,
        )

        assert result.event == "Purchase"
        assert result.total_events == 10000
        assert len(result.coverage) == 3

    def test_empty_coverage(self) -> None:
        """Test PropertyCoverageResult with empty coverage."""
        from mixpanel_data.types import PropertyCoverageResult

        result = PropertyCoverageResult(
            event="Purchase",
            from_date="2024-01-01",
            to_date="2024-01-31",
            total_events=0,
            coverage=(),
        )

        assert len(result.coverage) == 0

    def test_immutable(self) -> None:
        """PropertyCoverageResult should be immutable (frozen)."""
        from mixpanel_data.types import PropertyCoverageResult

        result = PropertyCoverageResult(
            event="Purchase",
            from_date="2024-01-01",
            to_date="2024-01-31",
            total_events=1000,
            coverage=(),
        )

        with pytest.raises(dataclasses.FrozenInstanceError):
            result.total_events = 2000  # type: ignore[misc]

    def test_df_has_expected_columns(self) -> None:
        """df should have property, defined_count, null_count, coverage_percentage."""
        from mixpanel_data.types import PropertyCoverage, PropertyCoverageResult

        coverage = (
            PropertyCoverage("prop1", 100, 0, 100.0),
            PropertyCoverage("prop2", 50, 50, 50.0),
        )
        result = PropertyCoverageResult(
            event="Purchase",
            from_date="2024-01-01",
            to_date="2024-01-31",
            total_events=100,
            coverage=coverage,
        )

        df = result.df
        assert "property" in df.columns
        assert "defined_count" in df.columns
        assert "null_count" in df.columns
        assert "coverage_percentage" in df.columns
        assert len(df) == 2

    def test_df_cached(self) -> None:
        """df should be cached on first access."""
        from mixpanel_data.types import PropertyCoverageResult

        result = PropertyCoverageResult(
            event="Purchase",
            from_date="2024-01-01",
            to_date="2024-01-31",
            total_events=0,
            coverage=(),
        )

        df1 = result.df
        df2 = result.df
        assert df1 is df2

    def test_to_dict_serializable(self) -> None:
        """to_dict output should be JSON serializable."""
        from mixpanel_data.types import PropertyCoverage, PropertyCoverageResult

        coverage = (PropertyCoverage("coupon_code", 100, 900, 10.0),)
        result = PropertyCoverageResult(
            event="Purchase",
            from_date="2024-01-01",
            to_date="2024-01-31",
            total_events=1000,
            coverage=coverage,
        )

        data = result.to_dict()
        json_str = json.dumps(data)

        assert "Purchase" in json_str
        assert data["total_events"] == 1000
        assert len(data["coverage"]) == 1


# =============================================================================
# Parallel Profile Fetch Types (Phase 019)
# =============================================================================


class TestProfilePageResult:
    """Tests for ProfilePageResult type."""

    def test_create_with_profiles(self) -> None:
        """ProfilePageResult should hold page data and metadata."""
        from mixpanel_data.types import ProfilePageResult

        profiles = [
            {"$distinct_id": "user1", "$properties": {"name": "Alice"}},
            {"$distinct_id": "user2", "$properties": {"name": "Bob"}},
        ]
        result = ProfilePageResult(
            profiles=profiles,
            session_id="abc123",
            page=0,
            has_more=True,
        )

        assert result.profiles == profiles
        assert result.session_id == "abc123"
        assert result.page == 0
        assert result.has_more is True

    def test_create_last_page(self) -> None:
        """ProfilePageResult should handle last page with no session_id."""
        from mixpanel_data.types import ProfilePageResult

        result = ProfilePageResult(
            profiles=[{"$distinct_id": "user1"}],
            session_id=None,
            page=5,
            has_more=False,
        )

        assert result.session_id is None
        assert result.has_more is False

    def test_to_dict(self) -> None:
        """to_dict should serialize all fields including profile_count."""
        from mixpanel_data.types import ProfilePageResult

        profiles = [
            {"$distinct_id": "user1"},
            {"$distinct_id": "user2"},
        ]
        result = ProfilePageResult(
            profiles=profiles,
            session_id="session123",
            page=2,
            has_more=True,
        )

        data = result.to_dict()

        assert data["profiles"] == profiles
        assert data["session_id"] == "session123"
        assert data["page"] == 2
        assert data["has_more"] is True
        assert data["profile_count"] == 2

    def test_to_dict_json_serializable(self) -> None:
        """to_dict output should be JSON serializable."""
        from mixpanel_data.types import ProfilePageResult

        result = ProfilePageResult(
            profiles=[
                {"$distinct_id": "user1", "$properties": {"email": "test@example.com"}}
            ],
            session_id="session123",
            page=0,
            has_more=True,
        )

        data = result.to_dict()
        json_str = json.dumps(data)

        assert "session123" in json_str
        assert "profile_count" in json_str

    def test_frozen_dataclass(self) -> None:
        """ProfilePageResult should be immutable."""
        from mixpanel_data.types import ProfilePageResult

        result = ProfilePageResult(
            profiles=[],
            session_id=None,
            page=0,
            has_more=False,
        )

        with pytest.raises(dataclasses.FrozenInstanceError):
            result.page = 1  # type: ignore[misc]


class TestProfileProgress:
    """Tests for ProfileProgress callback type."""

    def test_create_success_progress(self) -> None:
        """ProfileProgress should track successful page fetch."""
        from mixpanel_data.types import ProfileProgress

        progress = ProfileProgress(
            page_index=0,
            total_pages=None,
            rows=1000,
            success=True,
            error=None,
            cumulative_rows=1000,
        )

        assert progress.page_index == 0
        assert progress.total_pages is None
        assert progress.rows == 1000
        assert progress.success is True
        assert progress.error is None
        assert progress.cumulative_rows == 1000

    def test_create_failure_progress(self) -> None:
        """ProfileProgress should track failed page fetch."""
        from mixpanel_data.types import ProfileProgress

        progress = ProfileProgress(
            page_index=5,
            total_pages=10,
            rows=0,
            success=False,
            error="Rate limit exceeded",
            cumulative_rows=5000,
        )

        assert progress.page_index == 5
        assert progress.total_pages == 10
        assert progress.rows == 0
        assert progress.success is False
        assert progress.error == "Rate limit exceeded"
        assert progress.cumulative_rows == 5000

    def test_to_dict_success(self) -> None:
        """to_dict should serialize successful progress."""
        from mixpanel_data.types import ProfileProgress

        progress = ProfileProgress(
            page_index=0,
            total_pages=None,
            rows=1000,
            success=True,
            error=None,
            cumulative_rows=1000,
        )

        data = progress.to_dict()

        assert data["page_index"] == 0
        assert data["total_pages"] is None
        assert data["rows"] == 1000
        assert data["success"] is True
        assert data["error"] is None
        assert data["cumulative_rows"] == 1000

    def test_to_dict_failure(self) -> None:
        """to_dict should serialize failed progress."""
        from mixpanel_data.types import ProfileProgress

        progress = ProfileProgress(
            page_index=5,
            total_pages=10,
            rows=0,
            success=False,
            error="API error",
            cumulative_rows=5000,
        )

        data = progress.to_dict()

        assert data["page_index"] == 5
        assert data["total_pages"] == 10
        assert data["rows"] == 0
        assert data["success"] is False
        assert data["error"] == "API error"
        assert data["cumulative_rows"] == 5000

    def test_to_dict_json_serializable(self) -> None:
        """to_dict output should be JSON serializable."""
        from mixpanel_data.types import ProfileProgress

        progress = ProfileProgress(
            page_index=0,
            total_pages=None,
            rows=1000,
            success=True,
            error=None,
            cumulative_rows=1000,
        )

        data = progress.to_dict()
        json_str = json.dumps(data)

        assert "page_index" in json_str
        assert "cumulative_rows" in json_str

    def test_frozen_dataclass(self) -> None:
        """ProfileProgress should be immutable."""
        from mixpanel_data.types import ProfileProgress

        progress = ProfileProgress(
            page_index=0,
            total_pages=None,
            rows=1000,
            success=True,
            error=None,
            cumulative_rows=1000,
        )

        with pytest.raises(dataclasses.FrozenInstanceError):
            progress.page_index = 1  # type: ignore[misc]


class TestParallelProfileResult:
    """Tests for ParallelProfileResult type."""

    def test_create_success_result(self) -> None:
        """ParallelProfileResult should track successful parallel fetch."""
        from mixpanel_data.types import ParallelProfileResult

        now = datetime.now()
        result = ParallelProfileResult(
            table="my_profiles",
            total_rows=10000,
            successful_pages=10,
            failed_pages=0,
            failed_page_indices=(),
            duration_seconds=30.5,
            fetched_at=now,
        )

        assert result.table == "my_profiles"
        assert result.total_rows == 10000
        assert result.successful_pages == 10
        assert result.failed_pages == 0
        assert result.failed_page_indices == ()
        assert result.duration_seconds == 30.5
        assert result.fetched_at == now

    def test_create_partial_failure_result(self) -> None:
        """ParallelProfileResult should track partial failures."""
        from mixpanel_data.types import ParallelProfileResult

        now = datetime.now()
        result = ParallelProfileResult(
            table="profiles_with_issues",
            total_rows=8000,
            successful_pages=8,
            failed_pages=2,
            failed_page_indices=(5, 9),
            duration_seconds=45.0,
            fetched_at=now,
        )

        assert result.table == "profiles_with_issues"
        assert result.total_rows == 8000
        assert result.successful_pages == 8
        assert result.failed_pages == 2
        assert result.failed_page_indices == (5, 9)
        assert result.duration_seconds == 45.0

    def test_has_failures_true(self) -> None:
        """has_failures should return True when failed_pages > 0."""
        from mixpanel_data.types import ParallelProfileResult

        result = ParallelProfileResult(
            table="profiles",
            total_rows=8000,
            successful_pages=8,
            failed_pages=2,
            failed_page_indices=(5, 9),
            duration_seconds=45.0,
            fetched_at=datetime.now(),
        )

        assert result.has_failures is True

    def test_has_failures_false(self) -> None:
        """has_failures should return False when failed_pages == 0."""
        from mixpanel_data.types import ParallelProfileResult

        result = ParallelProfileResult(
            table="profiles",
            total_rows=10000,
            successful_pages=10,
            failed_pages=0,
            failed_page_indices=(),
            duration_seconds=30.0,
            fetched_at=datetime.now(),
        )

        assert result.has_failures is False

    def test_to_dict_success(self) -> None:
        """to_dict should serialize successful result."""
        from mixpanel_data.types import ParallelProfileResult

        now = datetime.now()
        result = ParallelProfileResult(
            table="profiles",
            total_rows=10000,
            successful_pages=10,
            failed_pages=0,
            failed_page_indices=(),
            duration_seconds=30.0,
            fetched_at=now,
        )

        data = result.to_dict()

        assert data["table"] == "profiles"
        assert data["total_rows"] == 10000
        assert data["successful_pages"] == 10
        assert data["failed_pages"] == 0
        assert data["failed_page_indices"] == []
        assert data["duration_seconds"] == 30.0
        assert data["fetched_at"] == now.isoformat()
        assert data["has_failures"] is False

    def test_to_dict_with_failures(self) -> None:
        """to_dict should serialize result with failures."""
        from mixpanel_data.types import ParallelProfileResult

        now = datetime.now()
        result = ParallelProfileResult(
            table="profiles",
            total_rows=8000,
            successful_pages=8,
            failed_pages=2,
            failed_page_indices=(5, 9),
            duration_seconds=45.0,
            fetched_at=now,
        )

        data = result.to_dict()

        assert data["failed_pages"] == 2
        assert data["failed_page_indices"] == [5, 9]
        assert data["has_failures"] is True

    def test_to_dict_json_serializable(self) -> None:
        """to_dict output should be JSON serializable."""
        from mixpanel_data.types import ParallelProfileResult

        result = ParallelProfileResult(
            table="profiles",
            total_rows=10000,
            successful_pages=10,
            failed_pages=0,
            failed_page_indices=(),
            duration_seconds=30.0,
            fetched_at=datetime.now(),
        )

        data = result.to_dict()
        json_str = json.dumps(data)

        assert "profiles" in json_str
        assert "successful_pages" in json_str
        assert "failed_page_indices" in json_str

    def test_frozen_dataclass(self) -> None:
        """ParallelProfileResult should be immutable."""
        from mixpanel_data.types import ParallelProfileResult

        result = ParallelProfileResult(
            table="profiles",
            total_rows=10000,
            successful_pages=10,
            failed_pages=0,
            failed_page_indices=(),
            duration_seconds=30.0,
            fetched_at=datetime.now(),
        )

        with pytest.raises(dataclasses.FrozenInstanceError):
            result.total_rows = 5000  # type: ignore[misc]
