# Implementation Plan: Frictionless Auth (`mp login` and `/me`-driven discovery)

**Branch**: `043-frictionless-auth` | **Date**: 2026-05-06 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/043-frictionless-auth/spec.md`
**Source design**: [`context/frictionless-auth.md`](../../context/frictionless-auth.md)
**PR strategy**: **Single integrated PR** (per user instruction). The four sibling Linear tickets (AIE-114/115/116/117) ship together as one shippable unit. Internal commit order may still follow the source's 115→114→116→117 sequence for reviewer ergonomics, but each commit need not be independently mergeable.

## Summary

Land four discovery improvements as one coherent feature so a new user can type `mp login`, authenticate in the browser, and have a fully-configured account ready to query — no region, no project ID, no local alias typed by hand.

The work decomposes into three pure-functional helpers (`region_probe`, `naming`, project-selection logic) plus one new CLI orchestrator (`mp login`) that composes them with the existing PKCE flow, service-account credential collection, and `accounts.add()` Python API. Region detection probes `/me` across `us`/`eu`/`in` for service-account and token credentials (browser auth commits region before the redirect, then verifies via `/me`). Account names default to a slug of the org name with `-2`/`-3` collision suffixes. Project selection follows a strict priority chain (`--project` > `MP_PROJECT_ID` > single auto-pick > interactive prompt > non-interactive fail).

The pure-functional resolver in `_internal/auth/resolver.py` is untouched. All discovery work lives at *add-time* (inside `mp login` and the relaxed `mp account add`), never at *resolve-time*. The on-disk schema is unchanged: `region` stays a required field on `Account` records and existing `~/.mp/config.toml` files keep working without migration.

The single PR includes: three new modules (`_internal/auth/region_probe.py`, `_internal/auth/naming.py`, `cli/commands/login.py`), one new public Python entry point (`accounts.login_unified()`), targeted relaxations in `cli/commands/account.py` and `accounts.py::add`, the corresponding test suites (unit + property-based + CLI snapshot), and a documentation refresh. Estimated +400 LoC against the existing ~6,500 LoC budget across ~20 files.

## Technical Context

**Language/Version**: Python 3.10+ (mypy --strict compliant)
**Primary Dependencies**: httpx (HTTP client; reused for region probes), Pydantic v2 (validation; existing `MeResponse`/`MeProjectInfo`/`MeOrgInfo` accommodate the new fields without schema changes), Typer (CLI), Rich (interactive prompts via `Prompt.ask`), tomli/tomli_w (TOML read/write — unchanged), pytest + Hypothesis (slug PBT, name-collision PBT), mutmut (≥80% on the two new pure modules).
**Storage**:
- TOML config at `~/.mp/config.toml` — schema unchanged; `region` stays a required field on every account record.
- Per-account state at `~/.mp/accounts/{name}/` — `tokens.json`, `client.json`, `me.json` (all `0o600`; parent dir `0o700`). Layout from 042 redesign is preserved; no migration needed.
- New `mp login` flow writes to a temporary placeholder directory, then renames it to the resolved account name once `/me` returns and the slug is computed.
**Testing**: pytest (unit + integration), Hypothesis (slug determinism, NFKD round-trip safety, collision suffix monotonicity), mutmut (region_probe.py + naming.py), CLI snapshot tests (Typer + Rich for `mp login` happy path, multi-org prompt, multi-project prompt, error paths).
**Target Platform**: Cross-platform (macOS, Linux, Windows). Filesystem permissions enforced on POSIX as in 042; TTY detection via `sys.stdin.isatty()` for prompt vs. fail-fast routing.
**Project Type**: Library + CLI feature addition (no plugin changes — `mixpanel-plugin/` is unchanged because the plugin already calls into `mp.accounts` and the new `accounts.login_unified()` is additive).
**Performance Goals**:
- `mp login --service-account` cold path on EU data ≤ 3 round-trips (US probe fail, EU probe success, optional second `/me` for project list — typically the first `/me` already returns the project list, so 2 RTTs is the common case).
- `mp login` browser flow CLI work ≤ 3 s after the OAuth callback fires (per SC-002).
- `mp login` re-login on existing account (refresh path) ≤ 1 RTT (token refresh, no probe).
- Slug computation (`naming.slugify`, `naming.default_account_name`) ≤ 1 ms for any input under 1 KB.
**Constraints**:
- mypy --strict compliance, zero `Any` types lacking explicit justification.
- ruff format/check passes with zero violations.
- 90% test coverage minimum (CI fails below).
- ≥80% mutation score on `_internal/auth/region_probe.py` and `_internal/auth/naming.py` (the two new pure modules).
- LoC budget: estimated +400 LoC against the existing ~6,500 / ~20 file ceiling. Will verify against `tests/unit/test_loc_budget.py` before merge.
- Pure-functional resolver (`_internal/auth/resolver.py`) MUST NOT change — discovery work happens at add-time, never at resolve-time (FR-008).
- Backward compat: existing `mp account add NAME --type X --region Y --project Z` calls MUST keep working unchanged (FR-023).
**Scale/Scope**: 3 new files (`region_probe.py`, `naming.py`, `cli/commands/login.py`), 4 modified files (`accounts.py`, `cli/main.py`, `cli/commands/account.py`, plus the `add()` signature relaxation). 4–5 new test files (`test_region_probe.py`, `test_naming.py`, `test_naming_pbt.py`, `cli/test_login_cli.py`, `integration/test_login_e2e.py`).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Evidence |
|-----------|--------|----------|
| I. Library-First | PASS | `mp login` is a thin Typer wrapper over a new public `accounts.login_unified(...)` Python API in `accounts.py`. The library function does all the work (collect creds, probe region, hit `/me`, compute name, persist via existing `accounts.add()`). The CLI handles only argument parsing, TTY-aware prompting, and stdout/stderr formatting. |
| II. Agent-Native | PASS WITH JUSTIFICATION | `mp login` is, by design, a conversational entry point — interactive prompts in TTY for project / org picking are part of its value proposition. **Non-interactive callers are first-class**: passing `--name`, `--project`, `--region`, and a credential source (env or `--secret-stdin`) makes the entire command run silently with structured error messages and stable exit codes. The existing all-flags `mp account add` path stays as the agent-native surface (FR-023). See [Complexity Tracking](#complexity-tracking) for the documented justification. |
| III. Context Window Efficiency | PASS | Region probing reuses the existing `MeService.fetch()` against `/me`; on success the `MeCache` populates `~/.mp/accounts/{name}/me.json` so subsequent `mp project list` calls hit cache. No new caches, no new endpoints. The probe stops at first success (sequential US→EU→IN). |
| IV. Two Data Paths | PASS | Auth-only feature; data-path-agnostic. Both live queries and streaming/discovery commands continue to share the same `Session` resolution. |
| V. Explicit Over Implicit | PASS | Region probe runs ONLY when `--region` is omitted (FR-007). Project selection follows a documented priority chain with no silent cross-axis fallback (FR-010). Re-login MUST NOT silently rewrite `default_project` (FR-020/021). The pure-functional resolver remains pure (FR-008). |
| VI. Unix Philosophy | PASS | `mp login` writes the success summary to stdout on the success path; all prompts and progress to stderr (FR-005). Non-interactive failure modes print structured error output and exit with the existing `0/1/2/3/4/5` exit codes from `cli/utils.py::ExitCode`. The `--secret-stdin` flag (existing) keeps secrets off argv. |
| VII. Secure by Default | PASS | Service-account secret collection uses the existing `--secret-stdin` / `MP_SECRET` paths (no new credential surface). OAuth tokens written to `~/.mp/accounts/{name}/tokens.json` with the existing `0o600` writes. The placeholder-then-rename pattern keeps no orphan token files: if `/me` fails, the placeholder dir is removed before raising. No new exposure. |

**Gate Result**: PASS — one principle (II. Agent-Native) needs explicit justification because `mp login` introduces interactive prompts on the default path. The justification (TTY-detect-and-fall-through-to-fail-fast in non-interactive contexts) is recorded in Complexity Tracking. No actual violations.

## Project Structure

### Documentation (this feature)

```text
specs/043-frictionless-auth/
├── plan.md                       # This file
├── spec.md                       # Feature specification (already created)
├── research.md                   # Phase 0 output (this command)
├── data-model.md                 # Phase 1 output (this command)
├── quickstart.md                 # Phase 1 output (this command)
├── contracts/                    # Phase 1 output (this command)
│   ├── python-api.md             # `accounts.login_unified()` + helper signatures
│   ├── cli-commands.md           # `mp login` flag/exit/output contract
│   └── error-messages.md         # Stable error message catalog (region mismatch, no-project, missing scope, ...)
├── checklists/
│   └── requirements.md           # Spec quality checklist (already created)
└── tasks.md                      # Phase 2 output (via /speckit.tasks)
```

### Source Code (repository root)

```text
src/mixpanel_headless/
├── accounts.py                                 # MODIFIED — add `login_unified(*, region=None, name=None, project=None, account_type=None, secret_stdin=False, no_browser=False, token_env=None) -> AccountSummary`. Reuse existing `add()` and `login()` for token refresh; add a `_login_oauth_browser_inline()` private that runs PKCE → /me → name → persist atomically.
├── _internal/
│   └── auth/
│       ├── region_probe.py                     # NEW — `probe_region(client_factory, credential) -> Region` walks us→eu→in, returns first 200; raises `RegionProbeError` listing all three failures on full miss.
│       ├── naming.py                           # NEW — `slugify(value: str) -> str`, `default_account_name(me: MeResponse, existing: set[str]) -> str` with `-N` collision suffix.
│       ├── flow.py                             # UNCHANGED — existing PKCE machinery is reused as-is.
│       └── resolver.py                         # UNCHANGED — pure-functional contract preserved (FR-008).
└── cli/
    ├── main.py                                 # MODIFIED — register the new `login` top-level command in `_register_commands()`.
    ├── commands/
    │   ├── login.py                            # NEW — Typer command; auth-type detection, TTY-aware project / org prompting, calls `accounts.login_unified()`, formats success line.
    │   └── account.py                          # MODIFIED — make `--project` optional for `service_account` and `oauth_token` types in `mp account add` (already optional for `oauth_browser`); update `--help` to mention `mp login`. Surface scope-hint when `/me` returns 403 for SA in `mp project list`.
    └── utils.py                                # UNCHANGED — existing `console`, `err_console`, `ExitCode`, `handle_errors` cover all needs.

tests/
├── unit/
│   ├── test_region_probe.py                    # NEW — region detection happy path (us / eu / in), all-fail consolidated error, single-region success short-circuits remaining probes.
│   ├── test_naming.py                          # NEW — slugify input/output table from spec FR-015 + collision suffix table from FR-016.
│   └── cli/
│       └── test_login_cli.py                   # NEW — `mp login` snapshot tests: oauth_browser happy, oauth_browser multi-project prompt, oauth_browser non-TTY fail, service_account no-region probe, service_account 403 scope-hint, re-login idempotency, --name override, --project override, region mismatch error.
├── pbt/
│   └── test_naming_pbt.py                      # NEW — Hypothesis: slugify is idempotent, output matches `^[a-zA-Z0-9_-]{0,32}$`, collision suffix is monotonic.
├── integration/
│   └── test_login_e2e.py                       # NEW — end-to-end against an httpx mock server: full `mp login` flow for each auth type, including stdout summary line and `~/.mp/accounts/{name}/` filesystem state.
└── unit/
    └── test_loc_budget.py                      # MODIFIED if needed — bump file count ceiling if +3 files breaches it; LoC ceiling already has headroom per source design (~400 LoC).

CLAUDE.md                                       # MODIFIED — top-level: add `mp login` to the env-vars / commands table; mention that `--region` and `NAME` are optional now.
src/mixpanel_headless/CLAUDE.md                 # MODIFIED — add `accounts.login_unified()` to the functional namespaces section.
src/mixpanel_headless/cli/CLAUDE.md             # MODIFIED — add `login` to the command groups table.
src/mixpanel_headless/cli/commands/CLAUDE.md    # MODIFIED — add `login.py` to the files table.
context/frictionless-auth.md                    # UNCHANGED — source design preserved as-is.
```

**Structure Decision**: Extends the existing single-project layout established in 042 (Library + CLI). Adds three new modules under existing directories (`_internal/auth/region_probe.py`, `_internal/auth/naming.py`, `cli/commands/login.py`) — no new top-level dirs. Modifies four existing files for the wiring (`accounts.py`, `cli/main.py`, `cli/commands/account.py`, plus the `add()` signature relaxation). Plugin (`mixpanel-plugin/`) is untouched: it already calls into `mp.accounts`, and the new `login_unified()` is purely additive.

The internal commit order within the single PR follows the source design's 115→114→116→117 sequence to give reviewers small, reviewable diffs:

1. **Commit 1 (AIE-115 prerequisites)**: Relax `--project` requirement for service accounts in `accounts.py::add` and `cli/commands/account.py`. Add scope-hint extension to the existing 403 message in `cli/commands/account.py::project_list`. Tests: extend existing `test_account_add.py` and `test_project_cli.py`.
2. **Commit 2 (AIE-114 region probe)**: New `_internal/auth/region_probe.py` + `test_region_probe.py`. Make `--region` optional in `cli/commands/account.py::add` for SA / oauth_token (probe when omitted). Browser-region-mismatch detection added to `accounts.py::login`.
3. **Commit 3 (AIE-116 naming)**: New `_internal/auth/naming.py` + `test_naming.py` + `test_naming_pbt.py`. Make `NAME` positional optional in `cli/commands/account.py::add` (derive when omitted). `accounts.py::add` exposes a `derive_name=True` kwarg as the Python API equivalent.
4. **Commit 4 (AIE-117 umbrella)**: New `cli/commands/login.py` + `accounts.login_unified()` + `cli/test_login_cli.py` + `integration/test_login_e2e.py`. Wire into `cli/main.py`. CLAUDE.md docs updated.

Each commit is a separate `git commit` with passing CI; the PR ships only after commit 4 lands. This preserves the source design's review ergonomics without splitting the work across four PRs.

## Constitution Re-Check (Post-Phase-1 Design)

Re-evaluated after producing data-model.md, contracts/, and quickstart.md:

| Principle | Status | Post-design evidence |
|-----------|--------|----------------------|
| I. Library-First | PASS | `accounts.login_unified()` is documented in [contracts/python-api.md](contracts/python-api.md) §1 with the full signature. CLI command in [contracts/cli-commands.md](contracts/cli-commands.md) §1 explicitly delegates with no business logic in the Typer handler. The two pure helpers (`region_probe.probe_region`, `naming.slugify` / `naming.default_account_name`) are independently importable per [contracts/python-api.md](contracts/python-api.md) §2. |
| II. Agent-Native | PASS | `mp login` interactive prompts are TTY-gated. Every prompt has a corresponding non-interactive failure mode that prints the same data structurally (project list, org list) to stderr and exits with `INVALID_ARGS=3`. CLI flag matrix in [contracts/cli-commands.md](contracts/cli-commands.md) §2 gives agents a complete way to drive the command silently. |
| III. Context Window Efficiency | PASS | Region probe reuses existing `MeService.fetch()` and `MeCache`. No new persistent caches. The success path populates `~/.mp/accounts/{name}/me.json` exactly once; subsequent `mp project list` and `mp account test` calls hit cache. No new endpoints called; only the existing `/api/app/me`. |
| IV. Two Data Paths | PASS | Auth-only feature; data-path-agnostic. |
| V. Explicit Over Implicit | PASS | Project-selection priority chain in [contracts/python-api.md](contracts/python-api.md) §1 is exhaustive and ordered. Re-login project preservation is enforced in `login_unified()` body (per [data-model.md](data-model.md) §4 state-transition table). Region mismatch on browser flow raises `ConfigError` rather than silently mutating user input. |
| VI. Unix Philosophy | PASS | Output split documented in [contracts/cli-commands.md](contracts/cli-commands.md) §3: success summary to stdout, all prompts and progress to stderr. Error catalog in [contracts/error-messages.md](contracts/error-messages.md) is the single source of truth for messages. |
| VII. Secure by Default | PASS | Placeholder-then-rename pattern documented in [data-model.md](data-model.md) §5. Token files written `0o600` via existing `_internal/io_utils.atomic_write_bytes`. Cleanup on probe failure removes the placeholder dir to avoid orphans. No secrets in argv (existing `--secret-stdin` and `MP_SECRET` paths reused). |

**Post-design Gate Result**: PASS — interactive-prompt justification stands, no new violations introduced by Phase 1 design.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| Interactive prompts on the default path of `mp login` (Principle II tension) | The entire feature exists to provide a conversational add-time experience: Santi's stated goal was *"type `mp login`, authenticate in the browser, and everything is configured automatically"*. For multi-project / multi-org users, "automatic" requires either picking a sensible default (often wrong) or asking. The spec chooses to ask interactively when stdin is a TTY and to fall-through-fail with the project list when it is not. Agents and CI scripts pass `--project` (and `--name`) and never hit a prompt. The existing all-flags `mp account add` path stays untouched as the canonical agent-native entry point. | "Always non-interactive, always pick the first project" would silently bind users to projects they did not see. "Always fail without prompting" would force every interactive user to run the command twice (once to get the list, once with the chosen `--project`) and would defeat the feature's purpose. The TTY-gated split delivers both audiences without compromising either. |
| Placeholder-then-rename of `~/.mp/accounts/{tmp}/` during `mp login` browser flow (slightly deferred Principle V — explicit naming) | The OAuth browser flow needs to write `tokens.json` to disk *before* `/me` returns the org name needed to compute the final account name. The placeholder pattern lets the PKCE flow finish atomically, then renames the directory after the `/me` lookup. If `/me` fails or the user aborts, the placeholder is cleaned up. The user never sees the placeholder name unless they `ls ~/.mp/accounts/` mid-flow. | The alternatives are worse: (a) hold tokens in memory until naming completes — but then a failed rename loses the tokens and forces a re-auth; (b) require the user to pre-supply `--name` for browser auth — defeats the feature; (c) rename via copy-and-delete — non-atomic, race-prone. The placeholder pattern is the standard atomic-publish pattern; we just document it. |
