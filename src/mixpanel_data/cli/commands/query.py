"""Query commands for local SQL and live API queries.

This module provides commands for querying data:
- sql: Query local DuckDB database
- segmentation: Live segmentation query
- funnel: Live funnel analysis
- retention: Live retention analysis
- jql: Execute custom JQL scripts
- event-counts: Multi-event time series
- property-counts: Property breakdown
- activity-feed: User activity history
- insights: Saved Insights reports
- frequency: Event frequency distribution
- segmentation-numeric: Numeric property bucketing
- segmentation-sum: Numeric sum aggregation
- segmentation-average: Numeric average aggregation
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from mixpanel_data.cli.utils import (
    err_console,
    get_workspace,
    handle_errors,
    output_result,
)

query_app = typer.Typer(
    name="query",
    help="Query local and live data.",
    no_args_is_help=True,
)


@query_app.command("sql")
@handle_errors
def query_sql(
    ctx: typer.Context,
    query: Annotated[
        str | None,
        typer.Argument(help="SQL query string."),
    ] = None,
    file: Annotated[
        Path | None,
        typer.Option("--file", "-F", help="Read query from file."),
    ] = None,
    scalar: Annotated[
        bool,
        typer.Option("--scalar", "-s", help="Return single value."),
    ] = False,
) -> None:
    """Execute SQL query against local DuckDB database.

    Query can be provided as an argument or read from a file with --file.
    """
    # Get query from argument or file
    if query is None and file is None:
        err_console.print("[red]Error:[/red] Provide a query or use --file")
        raise typer.Exit(3)

    if file is not None:
        if not file.exists():
            err_console.print(f"[red]Error:[/red] File not found: {file}")
            raise typer.Exit(3)
        sql_query = file.read_text()
    else:
        sql_query = query  # type: ignore[assignment]

    workspace = get_workspace(ctx)

    if scalar:
        result = workspace.sql_scalar(sql_query)
        # For scalar output, just print the raw value
        if ctx.obj.get("format") == "plain":
            print(result)
        else:
            output_result(ctx, {"value": result})
    else:
        result = workspace.sql_rows(sql_query)
        output_result(ctx, result)


@query_app.command("segmentation")
@handle_errors
def query_segmentation(
    ctx: typer.Context,
    event: Annotated[
        str,
        typer.Option("--event", "-e", help="Event name."),
    ],
    from_date: Annotated[
        str,
        typer.Option("--from", help="Start date (YYYY-MM-DD)."),
    ],
    to_date: Annotated[
        str,
        typer.Option("--to", help="End date (YYYY-MM-DD)."),
    ],
    on: Annotated[
        str | None,
        typer.Option("--on", "-o", help="Property to segment by."),
    ] = None,
    unit: Annotated[
        str,
        typer.Option("--unit", "-u", help="Time unit: day, week, month."),
    ] = "day",
    where: Annotated[
        str | None,
        typer.Option("--where", "-w", help="Filter expression."),
    ] = None,
) -> None:
    """Run live segmentation query against Mixpanel API."""
    workspace = get_workspace(ctx)

    result = workspace.segmentation(
        event=event,
        from_date=from_date,
        to_date=to_date,
        on=on,
        unit=unit,  # type: ignore[arg-type]
        where=where,
    )

    output_result(ctx, result.to_dict())


@query_app.command("funnel")
@handle_errors
def query_funnel(
    ctx: typer.Context,
    funnel_id: Annotated[
        int,
        typer.Argument(help="Funnel ID."),
    ],
    from_date: Annotated[
        str,
        typer.Option("--from", help="Start date (YYYY-MM-DD)."),
    ],
    to_date: Annotated[
        str,
        typer.Option("--to", help="End date (YYYY-MM-DD)."),
    ],
    unit: Annotated[
        str | None,
        typer.Option("--unit", "-u", help="Time unit: day, week, month."),
    ] = None,
    on: Annotated[
        str | None,
        typer.Option("--on", "-o", help="Property to segment by."),
    ] = None,
) -> None:
    """Run live funnel analysis against Mixpanel API."""
    workspace = get_workspace(ctx)

    result = workspace.funnel(
        funnel_id=funnel_id,
        from_date=from_date,
        to_date=to_date,
        unit=unit,
        on=on,
    )

    output_result(ctx, result.to_dict())


@query_app.command("retention")
@handle_errors
def query_retention(
    ctx: typer.Context,
    born: Annotated[
        str,
        typer.Option("--born", "-b", help="Birth event."),
    ],
    return_event: Annotated[
        str,
        typer.Option("--return", "-r", help="Return event."),
    ],
    from_date: Annotated[
        str,
        typer.Option("--from", help="Start date (YYYY-MM-DD)."),
    ],
    to_date: Annotated[
        str,
        typer.Option("--to", help="End date (YYYY-MM-DD)."),
    ],
    born_where: Annotated[
        str | None,
        typer.Option("--born-where", help="Birth event filter."),
    ] = None,
    return_where: Annotated[
        str | None,
        typer.Option("--return-where", help="Return event filter."),
    ] = None,
    interval: Annotated[
        int | None,
        typer.Option("--interval", "-i", help="Bucket size."),
    ] = None,
    intervals: Annotated[
        int | None,
        typer.Option("--intervals", "-n", help="Number of buckets."),
    ] = None,
    unit: Annotated[
        str,
        typer.Option("--unit", "-u", help="Time unit: day, week, month."),
    ] = "day",
) -> None:
    """Run live retention analysis against Mixpanel API."""
    workspace = get_workspace(ctx)

    # Use defaults if not provided
    actual_interval = interval if interval is not None else 1
    actual_interval_count = intervals if intervals is not None else 10

    result = workspace.retention(
        born_event=born,
        return_event=return_event,
        from_date=from_date,
        to_date=to_date,
        born_where=born_where,
        return_where=return_where,
        interval=actual_interval,
        interval_count=actual_interval_count,
        unit=unit,  # type: ignore[arg-type]
    )

    output_result(ctx, result.to_dict())


@query_app.command("jql")
@handle_errors
def query_jql(
    ctx: typer.Context,
    file: Annotated[
        Path | None,
        typer.Argument(help="JQL script file."),
    ] = None,
    script: Annotated[
        str | None,
        typer.Option("--script", "-c", help="Inline JQL script."),
    ] = None,
    param: Annotated[
        list[str] | None,
        typer.Option("--param", "-P", help="Parameter (key=value)."),
    ] = None,
) -> None:
    """Execute JQL script against Mixpanel API.

    Script can be provided as a file argument or inline with --script.
    Parameters can be passed with --param key=value (repeatable).
    """
    # Get script from file or inline
    if file is not None:
        if not file.exists():
            err_console.print(f"[red]Error:[/red] File not found: {file}")
            raise typer.Exit(2)
        jql_script = file.read_text()
    elif script is not None:
        jql_script = script
    else:
        err_console.print("[red]Error:[/red] Provide a file or use --script")
        raise typer.Exit(3)

    # Parse parameters
    params: dict[str, str] = {}
    if param:
        for p in param:
            if "=" not in p:
                err_console.print(f"[red]Error:[/red] Invalid parameter format: {p}")
                err_console.print("Use --param key=value")
                raise typer.Exit(3)
            key, value = p.split("=", 1)
            params[key] = value

    workspace = get_workspace(ctx)

    result = workspace.jql(
        script=jql_script,
        params=params if params else None,
    )

    output_result(ctx, result.to_dict())


@query_app.command("event-counts")
@handle_errors
def query_event_counts(
    ctx: typer.Context,
    events: Annotated[
        str,
        typer.Option("--events", "-e", help="Comma-separated event names."),
    ],
    from_date: Annotated[
        str,
        typer.Option("--from", help="Start date (YYYY-MM-DD)."),
    ],
    to_date: Annotated[
        str,
        typer.Option("--to", help="End date (YYYY-MM-DD)."),
    ],
    type_: Annotated[
        str,
        typer.Option("--type", "-t", help="Count type: general, unique, average."),
    ] = "general",
    unit: Annotated[
        str,
        typer.Option("--unit", "-u", help="Time unit: minute, hour, day, week, month."),
    ] = "day",
) -> None:
    """Query event counts over time for multiple events."""
    # Parse events
    events_list = [e.strip() for e in events.split(",")]

    workspace = get_workspace(ctx)

    result = workspace.event_counts(
        events=events_list,
        from_date=from_date,
        to_date=to_date,
        type=type_,  # type: ignore[arg-type]
        unit=unit,  # type: ignore[arg-type]
    )

    output_result(ctx, result.to_dict())


@query_app.command("property-counts")
@handle_errors
def query_property_counts(
    ctx: typer.Context,
    event: Annotated[
        str,
        typer.Option("--event", "-e", help="Event name."),
    ],
    property_name: Annotated[
        str,
        typer.Option("--property", "-p", help="Property name."),
    ],
    from_date: Annotated[
        str,
        typer.Option("--from", help="Start date (YYYY-MM-DD)."),
    ],
    to_date: Annotated[
        str,
        typer.Option("--to", help="End date (YYYY-MM-DD)."),
    ],
    type_: Annotated[
        str,
        typer.Option("--type", "-t", help="Count type: general, unique, average."),
    ] = "general",
    unit: Annotated[
        str,
        typer.Option("--unit", "-u", help="Time unit: minute, hour, day, week, month."),
    ] = "day",
    limit: Annotated[
        int,
        typer.Option("--limit", "-l", help="Max property values to return."),
    ] = 10,
) -> None:
    """Query event counts broken down by property values."""
    workspace = get_workspace(ctx)

    result = workspace.property_counts(
        event=event,
        property_name=property_name,
        from_date=from_date,
        to_date=to_date,
        type=type_,  # type: ignore[arg-type]
        unit=unit,  # type: ignore[arg-type]
        limit=limit,
    )

    output_result(ctx, result.to_dict())


@query_app.command("activity-feed")
@handle_errors
def query_activity_feed(
    ctx: typer.Context,
    users: Annotated[
        str,
        typer.Option("--users", "-U", help="Comma-separated distinct IDs."),
    ],
    from_date: Annotated[
        str | None,
        typer.Option("--from", help="Start date (YYYY-MM-DD)."),
    ] = None,
    to_date: Annotated[
        str | None,
        typer.Option("--to", help="End date (YYYY-MM-DD)."),
    ] = None,
) -> None:
    """Query user activity feed for specific users."""
    # Parse users
    user_list = [u.strip() for u in users.split(",")]

    workspace = get_workspace(ctx)

    result = workspace.activity_feed(
        distinct_ids=user_list,
        from_date=from_date,
        to_date=to_date,
    )

    output_result(ctx, result.to_dict())


@query_app.command("insights")
@handle_errors
def query_insights(
    ctx: typer.Context,
    bookmark_id: Annotated[
        int,
        typer.Argument(help="Saved Insights report bookmark ID."),
    ],
) -> None:
    """Query a saved Insights report by bookmark ID."""
    workspace = get_workspace(ctx)

    result = workspace.insights(bookmark_id=bookmark_id)

    output_result(ctx, result.to_dict())


@query_app.command("frequency")
@handle_errors
def query_frequency(
    ctx: typer.Context,
    from_date: Annotated[
        str,
        typer.Option("--from", help="Start date (YYYY-MM-DD)."),
    ],
    to_date: Annotated[
        str,
        typer.Option("--to", help="End date (YYYY-MM-DD)."),
    ],
    event: Annotated[
        str | None,
        typer.Option("--event", "-e", help="Event name (all events if omitted)."),
    ] = None,
    unit: Annotated[
        str,
        typer.Option("--unit", "-u", help="Time unit: day, week, month."),
    ] = "day",
    addiction_unit: Annotated[
        str,
        typer.Option("--addiction-unit", help="Addiction unit: hour, day."),
    ] = "hour",
    where: Annotated[
        str | None,
        typer.Option("--where", "-w", help="Filter expression."),
    ] = None,
) -> None:
    """Analyze event frequency distribution (addiction analysis)."""
    workspace = get_workspace(ctx)

    result = workspace.frequency(
        from_date=from_date,
        to_date=to_date,
        event=event,
        unit=unit,  # type: ignore[arg-type]
        addiction_unit=addiction_unit,  # type: ignore[arg-type]
        where=where,
    )

    output_result(ctx, result.to_dict())


@query_app.command("segmentation-numeric")
@handle_errors
def query_segmentation_numeric(
    ctx: typer.Context,
    event: Annotated[
        str,
        typer.Option("--event", "-e", help="Event name."),
    ],
    on: Annotated[
        str,
        typer.Option("--on", "-o", help="Numeric property to bucket."),
    ],
    from_date: Annotated[
        str,
        typer.Option("--from", help="Start date (YYYY-MM-DD)."),
    ],
    to_date: Annotated[
        str,
        typer.Option("--to", help="End date (YYYY-MM-DD)."),
    ],
    type_: Annotated[
        str,
        typer.Option("--type", "-t", help="Bucket type: linear, log."),
    ] = "linear",
    unit: Annotated[
        str,
        typer.Option("--unit", "-u", help="Time unit: day, week, month."),
    ] = "day",
    where: Annotated[
        str | None,
        typer.Option("--where", "-w", help="Filter expression."),
    ] = None,
) -> None:
    """Bucket events by numeric property ranges."""
    workspace = get_workspace(ctx)

    result = workspace.segmentation_numeric(
        event=event,
        on=on,
        from_date=from_date,
        to_date=to_date,
        type=type_,  # type: ignore[arg-type]
        unit=unit,  # type: ignore[arg-type]
        where=where,
    )

    output_result(ctx, result.to_dict())


@query_app.command("segmentation-sum")
@handle_errors
def query_segmentation_sum(
    ctx: typer.Context,
    event: Annotated[
        str,
        typer.Option("--event", "-e", help="Event name."),
    ],
    on: Annotated[
        str,
        typer.Option("--on", "-o", help="Numeric property to sum."),
    ],
    from_date: Annotated[
        str,
        typer.Option("--from", help="Start date (YYYY-MM-DD)."),
    ],
    to_date: Annotated[
        str,
        typer.Option("--to", help="End date (YYYY-MM-DD)."),
    ],
    unit: Annotated[
        str,
        typer.Option("--unit", "-u", help="Time unit: day, week, month."),
    ] = "day",
    where: Annotated[
        str | None,
        typer.Option("--where", "-w", help="Filter expression."),
    ] = None,
) -> None:
    """Calculate sum of numeric property over time."""
    workspace = get_workspace(ctx)

    result = workspace.segmentation_sum(
        event=event,
        on=on,
        from_date=from_date,
        to_date=to_date,
        unit=unit,  # type: ignore[arg-type]
        where=where,
    )

    output_result(ctx, result.to_dict())


@query_app.command("segmentation-average")
@handle_errors
def query_segmentation_average(
    ctx: typer.Context,
    event: Annotated[
        str,
        typer.Option("--event", "-e", help="Event name."),
    ],
    on: Annotated[
        str,
        typer.Option("--on", "-o", help="Numeric property to average."),
    ],
    from_date: Annotated[
        str,
        typer.Option("--from", help="Start date (YYYY-MM-DD)."),
    ],
    to_date: Annotated[
        str,
        typer.Option("--to", help="End date (YYYY-MM-DD)."),
    ],
    unit: Annotated[
        str,
        typer.Option("--unit", "-u", help="Time unit: day, week, month."),
    ] = "day",
    where: Annotated[
        str | None,
        typer.Option("--where", "-w", help="Filter expression."),
    ] = None,
) -> None:
    """Calculate average of numeric property over time."""
    workspace = get_workspace(ctx)

    result = workspace.segmentation_average(
        event=event,
        on=on,
        from_date=from_date,
        to_date=to_date,
        unit=unit,  # type: ignore[arg-type]
        where=where,
    )

    output_result(ctx, result.to_dict())
