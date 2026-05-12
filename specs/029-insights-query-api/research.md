# Research: Workspace.query() — Typed Insights Query API

**Feature**: 029-insights-query-api  
**Date**: 2026-04-04

## 1. Execution Path: Inline Params via POST

**Decision**: POST inline bookmark params directly to `/api/query/insights`.

**Rationale**: Confirmed working via live testing against `ecommerce-demo` project with Basic Auth. Single API call, no side effects, no temporary bookmark creation/deletion needed.

**Alternatives considered**:
- Create bookmark → query by ID → delete: Three API calls, transient state, requires App API access. Rejected.
- Extend existing `segmentation()`: Different API endpoint, different capabilities. Would break its simple interface. Rejected.

**Request format**:
```
POST /api/query/insights
Content-Type: application/json
Authorization: Basic <base64(username:secret)>

{
  "project_id": <int>,
  "bookmark": { <bookmark params dict> },
  "queryLimits": {"limit": 3000}
}
```

**Critical detail**: `project_id` goes in the request body, NOT in query params. The API client's `_request` auto-injects `project_id` into query params, so the implementation must use `inject_project_id=False` and include `project_id` manually in the body dict.

**Critical detail**: `queryLimits` goes at the top level of the request body, NOT inside the `bookmark` dict. The server rejects `queryLimits` inside bookmark with `"Extra inputs are not permitted at queryLimits"`.

## 2. Response Format

**Decision**: Parse the inline params response format, which differs slightly from `query_saved_report()`.

**Rationale**: The response structure is documented and confirmed via live testing.

**Response shape (timeseries)**:
```json
{
  "computed_at": "2026-04-03T06:11:50.670473+00:00",
  "date_range": {
    "from_date": "2023-05-25T00:00:00-07:00",
    "to_date": "2023-05-31T23:59:59.999000-07:00"
  },
  "headers": ["$metric"],
  "series": {
    "Product Added [Total Events]": {
      "2023-05-25T00:00:00-07:00": 756,
      "2023-05-26T00:00:00-07:00": 795
    }
  },
  "meta": {
    "min_sampling_factor": 1.0,
    "is_segmentation_limit_hit": false,
    "sub_query_count": 1,
    "report_sections": { ... }
  }
}
```

**Response shape (total mode — `chartType: "bar"`)**:
```json
{
  "series": {
    "Product Added [Unique Users]": {"all": 3551}
  }
}
```

**Key differences from `query_saved_report()`**:
- Date range is nested: `date_range.from_date` (not flat)
- `meta` field is present (absent in saved report response)
- No `bookmark_id` field (not applicable)
- Series key format same: `"Event Name [Math Label]"`

**Alternatives considered**:
- Reuse `SavedReportResult` with optional bookmark_id: Would require sentinel values, vestigial fields. Rejected.
- Return raw dict: No type safety, no .df property. Rejected.

## 3. Architecture Layering

**Decision**: Follow the three-layer pattern: API Client → Service → Workspace.

**Rationale**: Every existing query method follows this pattern. Consistency reduces cognitive overhead and ensures the same error handling, retry, and auth mechanisms apply.

**Layers**:
1. **API Client** (`api_client.py`): `insights_query(body: dict) -> dict` — low-level POST
2. **Service** (`live_query.py`): `query(bookmark_params: dict) -> QueryResult` — transforms response
3. **Workspace** (`workspace.py`): `query(events, *, ...) -> QueryResult` — validates args, builds bookmark params, delegates

**Key insight**: All bookmark params construction and validation happens in the Workspace layer, not the service layer. The service receives pre-built bookmark params and handles only API communication and response transformation.

## 4. Type System Integration

**Decision**: Define new types in `types.py` (public) for user-facing types; add literal aliases to `_literal_types.py` for internal use.

**Rationale**: Follows existing conventions. `BookmarkType`, `SavedReportType`, and result dataclasses are all in `types.py`. Internal literal types like `TimeUnit`, `CountType` are in `_literal_types.py`.

**New public types** (in `types.py`):
- `Metric` — frozen dataclass
- `Filter` — frozen dataclass with class methods
- `GroupBy` — frozen dataclass
- `QueryResult` — frozen dataclass extending `ResultWithDataFrame`
- `MathType` — Literal type alias
- `PerUserAggregation` — Literal type alias

**Alternatives considered**:
- Pydantic models for Metric/Filter/GroupBy: Overkill for simple value objects. Frozen dataclasses are lighter and match existing result types. Rejected.
- Separate module for query types: Would split related types across files unnecessarily. The existing types.py handles all result types. Rejected.

## 5. Bookmark Params Building

**Decision**: Build bookmark params as a plain dict in the Workspace layer via a private `_build_query_params()` method.

**Rationale**: Keeps the complex JSON construction logic contained in one place, testable independently, and separate from validation logic.

**Canonical reference**: `mixpanel-plugin/skills/mixpanel-analyst/references/bookmark-params.md` is the authoritative source for the Mixpanel bookmark JSON schema. The format below was confirmed via live QA against project 8.

**Show entry structure** — each metric in `sections.show[]`:
```json
{
  "type": "metric",
  "behavior": {
    "type": "event",
    "name": "Event Name",
    "resourceType": "events",
    "filtersDeterminer": "all",
    "filters": []
  },
  "measurement": {"math": "total"}
}
```

**Key**: Event name goes in `behavior.name` (NOT `dataset.$event_name`). Aggregation type goes in `measurement.math` (NOT `measurement.event_type`).

**Property aggregation** — `measurement.property` is an object, not a string:
```json
"measurement": {
  "math": "average",
  "property": {"name": "Amount", "resourceType": "events"}
}
```

**Time section** — `sections.time` is an **array** of time entries:
```json
// Relative (last N days)
[{"dateRangeType": "in the last", "unit": "day", "window": {"unit": "day", "value": 30}}]

// Absolute (between two dates)
[{"dateRangeType": "between", "unit": "day", "value": ["2024-01-01", "2024-03-31"]}]
```

**Important**: The `"since"` dateRangeType only accepts preset tokens (e.g., `$start_of_current_day`), NOT raw date strings. For `from_date`-only queries, use `"between"` with `[from_date, today]`.

**Formula entry** — appended to `sections.show[]` (NOT `sections.formula`):
```json
{
  "type": "formula",
  "definition": "(A / B) * 100",
  "name": "Conversion Rate",
  "measurement": {},
  "referencedMetrics": []
}
```

**Filter entry** — in `sections.filter[]` or `behavior.filters[]`:
```json
{
  "resourceType": "events",
  "filterType": "string",
  "defaultType": "string",
  "value": "$browser",
  "filterValue": ["Chrome"],
  "filterOperator": "equals"
}
```

**Group entry** — in `sections.group[]`:
```json
{
  "value": "$browser",
  "propertyName": "$browser",
  "resourceType": "events",
  "propertyType": "string",
  "propertyDefaultType": "string"
}
```

**Display options mapping** (confirmed via live testing):
- `mode="timeseries"` → `displayOptions.chartType = "line"`
- `mode="total"` → `displayOptions.chartType = "bar"`
- `mode="table"` → `displayOptions.chartType = "table"`
- `rolling=N` → `displayOptions.analysis = "rolling"` + `rollingWindowSize = N`
- `cumulative=True` → `displayOptions.analysis = "cumulative"`
- Default → `displayOptions.analysis = "linear"`

**Other rules** (confirmed via live testing):
- Hidden metrics (`isHidden: true`) are still computed but excluded from response series
- String filter `filterValue` for equals/not-equals is always an array: `["Chrome"]`
- Numeric filter `filterValue` is a scalar: `18`
- `contains`/`not contains` filter `filterValue` is a plain string: `"Chrome"`
- `sections.filter` and `sections.group` should always be present (empty arrays when unused)

## 6. Validation Strategy

**Decision**: Fail-fast validation at call time via `ValueError` before any API request.

**Rationale**: The Mixpanel server is lenient — it logs warnings for invalid combos but often silently falls back (e.g., `math="average"` without property → silently uses `math="total"`). For a typed API, silent fallbacks are worse than errors. A `ValueError` is immediately actionable.

**Validation is in two phases**:
1. Global validation: top-level parameter combinations (V1-V12)
2. Per-metric validation: each Metric object's fields (V13-V14)

Both run before any bookmark params construction or API call.

## 7. ResultWithDataFrame Extension

**Decision**: `QueryResult` extends `ResultWithDataFrame` with the same frozen-dataclass + lazy-df pattern used by all existing result types.

**Rationale**: Consistency with `SegmentationResult`, `SavedReportResult`, etc. The `df` property uses `object.__setattr__` to cache the DataFrame on frozen instances.

**QueryResult.df behavior**:
- Timeseries: columns = `date`, `event`, `count` — one row per (date, metric) pair
- Total: columns = `event`, `count` — one row per metric
- Breakdown: adds breakdown column(s) based on group_by

**QueryResult extra fields**:
- `params: dict[str, Any]` — the generated bookmark params (for debugging/persistence)
- `meta: dict[str, Any]` — response metadata (sampling factor, limit hit, etc.)
