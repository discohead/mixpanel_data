# mp CLI Specification

> Version: 0.3.0 (Draft)
> Status: Design Phase
> Last Updated: December 2024

## Overview

`mp` is a command-line interface for working with Mixpanel data. It provides commands for fetching data into a local analytical database, querying with SQL, running live Mixpanel reports, and managing authentication credentials.

The CLI is a thin wrapper around the `mixpanel_data` Python library. Every command maps directly to a library method, ensuring consistent behavior between programmatic and command-line usage.

## Design Principles

**Non-interactive by default**: All commands accept their inputs as arguments and flags. No prompts or interactive menus unless explicitly requested with `--interactive`.

**Structured output**: Output is machine-readable by default (JSON). Human-readable formats (table, plain text) are available via `--format`.

**Composable**: Commands output clean data suitable for piping to other tools (`jq`, `csvkit`, etc.). Progress and status messages go to stderr, data goes to stdout.

**Predictable**: Exit codes follow conventions. Errors include actionable guidance. No silent failures.

**Library parity**: Every CLI command corresponds to a library method. The CLI adds argument parsing and output formatting—nothing more.

---

## Installation

```bash
pip install mixpanel_data
```

This installs both the `mixpanel_data` Python library and the `mp` CLI.

---

## Quick Start

```bash
# Configure authentication
mp auth add production --username sa_xxx --secret xxx --project 12345 --region us
mp auth switch production

# Fetch events
mp fetch events --from 2024-01-01 --to 2024-01-31

# Query with SQL
mp sql "SELECT event_name, COUNT(*) as count FROM events GROUP BY 1"

# Get a quick answer without fetching
mp segmentation --event Purchase --from 2024-01-01 --to 2024-01-31 --on country
```

---

## Global Options

These options can be used with any command (before the command name).

| Option | Short | Description |
|--------|-------|-------------|
| `--account <name>` | `-a` | Use a specific named account instead of the default |
| `--quiet` | `-q` | Suppress progress bars and status messages |
| `--verbose` | `-v` | Show detailed output including API calls |
| `--help` | `-h` | Show help for the command |
| `--version` | | Show version information |

## Per-Command Options

The `--format` option is available on all commands that produce output (after the command name).

| Option | Short | Description |
|--------|-------|-------------|
| `--format <format>` | `-f` | Output format: `json` (default), `table`, `csv`, `jsonl`, `plain` |

### Format Details

| Format | Description | Best For |
|--------|-------------|----------|
| `json` | Pretty-printed JSON object or array | Piping to `jq`, programmatic parsing |
| `jsonl` | One JSON object per line | Streaming, large datasets |
| `table` | Human-readable ASCII table | Terminal viewing |
| `csv` | Comma-separated values with header | Spreadsheets, data tools |

### Examples

```bash
# Use a specific account (global option before command)
mp --account staging fetch events --from 2024-01-01 --to 2024-01-31

# Output as CSV (format option after command)
mp query sql "SELECT * FROM events" --format csv > events.csv

# Quiet mode for scripts (global option before command)
mp --quiet fetch events --from 2024-01-01 --to 2024-01-31

# Verbose mode for debugging
mp --verbose query segmentation --event Purchase --from 2024-01-01 --to 2024-01-31

# Combine global and per-command options
mp --account staging auth list --format table
```

---

## Command Reference

### mp auth

Manage authentication credentials. Credentials are stored in `~/.mp/config.toml`.

#### mp auth list

List all configured accounts.

**Syntax**
```
mp auth list [options]
```

**Options**
| Option | Description |
|--------|-------------|
| `--format <format>` | Output format: `table` (default), `json` |

**Output**

Displays account names, project IDs, regions, and indicates the default account.

**Examples**
```bash
# List accounts in table format
mp auth list

# Output:
#   NAME         PROJECT     REGION  DEFAULT
#   production   12345       us      ✓
#   staging      67890       eu

# List as JSON
mp auth list --format json
```

**Exit Codes**
| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | Config file not found or unreadable |

---

#### mp auth add

Add a new account configuration.

**Syntax**
```
mp auth add <name> [options]
```

**Arguments**
| Argument | Description |
|----------|-------------|
| `name` | Unique name for this account (e.g., "production", "staging") |

**Options**
| Option | Short | Description |
|--------|-------|-------------|
| `--username <username>` | `-u` | Service account username (required unless interactive) |
| `--secret <secret>` | `-s` | Service account secret (required unless interactive) |
| `--project <id>` | `-p` | Mixpanel project ID (required unless interactive) |
| `--region <region>` | `-r` | Data residency region: `us` (default), `eu`, `in` |
| `--default` | `-d` | Set this account as the default |
| `--interactive` | `-i` | Prompt for credentials interactively |

**Examples**
```bash
# Add account with all options
mp auth add production \
  --username sa_abc123 \
  --secret mysecret \
  --project 12345 \
  --region us \
  --default

# Add account interactively (prompts for credentials)
mp auth add staging --interactive

# Add EU account
mp auth add eu-production \
  --username sa_xyz789 \
  --secret anothersecret \
  --project 67890 \
  --region eu
```

**Exit Codes**
| Code | Meaning |
|------|---------|
| 0 | Account added successfully |
| 1 | Account with this name already exists |
| 2 | Missing required options |
| 3 | Invalid region specified |

---

#### mp auth remove

Remove an account configuration.

**Syntax**
```
mp auth remove <name> [options]
```

**Arguments**
| Argument | Description |
|----------|-------------|
| `name` | Name of the account to remove |

**Options**
| Option | Description |
|--------|-------------|
| `--force` | Skip confirmation prompt |

**Examples**
```bash
# Remove account (will prompt for confirmation)
mp auth remove staging

# Remove without confirmation
mp auth remove staging --force
```

**Exit Codes**
| Code | Meaning |
|------|---------|
| 0 | Account removed successfully |
| 1 | Account not found |
| 2 | User cancelled confirmation |

---

#### mp auth switch

Set the default account.

**Syntax**
```
mp auth switch <name>
```

**Arguments**
| Argument | Description |
|----------|-------------|
| `name` | Name of the account to set as default |

**Examples**
```bash
mp auth switch production
```

**Exit Codes**
| Code | Meaning |
|------|---------|
| 0 | Default account updated |
| 1 | Account not found |

---

#### mp auth show

Show details for an account (secret is redacted).

**Syntax**
```
mp auth show <name> [options]
```

**Arguments**
| Argument | Description |
|----------|-------------|
| `name` | Name of the account to show |

**Options**
| Option | Description |
|--------|-------------|
| `--format <format>` | Output format: `table` (default), `json` |

**Examples**
```bash
mp auth show production

# Output:
#   Name:       production
#   Username:   sa_abc123...
#   Secret:     ********
#   Project:    12345
#   Region:     us
#   Default:    yes
```

**Exit Codes**
| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | Account not found |

---

#### mp auth test

Test account credentials by making an API call.

**Syntax**
```
mp auth test [name] [options]
```

**Arguments**
| Argument | Description |
|----------|-------------|
| `name` | Account to test (optional, uses default if omitted) |

**Options**
| Option | Description |
|--------|-------------|
| `--format <format>` | Output format: `table` (default), `json` |

**Examples**
```bash
# Test default account
mp auth test

# Test specific account
mp auth test staging

# Output on success:
#   ✓ Authentication successful
#   Project: My Project (12345)
#   Region: us

# Output on failure:
#   ✗ Authentication failed
#   Error: Invalid credentials
```

**Exit Codes**
| Code | Meaning |
|------|---------|
| 0 | Authentication successful |
| 1 | Authentication failed |
| 2 | Account not found |

---

### mp fetch

Fetch data from Mixpanel into the local database.

#### mp fetch events

Fetch events from Mixpanel and store in a local table.

**Syntax**
```
mp fetch events [name] --from <date> --to <date> [options]
```

**Arguments**
| Argument | Description |
|----------|-------------|
| `name` | Table name to create (default: "events") |

**Options**
| Option | Short | Description |
|--------|-------|-------------|
| `--from <date>` | | Start date, inclusive (required). Format: YYYY-MM-DD |
| `--to <date>` | | End date, inclusive (required). Format: YYYY-MM-DD |
| `--events <list>` | `-e` | Comma-separated list of event names to filter |
| `--where <expr>` | `-w` | Mixpanel filter expression |
| `--no-progress` | | Hide progress bar |

**Examples**
```bash
# Fetch all events for January (creates "events" table)
mp fetch events --from 2024-01-01 --to 2024-01-31

# Fetch to a named table
mp fetch events january --from 2024-01-01 --to 2024-01-31

# Fetch specific events only
mp fetch events --from 2024-01-01 --to 2024-01-31 --events "Purchase,Signup"

# Fetch with a filter
mp fetch events big_purchases \
  --from 2024-01-01 \
  --to 2024-01-31 \
  --events Purchase \
  --where 'properties["amount"] > 1000'
```

**Output**

On success, prints a summary:
```
Fetched 15,234 events to table "events"
Date range: 2024-01-01 to 2024-01-31
Duration: 12.3 seconds
```

With `--format json`:
```json
{
  "table": "events",
  "rows": 15234,
  "from_date": "2024-01-01",
  "to_date": "2024-01-31",
  "duration_seconds": 12.3
}
```

**Exit Codes**
| Code | Meaning |
|------|---------|
| 0 | Fetch successful |
| 1 | Table already exists (use `mp drop` first) |
| 2 | Authentication error |
| 3 | Invalid date format |
| 4 | Invalid filter expression |
| 5 | Rate limit exceeded |

---

#### mp fetch profiles

Fetch user profiles from Mixpanel and store in a local table.

**Syntax**
```
mp fetch profiles [name] [options]
```

**Arguments**
| Argument | Description |
|----------|-------------|
| `name` | Table name to create (default: "profiles") |

**Options**
| Option | Short | Description |
|--------|-------|-------------|
| `--where <expr>` | `-w` | Mixpanel filter expression |
| `--no-progress` | | Hide progress bar |

**Examples**
```bash
# Fetch all profiles
mp fetch profiles

# Fetch to a named table with filter
mp fetch profiles premium_users --where 'user["plan"] == "premium"'
```

**Output**

Same format as `mp fetch events`.

**Exit Codes**

Same as `mp fetch events`.

---

### mp sql

Execute SQL queries against the local database.

**Syntax**
```
mp sql <query> [options]
mp sql --file <path> [options]
```

**Arguments**
| Argument | Description |
|----------|-------------|
| `query` | SQL query string |

**Options**
| Option | Short | Description |
|--------|-------|-------------|
| `--file <path>` | `-F` | Read query from file instead of argument |
| `--format <format>` | `-f` | Output format: `json` (default), `table`, `csv`, `jsonl` |
| `--scalar` | `-s` | Expect a single value result (for COUNT, SUM, etc.) |

**Examples**
```bash
# Simple query
mp sql "SELECT COUNT(*) FROM events"

# Query with table output
mp sql "SELECT event_name, COUNT(*) as count FROM events GROUP BY 1" --format table

# Query from file
mp sql --file analysis.sql

# Scalar result
mp sql --scalar "SELECT COUNT(*) FROM events"
# Output: 15234

# Export to CSV
mp sql "SELECT * FROM events" --format csv > events.csv

# Pipe to jq
mp sql "SELECT * FROM events LIMIT 10" | jq '.[].event_name'
```

**JSON Property Access**

Use DuckDB's JSON operators to query event properties:
```bash
mp sql "SELECT properties->>'$.country' as country, COUNT(*) FROM events GROUP BY 1"
```

**Exit Codes**
| Code | Meaning |
|------|---------|
| 0 | Query successful |
| 1 | SQL syntax error |
| 2 | Table not found |
| 3 | File not found (when using --file) |

---

### mp drop

Remove tables from the local database.

**Syntax**
```
mp drop <table>... [options]
mp drop --all [options]
```

**Arguments**
| Argument | Description |
|----------|-------------|
| `table` | One or more table names to drop |

**Options**
| Option | Description |
|--------|-------------|
| `--all` | Drop all tables |
| `--type <type>` | With `--all`: drop only "events" or "profiles" tables |
| `--force` | Skip confirmation prompt |

**Examples**
```bash
# Drop a single table
mp drop january

# Drop multiple tables
mp drop january february march

# Drop all tables (will prompt for confirmation)
mp drop --all

# Drop all event tables without confirmation
mp drop --all --type events --force
```

**Exit Codes**
| Code | Meaning |
|------|---------|
| 0 | Tables dropped successfully |
| 1 | One or more tables not found |
| 2 | User cancelled confirmation |

---

### mp events

List all event names in the Mixpanel project.

**Syntax**
```
mp events [options]
```

**Options**
| Option | Short | Description |
|--------|-------|-------------|
| `--format <format>` | `-f` | Output format: `json` (default), `table`, `plain` |

**Examples**
```bash
# List events as JSON array
mp events

# List as plain text (one per line)
mp events --format plain

# Count events
mp events --format plain | wc -l
```

**Output**

```json
["Login", "Purchase", "Signup", "View Item"]
```

With `--format plain`:
```
Login
Purchase
Signup
View Item
```

**Exit Codes**
| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | Authentication error |

---

### mp properties

List all properties for a specific event.

**Syntax**
```
mp properties <event> [options]
```

**Arguments**
| Argument | Description |
|----------|-------------|
| `event` | Event name |

**Options**
| Option | Short | Description |
|--------|-------|-------------|
| `--format <format>` | `-f` | Output format: `json` (default), `table`, `plain` |

**Examples**
```bash
mp properties Purchase

# Output:
# ["amount", "country", "currency", "product_id", "quantity"]
```

**Exit Codes**
| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | Authentication error |
| 2 | Event not found |

---

### mp values

List sample values for a property on an event.

**Syntax**
```
mp values <event> <property> [options]
```

**Arguments**
| Argument | Description |
|----------|-------------|
| `event` | Event name |
| `property` | Property name |

**Options**
| Option | Short | Description |
|--------|-------|-------------|
| `--limit <n>` | `-l` | Maximum values to return (default: 100) |
| `--format <format>` | `-f` | Output format: `json` (default), `table`, `plain` |

**Examples**
```bash
mp values Purchase country

# Output:
# ["US", "CA", "UK", "DE", "FR", "AU"]

mp values Purchase country --limit 3
# Output:
# ["US", "CA", "UK"]
```

**Exit Codes**
| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | Authentication error |
| 2 | Event not found |
| 3 | Property not found |

---

### mp funnels

List all saved funnel definitions in the Mixpanel project.

**Syntax**
```
mp funnels [options]
```

**Options**
| Option | Short | Description |
|--------|-------|-------------|
| `--format <format>` | `-f` | Output format: `json` (default), `table`, `plain` |

**Examples**
```bash
# List funnels as JSON
mp funnels

# Output:
# [
#   {"funnel_id": 123, "name": "Signup to Purchase"},
#   {"funnel_id": 456, "name": "Onboarding Flow"}
# ]

# List as table
mp funnels --format table

# Output:
#   ID      NAME
#   123     Signup to Purchase
#   456     Onboarding Flow

# List as plain (ID: Name per line)
mp funnels --format plain
# 123: Signup to Purchase
# 456: Onboarding Flow
```

**Notes**

Use this command to discover funnel IDs before running `mp funnel <id>`. Results are cached for the session.

**Exit Codes**
| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | Authentication error |

---

### mp cohorts

List all saved cohort definitions in the Mixpanel project.

**Syntax**
```
mp cohorts [options]
```

**Options**
| Option | Short | Description |
|--------|-------|-------------|
| `--format <format>` | `-f` | Output format: `json` (default), `table`, `plain` |

**Examples**
```bash
# List cohorts as JSON
mp cohorts

# Output:
# [
#   {"id": 789, "name": "Power Users", "count": 1234, "description": "...", ...},
#   {"id": 101, "name": "Churned Users", "count": 567, "description": "...", ...}
# ]

# List as table
mp cohorts --format table

# Output:
#   ID      NAME              COUNT     DESCRIPTION
#   789     Power Users       1234      Users with 10+ purchases
#   101     Churned Users     567       No activity in 30 days

# List as plain
mp cohorts --format plain
# 789: Power Users (1234 users)
# 101: Churned Users (567 users)
```

**Notes**

Cohorts can be used as filters in other queries. Results are cached for the session.

**Exit Codes**
| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | Authentication error |

---

### mp top-events

Get the top events in the Mixpanel project by volume.

**Syntax**
```
mp top-events [options]
```

**Options**
| Option | Short | Description |
|--------|-------|-------------|
| `--type <type>` | `-t` | Count type: `general` (default), `average`, `unique` |
| `--limit <n>` | `-l` | Maximum number of events to return |
| `--format <format>` | `-f` | Output format: `json` (default), `table`, `plain` |

**Type Options**
| Type | Description |
|------|-------------|
| `general` | Total event count (default) |
| `average` | Average events per user |
| `unique` | Unique users who triggered the event |

**Examples**
```bash
# Get top events
mp top-events

# Output:
# [
#   {"event": "Page View", "count": 50000, "percent_change": 12.3},
#   {"event": "Button Click", "count": 25000, "percent_change": -5.2},
#   ...
# ]

# Top 5 by unique users
mp top-events --type unique --limit 5

# Table format
mp top-events --format table --limit 10

# Output:
#   EVENT             COUNT       CHANGE
#   Page View         50,000      +12.3%
#   Button Click      25,000      -5.2%
#   Login             15,000      +8.1%
```

**Notes**

Unlike `mp events` which lists all event names from the schema, `mp top-events` returns real-time usage data ranked by volume. Results are NOT cached because they represent current activity.

**Exit Codes**
| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | Authentication error |

---

### mp info

Show workspace information.

**Syntax**
```
mp info [options]
```

**Options**
| Option | Short | Description |
|--------|-------|-------------|
| `--format <format>` | `-f` | Output format: `table` (default), `json` |

**Examples**
```bash
mp info

# Output:
#   Workspace
#   ─────────────────────────────
#   Path:       ~/.mixpanel_data/12345.db
#   Account:    production
#   Project:    12345
#   Region:     us
#   Size:       12.4 MB
#   Tables:     3
```

**Exit Codes**
| Code | Meaning |
|------|---------|
| 0 | Success |

---

### mp tables

List all tables in the local database.

**Syntax**
```
mp tables [options]
```

**Options**
| Option | Short | Description |
|--------|-------|-------------|
| `--format <format>` | `-f` | Output format: `table` (default), `json` |

**Examples**
```bash
mp tables

# Output:
#   NAME              TYPE      ROWS      DATE RANGE                 FETCHED
#   events            events    15234     2024-01-01 to 2024-01-31   2024-12-19 10:30
#   january           events    12000     2024-01-01 to 2024-01-31   2024-12-19 09:15
#   premium_users     profiles  892       —                          2024-12-19 10:45
```

**Exit Codes**
| Code | Meaning |
|------|---------|
| 0 | Success |

---

### mp schema

Show schema information for a table.

**Syntax**
```
mp schema <table> [options]
```

**Arguments**
| Argument | Description |
|----------|-------------|
| `table` | Table name |

**Options**
| Option | Short | Description |
|--------|-------|-------------|
| `--format <format>` | `-f` | Output format: `table` (default), `json` |
| `--sample` | `-s` | Include sample property values |

**Examples**
```bash
mp schema events

# Output:
#   Column        Type        Nullable
#   ──────────────────────────────────
#   event_name    VARCHAR     no
#   event_time    TIMESTAMP   no
#   distinct_id   VARCHAR     no
#   insert_id     VARCHAR     yes
#   properties    JSON        yes
#
#   Rows: 15,234

mp schema events --sample

# Also shows:
#   Sample Properties:
#     amount: 99.99, 149.00, 29.99, ...
#     country: "US", "CA", "UK", ...
#     product_id: "SKU-001", "SKU-002", ...
```

**Exit Codes**
| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | Table not found |

---

### mp segmentation

Run a segmentation query against Mixpanel (live query, no local storage).

**Syntax**
```
mp segmentation --event <event> --from <date> --to <date> [options]
```

**Options**
| Option | Short | Description |
|--------|-------|-------------|
| `--event <event>` | `-e` | Event name to analyze (required) |
| `--from <date>` | | Start date, inclusive (required). Format: YYYY-MM-DD |
| `--to <date>` | | End date, inclusive (required). Format: YYYY-MM-DD |
| `--on <property>` | `-o` | Property to segment by (e.g., "properties.country") |
| `--unit <unit>` | `-u` | Time unit: `minute`, `hour`, `day` (default), `week`, `month` |
| `--where <expr>` | `-w` | Filter expression |
| `--format <format>` | `-f` | Output format: `json` (default), `table`, `csv` |

**Examples**
```bash
# Basic segmentation
mp segmentation --event Purchase --from 2024-01-01 --to 2024-01-31

# Segment by country
mp segmentation \
  --event Purchase \
  --from 2024-01-01 \
  --to 2024-01-31 \
  --on properties.country

# Weekly aggregation with filter
mp segmentation \
  --event Purchase \
  --from 2024-01-01 \
  --to 2024-03-31 \
  --unit week \
  --where 'properties["amount"] > 100'
```

**Output**

```json
{
  "event": "Purchase",
  "from_date": "2024-01-01",
  "to_date": "2024-01-31",
  "unit": "day",
  "total": 15234,
  "data": {
    "2024-01-01": {"US": 100, "CA": 50, "UK": 30},
    "2024-01-02": {"US": 120, "CA": 45, "UK": 35}
  }
}
```

**Exit Codes**
| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | Authentication error |
| 2 | Invalid date format |
| 3 | Event not found |
| 4 | Invalid filter expression |

---

### mp funnel

Run a funnel analysis using a saved funnel definition.

**Syntax**
```
mp funnel <funnel_id> --from <date> --to <date> [options]
```

**Arguments**
| Argument | Description |
|----------|-------------|
| `funnel_id` | ID of the saved funnel in Mixpanel |

**Options**
| Option | Short | Description |
|--------|-------|-------------|
| `--from <date>` | | Start date, inclusive (required). Format: YYYY-MM-DD |
| `--to <date>` | | End date, inclusive (required). Format: YYYY-MM-DD |
| `--unit <unit>` | `-u` | Time unit: `day` (default), `week`, `month` |
| `--on <property>` | `-o` | Property to segment by |
| `--format <format>` | `-f` | Output format: `json` (default), `table`, `csv` |

**Examples**
```bash
# Basic funnel analysis
mp funnel 123 --from 2024-01-01 --to 2024-01-31

# Segment by country
mp funnel 123 --from 2024-01-01 --to 2024-01-31 --on properties.country

# Table output
mp funnel 123 --from 2024-01-01 --to 2024-01-31 --format table

# Output:
#   Step              Count     Conversion    Overall
#   ─────────────────────────────────────────────────
#   View Product      10000     100.0%        100.0%
#   Add to Cart       6500      65.0%         65.0%
#   Checkout          3200      49.2%         32.0%
#   Purchase          2800      87.5%         28.0%
```

**Exit Codes**
| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | Authentication error |
| 2 | Funnel not found |
| 3 | Invalid date format |

---

### mp retention

Run a retention analysis.

**Syntax**
```
mp retention --born <event> --return <event> --from <date> --to <date> [options]
```

**Options**
| Option | Short | Description |
|--------|-------|-------------|
| `--born <event>` | `-b` | Event that defines the cohort (required) |
| `--return <event>` | `-r` | Event that defines retention (required) |
| `--from <date>` | | Start date for cohort birth (required). Format: YYYY-MM-DD |
| `--to <date>` | | End date for cohort birth (required). Format: YYYY-MM-DD |
| `--born-where <expr>` | | Filter for birth event |
| `--return-where <expr>` | | Filter for return event |
| `--interval <n>` | `-i` | Size of each retention bucket (default: 1) |
| `--intervals <n>` | `-n` | Number of retention buckets (default: 10) |
| `--unit <unit>` | `-u` | Time unit: `day` (default), `week`, `month` |
| `--format <format>` | `-f` | Output format: `json` (default), `table`, `csv` |

**Examples**
```bash
# Basic retention: users who signed up and then purchased
mp retention \
  --born Signup \
  --return Purchase \
  --from 2024-01-01 \
  --to 2024-01-31

# Weekly retention over 12 weeks
mp retention \
  --born Signup \
  --return Login \
  --from 2024-01-01 \
  --to 2024-03-31 \
  --unit week \
  --intervals 12

# With filters
mp retention \
  --born Signup \
  --return Purchase \
  --from 2024-01-01 \
  --to 2024-01-31 \
  --born-where 'properties["source"] == "organic"' \
  --return-where 'properties["amount"] > 50'
```

**Output (table format)**

```
Cohort        Size    Day 0   Day 1   Day 2   Day 3   Day 7   Day 14
────────────────────────────────────────────────────────────────────
2024-01-01    500     100%    45%     38%     35%     28%     22%
2024-01-08    480     100%    48%     40%     36%     30%     24%
2024-01-15    520     100%    44%     37%     34%     27%     21%
```

**Exit Codes**
| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | Authentication error |
| 2 | Invalid date format |
| 3 | Event not found |
| 4 | Invalid filter expression |

---

### mp jql

Execute a JQL (JavaScript Query Language) query.

**Syntax**
```
mp jql <file> [options]
mp jql --code <script> [options]
```

**Arguments**
| Argument | Description |
|----------|-------------|
| `file` | Path to JQL script file |

**Options**
| Option | Short | Description |
|--------|-------|-------------|
| `--code <script>` | `-c` | Execute inline JQL script instead of file |
| `--param <key=value>` | `-P` | Set a parameter (can be repeated) |
| `--format <format>` | `-f` | Output format: `json` (default), `table`, `csv` |

**Examples**
```bash
# Run JQL from file
mp jql analysis.js

# Run with parameters
mp jql analysis.js --param from_date=2024-01-01 --param to_date=2024-01-31

# Inline JQL
mp jql --code 'function main() {
  return Events({from_date: "2024-01-01", to_date: "2024-01-31"})
    .groupBy(["properties.country"], mixpanel.reducer.count())
}'
```

**JQL File Example**

```javascript
// analysis.js
function main() {
  return Events({
    from_date: params.from_date,
    to_date: params.to_date
  })
  .filter(function(e) {
    return e.name === "Purchase";
  })
  .groupBy(["properties.country"], mixpanel.reducer.count());
}
```

**Exit Codes**
| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | Authentication error |
| 2 | File not found |
| 3 | JQL syntax error |
| 4 | JQL execution error |

---

### mp event-counts

Get time-series counts for multiple events in a single query.

**Syntax**
```
mp event-counts --events <list> --from <date> --to <date> [options]
```

**Options**
| Option | Short | Description |
|--------|-------|-------------|
| `--events <list>` | `-e` | Comma-separated event names (required) |
| `--from <date>` | | Start date, inclusive (required). Format: YYYY-MM-DD |
| `--to <date>` | | End date, inclusive (required). Format: YYYY-MM-DD |
| `--unit <unit>` | `-u` | Time unit: `minute`, `hour`, `day` (default), `week`, `month` |
| `--type <type>` | `-t` | Count type: `general` (default), `average`, `unique` |
| `--where <expr>` | `-w` | Filter expression |
| `--format <format>` | `-f` | Output format: `json` (default), `table`, `csv` |

**Type Options**
| Type | Description |
|------|-------------|
| `general` | Total event count (default) |
| `average` | Average events per user |
| `unique` | Unique users who triggered the event |

**Examples**
```bash
# Compare multiple events over time
mp event-counts \
  --events "Login,Purchase,Logout" \
  --from 2024-01-01 \
  --to 2024-01-31

# Output:
# {
#   "events": ["Login", "Purchase", "Logout"],
#   "from_date": "2024-01-01",
#   "to_date": "2024-01-31",
#   "unit": "day",
#   "type": "general",
#   "series": {
#     "Login": {"2024-01-01": 500, "2024-01-02": 520, ...},
#     "Purchase": {"2024-01-01": 150, "2024-01-02": 165, ...},
#     "Logout": {"2024-01-01": 480, "2024-01-02": 510, ...}
#   }
# }

# Weekly counts by unique users
mp event-counts \
  --events "Signup,Purchase" \
  --from 2024-01-01 \
  --to 2024-03-31 \
  --unit week \
  --type unique

# Table format
mp event-counts \
  --events "Login,Purchase" \
  --from 2024-01-01 \
  --to 2024-01-07 \
  --format table

# Output:
#   DATE          LOGIN     PURCHASE
#   2024-01-01    500       150
#   2024-01-02    520       165
#   2024-01-03    510       155
#   ...
```

**Notes**

This is more efficient than running multiple `mp segmentation` commands when you need to compare trends across several events.

**Exit Codes**
| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | Authentication error |
| 2 | Invalid date format |
| 3 | Event not found |
| 4 | Invalid filter expression |

---

### mp property-counts

Get time-series counts for an event, broken down by property values.

**Syntax**
```
mp property-counts --event <event> --property <name> --from <date> --to <date> [options]
```

**Options**
| Option | Short | Description |
|--------|-------|-------------|
| `--event <event>` | `-e` | Event name to analyze (required) |
| `--property <name>` | `-p` | Property to segment by (required) |
| `--from <date>` | | Start date, inclusive (required). Format: YYYY-MM-DD |
| `--to <date>` | | End date, inclusive (required). Format: YYYY-MM-DD |
| `--unit <unit>` | `-u` | Time unit: `minute`, `hour`, `day` (default), `week`, `month` |
| `--type <type>` | `-t` | Count type: `general` (default), `average`, `unique` |
| `--where <expr>` | `-w` | Filter expression |
| `--limit <n>` | `-l` | Maximum property values to return (default: 10) |
| `--format <format>` | `-f` | Output format: `json` (default), `table`, `csv` |

**Examples**
```bash
# Purchases by country over time
mp property-counts \
  --event Purchase \
  --property country \
  --from 2024-01-01 \
  --to 2024-01-31

# Output:
# {
#   "event": "Purchase",
#   "property_name": "country",
#   "from_date": "2024-01-01",
#   "to_date": "2024-01-31",
#   "unit": "day",
#   "type": "general",
#   "series": {
#     "US": {"2024-01-01": 100, "2024-01-02": 110, ...},
#     "CA": {"2024-01-01": 50, "2024-01-02": 45, ...},
#     "UK": {"2024-01-01": 30, "2024-01-02": 35, ...}
#   }
# }

# Top 5 plans by unique users, weekly
mp property-counts \
  --event Subscription \
  --property plan \
  --from 2024-01-01 \
  --to 2024-03-31 \
  --unit week \
  --type unique \
  --limit 5

# Table format
mp property-counts \
  --event Purchase \
  --property country \
  --from 2024-01-01 \
  --to 2024-01-07 \
  --format table

# Output:
#   DATE          US        CA        UK        DE        FR
#   2024-01-01    100       50        30        25        20
#   2024-01-02    110       45        35        28        22
#   2024-01-03    105       48        32        24        19
#   ...
```

**Notes**

Similar to `mp segmentation --on <property>`, but returns data in a format optimized for multi-value time-series analysis.

**Exit Codes**
| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | Authentication error |
| 2 | Invalid date format |
| 3 | Event not found |
| 4 | Property not found |
| 5 | Invalid filter expression |

---

### mp activity-feed

Get the activity feed (event history) for specific users.

**Syntax**
```
mp activity-feed --users <list> [options]
```

**Options**
| Option | Short | Description |
|--------|-------|-------------|
| `--users <list>` | `-u` | Comma-separated distinct_ids (required) |
| `--from <date>` | | Start date (optional). Format: YYYY-MM-DD |
| `--to <date>` | | End date (optional). Format: YYYY-MM-DD |
| `--format <format>` | `-f` | Output format: `json` (default), `table`, `csv` |

**Examples**
```bash
# Get activity for a single user
mp activity-feed --users user_123

# Get activity for multiple users with date range
mp activity-feed \
  --users "user_123,user_456" \
  --from 2024-01-01 \
  --to 2024-01-31

# Output:
# {
#   "distinct_ids": ["user_123", "user_456"],
#   "from_date": "2024-01-01",
#   "to_date": "2024-01-31",
#   "events": [
#     {"event": "Login", "time": "2024-01-15T10:30:00Z", "distinct_id": "user_123", ...},
#     {"event": "Purchase", "time": "2024-01-15T10:35:00Z", "distinct_id": "user_123", ...}
#   ]
# }

# Table format
mp activity-feed --users user_123 --format table

# Output:
#   TIME                  EVENT         DISTINCT_ID
#   2024-01-15 10:30:00   Login         user_123
#   2024-01-15 10:35:00   Purchase      user_123
```

**Notes**

Use this command to view a user's complete activity history, debug user-specific issues, or build user timelines for customer success.

**Exit Codes**
| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | Authentication error |
| 2 | Invalid date format |

---

### mp insights

Query a saved Insights report by bookmark ID.

**Syntax**
```
mp insights <bookmark_id> [options]
```

**Arguments**
| Argument | Description |
|----------|-------------|
| `bookmark_id` | ID of the saved Insights report (from Mixpanel URL) |

**Options**
| Option | Short | Description |
|--------|-------|-------------|
| `--format <format>` | `-f` | Output format: `json` (default), `table`, `csv` |

**Examples**
```bash
# Query a saved Insights report
mp insights 12345

# Output:
# {
#   "bookmark_id": 12345,
#   "computed_at": "2024-01-15T12:00:00Z",
#   "from_date": "2024-01-01",
#   "to_date": "2024-01-14",
#   "headers": ["$event"],
#   "series": {
#     "Login": {"2024-01-01": 500, "2024-01-02": 520, ...},
#     "Purchase": {"2024-01-01": 150, "2024-01-02": 165, ...}
#   }
# }

# Table format
mp insights 12345 --format table
```

**Notes**

Use this command to access pre-configured team reports programmatically. The bookmark ID can be found in the URL of a saved Insights report in the Mixpanel UI.

**Exit Codes**
| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | Authentication error |
| 2 | Bookmark not found |

---

### mp frequency

Analyze how frequently users perform an event within a time period.

**Syntax**
```
mp frequency --from <date> --to <date> [options]
```

**Options**
| Option | Short | Description |
|--------|-------|-------------|
| `--from <date>` | | Start date, inclusive (required). Format: YYYY-MM-DD |
| `--to <date>` | | End date, inclusive (required). Format: YYYY-MM-DD |
| `--unit <unit>` | `-u` | Overall period: `day` (default), `week`, `month` |
| `--addiction-unit <unit>` | `-a` | Granularity: `hour` (default), `day` |
| `--event <event>` | `-e` | Event name to analyze (optional) |
| `--where <expr>` | `-w` | Filter expression (optional) |
| `--format <format>` | `-f` | Output format: `json` (default), `table`, `csv` |

**Examples**
```bash
# Analyze daily event frequency by hour
mp frequency \
  --from 2024-01-01 \
  --to 2024-01-07 \
  --unit day \
  --addiction-unit hour

# Output:
# {
#   "event": null,
#   "from_date": "2024-01-01",
#   "to_date": "2024-01-07",
#   "unit": "day",
#   "addiction_unit": "hour",
#   "data": {
#     "2024-01-01": [305, 107, 60, 41, 32, 20, 12, 7, 4, 3, ...],
#     "2024-01-02": [495, 204, 117, 77, 53, 36, 26, 20, 12, 7, ...]
#   }
# }

# Frequency for specific event
mp frequency \
  --from 2024-01-01 \
  --to 2024-01-31 \
  --event Purchase \
  --unit week \
  --addiction-unit day
```

**Interpretation**

Each date maps to an array of user counts:
- Index N shows users who performed the event in at least N+1 time periods
- Example: On 2024-01-01, 305 users did the event in at least 1 hour, 107 users did it in at least 2 hours

**Use Cases**
- Measure user engagement depth
- Identify power users vs casual users
- Understand usage patterns (daily active vs occasional)

**Exit Codes**
| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | Authentication error |
| 2 | Invalid date format |
| 3 | Invalid unit specified |
| 4 | Invalid filter expression |

---

### mp segmentation-numeric

Segment events by a numeric property, automatically placing values into ranges/buckets.

**Syntax**
```
mp segmentation-numeric --event <event> --on <property> --from <date> --to <date> [options]
```

**Options**
| Option | Short | Description |
|--------|-------|-------------|
| `--event <event>` | `-e` | Event name to analyze (required) |
| `--on <property>` | `-o` | Numeric property expression to bucket (required) |
| `--from <date>` | | Start date, inclusive (required). Format: YYYY-MM-DD |
| `--to <date>` | | End date, inclusive (required). Format: YYYY-MM-DD |
| `--unit <unit>` | `-u` | Time unit: `hour`, `day` (default) |
| `--type <type>` | `-t` | Count type: `general` (default), `unique`, `average` |
| `--where <expr>` | `-w` | Filter expression (optional) |
| `--format <format>` | `-f` | Output format: `json` (default), `table`, `csv` |

**Examples**
```bash
# Bucket purchases by amount
mp segmentation-numeric \
  --event Purchase \
  --on 'properties["amount"]' \
  --from 2024-01-01 \
  --to 2024-01-31

# Output:
# {
#   "event": "Purchase",
#   "from_date": "2024-01-01",
#   "to_date": "2024-01-31",
#   "property_expr": "properties[\"amount\"]",
#   "unit": "day",
#   "series": {
#     "0 - 50": {"2024-01-01": 100, "2024-01-02": 110, ...},
#     "50 - 100": {"2024-01-01": 75, "2024-01-02": 80, ...},
#     "100 - 200": {"2024-01-01": 45, "2024-01-02": 50, ...}
#   }
# }

# Bucket by session duration
mp segmentation-numeric \
  --event "Session End" \
  --on 'properties["duration_seconds"]' \
  --from 2024-01-01 \
  --to 2024-01-07 \
  --type unique
```

**Use Cases**
- Analyze purchase amount distributions
- Segment users by session duration ranges
- Understand numeric property distributions

**Exit Codes**
| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | Authentication error |
| 2 | Invalid date format |
| 3 | Event not found |
| 4 | Invalid property expression |
| 5 | Invalid filter expression |

---

### mp segmentation-sum

Sum a numeric property's values for events per time unit.

**Syntax**
```
mp segmentation-sum --event <event> --on <property> --from <date> --to <date> [options]
```

**Options**
| Option | Short | Description |
|--------|-------|-------------|
| `--event <event>` | `-e` | Event name to analyze (required) |
| `--on <property>` | `-o` | Numeric expression to sum (required) |
| `--from <date>` | | Start date, inclusive (required). Format: YYYY-MM-DD |
| `--to <date>` | | End date, inclusive (required). Format: YYYY-MM-DD |
| `--unit <unit>` | `-u` | Time unit: `hour`, `day` (default) |
| `--where <expr>` | `-w` | Filter expression (optional) |
| `--format <format>` | `-f` | Output format: `json` (default), `table`, `csv` |

**Examples**
```bash
# Calculate daily revenue totals
mp segmentation-sum \
  --event Purchase \
  --on 'properties["amount"]' \
  --from 2024-01-01 \
  --to 2024-01-31

# Output:
# {
#   "event": "Purchase",
#   "from_date": "2024-01-01",
#   "to_date": "2024-01-31",
#   "property_expr": "properties[\"amount\"]",
#   "unit": "day",
#   "results": {
#     "2024-01-01": 15234.50,
#     "2024-01-02": 18456.75,
#     "2024-01-03": 12890.25,
#     ...
#   },
#   "computed_at": "2024-01-31T12:00:00Z"
# }

# Sum items purchased per day
mp segmentation-sum \
  --event Purchase \
  --on 'properties["quantity"]' \
  --from 2024-01-01 \
  --to 2024-01-07

# Table format
mp segmentation-sum \
  --event Purchase \
  --on 'properties["amount"]' \
  --from 2024-01-01 \
  --to 2024-01-07 \
  --format table

# Output:
#   DATE          SUM
#   2024-01-01    15,234.50
#   2024-01-02    18,456.75
#   2024-01-03    12,890.25
```

**Use Cases**
- Calculate daily revenue totals
- Sum items purchased per day
- Aggregate numeric metrics over time

**Exit Codes**
| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | Authentication error |
| 2 | Invalid date format |
| 3 | Event not found |
| 4 | Invalid property expression |
| 5 | Invalid filter expression |

---

### mp segmentation-average

Average a numeric property's values for events per time unit.

**Syntax**
```
mp segmentation-average --event <event> --on <property> --from <date> --to <date> [options]
```

**Options**
| Option | Short | Description |
|--------|-------|-------------|
| `--event <event>` | `-e` | Event name to analyze (required) |
| `--on <property>` | `-o` | Numeric expression to average (required) |
| `--from <date>` | | Start date, inclusive (required). Format: YYYY-MM-DD |
| `--to <date>` | | End date, inclusive (required). Format: YYYY-MM-DD |
| `--unit <unit>` | `-u` | Time unit: `hour`, `day` (default) |
| `--where <expr>` | `-w` | Filter expression (optional) |
| `--format <format>` | `-f` | Output format: `json` (default), `table`, `csv` |

**Examples**
```bash
# Calculate average order value per day
mp segmentation-average \
  --event Purchase \
  --on 'properties["amount"]' \
  --from 2024-01-01 \
  --to 2024-01-31

# Output:
# {
#   "event": "Purchase",
#   "from_date": "2024-01-01",
#   "to_date": "2024-01-31",
#   "property_expr": "properties[\"amount\"]",
#   "unit": "day",
#   "results": {
#     "2024-01-01": 85.45,
#     "2024-01-02": 92.30,
#     "2024-01-03": 78.15,
#     ...
#   }
# }

# Track average session duration trends
mp segmentation-average \
  --event "Session End" \
  --on 'properties["duration_seconds"]' \
  --from 2024-01-01 \
  --to 2024-01-07

# Table format
mp segmentation-average \
  --event Purchase \
  --on 'properties["amount"]' \
  --from 2024-01-01 \
  --to 2024-01-07 \
  --format table

# Output:
#   DATE          AVERAGE
#   2024-01-01    85.45
#   2024-01-02    92.30
#   2024-01-03    78.15
```

**Use Cases**
- Calculate average order value per day
- Track average session duration trends
- Analyze average engagement metrics

**Exit Codes**
| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | Authentication error |
| 2 | Invalid date format |
| 3 | Event not found |
| 4 | Invalid property expression |
| 5 | Invalid filter expression |

---

## Environment Variables

The CLI respects these environment variables, which take precedence over the config file.

| Variable | Description |
|----------|-------------|
| `MP_USERNAME` | Service account username |
| `MP_SECRET` | Service account secret |
| `MP_PROJECT_ID` | Project ID |
| `MP_REGION` | Data residency region (`us`, `eu`, `in`) |
| `MP_CONFIG_PATH` | Override config file location (default: `~/.mp/config.toml`) |
| `MP_DATA_DIR` | Override database directory (default: `~/.mixpanel_data/`) |
| `MP_FORMAT` | Default output format |
| `NO_COLOR` | Disable colored output when set |

**Examples**
```bash
# Use environment variables for CI/CD
export MP_USERNAME="sa_abc123"
export MP_SECRET="mysecret"
export MP_PROJECT_ID="12345"
export MP_REGION="us"

mp fetch events --from 2024-01-01 --to 2024-01-31
```

---

## Configuration

### Config File Location

The default config file is `~/.mp/config.toml`. Override with `MP_CONFIG_PATH` environment variable or `--config` global flag.

### Config File Format

```toml
# ~/.mp/config.toml

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

### Database Location

Local databases are stored in `~/.mixpanel_data/` by default, with one database file per project ID (e.g., `~/.mixpanel_data/12345.db`).

Override with `MP_DATA_DIR` environment variable.

---

## Exit Codes

The CLI uses consistent exit codes across all commands.

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | General error (see error message) |
| 2 | Authentication error |
| 3 | Invalid arguments or options |
| 4 | Resource not found (table, event, file, etc.) |
| 5 | Rate limit exceeded |
| 130 | Interrupted (Ctrl+C) |

---

## Output Conventions

### stdout vs stderr

Data output goes to stdout. Progress bars, status messages, and errors go to stderr.

This allows piping data while still seeing progress:
```bash
mp sql "SELECT * FROM events" > events.json
# Progress and status messages still visible
```

### JSON Output

JSON output is pretty-printed by default. For compact JSON (e.g., for piping), use `jq -c`:
```bash
mp events | jq -c
```

### Color Output

The CLI uses colored output when connected to a terminal. Disable with:
- `--no-color` flag
- `NO_COLOR=1` environment variable
- Piping to another command (automatically detected)

---

## Shell Completion

Generate shell completion scripts:

```bash
# Bash
mp --completion bash > ~/.local/share/bash-completion/completions/mp

# Zsh
mp --completion zsh > ~/.zfunc/_mp

# Fish
mp --completion fish > ~/.config/fish/completions/mp.fish
```

---

## Examples

### Daily Workflow

```bash
# Morning: fetch latest data
mp fetch events --from $(date -d "7 days ago" +%Y-%m-%d) --to $(date +%Y-%m-%d)

# Quick check
mp sql "SELECT event_name, COUNT(*) FROM events GROUP BY 1 ORDER BY 2 DESC LIMIT 10"

# Export for reporting
mp sql "SELECT * FROM events WHERE event_name = 'Purchase'" --format csv > purchases.csv
```

### Comparative Analysis

```bash
# Fetch two periods
mp fetch events q3 --from 2024-07-01 --to 2024-09-30
mp fetch events q4 --from 2024-10-01 --to 2024-12-31

# Compare
mp sql "
  SELECT 'Q3' as quarter, COUNT(*) as events, COUNT(DISTINCT distinct_id) as users FROM q3
  UNION ALL
  SELECT 'Q4', COUNT(*), COUNT(DISTINCT distinct_id) FROM q4
" --format table
```

### Scripting

```bash
#!/bin/bash
set -e

# Fetch if not already present
if ! mp tables --format json | jq -e '.[] | select(.name == "events")' > /dev/null 2>&1; then
  mp fetch events --from 2024-01-01 --to 2024-01-31
fi

# Run analysis
TOTAL=$(mp sql --scalar "SELECT COUNT(*) FROM events")
echo "Total events: $TOTAL"
```

### Integration with jq

```bash
# Get top countries
mp sql "
  SELECT properties->>'$.country' as country, COUNT(*) as count 
  FROM events 
  GROUP BY 1 
  ORDER BY 2 DESC
" | jq '.[0:5] | .[] | "\(.country): \(.count)"'
```

---

## Version History

| Version | Date | Notes |
|---------|------|-------|
| 0.1.0 | December 2024 | Initial CLI specification |
| 0.2.0 | December 2024 | Discovery enhancements: funnels, cohorts, top-events; event-counts, property-counts |
| 0.3.0 | December 2024 | Query service enhancements: activity-feed, insights, frequency, segmentation-numeric, segmentation-sum, segmentation-average |

---

*This specification defines the command-line interface for the `mp` tool. The CLI is a thin wrapper around the `mixpanel_data` Python library.*
