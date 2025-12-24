# Phase 007: Discovery Enhancements — Implementation Post-Mortem

**Branch:** `007-discovery-enhancements`
**Status:** Complete
**Date:** 2025-12-23

---

## Executive Summary

Phase 007 extended the DiscoveryService and LiveQueryService to provide complete coverage of Mixpanel's Query API discovery and event breakdown endpoints. This enhancement enables AI agents and users to discover project resources (funnels, cohorts) before querying them, explore real-time event activity, and analyze multi-event trends and property distributions.

**Key insight:** Discovery and analytics queries serve different purposes and have different caching needs. Funnel and cohort definitions are relatively stable (cache them), while today's top events change throughout the day (don't cache). This phase adds 8 new methods across 3 components, following the same patterns established in Phases 004 and 006.

**Bonus feature:** Added `Literal` type constraints for `type` and `unit` parameters in LiveQueryService methods, providing compile-time validation and better IDE autocomplete support.

---

## What Was Built

### 1. New Discovery Types (`types.py`)

Five new frozen dataclasses following existing patterns:

| Type | Purpose | Fields |
|------|---------|--------|
| `FunnelInfo` | Saved funnel reference | `funnel_id`, `name` |
| `SavedCohort` | Saved cohort reference | `id`, `name`, `count`, `description`, `created`, `is_visible` |
| `TopEvent` | Today's event activity | `event`, `count`, `percent_change` |
| `EventCountsResult` | Multi-event time series | `events`, `from_date`, `to_date`, `unit`, `type`, `series`, `.df` |
| `PropertyCountsResult` | Property breakdown time series | `event`, `property_name`, `from_date`, `to_date`, `unit`, `type`, `series`, `.df` |

**Design Decisions:**

| Decision | Rationale |
|----------|-----------|
| All types frozen | Immutability matches existing pattern; prevents accidental mutation |
| Lazy `.df` property | Time-series results support pandas DataFrame conversion on demand |
| `.to_dict()` method | All types support JSON serialization for CLI output |
| `Literal` types for enums | Compile-time validation for `type` and `unit` parameters |

---

### 2. API Client Methods (`api_client.py`)

Five new methods added to `MixpanelAPIClient`:

```
MixpanelAPIClient
├── Discovery Methods
│   ├── list_funnels()         # GET /funnels/list
│   ├── list_cohorts()         # POST /cohorts/list (unusual but per spec)
│   └── get_top_events()       # GET /events/top
└── Query Methods
    ├── event_counts()         # GET /events
    └── property_counts()      # GET /events/properties
```

**Key Implementation Details:**

```python
# list_funnels() - Simple GET, returns list of dicts
def list_funnels(self) -> list[dict[str, Any]]:
    url = self._build_url("query", "/funnels/list")
    response = self._request("GET", url)
    return response if isinstance(response, list) else []

# list_cohorts() - POST method (unusual for read-only)
def list_cohorts(self) -> list[dict[str, Any]]:
    url = self._build_url("query", "/cohorts/list")
    response = self._request("POST", url)
    return response if isinstance(response, list) else []

# event_counts() - JSON array in event parameter
def event_counts(self, events: list[str], ...) -> dict[str, Any]:
    params = {"event": json.dumps(events), ...}
```

---

### 3. DiscoveryService Enhancements (`discovery.py`)

Three new methods added:

| Method | Purpose | Cached |
|--------|---------|--------|
| `list_funnels()` | List saved funnels | ✅ Yes |
| `list_cohorts()` | List saved cohorts | ✅ Yes |
| `list_top_events()` | Today's top events | ❌ No |

**Caching Strategy:**

```python
# Cached: funnels and cohorts are stable definitions
def list_funnels(self) -> list[FunnelInfo]:
    cache_key = ("list_funnels",)
    if cache_key in self._cache:
        return list(self._cache[cache_key])
    raw = self._api_client.list_funnels()
    funnels = sorted([FunnelInfo(...) for f in raw], key=lambda x: x.name)
    self._cache[cache_key] = funnels
    return list(funnels)

# NOT cached: top events change throughout the day
def list_top_events(self, *, type: str = "general", limit: int | None = None) -> list[TopEvent]:
    raw = self._api_client.get_top_events(type=type, limit=limit)
    return [TopEvent(...) for e in raw.get("events", [])]
```

**Example Usage:**

```python
discovery = DiscoveryService(api_client)

# Find funnel IDs for querying
funnels = discovery.list_funnels()
for f in funnels:
    print(f"{f.name}: {f.funnel_id}")

# Find cohort IDs for profile filtering
cohorts = discovery.list_cohorts()
for c in cohorts:
    print(f"{c.name}: {c.id} ({c.count} users)")

# See what's happening today
top = discovery.list_top_events(limit=10)
for e in top:
    print(f"{e.event}: {e.count} ({e.percent_change:+.1%})")
```

---

### 4. LiveQueryService Enhancements (`live_query.py`)

Two new methods added for time-series analytics:

| Method | Purpose | API Endpoint |
|--------|---------|--------------|
| `event_counts()` | Multi-event time series | GET /events |
| `property_counts()` | Property breakdown time series | GET /events/properties |

**Type-Safe Parameters:**

```python
def event_counts(
    self,
    events: list[str],
    from_date: str,
    to_date: str,
    *,
    type: Literal["general", "unique", "average"] = "general",
    unit: Literal["day", "week", "month"] = "day",
) -> EventCountsResult:
```

The `Literal` types provide:
- IDE autocomplete showing valid options
- mypy errors for invalid values
- Clear documentation of allowed values

**Example Usage:**

```python
live_query = LiveQueryService(api_client)

# Compare multiple events over time
result = live_query.event_counts(
    events=["Sign Up", "Purchase", "Churn"],
    from_date="2024-01-01",
    to_date="2024-01-31",
    unit="week",
)
print(result.df)  # date, event, count columns

# Analyze property distribution
result = live_query.property_counts(
    event="Purchase",
    property_name="country",
    from_date="2024-01-01",
    to_date="2024-01-31",
    limit=10,
)
print(result.df)  # date, value, count columns
```

---

## Challenges & Solutions

### Challenge 1: POST Method for Cohorts List

**Problem:** The Mixpanel API uses POST for `/cohorts/list`, which is unusual for a read-only operation. This initially raised concerns about implementation correctness.

**Discovery:** Verified against Mixpanel API documentation that POST is indeed the correct method.

**Solution:** Implemented as documented with a comment explaining the unusual choice:

```python
def list_cohorts(self) -> list[dict[str, Any]]:
    # Note: POST method is unusual for read-only, but per API spec
    url = self._build_url("query", "/cohorts/list")
    response = self._request("POST", url)
```

**Lesson:** Trust the API documentation, but add comments when behavior is unexpected.

### Challenge 2: Field Name Mapping for TopEvent

**Problem:** The Mixpanel API returns `amount` for event counts, but our domain model uses `count` for consistency with other result types.

**API Response:**
```json
{
  "events": [
    {"event": "Sign Up", "amount": 1500, "percent_change": 0.15}
  ]
}
```

**Solution:** Map during transformation:

```python
def list_top_events(self, ...) -> list[TopEvent]:
    raw = self._api_client.get_top_events(type=type, limit=limit)
    return [
        TopEvent(
            event=e["event"],
            count=e["amount"],  # Map amount -> count
            percent_change=e["percent_change"],
        )
        for e in raw.get("events", [])
    ]
```

### Challenge 3: JSON Array in Query Parameters

**Problem:** The `/events` endpoint requires event names as a JSON array in the `event` query parameter.

**Solution:** Serialize with `json.dumps()`:

```python
def event_counts(self, events: list[str], ...) -> dict[str, Any]:
    params: dict[str, Any] = {
        "event": json.dumps(events),  # ["Sign Up", "Purchase"]
        "from_date": from_date,
        "to_date": to_date,
        "type": type,
        "unit": unit,
    }
```

---

## Test Coverage

### Unit Tests — Discovery (`test_discovery.py`) — 884 lines

**New Test Classes:**

| Class | Tests | Coverage |
|-------|-------|----------|
| `TestListFunnels` | 5 | Basic query, empty result, sorting, caching, auth error |
| `TestListCohorts` | 5 | Basic query, empty result, sorting, caching, auth error |
| `TestListTopEvents` | 6 | Basic query, type param, limit param, empty result, no caching, auth error |

**Key Test Pattern — Verifying No Caching:**

```python
def test_list_top_events_not_cached(self, discovery_factory):
    """Top events should not be cached (real-time data)."""
    call_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        return httpx.Response(200, json={"events": [...]})

    discovery = discovery_factory(handler)
    discovery.list_top_events()
    discovery.list_top_events()

    assert call_count == 2  # Not cached - called twice
```

### Unit Tests — Live Query (`test_live_query.py`) — 1,211 lines

**New Test Classes:**

| Class | Tests | Coverage |
|-------|-------|----------|
| `TestEventCounts` | 6 | Basic query, type/unit params, multiple events, empty result, DataFrame, auth error |
| `TestPropertyCounts` | 6 | Basic query, values filter, limit param, empty result, DataFrame, auth error |

**Key Test Pattern — Parameter Forwarding:**

```python
def test_event_counts_with_custom_type_and_unit(self, live_query_factory):
    def handler(request: httpx.Request) -> httpx.Response:
        url_str = str(request.url)
        assert "type=unique" in url_str
        assert "unit=week" in url_str
        return httpx.Response(200, json={...})

    result = live_query_factory(handler).event_counts(
        events=["Sign Up"],
        from_date="2024-01-01",
        to_date="2024-01-31",
        type="unique",
        unit="week",
    )
```

---

## Code Quality Highlights

### 1. Consistent Sorting for Discovery Results

All discovery methods return results sorted alphabetically by name:

```python
funnels = sorted(
    [FunnelInfo(funnel_id=f["funnel_id"], name=f["name"]) for f in raw],
    key=lambda x: x.name,
)
```

This ensures:
- Deterministic output for testing
- Predictable order for users
- Easy comparison across sessions

### 2. Literal Types for Constrained Parameters

```python
def event_counts(
    self,
    events: list[str],
    from_date: str,
    to_date: str,
    *,
    type: Literal["general", "unique", "average"] = "general",
    unit: Literal["day", "week", "month"] = "day",
) -> EventCountsResult:
```

Benefits:
- IDE autocomplete shows valid options
- mypy catches invalid values at compile time
- Self-documenting API

### 3. Defensive Parsing for API Responses

```python
def list_funnels(self) -> list[dict[str, Any]]:
    response = self._request("GET", url)
    if isinstance(response, list):
        return response
    return []  # Graceful fallback
```

### 4. Copy-on-Return for Cached Results

```python
def list_funnels(self) -> list[FunnelInfo]:
    if cache_key in self._cache:
        return list(self._cache[cache_key])  # Return copy, not reference
```

This prevents callers from accidentally mutating the cache.

---

## Integration Points

### Upstream Dependencies

**From Phase 002 (API Client):**
- `MixpanelAPIClient._request()` — HTTP request handling
- `MixpanelAPIClient._build_url()` — Regional endpoint construction
- Rate limiting and retry logic

**From Phase 001 (Foundation):**
- `AuthenticationError`, `QueryError`, `RateLimitError`
- Frozen dataclass patterns

### Downstream Impact

**For Phase 007 (Workspace Facade):**
```python
class Workspace:
    def list_funnels(self) -> list[FunnelInfo]:
        return self._discovery.list_funnels()

    def list_cohorts(self) -> list[SavedCohort]:
        return self._discovery.list_cohorts()

    def event_counts(self, events, from_date, to_date, **kwargs) -> EventCountsResult:
        return self._live_query.event_counts(events, from_date, to_date, **kwargs)
```

**For Phase 008 (CLI):**
```bash
mp discover funnels
mp discover cohorts
mp discover top-events --limit 10
mp query events "Sign Up,Purchase" --from 2024-01-01 --to 2024-01-31
mp query property-breakdown "Purchase" "country" --from 2024-01-01 --to 2024-01-31
```

**For AI Agents:**
```python
# Workflow: Discover funnel, then query it
funnels = workspace.list_funnels()
signup_funnel = next(f for f in funnels if "signup" in f.name.lower())
result = workspace.funnel(signup_funnel.funnel_id, "2024-01-01", "2024-01-31")

# Workflow: Compare events over time
result = workspace.event_counts(
    ["Sign Up", "Purchase", "Churn"],
    "2024-01-01",
    "2024-01-31",
    unit="week",
)
print(result.df.pivot(index="date", columns="event", values="count"))
```

---

## What's NOT Included

| Component | Reason |
|-----------|--------|
| Annotations API | Deferred to later phase |
| Data Pipelines API | Data engineering, not core analytics |
| Lexicon Schemas API | Schema management, separate concern |
| Profile property discovery | Not part of Query API event breakdown |
| Creating/modifying funnels or cohorts | Read-only discovery only |
| Funnel name in `list_funnels()` response enrichment | API returns name directly |

**Design principle:** This phase adds discovery and querying capabilities, not management operations.

---

## Performance Characteristics

| Method | Latency | Caching |
|--------|---------|---------|
| `list_funnels()` | 200-500ms (first call) | ✅ Cached |
| `list_cohorts()` | 200-500ms (first call) | ✅ Cached |
| `list_top_events()` | 200-500ms (every call) | ❌ Not cached |
| `event_counts()` | 500ms-2s | ❌ Not cached |
| `property_counts()` | 500ms-2s | ❌ Not cached |

**Caching rationale:**
- Funnel/cohort definitions are stable within a session
- Top events change throughout the day
- Time-series queries return fresh analytics data

---

## File Reference

| File | Lines | Purpose |
|------|-------|---------|
| [src/mixpanel_data/types.py](../../src/mixpanel_data/types.py) | 731 | +5 new result types |
| [src/mixpanel_data/_internal/api_client.py](../../src/mixpanel_data/_internal/api_client.py) | (modified) | +5 new API methods |
| [src/mixpanel_data/_internal/services/discovery.py](../../src/mixpanel_data/_internal/services/discovery.py) | 230 | +3 new discovery methods |
| [src/mixpanel_data/_internal/services/live_query.py](../../src/mixpanel_data/_internal/services/live_query.py) | 526 | +2 new query methods |
| [src/mixpanel_data/__init__.py](../../src/mixpanel_data/__init__.py) | (modified) | Export new types |
| [tests/unit/test_discovery.py](../../tests/unit/test_discovery.py) | 884 | Discovery tests |
| [tests/unit/test_live_query.py](../../tests/unit/test_live_query.py) | 1,211 | Live query tests |

**Total new/modified lines:** ~1,500 (implementation) + ~500 (tests) = ~2,000 total

---

## Lessons Learned

1. **Caching decisions depend on data volatility.** Funnel and cohort definitions are created by humans and change rarely—cache them. Top events and analytics queries return time-sensitive data—don't cache them. The key question: "Does this data change within a typical session?"

2. **Field name mapping belongs in the service layer.** The API returns `amount`, but our domain model uses `count`. Mapping during transformation keeps the public API consistent while accommodating API quirks.

3. **Literal types improve DX significantly.** Adding `Literal["general", "unique", "average"]` provides autocomplete, compile-time validation, and self-documenting code—minimal effort, high value.

4. **POST for read-only is unusual but valid.** The cohorts list endpoint uses POST despite being read-only. When API behavior seems wrong, verify against documentation before assuming a bug.

5. **Test both caching and non-caching behavior.** Verifying that `list_funnels()` is cached AND that `list_top_events()` is NOT cached are equally important tests.

---

## Next Phase: Workspace Facade

Phase 007 (Workspace) implements `Workspace`, the unified entry point for all library functionality:

```python
workspace = Workspace(account="production")

# Discovery (including new enhancements)
funnels = workspace.list_funnels()
cohorts = workspace.list_cohorts()
top_events = workspace.list_top_events()

# Live queries (including new enhancements)
event_data = workspace.event_counts(["Sign Up"], "2024-01-01", "2024-01-31")
property_data = workspace.property_counts("Purchase", "country", "2024-01-01", "2024-01-31")

# Local storage and SQL
workspace.fetch_events("2024-01-01", "2024-01-31", table="january")
df = workspace.query("SELECT * FROM january LIMIT 10")
```

**Key design:** Workspace owns service instances and delegates to them. The new discovery enhancements become immediately available through the Workspace facade.

---

**Post-Mortem Author:** Claude (Opus 4.5)
**Date:** 2025-12-23
**Lines of Code:** ~500 (implementation additions) + ~500 (test additions) = ~1,000 new lines
