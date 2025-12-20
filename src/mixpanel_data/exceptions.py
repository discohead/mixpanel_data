"""Exception hierarchy for mixpanel_data.

All library exceptions inherit from MixpanelDataError, enabling callers to
catch all library errors with a single except clause while still allowing
fine-grained exception handling when needed.
"""

from __future__ import annotations

from typing import Any


class MixpanelDataError(Exception):
    """Base exception for all mixpanel_data errors.

    All library exceptions inherit from this class, allowing callers to:
    - Catch all library errors: except MixpanelDataError
    - Handle specific errors: except AccountNotFoundError
    - Serialize errors: error.to_dict()
    """

    def __init__(
        self,
        message: str,
        code: str = "UNKNOWN_ERROR",
        details: dict[str, Any] | None = None,
    ) -> None:
        """Initialize exception.

        Args:
            message: Human-readable error message.
            code: Machine-readable error code for programmatic handling.
            details: Additional structured data about the error.
        """
        super().__init__(message)
        self._message = message
        self._code = code
        self._details = details or {}

    @property
    def code(self) -> str:
        """Machine-readable error code."""
        return self._code

    @property
    def message(self) -> str:
        """Human-readable error message."""
        return self._message

    @property
    def details(self) -> dict[str, Any]:
        """Additional structured error data."""
        return self._details

    def to_dict(self) -> dict[str, Any]:
        """Serialize exception for logging/JSON output.

        Returns:
            Dictionary with keys: code, message, details.
            All values are JSON-serializable.
        """
        return {
            "code": self._code,
            "message": self._message,
            "details": self._details,
        }

    def __str__(self) -> str:
        """Return human-readable error message."""
        return self._message

    def __repr__(self) -> str:
        """Return detailed string representation."""
        return (
            f"{self.__class__.__name__}(message={self._message!r}, code={self._code!r})"
        )


# Configuration Exceptions


class ConfigError(MixpanelDataError):
    """Base for configuration-related errors.

    Raised when there's a problem with configuration files, environment
    variables, or credential resolution.
    """

    def __init__(
        self,
        message: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        """Initialize ConfigError.

        Args:
            message: Human-readable error message.
            details: Additional structured data.
        """
        super().__init__(message, code="CONFIG_ERROR", details=details)


class AccountNotFoundError(ConfigError):
    """Named account does not exist in configuration.

    Raised when attempting to access an account that hasn't been configured.
    The available_accounts property lists valid account names to help users.
    """

    def __init__(
        self,
        account_name: str,
        available_accounts: list[str] | None = None,
    ) -> None:
        """Initialize AccountNotFoundError.

        Args:
            account_name: The requested account name that wasn't found.
            available_accounts: List of valid account names for suggestions.
        """
        available = available_accounts or []
        if available:
            available_str = ", ".join(f"'{a}'" for a in available)
            message = (
                f"Account '{account_name}' not found. "
                f"Available accounts: {available_str}"
            )
        else:
            message = f"Account '{account_name}' not found. No accounts configured."

        details = {
            "account_name": account_name,
            "available_accounts": available,
        }
        super().__init__(message, details=details)
        self._code = "ACCOUNT_NOT_FOUND"

    @property
    def account_name(self) -> str:
        """The requested account name that wasn't found."""
        return str(self._details.get("account_name", ""))

    @property
    def available_accounts(self) -> list[str]:
        """List of valid account names."""
        accounts = self._details.get("available_accounts")
        return accounts if isinstance(accounts, list) else []


class AccountExistsError(ConfigError):
    """Account name already exists in configuration.

    Raised when attempting to add an account with a name that's already in use.
    """

    def __init__(self, account_name: str) -> None:
        """Initialize AccountExistsError.

        Args:
            account_name: The conflicting account name.
        """
        message = f"Account '{account_name}' already exists."
        details = {"account_name": account_name}
        super().__init__(message, details=details)
        self._code = "ACCOUNT_EXISTS"

    @property
    def account_name(self) -> str:
        """The conflicting account name."""
        return str(self._details.get("account_name", ""))


# Authentication Exceptions


class AuthenticationError(MixpanelDataError):
    """Authentication with Mixpanel API failed.

    Raised when credentials are invalid, expired, or lack required permissions.
    """

    def __init__(
        self,
        message: str = "Authentication failed",
        details: dict[str, Any] | None = None,
    ) -> None:
        """Initialize AuthenticationError.

        Args:
            message: Human-readable error message.
            details: Additional structured data.
        """
        super().__init__(message, code="AUTH_FAILED", details=details)


# API Exceptions


class RateLimitError(MixpanelDataError):
    """Mixpanel API rate limit exceeded.

    Raised when the API returns a 429 status. The retry_after property
    indicates when the request can be retried.
    """

    def __init__(
        self,
        message: str = "Rate limit exceeded",
        retry_after: int | None = None,
    ) -> None:
        """Initialize RateLimitError.

        Args:
            message: Human-readable error message.
            retry_after: Seconds until retry is allowed (from Retry-After header).
        """
        details: dict[str, Any] = {}
        if retry_after is not None:
            details["retry_after"] = retry_after
            message = f"{message}. Retry after {retry_after} seconds."

        super().__init__(message, code="RATE_LIMITED", details=details)
        self._retry_after = retry_after

    @property
    def retry_after(self) -> int | None:
        """Seconds until retry is allowed, or None if unknown."""
        return self._retry_after


class QueryError(MixpanelDataError):
    """Query execution failed.

    Raised when a SQL or API query fails to execute. The details property
    may contain additional information about the failure.
    """

    def __init__(
        self,
        message: str = "Query execution failed",
        details: dict[str, Any] | None = None,
    ) -> None:
        """Initialize QueryError.

        Args:
            message: Human-readable error message.
            details: Additional structured data (e.g., query text, error position).
        """
        super().__init__(message, code="QUERY_FAILED", details=details)


# Storage Exceptions


class TableExistsError(MixpanelDataError):
    """Table already exists in local database.

    Raised when attempting to create a table that already exists.
    Use drop() first to remove the existing table.
    """

    def __init__(self, table_name: str) -> None:
        """Initialize TableExistsError.

        Args:
            table_name: Name of the existing table.
        """
        message = f"Table '{table_name}' already exists."
        details = {
            "table_name": table_name,
            "suggestion": "Use drop() first to remove the existing table.",
        }
        super().__init__(message, code="TABLE_EXISTS", details=details)

    @property
    def table_name(self) -> str:
        """Name of the existing table."""
        return str(self._details.get("table_name", ""))


class TableNotFoundError(MixpanelDataError):
    """Table does not exist in local database.

    Raised when attempting to access a table that hasn't been created.
    """

    def __init__(self, table_name: str) -> None:
        """Initialize TableNotFoundError.

        Args:
            table_name: Name of the missing table.
        """
        message = f"Table '{table_name}' not found."
        details = {"table_name": table_name}
        super().__init__(message, code="TABLE_NOT_FOUND", details=details)

    @property
    def table_name(self) -> str:
        """Name of the missing table."""
        return str(self._details.get("table_name", ""))
