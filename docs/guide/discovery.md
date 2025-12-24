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
    schema = ws.schema("jan_events")
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
