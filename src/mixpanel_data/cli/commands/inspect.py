"""Schema discovery and local database inspection commands.

This module provides commands for inspecting data:

Live (calls Mixpanel API):
- events: List event names from Mixpanel
- properties: List properties for an event
- values: List values for a property
- funnels: List saved funnels
- cohorts: List saved cohorts
- top-events: List today's top events
- bookmarks: List saved reports (bookmarks)
- lexicon-schemas: List Lexicon schemas
- lexicon-schema: Get a single Lexicon schema

JQL-based Remote Discovery (calls Mixpanel API with JQL):
- distribution: Property value distribution with counts/percentages
- numeric: Numeric property statistics (min/max/avg/percentiles)
- daily: Daily event counts over time
- engagement: User engagement distribution by event count
- coverage: Property coverage/null rate statistics

Local (uses DuckDB):
- info: Show workspace information
- tables: List local tables
- schema: Show table schema
- drop: Drop a table
- drop-all: Drop all tables
- sample: Show random sample rows
- summarize: Show statistical summary
- breakdown: Show event distribution
- keys: List JSON property keys
- column: Show column statistics
"""

from __future__ import annotations

from typing import Annotated

import typer

from mixpanel_data.cli.options import FormatOption, JqOption
from mixpanel_data.cli.utils import (
    err_console,
    get_workspace,
    handle_errors,
    output_result,
    status_spinner,
)
from mixpanel_data.cli.validators import (
    validate_count_type,
    validate_entity_type,
    validate_table_type,
)

inspect_app = typer.Typer(
    name="inspect",
    help="Inspect schema and local database.",
    epilog="""Live (calls Mixpanel API):
  events, properties, values, funnels, cohorts, top-events, bookmarks,
  lexicon-schemas, lexicon-schema

JQL-based Remote Discovery:
  distribution, numeric, daily, engagement, coverage

Local (uses DuckDB):
  info, tables, schema, drop, drop-all, sample, summarize, breakdown, keys, column""",
    no_args_is_help=True,
    rich_markup_mode="markdown",
)


@inspect_app.command("events")
@handle_errors
def inspect_events(
    ctx: typer.Context,
    format: FormatOption = "json",
    jq_filter: JqOption = None,
) -> None:
    """List all event names from Mixpanel project.

    Calls the Mixpanel API to retrieve tracked event types. Use this
    to discover what events exist before fetching or querying.

    Output Structure (JSON):

        ["Sign Up", "Login", "Purchase", "Page View", "Add to Cart"]

    Examples:

        mp inspect events
        mp inspect events --format table
        mp inspect events --format json --jq '.[0:3]'

    **jq Examples:**

        --jq '.[0:5]'                                 # Get first 5 events
        --jq 'length'                                 # Count total events
        --jq '[.[] | select(contains("Purchase"))]'  # Find events containing "Purchase"
        --jq 'sort'                                   # Sort alphabetically
    """
    workspace = get_workspace(ctx, read_only=True)
    with status_spinner(ctx, "Fetching events..."):
        events = workspace.events()
    output_result(ctx, events, format=format, jq_filter=jq_filter)


@inspect_app.command("properties")
@handle_errors
def inspect_properties(
    ctx: typer.Context,
    event: Annotated[
        str,
        typer.Option("--event", "-e", help="Event name."),
    ],
    format: FormatOption = "json",
    jq_filter: JqOption = None,
) -> None:
    """List properties for a specific event.

    Calls the Mixpanel API to retrieve property names tracked with an event.
    Shows both custom event properties and default Mixpanel properties.

    Output Structure (JSON):

        ["country", "browser", "device", "$city", "$region", "plan_type"]

    Examples:

        mp inspect properties -e "Sign Up"
        mp inspect properties -e "Purchase" --format table

    **jq Examples:**

        --jq '.[0:10]'                                    # Get first 10 properties
        --jq '[.[] | select(startswith("$") | not)]'     # User-defined properties (no $ prefix)
        --jq '[.[] | select(startswith("$"))]'           # Mixpanel system properties ($ prefix)
        --jq 'length'                                     # Count properties
    """
    workspace = get_workspace(ctx, read_only=True)
    with status_spinner(ctx, "Fetching properties..."):
        properties = workspace.properties(event)
    output_result(ctx, properties, format=format, jq_filter=jq_filter)


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
    format: FormatOption = "json",
    jq_filter: JqOption = None,
) -> None:
    """List sample values for a property.

    Calls the Mixpanel API to retrieve sample values for a property.
    Useful for understanding the data shape before writing queries.

    Output Structure (JSON):

        ["US", "UK", "DE", "FR", "CA", "AU", "JP"]

    Examples:

        mp inspect values -p country
        mp inspect values -p country -e "Sign Up" --limit 20
        mp inspect values -p browser --format table

    **jq Examples:**

        --jq '.[0:5]'                          # Get first 5 values
        --jq 'length'                          # Count unique values
        --jq '[.[] | select(test("^U"))]'      # Filter values matching pattern
        --jq 'sort'                            # Sort values alphabetically
    """
    workspace = get_workspace(ctx, read_only=True)
    with status_spinner(ctx, "Fetching values..."):
        values = workspace.property_values(
            property_name=property_name,
            event=event,
            limit=limit,
        )
    output_result(ctx, values, format=format, jq_filter=jq_filter)


@inspect_app.command("funnels")
@handle_errors
def inspect_funnels(
    ctx: typer.Context,
    format: FormatOption = "json",
    jq_filter: JqOption = None,
) -> None:
    """List saved funnels in Mixpanel project.

    Calls the Mixpanel API to retrieve saved funnel definitions.
    Use the funnel_id with 'mp query funnel' to run funnel analysis.

    Output Structure (JSON):

        [
          {"funnel_id": 12345, "name": "Onboarding Flow"},
          {"funnel_id": 12346, "name": "Purchase Funnel"},
          {"funnel_id": 12347, "name": "Trial to Paid"}
        ]

    Examples:

        mp inspect funnels
        mp inspect funnels --format table

    **jq Examples:**

        --jq '[.[].funnel_id]'                               # Get all funnel IDs
        --jq '.[] | select(.name | test("Purchase"; "i"))'   # Find funnel by name pattern
        --jq '[.[].name]'                                    # Get funnel names only
        --jq 'length'                                        # Count funnels
    """
    workspace = get_workspace(ctx, read_only=True)
    with status_spinner(ctx, "Fetching funnels..."):
        funnels = workspace.funnels()
    data = [{"funnel_id": f.funnel_id, "name": f.name} for f in funnels]
    output_result(
        ctx, data, columns=["funnel_id", "name"], format=format, jq_filter=jq_filter
    )


@inspect_app.command("cohorts")
@handle_errors
def inspect_cohorts(
    ctx: typer.Context,
    format: FormatOption = "json",
    jq_filter: JqOption = None,
) -> None:
    """List saved cohorts in Mixpanel project.

    Calls the Mixpanel API to retrieve saved cohort definitions.
    Shows cohort ID, name, user count, and description.

    Output Structure (JSON):

        [
          {"id": 1001, "name": "Power Users", "count": 5420, "description": "Users with 10+ sessions"},
          {"id": 1002, "name": "Trial Users", "count": 892, "description": "Active trial accounts"},
          {"id": 1003, "name": "Churned", "count": 2341, "description": "No activity in 30 days"}
        ]

    Examples:

        mp inspect cohorts
        mp inspect cohorts --format table

    **jq Examples:**

        --jq '[.[] | select(.count > 1000)]'           # Cohorts with more than 1000 users
        --jq '[.[].name]'                              # Get cohort names only
        --jq 'sort_by(.count) | reverse'               # Sort by user count descending
        --jq '.[] | select(.name == "Power Users")'    # Find cohort by name
    """
    workspace = get_workspace(ctx, read_only=True)
    with status_spinner(ctx, "Fetching cohorts..."):
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
    output_result(
        ctx,
        data,
        columns=["id", "name", "count", "description"],
        format=format,
        jq_filter=jq_filter,
    )


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
    format: FormatOption = "json",
    jq_filter: JqOption = None,
) -> None:
    """List today's top events by count.

    Calls the Mixpanel API to retrieve today's most frequent events.
    Useful for quick overview of project activity.

    Output Structure (JSON):

        [
          {"event": "Page View", "count": 15234, "percent_change": 12.5},
          {"event": "Login", "count": 8921, "percent_change": -3.2},
          {"event": "Purchase", "count": 1456, "percent_change": 8.7}
        ]

    Examples:

        mp inspect top-events
        mp inspect top-events --limit 20 --format table
        mp inspect top-events --type unique

    **jq Examples:**

        --jq '[.[] | select(.percent_change > 0)]'    # Events with positive growth
        --jq '[.[].event]'                            # Get just event names
        --jq '[.[] | select(.count > 10000)]'         # Events with count over 10000
        --jq 'max_by(.percent_change)'                # Event with highest growth
    """
    validated_type = validate_count_type(type_)
    workspace = get_workspace(ctx, read_only=True)
    with status_spinner(ctx, "Fetching top events..."):
        events = workspace.top_events(type=validated_type, limit=limit)
    data = [
        {
            "event": e.event,
            "count": e.count,
            "percent_change": e.percent_change,
        }
        for e in events
    ]
    output_result(
        ctx,
        data,
        columns=["event", "count", "percent_change"],
        format=format,
        jq_filter=jq_filter,
    )


@inspect_app.command("bookmarks")
@handle_errors
def inspect_bookmarks(
    ctx: typer.Context,
    type_: Annotated[
        str | None,
        typer.Option(
            "--type",
            "-t",
            help="Filter by type: insights, funnels, retention, flows, launch-analysis.",
        ),
    ] = None,
    format: FormatOption = "json",
    jq_filter: JqOption = None,
) -> None:
    """List saved reports (bookmarks) in Mixpanel project.

    Calls the Mixpanel API to retrieve saved report definitions.
    Use the bookmark ID with 'mp query saved-report' or 'mp query flows'.

    Output Structure (JSON):

        [
          {"id": 98765, "name": "Weekly KPIs", "type": "insights", "modified": "2024-01-15T10:30:00"},
          {"id": 98766, "name": "Conversion Funnel", "type": "funnels", "modified": "2024-01-14T15:45:00"},
          {"id": 98767, "name": "User Retention", "type": "retention", "modified": "2024-01-13T09:20:00"}
        ]

    Examples:

        mp inspect bookmarks
        mp inspect bookmarks --type insights
        mp inspect bookmarks --type funnels --format table

    **jq Examples:**

        --jq '[.[] | select(.type == "insights")]'    # Get bookmarks by type
        --jq '[.[].id]'                               # Get bookmark IDs only
        --jq 'sort_by(.modified) | reverse'           # Sort by modified date (newest first)
        --jq '.[] | select(.name | test("KPI"; "i"))' # Find bookmark by name
    """
    workspace = get_workspace(ctx, read_only=True)

    with status_spinner(ctx, "Fetching bookmarks..."):
        bookmarks = workspace.list_bookmarks(bookmark_type=type_)  # type: ignore[arg-type]
    data = [
        {
            "id": b.id,
            "name": b.name,
            "type": b.type,
            "modified": b.modified,
        }
        for b in bookmarks
    ]
    output_result(
        ctx,
        data,
        columns=["id", "name", "type", "modified"],
        format=format,
        jq_filter=jq_filter,
    )


@inspect_app.command("info")
@handle_errors
def inspect_info(
    ctx: typer.Context,
    format: FormatOption = "json",
    jq_filter: JqOption = None,
) -> None:
    """Show workspace information.

    Shows current account configuration, database location, and
    connection status. Uses local configuration only (no API call).

    Output Structure (JSON):

        {
          "path": "/path/to/mixpanel.db",
          "project_id": "12345",
          "region": "us",
          "account": "production",
          "tables": ["events", "profiles"],
          "size_mb": 42.5,
          "created_at": "2024-01-10T08:00:00"
        }

    Examples:

        mp inspect info
        mp inspect info --format json

    **jq Examples:**

        --jq '.path'         # Get database path
        --jq '.project_id'   # Get project ID
        --jq '.tables'       # Get list of tables
        --jq '.size_mb'      # Get database size in MB
    """
    workspace = get_workspace(ctx, read_only=True)
    info = workspace.info()
    output_result(ctx, info.to_dict(), format=format, jq_filter=jq_filter)


@inspect_app.command("tables")
@handle_errors
def inspect_tables(
    ctx: typer.Context,
    format: FormatOption = "json",
    jq_filter: JqOption = None,
) -> None:
    """List tables in local database.

    Shows all tables in the local DuckDB database with row counts
    and fetch timestamps. Use this to see what data has been fetched.

    Output Structure (JSON):

        [
          {"name": "events", "type": "events", "row_count": 125000, "fetched_at": "2024-01-15T10:30:00"},
          {"name": "jan_events", "type": "events", "row_count": 45000, "fetched_at": "2024-01-10T08:00:00"},
          {"name": "profiles", "type": "profiles", "row_count": 8500, "fetched_at": "2024-01-14T14:20:00"}
        ]

    Examples:

        mp inspect tables
        mp inspect tables --format table

    **jq Examples:**

        --jq '[.[].name]'                               # Get table names only
        --jq '[.[] | select(.row_count > 100000)]'      # Tables with more than 100k rows
        --jq '[.[] | select(.type == "events")]'        # Get only event tables
        --jq '[.[].row_count] | add'                    # Total row count across all tables
    """
    workspace = get_workspace(ctx, read_only=True)
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
    output_result(
        ctx,
        data,
        columns=["name", "type", "row_count", "fetched_at"],
        format=format,
        jq_filter=jq_filter,
    )


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
    format: FormatOption = "json",
    jq_filter: JqOption = None,
) -> None:
    """Show schema for a table in local database.

    Lists all columns with their types and nullability constraints.
    Useful for understanding the data structure before writing SQL.

    Note: The --sample option is reserved for future implementation.

    Output Structure (JSON):

        {
          "table": "events",
          "columns": [
            {"name": "event_name", "type": "VARCHAR", "nullable": false},
            {"name": "event_time", "type": "TIMESTAMP", "nullable": false},
            {"name": "distinct_id", "type": "VARCHAR", "nullable": false},
            {"name": "properties", "type": "JSON", "nullable": true}
          ]
        }

    Examples:

        mp inspect schema -t events
        mp inspect schema -t events --format table

    **jq Examples:**

        --jq '.columns | [.[].name]'                   # Get column names only
        --jq '.columns | [.[] | select(.nullable)]'   # Get nullable columns
        --jq '.columns | [.[] | {name, type}]'        # Get column types
        --jq '.columns | length'                       # Count columns
    """
    # Note: _sample is reserved for future implementation
    workspace = get_workspace(ctx, read_only=True)
    schema = workspace.table_schema(table)

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

    output_result(ctx, data, format=format, jq_filter=jq_filter)


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
    format: FormatOption = "json",
    jq_filter: JqOption = None,
) -> None:
    """Drop a table from the local database.

    Permanently removes a table and all its data. Use --force to skip
    the confirmation prompt. Commonly used before re-fetching data.

    Output Structure (JSON):

        {"dropped": "old_events"}

    Examples:

        mp inspect drop -t old_events
        mp inspect drop -t events --force

    **jq Examples:**

        --jq '.dropped'    # Get dropped table name
    """
    if not force:
        confirm = typer.confirm(f"Drop table '{table}'?")
        if not confirm:
            err_console.print("[yellow]Cancelled[/yellow]")
            raise typer.Exit(2)

    workspace = get_workspace(ctx)  # write access needed for drop
    workspace.drop(table)

    output_result(ctx, {"dropped": table}, format=format, jq_filter=jq_filter)


@inspect_app.command("drop-all")
@handle_errors
def inspect_drop_all(
    ctx: typer.Context,
    type_: Annotated[
        str | None,
        typer.Option(
            "--type", "-t", help="Only drop tables of this type: events or profiles."
        ),
    ] = None,
    force: Annotated[
        bool,
        typer.Option("--force", help="Skip confirmation prompt."),
    ] = False,
    format: FormatOption = "json",
    jq_filter: JqOption = None,
) -> None:
    """Drop all tables from the local database.

    Permanently removes all tables and their data. Use --type to filter
    by table type. Use --force to skip the confirmation prompt.

    Output Structure (JSON):

        {"dropped_count": 3}

        # With type filter:
        {"dropped_count": 2, "type_filter": "events"}

    Examples:

        mp inspect drop-all --force
        mp inspect drop-all --type events --force
        mp inspect drop-all -t profiles --force

    **jq Examples:**

        --jq '.dropped_count'        # Get count of dropped tables
        --jq '.dropped_count > 0'    # Check if any tables were dropped
    """
    # Validate type if provided
    type_filter = validate_table_type(type_) if type_ is not None else None

    workspace = get_workspace(ctx)  # write access needed for drop

    # Get count before dropping for output
    tables = workspace.tables()
    if type_filter is not None:
        tables = [t for t in tables if t.type == type_filter]
    count = len(tables)

    if not force:
        type_msg = f" of type '{type_filter}'" if type_filter else ""
        confirm = typer.confirm(f"Drop all {count} tables{type_msg}?")
        if not confirm:
            err_console.print("[yellow]Cancelled[/yellow]")
            raise typer.Exit(2)

    workspace.drop_all(type=type_filter)

    result: dict[str, str | int] = {"dropped_count": count}
    if type_filter is not None:
        result["type_filter"] = type_filter

    output_result(ctx, result, format=format, jq_filter=jq_filter)


@inspect_app.command("lexicon-schemas")
@handle_errors
def inspect_lexicon_schemas(
    ctx: typer.Context,
    type_: Annotated[
        str | None,
        typer.Option(
            "--type", "-t", help="Entity type: event, profile, custom_event, etc."
        ),
    ] = None,
    format: FormatOption = "json",
    jq_filter: JqOption = None,
) -> None:
    """List Lexicon schemas from Mixpanel data dictionary.

    Retrieves documented event and profile property schemas from the
    Mixpanel Lexicon. Shows schema names, types, and property counts.

    Output Structure (JSON):

        [
          {"entity_type": "event", "name": "Purchase", "property_count": 12, "description": "User completed purchase"},
          {"entity_type": "event", "name": "Sign Up", "property_count": 8, "description": "New user registration"},
          {"entity_type": "profile", "name": "Plan Type", "property_count": 3, "description": "User subscription tier"}
        ]

    Examples:

        mp inspect lexicon-schemas
        mp inspect lexicon-schemas --type event
        mp inspect lexicon-schemas --type profile --format table

    **jq Examples:**

        --jq '[.[] | select(.entity_type == "event")]'             # Get only event schemas
        --jq '[.[].name]'                                          # Get schema names
        --jq '[.[] | select(.property_count > 10)]'                # Schemas with many properties
        --jq '[.[] | select(.description | test("purchase"; "i"))]' # Search by description
    """
    validated_type = validate_entity_type(type_) if type_ is not None else None
    workspace = get_workspace(ctx, read_only=True)
    with status_spinner(ctx, "Fetching schemas..."):
        schemas = workspace.lexicon_schemas(entity_type=validated_type)
    data = [
        {
            "entity_type": s.entity_type,
            "name": s.name,
            "property_count": len(s.schema_json.properties),
            "description": s.schema_json.description,
        }
        for s in schemas
    ]
    output_result(
        ctx,
        data,
        columns=["entity_type", "name", "property_count", "description"],
        format=format,
        jq_filter=jq_filter,
    )


@inspect_app.command("lexicon-schema")
@handle_errors
def inspect_lexicon_schema(
    ctx: typer.Context,
    type_: Annotated[
        str,
        typer.Option(
            "--type", "-t", help="Entity type: event, profile, custom_event, etc."
        ),
    ],
    name: Annotated[
        str,
        typer.Option("--name", "-n", help="Entity name."),
    ],
    format: FormatOption = "json",
    jq_filter: JqOption = None,
) -> None:
    """Get a single Lexicon schema from Mixpanel data dictionary.

    Retrieves the full schema definition for a specific event or profile
    property, including all property definitions and metadata.

    Output Structure (JSON):

        {
          "entity_type": "event",
          "name": "Purchase",
          "schema_json": {
            "description": "User completed a purchase",
            "properties": {
              "amount": {"type": "number", "description": "Purchase amount in USD"},
              "currency": {"type": "string", "description": "Currency code"},
              "product_id": {"type": "string", "description": "Product identifier"}
            },
            "metadata": {"hidden": false, "dropped": false, "tags": ["revenue"]}
          }
        }

    Examples:

        mp inspect lexicon-schema --type event --name "Purchase"
        mp inspect lexicon-schema -t event -n "Sign Up"
        mp inspect lexicon-schema -t profile -n "Plan Type" --format json

    **jq Examples:**

        --jq '.schema_json.properties | keys'                                                     # Get property names only
        --jq '.schema_json.properties | to_entries | [.[] | {name: .key, type: .value.type}]'    # Get property types
        --jq '.schema_json.description'                                                           # Get description
        --jq '.schema_json.metadata.hidden'                                                       # Check if schema is hidden
    """
    validated_type = validate_entity_type(type_)
    workspace = get_workspace(ctx, read_only=True)
    with status_spinner(ctx, "Fetching schema..."):
        schema = workspace.lexicon_schema(validated_type, name)
    output_result(ctx, schema.to_dict(), format=format, jq_filter=jq_filter)


@inspect_app.command("sample")
@handle_errors
def inspect_sample(
    ctx: typer.Context,
    table: Annotated[
        str,
        typer.Option("--table", "-t", help="Table name."),
    ],
    rows: Annotated[
        int,
        typer.Option("--rows", "-n", help="Number of rows to sample."),
    ] = 10,
    format: FormatOption = "json",
    jq_filter: JqOption = None,
) -> None:
    """Show random sample rows from a table.

    Uses reservoir sampling to return representative rows from throughout
    the table. Useful for quickly exploring data structure and values.

    Output Structure (JSON):

        [
          {
            "event_name": "Purchase",
            "event_time": "2024-01-15T10:30:00",
            "distinct_id": "user_123",
            "properties": {"amount": 99.99, "currency": "USD", "product": "Pro Plan"}
          },
          {
            "event_name": "Login",
            "event_time": "2024-01-15T09:15:00",
            "distinct_id": "user_456",
            "properties": {"browser": "Chrome", "platform": "web"}
          }
        ]

    Examples:

        mp inspect sample -t events
        mp inspect sample -t events -n 5 --format json

    **jq Examples:**

        --jq '[.[].event_name]'                                    # Get event names from sample
        --jq '[.[].distinct_id] | unique'                          # Get unique distinct_ids
        --jq '[.[].properties.country]'                            # Extract specific property
        --jq '[.[] | select(.event_name == "Purchase")]'           # Filter sample by event type
    """
    workspace = get_workspace(ctx, read_only=True)
    df = workspace.sample(table, n=rows)
    # Convert DataFrame to list of dicts for output
    data = df.to_dict(orient="records")
    output_result(ctx, data, format=format, jq_filter=jq_filter)


@inspect_app.command("summarize")
@handle_errors
def inspect_summarize(
    ctx: typer.Context,
    table: Annotated[
        str,
        typer.Option("--table", "-t", help="Table name."),
    ],
    format: FormatOption = "json",
    jq_filter: JqOption = None,
) -> None:
    """Show statistical summary of all columns in a table.

    Uses DuckDB's SUMMARIZE command to compute per-column statistics
    including min/max, quartiles, null percentage, and distinct counts.

    Output Structure (JSON):

        {
          "table": "events",
          "row_count": 125000,
          "columns": [
            {
              "column_name": "event_name",
              "column_type": "VARCHAR",
              "min": "Add to Cart",
              "max": "View Page",
              "approx_unique": 25,
              "avg": null,
              "std": null,
              "q25": null,
              "q50": null,
              "q75": null,
              "count": 125000,
              "null_percentage": 0.0
            }
          ]
        }

    Examples:

        mp inspect summarize -t events
        mp inspect summarize -t events --format json

    **jq Examples:**

        --jq '.columns | [.[].column_name]'                         # Get column names
        --jq '.columns | [.[] | select(.null_percentage > 0)]'     # Find columns with nulls
        --jq '.row_count'                                           # Get row count
        --jq '.columns | [.[] | select(.approx_unique > 1000)]'    # High-cardinality columns
    """
    workspace = get_workspace(ctx, read_only=True)
    result = workspace.summarize(table)
    output_result(ctx, result.to_dict(), format=format, jq_filter=jq_filter)


@inspect_app.command("breakdown")
@handle_errors
def inspect_breakdown(
    ctx: typer.Context,
    table: Annotated[
        str,
        typer.Option("--table", "-t", help="Table name."),
    ],
    format: FormatOption = "json",
    jq_filter: JqOption = None,
) -> None:
    """Show event distribution in a table.

    Analyzes event counts, unique users, date ranges, and percentages
    for each event type. Requires event_name, event_time, distinct_id columns.

    Output Structure (JSON):

        {
          "table": "events",
          "total_events": 125000,
          "total_users": 8500,
          "date_range": ["2024-01-01T00:00:00", "2024-01-31T23:59:59"],
          "events": [
            {
              "event_name": "Page View",
              "count": 75000,
              "unique_users": 8200,
              "first_seen": "2024-01-01T00:05:00",
              "last_seen": "2024-01-31T23:55:00",
              "pct_of_total": 60.0
            },
            {
              "event_name": "Purchase",
              "count": 5000,
              "unique_users": 2100,
              "first_seen": "2024-01-01T08:30:00",
              "last_seen": "2024-01-31T22:15:00",
              "pct_of_total": 4.0
            }
          ]
        }

    Examples:

        mp inspect breakdown -t events
        mp inspect breakdown -t events --format json

    **jq Examples:**

        --jq '.events | sort_by(.count) | reverse | [.[].event_name]'    # Event names sorted by count
        --jq '.events | [.[] | select(.pct_of_total > 10)]'              # Events with more than 10%
        --jq '.total_events'                                              # Get total event count
        --jq '.events | max_by(.unique_users)'                            # Event with most unique users
    """
    workspace = get_workspace(ctx, read_only=True)
    result = workspace.event_breakdown(table)
    output_result(ctx, result.to_dict(), format=format, jq_filter=jq_filter)


@inspect_app.command("keys")
@handle_errors
def inspect_keys(
    ctx: typer.Context,
    table: Annotated[
        str,
        typer.Option("--table", "-t", help="Table name."),
    ],
    event: Annotated[
        str | None,
        typer.Option("--event", "-e", help="Filter to specific event type."),
    ] = None,
    format: FormatOption = "json",
    jq_filter: JqOption = None,
) -> None:
    """List JSON property keys in a table.

    Extracts distinct keys from the 'properties' JSON column. Useful
    for discovering queryable fields in event properties.

    Output Structure (JSON):

        ["amount", "browser", "campaign", "country", "currency", "device", "platform"]

    Examples:

        mp inspect keys -t events
        mp inspect keys -t events -e "Purchase"
        mp inspect keys -t events --format table

    **jq Examples:**

        --jq '.[0:10]'                            # Get first 10 keys
        --jq 'length'                             # Count total property keys
        --jq '[.[] | select(contains("utm"))]'    # Find keys containing "utm"
        --jq 'sort'                               # Sort keys alphabetically
    """
    workspace = get_workspace(ctx, read_only=True)
    keys = workspace.property_keys(table, event=event)
    output_result(ctx, keys, format=format, jq_filter=jq_filter)


@inspect_app.command("column")
@handle_errors
def inspect_column(
    ctx: typer.Context,
    table: Annotated[
        str,
        typer.Option("--table", "-t", help="Table name."),
    ],
    column: Annotated[
        str,
        typer.Option("--column", "-c", help="Column name or expression."),
    ],
    top: Annotated[
        int,
        typer.Option("--top", help="Number of top values to show."),
    ] = 10,
    format: FormatOption = "json",
    jq_filter: JqOption = None,
) -> None:
    """Show detailed statistics for a single column.

    Performs deep analysis including null rates, cardinality, top values,
    and numeric statistics. Supports JSON path expressions like
    "properties->>'$.country'" for analyzing JSON columns.

    Output Structure (JSON):

        {
          "table": "events",
          "column": "properties->>'$.country'",
          "dtype": "VARCHAR",
          "count": 120000,
          "null_count": 5000,
          "null_pct": 4.0,
          "unique_count": 45,
          "unique_pct": 0.04,
          "top_values": [["US", 45000], ["UK", 22000], ["DE", 15000]],
          "min": null,
          "max": null,
          "mean": null,
          "std": null
        }

    Examples:

        mp inspect column -t events -c event_name
        mp inspect column -t events -c "properties->>'$.country'"
        mp inspect column -t events -c distinct_id --top 20

    **jq Examples:**

        --jq '.top_values'               # Get top values only
        --jq '.null_pct'                 # Get null percentage
        --jq '.unique_count'             # Get unique count
        --jq '.top_values | map(.[0])'   # Get top value names only
    """
    workspace = get_workspace(ctx, read_only=True)
    result = workspace.column_stats(table, column, top_n=top)
    output_result(ctx, result.to_dict(), format=format, jq_filter=jq_filter)


# =============================================================================
# JQL-BASED REMOTE DISCOVERY COMMANDS
# =============================================================================


@inspect_app.command("distribution")
@handle_errors
def inspect_distribution(
    ctx: typer.Context,
    event: Annotated[
        str,
        typer.Option("--event", "-e", help="Event name to analyze."),
    ],
    property: Annotated[
        str,
        typer.Option("--property", "-p", help="Property name to get distribution for."),
    ],
    from_date: Annotated[
        str,
        typer.Option("--from", help="Start date (YYYY-MM-DD)."),
    ],
    to_date: Annotated[
        str,
        typer.Option("--to", help="End date (YYYY-MM-DD)."),
    ],
    limit: Annotated[
        int,
        typer.Option("--limit", "-l", help="Maximum values to return."),
    ] = 20,
    format: FormatOption = "json",
    jq_filter: JqOption = None,
) -> None:
    """Show property value distribution from Mixpanel.

    Uses JQL to count occurrences of each value for a property, showing
    counts and percentages sorted by frequency. Useful for understanding
    what values a property contains before writing queries.

    Output Structure (JSON):

        {
          "event": "Purchase",
          "property_name": "country",
          "from_date": "2024-01-01",
          "to_date": "2024-01-31",
          "total_count": 50000,
          "values": [
            {"value": "US", "count": 25000, "percentage": 50.0},
            {"value": "UK", "count": 10000, "percentage": 20.0},
            {"value": "DE", "count": 7500, "percentage": 15.0}
          ]
        }

    Examples:

        mp inspect distribution -e Purchase -p country --from 2024-01-01 --to 2024-01-31
        mp inspect distribution -e Signup -p referrer --from 2024-01-01 --to 2024-01-31 --limit 10

    **jq Examples:**

        --jq '.values | [.[].value]'                          # Get values only
        --jq '.values | [.[] | select(.percentage > 10)]'     # Values with more than 10%
        --jq '.total_count'                                   # Get total count
        --jq '.values[0]'                                     # Get top value
    """
    workspace = get_workspace(ctx, read_only=True)
    with status_spinner(ctx, "Analyzing property distribution..."):
        result = workspace.property_distribution(
            event=event,
            property=property,
            from_date=from_date,
            to_date=to_date,
            limit=limit,
        )
    output_result(ctx, result.to_dict(), format=format, jq_filter=jq_filter)


@inspect_app.command("numeric")
@handle_errors
def inspect_numeric(
    ctx: typer.Context,
    event: Annotated[
        str,
        typer.Option("--event", "-e", help="Event name to analyze."),
    ],
    property: Annotated[
        str,
        typer.Option("--property", "-p", help="Numeric property name."),
    ],
    from_date: Annotated[
        str,
        typer.Option("--from", help="Start date (YYYY-MM-DD)."),
    ],
    to_date: Annotated[
        str,
        typer.Option("--to", help="End date (YYYY-MM-DD)."),
    ],
    percentiles: Annotated[
        str | None,
        typer.Option(
            "--percentiles", help="Comma-separated percentiles (e.g., 25,50,75,90)."
        ),
    ] = None,
    format: FormatOption = "json",
    jq_filter: JqOption = None,
) -> None:
    """Show numeric property statistics from Mixpanel.

    Uses JQL to compute min, max, avg, stddev, and percentiles for a
    numeric property. Useful for understanding value ranges and distributions.

    Output Structure (JSON):

        {
          "event": "Purchase",
          "property_name": "amount",
          "from_date": "2024-01-01",
          "to_date": "2024-01-31",
          "count": 5000,
          "min": 9.99,
          "max": 999.99,
          "sum": 125000.50,
          "avg": 25.00,
          "stddev": 45.75,
          "percentiles": {"25": 12.99, "50": 19.99, "75": 49.99, "90": 99.99}
        }

    Examples:

        mp inspect numeric -e Purchase -p amount --from 2024-01-01 --to 2024-01-31
        mp inspect numeric -e Purchase -p amount --from 2024-01-01 --to 2024-01-31 --percentiles 10,50,90

    **jq Examples:**

        --jq '.avg'               # Get average value
        --jq '.percentiles["50"]' # Get median (50th percentile)
        --jq '{min, max}'         # Get min and max
        --jq '.percentiles'       # Get all percentiles
    """
    # Parse percentiles if provided
    percentile_list: list[int] | None = None
    if percentiles:
        percentile_list = [int(p.strip()) for p in percentiles.split(",")]

    workspace = get_workspace(ctx, read_only=True)
    with status_spinner(ctx, "Computing numeric statistics..."):
        result = workspace.numeric_summary(
            event=event,
            property=property,
            from_date=from_date,
            to_date=to_date,
            percentiles=percentile_list,
        )
    output_result(ctx, result.to_dict(), format=format, jq_filter=jq_filter)


@inspect_app.command("daily")
@handle_errors
def inspect_daily(
    ctx: typer.Context,
    from_date: Annotated[
        str,
        typer.Option("--from", help="Start date (YYYY-MM-DD)."),
    ],
    to_date: Annotated[
        str,
        typer.Option("--to", help="End date (YYYY-MM-DD)."),
    ],
    events: Annotated[
        str | None,
        typer.Option(
            "--events", "-e", help="Comma-separated event names (or all if omitted)."
        ),
    ] = None,
    format: FormatOption = "json",
    jq_filter: JqOption = None,
) -> None:
    """Show daily event counts from Mixpanel.

    Uses JQL to count events by day. Optionally filter to specific events.
    Useful for understanding activity trends over time.

    Output Structure (JSON):

        {
          "from_date": "2024-01-01",
          "to_date": "2024-01-07",
          "events": ["Purchase", "Signup"],
          "counts": [
            {"date": "2024-01-01", "event": "Purchase", "count": 150},
            {"date": "2024-01-01", "event": "Signup", "count": 45},
            {"date": "2024-01-02", "event": "Purchase", "count": 175},
            {"date": "2024-01-02", "event": "Signup", "count": 52}
          ]
        }

    Examples:

        mp inspect daily --from 2024-01-01 --to 2024-01-07
        mp inspect daily --from 2024-01-01 --to 2024-01-07 -e Purchase,Signup

    **jq Examples:**

        --jq '.counts | [.[] | select(.event == "Purchase")] | map(.count) | add'              # Total for one event
        --jq '.counts | [.[] | select(.date == "2024-01-01")]'                                 # Counts for specific date
        --jq '.counts | [.[].date] | unique'                                                   # Get all dates
        --jq '.counts | group_by(.date) | [.[] | {date: .[0].date, total: map(.count) | add}]' # Daily totals
    """
    # Parse events if provided
    event_list: list[str] | None = None
    if events:
        event_list = [e.strip() for e in events.split(",")]

    workspace = get_workspace(ctx, read_only=True)
    with status_spinner(ctx, "Fetching daily counts..."):
        result = workspace.daily_counts(
            from_date=from_date,
            to_date=to_date,
            events=event_list,
        )
    output_result(ctx, result.to_dict(), format=format, jq_filter=jq_filter)


@inspect_app.command("engagement")
@handle_errors
def inspect_engagement(
    ctx: typer.Context,
    from_date: Annotated[
        str,
        typer.Option("--from", help="Start date (YYYY-MM-DD)."),
    ],
    to_date: Annotated[
        str,
        typer.Option("--to", help="End date (YYYY-MM-DD)."),
    ],
    events: Annotated[
        str | None,
        typer.Option(
            "--events", "-e", help="Comma-separated event names (or all if omitted)."
        ),
    ] = None,
    buckets: Annotated[
        str | None,
        typer.Option(
            "--buckets", help="Comma-separated bucket boundaries (e.g., 1,5,10,50)."
        ),
    ] = None,
    format: FormatOption = "json",
    jq_filter: JqOption = None,
) -> None:
    """Show user engagement distribution from Mixpanel.

    Uses JQL to bucket users by their event count, showing how many
    users performed N events. Useful for understanding user engagement levels.

    Output Structure (JSON):

        {
          "from_date": "2024-01-01",
          "to_date": "2024-01-31",
          "events": null,
          "total_users": 8500,
          "buckets": [
            {"bucket_min": 1, "bucket_label": "1", "user_count": 2500, "percentage": 29.4},
            {"bucket_min": 2, "bucket_label": "2-5", "user_count": 3200, "percentage": 37.6},
            {"bucket_min": 6, "bucket_label": "6-10", "user_count": 1800, "percentage": 21.2},
            {"bucket_min": 11, "bucket_label": "11+", "user_count": 1000, "percentage": 11.8}
          ]
        }

    Examples:

        mp inspect engagement --from 2024-01-01 --to 2024-01-31
        mp inspect engagement --from 2024-01-01 --to 2024-01-31 -e Purchase
        mp inspect engagement --from 2024-01-01 --to 2024-01-31 --buckets 1,5,10,50,100

    **jq Examples:**

        --jq '.total_users'                                               # Get total users
        --jq '.buckets | [.[] | select(.bucket_min >= 10)]'               # Power users (high engagement)
        --jq '.buckets | .[] | select(.bucket_min == 1) | .percentage'    # Single-event user percentage
        --jq '.buckets | [.[].bucket_label]'                              # Get bucket labels only
    """
    # Parse events if provided
    event_list: list[str] | None = None
    if events:
        event_list = [e.strip() for e in events.split(",")]

    # Parse buckets if provided
    bucket_list: list[int] | None = None
    if buckets:
        bucket_list = [int(b.strip()) for b in buckets.split(",")]

    workspace = get_workspace(ctx, read_only=True)
    with status_spinner(ctx, "Analyzing engagement distribution..."):
        result = workspace.engagement_distribution(
            from_date=from_date,
            to_date=to_date,
            events=event_list,
            buckets=bucket_list,
        )
    output_result(ctx, result.to_dict(), format=format, jq_filter=jq_filter)


@inspect_app.command("coverage")
@handle_errors
def inspect_coverage(
    ctx: typer.Context,
    event: Annotated[
        str,
        typer.Option("--event", "-e", help="Event name to analyze."),
    ],
    properties: Annotated[
        str,
        typer.Option(
            "--properties", "-p", help="Comma-separated property names to check."
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
    format: FormatOption = "json",
    jq_filter: JqOption = None,
) -> None:
    """Show property coverage statistics from Mixpanel.

    Uses JQL to count how often each property is defined (non-null) vs
    undefined. Useful for data quality assessment.

    Output Structure (JSON):

        {
          "event": "Purchase",
          "from_date": "2024-01-01",
          "to_date": "2024-01-31",
          "total_events": 5000,
          "coverage": [
            {"property": "amount", "defined_count": 5000, "null_count": 0, "coverage_percentage": 100.0},
            {"property": "coupon_code", "defined_count": 1250, "null_count": 3750, "coverage_percentage": 25.0},
            {"property": "referrer", "defined_count": 4500, "null_count": 500, "coverage_percentage": 90.0}
          ]
        }

    Examples:

        mp inspect coverage -e Purchase -p coupon_code,referrer --from 2024-01-01 --to 2024-01-31

    **jq Examples:**

        --jq '.coverage | [.[] | select(.coverage_percentage < 50)]'     # Properties with low coverage
        --jq '.coverage | [.[] | select(.coverage_percentage == 100)]'   # Fully covered properties
        --jq '.coverage | [.[].property]'                                # Get property names only
        --jq '.coverage | sort_by(.coverage_percentage)'                 # Sort by coverage percentage
    """
    # Parse properties
    property_list = [p.strip() for p in properties.split(",")]

    workspace = get_workspace(ctx, read_only=True)
    with status_spinner(ctx, "Analyzing property coverage..."):
        result = workspace.property_coverage(
            event=event,
            properties=property_list,
            from_date=from_date,
            to_date=to_date,
        )
    output_result(ctx, result.to_dict(), format=format, jq_filter=jq_filter)
