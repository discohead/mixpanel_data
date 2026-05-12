# Tasks: Cohort Behaviors in Unified Query System

**Input**: Design documents from `/specs/036-cohort-behaviors/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: Included (TDD per project CLAUDE.md — tests written first, verified to fail, then implementation).

**Organization**: Tasks grouped by user story. Each story is independently implementable and testable.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Widen `Filter._value` type to accommodate cohort filter values — prerequisite for all user stories.

- [x] T001 Widen `Filter._value` type annotation to include `list[dict[str, Any]]` in `src/mixpanel_data/types.py`

**Checkpoint**: `Filter` dataclass accepts the widened value type. `just typecheck` passes. No functional changes yet.

---

## Phase 2: User Story 1 — Filter Queries by Cohort Membership (Priority: P1)

**Goal**: Developers can filter any query to users in/not in a cohort via `Filter.in_cohort()` / `Filter.not_in_cohort()`.

**Independent Test**: Construct `Filter.in_cohort(123, "Power Users")` and verify it produces correct bookmark JSON in `sections.filter[]`.

### Tests for User Story 1

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [x] T002 [P] [US1] Unit tests for `Filter.in_cohort()` and `Filter.not_in_cohort()` construction (saved cohort ID + inline CohortDefinition) in `tests/test_types.py`
- [x] T003 [P] [US1] Unit tests for `build_filter_entry()` cohort filter branch (saved + inline, contains + does not contain) in `tests/test_bookmark_builders.py`
- [x] T004 [P] [US1] Unit tests for CF1-CF2 validation (non-positive ID, empty name) in `tests/test_types.py`
- [x] T005 [P] [US1] Unit tests for `build_filter_section()` with mixed cohort + property filters in `tests/test_bookmark_builders.py`
- [x] T006 [P] [US1] Unit tests for flow cohort filter builder (`filter_by_cohort` legacy format) in `tests/test_bookmark_builders.py`
- [x] T007 [P] [US1] Unit tests for `query_flow()` `where=` parameter with cohort filters (and rejection of non-cohort filters) in `tests/test_workspace.py`
- [x] T008 [P] [US1] Layer 2 validation test for cohort filter entries (B25) in `tests/test_validation.py`
- [x] T009 [P] [US1] Integration tests verifying cohort filters work in `_resolve_and_build_params()` for insights in `tests/test_workspace.py`
- [x] T010 [P] [US1] Integration tests verifying cohort filters work in `_resolve_and_build_funnel_params()` for funnels in `tests/test_workspace.py`
- [x] T011 [P] [US1] Integration tests verifying cohort filters work in `_resolve_and_build_retention_params()` for retention in `tests/test_workspace.py`

### Implementation for User Story 1

- [x] T012 [US1] Add `Filter.in_cohort()` and `Filter.not_in_cohort()` class methods with CF1-CF2 validation in `src/mixpanel_data/types.py`
- [x] T013 [US1] Extend `build_filter_entry()` to detect `_property == "$cohorts"` and generate cohort-specific JSON in `src/mixpanel_data/_internal/bookmark_builders.py`
- [x] T014 [US1] Add `build_flow_cohort_filter()` helper for flows-specific `filter_by_cohort` tree format in `src/mixpanel_data/_internal/bookmark_builders.py`
- [x] T015 [US1] Add `where=` parameter to `query_flow()`, `build_flow_params()`, `_resolve_and_build_flow_params()`, and `_build_flow_params()` in `src/mixpanel_data/workspace.py`
- [x] T016 [US1] Extract cohort filters from `where=` into top-level `filter_by_cohort` in `_build_flow_params()`, reject non-cohort filters in `src/mixpanel_data/workspace.py`
- [x] T017 [US1] Add B25 cohort filter validation rule to `_validate_filter_clause()` in `src/mixpanel_data/_internal/validation.py`
- [x] T018 [US1] Verify all US1 tests pass with `just test -k cohort_filter`

**Checkpoint**: `Filter.in_cohort()` and `Filter.not_in_cohort()` produce correct bookmark JSON across all four query methods. All US1 tests green.

---

## Phase 3: User Story 2 — Break Down Results by Cohort Membership (Priority: P2)

**Goal**: Developers can segment results by cohort membership via `CohortBreakdown` in `group_by=`.

**Independent Test**: Construct `CohortBreakdown(123, "Power Users")` and verify it produces correct `sections.group[]` JSON.

### Tests for User Story 2

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [x] T019 [P] [US2] Unit tests for `CohortBreakdown` construction and `__post_init__` validation (CB1-CB2) in `tests/test_types.py`
- [x] T020 [P] [US2] Unit tests for `build_group_section()` with `CohortBreakdown` (saved + inline, include_negated true/false) in `tests/test_bookmark_builders.py`
- [x] T021 [P] [US2] Unit tests for mixed `CohortBreakdown` + `GroupBy` + `str` in `build_group_section()` in `tests/test_bookmark_builders.py`
- [x] T022 [P] [US2] Unit tests for retention mutual exclusivity (CB3) in `tests/test_validation.py`
- [x] T023 [P] [US2] Layer 2 validation test for cohort group entries (B26) in `tests/test_validation.py`
- [x] T024 [P] [US2] Integration tests verifying `CohortBreakdown` in `_resolve_and_build_params()` for insights in `tests/test_workspace.py`
- [x] T025 [P] [US2] Integration tests verifying `CohortBreakdown` in `_resolve_and_build_funnel_params()` for funnels in `tests/test_workspace.py`
- [x] T026 [P] [US2] Integration tests verifying `CohortBreakdown` in `_resolve_and_build_retention_params()` (alone OK, mixed with GroupBy rejected) in `tests/test_workspace.py`

### Implementation for User Story 2

- [x] T027 [US2] Add `CohortBreakdown` frozen dataclass with `__post_init__` validation (CB1-CB2) in `src/mixpanel_data/types.py`
- [x] T028 [US2] Widen `group_by` parameter type on `query()`, `_build_query_params()`, `_resolve_and_build_params()` in `src/mixpanel_data/workspace.py`
- [x] T029 [US2] Widen `group_by` parameter type on `query_funnel()`, `_build_funnel_params()`, `_resolve_and_build_funnel_params()` in `src/mixpanel_data/workspace.py`
- [x] T030 [US2] Widen `group_by` parameter type on `query_retention()`, `_build_retention_params()`, `_resolve_and_build_retention_params()` in `src/mixpanel_data/workspace.py`
- [x] T031 [US2] Extend `build_group_section()` to handle `CohortBreakdown` entries in `src/mixpanel_data/_internal/bookmark_builders.py`
- [x] T032 [US2] Add CB3 retention mutual exclusivity check to `validate_retention_args()` in `src/mixpanel_data/_internal/validation.py`
- [x] T033 [US2] Widen `validate_group_by_args()` to accept `CohortBreakdown` in `src/mixpanel_data/_internal/validation.py`
- [x] T034 [US2] Add B26 cohort group validation rule to `_validate_group_clause()` in `src/mixpanel_data/_internal/validation.py`
- [x] T035 [US2] Export `CohortBreakdown` from `src/mixpanel_data/__init__.py`
- [x] T036 [US2] Verify all US2 tests pass with `just test -k cohort_breakdown`

**Checkpoint**: `CohortBreakdown` produces correct `sections.group[]` JSON for insights, funnels, and retention. Retention mutual exclusivity enforced. All US2 tests green.

---

## Phase 4: User Story 3 — Track Cohort Size Over Time (Priority: P3)

**Goal**: Developers can track cohort size over time via `CohortMetric` in `events=` parameter of `query()`.

**Independent Test**: Construct `CohortMetric(123, "Power Users")` and verify it produces correct `sections.show[]` entry with `behavior.type: "cohort"`.

### Tests for User Story 3

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [x] T037 [P] [US3] Unit tests for `CohortMetric` construction and `__post_init__` validation (CM1-CM2) in `tests/test_types.py`
- [x] T038 [P] [US3] Unit tests for `_build_query_params()` cohort metric branch (saved + inline, behavior structure) in `tests/test_workspace.py`
- [x] T039 [P] [US3] Unit tests for `CohortMetric` mixed with `Metric` and `Formula` in `_build_query_params()` in `tests/test_workspace.py`
- [x] T040 [P] [US3] Unit tests for CM3 (math/math_property/per_user ignored for CohortMetric) in `tests/test_workspace.py`
- [x] T041 [P] [US3] Unit tests for `_resolve_and_build_params()` type guard accepting `CohortMetric` in `tests/test_workspace.py`
- [x] T042 [P] [US3] Unit tests for V21 event type validation accepting `CohortMetric` in `tests/test_validation.py`
- [x] T043 [P] [US3] Layer 2 validation tests for B22-B24 (cohort behavior id, resourceType, math) in `tests/test_validation.py`

### Implementation for User Story 3

- [x] T044 [US3] Add `CohortMetric` frozen dataclass with `__post_init__` validation (CM1-CM2) in `src/mixpanel_data/types.py`
- [x] T045 [US3] Widen `events` parameter type on `query()` and `_resolve_and_build_params()` to accept `CohortMetric` in `src/mixpanel_data/workspace.py`
- [x] T046 [US3] Extend type guard in `_resolve_and_build_params()` to accept `CohortMetric` in `src/mixpanel_data/workspace.py`
- [x] T047 [US3] Extend `_build_query_params()` to detect `CohortMetric` and generate cohort behavior show entries in `src/mixpanel_data/workspace.py`
- [x] T048 [US3] Extend `validate_query_args()` V21 type check to accept `CohortMetric` and skip math validation for it in `src/mixpanel_data/_internal/validation.py`
- [x] T049 [US3] Add B22-B24 cohort show clause validation to `_validate_show_clause()` and `_validate_measurement()` in `src/mixpanel_data/_internal/validation.py`
- [x] T050 [US3] Export `CohortMetric` from `src/mixpanel_data/__init__.py`
- [x] T051 [US3] Verify all US3 tests pass with `just test -k cohort_metric`

**Checkpoint**: `CohortMetric` produces correct `sections.show[]` entries. Formula interaction works. Insights-only enforcement in place. All US3 tests green.

---

## Phase 5: User Story 4 — Comprehensive Quality Assurance (Priority: P4)

**Goal**: Property-based tests and mutation testing ensure robustness and validation rule coverage.

### Tests for User Story 4

- [x] T052 [P] [US4] Property-based tests for `Filter.in_cohort()` / `Filter.not_in_cohort()` invariants in `tests/test_types_pbt.py`
- [x] T053 [P] [US4] Property-based tests for `CohortBreakdown` construction and bookmark JSON invariants in `tests/test_types_pbt.py`
- [x] T054 [P] [US4] Property-based tests for `CohortMetric` construction and bookmark JSON invariants in `tests/test_types_pbt.py`
- [x] T055 [P] [US4] Property-based tests for cohort filter + breakdown + metric integration with `CohortDefinition` in `tests/test_types_pbt.py`

### Implementation for User Story 4

- [x] T056 [US4] Run mutation testing on cohort filter validation code (CF1-CF2, B25) with `just mutate`
- [x] T057 [US4] Run mutation testing on cohort breakdown validation code (CB1-CB3, B26) with `just mutate`
- [x] T058 [US4] Run mutation testing on cohort metric validation code (CM1-CM2, B22-B24) with `just mutate`
- [x] T059 [US4] Kill surviving mutants by adding targeted tests
- [x] T060 [US4] Verify mutation score meets 80% threshold with `just mutate-check`

**Checkpoint**: PBT tests pass with 100+ examples. Mutation score >= 80% on all new validation code.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Final quality pass across all phases.

- [x] T061 [P] Verify all new classes and methods have complete docstrings with examples in `src/mixpanel_data/types.py`
- [x] T062 [P] Verify all new classes and methods have complete docstrings with examples in `src/mixpanel_data/workspace.py`
- [x] T063 [P] Verify all new classes and methods have complete docstrings with examples in `src/mixpanel_data/_internal/bookmark_builders.py`
- [x] T064 [P] Verify all new classes and methods have complete docstrings with examples in `src/mixpanel_data/_internal/validation.py`
- [x] T065 Run full quality gate: `just check` (lint + typecheck + test)
- [x] T066 Run test coverage: `just test-cov` — verify >= 90%
- [x] T067 Run PBT with CI profile: `just test-ci` — verify 200 examples pass
- [x] T068 Validate quickstart examples compile and produce expected structures

**Checkpoint**: All quality gates pass. Coverage >= 90%. All exports present. Docstrings complete.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: No dependencies — `Filter._value` type widening
- **Phase 2 (US1 — Filters)**: Depends on Phase 1 — adds `Filter.in_cohort()` and builder extensions
- **Phase 3 (US2 — Breakdowns)**: Depends on Phase 1 only — `CohortBreakdown` is independent of filters
- **Phase 4 (US3 — Metrics)**: Depends on Phase 1 only — `CohortMetric` is independent of filters and breakdowns
- **Phase 5 (US4 — QA)**: Depends on Phases 2, 3, and 4 — needs all types implemented
- **Phase 6 (Polish)**: Depends on Phase 5 — final quality pass

### User Story Dependencies

- **US1 (Filters)**: After Phase 1. No dependency on US2 or US3.
- **US2 (Breakdowns)**: After Phase 1. No dependency on US1 or US3. Can run in parallel with US1.
- **US3 (Metrics)**: After Phase 1. No dependency on US1 or US2. Can run in parallel with US1 and US2.
- **US4 (QA)**: After US1, US2, and US3 are all complete.

### Within Each User Story

- Tests MUST be written and FAIL before implementation
- Type definitions before builder extensions
- Builder extensions before workspace method changes
- Workspace changes before validation extensions
- Exports after type definitions
- All tests green before checkpoint

### Parallel Opportunities

- **US1, US2, US3 can run in parallel** after Phase 1 (different types, different builder branches, different validation rules)
- Within each story: all test tasks marked [P] can run in parallel
- Phase 5 PBT tasks (T052-T055) can run in parallel
- Phase 6 docstring verification tasks (T061-T064) can run in parallel

---

## Parallel Example: User Stories 1, 2, 3 (after Phase 1)

```
# All three can start simultaneously:
Agent A: US1 — Filter.in_cohort() + build_filter_entry() + flow cohort filter
Agent B: US2 — CohortBreakdown + build_group_section() + retention exclusivity
Agent C: US3 — CohortMetric + _build_query_params() + show clause validation
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (T001)
2. Complete Phase 2: US1 Tests (T002-T011) → verify they fail
3. Complete Phase 2: US1 Implementation (T012-T018) → verify tests pass
4. **STOP and VALIDATE**: Cohort filters work across all 4 query methods

### Incremental Delivery

1. Phase 1 (Setup) → Foundation ready
2. US1 (Filters) → Cohort filtering across all query methods (MVP)
3. US2 (Breakdowns) → Cohort-based segmentation added
4. US3 (Metrics) → Cohort size tracking added
5. US4 (QA) → PBT + mutation testing confidence
6. Polish → Full quality gate pass

### Parallel Strategy

1. Complete Phase 1 together (single task)
2. Launch US1, US2, US3 in parallel (3 agents on different files)
3. Merge all three, then US4 (QA pass)
4. Polish

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Tests follow TDD: write first, verify failure, then implement
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
- `just check` is the quality gate — run before every commit
