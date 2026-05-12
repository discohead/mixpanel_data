# Quickstart: Unified Query Engine Completeness

**Date**: 2026-04-14
**Feature**: 040-query-engine-completeness

## Phase A: Type Expansions and Core Parameters

### Expanded Math Types (Insights)

```python
from mixpanel_data import Workspace, Metric

ws = Workspace()

# Cumulative unique users over time
result = ws.query("Signup", math="cumulative_unique", last=30)

# Count sessions (not events or users)
result = ws.query("Login", math="sessions", last=30)

# Most frequent value of a property
result = ws.query("Purchase", math="most_frequent", math_property="category", last=30)

# Numeric summary (count, mean, variance, sum_of_squares)
result = ws.query("Purchase", math="numeric_summary", math_property="amount", last=30)

# Metric object with new math types
m = Metric("Purchase", math="unique_values", property="product_id")
result = ws.query(m, last=30)
```

### Expanded Math Types (Retention and Funnels)

```python
# Retention with total event count per bucket
result = ws.query_retention("Signup", "Purchase", math="total", last=90)

# Retention with average property value per bucket
result = ws.query_retention("Signup", "Purchase", math="average", last=90)

# Funnel with histogram math
result = ws.query_funnel(["View", "Cart", "Purchase"], math="histogram", math_property="amount")
```

### Segment Method

```python
# First-touch attribution (count only first qualifying event per user)
m = Metric("Purchase", segment_method="first")
result = ws.query_funnel(["View", "Purchase"], math="total")

# All-touch attribution (count all qualifying events, default)
m = Metric("Purchase", segment_method="all")
```

### Funnel Reentry Mode

```python
# Aggressive reentry — each re-entry generates additional conversion
result = ws.query_funnel(
    ["View Product", "Add to Cart", "Purchase"],
    reentry_mode="aggressive",
    last=30,
)

# Basic reentry — users can re-enter at steps after the first
result = ws.query_funnel(steps, reentry_mode="basic")
```

### Retention Unbounded and Cumulative Modes

```python
# Carry forward — count returning users in all intermediate buckets
result = ws.query_retention(
    "Signup", "Login",
    unbounded_mode="carry_forward",
    retention_unit="week",
    last=90,
)

# Cumulative retention view
result = ws.query_retention("Signup", "Login", retention_cumulative=True, last=90)

# Combined: cumulative with carry_forward
result = ws.query_retention(
    "Signup", "Login",
    unbounded_mode="carry_forward",
    retention_cumulative=True,
    last=90,
)
```

### New Filter Methods

```python
from mixpanel_data import Filter

# Numeric range negation
f = Filter.not_between("age", 18, 25)

# String prefix/suffix matching
f = Filter.starts_with("email", "admin")
f = Filter.ends_with("domain", ".edu")

# Date range negation
f = Filter.date_not_between("created", "2025-01-01", "2025-06-30")

# Future relative date
f = Filter.in_the_next("trial_end", 7, "day")

# Inclusive numeric bounds
f = Filter.at_least("purchase_count", 5)
f = Filter.at_most("age", 65)
```

## Phase B: New Feature Types

### Time Comparison

```python
from mixpanel_data import TimeComparison

# Compare last 30 days vs previous month
result = ws.query(
    "Signup",
    last=30,
    time_comparison=TimeComparison.relative("month"),
)

# Compare against a specific start date
result = ws.query(
    "Signup",
    from_date="2026-03-01",
    to_date="2026-03-31",
    time_comparison=TimeComparison.absolute_start("2026-02-01"),
)

# Works with funnels and retention too
result = ws.query_funnel(
    ["View", "Purchase"],
    last=30,
    time_comparison=TimeComparison.relative("week"),
)
```

### Frequency Analysis

```python
from mixpanel_data import FrequencyBreakdown, FrequencyFilter

# Break down by how many times users purchased
result = ws.query(
    "Signup",
    group_by=FrequencyBreakdown("Purchase", bucket_size=1, bucket_min=0, bucket_max=10),
    last=30,
)

# Filter to users who logged in at least 5 times
result = ws.query(
    "Purchase",
    where=FrequencyFilter("Login", operator="is at least", value=5),
    last=30,
)

# Frequency filter with time window
result = ws.query(
    "Purchase",
    where=FrequencyFilter(
        "Login",
        operator="is at least",
        value=3,
        date_range_value=7,
        date_range_unit="day",
    ),
    last=30,
)
```

### Enhanced Behavioral Cohorts

```python
from mixpanel_data import CohortCriteria, CohortDefinition

# Users whose average purchase value > $50
criteria = CohortCriteria.did_event(
    "Purchase",
    aggregation="average",
    aggregation_property="amount",
    at_least=50,
    within_days=30,
)

cohort = CohortDefinition(criteria)
ws.create_cohort(name="High-Value Buyers", definition=cohort)

# Users with 3+ unique product categories
criteria = CohortCriteria.did_event(
    "Purchase",
    aggregation="unique",
    aggregation_property="category",
    at_least=3,
    within_days=30,
)
```

## Phase C: Completeness

### Group Analytics Scoping

```python
# Scope query to a specific data group (e.g., companies)
result = ws.query("Feature Used", math="unique", data_group_id=5, last=30)

# Works across all query types
result = ws.query_funnel(["Trial", "Paid"], data_group_id=5, last=30)
result = ws.query_retention("Signup", "Login", data_group_id=5, last=90)
result = ws.query_flow("Login", data_group_id=5, last=30)
```

### Advanced Flow Features

```python
from mixpanel_data import FlowStep, Filter

# Session start/end as flow anchors
step = FlowStep(event="$session_start", session_event="start", forward=5)
result = ws.query_flow(step, last=30)

# Global property filter on flows
result = ws.query_flow(
    "Login",
    where=Filter.equals("country", "US"),
    last=30,
)
```
