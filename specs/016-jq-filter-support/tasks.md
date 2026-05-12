# Tasks: JQ Filter Support for CLI Output

**Input**: Design documents from `/specs/016-jq-filter-support/`
**Prerequisites**: plan.md (required), spec.md (required), research.md, data-model.md, quickstart.md

**Tests**: Included per project TDD requirements (CLAUDE.md mandates strict TDD).

**Organization**: Tasks grouped by user story for independent implementation and testing.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

- **Single project**: `src/mixpanel_data/`, `tests/` at repository root
- Uses existing CLI structure in `src/mixpanel_data/cli/`

---

## Phase 1: Setup

**Purpose**: Add jq.py dependency to project

- [X] T001 Add `jq>=1.9.0` to dependencies in pyproject.toml
- [X] T002 Run `uv sync` to install new dependency and verify import works

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user story can be implemented

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [X] T003 Add JqOption type alias in src/mixpanel_data/cli/options.py
- [X] T004 Add jq_filter parameter to output_result() signature in src/mixpanel_data/cli/utils.py
- [X] T005 Add jq_filter parameter to present_result() signature in src/mixpanel_data/cli/utils.py

**Checkpoint**: Foundation ready - user story implementation can now begin

---

## Phase 3: User Story 1 - Filter JSON Output with jq Expression (Priority: P1) 🎯 MVP

**Goal**: Users can filter and transform JSON output using jq syntax

**Independent Test**: Run `mp inspect events --format json --jq '.[0]'` and verify only first event is returned

### Tests for User Story 1 (TDD - Write FIRST, verify FAIL)

- [X] T006 [P] [US1] Unit test for _apply_jq_filter with simple dict field extraction in tests/unit/cli/test_utils.py
- [X] T007 [P] [US1] Unit test for _apply_jq_filter with list iteration in tests/unit/cli/test_utils.py
- [X] T008 [P] [US1] Unit test for _apply_jq_filter with select filter in tests/unit/cli/test_utils.py
- [X] T009 [P] [US1] Unit test for _apply_jq_filter with length filter in tests/unit/cli/test_utils.py
- [X] T010 [P] [US1] Unit test for _apply_jq_filter single vs multiple results handling in tests/unit/cli/test_utils.py
- [X] T011 [P] [US1] Unit test for output_result with jq_filter for JSON format in tests/unit/cli/test_utils.py

### Implementation for User Story 1

- [X] T012 [US1] Implement _apply_jq_filter() function in src/mixpanel_data/cli/utils.py
- [X] T013 [US1] Integrate _apply_jq_filter into output_result() for json format in src/mixpanel_data/cli/utils.py
- [X] T014 [US1] Integrate _apply_jq_filter into output_result() for jsonl format in src/mixpanel_data/cli/utils.py
- [X] T015 [US1] Verify all US1 tests pass with `just test -k test_apply_jq_filter`

**Checkpoint**: Basic jq filtering works. Can filter JSON output with jq expressions.

---

## Phase 4: User Story 2 - Receive Clear Error for Invalid jq Syntax (Priority: P2)

**Goal**: Users receive clear, actionable error messages when jq filter syntax is invalid

**Independent Test**: Run `mp inspect events --format json --jq '.name |'` and verify clear syntax error message

### Tests for User Story 2 (TDD - Write FIRST, verify FAIL)

- [X] T016 [P] [US2] Unit test for _apply_jq_filter with invalid syntax raises typer.Exit in tests/unit/cli/test_utils.py
- [X] T017 [P] [US2] Unit test for _apply_jq_filter error message contains "jq" in tests/unit/cli/test_utils.py
- [X] T018 [P] [US2] Unit test for _apply_jq_filter exits with ExitCode.INVALID_ARGS in tests/unit/cli/test_utils.py

### Implementation for User Story 2

- [X] T019 [US2] Add ValueError exception handling for jq compile errors in _apply_jq_filter() in src/mixpanel_data/cli/utils.py
- [X] T020 [US2] Format error message with "jq filter error:" prefix in src/mixpanel_data/cli/utils.py
- [X] T021 [US2] Verify all US2 tests pass with `just test -k test_apply_jq_filter`

**Checkpoint**: Invalid jq syntax produces clear error messages with exit code 3.

---

## Phase 5: User Story 3 - Receive Error for Incompatible Format (Priority: P2)

**Goal**: Users are informed when `--jq` is used with non-JSON formats

**Independent Test**: Run `mp inspect events --format table --jq '.[]'` and verify error stating jq requires JSON format

### Tests for User Story 3 (TDD - Write FIRST, verify FAIL)

- [X] T022 [P] [US3] Unit test for output_result rejects jq_filter with table format in tests/unit/cli/test_utils.py
- [X] T023 [P] [US3] Unit test for output_result rejects jq_filter with csv format in tests/unit/cli/test_utils.py
- [X] T024 [P] [US3] Unit test for output_result rejects jq_filter with plain format in tests/unit/cli/test_utils.py
- [X] T025 [P] [US3] Unit test for output_result error message mentions json/jsonl requirement in tests/unit/cli/test_utils.py

### Implementation for User Story 3

- [X] T026 [US3] Add format validation check at start of output_result() in src/mixpanel_data/cli/utils.py
- [X] T027 [US3] Print clear error message and raise typer.Exit(ExitCode.INVALID_ARGS) in src/mixpanel_data/cli/utils.py
- [X] T028 [US3] Verify all US3 tests pass with `just test -k test_output_result`

**Checkpoint**: Incompatible format combinations produce clear error messages.

---

## Phase 6: User Story 4 - Handle jq Runtime Errors Gracefully (Priority: P3)

**Goal**: Users receive helpful error messages when jq filter fails at runtime

**Independent Test**: Run `mp inspect events --format json --jq '.[0]'` on dict data and verify runtime error message

### Tests for User Story 4 (TDD - Write FIRST, verify FAIL)

- [X] T029 [P] [US4] Unit test for _apply_jq_filter runtime error (index dict as array) in tests/unit/cli/test_utils.py
- [X] T030 [P] [US4] Unit test for _apply_jq_filter runtime error message is helpful in tests/unit/cli/test_utils.py
- [X] T031 [P] [US4] Unit test for _apply_jq_filter runtime error exits with ExitCode.INVALID_ARGS in tests/unit/cli/test_utils.py

### Implementation for User Story 4

- [X] T032 [US4] Ensure ValueError from jq.input() is caught in _apply_jq_filter() in src/mixpanel_data/cli/utils.py
- [X] T033 [US4] Verify runtime error message is distinguishable from syntax error in src/mixpanel_data/cli/utils.py
- [X] T034 [US4] Verify all US4 tests pass with `just test -k test_apply_jq_filter`

**Checkpoint**: Runtime errors produce helpful error messages.

---

## Phase 7: User Story 5 - Empty Results Handled Gracefully (Priority: P3)

**Goal**: Users see empty array `[]` when jq filter matches no items, with success exit code

**Independent Test**: Run `mp inspect events --format json --jq '.[] | select(.x > 9999)'` and verify `[]` output with exit 0

### Tests for User Story 5 (TDD - Write FIRST, verify FAIL)

- [X] T035 [P] [US5] Unit test for _apply_jq_filter returns "[]" when no results in tests/unit/cli/test_utils.py
- [X] T036 [P] [US5] Unit test for _apply_jq_filter empty results does NOT raise exception in tests/unit/cli/test_utils.py

### Implementation for User Story 5

- [X] T037 [US5] Handle empty results list in _apply_jq_filter() returning "[]" in src/mixpanel_data/cli/utils.py
- [X] T038 [US5] Verify all US5 tests pass with `just test -k test_apply_jq_filter`

**Checkpoint**: Empty results handled gracefully with success exit code.

---

## Phase 8: Command Updates

**Purpose**: Add jq_filter parameter to all commands with --format option

### inspect.py Commands

- [X] T039 [P] Add jq_filter param to inspect events command in src/mixpanel_data/cli/commands/inspect.py
- [X] T040 [P] Add jq_filter param to inspect properties command in src/mixpanel_data/cli/commands/inspect.py
- [X] T041 [P] Add jq_filter param to inspect values command in src/mixpanel_data/cli/commands/inspect.py
- [X] T042 [P] Add jq_filter param to inspect funnels command in src/mixpanel_data/cli/commands/inspect.py
- [X] T043 [P] Add jq_filter param to inspect cohorts command in src/mixpanel_data/cli/commands/inspect.py
- [X] T044 [P] Add jq_filter param to inspect top_events command in src/mixpanel_data/cli/commands/inspect.py
- [X] T045 [P] Add jq_filter param to inspect bookmarks command in src/mixpanel_data/cli/commands/inspect.py
- [X] T046 [P] Add jq_filter param to inspect lexicon_schemas command in src/mixpanel_data/cli/commands/inspect.py
- [X] T047 [P] Add jq_filter param to inspect lexicon_schema command in src/mixpanel_data/cli/commands/inspect.py
- [X] T048 [P] Add jq_filter param to inspect distribution command in src/mixpanel_data/cli/commands/inspect.py
- [X] T049 [P] Add jq_filter param to inspect numeric command in src/mixpanel_data/cli/commands/inspect.py
- [X] T050 [P] Add jq_filter param to inspect daily command in src/mixpanel_data/cli/commands/inspect.py
- [X] T051 [P] Add jq_filter param to inspect engagement command in src/mixpanel_data/cli/commands/inspect.py
- [X] T052 [P] Add jq_filter param to inspect coverage command in src/mixpanel_data/cli/commands/inspect.py
- [X] T053 [P] Add jq_filter param to inspect info command in src/mixpanel_data/cli/commands/inspect.py
- [X] T054 [P] Add jq_filter param to inspect tables command in src/mixpanel_data/cli/commands/inspect.py
- [X] T055 [P] Add jq_filter param to inspect schema command in src/mixpanel_data/cli/commands/inspect.py
- [X] T056 [P] Add jq_filter param to inspect sample command in src/mixpanel_data/cli/commands/inspect.py
- [X] T057 [P] Add jq_filter param to inspect summarize command in src/mixpanel_data/cli/commands/inspect.py
- [X] T058 [P] Add jq_filter param to inspect breakdown command in src/mixpanel_data/cli/commands/inspect.py
- [X] T059 [P] Add jq_filter param to inspect keys command in src/mixpanel_data/cli/commands/inspect.py
- [X] T060 [P] Add jq_filter param to inspect column command in src/mixpanel_data/cli/commands/inspect.py

### query.py Commands

- [X] T061 [P] Add jq_filter param to query sql command in src/mixpanel_data/cli/commands/query.py
- [X] T062 [P] Add jq_filter param to query segmentation command in src/mixpanel_data/cli/commands/query.py
- [X] T063 [P] Add jq_filter param to query funnel command in src/mixpanel_data/cli/commands/query.py
- [X] T064 [P] Add jq_filter param to query retention command in src/mixpanel_data/cli/commands/query.py
- [X] T065 [P] Add jq_filter param to query jql command in src/mixpanel_data/cli/commands/query.py

### fetch.py Commands

- [X] T066 [P] Add jq_filter param to fetch events command in src/mixpanel_data/cli/commands/fetch.py
- [X] T067 [P] Add jq_filter param to fetch profiles command in src/mixpanel_data/cli/commands/fetch.py

**Checkpoint**: All commands now support --jq option.

---

## Phase 9: Integration & Property-Based Tests

**Purpose**: Comprehensive testing across the feature

- [X] T068 [P] Create CLI integration test file tests/unit/cli/test_jq_integration.py
- [X] T069 [P] Integration test for inspect events with --jq in tests/unit/cli/test_jq_integration.py
- [X] T070 [P] Integration test for query sql with --jq in tests/unit/cli/test_jq_integration.py
- [X] T071 [P] Integration test for --jq with incompatible format in tests/unit/cli/test_jq_integration.py
- [X] T072 [P] Create property-based test file tests/unit/cli/test_jq_pbt.py
- [X] T073 [P] PBT: Identity filter '.' preserves structure in tests/unit/cli/test_jq_pbt.py
- [X] T074 [P] PBT: 'length' filter returns correct count in tests/unit/cli/test_jq_pbt.py
- [X] T075 [P] PBT: select filter never increases size in tests/unit/cli/test_jq_pbt.py

**Checkpoint**: All tests pass including property-based tests.

---

## Phase 10: Polish & Documentation

**Purpose**: Final polish and documentation updates

- [X] T076 [P] Update docstring examples for inspect commands with --jq in src/mixpanel_data/cli/commands/inspect.py
- [X] T077 [P] Update docstring examples for query commands with --jq in src/mixpanel_data/cli/commands/query.py
- [X] T078 Run `just check` to verify lint, typecheck, and all tests pass
- [X] T079 Verify test coverage remains ≥90% with `just test-cov`
- [X] T080 Run quickstart.md examples manually to validate (integration tests verify functionality)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - BLOCKS all user stories
- **User Stories (Phase 3-7)**: All depend on Foundational phase completion
  - US1 (P1) must complete first (core implementation)
  - US2, US3 (P2) can proceed after US1 (error handling builds on core)
  - US4, US5 (P3) can proceed after US2/US3 (refinements)
- **Command Updates (Phase 8)**: Depends on US1 completion (core filtering must work)
- **Integration Tests (Phase 9)**: Depends on Command Updates
- **Polish (Phase 10)**: Depends on all previous phases

### User Story Dependencies

- **US1 (P1)**: Can start after Foundational - No dependencies on other stories - THIS IS MVP
- **US2 (P2)**: Should start after US1 (error handling uses same function)
- **US3 (P2)**: Can run parallel with US2 (different code path in output_result)
- **US4 (P3)**: Should start after US2 (similar error handling pattern)
- **US5 (P3)**: Should start after US1 (uses same function, no error case)

### Within Each User Story

- Tests MUST be written and FAIL before implementation
- Implementation makes tests pass
- All tests verified before moving to next story

### Parallel Opportunities

**Phase 1-2**: Sequential (dependencies)

**Phase 3 (US1)**: Tests T006-T011 can run in parallel

**Phase 4-7 (US2-US5)**: Tests within each story can run in parallel

**Phase 8**: All command updates T039-T067 can run in parallel (different sections of same files, but independent edits)

**Phase 9**: All integration and PBT tests T068-T075 can run in parallel

**Phase 10**: T076-T077 can run in parallel

---

## Parallel Example: Phase 8 Command Updates

```bash
# All inspect command updates can run in parallel:
Task: "Add jq_filter param to inspect events command"
Task: "Add jq_filter param to inspect properties command"
Task: "Add jq_filter param to inspect values command"
# ... (all 22 inspect commands)

# All query command updates can run in parallel:
Task: "Add jq_filter param to query sql command"
Task: "Add jq_filter param to query segmentation command"
# ... (all 5 query commands)

# All fetch command updates can run in parallel:
Task: "Add jq_filter param to fetch events command"
Task: "Add jq_filter param to fetch profiles command"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (add jq dependency)
2. Complete Phase 2: Foundational (add type and param signatures)
3. Complete Phase 3: User Story 1 (core jq filtering)
4. **STOP and VALIDATE**: Test with `mp inspect events --format json --jq '.[0]'`
5. Feature is usable at this point!

### Incremental Delivery

1. MVP (Setup + Foundational + US1) → Core filtering works
2. Add US2 + US3 → Error handling complete
3. Add US4 + US5 → Edge cases handled
4. Add Phase 8 → All commands support --jq
5. Add Phase 9-10 → Full test coverage and documentation

### Recommended Order for Single Developer

1. T001-T002 (Setup)
2. T003-T005 (Foundational)
3. T006-T015 (US1 - MVP)
4. T016-T021 (US2) + T022-T028 (US3) - can interleave
5. T029-T038 (US4 + US5)
6. T039-T067 (Command updates - mechanical, can batch)
7. T068-T075 (Integration + PBT)
8. T076-T080 (Polish)

---

## Notes

- [P] tasks = different files or independent sections, no dependencies
- [Story] label maps task to specific user story for traceability
- Each user story is independently testable after completion
- Verify tests fail before implementing (TDD)
- Run `just check` frequently to catch issues early
- The _apply_jq_filter function handles US1, US2, US4, US5 (core + all error cases)
- The output_result function handles US3 (format validation)
- Command updates (Phase 8) are mechanical: add param, pass to output_result
