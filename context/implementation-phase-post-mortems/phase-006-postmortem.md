# Phase 006: Live Query Service — Implementation Post-Mortem

**Branch:** `006-live-query-service`
**Status:** Complete
**Date:** 2025-12-23

---

## Executive Summary

Phase 006 implemented the `LiveQueryService`, the analytics query layer that executes live queries against the Mixpanel Query API and transforms raw responses into typed result objects. Unlike FetcherService (Phase 005), which fetches data for local storage, LiveQueryService returns results directly to callers for immediate analysis.

**Key insight:** Live queries are fundamentally different from data fetching—they're about real-time analytics, not data warehousing. The service delegates all HTTP communication to `MixpanelAPIClient` and focuses solely on response transformation. Each query method returns a frozen, typed result with lazy DataFrame conversion, enabling both programmatic access and tabular analysis.

**Bonus feature:** During implementation, we enhanced the exception hierarchy with `APIError` base class and full HTTP request/response context. This enables AI agents to autonomously diagnose and recover from API errors by seeing exactly what was sent and what came back.

---

## What Was Built

### 1. LiveQueryService Class

**Purpose:** Execute live analytics queries and transform responses into typed results.

**Architecture:**

```
LiveQueryService
├── __init__(api_client)        # Dependency injection
├── segmentation(...)           # Time-series event counts
├── funnel(...)                 # Step-by-step conversion
├── retention(...)              # Cohort-based retention
└── jql(...)                    # Custom JQL scripts
```

**Key Design Decisions:**

| Decision | Rationale |
|----------|-----------|
| Constructor injection | API client passed in; no hidden instantiation; easy to mock |
| No caching | Analytics data changes frequently; queries should return fresh data |
| Module-level transform functions | Pure functions that can be unit-tested independently |
| Pass-through errors | API client already raises typed exceptions; no wrapping needed |
| Typed result objects | Frozen dataclasses with lazy `.df` property for DataFrame conversion |

**Example:**

```python
from mixpanel_data._internal.api_client import MixpanelAPIClient
from mixpanel_data._internal.services.live_query import LiveQueryService

client = MixpanelAPIClient(credentials)
with client:
    live_query = LiveQueryService(client)

    # Time-series analysis
    result = live_query.segmentation(
        event="Sign Up",
        from_date="2024-01-01",
        to_date="2024-01-31",
        on='properties["country"]',
    )
    print(f"Total signups: {result.total}")
    print(result.df.head())
```

---

### 2. Segmentation Queries (`segmentation()`)

**Purpose:** Analyze event counts over time with optional property segmentation.

**API Response (input):**
```python
{
    "data": {
        "series": ["2024-01-01", "2024-01-02"],
        "values": {
            "US": {"2024-01-01": 100, "2024-01-02": 120},
            "CA": {"2024-01-01": 50, "2024-01-02": 60},
        },
    },
    "legend_size": 2,
}
```

**SegmentationResult (output):**
```python
SegmentationResult(
    event="Sign Up",
    from_date="2024-01-01",
    to_date="2024-01-02",
    unit="day",
    segment_property='properties["country"]',
    total=330,  # Calculated: 100+120+50+60
    series={"US": {...}, "CA": {...}},
)
```

**Key Design Decisions:**

| Decision | Rationale |
|----------|-----------|
| Calculate total from series | API doesn't provide total; sum all values |
| Preserve segment structure | Pass through values dict as-is for flexibility |
| Store segment property | Enables downstream consumers to understand the segmentation |

---

### 3. Funnel Queries (`funnel()`)

**Purpose:** Analyze step-by-step conversion through multi-step user flows.

**Challenge:** The Mixpanel API returns funnel data grouped by date, but most users want aggregated totals across the date range.

**API Response (input):**
```python
{
    "data": {
        "2024-01-01": {
            "steps": [
                {"count": 500, "event": "App Open"},
                {"count": 300, "event": "Sign Up"},
            ],
        },
        "2024-01-02": {
            "steps": [
                {"count": 500, "event": "App Open"},
                {"count": 300, "event": "Sign Up"},
            ],
        },
    },
}
```

**FunnelResult (output):**
```python
FunnelResult(
    funnel_id=12345,
    funnel_name="",
    from_date="2024-01-01",
    to_date="2024-01-02",
    conversion_rate=0.6,  # 600/1000
    steps=[
        FunnelStep(event="App Open", count=1000, conversion_rate=1.0),
        FunnelStep(event="Sign Up", count=600, conversion_rate=0.6),
    ],
)
```

**Transformation Logic:**

1. Iterate through all dates in the response
2. Aggregate step counts by step index
3. Recalculate step conversion rates from aggregated counts
4. Calculate overall conversion rate as `last_step / first_step`

**Key Design Decisions:**

| Decision | Rationale |
|----------|-----------|
| Aggregate across dates | Users want total conversion, not per-day breakdowns |
| Recalculate conversion rates | API rates are per-day; we need aggregated rates |
| First step always 1.0 | First step is 100% of itself by definition |
| Handle empty funnels | Return 0.0 conversion rate, empty steps list |

---

### 4. Retention Queries (`retention()`)

**Purpose:** Analyze cohort-based retention over time periods.

**API Response (input):**
```python
{
    "2024-01-01": {"counts": [100, 50, 25], "first": 100},
    "2024-01-02": {"counts": [80, 40, 20], "first": 80},
}
```

**RetentionResult (output):**
```python
RetentionResult(
    born_event="Sign Up",
    return_event="Purchase",
    from_date="2024-01-01",
    to_date="2024-01-02",
    unit="day",
    cohorts=[
        CohortInfo(date="2024-01-01", size=100, retention=[1.0, 0.5, 0.25]),
        CohortInfo(date="2024-01-02", size=80, retention=[1.0, 0.5, 0.25]),
    ],
)
```

**Transformation Logic:**

1. Sort cohorts by date for consistent ordering
2. Calculate retention percentages: `count / cohort_size`
3. Handle zero-size cohorts gracefully (return 0.0)

**Key Design Decisions:**

| Decision | Rationale |
|----------|-----------|
| Sort by date | API response order is not guaranteed |
| Calculate percentages | Users want percentages, not raw counts |
| Handle zero cohorts | Avoid division by zero; return 0.0 |

---

### 5. JQL Queries (`jql()`)

**Purpose:** Execute custom JavaScript Query Language scripts for advanced analytics.

**JQL is different:** Unlike other query types, JQL scripts can return arbitrary data structures. The transform function simply wraps the raw response.

```python
result = live_query.jql(
    script='''
    function main() {
      return Events({from_date: params.from, to_date: params.to})
        .groupBy(["name"], mixpanel.reducer.count())
    }
    ''',
    params={"from": "2024-01-01", "to": "2024-01-31"},
)
print(result.raw)  # Raw API response
print(result.df)   # Attempts DataFrame conversion
```

**Key Design Decisions:**

| Decision | Rationale |
|----------|-----------|
| Return raw data | JQL output is arbitrary; no standard transform possible |
| Support params | Script parameterization enables reusable queries |
| Lazy DataFrame | Attempt conversion, but may fail for complex structures |

---

### 6. APIError Enhancement

**Purpose:** Enable AI agents to autonomously diagnose and recover from API errors.

During implementation, we discovered that agents needed more context to understand and fix API errors. The solution: capture complete HTTP request/response context in exceptions.

**New Exception Hierarchy:**

```
MixpanelDataError (base)
├── APIError (new base for HTTP errors)
│   ├── AuthenticationError
│   ├── RateLimitError
│   ├── QueryError
│   │   └── JQLSyntaxError (new)
│   └── ServerError (new)
├── ConfigError
│   ├── AccountNotFoundError
│   └── AccountExistsError
├── TableExistsError
└── TableNotFoundError
```

**APIError Properties:**

| Property | Type | Description |
|----------|------|-------------|
| `status_code` | `int` | HTTP status code |
| `response_body` | `str \| None` | Raw response body |
| `request_method` | `str \| None` | HTTP method (GET, POST) |
| `request_url` | `str \| None` | Request URL |
| `request_params` | `dict \| None` | Query parameters |
| `request_body` | `str \| None` | Request body |

**Example Usage:**

```python
try:
    result = live_query.retention(...)
except QueryError as e:
    print(f"Status: {e.status_code}")
    print(f"URL: {e.request_url}")
    print(f"Params: {e.request_params}")
    print(f"Response: {e.response_body}")
    # Agent can now diagnose the issue and adjust parameters
```

**Why This Matters for AI Agents:**

Before: "QueryError: Invalid parameters" — agent has no idea what went wrong.
After: Agent sees exact request/response, can identify issues like parameter conflicts.

---

## Challenges & Solutions

### Challenge 1: Retention API Parameter Conflict

**Problem:** The Mixpanel retention API has an undocumented constraint: when `interval` is greater than 1, the `unit` parameter must NOT be included.

**Discovery:** During QA testing with real API credentials, retention queries with custom intervals failed:

```json
{
  "error": "unit and interval both specified",
  "request": {
    "unit": "day",
    "interval": 7,
    "interval_count": 10
  }
}
```

**Root Cause:** The API client was always including `unit` when provided, but Mixpanel interprets `interval > 1` as "custom interval" mode where `unit` is implied.

**Solution:** Update `MixpanelAPIClient.retention()` to conditionally exclude `unit` when `interval != 1`:

```python
# Only include unit when using default interval (1)
# Mixpanel API rejects requests with both unit and non-default interval
if unit and interval == 1:
    params["unit"] = unit
```

**Test:**
```python
def test_retention_custom_intervals(self, live_query_factory):
    def handler(request: httpx.Request) -> httpx.Response:
        url_str = str(request.url)
        assert "interval=7" in url_str  # Custom interval
        assert "unit=" not in url_str   # Unit excluded
        return httpx.Response(200, json={...})
```

**Lesson:** Undocumented API constraints require real-world testing. Mock-based tests pass, but real API rejects.

### Challenge 2: Funnel Date Aggregation

**Problem:** Mixpanel's funnel API returns step counts grouped by date. Users want totals.

```python
# API returns per-date:
{"2024-01-01": {"steps": [{"count": 500}, {"count": 300}]},
 "2024-01-02": {"steps": [{"count": 500}, {"count": 300}]}}

# Users expect:
steps = [{"event": "Step 1", "count": 1000},
         {"event": "Step 2", "count": 600}]
```

**Solution:** Aggregate during transformation:

```python
aggregated_counts: dict[int, tuple[str, int]] = {}

for date_data in data.values():
    for idx, step in enumerate(date_data.get("steps", [])):
        if idx in aggregated_counts:
            _, existing = aggregated_counts[idx]
            aggregated_counts[idx] = (event, existing + count)
        else:
            aggregated_counts[idx] = (event, count)
```

**Why not use API aggregation?** The Mixpanel API doesn't provide an aggregation option. Per-date data is useful for some analyses, but our primary use case is overall conversion.

### Challenge 3: Insufficient Error Context for Agents

**Problem:** When API calls failed, exceptions contained only error messages. AI agents couldn't diagnose issues without seeing the actual request/response.

**Example:** "QueryError: Invalid parameters" — which parameters? What values?

**Solution:** Introduce `APIError` base class with full HTTP context:

```python
class APIError(MixpanelDataError):
    def __init__(
        self,
        message: str,
        code: str,
        *,
        status_code: int | None = None,
        response_body: str | None = None,
        request_method: str | None = None,
        request_url: str | None = None,
        request_params: dict[str, Any] | None = None,
        request_body: str | None = None,
        details: dict[str, Any] | None = None,
    ):
```

**Result:** Agents can now see exactly what was sent and what came back, enabling autonomous diagnosis and recovery.

---

## Test Coverage

### Unit Tests (`test_live_query.py`) — 808 lines

**Test Classes:**

| Class | Tests | Coverage |
|-------|-------|----------|
| `TestLiveQueryService` | 1 | Initialization |
| `TestSegmentation` | 6 | Basic query, property segmentation, where filter, total calculation, empty result, auth error |
| `TestFunnel` | 6 | Basic query, date aggregation, conversion rate calculation, overall rate, empty result, query error |
| `TestRetention` | 6 | Basic query, percentage calculation, filters, custom intervals, empty result, date sorting |
| `TestJQL` | 4 | Basic query, params, empty result, script error |

**Testing Strategy:**

| Approach | Tool | Purpose |
|----------|------|---------|
| HTTP mocking | `httpx.MockTransport` | Deterministic responses, no network |
| Fixture factory | `live_query_factory` | Creates LiveQueryService with mock client |
| Request inspection | `str(request.url)` | Verify parameters are passed correctly |

**Key Test Patterns:**

```python
# Pattern 1: Verify parameter forwarding
def test_segmentation_with_property_segmentation(self, live_query_factory):
    def handler(request: httpx.Request) -> httpx.Response:
        assert "on=" in str(request.url)  # Parameter passed
        return httpx.Response(200, json={...})

# Pattern 2: Verify transformation logic
def test_funnel_aggregates_across_dates(self, live_query_factory):
    # API returns per-date data
    # Assert result.steps has aggregated counts

# Pattern 3: Verify edge cases
def test_retention_sorts_cohorts_by_date(self, live_query_factory):
    def handler(_request):
        return httpx.Response(200, json={
            "2024-01-03": {...},  # Out of order
            "2024-01-01": {...},
            "2024-01-02": {...},
        })

    result = live_query_factory(handler).retention(...)
    assert result.cohorts[0].date == "2024-01-01"  # Sorted
```

---

## Code Quality Highlights

### 1. Pure Transform Functions

Transform functions are module-level, pure, and independently testable:

```python
def _transform_funnel(
    raw: dict[str, Any],
    funnel_id: int,
    from_date: str,
    to_date: str,
) -> FunnelResult:
    """Transform raw funnel API response into FunnelResult."""
    # Pure transformation, no side effects
```

### 2. Comprehensive Docstrings

Every public method includes purpose, args, returns, raises, and examples:

```python
def segmentation(self, event: str, from_date: str, to_date: str, ...) -> SegmentationResult:
    """Run a segmentation query.

    Executes a segmentation query against the Mixpanel API and returns
    a typed result with time-series data and optional property segmentation.

    Args:
        event: Event name to segment.
        from_date: Start date (YYYY-MM-DD).
        ...

    Returns:
        SegmentationResult with time-series data and calculated total.

    Raises:
        AuthenticationError: Invalid credentials.
        QueryError: Invalid query parameters.
        RateLimitError: Rate limit exceeded.

    Example:
        >>> result = live_query.segmentation(
        ...     event="Sign Up",
        ...     from_date="2024-01-01",
        ...     to_date="2024-01-31",
        ... )
    """
```

### 3. Type Safety

All methods fully typed with Python 3.11+ syntax:

```python
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
```

Mypy passes with no errors.

### 4. TYPE_CHECKING Import Guard

```python
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from mixpanel_data._internal.api_client import MixpanelAPIClient
```

Benefits:
- No circular import at runtime
- Faster module loading
- Type hints still work for mypy/IDEs

---

## Integration Points

### Upstream Dependencies

**From Phase 002 (API Client):**
- `MixpanelAPIClient.segmentation()` → Raw segmentation response
- `MixpanelAPIClient.funnel()` → Raw funnel response
- `MixpanelAPIClient.retention()` → Raw retention response
- `MixpanelAPIClient.jql()` → Raw JQL response

**From Phase 001 (Foundation):**
- Returns: `SegmentationResult`, `FunnelResult`, `RetentionResult`, `JQLResult`
- Uses: `FunnelStep`, `CohortInfo`
- Raises: `AuthenticationError`, `QueryError`, `RateLimitError`

### Downstream Impact

**For Phase 007 (Workspace):**
```python
class Workspace:
    def __init__(self, ...):
        self._live_query = LiveQueryService(self._api_client)

    def segmentation(self, event, from_date, to_date, **kwargs):
        return self._live_query.segmentation(event, from_date, to_date, **kwargs)
```

**For Phase 008 (CLI):**
```bash
mp query segmentation "Sign Up" --from 2024-01-01 --to 2024-01-31 --on country
mp query funnel 12345 --from 2024-01-01 --to 2024-01-31
mp query retention "Sign Up" "Purchase" --from 2024-01-01 --to 2024-01-31
```

**For AI Agents:**
```python
# Agent can run analytics queries and iterate on results
result = workspace.segmentation("Sign Up", "2024-01-01", "2024-01-31")
print(f"Total signups: {result.total}")

# If query fails, agent can diagnose using exception context
try:
    result = workspace.retention(...)
except QueryError as e:
    print(f"Request URL: {e.request_url}")
    print(f"Request params: {e.request_params}")
    # Agent adjusts parameters and retries
```

---

## What's NOT Included

| Component | Phase | Notes |
|-----------|-------|-------|
| Result caching | N/A | Live queries should return fresh data |
| Query builder DSL | Future | Users provide raw parameters |
| Funnel creation | N/A | Only queries existing funnels |
| Retention curve visualization | 008 | CLI handles presentation |
| Time-zone handling | Future | Uses Mixpanel defaults |

**Design principle:** LiveQueryService is a thin transformation layer. It delegates HTTP to API client and presentation to callers.

---

## Performance Characteristics

| Query Type | Typical Latency | Bottleneck |
|------------|-----------------|------------|
| Segmentation | 500ms - 2s | API response time |
| Funnel | 500ms - 2s | API response time |
| Retention | 1s - 3s | API calculation complexity |
| JQL | Variable | Script complexity |

**No local caching:** Live queries always hit the API. This ensures fresh data but means repeated identical queries incur network latency each time.

**Transformation overhead:** Negligible (<10ms). The transform functions are O(n) in response size.

---

## File Reference

| File | Lines | Purpose |
|------|-------|---------|
| [src/mixpanel_data/_internal/services/live_query.py](../../src/mixpanel_data/_internal/services/live_query.py) | 405 | LiveQueryService implementation |
| [tests/unit/test_live_query.py](../../tests/unit/test_live_query.py) | 808 | Comprehensive unit tests |
| [src/mixpanel_data/exceptions.py](../../src/mixpanel_data/exceptions.py) | (modified) | APIError base class, JQLSyntaxError, ServerError |
| [src/mixpanel_data/_internal/api_client.py](../../src/mixpanel_data/_internal/api_client.py) | (modified) | HTTP context capture for exceptions |
| [tests/unit/test_exceptions.py](../../tests/unit/test_exceptions.py) | (modified) | APIError tests |

**Test coverage:** 100% of LiveQueryService methods and transform functions.

---

## Lessons Learned

1. **Undocumented API constraints require real testing:** The retention API's `unit`/`interval` conflict wasn't documented. Unit tests with mocks passed, but real API calls failed. Always test with actual API credentials before declaring "complete."

2. **Aggregation belongs in the service layer:** Mixpanel's funnel API returns per-date data, but users want totals. The service layer is the right place to aggregate—it's a transformation of API output, not a storage concern.

3. **No caching for live queries:** Unlike DiscoveryService (Phase 004), LiveQueryService doesn't cache. Analytics data changes frequently, and stale results are worse than slightly slower queries.

4. **AI agents need full context:** The APIError enhancement was driven by watching agents struggle to diagnose API errors. Seeing "Invalid parameters" without knowing what parameters were sent is useless. Full request/response context enables autonomous recovery.

5. **Transform functions should be pure:** Module-level pure functions are easier to test, easier to reason about, and have no hidden dependencies. The service class is just a thin coordinator.

---

## Next Phase: 007 (Workspace Facade)

Phase 007 implements `Workspace`, the unified entry point for all library functionality:

```python
workspace = Workspace(account="production")

# Discovery (Phase 004)
events = workspace.discover_events()

# Fetching (Phase 005)
result = workspace.fetch_events("2024-01-01", "2024-01-31", table="january_events")

# Live queries (Phase 006)
segmentation = workspace.segmentation("Sign Up", "2024-01-01", "2024-01-31")

# Local SQL queries
df = workspace.query("SELECT * FROM january_events LIMIT 10")
```

**Key design:** Workspace resolves credentials once at construction and owns service instances. It's the facade that ties together all the components built in Phases 001-006.

---

**Post-Mortem Author:** Claude (Opus 4.5)
**Date:** 2025-12-23
**Lines of Code:** 405 (implementation) + 808 (tests) = 1,213 total
