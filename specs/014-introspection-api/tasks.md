# Tasks: Local Introspection API

**Input**: Design documents from `/specs/014-introspection-api/`
**Prerequisites**: plan.md (required), spec.md (required), research.md, data-model.md, contracts/

**Tests**: Not explicitly requested in specification. Tests omitted per task generation rules.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

---

## Phase 1: Setup

**Purpose**: No setup required - working within existing Python package

- [x] T001 Verify existing project structure matches plan in src/mixpanel_data/

**Checkpoint**: Ready for implementation ✅

---

## Phase 2: Foundational (Shared Types)

**Purpose**: Create all result types that will be shared across user stories

**⚠️ CRITICAL**: Types must be complete before Workspace methods can return them

- [x] T002 [P] Add ColumnSummary dataclass to src/mixpanel_data/types.py
- [x] T003 [P] Add SummaryResult dataclass with df property to src/mixpanel_data/types.py
- [x] T004 [P] Add EventStats dataclass to src/mixpanel_data/types.py
- [x] T005 [P] Add EventBreakdownResult dataclass with df property to src/mixpanel_data/types.py
- [x] T006 [P] Add ColumnStatsResult dataclass with df property to src/mixpanel_data/types.py

**Checkpoint**: All result types defined - user story implementation can begin ✅

---

## Phase 3: User Story 1 - Sample Data Inspection (Priority: P1) 🎯 MVP

**Goal**: Enable users to see random sample rows from any table

**Independent Test**: `ws.sample("events", n=5)` returns 5 random rows as DataFrame

### Implementation for User Story 1

- [x] T007 [US1] Implement sample() method in src/mixpanel_data/workspace.py
- [x] T008 [US1] Add sample CLI command to src/mixpanel_data/cli/commands/inspect.py

**Checkpoint**: Users can sample any table via Python API and CLI ✅

---

## Phase 4: User Story 2 - Statistical Summary (Priority: P1)

**Goal**: Provide comprehensive per-column statistics for any table

**Independent Test**: `ws.summarize("events")` returns SummaryResult with column stats and row count

### Implementation for User Story 2

- [x] T009 [US2] Implement summarize() method in src/mixpanel_data/workspace.py
- [x] T010 [US2] Add summarize CLI command to src/mixpanel_data/cli/commands/inspect.py

**Checkpoint**: Users can get statistical summary of any table via Python API and CLI ✅

---

## Phase 5: User Story 3 - Event Distribution Analysis (Priority: P2)

**Goal**: Analyze event type distribution with counts, users, and date ranges

**Independent Test**: `ws.event_breakdown("events")` returns EventBreakdownResult with per-event stats

### Implementation for User Story 3

- [x] T011 [US3] Implement event_breakdown() method with schema validation in src/mixpanel_data/workspace.py
- [x] T012 [US3] Add breakdown CLI command to src/mixpanel_data/cli/commands/inspect.py

**Checkpoint**: Users can analyze event distribution via Python API and CLI ✅

---

## Phase 6: User Story 4 - Property Key Discovery (Priority: P2)

**Goal**: Discover all JSON property keys in a table, optionally filtered by event

**Independent Test**: `ws.property_keys("events")` returns sorted list of property key names

### Implementation for User Story 4

- [x] T013 [US4] Implement property_keys() method in src/mixpanel_data/workspace.py
- [x] T014 [US4] Add keys CLI command to src/mixpanel_data/cli/commands/inspect.py

**Checkpoint**: Users can discover JSON property keys via Python API and CLI ✅

---

## Phase 7: User Story 5 - Deep Column Analysis (Priority: P3)

**Goal**: Provide detailed statistics for a single column including top values

**Independent Test**: `ws.column_stats("events", "event_name")` returns ColumnStatsResult with top values

### Implementation for User Story 5

- [x] T015 [US5] Implement column_stats() method with JSON path support in src/mixpanel_data/workspace.py
- [x] T016 [US5] Add column CLI command to src/mixpanel_data/cli/commands/inspect.py

**Checkpoint**: Users can analyze individual columns via Python API and CLI ✅

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Finalize exports and validate complete implementation

- [x] T017 Export new types (ColumnSummary, SummaryResult, EventStats, EventBreakdownResult, ColumnStatsResult) in src/mixpanel_data/__init__.py
- [x] T018 Run type checking with mypy --strict on new code
- [x] T019 Run linting with ruff check on new code
- [x] T020 Validate quickstart.md examples work correctly

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - verify existing structure
- **Foundational (Phase 2)**: Depends on Setup - creates all shared types
- **User Stories (Phase 3-7)**: All depend on Foundational (Phase 2)
  - US1 and US2 can proceed in parallel (both P1)
  - US3 and US4 can proceed in parallel (both P2)
  - US5 can start after Foundational
- **Polish (Phase 8)**: Depends on all user stories being complete

### User Story Dependencies

- **User Story 1 (P1)**: Depends only on Phase 2 - No types required (returns DataFrame)
- **User Story 2 (P1)**: Depends on Phase 2 (T002, T003) - Uses ColumnSummary, SummaryResult
- **User Story 3 (P2)**: Depends on Phase 2 (T004, T005) - Uses EventStats, EventBreakdownResult
- **User Story 4 (P2)**: Depends only on Phase 2 - No types required (returns list[str])
- **User Story 5 (P3)**: Depends on Phase 2 (T006) - Uses ColumnStatsResult

### Parallel Opportunities

**Phase 2 (All types can be created in parallel)**:
```
T002, T003, T004, T005, T006 - All in different sections of types.py
```

**Phase 3-7 (User stories with same priority can run in parallel)**:
```
# P1 stories (can run in parallel after Phase 2):
T007, T008 (US1) | T009, T010 (US2)

# P2 stories (can run in parallel after Phase 2):
T011, T012 (US3) | T013, T014 (US4)

# P3 stories:
T015, T016 (US5)
```

---

## Parallel Example: Phase 2 (Foundational Types)

```bash
# Launch all type definitions together:
Task: "Add ColumnSummary dataclass to src/mixpanel_data/types.py"
Task: "Add SummaryResult dataclass to src/mixpanel_data/types.py"
Task: "Add EventStats dataclass to src/mixpanel_data/types.py"
Task: "Add EventBreakdownResult dataclass to src/mixpanel_data/types.py"
Task: "Add ColumnStatsResult dataclass to src/mixpanel_data/types.py"
```

## Parallel Example: P1 User Stories

```bash
# After Phase 2 completes, launch both P1 stories:
Task: "Implement sample() method in src/mixpanel_data/workspace.py"
Task: "Add sample CLI command to src/mixpanel_data/cli/commands/inspect.py"
# AND simultaneously:
Task: "Implement summarize() method in src/mixpanel_data/workspace.py"
Task: "Add summarize CLI command to src/mixpanel_data/cli/commands/inspect.py"
```

---

## Implementation Strategy

### MVP First (User Stories 1 & 2 Only)

1. Complete Phase 1: Setup (verify structure)
2. Complete Phase 2: Foundational types (T002-T006)
3. Complete Phase 3: User Story 1 - sample() (T007-T008)
4. Complete Phase 4: User Story 2 - summarize() (T009-T010)
5. **STOP and VALIDATE**: Both sample() and summarize() work
6. Deploy/demo if ready

### Incremental Delivery

1. Setup + Foundational → Types ready
2. Add US1 (sample) → Test → **MVP v1!**
3. Add US2 (summarize) → Test → **MVP v2!**
4. Add US3 (event_breakdown) → Test → Deploy
5. Add US4 (property_keys) → Test → Deploy
6. Add US5 (column_stats) → Test → Deploy
7. Polish phase → Final validation

### File Modification Summary

| File | Tasks |
|------|-------|
| `src/mixpanel_data/types.py` | T002, T003, T004, T005, T006 |
| `src/mixpanel_data/workspace.py` | T007, T009, T011, T013, T015 |
| `src/mixpanel_data/cli/commands/inspect.py` | T008, T010, T012, T014, T016 |
| `src/mixpanel_data/__init__.py` | T017 |

---

## Notes

- All types follow frozen dataclass pattern with lazy `_df_cache`
- All Workspace methods use existing `StorageEngine` methods
- All CLI commands use existing `handle_errors` and `output_result` helpers
- Schema validation for `event_breakdown()` per implementation plan
- Parameterized queries for `property_keys()` event filter
- JSON path expression support for `column_stats()` column parameter
