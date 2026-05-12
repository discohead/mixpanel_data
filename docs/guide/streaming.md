# Streaming Data

Stream events and user profiles directly from Mixpanel. Ideal for ETL pipelines, data processing, exports, and Unix-style piping.

!!! tip "Explore on DeepWiki"
    🤖 **[Data Flow Patterns →](https://deepwiki.com/mixpanel/mixpanel-headless/4.1-data-flow-patterns)**

    Ask questions about streaming, memory-efficient processing, or ETL pipeline patterns.

## Streaming Events

### Basic Usage

Stream all events for a date range:

```python
import mixpanel_headless as mp

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

### Filtering Events

Filter by event name or expression:

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

### Raw API Format

By default, streaming returns normalized data with `event_time` as a datetime. Use `raw=True` to get the exact Mixpanel API format:

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

## Streaming Profiles

### Basic Usage

Stream all user profiles:

```python
for profile in ws.stream_profiles():
    sync_to_crm(profile)
```

### Filtering Profiles

```python
for profile in ws.stream_profiles(
    where='properties["plan"]=="premium"'
):
    send_survey(profile)
```

### Streaming Specific Users

Stream a single user by their distinct ID:

```python
for profile in ws.stream_profiles(distinct_id="user_123"):
    process(profile)
```

Stream multiple specific users:

```python
user_ids = ["user_123", "user_456", "user_789"]
for profile in ws.stream_profiles(distinct_ids=user_ids):
    sync_to_external_system(profile)
```

!!! warning "Mutually Exclusive"
    `distinct_id` and `distinct_ids` cannot be used together. Use `distinct_id` for a single user, `distinct_ids` for multiple users.

### Streaming Group Profiles

Stream group profiles (e.g., companies, accounts) instead of user profiles:

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

### Behavioral Filtering

Stream users based on actions they've performed. Behaviors use a named pattern that you reference in a `where` clause:

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

!!! info "Behavior Format"
    Each behavior requires: `window` (time window like "30d"), `name` (identifier for `where` clause), and `event_selectors` (array with `{"event": "Name"}`).

!!! warning "Mutually Exclusive"
    `behaviors` cannot be used with `cohort_id`. Use one or the other for filtering.

### Historical Profile State

Query profile state at a specific point in time:

```python
import time

# Profile state from 7 days ago
seven_days_ago = int(time.time()) - (7 * 24 * 60 * 60)
for profile in ws.stream_profiles(as_of_timestamp=seven_days_ago):
    compare_historical_state(profile)
```

### Cohort Membership Analysis

Get all users with cohort membership marked:

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

!!! note "Requires cohort_id"
    `include_all_users` only works when `cohort_id` is specified.

## Processing Patterns

Use Python to filter, count, and export streamed data:

```python
import json
import mixpanel_headless as mp

ws = mp.Workspace()

# Filter to specific events
purchases = [
    e for e in ws.stream_events(from_date="2025-01-01", to_date="2025-01-31")
    if e["event_name"] == "Purchase"
]

# Count events
count = sum(1 for _ in ws.stream_events(from_date="2025-01-01", to_date="2025-01-31"))

# Save to JSONL file
with open("events.jsonl", "w") as f:
    for event in ws.stream_events(from_date="2025-01-01", to_date="2025-01-31"):
        f.write(json.dumps(event) + "\n")

# Extract specific fields
distinct_ids = [
    p["distinct_id"] for p in ws.stream_profiles()
]

ws.close()
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

### Raw Format (`raw=True`)

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
import mixpanel_headless as mp
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
import mixpanel_headless as mp

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
import mixpanel_headless as mp

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

- [Live Analytics](live-analytics.md) — Real-time Mixpanel reports
