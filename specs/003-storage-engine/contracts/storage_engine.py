"""
StorageEngine Class Contract

This file defines the public interface for the StorageEngine class.
It serves as a contract for implementation and documentation for consumers.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any, Protocol

import duckdb
import pandas as pd
from mixpanel_data.types import TableInfo, TableMetadata, TableSchema


class StorageEngine(Protocol):
    """Database operations for local Mixpanel data storage.

    StorageEngine manages DuckDB database lifecycle, schema, and query execution.
    It supports three operational modes:
    - Persistent: Database file survives process restarts
    - Ephemeral: Temporary database auto-deleted on close
    - Read-only: Open existing database without write permissions

    All methods are synchronous and non-interactive (agent-native design).
    """

    # ============================================================================
    # Construction
    # ============================================================================

    def __init__(self, path: Path | None = None) -> None:
        """Create or open a database.

        Args:
            path: Database file path. If None, creates ephemeral database.

        Raises:
            IOError: If path is unwritable or parent directory doesn't exist.
        """
        ...

    @classmethod
    def ephemeral(cls) -> StorageEngine:
        """Create ephemeral database that auto-deletes on close.

        Returns:
            StorageEngine instance with temporary database.

        Example:
            with StorageEngine.ephemeral() as storage:
                storage.create_events_table("events", data_iter, metadata)
                result = storage.execute_df("SELECT * FROM events LIMIT 10")
            # Database automatically deleted here
        """
        ...

    @classmethod
    def open_existing(cls, path: Path) -> StorageEngine:
        """Open existing database file.

        Args:
            path: Path to existing database file.

        Returns:
            StorageEngine instance connected to existing database.

        Raises:
            FileNotFoundError: If database file doesn't exist.

        Example:
            storage = StorageEngine.open_existing(Path("~/.mixpanel_data/12345.db"))
            tables = storage.list_tables()
        """
        ...

    # ============================================================================
    # Table Management
    # ============================================================================

    def create_events_table(
        self,
        name: str,
        data: Iterator[dict[str, Any]],
        metadata: TableMetadata,
        progress_callback: Callable[[int], None] | None = None,
    ) -> int:
        """Create events table and ingest data from iterator.

        Args:
            name: Table name (alphanumeric + underscore, no leading underscore).
            data: Iterator yielding event dictionaries with keys:
                - event_name (str)
                - event_time (datetime or ISO string)
                - distinct_id (str)
                - insert_id (str)
                - properties (dict)
            metadata: Fetch metadata to store in _metadata table.
            progress_callback: Optional callback invoked with row count updates.

        Returns:
            Total number of rows inserted.

        Raises:
            TableExistsError: If table with this name already exists.
            ValueError: If name is invalid or data has missing fields.
            QueryError: If database operation fails.

        Example:
            def on_progress(rows: int) -> None:
                print(f"Inserted {rows} rows")

            count = storage.create_events_table(
                "events_january",
                fetch_events_from_api(),
                TableMetadata(type="events", fetched_at=datetime.now(UTC)),
                progress_callback=on_progress
            )
        """
        ...

    def create_profiles_table(
        self,
        name: str,
        data: Iterator[dict[str, Any]],
        metadata: TableMetadata,
        progress_callback: Callable[[int], None] | None = None,
    ) -> int:
        """Create profiles table and ingest data from iterator.

        Args:
            name: Table name (alphanumeric + underscore, no leading underscore).
            data: Iterator yielding profile dictionaries with keys:
                - distinct_id (str)
                - properties (dict)
                - last_seen (datetime or ISO string)
            metadata: Fetch metadata to store in _metadata table.
            progress_callback: Optional callback invoked with row count updates.

        Returns:
            Total number of rows inserted.

        Raises:
            TableExistsError: If table with this name already exists.
            ValueError: If name is invalid or data has missing fields.
            QueryError: If database operation fails.
        """
        ...

    def drop_table(self, name: str) -> None:
        """Drop table and remove its metadata entry.

        Args:
            name: Table name to drop.

        Raises:
            TableNotFoundError: If table doesn't exist.
            QueryError: If database operation fails.

        Example:
            storage.drop_table("events_january")
        """
        ...

    def table_exists(self, name: str) -> bool:
        """Check if table exists.

        Args:
            name: Table name to check.

        Returns:
            True if table exists, False otherwise.

        Example:
            if not storage.table_exists("events_jan"):
                storage.create_events_table("events_jan", data, metadata)
        """
        ...

    # ============================================================================
    # Query Execution
    # ============================================================================

    def execute(self, sql: str) -> duckdb.DuckDBPyRelation:
        """Execute SQL and return raw DuckDB relation.

        Args:
            sql: SQL query string.

        Returns:
            DuckDB relation object (supports chaining, lazy evaluation).

        Raises:
            QueryError: If SQL execution fails.

        Example:
            relation = storage.execute("SELECT * FROM events WHERE event_time > '2024-01-01'")
            count = relation.count()
        """
        ...

    def execute_df(self, sql: str) -> pd.DataFrame:
        """Execute SQL and return pandas DataFrame.

        Args:
            sql: SQL query string.

        Returns:
            DataFrame with query results.

        Raises:
            QueryError: If SQL execution fails.

        Example:
            df = storage.execute_df(\"\"\"
                SELECT event_name, COUNT(*) as count
                FROM events
                GROUP BY event_name
                ORDER BY count DESC
            \"\"\")
        """
        ...

    def execute_scalar(self, sql: str) -> Any:
        """Execute SQL and return single scalar value.

        Args:
            sql: SQL query string that returns single row, single column.

        Returns:
            Scalar value (int, float, str, etc.).

        Raises:
            QueryError: If SQL execution fails.
            ValueError: If query returns multiple rows or columns.

        Example:
            total = storage.execute_scalar("SELECT COUNT(*) FROM events")
            assert isinstance(total, int)
        """
        ...

    def execute_rows(self, sql: str) -> list[tuple[Any, ...]]:
        """Execute SQL and return list of tuples.

        Args:
            sql: SQL query string.

        Returns:
            List of tuples, one per row.

        Raises:
            QueryError: If SQL execution fails.

        Example:
            rows = storage.execute_rows("SELECT event_name, COUNT(*) FROM events GROUP BY 1")
            for event_name, count in rows:
                print(f"{event_name}: {count}")
        """
        ...

    # ============================================================================
    # Introspection
    # ============================================================================

    def list_tables(self) -> list[TableInfo]:
        """List all user-created tables (excludes _metadata).

        Returns:
            List of TableInfo objects with table metadata.

        Example:
            for table in storage.list_tables():
                print(f"{table.name}: {table.row_count} rows")
        """
        ...

    def get_schema(self, table: str) -> TableSchema:
        """Get schema for specified table.

        Args:
            table: Table name.

        Returns:
            TableSchema with column information.

        Raises:
            TableNotFoundError: If table doesn't exist.

        Example:
            schema = storage.get_schema("events_jan")
            for col in schema.columns:
                print(f"{col.name}: {col.type}")
        """
        ...

    def get_metadata(self, table: str) -> TableMetadata:
        """Get fetch metadata for specified table.

        Args:
            table: Table name.

        Returns:
            TableMetadata from original fetch operation.

        Raises:
            TableNotFoundError: If table doesn't exist or has no metadata.

        Example:
            metadata = storage.get_metadata("events_jan")
            print(f"Fetched {metadata.from_date} to {metadata.to_date}")
        """
        ...

    # ============================================================================
    # Lifecycle
    # ============================================================================

    def close(self) -> None:
        """Close database connection and cleanup ephemeral files.

        Safe to call multiple times. For ephemeral databases, deletes the
        temporary file and WAL files.

        Example:
            storage = StorageEngine()
            try:
                # Use storage
                pass
            finally:
                storage.close()
        """
        ...

    def cleanup(self) -> None:
        """Cleanup ephemeral database files (alias for close).

        This method is identical to close() and exists for semantic clarity
        when explicitly cleaning up ephemeral databases.
        """
        ...

    # ============================================================================
    # Properties
    # ============================================================================

    @property
    def connection(self) -> duckdb.DuckDBPyConnection:
        """Direct access to DuckDB connection (escape hatch).

        Returns:
            DuckDB connection object.

        Warning:
            Direct connection access bypasses StorageEngine abstractions.
            Use only for advanced DuckDB features not exposed by StorageEngine.

        Example:
            # Advanced: Set DuckDB pragma
            storage.connection.execute("PRAGMA threads=4")
        """
        ...

    @property
    def path(self) -> Path | None:
        """Database file path (None for ephemeral databases).

        Returns:
            Path to database file, or None for ephemeral databases.

        Example:
            if storage.path:
                print(f"Database: {storage.path}")
            else:
                print("Ephemeral database (in-memory)")
        """
        ...

    # ============================================================================
    # Context Manager Protocol
    # ============================================================================

    def __enter__(self) -> StorageEngine:
        """Enter context manager."""
        ...

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: Any | None,
    ) -> None:
        """Exit context manager and close connection."""
        ...
