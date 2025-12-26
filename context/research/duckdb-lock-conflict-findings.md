# DuckDB Lock Conflict Research Findings

**Date:** 2025-12-26
**Status:** Discovery - Implementation Pending
**Origin:** Observed during QA testing of bookmarks API feature

This document catalogs findings from investigating DuckDB lock conflicts when multiple CLI processes attempt to access the same database file simultaneously.

## Problem Statement

When two `mp` CLI commands run concurrently against the same project, the second command crashes with a full Python traceback:

```
IOException: IO Error: Could not set lock on file "/home/vscode/.mp/data/3409416.db":
Conflicting lock is held in /usr/local/bin/python3.11 (PID 66618).
See also https://duckdb.org/docs/stable/connect/concurrency
```

This was discovered when:
1. An agent was running `mp inspect bookmarks` (long-running: ~20-27 seconds for 2500+ bookmarks)
2. A human simultaneously ran the same command
3. The second command crashed immediately with a non-user-friendly traceback

## Root Cause Analysis

### DuckDB's Concurrency Model

DuckDB uses a **single-writer, multiple-reader** model:

- Multiple processes can read simultaneously (`read_only=True`)
- Only ONE process can have write access at a time
- Lock conflicts occur at connection time, not query time

This design choice exists because:
> "DuckDB caches data in RAM for faster analytical queries, rather than going back and forth to disk during each query. It also allows the caching of function pointers, the database catalog, and other items so that subsequent queries on the same connection are faster."

Source: [DuckDB Concurrency Documentation](https://duckdb.org/docs/stable/connect/concurrency)

### Current Implementation Issue

The `Workspace.__init__` method eagerly creates a `StorageEngine` connection at construction time:

```python
# workspace.py:197
self._storage = StorageEngine(path=db_path)
```

And `StorageEngine.__init__` opens with write access:

```python
# storage.py:133
self._conn = duckdb.connect(database=str(path), read_only=False)
```

This means **every CLI command** acquires an exclusive write lock on startup, even commands that:
- Only call the Mixpanel API (e.g., `inspect bookmarks`, `query saved-report`)
- Only read from the database (e.g., `inspect schema`, `inspect sample`)

## Solution Options

### Option 1: Lazy Storage Initialization (Recommended)

Make `_storage` a lazy property that only connects when storage is actually accessed.

**Benefits:**
- API-only commands (`inspect bookmarks`, `query saved-report`, etc.) won't touch the database at all
- Faster startup time for API-only commands
- Eliminates the conflict for the most common concurrent use case

**Implementation:**
```python
@property
def storage(self) -> StorageEngine:
    if self._storage is None:
        db_path = Path.home() / ".mp" / "data" / f"{self._credentials.project_id}.db"
        self._storage = StorageEngine(path=db_path)
    return self._storage
```

**Effort:** Medium - requires updating all `self._storage` references to `self.storage`

### Option 2: Graceful Error Message

Catch `duckdb.IOException` and convert to a clean, user-friendly error.

**Benefits:**
- Quick to implement
- Reduces context pollution from tracebacks

**Implementation:**
```python
try:
    self._conn = duckdb.connect(database=str(path), read_only=False)
except duckdb.IOException as e:
    if "Could not set lock" in str(e):
        raise DatabaseLockedError(
            "Database is locked by another process. "
            "Wait for the other operation to complete and try again."
        ) from None
    raise
```

**Effort:** Low

### Option 3: Retry with Exponential Backoff

Automatically retry connection with delays for brief locks.

**Benefits:**
- Handles race conditions where locks are held briefly
- Transparent to user

**Drawbacks:**
- Won't help for long-running operations (like 20-second API calls)
- Adds latency on conflict

**Effort:** Low

### Option 4: Read-Only Fallback

If write lock fails, try read-only mode.

**Benefits:**
- Allows concurrent read operations
- Commands like `inspect sample` could still work

**Drawbacks:**
- Only works for read operations
- May confuse users if some commands work and others don't
- Requires detecting which operations need write access

**Effort:** Medium

## Recommendations

### Phase 1: Graceful Error Message (Quick Win)
Add a custom `DatabaseLockedError` exception and catch DuckDB lock conflicts at the storage layer. This immediately improves the user experience.

### Phase 2: Lazy Storage Initialization (Primary Fix)
Refactor `Workspace` to lazily initialize storage. This eliminates the conflict entirely for API-only commands, which represent the majority of the CLI surface area.

**Commands that DON'T need storage:**
- `auth login`, `auth logout`, `auth status`, `auth list`
- `inspect events`, `inspect properties`, `inspect values`
- `inspect funnels`, `inspect cohorts`, `inspect top-events`
- `inspect bookmarks`, `inspect lexicon-schemas`, `inspect lexicon-schema`
- `query segmentation`, `query funnel`, `query retention`
- `query jql`, `query event-counts`, `query property-counts`
- `query activity-feed`, `query saved-report`, `query flows`
- `query frequency`, `query segmentation-numeric`, `query segmentation-sum`, `query segmentation-average`

**Commands that DO need storage:**
- `fetch events`, `fetch profiles`
- `inspect tables`, `inspect schema`, `inspect sample`, `inspect describe`, `inspect column`
- `query sql`

### Phase 3: Read-Only Mode for Read Operations (Future)
For commands that read from storage but don't write, open with `read_only=True`. This enables true concurrent reads.

## Related Context

### Performance Observation

During this investigation, we also discovered that the Mixpanel Bookmarks API is slow for projects with many bookmarks:

| Bookmark Count | API Response Time |
|----------------|-------------------|
| 20 | 1.3-1.7 seconds |
| 2,561 | 20-27 seconds |

The transformation overhead (converting API response to Python dataclasses) is negligible (~4ms for 2,561 items). The slowness is entirely in the Mixpanel API itself.

This is why we added `status_spinner` to CLI commands - to show users that work is in progress during long API calls.

## References

- [DuckDB Concurrency Documentation](https://duckdb.org/docs/stable/connect/concurrency)
- [DuckDB Multiple Python Threads](https://duckdb.org/docs/stable/guides/python/multiple_threads)
- [DuckDB Analytics-Optimized Concurrent Transactions (Oct 2024)](https://duckdb.org/2024/10/30/analytics-optimized-concurrent-transactions)
