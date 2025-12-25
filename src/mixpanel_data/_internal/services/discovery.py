"""Discovery Service for Mixpanel schema introspection.

Provides methods to explore events, properties, and sample values
with session-scoped caching to avoid redundant API calls.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from mixpanel_data.types import (
    FunnelInfo,
    LexiconDefinition,
    LexiconMetadata,
    LexiconProperty,
    LexiconSchema,
    SavedCohort,
    TopEvent,
)

if TYPE_CHECKING:
    from mixpanel_data._internal.api_client import MixpanelAPIClient

_logger = logging.getLogger(__name__)


# =============================================================================
# Lexicon Schema Parser Functions
# =============================================================================


def _parse_lexicon_metadata(data: dict[str, Any] | None) -> LexiconMetadata | None:
    """Parse Lexicon metadata from API response.

    Extracts Mixpanel-specific metadata from the nested 'com.mixpanel' key
    in the API response.

    Args:
        data: Raw metadata dictionary from API response (may contain 'com.mixpanel').

    Returns:
        LexiconMetadata if data contains 'com.mixpanel', None otherwise.
    """
    if data is None:
        return None
    mp_data = data.get("com.mixpanel", {})
    if not mp_data:
        return None
    return LexiconMetadata(
        source=mp_data.get("$source"),
        display_name=mp_data.get("displayName"),
        tags=mp_data.get("tags", []),
        hidden=mp_data.get("hidden", False),
        dropped=mp_data.get("dropped", False),
        contacts=mp_data.get("contacts", []),
        team_contacts=mp_data.get("teamContacts", []),
    )


def _parse_lexicon_property(data: dict[str, Any]) -> LexiconProperty:
    """Parse a single Lexicon property from API response.

    Args:
        data: Raw property dictionary from API response.

    Returns:
        LexiconProperty with type, description, and optional metadata.
    """
    return LexiconProperty(
        type=data.get("type", "string"),
        description=data.get("description"),
        metadata=_parse_lexicon_metadata(data.get("metadata")),
    )


def _parse_lexicon_definition(data: dict[str, Any]) -> LexiconDefinition:
    """Parse Lexicon definition from API response.

    Args:
        data: Raw schemaJson dictionary from API response.

    Returns:
        LexiconDefinition with description, properties, and optional metadata.
    """
    properties_raw = data.get("properties", {})
    properties = {k: _parse_lexicon_property(v) for k, v in properties_raw.items()}
    return LexiconDefinition(
        description=data.get("description"),
        properties=properties,
        metadata=_parse_lexicon_metadata(data.get("metadata")),
    )


def _parse_lexicon_schema(data: dict[str, Any]) -> LexiconSchema:
    """Parse a complete Lexicon schema from API response.

    Args:
        data: Raw schema dictionary from API response.

    Returns:
        LexiconSchema with entity_type, name, and schema_json.
    """
    return LexiconSchema(
        entity_type=data["entityType"],
        name=data["name"],
        schema_json=_parse_lexicon_definition(data["schemaJson"]),
    )


class DiscoveryService:
    """Schema discovery service for Mixpanel projects.

    Provides methods to explore events, properties, and sample values
    with session-scoped caching to avoid redundant API calls.

    Caching Behavior:
        Results are cached in-memory for the lifetime of this service instance.
        Cache keys are tuples identifying each unique query:

        - ("list_events",) - All event names
        - ("list_properties", event) - Properties for a specific event
        - ("list_property_values", property, event, limit) - Sample values
        - ("list_funnels",) - All saved funnels
        - ("list_cohorts",) - All saved cohorts

        Exception: list_top_events() is NOT cached (real-time data).

        Use clear_cache() to force fresh data on next request.

    Example:
        ```python
        from mixpanel_data._internal.api_client import MixpanelAPIClient
        from mixpanel_data._internal.services.discovery import DiscoveryService

        client = MixpanelAPIClient(credentials)
        discovery = DiscoveryService(client)
        events = discovery.list_events()  # Fetches from API
        events = discovery.list_events()  # Returns cached result
        discovery.clear_cache()
        events = discovery.list_events()  # Fetches from API again
        ```
    """

    def __init__(self, api_client: MixpanelAPIClient) -> None:
        """Initialize discovery service.

        Args:
            api_client: Authenticated Mixpanel API client.
        """
        self._api_client = api_client
        # Internal cache: tuple keys map to cached results
        self._cache: dict[tuple[str | int | None, ...], list[Any]] = {}

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
        # Store a copy to prevent mutation if API client retains reference
        self._cache[cache_key] = list(result)
        return list(result)

    def list_funnels(self) -> list[FunnelInfo]:
        """List all saved funnels in the project.

        Returns:
            Alphabetically sorted list of FunnelInfo objects.
            Empty list if no funnels exist (not an error).

        Raises:
            AuthenticationError: Invalid credentials.

        Note:
            Results are cached for the lifetime of this service instance.
        """
        cache_key = ("list_funnels",)
        if cache_key in self._cache:
            return list(self._cache[cache_key])

        raw = self._api_client.list_funnels()
        funnels = sorted(
            [FunnelInfo(funnel_id=f["funnel_id"], name=f["name"]) for f in raw],
            key=lambda x: x.name,
        )
        self._cache[cache_key] = funnels
        return list(funnels)

    def list_cohorts(self) -> list[SavedCohort]:
        """List all saved cohorts in the project.

        Returns:
            Alphabetically sorted list of SavedCohort objects.
            Empty list if no cohorts exist (not an error).

        Raises:
            AuthenticationError: Invalid credentials.

        Note:
            Results are cached for the lifetime of this service instance.
        """
        cache_key = ("list_cohorts",)
        if cache_key in self._cache:
            return list(self._cache[cache_key])

        raw = self._api_client.list_cohorts()
        cohorts = sorted(
            [
                SavedCohort(
                    id=c["id"],
                    name=c["name"],
                    count=c["count"],
                    description=c.get("description", ""),
                    created=c["created"],
                    is_visible=bool(c["is_visible"]),
                )
                for c in raw
            ],
            key=lambda x: x.name,
        )
        self._cache[cache_key] = cohorts
        return list(cohorts)

    def list_top_events(
        self,
        *,
        type: str = "general",
        limit: int | None = None,
    ) -> list[TopEvent]:
        """Get today's top events with counts and trends.

        Args:
            type: Counting method - "general", "unique", or "average".
            limit: Maximum events to return (default: 100).

        Returns:
            List of TopEvent objects (NOT cached - real-time data).

        Raises:
            AuthenticationError: Invalid credentials.

        Note:
            Results are NOT cached because data changes throughout the day.
        """
        # No caching - always fetch fresh data
        raw = self._api_client.get_top_events(type=type, limit=limit)
        return [
            TopEvent(
                event=e["event"],
                count=e["amount"],  # Map amount -> count
                percent_change=e["percent_change"],
            )
            for e in raw.get("events", [])
        ]

    def clear_cache(self) -> None:
        """Clear all cached discovery results.

        After calling this method, the next discovery request will
        fetch fresh data from the Mixpanel API.
        """
        self._cache = {}

    # =========================================================================
    # Lexicon Schemas API
    # =========================================================================

    def list_schemas(
        self,
        *,
        entity_type: str | None = None,
    ) -> list[LexiconSchema]:
        """List Lexicon schemas in the project.

        Retrieves documented event and profile property schemas from the
        Mixpanel Lexicon (data dictionary).

        Args:
            entity_type: Optional filter by type ("event" or "profile").
                If None, returns all schemas.

        Returns:
            Alphabetically sorted list of LexiconSchema objects.

        Raises:
            AuthenticationError: Invalid credentials.

        Note:
            Results are cached for the lifetime of this service instance.
        """
        cache_key = ("list_schemas", entity_type)
        if cache_key in self._cache:
            return list(self._cache[cache_key])

        raw = self._api_client.get_schemas(entity_type=entity_type)
        schemas = sorted(
            [_parse_lexicon_schema(s) for s in raw],
            key=lambda x: (x.entity_type, x.name),
        )
        self._cache[cache_key] = schemas
        return list(schemas)

    def get_schema(
        self,
        entity_type: str,
        name: str,
    ) -> LexiconSchema:
        """Get a single Lexicon schema by entity type and name.

        Args:
            entity_type: Entity type ("event" or "profile").
            name: Entity name.

        Returns:
            LexiconSchema for the specified entity.

        Raises:
            AuthenticationError: Invalid credentials.
            QueryError: Schema not found.

        Note:
            Results are cached for the lifetime of this service instance.
        """
        cache_key = ("get_schema", entity_type, name)
        if cache_key in self._cache:
            cached = self._cache[cache_key]
            if cached:
                cached_schema: LexiconSchema = cached[0]
                return cached_schema

        raw = self._api_client.get_schema(entity_type, name)
        schema = _parse_lexicon_schema(raw)
        self._cache[cache_key] = [schema]
        return schema
