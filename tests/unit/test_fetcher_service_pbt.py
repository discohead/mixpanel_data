"""Property-based tests for FetcherService transform functions using Hypothesis.

These tests verify invariants that should hold for all possible inputs,
catching edge cases that example-based tests might miss.

Properties tested:
- transform_event: Non-mutation of input, field extraction invariants
- transform_profile: Non-mutation of input, field extraction invariants
"""

from __future__ import annotations

import copy
from datetime import datetime
from typing import Any

from hypothesis import given, settings
from hypothesis import strategies as st

from mixpanel_data._internal.transforms import (
    RESERVED_EVENT_KEYS,
    RESERVED_PROFILE_KEYS,
    transform_event,
    transform_profile,
)

# =============================================================================
# Custom Strategies
# =============================================================================

# Strategy for JSON-serializable primitive values
json_primitives = st.one_of(
    st.none(),
    st.booleans(),
    st.integers(),
    st.floats(allow_nan=False, allow_infinity=False),
    st.text(),
)

# Strategy for JSON-serializable values (recursive: primitives, lists, dicts)
# This matches what Mixpanel event properties can contain
json_values: st.SearchStrategy[Any] = st.recursive(
    json_primitives,
    lambda children: st.one_of(
        st.lists(children, max_size=5),
        st.dictionaries(st.text(), children, max_size=5),
    ),
    max_leaves=15,
)

# Strategy for event property keys (excluding reserved keys)
event_property_keys = st.text().filter(lambda k: k not in RESERVED_EVENT_KEYS)

# Strategy for event properties dict
# These are properties that might come from Mixpanel's Export API
# Reserved keys (distinct_id, time, $insert_id) are excluded since they're
# handled separately as standard fields in transform_event
event_properties = st.dictionaries(event_property_keys, json_values, max_size=10)

# Strategy for profile property keys (excluding reserved keys)
profile_property_keys = st.text().filter(lambda k: k not in RESERVED_PROFILE_KEYS)

# Strategy for profile properties dict
# Reserved keys ($last_seen) are excluded since they're handled separately
# as standard fields in transform_profile
profile_properties = st.dictionaries(profile_property_keys, json_values, max_size=10)

# Strategy for Unix timestamps (valid range for Mixpanel events)
# Mixpanel uses seconds since epoch
unix_timestamps = st.integers(min_value=0, max_value=2147483647)

# Strategy for distinct IDs (can be any string)
distinct_ids = st.text()

# Strategy for insert IDs (UUIDs as strings, or None)
insert_ids = st.one_of(
    st.none(),
    st.uuids().map(str),
    st.text(min_size=1, max_size=50),  # Custom insert IDs
)

# Strategy for event names
event_names = st.text()


# =============================================================================
# Strategies for Complete API Objects
# =============================================================================


@st.composite
def api_events(draw: st.DrawFn) -> dict[str, Any]:
    """Generate a raw event dict as returned by Mixpanel's Export API.

    The API returns events in this format:
    {
        "event": "Event Name",
        "properties": {
            "distinct_id": "user123",
            "time": 1704067200,
            "$insert_id": "uuid-string",
            ... other properties ...
        }
    }
    """
    event_name = draw(event_names)
    distinct_id = draw(distinct_ids)
    timestamp = draw(unix_timestamps)
    insert_id = draw(insert_ids)

    # Build properties with optional standard fields
    properties: dict[str, Any] = draw(event_properties)
    properties["distinct_id"] = distinct_id
    properties["time"] = timestamp
    if insert_id is not None:
        properties["$insert_id"] = insert_id

    return {
        "event": event_name,
        "properties": properties,
    }


@st.composite
def api_profiles(draw: st.DrawFn) -> dict[str, Any]:
    """Generate a raw profile dict as returned by Mixpanel's Engage API.

    The API returns profiles in this format:
    {
        "$distinct_id": "user123",
        "$properties": {
            "$last_seen": "2024-01-15T10:30:00",
            "$email": "user@example.com",
            ... other properties ...
        }
    }
    """
    distinct_id = draw(distinct_ids)
    last_seen = draw(
        st.one_of(
            st.none(),
            st.datetimes(
                min_value=datetime(2000, 1, 1),
                max_value=datetime(2030, 12, 31),
            ).map(lambda dt: dt.isoformat()),
        )
    )

    # Build properties with optional $last_seen
    properties: dict[str, Any] = draw(profile_properties)
    if last_seen is not None:
        properties["$last_seen"] = last_seen

    return {
        "$distinct_id": distinct_id,
        "$properties": properties,
    }


# =============================================================================
# transform_event Property Tests
# =============================================================================


class TestTransformEventProperties:
    """Property-based tests for transform_event function.

    The transform_event function transforms raw Mixpanel Export API events
    into the storage format expected by StorageEngine. It must:
    1. Never mutate the input dictionary
    2. Extract distinct_id, time, and $insert_id from properties
    3. Convert Unix timestamp to datetime
    4. Generate UUID if $insert_id is missing
    """

    @given(event=api_events())
    @settings(max_examples=100)
    def testtransform_event_never_mutates_input(self, event: dict[str, Any]) -> None:
        """transform_event should never mutate the input dictionary.

        This property is critical for streaming pipelines where the same
        dictionary might be reused or referenced elsewhere. Mutation would
        cause subtle, hard-to-debug issues.

        Args:
            event: A raw event dict from Mixpanel's Export API.
        """
        # Make a deep copy to compare after transformation
        original = copy.deepcopy(event)

        # Transform the event
        transform_event(event)

        # Input should be unchanged
        assert event == original, (
            f"Input was mutated.\nBefore: {original}\nAfter: {event}"
        )

    @given(event=api_events())
    @settings(max_examples=100)
    def testtransform_event_extracts_standard_fields(
        self, event: dict[str, Any]
    ) -> None:
        """transform_event output properties should not contain standard fields.

        The fields 'distinct_id', 'time', and '$insert_id' must be extracted
        to top-level output fields and removed from the output properties dict.

        Args:
            event: A raw event dict from Mixpanel's Export API.
        """
        result = transform_event(event)

        # Standard fields should NOT be in output properties
        output_props = result["properties"]
        assert "distinct_id" not in output_props, (
            "distinct_id should be extracted, not in output properties"
        )
        assert "time" not in output_props, (
            "time should be extracted, not in output properties"
        )
        assert "$insert_id" not in output_props, (
            "$insert_id should be extracted, not in output properties"
        )

    @given(event=api_events())
    def testtransform_event_has_required_output_fields(
        self, event: dict[str, Any]
    ) -> None:
        """transform_event output should have all required fields.

        The output dict must contain exactly: event_name, event_time,
        distinct_id, insert_id, and properties.

        Args:
            event: A raw event dict from Mixpanel's Export API.
        """
        result = transform_event(event)

        required_fields = {
            "event_name",
            "event_time",
            "distinct_id",
            "insert_id",
            "properties",
        }
        assert set(result.keys()) == required_fields

    @given(event=api_events())
    def testtransform_event_converts_timestamp_to_datetime(
        self, event: dict[str, Any]
    ) -> None:
        """transform_event should convert Unix timestamp to UTC datetime.

        Args:
            event: A raw event dict from Mixpanel's Export API.
        """
        result = transform_event(event)

        # event_time should be a datetime
        assert isinstance(result["event_time"], datetime)
        # Should be timezone-aware (UTC)
        assert result["event_time"].tzinfo is not None

    @given(event=api_events())
    def testtransform_event_preserves_custom_properties(
        self, event: dict[str, Any]
    ) -> None:
        """transform_event should preserve all non-standard properties.

        Any property that isn't distinct_id, time, or $insert_id should
        appear unchanged in the output properties.

        Args:
            event: A raw event dict from Mixpanel's Export API.
        """
        result = transform_event(event)

        input_props = event.get("properties", {})
        output_props = result["properties"]

        # Check that all non-standard input properties are preserved
        standard_fields = {"distinct_id", "time", "$insert_id"}
        for key, value in input_props.items():
            if key not in standard_fields:
                assert key in output_props, f"Property '{key}' was lost"
                assert output_props[key] == value, f"Property '{key}' value changed"

    @given(event=api_events())
    def testtransform_event_always_has_insert_id(self, event: dict[str, Any]) -> None:
        """transform_event should always produce an insert_id.

        If $insert_id is missing from input, a UUID should be generated.

        Args:
            event: A raw event dict from Mixpanel's Export API.
        """
        result = transform_event(event)

        assert result["insert_id"] is not None
        assert isinstance(result["insert_id"], str)
        assert len(result["insert_id"]) > 0


# =============================================================================
# transform_profile Property Tests
# =============================================================================


class TestTransformProfileProperties:
    """Property-based tests for transform_profile function.

    The transform_profile function transforms raw Mixpanel Engage API profiles
    into the storage format expected by StorageEngine. It must:
    1. Never mutate the input dictionary
    2. Extract $last_seen from properties
    3. Preserve all other properties
    """

    @given(profile=api_profiles())
    @settings(max_examples=100)
    def testtransform_profile_never_mutates_input(
        self, profile: dict[str, Any]
    ) -> None:
        """transform_profile should never mutate the input dictionary.

        This property is critical for streaming pipelines where the same
        dictionary might be reused or referenced elsewhere.

        Args:
            profile: A raw profile dict from Mixpanel's Engage API.
        """
        # Make a deep copy to compare after transformation
        original = copy.deepcopy(profile)

        # Transform the profile
        transform_profile(profile)

        # Input should be unchanged
        assert profile == original, (
            f"Input was mutated.\nBefore: {original}\nAfter: {profile}"
        )

    @given(profile=api_profiles())
    @settings(max_examples=100)
    def testtransform_profile_extracts_last_seen(self, profile: dict[str, Any]) -> None:
        """transform_profile output properties should not contain $last_seen.

        The $last_seen field must be extracted to a top-level output field
        and removed from the output properties dict.

        Args:
            profile: A raw profile dict from Mixpanel's Engage API.
        """
        result = transform_profile(profile)

        # $last_seen should NOT be in output properties
        output_props = result["properties"]
        assert "$last_seen" not in output_props, (
            "$last_seen should be extracted, not in output properties"
        )

    @given(profile=api_profiles())
    def testtransform_profile_has_required_output_fields(
        self, profile: dict[str, Any]
    ) -> None:
        """transform_profile output should have all required fields.

        The output dict must contain exactly: distinct_id, last_seen, properties.

        Args:
            profile: A raw profile dict from Mixpanel's Engage API.
        """
        result = transform_profile(profile)

        required_fields = {"distinct_id", "last_seen", "properties"}
        assert set(result.keys()) == required_fields

    @given(profile=api_profiles())
    def testtransform_profile_preserves_custom_properties(
        self, profile: dict[str, Any]
    ) -> None:
        """transform_profile should preserve all non-standard properties.

        Any property that isn't $last_seen should appear unchanged in
        the output properties.

        Args:
            profile: A raw profile dict from Mixpanel's Engage API.
        """
        result = transform_profile(profile)

        input_props = profile.get("$properties", {})
        output_props = result["properties"]

        # Check that all non-standard input properties are preserved
        for key, value in input_props.items():
            if key != "$last_seen":
                assert key in output_props, f"Property '{key}' was lost"
                assert output_props[key] == value, f"Property '{key}' value changed"


# =============================================================================
# Cross-Function Property Tests
# =============================================================================


class TestTransformConsistency:
    """Tests for consistency between transform functions."""

    @given(
        properties=event_properties,
        distinct_id=distinct_ids,
    )
    def test_transform_preserves_deterministic_fields(
        self,
        properties: dict[str, Any],
        distinct_id: str,
    ) -> None:
        """Transform functions preserve deterministic fields across calls.

        Note: insert_id is excluded from comparison since it's randomly
        generated when $insert_id is missing from input.

        Args:
            properties: Arbitrary event properties.
            distinct_id: User identifier.
        """
        # Create event and profile with same properties
        event = {
            "event": "Test",
            "properties": {
                "distinct_id": distinct_id,
                "time": 1704067200,
                **properties,
            },
        }
        profile = {
            "$distinct_id": distinct_id,
            "$properties": dict(properties),
        }

        # Transform twice
        result1_event = transform_event(copy.deepcopy(event))
        result2_event = transform_event(copy.deepcopy(event))

        result1_profile = transform_profile(copy.deepcopy(profile))
        result2_profile = transform_profile(copy.deepcopy(profile))

        # Deterministic fields should be identical across calls
        # Note: insert_id is excluded since it's randomly generated when missing
        assert result1_event["properties"] == result2_event["properties"]
        assert result1_event["event_name"] == result2_event["event_name"]
        assert result1_event["distinct_id"] == result2_event["distinct_id"]
        assert result1_event["event_time"] == result2_event["event_time"]

        assert result1_profile == result2_profile
