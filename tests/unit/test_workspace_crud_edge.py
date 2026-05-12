"""Edge case tests for Phase 024 Workspace CRUD methods.

Verifies HTTP request body serialization, empty response handling,
and method delegation for dashboard, bookmark, and cohort operations.

These tests capture the ACTUAL HTTP request body sent through the mock
transport, ensuring the Workspace correctly serializes Pydantic models
before calling the API.
"""
# ruff: noqa: ARG001, ARG005

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import httpx
import pytest
from pydantic import SecretStr

from mixpanel_headless._internal.api_client import MixpanelAPIClient
from mixpanel_headless._internal.auth.account import ServiceAccount
from mixpanel_headless._internal.auth.session import Project, Session
from mixpanel_headless.types import (
    BlueprintCard,
    BlueprintFinishParams,
    BulkUpdateBookmarkEntry,
    BulkUpdateCohortEntry,
    CreateBookmarkParams,
    CreateCohortParams,
    CreateDashboardParams,
    CreateRcaDashboardParams,
    RcaSourceData,
    UpdateDashboardParams,
    UpdateReportLinkParams,
)
from mixpanel_headless.workspace import Workspace
from tests.conftest import make_session
from tests.unit._bookmark_fixtures import MINIMAL_FUNNEL_PARAMS

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


def _make_creds() -> Session:
    """Create OAuth Credentials for testing.

    Returns:
        A Credentials instance with auth_method=oauth.
    """
    return make_session(project_id="12345", region="us", oauth_token="test-token")


# _make_config removed in B1 (Fix 9): the legacy v1 add_account signature
# is gone and ``_make_workspace`` now uses ``session=_TEST_SESSION``
# instead of resolving through ConfigManager.


def _make_workspace(temp_dir: Path, handler: Any) -> Workspace:
    """Create a Workspace with a mock HTTP transport.

    Args:
        temp_dir: Temporary directory for config and storage.
        handler: Mock transport handler function.

    Returns:
        A Workspace using the mock transport.
    """
    creds = _make_creds()
    transport = httpx.MockTransport(handler)
    client = MixpanelAPIClient(session=creds, _transport=transport)
    return Workspace(
        session=_TEST_SESSION,
        _api_client=client,
    )


class TestRequestBodySerialization:
    """Tests verifying correct HTTP request body serialization (Bug B5)."""

    def test_create_bookmark_sends_type_not_bookmark_type(self, temp_dir: Path) -> None:
        """Verify create_bookmark serializes bookmark_type as 'type' in the request body."""
        captured: dict[str, Any] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture request body and return a valid bookmark response."""
            if request.method == "POST" and "bookmarks" in str(request.url):
                captured["body"] = json.loads(request.content)
                return httpx.Response(
                    200,
                    json={
                        "status": "ok",
                        "results": {
                            "id": 1,
                            "name": "X",
                            "type": "funnels",
                            "params": {},
                        },
                    },
                )
            # Handle PATCH for add_report_to_dashboard
            if request.method == "PATCH":
                return httpx.Response(
                    200, json={"status": "ok", "results": {"id": 99, "title": "T"}}
                )
            return httpx.Response(200, json={"status": "ok", "results": []})

        # Use minimal valid funnel params so client-side schema
        # validation passes; this test is about request body
        # serialization (``bookmark_type`` → ``type`` alias), not about
        # validation behavior.
        ws = _make_workspace(temp_dir, handler)
        ws.create_bookmark(
            CreateBookmarkParams(
                name="X",
                bookmark_type="funnels",
                params=MINIMAL_FUNNEL_PARAMS,
                dashboard_id=99,
            )
        )

        body = captured["body"]
        assert "type" in body
        assert "bookmark_type" not in body
        assert body["type"] == "funnels"

    def test_create_cohort_sends_flattened_definition(self, temp_dir: Path) -> None:
        """Verify create_cohort flattens definition into the top-level request body."""
        captured: dict[str, Any] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture request body and return a valid cohort response."""
            if request.method == "POST" and "cohorts" in str(request.url):
                captured["body"] = json.loads(request.content)
                return httpx.Response(
                    200,
                    json={
                        "status": "ok",
                        "results": {"id": 1, "name": "X"},
                    },
                )
            return httpx.Response(200, json={"status": "ok", "results": []})

        ws = _make_workspace(temp_dir, handler)
        ws.create_cohort(
            CreateCohortParams(
                name="X",
                definition={"behavioral_filter": {"op": "and"}},
            )
        )

        body = captured["body"]
        assert "behavioral_filter" in body
        assert "definition" not in body

    def test_finalize_blueprint_sends_card_type_as_type(self, temp_dir: Path) -> None:
        """Verify finalize_blueprint serializes card_type as 'type' in card entries."""
        captured: dict[str, Any] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture request body and return a finalized dashboard response."""
            if request.method == "POST" and "blueprints" in str(request.url):
                captured["body"] = json.loads(request.content)
                return httpx.Response(
                    200,
                    json={
                        "status": "ok",
                        "results": {"id": 1, "title": "X"},
                    },
                )
            return httpx.Response(200, json={"status": "ok", "results": []})

        ws = _make_workspace(temp_dir, handler)
        ws.finalize_blueprint(
            BlueprintFinishParams(
                dashboard_id=1,
                cards=[BlueprintCard(card_type="report", bookmark_id=42)],
            )
        )

        body = captured["body"]
        assert body["cards"][0]["type"] == "report"
        assert "card_type" not in body["cards"][0]

    def test_create_rca_sends_source_type_as_type(self, temp_dir: Path) -> None:
        """Verify create_rca_dashboard serializes source_type as 'type' in rca_source_data."""
        captured: dict[str, Any] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture request body and return an RCA dashboard response."""
            if request.method == "POST" and "rca" in str(request.url):
                captured["body"] = json.loads(request.content)
                return httpx.Response(
                    200,
                    json={
                        "status": "ok",
                        "results": {"id": 1, "title": "RCA"},
                    },
                )
            return httpx.Response(200, json={"status": "ok", "results": []})

        ws = _make_workspace(temp_dir, handler)
        ws.create_rca_dashboard(
            CreateRcaDashboardParams(
                rca_source_id=42,
                rca_source_data=RcaSourceData(source_type="anomaly"),
            )
        )

        body = captured["body"]
        assert body["rca_source_data"]["type"] == "anomaly"
        assert "source_type" not in body["rca_source_data"]

    def test_update_report_link_sends_type(self, temp_dir: Path) -> None:
        """Verify update_report_link serializes link_type as 'type' in the request body."""
        captured: dict[str, Any] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture request body and return 204 No Content."""
            if request.method == "PATCH" and "report-links" in str(request.url):
                captured["body"] = json.loads(request.content)
                return httpx.Response(204)
            return httpx.Response(200, json={"status": "ok", "results": []})

        ws = _make_workspace(temp_dir, handler)
        ws.update_report_link(1, 42, UpdateReportLinkParams(link_type="embedded"))

        body = captured["body"]
        assert body["type"] == "embedded"
        assert "link_type" not in body


class TestEmptyResponseHandling:
    """Tests verifying behavior when API returns empty or minimal responses (Bug B3)."""

    def test_create_dashboard_empty_response_raises(self, temp_dir: Path) -> None:
        """Verify create_dashboard raises ValidationError when response is empty dict.

        An empty dict ``{}`` passes the ``is None`` check but fails Pydantic
        validation because required fields (``id``, ``title``) are missing.
        """
        from pydantic import ValidationError

        def handler(request: httpx.Request) -> httpx.Response:
            """Return an empty results dict for dashboard creation."""
            return httpx.Response(200, json={"status": "ok", "results": {}})

        ws = _make_workspace(temp_dir, handler)
        with pytest.raises(ValidationError):
            ws.create_dashboard(CreateDashboardParams(title="X"))

    def test_get_bookmark_empty_response_raises(self, temp_dir: Path) -> None:
        """Verify get_bookmark raises ValidationError when response is empty dict.

        An empty dict ``{}`` passes the ``is None`` check but fails Pydantic
        validation because required fields (``id``, ``name``, ``type``) are missing.
        """
        from pydantic import ValidationError

        def handler(request: httpx.Request) -> httpx.Response:
            """Return an empty results dict for bookmark retrieval."""
            return httpx.Response(200, json={"status": "ok", "results": {}})

        ws = _make_workspace(temp_dir, handler)
        with pytest.raises(ValidationError):
            ws.get_bookmark(1)

    def test_list_dashboards_empty_list_ok(self, temp_dir: Path) -> None:
        """Verify list_dashboards returns empty list when API returns empty results."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return an empty results list for dashboard listing."""
            return httpx.Response(200, json={"status": "ok", "results": []})

        ws = _make_workspace(temp_dir, handler)
        result = ws.list_dashboards()
        assert result == []


class TestWorkspaceMethodDelegation:
    """Tests verifying Workspace methods correctly delegate and serialize to API client."""

    def test_bulk_update_bookmarks_serializes_entries(self, temp_dir: Path) -> None:
        """Verify bulk_update_bookmarks sends correctly serialized entries with no None fields."""
        captured: dict[str, Any] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture request body for bulk bookmark update."""
            if request.method == "POST" and "bookmarks/bulk-update" in str(request.url):
                captured["body"] = json.loads(request.content)
                return httpx.Response(204)
            return httpx.Response(200, json={"status": "ok", "results": []})

        ws = _make_workspace(temp_dir, handler)
        ws.bulk_update_bookmarks([BulkUpdateBookmarkEntry(id=1, name="Renamed")])

        body = captured["body"]
        assert body == {"bookmarks": [{"id": 1, "name": "Renamed"}]}

    def test_bulk_update_cohorts_serializes_entries_with_definition(
        self, temp_dir: Path
    ) -> None:
        """Verify bulk_update_cohorts flattens definition into each entry."""
        captured: dict[str, Any] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture request body for bulk cohort update."""
            if request.method == "POST" and "cohorts/bulk-update" in str(request.url):
                captured["body"] = json.loads(request.content)
                return httpx.Response(204)
            return httpx.Response(200, json={"status": "ok", "results": []})

        ws = _make_workspace(temp_dir, handler)
        ws.bulk_update_cohorts(
            [BulkUpdateCohortEntry(id=1, definition={"filter": "x"})]
        )

        body = captured["body"]
        entry = body["cohorts"][0]
        assert entry["id"] == 1
        assert entry["filter"] == "x"
        assert "definition" not in entry

    def test_update_dashboard_exclude_none(self, temp_dir: Path) -> None:
        """Verify update_dashboard sends only non-None fields in request body."""
        captured: dict[str, Any] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture request body for dashboard update."""
            if request.method == "PATCH" and "dashboards" in str(request.url):
                captured["body"] = json.loads(request.content)
                return httpx.Response(
                    200,
                    json={
                        "status": "ok",
                        "results": {"id": 1, "title": "New"},
                    },
                )
            return httpx.Response(200, json={"status": "ok", "results": []})

        ws = _make_workspace(temp_dir, handler)
        ws.update_dashboard(1, UpdateDashboardParams(title="New"))

        body = captured["body"]
        assert body == {"title": "New"}

    def test_list_bookmarks_v2_no_filters(self, temp_dir: Path) -> None:
        """Verify list_bookmarks_v2 with no args sends no type or ids query params."""
        captured: dict[str, Any] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture request URL for bookmark listing."""
            if "/bookmarks" in str(request.url):
                captured["url"] = str(request.url)
                return httpx.Response(200, json={"status": "ok", "results": []})
            return httpx.Response(200, json={"status": "ok", "results": []})

        ws = _make_workspace(temp_dir, handler)
        ws.list_bookmarks_v2()

        url = captured["url"]
        assert "type=" not in url
        assert "ids=" not in url
