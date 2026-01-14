"""Cohort comparison tool using JQL for efficiency.

This module provides the cohort_comparison tool that compares
two user cohorts across behavioral dimensions using JQL to
minimize API calls (respecting Mixpanel's 60 requests/hour limit).

Uses 1-2 JQL calls instead of 80+ segmentation calls.

Example:
    Ask Claude: "Compare power users vs casual users"
    Claude uses: cohort_comparison(
        cohort_a_filter='properties["sessions"] >= 10',
        cohort_b_filter='properties["sessions"] < 3',
    )
"""

from dataclasses import asdict
from datetime import datetime, timedelta
from typing import Any

from fastmcp import Context

from mp_mcp_server.context import get_workspace
from mp_mcp_server.errors import handle_errors
from mp_mcp_server.server import mcp
from mp_mcp_server.types import CohortComparison, CohortMetrics


def _get_default_date_range(days_back: int = 30) -> tuple[str, str]:
    """Get default date range for cohort comparison.

    Args:
        days_back: Number of days to look back.

    Returns:
        Tuple of (from_date, to_date) as strings.
    """
    today = datetime.now().date()
    from_date = (today - timedelta(days=days_back)).isoformat()
    to_date = today.isoformat()
    return from_date, to_date


def _build_event_comparison_jql(
    cohort_a_filter: str,
    cohort_b_filter: str,
) -> str:
    """Build JQL script for event frequency comparison.

    Creates a JQL script that groups events by name and cohort,
    returning counts for each combination in a single API call.

    Args:
        cohort_a_filter: JavaScript filter expression for cohort A.
        cohort_b_filter: JavaScript filter expression for cohort B.

    Returns:
        JQL script string.
    """
    # The filters should be JavaScript expressions that reference event.properties
    # e.g.: 'event.properties["$browser"] == "Chrome"'
    # We auto-convert 'properties[' to 'event.properties[' for convenience
    filter_a = cohort_a_filter.replace('properties["', 'event.properties["')
    filter_b = cohort_b_filter.replace('properties["', 'event.properties["')

    return f"""
function main() {{
  return Events({{
    from_date: params.from_date,
    to_date: params.to_date
  }})
  .filter(function(event) {{
    var inA = {filter_a};
    var inB = {filter_b};
    return inA || inB;
  }})
  .groupBy(["name", function(event) {{
    if ({filter_a}) return "cohort_a";
    if ({filter_b}) return "cohort_b";
    return "other";
  }}], mixpanel.reducer.count());
}}
"""


def _build_user_comparison_jql(
    cohort_a_filter: str,
    cohort_b_filter: str,
) -> str:
    """Build JQL script for unique user comparison.

    Creates a JQL script that counts unique users per cohort,
    providing a retention/engagement proxy.

    Args:
        cohort_a_filter: JavaScript filter expression for cohort A.
        cohort_b_filter: JavaScript filter expression for cohort B.

    Returns:
        JQL script string.
    """
    # Auto-convert 'properties[' to 'event.properties[' for convenience
    filter_a = cohort_a_filter.replace('properties["', 'event.properties["')
    filter_b = cohort_b_filter.replace('properties["', 'event.properties["')

    return f"""
function main() {{
  return Events({{
    from_date: params.from_date,
    to_date: params.to_date
  }})
  .filter(function(event) {{
    var inA = {filter_a};
    var inB = {filter_b};
    return inA || inB;
  }})
  .groupByUser([function(event) {{
    if ({filter_a}) return "cohort_a";
    if ({filter_b}) return "cohort_b";
    return "other";
  }}], mixpanel.reducer.count());
}}
"""


def _parse_event_comparison_results(
    jql_results: list[dict[str, Any]],
) -> dict[str, Any]:
    """Parse JQL results into event comparison structure.

    Args:
        jql_results: Raw results from JQL query.

    Returns:
        Dictionary with cohort_a_frequency, cohort_b_frequency, and differences.
    """
    cohort_a_events: dict[str, int] = {}
    cohort_b_events: dict[str, int] = {}

    for row in jql_results:
        # JQL groupBy returns results like:
        # {"key": ["event_name", "cohort_a"], "value": 123}
        key = row.get("key", [])
        value = row.get("value", 0)

        if len(key) >= 2:
            event_name = key[0]
            cohort = key[1]

            if cohort == "cohort_a":
                cohort_a_events[event_name] = value
            elif cohort == "cohort_b":
                cohort_b_events[event_name] = value

    # Calculate differences
    differences: list[dict[str, Any]] = []
    all_events = set(cohort_a_events.keys()) | set(cohort_b_events.keys())

    for event in all_events:
        a_count = cohort_a_events.get(event, 0)
        b_count = cohort_b_events.get(event, 0)

        if a_count > 0 and b_count > 0:
            ratio = a_count / b_count
            if ratio > 1.5 or ratio < 0.67:
                differences.append({
                    "event": event,
                    "cohort_a_count": a_count,
                    "cohort_b_count": b_count,
                    "ratio": round(ratio, 2),
                    "interpretation": (
                        f"Cohort A has {ratio:.1f}x more {event} events"
                        if ratio > 1
                        else f"Cohort B has {1/ratio:.1f}x more {event} events"
                    ),
                })
        elif a_count > 0 and b_count == 0:
            differences.append({
                "event": event,
                "cohort_a_count": a_count,
                "cohort_b_count": 0,
                "ratio": float("inf"),
                "interpretation": f"Only Cohort A has {event} events",
            })
        elif b_count > 0 and a_count == 0:
            differences.append({
                "event": event,
                "cohort_a_count": 0,
                "cohort_b_count": b_count,
                "ratio": 0,
                "interpretation": f"Only Cohort B has {event} events",
            })

    # Sort by ratio magnitude (most different first)
    differences.sort(
        key=lambda x: abs(x["ratio"] - 1) if x["ratio"] != float("inf") else 1000,
        reverse=True,
    )

    # Get top events for each cohort
    top_a = sorted(cohort_a_events.items(), key=lambda x: x[1], reverse=True)[:10]
    top_b = sorted(cohort_b_events.items(), key=lambda x: x[1], reverse=True)[:10]

    return {
        "cohort_a_frequency": cohort_a_events,
        "cohort_b_frequency": cohort_b_events,
        "cohort_a_top_events": [{"event": e, "count": c} for e, c in top_a],
        "cohort_b_top_events": [{"event": e, "count": c} for e, c in top_b],
        "differences": differences[:10],
    }


def _parse_user_comparison_results(
    jql_results: list[dict[str, Any]],
) -> dict[str, Any]:
    """Parse JQL results into user comparison structure.

    Args:
        jql_results: Raw results from JQL query.

    Returns:
        Dictionary with user counts per cohort.
    """
    cohort_a_users = 0
    cohort_b_users = 0

    for row in jql_results:
        key = row.get("key", [])
        value = row.get("value", 0)

        if len(key) >= 1:
            cohort = key[0]
            if cohort == "cohort_a":
                cohort_a_users = value
            elif cohort == "cohort_b":
                cohort_b_users = value

    return {
        "cohort_a_users": cohort_a_users,
        "cohort_b_users": cohort_b_users,
        "user_ratio": (
            round(cohort_a_users / cohort_b_users, 2)
            if cohort_b_users > 0
            else float("inf")
        ),
    }


@mcp.tool
@handle_errors
def cohort_comparison(
    ctx: Context,
    cohort_a_filter: str,
    cohort_b_filter: str,
    cohort_a_name: str = "Cohort A",
    cohort_b_name: str = "Cohort B",
    from_date: str | None = None,
    to_date: str | None = None,
    acquisition_event: str = "signup",
    compare_dimensions: list[str] | None = None,
) -> dict[str, Any]:
    """Compare two user cohorts across behavioral dimensions.

    Analyzes event frequency, retention, and top events for two
    cohorts defined by filter expressions, identifying significant
    differences in behavior.

    Args:
        ctx: FastMCP context with workspace access.
        cohort_a_filter: Filter expression for cohort A
            (e.g., 'properties["sessions"] >= 10').
        cohort_b_filter: Filter expression for cohort B
            (e.g., 'properties["sessions"] < 3').
        cohort_a_name: Display name for cohort A.
        cohort_b_name: Display name for cohort B.
        from_date: Start date for analysis (YYYY-MM-DD).
            Defaults to 30 days ago.
        to_date: End date for analysis (YYYY-MM-DD).
            Defaults to today.
        acquisition_event: Event for retention analysis (default: signup).
        compare_dimensions: Dimensions to compare. Options:
            - 'event_frequency': Compare event counts
            - 'retention': Compare return rates
            - 'top_events': Compare most popular events
            Defaults to all dimensions.

    Returns:
        Dictionary containing:
        - cohort_a: CohortMetrics for first cohort
        - cohort_b: CohortMetrics for second cohort
        - period: Analysis date range
        - comparisons: Results for each comparison dimension
        - statistical_significance: Whether differences are significant
        - key_differences: Summary of notable differences

    Example:
        Ask: "Compare power users vs casual users"
        Uses: cohort_comparison(
            cohort_a_filter='properties["sessions"] >= 10',
            cohort_b_filter='properties["sessions"] < 3',
            cohort_a_name="Power Users",
            cohort_b_name="Casual Users",
        )

        Ask: "Compare US vs EU users on retention"
        Uses: cohort_comparison(
            cohort_a_filter='properties["$country_code"] == "US"',
            cohort_b_filter='properties["$country_code"] in ["DE","FR","UK"]',
            compare_dimensions=["retention"],
        )
    """
    ws = get_workspace(ctx)

    # Note: acquisition_event kept for API compatibility but not used in JQL approach
    _ = acquisition_event

    # Set default date range
    if not from_date or not to_date:
        from_date, to_date = _get_default_date_range()

    # Default to all dimensions
    if compare_dimensions is None:
        compare_dimensions = ["event_frequency", "retention", "top_events"]

    # Initialize cohort metrics
    cohort_a = CohortMetrics(
        name=cohort_a_name,
        filter=cohort_a_filter,
    )
    cohort_b = CohortMetrics(
        name=cohort_b_name,
        filter=cohort_b_filter,
    )

    comparisons: dict[str, dict[str, Any]] = {}
    key_differences: list[str] = []
    errors: list[str] = []

    # JQL call 1: Event frequency and top events comparison
    if "event_frequency" in compare_dimensions or "top_events" in compare_dimensions:
        try:
            jql_script = _build_event_comparison_jql(cohort_a_filter, cohort_b_filter)
            jql_result = ws.jql(
                script=jql_script,
                params={"from_date": from_date, "to_date": to_date},
            )

            # Parse results - JQLResult has a .raw property
            if hasattr(jql_result, "raw"):
                results_list = jql_result.raw
            elif isinstance(jql_result, list):
                results_list = jql_result
            else:
                results_list = []

            event_data = _parse_event_comparison_results(results_list)

            if "event_frequency" in compare_dimensions:
                comparisons["event_frequency"] = {
                    "cohort_a_frequency": event_data["cohort_a_frequency"],
                    "cohort_b_frequency": event_data["cohort_b_frequency"],
                    "differences": event_data["differences"],
                }

            if "top_events" in compare_dimensions:
                comparisons["top_events"] = {
                    "cohort_a_top_events": event_data["cohort_a_top_events"],
                    "cohort_b_top_events": event_data["cohort_b_top_events"],
                }

            # Extract key differences
            for diff in event_data["differences"][:3]:
                if "interpretation" in diff:
                    key_differences.append(diff["interpretation"])

        except Exception as e:
            error_msg = f"Event comparison JQL failed: {e}"
            errors.append(error_msg)
            comparisons["event_frequency"] = {"error": error_msg}

    # JQL call 2: User/retention comparison
    if "retention" in compare_dimensions:
        try:
            jql_script = _build_user_comparison_jql(cohort_a_filter, cohort_b_filter)
            jql_result = ws.jql(
                script=jql_script,
                params={"from_date": from_date, "to_date": to_date},
            )

            # Parse results - JQLResult has a .raw property
            if hasattr(jql_result, "raw"):
                results_list = jql_result.raw
            elif isinstance(jql_result, list):
                results_list = jql_result
            else:
                results_list = []

            user_data = _parse_user_comparison_results(results_list)

            comparisons["retention"] = {
                "cohort_a_users": user_data["cohort_a_users"],
                "cohort_b_users": user_data["cohort_b_users"],
                "user_ratio": user_data["user_ratio"],
                "note": "User counts as retention proxy (unique users in period)",
            }

            # Add to key differences
            if user_data["cohort_a_users"] > 0 and user_data["cohort_b_users"] > 0:
                ratio = user_data["user_ratio"]
                if ratio > 1.2:
                    key_differences.append(
                        f"{cohort_a_name} has {ratio:.1f}x more unique users"
                    )
                elif ratio < 0.8:
                    key_differences.append(
                        f"{cohort_b_name} has {1/ratio:.1f}x more unique users"
                    )

        except Exception as e:
            error_msg = f"User comparison JQL failed: {e}"
            errors.append(error_msg)
            comparisons["retention"] = {"error": error_msg}

    # Update cohort metrics
    if "event_frequency" in comparisons and "error" not in comparisons["event_frequency"]:
        cohort_a.metrics["event_frequency"] = comparisons["event_frequency"].get(
            "cohort_a_frequency", {}
        )
        cohort_b.metrics["event_frequency"] = comparisons["event_frequency"].get(
            "cohort_b_frequency", {}
        )

    if "top_events" in comparisons:
        cohort_a.metrics["top_events"] = comparisons["top_events"].get(
            "cohort_a_top_events", []
        )
        cohort_b.metrics["top_events"] = comparisons["top_events"].get(
            "cohort_b_top_events", []
        )

    if "retention" in comparisons and "error" not in comparisons["retention"]:
        cohort_a.metrics["users"] = comparisons["retention"].get("cohort_a_users", 0)
        cohort_b.metrics["users"] = comparisons["retention"].get("cohort_b_users", 0)

    # Build result
    result = CohortComparison(
        cohort_a=cohort_a,
        cohort_b=cohort_b,
        period={"from_date": from_date, "to_date": to_date},
        comparisons=comparisons,
        statistical_significance=None,  # Could add if needed
    )

    result_dict = asdict(result)
    result_dict["key_differences"] = key_differences
    result_dict["api_calls_used"] = 2  # JQL is efficient!

    if errors:
        result_dict["errors"] = errors

    return result_dict
