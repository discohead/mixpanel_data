# Research: Live Query Service API Response Transformations

**Date**: 2025-12-22
**Feature**: 006-live-query-service

## Overview

This document captures the research findings for transforming raw Mixpanel Query API responses into typed result objects. All response formats are derived from the OpenAPI spec at `docs/api-docs/openapi/src/query.openapi.yaml` and validated against the existing API client implementation.

---

## 1. Segmentation Response Transformation

### Raw API Response Format

```json
{
  "data": {
    "series": ["2024-01-01", "2024-01-02", "2024-01-03"],
    "values": {
      "Signed up": {
        "2024-01-01": 147,
        "2024-01-02": 146,
        "2024-01-03": 776
      }
    }
  },
  "legend_size": 1
}
```

When segmented by property (`on` parameter):
```json
{
  "data": {
    "series": ["2024-01-01", "2024-01-02"],
    "values": {
      "US": {"2024-01-01": 100, "2024-01-02": 120},
      "CA": {"2024-01-01": 50, "2024-01-02": 60}
    }
  },
  "legend_size": 2
}
```

### Target Type: `SegmentationResult`

```python
@dataclass(frozen=True)
class SegmentationResult:
    event: str                              # From input parameter
    from_date: str                          # From input parameter
    to_date: str                            # From input parameter
    unit: Literal["day", "week", "month"]   # From input parameter
    segment_property: str | None            # From input parameter (on)
    total: int                              # Calculated: sum of all values
    series: dict[str, dict[str, int]]       # From data.values
```

### Transformation Logic

```python
def _transform_segmentation(
    raw: dict[str, Any],
    event: str,
    from_date: str,
    to_date: str,
    unit: str,
    on: str | None
) -> SegmentationResult:
    data = raw.get("data", {})
    values = data.get("values", {})

    # Calculate total by summing all counts
    total = sum(
        count
        for segment_values in values.values()
        for count in segment_values.values()
    )

    return SegmentationResult(
        event=event,
        from_date=from_date,
        to_date=to_date,
        unit=unit,  # type: ignore (validated by caller)
        segment_property=on,
        total=total,
        series=values,
    )
```

### Decision
- **Chosen**: Extract `series` directly from `data.values`, calculate `total` by summing all values
- **Rationale**: Simple, direct mapping; no data loss
- **Alternatives**: Could store `data.series` (date list) separately, but it's redundant with dict keys

---

## 2. Funnel Response Transformation

### Raw API Response Format

The funnel API returns date-grouped data:
```json
{
  "meta": {
    "dates": ["2024-01-01", "2024-01-02"]
  },
  "data": {
    "2024-01-01": {
      "steps": [
        {
          "count": 32688,
          "step_conv_ratio": 1.0,
          "overall_conv_ratio": 1.0,
          "event": "App Open",
          "goal": "App Open"
        },
        {
          "count": 20524,
          "step_conv_ratio": 0.6278,
          "overall_conv_ratio": 0.6278,
          "event": "Game Played",
          "goal": "Game Played"
        }
      ],
      "analysis": {
        "completion": 20524,
        "starting_amount": 32688,
        "steps": 2,
        "worst": 1
      }
    },
    "2024-01-02": { ... }
  }
}
```

### Target Types: `FunnelResult` and `FunnelStep`

```python
@dataclass(frozen=True)
class FunnelStep:
    event: str           # From step.event or step.goal
    count: int           # From step.count
    conversion_rate: float  # From step.step_conv_ratio

@dataclass(frozen=True)
class FunnelResult:
    funnel_id: int       # From input parameter
    funnel_name: str     # NOT in API response - use empty string or fetch separately
    from_date: str       # From input parameter
    to_date: str         # From input parameter
    conversion_rate: float  # Calculated: last step count / first step count
    steps: list[FunnelStep]  # Aggregated across all dates
```

### Transformation Logic

**Key Decision**: The API returns per-date data. We need to aggregate across all dates.

```python
def _transform_funnel(
    raw: dict[str, Any],
    funnel_id: int,
    from_date: str,
    to_date: str
) -> FunnelResult:
    data = raw.get("data", {})

    # Aggregate steps across all dates
    # Use the most recent date's structure as template
    aggregated_counts: dict[int, tuple[str, int]] = {}  # step_idx -> (event, total_count)

    for date_data in data.values():
        steps = date_data.get("steps", [])
        for idx, step in enumerate(steps):
            event = step.get("event", step.get("goal", f"Step {idx + 1}"))
            count = step.get("count", 0)
            if idx in aggregated_counts:
                _, existing = aggregated_counts[idx]
                aggregated_counts[idx] = (event, existing + count)
            else:
                aggregated_counts[idx] = (event, count)

    # Build FunnelStep list
    steps: list[FunnelStep] = []
    prev_count = 0
    for idx in sorted(aggregated_counts.keys()):
        event, count = aggregated_counts[idx]
        if idx == 0:
            conv_rate = 1.0
        else:
            conv_rate = count / prev_count if prev_count > 0 else 0.0
        steps.append(FunnelStep(event=event, count=count, conversion_rate=conv_rate))
        prev_count = count

    # Overall conversion rate
    if steps:
        overall_rate = steps[-1].count / steps[0].count if steps[0].count > 0 else 0.0
    else:
        overall_rate = 0.0

    return FunnelResult(
        funnel_id=funnel_id,
        funnel_name="",  # Not available from API
        from_date=from_date,
        to_date=to_date,
        conversion_rate=overall_rate,
        steps=steps,
    )
```

### Decision
- **Chosen**: Aggregate step counts across all dates, recalculate conversion rates
- **Rationale**: Provides meaningful totals for the entire date range
- **Alternative Considered**: Return per-date breakdowns - rejected because spec requires single FunnelResult
- **Note**: `funnel_name` is not in the response; would require separate `/funnels/list` call. Using empty string for now.

---

## 3. Retention Response Transformation

### Raw API Response Format

```json
{
  "2024-01-01": {
    "counts": [9, 7, 6],
    "first": 10
  },
  "2024-01-02": {
    "counts": [8, 5, 4],
    "first": 9
  }
}
```

- `first`: Number of users in the cohort (performed born_event on that date)
- `counts`: Array of users who returned on period 0, 1, 2, etc.

### Target Types: `RetentionResult` and `CohortInfo`

```python
@dataclass(frozen=True)
class CohortInfo:
    date: str            # Cohort date (key from response)
    size: int            # From cohort.first
    retention: list[float]  # Calculated: counts[i] / first

@dataclass(frozen=True)
class RetentionResult:
    born_event: str      # From input parameter
    return_event: str    # From input parameter
    from_date: str       # From input parameter
    to_date: str         # From input parameter
    unit: Literal["day", "week", "month"]  # From input parameter
    cohorts: list[CohortInfo]  # Transformed from response
```

### Transformation Logic

```python
def _transform_retention(
    raw: dict[str, Any],
    born_event: str,
    return_event: str,
    from_date: str,
    to_date: str,
    unit: str
) -> RetentionResult:
    cohorts: list[CohortInfo] = []

    # Sort by date for consistent ordering
    for date in sorted(raw.keys()):
        cohort_data = raw[date]
        size = cohort_data.get("first", 0)
        counts = cohort_data.get("counts", [])

        # Calculate retention percentages
        retention = [
            count / size if size > 0 else 0.0
            for count in counts
        ]

        cohorts.append(CohortInfo(
            date=date,
            size=size,
            retention=retention,
        ))

    return RetentionResult(
        born_event=born_event,
        return_event=return_event,
        from_date=from_date,
        to_date=to_date,
        unit=unit,  # type: ignore
        cohorts=cohorts,
    )
```

### Decision
- **Chosen**: Calculate retention percentages as `counts[i] / first`
- **Rationale**: Percentages are more useful for analysis than raw counts
- **Alternative Considered**: Store raw counts alongside percentages - rejected for simplicity

---

## 4. JQL Response Transformation

### Raw API Response Format

JQL returns an array of arbitrary objects (depends on the script):
```json
[
  {"name": "Login", "value": 1523},
  {"name": "Purchase", "value": 847}
]
```

Or simple values:
```json
[1523, 847, 2134]
```

### Target Type: `JQLResult`

```python
@dataclass(frozen=True)
class JQLResult:
    _raw: list[Any]  # Raw result data

    @property
    def raw(self) -> list[Any]:
        return self._raw

    @property
    def df(self) -> pd.DataFrame:
        # Handle list of dicts -> DataFrame
        # Handle list of values -> DataFrame with 'value' column
```

### Transformation Logic

```python
def _transform_jql(raw: list[Any]) -> JQLResult:
    return JQLResult(_raw=raw)
```

### Decision
- **Chosen**: Pass through raw data, let JQLResult handle DataFrame conversion
- **Rationale**: JQL is too flexible to have a fixed schema; the existing JQLResult already handles this
- **Note**: DataFrame conversion logic already exists in types.py

---

## 5. Error Handling

All API errors are already handled by `MixpanelAPIClient`:
- 401 → `AuthenticationError`
- 429 → `RateLimitError`
- 400/other → `QueryError`

The `LiveQueryService` will propagate these exceptions unchanged.

### Decision
- **Chosen**: No exception wrapping in LiveQueryService
- **Rationale**: Consistent with DiscoveryService and FetcherService patterns

---

## 6. Caching Strategy

### Decision
- **Chosen**: No caching in LiveQueryService
- **Rationale**: Live queries should always return fresh data. Caching is appropriate for discovery (schema rarely changes) but not for analytics queries (data changes constantly).
- **Alternative Considered**: Session-scoped caching like DiscoveryService - rejected because query results are time-sensitive

---

## Summary of Decisions

| Topic | Decision | Rationale |
|-------|----------|-----------|
| Segmentation total | Calculate from values | Sum all counts for accurate total |
| Funnel aggregation | Sum across all dates | Single result for date range |
| Funnel name | Empty string | Not in API response |
| Retention percentages | Calculate from counts/first | More useful than raw counts |
| JQL transformation | Pass through | Flexible schema |
| Error handling | Propagate unchanged | Consistent with existing services |
| Caching | None | Live data should be fresh |
