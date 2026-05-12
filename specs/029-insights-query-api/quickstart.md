# Quickstart: Workspace.query()

## Simplest Query

```python
import mixpanel_data as mp

ws = mp.Workspace()
result = ws.query("Login")
print(result.df.head())
```

Returns daily Login event counts for the last 30 days.

## Common Patterns

### Unique users with custom time range

```python
result = ws.query("Login", math="unique", from_date="2024-01-01", to_date="2024-03-31", unit="week")
```

### DAU metric

```python
result = ws.query("Login", math="dau", last=90)
```

### Filtered by property

```python
from mixpanel_data import Filter

result = ws.query(
    "Purchase",
    where=[Filter.equals("country", "US"), Filter.equals("platform", "iOS")],
)
```

### Breakdown by property

```python
result = ws.query("Login", group_by="platform", last=14)
```

### Numeric property aggregation

```python
result = ws.query("Purchase", math="average", math_property="amount")
```

### Multi-metric comparison

```python
result = ws.query(["Signup", "Login", "Purchase"], math="unique")
```

### Formula-based conversion rate

```python
from mixpanel_data import Metric

result = ws.query(
    [Metric("Signup", math="unique"), Metric("Purchase", math="unique")],
    formula="(B / A) * 100",
    formula_label="Conversion Rate",
    unit="week",
)
```

### Per-user aggregation

```python
result = ws.query("Purchase", math="total", per_user="average", unit="week")
```

### Rolling average

```python
result = ws.query("Signup", math="unique", group_by="country", rolling=7, last=60)
```

### Aggregate KPI (single number)

```python
result = ws.query("Purchase", math="unique", from_date="2024-03-01", to_date="2024-03-31", mode="total")
total = result.df["count"].iloc[0]
```

### Numeric bucketed breakdown

```python
from mixpanel_data import GroupBy

result = ws.query(
    "Purchase",
    group_by=GroupBy("revenue", property_type="number", bucket_size=50, bucket_min=0, bucket_max=500),
)
```

## Saving a Query as a Report

```python
from mixpanel_data import CreateBookmarkParams

result = ws.query("Login", math="dau", group_by="platform", last=90)

ws.create_bookmark(CreateBookmarkParams(
    name="DAU by Platform (90d)",
    bookmark_type="insights",
    params=result.params,
))
```

## Debugging

Inspect the generated bookmark params:

```python
result = ws.query("Login", math="unique", last=7)
print(result.params)   # Full bookmark JSON sent to API
print(result.meta)     # Response metadata (sampling, limits)
```
