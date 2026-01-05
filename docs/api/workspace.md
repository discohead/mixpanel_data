# Workspace

The `Workspace` class is the unified entry point for all Mixpanel data operations.

## Overview

Workspace orchestrates four internal services:

- **DiscoveryService** — Schema exploration (events, properties, funnels, cohorts)
- **FetcherService** — Data ingestion from Mixpanel to DuckDB, or streaming without storage
- **LiveQueryService** — Real-time analytics queries
- **StorageEngine** — Local SQL query execution

## Key Features

### Parallel Fetching

For large date ranges, use `parallel=True` for up to 10x faster exports:

```python
# Parallel fetch for large date ranges (recommended)
result = ws.fetch_events(
    name="events",
    from_date="2024-01-01",
    to_date="2024-12-31",
    parallel=True
)

print(f"Fetched {result.total_rows} rows in {result.duration_seconds:.1f}s")
```

Parallel fetching:

- Splits date ranges into 7-day chunks (configurable via `chunk_days`)
- Fetches chunks concurrently (configurable via `max_workers`, default: 10)
- Returns `ParallelFetchResult` with batch statistics and failure tracking
- Supports progress callbacks via `on_batch_complete`

### Parallel Profile Fetching

For large profile datasets, use `parallel=True` for up to 5x faster exports:

```python
# Parallel profile fetch for large datasets
result = ws.fetch_profiles(
    name="users",
    parallel=True,
    max_workers=5  # Default and max is 5
)

print(f"Fetched {result.total_rows} profiles in {result.duration_seconds:.1f}s")
print(f"Pages: {result.successful_pages} succeeded, {result.failed_pages} failed")
```

Parallel profile fetching:

- Uses page-based parallelism with session IDs for consistency
- Fetches pages concurrently (configurable via `max_workers`, default: 5, max: 5)
- Returns `ParallelProfileResult` with page statistics and failure tracking
- Supports progress callbacks via `on_page_complete`

### Append Mode

The `fetch_events()` and `fetch_profiles()` methods support an `append` parameter for incremental data loading:

```python
# Initial fetch
ws.fetch_events(name="events", from_date="2025-01-01", to_date="2025-01-31")

# Append more data (duplicates are automatically skipped)
ws.fetch_events(name="events", from_date="2025-02-01", to_date="2025-02-28", append=True)
```

This is useful for:

- **Incremental loading**: Fetch data in chunks without creating multiple tables
- **Crash recovery**: Resume a failed fetch from the last successful point
- **Extending date ranges**: Add more historical or recent data to an existing table
- **Retrying failed parallel batches**: Use append mode to retry specific date ranges

Duplicate events (by `insert_id`) and profiles (by `distinct_id`) are automatically skipped via `INSERT OR IGNORE`.

### Advanced Profile Fetching

The `fetch_profiles()` and `stream_profiles()` methods support advanced filtering options:

```python
# Fetch specific users by ID
ws.fetch_profiles(name="vip_users", distinct_ids=["user_1", "user_2", "user_3"])

# Fetch group profiles (e.g., companies)
ws.fetch_profiles(name="companies", group_id="companies")

# Fetch users based on behavior
ws.fetch_profiles(
    name="purchasers",
    behaviors=[{"window": "30d", "name": "buyers", "event_selectors": [{"event": "Purchase"}]}],
    where='(behaviors["buyers"] > 0)'
)

# Query historical profile state
ws.fetch_profiles(
    name="profiles_last_week",
    as_of_timestamp=int(time.time()) - 604800  # 7 days ago
)

# Get all users with cohort membership marked
ws.fetch_profiles(
    name="cohort_analysis",
    cohort_id="12345",
    include_all_users=True
)
```

**Parameter constraints:**

- `distinct_id` and `distinct_ids` are mutually exclusive
- `behaviors` and `cohort_id` are mutually exclusive
- `include_all_users` requires `cohort_id` to be set

## Class Reference

::: mixpanel_data.Workspace
    options:
      show_root_heading: true
      show_root_toc_entry: true
      members:
        - __init__
        - ephemeral
        - memory
        - open
        - close
        - test_credentials
        - events
        - properties
        - property_values
        - funnels
        - cohorts
        - list_bookmarks
        - top_events
        - lexicon_schemas
        - lexicon_schema
        - clear_discovery_cache
        - fetch_events
        - fetch_profiles
        - stream_events
        - stream_profiles
        - sql
        - sql_scalar
        - sql_rows
        - segmentation
        - funnel
        - retention
        - jql
        - event_counts
        - property_counts
        - activity_feed
        - query_saved_report
        - query_flows
        - frequency
        - segmentation_numeric
        - segmentation_sum
        - segmentation_average
        - property_distribution
        - numeric_summary
        - daily_counts
        - engagement_distribution
        - property_coverage
        - info
        - tables
        - table_schema
        - drop
        - drop_all
        - sample
        - summarize
        - event_breakdown
        - property_keys
        - column_stats
        - connection
        - db_path
        - api
