"""Unit tests for Phase 008 MixpanelAPIClient methods.

Tests the new Query Service Enhancement API methods using httpx.MockTransport.
"""

from __future__ import annotations

from typing import Any

import httpx
import pytest
from pydantic import SecretStr

from mixpanel_data._internal.api_client import MixpanelAPIClient
from mixpanel_data._internal.config import Credentials
from mixpanel_data.exceptions import (
    AuthenticationError,
    QueryError,
    RateLimitError,
)


@pytest.fixture
def test_credentials() -> Credentials:
    """Create test credentials."""
    return Credentials(
        username="test_user",
        secret=SecretStr("test_secret"),
        project_id="12345",
        region="us",
    )


def create_mock_client(
    credentials: Credentials,
    handler: Any,
) -> MixpanelAPIClient:
    """Create a client with mock transport."""
    transport = httpx.MockTransport(handler)
    return MixpanelAPIClient(credentials, _transport=transport)


# =============================================================================
# US1: Activity Feed Tests
# =============================================================================


class TestActivityFeed:
    """Tests for MixpanelAPIClient.activity_feed()."""

    def test_activity_feed_basic(self, test_credentials: Credentials) -> None:
        """activity_feed() should return events for given users."""

        def handler(request: httpx.Request) -> httpx.Response:
            assert "/stream/query" in str(request.url)
            assert "distinct_ids" in str(request.url)
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
                                },
                            }
                        ]
                    },
                },
            )

        with create_mock_client(test_credentials, handler) as client:
            result = client.activity_feed(distinct_ids=["user_123"])

        assert result["status"] == "ok"
        assert len(result["results"]["events"]) == 1
        assert result["results"]["events"][0]["event"] == "Sign Up"

    def test_activity_feed_with_date_range(self, test_credentials: Credentials) -> None:
        """activity_feed() should pass date parameters."""

        def handler(request: httpx.Request) -> httpx.Response:
            url_str = str(request.url)
            assert "from_date=2024-01-01" in url_str
            assert "to_date=2024-01-31" in url_str
            return httpx.Response(200, json={"status": "ok", "results": {"events": []}})

        with create_mock_client(test_credentials, handler) as client:
            result = client.activity_feed(
                distinct_ids=["user_123"],
                from_date="2024-01-01",
                to_date="2024-01-31",
            )

        assert result["status"] == "ok"

    def test_activity_feed_multiple_users(self, test_credentials: Credentials) -> None:
        """activity_feed() should accept multiple user IDs."""

        def handler(request: httpx.Request) -> httpx.Response:
            url_str = str(request.url)
            # JSON-encoded list should be in the URL
            assert "user_123" in url_str
            assert "user_456" in url_str
            return httpx.Response(200, json={"status": "ok", "results": {"events": []}})

        with create_mock_client(test_credentials, handler) as client:
            result = client.activity_feed(distinct_ids=["user_123", "user_456"])

        assert result["status"] == "ok"


# =============================================================================
# US2: Numeric Sum Tests
# =============================================================================


class TestSegmentationSum:
    """Tests for MixpanelAPIClient.segmentation_sum()."""

    def test_segmentation_sum_basic(self, test_credentials: Credentials) -> None:
        """segmentation_sum() should return sum values."""

        def handler(request: httpx.Request) -> httpx.Response:
            assert "/segmentation/sum" in str(request.url)
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

        with create_mock_client(test_credentials, handler) as client:
            result = client.segmentation_sum(
                event="Purchase",
                from_date="2024-01-01",
                to_date="2024-01-02",
                on='properties["amount"]',
            )

        assert result["status"] == "ok"
        assert result["results"]["2024-01-01"] == 15432.50

    def test_segmentation_sum_with_filter(self, test_credentials: Credentials) -> None:
        """segmentation_sum() should pass where parameter."""

        def handler(request: httpx.Request) -> httpx.Response:
            assert "where=" in str(request.url)
            return httpx.Response(200, json={"status": "ok", "results": {}})

        with create_mock_client(test_credentials, handler) as client:
            result = client.segmentation_sum(
                event="Purchase",
                from_date="2024-01-01",
                to_date="2024-01-02",
                on='properties["amount"]',
                where='properties["country"] == "US"',
            )

        assert result["status"] == "ok"


# =============================================================================
# US3: Numeric Average Tests
# =============================================================================


class TestSegmentationAverage:
    """Tests for MixpanelAPIClient.segmentation_average()."""

    def test_segmentation_average_basic(self, test_credentials: Credentials) -> None:
        """segmentation_average() should return average values."""

        def handler(request: httpx.Request) -> httpx.Response:
            assert "/segmentation/average" in str(request.url)
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

        with create_mock_client(test_credentials, handler) as client:
            result = client.segmentation_average(
                event="Purchase",
                from_date="2024-01-01",
                to_date="2024-01-02",
                on='properties["amount"]',
            )

        assert result["status"] == "ok"
        assert result["results"]["2024-01-01"] == 54.32

    def test_segmentation_average_hourly(self, test_credentials: Credentials) -> None:
        """segmentation_average() should support hourly unit."""

        def handler(request: httpx.Request) -> httpx.Response:
            assert "unit=hour" in str(request.url)
            return httpx.Response(200, json={"status": "ok", "results": {}})

        with create_mock_client(test_credentials, handler) as client:
            result = client.segmentation_average(
                event="Purchase",
                from_date="2024-01-01",
                to_date="2024-01-01",
                on='properties["amount"]',
                unit="hour",
            )

        assert result["status"] == "ok"


# =============================================================================
# US4: Frequency Tests
# =============================================================================


class TestFrequency:
    """Tests for MixpanelAPIClient.frequency()."""

    def test_frequency_basic(self, test_credentials: Credentials) -> None:
        """frequency() should return frequency arrays."""

        def handler(request: httpx.Request) -> httpx.Response:
            assert "/retention/addiction" in str(request.url)
            return httpx.Response(
                200,
                json={
                    "data": {
                        "2024-01-01": [305, 107, 60, 41, 32],
                        "2024-01-02": [495, 204, 117, 77, 53],
                    }
                },
            )

        with create_mock_client(test_credentials, handler) as client:
            result = client.frequency(
                from_date="2024-01-01",
                to_date="2024-01-02",
                unit="day",
                addiction_unit="hour",
            )

        assert "data" in result
        assert "2024-01-01" in result["data"]
        assert result["data"]["2024-01-01"][0] == 305

    def test_frequency_with_event_filter(self, test_credentials: Credentials) -> None:
        """frequency() should pass event parameter."""

        def handler(request: httpx.Request) -> httpx.Response:
            assert "event=" in str(request.url)
            return httpx.Response(200, json={"data": {}})

        with create_mock_client(test_credentials, handler) as client:
            result = client.frequency(
                from_date="2024-01-01",
                to_date="2024-01-02",
                unit="day",
                addiction_unit="hour",
                event="App Open",
            )

        assert "data" in result


# =============================================================================
# US5: Numeric Bucketing Tests
# =============================================================================


class TestSegmentationNumeric:
    """Tests for MixpanelAPIClient.segmentation_numeric()."""

    def test_segmentation_numeric_basic(self, test_credentials: Credentials) -> None:
        """segmentation_numeric() should return bucketed values."""

        def handler(request: httpx.Request) -> httpx.Response:
            assert "/segmentation/numeric" in str(request.url)
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

        with create_mock_client(test_credentials, handler) as client:
            result = client.segmentation_numeric(
                event="Purchase",
                from_date="2024-01-01",
                to_date="2024-01-02",
                on='properties["amount"]',
            )

        assert "data" in result
        assert "0 - 100" in result["data"]["values"]

    def test_segmentation_numeric_with_type(
        self, test_credentials: Credentials
    ) -> None:
        """segmentation_numeric() should pass type parameter."""

        def handler(request: httpx.Request) -> httpx.Response:
            assert "type=unique" in str(request.url)
            return httpx.Response(200, json={"data": {"series": [], "values": {}}})

        with create_mock_client(test_credentials, handler) as client:
            result = client.segmentation_numeric(
                event="Purchase",
                from_date="2024-01-01",
                to_date="2024-01-02",
                on='properties["amount"]',
                type="unique",
            )

        assert "data" in result


# =============================================================================
# US6: Insights Tests
# =============================================================================


class TestQuerySavedReport:
    """Tests for MixpanelAPIClient.query_saved_report()."""

    def test_query_saved_report_basic(self, test_credentials: Credentials) -> None:
        """query_saved_report() should return report data."""

        def handler(request: httpx.Request) -> httpx.Response:
            assert "/insights" in str(request.url)
            assert "bookmark_id=" in str(request.url)
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
                    },
                },
            )

        with create_mock_client(test_credentials, handler) as client:
            result = client.query_saved_report(bookmark_id=12345678)

        assert "computed_at" in result
        assert "series" in result
        assert "Sign Up" in result["series"]

    def test_query_saved_report_passes_bookmark_id(
        self, test_credentials: Credentials
    ) -> None:
        """query_saved_report() should pass bookmark_id in request."""

        def handler(request: httpx.Request) -> httpx.Response:
            assert "bookmark_id=99887766" in str(request.url)
            return httpx.Response(200, json={"series": {}})

        with create_mock_client(test_credentials, handler) as client:
            result = client.query_saved_report(bookmark_id=99887766)

        assert "series" in result


# =============================================================================
# Error Handling Tests
# =============================================================================


class TestPhase008ErrorHandling:
    """Error handling tests for Phase 008 API methods."""

    # -------------------------------------------------------------------------
    # Activity Feed Error Handling
    # -------------------------------------------------------------------------

    def test_activity_feed_auth_error_on_401(
        self, test_credentials: Credentials
    ) -> None:
        """activity_feed() should raise AuthenticationError on 401."""

        def handler(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(401, json={"error": "Invalid credentials"})

        with (
            create_mock_client(test_credentials, handler) as client,
            pytest.raises(AuthenticationError) as exc_info,
        ):
            client.activity_feed(distinct_ids=["user_123"])

        assert "credentials" in str(exc_info.value).lower()

    def test_activity_feed_query_error_on_400(
        self, test_credentials: Credentials
    ) -> None:
        """activity_feed() should raise QueryError on 400."""

        def handler(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(400, json={"error": "Invalid query"})

        with (
            create_mock_client(test_credentials, handler) as client,
            pytest.raises(QueryError) as exc_info,
        ):
            client.activity_feed(distinct_ids=["user_123"])

        assert "Invalid query" in str(exc_info.value)

    def test_activity_feed_rate_limit_on_429(
        self, test_credentials: Credentials
    ) -> None:
        """activity_feed() should raise RateLimitError on 429."""

        def handler(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(429, headers={"Retry-After": "0"})

        transport = httpx.MockTransport(handler)
        client = MixpanelAPIClient(
            test_credentials, max_retries=1, _transport=transport
        )

        with client, pytest.raises(RateLimitError) as exc_info:
            client.activity_feed(distinct_ids=["user_123"])

        assert exc_info.value.retry_after == 0

    # -------------------------------------------------------------------------
    # Segmentation Sum Error Handling
    # -------------------------------------------------------------------------

    def test_segmentation_sum_auth_error_on_401(
        self, test_credentials: Credentials
    ) -> None:
        """segmentation_sum() should raise AuthenticationError on 401."""

        def handler(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(401, json={"error": "Invalid credentials"})

        with (
            create_mock_client(test_credentials, handler) as client,
            pytest.raises(AuthenticationError),
        ):
            client.segmentation_sum(
                event="Purchase",
                from_date="2024-01-01",
                to_date="2024-01-31",
                on='properties["amount"]',
            )

    def test_segmentation_sum_query_error_on_400(
        self, test_credentials: Credentials
    ) -> None:
        """segmentation_sum() should raise QueryError on 400."""

        def handler(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(400, json={"error": "Invalid property expression"})

        with (
            create_mock_client(test_credentials, handler) as client,
            pytest.raises(QueryError) as exc_info,
        ):
            client.segmentation_sum(
                event="Purchase",
                from_date="2024-01-01",
                to_date="2024-01-31",
                on='properties["amount"]',
            )

        assert "Invalid property expression" in str(exc_info.value)

    def test_segmentation_sum_rate_limit_on_429(
        self, test_credentials: Credentials
    ) -> None:
        """segmentation_sum() should raise RateLimitError on 429."""

        def handler(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(429, headers={"Retry-After": "0"})

        transport = httpx.MockTransport(handler)
        client = MixpanelAPIClient(
            test_credentials, max_retries=1, _transport=transport
        )

        with client, pytest.raises(RateLimitError) as exc_info:
            client.segmentation_sum(
                event="Purchase",
                from_date="2024-01-01",
                to_date="2024-01-31",
                on='properties["amount"]',
            )

        assert exc_info.value.retry_after == 0

    # -------------------------------------------------------------------------
    # Segmentation Average Error Handling
    # -------------------------------------------------------------------------

    def test_segmentation_average_auth_error_on_401(
        self, test_credentials: Credentials
    ) -> None:
        """segmentation_average() should raise AuthenticationError on 401."""

        def handler(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(401, json={"error": "Invalid credentials"})

        with (
            create_mock_client(test_credentials, handler) as client,
            pytest.raises(AuthenticationError),
        ):
            client.segmentation_average(
                event="Purchase",
                from_date="2024-01-01",
                to_date="2024-01-31",
                on='properties["amount"]',
            )

    def test_segmentation_average_query_error_on_400(
        self, test_credentials: Credentials
    ) -> None:
        """segmentation_average() should raise QueryError on 400."""

        def handler(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(400, json={"error": "Invalid event name"})

        with (
            create_mock_client(test_credentials, handler) as client,
            pytest.raises(QueryError) as exc_info,
        ):
            client.segmentation_average(
                event="Purchase",
                from_date="2024-01-01",
                to_date="2024-01-31",
                on='properties["amount"]',
            )

        assert "Invalid event name" in str(exc_info.value)

    def test_segmentation_average_rate_limit_on_429(
        self, test_credentials: Credentials
    ) -> None:
        """segmentation_average() should raise RateLimitError on 429."""

        def handler(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(429, headers={"Retry-After": "0"})

        transport = httpx.MockTransport(handler)
        client = MixpanelAPIClient(
            test_credentials, max_retries=1, _transport=transport
        )

        with client, pytest.raises(RateLimitError) as exc_info:
            client.segmentation_average(
                event="Purchase",
                from_date="2024-01-01",
                to_date="2024-01-31",
                on='properties["amount"]',
            )

        assert exc_info.value.retry_after == 0

    # -------------------------------------------------------------------------
    # Frequency Error Handling
    # -------------------------------------------------------------------------

    def test_frequency_auth_error_on_401(self, test_credentials: Credentials) -> None:
        """frequency() should raise AuthenticationError on 401."""

        def handler(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(401, json={"error": "Invalid credentials"})

        with (
            create_mock_client(test_credentials, handler) as client,
            pytest.raises(AuthenticationError),
        ):
            client.frequency(
                from_date="2024-01-01",
                to_date="2024-01-31",
                unit="day",
                addiction_unit="hour",
            )

    def test_frequency_query_error_on_400(self, test_credentials: Credentials) -> None:
        """frequency() should raise QueryError on 400."""

        def handler(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(400, json={"error": "Invalid date range"})

        with (
            create_mock_client(test_credentials, handler) as client,
            pytest.raises(QueryError) as exc_info,
        ):
            client.frequency(
                from_date="2024-01-01",
                to_date="2024-01-31",
                unit="day",
                addiction_unit="hour",
            )

        assert "Invalid date range" in str(exc_info.value)

    def test_frequency_rate_limit_on_429(self, test_credentials: Credentials) -> None:
        """frequency() should raise RateLimitError on 429."""

        def handler(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(429, headers={"Retry-After": "0"})

        transport = httpx.MockTransport(handler)
        client = MixpanelAPIClient(
            test_credentials, max_retries=1, _transport=transport
        )

        with client, pytest.raises(RateLimitError) as exc_info:
            client.frequency(
                from_date="2024-01-01",
                to_date="2024-01-31",
                unit="day",
                addiction_unit="hour",
            )

        assert exc_info.value.retry_after == 0

    # -------------------------------------------------------------------------
    # Segmentation Numeric Error Handling
    # -------------------------------------------------------------------------

    def test_segmentation_numeric_auth_error_on_401(
        self, test_credentials: Credentials
    ) -> None:
        """segmentation_numeric() should raise AuthenticationError on 401."""

        def handler(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(401, json={"error": "Invalid credentials"})

        with (
            create_mock_client(test_credentials, handler) as client,
            pytest.raises(AuthenticationError),
        ):
            client.segmentation_numeric(
                event="Purchase",
                from_date="2024-01-01",
                to_date="2024-01-31",
                on='properties["amount"]',
            )

    def test_segmentation_numeric_query_error_on_400(
        self, test_credentials: Credentials
    ) -> None:
        """segmentation_numeric() should raise QueryError on 400."""

        def handler(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(400, json={"error": "Property not found"})

        with (
            create_mock_client(test_credentials, handler) as client,
            pytest.raises(QueryError) as exc_info,
        ):
            client.segmentation_numeric(
                event="Purchase",
                from_date="2024-01-01",
                to_date="2024-01-31",
                on='properties["amount"]',
            )

        assert "Property not found" in str(exc_info.value)

    def test_segmentation_numeric_rate_limit_on_429(
        self, test_credentials: Credentials
    ) -> None:
        """segmentation_numeric() should raise RateLimitError on 429."""

        def handler(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(429, headers={"Retry-After": "0"})

        transport = httpx.MockTransport(handler)
        client = MixpanelAPIClient(
            test_credentials, max_retries=1, _transport=transport
        )

        with client, pytest.raises(RateLimitError) as exc_info:
            client.segmentation_numeric(
                event="Purchase",
                from_date="2024-01-01",
                to_date="2024-01-31",
                on='properties["amount"]',
            )

        assert exc_info.value.retry_after == 0

    # -------------------------------------------------------------------------
    # query_saved_report Error Handling
    # -------------------------------------------------------------------------

    def test_query_saved_report_auth_error_on_401(
        self, test_credentials: Credentials
    ) -> None:
        """query_saved_report() should raise AuthenticationError on 401."""

        def handler(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(401, json={"error": "Invalid credentials"})

        with (
            create_mock_client(test_credentials, handler) as client,
            pytest.raises(AuthenticationError),
        ):
            client.query_saved_report(bookmark_id=12345678)

    def test_query_saved_report_query_error_on_400(
        self, test_credentials: Credentials
    ) -> None:
        """query_saved_report() should raise QueryError on 400."""

        def handler(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(400, json={"error": "Invalid bookmark_id"})

        with (
            create_mock_client(test_credentials, handler) as client,
            pytest.raises(QueryError) as exc_info,
        ):
            client.query_saved_report(bookmark_id=99999999)

        assert "Invalid bookmark_id" in str(exc_info.value)

    def test_query_saved_report_rate_limit_on_429(
        self, test_credentials: Credentials
    ) -> None:
        """query_saved_report() should raise RateLimitError on 429."""

        def handler(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(429, headers={"Retry-After": "0"})

        transport = httpx.MockTransport(handler)
        client = MixpanelAPIClient(
            test_credentials, max_retries=1, _transport=transport
        )

        with client, pytest.raises(RateLimitError) as exc_info:
            client.query_saved_report(bookmark_id=12345678)

        assert exc_info.value.retry_after == 0
