# Data Model: Unified Query Engine Completeness

**Date**: 2026-04-14
**Feature**: 040-query-engine-completeness

## New Literal Types (`_literal_types.py`)

### SegmentMethod
```
Values: "all", "first"
Context: Retention, funnel, frequency queries (NOT insights)
```

### FunnelReentryMode
```
Values: "default", "basic", "aggressive", "optimized"
Context: Funnel queries only
```

### RetentionUnboundedMode
```
Values: "none", "carry_back", "carry_forward", "consecutive_forward"
Context: Retention queries only
```

### TimeComparisonType
```
Values: "relative", "absolute-start", "absolute-end"
Context: Insights, funnel, retention queries (NOT flows)
```

### TimeComparisonUnit
```
Values: "day", "week", "month", "quarter", "year"
Context: Used with TimeComparisonType="relative"
```

### CohortAggregationType
```
Values: "total", "unique", "average", "min", "max", "median"
Context: CohortCriteria.did_event() behavioral conditions
```

### FlowSessionEvent
```
Values: "start", "end"
Context: FlowStep for session start/end anchors
```

## Expanded Literal Types

### MathType (15 → 22 values)
```
Added: "cumulative_unique", "sessions", "unique_values", "most_frequent",
       "first_value", "multi_attribution", "numeric_summary"
```

### RetentionMathType (2 → 4 values)
```
Added: "total", "average"
```

### FunnelMathType (13 → 14 values)
```
Added: "histogram"
```

## New Dataclasses (`types.py`)

### TimeComparison (frozen dataclass)

Discriminated union for period-over-period comparison.

| Field | Type | Default | Notes |
|-------|------|---------|-------|
| `type` | `TimeComparisonType` | Required | Discriminant: relative, absolute-start, absolute-end |
| `unit` | `TimeComparisonUnit \| None` | `None` | Required when type="relative" |
| `date` | `str \| None` | `None` | Required when type=absolute-*; YYYY-MM-DD format |

Validation:
- TC1: type="relative" requires unit, rejects date
- TC2: type="absolute-start" or "absolute-end" requires date (YYYY-MM-DD), rejects unit
- TC3: date must be valid YYYY-MM-DD

Factory methods:
- `TimeComparison.relative(unit)` → type="relative"
- `TimeComparison.absolute_start(date)` → type="absolute-start"
- `TimeComparison.absolute_end(date)` → type="absolute-end"

### FrequencyBreakdown (frozen dataclass)

Break down queries by event frequency.

| Field | Type | Default | Notes |
|-------|------|---------|-------|
| `event` | `str` | Required | Event name to count frequency of |
| `bucket_size` | `int` | `1` | Width of frequency buckets |
| `bucket_min` | `int` | `0` | Minimum frequency value |
| `bucket_max` | `int` | `10` | Maximum frequency value |
| `label` | `str \| None` | `None` | Display label (defaults to "{event} Frequency") |

Validation:
- FB1: event must be non-empty
- FB2: bucket_size must be positive
- FB3: bucket_min must be < bucket_max
- FB4: bucket_min must be >= 0

### FrequencyFilter (frozen dataclass)

Filter queries by event frequency threshold.

| Field | Type | Default | Notes |
|-------|------|---------|-------|
| `event` | `str` | Required | Event name to filter by frequency of |
| `operator` | `str` | `"is at least"` | Comparison operator |
| `value` | `int \| float` | Required | Threshold value |
| `date_range_value` | `int \| None` | `None` | Lookback window size (None = lifetime) |
| `date_range_unit` | `Literal["day","week","month"] \| None` | `None` | Lookback window unit |
| `event_filters` | `list[Filter] \| None` | `None` | Property filters on the frequency event |
| `label` | `str \| None` | `None` | Display label |

Validation:
- FF1: event must be non-empty
- FF2: operator must be in {"is at least", "is at most", "is greater than", "is less than", "is equal to", "is between"}
- FF3: value must be non-negative
- FF4: date_range_value and date_range_unit must both be set or both be None
- FF5: date_range_value must be positive if set

## Modified Entities

### Metric (add 1 field)

| New Field | Type | Default |
|-----------|------|---------|
| `segment_method` | `SegmentMethod \| None` | `None` |

### Filter (add 7 factory methods)

| Method | Operator String | Property Type | Value Type |
|--------|----------------|--------------|------------|
| `not_between(prop, min, max)` | `"not between"` | number | `[min, max]` |
| `starts_with(prop, prefix)` | `"starts with"` | string | `str` |
| `ends_with(prop, suffix)` | `"ends with"` | string | `str` |
| `date_not_between(prop, from, to)` | `"was not between"` | datetime | `[from, to]` |
| `in_the_next(prop, qty, unit)` | `"was in the next"` | datetime | `qty` |
| `at_least(prop, val)` | `"is at least"` | number | `val` |
| `at_most(prop, val)` | `"is at most"` | number | `val` |

### CohortCriteria.did_event() (add 2 params)

| New Param | Type | Default |
|-----------|------|---------|
| `aggregation` | `CohortAggregationType \| None` | `None` |
| `aggregation_property` | `str \| None` | `None` |

Validation:
- CA1: aggregation requires aggregation_property
- CA2: aggregation_property requires aggregation
- CA3: When aggregation is set, at_least/at_most/exactly provide the comparison threshold for the aggregated property value (e.g., aggregation="average" + at_least=50 means "users whose average >= 50"). When aggregation is NOT set, at_least/at_most/exactly threshold the raw event count (existing behavior). Exactly one of at_least/at_most/exactly is always required.

### FlowStep (add 1 field)

| New Field | Type | Default |
|-----------|------|---------|
| `session_event` | `FlowSessionEvent \| None` | `None` |

Validation:
- FS1: When session_event is set, event must be the corresponding session sentinel ("start" requires "$session_start", "end" requires "$session_end"). Regular event names with session_event are rejected.

### Flow Segments (parameter type)

Flow segments reuse the existing `GroupBy` type for property-based breakdowns of flow paths.

| Parameter | Type | Default | Notes |
|-----------|------|---------|-------|
| `segments` | `GroupBy \| list[GroupBy] \| None` | `None` | Property breakdowns applied to flow paths |

### Flow Exclusions (parameter type)

Flow exclusions accept a simple list of event name strings to exclude between flow steps.
Unlike funnel exclusions (which support `Exclusion` objects with step ranges), flow exclusions
are event-name-only.

| Parameter | Type | Default |
|-----------|------|---------|
| `exclusions` | `list[str] \| None` | `None` |

## Modified Enum Constants (`bookmark_enums.py`)

### MATH_REQUIRING_PROPERTY (add 5 values)
```
Added: "unique_values", "most_frequent", "first_value", "multi_attribution", "numeric_summary"
```

### New Constants
```
VALID_FUNNEL_REENTRY_MODES = frozenset({"default", "basic", "aggressive", "optimized"})
VALID_RETENTION_UNBOUNDED_MODES = frozenset({"none", "carry_back", "carry_forward", "consecutive_forward"})
VALID_SEGMENT_METHODS = frozenset({"all", "first"})
VALID_TIME_COMPARISON_TYPES = frozenset({"relative", "absolute-start", "absolute-end"})
VALID_TIME_COMPARISON_UNITS = frozenset({"day", "week", "month", "quarter", "year"})
VALID_COHORT_AGGREGATION_OPERATORS = frozenset({"total", "unique", "average", "min", "max", "median"})
VALID_FREQUENCY_FILTER_OPERATORS = frozenset({"is at least", "is at most", "is greater than", "is less than", "is equal to", "is between"})
```

## Relationships

```
Metric --uses--> SegmentMethod (optional)
Workspace.query_funnel() --accepts--> FunnelReentryMode, TimeComparison
Workspace.query_retention() --accepts--> RetentionUnboundedMode, TimeComparison, retention_cumulative flag
Workspace.query() --accepts--> TimeComparison, FrequencyBreakdown (via group_by), FrequencyFilter (via where)
Workspace.query_flow() --accepts--> enhanced FlowStep, global property filters, segments, exclusions
FlowStep --uses--> FlowSessionEvent (optional, mutually exclusive with event)
CohortCriteria.did_event() --uses--> CohortAggregationType (optional)
All query methods --accept--> data_group_id: int | None
```
