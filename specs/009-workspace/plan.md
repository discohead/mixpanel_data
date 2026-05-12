# Implementation Plan: Workspace Facade

**Branch**: `009-workspace` | **Date**: 2025-12-23 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/009-workspace/spec.md`

## Summary

Implement the `Workspace` class as the unified public API facade that orchestrates all existing services (DiscoveryService, FetcherService, LiveQueryService, StorageEngine). The Workspace provides 30+ methods for Mixpanel data operations across 8 categories: lifecycle management, discovery, fetching, local SQL queries, live analytics, introspection, table management, and escape hatches. All underlying services are already implemented; this phase wires them together behind a single entry point with proper credential resolution, context manager support, and dependency injection for testing.

## Technical Context

**Language/Version**: Python 3.10+ (per constitution)
**Primary Dependencies**: DuckDB (storage), httpx (HTTP), Pydantic v2 (validation), Rich (progress bars), pandas (DataFrames)
**Storage**: DuckDB embedded database (persistent or ephemeral modes)
**Testing**: pytest with httpx.MockTransport for API mocking, real DuckDB for integration tests
**Target Platform**: Cross-platform Python library (Linux, macOS, Windows)
**Project Type**: Single Python package with src layout
**Performance Goals**: Fetch-query workflows under 5 minutes for 100k events; immediate response for cached discovery
**Constraints**: No interactive prompts; structured output only; credentials never in logs/output
**Scale/Scope**: 30+ public methods; 8 user stories; 42 functional requirements

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Evidence |
|-----------|--------|----------|
| I. Library-First | PASS | Workspace is the library entry point; CLI (Phase 010) will wrap it |
| II. Agent-Native Design | PASS | No interactive prompts; all methods return structured results; progress to callback |
| III. Context Window Efficiency | PASS | Fetch once → query many times; discovery caching; streaming ingestion |
| IV. Two Data Paths | PASS | Local queries (sql, fetch) + live queries (segmentation, funnel, etc.) |
| V. Explicit Over Implicit | PASS | TableExistsError on duplicate; explicit drop(); immutable credentials |
| VI. Unix Philosophy | PASS | Clean data output; composable results with .df and .to_dict() |
| VII. Secure by Default | PASS | Credentials from config/env only; SecretStr for secrets; no logging of secrets |

**Technology Stack Compliance**:
- [x] Python 3.10+ with type hints throughout
- [x] Pydantic v2 for Credentials model
- [x] DuckDB for local storage (via StorageEngine)
- [x] httpx for HTTP (via MixpanelAPIClient)
- [x] pandas for DataFrame conversion (via result types)
- [x] Rich for progress bars (optional, via progress callbacks)

**Quality Gates**:
- [ ] All public functions have type hints
- [ ] All public functions have docstrings (Google style)
- [ ] All new code passes `ruff check` and `ruff format`
- [ ] All new code passes `mypy --strict`
- [ ] Tests exist for new functionality (pytest)

## Project Structure

### Documentation (this feature)

```text
specs/009-workspace/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output (Python API contracts)
└── tasks.md             # Phase 2 output (/speckit.tasks command)
```

### Source Code (repository root)

```text
src/mixpanel_data/
├── __init__.py              # Public API exports (add Workspace, WorkspaceInfo)
├── workspace.py             # NEW: Workspace facade class
├── auth.py                  # Public auth module (existing)
├── exceptions.py            # All exception classes (existing)
├── types.py                 # Result types, dataclasses (existing, WorkspaceInfo exists)
├── py.typed                 # PEP 561 marker (existing)
└── _internal/               # Private implementation (existing)
    ├── __init__.py
    ├── config.py            # ConfigManager, Credentials (existing)
    ├── api_client.py        # MixpanelAPIClient (existing)
    ├── storage.py           # StorageEngine (existing)
    └── services/
        ├── __init__.py
        ├── discovery.py     # DiscoveryService (existing)
        ├── fetcher.py       # FetcherService (existing)
        └── live_query.py    # LiveQueryService (existing)

tests/
├── conftest.py              # Shared fixtures (existing)
├── unit/
│   ├── test_workspace.py    # NEW: Unit tests for Workspace
│   └── ... (existing tests)
└── integration/
    ├── test_workspace_integration.py  # NEW: Integration tests
    └── ... (existing tests)
```

**Structure Decision**: Single Python package following existing src layout. New file `workspace.py` at package root. All services already exist in `_internal/services/`. Tests follow existing pattern with unit/ and integration/ separation.

## Complexity Tracking

> No constitution violations. All patterns align with established architecture.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| (none) | - | - |

---

## Phase 0: Research Summary

See [research.md](research.md) for detailed findings.

### Key Decisions

All technology and pattern decisions are pre-established by the constitution and existing codebase:

1. **Credential Resolution**: Priority order (env → named account → default) already implemented in ConfigManager
2. **Service Orchestration**: Dependency injection pattern already used by all services
3. **Context Manager**: Pattern already implemented in StorageEngine
4. **Progress Callbacks**: Pattern already used by FetcherService
5. **Result Types**: All types already defined in types.py (including WorkspaceInfo)

### Unknowns Resolved

| Unknown | Resolution | Source |
|---------|------------|--------|
| How to handle opened workspaces without credentials? | Store optional api_client; raise error on API methods | Design decision |
| Should ephemeral() be classmethod or contextmanager? | Both - classmethod returning context manager | Python best practice |
| Progress bar implementation | Use Rich progress bar via callback adapter | Constitution (Rich required) |

---

## Phase 1: Design Artifacts

### Data Model

See [data-model.md](data-model.md) for complete entity definitions.

**Key Entities**:
- `Workspace` - Facade class holding credentials, services, and storage
- `WorkspaceInfo` - Immutable metadata returned by info() (already in types.py)
- `Credentials` - Immutable auth details (already in _internal/config.py)

### API Contracts

See [contracts/](contracts/) for Python interface definitions.

**Method Categories**:
1. Lifecycle (7): `__init__`, `ephemeral()`, `open()`, `__enter__`, `__exit__`, `close()`
2. Discovery (7): `events()`, `properties()`, `property_values()`, `funnels()`, `cohorts()`, `top_events()`, `clear_discovery_cache()`
3. Fetching (2): `fetch_events()`, `fetch_profiles()`
4. Local Queries (3): `sql()`, `sql_scalar()`, `sql_rows()`
5. Live Queries (12): All LiveQueryService methods delegated
6. Introspection (3): `info()`, `tables()`, `schema()`
7. Table Management (2): `drop()`, `drop_all()`
8. Escape Hatches (2): `connection`, `api` properties

### Quickstart

See [quickstart.md](quickstart.md) for usage examples.
