# ruff: noqa: ARG001
"""Integration tests for annotation CLI commands."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from mixpanel_headless.cli.main import app


class TestAnnotationsList:
    """Tests for mp annotations list command."""

    def test_list_json(self, cli_runner: CliRunner, mock_workspace: MagicMock) -> None:
        """Test annotations list in JSON format."""
        with patch(
            "mixpanel_headless.cli.commands.annotations.get_workspace",
            return_value=mock_workspace,
        ):
            result = cli_runner.invoke(app, ["annotations", "list", "--format", "json"])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert isinstance(data, list)
        assert data[0]["id"] == 1
        assert data[0]["description"] == "Test annotation"

    def test_list_table_format(
        self, cli_runner: CliRunner, mock_workspace: MagicMock
    ) -> None:
        """Test annotations list in table format."""
        with patch(
            "mixpanel_headless.cli.commands.annotations.get_workspace",
            return_value=mock_workspace,
        ):
            result = cli_runner.invoke(
                app, ["annotations", "list", "--format", "table"]
            )
        assert result.exit_code == 0
        assert len(result.stdout.strip()) > 0

    def test_list_empty(self, cli_runner: CliRunner, mock_workspace: MagicMock) -> None:
        """Test annotations list with no results."""
        mock_workspace.list_annotations.return_value = []
        with patch(
            "mixpanel_headless.cli.commands.annotations.get_workspace",
            return_value=mock_workspace,
        ):
            result = cli_runner.invoke(app, ["annotations", "list", "--format", "json"])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data == []

    def test_list_with_date_filters(
        self, cli_runner: CliRunner, mock_workspace: MagicMock
    ) -> None:
        """Test annotations list with --from and --to date filters."""
        with patch(
            "mixpanel_headless.cli.commands.annotations.get_workspace",
            return_value=mock_workspace,
        ):
            result = cli_runner.invoke(
                app,
                [
                    "annotations",
                    "list",
                    "--from",
                    "2026-01-01",
                    "--to",
                    "2026-03-31",
                ],
            )
        assert result.exit_code == 0
        mock_workspace.list_annotations.assert_called_once_with(
            from_date="2026-01-01", to_date="2026-03-31", tags=None
        )

    def test_list_with_tags_filter(
        self, cli_runner: CliRunner, mock_workspace: MagicMock
    ) -> None:
        """Test annotations list with --tags filter."""
        with patch(
            "mixpanel_headless.cli.commands.annotations.get_workspace",
            return_value=mock_workspace,
        ):
            result = cli_runner.invoke(app, ["annotations", "list", "--tags", "1,2"])
        assert result.exit_code == 0
        mock_workspace.list_annotations.assert_called_once_with(
            from_date=None, to_date=None, tags=[1, 2]
        )


class TestAnnotationsCreate:
    """Tests for mp annotations create command."""

    def test_create_minimal(
        self, cli_runner: CliRunner, mock_workspace: MagicMock
    ) -> None:
        """Test creating an annotation with only required options."""
        with patch(
            "mixpanel_headless.cli.commands.annotations.get_workspace",
            return_value=mock_workspace,
        ):
            result = cli_runner.invoke(
                app,
                [
                    "annotations",
                    "create",
                    "--date",
                    "2026-03-31",
                    "--description",
                    "Test",
                ],
            )
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert "id" in data

    def test_create_all_options(
        self, cli_runner: CliRunner, mock_workspace: MagicMock
    ) -> None:
        """Test creating an annotation with all options."""
        with patch(
            "mixpanel_headless.cli.commands.annotations.get_workspace",
            return_value=mock_workspace,
        ):
            result = cli_runner.invoke(
                app,
                [
                    "annotations",
                    "create",
                    "--date",
                    "2026-03-31",
                    "--description",
                    "Full annotation",
                    "--tags",
                    "1,2",
                    "--user-id",
                    "10",
                ],
            )
        assert result.exit_code == 0
        params = mock_workspace.create_annotation.call_args[0][0]
        assert params.date == "2026-03-31"
        assert params.description == "Full annotation"
        assert params.tags == [1, 2]
        assert params.user_id == 10


class TestAnnotationsGet:
    """Tests for mp annotations get command."""

    def test_get(self, cli_runner: CliRunner, mock_workspace: MagicMock) -> None:
        """Test getting a single annotation by ID."""
        with patch(
            "mixpanel_headless.cli.commands.annotations.get_workspace",
            return_value=mock_workspace,
        ):
            result = cli_runner.invoke(app, ["annotations", "get", "1"])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["id"] == 1
        assert data["description"] == "Test annotation"


class TestAnnotationsUpdate:
    """Tests for mp annotations update command."""

    def test_update_description(
        self, cli_runner: CliRunner, mock_workspace: MagicMock
    ) -> None:
        """Test updating an annotation's description."""
        with patch(
            "mixpanel_headless.cli.commands.annotations.get_workspace",
            return_value=mock_workspace,
        ):
            result = cli_runner.invoke(
                app,
                [
                    "annotations",
                    "update",
                    "1",
                    "--description",
                    "Updated text",
                ],
            )
        assert result.exit_code == 0
        params = mock_workspace.update_annotation.call_args[0][1]
        assert params.description == "Updated text"

    def test_update_tags(
        self, cli_runner: CliRunner, mock_workspace: MagicMock
    ) -> None:
        """Test updating an annotation's tags."""
        with patch(
            "mixpanel_headless.cli.commands.annotations.get_workspace",
            return_value=mock_workspace,
        ):
            result = cli_runner.invoke(
                app,
                ["annotations", "update", "1", "--tags", "1,2,3"],
            )
        assert result.exit_code == 0
        params = mock_workspace.update_annotation.call_args[0][1]
        assert params.tags == [1, 2, 3]


class TestAnnotationsDelete:
    """Tests for mp annotations delete command."""

    def test_delete(self, cli_runner: CliRunner, mock_workspace: MagicMock) -> None:
        """Test deleting an annotation."""
        with patch(
            "mixpanel_headless.cli.commands.annotations.get_workspace",
            return_value=mock_workspace,
        ):
            result = cli_runner.invoke(app, ["annotations", "delete", "1"])
        assert result.exit_code == 0
        mock_workspace.delete_annotation.assert_called_once_with(1)


class TestAnnotationTagsList:
    """Tests for mp annotations tags list command."""

    def test_tags_list(self, cli_runner: CliRunner, mock_workspace: MagicMock) -> None:
        """Test listing annotation tags."""
        with patch(
            "mixpanel_headless.cli.commands.annotations.get_workspace",
            return_value=mock_workspace,
        ):
            result = cli_runner.invoke(
                app, ["annotations", "tags", "list", "--format", "json"]
            )
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert isinstance(data, list)
        assert data[0]["name"] == "releases"


class TestAnnotationTagsCreate:
    """Tests for mp annotations tags create command."""

    def test_tags_create(
        self, cli_runner: CliRunner, mock_workspace: MagicMock
    ) -> None:
        """Test creating an annotation tag."""
        with patch(
            "mixpanel_headless.cli.commands.annotations.get_workspace",
            return_value=mock_workspace,
        ):
            result = cli_runner.invoke(
                app, ["annotations", "tags", "create", "--name", "new-tag"]
            )
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["name"] == "new-tag"


class TestAnnotationsInputValidation:
    """Tests for input validation on annotation commands."""

    def test_no_args_shows_help(
        self,
        cli_runner: CliRunner,
        mock_workspace: MagicMock,  # noqa: ARG002
    ) -> None:
        """Test that running annotations with no args shows help text."""
        result = cli_runner.invoke(app, ["annotations"])
        combined = result.stdout + (result.output or "")
        assert result.exit_code == 0 or result.exit_code == 2
        assert "annotations" in combined.lower() or "usage" in combined.lower()
