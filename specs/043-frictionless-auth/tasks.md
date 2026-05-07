---
description: "Task list for 043-frictionless-auth — single PR landing AIE-114/115/116/117 together"
---

# Tasks: Frictionless Auth (`mp login` and `/me`-driven discovery)

**Input**: Design documents from `/specs/043-frictionless-auth/`
**Prerequisites**: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md), [data-model.md](data-model.md), [contracts/](contracts/), [quickstart.md](quickstart.md)

**Tests**: REQUIRED. The project CLAUDE.md mandates strict TDD ("write tests FIRST, before any implementation code"), 90% coverage minimum, and ≥80% mutation score on the two new pure modules (`region_probe.py`, `naming.py`). Test tasks land before their corresponding implementation tasks within each phase.

**Organization**: Tasks are grouped by user story. The single-PR strategy means stories ship together, but each story is internally complete and independently verifiable as its commit lands. Phase order follows the plan's commit sequence: US3 (AIE-115) → US2 (AIE-114) → US4 (AIE-116) → US1 (AIE-117).

**Story dependency note**: US1 (the `mp login` umbrella) DEPENDS on the helpers introduced by US2 (region probe), US3 (SA project discovery) and US4 (naming). The dependency is inherent to the design — `mp login` composes the three helpers. Stories US2/US3/US4 are independent of each other and of US1.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: User story this task belongs to (US1 / US2 / US3 / US4) — omitted for Setup, Foundational, and Polish phases
- All file paths are project-relative

## Path Conventions

Single project (Library + CLI):
- Source: `src/mixpanel_headless/`
- Tests: `tests/unit/`, `tests/pbt/`, `tests/integration/`
- Specs: `specs/043-frictionless-auth/`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Verify the dev environment is ready. This phase is intentionally minimal — the existing 042 architecture provides all needed scaffolding.

- [ ] T001 Run `just install-hooks` from the repo root to ensure the pre-commit hook is installed (per project CLAUDE.md "First-time setup after cloning"). No-op if already installed.
- [ ] T002 [P] Run `just check` against `main` to establish a clean baseline (verifies starting state passes lint + format + typecheck + tests + build before any new work lands).

**Checkpoint**: Dev environment ready, baseline clean. Proceed to Foundational.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Add the one new exception type that US2 needs. Re-export from the package root so it appears in the public surface alongside `OAuthError`.

**⚠️ CRITICAL**: T003–T004 MUST land before US2's implementation tasks (the region probe raises this exception).

- [ ] T003 Add `RegionProbeError(OAuthError)` to `src/mixpanel_headless/exceptions.py` per [contracts/python-api.md](contracts/python-api.md) §5. Carries an `attempts: list[tuple[Region, int, str]]` field. Override `to_dict()` to include `attempts` so JSON-formatted error output preserves diagnostic detail. Full Google-style docstring per project standards.
- [ ] T004 [P] Re-export `RegionProbeError` from `src/mixpanel_headless/__init__.py` (alongside the existing `OAuthError` export). Update the `__all__` list.

**Checkpoint**: Foundational exception type available. User stories can begin in commit order.

---

## Phase 3: User Story 3 — Service-account project discovery without `--project` (Priority: P2, Commit 1, AIE-115)

**Goal**: Make `mp account add` accept service-account credentials without `--project`, and surface the explicit `user_details` scope name when `/me` returns 403.

**Independent Test**: With a service account that has the `user_details` scope and access to ≥2 projects, run `mp account add my-sa --type service_account --username U --secret-stdin --region us` (no `--project`). Confirm the account is created with no `default_project`. Then run `mp project list --account my-sa` and confirm all accessible projects are returned.

### Tests for User Story 3 (write FIRST, ensure they FAIL before implementation)

- [ ] T005 [P] [US3] Add unit test cases to `tests/unit/test_accounts_namespace.py`: `accounts.add()` with `type="service_account"` and `default_project=None` succeeds and produces an `AccountSummary` with `default_project is None`; same for `type="oauth_token"`.
- [ ] T006 [P] [US3] Add CLI snapshot test cases to `tests/unit/cli/test_cli.py` (or create `tests/unit/cli/test_account_cli.py` if no account-CLI suite exists yet — check first): `mp account add my-sa --type service_account --username U --secret-stdin --region us` (no `--project`) exits 0; resulting `mp account show my-sa` reports no default project.
- [ ] T007 [P] [US3] Add CLI test case to the same file as T006: `mp account add` `--help` output includes the new "TIP: For new setups, prefer `mp login`" epilog (cli-commands.md §2.2).
- [ ] T008 [P] [US3] Add unit test to the file containing existing `MeService` 403 → `ConfigError` mapping coverage (search `tests/` for `lacks /me permission`): with the new scope-hint message, the exception's user-facing string matches error catalog [E-10](contracts/error-messages.md#e-10-service-account-missing-user_details-scope) verbatim. Asserts the literal text including `user_details` and the Mixpanel Settings reference.
- [ ] T009 [P] [US3] Add CLI test case to T006's file: `mp project list --account limited-sa` (with a fixture SA whose `/me` returns 403) prints E-10's stderr exactly and exits 1.

### Implementation for User Story 3

- [ ] T010 [US3] Modify `src/mixpanel_headless/accounts.py::add()`: change `default_project` validation so it is no longer required for `type="service_account"` and `type="oauth_token"`. Preserve the existing required-for-`oauth_browser`-with-no-login-yet behavior. Update the docstring to reflect the relaxation.
- [ ] T011 [US3] Modify `src/mixpanel_headless/cli/commands/account.py::add` Typer command: drop the per-type required validation that forces `--project` for SA / oauth_token. Update `--help` text for `--project` to read "Project ID (optional; can be set later via `mp project use ID`)".
- [ ] T012 [US3] Modify the 403 error mapping in the SA `/me` callsite (likely `src/mixpanel_headless/_internal/me.py::MeService.fetch` or wherever the existing `ConfigError("...lacks /me permission")` is raised): rewrite the message to match error catalog [E-10](contracts/error-messages.md#e-10-service-account-missing-user_details-scope) verbatim, including the `user_details` scope name and the Settings → Service Accounts reference.
- [ ] T013 [US3] Add the "TIP: For new setups, prefer `mp login`" epilog to the `mp account add` Typer command's `--help` (`src/mixpanel_headless/cli/commands/account.py`).

### Verify User Story 3

- [ ] T014 [US3] Run `just check` from repo root. Confirm: every test added in T005–T009 passes, mypy `--strict` passes, ruff lint + format passes, coverage stays ≥90%.

**Checkpoint**: SA without `--project` works end-to-end. `mp project list` against an SA without configured project ID returns the project list. Scope-hint message lands. Commit 1 lands as a discrete git commit.

---

## Phase 4: User Story 2 — Region auto-detection for service-account and token credentials (Priority: P2, Commit 2, AIE-114)

**Goal**: When `--region` is omitted from `mp account add` for SA / oauth_token, probe `us → eu → in` against `/me` and persist the resolved region. For oauth_browser, detect region mismatch between `--region` and the picked project's `domain`.

**Independent Test**: Configure a service account with valid `MP_USERNAME`/`MP_SECRET` for an EU project. Run `mp account add my-eu-sa --type service_account --username U --secret-stdin` (no `--region`). Confirm the resulting account record has `region = eu` and `mp project list --account my-eu-sa` succeeds.

### Tests for User Story 2 (write FIRST)

- [ ] T015 [P] [US2] Create `tests/unit/test_region_probe.py` with cases: probe US succeeds first → returns `RegionProbeResult(region="us", attempts=[("us", 200)])` and never hits EU/IN; probe US 401 + EU 200 → `RegionProbeResult(region="eu", attempts=[("us", 401), ("eu", 200)])` and never hits IN; probe US 401 + EU 401 + IN 200 → `region="in"`; all three 401 → raises `RegionProbeError` with full attempts list; httpx network error rendered as status code `0` in attempts; respects custom `order=("eu", "us")` parameter; respects `timeout_seconds` parameter (mock httpx.Client to assert timeout passed through). Each test uses an httpx mock transport — no real network I/O.
- [ ] T016 [P] [US2] Add CLI snapshot test cases to T006's file: `mp account add my-sa --type service_account --username U --secret-stdin` (no `--region`) probes and persists resolved region; explicit `--region us` skips the probe (mock asserts no probe call); probe failure surfaces error catalog [E-1](contracts/error-messages.md#e-1-region-probe--all-regions-failed) verbatim and exits 2.
- [ ] T017 [P] [US2] Add unit test to `tests/unit/test_accounts_namespace.py`: re-running `accounts.add(name="x", type="service_account", region=None, ...)` with the same name as an existing account does NOT re-probe (uses cached region from the first add).
- [ ] T018 [P] [US2] Add unit test for browser-region-mismatch detection (a new test file `tests/unit/test_login_region_check.py` or extension of existing `test_workspace_oauth.py` if it exists): when `accounts.login()` (oauth_browser) commits region=`us` and the picked project's `MeProjectInfo.domain` is `eu.mixpanel.com`, raises `ConfigError` with message matching error catalog [E-2](contracts/error-messages.md#e-2-region-mismatch-browser-auth-picked-projects-region-differs-from-auth-region) verbatim. Cleans up the placeholder dir before raising.

### Implementation for User Story 2

- [ ] T019 [US2] Create `src/mixpanel_headless/_internal/auth/region_probe.py` per [contracts/python-api.md](contracts/python-api.md) §2.1. Functions: `probe_region(client_factory, headers, *, timeout_seconds=5.0, order=("us","eu","in")) -> RegionProbeResult`. Implementation walks the `order` tuple, calls `client_factory(region).get("/api/app/me", headers=headers, timeout=timeout_seconds)` for each, returns `RegionProbeResult` on first 200, raises `RegionProbeError` (from `mixpanel_headless.exceptions`) when none succeed. Network errors recorded as status `0`. Pure-functional: no `os.environ`, no logging, no `print`. Full Google-style docstrings on the module, the `RegionProbeResult` dataclass, and the `probe_region` function.
- [ ] T020 [US2] Modify `src/mixpanel_headless/cli/commands/account.py::add`: make `--region` optional for `service_account` and `oauth_token` types. When omitted, build the credential headers (Basic for SA, Bearer for token), then call `region_probe.probe_region` with a `client_factory` that constructs a regional `httpx.Client` from the existing region → base-URL mapping. Print one stderr line per probe attempt (`Probing region X ... ✓` or `... ✗ (NNN Reason)`). Persist resolved region via the existing `accounts.add()` call.
- [ ] T021 [US2] Modify `src/mixpanel_headless/accounts.py::add()`: when `type` is `service_account` or `oauth_token` and `region` is `None`, raise an informative `ConfigError` directing the caller to either supply `region` or use `mp login` (per the source design's "we don't probe inside `add` — that's `login`'s job" decision). The probing logic stays in the CLI layer where the stderr progress lines are appropriate; the Python API stays pure (no stderr writes from a library call).
- [ ] T022 [US2] Modify `src/mixpanel_headless/accounts.py::login()` (the existing oauth_browser refresh path): after PKCE completes and `MeService.fetch()` returns, look up the picked project's `domain` in `MeResponse.projects`. Map domain → region via the table in spec.md §"What `/me` actually returns". If the resolved project region differs from the committed auth region, clean up the placeholder dir (if one exists from `login_unified`'s atomic-publish flow) and raise `ConfigError` with message matching [E-2](contracts/error-messages.md#e-2-region-mismatch-browser-auth-picked-projects-region-differs-from-auth-region) verbatim.

### Verify User Story 2

- [ ] T023 [US2] Run `just check` and confirm all gates pass.
- [ ] T024 [US2] Run `just mutate -- --paths-to-mutate src/mixpanel_headless/_internal/auth/region_probe.py` and confirm mutation score ≥ 80% (per project CLAUDE.md mutation testing requirement). Inspect any survived mutants and either tighten tests or document with `# pragma: no mutate` and a justification comment.

**Checkpoint**: Region probe lands; SA / oauth_token can be added without `--region`; browser auth detects region mismatch with actionable error. Commit 2 lands.

---

## Phase 5: User Story 4 — Auto-derived account names (Priority: P3, Commit 3, AIE-116)

**Goal**: When the user does not supply a positional `NAME` to `mp account add` (or `--name` to `mp login`), derive a default from the first org returned by `/me`, slugified and collision-suffixed.

**Independent Test**: On a fresh config, run `mp account add --type oauth_browser --region us` (no positional name) against an account belonging to an org named "Acme Corp". Confirm the configured account name is `acme-corp`. Run again against a different account from a separate org also named "Acme Corp" and confirm the second account is named `acme-corp-2`.

### Tests for User Story 4 (write FIRST)

- [ ] T025 [P] [US4] Create `tests/unit/test_naming.py` with example-based tests covering the spec FR-015 input/output table verbatim: `slugify("Acme Corp") == "acme-corp"`; `slugify("ACME, Inc.") == "acme-inc"`; `slugify("Café Industries") == "cafe-industries"`; `slugify("  Acme  &  Sons ") == "acme-sons"`; `slugify("1Password") == "1password"`; `slugify("---") == ""`; 50-char input truncates to 32 chars with trailing `-` stripped. Plus FR-016 collision suffix table: `default_account_name(me_with_acme_org, set()) == "acme-corp"`; `default_account_name(me_with_acme_org, {"acme-corp"}) == "acme-corp-2"`; `default_account_name(me_with_acme_org, {"acme-corp", "acme-corp-2"}) == "acme-corp-3"`; empty-org-name fallback to `org-{org_id}`; empty-organizations dict fallback to `"account"`.
- [ ] T026 [P] [US4] Create `tests/pbt/test_naming_pbt.py` with Hypothesis property tests: `slugify` is idempotent (`slugify(slugify(x)) == slugify(x)` for all `x`); slugify output, when non-empty, matches `^[a-z0-9-]{1,32}$`; `default_account_name(me, existing)` always returns a string not in `existing`; collision suffix is monotonically increasing (the `-N` numbers appear in order, no gaps, never `-1`); `default_account_name` is deterministic (calling twice with the same inputs returns the same name). Use the project's existing Hypothesis profiles (`default`/`dev`/`ci`).
- [ ] T027 [P] [US4] Add CLI snapshot test cases to T006's file: `mp account add --type oauth_browser --region us` (no positional name) against a fixture `/me` with org "Acme Corp" produces account `acme-corp`; running the same command twice (against two different OAuth flows for two different orgs both named "Acme Corp") produces `acme-corp` and `acme-corp-2`; multi-org non-TTY context fails with error catalog [E-9](contracts/error-messages.md#e-9-non-interactive-context-multi-org-no---name) and exits 3; `--name foo` overrides derivation regardless of org count.

### Implementation for User Story 4

- [ ] T028 [US4] Create `src/mixpanel_headless/_internal/auth/naming.py` per [contracts/python-api.md](contracts/python-api.md) §2.2. Functions: `slugify(value: str | None) -> str` implementing the 6-step normalization (NFKD-normalize, ASCII-fold, lowercase, replace non-`[a-z0-9]` runs with `-`, strip leading/trailing `-`, truncate to 32 chars + strip trailing `-`); `default_account_name(me: MeResponse, existing: set[str]) -> str` picking the first org from `me.organizations`, slugifying its name, falling back to `org-{org_id}` when the slug is empty, falling back to `"account"` when `me.organizations` is empty, applying `-2`/`-3`/... collision suffix from `existing`. Module-level constant `_SLUG_MAX_LEN = 32`. Pure-functional: no `os.environ`, no `random`, no clock reads. Full docstrings per project standards (Google style, with usage examples in markdown code fences per project CLAUDE.md "Documentation (STRICT)").
- [ ] T029 [US4] Modify `src/mixpanel_headless/cli/commands/account.py::add`: make positional `NAME` optional. When omitted, after the credential is collected and `/me` returns, compute `default_account_name(me, existing=ConfigManager().list_accounts_names())`. For multi-org users in TTY context, prompt for org selection (renders the list per cli-commands.md §1.6.2). For multi-org users in non-TTY context, fail with [E-9](contracts/error-messages.md#e-9-non-interactive-context-multi-org-no---name) and exit 3.
- [ ] T030 [US4] Add `derive_name: bool = False` keyword-only parameter to `src/mixpanel_headless/accounts.py::add()` so the Python API path can opt into derived naming without going through the CLI. When `derive_name=True` and `name` is `None`, calls `naming.default_account_name` against the just-fetched `/me`. When `derive_name=True` and `name` is supplied, raises `TypeError` (mutually exclusive). Update the docstring with a "Derived naming" section.

### Verify User Story 4

- [ ] T031 [US4] Run `just check` and `just test-pbt` (with `HYPOTHESIS_PROFILE=default`) and confirm all gates pass.
- [ ] T032 [US4] Run `just mutate -- --paths-to-mutate src/mixpanel_headless/_internal/auth/naming.py` and confirm mutation score ≥ 80%. Inspect survivors.

**Checkpoint**: Naming utility lands; `mp account add` accepts derived NAME. Commit 3 lands.

---

## Phase 6: User Story 1 — One-command browser login for first-time users (Priority: P1, Commit 4, AIE-117 umbrella) 🎯 MVP

**Goal**: Land `mp login` as the conversational entry point that composes all the helpers from US2/US3/US4. A new user can type `mp login` and end up with a working account.

**Independent Test**: On a machine with no `~/.mp/` directory, run `mp login`, complete OAuth in the browser, and confirm a subsequent `mp query segmentation -e Login --from 2025-01-01` succeeds without further configuration.

### Tests for User Story 1 (write FIRST)

- [ ] T033 [P] [US1] Create `tests/unit/cli/test_login_cli.py` covering all 17 scenarios from [contracts/cli-commands.md](contracts/cli-commands.md) §6 (snapshot test coverage matrix): browser-happy-single-project, browser-multi-project-prompt, browser-non-tty-no-project, browser-explicit-project, browser-project-not-visible, browser-region-mismatch, sa-probe-us-success, sa-probe-eu-success, sa-probe-all-fail, sa-403-scope-hint, relogin-browser-preserves-project, relogin-with-project-emits-warning, relogin-region-change-refused, explicit-name-wins, collision-suffix, mp-project-id-stale-warning, mutually-exclusive-flags. Each test asserts (a) exit code, (b) stdout content, (c) stderr content, (d) resulting `~/.mp/config.toml` state and `~/.mp/accounts/{name}/` filesystem state.
- [ ] T034 [P] [US1] Create `tests/integration/test_login_e2e.py` exercising the full `accounts.login_unified()` flow against an httpx mock transport for each auth type. For oauth_browser: simulate the full PKCE flow (mock authorize URL, mock callback POST, mock /me) and verify the placeholder dir lifecycle (created → tokens written → renamed to `acme-corp/` → final state). For service_account: verify the probe sequence and the eventual atomic write. For oauth_token: verify the env-var read. Each test asserts that on failure the placeholder dir is cleaned up (no orphans under `~/.mp/accounts/.tmp-*/`).
- [ ] T035 [P] [US1] Add unit test to T034's file (or a separate `tests/unit/test_login_unified.py`): re-login state-transition table from [data-model.md](data-model.md) §4 — verify each row's expected behavior with mocked `ConfigManager` and `MeService`.

### Implementation for User Story 1

- [ ] T036 [US1] Add `accounts.login_unified(*, name=None, region=None, project=None, account_type=None, no_browser=False, secret_stdin=False, token_env=None) -> AccountSummary` to `src/mixpanel_headless/accounts.py` per [contracts/python-api.md](contracts/python-api.md) §1. Function body orchestrates: auth-type detection (priority chain from §1) → credential collection → region resolution (probe or commit per type) → PKCE for oauth_browser / probe-then-fetch for SA-token → `/me` lookup → project selection (priority chain from §1) → name derivation (or use explicit `name`) → re-login branch detection → persist via existing `accounts.add()`. Full docstring covering all parameters, returns, raises, and side effects per the contract.
- [ ] T037 [US1] Implement the placeholder-then-rename atomic publish pattern within `login_unified()` for the oauth_browser path per [data-model.md](data-model.md) §5. Helper: `_create_placeholder_account_dir() -> Path` returns `~/.mp/accounts/.tmp-{secrets.token_hex(4)}/`. After `/me` and naming resolve, atomic `os.rename` to the final `~/.mp/accounts/{final_name}/`. On any failure between placeholder creation and rename, remove the placeholder dir. On rename failure (EEXIST, EACCES), leave the placeholder for manual recovery and raise with the placeholder path in the error message.
- [ ] T038 [US1] Implement the project-selection priority chain in `login_unified()` per spec FR-010 and [data-model.md](data-model.md) §3: (1) `project` parameter → must exist in `me.projects`, else raise `ConfigError` per [E-6](contracts/error-messages.md#e-6-project-not-visible---project-flag); (2) `MP_PROJECT_ID` env → must exist or warn-and-fall-through per [E-7](contracts/error-messages.md#e-7-mp_project_id-stale-informational-not-an-error); (3) single project → auto-pick; (4) multiple projects → caller-supplied picker callback (the CLI layer provides one; the library raises `ConfigError` per [E-8](contracts/error-messages.md#e-8-non-interactive-context-no-project-default) if no callback is supplied).
- [ ] T039 [US1] Implement the re-login branch in `login_unified()` per [data-model.md](data-model.md) §4. Detect by `final_name in ConfigManager().list_accounts_names()`. Refresh tokens (oauth_browser) or update credential fields (SA / token). Preserve `default_project`. Emit stderr note per [E-5](contracts/error-messages.md#e-5-re-login-project-change-ignored-informational-not-an-error) when `--project` or `MP_PROJECT_ID` is set on the re-login path. Refuse with [E-3](contracts/error-messages.md#e-3-re-login-refused-region-change) on region mismatch. Refuse with [E-4](contracts/error-messages.md#e-4-re-login-refused-auth-type-change) on auth-type mismatch.
- [ ] T040 [P] [US1] Re-export `login_unified` from `src/mixpanel_headless/__init__.py` (alongside the existing `accounts` module re-exports). Also re-export `RegionProbeError` if T004 didn't already (re-check).
- [ ] T041 [US1] Create `src/mixpanel_headless/cli/commands/login.py` Typer command per [contracts/cli-commands.md](contracts/cli-commands.md) §1. Flags: `--name`, `--region`, `--project`, `--service-account / -S`, `--token-env`, `--no-browser`, `--secret-stdin`. Apply `@handle_errors` decorator. Function body: validate mutually exclusive flags (per §5, raising `INVALID_ARGS=3` on violations) → call `accounts.login_unified()` with a project_picker callback that handles the TTY-aware prompt → format the success summary line and print to stdout. All progress, prompts, and notes go to stderr via the existing `err_console`.
- [ ] T042 [US1] Implement the TTY-gated project picker callback in `cli/commands/login.py` per [cli-commands.md](contracts/cli-commands.md) §1.6.1. Renders the numbered list to stderr, sorted alphabetically by project name within org (org context shown when `len(orgs) > 1`). Default `[1]`, three retries before raising `ConfigError` per [E-14](contracts/error-messages.md#e-14-project-picker--too-many-invalid-responses). On non-TTY context, raises `ConfigError` per [E-8](contracts/error-messages.md#e-8-non-interactive-context-no-project-default).
- [ ] T043 [US1] Implement the TTY-gated org picker callback in `cli/commands/login.py` per [cli-commands.md](contracts/cli-commands.md) §1.6.2. Same prompt-loop shape as the project picker but for org selection (used when `len(me.organizations) > 1` AND `--name` not supplied). Three retries, per [E-15](contracts/error-messages.md#e-15-org-picker--too-many-invalid-responses).
- [ ] T044 [US1] Implement argument validation in `cli/commands/login.py` per [cli-commands.md](contracts/cli-commands.md) §5: `--service-account` + `--token-env` mutually exclusive ([E-11](contracts/error-messages.md#e-11-mutually-exclusive-auth-type-flags)); `--no-browser` only meaningful for oauth_browser ([E-12](contracts/error-messages.md#e-12---no-browser-with-non-browser-auth)); `--secret-stdin` only meaningful for service_account ([E-13](contracts/error-messages.md#e-13---secret-stdin-with-non-sa-auth)). All validation runs before any network I/O.
- [ ] T045 [US1] Register the `login` command in `src/mixpanel_headless/cli/main.py::_register_commands()` per [contracts/cli-commands.md](contracts/cli-commands.md) §4. Top-level command, `help="Add a Mixpanel account with guided region / project / name resolution."`.

### Verify User Story 1

- [ ] T046 [US1] Run `just check`. Confirm: every test from T033–T035 passes, mypy `--strict` passes, ruff lint + format passes, coverage stays ≥90%.
- [ ] T047 [US1] Manually exercise the `quickstart.md` scenarios 1.1, 1.2, 1.4, 4.1 against a real Mixpanel test account. Document any deviations from the contracted error / output strings.

**Checkpoint**: `mp login` ships. All four sibling Linear tickets land in this single PR. Stop here for the MVP smoke test before Polish.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Documentation, LoC budget verification, end-to-end smoke-test pass. These are NOT optional — the CI gates and the project's documentation discipline (per CLAUDE.md) require all of them before merge.

- [ ] T048 [P] Update top-level `CLAUDE.md`: add `mp login` to the env-vars / commands surface area; add a one-liner under "Recent Changes" or analogous section noting that `--region` and `NAME` are now optional for `mp account add`. Ensure the SPECKIT START/END markers added during planning still point at this plan.
- [ ] T049 [P] Update `src/mixpanel_headless/CLAUDE.md`: add `accounts.login_unified()` to the "Functional Namespaces" section. Add `RegionProbeError` to the Exception Hierarchy under `OAuthError`.
- [ ] T050 [P] Update `src/mixpanel_headless/cli/CLAUDE.md`: add `login` to the Command Groups table.
- [ ] T051 [P] Update `src/mixpanel_headless/cli/commands/CLAUDE.md`: add `login.py` row to the Files table with column entries `mp login` / "Guided account add (region probe, project picker, name derivation)".
- [ ] T052 Run `tests/unit/test_loc_budget.py` (via `pytest tests/unit/test_loc_budget.py -v`). Confirm the new file count and LoC totals stay under the existing ceiling (~6,500 LoC across ~20 files per project CLAUDE.md). If the +3 new files breach the file-count ceiling, bump the ceiling in the test with a comment citing this feature spec and the +3 file count.
- [ ] T053 [P] Run `quickstart.md` end-to-end smoke test (the "End-to-end smoke test (single command)" section) against a real Mixpanel test account. Capture the output for the PR description.
- [ ] T054 [P] Run `quickstart.md` backward-compat smoke test against an existing config that uses the legacy `mp account add NAME --type X --region Y --project Z` invocation form. Confirm no behavior change (per FR-023, FR-024, FR-025).
- [ ] T055 Run `just check` one more time as the final pre-PR gate. All checks must pass.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — can start immediately.
- **Foundational (Phase 2)**: Depends on Setup completion — BLOCKS US2 only (US3 and US4 do not need `RegionProbeError`). In practice, the small foundational phase lands first because it's trivial and helps the dependency tree.
- **US3 (Phase 3, Commit 1)**: Depends on Foundational. Independent of US2 / US4 / US1.
- **US2 (Phase 4, Commit 2)**: Depends on Foundational. Independent of US3 / US4. NOT depended on by US3 or US4.
- **US4 (Phase 5, Commit 3)**: Depends on Foundational. Independent of US2 / US3.
- **US1 (Phase 6, Commit 4) — UMBRELLA**: Depends on US2 + US3 + US4 (composes their helpers). The plan's commit order ensures US1 lands last so all helpers exist.
- **Polish (Phase 7)**: Depends on US1 + US2 + US3 + US4 all complete.

### Within Each User Story

- Tests MUST be written and FAIL before implementation (project CLAUDE.md "TDD Rules (Non-Negotiable)").
- For US2 and US4: pure module implementation lands before CLI wiring (smaller blast radius for review).
- For US1: `accounts.login_unified()` library implementation lands before `cli/commands/login.py` (Library-First per Constitution Principle I).
- Each story's verify step (`just check`, mutation testing) MUST pass before moving to the next phase.

### Parallel Opportunities

- All Setup tasks marked [P] can run in parallel (T002 only — T001 is one-shot).
- Within each story's test phase, all `[P]` test tasks can run in parallel (different files).
- Within US1's implementation: T040 (re-export) is `[P]` because it touches a different file than the rest. The other US1 implementation tasks share `accounts.py` and `cli/commands/login.py` so they MUST be sequential.
- Polish tasks T048–T051 are all `[P]` (different files).
- Polish tasks T053 and T054 are `[P]` (different smoke-test runs).

### Cross-story integration risks

- US3 and US4 both modify `cli/commands/account.py::add`. T011 (US3) and T029 (US4) edit the same Typer function. Either land US3 fully first, then US4 (matches the plan's commit order), or coordinate the merge carefully. The plan's serial commit order avoids the conflict.
- US3 and US4 both modify `accounts.py::add()`. T010 (US3) and T030 (US4) extend the same function. Same mitigation.

---

## Parallel Example: User Story 2

```bash
# Launch all US2 tests in parallel (different files):
Task: "T015 [P] [US2] Create tests/unit/test_region_probe.py with all probe-order cases"
Task: "T016 [P] [US2] Add CLI snapshot tests to tests/unit/cli/test_cli.py"
Task: "T017 [P] [US2] Add unit test to tests/unit/test_accounts_namespace.py"
Task: "T018 [P] [US2] Add unit test to tests/unit/test_login_region_check.py"

# After tests fail as expected, implement (mostly sequential — same files):
Task: "T019 [US2] Create src/mixpanel_headless/_internal/auth/region_probe.py"
Task: "T020 [US2] Modify src/mixpanel_headless/cli/commands/account.py::add for probe wiring"
Task: "T021 [US2] Modify src/mixpanel_headless/accounts.py::add() error message"
Task: "T022 [US2] Modify src/mixpanel_headless/accounts.py::login() for region mismatch"

# Final verify:
Task: "T023 [US2] just check"
Task: "T024 [US2] just mutate region_probe.py"
```

---

## Implementation Strategy

### Single-PR landing (the actual plan)

This is NOT a phased delivery. All four user stories ship in ONE PR. The phase structure above is the *internal commit order* within that PR, designed for reviewer ergonomics. Each commit lands on the feature branch with passing CI. The PR ships only after Commit 4 (US1) lands and Phase 7 polish completes.

1. Complete Phase 1 + Phase 2 (Setup + Foundational) — typically squashable into one preparatory commit.
2. Complete Phase 3 (US3) — squash into one commit titled `feat(accounts): make --project optional for service accounts`.
3. Complete Phase 4 (US2) — one commit titled `feat(auth): add region probe utility`.
4. Complete Phase 5 (US4) — one commit titled `feat(auth): add account name derivation from /me org`.
5. Complete Phase 6 (US1) — one commit titled `feat(cli): add 'mp login' guided account setup`.
6. Complete Phase 7 (Polish) — one commit titled `docs: update CLAUDE.md and verify LoC budget for 043`.
7. Open the PR, link the four Linear tickets, attach the smoke-test output from T053.

### Why not one PR per story?

The user explicitly directed this: "This will NOT be 4 PR's. It will be only 1 PR." Per [plan.md](plan.md) §"PR strategy", the four sibling Linear tickets ship together. The internal commit order preserves the source design's intended review ergonomics without splitting the work across PRs.

### Suggested MVP cut-off

If reviewer feedback forces a partial revert, the safe rollback boundary is between Commit 4 (US1) and Commits 1–3. The helper modules (US2 / US3 / US4) are independently valuable improvements to `mp account add`. If `mp login` itself must drop from this PR, leaving the three helper commits in place still meaningfully reduces friction for users running `mp account add`. The Linear tickets AIE-114, AIE-115, AIE-116 can be marked complete; AIE-117 stays open.

---

## Notes

- [P] tasks = different files, no dependencies on incomplete tasks in the same phase.
- [Story] label maps task to specific user story for traceability with the source design and Linear tickets.
- Each user story's verify step (`just check` + mutation testing where applicable) gates the next commit.
- The project's strict TDD requirement means tests MUST exist and fail before any T0NN-implementation task starts.
- Avoid: breaching mypy `--strict`, leaving `Any` types undocumented, emitting any output to stdout from library code (only the CLI layer writes to stdout), or modifying `_internal/auth/resolver.py` (the pure-functional resolver is invariant for this feature per FR-008).
