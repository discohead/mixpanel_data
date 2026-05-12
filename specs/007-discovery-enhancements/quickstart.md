# Quickstart: Discovery & Query API Enhancements

**Phase**: 1 (Design)
**Created**: 2025-12-23
**Status**: Complete

---

## Overview

This guide shows how to use the 5 new capabilities added by this feature.

---

## Setup

```python
from mixpanel_data import Workspace

# Connect to your Mixpanel project
ws = Workspace()  # Uses default credentials from ~/.mp/config.toml
```

---

## 1. Discover Available Funnels

Find funnel IDs before running funnel queries.

```python
# List all funnels in the project
funnels = ws.discovery.list_funnels()

for funnel in funnels:
    print(f"{funnel.name}: {funnel.funnel_id}")

# Output:
# Checkout Funnel: 12345
# Onboarding Funnel: 12346
# Signup Funnel: 12347

# Use funnel_id with funnel queries
result = ws.live_query.funnel(
    funnel_id=funnels[0].funnel_id,
    from_date="2024-01-01",
    to_date="2024-01-31",
)
print(f"Conversion rate: {result.conversion_rate:.1%}")
```

---

## 2. Discover Available Cohorts

Find cohort IDs for profile filtering.

```python
# List all cohorts in the project
cohorts = ws.discovery.list_cohorts()

for cohort in cohorts:
    print(f"{cohort.name}: {cohort.id} ({cohort.count} users)")
    if cohort.description:
        print(f"  Description: {cohort.description}")

# Output:
# Active Users: 1001 (15000 users)
#   Description: Users active in the last 30 days
# Power Users: 1002 (2500 users)
#   Description: Users with 10+ sessions
# Trial Users: 1003 (8000 users)

# Check cohort visibility
visible_cohorts = [c for c in cohorts if c.is_visible]
```

---

## 3. Explore Today's Top Events

See what's happening right now.

```python
# Get today's top events
top_events = ws.discovery.list_top_events(limit=10)

for event in top_events:
    trend = "+" if event.percent_change > 0 else ""
    print(f"{event.event}: {event.count} ({trend}{event.percent_change:.1%} vs yesterday)")

# Output:
# Page View: 15234 (+12.5% vs yesterday)
# Button Click: 8921 (-3.2% vs yesterday)
# Sign Up: 542 (+45.0% vs yesterday)

# Use different counting methods
unique_events = ws.discovery.list_top_events(type="unique", limit=5)
```

---

## 4. Analyze Multi-Event Time Series

Compare event volumes over time.

```python
# Query counts for multiple events
result = ws.live_query.event_counts(
    events=["Sign Up", "Purchase", "Add to Cart"],
    from_date="2024-01-01",
    to_date="2024-01-31",
    unit="day",
)

# Access time-series data
print(result.events)  # ["Sign Up", "Purchase", "Add to Cart"]
print(result.series["Sign Up"])  # {"2024-01-01": 150, "2024-01-02": 175, ...}

# Convert to DataFrame for analysis
df = result.df
print(df.head())
#         date       event  count
# 0 2024-01-01     Sign Up    150
# 1 2024-01-01    Purchase     45
# 2 2024-01-01  Add to Cart   320
# 3 2024-01-02     Sign Up    175
# 4 2024-01-02    Purchase     52

# Pivot for comparison
pivot = df.pivot(index="date", columns="event", values="count")
print(pivot.head())

# Serialize for output
print(result.to_dict())
```

---

## 5. Analyze Property Value Distributions

Segment metrics by property values.

```python
# Query counts by property values
result = ws.live_query.property_counts(
    event="Purchase",
    property_name="country",
    from_date="2024-01-01",
    to_date="2024-01-31",
    unit="week",
)

# Access time-series data
print(result.series["US"])  # {"2024-01-01": 450, "2024-01-08": 520, ...}
print(result.series["UK"])  # {"2024-01-01": 125, "2024-01-08": 140, ...}

# Convert to DataFrame
df = result.df
print(df.head())
#         date value  count
# 0 2024-01-01    US    450
# 1 2024-01-01    UK    125
# 2 2024-01-01    DE     85
# 3 2024-01-08    US    520
# 4 2024-01-08    UK    140

# Filter to specific values
result = ws.live_query.property_counts(
    event="Purchase",
    property_name="country",
    from_date="2024-01-01",
    to_date="2024-01-31",
    values=["US", "UK", "DE"],  # Only these countries
    limit=10,  # At most 10 values
)
```

---

## Complete Example: Funnel Discovery Workflow

```python
from mixpanel_data import Workspace

# 1. Connect
ws = Workspace()

# 2. Discover what's available
print("=== Available Funnels ===")
for funnel in ws.discovery.list_funnels():
    print(f"  {funnel.name} (ID: {funnel.funnel_id})")

print("\n=== Available Cohorts ===")
for cohort in ws.discovery.list_cohorts():
    print(f"  {cohort.name}: {cohort.count} users")

print("\n=== Today's Top Events ===")
for event in ws.discovery.list_top_events(limit=5):
    print(f"  {event.event}: {event.count}")

# 3. Run targeted analysis
print("\n=== Event Comparison ===")
result = ws.live_query.event_counts(
    events=["Sign Up", "Purchase"],
    from_date="2024-01-01",
    to_date="2024-01-07",
)
for event in result.events:
    total = sum(result.series[event].values())
    print(f"  {event}: {total} total")

# 4. Export for further analysis
df = result.df
df.to_csv("event_comparison.csv", index=False)
```

---

## Caching Behavior

| Method | Cached | Reason |
|--------|--------|--------|
| `list_funnels()` | Yes | Funnel definitions rarely change |
| `list_cohorts()` | Yes | Cohort definitions rarely change |
| `list_top_events()` | No | Data changes throughout the day |
| `event_counts()` | No | Live query - always fresh |
| `property_counts()` | No | Live query - always fresh |

```python
# Cached - second call is instant
funnels1 = ws.discovery.list_funnels()  # API call
funnels2 = ws.discovery.list_funnels()  # From cache

# Not cached - always fetches
top1 = ws.discovery.list_top_events()  # API call
top2 = ws.discovery.list_top_events()  # API call again

# Clear cache if needed
ws.discovery.clear_cache()
```

---

*Quickstart complete. See data-model.md for type definitions and contracts/ for method signatures.*
