# Tasks: Live Query Service

**Input**: Design documents from `/specs/006-live-query-service/`
**Prerequisites**: plan.md (required), spec.md (required for user stories), research.md, data-model.md

**Tests**: Required per constitution (Quality Gates: "Tests MUST exist for new functionality")

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each query type.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3, US4)
- Include exact file paths in descriptions

---

## Phase 1: Setup

**Purpose**: Create the LiveQueryService module file and test file structure

- [X] T001 Create LiveQueryService module file at src/mixpanel_data/_internal/services/live_query.py with module docstring and imports
- [X] T002 [P] Create test module file at tests/unit/test_live_query.py with module docstring and imports
- [X] T003 [P] Add live_query_factory fixture to tests/unit/test_live_query.py following discovery_factory pattern from tests/unit/test_discovery.py

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Create the LiveQueryService class skeleton that all query methods will be added to

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [X] T004 Implement LiveQueryService class with __init__ accepting MixpanelAPIClient in src/mixpanel_data/_internal/services/live_query.py
- [X] T005 Add LiveQueryService export to src/mixpanel_data/_internal/services/__init__.py
- [X] T006 [P] Add TestLiveQueryService class with test_init_with_api_client test in tests/unit/test_live_query.py

**Checkpoint**: LiveQueryService class exists and can be imported. Tests pass with `just test tests/unit/test_live_query.py`

---

## Phase 3: User Story 1 - Run Segmentation Queries (Priority: P1) 🎯 MVP

**Goal**: Execute segmentation queries and return structured SegmentationResult with time-series data

**Independent Test**: Run a segmentation query for an event and verify the result contains correct time-series data organized by date and segment

### Tests for User Story 1

- [X] T007 [P] [US1] Add TestSegmentation class with test_segmentation_basic_query test in tests/unit/test_live_query.py
- [X] T008 [P] [US1] Add test_segmentation_with_property_segmentation test to TestSegmentation in tests/unit/test_live_query.py
- [X] T009 [P] [US1] Add test_segmentation_with_where_filter test to TestSegmentation in tests/unit/test_live_query.py
- [X] T010 [P] [US1] Add test_segmentation_calculates_total test to TestSegmentation in tests/unit/test_live_query.py
- [X] T011 [P] [US1] Add test_segmentation_empty_result test to TestSegmentation in tests/unit/test_live_query.py
- [X] T012 [P] [US1] Add test_segmentation_propagates_auth_error test to TestSegmentation in tests/unit/test_live_query.py

### Implementation for User Story 1

- [X] T013 [US1] Implement _transform_segmentation helper function in src/mixpanel_data/_internal/services/live_query.py per research.md
- [X] T014 [US1] Implement segmentation() method in LiveQueryService in src/mixpanel_data/_internal/services/live_query.py
- [X] T015 [US1] Add type hints and docstring to segmentation() method per constitution requirements

**Checkpoint**: Segmentation queries work. Tests pass: `just test tests/unit/test_live_query.py::TestSegmentation`

---

## Phase 4: User Story 2 - Run Funnel Analysis (Priority: P1)

**Goal**: Execute funnel queries and return structured FunnelResult with step-by-step conversion data

**Independent Test**: Query a funnel by ID and verify the result contains steps with correct counts and conversion rates

### Tests for User Story 2

- [X] T016 [P] [US2] Add TestFunnel class with test_funnel_basic_query test in tests/unit/test_live_query.py
- [X] T017 [P] [US2] Add test_funnel_aggregates_across_dates test to TestFunnel in tests/unit/test_live_query.py
- [X] T018 [P] [US2] Add test_funnel_calculates_conversion_rates test to TestFunnel in tests/unit/test_live_query.py
- [X] T019 [P] [US2] Add test_funnel_overall_conversion_rate test to TestFunnel in tests/unit/test_live_query.py
- [X] T020 [P] [US2] Add test_funnel_empty_result test to TestFunnel in tests/unit/test_live_query.py
- [X] T021 [P] [US2] Add test_funnel_propagates_query_error test to TestFunnel in tests/unit/test_live_query.py

### Implementation for User Story 2

- [X] T022 [US2] Implement _transform_funnel helper function in src/mixpanel_data/_internal/services/live_query.py per research.md
- [X] T023 [US2] Implement funnel() method in LiveQueryService in src/mixpanel_data/_internal/services/live_query.py
- [X] T024 [US2] Add type hints and docstring to funnel() method per constitution requirements

**Checkpoint**: Funnel queries work. Tests pass: `just test tests/unit/test_live_query.py::TestFunnel`

---

## Phase 5: User Story 3 - Run Retention Analysis (Priority: P2)

**Goal**: Execute retention queries and return structured RetentionResult with cohort retention percentages

**Independent Test**: Run a retention query with born/return events and verify cohort data with correct retention percentages

### Tests for User Story 3

- [X] T025 [P] [US3] Add TestRetention class with test_retention_basic_query test in tests/unit/test_live_query.py
- [X] T026 [P] [US3] Add test_retention_calculates_percentages test to TestRetention in tests/unit/test_live_query.py
- [X] T027 [P] [US3] Add test_retention_with_filters test to TestRetention in tests/unit/test_live_query.py
- [X] T028 [P] [US3] Add test_retention_custom_intervals test to TestRetention in tests/unit/test_live_query.py
- [X] T029 [P] [US3] Add test_retention_empty_result test to TestRetention in tests/unit/test_live_query.py
- [X] T030 [P] [US3] Add test_retention_sorts_cohorts_by_date test to TestRetention in tests/unit/test_live_query.py

### Implementation for User Story 3

- [X] T031 [US3] Implement _transform_retention helper function in src/mixpanel_data/_internal/services/live_query.py per research.md
- [X] T032 [US3] Implement retention() method in LiveQueryService in src/mixpanel_data/_internal/services/live_query.py
- [X] T033 [US3] Add type hints and docstring to retention() method per constitution requirements

**Checkpoint**: Retention queries work. Tests pass: `just test tests/unit/test_live_query.py::TestRetention`

---

## Phase 6: User Story 4 - Run Custom JQL Queries (Priority: P3)

**Goal**: Execute arbitrary JQL scripts and return JQLResult with raw data

**Independent Test**: Execute a JQL script and verify the result contains the script output

### Tests for User Story 4

- [X] T034 [P] [US4] Add TestJQL class with test_jql_basic_query test in tests/unit/test_live_query.py
- [X] T035 [P] [US4] Add test_jql_with_params test to TestJQL in tests/unit/test_live_query.py
- [X] T036 [P] [US4] Add test_jql_empty_result test to TestJQL in tests/unit/test_live_query.py
- [X] T037 [P] [US4] Add test_jql_propagates_script_error test to TestJQL in tests/unit/test_live_query.py

### Implementation for User Story 4

- [X] T038 [US4] Implement jql() method in LiveQueryService in src/mixpanel_data/_internal/services/live_query.py
- [X] T039 [US4] Add type hints and docstring to jql() method per constitution requirements

**Checkpoint**: JQL queries work. Tests pass: `just test tests/unit/test_live_query.py::TestJQL`

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Final validation and quality checks

- [X] T040 Run full test suite with `just test` and verify all tests pass
- [X] T041 Run type checker with `just typecheck` and fix any errors
- [X] T042 Run linter with `just lint` and fix any issues
- [X] T043 Validate quickstart.md examples work by running sample code
- [X] T044 Update CLAUDE.md "What's Implemented" section to include LiveQueryService

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - BLOCKS all user stories
- **User Stories (Phase 3-6)**: All depend on Foundational phase completion
  - US1 and US2 are both P1 priority - can proceed in parallel
  - US3 (P2) can start after Foundational or after US1/US2
  - US4 (P3) can start after Foundational or after other stories
- **Polish (Phase 7)**: Depends on all user stories being complete

### User Story Dependencies

- **User Story 1 (Segmentation, P1)**: Can start after Foundational - No dependencies on other stories
- **User Story 2 (Funnel, P1)**: Can start after Foundational - No dependencies on other stories
- **User Story 3 (Retention, P2)**: Can start after Foundational - No dependencies on other stories
- **User Story 4 (JQL, P3)**: Can start after Foundational - No dependencies on other stories

### Within Each User Story

- Tests MUST be written and FAIL before implementation
- Helper function (_transform_*) before service method
- Service method complete before moving to next story

### Parallel Opportunities

**Phase 1 (Setup)**:
- T002 and T003 can run in parallel with T001

**Phase 2 (Foundational)**:
- T006 can run in parallel with T004/T005

**User Story Phases**:
- All test tasks within a story can run in parallel
- After Foundational, US1 and US2 can start in parallel (both P1)
- US3 and US4 can also run in parallel with US1/US2

---

## Parallel Example: User Story 1

```bash
# Launch all tests for User Story 1 together:
Task: "Add TestSegmentation class with test_segmentation_basic_query test"
Task: "Add test_segmentation_with_property_segmentation test"
Task: "Add test_segmentation_with_where_filter test"
Task: "Add test_segmentation_calculates_total test"
Task: "Add test_segmentation_empty_result test"
Task: "Add test_segmentation_propagates_auth_error test"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (T001-T003)
2. Complete Phase 2: Foundational (T004-T006)
3. Complete Phase 3: User Story 1 - Segmentation (T007-T015)
4. **STOP and VALIDATE**: Run `just test tests/unit/test_live_query.py::TestSegmentation`
5. Segmentation queries are functional - MVP delivered

### Incremental Delivery

1. Setup + Foundational → LiveQueryService class exists
2. Add US1 (Segmentation) → Test → Segmentation works (MVP!)
3. Add US2 (Funnel) → Test → Funnels work
4. Add US3 (Retention) → Test → Retention works
5. Add US4 (JQL) → Test → JQL works
6. Polish → Full feature complete

### Parallel Team Strategy

With two developers after Foundational:
- Developer A: US1 (Segmentation) + US3 (Retention)
- Developer B: US2 (Funnel) + US4 (JQL)

---

## Notes

- All result types (`SegmentationResult`, `FunnelResult`, etc.) already exist in `src/mixpanel_data/types.py`
- Follow the pattern established by `DiscoveryService` in `src/mixpanel_data/_internal/services/discovery.py`
- Use `mock_client_factory` fixture from `tests/conftest.py` for test setup
- Transformation logic is documented in `research.md`
- No caching - each query hits the API (per research.md decision)
