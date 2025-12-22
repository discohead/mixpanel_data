"""Discovery Service for Mixpanel schema introspection.

Provides methods to explore events, properties, and sample values
with session-scoped caching to avoid redundant API calls.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from mixpanel_data._internal.api_client import MixpanelAPIClient

_logger = logging.getLogger(__name__)


class DiscoveryService:
    """Schema discovery service for Mixpanel projects.

    Provides methods to explore events, properties, and sample values
    with session-scoped caching to avoid redundant API calls.

    Example:
        >>> from mixpanel_data._internal.api_client import MixpanelAPIClient
        >>> from mixpanel_data._internal.services.discovery import DiscoveryService
        >>>
        >>> client = MixpanelAPIClient(credentials)
        >>> discovery = DiscoveryService(client)
        >>> events = discovery.list_events()
        >>> properties = discovery.list_properties("Sign Up")
    """

    def __init__(self, api_client: MixpanelAPIClient) -> None:
        """Initialize discovery service.

        Args:
            api_client: Authenticated Mixpanel API client.
        """
        self._api_client = api_client
        # Cache key can contain str, None, or int values
        self._cache: dict[tuple[str | int | None, ...], list[str]] = {}

    def list_events(self) -> list[str]:
        """List all event names in the project.

        Returns:
            Alphabetically sorted list of event names.

        Raises:
            AuthenticationError: Invalid credentials.

        Note:
            Results are cached for the lifetime of this service instance.
        """
        cache_key = ("list_events",)
        if cache_key in self._cache:
            return list(self._cache[cache_key])

        result = self._api_client.get_events()
        sorted_result = sorted(result)
        self._cache[cache_key] = sorted_result
        return list(sorted_result)

    def list_properties(self, event: str) -> list[str]:
        """List all properties for a specific event.

        Args:
            event: Event name to get properties for.

        Returns:
            Alphabetically sorted list of property names.

        Raises:
            AuthenticationError: Invalid credentials.
            QueryError: Event does not exist.

        Note:
            Results are cached per event for the lifetime of this service instance.
        """
        cache_key = ("list_properties", event)
        if cache_key in self._cache:
            return list(self._cache[cache_key])

        result = self._api_client.get_event_properties(event)
        sorted_result = sorted(result)
        self._cache[cache_key] = sorted_result
        return list(sorted_result)

    def list_property_values(
        self,
        property_name: str,
        *,
        event: str | None = None,
        limit: int = 100,
    ) -> list[str]:
        """List sample values for a property.

        Args:
            property_name: Property name to get values for.
            event: Optional event name to scope the query.
            limit: Maximum number of values to return (default: 100).

        Returns:
            List of sample values as strings.

        Raises:
            AuthenticationError: Invalid credentials.

        Note:
            Results are cached per (property, event, limit) combination.
            Values are returned as strings regardless of original type.
        """
        # Use actual values in cache key (None and int are hashable)
        cache_key = ("list_property_values", property_name, event, limit)
        if cache_key in self._cache:
            return list(self._cache[cache_key])

        result = self._api_client.get_property_values(
            property_name, event=event, limit=limit
        )
        # Note: values are NOT sorted per research.md
        self._cache[cache_key] = result
        return list(result)

    def clear_cache(self) -> None:
        """Clear all cached discovery results.

        After calling this method, the next discovery request will
        fetch fresh data from the Mixpanel API.
        """
        self._cache = {}
