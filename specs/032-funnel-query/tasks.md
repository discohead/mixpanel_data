# Tasks: Funnel Query (`query_funnel()`)

**Input**: Design documents from `/specs/032-funnel-query/`  
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/public-api.md  
**Tests**: Required — project enforces strict TDD (CLAUDE.md)  
**Organization**: Tasks grouped by user story. US1+US2+US7+US8 are combined as the core MVP since they are inseparable (a funnel query requires configuration defaults, validation, and build-params support).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2)
- Exact file paths included in all descriptions

---

## Phase 1: Setup

**Purpose**: Branch preparation — no new project structure needed; this feature adds to existing modules.

- [x] T001 Verify shared infrastructure from Phase 1 (PR #88) is available: confirm `build_time_section`, `build_filter_section`, `build_group_section`, `build_filter_entry` exist in `src/mixpanel_data/_internal/bookmark_builders.py` and `validate_time_args`, `validate_group_by_args` exist in `src/mixpanel_data/_internal/validation.py`
- [x] T002 Verify funnel enum constants exist: confirm `VALID_MATH_FUNNELS`, `VALID_FUNNEL_ORDER`, `VALID_CONVERSION_WINDOW_UNITS` in `src/mixpanel_data/_internal/bookmark_enums.py`
- [x] T003 Run `just check` to confirm baseline — all existing tests pass, lint and typecheck clean

---

## Phase 2: Foundational Types & Validation (Blocking Prerequisites)

**Purpose**: Input types, output type, and validation that ALL user stories depend on

**CRITICAL**: No user story work can begin until this phase is complete

### Tests for Foundational Phase

> **Write these tests FIRST, ensure they FAIL before implementation**

- [x] T004 Write tests for `FunnelStep` frozen dataclass: construction, defaults, immutability, string interchangeability in `tests/test_types_funnel.py`
- [x] T005 Write tests for `Exclusion` frozen dataclass: construction, defaults, immutability, string shorthand equivalence in `tests/test_types_funnel.py`
- [x] T006 Write tests for `HoldingConstant` frozen dataclass: construction, defaults, immutability, string shorthand equivalence in `tests/test_types_funnel.py`
- [x] T007 Write tests for `FunnelQueryResult` frozen dataclass: construction, `.overall_conversion_rate` property, `.df` DataFrame shape and columns in `tests/test_types_funnel.py`
- [x] T008 [P] Write tests for `validate_funnel_args()`: all rules F1-F6 including reused time/group-by validation in `tests/test_validation_funnel.py`
- [x] T009 [P] Write tests for `_validate_measurement()` with `bookmark_type="funnels"`: valid funnel math accepted, invalid math rejected with suggestions in `tests/test_validation.py`

### Implementation for Foundational Phase

- [x] T010 Implement `FunnelStep` frozen dataclass in `src/mixpanel_data/types.py` — fields: event (str), label (str|None), filters (list[Filter]|None), filters_combinator (Literal["all","any"]), order (Literal["loose","any"]|None)
- [x] T011 Implement `Exclusion` frozen dataclass in `src/mixpanel_data/types.py` — fields: event (str), from_step (int=0), to_step (int|None)
- [x] T012 Implement `HoldingConstant` frozen dataclass in `src/mixpanel_data/types.py` — fields: property (str), resource_type (Literal["events","people"]="events")
- [x] T013 Implement `FunnelMathType` Literal type alias in `src/mixpanel_data/types.py` — 13 valid values matching `VALID_MATH_FUNNELS` (excluding "general", "session", "conversion_rate" which are internal aliases)
- [x] T014 Implement `FunnelQueryResult` frozen dataclass extending `ResultWithDataFrame` in `src/mixpanel_data/types.py` — fields: computed_at, from_date, to_date, steps_data, series, params, meta; properties: overall_conversion_rate, df
- [x] T015 Implement `validate_funnel_args()` in `src/mixpanel_data/_internal/validation.py` — rules F1 (>=2 steps), F2 (non-empty event names), F3 (positive conversion_window), F4 (non-empty exclusion events), F5 (reuse validate_time_args), F6 (reuse validate_group_by_args)
- [x] T016 Update `_validate_measurement()` in `src/mixpanel_data/_internal/validation.py` — branch on `bookmark_type=="funnels"` to use `VALID_MATH_FUNNELS` instead of `VALID_MATH_INSIGHTS`
- [x] T017 Run `just check` — all new and existing tests pass, lint and typecheck clean

**Checkpoint**: All types and validation ready. User story implementation can begin.

---

## Phase 3: US1+US2+US7+US8 — Core Funnel Query MVP (Priority: P1)

**Goal**: A user can call `ws.query_funnel(["Signup", "Purchase"])` with sensible defaults and receive a typed `FunnelQueryResult`. Validation catches invalid inputs before API calls. `build_funnel_params()` returns params without executing.

**Independent Test**: Call `build_funnel_params(["Signup", "Purchase"])` and verify the returned dict matches the canonical funnel bookmark JSON structure. Call `query_funnel()` with mocked API responses and verify the result has correct step data, conversion rates, and DataFrame shape.

### Tests for Core Funnel MVP

> **Write these tests FIRST, ensure they FAIL before implementation**

- [x] T018 [P] [US1] Write tests for `_build_funnel_params()` in `tests/test_build_funnel_params.py` — verify generated bookmark JSON structure: sections.show[0].behavior.type=="funnel", behaviors array matches steps, default conversion window (14 days), default order ("loose"), measurement.math, displayOptions.chartType
- [x] T019 [P] [US2] Write tests for `_build_funnel_params()` configuration options in `tests/test_build_funnel_params.py` — verify conversion_window/unit, order, time range (absolute and relative), math type, and mode→chartType mapping (steps→"funnel-steps", trends→"line", table→"table")
- [x] T020 [P] [US1] Write tests for `_transform_funnel_result()` in `tests/test_transform_funnel.py` — verify extraction of computed_at, from_date, to_date, steps_data from mock API response; verify error handling for missing/malformed response fields
- [x] T021 [P] [US8] Write tests for `query_funnel()` validation integration in `tests/test_workspace_funnel.py` — verify BookmarkValidationError raised for: <2 steps (F1), empty event name (F2), negative conversion_window (F3), invalid math type; verify all errors collected together
- [x] T022 [P] [US1] Write tests for `query_funnel()` execution path in `tests/test_workspace_funnel.py` — mock `insights_query()`, verify correct body sent (bookmark + project_id + queryLimits), verify FunnelQueryResult returned with correct fields
- [x] T023 [P] [US7] Write tests for `build_funnel_params()` in `tests/test_workspace_funnel.py` — verify returns dict (not FunnelQueryResult), verify same params as query_funnel() for identical inputs, verify no API call made, verify raises BookmarkValidationError for invalid inputs

### Implementation for Core Funnel MVP

- [x] T024 [US1] Implement `_build_funnel_params()` in `src/mixpanel_data/workspace.py` — build funnel bookmark JSON: sections.show[0] with behavior (type="funnel", behaviors array, conversionWindowDuration/Unit, funnelOrder, exclusions=[], aggregateBy=[]), measurement (math), sections.time (via build_time_section), sections.filter (via build_filter_section), sections.group (via build_group_section), sections.formula=[], displayOptions (chartType based on mode)
- [x] T025 [US1] Implement `_resolve_and_build_funnel_params()` in `src/mixpanel_data/workspace.py` — normalize steps (str→FunnelStep), normalize where/exclusions/holding_constant, call validate_funnel_args (L1), call _build_funnel_params, call validate_bookmark with bookmark_type="funnels" (L2), return validated params
- [x] T026 [US1] Implement `_transform_funnel_result()` in `src/mixpanel_data/_internal/services/live_query.py` — extract computed_at, date_range, steps_data from series, raw series, meta from insights API response; construct FunnelQueryResult
- [x] T027 [US1] Implement `query_funnel()` in `src/mixpanel_data/_internal/services/live_query.py` — accept bookmark_params and project_id, build body (bookmark + project_id + queryLimits), call insights_query(), call _transform_funnel_result(), return FunnelQueryResult
- [x] T028 [US1] Implement `query_funnel()` public method on Workspace in `src/mixpanel_data/workspace.py` — accept all parameters per design doc section 3.1, call _resolve_and_build_funnel_params(), call _live_query_service.query_funnel(), return result
- [x] T029 [US7] Implement `build_funnel_params()` public method on Workspace in `src/mixpanel_data/workspace.py` — same signature as query_funnel(), call _resolve_and_build_funnel_params(), return params dict without API call
- [x] T030 Run `just check` — all tests pass, lint and typecheck clean

**Checkpoint**: Core funnel MVP complete. `ws.query_funnel(["Signup", "Purchase"])` works end-to-end with defaults, configuration, validation, and build-params support.

---

## Phase 4: US3+US4 — Per-Step Filters, Labels & Segmentation (Priority: P2)

**Goal**: Users can add per-step filters and labels via `FunnelStep` objects, and apply global filters (`where`) and breakdowns (`group_by`) to funnel queries.

**Independent Test**: Build params with `FunnelStep` objects containing filters and labels, and with `where`/`group_by` parameters. Verify the generated bookmark JSON has correct per-step filter entries in `behavior.behaviors[].filters[]` and correct `sections.filter[]`/`sections.group[]` entries.

### Tests for Filters & Segmentation

> **Write these tests FIRST, ensure they FAIL before implementation**

- [x] T031 [P] [US3] Write tests for per-step filters in `_build_funnel_params()` in `tests/test_build_funnel_params.py` — verify FunnelStep.filters are converted via build_filter_entry() into behavior.behaviors[N].filters[]; verify filters_combinator maps to filtersDeterminer; verify FunnelStep.label maps to step name
- [x] T032 [P] [US4] Write tests for global filter and group-by in `_build_funnel_params()` in `tests/test_build_funnel_params.py` — verify where parameter produces sections.filter[] via build_filter_section(); verify group_by parameter produces sections.group[] via build_group_section()
- [x] T033 [P] [US3] Write tests for mixed string/FunnelStep steps in `tests/test_build_funnel_params.py` — verify list like ["Signup", FunnelStep("Purchase", filters=[...])] produces correct behaviors array with filter on Purchase only; verify FunnelStep(event, filters=[]) and FunnelStep(event, filters=None) produce identical output

### Implementation for Filters & Segmentation

- [x] T034 [US3] Extend `_build_funnel_params()` in `src/mixpanel_data/workspace.py` — for each FunnelStep: if filters is not None, convert each via build_filter_entry() and set in behavior entry's filters array; map filters_combinator to filtersDeterminer; use label as step display name when provided
- [x] T035 [US3] Extend `_build_funnel_params()` in `src/mixpanel_data/workspace.py` — for each FunnelStep with order set, pass FunnelStep.order to per-step funnelOrder in the behavior entry (only meaningful when top-level order="any")
- [x] T036 [US4] Verify global filter and group-by wiring in `_build_funnel_params()` in `src/mixpanel_data/workspace.py` — confirm build_filter_section(where) and build_group_section(group_by) are already called in _build_funnel_params; add integration test if not yet covered
- [x] T037 Run `just check` — all tests pass

**Checkpoint**: Per-step filters, labels, and global filters/group-by work. Funnel queries can be filtered and segmented.

---

## Phase 5: US5+US6 — Exclusions & Holding Property Constant (Priority: P3)

**Goal**: Users can exclude events between funnel steps and hold properties constant across steps.

**Independent Test**: Build params with `exclusions` and `holding_constant` parameters. Verify the generated bookmark JSON has correct `behavior.exclusions[]` and `behavior.aggregateBy[]` entries.

### Tests for Exclusions & HPC

> **Write these tests FIRST, ensure they FAIL before implementation**

- [x] T038 [P] [US5] Write tests for exclusion handling in `_build_funnel_params()` in `tests/test_build_funnel_params.py` — verify string exclusion produces exclusion entry covering all steps; verify Exclusion with from_step/to_step produces entry with steps range; verify default Exclusion (no range) covers all steps
- [x] T039 [P] [US6] Write tests for holding-constant handling in `_build_funnel_params()` in `tests/test_build_funnel_params.py` — verify string produces aggregateBy entry with resourceType="events"; verify HoldingConstant with resource_type="people" produces correct resourceType; verify list of holding constants produces multiple aggregateBy entries
- [x] T040 [P] [US5] Write tests for exclusion validation in `validate_funnel_args()` in `tests/test_validation_funnel.py` — verify empty exclusion event name rejected (F4); verify Exclusion.to_step < from_step rejected; verify Exclusion.to_step exceeding step count rejected

### Implementation for Exclusions & HPC

- [x] T041 [US5] Extend `_build_funnel_params()` in `src/mixpanel_data/workspace.py` — for each exclusion: if string, create entry with event name and steps covering all funnel steps; if Exclusion object, create entry with event name and steps={from: from_step, to: to_step}; set in behavior.exclusions[]
- [x] T042 [US5] Extend `_resolve_and_build_funnel_params()` in `src/mixpanel_data/workspace.py` — normalize exclusions (str→Exclusion(event=s)); pass to _build_funnel_params
- [x] T043 [US6] Extend `_build_funnel_params()` in `src/mixpanel_data/workspace.py` — for each holding_constant: if string, create aggregateBy entry with property name and resourceType="events"; if HoldingConstant object, use its resource_type; set in behavior.aggregateBy[]
- [x] T044 [US6] Extend `_resolve_and_build_funnel_params()` in `src/mixpanel_data/workspace.py` — normalize holding_constant (str→HoldingConstant(property=s)); pass to _build_funnel_params
- [x] T045 [US5] Extend `validate_funnel_args()` in `src/mixpanel_data/_internal/validation.py` — add validation for exclusion step ranges: to_step >= from_step, both within step count bounds
- [x] T046 Run `just check` — all tests pass

**Checkpoint**: All funnel query features complete — exclusions and holding-property-constant work.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Exports, property-based tests, quality assurance

- [x] T047 [P] Add all new public types to exports in `src/mixpanel_data/__init__.py` — add FunnelStep, Exclusion, HoldingConstant, FunnelMathType, FunnelQueryResult to imports and __all__
- [x] T048 [P] Write Hypothesis property-based tests in `tests/test_types_funnel_pbt.py` — FunnelStep immutability invariants, FunnelQueryResult.df shape invariants, FunnelMathType membership, round-trip consistency of build_funnel_params output structure
- [x] T049 [P] Validate quickstart.md examples in `specs/032-funnel-query/quickstart.md` — verify all code snippets are syntactically valid and use correct type names and method signatures
- [x] T050 Run `just check` — full suite passes
- [x] T051 Run `just test-cov` — verify coverage meets 90% threshold for all new code
- [x] T052 Run `just typecheck` — verify mypy --strict passes with zero errors on all new code

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — verification only
- **Foundational (Phase 2)**: Depends on Phase 1 — BLOCKS all user stories
- **Core MVP (Phase 3: US1+US2+US7+US8)**: Depends on Phase 2
- **Filters & Segmentation (Phase 4: US3+US4)**: Depends on Phase 3 (extends builder)
- **Exclusions & HPC (Phase 5: US5+US6)**: Depends on Phase 3 (extends builder); independent of Phase 4
- **Polish (Phase 6)**: Depends on Phases 3-5

### User Story Dependencies

- **US1+US2+US7+US8 (P1)**: Depend on Foundational (Phase 2) — form the MVP together
- **US3 (P2)**: Depends on Phase 3 — extends FunnelStep handling in builder
- **US4 (P2)**: Depends on Phase 3 — verifies global filter/group-by wiring; can run parallel with US3
- **US5 (P3)**: Depends on Phase 3 — extends builder with exclusions; independent of US3/US4
- **US6 (P3)**: Depends on Phase 3 — extends builder with HPC; can run parallel with US5

### Within Each Phase

- Tests MUST be written and FAIL before implementation (strict TDD)
- Implementation tasks within a phase follow dependency order
- `just check` gate at end of each phase

### Parallel Opportunities

- **Phase 2**: T008-T009 (validation tests) can run in parallel with T004-T007 (type tests, sequential within same file); T010-T013 (input types, sequential within same file)
- **Phase 3**: T018-T023 (all tests) can run in parallel
- **Phase 4**: T031-T033 (all tests) can run in parallel; Phase 4 overall can run parallel with Phase 5
- **Phase 5**: T038-T040 (all tests) can run in parallel
- **Phase 6**: T047-T049 can all run in parallel

---

## Parallel Example: Phase 3 (Core MVP Tests)

```text
# Launch all MVP tests in parallel (different files):
Agent: "Write _build_funnel_params tests in tests/test_build_funnel_params.py"
Agent: "Write _transform_funnel_result tests in tests/test_transform_funnel.py"
Agent: "Write query_funnel/build_funnel_params tests in tests/test_workspace_funnel.py"
```

---

## Implementation Strategy

### MVP First (Phase 3 = US1+US2+US7+US8)

1. Complete Phase 1: Setup (verify infrastructure)
2. Complete Phase 2: Foundational (types + validation)
3. Complete Phase 3: Core Funnel MVP
4. **STOP and VALIDATE**: `ws.query_funnel(["Signup", "Purchase"])` works end-to-end
5. This is a shippable increment — basic funnel queries work

### Incremental Delivery

1. Phases 1-3 → Core funnel MVP (shippable)
2. Phase 4 → Per-step filters, labels, segmentation (shippable)
3. Phase 5 → Exclusions and holding-property-constant (shippable)
4. Phase 6 → Polish, PBT tests, exports (release-ready)

### Parallel Strategy

With multiple agents:
1. All complete Setup + Foundational together
2. Once Phase 3 (MVP) is done:
   - Agent A: Phase 4 (US3+US4 — filters & segmentation)
   - Agent B: Phase 5 (US5+US6 — exclusions & HPC)
3. Phase 6 after both complete

---

## Notes

- [P] tasks = different files or independent sections, no dependencies
- [Story] label maps task to specific user story for traceability
- Strict TDD: write tests first, verify they fail, then implement
- Run `just check` at each phase checkpoint
- All new code must pass mypy --strict, ruff check, ruff format
- All public APIs require complete docstrings (per CLAUDE.md)
