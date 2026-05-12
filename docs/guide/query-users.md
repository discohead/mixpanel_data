# User Profile Queries

Query user profiles from Mixpanel's Engage API — filter by properties, sort, select fields, count matching profiles, and fetch large result sets with parallel pagination. Uses the same `Filter` vocabulary as all other query engines.

!!! tip "Recommended"
    `Workspace.query_user()` is the 5th engine in the unified query system. It answers **identity** questions ("who are these users?") that complement the behavioral questions answered by insights, funnels, retention, and flows.

## When to Use `query_user()`

Use `query_user()` when you need to work with **user profiles** rather than events:

| Use Case | Example |
|----------|---------|
| Filter profiles by property | `query_user(mode="profiles", where=Filter.equals("plan", "premium"))` |
| Count matching profiles | `query_user(where=Filter.is_set("$email"))` |
| Get top users by a metric | `query_user(mode="profiles", sort_by="ltv", sort_order="descending", limit=50)` |
| Look up specific users | `query_user(mode="profiles", distinct_id="user_abc123")` |
| Profile a behavioral cohort | `query_user(mode="profiles", cohort=CohortDefinition.all_of(...))` |
| Export profiles at scale | `query_user(mode="profiles", properties=[...], limit=5000, parallel=True)` |
| Cross-engine profiling | Insights identifies a segment, `query_user()` profiles those users |

Use `stream_profiles()` when you need to iterate over raw profile dicts without structured filtering or DataFrame output.

## Getting Started

```python
import mixpanel_headless as mp
from mixpanel_headless import Filter

ws = mp.Workspace()

# Quick count — how many profiles exist? (default: mode="aggregate")
result = ws.query_user()
print(f"Total profiles: {result.value}")

# Quick peek — one sample profile
result = ws.query_user(mode="profiles")
print(result.df)

# Filter and select properties
result = ws.query_user(
    mode="profiles",
    where=Filter.equals("plan", "premium"),
    properties=["$email", "$name", "ltv"],
    sort_by="ltv",
    sort_order="descending",
    limit=50,
)
print(result.df)  # distinct_id | last_seen | email | name | ltv
```

## Aggregate Mode

Aggregate mode is the default (`mode="aggregate"`). Compute statistics across matching profiles without fetching individual records:

```python
# Count users with email (aggregate is the default mode)
count = ws.query_user(where=Filter.is_set("$email"))
print(f"Users with email: {count.value}")

# Total users (all)
total = ws.query_user()
print(f"Total profiles: {total.value}")

# Extremes (min/max) of a numeric property
result = ws.query_user(
    aggregate="extremes",
    aggregate_property="ltv",
)
print(result.aggregate_data)  # {"max": 9500, "min": 0, ...}

# Percentile
result = ws.query_user(
    aggregate="percentile",
    aggregate_property="ltv",
    percentile=90,
)
print(result.aggregate_data)  # {"percentile": 90, "result": 4500}

# Numeric summary (count, mean, variance, sum_of_squares)
result = ws.query_user(
    aggregate="numeric_summary",
    aggregate_property="ltv",
)
print(result.aggregate_data)  # {"count": 1532, "mean": 245.6, ...}

# Segmented count by cohort IDs
result = ws.query_user(
    segment_by=[12345, 67890],
)
print(result.df)  # columns: segment, value
```

## Behavioral Filtering

Filter by behavioral criteria using the same `CohortDefinition` builders available across all engines:

```python
from mixpanel_headless import CohortDefinition, CohortCriteria

# Users who purchased 3+ times in 30 days
result = ws.query_user(
    mode="profiles",
    cohort=CohortDefinition.all_of(
        CohortCriteria.did_event("Purchase", at_least=3, within_days=30),
    ),
    properties=["$email", "plan", "ltv"],
    limit=200,
)
print(f"Power buyers: {len(result.profiles)}")

# Filter by saved cohort ID
result = ws.query_user(mode="profiles", cohort=12345, limit=100)
```

## Parallel Fetching

For large result sets, enable concurrent page retrieval:

```python
result = ws.query_user(
    mode="profiles",
    where=Filter.is_set("$email"),
    properties=["$email", "plan", "ltv"],
    limit=5000,
    parallel=True,
    workers=5,
)
print(f"Fetched {len(result.profiles)} profiles")
print(f"Pages: {result.meta['pages_fetched']}, Workers: {result.meta['workers']}")
```

## Cross-Engine Composition

The real power of `query_user()` is combining it with behavioral engines. Identify interesting behavior with event engines, then profile those users:

```python
# Step 1: Which plan drives the most DAU?
dau = ws.query("Login", math="dau", group_by="plan", last=30)
top_plan = dau.df.sort_values("count", ascending=False).iloc[0]["event"]

# Step 2: Profile users from that plan
users = ws.query_user(
    mode="profiles",
    where=Filter.equals("plan", top_plan),
    properties=["$email", "company", "ltv"],
    sort_by="ltv",
    sort_order="descending",
    limit=100,
)
print(f"Plan '{top_plan}' has {len(users.profiles)} top users")
print(users.df.describe())
```

## UserQueryResult

All results are returned as `UserQueryResult`, a frozen dataclass with:

| Property | Type | Description |
|----------|------|-------------|
| `.df` | `pd.DataFrame` | Lazy cached DataFrame. Profiles mode: `distinct_id`, `last_seen`, then alphabetical properties (`$` prefix stripped). Aggregate mode: `metric`/`value` columns. |
| `.total` | `int` | Number of profiles returned (`len(profiles)`). Use `mode='aggregate', aggregate='count'` for full population count. |
| `.profiles` | `list[dict]` | Normalized profile dicts |
| `.distinct_ids` | `list[str]` | List of distinct IDs from profiles |
| `.value` | `int \| float \| None` | Scalar aggregate result (aggregate mode only) |
| `.params` | `dict` | Engage API params used (for debugging) |
| `.meta` | `dict` | Execution metadata (session_id, pages_fetched, parallel, workers) |
| `.to_dict()` | `dict` | JSON-serializable output |

## Previewing Parameters

Inspect the generated Engage API params without executing:

```python
params = ws.build_user_params(
    where=Filter.equals("plan", "premium"),
    properties=["$email", "ltv"],
    sort_by="ltv",
)
import json
print(json.dumps(params, indent=2))
```

## What's Next

- [Unified Query System](unified-query-system.md) — how all five engines work together
- [Insights Queries](query.md) — event-level analytics
- [Funnel Queries](query-funnels.md) — conversion analysis
- [Retention Queries](query-retention.md) — cohort retention
- [Flow Queries](query-flows.md) — path analysis
- [API Reference](../api/workspace.md) — full method signatures
