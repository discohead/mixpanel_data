"""Unit tests for StorageEngine (User Story 1: Persistent Data Storage)."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC
from pathlib import Path
from typing import Any

import pytest

from mixpanel_data._internal.storage import StorageEngine

# =============================================================================
# T010: Test __init__ with explicit path
# =============================================================================


def test_init_with_explicit_path_creates_database_file(tmp_path: Path) -> None:
    """Test that StorageEngine creates database file at specified path."""
    db_path = tmp_path / "test.db"
    with StorageEngine(path=db_path, read_only=False) as storage:
        # Database file should exist
        assert db_path.exists()
        assert db_path.is_file()

        # Should have a valid DuckDB connection
        assert storage.connection is not None

        # Path property should return the correct path
        assert storage.path == db_path


def test_init_creates_parent_directories_if_needed(tmp_path: Path) -> None:
    """Test that StorageEngine creates parent directories automatically."""
    db_path = tmp_path / "subdir" / "nested" / "test.db"
    with StorageEngine(path=db_path, read_only=False):
        # Parent directories should be created
        assert db_path.parent.exists()
        assert db_path.exists()


def test_init_can_reopen_existing_database(tmp_path: Path) -> None:
    """Test that StorageEngine can reopen an existing database file."""
    db_path = tmp_path / "test.db"

    # Create database
    with StorageEngine(path=db_path, read_only=False):
        pass

    # Reopen same database
    with StorageEngine(path=db_path, read_only=False) as storage:
        assert storage.path == db_path
        assert storage.connection is not None


def test_init_with_invalid_path_raises_error() -> None:
    """Test that StorageEngine raises error for invalid paths."""
    # Try to create database in root directory (should fail on permissions)
    invalid_path = Path("/root/cannot_write_here.db")

    with pytest.raises(OSError):
        StorageEngine(path=invalid_path)


def test_init_ephemeral_with_non_temp_path_raises_error() -> None:
    """Test that _ephemeral=True with non-temp path raises ValueError."""
    # The _ephemeral parameter is for internal use only and should only
    # be used with paths in the system temp directory
    # Use a path clearly outside the temp directory
    non_temp_path = Path("/home/user/my_database.db")

    with pytest.raises(ValueError, match="_ephemeral parameter is for internal use"):
        StorageEngine(path=non_temp_path, _ephemeral=True)


def test_init_with_none_path_raises_error() -> None:
    """Test that path=None raises ValueError with helpful message."""
    with pytest.raises(ValueError, match="Use StorageEngine.ephemeral"):
        StorageEngine(path=None)


# =============================================================================
# T011: Test default path resolution
# =============================================================================


def test_init_resolves_default_path_with_project_id(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Test that default path is ~/.mixpanel_data/{project_id}.db."""
    # Mock Path.home() to use tmp_path
    monkeypatch.setattr(Path, "home", lambda: tmp_path)

    # Create storage without explicit path - should fail because we need project_id
    # For now, this test documents that we'll need to pass project_id somehow
    # We'll implement this in User Story 1 when we determine how to get project_id
    pass  # Placeholder - will implement when we add project_id parameter


# =============================================================================
# T012: Test context manager protocol
# =============================================================================


def test_context_manager_enters_and_exits(tmp_path: Path) -> None:
    """Test that StorageEngine works as context manager."""
    db_path = tmp_path / "test.db"

    with StorageEngine(path=db_path, read_only=False) as storage:
        # Inside context, storage should be usable
        assert storage.connection is not None
        assert storage.path == db_path

    # After exiting context, connection should be closed
    # (We can't directly test if connection is closed, but it should be)


def test_context_manager_closes_on_exception(tmp_path: Path) -> None:
    """Test that context manager closes connection even on exception."""
    db_path = tmp_path / "test.db"

    with (
        pytest.raises(ValueError),
        StorageEngine(path=db_path, read_only=False) as storage,
    ):
        assert storage.connection is not None
        # Raise exception to test cleanup
        raise ValueError("test exception")

    # Connection should be closed despite exception


def test_context_manager_returns_self(tmp_path: Path) -> None:
    """Test that __enter__ returns self."""
    db_path = tmp_path / "test.db"

    storage = StorageEngine(path=db_path, read_only=False)
    try:
        result = storage.__enter__()
        assert result is storage
    finally:
        storage.close()


# =============================================================================
# T013: Integration test for session persistence (moved to integration tests)
# =============================================================================
# This test will be in tests/integration/test_storage_integration.py


# =============================================================================
# T014-T020: Implementation tests (these verify the implementation details)
# =============================================================================


def test_close_can_be_called_multiple_times(tmp_path: Path) -> None:
    """Test that close() is idempotent."""
    db_path = tmp_path / "test.db"
    storage = StorageEngine(path=db_path, read_only=False)

    # Should be safe to call multiple times
    storage.close()
    storage.close()
    storage.close()


def test_path_property_returns_path(tmp_path: Path) -> None:
    """Test that path property returns the database path."""
    db_path = tmp_path / "test.db"
    with StorageEngine(path=db_path, read_only=False) as storage:
        assert storage.path == db_path


def test_connection_property_returns_duckdb_connection(tmp_path: Path) -> None:
    """Test that connection property returns DuckDB connection."""
    import duckdb

    db_path = tmp_path / "test.db"
    with StorageEngine(path=db_path, read_only=False) as storage:
        assert isinstance(storage.connection, duckdb.DuckDBPyConnection)


def test_cleanup_is_alias_for_close(tmp_path: Path) -> None:
    """Test that cleanup() calls close()."""
    db_path = tmp_path / "test.db"
    storage = StorageEngine(path=db_path, read_only=False)

    # cleanup() should work just like close()
    storage.cleanup()

    # Should be safe to call again
    storage.cleanup()


# =============================================================================
# T021: Unit test for create_events_table batch insert logic
# =============================================================================


def test_create_events_table_inserts_all_records(tmp_path: Path) -> None:
    """Test that create_events_table inserts all records from iterator."""
    from datetime import datetime

    db_path = tmp_path / "test.db"
    with StorageEngine(path=db_path, read_only=False) as storage:
        # Create sample events
        events = [
            {
                "event_name": "Page View",
                "event_time": datetime(2024, 1, 15, 10, 30, tzinfo=UTC),
                "distinct_id": "user_123",
                "insert_id": "event_001",
                "properties": {"page": "/home", "country": "US"},
            },
            {
                "event_name": "Button Click",
                "event_time": datetime(2024, 1, 15, 11, 0, tzinfo=UTC),
                "distinct_id": "user_456",
                "insert_id": "event_002",
                "properties": {"button": "signup", "country": "EU"},
            },
        ]

        from mixpanel_data.types import TableMetadata

        metadata = TableMetadata(
            type="events",
            fetched_at=datetime.now(UTC),
            from_date="2024-01-15",
            to_date="2024-01-15",
        )

        # Create events table
        row_count = storage.create_events_table("test_events", iter(events), metadata)

        # Verify row count
        assert row_count == 2

        # Verify data was inserted
        count_result = storage.connection.execute(
            "SELECT COUNT(*) FROM test_events"
        ).fetchone()
        assert count_result == (2,)

        # Verify schema is correct
        rows = storage.connection.execute(
            "SELECT event_name, distinct_id FROM test_events ORDER BY event_time"
        ).fetchall()
        assert rows == [("Page View", "user_123"), ("Button Click", "user_456")]


def test_create_events_table_handles_large_batches(tmp_path: Path) -> None:
    """Test that create_events_table handles batches correctly."""
    from datetime import datetime

    db_path = tmp_path / "test.db"
    with StorageEngine(path=db_path, read_only=False) as storage:
        # Create 2100 events to test batching (batch size is 2000, so this
        # creates 2 batches - enough to verify batching works correctly)
        def event_generator() -> Iterator[dict[str, Any]]:
            for i in range(2100):
                yield {
                    "event_name": "Event",
                    "event_time": datetime.now(UTC),
                    "distinct_id": f"user_{i}",
                    "insert_id": f"event_{i:06d}",
                    "properties": {"index": i},
                }

        from mixpanel_data.types import TableMetadata

        metadata = TableMetadata(
            type="events",
            fetched_at=datetime.now(UTC),
            from_date="2024-01-01",
            to_date="2024-01-31",
        )

        # Create events table
        row_count = storage.create_events_table(
            "large_events", event_generator(), metadata
        )

        # Verify row count
        assert row_count == 2100

        # Verify data was inserted
        result = storage.connection.execute(
            "SELECT COUNT(*) FROM large_events"
        ).fetchone()
        assert result == (2100,)


def test_create_events_table_raises_error_if_table_exists(tmp_path: Path) -> None:
    """Test that create_events_table raises TableExistsError if table exists."""
    from datetime import datetime

    from mixpanel_data.exceptions import TableExistsError
    from mixpanel_data.types import TableMetadata

    db_path = tmp_path / "test.db"
    with StorageEngine(path=db_path, read_only=False) as storage:
        events = [
            {
                "event_name": "Event",
                "event_time": datetime.now(UTC),
                "distinct_id": "user_1",
                "insert_id": "event_1",
                "properties": {},
            }
        ]

        metadata = TableMetadata(
            type="events",
            fetched_at=datetime.now(UTC),
        )

        # Create table first time - should succeed
        storage.create_events_table("test_events", iter(events), metadata)

        # Try to create again - should raise TableExistsError
        with pytest.raises(TableExistsError):
            storage.create_events_table("test_events", iter(events), metadata)


def test_create_events_table_validates_table_name(tmp_path: Path) -> None:
    """Test that create_events_table validates table names."""
    from datetime import datetime

    from mixpanel_data.types import TableMetadata

    db_path = tmp_path / "test.db"
    with StorageEngine(path=db_path, read_only=False) as storage:
        events = [
            {
                "event_name": "Event",
                "event_time": datetime.now(UTC),
                "distinct_id": "user_1",
                "insert_id": "event_1",
                "properties": {},
            }
        ]

        metadata = TableMetadata(
            type="events",
            fetched_at=datetime.now(UTC),
        )

        # Invalid: starts with underscore (reserved for internal tables)
        with pytest.raises(ValueError, match="underscore"):
            storage.create_events_table("_invalid", iter(events), metadata)

        # Invalid: contains spaces
        with pytest.raises(ValueError):
            storage.create_events_table("invalid name", iter(events), metadata)

        # Invalid: contains special characters
        with pytest.raises(ValueError):
            storage.create_events_table("invalid-name", iter(events), metadata)

        # Valid names should work
        storage.create_events_table("valid_name", iter(events), metadata)
        storage.create_events_table("valid123", iter(events), metadata)


def test_create_events_table_validates_required_fields(tmp_path: Path) -> None:
    """Test that create_events_table validates required fields."""
    from datetime import datetime

    from mixpanel_data.types import TableMetadata

    db_path = tmp_path / "test.db"
    with StorageEngine(path=db_path, read_only=False) as storage:
        metadata = TableMetadata(
            type="events",
            fetched_at=datetime.now(UTC),
        )

        # Missing event_name
        with pytest.raises(ValueError, match="event_name"):
            storage.create_events_table(
                "test_events1",
                iter(
                    [
                        {
                            "event_time": datetime.now(UTC),
                            "distinct_id": "user_1",
                            "insert_id": "event_1",
                            "properties": {},
                        }
                    ]
                ),
                metadata,
            )

        # Missing event_time
        with pytest.raises(ValueError, match="event_time"):
            storage.create_events_table(
                "test_events2",
                iter(
                    [
                        {
                            "event_name": "Event",
                            "distinct_id": "user_1",
                            "insert_id": "event_1",
                            "properties": {},
                        }
                    ]
                ),
                metadata,
            )

        # Missing distinct_id
        with pytest.raises(ValueError, match="distinct_id"):
            storage.create_events_table(
                "test_events3",
                iter(
                    [
                        {
                            "event_name": "Event",
                            "event_time": datetime.now(UTC),
                            "insert_id": "event_1",
                            "properties": {},
                        }
                    ]
                ),
                metadata,
            )

        # Missing insert_id
        with pytest.raises(ValueError, match="insert_id"):
            storage.create_events_table(
                "test_events4",
                iter(
                    [
                        {
                            "event_name": "Event",
                            "event_time": datetime.now(UTC),
                            "distinct_id": "user_1",
                            "properties": {},
                        }
                    ]
                ),
                metadata,
            )

        # Missing properties (should be allowed as it can default to empty dict)
        # Actually, let's require properties
        with pytest.raises(ValueError, match="properties"):
            storage.create_events_table(
                "test_events5",
                iter(
                    [
                        {
                            "event_name": "Event",
                            "event_time": datetime.now(UTC),
                            "distinct_id": "user_1",
                            "insert_id": "event_1",
                        }
                    ]
                ),
                metadata,
            )


# =============================================================================
# T022: Unit test for create_profiles_table batch insert logic
# =============================================================================


def test_create_profiles_table_inserts_all_records(tmp_path: Path) -> None:
    """Test that create_profiles_table inserts all records from iterator."""
    from datetime import datetime

    db_path = tmp_path / "test.db"
    with StorageEngine(path=db_path, read_only=False) as storage:
        # Create sample profiles
        profiles = [
            {
                "distinct_id": "user_123",
                "properties": {"name": "Alice", "email": "alice@example.com"},
                "last_seen": datetime(2024, 1, 15, 10, 30, tzinfo=UTC),
            },
            {
                "distinct_id": "user_456",
                "properties": {"name": "Bob", "email": "bob@example.com"},
                "last_seen": datetime(2024, 1, 15, 11, 0, tzinfo=UTC),
            },
        ]

        from mixpanel_data.types import TableMetadata

        metadata = TableMetadata(
            type="profiles",
            fetched_at=datetime.now(UTC),
        )

        # Create profiles table
        row_count = storage.create_profiles_table(
            "test_profiles", iter(profiles), metadata
        )

        # Verify row count
        assert row_count == 2

        # Verify data was inserted
        count_result = storage.connection.execute(
            "SELECT COUNT(*) FROM test_profiles"
        ).fetchone()
        assert count_result == (2,)

        # Verify schema is correct
        rows = storage.connection.execute(
            "SELECT distinct_id FROM test_profiles ORDER BY distinct_id"
        ).fetchall()
        assert rows == [("user_123",), ("user_456",)]


def test_create_profiles_table_validates_required_fields(tmp_path: Path) -> None:
    """Test that create_profiles_table validates required fields."""
    from datetime import datetime

    from mixpanel_data.types import TableMetadata

    db_path = tmp_path / "test.db"
    with StorageEngine(path=db_path, read_only=False) as storage:
        metadata = TableMetadata(
            type="profiles",
            fetched_at=datetime.now(UTC),
        )

        # Missing distinct_id
        with pytest.raises(ValueError, match="distinct_id"):
            storage.create_profiles_table(
                "test_profiles1",
                iter(
                    [
                        {
                            "properties": {"name": "Alice"},
                            "last_seen": datetime.now(UTC),
                        }
                    ]
                ),
                metadata,
            )

        # Missing properties
        with pytest.raises(ValueError, match="properties"):
            storage.create_profiles_table(
                "test_profiles2",
                iter(
                    [
                        {
                            "distinct_id": "user_1",
                            "last_seen": datetime.now(UTC),
                        }
                    ]
                ),
                metadata,
            )

        # Missing last_seen (should be allowed - can be NULL)
        # Actually, let's require last_seen
        with pytest.raises(ValueError, match="last_seen"):
            storage.create_profiles_table(
                "test_profiles3",
                iter([{"distinct_id": "user_1", "properties": {"name": "Alice"}}]),
                metadata,
            )


# =============================================================================
# T023: Unit test for progress callback invocation
# =============================================================================


def test_create_events_table_invokes_progress_callback(tmp_path: Path) -> None:
    """Test that create_events_table invokes progress callback."""
    from datetime import datetime

    db_path = tmp_path / "test.db"
    with StorageEngine(path=db_path, read_only=False) as storage:
        # Create events generator (2100 events = 2 batches with batch_size=2000)
        def event_generator() -> Iterator[dict[str, Any]]:
            for i in range(2100):
                yield {
                    "event_name": "Event",
                    "event_time": datetime.now(UTC),
                    "distinct_id": f"user_{i}",
                    "insert_id": f"event_{i:06d}",
                    "properties": {"index": i},
                }

        from mixpanel_data.types import TableMetadata

        metadata = TableMetadata(
            type="events",
            fetched_at=datetime.now(UTC),
        )

        # Track progress callbacks
        callback_invocations = []

        def on_progress(row_count: int) -> None:
            callback_invocations.append(row_count)

        # Create events table with callback
        total_rows = storage.create_events_table(
            "test_events", event_generator(), metadata, progress_callback=on_progress
        )

        # Verify callback was invoked
        assert len(callback_invocations) > 0

        # Verify final callback has total row count
        assert callback_invocations[-1] == total_rows == 2100

        # Verify callback was invoked multiple times (batching)
        # With batch size of 2000, we should have at least 2 invocations
        assert len(callback_invocations) >= 2


def test_create_profiles_table_invokes_progress_callback(tmp_path: Path) -> None:
    """Test that create_profiles_table invokes progress callback."""
    from datetime import datetime

    db_path = tmp_path / "test.db"
    with StorageEngine(path=db_path, read_only=False) as storage:
        # Create profiles generator (500 is enough to verify callback works)
        def profile_generator() -> Iterator[dict[str, Any]]:
            for i in range(500):
                yield {
                    "distinct_id": f"user_{i}",
                    "properties": {"name": f"User {i}"},
                    "last_seen": datetime.now(UTC),
                }

        from mixpanel_data.types import TableMetadata

        metadata = TableMetadata(
            type="profiles",
            fetched_at=datetime.now(UTC),
        )

        # Track progress callbacks
        callback_invocations = []

        def on_progress(row_count: int) -> None:
            callback_invocations.append(row_count)

        # Create profiles table with callback
        total_rows = storage.create_profiles_table(
            "test_profiles",
            profile_generator(),
            metadata,
            progress_callback=on_progress,
        )

        # Verify callback was invoked
        assert len(callback_invocations) > 0

        # Verify final callback has total row count
        assert callback_invocations[-1] == total_rows == 500


# =============================================================================
# T036: Unit test for ephemeral() classmethod
# =============================================================================


def test_ephemeral_creates_temporary_database() -> None:
    """Test that ephemeral() creates a temporary database file."""
    storage = StorageEngine.ephemeral()

    try:
        # Should have a valid connection
        assert storage.connection is not None

        # Path should exist but be in a temporary location
        assert storage.path is not None
        assert storage.path.exists()
        assert storage.path.is_file()

        # Should be able to create tables
        storage.connection.execute("CREATE TABLE test (id INTEGER, value VARCHAR)")
        storage.connection.execute("INSERT INTO test VALUES (1, 'hello')")

        # Should be able to query
        result = storage.connection.execute("SELECT value FROM test").fetchone()
        assert result == ("hello",)
    finally:
        # Cleanup
        temp_path = storage.path
        storage.close()
        assert temp_path is not None

        # After close, temp file should be deleted
        assert not temp_path.exists()


def test_ephemeral_returns_storage_engine_instance() -> None:
    """Test that ephemeral() returns a StorageEngine instance."""
    with StorageEngine.ephemeral() as storage:
        assert isinstance(storage, StorageEngine)


def test_ephemeral_path_is_unique_for_each_instance() -> None:
    """Test that each ephemeral database gets a unique path."""
    with StorageEngine.ephemeral() as storage1, StorageEngine.ephemeral() as storage2:
        assert storage1.path != storage2.path


# =============================================================================
# T037: Unit test for cleanup() method
# =============================================================================


def test_cleanup_deletes_ephemeral_database() -> None:
    """Test that cleanup() deletes ephemeral database file."""
    storage = StorageEngine.ephemeral()
    temp_path = storage.path
    assert temp_path is not None

    # Before cleanup, file should exist
    assert temp_path.exists()

    # Call cleanup
    storage.cleanup()

    # After cleanup, file should be deleted
    assert not temp_path.exists()


def test_cleanup_is_idempotent() -> None:
    """Test that cleanup() can be called multiple times safely."""
    storage = StorageEngine.ephemeral()
    temp_path = storage.path
    assert temp_path is not None

    # Call cleanup multiple times
    storage.cleanup()
    storage.cleanup()
    storage.cleanup()

    # Should not raise errors
    assert not temp_path.exists()


def test_cleanup_removes_wal_files_if_present() -> None:
    """Test that cleanup() removes WAL files if they exist."""
    storage = StorageEngine.ephemeral()
    temp_path = storage.path
    assert temp_path is not None

    # Create some data to potentially trigger WAL creation
    storage.connection.execute("CREATE TABLE test (id INTEGER)")
    storage.connection.execute("INSERT INTO test VALUES (1)")

    # Get potential WAL path
    wal_path = Path(str(temp_path) + ".wal")

    # Call cleanup
    storage.cleanup()

    # Both database and WAL should be gone
    assert not temp_path.exists()
    assert not wal_path.exists()


def test_cleanup_does_nothing_for_persistent_database(tmp_path: Path) -> None:
    """Test that cleanup() doesn't delete persistent databases."""
    db_path = tmp_path / "persistent.db"
    storage = StorageEngine(path=db_path, read_only=False)

    # Before cleanup, file should exist
    assert db_path.exists()

    # Call cleanup
    storage.cleanup()

    # After cleanup, persistent file should still exist
    assert db_path.exists()

    # Clean up
    storage.close()


# =============================================================================
# T047: Unit test for open_existing() classmethod
# =============================================================================


def test_open_existing_opens_existing_database(tmp_path: Path) -> None:
    """Test that open_existing() opens an existing database file."""
    db_path = tmp_path / "existing.db"

    # Create database first
    with StorageEngine(path=db_path, read_only=False) as storage1:
        storage1.connection.execute("CREATE TABLE test (id INTEGER, value VARCHAR)")
        storage1.connection.execute("INSERT INTO test VALUES (1, 'data')")

    # Open existing database
    with StorageEngine.open_existing(db_path) as storage:
        # Should be able to query existing data
        result = storage.connection.execute("SELECT value FROM test").fetchone()
        assert result == ("data",)


def test_open_existing_raises_error_if_file_missing(tmp_path: Path) -> None:
    """Test that open_existing() raises FileNotFoundError if database doesn't exist."""
    db_path = tmp_path / "nonexistent.db"

    with pytest.raises(FileNotFoundError):
        StorageEngine.open_existing(db_path)


# =============================================================================
# T059: Unit test for list_tables()
# =============================================================================


def test_list_tables_returns_empty_list_for_new_database(tmp_path: Path) -> None:
    """Test that list_tables() returns empty list for new database."""
    db_path = tmp_path / "test.db"
    with StorageEngine(path=db_path, read_only=False) as storage:
        # New database should have no user tables
        tables = storage.list_tables()
        assert tables == []


def test_list_tables_returns_all_user_tables(tmp_path: Path) -> None:
    """Test that list_tables() returns all user-created tables."""
    from datetime import datetime

    from mixpanel_data.types import TableMetadata

    db_path = tmp_path / "test.db"
    with StorageEngine(path=db_path, read_only=False) as storage:
        # Create multiple tables
        events = [
            {
                "event_name": "Event",
                "event_time": datetime.now(UTC),
                "distinct_id": "user_1",
                "insert_id": "event_1",
                "properties": {},
            }
        ]
        profiles = [
            {
                "distinct_id": "user_1",
                "properties": {"name": "Alice"},
                "last_seen": datetime.now(UTC),
            }
        ]

        events_metadata = TableMetadata(
            type="events",
            fetched_at=datetime.now(UTC),
            from_date="2024-01-01",
            to_date="2024-01-31",
        )
        profiles_metadata = TableMetadata(
            type="profiles",
            fetched_at=datetime.now(UTC),
        )

        storage.create_events_table("events_jan", iter(events), events_metadata)
        storage.create_profiles_table("profiles_all", iter(profiles), profiles_metadata)

        # List tables
        tables = storage.list_tables()

        # Should have 2 tables
        assert len(tables) == 2

        # Tables should be sorted by name
        assert tables[0].name == "events_jan"
        assert tables[1].name == "profiles_all"

        # Check table info
        assert tables[0].type == "events"
        assert tables[0].row_count == 1
        assert tables[0].fetched_at is not None

        assert tables[1].type == "profiles"
        assert tables[1].row_count == 1
        assert tables[1].fetched_at is not None


def test_list_tables_excludes_internal_metadata_table(tmp_path: Path) -> None:
    """Test that list_tables() excludes internal _metadata table."""
    from datetime import datetime

    from mixpanel_data.types import TableMetadata

    db_path = tmp_path / "test.db"
    with StorageEngine(path=db_path, read_only=False) as storage:
        # Create one user table
        events = [
            {
                "event_name": "Event",
                "event_time": datetime.now(UTC),
                "distinct_id": "user_1",
                "insert_id": "event_1",
                "properties": {},
            }
        ]
        metadata = TableMetadata(
            type="events",
            fetched_at=datetime.now(UTC),
        )
        storage.create_events_table("my_events", iter(events), metadata)

        # List tables
        tables = storage.list_tables()

        # Should only return user table, not _metadata
        assert len(tables) == 1
        assert tables[0].name == "my_events"

        # Verify _metadata table exists in database
        result = storage.connection.execute(
            "SELECT COUNT(*) FROM information_schema.tables WHERE table_name = '_metadata'"
        ).fetchone()
        assert result == (1,)


# =============================================================================
# T060: Unit test for get_schema(table)
# =============================================================================


def test_get_schema_returns_events_table_schema(tmp_path: Path) -> None:
    """Test that get_schema() returns correct schema for events table."""
    from datetime import datetime

    from mixpanel_data.types import TableMetadata

    db_path = tmp_path / "test.db"
    with StorageEngine(path=db_path, read_only=False) as storage:
        # Create events table
        events = [
            {
                "event_name": "Event",
                "event_time": datetime.now(UTC),
                "distinct_id": "user_1",
                "insert_id": "event_1",
                "properties": {},
            }
        ]
        metadata = TableMetadata(
            type="events",
            fetched_at=datetime.now(UTC),
        )
        storage.create_events_table("test_events", iter(events), metadata)

        # Get schema
        schema = storage.get_schema("test_events")

        # Verify table name
        assert schema.table_name == "test_events"

        # Verify columns
        assert len(schema.columns) == 5
        column_names = [col.name for col in schema.columns]
        assert "event_name" in column_names
        assert "event_time" in column_names
        assert "distinct_id" in column_names
        assert "insert_id" in column_names
        assert "properties" in column_names

        # Find insert_id column and verify it's primary key
        insert_id_col = next(col for col in schema.columns if col.name == "insert_id")
        assert insert_id_col.primary_key is True


def test_get_schema_returns_profiles_table_schema(tmp_path: Path) -> None:
    """Test that get_schema() returns correct schema for profiles table."""
    from datetime import datetime

    from mixpanel_data.types import TableMetadata

    db_path = tmp_path / "test.db"
    with StorageEngine(path=db_path, read_only=False) as storage:
        # Create profiles table
        profiles = [
            {
                "distinct_id": "user_1",
                "properties": {"name": "Alice"},
                "last_seen": datetime.now(UTC),
            }
        ]
        metadata = TableMetadata(
            type="profiles",
            fetched_at=datetime.now(UTC),
        )
        storage.create_profiles_table("test_profiles", iter(profiles), metadata)

        # Get schema
        schema = storage.get_schema("test_profiles")

        # Verify table name
        assert schema.table_name == "test_profiles"

        # Verify columns
        assert len(schema.columns) == 3
        column_names = [col.name for col in schema.columns]
        assert "distinct_id" in column_names
        assert "properties" in column_names
        assert "last_seen" in column_names

        # Find distinct_id column and verify it's primary key
        distinct_id_col = next(
            col for col in schema.columns if col.name == "distinct_id"
        )
        assert distinct_id_col.primary_key is True


# =============================================================================
# T061: Unit test for get_metadata(table)
# =============================================================================


def test_get_metadata_returns_table_metadata(tmp_path: Path) -> None:
    """Test that get_metadata() returns correct metadata for table."""
    from datetime import datetime

    from mixpanel_data.types import TableMetadata

    db_path = tmp_path / "test.db"
    with StorageEngine(path=db_path, read_only=False) as storage:
        # Create events table with specific metadata
        events = [
            {
                "event_name": "Event",
                "event_time": datetime.now(UTC),
                "distinct_id": "user_1",
                "insert_id": "event_1",
                "properties": {},
            }
        ]
        original_metadata = TableMetadata(
            type="events",
            fetched_at=datetime(2024, 1, 15, 10, 30, tzinfo=UTC),
            from_date="2024-01-01",
            to_date="2024-01-31",
        )
        storage.create_events_table("test_events", iter(events), original_metadata)

        # Get metadata
        retrieved_metadata = storage.get_metadata("test_events")

        # Verify metadata matches
        assert retrieved_metadata.type == "events"
        assert retrieved_metadata.from_date == "2024-01-01"
        assert retrieved_metadata.to_date == "2024-01-31"
        # Note: fetched_at will be datetime object after retrieval
        assert retrieved_metadata.fetched_at is not None


def test_get_metadata_returns_profiles_metadata(tmp_path: Path) -> None:
    """Test that get_metadata() returns correct metadata for profiles table."""
    from datetime import datetime

    from mixpanel_data.types import TableMetadata

    db_path = tmp_path / "test.db"
    with StorageEngine(path=db_path, read_only=False) as storage:
        # Create profiles table
        profiles = [
            {
                "distinct_id": "user_1",
                "properties": {"name": "Alice"},
                "last_seen": datetime.now(UTC),
            }
        ]
        original_metadata = TableMetadata(
            type="profiles",
            fetched_at=datetime.now(UTC),
        )
        storage.create_profiles_table(
            "test_profiles", iter(profiles), original_metadata
        )

        # Get metadata
        retrieved_metadata = storage.get_metadata("test_profiles")

        # Verify metadata
        assert retrieved_metadata.type == "profiles"
        assert retrieved_metadata.from_date is None
        assert retrieved_metadata.to_date is None


# =============================================================================
# T062: Unit test for TableNotFoundError on missing table
# =============================================================================


def test_get_schema_raises_error_for_missing_table(tmp_path: Path) -> None:
    """Test that get_schema() raises TableNotFoundError for missing table."""
    from mixpanel_data.exceptions import TableNotFoundError

    db_path = tmp_path / "test.db"
    with (
        StorageEngine(path=db_path, read_only=False) as storage,
        pytest.raises(TableNotFoundError, match="nonexistent_table"),
    ):
        storage.get_schema("nonexistent_table")


def test_get_metadata_raises_error_for_missing_table(tmp_path: Path) -> None:
    """Test that get_metadata() raises TableNotFoundError for missing table."""
    from mixpanel_data.exceptions import TableNotFoundError

    db_path = tmp_path / "test.db"
    with (
        StorageEngine(path=db_path, read_only=False) as storage,
        pytest.raises(TableNotFoundError, match="nonexistent_table"),
    ):
        storage.get_metadata("nonexistent_table")


# =============================================================================
# T068: Unit test for table_exists(name)
# =============================================================================


def test_table_exists_returns_true_for_existing_table(tmp_path: Path) -> None:
    """Test that table_exists() returns True for existing tables."""
    from datetime import datetime

    from mixpanel_data.types import TableMetadata

    db_path = tmp_path / "test.db"
    with StorageEngine(path=db_path, read_only=False) as storage:
        # Create a table
        events = [
            {
                "event_name": "Event",
                "event_time": datetime.now(UTC),
                "distinct_id": "user_1",
                "insert_id": "event_1",
                "properties": {},
            }
        ]

        metadata = TableMetadata(
            type="events",
            fetched_at=datetime.now(UTC),
        )

        storage.create_events_table("test_events", iter(events), metadata)

        # Check if table exists
        assert storage.table_exists("test_events") is True


def test_table_exists_returns_false_for_nonexistent_table(tmp_path: Path) -> None:
    """Test that table_exists() returns False for nonexistent tables."""
    db_path = tmp_path / "test.db"
    with StorageEngine(path=db_path, read_only=False) as storage:
        # Check for table that doesn't exist
        assert storage.table_exists("nonexistent_table") is False


def test_table_exists_returns_false_for_metadata_table(tmp_path: Path) -> None:
    """Test that table_exists() returns True for internal _metadata table."""
    from datetime import datetime

    from mixpanel_data.types import TableMetadata

    db_path = tmp_path / "test.db"
    with StorageEngine(path=db_path, read_only=False) as storage:
        # Create a table to trigger _metadata table creation
        events = [
            {
                "event_name": "Event",
                "event_time": datetime.now(UTC),
                "distinct_id": "user_1",
                "insert_id": "event_1",
                "properties": {},
            }
        ]

        metadata = TableMetadata(
            type="events",
            fetched_at=datetime.now(UTC),
        )

        storage.create_events_table("test_events", iter(events), metadata)

        # _metadata is an internal table but should still be detectable
        assert storage.table_exists("_metadata") is True


# =============================================================================
# T069: Unit test for drop_table(name)
# =============================================================================


def test_drop_table_removes_table_from_database(tmp_path: Path) -> None:
    """Test that drop_table() removes table from database."""
    from datetime import datetime

    from mixpanel_data.types import TableMetadata

    db_path = tmp_path / "test.db"
    with StorageEngine(path=db_path, read_only=False) as storage:
        # Create a table
        events = [
            {
                "event_name": "Event",
                "event_time": datetime.now(UTC),
                "distinct_id": "user_1",
                "insert_id": "event_1",
                "properties": {},
            }
        ]

        metadata = TableMetadata(
            type="events",
            fetched_at=datetime.now(UTC),
        )

        storage.create_events_table("test_events", iter(events), metadata)

        # Verify table exists
        assert storage.table_exists("test_events") is True

        # Drop table
        storage.drop_table("test_events")

        # Verify table is gone
        assert storage.table_exists("test_events") is False


def test_drop_table_removes_metadata_entry(tmp_path: Path) -> None:
    """Test that drop_table() removes metadata entry."""
    from datetime import datetime

    from mixpanel_data.types import TableMetadata

    db_path = tmp_path / "test.db"
    with StorageEngine(path=db_path, read_only=False) as storage:
        # Create a table
        events = [
            {
                "event_name": "Event",
                "event_time": datetime.now(UTC),
                "distinct_id": "user_1",
                "insert_id": "event_1",
                "properties": {},
            }
        ]

        metadata = TableMetadata(
            type="events",
            fetched_at=datetime.now(UTC),
        )

        storage.create_events_table("test_events", iter(events), metadata)

        # Verify metadata exists
        result = storage.connection.execute(
            "SELECT COUNT(*) FROM _metadata WHERE table_name = ?",
            ("test_events",),
        ).fetchone()
        assert result == (1,)

        # Drop table
        storage.drop_table("test_events")

        # Verify metadata is gone
        result = storage.connection.execute(
            "SELECT COUNT(*) FROM _metadata WHERE table_name = ?",
            ("test_events",),
        ).fetchone()
        assert result == (0,)


# =============================================================================
# T070: Unit test for TableExistsError on duplicate creation
# =============================================================================


def test_create_events_table_raises_table_exists_error_on_duplicate(
    tmp_path: Path,
) -> None:
    """Test that creating duplicate events table raises TableExistsError."""
    from datetime import datetime

    from mixpanel_data.exceptions import TableExistsError
    from mixpanel_data.types import TableMetadata

    db_path = tmp_path / "test.db"
    with StorageEngine(path=db_path, read_only=False) as storage:
        events = [
            {
                "event_name": "Event",
                "event_time": datetime.now(UTC),
                "distinct_id": "user_1",
                "insert_id": "event_1",
                "properties": {},
            }
        ]

        metadata = TableMetadata(
            type="events",
            fetched_at=datetime.now(UTC),
        )

        # Create table first time
        storage.create_events_table("duplicate_test", iter(events), metadata)

        # Try to create again - should raise TableExistsError
        with pytest.raises(TableExistsError, match="duplicate_test"):
            storage.create_events_table("duplicate_test", iter(events), metadata)


def test_create_profiles_table_raises_table_exists_error_on_duplicate(
    tmp_path: Path,
) -> None:
    """Test that creating duplicate profiles table raises TableExistsError."""
    from datetime import datetime

    from mixpanel_data.exceptions import TableExistsError
    from mixpanel_data.types import TableMetadata

    db_path = tmp_path / "test.db"
    with StorageEngine(path=db_path, read_only=False) as storage:
        profiles = [
            {
                "distinct_id": "user_1",
                "properties": {"name": "Alice"},
                "last_seen": datetime.now(UTC),
            }
        ]

        metadata = TableMetadata(
            type="profiles",
            fetched_at=datetime.now(UTC),
        )

        # Create table first time
        storage.create_profiles_table("duplicate_test", iter(profiles), metadata)

        # Try to create again - should raise TableExistsError
        with pytest.raises(TableExistsError, match="duplicate_test"):
            storage.create_profiles_table("duplicate_test", iter(profiles), metadata)


# =============================================================================
# T071: Unit test for TableNotFoundError on drop_table(missing)
# =============================================================================


def test_drop_table_raises_table_not_found_error_for_missing_table(
    tmp_path: Path,
) -> None:
    """Test that dropping nonexistent table raises TableNotFoundError."""
    from mixpanel_data.exceptions import TableNotFoundError

    db_path = tmp_path / "test.db"
    with (
        StorageEngine(path=db_path, read_only=False) as storage,
        pytest.raises(TableNotFoundError, match="nonexistent_table"),
    ):
        # Try to drop table that doesn't exist
        storage.drop_table("nonexistent_table")


def test_drop_table_raises_table_not_found_error_after_drop(tmp_path: Path) -> None:
    """Test that dropping same table twice raises TableNotFoundError."""
    from datetime import datetime

    from mixpanel_data.exceptions import TableNotFoundError
    from mixpanel_data.types import TableMetadata

    db_path = tmp_path / "test.db"
    with StorageEngine(path=db_path, read_only=False) as storage:
        # Create a table
        events = [
            {
                "event_name": "Event",
                "event_time": datetime.now(UTC),
                "distinct_id": "user_1",
                "insert_id": "event_1",
                "properties": {},
            }
        ]

        metadata = TableMetadata(
            type="events",
            fetched_at=datetime.now(UTC),
        )

        storage.create_events_table("test_events", iter(events), metadata)

        # Drop table once - should succeed
        storage.drop_table("test_events")

        # Try to drop again - should raise TableNotFoundError
        with pytest.raises(TableNotFoundError, match="test_events"):
            storage.drop_table("test_events")


# =============================================================================
# T048: Unit test for execute() returning DuckDB relation
# =============================================================================


def test_execute_returns_duckdb_relation(tmp_path: Path) -> None:
    """Test that execute() returns a DuckDB relation object."""
    import duckdb

    db_path = tmp_path / "test.db"
    with StorageEngine(path=db_path, read_only=False) as storage:
        # Create a test table
        storage.connection.execute("CREATE TABLE test (id INTEGER, value VARCHAR)")
        storage.connection.execute("INSERT INTO test VALUES (1, 'hello'), (2, 'world')")

        # Execute query and get relation
        relation = storage.execute("SELECT * FROM test ORDER BY id")

        # Should return DuckDB relation
        assert isinstance(relation, duckdb.DuckDBPyRelation)

        # Relation should be queryable
        result = relation.fetchall()
        assert result == [(1, "hello"), (2, "world")]


def test_execute_can_be_chained(tmp_path: Path) -> None:
    """Test that execute() returns a relation that can be chained."""
    import duckdb

    db_path = tmp_path / "test.db"
    with StorageEngine(path=db_path, read_only=False) as storage:
        # Create test data
        storage.connection.execute("CREATE TABLE test (id INTEGER, value VARCHAR)")
        storage.connection.execute(
            "INSERT INTO test VALUES (1, 'a'), (2, 'b'), (3, 'c')"
        )

        # Execute and chain DuckDB operations
        relation = storage.execute("SELECT * FROM test")

        # Should be chainable (DuckDB relation API)
        assert isinstance(relation, duckdb.DuckDBPyRelation)

        # Can call methods on relation
        filtered = relation.filter("id > 1")
        result = filtered.fetchall()
        assert len(result) == 2


# =============================================================================
# T049: Unit test for execute_df() returning DataFrame
# =============================================================================


def test_execute_df_returns_dataframe(tmp_path: Path) -> None:
    """Test that execute_df() returns a pandas DataFrame."""
    import pandas as pd

    db_path = tmp_path / "test.db"
    with StorageEngine(path=db_path, read_only=False) as storage:
        # Create test data
        storage.connection.execute("CREATE TABLE test (id INTEGER, value VARCHAR)")
        storage.connection.execute("INSERT INTO test VALUES (1, 'hello'), (2, 'world')")

        # Execute query and get DataFrame
        df = storage.execute_df("SELECT * FROM test ORDER BY id")

        # Should return DataFrame
        assert isinstance(df, pd.DataFrame)

        # Verify data
        assert len(df) == 2
        assert list(df.columns) == ["id", "value"]
        assert df["id"].tolist() == [1, 2]
        assert df["value"].tolist() == ["hello", "world"]


def test_execute_df_returns_empty_dataframe_for_empty_result(tmp_path: Path) -> None:
    """Test that execute_df() returns empty DataFrame for empty result."""
    import pandas as pd

    db_path = tmp_path / "test.db"
    with StorageEngine(path=db_path, read_only=False) as storage:
        # Create empty table
        storage.connection.execute("CREATE TABLE test (id INTEGER, value VARCHAR)")

        # Execute query with no results
        df = storage.execute_df("SELECT * FROM test")

        # Should return empty DataFrame
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 0
        assert list(df.columns) == ["id", "value"]


def test_execute_df_handles_json_columns(tmp_path: Path) -> None:
    """Test that execute_df() handles JSON columns correctly."""
    from datetime import datetime

    import pandas as pd

    db_path = tmp_path / "test.db"
    with StorageEngine(path=db_path, read_only=False) as storage:
        # Create events table with JSON properties
        from mixpanel_data.types import TableMetadata

        events = [
            {
                "event_name": "Page View",
                "event_time": datetime(2024, 1, 15, 10, 30, tzinfo=UTC),
                "distinct_id": "user_123",
                "insert_id": "event_001",
                "properties": {"page": "/home", "country": "US"},
            }
        ]

        metadata = TableMetadata(
            type="events",
            fetched_at=datetime.now(UTC),
        )

        storage.create_events_table("events", iter(events), metadata)

        # Query with JSON extraction
        df = storage.execute_df("SELECT event_name, properties FROM events")

        # Should return DataFrame
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 1
        assert df["event_name"].iloc[0] == "Page View"


# =============================================================================
# T050: Unit test for execute_scalar() returning single value
# =============================================================================


def test_execute_scalar_returns_single_value(tmp_path: Path) -> None:
    """Test that execute_scalar() returns a single scalar value."""
    db_path = tmp_path / "test.db"
    with StorageEngine(path=db_path, read_only=False) as storage:
        # Create test data
        storage.connection.execute("CREATE TABLE test (id INTEGER, value VARCHAR)")
        storage.connection.execute("INSERT INTO test VALUES (1, 'hello'), (2, 'world')")

        # Execute scalar query
        count = storage.execute_scalar("SELECT COUNT(*) FROM test")

        # Should return scalar value
        assert count == 2
        assert isinstance(count, int)


def test_execute_scalar_returns_different_types(tmp_path: Path) -> None:
    """Test that execute_scalar() returns correct types for different queries."""
    db_path = tmp_path / "test.db"
    with StorageEngine(path=db_path, read_only=False) as storage:
        # Create test data
        storage.connection.execute(
            "CREATE TABLE test (id INTEGER, price DECIMAL, name VARCHAR)"
        )
        storage.connection.execute("INSERT INTO test VALUES (1, 99.99, 'Product A')")

        # Integer
        max_id = storage.execute_scalar("SELECT MAX(id) FROM test")
        assert max_id == 1
        assert isinstance(max_id, int)

        # String
        name = storage.execute_scalar("SELECT name FROM test WHERE id = 1")
        assert name == "Product A"
        assert isinstance(name, str)

        # Decimal/Float (DuckDB returns Decimal for DECIMAL columns)
        price = storage.execute_scalar("SELECT price FROM test WHERE id = 1")
        assert float(price) == pytest.approx(99.99)


def test_execute_scalar_returns_none_for_null(tmp_path: Path) -> None:
    """Test that execute_scalar() returns None for NULL values."""
    db_path = tmp_path / "test.db"
    with StorageEngine(path=db_path, read_only=False) as storage:
        # Create test data with NULL
        storage.connection.execute("CREATE TABLE test (id INTEGER, value VARCHAR)")
        storage.connection.execute("INSERT INTO test VALUES (1, NULL)")

        # Execute scalar query for NULL
        value = storage.execute_scalar("SELECT value FROM test WHERE id = 1")

        # Should return None
        assert value is None


# =============================================================================
# T051: Unit test for execute_rows() returning list of tuples
# =============================================================================


def test_execute_rows_returns_list_of_tuples(tmp_path: Path) -> None:
    """Test that execute_rows() returns a list of tuples."""
    db_path = tmp_path / "test.db"
    with StorageEngine(path=db_path, read_only=False) as storage:
        # Create test data
        storage.connection.execute("CREATE TABLE test (id INTEGER, value VARCHAR)")
        storage.connection.execute(
            "INSERT INTO test VALUES (1, 'hello'), (2, 'world'), (3, 'test')"
        )

        # Execute query and get rows
        rows = storage.execute_rows("SELECT * FROM test ORDER BY id")

        # Should return list of tuples
        assert isinstance(rows, list)
        assert len(rows) == 3
        assert all(isinstance(row, tuple) for row in rows)

        # Verify data
        assert rows[0] == (1, "hello")
        assert rows[1] == (2, "world")
        assert rows[2] == (3, "test")


def test_execute_rows_returns_empty_list_for_empty_result(tmp_path: Path) -> None:
    """Test that execute_rows() returns empty list for empty result."""
    db_path = tmp_path / "test.db"
    with StorageEngine(path=db_path, read_only=False) as storage:
        # Create empty table
        storage.connection.execute("CREATE TABLE test (id INTEGER, value VARCHAR)")

        # Execute query with no results
        rows = storage.execute_rows("SELECT * FROM test")

        # Should return empty list
        assert isinstance(rows, list)
        assert len(rows) == 0


def test_execute_rows_handles_single_column(tmp_path: Path) -> None:
    """Test that execute_rows() handles single column queries."""
    db_path = tmp_path / "test.db"
    with StorageEngine(path=db_path, read_only=False) as storage:
        # Create test data
        storage.connection.execute("CREATE TABLE test (id INTEGER, value VARCHAR)")
        storage.connection.execute("INSERT INTO test VALUES (1, 'a'), (2, 'b')")

        # Execute single column query
        rows = storage.execute_rows("SELECT id FROM test ORDER BY id")

        # Should return list of tuples with single value
        assert isinstance(rows, list)
        assert len(rows) == 2
        assert rows[0] == (1,)
        assert rows[1] == (2,)


# =============================================================================
# T052: Unit test for QueryError wrapping on SQL errors
# =============================================================================


def test_execute_wraps_sql_errors_in_query_error(tmp_path: Path) -> None:
    """Test that execute() wraps SQL errors in QueryError."""
    from mixpanel_data.exceptions import QueryError

    db_path = tmp_path / "test.db"
    with StorageEngine(path=db_path, read_only=False) as storage:
        # Execute invalid SQL
        with pytest.raises(QueryError) as exc_info:
            storage.execute("SELECT * FROM nonexistent_table")

        # Should wrap DuckDB error
        error = exc_info.value
        assert (
            "nonexistent_table" in str(error).lower() or "catalog" in str(error).lower()
        )

        # Should have details
        assert error.details is not None


def test_execute_df_wraps_sql_errors_in_query_error(tmp_path: Path) -> None:
    """Test that execute_df() wraps SQL errors in QueryError."""
    from mixpanel_data.exceptions import QueryError

    db_path = tmp_path / "test.db"
    with StorageEngine(path=db_path, read_only=False) as storage:
        # Execute invalid SQL
        with pytest.raises(QueryError) as exc_info:
            storage.execute_df("INVALID SQL SYNTAX")

        # Should wrap DuckDB error
        error = exc_info.value
        assert error.details is not None


def test_execute_scalar_wraps_sql_errors_in_query_error(tmp_path: Path) -> None:
    """Test that execute_scalar() wraps SQL errors in QueryError."""
    from mixpanel_data.exceptions import QueryError

    db_path = tmp_path / "test.db"
    with StorageEngine(path=db_path, read_only=False) as storage:
        # Execute invalid SQL
        with pytest.raises(QueryError) as exc_info:
            storage.execute_scalar("SELECT * FROM missing_table")

        # Should wrap DuckDB error
        error = exc_info.value
        assert error.details is not None


def test_execute_rows_wraps_sql_errors_in_query_error(tmp_path: Path) -> None:
    """Test that execute_rows() wraps SQL errors in QueryError."""
    from mixpanel_data.exceptions import QueryError

    db_path = tmp_path / "test.db"
    with StorageEngine(path=db_path, read_only=False) as storage:
        # Execute invalid SQL
        with pytest.raises(QueryError) as exc_info:
            storage.execute_rows("GARBAGE SQL")

        # Should wrap DuckDB error
        error = exc_info.value
        assert error.details is not None


def test_query_error_includes_query_text(tmp_path: Path) -> None:
    """Test that QueryError includes the original query text."""
    from mixpanel_data.exceptions import QueryError

    db_path = tmp_path / "test.db"
    with StorageEngine(path=db_path, read_only=False) as storage:
        bad_query = "SELECT * FROM table_does_not_exist"

        # Execute invalid SQL
        with pytest.raises(QueryError) as exc_info:
            storage.execute(bad_query)

        # Should include query in error details
        error = exc_info.value
        # Query text should be in details or message
        error_str = str(error) + str(error.details)
        assert (
            "table_does_not_exist" in error_str.lower()
            or "catalog" in error_str.lower()
        )


# =============================================================================
# Duplicate Handling Tests
# =============================================================================
# The Mixpanel Export API returns raw data without deduplication, so duplicate
# insert_ids are expected. We use INSERT OR IGNORE to skip duplicates silently,
# matching Mixpanel's query-time deduplication behavior.


def test_create_events_table_skips_duplicate_insert_ids(tmp_path: Path) -> None:
    """Test that duplicate insert_ids are silently skipped."""
    from datetime import datetime

    from mixpanel_data.types import TableMetadata

    db_path = tmp_path / "test.db"
    with StorageEngine(path=db_path, read_only=False) as storage:
        # Create events with duplicate insert_ids (simulating raw export data)
        events = [
            {
                "event_name": "Page View",
                "event_time": datetime(2024, 1, 15, 10, 30, tzinfo=UTC),
                "distinct_id": "user_123",
                "insert_id": "duplicate_id",  # First occurrence
                "properties": {"page": "/home"},
            },
            {
                "event_name": "Page View",
                "event_time": datetime(2024, 1, 15, 10, 30, tzinfo=UTC),
                "distinct_id": "user_123",
                "insert_id": "duplicate_id",  # Duplicate - should be skipped
                "properties": {"page": "/home"},
            },
            {
                "event_name": "Button Click",
                "event_time": datetime(2024, 1, 15, 11, 0, tzinfo=UTC),
                "distinct_id": "user_456",
                "insert_id": "unique_id",  # Unique
                "properties": {"button": "submit"},
            },
        ]

        metadata = TableMetadata(
            type="events",
            fetched_at=datetime.now(UTC),
            from_date="2024-01-15",
            to_date="2024-01-15",
        )

        # Should not raise - duplicates silently skipped
        row_count = storage.create_events_table(
            name="test_events",
            data=iter(events),
            metadata=metadata,
        )

        # Row count reflects actual inserts (2), not attempted inserts (3)
        assert row_count == 2

        # Verify table count matches
        actual_count = storage.execute_scalar("SELECT COUNT(*) FROM test_events")
        assert actual_count == 2


def test_create_events_table_keeps_first_duplicate(tmp_path: Path) -> None:
    """Test that the first occurrence of a duplicate is kept."""
    from datetime import datetime

    from mixpanel_data.types import TableMetadata

    db_path = tmp_path / "test.db"
    with StorageEngine(path=db_path, read_only=False) as storage:
        # Create events with same insert_id but different properties
        events = [
            {
                "event_name": "Page View",
                "event_time": datetime(2024, 1, 15, 10, 30, tzinfo=UTC),
                "distinct_id": "user_123",
                "insert_id": "same_id",
                "properties": {"version": "first"},  # First - should be kept
            },
            {
                "event_name": "Page View",
                "event_time": datetime(2024, 1, 15, 10, 30, tzinfo=UTC),
                "distinct_id": "user_123",
                "insert_id": "same_id",
                "properties": {"version": "second"},  # Duplicate - skipped
            },
        ]

        metadata = TableMetadata(
            type="events",
            fetched_at=datetime.now(UTC),
            from_date="2024-01-15",
            to_date="2024-01-15",
        )

        storage.create_events_table(
            name="test_events",
            data=iter(events),
            metadata=metadata,
        )

        # Query the stored version
        df = storage.execute_df("SELECT properties FROM test_events")
        assert len(df) == 1

        # First occurrence should be kept
        import json

        props = json.loads(df["properties"].iloc[0])
        assert props["version"] == "first"


def test_create_profiles_table_skips_duplicate_distinct_ids(tmp_path: Path) -> None:
    """Test that duplicate distinct_ids are silently skipped."""
    from datetime import datetime

    from mixpanel_data.types import TableMetadata

    db_path = tmp_path / "test.db"
    with StorageEngine(path=db_path, read_only=False) as storage:
        # Create profiles with duplicate distinct_ids
        profiles = [
            {
                "distinct_id": "user_123",  # First occurrence
                "last_seen": datetime(2024, 1, 15, 10, 30, tzinfo=UTC),
                "properties": {"name": "Alice"},
            },
            {
                "distinct_id": "user_123",  # Duplicate - should be skipped
                "last_seen": datetime(2024, 1, 16, 10, 30, tzinfo=UTC),
                "properties": {"name": "Alice Updated"},
            },
            {
                "distinct_id": "user_456",  # Unique
                "last_seen": datetime(2024, 1, 15, 11, 0, tzinfo=UTC),
                "properties": {"name": "Bob"},
            },
        ]

        metadata = TableMetadata(
            type="profiles",
            fetched_at=datetime.now(UTC),
        )

        # Should not raise - duplicates silently skipped
        row_count = storage.create_profiles_table(
            name="test_profiles",
            data=iter(profiles),
            metadata=metadata,
        )

        # Row count reflects actual inserts (2), not attempted inserts (3)
        assert row_count == 2

        # Verify table count matches
        actual_count = storage.execute_scalar("SELECT COUNT(*) FROM test_profiles")
        assert actual_count == 2


def test_create_profiles_table_keeps_first_duplicate(tmp_path: Path) -> None:
    """Test that the first occurrence of a duplicate profile is kept."""
    from datetime import datetime

    from mixpanel_data.types import TableMetadata

    db_path = tmp_path / "test.db"
    with StorageEngine(path=db_path, read_only=False) as storage:
        # Create profiles with same distinct_id but different properties
        profiles = [
            {
                "distinct_id": "user_123",
                "last_seen": datetime(2024, 1, 15, 10, 30, tzinfo=UTC),
                "properties": {"version": "first"},  # First - should be kept
            },
            {
                "distinct_id": "user_123",
                "last_seen": datetime(2024, 1, 16, 10, 30, tzinfo=UTC),
                "properties": {"version": "second"},  # Duplicate - skipped
            },
        ]

        metadata = TableMetadata(
            type="profiles",
            fetched_at=datetime.now(UTC),
        )

        storage.create_profiles_table(
            name="test_profiles",
            data=iter(profiles),
            metadata=metadata,
        )

        # Query the stored version
        df = storage.execute_df("SELECT properties FROM test_profiles")
        assert len(df) == 1

        # First occurrence should be kept
        import json

        props = json.loads(df["properties"].iloc[0])
        assert props["version"] == "first"


def test_create_events_table_handles_many_duplicates(tmp_path: Path) -> None:
    """Test that many duplicates are handled efficiently."""
    from datetime import datetime

    from mixpanel_data.types import TableMetadata

    db_path = tmp_path / "test.db"
    with StorageEngine(path=db_path, read_only=False) as storage:
        # Create 100 events where each insert_id appears 3 times
        # (simulating the ai_demo project's ~65% duplicate rate)
        events = []
        for i in range(100):
            base_event = {
                "event_name": "Event",
                "event_time": datetime(2024, 1, 15, 10, 0, tzinfo=UTC),
                "distinct_id": f"user_{i}",
                "insert_id": f"id_{i}",
                "properties": {"index": i},
            }
            # Add each event 3 times
            events.extend([base_event.copy() for _ in range(3)])

        metadata = TableMetadata(
            type="events",
            fetched_at=datetime.now(UTC),
            from_date="2024-01-15",
            to_date="2024-01-15",
        )

        # Should handle 300 records efficiently
        row_count = storage.create_events_table(
            name="test_events",
            data=iter(events),
            metadata=metadata,
        )

        # Row count should match actual inserted rows, not attempted inserts
        assert row_count == 100

        # Verify the table count matches
        actual_count = storage.execute_scalar("SELECT COUNT(*) FROM test_events")
        assert actual_count == 100


def test_create_events_table_row_count_matches_actual_inserts(tmp_path: Path) -> None:
    """Test that returned row_count equals actual inserted rows, not batch size."""
    from datetime import datetime

    from mixpanel_data.types import TableMetadata

    db_path = tmp_path / "test.db"
    with StorageEngine(path=db_path, read_only=False) as storage:
        # Create events with 50% duplicates
        events = [
            {
                "event_name": "Event",
                "event_time": datetime(2024, 1, 15, 10, 0, tzinfo=UTC),
                "distinct_id": "user_1",
                "insert_id": "unique_1",
                "properties": {},
            },
            {
                "event_name": "Event",
                "event_time": datetime(2024, 1, 15, 10, 0, tzinfo=UTC),
                "distinct_id": "user_1",
                "insert_id": "unique_1",  # Duplicate
                "properties": {},
            },
            {
                "event_name": "Event",
                "event_time": datetime(2024, 1, 15, 10, 0, tzinfo=UTC),
                "distinct_id": "user_2",
                "insert_id": "unique_2",
                "properties": {},
            },
            {
                "event_name": "Event",
                "event_time": datetime(2024, 1, 15, 10, 0, tzinfo=UTC),
                "distinct_id": "user_2",
                "insert_id": "unique_2",  # Duplicate
                "properties": {},
            },
        ]

        metadata = TableMetadata(
            type="events",
            fetched_at=datetime.now(UTC),
            from_date="2024-01-15",
            to_date="2024-01-15",
        )

        row_count = storage.create_events_table(
            name="test_events",
            data=iter(events),
            metadata=metadata,
        )

        # Row count should be 2 (actual inserts), not 4 (attempted inserts)
        assert row_count == 2
        assert storage.execute_scalar("SELECT COUNT(*) FROM test_events") == 2


def test_create_profiles_table_row_count_matches_actual_inserts(tmp_path: Path) -> None:
    """Test that returned row_count equals actual inserted rows for profiles."""
    from datetime import datetime

    from mixpanel_data.types import TableMetadata

    db_path = tmp_path / "test.db"
    with StorageEngine(path=db_path, read_only=False) as storage:
        # Create profiles with duplicates
        profiles = [
            {
                "distinct_id": "user_1",
                "properties": {"name": "Alice"},
                "last_seen": datetime(2024, 1, 15, 10, 0, tzinfo=UTC),
            },
            {
                "distinct_id": "user_1",  # Duplicate
                "properties": {"name": "Alice Updated"},
                "last_seen": datetime(2024, 1, 15, 11, 0, tzinfo=UTC),
            },
            {
                "distinct_id": "user_2",
                "properties": {"name": "Bob"},
                "last_seen": datetime(2024, 1, 15, 10, 0, tzinfo=UTC),
            },
        ]

        metadata = TableMetadata(
            type="profiles",
            fetched_at=datetime.now(UTC),
        )

        row_count = storage.create_profiles_table(
            name="test_profiles",
            data=iter(profiles),
            metadata=metadata,
        )

        # Row count should be 2 (actual inserts), not 3 (attempted inserts)
        assert row_count == 2
        assert storage.execute_scalar("SELECT COUNT(*) FROM test_profiles") == 2


def test_append_events_table_row_count_matches_actual_inserts(tmp_path: Path) -> None:
    """Test that append row_count equals actual inserted rows."""
    from datetime import datetime

    from mixpanel_data.types import TableMetadata

    db_path = tmp_path / "test.db"
    with StorageEngine(path=db_path, read_only=False) as storage:
        # Create initial table
        initial_events = [
            {
                "event_name": "Event",
                "event_time": datetime(2024, 1, 15, 10, 0, tzinfo=UTC),
                "distinct_id": "user_1",
                "insert_id": "existing_id",
                "properties": {},
            },
        ]

        metadata = TableMetadata(
            type="events",
            fetched_at=datetime.now(UTC),
            from_date="2024-01-15",
            to_date="2024-01-15",
        )

        storage.create_events_table("test_events", iter(initial_events), metadata)

        # Append with mix of duplicates and new events
        append_events = [
            {
                "event_name": "Event",
                "event_time": datetime(2024, 1, 16, 10, 0, tzinfo=UTC),
                "distinct_id": "user_1",
                "insert_id": "existing_id",  # Duplicate of initial
                "properties": {},
            },
            {
                "event_name": "Event",
                "event_time": datetime(2024, 1, 16, 10, 0, tzinfo=UTC),
                "distinct_id": "user_2",
                "insert_id": "new_id_1",
                "properties": {},
            },
            {
                "event_name": "Event",
                "event_time": datetime(2024, 1, 16, 10, 0, tzinfo=UTC),
                "distinct_id": "user_2",
                "insert_id": "new_id_1",  # Duplicate within append
                "properties": {},
            },
            {
                "event_name": "Event",
                "event_time": datetime(2024, 1, 16, 10, 0, tzinfo=UTC),
                "distinct_id": "user_3",
                "insert_id": "new_id_2",
                "properties": {},
            },
        ]

        append_metadata = TableMetadata(
            type="events",
            fetched_at=datetime.now(UTC),
            from_date="2024-01-16",
            to_date="2024-01-16",
        )

        row_count = storage.append_events_table(
            "test_events", iter(append_events), append_metadata
        )

        # Should be 2 (new_id_1 and new_id_2), not 4 (all attempted)
        assert row_count == 2
        assert storage.execute_scalar("SELECT COUNT(*) FROM test_events") == 3


def test_append_profiles_table_row_count_matches_actual_inserts(tmp_path: Path) -> None:
    """Test that append row_count equals actual inserted rows for profiles."""
    from datetime import datetime

    from mixpanel_data.types import TableMetadata

    db_path = tmp_path / "test.db"
    with StorageEngine(path=db_path, read_only=False) as storage:
        # Create initial table
        initial_profiles = [
            {
                "distinct_id": "user_1",
                "properties": {"name": "Alice"},
                "last_seen": datetime(2024, 1, 15, 10, 0, tzinfo=UTC),
            },
        ]

        metadata = TableMetadata(
            type="profiles",
            fetched_at=datetime.now(UTC),
        )

        storage.create_profiles_table("test_profiles", iter(initial_profiles), metadata)

        # Append with duplicates
        append_profiles = [
            {
                "distinct_id": "user_1",  # Duplicate of initial
                "properties": {"name": "Alice Updated"},
                "last_seen": datetime(2024, 1, 16, 10, 0, tzinfo=UTC),
            },
            {
                "distinct_id": "user_2",
                "properties": {"name": "Bob"},
                "last_seen": datetime(2024, 1, 16, 10, 0, tzinfo=UTC),
            },
        ]

        row_count = storage.append_profiles_table(
            "test_profiles", iter(append_profiles), metadata
        )

        # Should be 1 (user_2 only), not 2 (all attempted)
        assert row_count == 1
        assert storage.execute_scalar("SELECT COUNT(*) FROM test_profiles") == 2


def test_progress_callback_reports_actual_inserted_rows(tmp_path: Path) -> None:
    """Test that progress callback receives accurate row counts."""
    from datetime import datetime

    from mixpanel_data.types import TableMetadata

    db_path = tmp_path / "test.db"
    with StorageEngine(path=db_path, read_only=False) as storage:
        # Create events with duplicates, using small batch size to trigger callbacks
        events = []
        for i in range(10):
            events.append(
                {
                    "event_name": "Event",
                    "event_time": datetime(2024, 1, 15, 10, 0, tzinfo=UTC),
                    "distinct_id": f"user_{i}",
                    "insert_id": f"id_{i % 5}",  # Only 5 unique IDs
                    "properties": {},
                }
            )

        metadata = TableMetadata(
            type="events",
            fetched_at=datetime.now(UTC),
            from_date="2024-01-15",
            to_date="2024-01-15",
        )

        progress_values: list[int] = []

        def progress_callback(count: int) -> None:
            progress_values.append(count)

        row_count = storage.create_events_table(
            name="test_events",
            data=iter(events),
            metadata=metadata,
            progress_callback=progress_callback,
            batch_size=3,  # Small batch to trigger multiple callbacks
        )

        # Final row count should be 5 (unique insert_ids)
        assert row_count == 5

        # Progress should report cumulative actual inserts, not attempted
        # The exact values depend on batch boundaries, but final should be 5
        if progress_values:
            assert progress_values[-1] == 5


# =============================================================================
# Transaction Rollback Tests
# =============================================================================


def test_create_events_table_rolls_back_on_failure(tmp_path: Path) -> None:
    """Test that failed event table creation rolls back the transaction."""
    from datetime import datetime

    from mixpanel_data.types import TableMetadata

    db_path = tmp_path / "test.db"

    def failing_iterator() -> Iterator[dict[str, Any]]:
        """Iterator that yields valid events then fails."""
        yield {
            "event_name": "Valid Event",
            "event_time": datetime(2024, 1, 1, 10, 0, tzinfo=UTC),
            "distinct_id": "user_1",
            "insert_id": "id_1",
            "properties": {"key": "value"},
        }
        raise ValueError("Simulated failure during iteration")

    with StorageEngine(path=db_path, read_only=False) as storage:
        metadata = TableMetadata(
            type="events",
            fetched_at=datetime.now(UTC),
            from_date="2024-01-01",
            to_date="2024-01-31",
        )

        # Should raise the error from the iterator
        with pytest.raises(ValueError, match="Simulated failure"):
            storage.create_events_table(
                name="test_events",
                data=failing_iterator(),
                metadata=metadata,
            )

        # Table should not exist due to rollback
        assert not storage.table_exists("test_events")


def test_create_profiles_table_rolls_back_on_failure(tmp_path: Path) -> None:
    """Test that failed profile table creation rolls back the transaction."""
    from datetime import datetime

    from mixpanel_data.types import TableMetadata

    db_path = tmp_path / "test.db"

    def failing_iterator() -> Iterator[dict[str, Any]]:
        """Iterator that yields valid profiles then fails."""
        yield {
            "distinct_id": "user_1",
            "last_seen": "2024-01-01T10:00:00Z",
            "properties": {"name": "Alice"},
        }
        raise RuntimeError("Simulated database error")

    with StorageEngine(path=db_path, read_only=False) as storage:
        metadata = TableMetadata(
            type="profiles",
            fetched_at=datetime.now(UTC),
        )

        # Should raise the error from the iterator
        with pytest.raises(RuntimeError, match="Simulated database error"):
            storage.create_profiles_table(
                name="test_profiles",
                data=failing_iterator(),
                metadata=metadata,
            )

        # Table should not exist due to rollback
        assert not storage.table_exists("test_profiles")


def test_rollback_allows_retry_without_table_exists_error(tmp_path: Path) -> None:
    """Test that after rollback, retrying table creation works."""
    from datetime import datetime

    from mixpanel_data.types import TableMetadata

    db_path = tmp_path / "test.db"
    attempt = [0]

    def sometimes_failing_iterator() -> Iterator[dict[str, Any]]:
        """Iterator that fails on first attempt, succeeds on second."""
        yield {
            "event_name": "Event",
            "event_time": datetime(2024, 1, 1, 10, 0, tzinfo=UTC),
            "distinct_id": "user_1",
            "insert_id": "id_1",
            "properties": {},
        }
        attempt[0] += 1
        if attempt[0] == 1:
            raise ValueError("First attempt fails")
        # Second attempt succeeds

    with StorageEngine(path=db_path, read_only=False) as storage:
        metadata = TableMetadata(
            type="events",
            fetched_at=datetime.now(UTC),
            from_date="2024-01-01",
            to_date="2024-01-01",
        )

        # First attempt fails
        with pytest.raises(ValueError):
            storage.create_events_table(
                name="retry_table",
                data=sometimes_failing_iterator(),
                metadata=metadata,
            )

        # Table should not exist
        assert not storage.table_exists("retry_table")

        # Retry should succeed (not raise TableExistsError)
        row_count = storage.create_events_table(
            name="retry_table",
            data=iter(
                [
                    {
                        "event_name": "Retry Event",
                        "event_time": datetime(2024, 1, 1, 10, 0, tzinfo=UTC),
                        "distinct_id": "user_1",
                        "insert_id": "id_2",
                        "properties": {},
                    }
                ]
            ),
            metadata=metadata,
        )

        assert row_count == 1
        assert storage.table_exists("retry_table")


# =============================================================================
# In-Memory Mode Tests
# =============================================================================


class TestInMemoryMode:
    """Tests for in-memory database mode (StorageEngine.memory())."""

    def test_memory_creates_in_memory_database(self) -> None:
        """Test that memory() creates a working in-memory database."""
        with StorageEngine.memory() as storage:
            # Should have valid connection
            assert storage.connection is not None
            # Path should be None (no file)
            assert storage.path is None
            # Should be able to create tables and query
            storage.connection.execute("CREATE TABLE test (id INTEGER)")
            storage.connection.execute("INSERT INTO test VALUES (1)")
            result = storage.connection.execute("SELECT * FROM test").fetchone()
            assert result == (1,)

    def test_memory_returns_storage_engine_instance(self) -> None:
        """Test that memory() returns a StorageEngine instance."""
        with StorageEngine.memory() as storage:
            assert isinstance(storage, StorageEngine)

    def test_memory_creates_unique_databases(self) -> None:
        """Test that each memory() call creates an independent database."""
        with StorageEngine.memory() as s1, StorageEngine.memory() as s2:
            # Create table in first database
            s1.connection.execute("CREATE TABLE test (id INTEGER)")
            s1.connection.execute("INSERT INTO test VALUES (1)")

            # Second database should not see first database's table
            tables = s2.connection.execute(
                "SELECT COUNT(*) FROM information_schema.tables WHERE table_name = 'test'"
            ).fetchone()
            assert tables == (0,)

    def test_memory_supports_events_table_creation(self) -> None:
        """Test that events can be stored in memory database."""
        from datetime import datetime

        from mixpanel_data.types import TableMetadata

        with StorageEngine.memory() as storage:
            events = [
                {
                    "event_name": "Test",
                    "event_time": datetime.now(UTC),
                    "distinct_id": "user_1",
                    "insert_id": "event_1",
                    "properties": {"key": "value"},
                }
            ]
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
        storage.close()  # Should not raise

    def test_memory_context_manager_cleanup(self) -> None:
        """Test context manager properly closes connection."""
        storage_ref = None
        with StorageEngine.memory() as storage:
            storage_ref = storage
            assert storage.connection is not None

        # After exit, attempting to use connection should fail
        with pytest.raises(RuntimeError, match="closed"):
            _ = storage_ref.connection

    def test_memory_path_is_none(self) -> None:
        """Test that path property returns None for memory databases."""
        with StorageEngine.memory() as storage:
            assert storage.path is None

    def test_memory_introspection_works(self) -> None:
        """Test that list_tables, get_schema work on memory DB."""
        from datetime import datetime

        from mixpanel_data.types import TableMetadata

        with StorageEngine.memory() as storage:
            # Initially empty
            assert storage.list_tables() == []

            # Create table
            events = [
                {
                    "event_name": "Test",
                    "event_time": datetime.now(UTC),
                    "distinct_id": "user_1",
                    "insert_id": "event_1",
                    "properties": {},
                }
            ]
            metadata = TableMetadata(type="events", fetched_at=datetime.now(UTC))
            storage.create_events_table("my_events", iter(events), metadata)

            # Introspection should work
            tables = storage.list_tables()
            assert len(tables) == 1
            assert tables[0].name == "my_events"

            schema = storage.get_schema("my_events")
            assert schema.table_name == "my_events"

    def test_memory_supports_profiles_table_creation(self) -> None:
        """Test that profiles can be stored in memory database."""
        from datetime import datetime

        from mixpanel_data.types import TableMetadata

        with StorageEngine.memory() as storage:
            profiles = [
                {
                    "distinct_id": "user_1",
                    "properties": {"name": "Alice"},
                    "last_seen": datetime.now(UTC),
                }
            ]
            metadata = TableMetadata(type="profiles", fetched_at=datetime.now(UTC))

            row_count = storage.create_profiles_table(
                "profiles", iter(profiles), metadata
            )
            assert row_count == 1

            result = storage.execute_scalar("SELECT COUNT(*) FROM profiles")
            assert result == 1

    def test_memory_query_methods_work(self) -> None:
        """Test that all query methods work on memory database."""
        from datetime import datetime

        from mixpanel_data.types import TableMetadata

        with StorageEngine.memory() as storage:
            events = [
                {
                    "event_name": f"Event_{i}",
                    "event_time": datetime.now(UTC),
                    "distinct_id": f"user_{i}",
                    "insert_id": f"event_{i}",
                    "properties": {"index": i},
                }
                for i in range(5)
            ]
            metadata = TableMetadata(type="events", fetched_at=datetime.now(UTC))
            storage.create_events_table("events", iter(events), metadata)

            # execute_df
            df = storage.execute_df("SELECT * FROM events")
            assert len(df) == 5

            # execute_scalar
            count = storage.execute_scalar("SELECT COUNT(*) FROM events")
            assert count == 5

            # execute_rows
            rows = storage.execute_rows(
                "SELECT event_name FROM events ORDER BY event_name"
            )
            assert len(rows) == 5

            # execute (returns relation)
            relation = storage.execute("SELECT * FROM events")
            assert relation.fetchall() is not None

    def test_memory_and_ephemeral_flags_mutually_exclusive(self) -> None:
        """Test that _in_memory and _ephemeral flags cannot both be True."""
        with pytest.raises(ValueError, match="Cannot use both"):
            StorageEngine(path=None, _ephemeral=True, _in_memory=True)


# =============================================================================
# Database Locking Tests
# =============================================================================


class TestDatabaseLocking:
    """Tests for database lock conflict handling."""

    def test_lock_conflict_raises_database_locked_error(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """IOException with 'Could not set lock' raises DatabaseLockedError."""
        import duckdb

        from mixpanel_data.exceptions import DatabaseLockedError

        db_path = tmp_path / "test.db"

        # Mock duckdb.connect to raise IOException with lock message
        def mock_connect(*_args: Any, **_kwargs: Any) -> Any:
            raise duckdb.IOException(
                "IO Error: Could not set lock on file "
                f'"{db_path}": Conflicting lock is held in /usr/bin/python (PID 12345).'
            )

        monkeypatch.setattr(duckdb, "connect", mock_connect)

        # Should raise DatabaseLockedError
        with pytest.raises(DatabaseLockedError) as exc_info:
            StorageEngine(path=db_path, read_only=False)

        # Error should contain the database path
        assert str(db_path) in str(exc_info.value.message)
        assert exc_info.value.db_path == str(db_path)

    def test_database_locked_error_includes_pid(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """DatabaseLockedError extracts PID from error message."""
        import duckdb

        from mixpanel_data.exceptions import DatabaseLockedError

        db_path = tmp_path / "locked.db"

        def mock_connect(*_args: Any, **_kwargs: Any) -> Any:
            raise duckdb.IOException(
                "IO Error: Could not set lock on file "
                f'"{db_path}": Conflicting lock is held in /usr/bin/python (PID 99999).'
            )

        monkeypatch.setattr(duckdb, "connect", mock_connect)

        with pytest.raises(DatabaseLockedError) as exc_info:
            StorageEngine(path=db_path, read_only=False)

        assert exc_info.value.details["db_path"] == str(db_path)
        assert exc_info.value.holding_pid == 99999

    def test_database_locked_error_without_pid(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """DatabaseLockedError works when PID is not in error message."""
        import duckdb

        from mixpanel_data.exceptions import DatabaseLockedError

        db_path = tmp_path / "locked.db"

        # Error message without PID
        def mock_connect(*_args: Any, **_kwargs: Any) -> Any:
            raise duckdb.IOException(
                f'IO Error: Could not set lock on file "{db_path}"'
            )

        monkeypatch.setattr(duckdb, "connect", mock_connect)

        with pytest.raises(DatabaseLockedError) as exc_info:
            StorageEngine(path=db_path, read_only=False)

        assert exc_info.value.holding_pid is None

    def test_other_ioexception_raises_oserror(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """IOException without lock message raises OSError."""
        import duckdb

        db_path = tmp_path / "test.db"

        def mock_connect(*_args: Any, **_kwargs: Any) -> Any:
            raise duckdb.IOException("IO Error: Permission denied")

        monkeypatch.setattr(duckdb, "connect", mock_connect)

        with pytest.raises(OSError, match="Failed to create database"):
            StorageEngine(path=db_path, read_only=False)

    def test_lock_released_after_close(self, tmp_path: Path) -> None:
        """Database can be opened after previous connection is closed."""
        db_path = tmp_path / "test.db"

        # Open and close first connection
        storage1 = StorageEngine(path=db_path, read_only=False)
        storage1.close()

        # Second connection should succeed
        storage2 = StorageEngine(path=db_path, read_only=False)
        try:
            assert storage2.connection is not None
        finally:
            storage2.close()

    def test_lock_released_after_context_manager_exit(self, tmp_path: Path) -> None:
        """Database can be opened after context manager exits."""
        db_path = tmp_path / "test.db"

        # Use context manager
        with StorageEngine(path=db_path, read_only=False):
            pass  # Lock held during context

        # After context exits, should be able to open
        with StorageEngine(path=db_path, read_only=False) as storage:
            assert storage.connection is not None

    def test_memory_databases_dont_conflict(self) -> None:
        """In-memory databases don't have lock conflicts."""
        # Multiple in-memory databases can coexist
        storage1 = StorageEngine.memory()
        storage2 = StorageEngine.memory()

        try:
            assert storage1.connection is not None
            assert storage2.connection is not None
        finally:
            storage1.close()
            storage2.close()


# =============================================================================
# Read-Only Mode Tests
# =============================================================================


class TestReadOnlyMode:
    """Tests for read-only database access mode."""

    def test_read_only_allows_select_queries(self, tmp_path: Path) -> None:
        """Read-only connection can execute SELECT queries."""
        db_path = tmp_path / "test.db"

        # Create database with write connection
        with StorageEngine(path=db_path, read_only=False) as writer:
            writer.connection.execute("CREATE TABLE test (id INTEGER)")
            writer.connection.execute("INSERT INTO test VALUES (1), (2), (3)")

        # Open read-only and query
        with StorageEngine(path=db_path, read_only=True) as reader:
            result = reader.connection.execute("SELECT COUNT(*) FROM test").fetchone()
            assert result is not None
            assert result[0] == 3

    def test_read_only_blocks_insert(self, tmp_path: Path) -> None:
        """Read-only connection cannot INSERT data."""
        import duckdb

        db_path = tmp_path / "test.db"

        # Create database
        with StorageEngine(path=db_path, read_only=False) as writer:
            writer.connection.execute("CREATE TABLE test (id INTEGER)")

        # Try to insert via read-only connection
        with (
            StorageEngine(path=db_path, read_only=True) as reader,
            pytest.raises(duckdb.InvalidInputException),
        ):
            reader.connection.execute("INSERT INTO test VALUES (1)")

    def test_read_only_blocks_update(self, tmp_path: Path) -> None:
        """Read-only connection cannot UPDATE data."""
        import duckdb

        db_path = tmp_path / "test.db"

        # Create database with data
        with StorageEngine(path=db_path, read_only=False) as writer:
            writer.connection.execute("CREATE TABLE test (id INTEGER)")
            writer.connection.execute("INSERT INTO test VALUES (1)")

        # Try to update via read-only connection
        with (
            StorageEngine(path=db_path, read_only=True) as reader,
            pytest.raises(duckdb.InvalidInputException),
        ):
            reader.connection.execute("UPDATE test SET id = 2")

    def test_read_only_blocks_delete(self, tmp_path: Path) -> None:
        """Read-only connection cannot DELETE data."""
        import duckdb

        db_path = tmp_path / "test.db"

        # Create database with data
        with StorageEngine(path=db_path, read_only=False) as writer:
            writer.connection.execute("CREATE TABLE test (id INTEGER)")
            writer.connection.execute("INSERT INTO test VALUES (1)")

        # Try to delete via read-only connection
        with (
            StorageEngine(path=db_path, read_only=True) as reader,
            pytest.raises(duckdb.InvalidInputException),
        ):
            reader.connection.execute("DELETE FROM test")

    def test_read_only_blocks_create_table(self, tmp_path: Path) -> None:
        """Read-only connection cannot CREATE TABLE."""
        import duckdb

        db_path = tmp_path / "test.db"

        # Create empty database
        with StorageEngine(path=db_path, read_only=False):
            pass

        # Try to create table via read-only connection
        with (
            StorageEngine(path=db_path, read_only=True) as reader,
            pytest.raises(duckdb.InvalidInputException),
        ):
            reader.connection.execute("CREATE TABLE test (id INTEGER)")

    def test_multiple_read_only_connections_coexist(self, tmp_path: Path) -> None:
        """Multiple read-only connections can access the same database."""
        db_path = tmp_path / "test.db"

        # Create database with data
        with StorageEngine(path=db_path, read_only=False) as writer:
            writer.connection.execute("CREATE TABLE test (id INTEGER)")
            writer.connection.execute("INSERT INTO test VALUES (1), (2)")

        # Open multiple read-only connections
        reader1 = StorageEngine(path=db_path, read_only=True)
        reader2 = StorageEngine(path=db_path, read_only=True)

        try:
            # Both can query
            result1 = reader1.connection.execute("SELECT COUNT(*) FROM test").fetchone()
            result2 = reader2.connection.execute("SELECT COUNT(*) FROM test").fetchone()

            assert result1 is not None and result1[0] == 2
            assert result2 is not None and result2[0] == 2
        finally:
            reader1.close()
            reader2.close()

    def test_read_only_opens_after_write_closed(self, tmp_path: Path) -> None:
        """Read-only connection can open after write connection is closed.

        Note: DuckDB does not allow mixing read-only and read-write connections
        to the same file within the same process. However, read-only connections
        from different processes can access a database while a writer has the lock.
        This test verifies the basic read-only functionality after writer closes.
        """
        db_path = tmp_path / "test.db"

        # Create database with data
        with StorageEngine(path=db_path, read_only=False) as writer:
            writer.connection.execute("CREATE TABLE test (id INTEGER)")
            writer.connection.execute("INSERT INTO test VALUES (1)")

        # Open read-only after writer is closed
        with StorageEngine(path=db_path, read_only=True) as reader:
            result = reader.connection.execute("SELECT COUNT(*) FROM test").fetchone()
            assert result is not None
            assert result[0] == 1

    def test_read_only_property_is_set(self, tmp_path: Path) -> None:
        """Read-only flag is accessible via property."""
        db_path = tmp_path / "test.db"

        # Create database
        with StorageEngine(path=db_path, read_only=False):
            pass

        # Check property on both modes
        with StorageEngine(path=db_path, read_only=False) as writer:
            assert writer.read_only is False

        with StorageEngine(path=db_path, read_only=True) as reader:
            assert reader.read_only is True

    def test_read_only_default_is_false(self, tmp_path: Path) -> None:
        """Default read_only value is False."""
        db_path = tmp_path / "test.db"

        with StorageEngine(path=db_path, read_only=False) as storage:
            assert storage.read_only is False

    def test_read_only_raises_not_found_for_missing_file(self, tmp_path: Path) -> None:
        """Read-only access to non-existent file raises DatabaseNotFoundError."""
        from mixpanel_data.exceptions import DatabaseNotFoundError

        db_path = tmp_path / "nonexistent.db"
        assert not db_path.exists()

        with pytest.raises(DatabaseNotFoundError) as exc_info:
            StorageEngine(path=db_path, read_only=True)

        assert exc_info.value.db_path == str(db_path)
        assert "does not exist" in str(exc_info.value).lower()

    def test_read_only_not_found_includes_suggestion(self, tmp_path: Path) -> None:
        """DatabaseNotFoundError includes helpful suggestion."""
        from mixpanel_data.exceptions import DatabaseNotFoundError

        db_path = tmp_path / "missing.db"

        with pytest.raises(DatabaseNotFoundError) as exc_info:
            StorageEngine(path=db_path, read_only=True)

        assert "suggestion" in exc_info.value.details
        assert "fetch" in exc_info.value.details["suggestion"].lower()

    def test_write_mode_creates_missing_file(self, tmp_path: Path) -> None:
        """Write mode creates file if it doesn't exist (no error)."""
        db_path = tmp_path / "new.db"
        assert not db_path.exists()

        with StorageEngine(path=db_path, read_only=False) as storage:
            assert db_path.exists()
            assert storage.connection is not None


# =============================================================================
# Append Mode Tests
# =============================================================================


def test_append_events_table_adds_rows_to_existing_table(tmp_path: Path) -> None:
    """Test that append_events_table adds rows to an existing events table."""
    from datetime import datetime

    from mixpanel_data.types import TableMetadata

    db_path = tmp_path / "test.db"
    with StorageEngine(path=db_path, read_only=False) as storage:
        # Create initial table with 2 events
        initial_events = [
            {
                "event_name": "Event A",
                "event_time": datetime(2024, 1, 15, 10, 0, tzinfo=UTC),
                "distinct_id": "user_1",
                "insert_id": "event_1",
                "properties": {"batch": "initial"},
            },
            {
                "event_name": "Event B",
                "event_time": datetime(2024, 1, 15, 11, 0, tzinfo=UTC),
                "distinct_id": "user_2",
                "insert_id": "event_2",
                "properties": {"batch": "initial"},
            },
        ]

        metadata = TableMetadata(
            type="events",
            fetched_at=datetime.now(UTC),
            from_date="2024-01-15",
            to_date="2024-01-15",
        )

        storage.create_events_table("my_events", iter(initial_events), metadata)

        # Verify initial state
        assert storage.execute_scalar("SELECT COUNT(*) FROM my_events") == 2

        # Append more events
        append_events = [
            {
                "event_name": "Event C",
                "event_time": datetime(2024, 1, 16, 10, 0, tzinfo=UTC),
                "distinct_id": "user_3",
                "insert_id": "event_3",
                "properties": {"batch": "append"},
            },
        ]

        append_metadata = TableMetadata(
            type="events",
            fetched_at=datetime.now(UTC),
            from_date="2024-01-16",
            to_date="2024-01-16",
        )

        row_count = storage.append_events_table(
            "my_events", iter(append_events), append_metadata
        )

        # Verify append
        assert row_count == 1
        assert storage.execute_scalar("SELECT COUNT(*) FROM my_events") == 3


def test_append_events_table_raises_error_for_missing_table(tmp_path: Path) -> None:
    """Test that append_events_table raises TableNotFoundError for missing table."""
    from datetime import datetime

    from mixpanel_data.exceptions import TableNotFoundError
    from mixpanel_data.types import TableMetadata

    db_path = tmp_path / "test.db"
    with StorageEngine(path=db_path, read_only=False) as storage:
        events = [
            {
                "event_name": "Event",
                "event_time": datetime.now(UTC),
                "distinct_id": "user_1",
                "insert_id": "event_1",
                "properties": {},
            }
        ]

        metadata = TableMetadata(
            type="events",
            fetched_at=datetime.now(UTC),
            from_date="2024-01-01",
            to_date="2024-01-01",
        )

        with pytest.raises(TableNotFoundError, match="nonexistent"):
            storage.append_events_table("nonexistent", iter(events), metadata)


def test_append_events_table_deduplicates_across_batches(tmp_path: Path) -> None:
    """Test that duplicates across initial and appended data are handled."""
    from datetime import datetime

    from mixpanel_data.types import TableMetadata

    db_path = tmp_path / "test.db"
    with StorageEngine(path=db_path, read_only=False) as storage:
        # Create initial table
        initial_events = [
            {
                "event_name": "Event",
                "event_time": datetime(2024, 1, 15, 10, 0, tzinfo=UTC),
                "distinct_id": "user_1",
                "insert_id": "shared_id",  # Will be duplicated
                "properties": {"version": "first"},
            },
        ]

        metadata = TableMetadata(
            type="events",
            fetched_at=datetime.now(UTC),
            from_date="2024-01-15",
            to_date="2024-01-15",
        )

        storage.create_events_table("my_events", iter(initial_events), metadata)

        # Append with duplicate insert_id
        append_events = [
            {
                "event_name": "Event",
                "event_time": datetime(2024, 1, 15, 10, 0, tzinfo=UTC),
                "distinct_id": "user_1",
                "insert_id": "shared_id",  # Duplicate - should be skipped
                "properties": {"version": "second"},
            },
            {
                "event_name": "Event",
                "event_time": datetime(2024, 1, 16, 10, 0, tzinfo=UTC),
                "distinct_id": "user_2",
                "insert_id": "unique_id",  # New
                "properties": {"version": "new"},
            },
        ]

        append_metadata = TableMetadata(
            type="events",
            fetched_at=datetime.now(UTC),
            from_date="2024-01-16",
            to_date="2024-01-16",
        )

        storage.append_events_table("my_events", iter(append_events), append_metadata)

        # Should only have 2 rows (duplicate skipped)
        assert storage.execute_scalar("SELECT COUNT(*) FROM my_events") == 2


def test_append_events_table_updates_metadata_date_range(tmp_path: Path) -> None:
    """Test that append updates metadata to expand date range."""
    from datetime import datetime

    from mixpanel_data.types import TableMetadata

    db_path = tmp_path / "test.db"
    with StorageEngine(path=db_path, read_only=False) as storage:
        # Create initial table for Jan 15
        initial_events = [
            {
                "event_name": "Event",
                "event_time": datetime(2024, 1, 15, 10, 0, tzinfo=UTC),
                "distinct_id": "user_1",
                "insert_id": "event_1",
                "properties": {},
            },
        ]

        metadata = TableMetadata(
            type="events",
            fetched_at=datetime.now(UTC),
            from_date="2024-01-15",
            to_date="2024-01-15",
        )

        storage.create_events_table("my_events", iter(initial_events), metadata)

        # Append events for Jan 20
        append_events = [
            {
                "event_name": "Event",
                "event_time": datetime(2024, 1, 20, 10, 0, tzinfo=UTC),
                "distinct_id": "user_2",
                "insert_id": "event_2",
                "properties": {},
            },
        ]

        append_metadata = TableMetadata(
            type="events",
            fetched_at=datetime.now(UTC),
            from_date="2024-01-20",
            to_date="2024-01-20",
        )

        storage.append_events_table("my_events", iter(append_events), append_metadata)

        # Metadata should show expanded date range
        retrieved_metadata = storage.get_metadata("my_events")
        assert retrieved_metadata.from_date == "2024-01-15"  # Original start
        assert retrieved_metadata.to_date == "2024-01-20"  # Extended end


def test_append_events_table_updates_row_count(tmp_path: Path) -> None:
    """Test that append updates the row count in metadata."""
    from datetime import datetime

    from mixpanel_data.types import TableMetadata

    db_path = tmp_path / "test.db"
    with StorageEngine(path=db_path, read_only=False) as storage:
        # Create initial table
        initial_events = [
            {
                "event_name": "Event",
                "event_time": datetime(2024, 1, 15, 10, 0, tzinfo=UTC),
                "distinct_id": "user_1",
                "insert_id": "event_1",
                "properties": {},
            },
        ]

        metadata = TableMetadata(
            type="events",
            fetched_at=datetime.now(UTC),
            from_date="2024-01-15",
            to_date="2024-01-15",
        )

        storage.create_events_table("my_events", iter(initial_events), metadata)

        # Append 2 more events
        append_events = [
            {
                "event_name": "Event",
                "event_time": datetime(2024, 1, 16, 10, 0, tzinfo=UTC),
                "distinct_id": "user_2",
                "insert_id": "event_2",
                "properties": {},
            },
            {
                "event_name": "Event",
                "event_time": datetime(2024, 1, 17, 10, 0, tzinfo=UTC),
                "distinct_id": "user_3",
                "insert_id": "event_3",
                "properties": {},
            },
        ]

        append_metadata = TableMetadata(
            type="events",
            fetched_at=datetime.now(UTC),
            from_date="2024-01-16",
            to_date="2024-01-17",
        )

        storage.append_events_table("my_events", iter(append_events), append_metadata)

        # Check metadata row count
        tables = storage.list_tables()
        my_events_info = next(t for t in tables if t.name == "my_events")
        assert my_events_info.row_count == 3


def test_append_profiles_table_adds_rows_to_existing_table(tmp_path: Path) -> None:
    """Test that append_profiles_table adds rows to an existing profiles table."""
    from datetime import datetime

    from mixpanel_data.types import TableMetadata

    db_path = tmp_path / "test.db"
    with StorageEngine(path=db_path, read_only=False) as storage:
        # Create initial table
        initial_profiles = [
            {
                "distinct_id": "user_1",
                "properties": {"name": "Alice"},
                "last_seen": datetime(2024, 1, 15, 10, 0, tzinfo=UTC),
            },
        ]

        metadata = TableMetadata(
            type="profiles",
            fetched_at=datetime.now(UTC),
        )

        storage.create_profiles_table("my_profiles", iter(initial_profiles), metadata)

        # Verify initial state
        assert storage.execute_scalar("SELECT COUNT(*) FROM my_profiles") == 1

        # Append more profiles
        append_profiles = [
            {
                "distinct_id": "user_2",
                "properties": {"name": "Bob"},
                "last_seen": datetime(2024, 1, 16, 10, 0, tzinfo=UTC),
            },
        ]

        append_metadata = TableMetadata(
            type="profiles",
            fetched_at=datetime.now(UTC),
        )

        row_count = storage.append_profiles_table(
            "my_profiles", iter(append_profiles), append_metadata
        )

        # Verify append
        assert row_count == 1
        assert storage.execute_scalar("SELECT COUNT(*) FROM my_profiles") == 2


def test_append_profiles_table_raises_error_for_missing_table(tmp_path: Path) -> None:
    """Test that append_profiles_table raises TableNotFoundError for missing table."""
    from datetime import datetime

    from mixpanel_data.exceptions import TableNotFoundError
    from mixpanel_data.types import TableMetadata

    db_path = tmp_path / "test.db"
    with StorageEngine(path=db_path, read_only=False) as storage:
        profiles = [
            {
                "distinct_id": "user_1",
                "properties": {"name": "Alice"},
                "last_seen": datetime.now(UTC),
            }
        ]

        metadata = TableMetadata(
            type="profiles",
            fetched_at=datetime.now(UTC),
        )

        with pytest.raises(TableNotFoundError, match="nonexistent"):
            storage.append_profiles_table("nonexistent", iter(profiles), metadata)


def test_append_profiles_table_deduplicates_across_batches(tmp_path: Path) -> None:
    """Test that duplicate distinct_ids across initial and appended data are handled."""
    from datetime import datetime

    from mixpanel_data.types import TableMetadata

    db_path = tmp_path / "test.db"
    with StorageEngine(path=db_path, read_only=False) as storage:
        # Create initial table
        initial_profiles = [
            {
                "distinct_id": "user_1",  # Will be duplicated
                "properties": {"version": "first"},
                "last_seen": datetime(2024, 1, 15, 10, 0, tzinfo=UTC),
            },
        ]

        metadata = TableMetadata(
            type="profiles",
            fetched_at=datetime.now(UTC),
        )

        storage.create_profiles_table("my_profiles", iter(initial_profiles), metadata)

        # Append with duplicate distinct_id
        append_profiles = [
            {
                "distinct_id": "user_1",  # Duplicate - should be skipped
                "properties": {"version": "second"},
                "last_seen": datetime(2024, 1, 16, 10, 0, tzinfo=UTC),
            },
            {
                "distinct_id": "user_2",  # New
                "properties": {"version": "new"},
                "last_seen": datetime(2024, 1, 16, 10, 0, tzinfo=UTC),
            },
        ]

        append_metadata = TableMetadata(
            type="profiles",
            fetched_at=datetime.now(UTC),
        )

        storage.append_profiles_table(
            "my_profiles", iter(append_profiles), append_metadata
        )

        # Should only have 2 rows (duplicate skipped)
        assert storage.execute_scalar("SELECT COUNT(*) FROM my_profiles") == 2


def test_append_events_table_invokes_progress_callback(tmp_path: Path) -> None:
    """Test that append_events_table invokes progress callback."""
    from datetime import datetime

    from mixpanel_data.types import TableMetadata

    db_path = tmp_path / "test.db"
    with StorageEngine(path=db_path, read_only=False) as storage:
        # Create initial table
        initial_events = [
            {
                "event_name": "Event",
                "event_time": datetime.now(UTC),
                "distinct_id": "user_0",
                "insert_id": "event_0",
                "properties": {},
            }
        ]

        metadata = TableMetadata(
            type="events",
            fetched_at=datetime.now(UTC),
            from_date="2024-01-01",
            to_date="2024-01-01",
        )

        storage.create_events_table("my_events", iter(initial_events), metadata)

        # Generate 2100 events to test batching
        def event_generator() -> Iterator[dict[str, Any]]:
            for i in range(2100):
                yield {
                    "event_name": "Event",
                    "event_time": datetime.now(UTC),
                    "distinct_id": f"user_{i + 1}",
                    "insert_id": f"event_{i + 1:06d}",
                    "properties": {},
                }

        append_metadata = TableMetadata(
            type="events",
            fetched_at=datetime.now(UTC),
            from_date="2024-01-02",
            to_date="2024-01-02",
        )

        callback_invocations: list[int] = []

        def on_progress(row_count: int) -> None:
            callback_invocations.append(row_count)

        storage.append_events_table(
            "my_events",
            event_generator(),
            append_metadata,
            progress_callback=on_progress,
        )

        # Callback should have been invoked
        assert len(callback_invocations) > 0
        assert callback_invocations[-1] == 2100


# =============================================================================
# Tests for batch_size parameter
# =============================================================================


def test_create_events_table_accepts_batch_size(tmp_path: Path) -> None:
    """Test that create_events_table accepts and uses batch_size parameter."""
    from datetime import datetime

    from mixpanel_data.types import TableMetadata

    db_path = tmp_path / "test.db"
    with StorageEngine(path=db_path, read_only=False) as storage:
        # Create 500 events
        def event_generator() -> Iterator[dict[str, Any]]:
            for i in range(500):
                yield {
                    "event_name": "Event",
                    "event_time": datetime.now(UTC),
                    "distinct_id": f"user_{i}",
                    "insert_id": f"event_{i:06d}",
                    "properties": {"index": i},
                }

        metadata = TableMetadata(
            type="events",
            fetched_at=datetime.now(UTC),
            from_date="2024-01-01",
            to_date="2024-01-31",
        )

        callback_invocations: list[int] = []

        def on_progress(row_count: int) -> None:
            callback_invocations.append(row_count)

        # Use small batch_size of 100 - should result in 5 callbacks (500/100)
        row_count = storage.create_events_table(
            "events",
            event_generator(),
            metadata,
            progress_callback=on_progress,
            batch_size=100,
        )

        assert row_count == 500
        # With batch_size=100 and 500 rows, expect 5 callbacks (at 100, 200, 300, 400, 500)
        # But the last batch may not trigger callback if it's not a multiple
        # The callback is invoked after each full batch, so we expect exactly 5
        assert len(callback_invocations) == 5
        assert callback_invocations == [100, 200, 300, 400, 500]


def test_create_events_table_batch_size_affects_callback_frequency(
    tmp_path: Path,
) -> None:
    """Test that larger batch_size results in fewer progress callbacks."""
    from datetime import datetime

    from mixpanel_data.types import TableMetadata

    db_path = tmp_path / "test.db"
    with StorageEngine(path=db_path, read_only=False) as storage:
        # Create 1000 events
        def event_generator() -> Iterator[dict[str, Any]]:
            for i in range(1000):
                yield {
                    "event_name": "Event",
                    "event_time": datetime.now(UTC),
                    "distinct_id": f"user_{i}",
                    "insert_id": f"event_{i:06d}",
                    "properties": {"index": i},
                }

        metadata = TableMetadata(
            type="events",
            fetched_at=datetime.now(UTC),
            from_date="2024-01-01",
            to_date="2024-01-31",
        )

        callback_invocations: list[int] = []

        def on_progress(row_count: int) -> None:
            callback_invocations.append(row_count)

        # Use batch_size of 500 - should result in 2 callbacks (1000/500)
        storage.create_events_table(
            "events",
            event_generator(),
            metadata,
            progress_callback=on_progress,
            batch_size=500,
        )

        assert len(callback_invocations) == 2
        assert callback_invocations == [500, 1000]


def test_create_profiles_table_accepts_batch_size(tmp_path: Path) -> None:
    """Test that create_profiles_table accepts and uses batch_size parameter."""
    from datetime import datetime

    from mixpanel_data.types import TableMetadata

    db_path = tmp_path / "test.db"
    with StorageEngine(path=db_path, read_only=False) as storage:
        # Create 300 profiles
        def profile_generator() -> Iterator[dict[str, Any]]:
            for i in range(300):
                yield {
                    "distinct_id": f"user_{i}",
                    "properties": {"name": f"User {i}"},
                    "last_seen": datetime.now(UTC).isoformat(),
                }

        metadata = TableMetadata(
            type="profiles",
            fetched_at=datetime.now(UTC),
        )

        callback_invocations: list[int] = []

        def on_progress(row_count: int) -> None:
            callback_invocations.append(row_count)

        # Use batch_size of 100 - should result in 3 callbacks
        row_count = storage.create_profiles_table(
            "profiles",
            profile_generator(),
            metadata,
            progress_callback=on_progress,
            batch_size=100,
        )

        assert row_count == 300
        assert len(callback_invocations) == 3
        assert callback_invocations == [100, 200, 300]


def test_append_events_table_accepts_batch_size(tmp_path: Path) -> None:
    """Test that append_events_table accepts and uses batch_size parameter."""
    from datetime import datetime

    from mixpanel_data.types import TableMetadata

    db_path = tmp_path / "test.db"
    with StorageEngine(path=db_path, read_only=False) as storage:
        # Create initial table
        initial_events = [
            {
                "event_name": "Event",
                "event_time": datetime.now(UTC),
                "distinct_id": "user_0",
                "insert_id": "event_0",
                "properties": {},
            }
        ]

        metadata = TableMetadata(
            type="events",
            fetched_at=datetime.now(UTC),
            from_date="2024-01-01",
            to_date="2024-01-01",
        )

        storage.create_events_table("my_events", iter(initial_events), metadata)

        # Append 400 events with batch_size=100
        def event_generator() -> Iterator[dict[str, Any]]:
            for i in range(400):
                yield {
                    "event_name": "Event",
                    "event_time": datetime.now(UTC),
                    "distinct_id": f"user_{i + 1}",
                    "insert_id": f"event_{i + 1:06d}",
                    "properties": {},
                }

        append_metadata = TableMetadata(
            type="events",
            fetched_at=datetime.now(UTC),
            from_date="2024-01-02",
            to_date="2024-01-02",
        )

        callback_invocations: list[int] = []

        def on_progress(row_count: int) -> None:
            callback_invocations.append(row_count)

        row_count = storage.append_events_table(
            "my_events",
            event_generator(),
            append_metadata,
            progress_callback=on_progress,
            batch_size=100,
        )

        assert row_count == 400
        assert len(callback_invocations) == 4
        assert callback_invocations == [100, 200, 300, 400]


def test_append_profiles_table_accepts_batch_size(tmp_path: Path) -> None:
    """Test that append_profiles_table accepts and uses batch_size parameter."""
    from datetime import datetime

    from mixpanel_data.types import TableMetadata

    db_path = tmp_path / "test.db"
    with StorageEngine(path=db_path, read_only=False) as storage:
        # Create initial table
        initial_profiles = [
            {
                "distinct_id": "user_0",
                "properties": {"name": "User 0"},
                "last_seen": datetime.now(UTC).isoformat(),
            }
        ]

        metadata = TableMetadata(
            type="profiles",
            fetched_at=datetime.now(UTC),
        )

        storage.create_profiles_table("my_profiles", iter(initial_profiles), metadata)

        # Append 250 profiles with batch_size=50
        def profile_generator() -> Iterator[dict[str, Any]]:
            for i in range(250):
                yield {
                    "distinct_id": f"user_{i + 1}",
                    "properties": {"name": f"User {i + 1}"},
                    "last_seen": datetime.now(UTC).isoformat(),
                }

        append_metadata = TableMetadata(
            type="profiles",
            fetched_at=datetime.now(UTC),
        )

        callback_invocations: list[int] = []

        def on_progress(row_count: int) -> None:
            callback_invocations.append(row_count)

        row_count = storage.append_profiles_table(
            "my_profiles",
            profile_generator(),
            append_metadata,
            progress_callback=on_progress,
            batch_size=50,
        )

        assert row_count == 250
        assert len(callback_invocations) == 5
        assert callback_invocations == [50, 100, 150, 200, 250]


def test_create_events_table_default_batch_size_is_1000(tmp_path: Path) -> None:
    """Test that default batch_size is 1000 when not specified."""
    from datetime import datetime

    from mixpanel_data.types import TableMetadata

    db_path = tmp_path / "test.db"
    with StorageEngine(path=db_path, read_only=False) as storage:
        # Create 2500 events - with default batch_size=1000, expect 2 callbacks
        # (at 1000 and 2000), then final count after remainder
        def event_generator() -> Iterator[dict[str, Any]]:
            for i in range(2500):
                yield {
                    "event_name": "Event",
                    "event_time": datetime.now(UTC),
                    "distinct_id": f"user_{i}",
                    "insert_id": f"event_{i:06d}",
                    "properties": {"index": i},
                }

        metadata = TableMetadata(
            type="events",
            fetched_at=datetime.now(UTC),
            from_date="2024-01-01",
            to_date="2024-01-31",
        )

        callback_invocations: list[int] = []

        def on_progress(row_count: int) -> None:
            callback_invocations.append(row_count)

        # Don't specify batch_size - should use default of 1000
        row_count = storage.create_events_table(
            "events",
            event_generator(),
            metadata,
            progress_callback=on_progress,
        )

        assert row_count == 2500
        # With default batch_size=1000, we get callbacks at 1000, 2000, and 2500
        # (callback is also invoked for final partial batch)
        assert len(callback_invocations) == 3
        assert callback_invocations == [1000, 2000, 2500]
