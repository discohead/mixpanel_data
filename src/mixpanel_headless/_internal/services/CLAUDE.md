# Services Layer

Domain services implementing core business logic. These are internal implementation details—consume via the `Workspace` facade.

## Files

| File | Purpose |
|------|---------|
| `discovery.py` | Schema exploration (events, properties, funnels, cohorts) with caching |
| `live_query.py` | Real-time API queries (segmentation, funnels, retention, JQL) |

## Design Patterns

**Dependency Injection**: All services accept their dependencies (API client) as constructor arguments. This enables testing with mocks.

**Lazy Initialization**: Services are created on-demand by `Workspace` when first accessed.

**Caching**: `DiscoveryService` caches schema data (events, properties, funnels) for the workspace lifetime. Call `clear_cache()` to force refresh.

## Service Responsibilities

### DiscoveryService
- Lists events, properties, property values
- Lists saved funnels and cohorts
- Gets top events (real-time, not cached)
- All results cached except `list_top_events()`

### LiveQueryService
- Executes real-time queries against Mixpanel API
- Segmentation, funnels, retention, JQL
- Event counts, property counts, insights, activity feed
- Frequency analysis, numeric aggregations
- Flows, saved reports, bookmarks, lexicon schemas

## Testing

Mock the API client:

```python
mock_api = Mock(spec=MixpanelAPIClient)
service = DiscoveryService(mock_api)
```
