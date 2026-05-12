# ruff: noqa: ARG001, ARG005
"""Unit tests for Annotation API client methods (Phase 026).

Tests for:
- Annotation CRUD: list, create, get, update, delete
- Annotation tags: list, create
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
    """Create a client with mock transport.

    Annotations use maybe_scoped_path (project-scoped by default),
    so no workspace_id is needed.

    Args:
        credentials: Authentication credentials.
        handler: Mock HTTP handler function.

    Returns:
        MixpanelAPIClient configured with mock transport.
    """
    transport = httpx.MockTransport(handler)
    client = MixpanelAPIClient(session=credentials, _transport=transport)
    return client


def _annotation_result(
    id: int = 1,
    description: str = "Test annotation",
) -> dict[str, Any]:
    """Return a minimal annotation dict matching the API shape.

    Args:
        id: Annotation ID.
        description: Annotation text.

    Returns:
        Dict that can be parsed into an Annotation model.
    """
    return {
        "id": id,
        "project_id": 12345,
        "date": "2026-03-31",
        "description": description,
        "tags": [],
    }


def _tag_result(
    id: int = 1,
    name: str = "releases",
) -> dict[str, Any]:
    """Return a minimal annotation tag dict matching the API shape.

    Args:
        id: Tag ID.
        name: Tag name.

    Returns:
        Dict that can be parsed into an AnnotationTag model.
    """
    return {"id": id, "name": name}


# =============================================================================
# Annotation CRUD Tests
# =============================================================================


class TestListAnnotations:
    """Tests for list_annotations() API client method."""

    def test_returns_annotation_list(self, oauth_credentials: Session) -> None:
        """list_annotations() returns a list of annotation dicts."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return sample annotation list."""
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": [
                        _annotation_result(1, "First"),
                        _annotation_result(2, "Second"),
                    ],
                },
            )

        client = create_mock_client(oauth_credentials, handler)
        with client:
            result = client.list_annotations()

        assert len(result) == 2
        assert result[0]["id"] == 1
        assert result[1]["description"] == "Second"

    def test_uses_maybe_scoped_path(self, oauth_credentials: Session) -> None:
        """list_annotations() uses maybe_scoped_path for URL building."""
        captured_urls: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture URL."""
            captured_urls.append(str(request.url))
            return httpx.Response(200, json={"status": "ok", "results": []})

        client = create_mock_client(oauth_credentials, handler)
        with client:
            client.list_annotations()

        assert "/annotations/" in captured_urls[0]

    def test_from_date_camel_case(self, oauth_credentials: Session) -> None:
        """list_annotations(from_date=...) passes fromDate query param."""
        captured_urls: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture URL."""
            captured_urls.append(str(request.url))
            return httpx.Response(200, json={"status": "ok", "results": []})

        client = create_mock_client(oauth_credentials, handler)
        with client:
            client.list_annotations(from_date="2026-01-01")

        assert "fromDate=2026-01-01" in captured_urls[0]

    def test_to_date_camel_case(self, oauth_credentials: Session) -> None:
        """list_annotations(to_date=...) passes toDate query param."""
        captured_urls: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture URL."""
            captured_urls.append(str(request.url))
            return httpx.Response(200, json={"status": "ok", "results": []})

        client = create_mock_client(oauth_credentials, handler)
        with client:
            client.list_annotations(to_date="2026-03-31")

        assert "toDate=2026-03-31" in captured_urls[0]

    def test_tags_filter(self, oauth_credentials: Session) -> None:
        """list_annotations(tags=[1, 2]) passes comma-separated tag IDs."""
        captured_urls: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture URL."""
            captured_urls.append(str(request.url))
            return httpx.Response(200, json={"status": "ok", "results": []})

        client = create_mock_client(oauth_credentials, handler)
        with client:
            client.list_annotations(tags=[1, 2])

        url = captured_urls[0]
        assert "tags=" in url
        assert "1" in url
        assert "2" in url

    def test_empty_result(self, oauth_credentials: Session) -> None:
        """list_annotations() returns empty list when no annotations exist."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return empty results."""
            return httpx.Response(200, json={"status": "ok", "results": []})

        client = create_mock_client(oauth_credentials, handler)
        with client:
            result = client.list_annotations()

        assert result == []

    def test_uses_get_method(self, oauth_credentials: Session) -> None:
        """list_annotations() uses GET HTTP method."""
        captured_methods: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture HTTP method."""
            captured_methods.append(request.method)
            return httpx.Response(200, json={"status": "ok", "results": []})

        client = create_mock_client(oauth_credentials, handler)
        with client:
            client.list_annotations()

        assert captured_methods[0] == "GET"


class TestCreateAnnotation:
    """Tests for create_annotation() API client method."""

    def test_creates_annotation(self, oauth_credentials: Session) -> None:
        """create_annotation() sends POST and returns annotation dict."""
        captured: list[tuple[str, Any]] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture request method and body."""
            captured.append((request.method, json.loads(request.content)))
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": _annotation_result(1, "New annotation"),
                },
            )

        client = create_mock_client(oauth_credentials, handler)
        with client:
            result = client.create_annotation(
                {"date": "2026-03-31", "description": "New annotation"}
            )

        assert captured[0][0] == "POST"
        assert captured[0][1]["description"] == "New annotation"
        assert result["id"] == 1

    def test_url_path(self, oauth_credentials: Session) -> None:
        """create_annotation() posts to the annotations endpoint."""
        captured_urls: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture URL."""
            captured_urls.append(str(request.url))
            return httpx.Response(
                200,
                json={"status": "ok", "results": _annotation_result()},
            )

        client = create_mock_client(oauth_credentials, handler)
        with client:
            client.create_annotation({"date": "2026-03-31", "description": "X"})

        assert "/annotations/" in captured_urls[0]


class TestGetAnnotation:
    """Tests for get_annotation() API client method."""

    def test_gets_annotation_by_id(self, oauth_credentials: Session) -> None:
        """get_annotation() sends GET with annotation ID in path."""
        captured_urls: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture URL and return annotation."""
            captured_urls.append(str(request.url))
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": _annotation_result(42, "Found"),
                },
            )

        client = create_mock_client(oauth_credentials, handler)
        with client:
            result = client.get_annotation(42)

        assert "/annotations/42/" in captured_urls[0]
        assert result["id"] == 42

    def test_uses_get_method(self, oauth_credentials: Session) -> None:
        """get_annotation() uses GET HTTP method."""
        captured_methods: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture HTTP method."""
            captured_methods.append(request.method)
            return httpx.Response(
                200,
                json={"status": "ok", "results": _annotation_result()},
            )

        client = create_mock_client(oauth_credentials, handler)
        with client:
            client.get_annotation(1)

        assert captured_methods[0] == "GET"


class TestUpdateAnnotation:
    """Tests for update_annotation() API client method."""

    def test_updates_annotation(self, oauth_credentials: Session) -> None:
        """update_annotation() sends PATCH with body."""
        captured: list[tuple[str, Any]] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture method and body."""
            captured.append((request.method, json.loads(request.content)))
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": _annotation_result(42, "Updated"),
                },
            )

        client = create_mock_client(oauth_credentials, handler)
        with client:
            result = client.update_annotation(42, {"description": "Updated"})

        assert captured[0][0] == "PATCH"
        assert captured[0][1]["description"] == "Updated"
        assert result["description"] == "Updated"

    def test_url_path(self, oauth_credentials: Session) -> None:
        """update_annotation() targets the correct annotation ID in URL."""
        captured_urls: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture URL."""
            captured_urls.append(str(request.url))
            return httpx.Response(
                200,
                json={"status": "ok", "results": _annotation_result()},
            )

        client = create_mock_client(oauth_credentials, handler)
        with client:
            client.update_annotation(42, {"description": "X"})

        assert "/annotations/42/" in captured_urls[0]


class TestDeleteAnnotation:
    """Tests for delete_annotation() API client method."""

    def test_deletes_annotation(self, oauth_credentials: Session) -> None:
        """delete_annotation() sends DELETE request."""
        captured_methods: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture method."""
            captured_methods.append(request.method)
            return httpx.Response(204)

        client = create_mock_client(oauth_credentials, handler)
        with client:
            client.delete_annotation(42)

        assert captured_methods[0] == "DELETE"

    def test_url_path(self, oauth_credentials: Session) -> None:
        """delete_annotation() targets the correct annotation ID in URL."""
        captured_urls: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture URL."""
            captured_urls.append(str(request.url))
            return httpx.Response(204)

        client = create_mock_client(oauth_credentials, handler)
        with client:
            client.delete_annotation(42)

        assert "/annotations/42/" in captured_urls[0]


# =============================================================================
# Annotation Tag Tests
# =============================================================================


class TestListAnnotationTags:
    """Tests for list_annotation_tags() API client method."""

    def test_returns_tag_list(self, oauth_credentials: Session) -> None:
        """list_annotation_tags() returns a list of tag dicts."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return sample tag list."""
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": [
                        _tag_result(1, "releases"),
                        _tag_result(2, "deployments"),
                    ],
                },
            )

        client = create_mock_client(oauth_credentials, handler)
        with client:
            result = client.list_annotation_tags()

        assert len(result) == 2
        assert result[0]["name"] == "releases"
        assert result[1]["name"] == "deployments"

    def test_url_path(self, oauth_credentials: Session) -> None:
        """list_annotation_tags() uses the tags sub-path."""
        captured_urls: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture URL."""
            captured_urls.append(str(request.url))
            return httpx.Response(200, json={"status": "ok", "results": []})

        client = create_mock_client(oauth_credentials, handler)
        with client:
            client.list_annotation_tags()

        assert "/annotations/tags/" in captured_urls[0]

    def test_uses_get_method(self, oauth_credentials: Session) -> None:
        """list_annotation_tags() uses GET HTTP method."""
        captured_methods: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture HTTP method."""
            captured_methods.append(request.method)
            return httpx.Response(200, json={"status": "ok", "results": []})

        client = create_mock_client(oauth_credentials, handler)
        with client:
            client.list_annotation_tags()

        assert captured_methods[0] == "GET"


class TestCreateAnnotationTag:
    """Tests for create_annotation_tag() API client method."""

    def test_creates_tag(self, oauth_credentials: Session) -> None:
        """create_annotation_tag() sends POST and returns tag dict."""
        captured: list[tuple[str, Any]] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture request method and body."""
            captured.append((request.method, json.loads(request.content)))
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": _tag_result(3, "new-tag"),
                },
            )

        client = create_mock_client(oauth_credentials, handler)
        with client:
            result = client.create_annotation_tag({"name": "new-tag"})

        assert captured[0][0] == "POST"
        assert captured[0][1]["name"] == "new-tag"
        assert result["id"] == 3
        assert result["name"] == "new-tag"

    def test_url_path(self, oauth_credentials: Session) -> None:
        """create_annotation_tag() posts to the tags sub-path."""
        captured_urls: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture URL."""
            captured_urls.append(str(request.url))
            return httpx.Response(
                200,
                json={"status": "ok", "results": _tag_result()},
            )

        client = create_mock_client(oauth_credentials, handler)
        with client:
            client.create_annotation_tag({"name": "test"})

        assert "/annotations/tags/" in captured_urls[0]
