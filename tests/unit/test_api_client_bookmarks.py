"""Tests for MixpanelAPIClient bookmark methods.

Phase 015: Bookmarks API - Tests for listing saved reports.
Phase 016: Smart routing for query_saved_report with bookmark_type parameter.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timedelta

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


class TestQuerySavedReportRouting:
    """Tests for MixpanelAPIClient.query_saved_report() smart routing."""

    def test_query_saved_report_default_routes_to_insights(
        self, test_credentials: Credentials
    ) -> None:
        """query_saved_report() without bookmark_type should call /insights."""

        def handler(request: httpx.Request) -> httpx.Response:
            assert "/api/query/insights" in str(request.url)
            assert "bookmark_id=12345" in str(request.url)
            return httpx.Response(
                200,
                json={
                    "headers": ["$metric"],
                    "computed_at": "2024-01-15T10:00:00",
                    "date_range": {"from_date": "2024-01-01", "to_date": "2024-01-15"},
                    "series": {"Event A": {"2024-01-01": 100}},
                },
            )

        with create_mock_client(test_credentials, handler) as client:
            result = client.query_saved_report(bookmark_id=12345)

        assert "headers" in result
        assert result["headers"] == ["$metric"]

    def test_query_saved_report_insights_type_routes_to_insights(
        self, test_credentials: Credentials
    ) -> None:
        """query_saved_report(bookmark_type='insights') should call /insights."""

        def handler(request: httpx.Request) -> httpx.Response:
            assert "/api/query/insights" in str(request.url)
            return httpx.Response(
                200,
                json={
                    "headers": ["$metric"],
                    "computed_at": "2024-01-15T10:00:00",
                    "date_range": {"from_date": "2024-01-01", "to_date": "2024-01-15"},
                    "series": {},
                },
            )

        with create_mock_client(test_credentials, handler) as client:
            client.query_saved_report(bookmark_id=12345, bookmark_type="insights")

    def test_query_saved_report_funnels_routes_to_funnels_endpoint(
        self, test_credentials: Credentials
    ) -> None:
        """query_saved_report(bookmark_type='funnels') should call /funnels."""

        def handler(request: httpx.Request) -> httpx.Response:
            assert "/api/query/funnels" in str(request.url)
            return httpx.Response(
                200,
                json={
                    "computed_at": "2024-01-15T10:00:00",
                    "data": {"2024-01-15": {"steps": []}},
                    "meta": {},
                },
            )

        with create_mock_client(test_credentials, handler) as client:
            client.query_saved_report(bookmark_id=12345, bookmark_type="funnels")

    def test_query_saved_report_funnels_uses_funnel_id_param(
        self, test_credentials: Credentials
    ) -> None:
        """query_saved_report(bookmark_type='funnels') should use funnel_id parameter."""

        def handler(request: httpx.Request) -> httpx.Response:
            # For funnels, the bookmark_id is passed as funnel_id
            assert "funnel_id=12345" in str(request.url)
            return httpx.Response(
                200,
                json={
                    "computed_at": "2024-01-15T10:00:00",
                    "data": {},
                    "meta": {},
                },
            )

        with create_mock_client(test_credentials, handler) as client:
            client.query_saved_report(bookmark_id=12345, bookmark_type="funnels")

    def test_query_saved_report_funnels_default_dates_last_30_days(
        self, test_credentials: Credentials
    ) -> None:
        """query_saved_report(bookmark_type='funnels') defaults to last 30 days."""
        today = datetime.now().strftime("%Y-%m-%d")
        thirty_days_ago = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")

        def handler(request: httpx.Request) -> httpx.Response:
            url_str = str(request.url)
            assert f"from_date={thirty_days_ago}" in url_str
            assert f"to_date={today}" in url_str
            return httpx.Response(
                200,
                json={
                    "computed_at": "2024-01-15T10:00:00",
                    "data": {},
                    "meta": {},
                },
            )

        with create_mock_client(test_credentials, handler) as client:
            client.query_saved_report(bookmark_id=12345, bookmark_type="funnels")

    def test_query_saved_report_funnels_uses_provided_dates(
        self, test_credentials: Credentials
    ) -> None:
        """query_saved_report(bookmark_type='funnels', from_date, to_date) uses provided dates."""

        def handler(request: httpx.Request) -> httpx.Response:
            url_str = str(request.url)
            assert "from_date=2024-06-01" in url_str
            assert "to_date=2024-06-30" in url_str
            return httpx.Response(
                200,
                json={
                    "computed_at": "2024-06-30T10:00:00",
                    "data": {},
                    "meta": {},
                },
            )

        with create_mock_client(test_credentials, handler) as client:
            client.query_saved_report(
                bookmark_id=12345,
                bookmark_type="funnels",
                from_date="2024-06-01",
                to_date="2024-06-30",
            )

    def test_query_saved_report_retention_routes_to_retention_endpoint(
        self, test_credentials: Credentials
    ) -> None:
        """query_saved_report(bookmark_type='retention') should call /retention."""

        def handler(request: httpx.Request) -> httpx.Response:
            assert "/api/query/retention" in str(request.url)
            assert "bookmark_id=12345" in str(request.url)
            return httpx.Response(
                200,
                json={
                    "2024-01-01": {"first": 100, "counts": [100, 80, 60], "rates": []},
                },
            )

        with create_mock_client(test_credentials, handler) as client:
            client.query_saved_report(bookmark_id=12345, bookmark_type="retention")

    def test_query_saved_report_flows_routes_to_arb_funnels(
        self, test_credentials: Credentials
    ) -> None:
        """query_saved_report(bookmark_type='flows') should call /arb_funnels."""

        def handler(request: httpx.Request) -> httpx.Response:
            url_str = str(request.url)
            assert "/api/query/arb_funnels" in url_str
            assert "bookmark_id=12345" in url_str
            assert "query_type=flows_sankey" in url_str
            return httpx.Response(
                200,
                json={
                    "computed_at": "2024-01-15T10:00:00",
                    "steps": [],
                    "breakdowns": [],
                    "overallConversionRate": 0.0,
                },
            )

        with create_mock_client(test_credentials, handler) as client:
            client.query_saved_report(bookmark_id=12345, bookmark_type="flows")

    def test_query_saved_report_funnels_only_to_date_derives_from_date(
        self, test_credentials: Credentials
    ) -> None:
        """query_saved_report(bookmark_type='funnels', to_date) derives from_date correctly.

        When only to_date is provided, from_date should be derived as 30 days
        before to_date, not 30 days before today. This prevents inverted date
        ranges when querying historical data.
        """
        historical_to_date = "2023-06-15"
        expected_from_date = "2023-05-16"  # 30 days before 2023-06-15

        def handler(request: httpx.Request) -> httpx.Response:
            url_str = str(request.url)
            assert f"from_date={expected_from_date}" in url_str
            assert f"to_date={historical_to_date}" in url_str
            return httpx.Response(
                200,
                json={"computed_at": "2023-06-15T10:00:00", "data": {}, "meta": {}},
            )

        with create_mock_client(test_credentials, handler) as client:
            client.query_saved_report(
                bookmark_id=12345,
                bookmark_type="funnels",
                to_date=historical_to_date,
            )

    def test_query_saved_report_funnels_only_from_date_derives_to_date(
        self, test_credentials: Credentials
    ) -> None:
        """query_saved_report(bookmark_type='funnels', from_date) derives to_date correctly.

        When only from_date is provided, to_date should be derived as 30 days
        after from_date, but capped at today to avoid querying future dates.
        """
        historical_from_date = "2023-06-15"
        expected_to_date = "2023-07-15"  # 30 days after 2023-06-15

        def handler(request: httpx.Request) -> httpx.Response:
            url_str = str(request.url)
            assert f"from_date={historical_from_date}" in url_str
            assert f"to_date={expected_to_date}" in url_str
            return httpx.Response(
                200,
                json={"computed_at": "2023-07-15T10:00:00", "data": {}, "meta": {}},
            )

        with create_mock_client(test_credentials, handler) as client:
            client.query_saved_report(
                bookmark_id=12345,
                bookmark_type="funnels",
                from_date=historical_from_date,
            )
