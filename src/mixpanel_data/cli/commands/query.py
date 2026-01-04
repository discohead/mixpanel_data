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

from mixpanel_data.cli.options import FormatOption, JqOption
from mixpanel_data.cli.utils import (
    ExitCode,
    err_console,
    get_workspace,
    handle_errors,
    output_result,
    present_result,
    status_spinner,
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
    jq_filter: JqOption = None,
) -> None:
    """Execute SQL query against local DuckDB database.

    Query can be provided as an argument or read from a file with --file.
    Use --scalar when your query returns a single value (e.g., COUNT(*)).

    **Output Structure (JSON):**

    Default (row results):

        [
          {"event": "Sign Up", "count": 1500},
          {"event": "Login", "count": 3200},
          {"event": "Purchase", "count": 450}
        ]

    With --scalar:

        {"value": 15234}

    **Examples:**

        mp query sql "SELECT COUNT(*) FROM events" --scalar
        mp query sql "SELECT event, COUNT(*) FROM events GROUP BY 1" --format table
        mp query sql --file analysis.sql --format csv

    **jq Examples:**

        --jq '.[0]'                      # First row
        --jq '.[] | .event'              # All event names
        --jq 'map(select(.count > 100))' # Filter rows
        --jq '.value'                    # Scalar result value
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

    workspace = get_workspace(ctx, read_only=True)

    if scalar:
        result = workspace.sql_scalar(sql_query)
        # For scalar output, just print the raw value
        if format == "plain":
            # Validate jq_filter - should error, not silently ignore
            if jq_filter:
                err_console.print(
                    "[red]Error:[/red] --jq requires --format json or jsonl"
                )
                raise typer.Exit(ExitCode.INVALID_ARGS)
            print(result)
        else:
            output_result(ctx, {"value": result}, format=format, jq_filter=jq_filter)
    else:
        result = workspace.sql_rows(sql_query)
        # Convert SQLResult to list of dicts for proper output formatting
        output_result(ctx, result.to_dicts(), format=format, jq_filter=jq_filter)


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
        typer.Option(
            "--on",
            "-o",
            help="Property to segment by (bare name or expression).",
        ),
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
    jq_filter: JqOption = None,
) -> None:
    """Run live segmentation query against Mixpanel API.

    Returns time-series event counts, optionally segmented by a property.
    Without --on, returns total counts per time period. With --on, breaks
    down counts by property values (e.g., --on country shows counts per country).

    The --on parameter accepts bare property names (e.g., 'country') or full
    filter expressions (e.g., 'properties["country"] == "US"').

    **Output Structure (JSON):**

        {
          "event": "Sign Up",
          "from_date": "2025-01-01",
          "to_date": "2025-01-07",
          "unit": "day",
          "segment_property": "country",
          "total": 1850,
          "series": {
            "US": {"2025-01-01": 150, "2025-01-02": 175, ...},
            "UK": {"2025-01-01": 75, "2025-01-02": 80, ...}
          }
        }

    **Examples:**

        mp query segmentation -e "Sign Up" --from 2025-01-01 --to 2025-01-31
        mp query segmentation -e "Purchase" --from 2025-01-01 --to 2025-01-31 --on country
        mp query segmentation -e "Login" --from 2025-01-01 --to 2025-01-07 --unit week

    **jq Examples:**

        --jq '.total'                    # Total event count
        --jq '.series | keys'            # List segment names
        --jq '.series["US"] | add'       # Sum counts for one segment
    """
    validated_unit = validate_time_unit(unit)
    workspace = get_workspace(ctx, read_only=True)

    with status_spinner(ctx, "Running segmentation query..."):
        result = workspace.segmentation(
            event=event,
            from_date=from_date,
            to_date=to_date,
            on=on,
            unit=validated_unit,
            where=where,
        )

    present_result(ctx, result, format, jq_filter=jq_filter)


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
    jq_filter: JqOption = None,
) -> None:
    """Run live funnel analysis against Mixpanel API.

    Analyzes conversion through a saved funnel's steps. The funnel_id can be
    found in the Mixpanel UI URL when viewing the funnel, or via 'mp inspect funnels'.

    **Output Structure (JSON):**

        {
          "funnel_id": 12345,
          "funnel_name": "Onboarding Funnel",
          "from_date": "2025-01-01",
          "to_date": "2025-01-31",
          "conversion_rate": 0.23,
          "steps": [
            {"event": "Sign Up", "count": 10000, "conversion_rate": 1.0},
            {"event": "Verify Email", "count": 7500, "conversion_rate": 0.75},
            {"event": "Complete Profile", "count": 4200, "conversion_rate": 0.56},
            {"event": "First Purchase", "count": 2300, "conversion_rate": 0.55}
          ]
        }

    **Examples:**

        mp query funnel 12345 --from 2025-01-01 --to 2025-01-31
        mp query funnel 12345 --from 2025-01-01 --to 2025-01-31 --unit week
        mp query funnel 12345 --from 2025-01-01 --to 2025-01-31 --on country

    **jq Examples:**

        --jq '.conversion_rate'              # Overall conversion rate
        --jq '.steps | length'               # Number of funnel steps
        --jq '.steps[-1].count'              # Users completing the funnel
        --jq '.steps[] | {event, rate: .conversion_rate}'
    """
    workspace = get_workspace(ctx, read_only=True)

    with status_spinner(ctx, "Running funnel query..."):
        result = workspace.funnel(
            funnel_id=funnel_id,
            from_date=from_date,
            to_date=to_date,
            unit=unit,
            on=on,
        )

    present_result(ctx, result, format, jq_filter=jq_filter)


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
    jq_filter: JqOption = None,
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

    **Output Structure (JSON):**

        {
          "born_event": "Sign Up",
          "return_event": "Login",
          "from_date": "2025-01-01",
          "to_date": "2025-01-31",
          "unit": "day",
          "cohorts": [
            {"date": "2025-01-01", "size": 500, "retention": [1.0, 0.65, 0.45, 0.38]},
            {"date": "2025-01-02", "size": 480, "retention": [1.0, 0.62, 0.41, 0.35]},
            {"date": "2025-01-03", "size": 520, "retention": [1.0, 0.68, 0.48, 0.40]}
          ]
        }

    **Examples:**

        mp query retention --born "Sign Up" --return "Login" --from 2025-01-01 --to 2025-01-31
        mp query retention --born "Sign Up" --return "Purchase" --from 2025-01-01 --to 2025-01-31 --unit week
        mp query retention --born "Sign Up" --return "Login" --from 2025-01-01 --to 2025-01-31 --intervals 7

    **jq Examples:**

        --jq '.cohorts | length'                   # Number of cohorts
        --jq '.cohorts[0].retention'               # First cohort retention curve
        --jq '.cohorts[] | {date, size, day7: .retention[7]}'
    """
    validated_unit = validate_time_unit(unit)
    workspace = get_workspace(ctx, read_only=True)

    # Use defaults if not provided
    actual_interval = interval if interval is not None else 1
    actual_interval_count = intervals if intervals is not None else 10

    with status_spinner(ctx, "Running retention query..."):
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

    present_result(ctx, result, format, jq_filter=jq_filter)


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
    jq_filter: JqOption = None,
) -> None:
    """Execute JQL script against Mixpanel API.

    Script can be provided as a file argument or inline with --script.
    Parameters can be passed with --param key=value (repeatable).

    **Output Structure (JSON):**

    The output structure depends on your JQL script. Common patterns:

    groupBy result:

        {
          "raw": [
            {"key": ["Login"], "value": 5234},
            {"key": ["Sign Up"], "value": 1892}
          ],
          "row_count": 2
        }

    Aggregation result:

        {
          "raw": [{"count": 15234, "unique_users": 3421}],
          "row_count": 1
        }

    **Examples:**

        mp query jql analysis.js
        mp query jql --script "function main() { return Events({...}).groupBy(['event'], mixpanel.reducer.count()) }"
        mp query jql analysis.js --param start_date=2025-01-01 --param event_name=Login

    **jq Examples:**

        --jq '.raw'                          # Get raw result array
        --jq '.raw[0]'                       # First result row
        --jq '.raw[] | {event: .key[0], count: .value}'
        --jq '.row_count'                    # Number of result rows
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

    workspace = get_workspace(ctx, read_only=True)

    with status_spinner(ctx, "Running JQL query..."):
        result = workspace.jql(
            script=jql_script,
            params=params if params else None,
        )

    present_result(ctx, result, format, jq_filter=jq_filter)


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
    jq_filter: JqOption = None,
) -> None:
    """Query event counts over time for multiple events.

    Compares multiple events on the same time series. Pass comma-separated
    event names to --events (e.g., --events "Sign Up,Login,Purchase").

    The --type option controls how counts are calculated:
    - general: Total event occurrences (default)
    - unique: Unique users who triggered the event
    - average: Average events per user

    **Output Structure (JSON):**

        {
          "events": ["Sign Up", "Login", "Purchase"],
          "from_date": "2025-01-01",
          "to_date": "2025-01-07",
          "unit": "day",
          "type": "general",
          "series": {
            "Sign Up": {"2025-01-01": 150, "2025-01-02": 175, ...},
            "Login": {"2025-01-01": 520, "2025-01-02": 610, ...},
            "Purchase": {"2025-01-01": 45, "2025-01-02": 52, ...}
          }
        }

    **Examples:**

        mp query event-counts --events "Sign Up,Login,Purchase" --from 2025-01-01 --to 2025-01-31
        mp query event-counts --events "Sign Up,Purchase" --from 2025-01-01 --to 2025-01-31 --type unique
        mp query event-counts --events "Login" --from 2025-01-01 --to 2025-01-31 --unit week

    **jq Examples:**

        --jq '.series | keys'                # List event names
        --jq '.series["Login"] | add'        # Sum counts for one event
        --jq '.series["Login"]["2025-01-01"]'  # Count for specific date
        --jq '[.series | to_entries[] | {event: .key, total: (.value | add)}]'
    """
    validated_type = validate_count_type(type_)
    validated_unit = validate_time_unit(unit)

    # Parse events
    events_list = [e.strip() for e in events.split(",")]

    workspace = get_workspace(ctx, read_only=True)

    with status_spinner(ctx, "Running event counts query..."):
        result = workspace.event_counts(
            events=events_list,
            from_date=from_date,
            to_date=to_date,
            type=validated_type,
            unit=validated_unit,
        )

    present_result(ctx, result, format, jq_filter=jq_filter)


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
    jq_filter: JqOption = None,
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

    **Output Structure (JSON):**

        {
          "event": "Purchase",
          "property_name": "country",
          "from_date": "2025-01-01",
          "to_date": "2025-01-07",
          "unit": "day",
          "type": "general",
          "series": {
            "US": {"2025-01-01": 150, "2025-01-02": 175, ...},
            "UK": {"2025-01-01": 75, "2025-01-02": 80, ...},
            "DE": {"2025-01-01": 45, "2025-01-02": 52, ...}
          }
        }

    **Examples:**

        mp query property-counts -e "Purchase" -p country --from 2025-01-01 --to 2025-01-31
        mp query property-counts -e "Sign Up" -p "utm_source" --from 2025-01-01 --to 2025-01-31 --limit 20
        mp query property-counts -e "Login" -p browser --from 2025-01-01 --to 2025-01-31 --type unique

    **jq Examples:**

        --jq '.series | keys'                # List property values
        --jq '.series["US"] | add'           # Sum counts for one value
        --jq '.series | to_entries | sort_by(.value | add) | reverse'
        --jq '[.series | to_entries[] | {value: .key, total: (.value | add)}]'
    """
    validated_type = validate_count_type(type_)
    validated_unit = validate_time_unit(unit)
    workspace = get_workspace(ctx, read_only=True)

    with status_spinner(ctx, "Running property counts query..."):
        result = workspace.property_counts(
            event=event,
            property_name=property_name,
            from_date=from_date,
            to_date=to_date,
            type=validated_type,
            unit=validated_unit,
            limit=limit,
        )

    present_result(ctx, result, format, jq_filter=jq_filter)


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
    jq_filter: JqOption = None,
) -> None:
    """Query user activity feed for specific users.

    Retrieves the event history for one or more users identified by their
    distinct_id. Pass comma-separated IDs to --users.

    Optionally filter by date range with --from and --to. Without date
    filters, returns recent activity (API default).

    **Output Structure (JSON):**

        {
          "distinct_ids": ["user123", "user456"],
          "from_date": "2025-01-01",
          "to_date": "2025-01-31",
          "event_count": 47,
          "events": [
            {
              "event": "Login",
              "time": "2025-01-15T10:30:00+00:00",
              "properties": {"$browser": "Chrome", "$city": "San Francisco", ...}
            },
            {
              "event": "Purchase",
              "time": "2025-01-15T11:45:00+00:00",
              "properties": {"product_id": "SKU123", "amount": 99.99, ...}
            }
          ]
        }

    **Examples:**

        mp query activity-feed --users "user123"
        mp query activity-feed --users "user123,user456" --from 2025-01-01 --to 2025-01-31
        mp query activity-feed --users "user123" --format table

    **jq Examples:**

        --jq '.event_count'                  # Total number of events
        --jq '.events | length'              # Same as above
        --jq '.events[].event'               # List all event names
        --jq '.events | group_by(.event) | map({event: .[0].event, count: length})'
    """
    # Parse users
    user_list = [u.strip() for u in users.split(",")]

    workspace = get_workspace(ctx, read_only=True)

    with status_spinner(ctx, "Fetching activity feed..."):
        result = workspace.activity_feed(
            distinct_ids=user_list,
            from_date=from_date,
            to_date=to_date,
        )

    present_result(ctx, result, format, jq_filter=jq_filter)


@query_app.command("saved-report")
@handle_errors
def query_saved_report(
    ctx: typer.Context,
    bookmark_id: Annotated[
        int,
        typer.Argument(help="Saved report bookmark ID."),
    ],
    format: FormatOption = "json",
    jq_filter: JqOption = None,
) -> None:
    """Query a saved report (Insights, Retention, or Funnel) by bookmark ID.

    Retrieves data from a saved report in Mixpanel. The bookmark_id
    can be found in the URL when viewing a report (the numeric ID
    after /insights/, /retention/, or /funnels/).

    The report type is automatically detected from the response headers.

    **Output Structure (JSON):**

    Insights report:

        {
          "bookmark_id": 12345,
          "computed_at": "2025-01-15T10:30:00Z",
          "from_date": "2025-01-01",
          "to_date": "2025-01-31",
          "headers": ["$event"],
          "series": {
            "Sign Up": {"2025-01-01": 150, "2025-01-02": 175, ...},
            "Login": {"2025-01-01": 520, "2025-01-02": 610, ...}
          },
          "report_type": "insights"
        }

    Funnel/Retention reports have different series structures based on
    the saved report configuration.

    **Examples:**

        mp query saved-report 12345
        mp query saved-report 12345 --format table

    **jq Examples:**

        --jq '.report_type'                  # Report type (insights/retention/funnel)
        --jq '.series | keys'                # List series names
        --jq '.headers'                      # Report column headers
        --jq '.series | to_entries | map({name: .key, total: (.value | add)})'
    """
    workspace = get_workspace(ctx, read_only=True)

    with status_spinner(ctx, "Querying saved report..."):
        result = workspace.query_saved_report(bookmark_id=bookmark_id)

    output_result(ctx, result.to_dict(), format=format, jq_filter=jq_filter)


@query_app.command("flows")
@handle_errors
def query_flows(
    ctx: typer.Context,
    bookmark_id: Annotated[
        int,
        typer.Argument(help="Saved flows report bookmark ID."),
    ],
    format: FormatOption = "json",
    jq_filter: JqOption = None,
) -> None:
    """Query a saved Flows report by bookmark ID.

    Retrieves data from a saved Flows report in Mixpanel. The bookmark_id
    can be found in the URL when viewing a flows report (the numeric ID
    after /flows/).

    Flows reports show user paths through a sequence of events with
    step-by-step conversion rates and path breakdowns.

    **Output Structure (JSON):**

        {
          "bookmark_id": 12345,
          "computed_at": "2025-01-15T10:30:00Z",
          "steps": [
            {"step": 1, "event": "Sign Up", "count": 10000},
            {"step": 2, "event": "Verify Email", "count": 7500},
            {"step": 3, "event": "Complete Profile", "count": 4200}
          ],
          "breakdowns": [
            {"path": ["Sign Up", "Verify Email", "Complete Profile"], "count": 3800},
            {"path": ["Sign Up", "Verify Email", "Drop Off"], "count": 3300}
          ],
          "overall_conversion_rate": 0.42,
          "metadata": {...}
        }

    **Examples:**

        mp query flows 12345
        mp query flows 12345 --format table

    **jq Examples:**

        --jq '.overall_conversion_rate'      # End-to-end conversion rate
        --jq '.steps | length'               # Number of flow steps
        --jq '.steps[] | {event, count}'     # Event and count per step
        --jq '.breakdowns | sort_by(.count) | reverse | .[0]'
    """
    workspace = get_workspace(ctx, read_only=True)

    with status_spinner(ctx, "Querying flows report..."):
        result = workspace.query_flows(bookmark_id=bookmark_id)

    present_result(ctx, result, format, jq_filter=jq_filter)


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
    jq_filter: JqOption = None,
) -> None:
    """Analyze event frequency distribution (addiction analysis).

    Shows how many users performed an event N times within each time period.
    Useful for understanding user engagement depth and "power user" distribution.

    The --addiction-unit controls granularity of frequency buckets (hour or day).
    For example, with --addiction-unit hour, the data shows how many users
    performed the event 1 time, 2 times, 3 times, etc. per hour.

    **Output Structure (JSON):**

        {
          "event": "Login",
          "from_date": "2025-01-01",
          "to_date": "2025-01-07",
          "unit": "day",
          "addiction_unit": "hour",
          "data": {
            "2025-01-01": [500, 250, 125, 60, 30, 15],
            "2025-01-02": [520, 260, 130, 65, 32, 16],
            ...
          }
        }

    Each array shows user counts by frequency (index 0 = 1x, index 1 = 2x, etc.).

    **Examples:**

        mp query frequency --from 2025-01-01 --to 2025-01-31
        mp query frequency -e "Login" --from 2025-01-01 --to 2025-01-31
        mp query frequency -e "Login" --from 2025-01-01 --to 2025-01-31 --addiction-unit day

    **jq Examples:**

        --jq '.data | keys'                  # List all dates
        --jq '.data["2025-01-01"][0]'        # Users who did it once on Jan 1
        --jq '.data["2025-01-01"] | add'     # Total active users on Jan 1
        --jq '.data | to_entries | map({date: .key, power_users: .value[4:] | add})'
    """
    validated_unit = validate_time_unit(unit)
    validated_addiction_unit = validate_hour_day_unit(
        addiction_unit, "--addiction-unit"
    )
    workspace = get_workspace(ctx, read_only=True)

    with status_spinner(ctx, "Running frequency query..."):
        result = workspace.frequency(
            from_date=from_date,
            to_date=to_date,
            event=event,
            unit=validated_unit,
            addiction_unit=validated_addiction_unit,
            where=where,
        )

    present_result(ctx, result, format, jq_filter=jq_filter)


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
        typer.Option(
            "--on",
            "-o",
            help="Numeric property to bucket (bare name or expression).",
        ),
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
    jq_filter: JqOption = None,
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

    **Output Structure (JSON):**

        {
          "event": "Purchase",
          "from_date": "2025-01-01",
          "to_date": "2025-01-07",
          "property_expr": "amount",
          "unit": "day",
          "series": {
            "0-50": {"2025-01-01": 120, "2025-01-02": 135, ...},
            "50-100": {"2025-01-01": 85, "2025-01-02": 92, ...},
            "100-500": {"2025-01-01": 45, "2025-01-02": 52, ...},
            "500+": {"2025-01-01": 12, "2025-01-02": 15, ...}
          }
        }

    **Examples:**

        mp query segmentation-numeric -e "Purchase" --on amount --from 2025-01-01 --to 2025-01-31
        mp query segmentation-numeric -e "Purchase" --on amount --from 2025-01-01 --to 2025-01-31 --type unique

    **jq Examples:**

        --jq '.series | keys'                # List bucket ranges
        --jq '.series["100-500"] | add'      # Sum counts for a bucket
        --jq '[.series | to_entries[] | {bucket: .key, total: (.value | add)}]'
        --jq '.series | to_entries | sort_by(.value | add) | reverse'
    """
    validated_type = validate_count_type(type_)
    validated_unit = validate_hour_day_unit(unit)
    workspace = get_workspace(ctx, read_only=True)

    with status_spinner(ctx, "Running numeric segmentation..."):
        result = workspace.segmentation_numeric(
            event=event,
            on=on,
            from_date=from_date,
            to_date=to_date,
            type=validated_type,
            unit=validated_unit,
            where=where,
        )

    present_result(ctx, result, format, jq_filter=jq_filter)


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
        typer.Option(
            "--on",
            "-o",
            help="Numeric property to sum (bare name or expression).",
        ),
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
    jq_filter: JqOption = None,
) -> None:
    """Calculate sum of numeric property over time.

    Sums the values of a numeric property across all matching events.
    Useful for tracking totals like revenue, quantity, or duration.

    For example, --event Purchase --on revenue calculates total revenue
    per time period.

    **Output Structure (JSON):**

        {
          "event": "Purchase",
          "from_date": "2025-01-01",
          "to_date": "2025-01-07",
          "property_expr": "revenue",
          "unit": "day",
          "results": {
            "2025-01-01": 15234.50,
            "2025-01-02": 18456.75,
            "2025-01-03": 12890.25,
            ...
          }
        }

    **Examples:**

        mp query segmentation-sum -e "Purchase" --on revenue --from 2025-01-01 --to 2025-01-31
        mp query segmentation-sum -e "Purchase" --on quantity --from 2025-01-01 --to 2025-01-31 --unit hour

    **jq Examples:**

        --jq '.results | add'                # Total sum across all dates
        --jq '.results | to_entries | max_by(.value)'  # Highest day
        --jq '.results | to_entries | min_by(.value)'  # Lowest day
        --jq '[.results | to_entries[] | {date: .key, revenue: .value}]'
    """
    validated_unit = validate_hour_day_unit(unit)
    workspace = get_workspace(ctx, read_only=True)

    with status_spinner(ctx, "Running sum query..."):
        result = workspace.segmentation_sum(
            event=event,
            on=on,
            from_date=from_date,
            to_date=to_date,
            unit=validated_unit,
            where=where,
        )

    present_result(ctx, result, format, jq_filter=jq_filter)


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
        typer.Option(
            "--on",
            "-o",
            help="Numeric property to average (bare name or expression).",
        ),
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
    jq_filter: JqOption = None,
) -> None:
    """Calculate average of numeric property over time.

    Calculates the mean value of a numeric property across all matching events.
    Useful for tracking averages like order value, session duration, or scores.

    For example, --event Purchase --on order_value calculates average order
    value per time period.

    **Output Structure (JSON):**

        {
          "event": "Purchase",
          "from_date": "2025-01-01",
          "to_date": "2025-01-07",
          "property_expr": "order_value",
          "unit": "day",
          "results": {
            "2025-01-01": 85.50,
            "2025-01-02": 92.75,
            "2025-01-03": 78.25,
            ...
          }
        }

    **Examples:**

        mp query segmentation-average -e "Purchase" --on order_value --from 2025-01-01 --to 2025-01-31
        mp query segmentation-average -e "Session" --on duration --from 2025-01-01 --to 2025-01-31 --unit hour

    **jq Examples:**

        --jq '.results | add / length'       # Overall average
        --jq '.results | to_entries | max_by(.value)'  # Highest day
        --jq '.results | to_entries | min_by(.value)'  # Lowest day
        --jq '[.results | to_entries[] | {date: .key, avg: .value}]'
    """
    validated_unit = validate_hour_day_unit(unit)
    workspace = get_workspace(ctx, read_only=True)

    with status_spinner(ctx, "Running average query..."):
        result = workspace.segmentation_average(
            event=event,
            on=on,
            from_date=from_date,
            to_date=to_date,
            unit=validated_unit,
            where=where,
        )

    present_result(ctx, result, format, jq_filter=jq_filter)
