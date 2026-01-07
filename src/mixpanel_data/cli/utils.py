"""CLI utility functions and error handling.

This module provides shared utilities for the CLI:
- ExitCode enum for standardized exit codes
- handle_errors decorator for exception-to-exit-code mapping
- Console instances for stdout/stderr separation
- Lazy workspace/config initialization helpers
- status_spinner context manager for long-running operations
- _apply_jq_filter for jq-based JSON filtering
"""

from __future__ import annotations

import functools
import json
import os
from collections.abc import Callable, Generator
from contextlib import contextmanager
from enum import IntEnum
from typing import TYPE_CHECKING, Any, Protocol, TypeVar

import jq  # type: ignore[import-not-found]
import typer
from rich.console import Console

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

if TYPE_CHECKING:
    from mixpanel_data._internal.config import ConfigManager
    from mixpanel_data.workspace import Workspace


class ResultWithTableAndDict(Protocol):
    """Protocol for result objects that support both table and dict output."""

    def to_table_dict(self) -> list[dict[str, Any]]: ...
    def to_dict(self) -> dict[str, Any]: ...


# Console instances for stdout/stderr separation
# Data output goes to stdout; progress/errors go to stderr
console = Console()
err_console = Console(stderr=True, no_color=bool(os.environ.get("NO_COLOR")))


class ExitCode(IntEnum):
    """Standardized exit codes for CLI commands.

    Exit codes follow Unix conventions:
    - 0: Success
    - 1-5: Application-specific errors
    - 130: Interrupted by SIGINT (Ctrl+C)
    """

    SUCCESS = 0
    GENERAL_ERROR = 1
    AUTH_ERROR = 2
    INVALID_ARGS = 3
    NOT_FOUND = 4
    RATE_LIMIT = 5
    INTERRUPTED = 130


F = TypeVar("F", bound=Callable[..., Any])


def handle_errors(func: F) -> F:
    """Decorator to convert library exceptions to CLI exit codes.

    Maps MixpanelDataError subclasses to appropriate exit codes and
    displays formatted error messages to stderr.

    Usage:
        @handle_errors
        def my_command(ctx: typer.Context):
            workspace = get_workspace(ctx)
            result = workspace.some_method()
            output_result(ctx, result.to_dict())
    """

    @functools.wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        try:
            return func(*args, **kwargs)
        except AuthenticationError as e:
            err_console.print(f"[red]Authentication error:[/red] {e.message}")
            # Show request context to help debug auth issues
            if e.request_url:
                # Extract endpoint without sensitive params
                endpoint = e.request_url.split("?")[0].split("/")[-1]
                err_console.print(f"  [dim]Endpoint:[/dim] {endpoint}")
            # Show API error message if available
            if isinstance(e.response_body, dict):
                api_error = e.response_body.get("error", "")
                if api_error:
                    err_console.print(f"  [dim]API response:[/dim] {api_error}")
            raise typer.Exit(ExitCode.AUTH_ERROR) from None
        except AccountNotFoundError as e:
            err_console.print(f"[red]Account not found:[/red] {e.account_name}")
            if e.available_accounts:
                err_console.print(
                    f"Available accounts: {', '.join(e.available_accounts)}"
                )
            raise typer.Exit(ExitCode.NOT_FOUND) from None
        except AccountExistsError as e:
            err_console.print(f"[red]Account exists:[/red] {e.account_name}")
            raise typer.Exit(ExitCode.GENERAL_ERROR) from None
        except TableExistsError as e:
            err_console.print(f"[red]Table exists:[/red] {e.table_name}")
            err_console.print("Use --replace to overwrite the existing table.")
            raise typer.Exit(ExitCode.GENERAL_ERROR) from None
        except TableNotFoundError as e:
            err_console.print(f"[red]Table not found:[/red] {e.table_name}")
            raise typer.Exit(ExitCode.NOT_FOUND) from None
        except DatabaseLockedError as e:
            err_console.print(f"[yellow]Database locked:[/yellow] {e.db_path}")
            if e.holding_pid:
                err_console.print(f"  [dim]Held by PID:[/dim] {e.holding_pid}")
            err_console.print("Another mp command may be running. Try again shortly.")
            raise typer.Exit(ExitCode.GENERAL_ERROR) from None
        except DatabaseNotFoundError as e:
            err_console.print(f"[yellow]No data yet:[/yellow] {e.db_path}")
            err_console.print(
                "Run 'mp fetch events' or 'mp fetch profiles' to create the database."
            )
            raise typer.Exit(ExitCode.NOT_FOUND) from None
        except RateLimitError as e:
            err_console.print(f"[yellow]Rate limited:[/yellow] {e.message}")
            if e.retry_after:
                err_console.print(
                    f"[cyan]Wait {e.retry_after} seconds before retrying.[/cyan]"
                )
            # Show which endpoint was hit
            if e.request_url:
                endpoint = e.request_url.split("/")[-1].split("?")[0]
                err_console.print(f"[dim]Endpoint: {endpoint}[/dim]")
            err_console.print(
                "[yellow]Tip:[/yellow] Use 'mp fetch' for bulk data, "
                "then query locally with SQL."
            )
            raise typer.Exit(ExitCode.RATE_LIMIT) from None
        except EventNotFoundError as e:
            err_console.print(f"[red]Event not found:[/red] '{e.event_name}'")
            if e.similar_events:
                suggestions = ", ".join(f"'{s}'" for s in e.similar_events[:5])
                err_console.print(f"Did you mean: {suggestions}?")
            raise typer.Exit(ExitCode.NOT_FOUND) from None
        except DateRangeTooLargeError as e:
            err_console.print(f"[red]Date range too large:[/red] {e.message}")
            err_console.print(
                f"  [dim]Requested:[/dim] {e.from_date} to {e.to_date} "
                f"({e.days_requested} days)"
            )
            err_console.print(f"  [dim]Maximum:[/dim] {e.max_days} days")
            err_console.print(
                "[yellow]Tip:[/yellow] Split into multiple fetches, e.g.:\n"
                f"  mp fetch events --from {e.from_date} --to <midpoint>\n"
                f"  mp fetch events --from <midpoint+1> --to {e.to_date} --append"
            )
            raise typer.Exit(ExitCode.INVALID_ARGS) from None
        except JQLSyntaxError as e:
            # JQLSyntaxError must be caught before QueryError (it's a subclass)
            err_console.print(
                f"[red]JQL error:[/red] {e.error_type}: {e.error_message}"
            )
            # Show line info if available (code snippet with caret)
            if e.line_info:
                err_console.print(f"[dim]{e.line_info}[/dim]")
            # Show stack trace if available
            if e.stack_trace:
                err_console.print(f"  [dim]Location:[/dim] {e.stack_trace}")
            # Show the script that failed (truncated for readability)
            if e.script:
                script_preview = e.script.strip()
                if len(script_preview) > 200:
                    script_preview = script_preview[:200] + "..."
                err_console.print(f"  [dim]Script:[/dim]\n{script_preview}")
            # Show raw error for debugging if it has more info
            if e.raw_error and e.raw_error != e.error_message:
                err_console.print(f"  [dim]Raw error:[/dim] {e.raw_error}")
            raise typer.Exit(ExitCode.INVALID_ARGS) from None
        except QueryError as e:
            err_console.print(f"[red]Query error:[/red] {e.message}")
            # Show response body - often contains the actual API error message
            if e.response_body:
                if isinstance(e.response_body, dict):
                    api_error = e.response_body.get("error", "")
                    if api_error and api_error not in e.message:
                        err_console.print(f"  [dim]API error:[/dim] {api_error}")
                elif (
                    isinstance(e.response_body, str)
                    and e.response_body not in e.message
                ):
                    # Truncate long response bodies
                    body_preview = e.response_body[:200]
                    if len(e.response_body) > 200:
                        body_preview += "..."
                    err_console.print(f"  [dim]Response:[/dim] {body_preview}")
            # Show non-sensitive request context for debugging
            if e.request_params:
                for key, value in e.request_params.items():
                    if key not in ("project_id",):
                        err_console.print(f"  [dim]{key}:[/dim] {value}")
            # Show request body if present (e.g., for POST requests)
            if e.request_body:
                for key, value in e.request_body.items():
                    if key not in ("script",):  # Don't duplicate JQL script
                        val_str = str(value)
                        if len(val_str) > 100:
                            val_str = val_str[:100] + "..."
                        err_console.print(f"  [dim]{key}:[/dim] {val_str}")
            # Provide contextual hints
            if e.status_code == 403:
                err_console.print(
                    "[yellow]Hint:[/yellow] Check service account permissions."
                )
            raise typer.Exit(ExitCode.INVALID_ARGS) from None
        except ServerError as e:
            err_console.print(f"[red]Server error ({e.status_code}):[/red] {e.message}")
            # Show response body - may contain actionable error details
            if e.response_body:
                if isinstance(e.response_body, dict):
                    api_error = e.response_body.get("error", "")
                    if api_error:
                        err_console.print(f"  [dim]API error:[/dim] {api_error}")
                elif isinstance(e.response_body, str):
                    body_preview = e.response_body[:200]
                    if len(e.response_body) > 200:
                        body_preview += "..."
                    err_console.print(f"  [dim]Response:[/dim] {body_preview}")
            # Show endpoint for context
            if e.request_url:
                endpoint = e.request_url.split("?")[0].split("/")[-1]
                err_console.print(f"  [dim]Endpoint:[/dim] {endpoint}")
            err_console.print(
                "[yellow]Hint:[/yellow] This may be a transient issue. "
                "Try again in a few moments."
            )
            raise typer.Exit(ExitCode.GENERAL_ERROR) from None
        except ConfigError as e:
            err_console.print(f"[red]Configuration error:[/red] {e.message}")
            raise typer.Exit(ExitCode.GENERAL_ERROR) from None
        except MixpanelDataError as e:
            err_console.print(f"[red]Error:[/red] {e.message}")
            raise typer.Exit(ExitCode.GENERAL_ERROR) from None
        except ValueError as e:
            # Handle validation errors (e.g., invalid date format)
            err_console.print(f"[red]Invalid argument:[/red] {e}")
            raise typer.Exit(ExitCode.INVALID_ARGS) from None

    return wrapper  # type: ignore[return-value]


def get_workspace(ctx: typer.Context, *, read_only: bool = False) -> Workspace:
    """Get or create workspace from context.

    Lazily initializes a Workspace instance, respecting the --account
    global option. The workspace is cached in the context for reuse.

    Note: The read_only parameter only applies when creating a new workspace.
    If a workspace already exists in context, that instance is returned
    regardless of the read_only parameter. This is safe because each CLI
    command runs in a separate process, so caching within a single command
    invocation doesn't cause read_only mismatches across commands.

    Args:
        ctx: Typer context with global options in obj dict.
        read_only: If True, open database in read-only mode allowing
            concurrent reads. Defaults to False (write access) matching
            DuckDB's native behavior. Pass True for read-only commands
            (query, inspect) to enable concurrent access.

    Returns:
        Configured Workspace instance.

    Raises:
        AccountNotFoundError: If specified account doesn't exist.
        ConfigError: If no credentials can be resolved.
    """
    from mixpanel_data.workspace import Workspace

    if "workspace" not in ctx.obj or ctx.obj["workspace"] is None:
        account = ctx.obj.get("account")
        ctx.obj["workspace"] = Workspace(account=account, read_only=read_only)
    workspace: Workspace = ctx.obj["workspace"]
    return workspace


def get_config(ctx: typer.Context) -> ConfigManager:
    """Get or create ConfigManager from context.

    Lazily initializes a ConfigManager instance. The instance is
    cached in the context for reuse.

    Args:
        ctx: Typer context with global options in obj dict.

    Returns:
        ConfigManager instance.
    """
    from mixpanel_data._internal.config import ConfigManager

    if "config" not in ctx.obj or ctx.obj["config"] is None:
        ctx.obj["config"] = ConfigManager()
    config: ConfigManager = ctx.obj["config"]
    return config


def _apply_jq_filter(json_str: str, filter_expr: str) -> list[Any]:
    """Apply jq filter to JSON string.

    Compiles and applies a jq filter expression to the input JSON string,
    returning the filtered results as a list of Python objects. The caller
    is responsible for formatting the output (JSON vs JSONL).

    Args:
        json_str: JSON string to filter.
        filter_expr: jq filter expression (e.g., ".name", ".[0]", "map(.x)").

    Returns:
        List of filtered results. May be empty, single-element, or multi-element.
        Caller should format based on output format requirements.

    Raises:
        typer.Exit: If JSON parsing fails, filter syntax is invalid, or
            runtime error occurs. Uses ExitCode.INVALID_ARGS (3).

    Example:
        ```python
        _apply_jq_filter('{"name": "test"}', '.name')
        # ['test']

        _apply_jq_filter('[1, 2, 3]', 'map(. * 2)')
        # [[2, 4, 6]]
        ```
    """
    try:
        # Parse the input JSON
        data = json.loads(json_str)
    except json.JSONDecodeError as e:
        err_console.print(f"[red]Invalid JSON input:[/red] {e.msg}")
        # Suppress chain: typer.Exit is a CLI exit signal, not a debugging exception.
        # Users want clean error messages, not stack traces.
        raise typer.Exit(ExitCode.INVALID_ARGS) from None

    try:
        # Compile and apply the jq filter
        compiled = jq.compile(filter_expr)
        results = list(compiled.input(data))
    except ValueError as e:
        # jq raises ValueError for both syntax errors and runtime errors
        error_msg = str(e)
        # Clean up the error message - remove "jq: error: " prefix if present
        if error_msg.startswith("jq: error: "):
            error_msg = error_msg[11:]
        err_console.print(f"[red]jq filter error:[/red] {error_msg}")
        # Suppress chain: typer.Exit is a CLI exit signal, not a debugging exception.
        # Users want clean error messages, not stack traces.
        raise typer.Exit(ExitCode.INVALID_ARGS) from None

    return results


def present_result(
    ctx: typer.Context,
    result: ResultWithTableAndDict,
    format: str,
    *,
    jq_filter: str | None = None,
) -> None:
    """Select appropriate dict format and output the result.

    For table format, uses normalized to_table_dict() for readable output.
    For other formats (json, jsonl, csv, plain), uses to_dict() to preserve
    the original nested structure.

    This centralizes the logic for choosing between to_table_dict() and
    to_dict(), eliminating duplication across all query commands.

    Args:
        ctx: Typer context with global options in obj dict.
        result: Result object with to_table_dict() and to_dict() methods.
        format: Output format (e.g., "table", "json", "jsonl", "csv", "plain").
        jq_filter: Optional jq filter expression. Only valid with json/jsonl format.

    Example:
        with status_spinner(ctx, "Running segmentation query..."):
            result = workspace.segmentation(...)

        present_result(ctx, result, format, jq_filter=jq_filter)
    """
    data = result.to_table_dict() if format == "table" else result.to_dict()
    output_result(ctx, data, format=format, jq_filter=jq_filter)


def output_result(
    ctx: typer.Context,
    data: dict[str, Any] | list[Any],
    columns: list[str] | None = None,
    *,
    format: str | None = None,
    jq_filter: str | None = None,
) -> None:
    """Output data in the requested format.

    Routes data to the appropriate formatter based on the --format
    option. Supports json, jsonl, table, csv, and plain formats.

    Args:
        ctx: Typer context with global options in obj dict.
        data: Data to output (dict or list).
        columns: Column names for table/csv format (auto-detected if None).
        format: Output format. If None, falls back to ctx.obj["format"] or "json".
        jq_filter: Optional jq filter expression. Only valid with json/jsonl format.

    Raises:
        typer.Exit: If jq_filter used with incompatible format.
    """
    from mixpanel_data.cli.formatters import (
        format_csv,
        format_json,
        format_jsonl,
        format_plain,
        format_table,
    )

    # Priority: explicit format param > ctx.obj > default
    fmt = format if format is not None else ctx.obj.get("format", "json")

    # Validate jq_filter is only used with json/jsonl formats
    if jq_filter and fmt not in ("json", "jsonl"):
        err_console.print("[red]Error:[/red] --jq requires --format json or jsonl")
        raise typer.Exit(ExitCode.INVALID_ARGS)

    if fmt == "json":
        if jq_filter:
            # Apply jq filter to JSON, then pretty-print result
            json_str = format_json(data)
            results = _apply_jq_filter(json_str, jq_filter)
            # Format: single result as-is, multiple results as array
            if len(results) == 0:
                output = "[]"
            elif len(results) == 1:
                output = json.dumps(results[0], indent=2)
            else:
                output = json.dumps(results, indent=2)
        else:
            output = format_json(data)
        # soft_wrap=True prevents Rich from inserting hard line breaks at 80 chars
        # when piped, which would corrupt JSON by putting newlines inside strings
        console.print(output, highlight=False, soft_wrap=True)
    elif fmt == "jsonl":
        if jq_filter:
            # Apply jq filter, then output each result as JSONL (one per line)
            json_str = format_json(data)
            results = _apply_jq_filter(json_str, jq_filter)
            # Output each result element on its own line
            for item in results:
                console.print(json.dumps(item), highlight=False, soft_wrap=True)
        else:
            output = format_jsonl(data)
            console.print(output, highlight=False, soft_wrap=True)
    elif fmt == "table":
        table = format_table(data, columns)
        console.print(table)
    elif fmt == "csv":
        output = format_csv(data)
        console.print(output, highlight=False, soft_wrap=True, end="")
    elif fmt == "plain":
        output = format_plain(data)
        console.print(output, highlight=False, soft_wrap=True)
    else:
        # Default to JSON for unknown formats
        output = format_json(data)
        console.print(output, highlight=False, soft_wrap=True)


@contextmanager
def status_spinner(ctx: typer.Context, message: str) -> Generator[None, None, None]:
    """Context manager to show a spinner for long-running operations.

    Shows an animated spinner on stderr while the wrapped operation runs.
    Respects the --quiet flag to suppress the spinner. Also skips the
    spinner in non-TTY environments (e.g., CI/CD pipelines) to avoid
    cluttering logs with escape sequences.

    Args:
        ctx: Typer context with global options in obj dict.
        message: Status message to display (e.g., "Fetching data...").

    Yields:
        None - the wrapped code block executes.

    Example:
        with status_spinner(ctx, "Fetching bookmarks..."):
            bookmarks = workspace.list_bookmarks()
    """
    import sys

    quiet = ctx.obj.get("quiet", False) if ctx.obj else False

    # Skip spinner if quiet mode or non-interactive (e.g., CI/CD, pipes)
    if quiet or not sys.stderr.isatty():
        yield
    else:
        with err_console.status(message):
            yield
