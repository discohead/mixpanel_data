"""Safe large fetch tool with confirmation.

This module provides the safe_large_fetch tool that estimates
data volume before fetching and requests user confirmation
for large operations.

Uses ctx.elicit() for user confirmation with graceful degradation
when elicitation is unavailable.

Example:
    Ask Claude: "Fetch all events from the last 90 days"
    Claude uses: safe_large_fetch(from_date="2025-10-15", to_date="2026-01-13")
    Claude prompts: "This will fetch ~1M events. Proceed?"
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from fastmcp import Context
from fastmcp.server.elicitation import (
    AcceptedElicitation,
    CancelledElicitation,
    DeclinedElicitation,
)

from mp_mcp_server.context import get_workspace
from mp_mcp_server.errors import handle_errors
from mp_mcp_server.server import mcp

# Default threshold for requiring confirmation (100k events)
CONFIRMATION_THRESHOLD = 100_000


@dataclass
class FetchConfirmation:
    """User confirmation for large fetch operation.

    Attributes:
        proceed: Whether to proceed with the fetch.
        reduce_scope: Whether to reduce the scope.
        new_limit: New event limit if reducing scope.
    """

    proceed: bool
    """Whether to proceed with the fetch."""

    reduce_scope: bool = False
    """Whether to reduce the scope."""

    new_limit: int | None = None
    """New event limit if reducing scope."""


def _get_default_date_range(days_back: int = 30) -> tuple[str, str]:
    """Get default date range for fetch.

    Args:
        days_back: Number of days to look back.

    Returns:
        Tuple of (from_date, to_date) as strings.
    """
    today = datetime.now().date()
    from_date = (today - timedelta(days=days_back)).isoformat()
    to_date = today.isoformat()
    return from_date, to_date


def estimate_event_count(
    ctx: Context,
    from_date: str,
    to_date: str,
    events: list[str] | None = None,
) -> dict[str, Any]:
    """Estimate event count for the specified date range.

    Uses top_events or historical data to estimate the volume
    of events that will be fetched.

    Args:
        ctx: FastMCP context with workspace access.
        from_date: Start date for fetch.
        to_date: End date for fetch.
        events: Optional list of specific events to estimate.

    Returns:
        Dictionary with estimation details:
        - estimated_count: Estimated number of events
        - days_in_range: Number of days in the date range
        - avg_per_day: Average events per day estimate
        - confidence: Confidence level of estimate (low/medium/high)
    """
    ws = get_workspace(ctx)

    # Calculate days in range
    from_dt = datetime.fromisoformat(from_date)
    to_dt = datetime.fromisoformat(to_date)
    days_in_range = (to_dt - from_dt).days + 1

    try:
        # Get top events to estimate volume
        top_events_result = ws.top_events(limit=50)

        if hasattr(top_events_result, "to_dict"):
            top_events_data = top_events_result.to_dict()
        else:
            top_events_data = top_events_result

        # Sum up event counts
        total_daily_avg = 0.0
        events_counted = 0

        if isinstance(top_events_data, dict):
            # Try different response formats
            if "data" in top_events_data:
                data = top_events_data["data"]
                if isinstance(data, dict):
                    for event_name, count in data.items():
                        if events is None or event_name in events:
                            # Count is typically from last period
                            total_daily_avg += float(count)
                            events_counted += 1
            elif "events" in top_events_data:
                for event in top_events_data["events"]:
                    event_name = event.get("name", "")
                    count = event.get("count", 0)
                    if events is None or event_name in events:
                        total_daily_avg += float(count)
                        events_counted += 1
        elif isinstance(top_events_data, list):
            for event in top_events_data:
                if isinstance(event, dict):
                    event_name = event.get("event", event.get("name", ""))
                    count = event.get("count", event.get("total", 0))
                    if events is None or event_name in events:
                        total_daily_avg += float(count) if count is not None else 0.0
                        events_counted += 1

        # Estimate: if top_events returns 30-day totals, divide by 30
        avg_per_day = total_daily_avg / 30 if total_daily_avg > 0 else 1000

        # Apply date range
        estimated_count = int(avg_per_day * days_in_range)

        # Confidence based on data quality
        confidence = "medium"
        if events_counted > 10:
            confidence = "high"
        elif events_counted == 0:
            confidence = "low"
            estimated_count = days_in_range * 10000  # Default estimate

        return {
            "estimated_count": estimated_count,
            "days_in_range": days_in_range,
            "avg_per_day": int(avg_per_day),
            "confidence": confidence,
            "events_analyzed": events_counted,
        }

    except Exception as e:
        # Fallback estimate based on date range
        # Assume 10k events per day as conservative estimate
        estimated_count = days_in_range * 10000

        return {
            "estimated_count": estimated_count,
            "days_in_range": days_in_range,
            "avg_per_day": 10000,
            "confidence": "low",
            "error": str(e),
        }


@mcp.tool
@handle_errors
async def safe_large_fetch(
    ctx: Context,
    from_date: str | None = None,
    to_date: str | None = None,
    events: list[str] | None = None,
    table: str | None = None,
    confirmation_threshold: int = CONFIRMATION_THRESHOLD,
) -> dict[str, Any]:
    """Safely fetch events with confirmation for large operations.

    Estimates the data volume before fetching and requests user
    confirmation if the estimated count exceeds the threshold.

    Uses ctx.elicit() for user confirmation when available; falls back
    to proceeding with a warning when elicitation is unavailable.

    Args:
        ctx: FastMCP context with workspace access.
        from_date: Start date for fetch (YYYY-MM-DD).
            Defaults to 30 days ago.
        to_date: End date for fetch (YYYY-MM-DD).
            Defaults to today.
        events: Optional list of specific events to fetch.
        table: Optional table name for storing results.
        confirmation_threshold: Number of events above which to
            require confirmation (default: 100,000).

    Returns:
        Dictionary containing:
        - status: "completed", "cancelled", "declined", or "warning"
        - estimated_count: Estimated event count
        - actual_count: Actual event count (if completed)
        - table_name: Name of the table created (if completed)
        - message: Status message

    Example:
        Ask: "Fetch all events from the last 90 days"
        Uses: safe_large_fetch(from_date="2025-10-15", to_date="2026-01-13")

        Ask: "Safely download signup events"
        Uses: safe_large_fetch(events=["signup"])
    """
    # Set default date range
    if not from_date or not to_date:
        from_date, to_date = _get_default_date_range()

    # Step 1: Estimate event count
    estimation = estimate_event_count(ctx, from_date, to_date, events)
    estimated_count = estimation["estimated_count"]
    confidence = estimation["confidence"]

    # Step 2: Check if confirmation is needed
    if estimated_count >= confirmation_threshold:
        # Build confirmation message
        events_desc = ", ".join(events) if events else "all events"
        confidence_note = f" (confidence: {confidence})" if confidence != "high" else ""

        confirmation_message = (
            f"This will fetch approximately {estimated_count:,} {events_desc} "
            f"from {from_date} to {to_date}{confidence_note}. "
            f"This may take several minutes. Proceed?"
        )

        # Try elicitation
        try:
            elicit_result = await ctx.elicit(
                confirmation_message,
                response_type=FetchConfirmation,  # type: ignore[arg-type]
            )

            match elicit_result:
                case AcceptedElicitation(data=confirm_data):
                    # Convert dict to FetchConfirmation fields
                    if isinstance(confirm_data, dict):
                        proceed = confirm_data.get("proceed", True)
                        reduce_scope = confirm_data.get("reduce_scope", False)
                        new_limit_val = confirm_data.get("new_limit")
                    else:
                        proceed = True
                        reduce_scope = False
                        new_limit_val = None

                    if not proceed:
                        return {
                            "status": "declined",
                            "estimated_count": estimated_count,
                            "message": "User chose not to proceed with fetch.",
                        }

                    # Check if scope should be reduced
                    limit = None
                    if reduce_scope and new_limit_val:
                        limit = int(new_limit_val)

                case DeclinedElicitation():
                    return {
                        "status": "declined",
                        "estimated_count": estimated_count,
                        "message": "User declined the fetch operation.",
                    }

                case CancelledElicitation():
                    return {
                        "status": "cancelled",
                        "estimated_count": estimated_count,
                        "message": "Fetch operation was cancelled.",
                    }

        except Exception as e:
            # Elicitation not available - proceed with warning
            error_msg = str(e)
            if "not supported" in error_msg.lower() or "elicit" in error_msg.lower():
                # Elicitation not available, proceed with warning
                pass
            else:
                # Other error, still proceed but log
                pass

            # Fallback: proceed with warning for large fetches
            limit = None

    else:
        # Below threshold, no confirmation needed
        limit = None

    # Step 3: Execute the fetch
    ws = get_workspace(ctx)

    try:
        # Build kwargs, only including non-None values
        fetch_kwargs: dict[str, Any] = {
            "from_date": from_date,
            "to_date": to_date,
        }
        if events:
            fetch_kwargs["events"] = events
        if table:
            fetch_kwargs["name"] = table
        if limit is not None:
            fetch_kwargs["limit"] = limit

        fetch_result = ws.fetch_events(**fetch_kwargs)

        # Get result details
        if hasattr(fetch_result, "to_dict"):
            result_data = fetch_result.to_dict()
        elif hasattr(fetch_result, "table_name") and hasattr(fetch_result, "row_count"):
            result_data = {
                "table_name": fetch_result.table_name,
                "row_count": fetch_result.row_count,
            }
        else:
            result_data = (
                fetch_result if isinstance(fetch_result, dict) else {"result": fetch_result}
            )

        return {
            "status": "completed",
            "estimated_count": estimated_count,
            "actual_count": result_data.get("row_count", 0),
            "table_name": result_data.get("table_name", table),
            "message": "Fetch completed successfully.",
            "estimation": estimation,
        }

    except Exception as e:
        return {
            "status": "error",
            "estimated_count": estimated_count,
            "message": f"Fetch failed: {str(e)}",
            "estimation": estimation,
        }
