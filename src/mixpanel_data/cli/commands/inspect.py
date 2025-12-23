"""Schema discovery and local database inspection commands.

This module provides commands for inspecting data:
- events: List event names from Mixpanel
- properties: List properties for an event
- values: List values for a property
- funnels: List saved funnels
- cohorts: List saved cohorts
- top-events: List today's top events
- info: Show workspace information
- tables: List local tables
- schema: Show table schema
- drop: Drop a table
"""

from __future__ import annotations

from typing import Annotated

import typer

from mixpanel_data.cli.utils import (
    err_console,
    get_workspace,
    handle_errors,
    output_result,
)

inspect_app = typer.Typer(
    name="inspect",
    help="Inspect schema and local database.",
    no_args_is_help=True,
)


@inspect_app.command("events")
@handle_errors
def inspect_events(ctx: typer.Context) -> None:
    """List all event names from Mixpanel project."""
    workspace = get_workspace(ctx)
    events = workspace.events()
    output_result(ctx, events)


@inspect_app.command("properties")
@handle_errors
def inspect_properties(
    ctx: typer.Context,
    event: Annotated[
        str,
        typer.Option("--event", "-e", help="Event name."),
    ],
) -> None:
    """List properties for a specific event."""
    workspace = get_workspace(ctx)
    properties = workspace.properties(event)
    output_result(ctx, properties)


@inspect_app.command("values")
@handle_errors
def inspect_values(
    ctx: typer.Context,
    property_name: Annotated[
        str,
        typer.Option("--property", "-p", help="Property name."),
    ],
    event: Annotated[
        str | None,
        typer.Option("--event", "-e", help="Event name (optional)."),
    ] = None,
    limit: Annotated[
        int,
        typer.Option("--limit", "-l", help="Maximum values to return."),
    ] = 100,
) -> None:
    """List sample values for a property."""
    workspace = get_workspace(ctx)
    values = workspace.property_values(
        property_name=property_name,
        event=event,
        limit=limit,
    )
    output_result(ctx, values)


@inspect_app.command("funnels")
@handle_errors
def inspect_funnels(ctx: typer.Context) -> None:
    """List saved funnels in Mixpanel project."""
    workspace = get_workspace(ctx)
    funnels = workspace.funnels()
    data = [{"funnel_id": f.funnel_id, "name": f.name} for f in funnels]
    output_result(ctx, data, columns=["funnel_id", "name"])


@inspect_app.command("cohorts")
@handle_errors
def inspect_cohorts(ctx: typer.Context) -> None:
    """List saved cohorts in Mixpanel project."""
    workspace = get_workspace(ctx)
    cohorts = workspace.cohorts()
    data = [
        {
            "id": c.id,
            "name": c.name,
            "count": c.count,
            "description": c.description,
        }
        for c in cohorts
    ]
    output_result(ctx, data, columns=["id", "name", "count", "description"])


@inspect_app.command("top-events")
@handle_errors
def inspect_top_events(
    ctx: typer.Context,
    type_: Annotated[
        str,
        typer.Option("--type", "-t", help="Count type: general, unique, average."),
    ] = "general",
    limit: Annotated[
        int,
        typer.Option("--limit", "-l", help="Maximum events to return."),
    ] = 10,
) -> None:
    """List today's top events by count."""
    workspace = get_workspace(ctx)
    events = workspace.top_events(type=type_, limit=limit)  # type: ignore[arg-type]
    data = [
        {
            "event": e.event,
            "count": e.count,
            "percent_change": e.percent_change,
        }
        for e in events
    ]
    output_result(ctx, data, columns=["event", "count", "percent_change"])


@inspect_app.command("info")
@handle_errors
def inspect_info(ctx: typer.Context) -> None:
    """Show workspace information."""
    workspace = get_workspace(ctx)
    info = workspace.info()
    output_result(ctx, info.to_dict())


@inspect_app.command("tables")
@handle_errors
def inspect_tables(ctx: typer.Context) -> None:
    """List tables in local database."""
    workspace = get_workspace(ctx)
    tables = workspace.tables()
    data = [
        {
            "name": t.name,
            "type": t.type,
            "row_count": t.row_count,
            "fetched_at": t.fetched_at,
        }
        for t in tables
    ]
    output_result(ctx, data, columns=["name", "type", "row_count", "fetched_at"])


@inspect_app.command("schema")
@handle_errors
def inspect_schema(
    ctx: typer.Context,
    table: Annotated[
        str,
        typer.Option("--table", "-t", help="Table name."),
    ],
    _sample: Annotated[
        bool,
        typer.Option("--sample", help="Include sample values."),
    ] = False,
) -> None:
    """Show schema for a table in local database."""
    # Note: _sample is reserved for future implementation
    workspace = get_workspace(ctx)
    schema = workspace.schema(table)

    data = {
        "table": schema.table_name,
        "columns": [
            {
                "name": c.name,
                "type": c.type,
                "nullable": c.nullable,
            }
            for c in schema.columns
        ],
    }

    output_result(ctx, data)


@inspect_app.command("drop")
@handle_errors
def inspect_drop(
    ctx: typer.Context,
    table: Annotated[
        str,
        typer.Option("--table", "-t", help="Table name to drop."),
    ],
    force: Annotated[
        bool,
        typer.Option("--force", help="Skip confirmation prompt."),
    ] = False,
) -> None:
    """Drop a table from the local database."""
    if not force:
        confirm = typer.confirm(f"Drop table '{table}'?")
        if not confirm:
            err_console.print("[yellow]Cancelled[/yellow]")
            raise typer.Exit(2)

    workspace = get_workspace(ctx)
    workspace.drop(table)

    output_result(ctx, {"dropped": table})
