# Implementation Plan: In-Memory Storage Mode (`:memory:`)

**Created**: 2024-12-24
**Status**: Draft
**Input**: Add true in-memory DuckDB mode as a complement to the existing ephemeral (temp-file) mode.

## Problem Statement

Currently, `mixpanel_data` supports two storage modes:

1. **Persistent**: Data stored in a file at a specified path (or default location)
2. **Ephemeral**: Data stored in a temp file that gets deleted on close

Both modes create files on disk. However, there are use cases where users want **zero disk footprint**:

- Privacy/security sensitive scenarios where data shouldn't touch disk
- Simple exploratory queries on small datasets
- Unit testing without filesystem side effects
- Quick ad-hoc analysis where startup overhead matters

DuckDB's `:memory:` mode provides exactly this capability—a true in-memory database with no file created on disk.

## Background: In-Memory vs Ephemeral

Research revealed an important distinction and a counter-intuitive finding:

| Aspect | Ephemeral (temp file) | In-Memory (`:memory:`) |
|--------|----------------------|------------------------|
| File on disk | Yes (in temp dir) | No |
| Compression | Yes (DuckDB default) | No |
| Performance (large data) | Better (8× faster on some workloads due to compression) | Worse |
| Disk footprint | Temp file exists during use | Zero until spill needed |
| Cleanup needed | Yes (file deletion) | No |
| Best for | Large datasets, typical analytics workloads | Small datasets, zero-footprint needs |

**Key insight**: The existing ephemeral mode is well-designed for the primary use case (analytics data). In-memory mode should be an *additional* option, not a replacement.

### Naming Convention

| Mode | Method | Semantic |
|------|--------|----------|
| Persistent | `StorageEngine(path=...)` | "I want data to persist after I'm done" |
| Ephemeral | `StorageEngine.ephemeral()` | "I want disk storage but don't want to keep the file" |
| In-Memory | `StorageEngine.memory()` | "I don't want any files created at all" |

## Proposed Solution

Add `memory()` classmethods to both `StorageEngine` and `Workspace` that create true in-memory DuckDB connections using `:memory:`.

### StorageEngine Changes

```python
# src/mixpanel_data/_internal/storage.py

class StorageEngine:
    def __init__(
        self,
        path: Path | None = None,
        *,
        _ephemeral: bool = False,
        _in_memory: bool = False,  # NEW
    ) -> None:
        """Initialize storage engine.

        Args:
            path: Path to database file. Required unless _in_memory=True.
            _ephemeral: Internal flag for ephemeral databases.
            _in_memory: Internal flag for in-memory databases.
        """
        self._is_in_memory = _in_memory  # NEW

        if _in_memory:
            # True in-memory mode - no file
            self._path = None
            self._conn = duckdb.connect(":memory:")
        elif path is not None:
            # Existing persistent/ephemeral logic
            ...
        else:
            raise ValueError(
                "Use StorageEngine.ephemeral() or StorageEngine.memory() "
                "for temporary databases"
            )

    @classmethod
    def memory(cls) -> StorageEngine:
        """Create true in-memory database with no disk footprint.

        The database exists only in RAM and is lost when closed.
        No files are created on disk (until DuckDB needs to spill
        for larger-than-memory operations).

        Best for:
        - Small datasets where zero disk footprint is required
        - Unit tests without filesystem side effects
        - Quick exploratory queries

        For large datasets, prefer ephemeral() which benefits from
        DuckDB's compression (can be 8× faster for large workloads).

        Returns:
            StorageEngine instance with in-memory database.

        Example:
            >>> with StorageEngine.memory() as storage:
            ...     storage.create_events_table("events", data, metadata)
            ...     df = storage.execute_df("SELECT * FROM events")
            # Database gone - no cleanup needed
        """
        return cls(path=None, _in_memory=True)

    @property
    def path(self) -> Path | None:
        """Path to the database file (None for in-memory databases)."""
        return self._path

    def close(self) -> None:
        """Close database connection and cleanup if ephemeral."""
        if self._is_in_memory:
            # Just close connection - nothing to clean up
            if self._conn is not None:
                self._conn.close()
                self._conn = None
        elif self._is_ephemeral:
            self._cleanup_ephemeral()
        else:
            # Persistent - just close connection
            if self._conn is not None:
                self._conn.close()
                self._conn = None
        self._closed = True
```

### Workspace Changes

```python
# src/mixpanel_data/workspace.py

class Workspace:
    @classmethod
    @contextmanager
    def memory(
        cls,
        account: str | None = None,
        project_id: str | None = None,
        region: str | None = None,
        _config_manager: ConfigManager | None = None,
        _api_client: MixpanelAPIClient | None = None,
    ) -> Iterator[Workspace]:
        """Create a workspace with true in-memory database.

        The database exists only in RAM with zero disk footprint.
        All data is lost when the context manager exits.

        Best for:
        - Small datasets where zero disk footprint is required
        - Unit tests without filesystem side effects
        - Quick exploratory queries

        For large datasets, prefer ephemeral() which benefits from
        DuckDB's compression (can be 8× faster for large workloads).

        Args:
            account: Named account from config file to use.
            project_id: Override project ID from credentials.
            region: Override region from credentials.
            _config_manager: Injected ConfigManager for testing.
            _api_client: Injected MixpanelAPIClient for testing.

        Yields:
            Workspace: A workspace with in-memory database.

        Example:
            >>> with Workspace.memory() as ws:
            ...     ws.fetch_events(from_date="2024-01-01", to_date="2024-01-01")
            ...     total = ws.sql_scalar("SELECT COUNT(*) FROM events")
            # Database gone - no cleanup needed, no files left behind
        """
        storage = StorageEngine.memory()
        ws = cls(
            account=account,
            project_id=project_id,
            region=region,
            _config_manager=_config_manager,
            _api_client=_api_client,
            _storage=storage,
        )
        try:
            yield ws
        finally:
            ws.close()
```

### WorkspaceInfo Changes

Update `WorkspaceInfo` to indicate in-memory mode:

```python
# src/mixpanel_data/types.py

@dataclass
class WorkspaceInfo:
    path: Path | None  # None for in-memory
    project_id: str
    region: str
    account: str | None
    tables: list[str]
    size_mb: float  # 0.0 for in-memory (can't measure RAM usage easily)
    created_at: datetime | None  # None for in-memory
```

The `Workspace.info()` method already handles `path=None`, but we should ensure `size_mb=0.0` and `created_at=None` are set appropriately for in-memory databases.

## Implementation Strategy

### Phase 1: StorageEngine.memory()

1. Add `_in_memory` parameter to `__init__`
2. Add `memory()` classmethod
3. Update `path` property to return `None` for in-memory
4. Update `close()` to handle in-memory mode
5. Update `connection` property error messages

### Phase 2: Workspace.memory()

1. Add `memory()` context manager classmethod
2. Update `info()` to handle in-memory databases gracefully

### Phase 3: Documentation

1. Update docstrings with guidance on when to use each mode
2. Add comparison table to docs

## Test Strategy

### Unit Tests (StorageEngine)

```python
# tests/unit/test_storage.py

class TestInMemoryMode:
    """Tests for in-memory database mode."""

    def test_memory_creates_in_memory_database(self) -> None:
        """Test that memory() creates a working in-memory database."""
        with StorageEngine.memory() as storage:
            # Should have valid connection
            assert storage.connection is not None
            # Path should be None
            assert storage.path is None
            # Should be able to create tables and query
            storage.connection.execute("CREATE TABLE test (id INTEGER)")
            storage.connection.execute("INSERT INTO test VALUES (1)")
            result = storage.connection.execute("SELECT * FROM test").fetchone()
            assert result == (1,)

    def test_memory_returns_storage_engine_instance(self) -> None:
        """Test that memory() returns StorageEngine."""
        with StorageEngine.memory() as storage:
            assert isinstance(storage, StorageEngine)

    def test_memory_creates_unique_databases(self) -> None:
        """Test that each memory() call creates independent database."""
        with StorageEngine.memory() as s1, StorageEngine.memory() as s2:
            s1.connection.execute("CREATE TABLE test (id INTEGER)")
            s1.connection.execute("INSERT INTO test VALUES (1)")
            # s2 should not see s1's table
            tables = s2.connection.execute(
                "SELECT COUNT(*) FROM information_schema.tables WHERE table_name = 'test'"
            ).fetchone()
            assert tables == (0,)

    def test_memory_supports_events_table_creation(self) -> None:
        """Test that events can be stored in memory database."""
        from datetime import datetime, UTC
        from mixpanel_data.types import TableMetadata

        with StorageEngine.memory() as storage:
            events = [{
                "event_name": "Test",
                "event_time": datetime.now(UTC),
                "distinct_id": "user_1",
                "insert_id": "event_1",
                "properties": {"key": "value"},
            }]
            metadata = TableMetadata(type="events", fetched_at=datetime.now(UTC))

            row_count = storage.create_events_table("events", iter(events), metadata)
            assert row_count == 1

            result = storage.execute_scalar("SELECT COUNT(*) FROM events")
            assert result == 1

    def test_memory_close_is_idempotent(self) -> None:
        """Test that close() can be called multiple times safely."""
        storage = StorageEngine.memory()
        storage.close()
        storage.close()  # Should not raise
        storage.close()

    def test_memory_context_manager_cleanup(self) -> None:
        """Test context manager properly closes connection."""
        storage_ref = None
        with StorageEngine.memory() as storage:
            storage_ref = storage
            assert storage.connection is not None

        # After exit, attempting to use connection should fail
        with pytest.raises(RuntimeError):
            _ = storage_ref.connection

    def test_memory_no_path_property(self) -> None:
        """Test that path is None for memory databases."""
        with StorageEngine.memory() as storage:
            assert storage.path is None

    def test_memory_introspection_works(self) -> None:
        """Test that list_tables, get_schema work on memory DB."""
        from datetime import datetime, UTC
        from mixpanel_data.types import TableMetadata

        with StorageEngine.memory() as storage:
            # Initially empty
            assert storage.list_tables() == []

            # Create table
            events = [{
                "event_name": "Test",
                "event_time": datetime.now(UTC),
                "distinct_id": "user_1",
                "insert_id": "event_1",
                "properties": {},
            }]
            metadata = TableMetadata(type="events", fetched_at=datetime.now(UTC))
            storage.create_events_table("my_events", iter(events), metadata)

            # Introspection should work
            tables = storage.list_tables()
            assert len(tables) == 1
            assert tables[0].name == "my_events"

            schema = storage.get_schema("my_events")
            assert schema.table_name == "my_events"
```

### Unit Tests (Workspace)

```python
# tests/unit/test_workspace.py

class TestMemoryWorkspace:
    """Tests for in-memory workspaces."""

    def test_memory_creates_in_memory_storage(
        self,
        mock_config_manager: MagicMock,
        mock_api_client: MagicMock,
    ) -> None:
        """Test memory() creates workspace with in-memory storage."""
        with Workspace.memory(
            _config_manager=mock_config_manager,
            _api_client=mock_api_client,
        ) as ws:
            assert ws._storage._is_in_memory is True
            assert ws._storage.path is None

    def test_memory_info_reflects_in_memory(
        self,
        mock_config_manager: MagicMock,
        mock_api_client: MagicMock,
    ) -> None:
        """Test info() returns appropriate values for memory workspace."""
        with Workspace.memory(
            _config_manager=mock_config_manager,
            _api_client=mock_api_client,
        ) as ws:
            info = ws.info()
            assert info.path is None
            assert info.size_mb == 0.0

    def test_memory_sql_operations_work(
        self,
        mock_config_manager: MagicMock,
        mock_api_client: MagicMock,
    ) -> None:
        """Test SQL operations work on memory workspace."""
        with Workspace.memory(
            _config_manager=mock_config_manager,
            _api_client=mock_api_client,
        ) as ws:
            # Direct SQL should work
            ws.connection.execute("CREATE TABLE test (id INTEGER)")
            ws.connection.execute("INSERT INTO test VALUES (1)")

            result = ws.sql_scalar("SELECT COUNT(*) FROM test")
            assert result == 1
```

### Integration Tests

```python
# tests/integration/test_storage_integration.py

class TestInMemoryIntegration:
    """Integration tests for in-memory storage."""

    def test_memory_full_workflow(self) -> None:
        """Test complete workflow with in-memory storage."""
        from datetime import datetime, UTC
        from mixpanel_data.types import TableMetadata

        with StorageEngine.memory() as storage:
            # Create multiple tables
            events = [{
                "event_name": f"Event_{i}",
                "event_time": datetime.now(UTC),
                "distinct_id": f"user_{i}",
                "insert_id": f"event_{i}",
                "properties": {"index": i},
            } for i in range(100)]

            profiles = [{
                "distinct_id": f"user_{i}",
                "properties": {"name": f"User {i}"},
                "last_seen": datetime.now(UTC),
            } for i in range(50)]

            events_meta = TableMetadata(type="events", fetched_at=datetime.now(UTC))
            profiles_meta = TableMetadata(type="profiles", fetched_at=datetime.now(UTC))

            storage.create_events_table("events", iter(events), events_meta)
            storage.create_profiles_table("profiles", iter(profiles), profiles_meta)

            # Query
            event_count = storage.execute_scalar("SELECT COUNT(*) FROM events")
            profile_count = storage.execute_scalar("SELECT COUNT(*) FROM profiles")

            assert event_count == 100
            assert profile_count == 50

            # Join query
            df = storage.execute_df("""
                SELECT e.event_name, p.properties->>'$.name' as user_name
                FROM events e
                JOIN profiles p ON e.distinct_id = p.distinct_id
                LIMIT 5
            """)
            assert len(df) == 5
```

## Files to Modify

1. `src/mixpanel_data/_internal/storage.py`
   - Add `_in_memory` parameter to `__init__`
   - Add `memory()` classmethod
   - Update `close()` method
   - Update `path` property docstring

2. `src/mixpanel_data/workspace.py`
   - Add `memory()` context manager classmethod
   - Update `info()` to handle in-memory gracefully

3. `tests/unit/test_storage.py`
   - Add `TestInMemoryMode` test class

4. `tests/unit/test_workspace.py`
   - Add `TestMemoryWorkspace` test class

5. `tests/integration/test_storage_integration.py`
   - Add `TestInMemoryIntegration` test class

6. Documentation files (if updating docs)
   - `docs/guide/fetching.md` - add section on storage modes
   - `docs/api/workspace.md` - document `Workspace.memory()`

## Risk Assessment

**Low Risk**:
- Adding a new classmethod doesn't change existing behavior
- In-memory mode is a well-established DuckDB feature
- Clear separation from existing ephemeral mode

**Considerations**:
- Users might misuse in-memory mode for large datasets (document performance tradeoffs)
- `path=None` needs to be handled gracefully in all code paths

## Success Criteria

1. `StorageEngine.memory()` creates working in-memory database
2. `Workspace.memory()` provides full Workspace functionality
3. All existing tests continue to pass
4. New tests cover in-memory mode comprehensively
5. Documentation clearly explains when to use each mode
6. `just check` passes (lint, typecheck, test)

## Out of Scope

- CLI support for in-memory mode (doesn't make sense for CLI - data lost on exit)
- Memory usage reporting (DuckDB doesn't expose this easily)
- Configuration of DuckDB memory limits (leave to defaults)
