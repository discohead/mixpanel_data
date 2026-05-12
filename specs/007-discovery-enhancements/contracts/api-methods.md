# API Contracts: Discovery & Query API Enhancements

**Phase**: 1 (Design)
**Created**: 2025-12-23
**Status**: Complete

---

## Overview

This document defines the method signatures for all new API client and service methods.

---

## Layer 1: API Client Methods

These are low-level HTTP methods in `MixpanelAPIClient`.

### list_funnels

```python
def list_funnels(self) -> list[dict[str, Any]]:
    """List all saved funnels in the project.

    Returns:
        List of funnel dictionaries with keys: funnel_id (int), name (str).

    Raises:
        AuthenticationError: Invalid credentials.
        RateLimitError: Rate limit exceeded after retries.
    """
```

**HTTP**: `GET /api/query/funnels/list`

**Parameters**: `project_id` (from credentials)

---

### list_cohorts

```python
def list_cohorts(self) -> list[dict[str, Any]]:
    """List all saved cohorts in the project.

    Returns:
        List of cohort dictionaries with keys:
        id (int), name (str), count (int), description (str),
        created (str), is_visible (int), project_id (int).

    Raises:
        AuthenticationError: Invalid credentials.
        RateLimitError: Rate limit exceeded after retries.
    """
```

**HTTP**: `POST /api/query/cohorts/list` (unusual but per API spec)

**Parameters**: `project_id` (from credentials)

---

### get_top_events

```python
def get_top_events(
    self,
    *,
    type: str = "general",
    limit: int | None = None,
) -> dict[str, Any]:
    """Get today's top events with counts and trends.

    Args:
        type: Counting method - "general", "unique", or "average".
        limit: Maximum events to return (default: 100).

    Returns:
        Dictionary with keys:
        - events: list of {amount: int, event: str, percent_change: float}
        - type: str

    Raises:
        AuthenticationError: Invalid credentials.
        RateLimitError: Rate limit exceeded after retries.
    """
```

**HTTP**: `GET /api/query/events/top`

**Parameters**: `project_id`, `type`, `limit`

---

### event_counts

```python
def event_counts(
    self,
    events: list[str],
    from_date: str,
    to_date: str,
    *,
    type: str = "general",
    unit: str = "day",
) -> dict[str, Any]:
    """Get aggregate counts for multiple events over time.

    Args:
        events: List of event names to query.
        from_date: Start date (YYYY-MM-DD).
        to_date: End date (YYYY-MM-DD).
        type: Counting method - "general", "unique", or "average".
        unit: Time unit - "day", "week", or "month".

    Returns:
        Dictionary with keys:
        - data.series: list of date strings
        - data.values: {event_name: {date: count}}
        - legend_size: int

    Raises:
        AuthenticationError: Invalid credentials.
        QueryError: Invalid parameters.
        RateLimitError: Rate limit exceeded after retries.
    """
```

**HTTP**: `GET /api/query/events`

**Parameters**: `project_id`, `event` (JSON array), `type`, `unit`, `from_date`, `to_date`

---

### property_counts

```python
def property_counts(
    self,
    event: str,
    property_name: str,
    from_date: str,
    to_date: str,
    *,
    type: str = "general",
    unit: str = "day",
    values: list[str] | None = None,
    limit: int | None = None,
) -> dict[str, Any]:
    """Get aggregate counts by property values over time.

    Args:
        event: Event name to query.
        property_name: Property to segment by.
        from_date: Start date (YYYY-MM-DD).
        to_date: End date (YYYY-MM-DD).
        type: Counting method - "general", "unique", or "average".
        unit: Time unit - "day", "week", or "month".
        values: Optional list of specific property values to include.
        limit: Maximum property values to return (default: 255).

    Returns:
        Dictionary with keys:
        - data.series: list of date strings
        - data.values: {property_value: {date: count}}
        - legend_size: int

    Raises:
        AuthenticationError: Invalid credentials.
        QueryError: Invalid parameters.
        RateLimitError: Rate limit exceeded after retries.
    """
```

**HTTP**: `GET /api/query/events/properties`

**Parameters**: `project_id`, `event`, `name`, `type`, `unit`, `from_date`, `to_date`, `values`, `limit`

---

## Layer 2: Discovery Service Methods

These are high-level methods in `DiscoveryService`.

### list_funnels

```python
def list_funnels(self) -> list[FunnelInfo]:
    """List all saved funnels in the project.

    Returns:
        Alphabetically sorted list of FunnelInfo objects.
        Empty list if no funnels exist (not an error).

    Raises:
        AuthenticationError: Invalid credentials.

    Note:
        Results are cached for the lifetime of this service instance.
    """
```

**Caching**: Yes — key `("list_funnels",)`

**Transformation**:
```python
sorted([FunnelInfo(**f) for f in raw], key=lambda x: x.name)
```

---

### list_cohorts

```python
def list_cohorts(self) -> list[SavedCohort]:
    """List all saved cohorts in the project.

    Returns:
        Alphabetically sorted list of SavedCohort objects.
        Empty list if no cohorts exist (not an error).

    Raises:
        AuthenticationError: Invalid credentials.

    Note:
        Results are cached for the lifetime of this service instance.
    """
```

**Caching**: Yes — key `("list_cohorts",)`

**Transformation**:
```python
sorted([
    SavedCohort(
        id=c["id"],
        name=c["name"],
        count=c["count"],
        description=c.get("description", ""),
        created=c["created"],
        is_visible=bool(c["is_visible"]),
    )
    for c in raw
], key=lambda x: x.name)
```

---

### list_top_events

```python
def list_top_events(
    self,
    *,
    type: str = "general",
    limit: int | None = None,
) -> list[TopEvent]:
    """Get today's top events with counts and trends.

    Args:
        type: Counting method - "general", "unique", or "average".
        limit: Maximum events to return (default: 100).

    Returns:
        List of TopEvent objects (NOT cached - real-time data).

    Raises:
        AuthenticationError: Invalid credentials.

    Note:
        Results are NOT cached because data changes throughout the day.
    """
```

**Caching**: No — always fetch fresh

**Transformation**:
```python
[
    TopEvent(
        event=e["event"],
        count=e["amount"],  # Map amount -> count
        percent_change=e["percent_change"],
    )
    for e in raw["events"]
]
```

---

## Layer 3: Live Query Service Methods

These are high-level methods in `LiveQueryService`.

### event_counts

```python
def event_counts(
    self,
    events: list[str],
    from_date: str,
    to_date: str,
    *,
    type: str = "general",
    unit: str = "day",
) -> EventCountsResult:
    """Query aggregate counts for multiple events over time.

    Args:
        events: List of event names to query.
        from_date: Start date (YYYY-MM-DD).
        to_date: End date (YYYY-MM-DD).
        type: Counting method - "general", "unique", or "average".
        unit: Time unit - "day", "week", or "month".

    Returns:
        EventCountsResult with time-series data and lazy DataFrame.

    Raises:
        AuthenticationError: Invalid credentials.
        QueryError: Invalid parameters.
        RateLimitError: Rate limit exceeded.

    Example:
        >>> result = live_query.event_counts(
        ...     events=["Sign Up", "Purchase"],
        ...     from_date="2024-01-01",
        ...     to_date="2024-01-31",
        ... )
        >>> print(result.series["Sign Up"])
        >>> print(result.df.head())
    """
```

**Caching**: No — live query

**Transformation**:
```python
EventCountsResult(
    events=events,
    from_date=from_date,
    to_date=to_date,
    unit=unit,
    type=type,
    series=raw["data"]["values"],
)
```

---

### property_counts

```python
def property_counts(
    self,
    event: str,
    property_name: str,
    from_date: str,
    to_date: str,
    *,
    type: str = "general",
    unit: str = "day",
    values: list[str] | None = None,
    limit: int | None = None,
) -> PropertyCountsResult:
    """Query aggregate counts by property values over time.

    Args:
        event: Event name to query.
        property_name: Property to segment by.
        from_date: Start date (YYYY-MM-DD).
        to_date: End date (YYYY-MM-DD).
        type: Counting method - "general", "unique", or "average".
        unit: Time unit - "day", "week", or "month".
        values: Optional list of specific property values to include.
        limit: Maximum property values to return (default: 255).

    Returns:
        PropertyCountsResult with time-series data and lazy DataFrame.

    Raises:
        AuthenticationError: Invalid credentials.
        QueryError: Invalid parameters.
        RateLimitError: Rate limit exceeded.

    Example:
        >>> result = live_query.property_counts(
        ...     event="Purchase",
        ...     property_name="country",
        ...     from_date="2024-01-01",
        ...     to_date="2024-01-31",
        ... )
        >>> print(result.series["US"])
        >>> print(result.df.head())
    """
```

**Caching**: No — live query

**Transformation**:
```python
PropertyCountsResult(
    event=event,
    property_name=property_name,
    from_date=from_date,
    to_date=to_date,
    unit=unit,
    type=type,
    series=raw["data"]["values"],
)
```

---

## Method Summary

| Layer | Method | Caching | Result Type |
|-------|--------|---------|-------------|
| API Client | `list_funnels()` | — | `list[dict]` |
| API Client | `list_cohorts()` | — | `list[dict]` |
| API Client | `get_top_events()` | — | `dict` |
| API Client | `event_counts()` | — | `dict` |
| API Client | `property_counts()` | — | `dict` |
| Discovery | `list_funnels()` | Yes | `list[FunnelInfo]` |
| Discovery | `list_cohorts()` | Yes | `list[SavedCohort]` |
| Discovery | `list_top_events()` | No | `list[TopEvent]` |
| LiveQuery | `event_counts()` | No | `EventCountsResult` |
| LiveQuery | `property_counts()` | No | `PropertyCountsResult` |

---

*Contracts complete. See quickstart.md for usage examples.*
