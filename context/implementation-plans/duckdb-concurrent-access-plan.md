# Implementation Plan: DuckDB Concurrent Access Handling

**Created**: 2025-12-26
**Status**: Draft
**Input**: [duckdb-lock-conflict-findings.md](../research/duckdb-lock-conflict-findings.md)

## Problem Statement

When multiple `mp` CLI processes run concurrently against the same Mixpanel project, the second process crashes with a DuckDB lock error:

```
IOException: IO Error: Could not set lock on file "/home/vscode/.mp/data/3409416.db":
Conflicting lock is held in /usr/local/bin/python3.11 (PID 66618).
```

This occurs because:
1. DuckDB uses a single-writer, multiple-reader concurrency model
2. `Workspace.__init__` eagerly opens the database with write access (`read_only=False`)
3. This happens for **all** CLI commands, even those that don't need storage

This is especially problematic for:
- AI agents running concurrent analysis tasks
- Human + agent working simultaneously
- Multiple terminal sessions

## Solution Overview

A 3-phase approach that progressively reduces lock contention:

| Phase | Description | Impact |
|-------|-------------|--------|
| 1 | Graceful error message | Better UX when conflicts occur |
| 2 | Lazy storage initialization | API-only commands don't touch database |
| 3 | Read-only mode for reads | Concurrent read operations supported |

---

## Command Classification

Understanding which commands need what level of database access:

### API-Only (No Storage Required)

These commands only call the Mixpanel API and should never touch the database:

| Command Group | Commands |
|---------------|----------|
| `inspect` | `events`, `properties`, `values`, `funnels`, `cohorts`, `top-events`, `bookmarks`, `lexicon-schemas`, `lexicon-schema` |
| `query` | `segmentation`, `funnel`, `retention`, `jql`, `event-counts`, `property-counts`, `activity-feed`, `saved-report`, `flows`, `frequency`, `segmentation-numeric`, `segmentation-sum`, `segmentation-average` |
| `auth` | `login`, `logout`, `status`, `list` |

**Count**: 26 commands (majority of CLI surface area)

### Storage Read-Only

These commands read from the local database but never write:

| Command | Method Called |
|---------|---------------|
| `inspect info` | `workspace.info()` |
| `inspect tables` | `workspace.tables()` |
| `inspect schema` | `workspace.table_schema()` |
| `inspect sample` | `workspace.sample()` |
| `inspect describe` | `workspace.summarize()` |
| `inspect event-breakdown` | `workspace.event_breakdown()` |
| `inspect property-keys` | `workspace.property_keys()` |
| `inspect column` | `workspace.column_stats()` |
| `query sql` | `workspace.sql_scalar()` / `workspace.sql_rows()` (mostly reads) |

**Count**: 9 commands

### Storage Write

These commands modify the database:

| Command | Method Called |
|---------|---------------|
| `fetch events` | `workspace.fetch_events()`, `workspace.drop()` |
| `fetch profiles` | `workspace.fetch_profiles()`, `workspace.drop()` |
| `inspect drop` | `workspace.drop()` |

**Count**: 3 commands

---

## Phase 1: Graceful Error Message

**Goal**: When a lock conflict occurs, show a clear, actionable error instead of a traceback.

### New Exception: `DatabaseLockedError`

```python
# In exceptions.py
class DatabaseLockedError(MixpanelDataError):
    """Database is locked by another process.

    Raised when attempting to access a DuckDB database that is locked
    by another process. DuckDB uses single-writer, multiple-reader
    concurrency - only one process can have write access at a time.
    """

    def __init__(
        self,
        db_path: str,
        holding_pid: int | None = None,
    ) -> None:
        self._db_path = db_path
        self._holding_pid = holding_pid

        message = f"Database '{db_path}' is locked by another process"
        if holding_pid:
            message += f" (PID {holding_pid})"
        message += ". Wait for the other operation to complete and try again."

        details = {"db_path": db_path}
        if holding_pid:
            details["holding_pid"] = holding_pid

        super().__init__(message, code="DATABASE_LOCKED", details=details)
```

### StorageEngine Changes

```python
# In storage.py __init__
try:
    self._conn = duckdb.connect(database=str(path), read_only=False)
except duckdb.IOException as e:
    error_str = str(e)
    if "Could not set lock" in error_str:
        # Extract PID if available
        import re
        pid_match = re.search(r"PID (\d+)", error_str)
        holding_pid = int(pid_match.group(1)) if pid_match else None
        raise DatabaseLockedError(str(path), holding_pid) from None
    raise OSError(f"Failed to create database at {path}: {e}") from e
```

### CLI Error Handler

```python
# In cli/utils.py handle_errors decorator
except DatabaseLockedError as e:
    err_console.print(f"[yellow]Database locked:[/yellow] {e.message}")
    err_console.print("Hint: Another mp command may be running. Try again shortly.")
    raise typer.Exit(ExitCode.GENERAL_ERROR) from None
```

### TDD: Test Cases for Phase 1

**File**: `tests/unit/test_storage.py`

```python
class TestDatabaseLocking:
    """Tests for database lock conflict handling."""

    def test_lock_conflict_raises_database_locked_error(self, tmp_path: Path) -> None:
        """Opening locked database raises DatabaseLockedError."""
        db_path = tmp_path / "test.db"

        # Open first connection (holds lock)
        storage1 = StorageEngine(path=db_path)

        # Second connection should raise DatabaseLockedError
        with pytest.raises(DatabaseLockedError) as exc_info:
            StorageEngine(path=db_path)

        assert str(db_path) in str(exc_info.value.message)
        storage1.close()

    def test_database_locked_error_includes_path(self, tmp_path: Path) -> None:
        """DatabaseLockedError includes the database path."""
        error = DatabaseLockedError("/path/to/db.duckdb", holding_pid=12345)
        assert "/path/to/db.duckdb" in error.message
        assert error.details["db_path"] == "/path/to/db.duckdb"

    def test_database_locked_error_includes_pid_if_available(self) -> None:
        """DatabaseLockedError includes holding PID when available."""
        error = DatabaseLockedError("/path/to/db.duckdb", holding_pid=12345)
        assert "PID 12345" in error.message
        assert error.details["holding_pid"] == 12345

    def test_database_locked_error_works_without_pid(self) -> None:
        """DatabaseLockedError works when PID is not available."""
        error = DatabaseLockedError("/path/to/db.duckdb")
        assert "locked by another process" in error.message
        assert "holding_pid" not in error.details
```

**File**: `tests/integration/cli/test_error_handling.py`

```python
class TestDatabaseLockedCLI:
    """CLI error handling for database lock conflicts."""

    def test_locked_database_shows_friendly_message(
        self, cli_runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """CLI shows user-friendly message for database lock."""
        # Mock get_workspace to raise DatabaseLockedError
        from mixpanel_data.exceptions import DatabaseLockedError

        def mock_get_workspace(ctx):
            raise DatabaseLockedError("/path/to/db.duckdb", holding_pid=12345)

        with patch("mixpanel_data.cli.commands.inspect.get_workspace", mock_get_workspace):
            result = cli_runner.invoke(app, ["inspect", "tables"])

        assert result.exit_code != 0
        assert "locked" in result.stderr.lower()
        assert "try again" in result.stderr.lower()
        # Should NOT have full traceback
        assert "Traceback" not in result.stdout
```

### Files to Modify (Phase 1)

| File | Changes |
|------|---------|
| `src/mixpanel_data/exceptions.py` | Add `DatabaseLockedError` class |
| `src/mixpanel_data/__init__.py` | Export `DatabaseLockedError` |
| `src/mixpanel_data/_internal/storage.py` | Catch `duckdb.IOException` and convert to `DatabaseLockedError` |
| `src/mixpanel_data/cli/utils.py` | Add `DatabaseLockedError` handler in `handle_errors` |
| `tests/unit/test_exceptions.py` | Add tests for `DatabaseLockedError` |
| `tests/unit/test_storage.py` | Add lock conflict tests |
| `tests/integration/cli/test_error_handling.py` | Add CLI error handling tests |

---

## Phase 2: Lazy Storage Initialization

**Goal**: Only connect to the database when storage is actually needed. API-only commands should never touch the database.

### Design Approach

1. Store database path instead of opening connection immediately
2. Create `storage` property that lazily initializes `StorageEngine`
3. Track whether storage has been accessed

```python
class Workspace:
    def __init__(self, ...):
        # ... credentials resolution ...

        # Store path but don't connect yet
        self._db_path: Path | None = None
        self._storage: StorageEngine | None = None

        if _storage is not None:
            # Injected for testing - use directly
            self._storage = _storage
        elif path is not None:
            self._db_path = Path(path) if isinstance(path, str) else path
        else:
            self._db_path = Path.home() / ".mp" / "data" / f"{self._credentials.project_id}.db"

    @property
    def storage(self) -> StorageEngine:
        """Lazily initialize storage connection.

        Only connects to database when first accessed.

        Returns:
            StorageEngine instance.

        Raises:
            DatabaseLockedError: If database is locked by another process.
        """
        if self._storage is None:
            if self._db_path is None:
                raise RuntimeError("No database path configured")
            self._storage = StorageEngine(path=self._db_path)
        return self._storage
```

### Internal Access Pattern

Update all internal `self._storage` references to use the property:

```python
# Before (eager access)
def sample(self, table: str, n: int = 10) -> pd.DataFrame:
    self._storage.get_schema(table)  # Direct access
    return self._storage.execute_df(...)

# After (lazy access)
def sample(self, table: str, n: int = 10) -> pd.DataFrame:
    self.storage.get_schema(table)  # Via property
    return self.storage.execute_df(...)
```

### Methods That Need Storage

These methods access storage and need to use `self.storage`:

| Category | Methods |
|----------|---------|
| Fetch | `fetch_events()`, `fetch_profiles()` |
| Query | `sql()`, `sql_df()`, `sql_scalar()`, `sql_rows()` |
| Introspection | `tables()`, `table_schema()`, `sample()`, `summarize()`, `event_breakdown()`, `property_keys()`, `column_stats()` |
| Management | `drop()`, `drop_all()`, `info()` |
| Internal | `_fetcher` (uses storage in FetcherService) |

### Methods That DON'T Need Storage

These methods only use API and should NOT trigger storage initialization:

| Category | Methods |
|----------|---------|
| Discovery | `events()`, `properties()`, `property_values()`, `funnels()`, `cohorts()`, `top_events()`, `list_bookmarks()`, `lexicon_schemas()`, `lexicon_schema()` |
| Live Query | `segmentation()`, `funnel()`, `retention()`, `jql()`, `event_counts()`, `property_counts()`, `activity_feed()`, `query_saved_report()`, `query_flows()`, `frequency()`, `segmentation_numeric()`, `segmentation_sum()`, `segmentation_average()` |
| Streaming | `stream_events()`, `stream_profiles()` |

### TDD: Test Cases for Phase 2

**File**: `tests/unit/test_workspace.py`

```python
class TestLazyStorageInitialization:
    """Tests for lazy storage initialization."""

    def test_api_only_method_does_not_initialize_storage(
        self, mock_config_manager: MagicMock
    ) -> None:
        """Calling API-only methods should not create storage connection."""
        with patch.object(StorageEngine, "__init__", return_value=None) as mock_init:
            ws = Workspace(_config_manager=mock_config_manager)
            # Mock the API client
            ws._api_client = MagicMock()
            ws._discovery = MagicMock()
            ws._discovery.events.return_value = ["Event1", "Event2"]

            # Call API-only method
            result = ws.events()

            # Storage should NOT have been initialized
            mock_init.assert_not_called()
            assert result == ["Event1", "Event2"]

    def test_storage_method_initializes_storage_on_first_access(
        self, tmp_path: Path, mock_config_manager: MagicMock
    ) -> None:
        """Calling storage method should initialize storage lazily."""
        ws = Workspace(path=tmp_path / "test.db", _config_manager=mock_config_manager)

        # Storage should not exist yet
        assert ws._storage is None

        # Access storage via property
        storage = ws.storage

        # Now storage should exist
        assert ws._storage is not None
        assert storage is ws._storage

    def test_storage_property_returns_same_instance(
        self, tmp_path: Path, mock_config_manager: MagicMock
    ) -> None:
        """Storage property should return same instance on repeated access."""
        ws = Workspace(path=tmp_path / "test.db", _config_manager=mock_config_manager)

        storage1 = ws.storage
        storage2 = ws.storage

        assert storage1 is storage2

    def test_multiple_api_calls_never_touch_storage(
        self, mock_config_manager: MagicMock
    ) -> None:
        """Multiple API-only calls should never initialize storage."""
        ws = Workspace(_config_manager=mock_config_manager)
        ws._api_client = MagicMock()
        ws._discovery = MagicMock()
        ws._live_query = MagicMock()

        # Call multiple API-only methods
        ws.events()
        ws.properties("event")
        ws.funnels()
        ws.cohorts()

        # Storage should still be None
        assert ws._storage is None
```

**File**: `tests/integration/test_lazy_storage.py`

```python
class TestLazyStorageIntegration:
    """Integration tests for lazy storage initialization."""

    def test_concurrent_api_calls_dont_conflict(self) -> None:
        """Two processes making API-only calls should not conflict."""
        # This test verifies the fix works end-to-end
        import subprocess
        import concurrent.futures

        def run_api_command():
            result = subprocess.run(
                ["uv", "run", "mp", "inspect", "events", "--format", "json"],
                capture_output=True,
                text=True,
                timeout=60,
            )
            return result.returncode

        # Run two API commands concurrently
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            futures = [executor.submit(run_api_command) for _ in range(2)]
            results = [f.result() for f in futures]

        # Both should succeed (or fail for auth reasons, not lock)
        # The key is neither should fail with DatabaseLockedError
        for result in results:
            assert result in [0, 2]  # 0=success, 2=auth error (no creds in CI)
```

### Files to Modify (Phase 2)

| File | Changes |
|------|---------|
| `src/mixpanel_data/workspace.py` | Add `storage` property, change `_storage` to lazy |
| `tests/unit/test_workspace.py` | Add lazy initialization tests |
| `tests/integration/test_lazy_storage.py` | Add concurrent access tests |

---

## Phase 3: Read-Only Mode for Read Operations

**Goal**: Commands that only read from the database should open with `read_only=True`, allowing concurrent reads.

### StorageEngine Changes

Add a `read_only` parameter:

```python
class StorageEngine:
    def __init__(
        self,
        path: Path | None = None,
        *,
        read_only: bool = False,  # NEW
        _ephemeral: bool = False,
        _in_memory: bool = False,
    ) -> None:
        self._read_only = read_only
        # ...

        if path is not None:
            try:
                self._conn = duckdb.connect(
                    database=str(path),
                    read_only=read_only,  # Use parameter
                )
            except duckdb.IOException as e:
                # ... lock error handling ...
```

### Workspace Changes

Add separate accessors for read-only vs read-write:

```python
class Workspace:
    @property
    def storage(self) -> StorageEngine:
        """Get read-write storage connection (for writes)."""
        if self._storage is None:
            self._storage = StorageEngine(path=self._db_path, read_only=False)
        return self._storage

    @property
    def storage_readonly(self) -> StorageEngine:
        """Get read-only storage connection (for concurrent reads)."""
        if self._storage_readonly is None:
            self._storage_readonly = StorageEngine(path=self._db_path, read_only=True)
        return self._storage_readonly
```

Alternatively, use a smarter approach where we track what access level we need:

```python
class Workspace:
    def _get_storage(self, write: bool = False) -> StorageEngine:
        """Get storage with appropriate access level.

        Args:
            write: If True, request write access. If False, read-only is sufficient.
        """
        if write:
            # Need write access - use/create write connection
            if self._storage is None:
                self._storage = StorageEngine(path=self._db_path, read_only=False)
            return self._storage
        else:
            # Read-only is sufficient
            # Prefer existing write connection if available (already locked)
            # Otherwise create read-only connection
            if self._storage is not None:
                return self._storage
            if self._storage_readonly is None:
                self._storage_readonly = StorageEngine(path=self._db_path, read_only=True)
            return self._storage_readonly
```

### Method Updates

Update methods to indicate their access level:

```python
# Read-only methods
def sample(self, table: str, n: int = 10) -> pd.DataFrame:
    return self._get_storage(write=False).execute_df(...)

def tables(self) -> list[TableInfo]:
    return self._get_storage(write=False).list_tables()

# Write methods
def drop(self, table: str) -> None:
    self._get_storage(write=True).drop_table(table)

def fetch_events(self, ...) -> FetchResult:
    # Uses write access via FetcherService
    ...
```

### TDD: Test Cases for Phase 3

**File**: `tests/unit/test_storage.py`

```python
class TestReadOnlyMode:
    """Tests for read-only storage mode."""

    def test_read_only_connection_allows_reads(self, tmp_path: Path) -> None:
        """Read-only connection can execute SELECT queries."""
        db_path = tmp_path / "test.db"

        # Create database with some data
        with StorageEngine(path=db_path) as storage:
            storage.connection.execute("CREATE TABLE test (id INT)")
            storage.connection.execute("INSERT INTO test VALUES (1), (2), (3)")

        # Open read-only and verify reads work
        with StorageEngine(path=db_path, read_only=True) as storage:
            result = storage.execute_scalar("SELECT COUNT(*) FROM test")
            assert result == 3

    def test_read_only_connection_blocks_writes(self, tmp_path: Path) -> None:
        """Read-only connection raises error on write attempts."""
        db_path = tmp_path / "test.db"

        # Create database
        with StorageEngine(path=db_path) as storage:
            storage.connection.execute("CREATE TABLE test (id INT)")

        # Open read-only and verify writes fail
        with StorageEngine(path=db_path, read_only=True) as storage:
            with pytest.raises(duckdb.InvalidInputException):
                storage.connection.execute("INSERT INTO test VALUES (1)")

    def test_concurrent_read_only_connections(self, tmp_path: Path) -> None:
        """Multiple read-only connections can coexist."""
        db_path = tmp_path / "test.db"

        # Create database
        with StorageEngine(path=db_path) as storage:
            storage.connection.execute("CREATE TABLE test (id INT)")
            storage.connection.execute("INSERT INTO test VALUES (1)")

        # Open multiple read-only connections
        storage1 = StorageEngine(path=db_path, read_only=True)
        storage2 = StorageEngine(path=db_path, read_only=True)

        # Both should work
        assert storage1.execute_scalar("SELECT COUNT(*) FROM test") == 1
        assert storage2.execute_scalar("SELECT COUNT(*) FROM test") == 1

        storage1.close()
        storage2.close()

    def test_read_only_with_existing_write_lock_succeeds(self, tmp_path: Path) -> None:
        """Read-only connection works even when write lock is held."""
        db_path = tmp_path / "test.db"

        # Hold write lock
        writer = StorageEngine(path=db_path)
        writer.connection.execute("CREATE TABLE test (id INT)")

        # Read-only should still work
        reader = StorageEngine(path=db_path, read_only=True)
        result = reader.execute_rows("SELECT name FROM sqlite_master WHERE type='table'")
        assert len(result) > 0

        reader.close()
        writer.close()
```

**File**: `tests/unit/test_workspace.py`

```python
class TestStorageAccessLevels:
    """Tests for appropriate storage access levels."""

    def test_sample_uses_read_only_storage(
        self, tmp_path: Path, mock_config_manager: MagicMock
    ) -> None:
        """sample() should use read-only storage access."""
        ws = Workspace(path=tmp_path / "test.db", _config_manager=mock_config_manager)

        # Create a table first
        ws.storage.connection.execute("CREATE TABLE test (id INT)")

        # Now sample should use read-only
        # (Implementation detail: verify _storage_readonly is used)
        ws.sample("test")

        # Write storage should NOT have been used for the read
        # This tests the optimization is working

    def test_drop_uses_write_storage(
        self, tmp_path: Path, mock_config_manager: MagicMock
    ) -> None:
        """drop() should use write storage access."""
        ws = Workspace(path=tmp_path / "test.db", _config_manager=mock_config_manager)

        # Create a table
        ws.storage.connection.execute("CREATE TABLE test (id INT)")

        # Drop requires write access
        ws.drop("test")

        # Verify table is gone
        assert not ws.storage.table_exists("test")
```

### Files to Modify (Phase 3)

| File | Changes |
|------|---------|
| `src/mixpanel_data/_internal/storage.py` | Add `read_only` parameter to `__init__` |
| `src/mixpanel_data/workspace.py` | Add `_get_storage(write: bool)` helper, update methods |
| `tests/unit/test_storage.py` | Add read-only mode tests |
| `tests/unit/test_workspace.py` | Add access level tests |
| `tests/integration/test_concurrent_reads.py` | Add concurrent read tests |

---

## Implementation Order

Following TDD principles, implement in this order:

### Phase 1: Graceful Error Message (1-2 hours)

1. **Write tests first**:
   - `tests/unit/test_exceptions.py` - `DatabaseLockedError` tests
   - `tests/unit/test_storage.py` - Lock conflict detection tests
   - `tests/integration/cli/test_error_handling.py` - CLI error message tests

2. **Implement**:
   - Add `DatabaseLockedError` to `exceptions.py`
   - Update `StorageEngine.__init__` to catch and convert lock errors
   - Add handler in `cli/utils.py`

3. **Verify**: `just check` passes

### Phase 2: Lazy Storage Initialization (2-3 hours)

1. **Write tests first**:
   - `tests/unit/test_workspace.py` - Lazy initialization tests
   - Verify API-only methods don't trigger storage

2. **Implement**:
   - Add `storage` property to `Workspace`
   - Store path without connecting
   - Update all `self._storage` to `self.storage`

3. **Verify**: `just check` passes

### Phase 3: Read-Only Mode (2-3 hours)

1. **Write tests first**:
   - `tests/unit/test_storage.py` - Read-only mode tests
   - `tests/unit/test_workspace.py` - Access level tests
   - `tests/integration/test_concurrent_reads.py` - Concurrent read tests

2. **Implement**:
   - Add `read_only` parameter to `StorageEngine`
   - Add `_get_storage(write: bool)` to `Workspace`
   - Update methods to use appropriate access level

3. **Verify**: `just check` passes

---

## Test-First Development Checklist

For each phase, follow this TDD workflow:

1. **RED**: Write failing tests that describe expected behavior
2. **GREEN**: Implement minimum code to make tests pass
3. **REFACTOR**: Clean up while keeping tests green

### Before Writing Any Test

- [ ] Read existing tests in the same file to understand patterns
- [ ] Copy fixture and mocking approaches exactly
- [ ] Use same naming conventions

### Before Marking Phase Complete

- [ ] All new tests pass
- [ ] All existing tests still pass (`just test`)
- [ ] Type checking passes (`just typecheck`)
- [ ] Linting passes (`just lint`)
- [ ] Full check suite passes (`just check`)

---

## Success Criteria

### Phase 1 Complete When

- [ ] `DatabaseLockedError` exception exists with proper attributes
- [ ] Lock conflicts raise `DatabaseLockedError` (not `OSError`)
- [ ] CLI shows friendly message without traceback
- [ ] All tests pass

### Phase 2 Complete When

- [ ] `mp inspect bookmarks` runs without touching database
- [ ] Two concurrent `mp inspect bookmarks` commands don't conflict
- [ ] Storage is only created when actually needed
- [ ] All existing tests still pass

### Phase 3 Complete When

- [ ] `mp inspect tables` can run while `mp fetch events` is running
- [ ] Multiple `mp query sql` commands can run concurrently (for SELECTs)
- [ ] Write operations still get exclusive access
- [ ] All tests pass

---

## Risks and Mitigations

| Risk | Mitigation |
|------|------------|
| Breaking existing tests | Run full test suite after each change |
| Changing too much at once | Implement in small, tested increments |
| Missing a storage access point | Grep for `_storage` and audit each usage |
| Read-only mode limitations | Document that `query sql` with writes needs exclusive access |

---

## References

- [DuckDB Concurrency Documentation](https://duckdb.org/docs/stable/connect/concurrency)
- [Research Findings](../research/duckdb-lock-conflict-findings.md)
- [CLAUDE.md TDD Guidelines](../../CLAUDE.md)
