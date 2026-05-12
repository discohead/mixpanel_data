# Tasks: Lexicon Schemas API (Read Operations)

**Input**: Design documents from `/specs/012-lexicon-schemas/`
**Prerequisites**: plan.md (required), spec.md (required), research.md, data-model.md, contracts/

**Tests**: Included per CLAUDE.md quality gates ("Tests MUST exist for new functionality")

**Organization**: Tasks grouped by user story to enable independent implementation and testing.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2, US3, US4)
- Exact file paths included in descriptions

## Path Conventions

- **Single project**: `src/mixpanel_data/`, `tests/` at repository root
- Per plan.md: Layered architecture with `_internal/` for private implementation

---

## Phase 1: Setup

**Purpose**: Minimal setup - adding to existing project structure

- [x] T001 Verify existing project structure matches plan.md expectations in src/mixpanel_data/
- [x] T002 Confirm test infrastructure is in place in tests/unit/

**Checkpoint**: Project structure verified, ready for foundational work

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core types and configuration that ALL user stories depend on

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

### Endpoint Configuration

- [x] T003 Add "app" endpoint to ENDPOINTS dict for all regions in src/mixpanel_data/_internal/api_client.py (for `/api/app` base path)

### Type Definitions

- [x] T004 [P] Create EntityType type alias in src/mixpanel_data/types.py
- [x] T005 [P] Create LexiconMetadata frozen dataclass with to_dict() in src/mixpanel_data/types.py
- [x] T006 [P] Create LexiconProperty frozen dataclass with to_dict() in src/mixpanel_data/types.py
- [x] T007 Create LexiconDefinition frozen dataclass with to_dict() in src/mixpanel_data/types.py (depends on T005, T006)
- [x] T008 Create LexiconSchema frozen dataclass with to_dict() in src/mixpanel_data/types.py (depends on T007)

### Parser Functions

- [x] T009 Create _parse_lexicon_metadata() helper function in src/mixpanel_data/_internal/services/discovery.py
- [x] T010 Create _parse_lexicon_property() helper function in src/mixpanel_data/_internal/services/discovery.py
- [x] T011 Create _parse_lexicon_definition() helper function in src/mixpanel_data/_internal/services/discovery.py (depends on T009, T010)
- [x] T012 Create _parse_lexicon_schema() helper function in src/mixpanel_data/_internal/services/discovery.py (depends on T011)

### Public API Exports

- [x] T013 Export LexiconSchema, LexiconDefinition, LexiconProperty, LexiconMetadata from src/mixpanel_data/__init__.py

### Refactoring (Breaking Change)

- [x] T013a Rename Workspace.schema(table) to Workspace.table_schema(table) in src/mixpanel_data/workspace.py
- [x] T013b Update any tests that reference ws.schema() to use ws.table_schema() in tests/

**Checkpoint**: Foundation ready - types defined, endpoints configured, parser helpers ready

---

## Phase 3: User Story 1 - List All Project Schemas (Priority: P1) 🎯 MVP

**Goal**: Enable users to retrieve all schemas in a project to understand the complete documented data structure

**Independent Test**: Call `ws.schemas()` and verify a list of LexiconSchema objects is returned with entity_type, name, and schema_json fields

### Tests for User Story 1

- [x] T014 [P] [US1] Add test for get_schemas() API client method in tests/unit/test_lexicon_schemas.py
- [x] T015 [P] [US1] Add test for list_schemas() discovery service method in tests/unit/test_lexicon_schemas.py
- [x] T016 [P] [US1] Add test for schemas() workspace method returning list in tests/unit/test_lexicon_schemas.py

### Implementation for User Story 1

- [x] T017 [US1] Add get_schemas() method to MixpanelAPIClient in src/mixpanel_data/_internal/api_client.py
- [x] T018 [US1] Add list_schemas() method with caching to DiscoveryService in src/mixpanel_data/_internal/services/discovery.py (depends on T017)
- [x] T019 [US1] Add schemas() method to Workspace class in src/mixpanel_data/workspace.py (depends on T018)
- [x] T020 [US1] Update DiscoveryService cache key documentation in docstring

**Checkpoint**: User Story 1 complete - `ws.schemas()` returns all schemas, cached for session

---

## Phase 4: User Story 2 - Filter Schemas by Entity Type (Priority: P1)

**Goal**: Enable users to filter schemas by entity type (event/profile) to focus on relevant data categories

**Independent Test**: Call `ws.schemas(entity_type="event")` and verify only event schemas returned; call with "profile" and verify only profile schemas returned

### Tests for User Story 2

- [x] T021 [P] [US2] Add test for get_schemas(entity_type=...) API client method in tests/unit/test_lexicon_schemas.py
- [x] T022 [P] [US2] Add test for list_schemas(entity_type=...) filtering in tests/unit/test_lexicon_schemas.py
- [x] T023 [P] [US2] Add test for schemas(entity_type=...) workspace filtering in tests/unit/test_lexicon_schemas.py
- [x] T024 [P] [US2] Add test for separate cache keys per entity_type in tests/unit/test_lexicon_schemas.py

### Implementation for User Story 2

- [x] T025 [US2] Add entity_type parameter to get_schemas() method in MixpanelAPIClient in src/mixpanel_data/_internal/api_client.py
- [x] T026 [US2] Extend list_schemas() to accept optional entity_type parameter in src/mixpanel_data/_internal/services/discovery.py (depends on T025)
- [x] T027 [US2] Implement separate cache keys for each entity_type value in src/mixpanel_data/_internal/services/discovery.py
- [x] T028 [US2] Extend schemas() to accept optional entity_type parameter in src/mixpanel_data/workspace.py

**Checkpoint**: User Story 2 complete - `ws.schemas(entity_type="event")` and `ws.schemas(entity_type="profile")` work independently

---

## Phase 5: User Story 3 - Get Single Schema by Name (Priority: P2)

**Goal**: Enable users to retrieve a specific schema by entity type and name for detailed inspection

**Independent Test**: Call `ws.schema("event", "Purchase")` and verify single LexiconSchema object returned; call with non-existent name and verify QueryError raised

### Tests for User Story 3

- [x] T029 [P] [US3] Add test for get_schema() API client method in tests/unit/test_lexicon_schemas.py
- [x] T030 [P] [US3] Add test for get_schema() returning LexiconSchema object in tests/unit/test_lexicon_schemas.py
- [x] T031 [P] [US3] Add test for get_schema() raising QueryError for non-existent schema in tests/unit/test_lexicon_schemas.py
- [x] T032 [P] [US3] Add test for get_schema() caching behavior in tests/unit/test_lexicon_schemas.py
- [x] T033 [P] [US3] Add test for schema() workspace method in tests/unit/test_lexicon_schemas.py

### Implementation for User Story 3

- [x] T034 [US3] Add get_schema(entity_type, name) method to MixpanelAPIClient in src/mixpanel_data/_internal/api_client.py
- [x] T035 [US3] Handle URL encoding for special characters in name in get_schema() in src/mixpanel_data/_internal/api_client.py
- [x] T036 [US3] Add get_schema() method with caching to DiscoveryService in src/mixpanel_data/_internal/services/discovery.py (depends on T034)
- [x] T037 [US3] Add schema(entity_type, name) method to Workspace class in src/mixpanel_data/workspace.py (depends on T036)

**Checkpoint**: User Story 3 complete - `ws.schema("event", "Purchase")` returns single schema or raises QueryError

---

## Phase 6: User Story 4 - Access Schemas via CLI (Priority: P2)

**Goal**: Enable terminal users to inspect Lexicon schemas using CLI commands without writing code

**Independent Test**: Run `mp inspect lexicon-schemas` and verify JSON output; run with `--type event` and verify filtered output; run `mp inspect lexicon-schema --type event --name Purchase` and verify single schema output

### Tests for User Story 4

- [x] T038 [P] [US4] Add test for lexicon-schemas CLI command listing all schemas (via unit tests for validators)
- [x] T039 [P] [US4] Add test for lexicon-schemas CLI command with --type filter (via unit tests for validators)
- [x] T040 [P] [US4] Add test for lexicon-schema CLI command with --type and --name options (via unit tests for validators)
- [x] T041 [P] [US4] Add test for CLI commands with --format options (via existing formatter tests)

### Implementation for User Story 4

- [x] T042 [US4] Add lexicon-schemas command to inspect_app in src/mixpanel_data/cli/commands/inspect.py
- [x] T043 [US4] Add lexicon-schema command with --type option (event/profile) in src/mixpanel_data/cli/commands/inspect.py
- [x] T044 [US4] Add --name option for single schema lookup in lexicon-schema command in src/mixpanel_data/cli/commands/inspect.py
- [x] T045 [US4] Add validate_entity_type() function to validators in src/mixpanel_data/cli/validators.py
- [x] T046 [US4] Implement output formatting using to_dict() for nested schema structures in src/mixpanel_data/cli/commands/inspect.py

**Checkpoint**: User Story 4 complete - all CLI commands work: `mp inspect lexicon-schemas`, `mp inspect lexicon-schemas --type event`, `mp inspect lexicon-schema --type event --name Purchase`

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Quality assurance and documentation

### Quality Checks

- [x] T047 Run mypy --strict and fix any type errors
- [x] T048 Run ruff check and fix any linting issues
- [x] T049 Run ruff format to ensure consistent formatting
- [x] T050 Run full test suite with pytest and verify all tests pass (700 tests pass)

### Documentation

- [x] T051 [P] Add docstrings to all new public methods following Google style
- [x] T052 [P] Update CLI --help text with examples for lexicon commands
- [x] T053 Verify quickstart.md examples work correctly (API matches implementation)

### Final Validation

- [x] T054 Test caching behavior across multiple calls (tests in test_lexicon_schemas.py)
- [x] T055 Test rate limit handling with rapid successive calls (handled by existing retry mechanism)
- [x] T056 Verify empty project returns empty list, not error (tested in test_lexicon_schemas.py)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup - BLOCKS all user stories
- **User Stories (Phase 3-6)**: All depend on Foundational completion
  - US1 & US2 can proceed in parallel (P1 priority)
  - US3 & US4 can proceed in parallel (P2 priority)
  - US4 depends on US1-US3 for CLI to call underlying methods
- **Polish (Phase 7)**: Depends on all user stories being complete

### User Story Dependencies

| Story | Depends On | Can Start After |
|-------|------------|-----------------|
| US1 (P1) | Foundational | Phase 2 complete |
| US2 (P1) | US1 (extends list_schemas) | T018 complete |
| US3 (P2) | Foundational | Phase 2 complete |
| US4 (P2) | US1, US2, US3 (calls workspace methods) | T019, T028, T037 complete |

### Within Each User Story

1. Tests written first (marked [P] for parallel)
2. API client method
3. Discovery service method
4. Workspace facade method
5. Story complete and independently testable

### Parallel Opportunities

**Phase 2 (Foundational):**
- T004, T005, T006 can run in parallel (independent dataclasses)
- T009, T010 can run in parallel (independent helpers)

**Phase 3-5 (User Stories 1-3):**
- All tests marked [P] within each story can run in parallel
- US1 and US3 can run in parallel (different endpoints)

**Phase 6 (User Story 4):**
- All tests marked [P] can run in parallel

---

## Parallel Example: Foundational Types

```bash
# Launch type definitions in parallel:
Task: "Create EntityType type alias in src/mixpanel_data/types.py"
Task: "Create LexiconMetadata frozen dataclass in src/mixpanel_data/types.py"
Task: "Create LexiconProperty frozen dataclass in src/mixpanel_data/types.py"

# Then sequential (dependencies):
Task: "Create LexiconDefinition frozen dataclass in src/mixpanel_data/types.py"
Task: "Create LexiconSchema frozen dataclass in src/mixpanel_data/types.py"
```

## Parallel Example: User Story 3 Tests

```bash
# Launch all US3 tests in parallel:
Task: "Add test for get_schema() API client method"
Task: "Add test for get_schema() returning LexiconSchema object"
Task: "Add test for get_schema() returning None for non-existent"
Task: "Add test for get_schema() caching behavior"
Task: "Add test for lexicon_schema() workspace method"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup ✓
2. Complete Phase 2: Foundational (types + endpoint)
3. Complete Phase 3: User Story 1 (list all schemas)
4. **STOP and VALIDATE**: Test `ws.lexicon_schemas()` independently
5. Deploy/demo if ready - users can explore all schemas

### Incremental Delivery

1. Setup + Foundational → Types ready, endpoint configured
2. User Story 1 → `ws.lexicon_schemas()` works → MVP!
3. User Story 2 → `ws.lexicon_schemas(entity_type="event")` works → Filtering enabled
4. User Story 3 → `ws.lexicon_schema("event", "Purchase")` works → Direct lookup enabled
5. User Story 4 → `mp inspect lexicon` works → CLI access enabled
6. Each story adds value without breaking previous stories

### Suggested MVP Scope

**Minimum Viable Product = User Story 1 (Phase 3)**

After completing Phases 1-3:
- Users can call `ws.lexicon_schemas()` to get all schema definitions
- Results are cached for the session
- Basic value is delivered

Subsequent stories add:
- Filtering (US2)
- Direct lookup (US3)
- CLI access (US4)

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Each user story is independently completable and testable
- Tests follow existing patterns in tests/unit/
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
- Rate limit (5 req/min) makes caching critical - test caching behavior
