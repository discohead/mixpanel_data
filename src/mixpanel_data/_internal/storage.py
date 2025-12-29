"""DuckDB-based storage engine for Mixpanel data.

This module provides the StorageEngine class for persistent and ephemeral
storage of Mixpanel events and profiles using DuckDB as the embedded database.
"""

from __future__ import annotations

import atexit
import json
import logging
import re
import tempfile
from collections.abc import Callable, Iterator
from datetime import datetime
from pathlib import Path
from typing import Any

import duckdb
import pandas as pd

from mixpanel_data.exceptions import (
    DatabaseLockedError,
    DatabaseNotFoundError,
    QueryError,
    TableExistsError,
    TableNotFoundError,
)
from mixpanel_data.types import ColumnInfo, TableInfo, TableMetadata, TableSchema

# Module-level logger for cleanup operations
_logger = logging.getLogger(__name__)


def _quote_identifier(name: str) -> str:
    """Quote a SQL identifier to prevent injection.

    Uses DuckDB's double-quote identifier quoting and escapes any
    embedded double quotes by doubling them.

    Args:
        name: The identifier to quote.

    Returns:
        Properly quoted identifier safe for SQL interpolation.
    """
    # Escape any embedded double quotes by doubling them
    escaped = name.replace('"', '""')
    return f'"{escaped}"'


class StorageEngine:
    """DuckDB-based storage for Mixpanel events and profiles.

    Provides persistent and ephemeral database management with streaming
    ingestion, flexible query execution, and comprehensive introspection.

    Examples:
        Persistent storage:

        ```python
        storage = StorageEngine(path=Path("~/data.db").expanduser())
        storage.create_events_table("events", data_iterator, metadata)
        df = storage.execute_df("SELECT * FROM events")
        storage.close()
        ```

        Ephemeral storage:

        ```python
        with StorageEngine.ephemeral() as storage:
            storage.create_events_table("events", data_iterator, metadata)
            df = storage.execute_df("SELECT * FROM events")
        # Database automatically cleaned up
        ```
    """

    def __init__(
        self,
        path: Path | None = None,
        *,
        read_only: bool = False,
        _ephemeral: bool = False,
        _in_memory: bool = False,
    ) -> None:
        """Initialize storage engine with database at specified path.

        Args:
            path: Path to database file. Required unless _in_memory=True.
            read_only: Open database in read-only mode. When True, the
                connection allows SELECT queries but blocks INSERT, UPDATE,
                DELETE, and DDL operations. Read-only connections can be
                opened concurrently, enabling parallel query operations.
            _ephemeral: Internal flag to mark database as ephemeral.
                DO NOT USE DIRECTLY - use StorageEngine.ephemeral() instead.
                This parameter is keyword-only and prefixed with underscore
                to indicate it's for internal use only.
            _in_memory: Internal flag for in-memory databases.
                DO NOT USE DIRECTLY - use StorageEngine.memory() instead.

        Raises:
            OSError: If path is invalid or lacks write permissions.
            ValueError: If _ephemeral or _in_memory is used incorrectly.
            DatabaseLockedError: If database is locked and read_only=False.
            DatabaseNotFoundError: If read_only=True and database file doesn't exist.
        """
        self._path: Path | None = None
        self._conn: duckdb.DuckDBPyConnection | None = None
        self._is_ephemeral = _ephemeral
        self._is_in_memory = _in_memory
        self._read_only = read_only
        self._closed = False  # Track if close() was explicitly called

        # Validate mutually exclusive flags
        if _ephemeral and _in_memory:
            raise ValueError("Cannot use both _ephemeral and _in_memory flags")

        # Handle in-memory mode - no file created
        if _in_memory:
            self._path = None
            self._conn = duckdb.connect(":memory:")
            return

        # Validate _ephemeral usage: prevent users from accidentally marking
        # arbitrary paths as ephemeral (which would delete them on close!)
        if _ephemeral and path is not None:
            # Only allow ephemeral flag for paths in temp directory
            temp_dir = Path(tempfile.gettempdir())
            try:
                path.resolve().relative_to(temp_dir.resolve())
            except ValueError:
                raise ValueError(
                    "The _ephemeral parameter is for internal use only. "
                    "Use StorageEngine.ephemeral() to create ephemeral databases."
                ) from None

        if path is not None:
            # Check for read-only access to non-existent file
            # DuckDB cannot create a new file in read-only mode
            if read_only and not path.exists():
                raise DatabaseNotFoundError(str(path))

            # Persistent mode: create database at specified path
            try:
                # Create parent directories if they don't exist
                path.parent.mkdir(parents=True, exist_ok=True)

                # Store the path
                self._path = path

                # Connect to database (creates file if doesn't exist)
                self._conn = duckdb.connect(database=str(path), read_only=read_only)

                # Register atexit handler for ephemeral databases
                if self._is_ephemeral:
                    atexit.register(self._cleanup_ephemeral)
            except duckdb.IOException as e:
                # Check for database lock conflict
                error_str = str(e)
                if "Could not set lock" in error_str:
                    # Best-effort PID extraction from DuckDB error message.
                    # Format may change across DuckDB versions; we silently
                    # fall back to None if parsing fails.
                    # Example: "Conflicting lock is held in ... (PID 12345)"
                    pid_match = re.search(r"PID (\d+)", error_str)
                    holding_pid = int(pid_match.group(1)) if pid_match else None
                    raise DatabaseLockedError(str(path), holding_pid) from e
                # Other IO errors - wrap as OSError
                raise OSError(f"Failed to create database at {path}: {e}") from e
            except OSError as e:
                # Filesystem errors (permissions, disk full, etc.)
                raise OSError(f"Failed to create database at {path}: {e}") from e
        else:
            # No path provided - should use ephemeral() or memory() classmethod
            raise ValueError(
                "Use StorageEngine.ephemeral() or StorageEngine.memory() "
                "for temporary databases"
            )

    @classmethod
    def ephemeral(cls) -> StorageEngine:
        """Create ephemeral database that auto-deletes on close.

        Returns:
            StorageEngine instance with temporary database.

        Example:
            ```python
            with StorageEngine.ephemeral() as storage:
                storage.create_events_table("events", data_iter, metadata)
                result = storage.execute_df("SELECT * FROM events LIMIT 10")
            # Database automatically deleted here
            ```
        """
        # Create temporary file (delete=False so we control when it's deleted)
        with tempfile.NamedTemporaryFile(suffix=".duckdb", delete=False) as temp_file:
            temp_path = Path(temp_file.name)

        # File is closed here. Delete it so DuckDB can create it fresh.
        temp_path.unlink()

        # Create storage engine with ephemeral flag (write access needed)
        storage = cls(path=temp_path, read_only=False, _ephemeral=True)

        return storage

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
        DuckDB's compression (can be 8x faster for large workloads).

        Returns:
            StorageEngine instance with in-memory database.

        Example:
            ```python
            with StorageEngine.memory() as storage:
                storage.create_events_table("events", data, metadata)
                df = storage.execute_df("SELECT * FROM events")
            # Database gone - no cleanup needed
            ```
        """
        return cls(path=None, read_only=False, _in_memory=True)

    @classmethod
    def open_existing(cls, path: Path, *, read_only: bool = True) -> StorageEngine:
        """Open existing database file.

        Args:
            path: Path to existing database file.
            read_only: If True (default), open in read-only mode allowing
                concurrent reads. Set to False for write access.

        Returns:
            StorageEngine instance.

        Raises:
            FileNotFoundError: If database file doesn't exist.

        Example:
            ```python
            storage = StorageEngine.open_existing(Path("~/.mixpanel_data/12345.db"))
            tables = storage.list_tables()
            ```
        """
        # Check if file exists
        if not path.exists():
            raise FileNotFoundError(f"Database file not found: {path}")

        # Open existing database
        return cls(path=path, read_only=read_only)

    @property
    def path(self) -> Path | None:
        """Path to the database file (None for ephemeral databases before creation).

        Returns:
            Path to database file, or None if not yet initialized.
        """
        return self._path

    @property
    def read_only(self) -> bool:
        """Whether the database was opened in read-only mode.

        Read-only connections allow SELECT queries but block INSERT, UPDATE,
        DELETE, and DDL operations. Multiple read-only connections can access
        the same database concurrently.

        Returns:
            True if opened with read_only=True, False otherwise.
        """
        return self._read_only

    @property
    def connection(self) -> duckdb.DuckDBPyConnection:
        """DuckDB connection for advanced operations.

        Use this for DuckDB-specific features not exposed by StorageEngine.

        Returns:
            DuckDB connection instance.

        Raises:
            RuntimeError: If connection was closed or never established.
        """
        if self._conn is None:
            if self._closed:
                raise RuntimeError(
                    "Database connection has been closed. "
                    "Create a new StorageEngine instance to reconnect."
                )
            else:
                raise RuntimeError(
                    "Database connection not established. "
                    "Ensure the StorageEngine was initialized with a valid path."
                )
        return self._conn

    def _cleanup_ephemeral(self) -> None:
        """Clean up ephemeral database file (internal helper).

        This is called by:
        - close() for ephemeral databases
        - atexit handler for cleanup on normal exit
        - context manager __exit__

        Safe to call multiple times (idempotent).
        """
        if not self._is_ephemeral or self._path is None:
            return

        # Close connection if still open
        if self._conn is not None:
            try:
                self._conn.close()
            except Exception as e:
                # Log error but continue cleanup (best-effort)
                _logger.debug("Failed to close ephemeral database connection: %s", e)
            finally:
                self._conn = None

        # Delete database file
        try:
            if self._path.exists():
                self._path.unlink()
        except Exception as e:
            # Log error but continue cleanup (best-effort)
            _logger.warning(
                "Failed to delete ephemeral database file %s: %s", self._path, e
            )

        # Delete WAL file if it exists
        try:
            wal_path = Path(str(self._path) + ".wal")
            if wal_path.exists():
                wal_path.unlink()
        except Exception as e:
            # Log error but continue cleanup (best-effort)
            _logger.debug("Failed to delete WAL file %s: %s", wal_path, e)

        # Mark as closed for better error messages
        self._closed = True

    def close(self) -> None:
        """Close database connection and cleanup if ephemeral.

        Safe to call multiple times. For ephemeral databases, deletes the
        temporary file and WAL files. For in-memory databases, just closes
        the connection (no file cleanup needed).

        Example:
            ```python
            storage = StorageEngine(path=Path("data.db"))
            try:
                # Use storage
                pass
            finally:
                storage.close()
            ```
        """
        if self._is_in_memory:
            # In-memory database - just close connection, no file cleanup
            if self._conn is not None:
                try:
                    self._conn.close()
                except Exception as e:
                    _logger.debug("Failed to close in-memory connection: %s", e)
                finally:
                    self._conn = None
        elif self._is_ephemeral:
            # Cleanup ephemeral database
            self._cleanup_ephemeral()
        else:
            # Just close connection for persistent databases
            if self._conn is not None:
                try:
                    self._conn.close()
                except Exception as e:
                    # Log error but continue (best-effort cleanup)
                    _logger.debug("Failed to close database connection: %s", e)
                finally:
                    self._conn = None

        # Mark as closed for better error messages
        self._closed = True

    def cleanup(self) -> None:
        """Cleanup database resources (alias for close).

        This method is identical to close() and exists for semantic clarity
        when explicitly cleaning up ephemeral databases.

        Example:
            ```python
            storage = StorageEngine.ephemeral()
            storage.cleanup()  # Same as storage.close()
            ```
        """
        self.close()

    # =========================================================================
    # Helper Methods (Private)
    # =========================================================================

    def _validate_table_name(self, name: str) -> None:
        """Validate table name follows rules.

        Args:
            name: Table name to validate.

        Raises:
            ValueError: If name is invalid.
        """
        # Must not start with underscore (reserved for internal tables)
        if name.startswith("_"):
            raise ValueError(
                f"Table name '{name}' cannot start with underscore (reserved for internal tables)"
            )

        # Must be alphanumeric + underscore only
        if not re.match(r"^[a-zA-Z0-9_]+$", name):
            raise ValueError(
                f"Table name '{name}' must contain only alphanumeric characters and underscores"
            )

    def _validate_event_record(self, record: dict[str, Any]) -> None:
        """Validate event record has required fields.

        Args:
            record: Event dictionary to validate.

        Raises:
            ValueError: If required field is missing.
        """
        required_fields = [
            "event_name",
            "event_time",
            "distinct_id",
            "insert_id",
            "properties",
        ]
        for field in required_fields:
            if field not in record:
                raise ValueError(f"Event record missing required field: {field}")

    def _validate_profile_record(self, record: dict[str, Any]) -> None:
        """Validate profile record has required fields.

        Args:
            record: Profile dictionary to validate.

        Raises:
            ValueError: If required field is missing.
        """
        required_fields = ["distinct_id", "properties", "last_seen"]
        for field in required_fields:
            if field not in record:
                raise ValueError(f"Profile record missing required field: {field}")

    def _create_events_table_schema(self, name: str) -> None:
        """Create events table with schema from data-model.md.

        Args:
            name: Table name.
        """
        quoted_name = _quote_identifier(name)
        sql = f"""
            CREATE TABLE {quoted_name} (
                event_name VARCHAR NOT NULL,
                event_time TIMESTAMP NOT NULL,
                distinct_id VARCHAR NOT NULL,
                insert_id VARCHAR PRIMARY KEY,
                properties JSON
            )
        """
        self.connection.execute(sql)

    def _create_profiles_table_schema(self, name: str) -> None:
        """Create profiles table with schema from data-model.md.

        Args:
            name: Table name.
        """
        quoted_name = _quote_identifier(name)
        sql = f"""
            CREATE TABLE {quoted_name} (
                distinct_id VARCHAR PRIMARY KEY,
                properties JSON,
                last_seen TIMESTAMP
            )
        """
        self.connection.execute(sql)

    def _create_metadata_table(self) -> None:
        """Create _metadata table if it doesn't exist."""
        sql = """
            CREATE TABLE IF NOT EXISTS _metadata (
                table_name VARCHAR PRIMARY KEY,
                type VARCHAR NOT NULL,
                fetched_at TIMESTAMP NOT NULL,
                from_date DATE,
                to_date DATE,
                row_count INTEGER NOT NULL
            )
        """
        self.connection.execute(sql)

    def _batch_insert_events(
        self,
        name: str,
        data: Iterator[dict[str, Any]],
        progress_callback: Callable[[int], None] | None = None,
        batch_size: int = 1000,
    ) -> int:
        """Insert events from iterator in batches with per-batch commits.

        Each batch is committed immediately after insertion to bound memory
        usage. DuckDB releases transaction buffers after each commit, keeping
        memory constant regardless of total dataset size.

        Args:
            name: Table name.
            data: Iterator yielding event dictionaries.
            progress_callback: Optional callback invoked with cumulative row count.
            batch_size: Number of rows per INSERT/COMMIT cycle. Default: 1000.
                Lower values use less memory but have more disk I/O overhead.

        Returns:
            Total number of rows actually inserted (excludes duplicates skipped
            by INSERT OR IGNORE).
        """
        batch: list[tuple[str, str, str, str, str]] = []
        quoted_name = _quote_identifier(name)
        # Use INSERT OR IGNORE to skip duplicates silently.
        # The Mixpanel Export API returns raw data without deduplication,
        # so duplicate insert_ids are expected. We deduplicate on insert
        # to match Mixpanel's query-time behavior.
        insert_sql = f"INSERT OR IGNORE INTO {quoted_name} VALUES (?, ?, ?, ?, ?)"
        count_sql = f"SELECT COUNT(*) FROM {quoted_name}"

        # Get initial row count to compute actual inserts accurately.
        # INSERT OR IGNORE silently skips duplicates, so len(batch) would
        # overcount when duplicates exist.
        result = self.connection.execute(count_sql).fetchone()
        initial_count: int = result[0] if result else 0

        for record in data:
            # Validate record
            self._validate_event_record(record)

            # Convert datetime to string if needed
            event_time = record["event_time"]
            if isinstance(event_time, datetime):
                event_time = event_time.isoformat()

            # Convert properties to JSON string
            properties_json = json.dumps(record["properties"])

            batch.append(
                (
                    record["event_name"],
                    event_time,
                    record["distinct_id"],
                    record["insert_id"],
                    properties_json,
                )
            )

            if len(batch) >= batch_size:
                # Insert batch and commit immediately to release memory
                self.connection.executemany(insert_sql, batch)
                self.connection.execute("COMMIT")
                self.connection.execute("BEGIN TRANSACTION")
                batch = []

                # Call progress callback with actual inserted count
                if progress_callback is not None:
                    result = self.connection.execute(count_sql).fetchone()
                    current_count: int = result[0] if result else 0
                    progress_callback(current_count - initial_count)

        # Insert remaining records
        if batch:
            self.connection.executemany(insert_sql, batch)

            # Final progress callback
            if progress_callback is not None:
                result = self.connection.execute(count_sql).fetchone()
                progress_callback((result[0] if result else 0) - initial_count)

        # Return actual inserted count (current - initial)
        result = self.connection.execute(count_sql).fetchone()
        final_count: int = result[0] if result else 0
        return final_count - initial_count

    def _batch_insert_profiles(
        self,
        name: str,
        data: Iterator[dict[str, Any]],
        progress_callback: Callable[[int], None] | None = None,
        batch_size: int = 1000,
    ) -> int:
        """Insert profiles from iterator in batches with per-batch commits.

        Each batch is committed immediately after insertion to bound memory
        usage. DuckDB releases transaction buffers after each commit, keeping
        memory constant regardless of total dataset size.

        Args:
            name: Table name.
            data: Iterator yielding profile dictionaries.
            progress_callback: Optional callback invoked with cumulative row count.
            batch_size: Number of rows per INSERT/COMMIT cycle. Default: 1000.
                Lower values use less memory but have more disk I/O overhead.

        Returns:
            Total number of rows actually inserted (excludes duplicates skipped
            by INSERT OR IGNORE).
        """
        batch: list[tuple[str, str, str]] = []
        quoted_name = _quote_identifier(name)
        # Use INSERT OR IGNORE to skip duplicates silently.
        # Duplicate distinct_ids can occur in profile exports.
        insert_sql = f"INSERT OR IGNORE INTO {quoted_name} VALUES (?, ?, ?)"
        count_sql = f"SELECT COUNT(*) FROM {quoted_name}"

        # Get initial row count to compute actual inserts accurately.
        # INSERT OR IGNORE silently skips duplicates, so len(batch) would
        # overcount when duplicates exist.
        result = self.connection.execute(count_sql).fetchone()
        initial_count: int = result[0] if result else 0

        for record in data:
            # Validate record
            self._validate_profile_record(record)

            # Convert datetime to string if needed
            last_seen = record["last_seen"]
            if isinstance(last_seen, datetime):
                last_seen = last_seen.isoformat()

            # Convert properties to JSON string
            properties_json = json.dumps(record["properties"])

            batch.append(
                (
                    record["distinct_id"],
                    properties_json,
                    last_seen,
                )
            )

            if len(batch) >= batch_size:
                # Insert batch and commit immediately to release memory
                self.connection.executemany(insert_sql, batch)
                self.connection.execute("COMMIT")
                self.connection.execute("BEGIN TRANSACTION")
                batch = []

                # Call progress callback with actual inserted count
                if progress_callback is not None:
                    result = self.connection.execute(count_sql).fetchone()
                    current_count: int = result[0] if result else 0
                    progress_callback(current_count - initial_count)

        # Insert remaining records
        if batch:
            self.connection.executemany(insert_sql, batch)

            # Final progress callback
            if progress_callback is not None:
                result = self.connection.execute(count_sql).fetchone()
                progress_callback((result[0] if result else 0) - initial_count)

        # Return actual inserted count (current - initial)
        result = self.connection.execute(count_sql).fetchone()
        final_count: int = result[0] if result else 0
        return final_count - initial_count

    def _record_metadata(
        self, table_name: str, metadata: TableMetadata, row_count: int
    ) -> None:
        """Record metadata for a table in _metadata table.

        Args:
            table_name: Name of the table.
            metadata: Fetch metadata.
            row_count: Number of rows inserted.
        """
        # Ensure _metadata table exists
        self._create_metadata_table()

        # Convert datetime to string
        fetched_at = metadata.fetched_at.isoformat()

        # Insert metadata
        self.connection.execute(
            """
            INSERT INTO _metadata (table_name, type, fetched_at, from_date, to_date, row_count)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                table_name,
                metadata.type,
                fetched_at,
                metadata.from_date,
                metadata.to_date,
                row_count,
            ),
        )

    def create_events_table(
        self,
        name: str,
        data: Iterator[dict[str, Any]],
        metadata: TableMetadata,
        progress_callback: Callable[[int], None] | None = None,
        batch_size: int = 1000,
    ) -> int:
        """Create events table with streaming batch insert.

        Uses per-batch commits to bound memory usage for large datasets.
        Each batch is committed immediately, allowing DuckDB to release
        transaction buffers. This trades atomicity for constant memory usage.

        Note:
            If an error occurs after some chunks have been committed, those
            chunks will remain in the database. The table will exist with
            partial data but no metadata entry. Use drop_table() to clean up
            before retrying.

        Args:
            name: Table name (alphanumeric + underscore, no leading _).
            data: Iterator yielding event dictionaries.
            metadata: Fetch operation metadata.
            progress_callback: Optional callback invoked with row count.
            batch_size: Number of rows per INSERT/COMMIT cycle. Controls the
                memory/IO tradeoff: smaller values use less memory but more
                disk IO; larger values use more memory but less IO.
                Default: 1000.

        Returns:
            Total number of rows inserted.

        Raises:
            TableExistsError: If table already exists.
            ValueError: If table name is invalid or data malformed.
        """
        # Validate table name
        self._validate_table_name(name)

        # Check if table exists - prevent accidental overwrites
        if self.table_exists(name):
            raise TableExistsError(f"Table '{name}' already exists")

        # Start transaction - will be periodically committed during insert
        # for memory efficiency. On error, only the current chunk is rolled back.
        self.connection.execute("BEGIN TRANSACTION")
        try:
            # Create table schema
            self._create_events_table_schema(name)

            # Batch insert data with periodic commits
            row_count = self._batch_insert_events(
                name, data, progress_callback, batch_size
            )

            # Record metadata
            self._record_metadata(name, metadata, row_count)

            self.connection.execute("COMMIT")
            return row_count
        except Exception:
            self.connection.execute("ROLLBACK")
            raise

    def create_profiles_table(
        self,
        name: str,
        data: Iterator[dict[str, Any]],
        metadata: TableMetadata,
        progress_callback: Callable[[int], None] | None = None,
        batch_size: int = 1000,
    ) -> int:
        """Create profiles table with streaming batch insert.

        Uses per-batch commits to bound memory usage for large datasets.
        Each batch is committed immediately, allowing DuckDB to release
        transaction buffers. This trades atomicity for constant memory usage.

        Note:
            If an error occurs after some chunks have been committed, those
            chunks will remain in the database. The table will exist with
            partial data but no metadata entry. Use drop_table() to clean up
            before retrying.

        Args:
            name: Table name (alphanumeric + underscore, no leading _).
            data: Iterator yielding profile dictionaries.
            metadata: Fetch operation metadata.
            progress_callback: Optional callback invoked with row count.
            batch_size: Number of rows per INSERT/COMMIT cycle. Controls the
                memory/IO tradeoff: smaller values use less memory but more
                disk IO; larger values use more memory but less IO.
                Default: 1000.

        Returns:
            Total number of rows inserted.

        Raises:
            TableExistsError: If table already exists.
            ValueError: If table name is invalid or data malformed.
        """
        # Validate table name
        self._validate_table_name(name)

        # Check if table exists - prevent accidental overwrites
        if self.table_exists(name):
            raise TableExistsError(f"Table '{name}' already exists")

        # Start transaction - will be periodically committed during insert
        # for memory efficiency. On error, only the current chunk is rolled back.
        self.connection.execute("BEGIN TRANSACTION")
        try:
            # Create table schema
            self._create_profiles_table_schema(name)

            # Batch insert data with periodic commits
            row_count = self._batch_insert_profiles(
                name, data, progress_callback, batch_size
            )

            # Record metadata
            self._record_metadata(name, metadata, row_count)

            self.connection.execute("COMMIT")
            return row_count
        except Exception:
            self.connection.execute("ROLLBACK")
            raise

    def append_events_table(
        self,
        name: str,
        data: Iterator[dict[str, Any]],
        metadata: TableMetadata,
        progress_callback: Callable[[int], None] | None = None,
        batch_size: int = 1000,
    ) -> int:
        """Append events to an existing table.

        Adds new events to an existing events table. Duplicates (by insert_id)
        are silently skipped via INSERT OR IGNORE. Metadata is updated to
        reflect the expanded date range and new row count.

        Uses per-batch commits to bound memory usage for large datasets.

        Args:
            name: Existing table name.
            data: Iterator yielding event dictionaries.
            metadata: Metadata for the appended data (dates will be merged).
            progress_callback: Optional callback invoked with row count.
            batch_size: Number of rows per INSERT/COMMIT cycle. Controls the
                memory/IO tradeoff: smaller values use less memory but more
                disk IO; larger values use more memory but less IO.
                Default: 1000.

        Returns:
            Number of rows inserted in this append operation.

        Raises:
            TableNotFoundError: If table does not exist.
            ValueError: If data is malformed.
        """
        # Validate table name
        self._validate_table_name(name)

        # Check if table exists
        if not self.table_exists(name):
            raise TableNotFoundError(f"Table '{name}' does not exist")

        # Start transaction
        self.connection.execute("BEGIN TRANSACTION")
        try:
            # Batch insert data with periodic commits
            row_count = self._batch_insert_events(
                name, data, progress_callback, batch_size
            )

            # Update metadata with expanded date range and row count
            self._update_metadata_for_append(name, metadata, row_count)

            self.connection.execute("COMMIT")
            return row_count
        except Exception:
            self.connection.execute("ROLLBACK")
            raise

    def append_profiles_table(
        self,
        name: str,
        data: Iterator[dict[str, Any]],
        metadata: TableMetadata,
        progress_callback: Callable[[int], None] | None = None,
        batch_size: int = 1000,
    ) -> int:
        """Append profiles to an existing table.

        Adds new profiles to an existing profiles table. Duplicates (by
        distinct_id) are silently skipped via INSERT OR IGNORE. Metadata
        is updated to reflect the new row count.

        Uses per-batch commits to bound memory usage for large datasets.

        Args:
            name: Existing table name.
            data: Iterator yielding profile dictionaries.
            metadata: Metadata for the appended data.
            progress_callback: Optional callback invoked with row count.
            batch_size: Number of rows per INSERT/COMMIT cycle. Controls the
                memory/IO tradeoff: smaller values use less memory but more
                disk IO; larger values use more memory but less IO.
                Default: 1000.

        Returns:
            Number of rows inserted in this append operation.

        Raises:
            TableNotFoundError: If table does not exist.
            ValueError: If data is malformed.
        """
        # Validate table name
        self._validate_table_name(name)

        # Check if table exists
        if not self.table_exists(name):
            raise TableNotFoundError(f"Table '{name}' does not exist")

        # Start transaction
        self.connection.execute("BEGIN TRANSACTION")
        try:
            # Batch insert data with periodic commits
            row_count = self._batch_insert_profiles(
                name, data, progress_callback, batch_size
            )

            # Update metadata with new row count
            self._update_metadata_for_append(name, metadata, row_count)

            self.connection.execute("COMMIT")
            return row_count
        except Exception:
            self.connection.execute("ROLLBACK")
            raise

    def _update_metadata_for_append(
        self,
        table_name: str,
        new_metadata: TableMetadata,
        appended_rows: int,
    ) -> None:
        """Update metadata after appending data.

        Expands date range to include new data and updates row count.

        Args:
            table_name: Name of the table.
            new_metadata: Metadata from the append operation.
            appended_rows: Number of rows added in this append.
        """
        # Get current metadata
        result = self.connection.execute(
            """
            SELECT from_date, to_date, row_count
            FROM _metadata
            WHERE table_name = ?
            """,
            (table_name,),
        ).fetchone()

        if result is None:
            # No metadata entry - create one
            self._record_metadata(table_name, new_metadata, appended_rows)
            return

        current_from_raw, current_to_raw, _ = result

        # Convert dates to strings for comparison (DuckDB may return date objects)
        current_from = str(current_from_raw) if current_from_raw else None
        current_to = str(current_to_raw) if current_to_raw else None

        # Calculate new date range (expand to include new data)
        new_from = current_from
        new_to = current_to

        if new_metadata.from_date and (
            current_from is None or new_metadata.from_date < current_from
        ):
            new_from = new_metadata.from_date

        if new_metadata.to_date and (
            current_to is None or new_metadata.to_date > current_to
        ):
            new_to = new_metadata.to_date

        # Get actual row count from table (not cumulative of appends)
        quoted_name = _quote_identifier(table_name)
        count_result = self.connection.execute(
            f"SELECT COUNT(*) FROM {quoted_name}"
        ).fetchone()
        actual_count = count_result[0] if count_result else 0

        # Update metadata
        self.connection.execute(
            """
            UPDATE _metadata
            SET from_date = ?, to_date = ?, row_count = ?, fetched_at = ?
            WHERE table_name = ?
            """,
            (
                new_from,
                new_to,
                actual_count,
                new_metadata.fetched_at.isoformat(),
                table_name,
            ),
        )

    def execute(self, sql: str) -> duckdb.DuckDBPyRelation:
        """Execute SQL and return DuckDB relation (for chaining).

        The returned relation object supports DuckDB's method chaining API,
        allowing you to apply additional transformations before fetching results.

        Args:
            sql: SQL query string.

        Returns:
            DuckDB relation object that can be further queried or transformed.

        Raises:
            QueryError: If query execution fails.

        Examples:
            Basic query:

            ```python
            storage = StorageEngine(path=Path("data.db"))
            relation = storage.execute("SELECT * FROM events WHERE event_name = 'Page View'")
            results = relation.fetchall()
            ```

            Method chaining:

            ```python
            relation = storage.execute("SELECT * FROM events")
            filtered = relation.filter("event_name = 'Page View'")
            limited = filtered.limit(10)
            df = limited.df()
            ```

            Converting to DataFrame:

            ```python
            relation = storage.execute("SELECT * FROM events")
            df = relation.df()  # DuckDB relation to pandas DataFrame
            ```
        """
        try:
            return self.connection.sql(sql)
        except duckdb.Error as e:
            raise QueryError(
                f"Query execution failed: {e}",
                status_code=0,  # Not an HTTP error
                response_body={"query": sql, "error": str(e)},
            ) from e

    def execute_df(self, sql: str) -> pd.DataFrame:
        """Execute SQL and return pandas DataFrame.

        This is the most convenient method for data analysis workflows,
        directly converting query results to a pandas DataFrame.

        Args:
            sql: SQL query string.

        Returns:
            Query results as pandas DataFrame.

        Raises:
            QueryError: If query execution fails.

        Examples:
            Basic query:

            ```python
            storage = StorageEngine(path=Path("data.db"))
            df = storage.execute_df("SELECT * FROM events LIMIT 10")
            print(df.head())
            ```

            Query with JSON extraction:

            ```python
            df = storage.execute_df('''
                SELECT
                    event_name,
                    properties->>'$.page' as page,
                    properties->>'$.country' as country
                FROM events
                WHERE event_name = 'Page View'
            ''')
            ```

            Aggregation query:

            ```python
            df = storage.execute_df('''
                SELECT
                    event_name,
                    COUNT(*) as event_count
                FROM events
                GROUP BY event_name
                ORDER BY event_count DESC
            ''')
            ```
        """
        try:
            return self.connection.execute(sql).df()
        except duckdb.Error as e:
            raise QueryError(
                f"Query execution failed: {e}",
                status_code=0,  # Not an HTTP error
                response_body={"query": sql, "error": str(e)},
            ) from e

    def execute_scalar(self, sql: str) -> Any:
        """Execute SQL and return single scalar value.

        Useful for queries that return a single value like COUNT(*), MAX(), etc.

        Args:
            sql: SQL query string (should return single row, single column).

        Returns:
            Scalar value (int, str, float, None, etc.).

        Raises:
            QueryError: If query execution fails.

        Examples:
            Count rows:

            ```python
            storage = StorageEngine(path=Path("data.db"))
            count = storage.execute_scalar("SELECT COUNT(*) FROM events")
            print(f"Total events: {count}")
            ```

            Get maximum value:

            ```python
            max_time = storage.execute_scalar("SELECT MAX(event_time) FROM events")
            ```

            Check existence:

            ```python
            exists = storage.execute_scalar('''
                SELECT COUNT(*) > 0
                FROM events
                WHERE event_name = 'Purchase'
            ''')
            ```
        """
        try:
            result = self.connection.execute(sql).fetchone()
            if result is None:
                return None
            return result[0]
        except duckdb.Error as e:
            raise QueryError(
                f"Query execution failed: {e}",
                status_code=0,  # Not an HTTP error
                response_body={"query": sql, "error": str(e)},
            ) from e

    def execute_rows(self, sql: str) -> list[tuple[Any, ...]]:
        """Execute SQL and return list of tuples.

        Useful when you need to iterate over results without pandas overhead,
        or when working with code that expects tuple-based results.

        Args:
            sql: SQL query string.

        Returns:
            List of row tuples.

        Raises:
            QueryError: If query execution fails.

        Examples:
            Basic iteration:

            ```python
            storage = StorageEngine(path=Path("data.db"))
            rows = storage.execute_rows("SELECT event_name, COUNT(*) FROM events GROUP BY event_name")
            for event_name, count in rows:
                print(f"{event_name}: {count}")
            ```

            Get specific rows:

            ```python
            rows = storage.execute_rows('''
                SELECT distinct_id, event_name, event_time
                FROM events
                WHERE event_name = 'Page View'
                LIMIT 5
            ''')
            for distinct_id, event_name, event_time in rows:
                print(f"{distinct_id} - {event_name} at {event_time}")
            ```
        """
        try:
            return self.connection.execute(sql).fetchall()
        except duckdb.Error as e:
            raise QueryError(
                f"Query execution failed: {e}",
                status_code=0,  # Not an HTTP error
                response_body={"query": sql, "error": str(e)},
            ) from e

    def list_tables(self) -> list[TableInfo]:
        """List all user-created tables in database.

        Returns:
            List of table information (excludes internal _metadata table),
            sorted alphabetically by table name.

        Example:
            ```python
            storage = StorageEngine(path=Path("data.db"))
            tables = storage.list_tables()
            for table in tables:
                print(f"{table.name}: {table.row_count} rows ({table.type})")
            ```
        """
        # Check if _metadata table exists
        metadata_exists = self.connection.execute(
            "SELECT COUNT(*) FROM information_schema.tables WHERE table_name = '_metadata'"
        ).fetchone()

        if not metadata_exists or metadata_exists[0] == 0:
            # No metadata table means no user tables yet
            return []

        # Query _metadata table for all user tables (exclude _metadata itself)
        result = self.connection.execute(
            """
            SELECT table_name, type, row_count, fetched_at
            FROM _metadata
            WHERE table_name != '_metadata'
            ORDER BY table_name
            """
        ).fetchall()

        # If no user tables, return empty list
        if not result:
            return []

        # Convert to TableInfo objects
        tables = []
        for row in result:
            table_name, table_type, row_count, fetched_at_str = row

            # Parse fetched_at timestamp
            # DuckDB returns timestamps as strings in ISO format
            if isinstance(fetched_at_str, str):
                fetched_at = datetime.fromisoformat(
                    fetched_at_str.replace("Z", "+00:00")
                )
            else:
                # Already a datetime object
                fetched_at = fetched_at_str

            tables.append(
                TableInfo(
                    name=table_name,
                    type=table_type,
                    row_count=row_count,
                    fetched_at=fetched_at,
                )
            )

        return tables

    def get_schema(self, table_name: str) -> TableSchema:
        """Get schema information for a table.

        Args:
            table_name: Name of table to inspect.

        Returns:
            Table schema with column definitions.

        Raises:
            TableNotFoundError: If table doesn't exist.

        Example:
            ```python
            schema = storage.get_schema("events")
            for col in schema.columns:
                print(f"{col.name}: {col.type} ({'NULL' if col.nullable else 'NOT NULL'})")
            ```
        """
        # Check if table exists
        if not self.table_exists(table_name):
            raise TableNotFoundError(f"Table '{table_name}' does not exist")

        # Get column information using PRAGMA table_info
        # Returns: (cid, name, type, notnull, dflt_value, pk)
        quoted_name = _quote_identifier(table_name)
        result = self.connection.execute(f"PRAGMA table_info({quoted_name})").fetchall()

        # Convert to ColumnInfo objects
        columns = []
        for row in result:
            cid, col_name, col_type, notnull, dflt_value, pk = row

            columns.append(
                ColumnInfo(
                    name=col_name,
                    type=col_type,
                    nullable=(
                        notnull == 0
                    ),  # notnull=0 means nullable, notnull=1 means NOT NULL
                    primary_key=(pk > 0),  # pk > 0 indicates primary key
                )
            )

        return TableSchema(
            table_name=table_name,
            columns=columns,
        )

    def get_metadata(self, table_name: str) -> TableMetadata:
        """Get fetch metadata for a table.

        Args:
            table_name: Name of table to inspect.

        Returns:
            Fetch operation metadata.

        Raises:
            TableNotFoundError: If table doesn't exist.

        Example:
            ```python
            metadata = storage.get_metadata("events_jan")
            print(f"Fetched {metadata.type} from {metadata.from_date} to {metadata.to_date}")
            ```
        """
        # Check if table exists
        if not self.table_exists(table_name):
            raise TableNotFoundError(f"Table '{table_name}' does not exist")

        # Query metadata table
        result = self.connection.execute(
            """
            SELECT type, fetched_at, from_date, to_date
            FROM _metadata
            WHERE table_name = ?
            """,
            (table_name,),
        ).fetchone()

        # If metadata not found (table exists but no metadata entry)
        if result is None:
            raise TableNotFoundError(
                f"Metadata not found for table '{table_name}' (table exists but has no metadata)"
            )

        table_type, fetched_at_str, from_date, to_date = result

        # Parse fetched_at timestamp
        if isinstance(fetched_at_str, str):
            fetched_at = datetime.fromisoformat(fetched_at_str.replace("Z", "+00:00"))
        else:
            fetched_at = fetched_at_str

        return TableMetadata(
            type=table_type,
            fetched_at=fetched_at,
            from_date=from_date.isoformat() if from_date else None,
            to_date=to_date.isoformat() if to_date else None,
        )

    def table_exists(self, name: str) -> bool:
        """Check if table exists in database.

        Args:
            name: Table name to check.

        Returns:
            True if table exists, False otherwise.

        Example:
            ```python
            if storage.table_exists("events"):
                print("Table exists")
            ```
        """
        result = self.connection.execute(
            "SELECT COUNT(*) FROM information_schema.tables WHERE table_name = ?",
            (name,),
        ).fetchone()
        return result is not None and result[0] > 0

    def drop_table(self, name: str) -> None:
        """Drop table and associated metadata.

        Args:
            name: Table name to drop.

        Raises:
            TableNotFoundError: If table doesn't exist.

        Example:
            ```python
            storage.drop_table("old_events")  # Explicitly remove before recreating
            storage.create_events_table("old_events", new_data, metadata)
            ```
        """
        # Check if table exists
        if not self.table_exists(name):
            raise TableNotFoundError(f"Table '{name}' does not exist")

        # Drop the table
        quoted_name = _quote_identifier(name)
        self.connection.execute(f"DROP TABLE {quoted_name}")

        # Remove metadata entry (if it exists)
        self.connection.execute("DELETE FROM _metadata WHERE table_name = ?", (name,))

    def __enter__(self) -> StorageEngine:
        """Context manager entry."""
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Context manager exit - close connection."""
        self.close()
