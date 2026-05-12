# Public API Contract: Retention Query

**Date**: 2026-04-06

## New Public Types

### RetentionEvent

```
RetentionEvent(
    event: str,                              # Required — Mixpanel event name
    filters: list[Filter] | None = None,     # Optional per-event filters
    filters_combinator: "all" | "any" = "all" # How filters combine (AND/OR)
)
```

- Immutable (frozen dataclass)
- Plain event name strings are accepted anywhere `RetentionEvent` is expected — auto-converted internally

### RetentionMathType

```
RetentionMathType = "retention_rate" | "unique"
```

- Type alias (Literal), not a runtime class

### RetentionQueryResult

```
RetentionQueryResult(
    computed_at: str,                        # ISO datetime — when query was computed
    from_date: str,                          # YYYY-MM-DD — effective start date
    to_date: str,                            # YYYY-MM-DD — effective end date
    cohorts: dict[str, dict],                # cohort_date → {first, counts, rates}
    average: dict,                           # Synthetic $average cohort
    params: dict,                            # Generated bookmark params (for debugging/persistence)
    meta: dict,                              # Response metadata
)
```

- Immutable (frozen dataclass), extends `ResultWithDataFrame`
- `.df` → DataFrame with columns: `cohort_date`, `bucket`, `count`, `rate`
- `.df` is lazily computed and cached

## New Public Methods on Workspace

### query_retention()

```
Workspace.query_retention(
    born_event: str | RetentionEvent,
    return_event: str | RetentionEvent,
    *,
    retention_unit: "day" | "week" | "month" = "week",
    alignment: "birth" | "interval_start" = "birth",
    bucket_sizes: list[int] | None = None,
    from_date: str | None = None,
    to_date: str | None = None,
    last: int = 30,
    unit: "hour" | "day" | "week" | "month" | "quarter" = "day",
    math: RetentionMathType = "retention_rate",
    group_by: str | GroupBy | list[str | GroupBy] | None = None,
    where: Filter | list[Filter] | None = None,
    mode: "curve" | "trends" | "table" = "curve",
) -> RetentionQueryResult
```

**Behavior**:
1. Normalizes string events to `RetentionEvent` objects
2. Validates all arguments (Layer 1: R1-R9)
3. Builds retention bookmark params
4. Validates bookmark structure (Layer 2: B1-B19)
5. POSTs to `/insights` via `insights_query()`
6. Transforms response to `RetentionQueryResult`

**Errors**:
- `BookmarkValidationError` — invalid arguments (before API call)
- `ConfigError` — missing credentials
- `QueryError` — API error response
- `RateLimitError` — rate limit exceeded
- `AuthenticationError` — invalid credentials

### build_retention_params()

```
Workspace.build_retention_params(
    born_event: str | RetentionEvent,
    return_event: str | RetentionEvent,
    *,
    # Same keyword arguments as query_retention()
) -> dict
```

**Behavior**: Same as `query_retention()` steps 1-4, but returns the raw params dict instead of querying the API. No API call is made.

## New Exports from `mixpanel_data`

```
from mixpanel_data import RetentionEvent, RetentionMathType, RetentionQueryResult
```

## Reused Types (no changes)

- `Filter` — filter conditions (per-event and global)
- `GroupBy` — property breakdown
- `BookmarkValidationError` — wraps list of `ValidationError`
- `ValidationError` — structured error with path, message, code, severity, suggestion

## Validation Error Codes

| Code | Field | Condition |
|------|-------|-----------|
| R1_EMPTY_BORN_EVENT | born_event | Empty or whitespace-only |
| R1_CONTROL_CHAR_BORN_EVENT | born_event | Contains control characters |
| R1_INVISIBLE_BORN_EVENT | born_event | Only invisible characters |
| R2_EMPTY_RETURN_EVENT | return_event | Empty or whitespace-only |
| R2_CONTROL_CHAR_RETURN_EVENT | return_event | Contains control characters |
| R2_INVISIBLE_RETURN_EVENT | return_event | Only invisible characters |
| R5_BUCKET_SIZES_POSITIVE | bucket_sizes | Contains non-positive values |
| R5_BUCKET_SIZES_INTEGER | bucket_sizes[i] | Contains float values |
| R6_BUCKET_SIZES_ASCENDING | bucket_sizes | Not in strictly ascending order |
| R7_INVALID_RETENTION_UNIT | retention_unit | Not in {day, week, month} |
| R8_INVALID_ALIGNMENT | alignment | Not in {birth, interval_start} |
| R9_INVALID_MATH | math | Not in {retention_rate, unique} |

Plus shared codes from `validate_time_args()` (V7-V10, V15, V20) and `validate_group_by_args()` (V11-V12, V18, V24).
