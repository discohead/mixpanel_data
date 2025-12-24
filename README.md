# mixpanel_data

[![PyPI](https://img.shields.io/pypi/v/mixpanel_data)](https://pypi.org/project/mixpanel_data/)
[![Python](https://img.shields.io/pypi/pyversions/mixpanel_data)](https://pypi.org/project/mixpanel_data/)
[![License](https://img.shields.io/github/license/discohead/mixpanel_data)](LICENSE)

A Python library and CLI for working with Mixpanel analytics data—fetch once, query repeatedly with SQL, or stream directly to ETL pipelines.

## Why mixpanel_data?

Every Mixpanel API call returns JSON that must be parsed, transformed, and reasoned about. For AI coding agents, this consumes valuable context window tokens. For data analysts, it means repetitive API calls.

**mixpanel_data** solves this by fetching data into a local [DuckDB](https://duckdb.org) database. Query it with SQL as many times as needed. Data lives on disk; only answers flow back.

## Installation

```bash
pip install mixpanel_data
```

Requires Python 3.11+. Verify installation:

```bash
mp --version
```

## Quick Start

### 1. Configure Credentials

```bash
# Interactive prompt (secure, recommended)
mp auth add production --username sa_xxx --project 12345 --region us
# You'll be prompted for the secret with hidden input

mp auth test  # Verify connection
```

Alternative methods for CI/CD:

```bash
# Via environment variable
MP_SECRET=xxx mp auth add production --username sa_xxx --project 12345

# Via stdin
echo "$SECRET" | mp auth add production --username sa_xxx --project 12345 --secret-stdin
```

Or set all credentials as environment variables: `MP_USERNAME`, `MP_SECRET`, `MP_PROJECT_ID`, `MP_REGION`

### 2. Explore Your Data

```bash
mp inspect events                      # List all events
mp inspect properties --event Purchase # Properties for an event
mp inspect funnels                     # Saved funnels
```

### 3. Fetch Events to Local Storage

```bash
mp fetch events jan --from 2024-01-01 --to 2024-01-31
```

### 4. Query with SQL

```bash
mp query sql "SELECT event_name, COUNT(*) FROM jan GROUP BY 1 ORDER BY 2 DESC" --format table
```

### 5. Run Live Analytics

```bash
mp query segmentation --event Purchase --from 2024-01-01 --to 2024-01-31 --on country
```

### 6. Or Stream Directly (No Storage)

```bash
# Stream events as JSONL for piping to other tools
mp fetch events --from 2024-01-01 --to 2024-01-31 --stdout | jq '.event_name'
```

## Python API

```python
import mixpanel_data as mp

ws = mp.Workspace()

# Fetch events into local DuckDB
ws.fetch_events("jan", from_date="2024-01-01", to_date="2024-01-31")

# Query with SQL — returns pandas DataFrame
df = ws.sql("""
    SELECT
        DATE_TRUNC('day', event_time) as day,
        event_name,
        COUNT(*) as count
    FROM jan
    GROUP BY 1, 2
    ORDER BY 1, 3 DESC
""")

# Or run live queries against Mixpanel API
result = ws.segmentation(
    event="Purchase",
    from_date="2024-01-01",
    to_date="2024-01-31",
    on="properties.country"
)
print(result.df)
```

### Ephemeral Workspaces

For one-off analysis without persisting data:

```python
with mp.Workspace.ephemeral() as ws:
    ws.fetch_events("events", from_date="2024-01-01", to_date="2024-01-07")
    total = ws.sql_scalar("SELECT COUNT(*) FROM events")
# Database automatically deleted
```

### Streaming

For ETL pipelines or one-time processing without storage:

```python
# Stream events directly to external system
for event in ws.stream_events(from_date="2024-01-01", to_date="2024-01-31"):
    send_to_warehouse(event)
```

## CLI Reference

The `mp` CLI provides 31 commands across four groups:

| Group | Commands |
|-------|----------|
| `mp auth` | `list`, `add`, `remove`, `switch`, `show`, `test` |
| `mp fetch` | `events`, `profiles` |
| `mp query` | `sql`, `segmentation`, `funnel`, `retention`, `jql`, `event-counts`, `property-counts`, `activity-feed`, `insights`, `frequency`, `segmentation-numeric`, `segmentation-sum`, `segmentation-average` |
| `mp inspect` | `events`, `properties`, `values`, `funnels`, `cohorts`, `top-events`, `info`, `tables`, `schema`, `drop` |

All commands support `--format` (json, jsonl, table, csv, plain) and `--help`.

`mp fetch` commands also support `--stdout` (stream as JSONL) and `--raw` (raw API format).

## DuckDB JSON Queries

Mixpanel properties are stored as JSON columns:

```sql
-- Extract property
SELECT properties->>'$.country' as country FROM events

-- Filter on property
SELECT * FROM events WHERE properties->>'$.plan' = 'premium'

-- Cast numeric
SELECT SUM(CAST(properties->>'$.amount' AS DECIMAL)) FROM events
```

## Documentation

Full documentation: [discohead.github.io/mixpanel_data](https://discohead.github.io/mixpanel_data/)

- [Installation](https://discohead.github.io/mixpanel_data/getting-started/installation/)
- [Quick Start](https://discohead.github.io/mixpanel_data/getting-started/quickstart/)
- [CLI Reference](https://discohead.github.io/mixpanel_data/cli/)
- [Python API](https://discohead.github.io/mixpanel_data/api/)
- [Streaming Guide](https://discohead.github.io/mixpanel_data/guide/streaming/)
- [SQL Query Guide](https://discohead.github.io/mixpanel_data/guide/sql-queries/)
- [Live Analytics](https://discohead.github.io/mixpanel_data/guide/live-analytics/)

## For AI Agents

`mixpanel_data` is designed with AI coding agents in mind:

- **Context preservation**: Fetch data once, query repeatedly without re-fetching
- **Streaming for ETL**: Stream data directly to external systems with `--stdout`
- **Structured output**: All commands support `--format json` for machine-readable responses
- **Discoverable schema**: `mp inspect` commands reveal events, properties, and values before querying
- **Local SQL**: Complex analysis via SQL instead of multiple API round-trips
- **Predictable errors**: Typed exceptions with error codes for programmatic handling

Typical agent workflow:

```bash
# 1. Discover schema
mp inspect events --format json
mp inspect properties --event Purchase --format json

# 2. Fetch relevant data (or stream with --stdout for ETL)
mp fetch events data --from 2024-01-01 --to 2024-01-31

# 3. Iterate with SQL queries
mp query sql "SELECT ..." --format json
mp query sql "SELECT ..." --format json  # No re-fetch needed
```

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup and guidelines.

## License

MIT
