# ruff: noqa: ARG001
"""Property-based tests for Phase 027 Data Governance types.

These tests verify invariants that should hold for all possible inputs
for the data governance Pydantic models introduced in Phase 027.

Properties tested:
- EventDefinition serialization round-trip via model_dump / model_validate
- PropertyDefinition serialization round-trip
- LexiconTag serialization round-trip and frozen immutability
- DropFilter serialization round-trip
- DropFilterLimitsResponse field preservation
- ComposedPropertyValue serialization round-trip
- CustomProperty serialization round-trip
- LookupTable serialization round-trip
- LookupTableUploadUrl serialization round-trip
- UpdateEventDefinitionParams exclude_none correctness
- UpdatePropertyDefinitionParams exclude_none correctness
- CreateTagParams / UpdateTagParams round-trip
- CreateDropFilterParams / UpdateDropFilterParams round-trip

Usage:
    pytest tests/unit/test_types_data_governance_pbt.py
    HYPOTHESIS_PROFILE=dev pytest tests/unit/test_types_data_governance_pbt.py
    HYPOTHESIS_PROFILE=ci pytest tests/unit/test_types_data_governance_pbt.py
"""

from __future__ import annotations

import json

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from mixpanel_headless.types import (
    ComposedPropertyValue,
    CreateCustomEventParams,
    CreateDropFilterParams,
    CreateTagParams,
    CustomEvent,
    CustomEventAlternative,
    CustomProperty,
    CustomPropertyResourceType,
    DropFilter,
    DropFilterLimitsResponse,
    EventDefinition,
    LexiconTag,
    LookupTable,
    LookupTableUploadUrl,
    PropertyDefinition,
    PropertyResourceType,
    UpdateDropFilterParams,
    UpdateEventDefinitionParams,
    UpdatePropertyDefinitionParams,
    UpdateTagParams,
)

# =============================================================================
# Custom Strategies
# =============================================================================

# Strategy for non-empty printable strings (names, keys, etc.)
_non_empty_text = st.text(
    alphabet=st.characters(categories=("L", "N", "P", "S")),
    min_size=1,
    max_size=50,
).filter(lambda s: s.strip())

# Strategy for optional non-empty strings
_optional_text = st.none() | _non_empty_text

# Strategy for positive integers (IDs)
_positive_ints = st.integers(min_value=1, max_value=10000)

# Strategy for optional positive ints
_optional_positive_ints = st.none() | _positive_ints

# Strategy for ISO 8601 timestamps
_timestamps = st.datetimes().map(lambda dt: dt.isoformat() + "Z")

# Strategy for optional timestamps
_optional_timestamps = st.none() | _timestamps

# Strategy for optional booleans
_optional_bools = st.none() | st.booleans()

# Strategy for tag lists
_tag_lists = st.lists(_non_empty_text, min_size=0, max_size=5)

# Strategy for optional tag lists
_optional_tag_lists = st.none() | _tag_lists

# Strategy for platform lists
_platform_lists = st.lists(
    st.sampled_from(["web", "ios", "android", "react_native", "flutter"]),
    min_size=0,
    max_size=3,
)

# Strategy for PropertyResourceType enum members
_property_resource_types = st.sampled_from(list(PropertyResourceType))

# Strategy for CustomPropertyResourceType enum members
_custom_property_resource_types = st.sampled_from(list(CustomPropertyResourceType))

# Strategy for simple filter conditions (list of dicts)
_simple_filters = st.lists(
    st.fixed_dictionaries(
        {"property": _non_empty_text, "value": _non_empty_text},
    ),
    min_size=0,
    max_size=3,
)

# Strategy for URL-like strings
_url_strings = st.text(min_size=10, max_size=100).map(lambda s: f"https://{s}")


# =============================================================================
# EventDefinition Property Tests
# =============================================================================


class TestEventDefinitionProperties:
    """Property-based tests for EventDefinition Pydantic model."""

    @given(
        id=_positive_ints,
        name=_non_empty_text,
        display_name=_optional_text,
        description=_optional_text,
        hidden=_optional_bools,
        dropped=_optional_bools,
        merged=_optional_bools,
        verified=_optional_bools,
        tags=_optional_tag_lists,
    )
    @settings(max_examples=50)
    def test_serialization_round_trip(
        self,
        id: int,
        name: str,
        display_name: str | None,
        description: str | None,
        hidden: bool | None,
        dropped: bool | None,
        merged: bool | None,
        verified: bool | None,
        tags: list[str] | None,
    ) -> None:
        """EventDefinition survives model_dump / model_validate round-trip.

        Args:
            id: Event definition ID.
            name: Event name.
            display_name: Optional display name.
            description: Optional description.
            hidden: Optional hidden flag.
            dropped: Optional dropped flag.
            merged: Optional merged flag.
            verified: Optional verified flag.
            tags: Optional tag list.
        """
        event_def = EventDefinition(
            id=id,
            name=name,
            display_name=display_name,
            description=description,
            hidden=hidden,
            dropped=dropped,
            merged=merged,
            verified=verified,
            tags=tags,
        )
        data = event_def.model_dump()
        restored = EventDefinition.model_validate(data)
        assert restored == event_def

    @given(id=_positive_ints, name=_non_empty_text)
    @settings(max_examples=50)
    def test_frozen_immutability(self, id: int, name: str) -> None:
        """EventDefinition instances are immutable (frozen=True).

        Args:
            id: Event definition ID.
            name: Event name.
        """
        event_def = EventDefinition(id=id, name=name)
        with pytest.raises(Exception):  # noqa: B017
            event_def.name = "mutated"  # type: ignore[misc]

    @given(id=_positive_ints, name=_non_empty_text)
    @settings(max_examples=50)
    def test_required_fields_present(self, id: int, name: str) -> None:
        """EventDefinition requires id and name fields.

        Args:
            id: Event definition ID.
            name: Event name.
        """
        event_def = EventDefinition(id=id, name=name)
        data = event_def.model_dump()
        assert data["id"] == id
        assert data["name"] == name


# =============================================================================
# PropertyDefinition Property Tests
# =============================================================================


class TestPropertyDefinitionProperties:
    """Property-based tests for PropertyDefinition Pydantic model."""

    @given(
        id=_positive_ints,
        name=_non_empty_text,
        description=_optional_text,
        hidden=_optional_bools,
        dropped=_optional_bools,
        merged=_optional_bools,
        sensitive=_optional_bools,
        data_group_id=_optional_text,
    )
    @settings(max_examples=50)
    def test_serialization_round_trip(
        self,
        id: int,
        name: str,
        description: str | None,
        hidden: bool | None,
        dropped: bool | None,
        merged: bool | None,
        sensitive: bool | None,
        data_group_id: str | None,
    ) -> None:
        """PropertyDefinition survives model_dump / model_validate round-trip.

        Args:
            id: Property definition ID.
            name: Property name.
            description: Optional description.
            hidden: Optional hidden flag.
            dropped: Optional dropped flag.
            merged: Optional merged flag.
            sensitive: Optional PII flag.
            data_group_id: Optional data group ID.
        """
        prop_def = PropertyDefinition(
            id=id,
            name=name,
            description=description,
            hidden=hidden,
            dropped=dropped,
            merged=merged,
            sensitive=sensitive,
            data_group_id=data_group_id,
        )
        data = prop_def.model_dump()
        restored = PropertyDefinition.model_validate(data)
        assert restored == prop_def

    @given(id=_positive_ints, name=_non_empty_text)
    @settings(max_examples=50)
    def test_frozen_immutability(self, id: int, name: str) -> None:
        """PropertyDefinition instances are immutable (frozen=True).

        Args:
            id: Property definition ID.
            name: Property name.
        """
        prop_def = PropertyDefinition(id=id, name=name)
        with pytest.raises(Exception):  # noqa: B017
            prop_def.name = "mutated"  # type: ignore[misc]


# =============================================================================
# PropertyResourceType Enum Property Tests
# =============================================================================


class TestPropertyResourceTypeProperties:
    """Property-based tests for PropertyResourceType enum."""

    @given(resource_type=_property_resource_types)
    @settings(max_examples=50)
    def test_enum_round_trip(self, resource_type: PropertyResourceType) -> None:
        """Constructing from .value returns the same member.

        Args:
            resource_type: A PropertyResourceType enum member.
        """
        assert PropertyResourceType(resource_type.value) is resource_type

    @given(resource_type=_property_resource_types)
    @settings(max_examples=50)
    def test_enum_is_str_subclass(self, resource_type: PropertyResourceType) -> None:
        """All enum members are valid strings.

        Args:
            resource_type: A PropertyResourceType enum member.
        """
        assert isinstance(resource_type, str)
        assert isinstance(resource_type.value, str)
        assert len(resource_type.value) > 0


# =============================================================================
# CustomPropertyResourceType Enum Property Tests
# =============================================================================


class TestCustomPropertyResourceTypeProperties:
    """Property-based tests for CustomPropertyResourceType enum."""

    @given(resource_type=_custom_property_resource_types)
    @settings(max_examples=50)
    def test_enum_round_trip(self, resource_type: CustomPropertyResourceType) -> None:
        """Constructing from .value returns the same member.

        Args:
            resource_type: A CustomPropertyResourceType enum member.
        """
        assert CustomPropertyResourceType(resource_type.value) is resource_type

    @given(resource_type=_custom_property_resource_types)
    @settings(max_examples=50)
    def test_enum_is_str_subclass(
        self, resource_type: CustomPropertyResourceType
    ) -> None:
        """All enum members are valid strings.

        Args:
            resource_type: A CustomPropertyResourceType enum member.
        """
        assert isinstance(resource_type, str)
        assert isinstance(resource_type.value, str)
        assert len(resource_type.value) > 0


# =============================================================================
# LexiconTag Property Tests
# =============================================================================


class TestLexiconTagProperties:
    """Property-based tests for LexiconTag Pydantic model."""

    @given(id=_positive_ints, name=_non_empty_text)
    @settings(max_examples=50)
    def test_serialization_round_trip(self, id: int, name: str) -> None:
        """LexiconTag survives model_dump / model_validate round-trip.

        Args:
            id: Tag ID.
            name: Tag name.
        """
        tag = LexiconTag(id=id, name=name)
        data = tag.model_dump()
        restored = LexiconTag.model_validate(data)
        assert restored == tag

    @given(id=_positive_ints, name=_non_empty_text)
    @settings(max_examples=50)
    def test_frozen_immutability(self, id: int, name: str) -> None:
        """LexiconTag instances are immutable (frozen=True).

        Args:
            id: Tag ID.
            name: Tag name.
        """
        tag = LexiconTag(id=id, name=name)
        with pytest.raises(Exception):  # noqa: B017
            tag.name = "mutated"  # type: ignore[misc]

    @given(id=_positive_ints, name=_non_empty_text)
    @settings(max_examples=50)
    def test_fields_match(self, id: int, name: str) -> None:
        """LexiconTag fields match construction values.

        Args:
            id: Tag ID.
            name: Tag name.
        """
        tag = LexiconTag(id=id, name=name)
        assert tag.id == id
        assert tag.name == name


# =============================================================================
# DropFilter Property Tests
# =============================================================================


class TestDropFilterProperties:
    """Property-based tests for DropFilter Pydantic model."""

    @given(
        id=_positive_ints,
        event_name=_non_empty_text,
        filters=_simple_filters,
        active=_optional_bools,
        display_name=_optional_text,
        created=_optional_timestamps,
    )
    @settings(max_examples=50)
    def test_serialization_round_trip(
        self,
        id: int,
        event_name: str,
        filters: list[dict[str, str]],
        active: bool | None,
        display_name: str | None,
        created: str | None,
    ) -> None:
        """DropFilter survives model_dump / model_validate round-trip.

        Args:
            id: Drop filter ID.
            event_name: Event name to filter.
            filters: Filter condition JSON.
            active: Optional active flag.
            display_name: Optional display name.
            created: Optional creation timestamp.
        """
        drop_filter = DropFilter(
            id=id,
            event_name=event_name,
            filters=filters,
            active=active,
            display_name=display_name,
            created=created,
        )
        data = drop_filter.model_dump()
        restored = DropFilter.model_validate(data)
        assert restored == drop_filter

    @given(id=_positive_ints, event_name=_non_empty_text)
    @settings(max_examples=50)
    def test_frozen_immutability(self, id: int, event_name: str) -> None:
        """DropFilter instances are immutable (frozen=True).

        Args:
            id: Drop filter ID.
            event_name: Event name to filter.
        """
        drop_filter = DropFilter(id=id, event_name=event_name)
        with pytest.raises(Exception):  # noqa: B017
            drop_filter.event_name = "mutated"  # type: ignore[misc]


# =============================================================================
# DropFilterLimitsResponse Property Tests
# =============================================================================


class TestDropFilterLimitsResponseProperties:
    """Property-based tests for DropFilterLimitsResponse."""

    @given(filter_limit=st.integers(min_value=0, max_value=100000))
    @settings(max_examples=50)
    def test_field_preservation(self, filter_limit: int) -> None:
        """filter_limit is preserved through model_dump / model_validate.

        Args:
            filter_limit: Maximum allowed filters.
        """
        response = DropFilterLimitsResponse(filter_limit=filter_limit)
        data = response.model_dump()
        restored = DropFilterLimitsResponse.model_validate(data)
        assert restored.filter_limit == filter_limit


# =============================================================================
# ComposedPropertyValue Property Tests
# =============================================================================


class TestComposedPropertyValueProperties:
    """Property-based tests for ComposedPropertyValue Pydantic model."""

    @given(
        resource_type=_non_empty_text,
        type_=_optional_text,
        type_cast=_optional_text,
        join_property_type=_optional_text,
    )
    @settings(max_examples=50)
    def test_serialization_round_trip(
        self,
        resource_type: str,
        type_: str | None,
        type_cast: str | None,
        join_property_type: str | None,
    ) -> None:
        """ComposedPropertyValue survives model_dump / model_validate round-trip.

        Args:
            resource_type: Resource type string.
            type_: Optional type field.
            type_cast: Optional type cast field.
            join_property_type: Optional join property type.
        """
        composed = ComposedPropertyValue(
            resource_type=resource_type,
            type=type_,
            type_cast=type_cast,
            join_property_type=join_property_type,
        )
        data = composed.model_dump()
        restored = ComposedPropertyValue.model_validate(data)
        assert restored == composed


# =============================================================================
# CustomProperty Property Tests
# =============================================================================


class TestCustomPropertyProperties:
    """Property-based tests for CustomProperty Pydantic model."""

    @given(
        custom_property_id=_positive_ints,
        name=_non_empty_text,
        resource_type=_custom_property_resource_types,
        description=_optional_text,
        property_type=_optional_text,
        display_formula=_optional_text,
        is_locked=_optional_bools,
        is_visible=_optional_bools,
        data_group_id=_optional_text,
        created=_optional_timestamps,
        modified=_optional_timestamps,
    )
    @settings(max_examples=50)
    def test_serialization_round_trip(
        self,
        custom_property_id: int,
        name: str,
        resource_type: CustomPropertyResourceType,
        description: str | None,
        property_type: str | None,
        display_formula: str | None,
        is_locked: bool | None,
        is_visible: bool | None,
        data_group_id: str | None,
        created: str | None,
        modified: str | None,
    ) -> None:
        """CustomProperty survives model_dump / model_validate round-trip.

        Args:
            custom_property_id: Custom property ID.
            name: Property name.
            resource_type: Resource type enum.
            description: Optional description.
            property_type: Optional property type.
            display_formula: Optional formula expression.
            is_locked: Optional locked flag.
            is_visible: Optional visibility flag.
            data_group_id: Optional data group ID.
            created: Optional creation timestamp.
            modified: Optional modification timestamp.
        """
        custom_prop = CustomProperty(
            custom_property_id=custom_property_id,
            name=name,
            resource_type=resource_type,
            description=description,
            property_type=property_type,
            display_formula=display_formula,
            is_locked=is_locked,
            is_visible=is_visible,
            data_group_id=data_group_id,
            created=created,
            modified=modified,
        )
        data = custom_prop.model_dump()
        restored = CustomProperty.model_validate(data)
        assert restored == custom_prop

    @given(
        custom_property_id=_positive_ints,
        name=_non_empty_text,
        resource_type=_custom_property_resource_types,
    )
    @settings(max_examples=50)
    def test_frozen_immutability(
        self,
        custom_property_id: int,
        name: str,
        resource_type: CustomPropertyResourceType,
    ) -> None:
        """CustomProperty instances are immutable (frozen=True).

        Args:
            custom_property_id: Custom property ID.
            name: Property name.
            resource_type: Resource type enum.
        """
        custom_prop = CustomProperty(
            custom_property_id=custom_property_id,
            name=name,
            resource_type=resource_type,
        )
        with pytest.raises(Exception):  # noqa: B017
            custom_prop.name = "mutated"  # type: ignore[misc]


# =============================================================================
# LookupTable Property Tests
# =============================================================================


class TestLookupTableProperties:
    """Property-based tests for LookupTable Pydantic model."""

    @given(
        id=_positive_ints,
        name=_non_empty_text,
        token=_optional_text,
        created_at=_optional_timestamps,
        last_modified_at=_optional_timestamps,
        has_mapped_properties=_optional_bools,
    )
    @settings(max_examples=50)
    def test_serialization_round_trip(
        self,
        id: int,
        name: str,
        token: str | None,
        created_at: str | None,
        last_modified_at: str | None,
        has_mapped_properties: bool | None,
    ) -> None:
        """LookupTable survives model_dump / model_validate round-trip.

        Args:
            id: Lookup table ID.
            name: Table name.
            token: Optional token.
            created_at: Optional creation timestamp.
            last_modified_at: Optional last modified timestamp.
            has_mapped_properties: Optional mapped properties flag.
        """
        lookup_table = LookupTable(
            id=id,
            name=name,
            token=token,
            created_at=created_at,
            last_modified_at=last_modified_at,
            has_mapped_properties=has_mapped_properties,
        )
        data = lookup_table.model_dump()
        restored = LookupTable.model_validate(data)
        assert restored == lookup_table

    @given(id=_positive_ints, name=_non_empty_text)
    @settings(max_examples=50)
    def test_frozen_immutability(self, id: int, name: str) -> None:
        """LookupTable instances are immutable (frozen=True).

        Args:
            id: Lookup table ID.
            name: Table name.
        """
        lookup_table = LookupTable(id=id, name=name)
        with pytest.raises(Exception):  # noqa: B017
            lookup_table.name = "mutated"  # type: ignore[misc]


# =============================================================================
# LookupTableUploadUrl Property Tests
# =============================================================================


class TestLookupTableUploadUrlProperties:
    """Property-based tests for LookupTableUploadUrl Pydantic model."""

    @given(
        url=_url_strings,
        path=_non_empty_text,
        key=_non_empty_text,
    )
    @settings(max_examples=50)
    def test_serialization_round_trip(
        self,
        url: str,
        path: str,
        key: str,
    ) -> None:
        """LookupTableUploadUrl survives model_dump / model_validate round-trip.

        Args:
            url: Signed GCS upload URL.
            path: GCS path for registration.
            key: Primary key column name.
        """
        upload_url = LookupTableUploadUrl(url=url, path=path, key=key)
        data = upload_url.model_dump()
        restored = LookupTableUploadUrl.model_validate(data)
        assert restored == upload_url

    @given(
        url=_url_strings,
        path=_non_empty_text,
        key=_non_empty_text,
    )
    @settings(max_examples=50)
    def test_fields_match(self, url: str, path: str, key: str) -> None:
        """LookupTableUploadUrl fields match construction values.

        Args:
            url: Signed GCS upload URL.
            path: GCS path for registration.
            key: Primary key column name.
        """
        upload_url = LookupTableUploadUrl(url=url, path=path, key=key)
        assert upload_url.url == url
        assert upload_url.path == path
        assert upload_url.key == key


# =============================================================================
# UpdateEventDefinitionParams Property Tests
# =============================================================================


class TestUpdateEventDefinitionParamsProperties:
    """Property-based tests for UpdateEventDefinitionParams."""

    @given(
        hidden=_optional_bools,
        dropped=_optional_bools,
        merged=_optional_bools,
        verified=_optional_bools,
        tags=_optional_tag_lists,
        description=_optional_text,
    )
    @settings(max_examples=50)
    def test_exclude_none_has_no_nones(
        self,
        hidden: bool | None,
        dropped: bool | None,
        merged: bool | None,
        verified: bool | None,
        tags: list[str] | None,
        description: str | None,
    ) -> None:
        """model_dump(exclude_none=True) never contains None values.

        Args:
            hidden: Optional hidden flag.
            dropped: Optional dropped flag.
            merged: Optional merged flag.
            verified: Optional verified flag.
            tags: Optional tag list.
            description: Optional description.
        """
        params = UpdateEventDefinitionParams(
            hidden=hidden,
            dropped=dropped,
            merged=merged,
            verified=verified,
            tags=tags,
            description=description,
        )
        dumped = params.model_dump(exclude_none=True)
        for value in dumped.values():
            assert value is not None

    @given(
        hidden=_optional_bools,
        dropped=_optional_bools,
        description=_optional_text,
    )
    @settings(max_examples=50)
    def test_round_trip_with_exclude_none(
        self,
        hidden: bool | None,
        dropped: bool | None,
        description: str | None,
    ) -> None:
        """Params round-trip through model_dump(exclude_none=True) / model_validate.

        Args:
            hidden: Optional hidden flag.
            dropped: Optional dropped flag.
            description: Optional description.
        """
        params = UpdateEventDefinitionParams(
            hidden=hidden,
            dropped=dropped,
            description=description,
        )
        dumped = params.model_dump(exclude_none=True)
        restored = UpdateEventDefinitionParams.model_validate(dumped)
        # Non-None fields must match; None fields become None in restored
        if hidden is not None:
            assert restored.hidden == hidden
        if dropped is not None:
            assert restored.dropped == dropped
        if description is not None:
            assert restored.description == description


# =============================================================================
# UpdatePropertyDefinitionParams Property Tests
# =============================================================================


class TestUpdatePropertyDefinitionParamsProperties:
    """Property-based tests for UpdatePropertyDefinitionParams."""

    @given(
        hidden=_optional_bools,
        dropped=_optional_bools,
        merged=_optional_bools,
        sensitive=_optional_bools,
        description=_optional_text,
    )
    @settings(max_examples=50)
    def test_exclude_none_has_no_nones(
        self,
        hidden: bool | None,
        dropped: bool | None,
        merged: bool | None,
        sensitive: bool | None,
        description: str | None,
    ) -> None:
        """model_dump(exclude_none=True) never contains None values.

        Args:
            hidden: Optional hidden flag.
            dropped: Optional dropped flag.
            merged: Optional merged flag.
            sensitive: Optional PII flag.
            description: Optional description.
        """
        params = UpdatePropertyDefinitionParams(
            hidden=hidden,
            dropped=dropped,
            merged=merged,
            sensitive=sensitive,
            description=description,
        )
        dumped = params.model_dump(exclude_none=True)
        for value in dumped.values():
            assert value is not None


# =============================================================================
# CreateTagParams / UpdateTagParams Property Tests
# =============================================================================


class TestCreateTagParamsProperties:
    """Property-based tests for CreateTagParams."""

    @given(name=_non_empty_text)
    @settings(max_examples=50)
    def test_serialization_round_trip(self, name: str) -> None:
        """CreateTagParams survives model_dump / model_validate round-trip.

        Args:
            name: Tag name.
        """
        params = CreateTagParams(name=name)
        data = params.model_dump()
        restored = CreateTagParams.model_validate(data)
        assert restored.name == name

    @given(name=_non_empty_text)
    @settings(max_examples=50)
    def test_name_always_present(self, name: str) -> None:
        """CreateTagParams always has name in dump.

        Args:
            name: Tag name.
        """
        params = CreateTagParams(name=name)
        dumped = params.model_dump(exclude_none=True)
        assert "name" in dumped
        assert dumped["name"] == name


class TestUpdateTagParamsProperties:
    """Property-based tests for UpdateTagParams."""

    @given(name=_optional_text)
    @settings(max_examples=50)
    def test_exclude_none_has_no_nones(self, name: str | None) -> None:
        """model_dump(exclude_none=True) never contains None values.

        Args:
            name: Optional tag name.
        """
        params = UpdateTagParams(name=name)
        dumped = params.model_dump(exclude_none=True)
        for value in dumped.values():
            assert value is not None


# =============================================================================
# CreateDropFilterParams / UpdateDropFilterParams Property Tests
# =============================================================================


class TestCreateDropFilterParamsProperties:
    """Property-based tests for CreateDropFilterParams."""

    @given(
        event_name=_non_empty_text,
        filters=_simple_filters,
    )
    @settings(max_examples=50)
    def test_serialization_round_trip(
        self,
        event_name: str,
        filters: list[dict[str, str]],
    ) -> None:
        """CreateDropFilterParams survives model_dump / model_validate round-trip.

        Args:
            event_name: Event name to filter.
            filters: Filter condition JSON.
        """
        params = CreateDropFilterParams(event_name=event_name, filters=filters)
        data = params.model_dump()
        restored = CreateDropFilterParams.model_validate(data)
        assert restored.event_name == event_name
        assert restored.filters == filters

    @given(event_name=_non_empty_text, filters=_simple_filters)
    @settings(max_examples=50)
    def test_required_fields_always_present(
        self,
        event_name: str,
        filters: list[dict[str, str]],
    ) -> None:
        """Required fields always present in dump.

        Args:
            event_name: Event name to filter.
            filters: Filter condition JSON.
        """
        params = CreateDropFilterParams(event_name=event_name, filters=filters)
        dumped = params.model_dump(exclude_none=True)
        assert "event_name" in dumped
        assert "filters" in dumped


class TestUpdateDropFilterParamsProperties:
    """Property-based tests for UpdateDropFilterParams."""

    @given(
        id=_positive_ints,
        event_name=_optional_text,
        active=_optional_bools,
    )
    @settings(max_examples=50)
    def test_exclude_none_has_no_nones(
        self,
        id: int,
        event_name: str | None,
        active: bool | None,
    ) -> None:
        """model_dump(exclude_none=True) never contains None values.

        Args:
            id: Drop filter ID.
            event_name: Optional event name.
            active: Optional active flag.
        """
        params = UpdateDropFilterParams(
            id=id,
            event_name=event_name,
            active=active,
        )
        dumped = params.model_dump(exclude_none=True)
        for value in dumped.values():
            assert value is not None
        # id is required, always present
        assert "id" in dumped

    @given(
        id=_positive_ints,
        event_name=_optional_text,
        active=_optional_bools,
    )
    @settings(max_examples=50)
    def test_round_trip_with_exclude_none(
        self,
        id: int,
        event_name: str | None,
        active: bool | None,
    ) -> None:
        """Params round-trip through model_dump(exclude_none=True) / model_validate.

        Args:
            id: Drop filter ID.
            event_name: Optional event name.
            active: Optional active flag.
        """
        params = UpdateDropFilterParams(
            id=id,
            event_name=event_name,
            active=active,
        )
        dumped = params.model_dump(exclude_none=True)
        restored = UpdateDropFilterParams.model_validate(dumped)
        assert restored.id == id
        if event_name is not None:
            assert restored.event_name == event_name
        if active is not None:
            assert restored.active == active


# =============================================================================
# CreateCustomEventParams Property Tests
# =============================================================================


class TestCreateCustomEventParamsProperties:
    """Property-based tests for CreateCustomEventParams."""

    @given(
        name=_non_empty_text,
        alternatives=st.lists(_non_empty_text, min_size=1, max_size=20, unique=True),
    )
    @settings(max_examples=50)
    def test_construction_invariant(self, name: str, alternatives: list[str]) -> None:
        """Any valid (non-empty name, non-empty unique alternatives) round-trips.

        Args:
            name: Display name for the custom event.
            alternatives: Unique underlying event names to alias.
        """
        params = CreateCustomEventParams(name=name, alternatives=alternatives)
        assert params.name == name
        assert params.alternatives == alternatives

    @given(
        name=_non_empty_text,
        alternatives=st.lists(_non_empty_text, min_size=1, max_size=10, unique=True),
    )
    @settings(max_examples=50)
    def test_form_body_alternatives_round_trip_to_event_dicts(
        self, name: str, alternatives: list[str]
    ) -> None:
        """to_form_body() always emits a JSON list of {event: name} dicts.

        Args:
            name: Display name for the custom event.
            alternatives: Unique underlying event names.
        """
        body = CreateCustomEventParams(
            name=name, alternatives=alternatives
        ).to_form_body()
        decoded = json.loads(body["alternatives"])
        assert decoded == [{"event": e} for e in alternatives]
        assert body["name"] == name

    @given(
        name=_non_empty_text,
        alternatives=st.lists(_non_empty_text, min_size=1, max_size=10, unique=True),
    )
    @settings(max_examples=50)
    def test_form_body_values_are_strings(
        self, name: str, alternatives: list[str]
    ) -> None:
        """All values in the form body are strings (form-encoding requirement).

        Args:
            name: Display name for the custom event.
            alternatives: Unique underlying event names.
        """
        body = CreateCustomEventParams(
            name=name, alternatives=alternatives
        ).to_form_body()
        assert all(isinstance(v, str) for v in body.values())


# =============================================================================
# CustomEvent Property Tests
# =============================================================================


class TestCustomEventProperties:
    """Property-based tests for CustomEvent."""

    @given(
        ce_id=_positive_ints,
        name=_non_empty_text,
        alts=st.lists(_non_empty_text, min_size=0, max_size=20),
    )
    @settings(max_examples=50)
    def test_round_trip_via_model_dump(
        self, ce_id: int, name: str, alts: list[str]
    ) -> None:
        """CustomEvent round-trips through model_dump / model_validate.

        Args:
            ce_id: Server-assigned custom event ID.
            name: Display name.
            alts: Alternative event names.
        """
        original = CustomEvent(
            id=ce_id,
            name=name,
            alternatives=[CustomEventAlternative(event=e) for e in alts],
        )
        rebuilt = CustomEvent.model_validate(original.model_dump())
        assert rebuilt == original

    @given(
        ce_id=_positive_ints,
        name=_non_empty_text,
        alts=st.lists(_non_empty_text, min_size=0, max_size=10),
    )
    @settings(max_examples=50)
    def test_alternatives_preserve_order(
        self, ce_id: int, name: str, alts: list[str]
    ) -> None:
        """CustomEvent preserves the order of alternatives across construction.

        Args:
            ce_id: Server-assigned custom event ID.
            name: Display name.
            alts: Alternative event names whose order must survive.
        """
        ce = CustomEvent(
            id=ce_id,
            name=name,
            alternatives=[CustomEventAlternative(event=e) for e in alts],
        )
        assert [a.event for a in ce.alternatives] == alts
