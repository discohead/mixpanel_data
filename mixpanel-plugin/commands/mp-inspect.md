---
description: Explore Mixpanel schema and local data structure
allowed-tools: Bash(mp inspect:*), Bash(mp query:*)
argument-hint: [operation] [table-name]
---

# Mixpanel Data Inspector

Explore Mixpanel schema, discover events, and analyze data structure.

## Pre-flight Check

Check credentials and local data availability:

```bash
!$(mp auth test 2>&1 || echo "⚠️  No credentials configured")
!$(mp inspect tables --format table 2>/dev/null || echo "No local tables found")
```

If no credentials: Suggest running `/mp-auth` first.

## Context Detection

Guide based on data availability:

- **No local tables**: Focus on live schema discovery (events, properties, funnels, cohorts)
- **Tables exist**: Offer both local exploration and live discovery
- **No credentials but tables exist**: Focus on local data exploration

## Operation Selection

Choose an inspection operation from `$1` or present menu:

### Category 1: Discover Schema (Live API)
1. **events** - List all tracked event names
2. **properties** - List properties for a specific event
3. **funnels** - List saved funnels
4. **cohorts** - List saved cohorts

### Category 2: Explore Local Data
5. **tables** - List local DuckDB tables
6. **schema** - Show table column definitions
7. **sample** - Preview random rows from table
8. **breakdown** - Event distribution in table

### Category 3: Analyze Patterns
9. **keys** - JSON property keys in table
10. **column** - Deep column statistics
11. **distribution** - Property value distribution (JQL)
12. **daily** - Daily event counts (JQL)

---

## Operation 1: events - List All Events

Discover all event names tracked in your Mixpanel project.

```bash
!$(mp inspect events --format table)
```

**Output**: List of all event names alphabetically sorted.

**Chain suggestions:**
- Pick an interesting event → Run `/mp-inspect properties <event-name>` to see its properties
- Ready to fetch specific events? → Run `/mp-fetch` with filtered event list
- Want to see trending events? → Use CLI: `mp inspect top-events --format table`

---

## Operation 2: properties - Event Properties

Show all properties tracked for a specific event.

### Determine Event Name

- Use `$2` if provided (e.g., `/mp-inspect properties PageView`)
- Otherwise, ask user for event name
- Suggest running `events` operation first if unsure

### Execute

```bash
!$(mp inspect properties -e "<event-name>" --format table)
```

**Output**: Property names, data types, and example values.

**Chain suggestions:**
- Check property values → Run `/mp-inspect distribution <property-name>`
- Use in fetch filter → Run `/mp-fetch` with WHERE clause on this property
- Query locally → Fetch data first, then use `/mp-query sql` with `properties->>'$.propname'`

---

## Operation 3: funnels - Saved Funnels

List all saved funnel definitions in your Mixpanel project.

```bash
!$(mp inspect funnels --format table)
```

**Output**: Funnel ID, name, and step count.

**Chain suggestions:**
- Analyze specific funnel → Run `/mp-funnel <funnel-id>`
- Create custom funnel → Run `/mp-funnel` and choose custom option
- See funnel details → Use CLI: `mp query funnel <funnel-id> --from <date> --to <date>`

---

## Operation 4: cohorts - Saved Cohorts

List all saved cohorts in your Mixpanel project.

```bash
!$(mp inspect cohorts --format table)
```

**Output**: Cohort ID, name, count, and description.

**Chain suggestions:**
- Fetch cohort profiles → Use CLI: `mp fetch profiles --cohort <cohort-id>`
- Analyze cohort behavior → Run `/mp-retention` with cohort context
- Filter events by cohort → Use in `/mp-fetch` WHERE clause

---

## Operation 5: tables - Local Tables

List all DuckDB tables in your local workspace.

```bash
!$(mp inspect tables --format table)
```

**Output**: Table names, row counts, and last fetch timestamp.

**Chain suggestions:**
- No tables? → Run `/mp-fetch` to get started
- Explore table structure → Run `/mp-inspect schema <table-name>`
- Preview data → Run `/mp-inspect sample <table-name>`
- See event distribution → Run `/mp-inspect breakdown <table-name>`

---

## Operation 6: schema - Table Schema

Show column definitions for a specific table.

### Determine Table Name

- Use `$2` if provided (e.g., `/mp-inspect schema events`)
- Otherwise, list tables and ask user to choose
- Run `tables` operation first if needed

### Execute

```bash
!$(mp inspect schema -t "<table-name>" --format table)
```

**Output**: Column names, data types, and nullable status.

**Key columns:**
- `event_name` - Event type identifier
- `event_time` - Timestamp of event
- `distinct_id` - User identifier
- `properties` - JSON column with all event properties

**Chain suggestions:**
- Preview data → Run `/mp-inspect sample <table-name>`
- See what events exist → Run `/mp-inspect breakdown <table-name>`
- Query the table → Run `/mp-query sql` with this table
- Explore JSON properties → Run `/mp-inspect keys <table-name>`

---

## Operation 7: sample - Preview Data

Show random sample rows from a table.

### Determine Table and Sample Size

- Table: Use `$2` if provided, otherwise ask
- Sample size: Default 10 rows, can specify with `-n` flag

### Execute

```bash
!$(mp inspect sample -t "<table-name>" -n 10 --format table)
```

**Output**: Random rows with all columns.

**Interpreting JSON properties:**
- Properties are stored as JSON: `{"country": "US", "plan": "pro"}`
- Use `properties->>'$.key'` in SQL to extract values
- Run `/mp-inspect keys` to see all available property keys

**Chain suggestions:**
- See all property keys → Run `/mp-inspect keys <table-name>`
- Analyze specific column → Run `/mp-inspect column <table-name> <column-name>`
- Build SQL query → Run `/mp-query sql` to analyze data

---

## Operation 8: breakdown - Event Distribution

Show event counts, unique users, and date ranges for each event in a table.

### Determine Table Name

- Use `$2` if provided
- Otherwise, list tables and ask user to choose

### Execute

```bash
!$(mp inspect breakdown -t "<table-name>" --format table)
```

**Output**: For each event:
- Event name
- Total event count
- Unique user count
- First and last occurrence dates

**Chain suggestions:**
- Analyze specific event → Filter in `/mp-query sql` with WHERE clause
- Build funnel → Run `/mp-funnel` with discovered events
- Time-series analysis → Run `/mp-inspect daily <event-name>`

---

## Operation 9: keys - JSON Property Keys

Show all unique JSON property keys in a table, optionally filtered by event.

### Determine Parameters

- Table: Use `$2` if provided, otherwise ask
- Event filter: Optional, use `-e` flag to filter by specific event

### Execute

**All events:**
```bash
!$(mp inspect keys -t "<table-name>" --format table)
```

**Specific event:**
```bash
!$(mp inspect keys -t "<table-name>" -e "<event-name>" --format table)
```

**Output**: List of property keys found in the JSON properties column.

**Using property keys in SQL:**
```sql
-- Extract property value
SELECT properties->>'$.country' as country FROM events

-- Filter by property
SELECT * FROM events WHERE properties->>'$.plan' = 'pro'

-- Aggregate by property
SELECT
  properties->>'$.country' as country,
  COUNT(*) as events
FROM events
GROUP BY 1
```

**Chain suggestions:**
- Deep dive on property → Run `/mp-inspect column` with property path
- Check property distribution → Run `/mp-inspect distribution <property-name>`
- Use in query → Run `/mp-query sql` with `properties->>'$.key'` syntax

---

## Operation 10: column - Column Analysis

Perform deep statistical analysis on a specific column.

### Determine Parameters

- Table: Required
- Column: Required (can be JSON path like `properties->>'$.country'`)

### Execute

**Simple column:**
```bash
!$(mp inspect column -t "<table-name>" -c "<column-name>" --format table)
```

**JSON property:**
```bash
!$(mp inspect column -t "<table-name>" -c "properties->>'$.country'" --top 20 --format table)
```

**Output**:
- Null count and percentage
- Cardinality (distinct values)
- Top values with counts
- For numeric columns: min, max, avg, median, stddev

**Chain suggestions:**
- High cardinality? → May need grouping or binning in analysis
- Low cardinality? → Good candidate for segmentation/breakdown
- Many nulls? → Check data quality, may need filtering
- Use in segmentation → Run `/mp-query segmentation --on <property>`

---

## Operation 11: distribution - Property Distribution

Analyze value distribution for a property using JQL (JavaScript Query Language).

### Required Parameters

- Property name (e.g., `country`, `plan`, `device_type`)
- Date range: `--from` and `--to` flags

### Execute

```bash
!$(mp query jql - --from <from-date> --to <to-date> << 'EOF'
function main() {
  return Events({
    from_date: params.from_date,
    to_date: params.to_date
  })
  .groupBy(['properties.<property-name>'], mixpanel.reducer.count())
  .sortDesc('value');
}
EOF
)
```

**Output**: Property values with counts and percentages.

**Chain suggestions:**
- Fetch filtered data → Run `/mp-fetch` with WHERE clause on high-value properties
- Local analysis → Fetch data, then use `/mp-query sql` for complex queries
- Segmentation → Run `/mp-query segmentation --on <property>` for time-series

---

## Operation 12: daily - Daily Event Counts

Show daily event counts over time using JQL.

### Parameters

- Event name: Optional filter (use `-e` flag)
- Date range: `--from` and `--to` flags

### Execute

**All events:**
```bash
!$(mp query jql - --from <from-date> --to <to-date> << 'EOF'
function main() {
  return Events({
    from_date: params.from_date,
    to_date: params.to_date
  })
  .groupBy(['day'], mixpanel.reducer.count())
  .sortAsc('key.0');
}
EOF
)
```

**Specific event:**
```bash
!$(mp query jql - --from <from-date> --to <to-date> << 'EOF'
function main() {
  return Events({
    from_date: params.from_date,
    to_date: params.to_date,
    event_selectors: [{event: '<event-name>'}]
  })
  .groupBy(['day'], mixpanel.reducer.count())
  .sortAsc('key.0');
}
EOF
)
```

**Output**: Daily counts showing trends and patterns.

**Chain suggestions:**
- See detailed breakdown → Run `/mp-query segmentation` with property breakdown
- Fetch period data → Run `/mp-fetch` for date range with high activity
- Retention analysis → Run `/mp-retention` to analyze user retention

---

## Next Steps

After inspecting your data:

- **Discovered interesting events?** → Run `/mp-fetch` to get them locally
- **Ready to analyze?** → Run `/mp-query` to execute SQL or JQL queries
- **Need funnel analysis?** → Run `/mp-funnel` for conversion analysis
- **Need retention analysis?** → Run `/mp-retention` for user retention curves
- **Want a report?** → Run `/mp-report` to generate comprehensive analysis

## Troubleshooting

### No Credentials Configured

If `mp auth test` fails:
- Run `/mp-auth` to setup credentials first

### No Local Tables

If `mp inspect tables` shows no tables:
- Run `/mp-fetch` to fetch data first
- Or use live discovery operations (events, properties, funnels, cohorts)

### Event/Property Not Found

If inspection fails with "not found":
- Verify event name is correct (case-sensitive)
- Check property exists with `/mp-inspect properties -e <event>`
- Use `/mp-inspect events` to see all available events

### JQL Operations Slow

If distribution/daily operations timeout:
- Reduce date range (Mixpanel API limit: 60 days recommended)
- Use local SQL queries after fetching data with `/mp-fetch`
- Check Mixpanel project size (large projects may be slower)
