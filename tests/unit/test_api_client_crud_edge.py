"""Edge case tests for Phase 024 API client CRUD methods.

Tests for:
- app_request() response unwrapping (Bug B1)
- List method response handling after unwrapping
- Silent error swallowing on non-dict results (Bug B2)
- Duplicate bookmark/dashboard lookup methods (Bug B6)
- Void operation (204) responses
- Error propagation through CRUD methods
- Workspace-scoped path construction
"""
# ruff: noqa: ARG001, ARG005

from __future__ import annotations

from collections.abc import Callable

import httpx
import pytest

from mixpanel_headless._internal.api_client import MixpanelAPIClient
from mixpanel_headless._internal.auth.session import Session
from mixpanel_headless.exceptions import (
    AuthenticationError,
    MixpanelHeadlessError,
    QueryError,
)
from tests.conftest import make_session

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def oauth_credentials() -> Session:
    """Create OAuth credentials for App API testing."""
    return make_session(project_id="12345", region="us", oauth_token="test-token")


def create_mock_client(
    credentials: Session,
    handler: Callable[[httpx.Request], httpx.Response],
) -> MixpanelAPIClient:
    """Create a client with mock transport.

    Args:
        credentials: Authentication credentials.
        handler: Mock HTTP handler function.

    Returns:
        MixpanelAPIClient configured with mock transport.
    """
    transport = httpx.MockTransport(handler)
    return MixpanelAPIClient(session=credentials, _transport=transport)


# =============================================================================
# Bug B1: app_request() unwrapping behavior
# =============================================================================


class TestAppRequestUnwrapping:
    """Test app_request() result-unwrapping for various response shapes."""

    def test_unwraps_results_list(self, oauth_credentials: Session) -> None:
        """app_request() unwraps a list from the results key."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return response with list results."""
            return httpx.Response(200, json={"status": "ok", "results": [1, 2, 3]})

        client = create_mock_client(oauth_credentials, handler)
        with client:
            result = client.app_request("GET", "/projects/12345/test")

        assert result == [1, 2, 3]

    def test_unwraps_results_dict(self, oauth_credentials: Session) -> None:
        """app_request() unwraps a dict from the results key."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return response with dict results."""
            return httpx.Response(200, json={"status": "ok", "results": {"id": 1}})

        client = create_mock_client(oauth_credentials, handler)
        with client:
            result = client.app_request("GET", "/projects/12345/test")

        assert result == {"id": 1}

    def test_no_results_key_returns_full_body(self, oauth_credentials: Session) -> None:
        """app_request() returns the full body when no results key is present."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return response without a results key."""
            return httpx.Response(200, json={"data": "x"})

        client = create_mock_client(oauth_credentials, handler)
        with client:
            result = client.app_request("GET", "/projects/12345/test")

        assert result == {"data": "x"}

    def test_204_returns_status_ok(self, oauth_credentials: Session) -> None:
        """app_request() returns status-ok dict for 204 No Content."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return 204 No Content response."""
            return httpx.Response(204)

        client = create_mock_client(oauth_credentials, handler)
        with client:
            result = client.app_request("DELETE", "/projects/12345/test")

        assert result == {"status": "ok"}


# =============================================================================
# Bug B1: List methods always receive unwrapped lists
# =============================================================================


class TestListMethodResponseHandling:
    """Test that list methods receive already-unwrapped lists from app_request()."""

    def test_list_dashboards_returns_unwrapped_list(
        self, oauth_credentials: Session
    ) -> None:
        """list_dashboards() returns the unwrapped list directly."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return dashboards wrapped in results."""
            return httpx.Response(200, json={"status": "ok", "results": [{"id": 1}]})

        client = create_mock_client(oauth_credentials, handler)
        with client:
            result = client.list_dashboards()

        assert result == [{"id": 1}]

    def test_list_dashboards_empty(self, oauth_credentials: Session) -> None:
        """list_dashboards() returns empty list for empty results."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return empty results list."""
            return httpx.Response(200, json={"status": "ok", "results": []})

        client = create_mock_client(oauth_credentials, handler)
        with client:
            result = client.list_dashboards()

        assert result == []

    def test_list_bookmarks_v2_returns_unwrapped_list(
        self, oauth_credentials: Session
    ) -> None:
        """list_bookmarks_v2() returns the unwrapped list directly."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return bookmarks wrapped in results."""
            return httpx.Response(
                200,
                json={"status": "ok", "results": [{"id": 10, "name": "Report"}]},
            )

        client = create_mock_client(oauth_credentials, handler)
        with client:
            result = client.list_bookmarks_v2()

        assert result == [{"id": 10, "name": "Report"}]

    def test_list_cohorts_app_returns_unwrapped_list(
        self, oauth_credentials: Session
    ) -> None:
        """list_cohorts_app() returns the unwrapped list directly."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return cohorts wrapped in results."""
            return httpx.Response(
                200,
                json={"status": "ok", "results": [{"id": 5, "name": "Power Users"}]},
            )

        client = create_mock_client(oauth_credentials, handler)
        with client:
            result = client.list_cohorts_app()

        assert result == [{"id": 5, "name": "Power Users"}]

    def test_list_blueprint_templates_returns_unwrapped_list(
        self, oauth_credentials: Session
    ) -> None:
        """list_blueprint_templates() returns the unwrapped list directly."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return blueprint templates wrapped in results."""
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": [{"template_type": "company_kpis"}],
                },
            )

        client = create_mock_client(oauth_credentials, handler)
        with client:
            result = client.list_blueprint_templates()

        assert result == [{"template_type": "company_kpis"}]

    def test_list_blueprint_templates_skips_non_dict_entries(
        self, oauth_credentials: Session
    ) -> None:
        """list_blueprint_templates() logs warning for non-dict template entries."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return templates with mixed types."""
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": {
                        "templates": {
                            "valid": {"title_key": "OK"},
                            "invalid_string": "not a dict",
                            "invalid_none": None,
                        }
                    },
                },
            )

        client = create_mock_client(oauth_credentials, handler)
        with client:
            result = client.list_blueprint_templates()

        # Only the valid dict entry should be returned
        assert len(result) == 1
        assert result[0]["name"] == "valid"
        assert result[0]["title_key"] == "OK"

    def test_list_dashboards_non_list_raises(self, oauth_credentials: Session) -> None:
        """list_dashboards() raises MixpanelHeadlessError when response is not a list."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return a string instead of list to test type validation."""
            return httpx.Response(200, json={"status": "ok", "results": "unexpected"})

        client = create_mock_client(oauth_credentials, handler)
        with client, pytest.raises(MixpanelHeadlessError, match="expected list"):
            client.list_dashboards()


# =============================================================================
# Bug B2: Response type validation (previously silent error swallowing)
# =============================================================================


class TestResponseTypeValidation:
    """Test methods that validate response types and raise on unexpected formats."""

    def test_create_dashboard_returns_dict(self, oauth_credentials: Session) -> None:
        """create_dashboard() returns unwrapped dict for normal response."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return created dashboard wrapped in results."""
            return httpx.Response(
                200,
                json={"status": "ok", "results": {"id": 1, "title": "X"}},
            )

        client = create_mock_client(oauth_credentials, handler)
        with client:
            result = client.create_dashboard({"title": "X"})

        assert result == {"id": 1, "title": "X"}

    def test_get_dashboard_returns_dict(self, oauth_credentials: Session) -> None:
        """get_dashboard() returns unwrapped dict for normal response."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return dashboard wrapped in results."""
            return httpx.Response(
                200,
                json={"status": "ok", "results": {"id": 42, "title": "My Dash"}},
            )

        client = create_mock_client(oauth_credentials, handler)
        with client:
            result = client.get_dashboard(42)

        assert result == {"id": 42, "title": "My Dash"}

    def test_create_bookmark_returns_dict(self, oauth_credentials: Session) -> None:
        """create_bookmark() returns unwrapped dict for normal response."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return created bookmark wrapped in results."""
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": {"id": 99, "name": "DAU", "type": "insights"},
                },
            )

        client = create_mock_client(oauth_credentials, handler)
        with client:
            result = client.create_bookmark(
                {"name": "DAU", "type": "insights", "params": {}}
            )

        assert result == {"id": 99, "name": "DAU", "type": "insights"}

    def test_get_cohort_returns_dict(self, oauth_credentials: Session) -> None:
        """get_cohort() returns unwrapped dict for normal response."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return cohort wrapped in results."""
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": {"id": 7, "name": "Churned"},
                },
            )

        client = create_mock_client(oauth_credentials, handler)
        with client:
            result = client.get_cohort(7)

        assert result == {"id": 7, "name": "Churned"}

    def test_bookmark_linked_ids_returns_list(self, oauth_credentials: Session) -> None:
        """bookmark_linked_dashboard_ids() returns list when results is a list."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return list of dashboard IDs wrapped in results."""
            return httpx.Response(200, json={"status": "ok", "results": [1, 2]})

        client = create_mock_client(oauth_credentials, handler)
        with client:
            result = client.bookmark_linked_dashboard_ids(42)

        assert result == [1, 2]

    def test_create_dashboard_non_dict_raises(self, oauth_credentials: Session) -> None:
        """create_dashboard() raises MixpanelHeadlessError when response is not a dict."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return a list instead of dict to test type validation."""
            return httpx.Response(200, json={"status": "ok", "results": [1, 2]})

        client = create_mock_client(oauth_credentials, handler)
        with client, pytest.raises(MixpanelHeadlessError, match="expected dict"):
            client.create_dashboard({"title": "X"})

    def test_get_bookmark_non_dict_raises(self, oauth_credentials: Session) -> None:
        """get_bookmark() raises MixpanelHeadlessError when response is not a dict."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return a list instead of dict to test type validation."""
            return httpx.Response(200, json={"status": "ok", "results": [1, 2]})

        client = create_mock_client(oauth_credentials, handler)
        with client, pytest.raises(MixpanelHeadlessError, match="expected dict"):
            client.get_bookmark(42)

    def test_bookmark_linked_ids_non_list_raises(
        self, oauth_credentials: Session
    ) -> None:
        """bookmark_linked_dashboard_ids() raises when response is not a list."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return a dict instead of list to test type validation."""
            return httpx.Response(200, json={"status": "ok", "results": {"id": 1}})

        client = create_mock_client(oauth_credentials, handler)
        with client, pytest.raises(MixpanelHeadlessError, match="expected list"):
            client.bookmark_linked_dashboard_ids(42)


# =============================================================================
# Bug B6: Duplicate bookmark/dashboard lookup methods
# =============================================================================


class TestDuplicateBookmarkDashboardMethods:
    """Test both get_bookmark_dashboard_ids() and bookmark_linked_dashboard_ids()."""

    def test_get_bookmark_dashboard_ids_path(self, oauth_credentials: Session) -> None:
        """get_bookmark_dashboard_ids() hits /dashboards/bookmark/{id}."""
        captured_urls: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture URL and return list results."""
            captured_urls.append(str(request.url))
            return httpx.Response(200, json={"status": "ok", "results": [1]})

        client = create_mock_client(oauth_credentials, handler)
        with client:
            client.get_bookmark_dashboard_ids(42)

        assert "/dashboards/bookmarks/42/dashboard-ids" in captured_urls[0]

    def test_bookmark_linked_dashboard_ids_path(
        self, oauth_credentials: Session
    ) -> None:
        """bookmark_linked_dashboard_ids() hits /bookmarks/{id}/dashboards."""
        captured_urls: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture URL and return list results."""
            captured_urls.append(str(request.url))
            return httpx.Response(200, json={"status": "ok", "results": [1]})

        client = create_mock_client(oauth_credentials, handler)
        with client:
            client.bookmark_linked_dashboard_ids(42)

        assert "/bookmarks/42/linked-dashboard-ids" in captured_urls[0]

    def test_both_return_list_of_ints(self, oauth_credentials: Session) -> None:
        """Both methods return the same list of ints for identical mock data."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return list of dashboard IDs wrapped in results."""
            return httpx.Response(200, json={"status": "ok", "results": [1, 2, 3]})

        client = create_mock_client(oauth_credentials, handler)
        with client:
            result_a = client.get_bookmark_dashboard_ids(42)
            result_b = client.bookmark_linked_dashboard_ids(42)

        assert result_a == [1, 2, 3]
        assert result_b == [1, 2, 3]

    def test_both_handle_empty_results(self, oauth_credentials: Session) -> None:
        """Both methods return empty list for empty results."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return empty list wrapped in results."""
            return httpx.Response(200, json={"status": "ok", "results": []})

        client = create_mock_client(oauth_credentials, handler)
        with client:
            result_a = client.get_bookmark_dashboard_ids(42)
            result_b = client.bookmark_linked_dashboard_ids(42)

        assert result_a == []
        assert result_b == []


# =============================================================================
# Void operations (204 No Content)
# =============================================================================


class TestVoidOperationResponses:
    """Test that void operations handle 204 No Content without errors."""

    def test_delete_dashboard_204(self, oauth_credentials: Session) -> None:
        """delete_dashboard() succeeds silently on 204."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return 204 No Content."""
            return httpx.Response(204)

        client = create_mock_client(oauth_credentials, handler)
        with client:
            client.delete_dashboard(1)  # Should not raise

    def test_favorite_dashboard_204(self, oauth_credentials: Session) -> None:
        """favorite_dashboard() succeeds silently on 204."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return 204 No Content."""
            return httpx.Response(204)

        client = create_mock_client(oauth_credentials, handler)
        with client:
            client.favorite_dashboard(1)  # Should not raise

    def test_bulk_delete_dashboards_204(self, oauth_credentials: Session) -> None:
        """bulk_delete_dashboards() succeeds silently on 204."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return 204 No Content."""
            return httpx.Response(204)

        client = create_mock_client(oauth_credentials, handler)
        with client:
            client.bulk_delete_dashboards([1, 2, 3])  # Should not raise


# =============================================================================
# Error propagation
# =============================================================================


class TestErrorPropagation:
    """Test that API errors propagate correctly through CRUD methods."""

    def test_list_dashboards_401(self, oauth_credentials: Session) -> None:
        """list_dashboards() raises AuthenticationError on 401."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return 401 Unauthorized."""
            return httpx.Response(401, json={"error": "Unauthorized"})

        client = create_mock_client(oauth_credentials, handler)
        with client, pytest.raises(AuthenticationError):
            client.list_dashboards()

    def test_create_bookmark_400(self, oauth_credentials: Session) -> None:
        """create_bookmark() raises QueryError on 400."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return 400 Bad Request with error body."""
            return httpx.Response(400, json={"error": "Invalid bookmark type"})

        client = create_mock_client(oauth_credentials, handler)
        with client, pytest.raises(QueryError):
            client.create_bookmark({"name": "Bad", "type": "invalid"})

    def test_get_cohort_404(self, oauth_credentials: Session) -> None:
        """get_cohort() raises QueryError on 404."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return 404 Not Found."""
            return httpx.Response(404, json={"error": "Not found"})

        client = create_mock_client(oauth_credentials, handler)
        with client, pytest.raises(QueryError):
            client.get_cohort(999999)


# =============================================================================
# Workspace-scoped paths
# =============================================================================


class TestWorkspaceScopedPaths:
    """Test that CRUD methods build correct project- or workspace-scoped paths."""

    def test_list_dashboards_project_scoped(self, oauth_credentials: Session) -> None:
        """list_dashboards() uses project-scoped path when no workspace set."""
        captured_urls: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture URL and return empty results."""
            captured_urls.append(str(request.url))
            return httpx.Response(200, json={"status": "ok", "results": []})

        client = create_mock_client(oauth_credentials, handler)
        with client:
            client.list_dashboards()

        assert "/projects/12345/dashboards" in captured_urls[0]

    def test_list_dashboards_workspace_scoped(self, oauth_credentials: Session) -> None:
        """list_dashboards() uses workspace-scoped path when workspace is set."""
        captured_urls: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture URL and return empty results."""
            captured_urls.append(str(request.url))
            return httpx.Response(200, json={"status": "ok", "results": []})

        client = create_mock_client(oauth_credentials, handler)
        client.set_workspace_id(789)
        with client:
            client.list_dashboards()

        assert "/workspaces/789/dashboards" in captured_urls[0]

    def test_list_bookmarks_v2_project_scoped(self, oauth_credentials: Session) -> None:
        """list_bookmarks_v2() uses project-scoped path with bookmarks."""
        captured_urls: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture URL and return empty results."""
            captured_urls.append(str(request.url))
            return httpx.Response(200, json={"status": "ok", "results": []})

        client = create_mock_client(oauth_credentials, handler)
        with client:
            client.list_bookmarks_v2()

        assert "/projects/12345/bookmarks" in captured_urls[0]

    def test_list_cohorts_app_project_scoped(self, oauth_credentials: Session) -> None:
        """list_cohorts_app() uses project-scoped path with cohorts."""
        captured_urls: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture URL and return empty results."""
            captured_urls.append(str(request.url))
            return httpx.Response(200, json={"status": "ok", "results": []})

        client = create_mock_client(oauth_credentials, handler)
        with client:
            client.list_cohorts_app()

        assert "/projects/12345/cohorts" in captured_urls[0]
