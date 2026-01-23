# Usage Patterns & Best Practices

Common patterns and best practices for using the Mixpanel MCP server.

## Workflow Patterns

### Pattern 1: Exploration -> Query -> Download -> Analyze

For comprehensive analysis of a new dataset:

```
1. list_events()                          # What events exist?
2. top_events(limit=10)                   # Which are most active?
3. list_properties(event="top_event")     # What data is captured?
4. segmentation(event="top_event", ...)   # Quick trend analysis
5. fetch_events(from_date=..., to_date=...) # Download for deep analysis
6. sample(table="events")                 # Preview the data
7. sql("SELECT ... GROUP BY ...")         # Custom analysis
8. drop_table("events")                   # Clean up when done
```

### Pattern 2: Diagnostic Investigation

For root cause analysis of metric changes:

```
1. diagnose_metric_drop(event="signup", date="2024-01-07")
   # Automatic comparison of baseline vs drop period
   # Identifies contributing segments

2. cohort_comparison(
       cohort_a_filter='properties["source"] == "ads"',
       cohort_b_filter='properties["source"] == "organic"'
   )
   # Compare specific segments

3. ask_mixpanel("Why did signups drop last week?")
   # Natural language investigation
```

### Pattern 3: Product Health Monitoring

For regular product health checks:

```
1. product_health_dashboard(acquisition_event="signup")
   # AARRR snapshot with health scores

2. guided_analysis(focus_area="retention")
   # Interactive drill-down on weak areas

3. funnel_optimization_report(funnel_id=123)
   # Detailed bottleneck analysis

4. retention(born_event="signup", unit="week", interval_count=12)
   # Long-term retention trends
```

### Pattern 4: Safe Large-Scale Operations

For downloading large datasets:

```
1. safe_large_fetch(from_date="2024-01-01", to_date="2024-12-31")
   # Estimates count, requests confirmation if > 100k events

2. fetch_events(..., parallel=True, workers=4)
   # Use parallel fetching for large date ranges (>7 days)

3. Monitor progress via task tracking
   # fetch_events is task-enabled with progress reporting
```

---

## JSON Property Access in DuckDB SQL

Events and profiles store properties as JSON columns. Use DuckDB's JSON operators:

### Basic Access

```sql
-- Extract string property
SELECT properties->>'$.country' as country FROM events

-- Extract nested property
SELECT properties->>'$.user.plan' as plan FROM events

-- Filter by property value
SELECT * FROM events
WHERE properties->>'$.amount' > '100'
```

### Type Casting

```sql
-- Cast to integer for comparison
SELECT * FROM events
WHERE CAST(properties->>'$.amount' AS INTEGER) > 100

-- Cast to timestamp
SELECT * FROM events
WHERE CAST(properties->>'$.timestamp' AS TIMESTAMP) > '2024-01-01'
```

### Aggregation with Properties

```sql
-- Count by property value
SELECT
    properties->>'$.country' as country,
    COUNT(*) as count
FROM events
GROUP BY properties->>'$.country'
ORDER BY count DESC

-- Sum numeric property
SELECT
    properties->>'$.plan' as plan,
    SUM(CAST(properties->>'$.amount' AS DECIMAL)) as total
FROM events
GROUP BY properties->>'$.plan'
```

### Filtering with Multiple Properties

```sql
SELECT * FROM events
WHERE properties->>'$.platform' = 'mobile'
  AND properties->>'$.country' IN ('US', 'UK', 'CA')
  AND properties->>'$.is_premium' = 'true'
```

### Working with Arrays

```sql
-- Check if array contains value (using json_array_contains)
SELECT * FROM events
WHERE json_array_contains(properties->'$.tags', '"important"')
```

---

## Filter Expressions for API Calls

Filter expressions use a SQL-like syntax for the Mixpanel API.

### WHERE Parameter Syntax

```python
# Property comparison
where='properties["amount"] > 100'

# String equality
where='properties["country"] == "US"'

# IN operator
where='properties["plan"] in ["premium", "enterprise"]'

# Boolean
where='properties["is_active"] == true'

# NOT IN
where='properties["status"] not in ["cancelled", "suspended"]'

# Combining with AND/OR
where='properties["amount"] > 100 and properties["plan"] == "premium"'
where='(properties["country"] == "US") or (properties["country"] == "UK")'
```

### ON Parameter (Segmentation)

```python
# Segment by property (bare names auto-wrapped)
segmentation(event="purchase", on="country")

# Or explicit property accessor
segmentation(event="purchase", on='properties["country"]')
```

---

## Error Handling

All tools return structured errors with actionable information.

### Common Errors

| Error Code | Meaning | Action |
|------------|---------|--------|
| `TABLE_EXISTS_ERROR` | Table already exists | Use `append=True` or call `drop_table` first |
| `AUTHENTICATION_ERROR` | Invalid credentials | Check credentials with `workspace_info()` |
| `RATE_LIMIT_ERROR` | API rate limited | Wait `retry_after` seconds and retry |
| `EVENT_NOT_FOUND_ERROR` | Event doesn't exist | Check with `list_events()` |
| `DATE_RANGE_TOO_LARGE_ERROR` | >100 days without parallel | Use `parallel=True` |

### Error Response Structure

```json
{
  "code": "RATE_LIMIT_ERROR",
  "message": "Rate limit exceeded. Please wait before retrying.",
  "details": {
    "retry_after": 60,
    "limit": 60,
    "remaining": 0
  },
  "suggestions": [
    "Wait 60 seconds before retrying",
    "Consider batching requests"
  ]
}
```

---

## Rate Limiting

The MCP server includes automatic rate limiting.

### API Limits

| API | Limit | Tools Affected |
|-----|-------|----------------|
| Query API | 60 req/hour | `segmentation`, `funnel`, `retention`, `frequency`, `jql` |
| Export API | 3 req/sec | `fetch_events`, `fetch_profiles` |

### Best Practices

1. **Cache discovery calls** - Schema rarely changes; `list_events`, `list_funnels` are cached for 5 minutes
2. **Batch event counts** - Use `event_counts(events=[...])` instead of multiple `segmentation` calls
3. **Use composed tools** - `cohort_comparison` uses JQL for 1-2 API calls vs 80+ segmentation calls
4. **Fetch once, query locally** - Download data with `fetch_events`, then use `sql` for unlimited queries

---

## Tool Selection Guide

| Need | Tool | Why |
|------|------|-----|
| List events | `list_events` | Discovery, cached |
| Event trends | `segmentation` | Time series with optional segmentation |
| Compare cohorts | `cohort_comparison` | Efficient JQL-based comparison |
| Funnel conversion | `funnel` | Step-by-step conversion analysis |
| User retention | `retention` | Cohort retention curves |
| Custom queries | `jql` | Full JavaScript flexibility |
| Multiple event counts | `event_counts` | Batch multiple events efficiently |
| Property distribution | `property_counts` | Break down by property values |
| User activity | `activity_feed` | Chronological event history |
| Product overview | `product_health_dashboard` | AARRR metrics snapshot |
| Root cause analysis | `diagnose_metric_drop` | AI-powered investigation |
| Natural language | `ask_mixpanel` | Question -> query -> answer |
| Local SQL | `sql` | Unlimited queries on downloaded data |
| Safe large fetch | `safe_large_fetch` | Confirmation before large downloads |

---

## Middleware Behavior

### Caching

Discovery tools are cached for 5 minutes:
- `list_events`
- `list_properties`
- `list_funnels`
- `list_cohorts`
- `list_bookmarks`
- `top_events`

### Audit Logging

All requests are logged with:
- Tool name
- Start/end time
- Success/failure status
- Error details if applicable

### Rate Limiting

Rate limits are applied per tool category:
- Query tools share a 60/hour limit
- Export tools share a 3/second limit
- Discovery tools are not rate-limited (cached instead)

---

## Task-Enabled Tools

Some tools support progress reporting and cancellation:

- `fetch_events` - Reports progress by day for long date ranges
- `fetch_profiles` - Reports progress by page

### Cancellation Behavior

When cancelled, these tools return partial results:
```json
{
  "status": "cancelled",
  "table_name": "events",
  "row_count": 25000,
  "days_fetched": 5,
  "message": "Cancelled after 5/10 days"
}
```

---

## Integration Patterns

### With External Tools

```bash
# Export to CSV via streaming
stream_events(...) | jq -r '[.event, .distinct_id] | @csv' > events.csv

# Pipe to pandas
fetch_events(...) && python -c "import pandas; df = ..."
```

### With Other MCP Servers

```
# Read context from Mixpanel
Read workspace://info from mixpanel

# Use in analysis prompt
Use the connected project {project_id} for analysis
```

### Combining Tools

```
# Pattern: Discover -> Analyze -> Detail

1. list_funnels() -> Get funnel IDs
2. funnel(funnel_id=X, ...) -> Get conversion data
3. diagnose_metric_drop(event=bottom_step, date=drop_date) -> Investigate drops
```
