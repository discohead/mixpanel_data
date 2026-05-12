"""Tests for Phase 025 Experiment types in mixpanel_headless.types.

Tests ExperimentStatus enum, ExperimentCreator, Experiment, and all
experiment param types including frozen immutability, extra field
preservation, populate_by_name, and exclude_none serialization.
"""

# ruff: noqa: ARG001

from __future__ import annotations

from typing import Any

import pytest
from pydantic import ValidationError

from mixpanel_headless.types import (
    CreateExperimentParams,
    DuplicateExperimentParams,
    Experiment,
    ExperimentConcludeParams,
    ExperimentCreator,
    ExperimentDecideParams,
    ExperimentStatus,
    UpdateExperimentParams,
)


class TestExperimentStatus:
    """Tests for ExperimentStatus enum values and usage."""

    def test_draft_value(self) -> None:
        """ExperimentStatus.DRAFT has value 'draft'."""
        assert ExperimentStatus.DRAFT.value == "draft"

    def test_active_value(self) -> None:
        """ExperimentStatus.ACTIVE has value 'active'."""
        assert ExperimentStatus.ACTIVE.value == "active"

    def test_concluded_value(self) -> None:
        """ExperimentStatus.CONCLUDED has value 'concluded'."""
        assert ExperimentStatus.CONCLUDED.value == "concluded"

    def test_success_value(self) -> None:
        """ExperimentStatus.SUCCESS has value 'success'."""
        assert ExperimentStatus.SUCCESS.value == "success"

    def test_fail_value(self) -> None:
        """ExperimentStatus.FAIL has value 'fail'."""
        assert ExperimentStatus.FAIL.value == "fail"

    def test_is_str_subclass(self) -> None:
        """ExperimentStatus members are also str instances."""
        assert isinstance(ExperimentStatus.DRAFT, str)
        assert ExperimentStatus.DRAFT.value == "draft"

    def test_all_members(self) -> None:
        """ExperimentStatus has exactly five members."""
        assert len(ExperimentStatus) == 5
        assert set(ExperimentStatus) == {
            ExperimentStatus.DRAFT,
            ExperimentStatus.ACTIVE,
            ExperimentStatus.CONCLUDED,
            ExperimentStatus.SUCCESS,
            ExperimentStatus.FAIL,
        }


class TestExperimentCreator:
    """Tests for ExperimentCreator model."""

    def test_required_fields_only(self) -> None:
        """ExperimentCreator with no fields uses defaults."""
        creator = ExperimentCreator()
        assert creator.id is None
        assert creator.first_name is None
        assert creator.last_name is None

    def test_all_fields(self) -> None:
        """ExperimentCreator with all fields stores values correctly."""
        creator = ExperimentCreator(
            id=42,
            first_name="Alice",
            last_name="Smith",
        )
        assert creator.id == 42
        assert creator.first_name == "Alice"
        assert creator.last_name == "Smith"

    def test_frozen(self) -> None:
        """ExperimentCreator is frozen and rejects attribute assignment."""
        creator = ExperimentCreator(id=1)
        with pytest.raises(ValidationError):
            creator.id = 2  # type: ignore[misc]

    def test_extra_fields_preserved(self) -> None:
        """ExperimentCreator preserves unknown fields via extra='allow'."""
        creator = ExperimentCreator(id=1, email="alice@example.com")
        assert creator.model_extra is not None
        assert creator.model_extra["email"] == "alice@example.com"


class TestExperiment:
    """Tests for Experiment model."""

    def test_required_fields_only(self) -> None:
        """Experiment with only required fields (id, name) succeeds."""
        exp = Experiment(id="xyz-456", name="Test Experiment")
        assert exp.id == "xyz-456"
        assert exp.name == "Test Experiment"
        assert exp.description is None
        assert exp.hypothesis is None
        assert exp.status is None
        assert exp.variants is None
        assert exp.metrics is None
        assert exp.settings is None
        assert exp.start_date is None
        assert exp.end_date is None
        assert exp.created is None
        assert exp.updated is None
        assert exp.creator is None
        assert exp.feature_flag is None
        assert exp.is_favorited is None
        assert exp.pinned_date is None
        assert exp.tags is None
        assert exp.can_edit is None

    def test_all_fields(self) -> None:
        """Experiment with every field populated stores all values correctly."""
        exp = Experiment(
            id="abc-123",
            name="Full Experiment",
            description="A complete experiment",
            hypothesis="Users will convert more",
            status=ExperimentStatus.ACTIVE,
            variants={"control": {}, "treatment": {}},
            metrics={"primary": "conversion_rate"},
            settings={"min_sample": 1000},
            exposures_cache={"total": 500},
            results_cache={"p_value": 0.03},
            start_date="2026-01-01T00:00:00Z",
            end_date="2026-02-01T00:00:00Z",
            created="2026-01-01T00:00:00Z",
            updated="2026-01-15T00:00:00Z",
            creator=ExperimentCreator(id=1, first_name="Alice"),
            feature_flag={"id": "flag-123", "key": "test_flag"},
            is_favorited=True,
            pinned_date="2026-01-05",
            tags=["growth", "checkout"],
            can_edit=True,
            last_modified_by_id=2,
            last_modified_by_name="Bob",
            last_modified_by_email="bob@example.com",
        )
        assert exp.id == "abc-123"
        assert exp.name == "Full Experiment"
        assert exp.description == "A complete experiment"
        assert exp.hypothesis == "Users will convert more"
        assert exp.status == ExperimentStatus.ACTIVE
        assert exp.variants == {"control": {}, "treatment": {}}
        assert exp.metrics == {"primary": "conversion_rate"}
        assert exp.settings == {"min_sample": 1000}
        assert exp.exposures_cache == {"total": 500}
        assert exp.results_cache == {"p_value": 0.03}
        assert exp.start_date == "2026-01-01T00:00:00Z"
        assert exp.end_date == "2026-02-01T00:00:00Z"
        assert exp.creator is not None
        assert exp.creator.first_name == "Alice"
        assert exp.feature_flag == {"id": "flag-123", "key": "test_flag"}
        assert exp.is_favorited is True
        assert exp.tags == ["growth", "checkout"]
        assert exp.can_edit is True
        assert exp.last_modified_by_id == 2
        assert exp.last_modified_by_name == "Bob"
        assert exp.last_modified_by_email == "bob@example.com"

    def test_list_shaped_variants_and_metrics(self) -> None:
        """Experiment accepts list-shaped variants and metrics from API."""
        exp = Experiment(
            id="list-exp",
            name="List Shape Test",
            variants=[
                {"key": "control", "weight": 50},
                {"key": "treatment", "weight": 50},
            ],
            metrics=[
                {"event": "Purchase", "type": "primary"},
            ],
        )
        assert isinstance(exp.variants, list)
        assert len(exp.variants) == 2
        assert isinstance(exp.metrics, list)
        assert len(exp.metrics) == 1

    def test_frozen(self) -> None:
        """Experiment model is frozen and rejects attribute assignment."""
        exp = Experiment(id="xyz-456", name="Test")
        with pytest.raises(ValidationError):
            exp.name = "new"  # type: ignore[misc]

    def test_extra_fields_preserved(self) -> None:
        """Experiment preserves unknown fields via extra='allow'."""
        exp = Experiment(id="xyz-456", name="Test", unknown_field="foo")
        assert exp.model_extra is not None
        assert exp.model_extra["unknown_field"] == "foo"

    def test_populate_by_name(self) -> None:
        """Experiment supports populate_by_name for aliased fields."""
        data: dict[str, Any] = {
            "id": "xyz-456",
            "name": "Test",
            "status": "active",
        }
        exp = Experiment.model_validate(data)
        assert exp.status == ExperimentStatus.ACTIVE

    def test_nested_creator(self) -> None:
        """Experiment parses nested creator dict into ExperimentCreator."""
        exp = Experiment.model_validate(
            {
                "id": "xyz-456",
                "name": "Test",
                "creator": {"id": 1, "first_name": "Alice", "last_name": "Smith"},
            }
        )
        assert exp.creator is not None
        assert isinstance(exp.creator, ExperimentCreator)
        assert exp.creator.id == 1
        assert exp.creator.first_name == "Alice"

    def test_status_from_string(self) -> None:
        """Experiment parses status string into ExperimentStatus enum."""
        exp = Experiment.model_validate(
            {"id": "xyz-456", "name": "Test", "status": "concluded"}
        )
        assert exp.status == ExperimentStatus.CONCLUDED


class TestCreateExperimentParams:
    """Tests for CreateExperimentParams model."""

    def test_required_field_only(self) -> None:
        """CreateExperimentParams with only name succeeds."""
        params = CreateExperimentParams(name="My Experiment")
        assert params.name == "My Experiment"
        assert params.description is None
        assert params.hypothesis is None
        assert params.settings is None
        assert params.access_type is None
        assert params.can_edit is None

    def test_all_fields(self) -> None:
        """CreateExperimentParams with all fields stores values correctly."""
        params = CreateExperimentParams(
            name="Full Experiment",
            description="A test",
            hypothesis="Users convert more",
            settings={"min_sample": 1000},
            access_type="team",
            can_edit=True,
        )
        assert params.name == "Full Experiment"
        assert params.description == "A test"
        assert params.hypothesis == "Users convert more"
        assert params.settings == {"min_sample": 1000}
        assert params.access_type == "team"
        assert params.can_edit is True

    def test_exclude_none(self) -> None:
        """CreateExperimentParams excludes None fields when serializing."""
        params = CreateExperimentParams(name="X")
        data = params.model_dump(exclude_none=True)
        assert data == {"name": "X"}

    def test_exclude_none_with_some_fields(self) -> None:
        """CreateExperimentParams excludes only None fields."""
        params = CreateExperimentParams(name="X", description="Desc")
        data = params.model_dump(exclude_none=True)
        assert data == {"name": "X", "description": "Desc"}
        assert "hypothesis" not in data
        assert "settings" not in data


class TestUpdateExperimentParams:
    """Tests for UpdateExperimentParams model."""

    def test_all_optional(self) -> None:
        """UpdateExperimentParams with no fields produces empty dict."""
        params = UpdateExperimentParams()
        data = params.model_dump(exclude_none=True)
        assert data == {}

    def test_single_field(self) -> None:
        """UpdateExperimentParams with one field serializes correctly."""
        params = UpdateExperimentParams(description="Updated")
        data = params.model_dump(exclude_none=True)
        assert data == {"description": "Updated"}

    def test_multiple_fields(self) -> None:
        """UpdateExperimentParams with multiple fields serializes all."""
        params = UpdateExperimentParams(
            name="New Name",
            description="New Desc",
            variants={"control": {}, "treatment": {}},
            tags=["growth"],
        )
        data = params.model_dump(exclude_none=True)
        assert data["name"] == "New Name"
        assert data["description"] == "New Desc"
        assert data["variants"] == {"control": {}, "treatment": {}}
        assert data["tags"] == ["growth"]

    def test_exclude_none(self) -> None:
        """UpdateExperimentParams excludes None fields from serialized output."""
        params = UpdateExperimentParams(name="Only Name")
        data = params.model_dump(exclude_none=True)
        assert "description" not in data
        assert "hypothesis" not in data
        assert "variants" not in data
        assert "metrics" not in data
        assert "settings" not in data

    def test_status_field(self) -> None:
        """UpdateExperimentParams accepts ExperimentStatus enum."""
        params = UpdateExperimentParams(status=ExperimentStatus.ACTIVE)
        data = params.model_dump(exclude_none=True)
        assert data["status"] == ExperimentStatus.ACTIVE


class TestExperimentConcludeParams:
    """Tests for ExperimentConcludeParams model."""

    def test_all_optional(self) -> None:
        """ExperimentConcludeParams with no fields produces empty dict."""
        params = ExperimentConcludeParams()
        data = params.model_dump(exclude_none=True)
        assert data == {}

    def test_with_end_date(self) -> None:
        """ExperimentConcludeParams with end_date serializes correctly."""
        params = ExperimentConcludeParams(end_date="2026-04-01")
        data = params.model_dump(exclude_none=True)
        assert data == {"end_date": "2026-04-01"}


class TestExperimentDecideParams:
    """Tests for ExperimentDecideParams model."""

    def test_required_field_only(self) -> None:
        """ExperimentDecideParams with only success succeeds."""
        params = ExperimentDecideParams(success=True)
        assert params.success is True
        assert params.variant is None
        assert params.message is None

    def test_all_fields(self) -> None:
        """ExperimentDecideParams with all fields stores values correctly."""
        params = ExperimentDecideParams(
            success=True,
            variant="treatment",
            message="Treatment increased conversions by 15%",
        )
        assert params.success is True
        assert params.variant == "treatment"
        assert params.message == "Treatment increased conversions by 15%"

    def test_exclude_none(self) -> None:
        """ExperimentDecideParams excludes None fields when serializing."""
        params = ExperimentDecideParams(success=False)
        data = params.model_dump(exclude_none=True)
        assert data == {"success": False}
        assert "variant" not in data
        assert "message" not in data

    def test_success_false(self) -> None:
        """ExperimentDecideParams accepts success=False."""
        params = ExperimentDecideParams(success=False, message="No improvement")
        data = params.model_dump(exclude_none=True)
        assert data["success"] is False
        assert data["message"] == "No improvement"


class TestDuplicateExperimentParams:
    """Tests for DuplicateExperimentParams model."""

    def test_required_field_only(self) -> None:
        """DuplicateExperimentParams with only name succeeds."""
        params = DuplicateExperimentParams(name="Experiment v2")
        assert params.name == "Experiment v2"

    def test_serialization(self) -> None:
        """DuplicateExperimentParams serializes correctly."""
        params = DuplicateExperimentParams(name="Copy of Test")
        data = params.model_dump()
        assert data == {"name": "Copy of Test"}
