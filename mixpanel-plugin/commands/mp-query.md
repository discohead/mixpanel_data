---
description: Interactive query builder for SQL and JQL queries on Mixpanel data
allowed-tools: Bash(mp query:*), Bash(mp inspect:*)
argument-hint: [sql|jql|segmentation|funnel|retention]
---

# Mixpanel Query Builder

Guide the user through building and executing queries on their Mixpanel data.

## Query Type Selection

Determine query type from `$1` or ask the user:

1. **sql** - Query local DuckDB tables with SQL
2. **jql** - Execute JavaScript Query Language for complex transformations
3. **segmentation** - Time-series event analysis with breakdowns
4. **funnel** - Conversion analysis through saved funnel steps
5. **retention** - Cohort retention analysis

## Available Data Context

Check what data is available:

```bash
!$(mp inspect tables --format table 2>/dev/null || echo "No tables found. Run /mp-fetch first.")
```

If no tables exist and user selects SQL, suggest running `/mp-fetch` first or `/mp-inspect` to explore live schema.

---

## SQL Queries (Local DuckDB)

### 1. Show Available Tables

```bash
!$(mp inspect tables --format table)
```

### 2. Quick Table Preview

For each table, offer to show:
- Schema: `mp inspect schema -t <table>`
- Sample: `mp query sql "SELECT * FROM <table> LIMIT 5" --format table`
- Event breakdown: `mp inspect breakdown -t <table> --format table`

### 3. Build SQL Query

Help construct the query based on user needs:

**Common query patterns**:

**Event counts by day**:
```sql
SELECT
  DATE_TRUNC('day', event_time) as day,
  event_name,
  COUNT(*) as count
FROM events
GROUP BY 1, 2
ORDER BY 1 DESC
```

**User activity**:
```sql
SELECT
  COUNT(DISTINCT distinct_id) as unique_users,
  COUNT(*) as total_events
FROM events
WHERE event_time >= '2024-01-01'
```

**Property analysis** (JSON extraction):
```sql
SELECT
  properties->>'$.country' as country,
  COUNT(*) as events,
  COUNT(DISTINCT distinct_id) as users
FROM events
WHERE event_name = 'Purchase'
GROUP BY 1
ORDER BY 2 DESC
```

**Numeric aggregation**:
```sql
SELECT
  DATE_TRUNC('day', event_time) as day,
  SUM(CAST(properties->>'$.amount' AS DOUBLE)) as revenue,
  AVG(CAST(properties->>'$.amount' AS DOUBLE)) as avg_order
FROM events
WHERE event_name = 'Purchase'
GROUP BY 1
ORDER BY 1
```

### 4. Execute Query

```bash
mp query sql "<query>" --format table
```

**Output format options**:
- `--format table` - Human-readable (default for exploration)
- `--format json` - Machine processing
- `--format csv` - Export to spreadsheet

**Next steps after query**:
- Deep column analysis → Run `/mp-inspect column -t <table> -c <column>` for statistics
- Explore workflow analysis → Run `/mp-funnel` or `/mp-retention` for specialized analytics

---

## JQL Queries (JavaScript Query Language)

### 1. Explain JQL Use Case

JQL is for:
- Complex event transformations
- User-level aggregations
- Custom reducers and bucketing
- Advanced funnel logic

### 2. Build JQL Script

Help construct based on analysis needs:

**Basic event count**:
```javascript
function main() {
  return Events({
    from_date: '2024-01-01',
    to_date: '2024-01-31'
  }).reduce(mixpanel.reducer.count());
}
```

**Group by property**:
```javascript
function main() {
  return Events({
    from_date: '2024-01-01',
    to_date: '2024-01-31',
    event_selectors: [{event: 'Purchase'}]
  })
  .groupBy(['properties.country'], [
    mixpanel.reducer.count(),
    mixpanel.reducer.sum('properties.amount')
  ])
  .sortDesc('value');
}
```

**User-level analysis**:
```javascript
function main() {
  return Events({
    from_date: '2024-01-01',
    to_date: '2024-01-31'
  })
  .groupByUser(mixpanel.reducer.count())
  .filter(function(item) {
    return item.value > 10; // Active users with >10 events
  });
}
```

### 3. Save and Execute

Save the script to a file (e.g., `analysis.js`):

```bash
mp query jql analysis.js --format table
```

With parameters:
```bash
mp query jql analysis.js \
  --param from_date=2024-01-01 \
  --param to_date=2024-01-31 \
  --format table
```

---

## Segmentation Queries (Live API)

Time-series event analysis with optional property breakdown.

### Required Parameters

- **Event**: Event name to analyze
- **From date**: Start date (YYYY-MM-DD)
- **To date**: End date (YYYY-MM-DD)

### Optional Parameters

- **Segment by** (`--on`): Property to break down by (e.g., `country`, `plan`)
- **Unit** (`--unit`): Time granularity (`day`, `week`, `month`)
- **Filter** (`--where`): Filter expression

### Examples

**Basic event trend**:
```bash
mp query segmentation -e "Purchase" \
  --from 2024-01-01 \
  --to 2024-01-31 \
  --format table
```

**Segmented by property**:
```bash
mp query segmentation -e "Purchase" \
  --from 2024-01-01 \
  --to 2024-01-31 \
  --on country \
  --format table
```

**With filter**:
```bash
mp query segmentation -e "Purchase" \
  --from 2024-01-01 \
  --to 2024-01-31 \
  --on plan \
  --where 'properties["amount"] > 100' \
  --format table
```

---

## Funnel Queries (Live API)

Analyze conversion through saved funnel steps.

### 1. List Available Funnels

```bash
!$(mp inspect funnels --format table)
```

### 2. Select Funnel

Ask user to choose funnel by ID from the list.

### 3. Execute Funnel Analysis

```bash
mp query funnel <funnel-id> \
  --from 2024-01-01 \
  --to 2024-01-31 \
  --format table
```

**Optional**:
- `--unit day|week|month` - Time granularity
- `--on property` - Segment by property

---

## Retention Queries (Live API)

Cohort retention analysis.

### Required Parameters

- **Born event**: Event defining cohort entry (e.g., "Sign Up")
- **Return event**: Event defining return (e.g., "Login")
- **From/To dates**: Analysis period

### Example

```bash
mp query retention \
  --born "Sign Up" \
  --return "Login" \
  --from 2024-01-01 \
  --to 2024-01-31 \
  --unit week \
  --format table
```

**With filters**:
```bash
mp query retention \
  --born "Sign Up" \
  --return "Purchase" \
  --from 2024-01-01 \
  --to 2024-01-31 \
  --born-where 'properties["source"] == "organic"' \
  --return-where 'properties["amount"] > 50' \
  --format table
```

---

## Output and Next Steps

After query execution:

1. **Review results** in chosen format
2. **Refine query** if needed based on results
3. **Export data** using `--format csv` for spreadsheets
4. **Visualize** using Python + pandas (refer to skill patterns.md)
5. **Save query** to project for reuse

## Query Optimization Tips

**For SQL**:
- Use `LIMIT` during exploration
- Filter early with WHERE clauses
- Index on commonly filtered columns isn't needed (DuckDB is fast)
- Use `DATE_TRUNC` for time-based grouping

**For JQL**:
- Filter with `event_selectors` rather than `.filter()` when possible
- Limit date ranges for faster results
- Use `groupByUser` for per-user analysis
- Leverage built-in reducers for common aggregations

**For Live Queries**:
- Smaller date ranges = faster results
- Cache results locally for repeated analysis
- Use SQL on fetched data for complex queries

## Troubleshooting

**"No tables found"**: Run `/mp-fetch` first to get local data
**"Event not found"**: Check `mp inspect events` for available events
**"Invalid query"**: Check SQL/JQL syntax in skill reference files
**"Rate limit"**: Wait before retrying live queries
**"Authentication error"**: Run `/mp-auth` to reconfigure credentials
