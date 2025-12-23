# Phase 008: Query Service Enhancements — Implementation Plan

> Extends the Live Query Service with 6 additional Mixpanel Query API endpoints.

**Version:** 1.0
**Created:** 2024-12-23
**Status:** Planning
**Dependencies:** Phase 002 (API Client), Phase 006 (Live Query Service)
**Branch:** `008-query-service-enhancements`

---

## Overview

This phase enhances the Live Query Service with 6 new Query API methods that provide:

1. **User Activity Feeds** — View event history for specific users
2. **Saved Insights Reports** — Query pre-configured Insights reports by bookmark ID
3. **Event Frequency Analysis** — Understand how frequently users perform events
4. **Numeric Bucketing** — Segment events by numeric property ranges
5. **Numeric Aggregations** — Sum and average numeric properties over time

These capabilities complement the existing Live Query methods (segmentation, funnel, retention, jql, event_counts, property_counts) and complete the library's coverage of Mixpanel's analytics Query API.

---

## API Endpoints

### 1. Activity Feed — Profile Event Activity

**Endpoint:** `GET /api/query/stream/query`

Returns the activity feed for specified users, showing their recent event history.

**Parameters:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `distinct_ids` | string (JSON array) | Yes | JSON array of distinct_ids to return activity for |
| `from_date` | string | No | Start date (YYYY-MM-DD) |
| `to_date` | string | No | End date (YYYY-MM-DD) |

**Response Structure:**
```json
{
  "status": "ok",
  "results": {
    "events": [
      {
        "event": "Game Played",
        "properties": {
          "time": 1599589453,
          "$distinct_id": "user_123",
          "$browser": "Chrome",
          "$city": "Austin"
        }
      }
    ]
  }
}
```

**Use Cases:**
- View a user's complete activity history
- Debug user-specific issues
- Build user timelines for customer success

---

### 2. Insights — Query Saved Report

**Endpoint:** `GET /api/query/insights`

Get data from saved Insights reports by their bookmark ID.

**Parameters:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `bookmark_id` | integer | Yes | The ID of the Insights report (from URL) |

**Response Structure:**
```json
{
  "computed_at": "2020-09-21T16:35:41.252314+00:00",
  "date_range": {
    "from_date": "2020-08-31T00:00:00-07:00",
    "to_date": "2020-09-12T23:59:59.999000-07:00"
  },
  "headers": ["$event"],
  "series": {
    "Logged in": {
      "2020-08-31T00:00:00-07:00": 9852,
      "2020-09-07T00:00:00-07:00": 4325
    },
    "Viewed page": {
      "2020-08-31T00:00:00-07:00": 10246,
      "2020-09-07T00:00:00-07:00": 11432
    }
  }
}
```

**Use Cases:**
- Access pre-configured team reports programmatically
- Automate report data extraction
- Build dashboards from saved queries

---

### 3. Retention — Frequency Report

**Endpoint:** `GET /api/query/retention/addiction`

Analyze how frequently users perform an event within a time period.

**Parameters:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `from_date` | string | Yes | Start date (YYYY-MM-DD) |
| `to_date` | string | Yes | End date (YYYY-MM-DD) |
| `unit` | string | Yes | Overall period: "day", "week", or "month" |
| `addiction_unit` | string | Yes | Granularity: "hour" or "day" |
| `event` | string | No | Event name to analyze |
| `where` | string | No | Filter expression |
| `on` | string | No | Property to segment by |
| `limit` | integer | No | Max segmentation values |

**Response Structure:**
```json
{
  "data": {
    "2012-01-01": [305, 107, 60, 41, 32, 20, 12, 7, 4, 3, 3, 3, 2, 2, 2, 1, 1, 1, 1, 1, 1, 1, 1, 1],
    "2012-01-02": [495, 204, 117, 77, 53, 36, 26, 20, 12, 7, 4, 3, 3, 1, 1, 1, 1, 0, 0, 0, 0, 0, 0, 0]
  }
}
```

**Interpretation:**
- Each date maps to an array of user counts
- Index N shows users who performed the event in at least N+1 time periods
- Example: On 2012-01-02, 495 users did the event in at least 1 hour, 204 users did it in at least 2 hours

**Use Cases:**
- Measure user engagement depth
- Identify power users vs casual users
- Understand usage patterns (daily active vs occasional)

---

### 4. Segmentation — Numeric Bucketing

**Endpoint:** `GET /api/query/segmentation/numeric`

Segment events by a numeric property, automatically placing values into ranges/buckets.

**Parameters:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `event` | string | Yes | Event name |
| `from_date` | string | Yes | Start date (YYYY-MM-DD) |
| `to_date` | string | Yes | End date (YYYY-MM-DD) |
| `on` | string | Yes | Numeric property expression to bucket |
| `unit` | string | No | Time unit: "hour" or "day" (default: "day") |
| `where` | string | No | Filter expression |
| `type` | string | No | Counting: "general", "unique", "average" |

**Response Structure:**
```json
{
  "data": {
    "series": ["2011-08-08", "2011-08-09", "2011-08-06", "2011-08-07"],
    "values": {
      "2,000 - 2,100": {
        "2011-08-06": 1,
        "2011-08-07": 5,
        "2011-08-08": 4,
        "2011-08-09": 15
      },
      "2,100 - 2,200": {
        "2011-08-07": 2,
        "2011-08-08": 7,
        "2011-08-09": 15
      }
    }
  },
  "legend_size": 5
}
```

**Use Cases:**
- Analyze purchase amount distributions
- Segment users by session duration ranges
- Understand numeric property distributions

---

### 5. Segmentation — Numeric Sum

**Endpoint:** `GET /api/query/segmentation/sum`

Sum a numeric property's values for events per time unit.

**Parameters:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `event` | string | Yes | Event name |
| `from_date` | string | Yes | Start date (YYYY-MM-DD) |
| `to_date` | string | Yes | End date (YYYY-MM-DD) |
| `on` | string | Yes | Numeric expression to sum |
| `unit` | string | No | Time unit: "hour" or "day" (default: "day") |
| `where` | string | No | Filter expression |

**Response Structure:**
```json
{
  "status": "ok",
  "computed_at": "2019-10-07T23:02:11.666218+00:00",
  "results": {
    "2019-10-06": 7,
    "2019-10-07": 4
  }
}
```

**Use Cases:**
- Calculate daily revenue totals
- Sum items purchased per day
- Aggregate numeric metrics over time

---

### 6. Segmentation — Numeric Average

**Endpoint:** `GET /api/query/segmentation/average`

Average a numeric property's values for events per time unit.

**Parameters:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `event` | string | Yes | Event name |
| `from_date` | string | Yes | Start date (YYYY-MM-DD) |
| `to_date` | string | Yes | End date (YYYY-MM-DD) |
| `on` | string | Yes | Numeric expression to average |
| `unit` | string | No | Time unit: "hour" or "day" (default: "day") |
| `where` | string | No | Filter expression |

**Response Structure:**
```json
{
  "results": {
    "2011-08-06": 8.64705882352939,
    "2011-08-07": 4.640625,
    "2011-08-08": 3.6230899830221,
    "2011-08-09": 7.3353658536585
  },
  "status": "ok"
}
```

**Use Cases:**
- Calculate average order value per day
- Track average session duration trends
- Analyze average engagement metrics

---

## Implementation Design

### New Result Types

Add these frozen dataclasses to `src/mixpanel_data/types.py`:

#### `ActivityFeedResult`
```python
@dataclass(frozen=True)
class UserEvent:
    """Single event in a user's activity feed."""
    event: str
    time: datetime
    properties: dict[str, Any]

@dataclass(frozen=True)
class ActivityFeedResult:
    """Result of activity feed query for user(s)."""
    distinct_ids: list[str]
    from_date: str | None
    to_date: str | None
    events: list[UserEvent]

    # Lazy DataFrame: columns = event, time, distinct_id, + flattened properties
```

#### `InsightsResult`
```python
@dataclass(frozen=True)
class InsightsResult:
    """Result of saved Insights report query."""
    bookmark_id: int
    computed_at: str
    from_date: str
    to_date: str
    headers: list[str]
    series: dict[str, dict[str, int]]  # {event: {date: count}}

    # Lazy DataFrame: columns = date, event, count
```

#### `FrequencyResult`
```python
@dataclass(frozen=True)
class FrequencyResult:
    """Result of event frequency analysis."""
    event: str | None
    from_date: str
    to_date: str
    unit: Literal["day", "week", "month"]
    addiction_unit: Literal["hour", "day"]
    data: dict[str, list[int]]  # {date: [count_at_1, count_at_2, ...]}

    # Lazy DataFrame: columns = date, period_1, period_2, ... period_N
```

#### `NumericBucketResult`
```python
@dataclass(frozen=True)
class NumericBucketResult:
    """Result of numeric bucketing segmentation."""
    event: str
    from_date: str
    to_date: str
    property_expr: str  # The 'on' expression used
    unit: Literal["hour", "day"]
    series: dict[str, dict[str, int]]  # {bucket_range: {date: count}}

    # Lazy DataFrame: columns = date, bucket, count
```

#### `NumericSumResult`
```python
@dataclass(frozen=True)
class NumericSumResult:
    """Result of numeric sum aggregation."""
    event: str
    from_date: str
    to_date: str
    property_expr: str  # The 'on' expression summed
    unit: Literal["hour", "day"]
    results: dict[str, float]  # {date: sum_value}
    computed_at: str | None

    # Lazy DataFrame: columns = date, sum
```

#### `NumericAverageResult`
```python
@dataclass(frozen=True)
class NumericAverageResult:
    """Result of numeric average aggregation."""
    event: str
    from_date: str
    to_date: str
    property_expr: str  # The 'on' expression averaged
    unit: Literal["hour", "day"]
    results: dict[str, float]  # {date: average_value}

    # Lazy DataFrame: columns = date, average
```

### API Client Methods

Add to `src/mixpanel_data/_internal/api_client.py`:

```python
def activity_feed(
    self,
    distinct_ids: list[str],
    *,
    from_date: str | None = None,
    to_date: str | None = None,
) -> dict[str, Any]:
    """Get activity feed for specified users."""

def insights(
    self,
    bookmark_id: int,
) -> dict[str, Any]:
    """Get data from saved Insights report."""

def frequency(
    self,
    from_date: str,
    to_date: str,
    unit: str,
    addiction_unit: str,
    *,
    event: str | None = None,
    where: str | None = None,
    on: str | None = None,
    limit: int | None = None,
) -> dict[str, Any]:
    """Get event frequency data (addiction report)."""

def segmentation_numeric(
    self,
    event: str,
    from_date: str,
    to_date: str,
    on: str,
    *,
    unit: str = "day",
    where: str | None = None,
    type: str = "general",
) -> dict[str, Any]:
    """Get numerically bucketed segmentation data."""

def segmentation_sum(
    self,
    event: str,
    from_date: str,
    to_date: str,
    on: str,
    *,
    unit: str = "day",
    where: str | None = None,
) -> dict[str, Any]:
    """Get sum of numeric expression per time unit."""

def segmentation_average(
    self,
    event: str,
    from_date: str,
    to_date: str,
    on: str,
    *,
    unit: str = "day",
    where: str | None = None,
) -> dict[str, Any]:
    """Get average of numeric expression per time unit."""
```

### Live Query Service Methods

Add to `src/mixpanel_data/_internal/services/live_query.py`:

```python
def activity_feed(
    self,
    distinct_ids: list[str],
    *,
    from_date: str | None = None,
    to_date: str | None = None,
) -> ActivityFeedResult:
    """Query user activity feed.

    Returns event history for specified users within the date range.
    """

def insights(
    self,
    bookmark_id: int,
) -> InsightsResult:
    """Query saved Insights report.

    Returns time-series data from a pre-configured Insights report.
    """

def frequency(
    self,
    from_date: str,
    to_date: str,
    *,
    unit: Literal["day", "week", "month"] = "day",
    addiction_unit: Literal["hour", "day"] = "hour",
    event: str | None = None,
    where: str | None = None,
) -> FrequencyResult:
    """Analyze event frequency patterns.

    Shows how many users performed an event across N time periods.
    """

def segmentation_numeric(
    self,
    event: str,
    from_date: str,
    to_date: str,
    on: str,
    *,
    unit: Literal["hour", "day"] = "day",
    where: str | None = None,
    type: Literal["general", "unique", "average"] = "general",
) -> NumericBucketResult:
    """Segment events into numeric buckets.

    Automatically groups numeric property values into ranges.
    """

def segmentation_sum(
    self,
    event: str,
    from_date: str,
    to_date: str,
    on: str,
    *,
    unit: Literal["hour", "day"] = "day",
    where: str | None = None,
) -> NumericSumResult:
    """Sum numeric property values per time unit.

    Calculates running totals of a numeric expression.
    """

def segmentation_average(
    self,
    event: str,
    from_date: str,
    to_date: str,
    on: str,
    *,
    unit: Literal["hour", "day"] = "day",
    where: str | None = None,
) -> NumericAverageResult:
    """Average numeric property values per time unit.

    Calculates mean values of a numeric expression.
    """
```

---

## Transformation Logic

### Activity Feed Transformation

```python
def _transform_activity_feed(
    raw: dict[str, Any],
    distinct_ids: list[str],
    from_date: str | None,
    to_date: str | None,
) -> ActivityFeedResult:
    """Transform raw activity feed response."""
    results = raw.get("results", {})
    raw_events = results.get("events", [])

    events = []
    for e in raw_events:
        props = e.get("properties", {})
        # Convert Unix timestamp to datetime
        time_val = props.get("time")
        event_time = datetime.fromtimestamp(time_val, tz=timezone.utc) if time_val else None

        events.append(UserEvent(
            event=e.get("event", ""),
            time=event_time,
            properties=props,
        ))

    return ActivityFeedResult(
        distinct_ids=distinct_ids,
        from_date=from_date,
        to_date=to_date,
        events=events,
    )
```

### Insights Transformation

```python
def _transform_insights(
    raw: dict[str, Any],
    bookmark_id: int,
) -> InsightsResult:
    """Transform raw insights response."""
    date_range = raw.get("date_range", {})

    return InsightsResult(
        bookmark_id=bookmark_id,
        computed_at=raw.get("computed_at", ""),
        from_date=date_range.get("from_date", ""),
        to_date=date_range.get("to_date", ""),
        headers=raw.get("headers", []),
        series=raw.get("series", {}),
    )
```

### Frequency Transformation

```python
def _transform_frequency(
    raw: dict[str, Any],
    event: str | None,
    from_date: str,
    to_date: str,
    unit: str,
    addiction_unit: str,
) -> FrequencyResult:
    """Transform raw frequency/addiction response."""
    data = raw.get("data", raw)  # API may return with or without 'data' wrapper

    return FrequencyResult(
        event=event,
        from_date=from_date,
        to_date=to_date,
        unit=unit,  # type: ignore[arg-type]
        addiction_unit=addiction_unit,  # type: ignore[arg-type]
        data=data,
    )
```

---

## User Stories

### US-1: Query User Activity (P1)
**As an** AI coding agent analyzing user behavior
**I want to** retrieve a specific user's event history
**So that** I can debug issues or understand individual user journeys

**Acceptance Criteria:**
- Can query activity for 1 or more distinct_ids
- Can filter by date range
- Returns typed result with events as structured objects
- DataFrame has columns: event, time, distinct_id, plus property columns

### US-2: Access Saved Insights Reports (P2)
**As a** data analyst
**I want to** programmatically access pre-configured Insights reports
**So that** I can automate report data extraction

**Acceptance Criteria:**
- Can query any saved Insights report by bookmark_id
- Returns time-series data in typed result
- DataFrame has columns: date, event, count
- Includes metadata (computed_at, date_range)

### US-3: Analyze Event Frequency (P1)
**As an** AI coding agent measuring engagement
**I want to** understand how frequently users perform events
**So that** I can identify power users and engagement patterns

**Acceptance Criteria:**
- Can specify granularity (hour/day within day/week/month)
- Returns frequency distribution per date
- DataFrame pivots data for easy analysis
- Optional event filter and property segmentation

### US-4: Bucket Numeric Properties (P2)
**As a** data analyst
**I want to** segment events by numeric property ranges
**So that** I can understand value distributions

**Acceptance Criteria:**
- Automatically creates appropriate bucket ranges
- Returns time-series data per bucket
- DataFrame has columns: date, bucket, count
- Works with any numeric property expression

### US-5: Sum Numeric Values (P1)
**As an** AI coding agent tracking revenue
**I want to** sum numeric property values over time
**So that** I can calculate daily totals

**Acceptance Criteria:**
- Sums any numeric expression per time unit
- Returns simple date -> value mapping
- DataFrame has columns: date, sum
- Non-numeric values treated as 0.0

### US-6: Average Numeric Values (P1)
**As a** data analyst
**I want to** calculate average values over time
**So that** I can track mean metrics per day

**Acceptance Criteria:**
- Averages any numeric expression per time unit
- Returns simple date -> value mapping
- DataFrame has columns: date, average
- Non-numeric values treated as 0.0

---

## Testing Strategy

### Unit Tests

For each new method:
1. **Happy path** — Valid inputs return typed result
2. **DataFrame conversion** — Lazy `.df` property works correctly
3. **to_dict serialization** — All fields serialize properly
4. **Parameter validation** — Literal types enforced
5. **Empty response handling** — Graceful handling of no data

### Integration Tests (with mocked API)

1. **API client method tests** — Correct URL, params, auth
2. **Response parsing** — Handle real API response structures
3. **Error mapping** — 401, 400, 429 mapped correctly

### Test Fixtures

Create mock response fixtures for each endpoint based on OpenAPI examples.

---

## Tasks (Estimated: 35-40)

### Result Types (6 tasks)
- [ ] Create `UserEvent` dataclass
- [ ] Create `ActivityFeedResult` with lazy DataFrame
- [ ] Create `InsightsResult` with lazy DataFrame
- [ ] Create `FrequencyResult` with lazy DataFrame
- [ ] Create `NumericBucketResult` with lazy DataFrame
- [ ] Create `NumericSumResult` and `NumericAverageResult` with lazy DataFrames
- [ ] Update `__init__.py` exports

### API Client Methods (6 tasks)
- [ ] Implement `activity_feed()` method
- [ ] Implement `insights()` method
- [ ] Implement `frequency()` method
- [ ] Implement `segmentation_numeric()` method
- [ ] Implement `segmentation_sum()` method
- [ ] Implement `segmentation_average()` method

### Transformation Functions (6 tasks)
- [ ] Implement `_transform_activity_feed()`
- [ ] Implement `_transform_insights()`
- [ ] Implement `_transform_frequency()`
- [ ] Implement `_transform_numeric_bucket()`
- [ ] Implement `_transform_numeric_sum()`
- [ ] Implement `_transform_numeric_average()`

### Live Query Service Methods (6 tasks)
- [ ] Implement `activity_feed()` service method
- [ ] Implement `insights()` service method
- [ ] Implement `frequency()` service method
- [ ] Implement `segmentation_numeric()` service method
- [ ] Implement `segmentation_sum()` service method
- [ ] Implement `segmentation_average()` service method

### Unit Tests (12 tasks)
- [ ] Unit tests for ActivityFeedResult
- [ ] Unit tests for InsightsResult
- [ ] Unit tests for FrequencyResult
- [ ] Unit tests for NumericBucketResult
- [ ] Unit tests for NumericSumResult
- [ ] Unit tests for NumericAverageResult
- [ ] Unit tests for API client activity_feed
- [ ] Unit tests for API client insights
- [ ] Unit tests for API client frequency
- [ ] Unit tests for API client segmentation_numeric
- [ ] Unit tests for API client segmentation_sum/average
- [ ] Unit tests for Live Query Service new methods

### Quality Checks (3 tasks)
- [ ] mypy --strict passes
- [ ] ruff check passes
- [ ] All existing tests still pass

---

## Success Criteria

- [ ] All 6 new Live Query methods implemented
- [ ] All result types are frozen dataclasses with lazy `.df` and `.to_dict()`
- [ ] Literal types for parameters provide compile-time validation
- [ ] All API errors mapped to appropriate exceptions
- [ ] 90%+ test coverage for new code
- [ ] All 400+ existing tests continue to pass
- [ ] Documentation strings with examples for all public methods

---

## Dependencies

- **Phase 002 (API Client)**: HTTP request infrastructure
- **Phase 006 (Live Query Service)**: Existing patterns to follow

No changes needed to:
- Storage Engine (these are live queries only)
- Discovery Service (no new discovery endpoints)
- Fetcher Service (no new export endpoints)

---

## Non-Goals

This phase does NOT include:
- Workspace facade integration (Phase 009)
- CLI commands for new methods (Phase 010)
- Caching for any of these endpoints (live data)
- Profile/Engage query enhancements

---

## Appendix: Existing Patterns to Follow

### Result Type Pattern
```python
@dataclass(frozen=True)
class ExampleResult:
    """Brief description."""

    field: str
    """Field docstring."""

    _df_cache: pd.DataFrame | None = field(default=None, repr=False)

    @property
    def df(self) -> pd.DataFrame:
        """Convert to DataFrame."""
        if self._df_cache is not None:
            return self._df_cache
        # Build DataFrame...
        object.__setattr__(self, "_df_cache", result_df)
        return result_df

    def to_dict(self) -> dict[str, Any]:
        """Serialize for JSON output."""
        return {...}
```

### API Client Method Pattern
```python
def method_name(
    self,
    required_param: str,
    *,
    optional_param: str | None = None,
) -> dict[str, Any]:
    """Brief description.

    Args:
        required_param: Description.
        optional_param: Description.

    Returns:
        Raw API response dictionary.

    Raises:
        AuthenticationError: Invalid credentials.
        QueryError: Invalid parameters.
        RateLimitError: Rate limit exceeded.
    """
    url = self._build_url("query", "/path")
    params: dict[str, Any] = {"required": required_param}
    if optional_param:
        params["optional"] = optional_param
    result: dict[str, Any] = self._request("GET", url, params=params)
    return result
```

### Live Query Service Method Pattern
```python
def method_name(
    self,
    required_param: str,
    *,
    typed_param: Literal["a", "b"] = "a",
) -> ResultType:
    """Brief description.

    Detailed explanation of what this query does.

    Args:
        required_param: Description.
        typed_param: Description with valid values.

    Returns:
        ResultType with data and lazy DataFrame.

    Raises:
        AuthenticationError: Invalid credentials.
        QueryError: Invalid parameters.
        RateLimitError: Rate limit exceeded.

    Example:
        >>> result = live_query.method_name(...)
        >>> print(result.df.head())
    """
    raw = self._api_client.method_name(
        required_param=required_param,
        typed_param=typed_param,
    )
    return _transform_method_name(raw, required_param, typed_param)
```
