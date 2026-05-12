# Quickstart: Streaming API

**Feature**: 011-streaming-api
**Date**: 2024-12-24

## Overview

The Streaming API enables you to retrieve Mixpanel data directly without storing it locally. This is ideal for:
- ETL pipelines that send data to external systems
- One-time exports without disk usage
- Memory-constrained environments processing large datasets
- Unix-style piping to other tools

## Python Library

### Stream Events

```python
import mixpanel_data as mp

# Create workspace with credentials
ws = mp.Workspace()

# Stream events (normalized format by default)
for event in ws.stream_events(from_date="2024-01-01", to_date="2024-01-31"):
    print(f"{event['event_name']}: {event['distinct_id']}")
    # event['event_time'] is a datetime object
    # event['properties'] contains remaining fields

ws.close()
```

### Stream with Filters

```python
# Filter by event names
for event in ws.stream_events(
    from_date="2024-01-01",
    to_date="2024-01-31",
    events=["Purchase", "Signup"],
):
    process(event)

# Filter with WHERE clause
for event in ws.stream_events(
    from_date="2024-01-01",
    to_date="2024-01-31",
    where='properties["country"]=="US"',
):
    process(event)
```

### Raw API Format

```python
# Get exact Mixpanel API format (for legacy systems)
for event in ws.stream_events(from_date="2024-01-01", to_date="2024-01-31", raw=True):
    # event has {"event": "...", "properties": {...}} structure
    # event['properties']['time'] is Unix timestamp
    legacy_system.ingest(event)
```

### Stream Profiles

```python
# Stream all profiles
for profile in ws.stream_profiles():
    sync_to_crm(profile)

# Filter profiles
for profile in ws.stream_profiles(where='properties["plan"]=="premium"'):
    send_survey(profile)
```

### Context Manager Usage

```python
# Recommended: use context manager for automatic cleanup
with mp.Workspace() as ws:
    for event in ws.stream_events(from_date="2024-01-01", to_date="2024-01-31"):
        process(event)
# No need to call ws.close()
```

## CLI

### Stream to Stdout

```bash
# Stream events as JSONL
mp fetch events --from 2024-01-01 --to 2024-01-31 --stdout

# Stream profiles
mp fetch profiles --stdout
```

### Pipe to Other Tools

```bash
# Filter with jq
mp fetch events --from 2024-01-01 --to 2024-01-31 --stdout | jq 'select(.event_name == "Purchase")'

# Count events
mp fetch events --from 2024-01-01 --to 2024-01-31 --stdout | wc -l

# Save to file
mp fetch events --from 2024-01-01 --to 2024-01-31 --stdout > events.jsonl

# Pipe to custom script
mp fetch events --from 2024-01-01 --to 2024-01-31 --stdout | python process_events.py
```

### Raw Format

```bash
# Get Mixpanel's native API format
mp fetch events --from 2024-01-01 --to 2024-01-31 --stdout --raw
```

### With Filters

```bash
# Filter by event names
mp fetch events --from 2024-01-01 --to 2024-01-31 --events "Purchase,Signup" --stdout

# Filter with WHERE clause
mp fetch events --from 2024-01-01 --to 2024-01-31 --where 'properties["country"]=="US"' --stdout
```

## Comparison: Fetch vs Stream

| Aspect | `fetch_events()` | `stream_events()` |
|--------|------------------|-------------------|
| Storage | Creates DuckDB table | No storage |
| Memory | Depends on table size | Constant (streaming) |
| Return value | `FetchResult` | `Iterator[dict]` |
| Query afterwards | Yes (SQL) | No |
| Use case | Repeated analysis | One-time processing |

## Common Patterns

### ETL Pipeline

```python
import mixpanel_data as mp
from your_warehouse import send_batch

ws = mp.Workspace()
batch = []

for event in ws.stream_events(from_date="2024-01-01", to_date="2024-01-31"):
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

```python
from collections import Counter
import mixpanel_data as mp

ws = mp.Workspace()
event_counts = Counter()

for event in ws.stream_events(from_date="2024-01-01", to_date="2024-01-31"):
    event_counts[event["event_name"]] += 1

print(event_counts.most_common(10))
ws.close()
```

### Parallel Processing with Generator

```python
import mixpanel_data as mp
from concurrent.futures import ThreadPoolExecutor

def process(event):
    # Your processing logic
    return transform(event)

ws = mp.Workspace()
events = ws.stream_events(from_date="2024-01-01", to_date="2024-01-31")

with ThreadPoolExecutor(max_workers=4) as executor:
    results = executor.map(process, events)
    for result in results:
        save(result)

ws.close()
```
