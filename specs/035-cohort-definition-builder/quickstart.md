# Quickstart: Cohort Definition Builder

## Basic Usage

```python
from mixpanel_data import CohortCriteria, CohortDefinition

# Simple behavioral cohort: users who purchased 3+ times in 30 days
cohort = CohortDefinition(
    CohortCriteria.did_event("Purchase", at_least=3, within_days=30)
)
print(cohort.to_dict())
# {"selector": {"operator": "and", "children": [...]}, "behaviors": {"bhvr_0": {...}}}
```

## Combining Criteria (AND)

```python
# Premium users who purchased 3+ times in 30 days
cohort = CohortDefinition.all_of(
    CohortCriteria.has_property("plan", "premium"),
    CohortCriteria.did_event("Purchase", at_least=3, within_days=30),
)
```

## Combining Criteria (OR)

```python
# Users who signed up recently OR are in the Power Users cohort
cohort = CohortDefinition.any_of(
    CohortCriteria.did_event("Signup", at_least=1, within_days=7),
    CohortCriteria.in_cohort(456),
)
```

## Nested Boolean Logic

```python
# (Premium AND active) OR Enterprise cohort
cohort = CohortDefinition.any_of(
    CohortDefinition.all_of(
        CohortCriteria.has_property("plan", "premium"),
        CohortCriteria.did_event("Login", at_least=5, within_days=30),
    ),
    CohortCriteria.in_cohort(789),  # Enterprise cohort
)
```

## With Event Property Filters

```python
from mixpanel_data import Filter

# Users who made high-value purchases
cohort = CohortDefinition(
    CohortCriteria.did_event(
        "Purchase",
        at_least=1,
        within_days=90,
        where=Filter.greater_than("amount", 100),
    )
)
```

## Inactive Users

```python
# Users who haven't logged in for 30 days
cohort = CohortDefinition(
    CohortCriteria.did_not_do_event("Login", within_days=30)
)
```

## Absolute Date Ranges

```python
# Users who purchased in Q1 2024
cohort = CohortDefinition(
    CohortCriteria.did_event(
        "Purchase",
        at_least=1,
        from_date="2024-01-01",
        to_date="2024-03-31",
    )
)
```

## Creating a Saved Cohort

```python
from mixpanel_data import Workspace, CreateCohortParams

ws = Workspace()

cohort_def = CohortDefinition.all_of(
    CohortCriteria.has_property("plan", "premium"),
    CohortCriteria.did_event("Purchase", at_least=3, within_days=30),
)

ws.create_cohort(CreateCohortParams(
    name="Premium Purchasers",
    definition=cohort_def.to_dict(),
))
```

## Inspecting the Output

```python
import json

cohort = CohortDefinition(
    CohortCriteria.did_event("Purchase", at_least=1, within_days=30)
)
print(json.dumps(cohort.to_dict(), indent=2))
```
