# Phase 004: Discovery Service — Implementation Post-Mortem

**Branch:** `004-discovery-service`
**Status:** Complete
**Date:** 2025-12-21
**PR:** https://github.com/jaredmcfarland/mixpanel_data/pull/10

---

## Executive Summary

Phase 004 implemented the `DiscoveryService`, a schema introspection layer that enables users to explore Mixpanel project structure before querying or fetching data. The service wraps existing API client methods with an in-memory cache to avoid redundant network requests during a session.

**Key insight:** This phase is strategically important for AI coding agents. By enabling schema exploration *before* data fetching, agents can understand what events and properties exist without consuming context window tokens on raw data exploration. The service is deliberately simple—a thin wrapper with caching—because the API client already handles authentication, rate limiting, and error conversion.

---

## What Was Built

### 1. DiscoveryService Class

**Purpose:** Schema discovery with session-scoped caching for Mixpanel projects.

**Architecture:**

```
DiscoveryService
├── __init__(api_client)          # Dependency injection
├── list_events()                  # Returns sorted event names
├── list_properties(event)         # Returns sorted property names
├── list_property_values(...)      # Returns sample values
└── clear_cache()                  # Clears all cached results
```

**Key Design Decisions:**

| Decision | Rationale |
|----------|-----------|
| Constructor injection | API client passed in; no hidden instantiation; easy to mock |
| Simple dict cache | O(1) lookup, no external dependencies, session-scoped only |
| Tuple cache keys | `(method_name, *args)` enables unique identification |
| Return copies from cache | Prevents caller mutation from affecting cached data |
| Pass-through errors | API client already raises typed exceptions; no wrapping needed |

**Example:**
```python
from mixpanel_data._internal.api_client import MixpanelAPIClient
from mixpanel_data._internal.services.discovery import DiscoveryService

client = MixpanelAPIClient(credentials)
discovery = DiscoveryService(client)

# First call hits API
events = discovery.list_events()           # ["Add to Cart", "Login", "Purchase", "Signup"]

# Second call uses cache (no network)
events = discovery.list_events()           # Same result, <1ms

# Explore properties
props = discovery.list_properties("Purchase")  # ["amount", "currency", "user_id"]

# Sample values
values = discovery.list_property_values("country", event="Purchase", limit=10)
```

---

### 2. Caching Strategy

**Purpose:** Avoid redundant API calls within a session while keeping implementation simple.

**Cache Key Design:**

| Method | Cache Key |
|--------|-----------|
| `list_events()` | `("list_events",)` |
| `list_properties("Purchase")` | `("list_properties", "Purchase")` |
| `list_property_values("country", event="Purchase", limit=50)` | `("list_property_values", "country", "Purchase", 50)` |

**Implementation:**

```python
class DiscoveryService:
    def __init__(self, api_client: MixpanelAPIClient) -> None:
        self._api_client = api_client
        self._cache: dict[tuple[str | int | None, ...], list[str]] = {}

    def list_events(self) -> list[str]:
        cache_key = ("list_events",)
        if cache_key in self._cache:
            return list(self._cache[cache_key])  # Return copy

        result = self._api_client.get_events()
        sorted_result = sorted(result)
        self._cache[cache_key] = sorted_result
        return list(sorted_result)  # Return copy
```

**Why return copies?**
```python
# Without copies: caller mutation corrupts cache
events = discovery.list_events()
events.append("Malicious Event")  # Would affect future calls!

# With copies: cache is isolated
events = discovery.list_events()
events.append("Safe Mutation")    # Only affects local copy
```

**Alternatives Considered:**

| Alternative | Rejected Because |
|-------------|------------------|
| `functools.lru_cache` | Decorator-based; harder to clear selectively; no composite keys |
| `cachetools.TTLCache` | TTL not required (session-scoped); adds dependency |
| Redis/external cache | Overkill for single-process, session-scoped use case |

---

### 3. API Client Integration

**Purpose:** Delegate all HTTP communication to the existing `MixpanelAPIClient`.

**Existing Methods Used:**

| API Client Method | DiscoveryService Method | Endpoint |
|-------------------|-------------------------|----------|
| `get_events()` | `list_events()` | `/events/names` |
| `get_event_properties(event)` | `list_properties(event)` | `/events/properties/top` |
| `get_property_values(property, event, limit)` | `list_property_values(...)` | `/events/properties/values` |

**What API Client Handles (DiscoveryService doesn't need to):**
- Authentication (Basic auth with credentials)
- Regional endpoint routing (US, EU, India)
- Rate limiting with exponential backoff
- Error conversion to typed exceptions
- HTTP request/response lifecycle

**TYPE_CHECKING Import Guard:**

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

### 4. Sorting Behavior

**Purpose:** Ensure consistent, predictable output regardless of API response order.

**Spec Requirements:**
- FR-002: Event lists must be alphabetically sorted
- FR-004: Property lists must be alphabetically sorted

**Implementation Decision:** Sort at service layer, not relying on API.

**Why?**
- API response order is not guaranteed
- Sorting at service layer ensures consistency
- Sorted output is more useful for AI agents (predictable structure)

**Example:**
```python
# API returns: ["Signup", "Login", "Purchase", "Add to Cart"]
# Service returns: ["Add to Cart", "Login", "Purchase", "Signup"]
```

**Exception:** `list_property_values()` does NOT sort results.

**Why not sort values?**
- Property values can be any type (strings, numbers, booleans)
- Sorting mixed types is semantically unclear
- Order from API may reflect frequency/recency (useful signal)

---

### 5. Error Handling

**Purpose:** Surface clear, typed errors to callers without redundant wrapping.

**Strategy:** Pass-through errors from API client.

**Exception Flow:**
```
User → DiscoveryService → MixpanelAPIClient → Mixpanel API
                                   ↓
         AuthenticationError | QueryError | RateLimitError
```

**Why no wrapper exceptions?**
- API client already raises appropriate exceptions
- Adding DiscoveryError would violate DRY
- Callers can catch the same exceptions they would from direct API use

**Error Scenarios:**

| Scenario | Exception | Example Message |
|----------|-----------|-----------------|
| Invalid credentials | `AuthenticationError` | "Invalid credentials" |
| Non-existent event | `QueryError` | "Event 'FakeEvent' not found" |
| Rate limit exceeded | `RateLimitError` | "Rate limit exceeded. Retry after 60s" |

---

## Test Coverage

### Unit Tests (`test_discovery.py`) — 460 lines, 18 tests

**Test Classes:**

| Class | Tests | Coverage |
|-------|-------|----------|
| `TestDiscoveryService` | 2 | Initialization, empty cache |
| `TestListEvents` | 4 | Sorting, caching, auth error, empty result |
| `TestListProperties` | 4 | Sorting, per-event caching, query error, empty result |
| `TestListPropertyValues` | 5 | Basic call, event scope, custom limit, caching, empty result |
| `TestClearCache` | 3 | Clear all, empty cache, causes API call |

**Testing Strategy:**

| Approach | Tool | Purpose |
|----------|------|---------|
| HTTP mocking | `httpx.MockTransport` | Deterministic responses, no network |
| Fixture factory | `discovery_factory` | Creates DiscoveryService with mock client |
| Call counting | `nonlocal call_count` | Verify cache prevents API calls |

**Key Test Patterns:**

```python
# Pattern 1: Verify caching prevents API calls
def test_list_events_caching_behavior(self, discovery_factory):
    call_count = 0

    def handler(_request):
        nonlocal call_count
        call_count += 1
        return httpx.Response(200, json=["Event1", "Event2"])

    discovery = discovery_factory(handler)

    events1 = discovery.list_events()
    assert call_count == 1

    events2 = discovery.list_events()  # Should use cache
    assert call_count == 1  # Still 1, not 2

# Pattern 2: Verify sorting
def test_list_events_returns_sorted_list(self, discovery_factory):
    def handler(_request):
        # Return unsorted to verify sorting
        return httpx.Response(200, json=["Signup", "Login", "Purchase"])

    discovery = discovery_factory(handler)
    events = discovery.list_events()

    assert events == ["Login", "Purchase", "Signup"]  # Sorted

# Pattern 3: Verify per-key caching
def test_list_properties_caching_per_event(self, discovery_factory):
    call_count = 0
    # ... handler that tracks calls per event ...

    discovery.list_properties("Purchase")  # call_count = 1
    discovery.list_properties("Purchase")  # call_count = 1 (cached)
    discovery.list_properties("Signup")    # call_count = 2 (different key)
```

---

## Code Quality Highlights

### 1. Minimal Implementation

The entire service is 137 lines including docstrings and comments. This reflects:
- Delegation to API client (no HTTP logic)
- Simple caching (no external dependencies)
- Pass-through errors (no wrapping)

### 2. Comprehensive Docstrings

Every public method includes:
- Purpose summary
- Args with types
- Returns description
- Raises documentation
- Usage notes

Example:
```python
def list_property_values(
    self,
    property_name: str,
    *,
    event: str | None = None,
    limit: int = 100,
) -> list[str]:
    """List sample values for a property.

    Args:
        property_name: Property name to get values for.
        event: Optional event name to scope the query.
        limit: Maximum number of values to return (default: 100).

    Returns:
        List of sample values as strings.

    Raises:
        AuthenticationError: Invalid credentials.

    Note:
        Results are cached per (property, event, limit) combination.
        Values are returned as strings regardless of original type.
    """
```

### 3. Type Safety

All methods fully typed:
```python
def __init__(self, api_client: MixpanelAPIClient) -> None: ...
def list_events(self) -> list[str]: ...
def list_properties(self, event: str) -> list[str]: ...
def list_property_values(
    self, property_name: str, *, event: str | None = None, limit: int = 100
) -> list[str]: ...
def clear_cache(self) -> None: ...
```

Mypy passes with `--strict` on the implementation.

---

## Integration Points

### Upstream Dependencies

**From Phase 002 (API Client):**
- `MixpanelAPIClient.get_events()` → `list[str]`
- `MixpanelAPIClient.get_event_properties(event)` → `list[str]`
- `MixpanelAPIClient.get_property_values(property, event, limit)` → `list[str]`

**From Phase 001 (Foundation):**
- `AuthenticationError` — raised on 401
- `QueryError` — raised on 400 (invalid event name)
- `RateLimitError` — raised on 429

### Downstream Impact

**For Phase 007 (Workspace):**
```python
class Workspace:
    def __init__(self, ...):
        self._discovery = DiscoveryService(self._api_client)

    def discover_events(self) -> list[str]:
        return self._discovery.list_events()

    def discover_properties(self, event: str) -> list[str]:
        return self._discovery.list_properties(event)
```

**For Phase 008 (CLI):**
```bash
mp discover events              # List all events
mp discover properties "Sign Up"  # List properties for event
mp discover values country --event "Sign Up" --limit 20
```

**For AI Agents:**
```python
# Agent workflow: explore before fetching
events = workspace.discover_events()
# → ["Add to Cart", "Checkout", "Login", "Purchase", "Signup"]

# Agent decides which events are relevant
props = workspace.discover_properties("Purchase")
# → ["amount", "currency", "discount_code", "payment_method", "user_id"]

# Agent constructs informed query
result = workspace.fetch_events(
    from_date="2024-01-01",
    to_date="2024-01-31",
    events=["Purchase"],
    where='properties["amount"] > 100',
    table="high_value_purchases"
)
```

---

## What's NOT Included

| Component | Notes |
|-----------|-------|
| Property type information | Not reliably available from Mixpanel API |
| Event metadata (descriptions, tags) | Out of scope per spec |
| Profile property discovery | Separate from event properties; not in Phase 004 |
| Cross-project discovery | Single project scope only |
| Persistent caching | Session-scoped only; no disk/Redis |
| Real-time cache invalidation | Manual `clear_cache()` only |

**Design principle:** DiscoveryService is intentionally minimal. It solves one problem well: schema exploration with caching.

---

## Performance Characteristics

| Metric | Target | Achieved |
|--------|--------|----------|
| Uncached request | <3s | Depends on API (typically <1s) |
| Cached request | <100ms | <1ms (dict lookup) |
| Memory per cache entry | Minimal | ~100 bytes for typical event list |

**Cache Memory Example:**
```python
# 500 events cached ≈ 500 × 20 chars × 2 bytes = ~20KB
# 50 properties per event × 10 events = 500 entries ≈ ~10KB
# Total: <50KB for typical project
```

---

## Specification Artifacts

Phase 004 used the speckit workflow to generate planning documents:

| File | Purpose |
|------|---------|
| [spec.md](../../specs/004-discovery-service/spec.md) | Feature specification with user stories |
| [plan.md](../../specs/004-discovery-service/plan.md) | Implementation plan with constitution check |
| [research.md](../../specs/004-discovery-service/research.md) | Research findings and decisions |
| [data-model.md](../../specs/004-discovery-service/data-model.md) | Entity definitions |
| [quickstart.md](../../specs/004-discovery-service/quickstart.md) | Usage examples |
| [tasks.md](../../specs/004-discovery-service/tasks.md) | Implementation tasks |
| [contracts/discovery_service.py](../../specs/004-discovery-service/contracts/discovery_service.py) | Interface contract |

---

## File Reference

| File | Lines | Purpose |
|------|-------|---------|
| [src/mixpanel_data/_internal/services/discovery.py](../../src/mixpanel_data/_internal/services/discovery.py) | 137 | DiscoveryService implementation |
| [src/mixpanel_data/_internal/services/__init__.py](../../src/mixpanel_data/_internal/services/__init__.py) | 4 | Package marker (new) |
| [tests/unit/test_discovery.py](../../tests/unit/test_discovery.py) | 460 | Comprehensive unit tests |

**Test coverage:** 100% of DiscoveryService methods.

---

## Lessons Learned

1. **Thin wrappers are valuable:** DiscoveryService adds only ~60 lines of logic (caching + sorting), but provides significant value by preventing redundant API calls and ensuring consistent output.

2. **Cache key design matters:** Tuple-based composite keys `(method, *args)` are simple, hashable, and debuggable. More complex approaches (frozen dataclasses, named tuples) would add overhead without benefit.

3. **Return copies from cache:** A subtle but critical pattern. Without copies, callers can accidentally corrupt the cache by mutating returned lists.

4. **Pass-through errors are fine:** When the underlying layer already provides typed, informative exceptions, wrapping them adds complexity without value.

5. **Sorting at service layer:** Don't rely on API response order. Sorting guarantees consistent, predictable output regardless of upstream changes.

---

## Next Phase: 005 (Fetch Service)

Phase 005 implements `FetcherService` for streaming data ingestion:
- `fetch_events(name, from_date, to_date, ...)` → `FetchResult`
- `fetch_profiles(name, where, ...)` → `FetchResult`

**Key difference from DiscoveryService:** FetcherService coordinates API client AND storage engine. Discovery is read-only introspection; Fetcher is write-heavy data ingestion.

---

**Post-Mortem Author:** Claude (Opus 4.5)
**Date:** 2025-12-22
**Lines of Code:** 137 (implementation) + 460 (tests) = 597 total
