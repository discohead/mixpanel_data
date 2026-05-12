# Data Model: Live Query Service

**Date**: 2025-12-22
**Feature**: 006-live-query-service

## Overview

This document describes the data model for the Live Query Service. All result types already exist in `src/mixpanel_data/types.py` and are frozen dataclasses with lazy DataFrame conversion.

---

## Entity Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                        LiveQueryService                          │
├─────────────────────────────────────────────────────────────────┤
│ - _api_client: MixpanelAPIClient                                 │
├─────────────────────────────────────────────────────────────────┤
│ + segmentation(...) → SegmentationResult                         │
│ + funnel(...) → FunnelResult                                     │
│ + retention(...) → RetentionResult                               │
│ + jql(...) → JQLResult                                           │
└─────────────────────────────────────────────────────────────────┘
          │
          │ returns
          ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Result Types (frozen)                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌──────────────────┐    ┌──────────────────┐                    │
│  │SegmentationResult│    │   FunnelResult   │                    │
│  ├──────────────────┤    ├──────────────────┤                    │
│  │ event: str       │    │ funnel_id: int   │                    │
│  │ from_date: str   │    │ funnel_name: str │                    │
│  │ to_date: str     │    │ from_date: str   │                    │
│  │ unit: str        │    │ to_date: str     │                    │
│  │ segment_property │    │ conversion_rate  │                    │
│  │ total: int       │    │ steps: list      │──┐                 │
│  │ series: dict     │    └──────────────────┘  │                 │
│  └──────────────────┘                          │                 │
│                                                │                 │
│  ┌──────────────────┐    ┌──────────────────┐  │                 │
│  │ RetentionResult  │    │   FunnelStep     │◄─┘                 │
│  ├──────────────────┤    ├──────────────────┤                    │
│  │ born_event: str  │    │ event: str       │                    │
│  │ return_event: str│    │ count: int       │                    │
│  │ from_date: str   │    │ conversion_rate  │                    │
│  │ to_date: str     │    └──────────────────┘                    │
│  │ unit: str        │                                            │
│  │ cohorts: list    │──┐                                         │
│  └──────────────────┘  │                                         │
│                        │   ┌──────────────────┐                  │
│  ┌──────────────────┐  │   │   CohortInfo     │◄─────────────────┘
│  │    JQLResult     │  │   ├──────────────────┤                   │
│  ├──────────────────┤  │   │ date: str        │                   │
│  │ _raw: list[Any]  │  │   │ size: int        │                   │
│  │ + raw property   │  │   │ retention: list  │                   │
│  │ + df property    │  │   └──────────────────┘                   │
│  └──────────────────┘  │                                          │
│                        └──────────────────────────────────────────┘
└───────────────────────────────────────────────────────────────────┘
```

---

## Result Types

### SegmentationResult

Time-series event counts, optionally segmented by property.

| Field | Type | Description |
|-------|------|-------------|
| `event` | `str` | Event name queried |
| `from_date` | `str` | Start date (YYYY-MM-DD) |
| `to_date` | `str` | End date (YYYY-MM-DD) |
| `unit` | `Literal["day", "week", "month"]` | Time aggregation unit |
| `segment_property` | `str \| None` | Property used for segmentation |
| `total` | `int` | Sum of all counts |
| `series` | `dict[str, dict[str, int]]` | {segment: {date: count}} |

**DataFrame Columns**: `date`, `segment`, `count`

**Validation Rules**:
- `unit` must be one of: day, week, month
- Dates must be YYYY-MM-DD format
- `total` must equal sum of all values in `series`

---

### FunnelResult

Step-by-step conversion data for a funnel.

| Field | Type | Description |
|-------|------|-------------|
| `funnel_id` | `int` | Funnel identifier |
| `funnel_name` | `str` | Funnel display name (may be empty) |
| `from_date` | `str` | Start date (YYYY-MM-DD) |
| `to_date` | `str` | End date (YYYY-MM-DD) |
| `conversion_rate` | `float` | Overall conversion (0.0 to 1.0) |
| `steps` | `list[FunnelStep]` | Step-by-step breakdown |

**DataFrame Columns**: `step`, `event`, `count`, `conversion_rate`

---

### FunnelStep

Single step in a funnel.

| Field | Type | Description |
|-------|------|-------------|
| `event` | `str` | Event name for this step |
| `count` | `int` | Number of users at this step |
| `conversion_rate` | `float` | Conversion from previous step (0.0 to 1.0) |

**Validation Rules**:
- First step always has `conversion_rate = 1.0`
- `conversion_rate` = this step count / previous step count

---

### RetentionResult

Cohort-based retention data.

| Field | Type | Description |
|-------|------|-------------|
| `born_event` | `str` | Event that defines cohort membership |
| `return_event` | `str` | Event that defines return |
| `from_date` | `str` | Start date (YYYY-MM-DD) |
| `to_date` | `str` | End date (YYYY-MM-DD) |
| `unit` | `Literal["day", "week", "month"]` | Retention period unit |
| `cohorts` | `list[CohortInfo]` | Cohort retention data |

**DataFrame Columns**: `cohort_date`, `cohort_size`, `period_0`, `period_1`, ...

---

### CohortInfo

Retention data for a single cohort.

| Field | Type | Description |
|-------|------|-------------|
| `date` | `str` | Cohort date (when users were "born") |
| `size` | `int` | Number of users in cohort |
| `retention` | `list[float]` | Retention percentages by period (0.0 to 1.0) |

**Validation Rules**:
- `retention[0]` is typically 1.0 (users who returned on day 0)
- Each value is calculated as: users_returned / cohort_size

---

### JQLResult

Raw results from JQL script execution.

| Field | Type | Description |
|-------|------|-------------|
| `_raw` | `list[Any]` | Raw result data (internal) |

**Properties**:
- `raw`: Returns the raw list
- `df`: Converts to DataFrame (list of dicts → columns, list of values → 'value' column)

---

## Service Interface

### LiveQueryService

```python
class LiveQueryService:
    def __init__(self, api_client: MixpanelAPIClient) -> None:
        """Initialize with authenticated API client."""

    def segmentation(
        self,
        event: str,
        from_date: str,
        to_date: str,
        *,
        on: str | None = None,
        unit: str = "day",
        where: str | None = None,
    ) -> SegmentationResult:
        """Run a segmentation query."""

    def funnel(
        self,
        funnel_id: int,
        from_date: str,
        to_date: str,
        *,
        unit: str = "day",
        on: str | None = None,
    ) -> FunnelResult:
        """Run a funnel analysis query."""

    def retention(
        self,
        born_event: str,
        return_event: str,
        from_date: str,
        to_date: str,
        *,
        born_where: str | None = None,
        return_where: str | None = None,
        interval: int = 1,
        interval_count: int = 10,
        unit: str = "day",
    ) -> RetentionResult:
        """Run a retention analysis query."""

    def jql(
        self,
        script: str,
        params: dict[str, Any] | None = None,
    ) -> JQLResult:
        """Execute a JQL script."""
```

---

## State Management

**No state**: `LiveQueryService` does not maintain any state between calls. Each query is independent.

**No caching**: Unlike `DiscoveryService`, live query results are not cached because analytics data changes frequently.

**Dependency injection**: The API client is injected via constructor, enabling easy testing with mock transports.

---

## Existing Types Location

All result types are already implemented in:
- `src/mixpanel_data/types.py`

The `LiveQueryService` will import and construct these types. No modifications to `types.py` are required.
