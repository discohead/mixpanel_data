# Tasks: Custom Properties in Queries

**Input**: Design documents from `/specs/037-custom-properties-queries/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/public-api.md, quickstart.md

**Tests**: Included — project mandates strict TDD (CLAUDE.md: "Never write implementation code without a failing test first").

**Organization**: Tasks grouped by user story. US4 (inline formula definitions) is folded into the Foundational phase because the types it defines are prerequisites for all other stories.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

---

## Phase 1: Setup

**Purpose**: No project initialization needed — existing project, existing branch.

_(No tasks — branch `037-custom-properties-queries` already created and checked out.)_

---

## Phase 2: Foundational — New Types & Type Widening

**Purpose**: Create the three new frozen dataclasses, widen existing type signatures, add the composed properties builder helper, and export new types. This phase also satisfies **US4 (Inline Formula Definitions)** — the `InlineCustomProperty`, `PropertyInput`, and `.numeric()` convenience constructor ARE the inline formula user experience.

**CRITICAL**: No user story work can begin until this phase is complete.

### Tests (write FIRST, verify they FAIL)

- [x] T001 [P] Write tests for PropertyInput construction: minimal (name only), explicit number type, user resource_type, all 5 valid types (string, number, boolean, datetime, list) in tests/test_custom_property_types.py
- [x] T002 [P] Write tests for InlineCustomProperty construction: minimal (formula + single input), full (all fields explicit) in tests/test_custom_property_types.py
- [x] T003 [P] Write tests for InlineCustomProperty.numeric() convenience constructor: multi-input (A * B) and single-input (A) cases in tests/test_custom_property_types.py
- [x] T004 [P] Write tests for CustomPropertyRef construction: stores integer ID in tests/test_custom_property_types.py
- [x] T005 [P] Write tests for immutability: FrozenInstanceError on PropertyInput.name, InlineCustomProperty.formula, CustomPropertyRef.id in tests/test_custom_property_types.py
- [x] T006 [P] Write tests for _build_composed_properties(): single input, multiple inputs, user resource_type preservation in tests/test_custom_property_builders.py

### Implementation

- [x] T007 Add PropertyInput frozen dataclass (name, type, resource_type with defaults) in src/mixpanel_data/types.py
- [x] T008 Add InlineCustomProperty frozen dataclass (formula, inputs, property_type, resource_type) with numeric() classmethod in src/mixpanel_data/types.py
- [x] T009 Add CustomPropertyRef frozen dataclass (id) in src/mixpanel_data/types.py
- [x] T010 Add PropertySpec type alias (str | CustomPropertyRef | InlineCustomProperty) in src/mixpanel_data/types.py
- [x] T011 Widen Metric.property from str | None to str | CustomPropertyRef | InlineCustomProperty | None in src/mixpanel_data/types.py
- [x] T012 Widen GroupBy.property from str to str | CustomPropertyRef | InlineCustomProperty in src/mixpanel_data/types.py
- [x] T013 Widen Filter._property and all 18 class method property parameters from str to str | CustomPropertyRef | InlineCustomProperty in src/mixpanel_data/types.py
- [x] T014 Add _build_composed_properties() helper function and update imports (CustomPropertyRef, InlineCustomProperty, PropertyInput) in src/mixpanel_data/_internal/bookmark_builders.py
- [x] T015 Add CustomPropertyRef, InlineCustomProperty, PropertyInput to imports and __all__ in src/mixpanel_data/__init__.py
- [x] T016 Run just typecheck to verify type widening is backward-compatible and all new types pass mypy --strict

**Checkpoint**: All type construction tests green. `just typecheck` passes. US4 acceptance scenarios 1-7 verified. Existing tests unchanged.

---

## Phase 3: User Story 1 — Break Down by Custom Properties (Priority: P1)

**Goal**: Update `build_group_section()` to produce correct bookmark JSON for `CustomPropertyRef` and `InlineCustomProperty` in the `group_by` position.

**Independent Test**: Pass a custom property to `group_by` in `build_params()` and verify the group section of the bookmark JSON contains the correct `customPropertyId` or `customProperty` dict.

### Tests (write FIRST, verify they FAIL)

- [x] T017 [P] [US1] Write test for build_group_section with plain string property unchanged (backward compat) in tests/test_custom_property_builders.py
- [x] T018 [P] [US1] Write test for build_group_section with GroupBy(property=CustomPropertyRef(42)): verify customPropertyId, no value/propertyName in tests/test_custom_property_builders.py
- [x] T019 [P] [US1] Write test for build_group_section with GroupBy(property=InlineCustomProperty.numeric(...)): verify customProperty dict with displayFormula, composedProperties in tests/test_custom_property_builders.py
- [x] T020 [P] [US1] Write test for bucketing (bucket_size, bucket_min, bucket_max) with CustomPropertyRef and InlineCustomProperty in tests/test_custom_property_builders.py
- [x] T021 [P] [US1] Write test for InlineCustomProperty.property_type overriding GroupBy.property_type in tests/test_custom_property_builders.py
- [ ] T021b [P] [US1] Write test for InlineCustomProperty.property_type=None falling back to GroupBy.property_type in tests/test_custom_property_builders.py
- [x] T022 [P] [US1] Write test for mixed group_by list (plain string + CustomPropertyRef + InlineCustomProperty) in tests/test_custom_property_builders.py
- [x] T023 [P] [US1] Write end-to-end tests for build_params, build_funnel_params, build_retention_params with custom property group_by in tests/test_custom_property_query.py

### Implementation

- [x] T024 [US1] Update build_group_section() GroupBy branch with three-way isinstance dispatch (str, CustomPropertyRef, InlineCustomProperty) in src/mixpanel_data/_internal/bookmark_builders.py (imports already added in T014)

**Checkpoint**: All group-by builder tests green. Group-by custom properties work in insights, funnels, and retention.

---

## Phase 4: User Story 2 — Filter by Custom Properties (Priority: P1)

**Goal**: Update `build_filter_entry()` to produce correct bookmark JSON for `CustomPropertyRef` and `InlineCustomProperty` in the `where` position.

**Independent Test**: Pass a custom property to a `Filter` class method and use it in `build_params()` `where=` — verify the filter section contains `customPropertyId` or `customProperty` dict.

### Tests (write FIRST, verify they FAIL)

- [x] T026 [P] [US2] Write test for build_filter_entry with plain string unchanged (backward compat, no customPropertyId/customProperty) in tests/test_custom_property_builders.py
- [x] T027 [P] [US2] Write test for build_filter_entry with CustomPropertyRef: verify customPropertyId, no value field, filterOperator preserved in tests/test_custom_property_builders.py
- [x] T028 [P] [US2] Write test for build_filter_entry with InlineCustomProperty: verify customProperty dict, no value field, filterValue preserved in tests/test_custom_property_builders.py
- [x] T029 [P] [US2] Write test for InlineCustomProperty filterType/defaultType using property_type in tests/test_custom_property_builders.py
- [x] T030 [P] [US2] Write test for CustomPropertyRef preserving Filter's resource_type (e.g., "people") in tests/test_custom_property_builders.py
- [x] T031 [P] [US2] Write test for InlineCustomProperty using its own resource_type in filter entry in tests/test_custom_property_builders.py
- [x] T032 [P] [US2] Write end-to-end tests for build_params with custom property filter (ref and inline) in tests/test_custom_property_query.py

### Implementation

- [x] T033 [US2] Update build_filter_entry() with three-way isinstance dispatch (str, CustomPropertyRef, InlineCustomProperty) in src/mixpanel_data/_internal/bookmark_builders.py

**Checkpoint**: All filter builder tests green. Filter custom properties work across all query methods.

---

## Phase 5: User Story 3 — Aggregate Metrics on Custom Properties (Priority: P2)

**Goal**: Update measurement property construction in `_build_query_params()` and `_build_funnel_params()` to produce correct bookmark JSON for `CustomPropertyRef` and `InlineCustomProperty` in the `Metric.property` position.

**Independent Test**: Pass a custom property to `Metric.property` with a property-based math type and verify the measurement section of the bookmark JSON.

### Tests (write FIRST, verify they FAIL)

- [x] T034 [P] [US3] Write test for plain string Metric.property measurement unchanged (backward compat) in tests/test_custom_property_builders.py
- [x] T035 [P] [US3] Write test for CustomPropertyRef in measurement: verify customPropertyId, resourceType, no name field in tests/test_custom_property_builders.py
- [x] T036 [P] [US3] Write test for InlineCustomProperty in measurement: verify customProperty dict, resourceType, no name field in tests/test_custom_property_builders.py
- [x] T037 [P] [US3] Write test for top-level math_property as plain string unchanged (backward compat) in tests/test_custom_property_builders.py
- [x] T038 [P] [US3] Write end-to-end test for build_params with Metric(property=CustomPropertyRef(...)) in tests/test_custom_property_query.py
- [x] T039 [P] [US3] Write end-to-end test for build_params with Metric(property=InlineCustomProperty.numeric(...)) in tests/test_custom_property_query.py
- [x] T040 [P] [US3] Write end-to-end test for build_funnel_params with custom property measurement in tests/test_custom_property_query.py

### Implementation

- [x] T041 [US3] Update imports in src/mixpanel_data/workspace.py to include CustomPropertyRef, InlineCustomProperty
- [x] T042 [US3] Update measurement property builder in _build_query_params() with three-way isinstance dispatch in src/mixpanel_data/workspace.py
- [x] T043 [US3] Update measurement property builder in _build_funnel_params() with three-way isinstance dispatch in src/mixpanel_data/workspace.py

**Checkpoint**: All measurement builder tests green. Metric aggregation on custom properties works in insights and funnels.

---

## Phase 6: Combined End-to-End Tests

**Purpose**: Verify custom properties work when combined across multiple positions and query engines.

- [x] T044 [P] Write test for CustomPropertyRef in group_by + InlineCustomProperty in where (combined) in tests/test_custom_property_query.py
- [x] T045 [P] Write test for all three positions simultaneously (Metric.property + group_by + where) in tests/test_custom_property_query.py
- [x] T046 Run just test to verify all tests pass and no regressions

**Checkpoint**: All end-to-end tests green. All existing tests still pass.

---

## Phase 7: User Story 5 — Fail-Fast Validation (Priority: P3)

**Goal**: Add 6 validation rules (CP1-CP6) via `_validate_custom_property()` helper and integrate into all three query validation pipelines.

**Independent Test**: Construct invalid custom property specs and verify that descriptive validation errors are raised before any API call.

### Tests (write FIRST, verify they FAIL)

- [x] T047 [P] [US5] Write test for CP1: CustomPropertyRef(0) and CustomPropertyRef(-1) in group_by raise validation error with "positive integer" in tests/test_custom_property_types.py
- [x] T048 [P] [US5] Write test for CP2: InlineCustomProperty with empty and whitespace-only formula raises "non-empty" in tests/test_custom_property_types.py
- [x] T049 [P] [US5] Write test for CP3: InlineCustomProperty with empty inputs dict raises "at least one input" in tests/test_custom_property_types.py
- [x] T050 [P] [US5] Write test for CP4: lowercase key, multi-char key, numeric key raise "uppercase" in tests/test_custom_property_types.py
- [x] T051 [P] [US5] Write test for CP5: formula > 20,000 chars raises "20,000" in tests/test_custom_property_types.py
- [x] T052 [P] [US5] Write test for CP6: PropertyInput with empty name raises "empty property name" in tests/test_custom_property_types.py
- [x] T053 [P] [US5] Write tests for valid InlineCustomProperty and valid CustomPropertyRef passing validation in tests/test_custom_property_types.py
- [x] T054 [P] [US5] Write tests for CP validation in where position (CustomPropertyRef(0) in Filter) in tests/test_custom_property_types.py
- [x] T055 [P] [US5] Write tests for CP validation in Metric.property position in tests/test_custom_property_types.py
- [x] T056 [P] [US5] Write tests for CP validation in funnel group_by and retention where positions in tests/test_custom_property_types.py

### Implementation

- [x] T057 [US5] Update imports in src/mixpanel_data/_internal/validation.py to include CustomPropertyRef, InlineCustomProperty
- [x] T058 [US5] Add _validate_custom_property() helper with CP1-CP6 rules in src/mixpanel_data/_internal/validation.py
- [x] T059 [US5] Integrate CP validation into validate_query_args() — scan group_by, where, and Metric.property in src/mixpanel_data/_internal/validation.py
- [x] T060 [US5] Integrate CP validation into validate_funnel_args() — scan group_by and where in src/mixpanel_data/_internal/validation.py
- [x] T061 [US5] Integrate CP validation into validate_retention_args() — scan group_by and where in src/mixpanel_data/_internal/validation.py

**Checkpoint**: All validation tests green. CP1-CP6 enforced across all pipelines.

---

## Phase 8: User Story 6 — Quality Assurance (Priority: P3)

**Goal**: Property-based tests with Hypothesis and mutation testing with mutmut to verify robustness across random inputs.

**Independent Test**: Run PBT suite and mutation testing, verify target scores.

### Implementation

- [x] T062 [P] [US6] Write Hypothesis strategies for valid PropertyInput (non-empty name, valid type, valid resource_type) in tests/test_custom_property_pbt.py
- [x] T063 [P] [US6] Write Hypothesis strategies for valid input keys (A-Z) and valid inputs dict (1-5 entries) in tests/test_custom_property_pbt.py
- [x] T064 [P] [US6] Write PBT test: PropertyInput round-trip — all field values survive construction in tests/test_custom_property_pbt.py
- [x] T065 [P] [US6] Write PBT test: InlineCustomProperty construction preserves formula and inputs in tests/test_custom_property_pbt.py
- [x] T066 [P] [US6] Write PBT test: _build_composed_properties() output keys match input keys exactly in tests/test_custom_property_pbt.py
- [x] T067 [P] [US6] Write PBT test: _build_composed_properties() output values have required fields (value, type, resourceType) in tests/test_custom_property_pbt.py
- [x] T068 [US6] Run just test-pbt to verify all property-based tests pass

**Checkpoint**: PBT suite green across all Hypothesis profiles.

---

## Phase 9: Polish & Cross-Cutting Concerns

**Purpose**: Final quality gates, docstrings, coverage, and mutation testing.

- [x] T069 [P] Verify all docstrings complete with examples on PropertyInput, InlineCustomProperty, CustomPropertyRef in src/mixpanel_data/types.py
- [x] T070 [P] Verify docstrings on _build_composed_properties() and updated builder functions in src/mixpanel_data/_internal/bookmark_builders.py
- [x] T071 [P] Verify docstrings on _validate_custom_property() in src/mixpanel_data/_internal/validation.py
- [x] T072 Run just check — all green (ruff format + ruff check + mypy --strict + pytest)
- [x] T073 Run just test-cov — verify coverage >= 90%
- [x] T074 Run mutation testing on custom property code — verify mutation score >= 80%
- [x] T075 Validate quickstart.md code examples execute correctly

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No tasks needed
- **Foundational (Phase 2)**: No dependencies — BLOCKS all user stories
- **US1 (Phase 3)**: Depends on Phase 2 completion
- **US2 (Phase 4)**: Depends on Phase 2 completion — **can run in parallel with Phase 3** (different builder branch)
- **US3 (Phase 5)**: Depends on Phase 2 completion — **can run in parallel with Phases 3-4** (different file: workspace.py)
- **Combined E2E (Phase 6)**: Depends on Phases 3, 4, and 5
- **US5 Validation (Phase 7)**: Depends on Phase 6 (validates built params from all positions)
- **US6 Quality (Phase 8)**: Depends on Phase 2 (tests type construction invariants)  — **can run in parallel with Phases 3-7**
- **Polish (Phase 9)**: Depends on all previous phases

### User Story Dependencies

- **US4 (P2)**: Satisfied by Phase 2 (Foundational) — types ARE the feature
- **US1 (P1)**: Independent after Phase 2 — group_by builder
- **US2 (P1)**: Independent after Phase 2 — filter builder (parallel with US1)
- **US3 (P2)**: Independent after Phase 2 — measurement builder (parallel with US1/US2)
- **US5 (P3)**: Depends on US1/US2/US3 completion (validates all positions)
- **US6 (P3)**: Independent after Phase 2 — PBT tests on types (parallel with US1/US2/US3)

### Within Each User Story

- Tests MUST be written and FAIL before implementation
- Builder implementation after tests
- End-to-end tests verify full pipeline

### Parallel Opportunities

```
Phase 2 (Foundational)
    ├── Phase 3 (US1: group_by)  ─┐
    ├── Phase 4 (US2: filter)    ─┼── All parallel after Phase 2
    ├── Phase 5 (US3: metric)    ─┤
    └── Phase 8 (US6: PBT)      ─┘
                                   │
                              Phase 6 (Combined E2E) ← needs 3+4+5
                                   │
                              Phase 7 (US5: Validation)
                                   │
                              Phase 9 (Polish)
```

---

## Parallel Example: Phases 3-5 (After Foundational)

```bash
# These can all run in parallel — different files, no dependencies:

# Agent 1: US1 group_by (bookmark_builders.py — build_group_section branch)
Task: "Write tests + update build_group_section() for custom properties"

# Agent 2: US2 filter (bookmark_builders.py — build_filter_entry branch)
Task: "Write tests + update build_filter_entry() for custom properties"

# Agent 3: US3 measurement (workspace.py — _build_query_params branch)
Task: "Write tests + update measurement property builder for custom properties"

# Agent 4: US6 PBT (test_custom_property_pbt.py — independent)
Task: "Write Hypothesis strategies and property-based tests"
```

---

## Implementation Strategy

### MVP First (Foundational + US1 Only)

1. Complete Phase 2: Foundational (types + widening + composed properties helper)
2. Complete Phase 3: US1 (group_by builder)
3. **STOP and VALIDATE**: Custom property breakdowns work in insights, funnels, retention
4. This alone delivers significant value — computed breakdowns are the #1 use case

### Incremental Delivery

1. Phase 2 → Types ready (US4 satisfied)
2. + Phase 3 → Group-by works (US1)
3. + Phase 4 → Filter works (US2)
4. + Phase 5 → Measurement works (US3)
5. + Phase 7 → Validation catches errors (US5)
6. + Phase 8 → PBT proves robustness (US6)
7. + Phase 9 → Polish and quality gates

### Parallel Strategy

With multiple agents after Phase 2:
- Agent A: US1 (group_by) + US2 (filter) — same file, different branches
- Agent B: US3 (measurement) — different file (workspace.py)
- Agent C: US6 (PBT) — independent test file
- Then converge: Combined E2E → Validation → Polish

---

## Notes

- [P] tasks = different files or independent test cases, no dependencies
- [Story] label maps task to specific user story for traceability
- US4 is satisfied by Phase 2 (Foundational) — the types ARE the inline formula experience
- Phases 3, 4, 5 modify different builder branches and can proceed in parallel
- Phase 8 (PBT) is independent of story implementations — tests type-level invariants
- Total: 75 tasks (16 foundational, 9 US1, 8 US2, 10 US3, 3 combined, 15 US5, 7 US6, 7 polish) — T025 removed (imports moved to T014), T021b added (FR-015 fallback test)
