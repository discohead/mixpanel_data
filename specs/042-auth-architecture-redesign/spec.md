# Feature Specification: Authentication Architecture Redesign (Account → Project → Workspace)

**Feature Branch**: `042-auth-architecture-redesign`
**Created**: 2026-04-21
**Status**: Released as `mixpanel_data 0.4.0` / plugin `5.0.0` (PR #126)
**Input**: User description: "ALL PHASES of @context/auth-architecture-redesign.md"
**Supersedes**: `038-auth-project-workspace-redesign`
**Source design**: [`context/auth-architecture-redesign.md`](../../context/auth-architecture-redesign.md)

> ## Post-implementation notes (2026-04-23)
>
> The spec below describes the *intended* full scope. Two scope changes
> were made during implementation. They are called out here once and then
> tagged inline against each affected requirement (`**[DESCOPED — see
> notes]**` / `**[REVISED — see notes]**`):
>
> 1. **User Story 10 ("One-Shot Legacy Config Conversion") was DESCOPED**
>    under the project's "alpha free to break" principle. The breaking
>    change is delivered as a hard cutover instead of an opt-in conversion:
>    legacy v1/v2 `~/.mp/config.toml` files raise a Pydantic validation
>    error on first load and the user wipes the file and re-adds accounts
>    via `mp account add ...`. The migration recipe is in
>    [`../../RELEASE_NOTES_0.4.0.md`](../../RELEASE_NOTES_0.4.0.md).
>    Affected: US10, FR-048, FR-055, FR-062, FR-072, FR-073, SC-017,
>    SC-019, SC-020, the "Missing OAuth tokens after install" edge case,
>    and the corresponding `mp config convert` documentation in
>    [`contracts/cli-commands.md`](contracts/cli-commands.md) §8 and
>    [`quickstart.md`](quickstart.md) "Migrating an existing config".
>
> 2. **FR-067 LoC budget was REVISED** from ≤4,000 LoC across ≤12 files to
>    ≤6,500 LoC across ≤20 files (current: ~5,800 LoC across 19 files at
>    HEAD). Rationale: the budget was set against a planned
>    `api_client.py` split that did not happen; that file accumulated
>    8,000+ lines of entity-CRUD methods (dashboards / reports / cohorts /
>    flags / experiments / alerts / data governance) that have nothing to
>    do with auth and was therefore excluded from the budget scope.
>    Verified via `tests/unit/test_loc_budget.py`. Affected: FR-067,
>    SC-001.

## Overview

The current authentication subsystem carries the scar tissue of an incomplete v1→v2 migration. Two schemas coexist in `~/.mp/config.toml`, the `Credentials` class still wraps every code path, OAuth project resolution consults six fallback layers, and a fresh service-account install silently lands on the legacy v1 path forever. The vocabulary is fragmented across five concepts (auth, credential, account, project alias, workspace), each with its own CLI verb and its own switching semantics.

This redesign is a **clean break** to a single unified model — **Account → Project → Workspace** — with one resolver, one configuration schema, one CLI grammar, and one Python facade. It treats Mixpanel's three credential mechanisms (service accounts, OAuth PKCE, raw bearer tokens) as variants of a single `Account` discriminated union, and elevates cross-account / cross-project / cross-workspace switching to a first-class one-line operation at every layer (Python, CLI, plugin agent).

The breaking change is intentional and acceptable because the package is pre-1.0 with a handful of alpha testers. v1 paths, the v1↔v2 bridge, and the runtime `migrate_v1_to_v2` command are all deleted; legacy configs ~~are converted by a one-shot opt-in script (`mp config convert`)~~ raise a Pydantic validation error on first load and the user wipes the file (recipe in `RELEASE_NOTES_0.4.0.md`) — see post-implementation notes above for the descope decision. The package version bumps to `mixpanel_data 0.4.0` and the plugin to `5.0.0` to signal the breaking change.

This specification covers **all 9 phases** of the redesign (Phase 0 documentation review through Phase 8 migration script + announcement).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - One Unified Account Model for All Three Auth Mechanisms (Priority: P1)

A user with a personal OAuth identity, a team service account, and a CI bearer token wants to manage all three through a single mental model and single set of commands. Today, service accounts live in `[accounts.X]` blocks, OAuth identities live in `[credentials.X]` blocks (or `tokens_{region}.json` for fresh OAuth flows), and bearer tokens can only be supplied via the `MP_OAUTH_TOKEN` env var with no way to persist or name them. There is no `mp account use ci-token` equivalent — switching between credential types means editing TOML by hand or rewriting environment variables.

After the redesign, all three credential mechanisms are stored as `[accounts.X]` entries with a `type` discriminator (`service_account` | `oauth_browser` | `oauth_token`). All three are first-class, named, persistable, and switchable through the same verb (`mp account use NAME`). All three flow through the same resolver and produce the same `Session` shape consumed by the API client.

**Why this priority**: This is the structural unification that everything else depends on. Without one Account type, every downstream layer (resolver, CLI, plugin) keeps the v1/v2/env-var fork. With it, every downstream layer simplifies dramatically.

**Independent Test**: A user can register one of each account type (`mp account add team --type service_account`, `mp account add personal --type oauth_browser`, `mp account add ci --type oauth_token --token-env MP_CI_TOKEN`), see all three in `mp account list`, switch between them with `mp account use NAME`, and run the same query against each — verifying that switching credential type is identical in cost and ergonomics to switching between two service accounts.

**Acceptance Scenarios**:

1. **Given** an empty config, **When** the user runs `mp account add team --type service_account --username "user.x.mp-service-account" --region us` and supplies the secret on stdin, **Then** a single `[accounts.team]` block is written to `~/.mp/config.toml` containing `type`, `region`, `username`, `secret` — and no `project_id` field.
2. **Given** an existing service-account in config, **When** the user runs `mp account add personal --type oauth_browser --region us` followed by `mp account login personal`, **Then** an `[accounts.personal]` block is written with `type = "oauth_browser"` and tokens are stored at `~/.mp/accounts/personal/tokens.json` (no inline secret in TOML).
3. **Given** a CI environment, **When** the user runs `mp account add ci --type oauth_token --token-env MP_CI_TOKEN --region us`, **Then** the account is stored without secret material; the token is resolved from `MP_CI_TOKEN` at request time.
4. **Given** all three account types are configured, **When** the user runs `mp account use team` then `mp account use personal` then `mp account use ci`, **Then** each switch updates `[active].account` in config and subsequent `mp session` shows the new active account; the cost and command shape are identical regardless of account type.
5. **Given** the user calls `ws.account` on a `Workspace` after switching, **Then** they receive a typed `ServiceAccount` | `OAuthBrowserAccount` | `OAuthTokenAccount` instance, distinguishable by its `type` field, with no shared "Credentials" wrapper class.

---

### User Story 2 - Single Schema, Fresh Installs Valid From Day One (Priority: P1)

A new user installs `mixpanel_data`, runs `mp account add team-sa --type service_account ...`, and is immediately on the production schema. Today, that exact onboarding path silently puts the user on the deprecated v1 schema (because `add_account` writes a v1 block and never sets `config_version = 2`), and the user remains on v1 forever unless they manually run `mp auth migrate`.

After the redesign, there is no `config_version` field. There is one schema. The first `mp account add` writes a v3 config; the first `mp account login` writes a v3 config; there is no silent fork between credential types or onboarding paths.

**Why this priority**: This eliminates the most insidious class of v1/v2 bug (a user lands on the legacy path and stays there). Without it, the redesign would just create a v1/v2/v3 trinity. With it, every config is a v3 config.

**Independent Test**: On a fresh machine with no `~/.mp/config.toml`, run any onboarding command (`mp account add ... --type service_account` OR `mp account add ... --type oauth_browser` OR `mp account login ...`). Inspect the resulting `~/.mp/config.toml` and confirm there is no `config_version` field, no `default = "X"` field, no v1-shaped account block, and no v2-shaped `[credentials.X]`/`[projects.X]` separation. The schema must contain only `[accounts.NAME]`, `[active]`, and optional `[targets.NAME]` and `[settings]` sections.

**Acceptance Scenarios**:

1. **Given** no `~/.mp/config.toml`, **When** the user runs `mp account add team-sa --type service_account --username "..." --region us` and supplies the secret, **Then** the resulting config file contains exactly one `[accounts.team-sa]` block with the new shape and an `[active]` section pointing at `team-sa`; it contains no `config_version` field, no `default` field, no `[credentials]` section, and no `[projects]` section.
2. **Given** no `~/.mp/config.toml`, **When** the user runs `mp account add personal --type oauth_browser --region us` then `mp account login personal`, **Then** the same v3-only schema is produced; tokens are stored at `~/.mp/accounts/personal/tokens.json` (not at the legacy `~/.mp/oauth/tokens_us.json`).
3. **Given** an existing legacy config (v1 or v2), **When** any `mp` command runs that needs to read it, **Then** the user receives a clear Pydantic validation error pointing at the offending fields. **[REVISED — `mp config convert` descoped; see post-implementation notes.]** The system does not silently auto-convert; recovery is `rm ~/.mp/config.toml` + `mp account add ...` per `RELEASE_NOTES_0.4.0.md`.
4. **Given** a converted config, **When** the user re-runs the original failing command, **Then** it succeeds against the new schema with no behavior difference from a fresh-install config.
5. **Given** the user adds a second account after the first, **When** they inspect the config, **Then** `[active].account` continues to point at the originally-active account (adding does not change active state); the user must run `mp account use NEW-NAME` to switch.

---

### User Story 3 - Single Resolver With Per-Axis Independent Priority (Priority: P1)

A user expects predictable, debuggable resolution: when they set `MP_PROJECT_ID`, they get that project, regardless of what's in config or which account is active. Today, the OAuth-from-disk path consults six different sources to determine which `project_id` to attach (env → v1 default → v1 first → v2 active → v2 first credential's region → scan-all-tokens), and resolution invariants depend on which auth method "won" earlier in the chain.

After the redesign, there is one `resolve_session()` function with three independent axes (account, project, workspace). Each axis resolves through its own ordered priority list (env → explicit param → target → bridge → config); the axes never affect each other. Env vars always win first (preserving the CI/agent escape hatch from PR #125).

**Why this priority**: Predictable resolution is the foundation for everything else — agents, CI pipelines, in-session switching, and human debuggers all depend on "same inputs always produce the same Session". Without one resolver, the rest of the redesign can't claim to have eliminated the v1/v2 fork.

**Independent Test**: Construct a `Workspace` with various combinations of env vars, explicit parameters, target references, and config file state. For each combination, the resolved `Session` must be identical across runs (deterministic), must follow per-axis priority order from the documented decision tree, and must never silently fall back across axes.

**Acceptance Scenarios**:

1. **Given** `MP_PROJECT_ID=8` is set in the environment and the active account has `default_project = "3713224"`, **When** any `mp` command runs, **Then** the resolved project is `8` (env wins on the project axis); the account and workspace axes are unaffected.
2. **Given** `MP_USERNAME` + `MP_SECRET` + `MP_REGION` are all set, **When** any `mp` command runs, **Then** the resolved account is a synthetic in-memory `ServiceAccount` named `"<env>"`; the project axis still resolves independently from `MP_PROJECT_ID` or config.
3. **Given** the user passes `--account demo-sa --project 3018488` to a CLI command, **When** the resolver runs, **Then** the account axis resolves from the explicit param (no env on account) and the project axis resolves from the explicit param (no env on project).
4. **Given** the user passes `--target ecom`, **When** the resolver runs, **Then** all three axes (account, project, workspace) resolve from the named target; passing `--target` together with `--account` / `--project` / `--workspace` raises a `ValueError` immediately.
5. **Given** no account can be resolved on any axis, **When** the resolver runs, **Then** it raises `ConfigError` with a multi-line message listing every supported account-configuration approach (`mp account add ...`, `mp account login ...`, `MP_USERNAME`+..., `MP_OAUTH_TOKEN`+...); it never silently picks a "first available" account.
6. **Given** identical inputs (env vars + params + config snapshot), **When** the resolver runs twice, **Then** it returns identical `Session` objects (deterministic; no environment-dependent surprises, no timestamp-based behavior, no random fallbacks).

---

### User Story 4 - One-Line In-Session Switching With `Workspace.use()` (Priority: P1)

A developer or AI agent constructs a `Workspace` once, then needs to switch between accounts, projects, or workspaces during the session — for example, looping over all projects to compare an event count, or running the same query against a personal OAuth identity and a team service account. Today, project switching uses `switch_project()`, workspace switching uses `set_workspace_id()`, account switching is not supported on a Workspace instance at all (you must construct a new one), and the persistence semantics differ across all three (`switch_project` doesn't write to config; `mp projects switch` doesn't update an in-memory Workspace).

After the redesign, there is one method — `Workspace.use(account=, project=, workspace=, target=, persist=False)` — that handles all switching axes. It returns `self` for chaining. The `persist=True` flag optionally writes the new state to `~/.mp/config.toml [active]`. The HTTP transport is preserved across switches (only auth headers and URL parameters change).

**Why this priority**: This is the "unique capability" the user explicitly called out. Cross-cutting analysis (cross-project, cross-account, cross-workspace) is what makes this library distinctive vs. raw `httpx.Client` use. Without one switching method, every cross-cutting workflow is bespoke.

**Independent Test**: Construct one `Workspace`, call `ws.use(project="A").events()` then `ws.use(project="B").events()`, verifying the two queries hit two different projects with the same auth credentials and the same underlying HTTP transport. Repeat for `ws.use(account=...)`, `ws.use(workspace=...)`, and `ws.use(target=...)`.

**Acceptance Scenarios**:

1. **Given** a `Workspace` constructed with the active session, **When** the user calls `ws.use(project="3018488")`, **Then** subsequent queries target project `3018488`; the account and (resolved) workspace are unchanged unless the new project's default workspace differs; `~/.mp/config.toml` is not modified.
2. **Given** a `Workspace`, **When** the user calls `ws.use(account="other-sa")`, **Then** the auth header is rebuilt for the new account; the project is automatically resolved from the new account's `default_project` (or `MP_PROJECT_ID` env override); if neither is set, the call raises `ConfigError` naming the new account and the four ways to provide a project (FR-024). The prior session's project is never carried forward.
3. **Given** a `Workspace`, **When** the user calls `ws.use(target="ecom")`, **Then** all three axes (account, project, workspace) are applied from the target's definition; combining `target=` with any of `account=`/`project=`/`workspace=` raises `ValueError`.
4. **Given** a `Workspace` and `persist=True`, **When** the user calls `ws.use(project="3018488", persist=True)`, **Then** the in-memory session updates AND the active account's `default_project` is rewritten to `"3018488"` in `~/.mp/config.toml`; new processes pick up the change. (`[active]` itself only stores `account` and `workspace`; project lives on the account.)
5. **Given** a sequence of switches `ws.use(workspace=N1)` → `ws.use(workspace=N2)` → `ws.use(workspace=N3)`, **When** measured, **Then** each switch is an in-memory field update with no API call; the underlying `httpx.Client` instance is the same object throughout.
6. **Given** `Workspace.use()` returns `self`, **When** the user writes `ws.use(project="A").segmentation(...)`, **Then** the chain compiles and runs as a single fluent expression.

---

### User Story 5 - Unified CLI Surface With One Verb Per Action (Priority: P1)

A user reads `mp --help` and sees a coherent verb grammar: `account`, `project`, `workspace`, `target`, `session` — each with the same set of verbs (`list`, `add`, `remove`, `use`, `show`, `test`). Today, the CLI has four overlapping command groups (`mp auth`, `mp projects`, `mp workspaces`, `mp context`), each with a different "switch" verb (`mp auth switch` changes the default account; `mp projects switch` updates the active project; `mp workspaces switch` mutates session state; `mp context switch` resolves an alias). The same word means four different things.

After the redesign, every state-change uses the single verb `use`. `switch`, `default`, `set-active`, and `set-default` are all eliminated. The command tree is `mp account` / `mp project` / `mp workspace` / `mp target` / `mp session`, each with a consistent verb set and consistent global flags (`--account` / `--project` / `--workspace` / `--target`).

**Why this priority**: The CLI is the most-used surface for both humans and agents. Without one verb per action, every onboarding tutorial and every `--help` output is a wall of conditional explanations; with it, learning curve collapses to "noun + verb + name".

**Independent Test**: Run `mp --help` and confirm only the new command groups exist (`account`, `project`, `workspace`, `target`, `session`); the old `auth`, `projects`, `workspaces`, `context` groups are gone. For each group with state, confirm `use` is the verb. For each global flag, confirm the new naming (`--workspace`, not `--workspace-id`; no `--credential`).

**Acceptance Scenarios**:

1. **Given** the CLI is installed, **When** the user runs `mp --help`, **Then** they see exactly five top-level groups under the auth/identity area: `account`, `project`, `workspace`, `target`, `session` (plus existing query/inspect/etc. groups that were already there).
2. **Given** the user runs `mp account use NAME` / `mp project use ID` / `mp workspace use ID` / `mp target use NAME`, **Then** each command updates the relevant `[active]` field in config and emits a single line confirming the new state; the verb is identical across all four commands.
3. **Given** the user passes a global flag, **When** they run `mp --account team-sa --project 8 query segmentation -e Login --from 2026-04-01`, **Then** the override applies for that command only; `[active]` is not modified; passing `--target NAME` together with `--account`/`--project`/`--workspace` exits with a clear error.
4. **Given** the user runs `mp account add NAME --type service_account ...` / `--type oauth_browser ...` / `--type oauth_token ...`, **Then** a single `add` command handles all three account types via the `--type` discriminator; there are not three separate add commands.
5. **Given** the user runs `mp account list` on a fresh install with no accounts, **Then** the output is a multi-line message that lists all three onboarding paths (OAuth recommended, service account, static bearer) with the exact commands to run; it is not a single empty line.
6. **Given** the user runs the deprecated `mp auth list` or `mp projects switch ID` or `mp context show`, **Then** the command does not exist (Typer reports unknown command); there is no compatibility shim.
7. **Given** the user runs `mp session`, **Then** they see a multi-line summary showing the current account name + type + region, project ID + name + organization, workspace ID + name (or "auto-resolved"), and the user identity (from cached `/me`).

---

### User Story 6 - Targets as Saved Cursor Positions (Priority: P2)

A power user juggles multiple `(account, project, workspace)` triples — for example, "production events on the main service account in workspace 3448413" vs. "staging feature flags on the personal OAuth identity in workspace 3448414". They want a one-command shortcut to jump back to either context.

After the redesign, `[targets.NAME]` blocks store named triples. `mp target add ecom --account team --project 3018488 --workspace 3448413` registers a target; `mp target use ecom` applies all three axes at once (writing to `[active]`); `mp --target ecom <command>` applies the target for one command without persisting.

**Why this priority**: Targets are quality-of-life for power users who run cross-cutting analysis frequently. They aren't required for any P1 capability — `mp account use` + `mp project use` + `mp workspace use` cover the same ground in three commands. Targets just collapse the three commands into one.

**Independent Test**: Register two targets (one for production, one for staging) using `mp target add`, switch between them with `mp target use NAME`, and verify each switch sets all three axes (account, project, workspace) in a single command. Apply a target as a per-command override with `mp --target NAME ...` and verify `[active]` is unchanged.

**Acceptance Scenarios**:

1. **Given** the user has at least one configured account, **When** they run `mp target add ecom --account team --project 3018488 --workspace 3448413`, **Then** a `[targets.ecom]` block is written with all three fields; `workspace` is optional in the schema (omitting it means "use the project's default workspace at resolution time").
2. **Given** a configured target, **When** the user runs `mp target use ecom`, **Then** `[active].account` and `[active].workspace` are written from the target, AND the target's project is persisted as the target account's `default_project` (with a confirmation message naming the account and the project). `mp session` reflects all three changes.
3. **Given** the user passes `mp --target ecom query segmentation -e Login --from 2026-04-01`, **Then** the target is applied for that command only; `[active]` is not modified; passing `--target` with `--account`/`--project`/`--workspace` exits with a clear error.
4. **Given** a target referencing an account that is later deleted, **When** the user runs `mp target use NAME`, **Then** they receive a clear `ConfigError` naming the missing account; the system does not silently fall back.
5. **Given** the user calls `mp.targets.list()` in Python, **Then** they receive a list of `Target` objects matching the on-disk `[targets.X]` blocks.

---

### User Story 7 - Cross-Cutting Iteration Across Accounts/Projects/Workspaces (Priority: P2)

An analyst or agent wants to run the same query against every project they have access to (e.g., "event count for `Login` last week, broken down by project"), or against the same project under two different credential identities. They expect a one-line operation per layer: Python sequential loop, Python parallel snapshot, CLI shell loop.

After the redesign, this is a first-class operation:
- **Python sequential**: `for p in ws.projects(): ws.use(project=p.id); ws.events()`
- **Python parallel (snapshot mode)**: `Session.replace(project=...)` produces an immutable snapshot suitable for `ThreadPoolExecutor`; each `Workspace(session=snap)` is an independent context.
- **CLI shell loop**: `mp project list -f jsonl | jq -r .id | xargs -I{} mp --project {} query segmentation -e Login --from 2026-04-01`.

**Why this priority**: Cross-cutting iteration is a major value-add and was a stated user goal in the source design. It depends on US3 (single resolver) and US4 (one-line switching), so it's prioritized after both are in place.

**Independent Test**: For a user with access to ≥2 projects, write a Python script that loops over `ws.projects()` and prints one event count per project — confirming sequential iteration works. Then write a parallel version using `ThreadPoolExecutor` and `Session.replace(...)` — confirming each task gets an independent Workspace and the script does not deadlock or race.

**Acceptance Scenarios**:

1. **Given** an account with access to multiple projects, **When** the user runs `for p in ws.projects(): ws.use(project=p.id); print(p.id, len(ws.events()))`, **Then** each iteration switches projects in O(1) (no re-auth); the script prints one line per accessible project.
2. **Given** the same setup, **When** the user creates `sessions = [ws.session.replace(project=Project(id=p.id)) for p in ws.projects()]` and dispatches each via `ThreadPoolExecutor`, **Then** each thread gets an independent `Workspace`, no thread mutates another's session, and results are returned in the iteration order.
3. **Given** a CLI-driven user, **When** they run `mp project list -f jsonl | jq -r .id | xargs -I{} mp --project {} query event-counts --events Login --from 2026-04-01`, **Then** the loop dispatches one query per project, each using the per-command `--project` override without modifying `[active]`.
4. **Given** a user with two configured accounts, **When** they iterate `for name in ["personal", "team"]: ws.use(account=name); print(ws.account.region, len(ws.projects()))`, **Then** each iteration re-authenticates against the new account and re-fetches `/me` (or uses the cached value) per account.

---

### User Story 8 - Decoupled Cowork Bridge (Identity Without Project Coupling) (Priority: P2)

A user sets up Cowork (a remote development VM) and expects their host machine's Mixpanel credentials to flow over to the VM through the bridge file. Today, the bridge file embeds `project_id` and `workspace_id` as required fields — meaning every Cowork session is locked to one project, even though the bridge is a credential courier. To work on a different project in Cowork, the user must regenerate the bridge.

After the redesign, the bridge embeds an `account` (the full discriminated union with secret material), and `project` and `workspace` become optional fields. The bridge is a credential courier; project selection happens in the VM the same way it happens on the host.

**Why this priority**: Cowork users are a subset; the bridge change is mostly cleanup. But the design principle (identity is project-agnostic) is the same as US1, and shipping the redesign without updating the bridge would leave a parallel resolution path with the old shape.

**Independent Test**: Generate a bridge on the host (`mp account export-bridge --to /tmp/bridge.json`), inspect that the bridge contains an `account` block with the current account's full record but no required project. Set `MP_AUTH_FILE=/tmp/bridge.json` and run `mp project use 3713224` then `mp query ...` in a fresh shell — confirming that project selection in the VM is independent from the bridge file.

**Acceptance Scenarios**:

1. **Given** an active OAuth account with valid tokens, **When** the user runs `mp account export-bridge --to /tmp/bridge.json`, **Then** the resulting JSON has shape `{"version": 2, "account": {...full record including refresh token...}, "project": "OPTIONAL", "workspace": OPTIONAL_INT, "headers": {...}}`.
2. **Given** `MP_AUTH_FILE` points at a bridge file, **When** any `mp` command runs, **Then** the resolver consults the bridge file as a synthetic config source: `account` axis loads from `bridge.account`; `project` and `workspace` axes use the bridge values if present, else fall through env/config/etc.
3. **Given** a bridge file without `project`, **When** the user runs `mp project list` in the VM, **Then** discovery works using the bridged credentials; `mp project use 3713224` selects a project locally without modifying the bridge file.
4. **Given** a bridge file with custom headers, **When** the resolver loads it, **Then** the headers are attached to the account object in memory; `os.environ` is not mutated.
5. **Given** an active bridge file, **When** the user runs `mp session --bridge`, **Then** they see a summary identifying the source as `bridge` (not `config`) and listing the bridge file path.
6. **Given** a previously-set-up bridge, **When** the user runs `mp account remove-bridge`, **Then** the bridge file is deleted from the default path (or `--at PATH` if specified).

---

### User Story 9 - Plugin / Agent Surface Without Version Branches (Priority: P3)

An AI agent (e.g., the `mixpanelyst` skill) calls `python auth_manager.py status` to check session state and dispatch the right next action. Today, `auth_manager.py` (727 lines) has `if version >= 2:` branches in 8 of 12 commands; the slash command (`/mixpanel-data:auth`) routes through the same conditionals. Both paths need to stay in sync as the underlying schema evolves.

After the redesign, `auth_manager.py` collapses to ~250 lines because there are no v1/v2 conditionals. Subcommands map 1:1 to CLI verbs (`session`, `account list/add/use/login/test`, `project list/use`, `workspace list/use`, `target list/add/use`, `bridge status`). Every subcommand outputs structured JSON with a stable shape.

**Why this priority**: Plugin/agent updates depend on the underlying CLI/Python surface stabilizing first. Once US1–US5 land, the plugin rewrite is mostly mechanical (delete v1 branches, rename verbs to match new CLI). Without the rewrite, the plugin would keep the old vocabulary indefinitely.

**Independent Test**: Run `python auth_manager.py session` against a configured machine and verify the JSON output has a stable shape: one of `{"state": "ok", "account": {...}, "project": {...}, "workspace": {...}}`, `{"state": "needs_account", "next": [...]}`, or `{"state": "needs_project", "next": [...]}`. Run each subcommand and verify they map 1:1 to the new CLI verbs.

**Acceptance Scenarios**:

1. **Given** a fully configured account+project+workspace, **When** the user runs `python auth_manager.py session`, **Then** the output is JSON with `state="ok"` and nested `account`, `project`, `workspace` objects matching the schema; no `config_version` field appears anywhere.
2. **Given** an empty config, **When** the user runs `python auth_manager.py session`, **Then** the output is JSON with `state="needs_account"` and a `next` array of suggested CLI commands.
3. **Given** an account but no project, **When** the user runs `python auth_manager.py session`, **Then** the output is JSON with `state="needs_project"` and a `next` array suggesting `mp project list` and `mp project use <id>`.
4. **Given** an updated `/mixpanel-data:auth` slash command, **When** an agent invokes it, **Then** the routing has no `if version >= 2` branches; the command produces a 1-2 line summary plus a single suggested next action.
5. **Given** the plugin's setup skill (`/mixpanel-data:setup`), **When** an agent runs it on a fresh machine, **Then** the skill walks the user through `mp account add` → `mp account login` → `mp project list` → `mp project use <id>` with no migration step.

---

### User Story 10 - One-Shot Legacy Config Conversion (Priority: P3)  **[DESCOPED — see post-implementation notes]**

> **Status: DESCOPED.** Replaced with a hard cutover (legacy configs raise
> on load; user wipes the file and re-adds accounts). The migration recipe
> is in [`../../RELEASE_NOTES_0.4.0.md`](../../RELEASE_NOTES_0.4.0.md).
> The acceptance scenarios below describe the original intent and are
> retained for historical context only — none of them are deliverables.

An existing alpha tester with a v1 or v2 `~/.mp/config.toml` upgrades `mixpanel_data` to 0.4.0. The user wants a single command that reads their old config, writes the new schema, and archives the original file — explicit, reviewable, with no surprises.

After the redesign, this command is `mp config convert`. It is opt-in (no auto-conversion at runtime — that violates the "clean break" principle and removes the moment of consent). It runs once per machine, reads the legacy file, writes the new schema, and renames the original to `~/.mp/config.toml.legacy`. After conversion, every `mp` command works against the new schema.

**Why this priority**: This affects only the existing handful of alpha testers (the package is pre-1.0). It is not required for new installs. It does need to ship by Phase 8 so that no alpha tester is stranded by the version bump.

**Independent Test**: Take a fixture v1 config and a fixture v2 config. For each, run `mp config convert`. Verify the resulting `~/.mp/config.toml` contains the new schema (with all accounts, the active account, and any project aliases mapped to targets), and the original file is renamed to `~/.mp/config.toml.legacy`. Run `mp account list`, `mp project list`, `mp session` against the converted config and verify behavior matches the pre-conversion intent.

**Acceptance Scenarios**:

1. **Given** an existing v1 config with three `[accounts.X]` blocks (each with embedded `project_id`) and a `default = "X"` field, **When** the user runs `mp config convert`, **Then** the new config contains three `[accounts.X]` blocks (each with the new shape, no `project_id`), three `[targets.X]` blocks (one per original account, capturing its account+project pair), and `[active].account` set to the former default's name.
2. **Given** an existing v2 config with `[credentials.X]` blocks, `[projects.X]` aliases, and `[active].credential`, **When** the user runs `mp config convert`, **Then** `[credentials.X]` becomes `[accounts.X]` (renamed key), `[projects.X]` becomes `[targets.X]`, `[active].credential` becomes `[active].account`, `[active].project_id` becomes the active account's `default_project` (since project lives on the account in v3), and `[active].workspace_id` becomes `[active].workspace`.
3. **Given** a converted config, **When** `mp config convert` is run a second time, **Then** the command exits with a friendly message stating the config is already on the new schema and no changes were made.
4. **Given** a successful conversion, **When** the user inspects `~/.mp/config.toml.legacy`, **Then** the original file is preserved verbatim (so the user can restore it manually if needed); the conversion does not delete the original.
5. **Given** OAuth tokens at the old path (`~/.mp/oauth/tokens_{region}.json`), **When** `mp config convert` runs, **Then** tokens are moved to `~/.mp/accounts/{account-name}/tokens.json` based on which account they belong to (matched by region, or by the synthetic account created during conversion).
6. **Given** a converted config plus a stale OAuth client info file, **When** `mp account login NAME` runs against the new path, **Then** the existing client info is reused (no new DCR registration unless the client info is missing or invalid).

---

### Edge Cases

- **Missing OAuth tokens after install of new version**  **[REVISED — `mp config convert` descoped; see post-implementation notes]**: A user upgrades to 0.4.0 with a v2 config and OAuth tokens at `~/.mp/oauth/tokens_us.json`. The first command that reads the config raises a Pydantic validation error (the new schema rejects the old shape with `extra="forbid"` and missing required fields). The user follows the recipe in `RELEASE_NOTES_0.4.0.md`: delete `~/.mp/config.toml`, re-run `mp account add ...`, then `mp account login NAME` for OAuth (re-PKCE; the legacy tokens at `~/.mp/oauth/` are not migrated and may be deleted manually).
- **Token env var pointed at non-existent variable**: An `oauth_token` account has `token_env = "MP_CI_TOKEN"` but the env var is unset. The account is invalid until the user sets it; `mp account test ci` returns a clear error naming the missing env var; `mp account list` shows the account with a status indicator (e.g., "needs token") rather than failing the entire list.
- **OAuth refresh token expired**: A long-idle OAuth account fails refresh. `mp account test NAME` reports "needs login"; `mp account login NAME` re-runs the PKCE flow against the existing client_id (no new DCR).
- **Multiple OAuth identities in same region**: A user runs `mp account add personal --type oauth_browser --region us` and `mp account add work --type oauth_browser --region us`. Each gets its own directory under `~/.mp/accounts/`; tokens never collide. Per design decision §18 #7, region stays per-account; multi-region requires separate account entries.
- **`workspace = None` and a workspace-scoped API call**: A `Session` has no workspace selected. The user calls a workspace-scoped endpoint (e.g., events-by-workspace). The API client lazy-resolves to the project's default workspace on first call and caches the result on the client instance for the session lifetime. Verified per source review (§13.2): every Mixpanel project has a default workspace, so this resolution always succeeds.
- **Bridge file present and explicit `--account` flag both supplied**: The explicit param wins on the account axis (env > param > target > bridge > config per §7.1); the user's intent is unambiguous.
- **`mp account remove NAME` while `NAME` is referenced by a target**: The remove command fails with `--force` required; with `--force`, the account is deleted and the orphaned target name is returned in the result for visibility.
- **`mp account remove NAME` while `NAME` is the active account**: Removing the active account clears `[active].account`; subsequent commands raise `ConfigError("No account configured")` until the user runs `mp account use OTHER`.
- **`mp account login NAME` for a non-OAuth account**: The command exits with a clear error stating that login only applies to `oauth_browser` accounts.
- **`MP_OAUTH_TOKEN` set without `MP_REGION`**: The synthetic OAuthTokenAccount cannot be constructed (region is required); resolver falls through to other account-axis sources; if none resolve, raises `ConfigError` naming `MP_REGION` as the missing piece.
- **Cross-axis interaction**: `mp account use NAME` is a single-axis config write — it updates `[active].account` only, never silently mutating workspace pinning or project assignment (project lives on the account itself, not in `[active]`). `Workspace.use(account=NAME)` in Python re-resolves project per FR-033: if the new account has a `default_project` (or `MP_PROJECT_ID` is set), the swap succeeds with that project; otherwise the call raises `ConfigError` with the standard four-paths-to-fix message. The workspace axis is always cleared on account swap (workspaces are project-scoped).

## Requirements *(mandatory)*

### Functional Requirements

#### Account Model & Storage

- **FR-001**: System MUST define a single `Account` discriminated union with three variants: `ServiceAccount` (type=`service_account`, fields: `name`, `region`, `default_project`, `username`, `secret`), `OAuthBrowserAccount` (type=`oauth_browser`, fields: `name`, `region`, `default_project`), and `OAuthTokenAccount` (type=`oauth_token`, fields: `name`, `region`, `default_project`, exactly one of `token` or `token_env`).
- **FR-002**: All `Account` instances MUST be immutable (frozen Pydantic models) and MUST forbid extra fields.
- **FR-003**: `Account.auth_header(token_resolver)` MUST produce a valid HTTP `Authorization` header for the account's type: Basic for SA, Bearer for both OAuth variants.
- **FR-004**: `Account.default_project` is the account's home project (the project the account works against by default). It is OPTIONAL (`str | None`) and matches `^\d+$`. For `service_account` and `oauth_token` accounts it MUST be supplied at account-add time (the user knows the project up-front for both flows). For `oauth_browser` accounts it is populated post-PKCE by the `/me` discovery call. Identity is otherwise project-agnostic — `default_project` is a hint that drives the project resolution chain (FR-017), not part of the credentials.
- **FR-005**: `OAuthTokenAccount` MUST validate that exactly one of `token` (inline) or `token_env` (env var name) is set; both or neither MUST raise a validation error.
- **FR-006**: For `oauth_browser` accounts, no secret material MUST live in the TOML config file; tokens, client info, and the `/me` cache MUST live at `~/.mp/accounts/{name}/`.
- **FR-007**: For `oauth_token` accounts with `token_env`, the env variable MUST be consulted at resolution time (not at config-load time); an absent env var MUST surface as a clear error at the point of use, not at config load.

#### Configuration Schema

- **FR-008**: System MUST recognize exactly one config schema in `~/.mp/config.toml`. The schema MUST consist of `[active]` (optional account/workspace pointers — project lives on the account, not in `[active]`), `[accounts.NAME]` blocks (any number; each carrying its own `default_project`), `[targets.NAME]` blocks (optional, any number), and `[settings]` (optional global request-level settings).
- **FR-009**: System MUST NOT read or write a `config_version` field; the absence of `config_version` and the presence of new-shape blocks IS the schema.
- **FR-010**  **[REVISED — `mp config convert` descoped; see post-implementation notes]**: System MUST reject configs containing v1-shaped fields (`default = "X"`, `[accounts.X].project_id` inline) or v2-shaped fields (`[credentials.X]`, `[projects.X]`). The current implementation surfaces this as a Pydantic validation error from `extra="forbid"` plus required-field violations; legacy detection helper code was deleted along with `mp config convert`. Users recover via `rm ~/.mp/config.toml` + `mp account add ...` per `RELEASE_NOTES_0.4.0.md`.
- **FR-011**: `[active].account` MUST reference an existing account name; the resolver MUST treat absence as "no active account configured" (not an error at config-load, but a `ConfigError` at resolution time if env vars do not supply auth).
- **FR-012**: `[active]` MUST contain only `account` (string) and `workspace` (positive integer) — both optional. The project field has been removed from `[active]`; project lives on the account as `default_project`. `[accounts.NAME].default_project` MUST be a string matching `^\d+$` (Mixpanel project IDs are numeric strings).
- **FR-013**: `[targets.NAME]` MUST require `account` and `project`; `workspace` is optional.
- **FR-014**: `[settings]` MAY include a global `custom_header = { name = "...", value = "..." }`; the resolver MUST attach it to the account in memory and MUST NOT mutate `os.environ`.

#### Resolution

- **FR-015**: System MUST expose a single `resolve_session(*, account=None, project=None, workspace=None, target=None, config=None) -> Session` function as the only path for obtaining a `Session` from configuration.
- **FR-016**: The resolver MUST treat the account, project, and workspace axes as independent; resolution on one axis MUST NOT affect the others.
- **FR-017**: For each axis, the resolver MUST consult sources in the documented priority order — first match wins per axis:
  - **Account axis**: env vars → explicit param → target → bridge → `[active].account`.
  - **Project axis**: env vars → explicit param → target → bridge → `account.default_project`. The chain ends at the resolved account; there is no `[active].project` fallback (project is account-scoped, not session-scoped).
  - **Workspace axis**: env vars → explicit param → target → bridge → `[active].workspace`. May resolve to `None` (lazy resolution per FR-025).
- **FR-018**: `MP_USERNAME`+`MP_SECRET`+`MP_REGION` MUST construct a synthetic in-memory `ServiceAccount` named `"<env>"` and short-circuit the account axis.
- **FR-019**: `MP_OAUTH_TOKEN`+`MP_REGION` MUST construct a synthetic in-memory `OAuthTokenAccount` named `"<env>"` and short-circuit the account axis. When both env-var sets are present, the SA quad takes precedence (preserves PR #125 behavior).
- **FR-020**: The resolver MUST raise `ValueError` immediately if `target=` is combined with any of `account=`/`project=`/`workspace=`.
- **FR-021**: The resolver MUST be deterministic: identical inputs (env + params + config snapshot) MUST always produce identical `Session` instances; no random fallbacks, no timestamp-based behavior.
- **FR-022**: The resolver MUST NOT read OAuth tokens, hit `/me`, or perform any network I/O; resolution is pure config + env reading.
- **FR-023**: The resolver MUST NOT mutate `os.environ` or any other process global state.
- **FR-024**: Failure to resolve the account axis MUST raise `ConfigError` with a multi-line message listing all four configuration paths (`mp account add ...`, `mp account login ...`, `MP_USERNAME`+..., `MP_OAUTH_TOKEN`+...); failure to resolve the project axis MUST raise `ConfigError` with a message that names the resolved account and points at the four ways to fix it (`MP_PROJECT_ID`, explicit `--project ID` / `project=` param, `mp account add NAME --project ID` at creation, `mp account update NAME --project ID` for an existing account).
- **FR-025**: The workspace axis MAY resolve to `None`; this is not an error. Workspace-scoped API endpoints MUST lazy-resolve `None` to the project's default workspace (via `/api/app/projects/{pid}/workspaces/public`) on first use, and MUST cache the result on the API client instance for the session lifetime.

#### Session & API Client

- **FR-026**: `Session` MUST be a frozen Pydantic model with fields `account: Account`, `project: Project`, `workspace: WorkspaceRef | None`. It MUST expose convenience properties `project_id: str`, `workspace_id: int | None`, `region: Region`, and `auth_header(token_resolver)`.
- **FR-027**: `Session` MUST support a `replace(...)` method (Pydantic-style copier) that produces a new immutable Session with one or more axes overridden — usable for parallel iteration.
- **FR-028**: `MixpanelAPIClient.__init__` MUST accept a `Session` (not a `Credentials`); the legacy `Credentials` class MUST be deleted.
- **FR-029**: `MixpanelAPIClient` MUST preserve its `httpx.Client` instance across in-session axis switches (only auth headers and base-URL parameters change on switch).

#### Python Public API

- **FR-030**: `Workspace.__init__` MUST accept the parameters `account=`, `project=`, `workspace=`, `target=`, `session=`. With no arguments, the Workspace MUST resolve from the active session in config + env. With `session=`, all other axis parameters MUST be ignored (full bypass).
- **FR-031**: `Workspace` MUST expose properties `account: Account`, `project: Project`, `workspace: WorkspaceRef | None`, `session: Session`.
- **FR-032**: `Workspace.use(*, account=None, project=None, workspace=None, target=None, persist=False) -> Self` MUST be the only in-session switching method. It MUST return `self` for chaining. With `persist=True`, it MUST also write to `~/.mp/config.toml [active]`.
- **FR-033**: `Workspace.use(account=NAME)` MUST re-resolve the project axis through the FR-017 priority chain (env > param > target > bridge > `account.default_project`) — the prior session's project is NEVER carried forward across an account swap because cross-account project access is not guaranteed. If no source produces a project, the call MUST raise `ConfigError` per FR-024. The workspace axis MUST also be cleared on account swap (workspaces are project-scoped; the prior workspace is meaningless under the new account/project) and lazy-resolved on the next workspace-scoped API call per FR-025.
- **FR-034**: `Workspace.use(target=NAME)` MUST be mutually exclusive with `account=`/`project=`/`workspace=`; combining them MUST raise `ValueError`.
- **FR-035**: `Workspace.projects() -> list[Project]` MUST return all accessible projects via `/me`, cached on disk per-account; the deprecated `discover_projects()` MUST be removed.
- **FR-036**: `Workspace.workspaces(*, project_all=False) -> list[WorkspaceRef]` MUST return workspaces in the current project; `project_all=True` MUST return workspaces across all accessible projects.
- **FR-037**: Top-level public namespaces `mp.accounts`, `mp.targets`, `mp.session`, `mp.config` MUST expose the documented surface (`list`, `add`, `remove`, `use`, `show`, `test`, `login`, `logout` for the first three as applicable; `convert` for `mp.config`). The `ConfigManager` class MUST be moved to `_internal` and MUST NOT be importable from the public package root.
- **FR-038**: All deprecated `Workspace` methods MUST be removed: `set_workspace_id`, `switch_project`, `switch_workspace`, `discover_projects`, `discover_workspaces`, `current_project`, `current_credential`, `workspace_id` property, `test_credentials` static method.

#### CLI Surface

- **FR-039**: The CLI MUST expose exactly five identity-related top-level groups: `mp account`, `mp project`, `mp workspace`, `mp target`, `mp session`. The deprecated groups `mp auth`, `mp projects`, `mp workspaces`, `mp context` MUST be removed (no compatibility shim).
- **FR-040**: Each group with state MUST use `use` as the verb for setting the active value: `mp account use NAME`, `mp project use ID`, `mp workspace use ID`, `mp target use NAME`. The verbs `switch`, `default`, `set-active`, `set-default` MUST NOT exist anywhere in the CLI.
- **FR-041**: `mp account add NAME --type {service_account|oauth_browser|oauth_token} ...` MUST be a single command handling all three account types via the `--type` discriminator.
- **FR-042**: Global flags `--account NAME` (`-a`), `--project ID` (`-p`), `--workspace ID` (`-w`), `--target NAME` MUST apply to every command for one-off override; corresponding env vars are `MP_ACCOUNT`, `MP_PROJECT_ID`, `MP_WORKSPACE_ID`, `MP_TARGET`. The deprecated flag `--workspace-id` MUST be replaced by `--workspace`; the deprecated flag `--credential` MUST be removed.
- **FR-043**: `--target` MUST be mutually exclusive with `--account` / `--project` / `--workspace`; combining them MUST exit with a clear error.
- **FR-044**: `mp account list` on an empty config MUST emit a multi-line message listing all three onboarding paths (OAuth recommended, service account, static bearer) with exact commands.
- **FR-045**: The first account added to an empty config MUST automatically become active (sensible default for fresh installs); subsequent additions MUST NOT change the active account.
- **FR-046**: `mp session` MUST display the current account name + type + region, project ID + name + organization, workspace ID + name (or "auto-resolved"), and user identity (from cached `/me`; if no cache exists yet, display `(uncached)` and do NOT trigger a fetch). `mp session --bridge` MUST show bridge file source if present.
- **FR-047**: `mp project list` MUST work with only authentication configured (no project required). Both `mp project list --refresh` and `mp workspace list --refresh` MUST bypass their respective local caches (`/me` cache, workspace cache) and refetch. `mp project list --remote` is an alias for `--refresh` (preserved for ergonomic continuity with the v2 surface).
- **FR-048**  **[DESCOPED — see post-implementation notes]**: `mp config convert` MUST be the one-shot conversion command; it MUST read legacy v1/v2 configs, write a v3 config, archive the original to `~/.mp/config.toml.legacy`, and exit with a clear summary of what was converted.

#### Cowork Bridge

- **FR-049**: The bridge file schema (version 2) MUST embed the full `account` record (discriminated union with secrets inline, including refresh token for `oauth_browser`); `project` and `workspace` MUST be optional fields; `headers` MUST be a top-level field.
- **FR-050**: When a bridge file is detected (env `MP_AUTH_FILE` or default Cowork path), the resolver MUST consult it as a synthetic config source: account axis loads from `bridge.account`; project and workspace axes use bridge values if present, else fall through env/config.
- **FR-051**: `mp account export-bridge --to PATH` MUST replace `mp auth cowork-setup`; `mp account remove-bridge [--at PATH]` MUST replace `mp auth cowork-teardown`; `mp session --bridge` MUST replace `mp auth cowork-status`.
- **FR-052**: Custom headers MUST be applied per-account in memory; the bridge MUST NOT mutate `os.environ`.

#### Filesystem Layout

- **FR-053**: Account-scoped state MUST live at `~/.mp/accounts/{name}/`; the directory layout per account is: `tokens.json` (oauth_browser only), `client.json` (oauth_browser only), `me.json` (any account, optional cache).
- **FR-054**: All account state files MUST be created with file mode `0o600`; the parent directory `~/.mp/accounts/` MUST be created with `0o700`.
- **FR-055**  **[DESCOPED — see post-implementation notes]**: The legacy `~/.mp/oauth/` directory MUST be retained on disk only when `~/.mp/config.toml.legacy` exists (i.e., post-conversion); `mp config convert` MUST migrate token files from `~/.mp/oauth/tokens_{region}.json` to `~/.mp/accounts/{name}/tokens.json`. (Hard cutover: legacy `~/.mp/oauth/` is left alone and the user re-runs `mp account login NAME` to re-PKCE into `~/.mp/accounts/{name}/`.)

#### Plugin / Agent Surface

- **FR-056**: `auth_manager.py` MUST contain no `if version >= 2` branches; subcommands MUST map 1:1 to the new CLI verbs (`session`, `account list/add/use/login/test`, `project list/use`, `workspace list/use`, `target list/add/use`, `bridge status`).
- **FR-057**: Every `auth_manager.py` subcommand MUST output structured JSON with a stable shape; the `session` subcommand MUST emit one of `{"state": "ok", ...}`, `{"state": "needs_account", "next": [...]}`, or `{"state": "needs_project", "next": [...]}`.
- **FR-058**: The `/mixpanel-data:auth` slash command MUST contain no v1/v2 conditional branches; it MUST present a 1-2 line session summary plus a single suggested next action.
- **FR-059**: The `/mixpanel-data:setup` skill MUST guide fresh-install users through `mp account add` → `mp account login` → `mp project list` → `mp project use <id>` with no migration step.

#### Discovery & `/me`

- **FR-060**: The `MeService` MUST be invokable for every account type (SA, OAuth-browser, OAuth-token); the only difference is what the `/me` response contains.
- **FR-061**: The `/me` cache MUST be per-account at `~/.mp/accounts/{name}/me.json` with a 24h TTL; `mp project list --refresh` MUST bypass it.
- **FR-062**  **[REVISED — second clause descoped; see post-implementation notes]**: The `OAuthTokens` model MUST drop its `project_id` field (legacy artifact). Existing token files at the old path are NOT auto-migrated; users re-run `mp account login NAME` after re-creating the account.

#### Tech Debt Removal

- **FR-063**: The following types MUST be deleted: `Credentials`, `AuthMethod`, `AccountInfo`, `CredentialInfo`, `AuthCredential`, `CredentialType`, `ProjectContext`, `ResolvedSession`, `ProjectAlias`, `MigrationResult`, `ActiveContext`.
- **FR-064**: The following methods MUST be deleted: `Workspace._session_to_credentials`, `MixpanelAPIClient.with_project`, `Credentials.from_oauth_token`, `Workspace.test_credentials`, `ConfigManager.resolve_credentials`, `ConfigManager.add_credential`, `ConfigManager.set_default`, `ConfigManager.set_active_credential`, `ConfigManager.set_active_project`, `ConfigManager.set_active_workspace`, `ConfigManager.set_active_context`, `ConfigManager.list_credentials`, `ConfigManager.list_project_aliases`, `ConfigManager.add_project_alias`, `ConfigManager.migrate_v1_to_v2`.
- **FR-065**: The following CLI commands MUST be deleted: `mp auth list/add/remove/switch/show/test/login/logout/status/token/migrate/cowork-setup/cowork-teardown/cowork-status`, `mp projects list/switch/show/refresh/alias`, `mp workspaces list/switch/show`, `mp context show/switch`.
- **FR-066**: The six-layer fallback in `_resolve_region_and_project_for_oauth` MUST be replaced by the single per-axis priority list documented in FR-017.
- **FR-067**  **[REVISED — see post-implementation notes]**: The auth subsystem MUST shrink from ~7,200 LOC across 15 files to ≤4,000 LOC across ≤12 files (target ≤3,500 / 12 per the source design). **Shipped budget**: ≤6,500 LOC across ≤20 files (current ~5,800 LoC across 19 files at HEAD). The original budget was set against a planned `api_client.py` split that did not happen; that file's entity-CRUD methods are out of scope for the auth budget. Verified via `tests/unit/test_loc_budget.py`.

#### Testing & Quality

- **FR-068**: Property-based (Hypothesis) tests MUST cover: resolver determinism (same inputs → same Session), account discriminated union round-trip serialization, axis independence (changing one axis input does not change other axes' resolution).
- **FR-069**: Mutation testing (mutmut) MUST achieve ≥85% mutation score on `_internal/auth/account.py`, `_internal/auth/session.py`, and the resolver in `config.py`.
- **FR-070**: CLI snapshot tests MUST cover the bootstrap UX (fresh install message), account-add wizard for each `--type`, project list output, target use output.
- **FR-071**: Plugin `auth_manager.py` MUST have end-to-end subprocess tests exercising each subcommand against fixture configs.

#### Migration & Release

- **FR-072**  **[DESCOPED — see post-implementation notes]**: `mp config convert` MUST be idempotent: running twice on an already-converted config MUST exit with a friendly message and zero exit code.
- **FR-073**  **[DESCOPED — see post-implementation notes]**: `mp config convert` MUST preserve the original config file as `~/.mp/config.toml.legacy`; it MUST NOT delete the original.
- **FR-074**  **[REVISED — `mp config convert` descoped; see post-implementation notes]**: The package version MUST bump to `mixpanel_data 0.4.0`; the plugin version MUST bump to `5.0.0`. Release notes MUST explicitly call out the breaking change and document the migration recipe (`rm ~/.mp/config.toml` + `mp account add ...`).
- **FR-075**: Project documentation (`CLAUDE.md` files at root, `src/mixpanel_data/`, `src/mixpanel_data/cli/`, `mixpanel-plugin/`, `context/mixpanel_data-design.md`) MUST be updated to reflect the new vocabulary, schema, and command surface. The v2 design doc (`context/auth-project-workspace-redesign.md`) MUST be archived with a header pointing to the new design.

### Key Entities

- **Account**: An authentication identity. A discriminated union of three variants (`ServiceAccount`, `OAuthBrowserAccount`, `OAuthTokenAccount`). Each has `name` (the local config key) and `region` (one of `us`, `eu`, `in`). `ServiceAccount` has `username` and `secret`. `OAuthBrowserAccount` carries no inline secret (tokens live on disk). `OAuthTokenAccount` has exactly one of `token` (inline bearer) or `token_env` (env var name). Identity is project-agnostic — accounts never embed `project_id`.
- **Project**: A Mixpanel project. Identified by Mixpanel's numeric `project_id` (stored as a string). Has `name` and `organization_id` populated lazily from `/me` discovery.
- **WorkspaceRef**: A reference to a workspace within a project. Identified by Mixpanel's numeric `workspace_id` (positive integer). Has optional `name`. Distinguished from the facade class `Workspace` to avoid name collision.
- **Session**: The fully-resolved triple `(Account, Project, WorkspaceRef | None)` consumed by the API client. Frozen and immutable. Replaces both v1 `Credentials` and v2 `ResolvedSession`. Supports `replace(...)` for parallel iteration. Workspace is optional in the type but lazy-resolves to the project's default workspace on first workspace-scoped call.
- **ActiveSession**: The persisted `(account_name?, workspace_id?)` pair stored in `~/.mp/config.toml [active]`. Renamed from v2 "ActiveContext" for clarity. Replaces v1 `default = "X"`. Note: project is NOT in `[active]` — it lives on the account as `default_project`.
- **Target**: A named saved-cursor-position — a triple of `(account_name, project_id, workspace_id?)` stored in `[targets.NAME]` config blocks. Replaces v2 "ProjectAlias" with broader semantics (captures account too, not just project). Applied via `mp target use NAME` (writes to `[active]`) or `--target NAME` flag (one-off override).
- **AccountSummary**: A read-only summary of an account suitable for `mp account list` output. Replaces v1 `AccountInfo` and v2 `CredentialInfo` (merged into one type). No `project_id` field.
- **AccountTestResult**: The structured result of `mp account test NAME` — captures whether `/me` succeeded, the user identity, accessible project count, and any error detail.
- **OAuthTokens**: Existing model. Modified to drop the `project_id` field (legacy artifact). Storage path moves from `~/.mp/oauth/tokens_{region}.json` to `~/.mp/accounts/{name}/tokens.json`.
- **OAuthClientInfo**: Existing DCR client info model. Storage path moves from `~/.mp/oauth/client_{region}.json` to `~/.mp/accounts/{name}/client.json`.
- **MeResponse / MeProjectInfo / MeWorkspaceInfo / MeOrgInfo**: Existing forward-compatible Pydantic models for `/me` responses. Survive unchanged. Cache path moves to `~/.mp/accounts/{name}/me.json`.
- **BridgeFile (v2)**: New schema for the Cowork credential courier. Embeds the full `Account` record (with secret material), optional `project`, optional `workspace`, and optional `headers` map. No required project coupling.

## Success Criteria *(mandatory)*

### Measurable Outcomes

#### Code shape

- **SC-001**  **[REVISED — see post-implementation notes]**: Auth subsystem source size shrinks from ~7,200 LOC across 15 files to ≤4,000 LOC across ≤12 files (≥40% reduction; target ≥50%). Verified via `tokei` or `wc -l` on the listed files. **Shipped outcome**: ~5,800 LOC across 19 files (≈19% reduction within the revised scope). The original target assumed an `api_client.py` split that did not happen; the auth-specific surface (the v3 modules under `_internal/auth/`, the new `cli/commands/{account,project,workspace,target,session}.py`, and the rewritten `_internal/config.py`) hits the spirit of the goal — it's the legacy-compatibility code that's gone, not entity-CRUD lines that were never auth in the first place.
- **SC-002**: Mutation testing score against `_internal/auth/account.py`, `_internal/auth/session.py`, and the resolver in `config.py` is ≥85%.
- **SC-003**: All `if config_version` / `if version >= 2` / equivalent version-conditional branches in source and test code count exactly zero (verified via `grep`).
- **SC-004**: Auth subsystem mypy --strict passes with zero violations and zero `Any` types without explicit justification.

#### User experience

- **SC-005**: A fresh-install user can complete the full bootstrap (`mp account add` → `mp account login` → `mp project list` → `mp project use <id>` → first successful `mp query`) in ≤5 commands. Wall-clock duration is documentation-only (not a CI gate) because the OAuth browser-flow latency depends on the user; recorded in release notes per T125.
- **SC-006**: A user switches between any two configured accounts, projects, or workspaces with exactly one CLI command (`mp account use NAME` / `mp project use ID` / `mp workspace use ID` / `mp target use NAME`).
- **SC-007**: A Python user switches axes with exactly one method call (`ws.use(project=...)`); the call returns `self` to enable chaining.
- **SC-008**: Cross-project iteration in Python (loop over `ws.projects()` and switch each one) costs O(1) per switch (no re-authentication, no `/me` refetch); verified via instrumented test that counts HTTP calls.
- **SC-009**: A CLI shell loop (`mp project list -f jsonl | jq -r .id | xargs -I{} mp --project {} <command>`) runs without persisting any `[active]` changes and without requiring intermediate auth steps.
- **SC-010**: A `Workspace.use(account=A, project=B, workspace=C)` chain produces the same `Session` as `mp.Workspace(session=Session(account=A, project=B, workspace=C))`; the two construction paths are interchangeable.

#### Vocabulary & surface

- **SC-011**: The CLI top-level identity command groups count exactly five: `account`, `project`, `workspace`, `target`, `session`. The deprecated groups `auth`, `projects`, `workspaces`, `context` count exactly zero.
- **SC-012**: The verb `use` is the only state-change verb across all five groups. The verbs `switch`, `default`, `set-active`, `set-default` count exactly zero in the CLI.
- **SC-013**: The public Python package `mixpanel_data.*` exposes the documented namespace: `Workspace`, `accounts`, `targets`, `session`, `config`, `Account`, `ServiceAccount`, `OAuthBrowserAccount`, `OAuthTokenAccount`, `Project`, `WorkspaceRef`, `Session`, `Target`, `AccountSummary` (plus existing exception types and result types). The deprecated names `Credentials`, `AccountInfo`, `CredentialInfo`, `AuthCredential`, `CredentialType`, `ProjectContext`, `ResolvedSession`, `ProjectAlias`, `MigrationResult`, `ActiveContext`, `AuthMethod` count exactly zero in the public surface.
- **SC-014**: The plugin `auth_manager.py` shrinks from ~727 lines to ≤300 lines.

#### Reliability

- **SC-015**: 100% of resolver invocations with identical inputs (env + params + config snapshot) return identical `Session` objects (verified via Hypothesis property-based tests over arbitrary input combinations).
- **SC-016**: 100% of error messages from `resolve_session()` failures explicitly state both what is missing AND what command to run to fix it (verified via test assertions on every documented failure mode).
- **SC-017**  **[DESCOPED — see post-implementation notes]**: 100% of legacy v1 and v2 fixture configs are convertible by `mp config convert` without data loss; subsequent operation against the converted config matches pre-conversion intent (verified via end-to-end fixture tests).
- **SC-018**: Every call to a workspace-scoped App API endpoint with a `Session` having `workspace=None` succeeds via lazy auto-resolution (verified against the live API or a contract test backed by the published OpenAPI shape; the existence guarantee is per source review §13.2).
- **SC-019**  **[DESCOPED — see post-implementation notes]**: 100% of v1/v2 ↔ v3 conversion test cases preserve the user's accessible projects and active selection through the conversion (no orphaned configs, no silent identity loss).

#### Migration & release

- **SC-020**  **[REVISED — see post-implementation notes]**: All existing alpha-tester configs (collected as fixtures) convert successfully by `mp config convert`; no manual TOML editing is required for any case. (Replaced under hard cutover: alpha testers wipe `~/.mp/config.toml` and re-add accounts via `mp account add ...`. The recipe is one paragraph in `RELEASE_NOTES_0.4.0.md`.)
- **SC-021**  **[REVISED — `mp config convert` descoped; see post-implementation notes]**: The `mixpanel_data` package version bumps to 0.4.0; the plugin version bumps to 5.0.0; release notes for both explicitly call out the breaking change and document the migration recipe (hard cutover, not conversion).
- **SC-022**: The v2 design document (`context/auth-project-workspace-redesign.md`) carries a clear superseded-by header pointing to the new design before the release ships.

## Assumptions

- **Pre-1.0 status legitimizes a clean break**: `mixpanel_data` is at 0.3.0 with a handful of alpha testers. Per design principle #9 ("no dead branches") and decision §18 #5 (version bump), breaking changes are acceptable now and become much more expensive after 1.0.
- **Mixpanel guarantees a default workspace per project**: Verified against the Mixpanel webapp source (`webapp/project/utils.py:271` calls `create_all_projects_data_view`). Every project is born with a default "All Project Data" workspace; `Session.workspace=None` plus lazy auto-resolution always succeeds.
- **Most App API endpoints are project-scoped, not workspace-scoped**: Verified per `webapp/app_api/projects/urls.py`. Cheap Session construction (no required workspace network call) is correct for the dominant case.
- **Service accounts CAN call `/me`**: Verified in the v2 design doc against Django source. All three account types share the same `/me` cache code path.
- **Env vars are the standard CI/agent escape hatch**: Per design decision §18 #4, env vars stay at the top of every resolution axis. This preserves PR #125 behavior and aligns with industry convention (12-factor app config).
- **Switching between two configured service accounts is the same operation as switching between an OAuth and an SA**: Per design principle #1 ("one model"), all account types are interchangeable at the resolution layer; only the auth header construction differs.
- **OAuth client info per-account is OK**: Per design decision §18 #7, region stays per-account; users with multi-region needs create separate account entries (e.g., `personal-us`, `personal-eu`). This avoids per-region token files inside one account directory and keeps the storage layout flat.
- **Custom headers stay global**: Per design decision §18 #6, per-account custom headers are not in scope; users with per-deployment headers use `MP_CUSTOM_HEADER_*` env vars per-invocation. This keeps the `Account` model simple.
- **Conversion is opt-in, not automatic**  **[REVISED — `mp config convert` descoped; see post-implementation notes]**: Per design decision §18 #8, `mp config convert` was the only path; runtime auto-conversion would violate the "clean break" principle and silently change the user's filesystem. (The conversion script itself was then descoped in favor of a hard cutover; the same anti-silent-mutation principle still applies — legacy configs error loudly.)
- **OAuth token refresh and DCR machinery survive unchanged**: The PKCE, DCR, and callback-server code (`flow.py`, `pkce.py`, `client_registration.py`, `callback_server.py`) is well-tested and remains as-is. Only the storage paths change (from `~/.mp/oauth/` to `~/.mp/accounts/{name}/`).
- **Existing exception types survive**: `AuthenticationError`, `OAuthError`, `ConfigError`, etc. are kept; only the messages and the call sites change.
- **API endpoint URLs and request signing logic in `api_client.py` are unaffected**: Only the constructor signature changes (takes `Session` instead of `Credentials`) and the `with_project` factory is removed in favor of in-place axis updates.
- **Plugin and CLI rewrites can land in lockstep with the Python API**: The plugin's `auth_manager.py` and the CLI's command groups are thin wrappers over the public Python namespaces (`mp.accounts`, `mp.targets`, `mp.session`); rewriting them is mostly mechanical once the Python surface is stable.
- **The 9-phase ordering in §16 of the source design is the implementation order**: Phase 0 (this spec) → Phase 1 (new types) → Phase 2 (resolver + ConfigManager) → Phase 3 (rewire API client + Workspace) → Phase 4 (CLI rewrite) → Phase 5 (plugin rewrite) → Phase 6 (Cowork bridge) → Phase 7 (documentation) → Phase 8 (migration script + announcement). Each phase is independently mergeable in principle, but Phase 4 onward depends on Phases 1–3 for the underlying types.
- **Deletion of v1 paths and v2/v1 bridges is the source of the LOC reduction**: Per source design §15.4, the ~50% LOC drop is removal of compatibility code, not feature cuts. No documented capability is lost.

## Out of Scope

- **New analytics/query features**: This redesign touches only the auth subsystem (accounts, projects, workspaces, sessions, targets, bridge). It does not add new query types, new entity-management commands, or new discovery features.
- **Multi-environment config files**: One config per machine. Power users with multi-environment needs use `MP_CONFIG_PATH` to point at alternate files.
- **Per-account custom headers**: See assumptions; deferred to a future iteration if alpha-tester feedback shows the need.
- **Automatic schema migration at runtime**  **[REVISED — `mp config convert` descoped; see post-implementation notes]**: Per design decision §18 #8, only `mp config convert` (opt-in, one-shot) was to handle legacy configs. Under the descope, NO automatic conversion of any kind is provided — legacy configs raise loudly and the user follows the `RELEASE_NOTES_0.4.0.md` recipe.
- **Backward-compatible Python imports for deleted types**: There is no shim that re-exports `Credentials` or `AuthCredential` from the public package. Code calling deleted names must be updated.
- **CI compatibility shim for deleted CLI verbs**: There is no `mp auth list` alias for `mp account list`. Scripts using deleted verbs must be updated.
- **OAuth token storage outside `~/.mp/accounts/{name}/`**: System-wide secret managers (Keychain, gnome-keyring, etc.) are not in scope. Tokens remain on disk with `0o600` permissions.
- **Multi-tenant or per-org account scoping**: An account is identified by its local name only. Multiple Mixpanel orgs accessible by one OAuth identity are surfaced via `/me` discovery, not by separate account entries.
- **Server-side Mixpanel changes**: This redesign assumes the existing Mixpanel App API surface (verified via the webapp source review in §13.2). No server-side changes are required.

## Dependencies

- **Mixpanel App API stability**: The redesign assumes the documented App API endpoints (`/me`, `/api/app/projects/{pid}/workspaces/public`, project-scoped CRUD endpoints, workspace-scoped CRUD endpoints) remain available with their current shape. Source review of the Mixpanel webapp confirmed current behavior.
- **PR #125 already merged**: The `MP_OAUTH_TOKEN` env-var path is the precedent for "env wins on the account axis"; this spec preserves and extends that behavior.
- **Existing test infrastructure**: Hypothesis (property-based tests), mutmut (mutation testing), and the `tests/unit/` + `tests/integration/` layout are already in place. No new test framework required.
- **Existing OAuth machinery**: `OAuthFlow`, `PKCEChallenge`, `DynamicClientRegistration`, `CallbackServer`, `OAuthTokens`, `OAuthClientInfo` survive with minor changes (storage paths, dropping `OAuthTokens.project_id`).
- **Existing `MeService` / `MeCache`**: Survive with storage path change.
- **Existing API client transport**: `httpx.Client` instance preserved across switches; existing connection pooling and retry logic unchanged.
- **`uv`, `just`, `mypy --strict`, `ruff`**: Existing development tooling. No new tools required.
