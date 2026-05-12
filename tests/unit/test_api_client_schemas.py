# ruff: noqa: ARG001, ARG005
"""Unit tests for Schema Registry API client methods (Phase 028).

Tests for:
- Schema Registry: list, create, create_bulk, update, update_bulk, delete
- URL path construction with entity_type and entity_name segments
- Percent-encoding of special characters in path segments
- Edge cases: duplicate entries, truncate mode, partial path variations
"""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any
from urllib.parse import unquote

import httpx
import pytest

from mixpanel_headless._internal.api_client import MixpanelAPIClient
from mixpanel_headless._internal.auth.session import Session
from mixpanel_headless.exceptions import MixpanelHeadlessError
from tests.conftest import make_session

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def oauth_credentials() -> Session:
    """Create OAuth credentials for App API testing.

    Returns:
        Credentials configured with OAuth auth method and a test access token.
    """
    return make_session(project_id="12345", region="us", oauth_token="test-oauth-token")


def create_mock_client(
    credentials: Session,
    handler: Callable[[httpx.Request], httpx.Response],
) -> MixpanelAPIClient:
    """Create a client with mock transport (no workspace ID set).

    Schema registry endpoints use maybe_scoped_path which defaults to project-scoped.

    Args:
        credentials: Authentication credentials.
        handler: Mock HTTP handler function.

    Returns:
        MixpanelAPIClient configured with mock transport.
    """
    transport = httpx.MockTransport(handler)
    return MixpanelAPIClient(session=credentials, _transport=transport)


# =============================================================================
# Schema Registry — list_schema_registry (US1 Scenario 1)
# =============================================================================


class TestListSchemaRegistry:
    """Tests for list_schema_registry() API client method."""

    def test_returns_list_all_schemas(self, oauth_credentials: Session) -> None:
        """list_schema_registry() with no entity_type returns all schemas."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return sample schema list for all entity types."""
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": [
                        {
                            "entity_type": "event",
                            "entity_name": "Signup",
                            "schema": {"properties": {"plan": {"type": "string"}}},
                        },
                        {
                            "entity_type": "profile",
                            "entity_name": "$name",
                            "schema": {"type": "string"},
                        },
                    ],
                },
            )

        client = create_mock_client(oauth_credentials, handler)
        with client:
            result = client.list_schema_registry()

        assert len(result) == 2
        assert result[0]["entity_type"] == "event"
        assert result[1]["entity_type"] == "profile"

    def test_returns_list_filtered_by_entity_type(
        self, oauth_credentials: Session
    ) -> None:
        """list_schema_registry(entity_type='event') returns only event schemas."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return event schemas only."""
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": [
                        {
                            "entity_type": "event",
                            "entity_name": "Signup",
                            "schema": {"properties": {}},
                        },
                    ],
                },
            )

        client = create_mock_client(oauth_credentials, handler)
        with client:
            result = client.list_schema_registry(entity_type="event")

        assert len(result) == 1
        assert result[0]["entity_type"] == "event"

    def test_uses_base_path_when_no_entity_type(
        self, oauth_credentials: Session
    ) -> None:
        """list_schema_registry() without entity_type targets schemas/ path."""
        captured_urls: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture URL."""
            captured_urls.append(str(request.url))
            return httpx.Response(200, json={"status": "ok", "results": []})

        client = create_mock_client(oauth_credentials, handler)
        with client:
            client.list_schema_registry()

        url = captured_urls[0]
        # Should not have an entity_type segment after schemas
        path = url.split("?")[0]
        assert path.rstrip("/").endswith("schemas")

    def test_uses_entity_type_path_segment(self, oauth_credentials: Session) -> None:
        """list_schema_registry(entity_type='event') targets schemas/event/ path."""
        captured_urls: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture URL."""
            captured_urls.append(str(request.url))
            return httpx.Response(200, json={"status": "ok", "results": []})

        client = create_mock_client(oauth_credentials, handler)
        with client:
            client.list_schema_registry(entity_type="event")

        assert "/schemas/event" in captured_urls[0]

    def test_uses_get_method(self, oauth_credentials: Session) -> None:
        """list_schema_registry() uses GET HTTP method."""
        captured_methods: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture HTTP method."""
            captured_methods.append(request.method)
            return httpx.Response(200, json={"status": "ok", "results": []})

        client = create_mock_client(oauth_credentials, handler)
        with client:
            client.list_schema_registry()

        assert captured_methods[0] == "GET"

    def test_uses_maybe_scoped_path(self, oauth_credentials: Session) -> None:
        """list_schema_registry() uses maybe_scoped_path for URL building."""
        captured_urls: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture URL."""
            captured_urls.append(str(request.url))
            return httpx.Response(200, json={"status": "ok", "results": []})

        client = create_mock_client(oauth_credentials, handler)
        with client:
            client.list_schema_registry()

        assert "/projects/12345/" in captured_urls[0]

    def test_empty_result(self, oauth_credentials: Session) -> None:
        """list_schema_registry() returns empty list when no schemas exist."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return empty results."""
            return httpx.Response(200, json={"status": "ok", "results": []})

        client = create_mock_client(oauth_credentials, handler)
        with client:
            result = client.list_schema_registry()

        assert result == []


# =============================================================================
# Schema Registry — create_schema (US1 Scenario 2)
# =============================================================================


class TestCreateSchema:
    """Tests for create_schema() API client method."""

    def test_returns_created_schema(self, oauth_credentials: Session) -> None:
        """create_schema() returns the created schema dict."""
        captured: list[tuple[str, Any]] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture method and body."""
            captured.append((request.method, json.loads(request.content)))
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": {
                        "entity_type": "event",
                        "entity_name": "Purchase",
                        "schema": {"properties": {"amount": {"type": "number"}}},
                    },
                },
            )

        client = create_mock_client(oauth_credentials, handler)
        with client:
            result = client.create_schema(
                "event",
                "Purchase",
                {"properties": {"amount": {"type": "number"}}},
            )

        assert captured[0][0] == "POST"
        assert result["entity_name"] == "Purchase"
        assert result["schema"]["properties"]["amount"]["type"] == "number"

    def test_path_includes_entity_type_and_name(
        self, oauth_credentials: Session
    ) -> None:
        """create_schema() builds path with entity_type and entity_name segments."""
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
            client.create_schema("event", "Purchase", {"properties": {}})

        assert "/schemas/event/Purchase" in captured_urls[0]

    def test_special_chars_percent_encoded(self, oauth_credentials: Session) -> None:
        """create_schema() percent-encodes special characters in entity_name."""
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
            client.create_schema("event", "User Sign Up / Login", {"properties": {}})

        url = captured_urls[0]
        # The entity name should be percent-encoded (spaces and slash)
        decoded_path = unquote(url)
        assert "User Sign Up / Login" in decoded_path
        # The raw URL should NOT contain literal spaces or unencoded slashes in the name
        path_after_schemas = url.split("/schemas/")[1]
        assert " " not in path_after_schemas.split("?")[0]

    def test_uses_post_method(self, oauth_credentials: Session) -> None:
        """create_schema() uses POST HTTP method."""
        captured_methods: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture HTTP method."""
            captured_methods.append(request.method)
            return httpx.Response(200, json={"status": "ok", "results": {}})

        client = create_mock_client(oauth_credentials, handler)
        with client:
            client.create_schema("event", "Signup", {"properties": {}})

        assert captured_methods[0] == "POST"

    def test_uses_maybe_scoped_path(self, oauth_credentials: Session) -> None:
        """create_schema() uses maybe_scoped_path for URL building."""
        captured_urls: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture URL."""
            captured_urls.append(str(request.url))
            return httpx.Response(200, json={"status": "ok", "results": {}})

        client = create_mock_client(oauth_credentials, handler)
        with client:
            client.create_schema("event", "Signup", {"properties": {}})

        assert "/projects/12345/" in captured_urls[0]

    def test_sends_schema_json_in_body(self, oauth_credentials: Session) -> None:
        """create_schema() sends schema_json as the request body."""
        captured_bodies: list[Any] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture request body."""
            captured_bodies.append(json.loads(request.content))
            return httpx.Response(200, json={"status": "ok", "results": {}})

        schema = {"properties": {"plan": {"type": "string"}}, "required": ["plan"]}
        client = create_mock_client(oauth_credentials, handler)
        with client:
            client.create_schema("event", "Signup", schema)

        assert captured_bodies[0] == schema


# =============================================================================
# Schema Registry — create_schemas_bulk (US1 Scenario 3 + 7)
# =============================================================================


class TestCreateSchemasBulk:
    """Tests for create_schemas_bulk() API client method."""

    def test_returns_added_and_deleted_counts(self, oauth_credentials: Session) -> None:
        """create_schemas_bulk() returns dict with added and deleted counts."""
        captured: list[tuple[str, Any]] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture method and body."""
            captured.append((request.method, json.loads(request.content)))
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": {"added": 3, "deleted": 0},
                },
            )

        body = {
            "entries": [
                {
                    "entity_type": "event",
                    "entity_name": "Signup",
                    "schema": {"properties": {}},
                },
                {
                    "entity_type": "event",
                    "entity_name": "Login",
                    "schema": {"properties": {}},
                },
                {
                    "entity_type": "event",
                    "entity_name": "Purchase",
                    "schema": {"properties": {}},
                },
            ],
            "truncate": False,
        }

        client = create_mock_client(oauth_credentials, handler)
        with client:
            result = client.create_schemas_bulk(body)

        assert captured[0][0] == "POST"
        assert result["added"] == 3
        assert result["deleted"] == 0

    def test_truncate_mode(self, oauth_credentials: Session) -> None:
        """create_schemas_bulk() with truncate=true reports deleted count."""
        captured_bodies: list[Any] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture body and return truncated response."""
            captured_bodies.append(json.loads(request.content))
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": {"added": 1, "deleted": 5},
                },
            )

        body = {
            "entries": [
                {
                    "entity_type": "event",
                    "entity_name": "Signup",
                    "schema": {"properties": {}},
                },
            ],
            "truncate": True,
        }

        client = create_mock_client(oauth_credentials, handler)
        with client:
            result = client.create_schemas_bulk(body)

        assert captured_bodies[0]["truncate"] is True
        assert result["deleted"] == 5
        assert result["added"] == 1

    def test_empty_entries(self, oauth_credentials: Session) -> None:
        """create_schemas_bulk() with empty entries list returns zero counts."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return zero counts."""
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": {"added": 0, "deleted": 0},
                },
            )

        body: dict[str, Any] = {"entries": [], "truncate": False}

        client = create_mock_client(oauth_credentials, handler)
        with client:
            result = client.create_schemas_bulk(body)

        assert result["added"] == 0
        assert result["deleted"] == 0

    def test_truncate_with_empty_entries(self, oauth_credentials: Session) -> None:
        """create_schemas_bulk() with truncate=true and empty entries deletes all."""
        captured_bodies: list[Any] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture body and return truncated-only response."""
            captured_bodies.append(json.loads(request.content))
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": {"added": 0, "deleted": 10},
                },
            )

        body: dict[str, Any] = {"entries": [], "truncate": True}

        client = create_mock_client(oauth_credentials, handler)
        with client:
            result = client.create_schemas_bulk(body)

        assert captured_bodies[0]["truncate"] is True
        assert captured_bodies[0]["entries"] == []
        assert result["deleted"] == 10

    def test_duplicate_entries(self, oauth_credentials: Session) -> None:
        """create_schemas_bulk() with duplicate entries sends them as-is to API."""
        captured_bodies: list[Any] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture body."""
            captured_bodies.append(json.loads(request.content))
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": {"added": 1, "deleted": 0},
                },
            )

        entry = {
            "entity_type": "event",
            "entity_name": "Signup",
            "schema": {"properties": {}},
        }
        body = {"entries": [entry, entry], "truncate": False}

        client = create_mock_client(oauth_credentials, handler)
        with client:
            client.create_schemas_bulk(body)

        assert len(captured_bodies[0]["entries"]) == 2

    def test_uses_base_schemas_path(self, oauth_credentials: Session) -> None:
        """create_schemas_bulk() targets schemas/ base path (no entity segments)."""
        captured_urls: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture URL."""
            captured_urls.append(str(request.url))
            return httpx.Response(
                200,
                json={"status": "ok", "results": {"added": 0, "deleted": 0}},
            )

        client = create_mock_client(oauth_credentials, handler)
        with client:
            client.create_schemas_bulk({"entries": [], "truncate": False})

        url = captured_urls[0]
        path = url.split("?")[0]
        assert path.rstrip("/").endswith("schemas")

    def test_uses_post_method(self, oauth_credentials: Session) -> None:
        """create_schemas_bulk() uses POST HTTP method."""
        captured_methods: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture HTTP method."""
            captured_methods.append(request.method)
            return httpx.Response(
                200,
                json={"status": "ok", "results": {"added": 0, "deleted": 0}},
            )

        client = create_mock_client(oauth_credentials, handler)
        with client:
            client.create_schemas_bulk({"entries": [], "truncate": False})

        assert captured_methods[0] == "POST"

    def test_uses_maybe_scoped_path(self, oauth_credentials: Session) -> None:
        """create_schemas_bulk() uses maybe_scoped_path for URL building."""
        captured_urls: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture URL."""
            captured_urls.append(str(request.url))
            return httpx.Response(
                200,
                json={"status": "ok", "results": {"added": 0, "deleted": 0}},
            )

        client = create_mock_client(oauth_credentials, handler)
        with client:
            client.create_schemas_bulk({"entries": [], "truncate": False})

        assert "/projects/12345/" in captured_urls[0]


# =============================================================================
# Schema Registry — update_schema (US1 Scenario 4)
# =============================================================================


class TestUpdateSchema:
    """Tests for update_schema() API client method."""

    def test_returns_updated_schema(self, oauth_credentials: Session) -> None:
        """update_schema() returns the updated schema dict."""
        captured: list[tuple[str, Any]] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture method and body."""
            captured.append((request.method, json.loads(request.content)))
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": {
                        "entity_type": "event",
                        "entity_name": "Purchase",
                        "schema": {
                            "properties": {
                                "amount": {"type": "number"},
                                "currency": {"type": "string"},
                            },
                        },
                    },
                },
            )

        client = create_mock_client(oauth_credentials, handler)
        with client:
            result = client.update_schema(
                "event",
                "Purchase",
                {
                    "properties": {
                        "amount": {"type": "number"},
                        "currency": {"type": "string"},
                    },
                },
            )

        assert captured[0][0] == "PATCH"
        assert result["entity_name"] == "Purchase"
        assert "currency" in result["schema"]["properties"]

    def test_path_includes_entity_type_and_name(
        self, oauth_credentials: Session
    ) -> None:
        """update_schema() builds path with entity_type and entity_name segments."""
        captured_urls: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture URL."""
            captured_urls.append(str(request.url))
            return httpx.Response(200, json={"status": "ok", "results": {}})

        client = create_mock_client(oauth_credentials, handler)
        with client:
            client.update_schema("event", "Purchase", {"properties": {}})

        assert "/schemas/event/Purchase" in captured_urls[0]

    def test_uses_patch_method(self, oauth_credentials: Session) -> None:
        """update_schema() uses PATCH HTTP method."""
        captured_methods: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture HTTP method."""
            captured_methods.append(request.method)
            return httpx.Response(200, json={"status": "ok", "results": {}})

        client = create_mock_client(oauth_credentials, handler)
        with client:
            client.update_schema("event", "Signup", {"properties": {}})

        assert captured_methods[0] == "PATCH"

    def test_sends_schema_json_in_body(self, oauth_credentials: Session) -> None:
        """update_schema() sends schema_json as the request body."""
        captured_bodies: list[Any] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture request body."""
            captured_bodies.append(json.loads(request.content))
            return httpx.Response(200, json={"status": "ok", "results": {}})

        schema = {"properties": {"plan": {"type": "string"}}}
        client = create_mock_client(oauth_credentials, handler)
        with client:
            client.update_schema("event", "Signup", schema)

        assert captured_bodies[0] == schema

    def test_uses_maybe_scoped_path(self, oauth_credentials: Session) -> None:
        """update_schema() uses maybe_scoped_path for URL building."""
        captured_urls: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture URL."""
            captured_urls.append(str(request.url))
            return httpx.Response(200, json={"status": "ok", "results": {}})

        client = create_mock_client(oauth_credentials, handler)
        with client:
            client.update_schema("event", "Signup", {"properties": {}})

        assert "/projects/12345/" in captured_urls[0]


# =============================================================================
# Schema Registry — update_schemas_bulk (US1 Scenario 5)
# =============================================================================


class TestUpdateSchemasBulk:
    """Tests for update_schemas_bulk() API client method."""

    def test_returns_list_of_results(self, oauth_credentials: Session) -> None:
        """update_schemas_bulk() returns a list of per-entry result dicts."""
        captured: list[tuple[str, Any]] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture method and body."""
            captured.append((request.method, json.loads(request.content)))
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": [
                        {
                            "entity_type": "event",
                            "entity_name": "Signup",
                            "status": "ok",
                        },
                        {
                            "entity_type": "event",
                            "entity_name": "Login",
                            "status": "ok",
                        },
                    ],
                },
            )

        body = {
            "entries": [
                {
                    "entity_type": "event",
                    "entity_name": "Signup",
                    "schema": {"properties": {}},
                },
                {
                    "entity_type": "event",
                    "entity_name": "Login",
                    "schema": {"properties": {}},
                },
            ],
        }

        client = create_mock_client(oauth_credentials, handler)
        with client:
            result = client.update_schemas_bulk(body)

        assert captured[0][0] == "PATCH"
        assert len(result) == 2
        assert result[0]["status"] == "ok"

    def test_mixed_ok_and_error_results(self, oauth_credentials: Session) -> None:
        """update_schemas_bulk() returns results with mixed ok/error statuses."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return mixed success/error results."""
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": [
                        {
                            "entity_type": "event",
                            "entity_name": "Signup",
                            "status": "ok",
                        },
                        {
                            "entity_type": "event",
                            "entity_name": "NonExistent",
                            "status": "error",
                            "error": "Schema not found",
                        },
                    ],
                },
            )

        body = {
            "entries": [
                {
                    "entity_type": "event",
                    "entity_name": "Signup",
                    "schema": {"properties": {}},
                },
                {
                    "entity_type": "event",
                    "entity_name": "NonExistent",
                    "schema": {"properties": {}},
                },
            ],
        }

        client = create_mock_client(oauth_credentials, handler)
        with client:
            result = client.update_schemas_bulk(body)

        assert len(result) == 2
        assert result[0]["status"] == "ok"
        assert result[1]["status"] == "error"
        assert result[1]["error"] == "Schema not found"

    def test_uses_base_schemas_path(self, oauth_credentials: Session) -> None:
        """update_schemas_bulk() targets schemas/ base path."""
        captured_urls: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture URL."""
            captured_urls.append(str(request.url))
            return httpx.Response(200, json={"status": "ok", "results": []})

        client = create_mock_client(oauth_credentials, handler)
        with client:
            client.update_schemas_bulk({"entries": []})

        url = captured_urls[0]
        path = url.split("?")[0]
        assert path.rstrip("/").endswith("schemas")

    def test_uses_patch_method(self, oauth_credentials: Session) -> None:
        """update_schemas_bulk() uses PATCH HTTP method."""
        captured_methods: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture HTTP method."""
            captured_methods.append(request.method)
            return httpx.Response(200, json={"status": "ok", "results": []})

        client = create_mock_client(oauth_credentials, handler)
        with client:
            client.update_schemas_bulk({"entries": []})

        assert captured_methods[0] == "PATCH"

    def test_uses_maybe_scoped_path(self, oauth_credentials: Session) -> None:
        """update_schemas_bulk() uses maybe_scoped_path for URL building."""
        captured_urls: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture URL."""
            captured_urls.append(str(request.url))
            return httpx.Response(200, json={"status": "ok", "results": []})

        client = create_mock_client(oauth_credentials, handler)
        with client:
            client.update_schemas_bulk({"entries": []})

        assert "/projects/12345/" in captured_urls[0]


# =============================================================================
# Schema Registry — delete_schemas (US1 Scenario 6)
# =============================================================================


class TestDeleteSchemas:
    """Tests for delete_schemas() API client method."""

    def test_delete_all_schemas(self, oauth_credentials: Session) -> None:
        """delete_schemas() with no args deletes all schemas and returns count."""
        captured_methods: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture method and return delete count."""
            captured_methods.append(request.method)
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": {"delete_count": 15},
                },
            )

        client = create_mock_client(oauth_credentials, handler)
        with client:
            result = client.delete_schemas()

        assert captured_methods[0] == "DELETE"
        assert result["delete_count"] == 15

    def test_delete_by_entity_type(self, oauth_credentials: Session) -> None:
        """delete_schemas(entity_type='event') deletes all event schemas."""
        captured_urls: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture URL."""
            captured_urls.append(str(request.url))
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": {"delete_count": 5},
                },
            )

        client = create_mock_client(oauth_credentials, handler)
        with client:
            result = client.delete_schemas(entity_type="event")

        assert "/schemas/event" in captured_urls[0]
        assert result["delete_count"] == 5

    def test_delete_by_entity_type_and_name(self, oauth_credentials: Session) -> None:
        """delete_schemas(entity_type='event', entity_name='Signup') deletes one."""
        captured_urls: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture URL."""
            captured_urls.append(str(request.url))
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": {"delete_count": 1},
                },
            )

        client = create_mock_client(oauth_credentials, handler)
        with client:
            result = client.delete_schemas(entity_type="event", entity_name="Signup")

        assert "/schemas/event/Signup" in captured_urls[0]
        assert result["delete_count"] == 1

    def test_delete_all_path(self, oauth_credentials: Session) -> None:
        """delete_schemas() with no args targets schemas/ base path."""
        captured_urls: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture URL."""
            captured_urls.append(str(request.url))
            return httpx.Response(
                200,
                json={"status": "ok", "results": {"delete_count": 0}},
            )

        client = create_mock_client(oauth_credentials, handler)
        with client:
            client.delete_schemas()

        path = captured_urls[0].split("?")[0]
        assert path.rstrip("/").endswith("schemas")

    def test_delete_with_entity_name_only_raises(
        self, oauth_credentials: Session
    ) -> None:
        """delete_schemas(entity_name=X) without entity_type raises error.

        Providing entity_name without entity_type would silently delete all
        schemas instead of the intended single schema.

        Args:
            oauth_credentials: OAuth credentials fixture.
        """

        def handler(request: httpx.Request) -> httpx.Response:
            """Should never be called."""
            return httpx.Response(
                200,
                json={"status": "ok", "results": {"delete_count": 0}},
            )

        client = create_mock_client(oauth_credentials, handler)
        with (
            client,
            pytest.raises(
                MixpanelHeadlessError, match="entity_name requires entity_type"
            ),
        ):
            client.delete_schemas(entity_name="Signup")

    def test_uses_delete_method(self, oauth_credentials: Session) -> None:
        """delete_schemas() uses DELETE HTTP method."""
        captured_methods: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture HTTP method."""
            captured_methods.append(request.method)
            return httpx.Response(
                200,
                json={"status": "ok", "results": {"delete_count": 0}},
            )

        client = create_mock_client(oauth_credentials, handler)
        with client:
            client.delete_schemas()

        assert captured_methods[0] == "DELETE"

    def test_uses_maybe_scoped_path(self, oauth_credentials: Session) -> None:
        """delete_schemas() uses maybe_scoped_path for URL building."""
        captured_urls: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture URL."""
            captured_urls.append(str(request.url))
            return httpx.Response(
                200,
                json={"status": "ok", "results": {"delete_count": 0}},
            )

        client = create_mock_client(oauth_credentials, handler)
        with client:
            client.delete_schemas()

        assert "/projects/12345/" in captured_urls[0]


# =============================================================================
# Edge Cases — Error Handling
# =============================================================================


class TestCreateSchemaAlreadyExists:
    """Tests for create_schema() when schema already exists."""

    def test_api_error_for_existing_schema(self, oauth_credentials: Session) -> None:
        """create_schema() propagates API error when schema already exists.

        When creating a schema for an entity that already has a schema defined,
        the API returns an error response. The client should propagate this
        error through the standard error handling path.
        """

        def handler(request: httpx.Request) -> httpx.Response:
            """Return error for existing schema."""
            return httpx.Response(
                409,
                json={
                    "status": "error",
                    "error": "Schema already exists for event 'Signup'",
                },
            )

        client = create_mock_client(oauth_credentials, handler)
        with client, pytest.raises(Exception):  # noqa: B017
            client.create_schema("event", "Signup", {"properties": {}})


class TestCreateSchemasBulkDuplicateEntries:
    """Tests for create_schemas_bulk() with duplicate entries in the same request."""

    def test_sends_duplicates_to_api(self, oauth_credentials: Session) -> None:
        """create_schemas_bulk() does not deduplicate on client side.

        The client sends duplicate entries as-is to the API, which decides
        how to handle them (last-write-wins, error, etc.).
        """
        captured_bodies: list[Any] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture body and return success."""
            captured_bodies.append(json.loads(request.content))
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": {"added": 1, "deleted": 0},
                },
            )

        entry = {
            "entity_type": "event",
            "entity_name": "Signup",
            "schema": {"properties": {"plan": {"type": "string"}}},
        }
        body = {"entries": [entry, entry, entry], "truncate": False}

        client = create_mock_client(oauth_credentials, handler)
        with client:
            client.create_schemas_bulk(body)

        assert len(captured_bodies[0]["entries"]) == 3
