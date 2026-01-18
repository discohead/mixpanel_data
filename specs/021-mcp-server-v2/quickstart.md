# Quickstart: MCP Server v2 - Intelligent Analytics Platform

**Feature Branch**: `021-mcp-server-v2` | **Date**: 2026-01-13

## Overview

This guide helps developers get started implementing intelligent tools, middleware, and enhanced resources for the `mp-mcp-server`.

---

## Prerequisites

- Python 3.10+
- FastMCP 2.14.1+ (for structured sampling support)
- mixpanel_data library with valid credentials configured
- Development environment with `just`, `uv`

```bash
# Verify FastMCP version
uv pip show fastmcp | grep Version
# Should be >= 2.14.1
```

---

## Key Concepts

### Tool Tiers

| Tier | Description | Key API |
|------|-------------|---------|
| **Tier 1** | Primitive tools (existing 27) | Direct Workspace calls |
| **Tier 2** | Composed tools | Orchestrate multiple Tier 1 |
| **Tier 3** | Intelligent tools | `ctx.sample()` for LLM synthesis |
| **Interactive** | Elicitation workflows | `ctx.elicit()` for user input |

### Graceful Degradation Pattern

Intelligent tools use sampling for synthesis but must work without it:

```python
from fastmcp import Context

@mcp.tool
async def diagnose_metric_drop(event: str, date: str, ctx: Context) -> dict:
    # 1. Gather data (always succeeds)
    raw_data = gather_diagnosis_data(event, date)

    # 2. Try sampling for synthesis
    try:
        synthesis = await ctx.sample(
            f"Analyze this drop: {json.dumps(raw_data)}",
            system_prompt="You are a Mixpanel analytics expert.",
            max_tokens=1000,
        )
        return {
            "status": "success",
            "findings": synthesis.text,
            "raw_data": raw_data,
        }
    except Exception:
        # 3. Graceful degradation: return raw data with hints
        return {
            "status": "sampling_unavailable",
            "message": "Client does not support sampling. Returning raw data.",
            "raw_data": raw_data,
            "analysis_hints": [
                "Compare baseline vs current period",
                "Look for segment-level drops",
                "Check for external factors",
            ],
        }
```

---

## Quick Examples

### Tier 2: Composed Tool

```python
@mcp.tool
async def product_health_dashboard(
    acquisition_event: str = "signup",
    from_date: str | None = None,
    to_date: str | None = None,
    ctx: Context = None,
) -> dict:
    """Generate AARRR product health dashboard."""
    ws = get_workspace(ctx)

    # Compute each AARRR category
    acquisition = compute_acquisition(ws, acquisition_event, from_date, to_date)
    retention = compute_retention(ws, acquisition_event, from_date, to_date)

    return {
        "period": {"from": from_date, "to": to_date},
        "acquisition": acquisition,
        "retention": retention,
        # ... other categories
    }
```

### Elicitation Workflow

```python
from dataclasses import dataclass

@dataclass
class FetchConfirmation:
    proceed: bool
    reduce_scope: bool = False
    new_limit: int | None = None

@mcp.tool
async def safe_large_fetch(
    from_date: str,
    to_date: str,
    ctx: Context,
) -> dict:
    """Fetch events with confirmation for large datasets."""
    estimated = estimate_event_count(from_date, to_date)

    if estimated > 100_000:
        result = await ctx.elicit(
            f"This will fetch ~{estimated:,} events. Proceed?",
            response_type=FetchConfirmation,
        )

        if result.action != "accept" or not result.data.proceed:
            return {"status": "cancelled", "estimated_events": estimated}

        if result.data.reduce_scope:
            # Use reduced limit
            limit = result.data.new_limit

    # Proceed with fetch
    return ws.fetch_events(from_date, to_date, limit=limit)
```

### Task-Enabled Tool

```python
from fastmcp.dependencies import Progress

@mcp.tool(task=True)
async def fetch_events(
    from_date: str,
    to_date: str,
    progress: Progress = Progress(),
    ctx: Context = None,
) -> dict:
    """Fetch events with progress reporting."""
    ws = get_workspace(ctx)
    days = calculate_date_range(from_date, to_date)

    await progress.set_total(len(days))
    total_rows = 0

    try:
        for day in days:
            await progress.set_message(f"Fetching {day}")
            result = ws.fetch_events(day, day, append=True)
            total_rows += result.row_count
            await progress.increment()
    except asyncio.CancelledError:
        return {"status": "cancelled", "rows_fetched": total_rows}

    return {"status": "complete", "rows": total_rows}
```

### Middleware Configuration

```python
from fastmcp import FastMCP
from fastmcp.server.middleware.caching import ResponseCachingMiddleware
from fastmcp.server.middleware.rate_limiting import RateLimitingMiddleware
from fastmcp.server.middleware.logging import LoggingMiddleware

mcp = FastMCP("mixpanel", lifespan=lifespan)

# Order: Logging (outermost) → Rate Limiting → Caching (innermost)
mcp.add_middleware(LoggingMiddleware(include_payloads=True))
mcp.add_middleware(RateLimitingMiddleware(max_requests_per_second=1.0))
mcp.add_middleware(ResponseCachingMiddleware(
    call_tool_settings=CallToolSettings(
        included_tools=["list_events", "list_funnels", "list_cohorts"],
        ttl=300,
    ),
))
```

---

## File Organization

New code goes in these directories:

```
mp-mcp-server/src/mp_mcp_server/
├── tools/
│   ├── intelligent/          # Tier 3 tools (sampling-powered)
│   │   ├── __init__.py
│   │   ├── diagnose.py       # diagnose_metric_drop
│   │   ├── ask.py            # ask_mixpanel
│   │   └── funnel_report.py  # funnel_optimization_report
│   ├── composed/             # Tier 2 tools
│   │   ├── __init__.py
│   │   ├── gqm.py            # gqm_investigation
│   │   ├── dashboard.py      # product_health_dashboard
│   │   └── cohort.py         # cohort_comparison
│   └── interactive/          # Elicitation tools
│       ├── __init__.py
│       ├── guided.py         # guided_analysis
│       └── safe_fetch.py     # safe_large_fetch
├── middleware/               # Middleware layer
│   ├── __init__.py
│   ├── caching.py
│   ├── rate_limiting.py
│   └── audit.py
└── types.py                  # Shared result types
```

---

## Testing Pattern

All tools require unit tests with mocked dependencies:

```python
import pytest
from unittest.mock import AsyncMock, MagicMock

@pytest.fixture
def mock_context():
    ctx = MagicMock()
    ctx.sample = AsyncMock(return_value=MagicMock(text="Analysis result"))
    return ctx

@pytest.fixture
def mock_workspace():
    ws = MagicMock()
    ws.segmentation.return_value = {"data": {}}
    return ws

async def test_diagnose_metric_drop_with_sampling(mock_context, mock_workspace):
    """Test diagnosis with sampling available."""
    result = await diagnose_metric_drop(
        event="signup",
        date="2026-01-10",
        ctx=mock_context,
    )
    assert result["status"] == "success"
    assert "findings" in result

async def test_diagnose_metric_drop_without_sampling(mock_context, mock_workspace):
    """Test graceful degradation when sampling unavailable."""
    mock_context.sample.side_effect = Exception("Sampling not supported")

    result = await diagnose_metric_drop(
        event="signup",
        date="2026-01-10",
        ctx=mock_context,
    )
    assert result["status"] == "sampling_unavailable"
    assert "raw_data" in result
    assert "analysis_hints" in result
```

---

## Common Patterns

### Getting Workspace from Context

```python
from mp_mcp_server.context import get_workspace

@mcp.tool
async def my_tool(ctx: Context) -> dict:
    ws = get_workspace(ctx)
    # Use ws.segmentation(), ws.retention(), etc.
```

### Date Range Handling

```python
from datetime import datetime, timedelta

def default_date_range(days_back: int = 30) -> tuple[str, str]:
    today = datetime.now().date()
    from_date = (today - timedelta(days=days_back)).isoformat()
    to_date = today.isoformat()
    return from_date, to_date
```

### Error Handling

```python
from mp_mcp_server.errors import MixpanelError, AuthenticationError

@mcp.tool
async def my_tool(ctx: Context) -> dict:
    try:
        result = ws.some_operation()
        return {"status": "success", "data": result}
    except AuthenticationError:
        return {"status": "error", "message": "Authentication failed"}
    except MixpanelError as e:
        return {"status": "error", "message": str(e)}
```

---

## Next Steps

1. Review [research.md](research.md) for FastMCP API details
2. Review [data-model.md](data-model.md) for result type definitions
3. Review [contracts/tools.yaml](contracts/tools.yaml) for tool schemas
4. Run `just check` to verify environment setup
5. Start implementation following existing patterns in `mp-mcp-server/`
