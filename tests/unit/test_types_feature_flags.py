# ruff: noqa: ARG001
"""Tests for Phase 025 Feature Flag types.

Tests round-trip serialization, frozen immutability, extra field preservation,
exclude_none behavior, and enum values for all feature flag types.
"""

from __future__ import annotations

from typing import Any

import pytest
from pydantic import ValidationError

from mixpanel_headless.types import (
    CreateFeatureFlagParams,
    FeatureFlag,
    FeatureFlagStatus,
    FlagContractStatus,
    FlagHistoryParams,
    FlagHistoryResponse,
    FlagLimitsResponse,
    ServingMethod,
    SetTestUsersParams,
    UpdateFeatureFlagParams,
)

# =============================================================================
# Enum Tests
# =============================================================================


class TestFeatureFlagStatusEnum:
    """Tests for FeatureFlagStatus enum values."""

    def test_enabled_value(self) -> None:
        """FeatureFlagStatus.ENABLED has value 'enabled'."""
        assert FeatureFlagStatus.ENABLED.value == "enabled"

    def test_disabled_value(self) -> None:
        """FeatureFlagStatus.DISABLED has value 'disabled'."""
        assert FeatureFlagStatus.DISABLED.value == "disabled"

    def test_archived_value(self) -> None:
        """FeatureFlagStatus.ARCHIVED has value 'archived'."""
        assert FeatureFlagStatus.ARCHIVED.value == "archived"

    def test_is_str_subclass(self) -> None:
        """FeatureFlagStatus members are also strings."""
        assert isinstance(FeatureFlagStatus.ENABLED, str)
        assert FeatureFlagStatus.ENABLED.value == "enabled"

    def test_all_members(self) -> None:
        """FeatureFlagStatus has exactly three members."""
        assert len(FeatureFlagStatus) == 3


class TestServingMethodEnum:
    """Tests for ServingMethod enum values."""

    def test_client_value(self) -> None:
        """ServingMethod.CLIENT has value 'client'."""
        assert ServingMethod.CLIENT.value == "client"

    def test_server_value(self) -> None:
        """ServingMethod.SERVER has value 'server'."""
        assert ServingMethod.SERVER.value == "server"

    def test_remote_or_local_value(self) -> None:
        """ServingMethod.REMOTE_OR_LOCAL has value 'remote_or_local'."""
        assert ServingMethod.REMOTE_OR_LOCAL.value == "remote_or_local"

    def test_remote_only_value(self) -> None:
        """ServingMethod.REMOTE_ONLY has value 'remote_only'."""
        assert ServingMethod.REMOTE_ONLY.value == "remote_only"

    def test_is_str_subclass(self) -> None:
        """ServingMethod members are also strings."""
        assert isinstance(ServingMethod.CLIENT, str)
        assert ServingMethod.CLIENT.value == "client"

    def test_all_members(self) -> None:
        """ServingMethod has exactly four members."""
        assert len(ServingMethod) == 4


class TestFlagContractStatusEnum:
    """Tests for FlagContractStatus enum values."""

    def test_active_value(self) -> None:
        """FlagContractStatus.ACTIVE has value 'active'."""
        assert FlagContractStatus.ACTIVE.value == "active"

    def test_grace_period_value(self) -> None:
        """FlagContractStatus.GRACE_PERIOD has value 'grace_period'."""
        assert FlagContractStatus.GRACE_PERIOD.value == "grace_period"

    def test_expired_value(self) -> None:
        """FlagContractStatus.EXPIRED has value 'expired'."""
        assert FlagContractStatus.EXPIRED.value == "expired"

    def test_is_str_subclass(self) -> None:
        """FlagContractStatus members are also strings."""
        assert isinstance(FlagContractStatus.ACTIVE, str)
        assert FlagContractStatus.ACTIVE.value == "active"

    def test_all_members(self) -> None:
        """FlagContractStatus has exactly three members."""
        assert len(FlagContractStatus) == 3


# =============================================================================
# FeatureFlag Model Tests
# =============================================================================


class TestFeatureFlagModel:
    """Tests for FeatureFlag Pydantic model."""

    def test_required_fields_only(self) -> None:
        """FeatureFlag with only required fields succeeds and has correct defaults."""
        flag = FeatureFlag(
            id="abc-123",
            project_id=12345,
            name="Test Flag",
            key="test_flag",
        )
        assert flag.id == "abc-123"
        assert flag.project_id == 12345
        assert flag.name == "Test Flag"
        assert flag.key == "test_flag"
        assert flag.description is None
        assert flag.status == FeatureFlagStatus.DISABLED
        assert flag.tags == []
        assert flag.experiment_id is None
        assert flag.context == ""
        assert flag.serving_method == ServingMethod.CLIENT
        assert flag.ruleset == {}
        assert flag.can_edit is False

    def test_all_fields(self) -> None:
        """FeatureFlag with every field populated stores all values correctly."""
        flag = FeatureFlag(
            id="abc-123",
            project_id=12345,
            name="Full Flag",
            key="full_flag",
            description="A complete feature flag",
            status=FeatureFlagStatus.ENABLED,
            tags=["release", "frontend"],
            experiment_id="exp-456",
            context="default",
            data_group_id="dg-789",
            serving_method=ServingMethod.SERVER,
            ruleset={"variants": [{"key": "on", "percentage": 100}]},
            hash_salt="salt123",
            workspace_id=999,
            content_type="feature_flag",
            created="2026-01-01T00:00:00Z",
            modified="2026-06-01T00:00:00Z",
            enabled_at="2026-03-01T00:00:00Z",
            deleted=None,
            creator_id=10,
            creator_name="Alice",
            creator_email="alice@example.com",
            last_modified_by_id=11,
            last_modified_by_name="Bob",
            last_modified_by_email="bob@example.com",
            is_favorited=True,
            pinned_date="2026-03-15",
            can_edit=True,
        )
        assert flag.id == "abc-123"
        assert flag.name == "Full Flag"
        assert flag.description == "A complete feature flag"
        assert flag.status == FeatureFlagStatus.ENABLED
        assert flag.tags == ["release", "frontend"]
        assert flag.experiment_id == "exp-456"
        assert flag.serving_method == ServingMethod.SERVER
        assert flag.creator_name == "Alice"
        assert flag.is_favorited is True
        assert flag.can_edit is True
        assert flag.workspace_id == 999

    def test_frozen(self) -> None:
        """FeatureFlag model is frozen and rejects attribute assignment."""
        flag = FeatureFlag(
            id="abc-123",
            project_id=12345,
            name="Test",
            key="test",
        )
        with pytest.raises(ValidationError):
            flag.name = "new"  # type: ignore[misc]

    def test_extra_fields_preserved(self) -> None:
        """FeatureFlag preserves unknown fields via extra='allow'."""
        flag = FeatureFlag(
            id="abc-123",
            project_id=12345,
            name="Test",
            key="test",
            unknown_field="foo",
        )
        assert flag.model_extra is not None
        assert flag.model_extra["unknown_field"] == "foo"

    def test_status_from_string(self) -> None:
        """FeatureFlag parses status from string value."""
        flag = FeatureFlag.model_validate(
            {
                "id": "abc",
                "project_id": 1,
                "name": "X",
                "key": "x",
                "status": "enabled",
            }
        )
        assert flag.status == FeatureFlagStatus.ENABLED

    def test_serving_method_from_string(self) -> None:
        """FeatureFlag parses serving_method from string value."""
        flag = FeatureFlag.model_validate(
            {
                "id": "abc",
                "project_id": 1,
                "name": "X",
                "key": "x",
                "serving_method": "server",
            }
        )
        assert flag.serving_method == ServingMethod.SERVER

    def test_model_validate_api_shape(self) -> None:
        """FeatureFlag parses a dict matching API response shape."""
        data: dict[str, Any] = {
            "id": "abc-123",
            "project_id": 12345,
            "name": "Dark Mode",
            "key": "dark_mode",
            "status": "disabled",
            "context": "default",
            "serving_method": "client",
            "ruleset": {},
            "created": "2026-01-01T00:00:00Z",
            "modified": "2026-01-01T00:00:00Z",
        }
        flag = FeatureFlag.model_validate(data)
        assert flag.key == "dark_mode"
        assert flag.status == FeatureFlagStatus.DISABLED


# =============================================================================
# CreateFeatureFlagParams Tests
# =============================================================================


class TestCreateFeatureFlagParams:
    """Tests for CreateFeatureFlagParams Pydantic model."""

    def test_required_fields_only(self) -> None:
        """CreateFeatureFlagParams with only name and key uses defaults."""
        params = CreateFeatureFlagParams(name="Dark Mode", key="dark_mode")
        assert params.name == "Dark Mode"
        assert params.key == "dark_mode"
        assert params.description is None
        assert params.status is None
        assert params.tags == []
        assert params.serving_method == ServingMethod.CLIENT
        assert params.context == "distinct_id"
        assert "variants" in params.ruleset

    def test_exclude_none(self) -> None:
        """CreateFeatureFlagParams excludes None fields when serializing."""
        params = CreateFeatureFlagParams(name="Dark Mode", key="dark_mode")
        data = params.model_dump(exclude_none=True)
        assert "name" in data
        assert "key" in data
        assert "tags" in data
        assert "context" in data
        assert "serving_method" in data
        assert "ruleset" in data
        assert "description" not in data
        assert "status" not in data

    def test_all_fields(self) -> None:
        """CreateFeatureFlagParams with all fields populated stores correctly."""
        params = CreateFeatureFlagParams(
            name="Dark Mode",
            key="dark_mode",
            description="Toggle dark mode",
            status=FeatureFlagStatus.ENABLED,
            tags=["ui"],
            context="default",
            serving_method=ServingMethod.CLIENT,
            ruleset={"variants": []},
        )
        data = params.model_dump(exclude_none=True)
        assert data["name"] == "Dark Mode"
        assert data["description"] == "Toggle dark mode"
        assert data["status"] == "enabled"
        assert data["tags"] == ["ui"]
        assert data["serving_method"] == "client"

    def test_all_fields_exclude_none(self) -> None:
        """CreateFeatureFlagParams with all fields includes all in dump."""
        params = CreateFeatureFlagParams(
            name="X",
            key="x",
            description="desc",
            status=FeatureFlagStatus.DISABLED,
            tags=[],
            context="ctx",
            serving_method=ServingMethod.SERVER,
            ruleset={},
        )
        data = params.model_dump(exclude_none=True)
        assert "description" in data
        assert "status" in data
        assert "serving_method" in data


# =============================================================================
# UpdateFeatureFlagParams Tests
# =============================================================================


class TestUpdateFeatureFlagParams:
    """Tests for UpdateFeatureFlagParams Pydantic model."""

    def test_required_fields(self) -> None:
        """UpdateFeatureFlagParams requires name, key, status, and ruleset."""
        params = UpdateFeatureFlagParams(
            name="Dark Mode",
            key="dark_mode",
            status=FeatureFlagStatus.ENABLED,
            ruleset={"variants": []},
        )
        assert params.name == "Dark Mode"
        assert params.key == "dark_mode"
        assert params.status == FeatureFlagStatus.ENABLED
        assert params.ruleset == {"variants": []}

    def test_missing_required_field_raises(self) -> None:
        """UpdateFeatureFlagParams raises ValidationError when required fields missing."""
        with pytest.raises(ValidationError):
            UpdateFeatureFlagParams(name="X")  # type: ignore[call-arg]

    def test_exclude_none(self) -> None:
        """UpdateFeatureFlagParams excludes None optional fields when serializing."""
        params = UpdateFeatureFlagParams(
            name="X",
            key="x",
            status=FeatureFlagStatus.DISABLED,
            ruleset={},
        )
        data = params.model_dump(exclude_none=True)
        assert "description" not in data
        # tags, context, serving_method have non-None defaults (API requires them)
        assert "tags" in data
        assert "context" in data
        assert "serving_method" in data
        assert data["name"] == "X"
        assert data["status"] == "disabled"

    def test_all_fields(self) -> None:
        """UpdateFeatureFlagParams with all fields populated stores correctly."""
        params = UpdateFeatureFlagParams(
            name="Dark Mode",
            key="dark_mode",
            status=FeatureFlagStatus.ENABLED,
            ruleset={"variants": [{"key": "on"}]},
            description="Updated description",
            tags=["release"],
            context="default",
            serving_method=ServingMethod.REMOTE_ONLY,
        )
        data = params.model_dump(exclude_none=True)
        assert data["description"] == "Updated description"
        assert data["tags"] == ["release"]
        assert data["serving_method"] == "remote_only"


# =============================================================================
# SetTestUsersParams Tests
# =============================================================================


class TestSetTestUsersParams:
    """Tests for SetTestUsersParams Pydantic model."""

    def test_required_fields(self) -> None:
        """SetTestUsersParams requires users dict."""
        params = SetTestUsersParams(users={"on": "user-1", "off": "user-2"})
        assert params.users == {"on": "user-1", "off": "user-2"}

    def test_empty_users(self) -> None:
        """SetTestUsersParams accepts empty users dict."""
        params = SetTestUsersParams(users={})
        assert params.users == {}

    def test_model_dump(self) -> None:
        """SetTestUsersParams serializes users dict correctly."""
        params = SetTestUsersParams(users={"variant_a": "uid-123"})
        data = params.model_dump()
        assert data == {"users": {"variant_a": "uid-123"}}


# =============================================================================
# FlagHistoryParams Tests
# =============================================================================


class TestFlagHistoryParams:
    """Tests for FlagHistoryParams Pydantic model."""

    def test_defaults(self) -> None:
        """FlagHistoryParams defaults to None for all fields."""
        params = FlagHistoryParams()
        assert params.page is None
        assert params.page_size is None

    def test_exclude_none_empty(self) -> None:
        """FlagHistoryParams with no fields produces empty dict."""
        params = FlagHistoryParams()
        data = params.model_dump(exclude_none=True)
        assert data == {}

    def test_with_values(self) -> None:
        """FlagHistoryParams with values serializes correctly."""
        params = FlagHistoryParams(page="cursor-abc", page_size=50)
        data = params.model_dump(exclude_none=True)
        assert data == {"page": "cursor-abc", "page_size": 50}

    def test_page_size_only(self) -> None:
        """FlagHistoryParams with only page_size excludes page."""
        params = FlagHistoryParams(page_size=25)
        data = params.model_dump(exclude_none=True)
        assert data == {"page_size": 25}
        assert "page" not in data


# =============================================================================
# FlagHistoryResponse Tests
# =============================================================================


class TestFlagHistoryResponse:
    """Tests for FlagHistoryResponse Pydantic model."""

    def test_required_fields(self) -> None:
        """FlagHistoryResponse requires events and count."""
        response = FlagHistoryResponse(events=[[1, "change"]], count=1)
        assert response.events == [[1, "change"]]
        assert response.count == 1

    def test_frozen(self) -> None:
        """FlagHistoryResponse is frozen and rejects attribute assignment."""
        response = FlagHistoryResponse(events=[], count=0)
        with pytest.raises(ValidationError):
            response.count = 5  # type: ignore[misc]

    def test_empty_events(self) -> None:
        """FlagHistoryResponse accepts empty events list."""
        response = FlagHistoryResponse(events=[], count=0)
        assert response.events == []
        assert response.count == 0

    def test_multiple_events(self) -> None:
        """FlagHistoryResponse stores multiple event arrays."""
        events: list[list[Any]] = [
            [1, "created", "2026-01-01"],
            [2, "enabled", "2026-01-02"],
        ]
        response = FlagHistoryResponse(events=events, count=2)
        assert len(response.events) == 2
        assert response.count == 2


# =============================================================================
# FlagLimitsResponse Tests
# =============================================================================


class TestFlagLimitsResponse:
    """Tests for FlagLimitsResponse Pydantic model."""

    def test_required_fields(self) -> None:
        """FlagLimitsResponse requires all four fields."""
        limits = FlagLimitsResponse(
            limit=100,
            is_trial=False,
            current_usage=42,
            contract_status=FlagContractStatus.ACTIVE,
        )
        assert limits.limit == 100
        assert limits.is_trial is False
        assert limits.current_usage == 42
        assert limits.contract_status == FlagContractStatus.ACTIVE

    def test_frozen(self) -> None:
        """FlagLimitsResponse is frozen and rejects attribute assignment."""
        limits = FlagLimitsResponse(
            limit=100,
            is_trial=False,
            current_usage=42,
            contract_status=FlagContractStatus.ACTIVE,
        )
        with pytest.raises(ValidationError):
            limits.limit = 200  # type: ignore[misc]

    def test_trial_account(self) -> None:
        """FlagLimitsResponse represents trial accounts."""
        limits = FlagLimitsResponse(
            limit=10,
            is_trial=True,
            current_usage=3,
            contract_status=FlagContractStatus.GRACE_PERIOD,
        )
        assert limits.is_trial is True
        assert limits.contract_status == FlagContractStatus.GRACE_PERIOD

    def test_contract_status_from_string(self) -> None:
        """FlagLimitsResponse parses contract_status from string."""
        limits = FlagLimitsResponse.model_validate(
            {
                "limit": 50,
                "is_trial": False,
                "current_usage": 10,
                "contract_status": "expired",
            }
        )
        assert limits.contract_status == FlagContractStatus.EXPIRED

    def test_missing_required_field_raises(self) -> None:
        """FlagLimitsResponse raises ValidationError when fields are missing."""
        with pytest.raises(ValidationError):
            FlagLimitsResponse(limit=100)  # type: ignore[call-arg]
