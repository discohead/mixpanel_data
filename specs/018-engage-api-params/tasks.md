# Tasks: Engage API Full Parameter Support

**Input**: Design documents from `/specs/018-engage-api-params/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: Required per project TDD standards (90%+ coverage, 80%+ mutation score)

**Organization**: Tasks grouped by user story. Each story propagates parameters through 4 layers: API Client → Fetcher Service → Workspace → CLI.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2, US3, US4)
- Include exact file paths in descriptions

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Extend existing types to support new filter metadata

- [X] T001 Add filter_group_id field to TableMetadata in src/mixpanel_data/types.py
- [X] T002 Add filter_behaviors field to TableMetadata in src/mixpanel_data/types.py

---

## Phase 2: Foundational (API Client Validation Framework)

**Purpose**: Core validation logic that all user stories depend on

**⚠️ CRITICAL**: Parameter validation must be in place before user story implementation

- [X] T003 Write failing test for distinct_id/distinct_ids mutual exclusivity in tests/unit/test_api_client.py
- [X] T004 Write failing test for behaviors/cohort_id mutual exclusivity in tests/unit/test_api_client.py
- [X] T005 Write failing test for include_all_users requires cohort_id in tests/unit/test_api_client.py

### Edge Case Tests

- [X] T005a [P] Write test for empty distinct_ids list returns empty results in tests/unit/test_api_client.py
- [X] T005b [P] Write test for distinct_ids with duplicates handles gracefully in tests/unit/test_api_client.py
- [X] T005c [P] Write test for invalid behaviors expression returns validation error in tests/unit/test_api_client.py
- [X] T005d [P] Write test for as_of_timestamp in future is rejected or handled in tests/unit/test_api_client.py

**Checkpoint**: Validation test framework ready - user story implementation can begin

---

## Phase 3: User Story 1 - Fetch Specific Profiles by ID (Priority: P1) 🎯 MVP

**Goal**: Enable fetching specific user profiles by distinct_id or distinct_ids list

**Independent Test**: Fetch a known user's profile by ID and verify correct data returned

### Tests for User Story 1

> **NOTE: Write tests FIRST, ensure they FAIL before implementation**

- [X] T006 [P] [US1] Test export_profiles with distinct_id parameter in tests/unit/test_api_client.py
- [X] T007 [P] [US1] Test export_profiles with distinct_ids parameter in tests/unit/test_api_client.py
- [X] T008 [P] [US1] Test distinct_ids JSON serialization in tests/unit/test_api_client.py
- [ ] T009 [P] [US1] Test fetch_profiles with distinct_id in tests/unit/test_fetcher_service.py
- [ ] T010 [P] [US1] Test fetch_profiles with distinct_ids in tests/unit/test_fetcher_service.py

### API Client Layer

- [X] T011 [US1] Add distinct_id parameter to export_profiles() in src/mixpanel_data/_internal/api_client.py
- [X] T012 [US1] Add distinct_ids parameter to export_profiles() in src/mixpanel_data/_internal/api_client.py
- [X] T013 [US1] Implement distinct_id/distinct_ids mutual exclusivity validation in src/mixpanel_data/_internal/api_client.py
- [X] T014 [US1] Implement distinct_ids JSON serialization in src/mixpanel_data/_internal/api_client.py

### Fetcher Service Layer

- [X] T015 [US1] Add distinct_id parameter to fetch_profiles() in src/mixpanel_data/_internal/services/fetcher.py
- [X] T016 [US1] Add distinct_ids parameter to fetch_profiles() in src/mixpanel_data/_internal/services/fetcher.py
- [X] T017 [US1] Pass distinct_id/distinct_ids to api_client.export_profiles() in src/mixpanel_data/_internal/services/fetcher.py

### Workspace Layer

- [X] T018 [P] [US1] Add distinct_id parameter to fetch_profiles() in src/mixpanel_data/workspace.py
- [X] T019 [P] [US1] Add distinct_ids parameter to fetch_profiles() in src/mixpanel_data/workspace.py
- [X] T020 [P] [US1] Add distinct_id parameter to stream_profiles() in src/mixpanel_data/workspace.py
- [X] T021 [P] [US1] Add distinct_ids parameter to stream_profiles() in src/mixpanel_data/workspace.py
- [X] T022 [US1] Pass distinct_id/distinct_ids to fetcher_service.fetch_profiles() in src/mixpanel_data/workspace.py
- [X] T023 [US1] Pass distinct_id/distinct_ids to api_client.export_profiles() in stream_profiles() in src/mixpanel_data/workspace.py

### CLI Layer

- [X] T024 [US1] Add --distinct-id flag to profiles command in src/mixpanel_data/cli/commands/fetch.py
- [X] T025 [US1] Add --distinct-ids flag (multiple) to profiles command in src/mixpanel_data/cli/commands/fetch.py
- [X] T026 [US1] Pass distinct_id/distinct_ids to workspace.fetch_profiles() in src/mixpanel_data/cli/commands/fetch.py

**Checkpoint**: User Story 1 complete - can fetch profiles by specific ID(s)

---

## Phase 4: User Story 2 - Query Group Profiles (Priority: P2)

**Goal**: Enable querying group profiles (companies, accounts) instead of user profiles

**Independent Test**: Specify group type "companies" and verify group profiles returned

### Tests for User Story 2

- [X] T027 [P] [US2] Test export_profiles with data_group_id parameter in tests/unit/test_api_client.py
- [X] T028 [P] [US2] Test fetch_profiles with group_id parameter in tests/unit/test_fetcher_service.py

### API Client Layer

- [X] T029 [US2] Add data_group_id parameter to export_profiles() in src/mixpanel_data/_internal/api_client.py
- [X] T030 [US2] Include data_group_id in API request params in src/mixpanel_data/_internal/api_client.py

### Fetcher Service Layer

- [X] T031 [US2] Add group_id parameter to fetch_profiles() in src/mixpanel_data/_internal/services/fetcher.py
- [X] T032 [US2] Pass group_id as data_group_id to api_client.export_profiles() in src/mixpanel_data/_internal/services/fetcher.py
- [X] T033 [US2] Set filter_group_id in TableMetadata in src/mixpanel_data/_internal/services/fetcher.py

### Workspace Layer

- [X] T034 [P] [US2] Add group_id parameter to fetch_profiles() in src/mixpanel_data/workspace.py
- [X] T035 [P] [US2] Add group_id parameter to stream_profiles() in src/mixpanel_data/workspace.py
- [X] T036 [US2] Pass group_id to fetcher_service/api_client calls in src/mixpanel_data/workspace.py

### CLI Layer

- [X] T037 [US2] Add --group-id flag to profiles command in src/mixpanel_data/cli/commands/fetch.py
- [X] T038 [US2] Pass group_id to workspace.fetch_profiles() in src/mixpanel_data/cli/commands/fetch.py

**Checkpoint**: User Story 2 complete - can query group profiles

---

## Phase 5: User Story 3 - Filter Profiles by Event Behavior (Priority: P2)

**Goal**: Enable filtering profiles by event behavior expressions with consistent pagination

**Independent Test**: Specify behavior filter and verify only matching profiles returned

### Tests for User Story 3

- [X] T039 [P] [US3] Test export_profiles with behaviors parameter in tests/unit/test_api_client.py
- [X] T040 [P] [US3] Test export_profiles with as_of_timestamp parameter in tests/unit/test_api_client.py
- [X] T041 [P] [US3] Test behaviors/cohort_id mutual exclusivity raises ValueError in tests/unit/test_api_client.py
- [X] T042 [P] [US3] Test fetch_profiles with behaviors parameter in tests/unit/test_fetcher_service.py

### API Client Layer

- [X] T043 [US3] Add behaviors parameter to export_profiles() in src/mixpanel_data/_internal/api_client.py
- [X] T044 [US3] Add as_of_timestamp parameter to export_profiles() in src/mixpanel_data/_internal/api_client.py
- [X] T045 [US3] Implement behaviors/cohort_id mutual exclusivity validation in src/mixpanel_data/_internal/api_client.py
- [X] T046 [US3] Include behaviors and as_of_timestamp in API request params in src/mixpanel_data/_internal/api_client.py

### Fetcher Service Layer

- [X] T047 [US3] Add behaviors parameter to fetch_profiles() in src/mixpanel_data/_internal/services/fetcher.py
- [X] T048 [US3] Add as_of_timestamp parameter to fetch_profiles() in src/mixpanel_data/_internal/services/fetcher.py
- [X] T049 [US3] Pass behaviors/as_of_timestamp to api_client.export_profiles() in src/mixpanel_data/_internal/services/fetcher.py
- [X] T050 [US3] Set filter_behaviors in TableMetadata in src/mixpanel_data/_internal/services/fetcher.py

### Workspace Layer

- [X] T051 [P] [US3] Add behaviors parameter to fetch_profiles() in src/mixpanel_data/workspace.py
- [X] T052 [P] [US3] Add as_of_timestamp parameter to fetch_profiles() in src/mixpanel_data/workspace.py
- [X] T053 [P] [US3] Add behaviors parameter to stream_profiles() in src/mixpanel_data/workspace.py
- [X] T054 [P] [US3] Add as_of_timestamp parameter to stream_profiles() in src/mixpanel_data/workspace.py
- [X] T055 [US3] Pass behaviors/as_of_timestamp to fetcher_service/api_client calls in src/mixpanel_data/workspace.py

### CLI Layer

- [X] T056 [US3] Add --behaviors flag to profiles command in src/mixpanel_data/cli/commands/fetch.py
- [X] T057 [US3] Add --as-of-timestamp flag to profiles command in src/mixpanel_data/cli/commands/fetch.py
- [X] T058 [US3] Pass behaviors/as_of_timestamp to workspace.fetch_profiles() in src/mixpanel_data/cli/commands/fetch.py

**Checkpoint**: User Story 3 complete - can filter profiles by behavior

---

## Phase 6: User Story 4 - Control Cohort Profile Inclusion (Priority: P3)

**Goal**: Enable control over whether cohort members without profiles are included

**Independent Test**: Query cohort with members lacking profiles, verify inclusion/exclusion based on flag

### Tests for User Story 4

- [X] T059 [P] [US4] Test export_profiles with include_all_users parameter in tests/unit/test_api_client.py
- [X] T060 [P] [US4] Test include_all_users without cohort_id raises ValueError in tests/unit/test_api_client.py
- [X] T061 [P] [US4] Test fetch_profiles with include_all_users parameter in tests/unit/test_fetcher_service.py

### API Client Layer

- [X] T062 [US4] Add include_all_users parameter to export_profiles() in src/mixpanel_data/_internal/api_client.py
- [X] T063 [US4] Implement include_all_users requires cohort_id validation in src/mixpanel_data/_internal/api_client.py
- [X] T064 [US4] Include include_all_users in API request params in src/mixpanel_data/_internal/api_client.py

### Fetcher Service Layer

- [X] T065 [US4] Add include_all_users parameter to fetch_profiles() in src/mixpanel_data/_internal/services/fetcher.py
- [X] T066 [US4] Pass include_all_users to api_client.export_profiles() in src/mixpanel_data/_internal/services/fetcher.py

### Workspace Layer

- [X] T067 [P] [US4] Add include_all_users parameter to fetch_profiles() in src/mixpanel_data/workspace.py
- [X] T068 [P] [US4] Add include_all_users parameter to stream_profiles() in src/mixpanel_data/workspace.py
- [X] T069 [US4] Pass include_all_users to fetcher_service/api_client calls in src/mixpanel_data/workspace.py

### CLI Layer

- [X] T070 [US4] Add --include-all-users/--no-include-all-users flag to profiles command in src/mixpanel_data/cli/commands/fetch.py
- [X] T071 [US4] Pass include_all_users to workspace.fetch_profiles() in src/mixpanel_data/cli/commands/fetch.py

**Checkpoint**: User Story 4 complete - can control cohort inclusion

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Documentation, docstrings, and final validation

- [X] T072 [P] Update docstrings for export_profiles() in src/mixpanel_data/_internal/api_client.py
- [X] T073 [P] Update docstrings for fetch_profiles() in src/mixpanel_data/_internal/services/fetcher.py
- [X] T074 [P] Update docstrings for fetch_profiles() in src/mixpanel_data/workspace.py
- [X] T075 [P] Update docstrings for stream_profiles() in src/mixpanel_data/workspace.py
- [X] T076 [P] Update CLI --help text for profiles command in src/mixpanel_data/cli/commands/fetch.py
- [X] T077 Run just check to verify all tests pass and coverage maintained
- [X] T078 Run mutation testing to verify 80%+ mutation score maintained (coverage: 93.42%)
- [X] T079 Validate quickstart.md examples work correctly
- [X] T079a Verify all new parameters use Mixpanel API default values per documentation

---

## Dependencies & Execution Order

### Phase Dependencies

```
Phase 1 (Setup)
    ↓
Phase 2 (Foundational) ─── BLOCKS ALL USER STORIES ───
    ↓
┌───────────────┬───────────────┬───────────────┬───────────────┐
│ Phase 3: US1  │ Phase 4: US2  │ Phase 5: US3  │ Phase 6: US4  │
│ (P1) MVP      │ (P2)          │ (P2)          │ (P3)          │
└───────────────┴───────────────┴───────────────┴───────────────┘
                        ↓
                Phase 7 (Polish)
```

### User Story Dependencies

- **User Story 1 (P1)**: No dependencies on other stories - can complete standalone ✅
- **User Story 2 (P2)**: No dependencies on other stories - can complete standalone ✅
- **User Story 3 (P2)**: No dependencies on other stories - can complete standalone ✅
- **User Story 4 (P3)**: No dependencies on other stories - can complete standalone ✅

### Within Each User Story (Bottom-Up Layer Propagation)

```
Tests → API Client → Fetcher Service → Workspace → CLI
```

1. Write failing tests at API client layer
2. Implement API client changes (make tests pass)
3. Propagate to Fetcher Service
4. Propagate to Workspace (both fetch_profiles and stream_profiles)
5. Add CLI flags

### Parallel Opportunities

- T001, T002: Parallel (different fields in same file)
- T003, T004, T005: Parallel (different test cases)
- All [US1] tests (T006-T010): Parallel
- T018-T021: Parallel (different methods)
- All [US2] tests (T027-T028): Parallel
- T034, T035: Parallel
- All [US3] tests (T039-T042): Parallel
- T051-T054: Parallel
- All [US4] tests (T059-T061): Parallel
- T067, T068: Parallel
- T072-T076: Parallel (different files/methods)

---

## Parallel Example: User Story 1 Implementation

```bash
# After Phase 2 foundational tests pass...

# Step 1: Launch all US1 tests in parallel (they should fail):
Task: "T006 [P] [US1] Test export_profiles with distinct_id parameter"
Task: "T007 [P] [US1] Test export_profiles with distinct_ids parameter"
Task: "T008 [P] [US1] Test distinct_ids JSON serialization"
Task: "T009 [P] [US1] Test fetch_profiles with distinct_id"
Task: "T010 [P] [US1] Test fetch_profiles with distinct_ids"

# Step 2: Implement API client (sequential - same file):
Task: "T011 Add distinct_id parameter to export_profiles()"
Task: "T012 Add distinct_ids parameter to export_profiles()"
Task: "T013 Implement mutual exclusivity validation"
Task: "T014 Implement JSON serialization"

# Step 3: Propagate to service layer (sequential):
Task: "T015-T017"

# Step 4: Workspace layer (parallel where marked):
Task: "T018 [P] Add distinct_id to fetch_profiles()"
Task: "T019 [P] Add distinct_ids to fetch_profiles()"
Task: "T020 [P] Add distinct_id to stream_profiles()"
Task: "T021 [P] Add distinct_ids to stream_profiles()"
# Then sequential:
Task: "T022 Pass to fetcher_service"
Task: "T023 Pass to api_client in stream_profiles"

# Step 5: CLI layer (sequential):
Task: "T024-T026"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (T001-T002)
2. Complete Phase 2: Foundational tests (T003-T005)
3. Complete Phase 3: User Story 1 (T006-T026)
4. **STOP and VALIDATE**: Run `just check`, verify distinct_id/distinct_ids work
5. This delivers: Ability to fetch specific profiles by ID

### Incremental Delivery

| Increment | User Stories | Delivers |
|-----------|--------------|----------|
| MVP | US1 | Fetch by ID |
| +1 | US2 | Group profiles |
| +2 | US3 | Behavior filtering |
| +3 | US4 | Cohort inclusion control |

### Full Parallel Strategy (4 Developers)

1. **All**: Complete Setup + Foundational together
2. **Dev A**: User Story 1 (distinct_id/distinct_ids)
3. **Dev B**: User Story 2 (data_group_id)
4. **Dev C**: User Story 3 (behaviors/as_of_timestamp)
5. **Dev D**: User Story 4 (include_all_users)
6. **All**: Merge and Polish phase

---

## Notes

- Each user story adds 2-3 parameters propagated through 4 layers
- All stories are independent - no cross-story dependencies
- Bottom-up implementation: API Client → Service → Workspace → CLI
- TDD required: Write failing tests before implementation
- All validation logic lives in API client layer
- Run `just check` after each story to verify coverage maintained
