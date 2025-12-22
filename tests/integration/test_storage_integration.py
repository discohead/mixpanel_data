"""Integration tests for StorageEngine (User Story 1: Session Persistence)."""

from __future__ import annotations

from datetime import UTC
from pathlib import Path

from mixpanel_data._internal.storage import StorageEngine

# =============================================================================
# T013: Integration test for session persistence
# =============================================================================


def test_database_persists_across_sessions(tmp_path: Path) -> None:
    """Test that database file persists and can be reopened across sessions.

    This is the key integration test for User Story 1:
    1. Create database and close it
    2. Reopen database in new session
    3. Verify database state is preserved
    """
    db_path = tmp_path / "persistent.db"

    # Session 1: Create database
    storage1 = StorageEngine(path=db_path)
    try:
        # Create a simple table to verify persistence
        storage1.connection.execute("""
            CREATE TABLE test_table (
                id INTEGER PRIMARY KEY,
                value VARCHAR
            )
        """)
        storage1.connection.execute("INSERT INTO test_table VALUES (1, 'hello')")
        storage1.connection.execute("INSERT INTO test_table VALUES (2, 'world')")
    finally:
        storage1.close()

    # Verify file exists
    assert db_path.exists()

    # Session 2: Reopen database
    storage2 = StorageEngine(path=db_path)
    try:
        # Verify table and data still exist
        result = storage2.connection.execute(
            "SELECT value FROM test_table ORDER BY id"
        ).fetchall()
        assert result == [("hello",), ("world",)]
    finally:
        storage2.close()


def test_multiple_reopens_preserve_data(tmp_path: Path) -> None:
    """Test that database can be reopened multiple times with data intact."""
    db_path = tmp_path / "multi_session.db"

    # Session 1: Create and insert
    with StorageEngine(path=db_path) as storage:
        storage.connection.execute("CREATE TABLE data (id INTEGER, name VARCHAR)")
        storage.connection.execute("INSERT INTO data VALUES (1, 'first')")

    # Session 2: Insert more
    with StorageEngine(path=db_path) as storage:
        storage.connection.execute("INSERT INTO data VALUES (2, 'second')")

    # Session 3: Verify all data present
    with StorageEngine(path=db_path) as storage:
        result = storage.connection.execute("SELECT COUNT(*) FROM data").fetchone()
        assert result == (2,)


def test_database_file_format_is_duckdb(tmp_path: Path) -> None:
    """Test that created file is a valid DuckDB database."""
    import duckdb

    db_path = tmp_path / "format_test.db"

    # Create via StorageEngine
    storage = StorageEngine(path=db_path)
    storage.close()

    # Verify we can open it directly with duckdb
    conn = duckdb.connect(str(db_path))
    try:
        # Should be able to query without error
        result = conn.execute("SELECT 1").fetchone()
        assert result == (1,)
    finally:
        conn.close()


# =============================================================================
# T024: Integration test for large dataset ingestion
# =============================================================================


def test_large_dataset_ingestion_100k_events(tmp_path: Path) -> None:
    """Test ingestion of 100K events with streaming (constant memory)."""
    from datetime import datetime

    from mixpanel_data.types import TableMetadata

    db_path = tmp_path / "large_dataset.db"
    storage = StorageEngine(path=db_path)

    try:
        # Create generator for 100K events
        def event_generator():
            for i in range(100_000):
                yield {
                    "event_name": "Event",
                    "event_time": datetime.now(UTC),
                    "distinct_id": f"user_{i % 10000}",  # 10K unique users
                    "insert_id": f"event_{i:08d}",
                    "properties": {"index": i, "batch": i // 1000},
                }

        metadata = TableMetadata(
            type="events",
            fetched_at=datetime.now(UTC),
            from_date="2024-01-01",
            to_date="2024-01-31",
        )

        # Track progress
        progress_updates = []

        def on_progress(row_count: int) -> None:
            progress_updates.append(row_count)

        # Create events table
        row_count = storage.create_events_table(
            "large_events", event_generator(), metadata, progress_callback=on_progress
        )

        # Verify all events inserted
        assert row_count == 100_000

        # Verify data in database
        result = storage.connection.execute(
            "SELECT COUNT(*) FROM large_events"
        ).fetchone()
        assert result == (100_000,)

        # Verify progress was tracked
        assert len(progress_updates) > 0
        assert progress_updates[-1] == 100_000

        # Verify metadata was recorded
        metadata_result = storage.connection.execute(
            "SELECT row_count, type FROM _metadata WHERE table_name = 'large_events'"
        ).fetchone()
        assert metadata_result == (100_000, "events")
    finally:
        storage.close()


def test_large_dataset_ingestion_50k_profiles(tmp_path: Path) -> None:
    """Test ingestion of 50K profiles with streaming."""
    from datetime import datetime

    from mixpanel_data.types import TableMetadata

    db_path = tmp_path / "large_profiles.db"
    storage = StorageEngine(path=db_path)

    try:
        # Create generator for 50K profiles
        def profile_generator():
            for i in range(50_000):
                yield {
                    "distinct_id": f"user_{i:08d}",
                    "properties": {
                        "name": f"User {i}",
                        "email": f"user{i}@example.com",
                        "plan": "free" if i % 10 < 8 else "premium",
                    },
                    "last_seen": datetime.now(UTC),
                }

        metadata = TableMetadata(
            type="profiles",
            fetched_at=datetime.now(UTC),
        )

        # Create profiles table
        row_count = storage.create_profiles_table(
            "large_profiles", profile_generator(), metadata
        )

        # Verify all profiles inserted
        assert row_count == 50_000

        # Verify data in database
        result = storage.connection.execute(
            "SELECT COUNT(*) FROM large_profiles"
        ).fetchone()
        assert result == (50_000,)
    finally:
        storage.close()


# =============================================================================
# T025: Memory profiling test for 1M events
# =============================================================================


# def test_memory_usage_stays_constant_for_1m_events(tmp_path: Path) -> None:
#     """Test that memory usage stays under 500MB for 1M events.

#     This test uses memory_profiler to track memory usage during ingestion.
#     Memory should stay constant (< 500MB) regardless of dataset size.
#     """
#     import tracemalloc
#     from datetime import datetime, timezone

#     from mixpanel_data.types import TableMetadata

#     db_path = tmp_path / "million_events.db"

#     # Start memory tracking
#     tracemalloc.start()

#     storage = StorageEngine(path=db_path)

#     try:
#         # Create generator for 1M events
#         def event_generator():
#             for i in range(1_000_000):
#                 yield {
#                     "event_name": "Event",
#                     "event_time": datetime.now(timezone.utc),
#                     "distinct_id": f"user_{i % 100000}",  # 100K unique users
#                     "insert_id": f"event_{i:08d}",
#                     "properties": {"index": i, "batch": i // 10000},
#                 }

#         metadata = TableMetadata(
#             type="events",
#             fetched_at=datetime.now(timezone.utc),
#             from_date="2024-01-01",
#             to_date="2024-12-31",
#         )

#         # Track memory at different points
#         memory_snapshots = []

#         def on_progress(row_count: int) -> None:
#             # Take memory snapshot every 100K rows
#             if row_count % 100_000 == 0:
#                 current, peak = tracemalloc.get_traced_memory()
#                 memory_snapshots.append(
#                     {
#                         "rows": row_count,
#                         "current_mb": current / 1024 / 1024,
#                         "peak_mb": peak / 1024 / 1024,
#                     }
#                 )

#         # Create events table
#         row_count = storage.create_events_table(
#             "million_events", event_generator(), metadata, progress_callback=on_progress
#         )

#         # Verify all events inserted
#         assert row_count == 1_000_000

#         # Verify memory usage stayed reasonable
#         # Get final memory usage
#         current, peak = tracemalloc.get_traced_memory()
#         peak_mb = peak / 1024 / 1024

#         # Stop tracking
#         tracemalloc.stop()

#         # Verify peak memory stayed under 500MB
#         assert (
#             peak_mb < 500
#         ), f"Peak memory usage {peak_mb:.2f} MB exceeded 500 MB limit"

#         # Verify memory didn't grow linearly with dataset size
#         # If memory grew linearly, 1M events would use ~10x more than 100K events
#         # With constant memory usage, the difference should be minimal
#         if len(memory_snapshots) >= 2:
#             first_snapshot = memory_snapshots[0]
#             last_snapshot = memory_snapshots[-1]
#             memory_growth = last_snapshot["current_mb"] - first_snapshot["current_mb"]

#             # Memory growth should be less than 100MB between first and last snapshot
#             assert (
#                 memory_growth < 100
#             ), f"Memory grew by {memory_growth:.2f} MB, indicating non-constant usage"

#         # Verify data in database
#         result = storage.connection.execute(
#             "SELECT COUNT(*) FROM million_events"
#         ).fetchone()
#         assert result == (1_000_000,)
#     finally:
#         storage.close()


# =============================================================================
# T038: Integration test for ephemeral cleanup on normal exit
# =============================================================================


def test_ephemeral_cleanup_on_normal_exit() -> None:
    """Test that ephemeral database is cleaned up on normal exit."""
    # Create ephemeral storage
    storage = StorageEngine.ephemeral()
    temp_path = storage.path

    # Verify file exists
    assert temp_path.exists()

    # Insert some data
    storage.connection.execute("CREATE TABLE test (id INTEGER, value VARCHAR)")
    storage.connection.execute("INSERT INTO test VALUES (1, 'data')")

    # Explicitly close
    storage.close()

    # File should be deleted
    assert not temp_path.exists()


# =============================================================================
# T039: Integration test for ephemeral cleanup on exception exit
# =============================================================================


def test_ephemeral_cleanup_on_exception() -> None:
    """Test that ephemeral database is cleaned up even when exceptions occur."""
    temp_path = None
    storage = None

    try:
        storage = StorageEngine.ephemeral()
        temp_path = storage.path

        # Verify file exists
        assert temp_path.exists()

        # Create some data
        storage.connection.execute("CREATE TABLE test (id INTEGER)")

        # Raise an exception
        raise ValueError("Test exception")
    except ValueError:
        # Exception was raised as expected
        pass
    finally:
        # Close storage if it exists
        if storage is not None:
            storage.close()

    # File should be deleted even though exception was raised
    assert temp_path is not None
    assert not temp_path.exists()


# =============================================================================
# T040: Integration test for ephemeral cleanup via context manager
# =============================================================================


def test_ephemeral_cleanup_via_context_manager() -> None:
    """Test that ephemeral database is cleaned up via context manager."""
    temp_path = None

    with StorageEngine.ephemeral() as storage:
        temp_path = storage.path

        # Verify file exists
        assert temp_path.exists()

        # Insert some data
        storage.connection.execute("CREATE TABLE test (id INTEGER, value VARCHAR)")
        storage.connection.execute("INSERT INTO test VALUES (1, 'data')")

    # After exiting context, file should be deleted
    assert temp_path is not None
    assert not temp_path.exists()


def test_ephemeral_cleanup_via_context_manager_with_exception() -> None:
    """Test that ephemeral database is cleaned up even when exception occurs in context."""
    temp_path = None

    try:
        with StorageEngine.ephemeral() as storage:
            temp_path = storage.path

            # Verify file exists
            assert temp_path.exists()

            # Create some data
            storage.connection.execute("CREATE TABLE test (id INTEGER)")

            # Raise an exception
            raise ValueError("Test exception in context manager")
    except ValueError:
        # Exception was raised as expected
        pass

    # File should be deleted even though exception was raised
    assert temp_path is not None
    assert not temp_path.exists()


def test_ephemeral_with_create_events_table() -> None:
    """Test ephemeral storage with real data ingestion workflow."""
    from datetime import datetime

    from mixpanel_data.types import TableMetadata

    temp_path = None

    with StorageEngine.ephemeral() as storage:
        temp_path = storage.path

        # Create sample events
        events = [
            {
                "event_name": "Page View",
                "event_time": datetime(2024, 1, 15, 10, 30, tzinfo=UTC),
                "distinct_id": "user_123",
                "insert_id": "event_001",
                "properties": {"page": "/home"},
            },
            {
                "event_name": "Button Click",
                "event_time": datetime(2024, 1, 15, 11, 0, tzinfo=UTC),
                "distinct_id": "user_456",
                "insert_id": "event_002",
                "properties": {"button": "signup"},
            },
        ]

        metadata = TableMetadata(
            type="events",
            fetched_at=datetime.now(UTC),
        )

        # Create events table
        row_count = storage.create_events_table("events", iter(events), metadata)

        # Verify data was inserted
        assert row_count == 2
        result = storage.connection.execute("SELECT COUNT(*) FROM events").fetchone()
        assert result == (2,)

    # After context exit, temp file should be deleted
    assert temp_path is not None
    assert not temp_path.exists()


# =============================================================================
# T077: Integration test for table replacement pattern
# =============================================================================


def test_table_replacement_pattern_create_drop_recreate(tmp_path: Path) -> None:
    """Test the complete workflow of creating, dropping, and recreating tables.

    This is the key integration test for User Story 6:
    1. Create table with data
    2. Verify table exists and data is accessible
    3. Drop table explicitly
    4. Recreate table with new data
    5. Verify new data is correct
    """
    from datetime import datetime

    from mixpanel_data.exceptions import TableExistsError
    from mixpanel_data.types import TableMetadata

    db_path = tmp_path / "replacement.db"
    storage = StorageEngine(path=db_path)

    try:
        # Step 1: Create initial table
        initial_events = [
            {
                "event_name": "Initial Event",
                "event_time": datetime(2024, 1, 1, 12, 0, tzinfo=UTC),
                "distinct_id": "user_1",
                "insert_id": "event_1",
                "properties": {"version": "v1"},
            },
            {
                "event_name": "Initial Event 2",
                "event_time": datetime(2024, 1, 1, 13, 0, tzinfo=UTC),
                "distinct_id": "user_2",
                "insert_id": "event_2",
                "properties": {"version": "v1"},
            },
        ]

        metadata_v1 = TableMetadata(
            type="events",
            fetched_at=datetime.now(UTC),
            from_date="2024-01-01",
            to_date="2024-01-01",
        )

        row_count = storage.create_events_table(
            "my_events", iter(initial_events), metadata_v1
        )
        assert row_count == 2

        # Step 2: Verify initial data
        result = storage.connection.execute("SELECT COUNT(*) FROM my_events").fetchone()
        assert result == (2,)

        result = storage.connection.execute(
            "SELECT event_name FROM my_events ORDER BY event_time"
        ).fetchall()
        assert result == [("Initial Event",), ("Initial Event 2",)]

        # Step 3: Attempting to recreate without dropping should fail
        new_events = [
            {
                "event_name": "New Event",
                "event_time": datetime(2024, 1, 2, 12, 0, tzinfo=UTC),
                "distinct_id": "user_3",
                "insert_id": "event_3",
                "properties": {"version": "v2"},
            }
        ]

        try:
            storage.create_events_table("my_events", iter(new_events), metadata_v1)
            raise AssertionError("Should have raised TableExistsError")
        except TableExistsError:
            # Expected behavior - table exists
            pass

        # Step 4: Drop the table
        storage.drop_table("my_events")

        # Verify table is gone
        assert storage.table_exists("my_events") is False

        # Step 5: Recreate table with new data
        replacement_events = [
            {
                "event_name": "Replacement Event",
                "event_time": datetime(2024, 1, 15, 12, 0, tzinfo=UTC),
                "distinct_id": "user_100",
                "insert_id": "event_100",
                "properties": {"version": "v2"},
            },
            {
                "event_name": "Replacement Event 2",
                "event_time": datetime(2024, 1, 15, 13, 0, tzinfo=UTC),
                "distinct_id": "user_101",
                "insert_id": "event_101",
                "properties": {"version": "v2"},
            },
            {
                "event_name": "Replacement Event 3",
                "event_time": datetime(2024, 1, 15, 14, 0, tzinfo=UTC),
                "distinct_id": "user_102",
                "insert_id": "event_102",
                "properties": {"version": "v2"},
            },
        ]

        metadata_v2 = TableMetadata(
            type="events",
            fetched_at=datetime.now(UTC),
            from_date="2024-01-15",
            to_date="2024-01-15",
        )

        row_count = storage.create_events_table(
            "my_events", iter(replacement_events), metadata_v2
        )
        assert row_count == 3

        # Step 6: Verify new data is correct (old data is gone)
        result = storage.connection.execute("SELECT COUNT(*) FROM my_events").fetchone()
        assert result == (3,)

        result = storage.connection.execute(
            "SELECT event_name FROM my_events ORDER BY event_time"
        ).fetchall()
        assert result == [
            ("Replacement Event",),
            ("Replacement Event 2",),
            ("Replacement Event 3",),
        ]

        # Verify metadata was updated
        result = storage.connection.execute(
            "SELECT from_date, to_date, row_count FROM _metadata WHERE table_name = ?",
            ("my_events",),
        ).fetchone()
        assert result is not None
        from_date, to_date, row_count = result
        # DuckDB returns date objects for DATE columns
        assert from_date.isoformat() == "2024-01-15"
        assert to_date.isoformat() == "2024-01-15"
        assert row_count == 3

    finally:
        storage.close()


def test_table_replacement_with_different_table_types(tmp_path: Path) -> None:
    """Test that table replacement works for both events and profiles tables."""
    from datetime import datetime

    from mixpanel_data.types import TableMetadata

    db_path = tmp_path / "mixed_types.db"
    storage = StorageEngine(path=db_path)

    try:
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
        metadata_events = TableMetadata(
            type="events",
            fetched_at=datetime.now(UTC),
        )
        storage.create_events_table("data_v1", iter(events), metadata_events)

        # Drop and recreate as profiles table (different schema)
        storage.drop_table("data_v1")

        profiles = [
            {
                "distinct_id": "user_1",
                "properties": {"name": "Alice"},
                "last_seen": datetime.now(UTC),
            }
        ]
        metadata_profiles = TableMetadata(
            type="profiles",
            fetched_at=datetime.now(UTC),
        )
        storage.create_profiles_table("data_v1", iter(profiles), metadata_profiles)

        # Verify new table has profiles schema
        result = storage.connection.execute("SELECT COUNT(*) FROM data_v1").fetchone()
        assert result == (1,)

        # Verify metadata type was updated
        result = storage.connection.execute(
            "SELECT type FROM _metadata WHERE table_name = ?",
            ("data_v1",),
        ).fetchone()
        assert result == ("profiles",)

    finally:
        storage.close()


# =============================================================================
# T067: Integration test for introspection workflow
# =============================================================================


def test_introspection_workflow_create_list_inspect_verify(tmp_path: Path) -> None:
    """Test complete introspection workflow: create tables, list, inspect, verify.

    This is the key integration test for User Story 5:
    1. Create multiple tables with different schemas and metadata
    2. List all tables and verify correct info returned
    3. Inspect each table's schema
    4. Inspect each table's metadata
    5. Verify all information is accurate
    """
    from datetime import datetime

    from mixpanel_data.types import TableMetadata

    db_path = tmp_path / "introspection.db"
    storage = StorageEngine(path=db_path)

    try:
        # Step 1: Create multiple tables with different schemas and metadata

        # Events table 1: January data
        jan_events = [
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
        jan_metadata = TableMetadata(
            type="events",
            fetched_at=datetime(2024, 1, 15, 12, 0, tzinfo=UTC),
            from_date="2024-01-01",
            to_date="2024-01-31",
        )
        storage.create_events_table("events_jan", iter(jan_events), jan_metadata)

        # Events table 2: February data
        feb_events = [
            {
                "event_name": "Purchase",
                "event_time": datetime(2024, 2, 10, 14, 0, tzinfo=UTC),
                "distinct_id": "user_789",
                "insert_id": "event_003",
                "properties": {"amount": 99.99, "currency": "USD"},
            }
        ]
        feb_metadata = TableMetadata(
            type="events",
            fetched_at=datetime(2024, 2, 10, 15, 0, tzinfo=UTC),
            from_date="2024-02-01",
            to_date="2024-02-29",
        )
        storage.create_events_table("events_feb", iter(feb_events), feb_metadata)

        # Profiles table
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
        profiles_metadata = TableMetadata(
            type="profiles",
            fetched_at=datetime(2024, 1, 15, 12, 0, tzinfo=UTC),
        )
        storage.create_profiles_table("profiles_all", iter(profiles), profiles_metadata)

        # Step 2: List all tables
        tables = storage.list_tables()

        # Verify we have 3 tables
        assert len(tables) == 3

        # Verify table names (should be sorted alphabetically)
        table_names = [t.name for t in tables]
        assert table_names == ["events_feb", "events_jan", "profiles_all"]

        # Verify table types
        table_types = {t.name: t.type for t in tables}
        assert table_types["events_jan"] == "events"
        assert table_types["events_feb"] == "events"
        assert table_types["profiles_all"] == "profiles"

        # Verify row counts
        table_row_counts = {t.name: t.row_count for t in tables}
        assert table_row_counts["events_jan"] == 2
        assert table_row_counts["events_feb"] == 1
        assert table_row_counts["profiles_all"] == 2

        # Verify fetched_at is present
        for table in tables:
            assert table.fetched_at is not None

        # Step 3: Inspect each table's schema

        # Events table schema (events_jan and events_feb should be identical)
        jan_schema = storage.get_schema("events_jan")
        assert jan_schema.table_name == "events_jan"
        assert len(jan_schema.columns) == 5
        jan_column_names = {col.name for col in jan_schema.columns}
        assert jan_column_names == {
            "event_name",
            "event_time",
            "distinct_id",
            "insert_id",
            "properties",
        }

        # Verify primary key on insert_id
        insert_id_col = next(
            col for col in jan_schema.columns if col.name == "insert_id"
        )
        assert insert_id_col.primary_key is True

        # Feb events should have same schema
        feb_schema = storage.get_schema("events_feb")
        assert feb_schema.table_name == "events_feb"
        assert len(feb_schema.columns) == 5
        feb_column_names = {col.name for col in feb_schema.columns}
        assert feb_column_names == jan_column_names

        # Profiles table schema
        profiles_schema = storage.get_schema("profiles_all")
        assert profiles_schema.table_name == "profiles_all"
        assert len(profiles_schema.columns) == 3
        profiles_column_names = {col.name for col in profiles_schema.columns}
        assert profiles_column_names == {"distinct_id", "properties", "last_seen"}

        # Verify primary key on distinct_id
        distinct_id_col = next(
            col for col in profiles_schema.columns if col.name == "distinct_id"
        )
        assert distinct_id_col.primary_key is True

        # Step 4: Inspect each table's metadata

        # Events January metadata
        jan_meta = storage.get_metadata("events_jan")
        assert jan_meta.type == "events"
        assert jan_meta.from_date == "2024-01-01"
        assert jan_meta.to_date == "2024-01-31"
        assert jan_meta.fetched_at is not None

        # Events February metadata
        feb_meta = storage.get_metadata("events_feb")
        assert feb_meta.type == "events"
        assert feb_meta.from_date == "2024-02-01"
        assert feb_meta.to_date == "2024-02-29"
        assert feb_meta.fetched_at is not None

        # Profiles metadata
        profiles_meta = storage.get_metadata("profiles_all")
        assert profiles_meta.type == "profiles"
        assert profiles_meta.from_date is None
        assert profiles_meta.to_date is None
        assert profiles_meta.fetched_at is not None

        # Step 5: Verify data integrity by querying actual table data

        # Verify events_jan has correct data
        jan_result = storage.connection.execute(
            "SELECT event_name, distinct_id FROM events_jan ORDER BY event_time"
        ).fetchall()
        assert jan_result == [("Page View", "user_123"), ("Button Click", "user_456")]

        # Verify events_feb has correct data
        feb_result = storage.connection.execute(
            "SELECT event_name, distinct_id FROM events_feb"
        ).fetchall()
        assert feb_result == [("Purchase", "user_789")]

        # Verify profiles_all has correct data
        profiles_result = storage.connection.execute(
            "SELECT distinct_id FROM profiles_all ORDER BY distinct_id"
        ).fetchall()
        assert profiles_result == [("user_123",), ("user_456",)]

    finally:
        storage.close()


def test_introspection_on_empty_database(tmp_path: Path) -> None:
    """Test that introspection works on empty database (no user tables)."""
    db_path = tmp_path / "empty.db"
    storage = StorageEngine(path=db_path)

    try:
        # List tables should return empty list
        tables = storage.list_tables()
        assert tables == []

    finally:
        storage.close()


def test_introspection_after_table_drop(tmp_path: Path) -> None:
    """Test that introspection reflects table drops correctly."""
    from datetime import datetime

    from mixpanel_data.types import TableMetadata

    db_path = tmp_path / "drop_test.db"
    storage = StorageEngine(path=db_path)

    try:
        # Create two tables
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

        storage.create_events_table("table1", iter(events), metadata)
        storage.create_events_table("table2", iter(events), metadata)

        # Verify both tables listed
        tables = storage.list_tables()
        assert len(tables) == 2
        assert {t.name for t in tables} == {"table1", "table2"}

        # Drop one table
        storage.drop_table("table1")

        # Verify only remaining table is listed
        tables = storage.list_tables()
        assert len(tables) == 1
        assert tables[0].name == "table2"

        # Verify get_schema raises error for dropped table
        from mixpanel_data.exceptions import TableNotFoundError

        try:
            storage.get_schema("table1")
            raise AssertionError("Should have raised TableNotFoundError")
        except TableNotFoundError:
            pass

        # Verify get_metadata raises error for dropped table
        try:
            storage.get_metadata("table1")
            raise AssertionError("Should have raised TableNotFoundError")
        except TableNotFoundError:
            pass

    finally:
        storage.close()
