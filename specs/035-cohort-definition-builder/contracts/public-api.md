# Public API Contract: Cohort Definition Builder

**Date**: 2026-04-07  
**Module**: `mixpanel_data`

## Exports

The following types are added to `mixpanel_data.__init__` public exports:

- `CohortCriteria`
- `CohortDefinition`

## CohortCriteria

Frozen dataclass. No public fields — constructed exclusively via class methods.

### Class Methods

#### `did_event(event, *, at_least, at_most, exactly, within_days, within_weeks, within_months, from_date, to_date, where) -> CohortCriteria`

| Parameter | Type | Required | Default |
|-----------|------|----------|---------|
| `event` | `str` | Yes | — |
| `at_least` | `int \| None` | No | `None` |
| `at_most` | `int \| None` | No | `None` |
| `exactly` | `int \| None` | No | `None` |
| `within_days` | `int \| None` | No | `None` |
| `within_weeks` | `int \| None` | No | `None` |
| `within_months` | `int \| None` | No | `None` |
| `from_date` | `str \| None` | No | `None` |
| `to_date` | `str \| None` | No | `None` |
| `where` | `Filter \| list[Filter] \| None` | No | `None` |

**Constraints**: Exactly one of `at_least`/`at_most`/`exactly` required. Exactly one time constraint required (`within_*` or `from_date`+`to_date`). `from_date` requires `to_date`. Dates must be YYYY-MM-DD.

**Raises**: `ValueError` on constraint violations (CD1-CD6).

#### `did_not_do_event(event, *, within_days, within_weeks, within_months, from_date, to_date) -> CohortCriteria`

Shorthand for `did_event(event, exactly=0, ...)`.

#### `has_property(property, value, *, operator, property_type) -> CohortCriteria`

| Parameter | Type | Required | Default |
|-----------|------|----------|---------|
| `property` | `str` | Yes | — |
| `value` | `str \| int \| float \| bool \| list[str]` | Yes | — |
| `operator` | `Literal["equals", "not_equals", "contains", "not_contains", "greater_than", "less_than", "is_set", "is_not_set"]` | No | `"equals"` |
| `property_type` | `Literal["string", "number", "boolean", "datetime", "list"]` | No | `"string"` |

**Raises**: `ValueError` if `property` is empty (CD7).

#### `property_is_set(property) -> CohortCriteria`

Shorthand for `has_property(property, "", operator="is_set")`.

#### `property_is_not_set(property) -> CohortCriteria`

Shorthand for `has_property(property, "", operator="is_not_set")`.

#### `in_cohort(cohort_id) -> CohortCriteria`

| Parameter | Type | Required |
|-----------|------|----------|
| `cohort_id` | `int` | Yes |

**Raises**: `ValueError` if `cohort_id` is not a positive integer (CD8).

#### `not_in_cohort(cohort_id) -> CohortCriteria`

Same as `in_cohort` but produces `"not in"` selector.

## CohortDefinition

Frozen dataclass.

### Constructor

#### `__init__(*criteria: CohortCriteria) -> None`

Combines one or more criteria with AND logic. Raises `ValueError` if no criteria provided (CD9).

### Class Methods

#### `all_of(*criteria: CohortCriteria | CohortDefinition) -> CohortDefinition`

Combines criteria/definitions with AND logic. Raises `ValueError` if no criteria provided.

#### `any_of(*criteria: CohortCriteria | CohortDefinition) -> CohortDefinition`

Combines criteria/definitions with OR logic. Raises `ValueError` if no criteria provided.

### Instance Methods

#### `to_dict() -> dict[str, Any]`

Returns `{"selector": {...}, "behaviors": {...}}` dict. Behavior keys are globally re-indexed to ensure uniqueness.

## Compatibility

`CohortDefinition.to_dict()` output is directly compatible with:

```python
CreateCohortParams(name="...", definition=cohort_def.to_dict())
```

The `_DefinitionFlatteningModel.model_dump()` flattens `selector` and `behaviors` to top-level keys in the API payload.
