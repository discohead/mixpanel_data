# Tasks: CLI Application

**Input**: Design documents from `/specs/010-cli-application/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Tests**: Tests are generated for integration testing of CLI commands.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

- **Single project**: `src/mixpanel_data/cli/` for CLI code, `tests/` for tests
- Based on plan.md structure for existing mixpanel_data library

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Create CLI package structure and shared utilities

- [ ] T001 Create CLI package directory structure at src/mixpanel_data/cli/
- [ ] T002 [P] Create CLI package __init__.py at src/mixpanel_data/cli/__init__.py
- [ ] T003 [P] Create commands package __init__.py at src/mixpanel_data/cli/commands/__init__.py
- [ ] T004 Create main.py with Typer app entry point and global options callback at src/mixpanel_data/cli/main.py
- [ ] T005 [P] Create utils.py with ExitCode enum and handle_errors decorator at src/mixpanel_data/cli/utils.py
- [ ] T006 [P] Create formatters.py with format_json, format_table, format_csv, format_jsonl, format_plain at src/mixpanel_data/cli/formatters.py
- [ ] T007 Add signal handler for SIGINT (Ctrl+C) returning exit code 130 in src/mixpanel_data/cli/main.py
- [ ] T008 Create output_result helper function that routes to appropriate formatter in src/mixpanel_data/cli/utils.py
- [ ] T009 Create get_workspace and get_config lazy initialization helpers in src/mixpanel_data/cli/utils.py
- [ ] T010 Verify entry point mp = mixpanel_data.cli.main:app in pyproject.toml

**Checkpoint**: CLI infrastructure ready - `mp --help` should work with no subcommands

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before user story commands can be added

**⚠️ CRITICAL**: Formatters and error handling must work before any command implementation

- [ ] T011 Implement Console instances (stdout and stderr) in src/mixpanel_data/cli/utils.py
- [ ] T012 [P] Implement exception-to-exit-code mapping for all MixpanelDataError subtypes in src/mixpanel_data/cli/utils.py
- [ ] T013 [P] Create test fixtures for CLI testing with mock Workspace and ConfigManager at tests/unit/cli/conftest.py
- [ ] T014 [P] Unit test for format_json in tests/unit/cli/test_formatters.py
- [ ] T015 [P] Unit test for format_table in tests/unit/cli/test_formatters.py
- [ ] T016 [P] Unit test for format_csv in tests/unit/cli/test_formatters.py
- [ ] T017 [P] Unit test for format_jsonl in tests/unit/cli/test_formatters.py
- [ ] T018 [P] Unit test for format_plain in tests/unit/cli/test_formatters.py
- [ ] T019 Unit test for handle_errors decorator exit code mapping in tests/unit/cli/test_utils.py
- [ ] T020 Verify `mp --help` displays global options (--account, --format, --quiet, --verbose)

**Checkpoint**: Foundation ready - formatters tested, error handling tested, user story implementation can begin

---

## Phase 3: User Story 1 - Configure Account Credentials (Priority: P1) 🎯 MVP

**Goal**: Enable developers to securely store and manage Mixpanel service account credentials

**Independent Test**: Run `mp auth add`, `mp auth list`, `mp auth remove` cycle to verify account CRUD

### Implementation for User Story 1

- [ ] T021 [US1] Create auth command group scaffold at src/mixpanel_data/cli/commands/auth.py
- [ ] T022 [US1] Register auth_app subcommand in main.py at src/mixpanel_data/cli/main.py
- [ ] T023 [US1] Implement `mp auth list` command delegating to ConfigManager.list_accounts() in src/mixpanel_data/cli/commands/auth.py
- [ ] T024 [US1] Implement `mp auth add` command with --username, --project, --region, --default, --interactive, --secret-stdin options (secret via secure prompt, MP_SECRET env, or stdin) in src/mixpanel_data/cli/commands/auth.py
- [ ] T025 [US1] Implement `mp auth remove` command with --force option and confirmation prompt in src/mixpanel_data/cli/commands/auth.py
- [ ] T026 [US1] Implement `mp auth switch` command delegating to ConfigManager.set_default() in src/mixpanel_data/cli/commands/auth.py
- [ ] T027 [US1] Implement `mp auth show` command with redacted secret display in src/mixpanel_data/cli/commands/auth.py
- [ ] T028 [US1] Implement `mp auth test` command delegating to Workspace.test_credentials() in src/mixpanel_data/cli/commands/auth.py

### Tests for User Story 1

- [ ] T029 [P] [US1] Integration test for auth list command in tests/integration/cli/test_auth_commands.py
- [ ] T030 [P] [US1] Integration test for auth add command in tests/integration/cli/test_auth_commands.py
- [ ] T031 [P] [US1] Integration test for auth remove command in tests/integration/cli/test_auth_commands.py
- [ ] T032 [P] [US1] Integration test for auth switch command in tests/integration/cli/test_auth_commands.py
- [ ] T033 [P] [US1] Integration test for auth show command in tests/integration/cli/test_auth_commands.py
- [ ] T034 [P] [US1] Integration test for auth test command in tests/integration/cli/test_auth_commands.py

**Checkpoint**: Auth commands complete - users can manage credentials via CLI

---

## Phase 4: User Story 2 - Fetch and Store Events Locally (Priority: P1) 🎯 MVP

**Goal**: Enable fetching Mixpanel events into local DuckDB storage for SQL analysis

**Independent Test**: Run `mp fetch events --from 2024-01-01 --to 2024-01-07` and verify table creation

### Implementation for User Story 2

- [ ] T035 [US2] Create fetch command group scaffold at src/mixpanel_data/cli/commands/fetch.py
- [ ] T036 [US2] Register fetch_app subcommand in main.py at src/mixpanel_data/cli/main.py
- [ ] T037 [US2] Implement `mp fetch events` command with --from, --to, --name, --events, --where, --replace options in src/mixpanel_data/cli/commands/fetch.py
- [ ] T038 [US2] Add Rich progress bar integration for fetch events with stderr output in src/mixpanel_data/cli/commands/fetch.py
- [ ] T039 [US2] Implement FetchResult output formatting (JSON shows table, rows, duration) in src/mixpanel_data/cli/commands/fetch.py

### Tests for User Story 2

- [ ] T040 [P] [US2] Integration test for fetch events command in tests/integration/cli/test_fetch_commands.py
- [ ] T041 [P] [US2] Integration test for fetch events with --replace option in tests/integration/cli/test_fetch_commands.py
- [ ] T042 [P] [US2] Integration test for fetch events table-exists error in tests/integration/cli/test_fetch_commands.py

**Checkpoint**: Event fetching complete - users can download events to local storage

---

## Phase 5: User Story 3 - Query Local Data with SQL (Priority: P1) 🎯 MVP

**Goal**: Enable SQL querying of locally stored Mixpanel data

**Independent Test**: Run `mp query sql "SELECT COUNT(*) FROM events"` against fetched data

### Implementation for User Story 3

- [ ] T043 [US3] Create query command group scaffold at src/mixpanel_data/cli/commands/query.py
- [ ] T044 [US3] Register query_app subcommand in main.py at src/mixpanel_data/cli/main.py
- [ ] T045 [US3] Implement `mp query sql` command with query argument and --file option in src/mixpanel_data/cli/commands/query.py
- [ ] T046 [US3] Implement --scalar option for single-value output in src/mixpanel_data/cli/commands/query.py
- [ ] T047 [US3] Handle SQL errors with appropriate exit code 3 in src/mixpanel_data/cli/commands/query.py
- [ ] T048 [US3] Handle table-not-found errors with exit code 4 in src/mixpanel_data/cli/commands/query.py

### Tests for User Story 3

- [ ] T049 [P] [US3] Integration test for query sql command in tests/integration/cli/test_query_commands.py
- [ ] T050 [P] [US3] Integration test for query sql --scalar option in tests/integration/cli/test_query_commands.py
- [ ] T051 [P] [US3] Integration test for query sql --file option in tests/integration/cli/test_query_commands.py
- [ ] T052 [P] [US3] Integration test for query sql error handling in tests/integration/cli/test_query_commands.py

**Checkpoint**: SQL querying complete - MVP is functional (auth + fetch + sql)

---

## Phase 6: User Story 4 - Run Live Analytics Queries (Priority: P2)

**Goal**: Enable live Mixpanel API queries (segmentation, funnel, retention, etc.)

**Independent Test**: Run `mp query segmentation --event "Signup" --from 2024-01-01 --to 2024-01-31`

### Implementation for User Story 4

- [ ] T053 [US4] Implement `mp query segmentation` command with --event, --from, --to, --on, --unit, --where in src/mixpanel_data/cli/commands/query.py
- [ ] T054 [US4] Implement `mp query funnel` command with funnel_id arg and --from, --to, --unit, --on in src/mixpanel_data/cli/commands/query.py
- [ ] T055 [US4] Implement `mp query retention` command with --born, --return, --from, --to and additional options in src/mixpanel_data/cli/commands/query.py
- [ ] T056 [US4] Implement `mp query jql` command with file arg and --script, --param options in src/mixpanel_data/cli/commands/query.py
- [ ] T057 [US4] Implement `mp query event-counts` command with --events, --from, --to, --unit, --type in src/mixpanel_data/cli/commands/query.py
- [ ] T058 [US4] Implement `mp query property-counts` command with --event, --property, --from, --to options in src/mixpanel_data/cli/commands/query.py
- [ ] T059 [US4] Implement `mp query activity-feed` command with --users, --from, --to options in src/mixpanel_data/cli/commands/query.py
- [ ] T060 [US4] Implement `mp query insights` command with bookmark_id argument in src/mixpanel_data/cli/commands/query.py
- [ ] T061 [US4] Implement `mp query frequency` command with --from, --to, --unit, --addiction-unit, --event in src/mixpanel_data/cli/commands/query.py
- [ ] T062 [US4] Implement `mp query segmentation-numeric` command with --event, --on, --from, --to options in src/mixpanel_data/cli/commands/query.py
- [ ] T063 [US4] Implement `mp query segmentation-sum` command with --event, --on, --from, --to options in src/mixpanel_data/cli/commands/query.py
- [ ] T064 [US4] Implement `mp query segmentation-average` command with --event, --on, --from, --to options in src/mixpanel_data/cli/commands/query.py
- [ ] T065 [US4] Handle rate limit errors with exit code 5 across all live query commands in src/mixpanel_data/cli/commands/query.py

### Tests for User Story 4

- [ ] T066 [P] [US4] Integration test for query segmentation command in tests/integration/cli/test_query_commands.py
- [ ] T067 [P] [US4] Integration test for query funnel command in tests/integration/cli/test_query_commands.py
- [ ] T068 [P] [US4] Integration test for query retention command in tests/integration/cli/test_query_commands.py
- [ ] T069 [P] [US4] Integration test for query jql command in tests/integration/cli/test_query_commands.py
- [ ] T070 [P] [US4] Integration test for query event-counts command in tests/integration/cli/test_query_commands.py
- [ ] T071 [P] [US4] Integration test for remaining live query commands in tests/integration/cli/test_query_commands.py

**Checkpoint**: Live queries complete - all 13 live query commands functional

---

## Phase 7: User Story 5 - Discover Schema and Metadata (Priority: P2)

**Goal**: Enable discovery of Mixpanel project schema (events, properties, funnels, cohorts)

**Independent Test**: Run `mp inspect events` to list all event names

### Implementation for User Story 5

- [ ] T072 [US5] Create inspect command group scaffold at src/mixpanel_data/cli/commands/inspect.py
- [ ] T073 [US5] Register inspect_app subcommand in main.py at src/mixpanel_data/cli/main.py
- [ ] T074 [US5] Implement `mp inspect events` command delegating to Workspace.events() in src/mixpanel_data/cli/commands/inspect.py
- [ ] T075 [US5] Implement `mp inspect properties` command with --event option in src/mixpanel_data/cli/commands/inspect.py
- [ ] T076 [US5] Implement `mp inspect values` command with --property, --event, --limit options in src/mixpanel_data/cli/commands/inspect.py
- [ ] T077 [US5] Implement `mp inspect funnels` command delegating to Workspace.funnels() in src/mixpanel_data/cli/commands/inspect.py
- [ ] T078 [US5] Implement `mp inspect cohorts` command delegating to Workspace.cohorts() in src/mixpanel_data/cli/commands/inspect.py
- [ ] T079 [US5] Implement `mp inspect top-events` command with --type, --limit options in src/mixpanel_data/cli/commands/inspect.py

### Tests for User Story 5

- [ ] T080 [P] [US5] Integration test for inspect events command in tests/integration/cli/test_inspect_commands.py
- [ ] T081 [P] [US5] Integration test for inspect properties command in tests/integration/cli/test_inspect_commands.py
- [ ] T082 [P] [US5] Integration test for inspect values command in tests/integration/cli/test_inspect_commands.py
- [ ] T083 [P] [US5] Integration test for inspect funnels and cohorts commands in tests/integration/cli/test_inspect_commands.py

**Checkpoint**: Schema discovery complete - 6 discovery commands functional

---

## Phase 8: User Story 6 - Inspect Local Database State (Priority: P2)

**Goal**: Enable inspection of local workspace state (tables, schemas, info)

**Independent Test**: Run `mp inspect info` to see workspace summary

### Implementation for User Story 6

- [ ] T084 [US6] Implement `mp inspect info` command delegating to Workspace.info() in src/mixpanel_data/cli/commands/inspect.py
- [ ] T085 [US6] Implement `mp inspect tables` command delegating to Workspace.tables() in src/mixpanel_data/cli/commands/inspect.py
- [ ] T086 [US6] Implement `mp inspect schema` command with --table option and optional --sample in src/mixpanel_data/cli/commands/inspect.py
- [ ] T087 [US6] Implement `mp inspect drop` command with --table and --force options with confirmation in src/mixpanel_data/cli/commands/inspect.py

### Tests for User Story 6

- [ ] T088 [P] [US6] Integration test for inspect info command in tests/integration/cli/test_inspect_commands.py
- [ ] T089 [P] [US6] Integration test for inspect tables command in tests/integration/cli/test_inspect_commands.py
- [ ] T090 [P] [US6] Integration test for inspect schema command in tests/integration/cli/test_inspect_commands.py
- [ ] T091 [P] [US6] Integration test for inspect drop command in tests/integration/cli/test_inspect_commands.py

**Checkpoint**: Local inspection complete - all 10 inspect commands functional

---

## Phase 9: User Story 7 - Fetch User Profiles (Priority: P3)

**Goal**: Enable fetching Mixpanel user profiles into local storage

**Independent Test**: Run `mp fetch profiles` and query with SQL

### Implementation for User Story 7

- [ ] T092 [US7] Implement `mp fetch profiles` command with --name, --where, --replace options in src/mixpanel_data/cli/commands/fetch.py
- [ ] T093 [US7] Add Rich progress bar integration for fetch profiles in src/mixpanel_data/cli/commands/fetch.py

### Tests for User Story 7

- [ ] T094 [P] [US7] Integration test for fetch profiles command in tests/integration/cli/test_fetch_commands.py

**Checkpoint**: Profile fetching complete - both fetch commands functional

---

## Phase 10: User Story 8 - Control Output Format (Priority: P3)

**Goal**: Enable users to control output format (json, table, csv, jsonl, plain)

**Independent Test**: Run same command with different --format values, verify output validity

### Implementation for User Story 8

- [ ] T095 [US8] Verify all auth commands support --format option in src/mixpanel_data/cli/commands/auth.py
- [ ] T096 [US8] Verify all inspect commands support --format option in src/mixpanel_data/cli/commands/inspect.py
- [ ] T097 [US8] Verify all query commands support --format option in src/mixpanel_data/cli/commands/query.py
- [ ] T098 [US8] Verify plain format outputs one item per line for list results in src/mixpanel_data/cli/formatters.py
- [ ] T099 [US8] Verify CSV format includes headers and is valid CSV in src/mixpanel_data/cli/formatters.py

### Tests for User Story 8

- [ ] T100 [P] [US8] Integration test for --format json across commands in tests/integration/cli/test_format_options.py
- [ ] T101 [P] [US8] Integration test for --format table across commands in tests/integration/cli/test_format_options.py
- [ ] T102 [P] [US8] Integration test for --format csv across commands in tests/integration/cli/test_format_options.py
- [ ] T103 [P] [US8] Integration test for --format jsonl across commands in tests/integration/cli/test_format_options.py

**Checkpoint**: Output formats complete - all 5 formats work across all commands

---

## Phase 11: User Story 9 - Use Different Accounts Per-Command (Priority: P3)

**Goal**: Enable --account global option to override default account

**Independent Test**: Run `mp --account staging inspect events` with non-default account

### Implementation for User Story 9

- [ ] T104 [US9] Verify get_workspace helper respects --account from context in src/mixpanel_data/cli/utils.py
- [ ] T105 [US9] Add error handling for invalid account name with available accounts list in src/mixpanel_data/cli/utils.py
- [ ] T106 [US9] Verify --account option propagates correctly to all command groups in src/mixpanel_data/cli/main.py

### Tests for User Story 9

- [ ] T107 [P] [US9] Integration test for --account option with valid account in tests/integration/cli/test_global_options.py
- [ ] T108 [P] [US9] Integration test for --account option with invalid account in tests/integration/cli/test_global_options.py

**Checkpoint**: Multi-account support complete - --account works on all commands

---

## Phase 12: Polish & Cross-Cutting Concerns

**Purpose**: Improvements that affect multiple user stories

- [ ] T109 [P] Add comprehensive help text with examples to all commands
- [ ] T110 [P] Add --version option to main app in src/mixpanel_data/cli/main.py
- [ ] T111 [P] Implement shell completion script generation (bash, zsh, fish) in src/mixpanel_data/cli/main.py
- [ ] T112 [P] Add NO_COLOR environment variable support in src/mixpanel_data/cli/utils.py
- [ ] T113 [P] Verify --quiet suppresses progress on all fetch commands
- [ ] T114 [P] Verify --verbose enables debug output on all commands
- [ ] T115 Run full integration test suite: just test -k cli
- [ ] T116 Validate quickstart.md examples work end-to-end
- [ ] T117 Run ruff check and mypy on all CLI code
- [ ] T118 Final verification: all 31 commands documented in `mp --help` tree

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - BLOCKS all user stories
- **User Stories (Phases 3-11)**: All depend on Foundational phase completion
  - User stories can then proceed in parallel (if staffed)
  - Or sequentially in priority order (P1 → P2 → P3)
- **Polish (Phase 12)**: Depends on all user stories being complete

### User Story Dependencies

| Story | Priority | Depends On | Can Start After |
|-------|----------|------------|-----------------|
| US1: Auth | P1 | Foundational | Phase 2 |
| US2: Fetch Events | P1 | Foundational | Phase 2 |
| US3: Query SQL | P1 | Foundational | Phase 2 |
| US4: Live Queries | P2 | US3 (query group) | Phase 5 |
| US5: Schema Discovery | P2 | Foundational | Phase 2 |
| US6: Local Inspection | P2 | Foundational | Phase 2 |
| US7: Fetch Profiles | P3 | US2 (fetch group) | Phase 4 |
| US8: Output Formats | P3 | All commands exist | After Phase 8 |
| US9: Multi-Account | P3 | US1 (auth exists) | Phase 3 |

### Within Each User Story

- Command group scaffold before individual commands
- Register subcommand in main.py before implementing commands
- Implement commands before tests
- Story complete before moving to next priority

### Parallel Opportunities

- All Setup tasks marked [P] can run in parallel
- All Foundational test tasks marked [P] can run in parallel
- Once Phase 2 completes:
  - US1, US2, US3, US5, US6 can start in parallel (different command groups)
- All integration tests within a story marked [P] can run in parallel

---

## Parallel Example: Phase 1 Setup

```bash
# These tasks target different files - run in parallel:
T002: Create CLI package __init__.py at src/mixpanel_data/cli/__init__.py
T003: Create commands package __init__.py at src/mixpanel_data/cli/commands/__init__.py
T005: Create utils.py with ExitCode enum at src/mixpanel_data/cli/utils.py
T006: Create formatters.py at src/mixpanel_data/cli/formatters.py
```

## Parallel Example: User Story 1 Tests

```bash
# All US1 tests target the same test file but test independent commands:
T029: Integration test for auth list command
T030: Integration test for auth add command
T031: Integration test for auth remove command
T032: Integration test for auth switch command
T033: Integration test for auth show command
T034: Integration test for auth test command
```

---

## Implementation Strategy

### MVP First (User Stories 1-3 Only)

1. Complete Phase 1: Setup (T001-T010)
2. Complete Phase 2: Foundational (T011-T020)
3. Complete Phase 3: User Story 1 - Auth (T021-T034)
4. Complete Phase 4: User Story 2 - Fetch Events (T035-T042)
5. Complete Phase 5: User Story 3 - Query SQL (T043-T052)
6. **STOP and VALIDATE**: Test MVP workflow (auth add → fetch events → query sql)
7. Deploy/demo if ready

### Incremental Delivery

| Milestone | Stories Complete | Commands Available |
|-----------|------------------|-------------------|
| MVP | US1, US2, US3 | 9 (auth 6, fetch 1, query 1, + groups) |
| Beta | + US4, US5, US6 | 29 (+ 13 live queries, 10 inspect) |
| Full | + US7, US8, US9 | 31 (all commands + all formats) |

### Task Count Summary

| Phase | Tasks | Story |
|-------|-------|-------|
| 1. Setup | 10 | - |
| 2. Foundational | 10 | - |
| 3. US1 Auth | 14 | P1 |
| 4. US2 Fetch Events | 8 | P1 |
| 5. US3 Query SQL | 10 | P1 |
| 6. US4 Live Queries | 19 | P2 |
| 7. US5 Schema Discovery | 12 | P2 |
| 8. US6 Local Inspection | 8 | P2 |
| 9. US7 Fetch Profiles | 3 | P3 |
| 10. US8 Output Formats | 9 | P3 |
| 11. US9 Multi-Account | 5 | P3 |
| 12. Polish | 10 | - |
| **Total** | **118** | - |

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Each user story should be independently completable and testable
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
- Commands delegate to Workspace/ConfigManager - no business logic in CLI
- All output goes through formatters for consistency
