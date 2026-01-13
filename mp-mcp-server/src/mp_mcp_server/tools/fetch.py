"""Data fetching tools for downloading Mixpanel data to local storage.

This module provides MCP tools for fetching events and profiles from
Mixpanel and storing them in the local DuckDB database for SQL analysis.

Example:
    Ask Claude: "Fetch events from January 1-7"
    Claude uses: fetch_events(from_date="2024-01-01", to_date="2024-01-07")
"""

from typing import Any

from fastmcp import Context

from mp_mcp_server.context import get_workspace
from mp_mcp_server.errors import handle_errors
from mp_mcp_server.server import mcp


@mcp.tool
@handle_errors
def fetch_events(
    ctx: Context,
    from_date: str,
    to_date: str,
    table: str | None = None,
    events: list[str] | None = None,
    where: str | None = None,
    limit: int | None = None,
    append: bool = False,
    parallel: bool = False,
    workers: int = 4,
) -> dict[str, Any]:
    """Fetch events from Mixpanel and store in local database.

    Downloads raw event data for the specified date range and stores
    it in a DuckDB table for local SQL analysis.

    Args:
        ctx: FastMCP context with workspace access.
        from_date: Start date (YYYY-MM-DD format).
        to_date: End date (YYYY-MM-DD format).
        table: Optional table name (auto-generated if not provided).
        events: Optional list of event names to filter by.
        where: Optional filter expression (e.g., 'properties["country"] == "US"').
        limit: Optional maximum number of events to fetch.
        append: Append to existing table instead of creating new one.
        parallel: Use parallel fetching for large date ranges.
        workers: Number of parallel workers (if parallel=True).

    Returns:
        Dictionary with table_name and row_count.

    Example:
        Ask: "Download last week's login events"
        Uses: fetch_events(from_date="2024-01-01", to_date="2024-01-07",
                          events=["login"])
    """
    ws = get_workspace(ctx)

    kwargs: dict[str, Any] = {
        "from_date": from_date,
        "to_date": to_date,
    }

    if table:
        kwargs["name"] = table
    if events:
        kwargs["events"] = events
    if where:
        kwargs["where"] = where
    if limit is not None:
        kwargs["limit"] = limit
    if append:
        kwargs["append"] = append
    if parallel:
        kwargs["parallel"] = parallel
        kwargs["max_workers"] = workers

    result = ws.fetch_events(**kwargs)
    return result.to_dict()


@mcp.tool
@handle_errors
def fetch_profiles(
    ctx: Context,
    table: str | None = None,
    where: str | None = None,
    cohort_id: str | None = None,
    output_properties: list[str] | None = None,
    distinct_id: str | None = None,
    distinct_ids: list[str] | None = None,
    group_id: str | None = None,
    append: bool = False,
    parallel: bool = False,
    workers: int = 4,
) -> dict[str, Any]:
    """Fetch user profiles from Mixpanel and store in local database.

    Downloads user profile data and stores it in a DuckDB table
    for local SQL analysis.

    Args:
        ctx: FastMCP context with workspace access.
        table: Optional table name (default: "profiles").
        where: Optional filter expression.
        cohort_id: Optional cohort ID to filter profiles by.
        output_properties: Optional list of properties to include in output.
        distinct_id: Optional single user ID to fetch.
        distinct_ids: Optional list of user IDs to fetch.
        group_id: Optional group ID for group profiles.
        append: Append to existing table instead of creating new one.
        parallel: Use parallel fetching.
        workers: Number of parallel workers.

    Returns:
        Dictionary with table_name and row_count.

    Example:
        Ask: "Download profiles from the 'Active Users' cohort"
        Uses: fetch_profiles(cohort_id="12345")
    """
    ws = get_workspace(ctx)

    kwargs: dict[str, Any] = {}

    if table:
        kwargs["name"] = table
    if where:
        kwargs["where"] = where
    if cohort_id:
        kwargs["cohort_id"] = cohort_id
    if output_properties:
        kwargs["output_properties"] = output_properties
    if distinct_id:
        kwargs["distinct_id"] = distinct_id
    if distinct_ids:
        kwargs["distinct_ids"] = distinct_ids
    if group_id:
        kwargs["group_id"] = group_id
    if append:
        kwargs["append"] = append
    if parallel:
        kwargs["parallel"] = parallel
        kwargs["max_workers"] = workers

    result = ws.fetch_profiles(**kwargs)
    return result.to_dict()


@mcp.tool
@handle_errors
def stream_events(
    ctx: Context,
    from_date: str,
    to_date: str,
    events: list[str] | None = None,
    where: str | None = None,
    limit: int = 1000,
) -> list[dict[str, Any]]:
    """Stream events directly without storing them.

    Returns events as a list without persisting to the database.
    Useful for quick exploration or when you don't need to keep the data.

    Args:
        ctx: FastMCP context with workspace access.
        from_date: Start date (YYYY-MM-DD format).
        to_date: End date (YYYY-MM-DD format).
        events: Optional list of event names to filter by.
        where: Optional filter expression (e.g., 'properties["country"] == "US"').
        limit: Maximum events to return.

    Returns:
        List of event dictionaries.

    Example:
        Ask: "Show me some recent login events"
        Uses: stream_events(from_date="2024-01-01", to_date="2024-01-07",
                           events=["login"])
    """
    ws = get_workspace(ctx)

    kwargs: dict[str, Any] = {
        "from_date": from_date,
        "to_date": to_date,
    }

    if events:
        kwargs["events"] = events
    if where:
        kwargs["where"] = where

    events_list = []
    for e in ws.stream_events(**kwargs):
        events_list.append(e)
        if len(events_list) >= limit:
            break

    return events_list


@mcp.tool
@handle_errors
def stream_profiles(
    ctx: Context,
    where: str | None = None,
    cohort_id: str | None = None,
    output_properties: list[str] | None = None,
    distinct_id: str | None = None,
    distinct_ids: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Stream profiles directly without storing them.

    Returns profiles as a list without persisting to the database.

    Note: The Mixpanel Engage API does not support a limit parameter.
    Use distinct_id, distinct_ids, cohort_id, or where filters to
    control the scope of profiles returned.

    Args:
        ctx: FastMCP context with workspace access.
        where: Optional filter expression.
        cohort_id: Optional cohort ID to filter profiles by.
        output_properties: Optional list of properties to include in output.
        distinct_id: Optional single user ID to fetch.
        distinct_ids: Optional list of user IDs to fetch.

    Returns:
        List of profile dictionaries.

    Example:
        Ask: "Show me profiles from the 'Active Users' cohort"
        Uses: stream_profiles(cohort_id="12345")
    """
    ws = get_workspace(ctx)

    kwargs: dict[str, Any] = {}
    if where:
        kwargs["where"] = where
    if cohort_id:
        kwargs["cohort_id"] = cohort_id
    if output_properties:
        kwargs["output_properties"] = output_properties
    if distinct_id:
        kwargs["distinct_id"] = distinct_id
    if distinct_ids:
        kwargs["distinct_ids"] = distinct_ids

    return list(ws.stream_profiles(**kwargs))
