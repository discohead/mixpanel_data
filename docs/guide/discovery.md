# Data Discovery

Explore your Mixpanel project's schema before writing queries. Discovery results are cached for the session.

## Listing Events

Get all event names in your project:

=== "Python"

    ```python
    import mixpanel_data as mp

    ws = mp.Workspace()

    events = ws.events()
    print(events)  # ['Login', 'Purchase', 'Signup', ...]
    ```

=== "CLI"

    ```bash
    mp inspect events
    ```

Events are returned sorted alphabetically.

## Listing Properties

Get properties for a specific event:

=== "Python"

    ```python
    properties = ws.properties("Purchase")
    print(properties)  # ['amount', 'country', 'product_id', ...]
    ```

=== "CLI"

    ```bash
    mp inspect properties --event Purchase
    ```

Properties include both event-specific and common properties.

## Property Values

Sample values for a property:

=== "Python"

    ```python
    # Sample values for a property
    values = ws.property_values("country", event="Purchase")
    print(values)  # ['US', 'UK', 'DE', 'FR', ...]

    # Limit results
    values = ws.property_values("country", event="Purchase", limit=5)
    ```

=== "CLI"

    ```bash
    mp inspect values --property country --event Purchase --limit 10
    ```

## Saved Funnels

List funnels defined in Mixpanel:

=== "Python"

    ```python
    funnels = ws.funnels()
    for f in funnels:
        print(f"{f.funnel_id}: {f.name}")
    ```

=== "CLI"

    ```bash
    mp inspect funnels
    ```

### FunnelInfo

```python
f.funnel_id  # 12345
f.name       # "Checkout Funnel"
```

## Saved Cohorts

List cohorts defined in Mixpanel:

=== "Python"

    ```python
    cohorts = ws.cohorts()
    for c in cohorts:
        print(f"{c.id}: {c.name} ({c.count} users)")
    ```

=== "CLI"

    ```bash
    mp inspect cohorts
    ```

### SavedCohort

```python
c.id           # 12345
c.name         # "Power Users"
c.count        # 5000
c.description  # "Users with 10+ logins"
c.created      # datetime
c.is_visible   # True
```

## Lexicon Schemas

Retrieve data dictionary schemas for events and profile properties. Schemas include descriptions, property types, and metadata defined in Mixpanel's Lexicon.

!!! note "Schema Coverage"
    The Lexicon API returns only events/properties with explicit schemas (defined via API, CSV import, or UI). It does not return all events visible in Lexicon's UI.

=== "Python"

    ```python
    # List all schemas
    schemas = ws.lexicon_schemas()
    for s in schemas:
        print(f"{s.entity_type}: {s.name}")

    # Filter by entity type
    event_schemas = ws.lexicon_schemas(entity_type="event")
    profile_schemas = ws.lexicon_schemas(entity_type="profile")

    # Get a specific schema
    schema = ws.lexicon_schema("event", "Purchase")
    print(schema.schema_json.description)
    for prop, info in schema.schema_json.properties.items():
        print(f"  {prop}: {info.type}")
    ```

=== "CLI"

    ```bash
    mp inspect lexicon-schemas
    mp inspect lexicon-schemas --type event
    mp inspect lexicon-schemas --type profile
    mp inspect lexicon-schema --type event --name Purchase
    ```

### LexiconSchema

```python
s.entity_type           # "event", "profile", or other API-returned types
s.name                  # "Purchase"
s.schema_json           # LexiconDefinition object
```

### LexiconDefinition

```python
s.schema_json.description                # "User completes a purchase"
s.schema_json.properties                 # dict[str, LexiconProperty]
s.schema_json.metadata                   # LexiconMetadata or None
```

### LexiconProperty

```python
prop = s.schema_json.properties["amount"]
prop.type                                # "number"
prop.description                         # "Purchase amount in USD"
prop.metadata                            # LexiconMetadata or None
```

### LexiconMetadata

```python
meta = s.schema_json.metadata
meta.display_name       # "Purchase Event"
meta.tags               # ["core", "revenue"]
meta.hidden             # False
meta.dropped            # False
meta.contacts           # ["owner@company.com"]
meta.team_contacts      # ["Analytics Team"]
```

!!! warning "Rate Limit"
    The Lexicon API has a strict rate limit of **5 requests per minute**. Schema results are cached for the session to minimize API calls.

## Top Events

Get today's most active events:

=== "Python"

    ```python
    # General top events
    top = ws.top_events(type="general")
    for event in top:
        print(f"{event.event}: {event.count} ({event.percent_change:+.1f}%)")

    # Average top events
    top = ws.top_events(type="average", limit=5)
    ```

=== "CLI"

    ```bash
    mp inspect top-events --type general --limit 10
    ```

### TopEvent

```python
event.event           # "Login"
event.count           # 15000
event.percent_change  # 12.5 (compared to yesterday)
```

!!! note "Not Cached"
    Unlike other discovery methods, `top_events()` always makes an API call since it returns real-time data.

## JQL-Based Remote Discovery

These methods use JQL (JavaScript Query Language) to analyze data directly on Mixpanel's servers, returning aggregated results without fetching raw data locally.

### Property Value Distribution

Understand what values a property contains and how often they appear:

=== "Python"

    ```python
    result = ws.property_distribution(
        event="Purchase",
        property="country",
        from_date="2024-01-01",
        to_date="2024-01-31",
        limit=10,
    )
    print(f"Total: {result.total_count}")
    for v in result.values:
        print(f"  {v.value}: {v.count} ({v.percentage:.1f}%)")
    ```

=== "CLI"

    ```bash
    mp inspect distribution -e Purchase -p country --from 2024-01-01 --to 2024-01-31
    mp inspect distribution -e Purchase -p country --from 2024-01-01 --to 2024-01-31 --limit 10
    ```

### Numeric Property Summary

Get statistical summary for numeric properties:

=== "Python"

    ```python
    result = ws.numeric_summary(
        event="Purchase",
        property="amount",
        from_date="2024-01-01",
        to_date="2024-01-31",
    )
    print(f"Count: {result.count}")
    print(f"Range: {result.min} to {result.max}")
    print(f"Avg: {result.avg:.2f}, Stddev: {result.stddev:.2f}")
    print(f"Median: {result.percentiles[50]}")
    ```

=== "CLI"

    ```bash
    mp inspect numeric -e Purchase -p amount --from 2024-01-01 --to 2024-01-31
    mp inspect numeric -e Purchase -p amount --from 2024-01-01 --to 2024-01-31 --percentiles 25,50,75,90
    ```

### Daily Event Counts

See event activity over time:

=== "Python"

    ```python
    result = ws.daily_counts(
        from_date="2024-01-01",
        to_date="2024-01-07",
        events=["Purchase", "Signup"],
    )
    for c in result.counts:
        print(f"{c.date} {c.event}: {c.count}")
    ```

=== "CLI"

    ```bash
    mp inspect daily --from 2024-01-01 --to 2024-01-07
    mp inspect daily --from 2024-01-01 --to 2024-01-07 -e Purchase,Signup
    ```

### User Engagement Distribution

Understand how engaged users are by their event count:

=== "Python"

    ```python
    result = ws.engagement_distribution(
        from_date="2024-01-01",
        to_date="2024-01-31",
    )
    print(f"Total users: {result.total_users}")
    for b in result.buckets:
        print(f"  {b.bucket_label} events: {b.user_count} ({b.percentage:.1f}%)")
    ```

=== "CLI"

    ```bash
    mp inspect engagement --from 2024-01-01 --to 2024-01-31
    mp inspect engagement --from 2024-01-01 --to 2024-01-31 --buckets 1,5,10,50,100
    ```

### Property Coverage

Check data quality by seeing how often properties are defined:

=== "Python"

    ```python
    result = ws.property_coverage(
        event="Purchase",
        properties=["coupon_code", "referrer", "utm_source"],
        from_date="2024-01-01",
        to_date="2024-01-31",
    )
    print(f"Total events: {result.total_events}")
    for c in result.coverage:
        print(f"  {c.property}: {c.coverage_percentage:.1f}% defined")
    ```

=== "CLI"

    ```bash
    mp inspect coverage -e Purchase -p coupon_code,referrer,utm_source --from 2024-01-01 --to 2024-01-31
    ```

!!! tip "When to Use JQL-Based Discovery"
    These methods are ideal for:

    - **Quick exploration**: Understand data shape before fetching locally
    - **Large date ranges**: Analyze months of data without downloading everything
    - **Data quality checks**: Verify property coverage and value distributions
    - **Trend analysis**: See daily activity patterns

See the [JQL Discovery Types](../api/types.md#jql-discovery-types) in the API reference for return type details.

## Caching

Discovery results are cached for the lifetime of the Workspace:

```python
ws = mp.Workspace()

# First call hits the API
events1 = ws.events()

# Second call returns cached result (instant)
events2 = ws.events()

# Clear cache to force refresh
ws.clear_discovery_cache()

# Now hits API again
events3 = ws.events()
```

## Local Data Analysis

After fetching data into DuckDB, use these introspection methods to understand your data before writing SQL queries.

### Sampling Data

Get random sample rows to see data structure:

=== "Python"

    ```python
    # Get 10 random rows (default)
    df = ws.sample("events")
    print(df)

    # Get 5 random rows
    df = ws.sample("events", n=5)
    ```

=== "CLI"

    ```bash
    mp inspect sample -t events
    mp inspect sample -t events -n 5
    mp inspect sample -t events --format table
    ```

### Statistical Summary

Get column-level statistics for an entire table:

=== "Python"

    ```python
    summary = ws.summarize("events")
    print(f"Total rows: {summary.row_count}")

    for col in summary.columns:
        print(f"{col.column_name}: {col.column_type}")
        print(f"  Nulls: {col.null_percentage:.1f}%")
        print(f"  Unique: {col.approx_unique}")
        if col.avg is not None:  # Numeric columns
            print(f"  Mean: {col.avg:.2f}, Std: {col.std:.2f}")
    ```

=== "CLI"

    ```bash
    mp inspect summarize -t events
    mp inspect summarize -t events --format table
    ```

### Event Breakdown

Analyze event distribution in an events table:

=== "Python"

    ```python
    breakdown = ws.event_breakdown("events")
    print(f"Total events: {breakdown.total_events}")
    print(f"Total users: {breakdown.total_users}")
    print(f"Date range: {breakdown.date_range[0]} to {breakdown.date_range[1]}")

    for event in breakdown.events:
        print(f"{event.event_name}: {event.count} ({event.pct_of_total:.1f}%)")
        print(f"  Users: {event.unique_users}")
        print(f"  First seen: {event.first_seen}")
    ```

=== "CLI"

    ```bash
    mp inspect breakdown -t events
    mp inspect breakdown -t events --format table
    ```

!!! note "Required Columns"
    The table must have `event_name`, `event_time`, and `distinct_id` columns.

### Property Key Discovery

Discover all JSON property keys in a table:

=== "Python"

    ```python
    # All property keys across all events
    keys = ws.property_keys("events")
    print(keys)  # ['amount', 'country', 'product_id', ...]

    # Property keys for a specific event
    keys = ws.property_keys("events", event="Purchase")
    ```

=== "CLI"

    ```bash
    mp inspect keys -t events
    mp inspect keys -t events -e "Purchase"
    ```

This is especially useful for building JSON path expressions like `properties->>'$.country'`.

### Column Statistics

Deep analysis of a single column:

=== "Python"

    ```python
    # Analyze a regular column
    stats = ws.column_stats("events", "event_name")
    print(f"Total: {stats.count}, Nulls: {stats.null_pct:.1f}%")
    print(f"Unique values: {stats.unique_count}")
    print("Top values:")
    for value, count in stats.top_values:
        print(f"  {value}: {count}")

    # Analyze a JSON property
    stats = ws.column_stats("events", "properties->>'$.country'", top_n=20)
    ```

=== "CLI"

    ```bash
    mp inspect column -t events -c event_name
    mp inspect column -t events -c "properties->>'$.country'" --top 20
    ```

For numeric columns, additional statistics are available:

```python
stats = ws.column_stats("purchases", "properties->>'$.amount'")
print(f"Min: {stats.min}, Max: {stats.max}")
print(f"Mean: {stats.mean:.2f}, Std: {stats.std:.2f}")
```

### Introspection Workflow

A typical workflow for exploring fetched data:

```python
import mixpanel_data as mp

ws = mp.Workspace()

# Fetch data first
ws.fetch_events("events", from_date="2024-01-01", to_date="2024-01-31")

# 1. Quick look at the data
print(ws.sample("events", n=3))

# 2. Get overall statistics
summary = ws.summarize("events")
print(f"Rows: {summary.row_count}")

# 3. Understand event distribution
breakdown = ws.event_breakdown("events")
for e in breakdown.events[:5]:
    print(f"{e.event_name}: {e.count}")

# 4. Discover available properties
keys = ws.property_keys("events", event="Purchase")
print(f"Purchase properties: {keys}")

# 5. Deep dive into specific columns
stats = ws.column_stats("events", "properties->>'$.country'")
print(f"Top countries: {stats.top_values[:5]}")

# Now write informed SQL queries
df = ws.sql("""
    SELECT properties->>'$.country' as country, COUNT(*) as count
    FROM events
    WHERE event_name = 'Purchase'
    GROUP BY 1
    ORDER BY 2 DESC
""")
```

## Local Table Discovery

Inspect tables in your local database:

### List Tables

=== "Python"

    ```python
    tables = ws.tables()
    for t in tables:
        print(f"{t.name}: {t.row_count} rows ({t.type})")
    ```

=== "CLI"

    ```bash
    mp inspect tables
    ```

### Table Schema

=== "Python"

    ```python
    schema = ws.table_schema("jan_events")
    for col in schema.columns:
        print(f"{col.name}: {col.type} (nullable: {col.nullable})")
    ```

=== "CLI"

    ```bash
    mp inspect schema --table jan_events
    ```

### Workspace Info

=== "Python"

    ```python
    info = ws.info()
    print(f"Database: {info.path}")
    print(f"Project: {info.project_id} ({info.region})")
    print(f"Account: {info.account}")
    print(f"Tables: {len(info.tables)}")
    print(f"Size: {info.size_mb:.1f} MB")
    ```

=== "CLI"

    ```bash
    mp inspect info
    ```

## Discovery Workflow

A typical discovery workflow before analysis:

```python
import mixpanel_data as mp

ws = mp.Workspace()

# 1. What events exist?
print("Events:")
for event in ws.events()[:10]:
    print(f"  - {event}")

# 2. What properties does Purchase have?
print("\nPurchase properties:")
for prop in ws.properties("Purchase"):
    print(f"  - {prop}")

# 3. What values does 'country' have?
print("\nCountry values:")
for value in ws.property_values("country", event="Purchase", limit=10):
    print(f"  - {value}")

# 4. What funnels are defined?
print("\nFunnels:")
for f in ws.funnels():
    print(f"  - {f.name} (ID: {f.funnel_id})")

# 5. Now fetch and analyze
ws.fetch_events("purchases", from_date="2024-01-01", to_date="2024-01-31",
                events=["Purchase"])

df = ws.sql("""
    SELECT properties->>'$.country' as country, COUNT(*) as count
    FROM purchases
    GROUP BY 1
    ORDER BY 2 DESC
""")
print(df)
```

## Next Steps

- [Fetching Data](fetching.md) — Fetch events for local analysis
- [SQL Queries](sql-queries.md) — Query with SQL
- [API Reference](../api/workspace.md) — Complete API documentation
