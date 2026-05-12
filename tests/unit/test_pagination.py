"""Unit tests for cursor-based pagination helper.

Tests for paginate_all() function that iterates through paginated App API responses.
"""
# ruff: noqa: ARG001, ARG005

from __future__ import annotations

import itertools
from collections.abc import Callable
from unittest.mock import patch

import httpx
import pytest

from mixpanel_headless._internal.api_client import MixpanelAPIClient
from mixpanel_headless._internal.auth.session import Session
from mixpanel_headless._internal.pagination import paginate_all
from mixpanel_headless.exceptions import (
    AuthenticationError,
    MixpanelHeadlessError,
    RateLimitError,
    ServerError,
)
from tests.conftest import make_session

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def oauth_credentials() -> Session:
    """Create OAuth credentials for pagination testing."""
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
# T028: Cursor pagination tests
# =============================================================================


class TestPaginateAll:
    """Test paginate_all() cursor pagination helper."""

    def test_yields_all_results_across_pages(self, oauth_credentials: Session) -> None:
        """paginate_all() should yield all results from multiple pages."""
        call_count = 0

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal call_count
            call_count += 1
            cursor = request.url.params.get("cursor")

            if cursor is None:
                # First page
                return httpx.Response(
                    200,
                    json={
                        "status": "ok",
                        "results": [{"id": 1}, {"id": 2}],
                        "pagination": {
                            "page_size": 2,
                            "next_cursor": "cursor_page2",
                        },
                    },
                )
            elif cursor == "cursor_page2":
                # Second page
                return httpx.Response(
                    200,
                    json={
                        "status": "ok",
                        "results": [{"id": 3}],
                        "pagination": {
                            "page_size": 2,
                            "next_cursor": None,
                        },
                    },
                )
            else:
                return httpx.Response(404, json={"error": "Unknown cursor"})

        client = create_mock_client(oauth_credentials, handler)
        with client:
            items = list(paginate_all(client, "/projects/12345/dashboards"))

        assert items == [{"id": 1}, {"id": 2}, {"id": 3}]
        assert call_count == 2

    def test_follows_next_cursor_until_none(self, oauth_credentials: Session) -> None:
        """paginate_all() should stop when next_cursor is None."""
        cursors_seen: list[str | None] = []

        def handler(request: httpx.Request) -> httpx.Response:
            cursor = request.url.params.get("cursor")
            cursors_seen.append(cursor)

            if cursor is None:
                return httpx.Response(
                    200,
                    json={
                        "status": "ok",
                        "results": [{"id": 1}],
                        "pagination": {
                            "page_size": 1,
                            "next_cursor": "c2",
                        },
                    },
                )
            elif cursor == "c2":
                return httpx.Response(
                    200,
                    json={
                        "status": "ok",
                        "results": [{"id": 2}],
                        "pagination": {
                            "page_size": 1,
                            "next_cursor": "c3",
                        },
                    },
                )
            else:
                return httpx.Response(
                    200,
                    json={
                        "status": "ok",
                        "results": [{"id": 3}],
                        "pagination": {
                            "page_size": 1,
                            "next_cursor": None,
                        },
                    },
                )

        client = create_mock_client(oauth_credentials, handler)
        with client:
            items = list(paginate_all(client, "/projects/12345/items"))

        assert len(items) == 3
        assert cursors_seen == [None, "c2", "c3"]

    def test_handles_empty_results(self, oauth_credentials: Session) -> None:
        """paginate_all() should handle empty results gracefully."""

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": [],
                    "pagination": {
                        "page_size": 100,
                        "next_cursor": None,
                    },
                },
            )

        client = create_mock_client(oauth_credentials, handler)
        with client:
            items = list(paginate_all(client, "/projects/12345/dashboards"))

        assert items == []

    def test_handles_missing_pagination_field(self, oauth_credentials: Session) -> None:
        """paginate_all() should treat missing pagination as single page."""

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": [{"id": 1}, {"id": 2}],
                },
            )

        client = create_mock_client(oauth_credentials, handler)
        with client:
            items = list(paginate_all(client, "/projects/12345/dashboards"))

        assert items == [{"id": 1}, {"id": 2}]

    def test_respects_page_size_parameter(self, oauth_credentials: Session) -> None:
        """paginate_all() should pass page_size as query parameter."""
        captured_params: list[dict[str, str]] = []

        def handler(request: httpx.Request) -> httpx.Response:
            captured_params.append(dict(request.url.params))
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": [{"id": 1}],
                    "pagination": {"page_size": 25, "next_cursor": None},
                },
            )

        client = create_mock_client(oauth_credentials, handler)
        with client:
            list(paginate_all(client, "/projects/12345/dashboards", page_size=25))

        assert captured_params[0]["page_size"] == "25"

    def test_passes_additional_params(self, oauth_credentials: Session) -> None:
        """paginate_all() should merge extra params with pagination params."""
        captured_params: list[dict[str, str]] = []

        def handler(request: httpx.Request) -> httpx.Response:
            captured_params.append(dict(request.url.params))
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": [],
                    "pagination": {"page_size": 100, "next_cursor": None},
                },
            )

        client = create_mock_client(oauth_credentials, handler)
        with client:
            list(
                paginate_all(
                    client,
                    "/projects/12345/dashboards",
                    params={"include_archived": "true"},
                )
            )

        assert captured_params[0]["include_archived"] == "true"

    def test_injects_query_origin_telemetry(self, oauth_credentials: Session) -> None:
        """paginate_all() should auto-inject the query_origin telemetry param.

        Locks the literal value so a future typo or accidental rename of the
        telemetry tag is caught at PR time rather than silently corrupting
        Mixpanel-internal analytics dashboards.
        """
        captured_params: list[dict[str, str]] = []

        def handler(request: httpx.Request) -> httpx.Response:
            captured_params.append(dict(request.url.params))
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": [{"id": 1}],
                    "pagination": {"page_size": 100, "next_cursor": None},
                },
            )

        client = create_mock_client(oauth_credentials, handler)
        with client:
            list(paginate_all(client, "/projects/12345/dashboards"))

        assert captured_params[0]["query_origin"] == "mixpanel-headless"

    def test_canonical_query_origin_wins_over_caller(
        self, oauth_credentials: Session
    ) -> None:
        """Caller-supplied ``query_origin`` cannot override the canonical value.

        The telemetry tag is non-negotiable: even if a caller passes a spoofed
        ``query_origin`` in ``params``, the canonical ``mixpanel-headless``
        value must win.
        """
        captured_params: list[dict[str, str]] = []

        def handler(request: httpx.Request) -> httpx.Response:
            captured_params.append(dict(request.url.params))
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": [{"id": 1}],
                    "pagination": {"page_size": 100, "next_cursor": None},
                },
            )

        client = create_mock_client(oauth_credentials, handler)
        with client:
            list(
                paginate_all(
                    client,
                    "/projects/12345/dashboards",
                    params={"query_origin": "spoofed-by-caller"},
                )
            )

        assert captured_params[0]["query_origin"] == "mixpanel-headless"

    def test_handles_response_without_results_key(
        self, oauth_credentials: Session
    ) -> None:
        """paginate_all() should handle responses where app_request returns a list."""

        def handler(request: httpx.Request) -> httpx.Response:
            # app_request unwraps results, so if the API returns results as
            # a list directly, paginate_all gets a list
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": [{"id": 1}],
                },
            )

        client = create_mock_client(oauth_credentials, handler)
        with client:
            items = list(paginate_all(client, "/projects/12345/items"))

        assert items == [{"id": 1}]


class TestPaginateAllRobustness:
    """Test paginate_all() robustness against infinite loops and bad responses."""

    def test_infinite_loop_same_cursor(self, oauth_credentials: Session) -> None:
        """Verify pagination terminates when the server returns the same cursor forever.

        A server that always returns the same next_cursor would cause an
        infinite loop without the MAX_PAGES guard.
        """

        def handler(request: httpx.Request) -> httpx.Response:
            """Return the same cursor on every page.

            Args:
                request: The incoming request.

            Returns:
                Response with a constant cursor.
            """
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": [{"id": 1}],
                    "pagination": {
                        "page_size": 1,
                        "next_cursor": "same",
                    },
                },
            )

        # Use a small MAX_PAGES for the test to avoid long runtime
        with patch("mixpanel_headless._internal.pagination.MAX_PAGES", 50):
            client = create_mock_client(oauth_credentials, handler)
            with (
                client,
                pytest.raises(MixpanelHeadlessError, match="maximum page limit"),
            ):
                # Consume all items — should raise before 15000
                list(
                    itertools.islice(
                        paginate_all(client, "/projects/12345/items"), 15000
                    )
                )

    def test_non_json_response(self, oauth_credentials: Session) -> None:
        """Verify pagination raises a clear error for non-JSON responses.

        If the server returns HTML or other non-JSON content, the function
        should raise MixpanelHeadlessError rather than a raw JSONDecodeError.
        """

        def handler(request: httpx.Request) -> httpx.Response:
            """Return HTML instead of JSON.

            Args:
                request: The incoming request.

            Returns:
                HTML response.
            """
            return httpx.Response(
                200,
                content=b"<html><body>Error</body></html>",
                headers={"content-type": "text/html"},
            )

        client = create_mock_client(oauth_credentials, handler)
        with client, pytest.raises(MixpanelHeadlessError, match="Non-JSON response"):
            list(paginate_all(client, "/projects/12345/items"))

    def test_http_429_mid_pagination(self, oauth_credentials: Session) -> None:
        """Verify that a 429 on the second page raises RateLimitError.

        Rate limits can occur mid-pagination; the error should propagate
        as a proper RateLimitError.
        """
        call_count = 0

        def handler(request: httpx.Request) -> httpx.Response:
            """Return OK on first page, 429 on second.

            Args:
                request: The incoming request.

            Returns:
                Success or rate-limit response.
            """
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return httpx.Response(
                    200,
                    json={
                        "status": "ok",
                        "results": [{"id": 1}],
                        "pagination": {"page_size": 1, "next_cursor": "c2"},
                    },
                )
            return httpx.Response(
                429,
                json={"error": "rate_limited"},
                headers={"Retry-After": "30"},
            )

        client = create_mock_client(oauth_credentials, handler)
        with client, pytest.raises(RateLimitError):
            list(paginate_all(client, "/projects/12345/items"))

    def test_http_500_mid_pagination(self, oauth_credentials: Session) -> None:
        """Verify that a 500 on the second page raises ServerError.

        Server errors during pagination should be mapped to ServerError.
        """
        call_count = 0

        def handler(request: httpx.Request) -> httpx.Response:
            """Return OK on first page, 500 on second.

            Args:
                request: The incoming request.

            Returns:
                Success or server-error response.
            """
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return httpx.Response(
                    200,
                    json={
                        "status": "ok",
                        "results": [{"id": 1}],
                        "pagination": {"page_size": 1, "next_cursor": "c2"},
                    },
                )
            return httpx.Response(500, json={"error": "internal_error"})

        client = create_mock_client(oauth_credentials, handler)
        with client, pytest.raises(ServerError):
            list(paginate_all(client, "/projects/12345/items"))

    def test_http_401_mid_pagination(self, oauth_credentials: Session) -> None:
        """Verify that a 401 on the second page raises AuthenticationError.

        Token expiry during pagination should be mapped to AuthenticationError.
        """
        call_count = 0

        def handler(request: httpx.Request) -> httpx.Response:
            """Return OK on first page, 401 on second.

            Args:
                request: The incoming request.

            Returns:
                Success or auth-error response.
            """
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return httpx.Response(
                    200,
                    json={
                        "status": "ok",
                        "results": [{"id": 1}],
                        "pagination": {"page_size": 1, "next_cursor": "c2"},
                    },
                )
            return httpx.Response(401, json={"error": "unauthorized"})

        client = create_mock_client(oauth_credentials, handler)
        with client, pytest.raises(AuthenticationError):
            list(paginate_all(client, "/projects/12345/items"))
