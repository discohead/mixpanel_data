# mixpanel_data

A complete programmable interface to Mixpanel analytics—available as both a Python library and CLI.

!!! tip "AI-Friendly Documentation"
    🤖 **[Explore on DeepWiki →](https://deepwiki.com/jaredmcfarland/mixpanel_data)**

    DeepWiki provides an AI-optimized view of this project—perfect for code assistants, agents, and LLM-powered workflows. Ask questions about the codebase, explore architecture, or get contextual help.

## Why This Exists

Mixpanel's web UI is built for interactive exploration. But many workflows need something different: scripts that run unattended, notebooks that combine Mixpanel data with other sources, agents that query analytics programmatically, or pipelines that move data between systems.

`mixpanel_data` provides direct programmatic access to Mixpanel's analytics platform. Core analytics—segmentation, funnels, retention, saved reports—plus capabilities like raw JQL execution and local SQL analysis are available as Python methods or shell commands.

## Two Interfaces, One Capability Set

**Python Library** — For notebooks, scripts, and applications:

```python
import mixpanel_data as mp

ws = mp.Workspace()

# Discover what's in your project
events = ws.list_events()
props = ws.list_properties("Purchase")
values = ws.list_property_values("Purchase", "country")
funnels = ws.list_funnels()
cohorts = ws.list_cohorts()
bookmarks = ws.list_bookmarks()

# Live queries—use discovered data to construct accurate queries
segmentation = ws.segmentation(
    event=events[0].name,
    from_date="2025-01-01",
    to_date="2025-01-31",
    on="country"
)

funnel = ws.funnel(
    funnel_id=funnels[0].id,
    from_date="2025-01-01",
    to_date="2025-01-31"
)

saved = ws.saved_report(bookmark_id=bookmarks[0].id)
activity = ws.activity_feed(
    distinct_id="user@example.com",
    from_date="2025-01-01"
)

# Fetch data locally (use parallel=True for large date ranges)
ws.fetch_events(
    "jan_events",
    from_date="2025-01-01",
    to_date="2025-01-31"
)
ws.fetch_events(
    "q1_events",
    from_date="2025-01-01",
    to_date="2025-03-31",
    parallel=True  # Up to 10x faster for large date ranges
)
ws.fetch_profiles("power_users", cohort_id=cohorts[0].id)

# Query with full SQL power—joins, window functions, CTEs
df = ws.sql("""
    SELECT
        e.properties->>'$.country' as country,
        COUNT(DISTINCT e.distinct_id) as users,
        COUNT(*) as events
    FROM jan_events e
    JOIN power_users u ON e.distinct_id = u.distinct_id
    GROUP BY 1
    ORDER BY 2 DESC
""")

# Results have .df for pandas interoperability
segmentation.df
funnel.df
df.to_csv("export.csv")

# Execute arbitrary JQL for custom analysis
jql_result = ws.jql("""
    function main() {
        return Events({...}).groupBy([...])
    }
""")
```

**CLI** — For shell scripts, pipelines, and agent tool calls:

```bash
# Discover your data landscape
mp inspect events
mp inspect properties "Purchase"
mp inspect values "Purchase" "country"
mp inspect top-events
mp inspect funnels
mp inspect cohorts
mp inspect bookmarks

# Live queries against Mixpanel API
mp query segmentation "Purchase" \
    --from 2025-01-01 --to 2025-01-31 --on country
mp query funnel 12345 --from 2025-01-01 --to 2025-01-31
mp query retention \
    --born-event Signup --return-event Purchase --from 2025-01-01
mp query activity-feed user@example.com --from 2025-01-01
mp query saved-report 67890
mp query frequency "Login" --from 2025-01-01

# Fetch data locally (use --parallel for large date ranges)
mp fetch events jan_events --from 2025-01-01 --to 2025-01-31
mp fetch events q1_events --from 2025-01-01 --to 2025-03-31 --parallel
mp fetch profiles users --cohort-id 12345

# Query locally with SQL
mp query sql "SELECT event_name, COUNT(*) FROM jan_events GROUP BY 1"

# Inspect local data
mp inspect tables
mp inspect schema jan_events
mp inspect sample jan_events
mp inspect summarize jan_events

# Filter with built-in jq
mp query segmentation "Purchase" --from 2025-01-01 --format json --jq '.total'

# Stream to Unix tools (memory-efficient for large datasets)
mp fetch events --stdout --from 2025-01-01 --to 2025-01-31 \
    | jq -r '.distinct_id' | sort -u | wc -l
```

## Capabilities

**Discovery** — Rapidly explore your project's data landscape:

- List all events, drill into properties, sample actual values
- Browse saved funnels, cohorts, and reports (bookmarks)
- Access Lexicon definitions from your data dictionary
- Analyze property distributions, coverage, and numeric statistics
- Inspect top events by volume, daily trends, user engagement patterns

Discovery commands let you survey what exists before writing queries—no guessing at event names or property values.

**Live Queries** — Execute Mixpanel analytics directly:

- Segmentation with filtering, grouping, and time bucketing
- Funnel conversion analysis
- Retention analysis
- Saved reports (Insights, Funnels, Flows, Retention)
- User activity feeds
- Frequency and engagement analysis
- Numeric aggregations (sum, average, bucket)
- Raw JQL execution for custom analysis

**Local Storage** — Fetch once, query repeatedly:

- Store events and profiles in a local DuckDB database
- Parallel fetching for large date ranges (up to 10x faster)
- Query with full SQL: joins, window functions, CTEs
- Introspect tables, sample data, analyze distributions
- Iterate on analysis without repeated API calls

**Streaming** — Process data without storage:

- Stream events directly for ETL pipelines
- One-time processing without local persistence
- Memory-efficient iteration over large datasets

## For Humans and Agents

The structured output and deterministic command interface make `mixpanel_data` particularly effective for AI coding agents—the same properties that make it scriptable for humans make it reliable for automated workflows.

Discovery commands are particularly valuable: an agent can rapidly survey your data landscape—listing events, inspecting properties, sampling values—then construct accurate queries based on what actually exists rather than guessing.

The tool is designed to be self-documenting: comprehensive `--help` on every command, complete docstrings on every method, full type annotations throughout, and rich exception messages that explain what went wrong and how to fix it. Agents can discover capabilities, learn correct usage, and recover from mistakes autonomously.

### LLM-Optimized Documentation

This documentation is built with AI consumption in mind. In addition to the standard HTML pages, we provide:

| Endpoint | Size | Use Case |
|----------|------|----------|
| [`llms.txt`](https://jaredmcfarland.github.io/mixpanel_data/llms.txt) | ~3KB | Structured index—discover what documentation exists |
| [`llms-full.txt`](https://jaredmcfarland.github.io/mixpanel_data/llms-full.txt) | ~400KB | Complete documentation in one file—comprehensive search |
| [`index.md`](https://jaredmcfarland.github.io/mixpanel_data/index.md) pages | Varies | Each HTML page has a corresponding `index.md` at the same path |

For interactive exploration of the codebase itself, see [DeepWiki](https://deepwiki.com/jaredmcfarland/mixpanel_data).

## Next Steps

- [Installation](getting-started/installation.md) — Get started with pip or uv
- [Quick Start](getting-started/quickstart.md) — Your first queries in 5 minutes
- [API Reference](api/index.md) — Complete Python API documentation
- [CLI Reference](cli/index.md) — Command-line interface documentation
