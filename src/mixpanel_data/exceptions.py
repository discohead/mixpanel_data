"""Exception hierarchy for mixpanel_data.

All library exceptions inherit from MixpanelDataError, enabling callers to
catch all library errors with a single except clause while still allowing
fine-grained exception handling when needed.

The exception hierarchy is designed to help AI agents autonomously recover
from errors by providing structured access to:
- HTTP status codes and response bodies
- Original request context (method, URL, params, body)
- Parsed error details for common error patterns
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


# API Exceptions - Base class for HTTP errors


class APIError(MixpanelDataError):
    """Base class for Mixpanel API HTTP errors.

    Provides structured access to HTTP request/response context for debugging
    and automated recovery by AI agents. All API-related exceptions inherit
    from this class, enabling agents to:

    - Understand what went wrong (status code, error message)
    - See exactly what was sent (request method, URL, params, body)
    - See exactly what came back (response body, headers)
    - Modify their approach and retry autonomously

    Example:
        ```python
        try:
            result = client.segmentation(event="signup", ...)
        except APIError as e:
            print(f"Status: {e.status_code}")
            print(f"Response: {e.response_body}")
            print(f"Request URL: {e.request_url}")
            print(f"Request params: {e.request_params}")
        ```
    """

    def __init__(
        self,
        message: str,
        *,
        status_code: int,
        response_body: str | dict[str, Any] | None = None,
        request_method: str | None = None,
        request_url: str | None = None,
        request_params: dict[str, Any] | None = None,
        request_body: dict[str, Any] | None = None,
        code: str = "API_ERROR",
    ) -> None:
        """Initialize APIError.

        Args:
            message: Human-readable error message.
            status_code: HTTP status code from response.
            response_body: Raw response body (string or parsed dict).
            request_method: HTTP method used (GET, POST).
            request_url: Full request URL.
            request_params: Query parameters sent.
            request_body: Request body sent (for POST requests).
            code: Machine-readable error code.
        """
        self._status_code = status_code
        self._response_body = response_body
        self._request_method = request_method
        self._request_url = request_url
        self._request_params = request_params
        self._request_body = request_body

        details: dict[str, Any] = {
            "status_code": status_code,
        }
        if response_body is not None:
            details["response_body"] = response_body
        if request_method is not None:
            details["request_method"] = request_method
        if request_url is not None:
            details["request_url"] = request_url
        if request_params is not None:
            details["request_params"] = request_params
        if request_body is not None:
            details["request_body"] = request_body

        super().__init__(message, code=code, details=details)

    @property
    def status_code(self) -> int:
        """HTTP status code from response."""
        return self._status_code

    @property
    def response_body(self) -> str | dict[str, Any] | None:
        """Raw response body (string or parsed dict)."""
        return self._response_body

    @property
    def request_method(self) -> str | None:
        """HTTP method used (GET, POST)."""
        return self._request_method

    @property
    def request_url(self) -> str | None:
        """Full request URL."""
        return self._request_url

    @property
    def request_params(self) -> dict[str, Any] | None:
        """Query parameters sent."""
        return self._request_params

    @property
    def request_body(self) -> dict[str, Any] | None:
        """Request body sent (for POST requests)."""
        return self._request_body


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


class AuthenticationError(APIError):
    """Authentication with Mixpanel API failed (HTTP 401).

    Raised when credentials are invalid, expired, or lack required permissions.
    Inherits from APIError to provide full request/response context.

    Example:
        ```python
        try:
            client.segmentation(...)
        except AuthenticationError as e:
            print(f"Auth failed: {e.message}")
            print(f"Request URL: {e.request_url}")
            # Check if project_id is correct, credentials are valid, etc.
        ```
    """

    def __init__(
        self,
        message: str = "Authentication failed",
        *,
        status_code: int = 401,
        response_body: str | dict[str, Any] | None = None,
        request_method: str | None = None,
        request_url: str | None = None,
        request_params: dict[str, Any] | None = None,
    ) -> None:
        """Initialize AuthenticationError.

        Args:
            message: Human-readable error message.
            status_code: HTTP status code (default 401).
            response_body: Raw response body.
            request_method: HTTP method used.
            request_url: Full request URL.
            request_params: Query parameters sent.
        """
        super().__init__(
            message,
            status_code=status_code,
            response_body=response_body,
            request_method=request_method,
            request_url=request_url,
            request_params=request_params,
            code="AUTH_FAILED",
        )


# Rate Limit Exceptions


class RateLimitError(APIError):
    """Mixpanel API rate limit exceeded (HTTP 429).

    Raised when the API returns a 429 status. The retry_after property
    indicates when the request can be retried. Inherits from APIError
    to provide full request context for debugging.

    Example:
        ```python
        try:
            for _ in range(1000):
                client.segmentation(...)
        except RateLimitError as e:
            print(f"Rate limited! Retry after {e.retry_after}s")
            print(f"Request: {e.request_method} {e.request_url}")
            time.sleep(e.retry_after or 60)
        ```
    """

    def __init__(
        self,
        message: str = "Rate limit exceeded",
        *,
        retry_after: int | None = None,
        status_code: int = 429,
        response_body: str | dict[str, Any] | None = None,
        request_method: str | None = None,
        request_url: str | None = None,
        request_params: dict[str, Any] | None = None,
    ) -> None:
        """Initialize RateLimitError.

        Args:
            message: Human-readable error message.
            retry_after: Seconds until retry is allowed (from Retry-After header).
            status_code: HTTP status code (default 429).
            response_body: Raw response body.
            request_method: HTTP method used.
            request_url: Full request URL.
            request_params: Query parameters sent.
        """
        self._retry_after = retry_after
        if retry_after is not None:
            message = f"{message}. Retry after {retry_after} seconds."

        super().__init__(
            message,
            status_code=status_code,
            response_body=response_body,
            request_method=request_method,
            request_url=request_url,
            request_params=request_params,
            code="RATE_LIMITED",
        )
        # Add retry_after to details
        if retry_after is not None:
            self._details["retry_after"] = retry_after

    @property
    def retry_after(self) -> int | None:
        """Seconds until retry is allowed, or None if unknown."""
        return self._retry_after


# Query Exceptions


class QueryError(APIError):
    """Query execution failed (HTTP 400 or query-specific error).

    Raised when an API query fails due to invalid parameters, syntax errors,
    or other query-specific issues. Inherits from APIError to provide full
    request/response context for debugging.

    Example:
        ```python
        try:
            client.segmentation(event="nonexistent", ...)
        except QueryError as e:
            print(f"Query failed: {e.message}")
            print(f"Response: {e.response_body}")
            print(f"Request params: {e.request_params}")
        ```
    """

    def __init__(
        self,
        message: str = "Query execution failed",
        *,
        status_code: int = 400,
        response_body: str | dict[str, Any] | None = None,
        request_method: str | None = None,
        request_url: str | None = None,
        request_params: dict[str, Any] | None = None,
        request_body: dict[str, Any] | None = None,
    ) -> None:
        """Initialize QueryError.

        Args:
            message: Human-readable error message.
            status_code: HTTP status code (default 400).
            response_body: Raw response body with error details.
            request_method: HTTP method used.
            request_url: Full request URL.
            request_params: Query parameters sent.
            request_body: Request body sent (for POST).
        """
        super().__init__(
            message,
            status_code=status_code,
            response_body=response_body,
            request_method=request_method,
            request_url=request_url,
            request_params=request_params,
            request_body=request_body,
            code="QUERY_FAILED",
        )


class ServerError(APIError):
    """Mixpanel server error (HTTP 5xx).

    Raised when the Mixpanel API returns a server error. These are typically
    transient issues that may succeed on retry. The response_body property
    contains the full error details from Mixpanel, which often include
    actionable information (e.g., "unit and interval both specified").

    Example:
        ```python
        try:
            client.retention(born_event="signup", ...)
        except ServerError as e:
            print(f"Server error {e.status_code}: {e.message}")
            print(f"Response: {e.response_body}")
            print(f"Request params: {e.request_params}")
            # AI agent can analyze response_body to fix the request
        ```
    """

    def __init__(
        self,
        message: str = "Server error",
        *,
        status_code: int = 500,
        response_body: str | dict[str, Any] | None = None,
        request_method: str | None = None,
        request_url: str | None = None,
        request_params: dict[str, Any] | None = None,
        request_body: dict[str, Any] | None = None,
    ) -> None:
        """Initialize ServerError.

        Args:
            message: Human-readable error message.
            status_code: HTTP status code (5xx).
            response_body: Raw response body with error details.
            request_method: HTTP method used.
            request_url: Full request URL.
            request_params: Query parameters sent.
            request_body: Request body sent (for POST).
        """
        super().__init__(
            message,
            status_code=status_code,
            response_body=response_body,
            request_method=request_method,
            request_url=request_url,
            request_params=request_params,
            request_body=request_body,
            code="SERVER_ERROR",
        )


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


class DatabaseLockedError(MixpanelDataError):
    """Database is locked by another process.

    Raised when attempting to access a DuckDB database that is locked
    by another process. DuckDB uses single-writer, multiple-reader
    concurrency - only one process can have write access at a time.

    Example:
        ```python
        try:
            ws = Workspace()
        except DatabaseLockedError as e:
            print(f"Database {e.db_path} is locked")
            if e.holding_pid:
                print(f"Held by PID {e.holding_pid}")
        ```
    """

    def __init__(
        self,
        db_path: str,
        holding_pid: int | None = None,
    ) -> None:
        """Initialize DatabaseLockedError.

        Args:
            db_path: Path to the locked database file.
            holding_pid: Process ID holding the lock, if available.
        """
        message = f"Database '{db_path}' is locked by another process"
        if holding_pid is not None:
            message += f" (PID {holding_pid})"
        message += ". Wait for the other operation to complete and try again."

        details: dict[str, str | int] = {
            "db_path": db_path,
            "suggestion": "Wait for the other operation to complete and try again.",
        }
        if holding_pid is not None:
            details["holding_pid"] = holding_pid

        super().__init__(message, code="DATABASE_LOCKED", details=details)

    @property
    def db_path(self) -> str:
        """Path to the locked database."""
        return str(self._details.get("db_path", ""))

    @property
    def holding_pid(self) -> int | None:
        """Process ID holding the lock, if available."""
        pid = self._details.get("holding_pid")
        return int(pid) if pid is not None else None


# JQL Exceptions


class JQLSyntaxError(QueryError):
    """JQL script execution failed with syntax or runtime error (HTTP 412).

    Raised when a JQL script fails to execute due to syntax errors,
    type errors, or other JavaScript runtime issues. Provides structured
    access to error details from Mixpanel's response.

    Inherits from QueryError (and thus APIError) to provide full HTTP context.

    Example:
        ```python
        try:
            result = live_query.jql(script)
        except JQLSyntaxError as e:
            print(f"Error: {e.error_type}: {e.error_message}")
            print(f"Script: {e.script}")
            print(f"Line info: {e.line_info}")
            # AI agent can use this to fix the script and retry
        ```
    """

    def __init__(
        self,
        raw_error: str,
        script: str | None = None,
        request_path: str | None = None,
    ) -> None:
        """Initialize JQLSyntaxError.

        Args:
            raw_error: Raw error string from Mixpanel API response.
            script: The JQL script that caused the error.
            request_path: API request path from error response.
        """
        # Parse structured error info from raw error string
        self._error_type = self._extract_error_type(raw_error)
        self._error_message = self._extract_message(raw_error)
        self._line_info = self._extract_line_info(raw_error)
        self._stack_trace = self._extract_stack_trace(raw_error)
        self._script = script
        self._raw_error = raw_error
        self._request_path = request_path

        # Build human-readable message
        message = f"JQL {self._error_type}: {self._error_message}"
        if self._line_info:
            message += f"\n{self._line_info}"

        # Build response body dict for APIError
        response_body: dict[str, Any] = {
            "error": raw_error,
        }
        if request_path:
            response_body["request"] = request_path

        super().__init__(
            message,
            status_code=412,
            response_body=response_body,
            request_body={"script": script} if script else None,
        )
        self._code = "JQL_SYNTAX_ERROR"

        # Add JQL-specific details
        self._details["error_type"] = self._error_type
        self._details["error_message"] = self._error_message
        self._details["line_info"] = self._line_info
        self._details["stack_trace"] = self._stack_trace
        self._details["script"] = script
        self._details["request_path"] = request_path
        self._details["raw_error"] = raw_error

    @property
    def error_type(self) -> str:
        """JavaScript error type (TypeError, SyntaxError, ReferenceError, etc.)."""
        return self._error_type

    @property
    def error_message(self) -> str:
        """Error message describing what went wrong."""
        return self._error_message

    @property
    def line_info(self) -> str | None:
        """Code snippet with caret showing error location, if available."""
        return self._line_info

    @property
    def stack_trace(self) -> str | None:
        """JavaScript stack trace, if available."""
        return self._stack_trace

    @property
    def script(self) -> str | None:
        """The JQL script that caused the error."""
        return self._script

    @property
    def raw_error(self) -> str:
        """Complete raw error string from Mixpanel."""
        return self._raw_error

    def _extract_error_type(self, raw: str) -> str:
        """Extract JavaScript error type from raw error string.

        Looks for patterns like "Uncaught exception TypeError:" or
        "SyntaxError:" at the start of error messages.
        """
        import re

        # Match "Uncaught exception TypeError:" pattern
        match = re.search(r"Uncaught exception (\w+Error):", raw)
        if match:
            return match.group(1)

        # Match standalone "TypeError:" at start
        match = re.search(r"^(\w+Error):", raw)
        if match:
            return match.group(1)

        # Match in stack trace section
        match = re.search(r"\n(\w+Error):", raw)
        if match:
            return match.group(1)

        return "Error"

    def _extract_message(self, raw: str) -> str:
        """Extract the core error message.

        Removes the wrapper text and extracts the actual error description.
        """
        import re

        # Remove "UserVisiblePreconditionFailedError: " prefix
        cleaned = re.sub(r"^UserVisiblePreconditionFailedError:\s*", "", raw)

        # Remove "Uncaught exception TypeError: " prefix
        cleaned = re.sub(r"^Uncaught exception \w+Error:\s*", "", cleaned)

        # Take first line (before newline with code snippet)
        first_line = cleaned.split("\n")[0].strip()

        # Limit length for readability
        if len(first_line) > 200:
            first_line = first_line[:197] + "..."

        return first_line if first_line else raw[:100]

    def _extract_line_info(self, raw: str) -> str | None:
        """Extract code snippet with caret pointer.

        Looks for patterns like:
          .limit(10);
           ^
        """
        import re

        # Match lines with code followed by caret pointer
        match = re.search(r"(\n\s+[^\n]+\n\s+\^)", raw)
        if match:
            return match.group(1).strip()

        return None

    def _extract_stack_trace(self, raw: str) -> str | None:
        """Extract JavaScript stack trace.

        Looks for "Stack trace:" section and extracts the location info.
        """
        import re

        # Find stack trace section
        match = re.search(r"Stack trace:\n(.+?)(?:\n\n|$)", raw, re.DOTALL)
        if match:
            return match.group(1).strip()

        # Alternative: look for "at main (<anonymous>:N:N)" pattern
        match = re.search(r"(at \w+ \(<anonymous>:\d+:\d+\))", raw)
        if match:
            return match.group(1)

        return None
