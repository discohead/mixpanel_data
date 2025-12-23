"""Unit tests for Phase 008 result types."""

from __future__ import annotations

import dataclasses
import json
from datetime import UTC, datetime

import pytest

from mixpanel_data.types import (
    ActivityFeedResult,
    FrequencyResult,
    InsightsResult,
    NumericAverageResult,
    NumericBucketResult,
    NumericSumResult,
    UserEvent,
)

# =============================================================================
# User Story 1: Activity Feed Types
# =============================================================================


class TestUserEvent:
    """Tests for UserEvent."""

    def test_basic_creation(self) -> None:
        """Test creating a UserEvent."""
        event_time = datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC)
        event = UserEvent(
            event="Sign Up",
            time=event_time,
            properties={"plan": "premium", "$distinct_id": "user_123"},
        )

        assert event.event == "Sign Up"
        assert event.time == event_time
        assert event.properties["plan"] == "premium"

    def test_immutable(self) -> None:
        """UserEvent should be immutable (frozen)."""
        event = UserEvent(
            event="Test",
            time=datetime.now(tz=UTC),
            properties={},
        )

        with pytest.raises(dataclasses.FrozenInstanceError):
            event.event = "Modified"  # type: ignore[misc]

    def test_to_dict_serializable(self) -> None:
        """to_dict output should be JSON serializable."""
        event = UserEvent(
            event="Sign Up",
            time=datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC),
            properties={"plan": "premium"},
        )

        data = event.to_dict()
        json_str = json.dumps(data)

        assert "Sign Up" in json_str
        assert data["event"] == "Sign Up"
        assert "2024-01-01" in data["time"]


class TestActivityFeedResult:
    """Tests for ActivityFeedResult."""

    def test_basic_creation(self) -> None:
        """Test creating an ActivityFeedResult."""
        events = [
            UserEvent(
                event="Sign Up",
                time=datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC),
                properties={"$distinct_id": "user_123"},
            ),
        ]
        result = ActivityFeedResult(
            distinct_ids=["user_123"],
            from_date="2024-01-01",
            to_date="2024-01-31",
            events=events,
        )

        assert result.distinct_ids == ["user_123"]
        assert result.from_date == "2024-01-01"
        assert len(result.events) == 1

    def test_df_has_expected_columns(self) -> None:
        """df should have event, time, distinct_id columns."""
        events = [
            UserEvent(
                event="Sign Up",
                time=datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC),
                properties={"$distinct_id": "user_123", "plan": "free"},
            ),
            UserEvent(
                event="Purchase",
                time=datetime(2024, 1, 2, 12, 0, 0, tzinfo=UTC),
                properties={"$distinct_id": "user_123", "amount": 99.99},
            ),
        ]
        result = ActivityFeedResult(
            distinct_ids=["user_123"],
            from_date="2024-01-01",
            to_date="2024-01-02",
            events=events,
        )

        df = result.df
        assert "event" in df.columns
        assert "time" in df.columns
        assert "distinct_id" in df.columns
        assert len(df) == 2

    def test_df_empty_events(self) -> None:
        """df should handle empty events list."""
        result = ActivityFeedResult(
            distinct_ids=["user_123"],
            from_date="2024-01-01",
            to_date="2024-01-31",
            events=[],
        )

        df = result.df
        assert len(df) == 0
        assert "event" in df.columns

    def test_df_cached(self) -> None:
        """df should be cached on first access."""
        result = ActivityFeedResult(
            distinct_ids=["user_123"],
            from_date=None,
            to_date=None,
            events=[],
        )

        df1 = result.df
        df2 = result.df
        assert df1 is df2

    def test_immutable(self) -> None:
        """ActivityFeedResult should be immutable (frozen)."""
        result = ActivityFeedResult(
            distinct_ids=["user_123"],
            from_date=None,
            to_date=None,
            events=[],
        )

        with pytest.raises(dataclasses.FrozenInstanceError):
            result.distinct_ids = ["modified"]  # type: ignore[misc]

    def test_to_dict_serializable(self) -> None:
        """to_dict output should be JSON serializable."""
        events = [
            UserEvent(
                event="Sign Up",
                time=datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC),
                properties={"$distinct_id": "user_123"},
            ),
        ]
        result = ActivityFeedResult(
            distinct_ids=["user_123"],
            from_date="2024-01-01",
            to_date="2024-01-31",
            events=events,
        )

        data = result.to_dict()
        json_str = json.dumps(data)

        assert "user_123" in json_str
        assert data["event_count"] == 1
        assert len(data["events"]) == 1


# =============================================================================
# User Story 2: Numeric Sum Types
# =============================================================================


class TestNumericSumResult:
    """Tests for NumericSumResult."""

    def test_basic_creation(self) -> None:
        """Test creating a NumericSumResult."""
        result = NumericSumResult(
            event="Purchase",
            from_date="2024-01-01",
            to_date="2024-01-31",
            property_expr='properties["amount"]',
            unit="day",
            results={"2024-01-01": 15432.50, "2024-01-02": 18976.25},
            computed_at="2024-01-31T23:02:11+00:00",
        )

        assert result.event == "Purchase"
        assert result.property_expr == 'properties["amount"]'
        assert result.results["2024-01-01"] == 15432.50

    def test_df_has_expected_columns(self) -> None:
        """df should have date, sum columns."""
        result = NumericSumResult(
            event="Purchase",
            from_date="2024-01-01",
            to_date="2024-01-02",
            property_expr='properties["amount"]',
            unit="day",
            results={"2024-01-01": 100.0, "2024-01-02": 200.0},
        )

        df = result.df
        assert "date" in df.columns
        assert "sum" in df.columns
        assert len(df) == 2

    def test_df_empty_results(self) -> None:
        """df should handle empty results."""
        result = NumericSumResult(
            event="Purchase",
            from_date="2024-01-01",
            to_date="2024-01-31",
            property_expr='properties["amount"]',
            unit="day",
            results={},
        )

        df = result.df
        assert len(df) == 0
        assert "date" in df.columns

    def test_to_dict_with_computed_at(self) -> None:
        """to_dict should include computed_at when present."""
        result = NumericSumResult(
            event="Purchase",
            from_date="2024-01-01",
            to_date="2024-01-31",
            property_expr='properties["amount"]',
            unit="day",
            results={"2024-01-01": 100.0},
            computed_at="2024-01-31T23:02:11+00:00",
        )

        data = result.to_dict()
        assert "computed_at" in data

    def test_to_dict_without_computed_at(self) -> None:
        """to_dict should exclude computed_at when None."""
        result = NumericSumResult(
            event="Purchase",
            from_date="2024-01-01",
            to_date="2024-01-31",
            property_expr='properties["amount"]',
            unit="day",
            results={"2024-01-01": 100.0},
        )

        data = result.to_dict()
        assert "computed_at" not in data


# =============================================================================
# User Story 3: Numeric Average Types
# =============================================================================


class TestNumericAverageResult:
    """Tests for NumericAverageResult."""

    def test_basic_creation(self) -> None:
        """Test creating a NumericAverageResult."""
        result = NumericAverageResult(
            event="Purchase",
            from_date="2024-01-01",
            to_date="2024-01-31",
            property_expr='properties["amount"]',
            unit="day",
            results={"2024-01-01": 54.32, "2024-01-02": 62.15},
        )

        assert result.event == "Purchase"
        assert result.results["2024-01-01"] == 54.32

    def test_df_has_expected_columns(self) -> None:
        """df should have date, average columns."""
        result = NumericAverageResult(
            event="Purchase",
            from_date="2024-01-01",
            to_date="2024-01-02",
            property_expr='properties["amount"]',
            unit="day",
            results={"2024-01-01": 50.0, "2024-01-02": 60.0},
        )

        df = result.df
        assert "date" in df.columns
        assert "average" in df.columns
        assert len(df) == 2

    def test_df_empty_results(self) -> None:
        """df should handle empty results."""
        result = NumericAverageResult(
            event="Purchase",
            from_date="2024-01-01",
            to_date="2024-01-31",
            property_expr='properties["amount"]',
            unit="day",
            results={},
        )

        df = result.df
        assert len(df) == 0
        assert "date" in df.columns

    def test_to_dict_serializable(self) -> None:
        """to_dict output should be JSON serializable."""
        result = NumericAverageResult(
            event="Purchase",
            from_date="2024-01-01",
            to_date="2024-01-31",
            property_expr='properties["amount"]',
            unit="day",
            results={"2024-01-01": 54.32},
        )

        data = result.to_dict()
        json_str = json.dumps(data)

        assert "Purchase" in json_str
        assert data["property_expr"] == 'properties["amount"]'


# =============================================================================
# User Story 4: Frequency Types
# =============================================================================


class TestFrequencyResult:
    """Tests for FrequencyResult."""

    def test_basic_creation(self) -> None:
        """Test creating a FrequencyResult."""
        result = FrequencyResult(
            event="App Open",
            from_date="2024-01-01",
            to_date="2024-01-07",
            unit="day",
            addiction_unit="hour",
            data={
                "2024-01-01": [305, 107, 60, 41, 32],
                "2024-01-02": [495, 204, 117, 77, 53],
            },
        )

        assert result.event == "App Open"
        assert result.unit == "day"
        assert result.addiction_unit == "hour"
        assert len(result.data["2024-01-01"]) == 5

    def test_df_has_expected_columns(self) -> None:
        """df should have date, period_N columns."""
        result = FrequencyResult(
            event="App Open",
            from_date="2024-01-01",
            to_date="2024-01-01",
            unit="day",
            addiction_unit="hour",
            data={"2024-01-01": [100, 50, 25]},
        )

        df = result.df
        assert "date" in df.columns
        assert "period_1" in df.columns
        assert "period_2" in df.columns
        assert "period_3" in df.columns
        assert len(df) == 1

    def test_df_empty_data(self) -> None:
        """df should handle empty data."""
        result = FrequencyResult(
            event=None,
            from_date="2024-01-01",
            to_date="2024-01-31",
            unit="day",
            addiction_unit="hour",
            data={},
        )

        df = result.df
        assert len(df) == 0
        assert "date" in df.columns

    def test_event_can_be_none(self) -> None:
        """event can be None for all events query."""
        result = FrequencyResult(
            event=None,
            from_date="2024-01-01",
            to_date="2024-01-31",
            unit="day",
            addiction_unit="hour",
            data={},
        )

        assert result.event is None

    def test_to_dict_serializable(self) -> None:
        """to_dict output should be JSON serializable."""
        result = FrequencyResult(
            event="App Open",
            from_date="2024-01-01",
            to_date="2024-01-07",
            unit="day",
            addiction_unit="hour",
            data={"2024-01-01": [100, 50]},
        )

        data = result.to_dict()
        json_str = json.dumps(data)

        assert "App Open" in json_str
        assert data["unit"] == "day"
        assert data["addiction_unit"] == "hour"


# =============================================================================
# User Story 5: Numeric Bucket Types
# =============================================================================


class TestNumericBucketResult:
    """Tests for NumericBucketResult."""

    def test_basic_creation(self) -> None:
        """Test creating a NumericBucketResult."""
        result = NumericBucketResult(
            event="Purchase",
            from_date="2024-01-01",
            to_date="2024-01-31",
            property_expr='properties["amount"]',
            unit="day",
            series={
                "0 - 100": {"2024-01-01": 50, "2024-01-02": 65},
                "100 - 200": {"2024-01-01": 35, "2024-01-02": 42},
            },
        )

        assert result.event == "Purchase"
        assert result.property_expr == 'properties["amount"]'
        assert result.series["0 - 100"]["2024-01-01"] == 50

    def test_df_has_expected_columns(self) -> None:
        """df should have date, bucket, count columns."""
        result = NumericBucketResult(
            event="Purchase",
            from_date="2024-01-01",
            to_date="2024-01-02",
            property_expr='properties["amount"]',
            unit="day",
            series={
                "0 - 100": {"2024-01-01": 50, "2024-01-02": 65},
                "100 - 200": {"2024-01-01": 35, "2024-01-02": 42},
            },
        )

        df = result.df
        assert "date" in df.columns
        assert "bucket" in df.columns
        assert "count" in df.columns
        assert len(df) == 4  # 2 buckets × 2 dates

    def test_df_empty_series(self) -> None:
        """df should handle empty series."""
        result = NumericBucketResult(
            event="Purchase",
            from_date="2024-01-01",
            to_date="2024-01-31",
            property_expr='properties["amount"]',
            unit="day",
            series={},
        )

        df = result.df
        assert len(df) == 0
        assert "date" in df.columns

    def test_to_dict_serializable(self) -> None:
        """to_dict output should be JSON serializable."""
        result = NumericBucketResult(
            event="Purchase",
            from_date="2024-01-01",
            to_date="2024-01-31",
            property_expr='properties["amount"]',
            unit="day",
            series={"0 - 100": {"2024-01-01": 50}},
        )

        data = result.to_dict()
        json_str = json.dumps(data)

        assert "Purchase" in json_str
        assert "0 - 100" in json_str


# =============================================================================
# User Story 6: Insights Types
# =============================================================================


class TestInsightsResult:
    """Tests for InsightsResult."""

    def test_basic_creation(self) -> None:
        """Test creating an InsightsResult."""
        result = InsightsResult(
            bookmark_id=12345678,
            computed_at="2024-01-15T10:30:00+00:00",
            from_date="2024-01-01",
            to_date="2024-01-07",
            headers=["$event"],
            series={
                "Sign Up": {"2024-01-01": 150, "2024-01-02": 175},
                "Purchase": {"2024-01-01": 50, "2024-01-02": 65},
            },
        )

        assert result.bookmark_id == 12345678
        assert result.computed_at == "2024-01-15T10:30:00+00:00"
        assert result.series["Sign Up"]["2024-01-01"] == 150

    def test_df_has_expected_columns(self) -> None:
        """df should have date, event, count columns."""
        result = InsightsResult(
            bookmark_id=12345,
            computed_at="2024-01-15T10:30:00+00:00",
            from_date="2024-01-01",
            to_date="2024-01-02",
            headers=["$event"],
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
        result = InsightsResult(
            bookmark_id=12345,
            computed_at="2024-01-15T10:30:00+00:00",
            from_date="2024-01-01",
            to_date="2024-01-31",
            headers=[],
            series={},
        )

        df = result.df
        assert len(df) == 0
        assert "date" in df.columns

    def test_to_dict_serializable(self) -> None:
        """to_dict output should be JSON serializable."""
        result = InsightsResult(
            bookmark_id=12345678,
            computed_at="2024-01-15T10:30:00+00:00",
            from_date="2024-01-01",
            to_date="2024-01-07",
            headers=["$event"],
            series={"Sign Up": {"2024-01-01": 150}},
        )

        data = result.to_dict()
        json_str = json.dumps(data)

        assert "12345678" in json_str
        assert data["computed_at"] == "2024-01-15T10:30:00+00:00"


# =============================================================================
# Immutability Tests for All Phase 008 Types
# =============================================================================


class TestPhase008TypesImmutability:
    """Tests for immutability of all Phase 008 result types."""

    def test_all_phase008_types_frozen(self) -> None:
        """All Phase 008 result types should be frozen dataclasses."""
        results: list[object] = [
            UserEvent(
                event="Test",
                time=datetime.now(tz=UTC),
                properties={},
            ),
            ActivityFeedResult(
                distinct_ids=["user"],
                from_date=None,
                to_date=None,
                events=[],
            ),
            InsightsResult(
                bookmark_id=1,
                computed_at="",
                from_date="2024-01-01",
                to_date="2024-01-31",
                headers=[],
                series={},
            ),
            FrequencyResult(
                event=None,
                from_date="2024-01-01",
                to_date="2024-01-31",
                unit="day",
                addiction_unit="hour",
                data={},
            ),
            NumericBucketResult(
                event="Test",
                from_date="2024-01-01",
                to_date="2024-01-31",
                property_expr="test",
                unit="day",
                series={},
            ),
            NumericSumResult(
                event="Test",
                from_date="2024-01-01",
                to_date="2024-01-31",
                property_expr="test",
                unit="day",
                results={},
            ),
            NumericAverageResult(
                event="Test",
                from_date="2024-01-01",
                to_date="2024-01-31",
                property_expr="test",
                unit="day",
                results={},
            ),
        ]

        for result in results:
            # Get any attribute name from the object
            attrs = [a for a in dir(result) if not a.startswith("_")]
            if attrs:
                with pytest.raises((TypeError, dataclasses.FrozenInstanceError)):
                    setattr(result, attrs[0], "modified")
