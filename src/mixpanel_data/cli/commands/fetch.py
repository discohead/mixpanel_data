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

from mixpanel_data.cli.options import FormatOption, JqOption
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
    limit: Annotated[
        int | None,
        typer.Option(
            "--limit",
            "-l",
            help="Maximum events to return (max 100000).",
            min=1,
            max=100000,
        ),
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
    parallel: Annotated[
        bool,
        typer.Option(
            "--parallel",
            "-p",
            help="Fetch in parallel using multiple threads. Faster for large date ranges.",
        ),
    ] = False,
    workers: Annotated[
        int | None,
        typer.Option(
            "--workers",
            help="Number of parallel workers (default: 10). Only applies with --parallel.",
            min=1,
        ),
    ] = None,
    chunk_days: Annotated[
        int,
        typer.Option(
            "--chunk-days",
            help="Days per chunk for parallel fetching (default: 7). Only applies with --parallel.",
            min=1,
            max=100,
        ),
    ] = 7,
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
    jq_filter: JqOption = None,
) -> None:
    """Fetch events from Mixpanel into local storage.

    Events are stored in a DuckDB table for SQL querying. A progress bar
    shows fetch progress (disable with --no-progress or --quiet).

    **Note:** This is a long-running operation. For large date ranges, use
    --parallel for up to 10x faster exports.

    Use --events to filter by event name (comma-separated list).
    Use --where for Mixpanel expression filters (e.g., 'properties["country"]=="US"').
    Use --limit to cap the number of events returned (max 100000).
    Use --replace to drop and recreate an existing table.
    Use --append to add data to an existing table.
    Use --parallel/-p for faster parallel fetching (recommended for large date ranges).
    Use --chunk-days to configure days per chunk for parallel fetching (default: 7).
    Use --stdout to stream JSONL to stdout instead of storing locally.
    Use --raw with --stdout to output raw Mixpanel API format.

    **Output Structure (JSON):**

        {
          "table": "events",
          "rows": 15234,
          "type": "events",
          "duration_seconds": 12.5,
          "date_range": ["2025-01-01", "2025-01-31"],
          "fetched_at": "2025-01-15T10:30:00Z"
        }

    **Parallel Output Structure (JSON):**

        {
          "table": "events",
          "total_rows": 15234,
          "successful_batches": 5,
          "failed_batches": 0,
          "has_failures": false,
          "duration_seconds": 2.5,
          "fetched_at": "2025-01-15T10:30:00Z"
        }

    **Examples:**

        mp fetch events --from 2025-01-01 --to 2025-01-31
        mp fetch events signups --from 2025-01-01 --to 2025-01-31 --events "Sign Up"
        mp fetch events --from 2025-01-01 --to 2025-01-31 --where 'properties["country"]=="US"'
        mp fetch events --from 2025-01-01 --to 2025-01-31 --limit 10000
        mp fetch events --from 2025-01-01 --to 2025-01-31 --replace
        mp fetch events --from 2025-01-01 --to 2025-01-31 --append
        mp fetch events --from 2025-01-01 --to 2025-01-31 --parallel
        mp fetch events --from 2025-01-01 --to 2025-01-31 --parallel --chunk-days 1
        mp fetch events --from 2025-01-01 --to 2025-01-31 --stdout
        mp fetch events --from 2025-01-01 --to 2025-01-31 --stdout --raw | jq '.event'

    **jq Examples:**

        --jq '.rows'                         # Number of events fetched (sequential)
        --jq '.total_rows'                   # Number of events fetched (parallel)
        --jq '.duration_seconds | round'     # Fetch duration in seconds
        --jq '.date_range'                   # Date range fetched
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

    # Validate --limit not with --parallel (limit not supported in parallel mode)
    if limit and parallel:
        err_console.print(
            "[red]Error:[/red] --limit is not supported with --parallel. "
            "Use one or the other."
        )
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
            limit=limit,
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

    # Create batch progress callback for parallel mode
    on_batch_complete = None
    if parallel and show_progress:
        from mixpanel_data.types import BatchProgress

        def _on_batch_progress(progress: BatchProgress) -> None:
            """Display batch completion status to stderr."""
            status = "✓" if progress.success else "✗"
            err_console.print(
                f"  {status} Batch {progress.batch_index + 1}/{progress.total_batches}: "
                f"{progress.from_date} to {progress.to_date} ({progress.rows} rows)",
                highlight=False,
            )

        on_batch_complete = _on_batch_progress

    result = workspace.fetch_events(
        name=table_name,
        from_date=from_date,
        to_date=to_date,
        events=events_list,
        where=where,
        limit=limit,
        progress=show_progress,
        append=append,
        batch_size=batch_size,
        parallel=parallel,
        max_workers=workers,
        on_batch_complete=on_batch_complete,
        chunk_days=chunk_days,
    )

    output_result(ctx, result.to_dict(), format=format, jq_filter=jq_filter)

    # Exit with code 1 if parallel fetch had failures
    from mixpanel_data.types import ParallelFetchResult

    if isinstance(result, ParallelFetchResult) and result.has_failures:
        raise typer.Exit(1)


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
    cohort: Annotated[
        str | None,
        typer.Option("--cohort", "-c", help="Filter by cohort ID."),
    ] = None,
    output_properties: Annotated[
        str | None,
        typer.Option(
            "--output-properties", "-o", help="Comma-separated properties to include."
        ),
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
    jq_filter: JqOption = None,
) -> None:
    """Fetch user profiles from Mixpanel into local storage.

    Profiles are stored in a DuckDB table for SQL querying. A progress bar
    shows fetch progress (disable with --no-progress or --quiet).

    **Note:** This is a long-running operation. For large profile sets,
    consider running in the background.

    Use --where for Mixpanel expression filters on profile properties.
    Use --cohort to filter by cohort ID membership.
    Use --output-properties to select specific properties (reduces bandwidth).
    Use --replace to drop and recreate an existing table.
    Use --append to add data to an existing table.
    Use --stdout to stream JSONL to stdout instead of storing locally.
    Use --raw with --stdout to output raw Mixpanel API format.

    **Output Structure (JSON):**

        {
          "table": "profiles",
          "rows": 5000,
          "type": "profiles",
          "duration_seconds": 8.2,
          "date_range": null,
          "fetched_at": "2025-01-15T10:30:00Z"
        }

    **Examples:**

        mp fetch profiles
        mp fetch profiles users --replace
        mp fetch profiles users --append
        mp fetch profiles --where 'properties["plan"]=="premium"'
        mp fetch profiles --cohort 12345
        mp fetch profiles --output-properties '$email,$name,plan'
        mp fetch profiles --stdout
        mp fetch profiles --stdout --raw

    **jq Examples:**

        --jq '.rows'                         # Number of profiles fetched
        --jq '.table'                        # Table name created
        --jq '.duration_seconds | round'     # Fetch duration in seconds
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

    # Parse output_properties filter
    props_list = (
        [p.strip() for p in output_properties.split(",")] if output_properties else None
    )

    workspace = get_workspace(ctx)

    # Streaming mode: output JSONL to stdout
    if stdout:
        quiet = ctx.obj.get("quiet", False)
        count = 0

        for profile in workspace.stream_profiles(
            where=where,
            cohort_id=cohort,
            output_properties=props_list,
            raw=raw,
        ):
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
        cohort_id=cohort,
        output_properties=props_list,
        progress=show_progress,
        append=append,
        batch_size=batch_size,
    )

    output_result(ctx, result.to_dict(), format=format, jq_filter=jq_filter)
