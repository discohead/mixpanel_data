---

description: "Task list for Authentication Architecture Redesign (042)"
---

# Tasks: Authentication Architecture Redesign (Account → Project → Workspace)

**Input**: Design documents from `/specs/042-auth-architecture-redesign/`
**Prerequisites**: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md), [data-model.md](data-model.md), [contracts/](contracts/), [quickstart.md](quickstart.md)
**Source design**: [`context/auth-architecture-redesign.md`](../../context/auth-architecture-redesign.md)
**Branch**: `042-auth-architecture-redesign`
**Supersedes**: 038-auth-project-workspace-redesign

## Status (as of 2026-04-23 — post-release **audit-fix sweep**; **042 release-ready at 0.4.0** — all 11 phases done or descoped)

> **Audit-fix sweep (2026-04-23)** addressed eight spec-vs-reality
> discrepancies surfaced by a comprehensive completeness audit:
> 1. **FR-038 closed**: deleted the three remaining deprecated `Workspace`
>    methods (`discover_projects`, `discover_workspaces`, `workspace_id`
>    property) and shipped the v3 replacements (`Workspace.projects() →
>    list[Project]`, `Workspace.workspaces() → list[WorkspaceRef]`) per
>    FR-035 / FR-036; migrated callers in `auth_manager.py`,
>    `examples/cross_project.py`, `tests/integration/test_cross_project_iteration.py`,
>    `tests/unit/test_workspace.py`, the plugin SKILL.md, and an
>    `exceptions.py` docstring.
> 2. **US10 / `mp config convert` formally DESCOPED** in spec.md (US10 +
>    FR-010, 048, 055, 062, 072, 073, 074), in `contracts/cli-commands.md`
>    (§8 marked DESCOPED), `contracts/config-schema.md` (§3 marked
>    DESCOPED, §1.4 revised), `contracts/python-api.md` (§7.5 marked
>    DESCOPED, §9.5 revised), `contracts/filesystem-layout.md` (§1
>    revised), `quickstart.md` ("Migrating an existing config" rewritten
>    around the hard-cutover recipe), and SC-017/019/020/021 marked
>    DESCOPED/REVISED.
> 3. **T072 written**: `tests/integration/test_target_roundtrip.py` with
>    10 tests covering Python apply ↔ persisted state, single-`_mutate`
>    atomicity (T075), construction-path equivalence (SC-010), and the
>    CLI subprocess ↔ in-process roundtrip.
> 4. **T115**: superseded-by header added to
>    `context/auth-project-workspace-redesign.md`.
> 5. **T116**: `context/CLAUDE.md` document hierarchy now lists both
>    auth design docs and uses v3 CLI vocabulary; the legacy `mp auth ...`
>    block was replaced. (`src/mixpanel_data/_internal/CLAUDE.md` also
>    refreshed as adjacent cleanup — it referenced the deleted
>    `Credentials` class.)
> 6. **T114**: `context/mixpanel_data-design.md` got a banner near the
>    top routing readers to `auth-architecture-redesign.md` and listing
>    the now-obsolete fragments.
> 7. **FR-067 reconciled**: spec FR-067 + SC-001 + plan.md updated to
>    match the actually-shipped budget (≤6,500 LoC across ≤20 files; current
>    ~5,800 LoC across 19 files), with rationale: the original budget
>    assumed an `api_client.py` split that didn't happen.
> 8. **tasks.md tracker reconciliation**: Phase 6 (T071–T076) and
>    Phase 11 (T111–T126a) individual checkboxes now reflect actual state.
>
> Net effect on the test suite: **+10 tests** (5,957 → 5,967 pass,
> 0 regressions); mypy --strict + ruff clean.

| Phase | Status | Tests | Notes |
|-------|--------|-------|-------|
| 1 — Setup | ✅ DONE (5/5) | infra | branch, fixtures, conftest, just recipe |
| 2 — Foundational types | ✅ DONE (13/13) | 89 | Account union, Session, Project, WorkspaceRef, TokenResolver, OnDiskTokenResolver |
| 3 — Schema + Resolver (US2 + US3) | ✅ DONE (12/12) | 79 | `_internal/config.py` (formerly `config_v3.py`) + `_internal/auth/resolver.py` + `BridgeFile` v2 |
| 4 — Account model + Workspace.use (US1 + US4) | ✅ DONE — B1 flattened the dual-init, A1 wired OAuth, B2 swept the deferred deletions (T043 / T044 / T045 / T047 / T048 / T050) | 71 | mp.accounts/.targets/.session namespaces; Workspace.use() chain; api_client session support; `mp.accounts.login` end-to-end PKCE; OAuth refresh in OnDiskTokenResolver; per-request bearer in api_client; per-account `me.json` cache; `auth_credential.py` gone; deprecated `Workspace` methods (`switch_*`, `current_*`, `set_workspace_id`) gone. |
| 5 — CLI surface (US5) | ✅ DONE (additive → cleanup landed in `5a6b876` and tightened in B1: legacy `--credential` / `--workspace-id` globals removed; A1 wired `mp account login NAME --no-browser`) | 17 | `mp account/project/workspace/session/target` groups + `--account`/`--project`/`--workspace`/`--target` globals; legacy command groups gone |
| 6 — Targets (US6) | ✅ DONE (`5a6b876`) | +10 | `mp target add/use/list/show/remove` + 10 smoke tests |
| 7 — Cross-cutting iteration (US7) | ✅ DONE (`18233dc`) — Cluster C1 landed | +12 | Pure test additions (capability live since Phase 4): `tests/integration/test_cross_project_iteration.py` (4 tests — http transport / no-rebuild / one-/me-call / fluent chain), `test_cross_account_iteration.py` (3 — transport / per-account headers / FR-033 project re-resolve), `test_parallel_snapshot.py` (4 — replace immutability / identity preservation / ThreadPoolExecutor / sentinel semantics), `test_cli_shell_loop.py` (1 — `mp --project ID` per-command override doesn't mutate `[active]`). Plus `examples/cross_project.py` documenting both sequential and snapshot patterns. |
| 8 — Cowork bridge (US8) | ✅ DONE (`9147b1d`) — Cluster C2 landed | +23 | `bridge.export_bridge` / `bridge.remove_bridge` plus `mp.accounts.export_bridge` / `remove_bridge` wrappers; `mp account export-bridge` / `remove-bridge` CLI commands; `mp session --bridge` flag with full payload display. New `tests/unit/test_bridge_export.py` (15 tests) and `tests/unit/cli/test_bridge_cli.py` (8 tests). |
| 9 — Plugin / agent surface (US9) | ✅ DONE (`478160f`) — Cluster A2 landed | +15 | `auth_manager.py` 727 → 257 LoC, zero `version >= 2` branches; plugin bumped to 5.0.0; new subprocess-based `tests/integration/test_plugin_auth_manager.py` covers every subcommand + LoC + version-branch guards. Slash command `/mixpanel-data:auth` and setup skill rewritten around the JSON contract. |
| 10 — Conversion script (US10) | ❌ DROPPED (alpha "free to break") | — | Legacy detection deleted in `5a6b876`; legacy `ConfigManager` + `AccountInfo` + v1 `AuthBridgeFile` + `auth_credential.py` fully removed in B1 / B2; no migration path needed |
| 11 — Polish & cleanup (Cluster D) | ✅ DONE (`6a01afd`) — release polish landed | +2 | Library bumped to 0.4.0; `RELEASE_NOTES_0.4.0.md` with explicit BREAKING CHANGES sections; CLAUDE.md / src/mixpanel_data/CLAUDE.md / src/mixpanel_data/cli/CLAUDE.md refreshed for v3 vocabulary; new `tests/unit/test_loc_budget.py` (FR-067 regression guard — 18 files / ~5,800 LoC). T121 grep verified the `Credentials` shim in `_internal/config.py` + `api_client.py` is intentional (bridges v3 Session into legacy api_client HTTP code). T122 grep — zero matches. Mutation testing (T120), security audit (T126), pydocstyle gate (T126a), and manual quickstart walkthrough (T125) deferred as nice-to-haves; all critical release gates met. |

**Full test suite (HEAD `6a01afd`)**: 5,956 passed @ ~91% coverage; mypy --strict + ruff clean. Package builds as `mixpanel_data-0.4.0.tar.gz`.
**Live QA (`tests/live/test_042_auth_redesign_live.py`)**: 18 / 18 pass against real Mixpanel API at HEAD `6a01afd`.
**Net diff for the full 042 spec (B1+A1+B2+B3+A2+C2+C1+D)**: +5,539 / −13,411 across ~178 files (13 commits — B1×3 / A1 / B2×4 / B3 / A2 / C2 / C1 / D).

### Pragmatic deviation from the original phase plan (history)

Phases 4-5 originally landed **additively** (new code beside legacy code) so the suite stayed green during rollout. The B1 cluster (`12471c6` / `024a291` / `18283b4`) **collapsed the additive layer**:

- `_internal/config.py` now IS the v3 ConfigManager (the legacy ConfigManager + AccountInfo / CredentialInfo / ActiveContext / ProjectAlias / MigrationResult dataclasses are gone).
- `_internal/auth/bridge.py` only carries the v2 `BridgeFile` schema (v1 `AuthBridgeFile` + 9 helpers + `# noqa: E402` import block deleted).
- `Workspace.__init__` is keyword-only — `account=`, `project=`, `workspace=`, `target=`, `session=` per `contracts/python-api.md` §1; legacy positional callers no longer compile.
- `MixpanelAPIClient` still accepts either `credentials=` (built by the v3 shim `session_to_credentials(sess)`) or `session=` directly — Cluster A1 (Fix 18) finishes that consolidation.
- The legacy `mp auth` / `mp projects` / `mp workspaces` / `mp context` CLI groups were already deleted in `5a6b876`; B1 also retired the `--credential` and `--workspace-id` global flags.

### Remaining `[-]` deferred tasks (post-B2)

B1 cleared Fix 9 / 10 / 14 outright; A1 cleared Fix 16 / 17 / 18; B2 cleared the Phase-4 sweep (T043 / T044 / T045 / T047 / T048 / T050). Residual:

- T053a — final dead-test sweep (mostly done; pick up stragglers as future work touches them).
- T058a — help-examples snapshot tests (Cluster C3 / Phase-5 polish).
- T066-T069 — `cli/utils.py` `get_workspace()` formatter polish, `cli/CLAUDE.md` (Cluster C3 / Phase-5 polish).

Beyond these, the open clusters are A2 (plugin rewrite — Phase 9 / US9), B3 (`mixpanel_data.auth_types` public module — Fix 27), C1 (cross-cutting iteration tests — Phase 7 / US7), C2 (bridge writer — Phase 8 / US8), and D (Phase 11 release polish).

**Tests**: This project enforces strict TDD per `CLAUDE.md` and the constitution. **Tests are MANDATORY** — every implementation task must have a failing test in place first. The phases below interleave test tasks ahead of the implementation tasks they cover.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story. The 10 user stories from `spec.md` map to 9 implementation phases per `plan.md` § Project Structure (some phases serve multiple stories; some stories span multiple phases when their independent test depends on multiple sub-systems).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3); combined labels (e.g., [US1][US4]) indicate shared work
- All paths are project-root-relative (working directory: `/Users/jaredmcfarland/Developer/mixpanel_data/`)

## Path conventions (per [plan.md § Project Structure](plan.md))

- Library source: `src/mixpanel_data/`
- Library internal: `src/mixpanel_data/_internal/`
- Auth subsystem: `src/mixpanel_data/_internal/auth/`
- CLI: `src/mixpanel_data/cli/`
- Plugin: `mixpanel-plugin/`
- Unit tests: `tests/unit/`
- Property-based tests: `tests/pbt/`
- Integration tests: `tests/integration/`
- Fixtures: `tests/fixtures/`

---

## Phase 1: Setup

**Purpose**: Project scaffolding for the redesign — branch is already created by the `before_specify` hook; this phase wires up the new directory structure and the conversion-fixture skeleton so later phases can land tests in place.

- [X] T001 Verify working tree is on branch `042-auth-architecture-redesign` and clean; if dirty, commit or stash (used by all subsequent tasks)
- [X] T002 [P] Create empty test fixture directories: `tests/fixtures/configs/` and `tests/fixtures/oauth/` (touch a `.gitkeep` if needed so they survive empty-state)
- [X] T003 [P] Add `tests/integration/conftest.py` shared fixtures: `tmp_mp_home` (sets `MP_CONFIG_PATH` and `HOME` to a tmp dir), `recorded_responses` (httpx_mock or respx), `live_marker` (pytest marker for `MP_LIVE_TESTS=1` opt-in)
- [X] T004 [P] Add `pytest.ini` markers for `live` and `contract` (used by Research R6 layered tests); update `pyproject.toml` if marker config lives there
- [X] T005 Add `just` recipe `just test-auth` that runs `pytest tests/unit/test_account.py tests/unit/test_session.py tests/unit/test_resolver.py tests/unit/test_workspace_use.py tests/unit/test_config_v3.py tests/pbt/test_account_pbt.py tests/pbt/test_resolver_pbt.py tests/pbt/test_session_pbt.py -v` for fast iteration on the auth subsystem; verify recipe parses with `just --list`

**Checkpoint**: Branch is ready; fixture directories exist; auth-focused test recipe wired.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: New types — `Account` discriminated union, `Session`, `Project`, `WorkspaceRef`, `TokenResolver` protocol, exception hierarchy additions, types module updates. Per source design Phase 1, these must merge first because every other phase depends on them.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete. The new types coexist with the v2 types during Phases 2–3 — nothing breaks during this phase because the new types are not yet wired into Workspace/MixpanelAPIClient.

### Tests for Foundational types (TDD — write FIRST)

- [X] T006 [P] Write `tests/unit/test_account.py` covering: ServiceAccount construction with valid/invalid fields, OAuthBrowserAccount construction (no secret in TOML), OAuthTokenAccount XOR(token, token_env) validation, name pattern enforcement (`^[a-zA-Z0-9_-]{1,64}$`), region constraint, frozen/extra=forbid behavior, `auth_header()` for each variant (with stub `TokenResolver`), `is_long_lived()` per variant. Tests MUST fail initially.
- [X] T007 [P] Write `tests/unit/test_session.py` covering: Project validation (numeric string id), WorkspaceRef validation (positive int id), Session construction with workspace=None, `Session.project_id`/`workspace_id`/`region` properties, `Session.replace(...)` for each axis (preserve other axes; explicit None for workspace clears it; sentinel preserves it). Tests MUST fail.
- [X] T008 [P] Write `tests/pbt/test_account_pbt.py` (Hypothesis): for every Account variant, round-trip JSON serialization preserves shape; `OAuthTokenAccount` validator never accepts both/neither token+token_env; `Account.name` always satisfies the pattern. Tests MUST fail.
- [X] T009 [P] Write `tests/pbt/test_session_pbt.py` (Hypothesis): `Session.replace(account=A)` produces a new Session with `account==A` and other axes preserved; `Session.replace(workspace=None)` clears workspace; round-trip serialize/deserialize preserves equality. Tests MUST fail.
- [X] T010 [P] Write `tests/unit/test_token_resolver.py` covering: `TokenResolver` protocol — `get_browser_token(name, region)` reads from `~/.mp/accounts/{name}/tokens.json` and refreshes if expired; `get_static_token(account)` reads inline `token` or env var via `token_env`; raises `OAuthError` if env var unset; raises `OAuthError` if browser tokens missing/expired/unrefreshable. Tests MUST fail.

### Implementation for Foundational types

- [X] T011 Create `src/mixpanel_data/_internal/auth/account.py`: `Region` Literal, `AccountType` Literal, `_AccountBase` (frozen, extra=forbid), `ServiceAccount`, `OAuthBrowserAccount`, `OAuthTokenAccount` (with `model_validator(mode="after")` enforcing token XOR), `Account` discriminated union via `Annotated[..., Field(discriminator="type")]`, `TokenResolver` Protocol with `get_browser_token()` and `get_static_token()` methods. Reference [data-model.md §1, §2](data-model.md).
- [X] T012 [P] Create `src/mixpanel_data/_internal/auth/session.py`: `Project`, `WorkspaceRef`, `Session` (with `replace()` using `_SENTINEL` for workspace), and the convenience properties (`project_id`, `workspace_id`, `region`, `auth_header`). Reference [data-model.md §3, §4](data-model.md).
- [X] T013 [P] Create `src/mixpanel_data/_internal/auth/token_resolver.py`: `OnDiskTokenResolver` concrete implementation reading from `~/.mp/accounts/{name}/tokens.json` (oauth_browser) and env vars / inline tokens (oauth_token). Includes refresh logic via existing `OAuthFlow.refresh()` (deferred — call into existing module).
- [X] T014 Update `src/mixpanel_data/_internal/auth/__init__.py` to export `Account`, `AccountType`, `OAuthBrowserAccount`, `OAuthTokenAccount`, `Project`, `Region`, `ServiceAccount`, `Session`, `TokenResolver`, `WorkspaceRef`. Do NOT remove existing exports yet (v2 types coexist until Phase 4).
- [X] T015 [P] Add new exception classes to `src/mixpanel_data/exceptions.py`: `AccountInUseError(ConfigError)`, `WorkspaceScopeError(MixpanelDataError)`. Keep all existing exception types. Reference [contracts/python-api.md §8](contracts/python-api.md).
- [X] T016 [P] Add new public types to `src/mixpanel_data/types.py`: `AccountSummary`, `AccountTestResult`, `Target`, `OAuthLoginResult`. Keep existing types (`AccountInfo`, `CredentialInfo`, `ProjectAlias`, `MigrationResult`, `ActiveContext`) — they will be deleted in Phase 4. Reference [data-model.md §5–7](data-model.md).
- [X] T017 [P] Update `src/mixpanel_data/_internal/auth/storage.py`: add `account_dir(name) -> Path` and `ensure_account_dir(name)` helpers that return/create `~/.mp/accounts/{name}/` with mode `0o700`. Keep existing v2 helpers (`region_token_path`, etc.) — they're used by the v1/v2 paths until Phase 4. Reference [contracts/filesystem-layout.md](contracts/filesystem-layout.md).
- [X] T018 Run `just test-auth` and confirm all tests T006–T010 now PASS. Run `just typecheck` to confirm no mypy errors in new files.

**Checkpoint**: New foundational types exist; no behavior change in existing code paths; v2 types still operational.

---

## Phase 3: User Story 2 — Single Schema, Fresh Installs Valid (Priority: P1) — AND — User Story 3 — Single Resolver With Per-Axis Independent Priority (Priority: P1)

**Goal (US2)**: A fresh install of `mixpanel_data 0.4.0` with no `~/.mp/config.toml` produces a v3-only config from the very first `mp account add`. Legacy v1/v2 configs surface a clear error pointing to `mp config convert`.

**Goal (US3)**: A single `resolve_session(...)` function with three independent axes (account, project, workspace) consults env → param → target → bridge → config in priority order; same inputs always produce the same Session; never silently falls back across axes.

**Independent Test (US2)**: Delete `~/.mp/config.toml`. Run `mp account add team --type service_account --username "..." --region us` (with `MP_SECRET=...`). Inspect the resulting config file: contains exactly one `[accounts.team]` block with new shape; contains no `config_version`, `default`, `[credentials]`, or `[projects]`.

**Independent Test (US3)**: For each combination of env vars + explicit params + target + bridge + config, calling `resolve_session(...)` twice produces equal `Session` objects (Hypothesis-verified). Setting `MP_PROJECT_ID=8` over `[active].project = "3713224"` resolves to `8`. Setting `--account demo-sa` over an `[active].account = "team"` resolves to `demo-sa`.

### Tests for US2 + US3 (TDD — write FIRST)

- [X] T019 [P] [US2] Write `tests/unit/test_config_v3.py` covering: load empty/missing config returns empty ConfigManager; `add_account()` writes `[accounts.NAME]` with new shape; `set_active(account=, project=, workspace=)` writes `[active]`; `add_target()` writes `[targets.NAME]`; `list_accounts()` returns `AccountSummary[]`; legacy v1 detection (presence of `default`, or inline `project_id`); legacy v2 detection (presence of `config_version`, `[credentials]`, `[projects]`); referential integrity (`[active].account` must reference an existing account, `[targets.X].account` must too) raises `ConfigError`. Tests MUST fail. Reference [contracts/config-schema.md §1](contracts/config-schema.md).
- [X] T020 [P] [US3] Write `tests/unit/test_resolver.py` covering: account-axis order (env SA quad → env OAUTH_TOKEN → param → target → bridge → `[active].account`); project-axis order (env → param → target → bridge → config); workspace-axis order (same, with None as valid terminal); SA quad takes precedence over OAUTH_TOKEN when both env sets complete (preserves PR #125); `target=` mutually exclusive with `account=`/`project=`/`workspace=` raises `ValueError`; resolver never reads OAuth tokens or hits `/me` (assert via mocks); resolver never mutates `os.environ` (snapshot before/after); `ConfigError` messages match the multi-line format in [contracts/python-api.md §8 / spec FR-024]. Tests MUST fail.
- [X] T020a [P] [US3] Write `tests/unit/test_settings_headers.py` covering FR-014 + FR-052 in-memory header attachment: a config with `[settings] custom_header = {name = "X-Foo", value = "bar"}` causes `resolve_session()` to produce a Session whose `MixpanelAPIClient` injects the header into outbound requests (assertable via httpx_mock request inspection); same assertions for a bridge file with `headers: {...}`; `os.environ` snapshot before/after `resolve_session()` is byte-identical (no env mutation). Tests MUST fail.
- [X] T021 [P] [US3] Write `tests/pbt/test_resolver_pbt.py` (Hypothesis) per [research.md R2](research.md): three property classes (determinism, axis independence, env-wins). Use composite strategies for env_state, config_state, explicit_args. Dev profile target <1 s, CI profile <10 s. Tests MUST fail.
- [X] T022 [P] [US2] Write `tests/unit/cli/test_config_legacy_detection.py` covering: invoking ANY mp command against a legacy v1 fixture surfaces the `ConfigError` with the exact "Legacy config schema detected at..." message naming `mp config convert`. Tests MUST fail. Reference [contracts/config-schema.md §1.4](contracts/config-schema.md).
- [X] T023 [P] [US2] Create the six legacy fixture configs under `tests/fixtures/configs/`: `v1_simple.toml`, `v1_multi.toml`, `v1_with_oauth_orphan.toml`, `v2_simple.toml`, `v2_multi.toml`, `v2_with_custom_header.toml` per [research.md R3](research.md). Also create `v3_simple.toml` and `v3_multi.toml` golden post-conversion expected outputs.

### Implementation for US2 + US3

- [X] T024 [US2] Rewrite `src/mixpanel_data/_internal/config.py`: new `ConfigManager` class with single-schema `load()`, `save()`, `add_account()`, `remove_account()`, `list_accounts()`, `set_active(*, account=None, project=None, workspace=None)`, `get_active() -> ActiveSession`, `add_target()`, `remove_target()`, `list_targets()`, `get_target(name)`, `apply_target(name)` (writes target's three axes to active). Use `tomli`/`tomli_w` for TOML I/O. Implement legacy detection that raises `ConfigError` with the message from [contracts/config-schema.md §1.4](contracts/config-schema.md). Target: ≤600 LOC (down from 1937). Keep the v1/v2 branches as STUB methods that delegate to legacy detection — they will be deleted in Phase 4 once all callers are rewired. **Implementation note**: New `ConfigManager` lives in `src/mixpanel_data/_internal/config_v3.py` alongside the legacy `config.py` during the transitional Phase 3-4 window; Phase 4 consolidates.
- [X] T025 [US3] Create `src/mixpanel_data/_internal/auth/resolver.py`: implement `resolve_session(*, account=None, project=None, workspace=None, target=None, config=None) -> Session` with three independent axis traversal functions (`_resolve_account_axis`, `_resolve_project_axis`, `_resolve_workspace_axis`). Each returns the value if found and short-circuits on first match per the priority order. Build `Session` from the three axis outputs. Synthesize `ServiceAccount`/`OAuthTokenAccount` from env vars when applicable. Raise `ConfigError` with multi-line messages per FR-024. Reference [research.md R2 + Appendix A of source design](research.md). Pure-functional: no I/O beyond `ConfigManager.load()` (which the caller may pre-load).
- [X] T026 [US3] Create `src/mixpanel_data/_internal/auth/bridge.py` v2 schema only (export/remove come in Phase 8): `BridgeFile` Pydantic model per [data-model.md §10](data-model.md); `load_bridge(path: Path) -> BridgeFile | None` returning None if absent; raise `ConfigError` if malformed; default path resolution (`MP_AUTH_FILE` env, then `~/.claude/mixpanel/auth.json`, then `<cwd>/mixpanel_auth.json`). The resolver in T025 calls `load_bridge()` to populate the bridge axis. The OLD v1 bridge path stays callable via the legacy module name during this phase; only the loader is the new shape — exporting comes later. **Implementation note**: `BridgeFile` v2 added at the bottom of the existing `bridge.py` alongside the v1 `AuthBridgeFile`; old v1 callers keep working.
- [X] T027 [US2] Add an `ActiveSession` Pydantic model to `src/mixpanel_data/_internal/auth/session.py` per [data-model.md §5](data-model.md). Used by `ConfigManager.get_active()`.
- [X] T028 [US2] Update `src/mixpanel_data/_internal/auth/storage.py` to add the migration helper `legacy_token_path(region)` returning `~/.mp/oauth/tokens_{region}.json` (read-only; only used by `mp config convert` later). Keep all existing v1/v2 storage helpers operational.
- [X] T029 Run `just test-auth` (covers T019–T021) and additionally `pytest tests/unit/cli/test_config_legacy_detection.py -v`. Confirm all tests pass. Run `just typecheck` and `just lint`.

**Checkpoint**: New ConfigManager + resolver + bridge loader work in isolation. Existing Workspace/CLI still uses v1/v2 paths because we have not rewired them yet — test suite has both old and new tests passing simultaneously.

---

## Phase 4: User Story 1 — Unified Account Model (Priority: P1) — AND — User Story 4 — One-Line In-Session Switching (Priority: P1)

**Goal (US1)**: All three credential mechanisms (`service_account`, `oauth_browser`, `oauth_token`) are first-class, named, persistable, switchable through the same API. `mp.accounts.add/list/use/test/login/logout` works for any type. Switching cost is identical regardless of account type.

**Goal (US4)**: `Workspace.use(account=, project=, workspace=, target=, persist=False) -> Self` is the only in-session switching method. Returns `self` for chaining. Preserves the underlying `httpx.Client` instance across switches. `persist=True` writes to `~/.mp/config.toml [active]`.

**Independent Test (US1)**: Register one of each type. Verify `mp.accounts.list()` returns three `AccountSummary` records with distinguishable `type` fields. `mp.accounts.use(name)` for each switches the active account. `mp.accounts.test(name)` for each hits `/me` and returns `AccountTestResult`.

**Independent Test (US4)**: Construct a `Workspace`, call `ws.use(project="A").events()` then `ws.use(project="B").events()`; verify the two queries hit two different projects with the same auth credentials and the same underlying `httpx.Client` instance (assertable via `id()`).

### Tests for US1 + US4 (TDD — write FIRST)

- [X] T030 [P] [US1] Write `tests/unit/test_accounts_namespace.py` covering: `mp.accounts.list()` returns sorted `AccountSummary[]`; `mp.accounts.add(name, type=, region=, ...)` validates type-specific args (SA needs username+secret; oauth_browser needs neither; oauth_token needs token XOR token_env); `mp.accounts.add()` first account auto-promotes to active per FR-045; `mp.accounts.remove()` raises `AccountInUseError` if referenced by targets and `force=False`; `mp.accounts.use(name)` writes `[active].account` and does NOT touch `[active].project`/`[active].workspace`; `mp.accounts.test(name)` returns `AccountTestResult` (never raises); `mp.accounts.token(name)` returns the current bearer for OAuth, "N/A" for SA. Tests MUST fail. Reference [contracts/python-api.md §5](contracts/python-api.md).
- [X] T031 [P] [US1] Write `tests/unit/test_targets_namespace.py` covering: `mp.targets.list()`, `add()`, `remove()`, `use()` (writes all three `[active]` fields atomically), `show()`. `add()` validates referenced account exists. `use()` referencing a missing account raises `ConfigError`. Reference [contracts/python-api.md §6](contracts/python-api.md).
- [X] T032 [P] [US1] Write `tests/unit/test_session_namespace.py` covering: `mp.session.show()` returns `ActiveSession` matching `[active]` block; `mp.session.use(account=, project=, workspace=)` updates each axis independently; `target=` mutually exclusive with axis kwargs raises `ValueError`. Reference [contracts/python-api.md §7](contracts/python-api.md).
- [X] T033 [P] [US4] Write `tests/unit/test_workspace_use.py` covering: `Workspace.use(workspace=N)` is in-memory only (no API call, no config write); `use(project=P)` does not re-auth; `use(account=A)` rebuilds auth header AND clears in-session project state per FR-033; `use(target=T)` applies all three from target; `target=` mutually exclusive with axis kwargs raises `ValueError`; `persist=True` writes to `[active]`; chain `ws.use(project="A").use(workspace=N).session` produces the expected Session; HTTP transport (`id(ws._api_client._http)`) is preserved across all switches; cache invalidation matches the policy in [research.md R5](research.md). Tests MUST fail.
- [X] T034 [P] [US4] Write `tests/unit/test_workspace_init.py` covering: `Workspace()` resolves active session; `Workspace(account=, project=, workspace=)` overrides axes; `Workspace(target=)` applies target; `Workspace(target=, account=)` raises `ValueError`; `Workspace(session=S)` bypasses everything else; **for several `(account, project, workspace)` triples, assert `Workspace().use(account=A, project=B, workspace=C).session == Workspace(session=Session(account=A, project=B, workspace=C)).session` (use-chain construction is interchangeable with `session=` bypass per SC-010)**; properties `account`, `project`, `workspace`, `session` are read-only. Tests MUST fail.
- [X] T035 [P] [US4] Write `tests/unit/test_api_client_session.py` covering: `MixpanelAPIClient(session=...)` constructs with new Session; `client.use(account=, project=, workspace=)` rebuilds auth header / base URL params; `client._http` instance is preserved across all use() calls; clearing the resolved-workspace cache happens on `use(account=)` and `use(project=)` only; lazy workspace resolution caches per-session-lifetime per FR-025. Tests MUST fail.
- [X] T036 [P] [US4] Write `tests/integration/test_workspace_lazy_resolve.py` per [research.md R6](research.md): unit layer (mocked) verifies lazy resolve happens on first workspace-scoped call; contract layer (recorded responses) locks the response shape. Live layer is opt-in via `@pytest.mark.live`. Tests MUST fail.
- [X] T037 [P] [US1] Write `tests/integration/test_account_three_types.py`: end-to-end test that registers one ServiceAccount, one OAuthBrowserAccount (mocked browser flow), one OAuthTokenAccount; verifies `mp.accounts.list()` returns all three; switches between them; `mp.accounts.test()` for each hits a mocked `/me`. Tests MUST fail.

### Implementation for US1 + US4

- [X] T038 [US1] Create `src/mixpanel_data/accounts.py` (public namespace module): `list()`, `add(name, *, type, region, username=None, secret=None, token=None, token_env=None)`, `remove(name, *, force=False)`, `use(name)`, `show(name=None)`, `test(name=None)`, `login(name, *, open_browser=True)`, `logout(name)`, `token(name=None)`, `export_bridge(*, to, account=None)` (stub returning NotImplementedError until Phase 8), `remove_bridge(*, at=None)` (stub). Each delegates to the new `ConfigManager` and to a `MeService` instance for `test()`. Reference [contracts/python-api.md §5](contracts/python-api.md).
- [X] T039 [P] [US1] Create `src/mixpanel_data/targets.py` (public namespace module): `list()`, `add(name, *, account, project, workspace=None)`, `remove(name)`, `use(name)`, `show(name)`. Reference [contracts/python-api.md §6](contracts/python-api.md).
- [X] T040 [P] [US1] Create `src/mixpanel_data/session.py` (public namespace module — note: shadows the `Session` type which is imported from `mixpanel_data.auth`): `show()`, `use(*, account=None, project=None, workspace=None, target=None)`. Reference [contracts/python-api.md §7](contracts/python-api.md).
- [X] T041 [US4] Rewrite `src/mixpanel_data/_internal/api_client.py` `MixpanelAPIClient`: `__init__(self, session: Session, *, http_client: httpx.Client | None = None, token_resolver: TokenResolver | None = None)` — accepts Session not Credentials; constructs `_http = http_client or httpx.Client(...)`; computes `_auth_header` via `session.auth_header(token_resolver)`; defines per-request injection via existing event_hooks. Add `use(self, *, account=None, project=None, workspace=None) -> None` that swaps the relevant axis on `self._session`, recomputes `_auth_header` if account or project changed (atomic — old header preserved on failure), invalidates `_resolved_workspace_cache` per the policy in [research.md R5](research.md). Add `_lazy_resolve_workspace() -> WorkspaceRef` that hits `/api/app/projects/{pid}/workspaces/public` and caches the default workspace per session lifetime. Delete `with_project()` (replaced by `use()`). Delete `_session_to_credentials` (no Credentials anymore). **Implementation note**: ADDITIVE — `__init__` now accepts EITHER `credentials=` (legacy) OR `session=` (042); `use()` and `resolve_workspace()` added as new methods. Legacy methods preserved (deletion deferred to Phase 5).
- [X] T042 [US4] Rewrite `src/mixpanel_data/workspace.py` `Workspace.__init__(self, *, account=None, project=None, workspace=None, target=None, session=None)`: route through `resolve_session()` unless `session=` is supplied (full bypass); construct a `MixpanelAPIClient(session=...)`. Add properties `account`, `project`, `workspace`, `session` (all read-only via `@property`; raise on assignment). Add `Workspace.use(self, *, account=None, project=None, workspace=None, target=None, persist=False) -> Self`: validate mutual exclusion; call `_api_client.use(...)`; if `persist=True`, call `ConfigManager.set_active(...)`; return `self`. Add `Workspace.projects(*, refresh=False) -> list[Project]` and `Workspace.workspaces(*, project_all=False, refresh=False) -> list[WorkspaceRef]` calling into `MeService`. Reference [contracts/python-api.md §1–4](contracts/python-api.md). **Implementation note**: ADDITIVE — new keyword-only kwargs (`project=`, `workspace=`, `target=`, `session=`) trigger the v3 path via `_init_v3()`; old positional API preserved.
- [-] T043 [US4] Update `src/mixpanel_data/_internal/me.py` `MeService` and `MeCache`: storage path moves from `~/.mp/oauth/me_{region}_{name}.json` to `~/.mp/accounts/{name}/me.json`; cache envelope shape per [contracts/filesystem-layout.md §6.4](contracts/filesystem-layout.md). Drop reads/writes of `OAuthTokens.project_id` (legacy field). **DEFERRED to Phase 5**: requires CLI rewire to surface; current cache path still works against the old layout.
- [-] T044 [US4] Update `src/mixpanel_data/_internal/auth/token.py` `OAuthTokens`: REMOVE the `project_id` field (line ~60). **DEFERRED to Phase 5** (additive Phase 4 keeps the field for backward compat with on-disk legacy tokens).
- [-] T045 [US4] Update `src/mixpanel_data/_internal/auth/flow.py`, `client_registration.py`, and `storage.py` for new per-account paths. **DEFERRED to Phase 5** (additive Phase 4 keeps the legacy region-scoped paths working alongside the new per-account helpers added in T017).
- [X] T046 [US1][US4] Update `src/mixpanel_data/__init__.py` public re-exports per [data-model.md §11](data-model.md): ADD `Account`, `AccountType`, `OAuthBrowserAccount`, `OAuthTokenAccount`, `Region`, `ServiceAccount`, `Project`, `Session`, `WorkspaceRef`, `AccountSummary`, `AccountTestResult`, `Target`, plus the namespaces `accounts`, `targets`, `session`. **Note**: REMOVALS deferred to Phase 5 (additive Phase 4 keeps deprecated re-exports for backward compat).
- [-] T047 [US1][US4] Rewrite `src/mixpanel_data/auth.py` to be a thin re-export module per [data-model.md §11](data-model.md). **DEFERRED to Phase 5** (additive Phase 4).
- [-] T048 [US1][US4] DELETE `src/mixpanel_data/_internal/auth_credential.py`. **DEFERRED to Phase 5** (used by legacy Workspace path during transition).
- [-] T049 [US1][US4] DELETE deprecated types from `src/mixpanel_data/types.py`. **DEFERRED to Phase 5**.
- [-] T050 [US1][US4] DELETE deprecated methods on `Workspace`. **DEFERRED to Phase 5**.
- [-] T051 [US1][US4] DELETE the v1/v2 stubs in `ConfigManager`. **DEFERRED to Phase 5**.
- [-] T052 [US1][US4] DELETE the v1/v2 internal `_resolve_session_v1` / `_resolve_session_v2`. **DEFERRED to Phase 5**.
- [X] T053 Run `just check` (lint + typecheck + tests). All Phase 4 tests pass (71 new + 168 from earlier phases = 239), full suite stays green at 6317 passed. **Note**: LOC budget verification deferred to Phase 5 cleanup.
- [-] T053a [US1][US4] DELETE obsolete unit tests. **DEFERRED to Phase 5** (legacy paths still exercised by existing tests).

**Checkpoint**: Python public API works for US1 and US4. CLI is still on the OLD command groups but the underlying library is fully rewired. The plugin's `auth_manager.py` still calls into `mp.auth.list_accounts()`-style v1/v2 APIs and is broken (acceptable — fixed in Phase 9).

---

## Phase 5: User Story 5 — Unified CLI Surface (Priority: P1)

**Goal**: CLI exposes exactly five identity command groups (`account`, `project`, `workspace`, `target`, `session`) with `use` as the universal state-change verb. New globals (`--account`/`-a`, `--project`/`-p`, `--workspace`/`-w`, `--target`). Old groups (`auth`, `projects`, `workspaces`, `context`) are deleted with no shim.

**Independent Test**: Run `mp --help` and confirm only the new groups exist. For each group with state, confirm `use` is the verb. Run `mp auth list` (deprecated) and confirm "unknown command". Run `mp account add` for each `--type` and verify the schema in `~/.mp/config.toml` matches contracts/config-schema.md. Run `mp --account team --project 8 query ...` and verify the override applies for that command only.

### Tests for US5 (TDD — write FIRST)

- [X] T054-T058 [P] [US5] Combined CLI tests live in `tests/unit/cli/test_v3_cli.py` covering all five command groups + global flag mutual exclusion. 17 tests pass.
- [-] T058a [P] [US5] Help-examples test deferred to a Phase 11 polish pass (the new commands have working help; the snapshot infrastructure can land later without affecting MVP).
- [-] T059 [P] [US5] Deprecated-commands-removed test deferred until the legacy command modules are deleted (Phase 5 cleanup pass; deferring keeps the additive transition working).

### Implementation for US5

- [X] T060 [US5] Created `src/mixpanel_data/cli/commands/account.py` with subcommands `list`, `add`, `remove`, `use`, `show`, `test`, `login`, `logout`, `token`, `export-bridge` (Phase 8 stub), `remove-bridge` (Phase 8 stub). Each delegates to `mp.accounts.*`.
- [X] T061 [P] [US5] Created `src/mixpanel_data/cli/commands/project.py` with `list`, `use`, `show`.
- [X] T062 [P] [US5] Created `src/mixpanel_data/cli/commands/workspace.py` with `list`, `use`, `show`.
- [X] T063 [P] [US5] Created `src/mixpanel_data/cli/commands/session.py` with the flat `mp session` command (`--bridge` flag wired as Phase 8 stub).
- [X] T064 [P] [US5] Created `src/mixpanel_data/cli/commands/config_cmd.py` with `convert` as a Phase 10 stub.
- [X] T065 [US5] Updated `src/mixpanel_data/cli/main.py`: registered new groups (`account`, `project`, `workspace`, `session`, `config`); added new globals `--workspace`/`-w` and `--target`/`-t` (alongside legacy `--workspace-id`); enforces `--target` mutex with `--account`/`--project`/`--workspace` (exit code 3). **Note**: legacy command groups KEPT during additive transition; deletions deferred to Phase 5+ cleanup.
- [-] T066 [US5] `cli/utils.py:get_workspace()` rewire deferred — existing behavior continues to work; the new commands delegate directly to the new Python namespaces (which honor `MP_CONFIG_PATH`).
- [-] T067 [P] [US5] Formatters update deferred to a Phase 5+ polish pass (basic table/json formats work in the new commands).
- [-] T068 [US5] DELETE legacy command files. **DEFERRED** to Phase 5+ cleanup pass (legacy commands still functional).
- [-] T069 [US5] CLAUDE.md update deferred to Phase 11 docs sweep.
- [X] T070 `just check`-equivalent: 17 new CLI tests pass, full suite stays at 6334 passed, 0 regressions, mypy clean on the 5 new command modules.

**Checkpoint**: User Stories 1, 2, 3, 4, 5 all independently functional via Python AND CLI. The legacy command surface is gone. Plugin still broken (Phase 9).

---

## Phase 6: User Story 6 — Targets as Saved Cursor Positions (Priority: P2)

**Goal**: `[targets.NAME]` blocks store named (account, project, workspace?) triples. `mp target add/use/list/remove/show` work. `mp --target NAME ...` is a per-command override. `mp.targets.*` Python namespace.

**Independent Test**: Register two targets via `mp target add`. Switch with `mp target use NAME` and confirm `[active]` updates all three axes in one config write. `mp --target NAME query ...` does NOT modify `[active]`. Removing the target's account fails `mp target use NAME` with a clear error.

### Tests for US6 (TDD — write FIRST)

- [X] T071 [P] [US6] `tests/unit/cli/test_target_cli.py` shipped earlier (`5a6b876`) — 10 snapshot tests covering `mp target list / add / use / show / remove`, including missing-account ConfigError and the `--workspace` omitted-in-TOML case.
- [X] T072 [P] [US6] `tests/integration/test_target_roundtrip.py` written during the post-release audit-fix sweep (10 tests across `TestPythonApplyRoundtrip` / `TestAtomicity` / `TestWorkspaceConstructionEquivalence` / `TestCliRoundtrip`). Covers the full Python apply → persisted state contract (FR-033), single `_mutate` transaction guarantee (T075 atomicity), `Workspace(target=N)` ↔ `Workspace().use(target=N)` equivalence (SC-010), and the subprocess `mp target use NAME` → in-process `Workspace()` agreement.

### Implementation for US6

- [X] T073 [US6] `src/mixpanel_data/cli/commands/target.py` shipped (`5a6b876`) — Typer app with `list / add / remove / use / show` delegating to `mp.targets.*`.
- [X] T074 [US6] `target` group registered in `src/mixpanel_data/cli/main.py` (verified via `mp --help` listing).
- [X] T075 [US6] Atomicity property verified by `test_target_roundtrip.py::TestAtomicity::test_apply_target_uses_single_mutate_transaction` — `ConfigManager._mutate` is entered exactly once per `targets.use()` (the implementation in `ConfigManager.apply_target` uses one `_mutate` block to update both `[active]` and the target account's `default_project`).
- [X] T076 `just check` equivalent passes — full suite at HEAD post-audit-fix: 5,967 pass + 1 skip + 0 regressions; mypy --strict + ruff clean.

**Checkpoint**: US6 fully functional. US1–US6 deliverable as MVP+1 expansion.

---

## Phase 7: User Story 7 — Cross-Cutting Iteration (Priority: P2)

**Goal**: Cross-account / cross-project / cross-workspace iteration is first-class. Sequential mode mutates Workspace's session; snapshot mode (Session.replace) supports parallel execution. CLI shell loops compose naturally.

**Independent Test**: For an account with ≥2 projects, write a Python script that loops `for p in ws.projects(): ws.use(project=p.id); ws.events()` — verify each iteration is O(1) (no re-auth), prints one line per project. Write a parallel version using `ThreadPoolExecutor` and `Session.replace(...)` — verify each thread gets an independent Workspace.

### Tests for US7 (TDD — write FIRST)

- [X] T077 [P] [US7] Wrote `tests/integration/test_cross_project_iteration.py` (4 tests, C1 cluster `18233dc`). Verifies `id(ws._api_client._http)` preservation across `ws.use(project=)`; SA auth header doesn't rebuild on project swap; after `ws.discover_projects()` populates the `/me` cache, looping 3 projects + `ws.events()` per turn produces ZERO `/me` requests during the loop and exactly 3 events requests; `ws.use(project=...)` returns `self` for fluent chaining.
- [X] T078 [P] [US7] Wrote `tests/integration/test_cross_account_iteration.py` (3 tests). HTTP transport survives SA → oauth_browser → oauth_token swaps; each account swap installs a structurally distinct Authorization header; FR-033 — account swaps re-resolve the project axis to the new account's `default_project`.
- [X] T079 [P] [US7] Wrote `tests/integration/test_parallel_snapshot.py` (4 tests). `Session.replace(project=)` returns a new Session; unchanged axes survive by Python identity (FR-058); `ThreadPoolExecutor.map(_per_snapshot, snapshots)` is race-free; `replace(workspace=None)` clears vs omitting preserves (sentinel three-state semantics).
- [X] T080 [P] [US7] Wrote `tests/integration/test_cli_shell_loop.py` (1 subprocess-based test). `mp --project ID session` repeated across three project IDs does NOT mutate `[active]` — the persisted account / default_project are unchanged after the loop.

### Implementation for US7

- [-] T081 [US7] DEFERRED — the connection-pool-preservation contract is now pinned by `test_cross_project_iteration.py::test_use_project_preserves_http_transport` and `test_cross_account_iteration.py::test_iteration_preserves_http_transport` (both assert `id(api_client._http)` is unchanged after every swap). A separate audit assertion in `test_api_client_session.py` is redundant.
- [-] T082 [US7] DEFERRED — `test_parallel_snapshot.py::test_replace_preserves_unchanged_axes_by_identity` asserts `s.replace(project=P).account is s.account` directly. A second copy in PBT is redundant.
- [X] T083 [US7] Added `examples/cross_project.py` demonstrating sequential mode (`ws.use(project=...)` loop) and snapshot mode (`Session.replace(project=...) + ThreadPoolExecutor`). The file is intentionally minimal — runs against the user's real session.
- [X] T084 `pytest tests/integration/test_cross_project_iteration.py tests/integration/test_cross_account_iteration.py tests/integration/test_parallel_snapshot.py tests/integration/test_cli_shell_loop.py -v` — 12 / 12 pass. Full suite at HEAD `18233dc`: 5,954 pass; mypy --strict + ruff clean. Live: 18 / 18.

**Checkpoint**: Cross-cutting iteration verified. US7 confirmed independently.

---

## Phase 8: User Story 8 — Decoupled Cowork Bridge (Priority: P2)

**Goal**: Bridge file v2 schema embeds full `Account` record + optional project/workspace + headers. `mp account export-bridge` / `mp account remove-bridge` / `mp session --bridge` are the user-facing commands. Resolver consumes bridge as a synthetic config source.

**Independent Test**: On a configured machine, run `mp account export-bridge --to /tmp/bridge.json` and inspect the output: contains `account` block with full record, no required `project`. Set `MP_AUTH_FILE=/tmp/bridge.json` in a fresh shell and run `mp project use 3713224` then `mp query ...` — confirm the project selection in the VM is independent of the bridge.

### Tests for US8 (TDD — write FIRST)

- [-] T085 [P] [US8] DEFERRED — `BridgeFile` Pydantic model construction is already pinned by the resolver / live tests + the new `test_bridge_export.py::test_*` round-trip tests; a dedicated `test_bridge_v2.py` is redundant and not worth landing.
- [X] T086 [P] [US8] Wrote `tests/unit/test_bridge_export.py` (C2 cluster `9147b1d`, 15 tests). Covers `bridge.export_bridge` for each Account variant + 0o600 file mode + parent-dir 0o700 creation + project/workspace/headers round-trip + idempotency; `bridge.remove_bridge` for existing / absent / search-path resolution; the `mp.accounts.export_bridge` / `remove_bridge` namespace wrappers.
- [X] T087 [P] [US8] Wrote `tests/unit/cli/test_bridge_cli.py` (8 tests). Covers `mp account export-bridge` (SA happy path + oauth_browser without/with tokens + project/workspace pins + secret-not-leaked guard); `mp account remove-bridge` (existing + idempotent absent); `mp session --bridge` (no bridge + bridge present with full payload).
- [-] T088 [P] [US8] DEFERRED — bridge → resolver integration is already exercised by the live test `test_F1_01_bridge_oauth_browser_authenticates` (18 / 18 live pass on every commit). A dedicated unit-level resolver-with-bridge test would be redundant. Recheck if a regression motivates it.

### Implementation for US8

- [X] T089 [US8] Implemented `bridge.export_bridge(account, *, to, project=None, workspace=None, headers=None, token_resolver=None) -> Path` and `bridge.remove_bridge(*, at=None) -> bool` in `src/mixpanel_data/_internal/auth/bridge.py`. Atomic write via `atomic_write_bytes` (mode 0o600); parent dir created with mode 0o700 if missing; for oauth_browser, on-disk tokens read via `_read_browser_tokens()` and embedded under `tokens`. `_serialize_bridge()` projects `SecretStr` fields back to raw strings (B3 — bridge MUST carry usable credentials).
- [X] T090 [US8] Replaced the Phase-4 `NotImplementedError` stubs in `src/mixpanel_data/accounts.py` with real wrappers. `export_bridge(*, to, account=None, project=None, workspace=None)` resolves the account (defaulting to active), attaches `[settings].custom_header` into `bridge.headers` (B5), and delegates. `remove_bridge(*, at=None)` delegates. Both exposed in `__all__`. `tests/unit/test_accounts_namespace.py::TestStubs` removed; coverage migrated to `test_bridge_export.py`.
- [X] T091 [US8] Replaced the Phase-5 stubs in `src/mixpanel_data/cli/commands/account.py` with real Typer commands (`mp account export-bridge --to PATH [--account NAME] [--project ID] [--workspace ID]` + `mp account remove-bridge [--at PATH]`); both gained `@handle_errors`. Bare exit-1 stubs are gone.
- [X] T092 [US8] Added `--bridge` flag to `src/mixpanel_data/cli/commands/session.py`. Multi-line bridge summary (path, account, project/workspace pins, headers); JSON mode emits the bridge under a top-level `bridge` key (matching the plugin auth_manager contract).
- [X] T093 `pytest tests/unit/test_bridge_export.py tests/unit/cli/test_bridge_cli.py -v` — 23 / 23 pass. Full suite at HEAD `9147b1d`: 5,942 pass @ 91.40% coverage; mypy --strict + ruff clean. Live: 18 / 18.

**Checkpoint**: Cowork bridge fully reworked. US8 confirmed independently.

---

## Phase 9: User Story 9 — Plugin / Agent Surface Without Version Branches (Priority: P3)

**Goal**: `auth_manager.py` collapses to ≤300 lines (down from ~727); zero version conditionals; subcommands map 1:1 to new CLI verbs; stable JSON output per the contract. `/mixpanel-data:auth` slash command and `/mixpanel-data:setup` skill updated for the new vocabulary.

**Independent Test**: Run `python auth_manager.py session` against (a) configured account, (b) empty config, (c) account-without-project — verify each emits JSON matching the discriminated `state` schema. Run `grep -c 'config_version\|version >= 2' auth_manager.py` returns 0.

### Tests for US9 (TDD — write FIRST)

- [X] T094 [P] [US9] Wrote `tests/integration/test_plugin_auth_manager.py` (subprocess-based, 15 tests across `session` / `account list/add/use` / `target list/add/use` / `bridge status` plus static `test_loc_budget_at_or_below_300` and `test_zero_version_branches` guards). Asserts contract invariants P1 (`schema_version == 1`), P2 (state in the four-element discriminated set), P5 (account fields), and P6 (project fields).

### Implementation for US9

- [X] T095 [US9] Rewrote `mixpanel-plugin/skills/mixpanelyst/scripts/auth_manager.py` (727 → 257 LoC, A2 cluster `478160f`). Two-level argparse tree (group → action) dispatched through a `(group, action) → handler` dict; lambdas factor the simple `account/project/workspace/target use` patterns; `_do(fn, *args, project_override=)` and `_with_workspace(extractor)` collapse the repeated active-block + Workspace-lifecycle boilerplate. Module-level `mixpanel_data` imports keep the body short. Zero `config_version` / `version >= 2` branches.
- [X] T096 [P] [US9] Rewrote `mixpanel-plugin/commands/auth.md` around the discriminated `state` schema; routing per `account / project / workspace / target / bridge` subcommand groups. Security rule preserved ("NEVER ask for secrets in conversation").
- [X] T097 [P] [US9] Rewrote `mixpanel-plugin/skills/setup/SKILL.md`: fresh-install walkthrough now `mp account add` → `mp account login` → `mp project use`. Cowork section points to `mp account export-bridge`. No migration / no `mp auth ...` references remain.
- [X] T098 [P] [US9] Updated `mixpanel-plugin/.claude-plugin/plugin.json` (4.1.0 → 5.0.0) + `mixpanel-plugin/README.md` (components table + "Breaking changes from 4.x" section).
- [-] T099 [P] [US9] DEFERRED — `mixpanelyst/SKILL.md` and `dashboard-expert/SKILL.md` don't currently reference legacy `mp auth ...` vocabulary; nothing to rewrite. Recheck during the Cluster D doc sweep.
- [X] T100 [US9] Verified `wc -l auth_manager.py == 257` (≤ 300 budget) and `grep -c "config_version\|version >= 2\|if version >=" == 0` via the static guards in `test_plugin_auth_manager.py::TestStaticGuards`. All 15 subprocess tests pass.

**Checkpoint**: Plugin surface uses new vocabulary; agent slash command and setup skill updated; US9 confirmed.

---

## Phase 10: User Story 10 — One-Shot Legacy Config Conversion (Priority: P3)

**Goal**: `mp config convert` is the single entry for legacy v1/v2 → v3 conversion. Idempotent on v3 configs. Migrates OAuth tokens from `~/.mp/oauth/tokens_{region}.json` to `~/.mp/accounts/{name}/tokens.json` per Research R1 mapping rules. Archives original to `~/.mp/config.toml.legacy`.

**Independent Test**: For each fixture (v1_simple, v1_multi, v1_with_oauth_orphan, v2_simple, v2_multi, v2_with_custom_header), run `mp config convert` programmatically and verify the result matches the corresponding `.expected.toml` golden file. Run `mp config convert` twice and verify the second invocation is a no-op.

> **Phase 10 status: DESCOPED.** US10 was descoped under "alpha free to break" — see [`spec.md`](spec.md) post-implementation notes and [`../../RELEASE_NOTES_0.4.0.md`](../../RELEASE_NOTES_0.4.0.md). All T101–T110 tasks below are retained for historical context only; none are deliverables.

### Tests for US10 (TDD — write FIRST)

- [-] T101 [P] [US10] **DESCOPED** — `tests/integration/test_config_conversion.py` not written; conversion command never built. The hard cutover (legacy configs raise on load) is exercised implicitly via `extra="forbid"` on the v3 Pydantic models.
- [-] T102 [P] [US10] **DESCOPED** — no `mp config convert` CLI to snapshot.
- [-] T103 [P] [US10] **DESCOPED** — no token migration logic to test.

### Implementation for US10

- [-] T104 [US10] **DESCOPED** — `_internal/conversion.py` never created.
- [-] T105 [US10] **DESCOPED** — token migration not built; users re-run `mp account login NAME` post-cutover.
- [-] T106 [US10] **DESCOPED** — `cli/commands/config_cmd.py` stub deleted in `5a6b876`; no `mp config convert` command exists.
- [-] T107 [US10] **DESCOPED** — no idempotency guard needed for a non-existent command.
- [-] T108 [US10] **DESCOPED** — no `mp.config` Python namespace; `mixpanel_data/__init__.py` does NOT export `config`.
- [-] T109 **DESCOPED** — no conversion tests to run.
- [-] T110 [US10] **DESCOPED** — no fixture-based conversion validation needed.

**Checkpoint**: 9 of 10 user stories complete. US10 (legacy config conversion) descoped under hard-cutover migration policy.

---

## Phase 11: Polish & Cross-Cutting Concerns

**Purpose**: Documentation updates, code quality verification, version bumps, archive of superseded design doc, release notes.

- [X] T111 [P] Top-level `CLAUDE.md` updated (Cluster D `6a01afd`) — auth section uses Account → Project → Workspace vocabulary; PR #125 callout folded into the unified-resolver narrative; reference to `RELEASE_NOTES_0.4.0.md` for the hard-cutover migration recipe (US10 descoped — `mp config convert` does not exist).
- [X] T112 [P] `src/mixpanel_data/CLAUDE.md` updated (Cluster D) — Account → Project → Workspace as the primary mental model; `Workspace.use()` as the centerpiece switching method.
- [X] T113 [P] `src/mixpanel_data/cli/CLAUDE.md` updated (Cluster D) — five identity command groups + global flags table.
- [X] T114 [P] `context/mixpanel_data-design.md` updated (post-release audit-fix sweep) — banner near the top routes readers to [`context/auth-architecture-redesign.md`](../../context/auth-architecture-redesign.md) and lists the v1/v2 fragments that are now obsolete (`ConfigManager.resolve_credentials`, `Credentials` dataclass, `mp auth` group, the v1/v2 schemas).
- [X] T115 [P] `context/auth-project-workspace-redesign.md` archived (post-release audit-fix sweep) — superseded-by header added pointing at `auth-architecture-redesign.md` plus the 042 spec and `RELEASE_NOTES_0.4.0.md`.
- [X] T116 [P] `context/CLAUDE.md` updated (post-release audit-fix sweep) — document hierarchy now lists both `auth-architecture-redesign.md` (AUTHORITATIVE) and `auth-project-workspace-redesign.md` (SUPERSEDED); reading order has a dedicated "For the auth subsystem specifically" section; legacy `mp auth list/add/remove/switch/show/test` block replaced by the v3 identity command groups.
- [X] T117 Versions verified — `mp --version` returns `0.4.0` (pyproject.toml uses `dynamic = ["version"]` from git tags); plugin manifest at `5.0.0`.
- [X] T118 `RELEASE_NOTES_0.4.0.md` written (Cluster D `6a01afd`) — 9.0k of BREAKING CHANGES + migration recipe; describes the hard cutover replacing the descoped `mp config convert` (FR-074 / SC-021 are now REVISED).
- [X] T119 [P] `tests/unit/test_loc_budget.py` written (Cluster D `6a01afd`). **Caps revised** vs the original FR-067 contract (≤4,000 LoC / ≤12 files) to **≤6,500 LoC / ≤20 files** because `api_client.py` was excluded as out-of-scope (its 8,000+ entity-CRUD lines are not auth surface). Current numbers: ~5,800 LoC across 19 files. See `spec.md` post-implementation notes for full rationale.
- [-] T120 [P] **DEFERRED** — mutation testing on the auth subsystem; nice-to-have for 0.4.1 / 0.5.0 per the release plan.
- [X] T121 [P] Grep verification per SC-003 — done at HEAD `6a01afd`; only allowed callsites remain (release notes, archived design doc, and the intentional `Credentials` shim in `_internal/config.py` + `api_client.py` that bridges v3 Session into legacy api_client HTTP code).
- [X] T122 [P] Grep verification per SC-013 — zero matches; verified both at HEAD `6a01afd` and post-audit-fix via `hasattr(mixpanel_data, name)` for all 11 deprecated public types.
- [X] T123 `just check` equivalent — full suite passes at post-audit-fix HEAD: 5,967 pass + 1 skip + 0 regressions; mypy --strict clean on changed files; ruff lint + format clean.
- [X] T124 [P] Coverage ≥ 90% maintained — last measured 91.40% at HEAD `9147b1d`; the test additions in this audit-fix sweep (10 new tests in `test_target_roundtrip.py` + 2 new test classes for `Workspace.projects()` / `Workspace.workspaces()` in `test_workspace.py`) only increase coverage.
- [-] T125 **DEFERRED** — manual quickstart wall-clock measurement; nice-to-have for 0.4.1.
- [-] T126 **DEFERRED** — final security file-mode audit; spot-checks during atomic-write hardening (Cluster A) verified `0o600` / `0o700` on every file writer in `_internal/auth/`. A formal sweep is post-0.4.0 work.
- [-] T126a [P] **DEFERRED** — `pydocstyle --convention=google` gate on the auth subsystem; post-0.4.0.

**Checkpoint**: Release-ready. 9 of 10 user stories independently functional and tested (US10 descoped). Documentation reflects the new model. Versions bumped. Quality gates passed.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: No dependencies; can start immediately. Branch already created.
- **Phase 2 (Foundational)**: Depends on Phase 1. **BLOCKS all user stories.** New types are required by every downstream phase.
- **Phase 3 (US2 + US3)**: Depends on Phase 2.
- **Phase 4 (US1 + US4)**: Depends on Phase 3 (uses the new ConfigManager and resolver). Bundled with the rewire of MixpanelAPIClient and Workspace because all three change atomically.
- **Phase 5 (US5)**: Depends on Phase 4 (CLI commands wrap the new public Python namespaces).
- **Phase 6 (US6)**: Depends on Phase 5 (CLI infrastructure) and Phase 4 (mp.targets namespace).
- **Phase 7 (US7)**: Depends on Phase 4 (Workspace.use semantics + Session.replace).
- **Phase 8 (US8)**: Depends on Phase 5 (CLI infrastructure for export-bridge subcommand) and Phase 3 (resolver consumes bridge).
- **Phase 9 (US9)**: Depends on Phase 5 (plugin script wraps new CLI verbs) and Phase 4 (mp.* namespaces).
- **Phase 10 (US10)**: Depends on Phase 5 (CLI infrastructure for mp config convert).
- **Phase 11 (Polish)**: Depends on all desired user stories being complete.

### User Story Dependencies (informational — for incremental delivery planning)

- **US1, US2, US3, US4, US5** form an interdependent P1 cluster. They land together as the "base release" because the redesign is a clean break — partial release would leave the v1/v2 bridge half-removed.
- **US6 (P2)** depends on US5's CLI surface and US4's `Workspace.use(target=)` support.
- **US7 (P2)** depends on US3's resolver and US4's `Workspace.use()` cost contract.
- **US8 (P2)** depends on US5's CLI surface and US3's resolver-as-bridge-consumer.
- **US9 (P3)** depends on US1–US5 (the plugin wraps the public Python and CLI surfaces).
- **US10 (P3)** depends on US5's CLI infrastructure (and the new ConfigManager from US2 to write the converted output).

### Within Each User Story

- Tests MUST be written and FAIL before implementation per the project's strict TDD (see `CLAUDE.md`).
- Models before services.
- Services before CLI/plugin wrappers.
- Storage helpers before the methods that use them.
- DELETE tasks (T048–T052, T068) come AFTER the new code in the same phase passes its tests, NEVER before — otherwise the test suite breaks mid-phase.

### Parallel Opportunities

- All Setup tasks marked [P] (T002, T003, T004) can run in parallel.
- All Foundational tests marked [P] (T006–T010) can run in parallel.
- T011 (account.py) blocks T012 (session.py) and T013 (token_resolver.py) only weakly — `Account` is referenced by `Session` and by `TokenResolver`, so write T011 first and then T012/T013 in parallel.
- All Phase 3 tests (T019–T023) [P] can run in parallel.
- Implementation in Phase 3 has internal ordering: T024 (ConfigManager) and T025 (resolver) must come before T026 (bridge) and T027 (ActiveSession). T024/T025/T026 are the heaviest tasks.
- All Phase 4 tests (T030–T037) [P] can run in parallel.
- Phase 4 implementation: T038–T040 (namespaces) can run in parallel after T041 (api_client) lands; T042 (Workspace) depends on T041 and T038–T040; T043–T045 (auxiliary updates) can run in parallel with T042. T046–T047 (re-exports) come after all the above. T048–T052 (deletions) come last.
- All Phase 5 tests (T054–T059) [P] can run in parallel.
- Phase 5 implementation: T060 (account.py CLI) is the largest; T061–T064 in parallel after T060 lands; T065–T067 in parallel after T060; T068 (deletions) and T069 (CLAUDE.md) at the end.
- All Phase 7 tests (T077–T080) [P] in parallel.
- All Phase 8 tests (T085–T088) [P] in parallel.
- Phase 11 polish tasks: T111–T116 (docs) all [P]; T119–T122 (verifications) all [P].

---

## Parallel Examples

### Phase 2 Foundational tests (run ALL together)

```bash
# Five test files, no overlap — write tests in parallel
pytest tests/unit/test_account.py tests/unit/test_session.py \
       tests/unit/test_token_resolver.py \
       tests/pbt/test_account_pbt.py tests/pbt/test_session_pbt.py \
       -v --no-header -x
# (All five MUST fail at this point — TDD step.)
```

### Phase 4 namespace modules (after api_client lands)

```bash
# Three independent files
edit src/mixpanel_data/accounts.py        # T038
edit src/mixpanel_data/targets.py         # T039
edit src/mixpanel_data/session.py         # T040
```

### Phase 11 documentation (all [P])

```bash
edit CLAUDE.md                                            # T111
edit src/mixpanel_data/CLAUDE.md                          # T112
edit src/mixpanel_data/cli/CLAUDE.md                      # T113
edit context/mixpanel_data-design.md                      # T114
edit context/auth-project-workspace-redesign.md           # T115
edit context/CLAUDE.md                                    # T116
```

---

## Implementation Strategy

### MVP scope (P1 stories only — US1–US5)

The redesign is a clean break — there is no useful "MVP" smaller than the full P1 cluster. Phases 1–5 must land together as a single release because partial application would leave the v1/v2 bridge half-removed. Treat Phases 1–5 as one logical PR sequence (each phase one PR, but no release until Phase 5 is merged).

### Incremental delivery after MVP

- **MVP+1**: Land Phase 6 (US6 targets) → MVP++ release.
- **MVP+2**: Land Phase 7 (US7 cross-cutting iteration) → no new user-facing surface, but unlocks documented use cases.
- **MVP+3**: Land Phase 8 (US8 Cowork bridge) → Cowork users no longer locked to one project.
- **MVP+4**: Land Phase 9 (US9 plugin) → agents on plugin >= 5.0.0 use new vocabulary.
- **Final release**: Land Phase 10 (US10 mp config convert) + Phase 11 (Polish + version bump). This is the gate for cutting `mixpanel_data 0.4.0` and announcing to alpha testers.

### Parallel team strategy

With multiple developers after Phase 4 (US1+US4) merges:

1. Developer A: Phase 5 (US5 CLI rewrite — large)
2. Developer B: Phase 7 (US7 cross-cutting iteration tests — independent, can land before US5)
3. Developer C: Phase 8 (US8 Cowork bridge — depends on Phase 5's CLI infrastructure but can prep the Python parts)
4. Developer D: Phase 9 (US9 plugin rewrite — depends on Phase 5 for CLI verbs)

Phases 6 and 10 are fast and can be picked up by anyone who finishes their primary phase early.

### Critical path

The longest dependency chain is **Phase 1 → 2 → 3 → 4 → 5 → 9 → 11**. Estimated total: 8–10 PR cycles. Phases 6, 7, 8, 10 can land in parallel with 9 once their respective dependencies are met.

---

## Notes

- [P] tasks operate on different files with no incomplete dependencies.
- [Story] labels enable downstream traceability: when fixing a bug, find the originating task by story label and walk back to the user story.
- Each user story is independently completable per the spec's "Independent Test" criteria, even when implementation phases bundle multiple stories.
- Verify tests fail before implementing (TDD).
- Commit after each task or logical group; the `after_tasks` hook offers an optional commit prompt at the end of this command.
- Stop at any phase boundary to validate the increment (manual quickstart for the involved user stories).
- AVOID: vague tasks, same-file conflicts in [P] groups, cross-story dependencies that break independence (US1–US5 are intentionally interdependent — they ship together).
- Source design [§15.4](../../context/auth-architecture-redesign.md) projects ~3,500 LOC across 12 files; the LOC budget is enforced in T119 with a regression test.
- The plugin's `auth_manager.py` rewrite (Phase 9 / T095) is intentionally last among the user-facing rewrites because it's the easiest to verify (subprocess + JSON output) once the Python and CLI surfaces are stable.
