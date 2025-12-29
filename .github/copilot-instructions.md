# Copilot Instructions for mixpanel_data

> Python library + CLI for Mixpanel analytics: discovery, live queries, local DuckDB analysis.

## Quick Reference (Start Here)

```bash
# Setup (REQUIRED first)
uv sync --all-extras

# Verify changes (run ALL before committing)
uv run ruff format src/ tests/                    # Format code
uv run ruff check src/ tests/                     # Lint code
uv run mypy src/ tests/                           # Type check
uv run pytest                                     # Run tests

# Run specific test
uv run pytest -k test_name

# Tests with coverage (must be ≥90%)
uv run pytest --cov=src/mixpanel_data --cov-fail-under=90
```

## Tech Stack

- **Language**: Python 3.11+
- **CLI**: Typer + Rich
- **Validation**: Pydantic v2
- **Database**: DuckDB
- **HTTP**: httpx
- **Testing**: pytest, ruff, mypy

## Project Structure

```
src/mixpanel_data/
├── workspace.py        # Main facade (entry point for library)
├── auth.py             # Public auth module
├── exceptions.py       # Exception hierarchy
├── types.py            # Result types (frozen dataclasses)
├── _internal/          # PRIVATE: never import in public signatures
│   ├── config.py       # ConfigManager, Credentials
│   ├── api_client.py   # MixpanelAPIClient
│   ├── storage.py      # StorageEngine (DuckDB)
│   └── services/       # Discovery, Fetcher, LiveQuery services
└── cli/
    ├── main.py         # Typer entry point
    └── commands/       # auth, fetch, query, inspect commands

tests/
├── unit/              # Isolated tests (mocked deps)
└── integration/       # Component interaction tests
```

## Architecture

```
CLI (Typer) → Public API (Workspace) → Services → Infrastructure (Config, API, Storage)
```

**Layer rules:**
- CLI calls Workspace only (never storage/API directly)
- Services call infrastructure only (no horizontal service calls)

## Code Requirements

### Types (STRICT)
- All code passes `mypy --strict`
- No `Any` without justification
- Use `X | None` (not `Optional[X]`)
- Use `Literal` for constrained strings

### Docstrings (REQUIRED)
Every function/method/class needs:
- One-line summary
- Args with types
- Returns description
- Raises section

### Testing (TDD)
- Write test FIRST, then implement
- Unit tests: `tests/unit/`
- Integration tests: `tests/integration/`
- Coverage minimum: 90%

### Patterns
- `frozen=True` on all dataclasses
- `model_config = ConfigDict(frozen=True)` on Pydantic models
- Use `Iterator[T]` not `list[T]` for streaming data
- Use `field(default_factory=list)` not `[]` for defaults

## Exceptions

Use library hierarchy, never bare `Exception`:

**Valid classes:**
- `MixpanelDataError` (base)
- `ConfigError`
- `AccountNotFoundError`
- `AccountExistsError`
- `AuthenticationError`
- `RateLimitError`
- `QueryError`
- `TableExistsError`
- `TableNotFoundError`

**Always chain:** `raise XError(...) from e`

## Security: Credentials

**NEVER expose secrets:**
- Use `secret.get_secret_value()` for SecretStr
- Don't interpolate secrets in f-strings
- Don't log Credentials without using `__repr__`

## Agent Task Guidelines

### Adding a Feature
1. Check `context/` for design specs
2. Write test in `tests/unit/` first
3. Implement minimal code to pass
4. Run all checks: `uv run ruff format src/ tests/ && uv run ruff check src/ tests/ && uv run mypy src/ tests/ && uv run pytest`

### Fixing a Bug  
1. Write failing test reproducing bug
2. Fix implementation
3. Run all checks: `uv run ruff format src/ tests/ && uv run ruff check src/ tests/ && uv run mypy src/ tests/ && uv run pytest`

### Adding CLI Command
1. Add to `src/mixpanel_data/cli/commands/`
2. Register in `main.py`
3. Follow existing patterns (formatters, error handling)

### Modifying Public API
1. Edit `workspace.py` or `auth.py`
2. Update `__init__.py` exports if needed
3. Never expose `_internal` types in signatures

## DO NOT

- Import from `_internal/` in public signatures
- Use `except Exception:` (use `MixpanelDataError`)
- Use mutable defaults (`list` → `field(default_factory=list)`)
- Skip type annotations
- Skip docstrings
- Commit without running all checks
