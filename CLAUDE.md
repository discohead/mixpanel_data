# CLAUDE.md

This file provides guidance to Claude Code when working with this repository.

## Project Overview

`mixpanel_headless` is a complete programmable interface to Mixpanel analytics—Python library and CLI for discovery, querying, streaming, and entity management. Discover your schema, run live analytics (segmentation, funnels, retention), execute JQL, and manage entities via the Mixpanel App API.

| Context | Name | Example |
|---------|------|---------|
| PyPI package | `mixpanel_headless` | `pip install mixpanel_headless` |
| Python import | `mixpanel_headless` | `import mixpanel_headless as mp` |
| CLI command | `mp` | `mp query segmentation -e Login --from 2025-01-01` |

## Architecture

Layered architecture with `Workspace` class as the primary facade:

```
CLI (Typer)              → mp commands, output formatting
    ↓
Public API               → Workspace, auth module, exceptions, types
    ↓
Services                 → DiscoveryService, LiveQueryService
    ↓
Infrastructure           → ConfigManager, MixpanelAPIClient
```

**Three capability areas:**
- **Discovery**: Explore schema (events, properties, funnels, cohorts, bookmarks)
- **Live queries & streaming**: Call Mixpanel API directly (segmentation, funnels, retention, user profiles, JQL), stream events and profiles
- **Entity CRUD & Data Governance**: Create, read, update, delete dashboards, reports (bookmarks), cohorts, feature flags, experiments, alerts, annotations, webhooks, Lexicon definitions, drop filters, custom properties, custom events, and lookup tables via App API

## Package Structure

```
src/mixpanel_headless/
├── __init__.py              # Public API exports
├── workspace.py             # Workspace facade — `use(account=, project=, workspace=, target=)`
├── auth_types.py            # Auth surface (Account union, Session, Region, OAuthTokens, …)
├── accounts.py              # `mp.accounts` — add/list/use/login/test/export-bridge/...
├── session.py               # `mp.session` — show/use the persisted [active] block
├── targets.py               # `mp.targets` — saved (account, project, workspace?) cursors
├── exceptions.py            # Exception hierarchy (incl. AccountInUseError, WorkspaceScopeError)
├── types.py                 # Result types (SegmentationResult, AccountSummary, …)
├── _internal/               # Private implementation (do not import directly)
│   ├── config.py            # ConfigManager (TOML-backed)
│   ├── api_client.py        # MixpanelAPIClient (Session-bound; per-request OAuth bearer)
│   ├── me.py                # MeService + per-account MeCache (~/.mp/accounts/{name}/me.json)
│   ├── pagination.py        # Cursor-based App API pagination
│   ├── auth/                # Auth subsystem
│   │   ├── account.py       # Account discriminated union + TokenResolver protocol
│   │   ├── session.py       # Session, Project, WorkspaceRef, ActiveSession
│   │   ├── resolver.py      # resolve_session(...) — env > param > target > bridge > config
│   │   ├── token_resolver.py # OnDiskTokenResolver (refresh + per-account paths)
│   │   ├── token.py         # OAuthTokens, OAuthClientInfo
│   │   ├── flow.py          # OAuthFlow (PKCE + callback)
│   │   ├── bridge.py        # BridgeFile v2 + load_bridge / export_bridge / remove_bridge
│   │   ├── storage.py       # account_dir + ensure_account_dir + atomic writes
│   │   ├── pkce.py          # PKCE challenge generation (RFC 7636)
│   │   ├── callback_server.py # Local HTTP callback server
│   │   └── client_registration.py # Dynamic Client Registration (RFC 7591)
│   ├── query/               # Query engine builders and validators
│   └── services/            # Discovery, LiveQuery services
└── cli/
    ├── main.py              # Typer entry point + global flags (-a / -p / -w / -t)
    ├── commands/            # account / project / workspace / target / session
    │                        # + query, inspect, dashboards, reports, cohorts, flags,
    │                        # experiments, alerts, annotations, webhooks, lexicon,
    │                        # drop-filters, custom-properties, custom-events,
    │                        # lookup-tables, schemas, business-context
    ├── formatters.py        # JSON, JSONL, Table, CSV, Plain output
    └── utils.py             # Error handling, console helpers
```

## Code Quality Standards (STRICT)

This project enforces strict standards. CI will reject code that doesn't meet them.

### Type Safety (STRICT)

All code must be fully typed and pass `mypy --strict`. This is non-negotiable:
- No `Any` types without explicit justification
- Use `Literal` types for constrained string values
- All function signatures must have complete type annotations
- All return types must be explicitly declared

### Formatting & Linting (STRICT)

Code must pass `ruff format` and `ruff check`. Run `just check` before committing:
- Zero tolerance for lint errors
- Consistent formatting enforced by pre-commit hooks
- CI will fail on any violation

### Documentation (STRICT)

**Every class, method, and function requires a complete docstring. No exceptions.**

This applies to:
- Public API methods and classes
- Private/internal methods (prefixed with `_`)
- Module-level functions
- Helper functions
- Test fixtures and test methods

Required docstring sections:
- **Summary**: One-line description of what it does
- **Args**: Every parameter with type and description
- **Returns**: What the function returns and when
- **Raises**: All exceptions that may be raised
- **Example**: Usage example where behavior isn't immediately obvious

**Example format**: Use markdown fenced code blocks with language hints, not doctest-style `>>>` operators:

```python
# CORRECT - markdown code fence with language hint
"""
Example:
    ```python
    result = my_function("input")
    # ["output"]
    ```
"""

# WRONG - doctest style (DO NOT USE)
"""
Example:
    >>> my_function("input")
    ["output"]
"""
```

Undocumented code will not pass code review.

## Test-Driven Development (STRICT)

This project follows **strict TDD**. Tests are not optional or an afterthought.

### The TDD Workflow

1. **Write tests FIRST** — Before any implementation code
2. **Tests define behavior** — The test is the specification
3. **Implement until tests pass** — Only write code to make tests green
4. **Refactor with confidence** — Tests protect against regressions

### TDD Rules (Non-Negotiable)

- **Never write implementation code without a failing test first**
- **Study existing test patterns** — Before writing any new test, read existing tests for the same module to understand established conventions, fixtures, and mocking strategies
- **Tests must pass in CI** — Never assume local success means CI success; local environments often have configuration that CI lacks
- **Coverage minimum: 90%** — CI fails if coverage drops below this threshold

### When Adding Tests

- Find and read the corresponding test file (e.g., `test_workspace.py` for `workspace.py`)
- Copy fixture patterns and mocking approaches exactly
- Use the same naming conventions and test organization

### Test Types

- **Unit tests**: Isolated, mocked dependencies
- **Integration tests**: Real component interaction
- **Property-based tests**: Invariants verified across random inputs (use Hypothesis)

### Property-Based Testing

This project uses [Hypothesis](https://hypothesis.works) for property-based testing. PBT tests verify invariants across randomly generated inputs, catching edge cases that example-based tests miss. Name PBT test files with `_pbt` suffix (e.g., `test_types_pbt.py`). Hypothesis profiles control example counts:
- `default`: 100 examples (local development)
- `dev`: 10 examples (fast iteration)
- `ci`: 200 examples, deterministic (CI/CD)

### Mutation Testing

This project uses [mutmut](https://mutmut.readthedocs.io/) for mutation testing. Mutation testing evaluates test quality by introducing small code changes (mutations) and verifying tests detect them:
- **Killed mutant**: Test fails when mutation introduced (good - test catches bugs)
- **Survived mutant**: Test passes despite mutation (test gap - needs improvement)
- **Mutation score**: Percentage of mutants killed (target: 80%+)

Run mutation testing:
```bash
just mutate              # Run on entire codebase (slow)
just mutate-results      # View results summary
just mutate-show 1       # Inspect specific mutant
just mutate-apply 1      # Apply mutation to see the change
just mutate-apply 0      # Reset to original code
just mutate-check        # Check score meets 80% threshold
```

## Key Design Decisions

- **Streaming data access**: API returns iterators for memory-efficient processing of large datasets
- **Account → Project → Workspace hierarchy** (042 redesign): every CLI verb and Python namespace maps to one of those three axes; `Workspace.use(account=, project=, workspace=)` is the single in-session switching method.
- **Three first-class account types**: `service_account` (Basic Auth), `oauth_browser` (PKCE, tokens auto-refreshed), `oauth_token` (static bearer for CI/agents). All managed through one unified surface.
- **Single resolver**: `resolve_session(...)` consults env → param → target → bridge → config in priority order; no silent cross-axis fallback.
- **Connection-pool preservation**: `ws.use(account=...)` rebuilds the auth header but reuses the underlying `httpx.Client` (same Python instance — verified by `id()` equality in `tests/integration/test_cross_project_iteration.py`).
- **Dependency injection**: Services accept dependencies as constructor arguments for testing.

## Environment Variables

| Variable | Purpose |
|----------|---------|
| `MP_USERNAME` | Service account username |
| `MP_SECRET` | Service account secret |
| `MP_OAUTH_TOKEN` | Raw OAuth 2.0 bearer token (alternative to service account; requires `MP_PROJECT_ID` + `MP_REGION`; ignored only when the full service-account env-var set — `MP_USERNAME` + `MP_SECRET` + `MP_PROJECT_ID` + `MP_REGION` — is also present) |
| `MP_PROJECT_ID` | Project ID |
| `MP_REGION` | Data residency (us, eu, in) |
| `MP_WORKSPACE_ID` | Workspace ID for App API operations |
| `MP_AUTH_FILE` | Override path to the v2 Cowork bridge file |
| `MP_CONFIG_PATH` | Override config file location |

Config file: `~/.mp/config.toml`
OAuth browser tokens: `~/.mp/accounts/{account_name}/tokens.json` (per-account, atomic 0o600 writes)
OAuth client metadata: `~/.mp/oauth/client_{region}.json` (DCR — one client per region)
Cowork bridge: `~/.claude/mixpanel/auth.json` (default) or `$MP_AUTH_FILE`

> **Breaking change from 0.3.x:** legacy v1 / v2 configs no longer load. There is no
> `mp config convert`. To upgrade: delete `~/.mp/config.toml` and re-add accounts via
> `mp account add NAME --type {service_account|oauth_browser|oauth_token} ...`.
> Full migration walkthrough in `RELEASE_NOTES_0.4.0.md`.

## Development

**Recommended:** Use the devcontainer (Python 3.10+, uv, just pre-installed)

**First-time setup after cloning**: run `just install-hooks` to install the
git pre-commit hook. Without it, `ruff check` / `ruff format` violations slip
through to CI.

This project uses [just](https://github.com/casey/just) as a command runner.

**`just check` is a strict superset of CI** — if `just check` passes locally,
CI will pass. The only documented difference is that CI sets
`HYPOTHESIS_PROFILE=ci` (200 deterministic examples vs the local default 100),
which doesn't change pass/fail outcomes.

| Command | Description |
|---------|-------------|
| `just` | List all available commands |
| `just install-hooks` | One-time: install git pre-commit hook (block ruff/format failures) |
| `just check` | Run all checks (lint + fmt-check + typecheck + test-cov + build) |
| `just test` | Run tests (supports args: `just test -k foo`) |
| `just test-dev` | Run tests with dev Hypothesis profile (fast, 10 examples) |
| `just test-ci` | Run tests with CI Hypothesis profile (thorough, 200 examples) |
| `just test-pbt` | Run property-based tests only |
| `just test-pbt-dev` | Run PBT tests with dev profile |
| `just test-cov` | Run tests with coverage (fails if below 90%) |
| `just mutate` | Run mutation testing on entire codebase |
| `just mutate-results` | Show mutation testing results |
| `just mutate-show ID` | Show details for specific mutant |
| `just mutate-check` | Check mutation score meets 80% threshold |
| `just hypo-codemod` | Refactor deprecated Hypothesis code |
| `just hypo-write` | Generate property-based tests for a module |
| `just lint` | Lint code with ruff |
| `just fmt` | Format code with ruff |
| `just typecheck` | Type check with mypy |
| `just mp` | Run the CLI (supports args: `just mp --help`) |

```bash
# Run all checks before committing
just check

# Run specific tests
just test -k test_name

# Fast iteration on property-based tests
just test-pbt-dev
```

### CLI Debugging (IMPORTANT)

**Never suppress stderr when running CLI commands.** The `mp` CLI provides rich error messages, stack traces, and diagnostic information that are essential for debugging.

```bash
# WRONG - hides errors
uv run mp query segmentation -e login 2>/dev/null

# CORRECT - preserves error output
uv run mp query segmentation -e login
```

Suppressing stderr causes silent failures and makes it impossible to diagnose issues like rate limits, authentication errors, or malformed queries.

## Technology Stack

- Python 3.10+ with full type hints (mypy --strict compliant)
- Typer (CLI) + Rich (output formatting)
- jq (JSON filtering via `--jq` option for CLI commands)
- httpx (HTTP client), Pydantic (validation)
- Hypothesis (property-based testing), mutmut (mutation testing)
- uv (package manager), just (command runner)

## mixpanel-headless Plugin (v4.1 — Distilled API Surface + Live Docs)

This project includes a Claude Code plugin in `mixpanel-plugin/`. The plugin provides the `mixpanel_headless` API surface and a live documentation system (`help.py`) for querying and analyzing Mixpanel data with Python.

### Plugin Components

| Type | Name | Invocation |
|------|------|------------|
| **Command** | `mixpanel-headless:auth` | `/mixpanel-headless:auth` — manage credentials, accounts, OAuth |
| **Skill** | `mixpanel-headless:setup` | `/mixpanel-headless:setup` — install deps, verify auth |
| **Skill** | `mixpanelyst` | Auto-triggered on analytics questions |
| **Skill** | `dashboard-expert` | Auto-triggered on dashboard analysis, creation, modification |
| **Script** | `help.py` | `python help.py Workspace.query` — live API docs with fuzzy search |
| **Script** | `auth_manager.py` | `python auth_manager.py status` — auth status JSON |

### Usage

```
# Setup
/mixpanel-headless:setup

# API lookup
python help.py Workspace.query        # method signature + docstring + referenced types
python help.py search cohort           # fuzzy search across names, docstrings, enum members
python help.py Filter                  # type fields + construction patterns + related methods
```

## Active Technologies
- Python 3.10+ (mypy --strict) + httpx (HTTP client), Pydantic v2 (validation), Typer (CLI), Rich (output)
- JSON files at `~/.mp/oauth/` (token + client info persistence)
- Mixpanel App API (remote CRUD for entities and data governance)
- Python 3.10+ with full type hints (mypy --strict) + httpx (HTTP client), Pydantic v2 (validation), pandas (DataFrames) (029-insights-query-api)
- N/A — live query only, no local persistence (029-insights-query-api)
- Python 3.10+ (mypy --strict) + httpx (HTTP), Pydantic v2 (validation), pandas (DataFrames) (031-shared-infra-extraction)
- Python 3.10+ (mypy --strict) + httpx (HTTP client), Pydantic v2 (validation), pandas (DataFrames) (033-retention-query)
- Python 3.10+ (mypy --strict) + Pydantic v2 (for existing `CreateCohortParams`), pandas (existing), Hypothesis (PBT) (035-cohort-definition-builder)
- N/A — pure types, no persistence (035-cohort-definition-builder)
- Python 3.10+ (mypy --strict) + Pydantic v2 (validation), httpx (HTTP), pandas (DataFrames), Hypothesis (PBT) (036-cohort-behaviors)
- Python 3.10+ (mypy --strict compliant) + Pydantic v2 (validation), httpx (HTTP client), Hypothesis (PBT), mutmut (mutation testing) (037-custom-properties-queries)
- N/A — pure query-building types, no persistence (037-custom-properties-queries)
- Python 3.10+ (mypy --strict compliant) + Pydantic v2 (validation/models), httpx (HTTP client), Typer (CLI), Rich (output), tomli/tomli_w (TOML read/write) (038-auth-project-workspace-redesign)
- TOML config file (`~/.mp/config.toml`), JSON cache files (`~/.mp/oauth/me_{region}.json`), JSON OAuth token files (`~/.mp/oauth/tokens_{region}.json`) (038-auth-project-workspace-redesign)
- Python 3.10+ (mypy --strict) + httpx (HTTP), Pydantic v2 (validation), pandas (DataFrames), Hypothesis (PBT) (039-query-user-engine)
- Python 3.10+ + httpx, Pydantic v2, Typer, Rich, pandas, Hypothesis (040-query-engine-completeness)
- N/A — query parameter types only, no persistence (040-query-engine-completeness)

## Recent Changes
- **0.4.0 (042-auth-architecture-redesign)**: Hard rewrite of the auth subsystem. Single schema, single resolver, three first-class account types (`service_account` / `oauth_browser` / `oauth_token`). New CLI groups: `mp account`, `mp project`, `mp workspace`, `mp target`, `mp session`. New globals: `--account` / `--project` / `--workspace` / `--target`. `Workspace.use(...)` is the single in-session switching method. `MP_OAUTH_TOKEN` env path (PR #125) preserved as the recommended non-interactive mode. Plugin bumped to 5.0.0 with stable JSON contract (`schema_version: 1`). **Breaking**: legacy v1 / v2 configs no longer load — wipe `~/.mp/config.toml` and re-add accounts. Full migration walkthrough in [`RELEASE_NOTES_0.4.0.md`](RELEASE_NOTES_0.4.0.md).
- 029-insights-query-api: Added Python 3.10+ with full type hints (mypy --strict) + httpx (HTTP client), Pydantic v2 (validation), pandas (DataFrames)

<!-- SPECKIT START -->
For additional context about technologies to be used, project structure,
shell commands, and other important information, read the current plan:
[specs/042-auth-architecture-redesign/plan.md](specs/042-auth-architecture-redesign/plan.md)
<!-- SPECKIT END -->
