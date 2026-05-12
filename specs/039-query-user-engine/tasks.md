# Tasks: User Profile Query Engine

**Input**: Design documents from `/specs/039-query-user-engine/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: Required — this project follows strict TDD (CLAUDE.md: "Never write implementation code without a failing test first").

**Organization**: Tasks grouped by user story. Foundational infrastructure ships first, then each story adds capabilities incrementally.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

---

## Phase 1: Setup

**Purpose**: Create new module files with docstrings and `__init__` wiring

- [X] T001 Create module src/mixpanel_data/_internal/query/user_builders.py with module docstring and empty function signatures for filter_to_selector, filters_to_selector, extract_cohort_filter
- [X] T002 [P] Create module src/mixpanel_data/_internal/query/user_validators.py with module docstring and empty function signatures for validate_user_args, validate_user_params

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core types, translation, validation, and API client extensions that ALL user stories depend on

**CRITICAL**: No user story work can begin until this phase is complete

### Tests for Foundational Phase

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [X] T003 [P] Write UserQueryResult unit tests in tests/test_types_user_query_result.py — test DataFrame construction from profiles (column schema, $-prefix stripping, alphabetical property sorting), DataFrame from aggregate data (metric/value schema, segmented schema), empty profiles producing empty DataFrame with correct columns, distinct_ids property, value property, mode-aware behavior, to_dict() serialization, lazy caching via object.__setattr__
- [X] T004 [P] Write filter-to-selector translation unit tests in tests/test_user_builders.py — test each operator mapping (equals, not_equals, contains, not_contains, greater_than, less_than, between, is_set, is_not_set, is_true, is_false), multi-value equals producing OR chain, multiple filters AND combination, cohort filter extraction (saved ID and inline CohortDefinition), value formatting (strings with quotes, ints, floats, booleans), edge cases (special characters in values, empty property names)
- [X] T005 [P] Write validation rule unit tests in tests/test_user_validators.py — test each rule U1-U24 individually, mode-specific validation (aggregate params with profiles mode produces error, profile params with aggregate mode produces error), multiple simultaneous violations collected, valid argument combinations pass cleanly, Layer 2 rules UP1-UP4
- [X] T006 [P] Write API client engage_stats() and export_profiles_page() extension tests in tests/test_api_client_engage_stats.py — test engage_stats() POSTs to /engage with filter_type=stats and correct params, test export_profiles_page() passes sort_key/sort_order/search/limit/filter_by_cohort params, test filter_by_cohort supports both {"id": N} and {"raw_cohort": {...}} formats

### Implementation for Foundational Phase

- [X] T007 [P] Implement UserQueryResult frozen dataclass extending ResultWithDataFrame in src/mixpanel_data/types.py — fields: computed_at, total, profiles, params, meta, mode, aggregate_data; lazy cached df property using object.__setattr__; distinct_ids property; value property; to_dict method; mode-aware DataFrame construction (profiles: distinct_id/last_seen/properties with $-stripping; aggregate: metric/value or segment/value)
- [X] T008 [P] Implement filter_to_selector(), filters_to_selector(), extract_cohort_filter() in src/mixpanel_data/_internal/query/user_builders.py — translate Filter._operator to engage selector syntax per operator mapping table in research.md R2; AND-combine multiple filters; extract Filter.in_cohort() from filter list and route to filter_by_cohort param; handle CohortDefinition via to_dict(); value formatting for str/int/float/bool types
- [X] T009 [P] Implement validate_user_args() with rules U1-U24 and validate_user_params() with rules UP1-UP4 in src/mixpanel_data/_internal/query/user_validators.py — follow validate_query_args() pattern: return list[ValidationError], use existing ValidationError and BookmarkValidationError types, include mode-specific cross-validation
- [X] T010 Extend API client in src/mixpanel_data/_internal/api_client.py — add engage_stats() method that POSTs to /engage with filter_type=stats accepting where/action/filter_by_cohort/segment_by_cohorts/group_id/as_of_timestamp/include_all_users params; add sort_key, sort_order, search, limit, filter_by_cohort parameters to export_profiles_page(); handle filter_by_cohort as JSON-encoded dict supporting both {"id": N} and {"raw_cohort": {...}}

**Checkpoint**: All foundational types, translation, validation, and API methods are tested and implemented. User story work can begin.

---

## Phase 3: User Story 1 - Query and Filter User Profiles (Priority: P1) MVP

**Goal**: Analysts can query user profiles using Filter vocabulary, get structured tabular results with property selection, sorting, search, limiting, and safe limit=1 default.

**Independent Test**: Filter users with property criteria and verify returned DataFrame contains correct profile data with distinct_id, last_seen, and requested properties.

### Tests for User Story 1

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [X] T011 [P] [US1] Write parameter builder unit tests in tests/test_workspace_build_user_params.py — test Filter translation to engage where param, cohort routing (saved ID → filter_by_cohort, CohortDefinition → raw_cohort), property selection → output_properties, sort_by → sort_key translation, as_of string → Unix timestamp conversion, distinct_id/distinct_ids handling, group_id → data_group_id, search passthrough, raw string where passthrough, validation errors raised as BookmarkValidationError
- [X] T012 [P] [US1] Write sequential query execution and public query_user() profiles mode tests in tests/test_workspace_query_user.py — test default limit=1 returns 1 profile + total count, explicit limit fetches correct number of profiles via pagination, property selection reduces DataFrame columns, sort_by/sort_order passed to API, search param passed to API, distinct_id lookup, distinct_ids batch lookup, group_id queries group profiles, as_of passes timestamp, result.total equals len(profiles), result.df has correct column schema, empty result returns empty DataFrame with correct columns, credentials check raises ConfigError when None

### Implementation for User Story 1

- [X] T013 [US1] Implement _resolve_and_build_user_params() private method in src/mixpanel_data/workspace.py — follow _resolve_and_build_params() pattern: type guards → normalize where (Filter/list/str) → call validate_user_args() → raise BookmarkValidationError if errors → build engage params dict via filter_to_selector/extract_cohort_filter → handle cohort (int → filter_by_cohort id, CohortDefinition → raw_cohort) → sort_by → sort_key translation → as_of → timestamp → call validate_user_params() → return params dict
- [X] T014 [US1] Implement _execute_user_query_sequential() private method in src/mixpanel_data/workspace.py — fetch page 0 via api_client.export_profiles_page() to get total/session_id/page_size; paginate sequentially until limit reached or pages exhausted; normalize profiles via transform_profile(); return (profiles, total, computed_at, meta)
- [X] T015 [US1] Implement public query_user() method (profiles mode, sequential only) in src/mixpanel_data/workspace.py — call _resolve_and_build_user_params(); check credentials (raise ConfigError if None); call _execute_user_query_sequential(); build and return UserQueryResult with mode="profiles"
- [X] T016 [US1] Implement public build_user_params() method in src/mixpanel_data/workspace.py — same signature as query_user() minus limit/parallel/workers; delegates to _resolve_and_build_user_params(); returns params dict without executing

**Checkpoint**: User Story 1 is fully functional. `ws.query_user(where=Filter.equals("plan", "premium"))` returns a UserQueryResult with .df, .total, .distinct_ids. Sequential pagination works. build_user_params() previews generated params.

---

## Phase 4: User Story 2 - Aggregate Statistics (Priority: P2)

**Goal**: Analysts can compute count/sum/mean/min/max across matching profiles without fetching individual records, with optional cohort segmentation.

**Independent Test**: Request a count of users matching a filter and verify the returned scalar value; request mean(ltv) segmented by cohorts and verify DataFrame rows.

### Tests for User Story 2

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [X] T017 [P] [US2] Write aggregate execution and query_user() aggregate mode tests in tests/test_workspace_query_user_aggregate.py — test count aggregate returns scalar value via result.value, sum/mean/min/max with aggregate_property, segmented aggregate returns DataFrame with segment/value columns, aggregate_property required for non-count (validation error U14), aggregate_property prohibited for count (U15), segment_by requires mode="aggregate" (U16), profile-only params rejected in aggregate mode (U18-U22), engage_stats() called with correct action expression (e.g., "mean(ltv)")

### Implementation for User Story 2

- [X] T018 [US2] Implement _execute_user_aggregate() private method in src/mixpanel_data/workspace.py — build stats params (filter_type=stats, action from aggregate/aggregate_property, segment_by_cohorts from segment_by); call api_client.engage_stats(); parse response (scalar or segmented dict); return (aggregate_data, total, computed_at, meta)
- [X] T019 [US2] Wire aggregate mode into query_user() in src/mixpanel_data/workspace.py — route mode="aggregate" to _execute_user_aggregate(); build UserQueryResult with mode="aggregate", aggregate_data, empty profiles list

**Checkpoint**: User Stories 1 AND 2 both work independently. `ws.query_user(aggregate="numeric_summary", aggregate_property="ltv")` returns result.aggregate_data with count, mean, and variance.

---

## Phase 5: User Story 3 - Behavioral Filtering (Priority: P2)

**Goal**: Analysts can filter users by behavioral criteria (e.g., "purchased 3+ times in 30 days") using typed CohortDefinition + CohortCriteria builders, with no raw query strings.

**Independent Test**: Define a behavioral cohort via CohortDefinition.all_of(CohortCriteria.did_event(...)) and verify returned profiles match criteria; verify CohortDefinition with OR logic works.

### Tests for User Story 3

- [X] T020 [US3] Write behavioral filtering integration tests in tests/test_workspace_query_user_integration.py — test cohort=CohortDefinition.all_of(CohortCriteria.did_event()) routes to filter_by_cohort with raw_cohort, test cohort=CohortDefinition.any_of() produces correct OR structure, test saved cohort by ID (cohort=12345) routes to filter_by_cohort with id, test combined cohort + where filters work together, test cohort + Filter.in_cohort() in where produces validation error U2, test CohortDefinition serialization failure produces validation error U24

**Checkpoint**: Behavioral filtering fully works. All three modes of cohort filtering (saved ID, inline definition, Filter.in_cohort) are tested and validated.

---

## Phase 6: User Story 4 - Parallel Fetching (Priority: P3)

**Goal**: Analysts can fetch large profile sets (5,000+) with concurrent page retrieval for up to 5x speedup, with graceful partial failure handling.

**Independent Test**: Request 5,000+ profiles with parallel=True and verify all profiles returned in single result set; simulate a page failure and verify partial results with failed_pages in metadata.

### Tests for User Story 4

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [X] T021 [P] [US4] Write parallel execution tests in tests/test_workspace_query_user_parallel.py — test single-page result skips parallel overhead, multi-page parallel fetch collects all profiles, limit-aware dispatch fetches only ceil(limit/page_size) pages, failed page handling returns partial results with meta["failed_pages"], worker cap enforcement (values > 5 rejected with validation error U23), rate limit warning when pages > 48, parallel=True with mode="aggregate" produces validation error U18, early exit when limit reached mid-fetch

### Implementation for User Story 4

- [X] T022 [US4] Implement _execute_user_query_parallel() private method in src/mixpanel_data/workspace.py — fetch page 0 sequentially for metadata (total, session_id, page_size); calculate pages needed (limit-aware); cap workers at min(workers, 5); dispatch pages 1..N via ThreadPoolExecutor; collect via as_completed(); handle per-future exceptions (record in failed_pages, log warning); log rate limit warning if pages > 48; truncate to limit; return (profiles, total, computed_at, meta)
- [X] T023 [US4] Wire parallel mode into query_user() in src/mixpanel_data/workspace.py — route parallel=True + mode="profiles" to _execute_user_query_parallel(); pass workers param; build UserQueryResult with parallel metadata

**Checkpoint**: Parallel fetching works. Large result sets complete significantly faster with parallel=True.

---

## Phase 7: User Story 5 - Cross-Engine Composition (Priority: P3)

**Goal**: Profile query results compose naturally with other engine outputs through shared identifiers and DataFrame operations.

**Independent Test**: Run an insights query, extract a segment value, use it as a Filter in query_user(), and verify returned profiles match.

- [X] T024 [US5] Write cross-engine composition integration tests in tests/test_workspace_query_user_integration.py — test result.distinct_ids returns list usable for downstream operations, test result.df composes with pandas operations (groupby, merge, describe), test Filter objects work identically across query() and query_user(), test cohort ID from funnel analysis works as query_user(cohort=ID)

**Checkpoint**: All 5 user stories work independently and compose together.

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Property-based tests, public exports, quality gates

- [X] T025 [P] Write property-based tests in tests/test_user_query_pbt.py — invariants: filter_to_selector() always produces syntactically valid selector for any Filter; .df has exactly len(profiles) rows for any profile list; distinct_id column always present; properties param limits columns to selection + distinct_id + last_seen; total >= len(profiles) always; aggregate .value matches first row of .df
- [X] T026 Export UserQueryResult from public API in src/mixpanel_data/__init__.py — add to __all__ and import statement
- [X] T027 Run `just check` to verify all lint, typecheck, and test quality gates pass
- [X] T028 Validate quickstart.md examples against implementation — verify code samples in specs/039-query-user-engine/quickstart.md are accurate and complete

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — can start immediately
- **Foundational (Phase 2)**: Depends on Setup — BLOCKS all user stories
- **US1 (Phase 3)**: Depends on Foundational — delivers MVP
- **US2 (Phase 4)**: Depends on Foundational — can run parallel with US1 after T013 (param builder)
- **US3 (Phase 5)**: Depends on US1 (uses param builder and query_user)
- **US4 (Phase 6)**: Depends on US1 (extends query_user with parallel mode)
- **US5 (Phase 7)**: Depends on US1 (integration tests use query_user)
- **Polish (Phase 8)**: Depends on all user stories being complete

### User Story Dependencies

- **US1 (P1)**: Start after Foundational — no dependencies on other stories
- **US2 (P2)**: Start after Foundational — independent of US1 (uses different execution path), but shares param builder
- **US3 (P2)**: Start after US1 — integration tests need working query_user()
- **US4 (P3)**: Start after US1 — extends sequential execution with parallel mode
- **US5 (P3)**: Start after US1 — integration tests need working query_user()

### Within Each User Story

- Tests MUST be written and FAIL before implementation
- Validation/translation before execution methods
- Private methods before public methods
- Core implementation before mode wiring

### Parallel Opportunities

- **Phase 2 tests** (T003-T006): All [P] — 4 different test files
- **Phase 2 implementation** (T007-T009): All [P] — 3 different source files
- **US1 tests** (T011, T012): [P] — 2 different test files
- **US2 and US4 stories**: Can proceed in parallel after US1 is complete
- **Phase 8** (T025, T026): [P] — different files

---

## Parallel Example: Foundational Phase

```
# Wave 1 — All foundational tests in parallel (4 agents):
Agent 1: T003 — UserQueryResult tests in tests/test_types_user_query_result.py
Agent 2: T004 — Filter→selector tests in tests/test_user_builders.py
Agent 3: T005 — Validation tests in tests/test_user_validators.py
Agent 4: T006 — API client tests in tests/test_api_client_engage_stats.py

# Wave 2 — All foundational implementations in parallel (3 agents):
Agent 1: T007 — UserQueryResult type in src/mixpanel_data/types.py
Agent 2: T008 — filter_to_selector in src/mixpanel_data/_internal/query/user_builders.py
Agent 3: T009 — validate_user_args in src/mixpanel_data/_internal/query/user_validators.py

# Wave 3 — API client (touches same file, sequential):
Agent 1: T010 — API client extensions in src/mixpanel_data/_internal/api_client.py
```

## Parallel Example: User Story 1

```
# Wave 1 — US1 tests in parallel (2 agents):
Agent 1: T011 — Parameter builder tests in tests/test_workspace_build_user_params.py
Agent 2: T012 — Sequential execution tests in tests/test_workspace_query_user.py

# Wave 2 — US1 implementation (sequential — all in workspace.py):
T013 → T014 → T015 → T016
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (T001-T002)
2. Complete Phase 2: Foundational (T003-T010)
3. Complete Phase 3: User Story 1 (T011-T016)
4. **STOP and VALIDATE**: `ws.query_user(where=Filter.equals("plan", "premium"))` works end-to-end
5. Run `just check` to verify quality gates

### Incremental Delivery

1. Setup + Foundational → Building blocks ready
2. Add US1 → Profile querying works → **MVP!**
3. Add US2 → Aggregate statistics available
4. Add US3 → Behavioral filtering verified
5. Add US4 → Parallel fetching for large result sets
6. Add US5 → Cross-engine composition verified
7. Polish → PBT tests, exports, quality gates

### Parallel Team Strategy

With multiple agents:

1. All complete Setup + Foundational together
2. Once Foundational is done:
   - Agent A: US1 (Profile Querying) — must complete first
   - After US1 complete:
     - Agent A: US2 (Aggregate Statistics)
     - Agent B: US4 (Parallel Fetching)
     - Agent C: US3 + US5 (Integration tests)
3. Polish phase after all stories complete

---

## Notes

- [P] tasks = different files, no dependencies on incomplete tasks in same phase
- [Story] label maps task to specific user story for traceability
- Tests MUST fail before implementation begins (strict TDD)
- Study existing test patterns before writing new tests (CLAUDE.md requirement)
- All code must pass mypy --strict, ruff check, ruff format
- All public functions need docstrings with Args/Returns/Raises/Example sections
- Coverage minimum: 90%, mutation score target: 80%
- Commit after each task or logical group
