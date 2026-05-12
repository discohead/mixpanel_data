# Quickstart: Cohort Behaviors

## Filter by Cohort

```python
from mixpanel_data import Workspace, Filter

ws = Workspace()

# Restrict insights to Power Users
result = ws.query("Purchase", where=Filter.in_cohort(123, "Power Users"))

# Exclude bots from funnel
result = ws.query_funnel(
    ["Signup", "Purchase"],
    where=Filter.not_in_cohort(789, "Bots"),
)

# Combine cohort and property filters
result = ws.query(
    "Purchase",
    where=[Filter.in_cohort(123), Filter.equals("platform", "iOS")],
)

# Inline cohort definition (no saving required)
from mixpanel_data import CohortCriteria, CohortDefinition

buyers = CohortDefinition(
    CohortCriteria.did_event("Purchase", at_least=3, within_days=30)
)
result = ws.query("Login", where=Filter.in_cohort(buyers, name="Frequent Buyers"))
```

## Break Down by Cohort

```python
from mixpanel_data import CohortBreakdown, GroupBy

# Segment by cohort membership
result = ws.query("Purchase", group_by=CohortBreakdown(123, "Power Users"))

# Mix cohort and property breakdowns
result = ws.query(
    "Purchase",
    group_by=[CohortBreakdown(123, "Power Users"), GroupBy("platform")],
)

# Only show "in cohort" segment (no "Not In" segment)
result = ws.query(
    "Purchase",
    group_by=CohortBreakdown(123, "Power Users", include_negated=False),
)
```

## Track Cohort Size Over Time

```python
from mixpanel_data import CohortMetric, Metric, Formula

# Cohort growth over 90 days
result = ws.query(CohortMetric(123, "Power Users"), last=90, unit="week")

# Compare two cohorts
result = ws.query([
    CohortMetric(123, "Power Users"),
    CohortMetric(456, "Enterprise Users"),
])

# Mix with event metrics and formulas
result = ws.query(
    [
        Metric("Login", math="unique"),
        CohortMetric(123, "Power Users"),
    ],
    formula="(B / A) * 100",
    formula_label="Power User %",
)
```

## Inline Cohort Definitions Everywhere

```python
from mixpanel_data import CohortCriteria, CohortDefinition

# Define once, use anywhere
premium_active = CohortDefinition.all_of(
    CohortCriteria.has_property("plan", "premium"),
    CohortCriteria.did_event("Login", at_least=5, within_days=30),
)

# As a filter
result = ws.query("Purchase", where=Filter.in_cohort(premium_active, name="Premium Active"))

# As a breakdown
result = ws.query("Purchase", group_by=CohortBreakdown(premium_active, name="Premium Active"))

# As a metric
result = ws.query(CohortMetric(premium_active, name="Premium Active"), last=90)

# Save it for reuse via CRUD
ws.create_cohort(CreateCohortParams(name="Premium Active", definition=premium_active.to_dict()))
```
