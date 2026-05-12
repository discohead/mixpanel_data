# ruff: noqa: ARG001, ARG005
"""Unit tests for Workspace alert methods (Phase 026).

Tests for alert CRUD operations and monitoring methods on the Workspace
facade. Each method delegates to MixpanelAPIClient and returns typed objects.

Verifies:
- Alert CRUD: list, create, get, update, delete, bulk_delete
- Alert operations: count, history, test, screenshot, validate
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
    AlertCount,
    AlertHistoryResponse,
    AlertScreenshotResponse,
    CreateAlertParams,
    CustomAlert,
    UpdateAlertParams,
    ValidateAlertsForBookmarkParams,
    ValidateAlertsForBookmarkResponse,
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
    return Workspace(
        session=_TEST_SESSION,
        _api_client=client,
    )


# =============================================================================
# Mock response data
# =============================================================================


def _alert_json(
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
# TestWorkspaceAlertCRUD
# =============================================================================


class TestWorkspaceAlertCRUD:
    """Tests for Workspace alert CRUD methods."""

    def test_list_alerts(self, temp_dir: Path) -> None:
        """list_alerts() returns list of CustomAlert objects."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return alert list."""
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": [
                        _alert_json(1, "Alert A"),
                        _alert_json(2, "Alert B"),
                    ],
                },
            )

        ws = _make_workspace(temp_dir, handler)
        alerts = ws.list_alerts()

        assert len(alerts) == 2
        assert isinstance(alerts[0], CustomAlert)
        assert alerts[0].id == 1
        assert alerts[0].name == "Alert A"
        assert alerts[1].id == 2

    def test_list_alerts_empty(self, temp_dir: Path) -> None:
        """list_alerts() returns empty list when no alerts exist."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return empty alert list."""
            return httpx.Response(200, json={"status": "ok", "results": []})

        ws = _make_workspace(temp_dir, handler)
        alerts = ws.list_alerts()

        assert alerts == []

    def test_list_alerts_with_bookmark_filter(self, temp_dir: Path) -> None:
        """list_alerts(bookmark_id=42) passes param to API."""
        captured_url: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture URL."""
            captured_url.append(str(request.url))
            return httpx.Response(
                200,
                json={"status": "ok", "results": [_alert_json()]},
            )

        ws = _make_workspace(temp_dir, handler)
        alerts = ws.list_alerts(bookmark_id=42)

        assert len(alerts) == 1
        assert "bookmark_id=42" in captured_url[0]

    def test_create_alert(self, temp_dir: Path) -> None:
        """create_alert() returns the created CustomAlert."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return created alert."""
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": _alert_json(99, "New Alert"),
                },
            )

        ws = _make_workspace(temp_dir, handler)
        params = CreateAlertParams(
            bookmark_id=123,
            name="New Alert",
            condition={"operator": "less_than", "value": 50},
            frequency=86400,
            paused=False,
            subscriptions=[],
        )
        alert = ws.create_alert(params)

        assert isinstance(alert, CustomAlert)
        assert alert.id == 99
        assert alert.name == "New Alert"

    def test_get_alert(self, temp_dir: Path) -> None:
        """get_alert() returns a single CustomAlert by ID."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return single alert."""
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": _alert_json(42, "My Alert"),
                },
            )

        ws = _make_workspace(temp_dir, handler)
        alert = ws.get_alert(42)

        assert isinstance(alert, CustomAlert)
        assert alert.id == 42
        assert alert.name == "My Alert"

    def test_update_alert(self, temp_dir: Path) -> None:
        """update_alert() returns the updated CustomAlert."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return updated alert."""
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": _alert_json(42, "Renamed"),
                },
            )

        ws = _make_workspace(temp_dir, handler)
        params = UpdateAlertParams(name="Renamed")
        alert = ws.update_alert(42, params)

        assert isinstance(alert, CustomAlert)
        assert alert.name == "Renamed"

    def test_delete_alert(self, temp_dir: Path) -> None:
        """delete_alert() returns None on success."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return 204 for delete."""
            return httpx.Response(204)

        ws = _make_workspace(temp_dir, handler)
        ws.delete_alert(42)  # Should not raise

    def test_bulk_delete_alerts(self, temp_dir: Path) -> None:
        """bulk_delete_alerts() returns None on success."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return 200 for bulk delete."""
            return httpx.Response(200, json={"status": "ok", "results": {}})

        ws = _make_workspace(temp_dir, handler)
        ws.bulk_delete_alerts([1, 2, 3])  # Should not raise


# =============================================================================
# TestWorkspaceAlertOperations
# =============================================================================


class TestWorkspaceAlertOperations:
    """Tests for Workspace alert monitoring and utility methods."""

    def test_get_alert_count(self, temp_dir: Path) -> None:
        """get_alert_count() returns AlertCount."""

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

        ws = _make_workspace(temp_dir, handler)
        count = ws.get_alert_count()

        assert isinstance(count, AlertCount)
        assert count.anomaly_alerts_count == 5
        assert count.alert_limit == 100
        assert count.is_below_limit is True

    def test_get_alert_count_with_type(self, temp_dir: Path) -> None:
        """get_alert_count(alert_type='anomaly') passes param."""
        captured_url: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture URL."""
            captured_url.append(str(request.url))
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

        ws = _make_workspace(temp_dir, handler)
        ws.get_alert_count(alert_type="anomaly")

        assert "type=anomaly" in captured_url[0]

    def test_get_alert_history(self, temp_dir: Path) -> None:
        """get_alert_history() returns AlertHistoryResponse."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return history response."""
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": {
                        "results": [{"fired": True}],
                        "pagination": {"page_size": 20},
                    },
                },
            )

        ws = _make_workspace(temp_dir, handler)
        history = ws.get_alert_history(42)

        assert isinstance(history, AlertHistoryResponse)
        assert len(history.results) == 1
        assert history.pagination is not None
        assert history.pagination.page_size == 20

    def test_get_alert_history_empty(self, temp_dir: Path) -> None:
        """get_alert_history() handles empty history."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return empty history."""
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
        history = ws.get_alert_history(42)

        assert isinstance(history, AlertHistoryResponse)
        assert history.results == []

    def test_test_alert(self, temp_dir: Path) -> None:
        """test_alert() returns opaque dict."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return test result."""
            return httpx.Response(
                200,
                json={"status": "ok", "results": {"status": "sent"}},
            )

        ws = _make_workspace(temp_dir, handler)
        params = CreateAlertParams(
            bookmark_id=123,
            name="Test",
            condition={},
            frequency=86400,
            paused=False,
            subscriptions=[],
        )
        result = ws.test_alert(params)

        assert isinstance(result, dict)
        assert result["status"] == "sent"

    def test_get_alert_screenshot_url(self, temp_dir: Path) -> None:
        """get_alert_screenshot_url() returns AlertScreenshotResponse."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return screenshot response."""
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": {"signed_url": "https://storage.googleapis.com/abc.png"},
                },
            )

        ws = _make_workspace(temp_dir, handler)
        resp = ws.get_alert_screenshot_url("screenshots/abc.png")

        assert isinstance(resp, AlertScreenshotResponse)
        assert resp.signed_url == "https://storage.googleapis.com/abc.png"

    def test_validate_alerts_for_bookmark(self, temp_dir: Path) -> None:
        """validate_alerts_for_bookmark() returns ValidateAlertsForBookmarkResponse."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return validation response."""
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": {
                        "alert_validations": [
                            {"alert_id": 1, "alert_name": "X", "valid": True},
                        ],
                        "invalid_count": 0,
                    },
                },
            )

        ws = _make_workspace(temp_dir, handler)
        params = ValidateAlertsForBookmarkParams(
            alert_ids=[1],
            bookmark_type="insights",
            bookmark_params={"event": "Signup"},
        )
        resp = ws.validate_alerts_for_bookmark(params)

        assert isinstance(resp, ValidateAlertsForBookmarkResponse)
        assert len(resp.alert_validations) == 1
        assert resp.invalid_count == 0
