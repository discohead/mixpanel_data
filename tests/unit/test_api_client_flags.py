# ruff: noqa: ARG001, ARG005
"""Unit tests for Feature Flag API client methods (Phase 025).

Tests for:
- Flag CRUD: list, create, get, update, delete
- Flag lifecycle: archive, restore, duplicate
- Flag operations: set_test_users, get_history, get_limits
"""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

import httpx
import pytest

from mixpanel_headless._internal.api_client import MixpanelAPIClient
from mixpanel_headless._internal.auth.session import Session
from tests.conftest import make_session

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def oauth_credentials() -> Session:
    """Create OAuth credentials for App API testing."""
    return make_session(project_id="12345", region="us", oauth_token="test-oauth-token")


def create_mock_client(
    credentials: Session,
    handler: Callable[[httpx.Request], httpx.Response],
    *,
    workspace_id: int = 100,
) -> MixpanelAPIClient:
    """Create a client with mock transport and workspace ID pre-set.

    Feature flags use require_scoped_path which needs a workspace ID.
    Setting it directly avoids needing to mock the workspace list endpoint.

    Args:
        credentials: Authentication credentials.
        handler: Mock HTTP handler function.
        workspace_id: Pre-set workspace ID (default: 100).

    Returns:
        MixpanelAPIClient configured with mock transport.
    """
    transport = httpx.MockTransport(handler)
    client = MixpanelAPIClient(session=credentials, _transport=transport)
    client.set_workspace_id(workspace_id)
    return client


def _flag_result(
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
# Flag CRUD Tests
# =============================================================================


class TestListFeatureFlags:
    """Tests for list_feature_flags() API client method."""

    def test_returns_flag_list(self, oauth_credentials: Session) -> None:
        """list_feature_flags() returns a list of flag dicts."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return sample flag list."""
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": [
                        _flag_result("id-1", "Flag A", "flag_a"),
                        _flag_result("id-2", "Flag B", "flag_b"),
                    ],
                },
            )

        client = create_mock_client(oauth_credentials, handler)
        with client:
            result = client.list_feature_flags()

        assert len(result) == 2
        assert result[0]["id"] == "id-1"
        assert result[1]["name"] == "Flag B"

    def test_uses_require_scoped_path(self, oauth_credentials: Session) -> None:
        """list_feature_flags() uses require_scoped_path for URL building."""
        captured_urls: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture URL."""
            captured_urls.append(str(request.url))
            return httpx.Response(200, json={"status": "ok", "results": []})

        client = create_mock_client(oauth_credentials, handler)
        with client:
            client.list_feature_flags()

        assert "/feature-flags" in captured_urls[0]

    def test_include_archived(self, oauth_credentials: Session) -> None:
        """list_feature_flags(include_archived=True) passes query param."""
        captured_urls: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture URL and return empty list."""
            captured_urls.append(str(request.url))
            return httpx.Response(200, json={"status": "ok", "results": []})

        client = create_mock_client(oauth_credentials, handler)
        with client:
            client.list_feature_flags(include_archived=True)

        assert "include_archived=true" in captured_urls[0].lower()

    def test_empty_result(self, oauth_credentials: Session) -> None:
        """list_feature_flags() returns empty list when no flags exist."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return empty results."""
            return httpx.Response(200, json={"status": "ok", "results": []})

        client = create_mock_client(oauth_credentials, handler)
        with client:
            result = client.list_feature_flags()

        assert result == []

    def test_uses_get_method(self, oauth_credentials: Session) -> None:
        """list_feature_flags() uses GET HTTP method."""
        captured_methods: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture HTTP method."""
            captured_methods.append(request.method)
            return httpx.Response(200, json={"status": "ok", "results": []})

        client = create_mock_client(oauth_credentials, handler)
        with client:
            client.list_feature_flags()

        assert captured_methods[0] == "GET"


class TestCreateFeatureFlag:
    """Tests for create_feature_flag() API client method."""

    def test_creates_flag(self, oauth_credentials: Session) -> None:
        """create_feature_flag() sends POST and returns flag dict."""
        captured: list[tuple[str, Any]] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture request method and body."""
            captured.append((request.method, json.loads(request.content)))
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": _flag_result("new-id", "New Flag", "new_flag"),
                },
            )

        client = create_mock_client(oauth_credentials, handler)
        with client:
            result = client.create_feature_flag({"name": "New Flag", "key": "new_flag"})

        assert captured[0][0] == "POST"
        assert captured[0][1] == {"name": "New Flag", "key": "new_flag"}
        assert result["id"] == "new-id"

    def test_url_path(self, oauth_credentials: Session) -> None:
        """create_feature_flag() posts to the feature-flags endpoint."""
        captured_urls: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture URL."""
            captured_urls.append(str(request.url))
            return httpx.Response(
                200,
                json={"status": "ok", "results": _flag_result()},
            )

        client = create_mock_client(oauth_credentials, handler)
        with client:
            client.create_feature_flag({"name": "X", "key": "x"})

        assert "/feature-flags" in captured_urls[0]


class TestGetFeatureFlag:
    """Tests for get_feature_flag() API client method."""

    def test_gets_flag_by_id(self, oauth_credentials: Session) -> None:
        """get_feature_flag() sends GET with flag ID in path."""
        captured_urls: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture URL and return flag."""
            captured_urls.append(str(request.url))
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": _flag_result("abc-123", "Test", "test"),
                },
            )

        client = create_mock_client(oauth_credentials, handler)
        with client:
            result = client.get_feature_flag("abc-123")

        assert "/feature-flags/abc-123" in captured_urls[0]
        assert result["id"] == "abc-123"

    def test_uses_get_method(self, oauth_credentials: Session) -> None:
        """get_feature_flag() uses GET HTTP method."""
        captured_methods: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture HTTP method."""
            captured_methods.append(request.method)
            return httpx.Response(
                200,
                json={"status": "ok", "results": _flag_result()},
            )

        client = create_mock_client(oauth_credentials, handler)
        with client:
            client.get_feature_flag("abc-123")

        assert captured_methods[0] == "GET"


class TestUpdateFeatureFlag:
    """Tests for update_feature_flag() API client method."""

    def test_updates_flag(self, oauth_credentials: Session) -> None:
        """update_feature_flag() sends PUT with body."""
        captured: list[tuple[str, Any]] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture method and body."""
            captured.append((request.method, json.loads(request.content)))
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": _flag_result("abc-123", "Updated", "test"),
                },
            )

        client = create_mock_client(oauth_credentials, handler)
        with client:
            result = client.update_feature_flag(
                "abc-123",
                {
                    "name": "Updated",
                    "key": "test",
                    "status": "enabled",
                    "ruleset": {},
                },
            )

        assert captured[0][0] == "PUT"
        assert captured[0][1]["name"] == "Updated"
        assert result["name"] == "Updated"

    def test_url_path(self, oauth_credentials: Session) -> None:
        """update_feature_flag() targets the correct flag ID in URL."""
        captured_urls: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture URL."""
            captured_urls.append(str(request.url))
            return httpx.Response(
                200,
                json={"status": "ok", "results": _flag_result()},
            )

        client = create_mock_client(oauth_credentials, handler)
        with client:
            client.update_feature_flag(
                "abc-123",
                {"name": "X", "key": "x", "status": "disabled", "ruleset": {}},
            )

        assert "/feature-flags/abc-123" in captured_urls[0]


class TestDeleteFeatureFlag:
    """Tests for delete_feature_flag() API client method."""

    def test_deletes_flag(self, oauth_credentials: Session) -> None:
        """delete_feature_flag() sends DELETE request."""
        captured_methods: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture method."""
            captured_methods.append(request.method)
            return httpx.Response(204)

        client = create_mock_client(oauth_credentials, handler)
        with client:
            client.delete_feature_flag("abc-123")

        assert captured_methods[0] == "DELETE"

    def test_url_path(self, oauth_credentials: Session) -> None:
        """delete_feature_flag() targets the correct flag ID in URL."""
        captured_urls: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture URL."""
            captured_urls.append(str(request.url))
            return httpx.Response(204)

        client = create_mock_client(oauth_credentials, handler)
        with client:
            client.delete_feature_flag("abc-123")

        assert "/feature-flags/abc-123" in captured_urls[0]


# =============================================================================
# Flag Lifecycle Tests
# =============================================================================


class TestArchiveFeatureFlag:
    """Tests for archive_feature_flag() API client method."""

    def test_archives_flag(self, oauth_credentials: Session) -> None:
        """archive_feature_flag() sends POST to archive endpoint."""
        captured: list[tuple[str, str]] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture method and URL."""
            captured.append((request.method, str(request.url)))
            return httpx.Response(204)

        client = create_mock_client(oauth_credentials, handler)
        with client:
            client.archive_feature_flag("abc-123")

        assert captured[0][0] == "POST"
        assert "/feature-flags/abc-123/archive" in captured[0][1]


class TestRestoreFeatureFlag:
    """Tests for restore_feature_flag() API client method."""

    def test_restores_flag(self, oauth_credentials: Session) -> None:
        """restore_feature_flag() sends DELETE to archive endpoint."""
        captured: list[tuple[str, str]] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture method and URL."""
            captured.append((request.method, str(request.url)))
            return httpx.Response(
                200,
                json={"status": "ok", "results": _flag_result()},
            )

        client = create_mock_client(oauth_credentials, handler)
        with client:
            result = client.restore_feature_flag("abc-123")

        assert captured[0][0] == "DELETE"
        assert "/feature-flags/abc-123/archive" in captured[0][1]
        assert result["id"] == "abc-123"


class TestDuplicateFeatureFlag:
    """Tests for duplicate_feature_flag() API client method."""

    def test_duplicates_flag(self, oauth_credentials: Session) -> None:
        """duplicate_feature_flag() sends POST to duplicate endpoint."""
        captured: list[tuple[str, str]] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture method and URL."""
            captured.append((request.method, str(request.url)))
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": _flag_result("dup-456", "Copy of Test", "test_copy"),
                },
            )

        client = create_mock_client(oauth_credentials, handler)
        with client:
            result = client.duplicate_feature_flag("abc-123")

        assert captured[0][0] == "POST"
        assert "/feature-flags/abc-123/duplicate" in captured[0][1]
        assert result["id"] == "dup-456"
        assert result["name"] == "Copy of Test"


# =============================================================================
# Flag Operations Tests
# =============================================================================


class TestSetFlagTestUsers:
    """Tests for set_flag_test_users() API client method."""

    def test_sets_test_users(self, oauth_credentials: Session) -> None:
        """set_flag_test_users() sends PUT with user mappings."""
        captured: list[tuple[str, str, Any]] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture method, URL, and body."""
            captured.append(
                (request.method, str(request.url), json.loads(request.content))
            )
            return httpx.Response(204)

        client = create_mock_client(oauth_credentials, handler)
        with client:
            client.set_flag_test_users(
                "abc-123", {"users": {"on": "user-1", "off": "user-2"}}
            )

        assert captured[0][0] == "PUT"
        assert "/feature-flags/abc-123/test-users" in captured[0][1]
        assert captured[0][2]["users"] == {"on": "user-1", "off": "user-2"}


class TestGetFlagHistory:
    """Tests for get_flag_history() API client method."""

    def test_gets_history(self, oauth_credentials: Session) -> None:
        """get_flag_history() sends GET and returns history response."""
        captured_urls: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture URL and return history."""
            captured_urls.append(str(request.url))
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": {
                        "events": [[1, "created"]],
                        "count": 1,
                    },
                },
            )

        client = create_mock_client(oauth_credentials, handler)
        with client:
            result = client.get_flag_history("abc-123")

        assert "/feature-flags/abc-123/history" in captured_urls[0]
        assert result["events"] == [[1, "created"]]
        assert result["count"] == 1

    def test_with_pagination_params(self, oauth_credentials: Session) -> None:
        """get_flag_history() passes pagination query params."""
        captured_urls: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture URL and return history."""
            captured_urls.append(str(request.url))
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": {"events": [], "count": 0},
                },
            )

        client = create_mock_client(oauth_credentials, handler)
        with client:
            client.get_flag_history(
                "abc-123", params={"page_size": "50", "page": "cursor-abc"}
            )

        url = captured_urls[0]
        assert "page_size=50" in url or "page_size" in url

    def test_uses_get_method(self, oauth_credentials: Session) -> None:
        """get_flag_history() uses GET HTTP method."""
        captured_methods: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture HTTP method."""
            captured_methods.append(request.method)
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": {"events": [], "count": 0},
                },
            )

        client = create_mock_client(oauth_credentials, handler)
        with client:
            client.get_flag_history("abc-123")

        assert captured_methods[0] == "GET"


class TestGetFlagLimits:
    """Tests for get_flag_limits() API client method."""

    def test_gets_limits(self, oauth_credentials: Session) -> None:
        """get_flag_limits() sends GET and returns limits response."""
        captured_urls: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture URL and return limits."""
            captured_urls.append(str(request.url))
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

        client = create_mock_client(oauth_credentials, handler)
        with client:
            result = client.get_flag_limits()

        assert "/feature-flags/limits" in captured_urls[0]
        assert result["limit"] == 100
        assert result["current_usage"] == 42

    def test_uses_get_method(self, oauth_credentials: Session) -> None:
        """get_flag_limits() uses GET HTTP method."""
        captured_methods: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture HTTP method."""
            captured_methods.append(request.method)
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": {
                        "limit": 10,
                        "is_trial": True,
                        "current_usage": 0,
                        "contract_status": "active",
                    },
                },
            )

        client = create_mock_client(oauth_credentials, handler)
        with client:
            client.get_flag_limits()

        assert captured_methods[0] == "GET"

    def test_always_uses_project_scoped_path(self, oauth_credentials: Session) -> None:
        """get_flag_limits() always uses project-scoped path, even with workspace set."""
        captured_urls: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture URL."""
            captured_urls.append(str(request.url))
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": {
                        "limit": 100,
                        "is_trial": False,
                        "current_usage": 0,
                        "contract_status": "active",
                    },
                },
            )

        # Client has workspace_id=100 set, but limits should still be project-scoped
        client = create_mock_client(oauth_credentials, handler)
        with client:
            client.get_flag_limits()

        assert "/projects/12345/feature-flags/limits" in captured_urls[0]
        assert "/workspaces/" not in captured_urls[0]
