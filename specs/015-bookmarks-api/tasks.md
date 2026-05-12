# Tasks: Bookmarks API for Saved Reports

**Input**: Design documents from `/specs/015-bookmarks-api/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: Included - follows TDD approach per implementation plan
**Organization**: Tasks grouped by user story to enable independent implementation and testing

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2, US3, US4)
- Exact file paths included in descriptions

---

## Phase 1: Setup (Type Definitions)

**Purpose**: Define new types and prepare for migration. These are shared across all user stories.

- [x] T001 [P] Add BookmarkType and SavedReportType literals in src/mixpanel_data/types.py
- [x] T002 [P] Add BookmarkInfo frozen dataclass with all fields and to_dict() in src/mixpanel_data/types.py
- [x] T003 Add SavedReportResult frozen dataclass (replacing InsightsResult pattern) with report_type property, df property, and to_dict() in src/mixpanel_data/types.py
- [x] T004 [P] Add FlowsResult frozen dataclass with df property and to_dict() in src/mixpanel_data/types.py
- [x] T005 Update public exports in src/mixpanel_data/__init__.py to include BookmarkInfo, BookmarkType, SavedReportResult, SavedReportType, FlowsResult

**Checkpoint**: All new types defined and exported ✅

---

## Phase 2: Foundational (Migration - BLOCKING)

**Purpose**: Rename existing insights() infrastructure to query_saved_report(). This MUST complete before user stories can proceed.

**⚠️ CRITICAL**: Existing code depends on InsightsResult and insights(). This migration enables proper naming.

### Tests for Migration

- [x] T006 Write tests for SavedReportResult including report_type detection in tests/unit/test_types_bookmarks.py
- [x] T007 [P] Write tests for FlowsResult in tests/unit/test_types_bookmarks.py

### Migration Implementation

- [x] T008 Remove InsightsResult from src/mixpanel_data/types.py (replaced by SavedReportResult in T003)
- [x] T009 Update InsightsResult import to SavedReportResult in src/mixpanel_data/__init__.py
- [x] T010 Rename insights() to query_saved_report() in src/mixpanel_data/_internal/api_client.py
- [x] T011 Rename insights() to query_saved_report() and _transform_insights() to _transform_saved_report() in src/mixpanel_data/_internal/services/live_query.py, update return type to SavedReportResult
- [x] T012 Rename insights() to query_saved_report() in src/mixpanel_data/workspace.py, update return type to SavedReportResult
- [x] T013 Update existing tests: replace InsightsResult with SavedReportResult and insights() with query_saved_report() in tests/unit/test_api_client_phase008.py
- [x] T014 Update existing tests: replace references in tests/unit/test_live_query_phase008.py (if exists)
- [x] T015 Run `just check` to verify migration doesn't break existing functionality

**Checkpoint**: Migration complete - insights → query_saved_report renamed throughout, all tests pass ✅

---

## Phase 3: User Story 1 - List Saved Reports (Priority: P1) 🎯 MVP

**Goal**: Enable users to discover all saved reports (bookmarks) in their Mixpanel project with metadata

**Independent Test**: List bookmarks and verify returned metadata (ID, name, type, timestamps)

### Tests for User Story 1

- [ ] T016 [P] [US1] Write tests for MixpanelAPIClient.list_bookmarks() in tests/unit/test_api_client_bookmarks.py - verify endpoint URL, params, response parsing
- [ ] T017 [P] [US1] Write tests for DiscoveryService.list_bookmarks() in tests/unit/test_discovery_bookmarks.py - verify BookmarkInfo parsing
- [ ] T018 [P] [US1] Write tests for Workspace.list_bookmarks() in tests/unit/test_workspace_bookmarks.py - verify delegation and type filter

### Implementation for User Story 1

- [ ] T019 [US1] Implement list_bookmarks() in src/mixpanel_data/_internal/api_client.py - call /api/app/projects/{project_id}/bookmarks with v=2
- [ ] T020 [US1] Implement _parse_bookmark_info() helper and list_bookmarks() in src/mixpanel_data/_internal/services/discovery.py
- [ ] T021 [US1] Implement list_bookmarks() in src/mixpanel_data/workspace.py - delegate to DiscoveryService
- [ ] T022 [US1] Run tests for US1: `just test tests/unit/test_api_client_bookmarks.py tests/unit/test_discovery_bookmarks.py tests/unit/test_workspace_bookmarks.py`

**Checkpoint**: `ws.list_bookmarks()` works and returns list[BookmarkInfo] with all metadata

---

## Phase 4: User Story 2 - Query Saved Reports (Priority: P1)

**Goal**: Execute saved Insights, Retention, and Funnel reports by bookmark ID with automatic type detection

**Independent Test**: Query a bookmark and verify report_type property correctly identifies insights/retention/funnel

### Tests for User Story 2

- [ ] T023 [P] [US2] Write tests for SavedReportResult.report_type detection in tests/unit/test_types_bookmarks.py - test insights, retention, funnel header patterns
- [ ] T024 [P] [US2] Write tests for query_saved_report with different bookmark types in tests/unit/test_workspace_bookmarks.py

### Implementation for User Story 2

- [ ] T025 [US2] Verify _transform_saved_report() correctly handles retention/funnel series structures in src/mixpanel_data/_internal/services/live_query.py
- [ ] T026 [US2] Update SavedReportResult.series type annotation to dict[str, Any] in src/mixpanel_data/types.py (if not already done)
- [ ] T027 [US2] Run tests for US2: `just test -k "saved_report or report_type"`

**Checkpoint**: `ws.query_saved_report(bookmark_id)` works for insights, retention, and funnel bookmarks with correct report_type

---

## Phase 5: User Story 3 - Query Saved Flows Reports (Priority: P2)

**Goal**: Execute saved Flows reports which require a different API endpoint

**Independent Test**: Query a flows bookmark and verify step data, breakdowns, and conversion rate returned

### Tests for User Story 3

- [ ] T028 [P] [US3] Write tests for MixpanelAPIClient.query_flows() in tests/unit/test_api_client_bookmarks.py - verify /api/query/arb_funnels endpoint with query_type=flows_sankey
- [ ] T029 [P] [US3] Write tests for LiveQueryService.query_flows() in tests/unit/test_live_query_bookmarks.py - verify FlowsResult transformation
- [ ] T030 [P] [US3] Write tests for Workspace.query_flows() in tests/unit/test_workspace_bookmarks.py

### Implementation for User Story 3

- [ ] T031 [US3] Implement query_flows() in src/mixpanel_data/_internal/api_client.py - call /api/query/arb_funnels with query_type=flows_sankey
- [ ] T032 [US3] Implement _transform_flows() and query_flows() in src/mixpanel_data/_internal/services/live_query.py
- [ ] T033 [US3] Implement query_flows() in src/mixpanel_data/workspace.py - delegate to LiveQueryService
- [ ] T034 [US3] Run tests for US3: `just test -k flows`

**Checkpoint**: `ws.query_flows(bookmark_id)` works and returns FlowsResult with steps, breakdowns, conversion rate

---

## Phase 6: User Story 4 - CLI Access to Bookmarks (Priority: P2)

**Goal**: Provide CLI commands for listing and querying bookmarks

**Independent Test**: Run CLI commands and verify JSON/table output formats

### Tests for User Story 4

- [ ] T035 [P] [US4] Write tests for `mp inspect bookmarks` command in tests/integration/cli/test_bookmark_commands.py
- [ ] T036 [P] [US4] Write tests for `mp query saved-report` command in tests/integration/cli/test_bookmark_commands.py
- [ ] T037 [P] [US4] Write tests for `mp query flows` command in tests/integration/cli/test_bookmark_commands.py

### Implementation for User Story 4

- [ ] T038 [US4] Add `bookmarks` command to src/mixpanel_data/cli/commands/inspect.py with --type filter and --format option
- [ ] T039 [US4] Rename `insights` command to `saved-report` in src/mixpanel_data/cli/commands/query.py
- [ ] T040 [US4] Add `flows` command to src/mixpanel_data/cli/commands/query.py
- [ ] T041 [US4] Update CLI help text and command epilog to include new commands
- [ ] T042 [US4] Run CLI tests: `just test tests/integration/cli/test_bookmark_commands.py`

**Checkpoint**: All CLI commands work: `mp inspect bookmarks`, `mp query saved-report`, `mp query flows`

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Final validation, documentation, and quality checks

- [ ] T043 Run full test suite: `just test`
- [ ] T044 Run linting and type checks: `just check`
- [ ] T045 [P] Validate quickstart.md examples work as documented
- [ ] T046 [P] Test across all data residency regions (US, EU, IN) if credentials available
- [ ] T047 Review and update docstrings for all new public methods
- [ ] T048 Final code review for constitution compliance

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: No dependencies - can start immediately
- **Phase 2 (Foundational)**: Depends on Phase 1 - BLOCKS all user stories
- **Phase 3-6 (User Stories)**: All depend on Phase 2 completion
  - US1 and US2 can proceed in parallel (both P1)
  - US3 depends on FlowsResult from Phase 1
  - US4 depends on all library methods from US1, US2, US3
- **Phase 7 (Polish)**: Depends on all user stories being complete

### User Story Dependencies

```
Phase 1 (Types) ─────────────────────────────────────────┐
                                                         │
Phase 2 (Migration) ─────────────────────────────────────┼──> Phase 7 (Polish)
         │                                               │
         ├──> Phase 3 (US1: List) ───────────────────────┤
         │                          └──> Phase 6 (US4) ──┤
         ├──> Phase 4 (US2: Query) ─────────────────────>│
         │                          └──> Phase 6 (US4) ──┤
         └──> Phase 5 (US3: Flows) ─────────────────────>│
                                    └──> Phase 6 (US4) ──┘
```

### Within Each User Story (TDD Order)

1. Write tests (T0XX [P]) - can run in parallel
2. Implement API client method
3. Implement service method
4. Implement workspace method
5. Run tests to verify

### Parallel Opportunities

**Phase 1** (all parallel - different parts of types.py):
- T001, T002, T004 can run in parallel

**Phase 2** (tests parallel):
- T006, T007 can run in parallel

**Phase 3** (tests parallel, then sequential implementation):
- T016, T017, T018 can run in parallel
- T019 → T020 → T021 sequential

**Phase 5** (tests parallel):
- T028, T029, T030 can run in parallel

**Phase 6** (tests parallel):
- T035, T036, T037 can run in parallel

---

## Parallel Example: User Story 1 Tests

```bash
# Launch all tests for User Story 1 together:
Task: "T016 [P] [US1] Write tests for MixpanelAPIClient.list_bookmarks()"
Task: "T017 [P] [US1] Write tests for DiscoveryService.list_bookmarks()"
Task: "T018 [P] [US1] Write tests for Workspace.list_bookmarks()"
```

---

## Implementation Strategy

### MVP First (User Story 1 + 2 Only)

1. Complete Phase 1: Setup (types)
2. Complete Phase 2: Migration (rename insights → query_saved_report)
3. Complete Phase 3: User Story 1 (list_bookmarks)
4. Complete Phase 4: User Story 2 (query_saved_report improvements)
5. **STOP and VALIDATE**: Test list + query independently
6. Deploy/demo if ready

### Incremental Delivery

1. Setup + Migration → Foundation ready
2. Add US1 (List) → `ws.list_bookmarks()` works → Demo
3. Add US2 (Query) → Report type detection works → Demo
4. Add US3 (Flows) → `ws.query_flows()` works → Demo
5. Add US4 (CLI) → All CLI commands work → Demo

### Single Developer Strategy

Execute in task order (T001 → T048), following TDD:
1. Write test, verify it fails
2. Implement, verify test passes
3. Refactor if needed
4. Commit and move to next task

---

## Notes

- [P] tasks = different files, no dependencies within that phase
- [Story] label maps task to specific user story for traceability
- Tests MUST be written and FAIL before implementation (TDD)
- Run `just check` after each phase to catch issues early
- Commit after each completed task or logical group
