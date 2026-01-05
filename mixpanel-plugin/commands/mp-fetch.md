---
description: Interactive wizard to fetch Mixpanel events into local DuckDB with validation
allowed-tools: Bash(mp fetch:*), Bash(mp inspect:*)
argument-hint: [YYYY-MM-DD] [YYYY-MM-DD] [table-name]
---

# Fetch Mixpanel Data

This command guides users through fetching either events or profiles from Mixpanel.

## Fetch Type Selection

Ask the user what they want to fetch:
- **Events**: Time-series event data (requires date range)
- **Profiles**: User profile data (no date range needed)

If date arguments are provided (`$1`, `$2`), assume events. Otherwise, ask.

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

**Calculate range**:
```python
from datetime import datetime
from_date = datetime.strptime("YYYY-MM-DD", "%Y-%m-%d")
to_date = datetime.strptime("YYYY-MM-DD", "%Y-%m-%d")
days = (to_date - from_date).days
```

**Recommend parallel fetching for large ranges**:
- If range > 7 days: Suggest `--parallel` for faster export (up to 10x speedup)
- If range > 100 days: `--parallel` is required (sequential has 100-day limit)

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

### 3. Parallel Fetching (Recommended for Large Ranges)

**Parallel mode** (`--parallel` or `-p`):
- Splits date range into chunks and fetches concurrently
- Up to 10x faster for multi-month ranges
- **Required for ranges > 100 days** (bypasses sequential API limit)
- Automatically recommend for ranges > 7 days

**Workers** (`--workers`, default: 10):
- Number of concurrent fetch threads
- Higher values may hit Mixpanel rate limits

**Chunk days** (`--chunk-days`, default: 7):
- Days per chunk for parallel splitting
- Valid range: 1-100 days
- Smaller = more parallelism, larger = fewer API calls

**Important**: `--limit` is incompatible with `--parallel`

### 4. Optional Filters (Advanced)

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
- **Not compatible with `--parallel`**

## Execute Fetch

### Base Command (Sequential)

```bash
mp fetch events <table-name> --from <from-date> --to <to-date>
```

### Parallel Command (Recommended for large ranges)

```bash
mp fetch events <table-name> --from <from-date> --to <to-date> --parallel
```

### With Options

Add flags based on user choices:
- `--parallel` or `-p` for parallel fetching (recommended for > 7 days)
- `--workers N` to control concurrency (default: 10)
- `--chunk-days N` to control chunk size (default: 7)
- `--append` if appending to existing table
- `--events "Event1" "Event2"` if filtering events
- `--where 'expression'` if filtering by properties
- `--limit N` if limiting results (NOT with --parallel)

### Examples

**Parallel fetch for large date range (recommended)**:
```bash
mp fetch events q4_events \
  --from 2024-10-01 \
  --to 2024-12-31 \
  --parallel
```

**Parallel fetch with custom workers and chunk size**:
```bash
mp fetch events yearly_events \
  --from 2024-01-01 \
  --to 2024-12-31 \
  --parallel \
  --workers 5 \
  --chunk-days 14
```

**Sequential fetch with filters (small range)**:
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

1. **Fetch results** (sequential):
   - Table name
   - Rows fetched
   - Time taken
   - Date range covered

1. **Fetch results** (parallel):
   - Table name
   - Total rows fetched
   - Successful/failed batches
   - Time taken (note the speedup vs sequential)
   - If failures: list failed date ranges for retry

2. **Verification query**:
```bash
mp query sql "SELECT COUNT(*) as total_events, COUNT(DISTINCT distinct_id) as unique_users FROM <table-name>" --format table
```

3. **Handle parallel failures** (if any):
   If some batches failed, offer to retry failed date ranges:
   ```bash
   mp fetch events <table-name> --from <failed-start> --to <failed-end> --append
   ```

4. **Next steps**:
   - Run `/mp-inspect` to explore table structure and events
   - Run `/mp-query` to analyze the data
   - Explore events: `mp inspect breakdown -t <table-name>`
   - Check schema: `mp inspect schema -t <table-name>`
   - Sample data: `mp query sql "SELECT * FROM <table-name> LIMIT 10" --format table`

## Common Patterns

**Full year with parallel (recommended)**:
```bash
mp fetch events events_2024 --from 2024-01-01 --to 2024-12-31 --parallel
```

**Quarter with parallel**:
```bash
mp fetch events q4_events --from 2024-10-01 --to 2024-12-31 --parallel
```

**Monthly data (sequential for small range)**:
```bash
mp fetch events jan --from 2024-01-01 --to 2024-01-31
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

**DateRangeTooLargeError**: Range > 100 days (sequential mode)
- Solution: Use `--parallel` flag for ranges > 100 days

**ValueError**: `--limit` used with `--parallel`
- Solution: Remove `--limit` or use sequential mode

**Parallel batch failures**: Some batches failed during parallel fetch
- The fetch continues and reports failures at the end
- Solution: Retry failed date ranges with `--append`:
  ```bash
  mp fetch events <table> --from <failed-start> --to <failed-end> --append
  ```

**TableExistsError**: Table exists without --append
- Solution: Use --append, --replace, or different name

**AuthenticationError**: Credentials invalid
- Solution: Run `/mp-auth` to reconfigure

**RateLimitError**: API rate limited
- Solution: Wait and retry (shows retry_after seconds)
- For parallel: reduce `--workers` count

**EventNotFoundError**: Event doesn't exist
- Solution: Check available events with `mp inspect events`

---

# Fetch Mixpanel Profiles

Guide the user through fetching user profiles from Mixpanel into a local DuckDB table.

## Pre-flight Check

First, verify credentials are configured:

```bash
!$(mp auth test 2>&1 || echo "No credentials configured")
```

If credentials aren't configured, suggest running `/mp-auth` first.

## Fetch Parameters

### 1. Table Name

**Table name**: `$3` if provided, otherwise suggest "profiles" as default

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

### 2. Parallel Fetching (Recommended for Large Datasets)

**Parallel mode** (`--parallel` or `-p`):
- Fetches pages concurrently using session-based pagination
- Up to 5x faster for large profile datasets
- Automatically recommend for datasets > 10,000 profiles

**Workers** (`--workers`, default: 5, max: 5):
- Number of concurrent fetch threads
- Mixpanel API limits parallel profile fetches to 5 concurrent requests

### 3. Optional Filters (Advanced)

Ask if the user wants to apply filters:

**Cohort filter** (optional):
- Filter to members of a specific cohort
- Example: `--cohort 12345`

**WHERE clause** (optional):
- Profile property filter expression
- Example: `--where 'properties["plan"] == "premium"'`

**Output properties** (optional):
- Specific properties to include
- Example: `--output-properties email,name,plan`

**Distinct IDs** (optional):
- Fetch specific users by ID
- Example: `--distinct-ids user_1 --distinct-ids user_2`

**Group profiles** (optional):
- Fetch group profiles instead of users
- Example: `--group-id companies`

**Behavioral filters** (optional):
- Filter users by behavior
- Example: `--behaviors '[{"window":"30d","name":"buyers","event_selectors":[{"event":"Purchase"}]}]' --where '(behaviors["buyers"] > 0)'`

## Execute Fetch

### Base Command (Sequential)

```bash
mp fetch profiles <table-name>
```

### Parallel Command (Recommended for large datasets)

```bash
mp fetch profiles <table-name> --parallel
```

### With Options

Add flags based on user choices:
- `--parallel` or `-p` for parallel fetching (recommended for large datasets)
- `--workers N` to control concurrency (default: 5, max: 5)
- `--append` if appending to existing table
- `--cohort ID` if filtering by cohort
- `--where 'expression'` if filtering by properties
- `--output-properties prop1,prop2` if selecting specific properties

### Examples

**Parallel fetch for large profile dataset (recommended)**:
```bash
mp fetch profiles all_users --parallel
```

**Parallel fetch with custom workers**:
```bash
mp fetch profiles users --parallel --workers 3
```

**Sequential fetch with filters (small dataset)**:
```bash
mp fetch profiles premium_users \
  --cohort 12345 \
  --where 'properties["plan"] == "premium"' \
  --append
```

**Behavioral filter**:
```bash
mp fetch profiles purchasers \
  --behaviors '[{"window":"30d","name":"buyers","event_selectors":[{"event":"Purchase"}]}]' \
  --where '(behaviors["buyers"] > 0)'
```

## Post-Fetch Summary

After fetch completes, show:

1. **Fetch results** (sequential):
   - Table name
   - Profiles fetched
   - Time taken

1. **Fetch results** (parallel):
   - Table name
   - Total profiles fetched
   - Successful/failed pages
   - Time taken (note the speedup vs sequential)
   - If failures: list failed page indices for retry

2. **Verification query**:
```bash
mp query sql "SELECT COUNT(*) as total_profiles FROM <table-name>" --format table
```

3. **Handle parallel failures** (if any):
   If some pages failed, offer to retry with append:
   ```bash
   mp fetch profiles <table-name> --append
   ```

4. **Next steps**:
   - Run `/mp-inspect` to explore table structure
   - Run `/mp-query` to analyze the data
   - Check schema: `mp inspect schema -t <table-name>`
   - Sample data: `mp query sql "SELECT * FROM <table-name> LIMIT 10" --format table`

## Common Patterns

**All profiles with parallel (recommended)**:
```bash
mp fetch profiles users --parallel
```

**Cohort members**:
```bash
mp fetch profiles cohort_users --cohort 12345
```

**Premium users**:
```bash
mp fetch profiles premium --where 'properties["plan"] == "premium"'
```

**Group profiles (companies)**:
```bash
mp fetch profiles companies --group-id companies
```

## Error Handling

**Parallel page failures**: Some pages failed during parallel fetch
- The fetch continues and reports failures at the end
- Solution: Retry with `--append`:
  ```bash
  mp fetch profiles <table> --append
  ```

**TableExistsError**: Table exists without --append
- Solution: Use --append, --replace, or different name

**AuthenticationError**: Credentials invalid
- Solution: Run `/mp-auth` to reconfigure

**RateLimitError**: API rate limited
- Solution: Wait and retry (shows retry_after seconds)
- For parallel: reduce `--workers` count (max 5)

**ValidationError**: Invalid parameter combination
- `--distinct-id` and `--distinct-ids` are mutually exclusive
- `--behaviors` and `--cohort` are mutually exclusive
- `--include-all-users` requires `--cohort`
