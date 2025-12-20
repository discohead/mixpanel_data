"""Unit tests for MixpanelAPIClient.

Tests use httpx.MockTransport for deterministic HTTP mocking.
"""

from __future__ import annotations

import json
from typing import Any

import httpx
import pytest

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
        secret="test_secret",
        project_id="12345",
        region="us",
    )


@pytest.fixture
def eu_credentials() -> Credentials:
    """Create EU region test credentials."""
    return Credentials(
        username="test_user",
        secret="test_secret",
        project_id="12345",
        region="eu",
    )


@pytest.fixture
def india_credentials() -> Credentials:
    """Create India region test credentials."""
    return Credentials(
        username="test_user",
        secret="test_secret",
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
            return httpx.Response(429, headers={"Retry-After": "60"})

        transport = httpx.MockTransport(handler)
        client = MixpanelAPIClient(
            test_credentials, max_retries=1, _transport=transport
        )

        with client, pytest.raises(RateLimitError) as exc_info:
            client.get_events()

        assert exc_info.value.retry_after == 60

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
