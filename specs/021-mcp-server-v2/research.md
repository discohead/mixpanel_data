# Research: MCP Server v2 - Intelligent Analytics Platform

**Feature Branch**: `021-mcp-server-v2` | **Date**: 2026-01-13

## Overview

This document consolidates research findings for implementing intelligent tools, elicitation workflows, task-enabled operations, and middleware in the `mp-mcp-server` using FastMCP 2.x APIs.

---

## 1. Sampling API (`ctx.sample()`)

### Decision
Use FastMCP's built-in `ctx.sample()` method for LLM synthesis in intelligent tools, with graceful degradation when sampling is unavailable.

### Rationale
- FastMCP 2.x provides native sampling support via `ctx.sample()`
- Structured output via `result_type` enables reliable JSON parsing
- Built-in fallback handler support enables graceful degradation

### API Signature

```python
async def sample(
    self,
    messages: str | Sequence[str | SamplingMessage],
    *,
    system_prompt: str | None = None,
    temperature: float | None = None,
    max_tokens: int | None = None,
    model_preferences: ModelPreferences | str | list[str] | None = None,
    tools: Sequence[SamplingTool | Callable[..., Any]] | None = None,
    result_type: type[ResultT] | None = None,
    mask_error_details: bool | None = None,
) -> SamplingResult[ResultT] | SamplingResult[str]
```

### Return Value
- `SamplingResult.text`: Raw text response
- `SamplingResult.result`: Typed result (when `result_type` specified)
- `SamplingResult.history`: All messages exchanged

### Graceful Degradation Pattern

```python
from fastmcp import FastMCP
from fastmcp.client.sampling.handlers.openai import OpenAISamplingHandler

# Configure fallback handler (only used if client doesn't support sampling)
server = FastMCP(
    name="mixpanel",
    sampling_handler=OpenAISamplingHandler(default_model="gpt-4o-mini"),
    sampling_handler_behavior="fallback",  # "fallback" or "always"
)
```

**Implementation Note**: For our use case, we'll check if sampling succeeds and fall back to raw data if it fails, rather than configuring a fallback handler (per user requirement: graceful degradation to raw data).

### Example Usage

```python
from fastmcp import Context

@mcp.tool
async def diagnose_metric_drop(event: str, date: str, ctx: Context) -> dict:
    # Gather data first
    baseline_data = ws.segmentation(event, ...)
    segment_data = ws.property_counts(event, ...)

    # Try sampling for synthesis
    try:
        synthesis = await ctx.sample(
            f"Analyze this metric drop: {json.dumps(data)}",
            system_prompt="You are a Mixpanel analytics expert.",
            max_tokens=1000,
        )
        return {
            "synthesis": synthesis.text,
            "raw_data": data,
        }
    except Exception:
        # Graceful degradation: return raw data
        return {
            "status": "sampling_unavailable",
            "message": "Client does not support sampling. Returning raw data.",
            "raw_data": data,
            "analysis_hints": ["Compare baseline vs current", "Look for segment drops"],
        }
```

### Alternatives Considered
1. **Direct Anthropic API calls**: Rejected because it requires API key management and doesn't integrate with MCP client capabilities.
2. **No sampling at all**: Rejected because it defeats the purpose of intelligent tools.

---

## 2. Elicitation API (`ctx.elicit()`)

### Decision
Use FastMCP's `ctx.elicit()` for interactive workflows requiring user input mid-execution.

### Rationale
- Native MCP protocol support for structured user input
- Type-safe response handling via dataclasses/Pydantic models
- Clean handling of accept/decline/cancel actions

### API Signature

```python
async def elicit(
    self,
    message: str,
    response_type: type[T] | list[str] | dict[str, dict[str, str]] | None = None,
) -> AcceptedElicitation[T] | DeclinedElicitation | CancelledElicitation
```

### Response Types Supported
1. **Scalar types**: `str`, `int`, `bool`
2. **No response**: `None` (approval only)
3. **Constrained options**: `["option1", "option2"]` or `Literal["a", "b"]`
4. **Multi-select**: `[["option1", "option2"]]`
5. **Structured responses**: `dataclass`, `TypedDict`, `BaseModel`

### Result Handling

```python
from fastmcp.server.elicitation import (
    AcceptedElicitation,
    DeclinedElicitation,
    CancelledElicitation,
)

result = await ctx.elicit("Confirm large fetch?", response_type=FetchConfirmation)

match result:
    case AcceptedElicitation(data=confirmation):
        if confirmation.proceed:
            # Execute fetch
            pass
    case DeclinedElicitation():
        return {"status": "declined"}
    case CancelledElicitation():
        return {"status": "cancelled"}
```

### Example: Safe Large Fetch

```python
from dataclasses import dataclass

@dataclass
class FetchConfirmation:
    proceed: bool
    reduce_scope: bool = False
    new_limit: int | None = None

@mcp.tool
async def safe_large_fetch(from_date: str, to_date: str, ctx: Context) -> dict:
    estimated_events = estimate_volume(from_date, to_date)

    if estimated_events > 100_000:
        result = await ctx.elicit(
            f"This will fetch ~{estimated_events:,} events. Proceed?",
            response_type=FetchConfirmation,
        )

        if result.action != "accept" or not result.data.proceed:
            return {"status": "cancelled", "estimated_events": estimated_events}

        if result.data.reduce_scope:
            limit = result.data.new_limit

    # Proceed with fetch
    return ws.fetch_events(from_date, to_date, limit=limit)
```

### Alternatives Considered
1. **Always require limit parameter**: Rejected because it burdens users with estimation.
2. **Automatic chunking without confirmation**: Rejected because it doesn't give user control.

---

## 3. Task-Enabled Tools (`@mcp.tool(task=True)`)

### Decision
Use FastMCP's task system with `Progress` dependency for long-running operations.

### Rationale
- Native progress reporting via MCP protocol
- Built-in cancellation handling via `asyncio.CancelledError`
- In-memory task storage sufficient for single-server deployment

### Configuration

```python
@mcp.tool(task=True)  # Equivalent to TaskConfig(mode="optional")
async def fetch_events(..., progress: Progress = Progress()) -> dict:
    ...
```

### Progress Reporting

```python
from fastmcp.dependencies import Progress

@mcp.tool(task=True)
async def fetch_events(
    from_date: str,
    to_date: str,
    progress: Progress = Progress(),
    ctx: Context,
) -> dict:
    days = calculate_date_range(from_date, to_date)
    await progress.set_total(len(days))

    for i, day in enumerate(days):
        await progress.set_message(f"Fetching {day}")
        # Do work...
        await progress.increment()

    return {"status": "complete", "rows": total_rows}
```

### Cancellation Handling

```python
import asyncio

@mcp.tool(task=True)
async def fetch_events(...) -> dict:
    total_rows = 0
    completed_days = 0

    try:
        for day in days:
            result = ws.fetch_events(day, day, append=True)
            total_rows += result.row_count
            completed_days += 1
            await progress.increment()
    except asyncio.CancelledError:
        # Return partial results
        return {
            "status": "cancelled",
            "partial_result": {
                "rows_fetched": total_rows,
                "days_completed": completed_days,
            },
        }

    return {"status": "complete", "rows": total_rows}
```

### Fallback Behavior
- Clients that don't support tasks receive synchronous execution
- No code changes needed for fallback

### Alternatives Considered
1. **Redis-backed task storage (Docket)**: Rejected per user requirement for in-memory only.
2. **Manual threading**: Rejected because FastMCP provides native support.

---

## 4. Middleware Layer

### Decision
Use FastMCP's built-in middleware classes for caching, rate limiting, and logging.

### Rationale
- Native integration with MCP request lifecycle
- Pre-built implementations available for common use cases
- Composable middleware chain

### Available Middleware Classes

| Middleware | Purpose | Import Path |
|------------|---------|-------------|
| `ResponseCachingMiddleware` | Cache tool/resource results | `fastmcp.server.middleware.caching` |
| `RateLimitingMiddleware` | Token bucket rate limiting | `fastmcp.server.middleware.rate_limiting` |
| `SlidingWindowRateLimitingMiddleware` | Time-window rate limiting | `fastmcp.server.middleware.rate_limiting` |
| `LoggingMiddleware` | Human-readable audit logs | `fastmcp.server.middleware.logging` |
| `StructuredLoggingMiddleware` | JSON-structured logs | `fastmcp.server.middleware.logging` |

### Middleware Registration Order

```python
from fastmcp import FastMCP
from fastmcp.server.middleware.caching import ResponseCachingMiddleware
from fastmcp.server.middleware.rate_limiting import RateLimitingMiddleware
from fastmcp.server.middleware.logging import LoggingMiddleware

mcp = FastMCP("mixpanel", lifespan=lifespan)

# Order: Logging (outermost) → Rate Limiting → Caching (innermost)
mcp.add_middleware(LoggingMiddleware(include_payloads=True))
mcp.add_middleware(RateLimitingMiddleware(max_requests_per_second=1.0))
mcp.add_middleware(ResponseCachingMiddleware())
```

### Caching Configuration

```python
from fastmcp.server.middleware.caching import (
    ResponseCachingMiddleware,
    CallToolSettings,
    ListToolsSettings,
)

mcp.add_middleware(ResponseCachingMiddleware(
    list_tools_settings=ListToolsSettings(ttl=300),  # 5 min for discovery
    call_tool_settings=CallToolSettings(
        included_tools=["list_events", "list_funnels", "list_cohorts"],
        ttl=300,
    ),
))
```

### Rate Limiting for Mixpanel API Limits

**Mixpanel Rate Limits**:
- Query API: 60 queries/hour, 5 concurrent
- Export API: 60 queries/hour, 3/second, 100 concurrent

```python
# Query API tools
QUERY_API_TOOLS = {
    "segmentation", "funnel", "retention", "jql",
    "event_counts", "property_counts", "activity_feed", "frequency",
}

# Export API tools
EXPORT_API_TOOLS = {"fetch_events", "fetch_profiles", "stream_events", "stream_profiles"}
```

**Note**: FastMCP's built-in rate limiters are per-server, not per-API-type. For Mixpanel's dual-limit structure, we may need a custom middleware that applies different limits based on tool name.

### Custom Middleware Pattern

```python
from fastmcp.server.middleware import Middleware, MiddlewareContext

class MixpanelRateLimitMiddleware(Middleware):
    def __init__(self):
        self.query_limiter = TokenBucket(rate=60/3600, capacity=5)
        self.export_limiter = TokenBucket(rate=60/3600, capacity=100)

    async def on_call_tool(self, context: MiddlewareContext, call_next):
        tool_name = context.message.params.get("name")

        if tool_name in QUERY_API_TOOLS:
            await self.query_limiter.acquire()
        elif tool_name in EXPORT_API_TOOLS:
            await self.export_limiter.acquire()

        return await call_next(context)
```

### Alternatives Considered
1. **External rate limiting (nginx/envoy)**: Rejected because it adds deployment complexity.
2. **No rate limiting**: Rejected because it risks API quota exhaustion.

---

## 5. Dynamic Resources

### Decision
Use FastMCP's parameterized resource templates for dynamic analytics views.

### Implementation Pattern

```python
@mcp.resource("analysis://retention/{event}/weekly")
async def retention_weekly(event: str, ctx: Context) -> str:
    ws = get_workspace(ctx)
    result = ws.retention(
        born_event=event,
        return_event=event,
        from_date=...,
        to_date=...,
        unit="week",
    )
    return json.dumps(result.to_dict(), indent=2)
```

### Resource Templates to Implement
- `analysis://retention/{event}/weekly`
- `analysis://trends/{event}/{days}`
- `users://{distinct_id}/journey`
- `recipes://weekly-review`
- `recipes://churn-investigation`

---

## 6. Framework Prompts

### Decision
Extend existing prompts with GQM, AARRR, experiment analysis, and data quality frameworks.

### Implementation Pattern

```python
@mcp.prompt
def gqm_decomposition(goal: str) -> str:
    return f"""You are conducting a structured analytics investigation using GQM.

## Your Goal
{goal}

## GQM Framework
- Goal (Conceptual): What you want to understand
- Question (Operational): 3-5 specific sub-questions
- Metric (Quantitative): Mixpanel query for each question

## Available Query Types
1. segmentation(event, from_date, to_date) - Time series
2. retention(born_event, return_event, ...) - Cohort curves
3. funnel(funnel_id, ...) - Conversion analysis
4. property_counts(event, property, ...) - Distributions

Now investigate: {goal}
"""
```

---

## Summary of Technology Choices

| Capability | FastMCP Feature | Version Required |
|------------|-----------------|------------------|
| LLM Sampling | `ctx.sample()` | 2.0.0+ |
| Structured Sampling | `result_type` param | 2.14.1+ |
| User Elicitation | `ctx.elicit()` | 2.x |
| Task Execution | `@mcp.tool(task=True)` | 2.x |
| Progress Reporting | `Progress` dependency | 2.x |
| Middleware | `Middleware` base class | 2.9.0+ |
| Built-in Caching | `ResponseCachingMiddleware` | 2.9.0+ |
| Built-in Rate Limiting | `RateLimitingMiddleware` | 2.9.0+ |
| Built-in Logging | `LoggingMiddleware` | 2.9.0+ |

**Minimum FastMCP Version**: 2.14.1 (for structured sampling support)

---

## Open Questions Resolved

| Question | Resolution |
|----------|------------|
| How to detect sampling support? | Use try/except; fallback handlers only configure server-side LLM |
| In-memory vs Redis for tasks? | In-memory per user requirement |
| Separate rate limiters per API? | Custom middleware needed for Mixpanel's dual-limit structure |
| Feature flags for Tier 2/3? | No flags; all tools always available per user requirement |
