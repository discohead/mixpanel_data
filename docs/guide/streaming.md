# Streaming Data

Stream events and user profiles directly from Mixpanel without storing to local database. Ideal for ETL pipelines, one-time exports, and Unix-style piping.

## When to Stream vs Fetch

| Use Case | Recommended | Why |
|----------|-------------|-----|
| Repeated analysis | `fetch_events()` | Query once, analyze many times |
| ETL to external system | `stream_events()` | No intermediate storage needed |
| Memory-constrained | `stream_events()` | Constant memory usage |
| Ad-hoc exploration | `fetch_events()` | SQL iteration is faster |
| Piping to tools | `--stdout` | JSONL integrates with jq, grep, etc. |

## Streaming Events

### Basic Usage

Stream all events for a date range:

=== "Python"

    ```python
    import mixpanel_data as mp

    ws = mp.Workspace()

    for event in ws.stream_events(
        from_date="2025-01-01",
        to_date="2025-01-31"
    ):
        print(f"{event['event_name']}: {event['distinct_id']}")
        # event_time is a datetime object
        # properties contains remaining fields

    ws.close()
    ```

=== "CLI"

    ```bash
    mp fetch events --from 2025-01-01 --to 2025-01-31 --stdout
    ```

### Filtering Events

Filter by event name or expression:

=== "Python"

    ```python
    # Filter by event names
    for event in ws.stream_events(
        from_date="2025-01-01",
        to_date="2025-01-31",
        events=["Purchase", "Signup"]
    ):
        process(event)

    # Filter with WHERE clause
    for event in ws.stream_events(
        from_date="2025-01-01",
        to_date="2025-01-31",
        where='properties["country"]=="US"'
    ):
        process(event)
    ```

=== "CLI"

    ```bash
    # Filter by event names
    mp fetch events --from 2025-01-01 --to 2025-01-31 \
        --events "Purchase,Signup" --stdout

    # Filter with WHERE clause
    mp fetch events --from 2025-01-01 --to 2025-01-31 \
        --where 'properties["country"]=="US"' --stdout
    ```

### Raw API Format

By default, streaming returns normalized data with `event_time` as a datetime. Use `raw=True` to get the exact Mixpanel API format:

=== "Python"

    ```python
    for event in ws.stream_events(
        from_date="2025-01-01",
        to_date="2025-01-31",
        raw=True
    ):
        # event has {"event": "...", "properties": {...}} structure
        # properties["time"] is Unix timestamp
        legacy_system.ingest(event)
    ```

=== "CLI"

    ```bash
    mp fetch events --from 2025-01-01 --to 2025-01-31 --stdout --raw
    ```

## Streaming Profiles

### Basic Usage

Stream all user profiles:

=== "Python"

    ```python
    for profile in ws.stream_profiles():
        sync_to_crm(profile)
    ```

=== "CLI"

    ```bash
    mp fetch profiles --stdout
    ```

### Filtering Profiles

=== "Python"

    ```python
    for profile in ws.stream_profiles(
        where='properties["plan"]=="premium"'
    ):
        send_survey(profile)
    ```

=== "CLI"

    ```bash
    mp fetch profiles --where 'properties["plan"]=="premium"' --stdout
    ```

### Streaming Specific Users

Stream a single user by their distinct ID:

=== "Python"

    ```python
    for profile in ws.stream_profiles(distinct_id="user_123"):
        process(profile)
    ```

=== "CLI"

    ```bash
    mp fetch profiles --distinct-id user_123 --stdout
    ```

Stream multiple specific users:

=== "Python"

    ```python
    user_ids = ["user_123", "user_456", "user_789"]
    for profile in ws.stream_profiles(distinct_ids=user_ids):
        sync_to_external_system(profile)
    ```

=== "CLI"

    ```bash
    mp fetch profiles --distinct-ids "user_123,user_456,user_789" --stdout
    ```

!!! warning "Mutually Exclusive"
    `distinct_id` and `distinct_ids` cannot be used together. Use `distinct_id` for a single user, `distinct_ids` for multiple users.

### Streaming Group Profiles

Stream group profiles (e.g., companies, accounts) instead of user profiles:

=== "Python"

    ```python
    # Stream all company profiles
    for company in ws.stream_profiles(group_id="companies"):
        sync_company(company)

    # Filter group profiles
    for account in ws.stream_profiles(
        group_id="accounts",
        where='properties["plan"]=="enterprise"'
    ):
        process_enterprise_account(account)
    ```

=== "CLI"

    ```bash
    # Stream company profiles
    mp fetch profiles --group-id companies --stdout

    # Filter group profiles
    mp fetch profiles --group-id accounts \
        --where 'properties["plan"]=="enterprise"' --stdout
    ```

### Behavioral Filtering

Stream users based on actions they've performed. Behaviors use a named pattern that you reference in a `where` clause:

=== "Python"

    ```python
    # Users who completed a purchase in last 30 days
    behaviors = [{
        "window": "30d",
        "name": "made_purchase",
        "event_selectors": [{"event": "Purchase"}]
    }]
    for profile in ws.stream_profiles(
        behaviors=behaviors,
        where='(behaviors["made_purchase"] > 0)'
    ):
        send_thank_you(profile)

    # Users who signed up but didn't purchase
    behaviors = [
        {"window": "30d", "name": "signed_up", "event_selectors": [{"event": "Signup"}]},
        {"window": "30d", "name": "purchased", "event_selectors": [{"event": "Purchase"}]}
    ]
    for profile in ws.stream_profiles(
        behaviors=behaviors,
        where='(behaviors["signed_up"] > 0) and (behaviors["purchased"] == 0)'
    ):
        send_conversion_reminder(profile)
    ```

=== "CLI"

    ```bash
    # Users who completed a purchase in last 30 days
    mp fetch profiles \
        --behaviors '[{"window":"30d","name":"made_purchase","event_selectors":[{"event":"Purchase"}]}]' \
        --where '(behaviors["made_purchase"] > 0)' \
        --stdout

    # Users who signed up but didn't purchase
    mp fetch profiles \
        --behaviors '[{"window":"30d","name":"signed_up","event_selectors":[{"event":"Signup"}]},{"window":"30d","name":"purchased","event_selectors":[{"event":"Purchase"}]}]' \
        --where '(behaviors["signed_up"] > 0) and (behaviors["purchased"] == 0)' \
        --stdout
    ```

!!! info "Behavior Format"
    Each behavior requires: `window` (time window like "30d"), `name` (identifier for `where` clause), and `event_selectors` (array with `{"event": "Name"}`).

!!! warning "Mutually Exclusive"
    `behaviors` cannot be used with `cohort_id`. Use one or the other for filtering.

### Historical Profile State

Query profile state at a specific point in time:

=== "Python"

    ```python
    import time

    # Profile state from 7 days ago
    seven_days_ago = int(time.time()) - (7 * 24 * 60 * 60)
    for profile in ws.stream_profiles(as_of_timestamp=seven_days_ago):
        compare_historical_state(profile)
    ```

=== "CLI"

    ```bash
    # Query historical state (Unix timestamp)
    mp fetch profiles --as-of-timestamp 1704067200 --stdout
    ```

### Cohort Membership Analysis

Get all users with cohort membership marked:

=== "Python"

    ```python
    # Stream all users, marking which are in the cohort
    for profile in ws.stream_profiles(
        cohort_id="12345",
        include_all_users=True
    ):
        if profile.get("in_cohort"):
            tag_as_cohort_member(profile)
        else:
            tag_as_non_member(profile)
    ```

=== "CLI"

    ```bash
    mp fetch profiles --cohort-id 12345 --include-all-users --stdout
    ```

!!! note "Requires cohort_id"
    `include_all_users` only works when `cohort_id` is specified.

## CLI Pipeline Examples

The `--stdout` flag outputs JSONL (one JSON object per line), perfect for Unix pipelines:

```bash
# Filter with jq
mp fetch events --from 2025-01-01 --to 2025-01-31 --stdout \
    | jq 'select(.event_name == "Purchase")'

# Count events
mp fetch events --from 2025-01-01 --to 2025-01-31 --stdout | wc -l

# Save to file
mp fetch events --from 2025-01-01 --to 2025-01-31 --stdout > events.jsonl

# Process with custom script
mp fetch events --from 2025-01-01 --to 2025-01-31 --stdout \
    | python process_events.py

# Extract specific fields
mp fetch profiles --stdout | jq -r '.distinct_id'
```

## Output Formats

### Normalized Format (Default)

Events:

```json
{
  "event_name": "Purchase",
  "distinct_id": "user_123",
  "event_time": "2025-01-15T10:30:00+00:00",
  "insert_id": "abc123",
  "properties": {
    "amount": 99.99,
    "currency": "USD"
  }
}
```

Profiles:

```json
{
  "distinct_id": "user_123",
  "last_seen": "2025-01-15T14:30:00",
  "properties": {
    "name": "Alice",
    "plan": "premium"
  }
}
```

### Raw Format (`raw=True` or `--raw`)

Events:

```json
{
  "event": "Purchase",
  "properties": {
    "distinct_id": "user_123",
    "time": 1705319400,
    "$insert_id": "abc123",
    "amount": 99.99,
    "currency": "USD"
  }
}
```

Profiles:

```json
{
  "$distinct_id": "user_123",
  "$properties": {
    "$last_seen": "2025-01-15T14:30:00",
    "name": "Alice",
    "plan": "premium"
  }
}
```

## Common Patterns

### ETL Pipeline

Batch events and send to external system:

```python
import mixpanel_data as mp
from your_warehouse import send_batch

ws = mp.Workspace()
batch = []

for event in ws.stream_events(from_date="2025-01-01", to_date="2025-01-31"):
    batch.append(event)
    if len(batch) >= 1000:
        send_batch(batch)
        batch = []

# Send remaining
if batch:
    send_batch(batch)

ws.close()
```

### Aggregation Without Storage

Compute statistics without creating a local table:

```python
from collections import Counter
import mixpanel_data as mp

ws = mp.Workspace()
event_counts = Counter()

for event in ws.stream_events(from_date="2025-01-01", to_date="2025-01-31"):
    event_counts[event["event_name"]] += 1

print(event_counts.most_common(10))
ws.close()
```

### Context Manager

Use `with` for automatic cleanup:

```python
import mixpanel_data as mp

with mp.Workspace() as ws:
    for event in ws.stream_events(from_date="2025-01-01", to_date="2025-01-31"):
        process(event)
# No need to call ws.close()
```

## Method Signatures

### stream_events()

```python
def stream_events(
    *,
    from_date: str,
    to_date: str,
    events: list[str] | None = None,
    where: str | None = None,
    raw: bool = False,
) -> Iterator[dict[str, Any]]
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `from_date` | `str` | Start date (YYYY-MM-DD) |
| `to_date` | `str` | End date (YYYY-MM-DD) |
| `events` | `list[str] \| None` | Event names to include |
| `where` | `str \| None` | Mixpanel expression filter |
| `raw` | `bool` | Return raw API format |

### stream_profiles()

```python
def stream_profiles(
    *,
    where: str | None = None,
    cohort_id: str | None = None,
    output_properties: list[str] | None = None,
    raw: bool = False,
    distinct_id: str | None = None,
    distinct_ids: list[str] | None = None,
    group_id: str | None = None,
    behaviors: list[dict[str, Any]] | None = None,
    as_of_timestamp: int | None = None,
    include_all_users: bool = False,
) -> Iterator[dict[str, Any]]
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `where` | `str \| None` | Mixpanel expression filter |
| `cohort_id` | `str \| None` | Filter by cohort membership |
| `output_properties` | `list[str] \| None` | Limit returned properties |
| `raw` | `bool` | Return raw API format |
| `distinct_id` | `str \| None` | Single user ID to fetch |
| `distinct_ids` | `list[str] \| None` | Multiple user IDs to fetch |
| `group_id` | `str \| None` | Group type for group profiles |
| `behaviors` | `list[dict] \| None` | Behavioral filters |
| `as_of_timestamp` | `int \| None` | Historical state Unix timestamp |
| `include_all_users` | `bool` | Include all users with cohort marking |

**Parameter Constraints:**

- `distinct_id` and `distinct_ids` are mutually exclusive
- `behaviors` and `cohort_id` are mutually exclusive
- `include_all_users` requires `cohort_id` to be set

## Next Steps

- [Fetching Data](fetching.md) — Store data locally for repeated SQL queries
- [SQL Queries](sql-queries.md) — Query stored data with DuckDB SQL
- [Live Analytics](live-analytics.md) — Real-time Mixpanel reports
