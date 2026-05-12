# Quickstart: Discovery Service

**Feature**: 004-discovery-service
**Date**: 2025-12-21

## Overview

The Discovery Service lets you explore Mixpanel schema before querying data. Discover what events exist, what properties they have, and sample values—all with automatic caching.

## Basic Usage

### Setup

```python
from mixpanel_data._internal.config import ConfigManager
from mixpanel_data._internal.api_client import MixpanelAPIClient
from mixpanel_data._internal.services.discovery import DiscoveryService

# Get credentials
config = ConfigManager()
credentials = config.resolve_credentials()

# Create services
with MixpanelAPIClient(credentials) as client:
    discovery = DiscoveryService(client)

    # Now use discovery methods...
```

### List All Events

```python
events = discovery.list_events()
print(f"Found {len(events)} events")
for event in events[:10]:
    print(f"  - {event}")
```

Output:
```
Found 47 events
  - Add to Cart
  - Checkout Complete
  - Login
  - Page View
  - ...
```

### List Properties for an Event

```python
properties = discovery.list_properties("Purchase")
print(f"Purchase event has {len(properties)} properties:")
for prop in properties:
    print(f"  - {prop}")
```

Output:
```
Purchase event has 12 properties:
  - amount
  - currency
  - item_count
  - payment_method
  - ...
```

### Get Sample Property Values

```python
# Get sample values for a property
countries = discovery.list_property_values("country")
print(f"Countries: {countries[:5]}")

# Scope to a specific event
payment_methods = discovery.list_property_values(
    "payment_method",
    event="Purchase",
    limit=10
)
print(f"Payment methods: {payment_methods}")
```

Output:
```
Countries: ['AU', 'CA', 'DE', 'FR', 'GB']
Payment methods: ['apple_pay', 'credit_card', 'paypal']
```

## Caching Behavior

Results are cached automatically for the session:

```python
# First call: hits Mixpanel API
events1 = discovery.list_events()  # ~1-2 seconds

# Second call: returns cached result instantly
events2 = discovery.list_events()  # <1 millisecond

# Same for properties
props1 = discovery.list_properties("Purchase")  # API call
props2 = discovery.list_properties("Purchase")  # Cached

# Different event = different cache entry
props3 = discovery.list_properties("Sign Up")  # API call
```

### Clearing the Cache

If your Mixpanel schema changes mid-session:

```python
# Clear all cached results
discovery.clear_cache()

# Next call fetches fresh data
events = discovery.list_events()  # API call
```

## Error Handling

```python
from mixpanel_data.exceptions import (
    AuthenticationError,
    QueryError,
    RateLimitError,
)

try:
    events = discovery.list_events()
except AuthenticationError:
    print("Invalid credentials. Check your service account.")
except RateLimitError as e:
    print(f"Rate limited. Retry after {e.details.get('retry_after')} seconds")

try:
    props = discovery.list_properties("NonExistentEvent")
except QueryError as e:
    print(f"Event not found: {e.message}")
```

## Common Patterns

### Build a Schema Overview

```python
def get_schema_overview(discovery: DiscoveryService) -> dict:
    """Get a complete schema overview of the project."""
    events = discovery.list_events()
    schema = {}

    for event in events:
        properties = discovery.list_properties(event)
        schema[event] = {
            "property_count": len(properties),
            "properties": properties,
        }

    return schema

overview = get_schema_overview(discovery)
print(f"Total events: {len(overview)}")
print(f"Total properties: {sum(e['property_count'] for e in overview.values())}")
```

### Find Events with a Specific Property

```python
def find_events_with_property(
    discovery: DiscoveryService,
    property_name: str
) -> list[str]:
    """Find all events that have a specific property."""
    events = discovery.list_events()
    matching = []

    for event in events:
        properties = discovery.list_properties(event)
        if property_name in properties:
            matching.append(event)

    return matching

# Find all events with "user_id" property
events = find_events_with_property(discovery, "user_id")
print(f"Events with user_id: {events}")
```

## Integration with Workspace (Future)

Once Workspace is implemented (Phase 007), usage will be simpler:

```python
from mixpanel_data import Workspace

ws = Workspace()
events = ws.events()           # Calls DiscoveryService.list_events()
props = ws.properties("Login") # Calls DiscoveryService.list_properties()
```

## Performance Notes

| Operation | Uncached | Cached |
|-----------|----------|--------|
| list_events() | 1-3 seconds | <1ms |
| list_properties(event) | 0.5-2 seconds | <1ms |
| list_property_values(...) | 0.5-2 seconds | <1ms |

- Cache is in-memory only; cleared when service instance is garbage collected
- No TTL—cache persists for entire session
- First request per unique parameters hits the API
