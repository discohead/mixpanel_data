# Fetching Data

Fetch events and user profiles from Mixpanel into a local DuckDB database for fast, repeated SQL queries.

## Fetching Events

### Basic Usage

Fetch all events for a date range:

=== "Python"

    ```python
    import mixpanel_data as mp

    ws = mp.Workspace()
    result = ws.fetch_events(
        name="jan_events",
        from_date="2024-01-01",
        to_date="2024-01-31"
    )

    print(f"Fetched {result.row_count} events")
    print(f"Duration: {result.duration_seconds:.1f}s")
    ```

=== "CLI"

    ```bash
    mp fetch events jan_events --from 2024-01-01 --to 2024-01-31
    ```

### Filtering Events

Fetch specific event types:

=== "Python"

    ```python
    result = ws.fetch_events(
        name="purchases",
        from_date="2024-01-01",
        to_date="2024-01-31",
        events=["Purchase", "Checkout Started"]
    )
    ```

=== "CLI"

    ```bash
    mp fetch events purchases --from 2024-01-01 --to 2024-01-31 \
        --events Purchase,"Checkout Started"
    ```

### Using Where Clauses

Filter with Mixpanel expression syntax:

=== "Python"

    ```python
    result = ws.fetch_events(
        name="premium_purchases",
        from_date="2024-01-01",
        to_date="2024-01-31",
        where='properties["plan"] == "premium"'
    )
    ```

=== "CLI"

    ```bash
    mp fetch events premium_purchases --from 2024-01-01 --to 2024-01-31 \
        --where 'properties["plan"] == "premium"'
    ```

### Progress Tracking

Monitor fetch progress with a callback:

```python
def on_progress(count: int) -> None:
    print(f"Fetched {count} events...")

result = ws.fetch_events(
    name="events",
    from_date="2024-01-01",
    to_date="2024-01-31",
    progress_callback=on_progress
)
```

The CLI automatically displays a progress bar.

## Fetching Profiles

Fetch user profiles into local storage:

=== "Python"

    ```python
    result = ws.fetch_profiles(name="users")
    print(f"Fetched {result.row_count} profiles")
    ```

=== "CLI"

    ```bash
    mp fetch profiles users
    ```

### Filtering Profiles

Use Mixpanel expression syntax:

=== "Python"

    ```python
    result = ws.fetch_profiles(
        name="premium_users",
        where='properties["plan"] == "premium"'
    )
    ```

=== "CLI"

    ```bash
    mp fetch profiles premium_users \
        --where 'properties["plan"] == "premium"'
    ```

## Table Naming

Tables are stored with the name you provide:

```python
ws.fetch_events(name="jan_events", ...)   # Creates table: jan_events
ws.fetch_events(name="feb_events", ...)   # Creates table: feb_events
ws.fetch_profiles(name="users")            # Creates table: users
```

!!! warning "Table Names Must Be Unique"
    Fetching to an existing table name raises `TableExistsError`. Drop the table first or use a different name.

## Table Management

### Listing Tables

```python
tables = ws.tables()
for table in tables:
    print(f"{table.name}: {table.row_count} rows ({table.type})")
```

### Viewing Table Schema

```python
schema = ws.schema("jan_events")
for col in schema.columns:
    print(f"{col.name}: {col.type}")
```

### Dropping Tables

```python
ws.drop("jan_events")  # Drop single table
ws.drop_all()          # Drop all tables
```

## FetchResult

Both `fetch_events()` and `fetch_profiles()` return a `FetchResult`:

```python
result = ws.fetch_events(...)

# Attributes
result.table_name       # "jan_events"
result.row_count        # 125000
result.duration_seconds # 45.2

# Metadata
result.metadata.from_date    # "2024-01-01"
result.metadata.to_date      # "2024-01-31"
result.metadata.events       # ["Purchase", "Signup"] or None
result.metadata.where        # 'properties["plan"]...' or None
result.metadata.fetched_at   # datetime

# Serialization
result.to_dict()  # JSON-serializable dict
```

## Event Table Schema

Fetched events have this schema:

| Column | Type | Description |
|--------|------|-------------|
| `event_id` | VARCHAR | Unique event identifier |
| `event_name` | VARCHAR | Event name |
| `event_time` | TIMESTAMP | When the event occurred |
| `distinct_id` | VARCHAR | User identifier |
| `insert_id` | VARCHAR | Deduplication ID |
| `properties` | JSON | All event properties |

## Profile Table Schema

Fetched profiles have this schema:

| Column | Type | Description |
|--------|------|-------------|
| `distinct_id` | VARCHAR | User identifier (primary key) |
| `properties` | JSON | All profile properties |

## Best Practices

### Chunk Large Date Ranges

For very large datasets, fetch in chunks:

```python
import datetime

start = datetime.date(2024, 1, 1)
end = datetime.date(2024, 12, 31)

current = start
while current < end:
    chunk_end = min(current + datetime.timedelta(days=30), end)
    table_name = f"events_{current.strftime('%Y%m')}"

    ws.fetch_events(
        name=table_name,
        from_date=str(current),
        to_date=str(chunk_end)
    )

    current = chunk_end + datetime.timedelta(days=1)
```

### Use Ephemeral Workspaces for One-Off Analysis

```python
with mp.Workspace.ephemeral() as ws:
    ws.fetch_events("events", from_date="2024-01-01", to_date="2024-01-07")
    result = ws.sql("SELECT event_name, COUNT(*) FROM events GROUP BY 1")
# Database automatically deleted
```

## Next Steps

- [SQL Queries](sql-queries.md) — Query your fetched data with SQL
- [Live Analytics](live-analytics.md) — Query Mixpanel directly for real-time data
