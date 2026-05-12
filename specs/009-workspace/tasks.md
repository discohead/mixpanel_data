# Tasks: Workspace Facade

**Input**: Design documents from `/specs/009-workspace/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: Included (SC-009 specifies 90% test coverage requirement)

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

- **Source**: `src/mixpanel_data/`
- **Tests**: `tests/unit/`, `tests/integration/`
- Single Python package following existing src layout

---

## Phase 1: Setup

**Purpose**: Create Workspace module skeleton and update package exports

- [X] T001 Create workspace.py skeleton with imports in src/mixpanel_data/workspace.py
- [X] T002 [P] Add Workspace and WorkspaceInfo to __all__ in src/mixpanel_data/__init__.py
- [X] T003 [P] Add TableMetadata, TableInfo, ColumnInfo, TableSchema to __all__ in src/mixpanel_data/__init__.py
- [X] T004 [P] Create test file skeleton in tests/unit/test_workspace.py
- [X] T005 [P] Create integration test skeleton in tests/integration/test_workspace_integration.py

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core Workspace infrastructure that all user stories depend on

**Critical**: No user story work can begin until this phase is complete

- [X] T006 Implement Workspace class with instance attributes (_credentials, _account_name, _storage, _api_client, _discovery, _fetcher, _live_query, _config_manager) in src/mixpanel_data/workspace.py
- [X] T007 Implement _get_api_client() lazy initialization method in src/mixpanel_data/workspace.py
- [X] T008 Implement _discovery_service property with lazy initialization in src/mixpanel_data/workspace.py
- [X] T009 Implement _fetcher_service property with lazy initialization in src/mixpanel_data/workspace.py
- [X] T010 Implement _live_query_service property with lazy initialization in src/mixpanel_data/workspace.py
- [X] T011 Implement _require_api_client() helper that raises ConfigError when credentials unavailable in src/mixpanel_data/workspace.py
- [X] T012 [P] Add Workspace fixture factory to tests/conftest.py for unit testing
- [X] T013 [P] Add integration test fixtures with temp database paths to tests/conftest.py

**Checkpoint**: Foundation ready - service wiring complete, user story implementation can begin

---

## Phase 3: User Story 5 - Credential Resolution (Priority: P2, but foundational)

**Goal**: Flexible credential configuration supporting env vars, named accounts, and defaults

**Independent Test**: Create Workspace with different credential sources and verify resolution

**Note**: Implemented first because US1-4 all depend on credential resolution

### Tests for User Story 5

- [X] T014 [P] [US5] Unit test for env var credential resolution in tests/unit/test_workspace.py
- [X] T015 [P] [US5] Unit test for named account credential resolution in tests/unit/test_workspace.py
- [X] T016 [P] [US5] Unit test for default account credential resolution in tests/unit/test_workspace.py
- [X] T017 [P] [US5] Unit test for ConfigError when no credentials available in tests/unit/test_workspace.py

### Implementation for User Story 5

- [X] T018 [US5] Implement __init__() with credential resolution (env → named → default) in src/mixpanel_data/workspace.py
- [X] T019 [US5] Implement StorageEngine creation with path parameter in src/mixpanel_data/workspace.py
- [X] T020 [US5] Implement dependency injection parameters (_config_manager, _api_client, _storage) in src/mixpanel_data/workspace.py
- [X] T021 [US5] Add comprehensive docstring with examples to __init__() in src/mixpanel_data/workspace.py

**Checkpoint**: Workspace can be constructed with credentials from any source

---

## Phase 4: User Story 1 - Basic Data Analysis Workflow (Priority: P1)

**Goal**: Fetch events, store locally, run SQL queries for offline analysis

**Independent Test**: Create Workspace, call fetch_events(), run sql() queries against stored data

### Tests for User Story 1

- [X] T022 [P] [US1] Unit test for fetch_events() delegation in tests/unit/test_workspace.py
- [X] T023 [P] [US1] Unit test for fetch_profiles() delegation in tests/unit/test_workspace.py
- [X] T024 [P] [US1] Unit test for sql() returning DataFrame in tests/unit/test_workspace.py
- [X] T025 [P] [US1] Unit test for sql_scalar() returning single value in tests/unit/test_workspace.py
- [X] T026 [P] [US1] Unit test for sql_rows() returning tuples in tests/unit/test_workspace.py
- [X] T027 [US1] Integration test for fetch-query workflow in tests/integration/test_workspace_integration.py
- [X] T028 [US1] Integration test for data persistence across sessions in tests/integration/test_workspace_integration.py

### Implementation for User Story 1

- [X] T029 [US1] Implement fetch_events() with progress bar callback adapter in src/mixpanel_data/workspace.py
- [X] T030 [US1] Implement fetch_profiles() with progress bar callback adapter in src/mixpanel_data/workspace.py
- [X] T031 [P] [US1] Implement sql() delegating to StorageEngine.execute_df() in src/mixpanel_data/workspace.py
- [X] T032 [P] [US1] Implement sql_scalar() delegating to StorageEngine.execute_scalar() in src/mixpanel_data/workspace.py
- [X] T033 [P] [US1] Implement sql_rows() delegating to StorageEngine.execute_rows() in src/mixpanel_data/workspace.py
- [X] T034 [US1] Implement close() method releasing all resources in src/mixpanel_data/workspace.py
- [X] T035 [US1] Implement __enter__() and __exit__() context manager protocol in src/mixpanel_data/workspace.py

**Checkpoint**: Complete fetch → query → close workflow works

---

## Phase 5: User Story 2 - Ephemeral Analysis Session (Priority: P1)

**Goal**: Temporary workspaces that auto-delete on exit for AI agents

**Independent Test**: Use Workspace.ephemeral() context manager, verify cleanup after exit

### Tests for User Story 2

- [X] T036 [P] [US2] Unit test for ephemeral() creating temporary storage in tests/unit/test_workspace.py
- [X] T037 [P] [US2] Unit test for ephemeral cleanup on normal exit in tests/unit/test_workspace.py
- [X] T038 [P] [US2] Unit test for ephemeral cleanup on exception in tests/unit/test_workspace.py
- [X] T039 [US2] Integration test for ephemeral fetch-query-cleanup workflow in tests/integration/test_workspace_integration.py

### Implementation for User Story 2

- [X] T040 [US2] Implement ephemeral() classmethod as context manager in src/mixpanel_data/workspace.py
- [X] T041 [US2] Ensure ephemeral uses StorageEngine.ephemeral() for temp database in src/mixpanel_data/workspace.py
- [X] T042 [US2] Add docstring with usage example to ephemeral() in src/mixpanel_data/workspace.py

**Checkpoint**: Ephemeral workspaces auto-cleanup in all scenarios

---

## Phase 6: User Story 3 - Live Analytics Queries (Priority: P1)

**Goal**: Real-time Mixpanel reports without local storage

**Independent Test**: Create Workspace, call segmentation/funnel/retention, verify results

### Tests for User Story 3

- [X] T043 [P] [US3] Unit test for segmentation() delegation in tests/unit/test_workspace.py
- [X] T044 [P] [US3] Unit test for funnel() delegation in tests/unit/test_workspace.py
- [X] T045 [P] [US3] Unit test for retention() delegation in tests/unit/test_workspace.py
- [X] T046 [P] [US3] Unit test for jql() delegation in tests/unit/test_workspace.py
- [X] T047 [P] [US3] Unit test for event_counts() delegation in tests/unit/test_workspace.py
- [X] T048 [P] [US3] Unit test for property_counts() delegation in tests/unit/test_workspace.py
- [X] T049 [P] [US3] Unit test for activity_feed() delegation in tests/unit/test_workspace.py
- [X] T050 [P] [US3] Unit test for insights() delegation in tests/unit/test_workspace.py
- [X] T051 [P] [US3] Unit test for frequency() delegation in tests/unit/test_workspace.py
- [X] T052 [P] [US3] Unit test for segmentation_numeric() delegation in tests/unit/test_workspace.py
- [X] T053 [P] [US3] Unit test for segmentation_sum() delegation in tests/unit/test_workspace.py
- [X] T054 [P] [US3] Unit test for segmentation_average() delegation in tests/unit/test_workspace.py

### Implementation for User Story 3

- [X] T055 [P] [US3] Implement segmentation() delegating to LiveQueryService in src/mixpanel_data/workspace.py
- [X] T056 [P] [US3] Implement funnel() delegating to LiveQueryService in src/mixpanel_data/workspace.py
- [X] T057 [P] [US3] Implement retention() delegating to LiveQueryService in src/mixpanel_data/workspace.py
- [X] T058 [P] [US3] Implement jql() delegating to LiveQueryService in src/mixpanel_data/workspace.py
- [X] T059 [P] [US3] Implement event_counts() delegating to LiveQueryService in src/mixpanel_data/workspace.py
- [X] T060 [P] [US3] Implement property_counts() delegating to LiveQueryService in src/mixpanel_data/workspace.py
- [X] T061 [P] [US3] Implement activity_feed() delegating to LiveQueryService in src/mixpanel_data/workspace.py
- [X] T062 [P] [US3] Implement insights() delegating to LiveQueryService in src/mixpanel_data/workspace.py
- [X] T063 [P] [US3] Implement frequency() delegating to LiveQueryService in src/mixpanel_data/workspace.py
- [X] T064 [P] [US3] Implement segmentation_numeric() delegating to LiveQueryService in src/mixpanel_data/workspace.py
- [X] T065 [P] [US3] Implement segmentation_sum() delegating to LiveQueryService in src/mixpanel_data/workspace.py
- [X] T066 [P] [US3] Implement segmentation_average() delegating to LiveQueryService in src/mixpanel_data/workspace.py

**Checkpoint**: All 12 live query methods work and return typed results

---

## Phase 7: User Story 4 - Schema Discovery (Priority: P2)

**Goal**: Explore events, properties, and values before writing queries

**Independent Test**: Create Workspace, call events/properties/property_values, verify caching

### Tests for User Story 4

- [X] T067 [P] [US4] Unit test for events() delegation and caching in tests/unit/test_workspace.py
- [X] T068 [P] [US4] Unit test for properties() delegation in tests/unit/test_workspace.py
- [X] T069 [P] [US4] Unit test for property_values() delegation in tests/unit/test_workspace.py
- [X] T070 [P] [US4] Unit test for funnels() delegation in tests/unit/test_workspace.py
- [X] T071 [P] [US4] Unit test for cohorts() delegation in tests/unit/test_workspace.py
- [X] T072 [P] [US4] Unit test for top_events() delegation (not cached) in tests/unit/test_workspace.py
- [X] T073 [P] [US4] Unit test for clear_discovery_cache() in tests/unit/test_workspace.py

### Implementation for User Story 4

- [X] T074 [P] [US4] Implement events() delegating to DiscoveryService.list_events() in src/mixpanel_data/workspace.py
- [X] T075 [P] [US4] Implement properties() delegating to DiscoveryService.list_properties() in src/mixpanel_data/workspace.py
- [X] T076 [P] [US4] Implement property_values() delegating to DiscoveryService.list_property_values() in src/mixpanel_data/workspace.py
- [X] T077 [P] [US4] Implement funnels() delegating to DiscoveryService.list_funnels() in src/mixpanel_data/workspace.py
- [X] T078 [P] [US4] Implement cohorts() delegating to DiscoveryService.list_cohorts() in src/mixpanel_data/workspace.py
- [X] T079 [P] [US4] Implement top_events() delegating to DiscoveryService.list_top_events() in src/mixpanel_data/workspace.py
- [X] T080 [US4] Implement clear_discovery_cache() delegating to DiscoveryService.clear_cache() in src/mixpanel_data/workspace.py

**Checkpoint**: All 7 discovery methods work with appropriate caching

---

## Phase 8: User Story 6 - Query-Only Access (Priority: P2)

**Goal**: Open existing database without API credentials

**Independent Test**: Use Workspace.open(path), run sql queries, verify API methods raise errors

### Tests for User Story 6

- [X] T081 [P] [US6] Unit test for Workspace.open() creating query-only workspace in tests/unit/test_workspace.py
- [X] T082 [P] [US6] Unit test for sql operations working without credentials in tests/unit/test_workspace.py
- [X] T083 [P] [US6] Unit test for API methods raising ConfigError in query-only mode in tests/unit/test_workspace.py
- [X] T084 [US6] Integration test for open existing database in tests/integration/test_workspace_integration.py

### Implementation for User Story 6

- [X] T085 [US6] Implement Workspace.open() classmethod for query-only access in src/mixpanel_data/workspace.py
- [X] T086 [US6] Ensure open() sets _credentials to None in src/mixpanel_data/workspace.py
- [X] T087 [US6] Verify _require_api_client() raises helpful ConfigError for opened workspaces in src/mixpanel_data/workspace.py

**Checkpoint**: Users can query existing databases without credentials

---

## Phase 9: User Story 7 - Table Introspection and Management (Priority: P3)

**Goal**: Understand and manage workspace data (info, tables, schema, drop)

**Independent Test**: Fetch data, call info/tables/schema/drop, verify results

### Tests for User Story 7

- [X] T088 [P] [US7] Unit test for info() returning WorkspaceInfo in tests/unit/test_workspace.py
- [X] T089 [P] [US7] Unit test for tables() delegation in tests/unit/test_workspace.py
- [X] T090 [P] [US7] Unit test for schema() delegation in tests/unit/test_workspace.py
- [X] T091 [P] [US7] Unit test for drop() delegation in tests/unit/test_workspace.py
- [X] T092 [P] [US7] Unit test for drop_all() with type filter in tests/unit/test_workspace.py
- [X] T093 [P] [US7] Unit test for TableNotFoundError on invalid drop in tests/unit/test_workspace.py
- [X] T094 [US7] Integration test for table management workflow in tests/integration/test_workspace_integration.py

### Implementation for User Story 7

- [X] T095 [US7] Implement info() computing WorkspaceInfo from storage and credentials in src/mixpanel_data/workspace.py
- [X] T096 [P] [US7] Implement tables() delegating to StorageEngine.list_tables() in src/mixpanel_data/workspace.py
- [X] T097 [P] [US7] Implement schema() delegating to StorageEngine.get_schema() in src/mixpanel_data/workspace.py
- [X] T098 [US7] Implement drop(*names) calling StorageEngine.drop_table() for each in src/mixpanel_data/workspace.py
- [X] T099 [US7] Implement drop_all(type) filtering tables by type before dropping in src/mixpanel_data/workspace.py

**Checkpoint**: Workspace introspection and table management complete

---

## Phase 10: User Story 8 - Advanced Access (Priority: P3)

**Goal**: Escape hatches for power users (direct DuckDB/API access)

**Independent Test**: Access .connection and .api properties, verify they work

### Tests for User Story 8

- [X] T100 [P] [US8] Unit test for connection property returning DuckDB connection in tests/unit/test_workspace.py
- [X] T101 [P] [US8] Unit test for api property returning MixpanelAPIClient in tests/unit/test_workspace.py
- [X] T102 [P] [US8] Unit test for api property raising ConfigError when no credentials in tests/unit/test_workspace.py

### Implementation for User Story 8

- [X] T103 [P] [US8] Implement connection property exposing StorageEngine.connection in src/mixpanel_data/workspace.py
- [X] T104 [US8] Implement api property with _require_api_client() check in src/mixpanel_data/workspace.py

**Checkpoint**: Power users can access underlying components

---

## Phase 11: Polish & Cross-Cutting Concerns

**Purpose**: Final quality improvements across all user stories

- [X] T105 Add comprehensive module docstring to src/mixpanel_data/workspace.py
- [X] T106 [P] Verify all public methods have Google-style docstrings in src/mixpanel_data/workspace.py
- [X] T107 Run ruff check and fix any linting issues in src/mixpanel_data/workspace.py
- [X] T108 Run mypy --strict and fix any type errors in src/mixpanel_data/workspace.py
- [X] T109 [P] Run test coverage report and verify 90%+ coverage for workspace module
- [X] T110 Validate quickstart.md examples work with implementation

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: No dependencies - can start immediately
- **Phase 2 (Foundational)**: Depends on Phase 1 - BLOCKS all user stories
- **Phase 3 (US5 Credentials)**: Depends on Phase 2 - BLOCKS user stories 1-4, 6-8
- **Phases 4-10 (User Stories)**: All depend on Phase 3 completion
  - US1-4, US7-8 require credentials
  - US6 (query-only) is independent after foundational
- **Phase 11 (Polish)**: Depends on all stories being complete

### User Story Dependencies

| Story | Depends On | Can Parallel With |
|-------|------------|-------------------|
| US5 (Credentials) | Foundation | None (first) |
| US1 (Basic Workflow) | US5 | US2, US3, US4 |
| US2 (Ephemeral) | US5 | US1, US3, US4 |
| US3 (Live Queries) | US5 | US1, US2, US4 |
| US4 (Discovery) | US5 | US1, US2, US3 |
| US6 (Query-Only) | Foundation | All others |
| US7 (Introspection) | US5 | US8 |
| US8 (Escape Hatches) | US5 | US7 |

### Parallel Opportunities

**Within Foundational Phase**:
- T012 and T013 (test fixtures) can run in parallel

**Within Each User Story**:
- All unit tests marked [P] can run in parallel
- All method implementations marked [P] can run in parallel

**Across Stories** (after Phase 3):
- US1-US4 can all proceed in parallel
- US6 can proceed independently
- US7-US8 can proceed in parallel

---

## Parallel Example: User Story 3

```bash
# Launch all 12 unit tests in parallel:
Task: T043 "Unit test for segmentation() delegation"
Task: T044 "Unit test for funnel() delegation"
Task: T045 "Unit test for retention() delegation"
...

# Launch all 12 implementations in parallel:
Task: T055 "Implement segmentation()"
Task: T056 "Implement funnel()"
Task: T057 "Implement retention()"
...
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (T001-T005)
2. Complete Phase 2: Foundational (T006-T013)
3. Complete Phase 3: US5 Credentials (T014-T021)
4. Complete Phase 4: US1 Basic Workflow (T022-T035)
5. **STOP and VALIDATE**: Test fetch → sql → close workflow
6. Deploy if ready

### Incremental Delivery

1. **Setup + Foundation + US5** → Credentials work
2. **Add US1** → Fetch and query works → MVP!
3. **Add US2** → Ephemeral workspaces work
4. **Add US3** → Live queries work
5. **Add US4** → Discovery works
6. **Add US6** → Query-only mode works
7. **Add US7** → Table management works
8. **Add US8** → Escape hatches available
9. **Polish** → Quality gates pass

### Suggested MVP Scope

**Phase 1 + 2 + 3 + 4** = T001-T035 (35 tasks)
- Creates Workspace with credential resolution
- Enables fetch → sql → close workflow
- Core value proposition complete

---

## Notes

- All services (DiscoveryService, FetcherService, LiveQueryService, StorageEngine) already exist
- This phase is primarily delegation and orchestration
- Most implementation tasks are straightforward delegation to existing services
- Focus on type hints, docstrings, and error handling
- Progress bar implementation uses Rich via callback adapter to existing FetcherService
- Test mocking uses existing patterns from conftest.py
