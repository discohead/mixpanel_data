# mixpanel_data

A Python library and CLI for working with Mixpanel analytics data, designed for AI coding agents.

**Status:** Foundation through query service enhancements complete — workspace facade next.

## The Problem

AI coding agents consume context window tokens when receiving Mixpanel API responses. A single query can return 30KB of JSON—tokens that could otherwise be used for reasoning and iteration.

## The Solution

Fetch data once, store it locally in DuckDB, query repeatedly with SQL. Data lives outside the context window; only precise answers flow back in.

## Features

- **Local Data Store** — Fetch events and profiles from Mixpanel, store in DuckDB, query with SQL
- **Live Queries** — Run Mixpanel reports (segmentation, funnels, retention) directly when fresh data is needed
- **Data Discovery** — Introspect events, properties, values, saved funnels, and cohorts before writing queries
- **Event Analytics** — Query multi-event time series and property breakdowns across date ranges
- **Advanced Analytics** — User activity feeds, saved Insights reports, frequency analysis, numeric aggregations
- **Python Library** — Import and use programmatically in scripts and notebooks
- **CLI** — Compose into Unix pipelines, invoke from agents without writing Python

## Installation

```bash
pip install mixpanel_data
```

## Quick Start

### Python API

```python
import mixpanel_data as mp

# Create workspace with stored credentials
ws = mp.Workspace()

# Fetch events into local DuckDB
ws.fetch_events("jan_events", from_date="2024-01-01", to_date="2024-01-31")

# Query with SQL
df = ws.sql("""
    SELECT
        DATE_TRUNC('day', event_time) as day,
        event_name,
        COUNT(*) as count
    FROM jan_events
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
```

### Ephemeral Workspace

```python
with mp.Workspace.ephemeral() as ws:
    ws.fetch_events("events", from_date="2024-01-01", to_date="2024-01-31")
    total = ws.sql_scalar("SELECT COUNT(*) FROM events")
# Database automatically deleted
```

### CLI

```bash
# Configure credentials
mp auth add production \
    --username sa_xxx \
    --secret xxx \
    --project 12345 \
    --region us

# Fetch events
mp fetch events --from 2024-01-01 --to 2024-01-31

# Query locally
mp sql "SELECT event_name, COUNT(*) FROM events GROUP BY 1" --format table

# Run live segmentation
mp segmentation --event Purchase --from 2024-01-01 --to 2024-01-31 --on country

# Export to CSV
mp sql "SELECT * FROM events" --format csv > events.csv
```

## Configuration

### Environment Variables

| Variable | Description |
|----------|-------------|
| `MP_USERNAME` | Service account username |
| `MP_SECRET` | Service account secret |
| `MP_PROJECT_ID` | Project ID |
| `MP_REGION` | Data residency region (`us`, `eu`, `in`) |

### Config File

Credentials can be stored in `~/.mp/config.toml`:

```toml
default = "production"

[accounts.production]
username = "sa_abc123..."
secret = "..."
project_id = "12345"
region = "us"

[accounts.staging]
username = "sa_xyz789..."
secret = "..."
project_id = "67890"
region = "eu"
```

## DuckDB JSON Query Syntax

Mixpanel properties are stored as JSON columns:

```sql
-- Extract string property
SELECT properties->>'$.country' as country FROM events

-- Extract and cast numeric
SELECT CAST(properties->>'$.amount' AS DECIMAL) as amount FROM events

-- Filter on property
SELECT * FROM events WHERE properties->>'$.plan' = 'premium'

-- Nested property access
SELECT properties->>'$.user.email' as email FROM events
```

## Documentation

- [Project Brief](docs/mixpanel_data-project-brief.md) — Vision and goals
- [Design Document](docs/mixpanel_data-design.md) — Architecture, component specs, public API
- [CLI Specification](docs/mp-cli-project-spec.md) — Full CLI reference
- [Mixpanel Data Model](docs/MIXPANEL_DATA_MODEL_REFERENCE.md) — Data model reference

## Architecture

```
CLI Layer (Typer)           → Argument parsing, output formatting
    ↓
Public API Layer            → Workspace class, auth module
    ↓
Service Layer               → DiscoveryService, FetcherService, LiveQueryService
    ↓
Infrastructure Layer        → ConfigManager, MixpanelAPIClient, StorageEngine (DuckDB)
```

## Technology Stack

| Component | Choice |
|-----------|--------|
| Language | Python 3.11+ |
| CLI Framework | Typer |
| Output Formatting | Rich |
| Validation | Pydantic |
| Database | DuckDB |
| HTTP Client | httpx |

## Development Status

Implementation following the phased roadmap in [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md):

1. ✅ **Foundation Layer** — Exceptions, types, ConfigManager, auth module
2. ✅ **API Client** — MixpanelAPIClient with HTTP transport, rate limiting, streaming
3. ✅ **Storage Engine** — DuckDB operations, schema management, query execution
4. ✅ **Discovery Service** — DiscoveryService with caching
5. ✅ **Fetch Service** — FetcherService for events/profiles ingestion
6. ✅ **Live Queries** — LiveQueryService for segmentation, funnels, retention, JQL
7. ✅ **Discovery Enhancements** — Funnels, cohorts, top events; event/property counts
8. ✅ **Query Service Enhancements** — Activity feed, insights, frequency, numeric aggregations
9. ⏳ **Workspace** — Facade class, lifecycle management (next)
10. ⏳ **CLI** — Typer application, all commands
11. ⏳ **Polish** — SKILL.md, documentation, PyPI release

## License

MIT
