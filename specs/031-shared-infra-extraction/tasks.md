# Tasks: Phase 1 — Shared Infrastructure Extraction

**Input**: Design documents from `/specs/031-shared-infra-extraction/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, quickstart.md

**Tests**: Required — project enforces strict TDD (CLAUDE.md). Tests MUST be written first and FAIL before implementation.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Phase 1: Setup

**Purpose**: No project initialization needed — this is an existing codebase. Verify baseline.

- [X] T001 Run `just check` to confirm all existing tests pass before any changes

**Checkpoint**: Baseline confirmed — all existing tests green.

---

## Phase 2: Foundational — Bookmark Enum Constants (US4, Priority: P2)

**Goal**: Add funnel/retention/flows-specific enum constants used by validators and builders in later phases.

**Independent Test**: Assert each new frozenset contains the expected members. Cross-reference with design doc canonical values.

### Tests for US4

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [X] T002 [P] [US4] Write tests for new enum constants `VALID_FUNNEL_ORDER`, `VALID_CONVERSION_WINDOW_UNITS`, `VALID_RETENTION_UNITS`, `VALID_RETENTION_ALIGNMENT`, `VALID_FLOWS_COUNT_TYPES`, `VALID_FLOWS_CHART_TYPES` in tests/unit/test_bookmark_enums.py
- [X] T003 [P] [US4] Write tests for extended `VALID_MATH_FUNNELS` (must include property aggregation types: average, median, min, max, p25, p75, p90, p99) in tests/unit/test_bookmark_enums.py

### Implementation for US4

- [X] T004 [US4] Add `VALID_FUNNEL_ORDER`, `VALID_CONVERSION_WINDOW_UNITS`, `VALID_RETENTION_UNITS`, `VALID_RETENTION_ALIGNMENT`, `VALID_FLOWS_COUNT_TYPES`, `VALID_FLOWS_CHART_TYPES` frozensets to src/mixpanel_data/_internal/bookmark_enums.py
- [X] T005 [US4] Extend `VALID_MATH_FUNNELS` with property aggregation types (`average`, `median`, `min`, `max`, `p25`, `p75`, `p90`, `p99`) in src/mixpanel_data/_internal/bookmark_enums.py
- [X] T006 [US4] Run `just check` to confirm all tests pass including new enum tests

**Checkpoint**: All new enum constants defined and tested. Existing tests still green.

---

## Phase 3: User Story 1 — Reusable Time Range Building (Priority: P1) 

**Goal**: Extract time-section and date-range builders from inline code in `_build_query_params()` into shared functions. Extract filter-section and group-section builders similarly.

**Independent Test**: Call each extracted builder with various date/filter/group combinations. Assert output dict structure matches expected bookmark JSON. No API access needed.

### Tests for US1

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [X] T007 [P] [US1] Write tests for `build_time_section()` — absolute range, from-only range, relative range — in tests/unit/test_bookmark_builders.py
- [X] T008 [P] [US1] Write tests for `build_date_range()` — relative (last=30), absolute (from+to) — in tests/unit/test_bookmark_builders.py
- [X] T009 [P] [US1] Write tests for `build_filter_section()` — single filter, multiple filters, None — in tests/unit/test_bookmark_builders.py
- [X] T010 [P] [US1] Write tests for `build_group_section()` — string group_by, GroupBy with buckets, multiple groups, None — in tests/unit/test_bookmark_builders.py

### Implementation for US1

- [X] T011 [US1] Implement `build_time_section(from_date, to_date, last, unit)` with complete docstring in src/mixpanel_data/_internal/bookmark_builders.py
- [X] T012 [US1] Implement `build_date_range(from_date, to_date, last)` with complete docstring in src/mixpanel_data/_internal/bookmark_builders.py
- [X] T013 [US1] Implement `build_filter_section(where)` with complete docstring in src/mixpanel_data/_internal/bookmark_builders.py — delegates to `_build_filter_entry()`
- [X] T014 [US1] Implement `build_group_section(group_by)` with complete docstring in src/mixpanel_data/_internal/bookmark_builders.py
- [X] T015 [US1] Refactor `Workspace._build_query_params()` in src/mixpanel_data/workspace.py to delegate time/filter/group building to the new shared functions
- [X] T016 [US1] Move `_build_filter_entry()` from `Workspace` static method to `bookmark_builders.py` module-level function; keep a delegating alias on `Workspace` for backward compat
- [X] T017 [US1] Run `just check` to confirm all tests pass — new builder tests AND existing query tests

**Checkpoint**: All four builders extracted, tested, and wired into `_build_query_params()`. Existing `query()` / `build_params()` output unchanged.

---

## Phase 4: User Story 2 — Reusable Time and GroupBy Validation (Priority: P1)

**Goal**: Extract time-argument validation (V7-V10, V15, V20) and group-by validation (V11-V12, V18, V24) from `validate_query_args()` into reusable functions.

**Independent Test**: Call each extracted validator with valid and invalid inputs. Assert the expected `ValidationError` objects (code, path, message) are returned. Compare output against pre-refactoring behavior.

### Tests for US2

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [X] T018 [P] [US2] Write tests for `validate_time_args()` — V7 (last positive), V8 (date format), V9 (to requires from), V10 (date/last exclusive), V15 (date order), V20 (last cap) — in tests/unit/test_query_validation.py
- [X] T019 [P] [US2] Write tests for `validate_group_by_args()` — V11 (bucket requires size), V12 (bucket size positive), V12B (bucket requires number), V12C (bucket requires bounds), V18 (bucket order), V24 (bucket finite) — in tests/unit/test_query_validation.py

### Implementation for US2

- [X] T020 [US2] Extract `validate_time_args(from_date, to_date, last)` from `validate_query_args()` in src/mixpanel_data/_internal/validation.py — rules V7-V10, V15, V20
- [X] T021 [US2] Extract `validate_group_by_args(group_by)` from `validate_query_args()` in src/mixpanel_data/_internal/validation.py — rules V11-V12, V18, V24
- [X] T022 [US2] Refactor `validate_query_args()` to call `validate_time_args()` and `validate_group_by_args()` — no change in external behavior
- [X] T023 [US2] Update validation module exports — add `validate_time_args` and `validate_group_by_args` to the import in src/mixpanel_data/_internal/validation.py
- [X] T024 [US2] Run `just check` to confirm all tests pass — new validator tests AND existing validation tests produce identical results

**Checkpoint**: Both validators extracted, tested, and wired into `validate_query_args()`. Existing validation behavior unchanged.

---

## Phase 5: User Story 3 — Filter-to-Segfilter Conversion (Priority: P2)

**Goal**: Build a `build_segfilter_entry()` converter that translates `Filter` objects to the legacy segfilter format used by flows step filters.

**Independent Test**: Create `Filter` objects with every supported operator type. Assert the segfilter output matches the canonical TypeScript reference test cases from `analytics/` repo.

### Tests for US3

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [X] T025 [P] [US3] Write tests for string operators — `equals` (`"=="`), `not_equals` (`"!="`), `contains` (`"in"`), `is_set` (`"set"`), `is_not_set` (`"not set"`) — in tests/unit/test_segfilter.py
- [X] T026 [P] [US3] Write tests for number operators — `greater_than` (`">"`), `less_than` (`"<"`), operand stringification — in tests/unit/test_segfilter.py
- [X] T027 [P] [US3] Write tests for boolean operators — `is_true` (operand `"true"`, no operator field), `is_false` (operand `"false"`) — in tests/unit/test_segfilter.py
- [X] T028 [P] [US3] Write tests for datetime operators — `on` (`"=="`), `not_on` (`"!="`), `before` (`">"`), `in_the_last` (`">"` with unit), date format conversion `YYYY-MM-DD` → `MM/DD/YYYY` — in tests/unit/test_segfilter.py
- [X] T029 [P] [US3] Write tests for resource type mapping — `"events"` → `"properties"`, `"people"` → `"user"` — in tests/unit/test_segfilter.py
- [X] T030 [P] [US3] Write tests for segfilter structure — `property`, `type`, `selected_property_type`, `filter` top-level keys present and correctly populated — in tests/unit/test_segfilter.py

### Implementation for US3

- [X] T031 [US3] Define `BOOKMARK_TO_SEGFILTER_OPERATOR` mapping dict and `RESOURCE_TYPE_MAP` with complete docstrings in src/mixpanel_data/_internal/segfilter.py
- [X] T032 [US3] Implement `build_segfilter_entry(f: Filter)` with complete docstring in src/mixpanel_data/_internal/segfilter.py — string, number, boolean, and existence operators
- [X] T033 [US3] Add datetime operator handling to `build_segfilter_entry()` — date format conversion, relative date with unit — in src/mixpanel_data/_internal/segfilter.py
- [X] T034 [US3] Run `just check` to confirm all segfilter tests pass and no regressions

**Checkpoint**: Segfilter converter handles all 14 `Filter` operator types. Ready for Phase 4 (Flows) integration.

---

## Phase 6: User Story 5 — Non-Regression Verification (Priority: P1)

**Goal**: Comprehensive verification that all extractions and refactoring produced zero behavioral changes in existing `query()`, `build_params()`, and validation functions.

**Independent Test**: Run full test suite + property-based equivalence tests + mutation testing on new code.

### Tests for US5

- [X] T035 [P] [US5] Write property-based test (Hypothesis) that generates random valid (from_date, to_date, last, unit) inputs, calls both `build_time_section()` directly and `_build_query_params()`, and asserts `params["sections"]["time"]` matches `build_time_section()` output (oracle test) — in tests/unit/test_bookmark_builders_pbt.py
- [X] T036 [P] [US5] Write property-based test (Hypothesis) comparing `validate_query_args()` error output before and after refactoring across randomized invalid inputs — in tests/unit/test_query_validation_pbt.py (extend existing file)

### Verification for US5

- [X] T037 [US5] Run full test suite: `just check` — all existing tests pass without modification
- [X] T038 [US5] Run property-based tests: `just test-pbt` — equivalence confirmed across randomized inputs
- [X] T039 [US5] Run code coverage: `just test-cov` — new modules meet 90% threshold
- [X] T040 [US5] Run mutation testing on new modules: `just mutate` — verify 80%+ kill rate on bookmark_builders.py and segfilter.py

**Checkpoint**: Zero regressions. All quality gates pass.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Final cleanup and documentation.

- [X] T041 [P] Verify all functions in src/mixpanel_data/_internal/bookmark_builders.py have complete docstrings (summary, args, returns, raises, example)
- [X] T042 [P] Verify all functions in src/mixpanel_data/_internal/segfilter.py have complete docstrings (summary, args, returns, raises, example)
- [X] T043 Verify mypy --strict passes: `just typecheck` — all new code fully typed
- [X] T044 Run final `just check` — all linting, formatting, type checking, and tests pass

**Checkpoint**: All quality gates pass. Phase 1 complete. Ready for Phase 2 (Funnels).

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — confirms baseline
- **Foundational / US4 (Phase 2)**: Depends on Setup — provides enum constants for later phases
- **US1 (Phase 3)**: Depends on Setup — independent of US4
- **US2 (Phase 4)**: Depends on Setup — independent of US1 and US4
- **US3 (Phase 5)**: Depends on Setup — independent of US1, US2, US4
- **US5 (Phase 6)**: Depends on US1, US2, US3, US4 all complete
- **Polish (Phase 7)**: Depends on US5

### User Story Dependencies

- **US4 (Enums)**: No deps on other stories. Can start immediately after Setup.
- **US1 (Builders)**: No deps on other stories. Can start in parallel with US4.
- **US2 (Validators)**: No deps on other stories. Can start in parallel with US1 and US4.
- **US3 (Segfilter)**: No deps on other stories. Can start in parallel with US1, US2, US4.
- **US5 (Regression)**: Depends on ALL other stories being complete.

### Within Each User Story

- Tests MUST be written and FAIL before implementation
- Implementation tasks within a story are sequential (later tasks depend on earlier ones)
- Checkpoint verification at the end of each story

### Parallel Opportunities

- **Phase 2**: T002 and T003 can run in parallel (different test groups)
- **Phase 3**: T007, T008, T009, T010 can all run in parallel (different test functions)
- **Phase 4**: T018 and T019 can run in parallel (different test functions)
- **Phase 5**: T025-T030 can all run in parallel (different test functions)
- **Phase 6**: T035 and T036 can run in parallel (different PBT files)
- **Phase 7**: T041 and T042 can run in parallel (different files)
- **Cross-phase**: US1 (Phase 3), US2 (Phase 4), US3 (Phase 5), and US4 (Phase 2) can all run in parallel with separate developers since they touch different files

---

## Parallel Example: US1 (Builders)

```
# Launch all test tasks in parallel (different test functions, same file):
Task T007: "Write tests for build_time_section()"
Task T008: "Write tests for build_date_range()"
Task T009: "Write tests for build_filter_section()"
Task T010: "Write tests for build_group_section()"

# Then implement sequentially (shared file):
Task T011: "Implement build_time_section()"
Task T012: "Implement build_date_range()"
Task T013: "Implement build_filter_section()"
Task T014: "Implement build_group_section()"
Task T015: "Refactor _build_query_params() to use builders"
```

---

## Implementation Strategy

### MVP First (US1 + US2 Only)

1. Complete Phase 1: Setup (T001)
2. Complete US1 (Phase 3): Builders extracted and wired
3. Complete US2 (Phase 4): Validators extracted and wired
4. **STOP and VALIDATE**: Run `just check` — all existing + new tests pass
5. Funnels and retention (Phases 2-3 of the project) can now begin

### Incremental Delivery

1. US4 (enums) → Foundation constants ready
2. US1 (builders) → Time/filter/group builders reusable → validate independently
3. US2 (validators) → Time/group_by validators reusable → validate independently
4. US3 (segfilter) → Flows filter converter ready → validate independently
5. US5 (regression) → Full verification → confirm zero regressions
6. Each story adds capability without breaking previous stories

### Parallel Strategy

With parallel execution:
1. Launch US4, US1, US2, US3 simultaneously (all independent)
2. When all complete → US5 (verification)
3. Then Polish

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- This project enforces strict TDD — tests written first in every story
- Commit after each task or logical group
- Stop at any checkpoint to validate independently
- The segfilter converter (US3) is the highest-risk component — if it takes longer, US1/US2/US4 can proceed independently
