# ruff: noqa: ARG001
"""Tests for Phase 026 Webhook types.

Tests round-trip serialization, frozen immutability, extra field preservation,
exclude_none behavior, and enum values for all webhook types.
"""

from __future__ import annotations

from typing import Any

import pytest
from pydantic import ValidationError

from mixpanel_headless.types import (
    CreateWebhookParams,
    ProjectWebhook,
    UpdateWebhookParams,
    WebhookAuthType,
    WebhookMutationResult,
    WebhookTestParams,
    WebhookTestResult,
)

# =============================================================================
# Enum Tests
# =============================================================================


class TestWebhookAuthTypeEnum:
    """Tests for WebhookAuthType enum values."""

    def test_basic_value(self) -> None:
        """WebhookAuthType.BASIC has value 'basic'."""
        assert WebhookAuthType.BASIC.value == "basic"

    def test_is_str_subclass(self) -> None:
        """WebhookAuthType members are also strings."""
        assert isinstance(WebhookAuthType.BASIC, str)
        assert WebhookAuthType.BASIC.value == "basic"

    def test_all_members(self) -> None:
        """WebhookAuthType has exactly one member."""
        assert len(WebhookAuthType) == 1


# =============================================================================
# ProjectWebhook Model Tests
# =============================================================================


class TestProjectWebhookModel:
    """Tests for ProjectWebhook Pydantic model."""

    def test_required_fields_only(self) -> None:
        """ProjectWebhook with only required fields succeeds."""
        wh = ProjectWebhook(
            id="wh-uuid-123",
            name="My Webhook",
            url="https://example.com/hook",
            is_enabled=True,
        )
        assert wh.id == "wh-uuid-123"
        assert wh.name == "My Webhook"
        assert wh.url == "https://example.com/hook"
        assert wh.is_enabled is True
        assert wh.auth_type is None
        assert wh.created is None
        assert wh.modified is None
        assert wh.creator_id is None
        assert wh.creator_name is None

    def test_all_fields(self) -> None:
        """ProjectWebhook with every field populated stores all values."""
        wh = ProjectWebhook(
            id="wh-uuid-123",
            name="Full Webhook",
            url="https://example.com/hook",
            is_enabled=False,
            auth_type="basic",
            created="2026-01-01T00:00:00Z",
            modified="2026-06-01T00:00:00Z",
            creator_id=42,
            creator_name="Alice",
        )
        assert wh.auth_type == "basic"
        assert wh.created == "2026-01-01T00:00:00Z"
        assert wh.creator_id == 42
        assert wh.creator_name == "Alice"

    def test_frozen(self) -> None:
        """ProjectWebhook model is frozen and rejects attribute assignment."""
        wh = ProjectWebhook(
            id="wh-uuid-123",
            name="Test",
            url="https://example.com",
            is_enabled=True,
        )
        with pytest.raises(ValidationError):
            wh.name = "new"  # type: ignore[misc]

    def test_extra_fields_preserved(self) -> None:
        """ProjectWebhook preserves unknown fields via extra='allow'."""
        wh = ProjectWebhook(
            id="wh-uuid-123",
            name="Test",
            url="https://example.com",
            is_enabled=True,
            custom_field="foo",
        )
        assert wh.model_extra is not None
        assert wh.model_extra["custom_field"] == "foo"

    def test_model_validate_api_shape(self) -> None:
        """ProjectWebhook parses a dict matching API response shape."""
        data: dict[str, Any] = {
            "id": "wh-uuid-123",
            "name": "Pipeline",
            "url": "https://example.com/hook",
            "is_enabled": True,
            "auth_type": "basic",
            "created": "2026-01-01T00:00:00Z",
            "modified": "2026-01-01T00:00:00Z",
        }
        wh = ProjectWebhook.model_validate(data)
        assert wh.id == "wh-uuid-123"
        assert wh.name == "Pipeline"
        assert wh.is_enabled is True


# =============================================================================
# CreateWebhookParams Tests
# =============================================================================


class TestCreateWebhookParams:
    """Tests for CreateWebhookParams Pydantic model."""

    def test_required_fields_only(self) -> None:
        """CreateWebhookParams with only name and url uses defaults."""
        params = CreateWebhookParams(name="Hook", url="https://example.com")
        assert params.name == "Hook"
        assert params.url == "https://example.com"
        assert params.auth_type is None
        assert params.username is None
        assert params.password is None

    def test_exclude_none(self) -> None:
        """CreateWebhookParams excludes None fields when serializing."""
        params = CreateWebhookParams(name="Hook", url="https://example.com")
        data = params.model_dump(exclude_none=True)
        assert "name" in data
        assert "url" in data
        assert "auth_type" not in data
        assert "username" not in data
        assert "password" not in data

    def test_all_fields(self) -> None:
        """CreateWebhookParams with all fields stores correctly."""
        params = CreateWebhookParams(
            name="Secure Hook",
            url="https://example.com/hook",
            auth_type="basic",
            username="user",
            password="pass",
        )
        data = params.model_dump(exclude_none=True)
        assert data["name"] == "Secure Hook"
        assert data["auth_type"] == "basic"
        assert data["username"] == "user"
        assert data["password"] == "pass"


# =============================================================================
# UpdateWebhookParams Tests
# =============================================================================


class TestUpdateWebhookParams:
    """Tests for UpdateWebhookParams Pydantic model."""

    def test_empty_params(self) -> None:
        """UpdateWebhookParams with no fields produces empty dump."""
        params = UpdateWebhookParams()
        data = params.model_dump(exclude_none=True)
        assert data == {}

    def test_partial_fields(self) -> None:
        """UpdateWebhookParams with partial fields includes only set fields."""
        params = UpdateWebhookParams(name="Renamed", is_enabled=False)
        data = params.model_dump(exclude_none=True)
        assert data == {"name": "Renamed", "is_enabled": False}
        assert "url" not in data

    def test_all_fields(self) -> None:
        """UpdateWebhookParams with all fields stores correctly."""
        params = UpdateWebhookParams(
            name="Updated",
            url="https://new.example.com",
            auth_type="basic",
            username="u",
            password="p",
            is_enabled=True,
        )
        data = params.model_dump(exclude_none=True)
        assert len(data) == 6


# =============================================================================
# WebhookTestParams Tests
# =============================================================================


class TestWebhookTestParams:
    """Tests for WebhookTestParams Pydantic model."""

    def test_required_url_only(self) -> None:
        """WebhookTestParams with only url uses defaults."""
        params = WebhookTestParams(url="https://example.com/hook")
        assert params.url == "https://example.com/hook"
        assert params.name is None

    def test_exclude_none(self) -> None:
        """WebhookTestParams excludes None fields when serializing."""
        params = WebhookTestParams(url="https://example.com/hook")
        data = params.model_dump(exclude_none=True)
        assert "url" in data
        assert "name" not in data

    def test_all_fields(self) -> None:
        """WebhookTestParams with all fields stores correctly."""
        params = WebhookTestParams(
            url="https://example.com/hook",
            name="Test Hook",
            auth_type="basic",
            username="user",
            password="pass",
        )
        data = params.model_dump(exclude_none=True)
        assert len(data) == 5


# =============================================================================
# WebhookTestResult Tests
# =============================================================================


class TestWebhookTestResult:
    """Tests for WebhookTestResult Pydantic model."""

    def test_required_fields(self) -> None:
        """WebhookTestResult with required fields."""
        result = WebhookTestResult(success=True, status_code=200, message="OK")
        assert result.success is True
        assert result.status_code == 200
        assert result.message == "OK"

    def test_frozen(self) -> None:
        """WebhookTestResult is frozen."""
        result = WebhookTestResult(success=True, status_code=200, message="OK")
        with pytest.raises(ValidationError):
            result.success = False  # type: ignore[misc]

    def test_extra_fields_preserved(self) -> None:
        """WebhookTestResult preserves unknown fields via extra='allow'."""
        result = WebhookTestResult(
            success=True, status_code=200, message="OK", extra_data="bar"
        )
        assert result.model_extra is not None
        assert result.model_extra["extra_data"] == "bar"

    def test_model_validate(self) -> None:
        """WebhookTestResult parses a dict matching API response."""
        data: dict[str, Any] = {
            "success": False,
            "status_code": 500,
            "message": "Internal Server Error",
        }
        result = WebhookTestResult.model_validate(data)
        assert result.success is False
        assert result.status_code == 500


# =============================================================================
# WebhookMutationResult Tests
# =============================================================================


class TestWebhookMutationResult:
    """Tests for WebhookMutationResult Pydantic model."""

    def test_required_fields(self) -> None:
        """WebhookMutationResult with required fields."""
        result = WebhookMutationResult(id="wh-uuid-123", name="My Hook")
        assert result.id == "wh-uuid-123"
        assert result.name == "My Hook"

    def test_frozen(self) -> None:
        """WebhookMutationResult is frozen."""
        result = WebhookMutationResult(id="wh-uuid-123", name="My Hook")
        with pytest.raises(ValidationError):
            result.name = "new"  # type: ignore[misc]

    def test_extra_fields_preserved(self) -> None:
        """WebhookMutationResult preserves unknown fields."""
        result = WebhookMutationResult(id="wh-uuid-123", name="My Hook", extra="baz")
        assert result.model_extra is not None
        assert result.model_extra["extra"] == "baz"

    def test_model_validate(self) -> None:
        """WebhookMutationResult parses a dict matching API response."""
        data: dict[str, Any] = {"id": "wh-uuid-123", "name": "Created Hook"}
        result = WebhookMutationResult.model_validate(data)
        assert result.id == "wh-uuid-123"
        assert result.name == "Created Hook"
