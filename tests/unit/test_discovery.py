"""Unit tests for DiscoveryService.

Tests use httpx.MockTransport for deterministic HTTP mocking.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

import httpx
import pytest

from mixpanel_data._internal.services.discovery import DiscoveryService
from mixpanel_data.exceptions import AuthenticationError, QueryError

if TYPE_CHECKING:
    from mixpanel_data._internal.api_client import MixpanelAPIClient


@pytest.fixture
def discovery_factory(
    request: pytest.FixtureRequest,
    mock_client_factory: Callable[
        [Callable[[httpx.Request], httpx.Response]], MixpanelAPIClient
    ],
) -> Callable[[Callable[[httpx.Request], httpx.Response]], DiscoveryService]:
    """Factory for creating DiscoveryService with mock API client.

    Usage:
        def test_something(discovery_factory):
            def handler(request):
                return httpx.Response(200, json=["event1", "event2"])

            discovery = discovery_factory(handler)
            result = discovery.list_events()
    """
    clients: list[MixpanelAPIClient] = []

    def factory(
        handler: Callable[[httpx.Request], httpx.Response],
    ) -> DiscoveryService:
        client = mock_client_factory(handler)
        # Enter context to ensure client is initialized
        client.__enter__()
        clients.append(client)
        return DiscoveryService(client)

    def cleanup() -> None:
        for client in clients:
            client.__exit__(None, None, None)

    request.addfinalizer(cleanup)
    return factory


class TestDiscoveryService:
    """Tests for DiscoveryService initialization."""

    def test_init_with_api_client(
        self,
        mock_client_factory: Callable[
            [Callable[[httpx.Request], httpx.Response]], MixpanelAPIClient
        ],
        success_handler: Callable[[httpx.Request], httpx.Response],
    ) -> None:
        """DiscoveryService should accept an API client."""
        client = mock_client_factory(success_handler)
        discovery = DiscoveryService(client)
        assert discovery._api_client is client

    def test_init_creates_empty_cache(
        self,
        mock_client_factory: Callable[
            [Callable[[httpx.Request], httpx.Response]], MixpanelAPIClient
        ],
        success_handler: Callable[[httpx.Request], httpx.Response],
    ) -> None:
        """DiscoveryService should initialize with empty cache."""
        client = mock_client_factory(success_handler)
        discovery = DiscoveryService(client)
        assert discovery._cache == {}


# =============================================================================
# User Story 1: list_events() Tests
# =============================================================================


class TestListEvents:
    """Tests for DiscoveryService.list_events()."""

    def test_list_events_returns_sorted_list(
        self,
        discovery_factory: Callable[
            [Callable[[httpx.Request], httpx.Response]], DiscoveryService
        ],
    ) -> None:
        """list_events() should return events sorted alphabetically."""

        def handler(_request: httpx.Request) -> httpx.Response:
            # Return unsorted list to verify sorting
            return httpx.Response(
                200, json=["Signup", "Login", "Purchase", "Add to Cart"]
            )

        discovery = discovery_factory(handler)
        events = discovery.list_events()

        assert events == ["Add to Cart", "Login", "Purchase", "Signup"]

    def test_list_events_caching_behavior(
        self,
        discovery_factory: Callable[
            [Callable[[httpx.Request], httpx.Response]], DiscoveryService
        ],
    ) -> None:
        """list_events() should cache results and not call API on second request."""
        call_count = 0

        def handler(_request: httpx.Request) -> httpx.Response:
            nonlocal call_count
            call_count += 1
            return httpx.Response(200, json=["Event1", "Event2"])

        discovery = discovery_factory(handler)

        # First call
        events1 = discovery.list_events()
        assert call_count == 1

        # Second call should use cache
        events2 = discovery.list_events()
        assert call_count == 1  # Still 1, not incremented

        # Results should be identical
        assert events1 == events2

    def test_list_events_with_authentication_error(
        self,
        discovery_factory: Callable[
            [Callable[[httpx.Request], httpx.Response]], DiscoveryService
        ],
    ) -> None:
        """list_events() should propagate AuthenticationError from API client."""

        def handler(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(401, json={"error": "Invalid credentials"})

        discovery = discovery_factory(handler)

        with pytest.raises(AuthenticationError):
            discovery.list_events()

    def test_list_events_with_empty_result(
        self,
        discovery_factory: Callable[
            [Callable[[httpx.Request], httpx.Response]], DiscoveryService
        ],
    ) -> None:
        """list_events() should return empty list when no events exist."""

        def handler(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json=[])

        discovery = discovery_factory(handler)
        events = discovery.list_events()

        assert events == []


# =============================================================================
# User Story 2: list_properties() Tests
# =============================================================================


class TestListProperties:
    """Tests for DiscoveryService.list_properties()."""

    def test_list_properties_returns_sorted_list(
        self,
        discovery_factory: Callable[
            [Callable[[httpx.Request], httpx.Response]], DiscoveryService
        ],
    ) -> None:
        """list_properties() should return properties sorted alphabetically."""

        def handler(_request: httpx.Request) -> httpx.Response:
            # Return unsorted dict to verify sorting (API returns dict with counts)
            return httpx.Response(
                200, json={"user_id": 100, "amount": 50, "currency": 75}
            )

        discovery = discovery_factory(handler)
        properties = discovery.list_properties("Purchase")

        assert properties == ["amount", "currency", "user_id"]

    def test_list_properties_caching_per_event(
        self,
        discovery_factory: Callable[
            [Callable[[httpx.Request], httpx.Response]], DiscoveryService
        ],
    ) -> None:
        """list_properties() should cache results per event name."""
        call_count = 0

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal call_count
            call_count += 1
            # Return different results based on the event parameter
            if "event=Purchase" in str(request.url):
                return httpx.Response(200, json={"amount": 1, "currency": 1})
            return httpx.Response(200, json={"user_id": 1, "email": 1})

        discovery = discovery_factory(handler)

        # First call for Purchase
        props1 = discovery.list_properties("Purchase")
        assert call_count == 1

        # Second call for Purchase should use cache
        props2 = discovery.list_properties("Purchase")
        assert call_count == 1  # Still 1

        # Call for different event should hit API
        props3 = discovery.list_properties("Signup")
        assert call_count == 2

        # Results should be correct
        assert props1 == props2 == ["amount", "currency"]
        assert props3 == ["email", "user_id"]

    def test_list_properties_with_query_error(
        self,
        discovery_factory: Callable[
            [Callable[[httpx.Request], httpx.Response]], DiscoveryService
        ],
    ) -> None:
        """list_properties() should propagate QueryError for invalid event."""

        def handler(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(400, json={"error": "Invalid event name"})

        discovery = discovery_factory(handler)

        with pytest.raises(QueryError):
            discovery.list_properties("NonExistentEvent")

    def test_list_properties_with_empty_result(
        self,
        discovery_factory: Callable[
            [Callable[[httpx.Request], httpx.Response]], DiscoveryService
        ],
    ) -> None:
        """list_properties() should return empty list when event has no properties."""

        def handler(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={})

        discovery = discovery_factory(handler)
        properties = discovery.list_properties("EmptyEvent")

        assert properties == []


# =============================================================================
# User Story 3: list_property_values() Tests
# =============================================================================


class TestListPropertyValues:
    """Tests for DiscoveryService.list_property_values()."""

    def test_list_property_values_basic_call(
        self,
        discovery_factory: Callable[
            [Callable[[httpx.Request], httpx.Response]], DiscoveryService
        ],
    ) -> None:
        """list_property_values() should return values from API."""

        def handler(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json=["US", "CA", "GB", "DE"])

        discovery = discovery_factory(handler)
        values = discovery.list_property_values("country")

        # Note: values are NOT sorted per research.md
        assert values == ["US", "CA", "GB", "DE"]

    def test_list_property_values_with_event_scope(
        self,
        discovery_factory: Callable[
            [Callable[[httpx.Request], httpx.Response]], DiscoveryService
        ],
    ) -> None:
        """list_property_values() should pass event parameter to API."""

        def handler(request: httpx.Request) -> httpx.Response:
            # Verify event parameter is passed
            if "event=Purchase" in str(request.url):
                return httpx.Response(200, json=["credit_card", "paypal"])
            return httpx.Response(200, json=["all_values"])

        discovery = discovery_factory(handler)
        values = discovery.list_property_values("payment_method", event="Purchase")

        assert values == ["credit_card", "paypal"]

    def test_list_property_values_with_custom_limit(
        self,
        discovery_factory: Callable[
            [Callable[[httpx.Request], httpx.Response]], DiscoveryService
        ],
    ) -> None:
        """list_property_values() should pass limit parameter to API."""

        def handler(request: httpx.Request) -> httpx.Response:
            # Verify limit parameter is passed
            if "limit=10" in str(request.url):
                return httpx.Response(200, json=["v1", "v2", "v3"])
            return httpx.Response(200, json=["all_values"])

        discovery = discovery_factory(handler)
        values = discovery.list_property_values("country", limit=10)

        assert values == ["v1", "v2", "v3"]

    def test_list_property_values_caching(
        self,
        discovery_factory: Callable[
            [Callable[[httpx.Request], httpx.Response]], DiscoveryService
        ],
    ) -> None:
        """list_property_values() should cache per (property, event, limit)."""
        call_count = 0

        def handler(_request: httpx.Request) -> httpx.Response:
            nonlocal call_count
            call_count += 1
            return httpx.Response(200, json=["value1", "value2"])

        discovery = discovery_factory(handler)

        # First call
        values1 = discovery.list_property_values("country", event="Purchase", limit=50)
        assert call_count == 1

        # Same params should use cache
        values2 = discovery.list_property_values("country", event="Purchase", limit=50)
        assert call_count == 1

        # Different limit should hit API
        discovery.list_property_values("country", event="Purchase", limit=100)
        assert call_count == 2

        # Different event should hit API
        discovery.list_property_values("country", event="Signup", limit=50)
        assert call_count == 3

        # Results should match
        assert values1 == values2 == ["value1", "value2"]

    def test_list_property_values_with_empty_result(
        self,
        discovery_factory: Callable[
            [Callable[[httpx.Request], httpx.Response]], DiscoveryService
        ],
    ) -> None:
        """list_property_values() should return empty list when no values exist."""

        def handler(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json=[])

        discovery = discovery_factory(handler)
        values = discovery.list_property_values("nonexistent_property")

        assert values == []


# =============================================================================
# User Story 4: clear_cache() Tests
# =============================================================================


class TestClearCache:
    """Tests for DiscoveryService.clear_cache()."""

    def test_clear_cache_clears_all_results(
        self,
        discovery_factory: Callable[
            [Callable[[httpx.Request], httpx.Response]], DiscoveryService
        ],
    ) -> None:
        """clear_cache() should clear all cached results."""

        def handler(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json=["event1", "event2"])

        discovery = discovery_factory(handler)

        # Populate cache
        discovery.list_events()
        assert len(discovery._cache) > 0

        # Clear cache
        discovery.clear_cache()
        assert discovery._cache == {}

    def test_clear_cache_on_empty_cache(
        self,
        discovery_factory: Callable[
            [Callable[[httpx.Request], httpx.Response]], DiscoveryService
        ],
    ) -> None:
        """clear_cache() should not error when cache is empty."""

        def handler(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json=[])

        discovery = discovery_factory(handler)

        # Cache should be empty initially
        assert discovery._cache == {}

        # Clearing empty cache should not raise
        discovery.clear_cache()
        assert discovery._cache == {}

    def test_clear_cache_causes_api_call(
        self,
        discovery_factory: Callable[
            [Callable[[httpx.Request], httpx.Response]], DiscoveryService
        ],
    ) -> None:
        """clear_cache() should cause next request to hit API."""
        call_count = 0

        def handler(_request: httpx.Request) -> httpx.Response:
            nonlocal call_count
            call_count += 1
            return httpx.Response(200, json=["event1", "event2"])

        discovery = discovery_factory(handler)

        # First call hits API
        discovery.list_events()
        assert call_count == 1

        # Second call uses cache
        discovery.list_events()
        assert call_count == 1

        # Clear cache
        discovery.clear_cache()

        # Third call should hit API again
        discovery.list_events()
        assert call_count == 2
