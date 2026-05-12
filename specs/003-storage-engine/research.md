# Research: Storage Engine

**Phase**: 0 (Outline & Research)
**Date**: 2025-12-21
**Focus**: DuckDB patterns, streaming ingestion, ephemeral cleanup strategies

## Research Areas

### 1. DuckDB Embedded Database Patterns

**Decision**: Use DuckDB's Python API with connection pooling disabled (single connection per StorageEngine instance)

**Rationale**:
- DuckDB is designed for embedded analytics with excellent JSON support
- Single-file database simplifies deployment and backup
- Native pandas DataFrame integration eliminates conversion overhead
- JSON column type supports Mixpanel's dynamic property schema
- ACID compliance ensures data integrity

**Alternatives Considered**:
- **SQLite**: Rejected - weaker JSON support, slower analytical queries, no native DataFrame integration
- **PostgreSQL**: Rejected - requires server process, overkill for embedded use case
- **In-memory only**: Rejected - doesn't meet persistence requirement

**Implementation Pattern**:
```python
import duckdb

# Single connection per instance (no pooling needed - embedded)
conn = duckdb.connect(database=str(path), read_only=False)

# JSON column support
conn.execute("""
    CREATE TABLE events (
        event_name VARCHAR,
        event_time TIMESTAMP,
        distinct_id VARCHAR,
        insert_id VARCHAR PRIMARY KEY,
        properties JSON
    )
""")

# Query JSON properties
conn.execute("SELECT properties->>'$.country' FROM events")
```

**Key Findings**:
- DuckDB connections are lightweight (embedded, no network overhead)
- Use `COPY FROM` or batch `INSERT` for bulk ingestion
- JSON extraction syntax: `properties->>'$.field'` for strings, `CAST(properties->>'$.num' AS INTEGER)` for numbers
- `PRAGMA` commands control memory limits and temporary directory

### 2. Streaming Batch Ingestion

**Decision**: Use iterator-based ingestion with batches of 1000-5000 rows inserted via prepared statements

**Rationale**:
- Iterators enable processing datasets larger than memory
- Batch inserts balance memory efficiency and transaction overhead
- Prepared statements prevent SQL injection and improve performance
- DuckDB's transaction model allows large atomic inserts

**Implementation Pattern**:
```python
from collections.abc import Iterator
from typing import Any

def create_events_table(
    name: str,
    data: Iterator[dict[str, Any]],
    batch_size: int = 1000
) -> int:
    """Stream data from iterator to DuckDB in batches."""
    conn.execute(f"CREATE TABLE {name} (...)")

    total_rows = 0
    batch = []

    for record in data:
        batch.append(record)

        if len(batch) >= batch_size:
            # Insert batch using executemany
            conn.executemany(
                f"INSERT INTO {name} VALUES (?, ?, ?, ?, ?)",
                [(r['event_name'], r['event_time'], ...) for r in batch]
            )
            total_rows += len(batch)
            batch = []

    # Insert remaining records
    if batch:
        conn.executemany(...)
        total_rows += len(batch)

    return total_rows
```

**Key Findings**:
- Batch size 1000-5000 provides good tradeoff (emperical testing needed)
- Use `executemany()` for batch inserts (single transaction per batch)
- Call optional progress callback every N batches (e.g., every 10 batches)
- Memory usage stays constant regardless of total dataset size

**Performance Benchmarks** (from DuckDB documentation):
- Single row inserts: ~10K rows/sec
- Batch inserts (1000 rows): ~500K rows/sec
- COPY FROM (bulk load): ~2M rows/sec
- Our approach: Batch inserts strike balance between streaming and performance

### 3. Ephemeral Database Cleanup

**Decision**: Use `tempfile.NamedTemporaryFile` with `delete=False` + `atexit` handler for cleanup

**Rationale**:
- Python's `tempfile` module handles OS-specific temp directory logic
- `delete=False` prevents premature deletion while database is open
- `atexit` handlers run on normal exit (Ctrl+C, exceptions, sys.exit())
- Temp files in system temp dir get OS-managed cleanup if process killed (SIGKILL)

**Implementation Pattern**:
```python
import atexit
import tempfile
from pathlib import Path

class StorageEngine:
    def __init__(self, path: Path | None = None):
        self._is_ephemeral = False
        self._temp_file: Any | None = None

        if path is None:
            # Ephemeral mode
            self._temp_file = tempfile.NamedTemporaryFile(
                suffix='.duckdb',
                delete=False
            )
            self._path = Path(self._temp_file.name)
            self._is_ephemeral = True

            # Register cleanup handler
            atexit.register(self._cleanup_ephemeral)
        else:
            self._path = path

    def _cleanup_ephemeral(self) -> None:
        """Clean up ephemeral database file."""
        if self._is_ephemeral and self._path.exists():
            try:
                self._conn.close()
                self._path.unlink()
                # Also remove WAL files if they exist
                wal_path = self._path.with_suffix('.duckdb.wal')
                if wal_path.exists():
                    wal_path.unlink()
            except Exception:
                pass  # Best effort cleanup

    def close(self) -> None:
        """Explicit cleanup (also called by __exit__)."""
        if self._is_ephemeral:
            self._cleanup_ephemeral()
        else:
            self._conn.close()
```

**Key Findings**:
- `atexit` handlers run in LIFO order (last registered, first executed)
- Handlers DO run on: normal exit, sys.exit(), unhandled exceptions, Ctrl+C (KeyboardInterrupt)
- Handlers DO NOT run on: SIGKILL (kill -9), os._exit(), catastrophic failures
- DuckDB creates WAL (Write-Ahead Log) files - must clean up both `.duckdb` and `.duckdb.wal`
- Best practice: Implement both `close()` and `__exit__` for explicit cleanup

**Cleanup Reliability Test Cases**:
1. Normal exit: ✓ `atexit` runs
2. Exception during execution: ✓ `atexit` runs
3. Ctrl+C (KeyboardInterrupt): ✓ `atexit` runs
4. Context manager `with` block: ✓ `__exit__` runs
5. SIGKILL (kill -9): ✗ No cleanup (OS handles orphaned temp files)

### 4. Default Database Path Resolution

**Decision**: Use `~/.mixpanel_data/{project_id}.db` with automatic directory creation

**Rationale**:
- Follows Unix convention of dot-directories in home directory for app data
- Project ID in filename enables multi-project support
- Cross-platform: `Path.home()` works on Linux, macOS, Windows
- Automatic directory creation reduces friction

**Implementation Pattern**:
```python
from pathlib import Path

def resolve_default_path(project_id: str) -> Path:
    """Resolve default database path."""
    data_dir = Path.home() / '.mixpanel_data'
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir / f'{project_id}.db'
```

**Key Findings**:
- `Path.home()` returns:
  - Linux/macOS: `/home/user` or `/Users/user`
  - Windows: `C:\Users\user`
- `mkdir(parents=True, exist_ok=True)` creates intermediate directories and doesn't error if exists
- File permissions inherit from parent directory (user's home dir)

### 5. Table Schema Design

**Decision**: Fixed schemas for events/profiles with JSON column for flexible properties

**Rationale**:
- Core columns (event_name, distinct_id, timestamp) are always present and benefit from indexing
- JSON column accommodates Mixpanel's dynamic property schema
- Hybrid approach balances query performance and flexibility
- Avoids EAV (Entity-Attribute-Value) anti-pattern

**Schema Definitions**:

```sql
-- Events table
CREATE TABLE {table_name} (
    event_name VARCHAR NOT NULL,
    event_time TIMESTAMP NOT NULL,
    distinct_id VARCHAR NOT NULL,
    insert_id VARCHAR PRIMARY KEY,  -- Deduplication key
    properties JSON
);

-- Profiles table
CREATE TABLE {table_name} (
    distinct_id VARCHAR PRIMARY KEY,
    properties JSON,
    last_seen TIMESTAMP
);

-- Metadata table (internal)
CREATE TABLE _metadata (
    table_name VARCHAR PRIMARY KEY,
    type VARCHAR NOT NULL,  -- 'events' or 'profiles'
    fetched_at TIMESTAMP NOT NULL,
    from_date DATE,
    to_date DATE,
    row_count INTEGER NOT NULL
);
```

**Key Findings**:
- `insert_id` as PRIMARY KEY enables efficient deduplication
- JSON column type supports nested structures (though Mixpanel limits nesting)
- No indexes beyond primary keys initially (can add based on query patterns)
- VARCHAR without length limit (DuckDB uses variable-length encoding)

### 6. Query Error Wrapping

**Decision**: Catch `duckdb.Error` and wrap in `QueryError` with enhanced context

**Implementation Pattern**:
```python
from mixpanel_data.exceptions import QueryError

def execute_df(self, sql: str) -> pd.DataFrame:
    """Execute query and return DataFrame."""
    try:
        return self._conn.execute(sql).df()
    except duckdb.Error as e:
        raise QueryError(
            message=f"SQL query failed: {e}",
            details={
                "query": sql,
                "error_type": type(e).__name__,
                "original_error": str(e)
            }
        ) from e
```

**Key Findings**:
- DuckDB exceptions inherit from `duckdb.Error`
- Use `from e` to preserve original traceback
- Include query text in error details for debugging
- Handle syntax errors, constraint violations, and runtime errors uniformly

### 7. Context Manager Protocol

**Decision**: Implement `__enter__` and `__exit__` for automatic resource cleanup

**Implementation Pattern**:
```python
class StorageEngine:
    def __enter__(self) -> StorageEngine:
        """Context manager entry."""
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: Any | None
    ) -> None:
        """Context manager exit - close connection."""
        self.close()
```

**Key Findings**:
- Context manager ensures cleanup even if exceptions occur
- Particularly important for ephemeral databases
- `__exit__` receives exception info but doesn't suppress by default (return None)
- Enables `with StorageEngine.ephemeral() as storage:` pattern

## Open Questions Resolved

1. **Q: How to handle concurrent access to same database file?**
   **A**: Document as out of scope for MVP. DuckDB supports concurrent reads but has write limitations. Single-process use is primary use case. Future: advisory file locks or connection pooling.

2. **Q: What batch size for streaming ingestion?**
   **A**: Start with 1000 rows/batch based on DuckDB benchmarks. Make configurable if needed. Empirical testing during implementation will refine.

3. **Q: How to handle malformed data in iterator?**
   **A**: Validate each record before adding to batch. On error, raise descriptive exception indicating batch number and problematic record. Don't silently skip or auto-correct.

4. **Q: Should we create indexes on tables?**
   **A**: No automatic indexes beyond primary keys. Future enhancement: allow users to create indexes via raw SQL if needed. DuckDB's columnar storage provides good scan performance without indexes for analytics.

## Technology Stack Validation

✅ **DuckDB 1.0+**: Confirmed compatible with Python 3.10+, stable API
✅ **pandas 2.0+**: Native DuckDB integration via `.df()` method
✅ **Pydantic 2.0**: Used for TableMetadata validation (frozen=True for immutability)
✅ **pytest**: Standard testing framework, compatible with all chosen technologies
✅ **atexit module**: Python standard library, cross-platform

No additional dependencies required beyond project standards.
