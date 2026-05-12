# Data Model: Discovery & Query API Enhancements

**Phase**: 1 (Design)
**Created**: 2025-12-23
**Status**: Complete

---

## Overview

This document defines the 5 new data types introduced by this feature. All types are frozen dataclasses following existing patterns in `types.py`.

---

## Entity Definitions

### FunnelInfo

Represents a saved funnel definition for use in funnel queries.

```python
@dataclass(frozen=True)
class FunnelInfo:
    """A saved funnel definition."""

    funnel_id: int
    """Unique identifier for funnel queries."""

    name: str
    """Human-readable funnel name."""
```

**Relationships**: Used as input to `LiveQueryService.funnel(funnel_id=...)` method.

**Validation Rules**:
- `funnel_id` must be positive integer
- `name` must be non-empty string

**Serialization**:
```python
def to_dict(self) -> dict[str, Any]:
    return {"funnel_id": self.funnel_id, "name": self.name}
```

---

### SavedCohort

Represents a saved user cohort for profile filtering.

```python
@dataclass(frozen=True)
class SavedCohort:
    """A saved cohort definition."""

    id: int
    """Unique identifier for profile filtering."""

    name: str
    """Human-readable cohort name."""

    count: int
    """Current number of users in cohort."""

    description: str
    """Optional description (may be empty string)."""

    created: str
    """Creation timestamp (YYYY-MM-DD HH:mm:ss)."""

    is_visible: bool
    """Whether cohort is visible in Mixpanel UI."""
```

**Relationships**: Used with `/engage` endpoint's `filter_by_cohort` parameter.

**Validation Rules**:
- `id` must be positive integer
- `name` must be non-empty string
- `count` must be non-negative integer
- `created` must be valid datetime string
- `is_visible` converted from API integer (0/1) to bool

**Serialization**:
```python
def to_dict(self) -> dict[str, Any]:
    return {
        "id": self.id,
        "name": self.name,
        "count": self.count,
        "description": self.description,
        "created": self.created,
        "is_visible": self.is_visible,
    }
```

---

### TopEvent

Represents an event's current activity for today.

```python
@dataclass(frozen=True)
class TopEvent:
    """Today's event activity data."""

    event: str
    """Event name."""

    count: int
    """Today's event count."""

    percent_change: float
    """Change vs yesterday (-1.0 to +infinity)."""
```

**Relationships**: Standalone discovery result, not used as input to other methods.

**Validation Rules**:
- `event` must be non-empty string
- `count` must be non-negative integer
- `percent_change` can be any float (-1.0 = 100% decrease, 1.0 = 100% increase)

**Serialization**:
```python
def to_dict(self) -> dict[str, Any]:
    return {
        "event": self.event,
        "count": self.count,
        "percent_change": self.percent_change,
    }
```

---

### EventCountsResult

Represents time-series event count data for multiple events.

```python
@dataclass(frozen=True)
class EventCountsResult:
    """Time-series event count data."""

    events: list[str]
    """Queried event names."""

    from_date: str
    """Query start date (YYYY-MM-DD)."""

    to_date: str
    """Query end date (YYYY-MM-DD)."""

    unit: Literal["day", "week", "month"]
    """Time unit for aggregation."""

    type: Literal["general", "unique", "average"]
    """Counting method used."""

    series: dict[str, dict[str, int]]
    """Time series data: {event_name: {date: count}}."""

    _df_cache: pd.DataFrame | None = field(default=None, repr=False)
```

**Relationships**: Result of `LiveQueryService.event_counts()`.

**Validation Rules**:
- `events` must be non-empty list of strings
- `from_date` and `to_date` must be valid YYYY-MM-DD format
- `series` keys are event names, values are {date_string: count}

**DataFrame Conversion**:
```python
@property
def df(self) -> pd.DataFrame:
    """Convert to DataFrame with columns: date, event, count."""
    # Lazy computation, cached after first access
```

**Serialization**:
```python
def to_dict(self) -> dict[str, Any]:
    return {
        "events": self.events,
        "from_date": self.from_date,
        "to_date": self.to_date,
        "unit": self.unit,
        "type": self.type,
        "series": self.series,
    }
```

---

### PropertyCountsResult

Represents time-series property value distribution data.

```python
@dataclass(frozen=True)
class PropertyCountsResult:
    """Time-series property value distribution data."""

    event: str
    """Queried event name."""

    property_name: str
    """Property used for segmentation."""

    from_date: str
    """Query start date (YYYY-MM-DD)."""

    to_date: str
    """Query end date (YYYY-MM-DD)."""

    unit: Literal["day", "week", "month"]
    """Time unit for aggregation."""

    type: Literal["general", "unique", "average"]
    """Counting method used."""

    series: dict[str, dict[str, int]]
    """Time series data: {property_value: {date: count}}."""

    _df_cache: pd.DataFrame | None = field(default=None, repr=False)
```

**Relationships**: Result of `LiveQueryService.property_counts()`.

**Validation Rules**:
- `event` must be non-empty string
- `property_name` must be non-empty string
- `from_date` and `to_date` must be valid YYYY-MM-DD format
- `series` keys are property values, values are {date_string: count}

**DataFrame Conversion**:
```python
@property
def df(self) -> pd.DataFrame:
    """Convert to DataFrame with columns: date, value, count."""
    # Lazy computation, cached after first access
```

**Serialization**:
```python
def to_dict(self) -> dict[str, Any]:
    return {
        "event": self.event,
        "property_name": self.property_name,
        "from_date": self.from_date,
        "to_date": self.to_date,
        "unit": self.unit,
        "type": self.type,
        "series": self.series,
    }
```

---

## Type Hierarchy

```
Result Types (existing)
├── FetchResult
├── SegmentationResult
├── FunnelResult
├── RetentionResult
├── JQLResult
└── Storage Types (TableMetadata, TableInfo, ColumnInfo, TableSchema)

Result Types (new - this feature)
├── FunnelInfo          # Simple value object
├── SavedCohort         # Simple value object
├── TopEvent            # Simple value object
├── EventCountsResult   # Time-series with lazy .df
└── PropertyCountsResult # Time-series with lazy .df
```

---

## State Transitions

None — all types are immutable value objects with no state transitions.

---

## Export Requirements

All 5 new types must be exported from `mixpanel_data/__init__.py`:

```python
from mixpanel_data.types import (
    # Existing exports...
    FunnelInfo,
    SavedCohort,
    TopEvent,
    EventCountsResult,
    PropertyCountsResult,
)

__all__ = [
    # Existing exports...
    "FunnelInfo",
    "SavedCohort",
    "TopEvent",
    "EventCountsResult",
    "PropertyCountsResult",
]
```

---

*Data model complete. See contracts/ for API method signatures.*
