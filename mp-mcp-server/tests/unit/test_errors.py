"""Tests for error handling and exception conversion.

These tests verify that mixpanel_data exceptions are properly converted
to FastMCP ToolError with appropriate messages and details.
"""

import json

import pytest

from mixpanel_data.exceptions import (
    AccountExistsError,
    AccountNotFoundError,
    AuthenticationError,
    ConfigError,
    DatabaseLockedError,
    DatabaseNotFoundError,
    DateRangeTooLargeError,
    EventNotFoundError,
    JQLSyntaxError,
    MixpanelDataError,
    QueryError,
    RateLimitError,
    ServerError,
    TableExistsError,
    TableNotFoundError,
)


class TestHandleErrors:
    """Tests for the handle_errors decorator."""

    def test_authentication_error_conversion(self) -> None:
        """AuthenticationError should convert to ToolError with message."""
        from fastmcp.exceptions import ToolError

        from mp_mcp_server.errors import handle_errors

        @handle_errors
        def failing_func() -> None:
            raise AuthenticationError("Invalid credentials")

        with pytest.raises(ToolError) as exc_info:
            failing_func()

        assert "authentication" in str(exc_info.value).lower()
        assert "Invalid credentials" in str(exc_info.value)

    def test_rate_limit_error_with_retry_after(self) -> None:
        """RateLimitError should include retry_after in error details."""
        from fastmcp.exceptions import ToolError

        from mp_mcp_server.errors import handle_errors

        @handle_errors
        def failing_func() -> None:
            raise RateLimitError("Rate limited", retry_after=30)

        with pytest.raises(ToolError) as exc_info:
            failing_func()

        error = exc_info.value
        assert "30" in str(error)
        assert "retry" in str(error).lower()

    def test_table_exists_error_conversion(self) -> None:
        """TableExistsError should convert to ToolError with table name."""
        from fastmcp.exceptions import ToolError

        from mp_mcp_server.errors import handle_errors

        @handle_errors
        def failing_func() -> None:
            raise TableExistsError("events_jan")

        with pytest.raises(ToolError) as exc_info:
            failing_func()

        assert "events_jan" in str(exc_info.value)
        assert "exists" in str(exc_info.value).lower()

    def test_table_not_found_error_conversion(self) -> None:
        """TableNotFoundError should convert to ToolError with table name."""
        from fastmcp.exceptions import ToolError

        from mp_mcp_server.errors import handle_errors

        @handle_errors
        def failing_func() -> None:
            raise TableNotFoundError("nonexistent")

        with pytest.raises(ToolError) as exc_info:
            failing_func()

        assert "nonexistent" in str(exc_info.value)
        assert "not found" in str(exc_info.value).lower()

    def test_query_error_conversion(self) -> None:
        """QueryError should convert to ToolError with query context."""
        from fastmcp.exceptions import ToolError

        from mp_mcp_server.errors import handle_errors

        @handle_errors
        def failing_func() -> None:
            raise QueryError("Invalid SQL syntax")

        with pytest.raises(ToolError) as exc_info:
            failing_func()

        assert "Invalid SQL syntax" in str(exc_info.value)

    def test_config_error_conversion(self) -> None:
        """ConfigError should convert to ToolError with config details."""
        from fastmcp.exceptions import ToolError

        from mp_mcp_server.errors import handle_errors

        @handle_errors
        def failing_func() -> None:
            raise ConfigError("Missing project_id")

        with pytest.raises(ToolError) as exc_info:
            failing_func()

        assert "Missing project_id" in str(exc_info.value)

    def test_generic_mixpanel_data_error_conversion(self) -> None:
        """Generic MixpanelDataError should convert to ToolError."""
        from fastmcp.exceptions import ToolError

        from mp_mcp_server.errors import handle_errors

        @handle_errors
        def failing_func() -> None:
            raise MixpanelDataError("Something went wrong")

        with pytest.raises(ToolError) as exc_info:
            failing_func()

        assert "Something went wrong" in str(exc_info.value)

    def test_successful_function_returns_value(self) -> None:
        """handle_errors should not interfere with successful function calls."""
        from mp_mcp_server.errors import handle_errors

        @handle_errors
        def successful_func() -> str:
            return "success"

        result = successful_func()
        assert result == "success"

    def test_non_mixpanel_error_wrapped_in_tool_error(self) -> None:
        """Non-MixpanelDataError exceptions should be wrapped in ToolError."""
        from fastmcp.exceptions import ToolError

        from mp_mcp_server.errors import handle_errors

        @handle_errors
        def failing_func() -> None:
            raise ValueError("Not a Mixpanel error")

        with pytest.raises(ToolError) as exc_info:
            failing_func()

        error_msg = str(exc_info.value)
        assert "ValueError" in error_msg
        assert "Not a Mixpanel error" in error_msg
        assert "Unexpected error" in error_msg

    def test_jql_syntax_error_includes_script_context(self) -> None:
        """JQLSyntaxError should include script context and line info."""
        from fastmcp.exceptions import ToolError

        from mp_mcp_server.errors import handle_errors

        # JQLSyntaxError takes a raw_error string and parses it
        raw_error = """ReferenceError: x is not defined
    return x;
           ^
    at main:1:12"""

        @handle_errors
        def failing_func() -> None:
            raise JQLSyntaxError(
                raw_error,
                script="function main() { return x; }",
            )

        with pytest.raises(ToolError) as exc_info:
            failing_func()

        error_msg = str(exc_info.value)
        assert "JQL script error" in error_msg
        assert "ReferenceError" in error_msg
        # Verify JSON details block is present
        assert "Error Details:" in error_msg
        assert '"code"' in error_msg

    def test_server_error_includes_status_code(self) -> None:
        """ServerError should include status code and transient hint."""
        from fastmcp.exceptions import ToolError

        from mp_mcp_server.errors import handle_errors

        @handle_errors
        def failing_func() -> None:
            raise ServerError("Internal server error", status_code=500)

        with pytest.raises(ToolError) as exc_info:
            failing_func()

        error_msg = str(exc_info.value)
        assert "500" in error_msg
        assert "transient" in error_msg.lower()

    def test_event_not_found_includes_similar_events(self) -> None:
        """EventNotFoundError should include similar event suggestions."""
        from fastmcp.exceptions import ToolError

        from mp_mcp_server.errors import handle_errors

        @handle_errors
        def failing_func() -> None:
            raise EventNotFoundError(
                "sign_up", similar_events=["signup", "user_signup", "sign-up"]
            )

        with pytest.raises(ToolError) as exc_info:
            failing_func()

        error_msg = str(exc_info.value)
        assert "sign_up" in error_msg
        assert "signup" in error_msg
        assert "Did you mean" in error_msg

    def test_date_range_too_large_includes_range_details(self) -> None:
        """DateRangeTooLargeError should include date range and max days."""
        from fastmcp.exceptions import ToolError

        from mp_mcp_server.errors import handle_errors

        @handle_errors
        def failing_func() -> None:
            raise DateRangeTooLargeError(
                from_date="2024-01-01",
                to_date="2024-06-01",
                days_requested=152,
                max_days=100,
            )

        with pytest.raises(ToolError) as exc_info:
            failing_func()

        error_msg = str(exc_info.value)
        assert "152" in error_msg
        assert "100" in error_msg
        assert "Maximum date range" in error_msg

    def test_database_locked_includes_pid(self) -> None:
        """DatabaseLockedError should include holding process ID if available."""
        from fastmcp.exceptions import ToolError

        from mp_mcp_server.errors import handle_errors

        @handle_errors
        def failing_func() -> None:
            raise DatabaseLockedError("/path/to/db.duckdb", holding_pid=12345)

        with pytest.raises(ToolError) as exc_info:
            failing_func()

        error_msg = str(exc_info.value)
        assert "12345" in error_msg
        assert "locked" in error_msg.lower()

    def test_database_not_found_includes_suggestion(self) -> None:
        """DatabaseNotFoundError should suggest fetching data first."""
        from fastmcp.exceptions import ToolError

        from mp_mcp_server.errors import handle_errors

        @handle_errors
        def failing_func() -> None:
            raise DatabaseNotFoundError("/path/to/db.duckdb")

        with pytest.raises(ToolError) as exc_info:
            failing_func()

        error_msg = str(exc_info.value)
        assert "fetch_events" in error_msg or "fetch_profiles" in error_msg

    def test_account_not_found_includes_available_accounts(self) -> None:
        """AccountNotFoundError should list available accounts."""
        from fastmcp.exceptions import ToolError

        from mp_mcp_server.errors import handle_errors

        @handle_errors
        def failing_func() -> None:
            raise AccountNotFoundError(
                "production", available_accounts=["dev", "staging", "prod"]
            )

        with pytest.raises(ToolError) as exc_info:
            failing_func()

        error_msg = str(exc_info.value)
        assert "production" in error_msg
        assert "dev" in error_msg
        assert "staging" in error_msg

    def test_account_exists_error_conversion(self) -> None:
        """AccountExistsError should convert to ToolError with account name."""
        from fastmcp.exceptions import ToolError

        from mp_mcp_server.errors import handle_errors

        @handle_errors
        def failing_func() -> None:
            raise AccountExistsError("production")

        with pytest.raises(ToolError) as exc_info:
            failing_func()

        error_msg = str(exc_info.value)
        assert "production" in error_msg
        assert "different" in error_msg.lower() or "delete" in error_msg.lower()

    def test_error_contains_json_details_block(self) -> None:
        """All errors should contain a JSON details block for agent parsing."""
        from fastmcp.exceptions import ToolError

        from mp_mcp_server.errors import handle_errors

        @handle_errors
        def failing_func() -> None:
            raise RateLimitError("Rate limited", retry_after=60)

        with pytest.raises(ToolError) as exc_info:
            failing_func()

        error_msg = str(exc_info.value)
        # Find the JSON block
        assert "Error Details:" in error_msg
        json_start = error_msg.find("{")
        json_end = error_msg.rfind("}") + 1
        assert json_start > 0
        assert json_end > json_start

        # Verify it's valid JSON
        json_block = error_msg[json_start:json_end]
        details = json.loads(json_block)
        assert "code" in details
        assert details["code"] == "RATE_LIMITED"

    def test_rate_limit_error_without_retry_after(self) -> None:
        """RateLimitError without retry_after shows generic wait message."""
        from fastmcp.exceptions import ToolError

        from mp_mcp_server.errors import handle_errors

        @handle_errors
        def failing_func() -> None:
            raise RateLimitError("Rate limited")

        with pytest.raises(ToolError) as exc_info:
            failing_func()

        error_msg = str(exc_info.value)
        assert "Wait before retrying" in error_msg

    def test_database_locked_without_pid(self) -> None:
        """DatabaseLockedError without holding_pid omits PID info."""
        from fastmcp.exceptions import ToolError

        from mp_mcp_server.errors import handle_errors

        @handle_errors
        def failing_func() -> None:
            raise DatabaseLockedError("/path/to/db.duckdb")

        with pytest.raises(ToolError) as exc_info:
            failing_func()

        error_msg = str(exc_info.value)
        assert "locked" in error_msg.lower()
        # Should NOT have a specific PID message
        assert "Database locked by process" not in error_msg

    def test_account_not_found_without_available_accounts(self) -> None:
        """AccountNotFoundError without available_accounts omits list."""
        from fastmcp.exceptions import ToolError

        from mp_mcp_server.errors import handle_errors

        @handle_errors
        def failing_func() -> None:
            raise AccountNotFoundError("production")

        with pytest.raises(ToolError) as exc_info:
            failing_func()

        error_msg = str(exc_info.value)
        assert "production" in error_msg
        # Should NOT have an "Available accounts:" line
        assert "Available accounts" not in error_msg


class TestFormatRichError:
    """Tests for the format_rich_error helper function."""

    def test_format_includes_summary(self) -> None:
        """format_rich_error should include the summary line."""
        from mp_mcp_server.errors import format_rich_error

        error = MixpanelDataError("Test error", code="TEST_ERROR")
        result = format_rich_error("Summary message.", error)

        assert result.startswith("Summary message.")

    def test_format_includes_json_details(self) -> None:
        """format_rich_error should include JSON-parseable details."""
        from mp_mcp_server.errors import format_rich_error

        error = MixpanelDataError(
            "Test error", code="TEST_ERROR", details={"key": "value"}
        )
        result = format_rich_error("Summary.", error)

        assert "Error Details:" in result
        # Find and parse the JSON block
        json_start = result.find("{")
        json_end = result.rfind("}") + 1
        json_block = result[json_start:json_end]
        details = json.loads(json_block)
        assert details["code"] == "TEST_ERROR"
        assert details["details"]["key"] == "value"

    def test_format_includes_suggestions(self) -> None:
        """format_rich_error should include suggestions when provided."""
        from mp_mcp_server.errors import format_rich_error

        error = MixpanelDataError("Test error")
        suggestions = ["Try this", "Or try that"]
        result = format_rich_error("Summary.", error, suggestions)

        assert "Suggestions:" in result
        assert "- Try this" in result
        assert "- Or try that" in result

    def test_format_without_suggestions(self) -> None:
        """format_rich_error should work without suggestions."""
        from mp_mcp_server.errors import format_rich_error

        error = MixpanelDataError("Test error")
        result = format_rich_error("Summary.", error)

        assert "Suggestions:" not in result
