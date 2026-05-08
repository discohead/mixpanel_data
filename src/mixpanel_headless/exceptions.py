"""Exception hierarchy for mixpanel_headless.

All library exceptions inherit from MixpanelHeadlessError, enabling callers to
catch all library errors with a single except clause while still allowing
fine-grained exception handling when needed.

The exception hierarchy is designed to help AI agents autonomously recover
from errors by providing structured access to:
- HTTP status codes and response bodies
- Original request context (method, URL, params, body)
- Parsed error details for common error patterns
- Structured validation errors with paths, suggestions, and fixes
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Literal

if TYPE_CHECKING:
    from mixpanel_headless._internal.auth.account import Region


class MixpanelHeadlessError(Exception):
    """Base exception for all mixpanel_headless errors.

    All library exceptions inherit from this class, allowing callers to:
    - Catch all library errors: except MixpanelHeadlessError
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


class APIError(MixpanelHeadlessError):
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


class ConfigError(MixpanelHeadlessError):
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


class ProjectNotFoundError(ConfigError):
    """Raised when a specified project is not accessible.

    Includes the requested project ID and optionally a list of
    accessible project IDs to help the user correct their selection.

    Example:
        ```python
        try:
            projects = ws.projects()
            match = [p for p in projects if p.id == target_id]
            if not match:
                raise ProjectNotFoundError(
                    target_id,
                    available_projects=[p.id for p in projects],
                )
        except ProjectNotFoundError as e:
            print(f"Project '{e.project_id}' not found.")
            if e.available_projects:
                print(f"Available: {', '.join(e.available_projects)}")
        ```
    """

    def __init__(
        self,
        project_id: str,
        available_projects: list[str] | None = None,
    ) -> None:
        """Initialize ProjectNotFoundError.

        Args:
            project_id: The requested project ID that wasn't found.
            available_projects: List of accessible project IDs for suggestions.
        """
        available = available_projects or []
        if available:
            available_str = ", ".join(f"'{p}'" for p in available)
            message = (
                f"Project '{project_id}' not found. Available projects: {available_str}"
            )
        else:
            message = (
                f"Project '{project_id}' not found. No accessible projects discovered."
            )

        details: dict[str, Any] = {
            "project_id": project_id,
            "available_projects": available,
        }
        super().__init__(message, details=details)
        self._code = "PROJECT_NOT_FOUND"

    @property
    def project_id(self) -> str:
        """The requested project ID that wasn't found."""
        return str(self._details.get("project_id", ""))

    @property
    def available_projects(self) -> list[str]:
        """List of accessible project IDs."""
        projects = self._details.get("available_projects")
        return projects if isinstance(projects, list) else []


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


class InvalidArgumentError(ConfigError):
    """Raised when a public API call combines mutually incompatible arguments.

    Carries a ``violation`` discriminator and the resolved
    ``detected_auth_type`` so non-CLI callers (Cowork's ``auth_manager.py``,
    JSON consumers) can dispatch programmatically without parsing the
    human message. The CLI ``handle_errors`` decorator maps this subclass
    to ``ExitCode.INVALID_ARGS`` (3) instead of the generic
    ``GENERAL_ERROR`` (1) that ``ConfigError`` would otherwise produce.

    Used by ``accounts.login_unified`` for the three documented
    flag-combination rejections (043 contract, ``cli-commands.md`` §5):
    ``--service-account`` + ``--token-env``, ``--no-browser`` against a
    non-browser auth type, and ``--secret-stdin`` against a non-SA
    auth type.

    Example:
        ```python
        try:
            accounts.login_unified(service_account=True, token_env="X")
        except InvalidArgumentError as exc:
            assert exc.violation == "mutually_exclusive"
            assert exc.detected_auth_type == "service_account"
        ```
    """

    _VALID_VIOLATIONS = (
        "mutually_exclusive",
        "no_browser_misuse",
        "secret_stdin_misuse",
    )

    def __init__(
        self,
        message: str,
        *,
        violation: Literal[
            "mutually_exclusive", "no_browser_misuse", "secret_stdin_misuse"
        ],
        detected_auth_type: str | None = None,
    ) -> None:
        """Initialize InvalidArgumentError.

        Args:
            message: Human-readable error message.
            violation: Discriminator for the kind of misuse. One of
                ``"mutually_exclusive"``, ``"no_browser_misuse"``,
                ``"secret_stdin_misuse"``.
            detected_auth_type: The auth type the orchestrator resolved
                from the supplied flags / env. ``None`` only when the
                violation was caught BEFORE detection ran (currently
                no such case, but kept optional for future-proofing).
        """
        if violation not in self._VALID_VIOLATIONS:
            raise ValueError(
                f"Invalid violation {violation!r}; must be one of "
                f"{self._VALID_VIOLATIONS}."
            )
        details: dict[str, Any] = {"violation": violation}
        if detected_auth_type is not None:
            details["detected_auth_type"] = detected_auth_type
        super().__init__(message, details=details)
        self._code = "INVALID_ARGUMENT"

    @property
    def violation(self) -> str:
        """The kind of misuse — see ``_VALID_VIOLATIONS``."""
        return str(self._details.get("violation", ""))

    @property
    def detected_auth_type(self) -> str | None:
        """The auth type the orchestrator resolved (or ``None`` if pre-detection)."""
        value = self._details.get("detected_auth_type")
        return str(value) if value is not None else None


class AccountInUseError(ConfigError):
    """Account is referenced by one or more targets and cannot be removed.

    Raised by ``mp.accounts.remove(name)`` when the account is referenced by
    one or more ``[targets.NAME]`` blocks and the caller did not pass
    ``force=True``. The list of dependent target names is available in
    ``referenced_by`` so callers can show a helpful error message or pass
    ``force=True`` to delete the account and orphan the targets.
    """

    def __init__(
        self, account_name: str, referenced_by: list[str] | None = None
    ) -> None:
        """Initialize AccountInUseError.

        Args:
            account_name: The account that callers tried to remove.
            referenced_by: Names of targets that reference the account.
        """
        targets = referenced_by or []
        if targets:
            target_str = ", ".join(f"'{t}'" for t in targets)
            message = (
                f"Account '{account_name}' is referenced by target(s): {target_str}. "
                f"Pass `force=True` to remove anyway."
            )
        else:
            message = (
                f"Account '{account_name}' is in use. Pass `force=True` to remove."
            )

        details: dict[str, Any] = {
            "account_name": account_name,
            "referenced_by": list(targets),
        }
        super().__init__(message, details=details)
        self._code = "ACCOUNT_IN_USE"

    @property
    def account_name(self) -> str:
        """The account name that callers tried to remove."""
        return str(self._details.get("account_name", ""))

    @property
    def referenced_by(self) -> list[str]:
        """Target names that reference the account."""
        targets = self._details.get("referenced_by")
        return targets if isinstance(targets, list) else []


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


class EventNotFoundError(MixpanelHeadlessError):
    """Event name not found in Mixpanel project.

    Raised when an event name is not found. Includes suggestions for
    similar event names based on case-insensitive and substring matching
    to help users correct typos or case mismatches.

    Example:
        ```python
        try:
            properties = discovery.list_properties("sign up")
        except EventNotFoundError as e:
            print(f"Event '{e.event_name}' not found.")
            if e.similar_events:
                print(f"Did you mean: {', '.join(e.similar_events)}")
        ```
    """

    def __init__(
        self,
        event_name: str,
        similar_events: list[str] | None = None,
    ) -> None:
        """Initialize EventNotFoundError.

        Args:
            event_name: The event name that was not found.
            similar_events: List of similar event names to suggest.
        """
        self._event_name = event_name
        self._similar_events = similar_events or []

        message = f"Event '{event_name}' not found."
        if self._similar_events:
            suggestions = ", ".join(f"'{e}'" for e in self._similar_events[:5])
            message += f" Did you mean: {suggestions}?"

        details: dict[str, Any] = {
            "event_name": event_name,
            "similar_events": self._similar_events,
        }

        super().__init__(message, code="EVENT_NOT_FOUND", details=details)

    @property
    def event_name(self) -> str:
        """The event name that was not found."""
        return self._event_name

    @property
    def similar_events(self) -> list[str]:
        """List of similar event names."""
        return self._similar_events


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


# Validation Exceptions


class DateRangeTooLargeError(MixpanelHeadlessError):
    """Date range exceeds maximum allowed by Mixpanel API.

    The Mixpanel Export API limits requests to 100 days maximum.
    Split large date ranges into smaller chunks.

    Example:
        ```python
        try:
            events = ws.stream_events(from_date="2024-01-01", to_date="2024-06-30")
        except DateRangeTooLargeError as e:
            print(f"Range is {e.days_requested} days, max is {e.max_days}")
        ```
    """

    def __init__(
        self,
        from_date: str,
        to_date: str,
        days_requested: int,
        max_days: int = 100,
    ) -> None:
        """Initialize DateRangeTooLargeError.

        Args:
            from_date: Start date that was requested.
            to_date: End date that was requested.
            days_requested: Number of days in the requested range.
            max_days: Maximum allowed days (default: 100).
        """
        self._from_date = from_date
        self._to_date = to_date
        self._days_requested = days_requested
        self._max_days = max_days

        message = (
            f"Date range from {from_date} to {to_date} spans {days_requested} days, "
            f"but maximum is {max_days} days. Split your request into smaller chunks."
        )

        details: dict[str, Any] = {
            "from_date": from_date,
            "to_date": to_date,
            "days_requested": days_requested,
            "max_days": max_days,
        }

        super().__init__(message, code="DATE_RANGE_TOO_LARGE", details=details)

    @property
    def from_date(self) -> str:
        """Start date that was requested."""
        return self._from_date

    @property
    def to_date(self) -> str:
        """End date that was requested."""
        return self._to_date

    @property
    def days_requested(self) -> int:
        """Number of days in the requested range."""
        return self._days_requested

    @property
    def max_days(self) -> int:
        """Maximum allowed days."""
        return self._max_days


# OAuth Exceptions


class OAuthError(MixpanelHeadlessError):
    """OAuth authentication flow error.

    Raised for failures during the OAuth 2.0 PKCE flow, including token
    exchange, token refresh, client registration, callback timeout,
    port unavailability, and browser launch failures.

    Error codes:
    - OAUTH_TOKEN_ERROR: Token exchange or validation failed
    - OAUTH_REFRESH_ERROR: Token refresh failed
    - OAUTH_REGISTRATION_ERROR: Dynamic Client Registration failed
    - OAUTH_TIMEOUT: Callback server timed out waiting for authorization
    - OAUTH_PORT_ERROR: All callback ports are occupied
    - OAUTH_BROWSER_ERROR: Could not open browser for authorization

    Example:
        ```python
        try:
            flow = OAuthFlow(region="us")
            tokens = flow.login()
        except OAuthError as e:
            print(f"OAuth failed: {e.message} (code: {e.code})")
        ```
    """

    def __init__(
        self,
        message: str,
        code: str = "OAUTH_TOKEN_ERROR",
        details: dict[str, Any] | None = None,
    ) -> None:
        """Initialize OAuthError.

        Args:
            message: Human-readable error message.
            code: Machine-readable error code. One of: OAUTH_TOKEN_ERROR,
                OAUTH_REFRESH_ERROR, OAUTH_REGISTRATION_ERROR, OAUTH_TIMEOUT,
                OAUTH_PORT_ERROR, OAUTH_BROWSER_ERROR.
            details: Additional structured data about the error.
        """
        super().__init__(message, code=code, details=details)


class RegionProbeError(OAuthError):
    """Raised when no region accepts the credential during region probing.

    The region probe walks a configured order (default ``us`` → ``eu`` →
    ``in``) against ``/api/app/me``, returning the first 200. When every
    probe attempt fails, this exception is raised carrying the full
    attempt list for diagnostic and telemetry use.

    A status code of ``0`` indicates the request never reached the server
    (network error); the third tuple element carries the failure detail
    (HTTP response text or the network error reason).

    See :class:`RegionProbeNetworkError` for the all-network-error
    subclass — the probe distinguishes "credential rejected" from
    "could not reach any region" so the CLI can render different
    remediation hints.

    Example:
        ```python
        try:
            result = probe_region(client_factory, headers)
        except RegionProbeError as exc:
            for region, status, body in exc.attempts:
                print(f"{region}: {status} {body}")
        ```
    """

    def __init__(
        self,
        message: str,
        *,
        attempts: list[tuple[Region, int, str]],
        code: str = "OAUTH_REGION_PROBE_FAILED",
    ) -> None:
        """Initialize RegionProbeError.

        Args:
            message: Human-readable error message.
            attempts: Ordered list of ``(region, status_code, error_body)``
                tuples for every probed region. ``status_code`` is ``0``
                for network errors; ``error_body`` carries the failure
                detail.
            code: Machine-readable error code. Defaults to
                ``OAUTH_REGION_PROBE_FAILED`` for the generic case;
                :class:`RegionProbeNetworkError` overrides to
                ``OAUTH_NETWORK_UNREACHABLE``.
        """
        self._attempts: list[tuple[Region, int, str]] = list(attempts)
        super().__init__(
            message,
            code=code,
            details={"attempts": [list(a) for a in self._attempts]},
        )

    @property
    def attempts(self) -> list[tuple[Region, int, str]]:
        """Ordered list of ``(region, status_code, error_body)`` tuples."""
        return list(self._attempts)

    def to_dict(self) -> dict[str, Any]:
        """Serialize the exception to a JSON-friendly dict.

        Includes ``attempts`` at the top level so consumers can inspect
        the per-region probe outcomes without unpacking ``details``.

        Returns:
            Dictionary with keys ``code``, ``message``, ``details``, and
            ``attempts``. Each ``attempts`` entry is a 3-element list
            ``[region, status_code, error_body]``.
        """
        base = super().to_dict()
        base["attempts"] = [list(a) for a in self._attempts]
        return base


class RegionProbeNetworkError(RegionProbeError):
    """Raised when every region probe attempt failed at the network layer.

    Subclass of :class:`RegionProbeError` used when ALL recorded
    attempts have ``status_code == 0`` — i.e. the credential was never
    actually evaluated because no region was reachable (DNS failure,
    TLS rejection, captive portal, no internet). The CLI catches this
    before the generic ``RegionProbeError`` so it can render "could
    not reach any Mixpanel region" instead of "credential not valid",
    which would mislead a user who is actually offline.

    Carries the same ``attempts`` shape as the parent so existing
    consumers can render the per-region detail without changes.
    """

    def __init__(
        self,
        message: str,
        *,
        attempts: list[tuple[Region, int, str]],
    ) -> None:
        """Initialize RegionProbeNetworkError.

        Args:
            message: Human-readable error message.
            attempts: Ordered list of ``(region, 0, error_body)``
                tuples — every entry must have status 0 by construction
                (the probe loop only raises this subclass when that
                invariant holds).
        """
        super().__init__(
            message,
            attempts=attempts,
            code="OAUTH_NETWORK_UNREACHABLE",
        )


class WorkspaceScopeError(MixpanelHeadlessError):
    """Scope resolution error (workspace or organization).

    Raised when an auth-axis identifier cannot be resolved during App
    API requests. Originally introduced for workspace resolution; also
    raised when the organization ID for an org-scoped business-context
    call cannot be auto-derived from the cached ``/me`` response.

    Error codes:
    - NO_WORKSPACES: Project has no accessible workspaces
    - AMBIGUOUS_WORKSPACE: Multiple workspaces, none default; must specify --workspace-id
    - WORKSPACE_NOT_FOUND: Explicit workspace ID doesn't match any workspace
    - ORGANIZATION_AMBIGUOUS: Cannot auto-resolve the organization for an
      org-scoped call (active project absent from /me AND >1 accessible
      organization). The ``details`` dict carries ``project_id`` and
      ``available_organizations``. Pass ``organization_id=N`` explicitly
      to bypass auto-resolution.

    Example:
        ```python
        try:
            workspace_id = ws.resolve_workspace_id()
        except WorkspaceScopeError as e:
            print(f"Scope issue: {e.message} (code: {e.code})")
        ```
    """

    def __init__(
        self,
        message: str,
        code: str = "NO_WORKSPACES",
        details: dict[str, Any] | None = None,
    ) -> None:
        """Initialize WorkspaceScopeError.

        Args:
            message: Human-readable error message.
            code: Machine-readable error code. One of: NO_WORKSPACES,
                AMBIGUOUS_WORKSPACE, WORKSPACE_NOT_FOUND,
                ORGANIZATION_AMBIGUOUS.
            details: Additional structured data about the error.
        """
        super().__init__(message, code=code, details=details)


# Business Context Validation


class BusinessContextValidationError(MixpanelHeadlessError):
    """Business context content failed client-side validation.

    Raised by ``Workspace.set_business_context()`` when the supplied
    content exceeds ``BUSINESS_CONTEXT_MAX_CHARS`` (50,000 characters).
    The check runs before the HTTP call so callers can fail fast and
    avoid a wasted round-trip — the server enforces the same limit
    server-side and would otherwise return ``QueryError`` (HTTP 400).

    The ``details`` dict carries ``length`` (the actual content length)
    and ``max`` (the configured limit) for programmatic recovery.

    Example:
        ```python
        try:
            ws.set_business_context("x" * 60_000, level="project")
        except BusinessContextValidationError as e:
            print(f"Too long: {e.details['length']} > {e.details['max']}")
        ```
    """

    def __init__(
        self,
        message: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        """Initialize BusinessContextValidationError.

        Args:
            message: Human-readable error message.
            details: Additional structured data — typically ``length``
                and ``max``.
        """
        super().__init__(
            message,
            code="BUSINESS_CONTEXT_TOO_LONG",
            details=details,
        )


# Bookmark Validation


@dataclass(frozen=True)
class ValidationError:
    """A single validation issue found in query arguments or bookmark params.

    Used by the bookmark validation engine to report all issues found in a
    single pass, enabling agents to fix multiple problems at once rather
    than discovering them one at a time.

    Attributes:
        path: JSONPath-like location of the error (e.g.
            ``"sections.show[0].measurement.math"``).
        message: Human-readable description of the issue.
        code: Machine-readable error code for programmatic handling
            (e.g. ``"INVALID_MATH_TYPE"``).
        severity: ``"error"`` blocks execution; ``"warning"`` is informational.
        suggestion: Fuzzy-matched valid alternatives, if applicable.
        fix: JSON structure template to correct the error, if applicable.

    Example:
        ```python
        error = ValidationError(
            path="sections.show[0].measurement.math",
            message="Invalid math type 'totl'",
            code="INVALID_MATH_TYPE",
            suggestion=("total",),
        )
        print(error)  # [ERROR] sections.show[0]...: Invalid math type 'totl'
        ```
    """

    path: str
    """JSONPath-like location of the error."""

    message: str
    """Human-readable description of the issue."""

    code: str = "VALIDATION_ERROR"
    """Machine-readable error code for programmatic handling."""

    severity: Literal["error", "warning"] = "error"
    """``"error"`` blocks execution; ``"warning"`` is informational."""

    suggestion: tuple[str, ...] | None = None
    """Fuzzy-matched valid alternatives, if applicable."""

    fix: dict[str, Any] | None = None
    """JSON structure template to correct the error, if applicable."""

    def to_dict(self) -> dict[str, Any]:
        """Serialize for JSON output.

        Returns:
            Dictionary with all ValidationError fields. Keys with ``None``
            values are omitted for cleaner output.
        """
        result: dict[str, Any] = {
            "path": self.path,
            "message": self.message,
            "code": self.code,
            "severity": self.severity,
        }
        if self.suggestion is not None:
            result["suggestion"] = list(self.suggestion)
        if self.fix is not None:
            result["fix"] = self.fix
        return result

    def __str__(self) -> str:
        """Return formatted error string.

        Returns:
            Formatted string with severity prefix, path, and message.
        """
        prefix = "WARNING" if self.severity == "warning" else "ERROR"
        s = f"[{prefix}] {self.path}: {self.message}"
        if self.suggestion:
            s += f" Did you mean '{self.suggestion[0]}'?"
        return s


class BookmarkValidationError(MixpanelHeadlessError):
    """Bookmark params failed validation.

    Contains all validation errors found, enabling agents to fix
    multiple issues in a single pass rather than one at a time.
    Integrates into the ``MixpanelHeadlessError`` hierarchy so callers
    using ``except MixpanelHeadlessError`` will catch these.

    Attributes:
        errors: All validation errors found (both errors and warnings).
        error_count: Number of severity="error" items.
        warning_count: Number of severity="warning" items.

    Example:
        ```python
        try:
            result = ws.query("Login", math="totl")
        except BookmarkValidationError as e:
            print(f"{e.error_count} errors, {e.warning_count} warnings")
            for err in e.errors:
                print(f"  {err.path}: {err.message}")
                if err.suggestion:
                    print(f"    Did you mean: {err.suggestion[0]}?")
        ```
    """

    def __init__(self, errors: Sequence[ValidationError]) -> None:
        """Initialize BookmarkValidationError.

        Args:
            errors: Sequence of validation errors found. Must contain at
                least one error with severity="error".
        """
        self._errors = tuple(errors)
        self._error_count = sum(1 for e in self._errors if e.severity == "error")
        self._warning_count = sum(1 for e in self._errors if e.severity == "warning")

        # Build summary message
        parts: list[str] = []
        for err in self._errors:
            if err.severity == "error":
                parts.append(f"  {err}")
        summary = "\n".join(parts)
        message = (
            f"Bookmark validation failed with {self._error_count} error(s)"
            f" and {self._warning_count} warning(s):\n{summary}"
        )

        details: dict[str, Any] = {
            "error_count": self._error_count,
            "warning_count": self._warning_count,
            "errors": [e.to_dict() for e in self._errors],
        }
        super().__init__(message, code="BOOKMARK_VALIDATION_ERROR", details=details)

    @property
    def errors(self) -> tuple[ValidationError, ...]:
        """All validation errors found (both errors and warnings)."""
        return self._errors

    @property
    def error_count(self) -> int:
        """Number of severity="error" items."""
        return self._error_count

    @property
    def warning_count(self) -> int:
        """Number of severity="warning" items."""
        return self._warning_count
