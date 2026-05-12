# Public API Contract: Unified Query Engine Completeness

**Date**: 2026-04-14
**Feature**: 040-query-engine-completeness

All changes are additive. Existing method signatures are unchanged — new parameters are keyword-only with `None` or `False` defaults.

---

## New Exports from `mixpanel_data`

### Literal Types

```python
SegmentMethod = Literal["all", "first"]
FunnelReentryMode = Literal["default", "basic", "aggressive", "optimized"]
RetentionUnboundedMode = Literal["none", "carry_back", "carry_forward", "consecutive_forward"]
TimeComparisonType = Literal["relative", "absolute-start", "absolute-end"]
TimeComparisonUnit = Literal["day", "week", "month", "quarter", "year"]
CohortAggregationType = Literal["total", "unique", "average", "min", "max", "median"]
FlowSessionEvent = Literal["start", "end"]
```

### Dataclasses

```python
TimeComparison      # Frozen dataclass with factory methods
FrequencyBreakdown  # Frozen dataclass for frequency group-by
FrequencyFilter     # Frozen dataclass for frequency where-clause
```

---

## Modified Method Signatures

### Workspace.query() / Workspace.build_params()

```python
def query(
    self,
    events: str | Metric | CohortMetric | Formula | Sequence[...],
    *,
    # ... all existing params unchanged ...
    time_comparison: TimeComparison | None = None,     # NEW (Phase B)
    data_group_id: int | None = None,                  # NEW (Phase C)
) -> QueryResult
```

The `group_by` parameter type union expands to include `FrequencyBreakdown`:
```python
group_by: str | GroupBy | CohortBreakdown | FrequencyBreakdown
         | list[str | GroupBy | CohortBreakdown | FrequencyBreakdown]
         | None = None
```

The `where` parameter type union expands to include `FrequencyFilter`:
```python
where: Filter | FrequencyFilter | list[Filter | FrequencyFilter] | None = None
```

### Workspace.query_funnel() / Workspace.build_funnel_params()

```python
def query_funnel(
    self,
    steps: list[str | FunnelStep],
    *,
    # ... all existing params unchanged ...
    reentry_mode: FunnelReentryMode | None = None,     # NEW (Phase A)
    time_comparison: TimeComparison | None = None,     # NEW (Phase B)
    data_group_id: int | None = None,                  # NEW (Phase C)
) -> FunnelQueryResult
```

### Workspace.query_retention() / Workspace.build_retention_params()

```python
def query_retention(
    self,
    born_event: str | RetentionEvent,
    return_event: str | RetentionEvent,
    *,
    # ... all existing params unchanged ...
    unbounded_mode: RetentionUnboundedMode | None = None,  # NEW (Phase A)
    retention_cumulative: bool = False,                     # NEW (Phase A)
    time_comparison: TimeComparison | None = None,          # NEW (Phase B)
    data_group_id: int | None = None,                       # NEW (Phase C)
) -> RetentionQueryResult
```

Note: `query_retention()` already has no `retention_cumulative` parameter, so this is purely additive. The insights `query()` has `cumulative: bool = False` for analysis type — `retention_cumulative` controls `retentionCumulative` in measurement, which is semantically different. The distinct name avoids confusion.

### Workspace.query_flow() / Workspace.build_flow_params()

```python
def query_flow(
    self,
    event: str | FlowStep | Sequence[str | FlowStep],
    *,
    # ... all existing params unchanged ...
    exclusions: list[str] | None = None,               # NEW (Phase C)
    segments: GroupBy | list[GroupBy] | None = None,    # NEW (Phase C)
    data_group_id: int | None = None,                  # NEW (Phase C)
) -> FlowQueryResult
```

The `where` parameter expands to accept property `Filter` objects (not just cohort filters):
```python
where: Filter | list[Filter] | None = None
# Currently: only Filter.in_cohort() / Filter.not_in_cohort() accepted
# After: also accepts property filters (Filter.equals, Filter.greater_than, etc.)
```

---

## Modified Type Signatures

### Metric

```python
@dataclass(frozen=True)
class Metric:
    event: str
    math: MathType = "total"
    property: str | CustomPropertyRef | InlineCustomProperty | None = None
    per_user: PerUserAggregation | None = None
    percentile_value: int | float | None = None
    filters: list[Filter] | None = None
    filters_combinator: FiltersCombinator = "all"
    segment_method: SegmentMethod | None = None          # NEW (Phase A)
```

### MathType (expanded)

```python
MathType = Literal[
    # Existing 15 values...
    "total", "unique", "dau", "wau", "mau",
    "average", "median", "min", "max",
    "p25", "p75", "p90", "p99",
    "percentile", "histogram",
    # NEW 7 values (Phase A)
    "cumulative_unique", "sessions",
    "unique_values", "most_frequent", "first_value",
    "multi_attribution", "numeric_summary",
]
```

### RetentionMathType (expanded)

```python
RetentionMathType = Literal[
    "retention_rate", "unique",
    "total", "average",              # NEW (Phase A)
]
```

### FunnelMathType (expanded)

```python
FunnelMathType = Literal[
    # Existing 13 values...
    "histogram",                      # NEW (Phase A)
]
```

### Filter (new factory methods)

```python
class Filter:
    # ... all existing methods unchanged ...

    # NEW (Phase A)
    @classmethod
    def not_between(cls, property: str, min_val: int | float, max_val: int | float,
                    *, resource_type: Literal["events", "people"] = "events") -> Filter

    @classmethod
    def starts_with(cls, property: str, prefix: str,
                    *, resource_type: Literal["events", "people"] = "events") -> Filter

    @classmethod
    def ends_with(cls, property: str, suffix: str,
                  *, resource_type: Literal["events", "people"] = "events") -> Filter

    @classmethod
    def date_not_between(cls, property: str, from_date: str, to_date: str,
                         *, resource_type: Literal["events", "people"] = "events") -> Filter

    @classmethod
    def in_the_next(cls, property: str, quantity: int, date_unit: FilterDateUnit,
                    *, resource_type: Literal["events", "people"] = "events") -> Filter

    @classmethod
    def at_least(cls, property: str, value: int | float,
                 *, resource_type: Literal["events", "people"] = "events") -> Filter

    @classmethod
    def at_most(cls, property: str, value: int | float,
                *, resource_type: Literal["events", "people"] = "events") -> Filter
```

### CohortCriteria.did_event() (expanded)

```python
@classmethod
def did_event(
    cls,
    event: str,
    *,
    at_least: int | None = None,
    at_most: int | None = None,
    exactly: int | None = None,
    # ... all existing params unchanged ...
    aggregation: CohortAggregationType | None = None,      # NEW (Phase B)
    aggregation_property: str | None = None,               # NEW (Phase B)
) -> CohortCriteria
```

### FlowStep (expanded)

```python
@dataclass(frozen=True)
class FlowStep:
    event: str
    forward: int | None = None
    reverse: int | None = None
    label: str | None = None
    filters: list[Filter] | None = None
    filters_combinator: FiltersCombinator = "all"
    session_event: FlowSessionEvent | None = None         # NEW (Phase C)
```

---

## Backward Compatibility Guarantees

1. All new parameters default to `None` or `False` — existing calls produce identical output
2. No existing parameter types are narrowed — all existing valid inputs remain valid
3. No existing method is removed or renamed
4. No existing return type changes
5. Existing tests pass without modification
6. All new public methods, fields, and classes include docstrings per constitution Principle I
5. Existing tests pass without modification
