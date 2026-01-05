"""Integration tests for fetch CLI commands."""

from __future__ import annotations

import json
from datetime import datetime
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from mixpanel_data.cli.main import app
from mixpanel_data.types import FetchResult, ParallelFetchResult


class TestFetchEvents:
    """Tests for mp fetch events command."""

    def test_events_happy_path(
        self, cli_runner: CliRunner, mock_workspace: MagicMock
    ) -> None:
        """Test fetching events with required options."""
        mock_workspace.fetch_events.return_value = FetchResult(
            table="events",
            rows=1000,
            type="events",
            date_range=("2024-01-01", "2024-01-31"),
            duration_seconds=5.0,
            fetched_at=datetime.now(),
        )

        with patch(
            "mixpanel_data.cli.commands.fetch.get_workspace",
            return_value=mock_workspace,
        ):
            result = cli_runner.invoke(
                app,
                [
                    "fetch",
                    "events",
                    "my_events",
                    "--from",
                    "2024-01-01",
                    "--to",
                    "2024-01-31",
                    "--format",
                    "json",
                ],
            )

        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["table"] == "events"
        assert data["rows"] == 1000
        mock_workspace.fetch_events.assert_called_once()
        call_kwargs = mock_workspace.fetch_events.call_args.kwargs
        assert call_kwargs["name"] == "my_events"
        assert call_kwargs["from_date"] == "2024-01-01"
        assert call_kwargs["to_date"] == "2024-01-31"

    def test_events_missing_from_date(self, cli_runner: CliRunner) -> None:
        """Test that missing --from date returns error."""
        result = cli_runner.invoke(
            app,
            ["fetch", "events", "--to", "2024-01-31", "--format", "json"],
        )

        assert result.exit_code == 3
        assert "--from is required" in result.output

    def test_events_missing_to_date(self, cli_runner: CliRunner) -> None:
        """Test that missing --to date returns error."""
        result = cli_runner.invoke(
            app,
            ["fetch", "events", "--from", "2024-01-01", "--format", "json"],
        )

        assert result.exit_code == 3
        assert "--to is required" in result.output

    def test_events_with_replace_flag(
        self, cli_runner: CliRunner, mock_workspace: MagicMock
    ) -> None:
        """Test --replace flag drops existing table first."""
        mock_workspace.fetch_events.return_value = FetchResult(
            table="events",
            rows=500,
            type="events",
            date_range=("2024-01-01", "2024-01-31"),
            duration_seconds=3.0,
            fetched_at=datetime.now(),
        )

        with patch(
            "mixpanel_data.cli.commands.fetch.get_workspace",
            return_value=mock_workspace,
        ):
            result = cli_runner.invoke(
                app,
                [
                    "fetch",
                    "events",
                    "events",
                    "--from",
                    "2024-01-01",
                    "--to",
                    "2024-01-31",
                    "--replace",
                    "--format",
                    "json",
                ],
            )

        assert result.exit_code == 0
        mock_workspace.drop.assert_called_once_with("events")

    def test_events_with_event_filter(
        self, cli_runner: CliRunner, mock_workspace: MagicMock
    ) -> None:
        """Test --events filter is passed to workspace."""
        mock_workspace.fetch_events.return_value = FetchResult(
            table="events",
            rows=100,
            type="events",
            date_range=("2024-01-01", "2024-01-31"),
            duration_seconds=1.0,
            fetched_at=datetime.now(),
        )

        with patch(
            "mixpanel_data.cli.commands.fetch.get_workspace",
            return_value=mock_workspace,
        ):
            result = cli_runner.invoke(
                app,
                [
                    "fetch",
                    "events",
                    "--from",
                    "2024-01-01",
                    "--to",
                    "2024-01-31",
                    "--events",
                    "Signup,Login,Purchase",
                    "--format",
                    "json",
                ],
            )

        assert result.exit_code == 0
        call_kwargs = mock_workspace.fetch_events.call_args.kwargs
        assert call_kwargs["events"] == ["Signup", "Login", "Purchase"]

    def test_events_with_where_filter(
        self, cli_runner: CliRunner, mock_workspace: MagicMock
    ) -> None:
        """Test --where filter is passed to workspace."""
        mock_workspace.fetch_events.return_value = FetchResult(
            table="events",
            rows=50,
            type="events",
            date_range=("2024-01-01", "2024-01-31"),
            duration_seconds=1.0,
            fetched_at=datetime.now(),
        )

        with patch(
            "mixpanel_data.cli.commands.fetch.get_workspace",
            return_value=mock_workspace,
        ):
            result = cli_runner.invoke(
                app,
                [
                    "fetch",
                    "events",
                    "--from",
                    "2024-01-01",
                    "--to",
                    "2024-01-31",
                    "--where",
                    'properties["country"] == "US"',
                    "--format",
                    "json",
                ],
            )

        assert result.exit_code == 0
        call_kwargs = mock_workspace.fetch_events.call_args.kwargs
        assert call_kwargs["where"] == 'properties["country"] == "US"'

    def test_events_with_no_progress(
        self, cli_runner: CliRunner, mock_workspace: MagicMock
    ) -> None:
        """Test --no-progress flag disables progress bar."""
        mock_workspace.fetch_events.return_value = FetchResult(
            table="events",
            rows=100,
            type="events",
            date_range=("2024-01-01", "2024-01-31"),
            duration_seconds=1.0,
            fetched_at=datetime.now(),
        )

        with patch(
            "mixpanel_data.cli.commands.fetch.get_workspace",
            return_value=mock_workspace,
        ):
            result = cli_runner.invoke(
                app,
                [
                    "fetch",
                    "events",
                    "--from",
                    "2024-01-01",
                    "--to",
                    "2024-01-31",
                    "--no-progress",
                    "--format",
                    "json",
                ],
            )

        assert result.exit_code == 0
        call_kwargs = mock_workspace.fetch_events.call_args.kwargs
        assert call_kwargs["progress"] is False


class TestFetchProfiles:
    """Tests for mp fetch profiles command."""

    def test_profiles_happy_path(
        self, cli_runner: CliRunner, mock_workspace: MagicMock
    ) -> None:
        """Test fetching profiles with default options."""
        mock_workspace.fetch_profiles.return_value = FetchResult(
            table="profiles",
            rows=500,
            type="profiles",
            date_range=None,
            duration_seconds=2.0,
            fetched_at=datetime.now(),
        )

        with patch(
            "mixpanel_data.cli.commands.fetch.get_workspace",
            return_value=mock_workspace,
        ):
            result = cli_runner.invoke(
                app,
                ["fetch", "profiles", "--format", "json"],
            )

        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["table"] == "profiles"
        assert data["rows"] == 500
        mock_workspace.fetch_profiles.assert_called_once()

    def test_profiles_with_custom_name(
        self, cli_runner: CliRunner, mock_workspace: MagicMock
    ) -> None:
        """Test fetching profiles with custom table name."""
        mock_workspace.fetch_profiles.return_value = FetchResult(
            table="users",
            rows=300,
            type="profiles",
            date_range=None,
            duration_seconds=1.5,
            fetched_at=datetime.now(),
        )

        with patch(
            "mixpanel_data.cli.commands.fetch.get_workspace",
            return_value=mock_workspace,
        ):
            result = cli_runner.invoke(
                app,
                ["fetch", "profiles", "users", "--format", "json"],
            )

        assert result.exit_code == 0
        call_kwargs = mock_workspace.fetch_profiles.call_args.kwargs
        assert call_kwargs["name"] == "users"

    def test_profiles_with_replace_flag(
        self, cli_runner: CliRunner, mock_workspace: MagicMock
    ) -> None:
        """Test --replace flag drops existing table first."""
        mock_workspace.fetch_profiles.return_value = FetchResult(
            table="profiles",
            rows=200,
            type="profiles",
            date_range=None,
            duration_seconds=1.0,
            fetched_at=datetime.now(),
        )

        with patch(
            "mixpanel_data.cli.commands.fetch.get_workspace",
            return_value=mock_workspace,
        ):
            result = cli_runner.invoke(
                app,
                ["fetch", "profiles", "--replace", "--format", "json"],
            )

        assert result.exit_code == 0
        mock_workspace.drop.assert_called_once_with("profiles")

    def test_profiles_with_where_filter(
        self, cli_runner: CliRunner, mock_workspace: MagicMock
    ) -> None:
        """Test --where filter is passed to workspace."""
        mock_workspace.fetch_profiles.return_value = FetchResult(
            table="profiles",
            rows=100,
            type="profiles",
            date_range=None,
            duration_seconds=0.5,
            fetched_at=datetime.now(),
        )

        with patch(
            "mixpanel_data.cli.commands.fetch.get_workspace",
            return_value=mock_workspace,
        ):
            result = cli_runner.invoke(
                app,
                [
                    "fetch",
                    "profiles",
                    "--where",
                    'properties["$city"] == "San Francisco"',
                    "--format",
                    "json",
                ],
            )

        assert result.exit_code == 0
        call_kwargs = mock_workspace.fetch_profiles.call_args.kwargs
        assert call_kwargs["where"] == 'properties["$city"] == "San Francisco"'

    def test_profiles_with_no_progress(
        self, cli_runner: CliRunner, mock_workspace: MagicMock
    ) -> None:
        """Test --no-progress flag disables progress bar."""
        mock_workspace.fetch_profiles.return_value = FetchResult(
            table="profiles",
            rows=100,
            type="profiles",
            date_range=None,
            duration_seconds=0.5,
            fetched_at=datetime.now(),
        )

        with patch(
            "mixpanel_data.cli.commands.fetch.get_workspace",
            return_value=mock_workspace,
        ):
            result = cli_runner.invoke(
                app,
                ["fetch", "profiles", "--no-progress", "--format", "json"],
            )

        assert result.exit_code == 0
        call_kwargs = mock_workspace.fetch_profiles.call_args.kwargs
        assert call_kwargs["progress"] is False


# =============================================================================
# Batch Size Parameter Tests
# =============================================================================


class TestFetchEventsBatchSize:
    """Tests for --batch-size option in fetch events command."""

    def test_batch_size_passed_to_workspace(
        self, cli_runner: CliRunner, mock_workspace: MagicMock
    ) -> None:
        """Test that --batch-size is passed to workspace.fetch_events."""
        mock_workspace.fetch_events.return_value = FetchResult(
            table="events",
            rows=1000,
            type="events",
            date_range=("2024-01-01", "2024-01-31"),
            duration_seconds=5.0,
            fetched_at=datetime.now(),
        )

        with patch(
            "mixpanel_data.cli.commands.fetch.get_workspace",
            return_value=mock_workspace,
        ):
            result = cli_runner.invoke(
                app,
                [
                    "fetch",
                    "events",
                    "--from",
                    "2024-01-01",
                    "--to",
                    "2024-01-31",
                    "--batch-size",
                    "500",
                    "--format",
                    "json",
                ],
            )

        assert result.exit_code == 0
        call_kwargs = mock_workspace.fetch_events.call_args.kwargs
        assert call_kwargs["batch_size"] == 500

    def test_batch_size_default_not_passed(
        self, cli_runner: CliRunner, mock_workspace: MagicMock
    ) -> None:
        """Test that default batch_size is passed when not specified."""
        mock_workspace.fetch_events.return_value = FetchResult(
            table="events",
            rows=1000,
            type="events",
            date_range=("2024-01-01", "2024-01-31"),
            duration_seconds=5.0,
            fetched_at=datetime.now(),
        )

        with patch(
            "mixpanel_data.cli.commands.fetch.get_workspace",
            return_value=mock_workspace,
        ):
            result = cli_runner.invoke(
                app,
                [
                    "fetch",
                    "events",
                    "--from",
                    "2024-01-01",
                    "--to",
                    "2024-01-31",
                    "--format",
                    "json",
                ],
            )

        assert result.exit_code == 0
        call_kwargs = mock_workspace.fetch_events.call_args.kwargs
        assert call_kwargs["batch_size"] == 1000

    def test_batch_size_invalid_too_small(self, cli_runner: CliRunner) -> None:
        """Test that batch_size below 100 is rejected by Typer."""
        result = cli_runner.invoke(
            app,
            [
                "fetch",
                "events",
                "--from",
                "2024-01-01",
                "--to",
                "2024-01-31",
                "--batch-size",
                "50",
            ],
        )

        assert result.exit_code != 0
        # Typer provides its own validation error message

    def test_batch_size_invalid_too_large(self, cli_runner: CliRunner) -> None:
        """Test that batch_size above 100000 is rejected by Typer."""
        result = cli_runner.invoke(
            app,
            [
                "fetch",
                "events",
                "--from",
                "2024-01-01",
                "--to",
                "2024-01-31",
                "--batch-size",
                "200000",
            ],
        )

        assert result.exit_code != 0
        # Typer provides its own validation error message


class TestFetchProfilesBatchSize:
    """Tests for --batch-size option in fetch profiles command."""

    def test_batch_size_passed_to_workspace(
        self, cli_runner: CliRunner, mock_workspace: MagicMock
    ) -> None:
        """Test that --batch-size is passed to workspace.fetch_profiles."""
        mock_workspace.fetch_profiles.return_value = FetchResult(
            table="profiles",
            rows=100,
            type="profiles",
            date_range=None,
            duration_seconds=0.5,
            fetched_at=datetime.now(),
        )

        with patch(
            "mixpanel_data.cli.commands.fetch.get_workspace",
            return_value=mock_workspace,
        ):
            result = cli_runner.invoke(
                app,
                [
                    "fetch",
                    "profiles",
                    "--batch-size",
                    "250",
                    "--format",
                    "json",
                ],
            )

        assert result.exit_code == 0
        call_kwargs = mock_workspace.fetch_profiles.call_args.kwargs
        assert call_kwargs["batch_size"] == 250


# =============================================================================
# Parallel Fetch Tests (US2)
# =============================================================================


class TestFetchEventsParallel:
    """Tests for --parallel option in fetch events command."""

    def test_parallel_flag_passed_to_workspace(
        self, cli_runner: CliRunner, mock_workspace: MagicMock
    ) -> None:
        """Test that --parallel is passed to workspace.fetch_events."""
        mock_workspace.fetch_events.return_value = ParallelFetchResult(
            table="events",
            total_rows=1000,
            successful_batches=3,
            failed_batches=0,
            failed_date_ranges=(),
            duration_seconds=5.0,
            fetched_at=datetime.now(),
        )

        with patch(
            "mixpanel_data.cli.commands.fetch.get_workspace",
            return_value=mock_workspace,
        ):
            result = cli_runner.invoke(
                app,
                [
                    "fetch",
                    "events",
                    "--from",
                    "2024-01-01",
                    "--to",
                    "2024-01-31",
                    "--parallel",
                    "--format",
                    "json",
                ],
            )

        assert result.exit_code == 0
        call_kwargs = mock_workspace.fetch_events.call_args.kwargs
        assert call_kwargs["parallel"] is True

    def test_parallel_short_flag(
        self, cli_runner: CliRunner, mock_workspace: MagicMock
    ) -> None:
        """Test that -p short flag works for parallel."""
        mock_workspace.fetch_events.return_value = ParallelFetchResult(
            table="events",
            total_rows=500,
            successful_batches=2,
            failed_batches=0,
            failed_date_ranges=(),
            duration_seconds=3.0,
            fetched_at=datetime.now(),
        )

        with patch(
            "mixpanel_data.cli.commands.fetch.get_workspace",
            return_value=mock_workspace,
        ):
            result = cli_runner.invoke(
                app,
                [
                    "fetch",
                    "events",
                    "--from",
                    "2024-01-01",
                    "--to",
                    "2024-01-31",
                    "-p",
                    "--format",
                    "json",
                ],
            )

        assert result.exit_code == 0
        call_kwargs = mock_workspace.fetch_events.call_args.kwargs
        assert call_kwargs["parallel"] is True

    def test_parallel_result_output_structure(
        self, cli_runner: CliRunner, mock_workspace: MagicMock
    ) -> None:
        """Test that ParallelFetchResult is output correctly as JSON."""
        mock_workspace.fetch_events.return_value = ParallelFetchResult(
            table="events",
            total_rows=1500,
            successful_batches=3,
            failed_batches=0,
            failed_date_ranges=(),
            duration_seconds=4.5,
            fetched_at=datetime.now(),
        )

        with patch(
            "mixpanel_data.cli.commands.fetch.get_workspace",
            return_value=mock_workspace,
        ):
            result = cli_runner.invoke(
                app,
                [
                    "fetch",
                    "events",
                    "--from",
                    "2024-01-01",
                    "--to",
                    "2024-01-31",
                    "--parallel",
                    "--format",
                    "json",
                ],
            )

        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["table"] == "events"
        assert data["total_rows"] == 1500
        assert data["successful_batches"] == 3
        assert data["failed_batches"] == 0
        assert data["has_failures"] is False

    def test_parallel_progress_callback_set(
        self, cli_runner: CliRunner, mock_workspace: MagicMock
    ) -> None:
        """Test that on_batch_complete callback is set when parallel."""
        mock_workspace.fetch_events.return_value = ParallelFetchResult(
            table="events",
            total_rows=1000,
            successful_batches=3,
            failed_batches=0,
            failed_date_ranges=(),
            duration_seconds=5.0,
            fetched_at=datetime.now(),
        )

        with patch(
            "mixpanel_data.cli.commands.fetch.get_workspace",
            return_value=mock_workspace,
        ):
            result = cli_runner.invoke(
                app,
                [
                    "fetch",
                    "events",
                    "--from",
                    "2024-01-01",
                    "--to",
                    "2024-01-31",
                    "--parallel",
                    "--format",
                    "json",
                ],
            )

        assert result.exit_code == 0
        call_kwargs = mock_workspace.fetch_events.call_args.kwargs
        # When parallel is True and not quiet, on_batch_complete should be set
        assert call_kwargs.get("on_batch_complete") is not None

    def test_parallel_no_progress_callback_when_quiet(
        self, cli_runner: CliRunner, mock_workspace: MagicMock
    ) -> None:
        """Test that on_batch_complete is None when --quiet is set."""
        mock_workspace.fetch_events.return_value = ParallelFetchResult(
            table="events",
            total_rows=1000,
            successful_batches=3,
            failed_batches=0,
            failed_date_ranges=(),
            duration_seconds=5.0,
            fetched_at=datetime.now(),
        )

        with patch(
            "mixpanel_data.cli.commands.fetch.get_workspace",
            return_value=mock_workspace,
        ):
            result = cli_runner.invoke(
                app,
                [
                    "--quiet",
                    "fetch",
                    "events",
                    "--from",
                    "2024-01-01",
                    "--to",
                    "2024-01-31",
                    "--parallel",
                    "--format",
                    "json",
                ],
            )

        assert result.exit_code == 0
        call_kwargs = mock_workspace.fetch_events.call_args.kwargs
        # When quiet is True, on_batch_complete should be None
        assert call_kwargs.get("on_batch_complete") is None

    def test_parallel_not_set_by_default(
        self, cli_runner: CliRunner, mock_workspace: MagicMock
    ) -> None:
        """Test that parallel is False by default."""
        mock_workspace.fetch_events.return_value = FetchResult(
            table="events",
            rows=1000,
            type="events",
            date_range=("2024-01-01", "2024-01-31"),
            duration_seconds=5.0,
            fetched_at=datetime.now(),
        )

        with patch(
            "mixpanel_data.cli.commands.fetch.get_workspace",
            return_value=mock_workspace,
        ):
            result = cli_runner.invoke(
                app,
                [
                    "fetch",
                    "events",
                    "--from",
                    "2024-01-01",
                    "--to",
                    "2024-01-31",
                    "--format",
                    "json",
                ],
            )

        assert result.exit_code == 0
        call_kwargs = mock_workspace.fetch_events.call_args.kwargs
        assert call_kwargs.get("parallel") is False

    def test_parallel_with_failures_exit_code_1(
        self, cli_runner: CliRunner, mock_workspace: MagicMock
    ) -> None:
        """Test that exit code is 1 when parallel fetch has failures."""
        mock_workspace.fetch_events.return_value = ParallelFetchResult(
            table="events",
            total_rows=500,
            successful_batches=2,
            failed_batches=1,
            failed_date_ranges=(("2024-01-15", "2024-01-21"),),
            duration_seconds=5.0,
            fetched_at=datetime.now(),
        )

        with patch(
            "mixpanel_data.cli.commands.fetch.get_workspace",
            return_value=mock_workspace,
        ):
            result = cli_runner.invoke(
                app,
                [
                    "fetch",
                    "events",
                    "--from",
                    "2024-01-01",
                    "--to",
                    "2024-01-31",
                    "--parallel",
                    "--format",
                    "json",
                ],
            )

        assert result.exit_code == 1

    def test_parallel_with_failures_outputs_failed_date_ranges(
        self, cli_runner: CliRunner, mock_workspace: MagicMock
    ) -> None:
        """Test that failed date ranges are included in output."""
        mock_workspace.fetch_events.return_value = ParallelFetchResult(
            table="events",
            total_rows=500,
            successful_batches=2,
            failed_batches=1,
            failed_date_ranges=(("2024-01-15", "2024-01-21"),),
            duration_seconds=5.0,
            fetched_at=datetime.now(),
        )

        with patch(
            "mixpanel_data.cli.commands.fetch.get_workspace",
            return_value=mock_workspace,
        ):
            result = cli_runner.invoke(
                app,
                [
                    "fetch",
                    "events",
                    "--from",
                    "2024-01-01",
                    "--to",
                    "2024-01-31",
                    "--parallel",
                    "--format",
                    "json",
                ],
            )

        data = json.loads(result.stdout)
        assert data["has_failures"] is True
        assert data["failed_batches"] == 1
        assert len(data["failed_date_ranges"]) == 1
        assert data["failed_date_ranges"][0] == ["2024-01-15", "2024-01-21"]

    def test_parallel_with_failures_shows_warning_on_stderr(
        self, cli_runner: CliRunner, mock_workspace: MagicMock
    ) -> None:
        """Test that failure warning is shown on stderr."""
        mock_workspace.fetch_events.return_value = ParallelFetchResult(
            table="events",
            total_rows=500,
            successful_batches=2,
            failed_batches=1,
            failed_date_ranges=(("2024-01-15", "2024-01-21"),),
            duration_seconds=5.0,
            fetched_at=datetime.now(),
        )

        with patch(
            "mixpanel_data.cli.commands.fetch.get_workspace",
            return_value=mock_workspace,
        ):
            result = cli_runner.invoke(
                app,
                [
                    "fetch",
                    "events",
                    "--from",
                    "2024-01-01",
                    "--to",
                    "2024-01-31",
                    "--parallel",
                    "--format",
                    "json",
                ],
            )

        # Should have warning in stderr about failed batches
        assert "failed" in result.output.lower() or "1 batch" in result.output.lower()

    def test_parallel_all_success_no_warning(
        self, cli_runner: CliRunner, mock_workspace: MagicMock
    ) -> None:
        """Test that no warning is shown when all batches succeed."""
        mock_workspace.fetch_events.return_value = ParallelFetchResult(
            table="events",
            total_rows=1500,
            successful_batches=3,
            failed_batches=0,
            failed_date_ranges=(),
            duration_seconds=4.5,
            fetched_at=datetime.now(),
        )

        with patch(
            "mixpanel_data.cli.commands.fetch.get_workspace",
            return_value=mock_workspace,
        ):
            result = cli_runner.invoke(
                app,
                [
                    "fetch",
                    "events",
                    "--from",
                    "2024-01-01",
                    "--to",
                    "2024-01-31",
                    "--parallel",
                    "--format",
                    "json",
                ],
            )

        assert result.exit_code == 0
        # Should not have failure warnings
        assert (
            "failed" not in result.output.lower() or "failed_batches" in result.output
        )

    def test_workers_option_passed_to_workspace(
        self, cli_runner: CliRunner, mock_workspace: MagicMock
    ) -> None:
        """Test that --workers is passed to workspace.fetch_events."""
        mock_workspace.fetch_events.return_value = ParallelFetchResult(
            table="events",
            total_rows=1000,
            successful_batches=3,
            failed_batches=0,
            failed_date_ranges=(),
            duration_seconds=5.0,
            fetched_at=datetime.now(),
        )

        with patch(
            "mixpanel_data.cli.commands.fetch.get_workspace",
            return_value=mock_workspace,
        ):
            result = cli_runner.invoke(
                app,
                [
                    "fetch",
                    "events",
                    "--from",
                    "2024-01-01",
                    "--to",
                    "2024-01-31",
                    "--parallel",
                    "--workers",
                    "5",
                    "--format",
                    "json",
                ],
            )

        assert result.exit_code == 0
        call_kwargs = mock_workspace.fetch_events.call_args.kwargs
        assert call_kwargs["max_workers"] == 5

    def test_workers_requires_parallel_flag(
        self, cli_runner: CliRunner, mock_workspace: MagicMock
    ) -> None:
        """Test that --workers only applies when --parallel is set."""
        mock_workspace.fetch_events.return_value = FetchResult(
            table="events",
            rows=1000,
            type="events",
            date_range=("2024-01-01", "2024-01-31"),
            duration_seconds=5.0,
            fetched_at=datetime.now(),
        )

        with patch(
            "mixpanel_data.cli.commands.fetch.get_workspace",
            return_value=mock_workspace,
        ):
            result = cli_runner.invoke(
                app,
                [
                    "fetch",
                    "events",
                    "--from",
                    "2024-01-01",
                    "--to",
                    "2024-01-31",
                    "--workers",
                    "5",
                    "--format",
                    "json",
                ],
            )

        # Should succeed but max_workers only applies when parallel=True
        assert result.exit_code == 0
        call_kwargs = mock_workspace.fetch_events.call_args.kwargs
        # Workers should still be passed through
        assert call_kwargs.get("max_workers") == 5

    def test_workers_default_not_passed(
        self, cli_runner: CliRunner, mock_workspace: MagicMock
    ) -> None:
        """Test that max_workers is None by default."""
        mock_workspace.fetch_events.return_value = ParallelFetchResult(
            table="events",
            total_rows=1000,
            successful_batches=3,
            failed_batches=0,
            failed_date_ranges=(),
            duration_seconds=5.0,
            fetched_at=datetime.now(),
        )

        with patch(
            "mixpanel_data.cli.commands.fetch.get_workspace",
            return_value=mock_workspace,
        ):
            result = cli_runner.invoke(
                app,
                [
                    "fetch",
                    "events",
                    "--from",
                    "2024-01-01",
                    "--to",
                    "2024-01-31",
                    "--parallel",
                    "--format",
                    "json",
                ],
            )

        assert result.exit_code == 0
        call_kwargs = mock_workspace.fetch_events.call_args.kwargs
        # Without --workers, max_workers should be None (use default)
        assert call_kwargs.get("max_workers") is None

    def test_workers_invalid_zero(
        self, cli_runner: CliRunner, mock_workspace: MagicMock
    ) -> None:
        """Test that --workers 0 is rejected."""
        with patch(
            "mixpanel_data.cli.commands.fetch.get_workspace",
            return_value=mock_workspace,
        ):
            result = cli_runner.invoke(
                app,
                [
                    "fetch",
                    "events",
                    "--from",
                    "2024-01-01",
                    "--to",
                    "2024-01-31",
                    "--parallel",
                    "--workers",
                    "0",
                    "--format",
                    "json",
                ],
            )

        assert result.exit_code != 0

    def test_workers_invalid_negative(
        self, cli_runner: CliRunner, mock_workspace: MagicMock
    ) -> None:
        """Test that --workers -1 is rejected."""
        with patch(
            "mixpanel_data.cli.commands.fetch.get_workspace",
            return_value=mock_workspace,
        ):
            result = cli_runner.invoke(
                app,
                [
                    "fetch",
                    "events",
                    "--from",
                    "2024-01-01",
                    "--to",
                    "2024-01-31",
                    "--parallel",
                    "--workers",
                    "-1",
                    "--format",
                    "json",
                ],
            )

        assert result.exit_code != 0

    def test_limit_with_parallel_rejected(
        self, cli_runner: CliRunner, mock_workspace: MagicMock
    ) -> None:
        """Test that --limit is rejected when combined with --parallel."""
        with patch(
            "mixpanel_data.cli.commands.fetch.get_workspace",
            return_value=mock_workspace,
        ):
            result = cli_runner.invoke(
                app,
                [
                    "fetch",
                    "events",
                    "--from",
                    "2024-01-01",
                    "--to",
                    "2024-01-31",
                    "--parallel",
                    "--limit",
                    "100",
                    "--format",
                    "json",
                ],
            )

        assert result.exit_code == 3
        # Error message is written to stderr via err_console
        assert "--limit is not supported with --parallel" in result.output

    def test_chunk_days_passed_to_workspace(
        self, cli_runner: CliRunner, mock_workspace: MagicMock
    ) -> None:
        """Test that --chunk-days value is passed to workspace."""
        from mixpanel_data.types import ParallelFetchResult

        mock_workspace.fetch_events.return_value = ParallelFetchResult(
            table="events",
            total_rows=100,
            successful_batches=7,
            failed_batches=0,
            failed_date_ranges=(),
            duration_seconds=1.5,
            fetched_at=MagicMock(),
        )

        with patch(
            "mixpanel_data.cli.commands.fetch.get_workspace",
            return_value=mock_workspace,
        ):
            result = cli_runner.invoke(
                app,
                [
                    "fetch",
                    "events",
                    "--from",
                    "2024-01-01",
                    "--to",
                    "2024-01-21",
                    "--parallel",
                    "--chunk-days",
                    "3",
                    "--format",
                    "json",
                ],
            )

        assert result.exit_code == 0

        # Verify chunk_days was passed to workspace
        call_kwargs = mock_workspace.fetch_events.call_args.kwargs
        assert call_kwargs.get("chunk_days") == 3

    def test_chunk_days_default_is_7(
        self, cli_runner: CliRunner, mock_workspace: MagicMock
    ) -> None:
        """Test that --chunk-days defaults to 7 when not specified."""
        from mixpanel_data.types import ParallelFetchResult

        mock_workspace.fetch_events.return_value = ParallelFetchResult(
            table="events",
            total_rows=100,
            successful_batches=3,
            failed_batches=0,
            failed_date_ranges=(),
            duration_seconds=1.5,
            fetched_at=MagicMock(),
        )

        with patch(
            "mixpanel_data.cli.commands.fetch.get_workspace",
            return_value=mock_workspace,
        ):
            result = cli_runner.invoke(
                app,
                [
                    "fetch",
                    "events",
                    "--from",
                    "2024-01-01",
                    "--to",
                    "2024-01-21",
                    "--parallel",
                    "--format",
                    "json",
                ],
            )

        assert result.exit_code == 0

        # Verify default chunk_days of 7 was passed
        call_kwargs = mock_workspace.fetch_events.call_args.kwargs
        assert call_kwargs.get("chunk_days") == 7

    def test_chunk_days_minimum_validation(
        self, cli_runner: CliRunner, mock_workspace: MagicMock
    ) -> None:
        """Test that --chunk-days validates minimum value."""
        with patch(
            "mixpanel_data.cli.commands.fetch.get_workspace",
            return_value=mock_workspace,
        ):
            result = cli_runner.invoke(
                app,
                [
                    "fetch",
                    "events",
                    "--from",
                    "2024-01-01",
                    "--to",
                    "2024-01-31",
                    "--parallel",
                    "--chunk-days",
                    "0",
                    "--format",
                    "json",
                ],
            )

        # Typer validates min=1, so this should fail
        assert result.exit_code != 0

    def test_chunk_days_maximum_validation(
        self, cli_runner: CliRunner, mock_workspace: MagicMock
    ) -> None:
        """Test that --chunk-days validates maximum value."""
        with patch(
            "mixpanel_data.cli.commands.fetch.get_workspace",
            return_value=mock_workspace,
        ):
            result = cli_runner.invoke(
                app,
                [
                    "fetch",
                    "events",
                    "--from",
                    "2024-01-01",
                    "--to",
                    "2024-01-31",
                    "--parallel",
                    "--chunk-days",
                    "101",
                    "--format",
                    "json",
                ],
            )

        # Typer validates max=100, so this should fail
        assert result.exit_code != 0


# =============================================================================
# Behaviors Parameter Validation Tests
# =============================================================================


class TestFetchProfilesBehaviorsValidation:
    """Tests for --behaviors option validation in fetch profiles command."""

    def test_behaviors_requires_where(self, cli_runner: CliRunner) -> None:
        """Test that --behaviors without --where returns error."""
        result = cli_runner.invoke(
            app,
            [
                "fetch",
                "profiles",
                "--behaviors",
                '[{"window":"30d","name":"buyers","event_selectors":[{"event":"Purchase"}]}]',
                "--format",
                "json",
            ],
        )

        assert result.exit_code == 3
        assert "--behaviors requires --where" in result.output

    def test_behaviors_missing_window_field(self, cli_runner: CliRunner) -> None:
        """Test that behavior missing 'window' field returns error."""
        result = cli_runner.invoke(
            app,
            [
                "fetch",
                "profiles",
                "--behaviors",
                '[{"name":"buyers","event_selectors":[{"event":"Purchase"}]}]',
                "--where",
                '(behaviors["buyers"] > 0)',
                "--format",
                "json",
            ],
        )

        assert result.exit_code == 3
        assert "missing required fields" in result.output
        assert "window" in result.output

    def test_behaviors_missing_name_field(self, cli_runner: CliRunner) -> None:
        """Test that behavior missing 'name' field returns error."""
        result = cli_runner.invoke(
            app,
            [
                "fetch",
                "profiles",
                "--behaviors",
                '[{"window":"30d","event_selectors":[{"event":"Purchase"}]}]',
                "--where",
                '(behaviors["buyers"] > 0)',
                "--format",
                "json",
            ],
        )

        assert result.exit_code == 3
        assert "missing required fields" in result.output
        assert "name" in result.output

    def test_behaviors_missing_event_selectors_field(
        self, cli_runner: CliRunner
    ) -> None:
        """Test that behavior missing 'event_selectors' field returns error."""
        result = cli_runner.invoke(
            app,
            [
                "fetch",
                "profiles",
                "--behaviors",
                '[{"window":"30d","name":"buyers"}]',
                "--where",
                '(behaviors["buyers"] > 0)',
                "--format",
                "json",
            ],
        )

        assert result.exit_code == 3
        assert "missing required fields" in result.output
        assert "event_selectors" in result.output

    def test_behaviors_event_selectors_not_array(self, cli_runner: CliRunner) -> None:
        """Test that event_selectors not being an array returns error."""
        result = cli_runner.invoke(
            app,
            [
                "fetch",
                "profiles",
                "--behaviors",
                '[{"window":"30d","name":"buyers","event_selectors":"not_an_array"}]',
                "--where",
                '(behaviors["buyers"] > 0)',
                "--format",
                "json",
            ],
        )

        assert result.exit_code == 3
        assert "event_selectors must be an array" in result.output

    def test_behaviors_not_json_array(self, cli_runner: CliRunner) -> None:
        """Test that --behaviors not being a JSON array returns error."""
        result = cli_runner.invoke(
            app,
            [
                "fetch",
                "profiles",
                "--behaviors",
                '{"window":"30d","name":"buyers","event_selectors":[{"event":"Purchase"}]}',
                "--where",
                '(behaviors["buyers"] > 0)',
                "--format",
                "json",
            ],
        )

        assert result.exit_code == 3
        assert "--behaviors must be a JSON array" in result.output

    def test_behaviors_invalid_json(self, cli_runner: CliRunner) -> None:
        """Test that invalid JSON for --behaviors returns error."""
        result = cli_runner.invoke(
            app,
            [
                "fetch",
                "profiles",
                "--behaviors",
                "not valid json",
                "--where",
                '(behaviors["buyers"] > 0)',
                "--format",
                "json",
            ],
        )

        assert result.exit_code == 3
        assert "Invalid JSON for --behaviors" in result.output

    def test_behaviors_behavior_not_object(self, cli_runner: CliRunner) -> None:
        """Test that behavior item not being an object returns error."""
        result = cli_runner.invoke(
            app,
            [
                "fetch",
                "profiles",
                "--behaviors",
                '["not an object"]',
                "--where",
                '(behaviors["buyers"] > 0)',
                "--format",
                "json",
            ],
        )

        assert result.exit_code == 3
        assert "must be an object" in result.output

    def test_behaviors_valid_format_passed_to_workspace(
        self, cli_runner: CliRunner, mock_workspace: MagicMock
    ) -> None:
        """Test that valid behaviors format is passed to workspace."""
        mock_workspace.fetch_profiles.return_value = FetchResult(
            table="profiles",
            rows=100,
            type="profiles",
            date_range=None,
            duration_seconds=0.5,
            fetched_at=datetime.now(),
        )

        with patch(
            "mixpanel_data.cli.commands.fetch.get_workspace",
            return_value=mock_workspace,
        ):
            result = cli_runner.invoke(
                app,
                [
                    "fetch",
                    "profiles",
                    "--behaviors",
                    '[{"window":"30d","name":"buyers","event_selectors":[{"event":"Purchase"}]}]',
                    "--where",
                    '(behaviors["buyers"] > 0)',
                    "--format",
                    "json",
                ],
            )

        assert result.exit_code == 0
        call_kwargs = mock_workspace.fetch_profiles.call_args.kwargs
        assert call_kwargs["behaviors"] == [
            {
                "window": "30d",
                "name": "buyers",
                "event_selectors": [{"event": "Purchase"}],
            }
        ]
        assert call_kwargs["where"] == '(behaviors["buyers"] > 0)'

    def test_behaviors_multiple_behaviors_valid(
        self, cli_runner: CliRunner, mock_workspace: MagicMock
    ) -> None:
        """Test that multiple behaviors are validated and passed correctly."""
        mock_workspace.fetch_profiles.return_value = FetchResult(
            table="profiles",
            rows=50,
            type="profiles",
            date_range=None,
            duration_seconds=0.3,
            fetched_at=datetime.now(),
        )

        behaviors_json = (
            '[{"window":"30d","name":"signed_up","event_selectors":[{"event":"Signup"}]},'
            '{"window":"30d","name":"purchased","event_selectors":[{"event":"Purchase"}]}]'
        )

        with patch(
            "mixpanel_data.cli.commands.fetch.get_workspace",
            return_value=mock_workspace,
        ):
            result = cli_runner.invoke(
                app,
                [
                    "fetch",
                    "profiles",
                    "--behaviors",
                    behaviors_json,
                    "--where",
                    '(behaviors["signed_up"] > 0) and (behaviors["purchased"] == 0)',
                    "--format",
                    "json",
                ],
            )

        assert result.exit_code == 0
        call_kwargs = mock_workspace.fetch_profiles.call_args.kwargs
        assert len(call_kwargs["behaviors"]) == 2
        assert call_kwargs["behaviors"][0]["name"] == "signed_up"
        assert call_kwargs["behaviors"][1]["name"] == "purchased"

    def test_behaviors_second_behavior_invalid(self, cli_runner: CliRunner) -> None:
        """Test that validation fails on second behavior if it's invalid."""
        # First behavior is valid, second is missing 'name'
        behaviors_json = (
            '[{"window":"30d","name":"buyers","event_selectors":[{"event":"Purchase"}]},'
            '{"window":"7d","event_selectors":[{"event":"Signup"}]}]'
        )

        result = cli_runner.invoke(
            app,
            [
                "fetch",
                "profiles",
                "--behaviors",
                behaviors_json,
                "--where",
                '(behaviors["buyers"] > 0)',
                "--format",
                "json",
            ],
        )

        assert result.exit_code == 3
        assert "index 1" in result.output
        assert "missing required fields" in result.output
        assert "name" in result.output
