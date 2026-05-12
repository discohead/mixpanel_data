# ruff: noqa: ARG001
"""Integration tests for experiment CLI commands."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from mixpanel_headless.cli.main import app


class TestExperimentsList:
    """Tests for mp experiments list command."""

    def test_list_json(self, cli_runner: CliRunner, mock_workspace: MagicMock) -> None:
        """Test experiments list in JSON format."""
        with patch(
            "mixpanel_headless.cli.commands.experiments.get_workspace",
            return_value=mock_workspace,
        ):
            result = cli_runner.invoke(app, ["experiments", "list", "--format", "json"])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert isinstance(data, list)
        assert data[0]["id"] == "xyz-456"
        assert data[0]["name"] == "Test Experiment"

    def test_list_table_format(
        self, cli_runner: CliRunner, mock_workspace: MagicMock
    ) -> None:
        """Test experiments list in table format."""
        with patch(
            "mixpanel_headless.cli.commands.experiments.get_workspace",
            return_value=mock_workspace,
        ):
            result = cli_runner.invoke(
                app, ["experiments", "list", "--format", "table"]
            )
        assert result.exit_code == 0
        assert len(result.stdout.strip()) > 0

    def test_list_include_archived(
        self, cli_runner: CliRunner, mock_workspace: MagicMock
    ) -> None:
        """Test experiments list with include-archived flag."""
        with patch(
            "mixpanel_headless.cli.commands.experiments.get_workspace",
            return_value=mock_workspace,
        ):
            result = cli_runner.invoke(
                app, ["experiments", "list", "--include-archived"]
            )
        assert result.exit_code == 0
        mock_workspace.list_experiments.assert_called_once_with(include_archived=True)

    def test_list_empty(self, cli_runner: CliRunner, mock_workspace: MagicMock) -> None:
        """Test experiments list with no results."""
        mock_workspace.list_experiments.return_value = []
        with patch(
            "mixpanel_headless.cli.commands.experiments.get_workspace",
            return_value=mock_workspace,
        ):
            result = cli_runner.invoke(app, ["experiments", "list", "--format", "json"])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data == []


class TestExperimentsCreate:
    """Tests for mp experiments create command."""

    def test_create_minimal(
        self, cli_runner: CliRunner, mock_workspace: MagicMock
    ) -> None:
        """Test creating an experiment with only a name."""
        with patch(
            "mixpanel_headless.cli.commands.experiments.get_workspace",
            return_value=mock_workspace,
        ):
            result = cli_runner.invoke(
                app, ["experiments", "create", "--name", "New Experiment"]
            )
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert "id" in data

    def test_create_all_options(
        self, cli_runner: CliRunner, mock_workspace: MagicMock
    ) -> None:
        """Test creating an experiment with all options."""
        with patch(
            "mixpanel_headless.cli.commands.experiments.get_workspace",
            return_value=mock_workspace,
        ):
            result = cli_runner.invoke(
                app,
                [
                    "experiments",
                    "create",
                    "--name",
                    "Full Experiment",
                    "--description",
                    "A test experiment",
                    "--hypothesis",
                    "Users will convert more",
                    "--settings",
                    '{"confidence_level": 0.95}',
                ],
            )
        assert result.exit_code == 0
        mock_workspace.create_experiment.assert_called_once()
        params = mock_workspace.create_experiment.call_args[0][0]
        assert params.name == "Full Experiment"
        assert params.description == "A test experiment"
        assert params.hypothesis == "Users will convert more"
        assert params.settings == {"confidence_level": 0.95}

    def test_create_invalid_settings_json(
        self, cli_runner: CliRunner, mock_workspace: MagicMock
    ) -> None:
        """Test creating an experiment with invalid JSON settings fails."""
        with patch(
            "mixpanel_headless.cli.commands.experiments.get_workspace",
            return_value=mock_workspace,
        ):
            result = cli_runner.invoke(
                app,
                [
                    "experiments",
                    "create",
                    "--name",
                    "Bad",
                    "--settings",
                    "not json",
                ],
            )
        assert result.exit_code != 0


class TestExperimentsGet:
    """Tests for mp experiments get command."""

    def test_get(self, cli_runner: CliRunner, mock_workspace: MagicMock) -> None:
        """Test getting a single experiment by ID."""
        with patch(
            "mixpanel_headless.cli.commands.experiments.get_workspace",
            return_value=mock_workspace,
        ):
            result = cli_runner.invoke(app, ["experiments", "get", "xyz-456"])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["id"] == "xyz-456"


class TestExperimentsUpdate:
    """Tests for mp experiments update command."""

    def test_update_name(
        self, cli_runner: CliRunner, mock_workspace: MagicMock
    ) -> None:
        """Test updating an experiment name."""
        with patch(
            "mixpanel_headless.cli.commands.experiments.get_workspace",
            return_value=mock_workspace,
        ):
            result = cli_runner.invoke(
                app, ["experiments", "update", "xyz-456", "--name", "Updated"]
            )
        assert result.exit_code == 0

    def test_update_with_json_fields(
        self, cli_runner: CliRunner, mock_workspace: MagicMock
    ) -> None:
        """Test updating an experiment with JSON fields."""
        with patch(
            "mixpanel_headless.cli.commands.experiments.get_workspace",
            return_value=mock_workspace,
        ):
            result = cli_runner.invoke(
                app,
                [
                    "experiments",
                    "update",
                    "xyz-456",
                    "--variants",
                    '{"control": {"weight": 50}, "test": {"weight": 50}}',
                    "--metrics",
                    '{"primary": "Purchase"}',
                    "--settings",
                    '{"confidence_level": 0.9}',
                    "--tags",
                    "checkout,conversion",
                ],
            )
        assert result.exit_code == 0
        params = mock_workspace.update_experiment.call_args[0][1]
        assert params.variants == {
            "control": {"weight": 50},
            "test": {"weight": 50},
        }
        assert params.metrics == {"primary": "Purchase"}
        assert params.settings == {"confidence_level": 0.9}
        assert params.tags == ["checkout", "conversion"]

    def test_update_invalid_variants_json(
        self, cli_runner: CliRunner, mock_workspace: MagicMock
    ) -> None:
        """Test updating with invalid variants JSON fails."""
        with patch(
            "mixpanel_headless.cli.commands.experiments.get_workspace",
            return_value=mock_workspace,
        ):
            result = cli_runner.invoke(
                app,
                ["experiments", "update", "xyz-456", "--variants", "bad json"],
            )
        assert result.exit_code != 0


class TestExperimentsDelete:
    """Tests for mp experiments delete command."""

    def test_delete(self, cli_runner: CliRunner, mock_workspace: MagicMock) -> None:
        """Test deleting an experiment."""
        with patch(
            "mixpanel_headless.cli.commands.experiments.get_workspace",
            return_value=mock_workspace,
        ):
            result = cli_runner.invoke(app, ["experiments", "delete", "xyz-456"])
        assert result.exit_code == 0
        mock_workspace.delete_experiment.assert_called_once_with("xyz-456")


class TestExperimentsLaunch:
    """Tests for mp experiments launch command."""

    def test_launch(self, cli_runner: CliRunner, mock_workspace: MagicMock) -> None:
        """Test launching an experiment."""
        with patch(
            "mixpanel_headless.cli.commands.experiments.get_workspace",
            return_value=mock_workspace,
        ):
            result = cli_runner.invoke(app, ["experiments", "launch", "xyz-456"])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["id"] == "xyz-456"
        mock_workspace.launch_experiment.assert_called_once_with("xyz-456")


class TestExperimentsConclude:
    """Tests for mp experiments conclude command."""

    def test_conclude_no_end_date(
        self, cli_runner: CliRunner, mock_workspace: MagicMock
    ) -> None:
        """Test concluding an experiment without an end date."""
        with patch(
            "mixpanel_headless.cli.commands.experiments.get_workspace",
            return_value=mock_workspace,
        ):
            result = cli_runner.invoke(app, ["experiments", "conclude", "xyz-456"])
        assert result.exit_code == 0
        mock_workspace.conclude_experiment.assert_called_once_with(
            "xyz-456", params=None
        )

    def test_conclude_with_end_date(
        self, cli_runner: CliRunner, mock_workspace: MagicMock
    ) -> None:
        """Test concluding an experiment with an end date."""
        with patch(
            "mixpanel_headless.cli.commands.experiments.get_workspace",
            return_value=mock_workspace,
        ):
            result = cli_runner.invoke(
                app,
                ["experiments", "conclude", "xyz-456", "--end-date", "2026-04-01"],
            )
        assert result.exit_code == 0
        params = mock_workspace.conclude_experiment.call_args[1]["params"]
        assert params.end_date == "2026-04-01"


class TestExperimentsDecide:
    """Tests for mp experiments decide command."""

    def test_decide_success(
        self, cli_runner: CliRunner, mock_workspace: MagicMock
    ) -> None:
        """Test deciding an experiment as successful."""
        with patch(
            "mixpanel_headless.cli.commands.experiments.get_workspace",
            return_value=mock_workspace,
        ):
            result = cli_runner.invoke(
                app,
                [
                    "experiments",
                    "decide",
                    "xyz-456",
                    "--success",
                    "--variant",
                    "test",
                    "--message",
                    "Clear winner",
                ],
            )
        assert result.exit_code == 0
        params = mock_workspace.decide_experiment.call_args[0][1]
        assert params.success is True
        assert params.variant == "test"
        assert params.message == "Clear winner"

    def test_decide_no_success(
        self, cli_runner: CliRunner, mock_workspace: MagicMock
    ) -> None:
        """Test deciding an experiment as not successful."""
        with patch(
            "mixpanel_headless.cli.commands.experiments.get_workspace",
            return_value=mock_workspace,
        ):
            result = cli_runner.invoke(
                app, ["experiments", "decide", "xyz-456", "--no-success"]
            )
        assert result.exit_code == 0
        params = mock_workspace.decide_experiment.call_args[0][1]
        assert params.success is False


class TestExperimentsArchive:
    """Tests for mp experiments archive command."""

    def test_archive(self, cli_runner: CliRunner, mock_workspace: MagicMock) -> None:
        """Test archiving an experiment."""
        with patch(
            "mixpanel_headless.cli.commands.experiments.get_workspace",
            return_value=mock_workspace,
        ):
            result = cli_runner.invoke(app, ["experiments", "archive", "xyz-456"])
        assert result.exit_code == 0
        mock_workspace.archive_experiment.assert_called_once_with("xyz-456")


class TestExperimentsRestore:
    """Tests for mp experiments restore command."""

    def test_restore(self, cli_runner: CliRunner, mock_workspace: MagicMock) -> None:
        """Test restoring an archived experiment."""
        with patch(
            "mixpanel_headless.cli.commands.experiments.get_workspace",
            return_value=mock_workspace,
        ):
            result = cli_runner.invoke(app, ["experiments", "restore", "xyz-456"])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["id"] == "xyz-456"


class TestExperimentsDuplicate:
    """Tests for mp experiments duplicate command."""

    def test_duplicate_requires_name(self, cli_runner: CliRunner) -> None:
        """Test that duplicating without --name fails."""
        result = cli_runner.invoke(app, ["experiments", "duplicate", "xyz-456"])
        assert result.exit_code != 0
        assert "--name" in result.output or "Missing" in result.output

    def test_duplicate_with_name(
        self, cli_runner: CliRunner, mock_workspace: MagicMock
    ) -> None:
        """Test duplicating an experiment with a name."""
        with patch(
            "mixpanel_headless.cli.commands.experiments.get_workspace",
            return_value=mock_workspace,
        ):
            result = cli_runner.invoke(
                app,
                ["experiments", "duplicate", "xyz-456", "--name", "Clone"],
            )
        assert result.exit_code == 0
        mock_workspace.duplicate_experiment.assert_called_once()
        call_args = mock_workspace.duplicate_experiment.call_args
        assert call_args[0][1].name == "Clone"


class TestExperimentsErf:
    """Tests for mp experiments erf command."""

    def test_erf(self, cli_runner: CliRunner, mock_workspace: MagicMock) -> None:
        """Test listing ERF experiments."""
        with patch(
            "mixpanel_headless.cli.commands.experiments.get_workspace",
            return_value=mock_workspace,
        ):
            result = cli_runner.invoke(app, ["experiments", "erf"])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert isinstance(data, list)
        assert data[0]["id"] == "xyz-456"


class TestExperimentsInputValidation:
    """Tests for input validation on experiment commands."""

    def test_no_args_shows_help(
        self,
        cli_runner: CliRunner,
        mock_workspace: MagicMock,  # noqa: ARG002
    ) -> None:
        """Test that running experiments with no args shows help text."""
        result = cli_runner.invoke(app, ["experiments"])
        combined = result.stdout + (result.output or "")
        assert result.exit_code == 0 or result.exit_code == 2
        assert "experiments" in combined.lower() or "usage" in combined.lower()
