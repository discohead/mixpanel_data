"""Tests for MixpanelAPIClient.list_bookmarks() method.

Phase 015: Bookmarks API - Tests for listing saved reports.
"""

from __future__ import annotations

from collections.abc import Callable

import httpx
import pytest

from mixpanel_data._internal.api_client import MixpanelAPIClient
from mixpanel_data._internal.config import Credentials
from mixpanel_data.exceptions import AuthenticationError, QueryError


@pytest.fixture
def test_credentials() -> Credentials:
    """Provide test credentials."""
    return Credentials(
        username="test_user",
        secret="test_secret",
        project_id="12345",
        region="us",
    )


def create_mock_client(
    credentials: Credentials,
    handler: Callable[[httpx.Request], httpx.Response] | None = None,
) -> MixpanelAPIClient:
    """Create a MixpanelAPIClient with a mock transport."""
    if handler is None:
        transport = httpx.MockTransport(lambda _: httpx.Response(200, json={}))
    else:
        transport = httpx.MockTransport(handler)
    return MixpanelAPIClient(credentials, _transport=transport)


class TestListBookmarks:
    """Tests for MixpanelAPIClient.list_bookmarks()."""

    def test_list_bookmarks_endpoint_url(self, test_credentials: Credentials) -> None:
        """list_bookmarks() should call correct endpoint with v=2."""

        def handler(request: httpx.Request) -> httpx.Response:
            assert "/api/app/projects/12345/bookmarks" in str(request.url)
            assert "v=2" in str(request.url)
            return httpx.Response(200, json={"results": []})

        with create_mock_client(test_credentials, handler) as client:
            client.list_bookmarks()

    def test_list_bookmarks_returns_results(
        self, test_credentials: Credentials
    ) -> None:
        """list_bookmarks() should return raw API response with results."""

        def handler(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                json={
                    "results": [
                        {
                            "id": 63877017,
                            "name": "Weekly Active Users",
                            "type": "insights",
                            "project_id": 12345,
                            "created": "2024-01-01T00:00:00",
                            "modified": "2024-06-15T10:30:00",
                        },
                        {
                            "id": 63877018,
                            "name": "Conversion Funnel",
                            "type": "funnels",
                            "project_id": 12345,
                            "created": "2024-02-01T00:00:00",
                            "modified": "2024-07-20T14:45:00",
                        },
                    ]
                },
            )

        with create_mock_client(test_credentials, handler) as client:
            result = client.list_bookmarks()

        assert "results" in result
        assert len(result["results"]) == 2
        assert result["results"][0]["name"] == "Weekly Active Users"
        assert result["results"][1]["type"] == "funnels"

    def test_list_bookmarks_with_type_filter(
        self, test_credentials: Credentials
    ) -> None:
        """list_bookmarks() should pass type parameter when specified."""

        def handler(request: httpx.Request) -> httpx.Response:
            assert "type=insights" in str(request.url)
            return httpx.Response(
                200,
                json={
                    "results": [
                        {
                            "id": 63877017,
                            "name": "Weekly Active Users",
                            "type": "insights",
                            "project_id": 12345,
                            "created": "2024-01-01T00:00:00",
                            "modified": "2024-06-15T10:30:00",
                        }
                    ]
                },
            )

        with create_mock_client(test_credentials, handler) as client:
            result = client.list_bookmarks(bookmark_type="insights")

        assert len(result["results"]) == 1
        assert result["results"][0]["type"] == "insights"

    def test_list_bookmarks_all_types(self, test_credentials: Credentials) -> None:
        """list_bookmarks() should support all valid bookmark types."""
        bookmark_types = [
            "insights",
            "funnels",
            "retention",
            "flows",
            "launch-analysis",
        ]

        for bm_type in bookmark_types:

            def handler(_request: httpx.Request) -> httpx.Response:
                return httpx.Response(200, json={"results": []})

            with create_mock_client(test_credentials, handler) as client:
                # Should not raise
                client.list_bookmarks(bookmark_type=bm_type)

    def test_list_bookmarks_empty_results(self, test_credentials: Credentials) -> None:
        """list_bookmarks() should handle empty results."""

        def handler(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={"results": []})

        with create_mock_client(test_credentials, handler) as client:
            result = client.list_bookmarks()

        assert result["results"] == []

    def test_list_bookmarks_full_metadata(self, test_credentials: Credentials) -> None:
        """list_bookmarks() should return all bookmark metadata fields."""

        def handler(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                json={
                    "results": [
                        {
                            "id": 63877017,
                            "name": "Monthly Recurring Revenue",
                            "type": "insights",
                            "project_id": 12345,
                            "workspace_id": 100,
                            "dashboard_id": 200,
                            "created": "2024-09-18T16:39:49",
                            "modified": "2025-08-26T05:16:50",
                            "creator_id": 42,
                            "creator_name": "John Doe",
                            "description": "Track monthly recurring revenue",
                        }
                    ]
                },
            )

        with create_mock_client(test_credentials, handler) as client:
            result = client.list_bookmarks()

        bookmark = result["results"][0]
        assert bookmark["id"] == 63877017
        assert bookmark["name"] == "Monthly Recurring Revenue"
        assert bookmark["type"] == "insights"
        assert bookmark["project_id"] == 12345
        assert bookmark["workspace_id"] == 100
        assert bookmark["dashboard_id"] == 200
        assert bookmark["created"] == "2024-09-18T16:39:49"
        assert bookmark["modified"] == "2025-08-26T05:16:50"
        assert bookmark["creator_id"] == 42
        assert bookmark["creator_name"] == "John Doe"
        assert bookmark["description"] == "Track monthly recurring revenue"


class TestListBookmarksErrors:
    """Error handling tests for list_bookmarks()."""

    def test_list_bookmarks_auth_error_on_401(
        self, test_credentials: Credentials
    ) -> None:
        """list_bookmarks() should raise AuthenticationError on 401."""

        def handler(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(401, json={"error": "Invalid credentials"})

        with (
            create_mock_client(test_credentials, handler) as client,
            pytest.raises(AuthenticationError),
        ):
            client.list_bookmarks()

    def test_list_bookmarks_query_error_on_403(
        self, test_credentials: Credentials
    ) -> None:
        """list_bookmarks() should raise QueryError on 403 permission denied."""

        def handler(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(403, json={"error": "Permission denied"})

        with (
            create_mock_client(test_credentials, handler) as client,
            pytest.raises(QueryError) as exc_info,
        ):
            client.list_bookmarks()

        assert "Permission denied" in str(exc_info.value)

    def test_list_bookmarks_query_error_on_400(
        self, test_credentials: Credentials
    ) -> None:
        """list_bookmarks() should raise QueryError on 400 bad request."""

        def handler(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(400, json={"error": "Invalid type parameter"})

        with (
            create_mock_client(test_credentials, handler) as client,
            pytest.raises(QueryError) as exc_info,
        ):
            client.list_bookmarks(bookmark_type="invalid")

        assert "Invalid type parameter" in str(exc_info.value)


class TestQueryFlows:
    """Tests for MixpanelAPIClient.query_flows()."""

    def test_query_flows_endpoint_url(self, test_credentials: Credentials) -> None:
        """query_flows() should call /api/query/arb_funnels with query_type=flows_sankey."""

        def handler(request: httpx.Request) -> httpx.Response:
            assert "/api/query/arb_funnels" in str(request.url)
            assert "query_type=flows_sankey" in str(request.url)
            assert "bookmark_id=12345" in str(request.url)
            return httpx.Response(
                200,
                json={
                    "steps": [],
                    "breakdowns": [],
                    "overallConversionRate": 0.0,
                    "computed_at": "2024-01-15T10:00:00",
                },
            )

        with create_mock_client(test_credentials, handler) as client:
            client.query_flows(bookmark_id=12345)

    def test_query_flows_returns_raw_response(
        self, test_credentials: Credentials
    ) -> None:
        """query_flows() should return raw API response."""

        def handler(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                json={
                    "steps": [
                        {"step": 1, "event": "Page View", "count": 1000},
                        {"step": 2, "event": "Add to Cart", "count": 500},
                    ],
                    "breakdowns": [{"path": "Page View -> Add to Cart", "count": 500}],
                    "overallConversionRate": 0.5,
                    "computed_at": "2024-01-15T10:00:00",
                    "metadata": {"version": "1.0"},
                },
            )

        with create_mock_client(test_credentials, handler) as client:
            result = client.query_flows(bookmark_id=12345)

        assert "steps" in result
        assert len(result["steps"]) == 2
        assert result["overallConversionRate"] == 0.5
        assert result["computed_at"] == "2024-01-15T10:00:00"

    def test_query_flows_auth_error_on_401(self, test_credentials: Credentials) -> None:
        """query_flows() should raise AuthenticationError on 401."""

        def handler(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(401, json={"error": "Invalid credentials"})

        with (
            create_mock_client(test_credentials, handler) as client,
            pytest.raises(AuthenticationError),
        ):
            client.query_flows(bookmark_id=12345)

    def test_query_flows_query_error_on_404(
        self, test_credentials: Credentials
    ) -> None:
        """query_flows() should raise QueryError on 404 (bookmark not found)."""

        def handler(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(404, json={"error": "Bookmark not found"})

        with (
            create_mock_client(test_credentials, handler) as client,
            pytest.raises(QueryError) as exc_info,
        ):
            client.query_flows(bookmark_id=99999)

        assert "Bookmark not found" in str(exc_info.value)
