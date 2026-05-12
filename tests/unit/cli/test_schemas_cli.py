# ruff: noqa: ARG001, ARG005
"""Tests for schemas CLI commands.

Tests cover all schema registry subcommands:
- list: List schema entries (all or by entity type)
- create: Create a single schema
- create-bulk: Bulk create schemas
- update: Update a single schema (merge semantics)
- update-bulk: Bulk update schemas
- delete: Delete schemas
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import typer.testing

from mixpanel_headless.cli.main import app

runner = typer.testing.CliRunner()


# =============================================================================
# List
# =============================================================================


class TestSchemasList:
    """Tests for mp schemas list."""

    @patch("mixpanel_headless.cli.commands.schemas.get_workspace")
    def test_returns_json_list(self, mock_get_ws: MagicMock) -> None:
        """Successful list returns JSON list of schema entries."""
        mock_ws = MagicMock()
        mock_ws.list_schema_registry.return_value = [
            MagicMock(
                model_dump=lambda **kw: {
                    "entityType": "event",
                    "name": "Purchase",
                    "schemaJson": {"properties": {}},
                }
            ),
            MagicMock(
                model_dump=lambda **kw: {
                    "entityType": "event",
                    "name": "Signup",
                    "schemaJson": {"properties": {}},
                }
            ),
        ]
        mock_get_ws.return_value = mock_ws

        result = runner.invoke(app, ["schemas", "list"])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert isinstance(data, list)
        assert len(data) == 2
        assert data[0]["name"] == "Purchase"
        assert data[1]["name"] == "Signup"

    @patch("mixpanel_headless.cli.commands.schemas.get_workspace")
    def test_with_entity_type_filter(self, mock_get_ws: MagicMock) -> None:
        """Passing --entity-type filters by entity type."""
        mock_ws = MagicMock()
        mock_ws.list_schema_registry.return_value = [
            MagicMock(
                model_dump=lambda **kw: {
                    "entityType": "event",
                    "name": "Purchase",
                }
            ),
        ]
        mock_get_ws.return_value = mock_ws

        result = runner.invoke(app, ["schemas", "list", "--entity-type", "event"])
        assert result.exit_code == 0
        mock_ws.list_schema_registry.assert_called_once_with(entity_type="event")


# =============================================================================
# Create
# =============================================================================


class TestSchemasCreate:
    """Tests for mp schemas create."""

    @patch("mixpanel_headless.cli.commands.schemas.get_workspace")
    def test_create_returns_json(self, mock_get_ws: MagicMock) -> None:
        """Successful create returns the created schema as JSON."""
        mock_ws = MagicMock()
        mock_ws.create_schema.return_value = {
            "entityType": "event",
            "name": "Purchase",
            "schemaJson": {"properties": {"amount": {"type": "number"}}},
        }
        mock_get_ws.return_value = mock_ws

        schema = json.dumps({"properties": {"amount": {"type": "number"}}})
        result = runner.invoke(
            app,
            [
                "schemas",
                "create",
                "--entity-type",
                "event",
                "--entity-name",
                "Purchase",
                "--schema-json",
                schema,
            ],
        )
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["name"] == "Purchase"
        assert data["entityType"] == "event"

    @patch("mixpanel_headless.cli.commands.schemas.get_workspace")
    def test_create_passes_args_to_workspace(self, mock_get_ws: MagicMock) -> None:
        """Arguments are passed correctly to the workspace method."""
        mock_ws = MagicMock()
        mock_ws.create_schema.return_value = {}
        mock_get_ws.return_value = mock_ws

        schema_dict = {"properties": {"plan": {"type": "string"}}}
        result = runner.invoke(
            app,
            [
                "schemas",
                "create",
                "--entity-type",
                "user",
                "--entity-name",
                "Profile",
                "--schema-json",
                json.dumps(schema_dict),
            ],
        )
        assert result.exit_code == 0
        mock_ws.create_schema.assert_called_once_with("user", "Profile", schema_dict)

    @patch("mixpanel_headless.cli.commands.schemas.get_workspace")
    def test_create_invalid_json_exits_3(self, mock_get_ws: MagicMock) -> None:
        """Invalid JSON for --schema-json exits with code 3 (INVALID_ARGS)."""
        mock_ws = MagicMock()
        mock_get_ws.return_value = mock_ws

        result = runner.invoke(
            app,
            [
                "schemas",
                "create",
                "--entity-type",
                "event",
                "--entity-name",
                "Test",
                "--schema-json",
                "not-json",
            ],
        )
        assert result.exit_code == 3


# =============================================================================
# Create Bulk
# =============================================================================


class TestSchemasCreateBulk:
    """Tests for mp schemas create-bulk."""

    @patch("mixpanel_headless.cli.commands.schemas.get_workspace")
    def test_create_bulk_returns_json(self, mock_get_ws: MagicMock) -> None:
        """Successful bulk create returns JSON with added/deleted counts."""
        mock_ws = MagicMock()
        mock_ws.create_schemas_bulk.return_value = MagicMock(
            model_dump=lambda **kw: {"added": 2, "deleted": 0}
        )
        mock_get_ws.return_value = mock_ws

        entries = json.dumps(
            [
                {
                    "entityType": "event",
                    "name": "Purchase",
                    "schemaJson": {"properties": {}},
                },
                {
                    "entityType": "event",
                    "name": "Signup",
                    "schemaJson": {"properties": {}},
                },
            ]
        )
        result = runner.invoke(app, ["schemas", "create-bulk", "--entries", entries])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["added"] == 2
        assert data["deleted"] == 0

    @patch("mixpanel_headless.cli.commands.schemas.get_workspace")
    def test_create_bulk_invalid_json_exits_3(self, mock_get_ws: MagicMock) -> None:
        """Invalid JSON for --entries exits with code 3 (INVALID_ARGS)."""
        mock_ws = MagicMock()
        mock_get_ws.return_value = mock_ws

        result = runner.invoke(app, ["schemas", "create-bulk", "--entries", "{bad"])
        assert result.exit_code == 3


# =============================================================================
# Update
# =============================================================================


class TestSchemasUpdate:
    """Tests for mp schemas update."""

    @patch("mixpanel_headless.cli.commands.schemas.get_workspace")
    def test_update_returns_json(self, mock_get_ws: MagicMock) -> None:
        """Successful update returns the updated schema as JSON."""
        mock_ws = MagicMock()
        mock_ws.update_schema.return_value = {
            "entityType": "event",
            "name": "Purchase",
            "schemaJson": {"properties": {"amount": {"type": "number"}}},
        }
        mock_get_ws.return_value = mock_ws

        schema = json.dumps({"properties": {"amount": {"type": "number"}}})
        result = runner.invoke(
            app,
            [
                "schemas",
                "update",
                "--entity-type",
                "event",
                "--entity-name",
                "Purchase",
                "--schema-json",
                schema,
            ],
        )
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["name"] == "Purchase"

    @patch("mixpanel_headless.cli.commands.schemas.get_workspace")
    def test_update_passes_args_to_workspace(self, mock_get_ws: MagicMock) -> None:
        """Arguments are passed correctly to the workspace method."""
        mock_ws = MagicMock()
        mock_ws.update_schema.return_value = {}
        mock_get_ws.return_value = mock_ws

        schema_dict = {"description": "Updated"}
        result = runner.invoke(
            app,
            [
                "schemas",
                "update",
                "--entity-type",
                "event",
                "--entity-name",
                "Purchase",
                "--schema-json",
                json.dumps(schema_dict),
            ],
        )
        assert result.exit_code == 0
        mock_ws.update_schema.assert_called_once_with("event", "Purchase", schema_dict)

    @patch("mixpanel_headless.cli.commands.schemas.get_workspace")
    def test_update_invalid_json_exits_3(self, mock_get_ws: MagicMock) -> None:
        """Invalid JSON for --schema-json exits with code 3 (INVALID_ARGS)."""
        mock_ws = MagicMock()
        mock_get_ws.return_value = mock_ws

        result = runner.invoke(
            app,
            [
                "schemas",
                "update",
                "--entity-type",
                "event",
                "--entity-name",
                "Test",
                "--schema-json",
                "not-json",
            ],
        )
        assert result.exit_code == 3


# =============================================================================
# Update Bulk
# =============================================================================


class TestSchemasUpdateBulk:
    """Tests for mp schemas update-bulk."""

    @patch("mixpanel_headless.cli.commands.schemas.get_workspace")
    def test_update_bulk_returns_json(self, mock_get_ws: MagicMock) -> None:
        """Successful bulk update returns JSON list of updated entries."""
        mock_ws = MagicMock()
        mock_ws.update_schemas_bulk.return_value = [
            MagicMock(
                model_dump=lambda **kw: {
                    "entityType": "event",
                    "name": "Purchase",
                    "schemaJson": {"properties": {}},
                }
            ),
        ]
        mock_get_ws.return_value = mock_ws

        entries = json.dumps(
            [
                {
                    "entityType": "event",
                    "name": "Purchase",
                    "schemaJson": {"properties": {}},
                },
            ]
        )
        result = runner.invoke(app, ["schemas", "update-bulk", "--entries", entries])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["name"] == "Purchase"

    @patch("mixpanel_headless.cli.commands.schemas.get_workspace")
    def test_update_bulk_invalid_json_exits_3(self, mock_get_ws: MagicMock) -> None:
        """Invalid JSON for --entries exits with code 3 (INVALID_ARGS)."""
        mock_ws = MagicMock()
        mock_get_ws.return_value = mock_ws

        result = runner.invoke(app, ["schemas", "update-bulk", "--entries", "not-json"])
        assert result.exit_code == 3


# =============================================================================
# Delete
# =============================================================================


class TestSchemasDelete:
    """Tests for mp schemas delete."""

    @patch("mixpanel_headless.cli.commands.schemas.get_workspace")
    def test_delete_returns_json(self, mock_get_ws: MagicMock) -> None:
        """Successful delete returns JSON with deleteCount."""
        mock_ws = MagicMock()
        mock_ws.delete_schemas.return_value = MagicMock(
            model_dump=lambda **kw: {"deleteCount": 1}
        )
        mock_get_ws.return_value = mock_ws

        result = runner.invoke(
            app,
            [
                "schemas",
                "delete",
                "--entity-type",
                "event",
                "--entity-name",
                "Purchase",
            ],
        )
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["deleteCount"] == 1

    @patch("mixpanel_headless.cli.commands.schemas.get_workspace")
    def test_delete_passes_filters_to_workspace(self, mock_get_ws: MagicMock) -> None:
        """Entity type and name filters are passed to the workspace method."""
        mock_ws = MagicMock()
        mock_ws.delete_schemas.return_value = MagicMock(
            model_dump=lambda **kw: {"deleteCount": 1}
        )
        mock_get_ws.return_value = mock_ws

        runner.invoke(
            app,
            [
                "schemas",
                "delete",
                "--entity-type",
                "event",
                "--entity-name",
                "Purchase",
            ],
        )
        mock_ws.delete_schemas.assert_called_once_with(
            entity_type="event", entity_name="Purchase"
        )

    @patch("mixpanel_headless.cli.commands.schemas.get_workspace")
    def test_delete_without_filters_confirms(self, mock_get_ws: MagicMock) -> None:
        """Delete without filters prompts for confirmation and proceeds on 'y'."""
        mock_ws = MagicMock()
        mock_ws.delete_schemas.return_value = MagicMock(
            model_dump=lambda **kw: {"deleteCount": 5}
        )
        mock_get_ws.return_value = mock_ws

        result = runner.invoke(app, ["schemas", "delete"], input="y\n")
        assert result.exit_code == 0
        mock_ws.delete_schemas.assert_called_once_with(
            entity_type=None, entity_name=None
        )

    @patch("mixpanel_headless.cli.commands.schemas.get_workspace")
    def test_delete_without_filters_aborts(self, mock_get_ws: MagicMock) -> None:
        """Delete without filters aborts on 'n'."""
        mock_ws = MagicMock()
        mock_get_ws.return_value = mock_ws

        result = runner.invoke(app, ["schemas", "delete"], input="n\n")
        assert result.exit_code != 0
        mock_ws.delete_schemas.assert_not_called()
