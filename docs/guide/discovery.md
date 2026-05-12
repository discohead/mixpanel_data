# Data Discovery

Explore your Mixpanel project's schema before writing queries. Discovery results are cached for the session.

!!! tip "Explore on DeepWiki"
    🤖 **[Discovery Methods Guide →](https://deepwiki.com/mixpanel/mixpanel-headless/3.2.2-discovery-methods)**

    Ask questions about schema exploration, caching behavior, or how to discover your data landscape.

## Listing Events

Get all event names in your project:

=== "Python"

    ```python
    import mixpanel_headless as mp

    ws = mp.Workspace()

    events = ws.events()
    print(events)  # ['Login', 'Purchase', 'Signup', ...]
    ```

=== "CLI"

    ```bash
    mp inspect events

    # Filter with jq - get first 5 events
    mp inspect events --format json --jq '.[:5]'

    # Find events containing "User"
    mp inspect events --format json --jq '.[] | select(contains("User"))'
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

## Subproperties

Some Mixpanel event properties are **lists of objects** — for example, a `cart` property whose value is `[{"Brand": "nike", "Category": "hats", "Price": 51}, ...]`. The `property_values()` endpoint returns these as JSON-encoded strings, which makes them awkward to inspect by eye. `subproperties()` parses a sample of those blobs and infers a scalar type per inner key.

=== "Python"

    ```python
    for sp in ws.subproperties("cart", event="Cart Viewed"):
        print(sp.name, sp.type, sp.sample_values)
    # Brand string ('nike', 'puma', 'h&m')
    # Category string ('hats', 'jeans')
    # Item ID number (35317, 35318)
    # Price number (51, 87, 102)
    ```

=== "CLI"

    ```bash
    mp inspect subproperties --property cart --event "Cart Viewed"

    # Sample more rows (default: 50)
    mp inspect subproperties -p cart -e "Cart Viewed" --sample-size 200

    # Tabular output
    mp inspect subproperties -p cart -e "Cart Viewed" --format table
    ```

Results are alphabetically sorted by `name`. Subproperties whose values are themselves dicts/lists are silently skipped (only scalar sub-values are reportable). When a sub-key is observed with mixed scalar shapes, with both scalar and dict shapes, or with only `null` values, the call emits a `UserWarning`.

The discovered names and types feed directly into [`Filter.list_contains`](query.md#list-of-object-filters) and [`GroupBy.list_item`](query.md#list-of-object-breakdowns) for filtering and breaking down by subproperty values.

### SubPropertyInfo

```python
sp.name           # "Brand"
sp.type           # "string" | "number" | "boolean" | "datetime"
sp.sample_values  # ('nike', 'puma', 'h&m')  — up to 5 distinct values
sp.to_dict()      # {'name': 'Brand', 'type': 'string', 'sample_values': ['nike', ...]}
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

!!! tip "Schema Registry CRUD"
    For write operations on the schema registry (create, update, delete schemas and enforcement configuration), see the [Data Governance guide — Schema Registry](data-governance.md#schema-registry).

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

!!! tip "Write Operations"
    The Lexicon schemas shown here are **read-only discovery** methods. For full CRUD operations on Lexicon definitions (update, delete events/properties, manage tags, bulk updates), see the [Data Governance guide](data-governance.md).

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
        from_date="2025-01-01",
        to_date="2025-01-31",
        limit=10,
    )
    print(f"Total: {result.total_count}")
    for v in result.values:
        print(f"  {v.value}: {v.count} ({v.percentage:.1f}%)")
    ```

=== "CLI"

    ```bash
    mp inspect distribution -e Purchase -p country --from 2025-01-01 --to 2025-01-31
    mp inspect distribution -e Purchase -p country --from 2025-01-01 --to 2025-01-31 --limit 10
    ```

### Numeric Property Summary

Get statistical summary for numeric properties:

=== "Python"

    ```python
    result = ws.numeric_summary(
        event="Purchase",
        property="amount",
        from_date="2025-01-01",
        to_date="2025-01-31",
    )
    print(f"Count: {result.count}")
    print(f"Range: {result.min} to {result.max}")
    print(f"Avg: {result.avg:.2f}, Stddev: {result.stddev:.2f}")
    print(f"Median: {result.percentiles[50]}")
    ```

=== "CLI"

    ```bash
    mp inspect numeric -e Purchase -p amount --from 2025-01-01 --to 2025-01-31
    mp inspect numeric -e Purchase -p amount --from 2025-01-01 --to 2025-01-31 --percentiles 25,50,75,90
    ```

### Daily Event Counts

See event activity over time:

=== "Python"

    ```python
    result = ws.daily_counts(
        from_date="2025-01-01",
        to_date="2025-01-07",
        events=["Purchase", "Signup"],
    )
    for c in result.counts:
        print(f"{c.date} {c.event}: {c.count}")
    ```

=== "CLI"

    ```bash
    mp inspect daily --from 2025-01-01 --to 2025-01-07
    mp inspect daily --from 2025-01-01 --to 2025-01-07 -e Purchase,Signup
    ```

### User Engagement Distribution

Understand how engaged users are by their event count:

=== "Python"

    ```python
    result = ws.engagement_distribution(
        from_date="2025-01-01",
        to_date="2025-01-31",
    )
    print(f"Total users: {result.total_users}")
    for b in result.buckets:
        print(f"  {b.bucket_label} events: {b.user_count} ({b.percentage:.1f}%)")
    ```

=== "CLI"

    ```bash
    mp inspect engagement --from 2025-01-01 --to 2025-01-31
    mp inspect engagement --from 2025-01-01 --to 2025-01-31 --buckets 1,5,10,50,100
    ```

### Property Coverage

Check data quality by seeing how often properties are defined:

=== "Python"

    ```python
    result = ws.property_coverage(
        event="Purchase",
        properties=["coupon_code", "referrer", "utm_source"],
        from_date="2025-01-01",
        to_date="2025-01-31",
    )
    print(f"Total events: {result.total_events}")
    for c in result.coverage:
        print(f"  {c.property}: {c.coverage_percentage:.1f}% defined")
    ```

=== "CLI"

    ```bash
    mp inspect coverage -e Purchase -p coupon_code,referrer,utm_source --from 2025-01-01 --to 2025-01-31
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

## Discovery Workflow

A typical discovery workflow before analysis:

```python
import mixpanel_headless as mp

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

# 5. Run a live query with discovered data
result = ws.segmentation(
    event="Purchase",
    from_date="2025-01-01",
    to_date="2025-01-31",
    on="country"
)
print(result.df)
```

## Next Steps

- [Streaming Data](streaming.md) — Stream events and profiles
- [API Reference](../api/workspace.md) — Complete API documentation
