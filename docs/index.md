# mixpanel_data

A complete programmable interface to Mixpanel analytics—available as both a Python library and CLI. Supports service account and OAuth 2.0 authentication.

!!! tip "AI-Friendly Documentation"
    🤖 **[Explore on DeepWiki →](https://deepwiki.com/jaredmcfarland/mixpanel_data)**

    DeepWiki provides an AI-optimized view of this project—perfect for code assistants, agents, and LLM-powered workflows. Ask questions about the codebase, explore architecture, or get contextual help.

!!! tip "Google Code Wiki"
    🔍 **[Explore on Code Wiki →](https://codewiki.google/github.com/jaredmcfarland/mixpanel_data)**

    Google's Code Wiki offers another AI-optimized interface for exploring this codebase—search, understand, and navigate the project with natural language queries.

## Why This Exists

Mixpanel's web UI is built for interactive exploration. But many workflows need something different: scripts that run unattended, notebooks that combine Mixpanel data with other sources, agents that query analytics programmatically, or pipelines that move data between systems.

`mixpanel_data` provides direct programmatic access to Mixpanel's analytics platform. Core analytics—typed insights queries, typed funnel queries, typed retention queries, typed flow queries, typed user profile queries, segmentation, saved reports—plus capabilities like raw JQL execution and streaming data extraction are available as Python methods or shell commands.

## Two Interfaces, One Capability Set

**Python Library** — For notebooks, scripts, and applications:

```python
import mixpanel_data as mp

ws = mp.Workspace()

# Discover what's in your project
events = ws.events()
props = ws.properties("Purchase")
values = ws.property_values("country", event="Purchase")
funnels = ws.funnels()
cohorts = ws.cohorts()
bookmarks = ws.list_bookmarks()

# Manage entities
dashboards = ws.list_dashboards()
cohort = ws.create_cohort(mp.CreateCohortParams(name="Power Users"))
flags = ws.list_feature_flags()
experiments = ws.list_experiments()

# Operational tooling
alerts = ws.list_alerts()
annotations = ws.list_annotations(from_date="2025-01-01")
webhooks = ws.list_webhooks()

# Data governance
event_defs = ws.get_event_definitions(names=["Signup"])
drop_filters = ws.list_drop_filters()
custom_props = ws.list_custom_properties()
lookup_tables = ws.list_lookup_tables()

# Schema governance
schemas = ws.list_schema_registry()
enforcement = ws.get_schema_enforcement()
audit = ws.run_audit()

# Insights queries — typed, composable analytics
from mixpanel_data import Metric, Filter, Formula

# Simple event query (last 30 days by default)
result = ws.query("Login")
print(result.df)

# DAU with breakdown
result = ws.query("Login", math="dau", group_by="platform", last=90)

# Multi-metric formula: conversion rate
result = ws.query(
    [Metric("Signup", math="unique"), Metric("Purchase", math="unique")],
    formula="(B / A) * 100",
    formula_label="Conversion Rate",
    unit="week",
)

# Filtered aggregation with numeric breakdown
result = ws.query(
    "Purchase",
    math="total",
    math_property="amount",
    where=[Filter.equals("country", "US"), Filter.greater_than("amount", 50)],
    group_by="platform",
)

# Typed funnel query — define steps inline
funnel_result = ws.query_funnel(
    ["Signup", "Add to Cart", "Purchase"],
    conversion_window=7,
    last=90,
)
print(funnel_result.overall_conversion_rate)

# Typed retention query — cohort retention with event pairs
from mixpanel_data import RetentionEvent
retention_result = ws.query_retention(
    "Signup",
    "Login",
    retention_unit="week",
    last=90,
)
print(retention_result.df.head())  # cohort_date | bucket | count | rate

# Typed flow query — analyze user paths through your product
from mixpanel_data import FlowStep
flow_result = ws.query_flow("Purchase", forward=3, reverse=1)
print(flow_result.nodes_df.head())   # step | event | type | count
print(flow_result.top_transitions(5))

# Typed user profile query — search and aggregate user profiles
from mixpanel_data import Filter
result = ws.query_user(
    where=Filter.equals("plan", "premium"),
    properties=["$email", "$name", "ltv"],
    sort_by="ltv",
    sort_order="descending",
    limit=50,
)
print(f"{result.total} premium users")
print(result.df)

# Cohort-scoped queries — filter, break down, or track cohorts
from mixpanel_data import CohortCriteria, CohortDefinition, CohortBreakdown, CohortMetric

# Define a cohort inline and use it immediately
power_users = CohortDefinition(
    CohortCriteria.did_event("Purchase", at_least=3, within_days=30)
)
result = ws.query("Login", where=Filter.in_cohort(power_users, name="Power Users"))
result = ws.query("Login", group_by=CohortBreakdown(power_users, name="Power Users"))
result = ws.query(CohortMetric(123, "Power Users"), last=90, unit="week")

# Legacy live queries
segmentation = ws.segmentation(
    event=events[0],
    from_date="2025-01-01",
    to_date="2025-01-31",
    on="country"
)

funnel = ws.funnel(
    funnel_id=funnels[0].id,
    from_date="2025-01-01",
    to_date="2025-01-31"
)

# Stream events for processing
for event in ws.stream_events(from_date="2025-01-01", to_date="2025-01-31"):
    process(event)

# Results have .df for pandas interoperability
result.df
segmentation.df
funnel.df
```

**CLI** — For shell scripts, pipelines, and agent tool calls:

```bash
# Discover your data landscape
mp inspect events
mp inspect properties --event Purchase
mp inspect values --event Purchase --property country
mp inspect top-events
mp inspect funnels
mp inspect cohorts
mp inspect bookmarks

# Manage entities
mp dashboards list
mp reports list --type insights
mp cohorts create --name "Power Users"
mp flags list
mp experiments list
mp alerts list
mp annotations list --from-date 2025-01-01
mp webhooks list

# Data governance
mp lexicon events get --names Signup,Login
mp drop-filters list
mp custom-properties list
mp lookup-tables list

# Schema governance
mp schemas list
mp lexicon enforcement get
mp lexicon audit

# Live queries against Mixpanel API
mp query segmentation "Purchase" \
    --from 2025-01-01 --to 2025-01-31 --on country
mp query funnel 12345 --from 2025-01-01 --to 2025-01-31
mp query retention \
    --born-event Signup --return-event Purchase --from 2025-01-01
mp query activity-feed user@example.com --from 2025-01-01
mp query saved-report 67890
mp query frequency "Login" --from 2025-01-01

# Filter with built-in jq
mp query segmentation "Purchase" --from 2025-01-01 --format json --jq '.total'

# Stream events via Python API (memory-efficient for large datasets)
# for event in ws.stream_events(from_date="2025-01-01", to_date="2025-01-31"):
#     process(event)
```

## Capabilities

**Discovery** — Rapidly explore your project's data landscape:

- List all events, drill into properties, sample actual values
- Browse saved funnels, cohorts, and reports (bookmarks)
- Access Lexicon definitions from your data dictionary
- Analyze property distributions, coverage, and numeric statistics
- Inspect top events by volume, daily trends, user engagement patterns

Discovery commands let you survey what exists before writing queries—no guessing at event names or property values.

**Insights Queries** — Typed, composable analytics using Mixpanel's Insights engine:

- DAU / WAU / MAU and unique user metrics
- Multi-metric comparison on a single chart
- Formula-based metrics (conversion rates, ratios)
- Per-user aggregation (average purchases per user)
- Rolling and cumulative analysis modes
- Percentiles (p25, p75, p90, p99, custom percentiles, histogram distributions)
- Typed filters (`Filter.equals()`, `Filter.greater_than()`, date filters like `Filter.in_the_last()`, etc.)
- Cohort-scoped queries — filter by cohort, break down by cohort membership, or track cohort size over time, using saved cohort IDs or inline `CohortDefinition` objects
- Property breakdowns with numeric bucketing
- Results as DataFrames, persistable as saved reports

**Live Queries** — Execute Mixpanel analytics directly:

- Segmentation with filtering, grouping, and time bucketing
- Typed funnel queries with ad-hoc step definitions, exclusions, and conversion windows
- Typed retention queries with event pairs, custom buckets, alignment modes, and segmentation
- Typed flow queries with path analysis, direction controls, and visualization modes
- Typed user profile queries with filtering, sorting, property selection, and aggregation
- Funnel conversion analysis (legacy saved funnels)
- Retention analysis (legacy)
- Saved reports (Insights, Funnels, Flows, Retention)
- User activity feeds
- Frequency and engagement analysis
- Numeric aggregations (sum, average, bucket)
- Raw JQL execution for custom analysis

**Entity Management** — Create, update, and delete Mixpanel entities:

- Full CRUD for dashboards, reports (bookmarks), cohorts, feature flags, experiments, alerts, annotations, and webhooks
- Bulk operations for efficient batch management
- Dashboard features: favorites, pins, blueprint templates, RCA dashboards
- Report history tracking and linked dashboard discovery
- Feature flag lifecycle (enable/disable/archive) with test users and history
- Experiment lifecycle management (draft/launch/conclude/decide)
- Alert monitoring: trigger history, test notifications, screenshot URLs, bookmark validation
- Timeline annotations with tagging system
- Webhook management with connectivity testing

**Data Governance** — Define and control your data taxonomy:

- Lexicon definitions: manage event and property metadata, tags, descriptions, visibility
- Drop filters: suppress unwanted events at ingestion
- Custom properties: create computed properties from formulas or behaviors
- Custom events: manage composite event definitions
- Lookup tables: upload, download, and manage CSV reference data for property enrichment
- Tracking metadata, change history, and bulk export for audit and governance workflows

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

| Endpoint                                    | Size   | Use Case                                                       |
| ------------------------------------------- | ------ | -------------------------------------------------------------- |
| <a href="llms.txt">`llms.txt`</a>           | ~3KB   | Structured index—discover what documentation exists            |
| <a href="llms-full.txt">`llms-full.txt`</a> | ~400KB | Complete documentation in one file—comprehensive search        |
| <a href="index.md">`index.md`</a> pages     | Varies | Each HTML page has a corresponding `index.md` at the same path |

Every page also has a **Copy Markdown** button in the upper right corner—click it to copy the page content as markdown, ready to paste into your AI assistant's context.

For interactive exploration of the codebase itself, see [DeepWiki](https://deepwiki.com/jaredmcfarland/mixpanel_data).

## Next Steps

- [Installation](getting-started/installation.md) — Get started with pip or uv
- [Quick Start](getting-started/quickstart.md) — Your first queries in 5 minutes
- [Insights Queries](guide/query.md) — Typed analytics queries with DAU, formulas, filters, and breakdowns
- [Funnel Queries](guide/query-funnels.md) — Typed funnel conversion analysis with steps, exclusions, and conversion windows
- [Retention Queries](guide/query-retention.md) — Typed retention analysis with event pairs, custom buckets, and alignment modes
- [Flow Queries](guide/query-flows.md) — Typed flow path analysis with direction controls and visualization modes
- [User Profile Queries](guide/query-users.md) — Typed user profile queries with filtering, sorting, and aggregation
- [API Reference](api/index.md) — Complete Python API documentation
- [Entity Management](guide/entity-management.md) — Manage dashboards, reports, cohorts, feature flags, experiments, alerts, annotations, and webhooks
- [Data Governance](guide/data-governance.md) — Manage Lexicon definitions, drop filters, custom properties, custom events, and lookup tables
- [Business Context](guide/business-context.md) — Read and write the markdown business context that grounds AI assistants (org and project scopes)
- [CLI Reference](cli/index.md) — Command-line interface documentation
