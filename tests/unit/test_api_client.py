"""Unit tests for MixpanelAPIClient.

Tests use httpx.MockTransport for deterministic HTTP mocking.
"""

from __future__ import annotations

import json
from typing import Any

import httpx
import pytest
from pydantic import SecretStr

from mixpanel_data._internal.api_client import ENDPOINTS, MixpanelAPIClient
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


@pytest.fixture
def eu_credentials() -> Credentials:
    """Create EU region test credentials."""
    return Credentials(
        username="test_user",
        secret=SecretStr("test_secret"),
        project_id="12345",
        region="eu",
    )


@pytest.fixture
def india_credentials() -> Credentials:
    """Create India region test credentials."""
    return Credentials(
        username="test_user",
        secret=SecretStr("test_secret"),
        project_id="12345",
        region="in",
    )


def create_mock_client(
    credentials: Credentials,
    handler: Any,
) -> MixpanelAPIClient:
    """Create a client with mock transport."""
    transport = httpx.MockTransport(handler)
    return MixpanelAPIClient(credentials, _transport=transport)


# =============================================================================
# Phase 2: Foundational Tests
# =============================================================================


class TestEndpoints:
    """Test ENDPOINTS configuration."""

    def test_us_endpoints_defined(self) -> None:
        """US endpoints should be defined."""
        assert "us" in ENDPOINTS
        assert "query" in ENDPOINTS["us"]
        assert "export" in ENDPOINTS["us"]
        assert "engage" in ENDPOINTS["us"]

    def test_eu_endpoints_defined(self) -> None:
        """EU endpoints should be defined."""
        assert "eu" in ENDPOINTS
        assert "query" in ENDPOINTS["eu"]
        assert "export" in ENDPOINTS["eu"]

    def test_india_endpoints_defined(self) -> None:
        """India endpoints should be defined."""
        assert "in" in ENDPOINTS
        assert "query" in ENDPOINTS["in"]
        assert "export" in ENDPOINTS["in"]


class TestClientInit:
    """Test client initialization."""

    def test_init_with_credentials(self, test_credentials: Credentials) -> None:
        """Client should accept credentials."""
        client = MixpanelAPIClient(test_credentials)
        assert client._credentials == test_credentials
        client.close()

    def test_init_with_custom_timeout(self, test_credentials: Credentials) -> None:
        """Client should accept custom timeout."""
        client = MixpanelAPIClient(test_credentials, timeout=60.0)
        assert client._timeout == 60.0
        client.close()

    def test_init_with_custom_export_timeout(
        self, test_credentials: Credentials
    ) -> None:
        """Client should accept custom export timeout."""
        client = MixpanelAPIClient(test_credentials, export_timeout=600.0)
        assert client._export_timeout == 600.0
        client.close()

    def test_init_with_max_retries(self, test_credentials: Credentials) -> None:
        """Client should accept max retries."""
        client = MixpanelAPIClient(test_credentials, max_retries=5)
        assert client._max_retries == 5
        client.close()


class TestClientLifecycle:
    """Test client lifecycle methods."""

    def test_context_manager(self, test_credentials: Credentials) -> None:
        """Client should work as context manager."""

        def handler(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json=["event1"])

        with create_mock_client(test_credentials, handler) as client:
            assert client._client is not None
        assert client._client is None

    def test_close_releases_resources(self, test_credentials: Credentials) -> None:
        """Close should release HTTP client."""

        def handler(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json=[])

        client = create_mock_client(test_credentials, handler)
        client._ensure_client()
        assert client._client is not None
        client.close()
        assert client._client is None


class TestAuthHeader:
    """Test auth header generation."""

    def test_auth_header_format(self, test_credentials: Credentials) -> None:
        """Auth header should be Base64 encoded Basic auth."""
        client = MixpanelAPIClient(test_credentials)
        header = client._get_auth_header()
        assert header.startswith("Basic ")
        # Decode and verify
        import base64

        encoded = header.replace("Basic ", "")
        decoded = base64.b64decode(encoded).decode()
        assert decoded == "test_user:test_secret"
        client.close()


class TestBuildUrl:
    """Test URL building."""

    def test_build_query_url_us(self, test_credentials: Credentials) -> None:
        """Should build correct US query URL."""
        client = MixpanelAPIClient(test_credentials)
        url = client._build_url("query", "/segmentation")
        assert url == "https://mixpanel.com/api/query/segmentation"
        client.close()

    def test_build_query_url_eu(self, eu_credentials: Credentials) -> None:
        """Should build correct EU query URL."""
        client = MixpanelAPIClient(eu_credentials)
        url = client._build_url("query", "/segmentation")
        assert url == "https://eu.mixpanel.com/api/query/segmentation"
        client.close()

    def test_build_query_url_india(self, india_credentials: Credentials) -> None:
        """Should build correct India query URL."""
        client = MixpanelAPIClient(india_credentials)
        url = client._build_url("query", "/segmentation")
        assert url == "https://in.mixpanel.com/api/query/segmentation"
        client.close()

    def test_build_export_url_us(self, test_credentials: Credentials) -> None:
        """Should build correct US export URL."""
        client = MixpanelAPIClient(test_credentials)
        url = client._build_url("export", "/export")
        assert url == "https://data.mixpanel.com/api/2.0/export"
        client.close()

    def test_build_export_url_eu(self, eu_credentials: Credentials) -> None:
        """Should build correct EU export URL."""
        client = MixpanelAPIClient(eu_credentials)
        url = client._build_url("export", "/export")
        assert url == "https://data-eu.mixpanel.com/api/2.0/export"
        client.close()

    def test_build_url_adds_leading_slash(self, test_credentials: Credentials) -> None:
        """Should add leading slash if missing."""
        client = MixpanelAPIClient(test_credentials)
        url = client._build_url("query", "segmentation")
        assert url == "https://mixpanel.com/api/query/segmentation"
        client.close()


# =============================================================================
# User Story 1: Authenticated API Requests
# =============================================================================


class TestAuthenticatedRequests:
    """Test authenticated request handling (US1)."""

    def test_auth_header_sent(self, test_credentials: Credentials) -> None:
        """Auth header should be sent with requests."""
        captured_headers: dict[str, str] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured_headers.update(dict(request.headers))
            return httpx.Response(200, json=["event1"])

        with create_mock_client(test_credentials, handler) as client:
            client.get_events()

        assert "authorization" in captured_headers
        assert captured_headers["authorization"].startswith("Basic ")

    def test_project_id_in_query_params(self, test_credentials: Credentials) -> None:
        """Project ID should be in query params."""
        captured_url: str = ""

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal captured_url
            captured_url = str(request.url)
            return httpx.Response(200, json=["event1"])

        with create_mock_client(test_credentials, handler) as client:
            client.get_events()

        assert "project_id=12345" in captured_url

    def test_authentication_error_on_401(self, test_credentials: Credentials) -> None:
        """Should raise AuthenticationError on 401."""

        def handler(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(401, json={"error": "Invalid credentials"})

        with (
            create_mock_client(test_credentials, handler) as client,
            pytest.raises(AuthenticationError) as exc_info,
        ):
            client.get_events()

        assert "credentials" in str(exc_info.value).lower()

    def test_credentials_not_in_error_messages(
        self, test_credentials: Credentials
    ) -> None:
        """Credentials should never appear in error messages."""

        def handler(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(401, json={"error": "Auth failed"})

        with (
            create_mock_client(test_credentials, handler) as client,
            pytest.raises(AuthenticationError) as exc_info,
        ):
            client.get_events()

        error_str = str(exc_info.value)
        assert "test_secret" not in error_str
        assert "test_user" not in error_str

    def test_regional_routing_us(self, test_credentials: Credentials) -> None:
        """US region should use US endpoints."""
        captured_url: str = ""

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal captured_url
            captured_url = str(request.url)
            return httpx.Response(200, json=["event1"])

        with create_mock_client(test_credentials, handler) as client:
            client.get_events()

        assert "mixpanel.com" in captured_url

    def test_regional_routing_eu(self, eu_credentials: Credentials) -> None:
        """EU region should use EU endpoints."""
        captured_url: str = ""

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal captured_url
            captured_url = str(request.url)
            return httpx.Response(200, json=["event1"])

        with create_mock_client(eu_credentials, handler) as client:
            client.get_events()

        assert "eu.mixpanel.com" in captured_url

    def test_regional_routing_india(self, india_credentials: Credentials) -> None:
        """India region should use India endpoints."""
        captured_url: str = ""

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal captured_url
            captured_url = str(request.url)
            return httpx.Response(200, json=["event1"])

        with create_mock_client(india_credentials, handler) as client:
            client.get_events()

        assert "in.mixpanel.com" in captured_url


# =============================================================================
# User Story 2: Rate Limiting
# =============================================================================


class TestRateLimiting:
    """Test rate limit handling (US2)."""

    def test_retry_on_429_with_retry_after(self, test_credentials: Credentials) -> None:
        """Should retry on 429 with Retry-After header."""
        call_count = 0

        def handler(_request: httpx.Request) -> httpx.Response:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return httpx.Response(429, headers={"Retry-After": "0"})
            return httpx.Response(200, json=["event1"])

        with create_mock_client(test_credentials, handler) as client:
            result = client.get_events()

        assert call_count == 2
        assert result == ["event1"]

    def test_exponential_backoff_without_retry_after(
        self, test_credentials: Credentials
    ) -> None:
        """Should use exponential backoff without Retry-After."""
        call_count = 0

        def handler(_request: httpx.Request) -> httpx.Response:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return httpx.Response(429)  # No Retry-After
            return httpx.Response(200, json=["event1"])

        # Use low max_retries for faster test
        transport = httpx.MockTransport(handler)
        client = MixpanelAPIClient(
            test_credentials, max_retries=2, _transport=transport
        )

        with client:
            result = client.get_events()

        assert call_count == 2
        assert result == ["event1"]

    def test_rate_limit_error_after_max_retries(
        self, test_credentials: Credentials
    ) -> None:
        """Should raise RateLimitError after max retries."""

        def handler(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(429, headers={"Retry-After": "0"})

        transport = httpx.MockTransport(handler)
        client = MixpanelAPIClient(
            test_credentials, max_retries=1, _transport=transport
        )

        with client, pytest.raises(RateLimitError) as exc_info:
            client.get_events()

        assert exc_info.value.retry_after == 0

    def test_successful_response_after_retry(
        self, test_credentials: Credentials
    ) -> None:
        """Should return successful response after retry."""
        call_count = 0

        def handler(_request: httpx.Request) -> httpx.Response:
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                return httpx.Response(429, headers={"Retry-After": "0"})
            return httpx.Response(200, json={"data": "success"})

        transport = httpx.MockTransport(handler)
        client = MixpanelAPIClient(
            test_credentials, max_retries=3, _transport=transport
        )

        with client:
            result = client.segmentation("event", "2024-01-01", "2024-01-31")

        assert call_count == 3
        assert result == {"data": "success"}


# =============================================================================
# User Story 3: Stream Large Event Exports
# =============================================================================


class TestEventExport:
    """Test event export streaming (US3)."""

    def test_export_events_returns_iterator(
        self, test_credentials: Credentials
    ) -> None:
        """export_events should return an iterator."""
        mock_data = b'{"event":"A","properties":{"time":1}}\n{"event":"B","properties":{"time":2}}\n'

        def handler(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, content=mock_data)

        with create_mock_client(test_credentials, handler) as client:
            result = client.export_events("2024-01-01", "2024-01-31")
            # Should be an iterator
            assert hasattr(result, "__iter__")
            assert hasattr(result, "__next__")

    def test_jsonl_parsing_line_by_line(self, test_credentials: Credentials) -> None:
        """Should parse JSONL line by line."""
        mock_data = b'{"event":"A","properties":{"time":1}}\n{"event":"B","properties":{"time":2}}\n'

        def handler(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, content=mock_data)

        with create_mock_client(test_credentials, handler) as client:
            events = list(client.export_events("2024-01-01", "2024-01-31"))

        assert len(events) == 2
        assert events[0]["event"] == "A"
        assert events[1]["event"] == "B"

    def test_on_batch_callback(self, test_credentials: Credentials) -> None:
        """Should invoke on_batch callback."""
        # Create enough events to trigger callback
        events_data = "\n".join(
            json.dumps({"event": f"E{i}", "properties": {"time": i}})
            for i in range(1500)
        )
        mock_data = events_data.encode() + b"\n"

        def handler(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, content=mock_data)

        batch_counts: list[int] = []

        def on_batch(count: int) -> None:
            batch_counts.append(count)

        with create_mock_client(test_credentials, handler) as client:
            list(client.export_events("2024-01-01", "2024-01-31", on_batch=on_batch))

        # Should have called on_batch at 1000 and final count
        assert 1000 in batch_counts
        assert 1500 in batch_counts

    def test_event_name_filtering(self, test_credentials: Credentials) -> None:
        """Should filter by event names."""
        captured_url: str = ""

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal captured_url
            captured_url = str(request.url)
            return httpx.Response(200, content=b"")

        with create_mock_client(test_credentials, handler) as client:
            list(
                client.export_events(
                    "2024-01-01", "2024-01-31", events=["Purchase", "View"]
                )
            )

        # Events should be JSON-encoded in URL
        assert "event=" in captured_url

    def test_malformed_json_skipped(self, test_credentials: Credentials) -> None:
        """Should skip malformed JSON lines with warning."""
        mock_data = b'{"event":"A","properties":{"time":1}}\nNOT JSON\n{"event":"B","properties":{"time":2}}\n'

        def handler(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, content=mock_data)

        with create_mock_client(test_credentials, handler) as client:
            events = list(client.export_events("2024-01-01", "2024-01-31"))

        # Should have skipped malformed line
        assert len(events) == 2
        assert events[0]["event"] == "A"
        assert events[1]["event"] == "B"


# =============================================================================
# User Story 4: Segmentation Queries
# =============================================================================


class TestSegmentation:
    """Test segmentation queries (US4)."""

    def test_segmentation_basic(self, test_credentials: Credentials) -> None:
        """Should make basic segmentation query."""
        captured_params: dict[str, Any] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            for key, value in request.url.params.items():
                captured_params[key] = value
            return httpx.Response(200, json={"data": {"values": {}}})

        with create_mock_client(test_credentials, handler) as client:
            client.segmentation("Purchase", "2024-01-01", "2024-01-31")

        assert captured_params["event"] == "Purchase"
        assert captured_params["from_date"] == "2024-01-01"
        assert captured_params["to_date"] == "2024-01-31"

    def test_segmentation_with_on(self, test_credentials: Credentials) -> None:
        """Should include 'on' parameter."""
        captured_params: dict[str, Any] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            for key, value in request.url.params.items():
                captured_params[key] = value
            return httpx.Response(200, json={"data": {}})

        with create_mock_client(test_credentials, handler) as client:
            client.segmentation(
                "Purchase", "2024-01-01", "2024-01-31", on="properties.country"
            )

        assert captured_params["on"] == "properties.country"

    def test_segmentation_with_where(self, test_credentials: Credentials) -> None:
        """Should include 'where' filter."""
        captured_params: dict[str, Any] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            for key, value in request.url.params.items():
                captured_params[key] = value
            return httpx.Response(200, json={"data": {}})

        with create_mock_client(test_credentials, handler) as client:
            client.segmentation(
                "Purchase",
                "2024-01-01",
                "2024-01-31",
                where='properties["amount"] > 100',
            )

        assert "where" in captured_params


# =============================================================================
# User Story 5: Discovery
# =============================================================================


class TestDiscovery:
    """Test discovery APIs (US5)."""

    def test_get_events(self, test_credentials: Credentials) -> None:
        """Should list events with type=general parameter."""
        captured_params: dict[str, Any] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            for key, value in request.url.params.items():
                captured_params[key] = value
            return httpx.Response(200, json=["event1", "event2", "event3"])

        with create_mock_client(test_credentials, handler) as client:
            events = client.get_events()

        assert events == ["event1", "event2", "event3"]
        assert captured_params["type"] == "general"

    def test_get_event_properties(self, test_credentials: Credentials) -> None:
        """Should list event properties from /events/properties/top endpoint."""
        captured_params: dict[str, Any] = {}
        captured_path: str = ""

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal captured_path
            captured_path = request.url.path
            for key, value in request.url.params.items():
                captured_params[key] = value
            # /events/properties/top returns dict with property names as keys
            return httpx.Response(200, json={"prop1": 100.0, "prop2": 50.5})

        with create_mock_client(test_credentials, handler) as client:
            props = client.get_event_properties("Purchase")

        assert captured_path.endswith("/events/properties/top")
        assert captured_params["event"] == "Purchase"
        assert set(props) == {"prop1", "prop2"}

    def test_get_property_values(self, test_credentials: Credentials) -> None:
        """Should list property values with limit."""
        captured_params: dict[str, Any] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            for key, value in request.url.params.items():
                captured_params[key] = value
            return httpx.Response(200, json=["value1", "value2"])

        with create_mock_client(test_credentials, handler) as client:
            values = client.get_property_values("country", limit=10)

        assert captured_params["name"] == "country"
        assert captured_params["limit"] == "10"
        assert values == ["value1", "value2"]


# =============================================================================
# User Story 6: Profile Export
# =============================================================================


class TestProfileExport:
    """Test profile export (US6)."""

    def test_export_profiles_returns_iterator(
        self, test_credentials: Credentials
    ) -> None:
        """export_profiles should return an iterator."""

        def handler(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                json={
                    "results": [{"$distinct_id": "u1", "$properties": {}}],
                    "session_id": None,
                },
            )

        with create_mock_client(test_credentials, handler) as client:
            result = client.export_profiles()
            assert hasattr(result, "__iter__")

    def test_pagination_with_session_id(self, test_credentials: Credentials) -> None:
        """Should handle pagination with session_id."""
        call_count = 0

        def handler(_request: httpx.Request) -> httpx.Response:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return httpx.Response(
                    200,
                    json={
                        "results": [{"$distinct_id": "u1"}],
                        "session_id": "abc123",
                    },
                )
            return httpx.Response(
                200,
                json={"results": [], "session_id": None},
            )

        with create_mock_client(test_credentials, handler) as client:
            profiles = list(client.export_profiles())

        assert len(profiles) == 1
        assert call_count == 2

    def test_where_filter(self, test_credentials: Credentials) -> None:
        """Should include where filter."""
        captured_body: dict[str, Any] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            if request.content:
                nonlocal captured_body
                captured_body = json.loads(request.content)
            return httpx.Response(200, json={"results": []})

        with create_mock_client(test_credentials, handler) as client:
            list(client.export_profiles(where='properties["plan"] == "premium"'))

        assert "where" in captured_body


# =============================================================================
# User Story 7: Funnel and Retention
# =============================================================================


class TestFunnelAndRetention:
    """Test funnel and retention queries (US7)."""

    def test_funnel(self, test_credentials: Credentials) -> None:
        """Should execute funnel query."""
        captured_params: dict[str, Any] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            for key, value in request.url.params.items():
                captured_params[key] = value
            return httpx.Response(200, json={"data": []})

        with create_mock_client(test_credentials, handler) as client:
            client.funnel(12345, "2024-01-01", "2024-01-31")

        assert captured_params["funnel_id"] == "12345"

    def test_retention(self, test_credentials: Credentials) -> None:
        """Should execute retention query."""
        captured_params: dict[str, Any] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            for key, value in request.url.params.items():
                captured_params[key] = value
            return httpx.Response(200, json={"data": {}})

        with create_mock_client(test_credentials, handler) as client:
            client.retention("Signup", "Purchase", "2024-01-01", "2024-01-31")

        assert captured_params["born_event"] == "Signup"
        assert captured_params["event"] == "Purchase"

    def test_retention_default_interval_sends_unit_only(
        self, test_credentials: Credentials
    ) -> None:
        """Regression: with default interval=1, should send 'unit' but NOT 'interval'.

        Bug: Mixpanel API rejects requests with both 'unit' and 'interval' set together,
        returning "Validate failed: unit and interval both set".
        Fix: Only send 'interval' when != 1, otherwise send 'unit'.
        """
        captured_params: dict[str, Any] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            for key, value in request.url.params.items():
                captured_params[key] = value
            return httpx.Response(200, json={})

        with create_mock_client(test_credentials, handler) as client:
            # Default interval is 1
            client.retention(
                "Signup",
                "Purchase",
                "2024-01-01",
                "2024-01-31",
                unit="day",
                interval=1,  # Default value
            )

        # Should send 'unit' for standard periods
        assert "unit" in captured_params
        assert captured_params["unit"] == "day"
        # Should NOT send 'interval' when it's the default value of 1
        assert "interval" not in captured_params

    def test_retention_custom_interval_sends_interval_only(
        self, test_credentials: Credentials
    ) -> None:
        """Regression: with custom interval!=1, should send 'interval' but NOT 'unit'.

        Bug: Mixpanel API rejects requests with both 'unit' and 'interval' set together,
        returning "Validate failed: unit and interval both set".
        Fix: Only send 'interval' when != 1, otherwise send 'unit'.
        """
        captured_params: dict[str, Any] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            for key, value in request.url.params.items():
                captured_params[key] = value
            return httpx.Response(200, json={})

        with create_mock_client(test_credentials, handler) as client:
            # Custom interval of 7 days
            client.retention(
                "Signup",
                "Purchase",
                "2024-01-01",
                "2024-01-31",
                unit="day",
                interval=7,  # Custom value
            )

        # Should send 'interval' for custom intervals
        assert "interval" in captured_params
        assert captured_params["interval"] == "7"
        # Should NOT send 'unit' when using custom interval
        assert "unit" not in captured_params

    def test_retention_unit_and_interval_mutually_exclusive(
        self, test_credentials: Credentials
    ) -> None:
        """Regression: 'unit' and 'interval' params must never be sent together.

        Bug: Mixpanel API rejects requests with both 'unit' and 'interval' set together,
        returning "Validate failed: unit and interval both set".
        This test verifies that regardless of input, only one is sent.
        """
        captured_params: dict[str, Any] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            for key, value in request.url.params.items():
                captured_params[key] = value
            return httpx.Response(200, json={})

        # Test with various interval values
        for interval in [1, 2, 7, 14, 30]:
            captured_params.clear()
            with create_mock_client(test_credentials, handler) as client:
                client.retention(
                    "Signup",
                    "Purchase",
                    "2024-01-01",
                    "2024-01-31",
                    unit="day",
                    interval=interval,
                )

            # Only one of 'unit' or 'interval' should be present, never both
            has_unit = "unit" in captured_params
            has_interval = "interval" in captured_params
            assert not (
                has_unit and has_interval
            ), f"Both 'unit' and 'interval' sent for interval={interval}"
            # At least one should be present
            assert (
                has_unit or has_interval
            ), f"Neither 'unit' nor 'interval' sent for interval={interval}"


# =============================================================================
# User Story 8: JQL
# =============================================================================


class TestJQL:
    """Test JQL queries (US8)."""

    def test_jql_basic(self, test_credentials: Credentials) -> None:
        """Should execute JQL script with form-encoded data."""
        captured_body: dict[str, str] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            if request.content:
                nonlocal captured_body
                # Parse form-encoded data
                from urllib.parse import parse_qs

                parsed = parse_qs(request.content.decode())
                captured_body = {k: v[0] for k, v in parsed.items()}
            return httpx.Response(200, json=[{"key": "value"}])

        with create_mock_client(test_credentials, handler) as client:
            result = client.jql("function main() { return []; }")

        assert "script" in captured_body
        assert result == [{"key": "value"}]

    def test_jql_with_params(self, test_credentials: Credentials) -> None:
        """Should pass params as JSON string in form data."""
        captured_body: dict[str, str] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            if request.content:
                nonlocal captured_body
                # Parse form-encoded data
                from urllib.parse import parse_qs

                parsed = parse_qs(request.content.decode())
                captured_body = {k: v[0] for k, v in parsed.items()}
            return httpx.Response(200, json=[])

        with create_mock_client(test_credentials, handler) as client:
            client.jql("function main() { return []; }", params={"from": "2024-01-01"})

        assert "params" in captured_body
        # params should be a JSON-encoded string
        assert json.loads(captured_body["params"]) == {"from": "2024-01-01"}


# =============================================================================
# Error Handling
# =============================================================================


class TestErrorHandling:
    """Test error handling."""

    def test_query_error_on_400(self, test_credentials: Credentials) -> None:
        """Should raise QueryError on 400."""

        def handler(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(400, json={"error": "Invalid query"})

        with (
            create_mock_client(test_credentials, handler) as client,
            pytest.raises(QueryError) as exc_info,
        ):
            client.get_events()

        assert "Invalid query" in str(exc_info.value)

    def test_jql_syntax_error_on_412(self, test_credentials: Credentials) -> None:
        """Should raise JQLSyntaxError on 412 with parsed error details."""
        from mixpanel_data.exceptions import JQLSyntaxError

        raw_error = (
            "UserVisiblePreconditionFailedError: Uncaught exception TypeError: "
            "Events(...).groupBy(...).limit is not a function\n"
            "  .limit(10);\n"
            "   ^\n"
            "\n"
            "Stack trace:\n"
            "TypeError: Events(...).groupBy(...).limit is not a function\n"
            "    at main (<anonymous>:7:4)\n"
        )

        def handler(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                412,
                json={
                    "request": "/api/query/jql?project_id=12345",
                    "error": raw_error,
                },
            )

        script = "function main() { return Events({}).groupBy().limit(10); }"

        with (
            create_mock_client(test_credentials, handler) as client,
            pytest.raises(JQLSyntaxError) as exc_info,
        ):
            client.jql(script)

        exc = exc_info.value
        assert exc.error_type == "TypeError"
        assert "limit is not a function" in exc.error_message
        assert exc.script == script
        assert exc.raw_error == raw_error
        assert exc.code == "JQL_SYNTAX_ERROR"

    def test_jql_syntax_error_includes_line_info(
        self, test_credentials: Credentials
    ) -> None:
        """JQLSyntaxError should include code snippet with caret."""
        from mixpanel_data.exceptions import JQLSyntaxError

        def handler(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                412,
                json={
                    "error": "TypeError: bad\n  .badMethod();\n   ^\n",
                },
            )

        with (
            create_mock_client(test_credentials, handler) as client,
            pytest.raises(JQLSyntaxError) as exc_info,
        ):
            client.jql("test script")

        assert exc_info.value.line_info is not None
        assert ".badMethod();" in exc_info.value.line_info
        assert "^" in exc_info.value.line_info

    def test_jql_syntax_error_catchable_as_query_error(
        self, test_credentials: Credentials
    ) -> None:
        """JQLSyntaxError should be catchable as QueryError for backwards compat."""

        def handler(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(412, json={"error": "SyntaxError: test"})

        with (
            create_mock_client(test_credentials, handler) as client,
            pytest.raises(QueryError),  # Should catch JQLSyntaxError
        ):
            client.jql("bad script")

    def test_412_without_json_falls_back_to_query_error(
        self, test_credentials: Credentials
    ) -> None:
        """412 without valid JSON should raise QueryError."""

        def handler(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(412, text="Not JSON")

        with (
            create_mock_client(test_credentials, handler) as client,
            pytest.raises(QueryError) as exc_info,
        ):
            client.jql("test")

        assert "JQL failed" in str(exc_info.value)

    def test_query_error_on_400_with_plain_text(
        self, test_credentials: Credentials
    ) -> None:
        """Should raise QueryError with plain text response on 400."""

        def handler(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(400, text="Bad request: missing required field")

        with (
            create_mock_client(test_credentials, handler) as client,
            pytest.raises(QueryError) as exc_info,
        ):
            client.get_events()

        assert "Bad request: missing required field" in str(exc_info.value)


class TestServerErrors:
    """Test 5xx server error handling."""

    def test_server_error_with_dict_body(self, test_credentials: Credentials) -> None:
        """Should raise ServerError with error message from dict."""
        from mixpanel_data.exceptions import ServerError

        def handler(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(500, json={"error": "Internal database error"})

        with (
            create_mock_client(test_credentials, handler) as client,
            pytest.raises(ServerError) as exc_info,
        ):
            client.get_events()

        assert "Internal database error" in str(exc_info.value)
        assert exc_info.value.status_code == 500

    def test_server_error_with_string_body(self, test_credentials: Credentials) -> None:
        """Should raise ServerError with truncated string body."""
        from mixpanel_data.exceptions import ServerError

        def handler(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(503, text="Service temporarily unavailable")

        with (
            create_mock_client(test_credentials, handler) as client,
            pytest.raises(ServerError) as exc_info,
        ):
            client.get_events()

        assert "Service temporarily unavailable" in str(exc_info.value)
        assert exc_info.value.status_code == 503

    def test_server_error_with_empty_body(self, test_credentials: Credentials) -> None:
        """Should raise ServerError with status code only."""
        from mixpanel_data.exceptions import ServerError

        def handler(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(502, text="")

        with (
            create_mock_client(test_credentials, handler) as client,
            pytest.raises(ServerError) as exc_info,
        ):
            client.get_events()

        assert "Server error: 502" in str(exc_info.value)


# =============================================================================
# Regression Tests: Request Encoding
# =============================================================================


class TestRequestEncodingRegression:
    """Regression tests for request encoding.

    These tests verify that request bodies are encoded correctly and would
    catch issues like double-serialization of JSON data.
    """

    def test_jql_params_not_double_serialized(
        self, test_credentials: Credentials
    ) -> None:
        """JQL params should be a JSON string, not double-serialized.

        Regression: params were being json.dumps'd then sent via json=data,
        causing double-serialization. API would receive escaped JSON strings.
        """
        from urllib.parse import parse_qs

        captured_content: bytes = b""
        captured_content_type: str = ""

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal captured_content, captured_content_type
            captured_content = request.content
            captured_content_type = request.headers.get("content-type", "")
            return httpx.Response(200, json=[])

        with create_mock_client(test_credentials, handler) as client:
            client.jql(
                "function main() { return []; }",
                params={"key": "value", "nested": {"a": 1}},
            )

        # Verify form-encoded content type
        assert "application/x-www-form-urlencoded" in captured_content_type

        # Parse the form data
        parsed = parse_qs(captured_content.decode())
        params_value = parsed["params"][0]

        # Parse the JSON string - should decode cleanly to original dict
        parsed_params = json.loads(params_value)
        assert parsed_params == {"key": "value", "nested": {"a": 1}}

        # Verify it's not double-serialized (would be a string if double-serialized)
        assert isinstance(parsed_params["nested"], dict)
        assert not isinstance(parsed_params["nested"], str)

    def test_jql_uses_form_encoding_not_json_body(
        self, test_credentials: Credentials
    ) -> None:
        """JQL should use form-encoded body, not JSON body.

        Regression: Using json= parameter instead of data= for form encoding.
        """
        captured_content_type: str = ""

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal captured_content_type
            captured_content_type = request.headers.get("content-type", "")
            return httpx.Response(200, json=[])

        with create_mock_client(test_credentials, handler) as client:
            client.jql("function main() { return []; }")

        # Must be form-encoded, not JSON
        assert "application/x-www-form-urlencoded" in captured_content_type
        assert "application/json" not in captured_content_type

    def test_profile_export_uses_json_body(self, test_credentials: Credentials) -> None:
        """Profile export should use JSON body (not form-encoded).

        Ensures we correctly distinguish which APIs need which encoding.
        """
        captured_content_type: str = ""

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal captured_content_type
            captured_content_type = request.headers.get("content-type", "")
            return httpx.Response(200, json={"results": []})

        with create_mock_client(test_credentials, handler) as client:
            list(client.export_profiles())

        # Profile export uses JSON body
        assert "application/json" in captured_content_type


# =============================================================================
# Regression Tests: State Reset in Retry Scenarios
# =============================================================================


class TestRetryStateResetRegression:
    """Regression tests for state reset during retry scenarios.

    These tests verify that internal state is properly reset between retry
    attempts, preventing state accumulation bugs.
    """

    def test_batch_count_resets_on_retry(self, test_credentials: Credentials) -> None:
        """Batch count should reset to zero on each retry attempt.

        Regression: batch_count was not reset between retries, causing
        accumulated counts across retry attempts.
        """
        attempt = 0
        batch_counts_per_attempt: list[list[int]] = []
        current_attempt_counts: list[int] = []

        # Create enough events to trigger on_batch callback
        events_data = "\n".join(
            json.dumps({"event": f"E{i}", "properties": {"time": i}})
            for i in range(1500)
        )
        mock_data = events_data.encode() + b"\n"

        def handler(_request: httpx.Request) -> httpx.Response:
            nonlocal attempt, current_attempt_counts, batch_counts_per_attempt
            attempt += 1

            # Save counts from previous attempt
            if current_attempt_counts:
                batch_counts_per_attempt.append(current_attempt_counts.copy())
            current_attempt_counts.clear()

            if attempt == 1:
                # First attempt: rate limited
                return httpx.Response(429, headers={"Retry-After": "0"})
            # Second attempt: success
            return httpx.Response(200, content=mock_data)

        def on_batch(count: int) -> None:
            current_attempt_counts.append(count)

        transport = httpx.MockTransport(handler)
        client = MixpanelAPIClient(
            test_credentials, max_retries=3, _transport=transport
        )

        with client:
            list(client.export_events("2024-01-01", "2024-01-31", on_batch=on_batch))

        # Save final attempt counts
        if current_attempt_counts:
            batch_counts_per_attempt.append(current_attempt_counts.copy())

        # Verify second attempt counts start from 0, not accumulated
        assert len(batch_counts_per_attempt) >= 1
        last_attempt_counts = batch_counts_per_attempt[-1]

        # First batch count should be 1000 (batch size), not accumulated
        assert 1000 in last_attempt_counts
        # Final count should be 1500, not 1500 + whatever was counted before
        assert 1500 in last_attempt_counts

    def test_profile_page_count_resets_on_retry(
        self, test_credentials: Credentials
    ) -> None:
        """Profile page count should reset on retry attempt.

        Verifies that pagination state doesn't accumulate across retries.
        """
        attempt = 0
        page_counts_per_attempt: list[list[int]] = []
        current_attempt_counts: list[int] = []

        def handler(_request: httpx.Request) -> httpx.Response:
            nonlocal attempt, current_attempt_counts, page_counts_per_attempt
            attempt += 1

            if attempt == 1:
                # First attempt: rate limited
                return httpx.Response(429, headers={"Retry-After": "0"})

            # Subsequent attempts: paginated response
            if attempt == 2:
                return httpx.Response(
                    200,
                    json={
                        "results": [{"$distinct_id": "u1"}],
                        "session_id": "abc123",
                    },
                )
            return httpx.Response(
                200,
                json={"results": [], "session_id": None},
            )

        def on_batch(count: int) -> None:
            current_attempt_counts.append(count)

        transport = httpx.MockTransport(handler)
        client = MixpanelAPIClient(
            test_credentials, max_retries=3, _transport=transport
        )

        with client:
            profiles = list(client.export_profiles(on_batch=on_batch))

        # Should have gotten profiles from retry
        assert len(profiles) == 1

        # on_batch should have been called with counts starting fresh
        # If state wasn't reset, counts would be wrong
        assert current_attempt_counts == [1]

    def test_multiple_retries_dont_accumulate_state(
        self, test_credentials: Credentials
    ) -> None:
        """Multiple retry attempts should each start fresh.

        Verifies no state leakage across multiple retry cycles.
        """
        attempts = 0

        # Small event set to keep test fast
        events_data = "\n".join(
            json.dumps({"event": f"E{i}", "properties": {"time": i}}) for i in range(5)
        )
        mock_data = events_data.encode() + b"\n"

        def handler(_request: httpx.Request) -> httpx.Response:
            nonlocal attempts
            attempts += 1
            if attempts < 3:
                return httpx.Response(429, headers={"Retry-After": "0"})
            return httpx.Response(200, content=mock_data)

        transport = httpx.MockTransport(handler)
        client = MixpanelAPIClient(
            test_credentials, max_retries=3, _transport=transport
        )

        with client:
            events = list(client.export_events("2024-01-01", "2024-01-31"))

        # Should have made 3 attempts (2 rate-limited + 1 success)
        assert attempts == 3

        # Should have exactly 5 events (not accumulated across attempts)
        assert len(events) == 5


# =============================================================================
# Public request() Method - Escape Hatch for Arbitrary APIs
# =============================================================================


class TestPublicRequest:
    """Test the public request() method for arbitrary API calls."""

    def test_request_sends_auth_header(self, test_credentials: Credentials) -> None:
        """request() should send authentication header."""
        captured_headers: dict[str, str] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured_headers.update(dict(request.headers))
            return httpx.Response(200, json={"result": "ok"})

        with create_mock_client(test_credentials, handler) as client:
            client.request("GET", "https://mixpanel.com/api/app/test")

        assert "authorization" in captured_headers
        assert captured_headers["authorization"].startswith("Basic ")

    def test_request_with_query_params(self, test_credentials: Credentials) -> None:
        """request() should include query parameters."""
        captured_url: str = ""

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal captured_url
            captured_url = str(request.url)
            return httpx.Response(200, json={})

        with create_mock_client(test_credentials, handler) as client:
            client.request(
                "GET",
                "https://mixpanel.com/api/app/test",
                params={"foo": "bar", "limit": 10},
            )

        assert "foo=bar" in captured_url
        assert "limit=10" in captured_url

    def test_request_with_json_body(self, test_credentials: Credentials) -> None:
        """request() should send JSON body for POST requests."""
        captured_body: dict[str, Any] = {}
        captured_content_type: str = ""

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal captured_body, captured_content_type
            captured_content_type = request.headers.get("content-type", "")
            if request.content:
                captured_body = json.loads(request.content)
            return httpx.Response(200, json={"created": True})

        with create_mock_client(test_credentials, handler) as client:
            client.request(
                "POST",
                "https://mixpanel.com/api/app/projects/12345/data",
                json_body={"name": "test", "value": 123},
            )

        assert "application/json" in captured_content_type
        assert captured_body == {"name": "test", "value": 123}

    def test_request_with_custom_headers(self, test_credentials: Credentials) -> None:
        """request() should merge custom headers with auth."""
        captured_headers: dict[str, str] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured_headers.update(dict(request.headers))
            return httpx.Response(200, json={})

        with create_mock_client(test_credentials, handler) as client:
            client.request(
                "GET",
                "https://mixpanel.com/api/app/test",
                headers={"X-Custom-Header": "custom-value"},
            )

        # Should have both auth and custom headers
        assert "authorization" in captured_headers
        assert captured_headers["x-custom-header"] == "custom-value"

    def test_request_does_not_inject_project_id(
        self, test_credentials: Credentials
    ) -> None:
        """request() should NOT automatically inject project_id (user controls URL)."""
        captured_url: str = ""

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal captured_url
            captured_url = str(request.url)
            return httpx.Response(200, json={})

        with create_mock_client(test_credentials, handler) as client:
            client.request("GET", "https://mixpanel.com/api/app/test")

        # project_id should NOT be automatically added
        assert "project_id" not in captured_url

    def test_request_returns_json_response(self, test_credentials: Credentials) -> None:
        """request() should return parsed JSON response."""

        def handler(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                json={"data": {"events": ["A", "B"]}, "status": "ok"},
            )

        with create_mock_client(test_credentials, handler) as client:
            result = client.request("GET", "https://mixpanel.com/api/app/test")

        assert result == {"data": {"events": ["A", "B"]}, "status": "ok"}

    def test_request_handles_401(self, test_credentials: Credentials) -> None:
        """request() should raise AuthenticationError on 401."""

        def handler(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(401, json={"error": "Invalid token"})

        with (
            create_mock_client(test_credentials, handler) as client,
            pytest.raises(AuthenticationError),
        ):
            client.request("GET", "https://mixpanel.com/api/app/test")

    def test_request_handles_400(self, test_credentials: Credentials) -> None:
        """request() should raise QueryError on 400."""

        def handler(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(400, json={"error": "Bad request"})

        with (
            create_mock_client(test_credentials, handler) as client,
            pytest.raises(QueryError) as exc_info,
        ):
            client.request("GET", "https://mixpanel.com/api/app/test")

        assert "Bad request" in str(exc_info.value)

    def test_request_handles_429_with_retry(
        self, test_credentials: Credentials
    ) -> None:
        """request() should retry on 429."""
        call_count = 0

        def handler(_request: httpx.Request) -> httpx.Response:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return httpx.Response(429, headers={"Retry-After": "0"})
            return httpx.Response(200, json={"success": True})

        with create_mock_client(test_credentials, handler) as client:
            result = client.request("GET", "https://mixpanel.com/api/app/test")

        assert call_count == 2
        assert result == {"success": True}

    def test_request_raises_rate_limit_after_max_retries(
        self, test_credentials: Credentials
    ) -> None:
        """request() should raise RateLimitError after max retries."""

        def handler(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(429, headers={"Retry-After": "0"})

        transport = httpx.MockTransport(handler)
        client = MixpanelAPIClient(
            test_credentials, max_retries=1, _transport=transport
        )

        with client, pytest.raises(RateLimitError) as exc_info:
            client.request("GET", "https://mixpanel.com/api/app/test")

        assert exc_info.value.retry_after == 0

    def test_request_lexicon_schemas_example(
        self, test_credentials: Credentials
    ) -> None:
        """Example: Fetch event schema from Lexicon API."""
        captured_url: str = ""
        captured_method: str = ""

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal captured_url, captured_method
            captured_url = str(request.url)
            captured_method = request.method
            return httpx.Response(
                200,
                json={
                    "entityType": "event",
                    "name": "Added To Cart",
                    "schemaJson": {"properties": {}},
                },
            )

        with create_mock_client(test_credentials, handler) as client:
            project_id = client.project_id
            result = client.request(
                "GET",
                f"https://mixpanel.com/api/app/projects/{project_id}/schemas/event/Added%20To%20Cart",
            )

        assert captured_method == "GET"
        assert "/projects/12345/schemas/event/Added%20To%20Cart" in captured_url
        assert result["entityType"] == "event"
        assert result["name"] == "Added To Cart"


class TestAPIClientProperties:
    """Test project_id and region properties on MixpanelAPIClient."""

    def test_project_id_property(self, test_credentials: Credentials) -> None:
        """project_id property should return credentials project_id."""
        client = MixpanelAPIClient(test_credentials)
        assert client.project_id == "12345"
        client.close()

    def test_region_property_us(self, test_credentials: Credentials) -> None:
        """region property should return US for US credentials."""
        client = MixpanelAPIClient(test_credentials)
        assert client.region == "us"
        client.close()

    def test_region_property_eu(self, eu_credentials: Credentials) -> None:
        """region property should return EU for EU credentials."""
        client = MixpanelAPIClient(eu_credentials)
        assert client.region == "eu"
        client.close()

    def test_region_property_india(self, india_credentials: Credentials) -> None:
        """region property should return IN for India credentials."""
        client = MixpanelAPIClient(india_credentials)
        assert client.region == "in"
        client.close()
