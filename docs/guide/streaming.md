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
    raw: bool = False,
) -> Iterator[dict[str, Any]]
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `where` | `str \| None` | Mixpanel expression filter |
| `raw` | `bool` | Return raw API format |

## Next Steps

- [Fetching Data](fetching.md) — Store data locally for repeated SQL queries
- [SQL Queries](sql-queries.md) — Query stored data with DuckDB SQL
- [Live Analytics](live-analytics.md) — Real-time Mixpanel reports
