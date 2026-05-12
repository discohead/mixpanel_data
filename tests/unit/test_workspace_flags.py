# ruff: noqa: ARG001, ARG005
"""Unit tests for Workspace feature flag methods (Phase 025).

Tests for feature flag CRUD operations, lifecycle management, test users,
history, and limits on the Workspace facade. Each method delegates to
MixpanelAPIClient and returns typed objects.

Verifies:
- Flag CRUD: list, create, get, update, delete
- Flag lifecycle: archive, restore, duplicate
- Flag operations: set_test_users, get_history, get_limits
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import httpx
from pydantic import SecretStr

from mixpanel_headless._internal.api_client import MixpanelAPIClient
from mixpanel_headless._internal.auth.account import ServiceAccount
from mixpanel_headless._internal.auth.session import Project, Session
from mixpanel_headless.types import (
    CreateFeatureFlagParams,
    FeatureFlag,
    FeatureFlagStatus,
    FlagContractStatus,
    FlagHistoryResponse,
    FlagLimitsResponse,
    ServingMethod,
    SetTestUsersParams,
    UpdateFeatureFlagParams,
)
from mixpanel_headless.workspace import Workspace
from tests.conftest import make_session

# ---- 042 redesign: canonical fake Session for Workspace(session=…) ----
_TEST_SESSION = Session(
    account=ServiceAccount(
        name="test_account",
        region="us",
        username="test_user",
        secret=SecretStr("test_secret"),
        default_project="12345",
    ),
    project=Project(id="12345"),
)

# =============================================================================
# Helpers
# =============================================================================


def _make_oauth_credentials() -> Session:
    """Create OAuth Credentials for testing.

    Returns:
        A Credentials instance with auth_method=oauth.
    """
    return make_session(project_id="12345", region="us", oauth_token="test-token")


# _setup_config_with_account removed in B1 (Fix 9): the legacy v1
# ``ConfigManager.add_account(project_id=, region=, …)`` signature is
# gone; ``_make_workspace`` now relies on ``session=_TEST_SESSION``
# instead, which never touches a real ConfigManager.


def _make_workspace(
    temp_dir: Path,
    handler: Any,
) -> Workspace:
    """Create a Workspace with a mock HTTP transport.

    Args:
        temp_dir: Temporary directory for config and storage.
        handler: Handler function for httpx.MockTransport.

    Returns:
        A Workspace instance wired to the mock transport.
    """
    creds = _make_oauth_credentials()
    transport = httpx.MockTransport(handler)
    client = MixpanelAPIClient(session=creds, _transport=transport)
    client.set_workspace_id(100)
    return Workspace(
        session=_TEST_SESSION,
        _api_client=client,
    )


# =============================================================================
# Mock response data
# =============================================================================


def _flag_json(
    id: str = "abc-123",
    name: str = "Test Flag",
    key: str = "test_flag",
) -> dict[str, Any]:
    """Return a minimal feature flag dict matching the API shape.

    Args:
        id: Flag UUID.
        name: Flag name.
        key: Flag key.

    Returns:
        Dict that can be parsed into a FeatureFlag model.
    """
    return {
        "id": id,
        "project_id": 12345,
        "name": name,
        "key": key,
        "status": "disabled",
        "context": "default",
        "serving_method": "client",
        "ruleset": {},
        "created": "2026-01-01T00:00:00Z",
        "modified": "2026-01-01T00:00:00Z",
    }


# =============================================================================
# TestWorkspaceFeatureFlagCRUD
# =============================================================================


class TestWorkspaceFeatureFlagCRUD:
    """Tests for Workspace feature flag CRUD methods."""

    def test_list_feature_flags(self, temp_dir: Path) -> None:
        """list_feature_flags() returns list of FeatureFlag objects."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return flag list."""
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": [
                        _flag_json("id-1", "Flag A", "flag_a"),
                        _flag_json("id-2", "Flag B", "flag_b"),
                    ],
                },
            )

        ws = _make_workspace(temp_dir, handler)
        flags = ws.list_feature_flags()

        assert len(flags) == 2
        assert isinstance(flags[0], FeatureFlag)
        assert flags[0].id == "id-1"
        assert flags[0].name == "Flag A"
        assert flags[1].id == "id-2"
        assert flags[1].name == "Flag B"

    def test_list_feature_flags_empty(self, temp_dir: Path) -> None:
        """list_feature_flags() returns empty list when no flags exist."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return empty flag list."""
            return httpx.Response(200, json={"status": "ok", "results": []})

        ws = _make_workspace(temp_dir, handler)
        flags = ws.list_feature_flags()

        assert flags == []

    def test_list_feature_flags_include_archived(self, temp_dir: Path) -> None:
        """list_feature_flags(include_archived=True) passes param to API."""
        captured_url: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture URL and return flag list."""
            captured_url.append(str(request.url))
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": [_flag_json()],
                },
            )

        ws = _make_workspace(temp_dir, handler)
        flags = ws.list_feature_flags(include_archived=True)

        assert len(flags) == 1
        assert isinstance(flags[0], FeatureFlag)
        assert len(captured_url) == 1
        assert "include_archived=true" in captured_url[0]

    def test_list_feature_flags_type_check(self, temp_dir: Path) -> None:
        """list_feature_flags() returns FeatureFlag instances with correct fields."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return flag with all default fields."""
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": [_flag_json()],
                },
            )

        ws = _make_workspace(temp_dir, handler)
        flags = ws.list_feature_flags()

        assert len(flags) == 1
        flag = flags[0]
        assert isinstance(flag, FeatureFlag)
        assert flag.status == FeatureFlagStatus.DISABLED
        assert flag.serving_method == ServingMethod.CLIENT

    def test_create_feature_flag(self, temp_dir: Path) -> None:
        """create_feature_flag() returns the created FeatureFlag."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return created flag."""
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": _flag_json("new-id", "New Flag", "new_flag"),
                },
            )

        ws = _make_workspace(temp_dir, handler)
        params = CreateFeatureFlagParams(name="New Flag", key="new_flag")
        flag = ws.create_feature_flag(params)

        assert isinstance(flag, FeatureFlag)
        assert flag.id == "new-id"
        assert flag.name == "New Flag"
        assert flag.key == "new_flag"

    def test_create_feature_flag_with_options(self, temp_dir: Path) -> None:
        """create_feature_flag() sends optional fields when provided."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return created flag with options."""
            data = _flag_json("new-id", "Dark Mode", "dark_mode")
            data["description"] = "Toggle dark mode"
            data["status"] = "enabled"
            return httpx.Response(
                200,
                json={"status": "ok", "results": data},
            )

        ws = _make_workspace(temp_dir, handler)
        params = CreateFeatureFlagParams(
            name="Dark Mode",
            key="dark_mode",
            description="Toggle dark mode",
            status=FeatureFlagStatus.ENABLED,
        )
        flag = ws.create_feature_flag(params)

        assert flag.description == "Toggle dark mode"
        assert flag.status == FeatureFlagStatus.ENABLED

    def test_get_feature_flag(self, temp_dir: Path) -> None:
        """get_feature_flag() returns a single FeatureFlag by ID."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return single flag."""
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": _flag_json("abc-123", "My Flag", "my_flag"),
                },
            )

        ws = _make_workspace(temp_dir, handler)
        flag = ws.get_feature_flag("abc-123")

        assert isinstance(flag, FeatureFlag)
        assert flag.id == "abc-123"
        assert flag.name == "My Flag"

    def test_get_feature_flag_preserves_extra(self, temp_dir: Path) -> None:
        """get_feature_flag() preserves extra fields from the API."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return flag with extra fields."""
            data = _flag_json()
            data["custom_metadata"] = {"team": "platform"}
            return httpx.Response(
                200,
                json={"status": "ok", "results": data},
            )

        ws = _make_workspace(temp_dir, handler)
        flag = ws.get_feature_flag("abc-123")

        assert flag.model_extra is not None
        assert flag.model_extra["custom_metadata"] == {"team": "platform"}

    def test_update_feature_flag(self, temp_dir: Path) -> None:
        """update_feature_flag() returns the updated FeatureFlag."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return updated flag."""
            data = _flag_json("abc-123", "Updated", "test_flag")
            data["status"] = "enabled"
            return httpx.Response(
                200,
                json={"status": "ok", "results": data},
            )

        ws = _make_workspace(temp_dir, handler)
        params = UpdateFeatureFlagParams(
            name="Updated",
            key="test_flag",
            status=FeatureFlagStatus.ENABLED,
            ruleset={"variants": []},
        )
        flag = ws.update_feature_flag("abc-123", params)

        assert isinstance(flag, FeatureFlag)
        assert flag.name == "Updated"
        assert flag.status == FeatureFlagStatus.ENABLED

    def test_delete_feature_flag(self, temp_dir: Path) -> None:
        """delete_feature_flag() returns None on success."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return 204 for delete."""
            return httpx.Response(204)

        ws = _make_workspace(temp_dir, handler)
        ws.delete_feature_flag("abc-123")  # Should not raise

    def test_delete_feature_flag_200(self, temp_dir: Path) -> None:
        """delete_feature_flag() handles 200 response too."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return 200 for delete."""
            return httpx.Response(200, json={"status": "ok", "results": {}})

        ws = _make_workspace(temp_dir, handler)
        ws.delete_feature_flag("abc-123")  # Should not raise


# =============================================================================
# TestWorkspaceFeatureFlagLifecycle
# =============================================================================


class TestWorkspaceFeatureFlagLifecycle:
    """Tests for Workspace feature flag lifecycle methods."""

    def test_archive_feature_flag(self, temp_dir: Path) -> None:
        """archive_feature_flag() returns None on success."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return 204 for archive."""
            return httpx.Response(204)

        ws = _make_workspace(temp_dir, handler)
        ws.archive_feature_flag("abc-123")  # Should not raise

    def test_restore_feature_flag(self, temp_dir: Path) -> None:
        """restore_feature_flag() returns the restored FeatureFlag."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return restored flag."""
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": _flag_json("abc-123", "Restored", "restored"),
                },
            )

        ws = _make_workspace(temp_dir, handler)
        flag = ws.restore_feature_flag("abc-123")

        assert isinstance(flag, FeatureFlag)
        assert flag.id == "abc-123"
        assert flag.name == "Restored"

    def test_duplicate_feature_flag(self, temp_dir: Path) -> None:
        """duplicate_feature_flag() returns the duplicated FeatureFlag."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return duplicated flag."""
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": _flag_json("dup-456", "Copy of Test", "test_flag_copy"),
                },
            )

        ws = _make_workspace(temp_dir, handler)
        flag = ws.duplicate_feature_flag("abc-123")

        assert isinstance(flag, FeatureFlag)
        assert flag.id == "dup-456"
        assert flag.name == "Copy of Test"
        assert flag.key == "test_flag_copy"


# =============================================================================
# TestWorkspaceFeatureFlagOperations
# =============================================================================


class TestWorkspaceFeatureFlagOperations:
    """Tests for Workspace feature flag test users, history, and limits."""

    def test_set_flag_test_users(self, temp_dir: Path) -> None:
        """set_flag_test_users() returns None on success."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return 204 for set test users."""
            return httpx.Response(204)

        ws = _make_workspace(temp_dir, handler)
        params = SetTestUsersParams(users={"on": "user-1", "off": "user-2"})
        ws.set_flag_test_users("abc-123", params)  # Should not raise

    def test_set_flag_test_users_empty(self, temp_dir: Path) -> None:
        """set_flag_test_users() accepts empty user mapping."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return 204 for empty test users."""
            return httpx.Response(204)

        ws = _make_workspace(temp_dir, handler)
        params = SetTestUsersParams(users={})
        ws.set_flag_test_users("abc-123", params)  # Should not raise

    def test_get_flag_history(self, temp_dir: Path) -> None:
        """get_flag_history() returns FlagHistoryResponse."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return history response."""
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": {
                        "events": [[1, "created"], [2, "enabled"]],
                        "count": 2,
                    },
                },
            )

        ws = _make_workspace(temp_dir, handler)
        history = ws.get_flag_history("abc-123")

        assert isinstance(history, FlagHistoryResponse)
        assert len(history.events) == 2
        assert history.count == 2

    def test_get_flag_history_empty(self, temp_dir: Path) -> None:
        """get_flag_history() handles empty history."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return empty history."""
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": {"events": [], "count": 0},
                },
            )

        ws = _make_workspace(temp_dir, handler)
        history = ws.get_flag_history("abc-123")

        assert isinstance(history, FlagHistoryResponse)
        assert history.events == []
        assert history.count == 0

    def test_get_flag_limits(self, temp_dir: Path) -> None:
        """get_flag_limits() returns FlagLimitsResponse."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return limits response."""
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": {
                        "limit": 100,
                        "is_trial": False,
                        "current_usage": 42,
                        "contract_status": "active",
                    },
                },
            )

        ws = _make_workspace(temp_dir, handler)
        limits = ws.get_flag_limits()

        assert isinstance(limits, FlagLimitsResponse)
        assert limits.limit == 100
        assert limits.is_trial is False
        assert limits.current_usage == 42
        assert limits.contract_status == FlagContractStatus.ACTIVE

    def test_get_flag_limits_trial(self, temp_dir: Path) -> None:
        """get_flag_limits() correctly parses trial account limits."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return trial limits."""
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": {
                        "limit": 10,
                        "is_trial": True,
                        "current_usage": 3,
                        "contract_status": "grace_period",
                    },
                },
            )

        ws = _make_workspace(temp_dir, handler)
        limits = ws.get_flag_limits()

        assert isinstance(limits, FlagLimitsResponse)
        assert limits.is_trial is True
        assert limits.contract_status == FlagContractStatus.GRACE_PERIOD
