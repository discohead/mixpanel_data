"""Data fetching commands.

This module provides commands for fetching data from Mixpanel:
- events: Fetch events into local storage
- profiles: Fetch user profiles into local storage
"""

from __future__ import annotations

import contextlib
from typing import Annotated

import typer

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
)


@fetch_app.command("events")
@handle_errors
def fetch_events(
    ctx: typer.Context,
    name: Annotated[
        str,
        typer.Argument(help="Table name for storing events."),
    ] = "events",
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
    no_progress: Annotated[
        bool,
        typer.Option("--no-progress", help="Hide progress bar."),
    ] = False,
) -> None:
    """Fetch events from Mixpanel into local storage.

    Events are stored in a DuckDB table for SQL querying.
    """
    # Validate required options
    if not from_date:
        err_console.print("[red]Error:[/red] --from is required")
        raise typer.Exit(3)
    if not to_date:
        err_console.print("[red]Error:[/red] --to is required")
        raise typer.Exit(3)

    # Parse events filter
    events_list = [e.strip() for e in events.split(",")] if events else None

    workspace = get_workspace(ctx)

    # Drop table if replace is set
    if replace:
        with contextlib.suppress(Exception):
            workspace.drop(name)

    quiet = ctx.obj.get("quiet", False)
    show_progress = not quiet and not no_progress

    result = workspace.fetch_events(
        name=name,
        from_date=from_date,
        to_date=to_date,
        events=events_list,
        where=where,
        progress=show_progress,
    )

    output_result(ctx, result.to_dict())


@fetch_app.command("profiles")
@handle_errors
def fetch_profiles(
    ctx: typer.Context,
    name: Annotated[
        str,
        typer.Argument(help="Table name for storing profiles."),
    ] = "profiles",
    where: Annotated[
        str | None,
        typer.Option("--where", "-w", help="Mixpanel filter expression."),
    ] = None,
    replace: Annotated[
        bool,
        typer.Option("--replace", help="Replace existing table."),
    ] = False,
    no_progress: Annotated[
        bool,
        typer.Option("--no-progress", help="Hide progress bar."),
    ] = False,
) -> None:
    """Fetch user profiles from Mixpanel into local storage.

    Profiles are stored in a DuckDB table for SQL querying.
    """
    workspace = get_workspace(ctx)

    # Drop table if replace is set
    if replace:
        with contextlib.suppress(Exception):
            workspace.drop(name)

    quiet = ctx.obj.get("quiet", False)
    show_progress = not quiet and not no_progress

    result = workspace.fetch_profiles(
        name=name,
        where=where,
        progress=show_progress,
    )

    output_result(ctx, result.to_dict())
