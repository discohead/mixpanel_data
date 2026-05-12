# Data Model: Mixpanel API Client

**Date**: 2025-12-20
**Feature**: 002-api-client

## Overview

The API Client is a stateless HTTP layer. It doesn't persist data—it transforms Mixpanel API responses into Python data structures. The "data model" here describes the shape of data flowing through the client.

## Entities

### 1. MixpanelAPIClient

The client itself is the primary entity. It holds connection state but no application data.

| Attribute | Type | Description |
|-----------|------|-------------|
| credentials | Credentials | Immutable auth data (from Phase 001) |
| timeout | float | Request timeout in seconds |
| max_retries | int | Maximum retry attempts for rate limits |
| _client | httpx.Client | Internal HTTP client with connection pooling |

**State Transitions**:
- `Created` → `Open` (on first request or context entry)
- `Open` → `Closed` (on close() or context exit)
- Once `Closed`, cannot be reopened

**Validation Rules**:
- credentials: Must be valid Credentials instance
- timeout: Must be positive number
- max_retries: Must be non-negative integer

---

### 2. Export Event (Output)

Raw event data from Export API. Caller receives as Python dict.

| Field | Type | Description |
|-------|------|-------------|
| event | string | Event name |
| properties | object | Event properties including: |
| properties.time | integer | Unix timestamp (seconds) |
| properties.distinct_id | string | User identifier |
| properties.$insert_id | string | Unique event identifier |
| properties.mp_processing_time_ms | integer | Server processing time |
| properties.* | any | Custom event properties |

**Example**:
```json
{
    "event": "Purchase",
    "properties": {
        "time": 1704067200,
        "distinct_id": "user_123",
        "$insert_id": "abc123",
        "amount": 99.99,
        "currency": "USD"
    }
}
```

---

### 3. Profile (Output)

User profile data from Engage API. Caller receives as Python dict.

| Field | Type | Description |
|-------|------|-------------|
| $distinct_id | string | User identifier |
| $properties | object | Profile properties |
| $properties.$last_seen | string | ISO timestamp of last activity |
| $properties.$name | string | Display name (optional) |
| $properties.$email | string | Email (optional) |
| $properties.* | any | Custom profile properties |

**Example**:
```json
{
    "$distinct_id": "user_123",
    "$properties": {
        "$last_seen": "2024-01-15T10:30:00",
        "$name": "Jane Doe",
        "plan": "premium",
        "signup_date": "2023-06-01"
    }
}
```

---

### 4. Query Responses (Output)

#### 4.1 Segmentation Response

| Field | Type | Description |
|-------|------|-------------|
| legend_size | integer | Number of segments |
| data.series | object | Time series by segment |
| data.values | object | Values by segment and date |

#### 4.2 Funnel Response

| Field | Type | Description |
|-------|------|-------------|
| meta.dates | object | Date range |
| data | array | Step-by-step conversion data |
| data[].count | integer | Users at step |
| data[].step_conv_ratio | float | Conversion from previous |
| data[].overall_conv_ratio | float | Conversion from first |

#### 4.3 Retention Response

| Field | Type | Description |
|-------|------|-------------|
| data | object | Cohort retention data |
| data.{date}.counts | array | Retention counts by period |
| data.{date}.first | integer | Cohort size |

#### 4.4 JQL Response

| Type | Description |
|------|-------------|
| list | Array of results from JQL script |

---

### 5. Discovery Responses (Output)

#### 5.1 Event Names

| Type | Description |
|------|-------------|
| list[string] | Array of event names |

#### 5.2 Event Properties

| Type | Description |
|------|-------------|
| list[string] | Array of property names for an event |

#### 5.3 Property Values

| Type | Description |
|------|-------------|
| list[string] | Sample values for a property |

---

## Data Flow

```
┌──────────────────────────────────────────────────────────────────┐
│                         Callers                                   │
│  (FetcherService, LiveQueryService, DiscoveryService, Workspace) │
└─────────────────────────────┬────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────────┐
│                    MixpanelAPIClient                              │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │ Input: Credentials, method params                          │  │
│  │ Output: Iterator[dict] for exports                         │  │
│  │         dict for queries                                   │  │
│  │         list[str] for discovery                            │  │
│  └────────────────────────────────────────────────────────────┘  │
└─────────────────────────────┬────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────────┐
│                     Mixpanel APIs                                 │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐   │
│  │ Export API   │  │ Query API    │  │ Events/Discovery API │   │
│  │ (JSONL)      │  │ (JSON)       │  │ (JSON)               │   │
│  └──────────────┘  └──────────────┘  └──────────────────────┘   │
└──────────────────────────────────────────────────────────────────┘
```

## Relationships

```
Credentials (Phase 001)
    │
    └──► MixpanelAPIClient (this phase)
              │
              ├──► Iterator[ExportEvent]
              ├──► Iterator[Profile]
              ├──► SegmentationResponse
              ├──► FunnelResponse
              ├──► RetentionResponse
              ├──► JQLResponse
              └──► list[str] (discovery)
```

## Notes

- All output types are raw Python dicts/lists, not Pydantic models
- Response transformation to result types (FetchResult, SegmentationResult, etc.) happens in service layer, not client
- The client is intentionally thin—it's HTTP + parsing, nothing more
