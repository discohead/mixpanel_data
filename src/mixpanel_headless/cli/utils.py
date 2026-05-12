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
import pydantic
import typer
from rich.console import Console
from rich.markup import escape as rich_escape

from mixpanel_headless.exceptions import (
    AccountExistsError,
    AccountNotFoundError,
    AuthenticationError,
    BusinessContextValidationError,
    ConfigError,
    DateRangeTooLargeError,
    EventNotFoundError,
    InvalidArgumentError,
    JQLSyntaxError,
    MixpanelHeadlessError,
    OAuthError,
    ProjectNotFoundError,
    QueryError,
    RateLimitError,
    RegionProbeError,
    RegionProbeNetworkError,
    ServerError,
    WorkspaceScopeError,
)

if TYPE_CHECKING:
    from mixpanel_headless._internal.config import ConfigManager
    from mixpanel_headless.workspace import Workspace


class ResultWithTableAndDict(Protocol):
    """Protocol for result objects that support both table and dict output."""

    def to_table_dict(self) -> list[dict[str, Any]]: ...
    def to_dict(self) -> dict[str, Any]: ...


# Console instances for stdout/stderr separation
# Data output goes to stdout; progress/errors go to stderr
# Note: Table cell content is escaped via rich_escape() in formatters.py
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

    Maps MixpanelHeadlessError subclasses to appropriate exit codes and
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
            err_console.print(
                f"[red]Authentication error:[/red] {rich_escape(e.message)}"
            )
            # Show request context to help debug auth issues
            if e.request_url:
                # Extract endpoint without sensitive params
                endpoint = e.request_url.split("?")[0].split("/")[-1]
                err_console.print(f"  [dim]Endpoint:[/dim] {rich_escape(endpoint)}")
            # Show API error message if available
            if isinstance(e.response_body, dict):
                api_error = e.response_body.get("error", "")
                if api_error:
                    err_console.print(
                        f"  [dim]API response:[/dim] {rich_escape(str(api_error))}"
                    )
            raise typer.Exit(ExitCode.AUTH_ERROR) from None
        except AccountNotFoundError as e:
            err_console.print(
                f"[red]Account not found:[/red] {rich_escape(e.account_name)}"
            )
            if e.available_accounts:
                joined = ", ".join(rich_escape(a) for a in e.available_accounts)
                err_console.print(f"Available accounts: {joined}")
            raise typer.Exit(ExitCode.NOT_FOUND) from None
        except AccountExistsError as e:
            err_console.print(
                f"[red]Account exists:[/red] {rich_escape(e.account_name)}"
            )
            raise typer.Exit(ExitCode.GENERAL_ERROR) from None
        except ProjectNotFoundError as e:
            err_console.print(
                f"[red]Project not found:[/red] {rich_escape(e.project_id)}"
            )
            if e.available_projects:
                joined = ", ".join(rich_escape(p) for p in e.available_projects)
                err_console.print(f"Accessible projects: {joined}")
            raise typer.Exit(ExitCode.NOT_FOUND) from None
        except RateLimitError as e:
            err_console.print(
                f"[yellow]Rate limited:[/yellow] {rich_escape(e.message)}"
            )
            if e.retry_after:
                err_console.print(
                    f"[cyan]Wait {e.retry_after} seconds before retrying.[/cyan]"
                )
            # Show which endpoint was hit
            if e.request_url:
                endpoint = e.request_url.split("/")[-1].split("?")[0]
                err_console.print(f"[dim]Endpoint: {rich_escape(endpoint)}[/dim]")
            err_console.print(
                "[yellow]Tip:[/yellow] Wait and retry, or reduce your date range."
            )
            raise typer.Exit(ExitCode.RATE_LIMIT) from None
        except EventNotFoundError as e:
            err_console.print(
                f"[red]Event not found:[/red] '{rich_escape(e.event_name)}'"
            )
            if e.similar_events:
                suggestions = ", ".join(
                    f"'{rich_escape(s)}'" for s in e.similar_events[:5]
                )
                err_console.print(f"Did you mean: {suggestions}?")
            raise typer.Exit(ExitCode.NOT_FOUND) from None
        except DateRangeTooLargeError as e:
            err_console.print(
                f"[red]Date range too large:[/red] {rich_escape(e.message)}"
            )
            err_console.print(
                f"  [dim]Requested:[/dim] {rich_escape(str(e.from_date))} to "
                f"{rich_escape(str(e.to_date))} ({e.days_requested} days)"
            )
            err_console.print(f"  [dim]Maximum:[/dim] {e.max_days} days")
            err_console.print(
                "[yellow]Tip:[/yellow] Split into smaller date ranges, e.g.:\n"
                f"  --from {rich_escape(str(e.from_date))} --to <midpoint>\n"
                f"  --from <midpoint+1> --to {rich_escape(str(e.to_date))}"
            )
            raise typer.Exit(ExitCode.INVALID_ARGS) from None
        except JQLSyntaxError as e:
            # JQLSyntaxError must be caught before QueryError (it's a subclass)
            err_console.print(
                f"[red]JQL error:[/red] {rich_escape(e.error_type)}: "
                f"{rich_escape(e.error_message)}"
            )
            # Show line info if available (code snippet with caret)
            if e.line_info:
                err_console.print(f"[dim]{rich_escape(e.line_info)}[/dim]")
            # Show stack trace if available
            if e.stack_trace:
                err_console.print(
                    f"  [dim]Location:[/dim] {rich_escape(e.stack_trace)}"
                )
            # Show the script that failed (truncated for readability)
            if e.script:
                script_preview = e.script.strip()
                if len(script_preview) > 200:
                    script_preview = script_preview[:200] + "..."
                err_console.print(
                    f"  [dim]Script:[/dim]\n{rich_escape(script_preview)}"
                )
            # Show raw error for debugging if it has more info
            if e.raw_error and e.raw_error != e.error_message:
                err_console.print(f"  [dim]Raw error:[/dim] {rich_escape(e.raw_error)}")
            raise typer.Exit(ExitCode.INVALID_ARGS) from None
        except QueryError as e:
            err_console.print(f"[red]Query error:[/red] {rich_escape(e.message)}")
            # Show response body - often contains the actual API error message
            if e.response_body:
                if isinstance(e.response_body, dict):
                    api_error = e.response_body.get("error", "")
                    if (
                        api_error
                        and isinstance(api_error, str)
                        and api_error not in e.message
                    ):
                        err_console.print(
                            f"  [dim]API error:[/dim] {rich_escape(api_error)}"
                        )
                elif (
                    isinstance(e.response_body, str)
                    and e.response_body not in e.message
                ):
                    # Truncate long response bodies
                    body_preview = e.response_body[:200]
                    if len(e.response_body) > 200:
                        body_preview += "..."
                    err_console.print(
                        f"  [dim]Response:[/dim] {rich_escape(body_preview)}"
                    )
            # Show non-sensitive request context for debugging
            if e.request_params:
                for key, value in e.request_params.items():
                    if key not in ("project_id",):
                        err_console.print(
                            f"  [dim]{rich_escape(str(key))}:[/dim] "
                            f"{rich_escape(str(value))}"
                        )
            # Show request body if present (e.g., for POST requests)
            if e.request_body:
                for key, value in e.request_body.items():
                    if key not in ("script",):  # Don't duplicate JQL script
                        val_str = str(value)
                        if len(val_str) > 100:
                            val_str = val_str[:100] + "..."
                        err_console.print(
                            f"  [dim]{rich_escape(str(key))}:[/dim] "
                            f"{rich_escape(val_str)}"
                        )
            # Provide contextual hints
            if e.status_code == 403:
                err_console.print(
                    "[yellow]Hint:[/yellow] Check service account permissions."
                )
            raise typer.Exit(ExitCode.INVALID_ARGS) from None
        except ServerError as e:
            err_console.print(
                f"[red]Server error ({e.status_code}):[/red] {rich_escape(e.message)}"
            )
            # Show response body - may contain actionable error details
            if e.response_body:
                if isinstance(e.response_body, dict):
                    api_error = e.response_body.get("error", "")
                    if api_error:
                        err_console.print(
                            f"  [dim]API error:[/dim] {rich_escape(str(api_error))}"
                        )
                elif isinstance(e.response_body, str):
                    body_preview = e.response_body[:200]
                    if len(e.response_body) > 200:
                        body_preview += "..."
                    err_console.print(
                        f"  [dim]Response:[/dim] {rich_escape(body_preview)}"
                    )
            # Show endpoint for context
            if e.request_url:
                endpoint = e.request_url.split("?")[0].split("/")[-1]
                err_console.print(f"  [dim]Endpoint:[/dim] {rich_escape(endpoint)}")
            err_console.print(
                "[yellow]Hint:[/yellow] This may be a transient issue. "
                "Try again in a few moments."
            )
            raise typer.Exit(ExitCode.GENERAL_ERROR) from None
        except RegionProbeNetworkError as e:
            # Subclass dispatch must come BEFORE the generic
            # RegionProbeError handler — otherwise the network case
            # falls through to "verify your credentials" advice that
            # makes no sense when the user is offline.
            err_console.print(f"[red]ERROR:[/red] {rich_escape(e.message)}")
            err_console.print("")
            err_console.print("Probe results:")
            for region, _status, body in e.attempts:
                err_console.print(
                    f"  {rich_escape(region)}: network error ({rich_escape(body)})"
                )
            err_console.print("")
            err_console.print(
                "Check your network connection (DNS, proxy, captive portal, "
                "TLS interception) and retry. If you know the region, pass "
                "--region {us|eu|in} explicitly to limit the probe to one "
                "host."
            )
            raise typer.Exit(ExitCode.AUTH_ERROR) from None
        except RegionProbeError as e:
            # Error catalog E-1 — render the per-region attempt table so
            # users see exactly which clusters rejected the credential.
            # Exit code 2 because the failure is an authentication
            # rejection across every cluster, not a generic OAuth glitch.
            err_console.print(f"[red]ERROR:[/red] {rich_escape(e.message)}")
            err_console.print("")
            err_console.print("Probe results:")
            for region, status, body in e.attempts:
                if status == 0:
                    err_console.print(
                        f"  {rich_escape(region)}: 0 (network error: "
                        f"{rich_escape(body)})"
                    )
                else:
                    # Render only the first line of the body to keep the
                    # table compact; full body is in e.attempts for
                    # programmatic consumers.
                    short = body.splitlines()[0] if body else ""
                    err_console.print(
                        f"  {rich_escape(region)}: {status} {rich_escape(short)}"
                    )
            err_console.print("")
            err_console.print(
                "If you know the region, pass --region {us|eu|in} explicitly "
                "to skip the probe."
            )
            err_console.print(
                "If your service account is new, verify the username and "
                "secret are correct."
            )
            raise typer.Exit(ExitCode.AUTH_ERROR) from None
        except OAuthError as e:
            err_console.print(f"[red]OAuth error:[/red] {rich_escape(e.message)}")
            if e.code:
                err_console.print(f"  [dim]Code:[/dim] {rich_escape(e.code)}")
            raise typer.Exit(ExitCode.AUTH_ERROR) from None
        except WorkspaceScopeError as e:
            err_console.print(f"[red]Workspace error:[/red] {rich_escape(e.message)}")
            if e.code:
                err_console.print(f"  [dim]Code:[/dim] {rich_escape(e.code)}")
            raise typer.Exit(ExitCode.GENERAL_ERROR) from None
        except InvalidArgumentError as e:
            # Subclass of ConfigError — must be caught BEFORE the
            # generic ConfigError handler so flag-misuse exits 3
            # (INVALID_ARGS) instead of 1 (GENERAL_ERROR). Matches the
            # 043 cli-commands.md §1.5 contract for `mp login`.
            err_console.print(f"[red]ERROR:[/red] {rich_escape(e.message)}")
            raise typer.Exit(ExitCode.INVALID_ARGS) from None
        except ConfigError as e:
            # Escape the message so block names like ``[accounts.NAME]`` are
            # rendered literally instead of being parsed as Rich markup.
            err_console.print(
                f"[red]Configuration error:[/red] {rich_escape(e.message)}"
            )
            raise typer.Exit(ExitCode.GENERAL_ERROR) from None
        except BusinessContextValidationError as e:
            # Client-side input validation rejection (oversize content) —
            # map to INVALID_ARGS (3) rather than GENERAL_ERROR (1) since
            # the failure was the caller's input, not an unknown error.
            err_console.print(
                f"[red]Business context too long:[/red] {rich_escape(e.message)}"
            )
            raise typer.Exit(ExitCode.INVALID_ARGS) from None
        except MixpanelHeadlessError as e:
            err_console.print(f"[red]Error:[/red] {rich_escape(e.message)}")
            raise typer.Exit(ExitCode.GENERAL_ERROR) from None
        except pydantic.ValidationError as e:
            err_console.print(
                "[red]API response parsing error:[/red] "
                "unexpected data format from Mixpanel API"
            )
            err_console.print(f"  [dim]{rich_escape(str(e))}[/dim]")
            raise typer.Exit(ExitCode.GENERAL_ERROR) from None
        except ValueError as e:
            # Handle validation errors (e.g., invalid date format)
            err_console.print(f"[red]Invalid argument:[/red] {rich_escape(str(e))}")
            raise typer.Exit(ExitCode.INVALID_ARGS) from None

    return wrapper  # type: ignore[return-value]


def get_workspace(ctx: typer.Context) -> Workspace:
    """Get or create workspace from context.

    Lazily initializes a Workspace instance, respecting the ``--account``,
    ``--project``, ``--workspace`` (alias ``--workspace-id``), and
    ``--target`` global options. The workspace is cached in the context
    for reuse.

    Args:
        ctx: Typer context with global options in obj dict.

    Returns:
        Configured Workspace instance.

    Raises:
        AccountNotFoundError: If specified account doesn't exist.
        ConfigError: If no credentials can be resolved.
    """
    from mixpanel_headless.workspace import Workspace

    if "workspace" not in ctx.obj or ctx.obj["workspace"] is None:
        account = ctx.obj.get("account")
        project = ctx.obj.get("project")
        workspace_id: int | None = ctx.obj.get("workspace_id")
        target = ctx.obj.get("target")

        ctx.obj["workspace"] = Workspace(
            account=account,
            project=project,
            workspace=workspace_id,
            target=target,
        )
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
    from mixpanel_headless._internal.config import ConfigManager

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
    from mixpanel_headless.cli.formatters import (
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
        print(output)
    elif fmt == "jsonl":
        if jq_filter:
            # Apply jq filter, then output each result as JSONL (one per line)
            json_str = format_json(data)
            results = _apply_jq_filter(json_str, jq_filter)
            # Output each result element on its own line
            for item in results:
                print(json.dumps(item))
        else:
            output = format_jsonl(data)
            print(output)
    elif fmt == "table":
        # Tables use styled console for box-drawing characters
        table = format_table(data, columns)
        console.print(table)
    elif fmt == "csv":
        output = format_csv(data)
        print(output, end="")
    elif fmt == "plain":
        output = format_plain(data)
        print(output)
    else:
        # Default to JSON for unknown formats
        output = format_json(data)
        print(output)


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
