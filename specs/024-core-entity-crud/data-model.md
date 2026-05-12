# Data Model: Core Entity CRUD

**Phase**: 1 — Design & Contracts
**Feature**: 024-core-entity-crud
**Date**: 2026-03-26

## Entity Overview

```
Dashboard ──< contains >── Bookmark (many-to-many via dashboard_id links)
Dashboard ──< has >── BlueprintTemplate (optional, for template-based creation)
Bookmark ──< has >── BookmarkHistory (one-to-many)
Cohort (standalone, can be referenced by dashboards/reports/flags)
```

## Dashboard Domain

### Dashboard (Response)

Primary entity representing a Mixpanel dashboard.

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| id | int | Yes | Unique identifier |
| title | str | Yes | Dashboard title |
| description | str | No | |
| is_private | bool | Yes | Default: False |
| is_restricted | bool | Yes | Default: False |
| creator_id | int | No | |
| creator_name | str | No | |
| creator_email | str | No | |
| created | datetime | No | Lenient parsing (may be null) |
| modified | datetime | No | Lenient parsing |
| is_favorited | bool | Yes | Default: False |
| pinned_date | str | No | |
| layout_version | Any | No | JSON value |
| unique_view_count | int | No | |
| total_view_count | int | No | |
| last_modified_by_id | int | No | |
| last_modified_by_name | str | No | |
| last_modified_by_email | str | No | |
| filters | list[Any] | No | JSON array |
| breakdowns | list[Any] | No | JSON array |
| time_filter | Any | No | JSON value |
| generation_type | str | No | |
| parent_dashboard_id | int | No | |
| child_dashboards | list[Any] | No | |
| can_update_basic | bool | Yes | Default: False |
| can_share | bool | Yes | Default: False |
| can_view | bool | Yes | Default: False |
| can_update_restricted | bool | Yes | Default: False |
| can_update_visibility | bool | Yes | Default: False |
| is_superadmin | bool | Yes | Default: False |
| allow_staff_override | bool | Yes | Default: False |
| can_pin | bool | Yes | Default: False |
| is_shared_with_project | bool | Yes | Default: False |
| creator | str | No | |
| ancestors | list[Any] | Yes | Default: [] |
| layout | Any | No | JSON value |
| contents | Any | No | JSON value |
| num_active_public_links | int | No | |
| new_content | Any | No | JSON value |
| template_type | str | No | |

**Config**: `frozen=True, extra="allow"` — forward-compatible with new API fields.

### CreateDashboardParams (Input)

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| title | str | Yes | |
| description | str | No | |
| is_private | bool | No | |
| is_restricted | bool | No | |
| filters | list[Any] | No | |
| breakdowns | list[Any] | No | |
| time_filter | Any | No | |
| duplicate | int | No | ID of dashboard to duplicate |

### UpdateDashboardParams (Input)

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| title | str | No | |
| description | str | No | |
| is_private | bool | No | |
| is_restricted | bool | No | |
| filters | list[Any] | No | |
| breakdowns | list[Any] | No | |
| time_filter | Any | No | |
| layout | Any | No | |
| content | Any | No | |

### BlueprintTemplate (Response)

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| title_key | str | Yes | |
| description_key | str | Yes | |
| alternative_description_key | str | No | |
| number_of_reports | int | No | |

### BlueprintConfig (Response)

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| variables | dict[str, str] | Yes | |

### BlueprintCard (Input, used in BlueprintFinishParams)

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| card_type | str | Yes | Serialized as "type" |
| text_card_id | int | No | |
| bookmark_id | int | No | |
| markdown | str | No | |
| name | str | No | |
| params | Any | No | |

### BlueprintFinishParams (Input)

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| dashboard_id | int | Yes | |
| cards | list[BlueprintCard] | Yes | |

### CreateRcaDashboardParams (Input)

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| rca_source_id | int | Yes | |
| rca_source_data | RcaSourceData | Yes | |

### RcaSourceData (Input)

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| source_type | str | Yes | Serialized as "type" |
| date | str | No | |
| metric_source | bool | No | |

### UpdateReportLinkParams (Input)

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| link_type | str | Yes | Serialized as "type" |

### UpdateTextCardParams (Input)

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| markdown | str | No | |

**Config**: `extra="allow"` — allows pass-through of additional fields.

---

## Bookmark/Report Domain

### BookmarkType (Enum/Literal)

Values: `"insights"`, `"funnels"`, `"flows"`, `"retention"`, `"segmentation"`, `"formulas"`, `"all_events"`, and potentially others. Use `str` enum or wide Literal for known types with fallback.

### Bookmark (Response)

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| id | int | Yes | |
| project_id | int | No | |
| name | str | Yes | |
| bookmark_type | str | Yes | Alias: "type" |
| description | str | No | |
| icon | str | No | |
| params | Any | Yes | Query parameters (JSON value) |
| dashboard_id | int | No | |
| include_in_dashboard | bool | No | |
| is_default | bool | No | |
| creator_id | int | No | |
| creator_name | str | No | |
| creator_email | str | No | |
| created | datetime | No | |
| modified | datetime | No | |
| last_modified_by_id | int | No | |
| last_modified_by_name | str | No | |
| last_modified_by_email | str | No | |
| metadata | BookmarkMetadata | No | |
| is_visibility_restricted | bool | No | |
| is_modification_restricted | bool | No | |
| can_update_basic | bool | No | |
| can_view | bool | No | |
| can_share | bool | No | |
| generation_type | str | No | |
| original_type | str | No | |
| unique_view_count | int | No | |
| total_view_count | int | No | |

**Config**: `frozen=True, extra="allow", populate_by_name=True`

### BookmarkMetadata (Response, nested)

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| table_display_mode | str | No | |
| compare_enabled | bool | No | |
| compare_filters | list[Any] | No | |
| retention_calculation_type | str | No | |
| event_name | str | No | |
| funnel_conversion_window | int | No | |
| funnel_breakdown_limit | int | No | |

**Config**: `frozen=True, extra="allow"`

### CreateBookmarkParams (Input)

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| name | str | Yes | |
| bookmark_type | str | Yes | Alias: "type" |
| params | Any | Yes | |
| description | str | No | |
| icon | str | No | |
| dashboard_id | int | No | |
| is_visibility_restricted | bool | No | |
| is_modification_restricted | bool | No | |

### UpdateBookmarkParams (Input)

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| name | str | No | |
| params | Any | No | |
| description | str | No | |
| icon | str | No | |
| dashboard_id | int | No | |
| is_visibility_restricted | bool | No | |
| is_modification_restricted | bool | No | |
| deleted | bool | No | |

### BulkUpdateBookmarkEntry (Input)

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| id | int | Yes | |
| name | str | No | |
| params | Any | No | |
| description | str | No | |
| icon | str | No | |
| is_visibility_restricted | bool | No | |
| is_modification_restricted | bool | No | |

### BookmarkHistoryResponse (Response)

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| results | list[Any] | Yes | Default: [] |
| pagination | BookmarkHistoryPagination | No | |

### BookmarkHistoryPagination (Response, nested)

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| next_cursor | str | No | |
| previous_cursor | str | No | |
| page_size | int | Yes | Default: 0 |

---

## Cohort Domain

### Cohort (Response)

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| id | int | Yes | |
| name | str | Yes | |
| description | str | No | |
| count | int | No | |
| is_visible | bool | No | |
| is_locked | bool | No | |
| data_group_id | str | No | |
| last_edited | str | No | |
| created_by | CohortCreator | No | |
| referenced_by | list[int] | No | |
| verified | bool | Yes | Default: False |
| last_queried | str | No | |
| referenced_directly_by | list[int] | Yes | Default: [] |
| active_integrations | list[int] | Yes | Default: [] |

**Config**: `frozen=True, extra="allow"` — the Rust type uses `#[serde(flatten)]` with HashMap for permissions and extra fields; Pydantic's `extra="allow"` captures both.

### CohortCreator (Response, nested)

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| id | int | No | |
| name | str | No | |
| email | str | No | |

**Config**: `frozen=True, extra="allow"`

### CreateCohortParams (Input)

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| name | str | Yes | |
| description | str | No | |
| data_group_id | str | No | |
| is_locked | bool | No | |
| is_visible | bool | No | |
| deleted | bool | No | |

**Note**: The Rust type uses `#[serde(flatten)]` for the `definition` field (a `Map<String, Value>`). In Python, the definition dict will be merged into the top-level JSON payload at serialization time.

### UpdateCohortParams (Input)

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| name | str | No | |
| description | str | No | |
| data_group_id | str | No | |
| is_locked | bool | No | |
| is_visible | bool | No | |
| deleted | bool | No | |
| definition | dict[str, Any] | No | Flattened into payload |

### BulkUpdateCohortEntry (Input)

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| id | int | Yes | |
| name | str | No | |
| description | str | No | |
| definition | dict[str, Any] | No | Flattened into payload |

---

## Validation Rules

1. **Dashboard.title**: Required, non-empty string
2. **Bookmark.name**: Required, non-empty string
3. **Bookmark.bookmark_type**: Must be a valid BookmarkType value
4. **Bookmark.params**: Required (query parameters define the report)
5. **Cohort.name**: Required, non-empty string
6. **All IDs**: Positive integers
7. **Bulk operation lists**: Non-empty (at least 1 entry)
8. **BlueprintFinishParams.cards**: Non-empty list

## State Transitions

### Dashboard Lifecycle
```
Created → Active → Favorited/Pinned (independent flags)
                 → Deleted
```

### Bookmark Lifecycle
```
Created → Active → Updated (name, params, description)
                → Soft-deleted (deleted=True via update)
                → Hard-deleted (DELETE endpoint)
```

### Cohort Lifecycle
```
Created → Active → Updated (definition, name)
                → Locked (is_locked=True)
                → Deleted
```
