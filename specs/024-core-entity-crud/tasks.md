# Tasks: Core Entity CRUD (Dashboards, Reports, Cohorts)

**Input**: Design documents from `/specs/024-core-entity-crud/`
**Prerequisites**: plan.md (required), spec.md (required), research.md, data-model.md, contracts/

**Tests**: Included — the project requires strict TDD with 90% coverage (per CLAUDE.md).

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

---

## Phase 1: Setup

**Purpose**: Shared type infrastructure needed by all three domains

- [X] T001 [P] Add Dashboard response and param types (Dashboard, CreateDashboardParams, UpdateDashboardParams) to src/mixpanel_data/types.py
- [X] T002 [P] Add Blueprint types (BlueprintTemplate, BlueprintConfig, BlueprintCard, BlueprintFinishParams, CreateRcaDashboardParams, RcaSourceData, UpdateReportLinkParams, UpdateTextCardParams) to src/mixpanel_data/types.py
- [X] T003 [P] Add Bookmark response and param types (Bookmark, BookmarkMetadata, CreateBookmarkParams, UpdateBookmarkParams, BulkUpdateBookmarkEntry, BookmarkHistoryResponse, BookmarkHistoryPagination) to src/mixpanel_data/types.py
- [X] T004 [P] Add Cohort response and param types (Cohort, CohortCreator, CreateCohortParams, UpdateCohortParams, BulkUpdateCohortEntry) to src/mixpanel_data/types.py

**Checkpoint**: All Pydantic types defined and importable. No runtime dependencies yet.

---

## Phase 2: Foundational (API Client Methods)

**Purpose**: API client methods that MUST be complete before Workspace or CLI layers can be built

**⚠️ CRITICAL**: No user story work (Workspace/CLI) can begin until this phase is complete

### Tests

- [X] T005 [P] Write respx-mocked unit tests for dashboard API client methods (list, create, get, update, delete, bulk_delete) in tests/test_api_client.py
- [X] T006 [P] Write respx-mocked unit tests for bookmark API client methods (list_v2, create, get, update, delete, bulk_delete, bulk_update, linked_dashboard_ids) in tests/test_api_client.py
- [X] T007 [P] Write respx-mocked unit tests for cohort API client methods (list_app, create, get, update, delete, bulk_delete, bulk_update) in tests/test_api_client.py

### Implementation

- [X] T008 [P] Implement dashboard API client methods (list_dashboards, create_dashboard, get_dashboard, update_dashboard, delete_dashboard, bulk_delete_dashboards) in src/mixpanel_data/_internal/api_client.py
- [X] T009 [P] Implement dashboard advanced API methods (favorite, unfavorite, pin, unpin, remove_report_from_dashboard) in src/mixpanel_data/_internal/api_client.py
- [X] T010 [P] Implement dashboard blueprint API methods (list_blueprint_templates, create_blueprint, get_blueprint_config, update_blueprint_cohorts, finalize_blueprint) in src/mixpanel_data/_internal/api_client.py
- [X] T011 [P] Implement dashboard specialized API methods (create_rca_dashboard, get_bookmark_dashboard_ids, get_dashboard_erf, update_report_link, update_text_card) in src/mixpanel_data/_internal/api_client.py
- [X] T012 [P] Implement bookmark API client methods (list_bookmarks_v2, create_bookmark, get_bookmark, update_bookmark, delete_bookmark, bulk_delete_bookmarks, bulk_update_bookmarks, bookmark_linked_dashboard_ids, get_bookmark_history) in src/mixpanel_data/_internal/api_client.py
- [X] T013 [P] Implement cohort API client methods (list_cohorts_app, get_cohort, create_cohort, update_cohort, delete_cohort, bulk_delete_cohorts, bulk_update_cohorts) in src/mixpanel_data/_internal/api_client.py

**Checkpoint**: All ~35 API client methods implemented and tested with respx mocks. Workspace layer can now be built.

---

## Phase 3: User Story 1 — Dashboard Management via Library (Priority: P1) 🎯 MVP

**Goal**: Developers can programmatically manage dashboards via Workspace methods — list, create, get, update, delete.

**Independent Test**: Call `list_dashboards()`, `create_dashboard()`, `get_dashboard()`, `update_dashboard()`, `delete_dashboard()` on a Workspace and verify typed Dashboard objects.

### Tests for User Story 1

- [X] T014 [P] [US1] Write unit tests for dashboard Workspace CRUD methods (list, create, get, update, delete, bulk_delete) in tests/test_workspace.py

### Implementation for User Story 1

- [X] T015 [US1] Implement dashboard Workspace CRUD methods (list_dashboards, create_dashboard, get_dashboard, update_dashboard, delete_dashboard, bulk_delete_dashboards) in src/mixpanel_data/workspace.py
- [X] T016 [US1] Export new Dashboard types from src/mixpanel_data/__init__.py

**Checkpoint**: Dashboard CRUD works via Python library. `ws.list_dashboards()` returns `list[Dashboard]`.

---

## Phase 4: User Story 2 — Report/Bookmark Management via Library (Priority: P1)

**Goal**: Developers can programmatically manage reports/bookmarks — list, create, get, update, delete, bulk operations, and query linked dashboards.

**Independent Test**: Call `list_bookmarks_v2()`, `create_bookmark()`, `get_bookmark()`, `update_bookmark()`, `delete_bookmark()`, `bulk_delete_bookmarks()`, `bulk_update_bookmarks()`, `bookmark_linked_dashboard_ids()` on a Workspace.

### Tests for User Story 2

- [X] T017 [P] [US2] Write unit tests for bookmark Workspace CRUD methods (list_v2, create, get, update, delete, bulk_delete, bulk_update, linked_dashboard_ids, history) in tests/test_workspace.py

### Implementation for User Story 2

- [X] T018 [US2] Implement bookmark Workspace CRUD methods (list_bookmarks_v2, create_bookmark, get_bookmark, update_bookmark, delete_bookmark, bulk_delete_bookmarks, bulk_update_bookmarks, bookmark_linked_dashboard_ids, get_bookmark_history) in src/mixpanel_data/workspace.py
- [X] T019 [US2] Export new Bookmark types from src/mixpanel_data/__init__.py

**Checkpoint**: Bookmark CRUD works via Python library. `ws.list_bookmarks_v2()` returns `list[Bookmark]`.

---

## Phase 5: User Story 3 — Cohort CRUD via Library (Priority: P1)

**Goal**: Developers can programmatically manage cohorts with full CRUD — extending the existing read-only discovery with App API-based mutations.

**Independent Test**: Call `list_cohorts_full()`, `get_cohort()`, `create_cohort()`, `update_cohort()`, `delete_cohort()`, `bulk_delete_cohorts()`, `bulk_update_cohorts()` on a Workspace.

### Tests for User Story 3

- [X] T020 [P] [US3] Write unit tests for cohort Workspace CRUD methods (list_full, get, create, update, delete, bulk_delete, bulk_update) in tests/test_workspace.py

### Implementation for User Story 3

- [X] T021 [US3] Implement cohort Workspace CRUD methods (list_cohorts_full, get_cohort, create_cohort, update_cohort, delete_cohort, bulk_delete_cohorts, bulk_update_cohorts) in src/mixpanel_data/workspace.py
- [X] T022 [US3] Export new Cohort types from src/mixpanel_data/__init__.py

**Checkpoint**: Cohort CRUD works via Python library. `ws.list_cohorts_full()` returns `list[Cohort]`.

---

## Phase 6: User Story 4 — Dashboard Advanced Operations (Priority: P2)

**Goal**: Developers can perform advanced dashboard operations — favorite/unfavorite, pin/unpin, remove reports, blueprints, RCA dashboards, ERF metrics.

**Independent Test**: Call `favorite_dashboard()`, `pin_dashboard()`, `remove_report_from_dashboard()`, `list_blueprint_templates()`, `create_rca_dashboard()`, `get_dashboard_erf()`.

### Tests for User Story 4

- [X] T023 [P] [US4] Write unit tests for dashboard advanced Workspace methods (favorite, unfavorite, pin, unpin, remove_report, blueprint operations, RCA, ERF, report_link, text_card) in tests/test_workspace.py

### Implementation for User Story 4

- [X] T024 [US4] Implement dashboard organization Workspace methods (favorite_dashboard, unfavorite_dashboard, pin_dashboard, unpin_dashboard, remove_report_from_dashboard) in src/mixpanel_data/workspace.py
- [X] T025 [US4] Implement blueprint Workspace methods (list_blueprint_templates, create_blueprint, get_blueprint_config, update_blueprint_cohorts, finalize_blueprint) in src/mixpanel_data/workspace.py
- [X] T026 [US4] Implement specialized dashboard Workspace methods (create_rca_dashboard, get_bookmark_dashboard_ids, get_dashboard_erf, update_report_link, update_text_card) in src/mixpanel_data/workspace.py

**Checkpoint**: All 20 dashboard Workspace methods functional.

---

## Phase 7: User Story 5 — CLI Command Access (Priority: P2)

**Goal**: DevOps engineers and developers can manage dashboards, reports, and cohorts from the `mp` CLI with all 5 output formats.

**Independent Test**: Run `mp dashboards list`, `mp reports list`, `mp cohorts list` and verify structured output.

### Tests for User Story 5

- [ ] T027 [P] [US5] Write CLI integration tests for `mp dashboards` commands (list, create, get, update, delete, bulk-delete, favorite, unfavorite, pin, unpin, remove-report, blueprints, blueprint-create, rca, erf, update-report-link, update-text-card) in tests/cli/test_dashboards_cli.py
- [ ] T028 [P] [US5] Write CLI integration tests for `mp reports` commands (list, create, get, update, delete, bulk-delete, bulk-update, linked-dashboards, dashboard-ids, history) in tests/cli/test_reports_cli.py
- [ ] T029 [P] [US5] Write CLI integration tests for `mp cohorts` commands (list, create, get, update, delete, bulk-delete, bulk-update) in tests/cli/test_cohorts_cli.py

### Implementation for User Story 5

- [X] T030 [P] [US5] Create dashboards CLI command group (17 subcommands) in src/mixpanel_data/cli/commands/dashboards.py
- [X] T031 [P] [US5] Create reports CLI command group (10 subcommands) in src/mixpanel_data/cli/commands/reports.py
- [X] T032 [P] [US5] Create cohorts CLI command group (7 subcommands) in src/mixpanel_data/cli/commands/cohorts.py
- [X] T033 [US5] Register dashboards, reports, cohorts command groups in src/mixpanel_data/cli/main.py

**Checkpoint**: All 34 CLI subcommands work with all 5 output formats.

---

## Phase 8: User Story 6 — Report History and Dashboard Linkage (Priority: P3)

**Goal**: Developers can view bookmark change history and track which dashboards contain a report.

**Independent Test**: Call `get_bookmark_history()` and `get_bookmark_dashboard_ids()`.

*Note: The Workspace methods and API client methods for this story are already implemented in Phases 2/4 (bookmark_linked_dashboard_ids, get_bookmark_history, get_bookmark_dashboard_ids). This phase validates the integration.*

- [X] T034 [US6] Write integration tests verifying bookmark history pagination and dashboard linkage queries in tests/test_workspace.py

**Checkpoint**: History and linkage queries return correct paginated results.

---

## Phase 9: User Story 7 — Dashboard ERF, RCA, and Blueprint Workflows (Priority: P3)

*Note: All methods for this story are already implemented in Phases 2/6 (ERF, RCA, blueprints). This phase validates end-to-end workflows.*

- [X] T035 [US7] Write integration tests verifying blueprint workflow (list templates → create → configure → finalize) and RCA dashboard creation in tests/test_workspace.py

**Checkpoint**: Blueprint and RCA workflows complete end-to-end.

---

## Phase 10: Polish & Cross-Cutting Concerns

**Purpose**: Quality gates, property tests, and documentation

- [ ] T036 [P] Write Hypothesis property-based tests for all new Pydantic types (round-trip serialization, field invariants) in tests/test_types_pbt.py
- [X] T037 [P] Add docstrings (Google style) to all new Workspace methods, API client methods, and Pydantic types
- [X] T038 Run `just check` (ruff format + ruff check + mypy --strict + pytest) and fix all issues; verify error messages include entity type and operation context per FR-014
- [ ] T039 Run `just test-cov` and ensure 90% coverage for all new code
- [ ] T040 Validate quickstart.md examples work end-to-end with mock fixtures

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup/Types)**: No dependencies — can start immediately
- **Phase 2 (API Client)**: Depends on Phase 1 (types must exist) — BLOCKS all user stories
- **Phases 3-5 (US1-US3, P1)**: All depend on Phase 2 — can run in parallel
- **Phase 6 (US4, P2)**: Depends on Phase 3 (dashboard CRUD must exist)
- **Phase 7 (US5, P2)**: Depends on Phases 3-6 (all Workspace methods must exist for CLI to wrap)
- **Phases 8-9 (US6-US7, P3)**: Depend on Phase 6 — validation only
- **Phase 10 (Polish)**: Depends on all previous phases

### User Story Dependencies

- **US1 (Dashboards)**: Phase 2 only — fully independent
- **US2 (Bookmarks)**: Phase 2 only — fully independent
- **US3 (Cohorts)**: Phase 2 only — fully independent
- **US4 (Advanced Dashboards)**: Depends on US1 (extends dashboard methods)
- **US5 (CLI)**: Depends on US1-US4 (wraps all Workspace methods)
- **US6 (History/Linkage)**: Depends on US2 + US4 (uses bookmark + dashboard methods)
- **US7 (ERF/RCA/Blueprints)**: Depends on US4 (uses advanced dashboard methods)

### Within Each User Story

- Tests MUST be written first and FAIL before implementation
- Types (Phase 1) before API methods (Phase 2)
- API methods before Workspace methods
- Workspace methods before CLI commands
- Core CRUD before advanced operations

### Parallel Opportunities

**Phase 1**: All 4 type tasks (T001-T004) can run in parallel (separate type groups)
**Phase 2**: All 6 API implementation tasks (T008-T013) can run in parallel (different API method groups in same file — but logically independent sections)
**Phase 2 tests**: All 3 test tasks (T005-T007) can run in parallel
**Phases 3-5**: US1, US2, US3 can all run in parallel after Phase 2
**Phase 7**: All 3 CLI command files (T030-T032) can run in parallel

---

## Parallel Example: Phase 2 (API Client)

```bash
# Launch all API client test tasks together:
Task: "Write respx-mocked tests for dashboard API methods in tests/test_api_client.py"
Task: "Write respx-mocked tests for bookmark API methods in tests/test_api_client.py"
Task: "Write respx-mocked tests for cohort API methods in tests/test_api_client.py"

# Launch all API client implementations together:
Task: "Implement dashboard API methods in api_client.py"
Task: "Implement bookmark API methods in api_client.py"
Task: "Implement cohort API methods in api_client.py"
```

## Parallel Example: Phases 3-5 (Library CRUD)

```bash
# After Phase 2 completes, launch all P1 stories in parallel:
Task: "Implement dashboard Workspace CRUD methods"
Task: "Implement bookmark Workspace CRUD methods"
Task: "Implement cohort Workspace CRUD methods"
```

## Parallel Example: Phase 7 (CLI)

```bash
# Launch all CLI command files together:
Task: "Create dashboards CLI in commands/dashboards.py"
Task: "Create reports CLI in commands/reports.py"
Task: "Create cohorts CLI in commands/cohorts.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Types (T001-T004)
2. Complete Phase 2: API Client for dashboards only (T005, T008)
3. Complete Phase 3: US1 Dashboard Workspace methods (T014-T016)
4. **STOP and VALIDATE**: `ws.list_dashboards()` returns typed Dashboard objects
5. Deploy if ready — dashboard CRUD works

### Incremental Delivery

1. Phase 1 + 2 → All API methods ready
2. Add US1 (Dashboards) → Test → Working dashboard CRUD
3. Add US2 (Bookmarks) → Test → Working report CRUD
4. Add US3 (Cohorts) → Test → Working cohort CRUD
5. Add US4 (Advanced) → Test → Full dashboard feature set
6. Add US5 (CLI) → Test → All 34 commands work
7. Add US6+US7 (History/RCA) → Test → Complete feature set
8. Polish → Quality gates pass

---

## Notes

- [P] tasks = different files or logically independent sections, no blocking dependencies
- [Story] label maps task to specific user story for traceability
- All types go in `types.py` — coordinate parallel type tasks to avoid merge conflicts
- All API methods go in `api_client.py` — logically independent sections but same file
- All Workspace methods go in `workspace.py` — same coordination note
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
