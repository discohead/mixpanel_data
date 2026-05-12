# Tasks: Streaming API

**Input**: Design documents from `/specs/011-streaming-api/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: Included per project quality gates (Constitution: mypy, ruff, pytest)

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3, US4)
- Include exact file paths in descriptions

---

## Phase 1: Setup

**Purpose**: Verify project is ready for streaming API implementation

- [X] T001 Verify existing workspace.py has _require_api_client() method available
- [X] T002 Verify _transform_event and _transform_profile functions are importable from src/mixpanel_data/_internal/services/fetcher.py

**Checkpoint**: Dependencies verified - implementation can begin

---

## Phase 2: Foundational (None Required)

**Purpose**: No foundational work needed - streaming is a surgical addition to existing infrastructure

**Note**: This feature adds to an existing, complete codebase. The API client iterators (`export_events`, `export_profiles`) and transformation functions (`_transform_event`, `_transform_profile`) already exist.

**Checkpoint**: Foundation ready - user story implementation can begin

---

## Phase 3: User Story 1 - Stream Events for ETL Pipeline (Priority: P1) 🎯 MVP

**Goal**: Enable data engineers to stream events directly from Mixpanel API without local storage

**Independent Test**: Call `ws.stream_events(from_date="...", to_date="...")` and iterate over results. Verify events are yielded and no database files are created.

### Implementation for User Story 1

- [X] T003 [US1] Implement stream_events() method in src/mixpanel_data/workspace.py with signature: `stream_events(*, from_date: str, to_date: str, events: list[str] | None = None, where: str | None = None, raw: bool = False) -> Iterator[dict[str, Any]]`
- [X] T004 [US1] Add docstring with Args, Yields, Raises, and Example sections per contract in contracts/workspace-streaming.md
- [X] T005 [US1] Import _transform_event from fetcher.py and apply when raw=False
- [X] T006 [US1] Write unit tests for stream_events() in tests/test_workspace_streaming.py covering: basic streaming, event name filter, where filter, raw=True, raw=False

**Checkpoint**: User Story 1 complete - stream_events() works independently with both normalized and raw output

---

## Phase 4: User Story 3 - Stream User Profiles (Priority: P2)

**Goal**: Enable streaming of user profiles without local storage

**Independent Test**: Call `ws.stream_profiles()` and iterate over results. Verify profiles are yielded and no database files are created.

**Note**: Can be implemented in parallel with User Story 1 (different method, no dependencies)

### Implementation for User Story 3

- [X] T007 [P] [US3] Implement stream_profiles() method in src/mixpanel_data/workspace.py with signature: `stream_profiles(*, where: str | None = None, raw: bool = False) -> Iterator[dict[str, Any]]`
- [X] T008 [US3] Add docstring with Args, Yields, Raises, and Example sections per contract
- [X] T009 [US3] Import _transform_profile from fetcher.py and apply when raw=False
- [X] T010 [US3] Write unit tests for stream_profiles() in tests/test_workspace_streaming.py covering: basic streaming, where filter, raw=True, raw=False

**Checkpoint**: User Story 3 complete - stream_profiles() works independently

---

## Phase 5: User Story 2 - CLI Export to Standard Output (Priority: P1)

**Goal**: Enable CLI users to stream data to stdout for piping to other tools

**Independent Test**: Run `mp fetch events --from 2024-01-01 --to 2024-01-31 --stdout` and pipe to `jq`. Verify valid JSONL output.

**Dependencies**: Requires stream_events() and stream_profiles() from US1 and US3

### Implementation for User Story 2

- [X] T011 [US2] Add --stdout option to fetch_events command in src/mixpanel_data/cli/commands/fetch.py
- [X] T012 [US2] Add --raw option to fetch_events command (only valid with --stdout)
- [X] T013 [US2] Make NAME argument optional when --stdout is set (use `typer.Argument(default=None)`)
- [X] T014 [US2] Implement stdout streaming logic: iterate over ws.stream_events(), print each dict as JSON line using json.dumps with default=str for datetime serialization
- [X] T015 [US2] Send progress to stderr using err_console when --stdout is set
- [X] T016 [US2] Add --stdout and --raw options to fetch_profiles command in src/mixpanel_data/cli/commands/fetch.py
- [X] T017 [US2] Implement stdout streaming logic for profiles: iterate over ws.stream_profiles(), print JSONL
- [X] T018 [US2] Write CLI tests in tests/integration/cli/test_fetch_streaming.py covering: --stdout output is valid JSONL, --raw changes output format, progress goes to stderr

**Checkpoint**: User Story 2 complete - CLI streaming works for both events and profiles

---

## Phase 6: User Story 4 - Choose Output Format (Priority: P2)

**Goal**: Support both normalized and raw API formats for integration flexibility

**Independent Test**: Stream with `raw=True` and verify output matches Mixpanel API format. Stream with `raw=False` (default) and verify normalized format.

**Note**: Core implementation is complete in US1 and US3. This phase adds edge case testing and documentation.

### Verification for User Story 4

- [X] T019 [US4] Add test case verifying normalized event format matches data-model.md structure in tests/unit/test_workspace_streaming.py
- [X] T020 [US4] Add test case verifying raw event format matches Mixpanel API structure (event + properties with time as Unix timestamp)
- [X] T021 [US4] Add test case verifying normalized profile format matches data-model.md structure
- [X] T022 [US4] Add test case verifying raw profile format matches Mixpanel API structure ($distinct_id + $properties)
- [X] T023 [US4] Add CLI test verifying --raw flag produces raw format output

**Checkpoint**: User Story 4 complete - both output formats verified

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Quality checks and validation

- [X] T024 Run `ruff check src/mixpanel_data/workspace.py src/mixpanel_data/cli/commands/fetch.py`
- [X] T025 Run `ruff format src/mixpanel_data/workspace.py src/mixpanel_data/cli/commands/fetch.py`
- [X] T026 Run `mypy --strict src/mixpanel_data/workspace.py src/mixpanel_data/cli/commands/fetch.py`
- [X] T027 Run full test suite with `pytest tests/`
- [X] T028 Validate quickstart.md examples work as documented (via tests)
- [X] T029 Verify backward compatibility: existing fetch commands still work without --stdout (via TestBackwardCompatibility)

---

## Dependencies & Execution Order

### Phase Dependencies

```
Phase 1: Setup ──────────────────────────────┐
                                             │
Phase 2: Foundational (none needed) ─────────┤
                                             ▼
        ┌────────────────────────────────────┴───────────────────────────────┐
        │                                                                    │
        ▼                                                                    ▼
Phase 3: US1 - stream_events()                           Phase 4: US3 - stream_profiles()
        │                                                                    │
        └────────────────────────┬───────────────────────────────────────────┘
                                 ▼
                    Phase 5: US2 - CLI --stdout/--raw
                                 │
                                 ▼
                    Phase 6: US4 - Output Format Verification
                                 │
                                 ▼
                    Phase 7: Polish
```

### User Story Dependencies

| Story | Depends On | Can Parallel With |
|-------|------------|-------------------|
| US1 (stream_events) | Setup only | US3 |
| US3 (stream_profiles) | Setup only | US1 |
| US2 (CLI --stdout) | US1, US3 | - |
| US4 (Output Format) | US1, US3, US2 | - |

### Parallel Opportunities

**Within Phase 3 & 4 (can run simultaneously):**
- T003-T006 (US1: stream_events)
- T007-T010 (US3: stream_profiles)

**Within Phase 5:**
- T011-T015 (events CLI) can partially parallel with T016-T017 (profiles CLI)

---

## Parallel Example: US1 and US3 Together

```bash
# These can run in parallel (different methods in same file):
Task: "T003 Implement stream_events() method in src/mixpanel_data/workspace.py"
Task: "T007 Implement stream_profiles() method in src/mixpanel_data/workspace.py"

# Note: If same developer, do sequentially to avoid merge conflicts in workspace.py
# If different developers, use feature branches and merge carefully
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (T001-T002)
2. Complete Phase 3: User Story 1 (T003-T006)
3. **STOP and VALIDATE**: Test `ws.stream_events()` independently
4. This alone enables ETL pipeline use case

### Full Feature (All Stories)

1. Complete Setup
2. Implement US1 and US3 in parallel (library methods)
3. Implement US2 (CLI depends on library)
4. Verify US4 (output formats)
5. Polish and validate

### Estimated Scope

| Phase | Tasks | Effort |
|-------|-------|--------|
| Setup | 2 | Minimal (verification only) |
| US1 | 4 | ~30 lines of code + tests |
| US3 | 4 | ~20 lines of code + tests |
| US2 | 8 | ~50 lines of code + tests |
| US4 | 5 | Tests only |
| Polish | 6 | Validation |
| **Total** | **29** | Small feature |

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- US1 and US3 can be implemented in parallel by different developers
- US2 (CLI) must wait for US1 and US3 to complete
- US4 is verification of functionality built into US1-US3
- Commit after each task or logical group
- Run `just check` after each phase to verify quality gates
