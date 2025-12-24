# Copilot Instructions for mixpanel_data

## Project Overview

**mixpanel_data** is a Python library and CLI for working with Mixpanel analytics data, designed for AI coding agents.

**Core Concept**: Fetch Mixpanel data once into a local DuckDB database, then query repeatedly with SQL—preserving context window for reasoning rather than consuming it with raw API responses.

**Technology Stack**: Python 3.11+, Typer (CLI), Rich (output), Pydantic v2 (validation), DuckDB (storage), httpx (HTTP client), pandas (DataFrames), pytest, ruff, mypy

## Build & Test Setup

### Prerequisites
- Python 3.11+ (3.12 recommended)
- [uv](https://docs.astral.sh/uv/) - Python package manager

### Development Commands

| Command | Description |
|---------|-------------|
| `uv sync --all-extras` | Sync all dependencies |
| `uv run pytest` | Run tests |
| `uv run pytest --cov=src/mixpanel_data` | Run tests with coverage |
| `uv run ruff check src/ tests/` | Lint code |
| `uv run ruff check --fix src/ tests/` | Auto-fix lint errors |
| `uv run ruff format src/ tests/` | Format code |
| `uv run mypy src/` | Type check |
| `uv build` | Build package |

### Installation & Setup
**ALWAYS sync dependencies before any development work:**
```bash
uv sync --all-extras
```

### Testing
```bash
# Run all tests
uv run pytest

# Run tests with coverage
uv run pytest --cov=src/mixpanel_data --cov-report=term-missing

# Run specific tests
uv run pytest -k test_name
uv run pytest tests/unit/test_config.py
```

Tests are organized:
- `tests/unit/` - Unit tests (isolated, mocked dependencies)
- `tests/integration/` - Integration tests (real component interaction)
- `tests/conftest.py` - Shared fixtures

### Pre-commit Checks
**ALWAYS run all checks before committing:**
```bash
uv run ruff format src/ tests/
uv run ruff check src/ tests/
uv run mypy src/
uv run pytest
```

## Project Structure

```
src/mixpanel_data/
├── __init__.py              # Public API exports
├── workspace.py             # Workspace facade class
├── auth.py                  # Public auth module
├── exceptions.py            # Exception hierarchy
├── types.py                 # Result types (FetchResult, SegmentationResult, etc.)
├── py.typed                 # PEP 561 marker for typed package
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

tests/
├── conftest.py              # Shared pytest fixtures
├── unit/                    # Unit tests
└── integration/             # Integration tests

context/                     # Design documentation
├── mixpanel_data-design.md              # Architecture & public API
├── mixpanel_data-project-brief.md       # Vision and goals
├── mp-cli-project-spec.md               # CLI specification
└── mixpanel-http-api-specification.md   # Mixpanel HTTP API reference
```

## Architecture

**Layered Design:**
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

## Code Style

### Type Safety
All code must be fully typed and pass `mypy --strict`:
- No `Any` types without explicit justification
- Use `Literal` types for constrained string values
- Use `X | None` instead of `Optional[X]` (modern union syntax)
- Missing type annotations are not acceptable

### Documentation
Every class, method, and function—public and private—requires a complete docstring:
- One-line summary
- Args section with type and description for each parameter
- Returns section describing the return value
- Raises section listing exceptions that may be raised
- Example section where usage isn't immediately obvious

### Formatting & Linting
Code must pass `ruff format` and `ruff check`. Run all checks before committing.

### Development Approach
This project uses spec-driven development and test-first (TDD):
1. Define behavior in specs/design docs before implementation
2. Write tests that capture expected behavior
3. Implement until tests pass
4. Refactor while keeping tests green

### Testing Requirements
New functionality requires tests:
- Unit tests: Isolated, mocked dependencies
- Integration tests: Real component interaction

## Key Design Decisions

- **Explicit table management**: Tables never implicitly overwritten; raise `TableExistsError` if exists
- **Streaming ingestion**: API returns iterators, storage accepts iterators (memory efficient)
- **JSON property storage**: Properties stored as JSON columns, queried with `properties->>'$.field'`
- **Immutable credentials**: Resolved once at Workspace construction
- **Frozen dataclasses**: All result types are frozen (immutable)
- **Dependency injection**: Services accept dependencies as constructor arguments

## Configuration System

Config file: `~/.mp/config.toml` (TOML format)
- Multiple named accounts supported
- One account marked as default
- Environment variables override config file: `MP_USERNAME`, `MP_SECRET`, `MP_PROJECT_ID`, `MP_REGION`, `MP_CONFIG_PATH`

## Code Review Guidelines

### Architecture Enforcement

**Layer Boundaries**: Flag any code that:
- Has CLI code directly accessing storage or API clients (should go through Workspace facade)
- Has services calling other services horizontally (they should only call infrastructure)

**Private API for External Consumers**: The `src/mixpanel_data/_internal/` directory is private implementation that external consumers should not import. However, internal package code (like `workspace.py`, `auth.py`, CLI commands) legitimately imports from `_internal/` to implement the public API. Flag any:
- Types from `_internal/` appearing in public function signatures (return types, parameters)
- `__all__` exports that include `_internal` symbols
- Documentation or examples that tell users to import from `_internal`

### Exception Handling

Use the library's exception hierarchy—never bare exceptions. Flag:
- `except Exception:` or `except BaseException:` (should be `except MixpanelDataError:`)
- `raise Exception(...)` (should use a specific subclass like `ConfigError`, `QueryError`, etc.)
- Missing exception chaining (`raise X from e`)

**Valid exception classes**: `MixpanelDataError`, `ConfigError`, `AccountNotFoundError`, `AccountExistsError`, `AuthenticationError`, `RateLimitError`, `QueryError`, `TableExistsError`, `TableNotFoundError`

### Security: Credential Handling

Flag any code that could expose secrets:
- Logging or printing `Credentials` objects without going through `__repr__` (which redacts)
- Using `str(secret)` instead of `secret.get_secret_value()` for SecretStr
- f-strings or `.format()` that interpolate secret values
- Secrets in error messages or exception details dicts

### Immutability Patterns

All result types and credentials must be immutable. Flag:
- Dataclasses without `frozen=True`
- Pydantic models without `model_config = ConfigDict(frozen=True)`
- Code that mutates frozen objects (should use `object.__setattr__` for internal caching only)
- Mutable default arguments (`list` instead of `field(default_factory=list)`)

### Streaming and Memory Efficiency

Data should flow through iterators, not be loaded entirely into memory. Flag:
- Functions returning `list[dict]` when they should return `Iterator[dict]`
- Collecting all results with `list()` when streaming is possible
- Large data structures stored in variables when they could be yielded
