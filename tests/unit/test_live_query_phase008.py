"""Unit tests for Phase 008 LiveQueryService methods.

Tests the new Query Service Enhancement service methods using httpx.MockTransport.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from typing import TYPE_CHECKING

import httpx
import pytest

from mixpanel_data._internal.services.live_query import LiveQueryService
from mixpanel_data.types import (
    ActivityFeedResult,
    FrequencyResult,
    InsightsResult,
    NumericAverageResult,
    NumericBucketResult,
    NumericSumResult,
    UserEvent,
)

if TYPE_CHECKING:
    from mixpanel_data._internal.api_client import MixpanelAPIClient


@pytest.fixture
def live_query_factory(
    request: pytest.FixtureRequest,
    mock_client_factory: Callable[
        [Callable[[httpx.Request], httpx.Response]], MixpanelAPIClient
    ],
) -> Callable[[Callable[[httpx.Request], httpx.Response]], LiveQueryService]:
    """Factory for creating LiveQueryService with mock API client."""
    clients: list[MixpanelAPIClient] = []

    def factory(
        handler: Callable[[httpx.Request], httpx.Response],
    ) -> LiveQueryService:
        client = mock_client_factory(handler)
        client.__enter__()
        clients.append(client)
        return LiveQueryService(client)

    def cleanup() -> None:
        for client in clients:
            client.__exit__(None, None, None)

    request.addfinalizer(cleanup)
    return factory


# =============================================================================
# US1: Activity Feed Tests
# =============================================================================


class TestActivityFeedService:
    """Tests for LiveQueryService.activity_feed()."""

    def test_activity_feed_returns_typed_result(
        self,
        live_query_factory: Callable[
            [Callable[[httpx.Request], httpx.Response]], LiveQueryService
        ],
    ) -> None:
        """activity_feed() should return ActivityFeedResult."""

        def handler(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": {
                        "events": [
                            {
                                "event": "Sign Up",
                                "properties": {
                                    "time": 1704067200,
                                    "$distinct_id": "user_123",
                                    "plan": "premium",
                                },
                            },
                            {
                                "event": "Purchase",
                                "properties": {
                                    "time": 1704153600,
                                    "$distinct_id": "user_123",
                                    "amount": 99.99,
                                },
                            },
                        ]
                    },
                },
            )

        live_query = live_query_factory(handler)
        result = live_query.activity_feed(distinct_ids=["user_123"])

        assert isinstance(result, ActivityFeedResult)
        assert result.distinct_ids == ["user_123"]
        assert len(result.events) == 2

    def test_activity_feed_converts_timestamps(
        self,
        live_query_factory: Callable[
            [Callable[[httpx.Request], httpx.Response]], LiveQueryService
        ],
    ) -> None:
        """activity_feed() should convert Unix timestamps to datetime."""

        def handler(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": {
                        "events": [
                            {
                                "event": "Sign Up",
                                "properties": {
                                    "time": 1704067200
                                },  # 2024-01-01 00:00:00 UTC
                            }
                        ]
                    },
                },
            )

        live_query = live_query_factory(handler)
        result = live_query.activity_feed(distinct_ids=["user_123"])

        assert len(result.events) == 1
        assert isinstance(result.events[0], UserEvent)
        assert isinstance(result.events[0].time, datetime)
        assert result.events[0].time.year == 2024
        assert result.events[0].time.month == 1
        assert result.events[0].time.day == 1

    def test_activity_feed_preserves_properties(
        self,
        live_query_factory: Callable[
            [Callable[[httpx.Request], httpx.Response]], LiveQueryService
        ],
    ) -> None:
        """activity_feed() should preserve event properties."""

        def handler(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": {
                        "events": [
                            {
                                "event": "Purchase",
                                "properties": {
                                    "time": 1704067200,
                                    "amount": 99.99,
                                    "product": "Widget",
                                },
                            }
                        ]
                    },
                },
            )

        live_query = live_query_factory(handler)
        result = live_query.activity_feed(distinct_ids=["user_123"])

        assert result.events[0].properties["amount"] == 99.99
        assert result.events[0].properties["product"] == "Widget"

    def test_activity_feed_df_conversion(
        self,
        live_query_factory: Callable[
            [Callable[[httpx.Request], httpx.Response]], LiveQueryService
        ],
    ) -> None:
        """activity_feed() result should support DataFrame conversion."""

        def handler(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": {
                        "events": [
                            {"event": "Sign Up", "properties": {"time": 1704067200}},
                            {"event": "Purchase", "properties": {"time": 1704153600}},
                        ]
                    },
                },
            )

        live_query = live_query_factory(handler)
        result = live_query.activity_feed(distinct_ids=["user_123"])
        df = result.df

        assert len(df) == 2
        assert "event" in df.columns
        assert "time" in df.columns


# =============================================================================
# US2: Numeric Sum Tests
# =============================================================================


class TestNumericSumService:
    """Tests for LiveQueryService.segmentation_sum()."""

    def test_segmentation_sum_returns_typed_result(
        self,
        live_query_factory: Callable[
            [Callable[[httpx.Request], httpx.Response]], LiveQueryService
        ],
    ) -> None:
        """segmentation_sum() should return NumericSumResult."""

        def handler(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "computed_at": "2024-01-31T23:02:11.666218+00:00",
                    "results": {
                        "2024-01-01": 15432.50,
                        "2024-01-02": 18976.25,
                    },
                },
            )

        live_query = live_query_factory(handler)
        result = live_query.segmentation_sum(
            event="Purchase",
            from_date="2024-01-01",
            to_date="2024-01-02",
            on='properties["amount"]',
        )

        assert isinstance(result, NumericSumResult)
        assert result.event == "Purchase"
        assert result.results["2024-01-01"] == 15432.50
        assert result.computed_at == "2024-01-31T23:02:11.666218+00:00"

    def test_segmentation_sum_df_columns(
        self,
        live_query_factory: Callable[
            [Callable[[httpx.Request], httpx.Response]], LiveQueryService
        ],
    ) -> None:
        """segmentation_sum() DataFrame should have expected columns."""

        def handler(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": {
                        "2024-01-01": 15432.50,
                        "2024-01-02": 18976.25,
                    },
                },
            )

        live_query = live_query_factory(handler)
        result = live_query.segmentation_sum(
            event="Purchase",
            from_date="2024-01-01",
            to_date="2024-01-02",
            on='properties["amount"]',
        )
        df = result.df

        assert len(df) == 2
        assert "date" in df.columns
        assert "sum" in df.columns


# =============================================================================
# US3: Numeric Average Tests
# =============================================================================


class TestNumericAverageService:
    """Tests for LiveQueryService.segmentation_average()."""

    def test_segmentation_average_returns_typed_result(
        self,
        live_query_factory: Callable[
            [Callable[[httpx.Request], httpx.Response]], LiveQueryService
        ],
    ) -> None:
        """segmentation_average() should return NumericAverageResult."""

        def handler(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": {
                        "2024-01-01": 54.32,
                        "2024-01-02": 62.15,
                    },
                },
            )

        live_query = live_query_factory(handler)
        result = live_query.segmentation_average(
            event="Purchase",
            from_date="2024-01-01",
            to_date="2024-01-02",
            on='properties["amount"]',
        )

        assert isinstance(result, NumericAverageResult)
        assert result.event == "Purchase"
        assert result.results["2024-01-01"] == 54.32

    def test_segmentation_average_df_columns(
        self,
        live_query_factory: Callable[
            [Callable[[httpx.Request], httpx.Response]], LiveQueryService
        ],
    ) -> None:
        """segmentation_average() DataFrame should have expected columns."""

        def handler(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": {
                        "2024-01-01": 54.32,
                    },
                },
            )

        live_query = live_query_factory(handler)
        result = live_query.segmentation_average(
            event="Purchase",
            from_date="2024-01-01",
            to_date="2024-01-01",
            on='properties["amount"]',
        )
        df = result.df

        assert "date" in df.columns
        assert "average" in df.columns


# =============================================================================
# US4: Frequency Tests
# =============================================================================


class TestFrequencyService:
    """Tests for LiveQueryService.frequency()."""

    def test_frequency_returns_typed_result(
        self,
        live_query_factory: Callable[
            [Callable[[httpx.Request], httpx.Response]], LiveQueryService
        ],
    ) -> None:
        """frequency() should return FrequencyResult."""

        def handler(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                json={
                    "data": {
                        "2024-01-01": [305, 107, 60, 41, 32],
                        "2024-01-02": [495, 204, 117, 77, 53],
                    }
                },
            )

        live_query = live_query_factory(handler)
        result = live_query.frequency(
            from_date="2024-01-01",
            to_date="2024-01-02",
        )

        assert isinstance(result, FrequencyResult)
        assert result.from_date == "2024-01-01"
        assert result.to_date == "2024-01-02"
        assert "2024-01-01" in result.data
        assert result.data["2024-01-01"][0] == 305

    def test_frequency_with_event_filter(
        self,
        live_query_factory: Callable[
            [Callable[[httpx.Request], httpx.Response]], LiveQueryService
        ],
    ) -> None:
        """frequency() should preserve event filter."""

        def handler(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={"data": {}})

        live_query = live_query_factory(handler)
        result = live_query.frequency(
            from_date="2024-01-01",
            to_date="2024-01-02",
            event="App Open",
        )

        assert result.event == "App Open"

    def test_frequency_df_conversion(
        self,
        live_query_factory: Callable[
            [Callable[[httpx.Request], httpx.Response]], LiveQueryService
        ],
    ) -> None:
        """frequency() result should support DataFrame conversion."""

        def handler(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                json={
                    "data": {
                        "2024-01-01": [305, 107, 60],
                        "2024-01-02": [495, 204, 117],
                    }
                },
            )

        live_query = live_query_factory(handler)
        result = live_query.frequency(
            from_date="2024-01-01",
            to_date="2024-01-02",
        )
        df = result.df

        assert len(df) == 2
        assert "date" in df.columns


# =============================================================================
# US5: Numeric Bucketing Tests
# =============================================================================


class TestNumericBucketService:
    """Tests for LiveQueryService.segmentation_numeric()."""

    def test_segmentation_numeric_returns_typed_result(
        self,
        live_query_factory: Callable[
            [Callable[[httpx.Request], httpx.Response]], LiveQueryService
        ],
    ) -> None:
        """segmentation_numeric() should return NumericBucketResult."""

        def handler(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                json={
                    "data": {
                        "series": ["2024-01-01", "2024-01-02"],
                        "values": {
                            "0 - 100": {"2024-01-01": 50, "2024-01-02": 65},
                            "100 - 200": {"2024-01-01": 35, "2024-01-02": 42},
                        },
                    },
                    "legend_size": 2,
                },
            )

        live_query = live_query_factory(handler)
        result = live_query.segmentation_numeric(
            event="Purchase",
            from_date="2024-01-01",
            to_date="2024-01-02",
            on='properties["amount"]',
        )

        assert isinstance(result, NumericBucketResult)
        assert result.event == "Purchase"
        assert "0 - 100" in result.series
        assert result.series["0 - 100"]["2024-01-01"] == 50

    def test_segmentation_numeric_df_conversion(
        self,
        live_query_factory: Callable[
            [Callable[[httpx.Request], httpx.Response]], LiveQueryService
        ],
    ) -> None:
        """segmentation_numeric() result should support DataFrame conversion."""

        def handler(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                json={
                    "data": {
                        "series": ["2024-01-01"],
                        "values": {
                            "0 - 100": {"2024-01-01": 50},
                            "100 - 200": {"2024-01-01": 35},
                        },
                    },
                    "legend_size": 2,
                },
            )

        live_query = live_query_factory(handler)
        result = live_query.segmentation_numeric(
            event="Purchase",
            from_date="2024-01-01",
            to_date="2024-01-01",
            on='properties["amount"]',
        )
        df = result.df

        assert "date" in df.columns
        assert "bucket" in df.columns
        assert "count" in df.columns


# =============================================================================
# US6: Insights Tests
# =============================================================================


class TestInsightsService:
    """Tests for LiveQueryService.insights()."""

    def test_insights_returns_typed_result(
        self,
        live_query_factory: Callable[
            [Callable[[httpx.Request], httpx.Response]], LiveQueryService
        ],
    ) -> None:
        """insights() should return InsightsResult."""

        def handler(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                json={
                    "computed_at": "2024-01-15T10:30:00.252314+00:00",
                    "date_range": {
                        "from_date": "2024-01-01T00:00:00-08:00",
                        "to_date": "2024-01-07T00:00:00-08:00",
                    },
                    "headers": ["$event"],
                    "series": {
                        "Sign Up": {"2024-01-01T00:00:00-08:00": 150},
                        "Purchase": {"2024-01-01T00:00:00-08:00": 50},
                    },
                },
            )

        live_query = live_query_factory(handler)
        result = live_query.insights(bookmark_id=12345678)

        assert isinstance(result, InsightsResult)
        assert result.bookmark_id == 12345678
        assert result.computed_at == "2024-01-15T10:30:00.252314+00:00"
        assert "Sign Up" in result.series
        assert "Purchase" in result.series

    def test_insights_preserves_metadata(
        self,
        live_query_factory: Callable[
            [Callable[[httpx.Request], httpx.Response]], LiveQueryService
        ],
    ) -> None:
        """insights() should preserve date range and headers."""

        def handler(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                json={
                    "computed_at": "2024-01-15T10:30:00+00:00",
                    "date_range": {
                        "from_date": "2024-01-01T00:00:00-08:00",
                        "to_date": "2024-01-07T00:00:00-08:00",
                    },
                    "headers": ["$event", "country"],
                    "series": {},
                },
            )

        live_query = live_query_factory(handler)
        result = live_query.insights(bookmark_id=12345678)

        assert result.from_date == "2024-01-01T00:00:00-08:00"
        assert result.to_date == "2024-01-07T00:00:00-08:00"
        assert result.headers == ["$event", "country"]

    def test_insights_df_conversion(
        self,
        live_query_factory: Callable[
            [Callable[[httpx.Request], httpx.Response]], LiveQueryService
        ],
    ) -> None:
        """insights() result should support DataFrame conversion."""

        def handler(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                json={
                    "computed_at": "2024-01-15T10:30:00+00:00",
                    "date_range": {
                        "from_date": "2024-01-01",
                        "to_date": "2024-01-07",
                    },
                    "headers": ["$event"],
                    "series": {
                        "Sign Up": {"2024-01-01": 150, "2024-01-02": 175},
                        "Purchase": {"2024-01-01": 50, "2024-01-02": 65},
                    },
                },
            )

        live_query = live_query_factory(handler)
        result = live_query.insights(bookmark_id=12345678)
        df = result.df

        assert "event" in df.columns
        assert "date" in df.columns
        assert "count" in df.columns
        assert len(df) == 4  # 2 events x 2 dates
