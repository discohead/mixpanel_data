# Integration Patterns

Common patterns for integrating mixpanel_data with pandas, jq, and Unix pipelines.

## Table of Contents
- Data Storage Schema
- JSON Property Queries in DuckDB
- pandas Integration
- jq Processing
- Unix Pipelines
- Date Range Chunking
- Multi-Account Workflows
- Data Science Workflows

## Data Storage Schema

### Events Table
```sql
CREATE TABLE events (
    event_name VARCHAR NOT NULL,
    event_time TIMESTAMP NOT NULL,
    distinct_id VARCHAR NOT NULL,
    insert_id VARCHAR PRIMARY KEY,
    properties JSON
)
```

### Profiles Table
```sql
CREATE TABLE profiles (
    distinct_id VARCHAR PRIMARY KEY,
    properties JSON,
    last_seen TIMESTAMP
)
```

## JSON Property Queries in DuckDB

Properties stored as JSON. Use `->>'$.field'` to extract.

### Basic Extraction
```sql
-- String property
SELECT properties->>'$.country' as country FROM events

-- Nested property
SELECT properties->>'$.user.plan' as plan FROM events

-- Multiple properties
SELECT
    properties->>'$.country' as country,
    properties->>'$.plan' as plan,
    properties->>'$.source' as source
FROM events
```

### Type Casting
```sql
-- Numeric property
SELECT CAST(properties->>'$.amount' AS DOUBLE) as amount FROM events

-- Integer
SELECT CAST(properties->>'$.quantity' AS INTEGER) as qty FROM events

-- Boolean (stored as string)
SELECT properties->>'$.is_premium' = 'true' as is_premium FROM events
```

### Filtering
```sql
-- Filter by property value
SELECT * FROM events
WHERE properties->>'$.country' = 'US'

-- Numeric comparison
SELECT * FROM events
WHERE CAST(properties->>'$.amount' AS DOUBLE) > 100

-- NULL handling
SELECT * FROM events
WHERE properties->>'$.referrer' IS NOT NULL
```

### Aggregation
```sql
SELECT
    properties->>'$.country' as country,
    COUNT(*) as events,
    COUNT(DISTINCT distinct_id) as users,
    AVG(CAST(properties->>'$.amount' AS DOUBLE)) as avg_amount
FROM events
WHERE event_name = 'Purchase'
GROUP BY properties->>'$.country'
ORDER BY events DESC
```

## pandas Integration

### DataFrame from SQL
```python
import mixpanel_data as mp

ws = mp.Workspace()
ws.fetch_events("events", from_date="2024-01-01", to_date="2024-01-31")

# Direct SQL to DataFrame
df = ws.sql("""
    SELECT
        DATE_TRUNC('day', event_time) as day,
        event_name,
        COUNT(*) as count
    FROM events
    GROUP BY 1, 2
""")

# Standard pandas operations
daily = df.groupby('day')['count'].sum()
pivot = df.pivot(index='day', columns='event_name', values='count').fillna(0)
```

### Result .df Property
All result types have lazy `.df` conversion:

```python
# Segmentation
result = ws.segmentation("Purchase", from_date="2024-01-01", to_date="2024-01-31", on="country")
df = result.df  # Lazy conversion, cached

# Funnel
result = ws.funnel(12345, from_date="2024-01-01", to_date="2024-01-31")
df = result.df

# Retention
result = ws.retention("Sign Up", "Purchase", from_date="2024-01-01", to_date="2024-01-31")
df = result.df
```

### Visualization
```python
import matplotlib.pyplot as plt

# Time series
df = ws.sql("SELECT DATE_TRUNC('day', event_time) as day, COUNT(*) as cnt FROM events GROUP BY 1")
df.plot(x='day', y='cnt', kind='line', figsize=(12, 6))
plt.title('Daily Events')
plt.savefig('daily.png')

# Segmentation visualization
result = ws.segmentation("Purchase", from_date="2024-01-01", to_date="2024-01-31", on="country")
pivot = result.df.pivot(index='date', columns='segment', values='count')
pivot.plot(figsize=(12, 6))
plt.title('Purchases by Country')
```

### Merging Data
```python
# Fetch multiple tables
ws.fetch_events("jan", from_date="2024-01-01", to_date="2024-01-31")
ws.fetch_events("feb", from_date="2024-02-01", to_date="2024-02-29", append=True)

# Or use SQL UNION
df = ws.sql("""
    SELECT * FROM jan
    UNION ALL
    SELECT * FROM feb
""")
```

## jq Processing

### Extract Fields
```bash
# Single field
mp fetch events --from 2024-01-01 --to 2024-01-01 --stdout | jq '.event'

# Multiple fields
mp fetch events --stdout | jq '{event, time: .event_time, user: .distinct_id}'

# Properties
mp fetch events --stdout | jq '.properties.country'
mp fetch events --stdout | jq '.properties | keys'  # List all property keys
```

### Filtering
```bash
# Filter by event
mp fetch events --stdout | jq 'select(.event == "Purchase")'

# Filter by property
mp fetch events --stdout | jq 'select(.properties.country == "US")'

# Numeric comparison
mp fetch events --stdout | jq 'select(.properties.amount > 100)'

# Multiple conditions
mp fetch events --stdout | jq 'select(.event == "Purchase" and .properties.amount > 100)'
```

### Aggregation
```bash
# Count by event
mp fetch events --stdout | jq -s 'group_by(.event) | map({event: .[0].event, count: length})'

# Sum numeric property
mp fetch events --stdout | jq -s '[.[].properties.amount] | add'

# Unique users
mp fetch events --stdout | jq -s '[.[].distinct_id] | unique | length'
```

### Transformation
```bash
# Flatten for CSV
mp fetch events --stdout | jq -r '[.event, .distinct_id, .event_time, .properties.country] | @csv'

# Create new structure
mp fetch events --stdout | jq '{
    event: .event,
    user: .distinct_id,
    country: .properties.country,
    amount: .properties.amount
}'
```

## Unix Pipelines

### Stream to CSV
```bash
# Events to CSV
mp fetch events --from 2024-01-01 --to 2024-01-01 --stdout \
  | jq -r '[.event, .distinct_id, .event_time] | @csv' \
  > events.csv

# With headers
echo "event,user,time" > events.csv
mp fetch events --stdout | jq -r '[.event, .distinct_id, .event_time] | @csv' >> events.csv
```

### Count with Filtering
```bash
# Count US purchases
mp fetch events --stdout \
  | jq 'select(.event == "Purchase" and .properties.country == "US")' \
  | wc -l

# Sum amounts
mp fetch events --stdout \
  | jq 'select(.event == "Purchase") | .properties.amount' \
  | awk '{sum+=$1} END {print sum}'
```

### Parallel Processing
```bash
# Process in batches
mp fetch events --stdout | parallel --pipe -N1000 'python process_batch.py'

# Multiple date ranges in parallel
seq 1 12 | parallel 'mp fetch events --from 2024-{}-01 --to 2024-{}-28 --stdout > month_{}.jsonl'
```

### Combine with Other Tools
```bash
# Sort by timestamp
mp fetch events --stdout | jq -c '.' | sort -t'"' -k8

# Sample random events
mp fetch events --stdout | shuf -n 100

# First/last N events
mp fetch events --stdout | head -100
mp fetch events --stdout | tail -100
```

## Date Range Chunking

### Python: Incremental Fetch
```python
import pandas as pd
import mixpanel_data as mp

ws = mp.Workspace()

# Fetch by month with append
for month_start in pd.date_range("2024-01-01", "2024-12-01", freq="MS"):
    month_end = (month_start + pd.DateOffset(months=1)) - pd.DateOffset(days=1)
    ws.fetch_events(
        "events",
        from_date=str(month_start.date()),
        to_date=str(month_end.date()),
        append=True,
    )
    print(f"Fetched {month_start.strftime('%B %Y')}")
```

### CLI: Shell Loop
```bash
# Monthly chunks
for m in 01 02 03 04 05 06 07 08 09 10 11 12; do
    mp fetch events --from 2024-${m}-01 --to 2024-${m}-28 --append
done

# Weekly chunks
start="2024-01-01"
while [[ "$start" < "2024-03-01" ]]; do
    end=$(date -d "$start + 6 days" +%Y-%m-%d)
    mp fetch events --from $start --to $end --append
    start=$(date -d "$start + 7 days" +%Y-%m-%d)
done
```

## Multi-Account Workflows

### Python: Multiple Workspaces
```python
import mixpanel_data as mp

# Compare production vs staging
ws_prod = mp.Workspace(account="production")
ws_staging = mp.Workspace(account="staging")

prod_events = ws_prod.events()
staging_events = ws_staging.events()

# Find events only in prod
prod_only = set(prod_events) - set(staging_events)
print(f"Production-only events: {prod_only}")

ws_prod.close()
ws_staging.close()
```

### CLI: Account Flag
```bash
# List events from different accounts
mp --account production inspect events
mp --account staging inspect events

# Fetch from multiple accounts
mp --account production fetch events --from 2024-01-01 --to 2024-01-31 --stdout > prod.jsonl
mp --account staging fetch events --from 2024-01-01 --to 2024-01-31 --stdout > staging.jsonl
```

## Data Science Workflows

### Funnel Analysis
```python
import mixpanel_data as mp
import matplotlib.pyplot as plt

ws = mp.Workspace()

# Get funnel data
funnels = ws.funnels()
print(f"Available funnels: {[f.name for f in funnels]}")

# Analyze conversion
result = ws.funnel(funnels[0].funnel_id, from_date="2024-01-01", to_date="2024-01-31")

# Visualize steps
steps = [(s.event, s.count, s.conversion_rate) for s in result.steps]
for event, count, rate in steps:
    print(f"{event}: {count} ({rate:.1%})")

# Bar chart
events = [s.event for s in result.steps]
counts = [s.count for s in result.steps]
plt.bar(events, counts)
plt.xticks(rotation=45)
plt.title(f'Funnel: {result.overall_conversion_rate:.1%} conversion')
plt.savefig('funnel.png', bbox_inches='tight')
```

### Retention Curves
```python
import mixpanel_data as mp
import matplotlib.pyplot as plt

ws = mp.Workspace()

result = ws.retention(
    born_event="Sign Up",
    return_event="Login",
    from_date="2024-01-01",
    to_date="2024-01-31",
    unit="week",
    interval_count=8,
)

# Plot retention curve
df = result.df
avg_retention = df.groupby('interval')['rate'].mean()
avg_retention.plot(kind='line', marker='o')
plt.xlabel('Weeks since signup')
plt.ylabel('Retention Rate')
plt.title('User Retention Curve')
plt.savefig('retention.png')
```

### User Segmentation
```python
import mixpanel_data as mp
import pandas as pd

ws = mp.Workspace()
ws.fetch_events("events", from_date="2024-01-01", to_date="2024-01-31")

# Segment users by activity
df = ws.sql("""
    SELECT
        distinct_id,
        COUNT(*) as events,
        COUNT(DISTINCT event_name) as unique_events,
        MIN(event_time) as first_seen,
        MAX(event_time) as last_seen
    FROM events
    GROUP BY distinct_id
""")

# Create segments
df['segment'] = pd.cut(
    df['events'],
    bins=[0, 5, 20, 100, float('inf')],
    labels=['Casual', 'Regular', 'Power', 'Super']
)

print(df.groupby('segment').size())
```

### Cohort Analysis
```python
import mixpanel_data as mp

ws = mp.Workspace()
ws.fetch_events("events", from_date="2024-01-01", to_date="2024-03-31")

# Weekly cohorts
df = ws.sql("""
    WITH user_cohorts AS (
        SELECT
            distinct_id,
            DATE_TRUNC('week', MIN(event_time)) as cohort_week
        FROM events
        GROUP BY distinct_id
    ),
    weekly_activity AS (
        SELECT
            e.distinct_id,
            c.cohort_week,
            DATE_TRUNC('week', e.event_time) as activity_week
        FROM events e
        JOIN user_cohorts c ON e.distinct_id = c.distinct_id
    )
    SELECT
        cohort_week,
        activity_week,
        COUNT(DISTINCT distinct_id) as users
    FROM weekly_activity
    GROUP BY 1, 2
    ORDER BY 1, 2
""")

# Pivot for cohort matrix
pivot = df.pivot(index='cohort_week', columns='activity_week', values='users')
print(pivot)
```
