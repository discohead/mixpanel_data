# Data Model: User Profile Query Engine

**Feature**: 039-query-user-engine  
**Date**: 2026-04-13

---

## Entities

### UserQueryResult

Extends `ResultWithDataFrame`. Mode-aware result container for user profile queries.

| Field | Type | Presence | Description |
|-------|------|----------|-------------|
| `computed_at` | `str` | Always | ISO timestamp when query was computed |
| `total` | `int` | Always | Number of profiles returned (`len(profiles)`) |
| `profiles` | `list[dict[str, Any]]` | Always | Normalized profile dicts; empty for aggregate mode |
| `params` | `dict[str, Any]` | Always | Engage API params used (for debugging) |
| `meta` | `dict[str, Any]` | Always | Execution metadata |
| `mode` | `Literal["profiles", "aggregate"]` | Always | Output mode |
| `aggregate_data` | `dict[str, Any] \| int \| float \| None` | Always | Aggregate value(s); None for profiles mode |

**Computed properties**:

| Property | Return Type | Mode | Description |
|----------|-------------|------|-------------|
| `df` | `pd.DataFrame` | Both | Lazy cached, mode-aware DataFrame |
| `distinct_ids` | `list[str]` | profiles | List of distinct IDs from profiles |
| `value` | `int \| float \| None` | aggregate | Scalar aggregate result (None if segmented) |

**Meta fields** (profiles mode):

| Key | Type | Description |
|-----|------|-------------|
| `session_id` | `str` | Engage API session ID |
| `pages_fetched` | `int` | Number of pages successfully fetched |
| `failed_pages` | `list[int]` | Page indices that failed (parallel mode) |
| `parallel` | `bool` | Whether parallel fetching was used |
| `workers` | `int` | Number of concurrent workers used |
| `duration_seconds` | `float` | Total fetch duration |

**Meta fields** (aggregate mode):

| Key | Type | Description |
|-----|------|-------------|
| `action` | `str` | Aggregation expression used (e.g., `"count()"`, `"numeric_summary(properties[\"ltv\"])"`) |
| `segmented` | `bool` | Whether cohort segmentation was applied |

---

### ProfilePageResult (existing, extended)

New parameters added to the underlying API client method:

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `sort_key` | `str \| None` | `None` | Sort expression (e.g., `properties["ltv"]`) |
| `sort_order` | `str \| None` | `None` | `"ascending"` or `"descending"` |
| `search` | `str \| None` | `None` | Full-text search term |
| `limit` | `int \| None` | `None` | Server-side result cap |
| `filter_by_cohort` | `str \| None` | `None` | JSON-encoded cohort filter dict |

---

### Filter → Selector Translation

Not a data entity, but a critical data transformation:

| Input | Output | Example |
|-------|--------|---------|
| `Filter` object | Selector string | `Filter.equals("plan", "premium")` → `'properties["plan"] == "premium"'` |
| `list[Filter]` | AND-combined selector | `[Filter.equals("plan", "premium"), Filter.is_set("email")]` → `'properties["plan"] == "premium" and defined(properties["email"])'` |
| `str` | Passthrough | `'properties["plan"] == "premium"'` → `'properties["plan"] == "premium"'` |

---

### ValidationError Codes

**Layer 1: Argument Validation (U1-U24)**

| Code | Rule | Severity |
|------|------|----------|
| U1 | `distinct_id` and `distinct_ids` mutually exclusive | error |
| U2 | `cohort` and `Filter.in_cohort()` in `where` mutually exclusive | error |
| U3 | `limit` must be positive if provided | error |
| U4 | `distinct_ids` must be non-empty list | error |
| U5 | `sort_by` must be non-empty string | error |
| U6 | `as_of` string must be valid YYYY-MM-DD | error |
| U7 | `include_all_users` requires `cohort` | error |
| U8 | `as_of` must not be in the future | error |
| U9 | `where` as string and Filter are mutually exclusive types | error |
| U10 | Filter property names must be non-empty | error |
| U11 | `properties` items must be non-empty strings | error |
| U12 | `Filter.not_in_cohort()` not supported | error |
| U13 | At most one `Filter.in_cohort()` in where list | error |
| U14 | `aggregate_property` required when `aggregate` is not "count" | error |
| U15 | `aggregate_property` must not be set when `aggregate` is "count" | error |
| U16 | `segment_by` requires `mode="aggregate"` | error |
| U17 | `segment_by` IDs must be positive integers | error |
| U18 | `parallel` only applies to `mode="profiles"` | error |
| U19 | `sort_by` only applies to `mode="profiles"` | error |
| U20 | `search` only applies to `mode="profiles"` | error |
| U21 | `distinct_id`/`distinct_ids` only apply to `mode="profiles"` | error |
| U22 | `properties` only applies to `mode="profiles"` | error |
| U23 | `workers` must be between 1 and 5 | error |
| U24 | `CohortDefinition.to_dict()` must succeed | error |
| U25 | Filter `_property` must be a string type | error |
| U26 | `percentile` required when `aggregate="percentile"` | error |
| U27 | `percentile` must NOT be set when `aggregate != "percentile"` | error |
| U28 | `percentile` must be between 0 and 100 exclusive | error |

**Layer 2: Parameter Validation (UP1-UP4)**

| Code | Rule | Severity |
|------|------|----------|
| UP1 | `sort_order` must be "ascending" or "descending" | error |
| UP2 | `filter_by_cohort` must have "id" or "raw_cohort" key | error |
| UP3 | `output_properties` must be non-empty array if present | error |
| UP4 | `action` must be valid aggregation expression | error |

---

## Relationships

```
Workspace
  ├── query_user()          → UserQueryResult
  ├── build_user_params()   → dict[str, Any]
  ├── stream_profiles()     → Iterator[dict]   (existing, unchanged)
  │
  ├── _resolve_and_build_user_params()
  │   ├── validate_user_args()          [user_validators.py]
  │   ├── filter_to_selector()          [user_builders.py]
  │   ├── extract_cohort_filter()       [user_builders.py]
  │   └── validate_user_params()        [user_validators.py]
  │
  ├── _execute_user_query_sequential()
  │   └── api_client.export_profiles_page()
  │
  ├── _execute_user_query_parallel()
  │   └── ThreadPoolExecutor
  │       └── api_client.export_profiles_page()
  │
  └── _execute_user_aggregate()
      └── api_client.engage_stats()     [NEW]

Filter ──[filter_to_selector()]──→ Selector string ──→ engage API `where` param
CohortDefinition ──[to_dict()]──→ raw_cohort dict ──→ engage API `filter_by_cohort` param
```

---

## DataFrame Schemas

### Profile Mode

| Column | Type | Source | Always Present |
|--------|------|--------|----------------|
| `distinct_id` | `str` | `profile["distinct_id"]` | Yes (first column) |
| `last_seen` | `str` | `profile["last_seen"]` | Yes |
| `<property>` | varies | `profile["properties"]["<prop>"]` | Only if present on profile |

- `$` prefix stripped from built-in property names: `$email` → `email`
- If `properties` param specified, only those columns appear (plus `distinct_id`, `last_seen`)
- Missing properties filled with `NaN`
- Columns sorted alphabetically after `distinct_id` and `last_seen`

### Aggregate Mode (unsegmented)

| Column | Type | Description |
|--------|------|-------------|
| `metric` | `str` | e.g., `"count()"`, `"numeric_summary(properties[\"ltv\"])"` |
| `value` | `int \| float` | Aggregate result |

### Aggregate Mode (segmented)

| Column | Type | Description |
|--------|------|-------------|
| `segment` | `str` | e.g., `"cohort_123"` |
| `value` | `int \| float` | Aggregate result per segment |
