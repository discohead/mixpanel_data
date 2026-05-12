# ruff: noqa: ARG001, ARG005
"""Tests for custom-events CLI commands.

Tests cover all custom-events subcommands:
- list: List all custom events
- update: Update a custom event definition
- delete: Delete a custom event
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import typer.testing

from mixpanel_headless.cli.main import app

runner = typer.testing.CliRunner()


class TestCustomEventsList:
    """Tests for mp custom-events list."""

    @patch("mixpanel_headless.cli.commands.custom_events.get_workspace")
    def test_returns_json_list(self, mock_get_ws: MagicMock) -> None:
        """Successful list returns JSON list of custom events."""
        mock_ws = MagicMock()
        mock_ws.list_custom_events.return_value = [
            MagicMock(model_dump=lambda: {"name": "Activated", "hidden": False}),
            MagicMock(model_dump=lambda: {"name": "Churned", "hidden": False}),
        ]
        mock_get_ws.return_value = mock_ws

        result = runner.invoke(app, ["custom-events", "list"])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert isinstance(data, list)
        assert len(data) == 2
        assert data[0]["name"] == "Activated"

    @patch("mixpanel_headless.cli.commands.custom_events.get_workspace")
    def test_empty_list(self, mock_get_ws: MagicMock) -> None:
        """Empty list returns empty JSON array."""
        mock_ws = MagicMock()
        mock_ws.list_custom_events.return_value = []
        mock_get_ws.return_value = mock_ws

        result = runner.invoke(app, ["custom-events", "list"])
        assert result.exit_code == 0
        assert json.loads(result.stdout) == []


class TestCustomEventsUpdate:
    """Tests for mp custom-events update."""

    @patch("mixpanel_headless.cli.commands.custom_events.get_workspace")
    def test_update_by_id_with_hidden_returns_json(
        self, mock_get_ws: MagicMock
    ) -> None:
        """--id update with --hidden returns JSON and skips lookup."""
        mock_ws = MagicMock()
        mock_ws.update_custom_event.return_value = MagicMock(
            model_dump=lambda: {"name": "Activated", "hidden": True}
        )
        mock_get_ws.return_value = mock_ws

        result = runner.invoke(
            app,
            ["custom-events", "update", "--id", "2044168", "--hidden"],
        )
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["hidden"] is True
        # Verify the resolved id was passed through, no lookup attempted
        mock_ws.list_custom_events.assert_not_called()
        called_id, called_params = mock_ws.update_custom_event.call_args[0]
        assert called_id == 2044168
        assert called_params.hidden is True

    @patch("mixpanel_headless.cli.commands.custom_events.get_workspace")
    def test_update_by_id_with_description(self, mock_get_ws: MagicMock) -> None:
        """--description passes through to the params."""
        mock_ws = MagicMock()
        mock_ws.update_custom_event.return_value = MagicMock(
            model_dump=lambda: {"name": "Activated", "description": "User activated"}
        )
        mock_get_ws.return_value = mock_ws

        result = runner.invoke(
            app,
            [
                "custom-events",
                "update",
                "--id",
                "2044168",
                "--description",
                "User activated",
            ],
        )
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["description"] == "User activated"

    @patch("mixpanel_headless.cli.commands.custom_events.get_workspace")
    def test_update_by_id_with_dropped(self, mock_get_ws: MagicMock) -> None:
        """--dropped flag passes dropped=True."""
        mock_ws = MagicMock()
        mock_ws.update_custom_event.return_value = MagicMock(
            model_dump=lambda: {"name": "OldEvent", "dropped": True}
        )
        mock_get_ws.return_value = mock_ws

        result = runner.invoke(
            app,
            ["custom-events", "update", "--id", "123", "--dropped"],
        )
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["dropped"] is True

    @patch("mixpanel_headless.cli.commands.custom_events.get_workspace")
    def test_update_by_name_resolves_to_id(self, mock_get_ws: MagicMock) -> None:
        """--name resolves to the unique custom_event_id and passes it through."""
        from mixpanel_headless.types import EventDefinition

        mock_ws = MagicMock()
        mock_ws.list_custom_events.return_value = [
            # An orphan with same name (customEventId=0) — must be filtered out
            EventDefinition(id=999, name="Activated", custom_event_id=0),
            # The real custom event
            EventDefinition(id=0, name="Activated", custom_event_id=2044168),
        ]
        mock_ws.update_custom_event.return_value = MagicMock(
            model_dump=lambda: {"name": "Activated", "verified": True}
        )
        mock_get_ws.return_value = mock_ws

        result = runner.invoke(
            app,
            ["custom-events", "update", "--name", "Activated", "--verified"],
        )
        assert result.exit_code == 0
        called_id, called_params = mock_ws.update_custom_event.call_args[0]
        assert called_id == 2044168
        assert called_params.verified is True

    @patch("mixpanel_headless.cli.commands.custom_events.get_workspace")
    def test_update_errors_when_name_not_found(self, mock_get_ws: MagicMock) -> None:
        """--name with no matching custom event errors out and names the query."""
        mock_ws = MagicMock()
        mock_ws.list_custom_events.return_value = []
        mock_get_ws.return_value = mock_ws

        result = runner.invoke(
            app,
            ["custom-events", "update", "--name", "Nonexistent", "--hidden"],
        )
        assert result.exit_code != 0
        combined = (result.stdout or "") + (result.stderr or "")
        assert "Nonexistent" in combined

    @patch("mixpanel_headless.cli.commands.custom_events.get_workspace")
    def test_update_errors_when_name_is_ambiguous(self, mock_get_ws: MagicMock) -> None:
        """--name matching multiple real custom events lists the colliding ids."""
        from mixpanel_headless.types import EventDefinition

        mock_ws = MagicMock()
        mock_ws.list_custom_events.return_value = [
            EventDefinition(id=0, name="Duplicate", custom_event_id=111),
            EventDefinition(id=0, name="Duplicate", custom_event_id=222),
        ]
        mock_get_ws.return_value = mock_ws

        result = runner.invoke(
            app,
            ["custom-events", "update", "--name", "Duplicate", "--hidden"],
        )
        assert result.exit_code != 0
        combined = (result.stdout or "") + (result.stderr or "")
        assert "111" in combined
        assert "222" in combined
        assert "--id" in combined

    @patch("mixpanel_headless.cli.commands.custom_events.get_workspace")
    def test_update_errors_when_name_only_matches_orphans(
        self, mock_get_ws: MagicMock
    ) -> None:
        """--name matching only orphan entries errors with an orphan-aware hint."""
        from mixpanel_headless.types import EventDefinition

        mock_ws = MagicMock()
        mock_ws.list_custom_events.return_value = [
            EventDefinition(id=999, name="OrphanOnly", custom_event_id=0),
            EventDefinition(id=998, name="OrphanOnly", custom_event_id=None),
        ]
        mock_get_ws.return_value = mock_ws

        result = runner.invoke(
            app,
            ["custom-events", "update", "--name", "OrphanOnly", "--hidden"],
        )
        assert result.exit_code != 0
        combined = (result.stdout or "") + (result.stderr or "")
        assert "orphan" in combined.lower()
        assert "--id" in combined

    @patch("mixpanel_headless.cli.commands.custom_events.get_workspace")
    def test_update_with_no_verified_passes_false(self, mock_get_ws: MagicMock) -> None:
        """--no-verified passes verified=False (not omitted)."""
        mock_ws = MagicMock()
        mock_ws.update_custom_event.return_value = MagicMock(
            model_dump=lambda: {"name": "Activated", "verified": False}
        )
        mock_get_ws.return_value = mock_ws

        result = runner.invoke(
            app,
            ["custom-events", "update", "--id", "2044168", "--no-verified"],
        )
        assert result.exit_code == 0
        _, called_params = mock_ws.update_custom_event.call_args[0]
        assert called_params.verified is False

    @patch("mixpanel_headless.cli.commands.custom_events.get_workspace")
    def test_update_without_verified_flag_omits_field(
        self, mock_get_ws: MagicMock
    ) -> None:
        """Omitting --verified leaves verified unset (None) in params."""
        mock_ws = MagicMock()
        mock_ws.update_custom_event.return_value = MagicMock(
            model_dump=lambda: {"name": "Activated", "hidden": True}
        )
        mock_get_ws.return_value = mock_ws

        result = runner.invoke(
            app,
            ["custom-events", "update", "--id", "2044168", "--hidden"],
        )
        assert result.exit_code == 0
        _, called_params = mock_ws.update_custom_event.call_args[0]
        assert called_params.verified is None
        # And it must drop out of the API body when serialized
        assert "verified" not in called_params.model_dump(exclude_none=True)

    def test_update_errors_when_neither_id_nor_name(self) -> None:
        """Update without --id and without --name errors out."""
        result = runner.invoke(app, ["custom-events", "update", "--hidden"])
        assert result.exit_code != 0

    def test_update_errors_when_both_id_and_name(self) -> None:
        """Update with both --id and --name errors out."""
        result = runner.invoke(
            app,
            [
                "custom-events",
                "update",
                "--id",
                "123",
                "--name",
                "X",
                "--hidden",
            ],
        )
        assert result.exit_code != 0


class TestCustomEventsDelete:
    """Tests for mp custom-events delete."""

    @patch("mixpanel_headless.cli.commands.custom_events.get_workspace")
    def test_delete_by_id_succeeds(self, mock_get_ws: MagicMock) -> None:
        """--id delete passes the int id straight to workspace.delete_custom_event."""
        mock_ws = MagicMock()
        mock_ws.delete_custom_event.return_value = None
        mock_get_ws.return_value = mock_ws

        result = runner.invoke(app, ["custom-events", "delete", "--id", "2044168"])
        assert result.exit_code == 0
        mock_ws.delete_custom_event.assert_called_once_with(2044168)
        mock_ws.list_custom_events.assert_not_called()

    @patch("mixpanel_headless.cli.commands.custom_events.get_workspace")
    def test_delete_by_name_resolves_to_id(self, mock_get_ws: MagicMock) -> None:
        """--name resolves to the unique custom_event_id and deletes by id."""
        from mixpanel_headless.types import EventDefinition

        mock_ws = MagicMock()
        mock_ws.list_custom_events.return_value = [
            EventDefinition(id=999, name="OldEvent", custom_event_id=0),  # orphan
            EventDefinition(id=0, name="OldEvent", custom_event_id=2044168),
        ]
        mock_ws.delete_custom_event.return_value = None
        mock_get_ws.return_value = mock_ws

        result = runner.invoke(app, ["custom-events", "delete", "--name", "OldEvent"])
        assert result.exit_code == 0
        mock_ws.delete_custom_event.assert_called_once_with(2044168)

    @patch("mixpanel_headless.cli.commands.custom_events.get_workspace")
    def test_delete_errors_when_name_not_found(self, mock_get_ws: MagicMock) -> None:
        """--name with no matching custom event errors out, doesn't delete."""
        mock_ws = MagicMock()
        mock_ws.list_custom_events.return_value = []
        mock_get_ws.return_value = mock_ws

        result = runner.invoke(
            app, ["custom-events", "delete", "--name", "Nonexistent"]
        )
        assert result.exit_code != 0
        mock_ws.delete_custom_event.assert_not_called()
        combined = (result.stdout or "") + (result.stderr or "")
        assert "Nonexistent" in combined

    @patch("mixpanel_headless.cli.commands.custom_events.get_workspace")
    def test_delete_errors_when_name_is_ambiguous(self, mock_get_ws: MagicMock) -> None:
        """--name matching multiple real custom events lists colliding ids and aborts."""
        from mixpanel_headless.types import EventDefinition

        mock_ws = MagicMock()
        mock_ws.list_custom_events.return_value = [
            EventDefinition(id=0, name="Duplicate", custom_event_id=111),
            EventDefinition(id=0, name="Duplicate", custom_event_id=222),
        ]
        mock_get_ws.return_value = mock_ws

        result = runner.invoke(app, ["custom-events", "delete", "--name", "Duplicate"])
        assert result.exit_code != 0
        mock_ws.delete_custom_event.assert_not_called()
        combined = (result.stdout or "") + (result.stderr or "")
        assert "111" in combined
        assert "222" in combined
        assert "--id" in combined

    @patch("mixpanel_headless.cli.commands.custom_events.get_workspace")
    def test_delete_errors_when_name_only_matches_orphans(
        self, mock_get_ws: MagicMock
    ) -> None:
        """--name matching only orphans aborts with an orphan-aware hint."""
        from mixpanel_headless.types import EventDefinition

        mock_ws = MagicMock()
        mock_ws.list_custom_events.return_value = [
            EventDefinition(id=999, name="OrphanOnly", custom_event_id=0),
            EventDefinition(id=998, name="OrphanOnly", custom_event_id=None),
        ]
        mock_get_ws.return_value = mock_ws

        result = runner.invoke(app, ["custom-events", "delete", "--name", "OrphanOnly"])
        assert result.exit_code != 0
        mock_ws.delete_custom_event.assert_not_called()
        combined = (result.stdout or "") + (result.stderr or "")
        assert "orphan" in combined.lower()
        assert "--id" in combined

    def test_delete_errors_when_neither_id_nor_name(self) -> None:
        """Delete without --id and without --name errors out."""
        result = runner.invoke(app, ["custom-events", "delete"])
        assert result.exit_code != 0

    def test_delete_errors_when_both_id_and_name(self) -> None:
        """Delete with both --id and --name errors out."""
        result = runner.invoke(
            app,
            ["custom-events", "delete", "--id", "123", "--name", "X"],
        )
        assert result.exit_code != 0


class TestCustomEventsCreate:
    """Tests for mp custom-events create."""

    @patch("mixpanel_headless.cli.commands.custom_events.get_workspace")
    def test_create_with_single_alternative_returns_json(
        self, mock_get_ws: MagicMock
    ) -> None:
        """Successful create returns JSON with the new custom event."""
        from mixpanel_headless.types import CustomEvent, CustomEventAlternative

        mock_ws = MagicMock()
        mock_ws.create_custom_event.return_value = CustomEvent(
            id=42,
            name="Metric Tree Opened",
            alternatives=[CustomEventAlternative(event="Enter room")],
        )
        mock_get_ws.return_value = mock_ws

        result = runner.invoke(
            app,
            [
                "custom-events",
                "create",
                "--name",
                "Metric Tree Opened",
                "--alternative",
                "Enter room",
            ],
        )

        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["id"] == 42
        assert data["name"] == "Metric Tree Opened"

        called_params = mock_ws.create_custom_event.call_args[0][0]
        assert called_params.name == "Metric Tree Opened"
        assert called_params.alternatives == ["Enter room"]

    @patch("mixpanel_headless.cli.commands.custom_events.get_workspace")
    def test_create_with_multiple_alternatives_preserves_order(
        self, mock_get_ws: MagicMock
    ) -> None:
        """--alternative is repeatable and preserves order."""
        from mixpanel_headless.types import CustomEvent

        mock_ws = MagicMock()
        mock_ws.create_custom_event.return_value = CustomEvent(
            id=1, name="Page View", alternatives=[]
        )
        mock_get_ws.return_value = mock_ws

        result = runner.invoke(
            app,
            [
                "custom-events",
                "create",
                "--name",
                "Page View",
                "--alternative",
                "Home",
                "--alternative",
                "Product",
                "--alternative",
                "Checkout",
            ],
        )

        assert result.exit_code == 0
        called_params = mock_ws.create_custom_event.call_args[0][0]
        assert called_params.alternatives == ["Home", "Product", "Checkout"]

    def test_create_missing_name_errors(self) -> None:
        """Omitting --name causes typer to exit non-zero."""
        result = runner.invoke(app, ["custom-events", "create", "--alternative", "X"])
        assert result.exit_code != 0

    def test_create_missing_alternative_errors(self) -> None:
        """Omitting --alternative causes a non-zero exit (Pydantic validation error)."""
        result = runner.invoke(app, ["custom-events", "create", "--name", "X"])
        assert result.exit_code != 0

    @patch("mixpanel_headless.cli.commands.custom_events.get_workspace")
    def test_create_empty_name_surfaces_as_input_error_not_api_error(
        self, mock_get_ws: MagicMock
    ) -> None:
        """Empty --name violates Pydantic min_length and reports as INPUT error.

        Empty ``--name`` violates ``CreateCustomEventParams.name`` ``min_length=1``
        and must surface as a CLI input error, not as "API response parsing
        error" — the latter would falsely imply the request reached the
        server. The error message must mention the offending field so the
        user can correct it.
        """
        mock_get_ws.return_value = MagicMock()  # no workspace call should happen

        result = runner.invoke(
            app,
            ["custom-events", "create", "--name", "", "--alternative", "X"],
        )

        assert result.exit_code != 0
        combined_output = (result.stdout or "") + (result.stderr or "")
        assert "API response parsing error" not in combined_output
        assert "name" in combined_output.lower()
