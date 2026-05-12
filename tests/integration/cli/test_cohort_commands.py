# ruff: noqa: ARG001
"""Integration tests for cohort CLI commands."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from mixpanel_headless.cli.main import app


class TestCohortsList:
    """Tests for mp cohorts list command."""

    def test_list_json(self, cli_runner: CliRunner, mock_workspace: MagicMock) -> None:
        """Verify listing cohorts returns JSON array with id and name."""
        with patch(
            "mixpanel_headless.cli.commands.cohorts.get_workspace",
            return_value=mock_workspace,
        ):
            result = cli_runner.invoke(app, ["cohorts", "list"])

        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["id"] == 1
        assert data[0]["name"] == "Power Users"

    def test_list_by_data_group(
        self, cli_runner: CliRunner, mock_workspace: MagicMock
    ) -> None:
        """Verify data-group-id option is forwarded to the workspace method."""
        with patch(
            "mixpanel_headless.cli.commands.cohorts.get_workspace",
            return_value=mock_workspace,
        ):
            result = cli_runner.invoke(
                app, ["cohorts", "list", "--data-group-id", "abc"]
            )

        assert result.exit_code == 0
        mock_workspace.list_cohorts_full.assert_called_once_with(
            data_group_id="abc",
            ids=None,
        )

    def test_list_by_ids(
        self, cli_runner: CliRunner, mock_workspace: MagicMock
    ) -> None:
        """Verify filtering cohorts by comma-separated IDs succeeds."""
        with patch(
            "mixpanel_headless.cli.commands.cohorts.get_workspace",
            return_value=mock_workspace,
        ):
            result = cli_runner.invoke(app, ["cohorts", "list", "--ids", "1,2"])

        assert result.exit_code == 0
        mock_workspace.list_cohorts_full.assert_called_once_with(
            data_group_id=None,
            ids=[1, 2],
        )


class TestCohortsCreate:
    """Tests for mp cohorts create command."""

    def test_create_minimal(
        self, cli_runner: CliRunner, mock_workspace: MagicMock
    ) -> None:
        """Verify creating a cohort with only a name returns JSON with id."""
        with patch(
            "mixpanel_headless.cli.commands.cohorts.get_workspace",
            return_value=mock_workspace,
        ):
            result = cli_runner.invoke(app, ["cohorts", "create", "--name", "New"])

        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["id"] == 1

    def test_create_with_definition(
        self, cli_runner: CliRunner, mock_workspace: MagicMock
    ) -> None:
        """Verify creating a cohort with a JSON definition succeeds."""
        definition = json.dumps({"behavioral_filter": {}})
        with patch(
            "mixpanel_headless.cli.commands.cohorts.get_workspace",
            return_value=mock_workspace,
        ):
            result = cli_runner.invoke(
                app,
                ["cohorts", "create", "--name", "New", "--definition", definition],
            )

        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["id"] == 1

    def test_create_invalid_json(
        self, cli_runner: CliRunner, mock_workspace: MagicMock
    ) -> None:
        """Verify invalid JSON definition causes a non-zero exit code."""
        with patch(
            "mixpanel_headless.cli.commands.cohorts.get_workspace",
            return_value=mock_workspace,
        ):
            result = cli_runner.invoke(
                app,
                ["cohorts", "create", "--name", "New", "--definition", "bad"],
            )

        assert result.exit_code != 0


class TestCohortsGetUpdateDelete:
    """Tests for mp cohorts get, update, and delete commands."""

    def test_get(self, cli_runner: CliRunner, mock_workspace: MagicMock) -> None:
        """Verify getting a cohort by ID returns JSON with matching id."""
        with patch(
            "mixpanel_headless.cli.commands.cohorts.get_workspace",
            return_value=mock_workspace,
        ):
            result = cli_runner.invoke(app, ["cohorts", "get", "1"])

        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["id"] == 1

    def test_update_name(
        self, cli_runner: CliRunner, mock_workspace: MagicMock
    ) -> None:
        """Verify updating a cohort name succeeds with exit code 0."""
        with patch(
            "mixpanel_headless.cli.commands.cohorts.get_workspace",
            return_value=mock_workspace,
        ):
            result = cli_runner.invoke(
                app, ["cohorts", "update", "1", "--name", "Renamed"]
            )

        assert result.exit_code == 0
        mock_workspace.update_cohort.assert_called_once()

    def test_update_definition(
        self, cli_runner: CliRunner, mock_workspace: MagicMock
    ) -> None:
        """Verify updating a cohort with a JSON definition succeeds."""
        definition = json.dumps({"filter": "x"})
        with patch(
            "mixpanel_headless.cli.commands.cohorts.get_workspace",
            return_value=mock_workspace,
        ):
            result = cli_runner.invoke(
                app, ["cohorts", "update", "1", "--definition", definition]
            )

        assert result.exit_code == 0
        mock_workspace.update_cohort.assert_called_once()

    def test_delete(self, cli_runner: CliRunner, mock_workspace: MagicMock) -> None:
        """Verify deleting a cohort by ID succeeds with exit code 0."""
        with patch(
            "mixpanel_headless.cli.commands.cohorts.get_workspace",
            return_value=mock_workspace,
        ):
            result = cli_runner.invoke(app, ["cohorts", "delete", "1"])

        assert result.exit_code == 0
        mock_workspace.delete_cohort.assert_called_once_with(1)


class TestCohortsBulk:
    """Tests for mp cohorts bulk-delete and bulk-update commands."""

    def test_bulk_delete(
        self, cli_runner: CliRunner, mock_workspace: MagicMock
    ) -> None:
        """Verify bulk-deleting cohorts by comma-separated IDs succeeds."""
        with patch(
            "mixpanel_headless.cli.commands.cohorts.get_workspace",
            return_value=mock_workspace,
        ):
            result = cli_runner.invoke(app, ["cohorts", "bulk-delete", "--ids", "1,2"])

        assert result.exit_code == 0
        mock_workspace.bulk_delete_cohorts.assert_called_once_with([1, 2])

    def test_bulk_update(
        self, cli_runner: CliRunner, mock_workspace: MagicMock
    ) -> None:
        """Verify bulk-updating cohorts with a JSON entries array succeeds."""
        entries = json.dumps([{"id": 1, "name": "Updated"}])
        with patch(
            "mixpanel_headless.cli.commands.cohorts.get_workspace",
            return_value=mock_workspace,
        ):
            result = cli_runner.invoke(
                app, ["cohorts", "bulk-update", "--entries", entries]
            )

        assert result.exit_code == 0
        mock_workspace.bulk_update_cohorts.assert_called_once()

    def test_bulk_update_invalid_json(
        self, cli_runner: CliRunner, mock_workspace: MagicMock
    ) -> None:
        """Verify invalid JSON in bulk-update entries causes a non-zero exit."""
        with patch(
            "mixpanel_headless.cli.commands.cohorts.get_workspace",
            return_value=mock_workspace,
        ):
            result = cli_runner.invoke(
                app, ["cohorts", "bulk-update", "--entries", "not json"]
            )

        assert result.exit_code != 0


class TestCohortsInputValidation:
    """Tests for cohort command input validation edge cases."""

    def test_invalid_ids(
        self, cli_runner: CliRunner, mock_workspace: MagicMock
    ) -> None:
        """Verify non-numeric IDs in list filter cause a non-zero exit code."""
        with patch(
            "mixpanel_headless.cli.commands.cohorts.get_workspace",
            return_value=mock_workspace,
        ):
            result = cli_runner.invoke(app, ["cohorts", "list", "--ids", "abc"])

        assert result.exit_code != 0

    def test_empty_ids_bulk_delete(
        self, cli_runner: CliRunner, mock_workspace: MagicMock
    ) -> None:
        """Verify empty IDs string in bulk-delete causes a non-zero exit code."""
        with patch(
            "mixpanel_headless.cli.commands.cohorts.get_workspace",
            return_value=mock_workspace,
        ):
            result = cli_runner.invoke(app, ["cohorts", "bulk-delete", "--ids", ""])

        assert result.exit_code != 0

    def test_no_args_shows_help(
        self,
        cli_runner: CliRunner,
        mock_workspace: MagicMock,  # noqa: ARG002
    ) -> None:
        """Verify invoking cohorts with no subcommand shows usage help."""
        result = cli_runner.invoke(app, ["cohorts"])

        # Typer's no_args_is_help exits with code 0 or 2 depending on version
        assert result.exit_code in (0, 2)
        combined = result.stdout + (result.output or "")
        assert "Usage" in combined or "cohorts" in combined
