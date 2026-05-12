# ruff: noqa: ARG001
"""Tests for Phase 026 Annotation types.

Tests round-trip serialization, frozen immutability, extra field preservation,
exclude_none behavior, and field validation for all annotation types.
"""

from __future__ import annotations

from typing import Any

import pytest
from pydantic import ValidationError

from mixpanel_headless.types import (
    Annotation,
    AnnotationTag,
    AnnotationUser,
    CreateAnnotationParams,
    CreateAnnotationTagParams,
    UpdateAnnotationParams,
)

# =============================================================================
# AnnotationUser Tests
# =============================================================================


class TestAnnotationUser:
    """Tests for AnnotationUser model."""

    def test_required_fields(self) -> None:
        """AnnotationUser requires id, first_name, last_name."""
        user = AnnotationUser(id=1, first_name="Alice", last_name="Smith")
        assert user.id == 1
        assert user.first_name == "Alice"
        assert user.last_name == "Smith"

    def test_frozen(self) -> None:
        """AnnotationUser is immutable."""
        user = AnnotationUser(id=1, first_name="Alice", last_name="Smith")
        with pytest.raises(ValidationError):
            user.first_name = "Bob"  # type: ignore[misc]

    def test_extra_fields_preserved(self) -> None:
        """AnnotationUser preserves extra fields from the API."""
        user = AnnotationUser(
            id=1, first_name="Alice", last_name="Smith", email="alice@example.com"
        )
        assert user.model_extra is not None
        assert user.model_extra["email"] == "alice@example.com"

    def test_model_validate(self) -> None:
        """AnnotationUser can be created from an API-like dict."""
        data: dict[str, Any] = {
            "id": 42,
            "first_name": "Bob",
            "last_name": "Jones",
        }
        user = AnnotationUser.model_validate(data)
        assert user.id == 42
        assert user.first_name == "Bob"

    def test_missing_required_field_raises(self) -> None:
        """AnnotationUser raises ValidationError when required field is missing."""
        with pytest.raises(ValidationError):
            AnnotationUser(id=1, first_name="Alice")  # type: ignore[call-arg]


# =============================================================================
# AnnotationTag Tests
# =============================================================================


class TestAnnotationTag:
    """Tests for AnnotationTag model."""

    def test_required_fields(self) -> None:
        """AnnotationTag requires id and name."""
        tag = AnnotationTag(id=1, name="releases")
        assert tag.id == 1
        assert tag.name == "releases"

    def test_optional_fields(self) -> None:
        """AnnotationTag has optional project_id and has_annotations."""
        tag = AnnotationTag(
            id=1, name="releases", project_id=12345, has_annotations=True
        )
        assert tag.project_id == 12345
        assert tag.has_annotations is True

    def test_frozen(self) -> None:
        """AnnotationTag is immutable."""
        tag = AnnotationTag(id=1, name="releases")
        with pytest.raises(ValidationError):
            tag.name = "other"  # type: ignore[misc]

    def test_extra_fields_preserved(self) -> None:
        """AnnotationTag preserves extra fields from the API."""
        tag = AnnotationTag(id=1, name="releases", custom_field="value")
        assert tag.model_extra is not None
        assert tag.model_extra["custom_field"] == "value"

    def test_model_dump(self) -> None:
        """AnnotationTag serializes correctly."""
        tag = AnnotationTag(id=1, name="releases")
        data = tag.model_dump()
        assert data["id"] == 1
        assert data["name"] == "releases"


# =============================================================================
# Annotation Tests
# =============================================================================


class TestAnnotation:
    """Tests for Annotation model."""

    def test_required_fields(self) -> None:
        """Annotation requires id, project_id, date, description."""
        ann = Annotation(
            id=1,
            project_id=12345,
            date="2026-03-31",
            description="Test",
        )
        assert ann.id == 1
        assert ann.project_id == 12345
        assert ann.date == "2026-03-31"
        assert ann.description == "Test"

    def test_optional_user(self) -> None:
        """Annotation user field is optional."""
        ann = Annotation(id=1, project_id=12345, date="2026-03-31", description="Test")
        assert ann.user is None

    def test_tags_default_empty(self) -> None:
        """Annotation tags defaults to empty list."""
        ann = Annotation(id=1, project_id=12345, date="2026-03-31", description="Test")
        assert ann.tags == []

    def test_with_user_and_tags(self) -> None:
        """Annotation can include user and tags."""
        ann = Annotation(
            id=1,
            project_id=12345,
            date="2026-03-31",
            description="Release",
            user=AnnotationUser(id=10, first_name="Alice", last_name="Smith"),
            tags=[AnnotationTag(id=1, name="releases")],
        )
        assert ann.user is not None
        assert ann.user.first_name == "Alice"
        assert len(ann.tags) == 1
        assert ann.tags[0].name == "releases"

    def test_frozen(self) -> None:
        """Annotation is immutable."""
        ann = Annotation(id=1, project_id=12345, date="2026-03-31", description="Test")
        with pytest.raises(ValidationError):
            ann.description = "Changed"  # type: ignore[misc]

    def test_extra_fields_preserved(self) -> None:
        """Annotation preserves extra fields from the API."""
        ann = Annotation(
            id=1,
            project_id=12345,
            date="2026-03-31",
            description="Test",
            custom_metadata={"team": "platform"},
        )
        assert ann.model_extra is not None
        assert ann.model_extra["custom_metadata"] == {"team": "platform"}

    def test_model_validate_from_api(self) -> None:
        """Annotation can be created from an API-like dict."""
        data: dict[str, Any] = {
            "id": 42,
            "project_id": 12345,
            "date": "2026-03-31",
            "description": "v2.5 release",
            "user": {"id": 10, "first_name": "Alice", "last_name": "Smith"},
            "tags": [{"id": 1, "name": "releases"}],
        }
        ann = Annotation.model_validate(data)
        assert ann.id == 42
        assert ann.description == "v2.5 release"
        assert ann.user is not None
        assert ann.user.first_name == "Alice"
        assert len(ann.tags) == 1

    def test_model_dump_roundtrip(self) -> None:
        """Annotation survives dump/validate roundtrip."""
        ann = Annotation(id=1, project_id=12345, date="2026-03-31", description="Test")
        data = ann.model_dump()
        restored = Annotation.model_validate(data)
        assert restored == ann

    def test_missing_required_raises(self) -> None:
        """Annotation raises ValidationError when required fields missing."""
        with pytest.raises(ValidationError):
            Annotation(id=1, project_id=12345)  # type: ignore[call-arg]


# =============================================================================
# CreateAnnotationParams Tests
# =============================================================================


class TestCreateAnnotationParams:
    """Tests for CreateAnnotationParams model."""

    def test_required_fields(self) -> None:
        """CreateAnnotationParams requires date and description."""
        params = CreateAnnotationParams(
            date="2026-03-31", description="Test annotation"
        )
        assert params.date == "2026-03-31"
        assert params.description == "Test annotation"

    def test_optional_fields_none(self) -> None:
        """CreateAnnotationParams optional fields default to None."""
        params = CreateAnnotationParams(date="2026-03-31", description="Test")
        assert params.tags is None
        assert params.user_id is None

    def test_with_all_fields(self) -> None:
        """CreateAnnotationParams accepts all fields."""
        params = CreateAnnotationParams(
            date="2026-03-31",
            description="v2.5 release",
            tags=[1, 2],
            user_id=10,
        )
        assert params.tags == [1, 2]
        assert params.user_id == 10

    def test_exclude_none(self) -> None:
        """CreateAnnotationParams exclude_none omits None fields."""
        params = CreateAnnotationParams(date="2026-03-31", description="Test")
        data = params.model_dump(exclude_none=True)
        assert "tags" not in data
        assert "user_id" not in data
        assert data["date"] == "2026-03-31"
        assert data["description"] == "Test"

    def test_exclude_none_keeps_set_fields(self) -> None:
        """CreateAnnotationParams exclude_none keeps explicitly set fields."""
        params = CreateAnnotationParams(date="2026-03-31", description="Test", tags=[1])
        data = params.model_dump(exclude_none=True)
        assert data["tags"] == [1]

    def test_description_max_length(self) -> None:
        """CreateAnnotationParams rejects descriptions over 512 characters."""
        with pytest.raises(ValidationError):
            CreateAnnotationParams(date="2026-03-31 00:00:00", description="A" * 513)

    def test_missing_required_raises(self) -> None:
        """CreateAnnotationParams raises for missing required fields."""
        with pytest.raises(ValidationError):
            CreateAnnotationParams(date="2026-03-31")  # type: ignore[call-arg]


# =============================================================================
# UpdateAnnotationParams Tests
# =============================================================================


class TestUpdateAnnotationParams:
    """Tests for UpdateAnnotationParams model."""

    def test_all_optional(self) -> None:
        """UpdateAnnotationParams has all optional fields."""
        params = UpdateAnnotationParams()
        assert params.description is None
        assert params.tags is None

    def test_with_description(self) -> None:
        """UpdateAnnotationParams accepts description."""
        params = UpdateAnnotationParams(description="Updated text")
        assert params.description == "Updated text"

    def test_with_tags(self) -> None:
        """UpdateAnnotationParams accepts tags."""
        params = UpdateAnnotationParams(tags=[1, 2, 3])
        assert params.tags == [1, 2, 3]

    def test_exclude_none(self) -> None:
        """UpdateAnnotationParams exclude_none omits None fields."""
        params = UpdateAnnotationParams(description="Updated")
        data = params.model_dump(exclude_none=True)
        assert "tags" not in data
        assert data["description"] == "Updated"

    def test_empty_exclude_none(self) -> None:
        """UpdateAnnotationParams with no fields gives empty dict after exclude_none."""
        params = UpdateAnnotationParams()
        data = params.model_dump(exclude_none=True)
        assert data == {}


# =============================================================================
# CreateAnnotationTagParams Tests
# =============================================================================


class TestCreateAnnotationTagParams:
    """Tests for CreateAnnotationTagParams model."""

    def test_required_name(self) -> None:
        """CreateAnnotationTagParams requires name."""
        params = CreateAnnotationTagParams(name="releases")
        assert params.name == "releases"

    def test_model_dump(self) -> None:
        """CreateAnnotationTagParams serializes correctly."""
        params = CreateAnnotationTagParams(name="deployments")
        data = params.model_dump()
        assert data == {"name": "deployments"}

    def test_missing_name_raises(self) -> None:
        """CreateAnnotationTagParams raises for missing name."""
        with pytest.raises(ValidationError):
            CreateAnnotationTagParams()  # type: ignore[call-arg]
