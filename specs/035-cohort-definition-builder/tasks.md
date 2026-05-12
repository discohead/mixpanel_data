# Tasks: Cohort Definition Builder

**Input**: Design documents from `/specs/035-cohort-definition-builder/`  
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/public-api.md  
**Tests**: Included (TDD — project mandate per CLAUDE.md)

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

---

## Phase 1: Setup

**Purpose**: No new project setup needed — existing codebase. This phase ensures the test file scaffolding exists.

- [X] T001 Create test file scaffold at tests/unit/test_cohort_definition.py with imports and empty test classes
- [X] T002 [P] Create PBT test file scaffold at tests/test_cohort_definition_pbt.py with Hypothesis imports and profile configuration

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Base dataclass shells and operator mapping dicts that ALL user stories depend on.

**CRITICAL**: No user story work can begin until this phase is complete.

- [X] T003 Add `CohortCriteria` frozen dataclass shell to src/mixpanel_data/types.py with internal fields `_selector_node`, `_behavior_key`, `_behavior` (no class methods yet)
- [X] T004 Add `CohortDefinition` frozen dataclass shell to src/mixpanel_data/types.py with internal fields `_criteria`, `_operator` and placeholder `to_dict()` raising NotImplementedError
- [X] T005 [P] Add `_PROPERTY_OPERATOR_MAP` dict to src/mixpanel_data/types.py mapping CohortCriteria operator strings to selector tree operators (equals→==, not_equals→!=, contains→in, not_contains→not in, greater_than→>, less_than→<, is_set→defined, is_not_set→not defined)
- [X] T006 [P] Add `_FILTER_TO_SELECTOR_MAP` dict to src/mixpanel_data/types.py mapping Filter._operator strings to event selector operators (equals→==, does not equal→!=, contains→in, does not contain→not in, is greater than→>, is less than→<, is set→defined, is not set→not defined, is between→between)

**Checkpoint**: Base types exist — user story implementation can begin.

---

## Phase 3: User Story 1 - Define a Behavioral Cohort Criterion (Priority: P1)

**Goal**: `CohortCriteria.did_event()` produces valid behavioral criteria with frequency + time window + optional event property filters.

**Independent Test**: Construct `CohortCriteria.did_event("Purchase", at_least=3, within_days=30)` and verify internal `_selector_node`, `_behavior_key`, and `_behavior` fields.

### Tests for User Story 1

> **Write these tests FIRST, ensure they FAIL before implementation**

- [X] T007 [US1] Write tests for `did_event()` construction with `at_least` + `within_days` in tests/unit/test_cohort_definition.py — verify `_selector_node` has `property: "behaviors"`, `operator: ">="`, `operand: 3`; verify `_behavior` has event_selector with event name, window with unit+value; verify `_behavior_key` is set
- [X] T008 [P] [US1] Write tests for `did_event()` with `at_most`, `exactly` frequency params and `within_weeks`, `within_months` time constraints in tests/unit/test_cohort_definition.py — verify correct operator mapping (at_most→<=, exactly→==) and window unit mapping (weeks→week, months→month)
- [X] T009 [P] [US1] Write tests for `did_event()` with `from_date`+`to_date` absolute date range in tests/unit/test_cohort_definition.py — verify behavior has from_date/to_date instead of window
- [X] T010 [P] [US1] Write tests for `did_event()` with `where=Filter.equals("plan", "premium")` in tests/unit/test_cohort_definition.py — verify behavior's event_selector.selector contains expression tree with Filter converted to event selector format
- [X] T011 [P] [US1] Write tests for `did_event()` with `where=[Filter.equals("plan", "premium"), Filter.greater_than("amount", 100)]` (multiple filters) in tests/unit/test_cohort_definition.py — verify selector has AND-combined children
- [X] T012 [P] [US1] Write validation error tests for `did_event()` in tests/unit/test_cohort_definition.py — CD1: conflicting frequency params (both at_least and at_most); CD2: negative frequency; CD3: no time constraint; CD3: both within_days and from_date; CD4: empty event name; CD5: from_date without to_date; CD6: invalid date format
- [X] T013 [US1] Write immutability test for CohortCriteria in tests/unit/test_cohort_definition.py — verify frozen dataclass rejects attribute assignment

### Implementation for User Story 1

- [X] T014 [US1] Implement `_build_event_selector()` helper function in src/mixpanel_data/types.py — converts Filter objects to event selector expression tree dicts using `_FILTER_TO_SELECTOR_MAP`, reads Filter._property, _operator, _value, _property_type
- [X] T015 [US1] Implement `CohortCriteria.did_event()` class method in src/mixpanel_data/types.py — validate CD1-CD6, build selector node (property: "behaviors", value: behavior_key, operator from frequency param, operand from frequency value), build behavior dict (event_selector with optional where filters, count type "absolute", window or from_date/to_date)
- [X] T016 [US1] Run tests for US1 and verify all pass in tests/unit/test_cohort_definition.py

**Checkpoint**: `CohortCriteria.did_event()` fully functional with all frequency params, time constraints, event filters, and validation.

---

## Phase 4: User Story 2 - Compose a Multi-Criteria Cohort Definition (Priority: P1)

**Goal**: `CohortDefinition` combines criteria with AND/OR logic and serializes to valid `selector` + `behaviors` JSON via `to_dict()`.

**Independent Test**: Construct `CohortDefinition.all_of(criterion_a, criterion_b)`, call `.to_dict()`, verify output has `selector` and `behaviors` keys with correct structure and globally unique behavior keys.

**Depends on**: US1 (needs at least one criterion type for test inputs)

### Tests for User Story 2

> **Write these tests FIRST, ensure they FAIL before implementation**

- [X] T017 [US2] Write tests for `CohortDefinition.__init__()` with single criterion in tests/unit/test_cohort_definition.py — verify `_criteria` tuple, `_operator` is "and", `.to_dict()` produces dict with `selector` and `behaviors` keys
- [X] T018 [P] [US2] Write tests for `CohortDefinition.all_of()` with two behavioral criteria in tests/unit/test_cohort_definition.py — verify selector has operator "and" with two children, behaviors dict has two entries (bhvr_0, bhvr_1)
- [X] T019 [P] [US2] Write tests for `CohortDefinition.any_of()` in tests/unit/test_cohort_definition.py — verify selector has operator "or"
- [X] T020 [P] [US2] Write tests for nested definitions `any_of(all_of(A, B), C)` in tests/unit/test_cohort_definition.py — verify selector tree nests AND inside OR, verify all behavior keys are globally unique (bhvr_0, bhvr_1, bhvr_2 — no duplicates)
- [X] T021 [P] [US2] Write tests for deeply nested definitions (3+ levels) in tests/unit/test_cohort_definition.py — verify behavior key uniqueness across all levels
- [X] T022 [P] [US2] Write test for `CohortDefinition()` with zero criteria in tests/unit/test_cohort_definition.py — verify ValueError raised (CD9)
- [X] T023 [P] [US2] Write immutability test for CohortDefinition in tests/unit/test_cohort_definition.py — verify frozen dataclass rejects attribute assignment

### Implementation for User Story 2

- [X] T025 [US2] Implement `CohortDefinition.__init__()` in src/mixpanel_data/types.py — accept `*criteria: CohortCriteria`, validate CD9 (at least one), store as tuple, set operator to "and"
- [X] T026 [US2] Implement `CohortDefinition.all_of()` classmethod in src/mixpanel_data/types.py — accept `*criteria: CohortCriteria | CohortDefinition`, validate CD9, set operator to "and"
- [X] T027 [US2] Implement `CohortDefinition.any_of()` classmethod in src/mixpanel_data/types.py — same as all_of but operator "or"
- [X] T028 [US2] Implement `CohortDefinition.to_dict()` in src/mixpanel_data/types.py — recursively collect all behaviors with global re-indexing (bhvr_0, bhvr_1, ...), build selector expression tree by walking criteria/nested definitions, update selector node behavior references to match re-indexed keys, return {"selector": tree, "behaviors": merged_dict}
- [X] T029 [US2] Run tests for US2 and verify all pass in tests/unit/test_cohort_definition.py

**Checkpoint**: `CohortDefinition` fully functional with AND/OR composition, nesting, and serialization.

---

## Phase 5: User Story 3 - Define a Property-Based Cohort Criterion (Priority: P2)

**Goal**: `CohortCriteria.has_property()`, `property_is_set()`, `property_is_not_set()` produce valid property selector nodes.

**Independent Test**: Construct `CohortCriteria.has_property("plan", "premium")` and verify selector node has correct property, value, operator, operand, and type fields.

### Tests for User Story 3

> **Write these tests FIRST, ensure they FAIL before implementation**

- [X] T030 [P] [US3] Write tests for `has_property()` with default operator ("equals") in tests/unit/test_cohort_definition.py — verify selector node: property="user", value="plan", operator="==", operand="premium", type="string"; verify _behavior_key is None, _behavior is None
- [X] T031 [P] [US3] Write tests for `has_property()` with all operators (not_equals, contains, not_contains, greater_than, less_than) in tests/unit/test_cohort_definition.py — verify operator mapping via `_PROPERTY_OPERATOR_MAP`
- [X] T032 [P] [US3] Write tests for `has_property()` with property_type="number" in tests/unit/test_cohort_definition.py — verify type field in selector node
- [X] T033 [P] [US3] Write tests for `property_is_set()` and `property_is_not_set()` in tests/unit/test_cohort_definition.py — verify operators "defined" and "not defined"
- [X] T034 [P] [US3] Write validation error test for `has_property("", "value")` in tests/unit/test_cohort_definition.py — verify ValueError raised (CD7)
- [X] T035 [P] [US3] Write test for property criteria in CohortDefinition.to_dict() in tests/unit/test_cohort_definition.py — verify property-only definition produces empty behaviors dict
- [X] T035b [P] [US3] Write test for definition with only non-behavioral criteria (property criteria) in tests/unit/test_cohort_definition.py — verify `behaviors` dict is empty `{}` (moved from US2 — requires property criteria to exist)

### Implementation for User Story 3

- [X] T036 [US3] Implement `CohortCriteria.has_property()` class method in src/mixpanel_data/types.py — validate CD7, build selector node with property="user", map operator via `_PROPERTY_OPERATOR_MAP`, set _behavior_key=None, _behavior=None
- [X] T037 [US3] Implement `CohortCriteria.property_is_set()` and `property_is_not_set()` class methods in src/mixpanel_data/types.py — delegate to has_property with appropriate operator
- [X] T038 [US3] Run tests for US3 and verify all pass in tests/unit/test_cohort_definition.py

**Checkpoint**: All three property criteria methods functional. Property-only definitions serialize correctly.

---

## Phase 6: User Story 4 - Reference a Saved Cohort in a Definition (Priority: P2)

**Goal**: `CohortCriteria.in_cohort()` and `not_in_cohort()` produce valid cohort reference selector nodes.

**Independent Test**: Construct `CohortCriteria.in_cohort(456)` and verify selector node has `property: "cohort"`, `value: 456`, `operator: "in"`.

### Tests for User Story 4

> **Write these tests FIRST, ensure they FAIL before implementation**

- [X] T039 [P] [US4] Write tests for `in_cohort(456)` in tests/unit/test_cohort_definition.py — verify selector node: property="cohort", value=456, operator="in"; verify _behavior_key is None, _behavior is None
- [X] T040 [P] [US4] Write tests for `not_in_cohort(456)` in tests/unit/test_cohort_definition.py — verify operator="not in"
- [X] T041 [P] [US4] Write validation error tests for `in_cohort(0)`, `in_cohort(-1)` in tests/unit/test_cohort_definition.py — verify ValueError raised (CD8)
- [X] T042 [P] [US4] Write test for cohort criteria in CohortDefinition.to_dict() in tests/unit/test_cohort_definition.py — verify cohort-only definition produces correct selector and empty behaviors

### Implementation for User Story 4

- [X] T043 [US4] Implement `CohortCriteria.in_cohort()` and `not_in_cohort()` class methods in src/mixpanel_data/types.py — validate CD8 (positive integer), build selector node with property="cohort", value=cohort_id, operator "in"/"not in", set _behavior_key=None, _behavior=None
- [X] T044 [US4] Run tests for US4 and verify all pass in tests/unit/test_cohort_definition.py

**Checkpoint**: All cohort reference methods functional. Mixed definitions (behavioral + property + cohort) serialize correctly.

---

## Phase 7: User Story 5 - Use Definition with Cohort CRUD (Priority: P2)

**Goal**: `CohortDefinition.to_dict()` output integrates with existing `CreateCohortParams` — `model_dump()` flattens `selector` and `behaviors` to top level.

**Independent Test**: Construct a definition, pass `to_dict()` to `CreateCohortParams(name="Test", definition=...)`, verify `model_dump(exclude_none=True)` has `name`, `selector`, `behaviors` at top level.

**Depends on**: US1 (behavioral criteria) and US3 (property criteria) for realistic test inputs

### Tests for User Story 5

> **Write these tests FIRST, ensure they FAIL before implementation**

- [X] T045 [US5] Write integration test in tests/unit/test_cohort_definition.py — construct CohortDefinition with behavioral + property criteria, pass to_dict() to CreateCohortParams(name="Test", definition=...), verify model_dump(exclude_none=True) has keys: name, selector, behaviors at top level (no definition key)
- [X] T046 [P] [US5] Write integration test for nested boolean definition with CRUD in tests/unit/test_cohort_definition.py — verify complex nested definition flattens correctly
- [X] T047 [P] [US5] Write test that to_dict() output is JSON-serializable in tests/unit/test_cohort_definition.py — json.dumps(cohort.to_dict()) succeeds without errors

### Implementation for User Story 5

- [X] T048 [US5] No new implementation needed — this phase validates existing functionality. Run tests and verify all pass. Fix any integration issues discovered.

**Checkpoint**: Builder output confirmed compatible with existing CRUD pipeline.

---

## Phase 8: User Story 6 - Convenience Shorthand for "Did Not Do" (Priority: P3)

**Goal**: `CohortCriteria.did_not_do_event()` is equivalent to `did_event(exactly=0, ...)`.

**Independent Test**: Verify `did_not_do_event("Login", within_days=30)` produces same internal state as `did_event("Login", exactly=0, within_days=30)`.

**Depends on**: US1 (`did_event`)

### Tests for User Story 6

> **Write these tests FIRST, ensure they FAIL before implementation**

- [X] T049 [US6] Write test for `did_not_do_event("Login", within_days=30)` in tests/unit/test_cohort_definition.py — verify result is equivalent to `did_event("Login", exactly=0, within_days=30)` by comparing _selector_node, _behavior_key, _behavior
- [X] T050 [P] [US6] Write test for `did_not_do_event()` with all time constraint variants (within_weeks, within_months, from_date+to_date) in tests/unit/test_cohort_definition.py

### Implementation for User Story 6

- [X] T051 [US6] Implement `CohortCriteria.did_not_do_event()` class method in src/mixpanel_data/types.py — delegate to `did_event(event, exactly=0, ...)`
- [X] T052 [US6] Run tests for US6 and verify all pass in tests/unit/test_cohort_definition.py

**Checkpoint**: All 7 CohortCriteria class methods fully implemented and tested.

---

## Phase 9: Polish & Cross-Cutting Concerns

**Purpose**: Property-based tests, public exports, type checking, and final validation.

- [X] T053 [P] Write Hypothesis PBT tests for CohortCriteria construction in tests/test_cohort_definition_pbt.py — generate random valid did_event params, verify no crashes, valid selector structure, behavior key always set
- [X] T054 [P] Write Hypothesis PBT tests for CohortDefinition.to_dict() in tests/test_cohort_definition_pbt.py — generate random trees of criteria (varying depth, mix of types), verify: no duplicate behavior keys, selector tree is valid (has operator+children or property+value), behaviors dict keys match selector references, output is JSON-serializable
- [X] T055 [P] Write Hypothesis PBT tests for validation rules in tests/test_cohort_definition_pbt.py — generate invalid inputs (multiple frequency params, missing time constraints, empty names, non-positive IDs), verify ValueError always raised
- [X] T056 Add `CohortCriteria` and `CohortDefinition` to public exports in src/mixpanel_data/__init__.py
- [X] T057 Run `just typecheck` and fix any mypy --strict errors in src/mixpanel_data/types.py
- [X] T058 Run `just lint` and fix any ruff errors
- [X] T059 Run `just test-cov` and verify 90%+ coverage for new code
- [X] T060 Run `just test-pbt` to verify all Hypothesis tests pass
- [X] T061 Validate quickstart.md examples — run each code snippet from specs/035-cohort-definition-builder/quickstart.md in a Python REPL (imports + construction + to_dict() calls)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — can start immediately
- **Foundational (Phase 2)**: Depends on Phase 1 — BLOCKS all user stories
- **US1 (Phase 3)**: Depends on Phase 2 — behavioral criteria
- **US2 (Phase 4)**: Depends on US1 — needs criteria for composition tests
- **US3 (Phase 5)**: Depends on Phase 2 — independent of US1/US2
- **US4 (Phase 6)**: Depends on Phase 2 — independent of US1/US2/US3
- **US5 (Phase 7)**: Depends on US1 + US3 — needs mixed criteria for realistic tests
- **US6 (Phase 8)**: Depends on US1 — extends did_event()
- **Polish (Phase 9)**: Depends on all user stories complete

### User Story Dependencies

```text
Phase 2 (Foundational)
    ├──→ US1 (P1: Behavioral) ──→ US2 (P1: Composition) ──→ US5 (P2: CRUD)
    │                          └──→ US6 (P3: Did Not Do)
    ├──→ US3 (P2: Property) ──────────────────────────────→ US5 (P2: CRUD)
    └──→ US4 (P2: Cohort Ref) ─── independent
```

### Parallel Opportunities

- **Phase 2**: T003-T006 all in parallel (different sections of types.py, but non-overlapping)
- **Phase 3**: T007-T013 test tasks in parallel (same file, different test classes)
- **Phase 5 + Phase 6**: US3 and US4 can run in parallel after Phase 2 (independent criteria types)
- **Phase 9**: T053-T055 PBT tests in parallel, T057-T060 checks in parallel

---

## Parallel Example: US3 + US4 (after Phase 2)

```text
# These two user stories are independent and can run in parallel:

Agent 1 — US3 (Property Criteria):
  T030-T035: Write property criteria tests
  T036-T037: Implement has_property, property_is_set, property_is_not_set
  T038: Verify

Agent 2 — US4 (Cohort References):
  T039-T042: Write cohort reference tests
  T043: Implement in_cohort, not_in_cohort
  T044: Verify
```

---

## Implementation Strategy

### MVP First (US1 + US2)

1. Complete Phase 1: Setup (test scaffolds)
2. Complete Phase 2: Foundational (dataclass shells, operator maps)
3. Complete Phase 3: US1 — `did_event()` with full validation
4. Complete Phase 4: US2 — `CohortDefinition` composition + `to_dict()`
5. **STOP and VALIDATE**: Build a cohort definition and inspect JSON output
6. At this point, `CohortDefinition(CohortCriteria.did_event(...)).to_dict()` works end-to-end

### Incremental Delivery

1. Setup + Foundational → Shells exist
2. US1 → Behavioral criteria work → Can construct criteria
3. US2 → Composition works → Can produce valid JSON
4. US3 + US4 (parallel) → Property and cohort criteria → Full criteria coverage
5. US5 → CRUD integration verified → Builder usable with existing API
6. US6 → Convenience shorthand → Polish
7. Polish → PBT, exports, type safety → Production ready

---

## Notes

- [P] tasks = different files or non-overlapping file sections, no dependencies
- [Story] label maps task to specific user story for traceability
- TDD workflow: write failing tests → implement → verify → commit
- Commit after each completed user story phase
- All validation raises `ValueError` directly (not `ValidationError` collector pattern)
- Behavior keys are placeholder during construction, globally re-indexed in `to_dict()`
