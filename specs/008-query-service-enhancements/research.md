# Research: Query Service Enhancements

**Date**: 2024-12-23
**Feature**: 008-query-service-enhancements
**Status**: Complete

## Overview

This research consolidates decisions for extending LiveQueryService with 6 new Mixpanel Query API endpoints. Since this phase follows established patterns from Phase 006, most decisions are straightforward pattern applications.

---

## API Endpoint Research

### 1. Activity Feed Endpoint

**Decision**: Use `GET /api/query/stream/query` with JSON-encoded distinct_ids array

**Rationale**:
- Endpoint documented in Mixpanel Query API
- Returns user event history with nested properties
- Supports optional date range filtering

**Alternatives Considered**:
- Raw export API: Rejected - requires full date range, not user-specific
- JQL: Rejected - more complex, activity feed is purpose-built

**Implementation Notes**:
- `distinct_ids` parameter must be JSON-encoded array
- Response has nested structure: `results.events[]`
- Timestamps are Unix epoch integers requiring conversion

---

### 2. Insights Endpoint

**Decision**: Use `GET /api/query/insights` with integer bookmark_id

**Rationale**:
- Simple single-parameter endpoint
- Returns pre-computed report data with metadata
- Bookmark ID matches Mixpanel UI URL pattern

**Alternatives Considered**:
- None - this is the only way to access saved Insights reports

**Implementation Notes**:
- Response includes `computed_at` for cache validation
- Date range in response uses ISO format with timezone
- Series data keyed by event name, then by date string

---

### 3. Frequency (Addiction) Endpoint

**Decision**: Use `GET /api/query/retention/addiction` with dual unit parameters

**Rationale**:
- Unique two-level granularity: `unit` for period, `addiction_unit` for measurement
- Returns frequency distribution as arrays per date
- Supports optional event filtering and segmentation

**Alternatives Considered**:
- JQL with custom aggregation: Rejected - addiction endpoint is purpose-built

**Implementation Notes**:
- `unit`: "day", "week", "month" - defines the overall time period
- `addiction_unit`: "hour", "day" - defines measurement granularity
- Response arrays: index N = users active in N+1 time periods
- Array length varies based on `addiction_unit` (24 for hour, varies for day)

---

### 4. Segmentation Numeric Endpoint

**Decision**: Use `GET /api/query/segmentation/numeric` with property expression

**Rationale**:
- API automatically determines bucket ranges
- Returns time-series data per bucket
- Supports standard segmentation parameters

**Alternatives Considered**:
- Manual bucketing in JQL: Rejected - API auto-bucketing is more robust
- Standard segmentation with WHERE: Rejected - less flexible for distributions

**Implementation Notes**:
- `on` parameter takes property expression (e.g., `properties["amount"]`)
- Bucket ranges returned as formatted strings (e.g., "2,000 - 2,100")
- `type` parameter: "general" (all), "unique" (users), "average"

---

### 5. Segmentation Sum Endpoint

**Decision**: Use `GET /api/query/segmentation/sum` with property expression

**Rationale**:
- Purpose-built for numeric aggregation
- Returns simple date-to-value mapping
- Includes `computed_at` metadata

**Alternatives Considered**:
- JQL with reduce: Rejected - sum endpoint is more efficient

**Implementation Notes**:
- `on` parameter takes numeric expression to sum
- Response format: `{results: {date: sum_value}}`
- Non-numeric values contribute 0 (handled by API)

---

### 6. Segmentation Average Endpoint

**Decision**: Use `GET /api/query/segmentation/average` with property expression

**Rationale**:
- Identical interface to sum endpoint
- Returns mean values per time period
- Handles non-numeric exclusion automatically

**Alternatives Considered**:
- None - direct API endpoint is optimal

**Implementation Notes**:
- Same parameters as sum endpoint
- Response format: `{results: {date: avg_value}, status: "ok"}`
- Excludes non-numeric values from calculation (API behavior)

---

## Result Type Decisions

### DataFrame Column Naming

**Decision**: Use consistent column naming across all new result types

| Result Type | DataFrame Columns |
|-------------|-------------------|
| ActivityFeedResult | event, time, distinct_id, + flattened properties |
| InsightsResult | date, event, count |
| FrequencyResult | date, period_1, period_2, ... period_N |
| NumericBucketResult | date, bucket, count |
| NumericSumResult | date, sum |
| NumericAverageResult | date, average |

**Rationale**: Consistent with existing result types (SegmentationResult uses date, segment, count)

---

### Timestamp Handling

**Decision**: Convert Unix timestamps to datetime objects in UserEvent

**Rationale**:
- Activity feed returns Unix epoch integers
- Consistent with Python datetime conventions
- Enables proper DataFrame datetime indexing

**Implementation**:
```python
from datetime import datetime, timezone
event_time = datetime.fromtimestamp(props.get("time"), tz=timezone.utc)
```

---

### Literal Type Parameters

**Decision**: Use Literal types for all enum-like parameters

| Method | Parameter | Literal Type |
|--------|-----------|--------------|
| frequency | unit | `Literal["day", "week", "month"]` |
| frequency | addiction_unit | `Literal["hour", "day"]` |
| segmentation_numeric | unit | `Literal["hour", "day"]` |
| segmentation_numeric | type | `Literal["general", "unique", "average"]` |
| segmentation_sum | unit | `Literal["hour", "day"]` |
| segmentation_average | unit | `Literal["hour", "day"]` |

**Rationale**: Compile-time validation per constitution; consistent with Phase 007 pattern

---

## Testing Strategy

### Mock Response Fixtures

**Decision**: Create JSON fixtures matching actual API response structures

**Rationale**:
- Enables repeatable unit tests
- Documents expected API behavior
- Isolates tests from network

**Fixture Files**:
- `activity_feed.json` - Multi-user event history
- `insights.json` - Saved report with multiple events
- `frequency.json` - Frequency distribution arrays
- `segmentation_numeric.json` - Bucketed time series
- `segmentation_sum.json` - Sum aggregation
- `segmentation_average.json` - Average aggregation

---

### Test Coverage

**Decision**: Minimum test coverage per method

| Test Category | Tests per Method |
|---------------|------------------|
| Happy path | 1 |
| DataFrame conversion | 1 |
| to_dict serialization | 1 |
| Empty response | 1 |
| Parameter validation | 1 (for Literal types) |

**Total**: ~30 tests for result types + ~10 tests for API client + ~10 tests for service

---

## Best Practices Applied

### From Phase 006 (Live Query Service)

1. **Transformation Functions**: Private module-level functions for API → Result conversion
2. **Lazy DataFrame**: Cache via `object.__setattr__` on frozen dataclass
3. **Type Ignores**: Use `# type: ignore[arg-type]` for Literal assignment from API strings
4. **Docstrings**: Google style with Args, Returns, Raises, Example sections

### From Phase 007 (Discovery Enhancements)

1. **Literal Types**: Strict typing for enum-like parameters
2. **Series Data Structure**: `dict[str, dict[str, int|float]]` for time-series
3. **Result Type Pattern**: Frozen dataclass with _df_cache field

---

## Dependencies Verified

| Dependency | Status | Notes |
|------------|--------|-------|
| Phase 002 (API Client) | Available | HTTP infrastructure ready |
| Phase 006 (Live Query) | Available | Patterns established |
| httpx | Installed | HTTP client |
| pandas | Installed | DataFrame support |
| Pydantic v2 | Installed | Validation (for Credentials) |

---

## Risks and Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| API response format differs from docs | Low | Medium | Validate against actual API in integration tests |
| Rate limiting on activity feed | Medium | Low | Use existing backoff infrastructure |
| Large activity feed responses | Medium | Low | Users can limit with date range |

---

## Conclusion

All research items resolved. Implementation can proceed using established patterns from Phases 006 and 007. No blocking issues or clarifications needed.
