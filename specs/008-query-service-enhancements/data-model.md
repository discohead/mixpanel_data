# Data Model: Query Service Enhancements

**Date**: 2024-12-23
**Feature**: 008-query-service-enhancements
**Status**: Complete

## Overview

This document defines the 7 new result types for Phase 008. All types are frozen dataclasses following the established pattern from `types.py`.

---

## Entity Definitions

### UserEvent

**Purpose**: Single event in a user's activity feed

**Fields**:

| Field | Type | Description |
|-------|------|-------------|
| event | str | Event name |
| time | datetime | Event timestamp (UTC) |
| properties | dict[str, Any] | All event properties including system props |

**Relationships**: Component of ActivityFeedResult

**Validation Rules**:
- `time` must be timezone-aware (UTC)
- `properties` may be empty dict but not None

**State Transitions**: None (immutable)

---

### ActivityFeedResult

**Purpose**: Collection of user events from activity feed query

**Fields**:

| Field | Type | Description |
|-------|------|-------------|
| distinct_ids | list[str] | Queried user identifiers |
| from_date | str \| None | Start date filter (YYYY-MM-DD) |
| to_date | str \| None | End date filter (YYYY-MM-DD) |
| events | list[UserEvent] | Event history (chronological) |
| _df_cache | pd.DataFrame \| None | Internal DataFrame cache |

**DataFrame Columns**: event, time, distinct_id, + flattened property columns

**Relationships**: Contains UserEvent instances

**Validation Rules**:
- `distinct_ids` must have at least one element
- `events` may be empty list

**Serialization** (`to_dict`):
```python
{
    "distinct_ids": [...],
    "from_date": "2024-01-01",
    "to_date": "2024-01-31",
    "event_count": 150,
    "events": [{"event": "...", "time": "...", "properties": {...}}, ...]
}
```

---

### InsightsResult

**Purpose**: Data from a saved Insights report

**Fields**:

| Field | Type | Description |
|-------|------|-------------|
| bookmark_id | int | Saved report identifier |
| computed_at | str | When report was computed (ISO format) |
| from_date | str | Report start date |
| to_date | str | Report end date |
| headers | list[str] | Report column headers |
| series | dict[str, dict[str, int]] | Time-series: {event: {date: count}} |
| _df_cache | pd.DataFrame \| None | Internal DataFrame cache |

**DataFrame Columns**: date, event, count

**Relationships**: Standalone result

**Validation Rules**:
- `bookmark_id` must be positive integer
- `series` may be empty dict

**Serialization** (`to_dict`):
```python
{
    "bookmark_id": 12345,
    "computed_at": "2024-01-15T10:30:00+00:00",
    "from_date": "2024-01-01",
    "to_date": "2024-01-31",
    "headers": ["$event"],
    "series": {"Sign Up": {"2024-01-01": 100, ...}, ...}
}
```

---

### FrequencyResult

**Purpose**: Event frequency distribution (addiction analysis)

**Fields**:

| Field | Type | Description |
|-------|------|-------------|
| event | str \| None | Filtered event (None = all events) |
| from_date | str | Query start date |
| to_date | str | Query end date |
| unit | Literal["day", "week", "month"] | Overall time period |
| addiction_unit | Literal["hour", "day"] | Measurement granularity |
| data | dict[str, list[int]] | Frequency arrays: {date: [count_1, count_2, ...]} |
| _df_cache | pd.DataFrame \| None | Internal DataFrame cache |

**DataFrame Columns**: date, period_1, period_2, ... period_N

**Relationships**: Standalone result

**Validation Rules**:
- `unit` must be valid Literal value
- `addiction_unit` must be valid Literal value
- Array lengths vary by `addiction_unit` (24 for hour, variable for day)

**Interpretation**:
- Index N in array = users who performed event in at least N+1 time periods
- Example: `[305, 107, 60]` means 305 users did it 1+ times, 107 did it 2+ times, 60 did it 3+ times

**Serialization** (`to_dict`):
```python
{
    "event": "Purchase",
    "from_date": "2024-01-01",
    "to_date": "2024-01-31",
    "unit": "day",
    "addiction_unit": "hour",
    "data": {"2024-01-01": [305, 107, 60, ...], ...}
}
```

---

### NumericBucketResult

**Purpose**: Events segmented into numeric property ranges

**Fields**:

| Field | Type | Description |
|-------|------|-------------|
| event | str | Queried event name |
| from_date | str | Query start date |
| to_date | str | Query end date |
| property_expr | str | The 'on' expression used for bucketing |
| unit | Literal["hour", "day"] | Time aggregation unit |
| series | dict[str, dict[str, int]] | Bucket data: {range: {date: count}} |
| _df_cache | pd.DataFrame \| None | Internal DataFrame cache |

**DataFrame Columns**: date, bucket, count

**Relationships**: Standalone result

**Validation Rules**:
- `property_expr` must be non-empty string
- `unit` must be valid Literal value
- Bucket range keys are formatted strings (e.g., "2,000 - 2,100")

**Serialization** (`to_dict`):
```python
{
    "event": "Purchase",
    "from_date": "2024-01-01",
    "to_date": "2024-01-31",
    "property_expr": "properties[\"amount\"]",
    "unit": "day",
    "series": {"0 - 100": {"2024-01-01": 50, ...}, ...}
}
```

---

### NumericSumResult

**Purpose**: Sum of numeric property values per time unit

**Fields**:

| Field | Type | Description |
|-------|------|-------------|
| event | str | Queried event name |
| from_date | str | Query start date |
| to_date | str | Query end date |
| property_expr | str | The 'on' expression summed |
| unit | Literal["hour", "day"] | Time aggregation unit |
| results | dict[str, float] | Sum values: {date: sum} |
| computed_at | str \| None | Computation timestamp (if provided) |
| _df_cache | pd.DataFrame \| None | Internal DataFrame cache |

**DataFrame Columns**: date, sum

**Relationships**: Standalone result

**Validation Rules**:
- `property_expr` must be non-empty string
- `unit` must be valid Literal value
- Values are floats (sum of numeric values)

**Serialization** (`to_dict`):
```python
{
    "event": "Purchase",
    "from_date": "2024-01-01",
    "to_date": "2024-01-31",
    "property_expr": "properties[\"amount\"]",
    "unit": "day",
    "results": {"2024-01-01": 15432.50, "2024-01-02": 18976.25, ...},
    "computed_at": "2024-01-31T12:00:00+00:00"
}
```

---

### NumericAverageResult

**Purpose**: Average of numeric property values per time unit

**Fields**:

| Field | Type | Description |
|-------|------|-------------|
| event | str | Queried event name |
| from_date | str | Query start date |
| to_date | str | Query end date |
| property_expr | str | The 'on' expression averaged |
| unit | Literal["hour", "day"] | Time aggregation unit |
| results | dict[str, float] | Average values: {date: average} |
| _df_cache | pd.DataFrame \| None | Internal DataFrame cache |

**DataFrame Columns**: date, average

**Relationships**: Standalone result

**Validation Rules**:
- `property_expr` must be non-empty string
- `unit` must be valid Literal value
- Values are floats (mean of numeric values)

**Serialization** (`to_dict`):
```python
{
    "event": "Purchase",
    "from_date": "2024-01-01",
    "to_date": "2024-01-31",
    "property_expr": "properties[\"amount\"]",
    "unit": "day",
    "results": {"2024-01-01": 54.32, "2024-01-02": 62.15, ...}
}
```

---

## Entity Relationship Diagram

```
┌─────────────────────┐
│   UserEvent         │
├─────────────────────┤
│ event: str          │
│ time: datetime      │
│ properties: dict    │
└─────────┬───────────┘
          │ 0..*
          │
┌─────────▼───────────┐
│ ActivityFeedResult  │
├─────────────────────┤
│ distinct_ids: list  │
│ from_date: str?     │
│ to_date: str?       │
│ events: list        │◄─────────────────────┐
└─────────────────────┘                      │
                                             │ All result types
┌─────────────────────┐                      │ implement:
│   InsightsResult    │                      │
├─────────────────────┤                      │ - @dataclass(frozen=True)
│ bookmark_id: int    │                      │ - .df property (lazy)
│ computed_at: str    │                      │ - .to_dict() method
│ from_date: str      │──────────────────────┤
│ to_date: str        │                      │
│ headers: list       │                      │
│ series: dict        │                      │
└─────────────────────┘                      │
                                             │
┌─────────────────────┐                      │
│   FrequencyResult   │                      │
├─────────────────────┤                      │
│ event: str?         │                      │
│ from_date: str      │──────────────────────┤
│ to_date: str        │                      │
│ unit: Literal       │                      │
│ addiction_unit: Lit │                      │
│ data: dict          │                      │
└─────────────────────┘                      │
                                             │
┌─────────────────────┐                      │
│ NumericBucketResult │                      │
├─────────────────────┤                      │
│ event: str          │                      │
│ from_date: str      │──────────────────────┤
│ to_date: str        │                      │
│ property_expr: str  │                      │
│ unit: Literal       │                      │
│ series: dict        │                      │
└─────────────────────┘                      │
                                             │
┌─────────────────────┐                      │
│  NumericSumResult   │                      │
├─────────────────────┤                      │
│ event: str          │                      │
│ from_date: str      │──────────────────────┤
│ to_date: str        │                      │
│ property_expr: str  │                      │
│ unit: Literal       │                      │
│ results: dict       │                      │
│ computed_at: str?   │                      │
└─────────────────────┘                      │
                                             │
┌─────────────────────┐                      │
│NumericAverageResult │                      │
├─────────────────────┤                      │
│ event: str          │                      │
│ from_date: str      │──────────────────────┘
│ to_date: str        │
│ property_expr: str  │
│ unit: Literal       │
│ results: dict       │
└─────────────────────┘
```

---

## Implementation Pattern

All result types follow this pattern from `types.py`:

```python
@dataclass(frozen=True)
class ExampleResult:
    """Brief description.

    Detailed description of what this result represents.
    """

    field: str
    """Field docstring."""

    other_field: dict[str, Any] = field(default_factory=dict)
    """Field with default."""

    _df_cache: pd.DataFrame | None = field(default=None, repr=False)

    @property
    def df(self) -> pd.DataFrame:
        """Convert to DataFrame.

        Columns: col1, col2, col3
        """
        if self._df_cache is not None:
            return self._df_cache

        rows: list[dict[str, Any]] = []
        # Build rows...

        result_df = pd.DataFrame(rows) if rows else pd.DataFrame(columns=[...])
        object.__setattr__(self, "_df_cache", result_df)
        return result_df

    def to_dict(self) -> dict[str, Any]:
        """Serialize for JSON output."""
        return {
            "field": self.field,
            "other_field": self.other_field,
        }
```
