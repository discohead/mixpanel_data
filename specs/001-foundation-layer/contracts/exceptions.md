# Contract: Exception Hierarchy

**Type**: Internal Python Interface
**Module**: `mixpanel_data.exceptions`
**Public Access**: Direct import from `mixpanel_data`

## Interface Definition

```python
class MixpanelDataError(Exception):
    """Base exception for all mixpanel_data errors."""

    def __init__(
        self,
        message: str,
        code: str = "UNKNOWN_ERROR",
        details: dict[str, Any] | None = None,
    ) -> None:
        """
        Initialize exception.

        Args:
            message: Human-readable error message.
            code: Machine-readable error code.
            details: Additional structured data.
        """
        ...

    @property
    def code(self) -> str:
        """Machine-readable error code."""
        ...

    @property
    def details(self) -> dict[str, Any]:
        """Additional structured error data."""
        ...

    def to_dict(self) -> dict[str, Any]:
        """
        Serialize exception for logging/JSON output.

        Returns:
            Dictionary with keys: code, message, details
        """
        ...


# Configuration Exceptions

class ConfigError(MixpanelDataError):
    """Base for configuration-related errors."""
    # code = "CONFIG_ERROR"


class AccountNotFoundError(ConfigError):
    """Named account does not exist in configuration."""

    def __init__(
        self,
        account_name: str,
        available_accounts: list[str] | None = None,
    ) -> None:
        """
        Args:
            account_name: The requested account name.
            available_accounts: List of valid account names.
        """
        # code = "ACCOUNT_NOT_FOUND"
        ...


class AccountExistsError(ConfigError):
    """Account name already exists in configuration."""

    def __init__(self, account_name: str) -> None:
        """
        Args:
            account_name: The conflicting account name.
        """
        # code = "ACCOUNT_EXISTS"
        ...


# Authentication Exceptions

class AuthenticationError(MixpanelDataError):
    """Authentication with Mixpanel API failed."""
    # code = "AUTH_FAILED"


# Storage Exceptions

class TableExistsError(MixpanelDataError):
    """Table already exists in local database."""

    def __init__(self, table_name: str) -> None:
        """
        Args:
            table_name: Name of the existing table.
        """
        # code = "TABLE_EXISTS"
        # details includes suggestion to use drop()
        ...


class TableNotFoundError(MixpanelDataError):
    """Table does not exist in local database."""

    def __init__(self, table_name: str) -> None:
        """
        Args:
            table_name: Name of the missing table.
        """
        # code = "TABLE_NOT_FOUND"
        ...


# API Exceptions

class RateLimitError(MixpanelDataError):
    """Mixpanel API rate limit exceeded."""

    def __init__(
        self,
        message: str = "Rate limit exceeded",
        retry_after: int | None = None,
    ) -> None:
        """
        Args:
            message: Error description.
            retry_after: Seconds until retry is allowed.
        """
        # code = "RATE_LIMITED"
        # details includes retry_after
        ...

    @property
    def retry_after(self) -> int | None:
        """Seconds until retry is allowed."""
        ...


class QueryError(MixpanelDataError):
    """Query execution failed."""
    # code = "QUERY_FAILED"
```

## Error Codes Reference

| Code | Exception | Description |
| ---- | --------- | ----------- |
| `UNKNOWN_ERROR` | MixpanelDataError | Unclassified error |
| `CONFIG_ERROR` | ConfigError | General configuration error |
| `ACCOUNT_NOT_FOUND` | AccountNotFoundError | Named account not in config |
| `ACCOUNT_EXISTS` | AccountExistsError | Account name already used |
| `AUTH_FAILED` | AuthenticationError | API authentication failed |
| `TABLE_EXISTS` | TableExistsError | Table already in database |
| `TABLE_NOT_FOUND` | TableNotFoundError | Table not in database |
| `RATE_LIMITED` | RateLimitError | API rate limit hit |
| `QUERY_FAILED` | QueryError | SQL or API query failed |

## Usage Examples

```python
from mixpanel_data import MixpanelDataError, TableExistsError, RateLimitError

# Catch all library errors
try:
    workspace.fetch_events(...)
except MixpanelDataError as e:
    print(f"Error [{e.code}]: {e}")
    log.error("mixpanel_data error", **e.to_dict())

# Handle specific errors
try:
    workspace.fetch_events(table_name="events", ...)
except TableExistsError as e:
    print(f"Table '{e.details['table_name']}' already exists")
    print(f"Suggestion: {e.details['suggestion']}")

# Handle rate limiting with retry
try:
    workspace.segmentation(...)
except RateLimitError as e:
    if e.retry_after:
        time.sleep(e.retry_after)
        # retry...
```

## Testing Contract

```python
def test_base_exception_serializable():
    """All exceptions must be JSON-serializable."""
    exc = MixpanelDataError("test", code="TEST", details={"key": "value"})
    result = exc.to_dict()

    assert result["code"] == "TEST"
    assert result["message"] == "test"
    assert result["details"]["key"] == "value"
    json.dumps(result)  # Should not raise


def test_account_not_found_includes_available():
    """AccountNotFoundError should list available accounts."""
    exc = AccountNotFoundError("missing", available_accounts=["a", "b"])

    assert "missing" in str(exc)
    assert exc.details["available_accounts"] == ["a", "b"]


def test_catch_all_works():
    """All specific exceptions should be catchable as base."""
    for exc_class in [
        ConfigError,
        AccountNotFoundError,
        AuthenticationError,
        TableExistsError,
        RateLimitError,
    ]:
        exc = exc_class("test") if exc_class != AccountNotFoundError else AccountNotFoundError("x")
        assert isinstance(exc, MixpanelDataError)
```
