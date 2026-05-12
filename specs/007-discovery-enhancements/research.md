# Research: Discovery & Query API Enhancements

**Phase**: 0 (Research)
**Created**: 2025-12-23
**Status**: Complete

---

## Overview

This document captures research findings for extending the Discovery and Live Query services with 5 new API capabilities.

---

## API Endpoint Research

### 1. List Saved Funnels

**Endpoint**: `GET /api/query/funnels/list`

**Decision**: Use GET method with project_id parameter

**Request**:
- `project_id` (required): Project identifier

**Response Format**:
```json
[
  {"funnel_id": 7509, "name": "Signup funnel"},
  {"funnel_id": 9070, "name": "Funnel tutorial"}
]
```

**Response Fields**:
| Field | Type | Description |
|-------|------|-------------|
| funnel_id | integer | Unique funnel identifier |
| name | string | Human-readable funnel name |

**Caching**: Yes (session-scoped) — funnel definitions are stable

**Alternatives Considered**:
- None — single documented API endpoint

---

### 2. List Saved Cohorts

**Endpoint**: `POST /api/query/cohorts/list`

**Decision**: Use POST method per Mixpanel API specification (unusual but documented)

**Request**:
- `project_id` (required): Project identifier
- Method: POST (no request body)

**Response Format**:
```json
[
  {
    "id": 1000,
    "name": "Cohort One",
    "count": 150,
    "description": "This cohort is visible...",
    "created": "2019-03-19 23:49:51",
    "is_visible": 1,
    "project_id": 1
  }
]
```

**Response Fields**:
| Field | Type | Description |
|-------|------|-------------|
| id | integer | Unique cohort identifier |
| name | string | Human-readable cohort name |
| count | integer | Number of users in cohort |
| description | string | Optional description |
| created | string | Creation timestamp (YYYY-MM-DD HH:mm:ss) |
| is_visible | integer | 0=hidden, 1=visible |
| project_id | integer | Owning project ID |

**Caching**: Yes (session-scoped) — cohort definitions are stable

**Risk**: POST method is unusual for read-only operations. Verified against official OpenAPI spec.

---

### 3. Today's Top Events

**Endpoint**: `GET /api/query/events/top`

**Decision**: Use GET method, no caching (real-time data)

**Request Parameters**:
| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| project_id | integer | Yes | — | Project identifier |
| type | string | Yes | — | `general`, `unique`, or `average` |
| limit | integer | No | 100 | Maximum events to return |

**Response Format**:
```json
{
  "events": [
    {"amount": 2, "event": "funnel", "percent_change": -0.356},
    {"amount": 75, "event": "pages", "percent_change": -0.202}
  ],
  "type": "unique"
}
```

**Response Fields**:
| Field | Type | Description |
|-------|------|-------------|
| events[].amount | integer | Today's event count |
| events[].event | string | Event name |
| events[].percent_change | float | Change vs yesterday (-1.0 to +∞) |
| type | string | Counting method used |

**Caching**: No — data changes throughout day

**Transformation**: Map `amount` → `count` for consistency with other result types

---

### 4. Aggregate Event Counts (Multi-Event Time Series)

**Endpoint**: `GET /api/query/events`

**Decision**: Use GET method, map to LiveQueryService (date range required)

**Request Parameters**:
| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| project_id | integer | Yes | — | Project identifier |
| event | string | Yes | — | JSON array of event names |
| type | string | Yes | — | `general`, `unique`, or `average` |
| unit | string | Yes | — | `day`, `week`, or `month` |
| from_date | string | Yes | — | Start date (YYYY-MM-DD) |
| to_date | string | Yes | — | End date (YYYY-MM-DD) |

**Response Format**:
```json
{
  "data": {
    "series": ["2010-05-29", "2010-05-30", "2010-05-31"],
    "values": {
      "account-page": {"2010-05-30": 1},
      "splash features": {"2010-05-29": 6, "2010-05-30": 4, "2010-05-31": 5}
    }
  },
  "legend_size": 2
}
```

**Response Fields**:
| Field | Type | Description |
|-------|------|-------------|
| data.series | string[] | All dates in response |
| data.values | object | {event_name: {date: count}} |
| legend_size | integer | Number of events |

**Caching**: No — live query data

**Transformation**: Extract `data.values` → `series` in result type

---

### 5. Aggregated Event Property Values (Property Distribution Time Series)

**Endpoint**: `GET /api/query/events/properties`

**Decision**: Use GET method, map to LiveQueryService (date range required)

**Request Parameters**:
| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| project_id | integer | Yes | — | Project identifier |
| event | string | Yes | — | Single event name |
| name | string | Yes | — | Property name |
| values | string | No | — | JSON array of specific values to include |
| type | string | Yes | — | `general`, `unique`, or `average` |
| unit | string | Yes | — | `day`, `week`, or `month` |
| from_date | string | Yes | — | Start date (YYYY-MM-DD) |
| to_date | string | Yes | — | End date (YYYY-MM-DD) |
| limit | integer | No | 255 | Maximum property values |

**Response Format**:
```json
{
  "data": {
    "series": ["2010-05-29", "2010-05-30", "2010-05-31"],
    "values": {
      "splash features": {"2010-05-29": 6, "2010-05-30": 4, "2010-05-31": 5}
    }
  },
  "legend_size": 2
}
```

**Response Fields**:
| Field | Type | Description |
|-------|------|-------------|
| data.series | string[] | All dates in response |
| data.values | object | {property_value: {date: count}} |
| legend_size | integer | Number of property values |

**Caching**: No — live query data

**Transformation**: Extract `data.values` → `series` in result type

---

## Service Placement Decision

| API | Service | Rationale |
|-----|---------|-----------|
| Funnels List | DiscoveryService | Resource introspection, no date range, cacheable |
| Cohorts List | DiscoveryService | Resource introspection, no date range, cacheable |
| Top Events | DiscoveryService | Introspection-like, no date range, but NOT cached (real-time) |
| Event Counts | LiveQueryService | Analytics query, requires date range, time-series result |
| Property Counts | LiveQueryService | Analytics query, requires date range, time-series result |

**Decision**: Discovery operations do NOT require date ranges and discover project resources. Live queries require date ranges and return time-series data.

---

## Type Design Decisions

### Frozen Dataclasses

All new types follow existing patterns:
- `@dataclass(frozen=True)` for immutability
- `_df_cache` field for lazy DataFrame conversion
- `to_dict()` method for JSON serialization
- `df` property using `object.__setattr__` for cache update

### Field Naming

| API Field | Type Field | Reason |
|-----------|------------|--------|
| funnel_id | funnel_id | Match API exactly |
| is_visible | is_visible | Keep as bool (convert from int 0/1) |
| amount | count | Consistency with other types |
| percent_change | percent_change | Match API exactly |
| data.values | series | Cleaner name for time-series data |

---

## Cache Type Broadening

**Current Cache Type**: `dict[tuple[str | int | None, ...], list[str]]`

**Issue**: New types return structured objects (`FunnelInfo`, `SavedCohort`), not strings.

**Decision**: Broaden cache type to `dict[tuple[str | int | None, ...], list[Any]]`

**Rationale**: All cached values are lists; the element type varies by method. Type safety maintained at method level.

---

## Error Handling

All new methods follow existing patterns:
- `AuthenticationError` for 401/403 responses
- `RateLimitError` for 429 responses (with retry)
- Empty lists for no results (not errors)

---

## Best Practices Applied

1. **Consistent Result Types**: All time-series results have same structure (series dict + lazy df)
2. **Alphabetical Sorting**: All discovery list results sorted by name
3. **Explicit Caching**: Document which methods cache vs. always fetch
4. **Type Safety**: Frozen dataclasses with full type hints
5. **Lazy DataFrame**: Only convert to DataFrame when `.df` accessed

---

*Research complete. Ready for Phase 1: Data Model and Contracts.*
