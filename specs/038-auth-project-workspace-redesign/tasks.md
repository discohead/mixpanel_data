# Tasks: Auth, Project & Workspace Management Redesign

**Input**: Design documents from `/specs/038-auth-project-workspace-redesign/`  
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/  
**Tests**: Included (project mandates strict TDD per CLAUDE.md)

## Format: `[ID] [P?] [Story?] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Phase 1: Setup

**Purpose**: Create new files and establish module structure

- [X] T001 Create new module file `src/mixpanel_data/_internal/auth_credential.py` with module docstring and imports
- [X] T002 [P] Create new module file `src/mixpanel_data/_internal/me.py` with module docstring and imports
- [X] T003 [P] Create new test file `tests/unit/test_auth_credential.py` with imports and fixtures
- [X] T004 [P] Create new test file `tests/unit/test_me.py` with imports and fixtures
- [X] T005 [P] Create new test file `tests/unit/test_config_v2.py` with imports and fixtures
- [X] T006 [P] Create new test file `tests/unit/test_migration.py` with imports and fixtures
- [X] T006b [P] Create new test file `tests/pbt/test_config_pbt.py` with imports and Hypothesis profile configuration

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core types that ALL user stories depend on — must complete before any story work

**CRITICAL**: No user story work can begin until this phase is complete

### Tests for Foundation

- [X] T007 [P] Write unit tests for `CredentialType` enum in `tests/unit/test_auth_credential.py`
- [X] T008 [P] Write unit tests for `AuthCredential` model (construction, validation, auth_header for both SA and OAuth) in `tests/unit/test_auth_credential.py`
- [X] T009 [P] Write unit tests for `ProjectContext` model (construction, validation, optional fields) in `tests/unit/test_auth_credential.py`
- [X] T010 [P] Write unit tests for `ResolvedSession` model (construction, properties, auth_header delegation) in `tests/unit/test_auth_credential.py`
- [X] T011 [P] Write unit tests for `MeOrgInfo`, `MeProjectInfo`, `MeWorkspaceInfo` models (construction, extra="allow" forward compat) in `tests/unit/test_me.py`
- [X] T012 [P] Write unit tests for `MeResponse` model (construction, extra="allow", serialization round-trip) in `tests/unit/test_me.py`
- [X] T013 [P] Write unit tests for `MeCache` (get, put, TTL expiry, invalidate, file permissions) in `tests/unit/test_me.py`

### Implementation for Foundation

- [X] T014 [P] Implement `CredentialType` enum and `AuthCredential` model in `src/mixpanel_data/_internal/auth_credential.py`
- [X] T015 [P] Implement `ProjectContext` model in `src/mixpanel_data/_internal/auth_credential.py`
- [X] T016 Implement `ResolvedSession` model in `src/mixpanel_data/_internal/auth_credential.py` (depends on T014, T015)
- [X] T017 [P] Implement `MeOrgInfo`, `MeProjectInfo`, `MeWorkspaceInfo` models in `src/mixpanel_data/_internal/me.py`
- [X] T018 Implement `MeResponse` model in `src/mixpanel_data/_internal/me.py` (depends on T017)
- [X] T019 Implement `MeCache` class (get, put, invalidate, TTL, file permissions) in `src/mixpanel_data/_internal/me.py`
- [X] T020 Add `to_resolved_session()` method to existing `Credentials` class in `src/mixpanel_data/_internal/config.py`
- [X] T021 Write unit test for `Credentials.to_resolved_session()` in `tests/unit/test_config_v2.py`
- [X] T022 Re-export `AuthCredential`, `ProjectContext`, `ResolvedSession`, `CredentialType` from `src/mixpanel_data/auth.py`
- [X] T023 Add new public types to `src/mixpanel_data/__init__.py` exports
- [X] T024 Run `just check` to verify all foundation types pass lint, typecheck, and tests

**Checkpoint**: Foundation types complete. All new models are tested, typed, and exported. `just check` passes.

---

## Phase 3: User Story 1 — Add Credentials Without Project Binding (Priority: P1)

**Goal**: Users can register credentials (username + secret + region) without specifying a project ID

**Independent Test**: Run `mp auth add my-sa -u "user"` without `--project`, verify credential stored in config without project_id

### Tests for User Story 1

- [X] T025 [P] [US1] Write tests for `ConfigManager.add_credential()` (SA type, OAuth type, duplicate name error) in `tests/unit/test_config_v2.py`
- [X] T026 [P] [US1] Write tests for `ConfigManager.list_credentials()` and `remove_credential()` in `tests/unit/test_config_v2.py`
- [X] T027 [P] [US1] Write tests for v2 config schema detection (`config_version()` method) in `tests/unit/test_config_v2.py`
- [X] T028 [P] [US1] Write tests for `CredentialInfo` and `ActiveContext` dataclasses in `tests/unit/test_config_v2.py`

### Implementation for User Story 1

- [X] T029 [US1] Add `CredentialInfo` and `ActiveContext` dataclasses to `src/mixpanel_data/_internal/config.py`
- [X] T030 [US1] Implement `ConfigManager.config_version()` method in `src/mixpanel_data/_internal/config.py`
- [X] T031 [US1] Implement `ConfigManager.add_credential()` method in `src/mixpanel_data/_internal/config.py`
- [X] T032 [US1] Implement `ConfigManager.list_credentials()` and `remove_credential()` methods in `src/mixpanel_data/_internal/config.py`
- [X] T033 [US1] Implement atomic config writes (temp file + `os.replace()`) in `ConfigManager._write_config()` in `src/mixpanel_data/_internal/config.py`
- [X] T034 [US1] Update `mp auth add` command to make `--project` optional in `src/mixpanel_data/cli/commands/auth.py`
- [X] T035 [US1] Write CLI test for `mp auth add` without `--project` in `tests/unit/cli/test_auth_cli.py` (or existing auth test file)
- [X] T036 [US1] Run `just check` to verify US1 passes all checks

**Checkpoint**: Users can add credentials without project binding. `mp auth add my-sa -u "user"` works.

---

## Phase 4: User Story 2 — Discover Accessible Projects (Priority: P1)

**Goal**: Users can list all projects they have access to via the /me API with disk caching

**Independent Test**: Run `mp projects list` after adding credentials, verify project list is displayed

### Tests for User Story 2

- [X] T037 [P] [US2] Write tests for `MeService.fetch()` (cache hit, cache miss, force_refresh) with mocked HTTP in `tests/unit/test_me.py`
- [X] T038 [P] [US2] Write tests for `MeService.list_projects()` and `find_project()` in `tests/unit/test_me.py`
- [X] T039 [P] [US2] Write tests for `MixpanelAPIClient.me()` endpoint method with wiremock in `tests/unit/test_api_client.py` (or existing file)
- [X] T040 [P] [US2] Write tests for `Workspace.discover_projects()` and `Workspace.me()` in `tests/unit/test_workspace.py` (or existing file)

### Implementation for User Story 2

- [X] T041 [US2] Implement `MeService` class (fetch, list_projects, find_project, list_workspaces, find_default_workspace) in `src/mixpanel_data/_internal/me.py`
- [X] T041b [US2] Handle 403/401 from /me endpoint in `MeService.fetch()` — fall back gracefully with clear error directing user to specify --project explicitly in `src/mixpanel_data/_internal/me.py`
- [X] T041c [P] [US2] Write test for /me API 403 fallback (service account without user_details scope) in `tests/unit/test_me.py`
- [X] T042 [US2] Add `me()` method to `MixpanelAPIClient` (GET /api/app/me) in `src/mixpanel_data/_internal/api_client.py`
- [X] T043 [US2] Add `me()` and `discover_projects()` methods to `Workspace` class in `src/mixpanel_data/workspace.py`
- [X] T044 [US2] Create `mp projects` command group with `list` and `refresh` subcommands in `src/mixpanel_data/cli/commands/projects.py`
- [X] T045 [US2] Register `projects` command group in `src/mixpanel_data/cli/main.py`
- [X] T046 [P] [US2] Write CLI tests for `mp projects list` and `mp projects refresh` in `tests/unit/cli/test_projects_cli.py`
- [X] T047 [US2] Add /me cache invalidation to `mp auth logout` in `src/mixpanel_data/cli/commands/auth.py`
- [X] T048 [US2] Add /me cache invalidation to `mp auth login` in `src/mixpanel_data/cli/commands/auth.py`
- [X] T049 [US2] Run `just check` to verify US2 passes all checks

**Checkpoint**: `mp projects list` displays all accessible projects. Cache works with 24h TTL.

---

## Phase 5: User Story 3 — Select and Persist Active Project (Priority: P1)

**Goal**: Users can select an active project that persists across sessions

**Independent Test**: Run `mp projects switch <id>`, close terminal, reopen, run query — confirms persistent selection

### Tests for User Story 3

- [X] T050 [P] [US3] Write tests for `ConfigManager.set_active_project()`, `set_active_credential()`, `get_active_context()` in `tests/unit/test_config_v2.py`
- [X] T051 [P] [US3] Write tests for `ConfigManager.resolve_session()` (env vars, explicit params, active context, OAuth fallback) in `tests/unit/test_config_v2.py`
- [X] T052 [P] [US3] Write tests for `MixpanelAPIClient` accepting `ResolvedSession` in constructor in `tests/unit/test_api_client.py`

### Implementation for User Story 3

- [X] T053 [US3] Implement `ConfigManager.get_active_context()`, `set_active_credential()`, `set_active_project()`, `set_active_workspace()` in `src/mixpanel_data/_internal/config.py`
- [X] T054 [US3] Implement `ConfigManager.resolve_session()` with full priority chain in `src/mixpanel_data/_internal/config.py`
- [X] T055 [US3] Implement `ConfigManager._resolve_session_v1()` for legacy config support in `src/mixpanel_data/_internal/config.py`
- [X] T056 [US3] Implement `ConfigManager._resolve_session_v2()` for new config support in `src/mixpanel_data/_internal/config.py`
- [X] T057 [US3] Update `MixpanelAPIClient.__init__()` to accept `Credentials | ResolvedSession` in `src/mixpanel_data/_internal/api_client.py`
- [X] T058 [US3] Update `Workspace.__init__()` to accept `credential` and `session` params; use `resolve_session()` in `src/mixpanel_data/workspace.py`
- [X] T059 [US3] Add `mp projects switch` and `mp projects show` subcommands in `src/mixpanel_data/cli/commands/projects.py`
- [X] T060 [US3] Add `--credential` and `--project` global options to `src/mixpanel_data/cli/main.py`
- [X] T061 [US3] Update `get_workspace()` helper in `src/mixpanel_data/cli/utils.py` to use `resolve_session()`
- [X] T062 [P] [US3] Write CLI tests for `mp projects switch` and `mp projects show` in `tests/unit/cli/test_projects_cli.py`
- [X] T063 [US3] Run `just check` to verify US3 passes all checks

**Checkpoint**: `mp projects switch <id>` persists selection. New sessions use persisted project. `Workspace(credential="x", project_id="y")` works.

---

## Phase 6: User Story 4 — Discover and Select Workspaces (Priority: P2)

**Goal**: Users can list workspaces for a project and select one that persists

**Independent Test**: Run `mp workspaces list`, `mp workspaces switch <id>`, verify persistence

### Tests for User Story 4

- [X] T064 [P] [US4] Write tests for `MeService.list_workspaces()` and `find_default_workspace()` in `tests/unit/test_me.py`
- [X] T065 [P] [US4] Write tests for `Workspace.discover_workspaces()` in `tests/unit/test_workspace.py`
- [X] T065b [P] [US4] Write test for auto-select default workspace when project switched without explicit workspace_id in `tests/unit/test_workspace.py`

### Implementation for User Story 4

- [X] T066 [US4] Add `discover_workspaces()` method and default-workspace auto-selection logic to `Workspace` class in `src/mixpanel_data/workspace.py`
- [X] T067 [US4] Create `mp workspaces` command group with `list`, `switch`, `show` subcommands in `src/mixpanel_data/cli/commands/workspaces_cmd.py`
- [X] T068 [US4] Register `workspaces` command group in `src/mixpanel_data/cli/main.py`
- [X] T069 [P] [US4] Write CLI tests for `mp workspaces list`, `switch`, `show` in `tests/unit/cli/test_workspaces_cli.py`
- [X] T070 [US4] Run `just check` to verify US4 passes all checks

**Checkpoint**: `mp workspaces list` and `mp workspaces switch` work. Workspace persists in config.

---

## Phase 7: User Story 5 — Switch Projects In-Session (Priority: P2)

**Goal**: Python API supports in-session project/workspace switching without new Workspace instance

**Independent Test**: Create Workspace, call `switch_project()`, verify subsequent queries target new project

### Tests for User Story 5

- [X] T071 [P] [US5] Write tests for `Workspace.switch_project()` (switches project, clears discovery cache, keeps auth) in `tests/unit/test_workspace.py`
- [X] T072 [P] [US5] Write tests for `Workspace.switch_workspace()` in `tests/unit/test_workspace.py`
- [X] T073 [P] [US5] Write tests for `MixpanelAPIClient.with_project()` factory method in `tests/unit/test_api_client.py`
- [X] T074 [P] [US5] Write tests for `Workspace.current_project` and `current_credential` properties in `tests/unit/test_workspace.py`

### Implementation for User Story 5

- [X] T075 [US5] Implement `MixpanelAPIClient.with_project()` factory method in `src/mixpanel_data/_internal/api_client.py`
- [X] T076 [US5] Implement `Workspace.switch_project()` (new API client, clear discovery cache) in `src/mixpanel_data/workspace.py`
- [X] T077 [US5] Implement `Workspace.switch_workspace()` in `src/mixpanel_data/workspace.py`
- [X] T078 [US5] Implement `Workspace.current_project` and `current_credential` properties in `src/mixpanel_data/workspace.py`
- [X] T079 [US5] Run `just check` to verify US5 passes all checks

**Checkpoint**: `ws.switch_project("id")` works in-session. Discovery cache clears. `current_project` reflects changes.

---

## Phase 8: User Story 6 — Migrate Existing Configuration (Priority: P2)

**Goal**: Users can migrate v1 config to v2 format safely with backup

**Independent Test**: Run `mp auth migrate` on v1 config, verify v2 output, backup created, all projects accessible

### Tests for User Story 6

- [X] T080 [P] [US6] Write tests for `ConfigManager.migrate_v1_to_v2()` (credential grouping, alias creation, backup, active context) in `tests/unit/test_migration.py`
- [X] T081 [P] [US6] Write tests for migration edge cases (already v2, empty config, single account) in `tests/unit/test_migration.py`
- [X] T082 [P] [US6] Write property-based test for migration round-trip (v1 projects accessible after migration) in `tests/pbt/test_config_pbt.py`

### Implementation for User Story 6

- [X] T083 [US6] Add `MigrationResult` dataclass to `src/mixpanel_data/_internal/config.py`
- [X] T084 [US6] Implement `ConfigManager.migrate_v1_to_v2()` (group credentials, create aliases, set active, backup) in `src/mixpanel_data/_internal/config.py`
- [X] T085 [US6] Add `mp auth migrate` subcommand with `--dry-run` in `src/mixpanel_data/cli/commands/auth.py`
- [X] T086 [P] [US6] Write CLI test for `mp auth migrate` and `--dry-run` in `tests/unit/cli/test_auth_cli.py`
- [X] T087 [US6] Run `just check` to verify US6 passes all checks

**Checkpoint**: `mp auth migrate` correctly converts v1 → v2. Backup created. All projects still accessible.

---

## Phase 9: User Story 9 — OAuth Authentication with Project Discovery (Priority: P2)

**Goal**: OAuth login works without project_id; project context comes from active config

**Independent Test**: Run `mp auth login` without --project, then `mp projects list`, then `mp projects switch`

### Tests for User Story 9

- [X] T088 [P] [US9] Write tests for OAuth credential resolution via `resolve_session()` (uses active.project_id, not token.project_id) in `tests/unit/test_config_v2.py`
- [X] T089 [P] [US9] Write tests for OAuth credential entry in v2 config (type="oauth") in `tests/unit/test_config_v2.py`

### Implementation for User Story 9

- [X] T090 [US9] Update `_resolve_from_oauth()` in `ConfigManager` to use `active.project_id` from config instead of token's project_id in `src/mixpanel_data/_internal/config.py`
- [X] T091 [US9] Ensure `mp auth login` invalidates /me cache and suggests `mp projects list` in `src/mixpanel_data/cli/commands/auth.py`
- [X] T092 [US9] Add OAuth credential entry support to `add_credential()` (type="oauth") in `src/mixpanel_data/_internal/config.py`
- [X] T093 [US9] Run `just check` to verify US9 passes all checks

**Checkpoint**: OAuth login → `mp projects list` → `mp projects switch` flow works end-to-end.

---

## Phase 10: User Story 7 — Create and Use Project Aliases (Priority: P3)

**Goal**: Named project aliases for quick context switching

**Independent Test**: Create alias, switch to it, verify correct credential + project active

### Tests for User Story 7

- [X] T094 [P] [US7] Write tests for `ConfigManager.add_project_alias()`, `list_project_aliases()`, `remove_project_alias()` in `tests/unit/test_config_v2.py`
- [X] T095 [P] [US7] Write tests for `ProjectAlias` dataclass in `tests/unit/test_config_v2.py`

### Implementation for User Story 7

- [X] T096 [US7] Add `ProjectAlias` dataclass to `src/mixpanel_data/_internal/config.py`
- [X] T097 [US7] Implement `ConfigManager.add_project_alias()`, `list_project_aliases()`, `remove_project_alias()` in `src/mixpanel_data/_internal/config.py`
- [X] T098 [US7] Add `mp projects alias add`, `alias remove`, `alias list` subcommands in `src/mixpanel_data/cli/commands/projects.py`
- [X] T099 [P] [US7] Write CLI tests for `mp projects alias` subcommands in `tests/unit/cli/test_projects_cli.py`
- [X] T100 [US7] Run `just check` to verify US7 passes all checks

**Checkpoint**: Project aliases can be created, listed, removed. Used by `mp context switch`.

---

## Phase 11: User Story 8 — View Current Context (Priority: P3)

**Goal**: Users can see their full current context (credential + project + workspace)

**Independent Test**: Run `mp context show`, verify output shows all three dimensions

### Tests for User Story 8

- [X] T101 [P] [US8] Write CLI tests for `mp context show` and `mp context switch` in `tests/unit/cli/test_context_cli.py`

### Implementation for User Story 8

- [X] T102 [US8] Create `mp context` command group with `show` and `switch` subcommands in `src/mixpanel_data/cli/commands/context.py`
- [X] T103 [US8] Register `context` command group in `src/mixpanel_data/cli/main.py`
- [X] T104 [US8] Run `just check` to verify US8 passes all checks

**Checkpoint**: `mp context show` displays full context. `mp context switch <alias>` switches everything.

---

## Phase 12: User Story 10 — Environment Variable Override (Priority: P3)

**Goal**: Verify existing env var override behavior is preserved in new resolution chain

**Independent Test**: Set all 4 env vars, run query, verify env vars take priority over everything

### Tests for User Story 10

- [X] T105 [P] [US10] Write tests verifying env vars override active context, OAuth, and explicit params in `tests/unit/test_config_v2.py`
- [X] T106 [P] [US10] Write tests verifying partial env vars do NOT trigger env resolution in `tests/unit/test_config_v2.py`

### Implementation for User Story 10

- [X] T107 [US10] Verify `resolve_session()` preserves env var priority (should already work from T054) in `src/mixpanel_data/_internal/config.py`
- [X] T108 [US10] Run `just check` to verify US10 passes all checks

**Checkpoint**: Env var override works exactly as before. No regressions.

---

## Phase 13: Polish & Cross-Cutting Concerns

**Purpose**: Improvements that affect multiple user stories

- [X] T109 [P] Add `ProjectNotFoundError` to `src/mixpanel_data/exceptions.py`
- [X] T110 [P] Update `mp auth list` to show credentials (v2) or accounts (v1) based on config version in `src/mixpanel_data/cli/commands/auth.py`
- [X] T111 [P] Enhance `mp auth status` to show active context in `src/mixpanel_data/cli/commands/auth.py`
- [X] T112 [P] Add /me cache management to `OAuthStorage` (clear_me on logout/clear_all) in `src/mixpanel_data/_internal/auth/storage.py`
- [X] T112b [P] Add orphaned alias warning to `ConfigManager.remove_credential()` — warn when project aliases still reference the removed credential in `src/mixpanel_data/_internal/config.py`
- [X] T112c [P] Write test for orphaned alias warning on credential removal in `tests/unit/test_config_v2.py`
- [X] T113 [P] Write property-based tests for config v2 round-trip (write → read = identity) in `tests/pbt/test_config_pbt.py`
- [X] T114 Update plugin `auth_manager.py` for v2 config in `mixpanel-plugin/skills/mixpanel-analyst/scripts/auth_manager.py`
- [X] T115 Run full test suite with coverage: `just test-cov` (must be >= 90%)
- [X] T116 Run `just check` for final verification (lint + typecheck + tests)
- [X] T117 Validate quickstart.md scenarios work end-to-end

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: No dependencies — can start immediately
- **Phase 2 (Foundational)**: Depends on Phase 1 — BLOCKS all user stories
- **Phases 3-5 (US1, US2, US3)**: Depend on Phase 2 — MUST be sequential (US1 → US2 → US3) because each builds on prior config infrastructure
- **Phases 6-9 (US4, US5, US6, US9)**: Depend on Phase 5 — can run in parallel after US3 complete
- **Phases 10-12 (US7, US8, US10)**: Depend on Phase 5 — can run in parallel after US3 complete
- **Phase 13 (Polish)**: Depends on all desired user stories being complete

### User Story Dependencies

- **US1 (P1)**: After Foundational → Adds credential CRUD to ConfigManager
- **US2 (P1)**: After US1 → Adds /me API + project discovery (needs credentials to exist)
- **US3 (P1)**: After US2 → Adds active context + resolve_session (needs discovery for project info)
- **US4 (P2)**: After US3 → Adds workspace discovery (needs active project)
- **US5 (P2)**: After US3 → Adds in-session switching (needs resolve_session + API client changes)
- **US6 (P2)**: After US3 → Adds migration (needs v2 config CRUD to be complete)
- **US9 (P2)**: After US3 → Adds OAuth flow changes (needs resolve_session)
- **US7 (P3)**: After US3 → Adds aliases (needs project CRUD in config)
- **US8 (P3)**: After US7 → Adds context commands (needs aliases for `mp context switch`)
- **US10 (P3)**: After US3 → Verifies env var behavior (needs resolve_session)

### Within Each User Story

- Tests MUST be written and FAIL before implementation
- Type definitions before service logic
- Config layer before API client changes
- API client before Workspace facade
- Workspace before CLI commands
- `just check` at each checkpoint

### Parallel Opportunities

**Phase 2**: T007-T013 (all tests) can run in parallel, then T014-T015 + T017 (models) in parallel
**Phase 3**: T025-T028 (tests) in parallel
**Phase 6-9**: US4, US5, US6, US9 can all run in parallel after US3 completes
**Phase 10-12**: US7, US8, US10 can all run in parallel after US3 completes
**Phase 13**: T109-T113 can all run in parallel

---

## Parallel Example: Foundational Phase

```
# Launch all foundation tests in parallel:
T007: "Tests for CredentialType enum"
T008: "Tests for AuthCredential model"
T009: "Tests for ProjectContext model"
T010: "Tests for ResolvedSession model"
T011: "Tests for MeOrgInfo, MeProjectInfo, MeWorkspaceInfo"
T012: "Tests for MeResponse model"
T013: "Tests for MeCache"

# Then launch independent models in parallel:
T014: "Implement CredentialType + AuthCredential"
T015: "Implement ProjectContext"
T017: "Implement Me* info models"
```

## Parallel Example: P2 Stories After US3

```
# All four P2 stories can proceed simultaneously:
Agent A: Phase 6 (US4 — Workspaces)
Agent B: Phase 7 (US5 — In-Session Switching)
Agent C: Phase 8 (US6 — Migration)
Agent D: Phase 9 (US9 — OAuth)
```

---

## Implementation Strategy

### MVP First (US1 + US2 + US3 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (CRITICAL — blocks everything)
3. Complete Phase 3: US1 — Credentials without project binding
4. Complete Phase 4: US2 — Project discovery
5. Complete Phase 5: US3 — Persistent active project
6. **STOP and VALIDATE**: Users can add credentials, discover projects, switch projects, and persist selections
7. This MVP delivers the core value: decoupled auth + discovery + persistence

### Incremental Delivery

1. Setup + Foundational → Types ready
2. US1 → Credential-only add → Testable
3. US2 → Project discovery → Testable
4. US3 → Persistent switching → **MVP Complete**
5. US4-US9 (P2) → Workspaces, in-session switching, migration, OAuth → Each independently testable
6. US7-US10 (P3) → Aliases, context view, env vars → Polish
7. Phase 13 → Final polish, full coverage, quickstart validation

### Parallel Team Strategy

With multiple agents/developers:

1. Team completes Setup + Foundational together
2. Sequential: US1 → US2 → US3 (these build on each other)
3. Once US3 complete, fan out:
   - Agent A: US4 (Workspaces) + US7 (Aliases)
   - Agent B: US5 (In-Session Switching) + US8 (Context View)
   - Agent C: US6 (Migration) + US9 (OAuth) + US10 (Env Vars)
4. All converge for Phase 13 (Polish)

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Project mandates strict TDD: tests written FIRST, must FAIL before implementation
- `just check` at every checkpoint (lint + typecheck + test)
- Commit after each task or logical group
- All new code requires docstrings (Google style), type hints, and mypy --strict compliance
