# Quickstart: Fetch Service

**Feature**: 005-fetch-service
**Date**: 2025-12-22

## Overview

The FetcherService enables fetching Mixpanel data into local DuckDB storage for offline analysis. This quickstart covers common usage patterns.

---

## Basic Setup

```python
from mixpanel_data._internal.config import ConfigManager
from mixpanel_data._internal.api_client import MixpanelAPIClient
from mixpanel_data._internal.storage import StorageEngine
from mixpanel_data._internal.services.fetcher import FetcherService
from pathlib import Path

# Resolve credentials
config = ConfigManager()
credentials = config.resolve_credentials()

# Initialize components
api_client = MixpanelAPIClient(credentials)
storage = StorageEngine(Path("~/mixpanel_data.db").expanduser())

# Create fetcher service
fetcher = FetcherService(api_client, storage)
```

---

## Fetch Events

### Basic Fetch

```python
result = fetcher.fetch_events(
    name="events",
    from_date="2024-01-01",
    to_date="2024-01-31",
)

print(f"Table: {result.table}")
print(f"Rows: {result.rows}")
print(f"Duration: {result.duration_seconds:.1f}s")
print(f"Date range: {result.date_range}")
```

### With Event Filter

```python
result = fetcher.fetch_events(
    name="signups",
    from_date="2024-01-01",
    to_date="2024-01-31",
    events=["Sign Up", "Registration Complete"],
)
```

### With Where Expression

```python
result = fetcher.fetch_events(
    name="large_purchases",
    from_date="2024-01-01",
    to_date="2024-01-31",
    events=["Purchase"],
    where='properties["amount"] > 1000',
)
```

---

## Fetch Profiles

### All Profiles

```python
result = fetcher.fetch_profiles(name="profiles")

print(f"Fetched {result.rows} profiles")
# Note: result.date_range is None for profiles
```

### Filtered Profiles

```python
result = fetcher.fetch_profiles(
    name="premium_users",
    where='user["plan"] == "premium"',
)
```

---

## Progress Monitoring

```python
import sys

def show_progress(count: int) -> None:
    print(f"\rFetched {count:,} events...", end="", file=sys.stderr)

result = fetcher.fetch_events(
    name="events",
    from_date="2024-01-01",
    to_date="2024-01-31",
    progress_callback=show_progress,
)

print(f"\nComplete: {result.rows:,} events", file=sys.stderr)
```

---

## Query Fetched Data

```python
# After fetching, query with SQL
df = storage.execute_df("""
    SELECT
        event_name,
        COUNT(*) as count
    FROM events
    GROUP BY event_name
    ORDER BY count DESC
""")

print(df)
```

### Extract JSON Properties

```python
df = storage.execute_df("""
    SELECT
        properties->>'$.browser' as browser,
        COUNT(*) as count
    FROM events
    WHERE event_name = 'Page View'
    GROUP BY browser
""")
```

---

## Error Handling

### Table Already Exists

```python
from mixpanel_data.exceptions import TableExistsError

try:
    result = fetcher.fetch_events(
        name="events",
        from_date="2024-01-01",
        to_date="2024-01-31",
    )
except TableExistsError:
    # Option 1: Drop and refetch
    storage.drop_table("events")
    result = fetcher.fetch_events(...)

    # Option 2: Use a different table name
    result = fetcher.fetch_events(
        name="events_v2",
        from_date="2024-01-01",
        to_date="2024-01-31",
    )
```

### Authentication Error

```python
from mixpanel_data.exceptions import AuthenticationError

try:
    result = fetcher.fetch_events(...)
except AuthenticationError as e:
    print(f"Auth failed: {e.message}")
    # Check ~/.mp/config.toml or environment variables
```

### Rate Limit

```python
from mixpanel_data.exceptions import RateLimitError
import time

try:
    result = fetcher.fetch_events(...)
except RateLimitError as e:
    wait_time = e.retry_after or 60
    print(f"Rate limited. Waiting {wait_time}s...")
    time.sleep(wait_time)
    # Retry
```

---

## Cleanup

```python
# Close connections when done
api_client.close()
storage.close()
```

### Using Context Managers

```python
with MixpanelAPIClient(credentials) as api_client:
    with StorageEngine(Path("data.db")) as storage:
        fetcher = FetcherService(api_client, storage)
        result = fetcher.fetch_events(
            name="events",
            from_date="2024-01-01",
            to_date="2024-01-31",
        )
# Connections automatically closed
```

---

## Full Example

```python
#!/usr/bin/env python3
"""Fetch last month's events and summarize."""

import sys
from datetime import datetime, timedelta
from pathlib import Path

from mixpanel_data._internal.config import ConfigManager
from mixpanel_data._internal.api_client import MixpanelAPIClient
from mixpanel_data._internal.storage import StorageEngine
from mixpanel_data._internal.services.fetcher import FetcherService
from mixpanel_data.exceptions import TableExistsError


def main():
    # Calculate date range (last 30 days)
    today = datetime.now()
    from_date = (today - timedelta(days=30)).strftime("%Y-%m-%d")
    to_date = today.strftime("%Y-%m-%d")

    # Setup
    config = ConfigManager()
    credentials = config.resolve_credentials()

    with MixpanelAPIClient(credentials) as api_client:
        with StorageEngine(Path("analysis.db")) as storage:
            fetcher = FetcherService(api_client, storage)

            # Progress callback
            def on_progress(count: int) -> None:
                print(f"\rFetching: {count:,} events", end="", file=sys.stderr)

            # Fetch events
            try:
                result = fetcher.fetch_events(
                    name="recent_events",
                    from_date=from_date,
                    to_date=to_date,
                    progress_callback=on_progress,
                )
            except TableExistsError:
                storage.drop_table("recent_events")
                result = fetcher.fetch_events(
                    name="recent_events",
                    from_date=from_date,
                    to_date=to_date,
                    progress_callback=on_progress,
                )

            print(f"\n\nFetched {result.rows:,} events in {result.duration_seconds:.1f}s")

            # Analyze
            summary = storage.execute_df("""
                SELECT
                    event_name,
                    COUNT(*) as count,
                    COUNT(DISTINCT distinct_id) as unique_users
                FROM recent_events
                GROUP BY event_name
                ORDER BY count DESC
                LIMIT 10
            """)

            print("\nTop 10 Events:")
            print(summary.to_string(index=False))


if __name__ == "__main__":
    main()
```

---

## Next Steps

- **Workspace facade**: The Workspace class will wrap FetcherService for simpler usage
- **CLI commands**: `mp fetch events` will expose this functionality via command line
- **Live queries**: For quick analysis, use LiveQueryService instead of fetching
