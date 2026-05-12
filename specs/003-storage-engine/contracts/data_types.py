"""
Data Types Contract for Storage Engine

Defines Python data structures used by StorageEngine for metadata and introspection.
These types should be added to src/mixpanel_data/types.py.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal


@dataclass(frozen=True)
class TableMetadata:
    """Metadata for a data fetch operation.

    This structure is passed to create_events_table() and create_profiles_table()
    to record information about the fetch operation. It's stored in the _metadata
    table and returned by get_metadata().

    Attributes:
        type: Type of data ("events" or "profiles")
        fetched_at: When the fetch completed (UTC timezone recommended)
        from_date: Start date for events (YYYY-MM-DD), None for profiles
        to_date: End date for events (YYYY-MM-DD), None for profiles
        filter_events: Event names filtered during fetch (if applicable)
        filter_where: WHERE clause used during fetch (if applicable)

    Example:
        metadata = TableMetadata(
            type="events",
            fetched_at=datetime.now(timezone.utc),
            from_date="2024-01-01",
            to_date="2024-01-31"
        )
    """

    type: Literal["events", "profiles"]
    """Type of data fetched."""

    fetched_at: datetime
    """When the fetch completed."""

    from_date: str | None = None
    """Start date for events (YYYY-MM-DD), None for profiles."""

    to_date: str | None = None
    """End date for events (YYYY-MM-DD), None for profiles."""

    filter_events: list[str] | None = None
    """Event names filtered during fetch (if applicable)."""

    filter_where: str | None = None
    """WHERE clause used during fetch (if applicable)."""


@dataclass(frozen=True)
class TableInfo:
    """Summary information about a table.

    Returned by list_tables() to provide overview of available tables.

    Attributes:
        name: Table name
        type: Table type ("events" or "profiles")
        row_count: Number of rows in table
        fetched_at: When data was fetched

    Example:
        for table in storage.list_tables():
            print(f"{table.name}: {table.row_count} {table.type} rows")
            print(f"  Fetched: {table.fetched_at}")
    """

    name: str
    """Table name."""

    type: Literal["events", "profiles"]
    """Table type."""

    row_count: int
    """Number of rows in table."""

    fetched_at: datetime
    """When data was fetched."""


@dataclass(frozen=True)
class ColumnInfo:
    """Information about a table column.

    Describes structure of a single column in a database table.

    Attributes:
        name: Column name
        type: DuckDB type (VARCHAR, TIMESTAMP, JSON, INTEGER, etc.)
        nullable: Whether column allows NULL values

    Example:
        col = ColumnInfo(name="event_name", type="VARCHAR", nullable=False)
        print(f"{col.name}: {col.type} {'NULL' if col.nullable else 'NOT NULL'}")
    """

    name: str
    """Column name."""

    type: str
    """DuckDB type (VARCHAR, TIMESTAMP, JSON, INTEGER, etc.)."""

    nullable: bool
    """Whether column allows NULL values."""


@dataclass(frozen=True)
class TableSchema:
    """Schema of a database table.

    Returned by get_schema() to describe table structure.

    Attributes:
        table_name: Name of the table
        columns: List of column definitions

    Example:
        schema = storage.get_schema("events_jan")
        print(f"Table: {schema.table_name}")
        for col in schema.columns:
            null_str = "NULL" if col.nullable else "NOT NULL"
            print(f"  {col.name}: {col.type} {null_str}")
    """

    table_name: str
    """Name of the table."""

    columns: list[ColumnInfo]
    """List of column definitions."""


# Type aliases for clarity
EventDict = dict[str, Any]
"""Dictionary representing an event record.

Expected keys:
- event_name: str
- event_time: datetime | str (ISO format)
- distinct_id: str
- insert_id: str
- properties: dict[str, Any]
"""

ProfileDict = dict[str, Any]
"""Dictionary representing a profile record.

Expected keys:
- distinct_id: str
- properties: dict[str, Any]
- last_seen: datetime | str (ISO format)
"""
