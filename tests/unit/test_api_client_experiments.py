"""Unit tests for Experiment API client methods (Phase 025).

Tests for:
- Experiment CRUD: list, create, get, update, delete
- Experiment lifecycle: launch, conclude, decide
- Experiment management: archive, restore, duplicate
- ERF experiments listing
- Error paths: invalid state transitions (400), not found (404)
"""

# ruff: noqa: ARG001, ARG005

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

import httpx
import pytest

from mixpanel_headless._internal.api_client import MixpanelAPIClient
from mixpanel_headless._internal.auth.session import Session
from mixpanel_headless.exceptions import APIError
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
# Experiment CRUD Tests
# =============================================================================


class TestListExperiments:
    """Tests for list_experiments() API client method."""

    def test_returns_experiment_list(self, oauth_credentials: Session) -> None:
        """list_experiments() returns a list of experiment dicts."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return sample experiment list."""
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": [
                        {"id": "abc-123", "name": "Experiment A"},
                        {"id": "def-456", "name": "Experiment B"},
                    ],
                },
            )

        client = create_mock_client(oauth_credentials, handler)
        with client:
            result = client.list_experiments()

        assert len(result) == 2
        assert result[0]["id"] == "abc-123"
        assert result[1]["name"] == "Experiment B"

    def test_uses_maybe_scoped_path(self, oauth_credentials: Session) -> None:
        """list_experiments() uses maybe_scoped_path for URL building."""
        captured_urls: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture URL."""
            captured_urls.append(str(request.url))
            return httpx.Response(200, json={"status": "ok", "results": []})

        client = create_mock_client(oauth_credentials, handler)
        with client:
            client.list_experiments()

        assert "/projects/12345/experiments" in captured_urls[0]

    def test_empty_result(self, oauth_credentials: Session) -> None:
        """list_experiments() returns empty list when no experiments."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return empty results."""
            return httpx.Response(200, json={"status": "ok", "results": []})

        client = create_mock_client(oauth_credentials, handler)
        with client:
            result = client.list_experiments()

        assert result == []

    def test_include_archived(self, oauth_credentials: Session) -> None:
        """list_experiments(include_archived=True) passes query param."""
        captured_urls: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture URL and return empty list."""
            captured_urls.append(str(request.url))
            return httpx.Response(200, json={"status": "ok", "results": []})

        client = create_mock_client(oauth_credentials, handler)
        with client:
            client.list_experiments(include_archived=True)

        assert "include_archived=true" in captured_urls[0]


class TestCreateExperiment:
    """Tests for create_experiment() API client method."""

    def test_creates_experiment(self, oauth_credentials: Session) -> None:
        """create_experiment() sends POST and returns experiment dict."""
        captured: list[tuple[str, str, Any]] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture request method, URL, and body."""
            captured.append(
                (request.method, str(request.url), json.loads(request.content))
            )
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": {"id": "new-123", "name": "New Experiment"},
                },
            )

        client = create_mock_client(oauth_credentials, handler)
        with client:
            result = client.create_experiment({"name": "New Experiment"})

        assert captured[0][0] == "POST"
        assert captured[0][2] == {"name": "New Experiment"}
        assert result["id"] == "new-123"

    def test_uses_trailing_slash(self, oauth_credentials: Session) -> None:
        """create_experiment() uses trailing slash on collection endpoint."""
        captured_urls: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture URL."""
            captured_urls.append(str(request.url))
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": {"id": "new-123", "name": "X"},
                },
            )

        client = create_mock_client(oauth_credentials, handler)
        with client:
            client.create_experiment({"name": "X"})

        # The URL should end with experiments/ (trailing slash)
        url = captured_urls[0]
        path = url.split("?")[0]
        assert path.endswith("experiments/")


class TestGetExperiment:
    """Tests for get_experiment() API client method."""

    def test_gets_experiment_by_id(self, oauth_credentials: Session) -> None:
        """get_experiment() sends GET with experiment ID in path."""
        captured_urls: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture URL and return experiment."""
            captured_urls.append(str(request.url))
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": {"id": "xyz-456", "name": "Test"},
                },
            )

        client = create_mock_client(oauth_credentials, handler)
        with client:
            result = client.get_experiment("xyz-456")

        assert "/experiments/xyz-456" in captured_urls[0]
        assert result["id"] == "xyz-456"

    def test_not_found(self, oauth_credentials: Session) -> None:
        """get_experiment() raises APIError on 404."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return 404."""
            return httpx.Response(
                404,
                json={"status": "error", "error": "Not found"},
            )

        client = create_mock_client(oauth_credentials, handler)
        with client, pytest.raises(APIError):
            client.get_experiment("nonexistent-id")


class TestUpdateExperiment:
    """Tests for update_experiment() API client method."""

    def test_updates_experiment(self, oauth_credentials: Session) -> None:
        """update_experiment() sends PATCH with body."""
        captured: list[tuple[str, Any]] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture method and body."""
            captured.append((request.method, json.loads(request.content)))
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": {"id": "xyz-456", "name": "Updated"},
                },
            )

        client = create_mock_client(oauth_credentials, handler)
        with client:
            result = client.update_experiment("xyz-456", {"name": "Updated"})

        assert captured[0][0] == "PATCH"
        assert result["name"] == "Updated"

    def test_url_contains_experiment_id(self, oauth_credentials: Session) -> None:
        """update_experiment() includes experiment ID in the URL."""
        captured_urls: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture URL."""
            captured_urls.append(str(request.url))
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": {"id": "xyz-456", "name": "X"},
                },
            )

        client = create_mock_client(oauth_credentials, handler)
        with client:
            client.update_experiment("xyz-456", {"name": "X"})

        assert "/experiments/xyz-456" in captured_urls[0]


class TestDeleteExperiment:
    """Tests for delete_experiment() API client method."""

    def test_deletes_experiment(self, oauth_credentials: Session) -> None:
        """delete_experiment() sends DELETE request."""
        captured_methods: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture method."""
            captured_methods.append(request.method)
            return httpx.Response(204)

        client = create_mock_client(oauth_credentials, handler)
        with client:
            client.delete_experiment("xyz-456")

        assert captured_methods[0] == "DELETE"

    def test_url_contains_experiment_id(self, oauth_credentials: Session) -> None:
        """delete_experiment() includes experiment ID in the URL."""
        captured_urls: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture URL."""
            captured_urls.append(str(request.url))
            return httpx.Response(204)

        client = create_mock_client(oauth_credentials, handler)
        with client:
            client.delete_experiment("xyz-456")

        assert "/experiments/xyz-456" in captured_urls[0]


# =============================================================================
# Experiment Lifecycle Tests
# =============================================================================


class TestLaunchExperiment:
    """Tests for launch_experiment() API client method."""

    def test_launches_experiment(self, oauth_credentials: Session) -> None:
        """launch_experiment() sends PUT to launch endpoint."""
        captured: list[tuple[str, str]] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture method and URL."""
            captured.append((request.method, str(request.url)))
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": {
                        "id": "xyz-456",
                        "name": "Test",
                        "status": "active",
                    },
                },
            )

        client = create_mock_client(oauth_credentials, handler)
        with client:
            result = client.launch_experiment("xyz-456")

        assert captured[0][0] == "PUT"
        assert "/experiments/xyz-456/launch" in captured[0][1]
        assert result["status"] == "active"

    def test_launch_non_draft_raises_error(self, oauth_credentials: Session) -> None:
        """launch_experiment() raises APIError when experiment is not in draft state."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return 400 for invalid state transition."""
            return httpx.Response(
                400,
                json={
                    "status": "error",
                    "error": "Experiment must be in draft state to launch",
                },
            )

        client = create_mock_client(oauth_credentials, handler)
        with client, pytest.raises(APIError):
            client.launch_experiment("xyz-456")


class TestConcludeExperiment:
    """Tests for conclude_experiment() API client method."""

    def test_concludes_experiment(self, oauth_credentials: Session) -> None:
        """conclude_experiment() sends PUT to force_conclude endpoint."""
        captured: list[tuple[str, str]] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture method and URL."""
            captured.append((request.method, str(request.url)))
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": {
                        "id": "xyz-456",
                        "name": "Test",
                        "status": "concluded",
                    },
                },
            )

        client = create_mock_client(oauth_credentials, handler)
        with client:
            result = client.conclude_experiment("xyz-456")

        assert captured[0][0] == "PUT"
        assert "/experiments/xyz-456/force_conclude" in captured[0][1]
        assert result["status"] == "concluded"

    def test_concludes_with_params(self, oauth_credentials: Session) -> None:
        """conclude_experiment() sends JSON body when params provided."""
        captured_bodies: list[Any] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture body."""
            captured_bodies.append(json.loads(request.content))
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": {
                        "id": "xyz-456",
                        "name": "Test",
                        "status": "concluded",
                    },
                },
            )

        client = create_mock_client(oauth_credentials, handler)
        with client:
            client.conclude_experiment("xyz-456", {"end_date": "2026-04-01"})

        assert captured_bodies[0] == {"end_date": "2026-04-01"}

    def test_concludes_without_params_sends_empty_body(
        self, oauth_credentials: Session
    ) -> None:
        """conclude_experiment() sends empty JSON body when no params."""
        captured_bodies: list[Any] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture body."""
            content = request.content
            captured_bodies.append(json.loads(content) if content else None)
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": {
                        "id": "xyz-456",
                        "name": "Test",
                        "status": "concluded",
                    },
                },
            )

        client = create_mock_client(oauth_credentials, handler)
        with client:
            client.conclude_experiment("xyz-456")

        assert captured_bodies[0] == {} or captured_bodies[0] is None

    def test_conclude_non_active_raises_error(self, oauth_credentials: Session) -> None:
        """conclude_experiment() raises APIError when experiment is not active."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return 400 for invalid state transition."""
            return httpx.Response(
                400,
                json={
                    "status": "error",
                    "error": "Experiment must be active to conclude",
                },
            )

        client = create_mock_client(oauth_credentials, handler)
        with client, pytest.raises(APIError):
            client.conclude_experiment("xyz-456")


class TestDecideExperiment:
    """Tests for decide_experiment() API client method."""

    def test_decides_experiment(self, oauth_credentials: Session) -> None:
        """decide_experiment() sends PATCH to decide endpoint."""
        captured: list[tuple[str, str, Any]] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture method, URL, and body."""
            captured.append(
                (request.method, str(request.url), json.loads(request.content))
            )
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": {
                        "id": "xyz-456",
                        "name": "Test",
                        "status": "success",
                    },
                },
            )

        client = create_mock_client(oauth_credentials, handler)
        with client:
            result = client.decide_experiment(
                "xyz-456", {"success": True, "variant": "treatment"}
            )

        assert captured[0][0] == "PATCH"
        assert "/experiments/xyz-456/decide" in captured[0][1]
        assert captured[0][2]["success"] is True
        assert result["status"] == "success"

    def test_decide_non_concluded_raises_error(
        self, oauth_credentials: Session
    ) -> None:
        """decide_experiment() raises APIError when experiment is not concluded."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return 400 for invalid state transition."""
            return httpx.Response(
                400,
                json={
                    "status": "error",
                    "error": "Experiment must be concluded to decide",
                },
            )

        client = create_mock_client(oauth_credentials, handler)
        with client, pytest.raises(APIError):
            client.decide_experiment("xyz-456", {"success": True})


# =============================================================================
# Experiment Management Tests
# =============================================================================


class TestArchiveExperiment:
    """Tests for archive_experiment() API client method."""

    def test_archives_experiment(self, oauth_credentials: Session) -> None:
        """archive_experiment() sends POST to archive endpoint."""
        captured: list[tuple[str, str]] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture method and URL."""
            captured.append((request.method, str(request.url)))
            return httpx.Response(204)

        client = create_mock_client(oauth_credentials, handler)
        with client:
            client.archive_experiment("xyz-456")

        assert captured[0][0] == "POST"
        assert "/experiments/xyz-456/archive" in captured[0][1]


class TestRestoreExperiment:
    """Tests for restore_experiment() API client method."""

    def test_restores_experiment(self, oauth_credentials: Session) -> None:
        """restore_experiment() sends DELETE to archive endpoint."""
        captured: list[tuple[str, str]] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture method and URL."""
            captured.append((request.method, str(request.url)))
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": {"id": "xyz-456", "name": "Restored"},
                },
            )

        client = create_mock_client(oauth_credentials, handler)
        with client:
            result = client.restore_experiment("xyz-456")

        assert captured[0][0] == "DELETE"
        assert "/experiments/xyz-456/archive" in captured[0][1]
        assert result["id"] == "xyz-456"


class TestDuplicateExperiment:
    """Tests for duplicate_experiment() API client method."""

    def test_duplicates_experiment(self, oauth_credentials: Session) -> None:
        """duplicate_experiment() sends POST to duplicate endpoint."""
        captured: list[tuple[str, str, Any]] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture method, URL, and body."""
            captured.append(
                (request.method, str(request.url), json.loads(request.content))
            )
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": {"id": "dup-789", "name": "Copy of Test"},
                },
            )

        client = create_mock_client(oauth_credentials, handler)
        with client:
            result = client.duplicate_experiment("xyz-456", {"name": "Copy of Test"})

        assert captured[0][0] == "POST"
        assert "/experiments/xyz-456/duplicate" in captured[0][1]
        assert captured[0][2] == {"name": "Copy of Test"}
        assert result["id"] == "dup-789"


class TestListErfExperiments:
    """Tests for list_erf_experiments() API client method."""

    def test_lists_erf_experiments(self, oauth_credentials: Session) -> None:
        """list_erf_experiments() sends GET to experiments/erf/ endpoint."""
        captured_urls: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture URL and return results."""
            captured_urls.append(str(request.url))
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": [
                        {"id": "erf-1", "name": "ERF Experiment"},
                    ],
                },
            )

        client = create_mock_client(oauth_credentials, handler)
        with client:
            result = client.list_erf_experiments()

        assert "/experiments/erf/" in captured_urls[0]
        assert len(result) == 1
        assert result[0]["id"] == "erf-1"

    def test_uses_get_method(self, oauth_credentials: Session) -> None:
        """list_erf_experiments() uses GET HTTP method."""
        captured_methods: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture HTTP method."""
            captured_methods.append(request.method)
            return httpx.Response(200, json={"status": "ok", "results": []})

        client = create_mock_client(oauth_credentials, handler)
        with client:
            client.list_erf_experiments()

        assert captured_methods[0] == "GET"
