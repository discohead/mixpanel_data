"""MCP resources for accessing Mixpanel schema and workspace state.

Resources provide read-only access to cacheable data like schema information
and workspace state. MCP clients can read these for context.

Includes dynamic resource templates for common analytics patterns:
- analysis://retention/{event}/weekly - 12-week retention curves
- analysis://trends/{event}/{days} - Event trend data
- users://{id}/journey - User activity journeys
- recipes://weekly-review - Weekly analytics checklist
- recipes://churn-investigation - Churn analysis playbook

Example:
    MCP clients can read schema://events to get the list of tracked events
    without making a tool call.
"""

import json
import logging
from collections.abc import Callable
from datetime import datetime, timedelta
from functools import wraps
from typing import Any, ParamSpec, TypeVar

from fastmcp import Context
from mcp.shared.exceptions import McpError
from mcp.types import INTERNAL_ERROR, ErrorData

from mixpanel_data.exceptions import MixpanelDataError
from mp_mcp.context import get_workspace
from mp_mcp.server import mcp

logger = logging.getLogger(__name__)

P = ParamSpec("P")
R = TypeVar("R", bound=str)


def handle_resource_errors(func: Callable[P, R]) -> Callable[P, R]:
    """Decorator to handle errors in MCP resources.

    Raises McpError with structured error data that agents can parse
    for self-correction. The error data includes error codes, messages,
    and actionable suggestions.

    Args:
        func: The resource function to wrap.

    Returns:
        The wrapped function that raises McpError on failure.

    Raises:
        McpError: When the resource fails, with structured error data
            in the `data` field for agent recovery.

    Example:
        ```python
        @mcp.resource("schema://events")
        @handle_resource_errors
        def events_resource(ctx: Context) -> str:
            ws = get_workspace(ctx)
            return json.dumps(ws.events())
        ```
    """

    @wraps(func)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> str:
        try:
            return func(*args, **kwargs)
        except MixpanelDataError as e:
            logger.warning("Resource error: %s", e, exc_info=True)
            raise McpError(
                ErrorData(
                    code=INTERNAL_ERROR,
                    message=str(e),
                    data=e.to_dict(),
                )
            ) from e
        except Exception as e:
            logger.exception("Unexpected resource error: %s", e)
            raise McpError(
                ErrorData(
                    code=INTERNAL_ERROR,
                    message=str(e),
                    data={
                        "code": "INTERNAL_ERROR",
                        "message": str(e),
                        "details": {"error_type": type(e).__name__},
                    },
                )
            ) from e

    return wrapper  # type: ignore[return-value]


@mcp.resource("workspace://info")
@handle_resource_errors
def workspace_info_resource(ctx: Context) -> str:
    """Workspace configuration and connection status.

    Returns project_id, region, and current session state.

    Args:
        ctx: FastMCP context with workspace access.

    Returns:
        JSON string with workspace info.
    """
    ws = get_workspace(ctx)
    workspace_info = ws.info()
    info = {
        "project_id": workspace_info.project_id,
        "region": workspace_info.region,
        "account": workspace_info.account,
        "path": str(workspace_info.path) if workspace_info.path else None,
        "size_mb": workspace_info.size_mb,
        "created_at": (
            workspace_info.created_at.isoformat() if workspace_info.created_at else None
        ),
        "tables": [t.to_dict() for t in ws.tables()],
    }
    return json.dumps(info, indent=2)


@mcp.resource("workspace://tables")
@handle_resource_errors
def tables_resource(ctx: Context) -> str:
    """List of locally stored tables.

    Returns table names, row counts, and types for all fetched data.

    Args:
        ctx: FastMCP context with workspace access.

    Returns:
        JSON string with table list.
    """
    ws = get_workspace(ctx)
    tables = [t.to_dict() for t in ws.tables()]
    return json.dumps(tables, indent=2)


@mcp.resource("schema://events")
@handle_resource_errors
def events_resource(ctx: Context) -> str:
    """List of event names tracked in the project.

    Returns all event names for schema exploration.

    Args:
        ctx: FastMCP context with workspace access.

    Returns:
        JSON string with event list.
    """
    ws = get_workspace(ctx)
    events = ws.events()
    return json.dumps(events, indent=2)


@mcp.resource("schema://funnels")
@handle_resource_errors
def funnels_resource(ctx: Context) -> str:
    """Saved funnel definitions.

    Returns funnel IDs, names, and step counts.

    Args:
        ctx: FastMCP context with workspace access.

    Returns:
        JSON string with funnel list.
    """
    ws = get_workspace(ctx)
    funnels = [f.to_dict() for f in ws.funnels()]
    return json.dumps(funnels, indent=2)


@mcp.resource("schema://cohorts")
@handle_resource_errors
def cohorts_resource(ctx: Context) -> str:
    """Saved cohort definitions.

    Returns cohort IDs, names, and user counts.

    Args:
        ctx: FastMCP context with workspace access.

    Returns:
        JSON string with cohort list.
    """
    ws = get_workspace(ctx)
    cohorts = [c.to_dict() for c in ws.cohorts()]
    return json.dumps(cohorts, indent=2)


@mcp.resource("schema://bookmarks")
@handle_resource_errors
def bookmarks_resource(ctx: Context) -> str:
    """Saved report bookmarks.

    Returns bookmark IDs, names, and report types.

    Args:
        ctx: FastMCP context with workspace access.

    Returns:
        JSON string with bookmark list.
    """
    ws = get_workspace(ctx)
    bookmarks = [b.to_dict() for b in ws.list_bookmarks()]
    return json.dumps(bookmarks, indent=2)


# =============================================================================
# Dynamic Resource Templates
# =============================================================================


def _get_date_range(days: int) -> tuple[str, str]:
    """Calculate date range for the last N days.

    Args:
        days: Number of days to look back.

    Returns:
        Tuple of (from_date, to_date) as YYYY-MM-DD strings.
    """
    today = datetime.now().date()
    from_date = (today - timedelta(days=days)).isoformat()
    to_date = today.isoformat()
    return from_date, to_date


@mcp.resource("analysis://retention/{event}/weekly")
@handle_resource_errors
def retention_weekly_resource(ctx: Context, event: str) -> str:
    """12-week retention curve for an event.

    Returns weekly retention data for the specified event,
    showing how users return over 12 weeks.

    Args:
        ctx: FastMCP context with workspace access.
        event: Event name for cohort entry (born event).

    Returns:
        JSON string with 12-week retention curve data.

    Example:
        Access analysis://retention/signup/weekly to get
        retention curve for users who signed up.
    """
    ws = get_workspace(ctx)

    # Get last 12 weeks
    from_date, to_date = _get_date_range(84)  # 12 weeks

    result = ws.retention(
        born_event=event,
        return_event=event,
        from_date=from_date,
        to_date=to_date,
        unit="week",
        interval_count=12,
    )

    # Build structured response
    response: dict[str, Any] = {
        "event": event,
        "period": "weekly",
        "from_date": from_date,
        "to_date": to_date,
        "weeks": 12,
    }

    if hasattr(result, "to_dict"):
        response["data"] = result.to_dict()
    else:
        response["data"] = result

    return json.dumps(response, indent=2)


@mcp.resource("analysis://trends/{event}/{days}")
@handle_resource_errors
def trends_resource(ctx: Context, event: str, days: str) -> str:
    """Daily event counts for the specified period.

    Returns daily counts for an event over the specified
    number of days.

    Args:
        ctx: FastMCP context with workspace access.
        event: Event name to analyze.
        days: Number of days to look back (as string from URL).

    Returns:
        JSON string with daily event counts.

    Example:
        Access analysis://trends/login/30 to get
        login counts for the last 30 days.
    """
    ws = get_workspace(ctx)

    # Parse days parameter
    try:
        days_int = int(days)
        if days_int < 1:
            days_int = 7
        elif days_int > 365:
            days_int = 365
    except ValueError:
        days_int = 30

    from_date, to_date = _get_date_range(days_int)

    result = ws.segmentation(
        event=event,
        from_date=from_date,
        to_date=to_date,
        unit="day",
    )

    response: dict[str, Any] = {
        "event": event,
        "days": days_int,
        "from_date": from_date,
        "to_date": to_date,
        "unit": "day",
    }

    if hasattr(result, "to_dict"):
        response["data"] = result.to_dict()
    else:
        response["data"] = result

    return json.dumps(response, indent=2)


@mcp.resource("users://{id}/journey")
@handle_resource_errors
def user_journey_resource(ctx: Context, id: str) -> str:
    """User's complete event journey.

    Returns the user's activity feed with event history
    and summary statistics.

    Args:
        ctx: FastMCP context with workspace access.
        id: User's distinct_id.

    Returns:
        JSON string with user journey data.

    Example:
        Access users://user123/journey to get
        the complete event history for user123.
    """
    ws = get_workspace(ctx)

    # Get activity feed for user
    from_date, to_date = _get_date_range(90)  # Last 90 days

    result = ws.activity_feed(
        distinct_ids=[id],
        from_date=from_date,
        to_date=to_date,
    )

    # Get events from result
    result_dict = result.to_dict()
    events = result_dict.get("events", [])

    # Build summary
    event_counts: dict[str, int] = {}
    for event in events:
        if isinstance(event, dict):
            event_name = event.get("event", "unknown")
            event_counts[event_name] = event_counts.get(event_name, 0) + 1

    response: dict[str, Any] = {
        "distinct_id": id,
        "period": {
            "from_date": from_date,
            "to_date": to_date,
        },
        "summary": {
            "total_events": len(events),
            "unique_events": len(event_counts),
            "event_breakdown": event_counts,
        },
        "events": events[:100],  # Limit to first 100 for readability
        "truncated": len(events) > 100,
    }

    return json.dumps(response, indent=2, default=str)


@mcp.resource("recipes://weekly-review")
@handle_resource_errors
def weekly_review_recipe(_ctx: Context) -> str:
    """Weekly analytics review checklist.

    Returns a structured checklist for weekly analytics review
    with recommended queries and analysis steps.

    Args:
        _ctx: FastMCP context (unused - recipe is static).

    Returns:
        JSON string with weekly review recipe.
    """
    from_date, to_date = _get_date_range(7)
    prev_from = (datetime.now().date() - timedelta(days=14)).isoformat()
    prev_to = (datetime.now().date() - timedelta(days=7)).isoformat()

    recipe: dict[str, Any] = {
        "name": "Weekly Analytics Review",
        "description": "Comprehensive weekly check on product health",
        "current_period": {"from": from_date, "to": to_date},
        "comparison_period": {"from": prev_from, "to": prev_to},
        "checklist": [
            {
                "step": 1,
                "name": "Core Metrics Review",
                "description": "Check key metrics against previous week",
                "tools": ["segmentation", "event_counts"],
                "queries": [
                    {
                        "description": "Compare weekly active users",
                        "tool": "event_counts",
                        "params": {
                            "events": ["session_start", "login"],
                            "from_date": from_date,
                            "to_date": to_date,
                            "type": "unique",
                        },
                    },
                ],
            },
            {
                "step": 2,
                "name": "Conversion Health",
                "description": "Review funnel performance",
                "tools": ["funnel", "list_funnels"],
                "queries": [
                    {
                        "description": "List available funnels for analysis",
                        "tool": "list_funnels",
                    },
                ],
            },
            {
                "step": 3,
                "name": "Retention Check",
                "description": "Analyze user return rates",
                "tools": ["retention"],
                "queries": [
                    {
                        "description": "Weekly retention curve",
                        "tool": "retention",
                        "params": {
                            "born_event": "signup",
                            "from_date": from_date,
                            "to_date": to_date,
                            "unit": "day",
                        },
                    },
                ],
            },
            {
                "step": 4,
                "name": "Anomaly Detection",
                "description": "Look for unusual patterns",
                "tools": ["diagnose_metric_drop", "top_events"],
                "queries": [
                    {
                        "description": "Check top event volumes",
                        "tool": "top_events",
                        "params": {"limit": 20},
                    },
                ],
            },
            {
                "step": 5,
                "name": "User Feedback",
                "description": "Review qualitative signals",
                "tools": ["activity_feed", "stream_events"],
                "queries": [
                    {
                        "description": "Sample recent user sessions",
                        "tool": "stream_events",
                        "params": {
                            "from_date": from_date,
                            "to_date": to_date,
                            "limit": 100,
                        },
                    },
                ],
            },
        ],
        "report_template": {
            "sections": [
                "Executive Summary",
                "Key Metrics WoW",
                "Funnel Performance",
                "Retention Trends",
                "Notable Anomalies",
                "Action Items",
            ],
        },
    }

    return json.dumps(recipe, indent=2)


@mcp.resource("recipes://churn-investigation")
@handle_resource_errors
def churn_investigation_recipe(_ctx: Context) -> str:
    """Churn investigation playbook.

    Returns a structured playbook for investigating
    user churn with recommended analysis steps.

    Args:
        _ctx: FastMCP context (unused - recipe is static).

    Returns:
        JSON string with churn investigation recipe.
    """
    from_date, to_date = _get_date_range(30)

    recipe: dict[str, Any] = {
        "name": "Churn Investigation Playbook",
        "description": "Systematic approach to understanding user churn",
        "analysis_period": {"from": from_date, "to": to_date},
        "phases": [
            {
                "phase": 1,
                "name": "Define Churn",
                "description": "Establish clear churn criteria",
                "questions": [
                    "What event defines an active user?",
                    "How many days without activity = churned?",
                    "Are there different churn definitions by user segment?",
                ],
                "tools": ["list_events", "list_cohorts"],
            },
            {
                "phase": 2,
                "name": "Measure Baseline",
                "description": "Quantify current churn rates",
                "queries": [
                    {
                        "description": "Calculate retention curve",
                        "tool": "retention",
                        "params": {
                            "born_event": "signup",
                            "from_date": from_date,
                            "to_date": to_date,
                        },
                    },
                    {
                        "description": "Identify churn points",
                        "tool": "frequency",
                        "params": {
                            "from_date": from_date,
                            "to_date": to_date,
                        },
                    },
                ],
                "metrics": [
                    "D1, D7, D30 retention rates",
                    "Weekly churn rate",
                    "Monthly churn rate",
                ],
            },
            {
                "phase": 3,
                "name": "Identify Patterns",
                "description": "Find common characteristics of churned users",
                "queries": [
                    {
                        "description": "Compare churned vs retained users",
                        "tool": "cohort_comparison",
                        "params": {
                            "cohort_a_filter": 'properties["churned"] == true',
                            "cohort_b_filter": 'properties["churned"] == false',
                            "cohort_a_name": "Churned",
                            "cohort_b_name": "Retained",
                        },
                    },
                ],
                "segments_to_analyze": [
                    "Acquisition source",
                    "User type/plan",
                    "Onboarding completion",
                    "Feature usage patterns",
                    "Geographic region",
                ],
            },
            {
                "phase": 4,
                "name": "Analyze Behavior",
                "description": "Deep dive into churned user journeys",
                "queries": [
                    {
                        "description": "Analyze last actions before churn",
                        "tool": "fetch_events",
                        "params": {
                            "from_date": from_date,
                            "to_date": to_date,
                        },
                    },
                ],
                "analysis_questions": [
                    "What was the last action before churn?",
                    "Did users hit any errors or frustration points?",
                    "How long between signup and churn?",
                    "Did users complete key activation steps?",
                ],
            },
            {
                "phase": 5,
                "name": "Prioritize Interventions",
                "description": "Identify highest-impact fixes",
                "framework": {
                    "dimensions": ["Impact", "Effort", "Confidence"],
                    "scoring": "1-5 scale for each dimension",
                    "formula": "Priority = (Impact * Confidence) / Effort",
                },
                "common_interventions": [
                    "Improve onboarding flow",
                    "Add engagement triggers",
                    "Reduce friction in core flows",
                    "Implement re-engagement campaigns",
                    "Address feature gaps",
                ],
            },
        ],
        "benchmarks": {
            "good_d1_retention": "40-60%",
            "good_d7_retention": "20-30%",
            "good_d30_retention": "10-20%",
            "acceptable_monthly_churn": "<5% for B2B, <10% for B2C",
        },
    }

    return json.dumps(recipe, indent=2)
