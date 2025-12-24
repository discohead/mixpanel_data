# mixpanel_data — Project Specification

> A foundational Python library and CLI for working with Mixpanel data, designed for AI coding agents.

**Version:** 1.0 Draft
**Date:** December 2024
**Author:** Jared Stenquist

> **Note:** This is a high-level project vision document. For authoritative API reference, see:
> - [mixpanel_data-api-specification.md](mixpanel_data-api-specification.md) — Python API
> - [mp-cli-api-specification.md](mp-cli-api-specification.md) — CLI command reference

---

## Executive Summary

`mixpanel_data` is a Python library and command-line tool that enables terminal-based coding agents (Claude Code, Cursor, etc.) to interact with Mixpanel data efficiently. Unlike the Mixpanel MCP server which dumps API responses directly into the context window, `mixpanel_data` takes a **database-first approach**: fetch data once, store it locally in DuckDB, then run unlimited queries against the local database.

### Naming

| Context | Name | Example |
|---------|------|---------|
| PyPI package | `mixpanel_data` | `pip install mixpanel_data` |
| Python import | `mixpanel_data` (aliased to `mp`) | `import mixpanel_data as mp` |
| CLI command | `mp` | `mp events fetch --from 2024-01-01` |

The name emphasizes the library's role as a **foundational layer for working with Mixpanel data**—querying, fetching, inspecting, transforming, and analyzing.

This preserves the agent's context window for reasoning and insights rather than consuming it with raw data. The tool also supports live Mixpanel queries for quick answers and provides comprehensive data discovery capabilities.

### Key Insight

```
┌─────────────────────────────────────────────────────────────┐
│  MCP Approach                                               │
│  Agent asks question → API call → 30KB JSON in context      │
│  Agent asks another question → API call → 30KB more         │
│  Context window fills up with data, not thinking            │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│  mp Approach                                                │
│  Agent fetches data once → stored in local DuckDB           │
│  Agent queries shape → small schema response                │
│  Agent runs SQL → precise answer, minimal tokens            │
│  Context window preserved for reasoning                     │
└─────────────────────────────────────────────────────────────┘
```

---

## Goals

1. **Context window efficiency** — Minimize tokens consumed by data; maximize tokens available for reasoning
2. **Agent-native design** — All commands are non-interactive, output structured data, compose into unix pipelines
3. **Two-path data access** — Live queries for quick answers, local database for deep analysis
4. **Library-first architecture** — CLI wraps a well-designed Python library that agents can import directly
5. **Data discovery** — Agents can introspect what events, properties, and values exist before querying
6. **Unix philosophy** — Do one thing well, compose with other tools via stdout/stdin

## Non-Goals (for MVP)

1. **Plugin system** — Architected for extensibility, but not implemented in v1
2. **Interactive modes** — `mp db shell` and `mp explore repl` are human-only conveniences
3. **Visualization** — Output is data (JSON/CSV/table), not charts
4. **Real-time streaming** — Batch fetch, not live event streams
5. **Write operations** — Read-only; no sending events or modifying Mixpanel data

---

## Architecture

### Library-First Design

```
┌─────────────────────────────────────────────────────────────┐
│  CLI Layer (thin)                                           │
│  mp/cli/                                                    │
│  - Argument parsing (Typer)                                 │
│  - Output formatting (Rich)                                 │
│  - Exit codes, error messages                               │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  Library Layer (thick)                                      │
│  mp/client/  — Mixpanel API client                          │
│  mp/db/      — DuckDB operations                            │
│  mp/models/  — Pydantic data models                         │
│  All actual logic lives here                                │
└─────────────────────────────────────────────────────────────┘
```

### Two Data Paths

| Path | Commands | Data Source | Use Case |
|------|----------|-------------|----------|
| **Live Query** | `mp report *`, `mp schema *` | Mixpanel Query API | Quick answers, data discovery |
| **Local Analysis** | `mp events fetch`, `mp query` | Local DuckDB | Deep exploration, custom analysis |

### Technology Stack

| Component | Technology | Rationale |
|-----------|------------|-----------|
| Language | Python 3.11+ | DuckDB/Pandas ecosystem, your familiarity |
| CLI Framework | Typer | Type hints, minimal boilerplate, auto-help |
| Output Formatting | Rich | Tables, progress bars, colors |
| Validation | Pydantic | API response validation, settings management |
| Database | DuckDB | Embedded, analytical, excellent JSON support |
| HTTP Client | httpx | Async support, modern API |

**pyproject.toml (key sections):**

```toml
[project]
name = "mixpanel_data"
description = "Python library and CLI for working with Mixpanel data"
requires-python = ">=3.11"
dependencies = [
    "typer>=0.9.0",
    "rich>=13.0.0",
    "pydantic>=2.0.0",
    "duckdb>=0.9.0",
    "httpx>=0.25.0",
    "pandas>=2.0.0",
]

[project.scripts]
mp = "mixpanel_data.cli.main:app"

[project.optional-dependencies]
dev = ["pytest", "pytest-cov", "ruff", "mypy"]
notebooks = ["marimo", "jupyter", "altair"]
```

---

## Project Structure

```
mixpanel_data/
├── pyproject.toml
├── README.md
├── LICENSE
│
├── src/
│   └── mixpanel_data/               # The library (import mixpanel_data as mp)
│       ├── __init__.py              # Public API exports
│       ├── __main__.py              # python -m mixpanel_data entry point
│       ├── py.typed                 # PEP 561 marker
│       │
│       ├── client/                  # Mixpanel API client
│       │   ├── __init__.py
│       │   ├── auth.py              # Authentication, credentials
│       │   ├── config.py            # Configuration management
│       │   ├── export.py            # Export API (raw events)
│       │   ├── query.py             # Query API (reports)
│       │   ├── engage.py            # Engage API (user profiles)
│       │   └── exceptions.py        # API-specific exceptions
│       │
│       ├── db/                      # Local database layer
│       │   ├── __init__.py
│       │   ├── connection.py        # DuckDB connection management
│       │   ├── schema.py            # Table definitions, migrations
│       │   ├── store.py             # Write operations
│       │   ├── query.py             # Read operations
│       │   └── workspace.py         # Workspace/lifecycle management
│       │
│       ├── models/                  # Pydantic models
│       │   ├── __init__.py
│       │   ├── events.py            # Event schema
│       │   ├── users.py             # User profile schema
│       │   ├── reports.py           # Report response schemas
│       │   └── config.py            # Configuration schemas
│       │
│       └── cli/                     # CLI layer
│           ├── __init__.py
│           ├── main.py              # Typer app, command registration
│           ├── commands/
│           │   ├── __init__.py
│           │   ├── auth.py          # mp auth *
│           │   ├── events.py        # mp events *
│           │   ├── users.py         # mp users *
│           │   ├── db.py            # mp db *
│           │   ├── query.py         # mp query
│           │   ├── report.py        # mp report *
│           │   ├── schema.py        # mp schema *
│           │   ├── explore.py       # mp explore *
│           │   └── raw.py           # mp raw
│           ├── formatters/
│           │   ├── __init__.py
│           │   ├── table.py
│           │   ├── json.py
│           │   └── csv.py
│           └── utils.py             # Shared CLI utilities
│
├── templates/                       # Generated file templates
│   ├── notebook.ipynb.jinja         # Jupyter notebook template
│   └── marimo_app.py.jinja          # marimo app template
│
├── tests/
│   ├── conftest.py                  # Pytest fixtures
│   ├── test_client/
│   ├── test_db/
│   └── test_cli/
│
└── docs/
    └── SKILL.md                     # Agent skill documentation
```

---

## Command Specification

### Global Flags

All commands support these global options (before the command):

```
--account <name>     Use a specific named account instead of the default
--quiet              Suppress progress and status output
--verbose            Enable debug output
--help               Show help for any command
--version            Show version information
```

Per-command options (after the command):

```
--format <fmt>       Output format: json (default), jsonl, table, csv, plain
```

### `mp auth` — Authentication & Project Management

```bash
mp auth login                      # Interactive login flow
mp auth login --token <token>      # Direct token auth (for CI)
mp auth status                     # Show current auth state
mp auth logout                     # Clear credentials
mp auth list                       # List configured projects
mp auth switch <project>           # Switch default project
mp auth add <name> --token <token> # Add a named project
mp auth remove <project>           # Remove a saved project
```

**Config file:** `~/.mp/config.toml`

```toml
default_project = "production"

[projects.production]
token = "abc123..."
api_secret = "..."          # Optional, for some endpoints
region = "US"               # US | EU

[projects.staging]
token = "xyz789..."
region = "US"

[settings]
default_format = "table"
```

**Environment variables:**
- `MP_PROJECT_TOKEN` — Override project token
- `MP_API_SECRET` — Override API secret
- `MP_REGION` — Override region (US/EU)
- `MP_EPHEMERAL=1` — Force ephemeral mode

**Library API:**

```python
from mixpanel_data.client.auth import login, logout, get_current_project, switch_project

login(token="...")
project = get_current_project()
switch_project("staging")
```

---

### `mp events` — Fetch Event Data

```bash
# Basic fetch
mp events fetch --from 2024-01-01
mp events fetch --from 2024-01-01 --to 2024-01-31

# Filter by event names
mp events fetch --from 2024-01-01 --event "Sign Up" --event "Purchase"

# Filter by properties (JQL-style expression)
mp events fetch --from 2024-01-01 --where 'properties["$browser"] == "Chrome"'

# Limit rows (useful for sampling)
mp events fetch --from 2024-01-01 --limit 10000

# Data handling
mp events fetch --from 2024-01-01 --append    # Add to existing (default)
mp events fetch --from 2024-01-01 --replace   # Drop existing first

# Progress control
mp events fetch --from 2024-01-01 --quiet     # No progress output
mp events fetch --from 2024-01-01 --dry-run   # Show what would be fetched

# List fetched events summary
mp events list                                 # Show events in local DB
```

**Library API:**

```python
from mixpanel_data.client.export import fetch_events
from mixpanel_data.models.events import FetchResult

result: FetchResult = fetch_events(
    from_date="2024-01-01",
    to_date="2024-01-31",
    events=["Sign Up", "Purchase"],
    where='properties["$browser"] == "Chrome"',
    limit=10000,
    replace=False,
    progress_callback=lambda current, total: ...,
)

print(f"Fetched {result.count} events")
```

---

### `mp users` — Fetch User Profiles

```bash
# Fetch all profiles
mp users fetch

# Fetch by cohort
mp users fetch --cohort "Power Users"
mp users fetch --cohort-id 12345

# Fetch recently active
mp users fetch --active-since 2024-01-01

# Select specific properties (reduces payload)
mp users fetch --properties '$email' '$name' 'plan_type'

# Data handling
mp users fetch --replace   # Drop existing first
```

**Library API:**

```python
from mixpanel_data.client.engage import fetch_users

result = fetch_users(
    cohort="Power Users",
    active_since="2024-01-01",
    properties=["$email", "$name", "plan_type"],
)
```

---

### `mp db` — Database Introspection & Management

```bash
# Table information
mp db tables                       # List tables with row counts
mp db schema <table>               # Show columns and types
mp db sample <table> --limit 5     # Preview data
mp db stats <table>                # Summary statistics

# Column exploration
mp db describe <table> <column>    # Unique values, distribution
mp db describe events properties   # Property keys in JSON column

# Database management
mp db path                         # Print path to DB file
mp db size                         # Size on disk
mp db reset                        # Drop all tables
mp db export <file>                # Export to parquet/csv
mp db vacuum                       # Reclaim disk space

# Workspace management
mp db workspace list               # List workspaces
mp db workspace create <name>      # Create new workspace
mp db workspace switch <name>      # Switch workspace
mp db workspace delete <name>      # Delete workspace

# Human-only (interactive)
mp db shell                        # Drop into DuckDB CLI
```

**Library API:**

```python
from mixpanel_data.db import get_tables, get_schema, get_stats, describe_column

tables = get_tables()  # [{"name": "events", "rows": 145232}, ...]
schema = get_schema("events")  # [{"column": "event", "type": "VARCHAR"}, ...]
stats = get_stats("events")  # {"rows": 145232, "date_range": [...], ...}
values = describe_column("events", "event")  # [{"value": "Sign Up", "count": 12453}, ...]
```

---

### `mp query` — Run SQL

```bash
# Basic query
mp query "SELECT event, COUNT(*) FROM events GROUP BY 1"

# Output formats
mp query "..." --format table      # Pretty ASCII table (default)
mp query "..." --format json       # JSON array of objects
mp query "..." --format jsonl      # Newline-delimited JSON
mp query "..." --format csv        # CSV

# Save to file
mp query "..." --output results.csv

# Read query from file
mp query --file analysis.sql

# Query JSON properties
mp query "SELECT properties->>'$browser' as browser, COUNT(*) FROM events GROUP BY 1"
```

**Library API:**

```python
from mixpanel_data.db import query, query_df

# Returns list of dicts
results = query("SELECT event, COUNT(*) as n FROM events GROUP BY 1")

# Returns pandas DataFrame
df = query_df("SELECT * FROM events WHERE event = 'Sign Up'")
```

---

### `mp report` — Live Mixpanel Queries

These call Mixpanel's Query API directly (like the MCP server does).

```bash
# Segmentation
mp report segmentation "Sign Up" --from 2024-01-01
mp report segmentation "Sign Up" --from 2024-01-01 --by day
mp report segmentation "Sign Up" --from 2024-01-01 --group-by '$browser'
mp report segmentation "Purchase" --from 2024-01-01 --measure sum --property amount

# Funnel
mp report funnel "Sign Up" "Purchase" --from 2024-01-01
mp report funnel "Sign Up" "Onboarding" "Purchase" --from 2024-01-01 --window 7d
mp report funnel "Sign Up" "Purchase" --from 2024-01-01 --group-by 'utm_source'

# Retention
mp report retention --born "Sign Up" --return "Login" --from 2024-01-01
mp report retention --born "Sign Up" --return "any" --from 2024-01-01 --by week

# Frequency
mp report frequency "Login" --from 2024-01-01
mp report frequency "Login" --from 2024-01-01 --buckets "1,2-5,6-10,11+"

# Save report results to local DB for further analysis
mp report funnel "Sign Up" "Purchase" --from 2024-01-01 --save-as signup_funnel
mp query "SELECT * FROM signup_funnel WHERE conversion_rate < 0.1"
```

**Library API:**

```python
from mixpanel_data.client.query import segmentation, funnel, retention, frequency

result = segmentation(
    event="Sign Up",
    from_date="2024-01-01",
    by="day",
    group_by="$browser",
)

result = funnel(
    events=["Sign Up", "Purchase"],
    from_date="2024-01-01",
    window_days=7,
)

result = retention(
    born_event="Sign Up",
    return_event="Login",
    from_date="2024-01-01",
)
```

---

### `mp schema` — Data Discovery

These query Mixpanel's API to discover what data exists (without fetching raw events).

```bash
# List all events
mp schema events
mp schema events --limit 20        # Top 20 by volume

# List properties for an event
mp schema properties "Sign Up"
mp schema properties "Sign Up" --type string   # Filter by type

# List values for a property
mp schema values "Sign Up" "plan_selected"
mp schema values "Sign Up" "$browser" --limit 10
```

**Output example:**

```
$ mp schema events
┌─────────────────┬────────────┬─────────────────────────────┐
│ event           │ count_30d  │ description                 │
├─────────────────┼────────────┼─────────────────────────────┤
│ Page View       │ 892,034    │                             │
│ Sign Up         │ 12,453     │ User completed registration │
│ Purchase        │ 3,421      │ Completed purchase          │
└─────────────────┴────────────┴─────────────────────────────┘

$ mp schema properties "Sign Up"
┌─────────────────┬───────────┬──────────────────────────┐
│ property        │ type      │ example_values           │
├─────────────────┼───────────┼──────────────────────────┤
│ $browser        │ string    │ Chrome, Safari, Firefox  │
│ utm_source      │ string    │ google, facebook, twitter│
│ plan_selected   │ string    │ free, pro, team          │
└─────────────────┴───────────┴──────────────────────────┘

$ mp schema values "Sign Up" "plan_selected"
┌───────────┬────────┬─────────┐
│ value     │ count  │ percent │
├───────────┼────────┼─────────┤
│ free      │ 8,234  │ 66.1%   │
│ pro       │ 3,102  │ 24.9%   │
│ team      │ 1,117  │ 9.0%    │
└───────────┴────────┴─────────┘
```

**Library API:**

```python
from mixpanel_data.client.query import get_events, get_properties, get_property_values

events = get_events()
properties = get_properties("Sign Up")
values = get_property_values("Sign Up", "plan_selected")
```

---

### `mp raw` — Direct API Access

Escape hatch for API endpoints not covered by other commands.

```bash
# Raw export
mp raw export --from 2024-01-01 --to 2024-01-31

# Raw JQL query
mp raw jql --script 'function main() { return Events({...}) }'

# Raw engage query
mp raw engage --where 'properties["$last_seen"] > "2024-01-01"'

# Output always goes to stdout (doesn't touch DB)
mp raw export --from 2024-01-01 | jq '.[] | select(.event == "Purchase")'
```

---

### `mp explore` — Notebook Generation

Generate starter notebooks pre-configured with `mp`. These are human-oriented outputs that agents generate for interactive exploration.

```bash
# Generate Jupyter notebook
mp explore notebook                              # Creates exploration.ipynb
mp explore notebook --output analysis.ipynb      # Custom filename

# Generate marimo reactive app
mp explore marimo                                # Creates exploration.py
mp explore marimo --output dashboard.py          # Custom filename

# Include specific data context in the generated notebook
mp explore marimo --include-events "Sign Up" "Purchase"
mp explore notebook --from 2024-01-01 --to 2024-01-31
```

**Generated marimo app structure:**

```python
# exploration.py (this IS the marimo notebook)
import marimo as mo

app = mo.App()

@app.cell
def setup():
    import mixpanel_data as mp
    import altair as alt
    mp.connect()
    return mp, alt

@app.cell
def interactive_controls(mp):
    dates = mo.ui.date_range(label="Date Range")
    events = mo.ui.multiselect(
        options=[e['name'] for e in mp.get_events()],
        label="Events"
    )
    return dates, events

@app.cell
def visualization(mp, alt, dates, events):
    df = mp.query_df(f"""
        SELECT DATE_TRUNC('day', time) as day, event, COUNT(*) as count
        FROM events
        WHERE event IN ({','.join(f"'{e}'" for e in events.value)})
        GROUP BY 1, 2
    """)
    return mo.ui.altair_chart(
        alt.Chart(df).mark_line().encode(x='day:T', y='count:Q', color='event:N')
    )

if __name__ == "__main__":
    app.run()
```

**Usage:**
- Edit: `marimo edit exploration.py`
- Run as app: `marimo run exploration.py`
- Run as script: `python exploration.py`

**Note:** `mp explore notebook` and `mp explore marimo` generate files for humans to open. Claude Code cannot interact with these interactively, but it can generate, edit, and run them as scripts.

---

## Data Models

### Database Schema

```sql
-- Events table
CREATE TABLE events (
    -- Mixpanel fields
    insert_id VARCHAR PRIMARY KEY,
    event VARCHAR NOT NULL,
    distinct_id VARCHAR,
    time TIMESTAMP NOT NULL,
    properties JSON,
    
    -- Extracted for fast filtering (optional optimization)
    mp_country VARCHAR,
    mp_city VARCHAR,
    mp_device VARCHAR,
    mp_os VARCHAR,
    mp_browser VARCHAR,
    
    -- Metadata
    _fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_events_event ON events(event);
CREATE INDEX idx_events_time ON events(time);
CREATE INDEX idx_events_distinct_id ON events(distinct_id);

-- Users table
CREATE TABLE users (
    distinct_id VARCHAR PRIMARY KEY,
    properties JSON,
    
    -- Extracted common fields
    mp_email VARCHAR,
    mp_name VARCHAR,
    mp_created TIMESTAMP,
    mp_last_seen TIMESTAMP,
    
    -- Metadata
    _fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Report cache (for --save-as functionality)
CREATE TABLE _report_cache (
    name VARCHAR PRIMARY KEY,
    report_type VARCHAR NOT NULL,
    parameters JSON,
    result JSON,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Fetch metadata
CREATE TABLE _fetch_log (
    id INTEGER PRIMARY KEY,
    table_name VARCHAR NOT NULL,
    from_date DATE,
    to_date DATE,
    filters JSON,
    row_count INTEGER,
    fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### Pydantic Models

```python
# mixpanel_data/models/events.py
from pydantic import BaseModel
from datetime import datetime
from typing import Any

class MixpanelEvent(BaseModel):
    insert_id: str | None = None
    event: str
    distinct_id: str | None = None
    time: datetime
    properties: dict[str, Any] = {}

class FetchResult(BaseModel):
    count: int
    from_date: str
    to_date: str
    events_filter: list[str] | None = None

# mixpanel_data/models/config.py
class ProjectConfig(BaseModel):
    token: str
    api_secret: str | None = None
    region: str = "US"  # US | EU

class Config(BaseModel):
    default_project: str | None = None
    projects: dict[str, ProjectConfig] = {}
    settings: dict[str, Any] = {}
```

---

## Database Lifecycle

### Storage Locations

```
~/.mp/
├── config.toml                              # Global configuration
├── credentials/                             # Secure token storage
│   └── ...
└── data/
    └── <project-token>/
        ├── default.duckdb                   # Default workspace
        ├── q4-analysis.duckdb               # Named workspace
        └── .tmp-<uuid>.duckdb               # Ephemeral databases
```

### Lifecycle Modes

| Mode | Flag/Env | Storage | Cleanup |
|------|----------|---------|---------|
| Persistent (default) | — | `~/.mp/data/<token>/default.duckdb` | Manual |
| Named workspace | `mp db workspace create X` | `~/.mp/data/<token>/X.duckdb` | Manual |
| Ephemeral | `--ephemeral` or `MP_EPHEMERAL=1` | Temp file | On process exit |

### Ephemeral Implementation

```python
# mixpanel_data/db/workspace.py
import atexit
import signal
import tempfile
import os

class EphemeralDatabase:
    def __init__(self):
        self.path = tempfile.mktemp(suffix='.duckdb', prefix='.tmp-')
        atexit.register(self.cleanup)
        signal.signal(signal.SIGTERM, self._signal_handler)
        signal.signal(signal.SIGINT, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        self.cleanup()
        sys.exit(0)
    
    def cleanup(self):
        if os.path.exists(self.path):
            os.remove(self.path)
            # Also remove DuckDB's WAL files
            for suffix in ['.wal', '.tmp']:
                wal = self.path + suffix
                if os.path.exists(wal):
                    os.remove(wal)
```

### Garbage Collection

```bash
# Clean up orphaned temp databases (crashed processes)
mp db prune --temp

# Clean up old workspaces
mp db prune --older-than 30d

# Full reset
mp db reset
```

---

## Library Public API

The library uses a **Workspace facade pattern** that provides a single entry point for all operations. The `Workspace` class orchestrates credentials, API client, storage, and services.

```python
# mixpanel_data/__init__.py

"""
mixpanel_data - Python library and CLI for working with Mixpanel data.

Usage as library:
    import mixpanel_data as mp

    with mp.Workspace(path="./analytics.db") as ws:
        # Fetch data to local storage
        ws.fetch_events("signups", from_date="2024-01-01", to_date="2024-01-31")

        # Query locally with SQL
        df = ws.query_df("SELECT event, COUNT(*) FROM signups GROUP BY 1")

        # Or use live Mixpanel queries
        result = ws.segmentation(event="Sign Up", from_date="2024-01-01")

Usage as CLI:
    mp fetch events --from 2024-01-01 --name signups
    mp query "SELECT * FROM signups"
"""

# Public API
from mixpanel_data.workspace import Workspace, ephemeral

# Auth utilities
from mixpanel_data.auth import (
    ConfigManager,
    Credentials,
    resolve_credentials,
)

# Exceptions
from mixpanel_data.exceptions import (
    MixpanelDataError,
    ConfigError,
    AccountNotFoundError,
    AccountExistsError,
    AuthenticationError,
    RateLimitError,
    QueryError,
    TableExistsError,
    TableNotFoundError,
)

# Result types (all frozen dataclasses with .df property)
from mixpanel_data.types import (
    # Fetch results
    FetchResult,
    TableMetadata,

    # Live query results
    SegmentationResult,
    FunnelResult,
    FunnelStep,
    RetentionResult,
    CohortInfo,
    JQLResult,
    EventCountsResult,
    PropertyCountsResult,
    ActivityFeedResult,
    InsightsResult,
    FrequencyResult,
    NumericBucketResult,
    NumericSumResult,
    NumericAverageResult,

    # Discovery types
    FunnelInfo,
    SavedCohort,
    TopEvent,

    # Introspection types
    TableInfo,
    TableSchema,
    ColumnInfo,
    WorkspaceInfo,
)

__all__ = [
    # Core
    "Workspace",
    "ephemeral",

    # Auth
    "ConfigManager",
    "Credentials",
    "resolve_credentials",

    # Exceptions
    "MixpanelDataError",
    "ConfigError",
    "AccountNotFoundError",
    "AccountExistsError",
    "AuthenticationError",
    "RateLimitError",
    "QueryError",
    "TableExistsError",
    "TableNotFoundError",

    # Result types
    "FetchResult",
    "TableMetadata",
    "SegmentationResult",
    "FunnelResult",
    "FunnelStep",
    "RetentionResult",
    "CohortInfo",
    "JQLResult",
    "EventCountsResult",
    "PropertyCountsResult",
    "ActivityFeedResult",
    "InsightsResult",
    "FrequencyResult",
    "NumericBucketResult",
    "NumericSumResult",
    "NumericAverageResult",
    "FunnelInfo",
    "SavedCohort",
    "TopEvent",
    "TableInfo",
    "TableSchema",
    "ColumnInfo",
    "WorkspaceInfo",
]
```

**Recommended usage pattern:**

```python
import mixpanel_data as mp

# Persistent workspace (data survives sessions)
with mp.Workspace(path="./analytics.db") as ws:
    ws.fetch_events("signups", from_date="2024-01-01", to_date="2024-01-31")
    df = ws.query_df("SELECT event, COUNT(*) FROM signups GROUP BY 1")

# Ephemeral workspace (auto-cleanup, great for exploration)
with mp.ephemeral() as ws:
    result = ws.segmentation(event="Sign Up", from_date="2024-01-01")
    print(result.df)
```

See [mixpanel_data-design.md](mixpanel_data-design.md#workspace-class) for complete Workspace API documentation.

---

## Implementation Phases

> **Note:** This section provides a high-level overview. For the authoritative, detailed implementation plan with task checklists, see **[IMPLEMENTATION_PLAN.md](../IMPLEMENTATION_PLAN.md)**.

The implementation is organized into 11 phases:

| Phase | Name | Description | Status |
|-------|------|-------------|--------|
| 001 | Foundation Layer | Config, credentials, exceptions | ✅ Complete |
| 002 | API Client | HTTP client with auth, rate limiting, streaming | ✅ Complete |
| 003 | Storage Engine | DuckDB-based storage with metadata | ✅ Complete |
| 004 | Discovery Service | Event/property schema introspection | ✅ Complete |
| 005 | Fetch Service | Event/profile fetching to local storage | ✅ Complete |
| 006 | Live Query Service | Segmentation, funnels, retention, JQL | ✅ Complete |
| 007 | Discovery Enhancements | Funnels, cohorts, top events, event/property counts | ✅ Complete |
| 008 | Query Service Enhancements | Activity feed, insights, frequency, numeric aggregations | ✅ Complete |
| **009** | **Workspace Facade** | **Unified `Workspace` class as single entry point** | ⏳ Next |
| 010 | CLI Application | Typer-based `mp` command-line interface | ⏳ Pending |
| 011 | Polish & Release | Documentation, examples, PyPI release | ⏳ Pending |

**Current state:** Phases 001-008 complete. All services (Discovery, Fetcher, LiveQuery) and infrastructure (Config, API Client, Storage) are implemented with comprehensive test coverage.

**Next up:** Phase 009 implements the `Workspace` facade that provides a clean, unified API over all services. This is the primary entry point for library users.

---

## Agent Skill Specification

The skill teaches Claude Code (and other agents) how to use `mixpanel_data` effectively.

```markdown
---
name: mixpanel_data
description: Query and analyze Mixpanel data via the mp CLI and Python library. Use for product 
  analytics questions, user behavior analysis, funnel optimization, and retention analysis. 
  Triggers on "mixpanel", "analytics", "funnel", "retention", "user behavior", "event data".
---

# Mixpanel Data Skill

## Overview

`mixpanel_data` is a Python library and CLI for working with Mixpanel data. 

**Install:** `pip install mixpanel_data`
**CLI command:** `mp`
**Python import:** `import mixpanel_data as mp`

It provides two paths:
- **Live queries** (`mp report`, `mp schema`) — Call Mixpanel API directly
- **Local analysis** (`mp events fetch`, `mp query`) — Store data locally, query with SQL

## When to Use Each Approach

**Use `mp report` for:**
- Quick answers about metrics ("How many signups this week?")
- Standard analytics (funnels, retention, segmentation)
- When you need fresh, real-time data

**Use `mp events fetch` + `mp query` for:**
- Deep exploration of user behavior
- Custom analysis not covered by standard reports
- Joining event data with user data
- Statistical analysis or ML tasks

**Use `mp schema` for:**
- Discovering what events exist
- Finding available properties and values
- Understanding the data shape before querying

## Workflow Patterns

### Pattern 1: Quick Answer
```bash
# "What's my signup conversion this month?"
mp report funnel "Sign Up" "Purchase" --from 2024-12-01
```

### Pattern 2: Data Discovery → Query
```bash
# "What events are being tracked?"
mp schema events

# "What properties does Sign Up have?"
mp schema properties "Sign Up"
```

### Pattern 3: Deep Analysis
```bash
# First, check what's in the local database
mp db tables

# If needed, fetch data
mp events fetch --from 2024-01-01 --event "Sign Up" --event "Purchase"

# Understand the shape
mp db stats events
mp db describe events properties

# Query for insights
mp query "
  SELECT 
    DATE_TRUNC('day', time) as day,
    COUNT(DISTINCT distinct_id) as users,
    COUNT(*) as events
  FROM events 
  WHERE event = 'Sign Up'
  GROUP BY 1
  ORDER BY 1
" --format json
```

### Pattern 4: Complex Analysis (Python)
For analysis beyond SQL, write a Python script:

```python
import mixpanel_data as mp

# Fetch data if needed
mp.fetch_events(from_date="2024-01-01", events=["Sign Up", "Purchase"])

# Get DataFrame
df = mp.query_df("SELECT * FROM events")

# Complex pandas/scipy work
signups = df[df['event'] == 'Sign Up']
purchases = df[df['event'] == 'Purchase']

# Calculate conversion by cohort
# ... analysis code

print(result.to_json())
```

Run with: `python analysis.py`

## Command Reference

### Data Discovery
- `mp schema events` — List all events
- `mp schema properties <event>` — Properties for an event
- `mp schema values <event> <property>` — Values for a property

### Live Reports
- `mp report segmentation <event> --from <date>` — Event counts
- `mp report funnel <event1> <event2> ... --from <date>` — Conversion funnel
- `mp report retention --born <event> --return <event> --from <date>` — Retention

### Local Database
- `mp events fetch --from <date> [--event <name>]` — Fetch events to local DB
- `mp db tables` — List tables and row counts
- `mp db schema <table>` — Show columns
- `mp db stats <table>` — Summary statistics
- `mp db describe <table> <column>` — Column value distribution
- `mp query "<sql>" --format json` — Run SQL query

## Best Practices

1. **Check before fetching** — Use `mp db tables` to see if data exists before fetching
2. **Limit initial fetches** — Use `--limit 10000` for exploration, fetch full data only when needed
3. **Use schema discovery** — Run `mp schema events` before writing queries against unknown data
4. **Prefer JSON output** — Use `--format json` for structured output you can process
5. **Pipe through jq** — Combine with `jq` for complex JSON transformations

## Notebook Integration

`mixpanel_data` works in any notebook environment.

### Quick Exploration (Jupyter/Colab)
```python
import mixpanel_data as mp
df = mp.query_df("SELECT * FROM events")
df.plot()
```

### Interactive Exploration (marimo)
For reactive exploration with UI controls, generate a marimo app:

```bash
mp explore marimo --output exploration.py
marimo edit exploration.py
```

The generated marimo notebook includes:
- mp library pre-imported and connected
- Interactive date pickers and event selectors  
- Reactive visualizations that update automatically

marimo apps are pure Python files—you can generate them, edit them, and run them as scripts.

### When to Use Each Approach

| Approach | Use When |
|----------|----------|
| `mp query` CLI | Quick answer, single query |
| `mp` in Python script | Complex analysis, automation |
| `mp` in Jupyter | Human exploration, documentation |
| `mp` in marimo | Interactive apps, sharing with stakeholders |

## Output Formats

All commands support the `--format` option (per-command, placed after the command name):
- `json` — JSON array of objects (default)
- `jsonl` — Newline-delimited JSON (streaming-friendly)
- `table` — Human-readable ASCII table
- `csv` — Comma-separated values
- `plain` — Minimal output (one value per line)

---

## Future Considerations

### Plugin Architecture (v2)

```python
# Plugin interface
from mixpanel_data.plugins import Plugin, command
import mixpanel_data as mp

class ForecastPlugin(Plugin):
    name = "forecast"
    
    @command()
    def run(self, metric: str, horizon: int = 30):
        """Forecast a metric using Prophet."""
        df = mp.query_df(f"SELECT date, {metric} FROM daily_metrics")
        # ... forecasting logic
```

### marimo as "Lens Runtime"

The marimo integration positions `mp explore marimo` as a lightweight alternative to building custom data exploration UIs. Instead of:

```
Build React app → CopilotKit → Custom components → Deploy infrastructure
```

The pattern becomes:

```
mp explore marimo → Agent edits .py file → marimo run → Done
```

A marimo app is simultaneously:
- A readable Python script (Claude Code can generate/edit)
- An interactive notebook (humans can explore)
- A deployable web app (`marimo run --host 0.0.0.0`)

This could evolve into a more sophisticated "Lens" experience where agents generate increasingly complex marimo apps with custom visualizations, AI-powered insights cells, and interactive controls.

### Additional Commands (v2+)

Commands that may be added in future versions:

- `mp annotations` — Event annotations management
- `mp alerts` — Alert configuration and monitoring
- `mp formulas` — Custom metric formulas

### MCP Server (v2+)

Expose `mp` as an MCP server itself, combining both approaches:
- Live queries (like existing Mixpanel MCP)
- Local database operations (unique to `mp`)

---

## Appendix: API Reference

### Mixpanel APIs Used

| API | Endpoint | Used By |
|-----|----------|---------|
| Export | `/api/2.0/export` | `mp events fetch` |
| Query | `/api/2.0/insights` | `mp report *` |
| Engage | `/api/2.0/engage` | `mp users fetch` |
| Events | `/api/2.0/events/names` | `mp schema events` |
| Properties | `/api/2.0/events/properties` | `mp schema properties` |
| Property Values | `/api/2.0/events/properties/values` | `mp schema values` |

### Authentication

Mixpanel uses different auth for different APIs:
- **Export/Engage API:** Project API Secret (Basic Auth)
- **Query API:** Service Account or OAuth
- **Data Management:** Project Token

The `mp auth` system handles this complexity internally.

---

## Appendix: Example Outputs

### `mp db tables`
```
┌─────────┬─────────┬─────────────────────┐
│ table   │ rows    │ last_updated        │
├─────────┼─────────┼─────────────────────┤
│ events  │ 145,232 │ 2024-12-19 10:23:45 │
│ users   │ 12,451  │ 2024-12-19 10:25:12 │
└─────────┴─────────┴─────────────────────┘
```

### `mp db schema events`
```
┌─────────────┬───────────┬──────────┐
│ column      │ type      │ nullable │
├─────────────┼───────────┼──────────┤
│ insert_id   │ VARCHAR   │ NO       │
│ event       │ VARCHAR   │ NO       │
│ distinct_id │ VARCHAR   │ YES      │
│ time        │ TIMESTAMP │ NO       │
│ properties  │ JSON      │ YES      │
│ mp_browser  │ VARCHAR   │ YES      │
│ _fetched_at │ TIMESTAMP │ NO       │
└─────────────┴───────────┴──────────┘
```

### `mp query "..." --format json`
```json
[
  {"event": "Page View", "count": 89234},
  {"event": "Sign Up", "count": 12453},
  {"event": "Purchase", "count": 3421}
]
```

### `mp report funnel "Sign Up" "Purchase" --from 2024-12-01`
```
Funnel: Sign Up → Purchase
Period: 2024-12-01 to 2024-12-19

┌───────────────┬─────────┬────────────┬─────────────┐
│ step          │ users   │ converted  │ conversion  │
├───────────────┼─────────┼────────────┼─────────────┤
│ Sign Up       │ 12,453  │ —          │ —           │
│ Purchase      │ 3,421   │ 3,421      │ 27.5%       │
└───────────────┴─────────┴────────────┴─────────────┘

Overall conversion: 27.5%
```

---

*End of specification.*
