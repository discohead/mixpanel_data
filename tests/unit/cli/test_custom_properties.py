# ruff: noqa: ARG001, ARG005
"""Tests for custom-properties CLI commands.

Tests cover all custom-properties subcommands:
- list: List all custom properties
- get: Get a single custom property
- create: Create a new custom property
- update: Update an existing custom property
- delete: Delete a custom property
- validate: Validate a custom property formula
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import typer.testing

from mixpanel_headless.cli.main import app

runner = typer.testing.CliRunner()


class TestCustomPropertiesList:
    """Tests for mp custom-properties list."""

    @patch("mixpanel_headless.cli.commands.custom_properties.get_workspace")
    def test_returns_json_list(self, mock_get_ws: MagicMock) -> None:
        """Successful list returns JSON list of custom properties."""
        mock_ws = MagicMock()
        mock_ws.list_custom_properties.return_value = [
            MagicMock(model_dump=lambda: {"id": "cp1", "name": "Revenue Per User"}),
            MagicMock(model_dump=lambda: {"id": "cp2", "name": "Lifetime Value"}),
        ]
        mock_get_ws.return_value = mock_ws

        result = runner.invoke(app, ["custom-properties", "list"])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert isinstance(data, list)
        assert len(data) == 2
        assert data[0]["name"] == "Revenue Per User"

    @patch("mixpanel_headless.cli.commands.custom_properties.get_workspace")
    def test_empty_list(self, mock_get_ws: MagicMock) -> None:
        """Empty list returns empty JSON array."""
        mock_ws = MagicMock()
        mock_ws.list_custom_properties.return_value = []
        mock_get_ws.return_value = mock_ws

        result = runner.invoke(app, ["custom-properties", "list"])
        assert result.exit_code == 0
        assert json.loads(result.stdout) == []


class TestCustomPropertiesGet:
    """Tests for mp custom-properties get."""

    @patch("mixpanel_headless.cli.commands.custom_properties.get_workspace")
    def test_get_returns_json(self, mock_get_ws: MagicMock) -> None:
        """Successful get returns JSON dict of custom property."""
        mock_ws = MagicMock()
        mock_ws.get_custom_property.return_value = MagicMock(
            model_dump=lambda: {
                "id": "cp1",
                "name": "Revenue Per User",
                "resource_type": "events",
            }
        )
        mock_get_ws.return_value = mock_ws

        result = runner.invoke(app, ["custom-properties", "get", "--id", "cp1"])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["id"] == "cp1"
        assert data["name"] == "Revenue Per User"

    @patch("mixpanel_headless.cli.commands.custom_properties.get_workspace")
    def test_get_passes_id(self, mock_get_ws: MagicMock) -> None:
        """The property ID is passed to the workspace method."""
        mock_ws = MagicMock()
        mock_ws.get_custom_property.return_value = MagicMock(
            model_dump=lambda: {"id": "abc"}
        )
        mock_get_ws.return_value = mock_ws

        runner.invoke(app, ["custom-properties", "get", "--id", "abc"])
        mock_ws.get_custom_property.assert_called_once_with("abc")


class TestCustomPropertiesCreate:
    """Tests for mp custom-properties create."""

    @patch("mixpanel_headless.cli.commands.custom_properties.get_workspace")
    def test_create_with_formula_returns_json(self, mock_get_ws: MagicMock) -> None:
        """Successful create with formula returns JSON."""
        mock_ws = MagicMock()
        mock_ws.create_custom_property.return_value = MagicMock(
            model_dump=lambda: {
                "id": "cp-new",
                "name": "Revenue Per User",
                "resource_type": "events",
            }
        )
        mock_get_ws.return_value = mock_ws

        composed = json.dumps({"amount": {"resource_type": "event"}})
        result = runner.invoke(
            app,
            [
                "custom-properties",
                "create",
                "--name",
                "Revenue Per User",
                "--resource-type",
                "events",
                "--display-formula",
                'number(properties["amount"])',
                "--composed-properties",
                composed,
            ],
        )
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["name"] == "Revenue Per User"

    @patch("mixpanel_headless.cli.commands.custom_properties.get_workspace")
    def test_create_with_behavior_returns_json(self, mock_get_ws: MagicMock) -> None:
        """Successful create with behavior specification returns JSON."""
        mock_ws = MagicMock()
        mock_ws.create_custom_property.return_value = MagicMock(
            model_dump=lambda: {
                "id": "cp-beh",
                "name": "First Touch UTM",
                "resource_type": "people",
            }
        )
        mock_get_ws.return_value = mock_ws

        behavior = json.dumps({"type": "first_touch", "property": "utm_source"})
        result = runner.invoke(
            app,
            [
                "custom-properties",
                "create",
                "--name",
                "First Touch UTM",
                "--resource-type",
                "people",
                "--behavior",
                behavior,
            ],
        )
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["name"] == "First Touch UTM"

    @patch("mixpanel_headless.cli.commands.custom_properties.get_workspace")
    def test_create_invalid_composed_json_exits_3(self, mock_get_ws: MagicMock) -> None:
        """Invalid JSON for --composed-properties exits with code 3."""
        mock_ws = MagicMock()
        mock_get_ws.return_value = mock_ws

        result = runner.invoke(
            app,
            [
                "custom-properties",
                "create",
                "--name",
                "Bad",
                "--resource-type",
                "events",
                "--display-formula",
                "A",
                "--composed-properties",
                "not-json",
            ],
        )
        assert result.exit_code == 3

    @patch("mixpanel_headless.cli.commands.custom_properties.get_workspace")
    def test_create_invalid_behavior_json_exits_3(self, mock_get_ws: MagicMock) -> None:
        """Invalid JSON for --behavior exits with code 3."""
        mock_ws = MagicMock()
        mock_get_ws.return_value = mock_ws

        result = runner.invoke(
            app,
            [
                "custom-properties",
                "create",
                "--name",
                "Bad",
                "--resource-type",
                "events",
                "--behavior",
                "not-json",
            ],
        )
        assert result.exit_code == 3


class TestCustomPropertiesUpdate:
    """Tests for mp custom-properties update."""

    @patch("mixpanel_headless.cli.commands.custom_properties.get_workspace")
    def test_update_returns_json(self, mock_get_ws: MagicMock) -> None:
        """Successful update returns JSON."""
        mock_ws = MagicMock()
        mock_ws.update_custom_property.return_value = MagicMock(
            model_dump=lambda: {"id": "cp1", "name": "Updated Name"}
        )
        mock_get_ws.return_value = mock_ws

        result = runner.invoke(
            app,
            ["custom-properties", "update", "--id", "cp1", "--name", "Updated Name"],
        )
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["name"] == "Updated Name"

    @patch("mixpanel_headless.cli.commands.custom_properties.get_workspace")
    def test_update_with_visibility(self, mock_get_ws: MagicMock) -> None:
        """Update with --no-is-visible passes is_visible=False."""
        mock_ws = MagicMock()
        mock_ws.update_custom_property.return_value = MagicMock(
            model_dump=lambda: {"id": "cp1", "is_visible": False}
        )
        mock_get_ws.return_value = mock_ws

        result = runner.invoke(
            app,
            ["custom-properties", "update", "--id", "cp1", "--no-is-visible"],
        )
        assert result.exit_code == 0

    @patch("mixpanel_headless.cli.commands.custom_properties.get_workspace")
    def test_update_invalid_composed_json_exits_3(self, mock_get_ws: MagicMock) -> None:
        """Invalid JSON for --composed-properties on update exits with code 3."""
        mock_ws = MagicMock()
        mock_get_ws.return_value = mock_ws

        result = runner.invoke(
            app,
            [
                "custom-properties",
                "update",
                "--id",
                "cp1",
                "--composed-properties",
                "bad{json",
            ],
        )
        assert result.exit_code == 3


class TestCustomPropertiesDelete:
    """Tests for mp custom-properties delete."""

    @patch("mixpanel_headless.cli.commands.custom_properties.get_workspace")
    def test_delete_succeeds(self, mock_get_ws: MagicMock) -> None:
        """Successful delete exits with code 0."""
        mock_ws = MagicMock()
        mock_ws.delete_custom_property.return_value = None
        mock_get_ws.return_value = mock_ws

        result = runner.invoke(app, ["custom-properties", "delete", "--id", "cp1"])
        assert result.exit_code == 0
        mock_ws.delete_custom_property.assert_called_once_with("cp1")


class TestCustomPropertiesValidate:
    """Tests for mp custom-properties validate."""

    @patch("mixpanel_headless.cli.commands.custom_properties.get_workspace")
    def test_validate_returns_json(self, mock_get_ws: MagicMock) -> None:
        """Successful validate returns JSON result."""
        mock_ws = MagicMock()
        mock_ws.validate_custom_property.return_value = {"valid": True, "errors": []}
        mock_get_ws.return_value = mock_ws

        composed = json.dumps({"amount": {"resource_type": "event"}})
        result = runner.invoke(
            app,
            [
                "custom-properties",
                "validate",
                "--name",
                "TestProp",
                "--resource-type",
                "events",
                "--display-formula",
                'number(properties["amount"])',
                "--composed-properties",
                composed,
            ],
        )
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["valid"] is True

    @patch("mixpanel_headless.cli.commands.custom_properties.get_workspace")
    def test_validate_with_behavior(self, mock_get_ws: MagicMock) -> None:
        """Validate with --behavior passes behavior to workspace."""
        mock_ws = MagicMock()
        mock_ws.validate_custom_property.return_value = {"valid": True}
        mock_get_ws.return_value = mock_ws

        behavior = json.dumps({"type": "first_touch"})
        result = runner.invoke(
            app,
            [
                "custom-properties",
                "validate",
                "--name",
                "TestProp",
                "--resource-type",
                "people",
                "--behavior",
                behavior,
            ],
        )
        assert result.exit_code == 0

    @patch("mixpanel_headless.cli.commands.custom_properties.get_workspace")
    def test_validate_invalid_behavior_json_exits_3(
        self, mock_get_ws: MagicMock
    ) -> None:
        """Invalid JSON for --behavior on validate exits with code 3."""
        mock_ws = MagicMock()
        mock_get_ws.return_value = mock_ws

        result = runner.invoke(
            app,
            [
                "custom-properties",
                "validate",
                "--name",
                "TestProp",
                "--resource-type",
                "events",
                "--behavior",
                "bad-json",
            ],
        )
        assert result.exit_code == 3
