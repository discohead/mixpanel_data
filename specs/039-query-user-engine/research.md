# Research: User Profile Query Engine

**Date**: 2026-04-13  
**Feature**: 039-query-user-engine  
**Status**: Complete

---

## R1: Query Engine Architecture Pattern

**Decision**: `query_user()` will follow the established two-method pattern (public query + public build_params) but will NOT delegate to `LiveQueryService`.

**Rationale**: The engage API uses a fundamentally different request format (form-encoded params, not bookmark JSON), a different endpoint (`/api/2.0/engage`, not `/query/insights`), and requires session-based pagination. Forcing this through `LiveQueryService` would require an awkward adapter layer with no benefit.

**Alternatives considered**:
- Route through `LiveQueryService` — rejected: different endpoint, different param format, different pagination model
- Create a new `UserQueryService` — rejected: adds a service layer for a single method; the complexity doesn't warrant it. The engage API interaction is simple enough to handle directly in workspace.py

**Implementation pattern**:
```
query_user() → _resolve_and_build_user_params() → credentials check → _execute_* → UserQueryResult
build_user_params() → _resolve_and_build_user_params() → return params dict
```

**Evidence**: All four existing engines (`query`, `query_funnel`, `query_retention`, `query_flow`) follow this exact two-method pattern in `workspace.py:2270-4184`. The private `_resolve_and_build_*_params()` method handles: type guards → normalization → Layer 1 validation → param building → Layer 2 validation → return dict.

---

## R2: Filter → Selector String Translation (NEW Path)

**Decision**: Create a new translation module `_internal/query/user_builders.py` that converts `Filter` objects to engage API selector strings.

**Rationale**: The engage API uses selector strings (e.g., `properties["plan"] == "premium"`) rather than bookmark filter dicts or segfilter entries. This is a third distinct translation format. Existing translation paths:
- `bookmark_builders.py:build_filter_entry()` → bookmark filter dicts (insights/funnels/retention)
- `segfilter.py:build_segfilter_entry()` → segfilter entries (flows steps)
- **NEW**: `user_builders.py:filter_to_selector()` → selector strings (engage)

**Alternatives considered**:
- Reuse `bookmark_builders.py` and convert bookmark dicts to selector strings — rejected: double conversion adds complexity and potential bugs
- Accept only raw selector strings (no Filter support) — rejected: breaks unified vocabulary goal; agents must learn a new syntax

**Operator mapping** (Filter internal operator → selector string):

| Filter Operator | Selector Output |
|---|---|
| `"equals"` | `properties["p"] == "v"` |
| `"does not equal"` | `properties["p"] != "v"` |
| `"contains"` | `"v" in properties["p"]` |
| `"does not contain"` | `not "v" in properties["p"]` |
| `"is greater than"` | `properties["p"] > n` |
| `"is less than"` | `properties["p"] < n` |
| `"is between"` | `properties["p"] >= a and properties["p"] <= b` |
| `"is set"` | `defined(properties["p"])` |
| `"is not set"` | `not defined(properties["p"])` |
| `"true"` | `properties["p"] == true` |
| `"false"` | `properties["p"] == false` |

**Evidence**: Filter internal attributes are `_property`, `_operator`, `_value`, `_property_type`, `_resource_type` (types.py:7262-7310). The engage API selector syntax is documented in the design document Appendix A.

---

## R3: API Client Extensions

**Decision**: Add new parameters to `export_profiles_page()` and create new `engage_stats()` method.

**Rationale**: The current `export_profiles_page()` (api_client.py:1381-1474) is missing parameters that `query_user()` needs: `sort_key`, `sort_order`, `search`, `limit`, and rich `filter_by_cohort` (dict format supporting `raw_cohort`). Rather than building a separate request path, extending the existing method maintains the single point of engage API interaction.

**Changes needed**:

1. **`export_profiles_page()` — add parameters**:
   - `sort_key: str | None = None` — sort expression (e.g., `properties["ltv"]`)
   - `sort_order: str | None = None` — `"ascending"` or `"descending"`
   - `search: str | None = None` — full-text search
   - `limit: int | None = None` — server-side result cap
   - `filter_by_cohort: str | None = None` — JSON-encoded cohort filter dict (supports `{"id": N}` and `{"raw_cohort": {...}}`)
   - Deprecation: `cohort_id` parameter remains for backward compat but `filter_by_cohort` takes precedence

2. **`engage_stats()` — new method**:
   - POSTs to `/api/2.0/engage` with `filter_type=stats`
   - Accepts: `where`, `action`, `filter_by_cohort`, `segment_by_cohorts`, `group_id`, `as_of_timestamp`, `include_all_users`
   - Returns raw response dict

**Alternatives considered**:
- Create a generic `engage_request()` that takes raw params — rejected: loses type safety and discoverability
- Pass raw params dict from workspace to API client — rejected: breaks the typed parameter pattern used by all other API client methods

**Evidence**: Current `export_profiles_page()` POSTs form-encoded data to `/api/2.0/engage` (api_client.py:1432-1457). Rate limiting and retry logic in `_execute_with_retry()` (api_client.py:395-512) applies automatically.

---

## R4: CohortDefinition Compatibility

**Decision**: `CohortDefinition.to_dict()` output will be passed to the engage API via `filter_by_cohort.raw_cohort`.

**Rationale**: `CohortDefinition.to_dict()` (types.py:8722-8783) serializes to `{"selector": {...}, "behaviors": {...}}` format. The engage API's `filter_by_cohort` parameter accepts `{"raw_cohort": <definition>}` which the server converts to a cohort query internally — the same path as the legacy `behaviors` parameter.

**Risk**: The `to_dict()` output format hasn't been validated against the engage `filter_by_cohort.raw_cohort` path. The design document notes this as Open Question #5. Integration testing against the live API will be needed to confirm compatibility.

**Mitigation**: Validation rule U24 checks that `to_dict()` serialization succeeds. If the format is incompatible, a translation layer can be added in `_build_user_params()` without changing the public API.

**Evidence**: `CohortDefinition` (types.py:8631-8783) with `all_of()`, `any_of()` class methods and `to_dict()` serialization. `CohortCriteria` (types.py:8169-8550) with `did_event()`, `has_property()`, `in_cohort()` builders.

---

## R5: Result Type Design

**Decision**: `UserQueryResult` extends `ResultWithDataFrame` as a frozen dataclass with mode-aware `df` property.

**Rationale**: All four existing result types follow the same pattern: frozen dataclass, `computed_at`/`params`/`meta` fields, lazy cached `df` property using `object.__setattr__()`. `UserQueryResult` adds mode-awareness (profiles vs. aggregate) which is unique but follows the precedent set by `FlowQueryResult` which has multiple DataFrame properties (`nodes_df`, `edges_df`, `df`).

**Alternatives considered**:
- Two separate result types (`ProfileResult`, `AggregateResult`) — rejected: forces callers to handle two types for what is conceptually one query; mode-aware single type is simpler
- Return raw dicts instead of a result type — rejected: breaks the unified result pattern and loses DataFrame conversion

**Key fields**:
- `computed_at: str` — ISO timestamp
- `total: int` — number of profiles returned (equals `len(profiles)`)
- `profiles: list[dict[str, Any]]` — normalized profile dicts (empty for aggregate mode)
- `params: dict[str, Any]` — engage API params used
- `meta: dict[str, Any]` — execution metadata (session_id, pages_fetched, etc.)
- `mode: Literal["profiles", "aggregate"]` — which mode produced this result
- `aggregate_data: dict[str, Any] | int | float | None` — raw aggregate value(s)

**Evidence**: `ResultWithDataFrame` base class at types.py:69-194. Existing result types: `QueryResult` (types.py:8900-9024), `FunnelQueryResult` (types.py:9316-9450), `RetentionQueryResult` (types.py:9521-9700), `FlowQueryResult` (types.py:10159-10400+).

---

## R6: Validation Architecture

**Decision**: Create `_internal/query/user_validators.py` with `validate_user_args()` function implementing rules U1-U24.

**Rationale**: Follows the exact pattern of `validate_query_args()` and `validate_funnel_args()` — collects all errors into `list[ValidationError]`, checks severity, raises `BookmarkValidationError` when any severity="error" item exists.

**Layer 2 validation**: The engage API doesn't use bookmark JSON format, so `validate_bookmark()` doesn't apply. Instead, a lightweight `validate_user_params()` function checks the generated engage params dict (rules UP1-UP4).

**Evidence**: `BookmarkValidationError` at exceptions.py:1062-1131. `validate_query_args()` at workspace.py:1742-2100. Two-layer validation pattern in `_resolve_and_build_params()` at workspace.py:2576-2700.

---

## R7: Parallel Execution Strategy

**Decision**: Use `concurrent.futures.ThreadPoolExecutor` with `as_completed()` directly in workspace.py private methods.

**Rationale**: The parallel fetch is a simple fan-out pattern: fetch page 0 sequentially for metadata, then dispatch remaining pages in parallel. `ThreadPoolExecutor` with max 5 workers matches the engage API's concurrency limit. Error tolerance (partial results) is implemented by catching exceptions per-future and recording failed pages in metadata.

**Alternatives considered**:
- `asyncio` with `httpx.AsyncClient` — rejected: the entire codebase uses synchronous httpx; adding async for one method creates an inconsistency. Listed as future consideration in design doc.
- `ParallelProfileFetcherService` (if one existed) — not applicable: no such service exists; the pattern is simple enough to handle inline

**Evidence**: Design document §7.3 details the parallel execution flow. `export_profiles_page()` is thread-safe (each call creates its own request). Rate limiting backoff in `_execute_with_retry()` handles 429s per-thread.

---

## R8: Property Name Normalization

**Decision**: Strip `$` prefix from Mixpanel built-in property names in DataFrame column headers.

**Rationale**: `$email` → `email`, `$name` → `name`, `$city` → `city` improves ergonomics. Users needing raw names can access `result.profiles` directly. The `properties` parameter accepts either form (`"$email"` or `"email"` both work).

**Evidence**: Design document §4.4 documents this behavior. The `transform_profile()` function (transforms.py:88-130) already extracts `$distinct_id` → `distinct_id` and `$last_seen` → `last_seen`, so this is consistent with existing normalization.
