# ruff: noqa: ARG001, ARG005
"""Tests for drop-filters CLI commands.

Tests cover all drop-filters subcommands:
- list: List all drop filters
- create: Create a new drop filter
- update: Update an existing drop filter
- delete: Delete a drop filter
- limits: Get drop filter usage limits
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import typer.testing

from mixpanel_headless.cli.main import app

runner = typer.testing.CliRunner()


class TestDropFiltersList:
    """Tests for mp drop-filters list."""

    @patch("mixpanel_headless.cli.commands.drop_filters.get_workspace")
    def test_returns_json_list(self, mock_get_ws: MagicMock) -> None:
        """Successful list returns JSON list of drop filters."""
        mock_ws = MagicMock()
        mock_ws.list_drop_filters.return_value = [
            MagicMock(
                model_dump=lambda: {"id": 1, "event_name": "PageView", "active": True}
            ),
            MagicMock(
                model_dump=lambda: {"id": 2, "event_name": "Debug", "active": False}
            ),
        ]
        mock_get_ws.return_value = mock_ws

        result = runner.invoke(app, ["drop-filters", "list"])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert isinstance(data, list)
        assert len(data) == 2
        assert data[0]["event_name"] == "PageView"

    @patch("mixpanel_headless.cli.commands.drop_filters.get_workspace")
    def test_empty_list(self, mock_get_ws: MagicMock) -> None:
        """Empty list returns empty JSON array."""
        mock_ws = MagicMock()
        mock_ws.list_drop_filters.return_value = []
        mock_get_ws.return_value = mock_ws

        result = runner.invoke(app, ["drop-filters", "list"])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data == []


class TestDropFiltersCreate:
    """Tests for mp drop-filters create."""

    @patch("mixpanel_headless.cli.commands.drop_filters.get_workspace")
    def test_create_returns_json(self, mock_get_ws: MagicMock) -> None:
        """Successful create returns JSON list of drop filters."""
        mock_ws = MagicMock()
        mock_ws.create_drop_filter.return_value = [
            MagicMock(
                model_dump=lambda: {"id": 1, "event_name": "Debug", "active": True}
            ),
        ]
        mock_get_ws.return_value = mock_ws

        filters_json = json.dumps({"property": "env", "value": "test"})
        result = runner.invoke(
            app,
            [
                "drop-filters",
                "create",
                "--event-name",
                "Debug",
                "--filters",
                filters_json,
            ],
        )
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert isinstance(data, list)

    @patch("mixpanel_headless.cli.commands.drop_filters.get_workspace")
    def test_create_invalid_filters_json_exits_3(self, mock_get_ws: MagicMock) -> None:
        """Invalid JSON for --filters exits with code 3."""
        mock_ws = MagicMock()
        mock_get_ws.return_value = mock_ws

        result = runner.invoke(
            app,
            [
                "drop-filters",
                "create",
                "--event-name",
                "Debug",
                "--filters",
                "not-json",
            ],
        )
        assert result.exit_code == 3


class TestDropFiltersUpdate:
    """Tests for mp drop-filters update."""

    @patch("mixpanel_headless.cli.commands.drop_filters.get_workspace")
    def test_update_returns_json(self, mock_get_ws: MagicMock) -> None:
        """Successful update returns JSON list of drop filters."""
        mock_ws = MagicMock()
        mock_ws.update_drop_filter.return_value = [
            MagicMock(
                model_dump=lambda: {"id": 1, "event_name": "Debug", "active": False}
            ),
        ]
        mock_get_ws.return_value = mock_ws

        result = runner.invoke(
            app,
            ["drop-filters", "update", "--id", "1", "--no-active"],
        )
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert isinstance(data, list)

    @patch("mixpanel_headless.cli.commands.drop_filters.get_workspace")
    def test_update_with_new_event_name(self, mock_get_ws: MagicMock) -> None:
        """Update with --event-name passes it to the workspace."""
        mock_ws = MagicMock()
        mock_ws.update_drop_filter.return_value = [
            MagicMock(model_dump=lambda: {"id": 1, "event_name": "NewEvent"}),
        ]
        mock_get_ws.return_value = mock_ws

        result = runner.invoke(
            app,
            ["drop-filters", "update", "--id", "1", "--event-name", "NewEvent"],
        )
        assert result.exit_code == 0

    @patch("mixpanel_headless.cli.commands.drop_filters.get_workspace")
    def test_update_invalid_filters_json_exits_3(self, mock_get_ws: MagicMock) -> None:
        """Invalid JSON for --filters on update exits with code 3."""
        mock_ws = MagicMock()
        mock_get_ws.return_value = mock_ws

        result = runner.invoke(
            app,
            ["drop-filters", "update", "--id", "1", "--filters", "bad{json"],
        )
        assert result.exit_code == 3


class TestDropFiltersDelete:
    """Tests for mp drop-filters delete."""

    @patch("mixpanel_headless.cli.commands.drop_filters.get_workspace")
    def test_delete_returns_json(self, mock_get_ws: MagicMock) -> None:
        """Successful delete returns the remaining drop filters as JSON."""
        mock_ws = MagicMock()
        mock_ws.delete_drop_filter.return_value = [
            MagicMock(model_dump=lambda: {"id": 2, "event_name": "Other"}),
        ]
        mock_get_ws.return_value = mock_ws

        result = runner.invoke(app, ["drop-filters", "delete", "--id", "1"])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert isinstance(data, list)


class TestDropFiltersLimits:
    """Tests for mp drop-filters limits."""

    @patch("mixpanel_headless.cli.commands.drop_filters.get_workspace")
    def test_limits_returns_json(self, mock_get_ws: MagicMock) -> None:
        """Successful limits returns JSON with count and max."""
        mock_ws = MagicMock()
        mock_ws.get_drop_filter_limits.return_value = MagicMock(
            model_dump=lambda: {"current_count": 5, "max_allowed": 50}
        )
        mock_get_ws.return_value = mock_ws

        result = runner.invoke(app, ["drop-filters", "limits"])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["current_count"] == 5
        assert data["max_allowed"] == 50
