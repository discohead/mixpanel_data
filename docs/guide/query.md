# Insights Queries

Build typed analytics queries against Mixpanel's Insights engine — the same engine that powers the Mixpanel web UI.

!!! tip "Recommended"
    `Workspace.query()` is the primary way to run analytics queries programmatically. It supports capabilities not available through the legacy query methods, including DAU/WAU/MAU, multi-metric comparison, formulas, per-user aggregation, rolling windows, and percentiles.

## When to Use `query()`

`query()` uses the Insights engine via inline bookmark params. The legacy methods (`segmentation()`, `funnel()`, `retention()`) use the older Query API endpoints. Use `query()` when you need any of the capabilities in the right column:

| Capability | Legacy methods | `query()` |
|---|---|---|
| Simple event count over time | `segmentation()` | `ws.query("Login")` |
| Unique users | `segmentation(type="unique")` | `math="unique"` |
| DAU / WAU / MAU | Not available | `math="dau"` |
| Multi-metric comparison | Not available | `["Signup", "Login", "Purchase"]` |
| Formulas (conversion rates, ratios) | Not available | `formula="(B/A)*100"` |
| Per-user aggregation | Not available | `per_user="average"` |
| Rolling / cumulative analysis | Not available | `rolling=7` |
| Percentiles (p25/p75/p90/p99) | Not available | `math="p90"` |
| Typed filters | Expression strings | `Filter.equals("country", "US")` |
| Numeric bucketed breakdowns | Not available | `GroupBy("revenue", property_type="number")` |
| Save query as a report | N/A | `result.params` → `create_bookmark()` |

Use the legacy methods when:

- You need to query a saved funnel by ID → `funnel()`
- You need cohort retention curves → `query_retention()` ([Retention Queries](query-retention.md))
- You need raw JQL execution → `jql()`
- You need to query a saved Flows report → `query_saved_flows()`

For ad-hoc funnel conversion analysis with typed step definitions, see **[Funnel Queries](query-funnels.md)**.
For ad-hoc flow path analysis with typed step definitions, see **[Flow Queries](query-flows.md)**.

## Getting Started

The simplest possible query — total event count per day for the last 30 days:

```python
import mixpanel_headless as mp

ws = mp.Workspace()

result = ws.query("Login")
print(result.df.head())
#         date                    event  count
# 0  2025-03-01  Login [Total Events]    142
# 1  2025-03-02  Login [Total Events]    158
```

Add a time range and aggregation:

```python
# Unique users per week for the last 7 days
result = ws.query("Login", math="unique", last=7, unit="week")

# Last 90 days of DAU
result = ws.query("Login", math="dau", last=90)

# Specific date range
result = ws.query(
    "Purchase",
    from_date="2025-01-01",
    to_date="2025-03-31",
    unit="month",
)
```

## Aggregation

### Counting

| Math type | What it counts |
|---|---|
| `"total"` (default) | Total event occurrences |
| `"unique"` | Unique users per period |
| `"dau"` | Daily active users |
| `"wau"` | Weekly active users |
| `"mau"` | Monthly active users |
| `"cumulative_unique"` | Running count of distinct users over time |
| `"sessions"` | Session count (not events or users) |

```python
# DAU over the last 90 days
result = ws.query("Login", math="dau", last=90)

# Monthly active users
result = ws.query("Login", math="mau", last=6, unit="month")

# Cumulative unique users over time
result = ws.query("Login", math="cumulative_unique", last=90)

# Count sessions instead of events
result = ws.query("Login", math="sessions", last=30)

# Distinct values of a property
result = ws.query("Purchase", math="unique_values", math_property="product_id")
```

### Property Aggregation

Aggregate a numeric property across events. Requires `math_property`:

| Math type | Aggregation |
|---|---|
| `"total"` + `math_property` | Sum of a numeric property |
| `"average"` | Mean value |
| `"median"` | Median value |
| `"min"` / `"max"` | Extremes |
| `"p25"` / `"p75"` / `"p90"` / `"p99"` | Percentiles |
| `"percentile"` + `percentile_value` | Custom percentile (e.g. p95) |
| `"histogram"` | Distribution of property values |
| `"unique_values"` | Count of distinct values of a property |
| `"most_frequent"` | Most commonly occurring property value |
| `"first_value"` | First observed value per user |
| `"multi_attribution"` | Multi-touch attribution across a property |
| `"numeric_summary"` | Summary stats (count, mean, variance) |

```python
# Average purchase amount per day
result = ws.query(
    "Purchase",
    math="average",
    math_property="amount",
    from_date="2025-01-01",
    to_date="2025-01-31",
)

# P90 response time
result = ws.query("API Call", math="p90", math_property="duration_ms")

# Custom percentile (p95) — use math="percentile" with percentile_value
result = ws.query(
    "API Call",
    math="percentile",
    math_property="duration_ms",
    percentile_value=95,
)

# Histogram — distribution of purchase amounts
result = ws.query("Purchase", math="histogram", math_property="amount")
```

### Per-User Aggregation

Aggregate per user first, then across all users — like a SQL subquery. For example, "what's the average number of purchases per user per week?"

```python
# Average purchases per user per week
result = ws.query(
    "Purchase",
    math="total",
    per_user="average",
    unit="week",
)
```

Valid `per_user` values: `"unique_values"`, `"total"`, `"average"`, `"min"`, `"max"`.

!!! note
    `per_user` is incompatible with `dau`, `wau`, `mau`, and `unique` math types.

### Segment Method

Control how events are counted per user with `Metric.segment_method`:

- `"all"` (default) — count every qualifying event
- `"first"` — count only the first qualifying event per user

```python
from mixpanel_headless import Metric

# Only count each user's first purchase
result = ws.query(Metric("Purchase", segment_method="first"), last=30)
```

### The `Metric` Class

When different events need different aggregation settings, use `Metric` objects instead of plain strings:

```python
from mixpanel_headless import Metric

# Different math per event
result = ws.query([
    Metric("Signup", math="unique"),
    Metric("Purchase", math="total", property="revenue"),
])
```

`Metric` also supports `percentile_value` for custom percentiles:

```python
# Per-metric custom percentile
result = ws.query(
    Metric("API Call", math="percentile", property="duration_ms", percentile_value=95),
)
```

Plain strings inherit the top-level `math`, `math_property`, and `per_user` defaults. `Metric` objects override them per-event:

```python
# These are equivalent:
ws.query("Login", math="unique")
ws.query(Metric("Login", math="unique"))

# Top-level defaults apply to all string events:
ws.query(["Signup", "Login"], math="unique")
# Both events use math="unique"

# Metric overrides per event:
ws.query([
    Metric("Signup", math="unique"),    # unique users
    Metric("Purchase", math="total"),   # total events
])
```

## Filters

### Global Filters

Apply filters across all metrics with `where=`. Construct filters using `Filter` class methods:

```python
from mixpanel_headless import Filter

# Single filter
result = ws.query(
    "Purchase",
    where=Filter.equals("country", "US"),
)

# Multiple filters (combined with AND)
result = ws.query(
    "Purchase",
    where=[
        Filter.equals("country", "US"),
        Filter.greater_than("amount", 50),
    ],
)
```

### Available Filter Methods

**String filters:**

```python
Filter.equals("browser", "Chrome")           # equals value
Filter.equals("browser", ["Chrome", "Firefox"])  # equals any in list
Filter.not_equals("browser", "Safari")        # does not equal
Filter.contains("email", "@company.com")      # contains substring
Filter.not_contains("url", "staging")         # does not contain
Filter.starts_with("email", "admin")          # prefix match
Filter.ends_with("email", "@company.com")     # suffix match
```

**Numeric filters:**

```python
Filter.greater_than("amount", 100)            # > 100
Filter.less_than("age", 65)                   # < 65
Filter.between("amount", 10, 100)             # 10 <= x <= 100
Filter.not_between("age", 18, 65)             # outside a range
Filter.at_least("score", 80)                  # >= 80
Filter.at_most("errors", 5)                   # <= 5
```

**Existence filters:**

```python
Filter.is_set("phone_number")                 # property exists
Filter.is_not_set("email")                    # property is null
```

**Boolean filters:**

```python
Filter.is_true("is_premium")                  # boolean true
Filter.is_false("is_trial")                   # boolean false
```

### List-of-object filters

When a property's value is a list of objects (e.g. `cart` is a list of `{Brand, Category, Price}` items), use `Filter.list_contains` to filter on a subproperty. Discover valid subproperty names and types via [`Workspace.subproperties()`](discovery.md#subproperties) first.

**Keyword shorthand** for the common equality case — each `key=value` becomes an inner equality filter. All inner conditions must match the same item:

```python
# Cart contains a nike-branded hat
result = ws.query(
    "Cart Viewed",
    where=Filter.list_contains("cart", Brand="nike", Category="hats"),
)
```

**Explicit `Filter` instances** for any non-equality operator:

```python
# Cart contains an item costing more than $50
result = ws.query(
    "Cart Viewed",
    where=Filter.list_contains("cart", Filter.greater_than("Price", 50)),
)
```

**Quantifier** — `"any"` (default) requires at least one item to satisfy all inner conditions; `"all"` requires every item to:

```python
# Every cart item costs more than $50
where = Filter.list_contains(
    "cart",
    Filter.greater_than("Price", 50),
    quantifier="all",
)
```

**Resource type** — `Filter.list_contains` accepts `resource_type="people"` for list-of-object people properties (e.g. `addresses`). When using kwarg shorthand, the inner equality filters inherit the outer `resource_type`. When passing positional `Filter` instances, each carries its own `resource_type` from its own factory call — pass `resource_type=` explicitly on each inner factory if you want them to match the outer.

```python
# Filter people by a list-of-object property
where = Filter.list_contains("addresses", resource_type="people", City="Brooklyn")
```

Cannot be nested (a `list_contains` cannot appear inside another `list_contains`). Mixing the kwarg and positional shapes in one call raises `ValueError`.

### Per-Metric Filters

Apply filters to individual metrics using `Metric.filters`:

```python
from mixpanel_headless import Metric, Filter

# Different filters on each event
result = ws.query([
    Metric("Purchase", math="unique"),
    Metric(
        "Purchase",
        math="unique",
        filters=[Filter.equals("plan", "premium")],
    ),
])
```

By default, multiple per-metric filters combine with AND logic. Use `filters_combinator="any"` for OR logic:

```python
result = ws.query(Metric(
    "Purchase",
    math="unique",
    filters=[
        Filter.equals("country", "US"),
        Filter.equals("country", "CA"),
    ],
    filters_combinator="any",  # match US OR CA
))
```

### Date Filters

Filter by datetime properties using purpose-built factory methods:

```python
from mixpanel_headless import Filter

# Absolute date filters
Filter.on("created", "2025-01-15")              # exact date match
Filter.not_on("created", "2025-01-15")           # not on date
Filter.before("created", "2025-01-01")           # before a date
Filter.since("created", "2025-01-01")            # on or after a date
Filter.date_between("created", "2025-01-01", "2025-06-30")  # date range

# Relative date filters — "in the last N units"
Filter.in_the_last("created", 30, "day")         # last 30 days
Filter.in_the_last("last_seen", 2, "week")       # last 2 weeks
Filter.not_in_the_last("created", 90, "day")     # NOT in last 90 days
Filter.date_not_between("created", "2025-01-01", "2025-06-30")  # dates outside a range
Filter.in_the_next("renewal_date", 30, "day")    # relative future date
```

The relative date methods accept a `FilterDateUnit`: `"hour"`, `"day"`, `"week"`, or `"month"`.

```python
from mixpanel_headless import FilterDateUnit  # Literal["hour", "day", "week", "month"]

# Example: recent signups with purchases
result = ws.query(
    "Purchase",
    where=Filter.in_the_last("signup_date", 7, "day"),
    last=30,
)
```

## Breakdowns

### String Breakdowns

Break down results by property values with `group_by`:

```python
# Simple string breakdown
result = ws.query("Login", group_by="platform", last=14)

# Multiple breakdowns
result = ws.query("Purchase", group_by=["country", "platform"])
```

### The `GroupBy` Class

For numeric bucketing, boolean breakdowns, or explicit type annotations, use `GroupBy`:

```python
from mixpanel_headless import GroupBy

# Numeric breakdown with buckets
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

# Boolean breakdown
result = ws.query(
    "Login",
    group_by=GroupBy("is_premium", property_type="boolean"),
)

# Mixed: string shorthand + GroupBy
result = ws.query(
    "Purchase",
    group_by=[
        "country",
        GroupBy("amount", property_type="number", bucket_size=25),
    ],
)
```

### List-of-object breakdowns

Mirror `Filter.list_contains` for breakdowns: when a property is a list of objects, break down by one of its subproperties via `GroupBy.list_item`. Discover valid subproperty names and types via [`Workspace.subproperties()`](discovery.md#subproperties).

```python
from mixpanel_headless import GroupBy

# Break down Cart Viewed events by cart.Brand
result = ws.query("Cart Viewed", group_by=GroupBy.list_item("cart", "Brand"))

# Break down by a numeric subproperty (sub_type controls aggregation)
result = ws.query(
    "Cart Viewed",
    group_by=GroupBy.list_item("cart", "Price", sub_type="number"),
)

# Mix list-item with regular breakdowns
result = ws.query(
    "Cart Viewed",
    group_by=["country", GroupBy.list_item("cart", "Brand")],
)
```

`sub_type` accepts the four scalar values from `CustomPropertyType` (`"string"`, `"number"`, `"boolean"`, `"datetime"`). Bucketing (`bucket_size`/`bucket_min`/`bucket_max`) is incompatible with list-item breakdowns.

!!! note "Asymmetric with `Filter.list_contains`"
    `GroupBy.list_item` is **events-only** — there is no `resource_type` parameter, because Mixpanel's UI does not support list-of-object breakdowns for people properties. `Filter.list_contains` accepts `resource_type="people"` because the wire format permits list-object filters on people properties (just not breakdowns).

## Formulas

Compute derived metrics from multiple events. Letters A-Z reference events by their position in the list.

### Top-Level `formula` Parameter

```python
from mixpanel_headless import Metric

# Conversion rate: purchases / signups * 100
result = ws.query(
    [Metric("Signup", math="unique"), Metric("Purchase", math="unique")],
    formula="(B / A) * 100",
    formula_label="Conversion Rate",
    unit="week",
)
```

When `formula` is set, the underlying metrics are automatically hidden — only the formula result appears in the output.

### `Formula` Class in Events List

For inline formula definitions, pass `Formula` objects alongside events:

```python
from mixpanel_headless import Metric, Formula

result = ws.query([
    Metric("Signup", math="unique"),
    Metric("Purchase", math="unique"),
    Formula("(B / A) * 100", label="Conversion Rate"),
])
```

Both approaches produce identical results. Use whichever reads more naturally.

### Multi-Metric Comparison (No Formula)

Compare multiple events side by side without a formula:

```python
# Three events on the same chart
result = ws.query(
    ["Signup", "Login", "Purchase"],
    math="unique",
    last=30,
)
```

## Time Ranges

### Relative (Default)

By default, `query()` returns the last 30 days. Customize with `last` and `unit`:

```python
# Last 7 days (daily granularity)
result = ws.query("Login", last=7)

# Last 4 weeks (weekly granularity)
result = ws.query("Login", last=4, unit="week")

# Last 6 months
result = ws.query("Login", last=6, unit="month")
```

The `unit` controls both what "last N" means and how data is bucketed on the time axis.

### Absolute

Specify explicit start and end dates:

```python
# Q1 2025
result = ws.query(
    "Purchase",
    from_date="2025-01-01",
    to_date="2025-03-31",
    unit="week",
)

# From a date to today
result = ws.query("Login", from_date="2025-01-01")
```

Dates must be in `YYYY-MM-DD` format.

### Hourly Granularity

Use `unit="hour"` for intraday analysis:

```python
result = ws.query("Login", last=2, unit="hour")
```

## Analysis Modes

### Rolling Windows

Smooth noisy data with a rolling average:

```python
# 7-day rolling average of signups by country
result = ws.query(
    "Signup",
    math="unique",
    group_by="country",
    rolling=7,
    last=60,
)
```

### Cumulative

Show running totals over time:

```python
result = ws.query("Signup", math="unique", cumulative=True, last=30)
```

!!! note
    `rolling` and `cumulative` are mutually exclusive.

### Result Modes

The `mode` parameter controls result aggregation semantics:

| Mode | Semantics | Use case |
|---|---|---|
| `"timeseries"` (default) | Per-period values | Trends over time |
| `"total"` | Single aggregate across the date range | KPI numbers |
| `"table"` | Tabular detail | Detailed breakdowns |

```python
# Single KPI number: total unique purchasers this month
result = ws.query(
    "Purchase",
    math="unique",
    from_date="2025-03-01",
    to_date="2025-03-31",
    mode="total",
)
total = result.df["count"].iloc[0]
```

!!! warning "Mode affects aggregation"
    `mode="total"` with `math="unique"` deduplicates users across the **entire date range**. `mode="timeseries"` with `math="unique"` counts unique users **per period** (not additive across periods). This is not just a display difference — it changes the numbers.

## Period-over-Period Comparison

Compare the current time range against a previous period using `TimeComparison`:

```python
from mixpanel_headless import TimeComparison

# Compare against previous week
result = ws.query("Login", time_comparison=TimeComparison.relative("week"), last=7)

# Compare against window starting on a fixed date
result = ws.query(
    "Purchase",
    time_comparison=TimeComparison.absolute_start("2025-01-01"),
    from_date="2026-01-01",
    to_date="2026-01-31",
)

# Compare against window ending on a fixed date
result = ws.query(
    "Purchase",
    time_comparison=TimeComparison.absolute_end("2025-12-31"),
    from_date="2026-01-01",
    to_date="2026-01-31",
)
```

Three factory methods:

| Method | What it compares against |
|---|---|
| `TimeComparison.relative(unit)` | Previous period offset by unit (day, week, month, quarter, year) |
| `TimeComparison.absolute_start(date)` | Window starting on a fixed date, same duration |
| `TimeComparison.absolute_end(date)` | Window ending on a fixed date, same duration |

`TimeComparison` also works with `query_funnel()` and `query_retention()`.

## Frequency Analysis

### Frequency Breakdown

Break down results by how often users performed an event using `FrequencyBreakdown`:

```python
from mixpanel_headless import FrequencyBreakdown

# How are logins distributed by purchase frequency?
result = ws.query(
    "Login",
    group_by=FrequencyBreakdown(
        event="Purchase",
        bucket_size=1,
        bucket_min=0,
        bucket_max=10,
    ),
    last=30,
)
```

Parameters:

| Parameter | Type | Default | Description |
|---|---|---|---|
| `event` | `str` | required | Event to count frequency for |
| `bucket_size` | `int` | `1` | Width of each frequency bucket |
| `bucket_min` | `int` | `0` | Minimum frequency value |
| `bucket_max` | `int` | `10` | Maximum frequency value |
| `label` | `str \| None` | `None` | Display label |

### Frequency Filter

Filter to users who performed an event a certain number of times using `FrequencyFilter`:

```python
from mixpanel_headless import FrequencyFilter

# Only users who purchased at least 3 times
result = ws.query(
    "Login",
    where=FrequencyFilter(
        event="Purchase",
        value=3,
        operator="is at least",
    ),
    last=30,
)

# With a lookback window — purchased at least 3 times in the last 30 days
result = ws.query(
    "Login",
    where=FrequencyFilter(
        event="Purchase",
        value=3,
        operator="is at least",
        date_range_value=30,
        date_range_unit="day",
    ),
    last=90,
)
```

Operators: `"is at least"`, `"is at most"`, `"is greater than"`, `"is less than"`, `"is equal to"`.

## Data Groups

Scope a query to a specific data group for group-level analytics:

```python
result = ws.query("Login", data_group_id=42, last=30)
```

`data_group_id` is available on all query engines: `query()`, `query_funnel()`, `query_retention()`, and `query_flow()`.

## Working with Results

### `QueryResult`

`query()` returns a `QueryResult` with:

```python
result = ws.query("Login", math="unique", last=7)

# DataFrame (lazy, cached)
result.df                  # pandas DataFrame

# Raw series data
result.series              # {"Login [Unique Users]": {"2025-03-01...": 142, ...}}

# Time range
result.from_date           # "2025-03-25T00:00:00-07:00"
result.to_date             # "2025-03-31T23:59:59.999000-07:00"

# Metadata
result.computed_at         # "2025-03-31T12:00:00.000000+00:00"
result.headers             # ["$metric"]
result.meta                # {"min_sampling_factor": 1.0, ...}

# Generated bookmark params (for debugging or persistence)
result.params              # dict — the full bookmark JSON sent to API
```

### DataFrame Structure

For **timeseries** mode, the DataFrame has columns `date`, `event`, `count`:

```python
result = ws.query(["Signup", "Login"], math="unique")
print(result.df.head())
#         date                      event  count
# 0  2025-03-01  Signup [Unique Users]    85
# 1  2025-03-01   Login [Unique Users]   312
# 2  2025-03-02  Signup [Unique Users]    92
```

For **total** mode, the DataFrame has columns `event`, `count` (no date).

### Persisting as a Saved Report

The generated bookmark params can be saved as a Mixpanel report:

```python
from mixpanel_headless import CreateBookmarkParams

# Run query
result = ws.query("Login", math="dau", group_by="platform", last=90)

# Save as a report using the generated params
ws.create_bookmark(CreateBookmarkParams(
    name="DAU by Platform (90d)",
    bookmark_type="insights",
    params=result.params,
))
```

### Debugging

Inspect `result.params` to see the exact bookmark JSON sent to the API. This is useful for:

- Understanding what was actually queried
- Comparing with Mixpanel web UI bookmark params
- Diagnosing unexpected results

```python
import json

result = ws.query("Login", math="unique", group_by="platform")
print(json.dumps(result.params, indent=2))
```

## Validation

`query()` validates all parameter combinations **before** making an API call and raises `ValueError` with descriptive messages:

| Rule | Error message |
|---|---|
| Property math without property | `math='average' requires math_property to be set` |
| Property set with counting math | `math_property is only valid with property-based math types` |
| Per-user with DAU/WAU/MAU | `per_user is incompatible with math='dau'` |
| Formula with < 2 events | `formula requires at least 2 events` |
| Rolling + cumulative | `rolling and cumulative are mutually exclusive` |
| `to_date` without `from_date` | `to_date requires from_date` |
| Invalid date format | `from_date must be YYYY-MM-DD format` |
| Invalid bucket config | `bucket_min/bucket_max require bucket_size` |

## Complete Examples

### Revenue Dashboard Metrics

```python
import mixpanel_headless as mp
from mixpanel_headless import Metric, Filter, GroupBy

ws = mp.Workspace()

# Total revenue by country this quarter
revenue = ws.query(
    "Purchase",
    math="total",
    math_property="amount",
    group_by="country",
    from_date="2025-01-01",
    to_date="2025-03-31",
    unit="month",
)

# Revenue distribution by bucket
distribution = ws.query(
    "Purchase",
    group_by=GroupBy(
        "amount",
        property_type="number",
        bucket_size=25,
        bucket_min=0,
        bucket_max=500,
    ),
    last=30,
)

# Conversion rate with per-metric filters
conversion = ws.query(
    [
        Metric("Purchase", math="unique"),
        Metric(
            "Purchase",
            math="unique",
            filters=[Filter.equals("plan", "premium")],
        ),
    ],
    formula="(B / A) * 100",
    formula_label="Premium %",
    group_by="platform",
    unit="week",
)
```

### User Engagement Analysis

```python
# 7-day rolling average of DAU by platform
engagement = ws.query(
    "Login",
    math="dau",
    group_by="platform",
    rolling=7,
    last=90,
)

# Average sessions per user per week
sessions = ws.query(
    "Session Start",
    math="total",
    per_user="average",
    unit="week",
    last=12,
)

# WAU trend for premium users
wau = ws.query(
    "Login",
    math="wau",
    where=Filter.is_true("is_premium"),
    last=6,
    unit="month",
)
```

## Generating Params Without Querying

Use `build_params()` to generate bookmark params without making an API call — useful for debugging, inspecting the generated JSON, or saving queries as reports:

```python
# Same arguments as query(), returns dict instead of QueryResult
params = ws.build_params(
    "Login",
    math="dau",
    group_by="platform",
    where=Filter.in_the_last("created", 30, "day"),
    last=90,
)

import json
print(json.dumps(params, indent=2))  # inspect the generated bookmark JSON

# Save as a report directly from params
ws.create_bookmark(CreateBookmarkParams(
    name="DAU by Platform (90d)",
    bookmark_type="insights",
    params=params,
))
```

## What's Next

`query()` is the foundation for a family of typed query methods. Each follows the same pattern — typed Python arguments generating the correct bookmark params:

- **[`query_funnel()`](query-funnels.md)** — Ad-hoc funnel conversion analysis with typed step definitions, exclusions, and conversion windows
- **[`query_retention()`](query-retention.md)** — Ad-hoc retention curves with event pairs, custom buckets, and alignment modes
- **[`query_flow()`](query-flows.md)** — Ad-hoc flow path analysis with step definitions, direction controls, and visualization modes
- **Cohort-scoped queries** — Filter, break down, or track cohort membership across all engines (see below)

## Cohort-Scoped Queries

Scope any query to a user segment — filter by cohort membership, break down by cohort, or track cohort size as a metric. Use saved cohort IDs or define cohorts inline with `CohortDefinition`.

### Cohort Filters

Restrict queries to users in (or not in) a cohort using `Filter.in_cohort()` and `Filter.not_in_cohort()`:

```python
from mixpanel_headless import Filter, CohortCriteria, CohortDefinition

# Saved cohort
result = ws.query("Purchase", where=Filter.in_cohort(123, "Power Users"))

# Inline cohort — define the segment right where you use it
power_users = CohortDefinition(
    CohortCriteria.did_event("Purchase", at_least=3, within_days=30)
)
result = ws.query("Login", where=Filter.in_cohort(power_users, name="Power Users"))

# Exclude a cohort
result = ws.query("Purchase", where=Filter.not_in_cohort(789, "Bots"))

# Combine with property filters
result = ws.query(
    "Purchase",
    where=[Filter.in_cohort(power_users, name="PU"), Filter.equals("platform", "iOS")],
)
```

Cohort filters work with all five query methods: `query()`, `query_funnel()`, `query_retention()`, `query_flow()`, and `query_user()`.

### Cohort Breakdowns

Segment results by cohort membership using `CohortBreakdown` in the `group_by=` parameter:

```python
from mixpanel_headless import CohortBreakdown

# Compare cohort vs. everyone else
result = ws.query(
    "Purchase",
    group_by=CohortBreakdown(123, "Power Users"),
)
# Result segments: "Power Users" and "Not In Power Users"

# Inline cohort breakdown
result = ws.query(
    "Purchase",
    group_by=CohortBreakdown(power_users, name="Power Users"),
)

# Only the cohort segment (no "Not In" group)
result = ws.query(
    "Purchase",
    group_by=CohortBreakdown(123, "PU", include_negated=False),
)

# Mix with property breakdowns
result = ws.query(
    "Purchase",
    group_by=[CohortBreakdown(123, "Power Users"), "platform"],
)
```

Cohort breakdowns work with `query()`, `query_funnel()`, and `query_retention()` (not flows).

### Cohort Metrics

Track cohort size over time as a metric — insights only:

```python
from mixpanel_headless import CohortMetric, Metric

# Track cohort growth
result = ws.query(CohortMetric(123, "Power Users"), last=90, unit="week")

# What % of active users are power users?
result = ws.query(
    [Metric("Login", math="unique"), CohortMetric(123, "Power Users")],
    formula="(B / A) * 100",
    formula_label="Power User %",
)
```

`CohortMetric` is insights-only — it cannot be used with `query_funnel()`, `query_retention()`, or `query_flow()`.

### Engine Compatibility

| Capability | `query()` | `query_funnel()` | `query_retention()` | `query_flow()` |
|---|:-:|:-:|:-:|:-:|
| **Cohort Filters** (`where=`) | ✓ | ✓ | ✓ | ✓ |
| **Cohort Breakdowns** (`group_by=`) | ✓ | ✓ | ✓ | — |
| **Cohort Metrics** (`events=`) | ✓ | — | — | — |

## Custom Properties in Queries

Use saved custom properties or define computed properties inline — in breakdowns, filters, and metric measurement. Custom properties work everywhere a plain string property name does.

To create and manage custom properties in Mixpanel, see [Data Governance — Custom Properties](data-governance.md#custom-properties).

### Referencing a Saved Custom Property

Use `CustomPropertyRef` to reference a custom property that already exists in your Mixpanel project by its numeric ID:

```python
from mixpanel_headless import CustomPropertyRef, GroupBy, Filter, Metric

ref = CustomPropertyRef(42)

# Breakdown by saved custom property
result = ws.query("Purchase", group_by=GroupBy(property=ref, property_type="number"))

# Filter by saved custom property
result = ws.query("Purchase", where=Filter.greater_than(property=ref, value=100))

# Aggregate a saved custom property
result = ws.query(Metric("Purchase", math="average", property=ref))
```

Find custom property IDs with `ws.list_custom_properties()` or `mp custom-properties list`.

### Inline Custom Properties

Use `InlineCustomProperty` to define a computed property at query time — no need to save it to your project first. Formulas reference raw properties through single-letter variables (A–Z), each mapped to a `PropertyInput`:

```python
from mixpanel_headless import InlineCustomProperty, PropertyInput

# Full constructor — explicit control over types
revenue = InlineCustomProperty(
    formula="A * B",
    inputs={
        "A": PropertyInput("price", type="number"),
        "B": PropertyInput("quantity", type="number"),
    },
    property_type="number",
)
```

For the common case of numeric formulas over event properties, use the `numeric()` convenience constructor:

```python
# Shorthand — auto-creates numeric PropertyInput objects
revenue = InlineCustomProperty.numeric("A * B", A="price", B="quantity")
```

Both forms produce identical results. Use the full constructor when you need non-numeric types or user-profile properties (`resource_type="user"`).

### Custom Property Breakdowns

Pass a custom property to `GroupBy.property` for breakdowns. Numeric bucketing works the same as with regular properties:

```python
from mixpanel_headless import GroupBy, CustomPropertyRef, InlineCustomProperty

# Saved custom property with numeric buckets
result = ws.query(
    "Purchase",
    group_by=GroupBy(
        property=CustomPropertyRef(42),
        property_type="number",
        bucket_size=50,
    ),
)

# Inline computed property
result = ws.query(
    "Purchase",
    group_by=GroupBy(
        property=InlineCustomProperty.numeric("A * B", A="price", B="quantity"),
        property_type="number",
        bucket_size=100,
        bucket_min=0,
        bucket_max=1000,
    ),
)

# Mix with regular property breakdowns
result = ws.query(
    "Purchase",
    group_by=["country", GroupBy(property=CustomPropertyRef(42), property_type="number")],
)
```

### Custom Property Filters

All 18 `Filter` factory methods accept custom properties in the `property` parameter:

```python
from mixpanel_headless import Filter, CustomPropertyRef, InlineCustomProperty

# Saved custom property
result = ws.query(
    "Purchase",
    where=Filter.greater_than(property=CustomPropertyRef(42), value=100),
)

# Inline computed property
result = ws.query(
    "Purchase",
    where=Filter.between(
        property=InlineCustomProperty.numeric("A * B", A="price", B="quantity"),
        value=[100, 1000],
    ),
)

# Combine with regular filters
result = ws.query(
    "Purchase",
    where=[
        Filter.equals("country", "US"),
        Filter.greater_than(property=CustomPropertyRef(42), value=50),
    ],
)
```

### Custom Property Measurement

Aggregate a custom property as the metric value using `Metric(property=...)`:

```python
from mixpanel_headless import Metric, CustomPropertyRef, InlineCustomProperty

# Average of a saved custom property
result = ws.query(
    Metric("Purchase", math="average", property=CustomPropertyRef(42)),
)

# Sum of an inline computed property
result = ws.query(
    Metric("Purchase", math="total", property=InlineCustomProperty.numeric("A * B", A="price", B="quantity")),
)

# Per-metric custom properties in multi-metric queries
result = ws.query([
    Metric("Purchase", math="total", property=InlineCustomProperty.numeric("A * B", A="price", B="quantity")),
    Metric("Purchase", math="unique"),
])
```

!!! warning "Use `Metric(property=...)`, not `math_property=`"
    The top-level `math_property` parameter only accepts plain string property names. To use a custom property for measurement, wrap the event in a `Metric` object and set `property=` on it.

### Engine Compatibility

| Capability | `query()` | `query_funnel()` | `query_retention()` | `query_flow()` |
|---|:-:|:-:|:-:|:-:|
| **CP Breakdowns** (`group_by=`) | ✓ | ✓ | ✓ | — |
| **CP Filters** (`where=`) | ✓ | ⚠ | ⚠ | — |
| **CP Measurement** (`Metric.property=`) | ✓ | — | — | — |

⚠ = Supported, but a known Mixpanel server bug may cause errors when custom property filters are used in funnel and retention global `where=`. Custom property breakdowns and measurement work reliably in those engines.

`query_flow()` does not support custom properties in any position (Mixpanel limitation).

### Custom Property Validation

Custom properties are validated **before** any API call. Invalid configurations raise `BookmarkValidationError`:

| Rule | Error code | Error message |
|---|---|---|
| ID must be positive integer | `CP1_INVALID_ID` | custom property ID must be a positive integer (got {id}) |
| Formula must be non-empty | `CP2_EMPTY_FORMULA` | inline custom property formula must be non-empty |
| At least one input required | `CP3_EMPTY_INPUTS` | inline custom property must have at least one input |
| Input keys must be single A–Z | `CP4_INVALID_INPUT_KEY` | input keys must be single uppercase letters (A-Z), got {key!r} |
| Formula max 20,000 chars | `CP5_FORMULA_TOO_LONG` | formula exceeds maximum length of 20,000 characters (got {len}) |
| Input property name non-empty | `CP6_EMPTY_INPUT_NAME` | input {key!r} has an empty property name |

```python
from mixpanel_headless import BookmarkValidationError, CustomPropertyRef

try:
    ws.query("Purchase", group_by=GroupBy(property=CustomPropertyRef(0), property_type="number"))
except BookmarkValidationError as e:
    for error in e.errors:
        print(f"[{error.code}] {error.path}: {error.message}")
    # [CP1_INVALID_ID] group_by[0].property: custom property ID must be a positive integer (got 0)
```

## Next Steps

- [Funnel Queries](query-funnels.md) — Typed funnel conversion analysis
- [Retention Queries](query-retention.md) — Typed retention analysis with event pairs and custom buckets
- [Flow Queries](query-flows.md) — Typed flow path analysis with steps, directions, and graph output
- [Live Analytics](live-analytics.md) — Legacy query methods (segmentation, funnels, retention)
- [Data Discovery](discovery.md) — Explore events and properties before querying
- [Data Governance — Custom Properties](data-governance.md#custom-properties) — Create and manage custom properties
- [API Reference — Workspace](../api/workspace.md) — Full method signatures
- [API Reference — Types](../api/types.md) — Metric, Filter, GroupBy, CustomPropertyRef, InlineCustomProperty, QueryResult details
