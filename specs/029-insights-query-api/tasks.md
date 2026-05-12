# Tasks: Workspace.query() — Typed Insights Query API

**Input**: Design documents from `/specs/029-insights-query-api/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/public-api.md

**Tests**: Included (project requires strict TDD per CLAUDE.md)

**Organization**: Tasks grouped by user story for independent implementation and testing.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

---

## Phase 1: Setup

**Purpose**: No new project initialization needed — this feature adds to an existing codebase. Verify test infrastructure.

- [X] T001 Verify test infrastructure runs correctly with `just test -k "not slow"`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core type aliases, constants, and the QueryResult base that ALL user stories depend on.

**CRITICAL**: No user story work can begin until this phase is complete.

- [X] T002 [P] Add `MathType`, `PerUserAggregation`, `FilterPropertyType` type aliases and `PROPERTY_MATH_TYPES`, `NO_PER_USER_MATH_TYPES` constants to `src/mixpanel_data/types.py`
- [X] T003 [P] Add `QueryResult` frozen dataclass extending `ResultWithDataFrame` with fields `computed_at`, `from_date`, `to_date`, `headers`, `series`, `params`, `meta` and lazy `df` property to `src/mixpanel_data/types.py`
- [X] T004 [P] Add `insights_query()` method to `src/mixpanel_data/_internal/api_client.py` — POST to `/api/query/insights` with `inject_project_id=False`, body `{"bookmark": params, "project_id": id, "queryLimits": {"limit": 3000}}`
- [X] T005 Add `_transform_query_result()` function to `src/mixpanel_data/_internal/services/live_query.py` — extract nested `date_range.from_date`/`to_date`, copy `computed_at`, `headers`, `series`, `meta`

**Checkpoint**: Foundation ready — type system and API plumbing in place.

---

## Phase 3: User Story 1 — Simple Event Query (Priority: P1) MVP

**Goal**: A developer queries a single event with just an event name and receives structured daily counts for the last 30 days.

**Independent Test**: Call `query("Login")` with a mocked API response and verify the returned DataFrame has date, event, and count columns.

### Tests for User Story 1

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [X] T006 [P] [US1] Write unit tests for `Metric` dataclass construction, defaults, and immutability in `tests/test_query_types.py`
- [X] T007 [P] [US1] Write unit tests for time range validation rules (V7-V11: positive last, date format, to_date requires from_date, no conflicting dates+last) in `tests/test_query_validation.py`
- [X] T008 [P] [US1] Write unit tests for basic bookmark params generation — single event, relative time (last N), absolute time (from/to), time unit mapping — in `tests/test_query_params.py`
- [X] T009 [P] [US1] Write integration tests for end-to-end `query("EventName")` with mocked HTTP response (timeseries shape) in `tests/test_query_integration.py`
- [X] T009b [P] [US1] Write integration test for query with non-existent event name — verify empty DataFrame returned, no exception raised — in `tests/test_query_integration.py`

### Implementation for User Story 1

- [X] T010 [US1] Add `Metric` frozen dataclass to `src/mixpanel_data/types.py` with fields `event`, `math`, `property`, `per_user`, `filters`
- [X] T011 [US1] Add `_validate_query_args()` private method to `src/mixpanel_data/workspace.py` — implement time range validation rules V7-V11
- [X] T012 [US1] Add `_build_query_params()` private method to `src/mixpanel_data/workspace.py` — generate bookmark params for single event with time range (sections.show, sections.time, displayOptions)
- [X] T013 [US1] Add `query()` public method to `src/mixpanel_data/workspace.py` — validate args, build params, delegate to service, return QueryResult
- [X] T014 [US1] Add `query()` method to `src/mixpanel_data/_internal/services/live_query.py` — call `api_client.insights_query()`, transform response via `_transform_query_result()`
- [X] T015 [US1] Add `Metric`, `QueryResult`, `MathType`, `PerUserAggregation` exports to `src/mixpanel_data/__init__.py`

**Checkpoint**: `ws.query("Login")` works end-to-end with all defaults. MVP complete.

---

## Phase 4: User Story 2 — Aggregation Control (Priority: P1)

**Goal**: A developer controls aggregation: unique users, DAU/WAU/MAU, property math (average, sum, percentiles), and per-user pre-aggregation.

**Independent Test**: Call `query("Login", math="dau")` and verify the result series key includes the DAU math label.

### Tests for User Story 2

- [X] T016 [P] [US2] Write unit tests for aggregation validation rules (V1-V3: property math requires property, non-property math rejects property, per_user incompatible with DAU/WAU/MAU) in `tests/test_query_validation.py`
- [X] T017 [P] [US2] Write unit tests for aggregation params generation — math types, math_property mapping to `measurement.property`, per_user mapping to `measurement.perUserAggregation` — in `tests/test_query_params.py`
- [X] T018 [P] [US2] Write unit tests for per-Metric validation (V13-V14: same rules applied per Metric object) in `tests/test_query_validation.py`

### Implementation for User Story 2

- [X] T019 [US2] Extend `_validate_query_args()` in `src/mixpanel_data/workspace.py` with validation rules V1-V3 (global) and V13-V14 (per-Metric)
- [X] T020 [US2] Extend `_build_query_params()` in `src/mixpanel_data/workspace.py` to map `math`, `math_property`, `per_user` into `sections.show[].measurement` fields
- [X] T021 [US2] Handle event resolution in `_build_query_params()` — plain strings inherit top-level math/math_property/per_user; Metric objects override

**Checkpoint**: All counting math (total, unique, dau, wau, mau), property math (average, sum, p90, etc.), and per-user aggregation work.

---

## Phase 5: User Story 3 — Filtering and Breakdown (Priority: P1)

**Goal**: A developer filters results by property conditions and breaks down results by property values, including numeric bucketing.

**Independent Test**: Call `query("Purchase", where=[Filter.equals("country", "US")], group_by="platform")` and verify the params contain correct filter and group sections.

### Tests for User Story 3

- [X] T022 [P] [US3] Write unit tests for `Filter` class method construction — all 11 methods, correct internal state, immutability — in `tests/test_query_types.py`
- [X] T023 [P] [US3] Write unit tests for `GroupBy` dataclass construction, bucketing validation (V11-V12), and defaults in `tests/test_query_types.py`
- [X] T024 [P] [US3] Write unit tests for filter params generation — filterType/filterOperator/filterValue format per operator, string array vs scalar vs null — in `tests/test_query_params.py`
- [X] T025 [P] [US3] Write unit tests for group params generation — string shorthand, typed GroupBy, numeric bucketing with customBucket, multiple breakdowns — in `tests/test_query_params.py`

### Implementation for User Story 3

- [X] T026 [US3] Add `Filter` frozen dataclass with all 11 class methods (`equals`, `not_equals`, `contains`, `not_contains`, `greater_than`, `less_than`, `between`, `is_set`, `is_not_set`, `is_true`, `is_false`) to `src/mixpanel_data/types.py`
- [X] T027 [US3] Add `GroupBy` frozen dataclass to `src/mixpanel_data/types.py`
- [X] T028 [US3] Extend `_validate_query_args()` in `src/mixpanel_data/workspace.py` with GroupBy validation rules V11-V12
- [X] T029 [US3] Extend `_build_query_params()` in `src/mixpanel_data/workspace.py` to build `sections.filter[]` from `where` parameter (Filter → bookmark filter JSON)
- [X] T030 [US3] Extend `_build_query_params()` in `src/mixpanel_data/workspace.py` to build `sections.group[]` from `group_by` parameter (string/GroupBy → bookmark group JSON)
- [X] T031 [US3] Add `Filter`, `GroupBy`, `FilterPropertyType` exports to `src/mixpanel_data/__init__.py`

**Checkpoint**: Filtering (string, numeric, boolean, existence) and breakdowns (string, numeric with buckets, multiple) work.

---

## Phase 6: User Story 4 — Multi-Metric Comparison (Priority: P2)

**Goal**: A developer compares multiple events side-by-side, each with optional per-event aggregation and filters.

**Independent Test**: Call `query(["Signup", "Login", "Purchase"], math="unique")` and verify the params contain three entries in `sections.show[]`.

### Tests for User Story 4

- [X] T032 [P] [US4] Write unit tests for multi-event params generation — list of strings, list of Metrics, mixed list, per-event filters in `behavior.filters[]` — in `tests/test_query_params.py`
- [X] T033 [P] [US4] Write integration test for multi-event query with mocked response containing multiple series keys in `tests/test_query_integration.py`

### Implementation for User Story 4

- [X] T034 [US4] Extend `_build_query_params()` in `src/mixpanel_data/workspace.py` to handle `events` as `Sequence[str | Metric]` — generate one `sections.show[]` entry per event with per-event filters

**Checkpoint**: Multi-event queries with per-event aggregation and filters work.

---

## Phase 7: User Story 5 — Formula-Based Computed Metrics (Priority: P2)

**Goal**: A developer defines computed metrics via formula expressions referencing events by position letter (A, B, C...).

**Independent Test**: Call `query([Metric("Signup", math="unique"), Metric("Purchase", math="unique")], formula="(B / A) * 100")` and verify params have `isHidden: true` on metrics and a formula entry in `sections.show[]`.

### Tests for User Story 5

- [X] T035 [P] [US5] Write unit tests for formula validation (V4: requires 2+ events) in `tests/test_query_validation.py`
- [X] T036 [P] [US5] Write unit tests for formula params generation — formula appended to `sections.show[]`, `isHidden: true` on input metrics, `formula_label` mapping — in `tests/test_query_params.py`
- [X] T037 [P] [US5] Write integration test for formula query with mocked response (hidden metrics absent from series, formula result present) in `tests/test_query_integration.py`

### Implementation for User Story 5

- [X] T038 [US5] Extend `_validate_query_args()` in `src/mixpanel_data/workspace.py` with validation rule V4 (formula requires 2+ events)
- [X] T039 [US5] Extend `_build_query_params()` in `src/mixpanel_data/workspace.py` to handle `formula` — append formula entry to `sections.show[]`, mark input metrics `isHidden: true`, map `formula_label`

**Checkpoint**: Formula-based computed metrics (conversion rates, ratios) work.

---

## Phase 8: User Story 6 — Advanced Analysis Modes (Priority: P2)

**Goal**: A developer applies rolling window averages or cumulative analysis to any query.

**Independent Test**: Call `query("Signup", rolling=7)` and verify `displayOptions.analysis` is `"rolling"` and `rollingWindowSize` is `7`.

### Tests for User Story 6

- [X] T040 [P] [US6] Write unit tests for analysis mode validation (V5: mutual exclusion, V6: positive rolling) in `tests/test_query_validation.py`
- [X] T041 [P] [US6] Write unit tests for analysis mode params — `rolling` → `analysis: "rolling"` + `rollingWindowSize`, `cumulative` → `analysis: "cumulative"`, neither → `analysis: "linear"` — in `tests/test_query_params.py`

### Implementation for User Story 6

- [X] T042 [US6] Extend `_validate_query_args()` in `src/mixpanel_data/workspace.py` with validation rules V5-V6
- [X] T043 [US6] Extend `_build_query_params()` in `src/mixpanel_data/workspace.py` to map `rolling`/`cumulative` into `displayOptions.analysis` and `displayOptions.rollingWindowSize`

**Checkpoint**: Rolling window and cumulative analysis modes work.

---

## Phase 9: User Story 7 — Result Mode Selection (Priority: P2)

**Goal**: A developer controls result shape via `mode` — timeseries (per-period), total (single aggregate), or table.

**Independent Test**: Call `query("Purchase", math="unique", mode="total")` and verify `displayOptions.chartType` is `"bar"` and QueryResult.df has a single row per metric.

### Tests for User Story 7

- [X] T044 [P] [US7] Write unit tests for mode→chartType mapping (`timeseries`→`line`, `total`→`bar`, `table`→`table`) in `tests/test_query_params.py`
- [X] T045 [P] [US7] Write unit tests for `QueryResult.df` behavior per mode — timeseries returns (date, event, count) rows, total returns (event, count) rows — in `tests/test_query_types.py`
- [X] T046 [P] [US7] Write integration test for total-mode query with mocked response (`{"all": value}` series shape) in `tests/test_query_integration.py`

### Implementation for User Story 7

- [X] T047 [US7] Extend `_build_query_params()` in `src/mixpanel_data/workspace.py` to map `mode` parameter to `displayOptions.chartType`
- [X] T048 [US7] Extend `QueryResult.df` property in `src/mixpanel_data/types.py` to handle total mode (`{"all": value}`) — single row per metric without date column

**Checkpoint**: All three result modes (timeseries, total, table) work with correct DataFrame shapes.

---

## Phase 10: User Story 8 — Query Debugging and Persistence (Priority: P3)

**Goal**: A developer inspects generated query parameters and response metadata for debugging, and can persist queries as saved reports.

**Independent Test**: Run any query, verify `result.params` contains the bookmark dict and `result.meta` contains response metadata.

### Tests for User Story 8

- [X] T049 [P] [US8] Write unit tests verifying `QueryResult.params` contains the bookmark dict sent to the API in `tests/test_query_types.py`
- [X] T050 [P] [US8] Write integration test verifying `result.params` can be passed to `create_bookmark()` successfully in `tests/test_query_integration.py`

### Implementation for User Story 8

- [X] T051 [US8] Verify `_transform_query_result()` in `src/mixpanel_data/_internal/services/live_query.py` populates `params` (from request) and `meta` (from response) on QueryResult
- [X] T052 [US8] Add docstring examples to `QueryResult` in `src/mixpanel_data/types.py` showing `.params` inspection and `create_bookmark()` persistence pattern

**Checkpoint**: Query results expose params and metadata. Persistence via create_bookmark(params=result.params) works.

---

## Phase 11: Polish & Cross-Cutting Concerns

**Purpose**: Comprehensive testing, documentation, and quality verification.

- [X] T053 [P] Write property-based tests for type invariants (valid Metric → valid params, valid Filter → correct filterValue format, validation exhaustiveness) in `tests/test_query_pbt.py`
- [X] T054 [P] Add complete docstrings (Google style) to all public types (`Metric`, `Filter`, `GroupBy`, `QueryResult`) and the `query()` method per CLAUDE.md standards
- [X] T055 Verify all exports in `src/mixpanel_data/__init__.py` — `Metric`, `Filter`, `GroupBy`, `QueryResult`, `MathType`, `PerUserAggregation`
- [X] T056 Run full test suite with coverage check — `just test-cov` — verify 90% threshold maintained
- [X] T057 Run `just check` (lint + typecheck + test) to ensure mypy --strict compliance
- [X] T058 Validate quickstart.md examples against implementation — verify all 12 example patterns produce valid params

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — verification only
- **Foundational (Phase 2)**: Depends on Phase 1 — BLOCKS all user stories
- **US1 (Phase 3)**: Depends on Phase 2 — MVP milestone
- **US2 (Phase 4)**: Depends on US1 (extends validation and params builder)
- **US3 (Phase 5)**: Depends on US1 (extends params builder). Can run in parallel with US2.
- **US4 (Phase 6)**: Depends on US2 (needs Metric aggregation handling)
- **US5 (Phase 7)**: Depends on US4 (formulas reference multiple metrics)
- **US6 (Phase 8)**: Depends on US1. Can run in parallel with US4, US5.
- **US7 (Phase 9)**: Depends on US1. Can run in parallel with US4, US5, US6.
- **US8 (Phase 10)**: Depends on US1. Can run in parallel with US2-US7.
- **Polish (Phase 11)**: Depends on all user stories being complete

### User Story Dependencies

```
Phase 2 (Foundational)
    └── US1 (Phase 3) ← MVP
         ├── US2 (Phase 4) ← extends aggregation
         │    └── US4 (Phase 6) ← multi-event
         │         └── US5 (Phase 7) ← formulas (needs multi-event)
         ├── US3 (Phase 5) ← can parallel with US2
         ├── US6 (Phase 8) ← can parallel with US2-US5
         ├── US7 (Phase 9) ← can parallel with US2-US6
         └── US8 (Phase 10) ← can parallel with US2-US7
```

### Within Each User Story

- Tests MUST be written and FAIL before implementation
- Type definitions before validation logic
- Validation logic before params building
- Params building before integration wiring

### Parallel Opportunities

- All foundational tasks T002-T005 can run in parallel
- Tests within each user story (marked [P]) can run in parallel
- US3 can run in parallel with US2
- US6, US7, US8 can all run in parallel with each other (and with US4/US5)
- All polish tasks marked [P] can run in parallel

---

## Parallel Example: User Story 3 (Filtering & Breakdown)

```bash
# Launch all tests for US3 together (all target different test files/sections):
Task: "Filter class method tests in tests/test_query_types.py"
Task: "GroupBy construction tests in tests/test_query_types.py"
Task: "Filter params generation tests in tests/test_query_params.py"
Task: "Group params generation tests in tests/test_query_params.py"

# Then implement sequentially:
Task: "Filter class in src/mixpanel_data/types.py"
Task: "GroupBy class in src/mixpanel_data/types.py"
Task: "Validation rules V11-V12"
Task: "Params builder: filter section"
Task: "Params builder: group section"
Task: "Exports"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (verify)
2. Complete Phase 2: Foundational (type aliases, QueryResult, API client, service)
3. Complete Phase 3: User Story 1 (simple event query end-to-end)
4. **STOP and VALIDATE**: `ws.query("Login")` returns a DataFrame with daily counts
5. This is a deployable increment — the simplest query works

### Incremental Delivery

1. Phase 2 → Foundation ready
2. US1 → Simple queries work → **MVP**
3. US2 → All aggregation types work (unique, DAU, property math)
4. US3 → Filtering and breakdowns work
5. US4 → Multi-metric comparison works
6. US5 → Formulas work (conversion rates, ratios)
7. US6+US7 → Rolling/cumulative + mode selection work (can parallel)
8. US8 → Debugging and persistence work
9. Polish → PBT, docstrings, coverage

Each increment adds value without breaking previous stories.

### Parallel Team Strategy

With multiple developers after Phase 2 completes:

- **Developer A**: US1 → US2 → US4 → US5 (aggregation → multi-event → formulas chain)
- **Developer B**: US3 (filtering/breakdown — independent of aggregation work)
- **Developer C**: US6 + US7 + US8 (analysis modes, result modes, debugging — all small and independent)

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- This feature is a single method (`query()`) with many parameters — user stories represent parameter groups, not independent endpoints
- TDD is mandatory per CLAUDE.md — all test tasks MUST produce failing tests before implementation
- Commit after each completed user story phase
- Run `just check` after each phase to catch regressions
