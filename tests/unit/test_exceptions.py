"""Unit tests for mixpanel_data exception hierarchy."""

from __future__ import annotations

import json

import pytest

from mixpanel_data.exceptions import (
    AccountExistsError,
    AccountNotFoundError,
    APIError,
    AuthenticationError,
    ConfigError,
    DatabaseLockedError,
    JQLSyntaxError,
    MixpanelDataError,
    QueryError,
    RateLimitError,
    ServerError,
    TableExistsError,
    TableNotFoundError,
)


class TestMixpanelDataError:
    """Tests for the base exception class."""

    def test_basic_initialization(self) -> None:
        """Test basic exception creation."""
        exc = MixpanelDataError("Something went wrong")
        assert str(exc) == "Something went wrong"
        assert exc.message == "Something went wrong"
        assert exc.code == "UNKNOWN_ERROR"
        assert exc.details == {}

    def test_with_code_and_details(self) -> None:
        """Test exception with custom code and details."""
        exc = MixpanelDataError(
            "Test error",
            code="TEST_ERROR",
            details={"key": "value", "count": 42},
        )
        assert exc.code == "TEST_ERROR"
        assert exc.details == {"key": "value", "count": 42}

    def test_to_dict_serializable(self) -> None:
        """Test that to_dict output is JSON serializable."""
        exc = MixpanelDataError(
            "Test error",
            code="TEST_ERROR",
            details={"nested": {"data": [1, 2, 3]}},
        )
        result = exc.to_dict()

        # Verify structure
        assert result["code"] == "TEST_ERROR"
        assert result["message"] == "Test error"
        assert result["details"]["nested"]["data"] == [1, 2, 3]

        # Verify JSON serializable
        json_str = json.dumps(result)
        assert "TEST_ERROR" in json_str

    def test_repr(self) -> None:
        """Test string representation."""
        exc = MixpanelDataError("Test error", code="TEST")
        assert "MixpanelDataError" in repr(exc)
        assert "Test error" in repr(exc)
        assert "TEST" in repr(exc)


class TestConfigError:
    """Tests for configuration error classes."""

    def test_config_error_code(self) -> None:
        """ConfigError should have CONFIG_ERROR code."""
        exc = ConfigError("Config issue")
        assert exc.code == "CONFIG_ERROR"
        assert isinstance(exc, MixpanelDataError)

    def test_account_not_found_with_available(self) -> None:
        """AccountNotFoundError should list available accounts."""
        exc = AccountNotFoundError("missing", available_accounts=["a", "b", "c"])

        assert exc.code == "ACCOUNT_NOT_FOUND"
        assert exc.account_name == "missing"
        assert exc.available_accounts == ["a", "b", "c"]
        assert "missing" in str(exc)
        assert "'a'" in str(exc)
        assert "'b'" in str(exc)

    def test_account_not_found_no_available(self) -> None:
        """AccountNotFoundError with no available accounts."""
        exc = AccountNotFoundError("missing")

        assert exc.available_accounts == []
        assert "No accounts configured" in str(exc)

    def test_account_not_found_details(self) -> None:
        """AccountNotFoundError includes available_accounts in details."""
        exc = AccountNotFoundError("x", available_accounts=["y", "z"])
        details = exc.details

        assert details["account_name"] == "x"
        assert details["available_accounts"] == ["y", "z"]

    def test_account_exists_error(self) -> None:
        """AccountExistsError should have correct code and message."""
        exc = AccountExistsError("duplicate")

        assert exc.code == "ACCOUNT_EXISTS"
        assert exc.account_name == "duplicate"
        assert "duplicate" in str(exc)
        assert "already exists" in str(exc)


class TestOperationExceptions:
    """Tests for operation-related exceptions."""

    def test_authentication_error(self) -> None:
        """AuthenticationError should have AUTH_FAILED code."""
        exc = AuthenticationError("Invalid credentials")

        assert exc.code == "AUTH_FAILED"
        assert isinstance(exc, MixpanelDataError)
        assert "Invalid credentials" in str(exc)

    def test_authentication_error_default_message(self) -> None:
        """AuthenticationError default message."""
        exc = AuthenticationError()

        assert "Authentication failed" in str(exc)

    def test_rate_limit_error_with_retry(self) -> None:
        """RateLimitError should include retry_after."""
        exc = RateLimitError("Too many requests", retry_after=60)

        assert exc.code == "RATE_LIMITED"
        assert exc.retry_after == 60
        assert "60" in str(exc)
        assert exc.details["retry_after"] == 60

    def test_rate_limit_error_no_retry(self) -> None:
        """RateLimitError without retry_after."""
        exc = RateLimitError("Too many requests")

        assert exc.retry_after is None
        assert "retry_after" not in exc.details

    def test_query_error(self) -> None:
        """QueryError should have QUERY_FAILED code and inherit from APIError."""
        exc = QueryError(
            "Invalid SQL syntax",
            status_code=400,
            response_body={"error": "syntax error"},
            request_params={"query": "SELECT * FROM"},
        )

        assert exc.code == "QUERY_FAILED"
        assert exc.status_code == 400
        assert exc.request_params == {"query": "SELECT * FROM"}


class TestStorageExceptions:
    """Tests for storage-related exceptions."""

    def test_table_exists_error(self) -> None:
        """TableExistsError should have correct code and suggestion."""
        exc = TableExistsError("events")

        assert exc.code == "TABLE_EXISTS"
        assert exc.table_name == "events"
        assert "events" in str(exc)
        assert "already exists" in str(exc)
        assert "drop()" in exc.details["suggestion"]

    def test_table_not_found_error(self) -> None:
        """TableNotFoundError should have correct code."""
        exc = TableNotFoundError("missing_table")

        assert exc.code == "TABLE_NOT_FOUND"
        assert exc.table_name == "missing_table"
        assert "missing_table" in str(exc)
        assert "not found" in str(exc)

    def test_database_locked_error_basic(self) -> None:
        """DatabaseLockedError should have correct code and message."""
        exc = DatabaseLockedError("/path/to/db.duckdb")

        assert exc.code == "DATABASE_LOCKED"
        assert exc.db_path == "/path/to/db.duckdb"
        assert "/path/to/db.duckdb" in str(exc)
        assert "locked" in str(exc).lower()

    def test_database_locked_error_with_pid(self) -> None:
        """DatabaseLockedError should include holding PID when provided."""
        exc = DatabaseLockedError("/path/to/db.duckdb", holding_pid=12345)

        assert exc.holding_pid == 12345
        assert "12345" in str(exc)
        assert exc.details["holding_pid"] == 12345

    def test_database_locked_error_without_pid(self) -> None:
        """DatabaseLockedError should work when PID is not available."""
        exc = DatabaseLockedError("/path/to/db.duckdb")

        assert exc.holding_pid is None
        assert "holding_pid" not in exc.details

    def test_database_locked_error_includes_suggestion(self) -> None:
        """DatabaseLockedError should include a helpful suggestion."""
        exc = DatabaseLockedError("/path/to/db.duckdb")

        assert "suggestion" in exc.details
        assert "try again" in exc.details["suggestion"].lower()

    def test_database_locked_error_to_dict(self) -> None:
        """DatabaseLockedError to_dict should be JSON serializable."""
        exc = DatabaseLockedError("/path/to/db.duckdb", holding_pid=99999)

        result = exc.to_dict()

        assert result["code"] == "DATABASE_LOCKED"
        assert result["details"]["db_path"] == "/path/to/db.duckdb"
        assert result["details"]["holding_pid"] == 99999

        # Verify JSON serializable
        json_str = json.dumps(result)
        assert "DATABASE_LOCKED" in json_str
        assert "99999" in json_str


class TestExceptionHierarchy:
    """Tests for exception inheritance."""

    def test_all_inherit_from_base(self) -> None:
        """All exceptions should inherit from MixpanelDataError."""
        exceptions: list[MixpanelDataError] = [
            ConfigError("test"),
            AccountNotFoundError("test"),
            AccountExistsError("test"),
            AuthenticationError("test"),
            RateLimitError("test"),
            QueryError("test"),
            JQLSyntaxError(raw_error="test"),
            TableExistsError("test"),
            TableNotFoundError("test"),
            DatabaseLockedError("/path/to/db"),
        ]

        for exc in exceptions:
            assert isinstance(exc, MixpanelDataError), (
                f"{exc.__class__.__name__} should inherit from MixpanelDataError"
            )
            assert isinstance(exc, Exception)

    def test_config_exceptions_inherit_from_config_error(self) -> None:
        """Config-related exceptions should inherit from ConfigError."""
        assert isinstance(AccountNotFoundError("x"), ConfigError)
        assert isinstance(AccountExistsError("x"), ConfigError)

    def test_catch_all_works(self) -> None:
        """Catch all library errors with single except clause."""
        exceptions_to_raise = [
            ConfigError("test"),
            AccountNotFoundError("test"),
            AuthenticationError("test"),
            TableExistsError("test"),
            RateLimitError("test"),
        ]

        for exc in exceptions_to_raise:
            with pytest.raises(MixpanelDataError) as caught:
                raise exc

            assert caught.value.code is not None
            assert caught.value.to_dict() is not None

    def test_error_codes_match_expected(self) -> None:
        """Verify all error codes match expected values."""
        expected_codes = {
            ConfigError: "CONFIG_ERROR",
            AccountNotFoundError: "ACCOUNT_NOT_FOUND",
            AccountExistsError: "ACCOUNT_EXISTS",
            AuthenticationError: "AUTH_FAILED",
            RateLimitError: "RATE_LIMITED",
            QueryError: "QUERY_FAILED",
            TableExistsError: "TABLE_EXISTS",
            TableNotFoundError: "TABLE_NOT_FOUND",
            DatabaseLockedError: "DATABASE_LOCKED",
        }

        for exc_class, expected_code in expected_codes.items():
            if exc_class in (AccountNotFoundError, AccountExistsError):
                exc = exc_class("test")
            elif exc_class in (TableExistsError, TableNotFoundError):
                exc = exc_class("test_table")
            elif exc_class == DatabaseLockedError:
                exc = exc_class("/path/to/db")
            else:
                exc = exc_class("test message")

            assert exc.code == expected_code, (
                f"{exc_class.__name__} should have code {expected_code}, got {exc.code}"
            )


class TestJQLSyntaxError:
    """Tests for JQL syntax error exception."""

    # Sample error from Mixpanel API
    SAMPLE_RAW_ERROR = (
        "UserVisiblePreconditionFailedError: Uncaught exception TypeError: "
        "Events(...).groupBy(...).limit is not a function\n"
        "  .limit(10);\n"
        "   ^\n"
        "\n"
        "Stack trace:\n"
        "TypeError: Events(...).groupBy(...).limit is not a function\n"
        "    at main (<anonymous>:7:4)\n"
    )

    SAMPLE_SCRIPT = """function main() {
  return Events({from_date: "2024-01-01", to_date: "2024-01-31"})
    .groupBy(["name"], mixpanel.reducer.count())
    .limit(10);
}"""

    def test_basic_creation(self) -> None:
        """JQLSyntaxError should parse error details from raw error."""
        exc = JQLSyntaxError(raw_error=self.SAMPLE_RAW_ERROR)

        assert exc.code == "JQL_SYNTAX_ERROR"
        assert isinstance(exc, QueryError)
        assert isinstance(exc, MixpanelDataError)

    def test_extracts_error_type(self) -> None:
        """Should extract JavaScript error type."""
        exc = JQLSyntaxError(raw_error=self.SAMPLE_RAW_ERROR)

        assert exc.error_type == "TypeError"

    def test_extracts_error_message(self) -> None:
        """Should extract error message."""
        exc = JQLSyntaxError(raw_error=self.SAMPLE_RAW_ERROR)

        assert "limit is not a function" in exc.error_message

    def test_extracts_line_info(self) -> None:
        """Should extract code snippet with caret."""
        exc = JQLSyntaxError(raw_error=self.SAMPLE_RAW_ERROR)

        assert exc.line_info is not None
        assert ".limit(10);" in exc.line_info
        assert "^" in exc.line_info

    def test_extracts_stack_trace(self) -> None:
        """Should extract stack trace."""
        exc = JQLSyntaxError(raw_error=self.SAMPLE_RAW_ERROR)

        assert exc.stack_trace is not None
        assert "at main" in exc.stack_trace
        assert "<anonymous>:7:4" in exc.stack_trace

    def test_includes_script(self) -> None:
        """Should include original script when provided."""
        exc = JQLSyntaxError(
            raw_error=self.SAMPLE_RAW_ERROR,
            script=self.SAMPLE_SCRIPT,
        )

        assert exc.script == self.SAMPLE_SCRIPT

    def test_includes_request_path(self) -> None:
        """Should include request path when provided."""
        exc = JQLSyntaxError(
            raw_error=self.SAMPLE_RAW_ERROR,
            request_path="/api/query/jql?project_id=12345",
        )

        assert exc.details["request_path"] == "/api/query/jql?project_id=12345"

    def test_raw_error_preserved(self) -> None:
        """Should preserve complete raw error string."""
        exc = JQLSyntaxError(raw_error=self.SAMPLE_RAW_ERROR)

        assert exc.raw_error == self.SAMPLE_RAW_ERROR

    def test_message_includes_error_type_and_message(self) -> None:
        """String representation should include error type and message."""
        exc = JQLSyntaxError(raw_error=self.SAMPLE_RAW_ERROR)

        message = str(exc)
        assert "JQL" in message
        assert "TypeError" in message

    def test_to_dict_includes_all_fields(self) -> None:
        """to_dict should include all parsed fields."""
        exc = JQLSyntaxError(
            raw_error=self.SAMPLE_RAW_ERROR,
            script=self.SAMPLE_SCRIPT,
            request_path="/api/query/jql",
        )

        result = exc.to_dict()

        assert result["code"] == "JQL_SYNTAX_ERROR"
        assert result["details"]["error_type"] == "TypeError"
        assert result["details"]["script"] == self.SAMPLE_SCRIPT
        assert result["details"]["request_path"] == "/api/query/jql"
        assert result["details"]["raw_error"] == self.SAMPLE_RAW_ERROR

        # Verify JSON serializable
        json_str = json.dumps(result)
        assert "TypeError" in json_str

    def test_handles_simple_error(self) -> None:
        """Should handle simple error without stack trace."""
        simple_error = "SyntaxError: Unexpected token }"

        exc = JQLSyntaxError(raw_error=simple_error)

        assert exc.error_type == "SyntaxError"
        assert "Unexpected token" in exc.error_message

    def test_handles_unknown_error_format(self) -> None:
        """Should gracefully handle unknown error format."""
        unknown_error = "Something went wrong"

        exc = JQLSyntaxError(raw_error=unknown_error)

        assert exc.error_type == "Error"  # Default
        assert exc.error_message == "Something went wrong"
        assert exc.raw_error == unknown_error

    def test_inherits_from_query_error(self) -> None:
        """JQLSyntaxError should be catchable as QueryError."""
        exc = JQLSyntaxError(raw_error="Test error")

        # Should be catchable with QueryError
        with pytest.raises(QueryError):
            raise exc

        # Should be catchable with MixpanelDataError
        with pytest.raises(MixpanelDataError):
            raise JQLSyntaxError(raw_error="Test error")


class TestAPIError:
    """Tests for APIError base class."""

    def test_basic_creation(self) -> None:
        """APIError should capture HTTP context."""
        exc = APIError(
            "Test error",
            status_code=500,
            response_body={"error": "Internal error"},
            request_method="GET",
            request_url="https://api.example.com/test",
            request_params={"param1": "value1"},
        )

        assert exc.status_code == 500
        assert exc.response_body == {"error": "Internal error"}
        assert exc.request_method == "GET"
        assert exc.request_url == "https://api.example.com/test"
        assert exc.request_params == {"param1": "value1"}
        assert exc.code == "API_ERROR"

    def test_inherits_from_base(self) -> None:
        """APIError should inherit from MixpanelDataError."""
        exc = APIError("Test", status_code=400)
        assert isinstance(exc, MixpanelDataError)

    def test_to_dict_includes_http_context(self) -> None:
        """to_dict should include all HTTP context."""
        exc = APIError(
            "Test error",
            status_code=400,
            response_body="Bad request",
            request_method="POST",
            request_url="https://api.example.com/query",
            request_params={"project_id": "123"},
            request_body={"data": "test"},
        )

        result = exc.to_dict()

        assert result["details"]["status_code"] == 400
        assert result["details"]["response_body"] == "Bad request"
        assert result["details"]["request_method"] == "POST"
        assert result["details"]["request_url"] == "https://api.example.com/query"
        assert result["details"]["request_params"] == {"project_id": "123"}
        assert result["details"]["request_body"] == {"data": "test"}

        # Verify JSON serializable
        json_str = json.dumps(result)
        assert "400" in json_str

    def test_optional_fields(self) -> None:
        """Optional fields should not appear in details if not provided."""
        exc = APIError("Test", status_code=500)

        assert exc.response_body is None
        assert exc.request_method is None
        assert "response_body" not in exc.details
        assert "request_method" not in exc.details

    def test_catchable_as_base(self) -> None:
        """APIError should be catchable as MixpanelDataError."""
        with pytest.raises(MixpanelDataError):
            raise APIError("Test", status_code=500)


class TestServerError:
    """Tests for ServerError (5xx errors)."""

    def test_basic_creation(self) -> None:
        """ServerError should have SERVER_ERROR code."""
        exc = ServerError("Internal server error", status_code=500)

        assert exc.code == "SERVER_ERROR"
        assert exc.status_code == 500
        assert isinstance(exc, APIError)
        assert isinstance(exc, MixpanelDataError)

    def test_with_full_context(self) -> None:
        """ServerError should include request/response context."""
        exc = ServerError(
            "Server error: unit and interval both specified",
            status_code=500,
            response_body={"error": "unit and interval both specified"},
            request_method="GET",
            request_url="https://mixpanel.com/api/query/retention",
            request_params={"unit": "day", "interval": 7},
        )

        assert "unit and interval" in str(exc)
        assert exc.response_body == {"error": "unit and interval both specified"}
        assert exc.request_params == {"unit": "day", "interval": 7}

    def test_to_dict_serializable(self) -> None:
        """ServerError to_dict should be JSON serializable."""
        exc = ServerError(
            "Test",
            status_code=503,
            response_body={"retry_after": 60},
        )

        result = exc.to_dict()
        json_str = json.dumps(result)
        assert "503" in json_str
        assert "SERVER_ERROR" in json_str


class TestAPIErrorHierarchy:
    """Tests for API error inheritance."""

    def test_authentication_error_inherits_from_api_error(self) -> None:
        """AuthenticationError should inherit from APIError."""
        exc = AuthenticationError(
            "Invalid credentials",
            status_code=401,
            request_url="https://api.example.com",
        )

        assert isinstance(exc, APIError)
        assert exc.status_code == 401
        assert exc.request_url == "https://api.example.com"

    def test_rate_limit_error_inherits_from_api_error(self) -> None:
        """RateLimitError should inherit from APIError."""
        exc = RateLimitError(
            "Too many requests",
            retry_after=60,
            status_code=429,
            request_method="GET",
            request_url="https://api.example.com/query",
        )

        assert isinstance(exc, APIError)
        assert exc.status_code == 429
        assert exc.retry_after == 60
        assert exc.request_method == "GET"

    def test_query_error_inherits_from_api_error(self) -> None:
        """QueryError should inherit from APIError."""
        exc = QueryError(
            "Invalid query",
            status_code=400,
            response_body={"error": "syntax error"},
            request_params={"event": "signup"},
        )

        assert isinstance(exc, APIError)
        assert exc.status_code == 400
        assert exc.response_body == {"error": "syntax error"}

    def test_jql_syntax_error_inherits_from_api_error(self) -> None:
        """JQLSyntaxError should inherit from APIError via QueryError."""
        exc = JQLSyntaxError(raw_error="TypeError: x is not defined")

        assert isinstance(exc, QueryError)
        assert isinstance(exc, APIError)
        assert exc.status_code == 412

    def test_server_error_inherits_from_api_error(self) -> None:
        """ServerError should inherit from APIError."""
        exc = ServerError("Internal error", status_code=500)

        assert isinstance(exc, APIError)
        assert exc.status_code == 500

    def test_catch_all_api_errors(self) -> None:
        """All API errors should be catchable with APIError."""
        errors = [
            AuthenticationError("test"),
            RateLimitError("test"),
            QueryError("test"),
            ServerError("test", status_code=500),
            JQLSyntaxError(raw_error="test"),
        ]

        for error in errors:
            with pytest.raises(APIError):
                raise error
