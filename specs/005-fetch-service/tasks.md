# Tasks: Fetch Service

**Input**: Design documents from `/specs/005-fetch-service/`
**Prerequisites**: plan.md (required), spec.md (required), research.md, data-model.md, contracts/

**Tests**: Included per project testing standards (pytest with mocked dependencies)

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2)
- Include exact file paths in descriptions

## Path Conventions

- **Project type**: Single Python package (`mixpanel_data`)
- **Source**: `src/mixpanel_data/`
- **Tests**: `tests/unit/`, `tests/integration/`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project already initialized; verify dependencies and structure

- [X] T001 Verify existing project structure matches plan in src/mixpanel_data/_internal/services/

**Note**: No additional setup required. Project structure from previous phases is already in place.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Create FetcherService class skeleton and helper functions that MUST be complete before user story implementation

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [X] T002 Create FetcherService class skeleton with constructor in src/mixpanel_data/_internal/services/fetcher.py
- [X] T003 [P] Implement _transform_event generator function in src/mixpanel_data/_internal/services/fetcher.py
- [X] T004 [P] Implement _transform_profile generator function in src/mixpanel_data/_internal/services/fetcher.py

**Checkpoint**: Foundation ready - FetcherService class exists with transformation helpers

---

## Phase 3: User Story 1 - Fetch Events into Local Database (Priority: P1) 🎯 MVP

**Goal**: Enable users to fetch a date range of events from Mixpanel into local DuckDB storage for SQL querying

**Independent Test**: Fetch events for a date range and verify they are queryable via `storage.execute_df("SELECT * FROM {table}")`

### Tests for User Story 1

- [X] T005 [P] [US1] Unit test for _transform_event with valid event data in tests/unit/test_fetcher_service.py
- [X] T006 [P] [US1] Unit test for _transform_event with missing $insert_id in tests/unit/test_fetcher_service.py
- [X] T007 [P] [US1] Unit test for fetch_events with mocked API client in tests/unit/test_fetcher_service.py
- [X] T008 [P] [US1] Unit test for fetch_events TableExistsError in tests/unit/test_fetcher_service.py
- [X] T009 [US1] Integration test for fetch_events with real DuckDB in tests/integration/test_fetch_service.py

### Implementation for User Story 1

- [X] T010 [US1] Implement fetch_events method in src/mixpanel_data/_internal/services/fetcher.py
- [X] T011 [US1] Add progress callback forwarding from API client on_batch in src/mixpanel_data/_internal/services/fetcher.py
- [X] T012 [US1] Add FetchResult construction with timing in src/mixpanel_data/_internal/services/fetcher.py
- [X] T013 [US1] Add TableMetadata construction with filter context in src/mixpanel_data/_internal/services/fetcher.py

**Checkpoint**: User Story 1 fully functional - events can be fetched and queried via SQL

---

## Phase 4: User Story 2 - Fetch User Profiles into Local Database (Priority: P2)

**Goal**: Enable users to fetch user profiles from Mixpanel into local DuckDB storage for joining with event data

**Independent Test**: Fetch profiles and verify they are queryable via `storage.execute_df("SELECT * FROM {table}")`

### Tests for User Story 2

- [X] T014 [P] [US2] Unit test for _transform_profile with valid profile data in tests/unit/test_fetcher_service.py
- [X] T015 [P] [US2] Unit test for _transform_profile with missing $last_seen in tests/unit/test_fetcher_service.py
- [X] T016 [P] [US2] Unit test for fetch_profiles with mocked API client in tests/unit/test_fetcher_service.py
- [X] T017 [P] [US2] Unit test for fetch_profiles TableExistsError in tests/unit/test_fetcher_service.py
- [X] T018 [US2] Integration test for fetch_profiles with real DuckDB in tests/integration/test_fetch_service.py

### Implementation for User Story 2

- [X] T019 [US2] Implement fetch_profiles method in src/mixpanel_data/_internal/services/fetcher.py
- [X] T020 [US2] Add progress callback forwarding from API client on_batch in src/mixpanel_data/_internal/services/fetcher.py
- [X] T021 [US2] Add FetchResult construction with date_range=None in src/mixpanel_data/_internal/services/fetcher.py

**Checkpoint**: User Story 2 fully functional - profiles can be fetched and queried via SQL

---

## Phase 5: Polish & Cross-Cutting Concerns

**Purpose**: Documentation, exports, and validation

- [X] T022 [P] Add comprehensive docstrings to FetcherService class and methods in src/mixpanel_data/_internal/services/fetcher.py
- [X] T023 [P] Export FetcherService from services __init__.py in src/mixpanel_data/_internal/services/__init__.py
- [X] T024 Run quickstart.md examples to validate implementation
- [X] T025 Run all tests and verify 100% pass rate with `just test`
- [X] T026 Run linting and type checking with `just check`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: Verify only - project already exists
- **Foundational (Phase 2)**: Create class skeleton and transformers - BLOCKS all user stories
- **User Story 1 (Phase 3)**: Depends on Foundational - implements fetch_events
- **User Story 2 (Phase 4)**: Depends on Foundational - implements fetch_profiles (can run parallel to US1)
- **Polish (Phase 5)**: Depends on all user stories being complete

### User Story Dependencies

- **User Story 1 (P1)**: Depends on Phase 2 (Foundational) - No dependencies on other stories
- **User Story 2 (P2)**: Depends on Phase 2 (Foundational) - Independent of US1

### Within Each User Story

- Tests written first (TDD approach)
- Core implementation before refinements
- Integration test validates end-to-end flow

### Parallel Opportunities

**Phase 2 (Foundational)**:
- T003 and T004 can run in parallel (different generator functions)

**Phase 3 (US1 Tests)**:
- T005, T006, T007, T008 can run in parallel (different test cases)

**Phase 4 (US2 Tests)**:
- T014, T015, T016, T017 can run in parallel (different test cases)

**Phase 5 (Polish)**:
- T022 and T023 can run in parallel (different files)

**Cross-Phase Parallelism**:
- After Phase 2 completes, US1 and US2 can be implemented in parallel

---

## Parallel Example: Phase 2 Foundational

```bash
# Launch transformation generators together:
Task: "Implement _transform_event generator function in src/mixpanel_data/_internal/services/fetcher.py"
Task: "Implement _transform_profile generator function in src/mixpanel_data/_internal/services/fetcher.py"
```

## Parallel Example: User Story 1 Tests

```bash
# Launch all unit tests together:
Task: "Unit test for _transform_event with valid event data in tests/unit/test_fetcher_service.py"
Task: "Unit test for _transform_event with missing $insert_id in tests/unit/test_fetcher_service.py"
Task: "Unit test for fetch_events with mocked API client in tests/unit/test_fetcher_service.py"
Task: "Unit test for fetch_events TableExistsError in tests/unit/test_fetcher_service.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (verify)
2. Complete Phase 2: Foundational (class + transformers)
3. Complete Phase 3: User Story 1 (fetch_events)
4. **STOP and VALIDATE**: Test fetch_events independently
5. Can deploy/demo with events-only functionality

### Incremental Delivery

1. Complete Setup + Foundational → Foundation ready
2. Add User Story 1 → Test independently → Events work (MVP!)
3. Add User Story 2 → Test independently → Profiles work
4. Polish → Documentation and exports complete

### Single Developer Strategy

Execute phases sequentially in priority order:
1. Phase 1 → Phase 2 → Phase 3 (US1) → Phase 4 (US2) → Phase 5

---

## Notes

- [P] tasks = different files or test cases, no dependencies
- [Story] label maps task to specific user story for traceability
- US3 (Explicit Table Management) is handled by StorageEngine's TableExistsError - no separate tasks needed
- US4 (Progress Monitoring) is built into fetch_events/fetch_profiles via progress_callback parameter
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
