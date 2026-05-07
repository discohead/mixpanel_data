# mixpanel_headless

[![Python](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org/downloads/)
[![License](https://img.shields.io/github/license/mixpanel/mixpanel-headless)](LICENSE)

> **⚠️ Pre-release Software**: This package is under active development and not yet published to PyPI. APIs may change between versions.

A complete programmable interface to Mixpanel analytics—Python library and CLI for discovery, querying, streaming, and entity management.

## Why mixpanel_headless?

Mixpanel's web UI is powerful for interactive exploration, but programmatic access requires navigating multiple REST endpoints with different conventions. **mixpanel_headless** provides a unified interface: discover your schema, run analytics queries, stream data, and manage entities—all through consistent Python methods or CLI commands.

Core analytics—typed Insights engine queries (DAU/WAU/MAU, formulas, filters, breakdowns, cohort-scoped queries, period-over-period comparison, frequency analysis), typed funnel queries (ad-hoc steps, exclusions, conversion windows), typed retention queries (event pairs, custom buckets, alignment modes), typed flow queries (path analysis, direction controls, visualization modes), typed user profile queries (property filtering, sorting, parallel fetching, aggregate statistics), segmentation, saved reports—plus entity management (dashboards, reports, cohorts, feature flags, experiments), raw JQL execution, and streaming data extraction.

## Installation

Install directly from GitHub (package not yet published to PyPI):

```bash
pip install git+https://github.com/mixpanel/mixpanel-headless.git
```

Requires Python 3.10+. Verify installation:

```bash
mp --version
```

## Quick Start

> **What's new in 0.4.0:** Three first-class account types (`service_account` / `oauth_browser` / `oauth_token`), single resolver (`env > param > target > bridge > [active]`), fluent in-session switching via `Workspace.use(...)`, new CLI groups (`mp account` / `mp project` / `mp workspace` / `mp target` / `mp session`). **Hard break from 0.3.x** — see [Migration → 0.3.x to 0.4.0](docs/migration/0.4.0.md) for the upgrade walkthrough.

### 1. Authenticate

**Option A: OAuth Login (interactive, recommended)**

```bash
mp account add personal --type oauth_browser --region us
mp account login personal     # Opens browser for PKCE flow
mp session                    # Verify resolved state
```

**Option B: Service Account (scripts, CI/CD)**

```bash
# Set the secret via env var (preferred)
export MP_SECRET="your-secret-here"
mp account add team --type service_account --username sa_xxx --project 12345 --region us
# Added account 'team' (service_account, us). Set as active.

mp account test team          # Verify connection
```

For CI/CD environments where the secret lives in a shell variable, pipe it via stdin:

```bash
echo "$SECRET" | mp account add team --type service_account \
    --username sa_xxx --project 12345 --region us --secret-stdin
```

Or set all credentials as environment variables: `MP_USERNAME`, `MP_SECRET`, `MP_PROJECT_ID`, `MP_REGION`

**Option C: Raw OAuth Bearer Token (CI / agents)**

If a managed OAuth client (e.g., a Claude Code plugin or CI pipeline) already gave you an access token, inject it via env vars without going through the browser flow:

```bash
export MP_OAUTH_TOKEN="<bearer-token>"
export MP_PROJECT_ID="12345"
export MP_REGION="us"  # or "eu", "in"
```

The full service-account env-var set (`MP_USERNAME` + `MP_SECRET` + `MP_PROJECT_ID` + `MP_REGION`) takes precedence when both sets are complete, so this is safe to add to a shell that already exports the service-account vars.

### 2. Explore Your Data

```bash
mp inspect events                      # List all events
mp inspect properties --event Purchase # Properties for an event
mp inspect funnels                     # Saved funnels
```

### 3. Run Analytics Queries

```python
import mixpanel_headless as mp

ws = mp.Workspace()

# Typed insights query (recommended)
result = ws.query("Purchase", math="unique", group_by="country", last=30)
print(result.df)
```

```bash
# Or use the CLI for legacy query methods
mp query segmentation --event Purchase --from 2025-01-01 --to 2025-01-31 --on country
```

### 4. Stream Data (Python API)

```python
import mixpanel_headless as mp

ws = mp.Workspace()
for event in ws.stream_events(from_date="2025-01-01", to_date="2025-01-31"):
    print(event["event"])
```

## Python API

```python
import mixpanel_headless as mp
from mixpanel_headless import Metric, Filter, Formula, GroupBy, RetentionEvent
from mixpanel_headless import TimeComparison, FrequencyBreakdown, FrequencyFilter

ws = mp.Workspace()

# Discover what's in your project
events = ws.events()
props = ws.properties("Purchase")
funnels = ws.funnels()
cohorts = ws.cohorts()

# Insights queries — typed, composable analytics
result = ws.query("Login")                            # simple event count
result = ws.query("Login", math="dau", last=90)       # DAU trend
result = ws.query("Purchase", math="total",             # revenue by country
    math_property="amount", group_by="country")
result = ws.query(                                     # conversion rate formula
    [Metric("Signup", math="unique"), Metric("Purchase", math="unique")],
    formula="(B / A) * 100",
    formula_label="Conversion Rate",
    unit="week",
)
result = ws.query("Purchase",                          # filtered with breakdown
    where=Filter.equals("country", "US"),
    group_by=GroupBy("amount", property_type="number", bucket_size=50),
)
print(result.df)  # pandas DataFrame

# Period-over-period comparison — compare against previous month
result = ws.query("Login", math="dau",
    time_comparison=TimeComparison.relative("month"), last=30)

# Frequency breakdown — segment by purchase frequency
result = ws.query("Login",
    group_by=FrequencyBreakdown(event="Purchase", bucket_max=10),
    last=30)

# New filter methods
result = ws.query("Purchase",
    where=[Filter.at_least("amount", 50), Filter.starts_with("email", "admin")])

# Typed funnel query — define steps inline
funnel = ws.query_funnel(
    ["Signup", "Add to Cart", "Purchase"],
    conversion_window=7,
    last=90,
)
print(funnel.overall_conversion_rate)  # e.g. 0.12

# Typed retention query — cohort retention with event pairs
retention = ws.query_retention(
    "Signup",
    "Login",
    retention_unit="week",
    last=90,
)
print(retention.df.head())  # cohort_date | bucket | count | rate

# Typed flow query — analyze user paths
from mixpanel_headless import FlowStep
flow_result = ws.query_flow("Purchase", forward=3, reverse=1)
print(flow_result.nodes_df.head())   # step | event | type | count
print(flow_result.top_transitions(5))

# User profile query — filter, sort, and aggregate profiles
result = ws.query_user(
    mode="profiles",
    where=Filter.equals("plan", "premium"),
    properties=["$email", "$name", "ltv"],
    sort_by="ltv",
    sort_order="descending",
    limit=50,
)
print(result.df)  # distinct_id | last_seen | email | name | ltv

# Aggregate count of matching profiles (aggregate is the default mode)
count = ws.query_user(where=Filter.is_set("$email"))
print(f"Users with email: {count.value}")

# Cohort-scoped queries — define cohorts inline, no UI needed
from mixpanel_headless import CohortCriteria, CohortDefinition, CohortBreakdown
power_users = CohortDefinition(
    CohortCriteria.did_event("Purchase", at_least=3, within_days=30)
)
result = ws.query("Login", where=Filter.in_cohort(power_users, name="Power Users"))
result = ws.query("Login", group_by=CohortBreakdown(power_users, name="Power Users"))

# Legacy live analytics queries
result = ws.segmentation(
    event=events[0],
    from_date="2025-01-01",
    to_date="2025-01-31",
    on="country"
)

# Query a saved funnel
funnel = ws.funnel(
    funnel_id=funnels[0].id,
    from_date="2025-01-01",
    to_date="2025-01-31"
)

# Manage entities
dashboards = ws.list_dashboards()
cohort = ws.create_cohort(mp.CreateCohortParams(name="Power Users"))

# Feature flags and experiments
flags = ws.list_feature_flags()
flag = ws.create_feature_flag(mp.CreateFeatureFlagParams(name="Dark Mode", key="dark_mode"))
experiments = ws.list_experiments()
exp = ws.create_experiment(mp.CreateExperimentParams(name="Checkout Flow Test"))

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

# Stream events for processing
for event in ws.stream_events(from_date="2025-01-01", to_date="2025-01-31"):
    process(event)
```

### Streaming

For ETL pipelines or one-time processing without storage:

```python
# Stream events directly to external system
for event in ws.stream_events(from_date="2025-01-01", to_date="2025-01-31"):
    send_to_warehouse(event)
```

## CLI Reference

**`mp account`** — Manage accounts: `list`, `add`, `update`, `remove`, `use`, `show`, `test`, `login`, `logout`, `token`, `export-bridge`, `remove-bridge`

**`mp project`** — Switch the active project: `list`, `use`, `show`

**`mp workspace`** — Switch the active workspace: `list`, `use`, `show`

**`mp target`** — Saved (account, project, optional workspace) cursors: `list`, `add`, `use`, `show`, `remove`

**`mp session`** — Show resolved auth state (`mp session [--bridge]`)

**`mp query`** — Run analytics: `segmentation`, `funnel`, `retention`, `jql`, `saved-report`, `flows`, `event-counts`, `property-counts`, `activity-feed`, `frequency`, `segmentation-numeric`, `segmentation-sum`, `segmentation-average`

**`mp inspect`** — Schema discovery: `events`, `properties`, `values`, `funnels`, `cohorts`, `top-events`, `bookmarks`, `lexicon-schemas`, `lexicon-schema`, `distribution`, `numeric`, `daily`, `engagement`, `coverage`

**`mp dashboards`** — Dashboard management: `list`, `create`, `get`, `update`, `delete`, `bulk-delete`, `favorite`, `unfavorite`, `pin`, `unpin`, `add-report`, `remove-report`, `update-report-link`, `update-text-card`, `blueprints`, `blueprint-create`, `rca`, `erf`

**`mp reports`** — Report management: `list`, `create`, `get`, `update`, `delete`, `bulk-delete`, `bulk-update`, `linked-dashboards`, `dashboard-ids`, `history`

**`mp cohorts`** — Cohort management: `list`, `create`, `get`, `update`, `delete`, `bulk-delete`, `bulk-update`

**`mp flags`** — Feature flag management: `list`, `create`, `get`, `update`, `delete`, `archive`, `restore`, `duplicate`, `set-test-users`, `history`, `limits`

**`mp experiments`** — Experiment management: `list`, `create`, `get`, `update`, `delete`, `launch`, `conclude`, `decide`, `archive`, `restore`, `duplicate`, `erf`

**`mp alerts`** — Alert management: `list`, `create`, `get`, `update`, `delete`, `bulk-delete`, `count`, `history`, `test`, `screenshot`, `validate`

**`mp annotations`** — Annotation management: `list`, `create`, `get`, `update`, `delete`, plus `tags list` and `tags create`

**`mp webhooks`** — Webhook management: `list`, `create`, `update`, `delete`, `test`

**`mp lexicon`** — Lexicon management: `events get/update/delete/bulk-update`, `properties get/update/bulk-update`, `tags list/create/update/delete`, `tracking-metadata`, `event-history`, `property-history`, `export`, `audit`, `enforcement get/init/update/replace/delete`, `anomalies list/update/bulk-update`, `deletion-requests list/create/cancel/preview`

**`mp drop-filters`** — Drop filter management: `list`, `create`, `update`, `delete`, `limits`

**`mp custom-properties`** — Custom property management: `list`, `get`, `create`, `update`, `delete`, `validate`

**`mp custom-events`** — Custom event management: `list`, `update`, `delete`

**`mp lookup-tables`** — Lookup table management: `list`, `upload`, `update`, `delete`, `download`, `upload-url`, `download-url`

**`mp schemas`** — Schema registry management: `list`, `create`, `create-bulk`, `update`, `update-bulk`, `delete`

All commands support `--format` (`json`, `jsonl`, `table`, `csv`, `plain`) and `--help`.

### Filtering with --jq

Commands that output JSON support `--jq` for client-side filtering:

```bash
# Get first 5 events
mp inspect events --format json --jq '.[:5]'

# Extract total from segmentation
mp query segmentation --event Purchase --from 2025-01-01 --to 2025-01-31 \
    --format json --jq '.total'

```

See [CLI Reference](https://mixpanel.github.io/mixpanel-headless/cli/) for complete documentation.

## Documentation

Full documentation: [mixpanel.github.io/mixpanel-headless](https://mixpanel.github.io/mixpanel-headless/)

- [Installation](https://mixpanel.github.io/mixpanel-headless/getting-started/installation/)
- [Quick Start](https://mixpanel.github.io/mixpanel-headless/getting-started/quickstart/)
- [Insights Queries](https://mixpanel.github.io/mixpanel-headless/guide/query/) — Typed analytics with DAU, formulas, filters, breakdowns
- [Funnel Queries](https://mixpanel.github.io/mixpanel-headless/guide/query-funnels/) — Typed funnel conversion analysis with steps, exclusions, conversion windows
- [Retention Queries](https://mixpanel.github.io/mixpanel-headless/guide/query-retention/) — Typed retention analysis with event pairs, custom buckets, alignment modes
- [Flow Queries](https://mixpanel.github.io/mixpanel-headless/guide/query-flows/) — Typed flow path analysis with direction controls, visualization modes
- [User Profile Queries](https://mixpanel.github.io/mixpanel-headless/guide/query-users/) — Profile filtering, sorting, parallel fetching, aggregate statistics
- [CLI Reference](https://mixpanel.github.io/mixpanel-headless/cli/)
- [Python API](https://mixpanel.github.io/mixpanel-headless/api/)
- [Streaming Guide](https://mixpanel.github.io/mixpanel-headless/guide/streaming/)
- [Live Analytics](https://mixpanel.github.io/mixpanel-headless/guide/live-analytics/)

- [![Ask DeepWiki](https://deepwiki.com/badge.svg)](https://deepwiki.com/mixpanel/mixpanel-headless)

## For Humans and Agents

The entire surface area is self-documenting. Every CLI command supports `--help` with complete argument descriptions. The Python API uses typed dataclasses for all return values—IDEs show you what fields are available. Exceptions include error codes and context for programmatic handling. This means both human developers and AI coding agents can explore capabilities without external documentation.

Key design features:

- **Typed Query Engines**: `query()`, `query_funnel()`, `query_retention()`, `query_flow()`, and `query_user()` provide five composable engines — Insights analytics, funnel conversion, retention cohorts, flow path analysis, and user profile queries — with period-over-period comparison (`TimeComparison`), frequency analysis (`FrequencyBreakdown`/`FrequencyFilter`), 21 math types, and 27+ filter methods, all sharing the same `Filter` vocabulary, `CohortDefinition` builders, and DataFrame output
- **Entity CRUD & Data Governance**: Full lifecycle management of dashboards, reports, cohorts, feature flags, experiments, alerts, annotations, webhooks, plus Lexicon definitions, drop filters, custom properties, custom events, and lookup tables via Mixpanel App API
- **Discoverable schema**: `events()`, `properties()`, `funnels()`, `cohorts()`, `bookmarks()` reveal what's in your project before you query
- **Consistent interfaces**: Same operations available as Python methods and CLI commands
- **Structured output**: All CLI commands support `--format json` for machine-readable responses, plus `--jq` for inline filtering
- **Streaming data extraction**: Memory-efficient iterators for events and profiles
- **Three first-class account types**: `service_account` (Basic Auth) for unattended automation, `oauth_browser` (PKCE flow with auto-refreshed tokens) for interactive use, `oauth_token` (static bearer) for CI / agents
- **Typed exceptions**: Error codes and context for programmatic handling

## Claude Code Plugin

This project includes a Claude Code plugin (v5.0) that turns Claude into a senior data analyst. The plugin is **CodeMode-first**: Claude writes Python code using `mixpanel_headless` + `pandas` rather than calling CLI commands or MCP tools.

The plugin is built around the 5-engine query taxonomy — `query()`, `query_funnel()`, `query_retention()`, `query_flow()`, and `query_user()` — with full cohort-scoped query support. Claude translates natural language analytics questions into typed query calls with filters, breakdowns, formulas, cohort definitions, and aggregations, then interprets results as DataFrames.

**Installation:**

Add the plugin from the `mixpanel-plugin/` directory, then restart Claude Code.

**What you get:**

- **Command**: `/mixpanel-headless:auth` — Manage credentials, accounts, OAuth login, project discovery
- **Skills**:
  - `setup` — Install dependencies and verify authentication
  - `mixpanelyst` — Auto-triggered on analytics questions; teaches 5-engine query patterns, analytical methodology (parameter sensitivity, statistical traps, counting modes), inline custom properties, cohort definitions, frequency analysis, and live API docs via `help.py`
  - `dashboard-expert` — Auto-triggered on dashboard requests; full CRUD for Mixpanel dashboards with layout system, text cards, report arrangement, and 9 design templates
- **Scripts**: `help.py` (live API documentation with fuzzy search) and `auth_manager.py` (programmatic credential management)
- **Secure by design**: Credentials managed outside conversation context

Learn more: [Plugin Documentation](mixpanel-plugin/README.md)

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup and guidelines.

## License

MIT
