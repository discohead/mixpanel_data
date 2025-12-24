"""Integration tests for fetch CLI commands."""

from __future__ import annotations

import json
from datetime import datetime
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from mixpanel_data.cli.main import app
from mixpanel_data.types import FetchResult


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
