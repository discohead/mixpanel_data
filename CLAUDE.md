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

## Code Style

**Type Safety**: All code must be fully typed and pass `mypy --strict`. No `Any` types without explicit justification. Use `Literal` types for constrained string values.

**Documentation**: Every class, method, and function—public and private—requires a complete docstring:
- One-line summary
- Args section with type and description for each parameter
- Returns section describing the return value
- Raises section listing exceptions that may be raised
- Example section where usage isn't immediately obvious

**Formatting & Linting**: Code must pass `ruff format` and `ruff check`. Run `just check` before committing to verify all standards are met.

**Development Approach**: This project uses spec-driven development and test-first (TDD):
1. Define behavior in specs/design docs before implementation
2. Write tests that capture expected behavior
3. Implement until tests pass
4. Refactor while keeping tests green

**Testing**: New functionality requires tests. Aim for both unit tests (isolated, mocked dependencies) and integration tests (real component interaction).

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
| `just lint` | Lint code with ruff |
| `just fmt` | Format code with ruff |
| `just typecheck` | Type check with mypy |
| `just mp` | Run the CLI (supports args: `just mp --help`) |

```bash
# Run all checks before committing
just check

# Run specific tests
just test -k test_name
```

## Technology Stack

- Python 3.11+ with full type hints (mypy --strict compliant)
- Typer (CLI) + Rich (output formatting)
- DuckDB (embedded analytical database)
- httpx (HTTP client), Pydantic (validation)
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

## Recent Changes
- 011-streaming-api: Added Python 3.11+ + Typer (CLI), httpx (HTTP), Rich (progress to stderr)
