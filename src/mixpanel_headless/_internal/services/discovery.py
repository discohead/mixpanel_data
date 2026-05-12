"""Discovery Service for Mixpanel schema introspection.

Provides methods to explore events, properties, and sample values
with session-scoped caching to avoid redundant API calls.
"""

from __future__ import annotations

import json
import logging
import re
import warnings
from datetime import datetime
from typing import TYPE_CHECKING, Any

from mixpanel_headless._literal_types import CustomPropertyType
from mixpanel_headless.exceptions import EventNotFoundError, QueryError
from mixpanel_headless.types import (
    BookmarkInfo,
    BookmarkType,
    FunnelInfo,
    LexiconDefinition,
    LexiconMetadata,
    LexiconProperty,
    LexiconSchema,
    SavedCohort,
    SubPropertyInfo,
    TopEvent,
)

if TYPE_CHECKING:
    from mixpanel_headless._internal.api_client import MixpanelAPIClient

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


def _parse_bookmark_info(data: dict[str, Any]) -> BookmarkInfo:
    """Parse a bookmark from API response into BookmarkInfo.

    Args:
        data: Raw bookmark dictionary from API response.

    Returns:
        BookmarkInfo with all available metadata fields.
    """
    return BookmarkInfo(
        id=data["id"],
        name=data["name"],
        type=data["type"],
        project_id=data["project_id"],
        created=data["created"],
        modified=data["modified"],
        workspace_id=data.get("workspace_id"),
        dashboard_id=data.get("dashboard_id"),
        description=data.get("description"),
        creator_id=data.get("creator_id"),
        creator_name=data.get("creator_name"),
    )


# =============================================================================
# Subproperty inference (for list-of-object event properties)
# =============================================================================


# ISO-8601 date or datetime patterns. Conservative — anchored to a plausible
# Y/M/D shape; values that merely contain digits are not treated as dates.
# Used as a fast pre-filter; calendar validity is then verified via
# datetime.fromisoformat (so "2025-13-99" is rejected as not-a-datetime).
_DATE_PATTERN = re.compile(
    r"^\d{4}-\d{2}-\d{2}(?:[T ]\d{2}:\d{2}(?::\d{2})?(?:\.\d+)?(?:Z|[+\-]\d{2}:?\d{2})?)?$"
)

# Maximum distinct sample values retained per subproperty.
_MAX_SAMPLE_VALUES = 5

# stacklevel for user-facing warnings emitted from _infer_subproperties.
# Pinned empirically by tests/unit/test_discovery.py::test_mixed_warning_stacklevel_*.
# Today the chain is:
#   user → Workspace.subproperties → DiscoveryService.list_subproperties
#   → _infer_subproperties → warnings.warn
# Python's stacklevel=N points to the body of the function N-1 levels up
# from warn's containing function: sl=2 → list_subproperties body,
# sl=3 → Workspace.subproperties body, sl=4 → user-code line that
# called Workspace.subproperties. If you reorganize the call chain,
# recount and update both this constant and the stacklevel test.
_USER_FRAME_STACKLEVEL = 4


def _is_valid_iso(s: str) -> bool:
    """Return True if ``s`` parses as a valid ISO-8601 date or datetime.

    Some valid-but-unusual ISO-8601 timezone offsets (e.g. ``+0530``
    without a colon) fall back to string classification on Python 3.10
    because ``datetime.fromisoformat`` is stricter there. That's the
    cost of preferring stdlib over a third-party parser; classifying
    those edge cases as ``string`` is conservative and harmless.

    Args:
        s: A string that already matched ``_DATE_PATTERN``.

    Returns:
        True if ``s`` represents a valid calendar date/datetime.
    """
    try:
        # Python 3.10's fromisoformat doesn't accept trailing 'Z'; strip it.
        datetime.fromisoformat(s.rstrip("Z") if s.endswith("Z") else s)
    except ValueError:
        return False
    return True


def _infer_scalar_type(
    values: list[str | int | float | bool],
) -> tuple[CustomPropertyType, bool]:
    """Infer the type of a homogeneous-ish sequence of scalar sub-values.

    Boolean is checked before number because Python treats ``bool`` as a
    subclass of ``int``. ISO-8601 date strings are validated via
    ``datetime.fromisoformat`` after the regex match, so impossible
    calendars like ``2025-13-99`` are classified as ``string``.

    Args:
        values: All scalar values observed for one subproperty across
            sampled rows. Caller guarantees only non-None scalars are
            present (None values must be filtered upstream by
            :func:`_infer_subproperties`).

    Returns:
        Tuple of (inferred type, mixed_observed). When mixed types are
        observed across the values, returns ``("string", True)`` so the
        caller can emit a warning.

    Raises:
        ValueError: If ``values`` is empty (the inference is undefined
            for an empty list and ``all([])`` would silently return
            ``True``, classifying as ``boolean``).
    """
    if not values:
        raise ValueError("_infer_scalar_type requires non-empty values")
    if all(isinstance(v, bool) for v in values):
        return "boolean", False
    if all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in values):
        return "number", False
    strs = [v for v in values if isinstance(v, str)]
    if len(strs) == len(values):
        if all(_DATE_PATTERN.match(s) and _is_valid_iso(s) for s in strs):
            return "datetime", False
        return "string", False
    return "string", True


def _iter_dict_rows(raw_values: list[str]) -> list[dict[str, Any]]:
    """Parse raw property-value strings into dict rows.

    Each raw value may be a JSON-encoded dict (one row), a JSON-encoded
    list-of-dicts (multiple rows), or anything else (skipped). Parse
    failures and non-dict/non-list parses are silently dropped from
    the result; failures are logged at debug level so users
    investigating an empty result can ``logging.basicConfig(level=DEBUG)``
    to see what was discarded.

    Args:
        raw_values: Strings as returned by the Mixpanel property-values
            endpoint.

    Returns:
        Flat list of dict rows. Order preserved.
    """
    rows: list[dict[str, Any]] = []
    for raw in raw_values:
        try:
            parsed = json.loads(raw)
        except (TypeError, ValueError) as exc:
            _logger.debug("Skipping unparseable property value: %s", exc)
            continue
        if isinstance(parsed, dict):
            rows.append(parsed)
        elif isinstance(parsed, list):
            for item in parsed:
                if isinstance(item, dict):
                    rows.append(item)
    return rows


def _infer_subproperties(raw_values: list[str]) -> list[SubPropertyInfo]:
    """Build a sorted list of SubPropertyInfo from sampled raw values.

    Behavior:

    - Treats JSON ``null`` sub-values as missing data (not as a type).
      Sub-keys observed exclusively with ``null`` produce a
      ``UserWarning`` and are excluded from output. Sub-keys observed
      with both scalar and dict/list shapes across rows produce a
      ``UserWarning`` and are reported using the scalar form (since
      ``GroupBy.list_item`` and ``Filter.list_contains`` only operate
      on scalar subproperty values).
    - Sub-keys observed with mixed scalar types (e.g. some rows int,
      some string) collapse to ``"string"`` with a ``UserWarning``.

    Args:
        raw_values: Raw strings returned by the property-values
            endpoint.

    Returns:
        Alphabetically sorted list of SubPropertyInfo (excluding any
        sub-keys whose only observed values were ``null``).
    """
    rows = _iter_dict_rows(raw_values)
    if not rows:
        return []
    per_key: dict[str, list[str | int | float | bool]] = {}
    observed: set[str] = set()
    saw_scalar: set[str] = set()
    saw_dict_or_list: set[str] = set()
    saw_non_null: set[str] = set()
    for row in rows:
        for key, value in row.items():
            observed.add(key)
            if value is None:
                continue  # treat null sub-values as missing data, not a type
            saw_non_null.add(key)
            if isinstance(value, (dict, list)):
                saw_dict_or_list.add(key)
                continue  # nested objects/lists out of scope for downstream API
            saw_scalar.add(key)
            per_key.setdefault(key, []).append(value)
    mixed_shape = saw_scalar & saw_dict_or_list
    null_only = observed - saw_non_null

    for name in sorted(mixed_shape):
        warnings.warn(
            f"Subproperty {name!r} observed with both scalar and nested-object "
            f"shapes across sampled rows; reporting the scalar form",
            UserWarning,
            stacklevel=_USER_FRAME_STACKLEVEL,
        )
    for name in sorted(null_only):
        warnings.warn(
            f"Subproperty {name!r} observed but all sampled values were null; "
            f"not classifiable",
            UserWarning,
            stacklevel=_USER_FRAME_STACKLEVEL,
        )

    out: list[SubPropertyInfo] = []
    for name in sorted(per_key):
        values = per_key[name]
        if not values:
            continue
        inferred, mixed = _infer_scalar_type(values)
        if mixed:
            warnings.warn(
                f"Subproperty {name!r} has mixed value types across sampled rows; "
                f"reporting as 'string'",
                UserWarning,
                stacklevel=_USER_FRAME_STACKLEVEL,
            )
        # Distinct sample values, preserving first-seen order, capped.
        seen: set[Any] = set()
        samples: list[str | int | float | bool] = []
        for v in values:
            if v in seen:
                continue
            seen.add(v)
            samples.append(v)
            if len(samples) >= _MAX_SAMPLE_VALUES:
                break
        out.append(
            SubPropertyInfo(name=name, type=inferred, sample_values=tuple(samples))
        )
    return out


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
        from mixpanel_headless._internal.api_client import MixpanelAPIClient
        from mixpanel_headless._internal.services.discovery import DiscoveryService

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
            EventNotFoundError: Event does not exist (includes suggestions).

        Note:
            Results are cached per event for the lifetime of this service instance.
        """
        cache_key = ("list_properties", event)
        if cache_key in self._cache:
            return list(self._cache[cache_key])

        try:
            result = self._api_client.get_event_properties(event)
        except QueryError as e:
            # If event not found (400 error), provide helpful suggestions
            if e.status_code == 400:
                available_events = self.list_events()
                similar = self._find_similar_events(event, available_events)
                raise EventNotFoundError(
                    event_name=event,
                    similar_events=similar,
                ) from e
            raise

        sorted_result = sorted(result)
        self._cache[cache_key] = sorted_result
        return list(sorted_result)

    def _find_similar_events(self, query: str, events: list[str]) -> list[str]:
        """Find events with similar names for suggestions.

        Uses a progressive matching strategy:
        1. Exact case-insensitive match (highest priority)
        2. Substring matches (query appears in event name)
        3. Word overlap matches (shared words between query and event)

        Args:
            query: The event name that was not found.
            events: List of available event names.

        Returns:
            List of up to 5 similar event names, ordered by relevance.
        """
        query_lower = query.lower()

        # 1. Exact case-insensitive match (highest priority)
        exact_matches = [e for e in events if e.lower() == query_lower]
        if exact_matches:
            return exact_matches

        # 2. Substring matches (query contained in event name)
        substring_matches = [e for e in events if query_lower in e.lower()]
        if substring_matches:
            # Sort by length (shorter = more specific match)
            return sorted(substring_matches, key=lambda x: len(x))[:5]

        # 3. Word overlap matches
        # Split query into words (handle spaces, underscores, hyphens)
        import re

        query_words = set(re.split(r"[\s_\-]+", query_lower))
        word_matches: list[tuple[str, int]] = []

        for e in events:
            event_words = set(re.split(r"[\s_\-]+", e.lower()))
            overlap = len(query_words & event_words)
            if overlap > 0:
                word_matches.append((e, overlap))

        if word_matches:
            # Sort by overlap count (descending), then by name length
            word_matches.sort(key=lambda x: (-x[1], len(x[0])))
            return [e for e, _ in word_matches[:5]]

        return []

    def list_subproperties(
        self,
        property_name: str,
        *,
        event: str | None = None,
        sample_size: int = 50,
    ) -> list[SubPropertyInfo]:
        """List inferred subproperties of a list-of-object event property.

        Samples values via :meth:`list_property_values`, parses each as
        JSON, walks dict rows, and infers a scalar type per subproperty
        from the observed sub-values. Designed for properties like
        ``cart`` whose values are objects with subkeys (``Brand``,
        ``Category``, ``Price``, ``Item ID``).

        Scope: only **scalar** subproperty values (string / number /
        boolean / ISO datetime string) are reported. Subproperties whose
        sub-values are themselves dicts or lists are silently skipped —
        they cannot be used by ``GroupBy.list_item`` or
        ``Filter.list_contains`` anyway.

        Args:
            property_name: Top-level list-of-object property name (e.g.
                ``"cart"``).
            event: Optional event name to scope the sample. Strongly
                recommended; without it the API may return values from
                across all events.
            sample_size: Number of raw values to sample. Default: 50.

        Returns:
            List of :class:`SubPropertyInfo`, alphabetically sorted by
            ``name``. Empty list if no parseable dict values were found.

        Raises:
            AuthenticationError: Invalid credentials.

        Warns:
            UserWarning: Emitted when a subproperty has values of mixed
                types across rows; the reported ``type`` collapses to
                ``"string"``.
        """
        raw = self.list_property_values(property_name, event=event, limit=sample_size)
        return _infer_subproperties(raw)

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

    def list_bookmarks(
        self,
        bookmark_type: BookmarkType | None = None,
    ) -> list[BookmarkInfo]:
        """List all saved reports (bookmarks) in the project.

        Retrieves metadata for all saved Insights, Funnel, Retention, and
        Flows reports in the project.

        Args:
            bookmark_type: Optional filter by report type. Valid values are
                'insights', 'funnels', 'retention', 'flows', 'launch-analysis'.
                If None, returns all bookmark types.

        Returns:
            List of BookmarkInfo objects with report metadata.
            Empty list if no bookmarks exist.

        Raises:
            AuthenticationError: Invalid credentials.
            QueryError: Permission denied or invalid type parameter.

        Note:
            Results are NOT cached because bookmarks may change frequently.
        """
        raw = self._api_client.list_bookmarks(bookmark_type=bookmark_type)
        # API returns nested structure: {"results": {"results": [...]}}
        results_container = raw.get("results", {})
        if isinstance(results_container, dict):
            results = results_container.get("results", [])
        else:
            # Fallback for older/different API versions returning flat list
            results = results_container
        return [_parse_bookmark_info(bm) for bm in results]

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
