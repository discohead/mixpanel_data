"""Unit tests for App API request methods and workspace scoping.

Tests for:
- app_request() method: Bearer auth, URL building, response unwrapping
- Workspace scoping: maybe_scoped_path(), require_scoped_path()
- Workspace resolution: list_workspaces(), resolve_workspace_id()
"""
# ruff: noqa: ARG001, ARG005

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

import httpx
import pytest

from mixpanel_headless._internal.api_client import ENDPOINTS, MixpanelAPIClient
from mixpanel_headless._internal.auth.session import Session
from mixpanel_headless.exceptions import (
    AuthenticationError,
    MixpanelHeadlessError,
    QueryError,
    ServerError,
    WorkspaceScopeError,
)
from mixpanel_headless.types import PublicWorkspace
from tests.conftest import make_session

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def oauth_credentials() -> Session:
    """Create OAuth credentials for App API testing."""
    return make_session(project_id="12345", region="us", oauth_token="test-oauth-token")


@pytest.fixture
def basic_credentials() -> Session:
    """Create Basic Auth credentials for App API testing."""
    return make_session(
        username="test_user",
        secret="test_secret",
        project_id="12345",
        region="us",
    )


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
# T026: app_request() method tests
# =============================================================================


class TestAppRequest:
    """Test app_request() method for App API calls."""

    def test_uses_bearer_auth_header(self, oauth_credentials: Session) -> None:
        """app_request() should use Bearer auth from credentials.auth_header()."""
        captured_headers: dict[str, str] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured_headers.update(dict(request.headers))
            return httpx.Response(200, json={"status": "ok", "results": []})

        client = create_mock_client(oauth_credentials, handler)
        with client:
            client.app_request("GET", "/dashboards")

        assert captured_headers["authorization"] == "Bearer test-oauth-token"

    def test_uses_basic_auth_when_configured(self, basic_credentials: Session) -> None:
        """app_request() should use Basic auth when credentials use basic method."""
        captured_headers: dict[str, str] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured_headers.update(dict(request.headers))
            return httpx.Response(200, json={"status": "ok", "results": []})

        client = create_mock_client(basic_credentials, handler)
        with client:
            client.app_request("GET", "/dashboards")

        assert captured_headers["authorization"].startswith("Basic ")

    def test_builds_correct_url(self, oauth_credentials: Session) -> None:
        """app_request() should build URL from ENDPOINTS['app'] + path."""
        captured_urls: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            captured_urls.append(str(request.url))
            return httpx.Response(200, json={"status": "ok", "results": []})

        client = create_mock_client(oauth_credentials, handler)
        with client:
            client.app_request("GET", "/projects/12345/dashboards")

        expected_base = ENDPOINTS["us"]["app"]
        assert captured_urls[0].startswith(f"{expected_base}/projects/12345/dashboards")

    def test_unwraps_results_field(self, oauth_credentials: Session) -> None:
        """app_request() should unwrap 'results' field from response."""

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": [{"id": 1, "name": "Dashboard 1"}],
                },
            )

        client = create_mock_client(oauth_credentials, handler)
        with client:
            result = client.app_request("GET", "/projects/12345/dashboards")

        assert result == [{"id": 1, "name": "Dashboard 1"}]

    def test_returns_full_response_when_no_results_key(
        self, oauth_credentials: Session
    ) -> None:
        """app_request() should return full body when no 'results' key."""

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={"status": "ok", "data": "something"})

        client = create_mock_client(oauth_credentials, handler)
        with client:
            result = client.app_request("GET", "/projects/12345/some-endpoint")

        assert result == {"status": "ok", "data": "something"}

    def test_handles_204_no_content(self, oauth_credentials: Session) -> None:
        """app_request() should return {'status': 'ok'} for 204 No Content."""

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(204)

        client = create_mock_client(oauth_credentials, handler)
        with client:
            result = client.app_request("DELETE", "/projects/12345/dashboards/1")

        assert result == {"status": "ok"}

    def test_maps_404_to_query_error(self, oauth_credentials: Session) -> None:
        """app_request() should raise QueryError on 404."""

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(404, json={"error": "Not found"})

        client = create_mock_client(oauth_credentials, handler)
        with client, pytest.raises(QueryError) as exc_info:
            client.app_request("GET", "/projects/12345/dashboards/999")

        assert exc_info.value.status_code == 404

    def test_maps_422_to_query_error(self, oauth_credentials: Session) -> None:
        """app_request() should raise QueryError on 422."""

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                422, json={"error": "Unprocessable entity", "details": "bad field"}
            )

        client = create_mock_client(oauth_credentials, handler)
        with client, pytest.raises(QueryError) as exc_info:
            client.app_request("GET", "/projects/12345/dashboards")

        assert exc_info.value.status_code == 422

    def test_maps_401_to_authentication_error(self, oauth_credentials: Session) -> None:
        """app_request() should raise AuthenticationError on 401."""

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(401, json={"error": "Unauthorized"})

        client = create_mock_client(oauth_credentials, handler)
        with client, pytest.raises(AuthenticationError):
            client.app_request("GET", "/projects/12345/dashboards")

    def test_maps_5xx_to_server_error(self, oauth_credentials: Session) -> None:
        """app_request() should raise ServerError on 5xx."""

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(500, json={"error": "Internal server error"})

        client = create_mock_client(oauth_credentials, handler)
        with client, pytest.raises(ServerError):
            client.app_request("GET", "/projects/12345/dashboards")

    def test_passes_query_params(self, oauth_credentials: Session) -> None:
        """app_request() should pass query params through."""
        captured_params: dict[str, str] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured_params.update(dict(request.url.params))
            return httpx.Response(200, json={"status": "ok", "results": []})

        client = create_mock_client(oauth_credentials, handler)
        with client:
            client.app_request(
                "GET", "/projects/12345/dashboards", params={"page_size": "50"}
            )

        assert captured_params["page_size"] == "50"

    def test_passes_json_body(self, oauth_credentials: Session) -> None:
        """app_request() should pass JSON body for POST/PATCH."""
        captured_body: dict[str, Any] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            body = json.loads(request.content.decode())
            captured_body.update(body)
            return httpx.Response(
                200, json={"status": "ok", "results": {"id": 1, "name": "New"}}
            )

        client = create_mock_client(oauth_credentials, handler)
        with client:
            client.app_request(
                "POST",
                "/projects/12345/dashboards",
                json_body={"name": "New Dashboard"},
            )

        assert captured_body["name"] == "New Dashboard"

    def test_eu_region_uses_eu_endpoint(self) -> None:
        """app_request() should use EU endpoint for EU credentials."""
        eu_creds = make_session(project_id="12345", region="eu", oauth_token="eu-token")
        captured_urls: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            captured_urls.append(str(request.url))
            return httpx.Response(200, json={"status": "ok", "results": []})

        client = create_mock_client(eu_creds, handler)
        with client:
            client.app_request("GET", "/projects/12345/dashboards")

        assert captured_urls[0].startswith(ENDPOINTS["eu"]["app"])


class TestAppRequestFormBody:
    """Test app_request() with form_body= for application/x-www-form-urlencoded.

    Some Mixpanel App API endpoints (notably ``custom_events/`` and
    ``data-definitions/lookup-tables/``) require form-encoded bodies rather
    than JSON. ``form_body=`` plumbs those callers through the same retry
    and error-wrapping path as JSON callers instead of forcing them to
    bypass ``app_request`` and lose those protections.
    """

    def test_form_body_sent_as_form_encoded(self, oauth_credentials: Session) -> None:
        """form_body= produces application/x-www-form-urlencoded with the fields."""
        captured: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture the outgoing request."""
            captured.append(request)
            return httpx.Response(200, json={"status": "ok", "results": {"id": 1}})

        client = create_mock_client(oauth_credentials, handler)
        with client:
            client.app_request(
                "POST",
                "/projects/12345/custom_events/",
                form_body={"name": "X", "alternatives": '[{"event": "Y"}]'},
            )

        from urllib.parse import parse_qs

        req = captured[0]
        assert req.method == "POST"
        assert req.headers["content-type"].startswith(
            "application/x-www-form-urlencoded"
        )
        decoded = parse_qs(req.content.decode())
        assert decoded["name"] == ["X"]
        assert decoded["alternatives"] == ['[{"event": "Y"}]']

    def test_form_body_retries_on_429(self, oauth_credentials: Session) -> None:
        """form_body= callers go through the same 429 retry path as json_body=."""
        attempts: list[int] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Return 429 once, then 200."""
            attempts.append(1)
            if len(attempts) == 1:
                return httpx.Response(
                    429,
                    headers={"Retry-After": "0"},
                    json={"error": "rate limited"},
                )
            return httpx.Response(200, json={"status": "ok", "results": {"id": 1}})

        client = create_mock_client(oauth_credentials, handler)
        with client:
            result = client.app_request(
                "POST",
                "/projects/12345/custom_events/",
                form_body={"name": "X", "alternatives": "[]"},
            )

        assert len(attempts) == 2  # one retry then success
        assert result == {"id": 1}

    def test_form_body_wraps_httpx_transport_error(
        self, oauth_credentials: Session
    ) -> None:
        """form_body= callers surface httpx.HTTPError as MixpanelHeadlessError."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Raise a transport-level ConnectError."""
            raise httpx.ConnectError("connection refused")

        client = create_mock_client(oauth_credentials, handler)
        with client, pytest.raises(MixpanelHeadlessError):
            client.app_request(
                "POST",
                "/projects/12345/custom_events/",
                form_body={"name": "X", "alternatives": "[]"},
            )

    def test_form_body_and_json_body_mutually_exclusive(
        self, oauth_credentials: Session
    ) -> None:
        """Passing both form_body and json_body raises ValueError."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Should never be called — error fires before request."""
            return httpx.Response(200, json={"status": "ok"})

        client = create_mock_client(oauth_credentials, handler)
        with client, pytest.raises(ValueError, match="form_body"):
            client.app_request(
                "POST",
                "/projects/12345/custom_events/",
                json_body={"a": 1},
                form_body={"b": "2"},
            )


# =============================================================================
# T027: Workspace scoping tests
# =============================================================================


class TestWorkspaceScoping:
    """Test workspace scoping path helpers."""

    def test_maybe_scoped_path_without_workspace(
        self, oauth_credentials: Session
    ) -> None:
        """maybe_scoped_path() returns project-scoped path when no workspace set."""
        client = create_mock_client(
            oauth_credentials, lambda _r: httpx.Response(200, json={})
        )
        path = client.maybe_scoped_path("dashboards")
        assert path == "/projects/12345/dashboards"

    def test_maybe_scoped_path_with_workspace(self, oauth_credentials: Session) -> None:
        """maybe_scoped_path() returns workspace-scoped path when workspace set."""
        client = create_mock_client(
            oauth_credentials, lambda _r: httpx.Response(200, json={})
        )
        client.set_workspace_id(789)
        path = client.maybe_scoped_path("dashboards")
        assert path == "/workspaces/789/dashboards"

    def test_maybe_scoped_path_with_workspace_none_resets(
        self, oauth_credentials: Session
    ) -> None:
        """set_workspace_id(None) should reset to project-scoped paths."""
        client = create_mock_client(
            oauth_credentials, lambda _r: httpx.Response(200, json={})
        )
        client.set_workspace_id(789)
        client.set_workspace_id(None)
        path = client.maybe_scoped_path("dashboards")
        assert path == "/projects/12345/dashboards"

    def test_require_scoped_path_with_explicit_workspace(
        self, oauth_credentials: Session
    ) -> None:
        """require_scoped_path() uses explicit workspace ID if set."""
        client = create_mock_client(
            oauth_credentials, lambda _r: httpx.Response(200, json={})
        )
        client.set_workspace_id(789)
        path = client.require_scoped_path("feature-flags")
        assert path == "/projects/12345/workspaces/789/feature-flags"

    def test_require_scoped_path_auto_discovers_workspace(
        self, oauth_credentials: Session
    ) -> None:
        """require_scoped_path() auto-discovers workspace when not set."""
        workspaces_response = {
            "status": "ok",
            "results": [
                {"id": 100, "name": "Main", "project_id": 12345, "is_default": True},
            ],
        }

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json=workspaces_response)

        client = create_mock_client(oauth_credentials, handler)
        with client:
            path = client.require_scoped_path("feature-flags")

        assert path == "/projects/12345/workspaces/100/feature-flags"

    def test_require_scoped_path_raises_on_no_workspaces(
        self, oauth_credentials: Session
    ) -> None:
        """require_scoped_path() raises WorkspaceScopeError if no workspaces."""
        workspaces_response = {
            "status": "ok",
            "results": [],
        }

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json=workspaces_response)

        client = create_mock_client(oauth_credentials, handler)
        with client, pytest.raises(WorkspaceScopeError):
            client.require_scoped_path("feature-flags")

    def test_require_scoped_path_caches_resolved_workspace(
        self, oauth_credentials: Session
    ) -> None:
        """require_scoped_path() caches resolved workspace ID."""
        call_count = 0
        workspaces_response = {
            "status": "ok",
            "results": [
                {"id": 100, "name": "Main", "project_id": 12345, "is_default": True},
            ],
        }

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal call_count
            call_count += 1
            return httpx.Response(200, json=workspaces_response)

        client = create_mock_client(oauth_credentials, handler)
        with client:
            client.require_scoped_path("feature-flags")
            client.require_scoped_path("experiments")

        # Only one HTTP call for workspace resolution
        assert call_count == 1


# =============================================================================
# Workspace resolution tests
# =============================================================================


class TestResolveWorkspaceId:
    """Test resolve_workspace_id() method."""

    def test_returns_explicit_workspace_id(self, oauth_credentials: Session) -> None:
        """resolve_workspace_id() returns explicit ID when set."""
        client = create_mock_client(
            oauth_credentials, lambda _r: httpx.Response(200, json={})
        )
        client.set_workspace_id(42)
        assert client.resolve_workspace_id() == 42

    def test_auto_discovers_default_workspace(self, oauth_credentials: Session) -> None:
        """resolve_workspace_id() finds is_default=True workspace."""
        workspaces_response = {
            "status": "ok",
            "results": [
                {"id": 10, "name": "Other", "project_id": 12345, "is_default": False},
                {"id": 20, "name": "Main", "project_id": 12345, "is_default": True},
            ],
        }

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json=workspaces_response)

        client = create_mock_client(oauth_credentials, handler)
        with client:
            ws_id = client.resolve_workspace_id()

        assert ws_id == 20

    def test_falls_back_to_first_workspace(self, oauth_credentials: Session) -> None:
        """resolve_workspace_id() uses first workspace when none is default."""
        workspaces_response = {
            "status": "ok",
            "results": [
                {"id": 10, "name": "First", "project_id": 12345, "is_default": False},
                {"id": 20, "name": "Second", "project_id": 12345, "is_default": False},
            ],
        }

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json=workspaces_response)

        client = create_mock_client(oauth_credentials, handler)
        with client:
            ws_id = client.resolve_workspace_id()

        assert ws_id == 10

    def test_raises_on_empty_workspaces(self, oauth_credentials: Session) -> None:
        """resolve_workspace_id() raises WorkspaceScopeError when no workspaces."""
        workspaces_response = {
            "status": "ok",
            "results": [],
        }

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json=workspaces_response)

        client = create_mock_client(oauth_credentials, handler)
        with client, pytest.raises(WorkspaceScopeError) as exc_info:
            client.resolve_workspace_id()

        assert exc_info.value.code == "NO_WORKSPACES"

    def test_caches_resolved_id(self, oauth_credentials: Session) -> None:
        """resolve_workspace_id() caches the resolved ID for subsequent calls."""
        call_count = 0
        workspaces_response = {
            "status": "ok",
            "results": [
                {"id": 100, "name": "Main", "project_id": 12345, "is_default": True},
            ],
        }

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal call_count
            call_count += 1
            return httpx.Response(200, json=workspaces_response)

        client = create_mock_client(oauth_credentials, handler)
        with client:
            first = client.resolve_workspace_id()
            second = client.resolve_workspace_id()

        assert first == second == 100
        assert call_count == 1


class TestListWorkspaces:
    """Test list_workspaces() method."""

    def test_returns_public_workspace_list(self, oauth_credentials: Session) -> None:
        """list_workspaces() returns list of PublicWorkspace models."""
        workspaces_response = {
            "status": "ok",
            "results": [
                {
                    "id": 1,
                    "name": "Default",
                    "project_id": 12345,
                    "is_default": True,
                },
                {
                    "id": 2,
                    "name": "Staging",
                    "project_id": 12345,
                    "is_default": False,
                },
            ],
        }

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json=workspaces_response)

        client = create_mock_client(oauth_credentials, handler)
        with client:
            workspaces = client.list_workspaces()

        assert len(workspaces) == 2
        assert isinstance(workspaces[0], PublicWorkspace)
        assert workspaces[0].id == 1
        assert workspaces[0].name == "Default"
        assert workspaces[0].is_default is True
        assert workspaces[1].id == 2
        assert workspaces[1].is_default is False

    def test_calls_correct_endpoint(self, oauth_credentials: Session) -> None:
        """list_workspaces() calls /api/app/projects/{pid}/workspaces/public."""
        captured_urls: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            captured_urls.append(str(request.url))
            return httpx.Response(200, json={"status": "ok", "results": []})

        client = create_mock_client(oauth_credentials, handler)
        with client:
            client.list_workspaces()

        expected = f"{ENDPOINTS['us']['app']}/projects/12345/workspaces/public"
        assert captured_urls[0].startswith(expected)


class TestResolveWorkspace:
    """Test ``resolve_workspace()`` (returns the full WorkspaceRef)."""

    def test_calls_correct_endpoint_no_double_prefix(
        self, oauth_credentials: Session
    ) -> None:
        """``resolve_workspace()`` hits ``{base}/projects/{pid}/workspaces/public`` exactly.

        Regression: the path used to start with ``/api/app/...`` and
        ``app_request()`` already prepends the same base, producing a
        404-yielding double ``/api/app/api/app`` prefix.
        """
        captured_urls: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            captured_urls.append(str(request.url))
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": [
                        {
                            "id": 7,
                            "name": "Default",
                            "project_id": 12345,
                            "is_default": True,
                        }
                    ],
                },
            )

        client = create_mock_client(oauth_credentials, handler)
        with client:
            client.resolve_workspace()

        expected = f"{ENDPOINTS['us']['app']}/projects/12345/workspaces/public"
        assert captured_urls == [expected], (
            f"resolve_workspace() must call {expected} exactly once; got "
            f"{captured_urls!r}"
        )
        assert "/api/app/api/app" not in captured_urls[0]

    def test_writes_to_resolve_workspace_id_cache(
        self, oauth_credentials: Session
    ) -> None:
        """A successful ``resolve_workspace()`` populates the int-id cache.

        After calling ``resolve_workspace()``, calling
        ``resolve_workspace_id()`` MUST NOT trigger another HTTP request —
        both paths share the same discovery and should share the cache.
        """
        call_count = 0

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal call_count
            call_count += 1
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": [
                        {
                            "id": 99,
                            "name": "Default",
                            "project_id": 12345,
                            "is_default": True,
                        }
                    ],
                },
            )

        client = create_mock_client(oauth_credentials, handler)
        with client:
            ref = client.resolve_workspace()
            ws_id = client.resolve_workspace_id()

        assert ref.id == 99
        assert ws_id == 99
        assert call_count == 1


# =============================================================================
# Phase 3B: Empty/None parameter edge cases
# =============================================================================


class TestAppApiEdgeCases:
    """Tests for edge-case parameter values in App API client methods.

    Verifies behavior when workspace IDs are zero or negative, which
    are technically valid integers but may indicate misconfiguration.
    """

    def test_set_workspace_id_zero(self, oauth_credentials: Session) -> None:
        """Verify that workspace ID 0 is accepted and included in scoped paths.

        While workspace ID 0 is unusual, the client should not reject it.
        ``maybe_scoped_path()`` should produce ``/workspaces/0/dashboards``.
        """
        client = create_mock_client(
            oauth_credentials, lambda _r: httpx.Response(200, json={})
        )
        client.set_workspace_id(0)
        path = client.maybe_scoped_path("dashboards")
        assert "/workspaces/0/" in path

    def test_set_workspace_id_negative(self, oauth_credentials: Session) -> None:
        """Verify that a negative workspace ID is accepted and included in scoped paths.

        While workspace ID -1 is invalid in practice, the client does not
        validate IDs — it delegates validation to the server. The path
        should contain ``/workspaces/-1/``.
        """
        client = create_mock_client(
            oauth_credentials, lambda _r: httpx.Response(200, json={})
        )
        client.set_workspace_id(-1)
        path = client.maybe_scoped_path("dashboards")
        assert "/workspaces/-1/" in path


# =============================================================================
# Phase 3D: list_workspaces non-list response (Bug B6)
# =============================================================================


class TestListWorkspacesEdgeCases:
    """Tests for list_workspaces() handling of unexpected response shapes.

    Documents behavior when the API returns non-list ``results`` or
    results missing required fields — edge cases that may occur with
    API version mismatches or server bugs.
    """

    def test_list_workspaces_string_response(self, oauth_credentials: Session) -> None:
        """Verify list_workspaces() raises on non-list results.

        When the API returns ``{"results": "unexpected_string"}``,
        ``app_request()`` unwraps results to the string ``"unexpected_string"``.
        ``list_workspaces()`` validates the type and raises ``MixpanelHeadlessError``.
        """

        def handler(request: httpx.Request) -> httpx.Response:
            """Return a response with string results instead of list."""
            return httpx.Response(
                200, json={"results": "unexpected_string", "status": "ok"}
            )

        client = create_mock_client(oauth_credentials, handler)
        with (
            client,
            pytest.raises(MixpanelHeadlessError, match="Unexpected response format"),
        ):
            client.list_workspaces()

    def test_list_workspaces_missing_required_fields(
        self, oauth_credentials: Session
    ) -> None:
        """Verify list_workspaces() raises ValidationError when fields are missing.

        When the API returns workspace objects missing required fields
        (like ``id``), Pydantic's ``model_validate()`` should raise
        ``ValidationError`` during deserialization.
        """
        from pydantic import ValidationError

        def handler(request: httpx.Request) -> httpx.Response:
            """Return workspace data missing the required 'id' field."""
            return httpx.Response(
                200,
                json={
                    "results": [{"name": "missing_id"}],
                    "status": "ok",
                },
            )

        client = create_mock_client(oauth_credentials, handler)
        with client, pytest.raises(ValidationError):
            client.list_workspaces()
