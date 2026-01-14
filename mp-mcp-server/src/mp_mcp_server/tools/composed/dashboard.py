"""Product health dashboard tool.

This module provides the product_health_dashboard tool that computes
AARRR (Acquisition, Activation, Retention, Revenue, Referral) metrics.

Composes multiple primitive tools to provide a comprehensive view
of product health.

Example:
    Ask Claude: "Show me a product health dashboard"
    Claude uses: product_health_dashboard(acquisition_event="signup")
"""

from dataclasses import asdict
from datetime import datetime, timedelta
from typing import Any

from fastmcp import Context

from mp_mcp_server.context import get_workspace
from mp_mcp_server.errors import handle_errors
from mp_mcp_server.server import mcp
from mp_mcp_server.types import AARRRMetrics, ProductHealthDashboard


def _get_default_date_range(days_back: int = 30) -> tuple[str, str]:
    """Get default date range for dashboard.

    Args:
        days_back: Number of days to look back.

    Returns:
        Tuple of (from_date, to_date) as strings.
    """
    today = datetime.now().date()
    from_date = (today - timedelta(days=days_back)).isoformat()
    to_date = today.isoformat()
    return from_date, to_date


def _compute_acquisition(
    ctx: Context,
    acquisition_event: str,
    from_date: str,
    to_date: str,
    segment_by: str | None = None,
) -> AARRRMetrics:
    """Compute acquisition metrics.

    Measures new user signups/acquisitions over time.

    Args:
        ctx: FastMCP context with workspace access.
        acquisition_event: Event that indicates acquisition (e.g., signup).
        from_date: Start date for analysis.
        to_date: End date for analysis.
        segment_by: Optional property to segment by.

    Returns:
        AARRRMetrics for acquisition.
    """
    ws = get_workspace(ctx)

    # Get time series for acquisition event
    try:
        result = ws.segmentation(
            event=acquisition_event,
            from_date=from_date,
            to_date=to_date,
            on=segment_by,
            unit="day",
        )
        data = result.to_dict()

        # Extract trend data from series (structure: {event_name: {date: count}})
        trend: dict[str, float] = {}
        total = float(data.get("total", 0))

        series = data.get("series", {})
        if isinstance(series, dict):
            # Sum all segments for trend
            for segment_values in series.values():
                if isinstance(segment_values, dict):
                    for date_str, count in segment_values.items():
                        trend[date_str] = trend.get(date_str, 0) + float(count)

        # Primary metric is total acquisitions
        primary_metric = total

        # Segment breakdown if requested
        by_segment: dict[str, dict[str, Any]] | None = None
        if segment_by and series:
            by_segment = {}
            for segment_name, segment_values in series.items():
                if isinstance(segment_values, dict):
                    seg_total = sum(float(v) for v in segment_values.values())
                    by_segment[segment_name] = {
                        "total": seg_total,
                        "trend": segment_values,
                    }

        return AARRRMetrics(
            category="acquisition",
            primary_metric=primary_metric,
            trend=trend,
            by_segment=by_segment,
        )

    except Exception as e:
        return AARRRMetrics(
            category="acquisition",
            primary_metric=0.0,
            trend={},
            by_segment={"_error": {"message": str(e)}},
        )


def _compute_activation(
    ctx: Context,
    activation_event: str,
    acquisition_event: str,
    from_date: str,
    to_date: str,
) -> AARRRMetrics:
    """Compute activation metrics.

    Measures users who completed activation (first value moment).

    Args:
        ctx: FastMCP context with workspace access.
        activation_event: Event that indicates activation.
        acquisition_event: Event that indicates acquisition (for ratio).
        from_date: Start date for analysis.
        to_date: End date for analysis.

    Returns:
        AARRRMetrics for activation.
    """
    ws = get_workspace(ctx)

    try:
        # Get activation event counts
        activation_result = ws.segmentation(
            event=activation_event,
            from_date=from_date,
            to_date=to_date,
            unit="day",
        )
        activation_data = activation_result.to_dict()

        # Get acquisition for comparison
        acquisition_result = ws.segmentation(
            event=acquisition_event,
            from_date=from_date,
            to_date=to_date,
            unit="day",
        )
        acquisition_data = acquisition_result.to_dict()

        # Calculate totals from series structure
        activation_total = float(activation_data.get("total", 0))
        acquisition_total = float(acquisition_data.get("total", 0))
        trend: dict[str, float] = {}

        activation_series = activation_data.get("series", {})
        if isinstance(activation_series, dict):
            for segment_values in activation_series.values():
                if isinstance(segment_values, dict):
                    for date_str, count in segment_values.items():
                        trend[date_str] = trend.get(date_str, 0) + float(count)

        # Primary metric is activation rate (activations / acquisitions)
        primary_metric = (
            activation_total / acquisition_total if acquisition_total > 0 else 0.0
        )

        return AARRRMetrics(
            category="activation",
            primary_metric=primary_metric,
            trend=trend,
        )

    except Exception as e:
        return AARRRMetrics(
            category="activation",
            primary_metric=0.0,
            trend={},
            by_segment={"_error": {"message": str(e)}},
        )


def _compute_retention(
    ctx: Context,
    retention_event: str,
    from_date: str,
    to_date: str,
) -> AARRRMetrics:
    """Compute retention metrics.

    Measures user return rates over time.

    Args:
        ctx: FastMCP context with workspace access.
        retention_event: Event that indicates return visit.
        from_date: Start date for analysis.
        to_date: End date for analysis.

    Returns:
        AARRRMetrics for retention.
    """
    ws = get_workspace(ctx)

    try:
        # Get retention curve
        result = ws.retention(
            born_event=retention_event,
            return_event=retention_event,
            from_date=from_date,
            to_date=to_date,
            unit="day",
            interval_count=7,
        )
        data = result.to_dict()

        # Extract D7 retention as primary metric
        primary_metric = 0.0
        trend: dict[str, float] = {}

        if "data" in data:
            retention_data = data["data"]
            # Look for day 7 retention
            if isinstance(retention_data, dict):
                # Try to find D7 retention rate
                for key, value in retention_data.items():
                    if isinstance(value, dict):
                        # This might be a cohort with retention values
                        if "7" in value or 7 in value:
                            d7_val = value.get("7", value.get(7, 0))
                            primary_metric = float(d7_val) if d7_val is not None else 0.0
                            break
                    elif isinstance(value, (int, float)) and "7" in str(key):
                        primary_metric = float(value) / 100.0  # Convert to rate
                        break

                # Build trend from cohort data
                for key, value in retention_data.items():
                    if isinstance(value, (int, float)):
                        trend[str(key)] = float(value)

        return AARRRMetrics(
            category="retention",
            primary_metric=primary_metric,
            trend=trend,
        )

    except Exception as e:
        return AARRRMetrics(
            category="retention",
            primary_metric=0.0,
            trend={},
            by_segment={"_error": {"message": str(e)}},
        )


def _compute_revenue(
    ctx: Context,
    revenue_event: str | None,
    from_date: str,
    to_date: str,
) -> AARRRMetrics | None:
    """Compute revenue metrics.

    Measures revenue-related events over time.

    Args:
        ctx: FastMCP context with workspace access.
        revenue_event: Event that indicates revenue (e.g., purchase).
        from_date: Start date for analysis.
        to_date: End date for analysis.

    Returns:
        AARRRMetrics for revenue, or None if no revenue event specified.
    """
    if not revenue_event:
        return None

    ws = get_workspace(ctx)

    try:
        result = ws.segmentation(
            event=revenue_event,
            from_date=from_date,
            to_date=to_date,
            unit="day",
        )
        data = result.to_dict()

        trend: dict[str, float] = {}
        total = float(data.get("total", 0))

        series = data.get("series", {})
        if isinstance(series, dict):
            for segment_values in series.values():
                if isinstance(segment_values, dict):
                    for date_str, count in segment_values.items():
                        trend[date_str] = trend.get(date_str, 0) + float(count)

        return AARRRMetrics(
            category="revenue",
            primary_metric=total,
            trend=trend,
        )

    except Exception as e:
        return AARRRMetrics(
            category="revenue",
            primary_metric=0.0,
            trend={},
            by_segment={"_error": {"message": str(e)}},
        )


def _compute_referral(
    ctx: Context,
    referral_event: str | None,
    from_date: str,
    to_date: str,
) -> AARRRMetrics | None:
    """Compute referral metrics.

    Measures referral/invitation events over time.

    Args:
        ctx: FastMCP context with workspace access.
        referral_event: Event that indicates referral (e.g., invite_sent).
        from_date: Start date for analysis.
        to_date: End date for analysis.

    Returns:
        AARRRMetrics for referral, or None if no referral event specified.
    """
    if not referral_event:
        return None

    ws = get_workspace(ctx)

    try:
        result = ws.segmentation(
            event=referral_event,
            from_date=from_date,
            to_date=to_date,
            unit="day",
        )
        data = result.to_dict()

        trend: dict[str, float] = {}
        total = float(data.get("total", 0))

        series = data.get("series", {})
        if isinstance(series, dict):
            for segment_values in series.values():
                if isinstance(segment_values, dict):
                    for date_str, count in segment_values.items():
                        trend[date_str] = trend.get(date_str, 0) + float(count)

        return AARRRMetrics(
            category="referral",
            primary_metric=total,
            trend=trend,
        )

    except Exception as e:
        return AARRRMetrics(
            category="referral",
            primary_metric=0.0,
            trend={},
            by_segment={"_error": {"message": str(e)}},
        )


def _compute_health_score(dashboard: ProductHealthDashboard) -> dict[str, int]:
    """Compute health scores (1-10) for each AARRR category.

    Scoring is relative to the metrics themselves:
    - Acquisition: Based on total count (subjective)
    - Activation: Based on activation rate (0-100%)
    - Retention: Based on D7 retention rate
    - Revenue: Based on total count (subjective)
    - Referral: Based on total count (subjective)

    Args:
        dashboard: The dashboard with computed metrics.

    Returns:
        Dictionary with scores for each category.
    """
    scores: dict[str, int] = {}

    # Acquisition: Score based on having data
    if dashboard.acquisition:
        if dashboard.acquisition.primary_metric > 1000:
            scores["acquisition"] = 8
        elif dashboard.acquisition.primary_metric > 100:
            scores["acquisition"] = 6
        elif dashboard.acquisition.primary_metric > 0:
            scores["acquisition"] = 4
        else:
            scores["acquisition"] = 2

    # Activation: Score based on rate (0-1)
    if dashboard.activation:
        rate = dashboard.activation.primary_metric
        if rate >= 0.5:
            scores["activation"] = 9
        elif rate >= 0.3:
            scores["activation"] = 7
        elif rate >= 0.1:
            scores["activation"] = 5
        elif rate > 0:
            scores["activation"] = 3
        else:
            scores["activation"] = 1

    # Retention: Score based on D7 rate
    if dashboard.retention:
        rate = dashboard.retention.primary_metric
        if rate >= 0.4:
            scores["retention"] = 9
        elif rate >= 0.25:
            scores["retention"] = 7
        elif rate >= 0.1:
            scores["retention"] = 5
        elif rate > 0:
            scores["retention"] = 3
        else:
            scores["retention"] = 1

    # Revenue: Score based on having data
    if dashboard.revenue:
        if dashboard.revenue.primary_metric > 1000:
            scores["revenue"] = 8
        elif dashboard.revenue.primary_metric > 100:
            scores["revenue"] = 6
        elif dashboard.revenue.primary_metric > 0:
            scores["revenue"] = 4
        else:
            scores["revenue"] = 2

    # Referral: Score based on having data
    if dashboard.referral:
        if dashboard.referral.primary_metric > 100:
            scores["referral"] = 8
        elif dashboard.referral.primary_metric > 10:
            scores["referral"] = 6
        elif dashboard.referral.primary_metric > 0:
            scores["referral"] = 4
        else:
            scores["referral"] = 2

    return scores


@mcp.tool
@handle_errors
def product_health_dashboard(
    ctx: Context,
    acquisition_event: str = "signup",
    activation_event: str | None = None,
    retention_event: str | None = None,
    revenue_event: str | None = None,
    referral_event: str | None = None,
    from_date: str | None = None,
    to_date: str | None = None,
    segment_by: str | None = None,
) -> dict[str, Any]:
    """Generate a comprehensive AARRR product health dashboard.

    Computes Acquisition, Activation, Retention, Revenue, and Referral
    metrics for the specified events and date range.

    Args:
        ctx: FastMCP context with workspace access.
        acquisition_event: Event indicating acquisition (default: "signup").
        activation_event: Event indicating activation/first value moment.
            If not specified, uses the acquisition event.
        retention_event: Event for retention analysis.
            If not specified, uses the acquisition event.
        revenue_event: Event indicating revenue (e.g., "purchase").
            Optional - omit if not tracking revenue events.
        referral_event: Event indicating referral (e.g., "invite_sent").
            Optional - omit if not tracking referral events.
        from_date: Start date for analysis (YYYY-MM-DD).
            Defaults to 30 days ago.
        to_date: End date for analysis (YYYY-MM-DD).
            Defaults to today.
        segment_by: Optional property to segment acquisition by.

    Returns:
        Dictionary containing:
        - period: Analysis date range
        - acquisition: Acquisition metrics and trends
        - activation: Activation rate and trends
        - retention: D7 retention rate and cohort data
        - revenue: Revenue metrics (if event specified)
        - referral: Referral metrics (if event specified)
        - health_score: 1-10 score for each category

    Example:
        Ask: "Show me a product health dashboard"
        Uses: product_health_dashboard()

        Ask: "Dashboard with purchase as revenue event"
        Uses: product_health_dashboard(
            acquisition_event="signup",
            revenue_event="purchase",
        )
    """
    # Default date range
    if not from_date or not to_date:
        from_date, to_date = _get_default_date_range()

    # Default events to acquisition event
    if not activation_event:
        activation_event = acquisition_event
    if not retention_event:
        retention_event = acquisition_event

    # Compute each AARRR category
    acquisition = _compute_acquisition(
        ctx, acquisition_event, from_date, to_date, segment_by
    )
    activation = _compute_activation(
        ctx, activation_event, acquisition_event, from_date, to_date
    )
    retention = _compute_retention(ctx, retention_event, from_date, to_date)
    revenue = _compute_revenue(ctx, revenue_event, from_date, to_date)
    referral = _compute_referral(ctx, referral_event, from_date, to_date)

    # Build dashboard
    dashboard = ProductHealthDashboard(
        period={"from_date": from_date, "to_date": to_date},
        acquisition=acquisition,
        activation=activation,
        retention=retention,
        revenue=revenue,
        referral=referral,
    )

    # Compute health scores
    health_scores = _compute_health_score(dashboard)
    dashboard.health_score = health_scores

    return asdict(dashboard)
