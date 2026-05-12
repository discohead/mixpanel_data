# Data Model: Fetch Service

**Feature**: 005-fetch-service
**Date**: 2025-12-22

## Overview

The Fetch Service operates on data flowing from the Mixpanel API to local DuckDB storage. This document defines the data structures involved in this transformation pipeline.

---

## Entity Definitions

### 1. FetchResult (Existing - types.py)

The outcome of a fetch operation, returned to the caller.

| Field | Type | Description |
|-------|------|-------------|
| `table` | `str` | Name of the created table |
| `rows` | `int` | Number of rows fetched and stored |
| `type` | `Literal["events", "profiles"]` | Type of data fetched |
| `duration_seconds` | `float` | Time taken to complete the fetch |
| `date_range` | `tuple[str, str] \| None` | (from_date, to_date) for events; None for profiles |
| `fetched_at` | `datetime` | UTC timestamp when fetch completed |

**Properties**:
- `df`: Lazy pandas DataFrame conversion (computed on first access)

**Methods**:
- `to_dict()`: JSON-serializable dictionary representation

---

### 2. TableMetadata (Existing - types.py)

Metadata about a fetch operation, persisted in the database.

| Field | Type | Description |
|-------|------|-------------|
| `type` | `Literal["events", "profiles"]` | Type of data |
| `fetched_at` | `datetime` | UTC timestamp when fetch completed |
| `from_date` | `str \| None` | Start date (YYYY-MM-DD) for events; None for profiles |
| `to_date` | `str \| None` | End date (YYYY-MM-DD) for events; None for profiles |
| `filter_events` | `list[str] \| None` | Event names filtered (if applicable) |
| `filter_where` | `str \| None` | WHERE clause filter (if applicable) |

---

### 3. API Event (Input - from MixpanelAPIClient)

Raw event as received from the Mixpanel Export API.

```python
{
    "event": str,           # Event name
    "properties": {
        "distinct_id": str,     # User identifier
        "time": int,            # Unix timestamp (seconds)
        "$insert_id": str,      # Deduplication ID (may be missing)
        # ... additional custom properties
    }
}
```

---

### 4. Storage Event (Output - for StorageEngine)

Transformed event ready for DuckDB storage.

```python
{
    "event_name": str,      # From API "event" field
    "event_time": int,      # From API "properties.time"
    "distinct_id": str,     # From API "properties.distinct_id"
    "insert_id": str,       # From API "properties.$insert_id" or generated UUID
    "properties": dict,     # Remaining properties (without extracted fields)
}
```

**Transformation Rules**:
1. `event` → `event_name`
2. `properties.time` → `event_time`
3. `properties.distinct_id` → `distinct_id`
4. `properties.$insert_id` → `insert_id` (generate UUID if missing)
5. Remove `time`, `distinct_id`, `$insert_id` from properties dict
6. Store remaining properties as JSON

---

### 5. API Profile (Input - from MixpanelAPIClient)

Raw profile as received from the Mixpanel Engage API.

```python
{
    "$distinct_id": str,        # User identifier
    "$properties": {
        "$last_seen": str,          # ISO timestamp (may be missing)
        # ... additional custom properties
    }
}
```

---

### 6. Storage Profile (Output - for StorageEngine)

Transformed profile ready for DuckDB storage.

```python
{
    "distinct_id": str,     # From API "$distinct_id"
    "last_seen": str | None, # From API "$properties.$last_seen" or None
    "properties": dict,     # Remaining $properties (without $last_seen)
}
```

**Transformation Rules**:
1. `$distinct_id` → `distinct_id`
2. `$properties.$last_seen` → `last_seen` (None if missing)
3. Remove `$last_seen` from properties dict
4. Store remaining `$properties` as JSON in `properties`

---

## Entity Relationships

```
┌─────────────────────────────────────────────────────────────────────┐
│                        Fetch Service Pipeline                        │
└─────────────────────────────────────────────────────────────────────┘

┌────────────────┐     transform      ┌─────────────────┐
│   API Event    │ ─────────────────► │  Storage Event  │
│   (iterator)   │                    │   (iterator)    │
└────────────────┘                    └────────┬────────┘
                                               │
                                               ▼
┌────────────────┐     transform      ┌─────────────────┐
│  API Profile   │ ─────────────────► │ Storage Profile │
│   (iterator)   │                    │   (iterator)    │
└────────────────┘                    └────────┬────────┘
                                               │
                                               ▼
                                      ┌─────────────────┐
                                      │  StorageEngine  │
                                      │  create_*_table │
                                      └────────┬────────┘
                                               │
                                               ▼
                                      ┌─────────────────┐
                                      │  TableMetadata  │
                                      │  (persisted)    │
                                      └────────┬────────┘
                                               │
                                               ▼
                                      ┌─────────────────┐
                                      │   FetchResult   │
                                      │   (returned)    │
                                      └─────────────────┘
```

---

## State Transitions

### Fetch Operation Lifecycle

```
┌─────────┐     start      ┌────────────┐     complete     ┌───────────┐
│  IDLE   │ ─────────────► │  FETCHING  │ ───────────────► │ COMPLETED │
└─────────┘                └────────────┘                  └───────────┘
                                 │
                                 │ error
                                 ▼
                           ┌──────────┐
                           │  FAILED  │
                           │(rollback)│
                           └──────────┘
```

**States**:
- **IDLE**: Service ready to accept fetch request
- **FETCHING**: Data streaming from API to storage
- **COMPLETED**: FetchResult returned, table queryable
- **FAILED**: Error occurred, transaction rolled back

Note: These states are implicit (not tracked as a field). The FetcherService is stateless; each call is independent.

---

## Validation Rules

### Event Validation (performed by StorageEngine)

| Field | Rule |
|-------|------|
| `event_name` | Required, non-empty string |
| `event_time` | Required, valid timestamp |
| `distinct_id` | Required, non-empty string |
| `insert_id` | Required, non-empty string (generated if missing from API) |
| `properties` | Required, valid JSON object |

### Profile Validation (performed by StorageEngine)

| Field | Rule |
|-------|------|
| `distinct_id` | Required, non-empty string |
| `last_seen` | Optional, valid timestamp or None |
| `properties` | Required, valid JSON object |

### Table Name Validation (performed by StorageEngine)

| Rule | Example |
|------|---------|
| Alphanumeric + underscore only | `events_jan`, `user_profiles` |
| Cannot start with underscore | `_metadata` reserved for internal use |
| Case-sensitive | `Events` ≠ `events` |

---

## Database Schema (Reference)

### Events Table

```sql
CREATE TABLE {name} (
    event_name VARCHAR NOT NULL,
    event_time TIMESTAMP NOT NULL,
    distinct_id VARCHAR NOT NULL,
    insert_id VARCHAR PRIMARY KEY,
    properties JSON
)
```

### Profiles Table

```sql
CREATE TABLE {name} (
    distinct_id VARCHAR PRIMARY KEY,
    properties JSON,
    last_seen TIMESTAMP
)
```

### Metadata Table (Internal)

```sql
CREATE TABLE IF NOT EXISTS _metadata (
    table_name VARCHAR PRIMARY KEY,
    type VARCHAR NOT NULL,
    fetched_at TIMESTAMP NOT NULL,
    from_date DATE,
    to_date DATE,
    row_count INTEGER NOT NULL
)
```
