# Tasks: Unified Query Engine Completeness

**Input**: Design documents from `/specs/040-query-engine-completeness/`
**Prerequisites**: plan.md (required), spec.md (required), research.md, data-model.md, contracts/public-api.md, quickstart.md

**Tests**: Included — this project enforces strict TDD per CLAUDE.md.

**Organization**: Tasks grouped by user story. Each story is independently testable.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2)
- Exact file paths included in descriptions

---

## Phase 1: Setup

**Purpose**: No project initialization needed — all changes modify existing files.

_(No tasks — existing project structure is sufficient)_

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Expand Literal types and enum constants that ALL user stories depend on

**CRITICAL**: No user story work can begin until this phase is complete

- [x] T001 Expand MathType (+7: cumulative_unique, sessions, unique_values, most_frequent, first_value, multi_attribution, numeric_summary), RetentionMathType (+2: total, average), FunnelMathType (+1: histogram), and add 7 new Literal type aliases (SegmentMethod, FunnelReentryMode, RetentionUnboundedMode, TimeComparisonType, TimeComparisonUnit, CohortAggregationType, FlowSessionEvent) with docstring tables in src/mixpanel_data/_literal_types.py
- [x] T002 [P] Update MATH_REQUIRING_PROPERTY (+5: unique_values, most_frequent, first_value, multi_attribution, numeric_summary) and add VALID_FUNNEL_REENTRY_MODES, VALID_RETENTION_UNBOUNDED_MODES, VALID_SEGMENT_METHODS, VALID_TIME_COMPARISON_TYPES, VALID_TIME_COMPARISON_UNITS, VALID_COHORT_AGGREGATION_OPERATORS, VALID_FREQUENCY_FILTER_OPERATORS frozenset constants in src/mixpanel_data/_internal/bookmark_enums.py
- [x] T003 Export new Literal types (SegmentMethod, FunnelReentryMode, RetentionUnboundedMode, TimeComparisonType, TimeComparisonUnit, CohortAggregationType, FlowSessionEvent) and update __all__ in src/mixpanel_data/__init__.py

**Checkpoint**: Foundation ready — all types and enums available for user story implementation

---

## Phase 3: User Story 1 - Complete Math Type Coverage (Priority: P1) MVP

**Goal**: Developers can specify all 22 insights math types, 4 retention math types, and 14 funnel math types without type errors

**Independent Test**: Construct Metric objects with each new math type, call build_params() and build_retention_params()/build_funnel_params(), verify acceptance and correct output

### Tests for User Story 1

> **Write these tests FIRST, ensure they FAIL before implementation**

- [x] T004 [P] [US1] Write tests for Metric construction with 7 new math types: verify acceptance, verify property-required math types (unique_values, most_frequent, first_value, multi_attribution, numeric_summary) reject missing property, verify property-optional types (cumulative_unique, sessions) accept without property in tests/test_types.py
- [x] T005 [P] [US1] Write tests for build_params() with new math types producing correct measurement.math, build_retention_params() accepting total/average, build_funnel_params() accepting histogram in tests/test_workspace.py

### Implementation for User Story 1

- [x] T006 [US1] Update _MATH_REQUIRING_PROPERTY frozenset in Metric.__post_init__() to include unique_values, most_frequent, first_value, multi_attribution, numeric_summary in src/mixpanel_data/types.py
- [x] T007 [P] [US1] Verify validate_query_args(), validate_funnel_args(), validate_retention_args() correctly accept expanded math types via the VALID_MATH_* enum sets — update any hardcoded checks in src/mixpanel_data/_internal/validation.py

**Checkpoint**: All 22 insights, 4 retention, and 14 funnel math types accepted and produce correct output

---

## Phase 4: User Story 2 - Advanced Funnel and Retention Modes (Priority: P1)

**Goal**: Developers can configure funnel reentry mode, retention unbounded mode, retention cumulative mode, and segment method

**Independent Test**: Call build_funnel_params() with reentry_mode="aggressive", build_retention_params() with unbounded_mode="carry_forward" and retention_cumulative=True, verify correct JSON structure

### Tests for User Story 2

> **Write these tests FIRST, ensure they FAIL before implementation**

- [x] T008 [P] [US2] Write tests for Metric with segment_method="first" and segment_method="all" construction, verify None default in tests/test_types.py
- [x] T009 [P] [US2] Write tests for build_funnel_params() with reentry_mode producing behavior.funnelReentryMode, build_retention_params() with unbounded_mode producing behavior.retentionUnboundedMode and retention_cumulative producing measurement.retentionCumulative, and segmentMethod in measurement block in tests/test_workspace.py
- [x] T010 [P] [US2] Write tests for validate_funnel_args() rejecting invalid reentry_mode, validate_retention_args() rejecting invalid unbounded_mode, and segment_method rejection for insights-only queries in tests/test_validation.py

### Implementation for User Story 2

- [x] T011 [US2] Add segment_method: SegmentMethod | None = None field to Metric dataclass with docstring in src/mixpanel_data/types.py
- [x] T012 [US2] Add reentry_mode: FunnelReentryMode | None = None to query_funnel()/build_funnel_params(), add unbounded_mode: RetentionUnboundedMode | None = None and retention_cumulative: bool = False to query_retention()/build_retention_params(), thread reentry_mode to _build_funnel_params() behavior block as funnelReentryMode, thread unbounded_mode to _build_retention_params() behavior block as retentionUnboundedMode, thread retention_cumulative to measurement block as retentionCumulative, thread segment_method to measurement block as segmentMethod in src/mixpanel_data/workspace.py
- [x] T013 [P] [US2] Add reentry_mode enum validation in validate_funnel_args(), unbounded_mode enum validation in validate_retention_args(), segment_method context validation (reject for insights-only) in src/mixpanel_data/_internal/validation.py

**Checkpoint**: Funnel reentry, retention unbounded, retention cumulative, and segment method all configurable with validation

---

## Phase 5: User Story 3 - Period-Over-Period Time Comparison (Priority: P2)

**Goal**: Developers can overlay a comparison time period on insights, funnel, and retention queries

**Independent Test**: Call build_params() with time_comparison=TimeComparison.relative("month"), verify displayOptions.timeComparison in output

### Tests for User Story 3

> **Write these tests FIRST, ensure they FAIL before implementation**

- [x] T014 [P] [US3] Write tests for TimeComparison dataclass: factory methods (relative, absolute_start, absolute_end), validation (relative requires unit, absolute requires date, date must be YYYY-MM-DD) in tests/test_types.py
- [x] T015 [P] [US3] Write tests for build_time_comparison() producing correct dict for all 3 types in tests/test_bookmark_builders.py
- [x] T016 [P] [US3] Write tests for time_comparison rejection on query_flow, acceptance on query/query_funnel/query_retention in tests/test_validation.py

### Implementation for User Story 3

- [x] T017 [US3] Create TimeComparison frozen dataclass with type/unit/date fields, factory methods (relative, absolute_start, absolute_end), __post_init__ validation (TC1-TC3) in src/mixpanel_data/types.py
- [x] T018 [P] [US3] Add build_time_comparison(tc: TimeComparison) -> dict builder function in src/mixpanel_data/_internal/bookmark_builders.py
- [x] T019 [US3] Add time_comparison: TimeComparison | None = None to query()/build_params(), query_funnel()/build_funnel_params(), query_retention()/build_retention_params(), thread to displayOptions via build_time_comparison() in src/mixpanel_data/workspace.py; export TimeComparison from src/mixpanel_data/__init__.py
- [x] T020 [P] [US3] Add time_comparison validation: reject for flows in validate_flow_args(), validate discriminated fields in validate_query_args()/validate_funnel_args()/validate_retention_args() in src/mixpanel_data/_internal/validation.py

**Checkpoint**: Time comparison works on insights, funnels, and retention; rejected for flows

---

## Phase 6: User Story 4 - Frequency Analysis (Priority: P2)

**Goal**: Developers can break down and filter queries by event frequency using the modern query engine

**Independent Test**: Call build_params() with group_by=FrequencyBreakdown("Purchase") and where=FrequencyFilter("Login", value=5), verify correct sections.group and sections.filter output

### Tests for User Story 4

> **Write these tests FIRST, ensure they FAIL before implementation**

- [x] T021 [P] [US4] Write tests for FrequencyBreakdown and FrequencyFilter dataclass construction, validation (FB1-FB4, FF1-FF5), and defaults in tests/test_types.py
- [x] T022 [P] [US4] Write tests for build_frequency_group_entry() producing behaviorType="$frequency" + resourceType="people", and build_frequency_filter_entry() producing customProperty.behavior structure with correct operators in tests/test_bookmark_builders.py
- [x] T023 [P] [US4] Write tests for build_params() accepting FrequencyBreakdown in group_by and FrequencyFilter in where in tests/test_workspace.py

### Implementation for User Story 4

- [x] T024 [US4] Create FrequencyBreakdown and FrequencyFilter frozen dataclasses with validation in src/mixpanel_data/types.py; export both from src/mixpanel_data/__init__.py
- [x] T025 [US4] Add build_frequency_group_entry() and build_frequency_filter_entry() functions, update build_group_section() type union to accept FrequencyBreakdown, update build_filter_section() type union to accept FrequencyFilter in src/mixpanel_data/_internal/bookmark_builders.py
- [x] T026 [US4] Update group_by parameter type annotation to include FrequencyBreakdown and where parameter to include FrequencyFilter on query()/build_params() in src/mixpanel_data/workspace.py

**Checkpoint**: Frequency breakdown and frequency filter produce correct bookmark JSON

---

## Phase 7: User Story 5 - Enhanced Behavioral Cohorts (Priority: P2)

**Goal**: Developers can create behavioral cohorts using property aggregation operators beyond count-based thresholds

**Independent Test**: Call CohortCriteria.did_event("Purchase", aggregation="average", aggregation_property="amount", at_least=50, within_days=30), verify serialized output includes aggregationOperator

### Tests for User Story 5

> **Write these tests FIRST, ensure they FAIL before implementation**

- [x] T027 [P] [US5] Write tests for CohortCriteria.did_event() with aggregation and aggregation_property: all 6 operators accepted, mutual requirement enforced (CA1-CA2), correct serialization of aggregationOperator in behavior dict in tests/test_types.py

### Implementation for User Story 5

- [x] T028 [US5] Add aggregation: CohortAggregationType | None = None and aggregation_property: str | None = None to CohortCriteria.did_event(), add validation (aggregation requires aggregation_property, vice versa), update behavior dict serialization to include aggregationOperator and property in src/mixpanel_data/types.py

**Checkpoint**: Cohort criteria support 6 aggregation operators with property-based thresholds

---

## Phase 8: User Story 6 - Complete Filter Operator Coverage (Priority: P3)

**Goal**: Developers can use all server-supported filter operators through fluent factory methods

**Independent Test**: Call each new Filter factory method, verify operator string and value structure

### Tests for User Story 6

> **Write these tests FIRST, ensure they FAIL before implementation**

- [x] T029 [P] [US6] Write tests for 7 new Filter factory methods: not_between produces "not between" with [min, max], starts_with produces "starts with", ends_with produces "ends with", date_not_between produces "was not between" with [from, to], in_the_next produces "was in the next" with date_unit, at_least produces "is at least", at_most produces "is at most" in tests/test_types.py
- [x] T030 [P] [US6] Write tests for new filter operators in build_filter_entry() output in tests/test_bookmark_builders.py

### Implementation for User Story 6

- [x] T031 [US6] Add 7 Filter factory methods (not_between, starts_with, ends_with, date_not_between, in_the_next, at_least, at_most) following existing patterns (property, operator, value, property_type, resource_type) in src/mixpanel_data/types.py

**Checkpoint**: All 7 new filter factory methods produce correct operator strings and value structures

---

## Phase 9: User Story 7 - Group Analytics Scoping (Priority: P3)

**Goal**: Developers can scope any query to a specific data group for group-level analytics

**Independent Test**: Call build_params() with data_group_id=5, verify dataGroupId appears in output instead of None

### Tests for User Story 7

> **Write these tests FIRST, ensure they FAIL before implementation**

- [x] T032 [P] [US7] Write tests for data_group_id parameter on build_params(), build_funnel_params(), build_retention_params(), build_flow_params() — verify dataGroupId/data_group_id in output in tests/test_workspace.py
- [x] T033 [P] [US7] Write tests for data_group_id threading through build_group_section() and _build_cohort_group_entry() replacing hardcoded None in tests/test_bookmark_builders.py

### Implementation for User Story 7

- [x] T034 [US7] Add data_group_id: int | None = None parameter to query()/build_params(), query_funnel()/build_funnel_params(), query_retention()/build_retention_params(), query_flow()/build_flow_params() and thread through all _resolve_and_build_* and _build_* methods in src/mixpanel_data/workspace.py
- [x] T035 [P] [US7] Add data_group_id parameter to build_group_section(), _build_cohort_group_entry(), and replace 5 hardcoded dataGroupId: None / data_group_id: None with parameter value in src/mixpanel_data/_internal/bookmark_builders.py
- [x] T036 [P] [US7] Add data_group_id validation (must be positive integer if provided) in validate_query_args(), validate_funnel_args(), validate_retention_args(), validate_flow_args() in src/mixpanel_data/_internal/validation.py

**Checkpoint**: data_group_id threads through all query engines, replacing hardcoded None

---

## Phase 10: User Story 8 - Advanced Flow Features (Priority: P3)

**Goal**: Developers can segment, exclude, anchor on sessions, and apply property filters in flow queries

**Independent Test**: Call build_flow_params() with FlowStep(event="$session_start", session_event="start"), verify session_event in output; call with where=Filter.equals("country", "US"), verify filter_by_event in output

### Tests for User Story 8

> **Write these tests FIRST, ensure they FAIL before implementation**

- [x] T037 [P] [US8] Write tests for FlowStep with session_event field: construction, mutual exclusivity with event name (FS1), session_event mapping in tests/test_types.py
- [x] T038 [P] [US8] Write tests for flow with segments parameter, exclusion events, session_event mapping in step output, and property filter producing filter_by_event structure in tests/test_workspace.py
- [x] T039 [P] [US8] Write tests for build_flow_property_filter() output structure in tests/test_bookmark_builders.py

### Implementation for User Story 8

- [x] T040 [US8] Add session_event: FlowSessionEvent | None = None to FlowStep dataclass, add validation (FS1: session_event mutually exclusive with regular event name) in src/mixpanel_data/types.py
- [x] T041 [P] [US8] Add build_flow_property_filter() builder for filter_by_event structure in src/mixpanel_data/_internal/bookmark_builders.py
- [x] T042 [US8] Update query_flow()/build_flow_params(): emit session_event in step dict when set, expand where parameter to accept property Filter objects (route to filter_by_event vs filter_by_cohort based on filter type), add segments parameter support in src/mixpanel_data/workspace.py
- [x] T043 [P] [US8] Add flow validation for session_event on steps, property filter validation, segments validation in validate_flow_args() in src/mixpanel_data/_internal/validation.py

**Checkpoint**: Flow queries support segments, exclusions, session events, and global property filters

---

## Phase 11: Polish & Cross-Cutting Concerns

**Purpose**: Quality assurance across all stories

- [x] T044 [P] Write PBT tests for TimeComparison, FrequencyBreakdown, FrequencyFilter, expanded MathType using Hypothesis strategies in tests/test_types_pbt.py
- [x] T045 [P] Verify all new types (Literal aliases, dataclasses) are exported in __all__ and importable from mixpanel_data in src/mixpanel_data/__init__.py
- [x] T046 Run just check (ruff check + ruff format + mypy --strict + pytest) and fix any issues
- [x] T047 Run just test-cov and verify 90% coverage threshold is met — add targeted tests for any uncovered branches
- [x] T048 Validate quickstart.md examples by running representative code snippets against build_*_params() methods
- [x] T049 Run just mutate-check and verify 80% mutation score — SKIPPED (macOS grep -P incompatibility; mutation testing deferred)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Foundational (Phase 2)**: No dependencies — can start immediately. BLOCKS all user stories.
- **US1 (Phase 3)**: Depends on Foundational only
- **US2 (Phase 4)**: Depends on Foundational only (segment_method on Metric is independent of math type expansion)
- **US3 (Phase 5)**: Depends on Foundational only
- **US4 (Phase 6)**: Depends on Foundational only
- **US5 (Phase 7)**: Depends on Foundational only
- **US6 (Phase 8)**: Depends on Foundational only
- **US7 (Phase 9)**: Depends on Foundational only
- **US8 (Phase 10)**: Depends on Foundational only
- **Polish (Phase 11)**: Depends on all user stories being complete

### User Story Dependencies

All 8 user stories are **independent** of each other. After the Foundational phase completes, any story can be implemented without waiting for others.

The only cross-story concern is that multiple stories modify the same files (workspace.py, validation.py, types.py). When implementing sequentially, later stories build on earlier changes. When implementing in parallel, merge conflicts in these files must be resolved.

### Within Each User Story

1. Test tasks MUST be written and FAIL before implementation
2. types.py changes before workspace.py changes
3. bookmark_builders.py [P] with validation.py (independent files)
4. workspace.py changes last (imports types, calls builders, calls validation)

### Parallel Opportunities

**Within Foundational**: T001 and T002 are [P] (different files: _literal_types.py vs bookmark_enums.py)

**Within each story**: Test tasks marked [P] can run in parallel. Implementation tasks on different files marked [P] can run in parallel.

**Across stories**: After Foundational, all stories CAN run in parallel if handled by separate developers with merge coordination on shared files.

---

## Parallel Example: User Story 3 (Time Comparison)

```text
# Launch all tests in parallel (3 different files):
T014: TimeComparison dataclass tests in tests/test_types.py
T015: build_time_comparison() tests in tests/test_bookmark_builders.py
T016: Time comparison validation tests in tests/test_validation.py

# Then implementation — types first, then parallel builder + validation:
T017: Create TimeComparison in src/mixpanel_data/types.py
  Then in parallel:
    T018: Add builder in src/mixpanel_data/_internal/bookmark_builders.py
    T020: Add validation in src/mixpanel_data/_internal/validation.py
  Then:
    T019: Thread param through workspace methods in src/mixpanel_data/workspace.py
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 2: Foundational (expand types and enums)
2. Complete Phase 3: US1 - Math Type Coverage
3. **STOP and VALIDATE**: Run `just check` — all 22 math types accepted
4. Commit and verify

### Incremental Delivery (Recommended)

1. Foundational → US1 (math types) → US2 (advanced modes) → **P1 complete**
2. US3 (time comparison) → US4 (frequency) → US5 (cohorts) → **P2 complete**
3. US6 (filters) → US7 (data groups) → US8 (flows) → **P3 complete**
4. Polish → **All 29 gaps closed**

Each story adds independent value and can be validated separately.

### Parallel Team Strategy

With 3 developers after Foundational:
- Developer A: US1 → US3 → US6 (math → time comparison → filters)
- Developer B: US2 → US4 → US7 (modes → frequency → data groups)
- Developer C: US5 → US8 → Polish (cohorts → flows → quality)

---

## Notes

- [P] tasks = different files, no dependencies on incomplete tasks in the same phase
- [Story] label maps to user stories from spec.md (US1-US8)
- TDD is enforced: test tasks must complete and fail before implementation
- The project validates bookmark JSON with validate_bookmark() — builder output must pass Layer 2 validation
- All new params default to None/False for backward compatibility (FR-026, FR-029)
- Commit after each completed story checkpoint
- Run `just check` after each story to catch regressions early

### Documentation Requirements (Constitution Mandate)

Per Constitution Principle I, ALL new public methods, fields, classes, and Literal types MUST include:
- Type hints (enforced by mypy --strict)
- Docstrings with: summary, Args, Returns, Raises, Example (where behavior isn't obvious)
- Docstring tables for Literal types (see existing MathType docstring as reference)

This applies to every implementation task — docstrings are part of the task, not a separate step.
