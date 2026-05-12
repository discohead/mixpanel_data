# Research: Fetch Service

**Feature**: 005-fetch-service
**Date**: 2025-12-22
**Status**: Complete

## Overview

This document captures research findings and design decisions for the FetcherService implementation. All technical decisions are based on analysis of existing codebase components (MixpanelAPIClient, StorageEngine, DiscoveryService) and the project constitution.

---

## 1. Event Data Transformation

### Context
The Mixpanel Export API returns events in a specific format that must be transformed to match the StorageEngine's expected schema.

### Decision
Transform events using a generator function that yields transformed records:

**API Format** (from `export_events()`):
```json
{
  "event": "Sign Up",
  "properties": {
    "distinct_id": "user_123",
    "time": 1609459200,
    "$insert_id": "abc-123-def",
    "browser": "Chrome",
    "country": "US"
  }
}
```

**Storage Format** (for `create_events_table()`):
```json
{
  "event_name": "Sign Up",
  "event_time": 1609459200,
  "distinct_id": "user_123",
  "insert_id": "abc-123-def",
  "properties": {
    "browser": "Chrome",
    "country": "US"
  }
}
```

### Rationale
- **Generator pattern**: Maintains streaming behavior; no memory accumulation
- **Shallow copy of properties**: Avoid mutating the API response
- **Remove extracted keys**: Keep properties clean for JSON storage

### Alternatives Considered
1. **Materialize to list first**: Rejected - breaks streaming, consumes memory
2. **Mutate in-place**: Rejected - could affect API client's internal state

---

## 2. Profile Data Transformation

### Context
The Mixpanel Engage API returns profiles in a format that must be transformed to match the StorageEngine's expected schema.

### Decision
Transform profiles using a generator function:

**API Format** (from `export_profiles()`):
```json
{
  "$distinct_id": "user_123",
  "$properties": {
    "$last_seen": "2024-01-15T10:30:00",
    "$email": "user@example.com",
    "plan": "premium"
  }
}
```

**Storage Format** (for `create_profiles_table()`):
```json
{
  "distinct_id": "user_123",
  "last_seen": "2024-01-15T10:30:00",
  "properties": {
    "$email": "user@example.com",
    "plan": "premium"
  }
}
```

### Rationale
- Consistent with event transformation pattern
- Preserves `$`-prefixed properties in JSON (except `$last_seen` which is extracted)
- Maintains streaming behavior

### Alternatives Considered
1. **Strip all $ prefixes**: Rejected - would lose semantic meaning of reserved properties

---

## 3. Missing Field Handling

### Context
Edge cases exist where events may lack `$insert_id` or profiles may lack `$last_seen`.

### Decision

**Events without `$insert_id`**:
- Generate a UUID using `uuid.uuid4()` as fallback
- Log a warning for observability
- This ensures deduplication still works via the primary key

**Profiles without `$last_seen`**:
- Use `None` (NULL in DuckDB)
- This is acceptable as `last_seen` is nullable in the schema

### Rationale
- **UUID fallback for insert_id**: Prevents primary key constraint violation; each fetch gets unique IDs
- **NULL for last_seen**: The schema allows NULL; no reasonable default exists

### Alternatives Considered
1. **Raise error on missing $insert_id**: Rejected - would fail on legitimate Mixpanel data
2. **Use current timestamp for last_seen**: Rejected - inaccurate; NULL is more honest

---

## 4. Progress Callback Coordination

### Context
Both the API client and storage engine support progress callbacks, but they fire at different intervals:
- API client: Every 1,000 events (or per page for profiles)
- Storage engine: Every 2,000 rows inserted

### Decision
Use **API client's `on_batch` callback only** for progress reporting. The storage engine's callback is internal.

**Implementation**:
```python
def fetch_events(self, ..., progress_callback: Callable[[int], None] | None = None):
    def on_api_batch(count: int) -> None:
        if progress_callback:
            progress_callback(count)

    events_iter = self._api_client.export_events(
        ...,
        on_batch=on_api_batch
    )
    # Don't pass progress_callback to storage - would double-report
    self._storage.create_events_table(name, transformed_iter, metadata)
```

### Rationale
- **Single source of progress**: Avoids confusing double-counting
- **API-side progress is more meaningful**: Represents data received, not stored
- **Simpler mental model**: Count goes up as data arrives

### Alternatives Considered
1. **Use storage callback only**: Rejected - delayed feedback (2,000 row batches)
2. **Sum both callbacks**: Rejected - confusing; would report 3x the rows

---

## 5. Timing and FetchResult Construction

### Context
FetchResult requires accurate `duration_seconds` and `fetched_at` timestamp.

### Decision
- Capture `start_time = datetime.now(timezone.utc)` at method entry
- Capture `fetched_at = datetime.now(timezone.utc)` after storage completes
- Calculate `duration_seconds = (fetched_at - start_time).total_seconds()`

### Rationale
- **UTC timestamps**: Consistent, timezone-agnostic
- **fetched_at after storage**: Represents when data is actually queryable
- **duration includes storage**: More accurate total operation time

### Alternatives Considered
1. **Wall clock time.time()**: Rejected - datetime is more explicit and testable

---

## 6. Transaction and Error Handling

### Context
The StorageEngine already wraps table creation in transactions. The FetcherService needs to handle errors appropriately.

### Decision
**Let exceptions propagate**. Do not add additional transaction handling.

**Error Flow**:
1. API errors (`AuthenticationError`, `RateLimitError`, `QueryError`) → propagate immediately
2. Storage errors (`TableExistsError`, `ValueError`) → propagate immediately
3. StorageEngine auto-rolls back on any error during `create_*_table()`

### Rationale
- **StorageEngine handles transactions**: No need for duplicate logic
- **Caller handles exceptions**: Workspace/CLI layer can present errors appropriately
- **Clean separation**: FetcherService orchestrates; doesn't manage transactions

### Alternatives Considered
1. **Wrap in try/except and re-raise**: Rejected - adds noise without value
2. **Explicit transaction management**: Rejected - StorageEngine already does this

---

## 7. Service Pattern

### Context
DiscoveryService provides a reference implementation for service classes in this codebase.

### Decision
Follow DiscoveryService pattern exactly:

```python
class FetcherService:
    def __init__(
        self,
        api_client: MixpanelAPIClient,
        storage: StorageEngine,
    ) -> None:
        self._api_client = api_client
        self._storage = storage

    def fetch_events(self, ...) -> FetchResult: ...
    def fetch_profiles(self, ...) -> FetchResult: ...
```

### Rationale
- **Dependency injection**: Enables testing with mocks
- **Private attributes**: Internal implementation detail
- **No caching**: Unlike DiscoveryService, fetch operations are not cacheable

### Alternatives Considered
1. **Factory methods**: Rejected - over-engineering for this use case
2. **Singleton**: Rejected - violates "no global mutable state" principle

---

## 8. TableMetadata Construction

### Context
The StorageEngine requires `TableMetadata` when creating tables. This metadata is persisted in the `_metadata` table.

### Decision
Construct `TableMetadata` in the fetch methods with all available context:

```python
metadata = TableMetadata(
    type="events",
    fetched_at=fetched_at,
    from_date=from_date,
    to_date=to_date,
    filter_events=events,
    filter_where=where,
)
```

### Rationale
- **Complete audit trail**: Know exactly what was fetched and when
- **filter_events/filter_where**: Useful for understanding table contents later
- **from_date/to_date**: Essential for date-based analysis

### Alternatives Considered
1. **Minimal metadata (type only)**: Rejected - loses valuable context

---

## Summary

All technical decisions are resolved. No NEEDS CLARIFICATION items remain. The implementation can proceed with:

1. **Event transformation**: Generator with shallow copy, UUID fallback for missing insert_id
2. **Profile transformation**: Generator with shallow copy, NULL for missing last_seen
3. **Progress callbacks**: API-side only, forwarded to caller
4. **Timing**: UTC timestamps, duration includes storage time
5. **Error handling**: Let exceptions propagate; StorageEngine handles transactions
6. **Service pattern**: Follow DiscoveryService; dependency injection
7. **Metadata**: Full context including filters and date range
