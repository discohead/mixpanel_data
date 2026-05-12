# Data Model: Engage API Full Parameter Support

**Feature**: 018-engage-api-params
**Date**: 2026-01-04

## Overview

This feature adds 6 new parameters to the profile querying functionality. No new entities are created; the feature extends existing parameter handling across 4 architectural layers.

## Parameter Types

### New Parameters

| Parameter | Python Type | Description |
|-----------|-------------|-------------|
| `distinct_id` | `str \| None` | Single user ID to fetch |
| `distinct_ids` | `list[str] \| None` | List of user IDs to fetch (max 2000) |
| `group_id` | `str \| None` | Group type for group profile queries |
| `behaviors` | `str \| None` | Event behavior selector expression |
| `as_of_timestamp` | `int \| None` | Unix epoch for point-in-time queries |
| `include_all_users` | `bool \| None` | Include cohort members without profiles |

### Validation Rules

```
┌─────────────────────────────────────────────────────────────┐
│                    Parameter Constraints                     │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  distinct_id ─────┬───> Only ONE allowed                    │
│                   │     ValueError if both specified        │
│  distinct_ids ────┘                                         │
│                                                             │
│  behaviors ───────┬───> Only ONE allowed                    │
│                   │     ValueError if both specified        │
│  cohort_id ───────┘                                         │
│                                                             │
│  include_all_users ──> Requires cohort_id                   │
│                        ValueError if cohort_id missing      │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

## Existing Type Extensions

### TableMetadata (types.py)

Add new field to track group profile fetches:

```python
@dataclass
class TableMetadata:
    type: Literal["events", "profiles"]
    fetched_at: datetime
    from_date: datetime | None
    to_date: datetime | None
    filter_events: list[str] | None
    filter_where: str | None
    filter_cohort_id: str | None
    filter_output_properties: list[str] | None
    # NEW FIELDS
    filter_group_id: str | None  # Track group profile queries
    filter_behaviors: str | None  # Track behavior-based filtering
```

## Layer-by-Layer Parameter Mapping

```
┌─────────────────┬─────────────────┬─────────────────┬─────────────────┐
│   API Client    │    Fetcher      │   Workspace     │      CLI        │
│ (api_client.py) │  (fetcher.py)   │ (workspace.py)  │   (fetch.py)    │
├─────────────────┼─────────────────┼─────────────────┼─────────────────┤
│ distinct_id     │ distinct_id     │ distinct_id     │ --distinct-id   │
│ distinct_ids    │ distinct_ids    │ distinct_ids    │ --distinct-ids  │
│ data_group_id   │ group_id        │ group_id        │ --group-id      │
│ behaviors       │ behaviors       │ behaviors       │ --behaviors     │
│ as_of_timestamp │ as_of_timestamp │ as_of_timestamp │ --as-of-timestamp│
│ include_all_users│include_all_users│include_all_users│ --include-all-users│
└─────────────────┴─────────────────┴─────────────────┴─────────────────┘
```

## Method Signatures

### API Client Layer

```python
def export_profiles(
    self,
    *,
    where: str | None = None,
    cohort_id: str | None = None,
    output_properties: list[str] | None = None,
    on_batch: Callable[[int], None] | None = None,
    # NEW PARAMETERS
    distinct_id: str | None = None,
    distinct_ids: list[str] | None = None,
    data_group_id: str | None = None,
    behaviors: str | None = None,
    as_of_timestamp: int | None = None,
    include_all_users: bool | None = None,
) -> Iterator[dict[str, Any]]:
```

### Fetcher Service Layer

```python
def fetch_profiles(
    self,
    name: str,
    *,
    where: str | None = None,
    cohort_id: str | None = None,
    output_properties: list[str] | None = None,
    progress_callback: Callable[[int], None] | None = None,
    append: bool = False,
    batch_size: int = 1000,
    # NEW PARAMETERS
    distinct_id: str | None = None,
    distinct_ids: list[str] | None = None,
    group_id: str | None = None,
    behaviors: str | None = None,
    as_of_timestamp: int | None = None,
    include_all_users: bool | None = None,
) -> FetchResult:
```

### Workspace Layer

```python
def fetch_profiles(
    self,
    name: str = "profiles",
    *,
    where: str | None = None,
    cohort_id: str | None = None,
    output_properties: list[str] | None = None,
    progress: bool = True,
    append: bool = False,
    batch_size: int = 1000,
    # NEW PARAMETERS
    distinct_id: str | None = None,
    distinct_ids: list[str] | None = None,
    group_id: str | None = None,
    behaviors: str | None = None,
    as_of_timestamp: int | None = None,
    include_all_users: bool | None = None,
) -> FetchResult:

def stream_profiles(
    self,
    *,
    where: str | None = None,
    cohort_id: str | None = None,
    output_properties: list[str] | None = None,
    raw: bool = False,
    # NEW PARAMETERS
    distinct_id: str | None = None,
    distinct_ids: list[str] | None = None,
    group_id: str | None = None,
    behaviors: str | None = None,
    as_of_timestamp: int | None = None,
    include_all_users: bool | None = None,
) -> Iterator[dict[str, Any]]:
```

## State Transitions

No state machine changes. Profile fetching remains stateless with pagination handled via session_id/page internally.

## Backward Compatibility

All new parameters are optional with `None` defaults. Existing code calling these methods without the new parameters will continue to work unchanged.
