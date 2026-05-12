# Data Model: Discovery Service

**Date**: 2025-12-21
**Feature**: 004-discovery-service

## Overview

The Discovery Service is primarily a read-only service that returns data from Mixpanel's API. It introduces minimal new data structures—mainly the cache layer for storing results.

## Entities

### Core Entities (from Mixpanel)

These entities are returned by the service but not owned by it:

#### Event Name
- **Type**: String
- **Description**: Name of a tracked event in Mixpanel (e.g., "Sign Up", "Purchase")
- **Constraints**: Non-empty string; max 255 characters (Mixpanel limit)
- **Source**: Mixpanel Query API `/events/names`

#### Property Name
- **Type**: String
- **Description**: Name of a property associated with an event (e.g., "country", "plan_type")
- **Constraints**: Non-empty string; max 255 characters
- **Source**: Mixpanel Query API `/events/properties/top`

#### Property Value
- **Type**: String
- **Description**: Sample value for a property (e.g., "US", "premium")
- **Constraints**: Converted to string; may be empty
- **Source**: Mixpanel Query API `/events/properties/values`

### Service Entities (internal)

#### Discovery Cache

**Purpose**: Store discovery results to avoid redundant API calls within a session.

| Field | Type | Description |
|-------|------|-------------|
| key | tuple | Composite key: (method_name, *args) |
| value | list[str] | Cached result (sorted list) |

**Lifecycle**:
- Created: When first discovery request for a key is made
- Updated: Never (immutable once cached)
- Deleted: On `clear_cache()` or service instance destruction

**Cache Key Examples**:

| Method Call | Cache Key |
|-------------|-----------|
| `list_events()` | `("list_events",)` |
| `list_properties("Sign Up")` | `("list_properties", "Sign Up")` |
| `list_property_values("country", event="Sign Up", limit=100)` | `("list_property_values", "country", "Sign Up", 100)` |

## Relationships

```
DiscoveryService
    │
    ├── owns → Cache (dict[tuple, list[str]])
    │
    └── uses → MixpanelAPIClient
                    │
                    └── calls → Mixpanel API
                                    │
                                    └── returns → Events, Properties, Values
```

## State Transitions

### Cache State Machine

```
┌─────────────┐
│    EMPTY    │ ← Initial state / After clear_cache()
└─────────────┘
       │
       │ First request for key K
       ▼
┌─────────────┐
│   MISS      │ → Call API, store result
└─────────────┘
       │
       │ Result cached
       ▼
┌─────────────┐
│   HIT       │ → Return cached result (no API call)
└─────────────┘
       │
       │ clear_cache()
       ▼
┌─────────────┐
│    EMPTY    │
└─────────────┘
```

## Validation Rules

| Entity | Rule | Error |
|--------|------|-------|
| Event Name (input) | Must be non-empty string | `QueryError` from API client |
| Property Name (input) | Must be non-empty string | `QueryError` from API client |
| Limit (input) | Must be positive integer | ValueError (Python) |

## Notes

- No database storage—all data is transient (in-memory cache)
- No persistence across sessions
- All returned lists are sorted alphabetically at the service layer
- Original API response order is not preserved
