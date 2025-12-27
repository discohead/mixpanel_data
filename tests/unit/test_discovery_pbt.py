"""Property-based tests for DiscoveryService parser functions using Hypothesis.

These tests verify invariants that should hold for all possible inputs,
catching edge cases that example-based tests might miss.

Properties tested:
- _parse_lexicon_metadata: Null handling, field extraction invariants
- _parse_lexicon_property: Type default invariant, metadata propagation
- _parse_lexicon_schema: Field preservation invariants
- _parse_bookmark_info: Required field preservation invariants
"""

from __future__ import annotations

from typing import Any, get_args

from hypothesis import given, settings
from hypothesis import strategies as st

from mixpanel_data._internal.services.discovery import (
    _parse_bookmark_info,
    _parse_lexicon_metadata,
    _parse_lexicon_property,
    _parse_lexicon_schema,
)
from mixpanel_data.types import BookmarkType

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
json_values: st.SearchStrategy[Any] = st.recursive(
    json_primitives,
    lambda children: st.one_of(
        st.lists(children, max_size=5),
        st.dictionaries(st.text(), children, max_size=5),
    ),
    max_leaves=15,
)

# Strategy for arbitrary dictionaries (what API might return)
arbitrary_dicts = st.dictionaries(st.text(), json_values, max_size=10)

# Strategy for valid bookmark types
bookmark_types = st.sampled_from(get_args(BookmarkType))

# Strategy for timestamps in ISO format
iso_timestamps = st.datetimes().map(lambda dt: dt.isoformat())


# =============================================================================
# Strategies for API Response Objects
# =============================================================================


@st.composite
def com_mixpanel_data(draw: st.DrawFn) -> dict[str, Any]:
    """Generate com.mixpanel metadata as returned by Mixpanel API.

    The API returns metadata in this format:
    {
        "$source": "api",
        "displayName": "Event Name",
        "tags": ["tag1", "tag2"],
        "hidden": false,
        "dropped": false,
        "contacts": ["email@example.com"],
        "teamContacts": ["team"]
    }
    """
    result: dict[str, Any] = {}

    # All fields are optional
    if draw(st.booleans()):
        result["$source"] = draw(st.text())
    if draw(st.booleans()):
        result["displayName"] = draw(st.text())
    if draw(st.booleans()):
        result["tags"] = draw(st.lists(st.text(), max_size=5))
    if draw(st.booleans()):
        result["hidden"] = draw(st.booleans())
    if draw(st.booleans()):
        result["dropped"] = draw(st.booleans())
    if draw(st.booleans()):
        result["contacts"] = draw(st.lists(st.text(), max_size=5))
    if draw(st.booleans()):
        result["teamContacts"] = draw(st.lists(st.text(), max_size=5))

    return result


@st.composite
def lexicon_metadata_input(draw: st.DrawFn) -> dict[str, Any] | None:
    """Generate input for _parse_lexicon_metadata.

    Can be None, empty dict, dict without com.mixpanel, or dict with com.mixpanel.
    """
    choice = draw(st.integers(min_value=0, max_value=3))

    if choice == 0:
        return None
    elif choice == 1:
        return {}
    elif choice == 2:
        # Dict without com.mixpanel key
        return draw(
            st.dictionaries(
                st.text().filter(lambda s: s != "com.mixpanel"),
                json_values,
                max_size=5,
            )
        )
    else:
        # Dict with com.mixpanel key
        mp_data = draw(com_mixpanel_data())
        other_data = draw(
            st.dictionaries(
                st.text().filter(lambda s: s != "com.mixpanel"),
                json_values,
                max_size=3,
            )
        )
        return {"com.mixpanel": mp_data, **other_data}


@st.composite
def valid_lexicon_metadata_input(draw: st.DrawFn) -> dict[str, Any]:
    """Generate input that will produce a non-None LexiconMetadata.

    Must have 'com.mixpanel' key with non-empty content.
    """
    mp_data = draw(com_mixpanel_data())
    # Ensure at least one field is present
    if not mp_data:
        mp_data["displayName"] = draw(st.text())

    other_data = draw(
        st.dictionaries(
            st.text().filter(lambda s: s != "com.mixpanel"),
            json_values,
            max_size=3,
        )
    )
    return {"com.mixpanel": mp_data, **other_data}


@st.composite
def lexicon_property_input(draw: st.DrawFn) -> dict[str, Any]:
    """Generate input for _parse_lexicon_property.

    The API returns property definitions in this format:
    {
        "type": "string",
        "description": "Property description",
        "metadata": {"com.mixpanel": {...}}
    }
    """
    result: dict[str, Any] = {}

    # type is optional (defaults to "string")
    if draw(st.booleans()):
        result["type"] = draw(
            st.sampled_from(
                ["string", "number", "boolean", "array", "object", "integer", "null"]
            )
        )

    # description is optional
    if draw(st.booleans()):
        result["description"] = draw(st.text())

    # metadata is optional
    if draw(st.booleans()):
        result["metadata"] = draw(valid_lexicon_metadata_input())

    # Extra fields that might be present
    extra = draw(
        st.dictionaries(
            st.text().filter(lambda s: s not in ("type", "description", "metadata")),
            json_values,
            max_size=3,
        )
    )
    result.update(extra)

    return result


@st.composite
def lexicon_schema_input(draw: st.DrawFn) -> dict[str, Any]:
    """Generate input for _parse_lexicon_schema.

    The API returns schemas in this format:
    {
        "entityType": "event",
        "name": "Event Name",
        "schemaJson": {
            "description": "...",
            "properties": {...},
            "metadata": {...}
        }
    }
    """
    entity_type = draw(st.text(min_size=1))
    name = draw(st.text())

    # schemaJson structure
    schema_json: dict[str, Any] = {}
    if draw(st.booleans()):
        schema_json["description"] = draw(st.text())

    # properties dict
    num_props = draw(st.integers(min_value=0, max_value=5))
    properties = {
        draw(st.text(min_size=1)): draw(lexicon_property_input())
        for _ in range(num_props)
    }
    schema_json["properties"] = properties

    if draw(st.booleans()):
        schema_json["metadata"] = draw(valid_lexicon_metadata_input())

    return {
        "entityType": entity_type,
        "name": name,
        "schemaJson": schema_json,
    }


@st.composite
def bookmark_info_input(draw: st.DrawFn) -> dict[str, Any]:
    """Generate input for _parse_bookmark_info.

    The API returns bookmarks in this format:
    {
        "id": 12345,
        "name": "Report Name",
        "type": "insights",
        "project_id": 67890,
        "created": "2024-01-15T10:30:00",
        "modified": "2024-01-15T10:30:00",
        "workspace_id": 111,
        "dashboard_id": 222,
        "description": "...",
        "creator_id": 333,
        "creator_name": "User Name"
    }
    """
    # Required fields
    result: dict[str, Any] = {
        "id": draw(st.integers()),
        "name": draw(st.text()),
        "type": draw(bookmark_types),
        "project_id": draw(st.integers()),
        "created": draw(iso_timestamps),
        "modified": draw(iso_timestamps),
    }

    # Optional fields
    if draw(st.booleans()):
        result["workspace_id"] = draw(st.integers())
    if draw(st.booleans()):
        result["dashboard_id"] = draw(st.integers())
    if draw(st.booleans()):
        result["description"] = draw(st.text())
    if draw(st.booleans()):
        result["creator_id"] = draw(st.integers())
    if draw(st.booleans()):
        result["creator_name"] = draw(st.text())

    return result


# =============================================================================
# _parse_lexicon_metadata Property Tests
# =============================================================================


class TestParseLexiconMetadataProperties:
    """Property-based tests for _parse_lexicon_metadata function.

    The _parse_lexicon_metadata function extracts Mixpanel-specific metadata
    from the nested 'com.mixpanel' key in API responses. It must:
    1. Return None for None, empty dict, or dicts without 'com.mixpanel'
    2. Return LexiconMetadata when 'com.mixpanel' has content
    3. Apply correct defaults for missing fields
    """

    @given(data=lexicon_metadata_input())
    @settings(max_examples=100)
    def test_null_handling_invariant(self, data: dict[str, Any] | None) -> None:
        """_parse_lexicon_metadata returns None if and only if input lacks valid com.mixpanel.

        This invariant ensures the parser correctly distinguishes between
        "no metadata" and "has metadata" states.

        Args:
            data: Input that may or may not contain valid com.mixpanel data.
        """
        result = _parse_lexicon_metadata(data)

        # Determine if input should produce None
        should_be_none = (
            data is None
            or data == {}
            or "com.mixpanel" not in data
            or not data.get("com.mixpanel")  # empty dict
        )

        if should_be_none:
            assert result is None, f"Expected None for input {data!r}, got {result}"
        else:
            assert result is not None, (
                f"Expected LexiconMetadata for input {data!r}, got None"
            )

    @given(data=valid_lexicon_metadata_input())
    @settings(max_examples=100)
    def test_field_defaults_applied(self, data: dict[str, Any]) -> None:
        """_parse_lexicon_metadata applies correct defaults for missing fields.

        When parsing valid input, missing fields should receive defaults:
        - tags: []
        - hidden: False
        - dropped: False
        - contacts: []
        - team_contacts: []

        Args:
            data: Valid input with com.mixpanel key.
        """
        result = _parse_lexicon_metadata(data)
        assert result is not None

        mp_data = data["com.mixpanel"]

        # Verify defaults are applied for missing fields
        assert result.tags == mp_data.get("tags", [])
        assert result.hidden == mp_data.get("hidden", False)
        assert result.dropped == mp_data.get("dropped", False)
        assert result.contacts == mp_data.get("contacts", [])
        assert result.team_contacts == mp_data.get("teamContacts", [])

    @given(data=valid_lexicon_metadata_input())
    def test_field_extraction_preserves_values(self, data: dict[str, Any]) -> None:
        """_parse_lexicon_metadata preserves field values when present.

        Args:
            data: Valid input with com.mixpanel key.
        """
        result = _parse_lexicon_metadata(data)
        assert result is not None

        mp_data = data["com.mixpanel"]

        # Values should match input when present
        if "$source" in mp_data:
            assert result.source == mp_data["$source"]
        if "displayName" in mp_data:
            assert result.display_name == mp_data["displayName"]
        if "tags" in mp_data:
            assert result.tags == mp_data["tags"]
        if "hidden" in mp_data:
            assert result.hidden == mp_data["hidden"]
        if "dropped" in mp_data:
            assert result.dropped == mp_data["dropped"]


# =============================================================================
# _parse_lexicon_property Property Tests
# =============================================================================


class TestParseLexiconPropertyProperties:
    """Property-based tests for _parse_lexicon_property function.

    The _parse_lexicon_property function parses property definitions from
    Lexicon API responses. It must:
    1. Always return a LexiconProperty (never None, never raises)
    2. Default type to "string" when not specified
    3. Propagate metadata when present
    """

    @given(data=lexicon_property_input())
    @settings(max_examples=100)
    def test_always_returns_lexicon_property(self, data: dict[str, Any]) -> None:
        """_parse_lexicon_property always returns a valid LexiconProperty.

        This ensures robustness when parsing arbitrary API responses.

        Args:
            data: Arbitrary property definition dict.
        """
        result = _parse_lexicon_property(data)
        assert result is not None
        assert hasattr(result, "type")
        assert hasattr(result, "description")
        assert hasattr(result, "metadata")

    @given(data=lexicon_property_input())
    @settings(max_examples=100)
    def test_type_default_invariant(self, data: dict[str, Any]) -> None:
        """_parse_lexicon_property defaults type to "string" when not specified.

        This invariant is critical because all properties must have a type
        for schema validation to work correctly.

        Args:
            data: Property definition that may or may not have type.
        """
        result = _parse_lexicon_property(data)

        if "type" in data:
            assert result.type == data["type"], (
                f"Type should be preserved: expected {data['type']!r}, "
                f"got {result.type!r}"
            )
        else:
            assert result.type == "string", (
                f"Type should default to 'string', got {result.type!r}"
            )

    @given(data=lexicon_property_input())
    def test_description_preserved(self, data: dict[str, Any]) -> None:
        """_parse_lexicon_property preserves description when present.

        Args:
            data: Property definition with optional description.
        """
        result = _parse_lexicon_property(data)

        if "description" in data:
            assert result.description == data["description"]
        else:
            assert result.description is None


# =============================================================================
# _parse_lexicon_schema Property Tests
# =============================================================================


class TestParseLexiconSchemaProperties:
    """Property-based tests for _parse_lexicon_schema function.

    The _parse_lexicon_schema function parses complete schema definitions.
    It must:
    1. Preserve entity_type exactly (used for lookups and sorting)
    2. Preserve name exactly (used for lookups and sorting)
    3. Parse nested schemaJson correctly
    """

    @given(data=lexicon_schema_input())
    @settings(max_examples=100)
    def test_entity_type_preserved_exactly(self, data: dict[str, Any]) -> None:
        """_parse_lexicon_schema preserves entity_type without modification.

        The entity_type is used for sorting and lookups, so any transformation
        (trimming, case change, encoding) would break functionality.

        Args:
            data: Schema definition with entityType.
        """
        result = _parse_lexicon_schema(data)

        assert result.entity_type == data["entityType"], (
            f"entity_type must be preserved exactly: "
            f"expected {data['entityType']!r}, got {result.entity_type!r}"
        )

    @given(data=lexicon_schema_input())
    @settings(max_examples=100)
    def test_name_preserved_exactly(self, data: dict[str, Any]) -> None:
        """_parse_lexicon_schema preserves name without modification.

        The name is used for sorting and lookups, so any transformation
        would break functionality.

        Args:
            data: Schema definition with name.
        """
        result = _parse_lexicon_schema(data)

        assert result.name == data["name"], (
            f"name must be preserved exactly: "
            f"expected {data['name']!r}, got {result.name!r}"
        )

    @given(data=lexicon_schema_input())
    def test_properties_count_preserved(self, data: dict[str, Any]) -> None:
        """_parse_lexicon_schema preserves the number of properties.

        Args:
            data: Schema definition with properties.
        """
        result = _parse_lexicon_schema(data)

        expected_count = len(data["schemaJson"].get("properties", {}))
        actual_count = len(result.schema_json.properties)

        assert actual_count == expected_count, (
            f"Property count should be preserved: "
            f"expected {expected_count}, got {actual_count}"
        )


# =============================================================================
# _parse_bookmark_info Property Tests
# =============================================================================


class TestParseBookmarkInfoProperties:
    """Property-based tests for _parse_bookmark_info function.

    The _parse_bookmark_info function parses bookmark metadata from the
    Bookmarks API. It must:
    1. Preserve required fields exactly (id, name, type, project_id, created, modified)
    2. Handle optional fields correctly (None when missing)
    """

    @given(data=bookmark_info_input())
    @settings(max_examples=100)
    def test_required_fields_preserved_exactly(self, data: dict[str, Any]) -> None:
        """_parse_bookmark_info preserves required fields without modification.

        These fields are used for identification and display, so any
        transformation would cause incorrect behavior.

        Args:
            data: Bookmark data with all required fields.
        """
        result = _parse_bookmark_info(data)

        assert result.id == data["id"], (
            f"id must be preserved: expected {data['id']}, got {result.id}"
        )
        assert result.name == data["name"], (
            f"name must be preserved: expected {data['name']!r}, got {result.name!r}"
        )
        assert result.type == data["type"], (
            f"type must be preserved: expected {data['type']!r}, got {result.type!r}"
        )
        assert result.project_id == data["project_id"], (
            f"project_id must be preserved: "
            f"expected {data['project_id']}, got {result.project_id}"
        )
        assert result.created == data["created"], (
            f"created must be preserved: "
            f"expected {data['created']!r}, got {result.created!r}"
        )
        assert result.modified == data["modified"], (
            f"modified must be preserved: "
            f"expected {data['modified']!r}, got {result.modified!r}"
        )

    @given(data=bookmark_info_input())
    @settings(max_examples=100)
    def test_optional_fields_handled_correctly(self, data: dict[str, Any]) -> None:
        """_parse_bookmark_info returns None for missing optional fields.

        Optional fields should be None when not present in input,
        and preserved when present.

        Args:
            data: Bookmark data with optional fields.
        """
        result = _parse_bookmark_info(data)

        # workspace_id
        if "workspace_id" in data:
            assert result.workspace_id == data["workspace_id"]
        else:
            assert result.workspace_id is None

        # dashboard_id
        if "dashboard_id" in data:
            assert result.dashboard_id == data["dashboard_id"]
        else:
            assert result.dashboard_id is None

        # description
        if "description" in data:
            assert result.description == data["description"]
        else:
            assert result.description is None

        # creator_id
        if "creator_id" in data:
            assert result.creator_id == data["creator_id"]
        else:
            assert result.creator_id is None

        # creator_name
        if "creator_name" in data:
            assert result.creator_name == data["creator_name"]
        else:
            assert result.creator_name is None
