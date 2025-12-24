"""Unit tests for CLI main module."""

from __future__ import annotations

import signal

import pytest
from typer.testing import CliRunner

from mixpanel_data.cli.main import _handle_interrupt, app
from mixpanel_data.cli.utils import ExitCode


@pytest.fixture
def cli_runner() -> CliRunner:
    """Create a CLI runner for testing commands."""
    return CliRunner()


class TestVersionCallback:
    """Tests for version callback."""

    def test_version_flag_shows_version(self, cli_runner: CliRunner) -> None:
        """Test that --version shows version and exits."""
        result = cli_runner.invoke(app, ["--version"])

        assert result.exit_code == 0
        assert "mp version" in result.stdout

    def test_version_flag_with_command(self, cli_runner: CliRunner) -> None:
        """Test that --version takes precedence over commands."""
        result = cli_runner.invoke(app, ["--version", "auth", "list"])

        assert result.exit_code == 0
        assert "mp version" in result.stdout


class TestInterruptHandler:
    """Tests for SIGINT (Ctrl+C) handling."""

    def test_handle_interrupt_exits_with_code_130(self) -> None:
        """Test that interrupt handler exits with code 130."""
        with pytest.raises(SystemExit) as exc_info:
            _handle_interrupt(signal.SIGINT, None)

        assert exc_info.value.code == ExitCode.INTERRUPTED

    def test_handle_interrupt_prints_message(
        self, capsys: pytest.CaptureFixture
    ) -> None:
        """Test that interrupt handler prints interrupted message."""
        with pytest.raises(SystemExit):
            _handle_interrupt(signal.SIGINT, None)

        # Rich prints to stderr
        captured = capsys.readouterr()
        assert "Interrupted" in captured.err


class TestMainCallback:
    """Tests for main callback and context setup."""

    def test_no_args_shows_help(self, cli_runner: CliRunner) -> None:
        """Test that no arguments shows help (exit code 2 per Typer convention)."""
        result = cli_runner.invoke(app, [])

        # Typer returns exit code 2 when no_args_is_help=True and no args provided
        assert result.exit_code == 2
        assert "Usage:" in result.stdout or "usage:" in result.stdout.lower()

    def test_help_flag_shows_help(self, cli_runner: CliRunner) -> None:
        """Test that --help shows help."""
        result = cli_runner.invoke(app, ["--help"])

        assert result.exit_code == 0
        assert "Mixpanel data CLI" in result.stdout
