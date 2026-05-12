# Tasks: Feature Management (Flags + Experiments)

**Input**: Design documents from `/specs/025-feature-management/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: Included (project requires strict TDD per CLAUDE.md).

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

- **Types**: `src/mixpanel_data/types.py`
- **API Client**: `src/mixpanel_data/_internal/api_client.py`
- **Workspace**: `src/mixpanel_data/workspace.py`
- **CLI Commands**: `src/mixpanel_data/cli/commands/{domain}.py`
- **CLI Main**: `src/mixpanel_data/cli/main.py`
- **Tests**: `tests/`

---

## Phase 1: Setup

**Purpose**: Define enums and shared types that all user stories depend on.

- [X] T001 [P] Add `FeatureFlagStatus` enum (`enabled`, `disabled`, `archived`) to `src/mixpanel_data/types.py`
- [X] T002 [P] Add `ServingMethod` enum (`client`, `server`, `remote_or_local`, `remote_only`) to `src/mixpanel_data/types.py`
- [X] T003 [P] Add `FlagContractStatus` enum (`active`, `grace_period`, `expired`) to `src/mixpanel_data/types.py`
- [X] T004 [P] Add `ExperimentStatus` enum (`draft`, `active`, `concluded`, `success`, `fail`) to `src/mixpanel_data/types.py`
- [X] T005 [P] Add `ExperimentCreator` frozen Pydantic model to `src/mixpanel_data/types.py`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core entity models and parameter types that ALL user stories depend on.

**CRITICAL**: No user story work can begin until this phase is complete.

- [X] T006 Add `FeatureFlag` frozen Pydantic model (all fields per data-model.md, `extra="allow"`, `populate_by_name=True`) to `src/mixpanel_data/types.py`
- [X] T007 [P] Add `CreateFeatureFlagParams` Pydantic model (name, key required; description, status, tags, context, serving_method, ruleset optional) to `src/mixpanel_data/types.py`
- [X] T008 [P] Add `UpdateFeatureFlagParams` Pydantic model (name, key, status, ruleset required — PUT semantics; description, tags, context, serving_method optional) to `src/mixpanel_data/types.py`
- [X] T009 [P] Add `SetTestUsersParams` Pydantic model (`users: dict[str, str]`) to `src/mixpanel_data/types.py`
- [X] T010 [P] Add `FlagHistoryParams` Pydantic model (`page: str | None`, `page_size: int | None`) to `src/mixpanel_data/types.py`
- [X] T011 [P] Add `FlagHistoryResponse` frozen Pydantic model (`events: list[list[Any]]`, `count: int`) to `src/mixpanel_data/types.py`
- [X] T012 [P] Add `FlagLimitsResponse` frozen Pydantic model (`limit`, `is_trial`, `current_usage`, `contract_status`) to `src/mixpanel_data/types.py`
- [X] T013 Add `Experiment` frozen Pydantic model (all fields per data-model.md, `extra="allow"`, `populate_by_name=True`) to `src/mixpanel_data/types.py`
- [X] T014 [P] Add `CreateExperimentParams` Pydantic model (name required; description, hypothesis, settings, access_type, can_edit optional) to `src/mixpanel_data/types.py`
- [X] T015 [P] Add `UpdateExperimentParams` Pydantic model (all optional — PATCH semantics) to `src/mixpanel_data/types.py`
- [X] T016 [P] Add `ExperimentConcludeParams` Pydantic model (`end_date: str | None`) to `src/mixpanel_data/types.py`
- [X] T017 [P] Add `ExperimentDecideParams` Pydantic model (`success: bool` required; `variant`, `message` optional) to `src/mixpanel_data/types.py`
- [X] T018 [P] Add `DuplicateExperimentParams` Pydantic model (`name: str` required) to `src/mixpanel_data/types.py`
- [X] T019 Export all new types from `src/mixpanel_data/__init__.py`

**Checkpoint**: All Pydantic types defined and exported. Ready for API client and workspace methods.

---

## Phase 3: User Story 1 — Feature Flag CRUD (Priority: P1) MVP

**Goal**: Users can list, create, get, update, and delete feature flags via library and API client.

**Independent Test**: Create a flag, read it back, update it, list all flags, delete it — all operations return correctly typed data.

### Tests for User Story 1

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [X] T020 [P] [US1] Write unit tests for `FeatureFlag`, `CreateFeatureFlagParams`, `UpdateFeatureFlagParams` round-trip serialization in `tests/test_types_feature_flags.py`
- [X] T021 [P] [US1] Write API client tests for `list_feature_flags`, `create_feature_flag`, `get_feature_flag`, `update_feature_flag`, `delete_feature_flag` with respx mocks in `tests/test_api_client_flags.py` — verify require_scoped_path (workspace-scoped URLs), PUT for update, correct endpoint paths; include error-path tests for 400 (duplicate key, validation), 404 (not found), and workspace scope errors
- [X] T022 [P] [US1] Write workspace method tests for `list_feature_flags`, `create_feature_flag`, `get_feature_flag`, `update_feature_flag`, `delete_feature_flag` in `tests/test_workspace_flags.py`

### Implementation for User Story 1

- [X] T023 [US1] Add `list_feature_flags(include_archived)` API client method using `require_scoped_path("feature-flags")` and GET in `src/mixpanel_data/_internal/api_client.py`
- [X] T024 [P] [US1] Add `create_feature_flag(params)` API client method using POST in `src/mixpanel_data/_internal/api_client.py`
- [X] T025 [P] [US1] Add `get_feature_flag(flag_id)` API client method using GET `feature-flags/{id}/` in `src/mixpanel_data/_internal/api_client.py`
- [X] T026 [P] [US1] Add `update_feature_flag(flag_id, params)` API client method using PUT (not PATCH) in `src/mixpanel_data/_internal/api_client.py`
- [X] T027 [P] [US1] Add `delete_feature_flag(flag_id)` API client method using DELETE in `src/mixpanel_data/_internal/api_client.py`
- [X] T028 [US1] Add `list_feature_flags`, `create_feature_flag`, `get_feature_flag`, `update_feature_flag`, `delete_feature_flag` workspace methods in `src/mixpanel_data/workspace.py` — follow existing dashboard CRUD pattern (call api_client, validate with Pydantic model)

**Checkpoint**: Flag CRUD works through library API. Tests pass.

---

## Phase 4: User Story 2 — Experiment Lifecycle Management (Priority: P1)

**Goal**: Users can create experiments and manage the full lifecycle (create → launch → conclude → decide).

**Independent Test**: Create an experiment, launch it, conclude it, decide a winner — each transition returns updated status.

### Tests for User Story 2

- [X] T029 [P] [US2] Write unit tests for `Experiment`, `CreateExperimentParams`, `ExperimentDecideParams`, `ExperimentConcludeParams` round-trip serialization in `tests/test_types_experiments.py`
- [X] T030 [P] [US2] Write API client tests for `list_experiments`, `create_experiment`, `get_experiment`, `update_experiment`, `delete_experiment`, `launch_experiment`, `conclude_experiment`, `decide_experiment` with respx mocks in `tests/test_api_client_experiments.py` — verify maybe_scoped_path, no trailing slash on entry endpoints, conclude always sends body; include error-path tests for invalid state transitions (launch non-draft → 400, conclude non-active → 400, decide non-concluded → 400) and 404 (not found)
- [X] T031 [P] [US2] Write workspace method tests for experiment CRUD + lifecycle in `tests/test_workspace_experiments.py`

### Implementation for User Story 2

- [X] T032 [US2] Add `list_experiments(include_archived)` API client method using `maybe_scoped_path("experiments")` and GET in `src/mixpanel_data/_internal/api_client.py`
- [X] T033 [P] [US2] Add `create_experiment(params)` API client method using POST `experiments/` in `src/mixpanel_data/_internal/api_client.py`
- [X] T034 [P] [US2] Add `get_experiment(experiment_id)` API client method using GET `experiments/{id}` (no trailing slash) in `src/mixpanel_data/_internal/api_client.py`
- [X] T035 [P] [US2] Add `update_experiment(experiment_id, params)` API client method using PATCH `experiments/{id}` in `src/mixpanel_data/_internal/api_client.py`
- [X] T036 [P] [US2] Add `delete_experiment(experiment_id)` API client method using DELETE `experiments/{id}` in `src/mixpanel_data/_internal/api_client.py`
- [X] T037 [P] [US2] Add `launch_experiment(experiment_id)` API client method using PUT `experiments/{id}/launch` in `src/mixpanel_data/_internal/api_client.py`
- [X] T038 [P] [US2] Add `conclude_experiment(experiment_id, params)` API client method using PUT `experiments/{id}/force_conclude` — always send JSON body (empty `{}` if params is None) in `src/mixpanel_data/_internal/api_client.py`
- [X] T039 [P] [US2] Add `decide_experiment(experiment_id, params)` API client method using PATCH `experiments/{id}/decide` in `src/mixpanel_data/_internal/api_client.py`
- [X] T040 [US2] Add `list_experiments`, `create_experiment`, `get_experiment`, `update_experiment`, `delete_experiment`, `launch_experiment`, `conclude_experiment`, `decide_experiment` workspace methods in `src/mixpanel_data/workspace.py`

**Checkpoint**: Experiment CRUD + lifecycle works through library API. Tests pass.

---

## Phase 5: User Story 3 — Flag Lifecycle Operations (Priority: P2)

**Goal**: Users can archive, restore, and duplicate feature flags.

**Independent Test**: Create a flag, archive it, verify excluded from default list, restore it, duplicate it.

### Tests for User Story 3

- [X] T041 [P] [US3] Write API client tests for `archive_feature_flag`, `restore_feature_flag`, `duplicate_feature_flag` with respx mocks in `tests/test_api_client_flags.py` (append to existing file)
- [X] T042 [P] [US3] Write workspace method tests for archive, restore, duplicate in `tests/test_workspace_flags.py` (append to existing file)

### Implementation for User Story 3

- [X] T043 [P] [US3] Add `archive_feature_flag(flag_id)` API client method using POST `feature-flags/{id}/archive/` in `src/mixpanel_data/_internal/api_client.py`
- [X] T044 [P] [US3] Add `restore_feature_flag(flag_id)` API client method using DELETE `feature-flags/{id}/archive/` in `src/mixpanel_data/_internal/api_client.py`
- [X] T045 [P] [US3] Add `duplicate_feature_flag(flag_id)` API client method using POST `feature-flags/{id}/duplicate/` in `src/mixpanel_data/_internal/api_client.py`
- [X] T046 [US3] Add `archive_feature_flag`, `restore_feature_flag`, `duplicate_feature_flag` workspace methods in `src/mixpanel_data/workspace.py`

**Checkpoint**: Flag lifecycle operations work. Tests pass.

---

## Phase 6: User Story 4 — Flag Test Users and History (Priority: P2)

**Goal**: Users can set test user overrides, view flag change history, and check account limits.

**Independent Test**: Set test users on a flag, query history, query limits — all return correctly typed data.

### Tests for User Story 4

- [X] T047 [P] [US4] Write API client tests for `set_flag_test_users`, `get_flag_history`, `get_flag_limits` with respx mocks in `tests/test_api_client_flags.py` (append)
- [X] T048 [P] [US4] Write workspace method tests for set_flag_test_users, get_flag_history, get_flag_limits in `tests/test_workspace_flags.py` (append)

### Implementation for User Story 4

- [X] T049 [P] [US4] Add `set_flag_test_users(flag_id, params)` API client method using PUT `feature-flags/{id}/test-users/` in `src/mixpanel_data/_internal/api_client.py`
- [X] T050 [P] [US4] Add `get_flag_history(flag_id, params)` API client method using GET `feature-flags/{id}/history/` with query params in `src/mixpanel_data/_internal/api_client.py`
- [X] T051 [P] [US4] Add `get_flag_limits()` API client method using GET `feature-flags/limits/` (uses `maybe_scoped_path`, not `require_scoped_path`) in `src/mixpanel_data/_internal/api_client.py`
- [X] T052 [US4] Add `set_flag_test_users`, `get_flag_history`, `get_flag_limits` workspace methods in `src/mixpanel_data/workspace.py`

**Checkpoint**: Flag test users, history, and limits work. Tests pass.

---

## Phase 7: User Story 5 — Experiment Extended Operations (Priority: P2)

**Goal**: Users can archive, restore, duplicate experiments and list ERF experiments.

**Independent Test**: Archive an experiment, restore it, duplicate it, list ERF experiments.

### Tests for User Story 5

- [X] T053 [P] [US5] Write API client tests for `archive_experiment`, `restore_experiment`, `duplicate_experiment`, `list_erf_experiments` with respx mocks in `tests/test_api_client_experiments.py` (append)
- [X] T054 [P] [US5] Write workspace method tests for archive, restore, duplicate, list_erf in `tests/test_workspace_experiments.py` (append)

### Implementation for User Story 5

- [X] T055 [P] [US5] Add `archive_experiment(experiment_id)` API client method using POST `experiments/{id}/archive` in `src/mixpanel_data/_internal/api_client.py`
- [X] T056 [P] [US5] Add `restore_experiment(experiment_id)` API client method using DELETE `experiments/{id}/archive` in `src/mixpanel_data/_internal/api_client.py`
- [X] T057 [P] [US5] Add `duplicate_experiment(experiment_id, params)` API client method using POST `experiments/{id}/duplicate` in `src/mixpanel_data/_internal/api_client.py`
- [X] T058 [P] [US5] Add `list_erf_experiments()` API client method using GET `experiments/erf/` in `src/mixpanel_data/_internal/api_client.py`
- [X] T059 [US5] Add `archive_experiment`, `restore_experiment`, `duplicate_experiment`, `list_erf_experiments` workspace methods in `src/mixpanel_data/workspace.py`

**Checkpoint**: All experiment operations work. Tests pass.

---

## Phase 8: User Story 6 — CLI Commands (Priority: P3)

**Goal**: All flag and experiment operations are accessible via `mp flags` and `mp experiments` CLI command groups.

**Independent Test**: Run each CLI subcommand and verify it produces correct output in all 5 formats.

### Tests for User Story 6

- [X] T060 [P] [US6] Write CLI integration tests for all `mp flags` subcommands (list, create, get, update, delete, archive, restore, duplicate, set-test-users, history, limits) in `tests/test_cli_flags.py`
- [X] T061 [P] [US6] Write CLI integration tests for all `mp experiments` subcommands (list, create, get, update, delete, launch, conclude, decide, archive, restore, duplicate, erf) in `tests/test_cli_experiments.py`

### Implementation for User Story 6

- [X] T062 [US6] Create `src/mixpanel_data/cli/commands/flags.py` with `flags_app` Typer group and 11 subcommands: list, create, get, update, delete, archive, restore, duplicate, set-test-users, history, limits — follow dashboards.py pattern (@handle_errors, get_workspace, status_spinner, output_result, FormatOption, JqOption)
- [X] T063 [P] [US6] Create `src/mixpanel_data/cli/commands/experiments.py` with `experiments_app` Typer group and 12 subcommands: list, create, get, update, delete, launch, conclude, decide, archive, restore, duplicate, erf — follow dashboards.py pattern
- [X] T064 [US6] Register `flags_app` and `experiments_app` in `src/mixpanel_data/cli/main.py` (add_typer calls)

**Checkpoint**: All CLI commands work. `mp flags --help` and `mp experiments --help` show subcommands. Tests pass.

---

## Phase 9: Polish & Cross-Cutting Concerns

**Purpose**: Property-based tests, quality verification, documentation.

- [X] T065 [P] Write property-based tests for `FeatureFlagStatus`, `ServingMethod`, `FlagContractStatus`, `ExperimentStatus` enum round-trips and `FeatureFlag` model serialization invariants in `tests/test_types_feature_flags_pbt.py`
- [X] T066 [P] Write property-based tests for `Experiment`, `ExperimentCreator` serialization invariants in `tests/test_types_experiments_pbt.py`
- [X] T067 Run `just check` (ruff format + ruff check + mypy --strict + pytest) and fix all issues
- [X] T068 Run `just test-cov` and verify 90%+ coverage on all new code
- [X] T069 Validate quickstart.md examples execute correctly against mock/test setup
- [X] T070 Update `src/mixpanel_data/cli/commands/CLAUDE.md` if it exists, or add docstrings per CLAUDE.md standards

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: No dependencies — start immediately
- **Phase 2 (Foundational)**: Depends on Phase 1 (enums must exist before entity models)
- **Phase 3 (US1 — Flag CRUD)**: Depends on Phase 2 (types must be defined)
- **Phase 4 (US2 — Experiment Lifecycle)**: Depends on Phase 2 — can run in PARALLEL with Phase 3
- **Phase 5 (US3 — Flag Lifecycle)**: Depends on Phase 3 (flag CRUD api_client methods must exist)
- **Phase 6 (US4 — Flag Test Users/History)**: Depends on Phase 3 (flag API client infrastructure)
- **Phase 7 (US5 — Experiment Extended)**: Depends on Phase 4 (experiment API client infrastructure)
- **Phase 8 (US6 — CLI)**: Depends on Phases 3-7 (all workspace methods must exist)
- **Phase 9 (Polish)**: Depends on all previous phases

### User Story Dependencies

- **US1 (Flag CRUD)** + **US2 (Experiment Lifecycle)**: Independent, can run in parallel after Phase 2
- **US3 (Flag Lifecycle)** + **US4 (Flag Test Users/History)**: Both depend on US1, can run in parallel with each other
- **US5 (Experiment Extended)**: Depends on US2, can run in parallel with US3/US4
- **US6 (CLI)**: Depends on US1-US5 (all workspace methods)

### Within Each User Story

- Tests MUST be written and FAIL before implementation
- API client methods before workspace methods
- Workspace methods before CLI commands
- Commit after each logical group

### Parallel Opportunities

- Phase 1: All 5 enum/type tasks are parallel (different types, same file but independent additions)
- Phase 2: All param/response models are parallel with each other (T007-T018)
- Phase 3 + Phase 4: US1 and US2 can run in parallel (flags vs experiments — different API domains)
- Phase 5 + Phase 6 + Phase 7: US3, US4, US5 can run in parallel (independent API methods)
- Phase 8: flags.py and experiments.py CLI files can be created in parallel (T062 || T063)

---

## Parallel Example: User Story 1 + User Story 2

```bash
# After Phase 2 completes, launch both P1 stories in parallel:

# Agent A: Feature Flag CRUD (US1)
Task: "Write flag type tests in tests/test_types_feature_flags.py"
Task: "Write flag API client tests in tests/test_api_client_flags.py"
Task: "Write flag workspace tests in tests/test_workspace_flags.py"
# Then implement flag API client methods + workspace methods

# Agent B: Experiment Lifecycle (US2)
Task: "Write experiment type tests in tests/test_types_experiments.py"
Task: "Write experiment API client tests in tests/test_api_client_experiments.py"
Task: "Write experiment workspace tests in tests/test_workspace_experiments.py"
# Then implement experiment API client methods + workspace methods
```

---

## Implementation Strategy

### MVP First (User Stories 1 + 2)

1. Complete Phase 1: Setup (enums)
2. Complete Phase 2: Foundational (all Pydantic models)
3. Complete Phase 3: Flag CRUD (US1) — **MVP for flags**
4. Complete Phase 4: Experiment Lifecycle (US2) — **MVP for experiments**
5. **STOP and VALIDATE**: Both core domains work independently
6. Run `just check` to verify quality gates

### Incremental Delivery

1. Setup + Foundational → Types ready
2. Flag CRUD (US1) + Experiment Lifecycle (US2) → Core MVP
3. Flag Lifecycle (US3) + Flag Test Users (US4) + Experiment Extended (US5) → Full API
4. CLI Commands (US6) → Full user-facing interface
5. Polish (Phase 9) → Production-ready

### Parallel Team Strategy

With 2 agents:

1. Both complete Setup + Foundational together
2. Agent A: US1 (Flag CRUD) → US3 (Flag Lifecycle) → US4 (Flag Test Users)
3. Agent B: US2 (Experiment Lifecycle) → US5 (Experiment Extended) → CLI experiments
4. Agent A picks up CLI flags
5. Both polish together

---

## Notes

- [P] tasks = different files, no dependencies (for same-file tasks, [P] means no logical dependency — execute sequentially within the file)
- [Story] label maps task to specific user story for traceability
- FR-029 (error propagation) is covered by convention: existing `app_request()` maps HTTP status codes to exceptions, and `@handle_errors` in CLI maps exceptions to exit codes. Error-path tests in T021 and T030 verify this.
- Feature flag IDs are **strings (UUIDs)**, not integers
- Feature flag update uses **PUT** (full replacement), not PATCH
- Experiment entry endpoints have **no trailing slash** — critical for URL construction
- `conclude_experiment` always sends a JSON body, even when empty
- Feature flags use `require_scoped_path` (workspace-required); experiments use `maybe_scoped_path`
- All Pydantic models need `ConfigDict(frozen=True, extra="allow", populate_by_name=True)` for response types
- Follow existing patterns in dashboards.py, reports.py, cohorts.py for consistency
- Commit after each task or logical group
