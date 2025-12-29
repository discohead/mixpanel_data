# Local SQL Queries

Query your fetched data with SQL using DuckDB's powerful analytical engine.

## Basic Queries

### Execute and Get DataFrame

```python
import mixpanel_data as mp

ws = mp.Workspace()

df = ws.sql("""
    SELECT
        event_name,
        COUNT(*) as count
    FROM jan_events
    GROUP BY 1
    ORDER BY 2 DESC
""")

print(df)
```

### Get Single Value

```python
total = ws.sql_scalar("SELECT COUNT(*) FROM jan_events")
print(f"Total events: {total}")
```

### Get Rows as Tuples

```python
rows = ws.sql_rows("""
    SELECT event_name, COUNT(*)
    FROM jan_events
    GROUP BY 1
    LIMIT 5
""")

for event_name, count in rows:
    print(f"{event_name}: {count}")
```

## DuckDB JSON Syntax

Mixpanel properties are stored as JSON columns. Use DuckDB's JSON operators to access them.

### Extract String Property

```sql
SELECT properties->>'$.country' as country
FROM jan_events
```

### Extract and Cast Numeric

```sql
SELECT CAST(properties->>'$.amount' AS DECIMAL) as amount
FROM jan_events
```

### Filter on Property

```sql
SELECT *
FROM jan_events
WHERE properties->>'$.plan' = 'premium'
```

### Nested Property Access

```sql
SELECT properties->>'$.user.email' as email
FROM jan_events
```

### Check Property Exists

```sql
SELECT *
FROM jan_events
WHERE properties->>'$.coupon_code' IS NOT NULL
```

### Array Properties

```sql
-- Array length
SELECT json_array_length(properties->'$.items') as item_count
FROM jan_events

-- Array element
SELECT properties->'$.items'->>0 as first_item
FROM jan_events
```

## Common Query Patterns

### Daily Event Counts

```sql
SELECT
    DATE_TRUNC('day', event_time) as day,
    COUNT(*) as count
FROM jan_events
GROUP BY 1
ORDER BY 1
```

### Events by User

```sql
SELECT
    distinct_id,
    COUNT(*) as event_count,
    MIN(event_time) as first_seen,
    MAX(event_time) as last_seen
FROM jan_events
GROUP BY 1
ORDER BY 2 DESC
LIMIT 10
```

### Property Distribution

```sql
SELECT
    properties->>'$.country' as country,
    COUNT(*) as count,
    ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 2) as pct
FROM jan_events
WHERE event_name = 'Purchase'
GROUP BY 1
ORDER BY 2 DESC
```

### Revenue by Day

```sql
SELECT
    DATE_TRUNC('day', event_time) as day,
    COUNT(*) as purchases,
    SUM(CAST(properties->>'$.amount' AS DECIMAL)) as revenue
FROM jan_events
WHERE event_name = 'Purchase'
GROUP BY 1
ORDER BY 1
```

### User Cohort Analysis

```sql
WITH first_events AS (
    SELECT
        distinct_id,
        DATE_TRUNC('week', MIN(event_time)) as cohort_week
    FROM jan_events
    WHERE event_name = 'Signup'
    GROUP BY 1
)
SELECT
    cohort_week,
    COUNT(DISTINCT distinct_id) as users
FROM first_events
GROUP BY 1
ORDER BY 1
```

### Funnel Query

```sql
WITH step1 AS (
    SELECT DISTINCT distinct_id
    FROM jan_events
    WHERE event_name = 'View Product'
),
step2 AS (
    SELECT DISTINCT distinct_id
    FROM jan_events
    WHERE event_name = 'Add to Cart'
    AND distinct_id IN (SELECT distinct_id FROM step1)
),
step3 AS (
    SELECT DISTINCT distinct_id
    FROM jan_events
    WHERE event_name = 'Purchase'
    AND distinct_id IN (SELECT distinct_id FROM step2)
)
SELECT
    (SELECT COUNT(*) FROM step1) as viewed,
    (SELECT COUNT(*) FROM step2) as added,
    (SELECT COUNT(*) FROM step3) as purchased
```

## Joining Events and Profiles

Query events with user profile data:

```python
# First, fetch both
ws.fetch_events("events", from_date="2025-01-01", to_date="2025-01-31")
ws.fetch_profiles("users")

# Join them
df = ws.sql("""
    SELECT
        e.event_name,
        u.properties->>'$.plan' as plan,
        COUNT(*) as count
    FROM events e
    JOIN users u ON e.distinct_id = u.distinct_id
    GROUP BY 1, 2
    ORDER BY 3 DESC
""")
```

## CLI Usage

Run SQL queries from the command line:

```bash
# Table output
mp query sql "SELECT event_name, COUNT(*) FROM events GROUP BY 1" --format table

# JSON output
mp query sql "SELECT * FROM events LIMIT 10" --format json

# CSV export
mp query sql "SELECT * FROM events" --format csv > events.csv

# JSONL for streaming
mp query sql "SELECT * FROM events" --format jsonl > events.jsonl
```

## Direct DuckDB Access

For advanced use cases, access the DuckDB connection directly:

```python
# Get the connection
conn = ws.connection

# Run DuckDB-specific operations
conn.execute("SET threads TO 4")
result = conn.execute("EXPLAIN ANALYZE SELECT * FROM events").fetchall()
```

## Performance Tips

### Use Appropriate Data Types

Cast properties to appropriate types for better performance:

```sql
-- Instead of string comparison
WHERE CAST(properties->>'$.amount' AS DECIMAL) > 100

-- Consider creating a view with typed columns
CREATE VIEW typed_events AS
SELECT
    event_id,
    event_name,
    event_time,
    distinct_id,
    CAST(properties->>'$.amount' AS DECIMAL) as amount,
    properties->>'$.country' as country
FROM jan_events
```

### Limit Result Sets

Always use LIMIT during exploration:

```sql
SELECT * FROM jan_events LIMIT 100
```

### Use Aggregations

DuckDB is optimized for analytical queries. Prefer aggregations over fetching raw rows.

## Next Steps

- [Live Analytics](live-analytics.md) — Query Mixpanel directly
- [API Reference](../api/workspace.md) — Complete Workspace API
