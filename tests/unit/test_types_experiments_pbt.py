# ruff: noqa: ARG001
"""Property-based tests for Phase 025 Experiment types.

These tests verify invariants that should hold for all possible inputs
for the experiment enums and Pydantic models introduced in Phase 025.

Properties tested:
- ExperimentStatus enum round-trip and str subclass
- ExperimentCreator serialization round-trip
- Experiment serialization round-trip via model_dump / model_validate
- Experiment frozen immutability
- Experiment extra fields preserved
- CreateExperimentParams exclude_none correctness
- UpdateExperimentParams all optional (empty params valid)
- ExperimentDecideParams success field always present

Usage:
    pytest tests/unit/test_types_experiments_pbt.py
    HYPOTHESIS_PROFILE=dev pytest tests/unit/test_types_experiments_pbt.py
"""

from __future__ import annotations

from typing import Any

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from mixpanel_headless.types import (
    CreateExperimentParams,
    Experiment,
    ExperimentCreator,
    ExperimentDecideParams,
    ExperimentStatus,
    UpdateExperimentParams,
)

# =============================================================================
# Custom Strategies
# =============================================================================

# Strategy for non-empty printable strings
_non_empty_text = st.text(
    alphabet=st.characters(categories=("L", "N", "P", "S")),
    min_size=1,
    max_size=50,
).filter(lambda s: s.strip())

# Strategy for optional non-empty strings
_optional_text = st.none() | _non_empty_text

# Strategy for UUID-like strings
_uuid_strings = st.uuids().map(str)

# Strategy for positive integers
_positive_ints = st.integers(min_value=1, max_value=10**9)

# Strategy for optional positive ints
_optional_positive_ints = st.none() | _positive_ints

# Strategy for ISO 8601 timestamps
_timestamps = st.datetimes().map(lambda dt: dt.isoformat() + "Z")

# Strategy for optional timestamps
_optional_timestamps = st.none() | _timestamps

# Strategy for tag lists
_tag_lists = st.none() | st.lists(_non_empty_text, min_size=0, max_size=5)

# Strategy for simple dict[str, Any]
_simple_dicts = st.none() | st.fixed_dictionaries(
    {},
    optional={
        "key": st.just("value"),
        "count": st.integers(min_value=0, max_value=100),
        "enabled": st.booleans(),
    },
)

# Strategy for ExperimentStatus enum members
_experiment_statuses = st.sampled_from(list(ExperimentStatus))

# Strategy for ExperimentCreator instances
_experiment_creators = st.builds(
    ExperimentCreator,
    id=_optional_positive_ints,
    first_name=_optional_text,
    last_name=_optional_text,
)

# Strategy for generating valid Experiment instances
_experiments = st.builds(
    Experiment,
    id=_uuid_strings,
    name=_non_empty_text,
    description=_optional_text,
    hypothesis=_optional_text,
    status=st.none() | _experiment_statuses,
    variants=_simple_dicts,
    metrics=_simple_dicts,
    settings=_simple_dicts,
    exposures_cache=_simple_dicts,
    results_cache=_simple_dicts,
    start_date=_optional_timestamps,
    end_date=_optional_timestamps,
    created=_optional_timestamps,
    updated=_optional_timestamps,
    creator=st.none() | _experiment_creators,
    feature_flag=_simple_dicts,
    is_favorited=st.none() | st.booleans(),
    pinned_date=_optional_timestamps,
    tags=_tag_lists,
    can_edit=st.none() | st.booleans(),
    last_modified_by_id=_optional_positive_ints,
    last_modified_by_name=_optional_text,
    last_modified_by_email=_optional_text,
)


# =============================================================================
# ExperimentStatus Enum Property Tests
# =============================================================================


class TestExperimentStatusProperties:
    """Property-based tests for ExperimentStatus enum."""

    @given(status=_experiment_statuses)
    @settings(max_examples=50)
    def test_enum_round_trip(self, status: ExperimentStatus) -> None:
        """Constructing from .value returns the same member.

        Args:
            status: An ExperimentStatus enum member.
        """
        assert ExperimentStatus(status.value) is status

    @given(status=_experiment_statuses)
    @settings(max_examples=50)
    def test_enum_is_str_subclass(self, status: ExperimentStatus) -> None:
        """All enum members are valid strings.

        Args:
            status: An ExperimentStatus enum member.
        """
        assert isinstance(status, str)
        assert isinstance(status.value, str)
        assert len(status.value) > 0


# =============================================================================
# ExperimentCreator Property Tests
# =============================================================================


class TestExperimentCreatorProperties:
    """Property-based tests for ExperimentCreator Pydantic model."""

    @given(creator=_experiment_creators)
    @settings(max_examples=50)
    def test_serialization_round_trip(self, creator: ExperimentCreator) -> None:
        """All fields preserved through model_dump / model_validate.

        Args:
            creator: A Hypothesis-generated ExperimentCreator instance.
        """
        data = creator.model_dump()
        restored = ExperimentCreator.model_validate(data)
        assert restored == creator

    @given(creator=_experiment_creators)
    @settings(max_examples=50)
    def test_frozen_immutability(self, creator: ExperimentCreator) -> None:
        """ExperimentCreator instances are immutable (frozen=True).

        Args:
            creator: A Hypothesis-generated ExperimentCreator instance.
        """
        with pytest.raises(Exception):  # noqa: B017
            creator.first_name = "mutated"  # type: ignore[misc]

    @given(
        creator_data=st.fixed_dictionaries(
            {},
            optional={
                "id": _optional_positive_ints,
                "first_name": _optional_text,
                "last_name": _optional_text,
            },
        ),
        extra_key=st.sampled_from(["custom_field", "api_extra", "meta_info"]),
        extra_value=st.text(min_size=1, max_size=20),
    )
    @settings(max_examples=50)
    def test_extra_fields_preserved(
        self,
        creator_data: dict[str, Any],
        extra_key: str,
        extra_value: str,
    ) -> None:
        """Unknown fields are preserved in model_extra.

        Args:
            creator_data: Base ExperimentCreator data.
            extra_key: Name of the extra field.
            extra_value: Value of the extra field.
        """
        creator_data[extra_key] = extra_value
        creator = ExperimentCreator.model_validate(creator_data)
        assert creator.model_extra is not None
        assert extra_key in creator.model_extra
        assert creator.model_extra[extra_key] == extra_value


# =============================================================================
# Experiment Model Property Tests
# =============================================================================


class TestExperimentProperties:
    """Property-based tests for Experiment Pydantic model."""

    @given(experiment=_experiments)
    @settings(max_examples=50)
    def test_serialization_round_trip(self, experiment: Experiment) -> None:
        """Experiment survives model_dump / model_validate round-trip.

        Args:
            experiment: A Hypothesis-generated Experiment instance.
        """
        data = experiment.model_dump()
        restored = Experiment.model_validate(data)
        assert restored == experiment

    @given(experiment=_experiments)
    @settings(max_examples=50)
    def test_frozen_immutability(self, experiment: Experiment) -> None:
        """Experiment instances are immutable (frozen=True).

        Args:
            experiment: A Hypothesis-generated Experiment instance.
        """
        with pytest.raises(Exception):  # noqa: B017
            experiment.name = "mutated"  # type: ignore[misc]

    @given(
        exp_data=st.fixed_dictionaries(
            {
                "id": _uuid_strings,
                "name": _non_empty_text,
            }
        ),
        extra_key=st.sampled_from(["custom_field_1", "new_api_field", "internal_meta"]),
        extra_value=st.text(min_size=1, max_size=20),
    )
    @settings(max_examples=50)
    def test_extra_fields_preserved(
        self,
        exp_data: dict[str, Any],
        extra_key: str,
        extra_value: str,
    ) -> None:
        """Unknown fields are preserved in model_extra.

        Args:
            exp_data: Base Experiment data.
            extra_key: Name of the extra field.
            extra_value: Value of the extra field.
        """
        exp_data[extra_key] = extra_value
        experiment = Experiment.model_validate(exp_data)
        assert experiment.model_extra is not None
        assert extra_key in experiment.model_extra
        assert experiment.model_extra[extra_key] == extra_value


# =============================================================================
# CreateExperimentParams Property Tests
# =============================================================================


class TestCreateExperimentParamsProperties:
    """Property-based tests for CreateExperimentParams."""

    @given(
        name=_non_empty_text,
        description=_optional_text,
        hypothesis_text=_optional_text,
        settings_dict=_simple_dicts,
        access_type=_optional_text,
        can_edit=st.none() | st.booleans(),
    )
    @settings(max_examples=50)
    def test_exclude_none_has_no_nones(
        self,
        name: str,
        description: str | None,
        hypothesis_text: str | None,
        settings_dict: dict[str, Any] | None,
        access_type: str | None,
        can_edit: bool | None,
    ) -> None:
        """model_dump(exclude_none=True) never contains None values.

        Args:
            name: Experiment name.
            description: Optional description.
            hypothesis_text: Optional hypothesis.
            settings_dict: Optional settings.
            access_type: Optional access type.
            can_edit: Optional edit permission.
        """
        params = CreateExperimentParams(
            name=name,
            description=description,
            hypothesis=hypothesis_text,
            settings=settings_dict,
            access_type=access_type,
            can_edit=can_edit,
        )
        dumped = params.model_dump(exclude_none=True)
        for value in dumped.values():
            assert value is not None
        # Required field always present
        assert "name" in dumped


# =============================================================================
# UpdateExperimentParams Property Tests
# =============================================================================


class TestUpdateExperimentParamsProperties:
    """Property-based tests for UpdateExperimentParams."""

    def test_all_optional_empty_params_valid(self) -> None:
        """Empty params creates a valid model (all fields optional).

        Verifies that UpdateExperimentParams can be constructed with no
        arguments since all fields have default None values.
        """
        params = UpdateExperimentParams()
        dumped = params.model_dump(exclude_none=True)
        assert dumped == {}

    @given(
        name=_optional_text,
        description=_optional_text,
        hypothesis_text=_optional_text,
        status=st.none() | _experiment_statuses,
    )
    @settings(max_examples=50)
    def test_exclude_none_has_no_nones(
        self,
        name: str | None,
        description: str | None,
        hypothesis_text: str | None,
        status: ExperimentStatus | None,
    ) -> None:
        """model_dump(exclude_none=True) never contains None values.

        Args:
            name: Optional name.
            description: Optional description.
            hypothesis_text: Optional hypothesis.
            status: Optional status.
        """
        params = UpdateExperimentParams(
            name=name,
            description=description,
            hypothesis=hypothesis_text,
            status=status,
        )
        dumped = params.model_dump(exclude_none=True)
        for value in dumped.values():
            assert value is not None


# =============================================================================
# ExperimentDecideParams Property Tests
# =============================================================================


class TestExperimentDecideParamsProperties:
    """Property-based tests for ExperimentDecideParams."""

    @given(
        success=st.booleans(),
        variant=_optional_text,
        message=_optional_text,
    )
    @settings(max_examples=50)
    def test_success_always_present(
        self,
        success: bool,
        variant: str | None,
        message: str | None,
    ) -> None:
        """The success field is always present in serialized output.

        Args:
            success: Whether the experiment succeeded.
            variant: Optional winning variant key.
            message: Optional decision message.
        """
        params = ExperimentDecideParams(
            success=success,
            variant=variant,
            message=message,
        )
        dumped = params.model_dump()
        assert "success" in dumped
        assert dumped["success"] is success

    @given(
        success=st.booleans(),
        variant=_optional_text,
        message=_optional_text,
    )
    @settings(max_examples=50)
    def test_serialization_round_trip(
        self,
        success: bool,
        variant: str | None,
        message: str | None,
    ) -> None:
        """ExperimentDecideParams survives model_dump / model_validate.

        Args:
            success: Whether the experiment succeeded.
            variant: Optional winning variant key.
            message: Optional decision message.
        """
        params = ExperimentDecideParams(
            success=success,
            variant=variant,
            message=message,
        )
        data = params.model_dump()
        restored = ExperimentDecideParams.model_validate(data)
        assert restored.success == params.success
        assert restored.variant == params.variant
        assert restored.message == params.message

    def test_missing_success_raises(self) -> None:
        """Omitting the required success field raises ValidationError.

        Verifies that success is mandatory.
        """
        with pytest.raises(Exception):  # noqa: B017
            ExperimentDecideParams()  # type: ignore[call-arg]
