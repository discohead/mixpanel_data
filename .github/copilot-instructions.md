# Copilot Instructions for mixpanel_data

## Project Overview

**mixpanel_data** is a Python library and CLI for working with Mixpanel analytics data, designed for AI coding agents. The project is in **early implementation phase** with foundation layer complete (~1,100 lines of code, 93 tests, 97% coverage).

**Core Concept**: Fetch Mixpanel data once into a local DuckDB database, then query repeatedly with SQL—preserving context window for reasoning rather than consuming it with raw API responses.

**Technology Stack**: Python 3.11+, Pydantic v2, DuckDB (future), httpx (future), Typer CLI (future), pandas, pytest, ruff, mypy

**Current Status**: Foundation layer complete (ConfigManager, exceptions, result types). Next phases: API client, storage engine, services, CLI.

## Build & Test Setup

### Prerequisites
- Python 3.12.3 (or Python 3.11+)
- pip 24.0+

### Installation & Setup
**ALWAYS run installation before any development work:**
```bash
cd /home/runner/work/mixpanel_data/mixpanel_data
pip install -e ".[dev]"
```

This installs the package in editable mode with all dev dependencies (pytest, ruff, mypy, pytest-cov, pandas-stubs). Installation takes ~30-60 seconds.

### Testing
**Run all tests (93 tests, ~1 second):**
```bash
cd /home/runner/work/mixpanel_data/mixpanel_data
pytest -v
```

**Run tests with coverage (target: 95%+):**
```bash
pytest --cov=src/mixpanel_data --cov-report=term
```

**Run specific test files:**
```bash
pytest tests/unit/test_config.py -v
pytest tests/integration/test_foundation.py -v
```

Tests are organized:
- `tests/unit/` - Unit tests for individual components
- `tests/integration/` - Integration tests for workflows
- `tests/conftest.py` - Shared fixtures (temp_dir, config_path, config_manager, sample_credentials)

### Linting & Type Checking

**ALWAYS run linting before committing:**
```bash
cd /home/runner/work/mixpanel_data/mixpanel_data
ruff check .
```

**Auto-fix linting issues (14 of 19 current issues are auto-fixable):**
```bash
ruff check --fix .
```

**Known acceptable linting warnings:**
- B017: Tests use `pytest.raises(Exception)` for frozen dataclass validation - this is intentional
- Some unused imports in test files that verify public API exports

**Type checking (must pass with zero errors):**
```bash
mypy src
```
Note: Tests are excluded from strict type checking (see pyproject.toml `tool.mypy.overrides`)

### Building the Package
**To build distribution packages:**
```bash
pip install build --user
python -m build
```
Creates `dist/mixpanel_data-0.1.0.tar.gz` and `dist/mixpanel_data-0.1.0-py3-none-any.whl` (~30 seconds)

## Project Structure

```
/home/runner/work/mixpanel_data/mixpanel_data/
├── src/mixpanel_data/          # Main source code
│   ├── __init__.py             # Public API exports (exceptions, result types)
│   ├── auth.py                 # Auth module (placeholder)
│   ├── exceptions.py           # All exception classes (85 lines, 100% coverage)
│   ├── types.py                # Result types: FetchResult, SegmentationResult, etc. (158 lines)
│   ├── py.typed                # PEP 561 marker for type checking
│   └── _internal/              # Private implementation (not in public API)
│       ├── config.py           # ConfigManager, Credentials, AccountInfo (153 lines, 96% coverage)
│       └── __init__.py
├── tests/                      # Test suite (93 tests)
│   ├── conftest.py             # Shared pytest fixtures
│   ├── unit/                   # Unit tests
│   │   ├── test_config.py      # ConfigManager tests
│   │   ├── test_exceptions.py  # Exception tests
│   │   └── test_types.py       # Result type tests
│   └── integration/            # Integration tests
│       ├── test_foundation.py  # Foundation layer workflow tests
│       └── test_config_file.py # Config file persistence tests
├── docs/                       # Design documentation
│   ├── mixpanel_data-design.md          # Architecture & component specs
│   ├── mixpanel_data-project-brief.md   # Vision and goals
│   ├── mp-cli-project-spec.md           # CLI specification
│   ├── MIXPANEL_DATA_MODEL_REFERENCE.md # Mixpanel data model
│   └── api-docs/                        # Mixpanel API documentation
├── specs/                      # Implementation specifications
│   └── 001-foundation-layer/   # Foundation layer spec (current phase)
├── pyproject.toml              # Project configuration (build, deps, tools)
├── README.md                   # User-facing documentation
├── CLAUDE.md                   # Claude Code specific guidance
└── .gitignore                  # Git ignore patterns
```

## Architecture

**Layered Design:**
```
CLI Layer (Typer)           → [NOT IMPLEMENTED] Argument parsing, output formatting
    ↓
Public API Layer            → [PARTIAL] Workspace class (future), auth module (stub)
    ↓
Service Layer               → [NOT IMPLEMENTED] DiscoveryService, FetcherService, LiveQueryService
    ↓
Infrastructure Layer        → [PARTIAL] ConfigManager (✓), MixpanelAPIClient (future), StorageEngine (future)
```

**Key Design Principles:**
- **Explicit table management**: Tables never implicitly overwritten; raise `TableExistsError` if exists
- **Immutable credentials**: Resolved once at Workspace construction
- **Frozen dataclasses**: All result types are frozen (immutable)
- **Dependency injection**: Services accept dependencies as constructor arguments

## Development Workflow

### Configuration System
Config file: `~/.mp/config.toml` (TOML format)
- Multiple named accounts supported
- One account marked as default
- Environment variables override config file: `MP_USERNAME`, `MP_SECRET`, `MP_PROJECT_ID`, `MP_REGION`, `MP_CONFIG_PATH`

### Adding New Code
1. **Check design docs first**: `docs/mixpanel_data-design.md` and `specs/001-foundation-layer/` contain detailed specifications
2. **Follow existing patterns**: Look at `config.py`, `exceptions.py`, `types.py` for style
3. **Use Pydantic v2**: For validation and data models (frozen dataclasses with `model_config`)
4. **Type annotations**: Use `from __future__ import annotations` and full type hints
5. **Docstrings**: Google-style docstrings for classes and public methods

### Writing Tests
1. **Use fixtures**: Import from `conftest.py` (`temp_dir`, `config_path`, `config_manager`, `sample_credentials`)
2. **Test organization**: Group tests in classes by component (e.g., `TestConfigManager`)
3. **Naming**: `test_<what_is_being_tested>` (e.g., `test_add_account_stores_correctly`)
4. **Coverage target**: 95%+ (currently 97%)
5. **Frozen models**: Use `pytest.raises(Exception)` for immutability tests (ignore B017 linting warning)

### Code Style
- **Line length**: 88 characters (Black-compatible)
- **Imports**: Sorted with isort (included in ruff)
- **String quotes**: No preference (project uses both single and double)
- **Type hints**: Always use (mypy strict mode enabled)

## Known Issues & Workarounds

### Linting Issues (Non-Critical)
The codebase currently has 19 ruff findings:
- **14 auto-fixable**: Run `ruff check --fix .` to fix import ordering and type annotation quotes
- **5 non-fixable B017 warnings**: `pytest.raises(Exception)` in tests for frozen model validation - this is intentional and can be ignored

### Test Execution
- **All tests pass**: 93/93 tests pass in ~1 second
- **No flaky tests**: Tests are deterministic
- **No timing issues**: All tests complete quickly

### Python Version
- **Required**: Python 3.11+ (specified in pyproject.toml)
- **Tested**: Python 3.12.3
- **tomli**: For Python <3.11 TOML parsing (not needed with 3.11+, which has tomllib built-in)

## File Locations Quick Reference

**Main Source Files:**
- Public API: `src/mixpanel_data/__init__.py`
- Exceptions: `src/mixpanel_data/exceptions.py`
- Result types: `src/mixpanel_data/types.py`
- Config management: `src/mixpanel_data/_internal/config.py`

**Test Files:**
- Unit tests: `tests/unit/test_*.py`
- Integration tests: `tests/integration/test_*.py`
- Shared fixtures: `tests/conftest.py`

**Configuration:**
- Package config: `pyproject.toml` (dependencies, tool configs)
- Ruff config: `[tool.ruff]` section in pyproject.toml
- Mypy config: `[tool.mypy]` section in pyproject.toml
- Pytest config: `[tool.pytest.ini_options]` section in pyproject.toml
- Git ignore: `.gitignore`

**Documentation:**
- User docs: `README.md`
- Design specs: `docs/*.md`
- Implementation specs: `specs/001-foundation-layer/`
- AI guidance: `CLAUDE.md`

## Trust These Instructions

**These instructions have been validated** by running all commands in the actual environment. If you encounter issues:
1. First verify you're in the correct directory: `/home/runner/work/mixpanel_data/mixpanel_data`
2. Check if dependencies are installed: `pip install -e ".[dev]"`
3. Only then search for additional information or report the issue

**Command execution times** (for timeout planning):
- `pip install -e ".[dev]"`: 30-60 seconds
- `pytest -v`: 1 second
- `pytest --cov`: 1 second
- `ruff check .`: <1 second
- `mypy src`: 2-3 seconds
- `python -m build`: 30 seconds
