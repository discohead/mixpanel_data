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
- saved-report: Saved reports (Insights, Retention, Funnel)
- flows: Saved flows reports
- frequency: Event frequency distribution
- segmentation-numeric: Numeric property bucketing
- segmentation-sum: Numeric sum aggregation
- segmentation-average: Numeric average aggregation
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from mixpanel_data.cli.options import FormatOption
from mixpanel_data.cli.utils import (
    ExitCode,
    err_console,
    get_workspace,
    handle_errors,
    output_result,
)
from mixpanel_data.cli.validators import (
    validate_count_type,
    validate_hour_day_unit,
    validate_time_unit,
)

query_app = typer.Typer(
    name="query",
    help="Query local and live data.",
    epilog="""Local (uses DuckDB):
  sql           Execute SQL against local database

Live (calls Mixpanel API):
  segmentation, funnel, retention, jql, event-counts,
  property-counts, activity-feed, saved-report, flows, frequency,
  segmentation-numeric, segmentation-sum, segmentation-average""",
    no_args_is_help=True,
    rich_markup_mode="markdown",
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
    format: FormatOption = "json",
) -> None:
    """Execute SQL query against local DuckDB database.

    Query can be provided as an argument or read from a file with --file.
    Use --scalar when your query returns a single value (e.g., COUNT(*)).

    Results are returned as a list of row objects by default. With --scalar,
    returns a single value wrapped in {"value": result} for JSON output,
    or just the raw value for plain output.

    Examples:

        mp query sql "SELECT COUNT(*) FROM events" --scalar
        mp query sql "SELECT event, COUNT(*) FROM events GROUP BY 1" --format table
        mp query sql --file analysis.sql --format csv
    """
    # Get query from argument or file
    if query is None and file is None:
        err_console.print("[red]Error:[/red] Provide a query or use --file")
        raise typer.Exit(3)

    if file is not None:
        if not file.exists():
            err_console.print(f"[red]Error:[/red] File not found: {file}")
            raise typer.Exit(ExitCode.NOT_FOUND)
        sql_query = file.read_text()
    else:
        sql_query = query  # type: ignore[assignment]

    workspace = get_workspace(ctx)

    if scalar:
        result = workspace.sql_scalar(sql_query)
        # For scalar output, just print the raw value
        if format == "plain":
            print(result)
        else:
            output_result(ctx, {"value": result}, format=format)
    else:
        result = workspace.sql_rows(sql_query)
        output_result(ctx, result, format=format)


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
    format: FormatOption = "json",
) -> None:
    """Run live segmentation query against Mixpanel API.

    Returns time-series event counts, optionally segmented by a property.
    Without --on, returns total counts per time period. With --on, breaks
    down counts by property values (e.g., --on country shows counts per country).

    Output includes event name, date range, total count, time unit, and
    a series dict mapping dates to counts (or segments to date/count dicts).

    Examples:

        mp query segmentation -e "Sign Up" --from 2025-01-01 --to 2025-01-31
        mp query segmentation -e "Purchase" --from 2025-01-01 --to 2025-01-31 --on country
        mp query segmentation -e "Login" --from 2025-01-01 --to 2025-01-07 --unit week
    """
    validated_unit = validate_time_unit(unit)
    workspace = get_workspace(ctx)

    result = workspace.segmentation(
        event=event,
        from_date=from_date,
        to_date=to_date,
        on=on,
        unit=validated_unit,
        where=where,
    )

    output_result(ctx, result.to_dict(), format=format)


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
    format: FormatOption = "json",
) -> None:
    """Run live funnel analysis against Mixpanel API.

    Analyzes conversion through a saved funnel's steps. The funnel_id can be
    found in the Mixpanel UI URL when viewing the funnel, or via 'mp inspect funnels'.

    Output includes funnel_id, date range, and steps array with each step's
    event name, count, and conversion_rate (percentage who completed this step).

    Examples:

        mp query funnel 12345 --from 2025-01-01 --to 2025-01-31
        mp query funnel 12345 --from 2025-01-01 --to 2025-01-31 --unit week
        mp query funnel 12345 --from 2025-01-01 --to 2025-01-31 --on country
    """
    workspace = get_workspace(ctx)

    result = workspace.funnel(
        funnel_id=funnel_id,
        from_date=from_date,
        to_date=to_date,
        unit=unit,
        on=on,
    )

    output_result(ctx, result.to_dict(), format=format)


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
    format: FormatOption = "json",
) -> None:
    """Run live retention analysis against Mixpanel API.

    Measures how many users return after their first action (birth event).
    Users are grouped into cohorts by when they first did the birth event,
    then tracked for how many returned to do the return event.

    The --interval and --intervals options control bucket granularity:
    --interval is the bucket size (default 1), --intervals is the number
    of buckets to track (default 10). Combined with --unit, this defines
    the retention window (e.g., --unit day --interval 1 --intervals 7
    tracks daily retention for 7 days).

    Output includes cohorts array with each cohort's date, user count,
    and retention percentages for each interval.

    Examples:

        mp query retention --born "Sign Up" --return "Login" --from 2025-01-01 --to 2025-01-31
        mp query retention --born "Sign Up" --return "Purchase" --from 2025-01-01 --to 2025-01-31 --unit week
        mp query retention --born "Sign Up" --return "Login" --from 2025-01-01 --to 2025-01-31 --intervals 7
    """
    validated_unit = validate_time_unit(unit)
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
        unit=validated_unit,
    )

    output_result(ctx, result.to_dict(), format=format)


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
    format: FormatOption = "json",
) -> None:
    """Execute JQL script against Mixpanel API.

    Script can be provided as a file argument or inline with --script.
    Parameters can be passed with --param key=value (repeatable).

    Examples:

        mp query jql analysis.js
        mp query jql --script "function main() { return Events({...}).groupBy(['event'], mixpanel.reducer.count()) }"
        mp query jql analysis.js --param start_date=2025-01-01 --param event_name=Login
    """
    # Get script from file or inline
    if file is not None:
        if not file.exists():
            err_console.print(f"[red]Error:[/red] File not found: {file}")
            raise typer.Exit(ExitCode.NOT_FOUND)
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

    output_result(ctx, result.to_dict(), format=format)


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
        typer.Option("--unit", "-u", help="Time unit: day, week, month."),
    ] = "day",
    format: FormatOption = "json",
) -> None:
    """Query event counts over time for multiple events.

    Compares multiple events on the same time series. Pass comma-separated
    event names to --events (e.g., --events "Sign Up,Login,Purchase").

    The --type option controls how counts are calculated:
    - general: Total event occurrences (default)
    - unique: Unique users who triggered the event
    - average: Average events per user

    Output includes events list, date range, and series dict mapping
    each event name to its date/count series.

    Examples:

        mp query event-counts --events "Sign Up,Login,Purchase" --from 2025-01-01 --to 2025-01-31
        mp query event-counts --events "Sign Up,Purchase" --from 2025-01-01 --to 2025-01-31 --type unique
        mp query event-counts --events "Login" --from 2025-01-01 --to 2025-01-31 --unit week
    """
    validated_type = validate_count_type(type_)
    validated_unit = validate_time_unit(unit)

    # Parse events
    events_list = [e.strip() for e in events.split(",")]

    workspace = get_workspace(ctx)

    result = workspace.event_counts(
        events=events_list,
        from_date=from_date,
        to_date=to_date,
        type=validated_type,
        unit=validated_unit,
    )

    output_result(ctx, result.to_dict(), format=format)


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
        typer.Option("--unit", "-u", help="Time unit: day, week, month."),
    ] = "day",
    limit: Annotated[
        int,
        typer.Option("--limit", "-l", help="Max property values to return."),
    ] = 10,
    format: FormatOption = "json",
) -> None:
    """Query event counts broken down by property values.

    Shows how event counts vary across different values of a property.
    For example, --property country shows event counts per country.

    The --type option controls how counts are calculated:
    - general: Total event occurrences (default)
    - unique: Unique users who triggered the event
    - average: Average events per user

    The --limit option controls how many property values to return
    (default 10, ordered by count descending).

    Output includes event, property name, date range, and series dict
    mapping each property value to its date/count series.

    Examples:

        mp query property-counts -e "Purchase" -p country --from 2025-01-01 --to 2025-01-31
        mp query property-counts -e "Sign Up" -p "utm_source" --from 2025-01-01 --to 2025-01-31 --limit 20
        mp query property-counts -e "Login" -p browser --from 2025-01-01 --to 2025-01-31 --type unique
    """
    validated_type = validate_count_type(type_)
    validated_unit = validate_time_unit(unit)
    workspace = get_workspace(ctx)

    result = workspace.property_counts(
        event=event,
        property_name=property_name,
        from_date=from_date,
        to_date=to_date,
        type=validated_type,
        unit=validated_unit,
        limit=limit,
    )

    output_result(ctx, result.to_dict(), format=format)


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
    format: FormatOption = "json",
) -> None:
    """Query user activity feed for specific users.

    Retrieves the event history for one or more users identified by their
    distinct_id. Pass comma-separated IDs to --users.

    Optionally filter by date range with --from and --to. Without date
    filters, returns recent activity (API default).

    Output includes distinct_ids queried, optional date range, and events
    array with each event's name, timestamp, and properties.

    Examples:

        mp query activity-feed --users "user123"
        mp query activity-feed --users "user123,user456" --from 2025-01-01 --to 2025-01-31
        mp query activity-feed --users "user123" --format table
    """
    # Parse users
    user_list = [u.strip() for u in users.split(",")]

    workspace = get_workspace(ctx)

    result = workspace.activity_feed(
        distinct_ids=user_list,
        from_date=from_date,
        to_date=to_date,
    )

    output_result(ctx, result.to_dict(), format=format)


@query_app.command("saved-report")
@handle_errors
def query_saved_report(
    ctx: typer.Context,
    bookmark_id: Annotated[
        int,
        typer.Argument(help="Saved report bookmark ID."),
    ],
    format: FormatOption = "json",
) -> None:
    """Query a saved report (Insights, Retention, or Funnel) by bookmark ID.

    Retrieves data from a saved report in Mixpanel. The bookmark_id
    can be found in the URL when viewing a report (the numeric ID
    after /insights/, /retention/, or /funnels/).

    The report type is automatically detected from the response headers.
    Output includes bookmark_id, computed_at timestamp, date_range, headers
    (column names), series data, and report_type.

    Examples:

        mp query saved-report 12345
        mp query saved-report 12345 --format table
    """
    workspace = get_workspace(ctx)

    result = workspace.query_saved_report(bookmark_id=bookmark_id)

    output_result(ctx, result.to_dict(), format=format)


@query_app.command("flows")
@handle_errors
def query_flows(
    ctx: typer.Context,
    bookmark_id: Annotated[
        int,
        typer.Argument(help="Saved flows report bookmark ID."),
    ],
    format: FormatOption = "json",
) -> None:
    """Query a saved Flows report by bookmark ID.

    Retrieves data from a saved Flows report in Mixpanel. The bookmark_id
    can be found in the URL when viewing a flows report (the numeric ID
    after /flows/).

    Flows reports show user paths through a sequence of events with
    step-by-step conversion rates and path breakdowns.

    Examples:

        mp query flows 12345
        mp query flows 12345 --format table
    """
    workspace = get_workspace(ctx)

    result = workspace.query_flows(bookmark_id=bookmark_id)

    output_result(ctx, result.to_dict(), format=format)


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
    format: FormatOption = "json",
) -> None:
    """Analyze event frequency distribution (addiction analysis).

    Shows how many users performed an event N times within each time period.
    Useful for understanding user engagement depth and "power user" distribution.

    The --addiction-unit controls granularity of frequency buckets (hour or day).
    For example, with --addiction-unit hour, the data shows how many users
    performed the event 1 time, 2 times, 3 times, etc. per hour.

    Output includes date range, units, and data dict mapping dates to
    arrays of user counts (index 0 = users who did it once, 1 = twice, etc.).

    Examples:

        mp query frequency --from 2025-01-01 --to 2025-01-31
        mp query frequency -e "Login" --from 2025-01-01 --to 2025-01-31
        mp query frequency -e "Login" --from 2025-01-01 --to 2025-01-31 --addiction-unit day
    """
    validated_unit = validate_time_unit(unit)
    validated_addiction_unit = validate_hour_day_unit(
        addiction_unit, "--addiction-unit"
    )
    workspace = get_workspace(ctx)

    result = workspace.frequency(
        from_date=from_date,
        to_date=to_date,
        event=event,
        unit=validated_unit,
        addiction_unit=validated_addiction_unit,
        where=where,
    )

    output_result(ctx, result.to_dict(), format=format)


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
        typer.Option("--type", "-t", help="Count type: general, unique, average."),
    ] = "general",
    unit: Annotated[
        str,
        typer.Option("--unit", "-u", help="Time unit: hour, day."),
    ] = "day",
    where: Annotated[
        str | None,
        typer.Option("--where", "-w", help="Filter expression."),
    ] = None,
    format: FormatOption = "json",
) -> None:
    """Bucket events by numeric property ranges.

    Groups events into buckets based on a numeric property's value.
    Mixpanel automatically determines optimal bucket ranges based on
    the property's value distribution.

    For example, --on price might create buckets like "0-10", "10-50", "50+".

    The --type option controls how counts are calculated:
    - general: Total event occurrences (default)
    - unique: Unique users who triggered the event
    - average: Average events per user

    Output includes event, property, date range, buckets info, and values
    dict mapping bucket labels to their date/count series.

    Examples:

        mp query segmentation-numeric -e "Purchase" --on amount --from 2025-01-01 --to 2025-01-31
        mp query segmentation-numeric -e "Purchase" --on amount --from 2025-01-01 --to 2025-01-31 --type unique
    """
    validated_type = validate_count_type(type_)
    validated_unit = validate_hour_day_unit(unit)
    workspace = get_workspace(ctx)

    result = workspace.segmentation_numeric(
        event=event,
        on=on,
        from_date=from_date,
        to_date=to_date,
        type=validated_type,
        unit=validated_unit,
        where=where,
    )

    output_result(ctx, result.to_dict(), format=format)


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
        typer.Option("--unit", "-u", help="Time unit: hour, day."),
    ] = "day",
    where: Annotated[
        str | None,
        typer.Option("--where", "-w", help="Filter expression."),
    ] = None,
    format: FormatOption = "json",
) -> None:
    """Calculate sum of numeric property over time.

    Sums the values of a numeric property across all matching events.
    Useful for tracking totals like revenue, quantity, or duration.

    For example, --event Purchase --on revenue calculates total revenue
    per time period.

    Output includes event, property, date range, and results dict mapping
    dates to the sum of property values for that period.

    Examples:

        mp query segmentation-sum -e "Purchase" --on revenue --from 2025-01-01 --to 2025-01-31
        mp query segmentation-sum -e "Purchase" --on quantity --from 2025-01-01 --to 2025-01-31 --unit hour
    """
    validated_unit = validate_hour_day_unit(unit)
    workspace = get_workspace(ctx)

    result = workspace.segmentation_sum(
        event=event,
        on=on,
        from_date=from_date,
        to_date=to_date,
        unit=validated_unit,
        where=where,
    )

    output_result(ctx, result.to_dict(), format=format)


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
        typer.Option("--unit", "-u", help="Time unit: hour, day."),
    ] = "day",
    where: Annotated[
        str | None,
        typer.Option("--where", "-w", help="Filter expression."),
    ] = None,
    format: FormatOption = "json",
) -> None:
    """Calculate average of numeric property over time.

    Calculates the mean value of a numeric property across all matching events.
    Useful for tracking averages like order value, session duration, or scores.

    For example, --event Purchase --on order_value calculates average order
    value per time period.

    Output includes event, property, date range, and results dict mapping
    dates to the average property value for that period.

    Examples:

        mp query segmentation-average -e "Purchase" --on order_value --from 2025-01-01 --to 2025-01-31
        mp query segmentation-average -e "Session" --on duration --from 2025-01-01 --to 2025-01-31 --unit hour
    """
    validated_unit = validate_hour_day_unit(unit)
    workspace = get_workspace(ctx)

    result = workspace.segmentation_average(
        event=event,
        on=on,
        from_date=from_date,
        to_date=to_date,
        unit=validated_unit,
        where=where,
    )

    output_result(ctx, result.to_dict(), format=format)
