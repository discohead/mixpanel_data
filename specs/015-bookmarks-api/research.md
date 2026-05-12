# Research: Bookmarks API Implementation

**Feature**: 015-bookmarks-api
**Date**: 2025-12-25
**Source**: [Bookmarks API Findings](../../context/research/bookmarks-api-findings.md)

## Executive Summary

Research validated the Mixpanel Bookmarks API and its integration with Query APIs. All technical questions have been resolved through API testing against a production Mixpanel project.

## Research Topics

### 1. Bookmarks API Endpoint

**Decision**: Use `GET /api/app/projects/{project_id}/bookmarks` with `v=2` query parameter.

**Rationale**:
- The "app" endpoint type is already configured in the existing `ENDPOINTS` dictionary
- Version 2 provides better response format with structured `results` array
- Supports type filtering via `type` query parameter

**Alternatives Considered**:
- Workspace-scoped endpoint (`/api/app/workspaces/{workspace_id}/bookmarks`) - rejected as project-scoped is more common
- Version 1 API - rejected due to inferior response format

**API Response Structure** (v=2):
```json
{
  "results": [
    {
      "id": 63877017,
      "name": "Monthly Recurring Revenue",
      "type": "insights",
      "project_id": 3409416,
      "workspace_id": null,
      "dashboard_id": null,
      "created": "2024-09-18T16:39:49",
      "modified": "2025-08-26T05:16:50",
      "creator_id": 12345,
      "creator_name": "John Doe",
      "description": "..."
    }
  ]
}
```

### 2. Query Saved Reports Approach

**Decision**: The existing `/api/query/insights` endpoint with `bookmark_id` parameter works for Insights, Retention, AND Funnel bookmarks.

**Rationale**:
- Tested and confirmed: `insights()` method already works for all three report types
- Report type can be detected from response headers:
  - `$retention` in headers → retention report
  - `$funnel` in headers → funnel report
  - Otherwise → insights report
- Normalizes response format across report types

**Alternatives Considered**:
- Separate endpoints per report type - rejected as unnecessary; unified endpoint works
- Native funnel endpoint (`/api/query/arb_funnels`) - considered for richer funnel data but normalized format is sufficient for most use cases

**Key Insight**: Current `insights()` method should be renamed to `query_saved_report()` to accurately describe its broader capability.

### 3. Flows Reports Handling

**Decision**: Flows require a separate endpoint: `GET /api/query/arb_funnels` with `query_type=flows_sankey`.

**Rationale**:
- Flows bookmarks cannot be queried via `/api/query/insights`
- The `arb_funnels` endpoint with `query_type` parameter is the only working approach
- Response format is distinct from other report types (steps, breakdowns, conversion rate)

**Response Structure**:
```json
{
  "steps": [...],
  "breakdowns": [...],
  "overallConversionRate": 0.15,
  "metadata": {...},
  "computed_at": "..."
}
```

### 4. Bookmark Types

**Decision**: Support four primary bookmark types: `insights`, `funnels`, `retention`, `flows`.

**Rationale**:
- These are the most commonly used report types
- `launch-analysis` (Impact Reports) exists but is rare (2 instances in test project vs 2000+ insights)

**Type Distribution** (test project):
| Type | Count |
|------|-------|
| insights | 2,059 |
| funnels | 282 |
| retention | 144 |
| flows | 74 |
| launch-analysis | 2 |

### 5. InsightsResult vs SavedReportResult

**Decision**: Rename `InsightsResult` to `SavedReportResult` and change `series` type from `dict[str, dict[str, int]]` to `dict[str, Any]`.

**Rationale**:
- The name `InsightsResult` is misleading since it works for retention and funnel bookmarks too
- Retention data has deeply nested structures that don't fit `dict[str, dict[str, int]]`
- Adding `report_type` property enables callers to determine data format

**New Type Structure**:
```python
@dataclass(frozen=True)
class SavedReportResult:
    bookmark_id: int
    computed_at: str
    from_date: str
    to_date: str
    headers: list[str]
    series: dict[str, Any]  # Changed from dict[str, dict[str, int]]

    @property
    def report_type(self) -> Literal["insights", "retention", "funnel"]:
        if "$retention" in self.headers:
            return "retention"
        if "$funnel" in self.headers:
            return "funnel"
        return "insights"
```

### 6. Regional Endpoint Support

**Decision**: Use existing regional endpoint configuration from `ENDPOINTS` dictionary.

**Rationale**:
- All three regions (US, EU, India) use the same path patterns
- Base URLs already configured: `mixpanel.com`, `eu.mixpanel.com`, `in.mixpanel.com`
- The "app" endpoint type follows the same regional pattern

### 7. Error Handling Patterns

**Decision**: Follow existing exception hierarchy: `AuthenticationError` (401), `QueryError` (400/403/404).

**Rationale**:
- Consistent with other API methods in the codebase
- Provides clear, actionable error messages
- Exit codes follow constitution (2=auth, 3=invalid args, 4=not found)

## Existing Code Patterns to Follow

### Type Definitions (types.py)
- Frozen dataclasses with `@dataclass(frozen=True)`
- Lazy DataFrame conversion via `_df_cache` pattern
- `to_dict()` method for JSON serialization
- `object.__setattr__` for setting cached values in frozen dataclasses

### API Client (api_client.py)
- `_build_url(endpoint_type, path)` for URL construction
- `_request(method, url, params=params)` for HTTP calls
- `inject_project_id` parameter for path-based project IDs

### Service Layer
- API client returns raw dicts; services transform to typed results
- `_transform_*` functions for response transformation
- Services accept API client via constructor

### Workspace Facade
- Lazy service initialization via properties
- Delegates to appropriate service methods
- Provides typed return values

### CLI Commands
- `@command_app.command("name")` decorator
- `@handle_errors` decorator for exception handling
- `output_result(ctx, data, format=format)` for output
- `FormatOption` for format parameter

## Resolved Clarifications

All technical questions have been resolved:

1. **API endpoint for listing bookmarks**: `/api/app/projects/{project_id}/bookmarks` with `v=2`
2. **Query approach for saved reports**: Unified `/api/query/insights` endpoint with `bookmark_id`
3. **Flows handling**: Separate `/api/query/arb_funnels` endpoint with `query_type=flows_sankey`
4. **Report type detection**: Inspect `headers` array for `$retention` or `$funnel`
5. **Type renaming**: `InsightsResult` → `SavedReportResult` (breaking change acceptable - not released)
6. **Series type flexibility**: Change to `dict[str, Any]` to accommodate nested retention data
