"""Guided analysis tool with multi-step elicitation.

This module provides the guided_analysis tool that walks users
through a structured analysis workflow with choices at each step.

Uses ctx.elicit() for user choices with graceful degradation
when elicitation is unavailable.

Example:
    Ask Claude: "Help me analyze my data"
    Claude uses: guided_analysis()
    Claude prompts: "What would you like to focus on: conversion, retention, engagement, or revenue?"
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Literal

from fastmcp import Context
from fastmcp.server.elicitation import (
    AcceptedElicitation,
    CancelledElicitation,
    DeclinedElicitation,
)

from mp_mcp.context import get_workspace
from mp_mcp.errors import handle_errors
from mp_mcp.server import mcp

# Analysis focus area descriptions
FOCUS_DESCRIPTIONS: dict[str, str] = {
    "conversion": "Analyze funnel performance and conversion rates",
    "retention": "Analyze user return rates and cohort behavior",
    "engagement": "Analyze feature usage and user activity patterns",
    "revenue": "Analyze purchase events and revenue metrics",
}


@dataclass
class AnalysisChoice:
    """User's choice for analysis direction.

    Response type for guided_analysis focus selection.

    Attributes:
        focus_area: Primary focus area.
        time_period: Analysis time period.
        custom_start: Custom start date if time_period is 'custom'.
        custom_end: Custom end date if time_period is 'custom'.
    """

    focus_area: Literal["conversion", "retention", "engagement", "revenue"]
    """Primary focus area."""

    time_period: Literal["last_7_days", "last_30_days", "last_90_days", "custom"] = (
        "last_30_days"
    )
    """Analysis time period."""

    custom_start: str | None = None
    """Custom start date if time_period is 'custom'."""

    custom_end: str | None = None
    """Custom end date if time_period is 'custom'."""


@dataclass
class SegmentChoice:
    """User's choice for segment investigation.

    Response type for guided_analysis segment selection.

    Attributes:
        segment_index: Index of selected segment from presented list.
        investigate_further: Whether to drill deeper into this segment.
    """

    segment_index: int
    """Index of selected segment from presented list."""

    investigate_further: bool = True
    """Whether to drill deeper into this segment."""


def _get_date_range_from_period(
    period: Literal["last_7_days", "last_30_days", "last_90_days", "custom"],
    custom_start: str | None = None,
    custom_end: str | None = None,
) -> tuple[str, str]:
    """Convert time period to date range.

    Args:
        period: Time period specification.
        custom_start: Custom start date if period is 'custom'.
        custom_end: Custom end date if period is 'custom'.

    Returns:
        Tuple of (from_date, to_date) as strings.
    """
    today = datetime.now().date()

    if period == "custom" and custom_start and custom_end:
        return custom_start, custom_end

    days_map: dict[str, int] = {
        "last_7_days": 7,
        "last_30_days": 30,
        "last_90_days": 90,
    }

    days = days_map.get(period, 30)
    from_date = (today - timedelta(days=days)).isoformat()
    to_date = today.isoformat()
    return from_date, to_date


async def prompt_focus_selection(ctx: Context) -> AnalysisChoice | None:
    """Prompt user for analysis focus selection.

    Uses ctx.elicit() to ask the user what they want to focus on.
    Returns None if elicitation is unavailable or cancelled.

    Args:
        ctx: FastMCP context for elicitation.

    Returns:
        AnalysisChoice if user accepted, None otherwise.
    """
    focus_options = "\n".join(
        f"- {area}: {desc}" for area, desc in FOCUS_DESCRIPTIONS.items()
    )

    prompt = (
        "What would you like to analyze?\n\n"
        f"{focus_options}\n\n"
        "Choose a focus area and time period:"
    )

    try:
        result = await ctx.elicit(
            prompt,
            response_type=AnalysisChoice,  # type: ignore[arg-type]
        )

        match result:
            case AcceptedElicitation(data=choice_data):
                # Convert dict to AnalysisChoice
                if isinstance(choice_data, dict):
                    return AnalysisChoice(
                        focus_area=choice_data.get("focus_area", "conversion"),
                        time_period=choice_data.get("time_period", "last_30_days"),
                        custom_start=choice_data.get("custom_start"),
                        custom_end=choice_data.get("custom_end"),
                    )
                return None
            case DeclinedElicitation() | CancelledElicitation():
                return None

    except Exception:
        # Elicitation not available
        return None

    return None


def run_initial_analysis(
    ctx: Context,
    focus_area: Literal["conversion", "retention", "engagement", "revenue"],
    from_date: str,
    to_date: str,
) -> dict[str, Any]:
    """Run initial analysis based on focus area.

    Executes appropriate queries for the chosen focus area
    and returns results with potential segments for drill-down.

    Args:
        ctx: FastMCP context with workspace access.
        focus_area: User's chosen analysis focus.
        from_date: Start date for analysis.
        to_date: End date for analysis.

    Returns:
        Dictionary with initial analysis results and segments.
    """
    ws = get_workspace(ctx)
    results: dict[str, Any] = {
        "focus_area": focus_area,
        "period": {"from_date": from_date, "to_date": to_date},
        "findings": [],
        "segments": [],
    }

    try:
        # Get available events
        events = ws.events()[:20]
        results["available_events"] = events[:5]
    except Exception:
        events = []

    if focus_area == "conversion":
        # Analyze conversion - look for funnel-like patterns
        try:
            # Get saved funnels
            funnels = ws.funnels()
            if funnels:
                results["findings"].append(
                    f"Found {len(funnels)} saved funnels for analysis"
                )
                results["funnels"] = funnels[:5]

            # Get top events for conversion analysis
            top_events = ws.top_events(limit=10)
            if hasattr(top_events, "to_dict"):
                top_data = top_events.to_dict()
            else:
                top_data = top_events

            results["top_events"] = top_data
            results["findings"].append("Retrieved top events for conversion analysis")

            # Add segment options
            results["segments"] = [
                {"name": "By Browser", "property": "$browser"},
                {"name": "By Platform", "property": "$os"},
                {"name": "By Country", "property": "$country_code"},
            ]

        except Exception as e:
            results["findings"].append(f"Conversion analysis error: {str(e)}")

    elif focus_area == "retention":
        # Analyze retention patterns
        try:
            # Try retention query with first available event
            acquisition_event = events[0] if events else "signup"

            ret_result = ws.retention(
                born_event=acquisition_event,
                return_event=acquisition_event,
                from_date=from_date,
                to_date=to_date,
                unit="day",
                interval_count=7,
            )
            results["retention_data"] = ret_result.to_dict()
            results["findings"].append(
                f"Retrieved D7 retention for '{acquisition_event}'"
            )

            # Add segment options
            results["segments"] = [
                {"name": "By Browser", "property": "$browser"},
                {"name": "By Platform", "property": "$os"},
                {"name": "By Source", "property": "utm_source"},
            ]

        except Exception as e:
            results["findings"].append(f"Retention analysis error: {str(e)}")

    elif focus_area == "engagement":
        # Analyze engagement patterns
        try:
            # Get event counts for engagement analysis
            if events:
                counts_result = ws.event_counts(
                    events=events[:10],
                    from_date=from_date,
                    to_date=to_date,
                    type="unique",
                )
                results["event_counts"] = counts_result.to_dict()
                results["findings"].append("Retrieved unique user counts per event")

            # Add frequency analysis suggestion
            results["frequency_suggestion"] = (
                "Consider analyzing user frequency (addiction) patterns"
            )

            # Add segment options
            results["segments"] = [
                {"name": "By Browser", "property": "$browser"},
                {"name": "By Platform", "property": "$os"},
                {"name": "Power Users", "property": "user_segment"},
            ]

        except Exception as e:
            results["findings"].append(f"Engagement analysis error: {str(e)}")

    elif focus_area == "revenue":
        # Analyze revenue patterns
        try:
            # Look for purchase-related events
            revenue_events = [
                e
                for e in events
                if any(k in e.lower() for k in ["purchase", "pay", "buy", "order"])
            ]

            if revenue_events:
                results["revenue_events"] = revenue_events
                results["findings"].append(
                    f"Found {len(revenue_events)} revenue events"
                )

                # Get segmentation for first revenue event
                seg_result = ws.segmentation(
                    event=revenue_events[0],
                    from_date=from_date,
                    to_date=to_date,
                    unit="day",
                )
                results["revenue_trend"] = seg_result.to_dict()
            else:
                results["findings"].append(
                    "No revenue events found - check event naming"
                )

            # Add segment options
            results["segments"] = [
                {"name": "By Product", "property": "product_name"},
                {"name": "By Plan", "property": "plan_type"},
                {"name": "By Country", "property": "$country_code"},
            ]

        except Exception as e:
            results["findings"].append(f"Revenue analysis error: {str(e)}")

    return results


async def prompt_segment_selection(
    ctx: Context,
    segments: list[dict[str, str]],
) -> SegmentChoice | None:
    """Prompt user for segment selection.

    Uses ctx.elicit() to ask the user which segment to drill into.
    Returns None if elicitation is unavailable or cancelled.

    Args:
        ctx: FastMCP context for elicitation.
        segments: List of available segments from initial analysis.

    Returns:
        SegmentChoice if user accepted, None otherwise.
    """
    if not segments:
        return None

    segment_options = "\n".join(
        f"{i + 1}. {s.get('name', s.get('property', 'Unknown'))}"
        for i, s in enumerate(segments)
    )

    prompt = (
        "Would you like to drill deeper into a specific segment?\n\n"
        f"Available segments:\n{segment_options}\n\n"
        "Select a segment to investigate:"
    )

    try:
        result = await ctx.elicit(
            prompt,
            response_type=SegmentChoice,  # type: ignore[arg-type]
        )

        match result:
            case AcceptedElicitation(data=segment_data):
                # Convert dict to SegmentChoice
                if isinstance(segment_data, dict):
                    return SegmentChoice(
                        segment_index=segment_data.get("segment_index", 0),
                    )
                return None
            case DeclinedElicitation() | CancelledElicitation():
                return None

    except Exception:
        # Elicitation not available
        return None

    return None


def run_segment_analysis(
    ctx: Context,
    focus_area: Literal["conversion", "retention", "engagement", "revenue"],
    segment_property: str,
    from_date: str,
    to_date: str,
) -> dict[str, Any]:
    """Run segment-specific analysis.

    Drills into a specific segment based on user selection.

    Args:
        ctx: FastMCP context with workspace access.
        focus_area: Original focus area.
        segment_property: Property to segment by.
        from_date: Start date for analysis.
        to_date: End date for analysis.

    Returns:
        Dictionary with segment analysis results.
    """
    ws = get_workspace(ctx)
    results: dict[str, Any] = {
        "segment_property": segment_property,
        "findings": [],
        "breakdown": {},
    }

    try:
        # Get available events
        events = ws.events()[:5]
        main_event = events[0] if events else "login"

        if focus_area == "retention":
            # Segment retention analysis not directly supported,
            # fall back to property counts
            prop_result = ws.property_counts(
                event=main_event,
                property_name=segment_property,
                from_date=from_date,
                to_date=to_date,
                limit=10,
            )
            results["breakdown"] = prop_result.to_dict()
            results["findings"].append(
                f"Retrieved user counts by {segment_property} for retention analysis"
            )

        else:
            # Use property counts for segmentation
            prop_result = ws.property_counts(
                event=main_event,
                property_name=segment_property,
                from_date=from_date,
                to_date=to_date,
                limit=10,
            )
            results["breakdown"] = prop_result.to_dict()
            results["findings"].append(f"Retrieved breakdown by {segment_property}")

    except Exception as e:
        results["findings"].append(f"Segment analysis error: {str(e)}")

    return results


@mcp.tool
@handle_errors
async def guided_analysis(
    ctx: Context,
    focus_area: Literal["conversion", "retention", "engagement", "revenue"]
    | None = None,
    time_period: Literal["last_7_days", "last_30_days", "last_90_days", "custom"]
    | None = None,
    from_date: str | None = None,
    to_date: str | None = None,
) -> dict[str, Any]:
    """Interactive guided analysis with multi-step workflow.

    Walks users through a structured analysis workflow:
    1. Select focus area (conversion, retention, engagement, revenue)
    2. Run initial analysis for the chosen focus
    3. Present segment options for drill-down
    4. Execute segment-specific analysis if requested

    Uses ctx.elicit() for interactive choices when available;
    falls back to parameter-based analysis when unavailable.

    Args:
        ctx: FastMCP context with workspace access.
        focus_area: Pre-selected focus area (skips elicitation).
        time_period: Pre-selected time period.
        from_date: Custom start date for analysis.
        to_date: Custom end date for analysis.

    Returns:
        Dictionary containing:
        - status: "completed", "partial", or "elicitation_unavailable"
        - focus_area: The analysis focus chosen
        - period: Date range analyzed
        - initial_analysis: Results from first analysis pass
        - segment_analysis: Results from drill-down (if performed)
        - suggestions: Recommended next steps

    Example:
        Ask: "Help me analyze my data"
        Uses: guided_analysis()

        Ask: "Guide me through retention analysis"
        Uses: guided_analysis(focus_area="retention")
    """
    result: dict[str, Any] = {
        "status": "completed",
        "workflow_steps": [],
    }

    # Step 1: Get focus area
    if focus_area is None:
        # Try elicitation
        choice = await prompt_focus_selection(ctx)

        if choice:
            focus_area = choice.focus_area
            time_period = choice.time_period
            from_date = choice.custom_start
            to_date = choice.custom_end
            result["workflow_steps"].append("User selected focus via elicitation")
        else:
            # Elicitation unavailable - provide guidance without selection
            result["status"] = "elicitation_unavailable"
            result["focus_options"] = FOCUS_DESCRIPTIONS
            result["message"] = (
                "Interactive guidance unavailable. "
                "Please call again with a focus_area parameter: "
                "'conversion', 'retention', 'engagement', or 'revenue'"
            )
            result["example"] = "guided_analysis(focus_area='retention')"
            return result
    else:
        result["workflow_steps"].append(f"Focus area provided: {focus_area}")

    # Resolve date range
    if not time_period:
        time_period = "last_30_days"

    analysis_from, analysis_to = _get_date_range_from_period(
        time_period, from_date, to_date
    )

    result["focus_area"] = focus_area
    result["period"] = {"from_date": analysis_from, "to_date": analysis_to}

    # Step 2: Run initial analysis
    initial_analysis = run_initial_analysis(ctx, focus_area, analysis_from, analysis_to)
    result["initial_analysis"] = initial_analysis
    result["workflow_steps"].append("Completed initial analysis")

    # Step 3: Offer segment drill-down
    segments = initial_analysis.get("segments", [])

    if segments:
        segment_choice = await prompt_segment_selection(ctx, segments)

        if segment_choice:
            # Validate segment index
            if 0 <= segment_choice.segment_index < len(segments):
                selected_segment = segments[segment_choice.segment_index]
                segment_property = selected_segment.get("property", "$browser")

                result["workflow_steps"].append(
                    f"User selected segment: {selected_segment.get('name', segment_property)}"
                )

                # Step 4: Run segment analysis
                if segment_choice.investigate_further:
                    segment_analysis = run_segment_analysis(
                        ctx,
                        focus_area,
                        segment_property,
                        analysis_from,
                        analysis_to,
                    )
                    result["segment_analysis"] = segment_analysis
                    result["workflow_steps"].append("Completed segment analysis")
            else:
                result["workflow_steps"].append("Invalid segment index, skipping")
        else:
            result["workflow_steps"].append("Segment selection unavailable or skipped")
            result["available_segments"] = segments

    # Add suggestions for next steps
    suggestions: list[str] = []

    if focus_area == "conversion":
        suggestions.extend(
            [
                "Use funnel_optimization_report for deeper funnel analysis",
                "Compare conversion rates across different user segments",
                "Track drop-off points in your key funnels",
            ]
        )
    elif focus_area == "retention":
        suggestions.extend(
            [
                "Use product_health_dashboard for AARRR metrics view",
                "Compare retention across cohorts",
                "Identify actions that correlate with better retention",
            ]
        )
    elif focus_area == "engagement":
        suggestions.extend(
            [
                "Use gqm_investigation to explore engagement hypotheses",
                "Analyze feature adoption rates",
                "Identify power users and their behaviors",
            ]
        )
    elif focus_area == "revenue":
        suggestions.extend(
            [
                "Track revenue per user over time",
                "Analyze upgrade/downgrade patterns",
                "Identify revenue drivers by segment",
            ]
        )

    result["suggestions"] = suggestions

    return result
