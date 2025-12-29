# Workspace

The `Workspace` class is the unified entry point for all Mixpanel data operations.

## Overview

Workspace orchestrates four internal services:

- **DiscoveryService** — Schema exploration (events, properties, funnels, cohorts)
- **FetcherService** — Data ingestion from Mixpanel to DuckDB, or streaming without storage
- **LiveQueryService** — Real-time analytics queries
- **StorageEngine** — Local SQL query execution

## Key Features

### Append Mode

The `fetch_events()` and `fetch_profiles()` methods support an `append` parameter for incremental data loading:

```python
# Initial fetch
ws.fetch_events(name="events", from_date="2024-01-01", to_date="2024-01-31")

# Append more data (duplicates are automatically skipped)
ws.fetch_events(name="events", from_date="2024-02-01", to_date="2024-02-28", append=True)
```

This is useful for:

- **Incremental loading**: Fetch data in chunks without creating multiple tables
- **Crash recovery**: Resume a failed fetch from the last successful point
- **Extending date ranges**: Add more historical or recent data to an existing table

Duplicate events (by `insert_id`) and profiles (by `distinct_id`) are automatically skipped via `INSERT OR IGNORE`.

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
        - api
