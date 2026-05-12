# The Unified Query System

Five analytics engines. One Python vocabulary. Every query validated before it hits the network.

```python
import mixpanel_headless as mp

ws = mp.Workspace()

ws.query("Login")                           # Insights
ws.query_funnel(["Signup", "Purchase"])      # Funnels
ws.query_retention("Signup", "Login")        # Retention
ws.query_flow("Purchase")                    # Flows
ws.query_user(where=Filter.is_set("$email")) # Users
```

Each method returns a typed result with a lazy `.df` property. Each method validates every parameter before making an API call. And the keyword arguments you learn for one method work in all the others.

---

## The pattern

Every query method shares the same vocabulary:

```python
# These keywords mean the same thing everywhere
result = ws.query(
    "Login",
    where=Filter.equals("country", "US"),  # filter
    group_by="platform",                    # breakdown
    last=90,                                # time range
    time_comparison="previous_period",      # compare periods
    data_group_id=42,                       # data group scope
)

result = ws.query_funnel(
    ["Signup", "Purchase"],
    where=Filter.equals("country", "US"),  # same
    group_by="platform",                    # same
    last=90,                                # same
    time_comparison="previous_period",      # same
    data_group_id=42,                       # same
)

result = ws.query_retention(
    "Signup", "Login",
    where=Filter.equals("country", "US"),  # same
    group_by="platform",                    # same
    last=90,                                # same
    time_comparison="previous_period",      # same
    data_group_id=42,                       # same
)

result = ws.query_flow(
    "Purchase",
    where=Filter.equals("country", "US"),  # property filters supported
    last=90,                                # same
    data_group_id=42,                       # same
)
```

Learn `Filter`, `GroupBy`, `where=`, `group_by=`, `last=`, `time_comparison=`, and `data_group_id=` once. Use them across engines (flows has some restrictions — see below).

---

## Strings first, objects when you need them

Every parameter that accepts a typed object also accepts a plain string. Start simple, upgrade to objects when you need more control:

```python
# Strings — simple and readable
ws.query("Login", group_by="country")

# GroupBy object — when you need numeric bucketing
ws.query(
    "Purchase",
    group_by=GroupBy(
        "revenue",
        property_type="number",
        bucket_size=50,
    ),
)
```

```python
# Strings — just event names
ws.query_funnel(["Signup", "Purchase"])

# FunnelStep objects — when you need per-step filters
ws.query_funnel([
    FunnelStep("Signup"),
    FunnelStep("Purchase", filters=[Filter.greater_than("amount", 50)]),
])
```

```python
# Strings — just born and return events
ws.query_retention("Signup", "Login")

# RetentionEvent objects — when you need per-event filters
ws.query_retention(
    RetentionEvent("Signup", filters=[Filter.equals("source", "organic")]),
    "Login",
)
```

```python
# String — just an anchor event
ws.query_flow("Purchase")

# FlowStep object — per-step direction or filters
ws.query_flow(
    FlowStep(
        "Purchase",
        forward=5,
        reverse=2,
        filters=[Filter.greater_than("amount", 50)],
    ),
)
```

Mix freely. Strings and objects can appear in the same query.

**Note:** `FlowStep.filters` accepts any `Filter` type for per-step filtering. The query-level `where=` parameter on `query_flow()` accepts both cohort filters (`Filter.in_cohort` / `Filter.not_in_cohort`) and property filters (`Filter.equals()`, `Filter.greater_than()`, etc.).

---

## Filters: typed methods, not operator strings

Every filter is a class method on `Filter`. Autocomplete shows you every option:

```python
from mixpanel_headless import Filter

# String comparisons
Filter.equals("country", "US")
Filter.equals("country", ["US", "CA", "UK"])  # multi-value
Filter.not_equals("status", "banned")
Filter.contains("email", "@company.com")

# Numeric comparisons
Filter.greater_than("amount", 100)
Filter.less_than("age", 18)
Filter.between("revenue", 50, 500)

# Existence
Filter.is_set("utm_source")
Filter.is_not_set("phone")

# Boolean
Filter.is_true("is_premium")
Filter.is_false("opted_out")

# Dates
Filter.in_the_last("created", 30, "day")
Filter.before("signup_date", "2025-01-01")

# Cohorts (see "Cohort scoping" below)
Filter.in_cohort(123, "Power Users")
Filter.not_in_cohort(456, "Bots")
```

Combine multiple filters with `where=`:

```python
# AND logic (default) — all conditions must match
result = ws.query("Purchase", where=[
    Filter.equals("country", "US"),
    Filter.greater_than("amount", 25),
    Filter.is_true("is_premium"),
])
```

Filters work identically across `query()`, `query_funnel()`, `query_retention()`, and `query_flow()`.

---

## Results: DataFrames, params, and metadata

Insights, funnel, and retention results share a common structure:

```python
result = ws.query("Login", math="dau", last=30)

result.df            # pandas DataFrame — lazy, cached
result.params        # the exact bookmark JSON sent to the API
result.from_date     # resolved start date
result.to_date       # resolved end date
result.computed_at   # when Mixpanel computed the result
result.meta          # sampling factor, cache status
```

Flow results have `computed_at`, `params`, and `meta` but not `from_date`/`to_date` — flow data is structured around nodes, edges, and trees instead.

Engine-specific results add domain-relevant properties:

```python
# Funnels
result = ws.query_funnel(["Signup", "Purchase"])
result.overall_conversion_rate   # 0.12
result.steps_data                # per-step counts and ratios

# Retention
result = ws.query_retention("Signup", "Login")
result.cohorts                   # per-cohort-date retention data
result.average                   # synthetic average

# Flows (sankey mode)
result = ws.query_flow("Purchase")
result.nodes_df                  # step | event | type | count
result.edges_df                  # source -> target with counts
result.graph                     # NetworkX DiGraph
result.top_transitions(5)        # highest-traffic edges
result.drop_off_summary()        # per-step drop-off rates

# Flows (tree mode)
result = ws.query_flow("Purchase", mode="tree")
result.trees                     # recursive FlowTreeNode objects
result.anytree                   # anytree AnyNode objects
```

---

## The five engines

### Insights — `query()`

The general-purpose analytics engine. Counts, aggregations, DAU/WAU/MAU, formulas, rolling windows.

```python
from mixpanel_headless import Metric, Formula, Filter, GroupBy

# DAU over 90 days, weekly
result = ws.query("Login", math="dau", last=90, unit="week")

# Revenue percentiles
result = ws.query("Purchase", math="p99", math_property="amount")

# Per-user average purchases
result = ws.query(
    "Purchase",
    math="total",
    per_user="average",
    math_property="amount",
)

# 7-day rolling average
result = ws.query("Signup", math="unique", rolling=7, last=60)

# Multi-event comparison
result = ws.query(["Signup", "Login", "Purchase"], math="unique")
```

#### Formulas

Compute derived metrics. Letters A-Z reference events by position:

```python
# Top-level formula parameter
result = ws.query(
    [
        Metric("Signup", math="unique"),
        Metric("Purchase", math="unique"),
    ],
    formula="(B / A) * 100",
    formula_label="Conversion Rate",
    unit="week",
)

# Or Formula objects in the event list
result = ws.query([
    Metric("Signup", math="unique"),
    Metric("Purchase", math="unique"),
    Formula("(B / A) * 100", label="Conversion Rate"),
])
```

#### The Metric class

When different events need different aggregation:

```python
result = ws.query([
    Metric("Signup", math="unique"),
    Metric("Purchase", math="total", property="revenue"),
    Metric(
        "Support Ticket",
        math="unique",
        filters=[Filter.equals("priority", "high")],
    ),
])
```

**Full reference:** [Insights Queries](query.md)

---

### Funnels — `query_funnel()`

Step-by-step conversion analysis with conversion windows, exclusions, and step ordering.

```python
from mixpanel_headless import (
    FunnelStep, Exclusion, HoldingConstant, Filter,
)

# Two-step funnel with 7-day conversion window
result = ws.query_funnel(
    ["Signup", "Purchase"],
    conversion_window=7,
)
print(f"Conversion: {result.overall_conversion_rate:.1%}")

# Per-step filters and labels
result = ws.query_funnel([
    FunnelStep("Signup"),
    FunnelStep(
        "Add to Cart",
        filters=[Filter.greater_than("item_count", 0)],
    ),
    FunnelStep("Checkout"),
    FunnelStep("Purchase", label="Completed Purchase"),
])

# Exclude events between steps
result = ws.query_funnel(
    ["Signup", "Add to Cart", "Purchase"],
    exclusions=["Logout"],  # all steps
    # Or target a specific range:
    # exclusions=[Exclusion("Refund", from_step=1, to_step=2)],
)

# Hold a property constant across all steps
result = ws.query_funnel(
    ["Signup", "Purchase"],
    # users must complete on same platform
    holding_constant="platform",
)

# Session-based conversion
result = ws.query_funnel(
    ["Browse", "Add to Cart", "Purchase"],
    conversion_window=1,
    conversion_window_unit="session",
    math="conversion_rate_session",
)

# Funnel trends over time
result = ws.query_funnel(
    ["Signup", "Purchase"],
    mode="trends",
    last=90,
    unit="week",
)
```

**Full reference:** [Funnel Queries](query-funnels.md)

---

### Retention — `query_retention()`

Cohort retention with custom buckets, alignment modes, and display options.

```python
from mixpanel_headless import RetentionEvent, Filter

# Weekly retention, last 90 days
result = ws.query_retention(
    "Signup", "Login",
    retention_unit="week",
    last=90,
)

# Average retention curve
avg = result.average
for i, rate in enumerate(avg["rates"]):
    print(f"  Week {i}: {rate:.1%}")

# Custom retention milestones
result = ws.query_retention(
    "Signup", "Login",
    retention_unit="day",
    bucket_sizes=[1, 3, 7, 14, 30, 60, 90],
    last=90,
)

# Per-event filters
result = ws.query_retention(
    RetentionEvent(
        "Signup",
        filters=[Filter.equals("source", "organic")],
    ),
    RetentionEvent(
        "Purchase",
        filters=[Filter.greater_than("amount", 0)],
    ),
    retention_unit="month",
    last=180,
)

# Retention trends over time
result = ws.query_retention(
    "Signup", "Login",
    mode="trends",
    unit="week",
    last=180,
)
```

**Full reference:** [Retention Queries](query-retention.md)

---

### Flows — `query_flow()`

Path analysis with forward/reverse tracing, three visualization modes, and graph algorithms.

```python
from mixpanel_headless import FlowStep, Filter

# What happens after Purchase?
result = ws.query_flow("Purchase", forward=5)

# What leads to Cancel Subscription?
result = ws.query_flow("Cancel Subscription", forward=0, reverse=5)

# Both directions
result = ws.query_flow("Add to Cart", forward=3, reverse=2)

# Hide noisy events, increase path variety
result = ws.query_flow(
    "Purchase",
    hidden_events=[
        "Session Start", "Page View", "Heartbeat",
    ],
    cardinality=10,
    collapse_repeated=True,
    last=90,
)
```

#### Three visualization modes

```python
# Sankey (default) — aggregated node/edge graph
result = ws.query_flow("Purchase", mode="sankey")
print(result.nodes_df)
print(result.edges_df)
g = result.graph   # NetworkX DiGraph

# Paths — top user paths as sequences
result = ws.query_flow("Purchase", mode="paths")
print(result.df)

# Tree — recursive decision tree from anchor
result = ws.query_flow("Purchase", mode="tree")
for tree in result.trees:
    print(tree.render())   # ASCII visualization
```

#### NetworkX graph

The sankey-mode graph unlocks the full NetworkX algorithm library:

```python
import networkx as nx

g = result.graph

# Shortest path from Signup to Purchase
path = nx.shortest_path(g, "Signup@0", "Purchase@3")

# Biggest bottleneck — highest betweenness centrality
betweenness = nx.betweenness_centrality(g, weight="count")
bottleneck = max(betweenness, key=betweenness.get)

# Micro-conversion between any two steps
cart_out = sum(
    d["count"]
    for _, _, d in g.out_edges("Add to Cart@2", data=True)
)
to_purchase = g.edges["Add to Cart@2", "Purchase@3"]["count"]
print(f"Cart → Purchase: {to_purchase / cart_out:.1%}")

# Dead ends — reachable but leading nowhere
dead_ends = [
    n for n in g.nodes()
    if g.out_degree(n) == 0 and g.in_degree(n) > 0
]
```

#### Tree traversal

Tree mode gives per-node conversion and drop-off counts:

```python
result = ws.query_flow("Signup", mode="tree", forward=4)

for tree in result.trees:
    # At each fork, what % takes each branch?
    for node in tree.flatten():
        if node.children:
            total = node.total_count
            print(f"\nAfter {node.event} ({total} users):")
            ranked = sorted(
                node.children,
                key=lambda c: c.total_count,
                reverse=True,
            )
            for child in ranked:
                pct = child.total_count / total * 100
                print(f"  -> {child.event}: {pct:.0f}%")

    # Best path through the product
    best = max(
        tree.all_paths(),
        key=lambda p: p[-1].converted_count,
    )
    print(" -> ".join(
        f"{n.event}({n.conversion_rate:.0%})"
        for n in best
    ))

    # Biggest single drop-off
    worst = max(
        tree.flatten(),
        key=lambda n: n.drop_off_count,
    )
    print(f"Biggest drop-off: {worst.event} "
          f"({worst.drop_off_count} users lost)")
```

Trees also convert to [anytree](https://anytree.readthedocs.io/) nodes for rendering, export, and Graphviz:

```python
from anytree import RenderTree
from anytree.exporter import UniqueDotExporter

root = result.anytree[0]
for pre, _, node in RenderTree(root):
    print(f"{pre}{node.event} ({node.total_count})")

UniqueDotExporter(root).to_picture("flow.png")
```

**Full reference:** [Flow Queries](query-flows.md)

---

### Users — `query_user()`

Search, filter, sort, and aggregate user profiles stored in Mixpanel. Default mode is `"aggregate"` — use `mode="profiles"` to fetch individual records.

```python
from mixpanel_headless import Filter

# Find premium users, sorted by lifetime value
result = ws.query_user(
    mode="profiles",
    where=Filter.equals("plan", "premium"),
    properties=["$email", "$name", "ltv"],
    sort_by="ltv",
    sort_order="descending",
    limit=50,
)
print(f"{result.total} premium users")
print(result.df)

# Count profiles matching a condition (aggregate is the default mode)
count = ws.query_user(where=Filter.is_set("$email"))
print(f"Users with email: {count.value}")
```

**Full reference:** [User Profile Queries](query-users.md)

---

## Cross-cutting capabilities

These features work across multiple engines through the same parameters.

### Recent additions

| Feature | Engines | Description |
|---|---|---|
| `time_comparison=` | Insights, Funnels, Retention | Compare the current period against a previous period |
| `data_group_id=` | Insights, Funnels, Retention, Flows | Scope queries to a specific data group |
| Property filters in `where=` | Flows | Flows now support property filters (e.g., `Filter.equals()`) in addition to cohort filters |
| `segments=` | Flows | Break down flow paths by property, cohort, or frequency |
| `exclusions=` | Flows | Hide specific events from flow paths |

### Cohort scoping

Three ways to use cohorts — all accept either a saved cohort ID or an inline `CohortDefinition`:

```python
from mixpanel_headless import (
    Filter, CohortBreakdown, CohortMetric,
    CohortCriteria, CohortDefinition,
)

# Define a cohort inline — no UI, no saving, no ID to look up
power_users = CohortDefinition(
    CohortCriteria.did_event("Purchase", at_least=3, within_days=30)
)
```

#### 1. Filter — restrict a query to a segment

```python
# Saved cohort
result = ws.query(
    "Login",
    where=Filter.in_cohort(123, "Power Users"),
)

# Inline cohort
result = ws.query(
    "Login",
    where=Filter.in_cohort(power_users, name="Power Users"),
)

# Exclude a cohort
result = ws.query(
    "Login",
    where=Filter.not_in_cohort(456, "Bots"),
)

# Works in all five engines
result = ws.query_funnel(
    ["Signup", "Purchase"],
    where=Filter.in_cohort(power_users, name="PU"),
)
result = ws.query_retention(
    "Signup", "Login",
    where=Filter.in_cohort(123, "PU"),
)
result = ws.query_flow(
    "Purchase",
    where=Filter.in_cohort(123, "PU"),
)
```

#### 2. Breakdown — compare a segment against everyone else

```python
result = ws.query(
    "Purchase",
    group_by=CohortBreakdown(123, "Power Users"),
)
# Two segments: "Power Users" and "Not In Power Users"

# Show only the cohort (no negation segment)
result = ws.query(
    "Purchase",
    group_by=CohortBreakdown(
        123, "PU", include_negated=False,
    ),
)

# Combine with property breakdowns
result = ws.query(
    "Purchase",
    group_by=[CohortBreakdown(123, "PU"), "platform"],
)
```

Works with `query()`, `query_funnel()`, and `query_retention()`.

#### 3. Metric — track cohort size over time

```python
# How many power users do we have each week?
result = ws.query(
    CohortMetric(123, "Power Users"),
    last=90,
    unit="week",
)

# What % of active users are power users?
result = ws.query(
    [
        Metric("Login", math="unique"),
        CohortMetric(123, "Power Users"),
    ],
    formula="(B / A) * 100",
    formula_label="Power User %",
)
```

Works with `query()` only.

#### Engine compatibility

| Capability | `query()` | `query_funnel()` | `query_retention()` | `query_flow()` | `query_user()` |
|---|:-:|:-:|:-:|:-:|:-:|
| **Cohort Filters** | yes | yes | yes | yes | yes |
| **Cohort Breakdowns** | yes | yes | yes | -- | -- |
| **Cohort Metrics** | yes | -- | -- | -- | -- |

---

### Custom properties

Use saved custom properties by ID or define computed properties inline at query time:

```python
from mixpanel_headless import (
    CustomPropertyRef, InlineCustomProperty,
    GroupBy, Filter, Metric,
)

# Reference a saved custom property
ref = CustomPropertyRef(42)

# Or define one inline — no UI, no saving
revenue = InlineCustomProperty.numeric(
    "A * B", A="price", B="quantity",
)
```

Custom properties plug into the same parameters you already know:

```python
# Breakdown
result = ws.query(
    "Purchase",
    group_by=GroupBy(
        property=revenue,
        property_type="number",
        bucket_size=100,
    ),
)

# Filter
result = ws.query(
    "Purchase",
    where=Filter.greater_than(property=ref, value=100),
)

# Measurement
result = ws.query(
    Metric("Purchase", math="average", property=ref),
)

# Mix with regular properties
result = ws.query(
    "Purchase",
    group_by=[
        "country",
        GroupBy(
            property=revenue,
            property_type="number",
            bucket_size=50,
        ),
    ],
    where=[
        Filter.equals("platform", "iOS"),
        Filter.greater_than(property=ref, value=100),
    ],
)
```

Works with `query()`, `query_funnel()`, and `query_retention()`.

---

### Breakdowns

`group_by=` accepts strings, `GroupBy` objects, `CohortBreakdown` objects, and lists mixing all three:

```python
# String — simple property breakdown
result = ws.query("Login", group_by="platform")

# Multiple properties
result = ws.query("Purchase", group_by=["country", "platform"])

# Numeric bucketing
result = ws.query(
    "Purchase",
    group_by=GroupBy(
        "revenue",
        property_type="number",
        bucket_size=50,
        bucket_min=0,
        bucket_max=500,
    ),
)

# Cohort breakdown
result = ws.query(
    "Purchase",
    group_by=CohortBreakdown(123, "Power Users"),
)

# Custom property breakdown
result = ws.query(
    "Purchase",
    group_by=GroupBy(
        property=CustomPropertyRef(42),
        property_type="number",
    ),
)

# Mix all types
result = ws.query(
    "Purchase",
    group_by=[
        "country",
        GroupBy(
            "revenue",
            property_type="number",
            bucket_size=50,
        ),
        CohortBreakdown(123, "Power Users"),
    ],
)
```

---

### Time ranges

`last=` and absolute dates (`from_date`/`to_date`) work in all five engines. The `unit=` parameter applies to insights, funnels, and retention (flows and users have no `unit=`).

```python
# Relative — last N days (default: 30)
result = ws.query("Login", last=90)
result = ws.query("Login", last=12, unit="week")

# Absolute — explicit dates
result = ws.query(
    "Login",
    from_date="2025-01-01",
    to_date="2025-03-31",
)

# Hourly granularity (insights only)
result = ws.query("Login", last=2, unit="hour")
```

---

## Validation

Every query is validated **before** the API call. Invalid parameters raise `BookmarkValidationError` with all errors at once — no "fix one, discover the next" cycle:

```python
from mixpanel_headless import BookmarkValidationError

try:
    ws.query_funnel([""], conversion_window=-1)
except BookmarkValidationError as e:
    for error in e.errors:
        print(f"[{error.code}] {error.path}: {error.message}")
        if error.suggestion:
            print(f"  Did you mean: {error.suggestion}")
    # [F2_EMPTY_STEP_EVENT] steps[0].event:
    #   Step event name must be a non-empty string
    # [F1_MIN_STEPS] steps:
    #   At least 2 steps are required (got 1)
    # [F3_CONVERSION_WINDOW_POSITIVE] conversion_window:
    #   conversion_window must be a positive integer
```

Each error includes:

| Field | What it is |
|---|---|
| `code` | Machine-readable rule ID (e.g., `V1`, `F3`, `R6`) |
| `path` | JSONPath-like location (e.g., `show[0].math`) |
| `message` | Human-readable description |
| `severity` | `"error"` or `"warning"` |
| `suggestion` | Fuzzy-matched alternatives for invalid enum values |
| `fix` | Suggested fix payload for programmatic correction |

You can also validate insights, funnel, or retention bookmark JSON directly (flow params are validated internally by `query_flow()`):

```python
from mixpanel_headless import validate_bookmark

errors = validate_bookmark(some_bookmark_dict)
```

---

## Inspect and persist: `build_*_params()`

Every `query_*()` method has a corresponding `build_*_params()` that generates and validates the bookmark JSON without executing the query:

```python
# Inspect what would be sent to the API
params = ws.build_params(
    "Login", math="dau", group_by="platform", last=90,
)
params = ws.build_funnel_params(
    ["Signup", "Purchase"], conversion_window=7,
)
params = ws.build_retention_params(
    "Signup", "Login", retention_unit="week",
)
params = ws.build_flow_params(
    "Purchase", forward=3, reverse=1,
)

import json
print(json.dumps(params, indent=2))
```

Save any query as a Mixpanel report:

```python
from mixpanel_headless import CreateBookmarkParams

result = ws.query("Login", math="dau", group_by="platform", last=90)

ws.create_bookmark(CreateBookmarkParams(
    name="DAU by Platform (90d)",
    bookmark_type="insights",
    params=result.params,
))
```

This works for all five engines. Build params in code, persist them as reports visible in the Mixpanel UI.

---

## One query, eight capabilities

Here's the single query that best demonstrates what the unified system can do. The business question it answers: *"What's the ARPU among activated users, by pricing plan, as a 4-week rolling average over the last quarter?"*

Every B2B SaaS PM asks this. In the Mixpanel UI it requires creating a saved custom property, creating a saved cohort, building a two-metric report with a formula, adding a breakdown, and configuring rolling analysis — minimum 10 clicks across 3 screens, plus two permanent entities to manage.

Here it's one call with zero pre-saved entities:

```python
from mixpanel_headless import (
    Workspace, Metric, Filter,
    InlineCustomProperty,
    CohortCriteria, CohortDefinition,
)

ws = Workspace()

# Revenue doesn't exist in the data — compute it
revenue = InlineCustomProperty.numeric(
    "A * B", A="price", B="quantity",
)

# Define the target segment in code
activated = CohortDefinition(
    CohortCriteria.did_event(
        "Complete Onboarding",
        at_least=1,
        within_days=14,
    )
)

# One call. Eight capabilities.
result = ws.query(
    [
        Metric(
            "Purchase",
            math="total",
            property=revenue,       # inline custom property
        ),
        Metric("Purchase", math="unique"),
    ],
    formula="(A / B)",              # ARPU formula
    formula_label="ARPU",
    where=Filter.in_cohort(         # inline cohort filter
        activated, name="Activated",
    ),
    group_by="plan",                # breakdown by plan tier
    rolling=4,                      # 4-week rolling average
    unit="week",
    last=90,
)

print(result.df)
# DataFrame with date, event, count columns:
#         date          event   count
# 0 2025-01-06  ARPU | Free   12.50
# 1 2025-01-06  ARPU | Pro    87.30
# 2 2025-01-06  ARPU | Ent   245.00
# ...

# Happy with it? Save as a Mixpanel report:
from mixpanel_headless import CreateBookmarkParams
ws.create_bookmark(CreateBookmarkParams(
    name="ARPU by Plan (Activated Users)",
    bookmark_type="insights",
    params=result.params,
))
```

What each line proves:

| Feature | What it demonstrates |
|---|---|
| `InlineCustomProperty.numeric(...)` | Compute values that don't exist in your data |
| `CohortDefinition(CohortCriteria(...))` | Define segments in code, no UI trip |
| `Metric(..., property=revenue)` | Custom properties plug into standard params |
| Two `Metric` objects | Different aggregation per metric |
| `formula="(A / B)"` | Derived KPIs from multiple metrics |
| `Filter.in_cohort(activated, ...)` | Scope to a programmatic segment |
| `group_by="plan"` | Segment by the dimension that matters |
| `rolling=4` | Smooth weekly noise into a trend |

Change `within_days=14` to `within_days=7` and re-run. Swap `"plan"` for `"country"`. Change the formula to `A * B * (1 - C)` to add discounts. Each iteration is instant — no UI round-trips, no saved entities to update.

---

## Putting it all together

A complete analysis combining multiple engines:

```python
import mixpanel_headless as mp
from mixpanel_headless import (
    Metric, Formula, Filter, GroupBy,
    FunnelStep, Exclusion, RetentionEvent,
    CohortCriteria, CohortDefinition,
    CohortBreakdown, InlineCustomProperty,
    CustomPropertyRef, CreateBookmarkParams,
)

ws = mp.Workspace()

# --- Reusable segments and computed properties ---

premium_users = CohortDefinition(
    CohortCriteria.did_event(
        "Upgrade", at_least=1, within_days=365,
    )
)

revenue = InlineCustomProperty.numeric(
    "A * B", A="price", B="quantity",
)


# --- Insights: revenue trends by country ---

daily_revenue = ws.query(
    Metric("Purchase", math="total", property=revenue),
    group_by="country",
    last=90,
    unit="week",
)
print(daily_revenue.df)


# --- Insights: conversion rate formula ---

conversion = ws.query(
    [
        Metric("Signup", math="unique"),
        Metric("Purchase", math="unique"),
    ],
    formula="(B / A) * 100",
    formula_label="Conversion Rate",
    where=Filter.in_cohort(
        premium_users, name="Premium",
    ),
    unit="week",
    last=90,
)
print(conversion.df)


# --- Funnels: checkout flow, premium vs. everyone ---

checkout = ws.query_funnel(
    [
        FunnelStep("Browse"),
        FunnelStep(
            "Add to Cart",
            filters=[Filter.greater_than("item_count", 0)],
        ),
        FunnelStep("Checkout"),
        FunnelStep("Purchase"),
    ],
    conversion_window=7,
    exclusions=["Logout"],
    group_by=CohortBreakdown(
        premium_users, name="Premium Users",
    ),
    last=90,
)
print(f"Overall: {checkout.overall_conversion_rate:.1%}")
print(checkout.df)


# --- Retention: do organic signups retain better? ---

bucket_sizes = [1, 3, 7, 14, 30]
organic_retention = ws.query_retention(
    RetentionEvent(
        "Signup",
        filters=[Filter.equals("source", "organic")],
    ),
    "Login",
    retention_unit="day",
    bucket_sizes=bucket_sizes,
    last=90,
)
avg = organic_retention.average
for day, rate in zip(bucket_sizes, avg["rates"]):
    print(f"  Day {day}: {rate:.1%}")


# --- Flows: what do users do after failed checkout? ---

failed_checkout = ws.query_flow(
    "Checkout Error",
    forward=4,
    hidden_events=["Session Start", "Page View"],
    cardinality=10,
    last=90,
)
for src, tgt, count in failed_checkout.top_transitions(5):
    print(f"  {src} -> {tgt}: {count:,}")

# Tree mode: where do users diverge?
tree_result = ws.query_flow(
    "Checkout Error", mode="tree", forward=4,
)
for tree in tree_result.trees:
    print(tree.render())


# --- Save any result as a Mixpanel report ---

ws.create_bookmark(CreateBookmarkParams(
    name="Checkout Funnel (Premium Segment)",
    bookmark_type="funnels",
    params=checkout.params,
))
```

---

## Quick reference

### Methods

| Method | Engine | Positional args |
|---|---|---|
| `query()` | Insights | `events` — str, Metric, Formula, or list |
| `query_funnel()` | Funnels | `steps` — list of str or FunnelStep |
| `query_retention()` | Retention | `born_event`, `return_event` |
| `query_flow()` | Flows | `event` — str, FlowStep, or list |
| `query_user()` | Users | keyword-only — `where`, `properties`, `sort_by`, `limit` |

Each has a matching `build_*_params()` that returns the validated params dict without querying.

### Shared parameters

| Parameter | Type | Default | Engines |
|---|---|---|---|
| `where=` | `Filter \| list[Filter]` | `None` | All |
| `group_by=` | `str \| GroupBy \| CohortBreakdown` | `None` | I, F, R |
| `last=` | `int` | `30` | I, F, R, Fl |
| `from_date=` | `str` (YYYY-MM-DD) | `None` | I, F, R, Fl |
| `to_date=` | `str` (YYYY-MM-DD) | `None` | I, F, R, Fl |
| `unit=` | `"day" \| "week" \| "month"` | `"day"` | I, F, R |
| `time_comparison=` | `str` | `None` | I, F, R |
| `data_group_id=` | `int` | `None` | I, F, R, Fl |
| `mode=` | engine-specific | varies | All |
| `math=` | engine-specific | varies | I, F, R |
| `math_property=` | `str` | `None` | I, F |

I = Insights, F = Funnels, R = Retention

### Engine-specific parameters

| Engine | Unique parameters |
|---|---|
| **Insights** | `per_user`, `percentile_value`, `formula`, `formula_label`, `rolling`, `cumulative` |
| **Funnels** | `conversion_window`, `conversion_window_unit`, `order`, `exclusions`, `holding_constant` |
| **Retention** | `retention_unit`, `alignment`, `bucket_sizes` |
| **Flows** | `forward`, `reverse`, `count_type`, `cardinality`, `collapse_repeated`, `hidden_events`, `segments`, `exclusions` |
| **Users** | `properties`, `sort_by`, `sort_order`, `limit`, `mode`, `aggregate`, `aggregate_property`, `percentile`, `segment_by`, `parallel`, `workers` |

### Result types

| Engine | Result type | Key properties |
|---|---|---|
| Insights | `QueryResult` | `.df`, `.series`, `.params` |
| Funnels | `FunnelQueryResult` | `.df`, `.overall_conversion_rate` |
| Retention | `RetentionQueryResult` | `.df`, `.cohorts`, `.average` |
| Flows | `FlowQueryResult` | `.nodes_df`, `.edges_df`, `.graph`, `.trees` |
| Users | `UserQueryResult` | `.df`, `.total`, `.value`, `.params` |

### Imports

```python
# Everything you might need
from mixpanel_headless import (
    # Core
    Workspace,

    # Insights
    Metric, Formula, GroupBy, Filter,
    MathType, PerUserAggregation,

    # Funnels
    FunnelStep, Exclusion, HoldingConstant,
    FunnelMathType,

    # Retention
    RetentionEvent,
    RetentionMathType,

    # Flows
    FlowStep, FlowTreeNode,

    # Cohorts
    CohortCriteria, CohortDefinition,
    CohortBreakdown, CohortMetric,

    # Custom properties
    CustomPropertyRef, InlineCustomProperty, PropertyInput,

    # Persistence
    CreateBookmarkParams,

    # Validation
    validate_bookmark, BookmarkValidationError,
)
```

---

## Next steps

- [Insights Queries](query.md) — full parameter reference, all 14 math types, per-user aggregation
- [Funnel Queries](query-funnels.md) — step configuration, exclusion targeting, session funnels
- [Retention Queries](query-retention.md) — alignment modes, custom buckets, cohort structure
- [Flow Queries](query-flows.md) — NetworkX graph algorithms, tree traversal, anytree export
- [User Profile Queries](query-users.md) — filtering, sorting, property selection, aggregation
- [API Reference: Workspace](../api/workspace.md) — complete method signatures
- [API Reference: Types](../api/types.md) — all type definitions
