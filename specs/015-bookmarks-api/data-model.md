# Data Model: Bookmarks API

**Feature**: 015-bookmarks-api
**Date**: 2025-12-25

## Entity Overview

```
┌─────────────────┐      ┌───────────────────────┐      ┌─────────────────┐
│  BookmarkInfo   │      │   SavedReportResult   │      │   FlowsResult   │
├─────────────────┤      ├───────────────────────┤      ├─────────────────┤
│ id              │──┐   │ bookmark_id           │   ┌──│ bookmark_id     │
│ name            │  │   │ computed_at           │   │  │ computed_at     │
│ type            │  │   │ from_date             │   │  │ steps           │
│ project_id      │  │   │ to_date               │   │  │ breakdowns      │
│ created         │  └──>│ headers               │   │  │ overall_rate    │
│ modified        │      │ series                │   │  │ metadata        │
│ workspace_id?   │      │ report_type (derived) │   │  └─────────────────┘
│ dashboard_id?   │      └───────────────────────┘   │
│ description?    │                                   │
│ creator_id?     │      ┌───────────────────────────┘
│ creator_name?   │      │
└─────────────────┘      │  Bookmark ID links
                         │  metadata to query results
```

## Type Definitions

### BookmarkType (Literal)

Constrained string values for report types.

```python
BookmarkType = Literal["insights", "funnels", "retention", "flows", "launch-analysis"]
```

**Values**:
| Value | Description |
|-------|-------------|
| `insights` | Standard metrics/events reports |
| `funnels` | Funnel conversion reports |
| `retention` | Cohort retention reports |
| `flows` | User path/navigation reports |
| `launch-analysis` | Impact/experiment reports (rare) |

### SavedReportType (Literal)

Report type detected from query results.

```python
SavedReportType = Literal["insights", "retention", "funnel"]
```

**Detection Logic**: Derived from `headers` array in query response.

---

### BookmarkInfo (Entity)

Metadata for a saved report from the Bookmarks API.

**Attributes**:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | `int` | Yes | Unique bookmark identifier |
| `name` | `str` | Yes | User-defined report name |
| `type` | `BookmarkType` | Yes | Report type |
| `project_id` | `int` | Yes | Parent project ID |
| `created` | `str` | Yes | Creation timestamp (ISO format) |
| `modified` | `str` | Yes | Last modification timestamp |
| `workspace_id` | `int \| None` | No | Workspace ID if scoped |
| `dashboard_id` | `int \| None` | No | Parent dashboard ID if linked |
| `description` | `str \| None` | No | User-provided description |
| `creator_id` | `int \| None` | No | Creator's user ID |
| `creator_name` | `str \| None` | No | Creator's display name |

**Validation Rules**:
- `id` must be positive integer
- `type` must be valid BookmarkType
- Timestamps must be ISO 8601 format

**Immutability**: Frozen dataclass (no mutations after creation)

**Serialization**: `to_dict()` method returns all fields as JSON-compatible dict

---

### SavedReportResult (Entity)

Data returned from querying a saved Insights, Retention, or Funnel report.

**Replaces**: `InsightsResult` (renamed for accuracy)

**Attributes**:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `bookmark_id` | `int` | Yes | Saved report identifier |
| `computed_at` | `str` | Yes | When report was computed (ISO) |
| `from_date` | `str` | Yes | Report start date |
| `to_date` | `str` | Yes | Report end date |
| `headers` | `list[str]` | Yes | Column headers (indicates type) |
| `series` | `dict[str, Any]` | Yes | Report data (structure varies) |

**Derived Properties**:

| Property | Type | Logic |
|----------|------|-------|
| `report_type` | `SavedReportType` | `"retention"` if `$retention` in headers; `"funnel"` if `$funnel` in headers; else `"insights"` |
| `df` | `pd.DataFrame` | Lazy conversion with caching |

**Series Structure by Report Type**:

**Insights**:
```python
{
    "Event Name": {
        "2024-01-01T00:00:00": 150,
        "2024-01-02T00:00:00": 175
    }
}
```

**Retention**:
```python
{
    "born_event and then return_event": {
        "2024-03-18T00:00:00": {
            "$overall": {
                "first": 3123,
                "counts": [1317, 1296, ...],
                "rates": [0.42, 0.41, ...]
            },
            "Segment1": {"first": 1543, ...}
        }
    }
}
```

**Funnel**:
```python
{
    "count": {"1. Step": {"all": 6030}, "2. Step": {"all": 2844}},
    "overall_conv_ratio": {"1. Step": {"all": 1.0}, "2. Step": {"all": 0.47}},
    "step_conv_ratio": {...},
    "avg_time": {...}
}
```

**Validation Rules**:
- `bookmark_id` must be positive integer
- `headers` must be list (may be empty)
- `series` must be dict (may be empty)

**Immutability**: Frozen dataclass with `_df_cache` for lazy computation

---

### FlowsResult (Entity)

Data returned from querying a saved Flows report.

**Attributes**:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `bookmark_id` | `int` | Yes | Saved report identifier |
| `computed_at` | `str` | Yes | When report was computed (ISO) |
| `steps` | `list[dict[str, Any]]` | Yes | Flow step data |
| `breakdowns` | `list[dict[str, Any]]` | Yes | Path breakdown data |
| `overall_conversion_rate` | `float` | Yes | End-to-end conversion rate |
| `metadata` | `dict[str, Any]` | Yes | Additional API metadata |

**Derived Properties**:

| Property | Type | Logic |
|----------|------|-------|
| `df` | `pd.DataFrame` | Converts steps to tabular format |

**Validation Rules**:
- `bookmark_id` must be positive integer
- `overall_conversion_rate` must be 0.0-1.0
- `steps` and `breakdowns` must be lists (may be empty)

**Immutability**: Frozen dataclass with `_df_cache` for lazy computation

---

## Relationships

```
Workspace
    │
    ├── list_bookmarks() ──────> list[BookmarkInfo]
    │
    ├── query_saved_report(bookmark_id) ──────> SavedReportResult
    │       Uses bookmark_id from BookmarkInfo
    │
    └── query_flows(bookmark_id) ──────> FlowsResult
            Uses bookmark_id from BookmarkInfo (type="flows")
```

**Key Relationship**: `BookmarkInfo.id` is used as the `bookmark_id` parameter for query methods.

---

## State Transitions

These entities are **read-only** from the library perspective. No state transitions occur within the library - all state is managed by the Mixpanel API.

| Operation | Input | Output | Side Effects |
|-----------|-------|--------|--------------|
| List bookmarks | filter params | `list[BookmarkInfo]` | None (read-only) |
| Query saved report | bookmark_id | `SavedReportResult` | None (read-only) |
| Query flows | bookmark_id | `FlowsResult` | None (read-only) |

---

## Migration Notes

### Breaking Changes (acceptable - pre-release)

1. **Remove `InsightsResult`** - Replace with `SavedReportResult`
2. **Rename `insights()` methods** - Rename to `query_saved_report()` at all layers
3. **CLI command rename** - `mp query insights` → `mp query saved-report`

### Files Requiring Updates

| File | Changes |
|------|---------|
| `types.py` | Remove `InsightsResult`, add new types |
| `__init__.py` | Update exports |
| `api_client.py` | Rename method, add new methods |
| `live_query.py` | Rename method, add new methods |
| `discovery.py` | Add `list_bookmarks()` |
| `workspace.py` | Rename method, add new methods |
| `query.py` (CLI) | Rename command, add new commands |
| `inspect.py` (CLI) | Add `bookmarks` command |
| All existing tests | Update references to `insights`/`InsightsResult` |
