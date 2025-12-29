# mixpanel_data

A Python library and CLI for working with Mixpanel analytics data, designed for AI coding agents.

## The Problem

AI coding agents consume context window tokens when receiving Mixpanel API responses. A single query can return 30KB of JSON—tokens that could otherwise be used for reasoning and iteration.

## The Solution

Fetch data once, store it locally in DuckDB, query repeatedly with SQL. Data lives outside the context window; only precise answers flow back in.

## Features

- **Local Data Store** — Fetch events and profiles from Mixpanel, store in DuckDB, query with SQL
- **Streaming** — Stream data directly without storage for ETL pipelines and one-time processing
- **Live Queries** — Run Mixpanel reports (segmentation, funnels, retention) directly when fresh data is needed
- **Data Discovery** — Introspect events, properties, values, saved funnels, and cohorts before writing queries
- **Event Analytics** — Query multi-event time series and property breakdowns across date ranges
- **Advanced Analytics** — User activity feeds, saved reports (Insights, Funnels, Flows), frequency analysis, numeric aggregations
- **Python Library** — Import and use programmatically in scripts and notebooks
- **CLI** — Compose into Unix pipelines, invoke from agents without writing Python

## Quick Example

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

## Next Steps

- [Installation](getting-started/installation.md) — Get started with pip or uv
- [Quick Start](getting-started/quickstart.md) — Your first queries in 5 minutes
- [API Reference](api/index.md) — Complete Python API documentation
- [CLI Reference](cli/index.md) — Command-line interface documentation
