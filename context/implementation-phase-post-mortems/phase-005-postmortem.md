# Phase 005: Fetch Service — Implementation Post-Mortem

**Branch:** `005-fetch-service`
**Status:** Complete
**Date:** 2025-12-22

---

## Executive Summary

Phase 005 implemented the `FetcherService`, the orchestration layer that bridges the API Client (Phase 002) and Storage Engine (Phase 003). This service coordinates the complete data flow: streaming events/profiles from Mixpanel's Export APIs, transforming them to the storage schema, and persisting them in DuckDB tables with metadata tracking.

**Key insight:** The FetcherService is a thin orchestration layer with no business logic of its own. Its sole responsibility is connecting existing components—it delegates HTTP communication to `MixpanelAPIClient`, delegates storage to `StorageEngine`, and performs streaming transformation in between. This separation keeps each layer focused and testable.

---

## What Was Built

### 1. FetcherService Class

**Purpose:** Coordinate data fetches from Mixpanel API to local DuckDB storage with progress reporting.

**Architecture:**

```
FetcherService
├── __init__(api_client, storage)  # Dependency injection
├── fetch_events(...)               # Events workflow: API → transform → storage
└── fetch_profiles(...)             # Profiles workflow: API → transform → storage
```

**Key Design Decisions:**

| Decision | Rationale |
|----------|-----------|
| Constructor injection | Dependencies passed in; no hidden instantiation; easy to mock for testing |
| Stateless service | No internal state; all state lives in storage or comes from parameters |
| Module-level transform functions | Pure functions that can be unit-tested independently |
| Iterator-based transformation | Streaming architecture preserves memory efficiency from Phase 002 |

**Example:**
```python
from mixpanel_data._internal.api_client import MixpanelAPIClient
from mixpanel_data._internal.storage import StorageEngine
from mixpanel_data._internal.services.fetcher import FetcherService

client = MixpanelAPIClient(credentials)
storage = StorageEngine(path)
fetcher = FetcherService(client, storage)

result = fetcher.fetch_events(
    name="january_events",
    from_date="2024-01-01",
    to_date="2024-01-31",
)
print(f"Fetched {result.rows} events in {result.duration_seconds:.2f}s")
```

---

### 2. Event Transformation (`_transform_event`)

**Purpose:** Transform raw API event format to storage schema format.

**API Format (input):**
```python
{
    "event": "Sign Up",
    "properties": {
        "distinct_id": "user_123",
        "time": 1609459200,           # Unix timestamp (seconds)
        "$insert_id": "abc-123-def",
        "browser": "Chrome",
        "country": "US",
    }
}
```

**Storage Format (output):**
```python
{
    "event_name": "Sign Up",
    "event_time": datetime(2021, 1, 1, 0, 0, 0, tzinfo=UTC),
    "distinct_id": "user_123",
    "insert_id": "abc-123-def",
    "properties": {"browser": "Chrome", "country": "US"},  # Standard fields removed
}
```

**Key Design Decisions:**

| Decision | Rationale |
|----------|-----------|
| Extract standard fields from properties | `distinct_id`, `time`, `$insert_id` become top-level columns; remaining properties stay in JSON |
| Convert Unix timestamp to datetime | DuckDB-native TIMESTAMP type enables time-based queries (`WHERE event_time > '2024-01-01'`) |
| Generate UUID for missing `$insert_id` | Ensures every event has a primary key; handles legacy data without `$insert_id` |
| Shallow copy before modification | Never mutate input data; safe for iterator reuse and debugging |

**UUID Generation Rationale:**

Some Mixpanel events lack `$insert_id` (e.g., events from older SDKs or custom imports). Without a primary key:
- DuckDB cannot enforce uniqueness
- Deduplication becomes impossible
- Joins on event identity fail

Solution: Generate a UUIDv4 for each event missing `$insert_id`. This ensures:
- Every event has a unique identifier
- Primary key constraint is always satisfiable
- Logging alerts developers to data quality issues

```python
if insert_id is None:
    insert_id = str(uuid.uuid4())
    _logger.debug("Generated insert_id for event missing $insert_id")
```

---

### 3. Profile Transformation (`_transform_profile`)

**Purpose:** Transform raw API profile format to storage schema format.

**API Format (input):**
```python
{
    "$distinct_id": "user_123",
    "$properties": {
        "$last_seen": "2024-01-15T10:30:00",
        "$email": "user@example.com",
        "plan": "premium",
    }
}
```

**Storage Format (output):**
```python
{
    "distinct_id": "user_123",
    "last_seen": "2024-01-15T10:30:00",
    "properties": {"$email": "user@example.com", "plan": "premium"},  # $last_seen removed
}
```

**Key Design Decisions:**

| Decision | Rationale |
|----------|-----------|
| Extract `$last_seen` as top-level column | Enables efficient filtering by user activity recency |
| Preserve `$`-prefixed properties | Properties like `$email`, `$name` are user-facing; only `$last_seen` is structural |
| Handle missing `$last_seen` gracefully | Returns `None`; storage layer handles NULL |

---

### 4. Streaming Pipeline Architecture

**Purpose:** Maintain memory efficiency from API to storage.

**Pipeline Flow:**

```
MixpanelAPIClient.export_events()  →  _transform_event()  →  StorageEngine.create_events_table()
         ↓                                   ↓                            ↓
    Iterator[dict]               Iterator[dict] (generator)        Batch INSERT (2000 rows)
    ~1KB per event               ~1KB per event                    ~1KB per event in batch
```

**Implementation:**

```python
def fetch_events(self, name, from_date, to_date, ...):
    # Stream from API (Phase 002)
    events_iter = self._api_client.export_events(
        from_date=from_date,
        to_date=to_date,
        ...
    )

    # Transform as generator (no buffering)
    def transform_iterator() -> Iterator[dict[str, Any]]:
        for event in events_iter:
            yield _transform_event(event)

    # Store (Phase 003 handles batching)
    row_count = self._storage.create_events_table(
        name=name,
        data=transform_iterator(),
        metadata=metadata,
    )
```

**Memory Profile:**
- Without streaming: 1M events × 1KB = ~1GB RAM (impossible for large exports)
- With streaming: ~2KB per event (current event + transform output)
- Batch size 2000: ~4MB per batch in DuckDB

**Why generator expression?**
- Lazy evaluation: transform only executed when storage pulls next event
- No intermediate list allocation
- Backpressure: storage batch size controls memory, not API response rate

---

### 5. Progress Callback Integration

**Purpose:** Enable UI progress reporting during long-running fetches.

**Design:**

```python
def fetch_events(
    self,
    name: str,
    from_date: str,
    to_date: str,
    *,
    progress_callback: Callable[[int], None] | None = None,
) -> FetchResult:
    # Wrap callback for API client
    def on_api_batch(count: int) -> None:
        if progress_callback:
            progress_callback(count)

    events_iter = self._api_client.export_events(
        ...,
        on_batch=on_api_batch,
    )
```

**Callback Flow:**

```
API returns 1000 events  →  on_batch(1000)  →  progress_callback(1000)  →  UI: "1,000 events fetched"
API returns 2000 events  →  on_batch(2000)  →  progress_callback(2000)  →  UI: "2,000 events fetched"
```

**Key Design Decisions:**

| Decision | Rationale |
|----------|-----------|
| Optional callback | Not all callers need progress (e.g., scripts, tests) |
| Cumulative count | UI shows absolute progress without maintaining state |
| API-level granularity | Progress fires at API batch boundaries (every 1000 events) |
| Wrapper function | Allows future transformation (e.g., rate limiting callbacks) |

---

### 6. FetchResult Construction

**Purpose:** Return structured result with timing and metadata.

**FetchResult Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `table` | `str` | Created table name |
| `rows` | `int` | Number of rows stored |
| `type` | `Literal["events", "profiles"]` | Data type |
| `duration_seconds` | `float` | Total fetch duration |
| `date_range` | `tuple[str, str] \| None` | Date range (events only) |
| `fetched_at` | `datetime` | Completion timestamp |

**Timing Implementation:**

```python
def fetch_events(self, ...):
    start_time = datetime.now(UTC)

    # ... fetch and store ...

    completed_at = datetime.now(UTC)
    duration_seconds = (completed_at - start_time).total_seconds()

    return FetchResult(
        table=name,
        rows=row_count,
        type="events",
        duration_seconds=duration_seconds,
        date_range=(from_date, to_date),
        fetched_at=completed_at,
    )
```

**Timestamp Semantics:**
- `start_time`: When `fetch_events()` was called
- `metadata.fetched_at`: When metadata was constructed (before storage)
- `completed_at` / `result.fetched_at`: When storage completed

The distinction matters for auditing: metadata records when fetch was *initiated*, result records when it *completed*.

---

## Challenges & Solutions

### Challenge 1: Duplicate `insert_id` Values from Export API

**Problem:** During real-world testing with the `ai_demo` project, storage failed with duplicate primary key errors. The Mixpanel Export API returned 9,441 events, but many had duplicate `$insert_id` values.

**Root Cause:** The Export API returns raw, unprocessed data. Unlike Mixpanel's query APIs (which deduplicate at query time), the Export API includes every event instance—including duplicates that Mixpanel would normally collapse.

**Initial Approach (incorrect):**
```python
# Storage used regular INSERT
self.connection.executemany(
    f"INSERT INTO {name} VALUES (?, ?, ?, ?, ?)",
    batch
)
# → duckdb.ConstraintException: Duplicate key "insert_id"
```

**Solution:** Use `INSERT OR IGNORE` to silently skip duplicates:
```python
self.connection.executemany(
    f"INSERT OR IGNORE INTO {name} VALUES (?, ?, ?, ?, ?)",
    batch
)
```

**Result:** 9,441 raw events → 3,273 unique events stored (matching Mixpanel's query-time deduplication).

**Trade-off:** Silent skipping means we don't know how many duplicates were encountered. Acceptable because:
- Duplicates are expected behavior (documented by Mixpanel)
- Logging every duplicate would be noisy for large exports
- Row count in FetchResult reflects actual stored rows

**Regression Test:**
```python
def test_create_events_table_handles_duplicate_insert_ids():
    """Duplicate insert_ids should be silently ignored."""
    events = [
        {"event_name": "E1", ..., "insert_id": "same-id", ...},
        {"event_name": "E2", ..., "insert_id": "same-id", ...},  # Duplicate
    ]

    row_count = storage.create_events_table("events", iter(events), metadata)

    assert row_count == 1  # Second event silently skipped
```

### Challenge 2: Variable Reuse for Timestamps

**Problem:** Initial implementation reused `fetched_at` variable for both metadata and result:
```python
fetched_at = datetime.now(UTC)
metadata = TableMetadata(..., fetched_at=fetched_at, ...)

# ... storage operation ...

fetched_at = datetime.now(UTC)  # Reused variable!
return FetchResult(..., fetched_at=fetched_at)
```

**Issue:** While functionally correct, the variable reuse obscured the semantic difference between the two timestamps. PR review flagged this as confusing.

**Solution:** Use distinct variable names:
```python
fetched_at = datetime.now(UTC)
metadata = TableMetadata(..., fetched_at=fetched_at, ...)

# ... storage operation ...

completed_at = datetime.now(UTC)  # Distinct name
return FetchResult(..., fetched_at=completed_at)
```

**Lesson:** Variable names should communicate semantic meaning, not just type. `fetched_at` vs `completed_at` makes the timing model explicit.

### Challenge 3: Input Mutation Prevention

**Problem:** Early implementation mutated the input event dictionary:
```python
def _transform_event(event):
    properties = event["properties"]
    distinct_id = properties.pop("distinct_id", "")  # Mutates input!
    time = properties.pop("time", 0)                 # Mutates input!
```

**Issue:** If the same event dict was reused (e.g., for logging or debugging), it would be missing fields.

**Solution:** Shallow copy before modification:
```python
def _transform_event(event):
    properties = event.get("properties", {})
    remaining_props = dict(properties)  # Shallow copy
    distinct_id = remaining_props.pop("distinct_id", "")  # Safe
    time = remaining_props.pop("time", 0)                 # Safe
```

**Test:**
```python
def test_transform_event_does_not_mutate_input():
    api_event = {"event": "Test", "properties": {"distinct_id": "u1", "time": 0, "extra": "x"}}
    original = dict(api_event["properties"])

    _transform_event(api_event)

    assert api_event["properties"] == original  # Unchanged
```

---

## Test Coverage

### Unit Tests (`test_fetcher_service.py`) — 605 lines

**Transform Function Tests:**

| Test Class | Tests | Coverage |
|------------|-------|----------|
| `TestTransformEvent` | 6 | Valid data, missing insert_id, no mutation, empty properties, missing keys |
| `TestTransformProfile` | 6 | Valid data, missing last_seen, no mutation, empty properties, missing keys |

**Service Tests:**

| Test Class | Tests | Coverage |
|------------|-------|----------|
| `TestFetcherServiceInit` | 1 | Dependency injection |
| `TestFetchEvents` | 6 | API/storage integration, filters, TableExistsError, progress callback, metadata, timing |
| `TestFetchProfiles` | 6 | API/storage integration, where filter, TableExistsError, progress callback, metadata, None dates |

**Testing Strategy:**

| Approach | Tool | Purpose |
|----------|------|---------|
| Mocked dependencies | `unittest.mock.MagicMock` | Isolate FetcherService from API/storage |
| Callback capture | Nonlocal variable capture | Verify progress callback forwarding |
| Iterator mocking | Generator functions | Test streaming behavior |

**Key Test Patterns:**

```python
# Pattern 1: Mock API client with generator
def mock_export() -> Iterator[dict[str, Any]]:
    yield {"event": "E1", "properties": {...}}
    yield {"event": "E2", "properties": {...}}

mock_api_client.export_events.return_value = mock_export()

# Pattern 2: Capture progress callbacks
progress_values: list[int] = []

def progress_callback(count: int) -> None:
    progress_values.append(count)

fetcher.fetch_events(..., progress_callback=progress_callback)
# Then: captured_callback(1000); assert progress_values == [1000]

# Pattern 3: Verify metadata construction
storage_call = mock_storage.create_events_table.call_args
metadata = storage_call.kwargs["metadata"]
assert metadata.type == "events"
assert metadata.from_date == "2024-01-01"
```

---

## Code Quality Highlights

### 1. Type Safety

All methods fully typed with modern Python 3.11+ syntax:

```python
from collections.abc import Callable, Iterator
from typing import Any

def fetch_events(
    self,
    name: str,
    from_date: str,
    to_date: str,
    *,
    events: list[str] | None = None,
    where: str | None = None,
    progress_callback: Callable[[int], None] | None = None,
) -> FetchResult:
```

Mypy passes with no errors.

### 2. Docstrings

Every public method includes comprehensive documentation:

```python
def fetch_events(self, ...) -> FetchResult:
    """Fetch events from Mixpanel and store in local database.

    Args:
        name: Table name to create (alphanumeric + underscore, no leading _).
        from_date: Start date (YYYY-MM-DD, inclusive).
        to_date: End date (YYYY-MM-DD, inclusive).
        events: Optional list of event names to filter.
        where: Optional filter expression.
        progress_callback: Optional callback invoked with row count during fetch.

    Returns:
        FetchResult with table name, row count, duration, and metadata.

    Raises:
        TableExistsError: If table with given name already exists.
        AuthenticationError: If API credentials are invalid.
        RateLimitError: If Mixpanel rate limit is exceeded.
        QueryError: If filter expression is invalid.
        ValueError: If table name is invalid.
    """
```

### 3. TYPE_CHECKING Import Guard

Dependencies only needed for type hints use conditional import:

```python
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from mixpanel_data._internal.api_client import MixpanelAPIClient
    from mixpanel_data._internal.storage import StorageEngine
```

Benefits:
- No circular import risk at runtime
- Faster module loading (no unnecessary imports)
- Type hints still work for mypy/IDEs

---

## Integration Points

### Upstream Dependencies

**From Phase 002 (API Client):**
- `MixpanelAPIClient.export_events()` → Returns `Iterator[dict]`
- `MixpanelAPIClient.export_profiles()` → Returns `Iterator[dict]`
- `on_batch` callback parameter → Forwarded from progress_callback

**From Phase 003 (Storage Engine):**
- `StorageEngine.create_events_table()` → Accepts `Iterator[dict]`, returns row count
- `StorageEngine.create_profiles_table()` → Accepts `Iterator[dict]`, returns row count
- Raises `TableExistsError` → Propagated to caller

**From Phase 001 (Foundation):**
- Returns `FetchResult` type
- Uses `TableMetadata` type
- Propagates exceptions: `TableExistsError`, `AuthenticationError`, `RateLimitError`, `QueryError`

### Downstream Impact

**For Phase 007 (Workspace):**
```python
class Workspace:
    def __init__(self, ...):
        self._fetcher = FetcherService(self._api_client, self._storage)

    def fetch_events(self, from_date, to_date, table, ...):
        return self._fetcher.fetch_events(
            name=table,
            from_date=from_date,
            to_date=to_date,
            ...
        )
```

**For Phase 008 (CLI):**
```bash
mp fetch events --from 2024-01-01 --to 2024-01-31 --table january_events
# Internally: workspace.fetch_events(...) → fetcher.fetch_events(...)
```

---

## What's NOT Included

| Component | Phase | Notes |
|-----------|-------|-------|
| Live query execution | 006 | Segmentation, funnels, retention (no storage) |
| Table replacement logic | 007 | Workspace handles "fetch with replace" semantics |
| CLI progress bars | 008 | Rich progress bars wrap the callback |
| Incremental fetches | Future | Date range continuation not implemented |
| Parallel fetches | Future | Single-threaded streaming only |

**Design principle:** FetcherService is a single-responsibility orchestrator. Higher-level concerns (table replacement, UI) belong in Workspace and CLI.

---

## File Reference

| File | Lines | Purpose |
|------|-------|---------|
| [src/mixpanel_data/_internal/services/fetcher.py](../../src/mixpanel_data/_internal/services/fetcher.py) | 275 | FetcherService implementation |
| [tests/unit/test_fetcher_service.py](../../tests/unit/test_fetcher_service.py) | 605 | Comprehensive unit tests |
| [src/mixpanel_data/_internal/storage.py](../../src/mixpanel_data/_internal/storage.py) | (modified) | INSERT OR IGNORE for duplicates |
| [tests/unit/test_storage.py](../../tests/unit/test_storage.py) | (modified) | Duplicate handling tests |

**Test coverage:** 100% of FetcherService methods and transform functions.

---

## Lessons Learned

1. **Real-world data is messy:** Unit tests with synthetic data passed, but real Mixpanel exports revealed duplicate `insert_id` values. Always test with real API data before declaring "complete."

2. **Variable names carry semantics:** Reusing `fetched_at` for two different timestamps was technically correct but semantically confusing. Distinct names (`fetched_at` vs `completed_at`) made the code self-documenting.

3. **Streaming requires immutability:** When data flows through an iterator pipeline, mutation at any stage corrupts all downstream stages. Defensive copying is cheap insurance.

4. **Thin orchestration layers are easy to test:** FetcherService has ~275 lines of implementation and ~605 lines of tests. The high test:code ratio reflects the simplicity of testing pure coordination logic with mocked dependencies.

5. **Progress callbacks need careful forwarding:** The callback wrapper pattern (`on_api_batch` wrapping `progress_callback`) allows future enhancement (rate limiting, transformation) without changing the public API.

---

## Next Phase: 006 (Live Queries)

Phase 006 implements `LiveQueryService` for real-time analytics queries:
- `segmentation(event, from_date, to_date, ...)` → `SegmentationResult`
- `funnel(funnel_id, from_date, to_date, ...)` → `FunnelResult`
- `retention(born_event, event, from_date, to_date, ...)` → `RetentionResult`
- `jql(script, params)` → `JQLResult`

**Key difference from FetcherService:** Live queries call the Mixpanel Query API and return result types directly—no storage involved. They're for real-time analytics, not historical data warehousing.

---

**Post-Mortem Author:** Claude (Opus 4.5)
**Date:** 2025-12-22
**Lines of Code:** 275 (implementation) + 605 (tests) = 880 total
