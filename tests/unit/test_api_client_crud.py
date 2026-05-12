"""Unit tests for Core Entity CRUD API client methods (Phase 024).

Tests for:
- Dashboard CRUD: list, create, get, update, delete, bulk_delete
- Dashboard advanced: favorite, unfavorite, pin, unpin, remove_report,
  blueprints, RCA, ERF, report_link, text_card
- Bookmark CRUD: list_v2, create, get, update, delete, bulk_delete,
  bulk_update, linked_dashboard_ids, history
- Cohort CRUD: list_app, get, create, update, delete, bulk_delete, bulk_update
"""
# ruff: noqa: ARG001, ARG005

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
# Dashboard CRUD Tests
# =============================================================================


class TestListDashboards:
    """Tests for list_dashboards() API client method."""

    def test_returns_dashboard_list(self, oauth_credentials: Session) -> None:
        """list_dashboards() returns a list of dashboard dicts."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return sample dashboard list."""
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": [
                        {"id": 1, "title": "Dashboard 1"},
                        {"id": 2, "title": "Dashboard 2"},
                    ],
                },
            )

        client = create_mock_client(oauth_credentials, handler)
        with client:
            result = client.list_dashboards()

        assert len(result) == 2
        assert result[0]["id"] == 1
        assert result[1]["title"] == "Dashboard 2"

    def test_filters_by_ids(self, oauth_credentials: Session) -> None:
        """list_dashboards(ids=[1,2]) passes ids as query param."""
        captured_urls: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture URL and return empty list."""
            captured_urls.append(str(request.url))
            return httpx.Response(200, json={"status": "ok", "results": []})

        client = create_mock_client(oauth_credentials, handler)
        with client:
            client.list_dashboards(ids=[1, 2])

        assert "ids=1%2C2" in captured_urls[0] or "ids=1,2" in captured_urls[0]

    def test_uses_maybe_scoped_path(self, oauth_credentials: Session) -> None:
        """list_dashboards() uses maybe_scoped_path for URL building."""
        captured_urls: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture URL."""
            captured_urls.append(str(request.url))
            return httpx.Response(200, json={"status": "ok", "results": []})

        client = create_mock_client(oauth_credentials, handler)
        with client:
            client.list_dashboards()

        assert "/projects/12345/dashboards" in captured_urls[0]

    def test_empty_result(self, oauth_credentials: Session) -> None:
        """list_dashboards() returns empty list when no dashboards."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return empty results."""
            return httpx.Response(200, json={"status": "ok", "results": []})

        client = create_mock_client(oauth_credentials, handler)
        with client:
            result = client.list_dashboards()

        assert result == []


class TestCreateDashboard:
    """Tests for create_dashboard() API client method."""

    def test_creates_dashboard(self, oauth_credentials: Session) -> None:
        """create_dashboard() sends POST and returns dashboard dict."""
        captured: list[tuple[str, Any]] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture request method and body."""
            captured.append((request.method, json.loads(request.content)))
            return httpx.Response(
                200,
                json={"status": "ok", "results": {"id": 1, "title": "New"}},
            )

        client = create_mock_client(oauth_credentials, handler)
        with client:
            result = client.create_dashboard({"title": "New"})

        assert captured[0][0] == "POST"
        assert captured[0][1] == {"title": "New"}
        assert result["id"] == 1


class TestGetDashboard:
    """Tests for get_dashboard() API client method."""

    def test_gets_dashboard_by_id(self, oauth_credentials: Session) -> None:
        """get_dashboard() sends GET with dashboard ID in path."""
        captured_urls: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture URL and return dashboard."""
            captured_urls.append(str(request.url))
            return httpx.Response(
                200,
                json={"status": "ok", "results": {"id": 42, "title": "Test"}},
            )

        client = create_mock_client(oauth_credentials, handler)
        with client:
            result = client.get_dashboard(42)

        assert "/dashboards/42" in captured_urls[0]
        assert result["id"] == 42


class TestUpdateDashboard:
    """Tests for update_dashboard() API client method."""

    def test_updates_dashboard(self, oauth_credentials: Session) -> None:
        """update_dashboard() sends PATCH with body."""
        captured: list[tuple[str, Any]] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture method and body."""
            captured.append((request.method, json.loads(request.content)))
            return httpx.Response(
                200,
                json={"status": "ok", "results": {"id": 1, "title": "Updated"}},
            )

        client = create_mock_client(oauth_credentials, handler)
        with client:
            result = client.update_dashboard(1, {"title": "Updated"})

        assert captured[0][0] == "PATCH"
        assert result["title"] == "Updated"


class TestDeleteDashboard:
    """Tests for delete_dashboard() API client method."""

    def test_deletes_dashboard(self, oauth_credentials: Session) -> None:
        """delete_dashboard() sends DELETE request."""
        captured_methods: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture method."""
            captured_methods.append(request.method)
            return httpx.Response(204)

        client = create_mock_client(oauth_credentials, handler)
        with client:
            client.delete_dashboard(1)

        assert captured_methods[0] == "DELETE"


class TestBulkDeleteDashboards:
    """Tests for bulk_delete_dashboards() API client method."""

    def test_bulk_deletes_dashboards(self, oauth_credentials: Session) -> None:
        """bulk_delete_dashboards() sends POST to bulk-delete with dashboard_ids body."""
        captured: list[tuple[str, str, Any]] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture method, URL, and body."""
            captured.append(
                (request.method, str(request.url), json.loads(request.content))
            )
            return httpx.Response(204)

        client = create_mock_client(oauth_credentials, handler)
        with client:
            client.bulk_delete_dashboards([1, 2, 3])

        assert captured[0][0] == "POST"
        assert "/dashboards/bulk-delete" in captured[0][1]
        assert captured[0][2] == {"dashboard_ids": [1, 2, 3]}


# =============================================================================
# Dashboard Advanced Operations Tests
# =============================================================================


class TestDashboardOrganization:
    """Tests for dashboard favorite, pin, and remove report operations."""

    def test_favorite_dashboard(self, oauth_credentials: Session) -> None:
        """favorite_dashboard() sends PUT to favorite endpoint."""
        captured: list[tuple[str, str]] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture method and URL."""
            captured.append((request.method, str(request.url)))
            return httpx.Response(204)

        client = create_mock_client(oauth_credentials, handler)
        with client:
            client.favorite_dashboard(1)

        assert captured[0][0] == "POST"
        assert "/dashboards/1/favorites" in captured[0][1]

    def test_unfavorite_dashboard(self, oauth_credentials: Session) -> None:
        """unfavorite_dashboard() sends DELETE to favorites endpoint."""
        captured: list[tuple[str, str]] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture method and URL."""
            captured.append((request.method, str(request.url)))
            return httpx.Response(204)

        client = create_mock_client(oauth_credentials, handler)
        with client:
            client.unfavorite_dashboard(1)

        assert captured[0][0] == "DELETE"
        assert "/dashboards/1/favorites" in captured[0][1]

    def test_pin_dashboard(self, oauth_credentials: Session) -> None:
        """pin_dashboard() sends POST to pin endpoint."""
        captured: list[tuple[str, str]] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture method and URL."""
            captured.append((request.method, str(request.url)))
            return httpx.Response(204)

        client = create_mock_client(oauth_credentials, handler)
        with client:
            client.pin_dashboard(1)

        assert captured[0][0] == "POST"
        assert "/dashboards/1/pin" in captured[0][1]

    def test_unpin_dashboard(self, oauth_credentials: Session) -> None:
        """unpin_dashboard() sends DELETE to pin endpoint."""
        captured: list[tuple[str, str]] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture method and URL."""
            captured.append((request.method, str(request.url)))
            return httpx.Response(204)

        client = create_mock_client(oauth_credentials, handler)
        with client:
            client.unpin_dashboard(1)

        assert captured[0][0] == "DELETE"
        assert "/dashboards/1/pin" in captured[0][1]

    def test_remove_report_from_dashboard(self, oauth_credentials: Session) -> None:
        """remove_report_from_dashboard() sends PATCH with content action and returns dashboard."""
        captured: list[tuple[str, str, Any]] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture method, URL, and body."""
            captured.append(
                (request.method, str(request.url), json.loads(request.content))
            )
            return httpx.Response(
                200,
                json={"status": "ok", "results": {"id": 1, "title": "Dash"}},
            )

        client = create_mock_client(oauth_credentials, handler)
        with client:
            result = client.remove_report_from_dashboard(1, 42)

        assert captured[0][0] == "PATCH"
        assert "/dashboards/1" in captured[0][1]
        assert captured[0][2] == {
            "content": {
                "action": "delete",
                "content_type": "report",
                "content_id": 42,
            }
        }
        assert result is not None
        assert result["id"] == 1

    def test_add_report_to_dashboard(self, oauth_credentials: Session) -> None:
        """add_report_to_dashboard() sends PATCH with create action and source_bookmark_id."""
        captured: list[tuple[str, str, Any]] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture method, URL, and body."""
            captured.append(
                (request.method, str(request.url), json.loads(request.content))
            )
            return httpx.Response(
                200,
                json={"status": "ok", "results": {"id": 1, "title": "Dash"}},
            )

        client = create_mock_client(oauth_credentials, handler)
        with client:
            result = client.add_report_to_dashboard(1, 42)

        assert captured[0][0] == "PATCH"
        assert "/dashboards/1" in captured[0][1]
        assert captured[0][2] == {
            "content": {
                "action": "create",
                "content_type": "report",
                "content_params": {"source_bookmark_id": 42},
            }
        }
        assert result is not None
        assert result["id"] == 1


class TestBlueprintOperations:
    """Tests for blueprint API methods."""

    def test_list_blueprint_templates(self, oauth_credentials: Session) -> None:
        """list_blueprint_templates() returns template list."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return templates."""
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": [
                        {"title_key": "onboarding", "description_key": "Get started"}
                    ],
                },
            )

        client = create_mock_client(oauth_credentials, handler)
        with client:
            result = client.list_blueprint_templates()

        assert len(result) == 1
        assert result[0]["title_key"] == "onboarding"

    def test_list_blueprint_templates_with_reports(
        self, oauth_credentials: Session
    ) -> None:
        """list_blueprint_templates(include_reports=True) passes param."""
        captured_urls: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture URL."""
            captured_urls.append(str(request.url))
            return httpx.Response(200, json={"status": "ok", "results": []})

        client = create_mock_client(oauth_credentials, handler)
        with client:
            client.list_blueprint_templates(include_reports=True)

        assert "include_reports=true" in captured_urls[0]

    def test_list_blueprint_templates_dict_of_dicts(
        self, oauth_credentials: Session
    ) -> None:
        """list_blueprint_templates() converts dict-of-dicts to list with name."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return templates in dict-of-dicts format."""
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": {
                        "templates": {
                            "onboarding": {"title_key": "Get Started", "reports": []},
                            "marketing": {"title_key": "Marketing KPIs"},
                        }
                    },
                },
            )

        client = create_mock_client(oauth_credentials, handler)
        with client:
            result = client.list_blueprint_templates()

        assert len(result) == 2
        names = {t["name"] for t in result}
        assert names == {"onboarding", "marketing"}
        onboarding = next(t for t in result if t["name"] == "onboarding")
        assert onboarding["title_key"] == "Get Started"

    def test_update_blueprint_cohorts(self, oauth_credentials: Session) -> None:
        """update_blueprint_cohorts() sends PUT with cohort mappings."""
        captured: list[Any] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture body."""
            captured.append(json.loads(request.content))
            return httpx.Response(204)

        client = create_mock_client(oauth_credentials, handler)
        with client:
            client.update_blueprint_cohorts(
                [{"placeholder": "new_users", "cohort_id": 42}]
            )

        assert captured[0] == {
            "cohorts": [{"placeholder": "new_users", "cohort_id": 42}]
        }

    def test_create_blueprint(self, oauth_credentials: Session) -> None:
        """create_blueprint() sends POST with template_type."""
        captured: list[Any] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture body."""
            captured.append(json.loads(request.content))
            return httpx.Response(
                200,
                json={"status": "ok", "results": {"id": 1, "title": "Blueprint"}},
            )

        client = create_mock_client(oauth_credentials, handler)
        with client:
            result = client.create_blueprint("onboarding")

        assert captured[0] == {"template_type": "onboarding"}
        assert result["id"] == 1

    def test_get_blueprint_config(self, oauth_credentials: Session) -> None:
        """get_blueprint_config() returns config dict."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return config."""
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": {"variables": {"event": "Signup"}},
                },
            )

        client = create_mock_client(oauth_credentials, handler)
        with client:
            result = client.get_blueprint_config(1)

        assert result["variables"]["event"] == "Signup"

    def test_finalize_blueprint(self, oauth_credentials: Session) -> None:
        """finalize_blueprint() sends POST and returns dashboard."""
        captured: list[Any] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture body."""
            captured.append(json.loads(request.content))
            return httpx.Response(
                200,
                json={"status": "ok", "results": {"id": 1, "title": "Finalized"}},
            )

        client = create_mock_client(oauth_credentials, handler)
        with client:
            result = client.finalize_blueprint(
                {"dashboard_id": 1, "cards": [{"type": "report"}]}
            )

        assert captured[0]["dashboard_id"] == 1
        assert result["title"] == "Finalized"


class TestDashboardAdvanced:
    """Tests for RCA, ERF, report link, and text card operations."""

    def test_create_rca_dashboard(self, oauth_credentials: Session) -> None:
        """create_rca_dashboard() sends POST and returns dashboard."""
        captured: list[Any] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture body."""
            captured.append(json.loads(request.content))
            return httpx.Response(
                200,
                json={"status": "ok", "results": {"id": 99, "title": "RCA"}},
            )

        client = create_mock_client(oauth_credentials, handler)
        with client:
            result = client.create_rca_dashboard(
                {"rca_source_id": 42, "rca_source_data": {"type": "anomaly"}}
            )

        assert captured[0]["rca_source_id"] == 42
        assert result["id"] == 99

    def test_get_bookmark_dashboard_ids(self, oauth_credentials: Session) -> None:
        """get_bookmark_dashboard_ids() returns list of int IDs."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return ID list."""
            return httpx.Response(
                200,
                json={"status": "ok", "results": [1, 2, 3]},
            )

        client = create_mock_client(oauth_credentials, handler)
        with client:
            result = client.get_bookmark_dashboard_ids(42)

        assert result == [1, 2, 3]

    def test_get_dashboard_erf(self, oauth_credentials: Session) -> None:
        """get_dashboard_erf() returns ERF metrics dict."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return ERF data."""
            return httpx.Response(
                200,
                json={"status": "ok", "results": {"metrics": []}},
            )

        client = create_mock_client(oauth_credentials, handler)
        with client:
            result = client.get_dashboard_erf(1)

        assert "metrics" in result

    def test_update_report_link(self, oauth_credentials: Session) -> None:
        """update_report_link() sends PATCH to correct endpoint."""
        captured: list[tuple[str, str, Any]] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture method, URL, and body."""
            captured.append(
                (request.method, str(request.url), json.loads(request.content))
            )
            return httpx.Response(204)

        client = create_mock_client(oauth_credentials, handler)
        with client:
            client.update_report_link(1, 42, {"type": "embedded"})

        assert captured[0][0] == "PATCH"
        assert "/dashboards/1/report-links/42" in captured[0][1]
        assert captured[0][2] == {"type": "embedded"}

    def test_update_text_card(self, oauth_credentials: Session) -> None:
        """update_text_card() sends PATCH to correct endpoint."""
        captured: list[tuple[str, str, Any]] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture method, URL, and body."""
            captured.append(
                (request.method, str(request.url), json.loads(request.content))
            )
            return httpx.Response(204)

        client = create_mock_client(oauth_credentials, handler)
        with client:
            client.update_text_card(1, 99, {"markdown": "# Hello"})

        assert captured[0][0] == "PATCH"
        assert "/dashboards/1/text-cards/99" in captured[0][1]
        assert captured[0][2] == {"markdown": "# Hello"}


# =============================================================================
# Bookmark/Report CRUD Tests
# =============================================================================


class TestListBookmarksV2:
    """Tests for list_bookmarks_v2() API client method."""

    def test_returns_bookmark_list(self, oauth_credentials: Session) -> None:
        """list_bookmarks_v2() returns list of bookmark dicts."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return bookmarks."""
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": [
                        {"id": 1, "name": "Report 1", "type": "insights"},
                        {"id": 2, "name": "Report 2", "type": "funnels"},
                    ],
                },
            )

        client = create_mock_client(oauth_credentials, handler)
        with client:
            result = client.list_bookmarks_v2()

        assert len(result) == 2
        assert result[0]["name"] == "Report 1"

    def test_filters_by_type(self, oauth_credentials: Session) -> None:
        """list_bookmarks_v2(bookmark_type='funnels') passes type param."""
        captured_urls: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture URL."""
            captured_urls.append(str(request.url))
            return httpx.Response(200, json={"status": "ok", "results": []})

        client = create_mock_client(oauth_credentials, handler)
        with client:
            client.list_bookmarks_v2(bookmark_type="funnels")

        assert "type=funnels" in captured_urls[0]

    def test_filters_by_ids(self, oauth_credentials: Session) -> None:
        """list_bookmarks_v2(ids=[1,2]) passes ids as query param."""
        captured_urls: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture URL."""
            captured_urls.append(str(request.url))
            return httpx.Response(200, json={"status": "ok", "results": []})

        client = create_mock_client(oauth_credentials, handler)
        with client:
            client.list_bookmarks_v2(ids=[10, 20])

        assert "ids=" in captured_urls[0]


class TestBookmarkCRUD:
    """Tests for bookmark create, get, update, delete operations."""

    def test_create_bookmark(self, oauth_credentials: Session) -> None:
        """create_bookmark() sends POST and returns bookmark dict."""
        captured: list[Any] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture body."""
            captured.append(json.loads(request.content))
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": {"id": 1, "name": "New Report", "type": "insights"},
                },
            )

        client = create_mock_client(oauth_credentials, handler)
        with client:
            result = client.create_bookmark(
                {"name": "New Report", "type": "insights", "params": {}}
            )

        assert result["id"] == 1
        assert captured[0]["name"] == "New Report"

    def test_get_bookmark(self, oauth_credentials: Session) -> None:
        """get_bookmark() sends GET with bookmark ID in path."""
        captured_urls: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture URL."""
            captured_urls.append(str(request.url))
            return httpx.Response(
                200,
                json={"status": "ok", "results": {"id": 42, "name": "Test"}},
            )

        client = create_mock_client(oauth_credentials, handler)
        with client:
            result = client.get_bookmark(42)

        assert "/bookmarks/42" in captured_urls[0]
        assert result["id"] == 42

    def test_update_bookmark(self, oauth_credentials: Session) -> None:
        """update_bookmark() sends PATCH with body."""
        captured: list[tuple[str, Any]] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture method and body."""
            captured.append((request.method, json.loads(request.content)))
            return httpx.Response(
                200,
                json={"status": "ok", "results": {"id": 1, "name": "Updated"}},
            )

        client = create_mock_client(oauth_credentials, handler)
        with client:
            result = client.update_bookmark(1, {"name": "Updated"})

        assert captured[0][0] == "PATCH"
        assert result["name"] == "Updated"

    def test_delete_bookmark(self, oauth_credentials: Session) -> None:
        """delete_bookmark() sends DELETE request."""
        captured_methods: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture method."""
            captured_methods.append(request.method)
            return httpx.Response(204)

        client = create_mock_client(oauth_credentials, handler)
        with client:
            client.delete_bookmark(1)

        assert captured_methods[0] == "DELETE"

    def test_bulk_delete_bookmarks(self, oauth_credentials: Session) -> None:
        """bulk_delete_bookmarks() sends POST to bulk-delete with bookmark_ids body."""
        captured: list[tuple[str, str, Any]] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture method, URL, and body."""
            captured.append(
                (request.method, str(request.url), json.loads(request.content))
            )
            return httpx.Response(204)

        client = create_mock_client(oauth_credentials, handler)
        with client:
            client.bulk_delete_bookmarks([1, 2])

        assert captured[0][0] == "POST"
        assert "/bookmarks/bulk-delete" in captured[0][1]
        assert captured[0][2] == {"bookmark_ids": [1, 2]}

    def test_bulk_update_bookmarks(self, oauth_credentials: Session) -> None:
        """bulk_update_bookmarks() sends PATCH with entries."""
        captured: list[Any] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture body."""
            captured.append(json.loads(request.content))
            return httpx.Response(204)

        client = create_mock_client(oauth_credentials, handler)
        with client:
            client.bulk_update_bookmarks([{"id": 1, "name": "Renamed"}])

        assert captured[0] == {"bookmarks": [{"id": 1, "name": "Renamed"}]}

    def test_bookmark_linked_dashboard_ids(self, oauth_credentials: Session) -> None:
        """bookmark_linked_dashboard_ids() returns list of dashboard IDs."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return ID list."""
            return httpx.Response(200, json={"status": "ok", "results": [10, 20, 30]})

        client = create_mock_client(oauth_credentials, handler)
        with client:
            result = client.bookmark_linked_dashboard_ids(1)

        assert result == [10, 20, 30]

    def test_get_bookmark_history(self, oauth_credentials: Session) -> None:
        """get_bookmark_history() returns history response."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return history."""
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": {
                        "results": [{"action": "created"}],
                        "pagination": {"page_size": 20},
                    },
                },
            )

        client = create_mock_client(oauth_credentials, handler)
        with client:
            result = client.get_bookmark_history(1)

        assert "results" in result

    def test_get_bookmark_history_with_pagination(
        self, oauth_credentials: Session
    ) -> None:
        """get_bookmark_history() passes cursor and page_size params."""
        captured_urls: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture URL."""
            captured_urls.append(str(request.url))
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": {"results": [], "pagination": {"page_size": 10}},
                },
            )

        client = create_mock_client(oauth_credentials, handler)
        with client:
            client.get_bookmark_history(1, cursor="abc", page_size=10)

        assert "cursor=abc" in captured_urls[0]
        assert "page_size=10" in captured_urls[0]

    def test_get_bookmark_history_preserves_pagination(
        self, oauth_credentials: Session
    ) -> None:
        """get_bookmark_history() preserves pagination data from API response."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return history with pagination cursor."""
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": {
                        "results": [{"action": "created"}],
                        "pagination": {
                            "page_size": 10,
                            "next_cursor": "cursor_abc",
                            "previous_cursor": None,
                        },
                    },
                },
            )

        client = create_mock_client(oauth_credentials, handler)
        with client:
            result = client.get_bookmark_history(1)

        assert result["pagination"] is not None
        assert result["pagination"]["next_cursor"] == "cursor_abc"
        assert result["pagination"]["page_size"] == 10


# =============================================================================
# Cohort CRUD Tests
# =============================================================================


class TestListCohortsApp:
    """Tests for list_cohorts_app() API client method."""

    def test_returns_cohort_list(self, oauth_credentials: Session) -> None:
        """list_cohorts_app() returns list of cohort dicts."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return cohorts."""
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": [
                        {"id": 1, "name": "Power Users"},
                        {"id": 2, "name": "Churned"},
                    ],
                },
            )

        client = create_mock_client(oauth_credentials, handler)
        with client:
            result = client.list_cohorts_app()

        assert len(result) == 2
        assert result[0]["name"] == "Power Users"

    def test_filters_by_data_group_id(self, oauth_credentials: Session) -> None:
        """list_cohorts_app(data_group_id='abc') passes param."""
        captured_urls: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture URL."""
            captured_urls.append(str(request.url))
            return httpx.Response(200, json={"status": "ok", "results": []})

        client = create_mock_client(oauth_credentials, handler)
        with client:
            client.list_cohorts_app(data_group_id="abc")

        assert "data_group_id=abc" in captured_urls[0]

    def test_filters_by_ids(self, oauth_credentials: Session) -> None:
        """list_cohorts_app(ids=[1,2]) passes ids param."""
        captured_urls: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture URL."""
            captured_urls.append(str(request.url))
            return httpx.Response(200, json={"status": "ok", "results": []})

        client = create_mock_client(oauth_credentials, handler)
        with client:
            client.list_cohorts_app(ids=[1, 2])

        assert "ids=" in captured_urls[0]


class TestCohortCRUD:
    """Tests for cohort create, get, update, delete operations."""

    def test_get_cohort(self, oauth_credentials: Session) -> None:
        """get_cohort() sends GET with cohort ID in path."""
        captured_urls: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture URL."""
            captured_urls.append(str(request.url))
            return httpx.Response(
                200,
                json={"status": "ok", "results": {"id": 42, "name": "Test"}},
            )

        client = create_mock_client(oauth_credentials, handler)
        with client:
            result = client.get_cohort(42)

        assert "/cohorts/42" in captured_urls[0]
        assert result["id"] == 42

    def test_create_cohort(self, oauth_credentials: Session) -> None:
        """create_cohort() sends POST and returns cohort dict."""
        captured: list[Any] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture body."""
            captured.append(json.loads(request.content))
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": {"id": 1, "name": "New Cohort"},
                },
            )

        client = create_mock_client(oauth_credentials, handler)
        with client:
            result = client.create_cohort({"name": "New Cohort"})

        assert result["id"] == 1
        assert captured[0]["name"] == "New Cohort"

    def test_update_cohort(self, oauth_credentials: Session) -> None:
        """update_cohort() sends PATCH with body."""
        captured: list[tuple[str, Any]] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture method and body."""
            captured.append((request.method, json.loads(request.content)))
            return httpx.Response(
                200,
                json={"status": "ok", "results": {"id": 1, "name": "Updated"}},
            )

        client = create_mock_client(oauth_credentials, handler)
        with client:
            result = client.update_cohort(1, {"name": "Updated"})

        assert captured[0][0] == "PATCH"
        assert result["name"] == "Updated"

    def test_delete_cohort(self, oauth_credentials: Session) -> None:
        """delete_cohort() sends DELETE request."""
        captured_methods: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture method."""
            captured_methods.append(request.method)
            return httpx.Response(204)

        client = create_mock_client(oauth_credentials, handler)
        with client:
            client.delete_cohort(1)

        assert captured_methods[0] == "DELETE"

    def test_bulk_delete_cohorts(self, oauth_credentials: Session) -> None:
        """bulk_delete_cohorts() sends POST to bulk-delete with cohort_ids body."""
        captured: list[tuple[str, str, Any]] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture method, URL, and body."""
            captured.append(
                (request.method, str(request.url), json.loads(request.content))
            )
            return httpx.Response(204)

        client = create_mock_client(oauth_credentials, handler)
        with client:
            client.bulk_delete_cohorts([1, 2])

        assert captured[0][0] == "POST"
        assert "/cohorts/bulk-delete" in captured[0][1]
        assert captured[0][2] == {"cohort_ids": [1, 2]}

    def test_bulk_update_cohorts(self, oauth_credentials: Session) -> None:
        """bulk_update_cohorts() sends PATCH with entries."""
        captured: list[Any] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture body."""
            captured.append(json.loads(request.content))
            return httpx.Response(204)

        client = create_mock_client(oauth_credentials, handler)
        with client:
            client.bulk_update_cohorts([{"id": 1, "name": "Renamed"}])

        assert captured[0] == {"cohorts": [{"id": 1, "name": "Renamed"}]}
