# CLAUDE.md

This file provides guidance to Claude Code when working with this repository.

## Project Overview

`mixpanel_data` is a Python library and CLI for working with Mixpanel analytics data. The core insight: fetch data once into a local DuckDB database, then query it repeatedly with SQL—preserving context window for reasoning rather than consuming it with raw API responses.

| Context | Name | Example |
|---------|------|---------|
| PyPI package | `mixpanel_data` | `pip install mixpanel_data` |
| Python import | `mixpanel_data` | `import mixpanel_data as mp` |
| CLI command | `mp` | `mp fetch events --from 2024-01-01` |

## Architecture

Layered architecture with `Workspace` class as the primary facade:

```
CLI (Typer)              → mp commands, output formatting
    ↓
Public API               → Workspace, auth module, exceptions, types
    ↓
Services                 → DiscoveryService, FetcherService, LiveQueryService
    ↓
Infrastructure           → ConfigManager, MixpanelAPIClient, StorageEngine (DuckDB)
```

**Two data paths:**
- **Live queries**: Call Mixpanel API directly (segmentation, funnels, retention)
- **Local analysis**: Fetch → Store in DuckDB → Query with SQL → Iterate

## Package Structure

```
src/mixpanel_data/
├── __init__.py              # Public API exports
├── workspace.py             # Workspace facade class
├── auth.py                  # Public auth module
├── exceptions.py            # Exception hierarchy
├── types.py                 # Result types (FetchResult, SegmentationResult, etc.)
├── _internal/               # Private implementation (do not import directly)
│   ├── config.py            # ConfigManager, Credentials
│   ├── api_client.py        # MixpanelAPIClient
│   ├── storage.py           # StorageEngine (DuckDB)
│   └── services/            # Discovery, Fetcher, LiveQuery services
└── cli/
    ├── main.py              # Typer app entry point
    ├── commands/            # auth, fetch, query, inspect command groups
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

- **Explicit table management**: Tables never implicitly overwritten; `TableExistsError` if exists
- **Streaming ingestion**: API returns iterators, storage accepts iterators (memory efficient)
- **JSON property storage**: Properties stored as JSON columns, queried with `properties->>'$.field'`
- **Immutable credentials**: Resolved once at Workspace construction
- **Dependency injection**: Services accept dependencies as constructor arguments for testing

## Environment Variables

| Variable | Purpose |
|----------|---------|
| `MP_USERNAME` | Service account username |
| `MP_SECRET` | Service account secret |
| `MP_PROJECT_ID` | Project ID |
| `MP_REGION` | Data residency (us, eu, in) |
| `MP_CONFIG_PATH` | Override config file location |

Config file: `~/.mp/config.toml`

## Development

**Recommended:** Use the devcontainer (Python 3.11, uv, just pre-installed)

This project uses [just](https://github.com/casey/just) as a command runner:

| Command | Description |
|---------|-------------|
| `just` | List all available commands |
| `just check` | Run all checks (lint, typecheck, test) |
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

## Technology Stack

- Python 3.11+ with full type hints (mypy --strict compliant)
- Typer (CLI) + Rich (output formatting)
- DuckDB (embedded analytical database)
- httpx (HTTP client), Pydantic (validation)
- Hypothesis (property-based testing), mutmut (mutation testing)
- uv (package manager), just (command runner)

## Reference Documentation

Design documents in `context/`:
- [mixpanel_data-project-brief.md](context/mixpanel_data-project-brief.md) — Vision and goals
- [mixpanel_data-design.md](context/mixpanel_data-design.md) — Architecture and public API
- [mp-cli-project-spec.md](context/mp-cli-project-spec.md) — CLI specification
- [mixpanel-http-api-specification.md](context/mixpanel-http-api-specification.md) — Mixpanel API reference

## Active Technologies
- Python 3.11+ + Typer (CLI), httpx (HTTP), Rich (progress to stderr) (011-streaming-api)
- N/A for streaming (bypasses DuckDB entirely) (011-streaming-api)
- Python 3.11+ + httpx (HTTP client), Typer (CLI), Rich (output formatting), Pydantic v2 (validation) (012-lexicon-schemas)
- N/A (read-only API operations, no local persistence) (012-lexicon-schemas)
- Python 3.11+ + DuckDB (analytical queries), pandas (DataFrame conversion), Typer (CLI), Rich (output formatting) (014-introspection-api)
- DuckDB (existing `StorageEngine` class) (014-introspection-api)
- Python 3.11+ with full type hints (mypy --strict compliant) + httpx (HTTP client), Typer (CLI), Rich (output formatting), Pydantic v2 (validation), pandas (DataFrame conversion) (015-bookmarks-api)
- N/A (live queries only - no local persistence for bookmark operations) (015-bookmarks-api)

## Recent Changes
- 011-streaming-api: Added Python 3.11+ + Typer (CLI), httpx (HTTP), Rich (progress to stderr)
