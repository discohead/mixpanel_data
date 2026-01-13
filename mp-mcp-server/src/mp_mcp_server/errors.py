"""Error handling for MCP tools.

This module provides a decorator for converting mixpanel_data exceptions
to FastMCP ToolError with appropriate messages and actionable guidance.

Example:
    ```python
    @mcp.tool
    @handle_errors
    def fetch_events(ctx: Context, from_date: str) -> dict:
        ws = get_workspace(ctx)
        return ws.fetch_events(from_date=from_date).to_dict()
    ```
"""

import json
from collections.abc import Callable
from functools import wraps
from typing import Any, ParamSpec, TypeVar

from fastmcp.exceptions import ToolError

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

P = ParamSpec("P")
R = TypeVar("R")


def format_rich_error(
    summary: str,
    error: MixpanelDataError,
    suggestions: list[str] | None = None,
) -> str:
    """Format error with structured details for agent parsing.

    Creates an error message with three parts:
    1. Human-readable summary line
    2. JSON block with full error details (parseable by agents)
    3. Actionable suggestions

    Args:
        summary: Human-readable summary line.
        error: The exception with to_dict() method.
        suggestions: Optional list of actionable suggestions.

    Returns:
        Formatted error message with embedded JSON.

    Example:
        ```python
        msg = format_rich_error(
            "Rate limited by Mixpanel API.",
            error,
            ["Wait 60 seconds before retrying"]
        )
        ```
    """
    lines = [summary, ""]

    # Add structured details block for agent parsing
    details = error.to_dict()
    lines.append("Error Details:")
    lines.append(json.dumps(details, indent=2, default=str))

    # Add actionable suggestions
    if suggestions:
        lines.append("")
        lines.append("Suggestions:")
        for suggestion in suggestions:
            lines.append(f"- {suggestion}")

    return "\n".join(lines)


def _get_error_details(error: MixpanelDataError) -> dict[str, Any]:
    """Extract error details as a dictionary for JSON serialization.

    Args:
        error: The exception to extract details from.

    Returns:
        Dictionary with error code, message, and type-specific details.
    """
    return error.to_dict()


def handle_errors(func: Callable[P, R]) -> Callable[P, R]:
    """Decorator to convert mixpanel_data exceptions to FastMCP ToolError.

    Wraps a tool function to catch mixpanel_data exceptions and convert them
    to ToolError with user-friendly messages and actionable guidance.

    Args:
        func: The tool function to wrap.

    Returns:
        The wrapped function that converts exceptions.

    Example:
        ```python
        @handle_errors
        def my_tool(ctx: Context) -> dict:
            # If this raises RateLimitError, it becomes a ToolError
            # with retry guidance
            return ws.segmentation(event="login").to_dict()
        ```
    """

    @wraps(func)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
        try:
            return func(*args, **kwargs)

        # JQL-specific errors (must be before QueryError - it's a subclass)
        except JQLSyntaxError as e:
            suggestions = [
                "Check the script syntax at the indicated line",
                "Verify property names and function calls",
                "See Mixpanel JQL documentation for correct usage",
            ]
            # Include script snippet if available
            summary = f"JQL script error: {e.error_type}: {e.error_message}"
            if e.line_info:
                summary += f"\n{e.line_info}"
            raise ToolError(format_rich_error(summary, e, suggestions)) from e

        # API errors - specific types first
        except RateLimitError as e:
            retry_msg = (
                f"Retry after {e.retry_after} seconds."
                if e.retry_after
                else "Wait before retrying."
            )
            suggestions = [
                retry_msg,
                "Use fetch_events/fetch_profiles for bulk data to reduce API calls",
                "Consider caching results locally with SQL queries",
            ]
            raise ToolError(
                format_rich_error("Rate limited by Mixpanel API.", e, suggestions)
            ) from e

        except AuthenticationError as e:
            suggestions = [
                "Check credentials in environment variables (MP_USERNAME, MP_SECRET)",
                "Verify ~/.mp/config.toml has valid credentials",
                "Ensure the service account has access to this project",
            ]
            raise ToolError(
                format_rich_error("Authentication failed.", e, suggestions)
            ) from e

        except ServerError as e:
            suggestions = [
                "This may be a transient issue - try again in a few moments",
                "Check Mixpanel status page if errors persist",
            ]
            raise ToolError(
                format_rich_error(
                    f"Mixpanel server error (HTTP {e.status_code}).", e, suggestions
                )
            ) from e

        except QueryError as e:
            status_info = f" (HTTP {e.status_code})" if e.status_code else ""
            suggestions = [
                "Check query parameters for typos or invalid values",
                "Verify event/property names exist using list_events/list_properties",
            ]
            raise ToolError(
                format_rich_error(f"Query error{status_info}.", e, suggestions)
            ) from e

        # Validation errors
        except EventNotFoundError as e:
            suggestions = ["Use list_events to see available events"]
            if e.similar_events:
                suggestions.insert(
                    0, f"Did you mean: {', '.join(e.similar_events[:5])}?"
                )
            raise ToolError(
                format_rich_error(f"Event not found: {e.event_name}", e, suggestions)
            ) from e

        except DateRangeTooLargeError as e:
            suggestions = [
                f"Maximum date range is {e.max_days} days per request",
                "Split into multiple requests and use append=True to combine results",
                f"Example: fetch from {e.from_date} to a date within {e.max_days} days",
            ]
            raise ToolError(
                format_rich_error(
                    f"Date range too large: {e.days_requested} days requested.",
                    e,
                    suggestions,
                )
            ) from e

        # Storage errors
        except TableExistsError as e:
            suggestions = [
                "Use drop_table to remove the existing table first",
                "Choose a different table name",
                "Use append=True to add data to the existing table",
            ]
            raise ToolError(format_rich_error(str(e), e, suggestions)) from e

        except TableNotFoundError as e:
            suggestions = [
                "Use list_tables to see available tables",
                "Fetch data first with fetch_events or fetch_profiles",
            ]
            raise ToolError(format_rich_error(str(e), e, suggestions)) from e

        except DatabaseLockedError as e:
            suggestions = [
                "Another mp command may be running - wait for it to complete",
                "Check for other processes using the database file",
            ]
            if e.holding_pid:
                suggestions.insert(0, f"Database locked by process {e.holding_pid}")
            raise ToolError(format_rich_error(str(e), e, suggestions)) from e

        except DatabaseNotFoundError as e:
            suggestions = [
                "Run fetch_events or fetch_profiles first to create the database",
                "Check the database path in your configuration",
            ]
            raise ToolError(format_rich_error(str(e), e, suggestions)) from e

        # Config errors
        except AccountNotFoundError as e:
            suggestions = ["Check account name spelling"]
            if e.available_accounts:
                suggestions.insert(
                    0, f"Available accounts: {', '.join(e.available_accounts)}"
                )
            raise ToolError(format_rich_error(str(e), e, suggestions)) from e

        except AccountExistsError as e:
            suggestions = [
                "Choose a different account name",
                "Delete the existing account first if you want to replace it",
            ]
            raise ToolError(format_rich_error(str(e), e, suggestions)) from e

        except ConfigError as e:
            suggestions = [
                "Check ~/.mp/config.toml for configuration errors",
                "Verify environment variables are set correctly",
            ]
            raise ToolError(format_rich_error(str(e), e, suggestions)) from e

        # Catch-all for any other MixpanelDataError
        except MixpanelDataError as e:
            raise ToolError(format_rich_error(f"Mixpanel error: {e}", e)) from e

    return wrapper
