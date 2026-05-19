"""Unit tests for DiscoveryService.

Tests use httpx.MockTransport for deterministic HTTP mocking.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import TYPE_CHECKING

import httpx
import pytest

from mixpanel_headless._internal.services.discovery import DiscoveryService
from mixpanel_headless.exceptions import (
    AuthenticationError,
    EventNotFoundError,
    QueryError,
)

if TYPE_CHECKING:
    from mixpanel_headless._internal.api_client import MixpanelAPIClient


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

    def test_list_events_caches_per_args_triple(
        self,
        discovery_factory: Callable[
            [Callable[[httpx.Request], httpx.Response]], DiscoveryService
        ],
    ) -> None:
        """Cache key is the (limit, from_date, to_date) triple.

        Calls with the same triple share a cache slot; calls with
        different triples each hit the API.
        """
        call_count = 0

        def handler(_request: httpx.Request) -> httpx.Response:
            nonlocal call_count
            call_count += 1
            return httpx.Response(200, json=[f"E{call_count}"])

        discovery = discovery_factory(handler)

        discovery.list_events(limit=10)
        discovery.list_events(limit=10)
        assert call_count == 1  # second call cached

        discovery.list_events(limit=20)
        assert call_count == 2  # different triple, new HTTP call

        discovery.list_events()  # all-None triple, distinct from above
        assert call_count == 3

    def test_list_events_forwards_kwargs_to_api_client(
        self,
        discovery_factory: Callable[
            [Callable[[httpx.Request], httpx.Response]], DiscoveryService
        ],
    ) -> None:
        """Caller-supplied limit/from_date/to_date reach the outbound request.

        Guards against accidental drop of the kwargs-filtering block.
        """
        captured_params: dict[str, str] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            for k, v in request.url.params.items():
                captured_params[k] = v
            return httpx.Response(200, json=["e1"])

        discovery = discovery_factory(handler)
        discovery.list_events(limit=7, from_date="2024-01-01", to_date="2024-12-31")

        assert captured_params["limit"] == "7"
        assert captured_params["from_date"] == "2024-01-01"
        assert captured_params["to_date"] == "2024-12-31"


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

    def test_list_properties_with_event_not_found_raises_with_suggestions(
        self,
        discovery_factory: Callable[
            [Callable[[httpx.Request], httpx.Response]], DiscoveryService
        ],
    ) -> None:
        """list_properties() should raise EventNotFoundError with suggestions for 400."""
        call_count = 0

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal call_count
            call_count += 1
            # First call: get events for suggestions
            if "/events/names" in str(request.url) or call_count == 2:
                return httpx.Response(
                    200, json=["Sign Up", "Login", "Purchase", "sign_up_complete"]
                )
            # Second call: get properties fails
            return httpx.Response(400, json={"error": "Invalid event name"})

        discovery = discovery_factory(handler)

        with pytest.raises(EventNotFoundError) as exc_info:
            discovery.list_properties("sign up")

        # Should have case-insensitive match as suggestion
        assert exc_info.value.event_name == "sign up"
        assert "Sign Up" in exc_info.value.similar_events

    def test_list_properties_with_query_error_non_400(
        self,
        discovery_factory: Callable[
            [Callable[[httpx.Request], httpx.Response]], DiscoveryService
        ],
    ) -> None:
        """list_properties() should propagate QueryError for non-400 errors."""

        def handler(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(403, json={"error": "Permission denied"})

        discovery = discovery_factory(handler)

        with pytest.raises(QueryError):
            discovery.list_properties("SomeEvent")

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
# Fuzzy Matching Tests
# =============================================================================


class TestFindSimilarEvents:
    """Tests for DiscoveryService._find_similar_events() fuzzy matching."""

    def test_exact_case_insensitive_match(
        self,
        discovery_factory: Callable[
            [Callable[[httpx.Request], httpx.Response]], DiscoveryService
        ],
        success_handler: Callable[[httpx.Request], httpx.Response],
    ) -> None:
        """Should find exact case-insensitive matches first."""
        discovery = discovery_factory(success_handler)
        events = ["Sign Up", "Login", "Purchase"]

        result = discovery._find_similar_events("sign up", events)

        assert result == ["Sign Up"]

    def test_substring_match(
        self,
        discovery_factory: Callable[
            [Callable[[httpx.Request], httpx.Response]], DiscoveryService
        ],
        success_handler: Callable[[httpx.Request], httpx.Response],
    ) -> None:
        """Should find events containing the query as substring."""
        discovery = discovery_factory(success_handler)
        events = ["User Sign Up", "Sign Up Complete", "Login", "sign_up_flow"]

        result = discovery._find_similar_events("sign", events)

        # Should be sorted by length (shorter = more specific)
        assert "sign_up_flow" in result
        assert "Login" not in result

    def test_word_overlap_match(
        self,
        discovery_factory: Callable[
            [Callable[[httpx.Request], httpx.Response]], DiscoveryService
        ],
        success_handler: Callable[[httpx.Request], httpx.Response],
    ) -> None:
        """Should find events with overlapping words."""
        discovery = discovery_factory(success_handler)
        events = ["User Created", "User Updated", "Order Placed", "user_deleted"]

        result = discovery._find_similar_events("user signup", events)

        # Should find events with "user" word
        assert "User Created" in result
        assert "User Updated" in result
        assert "user_deleted" in result
        assert "Order Placed" not in result

    def test_handles_underscores_and_hyphens(
        self,
        discovery_factory: Callable[
            [Callable[[httpx.Request], httpx.Response]], DiscoveryService
        ],
        success_handler: Callable[[httpx.Request], httpx.Response],
    ) -> None:
        """Should treat underscores and hyphens as word separators."""
        discovery = discovery_factory(success_handler)
        events = ["user_sign_up", "user-login", "User Logout"]

        result = discovery._find_similar_events("user", events)

        assert len(result) == 3

    def test_limits_to_five_results(
        self,
        discovery_factory: Callable[
            [Callable[[httpx.Request], httpx.Response]], DiscoveryService
        ],
        success_handler: Callable[[httpx.Request], httpx.Response],
    ) -> None:
        """Should return at most 5 suggestions."""
        discovery = discovery_factory(success_handler)
        events = [f"Event {i}" for i in range(10)]

        result = discovery._find_similar_events("event", events)

        assert len(result) <= 5

    def test_no_matches_returns_empty(
        self,
        discovery_factory: Callable[
            [Callable[[httpx.Request], httpx.Response]], DiscoveryService
        ],
        success_handler: Callable[[httpx.Request], httpx.Response],
    ) -> None:
        """Should return empty list when no matches found."""
        discovery = discovery_factory(success_handler)
        events = ["Login", "Logout", "Purchase"]

        result = discovery._find_similar_events("completely_different", events)

        assert result == []


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


# =============================================================================
# User Story 5: list_funnels() Tests
# =============================================================================


class TestListFunnels:
    """Tests for DiscoveryService.list_funnels()."""

    def test_list_funnels_returns_funnel_info_list(
        self,
        discovery_factory: Callable[
            [Callable[[httpx.Request], httpx.Response]], DiscoveryService
        ],
    ) -> None:
        """list_funnels() should return list of FunnelInfo objects."""

        def handler(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                json=[
                    {"funnel_id": 123, "name": "Checkout Funnel"},
                    {"funnel_id": 456, "name": "Onboarding Flow"},
                ],
            )

        discovery = discovery_factory(handler)
        funnels = discovery.list_funnels()

        assert len(funnels) == 2
        assert funnels[0].funnel_id == 123
        assert funnels[0].name == "Checkout Funnel"

    def test_list_funnels_returns_sorted_by_name(
        self,
        discovery_factory: Callable[
            [Callable[[httpx.Request], httpx.Response]], DiscoveryService
        ],
    ) -> None:
        """list_funnels() should return funnels sorted alphabetically by name."""

        def handler(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                json=[
                    {"funnel_id": 1, "name": "Zebra Funnel"},
                    {"funnel_id": 2, "name": "Alpha Funnel"},
                    {"funnel_id": 3, "name": "Beta Funnel"},
                ],
            )

        discovery = discovery_factory(handler)
        funnels = discovery.list_funnels()

        assert funnels[0].name == "Alpha Funnel"
        assert funnels[1].name == "Beta Funnel"
        assert funnels[2].name == "Zebra Funnel"

    def test_list_funnels_caching(
        self,
        discovery_factory: Callable[
            [Callable[[httpx.Request], httpx.Response]], DiscoveryService
        ],
    ) -> None:
        """list_funnels() should cache results."""
        call_count = 0

        def handler(_request: httpx.Request) -> httpx.Response:
            nonlocal call_count
            call_count += 1
            return httpx.Response(200, json=[{"funnel_id": 1, "name": "Funnel"}])

        discovery = discovery_factory(handler)

        funnels1 = discovery.list_funnels()
        assert call_count == 1

        funnels2 = discovery.list_funnels()
        assert call_count == 1  # Still 1, cached

        assert funnels1 == funnels2

    def test_list_funnels_empty_result(
        self,
        discovery_factory: Callable[
            [Callable[[httpx.Request], httpx.Response]], DiscoveryService
        ],
    ) -> None:
        """list_funnels() should return empty list when no funnels exist."""

        def handler(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json=[])

        discovery = discovery_factory(handler)
        funnels = discovery.list_funnels()

        assert funnels == []


# =============================================================================
# User Story 6: list_cohorts() Tests
# =============================================================================


class TestListCohorts:
    """Tests for DiscoveryService.list_cohorts()."""

    def test_list_cohorts_returns_saved_cohort_list(
        self,
        discovery_factory: Callable[
            [Callable[[httpx.Request], httpx.Response]], DiscoveryService
        ],
    ) -> None:
        """list_cohorts() should return list of SavedCohort objects."""

        def handler(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                json=[
                    {
                        "id": 123,
                        "name": "Power Users",
                        "count": 1500,
                        "description": "Users with 10+ purchases",
                        "created": "2024-01-15 10:30:00",
                        "is_visible": 1,
                        "project_id": 999,
                    },
                ],
            )

        discovery = discovery_factory(handler)
        cohorts = discovery.list_cohorts()

        assert len(cohorts) == 1
        assert cohorts[0].id == 123
        assert cohorts[0].name == "Power Users"
        assert cohorts[0].count == 1500
        assert cohorts[0].is_visible is True

    def test_list_cohorts_converts_is_visible_to_bool(
        self,
        discovery_factory: Callable[
            [Callable[[httpx.Request], httpx.Response]], DiscoveryService
        ],
    ) -> None:
        """list_cohorts() should convert is_visible int to bool."""

        def handler(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                json=[
                    {
                        "id": 1,
                        "name": "Visible",
                        "count": 100,
                        "description": "",
                        "created": "2024-01-01 00:00:00",
                        "is_visible": 1,
                    },
                    {
                        "id": 2,
                        "name": "Hidden",
                        "count": 50,
                        "description": "",
                        "created": "2024-01-01 00:00:00",
                        "is_visible": 0,
                    },
                ],
            )

        discovery = discovery_factory(handler)
        cohorts = discovery.list_cohorts()

        visible = next(c for c in cohorts if c.name == "Visible")
        hidden = next(c for c in cohorts if c.name == "Hidden")

        assert visible.is_visible is True
        assert hidden.is_visible is False

    def test_list_cohorts_returns_sorted_by_name(
        self,
        discovery_factory: Callable[
            [Callable[[httpx.Request], httpx.Response]], DiscoveryService
        ],
    ) -> None:
        """list_cohorts() should return cohorts sorted alphabetically by name."""

        def handler(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                json=[
                    {
                        "id": 1,
                        "name": "Zebra Cohort",
                        "count": 100,
                        "description": "",
                        "created": "2024-01-01 00:00:00",
                        "is_visible": 1,
                    },
                    {
                        "id": 2,
                        "name": "Alpha Cohort",
                        "count": 50,
                        "description": "",
                        "created": "2024-01-01 00:00:00",
                        "is_visible": 1,
                    },
                ],
            )

        discovery = discovery_factory(handler)
        cohorts = discovery.list_cohorts()

        assert cohorts[0].name == "Alpha Cohort"
        assert cohorts[1].name == "Zebra Cohort"

    def test_list_cohorts_caching(
        self,
        discovery_factory: Callable[
            [Callable[[httpx.Request], httpx.Response]], DiscoveryService
        ],
    ) -> None:
        """list_cohorts() should cache results."""
        call_count = 0

        def handler(_request: httpx.Request) -> httpx.Response:
            nonlocal call_count
            call_count += 1
            return httpx.Response(
                200,
                json=[
                    {
                        "id": 1,
                        "name": "Cohort",
                        "count": 100,
                        "description": "",
                        "created": "2024-01-01 00:00:00",
                        "is_visible": 1,
                    }
                ],
            )

        discovery = discovery_factory(handler)

        cohorts1 = discovery.list_cohorts()
        assert call_count == 1

        cohorts2 = discovery.list_cohorts()
        assert call_count == 1  # Cached

        assert cohorts1 == cohorts2

    def test_list_cohorts_empty_result(
        self,
        discovery_factory: Callable[
            [Callable[[httpx.Request], httpx.Response]], DiscoveryService
        ],
    ) -> None:
        """list_cohorts() should return empty list when no cohorts exist."""

        def handler(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json=[])

        discovery = discovery_factory(handler)
        cohorts = discovery.list_cohorts()

        assert cohorts == []


# =============================================================================
# User Story 7: list_top_events() Tests
# =============================================================================


class TestListTopEvents:
    """Tests for DiscoveryService.list_top_events()."""

    def test_list_top_events_returns_top_event_list(
        self,
        discovery_factory: Callable[
            [Callable[[httpx.Request], httpx.Response]], DiscoveryService
        ],
    ) -> None:
        """list_top_events() should return list of TopEvent objects."""

        def handler(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                json={
                    "events": [
                        {"event": "Sign Up", "amount": 1500, "percent_change": 0.25},
                        {"event": "Purchase", "amount": 500, "percent_change": -0.10},
                    ],
                    "type": "general",
                },
            )

        discovery = discovery_factory(handler)
        events = discovery.list_top_events()

        assert len(events) == 2
        assert events[0].event == "Sign Up"
        assert events[0].count == 1500
        assert events[0].percent_change == 0.25

    def test_list_top_events_maps_amount_to_count(
        self,
        discovery_factory: Callable[
            [Callable[[httpx.Request], httpx.Response]], DiscoveryService
        ],
    ) -> None:
        """list_top_events() should map API 'amount' field to 'count'."""

        def handler(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                json={
                    "events": [
                        {"event": "Test", "amount": 999, "percent_change": 0.0},
                    ],
                    "type": "general",
                },
            )

        discovery = discovery_factory(handler)
        events = discovery.list_top_events()

        assert events[0].count == 999  # 'amount' mapped to 'count'

    def test_list_top_events_not_cached(
        self,
        discovery_factory: Callable[
            [Callable[[httpx.Request], httpx.Response]], DiscoveryService
        ],
    ) -> None:
        """list_top_events() should NOT cache results (real-time data)."""
        call_count = 0

        def handler(_request: httpx.Request) -> httpx.Response:
            nonlocal call_count
            call_count += 1
            return httpx.Response(
                200,
                json={
                    "events": [
                        {"event": "Test", "amount": 100, "percent_change": 0.0},
                    ],
                    "type": "general",
                },
            )

        discovery = discovery_factory(handler)

        discovery.list_top_events()
        assert call_count == 1

        discovery.list_top_events()
        assert call_count == 2  # API called again, not cached

    def test_list_top_events_with_type_parameter(
        self,
        discovery_factory: Callable[
            [Callable[[httpx.Request], httpx.Response]], DiscoveryService
        ],
    ) -> None:
        """list_top_events() should pass type parameter to API."""

        def handler(request: httpx.Request) -> httpx.Response:
            assert "type=unique" in str(request.url)
            return httpx.Response(
                200,
                json={
                    "events": [],
                    "type": "unique",
                },
            )

        discovery = discovery_factory(handler)
        discovery.list_top_events(type="unique")

    def test_list_top_events_with_limit_parameter(
        self,
        discovery_factory: Callable[
            [Callable[[httpx.Request], httpx.Response]], DiscoveryService
        ],
    ) -> None:
        """list_top_events() should pass limit parameter to API."""

        def handler(request: httpx.Request) -> httpx.Response:
            assert "limit=10" in str(request.url)
            return httpx.Response(
                200,
                json={
                    "events": [],
                    "type": "general",
                },
            )

        discovery = discovery_factory(handler)
        discovery.list_top_events(limit=10)

    def test_list_top_events_empty_result(
        self,
        discovery_factory: Callable[
            [Callable[[httpx.Request], httpx.Response]], DiscoveryService
        ],
    ) -> None:
        """list_top_events() should return empty list when no events."""

        def handler(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                json={
                    "events": [],
                    "type": "general",
                },
            )

        discovery = discovery_factory(handler)
        events = discovery.list_top_events()

        assert events == []


class TestListSubproperties:
    """Tests for DiscoveryService.list_subproperties()."""

    @staticmethod
    def _values_handler(
        values: list[str],
    ) -> Callable[[httpx.Request], httpx.Response]:
        """Return a handler that always replies with `values`."""

        def handler(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json=values)

        return handler

    def test_extracts_string_subproperties_with_types(
        self,
        discovery_factory: Callable[
            [Callable[[httpx.Request], httpx.Response]], DiscoveryService
        ],
    ) -> None:
        """Subproperties with string values are reported as type 'string'."""

        values = [
            json.dumps({"Brand": "nike", "Category": "hats"}),
            json.dumps({"Brand": "puma", "Category": "shoes"}),
            json.dumps({"Brand": "h&m", "Category": "hats"}),
        ]
        discovery = discovery_factory(self._values_handler(values))
        subs = discovery.list_subproperties("cart", event="Cart Viewed")
        names = {s.name for s in subs}
        assert names == {"Brand", "Category"}
        for s in subs:
            assert s.type == "string"

    def test_extracts_numeric_subproperties(
        self,
        discovery_factory: Callable[
            [Callable[[httpx.Request], httpx.Response]], DiscoveryService
        ],
    ) -> None:
        """Subproperties with numeric values are reported as type 'number'."""

        values = [
            json.dumps({"Price": 51, "Item ID": 35317}),
            json.dumps({"Price": 87.5, "Item ID": 35318}),
            json.dumps({"Price": 102, "Item ID": 35319}),
        ]
        discovery = discovery_factory(self._values_handler(values))
        subs = {s.name: s for s in discovery.list_subproperties("cart", event="X")}
        assert subs["Price"].type == "number"
        assert subs["Item ID"].type == "number"

    def test_extracts_boolean_subproperties(
        self,
        discovery_factory: Callable[
            [Callable[[httpx.Request], httpx.Response]], DiscoveryService
        ],
    ) -> None:
        """Boolean values are detected as 'boolean', not 'number'."""

        values = [
            json.dumps({"on_sale": True}),
            json.dumps({"on_sale": False}),
        ]
        discovery = discovery_factory(self._values_handler(values))
        subs = discovery.list_subproperties("cart", event="X")
        assert len(subs) == 1
        assert subs[0].name == "on_sale"
        assert subs[0].type == "boolean"

    def test_extracts_datetime_subproperties(
        self,
        discovery_factory: Callable[
            [Callable[[httpx.Request], httpx.Response]], DiscoveryService
        ],
    ) -> None:
        """ISO-formatted date/datetime strings are detected as 'datetime'."""

        values = [
            json.dumps({"added_at": "2025-04-23"}),
            json.dumps({"added_at": "2025-04-24"}),
            json.dumps({"added_at": "2025-04-25T10:30:00Z"}),
        ]
        discovery = discovery_factory(self._values_handler(values))
        subs = discovery.list_subproperties("cart", event="X")
        assert subs[0].name == "added_at"
        assert subs[0].type == "datetime"

    def test_mixed_types_collapse_to_string_with_warning(
        self,
        discovery_factory: Callable[
            [Callable[[httpx.Request], httpx.Response]], DiscoveryService
        ],
    ) -> None:
        """Mixed sub-value types report 'string' and emit UserWarning."""
        import warnings

        values = [
            json.dumps({"id": "abc"}),
            json.dumps({"id": 123}),
        ]
        discovery = discovery_factory(self._values_handler(values))
        with warnings.catch_warnings(record=True) as captured:
            warnings.simplefilter("always")
            subs = discovery.list_subproperties("cart", event="X")
        assert subs[0].type == "string"
        assert any("mixed" in str(w.message).lower() for w in captured)

    def test_returns_alphabetical_order(
        self,
        discovery_factory: Callable[
            [Callable[[httpx.Request], httpx.Response]], DiscoveryService
        ],
    ) -> None:
        """Returned subproperties are sorted alphabetically by name."""

        values = [json.dumps({"Z": "z", "A": "a", "M": "m"})]
        discovery = discovery_factory(self._values_handler(values))
        names = [s.name for s in discovery.list_subproperties("cart", event="X")]
        assert names == ["A", "M", "Z"]

    def test_caps_sample_values_at_five_distinct(
        self,
        discovery_factory: Callable[
            [Callable[[httpx.Request], httpx.Response]], DiscoveryService
        ],
    ) -> None:
        """sample_values holds at most 5 distinct values."""

        values = [json.dumps({"Brand": f"b{i}"}) for i in range(20)]
        discovery = discovery_factory(self._values_handler(values))
        subs = discovery.list_subproperties("cart", event="X")
        assert len(subs[0].sample_values) <= 5
        # All distinct
        assert len(set(subs[0].sample_values)) == len(subs[0].sample_values)

    def test_skips_unparseable_values(
        self,
        discovery_factory: Callable[
            [Callable[[httpx.Request], httpx.Response]], DiscoveryService
        ],
    ) -> None:
        """Non-JSON / non-dict values are silently skipped."""

        values = [
            "not json at all",
            json.dumps(["just", "a", "list"]),
            json.dumps({"Brand": "nike"}),
        ]
        discovery = discovery_factory(self._values_handler(values))
        subs = discovery.list_subproperties("cart", event="X")
        assert [s.name for s in subs] == ["Brand"]

    def test_skips_nested_object_subvalues(
        self,
        discovery_factory: Callable[
            [Callable[[httpx.Request], httpx.Response]], DiscoveryService
        ],
    ) -> None:
        """Nested dicts/lists inside item objects are skipped (scalars only)."""

        values = [
            json.dumps(
                {
                    "Brand": "nike",
                    "metadata": {"sku": "x"},  # nested dict — skip
                    "tags": ["a", "b"],  # nested list — skip
                }
            ),
        ]
        discovery = discovery_factory(self._values_handler(values))
        names = {s.name for s in discovery.list_subproperties("cart", event="X")}
        assert names == {"Brand"}

    def test_empty_input_returns_empty_list(
        self,
        discovery_factory: Callable[
            [Callable[[httpx.Request], httpx.Response]], DiscoveryService
        ],
    ) -> None:
        """No values returns empty list, no error."""
        discovery = discovery_factory(self._values_handler([]))
        assert discovery.list_subproperties("cart", event="X") == []

    def test_handles_list_of_dicts_value_shape(
        self,
        discovery_factory: Callable[
            [Callable[[httpx.Request], httpx.Response]], DiscoveryService
        ],
    ) -> None:
        """When a value is a JSON list of dicts, each dict is one row."""

        values = [
            json.dumps([{"Brand": "nike"}, {"Brand": "puma"}]),
            json.dumps([{"Brand": "h&m"}]),
        ]
        discovery = discovery_factory(self._values_handler(values))
        subs = discovery.list_subproperties("cart", event="X")
        assert subs[0].name == "Brand"
        # Should have collected from all dicts in all values
        assert len(subs[0].sample_values) >= 2

    def test_skips_null_subvalues_no_mixed_warning(
        self,
        discovery_factory: Callable[
            [Callable[[httpx.Request], httpx.Response]], DiscoveryService
        ],
    ) -> None:
        """JSON null sub-values are treated as missing, not mixed types.

        Regression: previously a column of (str, None, str) collapsed to
        type='string' with a 'mixed types' UserWarning. Nulls now skip
        inference and never appear in ``sample_values``.
        """
        import warnings

        values = [
            json.dumps({"Brand": "nike", "Coupon": None}),
            json.dumps({"Brand": "puma", "Coupon": "FALL20"}),
            json.dumps({"Brand": "h&m", "Coupon": None}),
        ]
        discovery = discovery_factory(self._values_handler(values))
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            subs = discovery.list_subproperties("cart", event="X")
        by_name = {s.name: s for s in subs}
        assert by_name["Coupon"].type == "string"
        assert None not in by_name["Coupon"].sample_values
        assert by_name["Coupon"].sample_values == ("FALL20",)

    def test_iter_dict_rows_filters_non_dicts_in_lists(
        self,
        discovery_factory: Callable[
            [Callable[[httpx.Request], httpx.Response]], DiscoveryService
        ],
    ) -> None:
        """Within a JSON list, non-dict items are silently filtered out.

        E.g. ``[{"a": 1}, "junk", {"b": 2}]`` yields rows for the two
        dicts only; the bare string is dropped.
        """
        values = [json.dumps([{"Brand": "nike"}, "junk", {"Brand": "puma"}])]
        discovery = discovery_factory(self._values_handler(values))
        subs = discovery.list_subproperties("cart", event="X")
        assert [s.name for s in subs] == ["Brand"]
        assert set(subs[0].sample_values) == {"nike", "puma"}

    def test_mixed_shape_emits_warning_and_keeps_scalar(
        self,
        discovery_factory: Callable[
            [Callable[[httpx.Request], httpx.Response]], DiscoveryService
        ],
    ) -> None:
        """A sub-key seen with both scalar and dict shapes warns and reports scalar.

        Regression: previously the dict row was silently dropped without
        a warning, producing a misleading ``type='string'`` report.
        """
        import warnings

        values = [
            json.dumps({"X": 1}),
            json.dumps({"X": {"nested": 2}}),  # dict — silently dropped previously
            json.dumps({"X": 3}),
        ]
        discovery = discovery_factory(self._values_handler(values))
        with warnings.catch_warnings(record=True) as captured:
            warnings.simplefilter("always")
            subs = discovery.list_subproperties("cart", event="X")
        by_name = {s.name: s for s in subs}
        assert by_name["X"].type == "number"  # scalar form retained
        assert set(by_name["X"].sample_values) == {1, 3}
        assert any("scalar and nested-object" in str(w.message) for w in captured), [
            str(w.message) for w in captured
        ]

    def test_all_null_subproperty_warns_and_excluded(
        self,
        discovery_factory: Callable[
            [Callable[[httpx.Request], httpx.Response]], DiscoveryService
        ],
    ) -> None:
        """A sub-key with only null values warns and is excluded from output."""
        import warnings

        values = [
            json.dumps({"Brand": "nike", "Coupon": None}),
            json.dumps({"Brand": "puma", "Coupon": None}),
        ]
        discovery = discovery_factory(self._values_handler(values))
        with warnings.catch_warnings(record=True) as captured:
            warnings.simplefilter("always")
            subs = discovery.list_subproperties("cart", event="X")
        names = [s.name for s in subs]
        assert "Coupon" not in names
        assert "Brand" in names
        assert any(
            "all sampled values were null" in str(w.message) for w in captured
        ), [str(w.message) for w in captured]

    def test_invalid_calendar_date_classified_as_string(
        self,
        discovery_factory: Callable[
            [Callable[[httpx.Request], httpx.Response]], DiscoveryService
        ],
    ) -> None:
        """ISO-shaped strings with invalid calendar values fall back to 'string'."""
        for bad in ("2025-13-99", "2025-04-23T25:99:99"):
            values = [json.dumps({"X": bad})]
            discovery = discovery_factory(self._values_handler(values))
            subs = discovery.list_subproperties("cart", event="X")
            assert subs[0].type == "string", f"{bad!r} should not be datetime"

    def test_infer_scalar_type_empty_raises(self) -> None:
        """``_infer_scalar_type([])`` raises ValueError instead of returning a phantom."""
        from mixpanel_headless._internal.services.discovery import _infer_scalar_type

        with pytest.raises(ValueError, match="non-empty"):
            _infer_scalar_type([])

    def test_infer_scalar_type_mixed_int_bool_returns_string_with_warning(
        self,
    ) -> None:
        """``_infer_scalar_type([True, 1])`` returns ('string', True) — bool/int overlap."""
        from mixpanel_headless._internal.services.discovery import _infer_scalar_type

        inferred, mixed = _infer_scalar_type([True, 1])
        assert inferred == "string"
        assert mixed is True

    def test_mixed_warning_stacklevel_points_at_user_frame(
        self,
        discovery_factory: Callable[
            [Callable[[httpx.Request], httpx.Response]], DiscoveryService
        ],
    ) -> None:
        """Warning filename equals this test's __file__ via the documented chain.

        Pins ``_USER_FRAME_STACKLEVEL`` against the documented user
        chain ``user → Workspace.subproperties →
        DiscoveryService.list_subproperties → _infer_subproperties →
        warnings.warn``. ``discovery_factory`` gives us a
        ``DiscoveryService`` directly (skipping Workspace), so we wrap
        the call in ``workspace_subproperties_simulator`` to add the
        frame that ``Workspace.subproperties`` contributes in
        production. The wrapper call below is the "user" frame.
        """
        import warnings

        # Mixed int/string values trigger _infer_scalar_type's mixed-types path.
        values = [json.dumps({"X": 1}), json.dumps({"X": "abc"})]
        discovery = discovery_factory(self._values_handler(values))

        def workspace_subproperties_simulator() -> None:
            """Adds the frame Workspace.subproperties contributes in production."""
            discovery.list_subproperties("cart", event="X")

        with warnings.catch_warnings(record=True) as captured:
            warnings.simplefilter("always")
            workspace_subproperties_simulator()  # user frame
        # At least one captured warning must point to this test file.
        assert any(w.filename == __file__ for w in captured), [
            w.filename for w in captured
        ]
