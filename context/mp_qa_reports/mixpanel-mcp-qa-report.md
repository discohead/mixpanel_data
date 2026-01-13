# Mixpanel MCP Server — QA Post-Mortem Report

**Date:** 2025-01-12  
**Tester:** Claude (AI QA Engineer)  
**Test Type:** Exploratory / Live QA  
**Environment:** Claude.ai with MCP integration  
**Server:** Mixpanel MCP Server (FastMCP-based)  

---

## Executive Summary

A live exploratory QA session was conducted on the Mixpanel MCP server. The server successfully connects to a Mixpanel project and several core tools function correctly. However, **6 critical/high-severity bugs** were identified that prevent key functionality from working. Most issues stem from parameter naming mismatches, missing object attributes, and output validation failures.

**Overall Assessment:** The server is partially functional but not production-ready. Core schema discovery and retention analysis work, but segmentation, event streaming, and property inspection are broken.

---

## Test Environment

| Component | Details |
|-----------|---------|
| MCP Server | Mixpanel MCP (FastMCP-based) |
| Connected Project | Mixpanel Internal Infrastructure Metrics |
| Data Scale | ~161M events (track_events, sql-query) |
| Test Date Range | 2025-01-01 to 2025-01-12 |
| Client | Claude.ai chat interface |

---

## Issues Found

### Issue #1: Server Initialization — Lifespan State Error

**Severity:** 🔴 Critical (Blocking)  
**Status:** Resolved by user (server restart/code fix)  
**Component:** Server initialization / FastMCP lifespan management

**Error Message:**
```
'RequestContext' object has no attribute 'lifespan_state'
```

**Reproduction:**
1. Start MCP server
2. Call any tool (e.g., `workspace_info`, `list_events`)
3. Error occurs on all tool calls

**Root Cause Analysis:**
The server attempts to access shared state via `ctx.lifespan_state` but the FastMCP `RequestContext` object doesn't have this attribute. This suggests either:
- FastMCP version incompatibility (server written for different version)
- Incorrect lifespan context configuration
- Missing `@mcp.lifespan` decorator or improper yield of state dict

**Expected Pattern:**
```python
@mcp.lifespan
async def lifespan(server):
    # Initialize shared resources
    db = DuckDBConnection()
    client = MixpanelClient()
    yield {"db": db, "client": client}
    # Cleanup on shutdown
```

**Resolution:** User reported fixing and restarting server. Specific fix unknown.

---

### Issue #2: `workspace_info` — Missing Attribute

**Severity:** 🟠 High  
**Status:** Open  
**Component:** `workspace_info` tool

**Error Message:**
```
'Workspace' object has no attribute 'project_id'
```

**Reproduction:**
```
Tool: mixpanel:workspace_info
Parameters: (none)
Result: Error
```

**Root Cause Analysis:**
The `Workspace` class or object returned by the Mixpanel client doesn't expose a `project_id` attribute. Possible causes:
- Attribute renamed in Mixpanel SDK update (e.g., `id` vs `project_id`)
- Workspace object not fully initialized
- OAuth/API token lacks project scope

**Suggested Investigation:**
```python
# Debug: Print actual workspace attributes
workspace = get_workspace()
print(dir(workspace))
print(vars(workspace))
```

---

### Issue #3: `list_properties` — Output Validation Failure

**Severity:** 🟠 High  
**Status:** Open  
**Component:** `list_properties` tool / Output schema validation

**Error Message:**
```
Output validation error: 'zone' is not of type 'object'
```

**Reproduction:**
```
Tool: mixpanel:list_properties
Parameters: {"event": "mcp_tool_call"}
Result: Output validation error
```

**Root Cause Analysis:**
The Mixpanel API returns property data that doesn't match the expected output schema. The error indicates a field named `zone` is returning a non-object type (likely string or null) where the schema expects an object.

**Suggested Fix:**
1. Inspect raw API response to see actual `zone` field format
2. Update output schema to handle actual data types
3. Add defensive type coercion before validation

**Schema Investigation Needed:**
```python
# Capture raw response
raw_response = mixpanel_client.get_properties(event="mcp_tool_call")
print(json.dumps(raw_response, indent=2))
# Check 'zone' field type across multiple responses
```

---

### Issue #4: `segmentation` — Unexpected Keyword Argument

**Severity:** 🟠 High  
**Status:** Open  
**Component:** `segmentation` tool

**Error Message:**
```
Workspace.segmentation() got an unexpected keyword argument 'segment'
```

**Reproduction:**
```
Tool: mixpanel:segmentation
Parameters: {
  "event": "mcp_tool_call",
  "from_date": "2025-01-01",
  "to_date": "2025-01-12",
  "unit": "day"
}
Result: Error (even without segment_property parameter)
```

**Root Cause Analysis:**
The tool handler is passing a `segment` parameter to `Workspace.segmentation()` that the underlying method doesn't accept. This could be:
- Parameter renamed in Mixpanel SDK (`segment` → `segment_by` or similar)
- Extra parameter being passed unconditionally even when None
- Method signature mismatch between tool schema and implementation

**Suggested Fix:**
```python
# Current (broken):
def segmentation(event, from_date, to_date, segment_property=None, unit="day"):
    return workspace.segmentation(
        event=event,
        from_date=from_date,
        to_date=to_date,
        segment=segment_property,  # ❌ Wrong parameter name
        unit=unit
    )

# Fixed (example):
def segmentation(event, from_date, to_date, segment_property=None, unit="day"):
    kwargs = {"event": event, "from_date": from_date, "to_date": to_date, "unit": unit}
    if segment_property:
        kwargs["on"] = segment_property  # ✅ Check actual SDK param name
    return workspace.segmentation(**kwargs)
```

---

### Issue #5: `event_counts` — List Parameter Handling

**Severity:** 🟠 High  
**Status:** Open  
**Component:** `event_counts` tool

**Error Message:**
```
Query error: Error in event selectors: invalid string: ['mcp_tool_call', 'mcp_server_request', 'mcp_oauth_auth'] <class 'list'>
```

**Reproduction:**
```
Tool: mixpanel:event_counts
Parameters: {
  "events": ["mcp_tool_call", "mcp_server_request", "mcp_oauth_auth"],
  "from_date": "2025-01-01",
  "to_date": "2025-01-12"
}
Result: Error
```

**Root Cause Analysis:**
The events list is being passed as a Python list object to a function expecting a string (or formatted differently). The error shows the raw list representation in the error message, indicating no serialization/joining is happening.

**Suggested Fix:**
```python
# If API expects comma-separated string:
events_str = ",".join(events)

# If API expects JSON array:
events_json = json.dumps(events)

# If API expects multiple calls:
results = [query_single_event(e) for e in events]
```

---

### Issue #6: `stream_events` — Parameter Name Mismatch

**Severity:** 🟡 Medium  
**Status:** Open  
**Component:** `stream_events` tool

**Error Message:**
```
Workspace.stream_events() got an unexpected keyword argument 'event'. Did you mean 'events'?
```

**Reproduction:**
```
Tool: mixpanel:stream_events
Parameters: {
  "event": "mcp_tool_call",
  "from_date": "2025-01-10",
  "to_date": "2025-01-12",
  "limit": 10
}
Result: Error with helpful suggestion
```

**Root Cause Analysis:**
Tool schema defines parameter as `event` (singular) but underlying `Workspace.stream_events()` method expects `events` (plural). This is a simple naming inconsistency.

**Suggested Fix:**
```python
# In tool handler:
def stream_events(from_date, to_date, event=None, limit=1000):
    return workspace.stream_events(
        from_date=from_date,
        to_date=to_date,
        events=event,  # ✅ Map singular to plural
        limit=limit
    )
```

**Alternative:** Update tool schema to use `events` parameter for consistency with SDK.

---

## Working Functionality

The following tools were verified as functional:

| Tool | Test Performed | Result |
|------|----------------|--------|
| `list_events` | No parameters | ✅ Returned 100+ event names |
| `top_events` | `limit=15` | ✅ Returned events with counts and % change |
| `list_funnels` | No parameters | ✅ Returned 300+ funnel definitions |
| `list_cohorts` | No parameters | ✅ Returned 200+ cohort definitions |
| `retention` | `born_event="dqs-query"`, date range | ✅ Returned cohort retention data |
| `list_tables` | No parameters | ✅ Returned empty (expected before fetch) |

### Sample Working Response: `retention`

```json
{
  "born_event": "dqs-query",
  "from_date": "2025-01-01",
  "to_date": "2025-01-10",
  "cohorts": [
    {
      "date": "2025-01-01T00:00:00",
      "size": 662084,
      "retention": [0.999, 0.996, 0.999, ...]
    }
  ]
}
```

---

## Tools Not Tested

The following tools were not tested during this session:

| Tool | Reason |
|------|--------|
| `fetch_events` | User declined (downloads data) |
| `fetch_profiles` | Not attempted |
| `stream_profiles` | Not attempted |
| `funnel` | Requires specific funnel_id selection |
| `jql` | Requires JQL script authoring |
| `sql` / `sql_scalar` | Requires fetched data in local DB |
| `activity_feed` | Requires specific distinct_id |
| `frequency` | Not attempted |
| `property_counts` | Not attempted (likely has same issues) |
| `list_property_values` | Not attempted |
| `list_bookmarks` | Not attempted |

---

## Bug Summary Table

| # | Tool | Severity | Category | Status |
|---|------|----------|----------|--------|
| 1 | Server Init | 🔴 Critical | Lifespan/Context | Resolved |
| 2 | `workspace_info` | 🟠 High | Missing Attribute | Open |
| 3 | `list_properties` | 🟠 High | Schema Validation | Open |
| 4 | `segmentation` | 🟠 High | Parameter Mismatch | Open |
| 5 | `event_counts` | 🟠 High | Type Handling | Open |
| 6 | `stream_events` | 🟡 Medium | Parameter Naming | Open |

---

## Recommendations

### Immediate Fixes (P0)

1. **Audit all tool handlers against SDK method signatures**
   - Compare parameter names in tool schemas vs actual SDK methods
   - Check for `event` vs `events`, `segment` vs `on`, etc.

2. **Fix `workspace_info`**
   - Inspect Workspace object attributes
   - Update to use correct attribute name for project ID

3. **Fix output validation for `list_properties`**
   - Capture raw API response
   - Update schema or add type coercion

### Short-term Improvements (P1)

4. **Add integration tests**
   - Test each tool against live Mixpanel project
   - Validate parameter passing end-to-end

5. **Improve error messages**
   - Wrap SDK calls in try/except
   - Provide actionable error context

6. **Add parameter validation**
   - Validate types before passing to SDK
   - Handle None values explicitly

### Long-term Improvements (P2)

7. **Version compatibility matrix**
   - Document supported FastMCP versions
   - Document supported Mixpanel SDK versions

8. **Add dry-run mode for testing**
   - Allow schema/parameter validation without API calls

---

## Appendix A: Full Error Log

```
# Error 1 (Pre-restart)
Tool: workspace_info
Error: 'RequestContext' object has no attribute 'lifespan_state'

# Error 2
Tool: workspace_info  
Error: 'Workspace' object has no attribute 'project_id'

# Error 3
Tool: list_properties
Parameters: {"event": "mcp_tool_call"}
Error: Output validation error: 'zone' is not of type 'object'

# Error 4
Tool: segmentation
Parameters: {"event": "mcp_tool_call", "from_date": "2025-01-01", "to_date": "2025-01-12", "unit": "day"}
Error: Workspace.segmentation() got an unexpected keyword argument 'segment'

# Error 5
Tool: event_counts
Parameters: {"events": ["mcp_tool_call", "mcp_server_request", "mcp_oauth_auth"], "from_date": "2025-01-01", "to_date": "2025-01-12"}
Error: Query error: Error in event selectors: invalid string: ['mcp_tool_call', 'mcp_server_request', 'mcp_oauth_auth'] <class 'list'>

# Error 6
Tool: stream_events
Parameters: {"event": "mcp_tool_call", "from_date": "2025-01-10", "to_date": "2025-01-12", "limit": 10}
Error: Workspace.stream_events() got an unexpected keyword argument 'event'. Did you mean 'events'?
```

---

## Appendix B: Test Session Timeline

| Time | Action | Result |
|------|--------|--------|
| T+0 | Initial `workspace_info` call | ❌ Lifespan error |
| T+1 | `list_events` call | ❌ Lifespan error |
| T+2 | User restarts server | — |
| T+3 | `workspace_info` call | ❌ Missing attribute |
| T+4 | `list_events` call | ✅ Success |
| T+5 | `top_events` call | ✅ Success |
| T+6 | `list_properties` call | ❌ Validation error |
| T+7 | `list_funnels` call | ✅ Success |
| T+8 | `list_cohorts` call | ✅ Success |
| T+9 | `segmentation` call | ❌ Parameter error |
| T+10 | `event_counts` call | ❌ Type error |
| T+11 | `stream_events` call | ❌ Parameter error |
| T+12 | `list_tables` call | ✅ Success (empty) |
| T+13 | `fetch_events` call | ⏸️ User declined |
| T+14 | `retention` call (mcp_server_request) | ✅ Success (no data) |
| T+15 | `retention` call (dqs-query) | ✅ Success (full data) |

---

**Report Prepared By:** Claude (AI QA Engineer)  
**Report Version:** 1.0  
**Distribution:** Engineering Team
