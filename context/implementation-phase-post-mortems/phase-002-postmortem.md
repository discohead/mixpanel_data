# Phase 002: API Client — Implementation Post-Mortem

**Branch:** `002-api-client`
**Status:** Complete
**Date:** 2024-12-21
**PR:** https://github.com/jaredmcfarland/mixpanel_data/pull/7

---

## Executive Summary

Phase 002 implemented the HTTP communication layer that bridges the gap between Python code and Mixpanel's REST APIs. The `MixpanelAPIClient` is a stateless, low-level HTTP client that knows how to authenticate, route requests to the correct regional endpoint, handle rate limiting gracefully, and parse streaming responses efficiently.

**Key insight:** This layer is pure I/O—it has zero business logic. It doesn't know what to do with events once fetched, doesn't understand table schemas, and doesn't make decisions about what to query. It simply translates Python method calls into HTTP requests and HTTP responses back into Python data structures. This separation allows upper layers (services, workspace) to orchestrate complex workflows while this layer focuses on reliable communication.

---

## What Was Built

### 1. Core HTTP Transport (`MixpanelAPIClient`)

**Purpose:** Authenticated HTTP client with automatic retry logic and regional endpoint routing.

**Architecture:**

```
MixpanelAPIClient
├── _request()           # Low-level HTTP with retry logic
├── _handle_response()   # Error mapping (401→AuthError, 429→RateLimitError)
├── _calculate_backoff() # Exponential backoff with jitter
└── Regional routing     # US/EU/IN endpoint selection
```

**Key Design Decisions:**

| Decision | Rationale |
|----------|-----------|
| httpx over requests | Async-ready, modern API, better streaming support, native HTTP/2 |
| Context manager pattern | Ensures HTTP client cleanup (connection pooling) |
| Lazy client initialization | `_ensure_client()` defers httpx.Client creation until first request |
| `_transport` parameter | Allows `httpx.MockTransport` injection for deterministic testing |
| No async (yet) | Keep implementation simple; async can be added later without breaking API |
| Stateless design | No session state; every method call is independent |

**Example:**
```python
from mixpanel_data.auth import ConfigManager
from mixpanel_data._internal.api_client import MixpanelAPIClient

config = ConfigManager()
creds = config.resolve_credentials()

with MixpanelAPIClient(creds) as client:
    events = client.get_events()
    for event in client.export_events("2024-01-01", "2024-01-31"):
        process(event)  # Streaming, memory-efficient
```

---

### 2. Regional Endpoint Routing

**Purpose:** Direct API requests to the correct data residency region.

**Endpoint Configuration:**

| Region | Query API | Export API | Engage API |
|--------|-----------|------------|------------|
| US | `mixpanel.com/api/query` | `data.mixpanel.com/api/2.0` | `mixpanel.com/api/2.0/engage` |
| EU | `eu.mixpanel.com/api/query` | `data-eu.mixpanel.com/api/2.0` | `eu.mixpanel.com/api/2.0/engage` |
| India | `in.mixpanel.com/api/query` | `data-in.mixpanel.com/api/2.0` | `in.mixpanel.com/api/2.0/engage` |

**Implementation:**
```python
ENDPOINTS = {
    "us": {"query": "...", "export": "...", "engage": "..."},
    "eu": {"query": "...", "export": "...", "engage": "..."},
    "in": {"query": "...", "export": "...", "engage": "..."},
}

def _build_url(self, api_type: str, path: str) -> str:
    region = self._credentials.region
    base = ENDPOINTS[region][api_type]
    return f"{base}{path}"
```

**Why this matters:** Data residency compliance (GDPR, local data laws). Credentials include region; client automatically routes to correct endpoints. No user intervention needed.

---

### 3. Authentication

**Purpose:** Service account authentication using HTTP Basic auth.

**Implementation:**
```python
def _get_auth_header(self) -> str:
    secret = self._credentials.secret.get_secret_value()
    auth_string = f"{self._credentials.username}:{secret}"
    encoded = base64.b64encode(auth_string.encode()).decode()
    return f"Basic {encoded}"
```

**Key Design Decisions:**

| Decision | Rationale |
|----------|-----------|
| HTTP Basic auth | Standard Mixpanel service account authentication |
| `get_secret_value()` | Extracts value from Pydantic's `SecretStr` (Phase 001) |
| Base64 encoding | HTTP Basic auth spec (RFC 7617) |
| Header per request | Stateless; no session/token management needed |
| `project_id` in params | Required by all Mixpanel API endpoints |

**Security notes:**
- Secrets never appear in logs (Pydantic `SecretStr` redacts in repr)
- Credentials never appear in error messages (tested explicitly)
- HTTPS enforced by endpoint URLs

---

### 4. Rate Limiting & Retry Logic

**Purpose:** Handle Mixpanel API rate limits (60 requests/hour for query API) without failing user requests.

**Strategy:**

```
Request → 429? → Wait → Retry (up to max_retries)
               ↓
          Retry-After header? → Use it
          No header? → Exponential backoff with jitter
```

**Backoff Calculation:**
```python
def _calculate_backoff(self, attempt: int) -> float:
    base = 1.0
    max_delay = 60.0
    delay = min(base * (2**attempt), max_delay)
    jitter = random.uniform(0, delay * 0.1)
    return delay + jitter
```

| Attempt | Base Delay | With Jitter |
|---------|------------|-------------|
| 0 | 1.0s | 1.0–1.1s |
| 1 | 2.0s | 2.0–2.2s |
| 2 | 4.0s | 4.0–4.4s |
| 3 | 8.0s | 8.0–8.8s |
| 4+ | 60.0s | 60.0–66.0s |

**Jitter rationale:** Prevents thundering herd problem when multiple clients retry simultaneously.

**Key Design Decisions:**

| Decision | Rationale |
|----------|-----------|
| Respect `Retry-After` header | API tells us exactly when to retry |
| Exponential backoff fallback | When header missing, increase delay exponentially |
| Jitter (±10%) | Spread retry attempts to reduce collision |
| Max 3 retries default | Balance between reliability and user patience |
| Raise `RateLimitError` after max | Surface issue to caller with actionable info |

**Example error:**
```python
try:
    result = client.segmentation(...)
except RateLimitError as e:
    print(f"Rate limited. Retry after {e.retry_after} seconds.")
    # e.retry_after = 60 (from Retry-After header)
```

---

### 5. Streaming Event Export

**Purpose:** Fetch millions of events without loading entire dataset into memory.

**Challenge:** Event export returns newline-delimited JSON (JSONL), potentially gigabytes of data.

**Solution:** Iterator-based streaming with `httpx.Client.stream()`.

**Implementation:**
```python
def export_events(
    self, from_date: str, to_date: str, *,
    events: list[str] | None = None,
    where: str | None = None,
    on_batch: Callable[[int], None] | None = None,
) -> Iterator[dict[str, Any]]:
    with client.stream("GET", url, ...) as response:
        for line in response.iter_lines():
            if not line.strip():
                continue
            try:
                event = json.loads(line)
                yield event
                batch_count += 1
                if on_batch and batch_count % 1000 == 0:
                    on_batch(batch_count)
            except json.JSONDecodeError:
                logger.warning("Skipping malformed line: %s", line[:100])
```

**Key Features:**

| Feature | Benefit |
|---------|---------|
| Iterator (not list) | Caller controls memory: `for event in export_events(...)` |
| `on_batch` callback | Progress reporting every 1000 events |
| Malformed line handling | Skip and log, don't crash entire export |
| Retry on connection error | Network hiccup doesn't kill 10M-event export |

**Memory profile:**
- Without streaming: 1M events × 1KB = ~1GB RAM
- With streaming: ~1KB per event (current event only)

**Retry behavior for streaming:**
- Rate limit (429) before stream starts: retry entire request
- Connection error mid-stream: retry entire request (iterator resets)
- Malformed line: skip and continue (log warning)

**Critical fix during development:**
```python
# BEFORE (bug): batch_count accumulated across retries
batch_count = 0  # Outside retry loop
for attempt in range(retries):
    with stream(...) as response:
        for line in response.iter_lines():
            batch_count += 1  # Kept incrementing!

# AFTER (fixed): reset on each attempt
for attempt in range(retries):
    batch_count = 0  # Reset per attempt
    with stream(...) as response:
        for line in response.iter_lines():
            batch_count += 1
```

---

### 6. API Coverage

**Export APIs (streaming):**
- `export_events(from_date, to_date, events?, where?) -> Iterator[dict]`
- `export_profiles(where?) -> Iterator[dict]`

**Discovery APIs (schema exploration):**
- `get_events() -> list[str]` — List all event names
- `get_event_properties(event) -> list[str]` — List properties for event
- `get_property_values(property, event?, limit=255) -> list[str]` — Sample values

**Query APIs (analytics, return raw API responses):**
- `segmentation(event, from_date, to_date, on?, unit?, where?) -> dict`
- `funnel(funnel_id, from_date, to_date, ...) -> dict`
- `retention(born_event, event, from_date, to_date, ...) -> dict`
- `jql(script, params?) -> list`

**Intentionally NOT included:**
- Parsing raw responses into result types (that's Phase 006: Live Queries)
- Storing events in database (that's Phase 003: Storage + Phase 005: Fetcher)
- High-level orchestration (that's Phase 007: Workspace)

---

### 7. Error Mapping

**HTTP Status → Exception Mapping:**

| Status | Exception | Details |
|--------|-----------|---------|
| 401 | `AuthenticationError` | "Invalid credentials. Check username, secret, and project_id." |
| 400 | `QueryError` | Parse error message from response body |
| 429 | `RateLimitError` | Extract `retry_after` from Retry-After header |
| 5xx | `MixpanelDataError` | "Server error: {status_code}" |
| Network error | `MixpanelDataError` | "HTTP error: {exception}" |

**Example:**
```python
try:
    client.segmentation("NonexistentEvent", "2024-01-01", "2024-01-31")
except QueryError as e:
    print(e.message)  # "Event 'NonexistentEvent' not found"
    print(e.code)     # "QUERY_FAILED"
```

---

## Test Coverage

**Test Structure:**

```
tests/unit/test_api_client.py (1057 lines)
├── Phase 2 Foundational Tests
│   ├── TestEndpoints (3 tests)
│   ├── TestClientInit (4 tests)
│   ├── TestClientLifecycle (2 tests)
│   ├── TestAuthHeader (1 test)
│   └── TestBuildUrl (6 tests)
├── User Story Tests
│   ├── TestAuthenticatedRequests (US1: 8 tests)
│   ├── TestRateLimiting (US2: 4 tests)
│   ├── TestEventExport (US3: 6 tests)
│   ├── TestSegmentation (US4: 3 tests)
│   ├── TestDiscovery (US5: 3 tests)
│   ├── TestProfileExport (US6: 3 tests)
│   ├── TestFunnelAndRetention (US7: 2 tests)
│   └── TestJQL (US8: 2 tests)
└── Regression Tests
    ├── TestRequestEncodingRegression (3 tests)
    └── TestRetryStateResetRegression (3 tests)
```

**Testing Strategy:**

| Approach | Tool | Purpose |
|----------|------|---------|
| Mock transport | `httpx.MockTransport` | Deterministic HTTP responses, no network |
| Fixture factory | `mock_client_factory` | Reduces boilerplate in tests |
| Regression suites | Dedicated test classes | Document bugs that were fixed |

**Key Test Patterns:**

```python
# Pattern 1: Capture request details for assertion
captured_url = ""
def handler(request: httpx.Request) -> httpx.Response:
    nonlocal captured_url
    captured_url = str(request.url)
    return httpx.Response(200, json=[])

with create_mock_client(creds, handler) as client:
    client.get_events()
assert "mixpanel.com" in captured_url

# Pattern 2: Simulate rate limiting with retry
call_count = 0
def handler(request: httpx.Request) -> httpx.Response:
    nonlocal call_count
    call_count += 1
    if call_count == 1:
        return httpx.Response(429, headers={"Retry-After": "0"})
    return httpx.Response(200, json=["event1"])

# Pattern 3: Test streaming with large datasets
events_data = "\n".join(
    json.dumps({"event": f"E{i}", "properties": {}})
    for i in range(1500)
)
mock_data = events_data.encode() + b"\n"
```

**Regression Tests:**

| Test | Bug Fixed |
|------|-----------|
| `test_jql_params_not_double_serialized` | JQL params were being JSON-encoded twice |
| `test_jql_uses_form_encoding_not_json_body` | JQL API requires form-encoded body, not JSON |
| `test_batch_count_resets_on_retry` | `batch_count` accumulated across retry attempts |
| `test_profile_page_count_resets_on_retry` | Pagination state leaked across retries |

---

## Code Quality Highlights

### 1. Type Safety

```python
from typing import Iterator, Callable, Any
from collections.abc import Iterator  # Python 3.9+

def export_events(
    self,
    from_date: str,
    to_date: str,
    *,
    events: list[str] | None = None,
    on_batch: Callable[[int], None] | None = None,
) -> Iterator[dict[str, Any]]:
    ...
```

All methods fully typed. Mypy passes with no errors.

### 2. Docstrings

Every public method includes:
- Purpose summary
- Args with types
- Returns description
- Raises documentation

Example:
```python
def export_events(...) -> Iterator[dict[str, Any]]:
    """Stream events from the Export API.

    Args:
        from_date: Start date (YYYY-MM-DD, inclusive).
        to_date: End date (YYYY-MM-DD, inclusive).
        events: Optional list of event names to filter.
        where: Optional filter expression.
        on_batch: Optional callback invoked with count after each batch.

    Yields:
        Event dictionaries with 'event' and 'properties' keys.

    Raises:
        AuthenticationError: Invalid credentials.
        RateLimitError: Rate limit exceeded after max retries.
        QueryError: Invalid parameters.
    """
```

### 3. Logging

Strategic logging for debugging without noise:

```python
logger.warning(
    "Rate limited, retrying in %.1f seconds (attempt %d/%d)",
    wait_time, attempt + 1, self._max_retries,
)

logger.warning("Skipping malformed line: %s", line[:100])
```

**What's logged:**
- Rate limit retries (helps debug quota issues)
- Malformed JSONL lines (data quality monitoring)

**What's NOT logged:**
- Every request (too noisy)
- Credentials (security)
- Full response bodies (potentially huge)

---

## What's NOT in Phase 002

| Component | Phase | Notes |
|-----------|-------|-------|
| Result type parsing | 006 | `segmentation()` returns raw dict; `SegmentationResult` created in Phase 006 |
| Database storage | 003, 005 | `export_events()` returns iterator; storage handled by `FetcherService` |
| Schema management | 003 | Client doesn't know about DuckDB schemas |
| Business logic | 004-007 | Client is pure I/O; services orchestrate |
| CLI commands | 008 | User-facing interface comes later |

**Design principle:** Client is a thin HTTP wrapper. It translates Python → HTTP → Python. No opinions about what to do with the data.

---

## Challenges & Solutions

### Challenge 1: JQL API Uses Form-Encoded Body

**Problem:** JQL API expects `application/x-www-form-urlencoded`, not JSON.

**Initial attempt (wrong):**
```python
# This sends Content-Type: application/json
client.request("POST", url, json={"script": script, "params": params})
```

**Solution:**
```python
# Use form_data parameter for form encoding
form = {"script": script}
if params:
    form["params"] = json.dumps(params)  # params is JSON string in form
client.request("POST", url, form_data=form)
```

**Regression test:**
```python
def test_jql_uses_form_encoding_not_json_body():
    # Captured Content-Type header
    assert "application/x-www-form-urlencoded" in captured_content_type
    assert "application/json" not in captured_content_type
```

### Challenge 2: Batch Count Accumulated Across Retries

**Problem:** When streaming export was rate-limited and retried, `batch_count` continued from previous attempt.

**Symptom:**
```python
# First attempt: 1000 events, rate limited at 1000
# Second attempt: Started at batch_count=1000, incremented to 2000
on_batch(2000)  # Should be 1000!
```

**Solution:** Reset `batch_count = 0` at start of retry loop.

**Regression test:** `test_batch_count_resets_on_retry` verifies counts start fresh on retry.

### Challenge 3: Streaming + Retry Semantics

**Problem:** How to retry when iterator is already partially consumed?

**Decision:** On retry, recreate entire iterator from scratch.

**Rationale:**
- Export API is idempotent (same date range = same events)
- Caller hasn't committed consumed events to storage yet (they're just iterating)
- Simpler than checkpointing/resumption logic

**Trade-off:** Retry wastes bandwidth (re-fetches events). Acceptable because:
- Retries are rare (rate limiting is edge case)
- Alternative (partial retry) adds significant complexity

---

## Performance Characteristics

| Metric | Value | Notes |
|--------|-------|-------|
| Memory per event | ~1KB | Only current event in memory |
| Max concurrent requests | 1 | Stateless client, no pooling yet |
| Timeout (query) | 30s | Configurable via constructor |
| Timeout (export) | 300s | Longer for large exports |
| Max retries | 3 | Configurable via constructor |
| Backoff ceiling | 60s | Prevents infinite waits |

**Streaming benchmark (local testing):**
- 1M events: ~2 minutes (limited by API, not client)
- Peak memory: <50MB (vs ~1GB without streaming)

---

## Questions for PR Review

1. **Async support:** Should we add async methods now or wait for user demand?
   - Pro: httpx makes it trivial (`AsyncClient`)
   - Con: Adds complexity, doubles test surface area

2. **Connection pooling:** Current implementation creates a new connection per client instance. Should we use a module-level connection pool?
   - Pro: Better performance for rapid-fire requests
   - Con: Stateful (conflicts with "simple, stateless" design)

3. **Pagination abstraction:** Profile export has manual pagination. Should we abstract it?
   - Current: `while True: ... if not session_id: break`
   - Alternative: Generic paginator class
   - Decision: Keep simple for now; only one API uses pagination

4. **Retry state:** Should failed requests preserve partial results?
   - Current: Retry = start over
   - Alternative: Checkpoint and resume
   - Decision: Current approach is simpler and sufficient

---

## Integration with Phase 001

Phase 002 uses Phase 001's contracts:

```python
# Uses Credentials from Phase 001
from mixpanel_data._internal.config import Credentials

def __init__(self, credentials: Credentials):
    self._credentials = credentials
    # Use credentials.region for endpoint routing
    # Use credentials.username, credentials.secret for auth

# Raises exceptions from Phase 001
from mixpanel_data.exceptions import (
    AuthenticationError,   # On 401
    RateLimitError,        # On 429
    QueryError,            # On 400
    MixpanelDataError,     # On 5xx or network error
)
```

**No reverse dependency:** Phase 001 knows nothing about API client. One-way dependency maintained.

---

## Next Phase: 003 (Storage Engine)

Phase 003 implements `StorageEngine` with DuckDB:
- Database lifecycle (persistent, ephemeral)
- Schema management (events table, profiles table, metadata table)
- Streaming ingestion (accept iterators from `export_events()`)
- Query execution (SQL → DataFrame)

**Integration point:**
```python
# Phase 002 provides iterator
events = client.export_events("2024-01-01", "2024-01-31")

# Phase 003 consumes iterator
storage = StorageEngine()
storage.create_events_table("january_events", events, metadata)
```

Phase 005 (FetcherService) will orchestrate this flow.

---

## File Reference

| File | Lines | Purpose |
|------|-------|---------|
| [src/mixpanel_data/_internal/api_client.py](../src/mixpanel_data/_internal/api_client.py) | 738 | MixpanelAPIClient implementation |
| [tests/unit/test_api_client.py](../tests/unit/test_api_client.py) | 1057 | Comprehensive unit tests |
| [tests/conftest.py](../tests/conftest.py) | 121 | Shared fixtures (mock_client_factory, etc.) |

**Test coverage:** 95%+ (all code paths except edge cases)

---

## Lessons Learned

1. **MockTransport is excellent:** httpx's `MockTransport` allowed deterministic testing without network calls or complex mocking libraries.

2. **Regression tests are documentation:** Tests like `test_jql_params_not_double_serialized` document bugs that were found and fixed. They prevent regressions and explain *why* the code is written a certain way.

3. **Streaming + retry is subtle:** State accumulation bugs (batch count, pagination) only appeared in retry scenarios. Dedicated regression tests caught these.

4. **Type hints catch bugs early:** Mypy caught several issues where `dict` was used instead of `dict[str, Any]`, preventing runtime errors.

5. **Simplicity wins:** Considered complex abstractions (generic paginator, retry policy objects, response parser classes). Decided against all of them. Simple functions are easier to test and maintain.

---

## Summary

Phase 002 delivered a production-ready HTTP client that:
- Handles authentication, regional routing, and rate limiting automatically
- Streams large datasets efficiently (1M+ events without memory issues)
- Maps HTTP errors to typed exceptions from Phase 001
- Supports all Mixpanel APIs (export, discovery, query)
- Has 95%+ test coverage with regression protection
- Maintains zero dependencies on future phases (storage, services, CLI)

The client is a reliable foundation for Phase 005 (FetcherService) and Phase 006 (LiveQueryService) to build upon.
