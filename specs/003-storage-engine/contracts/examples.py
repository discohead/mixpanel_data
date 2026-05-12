"""
StorageEngine Usage Examples

Demonstrates common patterns and best practices for using StorageEngine.
These examples should be adapted into unit and integration tests.
"""

from datetime import UTC, datetime
from pathlib import Path

from mixpanel_data._internal.storage import StorageEngine
from mixpanel_data.exceptions import TableExistsError, TableNotFoundError
from mixpanel_data.types import TableMetadata

# =============================================================================
# Example 1: Persistent Storage
# =============================================================================


def example_persistent_storage() -> None:
    """Create persistent database, insert data, close, reopen."""

    # Create database at specific path
    db_path = Path("~/my_analysis/mixpanel.db").expanduser()
    storage = StorageEngine(path=db_path)

    try:
        # Generate sample data
        def sample_events():
            for i in range(1000):
                yield {
                    "event_name": "Page View",
                    "event_time": datetime.now(UTC),
                    "distinct_id": f"user_{i % 100}",
                    "insert_id": f"event_{i}",
                    "properties": {"page": f"/page{i % 10}"},
                }

        # Create table with metadata
        metadata = TableMetadata(
            type="events",
            fetched_at=datetime.now(UTC),
            from_date="2024-01-01",
            to_date="2024-01-31",
        )

        row_count = storage.create_events_table("events", sample_events(), metadata)
        print(f"Inserted {row_count} events")

    finally:
        storage.close()

    # Reopen and query
    storage = StorageEngine.open_existing(db_path)
    try:
        total = storage.execute_scalar("SELECT COUNT(*) FROM events")
        print(f"Total events: {total}")
    finally:
        storage.close()


# =============================================================================
# Example 2: Ephemeral Analysis
# =============================================================================


def example_ephemeral_analysis() -> None:
    """Use ephemeral database with context manager for automatic cleanup."""

    with StorageEngine.ephemeral() as storage:
        # Database created in temp directory

        def sample_data():
            for i in range(100):
                yield {
                    "event_name": "Purchase",
                    "event_time": datetime.now(UTC),
                    "distinct_id": f"user_{i}",
                    "insert_id": f"evt_{i}",
                    "properties": {"amount": i * 10.0},
                }

        metadata = TableMetadata(type="events", fetched_at=datetime.now(UTC))

        storage.create_events_table("purchases", sample_data(), metadata)

        # Quick analysis
        df = storage.execute_df(
            """
            SELECT
                properties->>'$.amount' as amount,
                COUNT(*) as count
            FROM purchases
            GROUP BY amount
            ORDER BY amount DESC
            LIMIT 10
        """
        )
        print(df)

    # Database automatically deleted here


# =============================================================================
# Example 3: Streaming Ingestion with Progress
# =============================================================================


def example_streaming_with_progress() -> None:
    """Stream large dataset with progress callback."""

    def on_progress(rows: int) -> None:
        """Called periodically during ingestion."""
        print(f"Progress: {rows:,} rows inserted")

    def large_dataset():
        """Simulate large dataset fetch."""
        for i in range(1_000_000):
            yield {
                "event_name": "Impression",
                "event_time": datetime.now(UTC),
                "distinct_id": f"user_{i % 10000}",
                "insert_id": f"imp_{i}",
                "properties": {"campaign_id": f"camp_{i % 100}"},
            }

    with StorageEngine.ephemeral() as storage:
        metadata = TableMetadata(type="events", fetched_at=datetime.now(UTC))

        row_count = storage.create_events_table(
            "impressions", large_dataset(), metadata, progress_callback=on_progress
        )

        print(f"Total: {row_count:,} rows")

        # Memory usage should stay constant (< 500MB)


# =============================================================================
# Example 4: Error Handling
# =============================================================================


def example_error_handling() -> None:
    """Demonstrate proper error handling patterns."""

    with StorageEngine.ephemeral() as storage:
        # Create initial table
        def sample_data():
            yield {
                "event_name": "Event1",
                "event_time": datetime.now(UTC),
                "distinct_id": "user_1",
                "insert_id": "evt_1",
                "properties": {},
            }

        metadata = TableMetadata(type="events", fetched_at=datetime.now(UTC))

        storage.create_events_table("events", sample_data(), metadata)

        # Attempt duplicate creation
        try:
            storage.create_events_table("events", sample_data(), metadata)
        except TableExistsError as e:
            print(f"Expected error: {e.message}")
            print(f"Table name: {e.table_name}")

        # Check before creating
        if not storage.table_exists("new_events"):
            storage.create_events_table("new_events", sample_data(), metadata)

        # Attempt to get schema for non-existent table
        try:
            storage.get_schema("missing_table")
        except TableNotFoundError as e:
            print(f"Expected error: {e.message}")

        # SQL error handling
        from mixpanel_data.exceptions import QueryError

        try:
            storage.execute_df("SELECT * FROM nonexistent")
        except QueryError as e:
            print(f"Query failed: {e.message}")
            print(f"Details: {e.details}")


# =============================================================================
# Example 5: Multiple Query Formats
# =============================================================================


def example_query_formats() -> None:
    """Demonstrate different query execution methods."""

    with StorageEngine.ephemeral() as storage:
        # Setup data
        def sample_data():
            for i in range(100):
                yield {
                    "event_name": f"Event{i % 5}",
                    "event_time": datetime.now(UTC),
                    "distinct_id": f"user_{i % 10}",
                    "insert_id": f"evt_{i}",
                    "properties": {"value": i},
                }

        metadata = TableMetadata(type="events", fetched_at=datetime.now(UTC))
        storage.create_events_table("events", sample_data(), metadata)

        # DataFrame (for data science)
        df = storage.execute_df("SELECT event_name, COUNT(*) FROM events GROUP BY 1")
        print("DataFrame:")
        print(df)

        # Scalar (for aggregates)
        total = storage.execute_scalar("SELECT COUNT(*) FROM events")
        print(f"\nScalar: {total}")

        # Rows (for iteration)
        rows = storage.execute_rows(
            "SELECT event_name, COUNT(*) FROM events GROUP BY 1 LIMIT 3"
        )
        print("\nRows:")
        for event_name, count in rows:
            print(f"  {event_name}: {count}")

        # Raw relation (for advanced DuckDB features)
        relation = storage.execute(
            "SELECT event_name, COUNT(*) as cnt FROM events GROUP BY 1"
        )
        filtered = relation.filter("cnt > 10")
        print("\nFiltered relation:")
        print(filtered.df())


# =============================================================================
# Example 6: Introspection
# =============================================================================


def example_introspection() -> None:
    """Explore database contents programmatically."""

    with StorageEngine.ephemeral() as storage:
        # Create multiple tables
        def sample_events():
            yield {
                "event_name": "Event1",
                "event_time": datetime.now(UTC),
                "distinct_id": "user_1",
                "insert_id": "evt_1",
                "properties": {},
            }

        def sample_profiles():
            yield {
                "distinct_id": "user_1",
                "properties": {"name": "Alice"},
                "last_seen": datetime.now(UTC),
            }

        metadata = TableMetadata(type="events", fetched_at=datetime.now(UTC))
        storage.create_events_table("events_jan", sample_events(), metadata)

        metadata_profiles = TableMetadata(type="profiles", fetched_at=datetime.now(UTC))
        storage.create_profiles_table("profiles", sample_profiles(), metadata_profiles)

        # List all tables
        print("Available tables:")
        for table in storage.list_tables():
            print(
                f"  {table.name}: {table.row_count} {table.type} rows (fetched {table.fetched_at})"
            )

        # Get schema
        schema = storage.get_schema("events_jan")
        print(f"\nSchema for {schema.table_name}:")
        for col in schema.columns:
            null_str = "NULL" if col.nullable else "NOT NULL"
            print(f"  {col.name}: {col.type} {null_str}")

        # Get metadata
        fetch_metadata = storage.get_metadata("events_jan")
        print("\nFetch metadata:")
        print(f"  Type: {fetch_metadata.type}")
        print(f"  Fetched at: {fetch_metadata.fetched_at}")


# =============================================================================
# Example 7: Table Replacement Pattern
# =============================================================================


def example_table_replacement() -> None:
    """Replace existing table with new data."""

    with StorageEngine.ephemeral() as storage:

        def old_data():
            yield {
                "event_name": "OldEvent",
                "event_time": datetime.now(UTC),
                "distinct_id": "user_1",
                "insert_id": "evt_1",
                "properties": {},
            }

        def new_data():
            for i in range(10):
                yield {
                    "event_name": "NewEvent",
                    "event_time": datetime.now(UTC),
                    "distinct_id": f"user_{i}",
                    "insert_id": f"evt_{i}",
                    "properties": {},
                }

        # Create initial table
        metadata = TableMetadata(type="events", fetched_at=datetime.now(UTC))
        storage.create_events_table("events", old_data(), metadata)

        # Check if exists
        if storage.table_exists("events"):
            # Explicit drop before recreating
            storage.drop_table("events")

        # Create new table
        new_metadata = TableMetadata(type="events", fetched_at=datetime.now(UTC))
        storage.create_events_table("events", new_data(), new_metadata)

        count = storage.execute_scalar("SELECT COUNT(*) FROM events")
        print(f"New table has {count} rows")


# =============================================================================
# Example 8: JSON Property Queries
# =============================================================================


def example_json_queries() -> None:
    """Query JSON properties in events and profiles."""

    with StorageEngine.ephemeral() as storage:

        def events_with_props():
            for i in range(100):
                yield {
                    "event_name": "Purchase",
                    "event_time": datetime.now(UTC),
                    "distinct_id": f"user_{i % 10}",
                    "insert_id": f"evt_{i}",
                    "properties": {
                        "country": "US" if i % 2 == 0 else "UK",
                        "amount": i * 10.0,
                        "plan": "premium" if i % 3 == 0 else "free",
                    },
                }

        metadata = TableMetadata(type="events", fetched_at=datetime.now(UTC))
        storage.create_events_table("purchases", events_with_props(), metadata)

        # Extract string property
        df = storage.execute_df(
            """
            SELECT
                properties->>'$.country' as country,
                COUNT(*) as count
            FROM purchases
            GROUP BY country
        """
        )
        print("By country:")
        print(df)

        # Extract and cast numeric property
        df = storage.execute_df(
            """
            SELECT
                CAST(properties->>'$.amount' AS DECIMAL) as amount
            FROM purchases
            WHERE CAST(properties->>'$.amount' AS DECIMAL) > 500
            LIMIT 10
        """
        )
        print("\nHigh-value purchases:")
        print(df)

        # Filter on JSON property
        df = storage.execute_df(
            """
            SELECT event_name, COUNT(*)
            FROM purchases
            WHERE properties->>'$.plan' = 'premium'
            GROUP BY event_name
        """
        )
        print("\nPremium purchases:")
        print(df)


if __name__ == "__main__":
    print("=== Example 1: Persistent Storage ===")
    example_persistent_storage()

    print("\n=== Example 2: Ephemeral Analysis ===")
    example_ephemeral_analysis()

    print("\n=== Example 4: Error Handling ===")
    example_error_handling()

    print("\n=== Example 5: Query Formats ===")
    example_query_formats()

    print("\n=== Example 6: Introspection ===")
    example_introspection()

    print("\n=== Example 7: Table Replacement ===")
    example_table_replacement()

    print("\n=== Example 8: JSON Queries ===")
    example_json_queries()
