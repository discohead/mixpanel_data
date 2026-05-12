# ruff: noqa: ARG001, ARG005
"""Unit tests for Workspace webhook methods (Phase 026).

Tests for webhook CRUD operations and connectivity testing on the
Workspace facade. Each method delegates to MixpanelAPIClient and
returns typed objects.

Verifies:
- Webhook CRUD: list, create, update, delete
- Webhook testing: test connectivity
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
    CreateWebhookParams,
    ProjectWebhook,
    UpdateWebhookParams,
    WebhookMutationResult,
    WebhookTestParams,
    WebhookTestResult,
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


def _webhook_json(
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


def _mutation_json(
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
# TestWorkspaceWebhookCRUD
# =============================================================================


class TestWorkspaceWebhookCRUD:
    """Tests for Workspace webhook CRUD methods."""

    def test_list_webhooks(self, temp_dir: Path) -> None:
        """list_webhooks() returns list of ProjectWebhook objects."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return webhook list."""
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": [
                        _webhook_json("id-1", "Hook A"),
                        _webhook_json("id-2", "Hook B"),
                    ],
                },
            )

        ws = _make_workspace(temp_dir, handler)
        webhooks = ws.list_webhooks()

        assert len(webhooks) == 2
        assert isinstance(webhooks[0], ProjectWebhook)
        assert webhooks[0].id == "id-1"
        assert webhooks[0].name == "Hook A"
        assert webhooks[1].id == "id-2"

    def test_list_webhooks_empty(self, temp_dir: Path) -> None:
        """list_webhooks() returns empty list when no webhooks exist."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return empty webhook list."""
            return httpx.Response(200, json={"status": "ok", "results": []})

        ws = _make_workspace(temp_dir, handler)
        webhooks = ws.list_webhooks()

        assert webhooks == []

    def test_create_webhook(self, temp_dir: Path) -> None:
        """create_webhook() returns WebhookMutationResult."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return mutation result."""
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": _mutation_json("new-id", "New Hook"),
                },
            )

        ws = _make_workspace(temp_dir, handler)
        params = CreateWebhookParams(name="New Hook", url="https://example.com")
        result = ws.create_webhook(params)

        assert isinstance(result, WebhookMutationResult)
        assert result.id == "new-id"
        assert result.name == "New Hook"

    def test_create_webhook_with_auth(self, temp_dir: Path) -> None:
        """create_webhook() sends auth fields when provided."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return mutation result."""
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": _mutation_json("new-id", "Secured"),
                },
            )

        ws = _make_workspace(temp_dir, handler)
        params = CreateWebhookParams(
            name="Secured",
            url="https://example.com",
            auth_type="basic",
            username="user",
            password="pass",
        )
        result = ws.create_webhook(params)

        assert isinstance(result, WebhookMutationResult)
        assert result.name == "Secured"

    def test_update_webhook(self, temp_dir: Path) -> None:
        """update_webhook() returns WebhookMutationResult."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return mutation result."""
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": _mutation_json("wh-uuid-123", "Renamed"),
                },
            )

        ws = _make_workspace(temp_dir, handler)
        params = UpdateWebhookParams(name="Renamed")
        result = ws.update_webhook("wh-uuid-123", params)

        assert isinstance(result, WebhookMutationResult)
        assert result.name == "Renamed"

    def test_delete_webhook(self, temp_dir: Path) -> None:
        """delete_webhook() returns None on success."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return 204 for delete."""
            return httpx.Response(204)

        ws = _make_workspace(temp_dir, handler)
        ws.delete_webhook("wh-uuid-123")  # Should not raise

    def test_delete_webhook_200(self, temp_dir: Path) -> None:
        """delete_webhook() handles 200 response too."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return 200 for delete."""
            return httpx.Response(200, json={"status": "ok", "results": {}})

        ws = _make_workspace(temp_dir, handler)
        ws.delete_webhook("wh-uuid-123")  # Should not raise


# =============================================================================
# TestWorkspaceWebhookTest
# =============================================================================


class TestWorkspaceWebhookTest:
    """Tests for Workspace webhook test method."""

    def test_test_webhook_success(self, temp_dir: Path) -> None:
        """test_webhook() returns WebhookTestResult on success."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return success test result."""
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

        ws = _make_workspace(temp_dir, handler)
        params = WebhookTestParams(url="https://example.com/hook")
        result = ws.test_webhook(params)

        assert isinstance(result, WebhookTestResult)
        assert result.success is True
        assert result.status_code == 200
        assert result.message == "OK"

    def test_test_webhook_failure(self, temp_dir: Path) -> None:
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

        ws = _make_workspace(temp_dir, handler)
        params = WebhookTestParams(url="https://bad.example.com")
        result = ws.test_webhook(params)

        assert isinstance(result, WebhookTestResult)
        assert result.success is False
        assert result.status_code == 500
