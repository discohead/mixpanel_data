"""Data fetching commands.

This module provides commands for fetching data from Mixpanel:
- events: Fetch events into local storage
- profiles: Fetch user profiles into local storage

Both commands support streaming to stdout with --stdout flag, which bypasses
local storage and outputs JSONL directly for piping to other tools.
"""

from __future__ import annotations

import contextlib
import json
import sys
from typing import Annotated, Any

import typer

from mixpanel_data.cli.options import FormatOption
from mixpanel_data.cli.utils import (
    err_console,
    get_workspace,
    handle_errors,
    output_result,
)

fetch_app = typer.Typer(
    name="fetch",
    help="Fetch data from Mixpanel.",
    no_args_is_help=True,
    rich_markup_mode="markdown",
)


def _json_serializer(obj: Any) -> str:
    """JSON serializer for objects not serializable by default json code."""
    if hasattr(obj, "isoformat"):
        result: str = obj.isoformat()
        return result
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")


@fetch_app.command("events")
@handle_errors
def fetch_events(
    ctx: typer.Context,
    name: Annotated[
        str | None,
        typer.Argument(help="Table name for storing events. Ignored with --stdout."),
    ] = None,
    from_date: Annotated[
        str,
        typer.Option("--from", help="Start date (YYYY-MM-DD).", show_default=False),
    ] = "",
    to_date: Annotated[
        str,
        typer.Option("--to", help="End date (YYYY-MM-DD).", show_default=False),
    ] = "",
    events: Annotated[
        str | None,
        typer.Option("--events", "-e", help="Comma-separated event filter."),
    ] = None,
    where: Annotated[
        str | None,
        typer.Option("--where", "-w", help="Mixpanel filter expression."),
    ] = None,
    replace: Annotated[
        bool,
        typer.Option("--replace", help="Replace existing table."),
    ] = False,
    append: Annotated[
        bool,
        typer.Option("--append", help="Append to existing table."),
    ] = False,
    no_progress: Annotated[
        bool,
        typer.Option("--no-progress", help="Hide progress bar."),
    ] = False,
    stdout: Annotated[
        bool,
        typer.Option("--stdout", help="Stream to stdout as JSONL instead of storing."),
    ] = False,
    raw: Annotated[
        bool,
        typer.Option("--raw", help="Output raw API format (only with --stdout)."),
    ] = False,
    batch_size: Annotated[
        int,
        typer.Option(
            "--batch-size",
            help="Rows per commit. Controls memory/IO tradeoff. (100-100000)",
            min=100,
            max=100000,
        ),
    ] = 1000,
    format: FormatOption = "json",
) -> None:
    """Fetch events from Mixpanel into local storage.

    Events are stored in a DuckDB table for SQL querying. A progress bar
    shows fetch progress (disable with --no-progress or --quiet).

    **Note:** This is a long-running operation. For large date ranges, chunk
    into smaller ranges with --append, or run in the background.

    Use --events to filter by event name (comma-separated list).
    Use --where for Mixpanel expression filters (e.g., 'properties["country"]=="US"').
    Use --replace to drop and recreate an existing table.
    Use --append to add data to an existing table.
    Use --stdout to stream JSONL to stdout instead of storing locally.
    Use --raw with --stdout to output raw Mixpanel API format.

    Output shows table name, row count, duration, and date range.

    Examples:

        mp fetch events --from 2025-01-01 --to 2025-01-31
        mp fetch events signups --from 2025-01-01 --to 2025-01-31 --events "Sign Up"
        mp fetch events --from 2025-01-01 --to 2025-01-31 --where 'properties["country"]=="US"'
        mp fetch events --from 2025-01-01 --to 2025-01-31 --replace
        mp fetch events --from 2025-01-01 --to 2025-01-31 --append
        mp fetch events --from 2025-01-01 --to 2025-01-31 --stdout
        mp fetch events --from 2025-01-01 --to 2025-01-31 --stdout --raw | jq '.event'
    """
    # Validate required options
    if not from_date:
        err_console.print("[red]Error:[/red] --from is required")
        raise typer.Exit(3)
    if not to_date:
        err_console.print("[red]Error:[/red] --to is required")
        raise typer.Exit(3)

    # Validate mutually exclusive options
    if replace and append:
        err_console.print(
            "[red]Error:[/red] --replace and --append are mutually exclusive"
        )
        raise typer.Exit(3)

    # Validate --raw only with --stdout
    if raw and not stdout:
        err_console.print("[red]Error:[/red] --raw requires --stdout")
        raise typer.Exit(3)

    # Parse events filter
    events_list = [e.strip() for e in events.split(",")] if events else None

    workspace = get_workspace(ctx)

    # Streaming mode: output JSONL to stdout
    if stdout:
        quiet = ctx.obj.get("quiet", False)
        count = 0

        for event in workspace.stream_events(
            from_date=from_date,
            to_date=to_date,
            events=events_list,
            where=where,
            raw=raw,
        ):
            print(json.dumps(event, default=_json_serializer), file=sys.stdout)
            count += 1
            if not quiet and count % 1000 == 0:
                err_console.print(f"Streaming events... {count} rows", highlight=False)

        if not quiet:
            err_console.print(f"Streamed {count} events", highlight=False)
        return

    # Storage mode: fetch into local database
    table_name = name if name else "events"

    # Drop table if replace is set
    if replace:
        with contextlib.suppress(Exception):
            workspace.drop(table_name)

    quiet = ctx.obj.get("quiet", False)
    show_progress = not quiet and not no_progress

    result = workspace.fetch_events(
        name=table_name,
        from_date=from_date,
        to_date=to_date,
        events=events_list,
        where=where,
        progress=show_progress,
        append=append,
        batch_size=batch_size,
    )

    output_result(ctx, result.to_dict(), format=format)


@fetch_app.command("profiles")
@handle_errors
def fetch_profiles(
    ctx: typer.Context,
    name: Annotated[
        str | None,
        typer.Argument(help="Table name for storing profiles. Ignored with --stdout."),
    ] = None,
    where: Annotated[
        str | None,
        typer.Option("--where", "-w", help="Mixpanel filter expression."),
    ] = None,
    replace: Annotated[
        bool,
        typer.Option("--replace", help="Replace existing table."),
    ] = False,
    append: Annotated[
        bool,
        typer.Option("--append", help="Append to existing table."),
    ] = False,
    no_progress: Annotated[
        bool,
        typer.Option("--no-progress", help="Hide progress bar."),
    ] = False,
    stdout: Annotated[
        bool,
        typer.Option("--stdout", help="Stream to stdout as JSONL instead of storing."),
    ] = False,
    raw: Annotated[
        bool,
        typer.Option("--raw", help="Output raw API format (only with --stdout)."),
    ] = False,
    batch_size: Annotated[
        int,
        typer.Option(
            "--batch-size",
            help="Rows per commit. Controls memory/IO tradeoff. (100-100000)",
            min=100,
            max=100000,
        ),
    ] = 1000,
    format: FormatOption = "json",
) -> None:
    """Fetch user profiles from Mixpanel into local storage.

    Profiles are stored in a DuckDB table for SQL querying. A progress bar
    shows fetch progress (disable with --no-progress or --quiet).

    **Note:** This is a long-running operation. For large profile sets,
    consider running in the background.

    Use --where for Mixpanel expression filters on profile properties.
    Use --replace to drop and recreate an existing table.
    Use --append to add data to an existing table.
    Use --stdout to stream JSONL to stdout instead of storing locally.
    Use --raw with --stdout to output raw Mixpanel API format.

    Output shows table name, row count, and fetch duration.

    Examples:

        mp fetch profiles
        mp fetch profiles users --replace
        mp fetch profiles users --append
        mp fetch profiles --where 'properties["plan"]=="premium"'
        mp fetch profiles --stdout
        mp fetch profiles --stdout --raw
    """
    # Validate mutually exclusive options
    if replace and append:
        err_console.print(
            "[red]Error:[/red] --replace and --append are mutually exclusive"
        )
        raise typer.Exit(3)

    # Validate --raw only with --stdout
    if raw and not stdout:
        err_console.print("[red]Error:[/red] --raw requires --stdout")
        raise typer.Exit(3)

    workspace = get_workspace(ctx)

    # Streaming mode: output JSONL to stdout
    if stdout:
        quiet = ctx.obj.get("quiet", False)
        count = 0

        for profile in workspace.stream_profiles(where=where, raw=raw):
            print(json.dumps(profile, default=_json_serializer), file=sys.stdout)
            count += 1
            if not quiet and count % 1000 == 0:
                err_console.print(
                    f"Streaming profiles... {count} rows", highlight=False
                )

        if not quiet:
            err_console.print(f"Streamed {count} profiles", highlight=False)
        return

    # Storage mode: fetch into local database
    table_name = name if name else "profiles"

    # Drop table if replace is set
    if replace:
        with contextlib.suppress(Exception):
            workspace.drop(table_name)

    quiet = ctx.obj.get("quiet", False)
    show_progress = not quiet and not no_progress

    result = workspace.fetch_profiles(
        name=table_name,
        where=where,
        progress=show_progress,
        append=append,
        batch_size=batch_size,
    )

    output_result(ctx, result.to_dict(), format=format)
