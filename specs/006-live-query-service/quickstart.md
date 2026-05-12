# Quickstart: Live Query Service

**Date**: 2025-12-22
**Feature**: 006-live-query-service

## Overview

The `LiveQueryService` provides a simple interface for running analytics queries against Mixpanel's Query API. It transforms raw API responses into typed result objects with DataFrame support.

---

## Basic Usage

### Setup

```python
from mixpanel_data._internal.api_client import MixpanelAPIClient
from mixpanel_data._internal.services.live_query import LiveQueryService
from mixpanel_data._internal.config import Credentials
from pydantic import SecretStr

# Create credentials
credentials = Credentials(
    username="your_service_account",
    secret=SecretStr("your_secret"),
    project_id="12345",
    region="us",
)

# Create API client and service
client = MixpanelAPIClient(credentials)
with client:
    live_query = LiveQueryService(client)

    # Now you can run queries...
```

---

## Segmentation Queries

Analyze event counts over time, optionally segmented by a property.

### Basic Event Counts

```python
# Count "Sign Up" events per day for the last 30 days
result = live_query.segmentation(
    event="Sign Up",
    from_date="2024-01-01",
    to_date="2024-01-31",
)

print(f"Total signups: {result.total}")
print(f"Daily breakdown: {result.series}")

# Convert to DataFrame for analysis
df = result.df
print(df.head())
#         date segment  count
# 0 2024-01-01   total    147
# 1 2024-01-02   total    152
```

### Segmented by Property

```python
# Segment signups by country
result = live_query.segmentation(
    event="Sign Up",
    from_date="2024-01-01",
    to_date="2024-01-31",
    on='properties["country"]',
)

print(f"Segmented by: {result.segment_property}")
df = result.df
print(df.head())
#         date segment  count
# 0 2024-01-01      US    100
# 1 2024-01-01      CA     25
# 2 2024-01-01      GB     22
```

### With Filtering

```python
# Only count signups from mobile users
result = live_query.segmentation(
    event="Sign Up",
    from_date="2024-01-01",
    to_date="2024-01-31",
    where='properties["platform"] == "mobile"',
)
```

### Weekly Aggregation

```python
# Aggregate by week instead of day
result = live_query.segmentation(
    event="Sign Up",
    from_date="2024-01-01",
    to_date="2024-03-31",
    unit="week",
)
```

---

## Funnel Analysis

Analyze conversion through multi-step user flows.

### Query a Saved Funnel

```python
# Query funnel with ID 12345
result = live_query.funnel(
    funnel_id=12345,
    from_date="2024-01-01",
    to_date="2024-01-31",
)

print(f"Overall conversion: {result.conversion_rate:.1%}")

# Examine each step
for i, step in enumerate(result.steps, 1):
    print(f"Step {i}: {step.event}")
    print(f"  Users: {step.count}")
    print(f"  Conversion from prev: {step.conversion_rate:.1%}")

# Convert to DataFrame
df = result.df
print(df)
#    step        event  count  conversion_rate
# 0     1    App Open  32688             1.00
# 1     2 Game Played  20524             0.63
```

---

## Retention Analysis

Analyze cohort-based user retention.

### Basic Retention Query

```python
# Users who signed up and returned to make a purchase
result = live_query.retention(
    born_event="Sign Up",
    return_event="Purchase",
    from_date="2024-01-01",
    to_date="2024-01-31",
)

print(f"Born event: {result.born_event}")
print(f"Return event: {result.return_event}")

# Examine each cohort
for cohort in result.cohorts:
    print(f"Cohort {cohort.date}: {cohort.size} users")
    print(f"  Retention: {[f'{r:.0%}' for r in cohort.retention]}")

# Convert to DataFrame (cohort rows, period columns)
df = result.df
print(df)
#   cohort_date  cohort_size  period_0  period_1  period_2
# 0  2024-01-01           10      0.90      0.70      0.60
# 1  2024-01-02            9      0.89      0.56      0.44
```

### With Filters

```python
# Only users who signed up on mobile and purchased on web
result = live_query.retention(
    born_event="Sign Up",
    return_event="Purchase",
    from_date="2024-01-01",
    to_date="2024-01-31",
    born_where='properties["platform"] == "mobile"',
    return_where='properties["platform"] == "web"',
)
```

### Custom Intervals

```python
# Weekly retention over 8 weeks
result = live_query.retention(
    born_event="Sign Up",
    return_event="Any Event",
    from_date="2024-01-01",
    to_date="2024-03-31",
    unit="week",
    interval=1,
    interval_count=8,
)
```

---

## JQL Queries

Execute custom JavaScript queries.

### Basic JQL Query

```python
# Count events by name
result = live_query.jql(
    script='''
    function main() {
      return Events({
        from_date: params.from,
        to_date: params.to
      })
      .groupBy(["name"], mixpanel.reducer.count())
    }
    ''',
    params={"from": "2024-01-01", "to": "2024-01-31"},
)

# Access raw results
print(result.raw)
# [{"key": ["Sign Up"], "value": 1523}, {"key": ["Purchase"], "value": 847}]

# Convert to DataFrame
df = result.df
print(df)
#           key  value
# 0    [Sign Up]   1523
# 1   [Purchase]    847
```

---

## Error Handling

```python
from mixpanel_data.exceptions import (
    AuthenticationError,
    RateLimitError,
    QueryError,
)

try:
    result = live_query.segmentation(
        event="Sign Up",
        from_date="2024-01-01",
        to_date="2024-01-31",
    )
except AuthenticationError as e:
    print(f"Invalid credentials: {e}")
except RateLimitError as e:
    print(f"Rate limit exceeded: {e}")
    # Wait and retry
except QueryError as e:
    print(f"Query failed: {e}")
    # Check query parameters
```

---

## Integration with Workspace (Future)

When the `Workspace` facade is implemented (Phase 007), usage will be simplified:

```python
from mixpanel_data import Workspace

# Workspace handles credential resolution and client setup
with Workspace(account="my_account", db="analytics.db") as ws:
    # Live query access
    result = ws.segmentation(
        event="Sign Up",
        from_date="2024-01-01",
        to_date="2024-01-31",
    )

    # Or fetch to local storage for repeated queries
    ws.fetch_events(
        name="jan_signups",
        from_date="2024-01-01",
        to_date="2024-01-31",
    )
    df = ws.query("SELECT * FROM jan_signups WHERE country = 'US'")
```

---

## Best Practices

1. **Use context managers**: Always use `with client:` to ensure proper cleanup.

2. **Choose the right path**:
   - Use live queries for quick, one-off analysis
   - Use fetch + local storage for repeated queries (saves API calls)

3. **Handle rate limits**: Mixpanel allows 60 queries/hour. Plan accordingly.

4. **Use DataFrames for analysis**: All result types have a `.df` property for easy manipulation.

5. **Filter at the API level**: Use `where` clauses to reduce data transfer.
