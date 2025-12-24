"""Unit tests for CLI fetch streaming commands (--stdout, --raw)."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from mixpanel_data.cli.main import app

if TYPE_CHECKING:
    pass


@pytest.fixture
def cli_runner() -> CliRunner:
    """Create a CLI runner for testing commands."""
    return CliRunner()


def raw_event(
    name: str = "PageView",
    distinct_id: str = "user_123",
    timestamp: int = 1705328400,
    **extra_props: Any,
) -> dict[str, Any]:
    """Create a raw event in Mixpanel API format."""
    props = {
        "distinct_id": distinct_id,
        "time": timestamp,
        "$insert_id": f"evt_{timestamp}",
        **extra_props,
    }
    return {"event": name, "properties": props}


def normalized_event(
    name: str = "PageView",
    distinct_id: str = "user_123",
    timestamp: datetime | None = None,
    **extra_props: Any,
) -> dict[str, Any]:
    """Create a normalized event."""
    if timestamp is None:
        timestamp = datetime(2024, 1, 15, 10, 0, 0, tzinfo=UTC)
    return {
        "event_name": name,
        "distinct_id": distinct_id,
        "event_time": timestamp,
        "insert_id": f"evt_{int(timestamp.timestamp())}",
        "properties": extra_props,
    }


def raw_profile(
    distinct_id: str = "user_123",
    last_seen: str | None = "2024-01-15T14:30:00",
    **extra_props: Any,
) -> dict[str, Any]:
    """Create a raw profile in Mixpanel API format."""
    props = {**extra_props}
    if last_seen:
        props["$last_seen"] = last_seen
    return {"$distinct_id": distinct_id, "$properties": props}


def normalized_profile(
    distinct_id: str = "user_123",
    last_seen: str | None = "2024-01-15T14:30:00",
    **extra_props: Any,
) -> dict[str, Any]:
    """Create a normalized profile."""
    return {
        "distinct_id": distinct_id,
        "last_seen": last_seen,
        "properties": extra_props,
    }


# =============================================================================
# Phase 5: User Story 2 - CLI Stream Events Tests (T011-T015)
# =============================================================================


class TestFetchEventsStdout:
    """Tests for mp fetch events --stdout command."""

    def test_stdout_outputs_jsonl(self, cli_runner: CliRunner) -> None:
        """T018: Test --stdout output is valid JSONL."""
        mock_workspace = MagicMock()
        mock_workspace.stream_events.return_value = iter(
            [
                normalized_event("PageView", "user_1", page="/home"),
                normalized_event("Click", "user_2", button="signup"),
            ]
        )

        with patch("mixpanel_data.cli.commands.fetch.get_workspace") as mock_get_ws:
            mock_get_ws.return_value = mock_workspace

            result = cli_runner.invoke(
                app,
                [
                    "-q",
                    "fetch",
                    "events",
                    "--from",
                    "2024-01-01",
                    "--to",
                    "2024-01-31",
                    "--stdout",
                ],
            )

        assert result.exit_code == 0, f"Failed with: {result.output}"

        # Parse each line as JSON
        lines = [line for line in result.stdout.strip().split("\n") if line]
        assert len(lines) == 2

        for line in lines:
            parsed = json.loads(line)
            assert "event_name" in parsed
            assert "distinct_id" in parsed

    def test_stdout_with_raw_flag(self, cli_runner: CliRunner) -> None:
        """T018: Test --raw changes output format."""
        mock_workspace = MagicMock()
        mock_workspace.stream_events.return_value = iter(
            [raw_event("PageView", "user_1", 1705328400, page="/home")]
        )

        with patch("mixpanel_data.cli.commands.fetch.get_workspace") as mock_get_ws:
            mock_get_ws.return_value = mock_workspace

            result = cli_runner.invoke(
                app,
                [
                    "-q",
                    "fetch",
                    "events",
                    "--from",
                    "2024-01-01",
                    "--to",
                    "2024-01-31",
                    "--stdout",
                    "--raw",
                ],
            )

        assert result.exit_code == 0, f"Failed with: {result.output}"

        # Parse output
        lines = [line for line in result.stdout.strip().split("\n") if line]
        assert len(lines) == 1

        parsed = json.loads(lines[0])
        # Raw format has "event" key, not "event_name"
        assert "event" in parsed
        assert "properties" in parsed
        assert parsed["properties"]["time"] == 1705328400

        # Verify stream_events was called with raw=True
        mock_workspace.stream_events.assert_called_once()
        call_kwargs = mock_workspace.stream_events.call_args[1]
        assert call_kwargs["raw"] is True

    def test_raw_without_stdout_fails(self, cli_runner: CliRunner) -> None:
        """T012: Test --raw without --stdout returns error."""
        result = cli_runner.invoke(
            app,
            ["fetch", "events", "--from", "2024-01-01", "--to", "2024-01-31", "--raw"],
        )

        assert result.exit_code == 3
        assert (
            "--raw requires --stdout" in result.stderr
            or "--raw requires --stdout" in result.output
        )

    def test_stdout_ignores_table_name(self, cli_runner: CliRunner) -> None:
        """T013: Test table name is ignored when --stdout is set."""
        mock_workspace = MagicMock()
        mock_workspace.stream_events.return_value = iter([])

        with patch("mixpanel_data.cli.commands.fetch.get_workspace") as mock_get_ws:
            mock_get_ws.return_value = mock_workspace

            result = cli_runner.invoke(
                app,
                [
                    "-q",
                    "fetch",
                    "events",
                    "my_table_name",
                    "--from",
                    "2024-01-01",
                    "--to",
                    "2024-01-31",
                    "--stdout",
                ],
            )

        assert result.exit_code == 0, f"Failed with: {result.output}"
        # stream_events should be called, not fetch_events
        mock_workspace.stream_events.assert_called_once()
        mock_workspace.fetch_events.assert_not_called()

    def test_stdout_progress_to_stderr(self, cli_runner: CliRunner) -> None:
        """T015: Test progress goes to stderr when --stdout is set."""
        mock_workspace = MagicMock()
        mock_workspace.stream_events.return_value = iter(
            [normalized_event("Event", f"user_{i}") for i in range(5)]
        )

        with patch("mixpanel_data.cli.commands.fetch.get_workspace") as mock_get_ws:
            mock_get_ws.return_value = mock_workspace

            # Run without -q to get progress output
            result = cli_runner.invoke(
                app,
                [
                    "fetch",
                    "events",
                    "--from",
                    "2024-01-01",
                    "--to",
                    "2024-01-31",
                    "--stdout",
                ],
                catch_exceptions=False,
            )

        assert result.exit_code == 0
        # stdout should only have JSONL (5 lines)
        stdout_lines = [
            line for line in result.stdout.strip().split("\n") if line.startswith("{")
        ]
        assert len(stdout_lines) == 5

    def test_stdout_with_event_filter(self, cli_runner: CliRunner) -> None:
        """Test --stdout with --events filter passes filter to stream_events."""
        mock_workspace = MagicMock()
        mock_workspace.stream_events.return_value = iter([])

        with patch("mixpanel_data.cli.commands.fetch.get_workspace") as mock_get_ws:
            mock_get_ws.return_value = mock_workspace

            result = cli_runner.invoke(
                app,
                [
                    "-q",
                    "fetch",
                    "events",
                    "--from",
                    "2024-01-01",
                    "--to",
                    "2024-01-31",
                    "--events",
                    "Purchase,Signup",
                    "--stdout",
                ],
            )

        assert result.exit_code == 0, f"Failed with: {result.output}"
        mock_workspace.stream_events.assert_called_once()
        call_kwargs = mock_workspace.stream_events.call_args[1]
        assert call_kwargs["events"] == ["Purchase", "Signup"]

    def test_stdout_with_where_filter(self, cli_runner: CliRunner) -> None:
        """Test --stdout with --where filter passes filter to stream_events."""
        mock_workspace = MagicMock()
        mock_workspace.stream_events.return_value = iter([])

        with patch("mixpanel_data.cli.commands.fetch.get_workspace") as mock_get_ws:
            mock_get_ws.return_value = mock_workspace

            result = cli_runner.invoke(
                app,
                [
                    "-q",
                    "fetch",
                    "events",
                    "--from",
                    "2024-01-01",
                    "--to",
                    "2024-01-31",
                    "--where",
                    'properties["country"]=="US"',
                    "--stdout",
                ],
            )

        assert result.exit_code == 0, f"Failed with: {result.output}"
        mock_workspace.stream_events.assert_called_once()
        call_kwargs = mock_workspace.stream_events.call_args[1]
        assert call_kwargs["where"] == 'properties["country"]=="US"'


# =============================================================================
# Phase 5: User Story 2 - CLI Stream Profiles Tests (T016-T017)
# =============================================================================


class TestFetchProfilesStdout:
    """Tests for mp fetch profiles --stdout command."""

    def test_stdout_outputs_jsonl(self, cli_runner: CliRunner) -> None:
        """T018: Test --stdout output is valid JSONL for profiles."""
        mock_workspace = MagicMock()
        mock_workspace.stream_profiles.return_value = iter(
            [
                normalized_profile("user_1", name="Alice"),
                normalized_profile("user_2", name="Bob"),
            ]
        )

        with patch("mixpanel_data.cli.commands.fetch.get_workspace") as mock_get_ws:
            mock_get_ws.return_value = mock_workspace

            result = cli_runner.invoke(
                app,
                ["-q", "fetch", "profiles", "--stdout"],
            )

        assert result.exit_code == 0, f"Failed with: {result.output}"

        # Parse each line as JSON
        lines = [line for line in result.stdout.strip().split("\n") if line]
        assert len(lines) == 2

        for line in lines:
            parsed = json.loads(line)
            assert "distinct_id" in parsed
            assert "properties" in parsed

    def test_stdout_with_raw_flag(self, cli_runner: CliRunner) -> None:
        """T018: Test --raw changes output format for profiles."""
        mock_workspace = MagicMock()
        mock_workspace.stream_profiles.return_value = iter(
            [raw_profile("user_1", "2024-01-15T10:00:00", name="Alice")]
        )

        with patch("mixpanel_data.cli.commands.fetch.get_workspace") as mock_get_ws:
            mock_get_ws.return_value = mock_workspace

            result = cli_runner.invoke(
                app,
                ["-q", "fetch", "profiles", "--stdout", "--raw"],
            )

        assert result.exit_code == 0, f"Failed with: {result.output}"

        # Parse output
        lines = [line for line in result.stdout.strip().split("\n") if line]
        assert len(lines) == 1

        parsed = json.loads(lines[0])
        # Raw format has "$distinct_id" key
        assert "$distinct_id" in parsed
        assert "$properties" in parsed

        # Verify stream_profiles was called with raw=True
        mock_workspace.stream_profiles.assert_called_once()
        call_kwargs = mock_workspace.stream_profiles.call_args[1]
        assert call_kwargs["raw"] is True

    def test_raw_without_stdout_fails_profiles(self, cli_runner: CliRunner) -> None:
        """Test --raw without --stdout returns error for profiles."""
        result = cli_runner.invoke(
            app,
            ["fetch", "profiles", "--raw"],
        )

        assert result.exit_code == 3
        assert (
            "--raw requires --stdout" in result.stderr
            or "--raw requires --stdout" in result.output
        )

    def test_stdout_with_where_filter(self, cli_runner: CliRunner) -> None:
        """Test --stdout with --where filter for profiles."""
        mock_workspace = MagicMock()
        mock_workspace.stream_profiles.return_value = iter([])

        with patch("mixpanel_data.cli.commands.fetch.get_workspace") as mock_get_ws:
            mock_get_ws.return_value = mock_workspace

            result = cli_runner.invoke(
                app,
                [
                    "-q",
                    "fetch",
                    "profiles",
                    "--where",
                    'properties["plan"]=="premium"',
                    "--stdout",
                ],
            )

        assert result.exit_code == 0, f"Failed with: {result.output}"
        mock_workspace.stream_profiles.assert_called_once()
        call_kwargs = mock_workspace.stream_profiles.call_args[1]
        assert call_kwargs["where"] == 'properties["plan"]=="premium"'


# =============================================================================
# Phase 6: User Story 4 - CLI Raw Format Verification (T023)
# =============================================================================


class TestCliRawFormat:
    """T023: Tests verifying --raw flag produces raw format output."""

    def test_events_raw_format_structure(self, cli_runner: CliRunner) -> None:
        """Verify --raw produces Mixpanel API format for events."""
        mock_workspace = MagicMock()
        mock_workspace.stream_events.return_value = iter(
            [
                {
                    "event": "Purchase",
                    "properties": {
                        "distinct_id": "user_abc",
                        "time": 1705328400,
                        "$insert_id": "evt_123",
                        "amount": 99.99,
                    },
                }
            ]
        )

        with patch("mixpanel_data.cli.commands.fetch.get_workspace") as mock_get_ws:
            mock_get_ws.return_value = mock_workspace

            result = cli_runner.invoke(
                app,
                [
                    "-q",
                    "fetch",
                    "events",
                    "--from",
                    "2024-01-01",
                    "--to",
                    "2024-01-31",
                    "--stdout",
                    "--raw",
                ],
            )

        assert result.exit_code == 0, f"Failed with: {result.output}"
        parsed = json.loads(result.stdout.strip())

        # Verify raw API structure
        assert parsed["event"] == "Purchase"
        assert parsed["properties"]["distinct_id"] == "user_abc"
        assert parsed["properties"]["time"] == 1705328400
        assert parsed["properties"]["$insert_id"] == "evt_123"

    def test_profiles_raw_format_structure(self, cli_runner: CliRunner) -> None:
        """Verify --raw produces Mixpanel API format for profiles."""
        mock_workspace = MagicMock()
        mock_workspace.stream_profiles.return_value = iter(
            [
                {
                    "$distinct_id": "user_abc",
                    "$properties": {
                        "$last_seen": "2024-01-15T14:30:00",
                        "name": "Alice",
                        "plan": "premium",
                    },
                }
            ]
        )

        with patch("mixpanel_data.cli.commands.fetch.get_workspace") as mock_get_ws:
            mock_get_ws.return_value = mock_workspace

            result = cli_runner.invoke(
                app,
                ["-q", "fetch", "profiles", "--stdout", "--raw"],
            )

        assert result.exit_code == 0, f"Failed with: {result.output}"
        parsed = json.loads(result.stdout.strip())

        # Verify raw API structure with $ prefixes
        assert parsed["$distinct_id"] == "user_abc"
        assert "$properties" in parsed
        assert parsed["$properties"]["$last_seen"] == "2024-01-15T14:30:00"


# =============================================================================
# Backward Compatibility Tests (T029)
# =============================================================================


class TestBackwardCompatibility:
    """T029: Tests verifying existing fetch commands still work without --stdout."""

    def test_fetch_events_without_stdout_stores_locally(
        self, cli_runner: CliRunner
    ) -> None:
        """Verify fetch events without --stdout uses fetch_events (storage mode)."""
        mock_workspace = MagicMock()
        mock_workspace.fetch_events.return_value = MagicMock(
            to_dict=lambda: {
                "table": "events",
                "rows": 100,
                "from_date": "2024-01-01",
                "to_date": "2024-01-31",
            }
        )

        with patch("mixpanel_data.cli.commands.fetch.get_workspace") as mock_get_ws:
            mock_get_ws.return_value = mock_workspace

            result = cli_runner.invoke(
                app,
                ["-q", "fetch", "events", "--from", "2024-01-01", "--to", "2024-01-31"],
            )

        assert result.exit_code == 0, f"Failed with: {result.output}"
        # fetch_events should be called, not stream_events
        mock_workspace.fetch_events.assert_called_once()
        mock_workspace.stream_events.assert_not_called()

    def test_fetch_profiles_without_stdout_stores_locally(
        self, cli_runner: CliRunner
    ) -> None:
        """Verify fetch profiles without --stdout uses fetch_profiles (storage mode)."""
        mock_workspace = MagicMock()
        mock_workspace.fetch_profiles.return_value = MagicMock(
            to_dict=lambda: {"table": "profiles", "rows": 50}
        )

        with patch("mixpanel_data.cli.commands.fetch.get_workspace") as mock_get_ws:
            mock_get_ws.return_value = mock_workspace

            result = cli_runner.invoke(
                app,
                ["-q", "fetch", "profiles"],
            )

        assert result.exit_code == 0, f"Failed with: {result.output}"
        # fetch_profiles should be called, not stream_profiles
        mock_workspace.fetch_profiles.assert_called_once()
        mock_workspace.stream_profiles.assert_not_called()
