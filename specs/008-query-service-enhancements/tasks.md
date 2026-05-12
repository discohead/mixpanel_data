# Tasks: Query Service Enhancements

**Input**: Design documents from `/specs/008-query-service-enhancements/`
**Prerequisites**: plan.md, spec.md, data-model.md, contracts/, research.md, quickstart.md

**Tests**: Included based on plan.md scope (~40 tests) and acceptance scenarios from spec.md.

**Organization**: Tasks grouped by user story to enable independent implementation and testing.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2)
- Include exact file paths in descriptions

## Path Conventions

- **Single project**: `src/mixpanel_data/`, `tests/` at repository root
- Following existing patterns from Phase 006/007

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Create test fixtures directory and shared infrastructure

- [X] T001 Create test fixtures directory at tests/fixtures/phase008/
- [X] T002 [P] Create activity_feed.json fixture in tests/fixtures/phase008/activity_feed.json
- [X] T003 [P] Create insights.json fixture in tests/fixtures/phase008/insights.json
- [X] T004 [P] Create frequency.json fixture in tests/fixtures/phase008/frequency.json
- [X] T005 [P] Create segmentation_numeric.json fixture in tests/fixtures/phase008/segmentation_numeric.json
- [X] T006 [P] Create segmentation_sum.json fixture in tests/fixtures/phase008/segmentation_sum.json
- [X] T007 [P] Create segmentation_average.json fixture in tests/fixtures/phase008/segmentation_average.json

**Checkpoint**: All fixtures created - ready for implementation phases

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: No foundational work needed - extending existing modules with established patterns

**Note**: This phase has no tasks because:
- LiveQueryService already exists (Phase 006)
- API client infrastructure exists (Phase 002)
- Result type patterns established in types.py
- Test patterns established in existing unit tests

**Checkpoint**: Foundation ready (inherited from previous phases)

---

## Phase 3: User Story 1 - Query User Activity Feed (Priority: P1)

**Goal**: Retrieve a user's complete event history with chronological events

**Independent Test**: Query activity for known user ID, verify returned events match expected history

### Tests for User Story 1

- [X] T008 [P] [US1] Unit test for UserEvent dataclass in tests/unit/test_types_phase008.py
- [X] T009 [P] [US1] Unit test for ActivityFeedResult.df property in tests/unit/test_types_phase008.py
- [X] T010 [P] [US1] Unit test for ActivityFeedResult.to_dict() in tests/unit/test_types_phase008.py
- [X] T011 [P] [US1] Unit test for api_client.activity_feed() in tests/unit/test_api_client_phase008.py
- [X] T012 [P] [US1] Unit test for LiveQueryService.activity_feed() in tests/unit/test_live_query_phase008.py
- [X] T013 [P] [US1] Unit test for empty activity feed response in tests/unit/test_live_query_phase008.py

### Implementation for User Story 1

- [X] T014 [P] [US1] Create UserEvent frozen dataclass in src/mixpanel_data/types.py
- [X] T015 [P] [US1] Create ActivityFeedResult frozen dataclass with lazy .df and .to_dict() in src/mixpanel_data/types.py
- [X] T016 [US1] Implement activity_feed() method in src/mixpanel_data/_internal/api_client.py
- [X] T017 [US1] Implement _transform_activity_feed() function in src/mixpanel_data/_internal/services/live_query.py
- [X] T018 [US1] Implement activity_feed() service method in src/mixpanel_data/_internal/services/live_query.py
- [X] T019 [US1] Export UserEvent and ActivityFeedResult in src/mixpanel_data/__init__.py
- [X] T020 [US1] Update LiveQueryService imports for ActivityFeedResult in src/mixpanel_data/_internal/services/live_query.py

**Checkpoint**: Activity feed query fully functional and independently testable

---

## Phase 4: User Story 2 - Sum Numeric Property Values (Priority: P1)

**Goal**: Calculate daily/hourly sum totals for numeric properties

**Independent Test**: Sum a known numeric property, verify daily totals match expected values

### Tests for User Story 2

- [X] T021 [P] [US2] Unit test for NumericSumResult.df property in tests/unit/test_types_phase008.py
- [X] T022 [P] [US2] Unit test for NumericSumResult.to_dict() in tests/unit/test_types_phase008.py
- [X] T023 [P] [US2] Unit test for api_client.segmentation_sum() in tests/unit/test_api_client_phase008.py
- [X] T024 [P] [US2] Unit test for LiveQueryService.segmentation_sum() in tests/unit/test_live_query_phase008.py
- [X] T025 [P] [US2] Unit test for empty sum response in tests/unit/test_live_query_phase008.py

### Implementation for User Story 2

- [X] T026 [P] [US2] Create NumericSumResult frozen dataclass with lazy .df and .to_dict() in src/mixpanel_data/types.py
- [X] T027 [US2] Implement segmentation_sum() method in src/mixpanel_data/_internal/api_client.py
- [X] T028 [US2] Implement _transform_numeric_sum() function in src/mixpanel_data/_internal/services/live_query.py
- [X] T029 [US2] Implement segmentation_sum() service method with Literal types in src/mixpanel_data/_internal/services/live_query.py
- [X] T030 [US2] Export NumericSumResult in src/mixpanel_data/__init__.py

**Checkpoint**: Numeric sum query fully functional and independently testable

---

## Phase 5: User Story 3 - Average Numeric Property Values (Priority: P1)

**Goal**: Calculate daily/hourly average values for numeric properties

**Independent Test**: Average a known numeric property, verify daily averages match expected calculations

### Tests for User Story 3

- [X] T031 [P] [US3] Unit test for NumericAverageResult.df property in tests/unit/test_types_phase008.py
- [X] T032 [P] [US3] Unit test for NumericAverageResult.to_dict() in tests/unit/test_types_phase008.py
- [X] T033 [P] [US3] Unit test for api_client.segmentation_average() in tests/unit/test_api_client_phase008.py
- [X] T034 [P] [US3] Unit test for LiveQueryService.segmentation_average() in tests/unit/test_live_query_phase008.py
- [X] T035 [P] [US3] Unit test for empty average response in tests/unit/test_live_query_phase008.py

### Implementation for User Story 3

- [X] T036 [P] [US3] Create NumericAverageResult frozen dataclass with lazy .df and .to_dict() in src/mixpanel_data/types.py
- [X] T037 [US3] Implement segmentation_average() method in src/mixpanel_data/_internal/api_client.py
- [X] T038 [US3] Implement _transform_numeric_average() function in src/mixpanel_data/_internal/services/live_query.py
- [X] T039 [US3] Implement segmentation_average() service method with Literal types in src/mixpanel_data/_internal/services/live_query.py
- [X] T040 [US3] Export NumericAverageResult in src/mixpanel_data/__init__.py

**Checkpoint**: Numeric average query fully functional and independently testable

---

## Phase 6: User Story 4 - Analyze Event Frequency (Priority: P1)

**Goal**: Show frequency distribution of how often users perform events

**Independent Test**: Query frequency data for known event, verify distribution matches expected patterns

### Tests for User Story 4

- [X] T041 [P] [US4] Unit test for FrequencyResult.df property in tests/unit/test_types_phase008.py
- [X] T042 [P] [US4] Unit test for FrequencyResult.to_dict() in tests/unit/test_types_phase008.py
- [X] T043 [P] [US4] Unit test for api_client.frequency() in tests/unit/test_api_client_phase008.py
- [X] T044 [P] [US4] Unit test for LiveQueryService.frequency() in tests/unit/test_live_query_phase008.py
- [X] T045 [P] [US4] Unit test for empty frequency response in tests/unit/test_live_query_phase008.py

### Implementation for User Story 4

- [X] T046 [P] [US4] Create FrequencyResult frozen dataclass with lazy .df and .to_dict() in src/mixpanel_data/types.py
- [X] T047 [US4] Implement frequency() method in src/mixpanel_data/_internal/api_client.py
- [X] T048 [US4] Implement _transform_frequency() function in src/mixpanel_data/_internal/services/live_query.py
- [X] T049 [US4] Implement frequency() service method with Literal types in src/mixpanel_data/_internal/services/live_query.py
- [X] T050 [US4] Export FrequencyResult in src/mixpanel_data/__init__.py

**Checkpoint**: Frequency analysis fully functional and independently testable

---

## Phase 7: User Story 5 - Bucket Events by Numeric Properties (Priority: P2)

**Goal**: Segment events into automatically determined numeric ranges

**Independent Test**: Bucket a known numeric property, verify ranges and counts match expected distribution

### Tests for User Story 5

- [X] T051 [P] [US5] Unit test for NumericBucketResult.df property in tests/unit/test_types_phase008.py
- [X] T052 [P] [US5] Unit test for NumericBucketResult.to_dict() in tests/unit/test_types_phase008.py
- [X] T053 [P] [US5] Unit test for api_client.segmentation_numeric() in tests/unit/test_api_client_phase008.py
- [X] T054 [P] [US5] Unit test for LiveQueryService.segmentation_numeric() in tests/unit/test_live_query_phase008.py
- [X] T055 [P] [US5] Unit test for empty bucket response in tests/unit/test_live_query_phase008.py

### Implementation for User Story 5

- [X] T056 [P] [US5] Create NumericBucketResult frozen dataclass with lazy .df and .to_dict() in src/mixpanel_data/types.py
- [X] T057 [US5] Implement segmentation_numeric() method in src/mixpanel_data/_internal/api_client.py
- [X] T058 [US5] Implement _transform_numeric_bucket() function in src/mixpanel_data/_internal/services/live_query.py
- [X] T059 [US5] Implement segmentation_numeric() service method with Literal types in src/mixpanel_data/_internal/services/live_query.py
- [X] T060 [US5] Export NumericBucketResult in src/mixpanel_data/__init__.py

**Checkpoint**: Numeric bucketing fully functional and independently testable

---

## Phase 8: User Story 6 - Query Saved Insights Reports (Priority: P2)

**Goal**: Retrieve data from pre-configured Insights reports by bookmark ID

**Independent Test**: Query known saved report, verify returned data matches saved report configuration

### Tests for User Story 6

- [X] T061 [P] [US6] Unit test for InsightsResult.df property in tests/unit/test_types_phase008.py
- [X] T062 [P] [US6] Unit test for InsightsResult.to_dict() in tests/unit/test_types_phase008.py
- [X] T063 [P] [US6] Unit test for api_client.insights() in tests/unit/test_api_client_phase008.py
- [X] T064 [P] [US6] Unit test for LiveQueryService.insights() in tests/unit/test_live_query_phase008.py
- [X] T065 [P] [US6] Unit test for invalid bookmark_id error in tests/unit/test_live_query_phase008.py

### Implementation for User Story 6

- [X] T066 [P] [US6] Create InsightsResult frozen dataclass with lazy .df and .to_dict() in src/mixpanel_data/types.py
- [X] T067 [US6] Implement insights() method in src/mixpanel_data/_internal/api_client.py
- [X] T068 [US6] Implement _transform_insights() function in src/mixpanel_data/_internal/services/live_query.py
- [X] T069 [US6] Implement insights() service method in src/mixpanel_data/_internal/services/live_query.py
- [X] T070 [US6] Export InsightsResult in src/mixpanel_data/__init__.py

**Checkpoint**: Insights query fully functional and independently testable

---

## Phase 9: Polish & Cross-Cutting Concerns

**Purpose**: Final validation and quality checks

- [X] T071 Run mypy --strict on all modified files
- [X] T072 Run ruff check on all modified files
- [X] T073 Run full test suite to verify no regressions
- [X] T074 Validate quickstart.md examples work correctly
- [X] T075 [P] Add docstrings with examples to all new public methods
- [X] T076 Verify all new types exported in src/mixpanel_data/__init__.py

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: No tasks (inherited from prior phases)
- **User Stories (Phases 3-8)**: All depend on Setup completion
  - All P1 stories (US1-US4) can proceed in parallel
  - P2 stories (US5-US6) can proceed in parallel with P1 stories
- **Polish (Phase 9)**: Depends on all user stories being complete

### User Story Dependencies

- **US1 (Activity Feed)**: Independent - no dependencies on other stories
- **US2 (Sum)**: Independent - no dependencies on other stories
- **US3 (Average)**: Independent - no dependencies on other stories
- **US4 (Frequency)**: Independent - no dependencies on other stories
- **US5 (Bucketing)**: Independent - no dependencies on other stories
- **US6 (Insights)**: Independent - no dependencies on other stories

### Within Each User Story

- Tests first (verify they fail)
- Result types (frozen dataclasses)
- API client method (raw HTTP)
- Transformation function
- Service method (typed interface)
- Exports in __init__.py
- Story complete before moving to next

### Parallel Opportunities

**Setup Phase (7 fixtures in parallel)**:
```
T002, T003, T004, T005, T006, T007 can all run in parallel
```

**All User Stories in Parallel**:
Once Setup complete, ALL 6 user stories can be worked on simultaneously:
```
US1 (Activity Feed) | US2 (Sum) | US3 (Average) | US4 (Frequency) | US5 (Bucketing) | US6 (Insights)
```

**Within Each Story (tests in parallel)**:
```
T008, T009, T010, T011, T012, T013 (US1 tests) - all parallel
T014, T015 (US1 result types) - parallel
```

---

## Parallel Example: User Story 2 (Sum)

```bash
# Launch all tests for US2 together:
Task: "Unit test for NumericSumResult.df property in tests/unit/test_types_phase008.py"
Task: "Unit test for NumericSumResult.to_dict() in tests/unit/test_types_phase008.py"
Task: "Unit test for api_client.segmentation_sum() in tests/unit/test_api_client_phase008.py"
Task: "Unit test for LiveQueryService.segmentation_sum() in tests/unit/test_live_query_phase008.py"
Task: "Unit test for empty sum response in tests/unit/test_live_query_phase008.py"

# Then implement (sequential within story):
Task: "Create NumericSumResult frozen dataclass"
Task: "Implement segmentation_sum() in api_client"
Task: "Implement _transform_numeric_sum()"
Task: "Implement segmentation_sum() service method"
Task: "Export NumericSumResult"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (fixtures)
2. Complete Phase 3: User Story 1 (Activity Feed)
3. **STOP and VALIDATE**: Test US1 independently
4. Run `just check` to verify quality gates

### Incremental Delivery

1. Setup → Foundation ready (inherited)
2. Add US1 (Activity Feed) → Test → Checkpoint (MVP!)
3. Add US2 (Sum) → Test → Checkpoint
4. Add US3 (Average) → Test → Checkpoint
5. Add US4 (Frequency) → Test → Checkpoint
6. Add US5 (Bucketing) → Test → Checkpoint
7. Add US6 (Insights) → Test → Checkpoint
8. Polish → Final validation

### Parallel Team Strategy

With 6 developers:

1. All: Setup (7 fixtures - 2 minutes)
2. Then each developer takes one story:
   - Dev A: US1 (Activity Feed)
   - Dev B: US2 (Sum)
   - Dev C: US3 (Average)
   - Dev D: US4 (Frequency)
   - Dev E: US5 (Bucketing)
   - Dev F: US6 (Insights)
3. All stories complete independently
4. All: Polish phase together

---

## Task Summary

| Phase | Story | Tasks | Parallelizable |
|-------|-------|-------|----------------|
| 1 | Setup | 7 | 6 |
| 2 | Foundational | 0 | 0 |
| 3 | US1 (P1) | 13 | 8 |
| 4 | US2 (P1) | 10 | 5 |
| 5 | US3 (P1) | 10 | 5 |
| 6 | US4 (P1) | 10 | 5 |
| 7 | US5 (P2) | 10 | 5 |
| 8 | US6 (P2) | 10 | 5 |
| 9 | Polish | 6 | 1 |
| **Total** | | **76** | **40** |

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story
- Each user story independently completable and testable
- All user stories share same file targets (types.py, api_client.py, live_query.py) but add separate code
- Commit after each task or logical group
- Run `just check` after each story completion
