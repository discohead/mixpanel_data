# Data Model: Phase 1 — Shared Infrastructure Extraction

**Date**: 2026-04-05
**Status**: Complete

## Overview

Phase 1 introduces no new public types. All new entities are internal dict structures (not frozen dataclasses) produced by extracted builder functions. This document defines the shapes of those dict outputs for contract validation.

## Entities

### Time Section Entry (sections-based reports)

Produced by `build_time_section()`. Used by insights, funnels, and retention.

**Variant 1: Absolute date range**
```python
{
    "dateRangeType": "between",       # Literal["between"]
    "unit": str,                       # e.g. "day", "week", "month"
    "value": [str, str],              # [from_date, to_date] in YYYY-MM-DD
}
```

**Variant 2: Relative date range**
```python
{
    "dateRangeType": "in the last",   # Literal["in the last"]
    "unit": str,                       # e.g. "day", "week"
    "window": {
        "unit": "day",                # Always "day" for the window unit
        "value": int,                 # Number of days
    },
}
```

**Invariants**:
- Exactly one of `"value"` or `"window"` is present, never both.
- `dateRangeType` is always one of `{"between", "in the last"}`.
- When `value` is present, both elements are valid `YYYY-MM-DD` strings.
- When `window` is present, `value` is a positive integer.

### Flows Date Range (flat format)

Produced by `build_date_range()`. Used only by flows.

**Variant 1: Relative**
```python
{
    "type": "in the last",
    "from_date": {"unit": "day", "value": int},  # e.g. 30
    "to_date": "$now",
}
```

**Variant 2: Absolute**
```python
{
    "type": "between",
    "from_date": str,     # YYYY-MM-DD
    "to_date": str,       # YYYY-MM-DD
}
```

**Invariants**:
- `type` is always one of `{"in the last", "between"}`.
- When `type` is `"in the last"`, `from_date` is a dict with `unit` and `value`; `to_date` is the string `"$now"`.
- When `type` is `"between"`, both `from_date` and `to_date` are `YYYY-MM-DD` strings.

### Filter Section Entry

Produced by `_build_filter_entry()` (existing) and consumed by `build_filter_section()` (new wrapper).

```python
{
    "resourceType": str,      # e.g. "events", "people"
    "filterType": str,        # e.g. "string", "number", "datetime", "boolean"
    "defaultType": str,       # Same as filterType
    "value": str,             # Property name
    "filterValue": Any,       # Operator-dependent value
    "filterOperator": str,    # e.g. "equals", "is greater than"
    "filterDateUnit": str,    # Optional — only for relative date filters
}
```

### Group Section Entry

Produced by `build_group_section()`.

```python
{
    "value": str,                   # Property name
    "propertyName": str,            # Property name (duplicate of value)
    "resourceType": "events",       # Resource type
    "propertyType": str,            # e.g. "string", "number"
    "propertyDefaultType": str,     # Same as propertyType
    "customBucket": {               # Optional — only when bucket_size is set
        "bucketSize": float,
        "min": float,               # Optional
        "max": float,               # Optional
    },
}
```

### Segfilter Entry

Produced by `build_segfilter_entry()`. Used by flows step filters.

```python
{
    "property": {
        "name": str,               # Property name
        "source": str,             # "properties" | "user" | "cohort" | "other"
        "type": str,               # "string" | "number" | "datetime" | "boolean"
    },
    "type": str,                   # Same as property.type
    "selected_property_type": str, # Same as property.type
    "filter": {
        "operator": str,           # Symbolic: "==", "!=", ">", "<", etc.
        "operand": Any,            # Type-dependent: str, list[str], int, ""
        "unit": str,               # Optional — only for relative date filters
    },
}
```

**Invariants**:
- `property.source` is mapped from `resourceType` via `RESOURCE_TYPE_MAP` (e.g. `"events"` → `"properties"`).
- `type` and `selected_property_type` always equal `property.type`.
- `filter.operator` is omitted for boolean filters (operand carries the value).
- Numeric values in `filter.operand` are always stringified.
- Date values in `filter.operand` use `MM/DD/YYYY` format (not `YYYY-MM-DD`).

## Relationships

```
Workspace._build_query_params()
    ├── calls build_time_section()      → sections.time[]
    ├── calls build_filter_section()    → sections.filter[]
    │         └── calls _build_filter_entry() per Filter
    └── calls build_group_section()     → sections.group[]

(future) Workspace._build_funnel_params()
    ├── calls build_time_section()      → sections.time[]
    ├── calls build_filter_section()    → sections.filter[]
    └── calls build_group_section()     → sections.group[]

(future) Workspace._build_flow_params()
    ├── calls build_date_range()        → date_range (flat)
    └── calls build_segfilter_entry()   → steps[].property_filter_params_list[]
```

## Validation Rules

No new validation entities. Extracted validators (`validate_time_args`, `validate_group_by_args`) return `list[ValidationError]` using the existing `ValidationError` type unchanged.

## Enum Constants (New)

| Constant | Type | Values |
|---|---|---|
| `VALID_FUNNEL_ORDER` | `frozenset[str]` | `{"loose", "any"}` |
| `VALID_CONVERSION_WINDOW_UNITS` | `frozenset[str]` | `{"second", "minute", "hour", "day", "week", "month", "session"}` |
| `VALID_RETENTION_UNITS` | `frozenset[str]` | `{"day", "week", "month"}` |
| `VALID_RETENTION_ALIGNMENT` | `frozenset[str]` | `{"birth", "interval_start"}` |
| `VALID_FLOWS_COUNT_TYPES` | `frozenset[str]` | `{"unique", "total", "session"}` |
| `VALID_FLOWS_CHART_TYPES` | `frozenset[str]` | `{"sankey", "top-paths"}` — user-facing API uses `"paths"` which maps to `"top-paths"` internally |

## Enum Constants (Extended)

| Constant | Added Values |
|---|---|
| `VALID_MATH_FUNNELS` | `"average"`, `"median"`, `"min"`, `"max"`, `"p25"`, `"p75"`, `"p90"`, `"p99"` |
