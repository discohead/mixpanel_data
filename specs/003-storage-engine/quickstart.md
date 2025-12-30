# Quickstart: Storage Engine

**Phase**: 1 (Design & Contracts)
**Audience**: Developers implementing or consuming StorageEngine
**Purpose**: Practical examples demonstrating core workflows

## Installation

```bash
# Install mixpanel_data (includes StorageEngine)
pip install mixpanel_data

# Or install from source
git clone https://github.com/jaredmcfarland/mixpanel_data
cd mixpanel_data
pip install -e .
```

## Basic Usage

### Persistent Storage

Create a database that survives between sessions:

```python
from pathlib import Path
from datetime import datetime, timezone
from mixpanel_data._internal.storage import StorageEngine
from mixpanel_data.types import TableMetadata

# Create database at specific path
storage = StorageEngine(path=Path("~/my_analysis.db").expanduser())

try:
    # Prepare data (iterator for memory efficiency)
    def events():
        yield {
            "event_name": "Purchase",
            "event_time": datetime.now(timezone.utc),
            "distinct_id": "user_123",
            "insert_id": "evt_001",
            "properties": {"amount": 29.99, "currency": "USD"}
        }

    # Create table with metadata
    metadata = TableMetadata(
        type="events",
        fetched_at=datetime.now(timezone.utc),
        from_date="2024-01-01",
        to_date="2024-01-31"
    )

    row_count = storage.create_events_table("purchases", events(), metadata)
    print(f"Inserted {row_count} events")

    # Query data
    df = storage.execute_df("SELECT * FROM purchases")
    print(df)

finally:
    storage.close()
```

### Ephemeral Analysis

Quick analysis without leaving database files:

```python
from mixpanel_data._internal.storage import StorageEngine
from mixpanel_data.types import TableMetadata

# Automatic cleanup with context manager
with StorageEngine.ephemeral() as storage:
    # Database created in temp directory

    def sample_data():
        for i in range(100):
            yield {
                "event_name": "Page View",
                "event_time": datetime.now(timezone.utc),
                "distinct_id": f"user_{i}",
                "insert_id": f"evt_{i}",
                "properties": {"page": f"/page{i % 10}"}
            }

    metadata = TableMetadata(type="events", fetched_at=datetime.now(timezone.utc))
    storage.create_events_table("pageviews", sample_data(), metadata)

    # Analyze
    top_pages = storage.execute_df("""
        SELECT
            properties->>'$.page' as page,
            COUNT(*) as views
        FROM pageviews
        GROUP BY page
        ORDER BY views DESC
        LIMIT 10
    """)
    print(top_pages)

# Database automatically deleted here
```

## Core Workflows

### 1. Streaming Large Datasets

Handle millions of events without running out of memory:

```python
def fetch_events_from_api():
    """Simulates fetching from Mixpanel API."""
    for i in range(1_000_000):
        yield {
            "event_name": "Impression",
            "event_time": datetime.now(timezone.utc),
            "distinct_id": f"user_{i % 10000}",
            "insert_id": f"imp_{i}",
            "properties": {"campaign": f"camp_{i % 100}"}
        }

def on_progress(rows: int):
    """Progress callback (optional)."""
    if rows % 10000 == 0:
        print(f"Inserted {rows:,} rows...")

with StorageEngine.ephemeral() as storage:
    metadata = TableMetadata(type="events", fetched_at=datetime.now(timezone.utc))

    # Memory usage stays constant (< 500MB)
    row_count = storage.create_events_table(
        "impressions",
        fetch_events_from_api(),
        metadata,
        progress_callback=on_progress
    )

    print(f"Total: {row_count:,} rows")
```

### 2. Querying with Different Formats

Choose the right format for your use case:

```python
with StorageEngine.ephemeral() as storage:
    # ... create table ...

    # DataFrame (for data science, pandas integration)
    df = storage.execute_df("""
        SELECT event_name, COUNT(*) as count
        FROM events
        GROUP BY event_name
    """)
    print(df.describe())

    # Scalar (for single values)
    total = storage.execute_scalar("SELECT COUNT(*) FROM events")
    assert isinstance(total, int)

    # Rows (for iteration)
    for event_name, count in storage.execute_rows("SELECT event_name, COUNT(*) FROM events GROUP BY 1"):
        print(f"{event_name}: {count}")

    # Raw DuckDB relation (for advanced features)
    relation = storage.execute("SELECT * FROM events")
    filtered = relation.filter("event_time > '2024-01-01'")
    result = filtered.df()
```

### 3. JSON Property Queries

Query dynamic properties stored in JSON column:

```python
# Extract string property
df = storage.execute_df("""
    SELECT
        properties->>'$.country' as country,
        COUNT(*) as count
    FROM events
    WHERE properties->>'$.country' IS NOT NULL
    GROUP BY country
""")

# Extract and cast numeric property
df = storage.execute_df("""
    SELECT
        event_name,
        CAST(properties->>'$.amount' AS DECIMAL) as amount
    FROM events
    WHERE CAST(properties->>'$.amount' AS DECIMAL) > 100
""")

# Nested property access
df = storage.execute_df("""
    SELECT properties->>'$.user.plan' as plan
    FROM events
""")
```

### 4. Introspection

Discover what data is available:

```python
with StorageEngine.ephemeral() as storage:
    # ... create tables ...

    # List all tables
    for table in storage.list_tables():
        print(f"{table.name}:")
        print(f"  Type: {table.type}")
        print(f"  Rows: {table.row_count:,}")
        print(f"  Fetched: {table.fetched_at}")

    # Get schema for a table
    schema = storage.get_schema("events")
    for col in schema.columns:
        null_str = "NULL" if col.nullable else "NOT NULL"
        print(f"{col.name}: {col.type} {null_str}")

    # Get fetch metadata
    metadata = storage.get_metadata("events")
    print(f"Date range: {metadata.from_date} to {metadata.to_date}")
```

### 5. Error Handling

Handle common error conditions:

```python
from mixpanel_data.exceptions import TableExistsError, TableNotFoundError, QueryError

with StorageEngine.ephemeral() as storage:

    # Prevent accidental overwrites
    if storage.table_exists("events"):
        storage.drop_table("events")

    storage.create_events_table("events", data_iter, metadata)

    # Handle duplicate creation
    try:
        storage.create_events_table("events", data_iter, metadata)
    except TableExistsError as e:
        print(f"Table already exists: {e.table_name}")

    # Handle missing tables
    try:
        storage.get_schema("missing_table")
    except TableNotFoundError as e:
        print(f"Table not found: {e.table_name}")

    # Handle SQL errors
    try:
        storage.execute_df("SELECT * FROM nonexistent")
    except QueryError as e:
        print(f"Query failed: {e.message}")
        print(f"Query: {e.details['query']}")
```

### 6. Table Replacement

Safely replace existing table with new data:

```python
with StorageEngine.ephemeral() as storage:
    table_name = "events"

    # Check and drop if exists
    if storage.table_exists(table_name):
        storage.drop_table(table_name)

    # Create fresh table
    storage.create_events_table(table_name, new_data_iter, metadata)
```

## Advanced Patterns

### Direct DuckDB Access

For advanced features not exposed by StorageEngine:

```python
with StorageEngine.ephemeral() as storage:
    # Set DuckDB pragmas
    storage.connection.execute("PRAGMA threads=4")
    storage.connection.execute("PRAGMA memory_limit='2GB'")

    # Use DuckDB-specific features
    storage.connection.execute("""
        COPY events TO 'events.parquet' (FORMAT PARQUET)
    """)
```

### Custom Batch Size

Control memory vs. performance tradeoff:

```python
class StorageEngineWithCustomBatch(StorageEngine):
    def create_events_table(self, name, data, metadata, progress_callback=None):
        # Implementation would use different batch size
        # This is for illustration - actual API doesn't expose batch_size
        pass
```

## Integration Examples

### With Workspace Facade

StorageEngine is typically used via the Workspace facade:

```python
from mixpanel_data import Workspace

# Workspace handles StorageEngine creation
with Workspace.ephemeral() as ws:
    # Fetch creates table using StorageEngine internally
    ws.fetch_events(
        name="events",
        from_date="2024-01-01",
        to_date="2024-01-31"
    )

    # Query uses StorageEngine internally
    df = ws.sql("SELECT * FROM events")
```

### With Custom Iterators

Adapt any data source to StorageEngine:

```python
import csv

def events_from_csv(path: str):
    """Read events from CSV file."""
    with open(path) as f:
        reader = csv.DictReader(f)
        for row in reader:
            yield {
                "event_name": row["event"],
                "event_time": row["timestamp"],
                "distinct_id": row["user_id"],
                "insert_id": row["id"],
                "properties": {"source": "csv"}
            }

with StorageEngine.ephemeral() as storage:
    metadata = TableMetadata(type="events", fetched_at=datetime.now(timezone.utc))
    storage.create_events_table("events", events_from_csv("data.csv"), metadata)
```

## Performance Tips

1. **Use streaming ingestion**: Always provide iterators, not lists
2. **Batch inserts automatically**: StorageEngine handles batching internally
3. **Index strategy**: Primary keys only; DuckDB's columnar storage is fast without indexes
4. **JSON queries**: DuckDB's JSON support is optimized; use `->>'$'` syntax
5. **Memory limits**: For very large datasets, set DuckDB memory limit via `storage.connection.execute("PRAGMA memory_limit='1GB'")`

## Common Pitfalls

❌ **Don't**: Load entire dataset into memory first
```python
events_list = list(fetch_events())  # Bad: loads everything
storage.create_events_table("events", events_list, metadata)
```

✅ **Do**: Use iterators
```python
storage.create_events_table("events", fetch_events(), metadata)  # Good: streams
```

❌ **Don't**: Forget to handle table existence
```python
storage.create_events_table("events", data, metadata)  # Fails if exists
```

✅ **Do**: Check or drop first
```python
if storage.table_exists("events"):
    storage.drop_table("events")
storage.create_events_table("events", data, metadata)
```

❌ **Don't**: Forget to close persistent databases
```python
storage = StorageEngine(path=Path("data.db"))
# ... use storage ...
# Forgot to close - connection left open
```

✅ **Do**: Use context managers or explicit close
```python
with StorageEngine(path=Path("data.db")) as storage:
    # ... use storage ...
# Automatically closed
```

## Next Steps

- **Full API Reference**: See [contracts/storage_engine.py](contracts/storage_engine.py)
- **Implementation Details**: See [research.md](research.md)
- **Data Model**: See [data-model.md](data-model.md)
- **Testing**: Review tests in `tests/unit/test_storage.py` and `tests/integration/test_storage_integration.py`

## Support

For issues, questions, or contributions:
- GitHub Issues: https://github.com/jaredmcfarland/mixpanel_data/issues
- Documentation: https://github.com/jaredmcfarland/mixpanel_data/blob/main/README.md
