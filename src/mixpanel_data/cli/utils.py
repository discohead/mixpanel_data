"""CLI utility functions and error handling.

This module provides shared utilities for the CLI:
- ExitCode enum for standardized exit codes
- handle_errors decorator for exception-to-exit-code mapping
- Console instances for stdout/stderr separation
- Lazy workspace/config initialization helpers
- status_spinner context manager for long-running operations
"""

from __future__ import annotations

import functools
import os
from collections.abc import Callable, Generator
from contextlib import contextmanager
from enum import IntEnum
from typing import TYPE_CHECKING, Any, TypeVar

import typer
from rich.console import Console

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

if TYPE_CHECKING:
    from mixpanel_data._internal.config import ConfigManager
    from mixpanel_data.workspace import Workspace

# Console instances for stdout/stderr separation
# Data output goes to stdout; progress/errors go to stderr
console = Console()
err_console = Console(stderr=True, force_terminal=not os.environ.get("NO_COLOR"))


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
        except RateLimitError as e:
            err_console.print(f"[yellow]Rate limited:[/yellow] {e.message}")
            if e.retry_after:
                err_console.print(f"Retry after {e.retry_after} seconds.")
            raise typer.Exit(ExitCode.RATE_LIMIT) from None
        except QueryError as e:
            err_console.print(f"[red]Query error:[/red] {e.message}")
            raise typer.Exit(ExitCode.INVALID_ARGS) from None
        except ConfigError as e:
            err_console.print(f"[red]Configuration error:[/red] {e.message}")
            raise typer.Exit(ExitCode.GENERAL_ERROR) from None
        except MixpanelDataError as e:
            err_console.print(f"[red]Error:[/red] {e.message}")
            raise typer.Exit(ExitCode.GENERAL_ERROR) from None

    return wrapper  # type: ignore[return-value]


def get_workspace(ctx: typer.Context) -> Workspace:
    """Get or create workspace from context.

    Lazily initializes a Workspace instance, respecting the --account
    global option. The workspace is cached in the context for reuse.

    Args:
        ctx: Typer context with global options in obj dict.

    Returns:
        Configured Workspace instance.

    Raises:
        AccountNotFoundError: If specified account doesn't exist.
        ConfigError: If no credentials can be resolved.
    """
    from mixpanel_data.workspace import Workspace

    if "workspace" not in ctx.obj or ctx.obj["workspace"] is None:
        account = ctx.obj.get("account")
        ctx.obj["workspace"] = Workspace(account=account)
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


def output_result(
    ctx: typer.Context,
    data: dict[str, Any] | list[Any],
    columns: list[str] | None = None,
    *,
    format: str | None = None,
) -> None:
    """Output data in the requested format.

    Routes data to the appropriate formatter based on the --format
    option. Supports json, jsonl, table, csv, and plain formats.

    Args:
        ctx: Typer context with global options in obj dict.
        data: Data to output (dict or list).
        columns: Column names for table/csv format (auto-detected if None).
        format: Output format. If None, falls back to ctx.obj["format"] or "json".
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

    if fmt == "json":
        output = format_json(data)
        console.print(output, highlight=False)
    elif fmt == "jsonl":
        output = format_jsonl(data)
        console.print(output, highlight=False)
    elif fmt == "table":
        table = format_table(data, columns)
        console.print(table)
    elif fmt == "csv":
        output = format_csv(data)
        console.print(output, highlight=False, end="")
    elif fmt == "plain":
        output = format_plain(data)
        console.print(output, highlight=False)
    else:
        # Default to JSON for unknown formats
        output = format_json(data)
        console.print(output, highlight=False)


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
