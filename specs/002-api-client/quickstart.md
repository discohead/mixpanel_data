# Quickstart: Mixpanel API Client

**Date**: 2025-12-20
**Feature**: 002-api-client

## Overview

The `MixpanelAPIClient` is a low-level HTTP client for Mixpanel APIs. It handles authentication, rate limiting, and response parsing. Most users won't use it directly—they'll use the `Workspace` class instead. This quickstart is for developers working on the library internals.

## Prerequisites

```bash
# Ensure you're on the feature branch
git checkout 002-api-client

# Install dependencies
uv sync --all-extras
```

## Basic Usage

### Creating a Client

```python
from mixpanel_data._internal.config import ConfigManager
from mixpanel_data._internal.api_client import MixpanelAPIClient

# Resolve credentials from config
config = ConfigManager()
credentials = config.resolve_credentials()

# Create client
client = MixpanelAPIClient(credentials)

# Use as context manager (recommended)
with MixpanelAPIClient(credentials) as client:
    events = client.get_events()
    print(events)
```

### Exporting Events

```python
from datetime import date

with MixpanelAPIClient(credentials) as client:
    # Stream events (memory efficient)
    for event in client.export_events(
        from_date="2024-01-01",
        to_date="2024-01-31"
    ):
        print(f"{event['event']}: {event['properties']['distinct_id']}")

    # With progress callback
    count = 0
    def on_batch(batch_size: int) -> None:
        nonlocal count
        count += batch_size
        print(f"Processed {count} events...")

    events = list(client.export_events(
        from_date="2024-01-01",
        to_date="2024-01-31",
        on_batch=on_batch
    ))
```

### Discovery

```python
with MixpanelAPIClient(credentials) as client:
    # List events
    events = client.get_events()
    print(f"Found {len(events)} events")

    # List properties for an event
    props = client.get_event_properties("Purchase")
    print(f"Purchase has {len(props)} properties")

    # Get sample values
    values = client.get_property_values("country", event="Purchase", limit=10)
    print(f"Countries: {values}")
```

### Live Queries

```python
with MixpanelAPIClient(credentials) as client:
    # Segmentation
    result = client.segmentation(
        event="Purchase",
        from_date="2024-01-01",
        to_date="2024-01-31",
        on='properties["country"]',
        unit="day"
    )
    print(result["data"]["values"])

    # Funnel
    result = client.funnel(
        funnel_id=12345,
        from_date="2024-01-01",
        to_date="2024-01-31"
    )
    print(f"Conversion: {result['data'][-1]['overall_conv_ratio']:.1%}")

    # JQL
    result = client.jql("""
        function main() {
            return Events({from_date: params.from, to_date: params.to})
                .groupBy(["name"], mixpanel.reducer.count());
        }
    """, params={"from": "2024-01-01", "to": "2024-01-31"})
    print(result)
```

### Error Handling

```python
from mixpanel_data.exceptions import (
    AuthenticationError,
    RateLimitError,
    QueryError,
)

try:
    with MixpanelAPIClient(credentials) as client:
        result = client.segmentation(
            event="NonExistentEvent",
            from_date="2024-01-01",
            to_date="2024-01-31"
        )
except AuthenticationError:
    print("Check your credentials")
except RateLimitError as e:
    print(f"Rate limited. Retry after {e.retry_after} seconds")
except QueryError as e:
    print(f"Query failed: {e.message}")
```

## Testing with Mock Transport

For unit tests, inject a mock transport:

```python
import httpx
from mixpanel_data._internal.api_client import MixpanelAPIClient
from mixpanel_data._internal.config import Credentials

def test_export_events():
    # Create mock credentials
    credentials = Credentials(
        username="test",
        secret="test",
        project_id="12345",
        region="us"
    )

    # Define mock response
    mock_response = b'{"event":"A","properties":{"time":1}}\n{"event":"B","properties":{"time":2}}\n'

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=mock_response)

    # Create client with mock transport
    transport = httpx.MockTransport(handler)
    with MixpanelAPIClient(credentials, _transport=transport) as client:
        events = list(client.export_events("2024-01-01", "2024-01-31"))

    assert len(events) == 2
    assert events[0]["event"] == "A"
    assert events[1]["event"] == "B"
```

## Configuration

| Parameter | Default | Description |
|-----------|---------|-------------|
| `timeout` | 120.0 | Request timeout (seconds) |
| `export_timeout` | 600.0 | Export request timeout (seconds) |
| `max_retries` | 3 | Max retries for rate limits |

```python
client = MixpanelAPIClient(
    credentials,
    timeout=60.0,
    export_timeout=600.0,
    max_retries=5
)
```

## Regional Endpoints

The client automatically routes to the correct regional endpoint based on `credentials.region`:

| Region | Query API | Export API |
|--------|-----------|------------|
| `us` | mixpanel.com/api/query | data.mixpanel.com/api/2.0 |
| `eu` | eu.mixpanel.com/api/query | data-eu.mixpanel.com/api/2.0 |
| `in` | in.mixpanel.com/api/query | data-in.mixpanel.com/api/2.0 |

## Next Steps

After implementing the API client:

1. Run tests: `pytest tests/unit/test_api_client.py -v`
2. Type check: `mypy src/mixpanel_data/_internal/api_client.py`
3. Lint: `ruff check src/mixpanel_data/_internal/api_client.py`
4. Proceed to Phase 003 (Storage Engine)
