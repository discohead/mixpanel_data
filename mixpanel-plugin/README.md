# mixpanel-headless — CodeMode Analyst Plugin

Query and analyze Mixpanel data with Python. Provides the `mixpanel_headless` API surface (5 query engines, discovery, entity CRUD) with a live documentation system (`help.py`) for method signatures, type lookup, fuzzy search, and hosted docs. Ask questions in natural language — Claude writes and executes Python to answer them.

## Quick Start

```
1. /mixpanel-headless:setup              # Install deps, verify auth
2. "How many signups last week?"      # Insights query
3. "Where do users drop off?"         # Funnel analysis
4. "Do users retain after onboarding?"# Retention curve
5. "What do users do after signup?"   # Flow analysis
6. "Who are our power users?"         # User profile query
```

## Query Engines

| Engine | Method | Core Question | Result Type |
|--------|--------|---------------|-------------|
| Insights | `ws.query()` | How much? How many? Trends? | `QueryResult` |
| Funnels | `ws.query_funnel()` | Do users convert through a sequence? | `FunnelQueryResult` |
| Retention | `ws.query_retention()` | Do users come back? | `RetentionQueryResult` |
| Flows | `ws.query_flow()` | What paths do users take? | `FlowQueryResult` |
| Users | `ws.query_user()` | Who are they? What do they look like? | `UserQueryResult` |

When you ask a question, Claude writes Python using the appropriate engine:

### Insights (trending metrics)

```python
import mixpanel_headless as mp
ws = mp.Workspace()
result = ws.query("Signup", last=30, unit="day")
df = result.df  # date, event, count

# With group_by segmentation
result = ws.query("Signup", last=30, group_by="platform")
df = result.df  # date, event, segment, count
```

### Funnels (conversion analysis)

```python
result = ws.query_funnel(
    ["Signup", "Onboarding Complete", "First Purchase"],
    conversion_window=14,
)
print(result.overall_conversion_rate)
print(result.df)  # step, event, count, step_conv_ratio, avg_time
```

### Retention (user return behavior)

```python
result = ws.query_retention(
    "Signup", "Login",
    retention_unit="week", last=90,
)
print(result.average)  # synthetic average across cohorts
print(result.df)       # cohort_date, bucket, count, rate
```

### Flows (user path analysis)

```python
result = ws.query_flow("Signup", forward=4)
g = result.graph                   # networkx DiGraph
print(result.top_transitions(5))   # highest-traffic paths
print(result.drop_off_summary())   # per-step drop-off

# Tree mode
result = ws.query_flow("Signup", mode="tree")
for tree in result.trees:
    print(tree.render())           # ASCII visualization
```

### Users (profile queries)

```python
from mixpanel_headless import Filter

result = ws.query_user(
    filters=Filter.greater_than("purchase_count", 10),
    properties=["$name", "$email", "plan"],
)
print(result.df)  # distinct_id, $name, $email, plan
```

## API Documentation

Use `help.py` for live API docs extracted from library docstrings, or browse the [hosted documentation](https://mixpanel.github.io/mixpanel-headless/).

```bash
python help.py Workspace.query        # method signature + docstring + referenced types
python help.py search cohort           # fuzzy search across names, docstrings, enum members
python help.py Filter                  # type fields + construction patterns + related methods
python help.py types                   # list all public types
python help.py exceptions              # list all exceptions
```

## Components

| Type | Name | Invocation |
|------|------|------------|
| Command | auth | `/mixpanel-headless:auth` — manage account / project / workspace / target / session / bridge |
| Skill | setup | `/mixpanel-headless:setup` — install deps, verify auth |
| Skill | mixpanelyst | Auto-triggered on analytics questions |
| Skill | dashboard-expert | Auto-triggered on dashboard analysis, creation, and modification |

| Script | Purpose |
|--------|---------|
| `help.py` | Live API documentation lookup with fuzzy search |
| `auth_manager.py` | Programmatic auth subcommand wrapper (JSON output, `schema_version: 1`) |

## Beyond Querying

The plugin also provides full entity CRUD via the Mixpanel App API:

- **Dashboards** — create, layout, text cards, blueprints, RCA dashboards
- **Reports/Bookmarks** — save queries as persistent reports
- **Cohorts** — define and manage user segments
- **Feature Flags & Experiments** — lifecycle management
- **Alerts & Annotations** — monitoring and timeline markers
- **Webhooks** — event-driven integrations
- **Data Governance** — Lexicon definitions, drop filters, custom properties, custom events, lookup tables, schema registry
- **Business Context** — read/write the markdown documentation that grounds AI assistants (org and project scopes, 50,000-char cap)

All entity methods require a workspace ID. Use `ws.resolve_workspace_id()` to auto-discover it. Business context lives at the project + org level, so it is **not** workspace-scoped — it works as soon as a project is set.

## Authentication

Three account types — `service_account` (Basic Auth), `oauth_browser` (PKCE
browser flow), and `oauth_token` (static bearer for CI / agents) — managed
through a single Account → Project → Workspace hierarchy. The recommended
starter command is `mp login`: it detects the right auth path from the
environment, derives the account name from `/me`, and pins a default
project in one call. SA and oauth_token paths probe `us → eu → in` for
the region; the browser PKCE path defaults to `us` (pass `--region
eu|in` for other clusters). Run `/mixpanel-headless:setup`
for first-time configuration, or `/mixpanel-headless:auth` to switch
accounts, projects, workspaces, or saved targets after initial setup.

## Installation

### From GitHub

```bash
/plugin marketplace add mixpanel/mixpanel-headless
/plugin install mixpanel-headless@mixpanel-headless-marketplace
```

### Local development

```bash
claude --plugin-dir /path/to/mixpanel_headless/mixpanel-plugin
```

Use `/reload-plugins` to pick up changes without restarting.

## Prerequisites

- Python 3.10+
- Mixpanel service account credentials (or OAuth)
- Claude Code with plugins enabled

## Directory Structure

```
mixpanel-plugin/
├── .claude-plugin/
│   └── plugin.json                     # Plugin manifest
├── skills/
│   ├── setup/
│   │   ├── SKILL.md                    # /mixpanel-headless:setup
│   │   └── scripts/
│   │       └── setup.sh               # Dependency installer
│   ├── dashboard-expert/
│   │   ├── SKILL.md                    # Dashboard analyze, build, modify, explain
│   │   └── references/
│   │       ├── dashboard-reference.md  # API, layout, text cards, gotchas
│   │       ├── dashboard-templates.md  # 9 design templates (KPI, AARRR, etc.)
│   │       ├── bookmark-pipeline.md    # Query → bookmark → dashboard
│   │       └── chart-types.md          # Chart type selection guide
│   └── mixpanelyst/
│       ├── SKILL.md                    # API reference (distilled workspace.py)
│       └── scripts/
│           ├── help.py                 # Live API documentation lookup
│           └── auth_manager.py         # Auth status and management
├── commands/
│   └── auth.md                         # /mixpanel-headless:auth command
├── docs/
│   ├── quickstart-claude-code.md       # Getting started (Claude Code)
│   ├── quickstart-claude-cowork.md     # Getting started (Cowork)
│   └── getting-started-guide.md        # General getting started
└── README.md
```

## Links

- [Library documentation](https://mixpanel.github.io/mixpanel-headless/)
- [Source repository](https://github.com/mixpanel/mixpanel-headless)

## License

MIT
