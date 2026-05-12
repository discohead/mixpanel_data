"""Unit tests for mixpanel_headless result types."""

from __future__ import annotations

import dataclasses
import json

import pandas as pd
import pytest

from mixpanel_headless.types import (
    CohortInfo,
    EventCountsResult,
    FunnelInfo,
    FunnelResult,
    FunnelResultStep,
    JQLResult,
    PropertyCountsResult,
    ResultWithDataFrame,
    RetentionResult,
    SavedCohort,
    SegmentationResult,
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
    """Tests for FunnelResult and FunnelResultStep."""

    def test_funnel_step_creation(self) -> None:
        """Test creating a FunnelResultStep."""
        step = FunnelResultStep(
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
            FunnelResultStep(event="View", count=1000, conversion_rate=1.0),
            FunnelResultStep(event="Click", count=500, conversion_rate=0.5),
            FunnelResultStep(event="Purchase", count=100, conversion_rate=0.2),
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
            FunnelResultStep(event="A", count=100, conversion_rate=1.0),
            FunnelResultStep(event="B", count=50, conversion_rate=0.5),
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
            FunnelResultStep(event="View", count=1000, conversion_rate=1.0),
            FunnelResultStep(event="Click", count=500, conversion_rate=0.5),
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
        steps = [FunnelResultStep(event="View", count=1000, conversion_rate=1.0)]
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
            FunnelResultStep(event="View", count=1000, conversion_rate=1.0),
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
            FunnelResultStep(event="e", count=0, conversion_rate=0),
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


# =============================================================================
# JQL Discovery Types Tests (Phase 016)
# =============================================================================


class TestPropertyValueCount:
    """Tests for PropertyValueCount."""

    def test_basic_creation(self) -> None:
        """Test creating a PropertyValueCount."""
        from mixpanel_headless.types import PropertyValueCount

        pvc = PropertyValueCount(value="US", count=1000, percentage=45.2)

        assert pvc.value == "US"
        assert pvc.count == 1000
        assert pvc.percentage == 45.2

    def test_with_none_value(self) -> None:
        """Test PropertyValueCount with None value."""
        from mixpanel_headless.types import PropertyValueCount

        pvc = PropertyValueCount(value=None, count=50, percentage=2.5)

        assert pvc.value is None
        assert pvc.count == 50

    def test_with_numeric_value(self) -> None:
        """Test PropertyValueCount with numeric value."""
        from mixpanel_headless.types import PropertyValueCount

        pvc = PropertyValueCount(value=42, count=100, percentage=10.0)

        assert pvc.value == 42

    def test_immutable(self) -> None:
        """PropertyValueCount should be immutable (frozen)."""
        from mixpanel_headless.types import PropertyValueCount

        pvc = PropertyValueCount(value="US", count=1000, percentage=45.2)

        with pytest.raises(dataclasses.FrozenInstanceError):
            pvc.count = 2000  # type: ignore[misc]

    def test_to_dict_serializable(self) -> None:
        """to_dict output should be JSON serializable."""
        from mixpanel_headless.types import PropertyValueCount

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
        from mixpanel_headless.types import (
            PropertyDistributionResult,
            PropertyValueCount,
        )

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
        from mixpanel_headless.types import PropertyDistributionResult

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
        from mixpanel_headless.types import PropertyDistributionResult

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
        from mixpanel_headless.types import (
            PropertyDistributionResult,
            PropertyValueCount,
        )

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
        from mixpanel_headless.types import PropertyDistributionResult

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
        from mixpanel_headless.types import PropertyDistributionResult

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
        from mixpanel_headless.types import (
            PropertyDistributionResult,
            PropertyValueCount,
        )

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
        from mixpanel_headless.types import NumericPropertySummaryResult

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
        from mixpanel_headless.types import NumericPropertySummaryResult

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
        from mixpanel_headless.types import NumericPropertySummaryResult

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
        from mixpanel_headless.types import DailyCount

        dc = DailyCount(date="2024-01-01", event="Purchase", count=523)

        assert dc.date == "2024-01-01"
        assert dc.event == "Purchase"
        assert dc.count == 523

    def test_immutable(self) -> None:
        """DailyCount should be immutable (frozen)."""
        from mixpanel_headless.types import DailyCount

        dc = DailyCount(date="2024-01-01", event="Purchase", count=100)

        with pytest.raises(dataclasses.FrozenInstanceError):
            dc.count = 200  # type: ignore[misc]

    def test_to_dict_serializable(self) -> None:
        """to_dict output should be JSON serializable."""
        from mixpanel_headless.types import DailyCount

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
        from mixpanel_headless.types import DailyCount, DailyCountsResult

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
        from mixpanel_headless.types import DailyCountsResult

        result = DailyCountsResult(
            from_date="2024-01-01",
            to_date="2024-01-31",
            events=None,
            counts=(),
        )

        assert result.events is None

    def test_immutable(self) -> None:
        """DailyCountsResult should be immutable (frozen)."""
        from mixpanel_headless.types import DailyCountsResult

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
        from mixpanel_headless.types import DailyCount, DailyCountsResult

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
        from mixpanel_headless.types import DailyCountsResult

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
        from mixpanel_headless.types import DailyCount, DailyCountsResult

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
        from mixpanel_headless.types import EngagementBucket

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
        from mixpanel_headless.types import EngagementBucket

        bucket = EngagementBucket(
            bucket_min=2,
            bucket_label="2-5",
            user_count=4521,
            percentage=30.4,
        )

        assert bucket.bucket_label == "2-5"

    def test_immutable(self) -> None:
        """EngagementBucket should be immutable (frozen)."""
        from mixpanel_headless.types import EngagementBucket

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
        from mixpanel_headless.types import EngagementBucket

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
        from mixpanel_headless.types import (
            EngagementBucket,
            EngagementDistributionResult,
        )

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
        from mixpanel_headless.types import EngagementDistributionResult

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
        from mixpanel_headless.types import EngagementDistributionResult

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
        from mixpanel_headless.types import (
            EngagementBucket,
            EngagementDistributionResult,
        )

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
        from mixpanel_headless.types import EngagementDistributionResult

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
        from mixpanel_headless.types import (
            EngagementBucket,
            EngagementDistributionResult,
        )

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
        from mixpanel_headless.types import PropertyCoverage

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
        from mixpanel_headless.types import PropertyCoverage

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
        from mixpanel_headless.types import PropertyCoverage

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
        from mixpanel_headless.types import PropertyCoverage

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
        from mixpanel_headless.types import PropertyCoverage, PropertyCoverageResult

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
        from mixpanel_headless.types import PropertyCoverageResult

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
        from mixpanel_headless.types import PropertyCoverageResult

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
        from mixpanel_headless.types import PropertyCoverage, PropertyCoverageResult

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
        from mixpanel_headless.types import PropertyCoverageResult

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
        from mixpanel_headless.types import PropertyCoverage, PropertyCoverageResult

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
        from mixpanel_headless.types import ProfilePageResult

        profiles = [
            {"$distinct_id": "user1", "$properties": {"name": "Alice"}},
            {"$distinct_id": "user2", "$properties": {"name": "Bob"}},
        ]
        result = ProfilePageResult(
            profiles=profiles,
            session_id="abc123",
            page=0,
            has_more=True,
            total=5000,
            page_size=1000,
        )

        assert result.profiles == profiles
        assert result.session_id == "abc123"
        assert result.page == 0
        assert result.has_more is True
        assert result.total == 5000
        assert result.page_size == 1000

    def test_create_last_page(self) -> None:
        """ProfilePageResult should handle last page with no session_id."""
        from mixpanel_headless.types import ProfilePageResult

        result = ProfilePageResult(
            profiles=[{"$distinct_id": "user1"}],
            session_id=None,
            page=5,
            has_more=False,
            total=5001,
            page_size=1000,
        )

        assert result.session_id is None
        assert result.has_more is False
        assert result.page == 5

    def test_to_dict(self) -> None:
        """to_dict should serialize all fields including profile_count."""
        from mixpanel_headless.types import ProfilePageResult

        profiles = [
            {"$distinct_id": "user1"},
            {"$distinct_id": "user2"},
        ]
        result = ProfilePageResult(
            profiles=profiles,
            session_id="session123",
            page=2,
            has_more=True,
            total=5000,
            page_size=1000,
        )

        data = result.to_dict()

        assert data["profiles"] == profiles
        assert data["session_id"] == "session123"
        assert data["page"] == 2
        assert data["has_more"] is True
        assert data["profile_count"] == 2
        assert data["total"] == 5000
        assert data["page_size"] == 1000
        assert data["num_pages"] == 5

    def test_to_dict_json_serializable(self) -> None:
        """to_dict output should be JSON serializable."""
        from mixpanel_headless.types import ProfilePageResult

        result = ProfilePageResult(
            profiles=[
                {"$distinct_id": "user1", "$properties": {"email": "test@example.com"}}
            ],
            session_id="session123",
            page=0,
            has_more=True,
            total=1000,
            page_size=1000,
        )

        data = result.to_dict()
        json_str = json.dumps(data)

        assert "session123" in json_str
        assert "profile_count" in json_str
        assert "total" in json_str
        assert "num_pages" in json_str

    def test_frozen_dataclass(self) -> None:
        """ProfilePageResult should be immutable."""
        from mixpanel_headless.types import ProfilePageResult

        result = ProfilePageResult(
            profiles=[],
            session_id=None,
            page=0,
            has_more=False,
            total=0,
            page_size=1000,
        )

        with pytest.raises(dataclasses.FrozenInstanceError):
            result.page = 1  # type: ignore[misc]


class TestProfilePageResultPagination:
    """Tests for ProfilePageResult total, page_size, and num_pages fields.

    These fields enable pre-computing the total number of pages for parallel
    fetching, allowing all pages to be submitted at once rather than dynamic
    discovery via has_more flag.
    """

    def test_profile_page_result_includes_total_field(self) -> None:
        """ProfilePageResult should include total field from API response.

        The Mixpanel Engage API returns total count of matching profiles,
        which enables calculating total pages for parallel fetching.
        """
        from mixpanel_headless.types import ProfilePageResult

        result = ProfilePageResult(
            profiles=[],
            session_id="session_abc",
            page=0,
            has_more=True,
            total=5000,
            page_size=1000,
        )
        assert result.total == 5000

    def test_profile_page_result_includes_page_size_field(self) -> None:
        """ProfilePageResult should include page_size field from API response.

        The API returns page_size (typically 1000), needed to calculate
        total number of pages.
        """
        from mixpanel_headless.types import ProfilePageResult

        result = ProfilePageResult(
            profiles=[],
            session_id="session_abc",
            page=0,
            has_more=True,
            total=5000,
            page_size=1000,
        )
        assert result.page_size == 1000

    def test_num_pages_property_computes_ceiling(self) -> None:
        """num_pages should compute ceil(total / page_size).

        When total doesn't divide evenly, an extra partial page is needed.
        """
        from mixpanel_headless.types import ProfilePageResult

        result = ProfilePageResult(
            profiles=[],
            session_id="session_abc",
            page=0,
            has_more=True,
            total=5432,
            page_size=1000,
        )
        # ceil(5432/1000) = 6
        assert result.num_pages == 6

    def test_num_pages_exact_division(self) -> None:
        """num_pages should be exact when total divides evenly by page_size."""
        from mixpanel_headless.types import ProfilePageResult

        result = ProfilePageResult(
            profiles=[],
            session_id="session_abc",
            page=0,
            has_more=True,
            total=5000,
            page_size=1000,
        )
        # 5000 / 1000 = 5 exactly
        assert result.num_pages == 5

    def test_num_pages_empty_result_returns_zero(self) -> None:
        """num_pages should return 0 when total is 0.

        An empty result set has no pages to fetch.
        """
        from mixpanel_headless.types import ProfilePageResult

        result = ProfilePageResult(
            profiles=[],
            session_id=None,
            page=0,
            has_more=False,
            total=0,
            page_size=1000,
        )
        assert result.num_pages == 0

    def test_num_pages_single_page(self) -> None:
        """num_pages should be 1 when total is less than page_size."""
        from mixpanel_headless.types import ProfilePageResult

        result = ProfilePageResult(
            profiles=[{"$distinct_id": "user1"}],
            session_id=None,
            page=0,
            has_more=False,
            total=500,
            page_size=1000,
        )
        # 500 < 1000, so only 1 page needed
        assert result.num_pages == 1

    def test_to_dict_includes_pagination_fields(self) -> None:
        """to_dict should include total, page_size, and num_pages."""
        from mixpanel_headless.types import ProfilePageResult

        result = ProfilePageResult(
            profiles=[{"$distinct_id": "user1"}],
            session_id="session_abc",
            page=0,
            has_more=True,
            total=5000,
            page_size=1000,
        )
        d = result.to_dict()

        assert d["total"] == 5000
        assert d["page_size"] == 1000
        assert d["num_pages"] == 5


class TestCustomEventExports:
    """Custom event types must be importable from the top-level package."""

    def test_create_custom_event_params_importable(self) -> None:
        """CreateCustomEventParams is reachable via the top-level package."""
        from mixpanel_headless import CreateCustomEventParams

        assert CreateCustomEventParams.__name__ == "CreateCustomEventParams"

    def test_custom_event_importable(self) -> None:
        """CustomEvent is reachable via the top-level package."""
        from mixpanel_headless import CustomEvent

        assert CustomEvent.__name__ == "CustomEvent"

    def test_custom_event_alternative_importable(self) -> None:
        """CustomEventAlternative is reachable via the top-level package."""
        from mixpanel_headless import CustomEventAlternative

        assert CustomEventAlternative.__name__ == "CustomEventAlternative"

    def test_listed_in_dunder_all(self) -> None:
        """All three custom event types are advertised in mixpanel_headless.__all__."""
        import mixpanel_headless

        assert "CreateCustomEventParams" in mixpanel_headless.__all__
        assert "CustomEvent" in mixpanel_headless.__all__
        assert "CustomEventAlternative" in mixpanel_headless.__all__


class TestSubPropertyInfo:
    """Tests for SubPropertyInfo serialization (Phase 5 of PR #128 review)."""

    def test_to_dict_returns_lists_for_sample_values(self) -> None:
        """``to_dict()`` converts the immutable tuple to a JSON-serializable list."""
        from mixpanel_headless import SubPropertyInfo

        sp = SubPropertyInfo(
            name="Brand", type="string", sample_values=("nike", "puma")
        )
        result = sp.to_dict()
        assert result == {
            "name": "Brand",
            "type": "string",
            "sample_values": ["nike", "puma"],
        }
        # The sample_values value must be a list (not tuple) for JSON.
        assert isinstance(result["sample_values"], list)
        # And the result must round-trip through json.dumps without error.
        assert json.loads(json.dumps(result)) == result
