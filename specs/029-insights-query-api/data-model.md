# Data Model: Workspace.query() — Typed Insights Query API

**Feature**: 029-insights-query-api  
**Date**: 2026-04-04

## Entities

### Metric

Encapsulates a single event to query with its aggregation settings.

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| event | string | Yes | — | Mixpanel event name |
| math | MathType | No | "total" | Aggregation function |
| property | string or null | No | null | Property name for property-based math |
| per_user | PerUserAggregation or null | No | null | Per-user pre-aggregation |
| filters | list of Filter or null | No | null | Per-metric filters |

**Validation rules**:
- If `math` is a property-based type, `property` is required
- If `math` is not property-based, `property` must be null
- `per_user` is incompatible with DAU/WAU/MAU math types

**Relationships**: Contains zero or more Filter entities. Referenced by position (A, B, C...) in formula expressions.

### Filter

Represents a typed filter condition on a property.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| _property | string | Yes | Property name to filter on |
| _operator | string | Yes | Internal operator string |
| _value | any | Yes | Value(s) to compare against |
| _property_type | FilterPropertyType | Yes | Data type of the property |
| _resource_type | "events" or "people" | Yes | Resource type to filter |

**Construction**: Created exclusively via class methods — never instantiated directly.

| Class Method | Input Types | Description |
|-------------|-------------|-------------|
| equals | string, string or list[string] | String equality |
| not_equals | string, string or list[string] | String inequality |
| contains | string, string | Substring containment |
| not_contains | string, string | Substring non-containment |
| greater_than | string, number | Numeric greater than |
| less_than | string, number | Numeric less than |
| between | string, number, number | Numeric range (inclusive) |
| is_set | string | Property existence |
| is_not_set | string | Property non-existence |
| is_true | string | Boolean true |
| is_false | string | Boolean false |

**Serialization**: Each class method maps to specific `filterType`, `filterOperator`, and `filterValue` format in the bookmark JSON. The mapping is internal — callers never see raw filter JSON.

### GroupBy

Specifies a property breakdown with optional numeric bucketing.

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| property | string | Yes | — | Property name to break down by |
| property_type | "string", "number", "boolean", "datetime" | No | "string" | Data type of the property |
| bucket_size | number or null | No | null | Bucket width for numeric properties |
| bucket_min | number or null | No | null | Minimum value for numeric buckets |
| bucket_max | number or null | No | null | Maximum value for numeric buckets |

**Validation rules**:
- `bucket_min` or `bucket_max` requires `bucket_size`
- `bucket_size` must be positive

### QueryResult

Structured output from a query execution.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| computed_at | string | Yes | When the query was computed (ISO format) |
| from_date | string | Yes | Effective start date from response |
| to_date | string | Yes | Effective end date from response |
| headers | list of string | Yes | Column headers from the insights response |
| series | dict | Yes | Query result data (structure varies by mode) |
| params | dict | Yes | Generated bookmark params sent to API |
| meta | dict | Yes | Response metadata (sampling, limits) |

**Inherits from**: ResultWithDataFrame (provides `df` property and `to_table_dict()`)

**Series structure by mode**:
- Timeseries: `{metric_name: {date_string: value}}`
- Total: `{metric_name: {"all": value}}`
- Table: `{metric_name: {date_string: value}}` (same as timeseries)

**DataFrame columns by mode**:
- Timeseries: `date`, `event`, `count`
- Total: `event`, `count`
- With breakdown: adds breakdown column name(s)

## Type Aliases

| Alias | Type | Values |
|-------|------|--------|
| MathType | Literal | "total", "unique", "dau", "wau", "mau", "average", "median", "min", "max", "sum", "p25", "p75", "p90", "p99" |
| PerUserAggregation | Literal | "average", "total", "min", "max" |
| FilterPropertyType | Literal | "string", "number", "boolean", "datetime", "list" |

## Constants

| Constant | Type | Values | Purpose |
|----------|------|--------|---------|
| PROPERTY_MATH_TYPES | set of string | {"average", "median", "min", "max", "sum", "p25", "p75", "p90", "p99"} | Math types requiring a property |
| NO_PER_USER_MATH_TYPES | set of string | {"dau", "wau", "mau"} | Math types incompatible with per_user |

## Entity Relationships

```
Workspace.query()
    ├── accepts: str | Metric | list[str | Metric]  (events)
    │       └── Metric contains: list[Filter] (optional per-metric filters)
    ├── accepts: Filter | list[Filter]  (global where clause)
    ├── accepts: str | GroupBy | list[str | GroupBy]  (breakdowns)
    └── returns: QueryResult
            ├── contains: dict (series data)
            ├── contains: dict (generated bookmark params)
            ├── contains: dict (response metadata)
            └── provides: DataFrame (via .df property)
```
