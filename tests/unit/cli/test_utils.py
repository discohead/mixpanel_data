"""Unit tests for CLI utilities."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import click.exceptions
import pytest
import typer

from mixpanel_data.cli.utils import (
    ExitCode,
    get_config,
    get_workspace,
    handle_errors,
    output_result,
)
from mixpanel_data.exceptions import (
    AccountExistsError,
    AccountNotFoundError,
    AuthenticationError,
    ConfigError,
    MixpanelDataError,
    QueryError,
    RateLimitError,
    TableExistsError,
    TableNotFoundError,
)


class TestExitCode:
    """Tests for ExitCode enum."""

    def test_success_is_zero(self) -> None:
        """Test that SUCCESS is 0."""
        assert ExitCode.SUCCESS == 0

    def test_general_error_is_one(self) -> None:
        """Test that GENERAL_ERROR is 1."""
        assert ExitCode.GENERAL_ERROR == 1

    def test_auth_error_is_two(self) -> None:
        """Test that AUTH_ERROR is 2."""
        assert ExitCode.AUTH_ERROR == 2

    def test_invalid_args_is_three(self) -> None:
        """Test that INVALID_ARGS is 3."""
        assert ExitCode.INVALID_ARGS == 3

    def test_not_found_is_four(self) -> None:
        """Test that NOT_FOUND is 4."""
        assert ExitCode.NOT_FOUND == 4

    def test_rate_limit_is_five(self) -> None:
        """Test that RATE_LIMIT is 5."""
        assert ExitCode.RATE_LIMIT == 5

    def test_interrupted_is_130(self) -> None:
        """Test that INTERRUPTED is 130."""
        assert ExitCode.INTERRUPTED == 130


class TestHandleErrors:
    """Tests for handle_errors decorator."""

    def test_successful_function_passes_through(self) -> None:
        """Test that successful functions work normally."""

        @handle_errors
        def success_func() -> str:
            return "success"

        assert success_func() == "success"

    def test_authentication_error_exits_with_code_2(self) -> None:
        """Test AuthenticationError maps to exit code 2."""

        @handle_errors
        def auth_fail() -> None:
            raise AuthenticationError("Invalid credentials")

        with pytest.raises(click.exceptions.Exit) as exc:
            auth_fail()
        assert exc.value.exit_code == ExitCode.AUTH_ERROR

    def test_account_not_found_exits_with_code_4(self) -> None:
        """Test AccountNotFoundError maps to exit code 4."""

        @handle_errors
        def account_fail() -> None:
            raise AccountNotFoundError("test_account", ["production", "staging"])

        with pytest.raises(click.exceptions.Exit) as exc:
            account_fail()
        assert exc.value.exit_code == ExitCode.NOT_FOUND

    def test_account_exists_exits_with_code_1(self) -> None:
        """Test AccountExistsError maps to exit code 1."""

        @handle_errors
        def account_exists() -> None:
            raise AccountExistsError("production")

        with pytest.raises(click.exceptions.Exit) as exc:
            account_exists()
        assert exc.value.exit_code == ExitCode.GENERAL_ERROR

    def test_table_exists_exits_with_code_1(self) -> None:
        """Test TableExistsError maps to exit code 1."""

        @handle_errors
        def table_exists() -> None:
            raise TableExistsError("events")

        with pytest.raises(click.exceptions.Exit) as exc:
            table_exists()
        assert exc.value.exit_code == ExitCode.GENERAL_ERROR

    def test_table_not_found_exits_with_code_4(self) -> None:
        """Test TableNotFoundError maps to exit code 4."""

        @handle_errors
        def table_not_found() -> None:
            raise TableNotFoundError("events")

        with pytest.raises(click.exceptions.Exit) as exc:
            table_not_found()
        assert exc.value.exit_code == ExitCode.NOT_FOUND

    def test_rate_limit_exits_with_code_5(self) -> None:
        """Test RateLimitError maps to exit code 5."""

        @handle_errors
        def rate_limit() -> None:
            raise RateLimitError("Too many requests", retry_after=60)

        with pytest.raises(click.exceptions.Exit) as exc:
            rate_limit()
        assert exc.value.exit_code == ExitCode.RATE_LIMIT

    def test_query_error_exits_with_code_3(self) -> None:
        """Test QueryError maps to exit code 3."""

        @handle_errors
        def query_fail() -> None:
            raise QueryError("Invalid query", status_code=400)

        with pytest.raises(click.exceptions.Exit) as exc:
            query_fail()
        assert exc.value.exit_code == ExitCode.INVALID_ARGS

    def test_config_error_exits_with_code_1(self) -> None:
        """Test ConfigError maps to exit code 1."""

        @handle_errors
        def config_fail() -> None:
            raise ConfigError("Invalid config")

        with pytest.raises(click.exceptions.Exit) as exc:
            config_fail()
        assert exc.value.exit_code == ExitCode.GENERAL_ERROR

    def test_generic_mixpanel_error_exits_with_code_1(self) -> None:
        """Test generic MixpanelDataError maps to exit code 1."""

        @handle_errors
        def generic_fail() -> None:
            raise MixpanelDataError("Something went wrong")

        with pytest.raises(click.exceptions.Exit) as exc:
            generic_fail()
        assert exc.value.exit_code == ExitCode.GENERAL_ERROR

    def test_preserves_function_metadata(self) -> None:
        """Test that the decorator preserves function name and docstring."""

        @handle_errors
        def documented_func() -> None:
            """This is a documented function."""
            pass

        assert documented_func.__name__ == "documented_func"
        assert "documented function" in (documented_func.__doc__ or "")


class TestGetWorkspace:
    """Tests for get_workspace helper."""

    def test_creates_workspace_on_first_call(self) -> None:
        """Test that workspace is created on first call."""
        ctx = MagicMock(spec=typer.Context)
        ctx.obj = {"account": None, "workspace": None}

        with patch("mixpanel_data.workspace.Workspace") as MockWorkspace:
            mock_ws = MagicMock()
            MockWorkspace.return_value = mock_ws

            result = get_workspace(ctx)

            MockWorkspace.assert_called_once_with(account=None)
            assert result == mock_ws
            assert ctx.obj["workspace"] == mock_ws

    def test_reuses_workspace_on_subsequent_calls(self) -> None:
        """Test that workspace is reused on subsequent calls."""
        ctx = MagicMock(spec=typer.Context)
        existing_ws = MagicMock()
        ctx.obj = {"account": None, "workspace": existing_ws}

        with patch("mixpanel_data.workspace.Workspace") as MockWorkspace:
            result = get_workspace(ctx)

            MockWorkspace.assert_not_called()
            assert result == existing_ws

    def test_respects_account_option(self) -> None:
        """Test that --account option is passed to Workspace."""
        ctx = MagicMock(spec=typer.Context)
        ctx.obj = {"account": "staging", "workspace": None}

        with patch("mixpanel_data.workspace.Workspace") as MockWorkspace:
            get_workspace(ctx)

            MockWorkspace.assert_called_once_with(account="staging")


class TestGetConfig:
    """Tests for get_config helper."""

    def test_creates_config_on_first_call(self) -> None:
        """Test that ConfigManager is created on first call."""
        ctx = MagicMock(spec=typer.Context)
        ctx.obj = {"config": None}

        with patch("mixpanel_data._internal.config.ConfigManager") as MockConfig:
            mock_config = MagicMock()
            MockConfig.return_value = mock_config

            result = get_config(ctx)

            MockConfig.assert_called_once()
            assert result == mock_config
            assert ctx.obj["config"] == mock_config

    def test_reuses_config_on_subsequent_calls(self) -> None:
        """Test that ConfigManager is reused on subsequent calls."""
        ctx = MagicMock(spec=typer.Context)
        existing_config = MagicMock()
        ctx.obj = {"config": existing_config}

        with patch("mixpanel_data._internal.config.ConfigManager") as MockConfig:
            result = get_config(ctx)

            MockConfig.assert_not_called()
            assert result == existing_config


class TestOutputResult:
    """Tests for output_result helper."""

    def test_outputs_json_by_default(self) -> None:
        """Test that JSON format is used by default."""
        ctx = MagicMock(spec=typer.Context)
        ctx.obj = {"format": "json"}

        with patch("mixpanel_data.cli.utils.console") as mock_console:
            output_result(ctx, {"key": "value"})

            mock_console.print.assert_called_once()
            call_args = mock_console.print.call_args
            # First argument should be the JSON string
            assert '"key"' in call_args[0][0]
            assert '"value"' in call_args[0][0]

    def test_outputs_table_format(self) -> None:
        """Test that table format works."""
        ctx = MagicMock(spec=typer.Context)
        ctx.obj = {"format": "table"}

        with patch("mixpanel_data.cli.utils.console") as mock_console:
            output_result(ctx, [{"name": "test"}])

            mock_console.print.assert_called_once()

    def test_outputs_csv_format(self) -> None:
        """Test that CSV format works."""
        ctx = MagicMock(spec=typer.Context)
        ctx.obj = {"format": "csv"}

        with patch("mixpanel_data.cli.utils.console") as mock_console:
            output_result(ctx, [{"name": "test"}])

            mock_console.print.assert_called_once()
            call_args = mock_console.print.call_args
            assert "name" in call_args[0][0]
            assert "test" in call_args[0][0]

    def test_outputs_plain_format(self) -> None:
        """Test that plain format works."""
        ctx = MagicMock(spec=typer.Context)
        ctx.obj = {"format": "plain"}

        with patch("mixpanel_data.cli.utils.console") as mock_console:
            output_result(ctx, ["item1", "item2"])

            mock_console.print.assert_called_once()
            call_args = mock_console.print.call_args
            assert "item1" in call_args[0][0]

    def test_outputs_jsonl_format(self) -> None:
        """Test that JSONL format works."""
        ctx = MagicMock(spec=typer.Context)
        ctx.obj = {"format": "jsonl"}

        with patch("mixpanel_data.cli.utils.console") as mock_console:
            output_result(ctx, [{"a": 1}, {"b": 2}])

            mock_console.print.assert_called_once()
            call_args = mock_console.print.call_args
            output = call_args[0][0]
            # JSONL should have one object per line
            lines = output.strip().split("\n")
            assert len(lines) == 2
