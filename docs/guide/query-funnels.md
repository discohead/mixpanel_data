# Funnel Queries

Build typed funnel conversion analysis against Mixpanel's Insights engine — define steps, exclusions, and conversion windows inline without creating saved funnels first.

!!! tip "Recommended"
    `Workspace.query_funnel()` is the typed way to run funnel analysis programmatically. It supports capabilities not available through the legacy `funnel()` method, including ad-hoc step definitions, per-step filters, exclusions, holding constant properties, and session-based conversion.

## When to Use `query_funnel()`

`query_funnel()` builds funnel bookmark params and posts them to the Insights engine. The legacy `funnel()` method queries pre-saved funnels by ID. Use `query_funnel()` when you need any of the capabilities in the right column:

| Capability | Legacy `funnel()` | `query_funnel()` |
|---|---|---|
| Query a saved funnel by ID | `funnel(funnel_id=123)` | Use `query_saved_report()` |
| Define steps inline | Not available | `["Signup", "Purchase"]` |
| Per-step filters | Not available | `FunnelStep("Purchase", filters=[...])` |
| Per-step labels | Not available | `FunnelStep("Purchase", label="High-Value")` |
| Exclusions between steps | Not available | `exclusions=["Logout"]` |
| Hold properties constant | Not available | `holding_constant=["platform"]` |
| Conversion window control | Not available | `conversion_window=7, conversion_window_unit="day"` |
| Session-based conversion | Not available | `conversion_window_unit="session"` |
| Step ordering modes | Not available | `order="any"` |
| Property breakdowns | `on="country"` | `group_by="country"` |
| Save query as a report | N/A | `result.params` → `create_bookmark()` |

Use the legacy `funnel()` when:

- You have an existing saved funnel in Mixpanel and just need its results → `funnel(funnel_id=123)`
- You need simple segmentation of a saved funnel → `funnel(funnel_id=123, on="country")`

## Getting Started

The simplest possible funnel — two steps with default settings (14-day conversion window, last 30 days):

```python
import mixpanel_headless as mp

ws = mp.Workspace()

result = ws.query_funnel(["Signup", "Purchase"])
print(f"Conversion: {result.overall_conversion_rate:.1%}")
# Conversion: 12.3%

print(result.df)
#   step     event  count  step_conv_ratio  overall_conv_ratio  avg_time  avg_time_from_start
# 1     1    Signup   1000             1.00                1.00       0.0                  0.0
# 2     2  Purchase    123             0.12                0.12    3600.0               3600.0
```

Add a conversion window and time range:

```python
# 7-day conversion window over the last 90 days
result = ws.query_funnel(
    ["Signup", "Add to Cart", "Checkout", "Purchase"],
    conversion_window=7,
    last=90,
)
```

## Steps

### Plain Strings

The simplest way to define steps — pass event names as strings:

```python
result = ws.query_funnel(["Signup", "Add to Cart", "Purchase"])
```

At least 2 steps are required, up to a maximum of 100.

### The `FunnelStep` Class

For per-step configuration, use `FunnelStep` objects:

```python
from mixpanel_headless import FunnelStep, Filter

result = ws.query_funnel([
    FunnelStep("Signup"),
    FunnelStep(
        "Purchase",
        label="High-Value Purchase",
        filters=[Filter.greater_than("amount", 50)],
    ),
])
```

`FunnelStep` fields:

| Field | Type | Default | Description |
|---|---|---|---|
| `event` | `str` | (required) | Mixpanel event name |
| `label` | `str \| None` | `None` | Display label (defaults to event name) |
| `filters` | `list[Filter] \| None` | `None` | Per-step filter conditions |
| `filters_combinator` | `"all" \| "any"` | `"all"` | How per-step filters combine (AND/OR) |
| `order` | `"loose" \| "any" \| None` | `None` | Per-step ordering override |

Plain strings and `FunnelStep` objects can be mixed freely:

```python
result = ws.query_funnel([
    "Signup",  # plain string — no filters needed
    FunnelStep("Purchase", filters=[Filter.greater_than("amount", 50)]),
])
```

### Per-Step Filters

Apply filters to individual steps using `FunnelStep.filters`. These restrict which events count for that specific step:

```python
from mixpanel_headless import FunnelStep, Filter

result = ws.query_funnel([
    FunnelStep("Signup", filters=[Filter.equals("source", "organic")]),
    FunnelStep("Purchase", filters=[
        Filter.equals("country", "US"),
        Filter.greater_than("amount", 25),
    ]),
])
```

By default, multiple per-step filters combine with AND logic. Use `filters_combinator="any"` for OR logic:

```python
result = ws.query_funnel([
    "Signup",
    FunnelStep(
        "Purchase",
        filters=[
            Filter.equals("country", "US"),
            Filter.equals("country", "CA"),
        ],
        filters_combinator="any",  # match US OR CA
    ),
])
```

See [Insights Queries — Filters](query.md#filters) for the full list of `Filter` factory methods.

## Conversion Window

Control how long users have to complete the funnel:

```python
# 7 days (default unit is "day")
result = ws.query_funnel(["Signup", "Purchase"], conversion_window=7)

# 2 hours
result = ws.query_funnel(["View", "Click"], conversion_window=2, conversion_window_unit="hour")

# 4 weeks
result = ws.query_funnel(["Signup", "Purchase"], conversion_window=4, conversion_window_unit="week")
```

### Conversion Window Units

| Unit | Max value | Description |
|---|---|---|
| `"second"` | 31,708,800 | Seconds (min: 2) |
| `"minute"` | 528,480 | Minutes |
| `"hour"` | 8,808 | Hours |
| `"day"` (default) | 367 | Days |
| `"week"` | 52 | Weeks |
| `"month"` | 12 | Months |
| `"session"` | 12 | Sessions |

All maximum values correspond to approximately 366 days.

### Session-Based Conversion

Use `conversion_window_unit="session"` to count conversions within a single Mixpanel session:

```python
# Users must complete all steps within one session
result = ws.query_funnel(
    ["View Product", "Add to Cart", "Purchase"],
    conversion_window=1,
    conversion_window_unit="session",
    math="conversion_rate_session",
)
```

!!! note
    Session-based conversion requires `conversion_window=1` and `math="conversion_rate_session"`.

## Ordering

The `order` parameter controls how steps must be completed:

| Order | Behavior |
|---|---|
| `"loose"` (default) | Steps must happen in the specified order, but other events can occur between them |
| `"any"` | Steps can happen in any order within the conversion window |

```python
# Steps in any order
result = ws.query_funnel(
    ["Feature A Used", "Feature B Used", "Feature C Used"],
    order="any",
    conversion_window=30,
)
```

### Per-Step Order Override

When the top-level `order` is `"any"`, individual steps can override to `"loose"`:

```python
result = ws.query_funnel(
    [
        FunnelStep("Signup"),  # must come first (loose)
        FunnelStep("Feature A", order="any"),
        FunnelStep("Feature B", order="any"),
    ],
    order="any",
)
```

## Aggregation

The `math` parameter controls what metric is computed. Default: `"conversion_rate_unique"`.

### Conversion Rates

| Math type | What it measures |
|---|---|
| `"conversion_rate_unique"` (default) | Unique-user conversion rate |
| `"conversion_rate_total"` | Total-event conversion rate |
| `"conversion_rate_session"` | Session-based conversion rate |

```python
# Total-event conversion (counts all events, not just unique users)
result = ws.query_funnel(
    ["View", "Purchase"],
    math="conversion_rate_total",
)
```

### Raw Counts

| Math type | What it counts |
|---|---|
| `"unique"` | Unique users per step |
| `"total"` | Total event count per step |

```python
# Raw unique user counts at each step
result = ws.query_funnel(["Signup", "Purchase"], math="unique")
```

### Property Aggregation

| Math type | Aggregation |
|---|---|
| `"average"` | Mean of a numeric property per step |
| `"median"` | Median value |
| `"min"` / `"max"` | Extremes |
| `"p25"` / `"p75"` / `"p90"` / `"p99"` | Percentiles |
| `"histogram"` | Distribution of a numeric property per step |

```python
# Average purchase amount at each step
result = ws.query_funnel(
    ["Signup", "Purchase"],
    math="average",
    math_property="amount",
)

# Distribution of purchase amounts at each funnel step
result = ws.query_funnel(
    ["Browse", "Add to Cart", "Purchase"],
    math="histogram",
    math_property="amount",
)
```

## Filters

### Global Filters

Apply filters across all steps with `where=`:

```python
from mixpanel_headless import Filter

# Filter the entire funnel
result = ws.query_funnel(
    ["Signup", "Purchase"],
    where=Filter.equals("country", "US"),
)

# Multiple global filters (AND logic)
result = ws.query_funnel(
    ["Signup", "Purchase"],
    where=[
        Filter.equals("platform", "web"),
        Filter.is_true("is_premium"),
    ],
)
```

Global filters apply to all steps in the funnel. For step-specific filtering, use `FunnelStep.filters` (see [Steps — Per-Step Filters](#per-step-filters)).

See [Insights Queries — Available Filter Methods](query.md#available-filter-methods) for the complete filter reference.

### Cohort Filters

Restrict the funnel to users in a cohort — saved or inline:

```python
from mixpanel_headless import Filter, CohortCriteria, CohortDefinition

# Saved cohort
result = ws.query_funnel(
    ["Signup", "Purchase"],
    where=Filter.in_cohort(123, "Power Users"),
)

# Inline cohort — no pre-saved cohort needed
active_users = CohortDefinition(
    CohortCriteria.did_event("Login", at_least=5, within_days=7)
)
result = ws.query_funnel(
    ["Signup", "Purchase"],
    where=Filter.in_cohort(active_users, name="Active Users"),
)
```

See [Insights Queries — Cohort Filters](query.md#cohort-filters) for the full cohort filter reference.

### Custom Property Filters

Use saved or inline custom properties in funnel filters:

```python
from mixpanel_headless import Filter, CustomPropertyRef

result = ws.query_funnel(
    ["Signup", "Purchase"],
    where=Filter.greater_than(property=CustomPropertyRef(42), value=100),
)
```

!!! warning
    Custom property filters in funnel `where=` may cause server errors due to a known Mixpanel API bug. Custom property breakdowns and measurement work reliably.

See [Insights Queries — Custom Properties in Queries](query.md#custom-properties-in-queries) for `InlineCustomProperty`, validation rules, and full options.

## Breakdowns

Break down funnel results by property values with `group_by`:

```python
from mixpanel_headless import GroupBy

# Simple string breakdown
result = ws.query_funnel(["Signup", "Purchase"], group_by="platform")

# Multiple breakdowns
result = ws.query_funnel(["Signup", "Purchase"], group_by=["country", "platform"])

# Numeric bucketing
result = ws.query_funnel(
    ["Signup", "Purchase"],
    group_by=GroupBy("amount", property_type="number", bucket_size=50),
)
```

### Cohort Breakdowns

Segment funnel results by cohort membership:

```python
from mixpanel_headless import CohortBreakdown

# Compare power users vs. everyone else through the funnel
result = ws.query_funnel(
    ["Signup", "Purchase"],
    group_by=CohortBreakdown(123, "Power Users"),
)
```

See [Insights Queries — Cohort Breakdowns](query.md#cohort-breakdowns) for inline definitions and options.

### Custom Property Breakdowns

Break down funnel results by a saved or inline custom property:

```python
from mixpanel_headless import GroupBy, InlineCustomProperty

result = ws.query_funnel(
    ["Signup", "Purchase"],
    group_by=GroupBy(
        property=InlineCustomProperty.numeric("A * B", A="price", B="quantity"),
        property_type="number",
        bucket_size=50,
    ),
)
```

See [Insights Queries — Custom Properties in Queries](query.md#custom-properties-in-queries) for `CustomPropertyRef` and full options.

See [Insights Queries — Breakdowns](query.md#breakdowns) for the full `GroupBy` reference.

## Exclusions

Exclude users who perform specific events between funnel steps. Users who trigger an excluded event within the specified step range are removed from the funnel.

### String Shorthand

Pass event names as strings to exclude them between all steps:

```python
# Exclude users who log out anywhere in the funnel
result = ws.query_funnel(
    ["Signup", "Add to Cart", "Purchase"],
    exclusions=["Logout"],
)
```

### The `Exclusion` Class

For targeted exclusion between specific steps, use `Exclusion` objects:

```python
from mixpanel_headless import Exclusion

result = ws.query_funnel(
    ["Signup", "Add to Cart", "Checkout", "Purchase"],
    exclusions=[
        Exclusion("Logout"),  # between all steps (same as string)
        Exclusion("Refund", from_step=2, to_step=3),  # only between Checkout and Purchase
    ],
)
```

`Exclusion` fields:

| Field | Type | Default | Description |
|---|---|---|---|
| `event` | `str` | (required) | Event name to exclude |
| `from_step` | `int` | `0` | Start of exclusion range (0-indexed, inclusive) |
| `to_step` | `int \| None` | `None` | End of exclusion range (0-indexed, inclusive). `None` = last step |

!!! note
    Step indices are 0-based. For a 3-step funnel `["A", "B", "C"]`, `from_step=0, to_step=2` covers the entire funnel.

## Holding Constant

Hold properties constant across all funnel steps. Only users whose property value is the same at every step are counted as converting.

### String Shorthand

Pass property names as strings:

```python
# Only count conversions where platform is the same at every step
result = ws.query_funnel(
    ["Signup", "Purchase"],
    holding_constant="platform",
)

# Multiple properties
result = ws.query_funnel(
    ["Signup", "Purchase"],
    holding_constant=["platform", "country"],
)
```

### The `HoldingConstant` Class

For user-profile properties, use `HoldingConstant` objects:

```python
from mixpanel_headless import HoldingConstant

result = ws.query_funnel(
    ["Signup", "Purchase"],
    holding_constant=[
        HoldingConstant("platform"),  # event property (default)
        HoldingConstant("plan_tier", resource_type="people"),  # user-profile property
    ],
)
```

`HoldingConstant` fields:

| Field | Type | Default | Description |
|---|---|---|---|
| `property` | `str` | (required) | Property name to hold constant |
| `resource_type` | `"events" \| "people"` | `"events"` | Whether this is an event or user-profile property |

!!! note
    Maximum 3 holding constant properties per query.

## Time Ranges

### Relative (Default)

By default, `query_funnel()` returns the last 30 days. Customize with `last` (always in days) and `unit` (aggregation granularity):

```python
# Last 7 days
result = ws.query_funnel(["Signup", "Purchase"], last=7)

# Last 84 days (~12 weeks), weekly granularity
result = ws.query_funnel(["Signup", "Purchase"], last=84, unit="week")

# Last 180 days (~6 months), monthly granularity
result = ws.query_funnel(["Signup", "Purchase"], last=180, unit="month")
```

### Absolute

Specify explicit start and end dates:

```python
# Q1 2025
result = ws.query_funnel(
    ["Signup", "Purchase"],
    from_date="2025-01-01",
    to_date="2025-03-31",
)
```

Dates must be in `YYYY-MM-DD` format.

## Display Modes

The `mode` parameter controls result presentation:

| Mode | Description | Use case |
|---|---|---|
| `"steps"` (default) | Step-level conversion data | Standard funnel analysis |
| `"trends"` | Conversion over time | Track funnel performance trends |
| `"table"` | Tabular breakdown | Detailed segment comparison |

```python
# Conversion trend over time
result = ws.query_funnel(
    ["Signup", "Purchase"],
    mode="trends",
    last=90,
    unit="week",
)
```

## Reentry Mode

Control how users re-enter the funnel after conversion using the `reentry_mode` parameter:

| Mode | Behavior |
|---|---|
| `"default"` | Server default reentry behavior |
| `"basic"` | Users can re-enter after their conversion window expires |
| `"aggressive"` | Users can re-enter as soon as they convert |
| `"optimized"` | Server-optimized reentry (best for most use cases) |

```python
# Allow aggressive re-entry for repeat purchase funnels
result = ws.query_funnel(
    ["Browse", "Add to Cart", "Purchase"],
    reentry_mode="aggressive",
    last=30,
)
```

!!! note
    Reentry mode only matters for funnels where the same user can convert multiple times.

## Period-over-Period Comparison

Compare funnel conversion against a previous period using `TimeComparison`:

```python
from mixpanel_headless import TimeComparison

# Compare this week's funnel against last week
result = ws.query_funnel(
    ["Signup", "Activate", "Purchase"],
    time_comparison=TimeComparison.relative("week"),
    last=7,
)
```

See [Insights > Period-over-Period Comparison](query.md#period-over-period-comparison) for all `TimeComparison` factory methods.

## Data Group Scoping

```python
# Scope funnel to a data group
result = ws.query_funnel(["Signup", "Purchase"], data_group_id=42)
```

## Working with Results

### `FunnelQueryResult`

`query_funnel()` returns a `FunnelQueryResult` with:

```python
result = ws.query_funnel(["Signup", "Add to Cart", "Purchase"])

# Overall conversion rate (first to last step)
result.overall_conversion_rate  # 0.12 (12%)

# DataFrame (lazy, cached)
result.df
#   step       event  count  step_conv_ratio  overall_conv_ratio  avg_time  avg_time_from_start
# 1     1      Signup   1000             1.00                1.00       0.0                  0.0
# 2     2  Add to Cart    450             0.45                0.45    1800.0               1800.0
# 3     3    Purchase    120             0.27                0.12    3600.0               5400.0

# Raw step data
result.steps_data       # list of dicts with step-level metrics
result.series           # raw API series data

# Time range
result.from_date        # "2025-03-01"
result.to_date          # "2025-03-31"

# Metadata
result.computed_at      # "2025-03-31T12:00:00.000000+00:00"
result.meta             # {"sampling_factor": 1.0, ...}

# Generated bookmark params (for debugging or persistence)
result.params           # dict — the full bookmark JSON sent to API
```

### DataFrame Structure

The DataFrame has one row per funnel step:

| Column | Description |
|---|---|
| `step` | Step number (1-indexed) |
| `event` | Event name |
| `count` | Number of users/events reaching this step |
| `step_conv_ratio` | Conversion rate from previous step (1.0 for first step) |
| `overall_conv_ratio` | Conversion rate from first step |
| `avg_time` | Average time from previous step (seconds) |
| `avg_time_from_start` | Average time from first step (seconds) |

### Persisting as a Saved Report

The generated bookmark params can be saved as a Mixpanel report:

```python
from mixpanel_headless import CreateBookmarkParams

result = ws.query_funnel(["Signup", "Purchase"], conversion_window=7, last=90)

ws.create_bookmark(CreateBookmarkParams(
    name="Signup → Purchase Funnel (7d window)",
    bookmark_type="funnels",
    params=result.params,
))
```

### Debugging

Inspect `result.params` to see the exact bookmark JSON sent to the API:

```python
import json

result = ws.query_funnel(["Signup", "Purchase"])
print(json.dumps(result.params, indent=2))
```

## Validation

`query_funnel()` validates all parameter combinations **before** making an API call and raises `BookmarkValidationError` with descriptive messages:

| Rule | Error code | Error message |
|---|---|---|
| Fewer than 2 steps | `F1_MIN_STEPS` | At least 2 steps are required |
| More than 100 steps | `F1_MAX_STEPS` | Maximum 100 steps allowed |
| Empty step event name | `F2_EMPTY_STEP_EVENT` | Step event name must be a non-empty string |
| Control chars in step name | `F2_CONTROL_CHAR_STEP_EVENT` | Step event name contains control characters |
| Non-positive conversion window | `F3_CONVERSION_WINDOW_POSITIVE` | conversion_window must be a positive integer |
| Window exceeds max for unit | `F3_CONVERSION_WINDOW_MAX` | conversion_window exceeds maximum for unit |
| Empty exclusion event | `F4_EMPTY_EXCLUSION_EVENT` | Exclusion event name must be non-empty |
| Exclusion step order invalid | `F4_EXCLUSION_STEP_ORDER` | to_step must be > from_step |
| Exclusion step out of bounds | `F4_EXCLUSION_STEP_BOUNDS` | Step index exceeds step count |
| Invalid conversion window unit | `F7_INVALID_WINDOW_UNIT` | Must be one of: second, minute, ... |
| Second unit requires window >= 2 | `F7_SECOND_MIN_WINDOW` | Must be at least 2 for seconds |
| More than 3 holding constant | `F8_MAX_HOLDING_CONSTANT` | Maximum 3 holding_constant properties |
| Session math without session unit | `F9_SESSION_MATH_REQUIRES_SESSION_WINDOW` | Requires conversion_window_unit='session' |
| Property math missing math_property | `F10_MATH_MISSING_PROPERTY` | Property-aggregation math types require math_property |
| Non-property math given math_property | `F11_MATH_REJECTS_PROPERTY` | Count/rate math types don't accept math_property |

## Complete Examples

### E-Commerce Funnel

```python
import mixpanel_headless as mp
from mixpanel_headless import FunnelStep, Filter, Exclusion, HoldingConstant

ws = mp.Workspace()

# Full purchase funnel with exclusions and filters
result = ws.query_funnel(
    [
        FunnelStep("View Product"),
        FunnelStep("Add to Cart"),
        FunnelStep(
            "Purchase",
            filters=[Filter.greater_than("amount", 0)],
        ),
    ],
    conversion_window=7,
    exclusions=[Exclusion("Remove from Cart", from_step=1, to_step=2)],
    holding_constant="platform",
    where=Filter.equals("country", "US"),
    group_by="platform",
    last=90,
)

print(f"Overall conversion: {result.overall_conversion_rate:.1%}")
print(result.df)
```

### Onboarding Funnel

```python
# Track user onboarding completion
result = ws.query_funnel(
    [
        "Create Account",
        "Verify Email",
        "Complete Profile",
        "First Action",
    ],
    conversion_window=3,
    conversion_window_unit="day",
    order="loose",
    math="conversion_rate_unique",
    last=30,
    unit="week",
    mode="trends",  # track onboarding trends over time
)

# Identify the biggest drop-off point
for step_data in result.steps_data:
    print(f"{step_data['event']}: {step_data['step_conv_ratio']:.0%} step conversion")
```

## Generating Params Without Querying

Use `build_funnel_params()` to generate bookmark params without making an API call — useful for debugging, inspecting the generated JSON, or saving queries as reports:

```python
# Same arguments as query_funnel(), returns dict instead of FunnelQueryResult
params = ws.build_funnel_params(
    ["Signup", "Add to Cart", "Purchase"],
    conversion_window=7,
    exclusions=["Logout"],
    holding_constant="platform",
    last=90,
)

import json
print(json.dumps(params, indent=2))  # inspect the generated bookmark JSON

# Save as a report directly from params
from mixpanel_headless import CreateBookmarkParams

ws.create_bookmark(CreateBookmarkParams(
    name="Purchase Funnel (7d)",
    bookmark_type="funnels",
    params=params,
))
```

## Next Steps

- [Insights Queries](query.md) — Typed analytics with DAU, formulas, filters, and breakdowns
- [Retention Queries](query-retention.md) — Typed retention analysis with event pairs and custom buckets
- [Flow Queries](query-flows.md) — Typed flow path analysis with steps, directions, and graph output
- [Live Analytics — Funnels](live-analytics.md#funnels) — Legacy funnel method (saved funnels by ID)
- [API Reference — Workspace](../api/workspace.md) — Full method signatures
- [API Reference — Types](../api/types.md) — FunnelStep, Exclusion, HoldingConstant, FunnelQueryResult details
