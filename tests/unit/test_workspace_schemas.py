# ruff: noqa: ARG001, ARG005
"""Unit tests for Workspace schema registry methods (Phase 028).

Tests for schema registry CRUD operations on the Workspace facade:
- list_schema_registry: list all or filtered by entity_type
- create_schema: create a single schema definition
- create_schemas_bulk: bulk create schemas with optional truncate
- update_schema: update a single schema (merge semantics)
- update_schemas_bulk: bulk update schemas (merge per entry)
- delete_schemas: delete by entity_type and/or entity_name

Verifies:
- Correct return types (SchemaEntry, BulkCreateSchemasResponse, etc.)
- Fields match mock data
- Parameters serialized correctly
- Edge cases (empty lists, no filters)
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import httpx
import pytest
from pydantic import SecretStr

from mixpanel_headless._internal.api_client import MixpanelAPIClient
from mixpanel_headless._internal.auth.account import ServiceAccount
from mixpanel_headless._internal.auth.session import Project, Session
from mixpanel_headless.types import (
    BulkCreateSchemasParams,
    BulkCreateSchemasResponse,
    BulkPatchResult,
    DeleteSchemasResponse,
    SchemaEntry,
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


def _schema_entry_json(
    entity_type: str = "event",
    name: str = "Purchase",
    schema_definition: dict[str, Any] | None = None,
    version: str | None = "2025-01-15",
) -> dict[str, Any]:
    """Return a minimal schema entry dict matching the API shape.

    Args:
        entity_type: Entity type ("event", "custom_event", "profile").
        name: Entity name.
        schema_definition: JSON Schema definition. Defaults to a simple schema.
        version: Schema version in YYYY-MM-DD format.

    Returns:
        Dict that can be parsed into a SchemaEntry model.
    """
    result: dict[str, Any] = {
        "entityType": entity_type,
        "name": name,
        "schemaJson": schema_definition
        or {"properties": {"amount": {"type": "number"}}, "required": ["amount"]},
    }
    if version is not None:
        result["version"] = version
    return result


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture()
def temp_dir(tmp_path: Path) -> Path:
    """Provide a temporary directory for test artifacts.

    Args:
        tmp_path: Pytest-provided temporary path.

    Returns:
        Path to the temporary directory.
    """
    return tmp_path


# =============================================================================
# Tests: list_schema_registry
# =============================================================================


class TestListSchemaRegistry:
    """Tests for Workspace.list_schema_registry()."""

    def test_list_all_schemas(self, temp_dir: Path) -> None:
        """list_schema_registry() returns all schemas as SchemaEntry list."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return schema list response."""
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": [
                        _schema_entry_json("event", "Purchase"),
                        _schema_entry_json("event", "Login"),
                        _schema_entry_json("profile", "$user"),
                    ],
                },
            )

        ws = _make_workspace(temp_dir, handler)
        schemas = ws.list_schema_registry()

        assert len(schemas) == 3
        assert isinstance(schemas[0], SchemaEntry)
        assert schemas[0].entity_type == "event"
        assert schemas[0].name == "Purchase"
        assert schemas[1].name == "Login"
        assert schemas[2].entity_type == "profile"
        assert schemas[2].name == "$user"

    def test_list_schemas_empty(self, temp_dir: Path) -> None:
        """list_schema_registry() returns empty list when no schemas exist."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return empty schema list."""
            return httpx.Response(200, json={"status": "ok", "results": []})

        ws = _make_workspace(temp_dir, handler)
        schemas = ws.list_schema_registry()

        assert schemas == []

    def test_list_schemas_with_entity_type_filter(self, temp_dir: Path) -> None:
        """list_schema_registry(entity_type='event') passes filter to API."""
        captured_url: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture URL and return filtered schema list."""
            captured_url.append(str(request.url))
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": [
                        _schema_entry_json("event", "Purchase"),
                    ],
                },
            )

        ws = _make_workspace(temp_dir, handler)
        schemas = ws.list_schema_registry(entity_type="event")

        assert len(schemas) == 1
        assert isinstance(schemas[0], SchemaEntry)
        assert schemas[0].entity_type == "event"
        assert len(captured_url) == 1
        assert "schemas/event" in captured_url[0]

    def test_list_schemas_preserves_schema_definition(self, temp_dir: Path) -> None:
        """list_schema_registry() preserves the schemaJson field content."""
        custom_schema = {
            "type": "object",
            "properties": {
                "amount": {"type": "number"},
                "currency": {"type": "string", "enum": ["USD", "EUR"]},
            },
            "required": ["amount", "currency"],
        }

        def handler(request: httpx.Request) -> httpx.Response:
            """Return schema with detailed schemaJson."""
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": [
                        _schema_entry_json(
                            "event", "Purchase", schema_definition=custom_schema
                        ),
                    ],
                },
            )

        ws = _make_workspace(temp_dir, handler)
        schemas = ws.list_schema_registry()

        assert len(schemas) == 1
        assert schemas[0].schema_definition == custom_schema

    def test_list_schemas_preserves_version(self, temp_dir: Path) -> None:
        """list_schema_registry() preserves the version field."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return schema with version."""
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": [
                        _schema_entry_json("event", "Purchase", version="2025-03-20"),
                    ],
                },
            )

        ws = _make_workspace(temp_dir, handler)
        schemas = ws.list_schema_registry()

        assert schemas[0].version == "2025-03-20"

    def test_list_schemas_extra_fields_preserved(self, temp_dir: Path) -> None:
        """list_schema_registry() preserves unknown fields (extra='allow')."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return schema with extra fields."""
            entry = _schema_entry_json("event", "Purchase")
            entry["customField"] = "extra-value"
            return httpx.Response(
                200,
                json={"status": "ok", "results": [entry]},
            )

        ws = _make_workspace(temp_dir, handler)
        schemas = ws.list_schema_registry()

        assert len(schemas) == 1
        # Extra fields should be accessible via model_extra or attribute
        assert hasattr(schemas[0], "customField") or "customField" in (
            schemas[0].model_extra or {}
        )


# =============================================================================
# Tests: create_schema
# =============================================================================


class TestCreateSchema:
    """Tests for Workspace.create_schema()."""

    def test_create_schema_returns_dict(self, temp_dir: Path) -> None:
        """create_schema() returns raw dict from API."""
        schema_def = {
            "properties": {"amount": {"type": "number"}},
            "required": ["amount"],
        }

        def handler(request: httpx.Request) -> httpx.Response:
            """Return created schema."""
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": {
                        "entityType": "event",
                        "name": "Purchase",
                        "schemaJson": schema_def,
                    },
                },
            )

        ws = _make_workspace(temp_dir, handler)
        result = ws.create_schema("event", "Purchase", schema_def)

        assert isinstance(result, dict)
        assert result["entityType"] == "event"
        assert result["name"] == "Purchase"

    def test_create_schema_sends_correct_path(self, temp_dir: Path) -> None:
        """create_schema() constructs the correct API path."""
        captured: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture request and return schema."""
            captured.append(request)
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": {"entityType": "event", "name": "Purchase"},
                },
            )

        ws = _make_workspace(temp_dir, handler)
        ws.create_schema("event", "Purchase", {"properties": {"x": {"type": "string"}}})

        assert len(captured) == 1
        assert "schemas/event/Purchase" in str(captured[0].url)
        assert captured[0].method == "POST"

    def test_create_schema_url_encodes_names(self, temp_dir: Path) -> None:
        """create_schema() percent-encodes entity names with special chars."""
        captured: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture request and return schema."""
            captured.append(request)
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": {
                        "entityType": "event",
                        "name": "My Event / Test",
                    },
                },
            )

        ws = _make_workspace(temp_dir, handler)
        ws.create_schema("event", "My Event / Test", {"properties": {}})

        assert len(captured) == 1
        # Slashes and spaces should be percent-encoded
        url_str = str(captured[0].url)
        assert "My Event / Test" not in url_str


# =============================================================================
# Tests: create_schemas_bulk
# =============================================================================


class TestCreateSchemasBulk:
    """Tests for Workspace.create_schemas_bulk()."""

    def test_bulk_create_returns_response(self, temp_dir: Path) -> None:
        """create_schemas_bulk() returns BulkCreateSchemasResponse."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return bulk create response."""
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": {"added": 3, "deleted": 0},
                },
            )

        ws = _make_workspace(temp_dir, handler)
        params = BulkCreateSchemasParams(
            entries=[
                SchemaEntry(
                    entity_type="event",
                    name="Purchase",
                    schema_definition={"properties": {"amount": {"type": "number"}}},
                ),
                SchemaEntry(
                    entity_type="event",
                    name="Login",
                    schema_definition={"properties": {}},
                ),
                SchemaEntry(
                    entity_type="event",
                    name="Signup",
                    schema_definition={"properties": {}},
                ),
            ],
        )
        result = ws.create_schemas_bulk(params)

        assert isinstance(result, BulkCreateSchemasResponse)
        assert result.added == 3
        assert result.deleted == 0

    def test_bulk_create_with_truncate(self, temp_dir: Path) -> None:
        """create_schemas_bulk() with truncate=True reports deleted count."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return bulk create response with deletes."""
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": {"added": 2, "deleted": 5},
                },
            )

        ws = _make_workspace(temp_dir, handler)
        params = BulkCreateSchemasParams(
            entries=[
                SchemaEntry(
                    entity_type="event",
                    name="Purchase",
                    schema_definition={"properties": {}},
                ),
                SchemaEntry(
                    entity_type="event",
                    name="Login",
                    schema_definition={"properties": {}},
                ),
            ],
            truncate=True,
            entity_type="event",
        )
        result = ws.create_schemas_bulk(params)

        assert isinstance(result, BulkCreateSchemasResponse)
        assert result.added == 2
        assert result.deleted == 5

    def test_bulk_create_empty_entries(self, temp_dir: Path) -> None:
        """create_schemas_bulk() with empty entries returns zero counts."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return bulk create response with zero counts."""
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": {"added": 0, "deleted": 0},
                },
            )

        ws = _make_workspace(temp_dir, handler)
        params = BulkCreateSchemasParams(entries=[])
        result = ws.create_schemas_bulk(params)

        assert isinstance(result, BulkCreateSchemasResponse)
        assert result.added == 0
        assert result.deleted == 0

    def test_bulk_create_sends_post(self, temp_dir: Path) -> None:
        """create_schemas_bulk() sends POST to schemas/ endpoint."""
        captured: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture request and return response."""
            captured.append(request)
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": {"added": 1, "deleted": 0},
                },
            )

        ws = _make_workspace(temp_dir, handler)
        params = BulkCreateSchemasParams(
            entries=[
                SchemaEntry(
                    entity_type="event",
                    name="Test",
                    schema_definition={"properties": {}},
                ),
            ],
        )
        ws.create_schemas_bulk(params)

        assert len(captured) == 1
        assert captured[0].method == "POST"
        assert "schemas" in str(captured[0].url)


# =============================================================================
# Tests: update_schema
# =============================================================================


class TestUpdateSchema:
    """Tests for Workspace.update_schema()."""

    def test_update_schema_returns_dict(self, temp_dir: Path) -> None:
        """update_schema() returns raw dict from API."""
        patch = {"properties": {"tax": {"type": "number"}}}

        def handler(request: httpx.Request) -> httpx.Response:
            """Return updated schema."""
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": {
                        "entityType": "event",
                        "name": "Purchase",
                        "schemaJson": {
                            "properties": {
                                "amount": {"type": "number"},
                                "tax": {"type": "number"},
                            },
                        },
                    },
                },
            )

        ws = _make_workspace(temp_dir, handler)
        result = ws.update_schema("event", "Purchase", patch)

        assert isinstance(result, dict)
        assert result["entityType"] == "event"
        assert result["name"] == "Purchase"
        assert "tax" in result["schemaJson"]["properties"]

    def test_update_schema_sends_patch(self, temp_dir: Path) -> None:
        """update_schema() sends PATCH to the correct path."""
        captured: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture request and return schema."""
            captured.append(request)
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": {"entityType": "event", "name": "Purchase"},
                },
            )

        ws = _make_workspace(temp_dir, handler)
        ws.update_schema("event", "Purchase", {"properties": {}})

        assert len(captured) == 1
        assert captured[0].method == "PATCH"
        assert "schemas/event/Purchase" in str(captured[0].url)

    def test_update_schema_url_encodes_profile(self, temp_dir: Path) -> None:
        """update_schema() correctly encodes $user for profile schemas."""
        captured: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture request and return schema."""
            captured.append(request)
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": {"entityType": "profile", "name": "$user"},
                },
            )

        ws = _make_workspace(temp_dir, handler)
        ws.update_schema("profile", "$user", {"properties": {}})

        assert len(captured) == 1
        # $user should be percent-encoded
        url_str = str(captured[0].url)
        assert "$user" not in url_str or "%24user" in url_str


# =============================================================================
# Tests: update_schemas_bulk
# =============================================================================


class TestUpdateSchemasBulk:
    """Tests for Workspace.update_schemas_bulk()."""

    def test_bulk_update_returns_results(self, temp_dir: Path) -> None:
        """update_schemas_bulk() returns list of BulkPatchResult."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return bulk update results."""
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": [
                        {
                            "entityType": "event",
                            "name": "Purchase",
                            "status": "ok",
                        },
                        {
                            "entityType": "event",
                            "name": "Login",
                            "status": "ok",
                        },
                    ],
                },
            )

        ws = _make_workspace(temp_dir, handler)
        params = BulkCreateSchemasParams(
            entries=[
                SchemaEntry(
                    entity_type="event",
                    name="Purchase",
                    schema_definition={"properties": {"amount": {"type": "number"}}},
                ),
                SchemaEntry(
                    entity_type="event",
                    name="Login",
                    schema_definition={"properties": {}},
                ),
            ],
        )
        results = ws.update_schemas_bulk(params)

        assert len(results) == 2
        assert isinstance(results[0], BulkPatchResult)
        assert results[0].entity_type == "event"
        assert results[0].name == "Purchase"
        assert results[0].status == "ok"
        assert results[1].name == "Login"
        assert results[1].status == "ok"

    def test_bulk_update_with_errors(self, temp_dir: Path) -> None:
        """update_schemas_bulk() returns error status for failed entries."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return bulk update results with one error."""
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": [
                        {
                            "entityType": "event",
                            "name": "Purchase",
                            "status": "ok",
                        },
                        {
                            "entityType": "event",
                            "name": "NonExistent",
                            "status": "error",
                            "error": "Entity not found",
                        },
                    ],
                },
            )

        ws = _make_workspace(temp_dir, handler)
        params = BulkCreateSchemasParams(
            entries=[
                SchemaEntry(
                    entity_type="event",
                    name="Purchase",
                    schema_definition={"properties": {}},
                ),
                SchemaEntry(
                    entity_type="event",
                    name="NonExistent",
                    schema_definition={"properties": {}},
                ),
            ],
        )
        results = ws.update_schemas_bulk(params)

        assert len(results) == 2
        assert results[0].status == "ok"
        assert results[0].error is None
        assert results[1].status == "error"
        assert results[1].error == "Entity not found"

    def test_bulk_update_empty_entries(self, temp_dir: Path) -> None:
        """update_schemas_bulk() with empty entries returns empty list."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return empty bulk update results."""
            return httpx.Response(
                200,
                json={"status": "ok", "results": []},
            )

        ws = _make_workspace(temp_dir, handler)
        params = BulkCreateSchemasParams(entries=[])
        results = ws.update_schemas_bulk(params)

        assert results == []

    def test_bulk_update_sends_patch(self, temp_dir: Path) -> None:
        """update_schemas_bulk() sends PATCH to schemas/ endpoint."""
        captured: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture request and return results."""
            captured.append(request)
            return httpx.Response(
                200,
                json={"status": "ok", "results": []},
            )

        ws = _make_workspace(temp_dir, handler)
        params = BulkCreateSchemasParams(entries=[])
        ws.update_schemas_bulk(params)

        assert len(captured) == 1
        assert captured[0].method == "PATCH"
        assert "schemas" in str(captured[0].url)


# =============================================================================
# Tests: delete_schemas
# =============================================================================


class TestDeleteSchemas:
    """Tests for Workspace.delete_schemas()."""

    def test_delete_all_schemas(self, temp_dir: Path) -> None:
        """delete_schemas() with no args deletes all and returns count."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return delete response."""
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": {"deleteCount": 10},
                },
            )

        ws = _make_workspace(temp_dir, handler)
        result = ws.delete_schemas()

        assert isinstance(result, DeleteSchemasResponse)
        assert result.delete_count == 10

    def test_delete_by_entity_type(self, temp_dir: Path) -> None:
        """delete_schemas(entity_type='event') deletes all event schemas."""
        captured: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture request and return delete response."""
            captured.append(request)
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": {"deleteCount": 5},
                },
            )

        ws = _make_workspace(temp_dir, handler)
        result = ws.delete_schemas(entity_type="event")

        assert isinstance(result, DeleteSchemasResponse)
        assert result.delete_count == 5
        assert len(captured) == 1
        assert "schemas/event" in str(captured[0].url)
        assert captured[0].method == "DELETE"

    def test_delete_single_schema(self, temp_dir: Path) -> None:
        """delete_schemas(entity_type, entity_name) deletes one schema."""
        captured: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture request and return delete response."""
            captured.append(request)
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": {"deleteCount": 1},
                },
            )

        ws = _make_workspace(temp_dir, handler)
        result = ws.delete_schemas(entity_type="event", entity_name="Purchase")

        assert isinstance(result, DeleteSchemasResponse)
        assert result.delete_count == 1
        assert len(captured) == 1
        assert "schemas/event/Purchase" in str(captured[0].url)

    def test_delete_zero_schemas(self, temp_dir: Path) -> None:
        """delete_schemas() returns zero count when nothing matches."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return delete response with zero count."""
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": {"deleteCount": 0},
                },
            )

        ws = _make_workspace(temp_dir, handler)
        result = ws.delete_schemas(entity_type="custom_event")

        assert isinstance(result, DeleteSchemasResponse)
        assert result.delete_count == 0

    def test_delete_sends_delete_method(self, temp_dir: Path) -> None:
        """delete_schemas() sends DELETE HTTP method."""
        captured: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture request and return response."""
            captured.append(request)
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": {"deleteCount": 0},
                },
            )

        ws = _make_workspace(temp_dir, handler)
        ws.delete_schemas()

        assert len(captured) == 1
        assert captured[0].method == "DELETE"

    def test_entity_name_without_type_raises(self, temp_dir: Path) -> None:
        """delete_schemas(entity_name=X) without entity_type raises MixpanelHeadlessError.

        Providing entity_name without entity_type would silently delete all
        schemas instead of the intended single schema.

        Args:
            temp_dir: Pytest tmp_path fixture.
        """
        from mixpanel_headless.exceptions import MixpanelHeadlessError

        def handler(request: httpx.Request) -> httpx.Response:
            """Should never be called."""
            return httpx.Response(
                200,
                json={"status": "ok", "results": {"deleteCount": 0}},
            )

        ws = _make_workspace(temp_dir, handler)
        with pytest.raises(
            MixpanelHeadlessError, match="entity_name requires entity_type"
        ):
            ws.delete_schemas(entity_name="Purchase")
