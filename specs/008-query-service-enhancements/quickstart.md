# Quickstart: Query Service Enhancements

**Feature**: 008-query-service-enhancements
**Date**: 2024-12-23

## Overview

This phase adds 6 new methods to the LiveQueryService for additional Mixpanel Query API capabilities.

---

## Usage Examples

### Activity Feed - User Event History

```python
from mixpanel_data._internal.api_client import MixpanelAPIClient
from mixpanel_data._internal.config import ConfigManager
from mixpanel_data._internal.services.live_query import LiveQueryService

config = ConfigManager()
credentials = config.resolve_credentials()

with MixpanelAPIClient(credentials) as client:
    live_query = LiveQueryService(client)

    # Query activity for specific users
    result = live_query.activity_feed(
        distinct_ids=["user_123", "user_456"],
        from_date="2024-01-01",
        to_date="2024-01-31",
    )

    print(f"Found {len(result.events)} events")
    for event in result.events[:5]:
        print(f"  {event.time}: {event.event}")

    # Convert to DataFrame for analysis
    df = result.df
    print(df.head())
```

---

### Insights - Saved Report Data

```python
# Query a saved Insights report by its bookmark ID
result = live_query.insights(bookmark_id=12345678)

print(f"Report computed at: {result.computed_at}")
print(f"Date range: {result.from_date} to {result.to_date}")

# Access time-series data
for event_name, series in result.series.items():
    print(f"\n{event_name}:")
    for date, count in series.items():
        print(f"  {date}: {count}")

# Convert to DataFrame
df = result.df
print(df.pivot(index="date", columns="event", values="count"))
```

---

### Frequency - Engagement Depth Analysis

```python
# Analyze how frequently users perform events
result = live_query.frequency(
    from_date="2024-01-01",
    to_date="2024-01-07",
    unit="day",
    addiction_unit="hour",
    event="App Open",
)

# Interpret frequency distribution
for date, counts in result.data.items():
    print(f"\n{date}:")
    print(f"  Users active 1+ hours: {counts[0]}")
    print(f"  Users active 2+ hours: {counts[1]}")
    print(f"  Users active 3+ hours: {counts[2]}")

# Convert to DataFrame with period columns
df = result.df
print(df)
```

---

### Numeric Bucketing - Value Distributions

```python
# Bucket events by numeric property ranges
result = live_query.segmentation_numeric(
    event="Purchase",
    from_date="2024-01-01",
    to_date="2024-01-31",
    on='properties["amount"]',
    type="general",
)

# See bucket distributions
for bucket, series in result.series.items():
    total = sum(series.values())
    print(f"{bucket}: {total} events")

# Convert to DataFrame
df = result.df
print(df.groupby("bucket")["count"].sum().sort_values(ascending=False))
```

---

### Numeric Sum - Revenue Totals

```python
# Calculate daily revenue totals
result = live_query.segmentation_sum(
    event="Purchase",
    from_date="2024-01-01",
    to_date="2024-01-31",
    on='properties["amount"]',
)

# View daily sums
total_revenue = 0
for date, amount in sorted(result.results.items()):
    print(f"{date}: ${amount:,.2f}")
    total_revenue += amount

print(f"\nTotal: ${total_revenue:,.2f}")

# Convert to DataFrame
df = result.df
print(f"Average daily revenue: ${df['sum'].mean():,.2f}")
```

---

### Numeric Average - Mean Values

```python
# Calculate average order value per day
result = live_query.segmentation_average(
    event="Purchase",
    from_date="2024-01-01",
    to_date="2024-01-31",
    on='properties["amount"]',
)

# View daily averages
for date, avg in sorted(result.results.items()):
    print(f"{date}: ${avg:.2f} avg")

# Convert to DataFrame
df = result.df
print(f"Overall average: ${df['average'].mean():.2f}")
```

---

## Result Type Reference

| Method | Result Type | DataFrame Columns |
|--------|-------------|-------------------|
| `activity_feed()` | `ActivityFeedResult` | event, time, distinct_id, + properties |
| `insights()` | `InsightsResult` | date, event, count |
| `frequency()` | `FrequencyResult` | date, period_1, period_2, ... |
| `segmentation_numeric()` | `NumericBucketResult` | date, bucket, count |
| `segmentation_sum()` | `NumericSumResult` | date, sum |
| `segmentation_average()` | `NumericAverageResult` | date, average |

---

## Common Patterns

### Filtering with WHERE

```python
# All methods with 'where' parameter support filter expressions
result = live_query.segmentation_sum(
    event="Purchase",
    from_date="2024-01-01",
    to_date="2024-01-31",
    on='properties["amount"]',
    where='properties["country"] == "US"',  # Filter to US only
)
```

### Hourly Granularity

```python
# Use unit="hour" for finer granularity
result = live_query.segmentation_sum(
    event="Purchase",
    from_date="2024-01-01",
    to_date="2024-01-01",  # Single day
    on='properties["amount"]',
    unit="hour",  # Hourly breakdown
)
```

### JSON Serialization

```python
# All results support to_dict() for JSON output
result = live_query.activity_feed(["user_123"])
json_data = result.to_dict()
print(json.dumps(json_data, indent=2))
```

---

## Error Handling

```python
from mixpanel_data.exceptions import (
    AuthenticationError,
    QueryError,
    RateLimitError,
)

try:
    result = live_query.insights(bookmark_id=99999999)
except AuthenticationError:
    print("Check your credentials")
except QueryError as e:
    print(f"Invalid request: {e}")
except RateLimitError as e:
    print(f"Rate limited, retry after {e.retry_after}s")
```
