# CLI Command Reference

Complete reference for the `mp` CLI application.

## Table of Contents
- Global Options
- Authentication Commands (mp auth)
- Fetch Commands (mp fetch)
- Query Commands (mp query)
- Inspect Commands (mp inspect)

## Global Options

| Option | Description |
|--------|-------------|
| `--account, -a` | Account name to use (overrides default) |
| `--quiet, -q` | Suppress progress output |
| `--verbose, -v` | Enable debug output |
| `--format` | Output format: json, jsonl, table, csv, plain |
| `--version` | Show version and exit |

## Filter Expression Syntax

Many commands accept `--where` (filter) and `--on` (segment) parameters using Mixpanel's filter expression syntax.

### ON Parameter
Accepts bare property names (auto-wrapped to `properties["..."]`) or full expressions:
```bash
--on country                         # Bare name (auto-wrapped)
--on 'properties["country"]'         # Full expression (equivalent)
--on '$browser'                      # Special property
```

### WHERE Parameter
Requires full filter expression syntax:
```bash
--where 'properties["country"] == "US"'
--where 'properties["amount"] > 100 and properties["plan"] in ["premium", "enterprise"]'
--where 'defined(properties["email"])'
```

See [query-expressions.md](query-expressions.md) for complete expression syntax reference.

## Authentication Commands (mp auth)

### mp auth list
List all configured accounts.
```bash
mp auth list --format table
```

### mp auth add
Add a new account.
```bash
mp auth add myaccount --username USER --project 123456 --region us
mp auth add myaccount --interactive  # Interactive prompts
mp auth add myaccount --secret-stdin < secret.txt  # Read secret from stdin
```
Options: `--username`, `--project`, `--region`, `--default`, `--interactive`, `--secret-stdin`

### mp auth remove
Remove an account.
```bash
mp auth remove myaccount
mp auth remove myaccount --force  # Skip confirmation
```

### mp auth switch
Set default account.
```bash
mp auth switch myaccount
```

### mp auth show
Show account details (secret redacted).
```bash
mp auth show           # Default account
mp auth show myaccount # Named account
```

### mp auth test
Validate credentials by pinging API.
```bash
mp auth test
mp auth test myaccount
```

## Fetch Commands (mp fetch)

### mp fetch events
Fetch events from Export API.
```bash
mp fetch events --from 2024-01-01 --to 2024-01-31
mp fetch events myevents --from 2024-01-01 --to 2024-01-31  # Custom table name
```

| Option | Description |
|--------|-------------|
| `--from` | Start date (YYYY-MM-DD, required) |
| `--to` | End date (YYYY-MM-DD, required) |
| `--events` | Comma-separated event names to filter |
| `--where` | Filter expression (see syntax above) |
| `--limit` | Max events (1-100000) |
| `--replace` | Replace existing table |
| `--append` | Append to existing table |
| `--stdout` | Stream JSONL to stdout instead of storing |
| `--raw` | Output raw API format (with --stdout) |
| `--batch-size` | Rows per commit (100-100000) |
| `--no-progress` | Disable progress bar |

### mp fetch profiles
Fetch user profiles from Engage API.
```bash
mp fetch profiles
mp fetch profiles myprofiles --cohort 12345
```

| Option | Description |
|--------|-------------|
| `--where` | Filter expression (see syntax above) |
| `--cohort` | Cohort ID to filter |
| `--output-properties` | Comma-separated properties to include |
| `--replace` | Replace existing table |
| `--append` | Append to existing table |
| `--stdout` | Stream JSONL to stdout |
| `--raw` | Output raw API format |
| `--batch-size` | Rows per commit |
| `--no-progress` | Disable progress bar |

## Query Commands (mp query)

### Local Queries

#### mp query sql
Execute SQL against local database.
```bash
mp query sql "SELECT COUNT(*) FROM events"
mp query sql --file query.sql
mp query sql "SELECT COUNT(*) FROM events" --scalar  # Single value
```

### Live Queries

#### mp query segmentation
Time-series event counts.
```bash
mp query segmentation -e Purchase --from 2024-01-01 --to 2024-01-31
mp query segmentation -e Purchase --from 2024-01-01 --to 2024-01-31 --on country
mp query segmentation -e Purchase --from 2024-01-01 --to 2024-01-31 -u week
```

| Option | Description |
|--------|-------------|
| `-e, --event` | Event name (required) |
| `--from` | Start date (required) |
| `--to` | End date (required) |
| `-o, --on` | Property to segment by (bare name or expression) |
| `-u, --unit` | Time unit: day, week, month |
| `-w, --where` | Filter expression |

#### mp query funnel
Funnel conversion analysis.
```bash
mp query funnel 12345 --from 2024-01-01 --to 2024-01-31
mp query funnel 12345 --from 2024-01-01 --to 2024-01-31 --on country
```

| Option | Description |
|--------|-------------|
| `funnel_id` | Saved funnel ID (positional, required) |
| `--from` | Start date (required) |
| `--to` | End date (required) |
| `-u, --unit` | Time unit |
| `-o, --on` | Property to segment by (bare name or expression) |

#### mp query retention
Cohort retention analysis.
```bash
mp query retention --born "Sign Up" --return "Purchase" --from 2024-01-01 --to 2024-01-31
mp query retention -b "Sign Up" -r "Login" --from 2024-01-01 --to 2024-01-31 -u week -n 8
```

| Option | Description |
|--------|-------------|
| `-b, --born` | Birth event (required) |
| `-r, --return` | Return event (required) |
| `--from` | Start date (required) |
| `--to` | End date (required) |
| `--born-where` | Filter for born event |
| `--return-where` | Filter for return event |
| `-u, --unit` | Time unit |
| `-i, --interval` | Interval size |
| `-n, --intervals` | Number of intervals |

#### mp query jql
Execute JQL script.
```bash
mp query jql script.js
mp query jql --script "function main() { return Events(...) }"
mp query jql script.js --param key=value --param other=123
```

| Option | Description |
|--------|-------------|
| `file` | JQL script file (positional) |
| `--script` | Inline JQL script |
| `--param` | Parameter key=value (repeatable) |

#### mp query event-counts
Multi-event time series.
```bash
mp query event-counts -e "Sign Up,Purchase,Login" --from 2024-01-01 --to 2024-01-31
```

| Option | Description |
|--------|-------------|
| `-e, --events` | Comma-separated events (required) |
| `--from` | Start date (required) |
| `--to` | End date (required) |
| `-t, --type` | Count type: general, unique, average |
| `-u, --unit` | Time unit |

#### mp query property-counts
Event breakdown by property.
```bash
mp query property-counts -e Purchase -p country --from 2024-01-01 --to 2024-01-31
```

| Option | Description |
|--------|-------------|
| `-e, --event` | Event name (required) |
| `-p, --property` | Property name (required) |
| `--from` | Start date (required) |
| `--to` | End date (required) |
| `-t, --type` | Count type |
| `-u, --unit` | Time unit |
| `-l, --limit` | Max values (default 10) |

#### mp query activity-feed
User event history.
```bash
mp query activity-feed -U user1,user2,user3
mp query activity-feed -U user1 --from 2024-01-01 --to 2024-01-31
```

| Option | Description |
|--------|-------------|
| `-U, --users` | Comma-separated distinct IDs (required) |
| `--from` | Start date |
| `--to` | End date |

#### mp query saved-report
Execute saved report.
```bash
mp query saved-report 12345
```

#### mp query flows
Execute saved Flows report.
```bash
mp query flows 12345
```

#### mp query frequency
Event frequency distribution.
```bash
mp query frequency --from 2024-01-01 --to 2024-01-31
mp query frequency --from 2024-01-01 --to 2024-01-31 -e Purchase --addiction-unit day
```

| Option | Description |
|--------|-------------|
| `--from` | Start date (required) |
| `--to` | End date (required) |
| `-e, --event` | Event name |
| `-u, --unit` | Time unit |
| `--addiction-unit` | Frequency unit: hour, day |
| `-w, --where` | Filter expression |

#### mp query segmentation-numeric
Bucket events by numeric property.
```bash
mp query segmentation-numeric -e Purchase --on amount --from 2024-01-01 --to 2024-01-31
```

| Option | Description |
|--------|-------------|
| `-e, --event` | Event name (required) |
| `-o, --on` | Numeric property (required) |
| `--from` | Start date (required) |
| `--to` | End date (required) |
| `-t, --type` | Count type |
| `-u, --unit` | Time unit: hour, day |
| `-w, --where` | Filter expression |

#### mp query segmentation-sum
Sum numeric property.
```bash
mp query segmentation-sum -e Purchase --on amount --from 2024-01-01 --to 2024-01-31
```

#### mp query segmentation-average
Average numeric property.
```bash
mp query segmentation-average -e Purchase --on amount --from 2024-01-01 --to 2024-01-31
```

## Inspect Commands (mp inspect)

### Discovery (Live API)

#### mp inspect events
List all tracked events.
```bash
mp inspect events --format table
```

#### mp inspect properties
List properties for an event.
```bash
mp inspect properties -e Purchase
```

#### mp inspect values
Sample property values.
```bash
mp inspect values -p country
mp inspect values -p country -e Purchase --limit 50
```

#### mp inspect funnels
List saved funnels.
```bash
mp inspect funnels --format table
```

#### mp inspect cohorts
List saved cohorts.
```bash
mp inspect cohorts --format table
```

#### mp inspect top-events
Today's trending events.
```bash
mp inspect top-events
mp inspect top-events -t unique -l 20
```

| Option | Description |
|--------|-------------|
| `-t, --type` | Count type: general, unique, average |
| `-l, --limit` | Max events |

#### mp inspect bookmarks
List saved reports.
```bash
mp inspect bookmarks
mp inspect bookmarks -t funnels  # Filter by type
```

| Option | Description |
|--------|-------------|
| `-t, --type` | Filter: insights, funnels, retention, flows, launch-analysis |

#### mp inspect lexicon-schemas
List Lexicon schemas.
```bash
mp inspect lexicon-schemas
mp inspect lexicon-schemas -t event
```

#### mp inspect lexicon-schema
Get single schema.
```bash
mp inspect lexicon-schema -t event -n Purchase
```

### Introspection (Local Database)

#### mp inspect info
Workspace metadata.
```bash
mp inspect info
```

#### mp inspect tables
List local tables.
```bash
mp inspect tables --format table
```

#### mp inspect schema
Table column definitions.
```bash
mp inspect schema -t events
```

#### mp inspect sample
Random sample rows.
```bash
mp inspect sample -t events
mp inspect sample -t events -n 20
```

#### mp inspect summarize
Statistical column summary.
```bash
mp inspect summarize -t events
```

#### mp inspect breakdown
Event distribution.
```bash
mp inspect breakdown -t events
```

#### mp inspect keys
JSON property keys.
```bash
mp inspect keys -t events
mp inspect keys -t events -e Purchase  # Filter by event
```

#### mp inspect column
Deep column analysis.
```bash
mp inspect column -t events -c event_name
mp inspect column -t events -c "properties->>'$.country'" --top 20
```

| Option | Description |
|--------|-------------|
| `-t, --table` | Table name (required) |
| `-c, --column` | Column name or JSON path (required) |
| `--top` | Top N values (default 10) |

#### mp inspect drop
Delete a table.
```bash
mp inspect drop -t events
mp inspect drop -t events --force  # Skip confirmation
```
