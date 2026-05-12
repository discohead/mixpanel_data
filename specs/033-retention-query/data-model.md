# Data Model: Retention Query (`query_retention()`)

**Date**: 2026-04-06

## Entities

### RetentionEvent

An event specification for retention queries. Wraps an event name with optional per-event filters.

| Field | Type | Default | Constraints | Description |
|-------|------|---------|-------------|-------------|
| `event` | string | required | Non-empty, no control chars | Mixpanel event name |
| `filters` | list of Filter or null | null | Each filter must be a valid Filter object | Per-event filter conditions |
| `filters_combinator` | "all" or "any" | "all" | Must be one of the two values | How filters combine (AND/OR) |

**Invariants**:
- Immutable (frozen dataclass)
- `event` must be non-empty after stripping whitespace
- `event` must not contain control characters or be invisible-only
- When `filters` is null, no per-event filtering is applied
- Used for both born_event and return_event positions

**Relationships**:
- Contains zero or more `Filter` objects (existing type, reused)
- Consumed by `_build_retention_params()` to generate behavior entries
- Validated by `validate_retention_args()` rules R1 and R2

---

### RetentionQueryResult

The result of a retention query. Contains cohort-level retention data.

| Field | Type | Default | Constraints | Description |
|-------|------|---------|-------------|-------------|
| `computed_at` | string | required | ISO datetime format | When query was computed |
| `from_date` | string | required | YYYY-MM-DD format | Effective start date |
| `to_date` | string | required | YYYY-MM-DD format | Effective end date |
| `cohorts` | dict (string to dict) | empty dict | Keys are cohort date strings | Cohort-level retention data |
| `average` | dict | empty dict | Synthetic `$average` cohort | Average retention across all cohorts |
| `params` | dict | empty dict | Valid bookmark JSON structure | Generated bookmark params sent to API |
| `meta` | dict | empty dict | Free-form | Response metadata (sampling_factor, etc.) |

**Cohort dict structure** (each value in `cohorts`):

| Key | Type | Description |
|-----|------|-------------|
| `first` | int | Cohort size — users who did born_event on this date |
| `counts` | list of int | User counts retained per bucket |
| `rates` | list of float | Retention rates per bucket (count / first) |

**Invariants**:
- Immutable (frozen dataclass)
- Extends `ResultWithDataFrame` — provides `.df` property
- `.df` is lazily computed and cached after first access
- `.df` shape: one row per (cohort_date, bucket) pair
- `.df` columns: `cohort_date`, `bucket`, `count`, `rate`
- Empty `cohorts` produces an empty DataFrame with correct column schema
- `params` always contains the bookmark JSON that was sent to the API

**Relationships**:
- Extends `ResultWithDataFrame` (existing base class)
- Created by `_transform_retention_result()` from raw API response
- Returned by `query_retention()` on the Workspace

---

### RetentionMathType

A constrained type alias for valid retention aggregation functions.

| Value | Description |
|-------|-------------|
| `"retention_rate"` | Percentage of cohort retained (default) |
| `"unique"` | Raw unique user count per bucket |

**Invariants**:
- Type alias (Literal), not a runtime object
- Default value in method signatures is `"retention_rate"`
- Maps directly to the `measurement.math` field in bookmark JSON

## Entity Relationships

```
RetentionEvent (input)
    ├── contains → Filter[] (existing, reused)
    └── consumed by → _build_retention_params()
                          └── produces → bookmark params dict
                                            ├── validated by → validate_retention_args() (L1)
                                            ├── validated by → validate_bookmark() (L2)
                                            └── sent to → insights_query() API
                                                            └── response parsed by → _transform_retention_result()
                                                                                        └── produces → RetentionQueryResult (output)
```

## Validation Rules

### Layer 1: Argument Validation (`validate_retention_args`)

| Code | Field | Rule | Error Message Template |
|------|-------|------|----------------------|
| R1 | born_event | Must be non-empty string (after strip) | `born_event must be a non-empty string` |
| R1b | born_event | No control characters | `born_event contains control characters` |
| R1c | born_event | Not invisible-only | `born_event contains only invisible characters` |
| R2 | return_event | Must be non-empty string (after strip) | `return_event must be a non-empty string` |
| R2b | return_event | No control characters | `return_event contains control characters` |
| R2c | return_event | Not invisible-only | `return_event contains only invisible characters` |
| R3 | time args | Delegated to `validate_time_args()` | (shared V7-V10, V15, V20) |
| R4 | group_by | Delegated to `validate_group_by_args()` | (shared V11-V12, V18, V24) |
| R5 | bucket_sizes | Each value must be positive integer | `bucket_sizes values must be positive integers` |
| R5b | bucket_sizes | Values must be integers, not floats | `bucket_sizes[{i}] must be an integer, got float` |
| R6 | bucket_sizes | Must be in strictly ascending order | `bucket_sizes must be in strictly ascending order` |
| R7 | retention_unit | Must be valid retention unit | `invalid retention_unit '{val}'; valid values: day, week, month` |
| R8 | alignment | Must be valid alignment type | `invalid alignment '{val}'; valid values: birth, interval_start` |
| R9 | math | Must be valid retention math type | `invalid math '{val}'; valid values: retention_rate, unique` |

### Layer 2: Bookmark Structure Validation (extension to `validate_bookmark`)

| Change | Detail |
|--------|--------|
| B9 extension | When `bookmark_type="retention"`, use `VALID_MATH_RETENTION` for math validation instead of `VALID_MATH_INSIGHTS` |

All other B-rules (B1-B8, B10-B19) apply unchanged.
