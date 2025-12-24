# Implementation Plan: Streaming API (No-DB Mode)

**Created**: 2024-12-24
**Status**: Draft
**Input**: Add the ability to bypass the database and directly return raw data from the Mixpanel API, enabling the library and CLI to function as a pure Python SDK for the Mixpanel HTTP API without local storage.

## Problem Statement

Currently, all data fetching operations in `mixpanel_data` require storing data in a local DuckDB database. This forces users into the "fetch once, query repeatedly" paradigm even when they just want to:

- Pipe data directly to another system (ETL pipelines, data warehouses)
- Process events in a streaming fashion without disk I/O
- Use the library as a conventional API SDK in existing workflows
- Avoid disk space usage for one-time data exports

## Proposed Solution

Add `stream_events()` and `stream_profiles()` methods to the `Workspace` class that return iterators of event/profile dictionaries directly from the Mixpanel API, bypassing local storage entirely.

**Key Insight**: The raw streaming capability already exists in the codebase. `MixpanelAPIClient.export_events()` and `export_profiles()` return memory-efficient iterators. We just need to expose this through the Workspace facade.

### Naming Convention

| Method | Behavior |
|--------|----------|
| `fetch_events()` | Fetch from API → Store in DuckDB → Return FetchResult |
| `stream_events()` | Fetch from API → Yield directly → No storage |

This naming clearly communicates intent: "fetch" implies persistence, "stream" implies flow-through.

## Python Library Changes

### New Workspace Methods

```python
def stream_events(
    self,
    *,
    from_date: str,
    to_date: str,
    events: list[str] | None = None,
    where: str | None = None,
    raw: bool = False,
) -> Iterator[dict[str, Any]]:
    """Stream events directly from Mixpanel API without storing.

    Args:
        from_date: Start date (YYYY-MM-DD).
        to_date: End date (YYYY-MM-DD).
        events: Optional list of event names to filter.
        where: Optional WHERE clause for filtering.
        raw: If True, return raw API format. If False (default),
             return normalized format matching stored events.

    Yields:
        Event dictionaries.

    Raises:
        ConfigError: If API credentials not available.
        AuthenticationError: If credentials are invalid.
    """

def stream_profiles(
    self,
    *,
    where: str | None = None,
    raw: bool = False,
) -> Iterator[dict[str, Any]]:
    """Stream user profiles directly from Mixpanel API without storing.

    Args:
        where: Optional WHERE clause for filtering.
        raw: If True, return raw API format. If False (default),
             return normalized format matching stored profiles.

    Yields:
        Profile dictionaries.

    Raises:
        ConfigError: If API credentials not available.
        AuthenticationError: If credentials are invalid.
    """
```

### The `raw` Parameter

Two output formats are supported:

**`raw=True`** - Exact Mixpanel API format:
```python
# Events
{"event": "PageView", "properties": {"distinct_id": "user123", "time": 1703433600, "$insert_id": "abc", "page": "/home"}}

# Profiles
{"$distinct_id": "user123", "$properties": {"$last_seen": "2024-01-01", "plan": "pro"}}
```

**`raw=False`** (default) - Normalized format matching what gets stored in DuckDB:
```python
# Events
{"event_name": "PageView", "event_time": datetime(...), "distinct_id": "user123", "insert_id": "abc", "properties": {"page": "/home"}}

# Profiles
{"distinct_id": "user123", "last_seen": "2024-01-01", "properties": {"plan": "pro"}}
```

The normalized format:
- Converts Unix timestamps to Python datetime objects
- Extracts standard fields (distinct_id, time, $insert_id) from properties
- Provides consistency with data stored via `fetch_*` methods

### Implementation Approach

The implementation is minimal because infrastructure already exists:

```python
# In Workspace class

def stream_events(
    self,
    *,
    from_date: str,
    to_date: str,
    events: list[str] | None = None,
    where: str | None = None,
    raw: bool = False,
) -> Iterator[dict[str, Any]]:
    api = self._require_api_client()
    events_iter = api.export_events(
        from_date=from_date,
        to_date=to_date,
        events=events,
        where=where,
    )

    if raw:
        yield from events_iter
    else:
        from mixpanel_data._internal.services.fetcher import _transform_event
        for event in events_iter:
            yield _transform_event(event)
```

**Note**: The `_transform_event` and `_transform_profile` functions in `fetcher.py` are already standalone functions, making them easy to reuse.

## CLI Changes

### Option A: Flag on Existing Command (Recommended)

Add `--stdout` flag to existing fetch commands:

```bash
# Current behavior (stores to DB)
mp fetch events --from 2024-01-01 --to 2024-01-31 my_events

# New: Stream to stdout as JSONL
mp fetch events --from 2024-01-01 --to 2024-01-31 --stdout

# With raw format
mp fetch events --from 2024-01-01 --to 2024-01-31 --stdout --raw
```

When `--stdout` is provided:
- The `TABLE_NAME` argument becomes optional (not needed)
- Output is JSONL (one JSON object per line) to stdout
- No database interaction occurs
- Progress output goes to stderr (if enabled)

### Option B: Separate Command

```bash
# Dedicated streaming command
mp stream events --from 2024-01-01 --to 2024-01-31
mp stream profiles --where 'properties["plan"] == "pro"'
```

**Recommendation**: Option A (`--stdout` flag) is preferred because:
- Fewer commands to learn
- Natural extension of existing mental model
- Consistent with Unix philosophy (commands can output to stdout or files)

### Output Format

JSONL (JSON Lines) format - one JSON object per line:

```jsonl
{"event_name": "PageView", "event_time": "2024-01-01T12:00:00Z", "distinct_id": "user1", ...}
{"event_name": "Click", "event_time": "2024-01-01T12:01:00Z", "distinct_id": "user2", ...}
```

This format:
- Streams naturally (no need to buffer entire response)
- Pipes cleanly to `jq`, other CLI tools, or file redirection
- Is the standard for streaming JSON data

### CLI Implementation Notes

```python
@events_app.command("events")
def fetch_events(
    # ... existing params ...
    stdout: Annotated[bool, typer.Option("--stdout", help="Stream to stdout instead of storing")] = False,
    raw: Annotated[bool, typer.Option("--raw", help="Output raw API format (with --stdout)")] = False,
):
    if stdout:
        # Stream mode - output JSONL to stdout
        ws = Workspace(account=account)
        try:
            for event in ws.stream_events(from_date=from_date, to_date=to_date, events=event_filter, where=where, raw=raw):
                # Use json.dumps for datetime serialization
                console.print(json.dumps(event, default=str))
        finally:
            ws.close()
    else:
        # Existing storage mode
        ...
```

## Design Decisions

### 1. Why not a "no-db" Workspace?

A separate `StreamingWorkspace` or `Workspace(no_db=True)` was considered but rejected:
- Would duplicate significant code
- Creates confusion about which class to use
- The streaming capability is orthogonal to workspace lifecycle

### 2. Why not modify FetcherService?

Adding a `store=False` parameter to `FetcherService.fetch_events()` was considered but rejected:
- Muddies the service's single responsibility (fetch → store)
- Would require changing return types (FetchResult vs Iterator)
- The transformation logic can be cleanly reused without modifying the service

### 3. Why default `raw=False`?

The normalized format is the default because:
- Consistency with stored data (users can switch between fetch and stream)
- More useful for Python consumers (datetime objects vs Unix timestamps)
- Users wanting raw API format can explicitly opt in

### 4. Why `--stdout` instead of `--stream`?

`--stdout` better describes what happens (output goes to stdout) and follows Unix conventions. `--stream` might be confused with "streaming mode" which is always true for large exports.

## Files to Modify

### Python Library

| File | Changes |
|------|---------|
| `src/mixpanel_data/workspace.py` | Add `stream_events()` and `stream_profiles()` methods |
| `src/mixpanel_data/__init__.py` | No changes needed (methods are on Workspace class) |

### CLI

| File | Changes |
|------|---------|
| `src/mixpanel_data/cli/commands/fetch.py` | Add `--stdout` and `--raw` options to fetch commands |

### Tests

| File | Changes |
|------|---------|
| `tests/test_workspace.py` | Add tests for `stream_events()` and `stream_profiles()` |
| `tests/cli/test_fetch.py` | Add tests for `--stdout` flag |

### Documentation

| File | Changes |
|------|---------|
| `README.md` or docs | Document streaming usage patterns |

## User Scenarios

### Scenario 1: ETL Pipeline Integration

```python
import mixpanel_data as mp

ws = mp.Workspace()
for event in ws.stream_events(from_date="2024-01-01", to_date="2024-01-31"):
    # Send to data warehouse, Kafka, etc.
    send_to_warehouse(event)
ws.close()
```

### Scenario 2: CLI Data Export

```bash
# Export to file
mp fetch events --from 2024-01-01 --to 2024-01-31 --stdout > events.jsonl

# Pipe to jq for filtering
mp fetch events --from 2024-01-01 --to 2024-01-31 --stdout | jq 'select(.event_name == "Purchase")'

# Pipe to another tool
mp fetch events --from 2024-01-01 --to 2024-01-31 --stdout | my-ingestion-tool
```

### Scenario 3: Memory-Constrained Environment

```python
# Process millions of events without loading all into memory
ws = mp.Workspace()
purchase_total = 0
for event in ws.stream_events(from_date="2024-01-01", to_date="2024-12-31", events=["Purchase"]):
    purchase_total += event["properties"].get("amount", 0)
print(f"Total purchases: ${purchase_total}")
ws.close()
```

### Scenario 4: Raw API Access for Compatibility

```python
# Get exact API format for systems expecting Mixpanel's native schema
for event in ws.stream_events(from_date="2024-01-01", to_date="2024-01-31", raw=True):
    # event has original {"event": ..., "properties": {...}} structure
    legacy_system.ingest(event)
```

## Success Criteria

- **SC-001**: Users can iterate over events/profiles without any database file being created
- **SC-002**: Memory usage remains constant regardless of dataset size (streaming, not buffering)
- **SC-003**: `--stdout` CLI flag outputs valid JSONL that can be piped to other tools
- **SC-004**: Both raw and normalized output formats work correctly
- **SC-005**: All existing fetch functionality remains unchanged (backward compatible)
- **SC-006**: Error handling (auth errors, rate limits) works identically to fetch methods

## Estimated Scope

This is a small, surgical change:
- ~30 lines of new code in `workspace.py`
- ~20 lines of new code in CLI
- ~50-100 lines of tests
- No changes to existing code paths
- No new dependencies
