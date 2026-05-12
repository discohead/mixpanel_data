# Quickstart: Retention Query

## Simple Retention Query

```python
import mixpanel_data as mp

ws = mp.Workspace()

# Weekly retention: Signup → Login
result = ws.query_retention("Signup", "Login")

# Inspect results
print(result.average)              # Average retention across all cohorts
print(result.cohorts.keys())       # Cohort dates
print(result.df.head())            # Tabular view
```

## Weekly Retention Over 90 Days

```python
result = ws.query_retention(
    "Signup", "Login",
    retention_unit="week",
    last=90,
)

# DataFrame: cohort_date | bucket | count | rate
print(result.df)
```

## Per-Event Filters

```python
from mixpanel_data import RetentionEvent, Filter

# Only organic signups, any login
result = ws.query_retention(
    RetentionEvent("Signup", filters=[Filter.equals("source", "organic")]),
    RetentionEvent("Login"),
    retention_unit="day",
)
```

## Segmented Retention

```python
# Compare retention by platform
result = ws.query_retention(
    "Signup", "Purchase",
    group_by="platform",
    retention_unit="week",
)
```

## Custom Retention Buckets

```python
# Day 1, 3, 7, 14, 30 retention
result = ws.query_retention(
    "Signup", "Login",
    retention_unit="day",
    bucket_sizes=[1, 3, 7, 14, 30],
)
```

## Trends View

```python
# Retention rate over time (line chart)
result = ws.query_retention(
    "Signup", "Login",
    mode="trends",
    unit="week",
    last=90,
)
```

## Debug / Persist

```python
# Inspect generated bookmark params
params = ws.build_retention_params("Signup", "Login")
print(params)

# Save as a Mixpanel report
from mixpanel_data import CreateBookmarkParams

ws.create_bookmark(CreateBookmarkParams(
    name="Signup → Login Retention",
    bookmark_type="retention",
    params=result.params,
))
```

## Error Handling

```python
from mixpanel_data import BookmarkValidationError

try:
    ws.query_retention("", "Login")
except BookmarkValidationError as e:
    for error in e.errors:
        print(f"[{error.code}] {error.path}: {error.message}")
    # [R1_EMPTY_BORN_EVENT] born_event: born_event must be a non-empty string
```
