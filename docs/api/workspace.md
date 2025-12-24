# Workspace

The `Workspace` class is the unified entry point for all Mixpanel data operations.

## Overview

Workspace orchestrates four internal services:

- **DiscoveryService** — Schema exploration (events, properties, funnels, cohorts)
- **FetcherService** — Data ingestion from Mixpanel to DuckDB, or streaming without storage
- **LiveQueryService** — Real-time analytics queries
- **StorageEngine** — Local SQL query execution

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
        - top_events
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
        - insights
        - frequency
        - segmentation_numeric
        - segmentation_sum
        - segmentation_average
        - info
        - tables
        - schema
        - drop
        - drop_all
        - connection
        - api
