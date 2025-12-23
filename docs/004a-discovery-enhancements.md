# Implementation Plan: Discovery & Query API Enhancements

**Phase**: 004a (Discovery Service Enhancement) + 006a (Live Query Enhancement)
**Status**: Planning
**Created**: 2025-12-23
**Input**: Extend Discovery Service to cover all Event Breakdown APIs plus funnel/cohort listing

---

## Overview

This implementation plan extends the existing Discovery Service (Phase 004) and Live Query Service (Phase 006) to provide complete coverage of Mixpanel's Query API discovery and event breakdown endpoints. The enhancement enables AI agents and users to:

1. **Discover project resources** — List saved funnels and cohorts before querying them
2. **Explore event activity** — See today's most active events with volume and trend data
3. **Analyze multi-event trends** — Query time-series counts for multiple events simultaneously
4. **Analyze property distributions** — Query time-series breakdowns by property values

---

## API Endpoint Coverage

### Event Breakdown APIs (6 total)

| Endpoint | API Name | Current | After |
|----------|----------|---------|-------|
| `/events/names` | Top Events (31 days) | `list_events()` | ✅ No change |
| `/events/top` | Today's Top Events | ❌ Missing | `list_top_events()` |
| `/events` | Aggregate Event Counts | ❌ Missing | `event_counts()` |
| `/events/properties/top` | Top Event Properties | `list_properties()` | ✅ No change |
| `/events/properties/values` | Top Property Values | `list_property_values()` | ✅ No change |
| `/events/properties` | Aggregated Property Values | ❌ Missing | `property_counts()` |

### Additional Discovery APIs

| Endpoint | API Name | Method | Purpose |
|----------|----------|--------|---------|
| `/funnels/list` | List Saved Funnels | GET | Discover funnel_ids for `funnel()` queries |
| `/cohorts/list` | List Saved Cohorts | POST* | Discover cohort_ids for profile filtering |

*Note: POST method is unusual but documented in Mixpanel API spec.

---

## User Scenarios & Acceptance Criteria

### US-1: Discover Available Funnels (P1)

**As** an AI coding agent or analyst, **I want** to list all saved funnels in a project **so that** I can identify funnel IDs to use with `funnel()` queries.

**Acceptance Criteria:**
1. **Given** valid credentials, **When** I call `list_funnels()`, **Then** I receive a list of `FunnelInfo` objects sorted alphabetically by name.
2. **Given** a project with no saved funnels, **When** I call `list_funnels()`, **Then** I receive an empty list (not an error).
3. **Given** valid credentials, **When** I call `list_funnels()` multiple times, **Then** subsequent calls return cached results without additional network requests.
4. **Given** each `FunnelInfo`, **Then** it contains `funnel_id` (int) and `name` (str).

**Testable Independently:** Yes — mock API response, verify transformation and caching.

---

### US-2: Discover Available Cohorts (P1)

**As** an AI coding agent or analyst, **I want** to list all saved cohorts in a project **so that** I can identify cohort IDs to use for profile filtering via the Engage API.

**Acceptance Criteria:**
1. **Given** valid credentials, **When** I call `list_cohorts()`, **Then** I receive a list of `SavedCohort` objects sorted alphabetically by name.
2. **Given** a project with no saved cohorts, **When** I call `list_cohorts()`, **Then** I receive an empty list.
3. **Given** valid credentials, **When** I call `list_cohorts()` multiple times, **Then** subsequent calls return cached results.
4. **Given** each `SavedCohort`, **Then** it contains: `id` (int), `name` (str), `count` (int), `description` (str), `created` (str), `is_visible` (bool).

**Testable Independently:** Yes — mock API response, verify transformation and caching.

---

### US-3: Explore Today's Top Events (P2)

**As** an AI coding agent or analyst, **I want** to see today's most active events with counts and trends **so that** I can quickly understand current activity patterns.

**Acceptance Criteria:**
1. **Given** valid credentials, **When** I call `list_top_events()`, **Then** I receive a list of `TopEvent` objects.
2. **Given** each `TopEvent`, **Then** it contains: `event` (str), `count` (int), `percent_change` (float).
3. **Given** `list_top_events()` is called, **Then** results are NOT cached (data changes throughout day).
4. **Given** optional `type` parameter ("general"/"unique"/"average"), **When** I specify it, **Then** the API is called with that type.
5. **Given** optional `limit` parameter, **When** I specify it, **Then** at most that many events are returned.

**Testable Independently:** Yes — mock API response, verify transformation; verify no caching behavior.

---

### US-4: Analyze Multi-Event Time Series (P2)

**As** an AI coding agent or analyst, **I want** to query aggregate counts for multiple events over time **so that** I can compare event volumes on a single chart.

**Acceptance Criteria:**
1. **Given** a list of event names and date range, **When** I call `event_counts()`, **Then** I receive an `EventCountsResult` with time-series data.
2. **Given** the result, **Then** `series` contains `{event_name: {date: count}}` for each event.
3. **Given** the result, **Then** `.df` property returns a DataFrame with columns: date, event, count.
4. **Given** optional `unit` parameter, **When** I specify "day"/"week"/"month", **Then** data is aggregated accordingly.
5. **Given** optional `type` parameter, **When** I specify "general"/"unique"/"average", **Then** the appropriate metric is returned.

**Testable Independently:** Yes — mock API response, verify transformation and DataFrame conversion.

---

### US-5: Analyze Property Value Distributions Over Time (P2)

**As** an AI coding agent or analyst, **I want** to query aggregate counts broken down by property values over time **so that** I can analyze how a metric varies across segments.

**Acceptance Criteria:**
1. **Given** an event name, property name, and date range, **When** I call `property_counts()`, **Then** I receive a `PropertyCountsResult`.
2. **Given** the result, **Then** `series` contains `{property_value: {date: count}}`.
3. **Given** the result, **Then** `.df` property returns a DataFrame with columns: date, value, count.
4. **Given** optional `values` parameter (list of strings), **When** specified, **Then** only those property values are included.
5. **Given** optional `limit` parameter, **When** specified, **Then** at most that many property values are included.

**Testable Independently:** Yes — mock API response, verify transformation and DataFrame conversion.

---

## Key Entities (Data Model)

### FunnelInfo
```
FunnelInfo
├── funnel_id: int     # Unique identifier for funnel queries
└── name: str          # Human-readable funnel name
```

### SavedCohort
```
SavedCohort
├── id: int            # Unique identifier for profile filtering
├── name: str          # Human-readable cohort name
├── count: int         # Number of users in cohort
├── description: str   # Optional description
├── created: str       # Creation timestamp (YYYY-MM-DD HH:mm:ss)
└── is_visible: bool   # Whether cohort is visible in Mixpanel UI
```

### TopEvent
```
TopEvent
├── event: str         # Event name
├── count: int         # Today's event count
└── percent_change: float  # Change vs yesterday (-1.0 to +∞)
```

### EventCountsResult
```
EventCountsResult
├── events: list[str]           # Queried event names
├── from_date: str              # Query start date
├── to_date: str                # Query end date
├── unit: str                   # Aggregation unit (day/week/month)
├── series: dict[str, dict[str, int]]  # {event: {date: count}}
└── df: pd.DataFrame            # Lazy: date, event, count columns
```

### PropertyCountsResult
```
PropertyCountsResult
├── event: str                  # Queried event
├── property_name: str          # Property segmented by
├── from_date: str              # Query start date
├── to_date: str                # Query end date
├── unit: str                   # Aggregation unit
├── series: dict[str, dict[str, int]]  # {value: {date: count}}
└── df: pd.DataFrame            # Lazy: date, value, count columns
```

---

## Component Architecture

### Service Placement

| API Type | Characteristic | Service | Caching |
|----------|---------------|---------|---------|
| Funnels List | Static definitions | DiscoveryService | ✅ Cached |
| Cohorts List | Static definitions | DiscoveryService | ✅ Cached |
| Top Events | Real-time activity | DiscoveryService | ❌ Not cached |
| Event Counts | Time-series query | LiveQueryService | ❌ Not cached |
| Property Counts | Time-series query | LiveQueryService | ❌ Not cached |

**Rationale:**
- **Discovery** = introspection of project resources, no date range required
- **LiveQuery** = analytics queries requiring date range, returns time-series data

### API Client Methods

```
MixpanelAPIClient (api_client.py)
├── Discovery Section
│   ├── get_events()           # Existing
│   ├── get_event_properties() # Existing
│   ├── get_property_values()  # Existing
│   ├── get_top_events()       # NEW: GET /events/top
│   ├── list_funnels()         # NEW: GET /funnels/list
│   └── list_cohorts()         # NEW: POST /cohorts/list
└── Query Section
    ├── segmentation()         # Existing
    ├── funnel()               # Existing
    ├── retention()            # Existing
    ├── jql()                  # Existing
    ├── event_counts()         # NEW: GET /events
    └── property_counts()      # NEW: GET /events/properties
```

---

## Success Criteria

| ID | Metric | Target |
|----|--------|--------|
| SC-1 | All 8 new methods implemented and passing tests | 100% |
| SC-2 | Discovery methods return sorted results | Alphabetical by name |
| SC-3 | Cached methods make single API call per session | Verify in tests |
| SC-4 | Non-cached methods always hit API | Verify in tests |
| SC-5 | All result types have `.to_dict()` serialization | 100% |
| SC-6 | Time-series results have lazy `.df` property | 100% |
| SC-7 | Unit test coverage for new code | ≥90% |
| SC-8 | mypy --strict passes | Zero errors |
| SC-9 | ruff check passes | Zero errors |

---

## Dependencies

- **Phase 001** (Foundation): Result types, exception hierarchy
- **Phase 002** (API Client): HTTP client, regional endpoints, rate limiting
- **Phase 004** (Discovery): Existing DiscoveryService class and caching pattern
- **Phase 006** (Live Query): Existing LiveQueryService class and transformation pattern

---

## Assumptions

- **A-1:** Funnel and cohort definitions are relatively stable within a session (safe to cache).
- **A-2:** Today's top events change frequently (should NOT cache).
- **A-3:** The POST method for `/cohorts/list` is correct per Mixpanel API documentation.
- **A-4:** Event counts and property counts are analytics queries (belong in LiveQueryService).
- **A-5:** All new types should be frozen dataclasses matching existing patterns.

---

## Out of Scope

- **Annotations API** — Useful for timeline context but deferred to later phase
- **Data Pipelines API** — Data engineering workflows, not core analytics
- **Lexicon Schemas API** — Schema management, to be revisited separately
- **Profile property discovery** — Not part of Query API event breakdown
- **Creating/modifying funnels or cohorts** — Read-only discovery operations only

---

## Files to Modify

| File | Changes |
|------|---------|
| `src/mixpanel_data/types.py` | Add 5 types: `FunnelInfo`, `SavedCohort`, `TopEvent`, `EventCountsResult`, `PropertyCountsResult` |
| `src/mixpanel_data/_internal/api_client.py` | Add 5 methods: `get_top_events()`, `list_funnels()`, `list_cohorts()`, `event_counts()`, `property_counts()` |
| `src/mixpanel_data/_internal/services/discovery.py` | Add 3 methods: `list_top_events()`, `list_funnels()`, `list_cohorts()` |
| `src/mixpanel_data/_internal/services/live_query.py` | Add 2 methods: `event_counts()`, `property_counts()` |
| `src/mixpanel_data/__init__.py` | Export new types |
| `tests/unit/test_discovery.py` | Tests for new discovery methods |
| `tests/unit/test_live_query.py` | Tests for new live query methods |

---

## Risk Assessment

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| POST method for cohorts fails | High | Low | Verify against real API in QA |
| API response format differs from docs | Medium | Medium | Parse defensively with defaults |
| Cache type change causes issues | Low | Low | Broaden to `list[Any]`, test thoroughly |
| New result types missing serialization | Medium | Low | Follow existing type patterns exactly |

---

## Edge Cases

| Scenario | Expected Behavior |
|----------|-------------------|
| Project has no funnels | Return empty list `[]`, not error |
| Project has no cohorts | Return empty list `[]`, not error |
| Today has no events | Return empty list `[]` for top events |
| Event not in time range | Return result with empty series |
| Property has no values | Return result with empty series |
| Invalid credentials | Raise `AuthenticationError` |
| Rate limit exceeded | Automatic retry with backoff, then `RateLimitError` |

---

*This implementation plan is ready for spec-kit specification generation.*
