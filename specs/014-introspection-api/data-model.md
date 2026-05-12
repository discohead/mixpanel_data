# Data Model: Local Introspection API

**Feature**: 014-introspection-api
**Date**: 2024-12-25

## Overview

This feature introduces 5 new result types that follow the established frozen dataclass pattern. All types are immutable, support lazy DataFrame conversion via `.df` property, and provide JSON serialization via `to_dict()`.

---

## Result Types

### 1. ColumnSummary

Statistical summary of a single column from DuckDB's SUMMARIZE command.

| Field | Type | Description |
|-------|------|-------------|
| `column_name` | `str` | Name of the column |
| `column_type` | `str` | DuckDB data type (VARCHAR, TIMESTAMP, INTEGER, JSON, etc.) |
| `min` | `Any` | Minimum value (type varies by column type) |
| `max` | `Any` | Maximum value (type varies by column type) |
| `approx_unique` | `int` | Approximate count of distinct values (HyperLogLog) |
| `avg` | `float \| None` | Mean value (None for non-numeric columns) |
| `std` | `float \| None` | Standard deviation (None for non-numeric columns) |
| `q25` | `Any` | 25th percentile value (None for non-numeric) |
| `q50` | `Any` | Median / 50th percentile (None for non-numeric) |
| `q75` | `Any` | 75th percentile value (None for non-numeric) |
| `count` | `int` | Number of non-null values |
| `null_percentage` | `float` | Percentage of null values (0.0 to 100.0) |

**Methods**:
- `to_dict() -> dict[str, Any]`: Serialize for JSON output

---

### 2. SummaryResult

Statistical summary of all columns in a table.

| Field | Type | Description |
|-------|------|-------------|
| `table` | `str` | Name of the summarized table |
| `row_count` | `int` | Total number of rows in the table |
| `columns` | `list[ColumnSummary]` | Per-column statistics |

**Properties**:
- `df -> pd.DataFrame`: One row per column with all statistics

**Methods**:
- `to_dict() -> dict[str, Any]`: Serialize for JSON output

---

### 3. EventStats

Statistics for a single event type.

| Field | Type | Description |
|-------|------|-------------|
| `event_name` | `str` | Name of the event |
| `count` | `int` | Total occurrences of this event |
| `unique_users` | `int` | Count of distinct users who triggered this event |
| `first_seen` | `datetime` | Earliest occurrence timestamp |
| `last_seen` | `datetime` | Latest occurrence timestamp |
| `pct_of_total` | `float` | Percentage of all events (0.0 to 100.0) |

**Methods**:
- `to_dict() -> dict[str, Any]`: Serialize for JSON output (datetimes as ISO strings)

---

### 4. EventBreakdownResult

Distribution of events in a table.

| Field | Type | Description |
|-------|------|-------------|
| `table` | `str` | Name of the analyzed table |
| `total_events` | `int` | Total number of events in the table |
| `total_users` | `int` | Total distinct users across all events |
| `date_range` | `tuple[datetime, datetime]` | (earliest, latest) event timestamps |
| `events` | `list[EventStats]` | Per-event statistics, ordered by count descending |

**Properties**:
- `df -> pd.DataFrame`: One row per event type

**Methods**:
- `to_dict() -> dict[str, Any]`: Serialize for JSON output

---

### 5. ColumnStatsResult

Deep statistical analysis of a single column.

| Field | Type | Description |
|-------|------|-------------|
| `table` | `str` | Name of the source table |
| `column` | `str` | Column expression analyzed (may include JSON path) |
| `dtype` | `str` | DuckDB data type of the column |
| `count` | `int` | Number of non-null values |
| `null_count` | `int` | Number of null values |
| `null_pct` | `float` | Percentage of null values (0.0 to 100.0) |
| `unique_count` | `int` | Approximate count of distinct values |
| `unique_pct` | `float` | Percentage of values that are unique (0.0 to 100.0) |
| `top_values` | `list[tuple[Any, int]]` | Most frequent (value, count) pairs |
| `min` | `float \| None` | Minimum value (None for non-numeric) |
| `max` | `float \| None` | Maximum value (None for non-numeric) |
| `mean` | `float \| None` | Mean value (None for non-numeric) |
| `std` | `float \| None` | Standard deviation (None for non-numeric) |

**Properties**:
- `df -> pd.DataFrame`: Top values as DataFrame with columns `value`, `count`

**Methods**:
- `to_dict() -> dict[str, Any]`: Serialize for JSON output

---

## Type Relationships

```
SummaryResult
    └── columns: list[ColumnSummary]

EventBreakdownResult
    └── events: list[EventStats]

ColumnStatsResult
    └── top_values: list[tuple[Any, int]]  (inline, not separate type)
```

---

## Validation Rules

### ColumnSummary
- `column_name`: Non-empty string
- `approx_unique`: Non-negative integer
- `count`: Non-negative integer
- `null_percentage`: Float between 0.0 and 100.0

### SummaryResult
- `row_count`: Non-negative integer
- `columns`: May be empty for empty tables

### EventStats
- `count`: Positive integer (at least 1)
- `unique_users`: Positive integer (at least 1)
- `first_seen` <= `last_seen`
- `pct_of_total`: Float between 0.0 and 100.0

### EventBreakdownResult
- `total_events`: Non-negative integer
- `total_users`: Non-negative integer
- `date_range[0]` <= `date_range[1]`
- Sum of `events[*].pct_of_total` ≈ 100.0

### ColumnStatsResult
- `count` + `null_count` = total rows
- `null_pct` between 0.0 and 100.0
- `unique_pct` between 0.0 and 100.0
- `top_values` ordered by count descending
- `len(top_values)` <= requested `top_n`

---

## Edge Cases

| Scenario | Behavior |
|----------|----------|
| Empty table | `SummaryResult` with `row_count=0`, empty `columns` |
| All nulls in column | `ColumnStatsResult` with `count=0`, `null_pct=100.0` |
| Single row table | All methods work normally |
| No events of type | `EventBreakdownResult` with empty `events` list |
| JSON with nested objects | `property_keys()` returns only top-level keys |
