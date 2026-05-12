# ruff: noqa: ARG001, ARG005
"""Unit tests for Webhook API client methods (Phase 026).

Tests for:
- Webhook CRUD: list, create, update, delete
- Webhook testing: test connectivity
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
    """Create a client with mock transport for webhook testing.

    Webhooks use maybe_scoped_path which works without workspace ID.

    Args:
        credentials: Authentication credentials.
        handler: Mock HTTP handler function.

    Returns:
        MixpanelAPIClient configured with mock transport.
    """
    transport = httpx.MockTransport(handler)
    return MixpanelAPIClient(session=credentials, _transport=transport)


def _webhook_result(
    id: str = "wh-uuid-123",
    name: str = "Test Webhook",
    url: str = "https://example.com/webhook",
) -> dict[str, Any]:
    """Return a minimal webhook dict matching the API shape.

    Args:
        id: Webhook UUID.
        name: Webhook name.
        url: Webhook URL.

    Returns:
        Dict that can be parsed into a ProjectWebhook model.
    """
    return {
        "id": id,
        "name": name,
        "url": url,
        "is_enabled": True,
        "auth_type": None,
        "created": "2026-01-01T00:00:00Z",
        "modified": "2026-01-01T00:00:00Z",
    }


def _mutation_result(
    id: str = "wh-uuid-123",
    name: str = "Test Webhook",
) -> dict[str, Any]:
    """Return a webhook mutation result dict.

    Args:
        id: Webhook UUID.
        name: Webhook name.

    Returns:
        Dict with id and name fields.
    """
    return {"id": id, "name": name}


# =============================================================================
# List Webhooks Tests
# =============================================================================


class TestListWebhooks:
    """Tests for list_webhooks() API client method."""

    def test_returns_webhook_list(self, oauth_credentials: Session) -> None:
        """list_webhooks() returns a list of webhook dicts."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return sample webhook list."""
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": [
                        _webhook_result("id-1", "Hook A"),
                        _webhook_result("id-2", "Hook B"),
                    ],
                },
            )

        client = create_mock_client(oauth_credentials, handler)
        with client:
            result = client.list_webhooks()

        assert len(result) == 2
        assert result[0]["id"] == "id-1"
        assert result[1]["name"] == "Hook B"

    def test_url_path(self, oauth_credentials: Session) -> None:
        """list_webhooks() uses maybe_scoped_path for URL building."""
        captured_urls: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture URL."""
            captured_urls.append(str(request.url))
            return httpx.Response(200, json={"status": "ok", "results": []})

        client = create_mock_client(oauth_credentials, handler)
        with client:
            client.list_webhooks()

        assert "/webhooks/" in captured_urls[0]

    def test_empty_result(self, oauth_credentials: Session) -> None:
        """list_webhooks() returns empty list when no webhooks exist."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return empty results."""
            return httpx.Response(200, json={"status": "ok", "results": []})

        client = create_mock_client(oauth_credentials, handler)
        with client:
            result = client.list_webhooks()

        assert result == []

    def test_uses_get_method(self, oauth_credentials: Session) -> None:
        """list_webhooks() uses GET HTTP method."""
        captured_methods: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture HTTP method."""
            captured_methods.append(request.method)
            return httpx.Response(200, json={"status": "ok", "results": []})

        client = create_mock_client(oauth_credentials, handler)
        with client:
            client.list_webhooks()

        assert captured_methods[0] == "GET"


# =============================================================================
# Create Webhook Tests
# =============================================================================


class TestCreateWebhook:
    """Tests for create_webhook() API client method."""

    def test_creates_webhook(self, oauth_credentials: Session) -> None:
        """create_webhook() sends POST and returns mutation result."""
        captured: list[tuple[str, Any]] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture request method and body."""
            captured.append((request.method, json.loads(request.content)))
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": _mutation_result("new-id", "New Hook"),
                },
            )

        client = create_mock_client(oauth_credentials, handler)
        with client:
            result = client.create_webhook(
                {"name": "New Hook", "url": "https://example.com"}
            )

        assert captured[0][0] == "POST"
        assert captured[0][1]["name"] == "New Hook"
        assert result["id"] == "new-id"

    def test_url_path(self, oauth_credentials: Session) -> None:
        """create_webhook() posts to the webhooks endpoint."""
        captured_urls: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture URL."""
            captured_urls.append(str(request.url))
            return httpx.Response(
                200,
                json={"status": "ok", "results": _mutation_result()},
            )

        client = create_mock_client(oauth_credentials, handler)
        with client:
            client.create_webhook({"name": "X", "url": "https://x.com"})

        assert "/webhooks/" in captured_urls[0]


# =============================================================================
# Update Webhook Tests
# =============================================================================


class TestUpdateWebhook:
    """Tests for update_webhook() API client method."""

    def test_updates_webhook(self, oauth_credentials: Session) -> None:
        """update_webhook() sends PATCH with body."""
        captured: list[tuple[str, Any]] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture method and body."""
            captured.append((request.method, json.loads(request.content)))
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": _mutation_result("wh-uuid-123", "Updated"),
                },
            )

        client = create_mock_client(oauth_credentials, handler)
        with client:
            result = client.update_webhook("wh-uuid-123", {"name": "Updated"})

        assert captured[0][0] == "PATCH"
        assert captured[0][1]["name"] == "Updated"
        assert result["name"] == "Updated"

    def test_url_path(self, oauth_credentials: Session) -> None:
        """update_webhook() targets the correct webhook ID in URL."""
        captured_urls: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture URL."""
            captured_urls.append(str(request.url))
            return httpx.Response(
                200,
                json={"status": "ok", "results": _mutation_result()},
            )

        client = create_mock_client(oauth_credentials, handler)
        with client:
            client.update_webhook("wh-uuid-123", {"name": "X"})

        assert "/webhooks/wh-uuid-123/" in captured_urls[0]


# =============================================================================
# Delete Webhook Tests
# =============================================================================


class TestDeleteWebhook:
    """Tests for delete_webhook() API client method."""

    def test_deletes_webhook(self, oauth_credentials: Session) -> None:
        """delete_webhook() sends DELETE request."""
        captured_methods: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture method."""
            captured_methods.append(request.method)
            return httpx.Response(204)

        client = create_mock_client(oauth_credentials, handler)
        with client:
            client.delete_webhook("wh-uuid-123")

        assert captured_methods[0] == "DELETE"

    def test_url_path(self, oauth_credentials: Session) -> None:
        """delete_webhook() targets the correct webhook ID in URL."""
        captured_urls: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture URL."""
            captured_urls.append(str(request.url))
            return httpx.Response(204)

        client = create_mock_client(oauth_credentials, handler)
        with client:
            client.delete_webhook("wh-uuid-123")

        assert "/webhooks/wh-uuid-123/" in captured_urls[0]


# =============================================================================
# Test Webhook Tests
# =============================================================================


class TestTestWebhook:
    """Tests for test_webhook() API client method."""

    def test_sends_post(self, oauth_credentials: Session) -> None:
        """test_webhook() sends POST request with body."""
        captured: list[tuple[str, Any]] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture method and body."""
            captured.append((request.method, json.loads(request.content)))
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": {
                        "success": True,
                        "status_code": 200,
                        "message": "OK",
                    },
                },
            )

        client = create_mock_client(oauth_credentials, handler)
        with client:
            result = client.test_webhook({"url": "https://example.com/hook"})

        assert captured[0][0] == "POST"
        assert result["success"] is True
        assert result["status_code"] == 200

    def test_url_path(self, oauth_credentials: Session) -> None:
        """test_webhook() posts to the webhooks/test/ endpoint."""
        captured_urls: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture URL."""
            captured_urls.append(str(request.url))
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": {
                        "success": True,
                        "status_code": 200,
                        "message": "OK",
                    },
                },
            )

        client = create_mock_client(oauth_credentials, handler)
        with client:
            client.test_webhook({"url": "https://example.com"})

        assert "/webhooks/test/" in captured_urls[0]

    def test_failure_result(self, oauth_credentials: Session) -> None:
        """test_webhook() returns failure result when test fails."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return failure test result."""
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": {
                        "success": False,
                        "status_code": 500,
                        "message": "Connection refused",
                    },
                },
            )

        client = create_mock_client(oauth_credentials, handler)
        with client:
            result = client.test_webhook({"url": "https://bad.example.com"})

        assert result["success"] is False
        assert result["status_code"] == 500
