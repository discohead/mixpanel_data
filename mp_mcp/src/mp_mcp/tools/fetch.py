"""Data fetching tools for downloading Mixpanel data to local storage.

This module provides MCP tools for fetching events and profiles from
Mixpanel and storing them in the local DuckDB database for SQL analysis.

Task-enabled versions support progress reporting and cancellation.

Example:
    Ask Claude: "Fetch events from January 1-7"
    Claude uses: fetch_events(from_date="2024-01-01", to_date="2024-01-07")
"""

import asyncio
from datetime import datetime, timedelta
from typing import Any

from fastmcp import Context

from mp_mcp.context import get_workspace
from mp_mcp.errors import handle_errors
from mp_mcp.server import mcp


def _calculate_date_range(from_date: str, to_date: str) -> list[str]:
    """Calculate list of dates in the range.

    Args:
        from_date: Start date (YYYY-MM-DD).
        to_date: End date (YYYY-MM-DD).

    Returns:
        List of date strings in the range.
    """
    from_dt = datetime.fromisoformat(from_date)
    to_dt = datetime.fromisoformat(to_date)

    dates: list[str] = []
    current = from_dt
    while current <= to_dt:
        dates.append(current.isoformat()[:10])
        current += timedelta(days=1)

    return dates


@mcp.tool(task=True)
@handle_errors
async def fetch_events(
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

    Supports progress reporting and cancellation for long-running operations.
    When cancelled, returns partial results for any completed days.

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
        progress: Progress reporter for task tracking.

    Returns:
        Dictionary with table_name, row_count, and status.

    Example:
        Ask: "Download last week's login events"
        Uses: fetch_events(from_date="2024-01-01", to_date="2024-01-07",
                          events=["login"])
    """
    ws = get_workspace(ctx)

    # Calculate date range for progress reporting
    days = _calculate_date_range(from_date, to_date)

    # For short ranges (1-3 days) or if parallel is requested, use single fetch
    if len(days) <= 3 or parallel:
        # Single fetch - no day-by-day progress
        await ctx.report_progress(0, 1, "Fetching events...")

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
        await ctx.report_progress(1, 1, "Complete")

        result_dict = result.to_dict()
        result_dict["status"] = "completed"
        return result_dict

    # For longer ranges, fetch day by day with progress
    total_days = len(days)
    total_rows = 0
    completed_days = 0
    result_table = table

    try:
        for i, day in enumerate(days):
            await ctx.report_progress(
                i, total_days, f"Fetching {day} ({i + 1}/{total_days})"
            )

            day_kwargs: dict[str, Any] = {
                "from_date": day,
                "to_date": day,
            }

            if result_table:
                day_kwargs["name"] = result_table
            if events:
                day_kwargs["events"] = events
            if where:
                day_kwargs["where"] = where
            if limit is not None:
                # Distribute limit across days
                remaining_limit = limit - total_rows
                if remaining_limit <= 0:
                    break
                day_kwargs["limit"] = remaining_limit

            # Append after first day
            if i > 0 or append:
                day_kwargs["append"] = True

            result = ws.fetch_events(**day_kwargs)
            result_dict = result.to_dict()

            # Capture table name from first result
            if result_table is None:
                result_table = result_dict.get("table_name")

            total_rows += result_dict.get("row_count", 0)
            completed_days += 1

            await ctx.report_progress(i + 1, total_days)

        return {
            "status": "completed",
            "table_name": result_table,
            "row_count": total_rows,
            "days_fetched": completed_days,
        }

    except asyncio.CancelledError:
        # Return partial results
        return {
            "status": "cancelled",
            "table_name": result_table,
            "row_count": total_rows,
            "days_fetched": completed_days,
            "message": f"Cancelled after {completed_days}/{len(days)} days",
        }


@mcp.tool(task=True)
@handle_errors
async def fetch_profiles(
    ctx: Context,
    table: str | None = None,
    where: str | None = None,
    cohort_id: str | None = None,
    output_properties: list[str] | None = None,
    distinct_id: str | None = None,
    distinct_ids: list[str] | None = None,
    group_id: str | None = None,
    behaviors: list[dict[str, Any]] | None = None,
    as_of_timestamp: int | None = None,
    include_all_users: bool = False,
    append: bool = False,
    parallel: bool = False,
    workers: int = 4,
) -> dict[str, Any]:
    """Fetch user profiles from Mixpanel and store in local database.

    Downloads user profile data and stores it in a DuckDB table
    for local SQL analysis.

    Supports progress reporting and cancellation for long-running operations.
    When cancelled, returns partial results.

    Args:
        ctx: FastMCP context with workspace access.
        table: Optional table name (default: "profiles").
        where: Optional filter expression.
        cohort_id: Optional cohort ID to filter profiles by.
        output_properties: Optional list of properties to include in output.
        distinct_id: Optional single user ID to fetch.
        distinct_ids: Optional list of user IDs to fetch.
        group_id: Optional group ID for group profiles.
        behaviors: Optional list of behavioral filter conditions.
        as_of_timestamp: Optional Unix timestamp for point-in-time profile state.
        include_all_users: Include all users with cohort membership markers.
        append: Append to existing table instead of creating new one.
        parallel: Use parallel fetching.
        workers: Number of parallel workers.

    Returns:
        Dictionary with table_name, row_count, and status.

    Example:
        Ask: "Download profiles from the 'Active Users' cohort"
        Uses: fetch_profiles(cohort_id="12345")
    """
    ws = get_workspace(ctx)

    # Estimate pages based on query type
    if distinct_id:
        # Single profile - one page
        estimated_pages = 1
    elif distinct_ids:
        # Multiple specific IDs - estimate based on batch size
        estimated_pages = max(1, len(distinct_ids) // 100)
    else:
        # Unknown size - estimate 10 pages (1000 profiles typical page size)
        estimated_pages = 10

    await ctx.report_progress(0, estimated_pages, "Fetching profiles...")

    total_profiles = 0
    pages_fetched = 0
    result_table = table or "profiles"

    try:
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
        if behaviors:
            kwargs["behaviors"] = behaviors
        if as_of_timestamp is not None:
            kwargs["as_of_timestamp"] = as_of_timestamp
        if include_all_users:
            kwargs["include_all_users"] = include_all_users
        if append:
            kwargs["append"] = append
        if parallel:
            kwargs["parallel"] = parallel
            kwargs["max_workers"] = workers

        # The underlying workspace method handles pagination internally
        # We update progress based on estimated pages
        result = ws.fetch_profiles(**kwargs)
        result_dict = result.to_dict()

        total_profiles = result_dict.get("row_count", 0)
        result_table = result_dict.get("table_name", result_table)

        # Update progress to completion
        pages_fetched = max(1, total_profiles // 1000)
        await ctx.report_progress(pages_fetched, pages_fetched, "Complete")

        return {
            "status": "completed",
            "table_name": result_table,
            "row_count": total_profiles,
            "pages_fetched": pages_fetched,
        }

    except asyncio.CancelledError:
        # Return partial results
        return {
            "status": "cancelled",
            "table_name": result_table,
            "row_count": total_profiles,
            "pages_fetched": pages_fetched,
            "message": "Fetch cancelled by user",
        }


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
        "limit": limit,
        "raw": True,  # Use raw format for JSON serialization
    }

    if events:
        kwargs["events"] = events
    if where:
        kwargs["where"] = where

    return list(ws.stream_events(**kwargs))


@mcp.tool
@handle_errors
def stream_profiles(
    ctx: Context,
    where: str | None = None,
    cohort_id: str | None = None,
    output_properties: list[str] | None = None,
    distinct_id: str | None = None,
    distinct_ids: list[str] | None = None,
    group_id: str | None = None,
    behaviors: list[dict[str, Any]] | None = None,
    as_of_timestamp: int | None = None,
    include_all_users: bool = False,
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
        group_id: Optional group ID for group profiles.
        behaviors: Optional list of behavioral filter conditions.
        as_of_timestamp: Optional Unix timestamp for point-in-time profile state.
        include_all_users: Include all users with cohort membership markers.

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
    if group_id:
        kwargs["group_id"] = group_id
    if behaviors:
        kwargs["behaviors"] = behaviors
    if as_of_timestamp is not None:
        kwargs["as_of_timestamp"] = as_of_timestamp
    if include_all_users:
        kwargs["include_all_users"] = include_all_users

    return list(ws.stream_profiles(**kwargs))
