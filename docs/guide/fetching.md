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
        from_date="2025-01-01",
        to_date="2025-01-31"
    )

    print(f"Fetched {result.row_count} events")
    print(f"Duration: {result.duration_seconds:.1f}s")
    ```

=== "CLI"

    ```bash
    mp fetch events jan_events --from 2025-01-01 --to 2025-01-31
    ```

### Filtering Events

Fetch specific event types:

=== "Python"

    ```python
    result = ws.fetch_events(
        name="purchases",
        from_date="2025-01-01",
        to_date="2025-01-31",
        events=["Purchase", "Checkout Started"]
    )
    ```

=== "CLI"

    ```bash
    mp fetch events purchases --from 2025-01-01 --to 2025-01-31 \
        --events Purchase,"Checkout Started"
    ```

### Using Where Clauses

Filter with Mixpanel expression syntax:

=== "Python"

    ```python
    result = ws.fetch_events(
        name="premium_purchases",
        from_date="2025-01-01",
        to_date="2025-01-31",
        where='properties["plan"] == "premium"'
    )
    ```

=== "CLI"

    ```bash
    mp fetch events premium_purchases --from 2025-01-01 --to 2025-01-31 \
        --where 'properties["plan"] == "premium"'
    ```

### Limiting Results

Cap the number of events returned (max 100,000):

=== "Python"

    ```python
    result = ws.fetch_events(
        name="sample_events",
        from_date="2025-01-01",
        to_date="2025-01-31",
        limit=10000
    )
    ```

=== "CLI"

    ```bash
    mp fetch events sample_events --from 2025-01-01 --to 2025-01-31 \
        --limit 10000
    ```

This is useful for testing queries or sampling data before a full fetch.

### Progress Tracking

Monitor fetch progress with a callback:

```python
def on_progress(count: int) -> None:
    print(f"Fetched {count} events...")

result = ws.fetch_events(
    name="events",
    from_date="2025-01-01",
    to_date="2025-01-31",
    progress_callback=on_progress
)
```

The CLI automatically displays a progress bar.

### Batch Size

Control the memory/IO tradeoff with `batch_size`:

=== "Python"

    ```python
    # Smaller batch size = less memory, more disk IO
    result = ws.fetch_events(
        name="events",
        from_date="2025-01-01",
        to_date="2025-01-31",
        batch_size=500
    )

    # Larger batch size = more memory, less disk IO
    result = ws.fetch_events(
        name="events",
        from_date="2025-01-01",
        to_date="2025-01-31",
        batch_size=5000
    )
    ```

=== "CLI"

    ```bash
    mp fetch events --from 2025-01-01 --to 2025-01-31 --batch-size 500
    ```

The default is 1000 rows per commit. Valid range: 100-100,000.

## Parallel Fetching

For large date ranges, parallel fetching can dramatically speed up exports—up to 10x faster for multi-month ranges.

### Basic Parallel Fetch

Enable parallel fetching with the `parallel` flag:

=== "Python"

    ```python
    result = ws.fetch_events(
        name="q4_events",
        from_date="2024-10-01",
        to_date="2024-12-31",
        parallel=True
    )

    print(f"Fetched {result.total_rows} rows in {result.duration_seconds:.1f}s")
    print(f"Batches: {result.successful_batches} succeeded, {result.failed_batches} failed")
    ```

=== "CLI"

    ```bash
    mp fetch events q4_events --from 2024-10-01 --to 2024-12-31 --parallel
    ```

Parallel fetching splits the date range into 7-day chunks and fetches them concurrently using multiple threads. This bypasses Mixpanel's 100-day limit and enables faster exports.

### How It Works

1. **Date Range Chunking**: The date range is split into chunks (default: 7 days each)
2. **Concurrent Fetching**: Multiple threads fetch chunks simultaneously from Mixpanel
3. **Single-Writer Queue**: A dedicated writer thread serializes writes to DuckDB (respecting its single-writer constraint)
4. **Partial Failure Handling**: Failed batches are tracked for potential retry

### Performance

| Date Range | Sequential | Parallel (10 workers) | Speedup |
|------------|------------|----------------------|---------|
| 7 days | ~5s | ~5s | 1x (no benefit) |
| 30 days | ~20s | ~5s | 4x |
| 90 days | ~60s | ~8s | 7.5x |

!!! tip "When to Use Parallel Fetching"
    - **Use parallel** for date ranges > 7 days
    - **Use sequential** for small ranges or when you need the `limit` parameter

### Configuring Workers

Control the number of concurrent fetch threads:

=== "Python"

    ```python
    result = ws.fetch_events(
        name="events",
        from_date="2024-01-01",
        to_date="2024-03-31",
        parallel=True,
        max_workers=5  # Default is 10
    )
    ```

=== "CLI"

    ```bash
    mp fetch events --from 2024-01-01 --to 2024-03-31 --parallel --workers 5
    ```

Higher worker counts may hit Mixpanel rate limits. The default of 10 works well for most cases.

### Configuring Chunk Size

Control how many days each chunk covers:

=== "Python"

    ```python
    result = ws.fetch_events(
        name="events",
        from_date="2024-01-01",
        to_date="2024-03-31",
        parallel=True,
        chunk_days=14  # Default is 7
    )
    ```

=== "CLI"

    ```bash
    mp fetch events --from 2024-01-01 --to 2024-03-31 --parallel --chunk-days 14
    ```

Smaller chunk sizes create more parallel batches (potentially faster) but increase API overhead. Valid range: 1-100 days.

### Progress Callbacks

Monitor batch completion with a callback:

```python
from mixpanel_data import BatchProgress

def on_batch(progress: BatchProgress) -> None:
    status = "✓" if progress.success else "✗"
    print(f"[{status}] Batch {progress.batch_index + 1}/{progress.total_batches}: "
          f"{progress.from_date} to {progress.to_date} ({progress.rows} rows)")

result = ws.fetch_events(
    name="events",
    from_date="2024-01-01",
    to_date="2024-03-31",
    parallel=True,
    on_batch_complete=on_batch
)
```

The CLI automatically displays batch progress when `--parallel` is used.

### Handling Failures

Parallel fetching tracks failures and provides retry information:

```python
result = ws.fetch_events(
    name="events",
    from_date="2024-01-01",
    to_date="2024-03-31",
    parallel=True
)

if result.has_failures:
    print(f"Warning: {result.failed_batches} batches failed")
    for from_date, to_date in result.failed_date_ranges:
        print(f"  Failed: {from_date} to {to_date}")

    # Retry failed ranges with append mode
    for from_date, to_date in result.failed_date_ranges:
        ws.fetch_events(
            name="events",
            from_date=from_date,
            to_date=to_date,
            append=True  # Append to existing table
        )
```

!!! warning "Parallel Fetch Limitations"
    - **No `limit` parameter**: Parallel fetch does not support the `limit` parameter. Using both raises an error.
    - **Exit code 1 on partial failure**: The CLI returns exit code 1 if any batches fail, even if some succeeded.

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

### Filtering by Cohort

Fetch only profiles that are members of a specific cohort:

=== "Python"

    ```python
    result = ws.fetch_profiles(
        name="power_users",
        cohort_id="12345"
    )
    ```

=== "CLI"

    ```bash
    mp fetch profiles power_users --cohort 12345
    ```

### Selecting Specific Properties

Reduce bandwidth and memory by fetching only the properties you need:

=== "Python"

    ```python
    result = ws.fetch_profiles(
        name="user_emails",
        output_properties=["$email", "$name", "plan"]
    )
    ```

=== "CLI"

    ```bash
    mp fetch profiles user_emails --output-properties '$email,$name,plan'
    ```

### Combining Filters

Filters can be combined for precise data selection:

=== "Python"

    ```python
    result = ws.fetch_profiles(
        name="premium_emails",
        cohort_id="premium_cohort",
        output_properties=["$email", "$name"],
        where='properties["country"] == "US"'
    )
    ```

=== "CLI"

    ```bash
    mp fetch profiles premium_emails \
        --cohort premium_cohort \
        --output-properties '$email,$name' \
        --where 'properties["country"] == "US"'
    ```

### Fetching Specific Users by ID

Fetch one or more specific users by their distinct ID:

=== "Python"

    ```python
    # Single user
    result = ws.fetch_profiles(
        name="single_user",
        distinct_id="user_123"
    )

    # Multiple specific users
    result = ws.fetch_profiles(
        name="specific_users",
        distinct_ids=["user_1", "user_2", "user_3"]
    )
    ```

=== "CLI"

    ```bash
    # Single user
    mp fetch profiles single_user --distinct-id user_123

    # Multiple specific users
    mp fetch profiles specific_users \
        --distinct-ids user_1 --distinct-ids user_2 --distinct-ids user_3
    ```

!!! note "Mutually Exclusive"
    `distinct_id` and `distinct_ids` cannot be used together. Choose one approach based on your needs.

### Fetching Group Profiles

Fetch group profiles (companies, accounts, etc.) instead of user profiles:

=== "Python"

    ```python
    result = ws.fetch_profiles(
        name="companies",
        group_id="companies"  # The group type defined in your Mixpanel project
    )
    ```

=== "CLI"

    ```bash
    mp fetch profiles companies --group-id companies
    ```

### Behavioral Filtering

Filter profiles by event behavior—users who performed specific actions. Behaviors use a named pattern that you reference in a `where` clause:

=== "Python"

    ```python
    # Users who purchased in the last 30 days
    result = ws.fetch_profiles(
        name="recent_purchasers",
        behaviors=[{
            "window": "30d",
            "name": "made_purchase",
            "event_selectors": [{"event": "Purchase"}]
        }],
        where='(behaviors["made_purchase"] > 0)'
    )

    # Users with multiple behavior criteria
    result = ws.fetch_profiles(
        name="engaged_users",
        behaviors=[
            {
                "window": "30d",
                "name": "purchased",
                "event_selectors": [{"event": "Purchase"}]
            },
            {
                "window": "7d",
                "name": "active",
                "event_selectors": [{"event": "Page View"}]
            }
        ],
        where='(behaviors["purchased"] > 0) and (behaviors["active"] >= 5)'
    )
    ```

=== "CLI"

    ```bash
    # Users who purchased in the last 30 days
    mp fetch profiles recent_purchasers \
        --behaviors '[{"window":"30d","name":"made_purchase","event_selectors":[{"event":"Purchase"}]}]' \
        --where '(behaviors["made_purchase"] > 0)'

    # Users with multiple behavior criteria
    mp fetch profiles engaged_users \
        --behaviors '[{"window":"30d","name":"purchased","event_selectors":[{"event":"Purchase"}]},{"window":"7d","name":"active","event_selectors":[{"event":"Page View"}]}]' \
        --where '(behaviors["purchased"] > 0) and (behaviors["active"] >= 5)'
    ```

!!! info "Behavior Format"
    Each behavior requires:

    - `window`: Time window (e.g., "30d", "7d", "90d")
    - `name`: Identifier to reference in `where` clause
    - `event_selectors`: Array of event filters with `{"event": "Event Name"}`

    The `where` clause filters using `behaviors["name"]` to check counts.

!!! warning "Mutually Exclusive"
    `behaviors` and `cohort_id` cannot be used together. Use one or the other for filtering.

### Historical Profile State

Query profile properties as they existed at a specific point in time:

=== "Python"

    ```python
    import time

    # Get profiles as of January 1, 2024
    timestamp = 1704067200  # Unix timestamp

    result = ws.fetch_profiles(
        name="historical_profiles",
        as_of_timestamp=timestamp
    )
    ```

=== "CLI"

    ```bash
    # Get profiles as of January 1, 2024 (Unix timestamp)
    mp fetch profiles historical_profiles --as-of-timestamp 1704067200
    ```

### Cohort Membership Analysis

Include all users and mark whether they're in a cohort:

=== "Python"

    ```python
    result = ws.fetch_profiles(
        name="cohort_analysis",
        cohort_id="power_users",
        include_all_users=True  # Include non-members too
    )
    ```

=== "CLI"

    ```bash
    mp fetch profiles cohort_analysis \
        --cohort power_users --include-all-users
    ```

This is useful for comparing users inside and outside a cohort. The response includes a membership indicator for each profile.

!!! note "Requires Cohort"
    `include_all_users` requires `cohort_id`. It has no effect without specifying a cohort.

## Table Naming

Tables are stored with the name you provide:

```python
ws.fetch_events(name="jan_events", ...)   # Creates table: jan_events
ws.fetch_events(name="feb_events", ...)   # Creates table: feb_events
ws.fetch_profiles(name="users")            # Creates table: users
```

!!! warning "Table Names Must Be Unique"
    Fetching to an existing table name raises `TableExistsError`. Use `--replace` to overwrite, `--append` to add data, or choose a different name.

## Replacing and Appending

### Replace Mode

Drop and recreate a table with fresh data:

=== "Python"

    ```python
    # First drop the table, then fetch
    ws.drop("events")
    result = ws.fetch_events(
        name="events",
        from_date="2025-01-01",
        to_date="2025-01-31"
    )
    ```

=== "CLI"

    ```bash
    mp fetch events --from 2025-01-01 --to 2025-01-31 --replace
    ```

### Append Mode

Add data to an existing table. Duplicates (by `insert_id` for events, `distinct_id` for profiles) are automatically skipped:

=== "Python"

    ```python
    # Initial fetch
    ws.fetch_events(
        name="events",
        from_date="2025-01-01",
        to_date="2025-01-31"
    )

    # Append more data
    ws.fetch_events(
        name="events",
        from_date="2025-02-01",
        to_date="2025-02-28",
        append=True
    )
    ```

=== "CLI"

    ```bash
    # Initial fetch
    mp fetch events --from 2025-01-01 --to 2025-01-31

    # Append more data
    mp fetch events --from 2025-02-01 --to 2025-02-28 --append
    ```

!!! tip "Resuming Failed Fetches"
    If a fetch crashes or times out, use append mode to resume from where you left off:

    ```bash
    # Check the last event timestamp
    mp query sql "SELECT MAX(event_time) FROM events"
    # 2025-01-15T14:30:00

    # Resume from that point
    mp fetch events --from 2025-01-15 --to 2025-01-31 --append
    ```

    Overlapping date ranges are safe—duplicates are automatically skipped.

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
result.metadata.from_date    # "2025-01-01"
result.metadata.to_date      # "2025-01-31"
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

### Use Parallel Fetching for Large Date Ranges

For date ranges longer than a week, use parallel fetching for the best performance:

=== "Python"

    ```python
    # Recommended: Parallel fetch for large date ranges
    result = ws.fetch_events(
        name="events_2025",
        from_date="2025-01-01",
        to_date="2025-12-31",
        parallel=True
    )
    print(f"Fetched {result.total_rows} rows in {result.duration_seconds:.1f}s")
    ```

=== "CLI"

    ```bash
    # Recommended: Parallel fetch for large date ranges
    mp fetch events events_2025 --from 2025-01-01 --to 2025-12-31 --parallel
    ```

Parallel fetching automatically handles chunking, concurrent API requests, and serialized writes to DuckDB—no manual chunking required.

### Manual Chunking (Alternative)

If you need the `limit` parameter (incompatible with parallel), or want fine-grained control, you can manually chunk:

=== "Single Table (Recommended)"

    ```python
    import datetime

    # Fetch first chunk
    ws.fetch_events(
        name="events_2025",
        from_date="2025-01-01",
        to_date="2025-01-31"
    )

    # Append subsequent chunks
    start = datetime.date(2025, 2, 1)
    end = datetime.date(2025, 12, 31)

    current = start
    while current <= end:
        chunk_end = min(current + datetime.timedelta(days=30), end)

        ws.fetch_events(
            name="events_2025",
            from_date=str(current),
            to_date=str(chunk_end),
            append=True  # Add to existing table
        )

        current = chunk_end + datetime.timedelta(days=1)
    ```

=== "CLI"

    ```bash
    # Fetch month by month, appending to a single table
    mp fetch events events_2025 --from 2025-01-01 --to 2025-01-31
    mp fetch events events_2025 --from 2025-02-01 --to 2025-02-29 --append
    mp fetch events events_2025 --from 2025-03-01 --to 2025-03-31 --append
    # ... continue for each month
    ```

=== "Separate Tables"

    ```python
    import datetime

    start = datetime.date(2025, 1, 1)
    end = datetime.date(2025, 12, 31)

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

### Choose the Right Storage Mode

mixpanel_data offers three storage modes:

| Mode | Method | Disk Usage | Best For |
|------|--------|------------|----------|
| **Persistent** | `Workspace()` | Yes (permanent) | Repeated analysis, large datasets |
| **Ephemeral** | `Workspace.ephemeral()` | Yes (temp file, auto-deleted) | One-off analysis with large data |
| **In-Memory** | `Workspace.memory()` | None | Small datasets, testing, zero disk footprint |

**Ephemeral mode** creates a temp file that benefits from DuckDB's compression—up to 8× faster for large datasets:

```python
with mp.Workspace.ephemeral() as ws:
    ws.fetch_events("events", from_date="2025-01-01", to_date="2025-01-31")
    result = ws.sql("SELECT event_name, COUNT(*) FROM events GROUP BY 1")
# Database automatically deleted
```

**In-memory mode** creates no files at all—ideal for small datasets, unit tests, or privacy-sensitive scenarios:

```python
with mp.Workspace.memory() as ws:
    ws.fetch_events("events", from_date="2025-01-01", to_date="2025-01-07")
    total = ws.sql_scalar("SELECT COUNT(*) FROM events")
# Database gone - no files ever created
```

!!! tip "When to use each mode"
    - **Persistent**: You'll query the same data multiple times across sessions
    - **Ephemeral**: Large datasets where you need compression benefits but won't keep the data
    - **In-Memory**: Small datasets, unit tests, or when zero disk footprint is required

## Streaming as an Alternative

If you don't need to store data locally, use streaming instead:

| Approach | Storage | Best For |
|----------|---------|----------|
| `fetch_events()` | DuckDB table | Repeated SQL analysis |
| `stream_events()` | None | ETL pipelines, one-time processing |

```python
# Stream directly without storage
for event in ws.stream_events(from_date="2025-01-01", to_date="2025-01-31"):
    send_to_warehouse(event)
```

See [Streaming Data](streaming.md) for details.

## Next Steps

- [Streaming Data](streaming.md) — Process data without local storage
- [SQL Queries](sql-queries.md) — Query your fetched data with SQL
- [Live Analytics](live-analytics.md) — Query Mixpanel directly for real-time data
