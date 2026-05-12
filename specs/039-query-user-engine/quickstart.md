# Quickstart: User Profile Query Engine

**Feature**: 039-query-user-engine

---

## Basic Profile Query

```python
import mixpanel_data as mp

ws = mp.Workspace()

# Default mode is aggregate — get a count
result = ws.query_user(where=mp.Filter.equals("plan", "premium"))
print(f"{result.value} premium users")  # e.g., 45000

# Fetch 1 sample profile with mode="profiles"
result = ws.query_user(mode="profiles", where=mp.Filter.equals("plan", "premium"))
print(result.df)  # 1-row DataFrame
```

## Filter and Select Properties

```python
# Top 50 users by LTV with selected properties
result = ws.query_user(
    mode="profiles",
    where=[
        mp.Filter.equals("plan", "premium"),
        mp.Filter.greater_than("ltv", 100),
    ],
    properties=["$email", "$name", "plan", "ltv", "company"],
    sort_by="ltv",
    sort_order="descending",
    limit=50,
)
print(result.df)
# distinct_id | last_seen | email | name | plan | ltv | company
```

## Aggregate Statistics

Aggregate is the default mode, so `mode="aggregate"` can be omitted:

```python
# Count premium users
result = ws.query_user(
    where=mp.Filter.equals("plan", "premium"),
)
print(f"Premium users: {result.value}")  # e.g., 45000

# Numeric summary (count, mean, variance) of LTV
result = ws.query_user(
    aggregate="numeric_summary",
    aggregate_property="ltv",
)
print(result.aggregate_data)  # {"count": 1532, "mean": 245.6, ...}

# LTV by cohort segment
result = ws.query_user(
    aggregate="numeric_summary",
    aggregate_property="ltv",
    segment_by=[123, 456],
)
print(result.df)
#   segment    | value
#   cohort_123 | 145.0
#   cohort_456 | 320.5
```

## Behavioral Filtering

```python
from mixpanel_data import CohortDefinition, CohortCriteria

# Users who purchased 3+ times in last 30 days
result = ws.query_user(
    mode="profiles",
    cohort=CohortDefinition.all_of(
        CohortCriteria.did_event("Purchase", at_least=3, within_days=30),
    ),
    properties=["$email", "plan", "ltv"],
    sort_by="ltv",
    sort_order="descending",
    limit=200,
)
print(f"Active buyers: {result.total}")

# Combined behavioral + property criteria
power_users = ws.query_user(
    mode="profiles",
    cohort=CohortDefinition.all_of(
        CohortCriteria.did_event("Purchase", at_least=3, within_days=30),
        CohortCriteria.did_event("Login", at_least=5, within_days=7),
        CohortCriteria.has_property("plan", "premium"),
    ),
    properties=["$email", "ltv", "company"],
)
```

## Parallel Fetching (Large Result Sets)

```python
# Fetch all premium users with parallel fetching (up to 5x faster)
all_premium = ws.query_user(
    mode="profiles",
    where=mp.Filter.equals("plan", "premium"),
    properties=["$email", "ltv", "signup_date"],
    limit=None,  # Fetch all
    parallel=True,
    workers=5,
)
print(f"Fetched {len(all_premium.profiles)} profiles "
      f"in {all_premium.meta['duration_seconds']:.1f}s")
```

## Specific Users and Search

```python
# Look up a single user
result = ws.query_user(mode="profiles", distinct_id="user_abc123")

# Look up multiple users
result = ws.query_user(mode="profiles", distinct_ids=["user_1", "user_2", "user_3"])

# Full-text search
result = ws.query_user(mode="profiles", search="alice@example.com", limit=10)
```

## Group Profiles

```python
# Query company profiles instead of users
companies = ws.query_user(
    mode="profiles",
    group_id="companies",
    where=mp.Filter.greater_than("arr", 50000),
    properties=["company_name", "arr", "employee_count"],
    sort_by="arr",
    sort_order="descending",
    limit=50,
)
```

## Cross-Engine Composition

```python
# Step 1: Which plan drives the most DAU?
dau = ws.query("Login", math="dau", group_by="plan", last=30)
top_plan = dau.df.sort_values("count", ascending=False).iloc[0]["event"]

# Step 2: Get profiles from top plan
users = ws.query_user(
    mode="profiles",
    where=mp.Filter.equals("plan", top_plan),
    properties=["$email", "company", "ltv"],
    sort_by="ltv",
    sort_order="descending",
    limit=200,
)
print(f"Plan '{top_plan}' has {users.total} users")
```

## Inspect Generated Parameters

```python
# Preview engage API params without executing
params = ws.build_user_params(
    mode="profiles",
    where=mp.Filter.equals("plan", "premium"),
    properties=["$email", "ltv"],
    sort_by="ltv",
)
import json
print(json.dumps(params, indent=2))
```
