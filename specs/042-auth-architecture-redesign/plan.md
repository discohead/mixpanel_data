# Implementation Plan: Authentication Architecture Redesign (Account → Project → Workspace)

**Branch**: `042-auth-architecture-redesign` | **Date**: 2026-04-21 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/042-auth-architecture-redesign/spec.md`
**Supersedes**: `038-auth-project-workspace-redesign`
**Source design**: [`context/auth-architecture-redesign.md`](../../context/auth-architecture-redesign.md)

## Summary

Replace the current v1+v2 authentication subsystem with a single unified model — **Account → Project → Workspace** — by deleting the v1 paths, the v1↔v2 bridge, and the runtime migration code; rebuilding the type system around a discriminated `Account` union (`ServiceAccount` | `OAuthBrowserAccount` | `OAuthTokenAccount`); collapsing the six-layer fallback resolver into one pure-functional `resolve_session()` with three independent priority axes (env → param → target → bridge → config); and restructuring the CLI grammar so every state-change verb is `use` and every flag/global is consistent across `mp account`/`mp project`/`mp workspace`/`mp target`/`mp session`. The redesign delivers a one-line `Workspace.use(...)` switching contract that preserves the underlying `httpx.Client` across switches, makes cross-cutting iteration first-class (Python sequential, Python parallel via `Session.replace()`, CLI shell loops), and lets the plugin's `auth_manager.py` collapse from ~727 lines to ≤300 lines because there are no v1/v2 conditionals. Legacy configs are converted by an opt-in `mp config convert` script (no auto-conversion at runtime). The package version bumps to `mixpanel_data 0.4.0` and the plugin to `5.0.0`.

The spec covers all 9 phases (Phase 0 documentation review through Phase 8 release). This plan rewires the work into 9 implementation phases with explicit dependencies, defines the Phase 0 research deliverables (filesystem migration safety, axis-priority test surface, conversion fixture corpus, plugin JSON contract stability), and produces the Phase 1 data-model.md, contracts/, and quickstart.md for downstream `/speckit.tasks` to consume.

## Technical Context

**Language/Version**: Python 3.10+ (mypy --strict compliant)
**Primary Dependencies**: Pydantic v2 (frozen models, discriminated unions), httpx (HTTP client; transport preserved across switches), Typer (CLI), Rich (output), tomli/tomli_w (TOML read/write), pytest + Hypothesis (property-based tests), mutmut (mutation testing)
**Storage**:
- TOML config at `~/.mp/config.toml` (one schema, no `config_version` field)
- Per-account state at `~/.mp/accounts/{name}/` (`tokens.json`, `client.json`, `me.json`; all `0o600`; parent dir `0o700`)
- Bridge file at `~/.claude/mixpanel/auth.json` (or `MP_AUTH_FILE`); v2 schema embedding full `Account` record + optional project/workspace + headers
- Legacy archive at `~/.mp/config.toml.legacy` (post-conversion only)
**Testing**: pytest (unit + integration), Hypothesis (resolver determinism, account union round-trip, axis independence), mutmut (≥85% on `_internal/auth/account.py`, `_internal/auth/session.py`, resolver in `config.py`), CLI snapshot tests (Typer + Rich), subprocess tests (plugin `auth_manager.py` end-to-end)
**Target Platform**: Cross-platform (macOS, Linux, Windows). Filesystem permissions enforced on POSIX; Windows uses ACL fallback per existing convention.
**Project Type**: Library + CLI + plugin (auth subsystem refactor — no new product surfaces)
**Performance Goals**:
- `Workspace.use(workspace=N)` ≤ 1 ms (in-memory field update only)
- `Workspace.use(project=P)` ≤ 5 ms (no API call; auth header unchanged)
- `Workspace.use(account=A)` ≤ 10 ms (re-resolve account; new auth header; clear caches; HTTP transport preserved)
- `resolve_session(...)` ≤ 50 ms cold (TOML parse + env lookups + per-axis priority traversal); ≤ 5 ms warm (cached config)
- Cross-project iteration: O(1) per project switch, no re-auth, no `/me` refetch (verified via instrumented HTTP-call counter)
- `mp config convert` ≤ 2 s for typical fixture configs (handful of accounts, handful of project aliases)
**Constraints**:
- mypy --strict compliance with zero `Any` types lacking explicit justification
- ruff format/check passes with zero violations
- 90% test coverage minimum (CI fails below)
- ≥85% mutation score on the three auth files listed above
- Auth subsystem total LOC ≤ 4,000 across ≤ 12 files (down from ~7,200 across 15) — **REVISED at release: ≤6,500 LOC across ≤20 files; current ~5,800 / 19 (see [`spec.md`](spec.md) post-implementation notes and `tests/unit/test_loc_budget.py`).**
- Zero `if config_version` / `if version >= 2` branches in source or tests (verified via grep)
- Zero `os.environ` mutations from any auth code (custom headers attach to `Account` instances)
- Zero deprecated names (`Credentials`, `AuthCredential`, `ProjectContext`, `ResolvedSession`, `ProjectAlias`, `MigrationResult`, `ActiveContext`, `AuthMethod`, `CredentialType`, `AccountInfo`, `CredentialInfo`) reachable from public package root
**Scale/Scope**: ~10 new files, ~12 modified files, ~10 deleted files. 9 implementation phases (Phase 0–Phase 8). Affects `src/mixpanel_data/`, `mixpanel-plugin/`, top-level `CLAUDE.md` files, and the `context/auth-project-workspace-redesign.md` archive.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Evidence |
|-----------|--------|----------|
| I. Library-First | PASS | All capabilities (`Workspace.use`, `mp.accounts.*`, `mp.targets.*`, `mp.session.*`, `resolve_session`) are Python-API-first; CLI commands (`mp account use`, `mp project use`, etc.) are thin Typer wrappers that delegate to the public Python namespaces. Plugin `auth_manager.py` calls into the same Python API, never re-implementing logic. |
| II. Agent-Native | PASS | Every CLI command runs non-interactively when given complete arguments; `mp account add` accepts `--secret-stdin` / `MP_SECRET` env to avoid prompts; `mp account login` is the only command that requires interactive browser flow (and is opt-in per account). All output supports `-f json/jsonl/csv/table/plain`. Exit codes follow the existing `0/1/2/3/4/5` convention defined in the constitution. The plugin's `auth_manager.py` emits structured JSON with stable shape (per FR-057). |
| III. Context Window Efficiency | PASS | `/me` cache stays per-account at `~/.mp/accounts/{name}/me.json` with 24 h TTL; cross-project iteration reuses cached `/me` (no refetch on `ws.use(project=...)`); `resolve_session` is pure-functional and never logs raw tokens. Error messages are precise and actionable per FR-024 (multi-line listing of fixes), avoiding speculative dumps. |
| IV. Two Data Paths | PASS | Auth redesign is data-path-agnostic. Both live queries (`mp query ...`) and streaming/discovery commands share the same `Session` resolution. `MixpanelAPIClient` accepts a `Session` regardless of whether the caller is a live-query method, a streaming method, or an entity CRUD command. |
| V. Explicit Over Implicit | PASS | `Workspace.use(account=...)` explicitly clears in-session project state (FR-033) so cross-account project access is never silently assumed. `--target` is mutually exclusive with `--account`/`--project`/`--workspace` (FR-043). `mp config convert` is opt-in (FR-072) — runtime auto-conversion is rejected per design decision §18 #8. No silent fallback across resolution axes (FR-016, FR-024). The active session is explicit in `[active]`; there is no "first-available" account fallback. |
| VI. Unix Philosophy | PASS | CLI loops compose naturally: `mp project list -f jsonl | jq -r .id | xargs -I{} mp --project {} <command>`. Per-command `--account`/`--project`/`--workspace`/`--target` flags do not modify `[active]`. Errors go to stderr; data goes to stdout. Plugin `auth_manager.py` produces stable JSON shapes consumable by other tools. |
| VII. Secure by Default | PASS | All account state files at `~/.mp/accounts/{name}/` written with `0o600`; parent dir `0o700` (FR-054). Secrets never appear in CLI args (always env or stdin or interactive only for `mp account login`). `Account.secret`/`Account.token` are `SecretStr` (Pydantic redaction in repr). Bridge file written with `0o600` and embeds full account record only because Cowork crosses a trust boundary by design. `os.environ` mutation forbidden (FR-023). |

**Gate Result**: PASS — No violations. Proceeding to Phase 0.

**Notes for re-evaluation after Phase 1 design**:
- The bridge file embedding the full account record (with refresh token) is a documented exception to "secrets stay in config files only" — it's necessary for Cowork's host→VM credential transfer and matches the existing v1/v2 bridge behavior. No new violation.
- Lazy workspace auto-resolution (FR-025) is a "magic" behavior in tension with V (Explicit Over Implicit). Justification: every Mixpanel project guarantees a default workspace (verified per source review §13.2), so the lazy resolution is deterministic and never surprises the user. The alternative (always-required workspace) would force network I/O at every Session construction — a worse violation of III (Context Window Efficiency) and I (Library-First, since cheap Workspace construction is a public API contract). Documented in Complexity Tracking.

## Project Structure

### Documentation (this feature)

```text
specs/042-auth-architecture-redesign/
├── plan.md                         # This file
├── spec.md                         # Feature specification
├── research.md                     # Phase 0 output (this command)
├── data-model.md                   # Phase 1 output (this command)
├── quickstart.md                   # Phase 1 output (this command)
├── contracts/                      # Phase 1 output (this command)
│   ├── python-api.md               # Public Python API contracts (mp.accounts/.targets/.session, Workspace.use)
│   ├── cli-commands.md             # CLI command contracts (mp account/project/workspace/target/session, mp config convert)
│   ├── config-schema.md            # ~/.mp/config.toml v3 schema + bridge v2 schema
│   ├── plugin-auth-manager.md      # auth_manager.py JSON output contracts
│   └── filesystem-layout.md        # ~/.mp/accounts/{name}/ + bridge file path conventions
├── checklists/
│   └── requirements.md             # Spec quality checklist (already created by /speckit.specify)
└── tasks.md                        # Phase 2 output (via /speckit.tasks)
```

### Source Code (repository root)

```text
src/mixpanel_data/
├── __init__.py                              # MODIFIED — re-export Account, Session, Project, WorkspaceRef, Target, AccountSummary; remove deleted names
├── workspace.py                             # MODIFIED — accept account/project/workspace/target/session in __init__; add use(); remove switch_project/switch_workspace/discover_*/current_*; replace ResolvedSession with Session
├── auth.py                                  # MODIFIED — re-export Account variants; remove AuthCredential/Credentials re-exports
├── exceptions.py                            # MODIFIED — keep AuthenticationError/OAuthError/ConfigError; remove MigrationResult
├── types.py                                 # MODIFIED — add AccountSummary, Target, AccountTestResult; remove AccountInfo, CredentialInfo, ProjectAlias
├── _internal/
│   ├── api_client.py                        # MODIFIED — accept Session in __init__; add use(account=,project=,workspace=); cache resolved workspace per session lifetime; remove with_project, _session_to_credentials
│   ├── config.py                            # MODIFIED — shrink from 1937 → ~600 LOC: rewrite to single resolve_session(), single ConfigManager; delete v1 paths and v1↔v2 bridge; reject legacy schemas with ConfigError pointing at `mp config convert`
│   ├── pagination.py                        # UNCHANGED
│   ├── auth_credential.py                   # DELETED (replaced by _internal/auth/account.py + session.py)
│   ├── me.py                                # MODIFIED — drop OAuthTokens.project_id field reads/writes; storage path moves to ~/.mp/accounts/{name}/me.json
│   ├── auth/
│   │   ├── __init__.py                      # MODIFIED — export Account, Session, Project, WorkspaceRef
│   │   ├── account.py                       # NEW — Account discriminated union (ServiceAccount, OAuthBrowserAccount, OAuthTokenAccount), TokenResolver protocol
│   │   ├── session.py                       # NEW — Project, WorkspaceRef, Session with replace()
│   │   ├── resolver.py                      # NEW — single resolve_session() with three independent axes
│   │   ├── token_resolver.py                # NEW — concrete TokenResolver impl: reads ~/.mp/accounts/{name}/tokens.json or env vars
│   │   ├── flow.py                          # MODIFIED — storage path change only (~/.mp/oauth/ → ~/.mp/accounts/{name}/)
│   │   ├── pkce.py                          # UNCHANGED
│   │   ├── client_registration.py           # MODIFIED — storage path change only
│   │   ├── callback_server.py               # UNCHANGED
│   │   ├── storage.py                       # MODIFIED — per-account directory layout; rename oauth/ → accounts/
│   │   ├── token.py                         # MODIFIED — drop OAuthTokens.project_id
│   │   └── bridge.py                        # MODIFIED — new v2 bridge schema embedding full Account record; load_bridge() returns synthetic config source for resolver
│   └── services/
│       ├── discovery.py                     # MODIFIED — Workspace.projects()/workspaces() route through public namespace; remove discover_projects naming
│       └── live_query.py                    # UNCHANGED
└── cli/
    ├── main.py                              # MODIFIED — register account/project/workspace/target/session groups; add --account/-a, --project/-p, --workspace/-w, --target globals; remove --workspace-id, --credential
    ├── utils.py                             # MODIFIED — get_workspace() resolves from new resolver; show_session() formatter
    ├── formatters.py                        # MODIFIED — add account_summary, target, session formatters
    └── commands/
        ├── auth.py                          # DELETED (replaced by account.py)
        ├── projects.py                      # DELETED (replaced by project.py)
        ├── workspaces_cmd.py                # DELETED (replaced by workspace.py)
        ├── context.py                       # DELETED (replaced by session.py)
        ├── account.py                       # NEW — list/add/remove/use/show/test/login/logout/token/export-bridge/remove-bridge
        ├── project.py                       # NEW — list (with --remote, --refresh) /use/show
        ├── workspace.py                     # NEW — list/use/show
        ├── target.py                        # NEW — list/add/remove/use/show
        ├── session.py                       # NEW — show (default) / --bridge
        └── config_cmd.py                    # NEW — convert (one-shot legacy → v3)

mixpanel-plugin/
├── plugin.json                              # MODIFIED — version 5.0.0
├── README.md                                # MODIFIED — new vocabulary, new commands
├── commands/
│   └── auth.md                              # MODIFIED — slash command routing without v1/v2 branches
└── skills/
    ├── mixpanelyst/
    │   └── scripts/
    │       └── auth_manager.py              # REWRITTEN — ~727 → ≤300 LOC; subcommands map 1:1 to new CLI verbs; stable JSON output
    ├── setup/
    │   └── SKILL.md                         # MODIFIED — fresh-install walkthrough with new command names; no migration step
    └── dashboard-expert/                    # UNCHANGED

tests/
├── unit/
│   ├── test_account.py                      # NEW — Account discriminated union tests
│   ├── test_session.py                      # NEW — Session, Project, WorkspaceRef, replace()
│   ├── test_resolver.py                     # NEW — single resolve_session(), per-axis priority, env wins, target mutual exclusion
│   ├── test_token_resolver.py               # NEW — TokenResolver loads from disk and env
│   ├── test_config_v3.py                    # NEW — ConfigManager CRUD against new schema; rejection of legacy schemas
│   ├── test_workspace_use.py                # NEW — Workspace.use() per-axis switching cost contract
│   ├── test_bridge_v2.py                    # MODIFIED (new file replacing existing test_auth_bridge.py) — new schema, headers attached to Account in memory
│   ├── test_storage_v3.py                   # MODIFIED (new file replacing test_auth_storage.py) — per-account directory layout
│   ├── test_me_v3.py                        # MODIFIED — cache path change; OAuthTokens.project_id removal
│   ├── test_config_v2.py                    # DELETED — covered by conversion fixture tests in tests/integration/
│   ├── test_migration.py                    # DELETED
│   ├── test_workspace_oauth.py              # DELETED — v1 cases removed; v2 cases moved into test_workspace_use.py + test_resolver.py
│   ├── test_auth_credential.py              # DELETED
│   ├── test_auth_bridge.py                  # DELETED (replaced by test_bridge_v2.py)
│   ├── test_auth_storage.py                 # DELETED (replaced by test_storage_v3.py)
│   └── cli/
│       ├── test_account_cli.py              # NEW — `mp account` snapshot tests for each --type
│       ├── test_project_cli.py              # NEW — `mp project list/use/show`
│       ├── test_workspace_cli.py            # NEW — `mp workspace list/use/show`
│       ├── test_target_cli.py               # NEW — `mp target add/use/list`
│       ├── test_session_cli.py              # NEW — `mp session` and `mp session --bridge`
│       ├── test_config_convert_cli.py       # NEW — `mp config convert` happy path + idempotency
│       ├── test_auth_cli.py                 # DELETED
│       ├── test_projects_cli.py             # DELETED
│       ├── test_workspaces_cli.py           # DELETED
│       └── test_context_cli.py              # DELETED
├── pbt/
│   ├── test_account_pbt.py                  # NEW — discriminated union round-trip serialization
│   ├── test_resolver_pbt.py                 # NEW — resolver determinism + axis independence (Hypothesis)
│   └── test_session_pbt.py                  # NEW — Session.replace() invariants
├── integration/
│   ├── test_config_conversion.py            # NEW — fixture v1/v2 configs convert correctly; OAuth tokens migrate to new paths; alpha-tester fixtures
│   ├── test_cross_project_iteration.py      # NEW — Workspace.use(project=) preserves transport, no re-auth
│   ├── test_cross_account_iteration.py      # NEW — Workspace.use(account=) clears project state; new auth header
│   ├── test_plugin_auth_manager.py          # NEW — subprocess test of every auth_manager.py subcommand against fixture configs
│   └── test_workspace_lazy_resolve.py       # NEW — Session(workspace=None) auto-resolves on first workspace-scoped call
└── fixtures/
    ├── configs/
    │   ├── v1_simple.toml                   # NEW — minimal v1 (one account)
    │   ├── v1_multi.toml                    # NEW — 7 accounts sharing creds (the demo case from spec §1.1)
    │   ├── v2_simple.toml                   # NEW — credentials + projects + active
    │   ├── v2_multi.toml                    # NEW — multiple credentials + project aliases
    │   ├── v3_simple.toml                   # NEW — single account + active
    │   └── v3_multi.toml                    # NEW — three accounts + targets + active
    └── oauth/
        └── tokens_us.json                   # NEW — legacy token file used by conversion tests

CLAUDE.md                                    # MODIFIED — top-level: new vocabulary, new env vars (drop v1/v2 references), new auth subsystem section
src/mixpanel_data/CLAUDE.md                  # MODIFIED — package overview with Account → Project → Workspace
src/mixpanel_data/cli/CLAUDE.md              # MODIFIED — CLI command tree with new groups
context/mixpanel_data-design.md              # MODIFIED — auth section rewrite
context/auth-project-workspace-redesign.md   # ARCHIVED — add superseded-by header pointing to auth-architecture-redesign.md
```

**Structure Decision**: Extends the existing single-project layout (Library + CLI + plugin). Keeps the `src/mixpanel_data/_internal/auth/` directory introduced for the v2 OAuth machinery and adds three new modules (`account.py`, `session.py`, `resolver.py`, `token_resolver.py`) alongside the surviving PKCE/DCR/callback machinery. Deletes 10 files outright (legacy auth_credential.py, four CLI command modules, and their corresponding tests). Plugin and CLI rewrites are mechanical because both layers are thin wrappers over the new Python public namespaces.

The 9 source-design phases map to a single PR sequence (each phase one PR or one PR group):
1. **Phase 1 (Types)**: `_internal/auth/account.py`, `_internal/auth/session.py`, plus PBT tests. No behavior change. Merges first.
2. **Phase 2 (Resolver + ConfigManager)**: `_internal/auth/resolver.py`, `_internal/auth/token_resolver.py`, `_internal/config.py` rewrite. Merges only after Phase 1.
3. **Phase 3 (API client + Workspace)**: `_internal/api_client.py`, `workspace.py`, `_internal/auth/storage.py` (path changes), `_internal/me.py` (drop project_id field). Merges after Phase 2.
4. **Phase 4 (CLI)**: `cli/main.py`, `cli/commands/{account,project,workspace,target,session,config_cmd}.py` plus snapshot tests. Old command files deleted in same PR. Merges after Phase 3.
5. **Phase 5 (Plugin)**: `mixpanel-plugin/skills/mixpanelyst/scripts/auth_manager.py` rewrite + slash command + setup skill updates. Merges after Phase 4.
6. **Phase 6 (Bridge)**: `_internal/auth/bridge.py` v2 schema + `cli/commands/account.py` export-bridge/remove-bridge subcommands. Merges after Phase 4 (independent of Phase 5).
7. **Phase 7 (Docs)**: `CLAUDE.md` + `src/.../CLAUDE.md` + design doc archive. Lands continuously across earlier phases.
8. **Phase 8 (Migration script + release)**: `cli/commands/config_cmd.py` finalization, conversion fixture corpus, version bump, release notes. Merges last.

Phase 0 (this command) produces research.md + data-model.md + contracts/ + quickstart.md.

## Constitution Re-Check (Post-Phase-1 Design)

Re-evaluated after producing data-model.md, contracts/, and quickstart.md:

| Principle | Status | Post-design evidence |
|-----------|--------|----------------------|
| I. Library-First | PASS | `mp.accounts.*` / `mp.targets.*` / `mp.session.*` namespaces are documented in [contracts/python-api.md](contracts/python-api.md) before any CLI binding. CLI in [contracts/cli-commands.md](contracts/cli-commands.md) explicitly delegates to these namespaces. |
| II. Agent-Native | PASS | All CLI commands have JSON output formats and stable exit codes. Plugin `auth_manager.py` JSON contract is locked in [contracts/plugin-auth-manager.md](contracts/plugin-auth-manager.md) with `schema_version: 1` and discriminated `state` field. No interactive prompts except `mp account login` (browser by design). |
| III. Context Window Efficiency | PASS | `/me` cache layout in [contracts/filesystem-layout.md](contracts/filesystem-layout.md) preserves the 24h TTL; `Workspace.use(project=)` cost contract (≤5 ms, no API call) verified in [contracts/python-api.md](contracts/python-api.md) §3. Cross-project iteration explicitly preserves connection pool. |
| IV. Two Data Paths | PASS | `Session` consumed by both `MixpanelAPIClient` (live queries) and the streaming/discovery services unchanged. Auth redesign is data-path-agnostic. |
| V. Explicit Over Implicit | PASS WITH JUSTIFICATION | Lazy workspace auto-resolution remains the only "magic" behavior; documented in Complexity Tracking below. All other behavior is explicit per the contracts. |
| VI. Unix Philosophy | PASS | Output formats locked in [contracts/cli-commands.md](contracts/cli-commands.md) §10. Quickstart shows `mp project list -f jsonl | jq | xargs` patterns. stderr/stdout split documented in §12.2. |
| VII. Secure by Default | PASS | Permissions matrix in [contracts/filesystem-layout.md](contracts/filesystem-layout.md) §3 enforces `0o600`/`0o700` everywhere. `SecretStr` redaction enforced in `Account` models. Bridge file's secret embedding documented as a deliberate trust-boundary exception. |

**Post-design Gate Result**: PASS — no new violations introduced by Phase 1 design.

## Complexity Tracking

> Per the Constitution Re-Check, one design choice creates apparent tension with Principle V (Explicit Over Implicit) and warrants documentation:

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| Lazy workspace auto-resolution (FR-025) — `Session(workspace=None)` triggers a network call to `/api/app/projects/{pid}/workspaces/public` on the first workspace-scoped API call, not at Session construction | Every Mixpanel project is born with a default workspace (verified per source review §13.2 — `webapp/project/utils.py:271`); the resolution is deterministic and never user-surprising. Lazy means cheap Session construction (no network I/O), which matters for cross-project iteration (no per-iteration `/me` refetch). | Always-required workspace would force every Session construction to hit `/projects/{pid}/workspaces/public` (or `/me`) before any API call. This penalizes every CLI invocation, every `Workspace()` construction, and especially cross-project loops (where each `ws.use(project=...)` would need a workspace fetch before any operation). Cheap construction is a public API contract per Principle I (Library-First) and III (Context Window Efficiency); they win the tradeoff. |
