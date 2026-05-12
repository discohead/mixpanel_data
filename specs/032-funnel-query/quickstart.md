# Quickstart: Funnel Query

## Basic Usage

```python
import mixpanel_data as mp

ws = mp.Workspace()

# Simplest funnel — two event names
result = ws.query_funnel(["Signup", "Purchase"])
print(result.overall_conversion_rate)  # e.g., 0.12
print(result.df)
#   step  event     count  step_conv_ratio  overall_conv_ratio  avg_time  avg_time_from_start
# 0    1  Signup     1000             1.00                1.00       0.0                  0.0
# 1    2  Purchase    120             0.12                0.12   86400.0              86400.0
```

## Multi-Step Funnel with Configuration

```python
result = ws.query_funnel(
    ["Signup", "Add to Cart", "Checkout", "Purchase"],
    conversion_window=7,
    conversion_window_unit="day",
    order="loose",
    last=90,
)
```

## Per-Step Filters

```python
from mixpanel_data import FunnelStep, Filter

result = ws.query_funnel([
    FunnelStep("Signup"),
    FunnelStep("Purchase",
               label="High-Value Purchase",
               filters=[Filter.greater_than("amount", 50)]),
])
```

## Segmented Funnel

```python
result = ws.query_funnel(
    ["Signup", "Purchase"],
    group_by="platform",
    where=[Filter.equals("country", "US")],
)
```

## Exclusions and Holding Constant

```python
from mixpanel_data import Exclusion, HoldingConstant

result = ws.query_funnel(
    ["Signup", "Add to Cart", "Purchase"],
    exclusions=["Logout", Exclusion("Refund", from_step=1, to_step=2)],
    holding_constant="platform",
)
```

## Inspect Without Executing

```python
params = ws.build_funnel_params(["Signup", "Purchase"])
print(params)  # Bookmark JSON dict — no API call made
```

## Persist as Saved Report

```python
from mixpanel_data.types import CreateBookmarkParams

result = ws.query_funnel(["Signup", "Purchase"])
ws.create_bookmark(CreateBookmarkParams(
    name="Signup → Purchase Funnel",
    bookmark_type="funnels",
    params=result.params,
))
```
