# Data Model: Cohort Definition Builder

**Date**: 2026-04-07  
**Spec**: [spec.md](spec.md) | **Plan**: [plan.md](plan.md)

## Entities

### CohortCriteria

A single atomic condition for cohort membership. Frozen dataclass constructed exclusively via class methods.

| Field | Type | Description |
|-------|------|-------------|
| `_selector_node` | `dict[str, Any]` | Expression tree leaf node (behavioral, property, or cohort reference) |
| `_behavior_key` | `str \| None` | Placeholder behavior key (e.g., `"bhvr_0"`). `None` for non-behavioral criteria. |
| `_behavior` | `dict[str, Any] \| None` | Behavior dict entry (event selector + window/dates). `None` for non-behavioral criteria. |

**Construction Methods**:

| Method | Produces Behavior? | Selector `property` | Description |
|--------|-------------------|---------------------|-------------|
| `did_event()` | Yes | `"behaviors"` | Event frequency within time window |
| `did_not_do_event()` | Yes | `"behaviors"` | Shorthand for `did_event(exactly=0)` |
| `has_property()` | No | `"user"` | User profile property match |
| `property_is_set()` | No | `"user"` | Property existence check |
| `property_is_not_set()` | No | `"user"` | Property non-existence check |
| `in_cohort()` | No | `"cohort"` | Cohort membership (inclusion) |
| `not_in_cohort()` | No | `"cohort"` | Cohort membership (exclusion) |

### CohortDefinition

A composed set of criteria combined with AND/OR logic. Frozen dataclass.

| Field | Type | Description |
|-------|------|-------------|
| `_criteria` | `tuple[CohortCriteria \| CohortDefinition, ...]` | One or more criteria or nested definitions |
| `_operator` | `Literal["and", "or"]` | Boolean combinator (default: `"and"`) |

**Methods**:

| Method | Type | Description |
|--------|------|-------------|
| `__init__(*criteria)` | Constructor | AND-combined criteria |
| `all_of(*criteria)` | Classmethod | Explicit AND combination |
| `any_of(*criteria)` | Classmethod | Explicit OR combination |
| `to_dict()` | Instance | Serialize to `{"selector": {...}, "behaviors": {...}}` |

## Serialization Formats

### Selector Node Variants

**Behavioral** (references behavior dict entry):
```json
{
  "property": "behaviors",
  "value": "bhvr_0",
  "operator": ">=",
  "operand": 3
}
```

**Property** (user profile property):
```json
{
  "property": "user",
  "value": "plan",
  "operator": "==",
  "operand": "premium",
  "type": "string"
}
```

**Cohort reference**:
```json
{
  "property": "cohort",
  "value": 456,
  "operator": "in"
}
```

**Boolean combinator** (AND/OR wrapper):
```json
{
  "operator": "and",
  "children": [/* selector nodes */]
}
```

### Behavior Entry

```json
{
  "bhvr_0": {
    "count": {
      "event_selector": {
        "event": "Purchase",
        "selector": null
      },
      "type": "absolute"
    },
    "window": {"unit": "day", "value": 30}
  }
}
```

With event property filters:
```json
{
  "bhvr_0": {
    "count": {
      "event_selector": {
        "event": "Purchase",
        "selector": {
          "operator": "and",
          "children": [
            {"property": "event", "value": "amount", "operator": ">", "operand": 50, "type": "number"}
          ]
        }
      },
      "type": "absolute"
    },
    "window": {"unit": "day", "value": 30}
  }
}
```

With absolute date range (instead of rolling window):
```json
{
  "bhvr_0": {
    "count": {
      "event_selector": {
        "event": "Purchase",
        "selector": null
      },
      "type": "absolute"
    },
    "from_date": "2024-01-01",
    "to_date": "2024-03-31"
  }
}
```

## Validation Rules

| Code | When | Rule | Error Message |
|------|------|------|---------------|
| CD1 | `did_event()` | Exactly one frequency param required | `exactly one of at_least, at_most, exactly must be set` |
| CD2 | `did_event()` | Frequency param must be non-negative | `frequency value must be >= 0` |
| CD3 | `did_event()` | Exactly one time constraint required | `exactly one time constraint required (within_days/weeks/months or from_date+to_date)` |
| CD4 | `did_event()` | Event name must be non-empty | `event name must be non-empty` |
| CD5 | `did_event()` | `from_date` requires `to_date` | `from_date requires to_date` |
| CD6 | `did_event()` | Dates must be YYYY-MM-DD | `dates must be YYYY-MM-DD format` |
| CD7 | `has_property()` | Property name must be non-empty | `property name must be non-empty` |
| CD8 | `in_cohort()` / `not_in_cohort()` | Cohort ID must be positive integer | `cohort_id must be a positive integer` |
| CD9 | `CohortDefinition` | At least one criterion required | `CohortDefinition requires at least one criterion` |
| CD10 | `to_dict()` | All behavior keys must be unique | Internal invariant (enforced by re-indexing) |

## Relationships

```text
CohortDefinition 1──* CohortCriteria | CohortDefinition (recursive)
                                         │
CohortCriteria ──0..1── Behavior Entry   (only behavioral criteria)
                                         │
CohortCriteria ──1── Selector Node       (always present)
                                         │
Behavior Entry ──0..1── Filter(s)        (via did_event where= parameter)
```

## Integration Points

- **CreateCohortParams**: `CohortDefinition.to_dict()` → `CreateCohortParams(definition=...)` → `model_dump()` flattens `selector` and `behaviors` to top level
- **Filter**: `CohortCriteria.did_event(where=Filter.equals(...))` reads Filter's internal fields to build event selector expressions
- **__init__.py**: `CohortCriteria` and `CohortDefinition` added to public exports
