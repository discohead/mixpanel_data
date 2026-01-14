# MCP Server v2: Advanced Capabilities Implementation Plan

## Executive Summary

This document defines the next generation of `mp-mcp-server` enhancements, transforming it from a thin API wrapper into an **intelligent analytics platform**. The key insight driving this evolution comes from Notion's MCP server: instead of exposing raw primitives, expose **higher-order abstractions** that compose multiple operations into single, meaningful workflows.

### Vision

> **Don't expose Mixpanel's API—expose analytics intelligence.**

Current state: 27 tools that map 1:1 to `Workspace` methods.

Target state: A tiered capability model where:
- **Tier 1 (Primitives)**: Existing 27 tools remain unchanged
- **Tier 2 (Composed)**: Higher-order tools that orchestrate multiple primitives
- **Tier 3 (Intelligent)**: Sampling-powered tools that synthesize and recommend

### Core MCP Features to Leverage

| Feature | Status | Enhancement Opportunity |
|---------|--------|-------------------------|
| **Tools** | Implemented (27) | Add composed tools, NL interface |
| **Resources** | Implemented (6) | Add dynamic templates, cached views |
| **Prompts** | Implemented (4) | Add framework-embedded expertise |
| **Sampling** | Not used | Server requests LLM analysis of results |
| **Elicitation** | Not used | Interactive workflows with user input |
| **Tasks** | Not used | Progress reporting for long-running operations |
| **Middleware** | Not used | Caching, rate limiting, audit logging |

---

## Architecture Evolution

### Current Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      MCP Client                              │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    mp-mcp-server                             │
│  ┌───────────────────────────────────────────────────────┐  │
│  │ Tools (27)  │  Resources (6)  │  Prompts (4)          │  │
│  └───────────────────────────────────────────────────────┘  │
│                              │                               │
│                              ▼                               │
│  ┌───────────────────────────────────────────────────────┐  │
│  │              mixpanel_data.Workspace                   │  │
│  └───────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

### Target Architecture (v2)

```
┌─────────────────────────────────────────────────────────────┐
│                      MCP Client                              │
└─────────────────────────────────────────────────────────────┘
         │                    │                    │
         ▼                    ▼                    ▼
┌─────────────┐      ┌─────────────┐      ┌─────────────┐
│  Sampling   │      │ Elicitation │      │   Tools     │
│  (LLM call) │      │ (User input)│      │  (Actions)  │
└──────┬──────┘      └──────┬──────┘      └──────┬──────┘
       │                    │                    │
       └────────────────────┼────────────────────┘
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                    mp-mcp-server v2                          │
│  ┌───────────────────────────────────────────────────────┐  │
│  │                    Middleware Layer                    │  │
│  │  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌──────────┐  │  │
│  │  │ Caching │  │  Rate   │  │  Audit  │  │ Progress │  │  │
│  │  │         │  │ Limiting│  │ Logging │  │ Tracking │  │  │
│  │  └─────────┘  └─────────┘  └─────────┘  └──────────┘  │  │
│  └───────────────────────────────────────────────────────┘  │
│                              │                               │
│  ┌───────────────────────────────────────────────────────┐  │
│  │               Tier 3: Intelligent Tools                │  │
│  │  ┌─────────────────┐  ┌─────────────────────────────┐  │  │
│  │  │ diagnose_drop   │  │ ask_mixpanel (NL interface) │  │  │
│  │  │ (uses sampling) │  │ (uses sampling)             │  │  │
│  │  └─────────────────┘  └─────────────────────────────┘  │  │
│  └───────────────────────────────────────────────────────┘  │
│                              │                               │
│  ┌───────────────────────────────────────────────────────┐  │
│  │               Tier 2: Composed Tools                   │  │
│  │  ┌──────────────┐  ┌──────────────┐  ┌─────────────┐  │  │
│  │  │ funnel_      │  │ retention_   │  │ cohort_     │  │  │
│  │  │ optimization │  │ benchmark    │  │ comparison  │  │  │
│  │  └──────────────┘  └──────────────┘  └─────────────┘  │  │
│  └───────────────────────────────────────────────────────┘  │
│                              │                               │
│  ┌───────────────────────────────────────────────────────┐  │
│  │               Tier 1: Primitive Tools (27)             │  │
│  │  Discovery │ Live Query │ Fetch │ Local SQL            │  │
│  └───────────────────────────────────────────────────────┘  │
│                              │                               │
│  ┌───────────────────────────────────────────────────────┐  │
│  │          Enhanced Resources & Prompts                  │  │
│  │  ┌───────────────┐  ┌────────────────────────────────┐ │  │
│  │  │ Dynamic       │  │ Framework-Embedded Prompts     │ │  │
│  │  │ Templates     │  │ (AARRR, GQM, Benchmarks)       │ │  │
│  │  └───────────────┘  └────────────────────────────────┘ │  │
│  └───────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│              mixpanel_data.Workspace                         │
└─────────────────────────────────────────────────────────────┘
```

---

## Phase 1: Sampling-Powered Intelligent Tools

### 1.1 Overview

FastMCP's `ctx.sample()` enables the server to request LLM completions from the client. This transforms tools from data-fetchers into **analytical agents** that can:

1. Execute multiple queries
2. Synthesize results
3. Generate recommendations
4. Explain findings

### 1.2 Tool: `diagnose_metric_drop`

**Purpose**: Complete root cause analysis of a metric decline in one tool call.

**Workflow**:
```
User asks: "Why did signups drop on Tuesday?"
                    │
                    ▼
┌─────────────────────────────────────────────────────────────┐
│ Step 1: Confirm the Drop                                     │
│ - segmentation(signup, baseline_period)                      │
│ - segmentation(signup, current_period)                       │
│ - Calculate percentage change                                │
└─────────────────────────────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────────────────────┐
│ Step 2: Segment by Key Dimensions                            │
│ - property_counts(signup, platform, period)                  │
│ - property_counts(signup, country, period)                   │
│ - property_counts(signup, source, period)                    │
│ - property_counts(signup, device_type, period)               │
└─────────────────────────────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────────────────────┐
│ Step 3: Identify Anomalous Segment                           │
│ - Compare each dimension's before/after                      │
│ - Find largest contributing decline                          │
└─────────────────────────────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────────────────────┐
│ Step 4: Use Sampling for Synthesis                           │
│ - ctx.sample() with all data                                 │
│ - Ask LLM to identify root cause                             │
│ - Generate actionable recommendations                        │
└─────────────────────────────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────────────────────┐
│ Return: Structured Analysis Report                           │
│ - drop_confirmed: bool                                       │
│ - drop_percentage: float                                     │
│ - primary_driver: {dimension, segment, contribution}         │
│ - secondary_factors: [...]                                   │
│ - recommendations: [...]                                     │
│ - raw_data: {baseline, current, segments}                    │
└─────────────────────────────────────────────────────────────┘
```

**Implementation**:

```python
from fastmcp import Context
from mp_mcp_server.server import mcp
from mp_mcp_server.context import get_workspace
from datetime import datetime, timedelta
import json

@mcp.tool
async def diagnose_metric_drop(
    event: str,
    date: str,
    comparison_days: int = 7,
    dimensions: list[str] | None = None,
    ctx: Context,
) -> dict:
    """Diagnose why a metric dropped on a specific date.

    Performs comprehensive root cause analysis by:
    1. Confirming the drop magnitude
    2. Segmenting by key dimensions to find drivers
    3. Using AI to synthesize findings and recommend actions

    Args:
        event: Event name to analyze (e.g., "signup", "purchase").
        date: Date when drop occurred (YYYY-MM-DD).
        comparison_days: Days before drop to use as baseline (default 7).
        dimensions: Properties to segment by (default: platform, country, source).

    Returns:
        Structured analysis with:
        - drop_confirmed: Whether drop is statistically significant
        - drop_percentage: Magnitude of decline
        - primary_driver: Main cause of drop
        - recommendations: Actionable next steps
        - raw_data: All underlying query results

    Example:
        diagnose_metric_drop("signup", "2024-01-15")
        → "Signups dropped 35% due to mobile iOS users from paid ads.
           Recommend checking mobile app store listing and ad creative."
    """
    ws = get_workspace(ctx)

    # Default dimensions based on common analytics patterns
    if dimensions is None:
        dimensions = ["platform", "country", "utm_source", "device_type"]

    # Parse dates
    drop_date = datetime.strptime(date, "%Y-%m-%d")
    baseline_start = (drop_date - timedelta(days=comparison_days)).strftime("%Y-%m-%d")
    baseline_end = (drop_date - timedelta(days=1)).strftime("%Y-%m-%d")

    # Step 1: Get baseline and current metrics
    baseline = ws.segmentation(
        event,
        from_date=baseline_start,
        to_date=baseline_end,
        unit="day"
    )
    current = ws.segmentation(
        event,
        from_date=date,
        to_date=date,
        unit="day"
    )

    baseline_avg = sum(baseline.series.get("", {}).values()) / comparison_days
    current_count = sum(current.series.get("", {}).values())
    drop_pct = ((baseline_avg - current_count) / baseline_avg) * 100 if baseline_avg > 0 else 0

    # Step 2: Segment by each dimension
    segment_data = {}
    for dim in dimensions:
        try:
            baseline_seg = ws.property_counts(
                event, dim,
                from_date=baseline_start,
                to_date=baseline_end
            )
            current_seg = ws.property_counts(
                event, dim,
                from_date=date,
                to_date=date
            )
            segment_data[dim] = {
                "baseline": baseline_seg.to_dict(),
                "current": current_seg.to_dict(),
            }
        except Exception:
            # Property may not exist
            continue

    # Step 3: Use sampling to synthesize
    analysis_prompt = f"""Analyze this metric drop and identify the root cause.

Event: {event}
Date of drop: {date}
Baseline period: {baseline_start} to {baseline_end}

Overall metrics:
- Baseline daily average: {baseline_avg:.1f}
- Drop day count: {current_count}
- Percentage change: {drop_pct:.1f}%

Segment breakdowns by dimension:
{json.dumps(segment_data, indent=2, default=str)}

Instructions:
1. Identify which segment(s) contributed most to the drop
2. Calculate each segment's contribution to the overall decline
3. Provide 2-3 specific, actionable recommendations
4. Note any data quality concerns or caveats

Format your response as JSON with these keys:
- drop_confirmed (bool): Is this a significant drop?
- drop_percentage (float): The percentage decline
- primary_driver (object): {{dimension, segment, contribution_pct, description}}
- secondary_factors (array): Other contributing factors
- recommendations (array): Actionable next steps
- confidence (string): low/medium/high
- caveats (array): Any data quality concerns
"""

    # Request LLM analysis via sampling
    synthesis = await ctx.sample(
        messages=[{"role": "user", "content": analysis_prompt}],
        max_tokens=1000,
    )

    # Parse LLM response (with fallback)
    try:
        analysis = json.loads(synthesis.text)
    except json.JSONDecodeError:
        analysis = {
            "drop_confirmed": drop_pct > 10,
            "drop_percentage": drop_pct,
            "synthesis": synthesis.text,
            "parse_error": "Could not parse structured response",
        }

    return {
        **analysis,
        "raw_data": {
            "baseline_avg": baseline_avg,
            "current_count": current_count,
            "baseline_period": {"start": baseline_start, "end": baseline_end},
            "segments": segment_data,
        },
    }
```

### 1.3 Tool: `funnel_optimization_report`

**Purpose**: Complete funnel analysis with actionable recommendations.

**Workflow**:
```
1. Run base funnel query
2. Identify worst-performing step
3. Segment that step by multiple dimensions
4. Calculate time-to-convert distribution
5. Use sampling to generate optimization recommendations
```

**Implementation**:

```python
@mcp.tool
async def funnel_optimization_report(
    funnel_id: int,
    from_date: str,
    to_date: str,
    segment_dimensions: list[str] | None = None,
    ctx: Context,
) -> dict:
    """Generate comprehensive funnel optimization report.

    Analyzes a conversion funnel to identify:
    - Overall conversion rates
    - Biggest drop-off points
    - Segment-level performance differences
    - Time-to-convert patterns
    - Actionable optimization recommendations

    Args:
        funnel_id: Saved funnel ID from Mixpanel.
        from_date: Analysis start date (YYYY-MM-DD).
        to_date: Analysis end date (YYYY-MM-DD).
        segment_dimensions: Properties to segment by.

    Returns:
        Comprehensive report with:
        - executive_summary: Key findings in 2-3 sentences
        - funnel_performance: Step-by-step conversion data
        - bottleneck_analysis: Details on worst-performing step
        - segment_insights: Performance by dimension
        - recommendations: Prioritized optimization actions

    Example:
        funnel_optimization_report(12345, "2024-01-01", "2024-01-31")
        → Complete analysis with "Focus on Step 2→3 where mobile users
           drop off at 2x the rate of desktop users."
    """
    ws = get_workspace(ctx)

    if segment_dimensions is None:
        segment_dimensions = ["platform", "country", "utm_source"]

    # Step 1: Base funnel
    base_funnel = ws.funnel(funnel_id, from_date=from_date, to_date=to_date)

    # Step 2: Identify worst step
    steps = base_funnel.steps
    worst_step_idx = 0
    worst_drop = 0
    for i in range(1, len(steps)):
        drop = steps[i-1].count - steps[i].count
        drop_pct = (drop / steps[i-1].count * 100) if steps[i-1].count > 0 else 0
        if drop_pct > worst_drop:
            worst_drop = drop_pct
            worst_step_idx = i

    # Step 3: Segment the bottleneck step
    segment_results = {}
    for dim in segment_dimensions:
        try:
            segmented = ws.funnel(
                funnel_id,
                from_date=from_date,
                to_date=to_date,
                on=f"properties['{dim}']"
            )
            segment_results[dim] = segmented.to_dict()
        except Exception:
            continue

    # Step 4: Use sampling for synthesis
    report_prompt = f"""Generate a funnel optimization report.

Funnel: {base_funnel.funnel_name} (ID: {funnel_id})
Period: {from_date} to {to_date}

Overall Funnel Performance:
{json.dumps(base_funnel.to_dict(), indent=2, default=str)}

Bottleneck identified at step {worst_step_idx + 1} with {worst_drop:.1f}% drop-off.

Segmented Results:
{json.dumps(segment_results, indent=2, default=str)}

Generate a report with:
1. Executive summary (2-3 sentences)
2. Key metrics (overall conversion, biggest drop-off)
3. Segment insights (which segments perform best/worst)
4. 3-5 prioritized recommendations with expected impact

Format as JSON with keys:
- executive_summary (string)
- overall_conversion_rate (float)
- bottleneck (object): {{step_number, step_name, drop_percentage}}
- top_performing_segments (array)
- underperforming_segments (array)
- recommendations (array of {{action, priority, expected_impact}})
"""

    synthesis = await ctx.sample(
        messages=[{"role": "user", "content": report_prompt}],
        max_tokens=1500,
    )

    try:
        report = json.loads(synthesis.text)
    except json.JSONDecodeError:
        report = {"synthesis": synthesis.text}

    return {
        **report,
        "raw_data": {
            "base_funnel": base_funnel.to_dict(),
            "segments": segment_results,
            "worst_step_index": worst_step_idx,
        },
    }
```

### 1.4 Tool: `ask_mixpanel` (Natural Language Interface)

**Purpose**: Answer any analytics question using natural language.

**Workflow**:
```
User: "Why do mobile users have lower retention?"
                    │
                    ▼
┌─────────────────────────────────────────────────────────────┐
│ Step 1: Parse Intent (via sampling)                          │
│ - Identify query type: retention analysis                    │
│ - Extract filters: platform = mobile                         │
│ - Determine comparison: mobile vs non-mobile                 │
└─────────────────────────────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────────────────────┐
│ Step 2: Generate Execution Plan                              │
│ - retention(born_event=signup, filter=mobile)                │
│ - retention(born_event=signup, filter=desktop)               │
│ - property_counts for feature usage comparison               │
└─────────────────────────────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────────────────────┐
│ Step 3: Execute Queries                                      │
│ - Run all queries from plan                                  │
│ - Collect results                                            │
└─────────────────────────────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────────────────────┐
│ Step 4: Synthesize Answer (via sampling)                     │
│ - Combine all data                                           │
│ - Generate human-readable answer                             │
│ - Include supporting evidence                                │
└─────────────────────────────────────────────────────────────┘
```

**Implementation**:

```python
@mcp.tool
async def ask_mixpanel(
    question: str,
    context: str | None = None,
    ctx: Context,
) -> dict:
    """Answer any analytics question using natural language.

    Interprets your question, executes appropriate queries,
    and synthesizes a comprehensive answer.

    Args:
        question: Natural language question about your data.
        context: Optional additional context about your product/metrics.

    Returns:
        - answer: Human-readable response to your question
        - confidence: How confident the analysis is (low/medium/high)
        - queries_executed: List of queries run to answer
        - supporting_data: Raw data supporting the answer
        - follow_up_suggestions: Related questions to explore

    Examples:
        ask_mixpanel("Why did signups drop last Tuesday?")
        ask_mixpanel("Which features correlate with higher retention?")
        ask_mixpanel("What's the typical user journey from signup to first purchase?")
    """
    ws = get_workspace(ctx)

    # Get available schema for context
    events = ws.events()
    funnels = [f.to_dict() for f in ws.funnels()]

    # Step 1: Parse intent and generate plan
    planning_prompt = f"""You are a Mixpanel analytics expert. Parse this question and create an execution plan.

Question: {question}
{f"Additional context: {context}" if context else ""}

Available events: {json.dumps(events[:50])}  # First 50 for context
Available funnels: {json.dumps(funnels[:10])}  # First 10 for context

Available query types:
1. segmentation(event, from_date, to_date, on=property) - Time series of event counts
2. retention(born_event, return_event, from_date, to_date) - Cohort retention
3. funnel(funnel_id, from_date, to_date) - Conversion analysis
4. property_counts(event, property, from_date, to_date) - Property distribution
5. event_counts(events[], from_date, to_date) - Compare multiple events
6. activity_feed(distinct_id) - User's event history
7. jql(script) - Custom JavaScript queries

Create an execution plan as JSON:
{{
  "intent": "brief description of what user wants to know",
  "query_type": "primary analysis type",
  "queries": [
    {{"method": "segmentation", "params": {{"event": "signup", ...}}}},
    ...
  ],
  "date_range": {{"from_date": "YYYY-MM-DD", "to_date": "YYYY-MM-DD"}},
  "comparison_needed": true/false,
  "reasoning": "why these queries answer the question"
}}
"""

    plan_response = await ctx.sample(
        messages=[{"role": "user", "content": planning_prompt}],
        max_tokens=800,
    )

    try:
        plan = json.loads(plan_response.text)
    except json.JSONDecodeError:
        return {
            "answer": "I couldn't parse your question into a query plan.",
            "error": "Planning failed",
            "raw_response": plan_response.text,
        }

    # Step 2: Execute queries
    results = {}
    queries_executed = []

    for query_spec in plan.get("queries", []):
        method = query_spec.get("method")
        params = query_spec.get("params", {})

        try:
            if method == "segmentation":
                result = ws.segmentation(**params)
            elif method == "retention":
                result = ws.retention(**params)
            elif method == "funnel":
                result = ws.funnel(**params)
            elif method == "property_counts":
                result = ws.property_counts(**params)
            elif method == "event_counts":
                result = ws.event_counts(**params)
            elif method == "activity_feed":
                result = ws.activity_feed(**params)
            elif method == "jql":
                result = ws.jql(**params)
            else:
                continue

            results[f"{method}_{len(results)}"] = result.to_dict()
            queries_executed.append({"method": method, "params": params})
        except Exception as e:
            results[f"{method}_error"] = str(e)

    # Step 3: Synthesize answer
    synthesis_prompt = f"""Answer this analytics question based on the data.

Original question: {question}
Query plan intent: {plan.get('intent', 'unknown')}

Query results:
{json.dumps(results, indent=2, default=str)}

Provide a comprehensive answer that:
1. Directly answers the question
2. Cites specific numbers from the data
3. Notes any caveats or limitations
4. Suggests 2-3 follow-up questions

Format as JSON:
{{
  "answer": "Your detailed answer here...",
  "key_metrics": [{{"metric": "name", "value": 123, "interpretation": "..."}}],
  "confidence": "low/medium/high",
  "caveats": ["any data limitations"],
  "follow_up_suggestions": ["related questions to explore"]
}}
"""

    answer_response = await ctx.sample(
        messages=[{"role": "user", "content": synthesis_prompt}],
        max_tokens=1200,
    )

    try:
        answer = json.loads(answer_response.text)
    except json.JSONDecodeError:
        answer = {"answer": answer_response.text}

    return {
        **answer,
        "queries_executed": queries_executed,
        "supporting_data": results,
        "plan": plan,
    }
```

### 1.5 Sampling Client Requirements

Sampling requires MCP client support. The server will:

1. **Check client capabilities** during initialization via capability negotiation
2. **Gracefully degrade** if sampling unavailable:
   - Intelligent tools return raw data without synthesis
   - Tool docstrings indicate "requires sampling-capable client"
   - Log warning when sampling requested but unavailable

```python
@mcp.tool
async def diagnose_metric_drop(
    event: str,
    date: str,
    ctx: Context,
) -> dict:
    """Diagnose why a metric dropped on a specific date.

    Note: Full synthesis requires a sampling-capable MCP client.
    Without sampling, returns raw data for manual interpretation.
    """
    # ... gather data ...

    # Check if client supports sampling
    if not ctx.client_supports_sampling():
        return {
            "status": "partial",
            "message": "Client does not support sampling. Returning raw data.",
            "raw_data": {
                "baseline": baseline_data,
                "current": current_data,
                "segments": segment_data,
            },
            "manual_analysis_hints": [
                "Compare baseline vs current counts",
                "Look for segments with largest percentage drops",
                "Check if drop correlates with specific dimensions",
            ],
        }

    # Proceed with sampling-powered synthesis
    synthesis = await ctx.sample(...)
    return {...}
```

**Future consideration**: A fallback sampling handler could be added when users explicitly configure an API key, but we avoid auto-discovery of environment variables like `ANTHROPIC_API_KEY` to prevent unexpected API usage.

---

## Phase 2: Elicitation for Interactive Workflows

### 2.1 Overview

FastMCP's `ctx.elicit()` enables servers to request structured input from users mid-execution. This transforms tools into **interactive workflows**.

### 2.2 Tool: `guided_analysis`

**Purpose**: Interactive analysis session that adapts based on user choices.

```python
from pydantic import BaseModel
from typing import Literal

class AnalysisChoice(BaseModel):
    """User's choice for analysis direction."""
    focus_area: Literal["conversion", "retention", "engagement", "revenue"]
    time_period: Literal["last_7_days", "last_30_days", "last_90_days", "custom"]
    custom_start: str | None = None
    custom_end: str | None = None

class SegmentChoice(BaseModel):
    """User's choice for which segment to investigate."""
    segment_index: int
    investigate_further: bool

@mcp.tool
async def guided_analysis(
    goal: str | None = None,
    ctx: Context,
) -> dict:
    """Start an interactive guided analysis session.

    Walks you through a structured analytics investigation,
    asking for input at key decision points.

    Args:
        goal: Optional starting goal (e.g., "improve signup conversion").

    Returns:
        Complete analysis results based on your choices.
    """
    ws = get_workspace(ctx)

    # Step 1: Elicit analysis focus if not provided
    if goal is None:
        choice = await ctx.elicit(
            message="What would you like to analyze?",
            response_type=AnalysisChoice,
        )
        if choice.cancelled:
            return {"status": "cancelled", "message": "Analysis cancelled by user"}

        focus = choice.data.focus_area
        period = choice.data.time_period
    else:
        # Parse goal to determine focus
        focus = "conversion"  # Default
        period = "last_30_days"

    # Determine date range
    from datetime import datetime, timedelta
    today = datetime.now()
    if period == "last_7_days":
        from_date = (today - timedelta(days=7)).strftime("%Y-%m-%d")
    elif period == "last_30_days":
        from_date = (today - timedelta(days=30)).strftime("%Y-%m-%d")
    elif period == "last_90_days":
        from_date = (today - timedelta(days=90)).strftime("%Y-%m-%d")
    else:
        from_date = choice.data.custom_start
    to_date = today.strftime("%Y-%m-%d")

    # Step 2: Run initial analysis based on focus
    if focus == "conversion":
        funnels = ws.funnels()
        if funnels:
            # Run first funnel
            result = ws.funnel(funnels[0].funnel_id, from_date=from_date, to_date=to_date)
            initial_data = result.to_dict()
        else:
            initial_data = {"error": "No funnels configured"}

    elif focus == "retention":
        events = ws.events()
        # Find likely activation event
        activation_event = next((e for e in events if "signup" in e.lower()), events[0])
        result = ws.retention(
            born_event=activation_event,
            return_event=activation_event,
            from_date=from_date,
            to_date=to_date
        )
        initial_data = result.to_dict()

    # Step 3: Show results and elicit next step
    segments = [
        {"index": 0, "name": "Mobile users", "metric": 45.2},
        {"index": 1, "name": "Desktop users", "metric": 62.1},
        {"index": 2, "name": "New users", "metric": 38.5},
    ]  # Would be computed from actual data

    segment_choice = await ctx.elicit(
        message=f"""Initial analysis complete for {focus}.

Found {len(segments)} interesting segments:
{chr(10).join(f"{s['index']+1}. {s['name']}: {s['metric']}%" for s in segments)}

Which segment would you like to investigate further?""",
        response_type=SegmentChoice,
    )

    if segment_choice.cancelled:
        return {
            "status": "partial",
            "initial_analysis": initial_data,
            "message": "Analysis stopped after initial phase",
        }

    # Step 4: Deep dive on selected segment
    selected = segments[segment_choice.data.segment_index]
    # ... perform deeper analysis on selected segment ...

    return {
        "status": "complete",
        "focus_area": focus,
        "period": {"from": from_date, "to": to_date},
        "initial_analysis": initial_data,
        "selected_segment": selected,
        "deep_dive": {"placeholder": "deep dive results"},
    }
```

### 2.3 Tool: `safe_large_fetch`

**Purpose**: Confirm before fetching large datasets.

```python
class FetchConfirmation(BaseModel):
    """Confirmation for large data fetch."""
    proceed: bool
    reduce_scope: bool = False
    new_limit: int | None = None

@mcp.tool
async def safe_fetch_events(
    from_date: str,
    to_date: str,
    table: str = "events",
    events: list[str] | None = None,
    ctx: Context,
) -> dict:
    """Fetch events with confirmation for large datasets.

    Estimates data size before fetching and asks for confirmation
    if the fetch would be large (>100K events).

    Args:
        from_date: Start date (YYYY-MM-DD).
        to_date: End date (YYYY-MM-DD).
        table: Table name for storage.
        events: Optional list of specific events to fetch.

    Returns:
        FetchResult with row count and duration.
    """
    ws = get_workspace(ctx)

    # Estimate size using segmentation
    if events:
        estimate_event = events[0]
    else:
        top = ws.top_events(limit=1)
        estimate_event = top[0].name if top else None

    if estimate_event:
        seg = ws.segmentation(estimate_event, from_date=from_date, to_date=to_date)
        estimated_count = sum(seg.series.get("", {}).values())
        # Rough multiplier for all events
        all_events_count = ws.events()
        estimated_total = estimated_count * len(all_events_count) if not events else estimated_count * len(events)
    else:
        estimated_total = 0

    # If large, ask for confirmation
    if estimated_total > 100_000:
        from datetime import datetime
        days = (datetime.strptime(to_date, "%Y-%m-%d") - datetime.strptime(from_date, "%Y-%m-%d")).days

        confirm = await ctx.elicit(
            message=f"""This fetch will download approximately {estimated_total:,} events.

Date range: {from_date} to {to_date} ({days} days)
Estimated time: {estimated_total // 10000} minutes
Estimated storage: {estimated_total * 500 // 1_000_000} MB

Do you want to proceed?""",
            response_type=FetchConfirmation,
        )

        if confirm.cancelled or not confirm.data.proceed:
            return {
                "status": "cancelled",
                "estimated_events": estimated_total,
                "message": "Fetch cancelled. Consider narrowing the date range or filtering specific events.",
            }

        if confirm.data.reduce_scope and confirm.data.new_limit:
            # Apply limit
            result = ws.fetch_events(
                from_date=from_date,
                to_date=to_date,
                table=table,
                limit=confirm.data.new_limit,
            )
            return result.to_dict()

    # Proceed with fetch
    result = ws.fetch_events(from_date=from_date, to_date=to_date, table=table)
    return result.to_dict()
```

---

## Phase 3: Higher-Order Composed Tools

### 3.1 Design Philosophy

Composed tools follow the **Notion pattern**: abstract away complexity into single, meaningful operations. Each composed tool:

1. Orchestrates multiple primitive tools
2. Handles intermediate data flow
3. Produces a complete, actionable result
4. Is more valuable than the sum of its parts

### 3.2 Tool: `gqm_investigation`

**Purpose**: Structured investigation using the Goal-Question-Metric framework.

The GQM (Goal-Question-Metric) methodology decomposes vague analytics questions into systematic investigations:

| Level | Type | Description |
|-------|------|-------------|
| **Goal** | Conceptual | What the user wants to understand or achieve |
| **Question** | Operational | 3-5 specific, answerable sub-questions |
| **Metric** | Quantitative | Concrete Mixpanel query for each question |

```python
@mcp.tool
async def gqm_investigation(
    goal: str,
    category: Literal["acquisition", "activation", "retention", "revenue", "referral"] | None = None,
    from_date: str | None = None,
    to_date: str | None = None,
    ctx: Context,
) -> dict:
    """Perform structured investigation using GQM (Goal-Question-Metric) framework.

    Decomposes a high-level analytics goal into answerable sub-questions,
    executes targeted queries for each, and synthesizes findings.

    This is the primary tool for open-ended analytics questions like:
    - "Why is retention down?"
    - "What's driving revenue growth?"
    - "Which acquisition channels are most effective?"

    Args:
        goal: The analytics goal to investigate (e.g., "Understand why signups dropped").
        category: Optional AARRR category to scope investigation.
        from_date: Analysis start date (defaults to 30 days ago).
        to_date: Analysis end date (defaults to today).

    Returns:
        Structured investigation with:
        - interpreted_goal: Clarified version of the goal
        - aarrr_category: Classification for scoping
        - questions: List of sub-questions with metrics
        - findings: Results for each question
        - synthesis: Overall answer to the goal
        - next_steps: Suggested follow-up investigations

    Example:
        gqm_investigation("Why is retention declining?")
        → Generates 4-5 questions about magnitude, segments, behaviors,
          acquisition mix, and product changes, then synthesizes findings.
    """
    ws = get_workspace(ctx)

    from datetime import datetime, timedelta
    if to_date is None:
        to_date = datetime.now().strftime("%Y-%m-%d")
    if from_date is None:
        from_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")

    # Discover available data
    events = ws.events()
    funnels = [f.to_dict() for f in ws.funnels()]
    top_events = [e.to_dict() for e in ws.top_events(limit=10)]

    # Auto-classify if category not provided
    if category is None:
        goal_lower = goal.lower()
        if any(kw in goal_lower for kw in ["signup", "traffic", "acquisition", "channel", "source"]):
            category = "acquisition"
        elif any(kw in goal_lower for kw in ["onboard", "activate", "first", "start"]):
            category = "activation"
        elif any(kw in goal_lower for kw in ["retain", "return", "churn", "come back"]):
            category = "retention"
        elif any(kw in goal_lower for kw in ["revenue", "purchase", "pay", "convert", "monetiz"]):
            category = "revenue"
        elif any(kw in goal_lower for kw in ["refer", "invite", "share", "viral"]):
            category = "referral"
        else:
            category = "retention"  # Default to retention as most common

    # Generate category-specific questions
    questions_and_queries = []

    if category == "retention":
        # Find likely signup/session events
        signup_event = next((e for e in events if "signup" in e.lower()), events[0] if events else "Signup")
        session_event = next((e for e in events if "session" in e.lower() or "login" in e.lower()), signup_event)

        questions_and_queries = [
            {
                "question": "What is the magnitude and trend of retention?",
                "query_type": "retention",
                "query_fn": lambda: ws.retention(
                    born_event=signup_event,
                    return_event=session_event,
                    from_date=from_date,
                    to_date=to_date,
                    unit="week",
                ),
            },
            {
                "question": "How does retention vary by user segment (platform)?",
                "query_type": "property_counts",
                "query_fn": lambda: ws.property_counts(
                    signup_event, "platform",
                    from_date=from_date, to_date=to_date
                ),
            },
            {
                "question": "What events do retained users perform that churned users don't?",
                "query_type": "event_counts",
                "query_fn": lambda: ws.event_counts(
                    [e for e in events[:10]],  # Top 10 events
                    from_date=from_date, to_date=to_date
                ),
            },
            {
                "question": "Has acquisition volume or mix changed?",
                "query_type": "segmentation",
                "query_fn": lambda: ws.segmentation(
                    signup_event,
                    from_date=from_date, to_date=to_date,
                    unit="day"
                ),
            },
        ]

    elif category == "acquisition":
        signup_event = next((e for e in events if "signup" in e.lower()), events[0] if events else "Signup")

        questions_and_queries = [
            {
                "question": "What is the acquisition trend over time?",
                "query_type": "segmentation",
                "query_fn": lambda: ws.segmentation(
                    signup_event,
                    from_date=from_date, to_date=to_date,
                    unit="day"
                ),
            },
            {
                "question": "Which channels are driving acquisition?",
                "query_type": "property_counts",
                "query_fn": lambda: ws.property_counts(
                    signup_event, "utm_source",
                    from_date=from_date, to_date=to_date
                ),
            },
            {
                "question": "How do acquisition sources compare by volume?",
                "query_type": "property_counts",
                "query_fn": lambda: ws.property_counts(
                    signup_event, "utm_medium",
                    from_date=from_date, to_date=to_date
                ),
            },
            {
                "question": "What is the geographic distribution?",
                "query_type": "property_counts",
                "query_fn": lambda: ws.property_counts(
                    signup_event, "country",
                    from_date=from_date, to_date=to_date
                ),
            },
        ]

    elif category == "revenue":
        purchase_event = next((e for e in events if any(kw in e.lower() for kw in ["purchase", "order", "payment"])), events[0] if events else "Purchase")

        questions_and_queries = [
            {
                "question": "What is the revenue event trend?",
                "query_type": "segmentation",
                "query_fn": lambda: ws.segmentation(
                    purchase_event,
                    from_date=from_date, to_date=to_date,
                    unit="day"
                ),
            },
            {
                "question": "How does revenue break down by platform?",
                "query_type": "property_counts",
                "query_fn": lambda: ws.property_counts(
                    purchase_event, "platform",
                    from_date=from_date, to_date=to_date
                ),
            },
            {
                "question": "What is the conversion funnel performance?",
                "query_type": "funnel",
                "query_fn": lambda: ws.funnel(
                    funnels[0]["funnel_id"],
                    from_date=from_date, to_date=to_date
                ) if funnels else None,
            },
        ]

    # Similar patterns for activation and referral...

    # Execute all queries
    findings = []
    for item in questions_and_queries:
        try:
            result = item["query_fn"]()
            findings.append({
                "question": item["question"],
                "query_type": item["query_type"],
                "result": result.to_dict() if result and hasattr(result, 'to_dict') else result,
                "status": "success",
            })
        except Exception as e:
            findings.append({
                "question": item["question"],
                "query_type": item["query_type"],
                "error": str(e),
                "status": "failed",
            })

    # Generate suggested next steps based on category
    next_steps = {
        "retention": [
            "Deep-dive: Compare feature usage between retained vs churned users",
            "Segment: Analyze retention by acquisition source",
            "Experiment: Test re-engagement campaigns for at-risk users",
        ],
        "acquisition": [
            "Deep-dive: Calculate CAC by channel",
            "Compare: Conversion rates from signup to activation by source",
            "Test: A/B test landing pages for top channels",
        ],
        "revenue": [
            "Deep-dive: Calculate LTV by cohort",
            "Segment: Revenue by user acquisition source",
            "Analyze: Price sensitivity and upgrade triggers",
        ],
        "activation": [
            "Funnel: Analyze onboarding step-by-step drop-offs",
            "Segment: Activation rates by user segment",
            "Experiment: Test simplified onboarding flow",
        ],
        "referral": [
            "Calculate: Viral coefficient (K-factor)",
            "Segment: Referral rates by user type",
            "Test: Different referral incentive structures",
        ],
    }

    return {
        "interpreted_goal": goal,
        "aarrr_category": category,
        "period": {"from": from_date, "to": to_date},
        "schema_context": {
            "total_events": len(events),
            "top_events": [e["name"] for e in top_events[:5]] if top_events else [],
            "available_funnels": len(funnels),
        },
        "questions": [
            {"question": item["question"], "query_type": item["query_type"]}
            for item in questions_and_queries
        ],
        "findings": findings,
        "synthesis": {
            "status": "complete",
            "successful_queries": sum(1 for f in findings if f["status"] == "success"),
            "total_queries": len(findings),
            "note": "Review findings for each question to understand patterns",
        },
        "next_steps": next_steps.get(category, []),
    }
```

### 3.3 Tool: `cohort_comparison`

**Purpose**: Compare two user cohorts across all dimensions.

```python
@mcp.tool
async def cohort_comparison(
    cohort_a_filter: str,
    cohort_b_filter: str,
    cohort_a_name: str = "Cohort A",
    cohort_b_name: str = "Cohort B",
    from_date: str = None,
    to_date: str = None,
    compare_dimensions: list[str] | None = None,
    ctx: Context,
) -> dict:
    """Compare two user cohorts across multiple dimensions.

    Provides comprehensive comparison including:
    - Event frequency differences
    - Retention rate comparison
    - Property distribution differences
    - Statistical significance of differences

    Args:
        cohort_a_filter: Filter expression for first cohort.
        cohort_b_filter: Filter expression for second cohort.
        cohort_a_name: Display name for first cohort.
        cohort_b_name: Display name for second cohort.
        from_date: Analysis start date.
        to_date: Analysis end date.
        compare_dimensions: Dimensions to compare.

    Returns:
        Detailed comparison with statistical analysis.

    Example:
        cohort_comparison(
            'properties["plan"] == "premium"',
            'properties["plan"] == "free"',
            "Premium Users",
            "Free Users"
        )
    """
    ws = get_workspace(ctx)

    # Default dates and dimensions
    from datetime import datetime, timedelta
    if to_date is None:
        to_date = datetime.now().strftime("%Y-%m-%d")
    if from_date is None:
        from_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")

    if compare_dimensions is None:
        compare_dimensions = ["event_frequency", "retention", "top_events"]

    results = {
        "cohort_a": {"name": cohort_a_name, "filter": cohort_a_filter},
        "cohort_b": {"name": cohort_b_name, "filter": cohort_b_filter},
        "period": {"from": from_date, "to": to_date},
        "comparisons": {},
    }

    # Compare top events for each cohort
    if "top_events" in compare_dimensions:
        # Would use JQL or filtered queries
        results["comparisons"]["top_events"] = {
            "cohort_a": ["event1", "event2", "event3"],
            "cohort_b": ["event1", "event3", "event4"],
            "unique_to_a": ["event2"],
            "unique_to_b": ["event4"],
        }

    # Compare retention
    if "retention" in compare_dimensions:
        # Would run retention with cohort filters
        results["comparisons"]["retention"] = {
            "cohort_a": {"d7": 0.25, "d30": 0.12},
            "cohort_b": {"d7": 0.18, "d30": 0.08},
            "difference": {"d7": 0.07, "d30": 0.04},
            "cohort_a_better_by": {"d7": "38.9%", "d30": "50.0%"},
        }

    # Compare event frequency
    if "event_frequency" in compare_dimensions:
        results["comparisons"]["event_frequency"] = {
            "cohort_a": {"avg_events_per_user": 45.2, "median": 32},
            "cohort_b": {"avg_events_per_user": 28.1, "median": 18},
            "difference": {"avg": 17.1, "pct": "60.9%"},
        }

    return results
```

### 3.4 Tool: `product_health_dashboard`

**Purpose**: Generate complete AARRR metrics dashboard.

```python
@mcp.tool
async def product_health_dashboard(
    acquisition_event: str = "signup",
    activation_event: str | None = None,
    retention_event: str | None = None,
    revenue_event: str | None = None,
    referral_event: str | None = None,
    from_date: str = None,
    to_date: str = None,
    ctx: Context,
) -> dict:
    """Generate comprehensive product health dashboard using AARRR framework.

    Computes all pirate metrics:
    - Acquisition: New user signups by source
    - Activation: Onboarding/first value completion
    - Retention: D1/D7/D30 return rates
    - Revenue: Conversion and monetization (if applicable)
    - Referral: Viral coefficient (if applicable)

    Args:
        acquisition_event: Event for new user acquisition.
        activation_event: Event indicating user activation.
        retention_event: Event for measuring return.
        revenue_event: Purchase/subscription event.
        referral_event: Invite/share event.
        from_date: Dashboard start date.
        to_date: Dashboard end date.

    Returns:
        Complete AARRR dashboard with trends and insights.
    """
    ws = get_workspace(ctx)

    from datetime import datetime, timedelta
    if to_date is None:
        to_date = datetime.now().strftime("%Y-%m-%d")
    if from_date is None:
        from_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")

    # If events not specified, try to infer them
    events = ws.events()
    if activation_event is None:
        activation_event = next(
            (e for e in events if any(kw in e.lower() for kw in ["onboard", "complete", "activate"])),
            acquisition_event
        )
    if retention_event is None:
        retention_event = acquisition_event

    dashboard = {
        "period": {"from": from_date, "to": to_date},
        "metrics": {},
    }

    # Acquisition
    acq = ws.segmentation(acquisition_event, from_date=from_date, to_date=to_date, unit="day")
    acq_by_source = ws.property_counts(acquisition_event, "utm_source", from_date=from_date, to_date=to_date)
    dashboard["metrics"]["acquisition"] = {
        "total_new_users": sum(acq.series.get("", {}).values()),
        "daily_average": sum(acq.series.get("", {}).values()) / 30,
        "by_source": acq_by_source.to_dict(),
        "trend": acq.to_dict(),
    }

    # Activation (if different from acquisition)
    if activation_event != acquisition_event:
        act = ws.segmentation(activation_event, from_date=from_date, to_date=to_date, unit="day")
        act_count = sum(act.series.get("", {}).values())
        acq_count = dashboard["metrics"]["acquisition"]["total_new_users"]
        dashboard["metrics"]["activation"] = {
            "total_activated": act_count,
            "activation_rate": act_count / acq_count if acq_count > 0 else 0,
            "trend": act.to_dict(),
        }

    # Retention
    ret = ws.retention(
        born_event=acquisition_event,
        return_event=retention_event,
        from_date=from_date,
        to_date=to_date,
        unit="day",
    )
    dashboard["metrics"]["retention"] = ret.to_dict()

    # Revenue (if event specified)
    if revenue_event:
        rev = ws.segmentation(revenue_event, from_date=from_date, to_date=to_date, unit="day")
        dashboard["metrics"]["revenue"] = {
            "total_transactions": sum(rev.series.get("", {}).values()),
            "trend": rev.to_dict(),
        }

    # Referral (if event specified)
    if referral_event:
        ref = ws.segmentation(referral_event, from_date=from_date, to_date=to_date, unit="day")
        dashboard["metrics"]["referral"] = {
            "total_referrals": sum(ref.series.get("", {}).values()),
            "trend": ref.to_dict(),
        }

    return dashboard
```

---

## Phase 4: Enhanced Resources

### 4.1 Dynamic Resource Templates

Expand resources to provide pre-computed views.

```python
@mcp.resource("analysis://retention/{event}/weekly")
async def retention_weekly_resource(event: str, ctx: Context) -> str:
    """Pre-computed weekly retention for an event."""
    ws = get_workspace(ctx)
    from datetime import datetime, timedelta

    to_date = datetime.now().strftime("%Y-%m-%d")
    from_date = (datetime.now() - timedelta(days=90)).strftime("%Y-%m-%d")

    result = ws.retention(
        born_event=event,
        return_event=event,
        from_date=from_date,
        to_date=to_date,
        unit="week",
        interval_count=12,
    )
    return json.dumps(result.to_dict(), indent=2, default=str)


@mcp.resource("analysis://trends/{event}/{days}")
async def event_trend_resource(event: str, days: str, ctx: Context) -> str:
    """Daily trend for an event over specified days."""
    ws = get_workspace(ctx)
    from datetime import datetime, timedelta

    days_int = int(days)
    to_date = datetime.now().strftime("%Y-%m-%d")
    from_date = (datetime.now() - timedelta(days=days_int)).strftime("%Y-%m-%d")

    result = ws.segmentation(event, from_date=from_date, to_date=to_date, unit="day")
    return json.dumps(result.to_dict(), indent=2, default=str)


@mcp.resource("users://{distinct_id}/journey")
async def user_journey_resource(distinct_id: str, ctx: Context) -> str:
    """Complete user journey with key moments."""
    ws = get_workspace(ctx)

    feed = ws.activity_feed(distinct_id, limit=500)
    events = feed.events

    journey = {
        "user_id": distinct_id,
        "total_events": len(events),
        "first_seen": events[-1]["time"] if events else None,
        "last_seen": events[0]["time"] if events else None,
        "event_summary": {},
        "timeline": events[:50],  # Last 50 events
    }

    # Summarize events
    for event in events:
        name = event.get("event") or event.get("name")
        journey["event_summary"][name] = journey["event_summary"].get(name, 0) + 1

    return json.dumps(journey, indent=2, default=str)


@mcp.resource("insights://top-segments/{event}")
async def top_segments_resource(event: str, ctx: Context) -> str:
    """Top performing segments for an event."""
    ws = get_workspace(ctx)
    from datetime import datetime, timedelta

    to_date = datetime.now().strftime("%Y-%m-%d")
    from_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")

    dimensions = ["platform", "country", "utm_source"]
    segments = {}

    for dim in dimensions:
        try:
            counts = ws.property_counts(event, dim, from_date=from_date, to_date=to_date)
            segments[dim] = counts.to_dict()
        except Exception:
            continue

    return json.dumps(segments, indent=2, default=str)
```

### 4.2 Recipe Resources

Store reusable analysis patterns.

```python
@mcp.resource("recipes://weekly-review")
def weekly_review_recipe(ctx: Context) -> str:
    """Recipe for weekly product review."""
    return json.dumps({
        "name": "Weekly Product Review",
        "description": "Standard weekly product metrics review",
        "steps": [
            {
                "name": "acquisition_trends",
                "tool": "segmentation",
                "params": {"event": "signup", "unit": "day"},
                "date_range": "last_7_days",
            },
            {
                "name": "conversion_funnel",
                "tool": "funnel",
                "params": {"funnel_id": "${primary_funnel_id}"},
                "date_range": "last_7_days",
            },
            {
                "name": "retention_check",
                "tool": "retention",
                "params": {"born_event": "signup", "return_event": "login"},
                "date_range": "last_30_days",
            },
            {
                "name": "top_events",
                "tool": "top_events",
                "params": {"limit": 10},
            },
        ],
        "output_format": "executive_summary",
    }, indent=2)


@mcp.resource("recipes://churn-investigation")
def churn_investigation_recipe(ctx: Context) -> str:
    """Recipe for investigating user churn."""
    return json.dumps({
        "name": "Churn Investigation",
        "description": "Identify why users are churning",
        "steps": [
            {
                "name": "identify_churned",
                "description": "Find users who haven't returned in 14+ days",
                "tool": "jql",
                "params": {
                    "script": """
                    function main() {
                      return People()
                        .filter(function(u) {
                          return u.last_seen < new Date(Date.now() - 14*24*60*60*1000);
                        })
                        .map(function(u) {
                          return {
                            distinct_id: u.distinct_id,
                            last_seen: u.last_seen,
                            properties: u.properties
                          };
                        });
                    }
                    """,
                },
            },
            {
                "name": "compare_churned_vs_retained",
                "tool": "cohort_comparison",
                "params": {
                    "cohort_a_name": "Churned",
                    "cohort_b_name": "Retained",
                },
            },
        ],
    }, indent=2)
```

---

## Phase 5: Framework-Embedded Prompts

### 5.1 Enhanced Prompt Design

Prompts that encode domain expertise and analytical frameworks.

```python
@mcp.prompt
def gqm_decomposition(goal: str) -> str:
    """Goal-Question-Metric framework for structured investigation."""
    return f"""You are conducting a structured analytics investigation using the GQM (Goal-Question-Metric) framework.

## Your Goal
{goal}

## GQM Framework

The GQM methodology decomposes analytics questions into three levels:

| Level | Type | Description |
|-------|------|-------------|
| **Goal** | Conceptual | What you want to understand or achieve |
| **Question** | Operational | 3-5 specific, answerable sub-questions |
| **Metric** | Quantitative | Concrete Mixpanel query for each question |

## Step 1: Classify the Goal (AARRR)

First, classify which area of the user lifecycle this goal relates to:

| Category | Focus | Key Events |
|----------|-------|------------|
| **Acquisition** | How users find you | Signup, landing page, utm_source |
| **Activation** | First value experience | Onboarding, first action, tutorial |
| **Retention** | Do users come back | Login, session, return visits |
| **Revenue** | Can you monetize | Purchase, subscribe, upgrade |
| **Referral** | Do users tell others | Invite, share, referral |

## Step 2: Generate Sub-Questions

For your goal, generate 3-5 operational questions that are:
- **Specific**: Clear enough to answer with data
- **Measurable**: Can be answered with Mixpanel queries
- **Actionable**: Answers lead to decisions

### Example Questions by Category:

**Retention Goal**: "Why is retention declining?"
1. What is the magnitude and timing of the decline? → retention query
2. Which user segments are most affected? → segmented retention
3. What behavioral differences exist between retained vs churned? → event comparison
4. Did acquisition mix change? → segmentation by source
5. Did a product change coincide? → feature usage trends

**Acquisition Goal**: "Which channels are most effective?"
1. What is the volume by channel? → segmentation by utm_source
2. What is the cost per acquisition by channel? → (requires external data)
3. How do conversion rates differ by channel? → funnel by segment
4. What is the quality (retention) by channel? → retention by source

## Step 3: Map to Mixpanel Queries

For each question, specify the exact query:

| Query Type | Tool | Use Case |
|------------|------|----------|
| `segmentation` | Time series of event | Trends, volumes |
| `property_counts` | Breakdown by dimension | Segment analysis |
| `retention` | Cohort return rates | User return behavior |
| `funnel` | Conversion analysis | Step-by-step drop-offs |
| `event_counts` | Multi-event comparison | Compare behaviors |
| `jql` | Complex transformations | Custom analysis |

## Step 4: Execute and Synthesize

For each question:
1. Run the specified query
2. Extract the key metric(s)
3. Note observations and anomalies

Then synthesize:
- **Direct answer** to the original goal
- **Evidence** from each sub-question
- **Confidence level** (how certain are we?)
- **Next steps** for deeper investigation

## Output Format

### Goal
> [Restated goal]

### AARRR Category
> [Category with rationale]

### Questions & Metrics

| # | Question | Query | Key Finding |
|---|----------|-------|-------------|
| 1 | ... | segmentation(...) | Result |
| 2 | ... | retention(...) | Result |

### Synthesis
> [Direct answer to goal, supported by evidence]

### Next Steps
1. [Follow-up investigation 1]
2. [Follow-up investigation 2]
3. [Follow-up investigation 3]

---

Now investigate: {goal}
"""


@mcp.prompt
def growth_accounting() -> str:
    """AARRR pirate metrics framework analysis."""
    return """You are conducting a growth accounting analysis using the AARRR framework.

## AARRR Framework

### 1. Acquisition (How do users find us?)
- Use `segmentation("signup", ...)` to get new user trends
- Use `property_counts("signup", "utm_source", ...)` for channel breakdown
- Compare: Which channels are growing? Which are declining?

### 2. Activation (Do users have a great first experience?)
- Identify your "aha moment" event (first value moment)
- Use `funnel()` to measure signup → activation conversion
- Benchmark: 60% activation is median, 80%+ is top quartile

### 3. Retention (Do users come back?)
- Use `retention("signup", "login", ...)` for cohort curves
- Key metrics: D1, D7, D30 retention
- Benchmarks by industry:
  - B2B SaaS: D1=40%, D7=25%, D30=15%
  - B2C SaaS: D1=35%, D7=20%, D30=10%
  - E-commerce: D1=20%, D7=10%, D30=5%

### 4. Revenue (Can we monetize?)
- Use `segmentation("purchase", ...)` for transaction trends
- Calculate: Conversion rate, ARPU, LTV
- Compare revenue across cohorts

### 5. Referral (Do users tell others?)
- Look for invite/share/refer events
- Calculate viral coefficient: invites_sent × invite_conversion_rate
- Target: K-factor > 0.5 indicates healthy virality

## Analysis Workflow

1. Start with `top_events()` to understand data availability
2. Map events to AARRR stages
3. Run queries for each stage
4. Compare to benchmarks
5. Identify weakest stage (your "leaky bucket")
6. Drill into that stage for root cause

## Output Format

Provide a health score (1-10) for each stage and overall, with specific metrics and recommendations.
"""


@mcp.prompt
def experiment_analysis(experiment_name: str, control_cohort: str, treatment_cohort: str) -> str:
    """A/B test evaluation with statistical rigor."""
    return f"""You are analyzing the A/B test: {experiment_name}

## Cohorts
- Control: {control_cohort}
- Treatment: {treatment_cohort}

## Analysis Framework

### Step 1: Sample Size Validation
- Use `cohort_comparison()` to get user counts
- Minimum: 1000 users per arm for reliable results
- Check for sample ratio mismatch (SRM)

### Step 2: Primary Metric Analysis
- Identify the primary success metric
- Calculate for both cohorts:
  - Mean and standard deviation
  - Confidence intervals (95%)
  - Relative lift: (treatment - control) / control

### Step 3: Statistical Significance
- Calculate p-value using two-sample t-test
- Threshold: p < 0.05 for significance
- Also calculate: statistical power, effect size

### Step 4: Segment Analysis
- Check for heterogeneous treatment effects
- Run by: platform, country, user tenure
- Watch for Simpson's Paradox

### Step 5: Guardrail Metrics
- Check metrics that should NOT change
- Examples: error rates, latency, support tickets
- Any regression = pause and investigate

## Decision Framework

| Outcome | Criteria | Action |
|---------|----------|--------|
| Ship | p<0.05, lift>10%, no guardrail regression | Deploy to 100% |
| Iterate | p<0.05, lift<10% | Refine hypothesis |
| Kill | p>0.20 OR negative lift | End experiment |
| Extend | 0.05<p<0.20 | Run longer for more power |

## Output Format

Provide clear recommendation with supporting evidence.
"""


@mcp.prompt
def data_quality_audit() -> str:
    """Systematic data quality assessment."""
    return """You are conducting a data quality audit on the Mixpanel implementation.

## Audit Checklist

### 1. Event Coverage
- Use `list_events()` to get all events
- Check for:
  - [ ] User lifecycle events (signup, login, logout)
  - [ ] Core product actions (the "jobs to be done")
  - [ ] Conversion events (purchase, subscribe, upgrade)
  - [ ] Error/failure events

### 2. Property Completeness
- For each major event, use `list_properties(event)`
- Check for:
  - [ ] User identifiers (distinct_id consistency)
  - [ ] Timestamp properties (for duration calculations)
  - [ ] Categorical dimensions (platform, country, etc.)
  - [ ] Numeric values (amounts, quantities, scores)

### 3. Data Freshness
- Use `top_events()` to check recent activity
- Verify events are being tracked in real-time
- Check for gaps in the data

### 4. Property Value Quality
- Use `list_property_values(event, property)` to audit values
- Check for:
  - [ ] Consistent casing (iOS vs ios vs IOS)
  - [ ] No PII leakage (emails, names in wrong fields)
  - [ ] Reasonable value ranges (no negative prices)
  - [ ] Complete coverage (not too many nulls)

### 5. Funnel Integrity
- Use `list_funnels()` to review saved funnels
- Verify funnel steps match actual user flow
- Check for missing intermediate steps

## Quality Score

Rate each area 1-5:
1. Event coverage: _/5
2. Property completeness: _/5
3. Data freshness: _/5
4. Value quality: _/5
5. Funnel integrity: _/5

Overall: _/25 (20+ = good, 15-19 = needs work, <15 = critical issues)

## Remediation Plan

For each issue found, provide:
- Severity (critical/high/medium/low)
- Description
- Recommended fix
- Effort estimate
"""
```

---

## Phase 6: Middleware Layer

### 6.1 Caching Middleware

```python
from fastmcp.server.middleware import Middleware
import hashlib
import time

# Simple in-memory cache (production would use Redis)
_cache: dict[str, tuple[float, any]] = {}
CACHE_TTL = 300  # 5 minutes

class CachingMiddleware(Middleware):
    """Cache expensive query results."""

    CACHEABLE_TOOLS = {
        "list_events", "list_funnels", "list_cohorts", "list_bookmarks",
        "top_events", "workspace_info", "list_tables",
    }

    async def __call__(self, call_next, context, tool, arguments):
        # Only cache specific tools
        if tool.name not in self.CACHEABLE_TOOLS:
            return await call_next(context, tool, arguments)

        # Generate cache key
        cache_key = hashlib.md5(
            f"{tool.name}:{json.dumps(arguments, sort_keys=True)}".encode()
        ).hexdigest()

        # Check cache
        if cache_key in _cache:
            cached_time, cached_result = _cache[cache_key]
            if time.time() - cached_time < CACHE_TTL:
                return cached_result

        # Execute and cache
        result = await call_next(context, tool, arguments)
        _cache[cache_key] = (time.time(), result)

        return result
```

### 6.2 Rate Limiting Middleware

Mixpanel has different rate limits for different API types:

| API | Rate Limit | Concurrency | Notes |
|-----|------------|-------------|-------|
| **Query API** | 60 queries/hour | 5 concurrent | Segmentation, funnel, retention, JQL |
| **Raw Export API** | 60 queries/hour, 3/second | 100 concurrent | Event/profile fetching |

A 429 error is returned when limits are exceeded.

```python
from collections import defaultdict
import asyncio
import time

class RateLimitMiddleware(Middleware):
    """Prevent Mixpanel API quota exhaustion.

    Implements separate rate limiting for Query API and Export API
    based on Mixpanel's documented limits.
    """

    # Query API tools (60/hour, max 5 concurrent)
    QUERY_API_TOOLS = {
        "segmentation", "funnel", "retention", "jql",
        "event_counts", "property_counts", "activity_feed",
        "frequency", "segmentation_numeric", "segmentation_sum",
        "segmentation_average", "query_flows", "query_saved_report",
    }

    # Export API tools (60/hour, 3/second, max 100 concurrent)
    EXPORT_API_TOOLS = {
        "fetch_events", "fetch_profiles",
        "stream_events", "stream_profiles",
    }

    def __init__(self):
        # Query API: 60/hour, 5 concurrent
        self.query_hourly_limit = 60
        self.query_concurrent_limit = 5
        self.query_request_times: list[float] = []
        self.query_active_count = 0
        self._query_lock = asyncio.Lock()

        # Export API: 60/hour, 3/second, 100 concurrent
        self.export_hourly_limit = 60
        self.export_per_second_limit = 3
        self.export_concurrent_limit = 100
        self.export_hourly_times: list[float] = []
        self.export_second_times: list[float] = []
        self.export_active_count = 0
        self._export_lock = asyncio.Lock()

    async def _check_query_limits(self) -> float | None:
        """Check Query API limits. Returns wait time if needed."""
        async with self._query_lock:
            now = time.time()

            # Check concurrent limit
            if self.query_active_count >= self.query_concurrent_limit:
                return 0.5  # Wait and retry

            # Check hourly limit (remove requests older than 1 hour)
            self.query_request_times = [
                t for t in self.query_request_times if now - t < 3600
            ]

            if len(self.query_request_times) >= self.query_hourly_limit:
                # Wait until oldest request expires from hourly window
                oldest = min(self.query_request_times)
                return 3600 - (now - oldest) + 1

            # Increment concurrent counter and record time
            self.query_active_count += 1
            self.query_request_times.append(now)
            return None

    async def _release_query_slot(self):
        """Release a Query API concurrent slot."""
        async with self._query_lock:
            self.query_active_count = max(0, self.query_active_count - 1)

    async def _check_export_limits(self) -> float | None:
        """Check Export API limits. Returns wait time if needed."""
        async with self._export_lock:
            now = time.time()

            # Check concurrent limit
            if self.export_active_count >= self.export_concurrent_limit:
                return 0.5  # Wait and retry

            # Check per-second limit (3/second)
            self.export_second_times = [
                t for t in self.export_second_times if now - t < 1.0
            ]
            if len(self.export_second_times) >= self.export_per_second_limit:
                oldest = min(self.export_second_times)
                return 1.0 - (now - oldest) + 0.1

            # Check hourly limit
            self.export_hourly_times = [
                t for t in self.export_hourly_times if now - t < 3600
            ]
            if len(self.export_hourly_times) >= self.export_hourly_limit:
                oldest = min(self.export_hourly_times)
                return 3600 - (now - oldest) + 1

            # Increment counters
            self.export_active_count += 1
            self.export_second_times.append(now)
            self.export_hourly_times.append(now)
            return None

    async def _release_export_slot(self):
        """Release an Export API concurrent slot."""
        async with self._export_lock:
            self.export_active_count = max(0, self.export_active_count - 1)

    async def __call__(self, call_next, context, tool, arguments):
        # Determine which API this tool uses
        if tool.name in self.QUERY_API_TOOLS:
            # Query API rate limiting
            while True:
                wait_time = await self._check_query_limits()
                if wait_time is None:
                    break
                await context.report_progress(
                    f"Rate limited (Query API). Waiting {wait_time:.1f}s..."
                )
                await asyncio.sleep(wait_time)

            try:
                return await call_next(context, tool, arguments)
            finally:
                await self._release_query_slot()

        elif tool.name in self.EXPORT_API_TOOLS:
            # Export API rate limiting
            while True:
                wait_time = await self._check_export_limits()
                if wait_time is None:
                    break
                await context.report_progress(
                    f"Rate limited (Export API). Waiting {wait_time:.1f}s..."
                )
                await asyncio.sleep(wait_time)

            try:
                return await call_next(context, tool, arguments)
            finally:
                await self._release_export_slot()

        else:
            # Non-API tool, no rate limiting needed
            return await call_next(context, tool, arguments)
```

**Rate Limit Recovery**: When a 429 error is received from Mixpanel, the error handler should parse the `Retry-After` header and provide guidance:

```python
# In errors.py
except RateLimitError as e:
    raise ToolError(
        f"Mixpanel rate limit exceeded. Retry after {e.retry_after} seconds.",
        details={
            "code": "rate_limit_exceeded",
            "retry_after_seconds": e.retry_after,
            "api_type": "query" if e.endpoint in QUERY_ENDPOINTS else "export",
            "suggestion": "Consider using broader time granularity or caching results",
        },
    ) from e
```

### 6.3 Audit Logging Middleware

```python
import logging
from datetime import datetime

logger = logging.getLogger("mp-mcp-audit")

class AuditMiddleware(Middleware):
    """Log all tool calls for reproducibility."""

    async def __call__(self, call_next, context, tool, arguments):
        start_time = time.time()
        request_id = context.request_context.request_id

        logger.info(
            "TOOL_START",
            extra={
                "request_id": request_id,
                "tool": tool.name,
                "arguments": arguments,
                "timestamp": datetime.utcnow().isoformat(),
            }
        )

        try:
            result = await call_next(context, tool, arguments)
            duration = time.time() - start_time

            logger.info(
                "TOOL_SUCCESS",
                extra={
                    "request_id": request_id,
                    "tool": tool.name,
                    "duration_ms": duration * 1000,
                    "result_size": len(str(result)),
                }
            )

            return result

        except Exception as e:
            duration = time.time() - start_time

            logger.error(
                "TOOL_ERROR",
                extra={
                    "request_id": request_id,
                    "tool": tool.name,
                    "duration_ms": duration * 1000,
                    "error": str(e),
                    "error_type": type(e).__name__,
                }
            )
            raise
```

### 6.4 Register Middleware

```python
# In server.py
mcp = FastMCP(
    "Mixpanel Analytics",
    instructions="...",
    lifespan=lifespan,
)

# Add middleware (order matters - first added is outermost)
mcp.add_middleware(AuditMiddleware())
mcp.add_middleware(RateLimitMiddleware(requests_per_minute=60))
mcp.add_middleware(CachingMiddleware())
```

---

## Phase 7: Task-Enabled Tools for Long-Running Operations

### 7.1 Overview

FastMCP v2.14.0 introduced `@mcp.tool(task=True)` for tools that execute asynchronously. This enables:

- **Non-blocking execution** — Client receives task ID immediately
- **Progress reporting** — Real-time updates during long operations
- **Cancellation support** — Users can cancel in-flight operations
- **Graceful degradation** — Falls back to synchronous if client doesn't support tasks

### 7.2 When to Use Task-Enabled Tools

| Characteristic | Use `task=True` | Use Regular Tool |
|----------------|-----------------|------------------|
| Execution time | > 10 seconds | < 10 seconds |
| Has progress stages | ✓ | ✗ |
| User may want to cancel | ✓ | ✗ |
| Fetches large datasets | ✓ | ✗ |
| Orchestrates multiple queries | ✓ | ✗ |

### 7.3 Candidate Tools for Task-Enabling

| Tool | Rationale | Progress Pattern |
|------|-----------|------------------|
| `fetch_events` | Large date ranges can take minutes | "Fetched day X of Y: N events" |
| `fetch_profiles` | Profile exports scale with cohort size | "Fetched page X: N profiles" |
| `gqm_investigation` | Executes 3-5 sequential queries | "Running query X of Y: [question]" |
| `diagnose_metric_drop` | Multi-step analysis with sampling | "Step X: [analysis phase]" |
| `product_health_dashboard` | Computes all AARRR metrics | "Computing [A/A/R/R/R] metrics..." |
| `cohort_comparison` | Multiple comparison dimensions | "Comparing dimension X of Y" |

### 7.4 Implementation Pattern

```python
from fastmcp import FastMCP, Context

mcp = FastMCP("mp-mcp-server")

@mcp.tool(task=True)
async def fetch_events(
    from_date: str,
    to_date: str,
    events: list[str] | None = None,
    table: str | None = None,
    ctx: Context,
) -> dict:
    """Fetch events from Mixpanel and store locally.

    This is a task-enabled tool that provides progress updates
    during long-running fetches.
    """
    ws = get_workspace(ctx)

    # Parse date range
    from datetime import datetime, timedelta
    start = datetime.strptime(from_date, "%Y-%m-%d")
    end = datetime.strptime(to_date, "%Y-%m-%d")
    total_days = (end - start).days + 1

    # Generate table name if not provided
    if table is None:
        table = f"events_{from_date}_{to_date}".replace("-", "")

    total_rows = 0

    for i, day_offset in enumerate(range(total_days)):
        current_date = start + timedelta(days=day_offset)
        date_str = current_date.strftime("%Y-%m-%d")

        # Report progress
        await ctx.task.update(
            progress=int((i / total_days) * 100),
            message=f"Fetching {date_str} ({i + 1}/{total_days})..."
        )

        # Check for cancellation
        if ctx.task.is_cancelled():
            return {
                "status": "cancelled",
                "rows_fetched": total_rows,
                "days_completed": i,
                "table": table,
            }

        # Fetch this day's events
        result = ws.fetch_events(
            from_date=date_str,
            to_date=date_str,
            events=events,
            table=table,
            append=(i > 0),  # Append after first day
        )
        total_rows += result.row_count

    # Final progress update
    await ctx.task.update(progress=100, message="Complete")

    return {
        "status": "success",
        "table": table,
        "rows": total_rows,
        "days": total_days,
    }
```

### 7.5 Progress Reporting Patterns

#### Pattern 1: Day-by-Day Fetching

```python
@mcp.tool(task=True)
async def fetch_events(..., ctx: Context) -> dict:
    for i, day in enumerate(date_range):
        await ctx.task.update(
            progress=int((i / len(date_range)) * 100),
            message=f"Fetching {day}: {events_count} events"
        )
```

#### Pattern 2: Multi-Query Investigation

```python
@mcp.tool(task=True)
async def gqm_investigation(..., ctx: Context) -> dict:
    questions = generate_questions(goal, category)

    for i, q in enumerate(questions):
        await ctx.task.update(
            progress=int((i / len(questions)) * 100),
            message=f"Q{i+1}/{len(questions)}: {q['question'][:50]}..."
        )

        result = execute_query(q)
        findings.append(result)

    await ctx.task.update(progress=100, message="Synthesizing findings...")
```

#### Pattern 3: Phased Analysis

```python
@mcp.tool(task=True)
async def diagnose_metric_drop(..., ctx: Context) -> dict:
    phases = [
        (10, "Fetching baseline data..."),
        (30, "Fetching comparison data..."),
        (50, "Analyzing segments..."),
        (70, "Identifying anomalies..."),
        (90, "Generating synthesis..."),
        (100, "Complete"),
    ]

    for progress, message in phases:
        await ctx.task.update(progress=progress, message=message)
        # ... do work for this phase ...
```

### 7.6 Cancellation Handling

Always check for cancellation at natural checkpoints:

```python
@mcp.tool(task=True)
async def fetch_events(..., ctx: Context) -> dict:
    for i, day in enumerate(date_range):
        # Check at the start of each iteration
        if ctx.task.is_cancelled():
            return {
                "status": "cancelled",
                "partial_result": {
                    "rows_fetched": total_rows,
                    "days_completed": i,
                    "table": table,
                },
                "message": f"Cancelled after {i}/{len(date_range)} days"
            }

        # ... fetch logic ...
```

**Best practices for cancellation:**
1. Check before expensive operations, not after
2. Return partial results when cancelled (don't discard work)
3. Include metadata about how much was completed
4. Clean up any temporary state

### 7.7 Storage Considerations

For a local MCP server, **in-memory task storage** is sufficient:

```python
# Default: in-memory storage (no external dependencies)
mcp = FastMCP("mp-mcp-server")

# Optional: Redis for persistence across restarts
# Only needed if users require:
# - Task history after server restart
# - Multiple server instances
# - Long-running task recovery
from docket import Docket
mcp = FastMCP(
    "mp-mcp-server",
    task_runner=Docket(redis_url="redis://localhost:6379")
)
```

**Recommendation**: Start with in-memory (zero dependencies). Add Redis only if users report losing task state during server restarts as a pain point.

### 7.8 Client Compatibility

Task-enabled tools gracefully degrade for clients that don't support tasks:

| Client Support | Behavior |
|----------------|----------|
| **Supports tasks** | Returns `ToolTask` immediately, client polls for progress |
| **No task support** | Executes synchronously, blocks until complete |

The server handles this automatically—no conditional code needed in tool implementations.

---

## Phase 8: Implementation Roadmap

### Priority Matrix

| Enhancement | Value | Effort | Priority |
|------------|-------|--------|----------|
| Sampling: `diagnose_metric_drop` | Very High | High | P0 |
| Sampling: `ask_mixpanel` NL interface | Very High | High | P0 |
| Composed: `product_health_dashboard` | High | Medium | P1 |
| Composed: `gqm_investigation` | High | Medium | P1 |
| Task-enabled: `fetch_events`, `fetch_profiles` | High | Low | P1 |
| Elicitation: `safe_large_fetch` | Medium | Low | P1 |
| Task-enabled: composed tools | Medium | Low | P2 |
| Resource templates (retention, trends) | Medium | Low | P2 |
| Prompts: AARRR + GQM frameworks | Medium | Low | P2 |
| Middleware: Caching | Medium | Medium | P2 |
| Middleware: Rate limiting | High | Medium | P2 |
| Elicitation: `guided_analysis` | Medium | High | P3 |
| Composed: `cohort_comparison` | Medium | Medium | P3 |
| Middleware: Audit logging | Low | Low | P3 |

### Phase 8.1: Core Intelligence (Week 1-2)

**Goal**: Add sampling-powered intelligent tools.

1. Implement sampling handler fallback configuration
2. Build `diagnose_metric_drop` with full workflow
3. Build `ask_mixpanel` natural language interface
4. Add tests for sampling flows (mock LLM responses)
5. Documentation for intelligent tools

**Deliverables**:
- 2 new intelligent tools
- Sampling integration tested
- Usage examples documented

### Phase 8.2: Composed Tools & Task-Enabling (Week 3-4)

**Goal**: Higher-order tools that orchestrate workflows, with progress reporting for long operations.

1. Implement `product_health_dashboard` (AARRR)
2. Implement `gqm_investigation` (GQM framework)
3. Implement `funnel_optimization_report`
4. Add `task=True` to `fetch_events` and `fetch_profiles` with progress reporting
5. Add `task=True` to composed tools with multi-query progress
6. Add comprehensive tests (including task progress and cancellation)
7. Document composed tool and task patterns

**Deliverables**:
- 3 new composed tools
- 4+ task-enabled tools with progress reporting
- GQM + AARRR framework integration
- Cancellation handling for all long-running operations
- Workflow documentation

### Phase 8.3: Interactive & Resources (Week 5-6)

**Goal**: Elicitation and enhanced resources.

1. Implement `safe_large_fetch` with confirmation
2. Implement `guided_analysis` interactive session
3. Add dynamic resource templates
4. Add recipe resources
5. Enhanced prompts with frameworks

**Deliverables**:
- 2 elicitation-enabled tools
- 5+ new resource templates
- 3+ framework prompts

### Phase 8.4: Infrastructure (Week 7-8)

**Goal**: Middleware and production readiness.

1. Implement caching middleware
2. Implement rate limiting middleware
3. Implement audit logging middleware
4. Performance testing and optimization
5. Production deployment documentation

**Deliverables**:
- 3 middleware components
- Performance benchmarks
- Deployment guide

---

## Testing Strategy

### Unit Tests

```python
# tests/unit/test_intelligent_tools.py

import pytest
from unittest.mock import AsyncMock, patch

@pytest.fixture
def mock_sampling():
    """Mock ctx.sample() for testing."""
    async def mock_sample(*args, **kwargs):
        return AsyncMock(text='{"answer": "mocked response"}')
    return mock_sample

async def test_diagnose_metric_drop_confirms_drop(mock_sampling):
    """diagnose_metric_drop identifies significant drops."""
    # ... test implementation

async def test_ask_mixpanel_parses_intent(mock_sampling):
    """ask_mixpanel correctly interprets questions."""
    # ... test implementation

async def test_ask_mixpanel_handles_invalid_plan(mock_sampling):
    """ask_mixpanel gracefully handles malformed LLM responses."""
    # ... test implementation
```

### Integration Tests

```python
# tests/integration/test_composed_workflows.py

async def test_product_health_dashboard_complete_flow(client):
    """Full AARRR dashboard generation."""
    result = await client.call_tool("product_health_dashboard", {
        "acquisition_event": "signup",
    })

    assert "metrics" in result.data
    assert "acquisition" in result.data["metrics"]
    assert "retention" in result.data["metrics"]

async def test_retention_benchmark_with_industry(client):
    """Retention benchmarking against industry data."""
    result = await client.call_tool("retention_benchmark", {
        "born_event": "signup",
        "industry": "saas_b2c",
    })

    assert "retention_rates" in result.data
    assert "assessment" in result.data
```

---

## Documentation Requirements

### User Documentation

1. **Getting Started with Intelligent Tools**
   - How sampling works
   - Example conversations
   - Best practices for prompts

2. **Composed Tool Reference**
   - Each tool with examples
   - Expected outputs
   - Common use cases

3. **Resource Templates**
   - Available templates
   - How to use dynamic resources
   - Caching behavior

### Developer Documentation

1. **Adding New Intelligent Tools**
   - Sampling API usage
   - Response parsing patterns
   - Error handling

2. **Middleware Development**
   - Middleware interface
   - Ordering considerations
   - Testing strategies

---

## Success Metrics

### Quantitative

| Metric | Target | Measurement |
|--------|--------|-------------|
| Tool invocation success rate | >95% | Audit logs |
| Average query response time | <5s for primitives, <30s for composed | Performance monitoring |
| Sampling fallback usage | <20% | Track fallback invocations |
| Cache hit rate | >50% for cacheable tools | Cache middleware stats |

### Qualitative

- Users can answer complex questions with single tool calls
- Recommendations from intelligent tools are actionable
- Interactive workflows feel natural, not frustrating
- Error messages guide users to solutions

---

## Appendix A: MCP Feature Reference

| Feature | Spec Version | FastMCP Support | Our Usage |
|---------|--------------|-----------------|-----------|
| Tools | Core | Full | 27 primitive + N composed |
| Resources | Core | Full | 6 static + N templates |
| Prompts | Core | Full | 4 current + N framework |
| Sampling | 2024-11 | Full | Intelligent tools |
| Elicitation | 2025-06 | Full | Interactive workflows |
| Middleware | FastMCP 2.0 | Full | Caching, rate limiting, audit |
| Progress | Core | Full | Long-running fetches |
| Cancellation | Core | Full | Abort long operations |

---

## Appendix B: Related Documents

- [2026-01-12-mcp-server-implementation-plan.md](2026-01-12-mcp-server-implementation-plan.md) - Original MCP server implementation
- [mixpanel_data-design.md](../mixpanel_data-design.md) - Core library architecture
- [mp-cli-project-spec.md](../mp-cli-project-spec.md) - CLI specification
- [mixpanel-http-api-specification.md](../mixpanel-http-api-specification.md) - Mixpanel API reference

---

## Appendix C: Example Conversations

### Example 1: Diagnosing a Drop

```
User: Why did our signups drop last Tuesday?

Claude: I'll analyze this using the diagnose_metric_drop tool.

[Calls diagnose_metric_drop("signup", "2024-01-09")]

Based on my analysis:

**Drop Confirmed**: Signups dropped 34% on Tuesday (from avg 1,250/day to 825).

**Primary Driver**: Mobile iOS users from paid Facebook ads dropped 65%.
- This segment contributed 78% of the total decline.
- Desktop and Android remained stable.

**Recommendations**:
1. Check if iOS app was experiencing issues (crash reports, reviews)
2. Review Facebook ad creative that went live Monday
3. Verify iOS deep linking is working correctly

Would you like me to investigate the Facebook ad performance in more detail?
```

### Example 2: GQM Investigation

```
User: Why is retention declining?

Claude: [Calls gqm_investigation("Why is retention declining?")]

I conducted a structured investigation using the GQM framework.

**Goal**: Understand the root cause of declining user retention
**AARRR Category**: Retention

**Questions & Findings**:

| # | Question | Query | Finding |
|---|----------|-------|---------|
| 1 | What is the magnitude and trend? | retention | D7 dropped 28% → 21% over 3 weeks |
| 2 | Which segments are affected? | property_counts | Free tier dropped 22%, Premium only 4% |
| 3 | What events differ for retained users? | event_counts | Retained users do 3x more "Dashboard views" |
| 4 | Has acquisition mix changed? | segmentation | Paid search up from 20% → 35% of signups |

**Synthesis**: Retention decline is primarily driven by acquisition mix shift. Paid search now represents 35% of signups (was 20%), bringing lower-intent users who are 40% less likely to retain. Free tier users are most affected because they rely on organic feature discovery.

**Next Steps**:
1. Deep-dive: Compare feature usage between retained vs churned users
2. Segment: Analyze retention by acquisition source
3. Experiment: Test re-engagement campaigns for at-risk users

Would you like me to drill into any of these findings?
```

### Example 3: Natural Language Query

```
User: What features do our best users engage with?

Claude: [Calls ask_mixpanel with the question]

I analyzed your data to identify what distinguishes power users.

**Definition Used**: Power users = top 10% by event frequency (50+ events/week)

**Top Features for Power Users vs Regular Users**:
| Feature | Power Users | Regular Users | Difference |
|---------|-------------|---------------|------------|
| Dashboard views | 12.4/week | 2.1/week | 6x |
| Report exports | 8.2/week | 0.3/week | 27x |
| Team collaboration | 5.1/week | 0.1/week | 51x |

**Insight**: Collaboration features are the strongest predictor of power user behavior. Users who share or collaborate are 51x more likely to become power users.

**Recommendation**: Focus onboarding on getting users to invite a teammate within the first week.

Follow-up questions I can help with:
- What's the retention difference between collaborators vs solo users?
- At what point in the journey do users typically start collaborating?
```

---

*Document Version: 1.0*
*Created: 2026-01-13*
*Status: Ready for Review*
