# Data Model: Streaming API

**Feature**: 011-streaming-api
**Date**: 2024-12-24

## Overview

The streaming API feature introduces no new persistent data models. It exposes existing data structures (events, profiles) through a streaming interface without storage.

## Entities

### Streamed Event (Normalized Format)

When `raw=False` (default), events are yielded with this structure:

| Field | Type | Description |
|-------|------|-------------|
| `event_name` | `str` | Name of the event (e.g., "PageView", "Purchase") |
| `event_time` | `datetime` | UTC timestamp when event occurred |
| `distinct_id` | `str` | User identifier |
| `insert_id` | `str` | Unique event identifier (UUID if not provided by Mixpanel) |
| `properties` | `dict[str, Any]` | Remaining event properties (excluding extracted fields) |

**Example**:
```json
{
  "event_name": "Purchase",
  "event_time": "2024-01-15T14:30:00+00:00",
  "distinct_id": "user_abc123",
  "insert_id": "evt_xyz789",
  "properties": {
    "amount": 99.99,
    "product": "Pro Plan",
    "currency": "USD"
  }
}
```

### Streamed Event (Raw Format)

When `raw=True`, events are yielded in Mixpanel's native API format:

| Field | Type | Description |
|-------|------|-------------|
| `event` | `str` | Name of the event |
| `properties` | `dict[str, Any]` | All properties including `distinct_id`, `time`, `$insert_id` |

**Example**:
```json
{
  "event": "Purchase",
  "properties": {
    "distinct_id": "user_abc123",
    "time": 1705328400,
    "$insert_id": "evt_xyz789",
    "amount": 99.99,
    "product": "Pro Plan",
    "currency": "USD"
  }
}
```

### Streamed Profile (Normalized Format)

When `raw=False` (default), profiles are yielded with this structure:

| Field | Type | Description |
|-------|------|-------------|
| `distinct_id` | `str` | User identifier |
| `last_seen` | `str \| None` | ISO timestamp of last activity |
| `properties` | `dict[str, Any]` | User profile properties (excluding `$last_seen`) |

**Example**:
```json
{
  "distinct_id": "user_abc123",
  "last_seen": "2024-01-15T14:30:00",
  "properties": {
    "name": "Alice Smith",
    "email": "alice@example.com",
    "plan": "pro"
  }
}
```

### Streamed Profile (Raw Format)

When `raw=True`, profiles are yielded in Mixpanel's native API format:

| Field | Type | Description |
|-------|------|-------------|
| `$distinct_id` | `str` | User identifier (with $ prefix) |
| `$properties` | `dict[str, Any]` | All properties including `$last_seen` |

**Example**:
```json
{
  "$distinct_id": "user_abc123",
  "$properties": {
    "$last_seen": "2024-01-15T14:30:00",
    "name": "Alice Smith",
    "email": "alice@example.com",
    "plan": "pro"
  }
}
```

## Data Flow

```
┌─────────────────────┐
│  Mixpanel API       │
│  (JSONL stream)     │
└──────────┬──────────┘
           │ Iterator[dict]
           ▼
┌─────────────────────┐
│  MixpanelAPIClient  │
│  export_events()    │
│  export_profiles()  │
└──────────┬──────────┘
           │ Iterator[dict] (raw format)
           ▼
┌─────────────────────┐     raw=True
│  Workspace          │ ─────────────────► yield as-is
│  stream_events()    │
│  stream_profiles()  │     raw=False
└──────────┬──────────┘ ─────────────────► _transform_*()
           │                                     │
           │ Iterator[dict]                      │
           ▼                                     ▼
┌─────────────────────┐              ┌─────────────────────┐
│  Consumer           │              │  Normalized dict    │
│  (ETL, CLI, etc.)   │              │  (datetime objects) │
└─────────────────────┘              └─────────────────────┘
```

## Validation Rules

No validation is performed on streamed data—it passes through as received from the API. This is intentional:

1. **Performance**: Validation would add overhead to streaming
2. **Fidelity**: Users may want exact API output for debugging
3. **Existing behavior**: Matches how `fetch_events()` works (validation happens at API level)

## State Transitions

N/A - Streaming is stateless. No data persists; each record is yielded and forgotten.

## Relationships

- **Events ↔ Profiles**: No relationship enforced at streaming level
- **Streaming ↔ Storage**: Mutually exclusive paths; streaming bypasses storage entirely
