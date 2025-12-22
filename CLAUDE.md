# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

`mixpanel_data` is a Python library and CLI for working with Mixpanel analytics data, designed for AI coding agents. The core insight: agents should fetch data once into a local DuckDB database, then query it repeatedly with SQL—preserving context window for reasoning rather than consuming it with raw API responses.

**Status:** Foundation layer implemented. Comprehensive specifications exist in `docs/`; core infrastructure is complete.

## Naming Convention

| Context | Name | Example |
|---------|------|---------|
| PyPI package | `mixpanel_data` | `pip install mixpanel_data` |
| Python import | `mixpanel_data` | `import mixpanel_data as mp` |
| CLI command | `mp` | `mp fetch events --from 2024-01-01` |

## Architecture

Layered architecture with `Workspace` class as facade:

```
CLI Layer (Typer)           → Argument parsing, output formatting
    ↓
Public API Layer            → Workspace class, auth module
    ↓
Service Layer               → DiscoveryService, FetcherService, LiveQueryService
    ↓
Infrastructure Layer        → ConfigManager, MixpanelAPIClient, StorageEngine (DuckDB)
```

**Two data paths:**
- **Live queries**: Call Mixpanel API directly (segmentation, funnels, retention)
- **Local analysis**: Fetch → Store in DuckDB → Query with SQL → Iterate

## Technology Stack

- Python 3.11+, Typer (CLI), Rich (output), Pydantic (validation)
- DuckDB (embedded analytical database), httpx (HTTP client)
- pandas (DataFrame integration)
- uv (package manager), just (command runner)

## Design Documents

Read in this order for implementation:

1. **[docs/mixpanel_data-project-brief.md](docs/mixpanel_data-project-brief.md)** — Vision and goals
2. **[docs/mixpanel_data-design.md](docs/mixpanel_data-design.md)** — Architecture, component specs, public API
3. **[docs/mp-cli-project-spec.md](docs/mp-cli-project-spec.md)** — Full CLI specification
4. **[docs/MIXPANEL_DATA_MODEL_REFERENCE.md](docs/MIXPANEL_DATA_MODEL_REFERENCE.md)** — Mixpanel data model for Pydantic/DuckDB mapping

## Package Structure

```
justfile                     # Development commands (run `just` to see all)
src/mixpanel_data/
├── __init__.py              # ✅ Public API exports (exceptions, result types)
├── workspace.py             # ⏳ Workspace facade class
├── auth.py                  # ✅ Public auth module (re-exports ConfigManager, Credentials)
├── exceptions.py            # ✅ Exception hierarchy (9 exception classes)
├── types.py                 # ✅ Result types (FetchResult, SegmentationResult, etc.)
├── py.typed                 # ✅ PEP 561 marker for typed package
├── _internal/               # Private implementation
│   ├── __init__.py          # ✅
│   ├── config.py            # ✅ ConfigManager, Credentials, AccountInfo
│   ├── api_client.py        # ✅ MixpanelAPIClient
│   ├── storage.py           # ✅ StorageEngine (DuckDB)
│   └── services/
│       ├── __init__.py      # ✅ Services package
│       ├── discovery.py     # ✅ DiscoveryService
│       ├── fetcher.py       # ⏳ FetcherService
│       └── live_query.py    # ⏳ LiveQueryService
└── cli/
    ├── main.py              # ⏳ Typer app entry point
    └── commands/            # ⏳ auth, fetch, query, inspect commands

tests/
├── conftest.py              # ✅ Shared pytest fixtures
├── unit/                    # ✅ Unit tests (exceptions, config, types)
└── integration/             # ✅ Integration tests (config file, foundation)
```

Legend: ✅ Implemented | ⏳ Pending

## Key Design Decisions

- **Explicit table management**: Tables never implicitly overwritten; `TableExistsError` if exists
- **Streaming ingestion**: API returns iterators, storage accepts iterators (memory efficient)
- **JSON property storage**: Properties stored as JSON columns, queried with `properties->>'$.field'`
- **Immutable credentials**: Resolved once at Workspace construction
- **Dependency injection**: Services accept dependencies as constructor arguments for testing

## Mixpanel API Reference

Complete API documentation in `docs/api-docs/`:
- **Event Export API** — Raw event fetching for local storage
- **Query API** — Segmentation, funnels, retention, JQL
- **Lexicon Schemas API** — Event/property discovery

OpenAPI specs: `docs/api-docs/openapi/src/*.openapi.yaml`

## Environment Variables

| Variable | Purpose |
|----------|---------|
| `MP_USERNAME` | Service account username |
| `MP_SECRET` | Service account secret |
| `MP_PROJECT_ID` | Project ID |
| `MP_REGION` | Data residency (us, eu, in) |
| `MP_CONFIG_PATH` | Override config file location |

Config file: `~/.mp/config.toml`

## Implementation Phases

**Master Plan:** [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md)

| Phase | Name | Status | Branch |
|-------|------|--------|--------|
| 001 | Foundation Layer | ✅ Complete | `001-foundation-layer` |
| 002 | API Client | ✅ Complete | `002-api-client` |
| 003 | Storage Engine | ✅ Complete | `003-storage-engine` |
| 004 | Discovery Service | ✅ Complete | `004-discovery-service` |
| 005 | Fetch Service | ⏳ Next | `005-fetch-service` |
| 006 | Live Queries | ⏳ Pending | `006-live-queries` |
| 007 | Workspace Facade | ⏳ Pending | `007-workspace` |
| 008 | CLI Application | ⏳ Pending | `008-cli` |
| 009 | Polish & Release | ⏳ Pending | `009-polish` |

**Next up:** Phase 005 (Fetch Service) - implements `FetcherService` for fetching and storing events/profiles in DuckDB.

## What's Implemented

### Exceptions (`exceptions.py`)
- `MixpanelDataError` — Base exception with `code`, `message`, `details`, `to_dict()`
- Config: `ConfigError`, `AccountNotFoundError`, `AccountExistsError`
- API: `AuthenticationError`, `RateLimitError`, `QueryError`
- Storage: `TableExistsError`, `TableNotFoundError`

### Configuration (`_internal/config.py`, `auth.py`)
- `Credentials` — Frozen Pydantic model with SecretStr for secrets
- `ConfigManager` — TOML-based account management at `~/.mp/config.toml`
- Credential resolution: env vars → named account → default account
- Account CRUD: `add_account()`, `remove_account()`, `set_default()`, `list_accounts()`

### API Client (`_internal/api_client.py`)
- `MixpanelAPIClient` — HTTP client with service account authentication
- Regional endpoint routing (US, EU, India) for query and export APIs
- Automatic rate limit handling with exponential backoff and jitter
- Streaming JSONL parsing for large exports (memory efficient)
- Low-level HTTP methods: `get()`, `post()`
- Export APIs: `export_events()`, `export_profiles()` (streaming iterators)
- Discovery APIs: `get_events()`, `get_event_properties()`, `get_property_values()`
- Query APIs: `segmentation()`, `funnel()`, `retention()`, `jql()` (raw responses)

### Result Types (`types.py`)
All frozen dataclasses with lazy `.df` property and `.to_dict()` method:
- `FetchResult` — Events/profiles fetch results
- `SegmentationResult` — Time-series segmentation data
- `FunnelResult`, `FunnelStep` — Funnel conversion data
- `RetentionResult`, `CohortInfo` — Cohort retention data
- `JQLResult` — Custom JQL query results
- `TableMetadata` — Fetch operation metadata
- `TableInfo` — Table summary (name, type, row count, fetched_at)
- `ColumnInfo` — Column definition (name, type, nullable, primary_key)
- `TableSchema` — Complete table schema with columns

### Storage Engine (`_internal/storage.py`)
- `StorageEngine` — DuckDB-based storage with persistent and ephemeral modes
- Database lifecycle: `__init__()`, `ephemeral()`, `open_existing()`, `close()`, `cleanup()`
- Table creation: `create_events_table()`, `create_profiles_table()` with streaming batch ingestion
- Query execution: `execute()`, `execute_df()`, `execute_scalar()`, `execute_rows()`
- Introspection: `list_tables()`, `get_schema()`, `get_metadata()`, `table_exists()`
- Table management: `drop_table()` with metadata cleanup
- Context manager support for resource cleanup

### Discovery Service (`_internal/services/discovery.py`)
- `DiscoveryService` — Schema introspection with session-scoped caching
- `list_events()` — List all event names (sorted alphabetically, cached)
- `list_properties(event)` — List properties for an event (sorted, cached per event)
- `list_property_values(property, event, limit)` — Sample values for a property (cached)
- `clear_cache()` — Clear all cached discovery results
- Constructor injection of `MixpanelAPIClient` for testing

### Tests
- Unit tests for exceptions, config, types, storage, discovery
- Integration tests for config file CRUD, foundation layer, storage engine
- Requires Python 3.11+ (use devcontainer or pyenv)

## Development Commands

This project uses [just](https://github.com/casey/just) as a command runner. Run `just` to see all available commands.

| Command | Description |
|---------|-------------|
| `just` | List all available commands |
| `just check` | Run all checks (lint, typecheck, test) |
| `just test` | Run tests (supports args: `just test -k foo`) |
| `just test-cov` | Run tests with coverage |
| `just lint` | Lint code with ruff |
| `just lint-fix` | Auto-fix lint errors |
| `just fmt` | Format code with ruff |
| `just typecheck` | Type check with mypy |
| `just sync` | Sync dependencies |
| `just clean` | Remove caches and build artifacts |
| `just build` | Build package |

## Development Environment

**Recommended:** Use the devcontainer (Python 3.11, uv, just, Claude Code pre-installed)

```bash
# See all available commands
just

# Run all checks before committing
just check

# Run specific tests
just test -k test_name

# Format and lint
just fmt && just lint
```

## Recent Changes
- 005-fetch-service: Added Python 3.11+ (type hints throughout per constitution) + httpx (HTTP), DuckDB (storage), Pydantic v2 (validation)
- Added `just` command runner with justfile for common development tasks
- 004-discovery-service: Added Python 3.11+ + httpx (via MixpanelAPIClient from Phase 002)

## Active Technologies
- Python 3.11+ (type hints throughout per constitution) + httpx (HTTP), DuckDB (storage), Pydantic v2 (validation) (005-fetch-service)
- DuckDB (embedded analytical database, per constitution) (005-fetch-service)
