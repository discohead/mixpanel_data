"""Funnel optimization report tool with AI synthesis.

This module provides the funnel_optimization_report tool that analyzes
funnel performance, identifies bottlenecks, and generates recommendations.

Uses ctx.sample() for LLM synthesis with graceful degradation when
sampling is unavailable.

Example:
    Ask Claude: "Analyze my signup funnel for optimization opportunities"
    Claude uses: funnel_optimization_report(funnel_id=123)
"""

import json
from dataclasses import asdict
from datetime import datetime, timedelta
from typing import Any

from fastmcp import Context

from mp_mcp.context import get_workspace
from mp_mcp.errors import handle_errors
from mp_mcp.server import mcp
from mp_mcp.types import FunnelOptimizationResult, OptimizationRecommendation

# Synthesis prompt template for funnel optimization
FUNNEL_OPTIMIZATION_PROMPT = """You are a conversion rate optimization expert analyzing a funnel.

## Funnel Analysis Data
{funnel_data}

## Segment Performance
{segment_data}

## Your Task
Analyze this funnel data and provide:

1. **Executive Summary** (2-3 sentences): Key findings about funnel performance

2. **Bottleneck Analysis**: Identify the step with the highest drop-off and explain why it might be underperforming

3. **Recommendations** (3-5 items): Prioritized actions to improve conversion, formatted as:
   - action: What to do
   - priority: high/medium/low
   - expected_impact: Expected improvement percentage or description

Return your analysis as JSON:
{{
    "executive_summary": "...",
    "bottleneck_analysis": "...",
    "recommendations": [
        {{"action": "...", "priority": "high|medium|low", "expected_impact": "..."}}
    ]
}}
"""

# Analysis hints for graceful degradation
ANALYSIS_HINTS: list[str] = [
    "Focus on the step with the highest drop-off percentage",
    "Compare conversion rates across different user segments",
    "Look for patterns in which segments convert better",
    "Consider the time between steps as a friction indicator",
    "Analyze the overall conversion rate vs. industry benchmarks",
]


def _get_default_date_range(days_back: int = 30) -> tuple[str, str]:
    """Get default date range for funnel analysis.

    Args:
        days_back: Number of days to look back.

    Returns:
        Tuple of (from_date, to_date) as strings.
    """
    today = datetime.now().date()
    from_date = (today - timedelta(days=days_back)).isoformat()
    to_date = today.isoformat()
    return from_date, to_date


def analyze_funnel_steps(
    ctx: Context,
    funnel_id: int,
    from_date: str,
    to_date: str,
) -> dict[str, Any]:
    """Analyze funnel step performance and identify bottleneck.

    Retrieves funnel data and calculates conversion rates between steps.

    Args:
        ctx: FastMCP context with workspace access.
        funnel_id: ID of the saved funnel to analyze.
        from_date: Start date for analysis.
        to_date: End date for analysis.

    Returns:
        Dictionary with funnel analysis including:
        - steps: List of step data with counts and conversion rates
        - overall_conversion: End-to-end conversion rate
        - bottleneck: Step with highest drop-off
    """
    ws = get_workspace(ctx)

    # Get funnel data
    result = ws.funnel(
        funnel_id=funnel_id,
        from_date=from_date,
        to_date=to_date,
    )
    data = result.to_dict()

    # Process funnel data
    steps: list[dict[str, Any]] = []
    bottleneck: dict[str, Any] = {}
    max_drop = 0.0
    overall_conversion = 0.0

    # Parse the funnel response
    if "data" in data:
        funnel_data = data["data"]

        # Handle different response formats
        if isinstance(funnel_data, dict):
            # Extract step counts
            step_counts: list[int] = []

            if "steps" in funnel_data:
                for i, step in enumerate(funnel_data["steps"]):
                    count = step.get("count", 0)
                    name = step.get("event", f"Step {i + 1}")
                    step_counts.append(count)

                    steps.append(
                        {
                            "step_number": i + 1,
                            "step_name": name,
                            "count": count,
                        }
                    )
            elif "analysis" in funnel_data:
                # Alternative format
                analysis = funnel_data["analysis"]
                if isinstance(analysis, dict) and "steps" in analysis:
                    for i, step in enumerate(analysis["steps"]):
                        count = step.get("count", 0)
                        name = step.get("event", f"Step {i + 1}")
                        step_counts.append(count)
                        steps.append(
                            {
                                "step_number": i + 1,
                                "step_name": name,
                                "count": count,
                            }
                        )

            # Calculate conversion rates and find bottleneck
            if step_counts:
                first_step = step_counts[0] if step_counts[0] > 0 else 1
                last_step = step_counts[-1] if len(step_counts) > 1 else step_counts[0]
                overall_conversion = last_step / first_step if first_step > 0 else 0.0

                for i, step in enumerate(steps):
                    if i > 0:
                        prev_count = steps[i - 1]["count"]
                        curr_count = step["count"]

                        if prev_count > 0:
                            conversion = curr_count / prev_count
                            drop_pct = 1 - conversion
                            step["conversion_from_prev"] = conversion
                            step["drop_percentage"] = drop_pct

                            if drop_pct > max_drop:
                                max_drop = drop_pct
                                bottleneck = {
                                    "step_number": step["step_number"],
                                    "step_name": step["step_name"],
                                    "drop_percentage": drop_pct,
                                    "users_lost": prev_count - curr_count,
                                }

    return {
        "steps": steps,
        "overall_conversion": overall_conversion,
        "bottleneck": bottleneck,
        "raw_data": data,
    }


def segment_funnel_performance(
    ctx: Context,
    funnel_id: int,
    from_date: str,
    to_date: str,
    segment_properties: list[str] | None = None,
) -> dict[str, Any]:
    """Analyze funnel performance across different segments.

    Breaks down funnel conversion by user properties to identify
    high and low performing segments.

    Args:
        ctx: FastMCP context with workspace access.
        funnel_id: ID of the saved funnel to analyze.
        from_date: Start date for analysis.
        to_date: End date for analysis.
        segment_properties: Properties to segment by (default: browser, os).

    Returns:
        Dictionary with segment analysis including:
        - top_segments: Segments with highest conversion
        - underperforming_segments: Segments with lowest conversion
    """
    ws = get_workspace(ctx)

    if segment_properties is None:
        segment_properties = ["$browser", "$os"]

    top_segments: list[dict[str, Any]] = []
    underperforming_segments: list[dict[str, Any]] = []

    for prop in segment_properties:
        try:
            # Get funnel data segmented by property
            result = ws.funnel(
                funnel_id=funnel_id,
                from_date=from_date,
                to_date=to_date,
                on=f'properties["{prop}"]',
            )
            data = result.to_dict()

            # Parse segment data
            if "data" in data and isinstance(data["data"], dict):
                segments = data["data"]

                segment_conversions: list[dict[str, Any]] = []

                for segment_name, segment_data in segments.items():
                    if isinstance(segment_data, dict) and "steps" in segment_data:
                        steps = segment_data["steps"]
                        if len(steps) >= 2:
                            first = steps[0].get("count", 0)
                            last = steps[-1].get("count", 0)
                            conversion = last / first if first > 0 else 0

                            segment_conversions.append(
                                {
                                    "segment": segment_name,
                                    "property": prop,
                                    "conversion_rate": conversion,
                                    "sample_size": first,
                                }
                            )

                # Sort by conversion rate
                segment_conversions.sort(
                    key=lambda x: x["conversion_rate"], reverse=True
                )

                # Get top 3 and bottom 3
                if segment_conversions:
                    for seg in segment_conversions[:3]:
                        if seg["sample_size"] > 10:  # Minimum sample size
                            top_segments.append(seg)

                    for seg in segment_conversions[-3:]:
                        if seg["sample_size"] > 10:
                            underperforming_segments.append(seg)

        except Exception:
            # Continue with other properties if one fails
            continue

    # Sort final lists
    top_segments.sort(key=lambda x: x["conversion_rate"], reverse=True)
    underperforming_segments.sort(key=lambda x: x["conversion_rate"])

    return {
        "top_segments": top_segments[:5],
        "underperforming_segments": underperforming_segments[:5],
    }


def _generate_default_recommendations(
    bottleneck: dict[str, Any],
    top_segments: list[dict[str, Any]],
    underperforming_segments: list[dict[str, Any]],
) -> list[OptimizationRecommendation]:
    """Generate default recommendations without LLM synthesis.

    Creates actionable recommendations based on the data patterns.

    Args:
        bottleneck: The identified bottleneck step.
        top_segments: Best performing segments.
        underperforming_segments: Worst performing segments.

    Returns:
        List of OptimizationRecommendation objects.
    """
    recommendations: list[OptimizationRecommendation] = []

    # Bottleneck recommendation
    if bottleneck:
        step_name = bottleneck.get("step_name", "unknown step")
        drop_pct = bottleneck.get("drop_percentage", 0)
        recommendations.append(
            OptimizationRecommendation(
                action=f"Investigate and optimize '{step_name}' step "
                f"(current drop-off: {drop_pct:.1%})",
                priority="high",
                expected_impact=f"Reducing drop-off by 20% could increase "
                f"overall conversion by {drop_pct * 0.2:.1%}",
            )
        )

    # Segment-based recommendations
    if top_segments and underperforming_segments:
        top_seg = top_segments[0]
        low_seg = underperforming_segments[0]

        recommendations.append(
            OptimizationRecommendation(
                action=f"Study why {top_seg['segment']} ({top_seg['property']}) "
                f"converts at {top_seg['conversion_rate']:.1%} and apply learnings",
                priority="high",
                expected_impact="Apply successful patterns to other segments",
            )
        )

        recommendations.append(
            OptimizationRecommendation(
                action=f"Investigate why {low_seg['segment']} ({low_seg['property']}) "
                f"underperforms ({low_seg['conversion_rate']:.1%})",
                priority="medium",
                expected_impact="May reveal UX or technical issues affecting this segment",
            )
        )

    # Generic recommendations
    recommendations.extend(
        [
            OptimizationRecommendation(
                action="Add urgency or scarcity elements to encourage completion",
                priority="medium",
                expected_impact="Typically improves conversion by 5-15%",
            ),
            OptimizationRecommendation(
                action="Implement exit-intent surveys to understand abandonment",
                priority="low",
                expected_impact="Provides qualitative insights for optimization",
            ),
        ]
    )

    return recommendations[:5]  # Return top 5 recommendations


@mcp.tool
@handle_errors
async def funnel_optimization_report(
    ctx: Context,
    funnel_id: int,
    from_date: str | None = None,
    to_date: str | None = None,
    segment_properties: list[str] | None = None,
) -> dict[str, Any]:
    """Generate comprehensive funnel optimization report.

    Analyzes funnel performance, identifies bottlenecks, compares
    segment performance, and generates prioritized recommendations.

    Uses LLM synthesis for insights when available; provides structured
    analysis with default recommendations when sampling is unavailable.

    Args:
        ctx: FastMCP context with workspace access.
        funnel_id: ID of the saved funnel to analyze.
        from_date: Start date for analysis (YYYY-MM-DD).
            Defaults to 30 days ago.
        to_date: End date for analysis (YYYY-MM-DD).
            Defaults to today.
        segment_properties: Properties to segment by (e.g., ["$browser", "$os"]).
            Defaults to browser and OS.

    Returns:
        Dictionary containing:
        - status: "success" or "partial" (if synthesis unavailable)
        - executive_summary: Key findings summary
        - overall_conversion_rate: End-to-end conversion
        - bottleneck: Details of worst-performing step
        - top_performing_segments: Best converting segments
        - underperforming_segments: Worst converting segments
        - recommendations: Prioritized optimization actions
        - raw_data: Underlying funnel and segment data
        - analysis_hints: Manual analysis guidance (if synthesis unavailable)

    Example:
        Ask: "Analyze my signup funnel"
        Uses: funnel_optimization_report(funnel_id=123)

        Ask: "Optimize checkout funnel by device"
        Uses: funnel_optimization_report(
            funnel_id=456,
            segment_properties=["$device_type"],
        )
    """
    # Set default date range
    if not from_date or not to_date:
        from_date, to_date = _get_default_date_range()

    # Step 1: Analyze funnel steps
    funnel_analysis = analyze_funnel_steps(ctx, funnel_id, from_date, to_date)

    # Step 2: Segment performance analysis
    segment_analysis = segment_funnel_performance(
        ctx, funnel_id, from_date, to_date, segment_properties
    )

    # Combine data for synthesis
    overall_conversion = funnel_analysis.get("overall_conversion", 0.0)
    bottleneck = funnel_analysis.get("bottleneck", {})
    top_segments = segment_analysis.get("top_segments", [])
    underperforming_segments = segment_analysis.get("underperforming_segments", [])

    # Try LLM synthesis
    try:
        synthesis_prompt = FUNNEL_OPTIMIZATION_PROMPT.format(
            funnel_data=json.dumps(funnel_analysis, indent=2),
            segment_data=json.dumps(segment_analysis, indent=2),
        )

        synthesis = await ctx.sample(
            synthesis_prompt,
            system_prompt="You are a conversion optimization expert. Provide actionable insights.",
            max_tokens=1500,
        )

        # Parse synthesis result
        if synthesis.text is None:
            raise ValueError("LLM returned empty response")
        text = synthesis.text.strip()
        if "```json" in text:
            start = text.index("```json") + 7
            end = text.index("```", start)
            text = text[start:end].strip()
        elif "```" in text:
            start = text.index("```") + 3
            end = text.index("```", start)
            text = text[start:end].strip()

        synth_data = json.loads(text)

        # Build recommendations from synthesis
        recommendations: list[OptimizationRecommendation] = []
        for rec in synth_data.get("recommendations", []):
            recommendations.append(
                OptimizationRecommendation(
                    action=rec.get("action", ""),
                    priority=rec.get("priority", "medium"),
                    expected_impact=rec.get("expected_impact", ""),
                )
            )

        result = FunnelOptimizationResult(
            executive_summary=synth_data.get("executive_summary", ""),
            overall_conversion_rate=overall_conversion,
            bottleneck=bottleneck,
            top_performing_segments=top_segments,
            underperforming_segments=underperforming_segments,
            recommendations=recommendations,
            raw_data={
                "funnel_analysis": funnel_analysis,
                "segment_analysis": segment_analysis,
            },
        )

        return {
            "status": "success",
            **asdict(result),
        }

    except Exception as e:
        # Graceful degradation - provide analysis without LLM
        error_msg = str(e)

        # Generate default recommendations
        recommendations = _generate_default_recommendations(
            bottleneck, top_segments, underperforming_segments
        )

        # Generate default summary
        if bottleneck:
            summary = (
                f"Funnel converts at {overall_conversion:.1%}. "
                f"Main bottleneck at '{bottleneck.get('step_name', 'unknown')}' "
                f"with {bottleneck.get('drop_percentage', 0):.1%} drop-off."
            )
        else:
            summary = f"Funnel converts at {overall_conversion:.1%}."

        result = FunnelOptimizationResult(
            executive_summary=summary,
            overall_conversion_rate=overall_conversion,
            bottleneck=bottleneck,
            top_performing_segments=top_segments,
            underperforming_segments=underperforming_segments,
            recommendations=recommendations,
            raw_data={
                "funnel_analysis": funnel_analysis,
                "segment_analysis": segment_analysis,
            },
        )

        status = "partial"
        if "sampling" in error_msg.lower() or "not supported" in error_msg.lower():
            status_msg = "Client does not support sampling for synthesis."
        else:
            status_msg = f"Synthesis failed: {error_msg}"

        return {
            "status": status,
            "message": status_msg,
            **asdict(result),
            "analysis_hints": ANALYSIS_HINTS,
        }
