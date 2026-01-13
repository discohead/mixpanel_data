# Tasks: MCP Server for mixpanel_data

## ✅ IMPLEMENTATION COMPLETE

**Status**: All 11 phases implemented successfully
**Tests**: 68 passing (64 unit + 4 integration)
**Components**: 31 tools, 6 resources, 4 prompts
**CLI**: `mp-mcp-server --help` verified working

### Remaining Tasks
- T149: Verify 90% coverage threshold (`just test-cov mp-mcp-server/tests/`)

---

**Input**: Design documents from `/specs/020-mcp-server/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md
**TDD Approach**: Tests FIRST (per CLAUDE.md strict TDD requirements)

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

- **Source**: `mp-mcp-server/src/mp_mcp_server/`
- **Tests**: `mp-mcp-server/tests/`

---

## Phase 1: Setup (Project Scaffolding) ✅ COMPLETE

**Purpose**: Create package structure and FastMCP server foundation

- [x] T001 Create mp-mcp-server package directory structure per plan.md
- [x] T002 Create pyproject.toml with fastmcp>=2.0 and mixpanel_data dependencies in mp-mcp-server/pyproject.toml
- [x] T003 [P] Create package __init__.py in mp-mcp-server/src/mp_mcp_server/__init__.py
- [x] T004 [P] Create tools package __init__.py in mp-mcp-server/src/mp_mcp_server/tools/__init__.py
- [x] T005 [P] Create tests conftest.py with shared fixtures in mp-mcp-server/tests/conftest.py
- [x] T006 [P] Create unit tests directory structure in mp-mcp-server/tests/unit/
- [x] T007 [P] Create integration tests directory in mp-mcp-server/tests/integration/

**Checkpoint**: Package structure ready for development ✅

---

## Phase 2: Foundational (Core Server & Context) ✅ COMPLETE

**Purpose**: Core infrastructure that MUST be complete before ANY user story can be implemented

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

### Tests for Foundational

- [x] T008 [P] Write test_server.py: test_server_has_name, test_server_has_instructions in mp-mcp-server/tests/unit/test_server.py
- [x] T009 [P] Write test_server.py: test_lifespan_creates_workspace, test_lifespan_closes_workspace in mp-mcp-server/tests/unit/test_server.py
- [x] T010 [P] Write test_context.py: test_get_workspace_returns_workspace, test_get_workspace_raises_without_lifespan in mp-mcp-server/tests/unit/test_context.py
- [x] T011 [P] Write test_errors.py: test exception conversion for AuthenticationError, RateLimitError (with retry_after), TableExistsError, TableNotFoundError, QueryError, ConfigError, and generic MixpanelDataError in mp-mcp-server/tests/unit/test_errors.py

### Implementation for Foundational

- [x] T012 Implement FastMCP server with lifespan pattern in mp-mcp-server/src/mp_mcp_server/server.py
- [x] T013 Implement get_workspace context helper in mp-mcp-server/src/mp_mcp_server/context.py
- [x] T014 Implement handle_errors decorator for exception conversion in mp-mcp-server/src/mp_mcp_server/errors.py
- [x] T015 Run tests and verify all pass: just test -k "test_server or test_context or test_errors"

**Checkpoint**: Foundation ready - user story implementation can now begin in parallel ✅

---

## Phase 3: User Story 1 - Schema Discovery (Priority: P1) 🎯 MVP ✅ COMPLETE

**Goal**: Enable AI assistants to explore Mixpanel project schema (events, properties, funnels, cohorts)

**Independent Test**: Connect to MCP server and ask "What events are tracked?" - should return event list

### Tests for User Story 1

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [x] T016 [P] [US1] Write test_list_events_tool_registered in mp-mcp-server/tests/unit/test_tools_discovery.py
- [x] T017 [P] [US1] Write test_list_events_returns_event_names in mp-mcp-server/tests/unit/test_tools_discovery.py
- [x] T018 [P] [US1] Write test_list_properties_tool_registered in mp-mcp-server/tests/unit/test_tools_discovery.py
- [x] T019 [P] [US1] Write test_list_properties_returns_property_names in mp-mcp-server/tests/unit/test_tools_discovery.py
- [x] T020 [P] [US1] Write test_list_property_values_returns_values in mp-mcp-server/tests/unit/test_tools_discovery.py
- [x] T021 [P] [US1] Write test_list_funnels_returns_funnel_info in mp-mcp-server/tests/unit/test_tools_discovery.py
- [x] T022 [P] [US1] Write test_list_cohorts_returns_cohort_info in mp-mcp-server/tests/unit/test_tools_discovery.py
- [x] T023 [P] [US1] Write test_list_bookmarks_returns_bookmark_info in mp-mcp-server/tests/unit/test_tools_discovery.py
- [x] T024 [P] [US1] Write test_top_events_returns_event_activity in mp-mcp-server/tests/unit/test_tools_discovery.py
- [x] T025 [P] [US1] Write test_workspace_info_returns_state in mp-mcp-server/tests/unit/test_tools_discovery.py

### Implementation for User Story 1

- [x] T026 [US1] Implement list_events tool in mp-mcp-server/src/mp_mcp_server/tools/discovery.py
- [x] T027 [US1] Implement list_properties tool in mp-mcp-server/src/mp_mcp_server/tools/discovery.py
- [x] T028 [US1] Implement list_property_values tool in mp-mcp-server/src/mp_mcp_server/tools/discovery.py
- [x] T029 [US1] Implement list_funnels tool in mp-mcp-server/src/mp_mcp_server/tools/discovery.py
- [x] T030 [US1] Implement list_cohorts tool in mp-mcp-server/src/mp_mcp_server/tools/discovery.py
- [x] T031 [US1] Implement list_bookmarks tool in mp-mcp-server/src/mp_mcp_server/tools/discovery.py
- [x] T032 [US1] Implement top_events tool in mp-mcp-server/src/mp_mcp_server/tools/discovery.py
- [x] T033 [US1] Implement workspace_info tool in mp-mcp-server/src/mp_mcp_server/tools/discovery.py
- [x] T034 [US1] Register discovery tools in server.py imports in mp-mcp-server/src/mp_mcp_server/server.py
- [x] T035 [US1] Run discovery tests and verify all pass: just test -k test_tools_discovery

**Checkpoint**: At this point, User Story 1 should be fully functional and testable independently ✅

---

## Phase 4: User Story 2 - Live Analytics Queries (Priority: P1) ✅ COMPLETE

**Goal**: Execute live Mixpanel queries (segmentation, funnel, retention) through natural language

**Independent Test**: Ask "How many logins happened each day last month?" - should return daily counts

### Tests for User Story 2

- [x] T036 [P] [US2] Write test_segmentation_returns_time_series in mp-mcp-server/tests/unit/test_tools_live_query.py
- [x] T037 [P] [US2] Write test_segmentation_with_segment_property in mp-mcp-server/tests/unit/test_tools_live_query.py
- [x] T038 [P] [US2] Write test_funnel_returns_conversion_data in mp-mcp-server/tests/unit/test_tools_live_query.py
- [x] T039 [P] [US2] Write test_retention_returns_cohort_data in mp-mcp-server/tests/unit/test_tools_live_query.py
- [x] T040 [P] [US2] Write test_jql_executes_script in mp-mcp-server/tests/unit/test_tools_live_query.py
- [x] T041 [P] [US2] Write test_event_counts_returns_multi_event_series in mp-mcp-server/tests/unit/test_tools_live_query.py
- [x] T042 [P] [US2] Write test_property_counts_returns_value_breakdown in mp-mcp-server/tests/unit/test_tools_live_query.py
- [x] T043 [P] [US2] Write test_activity_feed_returns_user_events in mp-mcp-server/tests/unit/test_tools_live_query.py
- [x] T044 [P] [US2] Write test_frequency_returns_distribution in mp-mcp-server/tests/unit/test_tools_live_query.py
- [x] T045 [P] [US2] Write test_segmentation_numeric_returns_buckets in mp-mcp-server/tests/unit/test_tools_live_query.py
- [x] T046 [P] [US2] Write test_segmentation_sum_returns_totals in mp-mcp-server/tests/unit/test_tools_live_query.py
- [x] T047 [P] [US2] Write test_segmentation_average_returns_averages in mp-mcp-server/tests/unit/test_tools_live_query.py
- [x] T048 [P] [US2] Write test_query_flows_executes_flows_report in mp-mcp-server/tests/unit/test_tools_live_query.py
- [x] T049 [P] [US2] Write test_query_saved_report_executes_insight in mp-mcp-server/tests/unit/test_tools_live_query.py

### Implementation for User Story 2

- [x] T050 [US2] Implement segmentation tool in mp-mcp-server/src/mp_mcp_server/tools/live_query.py
- [x] T051 [US2] Implement funnel tool in mp-mcp-server/src/mp_mcp_server/tools/live_query.py
- [x] T052 [US2] Implement retention tool in mp-mcp-server/src/mp_mcp_server/tools/live_query.py
- [x] T053 [US2] Implement jql tool in mp-mcp-server/src/mp_mcp_server/tools/live_query.py
- [x] T054 [US2] Implement event_counts tool in mp-mcp-server/src/mp_mcp_server/tools/live_query.py
- [x] T055 [US2] Implement property_counts tool in mp-mcp-server/src/mp_mcp_server/tools/live_query.py
- [x] T056 [US2] Implement activity_feed tool in mp-mcp-server/src/mp_mcp_server/tools/live_query.py
- [x] T057 [US2] Implement frequency tool in mp-mcp-server/src/mp_mcp_server/tools/live_query.py
- [x] T058 [US2] Implement segmentation_numeric tool in mp-mcp-server/src/mp_mcp_server/tools/live_query.py
- [x] T059 [US2] Implement segmentation_sum tool in mp-mcp-server/src/mp_mcp_server/tools/live_query.py
- [x] T060 [US2] Implement segmentation_average tool in mp-mcp-server/src/mp_mcp_server/tools/live_query.py
- [x] T061 [US2] Implement query_flows tool in mp-mcp-server/src/mp_mcp_server/tools/live_query.py
- [x] T062 [US2] Implement query_saved_report tool in mp-mcp-server/src/mp_mcp_server/tools/live_query.py
- [x] T063 [US2] Register live query tools in server.py imports in mp-mcp-server/src/mp_mcp_server/server.py
- [x] T064 [US2] Run live query tests and verify all pass: just test -k test_tools_live_query

**Checkpoint**: At this point, User Stories 1 AND 2 should both work independently ✅

---

## Phase 5: User Story 3 - Data Fetching (Priority: P2) ✅ COMPLETE

**Goal**: Fetch raw event data into local database for custom SQL analysis

**Independent Test**: Ask "Fetch events from January 1-7" - should download and store events

### Tests for User Story 3

- [x] T065 [P] [US3] Write test_fetch_events_creates_table in mp-mcp-server/tests/unit/test_tools_fetch.py
- [x] T066 [P] [US3] Write test_fetch_events_returns_fetch_result in mp-mcp-server/tests/unit/test_tools_fetch.py
- [x] T067 [P] [US3] Write test_fetch_events_with_date_range in mp-mcp-server/tests/unit/test_tools_fetch.py
- [x] T068 [P] [US3] Write test_fetch_profiles_creates_table in mp-mcp-server/tests/unit/test_tools_fetch.py
- [x] T069 [P] [US3] Write test_fetch_profiles_returns_fetch_result in mp-mcp-server/tests/unit/test_tools_fetch.py
- [x] T070 [P] [US3] Write test_stream_events_returns_iterator_info in mp-mcp-server/tests/unit/test_tools_fetch.py
- [x] T071 [P] [US3] Write test_fetch_events_parallel_uses_workers in mp-mcp-server/tests/unit/test_tools_fetch.py

### Implementation for User Story 3

- [x] T072 [US3] Implement fetch_events tool in mp-mcp-server/src/mp_mcp_server/tools/fetch.py
- [x] T073 [US3] Implement fetch_profiles tool in mp-mcp-server/src/mp_mcp_server/tools/fetch.py
- [x] T074 [US3] Implement stream_events tool in mp-mcp-server/src/mp_mcp_server/tools/fetch.py
- [x] T075 [US3] Implement stream_profiles tool in mp-mcp-server/src/mp_mcp_server/tools/fetch.py
- [x] T076 [US3] Register fetch tools in server.py imports in mp-mcp-server/src/mp_mcp_server/server.py
- [x] T077 [US3] Run fetch tests and verify all pass: just test -k test_tools_fetch

**Checkpoint**: Data fetching complete - local analysis can begin ✅

---

## Phase 6: User Story 4 - Local SQL Analysis (Priority: P2) ✅ COMPLETE

**Goal**: Run custom SQL queries against locally fetched data

**Independent Test**: Fetch data then ask "Find the top 10 users by event count" - should execute SQL

### Tests for User Story 4

- [x] T078 [P] [US4] Write test_sql_executes_query in mp-mcp-server/tests/unit/test_tools_local.py
- [x] T079 [P] [US4] Write test_sql_returns_dict_format in mp-mcp-server/tests/unit/test_tools_local.py
- [x] T080 [P] [US4] Write test_sql_scalar_returns_single_value in mp-mcp-server/tests/unit/test_tools_local.py
- [x] T081 [P] [US4] Write test_list_tables_returns_table_info in mp-mcp-server/tests/unit/test_tools_local.py
- [x] T082 [P] [US4] Write test_table_schema_returns_columns in mp-mcp-server/tests/unit/test_tools_local.py
- [x] T083 [P] [US4] Write test_sample_returns_random_rows in mp-mcp-server/tests/unit/test_tools_local.py
- [x] T084 [P] [US4] Write test_summarize_returns_statistics in mp-mcp-server/tests/unit/test_tools_local.py
- [x] T085 [P] [US4] Write test_event_breakdown_returns_counts in mp-mcp-server/tests/unit/test_tools_local.py
- [x] T086 [P] [US4] Write test_property_keys_extracts_json_keys in mp-mcp-server/tests/unit/test_tools_local.py
- [x] T087 [P] [US4] Write test_column_stats_returns_detailed_stats in mp-mcp-server/tests/unit/test_tools_local.py
- [x] T088 [P] [US4] Write test_drop_table_removes_table in mp-mcp-server/tests/unit/test_tools_local.py
- [x] T089 [P] [US4] Write test_drop_all_removes_all_tables in mp-mcp-server/tests/unit/test_tools_local.py

### Implementation for User Story 4

- [x] T090 [US4] Implement sql tool in mp-mcp-server/src/mp_mcp_server/tools/local.py
- [x] T091 [US4] Implement sql_scalar tool in mp-mcp-server/src/mp_mcp_server/tools/local.py
- [x] T092 [US4] Implement list_tables tool in mp-mcp-server/src/mp_mcp_server/tools/local.py
- [x] T093 [US4] Implement table_schema tool in mp-mcp-server/src/mp_mcp_server/tools/local.py
- [x] T094 [US4] Implement sample tool in mp-mcp-server/src/mp_mcp_server/tools/local.py
- [x] T095 [US4] Implement summarize tool in mp-mcp-server/src/mp_mcp_server/tools/local.py
- [x] T096 [US4] Implement event_breakdown tool in mp-mcp-server/src/mp_mcp_server/tools/local.py
- [x] T097 [US4] Implement property_keys tool in mp-mcp-server/src/mp_mcp_server/tools/local.py
- [x] T098 [US4] Implement column_stats tool in mp-mcp-server/src/mp_mcp_server/tools/local.py
- [x] T099 [US4] Implement drop_table tool in mp-mcp-server/src/mp_mcp_server/tools/local.py
- [x] T100 [US4] Implement drop_all_tables tool in mp-mcp-server/src/mp_mcp_server/tools/local.py
- [x] T101 [US4] Register local tools in server.py imports in mp-mcp-server/src/mp_mcp_server/server.py
- [x] T102 [US4] Run local tests and verify all pass: just test -k test_tools_local

**Checkpoint**: Full fetch + local analysis workflow complete ✅

---

## Phase 7: User Story 5 - Session Persistence (Priority: P3) ✅ COMPLETE

**Goal**: Maintain session state across multiple tool calls within a conversation

**Independent Test**: Fetch data, run query, then run another query - data should persist

### Tests for User Story 5

- [x] T103 [P] [US5] Write test_workspace_info_resource in mp-mcp-server/tests/unit/test_resources.py
- [x] T104 [P] [US5] Write test_tables_resource in mp-mcp-server/tests/unit/test_resources.py
- [x] T105 [P] [US5] Write test_events_resource in mp-mcp-server/tests/unit/test_resources.py
- [x] T106 [P] [US5] Write test_funnels_resource in mp-mcp-server/tests/unit/test_resources.py
- [x] T107 [P] [US5] Write test_cohorts_resource in mp-mcp-server/tests/unit/test_resources.py
- [x] T108 [P] [US5] Write test_properties_resource_template in mp-mcp-server/tests/unit/test_resources.py
- [x] T109 [P] [US5] Write test_table_schema_resource_template in mp-mcp-server/tests/unit/test_resources.py

### Implementation for User Story 5

- [x] T110 [US5] Implement workspace://info resource in mp-mcp-server/src/mp_mcp_server/resources.py
- [x] T111 [US5] Implement workspace://tables resource in mp-mcp-server/src/mp_mcp_server/resources.py
- [x] T112 [US5] Implement schema://events resource in mp-mcp-server/src/mp_mcp_server/resources.py
- [x] T113 [US5] Implement schema://funnels resource in mp-mcp-server/src/mp_mcp_server/resources.py
- [x] T114 [US5] Implement schema://cohorts resource in mp-mcp-server/src/mp_mcp_server/resources.py
- [x] T115 [US5] Implement schema://bookmarks resource in mp-mcp-server/src/mp_mcp_server/resources.py
- [x] T116 [US5] Implement schema://properties/{event} resource template in mp-mcp-server/src/mp_mcp_server/resources.py
- [x] T117 [US5] Implement workspace://schema/{table} resource template in mp-mcp-server/src/mp_mcp_server/resources.py
- [x] T118 [US5] Implement workspace://sample/{table} resource template in mp-mcp-server/src/mp_mcp_server/resources.py
- [x] T119 [US5] Register resources in server.py imports in mp-mcp-server/src/mp_mcp_server/server.py
- [x] T120 [US5] Run resource tests and verify all pass: just test -k test_resources

**Checkpoint**: MCP resources provide session state visibility ✅

---

## Phase 8: User Story 6 - Guided Analytics Workflows (Priority: P3) ✅ COMPLETE

**Goal**: Provide prompt templates that guide users through analytics workflows

**Independent Test**: Request "analytics workflow" prompt - should receive guided steps

### Tests for User Story 6

- [x] T121 [P] [US6] Write test_analytics_workflow_prompt_registered in mp-mcp-server/tests/unit/test_prompts.py
- [x] T122 [P] [US6] Write test_funnel_analysis_prompt_registered in mp-mcp-server/tests/unit/test_prompts.py
- [x] T123 [P] [US6] Write test_retention_analysis_prompt_registered in mp-mcp-server/tests/unit/test_prompts.py
- [x] T124 [P] [US6] Write test_local_analysis_workflow_prompt_registered in mp-mcp-server/tests/unit/test_prompts.py
- [x] T125 [P] [US6] Write test_analytics_workflow_returns_messages in mp-mcp-server/tests/unit/test_prompts.py

### Implementation for User Story 6

- [x] T126 [US6] Implement analytics_workflow prompt in mp-mcp-server/src/mp_mcp_server/prompts.py
- [x] T127 [US6] Implement funnel_analysis prompt in mp-mcp-server/src/mp_mcp_server/prompts.py
- [x] T128 [US6] Implement retention_analysis prompt in mp-mcp-server/src/mp_mcp_server/prompts.py
- [x] T129 [US6] Implement local_analysis_workflow prompt in mp-mcp-server/src/mp_mcp_server/prompts.py
- [x] T130 [US6] Register prompts in server.py imports in mp-mcp-server/src/mp_mcp_server/server.py
- [x] T131 [US6] Run prompt tests and verify all pass: just test -k test_prompts

**Checkpoint**: All user stories complete with guided workflows ✅

---

## Phase 9: CLI Entry Point ✅ COMPLETE

**Purpose**: Command-line interface to run the server

### Tests for CLI

- [x] T132 [P] Write test_cli_runs_server in mp-mcp-server/tests/unit/test_cli.py
- [x] T133 [P] Write test_cli_accepts_account_option in mp-mcp-server/tests/unit/test_cli.py
- [x] T134 [P] Write test_cli_accepts_transport_option in mp-mcp-server/tests/unit/test_cli.py
- [x] T135 [P] Write test_cli_accepts_port_option in mp-mcp-server/tests/unit/test_cli.py

### Implementation for CLI

- [x] T136 Implement CLI entry point with argparse in mp-mcp-server/src/mp_mcp_server/cli.py
- [x] T137 Verify entry point works: mp-mcp-server --help
- [x] T138 Run CLI tests and verify all pass: just test -k test_cli

---

## Phase 10: Integration Testing ✅ COMPLETE

**Purpose**: End-to-end validation with FastMCP in-memory client

- [x] T139 [P] Write test_discovery_workflow integration test in mp-mcp-server/tests/integration/test_server_integration.py
- [x] T140 [P] Write test_fetch_and_sql_workflow integration test in mp-mcp-server/tests/integration/test_server_integration.py
- [x] T141 [P] Write test_segmentation_workflow integration test in mp-mcp-server/tests/integration/test_server_integration.py
- [x] T142 [P] Write test_resource_access integration test in mp-mcp-server/tests/integration/test_server_integration.py
- [x] T143 Run all integration tests: just test -k test_server_integration
- [x] T144 Run full test suite: just test mp-mcp-server/tests/

---

## Phase 11: Polish & Documentation ✅ COMPLETE

**Purpose**: Final polish and documentation

- [x] T145 [P] Create README.md with installation and usage in mp-mcp-server/README.md
- [x] T146 [P] Create claude_desktop_config.json example in mp-mcp-server/claude_desktop_config.json
- [x] T147 Verify quickstart.md steps work end-to-end per specs/020-mcp-server/quickstart.md
- [x] T148 Run full quality checks: ruff check/format pass
- [ ] T149 Verify coverage meets 90% threshold: just test-cov mp-mcp-server/tests/
- [x] T150 [P] Add type stubs or py.typed marker in mp-mcp-server/src/mp_mcp_server/py.typed

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - BLOCKS all user stories
- **User Stories (Phase 3-8)**: All depend on Foundational phase completion
  - US1 and US2 can proceed in parallel (both P1)
  - US3 and US4 can proceed in parallel (both P2)
  - US5 and US6 can proceed in parallel (both P3)
- **CLI (Phase 9)**: Depends on all tools being registered
- **Integration (Phase 10)**: Depends on CLI and all tools complete
- **Polish (Phase 11)**: Depends on all user stories complete

### User Story Dependencies

- **User Story 1 (P1)**: Can start after Foundational (Phase 2) - No dependencies
- **User Story 2 (P1)**: Can start after Foundational (Phase 2) - No dependencies
- **User Story 3 (P2)**: Can start after Foundational (Phase 2) - Independent of US1/US2
- **User Story 4 (P2)**: Logically after US3 (needs fetched data), but tools are independent
- **User Story 5 (P3)**: Can start after Foundational (Phase 2) - Resources are independent
- **User Story 6 (P3)**: Can start after Foundational (Phase 2) - Prompts are independent

### Within Each User Story

- Tests MUST be written and FAIL before implementation
- Implement tools in order listed
- Register tools in server.py after implementation
- Run tests to verify before moving to next story

### Parallel Opportunities

- All Setup tasks marked [P] can run in parallel
- All Foundational tests marked [P] can run in parallel
- All tests for a user story marked [P] can run in parallel
- US1 and US2 can be developed in parallel (both P1)
- US3 and US4 can be developed in parallel (both P2)
- US5 and US6 can be developed in parallel (both P3)

---

## Parallel Example: User Story 1 Tests

```bash
# Launch all tests for User Story 1 together:
# T016-T025 can all be written in parallel (different test functions)
```

## Parallel Example: User Story 2 Implementation

```bash
# These tools can be implemented in parallel (separate functions):
# T050: segmentation tool
# T051: funnel tool
# T052: retention tool
# T053: jql tool
```

---

## Implementation Strategy

### MVP First (User Stories 1 & 2 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (CRITICAL - blocks all stories)
3. Complete Phase 3: User Story 1 (Schema Discovery)
4. **STOP and VALIDATE**: Test discovery independently
5. Complete Phase 4: User Story 2 (Live Analytics)
6. **STOP and VALIDATE**: Test live queries independently
7. Deploy/demo if ready - This is the MVP!

### Incremental Delivery

1. Complete Setup + Foundational → Foundation ready
2. Add User Story 1 → Test independently → MVP Schema Discovery
3. Add User Story 2 → Test independently → MVP Live Queries
4. Add User Story 3 → Test independently → Data Fetching
5. Add User Story 4 → Test independently → Local SQL Analysis
6. Add User Story 5 → Test independently → Session Resources
7. Add User Story 6 → Test independently → Guided Workflows
8. Complete CLI, Integration, Polish → Production Ready

### Parallel Team Strategy

With multiple developers:

1. Team completes Setup + Foundational together
2. Once Foundational is done:
   - Developer A: User Story 1 (Schema Discovery)
   - Developer B: User Story 2 (Live Analytics)
3. After US1/US2:
   - Developer A: User Story 3 (Fetch)
   - Developer B: User Story 4 (Local SQL)
4. After US3/US4:
   - Developer A: User Story 5 (Resources)
   - Developer B: User Story 6 (Prompts)
5. Team completes CLI, Integration, Polish together

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Each user story should be independently completable and testable
- Verify tests fail before implementing (strict TDD per CLAUDE.md)
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
- **Actual implementation**: 31 tools (8 discovery + 9 live query + 4 fetch + 10 local), 6 resources, 4 prompts
- 68 tests: 64 unit + 4 integration
