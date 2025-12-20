"""Unit tests for mixpanel_data exception hierarchy."""

from __future__ import annotations

import json

import pytest

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
        """QueryError should have QUERY_FAILED code."""
        exc = QueryError("Invalid SQL syntax", details={"query": "SELECT * FROM"})

        assert exc.code == "QUERY_FAILED"
        assert exc.details["query"] == "SELECT * FROM"


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
            TableExistsError("test"),
            TableNotFoundError("test"),
        ]

        for exc in exceptions:
            assert isinstance(
                exc, MixpanelDataError
            ), f"{exc.__class__.__name__} should inherit from MixpanelDataError"
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
        }

        for exc_class, expected_code in expected_codes.items():
            if exc_class in (AccountNotFoundError, AccountExistsError):
                exc = exc_class("test")
            elif exc_class in (TableExistsError, TableNotFoundError):
                exc = exc_class("test_table")
            else:
                exc = exc_class("test message")

            assert (
                exc.code == expected_code
            ), f"{exc_class.__name__} should have code {expected_code}, got {exc.code}"
