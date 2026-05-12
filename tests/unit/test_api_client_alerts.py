# ruff: noqa: ARG001, ARG005
"""Unit tests for Alert API client methods (Phase 026).

Tests for:
- Alert CRUD: list, create, get, update, delete, bulk_delete
- Alert operations: count, history, test, screenshot, validate
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
) -> MixpanelAPIClient:
    """Create a client with mock transport (no workspace ID set).

    Alerts use maybe_scoped_path which defaults to project-scoped.

    Args:
        credentials: Authentication credentials.
        handler: Mock HTTP handler function.

    Returns:
        MixpanelAPIClient configured with mock transport.
    """
    transport = httpx.MockTransport(handler)
    return MixpanelAPIClient(session=credentials, _transport=transport)


def _alert_result(
    id: int = 1,
    name: str = "Test Alert",
) -> dict[str, Any]:
    """Return a minimal alert dict matching the API shape.

    Args:
        id: Alert ID.
        name: Alert name.

    Returns:
        Dict that can be parsed into a CustomAlert model.
    """
    return {
        "id": id,
        "name": name,
        "condition": {"operator": "less_than", "value": 100},
        "frequency": 86400,
        "paused": False,
        "subscriptions": [{"type": "email", "value": "test@co.com"}],
        "created": "2026-01-01T00:00:00Z",
        "modified": "2026-01-01T00:00:00Z",
        "valid": True,
    }


# =============================================================================
# Alert CRUD Tests
# =============================================================================


class TestListAlerts:
    """Tests for list_alerts() API client method."""

    def test_returns_alert_list(self, oauth_credentials: Session) -> None:
        """list_alerts() returns a list of alert dicts."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return sample alert list."""
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": [
                        _alert_result(1, "Alert A"),
                        _alert_result(2, "Alert B"),
                    ],
                },
            )

        client = create_mock_client(oauth_credentials, handler)
        with client:
            result = client.list_alerts()

        assert len(result) == 2
        assert result[0]["id"] == 1
        assert result[1]["name"] == "Alert B"

    def test_uses_maybe_scoped_path(self, oauth_credentials: Session) -> None:
        """list_alerts() uses maybe_scoped_path for URL building."""
        captured_urls: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture URL."""
            captured_urls.append(str(request.url))
            return httpx.Response(200, json={"status": "ok", "results": []})

        client = create_mock_client(oauth_credentials, handler)
        with client:
            client.list_alerts()

        assert "/alerts/custom/" in captured_urls[0]

    def test_bookmark_id_param(self, oauth_credentials: Session) -> None:
        """list_alerts(bookmark_id=42) passes query param."""
        captured_urls: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture URL."""
            captured_urls.append(str(request.url))
            return httpx.Response(200, json={"status": "ok", "results": []})

        client = create_mock_client(oauth_credentials, handler)
        with client:
            client.list_alerts(bookmark_id=42)

        assert "bookmark_id=42" in captured_urls[0]

    def test_skip_user_filter_param(self, oauth_credentials: Session) -> None:
        """list_alerts(skip_user_filter=True) passes query param."""
        captured_urls: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture URL."""
            captured_urls.append(str(request.url))
            return httpx.Response(200, json={"status": "ok", "results": []})

        client = create_mock_client(oauth_credentials, handler)
        with client:
            client.list_alerts(skip_user_filter=True)

        assert "skip_user_filter=true" in captured_urls[0]

    def test_empty_result(self, oauth_credentials: Session) -> None:
        """list_alerts() returns empty list when no alerts exist."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return empty results."""
            return httpx.Response(200, json={"status": "ok", "results": []})

        client = create_mock_client(oauth_credentials, handler)
        with client:
            result = client.list_alerts()

        assert result == []

    def test_uses_get_method(self, oauth_credentials: Session) -> None:
        """list_alerts() uses GET HTTP method."""
        captured_methods: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture HTTP method."""
            captured_methods.append(request.method)
            return httpx.Response(200, json={"status": "ok", "results": []})

        client = create_mock_client(oauth_credentials, handler)
        with client:
            client.list_alerts()

        assert captured_methods[0] == "GET"


class TestCreateAlert:
    """Tests for create_alert() API client method."""

    def test_creates_alert(self, oauth_credentials: Session) -> None:
        """create_alert() sends POST and returns alert dict."""
        captured: list[tuple[str, Any]] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture request method and body."""
            captured.append((request.method, json.loads(request.content)))
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": _alert_result(99, "New Alert"),
                },
            )

        client = create_mock_client(oauth_credentials, handler)
        with client:
            result = client.create_alert({"name": "New Alert", "frequency": 86400})

        assert captured[0][0] == "POST"
        assert captured[0][1]["name"] == "New Alert"
        assert result["id"] == 99

    def test_url_path(self, oauth_credentials: Session) -> None:
        """create_alert() posts to the alerts/custom/ endpoint."""
        captured_urls: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture URL."""
            captured_urls.append(str(request.url))
            return httpx.Response(
                200,
                json={"status": "ok", "results": _alert_result()},
            )

        client = create_mock_client(oauth_credentials, handler)
        with client:
            client.create_alert({"name": "X"})

        assert "/alerts/custom/" in captured_urls[0]


class TestGetAlert:
    """Tests for get_alert() API client method."""

    def test_gets_alert_by_id(self, oauth_credentials: Session) -> None:
        """get_alert() sends GET with alert ID in path."""
        captured_urls: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture URL and return alert."""
            captured_urls.append(str(request.url))
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": _alert_result(42, "My Alert"),
                },
            )

        client = create_mock_client(oauth_credentials, handler)
        with client:
            result = client.get_alert(42)

        assert "/alerts/custom/42/" in captured_urls[0]
        assert result["id"] == 42

    def test_uses_get_method(self, oauth_credentials: Session) -> None:
        """get_alert() uses GET HTTP method."""
        captured_methods: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture HTTP method."""
            captured_methods.append(request.method)
            return httpx.Response(
                200,
                json={"status": "ok", "results": _alert_result()},
            )

        client = create_mock_client(oauth_credentials, handler)
        with client:
            client.get_alert(1)

        assert captured_methods[0] == "GET"


class TestUpdateAlert:
    """Tests for update_alert() API client method."""

    def test_updates_alert(self, oauth_credentials: Session) -> None:
        """update_alert() sends PATCH with body."""
        captured: list[tuple[str, Any]] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture method and body."""
            captured.append((request.method, json.loads(request.content)))
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": _alert_result(42, "Updated"),
                },
            )

        client = create_mock_client(oauth_credentials, handler)
        with client:
            result = client.update_alert(42, {"name": "Updated"})

        assert captured[0][0] == "PATCH"
        assert captured[0][1]["name"] == "Updated"
        assert result["name"] == "Updated"

    def test_url_path(self, oauth_credentials: Session) -> None:
        """update_alert() targets the correct alert ID in URL."""
        captured_urls: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture URL."""
            captured_urls.append(str(request.url))
            return httpx.Response(
                200,
                json={"status": "ok", "results": _alert_result()},
            )

        client = create_mock_client(oauth_credentials, handler)
        with client:
            client.update_alert(42, {"name": "X"})

        assert "/alerts/custom/42/" in captured_urls[0]


class TestDeleteAlert:
    """Tests for delete_alert() API client method."""

    def test_deletes_alert(self, oauth_credentials: Session) -> None:
        """delete_alert() sends DELETE request."""
        captured_methods: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture method."""
            captured_methods.append(request.method)
            return httpx.Response(204)

        client = create_mock_client(oauth_credentials, handler)
        with client:
            client.delete_alert(42)

        assert captured_methods[0] == "DELETE"

    def test_url_path(self, oauth_credentials: Session) -> None:
        """delete_alert() targets the correct alert ID in URL."""
        captured_urls: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture URL."""
            captured_urls.append(str(request.url))
            return httpx.Response(204)

        client = create_mock_client(oauth_credentials, handler)
        with client:
            client.delete_alert(42)

        assert "/alerts/custom/42/" in captured_urls[0]


class TestBulkDeleteAlerts:
    """Tests for bulk_delete_alerts() API client method."""

    def test_bulk_deletes(self, oauth_credentials: Session) -> None:
        """bulk_delete_alerts() sends POST with alert_ids."""
        captured: list[tuple[str, Any]] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture method and body."""
            captured.append((request.method, json.loads(request.content)))
            return httpx.Response(200, json={"status": "ok", "results": {}})

        client = create_mock_client(oauth_credentials, handler)
        with client:
            client.bulk_delete_alerts([1, 2, 3])

        assert captured[0][0] == "POST"
        assert captured[0][1] == {"alert_ids": [1, 2, 3]}

    def test_url_path(self, oauth_credentials: Session) -> None:
        """bulk_delete_alerts() posts to bulk-delete endpoint."""
        captured_urls: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture URL."""
            captured_urls.append(str(request.url))
            return httpx.Response(200, json={"status": "ok", "results": {}})

        client = create_mock_client(oauth_credentials, handler)
        with client:
            client.bulk_delete_alerts([1])

        assert "/alerts/custom/bulk-delete/" in captured_urls[0]


# =============================================================================
# Alert Operation Tests
# =============================================================================


class TestGetAlertCount:
    """Tests for get_alert_count() API client method."""

    def test_gets_count(self, oauth_credentials: Session) -> None:
        """get_alert_count() returns count dict."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return count response."""
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": {
                        "anomaly_alerts_count": 5,
                        "alert_limit": 100,
                        "is_below_limit": True,
                    },
                },
            )

        client = create_mock_client(oauth_credentials, handler)
        with client:
            result = client.get_alert_count()

        assert result["anomaly_alerts_count"] == 5
        assert result["alert_limit"] == 100

    def test_url_path(self, oauth_credentials: Session) -> None:
        """get_alert_count() targets alert-count endpoint."""
        captured_urls: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture URL."""
            captured_urls.append(str(request.url))
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": {
                        "anomaly_alerts_count": 0,
                        "alert_limit": 10,
                        "is_below_limit": True,
                    },
                },
            )

        client = create_mock_client(oauth_credentials, handler)
        with client:
            client.get_alert_count()

        assert "/alerts/custom/alert-count/" in captured_urls[0]

    def test_with_type_param(self, oauth_credentials: Session) -> None:
        """get_alert_count(alert_type='anomaly') passes type param."""
        captured_urls: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture URL."""
            captured_urls.append(str(request.url))
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": {
                        "anomaly_alerts_count": 2,
                        "alert_limit": 50,
                        "is_below_limit": True,
                    },
                },
            )

        client = create_mock_client(oauth_credentials, handler)
        with client:
            client.get_alert_count(alert_type="anomaly")

        assert "type=anomaly" in captured_urls[0]


class TestGetAlertHistory:
    """Tests for get_alert_history() API client method."""

    def test_gets_history(self, oauth_credentials: Session) -> None:
        """get_alert_history() returns history response."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return history response."""
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": {
                        "results": [{"fired": True, "timestamp": "2026-01-01"}],
                        "pagination": {"page_size": 20},
                    },
                },
            )

        client = create_mock_client(oauth_credentials, handler)
        with client:
            result = client.get_alert_history(42)

        assert len(result["results"]) == 1
        assert result["pagination"]["page_size"] == 20

    def test_url_path(self, oauth_credentials: Session) -> None:
        """get_alert_history() targets history endpoint."""
        captured_urls: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture URL."""
            captured_urls.append(str(request.url))
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": {"results": [], "pagination": {"page_size": 20}},
                },
            )

        client = create_mock_client(oauth_credentials, handler)
        with client:
            client.get_alert_history(42)

        assert "/alerts/custom/42/history/" in captured_urls[0]

    def test_with_pagination_params(self, oauth_credentials: Session) -> None:
        """get_alert_history() passes pagination query params."""
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
            client.get_alert_history(42, page_size=10, next_cursor="abc")

        url = captured_urls[0]
        assert "page_size=10" in url
        assert "next_cursor=abc" in url


class TestTestAlert:
    """Tests for test_alert() API client method."""

    def test_sends_test(self, oauth_credentials: Session) -> None:
        """test_alert() sends POST and returns result."""
        captured: list[tuple[str, Any]] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture method and body."""
            captured.append((request.method, json.loads(request.content)))
            return httpx.Response(
                200,
                json={"status": "ok", "results": {"status": "sent"}},
            )

        client = create_mock_client(oauth_credentials, handler)
        with client:
            result = client.test_alert({"name": "Test", "frequency": 86400})

        assert captured[0][0] == "POST"
        assert result["status"] == "sent"

    def test_url_path(self, oauth_credentials: Session) -> None:
        """test_alert() posts to test endpoint."""
        captured_urls: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture URL."""
            captured_urls.append(str(request.url))
            return httpx.Response(
                200,
                json={"status": "ok", "results": {}},
            )

        client = create_mock_client(oauth_credentials, handler)
        with client:
            client.test_alert({"name": "X"})

        assert "/alerts/custom/test/" in captured_urls[0]


class TestGetAlertScreenshotUrl:
    """Tests for get_alert_screenshot_url() API client method."""

    def test_gets_url(self, oauth_credentials: Session) -> None:
        """get_alert_screenshot_url() returns signed URL dict."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return screenshot response."""
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": {"signed_url": "https://storage.googleapis.com/abc.png"},
                },
            )

        client = create_mock_client(oauth_credentials, handler)
        with client:
            result = client.get_alert_screenshot_url("screenshots/abc.png")

        assert result["signed_url"] == "https://storage.googleapis.com/abc.png"

    def test_url_path(self, oauth_credentials: Session) -> None:
        """get_alert_screenshot_url() targets screenshot endpoint."""
        captured_urls: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture URL."""
            captured_urls.append(str(request.url))
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": {"signed_url": "https://example.com"},
                },
            )

        client = create_mock_client(oauth_credentials, handler)
        with client:
            client.get_alert_screenshot_url("key")

        assert "/alerts/custom/screenshot/" in captured_urls[0]
        assert "gcs_key=key" in captured_urls[0]


class TestValidateAlertsForBookmark:
    """Tests for validate_alerts_for_bookmark() API client method."""

    def test_validates(self, oauth_credentials: Session) -> None:
        """validate_alerts_for_bookmark() sends POST and returns result."""
        captured: list[tuple[str, Any]] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture method and body."""
            captured.append((request.method, json.loads(request.content)))
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": {
                        "alert_validations": [],
                        "invalid_count": 0,
                    },
                },
            )

        client = create_mock_client(oauth_credentials, handler)
        with client:
            result = client.validate_alerts_for_bookmark(
                {
                    "alert_ids": [1, 2],
                    "bookmark_type": "insights",
                    "bookmark_params": {"event": "Signup"},
                }
            )

        assert captured[0][0] == "POST"
        assert result["invalid_count"] == 0

    def test_url_path(self, oauth_credentials: Session) -> None:
        """validate_alerts_for_bookmark() targets validate endpoint."""
        captured_urls: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture URL."""
            captured_urls.append(str(request.url))
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": {"alert_validations": [], "invalid_count": 0},
                },
            )

        client = create_mock_client(oauth_credentials, handler)
        with client:
            client.validate_alerts_for_bookmark({"alert_ids": [1]})

        assert "/alerts/custom/validate-alerts-for-bookmark/" in captured_urls[0]
