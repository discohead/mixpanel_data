# Live Analytics

Query Mixpanel's analytics APIs directly for real-time data without fetching to local storage.

## When to Use Live Queries

Use live queries when:

- You need the most current data
- You're running one-off analysis
- The query is already optimized by Mixpanel (segmentation, funnels, retention)
- You want to leverage Mixpanel's pre-computed aggregations

Use local queries when:

- You need to run many queries over the same data
- You need custom SQL logic
- You want to minimize API calls
- Context window preservation matters (for AI agents)

## Segmentation

Time-series event counts with optional property segmentation:

=== "Python"

    ```python
    import mixpanel_data as mp

    ws = mp.Workspace()

    # Simple count over time
    result = ws.segmentation(
        event="Purchase",
        from_date="2025-01-01",
        to_date="2025-01-31"
    )

    # Segment by property
    result = ws.segmentation(
        event="Purchase",
        from_date="2025-01-01",
        to_date="2025-01-31",
        on="properties.country"
    )

    # With filtering
    result = ws.segmentation(
        event="Purchase",
        from_date="2025-01-01",
        to_date="2025-01-31",
        on="properties.country",
        where='properties["plan"] == "premium"',
        unit="week"  # day, week, month
    )

    # Access as DataFrame
    print(result.df)
    ```

=== "CLI"

    ```bash
    # Simple segmentation
    mp query segmentation --event Purchase --from 2025-01-01 --to 2025-01-31

    # With property breakdown
    mp query segmentation --event Purchase --from 2025-01-01 --to 2025-01-31 \
        --on country --format table
    ```

### SegmentationResult

```python
result.event          # "Purchase"
result.dates          # ["2025-01-01", "2025-01-02", ...]
result.values         # {"$overall": [100, 150, ...]}
result.segments       # ["US", "UK", "DE", ...]
result.df             # pandas DataFrame
result.to_dict()      # JSON-serializable dict
```

## Funnels

Analyze conversion through a sequence of steps:

=== "Python"

    ```python
    # First, find your funnel ID
    funnels = ws.funnels()
    for f in funnels:
        print(f"{f.funnel_id}: {f.name}")

    # Query the funnel
    result = ws.funnel(
        funnel_id=12345,
        from_date="2025-01-01",
        to_date="2025-01-31"
    )

    # With segmentation
    result = ws.funnel(
        funnel_id=12345,
        from_date="2025-01-01",
        to_date="2025-01-31",
        on="properties.country"
    )

    # Access results
    for step in result.steps:
        print(f"{step.event}: {step.count} ({step.conversion_rate:.1%})")
    ```

=== "CLI"

    ```bash
    # List available funnels
    mp inspect funnels

    # Query a funnel
    mp query funnel --funnel-id 12345 --from 2025-01-01 --to 2025-01-31 --format table
    ```

### FunnelResult

```python
result.funnel_id       # 12345
result.steps           # [FunnelStep, ...]
result.overall_rate    # 0.15 (15% overall conversion)
result.df              # DataFrame with step metrics

# Each step
step.event             # "Checkout Started"
step.count             # 5000
step.conversion_rate   # 0.85
step.avg_time          # timedelta or None
```

## Retention

Cohort-based retention analysis:

=== "Python"

    ```python
    result = ws.retention(
        born_event="Signup",
        return_event="Login",
        from_date="2025-01-01",
        to_date="2025-01-31",
        born_where='properties["source"] == "organic"',
        unit="week"
    )

    # Access cohorts
    for cohort in result.cohorts:
        print(f"{cohort.date}: {cohort.size} users")
        print(f"  Retention: {cohort.retention_rates}")
    ```

=== "CLI"

    ```bash
    mp query retention \
        --born-event Signup \
        --return-event Login \
        --from 2025-01-01 \
        --to 2025-01-31 \
        --unit week \
        --format table
    ```

### RetentionResult

```python
result.born_event      # "Signup"
result.return_event    # "Login"
result.cohorts         # [CohortInfo, ...]
result.df              # DataFrame with retention matrix

# Each cohort
cohort.date            # "2025-01-01"
cohort.size            # 1000
cohort.retention_rates # [1.0, 0.45, 0.32, 0.28, ...]
```

## JQL (JavaScript Query Language)

Run custom JQL scripts for advanced analysis:

=== "Python"

    ```python
    script = """
    function main() {
        return Events({
            from_date: params.from_date,
            to_date: params.to_date,
            event_selectors: [{event: "Purchase"}]
        })
        .groupBy(["properties.country"], mixpanel.reducer.count())
        .sortDesc("value")
        .take(10);
    }
    """

    result = ws.jql(
        script=script,
        params={"from_date": "2025-01-01", "to_date": "2025-01-31"}
    )

    print(result.data)  # Raw JQL result
    print(result.df)    # As DataFrame
    ```

=== "CLI"

    ```bash
    # From file
    mp query jql --script ./query.js --param from_date=2025-01-01 --param to_date=2025-01-31

    # Inline
    mp query jql --script 'function main() { return Events({...}).count(); }'
    ```

## Event Counts

Multi-event time series comparison:

=== "Python"

    ```python
    result = ws.event_counts(
        events=["Signup", "Purchase", "Churn"],
        from_date="2025-01-01",
        to_date="2025-01-31",
        unit="day"
    )

    # DataFrame with columns: date, Signup, Purchase, Churn
    print(result.df)
    ```

=== "CLI"

    ```bash
    mp query event-counts \
        --event Signup --event Purchase --event Churn \
        --from 2025-01-01 --to 2025-01-31 \
        --format table
    ```

## Property Counts

Break down an event by property values:

=== "Python"

    ```python
    result = ws.property_counts(
        event="Purchase",
        property_name="country",
        from_date="2025-01-01",
        to_date="2025-01-31",
        limit=10
    )

    print(result.df)  # Columns: date, US, UK, DE, ...
    ```

=== "CLI"

    ```bash
    mp query property-counts \
        --event Purchase \
        --property country \
        --from 2025-01-01 --to 2025-01-31 \
        --limit 10 \
        --format table
    ```

## Activity Feed

Get a user's event history:

=== "Python"

    ```python
    result = ws.activity_feed(
        distinct_ids=["user_123", "user_456"],
        from_date="2025-01-01",
        to_date="2025-01-31"
    )

    for event in result.events:
        print(f"{event.time}: {event.event}")
        print(f"  Properties: {event.properties}")
    ```

=== "CLI"

    ```bash
    mp query activity-feed \
        --distinct-id user_123 \
        --from 2025-01-01 --to 2025-01-31 \
        --format json
    ```

## Saved Reports

Query saved reports from Mixpanel (Insights, Retention, Funnels, and Flows).

### Listing Bookmarks

First, find available saved reports:

=== "Python"

    ```python
    # List all saved reports
    bookmarks = ws.list_bookmarks()
    for b in bookmarks:
        print(f"{b.id}: {b.name} ({b.type})")

    # Filter by type
    insights = ws.list_bookmarks(bookmark_type="insights")
    funnels = ws.list_bookmarks(bookmark_type="funnels")
    ```

=== "CLI"

    ```bash
    mp inspect bookmarks
    mp inspect bookmarks --type insights
    mp inspect bookmarks --type funnels --format table
    ```

### Querying Saved Reports

Query Insights, Retention, or Funnel reports by bookmark ID:

!!! tip "Get Bookmark IDs First"
    Run `list_bookmarks()` or `mp inspect bookmarks` to find the numeric ID of the report you want to query.

=== "Python"

    ```python
    # Get the bookmark ID from list_bookmarks() first
    bookmarks = ws.list_bookmarks(bookmark_type="insights")
    bookmark_id = bookmarks[0].id  # e.g., 98765

    result = ws.query_saved_report(bookmark_id=bookmark_id)
    print(f"Report type: {result.report_type}")
    print(result.df)
    ```

=== "CLI"

    ```bash
    # First find your bookmark ID
    mp inspect bookmarks --type insights --format table

    # Then query it
    mp query saved-report --bookmark-id 98765 --format table
    ```

## Flows

Query saved Flows reports:

!!! tip "Flows Use Different IDs"
    Flows reports have their own bookmark IDs. Filter with `--type flows` when listing.

=== "Python"

    ```python
    # Get Flows bookmark ID
    flows = ws.list_bookmarks(bookmark_type="flows")
    bookmark_id = flows[0].id  # e.g., 54321

    result = ws.query_flows(bookmark_id=bookmark_id)
    print(f"Conversion rate: {result.overall_conversion_rate:.1%}")
    for step in result.steps:
        print(f"  {step}")
    ```

=== "CLI"

    ```bash
    # First find Flows bookmark IDs
    mp inspect bookmarks --type flows --format table

    # Then query it
    mp query flows --bookmark-id 54321 --format table
    ```

## Frequency Analysis

Analyze how often users perform an event:

=== "Python"

    ```python
    result = ws.frequency(
        event="Login",
        from_date="2025-01-01",
        to_date="2025-01-31",
        unit="month",
        addiction_unit="day"
    )

    # Distribution of logins per day
    print(result.buckets)  # {"0": 1000, "1": 500, "2-3": 300, ...}
    ```

=== "CLI"

    ```bash
    mp query frequency \
        --event Login \
        --from 2025-01-01 --to 2025-01-31 \
        --format table
    ```

## Numeric Aggregations

Aggregate numeric properties:

### Bucketing

```python
result = ws.segmentation_numeric(
    event="Purchase",
    from_date="2025-01-01",
    to_date="2025-01-31",
    on="properties.amount",
    type="general"  # or "linear", "logarithmic"
)
```

### Sum

```python
result = ws.segmentation_sum(
    event="Purchase",
    from_date="2025-01-01",
    to_date="2025-01-31",
    on="properties.amount"
)
# Total revenue per time period
```

### Average

```python
result = ws.segmentation_average(
    event="Purchase",
    from_date="2025-01-01",
    to_date="2025-01-31",
    on="properties.amount"
)
# Average purchase amount per time period
```

## API Escape Hatch

For Mixpanel APIs not covered by the Workspace class, use the `api` property to make authenticated requests directly:

=== "Python"

    ```python
    import mixpanel_data as mp

    ws = mp.Workspace()
    client = ws.api

    # Example: List annotations from the Annotations API
    # Many Mixpanel APIs require the project ID in the URL path
    base_url = "https://mixpanel.com/api/app"  # Use eu.mixpanel.com for EU
    url = f"{base_url}/projects/{client.project_id}/annotations"

    response = client.request("GET", url)
    annotations = response["results"]

    for ann in annotations:
        print(f"{ann['id']}: {ann['date']} - {ann['description']}")

    # Get a specific annotation by ID
    if annotations:
        annotation_id = annotations[0]["id"]
        detail_url = f"{base_url}/projects/{client.project_id}/annotations/{annotation_id}"
        annotation = client.request("GET", detail_url)
        print(annotation)
    ```

### Request Parameters

```python
client.request(
    "POST",
    "https://mixpanel.com/api/some/endpoint",
    params={"key": "value"},           # Query parameters
    json_body={"data": "payload"},     # JSON request body
    headers={"X-Custom": "header"},    # Additional headers
    timeout=60.0                       # Request timeout in seconds
)
```

Authentication is handled automatically — the client adds the proper `Authorization` header to all requests.

The client also exposes `project_id` and `region` properties, which are useful when constructing URLs for APIs that require these values in the path.

## Next Steps

- [Data Discovery](discovery.md) — Explore your event schema
- [API Reference](../api/workspace.md) — Complete API documentation
