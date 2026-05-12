# Public API Contract: Cohort Behaviors

**Date**: 2026-04-06

## New Public Types

### CohortBreakdown

```python
from mixpanel_data import CohortBreakdown, CohortDefinition

# Saved cohort by ID
cb = CohortBreakdown(cohort=123, name="Power Users")
cb = CohortBreakdown(cohort=123, name="Power Users", include_negated=False)

# Inline cohort definition
cb = CohortBreakdown(cohort=cohort_def, name="Active Users")
```

**Fields**: `cohort: int | CohortDefinition`, `name: str | None = None`, `include_negated: bool = True`

### CohortMetric

```python
from mixpanel_data import CohortMetric, CohortDefinition

# Saved cohort by ID
cm = CohortMetric(cohort=123, name="Power Users")

# Inline cohort definition
cm = CohortMetric(cohort=cohort_def, name="Active Premium")
```

**Fields**: `cohort: int | CohortDefinition`, `name: str | None = None`

## Extended Methods on Filter

### Filter.in_cohort()

```python
from mixpanel_data import Filter, CohortDefinition

# Saved cohort
f = Filter.in_cohort(123, "Power Users")
f = Filter.in_cohort(123)  # name optional for saved cohorts

# Inline cohort
f = Filter.in_cohort(cohort_def, name="Frequent Buyers")
```

**Signature**: `Filter.in_cohort(cohort: int | CohortDefinition, name: str | None = None) -> Filter`

### Filter.not_in_cohort()

```python
f = Filter.not_in_cohort(789, "Bots")
f = Filter.not_in_cohort(cohort_def, name="Inactive Users")
```

**Signature**: `Filter.not_in_cohort(cohort: int | CohortDefinition, name: str | None = None) -> Filter`

## Changed Method Signatures

### Workspace.query() — `events` parameter widened

```python
# Before
def query(self, events: str | Metric | Formula | Sequence[str | Metric | Formula], ...) -> QueryResult

# After
def query(self, events: str | Metric | CohortMetric | Formula | Sequence[str | Metric | CohortMetric | Formula], ...) -> QueryResult
```

### Workspace.query() / query_funnel() / query_retention() — `group_by` parameter widened

```python
# Before
group_by: str | GroupBy | list[str | GroupBy] | None = None

# After
group_by: str | GroupBy | CohortBreakdown | list[str | GroupBy | CohortBreakdown] | None = None
```

### Workspace.query_flow() — `where` parameter added

```python
# Before
def query_flow(self, event, *, forward=3, reverse=0, ...) -> FlowQueryResult

# After
def query_flow(self, event, *, forward=3, reverse=0, ..., where: Filter | list[Filter] | None = None) -> FlowQueryResult
```

## Backward Compatibility

All changes are additive:
- New optional parameters have default `None`
- Existing parameter types are widened (union extended), not changed
- Existing calls without cohort types work identically
- No return type changes
- No removed methods or parameters

## Error Contract

All validation errors raise `ValueError` at construction time:
- Non-positive cohort ID: `"cohort must be a positive integer"` (CohortBreakdown, CohortMetric, Filter.in_cohort/not_in_cohort)
- Empty name: `"cohort name must be non-empty when provided"`
- Mixed retention breakdowns: `"query_retention does not support mixing CohortBreakdown with property GroupBy"`
- Non-cohort filter in flow `where=`: `"query_flow where= only accepts cohort filters (Filter.in_cohort/not_in_cohort)"`
