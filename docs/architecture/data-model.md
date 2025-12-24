# Data Model

How Mixpanel data maps to local storage.

## Mixpanel Data Model

Mixpanel tracks two primary data types:

### Events

Actions users take in your product:

| Field | Description |
|-------|-------------|
| `event` | Event name (e.g., "Purchase", "Signup") |
| `time` | Unix timestamp when event occurred |
| `distinct_id` | User identifier |
| `$insert_id` | Deduplication ID |
| `properties` | Custom properties (JSON object) |

### User Profiles

Persistent attributes about users:

| Field | Description |
|-------|-------------|
| `$distinct_id` | User identifier (primary key) |
| `$properties` | Profile properties (JSON object) |

## Local Storage Schema

### Events Table

When you fetch events, they're stored with this schema:

| Column | Type | Description |
|--------|------|-------------|
| `event_id` | VARCHAR | Unique event identifier |
| `event_name` | VARCHAR | Event name |
| `event_time` | TIMESTAMP | When the event occurred |
| `distinct_id` | VARCHAR | User identifier |
| `insert_id` | VARCHAR | Deduplication ID |
| `properties` | JSON | All event properties |

Example query:

```sql
SELECT
    event_name,
    event_time,
    distinct_id,
    properties->>'$.country' as country,
    CAST(properties->>'$.amount' AS DECIMAL) as amount
FROM events
WHERE event_name = 'Purchase'
```

### Profiles Table

User profiles are stored with:

| Column | Type | Description |
|--------|------|-------------|
| `distinct_id` | VARCHAR | User identifier (primary key) |
| `properties` | JSON | All profile properties |

Example query:

```sql
SELECT
    distinct_id,
    properties->>'$.name' as name,
    properties->>'$.email' as email,
    properties->>'$.plan' as plan
FROM profiles
WHERE properties->>'$.plan' = 'premium'
```

## JSON Property Access

DuckDB provides powerful JSON operators for querying properties:

### Extract String

```sql
-- Arrow operator returns JSON, ->> returns text
SELECT properties->>'$.country' as country FROM events
```

### Extract and Cast

```sql
SELECT CAST(properties->>'$.amount' AS DECIMAL) as amount FROM events
```

### Nested Access

```sql
SELECT properties->>'$.user.address.city' as city FROM events
```

### Array Access

```sql
-- First element
SELECT properties->'$.items'->>0 as first_item FROM events

-- Array length
SELECT json_array_length(properties->'$.items') as count FROM events
```

### Check Existence

```sql
SELECT * FROM events
WHERE properties->>'$.coupon_code' IS NOT NULL
```

## Metadata Table

Each workspace maintains a `_mp_metadata` table for tracking fetch operations:

| Column | Type | Description |
|--------|------|-------------|
| `table_name` | VARCHAR | Name of the data table |
| `table_type` | VARCHAR | "events" or "profiles" |
| `from_date` | VARCHAR | Start date (events only) |
| `to_date` | VARCHAR | End date (events only) |
| `events` | JSON | Event filter (if any) |
| `where_clause` | VARCHAR | Where filter (if any) |
| `row_count` | BIGINT | Number of rows |
| `fetched_at` | TIMESTAMP | When fetch completed |

This metadata is used by `ws.tables()` and `ws.info()`.

## Common Mixpanel Properties

### Event Properties

| Property | Type | Description |
|----------|------|-------------|
| `$city` | string | User's city |
| `$region` | string | User's region/state |
| `$country_code` | string | Two-letter country code |
| `$browser` | string | Browser name |
| `$device` | string | Device type |
| `$os` | string | Operating system |
| `mp_country_code` | string | Country code |
| `$current_url` | string | Page URL |
| `$referrer` | string | Referrer URL |

### Profile Properties

| Property | Type | Description |
|----------|------|-------------|
| `$email` | string | User's email |
| `$name` | string | User's name |
| `$first_name` | string | First name |
| `$last_name` | string | Last name |
| `$created` | timestamp | When profile was created |
| `$last_seen` | timestamp | Last activity time |

## Query Patterns

### Daily Active Users

```sql
SELECT
    DATE_TRUNC('day', event_time) as day,
    COUNT(DISTINCT distinct_id) as dau
FROM events
GROUP BY 1
ORDER BY 1
```

### Revenue by Country

```sql
SELECT
    properties->>'$.country_code' as country,
    SUM(CAST(properties->>'$.amount' AS DECIMAL)) as revenue
FROM events
WHERE event_name = 'Purchase'
GROUP BY 1
ORDER BY 2 DESC
```

### Join Events with Profiles

```sql
SELECT
    e.event_name,
    p.properties->>'$.plan' as plan,
    COUNT(*) as count
FROM events e
JOIN profiles p ON e.distinct_id = p.distinct_id
GROUP BY 1, 2
```

### Funnel Analysis

```sql
WITH step1 AS (
    SELECT DISTINCT distinct_id, MIN(event_time) as t1
    FROM events WHERE event_name = 'View Product' GROUP BY 1
),
step2 AS (
    SELECT DISTINCT e.distinct_id, MIN(e.event_time) as t2
    FROM events e
    JOIN step1 s ON e.distinct_id = s.distinct_id
    WHERE e.event_name = 'Add to Cart' AND e.event_time > s.t1
    GROUP BY 1
),
step3 AS (
    SELECT DISTINCT e.distinct_id
    FROM events e
    JOIN step2 s ON e.distinct_id = s.distinct_id
    WHERE e.event_name = 'Purchase' AND e.event_time > s.t2
)
SELECT
    (SELECT COUNT(*) FROM step1) as viewed,
    (SELECT COUNT(*) FROM step2) as added,
    (SELECT COUNT(*) FROM step3) as purchased
```

## See Also

- [SQL Queries Guide](../guide/sql-queries.md) — More query examples
- [DuckDB JSON Documentation](https://duckdb.org/docs/extensions/json) — Complete JSON function reference
