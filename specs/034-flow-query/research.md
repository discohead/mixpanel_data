# Research: Typed Flow Query API

**Date**: 2026-04-06  
**Feature**: 034-flow-query  
**Status**: Complete — all unknowns resolved

---

## 1. Segfilter Format (Filter → Legacy Converter)

### Decision
Build a `build_segfilter_entry(f: Filter) -> dict` converter that maps the library's `Filter` objects to the legacy segfilter format used by flows per-step filters.

### Rationale
Flows steps use `property_filter_params_list` with segfilter-format dicts, not the bookmark-style filter dicts used by insights/funnels/retention. The format differences are well-specified by the canonical TypeScript implementation and round-trip tests.

### Operator Mapping (Bookmark → Segfilter)

| Filter method | Bookmark operator | Segfilter operator | Notes |
|---------------|------------------|-------------------|-------|
| `equals` | `"equals"` | `"=="` | String/number |
| `does_not_equal` | `"does not equal"` | `"!="` | String/number |
| `contains` | `"contains"` | `"in"` | Substring match |
| `does_not_contain` | `"does not contain"` | `"not in"` | |
| `greater_than` | `"is greater than"` | `">"` | Number |
| `less_than` | `"is less than"` | `"<"` | Number |
| `greater_than_or_equal` | `"is greater than or equal to"` | `">="` | Number |
| `less_than_or_equal` | `"is less than or equal to"` | `"<="` | Number |
| `between` | `"is between"` | `"><"` | Number range |
| `not_between` | `"is not between"` | `"!><"` | Number range |
| `is_set` | `"is set"` | `"is set"` (number) / `"set"` (string) | Type-dependent |
| `is_not_set` | `"is not set"` | `"is not set"` (number) / `"not set"` (string) | Type-dependent |
| `true_` | `"true"` | (no operator) | Operand = `"true"` |
| `false_` | `"false"` | (no operator) | Operand = `"false"` |

### Property Structure Mapping

```python
# Bookmark filter (what we have):
{"resourceType": "events", "filterType": "string", "value": "country", ...}

# Segfilter (what we need):
{
    "property": {"name": "country", "source": "properties", "type": "string"},
    "type": "string",
    "selected_property_type": "string",
    "filter": {"operator": "==", "operand": ["US"]}
}
```

Resource type mapping: `"events"` → `"properties"`, `"people"` → `"user"`.

### Value Serialization Rules

| Type | Bookmark `filterValue` | Segfilter `filter.operand` |
|------|----------------------|--------------------------|
| String equals | `["US"]` | `["US"]` |
| Number | `50` | `"50"` (stringified) |
| Number range | `[5, 10]` | `["5", "10"]` (stringified) |
| Boolean | `true` | `"true"` (string) |
| Date | `"2025-01-01"` | `"01/01/2025"` (MM/DD/YYYY) |
| Date range | `["2025-01-01", "2025-01-31"]` | `["01/01/2025", "01/31/2025"]` |
| Set/NotSet | (none) | `""` (empty string) |

### Known Bugs in Existing Implementations

The existing Python converter in `analytics/mixpanel_mcp/mcp_server/utils/reports/flows.py` has multiple bugs:
- `"contains"` mapped to `"contains"` instead of `"in"`
- `"is set"` mapped to `"defined"` instead of `"is set"`/`"set"`
- No date format conversion
- Numbers not stringified

Our implementation will be correct from the start, based on the TypeScript reference and round-trip tests.

### Alternatives Considered
- **Pass-through raw dicts**: Rejected — forces users to know segfilter format, defeats the purpose of `Filter` abstraction.
- **Accept both formats**: Rejected — unnecessary complexity. `Filter` is the public API; segfilter is internal.

---

## 2. Flows API Response Format

### Decision
Handle both sankey and top-paths response structures. `totalCount` is always a string in the JSON response (despite TypeScript interfaces declaring `number`). Parse with `int()`.

### Sankey Response Structure

```json
{
    "computed_at": "2025-01-15T10:00:00",
    "metadata": {"min_sampling_factor": 1.0},
    "breakdowns": [],
    "steps": [
        {
            "nodes": [
                {
                    "event": "Login",
                    "type": "ANCHOR",
                    "anchorType": "NORMAL",
                    "totalCount": "100",
                    "isComputed": false,
                    "isCustomEvent": false,
                    "segments": [],
                    "conversionRateChange": 0.0,
                    "breakdowns": [],
                    "edges": [
                        {
                            "event": "Search",
                            "type": "NORMAL",
                            "anchorType": "NORMAL",
                            "step": 1,
                            "totalCount": "80",
                            "isComputed": false,
                            "segments": [],
                            "breakdowns": []
                        }
                    ]
                }
            ]
        }
    ]
}
```

### Top-Paths Response Structure

```json
{
    "computed_at": "2025-01-15T10:00:00",
    "metadata": {"min_sampling_factor": 1.0},
    "flows": [
        {
            "flowSteps": [
                {
                    "event": "Login",
                    "type": "ANCHOR",
                    "isComputed": false,
                    "totalCount": "100"
                },
                {
                    "event": "Search",
                    "type": "NORMAL",
                    "isComputed": false,
                    "totalCount": "80"
                }
            ],
            "segments": []
        }
    ]
}
```

### Node Types

| Type | Meaning |
|------|---------|
| `ANCHOR` | User-specified event (the waypoints) |
| `NORMAL` | Intermediate discovered event |
| `FORWARD` | Event in forward direction from anchor |
| `REVERSE` | Event in reverse direction from anchor |
| `DROPOFF` | Terminal — user left the flow |
| `PRUNED` | Low-frequency events merged into "Other" |

### Inline Bookmark POST Format

Confirmed via `FunnelMetricParams.get_bookmark_from_params()` at `funnel_metric_params.py:670-692`:

```python
# The API checks for inline "bookmark" dict BEFORE "bookmark_id"
if "bookmark" in query_params:
    bookmark = query_params["bookmark"]
    bookmark_params = json.loads(bookmark) if isinstance(bookmark, str) else bookmark
elif "bookmark_id" in query_params:
    # ... lookup saved bookmark
```

**Request body**:
```json
{
    "project_id": 123,
    "query_type": "flows_sankey",
    "bookmark": { /* flat flows bookmark params */ }
}
```

### Alternatives Considered
- **Separate result types per mode**: Rejected — one `FlowQueryResult` with mode-aware properties is simpler and matches how the existing codebase handles insights mode variants.

---

## 3. Test Patterns

### Decision
Follow the exact patterns established in Phase 3 (retention) tests.

### Key Patterns to Reuse

| Pattern | Source | Application |
|---------|--------|-------------|
| `_make_result(**overrides)` factory | `test_types_retention.py:95` | `FlowQueryResult` construction |
| `_valid_*_args(**overrides)` defaults | `test_validation_retention.py:37` | `validate_flow_args()` testing |
| `_codes(errors)` helper | `test_validation_retention.py:67` | Error code extraction |
| `_make_workspace()` inline factory | `test_types_retention_pbt.py:82` | PBT workspace construction |
| MagicMock API client | `test_live_query_bookmarks.py:15` | Service layer testing |
| `@st.composite` strategies | `test_types_retention_pbt.py` | Hypothesis strategies for FlowStep |
| CliRunner with patch | `test_bookmark_commands.py:213` | CLI command testing |

### Test Files to Create

| File | Contents |
|------|----------|
| `tests/test_types_flow.py` | FlowStep, FlowQueryResult construction, df, graph |
| `tests/test_types_flow_pbt.py` | Property-based tests for FlowStep, FlowQueryResult |
| `tests/test_validation_flow.py` | FL1-FL8 rules, L2 flat bookmark validation |
| `tests/unit/test_bookmark_builders_segfilter.py` | Segfilter converter unit tests |
| `tests/unit/test_live_query_flow.py` | Service layer with mocked API |

### Alternatives Considered
- **Single large test file**: Rejected — existing pattern separates types, validation, service, and PBT tests.

---

## 4. NetworkX Integration

### Decision
Add `networkx>=3.0` as a hard dependency. Provide lazy-cached `.graph` property on `FlowQueryResult`.

### Rationale
- 2.1 MB wheel, zero transitive dependencies, pure Python (`py3-none-any`)
- Lighter than httpx (already required), no platform-specific builds
- The flows response IS a graph — representing it as one is semantically correct
- Enables one-liner path queries, bottleneck analysis, subgraph extraction

### Graph Construction

Nodes keyed as `"{event}@{step}"` to handle the same event at multiple positions:

```python
G = nx.DiGraph()
for step_idx, step in enumerate(self.steps):
    for node in step.get("nodes", []):
        node_id = f"{node['event']}@{step_idx}"
        G.add_node(node_id, step=step_idx, event=node["event"],
                   type=node.get("type", ""), count=int(node.get("totalCount", "0")), ...)
        for edge in node.get("edges", []):
            target_id = f"{edge['event']}@{edge.get('step', step_idx + 1)}"
            G.add_edge(node_id, target_id, count=int(edge.get("totalCount", "0")), ...)
```

### Alternatives Considered
- **Optional dependency**: Rejected — conditional imports add complexity, and NetworkX is lighter than most existing deps.
- **rustworkx/igraph**: Rejected — compiled wheels, overkill for <50 node graphs.
- **Dict-based graph**: Rejected — forces users to reimplement BFS/DFS.

---

## 5. Method Rename Strategy

### Decision
Rename `query_flows()` → `query_saved_flows()` across all layers. No deprecation shim.

### Rationale
This is a pre-1.0 library. Breaking changes are acceptable. A deprecation shim would add complexity for no benefit. The rename makes the API self-documenting:
- `query_flow()` — build and execute an ad-hoc flow query
- `query_saved_flows()` — retrieve a pre-saved flows report by bookmark ID

### Files Affected

| Layer | File | Old Name | New Name |
|-------|------|----------|----------|
| Workspace | `workspace.py` | `query_flows()` | `query_saved_flows()` |
| Service | `live_query.py` | `query_flows()` | `query_saved_flows()` |
| API Client | `api_client.py` | `query_flows()` | `query_saved_flows()` |
| Tests | `test_live_query_bookmarks.py` | `TestQueryFlows` | `TestQuerySavedFlows` |
| CLI | `cli/commands/query.py` | `flows` command | Update to call `query_saved_flows()` |
| CLI Tests | `test_bookmark_commands.py` | `TestQueryFlows` | `TestQuerySavedFlows` |

### Alternatives Considered
- **Keep both names**: Rejected — confusing; which to use when?
- **Deprecation warning**: Rejected — pre-1.0, no backwards compatibility guarantee.
