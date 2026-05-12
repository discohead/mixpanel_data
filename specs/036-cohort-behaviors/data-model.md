# Data Model: Cohort Behaviors

**Date**: 2026-04-06

## Entities

### Filter (extended)

Existing frozen dataclass. Two new class methods added:

| Method | Parameters | Internal Fields Set |
|--------|-----------|-------------------|
| `in_cohort(cohort, name)` | `cohort: int \| CohortDefinition`, `name: str \| None = None` | `_property="$cohorts"`, `_operator="contains"`, `_value=[{cohort: {...}}]`, `_property_type="list"`, `_resource_type="events"` |
| `not_in_cohort(cohort, name)` | `cohort: int \| CohortDefinition`, `name: str \| None = None` | `_property="$cohorts"`, `_operator="does not contain"`, `_value=[{cohort: {...}}]`, `_property_type="list"`, `_resource_type="events"` |

**`_value` structure for saved cohort (int)**:
```json
[{"cohort": {"id": 123, "name": "Power Users", "negated": false}}]
```

**`_value` structure for inline cohort (CohortDefinition)**:
```json
[{"cohort": {"raw_cohort": {"selector": {...}, "behaviors": {...}}, "name": "Power Users", "negated": false}}]
```

**Validation rules**:
- CF1: `cohort` must be a positive integer (when int) — `ValueError`
- CF2: `name`, if provided, must be non-empty — `ValueError`

### CohortBreakdown (new)

Frozen dataclass representing a cohort-based breakdown dimension.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `cohort` | `int \| CohortDefinition` | (required) | Saved cohort ID or inline definition |
| `name` | `str \| None` | `None` | Display name. Required for inline definitions. |
| `include_negated` | `bool` | `True` | Whether to include "Not In" segment |

**Validation rules** (at construction via `__post_init__`):
- CB1: `cohort` must be a positive integer (when int) — `ValueError`
- CB2: `name`, if provided, must be non-empty — `ValueError`
- CB3: Cannot mix with `GroupBy` in `query_retention()` — enforced in `validate_retention_args()`

**Bookmark JSON output** (via `build_group_section()`):

For saved cohort with `include_negated=True`:
```json
{
  "value": ["Power Users", "Not In Power Users"],
  "resourceType": "events",
  "profileType": null,
  "search": "",
  "dataGroupId": null,
  "propertyType": null,
  "typeCast": null,
  "cohorts": [
    {"id": 123, "name": "Power Users", "negated": false, "data_group_id": null, "groups": []},
    {"id": 123, "name": "Power Users", "negated": true, "data_group_id": null, "groups": []}
  ],
  "isHidden": false
}
```

### CohortMetric (new)

Frozen dataclass representing a cohort size metric.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `cohort` | `int \| CohortDefinition` | (required) | Saved cohort ID or inline definition |
| `name` | `str \| None` | `None` | Display name / series label. Required for inline definitions. |

**Validation rules** (at construction via `__post_init__`):
- CM1: `cohort` must be a positive integer (when int) — `ValueError`
- CM2: `name`, if provided, must be non-empty — `ValueError`
- CM3: Top-level `math`/`math_property`/`per_user` ignored — enforced in `_build_query_params()`
- CM4: Insights-only — enforced by type signatures + `_resolve_and_build_params()` type guard

**Bookmark JSON output** (via `_build_query_params()`):

For saved cohort:
```json
{
  "type": "metric",
  "behavior": {
    "type": "cohort",
    "name": "Power Users",
    "id": 123,
    "resourceType": "cohorts",
    "dataGroupId": null,
    "dataset": "$mixpanel",
    "filtersDeterminer": "all",
    "filters": []
  },
  "measurement": {
    "math": "unique",
    "property": null,
    "perUserAggregation": null
  },
  "isHidden": false
}
```

For inline CohortDefinition:
```json
{
  "type": "metric",
  "behavior": {
    "type": "cohort",
    "name": "Active Premium",
    "raw_cohort": {"selector": {...}, "behaviors": {...}},
    "resourceType": "cohorts",
    "dataGroupId": null,
    "dataset": "$mixpanel",
    "filtersDeterminer": "all",
    "filters": []
  },
  "measurement": {
    "math": "unique",
    "property": null,
    "perUserAggregation": null
  },
  "isHidden": false
}
```

### CohortDefinition (existing, unchanged)

Used as the inline cohort type across all three integration points. Produces `{"selector": {...}, "behaviors": {...}}` via `to_dict()`.

## Relationships

```
Filter.in_cohort() ──→ accepts ──→ int | CohortDefinition
CohortBreakdown    ──→ accepts ──→ int | CohortDefinition
CohortMetric       ──→ accepts ──→ int | CohortDefinition

Filter.in_cohort()  ──→ used in ──→ query(), query_funnel(), query_retention(), query_flow()
CohortBreakdown     ──→ used in ──→ query(), query_funnel(), query_retention()
CohortMetric        ──→ used in ──→ query() only
```

## Validation Rule Summary

| Code | Type | Rule | Enforced In |
|------|------|------|-------------|
| CF1 | Filter | `cohort` (int) must be positive | `Filter.in_cohort()` / `Filter.not_in_cohort()` |
| CF2 | Filter | `name` must be non-empty when provided | `Filter.in_cohort()` / `Filter.not_in_cohort()` |
| CB1 | Breakdown | `cohort` (int) must be positive | `CohortBreakdown.__post_init__()` |
| CB2 | Breakdown | `name` must be non-empty when provided | `CohortBreakdown.__post_init__()` |
| CB3 | Breakdown | Mutually exclusive with `GroupBy` in retention | `validate_retention_args()` |
| CM1 | Metric | `cohort` (int) must be positive | `CohortMetric.__post_init__()` |
| CM2 | Metric | `name` must be non-empty when provided | `CohortMetric.__post_init__()` |
| CM3 | Metric | math/math_property/per_user ignored | `_build_query_params()` |
| CM4 | Metric | Insights-only | Type signatures + type guard |
| B22 | Bookmark | Cohort behavior requires positive int `id` | `_validate_show_clause()` |
| B23 | Bookmark | Cohort behavior `resourceType` must be `"cohorts"` | `_validate_show_clause()` |
| B24 | Bookmark | Cohort behavior `math` must be `"unique"` | `_validate_measurement()` |
| B25 | Bookmark | Cohort filter `value` must be `"$cohorts"` | `_validate_filter_clause()` |
| B26 | Bookmark | Cohort group entry must have non-empty `cohorts` array | `_validate_group_clause()` |

## Type Signature Changes

### `group_by` parameter (query, query_funnel, query_retention)

```
Before: str | GroupBy | list[str | GroupBy] | None
After:  str | GroupBy | CohortBreakdown | list[str | GroupBy | CohortBreakdown] | None
```

### `events` parameter (query only)

```
Before: str | Metric | Formula | Sequence[str | Metric | Formula]
After:  str | Metric | CohortMetric | Formula | Sequence[str | Metric | CohortMetric | Formula]
```

### `where` parameter on query_flow (new)

```
Before: (not present)
After:  where: Filter | list[Filter] | None = None
```

### `Filter._value` field

```
Before: str | int | float | list[str] | list[int | float] | None
After:  str | int | float | list[str] | list[int | float] | list[dict[str, Any]] | None
```
