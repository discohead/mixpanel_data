---
description: Interactive wizard to fetch Mixpanel events into local DuckDB with validation
allowed-tools: Bash(mp fetch:*), Bash(mp inspect:*)
argument-hint: [YYYY-MM-DD] [YYYY-MM-DD] [table-name]
---

# Fetch Mixpanel Events

Guide the user through fetching events from Mixpanel into a local DuckDB table.

## Pre-flight Check

First, verify credentials are configured:

```bash
!$(mp auth test 2>&1 || echo "No credentials configured")
```

If credentials aren't configured, suggest running `/mp-auth` first.

## Fetch Parameters

### 1. Date Range

**From date**: `$1` if provided, otherwise ask in YYYY-MM-DD format
**To date**: `$2` if provided, otherwise ask in YYYY-MM-DD format

**Validation**:
- Both dates must be in YYYY-MM-DD format
- From date must be ≤ to date
- **CRITICAL**: Date range must be ≤ 100 days (Mixpanel API limit)
- If range exceeds 100 days, suggest:
  - Breaking into chunks (offer to help with multiple fetches)
  - Using a smaller range for initial exploration

**Calculate range**:
```python
from datetime import datetime
from_date = datetime.strptime("YYYY-MM-DD", "%Y-%m-%d")
to_date = datetime.strptime("YYYY-MM-DD", "%Y-%m-%d")
days = (to_date - from_date).days
if days > 100:
    print(f"⚠️ Range is {days} days (max: 100)")
```

### 2. Table Name

**Table name**: `$3` if provided, otherwise suggest "events" as default

**Check if table exists**:
```bash
!$(mp inspect tables 2>/dev/null | grep -q "^$table_name$" && echo "EXISTS" || echo "NEW")
```

If table exists:
- ⚠️ **Warning**: Table already exists with existing data
- Options:
  - `--append`: Add new data to existing table
  - `--replace`: Replace entire table (destructive!)
  - Choose different table name
- Confirm user's choice before proceeding

### 3. Optional Filters (Advanced)

Ask if the user wants to apply filters:

**Event filter** (optional):
- Specific event names to fetch
- Example: `--events "Purchase" "Sign Up" "Page View"`

**WHERE clause** (optional):
- Mixpanel filter expression
- Example: `--where 'properties["country"] == "US" and properties["amount"] > 100'`
- Refer to query-expressions.md in skill for complete syntax

**Limit** (optional):
- Maximum events to fetch (1-100000)
- Useful for testing or sampling

## Execute Fetch

### Base Command

```bash
mp fetch events <table-name> --from <from-date> --to <to-date>
```

### With Options

Add flags based on user choices:
- `--append` if appending to existing table
- `--events "Event1" "Event2"` if filtering events
- `--where 'expression'` if filtering by properties
- `--limit N` if limiting results

### Example with all options:

```bash
mp fetch events jan_purchases \
  --from 2024-01-01 \
  --to 2024-01-31 \
  --events "Purchase" \
  --where 'properties["amount"] > 100' \
  --append
```

## Post-Fetch Summary

After fetch completes, show:

1. **Fetch results**:
   - Table name
   - Rows fetched
   - Time taken
   - Date range covered

2. **Verification query**:
```bash
mp query sql "SELECT COUNT(*) as total_events, COUNT(DISTINCT distinct_id) as unique_users FROM <table-name>" --format table
```

3. **Next steps**:
   - Run `/mp-inspect` to explore table structure and events
   - Run `/mp-query` to analyze the data
   - Explore events: `mp inspect breakdown -t <table-name>`
   - Check schema: `mp inspect schema -t <table-name>`
   - Sample data: `mp query sql "SELECT * FROM <table-name> LIMIT 10" --format table`

## Common Patterns

**Monthly data**:
```bash
mp fetch events jan --from 2024-01-01 --to 2024-01-31
mp fetch events feb --from 2024-02-01 --to 2024-02-29 --append
```

**Testing/sampling**:
```bash
mp fetch events sample --from 2024-01-01 --to 2024-01-01 --limit 1000
```

**Specific event analysis**:
```bash
mp fetch events purchases --from 2024-01-01 --to 2024-01-31 --events "Purchase"
```

## Error Handling

**DateRangeTooLargeError**: Range > 100 days
- Solution: Break into chunks or reduce range

**TableExistsError**: Table exists without --append
- Solution: Use --append, --replace, or different name

**AuthenticationError**: Credentials invalid
- Solution: Run `/mp-auth` to reconfigure

**RateLimitError**: API rate limited
- Solution: Wait and retry (shows retry_after seconds)

**EventNotFoundError**: Event doesn't exist
- Solution: Check available events with `mp inspect events`
