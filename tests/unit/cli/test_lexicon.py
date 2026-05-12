# ruff: noqa: ARG001, ARG005
"""Tests for lexicon CLI commands.

Tests cover all lexicon subcommands:
- events: get, update, delete, bulk-update
- properties: get, update, bulk-update
- tags: list, create, update, delete
- Top-level: tracking-metadata, event-history, property-history, export
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import typer.testing

from mixpanel_headless.cli.main import app

runner = typer.testing.CliRunner()


# =============================================================================
# Event Definitions
# =============================================================================


class TestLexiconEventsGet:
    """Tests for mp lexicon events get."""

    @patch("mixpanel_headless.cli.commands.lexicon.get_workspace")
    def test_returns_json_output(self, mock_get_ws: MagicMock) -> None:
        """Successful get returns JSON list of event definitions."""
        mock_ws = MagicMock()
        mock_ws.get_event_definitions.return_value = [
            MagicMock(model_dump=lambda: {"id": 1, "name": "Purchase"}),
            MagicMock(model_dump=lambda: {"id": 2, "name": "Signup"}),
        ]
        mock_get_ws.return_value = mock_ws

        result = runner.invoke(
            app, ["lexicon", "events", "get", "--names", "Purchase,Signup"]
        )
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert isinstance(data, list)
        assert len(data) == 2
        assert data[0]["name"] == "Purchase"
        assert data[1]["name"] == "Signup"

    @patch("mixpanel_headless.cli.commands.lexicon.get_workspace")
    def test_passes_names_to_workspace(self, mock_get_ws: MagicMock) -> None:
        """Names are split and passed as a list to the workspace method."""
        mock_ws = MagicMock()
        mock_ws.get_event_definitions.return_value = []
        mock_get_ws.return_value = mock_ws

        runner.invoke(app, ["lexicon", "events", "get", "--names", "A, B, C"])
        mock_ws.get_event_definitions.assert_called_once_with(names=["A", "B", "C"])


class TestLexiconEventsUpdate:
    """Tests for mp lexicon events update."""

    @patch("mixpanel_headless.cli.commands.lexicon.get_workspace")
    def test_update_returns_json(self, mock_get_ws: MagicMock) -> None:
        """Successful update returns the updated event definition as JSON."""
        mock_ws = MagicMock()
        mock_ws.update_event_definition.return_value = MagicMock(
            model_dump=lambda: {"name": "Purchase", "hidden": True}
        )
        mock_get_ws.return_value = mock_ws

        result = runner.invoke(
            app,
            ["lexicon", "events", "update", "--name", "Purchase", "--hidden"],
        )
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["hidden"] is True

    @patch("mixpanel_headless.cli.commands.lexicon.get_workspace")
    def test_update_with_description(self, mock_get_ws: MagicMock) -> None:
        """Update with --description passes it to the workspace."""
        mock_ws = MagicMock()
        mock_ws.update_event_definition.return_value = MagicMock(
            model_dump=lambda: {"name": "Signup", "description": "User signed up"}
        )
        mock_get_ws.return_value = mock_ws

        result = runner.invoke(
            app,
            [
                "lexicon",
                "events",
                "update",
                "--name",
                "Signup",
                "--description",
                "User signed up",
            ],
        )
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["description"] == "User signed up"


class TestLexiconEventsDelete:
    """Tests for mp lexicon events delete."""

    @patch("mixpanel_headless.cli.commands.lexicon.get_workspace")
    def test_delete_succeeds(self, mock_get_ws: MagicMock) -> None:
        """Successful delete exits with code 0."""
        mock_ws = MagicMock()
        mock_ws.delete_event_definition.return_value = None
        mock_get_ws.return_value = mock_ws

        result = runner.invoke(
            app, ["lexicon", "events", "delete", "--name", "OldEvent"]
        )
        assert result.exit_code == 0
        mock_ws.delete_event_definition.assert_called_once_with("OldEvent")


class TestLexiconEventsBulkUpdate:
    """Tests for mp lexicon events bulk-update."""

    @patch("mixpanel_headless.cli.commands.lexicon.get_workspace")
    def test_bulk_update_returns_json(self, mock_get_ws: MagicMock) -> None:
        """Successful bulk update returns JSON list."""
        mock_ws = MagicMock()
        mock_ws.bulk_update_event_definitions.return_value = [
            MagicMock(model_dump=lambda: {"name": "A", "hidden": True}),
        ]
        mock_get_ws.return_value = mock_ws

        payload = json.dumps({"events": [{"name": "A", "hidden": True}]})
        result = runner.invoke(
            app,
            ["lexicon", "events", "bulk-update", "--data", payload],
        )
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert isinstance(data, list)

    @patch("mixpanel_headless.cli.commands.lexicon.get_workspace")
    def test_bulk_update_invalid_json_exits_3(self, mock_get_ws: MagicMock) -> None:
        """Invalid JSON for --data exits with code 3 (INVALID_ARGS)."""
        mock_ws = MagicMock()
        mock_get_ws.return_value = mock_ws

        result = runner.invoke(
            app,
            ["lexicon", "events", "bulk-update", "--data", "not-json"],
        )
        assert result.exit_code == 3


# =============================================================================
# Property Definitions
# =============================================================================


class TestLexiconPropertiesGet:
    """Tests for mp lexicon properties get."""

    @patch("mixpanel_headless.cli.commands.lexicon.get_workspace")
    def test_returns_json_output(self, mock_get_ws: MagicMock) -> None:
        """Successful get returns JSON list of property definitions."""
        mock_ws = MagicMock()
        mock_ws.get_property_definitions.return_value = [
            MagicMock(model_dump=lambda: {"name": "plan_type", "type": "string"}),
        ]
        mock_get_ws.return_value = mock_ws

        result = runner.invoke(
            app, ["lexicon", "properties", "get", "--names", "plan_type"]
        )
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert isinstance(data, list)
        assert data[0]["name"] == "plan_type"

    @patch("mixpanel_headless.cli.commands.lexicon.get_workspace")
    def test_with_resource_type(self, mock_get_ws: MagicMock) -> None:
        """Passing --resource-type includes it in the workspace call."""
        mock_ws = MagicMock()
        mock_ws.get_property_definitions.return_value = []
        mock_get_ws.return_value = mock_ws

        runner.invoke(
            app,
            [
                "lexicon",
                "properties",
                "get",
                "--names",
                "email",
                "--resource-type",
                "user",
            ],
        )
        mock_ws.get_property_definitions.assert_called_once_with(
            names=["email"], resource_type="user"
        )


class TestLexiconPropertiesUpdate:
    """Tests for mp lexicon properties update."""

    @patch("mixpanel_headless.cli.commands.lexicon.get_workspace")
    def test_update_returns_json(self, mock_get_ws: MagicMock) -> None:
        """Successful property update returns JSON."""
        mock_ws = MagicMock()
        mock_ws.update_property_definition.return_value = MagicMock(
            model_dump=lambda: {"name": "email", "sensitive": True}
        )
        mock_get_ws.return_value = mock_ws

        result = runner.invoke(
            app,
            ["lexicon", "properties", "update", "--name", "email", "--sensitive"],
        )
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["sensitive"] is True

    @patch("mixpanel_headless.cli.commands.lexicon.get_workspace")
    def test_update_with_description(self, mock_get_ws: MagicMock) -> None:
        """Update with --description passes it through."""
        mock_ws = MagicMock()
        mock_ws.update_property_definition.return_value = MagicMock(
            model_dump=lambda: {"name": "email", "description": "User email"}
        )
        mock_get_ws.return_value = mock_ws

        result = runner.invoke(
            app,
            [
                "lexicon",
                "properties",
                "update",
                "--name",
                "email",
                "--description",
                "User email",
            ],
        )
        assert result.exit_code == 0


class TestLexiconPropertiesBulkUpdate:
    """Tests for mp lexicon properties bulk-update."""

    @patch("mixpanel_headless.cli.commands.lexicon.get_workspace")
    def test_bulk_update_returns_json(self, mock_get_ws: MagicMock) -> None:
        """Successful bulk update returns JSON list."""
        mock_ws = MagicMock()
        mock_ws.bulk_update_property_definitions.return_value = [
            MagicMock(model_dump=lambda: {"name": "email", "hidden": False}),
        ]
        mock_get_ws.return_value = mock_ws

        payload = json.dumps(
            {
                "properties": [
                    {"name": "email", "resource_type": "event", "hidden": False}
                ]
            }
        )
        result = runner.invoke(
            app,
            ["lexicon", "properties", "bulk-update", "--data", payload],
        )
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert isinstance(data, list)

    @patch("mixpanel_headless.cli.commands.lexicon.get_workspace")
    def test_bulk_update_invalid_json_exits_3(self, mock_get_ws: MagicMock) -> None:
        """Invalid JSON for --data exits with code 3."""
        mock_ws = MagicMock()
        mock_get_ws.return_value = mock_ws

        result = runner.invoke(
            app,
            ["lexicon", "properties", "bulk-update", "--data", "{bad json"],
        )
        assert result.exit_code == 3


# =============================================================================
# Tags
# =============================================================================


class TestLexiconTagsList:
    """Tests for mp lexicon tags list."""

    @patch("mixpanel_headless.cli.commands.lexicon.get_workspace")
    def test_returns_json_list(self, mock_get_ws: MagicMock) -> None:
        """Successful list returns JSON list of tags."""
        mock_ws = MagicMock()
        mock_ws.list_lexicon_tags.return_value = [
            MagicMock(model_dump=lambda: {"id": 1, "name": "core"}),
            MagicMock(model_dump=lambda: {"id": 2, "name": "deprecated"}),
        ]
        mock_get_ws.return_value = mock_ws

        result = runner.invoke(app, ["lexicon", "tags", "list"])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert isinstance(data, list)
        assert len(data) == 2


class TestLexiconTagsCreate:
    """Tests for mp lexicon tags create."""

    @patch("mixpanel_headless.cli.commands.lexicon.get_workspace")
    def test_create_returns_json(self, mock_get_ws: MagicMock) -> None:
        """Successful create returns the created tag as JSON."""
        mock_ws = MagicMock()
        mock_ws.create_lexicon_tag.return_value = MagicMock(
            model_dump=lambda: {"id": 3, "name": "new-tag"}
        )
        mock_get_ws.return_value = mock_ws

        result = runner.invoke(app, ["lexicon", "tags", "create", "--name", "new-tag"])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["name"] == "new-tag"


class TestLexiconTagsUpdate:
    """Tests for mp lexicon tags update."""

    @patch("mixpanel_headless.cli.commands.lexicon.get_workspace")
    def test_update_returns_json(self, mock_get_ws: MagicMock) -> None:
        """Successful update returns the updated tag as JSON."""
        mock_ws = MagicMock()
        mock_ws.update_lexicon_tag.return_value = MagicMock(
            model_dump=lambda: {"id": 1, "name": "renamed-tag"}
        )
        mock_get_ws.return_value = mock_ws

        result = runner.invoke(
            app, ["lexicon", "tags", "update", "--id", "1", "--name", "renamed-tag"]
        )
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["name"] == "renamed-tag"


class TestLexiconTagsDelete:
    """Tests for mp lexicon tags delete."""

    @patch("mixpanel_headless.cli.commands.lexicon.get_workspace")
    def test_delete_succeeds(self, mock_get_ws: MagicMock) -> None:
        """Successful delete exits with code 0."""
        mock_ws = MagicMock()
        mock_ws.delete_lexicon_tag.return_value = None
        mock_get_ws.return_value = mock_ws

        result = runner.invoke(app, ["lexicon", "tags", "delete", "--name", "old-tag"])
        assert result.exit_code == 0
        mock_ws.delete_lexicon_tag.assert_called_once_with("old-tag")


# =============================================================================
# Top-level Commands
# =============================================================================


class TestLexiconTrackingMetadata:
    """Tests for mp lexicon tracking-metadata."""

    @patch("mixpanel_headless.cli.commands.lexicon.get_workspace")
    def test_returns_json(self, mock_get_ws: MagicMock) -> None:
        """Successful tracking-metadata returns JSON dict."""
        mock_ws = MagicMock()
        mock_ws.get_tracking_metadata.return_value = {
            "event_name": "Purchase",
            "sources": ["iOS", "Android"],
        }
        mock_get_ws.return_value = mock_ws

        result = runner.invoke(
            app, ["lexicon", "tracking-metadata", "--event-name", "Purchase"]
        )
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["event_name"] == "Purchase"


class TestLexiconEventHistory:
    """Tests for mp lexicon event-history."""

    @patch("mixpanel_headless.cli.commands.lexicon.get_workspace")
    def test_returns_json(self, mock_get_ws: MagicMock) -> None:
        """Successful event-history returns JSON."""
        mock_ws = MagicMock()
        mock_ws.get_event_history.return_value = [
            {"action": "created", "timestamp": "2024-01-01T00:00:00Z"},
        ]
        mock_get_ws.return_value = mock_ws

        result = runner.invoke(
            app, ["lexicon", "event-history", "--event-name", "Signup"]
        )
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert isinstance(data, list)


class TestLexiconPropertyHistory:
    """Tests for mp lexicon property-history."""

    @patch("mixpanel_headless.cli.commands.lexicon.get_workspace")
    def test_returns_json(self, mock_get_ws: MagicMock) -> None:
        """Successful property-history returns JSON."""
        mock_ws = MagicMock()
        mock_ws.get_property_history.return_value = [
            {"action": "updated", "timestamp": "2024-02-01T00:00:00Z"},
        ]
        mock_get_ws.return_value = mock_ws

        result = runner.invoke(
            app,
            [
                "lexicon",
                "property-history",
                "--property-name",
                "email",
                "--entity-type",
                "user",
            ],
        )
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert isinstance(data, list)

    @patch("mixpanel_headless.cli.commands.lexicon.get_workspace")
    def test_passes_entity_type(self, mock_get_ws: MagicMock) -> None:
        """Entity type is passed to the workspace method."""
        mock_ws = MagicMock()
        mock_ws.get_property_history.return_value = []
        mock_get_ws.return_value = mock_ws

        runner.invoke(
            app,
            [
                "lexicon",
                "property-history",
                "--property-name",
                "plan",
                "--entity-type",
                "event",
            ],
        )
        mock_ws.get_property_history.assert_called_once_with("plan", "event")


class TestLexiconExport:
    """Tests for mp lexicon export."""

    @patch("mixpanel_headless.cli.commands.lexicon.get_workspace")
    def test_export_returns_json(self, mock_get_ws: MagicMock) -> None:
        """Successful export returns JSON."""
        mock_ws = MagicMock()
        mock_ws.export_lexicon.return_value = {
            "events": [{"name": "Purchase"}],
            "event_properties": [],
        }
        mock_get_ws.return_value = mock_ws

        result = runner.invoke(app, ["lexicon", "export"])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert "events" in data

    @patch("mixpanel_headless.cli.commands.lexicon.get_workspace")
    def test_export_with_types_filter(self, mock_get_ws: MagicMock) -> None:
        """Export with --types passes export_types to workspace."""
        mock_ws = MagicMock()
        mock_ws.export_lexicon.return_value = {}
        mock_get_ws.return_value = mock_ws

        runner.invoke(app, ["lexicon", "export", "--types", "events,user_properties"])
        mock_ws.export_lexicon.assert_called_once_with(
            export_types=["events", "user_properties"]
        )
