# Quickstart: Local Introspection API

**Feature**: 014-introspection-api
**Date**: 2024-12-25

## Overview

This feature adds 5 introspection methods to the `Workspace` class for exploring local DuckDB data:

| Method | Purpose |
|--------|---------|
| `sample(table, n=10)` | Random sample rows |
| `summarize(table)` | Statistical summary of all columns |
| `event_breakdown(table)` | Event distribution analysis |
| `property_keys(table, event=None)` | JSON property key discovery |
| `column_stats(table, column)` | Deep single-column analysis |

---

## Python API Usage

### Basic Exploration Workflow

```python
from mixpanel_data import Workspace

# Open existing workspace
ws = Workspace()

# 1. See what data looks like
sample = ws.sample("events", n=5)
print(sample)

# 2. Get column statistics
summary = ws.summarize("events")
print(f"Table has {summary.row_count} rows")
for col in summary.columns:
    print(f"  {col.column_name}: {col.column_type}, {col.null_percentage}% null")

# 3. Understand event distribution
breakdown = ws.event_breakdown("events")
print(f"Total events: {breakdown.total_events}")
print(f"Unique users: {breakdown.total_users}")
for event in breakdown.events[:5]:
    print(f"  {event.event_name}: {event.count} ({event.pct_of_total}%)")

# 4. Discover JSON property keys
keys = ws.property_keys("events")
print(f"Available properties: {keys}")

# Filter to specific event
purchase_keys = ws.property_keys("events", event="Purchase")
print(f"Purchase properties: {purchase_keys}")

# 5. Deep dive into a column
stats = ws.column_stats("events", "event_name")
print(f"Unique values: {stats.unique_count}")
print(f"Top values: {stats.top_values[:3]}")

# Analyze JSON property
country_stats = ws.column_stats("events", "properties->>'$.country'")
print(f"Top countries: {country_stats.top_values}")
```

### Working with Result Types

```python
# All results support .df for DataFrame conversion
summary_df = ws.summarize("events").df
breakdown_df = ws.event_breakdown("events").df
column_df = ws.column_stats("events", "event_name").df

# All results support .to_dict() for JSON serialization
import json
print(json.dumps(ws.summarize("events").to_dict(), indent=2))
```

---

## CLI Usage

### Sample Data

```bash
# Default: 10 rows, table format
mp inspect sample -t events

# Specific count, JSON format
mp inspect sample -t events -n 5 --format json
```

### Summarize Table

```bash
# Table format
mp inspect summarize -t events

# JSON for piping to jq
mp inspect summarize -t events --format json | jq '.columns[] | select(.null_percentage > 10)'
```

### Event Breakdown

```bash
# See event distribution
mp inspect breakdown -t events

# JSON for analysis
mp inspect breakdown -t events --format json
```

### Property Keys

```bash
# All keys
mp inspect keys -t events

# Keys for specific event
mp inspect keys -t events -e "Purchase"
```

### Column Statistics

```bash
# Standard column
mp inspect column -t events -c event_name

# JSON property
mp inspect column -t events -c "properties->>'$.country'"

# Custom top count
mp inspect column -t events -c distinct_id --top 20
```

---

## Implementation Notes

### Files to Modify

1. **`src/mixpanel_data/types.py`**: Add result types
   - `ColumnSummary`
   - `SummaryResult`
   - `EventStats`
   - `EventBreakdownResult`
   - `ColumnStatsResult`

2. **`src/mixpanel_data/workspace.py`**: Add methods
   - `sample()`
   - `summarize()`
   - `event_breakdown()`
   - `property_keys()`
   - `column_stats()`

3. **`src/mixpanel_data/__init__.py`**: Export new types

4. **`src/mixpanel_data/cli/commands/inspect.py`**: Add CLI commands
   - `inspect sample`
   - `inspect summarize`
   - `inspect breakdown`
   - `inspect keys`
   - `inspect column`

### Testing

```bash
# Run unit tests
just test -k introspection

# Run all tests
just check
```

---

## Error Handling

```python
from mixpanel_data.exceptions import TableNotFoundError, QueryError

try:
    ws.sample("nonexistent")
except TableNotFoundError as e:
    print(f"Table not found: {e}")

try:
    ws.event_breakdown("users")  # Missing required columns
except QueryError as e:
    print(f"Query error: {e}")
    # Message: "event_breakdown() requires columns {...}, but users is missing: {...}"
```
