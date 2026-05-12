# Quickstart: Bookmarks API

**Feature**: 015-bookmarks-api

## Overview

The Bookmarks API lets you discover and query saved Mixpanel reports programmatically.

## Prerequisites

```bash
# Configure credentials (one-time)
mp auth login
```

## Python Library Usage

### List All Saved Reports

```python
import mixpanel_data as mp

ws = mp.Workspace()

# List all bookmarks
bookmarks = ws.list_bookmarks()
for bm in bookmarks:
    print(f"{bm.id}: {bm.name} ({bm.type})")

# Filter by type
insights = ws.list_bookmarks(bookmark_type="insights")
retention = ws.list_bookmarks(bookmark_type="retention")
funnels = ws.list_bookmarks(bookmark_type="funnels")
flows = ws.list_bookmarks(bookmark_type="flows")
```

### Query a Saved Report

```python
# Find a specific report
bookmarks = ws.list_bookmarks(bookmark_type="retention")
for bm in bookmarks:
    if "onboarding" in bm.name.lower():
        print(f"Found: {bm.id} - {bm.name}")

# Query by bookmark ID
result = ws.query_saved_report(bookmark_id=12345678)

# Check report type
print(f"Report type: {result.report_type}")  # 'insights', 'retention', or 'funnel'
print(f"Computed at: {result.computed_at}")
print(f"Date range: {result.from_date} to {result.to_date}")

# Access the data
print(result.series)

# Convert to DataFrame
df = result.df
print(df.head())
```

### Query Flows Reports

```python
# Find flows bookmarks
flows = ws.list_bookmarks(bookmark_type="flows")
for f in flows:
    print(f"{f.id}: {f.name}")

# Query a flows report
result = ws.query_flows(bookmark_id=63880055)

print(f"Overall conversion: {result.overall_conversion_rate:.1%}")
for step in result.steps:
    print(step)

# Convert to DataFrame
df = result.df
```

### Working with Different Report Types

```python
result = ws.query_saved_report(bookmark_id=12345678)

if result.report_type == "insights":
    # Standard time-series data
    for event_name, date_counts in result.series.items():
        for date, count in date_counts.items():
            print(f"{event_name} on {date}: {count}")

elif result.report_type == "retention":
    # Cohort retention data
    for metric, cohorts in result.series.items():
        for date, segments in cohorts.items():
            overall = segments.get("$overall", {})
            print(f"{date}: {overall.get('first', 0)} users, "
                  f"rates={overall.get('rates', [])[:3]}")

elif result.report_type == "funnel":
    # Funnel conversion data
    counts = result.series.get("count", {})
    ratios = result.series.get("overall_conv_ratio", {})
    for step, data in counts.items():
        ratio = ratios.get(step, {}).get("all", 0)
        print(f"{step}: {data.get('all', 0)} users ({ratio:.1%})")
```

## CLI Usage

### List Bookmarks

```bash
# List all saved reports
mp inspect bookmarks

# Filter by type
mp inspect bookmarks --type insights
mp inspect bookmarks --type retention
mp inspect bookmarks --type funnels
mp inspect bookmarks --type flows

# Output as table
mp inspect bookmarks --format table

# JSON output (default)
mp inspect bookmarks --format json
```

### Query Saved Reports

```bash
# Query by bookmark ID
mp query saved-report 12345678

# Table output
mp query saved-report 12345678 --format table

# Pipe to jq for processing
mp query saved-report 12345678 | jq '.series'
```

### Query Flows Reports

```bash
# Query a flows report
mp query flows 63880055

# JSON output
mp query flows 63880055 --format json
```

## Common Patterns

### Find Reports by Name

```python
ws = mp.Workspace()

# Search for reports containing a keyword
keyword = "revenue"
matching = [
    bm for bm in ws.list_bookmarks()
    if keyword.lower() in bm.name.lower()
]

for bm in matching:
    print(f"{bm.type}: {bm.name} (ID: {bm.id})")
```

### Get All Report Data for a Dashboard

```python
# Find all reports on a specific dashboard
dashboard_id = 12345
bookmarks = ws.list_bookmarks()
dashboard_reports = [bm for bm in bookmarks if bm.dashboard_id == dashboard_id]

# Query each report
for bm in dashboard_reports:
    if bm.type == "flows":
        result = ws.query_flows(bm.id)
    else:
        result = ws.query_saved_report(bm.id)
    print(f"{bm.name}: {len(result.series)} metrics")
```

### Export Bookmark List to CSV

```bash
mp inspect bookmarks --format json | \
  jq -r '.[] | [.id, .name, .type, .created] | @csv' > bookmarks.csv
```

## Error Handling

```python
from mixpanel_data.exceptions import AuthenticationError, QueryError

try:
    result = ws.query_saved_report(bookmark_id=99999999)
except AuthenticationError:
    print("Check your credentials")
except QueryError as e:
    print(f"Query failed: {e}")
```

## Type Reference

```python
from mixpanel_data import (
    BookmarkInfo,      # Bookmark metadata
    SavedReportResult, # Query result for insights/retention/funnel
    FlowsResult,       # Query result for flows
)
```
