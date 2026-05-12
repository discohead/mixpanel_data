"""Discovery Service Interface Contract.

This file defines the expected interface for DiscoveryService.
It is a contract, not implementation—used for planning and validation.

Location: src/mixpanel_data/_internal/services/discovery.py
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from mixpanel_data._internal.api_client import MixpanelAPIClient


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
        ...

    def list_events(self) -> list[str]:
        """List all event names in the project.

        Returns:
            Alphabetically sorted list of event names.

        Raises:
            AuthenticationError: Invalid credentials.

        Note:
            Results are cached for the lifetime of this service instance.
        """
        ...

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
        ...

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
        ...

    def clear_cache(self) -> None:
        """Clear all cached discovery results.

        After calling this method, the next discovery request will
        fetch fresh data from the Mixpanel API.
        """
        ...


# =============================================================================
# Exception Contracts (re-exported from exceptions.py)
# =============================================================================

# AuthenticationError: Raised when credentials are invalid
# QueryError: Raised when event does not exist or query is invalid
# RateLimitError: Raised when Mixpanel rate limits are exceeded

# All exceptions inherit from MixpanelDataError and have:
# - code: str (machine-readable error code)
# - message: str (human-readable description)
# - details: dict (additional context)
# - to_dict() -> dict (JSON-serializable representation)
