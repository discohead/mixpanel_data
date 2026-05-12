"""Unit tests for Workspace OAuth integration (T034).

Integration tests for Workspace construction with OAuth tokens and
workspace management methods (list_workspaces, resolve_workspace_id,
set_workspace_id, workspace_id property).

Verifies:
- Workspace construction with OAuth credentials
- list_workspaces() delegates to api_client
- resolve_workspace_id() delegates to api_client
- set_workspace_id() delegates to api_client
- workspace_id property returns current workspace id
- Backward compatibility with Basic Auth Workspace usage
"""
# ruff: noqa: ARG001, ARG005

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

import httpx
from pydantic import SecretStr

from mixpanel_headless._internal.api_client import MixpanelAPIClient
from mixpanel_headless._internal.auth.account import ServiceAccount
from mixpanel_headless._internal.auth.session import Project, Session
from mixpanel_headless.types import PublicWorkspace
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


def _make_oauth_credentials(
    project_id: str = "12345",
    region: str = "us",
    access_token: str = "test-oauth-token",
) -> Session:
    """Create OAuth Credentials for testing.

    Args:
        project_id: Mixpanel project ID.
        region: Data residency region.
        access_token: OAuth access token.

    Returns:
        A Credentials instance with auth_method=oauth.
    """
    return make_session(
        project_id=project_id,
        region=region,
        oauth_token=access_token,
    )


def _make_basic_credentials(
    project_id: str = "12345",
    region: str = "us",
) -> Session:
    """Create Basic Auth Credentials for testing.

    Args:
        project_id: Mixpanel project ID.
        region: Data residency region.

    Returns:
        A Credentials instance with auth_method=basic.
    """
    return make_session(
        username="test_user",
        secret="test_secret",
        project_id=project_id,
        region=region,
    )


def _workspaces_json() -> list[dict[str, Any]]:
    """Return a sample list of workspace dicts for mock responses.

    Returns:
        List of workspace dictionaries matching the Mixpanel API format.
    """
    return [
        {
            "id": 100,
            "name": "Default Workspace",
            "project_id": 12345,
            "is_default": True,
            "description": "The default workspace",
            "is_global": False,
            "is_restricted": False,
            "is_visible": True,
            "created_iso": "2024-01-01T00:00:00Z",
            "creator_name": "Admin",
        },
        {
            "id": 200,
            "name": "Dev Workspace",
            "project_id": 12345,
            "is_default": False,
            "description": "Development workspace",
            "is_global": False,
            "is_restricted": False,
            "is_visible": True,
            "created_iso": "2024-02-01T00:00:00Z",
            "creator_name": "Dev",
        },
    ]


def _make_workspace_handler() -> Callable[[httpx.Request], httpx.Response]:
    """Create a mock HTTP handler that returns workspace list responses.

    Returns:
        A handler function for httpx.MockTransport.
    """

    def handler(request: httpx.Request) -> httpx.Response:
        """Handle mock HTTP requests for workspace endpoints.

        Args:
            request: The incoming HTTP request.

        Returns:
            Mock response with workspace data for workspace paths,
            404 for unrecognized paths.
        """
        url_path = request.url.path
        if "workspaces/public" in url_path:
            return httpx.Response(
                200,
                json={"results": _workspaces_json(), "status": "ok"},
            )
        return httpx.Response(404, json={"error": "not found"})

    return handler


# _setup_config_with_account removed in B1 (Fix 9): the legacy v1
# ``ConfigManager.add_account(project_id=, region=, …)`` signature is
# gone; ``_make_workspace`` now relies on ``session=_TEST_SESSION``
# instead, which never touches a real ConfigManager.


class TestWorkspaceConstructionWithOAuth:
    """Tests for Workspace construction with OAuth credentials."""

    def test_workspace_with_oauth_credentials(self) -> None:
        """An OAuth-typed Session yields ``_credentials.auth_method == oauth``."""
        from mixpanel_headless._internal.auth.account import OAuthTokenAccount

        oauth_creds = _make_oauth_credentials()
        transport = httpx.MockTransport(_make_workspace_handler())
        client = MixpanelAPIClient(session=oauth_creds, _transport=transport)
        oauth_session = Session(
            account=OAuthTokenAccount(
                name="test_account",
                region="us",
                token=SecretStr("test-oauth-token"),
                default_project="12345",
            ),
            project=Project(id="12345"),
        )
        ws = Workspace(session=oauth_session, _api_client=client)

        from mixpanel_headless._internal.auth.account import OAuthTokenAccount

        assert isinstance(ws.session.account, OAuthTokenAccount)

    def test_workspace_backward_compat_basic_auth(self) -> None:
        """A service-account Session resolves through the ServiceAccount path."""
        from mixpanel_headless._internal.auth.account import ServiceAccount

        basic_creds = _make_basic_credentials()
        transport = httpx.MockTransport(lambda _r: httpx.Response(200, json=[]))
        client = MixpanelAPIClient(session=basic_creds, _transport=transport)

        ws = Workspace(session=_TEST_SESSION, _api_client=client)

        assert isinstance(ws.session.account, ServiceAccount)
        assert ws.session.account.username == "test_user"


class TestWorkspaceListWorkspaces:
    """Tests for Workspace.list_workspaces()."""

    def test_list_workspaces_returns_workspace_models(
        self,
        temp_dir: Path,
    ) -> None:
        """list_workspaces() returns a list of PublicWorkspace objects."""
        oauth_creds = _make_oauth_credentials()
        transport = httpx.MockTransport(_make_workspace_handler())
        client = MixpanelAPIClient(session=oauth_creds, _transport=transport)
        ws = Workspace(
            session=_TEST_SESSION,
            _api_client=client,
        )

        workspaces = ws.list_workspaces()

        assert len(workspaces) == 2
        assert isinstance(workspaces[0], PublicWorkspace)
        assert workspaces[0].name == "Default Workspace"
        assert workspaces[0].id == 100
        assert workspaces[0].is_default is True
        assert workspaces[1].id == 200

    def test_list_workspaces_empty(
        self,
        temp_dir: Path,
    ) -> None:
        """list_workspaces() returns empty list when no workspaces exist."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return empty workspace list.

            Args:
                _request: The HTTP request (unused).

            Returns:
                Response with empty results.
            """
            return httpx.Response(
                200,
                json={"results": [], "status": "ok"},
            )

        oauth_creds = _make_oauth_credentials()
        transport = httpx.MockTransport(handler)
        client = MixpanelAPIClient(session=oauth_creds, _transport=transport)
        ws = Workspace(
            session=_TEST_SESSION,
            _api_client=client,
        )

        workspaces = ws.list_workspaces()
        assert workspaces == []


class TestWorkspaceResolveWorkspaceId:
    """Tests for Workspace.resolve_workspace_id()."""

    def test_resolve_workspace_id_returns_default(
        self,
        temp_dir: Path,
    ) -> None:
        """resolve_workspace_id() returns the default workspace ID."""
        oauth_creds = _make_oauth_credentials()
        transport = httpx.MockTransport(_make_workspace_handler())
        client = MixpanelAPIClient(session=oauth_creds, _transport=transport)
        ws = Workspace(
            session=_TEST_SESSION,
            _api_client=client,
        )

        ws_id = ws.resolve_workspace_id()
        assert ws_id == 100  # The default workspace


# TestWorkspaceSetWorkspaceId removed in B2 (T050 / FR-038):
# ``set_workspace_id`` is gone — use ``ws.use(workspace=N)`` instead.
