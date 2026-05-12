# Research: Discovery Service

**Date**: 2025-12-21
**Feature**: 004-discovery-service

## Overview

Research findings for implementing the DiscoveryService. This feature is straightforward—wrapping existing API client methods with caching—so research focuses on caching patterns and integration with existing code.

## Research Items

### 1. Caching Strategy

**Decision**: Simple dictionary-based in-memory cache with composite keys

**Rationale**:
- Session-scoped caching only (per spec A-002)
- No TTL required—cache lives as long as service instance
- Small data volume (event names, property lists) fits comfortably in memory
- Dictionary lookup is O(1) and sufficient for <100ms cached response requirement

**Alternatives Considered**:

| Alternative | Rejected Because |
|-------------|------------------|
| `functools.lru_cache` | Harder to clear selectively; decorator-based doesn't allow explicit clear |
| `cachetools.TTLCache` | TTL not required per spec; adds dependency |
| Redis/external cache | Overkill for session-scoped, single-process use case |

**Implementation Pattern**:
```python
# Cache key format: (method_name, *sorted_args)
# Examples:
#   ("list_events",)
#   ("list_properties", "Sign Up")
#   ("list_property_values", "country", "Sign Up", 100)
```

### 2. API Client Integration

**Decision**: Accept `MixpanelAPIClient` via constructor injection

**Rationale**:
- Matches established pattern from `StorageEngine` and other services
- Enables easy testing with mock clients
- No direct httpx dependency in DiscoveryService

**Existing Methods Available** (from `api_client.py` lines 487-553):

| Method | Returns | Endpoint |
|--------|---------|----------|
| `get_events()` | `list[str]` | `/events/names` |
| `get_event_properties(event)` | `list[str]` | `/events/properties/top` |
| `get_property_values(property_name, event, limit)` | `list[str]` | `/events/properties/values` |

All methods already handle:
- Authentication
- Regional endpoint routing
- Rate limiting with backoff
- Error conversion to library exceptions

### 3. Error Handling

**Decision**: Pass through exceptions from API client; no wrapping

**Rationale**:
- API client already raises appropriate exceptions (`AuthenticationError`, `QueryError`, `RateLimitError`)
- Adding wrapper exceptions would violate DRY
- Spec FR-010/FR-011 satisfied by existing client exceptions

**Exception Flow**:
```
User → DiscoveryService → MixpanelAPIClient → Mixpanel API
                           ↓
          AuthenticationError | QueryError | RateLimitError
```

### 4. Sorting Behavior

**Decision**: Sort results at service layer, not relying on API

**Rationale**:
- Spec FR-002/FR-004 require alphabetical sorting
- API response order is not guaranteed to be alphabetical
- Sorting at service layer ensures consistency regardless of API changes

**Implementation**: `sorted(result)` on all list returns

### 5. Testing Strategy

**Decision**: Unit tests with mocked API client; optional integration tests

**Rationale**:
- Unit tests verify caching, sorting, error propagation
- Integration tests require live credentials (environment-dependent)
- Mock pattern already established in `tests/unit/test_api_client.py`

**Mock Pattern** (from existing tests):
```python
@pytest.fixture
def mock_client_factory(mock_credentials):
    def factory(handler):
        transport = httpx.MockTransport(handler)
        return MixpanelAPIClient(mock_credentials, _transport=transport)
    return factory
```

## Unknowns Resolved

| Unknown | Resolution |
|---------|------------|
| Cache TTL | Session-only, no TTL (spec A-002) |
| Cache clearing | Explicit `clear_cache()` method (spec FR-009) |
| All properties method | Not included—per-event only (spec FR-003) |
| Property types | Out of scope (spec Out of Scope section) |

## Dependencies Verified

| Dependency | Status | Notes |
|------------|--------|-------|
| MixpanelAPIClient | ✅ Available | Phase 002 complete |
| Exception hierarchy | ✅ Available | Phase 001 complete |
| Test fixtures | ✅ Available | `conftest.py` has mock patterns |

## Conclusion

No blockers identified. Implementation can proceed with:
1. Simple dict-based cache
2. Constructor injection of API client
3. Pass-through error handling
4. Service-layer sorting
5. Unit tests with mocked client
