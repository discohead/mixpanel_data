# Tasks: Discovery & Query API Enhancements

**Input**: Design documents from `/specs/007-discovery-enhancements/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: Included per constitution requirement (quality gate: "Tests MUST exist for new functionality")

**Organization**: Tasks grouped by user story for independent implementation and testing

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2, US3, US4, US5)
- Exact file paths included in descriptions

---

## Phase 1: Setup

**Purpose**: No new setup needed — extending existing project structure

> This feature extends an existing codebase. All infrastructure (pytest, httpx, pandas) already exists.

- [x] T001 Review existing patterns in src/mixpanel_data/types.py for frozen dataclass conventions
- [x] T002 Review existing patterns in src/mixpanel_data/_internal/api_client.py for HTTP method conventions
- [x] T003 Review existing patterns in src/mixpanel_data/_internal/services/discovery.py for caching conventions

**Checkpoint**: Ready to begin user story implementation

---

## Phase 2: Foundational

**Purpose**: Shared infrastructure changes that enable all user stories

**⚠️ CRITICAL**: Complete before starting any user story

- [x] T004 Broaden cache type annotation in src/mixpanel_data/_internal/services/discovery.py from `list[str]` to `list[Any]` to support structured result types

**Checkpoint**: Foundation ready — user story implementation can now begin

---

## Phase 3: User Story 1 - Discover Available Funnels (Priority: P1) 🎯 MVP

**Goal**: Enable users to list all saved funnels in a project to identify funnel IDs for subsequent queries

**Independent Test**: Request list of funnels → verify response contains funnel_id and name for each funnel, sorted alphabetically

### Tests for User Story 1

- [x] T005 [P] [US1] Unit test for FunnelInfo type in tests/unit/test_types.py
- [x] T006 [P] [US1] Unit test for api_client.list_funnels() in tests/unit/test_api_client.py
- [x] T007 [P] [US1] Unit test for discovery.list_funnels() with caching in tests/unit/test_discovery.py

### Implementation for User Story 1

- [x] T008 [P] [US1] Add FunnelInfo frozen dataclass with to_dict() method in src/mixpanel_data/types.py
- [x] T009 [US1] Add list_funnels() API method (GET /funnels/list) in src/mixpanel_data/_internal/api_client.py
- [x] T010 [US1] Add list_funnels() service method with caching in src/mixpanel_data/_internal/services/discovery.py
- [x] T011 [US1] Export FunnelInfo from src/mixpanel_data/__init__.py

**Checkpoint**: User Story 1 complete — can list funnels independently

---

## Phase 4: User Story 2 - Discover Available Cohorts (Priority: P1)

**Goal**: Enable users to list all saved cohorts to identify cohort IDs for profile filtering

**Independent Test**: Request list of cohorts → verify response contains id, name, count, description, created, is_visible for each cohort, sorted alphabetically

### Tests for User Story 2

- [x] T012 [P] [US2] Unit test for SavedCohort type in tests/unit/test_types.py
- [x] T013 [P] [US2] Unit test for api_client.list_cohorts() (POST method) in tests/unit/test_api_client.py
- [x] T014 [P] [US2] Unit test for discovery.list_cohorts() with caching in tests/unit/test_discovery.py

### Implementation for User Story 2

- [x] T015 [P] [US2] Add SavedCohort frozen dataclass with to_dict() method in src/mixpanel_data/types.py
- [x] T016 [US2] Add list_cohorts() API method (POST /cohorts/list) in src/mixpanel_data/_internal/api_client.py
- [x] T017 [US2] Add list_cohorts() service method with caching and is_visible bool conversion in src/mixpanel_data/_internal/services/discovery.py
- [x] T018 [US2] Export SavedCohort from src/mixpanel_data/__init__.py

**Checkpoint**: User Stories 1 AND 2 complete — full P1 discovery capabilities available

---

## Phase 5: User Story 3 - Explore Today's Top Events (Priority: P2)

**Goal**: Enable users to see today's most active events with counts and trends for real-time activity awareness

**Independent Test**: Request top events → verify response contains event, count, percent_change; verify NOT cached

### Tests for User Story 3

- [x] T019 [P] [US3] Unit test for TopEvent type in tests/unit/test_types.py
- [x] T020 [P] [US3] Unit test for api_client.get_top_events() with type/limit params in tests/unit/test_api_client.py
- [x] T021 [P] [US3] Unit test for discovery.list_top_events() verifying no caching in tests/unit/test_discovery.py

### Implementation for User Story 3

- [x] T022 [P] [US3] Add TopEvent frozen dataclass with to_dict() method in src/mixpanel_data/types.py
- [x] T023 [US3] Add get_top_events() API method (GET /events/top) with type, limit params in src/mixpanel_data/_internal/api_client.py
- [x] T024 [US3] Add list_top_events() service method (no caching, amount→count mapping) in src/mixpanel_data/_internal/services/discovery.py
- [x] T025 [US3] Export TopEvent from src/mixpanel_data/__init__.py

**Checkpoint**: User Story 3 complete — all discovery capabilities available

---

## Phase 6: User Story 4 - Analyze Multi-Event Time Series (Priority: P2)

**Goal**: Enable users to query aggregate counts for multiple events over time for trend comparison

**Independent Test**: Request counts for multiple events with date range → verify series contains {event: {date: count}}, verify DataFrame conversion works

### Tests for User Story 4

- [x] T026 [P] [US4] Unit test for EventCountsResult type with lazy .df property in tests/unit/test_types.py
- [x] T027 [P] [US4] Unit test for api_client.event_counts() with events, dates, type, unit params in tests/unit/test_api_client.py
- [x] T028 [P] [US4] Unit test for live_query.event_counts() transformation in tests/unit/test_live_query.py

### Implementation for User Story 4

- [x] T029 [P] [US4] Add EventCountsResult frozen dataclass with to_dict() and lazy .df property in src/mixpanel_data/types.py
- [x] T030 [US4] Add event_counts() API method (GET /events) with JSON-encoded events param in src/mixpanel_data/_internal/api_client.py
- [x] T031 [US4] Add event_counts() service method in src/mixpanel_data/_internal/services/live_query.py
- [x] T032 [US4] Export EventCountsResult from src/mixpanel_data/__init__.py

**Checkpoint**: User Story 4 complete — multi-event time series analysis available

---

## Phase 7: User Story 5 - Analyze Property Value Distributions (Priority: P2)

**Goal**: Enable users to query aggregate counts broken down by property values over time for segmentation analysis

**Independent Test**: Request property counts for event/property/date range → verify series contains {value: {date: count}}, verify DataFrame conversion works

### Tests for User Story 5

- [x] T033 [P] [US5] Unit test for PropertyCountsResult type with lazy .df property in tests/unit/test_types.py
- [x] T034 [P] [US5] Unit test for api_client.property_counts() with values, limit params in tests/unit/test_api_client.py
- [x] T035 [P] [US5] Unit test for live_query.property_counts() transformation in tests/unit/test_live_query.py

### Implementation for User Story 5

- [x] T036 [P] [US5] Add PropertyCountsResult frozen dataclass with to_dict() and lazy .df property in src/mixpanel_data/types.py
- [x] T037 [US5] Add property_counts() API method (GET /events/properties) in src/mixpanel_data/_internal/api_client.py
- [x] T038 [US5] Add property_counts() service method in src/mixpanel_data/_internal/services/live_query.py
- [x] T039 [US5] Export PropertyCountsResult from src/mixpanel_data/__init__.py

**Checkpoint**: All 5 user stories complete — full feature implemented

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Quality verification and documentation

- [x] T040 Run mypy --strict on all modified files
- [x] T041 Run ruff check on all modified files
- [x] T042 [P] Run full test suite (just test) and verify all tests pass
- [x] T043 Verify quickstart.md examples work against implementation
- [x] T044 Update CLAUDE.md with new types if needed

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: Review only — no changes
- **Foundational (Phase 2)**: BLOCKS all user stories (cache type broadening)
- **User Stories (Phase 3-7)**: All depend on Foundational completion
  - US1 and US2 (both P1) can run in parallel
  - US3, US4, US5 (all P2) can run in parallel after P1 complete
- **Polish (Phase 8)**: Depends on all user stories complete

### User Story Dependencies

| Story | Depends On | Can Parallel With |
|-------|------------|-------------------|
| US1 (Funnels) | Foundational | US2 |
| US2 (Cohorts) | Foundational | US1 |
| US3 (Top Events) | Foundational | US4, US5 |
| US4 (Event Counts) | Foundational | US3, US5 |
| US5 (Property Counts) | Foundational | US3, US4 |

### Within Each User Story

1. Tests written first (can run in parallel with each other)
2. Type implementation (can run in parallel with other stories)
3. API client method (depends on type)
4. Service method (depends on API client method)
5. Export (depends on type)

### Parallel Opportunities

**Tests (all [P] within each story)**:
```
US1: T005, T006, T007 can run in parallel
US2: T012, T013, T014 can run in parallel
US3: T019, T020, T021 can run in parallel
US4: T026, T027, T028 can run in parallel
US5: T033, T034, T035 can run in parallel
```

**Types (all [P] across stories)**:
```
T008, T015, T022, T029, T036 can all run in parallel
(Each adds to different section of types.py)
```

---

## Parallel Example: User Story 1

```bash
# Launch all tests for US1 together:
Task: "Unit test for FunnelInfo type in tests/unit/test_types.py"
Task: "Unit test for api_client.list_funnels() in tests/unit/test_api_client.py"
Task: "Unit test for discovery.list_funnels() with caching in tests/unit/test_discovery.py"

# After tests written, implement type (can parallel with US2 type):
Task: "Add FunnelInfo frozen dataclass with to_dict() method in src/mixpanel_data/types.py"
```

---

## Implementation Strategy

### MVP First (User Stories 1 & 2 Only)

1. Complete Phase 1: Setup (review patterns)
2. Complete Phase 2: Foundational (cache type)
3. Complete Phase 3: User Story 1 (Funnels)
4. **STOP and VALIDATE**: Test list_funnels independently
5. Complete Phase 4: User Story 2 (Cohorts)
6. **STOP and VALIDATE**: Test list_cohorts independently
7. Deploy/demo P1 capabilities

### Incremental Delivery

| Increment | Stories | Value Delivered |
|-----------|---------|-----------------|
| MVP | US1 + US2 | Discover funnels and cohorts |
| +P2 Discovery | US3 | Real-time event activity |
| +P2 Queries | US4 + US5 | Time-series analysis |

### Suggested Execution Order

```
T001-T003 (Setup review)
    ↓
T004 (Foundational)
    ↓
┌───────────────────────┐
│ US1 (T005-T011)       │ ← Can run in parallel
│ US2 (T012-T018)       │
└───────────────────────┘
    ↓
┌───────────────────────┐
│ US3 (T019-T025)       │
│ US4 (T026-T032)       │ ← Can run in parallel
│ US5 (T033-T039)       │
└───────────────────────┘
    ↓
T040-T044 (Polish)
```

---

## Task Summary

| Phase | User Story | Task Count | Parallel Tasks |
|-------|------------|------------|----------------|
| 1 | Setup | 3 | 0 |
| 2 | Foundational | 1 | 0 |
| 3 | US1 - Funnels | 7 | 4 |
| 4 | US2 - Cohorts | 7 | 4 |
| 5 | US3 - Top Events | 7 | 4 |
| 6 | US4 - Event Counts | 7 | 4 |
| 7 | US5 - Property Counts | 7 | 4 |
| 8 | Polish | 5 | 1 |
| **Total** | | **44** | **21** |

---

## Notes

- [P] tasks can run in parallel (different files, no dependencies)
- [Story] label maps task to specific user story
- Each user story is independently completable and testable
- Tests written before implementation per TDD approach
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
