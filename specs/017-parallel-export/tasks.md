# Tasks: Parallel Export Performance

**Input**: Design documents from `/specs/017-parallel-export/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md

**TDD Approach**: This project follows strict TDD per CLAUDE.md. Tests are written FIRST, must FAIL before implementation.

**Organization**: Tasks grouped by user story for independent implementation and testing.

## Format: `[ID] [P?] [Story?] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2, US3, US4)
- Paths use existing project structure in `src/mixpanel_data/` and `tests/`

---

## Phase 1: Setup

**Purpose**: No setup needed - project already exists with established patterns

*Skip to Phase 2*

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core types and utilities that MUST be complete before ANY user story

**⚠️ CRITICAL**: All user stories depend on these foundational components

### Tests First (TDD)

- [X] T001 [P] Create unit tests for BatchProgress, BatchResult, ParallelFetchResult types in tests/unit/test_types_parallel.py
- [X] T002 [P] Create unit tests for RateLimiter in tests/unit/test_rate_limiter.py
- [X] T003 [P] Create unit tests for split_date_range in tests/unit/test_date_utils.py
- [X] T004 [P] Create property-based tests for split_date_range in tests/unit/test_date_utils_pbt.py

### Implementation

- [X] T005 [P] Implement BatchProgress dataclass in src/mixpanel_data/types.py
- [X] T006 [P] Implement BatchResult dataclass in src/mixpanel_data/types.py
- [X] T007 [P] Implement ParallelFetchResult dataclass with has_failures property in src/mixpanel_data/types.py
- [X] T008 [P] Export new types from src/mixpanel_data/__init__.py
- [X] T009 Implement RateLimiter class with semaphore in src/mixpanel_data/_internal/rate_limiter.py
- [X] T010 Implement split_date_range function in src/mixpanel_data/_internal/date_utils.py
- [X] T011 Run `just check` to verify all foundational tests pass and types are correct

**Checkpoint**: Foundation ready - all tests pass, types exported, date utilities working

---

## Phase 3: User Story 1 - Faster Large Date Range Exports (Priority: P1) 🎯 MVP

**Goal**: Enable parallel fetching for events with 7-day chunks, delivering up to 10x speedup

**Independent Test**: Export 30+ day range with `parallel=True`, verify all data retrieved correctly and faster than sequential

### Tests First (TDD)

- [X] T012 [P] [US1] Create unit tests for ParallelFetcherService in tests/unit/test_parallel_fetcher.py
- [X] T013 [P] [US1] Create integration tests for parallel fetcher with mocked API in tests/integration/test_parallel_fetcher.py
- [X] T014 [P] [US1] Add parallel delegation tests to tests/unit/test_fetcher_service.py
- [X] T015 [P] [US1] Add parallel parameter tests to tests/unit/test_workspace.py

### Implementation

- [X] T016 [US1] Implement ParallelFetcherService with ThreadPoolExecutor and producer-consumer queue in src/mixpanel_data/_internal/services/parallel_fetcher.py
- [X] T017 [US1] Add parallel, max_workers, on_batch_complete parameters to FetcherService.fetch_events in src/mixpanel_data/_internal/services/fetcher.py
- [X] T018 [US1] Implement delegation to ParallelFetcherService when parallel=True in src/mixpanel_data/_internal/services/fetcher.py
- [X] T019 [US1] Add parallel, max_workers, on_batch_complete parameters to Workspace.fetch_events in src/mixpanel_data/workspace.py
- [X] T020 [US1] Update return type annotation to FetchResult | ParallelFetchResult in src/mixpanel_data/workspace.py
- [X] T021 [US1] Run `just check` to verify US1 tests pass

**Checkpoint**: Parallel fetching works via library API. Can export 30+ days faster with `parallel=True`

---

## Phase 4: User Story 2 - Progress Visibility (Priority: P2)

**Goal**: Show batch completion progress during parallel exports

**Independent Test**: Run parallel export, verify on_batch_complete callback receives accurate BatchProgress objects

### Tests First (TDD)

- [X] T022 [P] [US2] Add CLI progress display tests to tests/cli/test_fetch_commands.py

### Implementation

- [X] T023 [US2] Add --parallel / -p flag to mp fetch events in src/mixpanel_data/cli/commands/fetch.py
- [X] T024 [US2] Implement batch progress display callback for CLI in src/mixpanel_data/cli/commands/fetch.py
- [X] T025 [US2] Display batch completion status to stderr during parallel export in src/mixpanel_data/cli/commands/fetch.py
- [X] T026 [US2] Run `just check` to verify US2 tests pass

**Checkpoint**: CLI shows progress during parallel exports with batch completion messages

---

## Phase 5: User Story 3 - Handling Partial Failures (Priority: P2)

**Goal**: Continue exporting on batch failures, report failed date ranges for retry

**Independent Test**: Simulate network failure for one batch, verify other batches complete and failures are reported

### Tests First (TDD)

- [X] T027 [P] [US3] Add partial failure tests to tests/unit/test_parallel_fetcher.py
- [X] T028 [P] [US3] Add CLI failure output tests to tests/cli/test_fetch_commands.py

### Implementation

- [X] T029 [US3] Ensure ParallelFetcherService continues on batch failure in src/mixpanel_data/_internal/services/parallel_fetcher.py
- [X] T030 [US3] Ensure failed_date_ranges is populated correctly in ParallelFetchResult in src/mixpanel_data/_internal/services/parallel_fetcher.py
- [X] T031 [US3] Display failure summary and failed date ranges in CLI output in src/mixpanel_data/cli/commands/fetch.py
- [X] T032 [US3] Set exit code to 1 when has_failures is True in src/mixpanel_data/cli/commands/fetch.py
- [X] T033 [US3] Run `just check` to verify US3 tests pass

**Checkpoint**: Partial failures are handled gracefully, failed ranges reported for retry

---

## Phase 6: User Story 4 - Configurable Concurrency (Priority: P3)

**Goal**: Allow users to configure number of concurrent workers

**Independent Test**: Run export with --workers 5, verify concurrency is limited to 5

### Tests First (TDD)

- [X] T034 [P] [US4] Add max_workers configuration tests to tests/unit/test_parallel_fetcher.py
- [X] T035 [P] [US4] Add --workers CLI option tests to tests/cli/test_fetch_commands.py

### Implementation

- [X] T036 [US4] Add --workers N option to mp fetch events in src/mixpanel_data/cli/commands/fetch.py
- [X] T037 [US4] Validate workers is positive integer in src/mixpanel_data/cli/commands/fetch.py
- [X] T038 [US4] Pass workers value through to Workspace.fetch_events in src/mixpanel_data/cli/commands/fetch.py
- [X] T039 [US4] Run `just check` to verify US4 tests pass

**Checkpoint**: Users can configure concurrency with --workers flag

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Final cleanup, coverage validation, mutation testing

- [X] T040 [P] Add docstrings to all new public functions and classes
- [X] T041 Run `just test-cov` to verify 90%+ coverage on new code
- [X] T042 Run `just mutate` to verify mutation testing score
- [X] T043 Run `just typecheck` to verify mypy --strict passes
- [X] T044 Validate quickstart.md examples work correctly
- [X] T045 Final `just check` to verify all quality gates pass

---

## Dependencies & Execution Order

### Phase Dependencies

```
Phase 1 (Setup)
    ↓
Phase 2 (Foundational) ← BLOCKS all user stories
    ↓
┌───┴───┬───────┬───────┐
↓       ↓       ↓       ↓
US1     US2*    US3*    US4*
(P1)    (P2)    (P2)    (P3)
        ↓       ↓       ↓
        [Depend on US1 for parallel infrastructure]
    ↓
Phase 7 (Polish)
```

*Note: US2, US3, US4 can run after US1 core is complete, but share the parallel infrastructure

### User Story Dependencies

| Story | Depends On | Can Start After |
|-------|------------|-----------------|
| US1 | Foundational (Phase 2) | Phase 2 complete |
| US2 | US1 (parallel infrastructure) | T016-T018 complete |
| US3 | US1 (parallel infrastructure) | T016-T018 complete |
| US4 | US1 (parallel infrastructure) | T016-T018 complete |

### Within Each User Story

1. Tests written FIRST, verified to FAIL
2. Implementation until tests PASS
3. `just check` before moving to next story

### Parallel Opportunities

**Phase 2 (Foundational)**:
- T001, T002, T003, T004 (tests) can run in parallel
- T005, T006, T007, T008 (types) can run in parallel

**US1**:
- T012, T013, T014, T015 (tests) can run in parallel

**After US1 core complete (T016-T018)**:
- US2, US3, US4 can be worked on in parallel

---

## Parallel Example: Foundational Phase

```bash
# Launch all foundational tests together:
Task: "Create unit tests for BatchProgress, BatchResult, ParallelFetchResult types in tests/unit/test_types_parallel.py"
Task: "Create unit tests for RateLimiter in tests/unit/test_rate_limiter.py"
Task: "Create unit tests for split_date_range in tests/unit/test_date_utils.py"
Task: "Create property-based tests for split_date_range in tests/unit/test_date_utils_pbt.py"

# Launch all type implementations together:
Task: "Implement BatchProgress dataclass in src/mixpanel_data/types.py"
Task: "Implement BatchResult dataclass in src/mixpanel_data/types.py"
Task: "Implement ParallelFetchResult dataclass in src/mixpanel_data/types.py"
```

---

## Implementation Strategy

### MVP First (US1 Only)

1. Complete Phase 2: Foundational
2. Complete Phase 3: User Story 1
3. **STOP and VALIDATE**: Test parallel export via library API
4. Deploy if ready - users get 10x faster exports

### Incremental Delivery

1. Foundational → Types and utilities ready
2. US1 → Core parallel fetching (MVP!)
3. US2 → CLI progress display
4. US3 → Partial failure handling
5. US4 → Configurable concurrency
6. Polish → Coverage, mutation testing, docs

### Suggested MVP Scope

**MVP = Phase 2 + US1 (Tasks T001-T021)**

This delivers:
- ✅ Parallel fetching via library API
- ✅ Up to 10x faster exports
- ✅ Full data correctness
- ✅ Backward compatibility

CLI features (US2-US4) can be added incrementally.

---

## Notes

- [P] tasks can run in parallel (different files)
- [Story] label maps task to user story
- TDD: Tests written FIRST, must FAIL before implementation
- Each story independently testable
- Commit after each task or logical group
- Run `just check` at each checkpoint
