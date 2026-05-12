# Tasks: Storage Engine

**Input**: Design documents from `/specs/003-storage-engine/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: Included - StorageEngine is a foundational component requiring comprehensive test coverage (SC-007: 90%+ coverage target)

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

- Single project structure: `src/mixpanel_data/`, `tests/` at repository root
- Implementation: `src/mixpanel_data/_internal/storage.py` (new)
- Type extensions: `src/mixpanel_data/types.py` (extend existing)
- Tests: `tests/unit/test_storage.py` (new), `tests/integration/test_storage_integration.py` (new)

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and dependency verification

- [X] T001 Verify DuckDB 1.0+ installed in project dependencies (pyproject.toml)
- [X] T002 Verify pandas 2.0+ installed in project dependencies (pyproject.toml)
- [X] T003 [P] Verify existing exception classes available (TableExistsError, TableNotFoundError, QueryError in src/mixpanel_data/exceptions.py)
- [X] T004 Create test fixtures directory structure (tests/unit/, tests/integration/ if not exists)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core data structures and base class that MUST be complete before ANY user story can be implemented

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [X] T005 [P] Add TableMetadata dataclass to src/mixpanel_data/types.py (frozen, with type, fetched_at, from_date, to_date, filter_events, filter_where)
- [X] T006 [P] Add TableInfo dataclass to src/mixpanel_data/types.py (frozen, with name, type, row_count, fetched_at)
- [X] T007 [P] Add TableSchema and ColumnInfo dataclasses to src/mixpanel_data/types.py (frozen)
- [X] T008 Create src/mixpanel_data/_internal/storage.py with StorageEngine class skeleton (imports, class definition, __init__ signature)
- [X] T009 Add StorageEngine to src/mixpanel_data/_internal/__init__.py exports (if needed for internal imports)

**Checkpoint**: Foundation ready - data structures defined, base class exists. User story implementation can now begin in parallel.

---

## Phase 3: User Story 1 - Persistent Data Storage (Priority: P1) 🎯 MVP

**Goal**: Enable library users to create and reopen persistent database files for repeated querying across sessions

**Independent Test**: Create database at path, insert data, close connection, reopen database file, verify data queryable with exact same values

### Tests for User Story 1

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [X] T010 [P] [US1] Unit test for __init__ with explicit path in tests/unit/test_storage.py
- [X] T011 [P] [US1] Unit test for default path resolution in tests/unit/test_storage.py
- [X] T012 [P] [US1] Unit test for context manager protocol in tests/unit/test_storage.py
- [X] T013 [P] [US1] Integration test for session persistence in tests/integration/test_storage_integration.py (create, close, reopen, query)

### Implementation for User Story 1

- [X] T014 [US1] Implement __init__(path) in src/mixpanel_data/_internal/storage.py (database file creation, DuckDB connection)
- [ ] T015 [US1] Implement default path resolution (~/.mixpanel_data/{project_id}.db) in src/mixpanel_data/_internal/storage.py (deferred - project_id not available in __init__)
- [X] T016 [US1] Implement close() method in src/mixpanel_data/_internal/storage.py
- [X] T017 [US1] Implement context manager protocol (__enter__, __exit__) in src/mixpanel_data/_internal/storage.py
- [X] T018 [US1] Implement path property in src/mixpanel_data/_internal/storage.py
- [X] T019 [US1] Implement connection property (DuckDB connection escape hatch) in src/mixpanel_data/_internal/storage.py
- [X] T020 [US1] Add error handling for invalid paths and permission issues in src/mixpanel_data/_internal/storage.py

**Checkpoint**: At this point, users can create persistent databases, close them, and reopen them. Database lifecycle management is fully functional.

---

## Phase 4: User Story 2 - Memory-Efficient Data Ingestion (Priority: P1)

**Goal**: Enable streaming ingestion of large datasets (1M+ events) with constant memory usage (<500MB)

**Independent Test**: Create generator yielding 1M+ event dictionaries, pass to create_events_table(), verify all events inserted with memory usage staying constant

### Tests for User Story 2

- [X] T021 [P] [US2] Unit test for create_events_table batch insert logic in tests/unit/test_storage.py
- [X] T022 [P] [US2] Unit test for create_profiles_table batch insert logic in tests/unit/test_storage.py
- [X] T023 [P] [US2] Unit test for progress callback invocation in tests/unit/test_storage.py
- [X] T024 [P] [US2] Integration test for large dataset ingestion (100K events minimum) in tests/integration/test_storage_integration.py
- [X] T025 [P] [US2] Memory profiling test for 1M events (<500MB constraint) in tests/integration/test_storage_integration.py

### Implementation for User Story 2

- [X] T026 [US2] Implement _create_events_table_schema() helper in src/mixpanel_data/_internal/storage.py (CREATE TABLE events with schema from data-model.md)
- [X] T027 [US2] Implement _create_profiles_table_schema() helper in src/mixpanel_data/_internal/storage.py (CREATE TABLE profiles with schema from data-model.md)
- [X] T028 [US2] Implement _create_metadata_table() helper in src/mixpanel_data/_internal/storage.py (CREATE TABLE _metadata if not exists)
- [X] T029 [US2] Implement _batch_insert_events() helper in src/mixpanel_data/_internal/storage.py (streaming batch insert with executemany, batch_size=1000-5000)
- [X] T030 [US2] Implement _batch_insert_profiles() helper in src/mixpanel_data/_internal/storage.py (streaming batch insert with executemany)
- [X] T031 [US2] Implement create_events_table(name, data, metadata, progress_callback) in src/mixpanel_data/_internal/storage.py
- [X] T032 [US2] Implement create_profiles_table(name, data, metadata, progress_callback) in src/mixpanel_data/_internal/storage.py
- [X] T033 [US2] Implement _record_metadata(table_name, metadata, row_count) helper in src/mixpanel_data/_internal/storage.py (INSERT INTO _metadata)
- [X] T034 [US2] Add validation for table name (alphanumeric + underscore, no leading underscore) in src/mixpanel_data/_internal/storage.py
- [X] T035 [US2] Add validation for required fields in event/profile dictionaries in src/mixpanel_data/_internal/storage.py

**Checkpoint**: At this point, users can ingest millions of events/profiles with constant memory usage. Streaming ingestion is fully functional with metadata tracking.

---

## Phase 5: User Story 3 - Ephemeral Analysis Workflows (Priority: P1)

**Goal**: Enable temporary databases that auto-delete on close for one-off analysis without manual cleanup

**Independent Test**: Create ephemeral StorageEngine, insert data, query it, close it, verify temporary file deleted (even on exception)

### Tests for User Story 3

- [X] T036 [P] [US3] Unit test for ephemeral() classmethod in tests/unit/test_storage.py
- [X] T037 [P] [US3] Unit test for cleanup() method in tests/unit/test_storage.py
- [X] T038 [P] [US3] Integration test for ephemeral cleanup on normal exit in tests/integration/test_storage_integration.py
- [X] T039 [P] [US3] Integration test for ephemeral cleanup on exception exit in tests/integration/test_storage_integration.py
- [X] T040 [P] [US3] Integration test for ephemeral cleanup via context manager in tests/integration/test_storage_integration.py

### Implementation for User Story 3

- [X] T041 [US3] Implement ephemeral() classmethod in src/mixpanel_data/_internal/storage.py (tempfile.NamedTemporaryFile with delete=False)
- [X] T042 [US3] Implement _cleanup_ephemeral() helper in src/mixpanel_data/_internal/storage.py (close connection, delete temp file and WAL)
- [X] T043 [US3] Implement cleanup() method (alias for close) in src/mixpanel_data/_internal/storage.py
- [X] T044 [US3] Register atexit handler in __init__ for ephemeral databases in src/mixpanel_data/_internal/storage.py
- [X] T045 [US3] Update close() to handle ephemeral cleanup path in src/mixpanel_data/_internal/storage.py
- [X] T046 [US3] Update __exit__ to ensure cleanup is called in src/mixpanel_data/_internal/storage.py
- [X] T047 [US3] Implement open_existing(path) classmethod in src/mixpanel_data/_internal/storage.py (open existing database, raise FileNotFoundError if missing)

**Checkpoint**: At this point, users can create ephemeral databases that auto-cleanup 100% reliably (normal exit, exceptions, atexit). Temporary analysis workflows are fully functional.

---

## Phase 6: User Story 4 - Flexible Query Execution (Priority: P2)

**Goal**: Enable querying stored data in multiple formats (DataFrame, scalar, rows, raw relation) for different use cases

**Independent Test**: Create table with known data, execute same query via each method (execute_df, execute_scalar, execute_rows, execute), verify correct results in expected format

### Tests for User Story 4

- [X] T048 [P] [US4] Unit test for execute() returning DuckDB relation in tests/unit/test_storage_us4.py
- [X] T049 [P] [US4] Unit test for execute_df() returning DataFrame in tests/unit/test_storage_us4.py
- [X] T050 [P] [US4] Unit test for execute_scalar() returning single value in tests/unit/test_storage_us4.py
- [X] T051 [P] [US4] Unit test for execute_rows() returning list of tuples in tests/unit/test_storage_us4.py
- [X] T052 [P] [US4] Unit test for QueryError wrapping on SQL errors in tests/unit/test_storage_us4.py

### Implementation for User Story 4

- [X] T053 [P] [US4] Implement execute(sql) in src/mixpanel_data/_internal/storage.py (return DuckDB relation)
- [X] T054 [P] [US4] Implement execute_df(sql) in src/mixpanel_data/_internal/storage.py (return pandas DataFrame via .df())
- [X] T055 [P] [US4] Implement execute_scalar(sql) in src/mixpanel_data/_internal/storage.py (return fetchone()[0])
- [X] T056 [P] [US4] Implement execute_rows(sql) in src/mixpanel_data/_internal/storage.py (return fetchall())
- [X] T057 [US4] Add QueryError wrapping for all execute methods in src/mixpanel_data/_internal/storage.py (catch duckdb.Error, wrap with query text and error details)
- [X] T058 [US4] Add docstrings with usage examples for all execute methods in src/mixpanel_data/_internal/storage.py

**Checkpoint**: At this point, users can query data in any format needed (DataFrame for data science, scalar for counts, rows for iteration, raw relation for advanced DuckDB features). Query execution is fully flexible.

---

## Phase 7: User Story 5 - Database Introspection (Priority: P2)

**Goal**: Enable discovery of available tables, schemas, and metadata without prior knowledge of database contents

**Independent Test**: Create multiple tables with different schemas and metadata, call list_tables(), get_schema(), get_metadata() to verify correct information returned

### Tests for User Story 5

- [X] T059 [P] [US5] Unit test for list_tables() in tests/unit/test_storage.py
- [X] T060 [P] [US5] Unit test for get_schema(table) in tests/unit/test_storage.py
- [X] T061 [P] [US5] Unit test for get_metadata(table) in tests/unit/test_storage.py
- [X] T062 [P] [US5] Unit test for TableNotFoundError on missing table in tests/unit/test_storage.py

### Implementation for User Story 5

- [X] T063 [P] [US5] Implement list_tables() in src/mixpanel_data/_internal/storage.py (SELECT FROM _metadata WHERE table_name != '_metadata', return list[TableInfo])
- [X] T064 [P] [US5] Implement get_schema(table) in src/mixpanel_data/_internal/storage.py (PRAGMA table_info, return TableSchema with ColumnInfo list)
- [X] T065 [P] [US5] Implement get_metadata(table) in src/mixpanel_data/_internal/storage.py (SELECT FROM _metadata WHERE table_name = ?, return TableMetadata)
- [X] T066 [US5] Add TableNotFoundError handling for get_schema() and get_metadata() in src/mixpanel_data/_internal/storage.py
- [X] T067 [US5] Add integration test for introspection workflow in tests/integration/test_storage_integration.py (create tables, list, inspect, verify)

**Checkpoint**: At this point, users (especially AI agents) can discover all available data through introspection without prior knowledge. Database exploration is fully functional.

---

## Phase 8: User Story 6 - Explicit Table Management (Priority: P2)

**Goal**: Prevent accidental data overwrites by requiring explicit drop operations before table recreation

**Independent Test**: Create table, attempt to create again, verify TableExistsError raised, then explicitly drop and recreate successfully

### Tests for User Story 6

- [X] T068 [P] [US6] Unit test for table_exists(name) in tests/unit/test_storage.py
- [X] T069 [P] [US6] Unit test for drop_table(name) in tests/unit/test_storage.py
- [X] T070 [P] [US6] Unit test for TableExistsError on duplicate creation in tests/unit/test_storage.py
- [X] T071 [P] [US6] Unit test for TableNotFoundError on drop_table(missing) in tests/unit/test_storage.py

### Implementation for User Story 6

- [X] T072 [P] [US6] Implement table_exists(name) in src/mixpanel_data/_internal/storage.py (check DuckDB system tables)
- [X] T073 [P] [US6] Implement drop_table(name) in src/mixpanel_data/_internal/storage.py (DROP TABLE, DELETE FROM _metadata)
- [X] T074 [US6] Add TableExistsError check in create_events_table() in src/mixpanel_data/_internal/storage.py
- [X] T075 [US6] Add TableExistsError check in create_profiles_table() in src/mixpanel_data/_internal/storage.py
- [X] T076 [US6] Add TableNotFoundError check in drop_table() in src/mixpanel_data/_internal/storage.py
- [X] T077 [US6] Add integration test for table replacement pattern in tests/integration/test_storage_integration.py (create, drop, recreate)

**Checkpoint**: All user stories complete. StorageEngine fully implements explicit table management - no accidental overwrites possible. Data safety is guaranteed.

---

## Phase 9: Polish & Cross-Cutting Concerns

**Purpose**: Finalization, optimization, and documentation

- [ ] T078 [P] Add comprehensive docstrings to all public methods in src/mixpanel_data/_internal/storage.py (Google style, with examples)
- [ ] T079 [P] Add type hints to all methods and helpers in src/mixpanel_data/_internal/storage.py (strict mypy compliance)
- [ ] T080 [P] Create pytest fixtures for StorageEngine in tests/conftest.py (ephemeral storage, sample data generators)
- [ ] T081 Run mypy --strict on src/mixpanel_data/_internal/storage.py and src/mixpanel_data/types.py (fix all type errors)
- [ ] T082 Run ruff check and ruff format on all storage-related files (fix all linting issues)
- [ ] T083 [P] Add edge case tests for malformed data handling in tests/unit/test_storage.py
- [ ] T084 [P] Add edge case tests for disk space errors in tests/unit/test_storage.py
- [ ] T085 [P] Add edge case tests for empty iterator handling in tests/unit/test_storage.py
- [ ] T086 Run pytest with coverage on storage tests (verify 90%+ coverage per SC-007)
- [ ] T087 Add JSON property query examples to docstrings in src/mixpanel_data/_internal/storage.py (properties->>'$.field' syntax)
- [ ] T088 Update CLAUDE.md with StorageEngine usage patterns (if needed for context)
- [ ] T089 Validate all examples from contracts/examples.py work correctly (manual run/review)
- [ ] T090 Create conftest.py fixtures for common test patterns (event generators, profile generators, table creation helpers)
- [ ] T091 Performance benchmark: Verify 1M events ingest completes within reasonable time (<5 minutes) and memory (<500MB)
- [ ] T092 Final integration test: Run all quickstart.md examples end-to-end (verify all documented patterns work)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - BLOCKS all user stories
- **User Stories (Phase 3-8)**: All depend on Foundational phase completion
  - User stories can then proceed in parallel (if staffed)
  - Or sequentially in priority order: US1 (P1) → US2 (P1) → US3 (P1) → US4 (P2) → US5 (P2) → US6 (P2)
- **Polish (Phase 9)**: Depends on all desired user stories being complete

### User Story Dependencies

- **US1 - Persistent Storage** (P1): Can start after Foundational (Phase 2) - No dependencies on other stories
- **US2 - Memory-Efficient Ingestion** (P1): Can start after Foundational (Phase 2) - Integrates with US1 for database creation
- **US3 - Ephemeral Workflows** (P1): Can start after Foundational (Phase 2) - Extends US1 with cleanup behavior
- **US4 - Flexible Query Execution** (P2): Can start after Foundational (Phase 2) - Requires database to exist (US1)
- **US5 - Database Introspection** (P2): Can start after Foundational (Phase 2) - Requires metadata tracking (US2)
- **US6 - Explicit Table Management** (P2): Can start after Foundational (Phase 2) - Integrates with US2 for table creation checks

### Within Each User Story

- Tests MUST be written and FAIL before implementation
- Helpers before main methods
- Core implementation before error handling
- Unit tests before integration tests
- Story complete and independently tested before moving to next priority

### Parallel Opportunities

**Setup Phase (all parallel)**:
- T001, T002, T003, T004 - all can run together

**Foundational Phase (all parallel)**:
- T005, T006, T007 - all dataclass definitions can be added simultaneously
- T008, T009 depend on T005-T007 completion

**Within Each User Story**:
- All tests for a story can be written in parallel
- Helper methods can often be implemented in parallel
- Main methods that depend on helpers must wait

**Across User Stories (after Foundational complete)**:
- US1, US2, US3 can start in parallel (different aspects of database lifecycle)
- US4, US5, US6 can start in parallel (all query/management operations)
- With 3+ developers: Each can own 1-2 user stories concurrently

---

## Parallel Example: User Story 2 (Memory-Efficient Ingestion)

```bash
# Launch all tests together (write tests first):
Task T021: "Unit test for create_events_table batch insert logic"
Task T022: "Unit test for create_profiles_table batch insert logic"
Task T023: "Unit test for progress callback invocation"
Task T024: "Integration test for large dataset ingestion (100K events)"
Task T025: "Memory profiling test for 1M events (<500MB)"

# After tests fail, launch helper implementations in parallel:
Task T026: "Implement _create_events_table_schema() helper"
Task T027: "Implement _create_profiles_table_schema() helper"
Task T028: "Implement _create_metadata_table() helper"
Task T029: "Implement _batch_insert_events() helper"
Task T030: "Implement _batch_insert_profiles() helper"

# Then sequential main methods:
Task T031: "Implement create_events_table()" (depends on T026, T029)
Task T032: "Implement create_profiles_table()" (depends on T027, T030)
Task T033: "Implement _record_metadata() helper"

# Then validations:
Task T034: "Add table name validation"
Task T035: "Add field validation"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (T001-T004)
2. Complete Phase 2: Foundational (T005-T009) - CRITICAL checkpoint
3. Complete Phase 3: User Story 1 (T010-T020)
4. **STOP and VALIDATE**: Create database, insert data, close, reopen, query
5. If validation passes: MVP ready for demo/integration with FetcherService

**Why this MVP?** Persistent storage is the foundation. Without it, nothing else works. This enables basic "fetch once, query many times" workflow.

### Incremental Delivery (Recommended)

1. **Foundation** (Phases 1-2) → Data structures and base class ready
2. **MVP** (Phase 3: US1) → Persistent storage working → Can demo basic workflow
3. **Production-Ready** (Phase 4: US2) → Streaming ingestion → Can handle large datasets
4. **Agent-Friendly** (Phase 5: US3) → Ephemeral workflows → Automation-ready
5. **Query Flexibility** (Phase 6: US4) → Multiple query formats → Data science workflows
6. **Discoverability** (Phase 7: US5) → Introspection → AI agent exploration
7. **Safety** (Phase 8: US6) → Explicit management → Production-hardened
8. **Polish** (Phase 9) → Documentation, optimization, edge cases

Each phase adds value without breaking previous phases. Can deploy/demo at any checkpoint.

### Parallel Team Strategy

With 2-3 developers after Foundational phase complete:

**Developer A**: US1 + US4 (database lifecycle + query execution)
**Developer B**: US2 + US5 (ingestion + introspection)
**Developer C**: US3 + US6 (ephemeral + table management)

Then collaborate on Phase 9 (Polish).

---

## Notes

- [P] tasks = different files or independent components, no dependencies
- [Story] label maps task to specific user story for traceability
- Each user story should be independently completable and testable
- Tests written first (TDD approach) since this is foundational infrastructure
- SC-007 requires 90%+ test coverage - comprehensive testing is critical
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
- All integration tests should verify story works end-to-end
- Memory profiling test (T025) is critical for SC-001 validation
- Ephemeral cleanup tests (T038-T040) are critical for SC-002 validation
- Type hints required throughout for strict mypy compliance (per constitution Quality Gates)
- DuckDB-specific features documented in docstrings (JSON queries, relation chaining)
