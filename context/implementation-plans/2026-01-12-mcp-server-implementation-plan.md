# TDD Implementation Plan: FastMCP Server for mixpanel_data

## Summary

Expose `mixpanel_data` library capabilities as an MCP (Model Context Protocol) server using FastMCP, enabling LLM applications (Claude Desktop, other MCP clients) to perform Mixpanel analytics queries, data discovery, and local SQL analysis.

## Goal

Create a production-ready MCP server that:
1. Exposes all `Workspace` methods as MCP tools and resources
2. Maintains session state for multi-step analytics workflows
3. Provides structured, LLM-friendly outputs
4. Handles authentication via credential resolution
5. Supports both discovery (schema exploration) and analysis (queries)

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           MCP Client (Claude Desktop)                       │
└─────────────────────────────────────────────────────────────────────────────┘
                                       │
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                        FastMCP Server (mp-mcp-server)                       │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │                           MCP Tools                                    │  │
│  │  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────────┐  │  │
│  │  │  Discovery  │ │ Live Query  │ │ Data Fetch  │ │ Local Analysis  │  │  │
│  │  │  • events   │ │ • segment   │ │ • fetch     │ │ • sql           │  │  │
│  │  │  • props    │ │ • funnel    │ │ • stream    │ │ • summarize     │  │  │
│  │  │  • funnels  │ │ • retention │ │             │ │ • sample        │  │  │
│  │  │  • cohorts  │ │ • jql       │ │             │ │ • breakdown     │  │  │
│  │  └─────────────┘ └─────────────┘ └─────────────┘ └─────────────────┘  │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │                          MCP Resources                                 │  │
│  │  • workspace://info          - Current workspace state                 │  │
│  │  • workspace://tables        - List of fetched tables                  │  │
│  │  • schema://events           - All event names                         │  │
│  │  • schema://funnels          - All saved funnels                       │  │
│  │  • schema://cohorts          - All saved cohorts                       │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │                          MCP Prompts                                   │  │
│  │  • analytics_workflow        - Guided analytics session                │  │
│  │  • funnel_analysis           - Conversion funnel template              │  │
│  │  • retention_analysis        - Retention cohort template               │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘
                                       │
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                        mixpanel_data Library                                │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                         Workspace                                    │    │
│  │  Discovery │ Live Query │ Fetch │ Local SQL │ Introspection        │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │    DiscoveryService │ LiveQueryService │ FetcherService             │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │         MixpanelAPIClient          │       StorageEngine (DuckDB)   │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Design Decisions

### 1. Package Structure: **Separate `mp-mcp-server` Package**
- New package `mp-mcp-server` in repository root (sibling to `src/mixpanel_data`)
- Depends on `mixpanel_data` as a library
- Separate installation: `pip install mp-mcp-server`
- Entry point: `mp-mcp-server` command

### 2. Session Management: **Server-Level Workspace Singleton**
- Single `Workspace` instance per server session (lifespan pattern)
- Workspace created on server start, closed on server stop
- Session state persists across tool calls (DuckDB tables, caches)
- Context object provides access to workspace in tools/resources

### 3. Tool Design: **One Tool Per Workspace Method**
- Direct 1:1 mapping between Workspace methods and MCP tools
- Preserves library semantics (no abstraction leakage)
- Docstrings become tool descriptions
- Type hints become JSON schema

### 4. Resource Design: **Read-Only Schema/State Resources**
- Resources for cacheable/static data (events, funnels, cohorts)
- Dynamic resource templates for parameterized queries
- Resource URIs follow `{category}://{identifier}` pattern

### 5. Error Handling: **Structured Error Responses**
- All `MixpanelDataError` exceptions converted to structured tool errors
- Include error code, message, and details for LLM recovery
- Rate limit errors include retry guidance

### 6. Authentication: **Environment/Config Resolution**
- Server uses same credential resolution as library (env → config → default)
- Optional `--account` CLI flag to specify named account
- No credentials in MCP protocol (resolved at server startup)

---

## Critical Files

### New Files to Create

| File | Purpose |
|------|---------|
| `mp-mcp-server/src/mp_mcp_server/__init__.py` | Package initialization |
| `mp-mcp-server/src/mp_mcp_server/server.py` | FastMCP server definition |
| `mp-mcp-server/src/mp_mcp_server/tools/discovery.py` | Discovery tools (events, properties, funnels, cohorts) |
| `mp-mcp-server/src/mp_mcp_server/tools/live_query.py` | Live query tools (segmentation, funnel, retention, jql) |
| `mp-mcp-server/src/mp_mcp_server/tools/fetch.py` | Data fetching tools |
| `mp-mcp-server/src/mp_mcp_server/tools/local.py` | Local SQL and introspection tools |
| `mp-mcp-server/src/mp_mcp_server/resources.py` | MCP resources |
| `mp-mcp-server/src/mp_mcp_server/prompts.py` | MCP prompts |
| `mp-mcp-server/src/mp_mcp_server/context.py` | Context and state management |
| `mp-mcp-server/src/mp_mcp_server/errors.py` | Error handling and conversion |
| `mp-mcp-server/src/mp_mcp_server/cli.py` | CLI entry point |
| `mp-mcp-server/pyproject.toml` | Package configuration |
| `mp-mcp-server/tests/` | Test directory |

### Existing Files Referenced

| File | Purpose |
|------|---------|
| [workspace.py](src/mixpanel_data/workspace.py) | Workspace facade (all public methods) |
| [types.py](src/mixpanel_data/types.py) | Result types with `.to_dict()` |
| [exceptions.py](src/mixpanel_data/exceptions.py) | Exception hierarchy with `.to_dict()` |
| [auth.py](src/mixpanel_data/auth.py) | ConfigManager for credentials |

---

## Implementation Phases (TDD Approach)

Each phase follows strict TDD: **Write tests FIRST, then implement until tests pass.**

---

### Phase 1: Project Scaffolding & Core Server

**Goal:** Create package structure, FastMCP server, and lifespan management.

#### 1.1 Package Setup

Create `mp-mcp-server/pyproject.toml`:
```toml
[project]
name = "mp-mcp-server"
version = "0.1.0"
description = "MCP server for Mixpanel analytics via mixpanel_data"
requires-python = ">=3.11"
dependencies = [
    "fastmcp>=2.0",
    "mixpanel_data>=0.1.0",
]

[project.scripts]
mp-mcp-server = "mp_mcp_server.cli:main"
```

#### 1.2 Tests First

**Create:** `mp-mcp-server/tests/unit/test_server.py`
```python
# Test server creation
def test_server_has_name():
    """Server has correct name."""

def test_server_has_instructions():
    """Server has usage instructions."""

# Test lifespan
async def test_lifespan_creates_workspace():
    """Lifespan creates Workspace on startup."""

async def test_lifespan_closes_workspace():
    """Lifespan closes Workspace on shutdown."""

async def test_lifespan_workspace_available_in_context():
    """Context.workspace returns lifespan-created Workspace."""
```

**Create:** `mp-mcp-server/tests/unit/test_context.py`
```python
def test_get_workspace_returns_workspace():
    """get_workspace() returns Workspace from context."""

def test_get_workspace_raises_without_lifespan():
    """get_workspace() raises if workspace not initialized."""
```

#### 1.3 Implementation

**Create:** `mp-mcp-server/src/mp_mcp_server/server.py`
```python
from contextlib import asynccontextmanager
from fastmcp import FastMCP, Context
from mixpanel_data import Workspace

@asynccontextmanager
async def lifespan(mcp: FastMCP):
    """Manage Workspace lifecycle."""
    workspace = Workspace()  # Uses default credential resolution
    mcp.state["workspace"] = workspace
    try:
        yield
    finally:
        workspace.close()

mcp = FastMCP(
    "Mixpanel Analytics",
    instructions="...",
    lifespan=lifespan,
)
```

**Create:** `mp-mcp-server/src/mp_mcp_server/context.py`
```python
from fastmcp import Context
from mixpanel_data import Workspace

def get_workspace(ctx: Context) -> Workspace:
    """Get Workspace from context state."""
    workspace = ctx.request_context.lifespan_state.get("workspace")
    if workspace is None:
        raise RuntimeError("Workspace not initialized")
    return workspace
```

#### 1.4 Verification
```bash
just test -k test_server
just test -k test_context
just typecheck
```

---

### Phase 2: Discovery Tools

**Goal:** Expose schema discovery methods as MCP tools.

#### 2.1 Tests First

**Create:** `mp-mcp-server/tests/unit/test_tools_discovery.py`
```python
# Test tool registration
def test_list_events_tool_registered():
    """list_events tool is registered on server."""

def test_list_properties_tool_registered():
    """list_properties tool is registered on server."""

# Test tool execution
async def test_list_events_returns_event_names():
    """list_events returns list of event names."""

async def test_list_properties_requires_event():
    """list_properties requires event parameter."""

async def test_list_properties_returns_property_names():
    """list_properties returns property names for event."""

async def test_list_property_values_returns_values():
    """list_property_values returns sample values."""

async def test_list_funnels_returns_funnel_info():
    """list_funnels returns list of FunnelInfo dicts."""

async def test_list_cohorts_returns_cohort_info():
    """list_cohorts returns list of SavedCohort dicts."""

async def test_list_bookmarks_returns_bookmark_info():
    """list_bookmarks returns list of BookmarkInfo dicts."""

async def test_top_events_returns_event_activity():
    """top_events returns list of TopEvent dicts."""

async def test_lexicon_schemas_returns_entity_types():
    """lexicon_schemas returns lexicon entity types."""
```

#### 2.2 Implementation

**Create:** `mp-mcp-server/src/mp_mcp_server/tools/discovery.py`
```python
from fastmcp import Context
from mp_mcp_server.context import get_workspace
from mp_mcp_server.server import mcp

@mcp.tool
def list_events(ctx: Context) -> list[str]:
    """List all event names tracked in the Mixpanel project.

    Returns alphabetically sorted list of event names.
    Use this to discover what events are available before querying.
    """
    ws = get_workspace(ctx)
    return ws.events()

@mcp.tool
def list_properties(event: str, ctx: Context) -> list[str]:
    """List all properties tracked for a specific event.

    Args:
        event: The event name to get properties for.

    Returns alphabetically sorted list of property names.
    """
    ws = get_workspace(ctx)
    return ws.properties(event)

@mcp.tool
def list_property_values(
    event: str,
    property_name: str,
    limit: int = 100,
    ctx: Context,
) -> list[str]:
    """Get sample values recorded for a property.

    Args:
        event: The event name.
        property_name: The property to get values for.
        limit: Maximum number of values to return (default 100).

    Returns list of sample values (strings).
    """
    ws = get_workspace(ctx)
    return ws.property_values(property_name, event=event, limit=limit)

@mcp.tool
def list_funnels(ctx: Context) -> list[dict]:
    """List all saved funnels in the project.

    Returns list of funnel info dicts with keys:
    - funnel_id: Unique funnel identifier
    - name: Funnel name
    - created: Creation timestamp
    - steps: Number of steps in funnel
    """
    ws = get_workspace(ctx)
    return [f.to_dict() for f in ws.funnels()]

@mcp.tool
def list_cohorts(ctx: Context) -> list[dict]:
    """List all saved cohorts in the project.

    Returns list of cohort info dicts with keys:
    - cohort_id: Unique cohort identifier
    - name: Cohort name
    - description: Cohort description
    - size: Number of users in cohort
    """
    ws = get_workspace(ctx)
    return [c.to_dict() for c in ws.cohorts()]

@mcp.tool
def list_bookmarks(bookmark_type: str | None = None, ctx: Context) -> list[dict]:
    """List saved reports/bookmarks.

    Args:
        bookmark_type: Optional filter - "insights", "funnels", "retention", "flows"

    Returns list of bookmark info dicts.
    """
    ws = get_workspace(ctx)
    return [b.to_dict() for b in ws.list_bookmarks(bookmark_type)]

@mcp.tool
def top_events(limit: int = 10, ctx: Context) -> list[dict]:
    """Get most active events in the project (real-time).

    Args:
        limit: Maximum number of events to return.

    Returns list of TopEvent dicts with event name and count.
    Note: This is NOT cached - returns fresh data.
    """
    ws = get_workspace(ctx)
    return [e.to_dict() for e in ws.top_events(limit=limit)]

@mcp.tool
def lexicon_schemas(ctx: Context) -> dict[str, str]:
    """Get available lexicon schema entity types.

    Returns dict mapping entity type to description.
    Use lexicon_schema(entity_type) to get full schema.
    """
    ws = get_workspace(ctx)
    return ws.lexicon_schemas()

@mcp.tool
def lexicon_schema(entity_type: str, ctx: Context) -> dict:
    """Get full lexicon schema for an entity type.

    Args:
        entity_type: Entity type from lexicon_schemas().

    Returns full schema with properties and metadata.
    """
    ws = get_workspace(ctx)
    return ws.lexicon_schema(entity_type).to_dict()
```

#### 2.3 Verification
```bash
just test -k test_tools_discovery
just typecheck
```

---

### Phase 3: Live Query Tools

**Goal:** Expose real-time analytics query methods as MCP tools.

#### 3.1 Tests First

**Create:** `mp-mcp-server/tests/unit/test_tools_live_query.py`
```python
# Core analytics
async def test_segmentation_returns_time_series():
    """segmentation returns time series data."""

async def test_segmentation_with_segment_property():
    """segmentation can segment by property."""

async def test_funnel_returns_conversion_data():
    """funnel returns step-by-step conversion."""

async def test_retention_returns_cohort_data():
    """retention returns cohort retention curves."""

async def test_jql_executes_script():
    """jql executes JavaScript Query Language script."""

# Extended analytics
async def test_event_counts_returns_multi_event_series():
    """event_counts returns counts for multiple events."""

async def test_property_counts_returns_value_breakdown():
    """property_counts returns property value distribution."""

async def test_activity_feed_returns_user_events():
    """activity_feed returns user's event history."""

async def test_frequency_returns_distribution():
    """frequency returns event frequency distribution."""

# Numeric aggregations
async def test_segmentation_numeric_returns_buckets():
    """segmentation_numeric returns numeric property buckets."""

async def test_segmentation_sum_returns_totals():
    """segmentation_sum returns property sum per period."""

async def test_segmentation_average_returns_averages():
    """segmentation_average returns property average per period."""

# Saved reports
async def test_query_flows_executes_flows_report():
    """query_flows executes saved flows bookmark."""

async def test_query_saved_report_executes_insight():
    """query_saved_report executes saved insight."""
```

#### 3.2 Implementation

**Create:** `mp-mcp-server/src/mp_mcp_server/tools/live_query.py`
```python
from typing import Literal
from fastmcp import Context
from mp_mcp_server.context import get_workspace
from mp_mcp_server.server import mcp

@mcp.tool
def segmentation(
    event: str,
    from_date: str,
    to_date: str,
    unit: Literal["day", "week", "month"] = "day",
    on: str | None = None,
    ctx: Context,
) -> dict:
    """Run segmentation query - time series of event counts.

    Args:
        event: Event name to analyze.
        from_date: Start date (YYYY-MM-DD).
        to_date: End date (YYYY-MM-DD).
        unit: Time granularity - "day", "week", or "month".
        on: Optional property to segment by.

    Returns:
        - event: Event name queried
        - from_date, to_date: Date range
        - unit: Time unit used
        - segment_property: Property segmented by (if any)
        - total: Total event count
        - series: Dict of {segment: {date: count}}
    """
    ws = get_workspace(ctx)
    return ws.segmentation(event, from_date=from_date, to_date=to_date,
                           unit=unit, on=on).to_dict()

@mcp.tool
def funnel(
    funnel_id: int,
    from_date: str,
    to_date: str,
    interval: int | None = None,
    unit: Literal["hour", "day"] | None = None,
    ctx: Context,
) -> dict:
    """Run funnel analysis - step-by-step conversion rates.

    Args:
        funnel_id: Saved funnel ID (from list_funnels).
        from_date: Start date (YYYY-MM-DD).
        to_date: End date (YYYY-MM-DD).
        interval: Optional max days between steps.
        unit: Optional time unit for breakdown.

    Returns:
        - funnel_id, funnel_name: Funnel identification
        - from_date, to_date: Date range
        - conversion_rate: Overall conversion percentage
        - steps: List of step details with counts and rates
    """
    ws = get_workspace(ctx)
    return ws.funnel(funnel_id, from_date=from_date, to_date=to_date,
                     interval=interval, unit=unit).to_dict()

@mcp.tool
def retention(
    born_event: str,
    return_event: str,
    from_date: str,
    to_date: str,
    unit: Literal["day", "week", "month"] = "day",
    retention_type: str = "returning",
    ctx: Context,
) -> dict:
    """Run retention analysis - cohort return rates over time.

    Args:
        born_event: Event that defines cohort entry.
        return_event: Event that defines return activity.
        from_date: Start date (YYYY-MM-DD).
        to_date: End date (YYYY-MM-DD).
        unit: Cohort granularity - "day", "week", or "month".
        retention_type: "returning" (default) or "first_time".

    Returns:
        - born_event, return_event: Events used
        - from_date, to_date: Date range
        - unit: Time unit
        - cohorts: List of cohort retention data
    """
    ws = get_workspace(ctx)
    return ws.retention(born_event=born_event, return_event=return_event,
                        from_date=from_date, to_date=to_date, unit=unit,
                        retention_type=retention_type).to_dict()

@mcp.tool
def jql(
    script: str,
    params: dict | None = None,
    ctx: Context,
) -> dict:
    """Execute JavaScript Query Language (JQL) script.

    Args:
        script: JQL script to execute.
        params: Optional parameters to pass to script.

    Returns dict with 'data' key containing query results.

    JQL enables complex event transformations and aggregations
    that aren't possible with standard segmentation queries.
    """
    ws = get_workspace(ctx)
    return ws.jql(script, params=params).to_dict()

@mcp.tool
def event_counts(
    events: list[str],
    from_date: str,
    to_date: str,
    unit: Literal["day", "week", "month"] = "day",
    count_type: Literal["general", "unique", "average"] = "general",
    ctx: Context,
) -> dict:
    """Get event counts for multiple events over time.

    Args:
        events: List of event names to count.
        from_date: Start date (YYYY-MM-DD).
        to_date: End date (YYYY-MM-DD).
        unit: Time granularity.
        count_type: "general" (total), "unique" (per user), "average".

    Returns time series counts for each event.
    """
    ws = get_workspace(ctx)
    return ws.event_counts(events, from_date=from_date, to_date=to_date,
                           unit=unit, count_type=count_type).to_dict()

@mcp.tool
def property_counts(
    event: str,
    property_name: str,
    from_date: str,
    to_date: str,
    unit: Literal["day", "week", "month"] = "day",
    count_type: Literal["general", "unique", "average"] = "general",
    ctx: Context,
) -> dict:
    """Get property value distribution over time.

    Args:
        event: Event name.
        property_name: Property to break down by.
        from_date: Start date (YYYY-MM-DD).
        to_date: End date (YYYY-MM-DD).
        unit: Time granularity.
        count_type: "general", "unique", or "average".

    Returns time series with value breakdown.
    """
    ws = get_workspace(ctx)
    return ws.property_counts(event, property_name, from_date=from_date,
                              to_date=to_date, unit=unit,
                              count_type=count_type).to_dict()

@mcp.tool
def activity_feed(
    distinct_id: str,
    limit: int = 100,
    ctx: Context,
) -> dict:
    """Get a user's recent event activity.

    Args:
        distinct_id: User identifier.
        limit: Maximum events to return (default 100).

    Returns list of user's events with timestamps and properties.
    """
    ws = get_workspace(ctx)
    return ws.activity_feed(distinct_id, limit=limit).to_dict()

@mcp.tool
def frequency(
    event: str,
    from_date: str,
    to_date: str,
    unit: Literal["hour", "day"] = "day",
    ctx: Context,
) -> dict:
    """Analyze how often users trigger an event.

    Args:
        event: Event name.
        from_date: Start date (YYYY-MM-DD).
        to_date: End date (YYYY-MM-DD).
        unit: Time granularity.

    Returns frequency distribution (how many users did event N times).
    """
    ws = get_workspace(ctx)
    return ws.frequency(event=event, from_date=from_date, to_date=to_date,
                        unit=unit).to_dict()

@mcp.tool
def segmentation_numeric(
    event: str,
    property_name: str,
    from_date: str,
    to_date: str,
    unit: Literal["hour", "day"] = "day",
    ctx: Context,
) -> dict:
    """Bucket events by numeric property ranges.

    Args:
        event: Event name.
        property_name: Numeric property to bucket.
        from_date: Start date.
        to_date: End date.
        unit: Time granularity.

    Returns bucket distribution.
    """
    ws = get_workspace(ctx)
    return ws.segmentation_numeric(event, property_name, from_date=from_date,
                                   to_date=to_date, unit=unit).to_dict()

@mcp.tool
def segmentation_sum(
    event: str,
    property_name: str,
    from_date: str,
    to_date: str,
    unit: Literal["hour", "day"] = "day",
    ctx: Context,
) -> dict:
    """Calculate sum of numeric property over time.

    Args:
        event: Event name.
        property_name: Numeric property to sum.
        from_date: Start date.
        to_date: End date.
        unit: Time granularity.

    Returns sum per time period.
    """
    ws = get_workspace(ctx)
    return ws.segmentation_sum(event, property_name, from_date=from_date,
                               to_date=to_date, unit=unit).to_dict()

@mcp.tool
def segmentation_average(
    event: str,
    property_name: str,
    from_date: str,
    to_date: str,
    unit: Literal["hour", "day"] = "day",
    ctx: Context,
) -> dict:
    """Calculate average of numeric property over time.

    Args:
        event: Event name.
        property_name: Numeric property to average.
        from_date: Start date.
        to_date: End date.
        unit: Time granularity.

    Returns average per time period.
    """
    ws = get_workspace(ctx)
    return ws.segmentation_average(event, property_name, from_date=from_date,
                                   to_date=to_date, unit=unit).to_dict()

@mcp.tool
def query_flows(bookmark_id: int, ctx: Context) -> dict:
    """Execute a saved Flows report.

    Args:
        bookmark_id: Bookmark ID of saved Flows report.

    Returns flows visualization data.
    """
    ws = get_workspace(ctx)
    return ws.query_flows(bookmark_id).to_dict()

@mcp.tool
def query_saved_report(bookmark_id: int, ctx: Context) -> dict:
    """Execute a saved Insights report.

    Args:
        bookmark_id: Bookmark ID of saved report.

    Returns report data with headers and rows.
    """
    ws = get_workspace(ctx)
    return ws.query_saved_report(bookmark_id).to_dict()
```

#### 3.3 Verification
```bash
just test -k test_tools_live_query
just typecheck
```

---

### Phase 4: Data Fetching Tools

**Goal:** Expose data fetching methods as MCP tools.

#### 4.1 Tests First

**Create:** `mp-mcp-server/tests/unit/test_tools_fetch.py`
```python
async def test_fetch_events_creates_table():
    """fetch_events creates DuckDB table with events."""

async def test_fetch_events_returns_fetch_result():
    """fetch_events returns FetchResult dict."""

async def test_fetch_events_with_date_range():
    """fetch_events accepts from_date and to_date."""

async def test_fetch_profiles_creates_table():
    """fetch_profiles creates DuckDB table with profiles."""

async def test_fetch_profiles_returns_fetch_result():
    """fetch_profiles returns FetchResult dict."""

async def test_stream_events_returns_iterator_info():
    """stream_events returns event data without storage."""

async def test_fetch_events_parallel_uses_workers():
    """fetch_events with parallel=True uses parallel fetcher."""
```

#### 4.2 Implementation

**Create:** `mp-mcp-server/src/mp_mcp_server/tools/fetch.py`
```python
from fastmcp import Context
from mp_mcp_server.context import get_workspace
from mp_mcp_server.server import mcp

@mcp.tool
def fetch_events(
    from_date: str,
    to_date: str,
    table: str = "events",
    parallel: bool = False,
    max_workers: int = 10,
    ctx: Context,
) -> dict:
    """Fetch events from Mixpanel into local DuckDB table.

    Args:
        from_date: Start date (YYYY-MM-DD).
        to_date: End date (YYYY-MM-DD).
        table: Table name (default "events").
        parallel: Use parallel fetching for large date ranges.
        max_workers: Number of parallel workers (default 10).

    Returns:
        - table: Table name created
        - rows: Number of rows fetched
        - duration_seconds: Fetch duration
        - date_range: (from_date, to_date)

    Raises TableExistsError if table already exists.
    Use drop_table() first to replace existing data.

    After fetching, use sql() to query the local data.
    """
    ws = get_workspace(ctx)
    if parallel:
        result = ws.fetch_events_parallel(
            from_date=from_date, to_date=to_date,
            table=table, num_workers=max_workers
        )
    else:
        result = ws.fetch_events(
            from_date=from_date, to_date=to_date, table=table
        )
    return result.to_dict()

@mcp.tool
def fetch_profiles(
    table: str = "profiles",
    limit: int | None = None,
    parallel: bool = False,
    max_workers: int = 4,
    ctx: Context,
) -> dict:
    """Fetch user profiles from Mixpanel into local DuckDB table.

    Args:
        table: Table name (default "profiles").
        limit: Maximum profiles to fetch (default all).
        parallel: Use parallel fetching.
        max_workers: Number of parallel workers (default 4).

    Returns:
        - table: Table name created
        - rows: Number of profiles fetched
        - duration_seconds: Fetch duration

    Raises TableExistsError if table already exists.
    """
    ws = get_workspace(ctx)
    if parallel:
        result = ws.fetch_profiles_parallel(
            table=table, limit=limit, num_workers=max_workers
        )
    else:
        result = ws.fetch_profiles(table=table, limit=limit)
    return result.to_dict()

@mcp.tool
def stream_events(
    from_date: str,
    to_date: str,
    limit: int | None = None,
    ctx: Context,
) -> list[dict]:
    """Stream events without storing to database.

    Args:
        from_date: Start date (YYYY-MM-DD).
        to_date: End date (YYYY-MM-DD).
        limit: Maximum events to return (recommended for large ranges).

    Returns list of event dicts directly without creating a table.
    Use this for quick data exploration before committing to a fetch.

    Warning: Large date ranges without limit can return millions of events.
    """
    ws = get_workspace(ctx)
    return list(ws.stream_events(from_date=from_date, to_date=to_date,
                                 limit=limit))

@mcp.tool
def stream_profiles(
    limit: int | None = None,
    ctx: Context,
) -> list[dict]:
    """Stream profiles without storing to database.

    Args:
        limit: Maximum profiles to return.

    Returns list of profile dicts directly.
    """
    ws = get_workspace(ctx)
    return list(ws.stream_profiles(limit=limit))
```

#### 4.3 Verification
```bash
just test -k test_tools_fetch
just typecheck
```

---

### Phase 5: Local Analysis Tools

**Goal:** Expose SQL queries and introspection methods as MCP tools.

#### 5.1 Tests First

**Create:** `mp-mcp-server/tests/unit/test_tools_local.py`
```python
# SQL tools
async def test_sql_executes_query():
    """sql executes SQL and returns results."""

async def test_sql_returns_dict_format():
    """sql returns column-oriented dict format."""

async def test_sql_scalar_returns_single_value():
    """sql_scalar returns single scalar value."""

# Introspection tools
async def test_workspace_info_returns_state():
    """workspace_info returns workspace state."""

async def test_list_tables_returns_table_info():
    """list_tables returns list of table metadata."""

async def test_table_schema_returns_columns():
    """table_schema returns column definitions."""

async def test_sample_returns_random_rows():
    """sample returns random rows from table."""

async def test_summarize_returns_statistics():
    """summarize returns column statistics."""

async def test_event_breakdown_returns_counts():
    """event_breakdown returns per-event counts."""

async def test_property_keys_extracts_json_keys():
    """property_keys extracts keys from JSON column."""

async def test_column_stats_returns_detailed_stats():
    """column_stats returns detailed column statistics."""

# Table management
async def test_drop_table_removes_table():
    """drop_table removes specified table."""

async def test_drop_all_removes_all_tables():
    """drop_all removes all tables."""
```

#### 5.2 Implementation

**Create:** `mp-mcp-server/src/mp_mcp_server/tools/local.py`
```python
from typing import Any, Literal
from fastmcp import Context
from mp_mcp_server.context import get_workspace
from mp_mcp_server.server import mcp

# === SQL Query Tools ===

@mcp.tool
def sql(query: str, ctx: Context) -> dict:
    """Execute SQL query on local DuckDB database.

    Args:
        query: SQL query string.

    Returns dict with:
        - columns: List of column names
        - rows: List of row tuples

    Example queries:
        SELECT * FROM events LIMIT 10
        SELECT event_name, COUNT(*) FROM events GROUP BY event_name
        SELECT properties->>'$.country' as country FROM events
    """
    ws = get_workspace(ctx)
    result = ws.sql_rows(query)
    return result.to_dict()

@mcp.tool
def sql_scalar(query: str, ctx: Context) -> Any:
    """Execute SQL query and return single scalar value.

    Args:
        query: SQL query that returns exactly one value.

    Returns the scalar value.

    Example: SELECT COUNT(*) FROM events
    """
    ws = get_workspace(ctx)
    return ws.sql_scalar(query)

# === Introspection Tools ===

@mcp.tool
def workspace_info(ctx: Context) -> dict:
    """Get current workspace state and configuration.

    Returns:
        - db_path: Path to DuckDB file (or None for in-memory)
        - is_ephemeral: Whether workspace is temporary
        - is_in_memory: Whether using in-memory database
        - is_read_only: Whether database is read-only
        - tables: List of table summaries
    """
    ws = get_workspace(ctx)
    return ws.info().to_dict()

@mcp.tool
def list_tables(ctx: Context) -> list[dict]:
    """List all tables in the local database.

    Returns list of table info dicts with:
        - name: Table name
        - row_count: Number of rows
        - bytes: Table size in bytes
        - created_at: When table was created
        - fetch_metadata: Fetch parameters if from fetch operation
    """
    ws = get_workspace(ctx)
    return [t.to_dict() for t in ws.tables()]

@mcp.tool
def table_schema(table: str, ctx: Context) -> dict:
    """Get column schema for a table.

    Args:
        table: Table name.

    Returns:
        - table: Table name
        - columns: List of {name, type} dicts
    """
    ws = get_workspace(ctx)
    return ws.table_schema(table).to_dict()

@mcp.tool
def sample(table: str, n: int = 10, ctx: Context) -> dict:
    """Get random sample rows from a table.

    Args:
        table: Table name.
        n: Number of rows to sample (default 10).

    Returns dict with columns and sampled rows.
    """
    ws = get_workspace(ctx)
    df = ws.sample(table, n=n)
    return {
        "columns": df.columns.tolist(),
        "rows": df.values.tolist(),
    }

@mcp.tool
def summarize(table: str, ctx: Context) -> dict:
    """Get statistical summary of table columns.

    Args:
        table: Table name.

    Returns column-wise statistics (count, nulls, mean, stddev, min, max).
    """
    ws = get_workspace(ctx)
    return ws.summarize(table).to_dict()

@mcp.tool
def event_breakdown(table: str, ctx: Context) -> dict:
    """Get count of each event in an events table.

    Args:
        table: Events table name.

    Returns list of {event, count} sorted by count descending.
    """
    ws = get_workspace(ctx)
    return ws.event_breakdown(table).to_dict()

@mcp.tool
def property_keys(
    table: str,
    column: str = "properties",
    ctx: Context,
) -> list[str]:
    """Extract all JSON property keys from a column.

    Args:
        table: Table name.
        column: JSON column name (default "properties").

    Returns list of property key names found in the column.
    """
    ws = get_workspace(ctx)
    return ws.property_keys(table, column=column)

@mcp.tool
def column_stats(
    table: str,
    column: str,
    top_n: int = 10,
    ctx: Context,
) -> dict:
    """Get detailed statistics for a specific column.

    Args:
        table: Table name.
        column: Column name.
        top_n: Number of top values to show (default 10).

    Returns detailed stats including value distribution.
    """
    ws = get_workspace(ctx)
    return ws.column_stats(table, column, top_n=top_n).to_dict()

# === Table Management Tools ===

@mcp.tool
def drop_table(table: str, ctx: Context) -> dict:
    """Delete a table from the local database.

    Args:
        table: Table name to drop.

    Returns confirmation dict.
    Raises TableNotFoundError if table doesn't exist.
    """
    ws = get_workspace(ctx)
    ws.drop(table)
    return {"dropped": table, "success": True}

@mcp.tool
def drop_all_tables(
    table_type: Literal["events", "profiles"] | None = None,
    ctx: Context,
) -> dict:
    """Delete all tables from the local database.

    Args:
        table_type: Optional filter - "events" or "profiles" only.

    Returns confirmation dict with list of dropped tables.
    """
    ws = get_workspace(ctx)
    tables_before = [t.name for t in ws.tables()]
    ws.drop_all(type=table_type)
    tables_after = [t.name for t in ws.tables()]
    dropped = [t for t in tables_before if t not in tables_after]
    return {"dropped": dropped, "success": True}
```

#### 5.3 Verification
```bash
just test -k test_tools_local
just typecheck
```

---

### Phase 6: MCP Resources

**Goal:** Expose schema and state as MCP resources for efficient context loading.

#### 6.1 Tests First

**Create:** `mp-mcp-server/tests/unit/test_resources.py`
```python
# Static resources
async def test_workspace_info_resource():
    """workspace://info returns workspace state."""

async def test_tables_resource():
    """workspace://tables returns table list."""

# Dynamic schema resources
async def test_events_resource():
    """schema://events returns event list."""

async def test_funnels_resource():
    """schema://funnels returns funnel list."""

async def test_cohorts_resource():
    """schema://cohorts returns cohort list."""

# Resource templates
async def test_properties_resource_template():
    """schema://properties/{event} returns properties for event."""

async def test_table_schema_resource_template():
    """workspace://schema/{table} returns table schema."""
```

#### 6.2 Implementation

**Create:** `mp-mcp-server/src/mp_mcp_server/resources.py`
```python
from fastmcp import Context
from mp_mcp_server.context import get_workspace
from mp_mcp_server.server import mcp
import json

# === Workspace State Resources ===

@mcp.resource("workspace://info")
def workspace_info_resource(ctx: Context) -> str:
    """Current workspace state and configuration."""
    ws = get_workspace(ctx)
    return json.dumps(ws.info().to_dict(), indent=2)

@mcp.resource("workspace://tables")
def tables_resource(ctx: Context) -> str:
    """List of tables in local database."""
    ws = get_workspace(ctx)
    return json.dumps([t.to_dict() for t in ws.tables()], indent=2)

# === Schema Resources ===

@mcp.resource("schema://events")
def events_resource(ctx: Context) -> str:
    """All event names in the project (cached)."""
    ws = get_workspace(ctx)
    return json.dumps(ws.events(), indent=2)

@mcp.resource("schema://funnels")
def funnels_resource(ctx: Context) -> str:
    """All saved funnels (cached)."""
    ws = get_workspace(ctx)
    return json.dumps([f.to_dict() for f in ws.funnels()], indent=2)

@mcp.resource("schema://cohorts")
def cohorts_resource(ctx: Context) -> str:
    """All saved cohorts (cached)."""
    ws = get_workspace(ctx)
    return json.dumps([c.to_dict() for c in ws.cohorts()], indent=2)

@mcp.resource("schema://bookmarks")
def bookmarks_resource(ctx: Context) -> str:
    """All saved bookmarks/reports (cached)."""
    ws = get_workspace(ctx)
    return json.dumps([b.to_dict() for b in ws.list_bookmarks()], indent=2)

# === Dynamic Resource Templates ===

@mcp.resource("schema://properties/{event}")
def properties_resource(event: str, ctx: Context) -> str:
    """Properties for a specific event (cached)."""
    ws = get_workspace(ctx)
    return json.dumps(ws.properties(event), indent=2)

@mcp.resource("workspace://schema/{table}")
def table_schema_resource(table: str, ctx: Context) -> str:
    """Schema for a specific table."""
    ws = get_workspace(ctx)
    return json.dumps(ws.table_schema(table).to_dict(), indent=2)

@mcp.resource("workspace://sample/{table}")
def table_sample_resource(table: str, ctx: Context) -> str:
    """Sample rows from a table (10 random rows)."""
    ws = get_workspace(ctx)
    df = ws.sample(table, n=10)
    return json.dumps({
        "columns": df.columns.tolist(),
        "rows": df.values.tolist(),
    }, indent=2, default=str)
```

#### 6.3 Verification
```bash
just test -k test_resources
just typecheck
```

---

### Phase 7: MCP Prompts

**Goal:** Create reusable prompt templates for common analytics workflows.

#### 7.1 Tests First

**Create:** `mp-mcp-server/tests/unit/test_prompts.py`
```python
def test_analytics_workflow_prompt_registered():
    """analytics_workflow prompt is registered."""

def test_funnel_analysis_prompt_registered():
    """funnel_analysis prompt is registered."""

def test_retention_analysis_prompt_registered():
    """retention_analysis prompt is registered."""

def test_analytics_workflow_returns_messages():
    """analytics_workflow returns properly formatted messages."""
```

#### 7.2 Implementation

**Create:** `mp-mcp-server/src/mp_mcp_server/prompts.py`
```python
from fastmcp import Context
from mp_mcp_server.server import mcp

@mcp.prompt
def analytics_workflow() -> str:
    """Guided workflow for Mixpanel analytics session.

    Use this prompt to start a structured analytics investigation.
    """
    return """You are starting a Mixpanel analytics investigation.

Follow this workflow:

1. **Discover** - First, understand what data is available:
   - Use list_events() to see all tracked events
   - Use list_funnels() and list_cohorts() for saved analyses
   - Use top_events() to see what's most active

2. **Explore** - Investigate patterns:
   - Use segmentation() for time-series trends
   - Use event_counts() to compare multiple events
   - Use property_counts() to break down by dimensions

3. **Deep Dive** - For detailed analysis:
   - Use fetch_events() to download data locally
   - Use sql() to run custom queries
   - Use sample() and summarize() to explore tables

4. **Iterate** - Refine your analysis:
   - Use jql() for complex transformations
   - Use retention() and funnel() for behavior analysis

Start by discovering what events are available."""

@mcp.prompt
def funnel_analysis(funnel_name: str) -> str:
    """Template for analyzing a conversion funnel.

    Args:
        funnel_name: Name of the funnel to analyze.
    """
    return f"""Analyze the conversion funnel: {funnel_name}

Steps:
1. Use list_funnels() to find the funnel_id for "{funnel_name}"
2. Use funnel() with the funnel_id to get conversion data
3. Identify the biggest drop-off step
4. Use segmentation() on the drop-off event to find patterns
5. Suggest hypotheses for why users drop off

Provide actionable recommendations based on your findings."""

@mcp.prompt
def retention_analysis(
    born_event: str,
    return_event: str,
) -> str:
    """Template for cohort retention analysis.

    Args:
        born_event: Event that defines user acquisition.
        return_event: Event that indicates user return.
    """
    return f"""Analyze user retention patterns.

Configuration:
- Acquisition event (born_event): {born_event}
- Return event: {return_event}

Steps:
1. Use retention() with these events to get cohort curves
2. Compare day-1, day-7, day-30 retention rates
3. Look for patterns in when users stop returning
4. Use segmentation() on the born_event to find high-retention segments
5. Identify characteristics of retained vs churned users

Provide insights on improving retention."""

@mcp.prompt
def local_analysis_workflow(table: str) -> str:
    """Template for analyzing locally fetched data.

    Args:
        table: Name of the local table to analyze.
    """
    return f"""Analyze the local data in table: {table}

Steps:
1. Use table_schema("{table}") to understand the columns
2. Use sample("{table}") to see example rows
3. Use summarize("{table}") for statistical overview
4. Use event_breakdown("{table}") if it's an events table
5. Use property_keys("{table}") to discover JSON properties
6. Write custom SQL queries with sql() for specific analysis

Key SQL patterns for events:
- Count by event: SELECT event_name, COUNT(*) FROM {table} GROUP BY 1
- Daily trend: SELECT DATE_TRUNC('day', event_time), COUNT(*) FROM {table} GROUP BY 1
- Property extraction: SELECT properties->>'$.key' FROM {table}

Explore the data and surface interesting insights."""
```

#### 7.3 Verification
```bash
just test -k test_prompts
just typecheck
```

---

### Phase 8: Error Handling

**Goal:** Convert library exceptions to structured MCP errors.

#### 8.1 Tests First

**Create:** `mp-mcp-server/tests/unit/test_errors.py`
```python
def test_authentication_error_converted():
    """AuthenticationError becomes structured error."""

def test_rate_limit_error_includes_retry_after():
    """RateLimitError includes retry_after in details."""

def test_table_exists_error_converted():
    """TableExistsError includes table name."""

def test_query_error_includes_details():
    """QueryError includes query details."""

def test_unknown_error_wrapped():
    """Unknown exceptions wrapped with message."""
```

#### 8.2 Implementation

**Create:** `mp-mcp-server/src/mp_mcp_server/errors.py`
```python
from functools import wraps
from typing import Any, Callable, TypeVar
from fastmcp.exceptions import ToolError
from mixpanel_data import (
    MixpanelDataError,
    AuthenticationError,
    RateLimitError,
    QueryError,
    TableExistsError,
    TableNotFoundError,
    ConfigError,
)

T = TypeVar("T")

def handle_errors(func: Callable[..., T]) -> Callable[..., T]:
    """Decorator to convert library exceptions to MCP errors."""
    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> T:
        try:
            return func(*args, **kwargs)
        except AuthenticationError as e:
            raise ToolError(
                f"Authentication failed: {e.message}",
                details={"code": e.code, **e.to_dict()},
            ) from e
        except RateLimitError as e:
            raise ToolError(
                f"Rate limited. Retry after {e.retry_after} seconds.",
                details={
                    "code": e.code,
                    "retry_after": e.retry_after,
                    **e.to_dict(),
                },
            ) from e
        except TableExistsError as e:
            raise ToolError(
                f"Table already exists: {e.table}. Use drop_table() first.",
                details={"code": e.code, "table": e.table},
            ) from e
        except TableNotFoundError as e:
            raise ToolError(
                f"Table not found: {e.table}",
                details={"code": e.code, "table": e.table},
            ) from e
        except QueryError as e:
            raise ToolError(
                f"Query error: {e.message}",
                details={"code": e.code, **e.to_dict()},
            ) from e
        except ConfigError as e:
            raise ToolError(
                f"Configuration error: {e.message}",
                details={"code": e.code},
            ) from e
        except MixpanelDataError as e:
            raise ToolError(
                f"Mixpanel error: {e.message}",
                details=e.to_dict(),
            ) from e
        except Exception as e:
            raise ToolError(
                f"Unexpected error: {str(e)}",
                details={"error_type": type(e).__name__},
            ) from e
    return wrapper
```

Apply decorator to all tools in previous phases.

#### 8.3 Verification
```bash
just test -k test_errors
just typecheck
```

---

### Phase 9: CLI Entry Point

**Goal:** Create command-line interface to run the server.

#### 9.1 Tests First

**Create:** `mp-mcp-server/tests/unit/test_cli.py`
```python
def test_cli_runs_server():
    """CLI main() runs FastMCP server."""

def test_cli_accepts_account_option():
    """CLI accepts --account flag."""

def test_cli_accepts_transport_option():
    """CLI accepts --transport flag."""

def test_cli_accepts_port_option():
    """CLI accepts --port flag for HTTP transport."""
```

#### 9.2 Implementation

**Create:** `mp-mcp-server/src/mp_mcp_server/cli.py`
```python
import argparse
import os
from mp_mcp_server.server import mcp

def main() -> None:
    """Run the Mixpanel MCP server."""
    parser = argparse.ArgumentParser(
        description="Mixpanel Analytics MCP Server"
    )
    parser.add_argument(
        "--account",
        help="Named account from ~/.mp/config.toml",
    )
    parser.add_argument(
        "--transport",
        choices=["stdio", "http", "sse"],
        default="stdio",
        help="Transport protocol (default: stdio)",
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Host for HTTP transport",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port for HTTP transport",
    )
    args = parser.parse_args()

    # Set account via environment if specified
    if args.account:
        os.environ["MP_ACCOUNT"] = args.account

    # Run server
    if args.transport == "stdio":
        mcp.run()
    else:
        mcp.run(
            transport=args.transport,
            host=args.host,
            port=args.port,
        )

if __name__ == "__main__":
    main()
```

#### 9.3 Verification
```bash
just test -k test_cli
just typecheck
```

---

### Phase 10: Integration Testing

**Goal:** End-to-end tests with FastMCP in-memory client.

#### 10.1 Integration Tests

**Create:** `mp-mcp-server/tests/integration/test_server_integration.py`
```python
import pytest
from fastmcp import Client
from mp_mcp_server.server import mcp

@pytest.fixture
async def client():
    """In-memory client for testing."""
    async with Client(mcp) as client:
        yield client

# Discovery workflow
async def test_discovery_workflow(client):
    """Complete discovery workflow works."""
    events = await client.call_tool("list_events", {})
    assert isinstance(events.data, list)

    if events.data:
        props = await client.call_tool(
            "list_properties",
            {"event": events.data[0]}
        )
        assert isinstance(props.data, list)

# Fetch and query workflow
async def test_fetch_and_sql_workflow(client):
    """Fetch events then query with SQL."""
    # Fetch events
    result = await client.call_tool("fetch_events", {
        "from_date": "2024-01-01",
        "to_date": "2024-01-07",
        "table": "test_events",
    })
    assert result.data["rows"] >= 0

    # Query with SQL
    sql_result = await client.call_tool("sql", {
        "query": "SELECT COUNT(*) as cnt FROM test_events"
    })
    assert "rows" in sql_result.data

# Live query workflow
async def test_segmentation_workflow(client):
    """Segmentation query works."""
    events = await client.call_tool("list_events", {})
    if events.data:
        result = await client.call_tool("segmentation", {
            "event": events.data[0],
            "from_date": "2024-01-01",
            "to_date": "2024-01-07",
        })
        assert "series" in result.data

# Resource access
async def test_resource_access(client):
    """Resources return schema data."""
    events = await client.read_resource("schema://events")
    assert events is not None

    info = await client.read_resource("workspace://info")
    assert info is not None
```

#### 10.2 Verification
```bash
just test -k test_server_integration
just check
```

---

### Phase 11: Documentation & Claude Desktop Config

**Goal:** Usage documentation and Claude Desktop configuration.

#### 11.1 README

**Create:** `mp-mcp-server/README.md`

#### 11.2 Claude Desktop Configuration

**Create:** `mp-mcp-server/claude_desktop_config.json` (example)
```json
{
  "mcpServers": {
    "mixpanel": {
      "command": "mp-mcp-server",
      "args": ["--account", "production"]
    }
  }
}
```

---

## Tool Summary

| Category | Tool | Workspace Method |
|----------|------|------------------|
| **Discovery** | `list_events` | `events()` |
| | `list_properties` | `properties(event)` |
| | `list_property_values` | `property_values(prop, event, limit)` |
| | `list_funnels` | `funnels()` |
| | `list_cohorts` | `cohorts()` |
| | `list_bookmarks` | `list_bookmarks(type)` |
| | `top_events` | `top_events(limit)` |
| | `lexicon_schemas` | `lexicon_schemas()` |
| | `lexicon_schema` | `lexicon_schema(entity_type)` |
| **Live Query** | `segmentation` | `segmentation(...)` |
| | `funnel` | `funnel(funnel_id, ...)` |
| | `retention` | `retention(...)` |
| | `jql` | `jql(script, params)` |
| | `event_counts` | `event_counts(events, ...)` |
| | `property_counts` | `property_counts(...)` |
| | `activity_feed` | `activity_feed(distinct_id, limit)` |
| | `frequency` | `frequency(...)` |
| | `segmentation_numeric` | `segmentation_numeric(...)` |
| | `segmentation_sum` | `segmentation_sum(...)` |
| | `segmentation_average` | `segmentation_average(...)` |
| | `query_flows` | `query_flows(bookmark_id)` |
| | `query_saved_report` | `query_saved_report(bookmark_id)` |
| **Fetch** | `fetch_events` | `fetch_events(...)` / `fetch_events_parallel(...)` |
| | `fetch_profiles` | `fetch_profiles(...)` / `fetch_profiles_parallel(...)` |
| | `stream_events` | `stream_events(...)` |
| | `stream_profiles` | `stream_profiles(...)` |
| **Local** | `sql` | `sql_rows(query)` |
| | `sql_scalar` | `sql_scalar(query)` |
| | `workspace_info` | `info()` |
| | `list_tables` | `tables()` |
| | `table_schema` | `table_schema(table)` |
| | `sample` | `sample(table, n)` |
| | `summarize` | `summarize(table)` |
| | `event_breakdown` | `event_breakdown(table)` |
| | `property_keys` | `property_keys(table, column)` |
| | `column_stats` | `column_stats(table, column, top_n)` |
| | `drop_table` | `drop(table)` |
| | `drop_all_tables` | `drop_all(type)` |

**Total: 35 tools**

---

## Resource Summary

| URI | Type | Description |
|-----|------|-------------|
| `workspace://info` | Static | Workspace state |
| `workspace://tables` | Static | Table list |
| `schema://events` | Static | Event names (cached) |
| `schema://funnels` | Static | Saved funnels (cached) |
| `schema://cohorts` | Static | Saved cohorts (cached) |
| `schema://bookmarks` | Static | Saved reports (cached) |
| `schema://properties/{event}` | Template | Properties for event |
| `workspace://schema/{table}` | Template | Table schema |
| `workspace://sample/{table}` | Template | Sample rows |

---

## Validation Requirements

Each phase must pass:
1. `just check` - All linting, type checking, and tests pass
2. Coverage maintained at 90%+
3. All new code has complete docstrings
4. In-memory tests with FastMCP Client

---

## Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| `fastmcp` | `>=2.0,<3` | MCP server framework |
| `mixpanel_data` | `>=0.1.0` | Analytics library |

---

## Estimated Complexity

| Phase | Effort | Notes |
|-------|--------|-------|
| 1. Scaffolding | Low | Package setup, lifespan |
| 2. Discovery Tools | Medium | 9 tools, straightforward mapping |
| 3. Live Query Tools | High | 14 tools, type handling |
| 4. Fetch Tools | Medium | 4 tools, parallel options |
| 5. Local Tools | Medium | 12 tools, SQL execution |
| 6. Resources | Low | 9 resources, JSON serialization |
| 7. Prompts | Low | 4 prompts, templates |
| 8. Error Handling | Medium | Exception mapping |
| 9. CLI | Low | argparse entry point |
| 10. Integration Tests | Medium | End-to-end validation |
| 11. Documentation | Low | README, examples |

---

## Future Work (Out of Scope)

- **Authentication middleware**: OAuth/API key protection for HTTP transport
- **Multi-workspace support**: Multiple Mixpanel projects in one server
- **Streaming responses**: Real-time event streaming
- **Caching layer**: Redis/memcached for shared state
- **Metrics/observability**: Prometheus metrics, OpenTelemetry tracing
