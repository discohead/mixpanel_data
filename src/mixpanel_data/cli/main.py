"""CLI entry point for mixpanel_data.

This module provides the `mp` command-line interface, the main entry
point for the CLI. It defines global options and registers command
groups.

Usage:
    mp [OPTIONS] COMMAND [ARGS]...

Examples:
    mp --help
    mp auth list
    mp --account staging fetch events --from 2024-01-01 --to 2024-01-31
    mp query sql "SELECT COUNT(*) FROM events"
"""

from __future__ import annotations

import signal
import sys
from typing import Annotated, Literal

import typer

import mixpanel_data
from mixpanel_data.cli.utils import ExitCode, err_console


def _get_rich_markup_mode() -> Literal["markdown", "rich"] | None:
    """Determine rich_markup_mode based on terminal detection.

    Returns "markdown" for interactive terminals to provide rich formatting,
    or None for non-TTY contexts (pipes, AI agents) to minimize token usage.

    Returns:
        "markdown" if stdout is a TTY, None otherwise.
    """
    import os

    # MP_PLAIN=1 forces plain output even in TTY
    if os.environ.get("MP_PLAIN", "").lower() in ("1", "true", "yes"):
        return None
    # Use rich formatting only in interactive terminals
    return "markdown" if sys.stdout.isatty() else None


# Create main application
app = typer.Typer(
    name="mp",
    help="Mixpanel data CLI - fetch, store, and query analytics data.",
    epilog="""Two data paths:
  Live:  mp query segmentation, mp query funnel (call Mixpanel API directly)
  Local: mp fetch events → mp query sql (store locally, query with SQL)

Workflow: mp inspect events → mp fetch events → mp query sql""",
    no_args_is_help=True,
    add_completion=True,
    rich_markup_mode=_get_rich_markup_mode(),
)


def version_callback(value: bool) -> None:
    """Show version and exit."""
    if value:
        print(f"mp version {mixpanel_data.__version__}")
        raise typer.Exit()


def _handle_interrupt(_signum: int, _frame: object) -> None:
    """Handle SIGINT (Ctrl+C) gracefully."""
    err_console.print("\n[yellow]Interrupted[/yellow]")
    sys.exit(ExitCode.INTERRUPTED)


# Set up signal handler for Ctrl+C
signal.signal(signal.SIGINT, _handle_interrupt)


@app.callback()
def main(
    ctx: typer.Context,
    account: Annotated[
        str | None,
        typer.Option(
            "--account",
            "-a",
            help="Account name to use (overrides default).",
            envvar="MP_ACCOUNT",
        ),
    ] = None,
    quiet: Annotated[
        bool,
        typer.Option(
            "--quiet",
            "-q",
            help="Suppress progress output.",
        ),
    ] = False,
    verbose: Annotated[
        bool,
        typer.Option(
            "--verbose",
            "-v",
            help="Enable debug output.",
        ),
    ] = False,
    _version: Annotated[
        bool,
        typer.Option(
            "--version",
            help="Show version and exit.",
            callback=version_callback,
            is_eager=True,
        ),
    ] = False,
) -> None:
    """Mixpanel data CLI - fetch, store, and query analytics data.

    Designed for AI coding agents. Fetch data once into a local DuckDB
    database, then query it repeatedly with SQL.
    """
    ctx.ensure_object(dict)
    ctx.obj["account"] = account
    ctx.obj["quiet"] = quiet
    ctx.obj["verbose"] = verbose
    ctx.obj["workspace"] = None
    ctx.obj["config"] = None


# Import and register command groups
# These imports are done here to avoid circular imports
def _register_commands() -> None:
    """Register all command groups with the main app."""
    from mixpanel_data.cli.commands.auth import auth_app
    from mixpanel_data.cli.commands.fetch import fetch_app
    from mixpanel_data.cli.commands.flags import flags_app
    from mixpanel_data.cli.commands.inspect import inspect_app
    from mixpanel_data.cli.commands.query import query_app

    app.add_typer(auth_app, name="auth", help="Manage authentication and accounts.")
    app.add_typer(fetch_app, name="fetch", help="Fetch data from Mixpanel.")
    app.add_typer(flags_app, name="flags", help="Manage feature flags.")
    app.add_typer(query_app, name="query", help="Query local and live data.")
    app.add_typer(
        inspect_app, name="inspect", help="Inspect schema and local database."
    )


# Register commands when module is imported
_register_commands()


if __name__ == "__main__":
    app()
