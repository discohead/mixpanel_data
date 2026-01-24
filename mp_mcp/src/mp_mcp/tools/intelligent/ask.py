"""Natural language analytics query tool.

This module provides the ask_mixpanel tool that translates natural
language questions into Mixpanel queries and synthesizes the results.

Uses ctx.sample() for LLM synthesis with graceful degradation when
sampling is unavailable.

Example:
    Ask Claude: "What features do our best users engage with?"
    Claude uses: ask_mixpanel(question="What features do our best users engage with?")
"""

import json
from dataclasses import asdict
from datetime import datetime, timedelta
from typing import Any

from fastmcp import Context

from mp_mcp.context import get_workspace
from mp_mcp.errors import handle_errors
from mp_mcp.server import mcp
from mp_mcp.types import ExecutionPlan, QuerySpec

# Plan generation prompt template
PLAN_GENERATION_PROMPT = """You are a Mixpanel analytics expert. Given a natural language question, generate an execution plan to answer it.

## Question
{question}

## Available Query Methods
1. segmentation(event, from_date, to_date, on=None, unit="day", where=None) - Time series event counts
2. retention(born_event, return_event, from_date, to_date, unit="day") - Cohort retention curves
3. funnel(funnel_id, from_date, to_date) - Conversion funnel analysis (requires saved funnel)
4. property_counts(event, property_name, from_date, to_date, type="general", limit=10) - Property distributions
5. event_counts(events, from_date, to_date, type="general") - Compare multiple events
6. activity_feed(distinct_id, from_date=None, to_date=None) - User event history (requires user ID)
7. jql(script, params) - Custom JavaScript queries (advanced)

## Available Events (for reference)
{available_events}

## Default Date Range
from_date: {from_date}
to_date: {to_date}

## Your Task
Generate an execution plan as JSON:
{{
    "intent": "Brief description of what the user wants to know",
    "query_type": "retention|conversion|trend|distribution|comparison",
    "queries": [
        {{
            "method": "segmentation|retention|funnel|property_counts|event_counts|activity_feed|jql",
            "params": {{...method parameters...}}
        }}
    ],
    "date_range": {{"from_date": "YYYY-MM-DD", "to_date": "YYYY-MM-DD"}},
    "comparison_needed": true/false,
    "reasoning": "Why these queries will answer the question"
}}

Important:
- Use the available events when possible
- Keep queries focused and minimal
- Prefer segmentation and property_counts for most questions
- Use retention for questions about user return behavior
- Avoid jql unless necessary for complex transformations
"""

# Synthesis prompt template
SYNTHESIS_PROMPT_TEMPLATE = """You are a Mixpanel analytics expert. Synthesize the query results to answer the user's question.

## Original Question
{question}

## Execution Plan
{plan}

## Query Results
{results}

## Your Task
Provide a clear, actionable answer to the question based on the data. Include:
1. A direct answer to the question
2. Key metrics and numbers that support your answer
3. Any notable patterns or insights
4. Suggested follow-up questions if relevant

Keep your response concise but complete. Focus on what the data tells us, not how we got it.
"""

# Analysis hints for graceful degradation
ANALYSIS_HINTS: list[str] = [
    "Review the query results to identify relevant patterns",
    "Look for trends in the segmentation data",
    "Compare metrics across different dimensions",
    "Consider the time range and any seasonal effects",
    "Look for segments with unusual behavior",
    "Cross-reference multiple query results if available",
]


def _get_default_date_range(days_back: int = 30) -> tuple[str, str]:
    """Get default date range for queries.

    Args:
        days_back: Number of days to look back.

    Returns:
        Tuple of (from_date, to_date) as strings.
    """
    today = datetime.now().date()
    from_date = (today - timedelta(days=days_back)).isoformat()
    to_date = today.isoformat()
    return from_date, to_date


def _get_available_events(ctx: Context, limit: int = 20) -> list[str]:
    """Get list of available events from the workspace.

    Args:
        ctx: FastMCP context with workspace access.
        limit: Maximum number of events to return.

    Returns:
        List of event names.
    """
    try:
        ws = get_workspace(ctx)
        events = ws.events()
        return events[:limit] if len(events) > limit else events
    except Exception:
        return []


async def _generate_execution_plan(
    ctx: Context,
    question: str,
    from_date: str | None = None,
    to_date: str | None = None,
) -> ExecutionPlan:
    """Generate an execution plan from a natural language question.

    Uses LLM sampling to interpret the question and generate query plan.

    Args:
        ctx: FastMCP context with workspace access.
        question: Natural language question to answer.
        from_date: Optional start date for queries.
        to_date: Optional end date for queries.

    Returns:
        ExecutionPlan with queries to execute.

    Raises:
        Exception: If plan generation fails.
    """
    # Get available events for context
    available_events = _get_available_events(ctx)

    # Use default date range if not specified
    if not from_date or not to_date:
        from_date, to_date = _get_default_date_range()

    prompt = PLAN_GENERATION_PROMPT.format(
        question=question,
        available_events=json.dumps(available_events),
        from_date=from_date,
        to_date=to_date,
    )

    synthesis = await ctx.sample(
        prompt,
        system_prompt="You are a Mixpanel analytics expert. Generate a valid JSON execution plan.",
        max_tokens=1500,
    )

    # Parse the plan
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

    data = json.loads(text)

    # Convert to ExecutionPlan
    queries: list[QuerySpec] = []
    for q in data.get("queries", []):
        queries.append(
            QuerySpec(
                method=q.get("method", "segmentation"),
                params=q.get("params", {}),
            )
        )

    return ExecutionPlan(
        intent=data.get("intent", ""),
        query_type=data.get("query_type", "trend"),
        queries=queries,
        date_range=data.get("date_range", {"from_date": from_date, "to_date": to_date}),
        comparison_needed=data.get("comparison_needed", False),
        reasoning=data.get("reasoning", ""),
    )


def _execute_queries(
    ctx: Context,
    plan: ExecutionPlan,
) -> dict[str, Any]:
    """Execute queries from an execution plan.

    Args:
        ctx: FastMCP context with workspace access.
        plan: ExecutionPlan with queries to execute.

    Returns:
        Dictionary with results for each query.
    """
    ws = get_workspace(ctx)
    results: dict[str, Any] = {}

    for i, query in enumerate(plan.queries):
        query_key = f"query_{i}_{query.method}"
        try:
            method = getattr(ws, query.method, None)
            if method is None:
                results[query_key] = {"error": f"Unknown method: {query.method}"}
                continue

            result = method(**query.params)

            # Convert result to dict if it has to_dict method
            if hasattr(result, "to_dict"):
                results[query_key] = result.to_dict()
            elif hasattr(result, "raw"):
                results[query_key] = result.raw
            else:
                results[query_key] = result

        except Exception as e:
            results[query_key] = {"error": str(e)}

    return results


@mcp.tool
@handle_errors
async def ask_mixpanel(
    ctx: Context,
    question: str,
    from_date: str | None = None,
    to_date: str | None = None,
) -> dict[str, Any]:
    """Answer natural language analytics questions.

    Interprets a natural language question, generates a query plan,
    executes the queries, and synthesizes the results into an answer.

    Uses LLM sampling for plan generation and synthesis when available;
    gracefully degrades to raw query results when sampling is unavailable.

    Args:
        ctx: FastMCP context with workspace access.
        question: Natural language question about your analytics data.
        from_date: Optional start date for analysis (YYYY-MM-DD).
            Defaults to 30 days ago.
        to_date: Optional end date for analysis (YYYY-MM-DD).
            Defaults to today.

    Returns:
        Dictionary containing:
        - status: "success", "partial", or "sampling_unavailable"
        - answer: Natural language answer (when sampling available)
        - plan: The execution plan that was generated
        - results: Raw query results for transparency
        - analysis_hints: Manual analysis guidance (when sampling unavailable)

    Example:
        Ask: "What features do our best users engage with?"
        Uses: ask_mixpanel(question="What features do our best users engage with?")

        Ask: "How has signup retention changed this quarter?"
        Uses: ask_mixpanel(
            question="How has signup retention changed?",
            from_date="2025-10-01",
            to_date="2026-01-13",
        )
    """
    # Use default date range if not specified
    if not from_date or not to_date:
        from_date, to_date = _get_default_date_range()

    # Step 1: Generate execution plan
    try:
        plan = await _generate_execution_plan(ctx, question, from_date, to_date)
    except Exception as e:
        # If plan generation fails, try a simple fallback
        error_msg = str(e)
        if "sampling" in error_msg.lower() or "not supported" in error_msg.lower():
            return {
                "status": "sampling_unavailable",
                "message": "Client does not support sampling. Cannot generate query plan.",
                "question": question,
                "analysis_hints": [
                    "Try using the segmentation, retention, or property_counts tools directly",
                    "Start with top_events to see what events are available",
                    "Use list_events and list_properties to explore the schema",
                ],
            }
        return {
            "status": "error",
            "message": f"Failed to generate execution plan: {error_msg}",
            "question": question,
        }

    # Step 2: Execute queries
    query_results = _execute_queries(ctx, plan)

    # Step 3: Synthesize results
    try:
        synthesis_prompt = SYNTHESIS_PROMPT_TEMPLATE.format(
            question=question,
            plan=json.dumps(asdict(plan), indent=2),
            results=json.dumps(query_results, indent=2),
        )

        synthesis = await ctx.sample(
            synthesis_prompt,
            system_prompt="You are a Mixpanel analytics expert. Provide a clear, data-driven answer.",
            max_tokens=2000,
        )

        return {
            "status": "success",
            "answer": synthesis.text,
            "plan": asdict(plan),
            "results": query_results,
        }

    except Exception as e:
        # Synthesis failed but we have plan and results
        error_msg = str(e)
        if "sampling" in error_msg.lower() or "not supported" in error_msg.lower():
            status_msg = "Client does not support sampling for synthesis."
        else:
            status_msg = f"Synthesis failed: {error_msg}"

        return {
            "status": "partial",
            "message": status_msg,
            "plan": asdict(plan),
            "results": query_results,
            "analysis_hints": ANALYSIS_HINTS,
        }
