# ruff: noqa: ARG001, ARG005
"""Unit tests for Workspace annotation methods (Phase 026).

Tests for annotation CRUD operations and annotation tag management
on the Workspace facade. Each method delegates to MixpanelAPIClient
and returns typed objects.

Verifies:
- Annotation CRUD: list, create, get, update, delete
- Annotation tags: list, create
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
    Annotation,
    AnnotationTag,
    CreateAnnotationParams,
    CreateAnnotationTagParams,
    UpdateAnnotationParams,
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


def _annotation_json(
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


def _tag_json(
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
# TestWorkspaceAnnotationCRUD
# =============================================================================


class TestWorkspaceAnnotationCRUD:
    """Tests for Workspace annotation CRUD methods."""

    def test_list_annotations(self, temp_dir: Path) -> None:
        """list_annotations() returns list of Annotation objects."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return annotation list."""
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": [
                        _annotation_json(1, "First"),
                        _annotation_json(2, "Second"),
                    ],
                },
            )

        ws = _make_workspace(temp_dir, handler)
        annotations = ws.list_annotations()

        assert len(annotations) == 2
        assert isinstance(annotations[0], Annotation)
        assert annotations[0].id == 1
        assert annotations[0].description == "First"
        assert annotations[1].id == 2

    def test_list_annotations_empty(self, temp_dir: Path) -> None:
        """list_annotations() returns empty list when no annotations exist."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return empty annotation list."""
            return httpx.Response(200, json={"status": "ok", "results": []})

        ws = _make_workspace(temp_dir, handler)
        annotations = ws.list_annotations()

        assert annotations == []

    def test_list_annotations_with_filters(self, temp_dir: Path) -> None:
        """list_annotations() passes filter params to API."""
        captured_url: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture URL and return annotation list."""
            captured_url.append(str(request.url))
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": [_annotation_json()],
                },
            )

        ws = _make_workspace(temp_dir, handler)
        annotations = ws.list_annotations(from_date="2026-01-01", to_date="2026-03-31")

        assert len(annotations) == 1
        assert isinstance(annotations[0], Annotation)
        assert len(captured_url) == 1
        assert "fromDate=2026-01-01" in captured_url[0]
        assert "toDate=2026-03-31" in captured_url[0]

    def test_create_annotation(self, temp_dir: Path) -> None:
        """create_annotation() returns the created Annotation."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return created annotation."""
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": _annotation_json(10, "New annotation"),
                },
            )

        ws = _make_workspace(temp_dir, handler)
        params = CreateAnnotationParams(date="2026-03-31", description="New annotation")
        annotation = ws.create_annotation(params)

        assert isinstance(annotation, Annotation)
        assert annotation.id == 10
        assert annotation.description == "New annotation"

    def test_create_annotation_with_options(self, temp_dir: Path) -> None:
        """create_annotation() sends optional fields when provided."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return created annotation with tags."""
            data = _annotation_json(10, "Tagged")
            data["tags"] = [{"id": 1, "name": "releases"}]
            return httpx.Response(
                200,
                json={"status": "ok", "results": data},
            )

        ws = _make_workspace(temp_dir, handler)
        params = CreateAnnotationParams(
            date="2026-03-31",
            description="Tagged",
            tags=[1],
            user_id=5,
        )
        annotation = ws.create_annotation(params)

        assert len(annotation.tags) == 1
        assert annotation.tags[0].name == "releases"

    def test_get_annotation(self, temp_dir: Path) -> None:
        """get_annotation() returns a single Annotation by ID."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return single annotation."""
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": _annotation_json(42, "Found it"),
                },
            )

        ws = _make_workspace(temp_dir, handler)
        annotation = ws.get_annotation(42)

        assert isinstance(annotation, Annotation)
        assert annotation.id == 42
        assert annotation.description == "Found it"

    def test_get_annotation_preserves_extra(self, temp_dir: Path) -> None:
        """get_annotation() preserves extra fields from the API."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return annotation with extra fields."""
            data = _annotation_json()
            data["custom_field"] = "extra_value"
            return httpx.Response(
                200,
                json={"status": "ok", "results": data},
            )

        ws = _make_workspace(temp_dir, handler)
        annotation = ws.get_annotation(1)

        assert annotation.model_extra is not None
        assert annotation.model_extra["custom_field"] == "extra_value"

    def test_update_annotation(self, temp_dir: Path) -> None:
        """update_annotation() returns the updated Annotation."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return updated annotation."""
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": _annotation_json(42, "Updated text"),
                },
            )

        ws = _make_workspace(temp_dir, handler)
        params = UpdateAnnotationParams(description="Updated text")
        annotation = ws.update_annotation(42, params)

        assert isinstance(annotation, Annotation)
        assert annotation.description == "Updated text"

    def test_delete_annotation(self, temp_dir: Path) -> None:
        """delete_annotation() returns None on success."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return 204 for delete."""
            return httpx.Response(204)

        ws = _make_workspace(temp_dir, handler)
        ws.delete_annotation(42)  # Should not raise

    def test_delete_annotation_200(self, temp_dir: Path) -> None:
        """delete_annotation() handles 200 response too."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return 200 for delete."""
            return httpx.Response(200, json={"status": "ok", "results": {}})

        ws = _make_workspace(temp_dir, handler)
        ws.delete_annotation(42)  # Should not raise


# =============================================================================
# TestWorkspaceAnnotationTags
# =============================================================================


class TestWorkspaceAnnotationTags:
    """Tests for Workspace annotation tag methods."""

    def test_list_annotation_tags(self, temp_dir: Path) -> None:
        """list_annotation_tags() returns list of AnnotationTag objects."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return tag list."""
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": [
                        _tag_json(1, "releases"),
                        _tag_json(2, "deployments"),
                    ],
                },
            )

        ws = _make_workspace(temp_dir, handler)
        tags = ws.list_annotation_tags()

        assert len(tags) == 2
        assert isinstance(tags[0], AnnotationTag)
        assert tags[0].name == "releases"
        assert tags[1].name == "deployments"

    def test_list_annotation_tags_empty(self, temp_dir: Path) -> None:
        """list_annotation_tags() returns empty list when no tags exist."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return empty tag list."""
            return httpx.Response(200, json={"status": "ok", "results": []})

        ws = _make_workspace(temp_dir, handler)
        tags = ws.list_annotation_tags()

        assert tags == []

    def test_create_annotation_tag(self, temp_dir: Path) -> None:
        """create_annotation_tag() returns the created AnnotationTag."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return created tag."""
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": _tag_json(3, "new-tag"),
                },
            )

        ws = _make_workspace(temp_dir, handler)
        params = CreateAnnotationTagParams(name="new-tag")
        tag = ws.create_annotation_tag(params)

        assert isinstance(tag, AnnotationTag)
        assert tag.id == 3
        assert tag.name == "new-tag"
