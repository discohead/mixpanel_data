# Data Model: Storage Engine

**Phase**: 1 (Design & Contracts)
**Date**: 2025-12-21
**Purpose**: Define database schemas and Python data structures for Storage Engine

## Database Tables

### Events Table

**Purpose**: Store timestamped user actions fetched from Mixpanel

**Schema**:
```sql
CREATE TABLE {table_name} (
    event_name VARCHAR NOT NULL,
    event_time TIMESTAMP NOT NULL,
    distinct_id VARCHAR NOT NULL,
    insert_id VARCHAR PRIMARY KEY,
    properties JSON
);
```

**Columns**:

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `event_name` | VARCHAR | NOT NULL | Name of the event (e.g., "Purchase", "Page View") |
| `event_time` | TIMESTAMP | NOT NULL | When the event occurred (UTC) |
| `distinct_id` | VARCHAR | NOT NULL | User identifier |
| `insert_id` | VARCHAR | PRIMARY KEY | Unique event identifier for deduplication |
| `properties` | JSON | - | All event properties as JSON object |

**Indexes**:
- Primary key on `insert_id` (automatic, ensures uniqueness)
- No additional indexes initially (columnar storage provides fast scans)

**Sample Data**:
```json
{
  "event_name": "Song Played",
  "event_time": "2024-01-15T10:30:00Z",
  "distinct_id": "user_123",
  "insert_id": "5d958f87-542d-4c10-9422-0ed75893dc81",
  "properties": {
    "song_id": "song_456",
    "duration": 180,
    "shuffle_mode": true,
    "country": "US"
  }
}
```

**Query Patterns**:
```sql
-- Count events by type
SELECT event_name, COUNT(*)
FROM events
GROUP BY event_name;

-- Extract JSON property
SELECT
    event_name,
    properties->>'$.country' as country
FROM events
WHERE properties->>'$.country' = 'US';

-- Time-series aggregation
SELECT
    DATE_TRUNC('day', event_time) as day,
    COUNT(*) as event_count
FROM events
GROUP BY day
ORDER BY day;
```

---

### Profiles Table

**Purpose**: Store current state of user attributes fetched from Mixpanel

**Schema**:
```sql
CREATE TABLE {table_name} (
    distinct_id VARCHAR PRIMARY KEY,
    properties JSON,
    last_seen TIMESTAMP
);
```

**Columns**:

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `distinct_id` | VARCHAR | PRIMARY KEY | User identifier |
| `properties` | JSON | - | All profile properties as JSON object |
| `last_seen` | TIMESTAMP | - | Last activity timestamp |

**Sample Data**:
```json
{
  "distinct_id": "user_123",
  "properties": {
    "$name": "Alice Johnson",
    "$email": "alice@example.com",
    "$created": "2023-06-15T08:00:00Z",
    "plan": "premium",
    "credits": 100
  },
  "last_seen": "2024-01-15T10:30:00Z"
}
```

**Query Patterns**:
```sql
-- Find profiles by property
SELECT
    distinct_id,
    properties->>'$.$name' as name
FROM profiles
WHERE properties->>'$.plan' = 'premium';

-- Join events with profiles
SELECT
    e.event_name,
    p.properties->>'$.$email' as email
FROM events e
JOIN profiles p ON e.distinct_id = p.distinct_id
WHERE e.event_time >= '2024-01-01';
```

---

### Metadata Table (_metadata)

**Purpose**: Internal tracking of fetch operations and table metadata

**Schema**:
```sql
CREATE TABLE _metadata (
    table_name VARCHAR PRIMARY KEY,
    type VARCHAR NOT NULL,
    fetched_at TIMESTAMP NOT NULL,
    from_date DATE,
    to_date DATE,
    row_count INTEGER NOT NULL
);
```

**Columns**:

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `table_name` | VARCHAR | PRIMARY KEY | Name of the user-created table |
| `type` | VARCHAR | NOT NULL | Table type: "events" or "profiles" |
| `fetched_at` | TIMESTAMP | NOT NULL | When the fetch completed |
| `from_date` | DATE | - | Start of date range (NULL for profiles) |
| `to_date` | DATE | - | End of date range (NULL for profiles) |
| `row_count` | INTEGER | NOT NULL | Number of rows inserted |

**Sample Data**:
```json
{
  "table_name": "events_january",
  "type": "events",
  "fetched_at": "2024-01-15T10:35:12Z",
  "from_date": "2024-01-01",
  "to_date": "2024-01-31",
  "row_count": 125430
}
```

**Usage**:
- Automatically populated by `create_events_table()` and `create_profiles_table()`
- Queried by `list_tables()`, `get_metadata()`
- Updated when table is dropped via `drop_table()`
- Not exposed in `list_tables()` results (internal implementation detail)

---

## Python Data Structures

### TableMetadata

**Purpose**: Metadata passed to table creation methods and stored in _metadata table

**Definition**:
```python
from dataclasses import dataclass
from datetime import datetime
from typing import Literal

@dataclass(frozen=True)
class TableMetadata:
    """Metadata for a fetch operation."""

    type: Literal["events", "profiles"]
    """Type of data fetched."""

    fetched_at: datetime
    """When the fetch completed."""

    from_date: str | None = None
    """Start date for events (YYYY-MM-DD), None for profiles."""

    to_date: str | None = None
    """End date for events (YYYY-MM-DD), None for profiles."""

    filter_events: list[str] | None = None
    """Event names filtered (if applicable)."""

    filter_where: str | None = None
    """WHERE clause filter (if applicable)."""
```

**Usage**:
```python
metadata = TableMetadata(
    type="events",
    fetched_at=datetime.now(timezone.utc),
    from_date="2024-01-01",
    to_date="2024-01-31"
)

row_count = storage.create_events_table("events_jan", data_iterator, metadata)
```

---

### TableInfo

**Purpose**: Summary information returned by `list_tables()`

**Definition**:
```python
@dataclass(frozen=True)
class TableInfo:
    """Information about a table in the database."""

    name: str
    """Table name."""

    type: Literal["events", "profiles"]
    """Table type."""

    row_count: int
    """Number of rows."""

    fetched_at: datetime
    """When data was fetched."""
```

**Usage**:
```python
tables = storage.list_tables()
for table in tables:
    print(f"{table.name}: {table.row_count} rows ({table.type})")
```

---

### TableSchema

**Purpose**: Schema information returned by `get_schema()`

**Definition**:
```python
@dataclass(frozen=True)
class ColumnInfo:
    """Information about a column."""

    name: str
    """Column name."""

    type: str
    """DuckDB type (VARCHAR, TIMESTAMP, JSON, etc.)."""

    nullable: bool
    """Whether column allows NULL."""

@dataclass(frozen=True)
class TableSchema:
    """Schema of a table."""

    table_name: str
    """Table name."""

    columns: list[ColumnInfo]
    """Column definitions."""
```

**Usage**:
```python
schema = storage.get_schema("events_jan")
for col in schema.columns:
    null_str = "NULL" if col.nullable else "NOT NULL"
    print(f"{col.name}: {col.type} {null_str}")
```

---

## Data Flow

### Table Creation Flow

```
User/FetcherService
    │
    ├─→ create_events_table(name, Iterator[dict], TableMetadata)
    │       │
    │       ├─→ Check table_exists(name) → raise TableExistsError if True
    │       │
    │       ├─→ CREATE TABLE {name} with events schema
    │       │
    │       ├─→ Batch insert loop:
    │       │     For each batch from iterator:
    │       │       - Collect rows (up to batch_size)
    │       │       - executemany(INSERT INTO {name} VALUES ...)
    │       │       - Call progress_callback if provided
    │       │
    │       ├─→ INSERT INTO _metadata (table_name, type, fetched_at, ...)
    │       │
    │       └─→ Return total row count
    │
    └─→ create_profiles_table(name, Iterator[dict], TableMetadata)
            └─→ [Similar flow with profiles schema]
```

### Query Execution Flow

```
User/Workspace
    │
    ├─→ execute_df(sql) → pandas.DataFrame
    │       └─→ conn.execute(sql).df()
    │
    ├─→ execute_scalar(sql) → Any
    │       └─→ conn.execute(sql).fetchone()[0]
    │
    ├─→ execute_rows(sql) → list[tuple]
    │       └─→ conn.execute(sql).fetchall()
    │
    └─→ execute(sql) → duckdb.DuckDBPyRelation
            └─→ conn.execute(sql)
```

### Introspection Flow

```
User/Workspace
    │
    ├─→ list_tables() → list[TableInfo]
    │       └─→ SELECT * FROM _metadata WHERE table_name != '_metadata'
    │
    ├─→ get_schema(table_name) → TableSchema
    │       └─→ PRAGMA table_info({table_name})
    │
    └─→ get_metadata(table_name) → TableMetadata
            └─→ SELECT * FROM _metadata WHERE table_name = {table_name}
```

## Validation Rules

### Table Creation
- `table_name` must be valid SQL identifier (alphanumeric + underscore, no spaces)
- `table_name` must not start with `_` (reserved for internal tables)
- `data` iterator must yield dictionaries with required fields:
  - Events: `event_name`, `event_time`, `distinct_id`, `insert_id`, `properties`
  - Profiles: `distinct_id`, `properties`, `last_seen`
- `TableMetadata.type` must match table creation method (`create_events_table` → "events")

### Query Execution
- SQL queries must be strings (no parameterized queries for execute_df/execute_scalar/execute_rows)
- Use parameterized queries for batch inserts (security)
- Catch and wrap all `duckdb.Error` exceptions in `QueryError`

### Data Types
- Timestamps stored as `TIMESTAMP` (UTC)
- JSON properties stored as `JSON` type (validated by DuckDB)
- All strings stored as `VARCHAR` (variable length, DuckDB optimizes encoding)

## Migration Strategy

**Not Applicable**: Initial implementation. No schema migrations needed.

**Future Considerations**:
- If schema changes required, use DuckDB's `ALTER TABLE` or create new table + data migration
- Version metadata table to track schema version
- Provide migration utilities in future releases
