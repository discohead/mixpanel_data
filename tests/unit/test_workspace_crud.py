"""Unit tests for Workspace CRUD methods (Phase 024).

Tests for dashboard, bookmark, and cohort CRUD operations on the Workspace
facade. Each method delegates to MixpanelAPIClient and returns typed objects.

Verifies:
- Dashboard CRUD: list, create, get, update, delete, bulk_delete
- Bookmark CRUD: list, create, get, update, delete, bulk_delete, bulk_update,
  linked_dashboard_ids, history
- Cohort CRUD: list, create, get, update, delete, bulk_delete, bulk_update
"""

# ruff: noqa: ARG001, ARG005

from __future__ import annotations

from pathlib import Path
from typing import Any

import httpx
import pytest
from pydantic import SecretStr

from mixpanel_data._internal.api_client import MixpanelAPIClient
from mixpanel_data._internal.auth.account import ServiceAccount
from mixpanel_data._internal.auth.session import Project, Session
from mixpanel_data.exceptions import BookmarkValidationError, MixpanelDataError
from mixpanel_data.types import (
    Bookmark,
    BookmarkHistoryResponse,
    BulkUpdateBookmarkEntry,
    BulkUpdateCohortEntry,
    Cohort,
    CreateBookmarkParams,
    CreateCohortParams,
    CreateDashboardParams,
    Dashboard,
    UpdateBookmarkParams,
    UpdateCohortParams,
    UpdateDashboardParams,
)
from mixpanel_data.workspace import Workspace
from tests.conftest import make_session
from tests.unit._bookmark_fixtures import (
    MINIMAL_FUNNEL_PARAMS,
    MINIMAL_INSIGHTS_PARAMS,
)

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
    return Workspace(
        session=_TEST_SESSION,
        _api_client=client,
    )


# =============================================================================
# Mock response data
# =============================================================================


def _dashboard_json(
    id: int = 1,
    title: str = "Test Dashboard",
) -> dict[str, Any]:
    """Return a minimal dashboard dict matching the API shape.

    Args:
        id: Dashboard ID.
        title: Dashboard title.

    Returns:
        Dict that can be parsed into a Dashboard model.
    """
    return {
        "id": id,
        "title": title,
        "is_private": False,
        "is_restricted": False,
        "is_favorited": False,
        "can_update_basic": True,
        "can_share": True,
        "can_view": True,
        "can_update_restricted": False,
        "can_update_visibility": False,
        "is_superadmin": False,
        "allow_staff_override": False,
        "can_pin": True,
        "is_shared_with_project": True,
        "ancestors": [],
    }


def _bookmark_json(
    id: int = 1,
    name: str = "Test Bookmark",
    bookmark_type: str = "insights",
) -> dict[str, Any]:
    """Return a minimal bookmark dict matching the API shape.

    Args:
        id: Bookmark ID.
        name: Bookmark name.
        bookmark_type: Report type (sent as ``"type"`` in the API).

    Returns:
        Dict that can be parsed into a Bookmark model.
    """
    return {
        "id": id,
        "name": name,
        "type": bookmark_type,
        "params": {"events": []},
    }


def _cohort_json(
    id: int = 1,
    name: str = "Test Cohort",
) -> dict[str, Any]:
    """Return a minimal cohort dict matching the API shape.

    Args:
        id: Cohort ID.
        name: Cohort name.

    Returns:
        Dict that can be parsed into a Cohort model.
    """
    return {
        "id": id,
        "name": name,
        "count": 100,
        "is_visible": True,
    }


# =============================================================================
# TestWorkspaceDashboardCRUD
# =============================================================================


class TestWorkspaceDashboardCRUD:
    """Tests for Workspace dashboard CRUD methods."""

    def test_list_dashboards(self, temp_dir: Path) -> None:
        """list_dashboards() returns list of Dashboard objects."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return dashboard list."""
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": [
                        _dashboard_json(1, "Dash A"),
                        _dashboard_json(2, "Dash B"),
                    ],
                },
            )

        ws = _make_workspace(temp_dir, handler)
        dashboards = ws.list_dashboards()

        assert len(dashboards) == 2
        assert isinstance(dashboards[0], Dashboard)
        assert dashboards[0].id == 1
        assert dashboards[0].title == "Dash A"
        assert dashboards[1].id == 2
        assert dashboards[1].title == "Dash B"

    def test_list_dashboards_empty(self, temp_dir: Path) -> None:
        """list_dashboards() returns empty list when no dashboards exist."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return empty dashboard list."""
            return httpx.Response(200, json={"status": "ok", "results": []})

        ws = _make_workspace(temp_dir, handler)
        dashboards = ws.list_dashboards()

        assert dashboards == []

    def test_list_dashboards_with_ids_filter(self, temp_dir: Path) -> None:
        """list_dashboards(ids=[1, 2]) passes filter to API."""
        captured_url: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture URL and return dashboard list."""
            captured_url.append(str(request.url))
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": [
                        _dashboard_json(1, "Dash A"),
                        _dashboard_json(2, "Dash B"),
                    ],
                },
            )

        ws = _make_workspace(temp_dir, handler)
        dashboards = ws.list_dashboards(ids=[1, 2])

        assert len(dashboards) == 2
        assert isinstance(dashboards[0], Dashboard)

    def test_create_dashboard(self, temp_dir: Path) -> None:
        """create_dashboard() returns the created Dashboard."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return created dashboard."""
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": _dashboard_json(10, "New Dashboard"),
                },
            )

        ws = _make_workspace(temp_dir, handler)
        params = CreateDashboardParams(title="New Dashboard")
        dashboard = ws.create_dashboard(params)

        assert isinstance(dashboard, Dashboard)
        assert dashboard.id == 10
        assert dashboard.title == "New Dashboard"

    def test_create_dashboard_with_description(self, temp_dir: Path) -> None:
        """create_dashboard() sends description when provided."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return created dashboard with description."""
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": {
                        **_dashboard_json(11, "Described"),
                        "description": "A test dashboard",
                    },
                },
            )

        ws = _make_workspace(temp_dir, handler)
        params = CreateDashboardParams(
            title="Described", description="A test dashboard"
        )
        dashboard = ws.create_dashboard(params)

        assert dashboard.description == "A test dashboard"

    def test_create_dashboard_private(self, temp_dir: Path) -> None:
        """create_dashboard() can create a private dashboard."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return private dashboard."""
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": {
                        **_dashboard_json(12, "Private"),
                        "is_private": True,
                    },
                },
            )

        ws = _make_workspace(temp_dir, handler)
        params = CreateDashboardParams(title="Private", is_private=True)
        dashboard = ws.create_dashboard(params)

        assert dashboard.is_private is True

    def test_get_dashboard(self, temp_dir: Path) -> None:
        """get_dashboard() returns a single Dashboard by ID."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return single dashboard."""
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": _dashboard_json(1, "My Dashboard"),
                },
            )

        ws = _make_workspace(temp_dir, handler)
        dashboard = ws.get_dashboard(1)

        assert isinstance(dashboard, Dashboard)
        assert dashboard.id == 1
        assert dashboard.title == "My Dashboard"

    def test_get_dashboard_with_details(self, temp_dir: Path) -> None:
        """get_dashboard() preserves extra fields from the API."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return dashboard with extra fields."""
            data = _dashboard_json(5, "Detailed")
            data["description"] = "Full details"
            data["creator_name"] = "Alice"
            return httpx.Response(200, json={"status": "ok", "results": data})

        ws = _make_workspace(temp_dir, handler)
        dashboard = ws.get_dashboard(5)

        assert dashboard.description == "Full details"
        assert dashboard.creator_name == "Alice"

    def test_update_dashboard(self, temp_dir: Path) -> None:
        """update_dashboard() returns the updated Dashboard."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return updated dashboard."""
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": _dashboard_json(1, "Updated Title"),
                },
            )

        ws = _make_workspace(temp_dir, handler)
        params = UpdateDashboardParams(title="Updated Title")
        dashboard = ws.update_dashboard(1, params)

        assert isinstance(dashboard, Dashboard)
        assert dashboard.title == "Updated Title"

    def test_update_dashboard_description(self, temp_dir: Path) -> None:
        """update_dashboard() can update description."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return dashboard with updated description."""
            data = _dashboard_json(1, "Same Title")
            data["description"] = "New description"
            return httpx.Response(200, json={"status": "ok", "results": data})

        ws = _make_workspace(temp_dir, handler)
        params = UpdateDashboardParams(description="New description")
        dashboard = ws.update_dashboard(1, params)

        assert dashboard.description == "New description"

    def test_update_dashboard_privacy(self, temp_dir: Path) -> None:
        """update_dashboard() can toggle privacy."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return dashboard with updated privacy."""
            data = _dashboard_json(1, "Toggle")
            data["is_private"] = True
            return httpx.Response(200, json={"status": "ok", "results": data})

        ws = _make_workspace(temp_dir, handler)
        params = UpdateDashboardParams(is_private=True)
        dashboard = ws.update_dashboard(1, params)

        assert dashboard.is_private is True

    def test_delete_dashboard(self, temp_dir: Path) -> None:
        """delete_dashboard() returns None on success."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return 204 for delete."""
            return httpx.Response(204)

        ws = _make_workspace(temp_dir, handler)
        ws.delete_dashboard(1)  # Should not raise

    def test_delete_dashboard_200(self, temp_dir: Path) -> None:
        """delete_dashboard() handles 200 response too."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return 200 for delete."""
            return httpx.Response(200, json={"status": "ok", "results": {}})

        ws = _make_workspace(temp_dir, handler)
        ws.delete_dashboard(1)  # Should not raise

    def test_bulk_delete_dashboards(self, temp_dir: Path) -> None:
        """bulk_delete_dashboards() returns None on success."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return 204 for bulk delete."""
            return httpx.Response(204)

        ws = _make_workspace(temp_dir, handler)
        ws.bulk_delete_dashboards([1, 2])  # Should not raise

    def test_bulk_delete_dashboards_single(self, temp_dir: Path) -> None:
        """bulk_delete_dashboards() works with a single ID."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return 204 for single bulk delete."""
            return httpx.Response(204)

        ws = _make_workspace(temp_dir, handler)
        ws.bulk_delete_dashboards([42])  # Should not raise

    def test_list_dashboards_preserves_order(self, temp_dir: Path) -> None:
        """list_dashboards() preserves the API response order."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return dashboards in specific order."""
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": [
                        _dashboard_json(3, "Third"),
                        _dashboard_json(1, "First"),
                        _dashboard_json(2, "Second"),
                    ],
                },
            )

        ws = _make_workspace(temp_dir, handler)
        dashboards = ws.list_dashboards()

        assert [d.id for d in dashboards] == [3, 1, 2]

    def test_create_dashboard_with_duplicate(self, temp_dir: Path) -> None:
        """create_dashboard() supports duplicate parameter."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return duplicated dashboard."""
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": _dashboard_json(20, "Copy of Dash"),
                },
            )

        ws = _make_workspace(temp_dir, handler)
        params = CreateDashboardParams(title="Copy of Dash", duplicate=5)
        dashboard = ws.create_dashboard(params)

        assert dashboard.id == 20

    def test_get_dashboard_type_correctness(self, temp_dir: Path) -> None:
        """get_dashboard() result has correct boolean field types."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return dashboard with all boolean fields set."""
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": _dashboard_json(1, "Booleans"),
                },
            )

        ws = _make_workspace(temp_dir, handler)
        dashboard = ws.get_dashboard(1)

        assert isinstance(dashboard.is_private, bool)
        assert isinstance(dashboard.is_restricted, bool)
        assert isinstance(dashboard.can_update_basic, bool)
        assert isinstance(dashboard.can_share, bool)
        assert isinstance(dashboard.can_view, bool)

    def test_bulk_delete_dashboards_multiple(self, temp_dir: Path) -> None:
        """bulk_delete_dashboards() sends multiple IDs."""
        captured_body: list[bytes] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture request body and return 204."""
            captured_body.append(request.content)
            return httpx.Response(204)

        ws = _make_workspace(temp_dir, handler)
        ws.bulk_delete_dashboards([10, 20, 30])

        assert len(captured_body) == 1


# =============================================================================
# TestWorkspaceBookmarkCRUD
# =============================================================================


class TestWorkspaceBookmarkCRUD:
    """Tests for Workspace bookmark CRUD methods."""

    def test_list_bookmarks_v2(self, temp_dir: Path) -> None:
        """list_bookmarks_v2() returns list of Bookmark objects."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return bookmark list."""
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": [
                        _bookmark_json(1, "Bookmark A", "insights"),
                        _bookmark_json(2, "Bookmark B", "funnels"),
                    ],
                },
            )

        ws = _make_workspace(temp_dir, handler)
        bookmarks = ws.list_bookmarks_v2()

        assert len(bookmarks) == 2
        assert isinstance(bookmarks[0], Bookmark)
        assert bookmarks[0].id == 1
        assert bookmarks[0].name == "Bookmark A"
        assert bookmarks[0].bookmark_type == "insights"
        assert bookmarks[1].bookmark_type == "funnels"

    def test_list_bookmarks_v2_empty(self, temp_dir: Path) -> None:
        """list_bookmarks_v2() returns empty list when none exist."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return empty bookmark list."""
            return httpx.Response(200, json={"status": "ok", "results": []})

        ws = _make_workspace(temp_dir, handler)
        bookmarks = ws.list_bookmarks_v2()

        assert bookmarks == []

    def test_list_bookmarks_v2_with_type_filter(self, temp_dir: Path) -> None:
        """list_bookmarks_v2(bookmark_type='funnels') passes filter."""
        captured_url: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture URL and return bookmark list."""
            captured_url.append(str(request.url))
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": [_bookmark_json(1, "Funnel", "funnels")],
                },
            )

        ws = _make_workspace(temp_dir, handler)
        bookmarks = ws.list_bookmarks_v2(bookmark_type="funnels")

        assert len(bookmarks) == 1
        assert bookmarks[0].bookmark_type == "funnels"

    def test_list_bookmarks_v2_preserves_order(self, temp_dir: Path) -> None:
        """list_bookmarks_v2() preserves the API response order."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return bookmarks in specific order."""
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": [
                        _bookmark_json(5, "E"),
                        _bookmark_json(3, "C"),
                        _bookmark_json(1, "A"),
                    ],
                },
            )

        ws = _make_workspace(temp_dir, handler)
        bookmarks = ws.list_bookmarks_v2()

        assert [b.id for b in bookmarks] == [5, 3, 1]

    def test_create_bookmark(self, temp_dir: Path) -> None:
        """create_bookmark() returns the created Bookmark."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return created bookmark or handle add-to-dashboard PATCH."""
            if request.method == "PATCH":
                return httpx.Response(
                    200, json={"status": "ok", "results": _dashboard_json(id=99)}
                )
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": _bookmark_json(10, "New Bookmark", "insights"),
                },
            )

        ws = _make_workspace(temp_dir, handler)
        params = CreateBookmarkParams(
            name="New Bookmark",
            bookmark_type="insights",
            params=MINIMAL_INSIGHTS_PARAMS,
            dashboard_id=99,
        )
        bookmark = ws.create_bookmark(params)

        assert isinstance(bookmark, Bookmark)
        assert bookmark.id == 10
        assert bookmark.name == "New Bookmark"

    def test_create_bookmark_with_description(self, temp_dir: Path) -> None:
        """create_bookmark() sends description when provided."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return created bookmark with description."""
            if request.method == "PATCH":
                return httpx.Response(
                    200, json={"status": "ok", "results": _dashboard_json(id=99)}
                )
            data = _bookmark_json(11, "Described BM", "funnels")
            data["description"] = "A test bookmark"
            return httpx.Response(200, json={"status": "ok", "results": data})

        ws = _make_workspace(temp_dir, handler)
        params = CreateBookmarkParams(
            name="Described BM",
            bookmark_type="funnels",
            params=MINIMAL_FUNNEL_PARAMS,
            description="A test bookmark",
            dashboard_id=99,
        )
        bookmark = ws.create_bookmark(params)

        assert bookmark.description == "A test bookmark"

    def test_create_bookmark_with_dashboard_id(self, temp_dir: Path) -> None:
        """create_bookmark() can associate with a dashboard."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return created bookmark with dashboard_id or handle PATCH."""
            if request.method == "PATCH":
                return httpx.Response(
                    200, json={"status": "ok", "results": _dashboard_json(id=99)}
                )
            data = _bookmark_json(12, "On Dashboard", "insights")
            data["dashboard_id"] = 99
            return httpx.Response(200, json={"status": "ok", "results": data})

        ws = _make_workspace(temp_dir, handler)
        params = CreateBookmarkParams(
            name="On Dashboard",
            bookmark_type="insights",
            params=MINIMAL_INSIGHTS_PARAMS,
            dashboard_id=99,
        )
        bookmark = ws.create_bookmark(params)

        assert bookmark.dashboard_id == 99

    def test_create_bookmark_auto_adds_to_dashboard(self, temp_dir: Path) -> None:
        """create_bookmark() issues a PATCH to add the report to dashboard layout."""
        requests_made: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture requests and return appropriate responses."""
            requests_made.append(request)
            if request.method == "POST" and "bookmarks" in str(request.url):
                data = _bookmark_json(42, "Auto Add", "insights")
                data["dashboard_id"] = 99
                return httpx.Response(200, json={"status": "ok", "results": data})
            if request.method == "PATCH" and "dashboards" in str(request.url):
                return httpx.Response(
                    200,
                    json={"status": "ok", "results": _dashboard_json(id=99)},
                )
            return httpx.Response(200, json={"status": "ok", "results": {}})

        ws = _make_workspace(temp_dir, handler)
        ws.create_bookmark(
            CreateBookmarkParams(
                name="Auto Add",
                bookmark_type="insights",
                params=MINIMAL_INSIGHTS_PARAMS,
                dashboard_id=99,
            )
        )

        patch_requests = [
            r
            for r in requests_made
            if r.method == "PATCH" and "dashboards" in str(r.url)
        ]
        assert len(patch_requests) == 1, (
            f"Expected 1 PATCH to dashboards, got {len(patch_requests)}"
        )
        import json

        patch_body = json.loads(patch_requests[0].content)
        assert patch_body["content"]["content_params"]["source_bookmark_id"] == 42

    def test_create_bookmark_requires_dashboard_id(self, temp_dir: Path) -> None:
        """create_bookmark() raises MixpanelDataError when dashboard_id is missing."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Should not be called."""
            return httpx.Response(200, json={"status": "ok", "results": {}})

        ws = _make_workspace(temp_dir, handler)
        params = CreateBookmarkParams(
            name="No Dashboard",
            bookmark_type="insights",
            params=MINIMAL_INSIGHTS_PARAMS,
        )
        with pytest.raises(MixpanelDataError, match="dashboard_id is required"):
            ws.create_bookmark(params)

    def test_create_bookmark_rejects_malformed_sorting(self, temp_dir: Path) -> None:
        """create_bookmark() raises BookmarkValidationError before any API call.

        Pinning: malformed ``params['sorting']`` (missing ``colSortAttrs``,
        extra ``segmentation``) must be rejected client-side. Without this
        check, the v2 ``POST /bookmarks`` endpoint accepts and persists
        the garbage; failure surfaces only later at chart-render time.
        """
        api_calls: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture every API call so we can assert none were made."""
            api_calls.append(request)
            return httpx.Response(200, json={"status": "ok", "results": {}})

        ws = _make_workspace(temp_dir, handler)
        # Use a minimal-valid bookmark + the malformed sorting block so
        # validation only fires on the sorting.
        bad_params = dict(MINIMAL_INSIGHTS_PARAMS)
        bad_params["sorting"] = {
            "bar": {
                "sortBy": "value",
                "sortOrder": "asc",
                "segmentation": "value",
            }
        }
        params = CreateBookmarkParams(
            name="Bad Sort",
            bookmark_type="insights",
            params=bad_params,
            dashboard_id=99,
        )
        with pytest.raises(BookmarkValidationError) as excinfo:
            ws.create_bookmark(params)

        # Sorting wrapper produces granular S* codes (single source of
        # truth: same Pydantic mirror as create-path uses for the rest).
        codes = {e.code for e in excinfo.value.errors}
        assert "S2_MISSING_COL_SORT_ATTRS" in codes
        assert "S3_UNKNOWN_FIELD" in codes  # extra segmentation field
        assert api_calls == []

    def test_update_bookmark_rejects_malformed_sorting(self, temp_dir: Path) -> None:
        """update_bookmark() rejects malformed sorting before calling the API."""
        api_calls: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture every API call so we can assert none were made."""
            api_calls.append(request)
            return httpx.Response(200, json={"status": "ok", "results": {}})

        ws = _make_workspace(temp_dir, handler)
        params = UpdateBookmarkParams(
            params={"sorting": {"bar": {"sortBy": "value", "segmentation": "value"}}}
        )
        with pytest.raises(BookmarkValidationError):
            ws.update_bookmark(1, params)

        assert api_calls == []

    def test_update_bookmark_rejects_malformed_display_options(
        self, temp_dir: Path
    ) -> None:
        """update_bookmark() rejects malformed displayOptions (Issue 4 regression).

        Previously update_bookmark() only validated ``sorting`` — every other
        malformation slipped through. With partial-aware validation, malformed
        sub-models (e.g. ``displayOptions`` with an invalid ``chartType``) are
        caught before the API call.
        """
        api_calls: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture every API call so we can assert none were made."""
            api_calls.append(request)
            return httpx.Response(200, json={"status": "ok", "results": {}})

        ws = _make_workspace(temp_dir, handler)
        # displayOptions missing required chartType → B0_MISSING_FIELD
        params = UpdateBookmarkParams(
            params={"displayOptions": {"plotStyle": "stacked"}}
        )
        with pytest.raises(BookmarkValidationError) as excinfo:
            ws.update_bookmark(1, params)

        codes = {e.code for e in excinfo.value.errors}
        assert "B0_MISSING_FIELD" in codes  # missing displayOptions.chartType
        assert api_calls == []

    def test_update_bookmark_partial_name_only_no_validation(
        self, temp_dir: Path
    ) -> None:
        """update_bookmark() with partial=name-only does not false-reject.

        Validation must NOT trigger for legitimate partial updates that
        omit ``sections`` / ``displayOptions``. The API is reached.
        """
        api_calls: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture API calls and return a valid bookmark."""
            api_calls.append(request)
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": _bookmark_json(1, "Renamed", "insights"),
                },
            )

        ws = _make_workspace(temp_dir, handler)
        ws.update_bookmark(1, UpdateBookmarkParams(name="Renamed"))
        assert len(api_calls) == 1

    def test_update_bookmark_warning_only_does_not_raise(self, temp_dir: Path) -> None:
        """update_bookmark() with warning-only schema_errors does NOT raise.

        ``S4_UNKNOWN_CHART_TYPE`` is severity=warning. The
        ``any(e.severity == "error" ...)`` gate must let the call through.
        """
        api_calls: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Return a valid bookmark; capture API calls to assert it's reached."""
            api_calls.append(request)
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": _bookmark_json(1, "X", "insights"),
                },
            )

        ws = _make_workspace(temp_dir, handler)
        params = UpdateBookmarkParams(
            params={"sorting": {"barz": {"sortBy": "column", "colSortAttrs": []}}}
        )
        ws.update_bookmark(1, params)  # MUST NOT raise
        assert len(api_calls) == 1

    def test_create_bookmark_warning_logged(
        self, temp_dir: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """create_bookmark() logs warnings (instead of dropping silently)."""
        import logging

        def handler(request: httpx.Request) -> httpx.Response:
            """Return success for both POST and the dashboard PATCH."""
            if request.method == "PATCH":
                return httpx.Response(
                    200, json={"status": "ok", "results": _dashboard_json(id=99)}
                )
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": _bookmark_json(77, "WarnTest", "insights"),
                },
            )

        ws = _make_workspace(temp_dir, handler)
        good_params = dict(MINIMAL_INSIGHTS_PARAMS)
        good_params["sorting"] = {"barz": {"sortBy": "column", "colSortAttrs": []}}
        params = CreateBookmarkParams(
            name="WarnTest",
            bookmark_type="insights",
            params=good_params,
            dashboard_id=99,
        )
        with caplog.at_level(logging.WARNING, logger="mixpanel_data.workspace"):
            ws.create_bookmark(params)

        warning_messages = [
            r.message for r in caplog.records if r.levelno == logging.WARNING
        ]
        assert any("S4_UNKNOWN_CHART_TYPE" in m for m in warning_messages)

    def test_create_bookmark_allows_valid_sorting(self, temp_dir: Path) -> None:
        """create_bookmark() accepts the canonical valid sorting block."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return success for both POST and the dashboard PATCH."""
            if request.method == "PATCH":
                return httpx.Response(
                    200, json={"status": "ok", "results": _dashboard_json(id=99)}
                )
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": _bookmark_json(77, "Good Sort", "insights"),
                },
            )

        ws = _make_workspace(temp_dir, handler)
        good_params = dict(MINIMAL_INSIGHTS_PARAMS)
        good_params["sorting"] = {
            "bar": {
                "sortBy": "column",
                "colSortAttrs": [
                    {
                        "sortBy": "value",
                        "sortOrder": "asc",
                        "valueField": "averageValue",
                    }
                ],
            }
        }
        params = CreateBookmarkParams(
            name="Good Sort",
            bookmark_type="insights",
            params=good_params,
            dashboard_id=99,
        )
        bookmark = ws.create_bookmark(params)
        assert bookmark.id == 77

    def test_get_bookmark(self, temp_dir: Path) -> None:
        """get_bookmark() returns a single Bookmark by ID."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return single bookmark."""
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": _bookmark_json(1, "My Bookmark", "retention"),
                },
            )

        ws = _make_workspace(temp_dir, handler)
        bookmark = ws.get_bookmark(1)

        assert isinstance(bookmark, Bookmark)
        assert bookmark.id == 1
        assert bookmark.name == "My Bookmark"
        assert bookmark.bookmark_type == "retention"

    def test_get_bookmark_with_details(self, temp_dir: Path) -> None:
        """get_bookmark() preserves extra fields."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return bookmark with extra fields."""
            data = _bookmark_json(5, "Detailed", "insights")
            data["creator_name"] = "Bob"
            data["description"] = "Detailed bookmark"
            return httpx.Response(200, json={"status": "ok", "results": data})

        ws = _make_workspace(temp_dir, handler)
        bookmark = ws.get_bookmark(5)

        assert bookmark.creator_name == "Bob"
        assert bookmark.description == "Detailed bookmark"

    def test_update_bookmark(self, temp_dir: Path) -> None:
        """update_bookmark() returns the updated Bookmark."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return updated bookmark."""
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": _bookmark_json(1, "Updated Name", "insights"),
                },
            )

        ws = _make_workspace(temp_dir, handler)
        params = UpdateBookmarkParams(name="Updated Name")
        bookmark = ws.update_bookmark(1, params)

        assert isinstance(bookmark, Bookmark)
        assert bookmark.name == "Updated Name"

    def test_update_bookmark_description(self, temp_dir: Path) -> None:
        """update_bookmark() can update description."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return bookmark with updated description."""
            data = _bookmark_json(1, "Same", "insights")
            data["description"] = "New desc"
            return httpx.Response(200, json={"status": "ok", "results": data})

        ws = _make_workspace(temp_dir, handler)
        params = UpdateBookmarkParams(description="New desc")
        bookmark = ws.update_bookmark(1, params)

        assert bookmark.description == "New desc"

    def test_update_bookmark_params(self, temp_dir: Path) -> None:
        """update_bookmark() can update query params."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return bookmark with updated params."""
            data = _bookmark_json(1, "Same", "insights")
            data["params"] = {"events": [{"event": "Login"}]}
            return httpx.Response(200, json={"status": "ok", "results": data})

        ws = _make_workspace(temp_dir, handler)
        params = UpdateBookmarkParams(params={"events": [{"event": "Login"}]})
        bookmark = ws.update_bookmark(1, params)

        assert bookmark.params == {"events": [{"event": "Login"}]}

    def test_delete_bookmark(self, temp_dir: Path) -> None:
        """delete_bookmark() returns None on success."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return 204 for delete."""
            return httpx.Response(204)

        ws = _make_workspace(temp_dir, handler)
        ws.delete_bookmark(1)  # Should not raise

    def test_delete_bookmark_200(self, temp_dir: Path) -> None:
        """delete_bookmark() handles 200 response."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return 200 for delete."""
            return httpx.Response(200, json={"status": "ok", "results": {}})

        ws = _make_workspace(temp_dir, handler)
        ws.delete_bookmark(1)  # Should not raise

    def test_bulk_delete_bookmarks(self, temp_dir: Path) -> None:
        """bulk_delete_bookmarks() returns None on success."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return 204 for bulk delete."""
            return httpx.Response(204)

        ws = _make_workspace(temp_dir, handler)
        ws.bulk_delete_bookmarks([1, 2])  # Should not raise

    def test_bulk_delete_bookmarks_single(self, temp_dir: Path) -> None:
        """bulk_delete_bookmarks() works with a single ID."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return 204 for single bulk delete."""
            return httpx.Response(204)

        ws = _make_workspace(temp_dir, handler)
        ws.bulk_delete_bookmarks([42])  # Should not raise

    def test_bulk_delete_bookmarks_multiple(self, temp_dir: Path) -> None:
        """bulk_delete_bookmarks() sends multiple IDs."""
        captured_body: list[bytes] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture request body and return 204."""
            captured_body.append(request.content)
            return httpx.Response(204)

        ws = _make_workspace(temp_dir, handler)
        ws.bulk_delete_bookmarks([10, 20, 30])

        assert len(captured_body) == 1

    def test_bulk_update_bookmarks(self, temp_dir: Path) -> None:
        """bulk_update_bookmarks() returns None on success."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return 200 for bulk update."""
            return httpx.Response(200, json={"status": "ok", "results": {}})

        ws = _make_workspace(temp_dir, handler)
        entries = [BulkUpdateBookmarkEntry(id=1, name="Updated A")]
        ws.bulk_update_bookmarks(entries)  # Should not raise

    def test_bulk_update_bookmarks_multiple(self, temp_dir: Path) -> None:
        """bulk_update_bookmarks() handles multiple entries."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return 200 for bulk update."""
            return httpx.Response(200, json={"status": "ok", "results": {}})

        ws = _make_workspace(temp_dir, handler)
        entries = [
            BulkUpdateBookmarkEntry(id=1, name="A"),
            BulkUpdateBookmarkEntry(id=2, name="B"),
            BulkUpdateBookmarkEntry(id=3, description="New desc"),
        ]
        ws.bulk_update_bookmarks(entries)  # Should not raise

    def test_bulk_update_bookmarks_with_params(self, temp_dir: Path) -> None:
        """bulk_update_bookmarks() can update query params."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return 200 for bulk update with params."""
            return httpx.Response(200, json={"status": "ok", "results": {}})

        ws = _make_workspace(temp_dir, handler)
        entries = [
            BulkUpdateBookmarkEntry(id=1, params={"events": [{"event": "Login"}]}),
        ]
        ws.bulk_update_bookmarks(entries)  # Should not raise

    def test_bookmark_linked_dashboard_ids(self, temp_dir: Path) -> None:
        """bookmark_linked_dashboard_ids() returns list of int."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return linked dashboard IDs."""
            return httpx.Response(
                200,
                json={"status": "ok", "results": [10, 20, 30]},
            )

        ws = _make_workspace(temp_dir, handler)
        ids = ws.bookmark_linked_dashboard_ids(1)

        assert ids == [10, 20, 30]

    def test_bookmark_linked_dashboard_ids_empty(self, temp_dir: Path) -> None:
        """bookmark_linked_dashboard_ids() returns empty list when none linked."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return empty linked dashboard IDs."""
            return httpx.Response(200, json={"status": "ok", "results": []})

        ws = _make_workspace(temp_dir, handler)
        ids = ws.bookmark_linked_dashboard_ids(1)

        assert ids == []

    def test_bookmark_linked_dashboard_ids_single(self, temp_dir: Path) -> None:
        """bookmark_linked_dashboard_ids() works with a single ID."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return single linked dashboard ID."""
            return httpx.Response(200, json={"status": "ok", "results": [42]})

        ws = _make_workspace(temp_dir, handler)
        ids = ws.bookmark_linked_dashboard_ids(1)

        assert ids == [42]

    def test_get_bookmark_history(self, temp_dir: Path) -> None:
        """get_bookmark_history() returns BookmarkHistoryResponse."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return bookmark history."""
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": {
                        "results": [
                            {"action": "created", "timestamp": "2024-01-01"},
                            {"action": "updated", "timestamp": "2024-02-01"},
                        ],
                        "pagination": {
                            "page_size": 20,
                            "next_cursor": None,
                            "previous_cursor": None,
                        },
                    },
                },
            )

        ws = _make_workspace(temp_dir, handler)
        history = ws.get_bookmark_history(1)

        assert isinstance(history, BookmarkHistoryResponse)
        assert len(history.results) == 2
        assert history.results[0]["action"] == "created"

    def test_get_bookmark_history_empty(self, temp_dir: Path) -> None:
        """get_bookmark_history() handles empty history."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return empty bookmark history."""
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": {
                        "results": [],
                        "pagination": {"page_size": 20},
                    },
                },
            )

        ws = _make_workspace(temp_dir, handler)
        history = ws.get_bookmark_history(1)

        assert isinstance(history, BookmarkHistoryResponse)
        assert history.results == []

    def test_get_bookmark_history_with_pagination(self, temp_dir: Path) -> None:
        """get_bookmark_history() preserves pagination metadata."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return bookmark history with pagination."""
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": {
                        "results": [{"action": "created"}],
                        "pagination": {
                            "page_size": 10,
                            "next_cursor": "abc123",
                            "previous_cursor": None,
                        },
                    },
                },
            )

        ws = _make_workspace(temp_dir, handler)
        history = ws.get_bookmark_history(1)

        assert history.pagination is not None
        assert history.pagination.page_size == 10
        assert history.pagination.next_cursor == "abc123"

    def test_list_bookmarks_v2_type_field_alias(self, temp_dir: Path) -> None:
        """list_bookmarks_v2() correctly maps 'type' to bookmark_type."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return bookmarks with type field."""
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": [
                        {"id": 1, "name": "F", "type": "flows", "params": {}},
                    ],
                },
            )

        ws = _make_workspace(temp_dir, handler)
        bookmarks = ws.list_bookmarks_v2()

        assert bookmarks[0].bookmark_type == "flows"

    def test_create_bookmark_funnel_type(self, temp_dir: Path) -> None:
        """create_bookmark() works with funnel bookmark type."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return created funnel bookmark or handle PATCH."""
            if request.method == "PATCH":
                return httpx.Response(
                    200, json={"status": "ok", "results": _dashboard_json(id=99)}
                )
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": _bookmark_json(20, "Funnel BM", "funnels"),
                },
            )

        ws = _make_workspace(temp_dir, handler)
        params = CreateBookmarkParams(
            name="Funnel BM",
            bookmark_type="funnels",
            params=MINIMAL_FUNNEL_PARAMS,
            dashboard_id=99,
        )
        bookmark = ws.create_bookmark(params)

        assert bookmark.bookmark_type == "funnels"


# =============================================================================
# TestWorkspaceCohortCRUD
# =============================================================================


class TestWorkspaceCohortCRUD:
    """Tests for Workspace cohort CRUD methods."""

    def test_list_cohorts_full(self, temp_dir: Path) -> None:
        """list_cohorts_full() returns list of Cohort objects."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return cohort list."""
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": [
                        _cohort_json(1, "Cohort A"),
                        _cohort_json(2, "Cohort B"),
                    ],
                },
            )

        ws = _make_workspace(temp_dir, handler)
        cohorts = ws.list_cohorts_full()

        assert len(cohorts) == 2
        assert isinstance(cohorts[0], Cohort)
        assert cohorts[0].id == 1
        assert cohorts[0].name == "Cohort A"
        assert cohorts[1].id == 2

    def test_list_cohorts_full_empty(self, temp_dir: Path) -> None:
        """list_cohorts_full() returns empty list when none exist."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return empty cohort list."""
            return httpx.Response(200, json={"status": "ok", "results": []})

        ws = _make_workspace(temp_dir, handler)
        cohorts = ws.list_cohorts_full()

        assert cohorts == []

    def test_list_cohorts_full_with_data_group_filter(self, temp_dir: Path) -> None:
        """list_cohorts_full(data_group_id='abc') passes filter."""
        captured_url: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture URL and return cohort list."""
            captured_url.append(str(request.url))
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": [_cohort_json(1, "Filtered")],
                },
            )

        ws = _make_workspace(temp_dir, handler)
        cohorts = ws.list_cohorts_full(data_group_id="abc")

        assert len(cohorts) == 1

    def test_list_cohorts_full_preserves_order(self, temp_dir: Path) -> None:
        """list_cohorts_full() preserves API response order."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return cohorts in specific order."""
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": [
                        _cohort_json(3, "C"),
                        _cohort_json(1, "A"),
                        _cohort_json(2, "B"),
                    ],
                },
            )

        ws = _make_workspace(temp_dir, handler)
        cohorts = ws.list_cohorts_full()

        assert [c.id for c in cohorts] == [3, 1, 2]

    def test_get_cohort(self, temp_dir: Path) -> None:
        """get_cohort() returns a single Cohort by ID."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return single cohort."""
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": _cohort_json(1, "My Cohort"),
                },
            )

        ws = _make_workspace(temp_dir, handler)
        cohort = ws.get_cohort(1)

        assert isinstance(cohort, Cohort)
        assert cohort.id == 1
        assert cohort.name == "My Cohort"

    def test_get_cohort_with_details(self, temp_dir: Path) -> None:
        """get_cohort() preserves extra fields."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return cohort with extra fields."""
            data = _cohort_json(5, "Detailed")
            data["description"] = "A detailed cohort"
            data["data_group_id"] = "group-1"
            return httpx.Response(200, json={"status": "ok", "results": data})

        ws = _make_workspace(temp_dir, handler)
        cohort = ws.get_cohort(5)

        assert cohort.description == "A detailed cohort"
        assert cohort.data_group_id == "group-1"

    def test_get_cohort_with_count(self, temp_dir: Path) -> None:
        """get_cohort() preserves count field."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return cohort with count."""
            data = _cohort_json(1, "Counted")
            data["count"] = 42
            return httpx.Response(200, json={"status": "ok", "results": data})

        ws = _make_workspace(temp_dir, handler)
        cohort = ws.get_cohort(1)

        assert cohort.count == 42

    def test_create_cohort(self, temp_dir: Path) -> None:
        """create_cohort() returns the created Cohort."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return created cohort."""
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": _cohort_json(10, "New Cohort"),
                },
            )

        ws = _make_workspace(temp_dir, handler)
        params = CreateCohortParams(name="New Cohort")
        cohort = ws.create_cohort(params)

        assert isinstance(cohort, Cohort)
        assert cohort.id == 10
        assert cohort.name == "New Cohort"

    def test_create_cohort_with_description(self, temp_dir: Path) -> None:
        """create_cohort() sends description when provided."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return created cohort with description."""
            data = _cohort_json(11, "Described")
            data["description"] = "A test cohort"
            return httpx.Response(200, json={"status": "ok", "results": data})

        ws = _make_workspace(temp_dir, handler)
        params = CreateCohortParams(name="Described", description="A test cohort")
        cohort = ws.create_cohort(params)

        assert cohort.description == "A test cohort"

    def test_create_cohort_with_definition(self, temp_dir: Path) -> None:
        """create_cohort() sends definition when provided."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return created cohort."""
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": _cohort_json(12, "Defined"),
                },
            )

        ws = _make_workspace(temp_dir, handler)
        params = CreateCohortParams(
            name="Defined",
            definition={"filter": {"event": "Signup"}},
        )
        cohort = ws.create_cohort(params)

        assert cohort.id == 12

    def test_create_cohort_with_data_group(self, temp_dir: Path) -> None:
        """create_cohort() sends data_group_id when provided."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return created cohort with data_group_id."""
            data = _cohort_json(13, "Grouped")
            data["data_group_id"] = "group-x"
            return httpx.Response(200, json={"status": "ok", "results": data})

        ws = _make_workspace(temp_dir, handler)
        params = CreateCohortParams(name="Grouped", data_group_id="group-x")
        cohort = ws.create_cohort(params)

        assert cohort.data_group_id == "group-x"

    def test_update_cohort(self, temp_dir: Path) -> None:
        """update_cohort() returns the updated Cohort."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return updated cohort."""
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": _cohort_json(1, "Updated Name"),
                },
            )

        ws = _make_workspace(temp_dir, handler)
        params = UpdateCohortParams(name="Updated Name")
        cohort = ws.update_cohort(1, params)

        assert isinstance(cohort, Cohort)
        assert cohort.name == "Updated Name"

    def test_update_cohort_description(self, temp_dir: Path) -> None:
        """update_cohort() can update description."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return cohort with updated description."""
            data = _cohort_json(1, "Same")
            data["description"] = "New desc"
            return httpx.Response(200, json={"status": "ok", "results": data})

        ws = _make_workspace(temp_dir, handler)
        params = UpdateCohortParams(description="New desc")
        cohort = ws.update_cohort(1, params)

        assert cohort.description == "New desc"

    def test_update_cohort_visibility(self, temp_dir: Path) -> None:
        """update_cohort() can toggle visibility."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return cohort with updated visibility."""
            data = _cohort_json(1, "Toggle")
            data["is_visible"] = False
            return httpx.Response(200, json={"status": "ok", "results": data})

        ws = _make_workspace(temp_dir, handler)
        params = UpdateCohortParams(is_visible=False)
        cohort = ws.update_cohort(1, params)

        assert cohort.is_visible is False

    def test_update_cohort_definition(self, temp_dir: Path) -> None:
        """update_cohort() can update the definition."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return updated cohort."""
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": _cohort_json(1, "Redefined"),
                },
            )

        ws = _make_workspace(temp_dir, handler)
        params = UpdateCohortParams(definition={"filter": {"event": "Purchase"}})
        cohort = ws.update_cohort(1, params)

        assert cohort.id == 1

    def test_delete_cohort(self, temp_dir: Path) -> None:
        """delete_cohort() returns None on success."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return 204 for delete."""
            return httpx.Response(204)

        ws = _make_workspace(temp_dir, handler)
        ws.delete_cohort(1)  # Should not raise

    def test_delete_cohort_200(self, temp_dir: Path) -> None:
        """delete_cohort() handles 200 response."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return 200 for delete."""
            return httpx.Response(200, json={"status": "ok", "results": {}})

        ws = _make_workspace(temp_dir, handler)
        ws.delete_cohort(1)  # Should not raise

    def test_bulk_delete_cohorts(self, temp_dir: Path) -> None:
        """bulk_delete_cohorts() returns None on success."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return 204 for bulk delete."""
            return httpx.Response(204)

        ws = _make_workspace(temp_dir, handler)
        ws.bulk_delete_cohorts([1, 2])  # Should not raise

    def test_bulk_delete_cohorts_single(self, temp_dir: Path) -> None:
        """bulk_delete_cohorts() works with a single ID."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return 204 for single bulk delete."""
            return httpx.Response(204)

        ws = _make_workspace(temp_dir, handler)
        ws.bulk_delete_cohorts([42])  # Should not raise

    def test_bulk_delete_cohorts_multiple(self, temp_dir: Path) -> None:
        """bulk_delete_cohorts() sends multiple IDs."""
        captured_body: list[bytes] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture request body and return 204."""
            captured_body.append(request.content)
            return httpx.Response(204)

        ws = _make_workspace(temp_dir, handler)
        ws.bulk_delete_cohorts([10, 20, 30])

        assert len(captured_body) == 1

    def test_bulk_update_cohorts(self, temp_dir: Path) -> None:
        """bulk_update_cohorts() returns None on success."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return 200 for bulk update."""
            return httpx.Response(200, json={"status": "ok", "results": {}})

        ws = _make_workspace(temp_dir, handler)
        entries = [BulkUpdateCohortEntry(id=1, name="Updated A")]
        ws.bulk_update_cohorts(entries)  # Should not raise

    def test_bulk_update_cohorts_multiple(self, temp_dir: Path) -> None:
        """bulk_update_cohorts() handles multiple entries."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return 200 for bulk update."""
            return httpx.Response(200, json={"status": "ok", "results": {}})

        ws = _make_workspace(temp_dir, handler)
        entries = [
            BulkUpdateCohortEntry(id=1, name="A"),
            BulkUpdateCohortEntry(id=2, name="B"),
            BulkUpdateCohortEntry(id=3, description="New desc"),
        ]
        ws.bulk_update_cohorts(entries)  # Should not raise

    def test_bulk_update_cohorts_with_definition(self, temp_dir: Path) -> None:
        """bulk_update_cohorts() can update definitions."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return 200 for bulk update with definition."""
            return httpx.Response(200, json={"status": "ok", "results": {}})

        ws = _make_workspace(temp_dir, handler)
        entries = [
            BulkUpdateCohortEntry(id=1, definition={"filter": {"event": "Signup"}}),
        ]
        ws.bulk_update_cohorts(entries)  # Should not raise

    def test_list_cohorts_full_with_count(self, temp_dir: Path) -> None:
        """list_cohorts_full() preserves count on each cohort."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return cohorts with counts."""
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": [
                        {**_cohort_json(1, "Small"), "count": 10},
                        {**_cohort_json(2, "Large"), "count": 10000},
                    ],
                },
            )

        ws = _make_workspace(temp_dir, handler)
        cohorts = ws.list_cohorts_full()

        assert cohorts[0].count == 10
        assert cohorts[1].count == 10000

    def test_get_cohort_type_correctness(self, temp_dir: Path) -> None:
        """get_cohort() result has correct field types."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return cohort with typed fields."""
            data = _cohort_json(1, "Typed")
            data["is_visible"] = True
            data["is_locked"] = False
            data["verified"] = True
            return httpx.Response(200, json={"status": "ok", "results": data})

        ws = _make_workspace(temp_dir, handler)
        cohort = ws.get_cohort(1)

        assert isinstance(cohort.is_visible, bool)
        assert isinstance(cohort.is_locked, bool)
        assert isinstance(cohort.verified, bool)
        assert cohort.verified is True

    def test_create_cohort_locked(self, temp_dir: Path) -> None:
        """create_cohort() can create a locked cohort."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return locked cohort."""
            data = _cohort_json(14, "Locked")
            data["is_locked"] = True
            return httpx.Response(200, json={"status": "ok", "results": data})

        ws = _make_workspace(temp_dir, handler)
        params = CreateCohortParams(name="Locked", is_locked=True)
        cohort = ws.create_cohort(params)

        assert cohort.is_locked is True

    def test_update_cohort_lock(self, temp_dir: Path) -> None:
        """update_cohort() can toggle lock state."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return cohort with toggled lock."""
            data = _cohort_json(1, "Unlocked")
            data["is_locked"] = False
            return httpx.Response(200, json={"status": "ok", "results": data})

        ws = _make_workspace(temp_dir, handler)
        params = UpdateCohortParams(is_locked=False)
        cohort = ws.update_cohort(1, params)

        assert cohort.is_locked is False


# =============================================================================
# Additional Coverage (PR Review Findings)
# =============================================================================


class TestWorkspaceBlueprintCohorts:
    """Tests for update_blueprint_cohorts workspace method."""

    def test_update_blueprint_cohorts(self, temp_dir: Path) -> None:
        """update_blueprint_cohorts() delegates to API client."""
        captured: list[Any] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture request body."""
            import json

            captured.append(json.loads(request.content))
            return httpx.Response(204)

        ws = _make_workspace(temp_dir, handler)
        ws.update_blueprint_cohorts([{"placeholder": "new_users", "cohort_id": 42}])

        assert captured[0] == {
            "cohorts": [{"placeholder": "new_users", "cohort_id": 42}]
        }


class TestRemoveReportFromDashboard:
    """Tests for remove_report_from_dashboard using PATCH with content action."""

    def test_remove_report_returns_dashboard(self, temp_dir: Path) -> None:
        """remove_report_from_dashboard() sends PATCH and returns updated dashboard."""
        call_count = 0

        def handler(request: httpx.Request) -> httpx.Response:
            """Return updated dashboard for PATCH request."""
            nonlocal call_count
            call_count += 1
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": {"id": 1, "title": "Updated Dashboard"},
                },
            )

        ws = _make_workspace(temp_dir, handler)
        result = ws.remove_report_from_dashboard(1, 42)

        assert isinstance(result, Dashboard)
        assert result.title == "Updated Dashboard"
        assert call_count == 1  # Single PATCH request


class TestAddReportToDashboard:
    """Tests for add_report_to_dashboard using PATCH with content action."""

    def test_add_report_returns_dashboard(self, temp_dir: Path) -> None:
        """add_report_to_dashboard() sends PATCH and returns updated dashboard."""
        call_count = 0

        def handler(request: httpx.Request) -> httpx.Response:
            """Return updated dashboard for PATCH request."""
            nonlocal call_count
            call_count += 1
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": {"id": 1, "title": "Updated Dashboard"},
                },
            )

        ws = _make_workspace(temp_dir, handler)
        result = ws.add_report_to_dashboard(1, 42)

        assert isinstance(result, Dashboard)
        assert result.title == "Updated Dashboard"
        assert call_count == 1  # Single PATCH request

    def test_add_report_raises_on_unexpected_response(self, temp_dir: Path) -> None:
        """add_report_to_dashboard() raises MixpanelDataError for non-dashboard response."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return 204-style response without dashboard payload."""
            return httpx.Response(204)

        ws = _make_workspace(temp_dir, handler)
        with pytest.raises(MixpanelDataError, match="Unexpected response"):
            ws.add_report_to_dashboard(1, 42)

    def test_add_report_raises_on_dict_without_id(self, temp_dir: Path) -> None:
        """add_report_to_dashboard() raises MixpanelDataError when response dict lacks 'id'."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return a dict response that is missing the 'id' key."""
            return httpx.Response(
                200,
                json={"status": "ok", "results": {"title": "No ID Dashboard"}},
            )

        ws = _make_workspace(temp_dir, handler)
        with pytest.raises(MixpanelDataError, match="Unexpected response"):
            ws.add_report_to_dashboard(1, 42)
