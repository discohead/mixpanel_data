# ruff: noqa: ARG001
"""Property-based tests for Schema Registry types (Phase 028).

These tests verify invariants that should hold for all possible inputs
for the schema registry Pydantic models introduced in Phase 028.

Properties tested:
- SchemaEntry serialization round-trip via model_dump / model_validate
- SchemaEntry camelCase alias round-trip
- SchemaEntry frozen immutability
- SchemaEntry extra field preservation
- BulkCreateSchemasParams serialization round-trip
- BulkCreateSchemasParams camelCase alias round-trip
- BulkCreateSchemasResponse serialization round-trip
- BulkCreateSchemasResponse frozen immutability
- BulkCreateSchemasResponse extra field preservation
- BulkPatchResult serialization round-trip
- BulkPatchResult camelCase alias round-trip
- BulkPatchResult frozen immutability
- BulkPatchResult extra field preservation
- DeleteSchemasResponse serialization round-trip
- DeleteSchemasResponse camelCase alias round-trip
- DeleteSchemasResponse frozen immutability
- DeleteSchemasResponse extra field preservation

Usage:
    pytest tests/unit/test_types_schemas_pbt.py
    HYPOTHESIS_PROFILE=dev pytest tests/unit/test_types_schemas_pbt.py
    HYPOTHESIS_PROFILE=ci pytest tests/unit/test_types_schemas_pbt.py
"""

from __future__ import annotations

from typing import Any

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from mixpanel_headless.types import (
    BulkCreateSchemasParams,
    BulkCreateSchemasResponse,
    BulkPatchResult,
    DeleteSchemasResponse,
    SchemaEntry,
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

# Strategy for optional booleans
_optional_bools = st.none() | st.booleans()

# Strategy for non-negative integers (counts)
_non_negative_ints = st.integers(min_value=0, max_value=100000)

# Strategy for entity type strings (realistic values)
_entity_types = st.sampled_from(["event", "custom_event", "profile"])

# Strategy for status strings (realistic values)
_status_values = st.sampled_from(["ok", "error"])

# Strategy for schema_definition dictionaries (simple JSON Schema-like dicts)
_schema_definition = st.dictionaries(
    st.text(min_size=1, max_size=20),
    st.one_of(st.text(), st.integers(), st.booleans()),
    min_size=0,
    max_size=5,
)

# Strategy for extra fields (to test extra="allow" models)
_extra_fields = st.dictionaries(
    st.text(
        alphabet=st.characters(categories=["L"]),
        min_size=3,
        max_size=10,
    ).map(lambda s: f"extra_{s}"),
    st.one_of(st.text(min_size=1, max_size=10), st.integers(), st.booleans()),
    min_size=1,
    max_size=3,
)


# =============================================================================
# SchemaEntry Property Tests
# =============================================================================


class TestSchemaEntryProperties:
    """Property-based tests for SchemaEntry Pydantic model."""

    @given(
        entity_type=_entity_types,
        name=_non_empty_text,
        version=_optional_text,
        schema_definition=_schema_definition,
    )
    @settings(max_examples=50)
    def test_serialization_round_trip(
        self,
        entity_type: str,
        name: str,
        version: str | None,
        schema_definition: dict[str, Any],
    ) -> None:
        """SchemaEntry survives model_dump / model_validate round-trip.

        Args:
            entity_type: Entity type string.
            name: Entity name.
            version: Optional schema version.
            schema_definition: JSON Schema definition dict.
        """
        entry = SchemaEntry(
            entity_type=entity_type,
            name=name,
            version=version,
            schema_definition=schema_definition,
        )
        data = entry.model_dump()
        restored = SchemaEntry.model_validate(data)
        assert restored == entry

    @given(
        entity_type=_entity_types,
        name=_non_empty_text,
        version=_optional_text,
        schema_definition=_schema_definition,
    )
    @settings(max_examples=50)
    def test_camel_case_alias_round_trip(
        self,
        entity_type: str,
        name: str,
        version: str | None,
        schema_definition: dict[str, Any],
    ) -> None:
        """SchemaEntry survives round-trip with camelCase alias serialization.

        Args:
            entity_type: Entity type string.
            name: Entity name.
            version: Optional schema version.
            schema_definition: JSON Schema definition dict.
        """
        entry = SchemaEntry(
            entity_type=entity_type,
            name=name,
            version=version,
            schema_definition=schema_definition,
        )
        data = entry.model_dump(by_alias=True)
        # Verify camelCase keys are present
        assert "entityType" in data
        assert "schemaJson" in data
        restored = SchemaEntry.model_validate(data)
        assert restored == entry

    @given(entity_type=_entity_types, name=_non_empty_text)
    @settings(max_examples=50)
    def test_frozen_immutability(self, entity_type: str, name: str) -> None:
        """SchemaEntry instances are immutable (frozen=True).

        Args:
            entity_type: Entity type string.
            name: Entity name.
        """
        entry = SchemaEntry(
            entity_type=entity_type,
            name=name,
            schema_definition={},
        )
        with pytest.raises(Exception):  # noqa: B017
            entry.name = "mutated"  # type: ignore[misc]

    @given(
        entity_type=_entity_types,
        name=_non_empty_text,
        schema_definition=_schema_definition,
        extra=_extra_fields,
    )
    @settings(max_examples=50)
    def test_extra_field_preservation(
        self,
        entity_type: str,
        name: str,
        schema_definition: dict[str, Any],
        extra: dict[str, Any],
    ) -> None:
        """SchemaEntry preserves extra fields (extra='allow').

        Args:
            entity_type: Entity type string.
            name: Entity name.
            schema_definition: JSON Schema definition dict.
            extra: Extra fields to attach.
        """
        entry = SchemaEntry(
            entity_type=entity_type,
            name=name,
            schema_definition=schema_definition,
            **extra,
        )
        dumped = entry.model_dump()
        for key, value in extra.items():
            assert dumped[key] == value

    @given(
        entity_type=_entity_types,
        name=_non_empty_text,
        version=_optional_text,
        schema_definition=_schema_definition,
    )
    @settings(max_examples=50)
    def test_required_fields_present(
        self,
        entity_type: str,
        name: str,
        version: str | None,
        schema_definition: dict[str, Any],
    ) -> None:
        """SchemaEntry required fields match construction values.

        Args:
            entity_type: Entity type string.
            name: Entity name.
            version: Optional schema version.
            schema_definition: JSON Schema definition dict.
        """
        entry = SchemaEntry(
            entity_type=entity_type,
            name=name,
            version=version,
            schema_definition=schema_definition,
        )
        assert entry.entity_type == entity_type
        assert entry.name == name
        assert entry.version == version
        assert entry.schema_definition == schema_definition


# =============================================================================
# BulkCreateSchemasParams Property Tests
# =============================================================================


class TestBulkCreateSchemasParamsProperties:
    """Property-based tests for BulkCreateSchemasParams Pydantic model."""

    @given(
        entity_type=_entity_types,
        name=_non_empty_text,
        schema_definition=_schema_definition,
        truncate=_optional_bools,
        params_entity_type=st.none() | _entity_types,
    )
    @settings(max_examples=50)
    def test_serialization_round_trip(
        self,
        entity_type: str,
        name: str,
        schema_definition: dict[str, Any],
        truncate: bool | None,
        params_entity_type: str | None,
    ) -> None:
        """BulkCreateSchemasParams survives model_dump / model_validate round-trip.

        Args:
            entity_type: Entity type for the schema entry.
            name: Entity name for the schema entry.
            schema_definition: JSON Schema definition for the entry.
            truncate: Optional truncate flag.
            params_entity_type: Optional entity type for the batch.
        """
        entry = SchemaEntry(
            entity_type=entity_type,
            name=name,
            schema_definition=schema_definition,
        )
        params = BulkCreateSchemasParams(
            entries=[entry],
            truncate=truncate,
            entity_type=params_entity_type,
        )
        data = params.model_dump()
        restored = BulkCreateSchemasParams.model_validate(data)
        assert restored == params

    @given(
        entity_type=_entity_types,
        name=_non_empty_text,
        schema_definition=_schema_definition,
        truncate=_optional_bools,
        params_entity_type=st.none() | _entity_types,
    )
    @settings(max_examples=50)
    def test_camel_case_alias_round_trip(
        self,
        entity_type: str,
        name: str,
        schema_definition: dict[str, Any],
        truncate: bool | None,
        params_entity_type: str | None,
    ) -> None:
        """BulkCreateSchemasParams survives round-trip with camelCase aliases.

        Args:
            entity_type: Entity type for the schema entry.
            name: Entity name for the schema entry.
            schema_definition: JSON Schema definition for the entry.
            truncate: Optional truncate flag.
            params_entity_type: Optional entity type for the batch.
        """
        entry = SchemaEntry(
            entity_type=entity_type,
            name=name,
            schema_definition=schema_definition,
        )
        params = BulkCreateSchemasParams(
            entries=[entry],
            truncate=truncate,
            entity_type=params_entity_type,
        )
        data = params.model_dump(by_alias=True)
        # Verify camelCase key for entity_type at params level
        assert "entityType" in data or params_entity_type is None
        restored = BulkCreateSchemasParams.model_validate(data)
        assert restored == params

    @given(
        num_entries=st.integers(min_value=0, max_value=5),
        truncate=_optional_bools,
    )
    @settings(max_examples=50)
    def test_entries_list_length_preserved(
        self,
        num_entries: int,
        truncate: bool | None,
    ) -> None:
        """BulkCreateSchemasParams preserves the number of entries.

        Args:
            num_entries: Number of schema entries to create.
            truncate: Optional truncate flag.
        """
        entries = [
            SchemaEntry(
                entity_type="event",
                name=f"Event_{i}",
                schema_definition={"type": "object"},
            )
            for i in range(num_entries)
        ]
        params = BulkCreateSchemasParams(entries=entries, truncate=truncate)
        data = params.model_dump()
        restored = BulkCreateSchemasParams.model_validate(data)
        assert len(restored.entries) == num_entries


# =============================================================================
# BulkCreateSchemasResponse Property Tests
# =============================================================================


class TestBulkCreateSchemasResponseProperties:
    """Property-based tests for BulkCreateSchemasResponse Pydantic model."""

    @given(
        added=_non_negative_ints,
        deleted=_non_negative_ints,
    )
    @settings(max_examples=50)
    def test_serialization_round_trip(
        self,
        added: int,
        deleted: int,
    ) -> None:
        """BulkCreateSchemasResponse survives model_dump / model_validate round-trip.

        Args:
            added: Number of schemas added.
            deleted: Number of schemas deleted.
        """
        response = BulkCreateSchemasResponse(added=added, deleted=deleted)
        data = response.model_dump()
        restored = BulkCreateSchemasResponse.model_validate(data)
        assert restored == response

    @given(
        added=_non_negative_ints,
        deleted=_non_negative_ints,
    )
    @settings(max_examples=50)
    def test_frozen_immutability(
        self,
        added: int,
        deleted: int,
    ) -> None:
        """BulkCreateSchemasResponse instances are immutable (frozen=True).

        Args:
            added: Number of schemas added.
            deleted: Number of schemas deleted.
        """
        response = BulkCreateSchemasResponse(added=added, deleted=deleted)
        with pytest.raises(Exception):  # noqa: B017
            response.added = 999  # type: ignore[misc]

    @given(
        added=_non_negative_ints,
        deleted=_non_negative_ints,
        extra=_extra_fields,
    )
    @settings(max_examples=50)
    def test_extra_field_preservation(
        self,
        added: int,
        deleted: int,
        extra: dict[str, Any],
    ) -> None:
        """BulkCreateSchemasResponse preserves extra fields (extra='allow').

        Args:
            added: Number of schemas added.
            deleted: Number of schemas deleted.
            extra: Extra fields to attach.
        """
        response = BulkCreateSchemasResponse(added=added, deleted=deleted, **extra)
        dumped = response.model_dump()
        for key, value in extra.items():
            assert dumped[key] == value

    @given(
        added=_non_negative_ints,
        deleted=_non_negative_ints,
    )
    @settings(max_examples=50)
    def test_fields_match(
        self,
        added: int,
        deleted: int,
    ) -> None:
        """BulkCreateSchemasResponse fields match construction values.

        Args:
            added: Number of schemas added.
            deleted: Number of schemas deleted.
        """
        response = BulkCreateSchemasResponse(added=added, deleted=deleted)
        assert response.added == added
        assert response.deleted == deleted


# =============================================================================
# BulkPatchResult Property Tests
# =============================================================================


class TestBulkPatchResultProperties:
    """Property-based tests for BulkPatchResult Pydantic model."""

    @given(
        entity_type=_entity_types,
        name=_non_empty_text,
        status=_status_values,
        error=_optional_text,
    )
    @settings(max_examples=50)
    def test_serialization_round_trip(
        self,
        entity_type: str,
        name: str,
        status: str,
        error: str | None,
    ) -> None:
        """BulkPatchResult survives model_dump / model_validate round-trip.

        Args:
            entity_type: Entity type processed.
            name: Entity name processed.
            status: Result status string.
            error: Optional error message.
        """
        result = BulkPatchResult(
            entity_type=entity_type,
            name=name,
            status=status,
            error=error,
        )
        data = result.model_dump()
        restored = BulkPatchResult.model_validate(data)
        assert restored == result

    @given(
        entity_type=_entity_types,
        name=_non_empty_text,
        status=_status_values,
        error=_optional_text,
    )
    @settings(max_examples=50)
    def test_camel_case_alias_round_trip(
        self,
        entity_type: str,
        name: str,
        status: str,
        error: str | None,
    ) -> None:
        """BulkPatchResult survives round-trip with camelCase alias serialization.

        Args:
            entity_type: Entity type processed.
            name: Entity name processed.
            status: Result status string.
            error: Optional error message.
        """
        result = BulkPatchResult(
            entity_type=entity_type,
            name=name,
            status=status,
            error=error,
        )
        data = result.model_dump(by_alias=True)
        assert "entityType" in data
        restored = BulkPatchResult.model_validate(data)
        assert restored == result

    @given(entity_type=_entity_types, name=_non_empty_text, status=_status_values)
    @settings(max_examples=50)
    def test_frozen_immutability(
        self, entity_type: str, name: str, status: str
    ) -> None:
        """BulkPatchResult instances are immutable (frozen=True).

        Args:
            entity_type: Entity type processed.
            name: Entity name processed.
            status: Result status string.
        """
        result = BulkPatchResult(entity_type=entity_type, name=name, status=status)
        with pytest.raises(Exception):  # noqa: B017
            result.name = "mutated"  # type: ignore[misc]

    @given(
        entity_type=_entity_types,
        name=_non_empty_text,
        status=_status_values,
        extra=_extra_fields,
    )
    @settings(max_examples=50)
    def test_extra_field_preservation(
        self,
        entity_type: str,
        name: str,
        status: str,
        extra: dict[str, Any],
    ) -> None:
        """BulkPatchResult preserves extra fields (extra='allow').

        Args:
            entity_type: Entity type processed.
            name: Entity name processed.
            status: Result status string.
            extra: Extra fields to attach.
        """
        result = BulkPatchResult(
            entity_type=entity_type,
            name=name,
            status=status,
            **extra,
        )
        dumped = result.model_dump()
        for key, value in extra.items():
            assert dumped[key] == value


# =============================================================================
# DeleteSchemasResponse Property Tests
# =============================================================================


class TestDeleteSchemasResponseProperties:
    """Property-based tests for DeleteSchemasResponse Pydantic model."""

    @given(delete_count=_non_negative_ints)
    @settings(max_examples=50)
    def test_serialization_round_trip(self, delete_count: int) -> None:
        """DeleteSchemasResponse survives model_dump / model_validate round-trip.

        Args:
            delete_count: Number of schemas deleted.
        """
        response = DeleteSchemasResponse(delete_count=delete_count)
        data = response.model_dump()
        restored = DeleteSchemasResponse.model_validate(data)
        assert restored == response

    @given(delete_count=_non_negative_ints)
    @settings(max_examples=50)
    def test_camel_case_alias_round_trip(self, delete_count: int) -> None:
        """DeleteSchemasResponse survives round-trip with camelCase alias serialization.

        Args:
            delete_count: Number of schemas deleted.
        """
        response = DeleteSchemasResponse(delete_count=delete_count)
        data = response.model_dump(by_alias=True)
        assert "deleteCount" in data
        restored = DeleteSchemasResponse.model_validate(data)
        assert restored == response

    @given(delete_count=_non_negative_ints)
    @settings(max_examples=50)
    def test_frozen_immutability(self, delete_count: int) -> None:
        """DeleteSchemasResponse instances are immutable (frozen=True).

        Args:
            delete_count: Number of schemas deleted.
        """
        response = DeleteSchemasResponse(delete_count=delete_count)
        with pytest.raises(Exception):  # noqa: B017
            response.delete_count = 999  # type: ignore[misc]

    @given(
        delete_count=_non_negative_ints,
        extra=_extra_fields,
    )
    @settings(max_examples=50)
    def test_extra_field_preservation(
        self,
        delete_count: int,
        extra: dict[str, Any],
    ) -> None:
        """DeleteSchemasResponse preserves extra fields (extra='allow').

        Args:
            delete_count: Number of schemas deleted.
            extra: Extra fields to attach.
        """
        response = DeleteSchemasResponse(delete_count=delete_count, **extra)
        dumped = response.model_dump()
        for key, value in extra.items():
            assert dumped[key] == value

    @given(delete_count=_non_negative_ints)
    @settings(max_examples=50)
    def test_field_matches(self, delete_count: int) -> None:
        """DeleteSchemasResponse field matches construction value.

        Args:
            delete_count: Number of schemas deleted.
        """
        response = DeleteSchemasResponse(delete_count=delete_count)
        assert response.delete_count == delete_count
