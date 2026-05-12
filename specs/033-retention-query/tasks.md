# Tasks: Retention Query (`query_retention()`)

**Input**: Design documents from `/specs/033-retention-query/`
**Prerequisites**: plan.md, spec.md, data-model.md, contracts/public-api.md, research.md, quickstart.md

**Tests**: Required — this project enforces strict TDD (CLAUDE.md: "Never write implementation code without a failing test first").

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

- **Source**: `src/mixpanel_data/` (library code)
- **Tests**: `tests/` (test files)
- All paths relative to repository root

---

## Phase 1: Setup

**Purpose**: No project initialization needed — this extends an existing project. This phase verifies prerequisites.

- [X] T001 Verify existing shared infrastructure is available: confirm `build_time_section`, `build_filter_section`, `build_group_section`, `build_filter_entry` exist in `src/mixpanel_data/_internal/bookmark_builders.py`
- [X] T002 Verify existing retention enums are in place: confirm `VALID_MATH_RETENTION`, `VALID_RETENTION_UNITS`, `VALID_RETENTION_ALIGNMENT` exist in `src/mixpanel_data/_internal/bookmark_enums.py`
- [X] T003 Verify `validate_time_args` and `validate_group_by_args` shared validators exist in `src/mixpanel_data/_internal/validation.py`

---

## Phase 2: Foundational (Types)

**Purpose**: Define new types that ALL user stories depend on. Must complete before any user story.

**CRITICAL**: No user story work can begin until this phase is complete.

### Tests for Foundational Types

- [X] T004 [P] Write `RetentionEvent` unit tests (construction, defaults, immutability, field preservation, filters handling) in `tests/test_types_retention.py`
- [X] T005 [P] Write `RetentionQueryResult` unit tests (construction, defaults, immutability, `.df` columns/shape/caching, `.average` field, `.to_dict()`, empty cohorts edge case) in `tests/test_types_retention.py`
- [X] T006 [P] Write `RetentionMathType` type alias validation tests (valid values accepted, invalid rejected at validation layer) in `tests/test_types_retention.py`

### Implementation for Foundational Types

- [X] T007 Implement `RetentionEvent` frozen dataclass (event, filters, filters_combinator) in `src/mixpanel_data/types.py`
- [X] T008 Implement `RetentionMathType` Literal type alias (`"retention_rate"`, `"unique"`) in `src/mixpanel_data/types.py`
- [X] T009 Implement `RetentionQueryResult` frozen dataclass extending `ResultWithDataFrame` (computed_at, from_date, to_date, cohorts, average, params, meta, `.df` property with lazy caching) in `src/mixpanel_data/types.py`
- [X] T010 Run tests to verify Phase 2 types pass: `just test -k test_types_retention`

**Checkpoint**: All three types exist and pass their unit tests.

---

## Phase 3: User Story 1 — Simple Retention Query (Priority: P1) MVP

**Goal**: Users can call `query_retention("Signup", "Login")` with minimal args and get a structured `RetentionQueryResult` with cohort data and DataFrame.

**Independent Test**: Call `query_retention("Signup", "Login")` with mocked API client and verify the result contains correct cohort data, retention rates, and well-shaped DataFrame.

### Tests for User Story 1

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [X] T011 [P] [US1] Write validation tests for R1 (born_event non-empty, control chars, invisible) in `tests/test_validation_retention.py`
- [X] T012 [P] [US1] Write validation tests for R2 (return_event non-empty, control chars, invisible) in `tests/test_validation_retention.py`
- [X] T013 [P] [US1] Write validation tests for R7 (retention_unit valid), R8 (alignment valid), R9 (math valid) in `tests/test_validation_retention.py`
- [X] T014 [P] [US1] Write validation tests for shared delegation: R3 (time args via `validate_time_args`) and R4 (group_by via `validate_group_by_args`) in `tests/test_validation_retention.py`
- [X] T015 [P] [US1] Write bookmark builder tests for default structure: behavior type="retention", 2 behaviors (born/return), retentionUnit, retentionAlignmentType, measurement math, chart type in `tests/test_build_retention_params.py`
- [X] T016 [P] [US1] Write bookmark builder tests for time section, empty filter section, empty group section using shared builders in `tests/test_build_retention_params.py`
- [X] T017 [P] [US1] Write response transformer tests: basic response parsing (computed_at, from_date, to_date, cohorts extraction, average extraction, params preservation, meta) in `tests/test_transform_retention.py`
- [X] T018 [P] [US1] Write response transformer tests: error handling (error key raises QueryError, missing series raises QueryError, empty response) in `tests/test_transform_retention.py`
- [X] T019 [P] [US1] Write workspace integration tests: correct body sent to API (bookmark, project_id, queryLimits), result is RetentionQueryResult, credentials validation in `tests/test_workspace_retention.py`

### Implementation for User Story 1

- [X] T020 [US1] Implement `validate_retention_args()` with rules R1, R2, R7, R8, R9 and delegation to `validate_time_args`/`validate_group_by_args` in `src/mixpanel_data/_internal/validation.py`
- [X] T021 [US1] Extend `validate_bookmark()` to use `VALID_MATH_RETENTION` when `bookmark_type="retention"` in `src/mixpanel_data/_internal/validation.py`
- [X] T022 [US1] Implement `_build_retention_params()` — build retention bookmark JSON with behavior type="retention", 2 behaviors, retentionUnit, retentionAlignmentType, retentionCustomBucketSizes=[], measurement, time/filter/group sections in `src/mixpanel_data/workspace.py`
- [X] T023 [US1] Implement `_transform_retention_result()` — parse API response, extract cohort data and `$average`, handle format variations, produce `RetentionQueryResult` in `src/mixpanel_data/_internal/services/live_query.py`
- [X] T024 [US1] Implement `query_retention()` service method on `LiveQueryService` — build body, call `insights_query()`, transform response in `src/mixpanel_data/_internal/services/live_query.py`
- [X] T025 [US1] Implement `_resolve_and_build_retention_params()` — normalize events, Layer 1 validation, build params, Layer 2 validation in `src/mixpanel_data/workspace.py`
- [X] T026 [US1] Implement `query_retention()` public method on `Workspace` — delegate to `_resolve_and_build_retention_params()` then `_live_query_service.query_retention()` in `src/mixpanel_data/workspace.py`
- [X] T027 [US1] Run all US1 tests to verify: `just test -k "test_validation_retention or test_build_retention or test_transform_retention or test_workspace_retention"`

**Checkpoint**: `query_retention("Signup", "Login")` works end-to-end with mocked API. MVP is functional.

---

## Phase 4: User Story 2 — Filters and Segmentation (Priority: P2)

**Goal**: Users can add per-event filters via `RetentionEvent`, global filters via `where`, and breakdowns via `group_by`.

**Independent Test**: Call `query_retention()` with `RetentionEvent` objects, `where` filters, and `group_by` and verify bookmark params contain correct filter/group sections and per-event filters in behavior entries.

### Tests for User Story 2

- [X] T028 [P] [US2] Write builder tests for per-event filters: RetentionEvent with filters produces non-empty filters array in behavior entry, filters_combinator maps to filtersDeterminer in `tests/test_build_retention_params.py`
- [X] T029 [P] [US2] Write builder tests for global where filter: Filter objects produce filter section entries in `tests/test_build_retention_params.py`
- [X] T030 [P] [US2] Write builder tests for group_by: string and GroupBy objects produce group section entries in `tests/test_build_retention_params.py`
- [X] T031 [P] [US2] Write workspace integration test for per-event filters and segmented queries in `tests/test_workspace_retention.py`

### Implementation for User Story 2

- [X] T032 [US2] Add per-event filter handling in `_build_retention_params()` — convert RetentionEvent.filters to behavior entry filters using `build_filter_entry()` in `src/mixpanel_data/workspace.py`
- [X] T033 [US2] Run US2 tests: `just test -k "test_build_retention_params or test_workspace_retention"`

**Checkpoint**: Filters and group_by work in retention queries.

---

## Phase 5: User Story 3 — Custom Bucket Sizes (Priority: P2)

**Goal**: Users can pass `bucket_sizes=[1, 3, 7, 14, 30]` for non-uniform retention periods.

**Independent Test**: Call `query_retention()` with `bucket_sizes` and verify the bookmark params contain `retentionCustomBucketSizes` with the correct values.

### Tests for User Story 3

- [X] T034 [P] [US3] Write validation tests for R5 (bucket_sizes positive integers, float rejection) and R6 (strictly ascending order, duplicates rejected) in `tests/test_validation_retention.py`
- [X] T035 [P] [US3] Write builder tests for bucket_sizes: populates `retentionCustomBucketSizes` in behavior block, None produces empty list in `tests/test_build_retention_params.py`

### Implementation for User Story 3

- [X] T036 [US3] Add R5 and R6 validation rules to `validate_retention_args()` in `src/mixpanel_data/_internal/validation.py`
- [X] T037 [US3] Add `bucket_sizes` handling in `_build_retention_params()` — populate `retentionCustomBucketSizes` in `src/mixpanel_data/workspace.py`
- [X] T038 [US3] Run US3 tests: `just test -k "test_validation_retention or test_build_retention_params"`

**Checkpoint**: Custom bucket sizes validated and included in bookmark params.

---

## Phase 6: User Story 4 — Build Params Without Executing (Priority: P3)

**Goal**: Users can call `build_retention_params()` to inspect generated bookmark JSON without querying the API.

**Independent Test**: Call `build_retention_params("Signup", "Login")` and verify it returns a dict, makes no API call, and matches what `query_retention()` would send.

### Tests for User Story 4

- [X] T039 [P] [US4] Write tests for `build_retention_params()`: returns dict (not result), has sections/displayOptions keys, no API call made in `tests/test_workspace_retention.py`
- [X] T040 [P] [US4] Write consistency test: `build_retention_params()` output matches `query_retention()` bookmark params in `tests/test_workspace_retention.py`

### Implementation for User Story 4

- [X] T041 [US4] Implement `build_retention_params()` public method on `Workspace` — same signature as `query_retention()` but returns dict from `_resolve_and_build_retention_params()` in `src/mixpanel_data/workspace.py`
- [X] T042 [US4] Run US4 tests: `just test -k test_workspace_retention`

**Checkpoint**: `build_retention_params()` works and is consistent with `query_retention()`.

---

## Phase 7: User Story 5 — Fail-Fast Validation (Priority: P3)

**Goal**: Invalid inputs are caught before API calls with structured, actionable errors including codes, paths, and suggestions.

**Independent Test**: Call `query_retention()` with multiple invalid inputs and verify all errors are collected and returned together with correct codes.

### Tests for User Story 5

- [X] T043 [P] [US5] Write multi-error collection tests: multiple simultaneous validation failures (e.g., empty born_event + invalid unit) all returned in single BookmarkValidationError in `tests/test_validation_retention.py`
- [X] T044 [P] [US5] Write validation error structure tests: error code format, path accuracy, suggestion presence for enum validation (R7, R8, R9) in `tests/test_validation_retention.py`
- [X] T045 [P] [US5] Write workspace validation integration test: BookmarkValidationError raised before API call, API client never called in `tests/test_workspace_retention.py`

### Implementation for User Story 5

- [X] T046 [US5] Review and verify error codes, paths, and suggestions in `validate_retention_args()` match contracts/public-api.md error code table in `src/mixpanel_data/_internal/validation.py`
- [X] T047 [US5] Run US5 tests: `just test -k "test_validation_retention or test_workspace_retention"`

**Checkpoint**: All invalid inputs produce structured, actionable errors.

---

## Phase 8: User Story 6 — Result Display Modes (Priority: P3)

**Goal**: Users can request retention data in different display formats: curve (default), trends, or table.

**Independent Test**: Call `query_retention()` with each mode value and verify the bookmark params contain the correct `chartType`.

### Tests for User Story 6

- [X] T048 [P] [US6] Write builder tests for mode→chartType mapping: curve→retention-curve, trends→line, table→table in `tests/test_build_retention_params.py`

### Implementation for User Story 6

- [X] T049 [US6] Add mode→chartType mapping in `_build_retention_params()` displayOptions in `src/mixpanel_data/workspace.py`
- [X] T050 [US6] Run US6 tests: `just test -k test_build_retention_params`

**Checkpoint**: All three display modes produce correct chart types.

---

## Phase 9: Polish & Cross-Cutting Concerns

**Purpose**: Property-based tests, exports, comprehensive quality checks.

- [X] T051 [P] Write Hypothesis PBT tests for `RetentionEvent` (immutability, equality, field preservation across random inputs) in `tests/test_types_retention_pbt.py`
- [X] T052 [P] Write Hypothesis PBT tests for `RetentionQueryResult` (DataFrame row count matches cohorts, column count always 4, deterministic conversion) in `tests/test_types_retention_pbt.py`
- [X] T053 [P] Write Hypothesis PBT tests for `_build_retention_params` invariants (always has sections/displayOptions, behavior count always 2, chart type always valid) in `tests/test_types_retention_pbt.py`
- [X] T054 [P] Write response transformer tests for format variations: direct cohort dict, nested `$overall`, segmented format, insights API wrapper format in `tests/test_transform_retention.py`
- [X] T055 Add `RetentionEvent`, `RetentionMathType`, `RetentionQueryResult` exports to `src/mixpanel_data/__init__.py`
- [X] T056 Verify all docstrings complete for new types, methods, and functions per CLAUDE.md standards
- [X] T057 Run full quality check: `just check` (lint + typecheck + test)
- [X] T058 Run test coverage check: `just test-cov` (must be >= 90%)
- [X] T059 Run quickstart.md validation: verify all code examples from `specs/033-retention-query/quickstart.md` are syntactically valid

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — verification only
- **Foundational (Phase 2)**: Depends on Setup — defines types all stories need
- **US1 (Phase 3)**: Depends on Foundational — core pipeline MVP
- **US2 (Phase 4)**: Depends on US1 — adds filter/segmentation handling
- **US3 (Phase 5)**: Depends on US1 — adds bucket_sizes to validation + builder
- **US4 (Phase 6)**: Depends on US1 — adds build_retention_params() public method
- **US5 (Phase 7)**: Depends on US1 + US3 — comprehensive validation testing
- **US6 (Phase 8)**: Depends on US1 — adds mode parameter
- **Polish (Phase 9)**: Depends on all user stories complete

### User Story Dependencies

- **US1 (P1)**: Requires Phase 2 types only — the core MVP
- **US2 (P2)**: Requires US1 pipeline working — extends with filters
- **US3 (P2)**: Requires US1 pipeline working — extends with bucket_sizes
- **US4 (P3)**: Requires US1 pipeline working — wraps as build-only method
- **US5 (P3)**: Requires US1 + US3 validation — tests comprehensive error collection
- **US6 (P3)**: Requires US1 builder working — extends with mode mapping

### Parallel Opportunities

- **Phase 2**: T004, T005, T006 (type tests) can run in parallel
- **Phase 3**: T011-T019 (all US1 tests) can run in parallel
- **Phase 4-6**: US2, US3, US4 can proceed in parallel after US1 is complete (different files and concerns)
- **Phase 9**: T051-T054 (PBT + format variation tests) can run in parallel

### Within Each User Story

- Tests MUST be written and FAIL before implementation
- Validation before builder (validation catches bad inputs before they reach the builder)
- Builder before transformer (builder creates params, transformer parses responses)
- Service before workspace (service is called by workspace)
- Run test command at end of each phase to verify

---

## Parallel Example: User Story 1

```bash
# Launch all US1 tests together (T011-T019 are in different files):
Task: "Write validation tests for R1, R2, R7, R8, R9 in tests/test_validation_retention.py"
Task: "Write builder tests for default structure in tests/test_build_retention_params.py"
Task: "Write transformer tests in tests/test_transform_retention.py"
Task: "Write workspace integration tests in tests/test_workspace_retention.py"

# Then implement sequentially:
Task: "Implement validate_retention_args() in validation.py"
Task: "Implement _build_retention_params() in workspace.py"
Task: "Implement _transform_retention_result() in live_query.py"
Task: "Implement query_retention() service method in live_query.py"
Task: "Implement Workspace methods in workspace.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (verification)
2. Complete Phase 2: Foundational types
3. Complete Phase 3: User Story 1 — simple retention query
4. **STOP and VALIDATE**: `just test -k retention` — all tests pass
5. US1 delivers: `query_retention("Signup", "Login")` works end-to-end

### Incremental Delivery

1. Phase 2 → Types ready
2. Phase 3 (US1) → Simple query works (MVP)
3. Phase 4 (US2) → Filters and segmentation work
4. Phase 5 (US3) → Custom bucket sizes work
5. Phase 6 (US4) → `build_retention_params()` available
6. Phase 7 (US5) → Comprehensive validation verified
7. Phase 8 (US6) → Display modes work
8. Phase 9 → PBT, exports, quality gates pass

### Parallel Opportunities After US1

Once US1 is complete, US2, US3, US4, and US6 can proceed in parallel:
- US2 modifies `_build_retention_params()` (per-event filters)
- US3 modifies `validate_retention_args()` + `_build_retention_params()` (bucket_sizes)
- US4 adds `build_retention_params()` (new method, no conflicts)
- US6 modifies `_build_retention_params()` (displayOptions)

If working sequentially, follow priority order: US2 → US3 → US4 → US5 → US6.

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Each user story should be independently completable and testable
- Write tests first — verify they FAIL before implementing
- Commit after each phase checkpoint
- Follow existing funnel test patterns: see `tests/test_types_funnel.py`, `tests/test_validation_funnel.py`, `tests/test_build_funnel_params.py`, `tests/test_transform_funnel.py`, `tests/test_workspace_funnel.py` for fixture patterns, mocking strategies, and test organization
- Use `_valid_retention_args(**overrides)` helper pattern from `test_validation_funnel.py` for validation tests
- Use workspace factory fixture pattern from `test_workspace_funnel.py` for integration tests
