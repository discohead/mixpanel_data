"""Transform functions for Mixpanel data.

Shared transformation functions for converting raw Mixpanel API responses
to the storage format used by DuckDB tables.
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime
from typing import Any

_logger = logging.getLogger(__name__)

# Reserved keys that transform_event extracts from properties.
# These are standard Mixpanel fields that become top-level columns in storage.
RESERVED_EVENT_KEYS = frozenset({"distinct_id", "time", "$insert_id"})


def transform_event(event: dict[str, Any]) -> dict[str, Any]:
    """Transform API event to storage format.

    Extracts standard Mixpanel fields (distinct_id, time, $insert_id) from
    the properties dict and promotes them to top-level fields. The time
    field is converted from Unix timestamp to datetime, and a UUID is
    generated if $insert_id is missing.

    Args:
        event: Raw event from Mixpanel Export API with 'event' and 'properties' keys.

    Returns:
        Transformed event dict with event_name, event_time, distinct_id,
        insert_id, and properties keys.

    Example:
        ```python
        raw = {
            "event": "Sign Up",
            "properties": {
                "distinct_id": "user123",
                "time": 1704067200,
                "$insert_id": "abc123",
                "plan": "premium",
            }
        }
        transformed = transform_event(raw)
        # {
        #     "event_name": "Sign Up",
        #     "event_time": datetime(2024, 1, 1, 0, 0, tzinfo=UTC),
        #     "distinct_id": "user123",
        #     "insert_id": "abc123",
        #     "properties": {"plan": "premium"},
        # }
        ```
    """
    properties = event.get("properties", {})

    # Extract and remove standard fields from properties (shallow copy to avoid mutation)
    remaining_props = dict(properties)
    distinct_id = remaining_props.pop("distinct_id", "")
    event_time_raw = remaining_props.pop("time", 0)
    insert_id = remaining_props.pop("$insert_id", None)

    # Convert Unix timestamp to datetime
    # Mixpanel Export API returns time as Unix timestamp in seconds (integer)
    event_time = datetime.fromtimestamp(event_time_raw, tz=UTC)

    # Generate UUID if $insert_id is missing
    if insert_id is None:
        insert_id = str(uuid.uuid4())
        _logger.debug("Generated insert_id for event missing $insert_id")

    return {
        "event_name": event.get("event", ""),
        "event_time": event_time,
        "distinct_id": distinct_id,
        "insert_id": insert_id,
        "properties": remaining_props,
    }


# Reserved keys that transform_profile extracts from properties.
# These are standard Mixpanel fields that become top-level columns in storage.
RESERVED_PROFILE_KEYS = frozenset({"$last_seen"})


def transform_profile(profile: dict[str, Any]) -> dict[str, Any]:
    """Transform API profile to storage format.

    Extracts standard Mixpanel fields ($distinct_id, $last_seen) from the
    profile and promotes them to top-level fields.

    Args:
        profile: Raw profile from Mixpanel Engage API with '$distinct_id'
            and '$properties' keys.

    Returns:
        Transformed profile dict with distinct_id, last_seen, and properties keys.

    Example:
        ```python
        raw = {
            "$distinct_id": "user123",
            "$properties": {
                "$last_seen": "2024-01-15T10:30:00",
                "plan": "premium",
                "email": "alice@example.com",
            }
        }
        transformed = transform_profile(raw)
        # {
        #     "distinct_id": "user123",
        #     "last_seen": "2024-01-15T10:30:00",
        #     "properties": {"plan": "premium", "email": "alice@example.com"},
        # }
        ```
    """
    distinct_id = profile.get("$distinct_id", "")
    properties = profile.get("$properties", {})

    # Extract and remove $last_seen from properties (shallow copy to avoid mutation)
    remaining_props = dict(properties)
    last_seen = remaining_props.pop("$last_seen", None)

    return {
        "distinct_id": distinct_id,
        "last_seen": last_seen,
        "properties": remaining_props,
    }
