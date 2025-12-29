# CLI Overview

The `mp` command provides full access to mixpanel_data functionality from the command line.

## Installation

The CLI is installed automatically with the package:

```bash
pip install mixpanel_data
```

Verify installation:

```bash
mp --version
```

## Global Options

| Option | Short | Description |
|--------|-------|-------------|
| `--account` | `-a` | Account name to use (overrides default) |
| `--quiet` | `-q` | Suppress progress output |
| `--verbose` | `-v` | Enable debug output |
| `--version` | | Show version and exit |
| `--help` | | Show help and exit |

## Command Groups

### auth — Account Management

Manage stored credentials and accounts.

| Command | Description |
|---------|-------------|
| `mp auth list` | List configured accounts |
| `mp auth add` | Add a new account |
| `mp auth remove` | Remove an account |
| `mp auth switch` | Set the default account |
| `mp auth show` | Display account details |
| `mp auth test` | Test account credentials |

### fetch — Data Fetching

Fetch data from Mixpanel into local storage, or stream directly to stdout.

| Command | Description |
|---------|-------------|
| `mp fetch events` | Fetch events to local DuckDB |
| `mp fetch profiles` | Fetch user profiles to local DuckDB |

**Table Options:**

| Option | Description |
|--------|-------------|
| `--replace` | Drop and recreate existing table |
| `--append` | Add data to existing table (duplicates skipped) |
| `--batch-size` | Rows per commit (100-100000, default: 1000) |

**Streaming Options:**

| Option | Description |
|--------|-------------|
| `--stdout` | Stream data as JSONL to stdout instead of storing |
| `--raw` | Output raw Mixpanel API format (requires `--stdout`) |

**Event Filter Options (fetch events only):**

| Option | Short | Description |
|--------|-------|-------------|
| `--events` | `-e` | Comma-separated event names to filter |
| `--where` | `-w` | Mixpanel filter expression |
| `--limit` | `-l` | Maximum events to return (max 100000) |

**Profile Filter Options (fetch profiles only):**

| Option | Short | Description |
|--------|-------|-------------|
| `--cohort` | `-c` | Filter by cohort ID |
| `--output-properties` | `-o` | Comma-separated properties to include |
| `--where` | `-w` | Mixpanel filter expression |

### query — Query Operations

Execute queries against local or remote data.

| Command | Description |
|---------|-------------|
| `mp query sql` | Query local DuckDB with SQL |
| `mp query segmentation` | Time-series event counts |
| `mp query funnel` | Funnel conversion analysis |
| `mp query retention` | Cohort retention analysis |
| `mp query jql` | Execute JQL scripts |
| `mp query event-counts` | Multi-event time series |
| `mp query property-counts` | Property breakdown time series |
| `mp query activity-feed` | User event history |
| `mp query saved-report` | Query saved reports (Insights, Retention, Funnel) |
| `mp query flows` | Query saved Flows reports |
| `mp query frequency` | Event frequency distribution |
| `mp query segmentation-numeric` | Numeric property bucketing |
| `mp query segmentation-sum` | Numeric property sum |
| `mp query segmentation-average` | Numeric property average |

!!! tip "Saved Reports Workflow"
    Use `mp inspect bookmarks` to list available saved reports and get their IDs, then query them with `mp query saved-report` or `mp query flows`.

### inspect — Discovery & Introspection

Explore schema and local database.

| Command | Description |
|---------|-------------|
| `mp inspect events` | List event names |
| `mp inspect properties` | List properties for an event |
| `mp inspect values` | List values for a property |
| `mp inspect funnels` | List saved funnels |
| `mp inspect cohorts` | List saved cohorts |
| `mp inspect bookmarks` | List saved reports (bookmarks) |
| `mp inspect top-events` | List today's top events |
| `mp inspect info` | Show workspace info |
| `mp inspect tables` | List local tables |
| `mp inspect schema` | Show table schema |
| `mp inspect drop` | Drop a local table |
| `mp inspect drop-all` | Drop all tables (with optional type filter) |
| `mp inspect sample` | Random sample rows from a table |
| `mp inspect summarize` | Statistical summary of all columns |
| `mp inspect breakdown` | Event distribution analysis |
| `mp inspect keys` | Discover JSON property keys |
| `mp inspect column` | Deep column-level statistics |
| `mp inspect distribution` | Property value distribution (JQL) |
| `mp inspect numeric` | Numeric property statistics (JQL) |
| `mp inspect daily` | Daily event counts (JQL) |
| `mp inspect engagement` | User engagement distribution (JQL) |
| `mp inspect coverage` | Property coverage analysis (JQL) |

## Output Formats

All commands support the `--format` option:

| Format | Description | Use Case |
|--------|-------------|----------|
| `json` | Pretty-printed JSON | Default, human-readable |
| `jsonl` | JSON Lines | Streaming, large datasets |
| `table` | Rich formatted table | Terminal viewing |
| `csv` | CSV with headers | Spreadsheet export |
| `plain` | Minimal text | Scripting |

Example:

```bash
# Table output for terminal
mp query sql "SELECT * FROM events LIMIT 10" --format table

# CSV for export
mp query sql "SELECT * FROM events" --format csv > events.csv

# JSONL for streaming processing
mp query sql "SELECT * FROM events" --format jsonl | jq '.event_name'
```

## Exit Codes

| Code | Meaning | Exception |
|------|---------|-----------|
| 0 | Success | — |
| 1 | General error | `MixpanelDataError` |
| 2 | Authentication error | `AuthenticationError` |
| 3 | Invalid arguments | `ConfigError`, validation errors |
| 4 | Resource not found | `TableNotFoundError`, `AccountNotFoundError` |
| 5 | Rate limit exceeded | `RateLimitError` |
| 130 | Interrupted | Ctrl+C |

## Environment Variables

| Variable | Description |
|----------|-------------|
| `MP_USERNAME` | Service account username |
| `MP_SECRET` | Service account secret |
| `MP_PROJECT_ID` | Project ID |
| `MP_REGION` | Data residency region |
| `MP_ACCOUNT` | Account name to use |
| `MP_CONFIG_PATH` | Override config file path |

## Examples

### Complete Workflow

```bash
# 1. Set up credentials (prompts for secret securely)
mp auth add production --username sa_... --project 12345 --region us

# 2. Explore schema
mp inspect events
mp inspect properties --event Purchase

# 3. Fetch data
mp fetch events jan --from 2024-01-01 --to 2024-01-31

# 4. Query locally
mp query sql "SELECT event_name, COUNT(*) FROM jan GROUP BY 1" --format table

# 5. Run live queries
mp query segmentation --event Purchase --from 2024-01-01 --to 2024-01-31 --format table
```

### Incremental Fetching

```bash
# Fetch initial data
mp fetch events events --from 2024-01-01 --to 2024-01-31

# Append more data later
mp fetch events events --from 2024-02-01 --to 2024-02-28 --append

# Resume after a crash (overlapping dates are safe)
mp query sql "SELECT MAX(event_time) FROM events"
mp fetch events events --from 2024-02-15 --to 2024-02-28 --append

# Replace with fresh data
mp fetch events events --from 2024-01-01 --to 2024-02-28 --replace
```

### Piping and Scripting

```bash
# Export to file
mp query sql "SELECT * FROM events" --format csv > events.csv

# Process with jq
mp query segmentation --event Login --from 2024-01-01 --to 2024-01-31 --format json \
    | jq '.values."$overall"'

# Count lines
mp query sql "SELECT * FROM events" --format jsonl | wc -l
```

### Streaming to Stdout

Stream data directly without storing locally:

```bash
# Stream events as JSONL
mp fetch events --from 2024-01-01 --to 2024-01-31 --stdout

# Stream profiles
mp fetch profiles --stdout

# Stream profiles filtered by cohort
mp fetch profiles --stdout --cohort 12345

# Stream specific profile properties only
mp fetch profiles --stdout --output-properties '$email,$name,plan'

# Pipe to jq for filtering
mp fetch events --from 2024-01-01 --to 2024-01-31 --stdout \
    | jq 'select(.event_name == "Purchase")'

# Save to file
mp fetch events --from 2024-01-01 --to 2024-01-31 --stdout > events.jsonl

# Raw Mixpanel API format
mp fetch events --from 2024-01-01 --to 2024-01-31 --stdout --raw
```

## Full Command Reference

See [Commands](commands.md) for the complete auto-generated reference.
