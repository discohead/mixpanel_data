# ruff: noqa: ARG001
"""Property-based tests for Phase 025 Feature Flag types.

These tests verify invariants that should hold for all possible inputs
for the feature flag enums and Pydantic models introduced in Phase 025.

Properties tested:
- Enum round-trip: constructing from .value returns the same member
- Enum str subclass: all members are valid strings
- FeatureFlag serialization round-trip via model_dump / model_validate
- FeatureFlag frozen immutability
- FeatureFlag extra fields preserved
- CreateFeatureFlagParams exclude_none correctness
- UpdateFeatureFlagParams required fields present
- FlagHistoryResponse count preservation
- FlagLimitsResponse contract_status round-trip

Usage:
    pytest tests/unit/test_types_feature_flags_pbt.py
    HYPOTHESIS_PROFILE=dev pytest tests/unit/test_types_feature_flags_pbt.py
"""

from __future__ import annotations

from typing import Any

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from mixpanel_headless.types import (
    CreateFeatureFlagParams,
    FeatureFlag,
    FeatureFlagStatus,
    FlagContractStatus,
    FlagHistoryResponse,
    FlagLimitsResponse,
    ServingMethod,
    UpdateFeatureFlagParams,
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

# Strategy for UUID-like strings
_uuid_strings = st.uuids().map(str)

# Strategy for positive integers (project IDs, workspace IDs)
_positive_ints = st.integers(min_value=1, max_value=10**9)

# Strategy for optional positive ints
_optional_positive_ints = st.none() | _positive_ints

# Strategy for ISO 8601 timestamps
_timestamps = st.datetimes().map(lambda dt: dt.isoformat() + "Z")

# Strategy for optional timestamps
_optional_timestamps = st.none() | _timestamps

# Strategy for tag lists
_tag_lists = st.lists(_non_empty_text, min_size=0, max_size=5)

# Strategy for simple dict[str, Any] (ruleset-like)
_simple_dicts = st.fixed_dictionaries(
    {},
    optional={
        "variants": st.just([]),
        "rollout": st.just(100),
        "enabled": st.booleans(),
    },
)

# Strategy for FeatureFlagStatus enum members
_flag_statuses = st.sampled_from(list(FeatureFlagStatus))

# Strategy for ServingMethod enum members
_serving_methods = st.sampled_from(list(ServingMethod))

# Strategy for FlagContractStatus enum members
_contract_statuses = st.sampled_from(list(FlagContractStatus))


# Strategy for generating valid FeatureFlag instances
_feature_flags = st.builds(
    FeatureFlag,
    id=_uuid_strings,
    project_id=_positive_ints,
    name=_non_empty_text,
    key=_non_empty_text,
    description=_optional_text,
    status=_flag_statuses,
    tags=_tag_lists,
    experiment_id=st.none() | _uuid_strings,
    context=_non_empty_text,
    data_group_id=_optional_text,
    serving_method=_serving_methods,
    ruleset=_simple_dicts,
    hash_salt=_optional_text,
    workspace_id=_optional_positive_ints,
    content_type=_optional_text,
    created=_timestamps,
    modified=_timestamps,
    enabled_at=_optional_timestamps,
    deleted=_optional_timestamps,
    creator_id=_optional_positive_ints,
    creator_name=_optional_text,
    creator_email=_optional_text,
    last_modified_by_id=_optional_positive_ints,
    last_modified_by_name=_optional_text,
    last_modified_by_email=_optional_text,
    is_favorited=st.none() | st.booleans(),
    pinned_date=_optional_timestamps,
    can_edit=st.booleans(),
)


# =============================================================================
# Enum Property Tests
# =============================================================================


class TestFeatureFlagStatusProperties:
    """Property-based tests for FeatureFlagStatus enum."""

    @given(status=_flag_statuses)
    @settings(max_examples=50)
    def test_enum_round_trip(self, status: FeatureFlagStatus) -> None:
        """Constructing from .value returns the same member.

        Args:
            status: A FeatureFlagStatus enum member.
        """
        assert FeatureFlagStatus(status.value) is status

    @given(status=_flag_statuses)
    @settings(max_examples=50)
    def test_enum_is_str_subclass(self, status: FeatureFlagStatus) -> None:
        """All enum members are valid strings.

        Args:
            status: A FeatureFlagStatus enum member.
        """
        assert isinstance(status, str)
        assert isinstance(status.value, str)
        assert len(status.value) > 0


class TestServingMethodProperties:
    """Property-based tests for ServingMethod enum."""

    @given(method=_serving_methods)
    @settings(max_examples=50)
    def test_enum_round_trip(self, method: ServingMethod) -> None:
        """Constructing from .value returns the same member.

        Args:
            method: A ServingMethod enum member.
        """
        assert ServingMethod(method.value) is method

    @given(method=_serving_methods)
    @settings(max_examples=50)
    def test_enum_is_str_subclass(self, method: ServingMethod) -> None:
        """All enum members are valid strings.

        Args:
            method: A ServingMethod enum member.
        """
        assert isinstance(method, str)
        assert isinstance(method.value, str)
        assert len(method.value) > 0


class TestFlagContractStatusProperties:
    """Property-based tests for FlagContractStatus enum."""

    @given(status=_contract_statuses)
    @settings(max_examples=50)
    def test_enum_round_trip(self, status: FlagContractStatus) -> None:
        """Constructing from .value returns the same member.

        Args:
            status: A FlagContractStatus enum member.
        """
        assert FlagContractStatus(status.value) is status

    @given(status=_contract_statuses)
    @settings(max_examples=50)
    def test_enum_is_str_subclass(self, status: FlagContractStatus) -> None:
        """All enum members are valid strings.

        Args:
            status: A FlagContractStatus enum member.
        """
        assert isinstance(status, str)
        assert isinstance(status.value, str)
        assert len(status.value) > 0


# =============================================================================
# FeatureFlag Model Property Tests
# =============================================================================


class TestFeatureFlagProperties:
    """Property-based tests for FeatureFlag Pydantic model."""

    @given(flag=_feature_flags)
    @settings(max_examples=50)
    def test_serialization_round_trip(self, flag: FeatureFlag) -> None:
        """FeatureFlag survives model_dump / model_validate round-trip.

        Args:
            flag: A Hypothesis-generated FeatureFlag instance.
        """
        data = flag.model_dump()
        restored = FeatureFlag.model_validate(data)
        assert restored == flag

    @given(flag=_feature_flags)
    @settings(max_examples=50)
    def test_frozen_immutability(self, flag: FeatureFlag) -> None:
        """FeatureFlag instances are immutable (frozen=True).

        Args:
            flag: A Hypothesis-generated FeatureFlag instance.
        """
        with pytest.raises(Exception):  # noqa: B017
            flag.name = "mutated"  # type: ignore[misc]

    @given(
        flag_data=st.fixed_dictionaries(
            {
                "id": _uuid_strings,
                "project_id": _positive_ints,
                "name": _non_empty_text,
                "key": _non_empty_text,
                "created": _timestamps,
                "modified": _timestamps,
                "context": _non_empty_text,
                "ruleset": _simple_dicts,
            }
        ),
        extra_key=st.sampled_from(["custom_field_1", "new_api_field", "internal_meta"]),
        extra_value=st.text(min_size=1, max_size=20),
    )
    @settings(max_examples=50)
    def test_extra_fields_preserved(
        self,
        flag_data: dict[str, Any],
        extra_key: str,
        extra_value: str,
    ) -> None:
        """Unknown fields are preserved in model_extra.

        Args:
            flag_data: Base FeatureFlag data.
            extra_key: Name of the extra field.
            extra_value: Value of the extra field.
        """
        flag_data[extra_key] = extra_value
        flag = FeatureFlag.model_validate(flag_data)
        assert flag.model_extra is not None
        assert extra_key in flag.model_extra
        assert flag.model_extra[extra_key] == extra_value


# =============================================================================
# CreateFeatureFlagParams Property Tests
# =============================================================================


class TestCreateFeatureFlagParamsProperties:
    """Property-based tests for CreateFeatureFlagParams."""

    @given(
        name=_non_empty_text,
        key=_non_empty_text,
        description=_optional_text,
        status=st.none() | _flag_statuses,
    )
    @settings(max_examples=50)
    def test_exclude_none_has_no_nones(
        self,
        name: str,
        key: str,
        description: str | None,
        status: FeatureFlagStatus | None,
    ) -> None:
        """model_dump(exclude_none=True) never contains None values.

        Args:
            name: Flag name.
            key: Flag key.
            description: Optional description.
            status: Optional status.
        """
        params = CreateFeatureFlagParams(
            name=name,
            key=key,
            description=description,
            status=status,
        )
        dumped = params.model_dump(exclude_none=True)
        for value in dumped.values():
            assert value is not None
        # Required fields always present
        assert "name" in dumped
        assert "key" in dumped
        # API-required fields always present (have defaults)
        assert "tags" in dumped
        assert "context" in dumped
        assert "serving_method" in dumped
        assert "ruleset" in dumped


# =============================================================================
# UpdateFeatureFlagParams Property Tests
# =============================================================================


class TestUpdateFeatureFlagParamsProperties:
    """Property-based tests for UpdateFeatureFlagParams."""

    @given(
        name=_non_empty_text,
        key=_non_empty_text,
        status=_flag_statuses,
        ruleset=_simple_dicts,
    )
    @settings(max_examples=50)
    def test_required_fields_present(
        self,
        name: str,
        key: str,
        status: FeatureFlagStatus,
        ruleset: dict[str, Any],
    ) -> None:
        """UpdateFeatureFlagParams must have name, key, status, ruleset.

        Args:
            name: Flag name.
            key: Flag key.
            status: Flag status.
            ruleset: Flag ruleset.
        """
        params = UpdateFeatureFlagParams(
            name=name,
            key=key,
            status=status,
            ruleset=ruleset,
        )
        dumped = params.model_dump()
        assert dumped["name"] == name
        assert dumped["key"] == key
        assert dumped["status"] == status.value
        assert dumped["ruleset"] == ruleset

    def test_missing_required_fields_raises(self) -> None:
        """Omitting required fields raises ValidationError.

        Verifies that name, key, status, and ruleset are all mandatory.
        """
        with pytest.raises(Exception):  # noqa: B017
            UpdateFeatureFlagParams()  # type: ignore[call-arg]


# =============================================================================
# FlagHistoryResponse Property Tests
# =============================================================================


class TestFlagHistoryResponseProperties:
    """Property-based tests for FlagHistoryResponse."""

    @given(
        count=st.integers(min_value=0, max_value=10000),
        num_events=st.integers(min_value=0, max_value=20),
    )
    @settings(max_examples=50)
    def test_count_preserved_through_serialization(
        self, count: int, num_events: int
    ) -> None:
        """Count field is preserved through model_dump / model_validate.

        Args:
            count: Total event count.
            num_events: Number of event arrays to generate.
        """
        events = [[i, f"event_{i}"] for i in range(num_events)]
        response = FlagHistoryResponse(events=events, count=count)
        data = response.model_dump()
        restored = FlagHistoryResponse.model_validate(data)
        assert restored.count == count
        assert len(restored.events) == num_events


# =============================================================================
# FlagLimitsResponse Property Tests
# =============================================================================


class TestFlagLimitsResponseProperties:
    """Property-based tests for FlagLimitsResponse."""

    @given(
        limit=st.integers(min_value=0, max_value=100000),
        is_trial=st.booleans(),
        current_usage=st.integers(min_value=0, max_value=100000),
        contract_status=_contract_statuses,
    )
    @settings(max_examples=50)
    def test_contract_status_round_trip(
        self,
        limit: int,
        is_trial: bool,
        current_usage: int,
        contract_status: FlagContractStatus,
    ) -> None:
        """FlagContractStatus survives serialization round-trip.

        Args:
            limit: Maximum flag count.
            is_trial: Trial flag.
            current_usage: Current usage count.
            contract_status: Contract status enum member.
        """
        response = FlagLimitsResponse(
            limit=limit,
            is_trial=is_trial,
            current_usage=current_usage,
            contract_status=contract_status,
        )
        data = response.model_dump()
        restored = FlagLimitsResponse.model_validate(data)
        assert restored.contract_status == contract_status
        assert restored.limit == limit
        assert restored.is_trial == is_trial
        assert restored.current_usage == current_usage
