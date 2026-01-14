"""Diagnose metric drop tool with AI synthesis.

This module provides the diagnose_metric_drop tool that analyzes
metric drops by comparing baseline vs current periods and identifying
contributing segments.

Uses ctx.sample() for LLM synthesis with graceful degradation when
sampling is unavailable.

Example:
    Ask Claude: "Why did signups drop on January 7th?"
    Claude uses: diagnose_metric_drop(event="signup", date="2026-01-07")
"""

import json
from dataclasses import asdict
from datetime import datetime, timedelta
from typing import Any

from fastmcp import Context

from mp_mcp_server.context import get_workspace
from mp_mcp_server.errors import handle_errors
from mp_mcp_server.server import mcp
from mp_mcp_server.types import DiagnosisResult, SegmentContribution

# Default dimensions to analyze for segment contributions
DEFAULT_DIMENSIONS: list[str] = [
    "$browser",
    "$os",
    "$city",
    "$region",
    "mp_country_code",
    "mp_lib",
    "$device",
]

# Synthesis prompt template
DIAGNOSIS_PROMPT_TEMPLATE = """You are a Mixpanel analytics expert analyzing a metric drop.

## Event Being Analyzed
{event}

## Date of Observed Drop
{date}

## Baseline Period Data (7 days before)
{baseline_data}

## Drop Period Data (the day of the drop)
{drop_data}

## Segment Analysis (breakdown by dimensions)
{segment_data}

## Your Task
Analyze this data and provide:
1. Confirm whether there is a significant drop (>10% decrease)
2. Calculate the exact drop percentage
3. Identify the PRIMARY driver (which segment contributed most to the drop)
4. List any SECONDARY factors (other segments showing decline)
5. Provide 2-3 actionable RECOMMENDATIONS for investigation
6. Assess your CONFIDENCE level (low/medium/high) based on data quality
7. Note any CAVEATS about the data or analysis

Respond in JSON format matching this structure:
{{
    "drop_confirmed": true/false,
    "drop_percentage": -25.5,
    "primary_driver": {{
        "dimension": "platform",
        "segment": "iOS",
        "contribution_pct": 65.0,
        "baseline_value": 1000,
        "current_value": 650,
        "description": "iOS users dropped by 35%, accounting for 65% of total drop"
    }},
    "secondary_factors": [...],
    "recommendations": ["Check iOS app store reviews", "..."],
    "confidence": "high",
    "caveats": ["Limited data for some segments"]
}}
"""

# Analysis hints for graceful degradation
ANALYSIS_HINTS: list[str] = [
    "Compare baseline total vs drop period total to calculate percentage change",
    "Look for segments with largest absolute decreases",
    "Check if any single dimension accounts for >50% of the drop",
    "Consider external factors (holidays, app updates, marketing changes)",
    "Look at the segment breakdown to identify patterns",
    "A segment's contribution = (baseline - current) / total_drop * 100",
]


def _calculate_date_range(date: str, days_before: int = 7) -> tuple[str, str]:
    """Calculate a date range for baseline comparison.

    Args:
        date: The target date (YYYY-MM-DD format).
        days_before: Number of days before the target date for baseline.

    Returns:
        Tuple of (from_date, to_date) as strings.
    """
    target = datetime.strptime(date, "%Y-%m-%d").date()
    from_date = target - timedelta(days=days_before)
    to_date = target - timedelta(days=1)  # Day before the drop
    return from_date.isoformat(), to_date.isoformat()


def _gather_diagnosis_data(
    ctx: Context,
    event: str,
    date: str,
    dimensions: list[str] | None = None,
) -> dict[str, Any]:
    """Gather data for metric drop diagnosis.

    Executes baseline comparison and segment analysis queries.

    Args:
        ctx: FastMCP context with workspace access.
        event: Event name to analyze.
        date: Date of the observed drop (YYYY-MM-DD).
        dimensions: Property dimensions to analyze for segment breakdown.

    Returns:
        Dictionary containing baseline_data, drop_data, and segment_data.
    """
    ws = get_workspace(ctx)
    dims = dimensions or DEFAULT_DIMENSIONS

    # Calculate baseline period (7 days before the drop)
    baseline_from, baseline_to = _calculate_date_range(date, days_before=7)

    # Get baseline segmentation data
    try:
        baseline_result = ws.segmentation(
            event=event,
            from_date=baseline_from,
            to_date=baseline_to,
            unit="day",
        )
        baseline_data = baseline_result.to_dict()
    except Exception as e:
        baseline_data = {"error": str(e)}

    # Get drop day segmentation data
    try:
        drop_result = ws.segmentation(
            event=event,
            from_date=date,
            to_date=date,
            unit="day",
        )
        drop_data = drop_result.to_dict()
    except Exception as e:
        drop_data = {"error": str(e)}

    # Get segment breakdown for each dimension
    segment_data: dict[str, Any] = {}
    for dim in dims:
        try:
            # Baseline segment data
            baseline_seg = ws.property_counts(
                event=event,
                property_name=dim,
                from_date=baseline_from,
                to_date=baseline_to,
                type="general",
                limit=10,
            )
            # Drop period segment data
            drop_seg = ws.property_counts(
                event=event,
                property_name=dim,
                from_date=date,
                to_date=date,
                type="general",
                limit=10,
            )
            segment_data[dim] = {
                "baseline": baseline_seg.to_dict(),
                "drop_period": drop_seg.to_dict(),
            }
        except Exception:
            # Skip dimensions that fail (property might not exist)
            continue

    return {
        "baseline_data": baseline_data,
        "drop_data": drop_data,
        "segment_data": segment_data,
        "baseline_period": {"from": baseline_from, "to": baseline_to},
        "drop_period": {"from": date, "to": date},
    }


def _build_synthesis_prompt(
    event: str,
    date: str,
    raw_data: dict[str, Any],
) -> str:
    """Build the synthesis prompt from raw data.

    Args:
        event: Event name being analyzed.
        date: Date of the observed drop.
        raw_data: Raw data from _gather_diagnosis_data.

    Returns:
        Formatted prompt string for LLM synthesis.
    """
    return DIAGNOSIS_PROMPT_TEMPLATE.format(
        event=event,
        date=date,
        baseline_data=json.dumps(raw_data.get("baseline_data", {}), indent=2),
        drop_data=json.dumps(raw_data.get("drop_data", {}), indent=2),
        segment_data=json.dumps(raw_data.get("segment_data", {}), indent=2),
    )


def _parse_synthesis_result(synthesis_text: str) -> DiagnosisResult:
    """Parse LLM synthesis result into DiagnosisResult.

    Args:
        synthesis_text: Raw text from LLM synthesis.

    Returns:
        Parsed DiagnosisResult dataclass.

    Raises:
        ValueError: If parsing fails.
    """
    # Try to extract JSON from the response
    text = synthesis_text.strip()

    # Handle markdown code blocks
    if "```json" in text:
        start = text.index("```json") + 7
        end = text.index("```", start)
        text = text[start:end].strip()
    elif "```" in text:
        start = text.index("```") + 3
        end = text.index("```", start)
        text = text[start:end].strip()

    data = json.loads(text)

    # Parse primary driver if present
    primary_driver = None
    if data.get("primary_driver"):
        pd = data["primary_driver"]
        primary_driver = SegmentContribution(
            dimension=pd.get("dimension", "unknown"),
            segment=pd.get("segment", "unknown"),
            contribution_pct=float(pd.get("contribution_pct", 0)),
            baseline_value=float(pd.get("baseline_value", 0)),
            current_value=float(pd.get("current_value", 0)),
            description=pd.get("description", ""),
        )

    # Parse secondary factors
    secondary_factors: list[SegmentContribution] = []
    for sf in data.get("secondary_factors", []):
        secondary_factors.append(
            SegmentContribution(
                dimension=sf.get("dimension", "unknown"),
                segment=sf.get("segment", "unknown"),
                contribution_pct=float(sf.get("contribution_pct", 0)),
                baseline_value=float(sf.get("baseline_value", 0)),
                current_value=float(sf.get("current_value", 0)),
                description=sf.get("description", ""),
            )
        )

    return DiagnosisResult(
        drop_confirmed=data.get("drop_confirmed", False),
        drop_percentage=float(data.get("drop_percentage", 0)),
        primary_driver=primary_driver,
        secondary_factors=secondary_factors,
        recommendations=data.get("recommendations", []),
        confidence=data.get("confidence", "medium"),
        caveats=data.get("caveats", []),
    )


@mcp.tool
@handle_errors
async def diagnose_metric_drop(
    ctx: Context,
    event: str,
    date: str,
    dimensions: list[str] | None = None,
) -> dict[str, Any]:
    """Diagnose a metric drop with AI-powered analysis.

    Analyzes a metric drop by comparing baseline (7 days before) to the
    drop period, identifying contributing segments, and synthesizing
    findings with recommendations.

    Uses LLM sampling for synthesis when available; gracefully degrades
    to raw data with analysis hints when sampling is unavailable.

    Args:
        ctx: FastMCP context with workspace access.
        event: Event name to analyze (e.g., "signup", "login").
        date: Date of the observed drop (YYYY-MM-DD format).
        dimensions: Optional list of property dimensions to analyze.
            Defaults to common dimensions like $browser, $os, etc.

    Returns:
        Dictionary containing:
        - status: "success", "partial", or "sampling_unavailable"
        - findings: Structured diagnosis result (when sampling available)
        - raw_data: Underlying query results for transparency
        - analysis_hints: Manual analysis guidance (when sampling unavailable)

    Example:
        Ask: "Why did signups drop on January 7th?"
        Uses: diagnose_metric_drop(event="signup", date="2026-01-07")

        Ask: "Analyze the login drop by browser and country"
        Uses: diagnose_metric_drop(
            event="login",
            date="2026-01-10",
            dimensions=["$browser", "mp_country_code"],
        )
    """
    # Step 1: Gather data (always succeeds)
    raw_data = _gather_diagnosis_data(ctx, event, date, dimensions)

    # Step 2: Try sampling for synthesis
    try:
        prompt = _build_synthesis_prompt(event, date, raw_data)

        synthesis = await ctx.sample(
            prompt,
            system_prompt="You are a Mixpanel analytics expert. Analyze the data and respond with valid JSON only.",
            max_tokens=2000,
        )

        # Step 3: Parse the synthesis result
        try:
            if synthesis.text is None:
                raise ValueError("LLM returned empty response")
            diagnosis = _parse_synthesis_result(synthesis.text)
            diagnosis.raw_data = raw_data

            return {
                "status": "success",
                "findings": asdict(diagnosis),
                "raw_data": raw_data,
            }
        except (json.JSONDecodeError, ValueError, KeyError) as e:
            # Parsing failed, but we have synthesis text
            return {
                "status": "partial",
                "message": f"Synthesis completed but parsing failed: {e}",
                "synthesis_text": synthesis.text,
                "raw_data": raw_data,
                "analysis_hints": ANALYSIS_HINTS,
            }

    except Exception as e:
        # Step 4: Graceful degradation when sampling unavailable
        error_msg = str(e)
        if "sampling" in error_msg.lower() or "not supported" in error_msg.lower():
            status_msg = "Client does not support sampling. Returning raw data."
        else:
            status_msg = f"Synthesis failed: {error_msg}. Returning raw data."

        return {
            "status": "sampling_unavailable",
            "message": status_msg,
            "raw_data": raw_data,
            "analysis_hints": ANALYSIS_HINTS,
        }
