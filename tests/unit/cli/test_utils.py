"""Unit tests for CLI utilities."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import click.exceptions
import pytest
import typer

from mixpanel_data.cli.utils import (
    ExitCode,
    _apply_jq_filter,
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
    DatabaseLockedError,
    DateRangeTooLargeError,
    JQLSyntaxError,
    MixpanelDataError,
    QueryError,
    RateLimitError,
    ServerError,
    TableExistsError,
    TableNotFoundError,
)


class TestExitCode:
    """Tests for ExitCode enum."""

    def test_success_is_zero(self) -> None:
        """Test that SUCCESS is 0."""
        assert ExitCode.SUCCESS.value == 0

    def test_general_error_is_one(self) -> None:
        """Test that GENERAL_ERROR is 1."""
        assert ExitCode.GENERAL_ERROR.value == 1

    def test_auth_error_is_two(self) -> None:
        """Test that AUTH_ERROR is 2."""
        assert ExitCode.AUTH_ERROR.value == 2

    def test_invalid_args_is_three(self) -> None:
        """Test that INVALID_ARGS is 3."""
        assert ExitCode.INVALID_ARGS.value == 3

    def test_not_found_is_four(self) -> None:
        """Test that NOT_FOUND is 4."""
        assert ExitCode.NOT_FOUND.value == 4

    def test_rate_limit_is_five(self) -> None:
        """Test that RATE_LIMIT is 5."""
        assert ExitCode.RATE_LIMIT.value == 5

    def test_interrupted_is_130(self) -> None:
        """Test that INTERRUPTED is 130."""
        assert ExitCode.INTERRUPTED.value == 130


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

    def test_jql_syntax_error_exits_with_code_3(self) -> None:
        """Test JQLSyntaxError maps to exit code 3 (INVALID_ARGS)."""

        @handle_errors
        def jql_fail() -> None:
            raise JQLSyntaxError(
                raw_error="TypeError: undefined is not a function",
                script="function main() { return Events().foo(); }",
            )

        with pytest.raises(click.exceptions.Exit) as exc:
            jql_fail()
        assert exc.value.exit_code == ExitCode.INVALID_ARGS

    def test_jql_syntax_error_shows_error_details(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Test JQLSyntaxError displays rich error context."""

        @handle_errors
        def jql_fail() -> None:
            raise JQLSyntaxError(
                raw_error="Uncaught exception TypeError: foo is not a function\n  .foo()\n  ^",
                script="function main() { return Events().foo(); }",
            )

        with pytest.raises(click.exceptions.Exit):
            jql_fail()

        captured = capsys.readouterr()
        # Should show error type and message
        assert "TypeError" in captured.err
        # Should show the script (truncated if long)
        assert "Events()" in captured.err

    def test_server_error_exits_with_code_1(self) -> None:
        """Test ServerError maps to exit code 1 (GENERAL_ERROR)."""

        @handle_errors
        def server_fail() -> None:
            raise ServerError(
                "Internal server error",
                status_code=500,
                response_body={"error": "Service temporarily unavailable"},
            )

        with pytest.raises(click.exceptions.Exit) as exc:
            server_fail()
        assert exc.value.exit_code == ExitCode.GENERAL_ERROR

    def test_server_error_shows_status_code(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Test ServerError displays status code and response."""

        @handle_errors
        def server_fail() -> None:
            raise ServerError(
                "Service unavailable",
                status_code=503,
                response_body={"error": "Database connection failed"},
                request_url="https://api.mixpanel.com/query/segmentation",
            )

        with pytest.raises(click.exceptions.Exit):
            server_fail()

        captured = capsys.readouterr()
        # Should show status code
        assert "503" in captured.err
        # Should show API error from response
        assert "Database connection failed" in captured.err
        # Should show endpoint
        assert "segmentation" in captured.err

    def test_database_locked_error_shows_pid(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Test DatabaseLockedError displays holding PID when available."""

        @handle_errors
        def db_locked() -> None:
            raise DatabaseLockedError(
                db_path="/home/user/.mp/mixpanel.db",
                holding_pid=12345,
            )

        with pytest.raises(click.exceptions.Exit):
            db_locked()

        captured = capsys.readouterr()
        assert "12345" in captured.err
        assert "PID" in captured.err

    def test_date_range_error_shows_details(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Test DateRangeTooLargeError displays date range details."""

        @handle_errors
        def date_range_fail() -> None:
            raise DateRangeTooLargeError(
                from_date="2024-01-01",
                to_date="2024-06-30",
                days_requested=181,
                max_days=100,
            )

        with pytest.raises(click.exceptions.Exit):
            date_range_fail()

        captured = capsys.readouterr()
        # Should show requested dates
        assert "2024-01-01" in captured.err
        assert "2024-06-30" in captured.err
        # Should show days count
        assert "181" in captured.err
        # Should show max allowed
        assert "100" in captured.err

    def test_auth_error_shows_endpoint(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Test AuthenticationError displays endpoint context."""

        @handle_errors
        def auth_fail() -> None:
            raise AuthenticationError(
                "Invalid API key",
                status_code=401,
                request_url="https://api.mixpanel.com/query/segmentation?project_id=123",
                response_body={"error": "Unauthorized"},
            )

        with pytest.raises(click.exceptions.Exit):
            auth_fail()

        captured = capsys.readouterr()
        # Should show endpoint (without sensitive params)
        assert "segmentation" in captured.err

    def test_query_error_shows_response_body(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Test QueryError displays response body with API error message."""

        @handle_errors
        def query_fail() -> None:
            raise QueryError(
                "Query failed",
                status_code=400,
                response_body={"error": "Invalid event name: 'NonExistent'"},
                request_params={"event": "NonExistent"},
            )

        with pytest.raises(click.exceptions.Exit):
            query_fail()

        captured = capsys.readouterr()
        # Should show the API error from response body
        assert "Invalid event name" in captured.err
        # Should show request params
        assert "NonExistent" in captured.err


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

            MockWorkspace.assert_called_once_with(account=None, read_only=False)
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

            MockWorkspace.assert_called_once_with(account="staging", read_only=False)


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

    def test_explicit_format_parameter(self) -> None:
        """Test that explicit format parameter works."""
        ctx = MagicMock(spec=typer.Context)
        ctx.obj = {}  # No format in context

        with patch("mixpanel_data.cli.utils.console") as mock_console:
            output_result(ctx, {"key": "value"}, format="json")

            mock_console.print.assert_called_once()
            call_args = mock_console.print.call_args
            assert '"key"' in call_args[0][0]

    def test_explicit_format_overrides_context(self) -> None:
        """Test that explicit format parameter takes precedence over ctx.obj."""
        ctx = MagicMock(spec=typer.Context)
        ctx.obj = {"format": "table"}  # Context says table

        with patch("mixpanel_data.cli.utils.console") as mock_console:
            output_result(ctx, {"key": "value"}, format="json")  # Explicit json

            mock_console.print.assert_called_once()
            call_args = mock_console.print.call_args
            # Should be JSON, not table
            assert '"key"' in call_args[0][0]
            assert '"value"' in call_args[0][0]

    def test_defaults_to_json_when_no_format_specified(self) -> None:
        """Test that output defaults to JSON when neither param nor ctx.obj provided."""
        ctx = MagicMock(spec=typer.Context)
        ctx.obj = {}  # No format in context

        with patch("mixpanel_data.cli.utils.console") as mock_console:
            output_result(ctx, {"key": "value"})  # No explicit format

            mock_console.print.assert_called_once()
            call_args = mock_console.print.call_args
            # Should default to JSON
            assert '"key"' in call_args[0][0]

    def test_jq_filter_with_json_format(self) -> None:
        """Test that jq_filter is applied to JSON output (T011)."""
        ctx = MagicMock(spec=typer.Context)
        ctx.obj = {"format": "json"}

        with patch("mixpanel_data.cli.utils.console") as mock_console:
            data = {"name": "test", "count": 42}
            output_result(ctx, data, format="json", jq_filter=".name")

            mock_console.print.assert_called_once()
            call_args = mock_console.print.call_args
            output = call_args[0][0]
            # Should only have the name field extracted
            assert output.strip() == '"test"'

    def test_jq_filter_with_jsonl_format(self) -> None:
        """Test that jq_filter is applied to JSONL output."""
        ctx = MagicMock(spec=typer.Context)
        ctx.obj = {"format": "jsonl"}

        with patch("mixpanel_data.cli.utils.console") as mock_console:
            data = [{"name": "a"}, {"name": "b"}]
            output_result(ctx, data, format="jsonl", jq_filter=".[0]")

            mock_console.print.assert_called_once()
            call_args = mock_console.print.call_args
            output = call_args[0][0]
            # Should extract first element
            parsed = json.loads(output.strip())
            assert parsed == {"name": "a"}


class TestApplyJqFilter:
    """Tests for _apply_jq_filter function (User Story 1)."""

    def test_simple_field_extraction(self) -> None:
        """Test extracting a single field from dict (T006)."""
        json_str = '{"name": "test", "count": 42}'
        result = _apply_jq_filter(json_str, ".name")
        assert result == ["test"]

    def test_nested_field_extraction(self) -> None:
        """Test extracting nested fields."""
        json_str = '{"user": {"name": "alice", "id": 1}}'
        result = _apply_jq_filter(json_str, ".user.name")
        assert result == ["alice"]

    def test_list_iteration(self) -> None:
        """Test iterating over list elements (T007)."""
        json_str = '[{"name": "a"}, {"name": "b"}, {"name": "c"}]'
        result = _apply_jq_filter(json_str, ".[].name")
        # Multiple results returned as list
        assert result == ["a", "b", "c"]

    def test_list_indexing(self) -> None:
        """Test accessing list by index."""
        json_str = '["first", "second", "third"]'
        result = _apply_jq_filter(json_str, ".[1]")
        assert result == ["second"]

    def test_select_filter(self) -> None:
        """Test filtering with select() (T008)."""
        json_str = '[{"name": "a", "active": true}, {"name": "b", "active": false}]'
        result = _apply_jq_filter(json_str, ".[] | select(.active)")
        # Should only return the active item
        assert result == [{"name": "a", "active": True}]

    def test_select_filter_multiple_results(self) -> None:
        """Test select() returning multiple results."""
        json_str = '[{"v": 1}, {"v": 5}, {"v": 10}, {"v": 15}]'
        result = _apply_jq_filter(json_str, ".[] | select(.v > 3)")
        assert result == [{"v": 5}, {"v": 10}, {"v": 15}]

    def test_length_filter(self) -> None:
        """Test length filter (T009)."""
        json_str = '["a", "b", "c", "d", "e"]'
        result = _apply_jq_filter(json_str, "length")
        assert result == [5]

    def test_length_filter_on_object(self) -> None:
        """Test length filter on object (counts keys)."""
        json_str = '{"a": 1, "b": 2, "c": 3}'
        result = _apply_jq_filter(json_str, "length")
        assert result == [3]

    def test_single_result_returns_list(self) -> None:
        """Test that single result is returned as single-element list."""
        json_str = '{"name": "solo"}'
        result = _apply_jq_filter(json_str, ".name")
        # Results always returned as list, caller formats
        assert result == ["solo"]

    def test_multiple_results_as_list(self) -> None:
        """Test that multiple results are returned as list."""
        json_str = '[{"x": 1}, {"x": 2}, {"x": 3}]'
        result = _apply_jq_filter(json_str, ".[].x")
        assert result == [1, 2, 3]

    def test_identity_filter(self) -> None:
        """Test identity filter '.' returns input unchanged."""
        json_str = '{"key": "value"}'
        result = _apply_jq_filter(json_str, ".")
        assert result == [{"key": "value"}]

    def test_keys_filter(self) -> None:
        """Test keys filter extracts object keys."""
        json_str = '{"b": 1, "a": 2, "c": 3}'
        result = _apply_jq_filter(json_str, "keys")
        # Result is list containing one element (the keys array)
        assert len(result) == 1
        assert set(result[0]) == {"a", "b", "c"}

    def test_map_filter(self) -> None:
        """Test map transformation."""
        json_str = "[1, 2, 3]"
        result = _apply_jq_filter(json_str, "map(. * 2)")
        # map() returns single array result
        assert result == [[2, 4, 6]]

    def test_slice_filter(self) -> None:
        """Test array slicing."""
        json_str = "[0, 1, 2, 3, 4, 5]"
        result = _apply_jq_filter(json_str, ".[:3]")
        # slice returns single array result
        assert result == [[0, 1, 2]]


class TestApplyJqFilterErrors:
    """Tests for _apply_jq_filter error handling (User Story 2)."""

    def test_invalid_json_input_raises_exit(self) -> None:
        """Test that invalid JSON input raises typer.Exit with clean message."""
        invalid_json = "not valid json {"
        with pytest.raises(click.exceptions.Exit) as exc:
            _apply_jq_filter(invalid_json, ".")
        assert exc.value.exit_code == ExitCode.INVALID_ARGS

    def test_invalid_json_error_message(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Test that invalid JSON error message is helpful."""
        invalid_json = '{"unclosed": '
        with pytest.raises(click.exceptions.Exit):
            _apply_jq_filter(invalid_json, ".")

        captured = capsys.readouterr()
        assert "invalid json" in captured.err.lower()

    def test_invalid_syntax_raises_exit(self) -> None:
        """Test that invalid jq syntax raises typer.Exit (T016)."""
        json_str = '{"name": "test"}'
        with pytest.raises(click.exceptions.Exit) as exc:
            _apply_jq_filter(json_str, ".name |")  # Incomplete pipe
        assert exc.value.exit_code == ExitCode.INVALID_ARGS

    def test_error_message_contains_jq(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Test that error message contains 'jq' for context (T017)."""
        json_str = '{"name": "test"}'
        with pytest.raises(click.exceptions.Exit):
            _apply_jq_filter(json_str, ".name |")

        captured = capsys.readouterr()
        assert "jq" in captured.err.lower()

    def test_invalid_syntax_exits_with_invalid_args(self) -> None:
        """Test that syntax error exits with ExitCode.INVALID_ARGS (T018)."""
        json_str = "[1, 2, 3]"
        with pytest.raises(click.exceptions.Exit) as exc:
            _apply_jq_filter(json_str, ".[")  # Unclosed bracket
        assert exc.value.exit_code == ExitCode.INVALID_ARGS

    def test_unknown_function_error(self) -> None:
        """Test error for unknown jq function."""
        json_str = '{"x": 1}'
        with pytest.raises(click.exceptions.Exit) as exc:
            _apply_jq_filter(json_str, "nonexistent_function")
        assert exc.value.exit_code == ExitCode.INVALID_ARGS


class TestOutputResultFormatValidation:
    """Tests for output_result jq_filter format validation (User Story 3)."""

    def test_jq_filter_rejected_with_table_format(self) -> None:
        """Test that jq_filter with table format raises Exit (T022)."""
        ctx = MagicMock(spec=typer.Context)
        ctx.obj = {}

        with pytest.raises(click.exceptions.Exit) as exc:
            output_result(ctx, {"name": "test"}, format="table", jq_filter=".")
        assert exc.value.exit_code == ExitCode.INVALID_ARGS

    def test_jq_filter_rejected_with_csv_format(self) -> None:
        """Test that jq_filter with csv format raises Exit (T023)."""
        ctx = MagicMock(spec=typer.Context)
        ctx.obj = {}

        with pytest.raises(click.exceptions.Exit) as exc:
            output_result(ctx, [{"name": "test"}], format="csv", jq_filter=".")
        assert exc.value.exit_code == ExitCode.INVALID_ARGS

    def test_jq_filter_rejected_with_plain_format(self) -> None:
        """Test that jq_filter with plain format raises Exit (T024)."""
        ctx = MagicMock(spec=typer.Context)
        ctx.obj = {}

        with pytest.raises(click.exceptions.Exit) as exc:
            output_result(ctx, ["item1"], format="plain", jq_filter=".")
        assert exc.value.exit_code == ExitCode.INVALID_ARGS

    def test_error_message_mentions_json_jsonl(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Test that error message mentions json/jsonl requirement (T025)."""
        ctx = MagicMock(spec=typer.Context)
        ctx.obj = {}

        with pytest.raises(click.exceptions.Exit):
            output_result(ctx, {"x": 1}, format="table", jq_filter=".")

        captured = capsys.readouterr()
        # Error should mention that json/jsonl is required
        assert "json" in captured.err.lower()

    def test_jq_filter_allowed_with_json_format(self) -> None:
        """Test that jq_filter works with json format."""
        ctx = MagicMock(spec=typer.Context)
        ctx.obj = {}

        with patch("mixpanel_data.cli.utils.console") as mock_console:
            output_result(ctx, {"name": "test"}, format="json", jq_filter=".name")
            mock_console.print.assert_called_once()

    def test_jq_filter_allowed_with_jsonl_format(self) -> None:
        """Test that jq_filter works with jsonl format."""
        ctx = MagicMock(spec=typer.Context)
        ctx.obj = {}

        with patch("mixpanel_data.cli.utils.console") as mock_console:
            output_result(ctx, [{"a": 1}], format="jsonl", jq_filter=".[0]")
            mock_console.print.assert_called_once()

    def test_jq_filter_jsonl_outputs_per_line(self) -> None:
        """Test that jq filter with jsonl outputs each result on its own line."""
        ctx = MagicMock(spec=typer.Context)
        ctx.obj = {}

        with patch("mixpanel_data.cli.utils.console") as mock_console:
            # Filter that produces multiple results
            output_result(
                ctx, [{"x": 1}, {"x": 2}, {"x": 3}], format="jsonl", jq_filter=".[].x"
            )
            # Each result should be printed separately (3 calls for 3 results)
            assert mock_console.print.call_count == 3
            # Each call should have a single JSON value (1, 2, 3)
            calls = mock_console.print.call_args_list
            assert calls[0][0][0] == "1"
            assert calls[1][0][0] == "2"
            assert calls[2][0][0] == "3"


class TestApplyJqFilterRuntimeErrors:
    """Tests for _apply_jq_filter runtime error handling (User Story 4)."""

    def test_runtime_error_index_dict_as_array(self) -> None:
        """Test runtime error when indexing dict as array (T029)."""
        json_str = '{"name": "test"}'
        with pytest.raises(click.exceptions.Exit) as exc:
            _apply_jq_filter(json_str, ".[0]")  # Can't index dict with number
        assert exc.value.exit_code == ExitCode.INVALID_ARGS

    def test_runtime_error_message_is_helpful(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Test that runtime error message is helpful (T030)."""
        json_str = '{"name": "test"}'
        with pytest.raises(click.exceptions.Exit):
            _apply_jq_filter(json_str, ".[0]")

        captured = capsys.readouterr()
        # Error message should provide context
        assert "jq filter error" in captured.err.lower()

    def test_runtime_error_exits_with_invalid_args(self) -> None:
        """Test runtime error exits with ExitCode.INVALID_ARGS (T031)."""
        json_str = '"just a string"'
        with pytest.raises(click.exceptions.Exit) as exc:
            _apply_jq_filter(json_str, ".missing.path")  # Can't access on string
        assert exc.value.exit_code == ExitCode.INVALID_ARGS


class TestApplyJqFilterEmptyResults:
    """Tests for _apply_jq_filter empty results handling (User Story 5)."""

    def test_empty_results_return_empty_list(self) -> None:
        """Test that no matches returns empty list (T035)."""
        json_str = '[{"x": 1}, {"x": 2}, {"x": 3}]'
        result = _apply_jq_filter(json_str, ".[] | select(.x > 100)")
        assert result == []

    def test_empty_results_does_not_raise(self) -> None:
        """Test that empty results do NOT raise exception (T036)."""
        json_str = "[]"
        # This should not raise - empty input with filter = empty output
        result = _apply_jq_filter(json_str, ".[]")
        assert result == []

    def test_select_no_matches_returns_empty(self) -> None:
        """Test select with no matches returns empty list."""
        json_str = '[{"active": false}, {"active": false}]'
        result = _apply_jq_filter(json_str, ".[] | select(.active)")
        assert result == []
