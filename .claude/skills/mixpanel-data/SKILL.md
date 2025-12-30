---
name: mixpanel-data
description: Analyze Mixpanel analytics data using the mixpanel_data Python library or mp CLI. Use when working with Mixpanel event data, user profiles, funnels, retention, cohorts, segmentation queries, JQL scripts, or SQL analysis on local DuckDB. Supports filter expressions for WHERE/ON clauses, JQL (JavaScript Query Language) for complex transformations, Python scripts with pandas integration, and CLI pipelines with jq/Unix tools. Triggers on mentions of Mixpanel, event analytics, funnel analysis, retention curves, user behavior tracking, JQL queries, filter expressions, or requests to fetch/query analytics data.
---

# Mixpanel Data Analysis

Fetch Mixpanel data once into local DuckDB, then query repeatedly with SQL—preserving context for reasoning rather than consuming it with raw API responses.

## Documentation Access

Full documentation is hosted at **https://jaredmcfarland.github.io/mixpanel_data/** with LLM-optimized access:

| Resource | URL | Use Case |
|----------|-----|----------|
| **llms.txt** | `https://jaredmcfarland.github.io/mixpanel_data/llms.txt` | Index of all docs with descriptions |
| **llms-full.txt** | `https://jaredmcfarland.github.io/mixpanel_data/llms-full.txt` | Complete documentation (~400KB) |
| **Individual pages** | `https://jaredmcfarland.github.io/mixpanel_data/{path}/index.md` | Specific topic deep-dive |

### When to Fetch Documentation

- **Use this skill** for quick patterns, common examples, and API summaries
- **Fetch llms.txt** to discover what documentation exists
- **Fetch llms-full.txt** when you need comprehensive reference (API signatures, all parameters, edge cases)
- **Fetch individual .md** for focused deep-dives (e.g., `/api/workspace/index.md` for Workspace class details)

### Documentation Structure

| Path | Content |
|------|---------|
| `/getting-started/installation/index.md` | Installation options |
| `/getting-started/quickstart/index.md` | 5-minute tutorial |
| `/getting-started/configuration/index.md` | Credentials and config |
| `/guide/fetching/index.md` | Fetching events/profiles |
| `/guide/streaming/index.md` | Streaming without storage |
| `/guide/sql-queries/index.md` | DuckDB SQL patterns |
| `/guide/live-analytics/index.md` | Segmentation, funnels, retention |
| `/guide/discovery/index.md` | Schema exploration |
| `/api/workspace/index.md` | Workspace class reference |
| `/api/auth/index.md` | Authentication module |
| `/api/exceptions/index.md` | Exception hierarchy |
| `/api/types/index.md` | Result types |
| `/cli/commands/index.md` | CLI command reference |

## When to Use

### Python Library (`mixpanel_data`)
- Building scripts, notebooks, or data pipelines
- Need DataFrame results for pandas/visualization
- Complex multi-step analysis
- Programmatic credential management

### CLI (`mp`)
- Quick one-off queries
- Shell scripting or Unix pipelines
- Streaming data to jq, awk, or other tools
- Non-Python environments

## Two Data Paths

### Path 1: Live Queries (Quick Answers)
Call Mixpanel API directly for real-time metrics without local storage.

```python
# Python
result = ws.segmentation("Purchase", from_date="2024-01-01", to_date="2024-01-31", on="country")
print(result.df)
```

```bash
# CLI
mp query segmentation -e Purchase --from 2024-01-01 --to 2024-01-31 --on country
```

### Path 2: Local Analysis (Deep Analysis)
Fetch data into DuckDB, then query with SQL repeatedly.

```python
# Python
ws.fetch_events("events", from_date="2024-01-01", to_date="2024-01-31")
df = ws.sql("SELECT event_name, COUNT(*) FROM events GROUP BY 1")
```

```bash
# CLI
mp fetch events --from 2024-01-01 --to 2024-01-31
mp query sql "SELECT event_name, COUNT(*) FROM events GROUP BY 1"
```

### Path 3: Streaming (Pipelines)
Stream to stdout for processing with external tools.

```bash
mp fetch events --from 2024-01-01 --to 2024-01-01 --stdout | jq '.event'
mp fetch events --stdout | jq -r '[.event, .distinct_id] | @csv' > events.csv
```

## JSON Property Access (Critical)

Events and profiles store properties as JSON. Access with:

```sql
-- DuckDB SQL (local queries)
SELECT properties->>'$.country' as country FROM events
SELECT CAST(properties->>'$.amount' AS DOUBLE) as amount FROM events
WHERE properties->>'$.plan' = 'premium'
```

```python
# Python streaming
for event in ws.stream_events(from_date="2024-01-01", to_date="2024-01-01"):
    print(event["properties"]["country"])
```

```bash
# CLI + jq
mp fetch events --stdout | jq '.properties.country'
mp fetch events --stdout | jq 'select(.properties.plan == "premium")'
```

## Filter Expressions (WHERE/ON)

Filter expressions use SQL-like syntax for filtering and segmenting data in API calls.

### ON Parameter (Segmentation)
Accepts bare property names (auto-wrapped) or full expressions:
```bash
# Bare name (auto-wrapped to properties["country"])
mp query segmentation -e Purchase --on country

# Full expression
mp query segmentation -e Purchase --on 'properties["country"]'
```

```python
ws.segmentation("Purchase", from_date="2024-01-01", to_date="2024-01-31", on="country")
```

### WHERE Parameter (Filtering)
Always uses full expression syntax:
```bash
mp fetch events --where 'properties["amount"] > 100 and properties["plan"] in ["premium", "enterprise"]'
mp query segmentation -e Purchase --on country --where 'properties["amount"] > 100'
```

```python
ws.fetch_events("events", from_date="2024-01-01", to_date="2024-01-31",
                where='properties["country"] == "US"')
ws.segmentation("Purchase", from_date="2024-01-01", to_date="2024-01-31",
                on="country", where='properties["amount"] > 100')
```

### Expression Syntax
```javascript
// Comparison
properties["age"] > 18
properties["status"] != "deleted"

// Logical
properties["plan"] == "premium" and properties["active"] == true
properties["source"] == "web" or properties["source"] == "mobile"

// Set operations
properties["country"] in ["US", "CA", "UK"]

// Existence
defined(properties["email"])
```

## JQL (JavaScript Query Language)

Full JavaScript-based query language for complex transformations.

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

```bash
mp query jql script.js --param from_date=2024-01-01 --param to_date=2024-01-31
```

```python
result = ws.jql(script, params={"from_date": "2024-01-01", "to_date": "2024-01-31"})
df = result.df
```

For complete filter expression and JQL reference, see [references/query-expressions.md](references/query-expressions.md).

## Credentials

Resolution priority:
1. Environment variables: `MP_USERNAME`, `MP_SECRET`, `MP_PROJECT_ID`, `MP_REGION`
2. Named account: `Workspace(account="prod")` or `mp --account prod`
3. Default account from `~/.mp/config.toml`

## Quick Start Examples

### Python: Fetch and Analyze

```python
import mixpanel_data as mp

ws = mp.Workspace()
ws.fetch_events("jan", from_date="2024-01-01", to_date="2024-01-31")

# SQL queries
df = ws.sql("""
    SELECT properties->>'$.country' as country, COUNT(*) as cnt
    FROM jan GROUP BY 1 ORDER BY 2 DESC
""")

# Introspection
ws.event_breakdown("jan")  # Event distribution
ws.summarize("jan")        # Column statistics

ws.close()
```

### Python: Ephemeral Workspace

```python
with mp.Workspace.ephemeral() as ws:
    ws.fetch_events("events", from_date="2024-01-01", to_date="2024-01-01")
    count = ws.sql_scalar("SELECT COUNT(*) FROM events")
# Database automatically deleted
```

### CLI: Discover and Fetch

```bash
# Discover available events
mp inspect events --format table

# Fetch events to local database
mp fetch events --from 2024-01-01 --to 2024-01-31

# Query locally
mp query sql "SELECT COUNT(*) FROM events" --format table
mp inspect breakdown -t events  # Event distribution
```

### CLI: Live Queries

```bash
# Segmentation
mp query segmentation -e Purchase --from 2024-01-01 --to 2024-01-31 --on country

# Funnel (requires saved funnel ID)
mp inspect funnels  # List funnels to get ID
mp query funnel 12345 --from 2024-01-01 --to 2024-01-31

# Retention
mp query retention --born "Sign Up" --return "Purchase" --from 2024-01-01 --to 2024-01-31
```

## Data Storage Schema

Events table:
```sql
CREATE TABLE events (
    event_name VARCHAR NOT NULL,
    event_time TIMESTAMP NOT NULL,
    distinct_id VARCHAR NOT NULL,
    insert_id VARCHAR PRIMARY KEY,
    properties JSON
)
```

Profiles table:
```sql
CREATE TABLE profiles (
    distinct_id VARCHAR PRIMARY KEY,
    properties JSON,
    last_seen TIMESTAMP
)
```

## Output Formats (CLI)

| Format | Use Case |
|--------|----------|
| `--format json` | Machine processing (default) |
| `--format jsonl` | Streaming pipelines |
| `--format table` | Human inspection |
| `--format csv` | Spreadsheets |
| `--format plain` | Minimal output |

## API Reference Summary

### Discovery Methods
| Method | Description |
|--------|-------------|
| `events()` | List all event names |
| `properties(event)` | List properties for an event |
| `property_values(name, event, limit)` | Sample property values |
| `funnels()` | List saved funnels |
| `cohorts()` | List saved cohorts |
| `top_events(type, limit)` | Today's trending events |
| `list_bookmarks(type)` | Saved reports by type |

### Fetching Methods
| Method | Description |
|--------|-------------|
| `fetch_events(name, from_date, to_date, ...)` | Fetch events to table |
| `fetch_profiles(name, ...)` | Fetch profiles to table |
| `stream_events(...)` | Iterator without storage |
| `stream_profiles(...)` | Iterator without storage |

### Local Query Methods
| Method | Description |
|--------|-------------|
| `sql(query)` | Execute SQL, return DataFrame |
| `sql_scalar(query)` | Execute SQL, return single value |
| `sql_rows(query)` | Execute SQL, return list of tuples |

### Live Query Methods
| Method | Description |
|--------|-------------|
| `segmentation(event, from_date, to_date, on, unit, where)` | Time-series breakdown |
| `funnel(funnel_id, from_date, to_date, unit, on)` | Funnel conversion |
| `retention(born_event, return_event, ...)` | Cohort retention |
| `jql(script, params)` | Custom JQL script |
| `event_counts(events, from_date, to_date, type, unit)` | Multi-event counts |

### Introspection Methods
| Method | Description |
|--------|-------------|
| `info()` | Workspace metadata |
| `tables()` | List tables with row counts |
| `table_schema(table)` | Column definitions |
| `sample(table, n)` | Random sample rows |
| `summarize(table)` | Column statistics |
| `event_breakdown(table)` | Per-event statistics |

For complete method signatures, see [references/library-api.md](references/library-api.md).
For CLI commands, see [references/cli-commands.md](references/cli-commands.md).
For filter expressions and JQL, see [references/query-expressions.md](references/query-expressions.md).
For pandas/jq integration patterns, see [references/patterns.md](references/patterns.md).
For documentation access and URLs, see [references/documentation.md](references/documentation.md).

## Common Errors

| Error | Cause | Solution |
|-------|-------|----------|
| `TableExistsError` | Table already exists | Use `--replace` or `--append` |
| `AuthenticationError` | Invalid credentials | Check `mp auth test` |
| `RateLimitError` | API rate limited | Wait for retry_after seconds |
| `DateRangeTooLargeError` | >100 days range | Split into smaller chunks |
| `EventNotFoundError` | Event not in project | Check `mp inspect events` |
