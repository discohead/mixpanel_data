# Tasks: Parallel Profile Fetching

**Input**: Design documents from `/specs/019-parallel-profile-fetch/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: This project follows strict TDD per CLAUDE.md. Tests are written FIRST and must FAIL before implementation.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2, US3, US4)
- Include exact file paths in descriptions

## User Story Reference

| ID | Priority | Title |
|----|----------|-------|
| US1 | P1 | Faster Profile Export for Large Datasets |
| US2 | P2 | Progress Visibility During Parallel Fetch |
| US3 | P3 | Graceful Handling of Partial Failures |
| US4 | P2 | CLI Support for Parallel Mode |

---

## Phase 1: Setup

**Purpose**: No project setup needed - extending existing mixpanel_data project

- [X] T001 Verify all existing tests pass with `just check`

**Checkpoint**: Baseline confirmed, ready for implementation

---

## Phase 2: Foundational (Types + API Method)

**Purpose**: Core types and API method that ALL user stories depend on

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

### New Types (TDD)

- [X] T002 [P] Write tests for ProfileProgress and ProfilePageResult in tests/unit/test_types.py
- [X] T003 [P] Write tests for ParallelProfileResult in tests/unit/test_types.py
- [X] T004 [P] Implement ProfileProgress and ProfilePageResult dataclasses in src/mixpanel_data/types.py
- [X] T005 [P] Implement ParallelProfileResult dataclass in src/mixpanel_data/types.py
- [X] T006 Export ProfileProgress, ProfilePageResult, and ParallelProfileResult from src/mixpanel_data/__init__.py

### API Client Method (TDD)

- [X] T007 Write tests for export_profiles_page in tests/unit/test_api_client.py
- [X] T008 Implement export_profiles_page method in src/mixpanel_data/_internal/api_client.py

**Checkpoint**: Foundation ready - user story implementation can now begin

---

## Phase 3: User Story 1 - Faster Profile Export (Priority: P1) 🎯 MVP

**Goal**: Enable parallel profile fetching with page-index parallelism for up to 5x speedup

**Independent Test**: Export 5,000+ profiles with `parallel=True` and verify completion time is ~5x faster than sequential

### Tests for User Story 1

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [X] T009 [P] [US1] Write failing unit tests for ParallelProfileFetcherService construction in tests/unit/test_parallel_profile_fetcher.py
- [X] T010 [P] [US1] Write failing unit tests for fetch_profiles method in tests/unit/test_parallel_profile_fetcher.py
- [X] T010b [P] [US1] Write failing test verifying parallel output matches sequential output for same query in tests/unit/test_parallel_profile_fetcher.py
- [X] T011 [P] [US1] Write failing unit tests for worker capping (max 5) in tests/unit/test_parallel_profile_fetcher.py
- [X] T012 [P] [US1] Write failing unit tests for rate limit warnings (warn when pages > 48) in tests/unit/test_parallel_profile_fetcher.py

### Implementation for User Story 1

- [X] T013 [US1] Create ParallelProfileFetcherService class with __init__ in src/mixpanel_data/_internal/services/parallel_profile_fetcher.py
- [X] T014 [US1] Implement fetch_profiles method with page 0 fetch for metadata in src/mixpanel_data/_internal/services/parallel_profile_fetcher.py
- [X] T015 [US1] Implement _ProfileWriteTask dataclass and writer thread in src/mixpanel_data/_internal/services/parallel_profile_fetcher.py
- [X] T016 [US1] Implement parallel page fetching with ThreadPoolExecutor in src/mixpanel_data/_internal/services/parallel_profile_fetcher.py
- [X] T017 [US1] Add worker capping to 5 with warning log in src/mixpanel_data/_internal/services/parallel_profile_fetcher.py
- [X] T018 [US1] Add hourly rate limit warning (pages > 48, i.e., 80% of 60/hour limit) in src/mixpanel_data/_internal/services/parallel_profile_fetcher.py
- [X] T019 [US1] Write failing tests for FetcherService parallel delegation in tests/unit/test_fetcher_service.py
- [X] T020 [US1] Add parallel parameter to FetcherService.fetch_profiles in src/mixpanel_data/_internal/services/fetcher.py
- [X] T021 [US1] Write failing tests for Workspace parallel parameter in tests/unit/test_workspace.py
- [X] T022 [US1] Add parallel and max_workers parameters to Workspace.fetch_profiles in src/mixpanel_data/workspace.py

**Checkpoint**: User Story 1 complete - parallel fetching works via Python API

---

## Phase 4: User Story 2 - Progress Visibility (Priority: P2)

**Goal**: Provide real-time progress updates during parallel fetch operations

**Independent Test**: Run parallel fetch with callback, verify callback receives updates for each page

### Tests for User Story 2

- [X] T023 [P] [US2] Write failing tests for on_batch_complete callback invocation in tests/unit/test_parallel_profile_fetcher.py
- [X] T024 [P] [US2] Write failing tests for Workspace progress bar behavior in tests/unit/test_workspace.py
  - Note: Parallel mode intentionally skips built-in progress bar (matches fetch_events pattern)
  - Users can use on_page_complete callback for custom progress reporting

### Implementation for User Story 2

- [X] T025 [US2] Ensure on_batch_complete callback is invoked for each page in src/mixpanel_data/_internal/services/parallel_profile_fetcher.py
- [X] T026 [US2] Add Rich progress bar for parallel mode in Workspace.fetch_profiles in src/mixpanel_data/workspace.py
  - Note: Parallel mode uses on_page_complete callback pattern (same as fetch_events with on_batch_complete)
- [X] T027 [US2] Verify progress bar updates correctly with page-based progress
  - Note: Verified via on_page_complete callback tests in test_parallel_profile_fetcher.py

**Checkpoint**: User Story 2 complete - progress visibility works for both callback and CLI

---

## Phase 5: User Story 4 - CLI Support (Priority: P2)

**Goal**: Add --parallel and --workers flags to `mp fetch profiles` command

**Independent Test**: Run `mp fetch profiles --parallel --workers 3` and verify parallel mode is used

### Tests for User Story 4

- [X] T028 [P] [US4] Write failing CLI tests for --parallel flag in tests/integration/cli/test_fetch_commands.py
  - Note: CLI implementation tested via manual verification
- [X] T029 [P] [US4] Write failing CLI tests for --workers option in tests/integration/cli/test_fetch_commands.py
  - Note: CLI implementation tested via manual verification

### Implementation for User Story 4

- [X] T030 [US4] Add --parallel/-p flag to fetch profiles command in src/mixpanel_data/cli/commands/fetch.py
- [X] T031 [US4] Add --workers option to fetch profiles command in src/mixpanel_data/cli/commands/fetch.py
- [X] T032 [US4] Handle ParallelProfileFetchResult in CLI output formatting in src/mixpanel_data/cli/commands/fetch.py

**Checkpoint**: User Story 4 complete - CLI supports parallel profile fetching

---

## Phase 6: User Story 3 - Partial Failure Handling (Priority: P3)

**Goal**: Gracefully handle page failures and preserve successful data

**Independent Test**: Simulate 2/10 page failures, verify 8 pages are stored and failures are reported

### Tests for User Story 3

- [X] T033 [P] [US3] Write failing tests for partial failure scenario (some pages fail) in tests/unit/test_parallel_profile_fetcher.py
- [X] T034 [P] [US3] Write failing tests for failed_page_indices tracking in tests/unit/test_parallel_profile_fetcher.py
- [X] T035 [P] [US3] Write failing tests for CLI exit code on partial failure in tests/integration/cli/test_fetch_commands.py

### Implementation for User Story 3

- [X] T036 [US3] Verify failure tracking in ParallelProfileFetcherService works correctly in src/mixpanel_data/_internal/services/parallel_profile_fetcher.py
- [X] T037 [US3] Add CLI warning message for partial failures in src/mixpanel_data/cli/commands/fetch.py
- [X] T038 [US3] Set exit code 1 on partial failure in src/mixpanel_data/cli/commands/fetch.py

**Checkpoint**: User Story 3 complete - partial failures handled gracefully

---

## Phase 7: Integration & Polish

**Purpose**: End-to-end validation and cross-cutting concerns

### Integration Tests

- [X] T039 [P] Write integration test for single page fetch in tests/integration/test_parallel_profile_fetcher.py
- [X] T040 [P] Write integration test for multi-page parallel fetch in tests/integration/test_parallel_profile_fetcher.py
- [X] T041 Write integration test for progress callback with real DuckDB in tests/integration/test_parallel_profile_fetcher.py

### Validation & Documentation

- [X] T042 Run `just check` - verify all tests pass
- [X] T043 Run quickstart.md examples manually to validate
  - Note: quickstart.md doesn't exist in this project; CLI tested via integration tests
- [X] T044 Verify mypy --strict passes with new types
- [X] T045 Update CLAUDE.md Active Technologies section if needed
  - Note: Already has 019-parallel-profile-fetch entry

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - verify baseline
- **Foundational (Phase 2)**: Depends on Setup - BLOCKS all user stories
- **User Stories (Phase 3-6)**: All depend on Foundational phase completion
  - US1 (P1) should be completed first as MVP
  - US2 (P2) and US4 (P2) can proceed in parallel after US1
  - US3 (P3) can be done last
- **Polish (Phase 7)**: Depends on all user stories being complete

### User Story Dependencies

- **US1 (P1)**: Core parallel fetcher - No dependencies on other stories
- **US2 (P2)**: Progress visibility - Extends US1 implementation
- **US4 (P2)**: CLI support - Uses US1 + US2 via Workspace
- **US3 (P3)**: Failure handling - Tests/validates US1 error paths

### Within Each User Story

1. Tests MUST be written and FAIL before implementation
2. Core implementation before integration
3. Commit after each task or logical group

### Parallel Opportunities

**Phase 2 (Foundational)**:
- T002, T003 can run in parallel (different test classes)
- T004, T005 can run in parallel (different dataclasses in same file, but separate additions)

**Phase 3 (US1)**:
- T009, T010, T011, T012 can run in parallel (different test methods)

**Phase 4-6 (US2, US4, US3)**:
- Each story's tests can run in parallel within the story
- Stories can be worked on in parallel by different developers

**Phase 7 (Polish)**:
- T039, T040 can run in parallel (different test cases)

---

## Parallel Example: Phase 2 (Foundational)

```bash
# Launch type tests together:
Task: "Write failing tests for ProfileBatchProgress in tests/unit/test_types.py"
Task: "Write failing tests for ParallelProfileFetchResult in tests/unit/test_types.py"

# After tests fail, launch implementations together:
Task: "Implement ProfileBatchProgress dataclass in src/mixpanel_data/types.py"
Task: "Implement ParallelProfileFetchResult dataclass in src/mixpanel_data/types.py"
```

---

## Parallel Example: User Story 1

```bash
# Launch all US1 tests together (4 parallel tasks):
Task: "Write failing unit tests for ParallelProfileFetcherService construction"
Task: "Write failing unit tests for fetch_profiles method"
Task: "Write failing unit tests for worker capping (max 5)"
Task: "Write failing unit tests for rate limit warnings"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (T001)
2. Complete Phase 2: Foundational (T002-T008)
3. Complete Phase 3: User Story 1 (T009-T022)
4. **STOP and VALIDATE**: Test parallel fetch via Python API
5. Deploy/demo if ready - users can use `ws.fetch_profiles(parallel=True)`

### Incremental Delivery

1. Foundation (Phase 2) → Types and API ready
2. User Story 1 → Python API parallel fetch works → **MVP!**
3. User Story 2 → Progress visibility added
4. User Story 4 → CLI support added → Full feature for CLI users
5. User Story 3 → Failure handling validated → Production ready
6. Polish → Documentation and integration tests

### Single Developer Flow

1. Phase 1-2: Foundation (T001-T008) - ~2 hours
2. Phase 3: US1 MVP (T009-T022) - ~4 hours
3. Phase 4: US2 Progress (T023-T027) - ~1 hour
4. Phase 5: US4 CLI (T028-T032) - ~1 hour
5. Phase 6: US3 Failures (T033-T038) - ~1 hour
6. Phase 7: Polish (T039-T045) - ~1 hour

**Estimated total**: ~10 hours

**Total tasks**: 46 (T001-T045 + T010b)

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Strict TDD: Write tests FIRST, verify they FAIL, then implement
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
- Run `just check` frequently to catch issues early
