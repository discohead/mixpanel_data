"""Live analytics query tools for real-time Mixpanel analysis.

This module provides MCP tools for executing live queries against Mixpanel,
including segmentation, funnel, retention, and JQL queries.

Example:
    Ask Claude: "How many logins happened each day last month?"
    Claude uses: segmentation(event="login", from_date="2024-01-01", ...)
"""

from typing import Any, Literal

from fastmcp import Context

from mp_mcp.context import get_workspace
from mp_mcp.errors import handle_errors
from mp_mcp.server import mcp

# Type aliases for parameters
UnitType = Literal["day", "week", "month"]
CountType = Literal["general", "unique", "average"]
AddictionUnitType = Literal["hour", "day"]


@mcp.tool
@handle_errors
def segmentation(
    ctx: Context,
    event: str,
    from_date: str,
    to_date: str,
    segment_property: str | None = None,
    unit: UnitType = "day",
    where: str | None = None,
) -> dict[str, Any]:
    """Run a segmentation query to analyze event trends over time.

    Returns time series data showing event counts, optionally segmented
    by a property value.

    Args:
        ctx: FastMCP context with workspace access.
        event: Event name to analyze.
        from_date: Start date (YYYY-MM-DD format).
        to_date: End date (YYYY-MM-DD format).
        segment_property: Optional property to segment by.
        unit: Time unit for aggregation (day, week, month).
        where: Optional filter expression (e.g., 'properties["country"] == "US"').

    Returns:
        Dictionary with time series data.

    Example:
        Ask: "How many logins per day last week from mobile?"
        Uses: segmentation(event="login", from_date="2024-01-01", to_date="2024-01-07",
                          where='properties["platform"] == "mobile"')
    """
    ws = get_workspace(ctx)
    result = ws.segmentation(
        event=event,
        from_date=from_date,
        to_date=to_date,
        on=segment_property,
        unit=unit,
        where=where,
    )
    return result.to_dict()


@mcp.tool
@handle_errors
def funnel(
    ctx: Context,
    funnel_id: int,
    from_date: str,
    to_date: str,
    unit: UnitType = "day",
    on: str | None = None,
) -> dict[str, Any]:
    """Analyze conversion through a saved funnel.

    Returns step-by-step conversion data for a saved funnel definition.

    Args:
        ctx: FastMCP context with workspace access.
        funnel_id: ID of the saved funnel to analyze.
        from_date: Start date (YYYY-MM-DD format).
        to_date: End date (YYYY-MM-DD format).
        unit: Time unit for cohort grouping.
        on: Optional property to segment funnel by. Must use property accessor
            format (e.g., 'properties["country"]') - bare names not yet supported.

    Returns:
        Dictionary with funnel conversion data.

    Example:
        Ask: "What's my signup funnel conversion this month by country?"
        Uses: funnel(funnel_id=1, from_date="2024-01-01",
                    to_date="2024-01-31", on='properties["country"]')
    """
    ws = get_workspace(ctx)
    result = ws.funnel(
        funnel_id=funnel_id,
        from_date=from_date,
        to_date=to_date,
        unit=unit,
        on=on,
    )
    return result.to_dict()


@mcp.tool
@handle_errors
def retention(
    ctx: Context,
    born_event: str,
    from_date: str,
    to_date: str,
    return_event: str | None = None,
    born_where: str | None = None,
    return_where: str | None = None,
    interval: int = 1,
    interval_count: int = 7,
    unit: UnitType = "day",
) -> dict[str, Any]:
    """Analyze user retention over time.

    Returns cohort retention curves showing how users return after
    their initial action.

    Args:
        ctx: FastMCP context with workspace access.
        born_event: Event that defines cohort entry.
        from_date: Start date (YYYY-MM-DD format).
        to_date: End date (YYYY-MM-DD format).
        return_event: Event to measure return (defaults to born_event).
        born_where: Optional filter for born event
            (e.g., 'properties["source"] == "mobile"').
        return_where: Optional filter for return event.
        interval: Length of each retention interval (default: 1).
        interval_count: Number of retention intervals to analyze.
        unit: Time unit for intervals (day, week, month).

    Returns:
        Dictionary with retention cohort data.

    Example:
        Ask: "What's day-7 retention for new signups from mobile?"
        Uses: retention(born_event="signup", from_date="2024-01-01", ...,
                       born_where='properties["platform"] == "mobile"')
    """
    ws = get_workspace(ctx)
    # return_event defaults to born_event if not specified
    actual_return_event = return_event if return_event else born_event
    result = ws.retention(
        born_event=born_event,
        from_date=from_date,
        to_date=to_date,
        return_event=actual_return_event,
        born_where=born_where,
        return_where=return_where,
        interval=interval,
        interval_count=interval_count,
        unit=unit,
    )
    return result.to_dict()


@mcp.tool
@handle_errors
def jql(
    ctx: Context,
    script: str,
    params: dict[str, Any] | None = None,
) -> list[Any]:
    """Execute a JQL (JavaScript Query Language) script.

    JQL allows complex event transformations and aggregations
    beyond what standard queries support.

    Args:
        ctx: FastMCP context with workspace access.
        script: JQL script to execute.
        params: Optional parameters to pass to the script.

    Returns:
        List of result dictionaries from the JQL execution.

    Example:
        Ask: "Run this custom JQL script with parameters"
        Uses: jql(script="function main() { ... }", params={"from_date": "2024-01-01"})
    """
    ws = get_workspace(ctx)
    result = ws.jql(script=script, params=params)
    return result.raw


@mcp.tool
@handle_errors
def event_counts(
    ctx: Context,
    events: list[str],
    from_date: str,
    to_date: str,
    unit: UnitType = "day",
    type: CountType = "general",
) -> dict[str, Any]:
    """Get counts for multiple events in a single query.

    Efficient way to compare multiple events over the same time period.

    Args:
        ctx: FastMCP context with workspace access.
        events: List of event names to count.
        from_date: Start date (YYYY-MM-DD format).
        to_date: End date (YYYY-MM-DD format).
        unit: Time unit for aggregation.
        type: Count type - general (total), unique (unique users), or average.

    Returns:
        Dictionary with counts for each event.

    Example:
        Ask: "Compare unique login and signup users this month"
        Uses: event_counts(events=["login", "signup"], ..., type="unique")
    """
    ws = get_workspace(ctx)
    result = ws.event_counts(
        events=events,
        from_date=from_date,
        to_date=to_date,
        unit=unit,
        type=type,
    )
    return result.to_dict()


@mcp.tool
@handle_errors
def property_counts(
    ctx: Context,
    event: str,
    property_name: str,
    from_date: str,
    to_date: str,
    type: CountType = "general",
    unit: UnitType = "day",
    values: list[str] | None = None,
    limit: int | None = None,
) -> dict[str, Any]:
    """Get event counts broken down by property value.

    Shows distribution of property values for an event.

    Args:
        ctx: FastMCP context with workspace access.
        event: Event name to analyze.
        property_name: Property to break down by.
        from_date: Start date (YYYY-MM-DD format).
        to_date: End date (YYYY-MM-DD format).
        type: Count type - general (total), unique (unique users), or average.
        unit: Time unit for aggregation (day, week, month).
        values: Optional list of specific property values to include.
        limit: Optional maximum number of property values to return.

    Returns:
        Dictionary with counts per property value.

    Example:
        Ask: "What are the top 5 browsers users log in with?"
        Uses: property_counts(event="login", property_name="browser", ..., limit=5)
    """
    ws = get_workspace(ctx)
    result = ws.property_counts(
        event=event,
        property_name=property_name,
        from_date=from_date,
        to_date=to_date,
        type=type,
        unit=unit,
        values=values,
        limit=limit,
    )
    return result.to_dict()


@mcp.tool
@handle_errors
def activity_feed(
    ctx: Context,
    distinct_id: str,
    from_date: str | None = None,
    to_date: str | None = None,
    limit: int = 100,
) -> dict[str, Any]:
    """Get activity feed for a specific user.

    Returns chronological event history for a user using the
    Activity Stream API. Results are limited to prevent overwhelming
    output for users with long event histories.

    Args:
        ctx: FastMCP context with workspace access.
        distinct_id: User identifier to look up.
        from_date: Optional start date (YYYY-MM-DD).
        to_date: Optional end date (YYYY-MM-DD).
        limit: Maximum number of events to return (default 100).
            Use higher values for longer histories.
            Set to 0 for unlimited results.

    Returns:
        Dictionary with user events (limited to specified count).

    Example:
        Ask: "What has user alice done recently?"
        Uses: activity_feed(distinct_id="alice")

        Ask: "Show me the last 500 events for user bob"
        Uses: activity_feed(distinct_id="bob", limit=500)
    """
    ws = get_workspace(ctx)
    result = ws.activity_feed(
        distinct_ids=[distinct_id],
        from_date=from_date,
        to_date=to_date,
    )

    # Limit events to prevent overwhelming context windows
    output = result.to_dict()
    if "events" in output:
        total_event_count = len(result.events)
        if limit > 0 and total_event_count > limit:
            output["events"] = output["events"][:limit]
            output["truncated"] = True
        else:
            output["truncated"] = False
        output["total_events"] = total_event_count
    else:
        output["truncated"] = False
        output["total_events"] = 0

    return output


@mcp.tool
@handle_errors
def frequency(
    ctx: Context,
    from_date: str,
    to_date: str,
    event: str | None = None,
    unit: UnitType = "day",
    addiction_unit: AddictionUnitType = "hour",
    where: str | None = None,
) -> dict[str, Any]:
    """Analyze how often users perform events (addiction analysis).

    Returns frequency distribution showing how many users performed
    events in N time periods.

    Args:
        ctx: FastMCP context with workspace access.
        from_date: Start date (YYYY-MM-DD format).
        to_date: End date (YYYY-MM-DD format).
        event: Optional event name to filter (None = all events).
        unit: Time unit for aggregation (day, week, month).
        addiction_unit: Time unit for measuring frequency (hour or day).
        where: Optional filter expression (e.g., 'properties["country"] == "US"').

    Returns:
        Dictionary with frequency distribution data.

    Example:
        Ask: "How many times do mobile users typically log in?"
        Uses: frequency(from_date="2024-01-01", to_date="2024-01-07", event="login",
                       where='properties["platform"] == "mobile"')
    """
    ws = get_workspace(ctx)
    result = ws.frequency(
        from_date=from_date,
        to_date=to_date,
        unit=unit,
        addiction_unit=addiction_unit,
        event=event,
        where=where,
    )
    return result.to_dict()
