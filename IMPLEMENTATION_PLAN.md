# mixpanel_data — Master Implementation Plan

> Definitive multi-phase implementation roadmap for spec-driven development.

**Version:** 1.0
**Created:** 2024-12-20
**Status:** Active
**Constitution:** [docs/mixpanel_data-design.md](docs/mixpanel_data-design.md)

---

## Overview

This document defines the complete implementation roadmap for `mixpanel_data`, organized into discrete phases that build upon each other. Each phase produces independently testable, shippable components.

### Implementation Philosophy

1. **Spec-Driven**: Each phase gets a full spec in `specs/XXX-phase-name/` before implementation
2. **Test-First**: Write contracts and tests before implementation code
3. **Dependency Order**: Each phase depends only on completed phases
4. **Atomic Deliverables**: Each phase produces working, tested functionality
5. **Constitution Compliance**: Every phase validates against design principles

### Phase Dependencies

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                                                                             │
│  ┌──────────────────┐                                                       │
│  │  001-Foundation  │ ✅ COMPLETE                                            │
│  │  (Exceptions,    │                                                       │
│  │   Types, Config) │                                                       │
│  └────────┬─────────┘                                                       │
│           │                                                                 │
│           ▼                                                                 │
│  ┌──────────────────┐                                                       │
│  │  002-API-Client  │ ✅ COMPLETE                                            │
│  │  (HTTP, Auth,    │                                                       │
│  │   Rate Limiting) │                                                       │
│  └────────┬─────────┘                                                       │
│           │                                                                 │
│           ├──────────────────────────────┐                                  │
│           ▼                              ▼                                  │
│  ┌──────────────────┐           ┌──────────────────┐                        │
│  │  003-Storage     │           │  004-Discovery   │                        │
│  │  (DuckDB,        │           │  (Event/Property │                        │
│  │   Schema, I/O)   │ ✅         │   Introspection) │ ✅                      │
│  └────────┬─────────┘           └────────┬─────────┘                        │
│           │                              │                                  │
│           └──────────────┬───────────────┘                                  │
│                          ▼                                                  │
│                 ┌──────────────────┐                                        │
│                 │  005-Fetch       │ ✅                                      │
│                 │  (Events,        │                                        │
│                 │   Profiles)      │                                        │
│                 └────────┬─────────┘                                        │
│                          │                                                  │
│           ┌──────────────┼──────────────┐                                   │
│           ▼              ▼              ▼                                   │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐                         │
│  │ 006-Live     │ │ 007-Workspace│ │              │                         │
│  │ Queries      │ │ (Facade,     │ │ 008-CLI      │                         │
│  │ (Seg/Funnel/ │ │  Lifecycle)  │ │ (Typer App)  │                         │
│  │  Retention)  │ │              │ │              │                         │
│  └──────────────┘ └──────────────┘ └──────┬───────┘                         │
│                          │                │                                 │
│                          └────────────────┤                                 │
│                                           ▼                                 │
│                                  ┌──────────────────┐                       │
│                                  │  009-Polish      │                       │
│                                  │  (SKILL.md,      │                       │
│                                  │   Docs, PyPI)    │                       │
│                                  └──────────────────┘                       │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Phase Summary

| Phase | Name | Components | Status | Branch |
|-------|------|------------|--------|--------|
| 001 | Foundation Layer | Exceptions, Types, ConfigManager, Auth | ✅ Complete | `001-foundation-layer` |
| 002 | API Client | MixpanelAPIClient, HTTP, Rate Limiting | ✅ Complete | `002-api-client` |
| 003 | Storage Engine | StorageEngine, DuckDB, Schema Management | ✅ Complete | `003-storage-engine` |
| 004 | Discovery Service | DiscoveryService, Event/Property APIs | ✅ Complete | `004-discovery-service` |
| 005 | Fetch Service | FetcherService, Events/Profiles Export | ✅ Complete | `005-fetch-service` |
| 006 | Live Queries | LiveQueryService, Segmentation, Funnels, Retention | ⏳ Next | `006-live-queries` |
| 007 | Workspace Facade | Workspace class, Lifecycle Management | ⏳ Pending | `007-workspace` |
| 008 | CLI Application | Typer app, Commands, Formatters | ⏳ Pending | `008-cli` |
| 009 | Polish & Release | SKILL.md, Documentation, PyPI | ⏳ Pending | `009-polish` |

---

## Phase 001: Foundation Layer ✅

**Status:** COMPLETE
**Branch:** `001-foundation-layer`
**Spec:** [specs/001-foundation-layer/](specs/001-foundation-layer/)

### Delivered Components

| Component | Location | Description |
|-----------|----------|-------------|
| Exceptions | `src/mixpanel_data/exceptions.py` | 9 exception classes with hierarchy |
| Types | `src/mixpanel_data/types.py` | Result dataclasses with lazy DataFrame |
| ConfigManager | `src/mixpanel_data/_internal/config.py` | TOML-based credential storage |
| Auth Module | `src/mixpanel_data/auth.py` | Public auth API |

### Key Deliverables

- [x] Exception hierarchy: `MixpanelDataError` → Config/API/Storage exceptions
- [x] Result types: `FetchResult`, `SegmentationResult`, `FunnelResult`, `RetentionResult`, `JQLResult`
- [x] Credentials resolution: env vars → named account → default account
- [x] Account CRUD: add, remove, list, set_default, get
- [x] Unit tests: 90%+ coverage
- [x] Integration tests: config file I/O

---

## Phase 002: API Client ✅

**Status:** COMPLETE
**Branch:** `002-api-client`
**Dependencies:** Phase 001

### Overview

The `MixpanelAPIClient` provides HTTP communication with Mixpanel APIs including authentication, regional endpoint routing, rate limiting, and response parsing. It has no knowledge of local storage.

### Key Deliverables

- [x] HTTP client with httpx supporting GET/POST methods
- [x] Service account authentication via HTTP Basic auth
- [x] Regional endpoint routing (US, EU, India) for query and export APIs
- [x] Automatic rate limit handling with exponential backoff and jitter
- [x] Streaming JSONL parsing for memory-efficient large exports
- [x] Export API methods: `export_events()`, `export_profiles()` (streaming iterators)
- [x] Discovery API methods: `get_events()`, `get_event_properties()`, `get_property_values()`
- [x] Query API methods: `segmentation()`, `funnel()`, `retention()`, `jql()`
- [x] Comprehensive error mapping: 401→AuthenticationError, 429→RateLimitError, 400→QueryError
- [x] Unit tests with 90%+ coverage
- [x] Integration tests with rate limiting behavior
- [x] Context manager support for resource cleanup

### Components to Build

| Component | Location | Description |
|-----------|----------|-------------|
| MixpanelAPIClient | `src/mixpanel_data/_internal/api_client.py` | Core HTTP client |
| Endpoint Router | (within api_client.py) | Regional URL resolution |
| Rate Limiter | (within api_client.py) | Exponential backoff with jitter |

### Design Reference

From [docs/mixpanel_data-design.md](docs/mixpanel_data-design.md):

```python
class MixpanelAPIClient:
    def __init__(self, credentials: Credentials): ...

    # Low-level HTTP
    def get(self, endpoint: str, params: dict | None = None) -> Any: ...
    def post(self, endpoint: str, data: dict | None = None) -> Any: ...

    # Export API (streaming)
    def export_events(...) -> Iterator[dict]: ...
    def export_profiles(...) -> Iterator[dict]: ...

    # Discovery APIs
    def get_events(self) -> list[str]: ...
    def get_event_properties(self, event: str) -> list[str]: ...
    def get_property_values(self, event: str, prop: str, limit: int) -> list[str]: ...

    # Query APIs
    def segmentation(...) -> dict: ...
    def funnel(...) -> dict: ...
    def retention(...) -> dict: ...
    def jql(self, script: str, params: dict | None = None) -> list: ...
```

### Regional Endpoints

| Region | Query | Export |
|--------|-------|--------|
| US | `mixpanel.com/api` | `data.mixpanel.com` |
| EU | `eu.mixpanel.com/api` | `data-eu.mixpanel.com` |
| India | `in.mixpanel.com/api` | `data-in.mixpanel.com` |

### User Stories

1. **Make authenticated API requests** (P1)
   - Use service account credentials
   - Handle regional endpoints
   - Parse responses, raise appropriate exceptions

2. **Handle rate limiting gracefully** (P1)
   - Detect 429 responses
   - Implement exponential backoff with jitter
   - Raise `RateLimitError` when retries exhausted

3. **Stream large exports** (P2)
   - Export API returns JSONL (newline-delimited JSON)
   - Yield events as iterator for memory efficiency
   - Support batched callbacks for progress reporting

### Tasks (Estimated: 35-40)

**Core Client:**
- [ ] Create `MixpanelAPIClient` class with `Credentials` injection
- [ ] Implement `get()` and `post()` methods using httpx
- [ ] Implement regional endpoint routing based on `credentials.region`
- [ ] Implement Basic auth header generation from credentials
- [ ] Implement response parsing (JSON extraction, error detection)

**Rate Limiting:**
- [ ] Implement 429 detection and retry logic
- [ ] Implement exponential backoff with jitter
- [ ] Implement configurable max retries
- [ ] Raise `RateLimitError` with retry_after when exhausted

**Export API:**
- [ ] Implement `export_events()` streaming iterator
- [ ] Handle JSONL response format (one JSON object per line)
- [ ] Support `on_batch` callback for progress
- [ ] Implement `export_profiles()` streaming iterator

**Discovery API:**
- [ ] Implement `get_events()` → list[str]
- [ ] Implement `get_event_properties(event)` → list[str]
- [ ] Implement `get_property_values(event, prop, limit)` → list[str]

**Query API (raw methods):**
- [ ] Implement `segmentation()` → dict (raw API response)
- [ ] Implement `funnel()` → dict (raw API response)
- [ ] Implement `retention()` → dict (raw API response)
- [ ] Implement `jql()` → list (raw API response)

**Error Handling:**
- [ ] Map HTTP 401 → `AuthenticationError`
- [ ] Map HTTP 400 → `QueryError` with details
- [ ] Map HTTP 429 → rate limit retry / `RateLimitError`
- [ ] Map HTTP 5xx → `MixpanelDataError` with retry suggestion

**Testing:**
- [ ] Unit tests with httpx mock transport
- [ ] Rate limiting behavior tests
- [ ] Regional endpoint routing tests
- [ ] Streaming export tests with large payloads
- [ ] Error mapping tests

### Success Criteria

- [ ] All Mixpanel API endpoints accessible via single client
- [ ] Rate limiting transparent to caller (automatic retry)
- [ ] Streaming exports handle 1M+ events without memory issues
- [ ] 90%+ test coverage
- [ ] No credentials appear in logs/errors

---

## Phase 003: Storage Engine ✅

**Status:** COMPLETE
**Branch:** `003-storage-engine`
**Dependencies:** Phase 001

### Overview

The `StorageEngine` manages DuckDB database lifecycle, schema, and query execution. It has no knowledge of Mixpanel APIs.

### Components to Build

| Component | Location | Description |
|-----------|----------|-------------|
| StorageEngine | `src/mixpanel_data/_internal/storage.py` | DuckDB operations |
| TableMetadata | `src/mixpanel_data/_internal/storage.py` | Fetch metadata tracking |

### Design Reference

From [docs/mixpanel_data-design.md](docs/mixpanel_data-design.md):

```python
class StorageEngine:
    def __init__(self, path: Path | None = None): ...

    @classmethod
    def ephemeral(cls) -> StorageEngine: ...

    @classmethod
    def open_existing(cls, path: Path) -> StorageEngine: ...

    # Table management
    def create_events_table(self, name: str, data: Iterator[dict],
                            metadata: TableMetadata) -> int: ...
    def create_profiles_table(self, name: str, data: Iterator[dict],
                              metadata: TableMetadata) -> int: ...
    def drop_table(self, name: str) -> None: ...
    def table_exists(self, name: str) -> bool: ...

    # Query execution
    def execute(self, sql: str) -> duckdb.DuckDBPyRelation: ...
    def execute_df(self, sql: str) -> pd.DataFrame: ...
    def execute_scalar(self, sql: str) -> Any: ...
    def execute_rows(self, sql: str) -> list[tuple]: ...

    # Introspection
    def list_tables(self) -> list[TableInfo]: ...
    def get_schema(self, table: str) -> TableSchema: ...
    def get_metadata(self, table: str) -> TableMetadata: ...

    # Lifecycle
    def close(self) -> None: ...
    def cleanup(self) -> None: ...
```

### Database Schema

**Events Table:**
| Column | Type | Description |
|--------|------|-------------|
| event_name | VARCHAR | Name of the event |
| event_time | TIMESTAMP | When the event occurred |
| distinct_id | VARCHAR | User identifier |
| insert_id | VARCHAR | Unique event identifier |
| properties | JSON | All event properties |

**Profiles Table:**
| Column | Type | Description |
|--------|------|-------------|
| distinct_id | VARCHAR | User identifier |
| properties | JSON | All profile properties |
| last_seen | TIMESTAMP | Last activity timestamp |

**Metadata Table (`_metadata`):**
| Column | Type | Description |
|--------|------|-------------|
| table_name | VARCHAR | Name of fetched table |
| type | VARCHAR | "events" or "profiles" |
| fetched_at | TIMESTAMP | When fetch occurred |
| from_date | DATE | Start of date range |
| to_date | DATE | End of date range |
| row_count | INTEGER | Number of rows |

### User Stories

1. **Create and manage database files** (P1)
   - Persistent databases at configurable paths
   - Ephemeral databases auto-deleted on exit
   - Open existing databases for query-only access

2. **Store and query event data** (P1)
   - Batch insert events from iterator (streaming ingest)
   - Query with SQL, return DataFrames
   - Track fetch metadata

3. **Introspect database contents** (P2)
   - List all tables with row counts
   - Get table schema
   - Get fetch metadata (date ranges, filters used)

### Delivered Components

| Component | Location | Description |
|-----------|----------|-------------|
| StorageEngine | `src/mixpanel_data/_internal/storage.py` | DuckDB operations |
| TableMetadata | `src/mixpanel_data/types.py` | Fetch metadata tracking |
| TableInfo | `src/mixpanel_data/types.py` | Table summary information |
| ColumnInfo | `src/mixpanel_data/types.py` | Column schema definition |
| TableSchema | `src/mixpanel_data/types.py` | Complete table schema |

### Key Deliverables

- [x] Create `StorageEngine` class with DuckDB connection
- [x] Implement path resolution (default: `~/.mixpanel_data/{project_id}.db`)
- [x] Implement `ephemeral()` classmethod with temp file cleanup
- [x] Implement `open_existing()` classmethod (no credentials needed)
- [x] Implement `close()` and context manager protocol
- [x] Implement events table creation with schema
- [x] Implement profiles table creation with schema
- [x] Implement `_metadata` table creation
- [x] Implement `table_exists()` check
- [x] Implement `drop_table()` with metadata cleanup
- [x] Implement `create_events_table()` with streaming batch inserts
- [x] Implement `create_profiles_table()` with streaming batch inserts
- [x] Implement metadata recording on table creation
- [x] Raise `TableExistsError` if table already exists
- [x] Implement `execute()` returning DuckDB relation
- [x] Implement `execute_df()` returning pandas DataFrame
- [x] Implement `execute_scalar()` for single values
- [x] Implement `execute_rows()` for list of tuples
- [x] Wrap SQL errors in `QueryError`
- [x] Implement `list_tables()` → list[TableInfo]
- [x] Implement `get_schema()` → TableSchema
- [x] Implement `get_metadata()` → TableMetadata
- [x] Implement cleanup for ephemeral databases (atexit handler)
- [x] Implement WAL file cleanup
- [x] Unit tests for all methods
- [x] Integration tests with actual DuckDB files
- [x] Large dataset ingestion tests (memory efficiency)
- [x] Ephemeral cleanup tests

---

## Phase 004: Discovery Service ✅

**Status:** COMPLETE
**Branch:** `004-discovery-service`
**Dependencies:** Phase 002 (API Client)
**Spec:** [specs/004-discovery-service/](specs/004-discovery-service/)

### Overview

The `DiscoveryService` retrieves schema information from Mixpanel—event names, properties, and sample values. This enables agents to understand data shape before querying.

### Delivered Components

| Component | Location | Description |
|-----------|----------|-------------|
| DiscoveryService | `src/mixpanel_data/_internal/services/discovery.py` | Schema discovery with caching |
| Unit Tests | `tests/unit/test_discovery.py` | 18 tests with mocked API client |

### Key Deliverables

- [x] Create `DiscoveryService` class with API client injection
- [x] Implement `list_events()` with alphabetical sorting and caching
- [x] Implement `list_properties(event)` with per-event caching
- [x] Implement `list_property_values(property, event, limit)` with caching
- [x] Implement `clear_cache()` for manual cache invalidation
- [x] Session-scoped in-memory cache (dict-based)
- [x] Pass-through error handling from API client
- [x] Unit tests with mocked API client (18 tests)
- [x] mypy --strict passes
- [x] ruff check passes

### Success Criteria

- [x] All discovery methods return sorted lists (events and properties)
- [x] Caching reduces duplicate API calls
- [x] 100% test coverage for DiscoveryService

---

## Phase 005: Fetch Service ✅

**Status:** COMPLETE
**Branch:** `005-fetch-service`
**Dependencies:** Phase 002 (API Client), Phase 003 (Storage)

### Overview

The `FetcherService` coordinates data fetches from the Mixpanel Export API into local DuckDB storage. It bridges the API client and storage engine.

### Delivered Components

| Component | Location | Description |
|-----------|----------|-------------|
| FetcherService | `src/mixpanel_data/_internal/services/fetcher.py` | Fetch orchestration |
| Unit Tests | `tests/unit/test_fetcher_service.py` | Tests with mocked dependencies |

### Key Deliverables

- [x] Create `FetcherService` class with dependency injection
- [x] Implement `fetch_events()` orchestration with streaming transformation
- [x] Wire API client streaming → storage engine ingestion (memory efficient)
- [x] Implement progress callback integration for monitoring
- [x] Implement `fetch_profiles()` orchestration
- [x] Event transformation: API format → storage format (extract distinct_id, event_time, insert_id)
- [x] Profile transformation: API format → storage format (extract distinct_id, last_seen)
- [x] Generate UUID for events missing $insert_id
- [x] Return `FetchResult` with table name, row count, duration, and metadata
- [x] Unit tests with mocked API client and storage engine
- [x] mypy --strict passes
- [x] ruff check passes

### Success Criteria

- [x] Streaming fetch handles large datasets (iterator-based, no memory accumulation)
- [x] Progress callbacks fire during fetch
- [x] FetchResult includes accurate timing
- [x] TableExistsError raised if table exists

---

## Phase 006: Live Query Service ⏳

**Status:** PENDING
**Branch:** `006-live-queries`
**Dependencies:** Phase 002 (API Client)

### Overview

The `LiveQueryService` executes queries directly against Mixpanel's Query API and transforms results into structured types. No local storage involved.

### Components to Build

| Component | Location | Description |
|-----------|----------|-------------|
| LiveQueryService | `src/mixpanel_data/_internal/services/live_query.py` | Query execution |

### Design Reference

```python
class LiveQueryService:
    def __init__(self, api_client: MixpanelAPIClient): ...

    def segmentation(
        self,
        event: str,
        from_date: str,
        to_date: str,
        on: str | None = None,
        unit: str = "day",
        where: str | None = None
    ) -> SegmentationResult: ...

    def funnel(
        self,
        funnel_id: int,
        from_date: str,
        to_date: str,
        unit: str = "day",
        on: str | None = None
    ) -> FunnelResult: ...

    def retention(
        self,
        born_event: str,
        return_event: str,
        from_date: str,
        to_date: str,
        born_where: str | None = None,
        return_where: str | None = None,
        interval: int = 1,
        interval_count: int = 10,
        unit: str = "day"
    ) -> RetentionResult: ...

    def jql(self, script: str, params: dict | None = None) -> JQLResult: ...
```

### User Stories

1. **Run segmentation queries** (P1)
   - Event counts over time
   - Segment by property
   - Return structured result with DataFrame

2. **Run funnel analysis** (P1)
   - Analyze saved funnels
   - Get step-by-step conversion

3. **Run retention analysis** (P2)
   - Cohort-based retention
   - Multiple time units

4. **Run custom JQL queries** (P3)
   - Execute arbitrary JQL
   - Return raw + DataFrame

### Tasks (Estimated: 25-30)

- [ ] Create `LiveQueryService` class
- [ ] Implement `segmentation()` with API call and result transformation
- [ ] Transform segmentation response → `SegmentationResult`
- [ ] Implement `funnel()` with API call and result transformation
- [ ] Transform funnel response → `FunnelResult`
- [ ] Implement `retention()` with all parameters
- [ ] Transform retention response → `RetentionResult`
- [ ] Implement `jql()` with script execution
- [ ] Transform JQL response → `JQLResult`
- [ ] Unit tests with mocked API responses

### Success Criteria

- [ ] All result types have accurate data
- [ ] DataFrames have expected columns and types
- [ ] API errors wrapped in appropriate exceptions

---

## Phase 007: Workspace Facade ⏳

**Status:** PENDING
**Branch:** `007-workspace`
**Dependencies:** Phases 002-006 (all services)

### Overview

The `Workspace` class is the primary entry point—a facade that orchestrates all services and provides the unified public API.

### Components to Build

| Component | Location | Description |
|-----------|----------|-------------|
| Workspace | `src/mixpanel_data/workspace.py` | Facade class |

### Design Reference

```python
class Workspace:
    def __init__(
        self,
        account: str | None = None,
        project_id: str | None = None,
        region: str | None = None,
        path: str | Path | None = None,
        # Dependency injection for testing
        _config_manager: ConfigManager | None = None,
        _api_client: MixpanelAPIClient | None = None,
        _storage: StorageEngine | None = None,
    ): ...

    @classmethod
    def ephemeral(cls, ...) -> ContextManager[Workspace]: ...

    @classmethod
    def open(cls, path: str | Path) -> Workspace: ...

    # Discovery (delegates to DiscoveryService)
    def events(self) -> list[str]: ...
    def properties(self, event: str) -> list[str]: ...
    def property_values(self, event: str, prop: str, limit: int = 100) -> list[str]: ...

    # Fetching (delegates to FetcherService)
    def fetch_events(self, name: str = "events", ...) -> FetchResult: ...
    def fetch_profiles(self, name: str = "profiles", ...) -> FetchResult: ...

    # Local Queries (delegates to StorageEngine)
    def sql(self, query: str) -> pd.DataFrame: ...
    def sql_scalar(self, query: str) -> Any: ...
    def sql_rows(self, query: str) -> list[tuple]: ...

    # Live Queries (delegates to LiveQueryService)
    def segmentation(self, ...) -> SegmentationResult: ...
    def funnel(self, ...) -> FunnelResult: ...
    def retention(self, ...) -> RetentionResult: ...
    def jql(self, script: str, params: dict | None = None) -> JQLResult: ...

    # Introspection
    def info(self) -> WorkspaceInfo: ...
    def tables(self) -> list[TableInfo]: ...
    def schema(self, table: str) -> TableSchema: ...

    # Table Management
    def drop(self, *names: str) -> None: ...
    def drop_all(self, type: str | None = None) -> None: ...

    # Escape Hatches
    @property
    def connection(self) -> duckdb.DuckDBPyConnection: ...
    @property
    def api(self) -> MixpanelAPIClient: ...
```

### User Stories

1. **Create workspace from credentials** (P1)
   - Resolve credentials from config/env
   - Initialize API client and storage

2. **Use ephemeral workspace** (P1)
   - Temporary database auto-cleaned
   - Context manager pattern

3. **Open existing database** (P2)
   - Query-only access without credentials

### Tasks (Estimated: 35-40)

- [ ] Create `Workspace` class with DI
- [ ] Implement credential resolution and service wiring
- [ ] Implement `ephemeral()` context manager
- [ ] Implement `open()` for existing databases
- [ ] Delegate discovery methods to DiscoveryService
- [ ] Delegate fetch methods to FetcherService
- [ ] Delegate SQL methods to StorageEngine
- [ ] Delegate live query methods to LiveQueryService
- [ ] Implement introspection methods
- [ ] Implement table management methods
- [ ] Implement escape hatch properties
- [ ] Update `__init__.py` with Workspace export
- [ ] Comprehensive integration tests
- [ ] End-to-end workflow tests

### Success Criteria

- [ ] Single Workspace object provides all functionality
- [ ] Credentials resolved once at construction
- [ ] Ephemeral workspaces always cleaned up
- [ ] All methods documented with examples
- [ ] Integration tests cover full workflows

---

## Phase 008: CLI Application ⏳

**Status:** PENDING
**Branch:** `008-cli`
**Dependencies:** Phase 007 (Workspace)

### Overview

The CLI is a thin wrapper over the library using Typer. Every command maps directly to library methods.

### Components to Build

| Component | Location | Description |
|-----------|----------|-------------|
| Main App | `src/mixpanel_data/cli/main.py` | Typer app entry |
| Auth Commands | `src/mixpanel_data/cli/commands/auth.py` | `mp auth *` |
| Fetch Commands | `src/mixpanel_data/cli/commands/fetch.py` | `mp fetch *` |
| Query Commands | `src/mixpanel_data/cli/commands/query.py` | `mp sql`, `mp segmentation`, etc. |
| Inspect Commands | `src/mixpanel_data/cli/commands/inspect.py` | `mp events`, `mp tables`, etc. |
| Formatters | `src/mixpanel_data/cli/formatters/` | JSON, Table, CSV output |

### Command Groups

| Group | Commands |
|-------|----------|
| `mp auth` | `list`, `add`, `remove`, `switch`, `show`, `test` |
| `mp fetch` | `events`, `profiles` |
| `mp` (query) | `sql`, `segmentation`, `funnel`, `retention`, `jql` |
| `mp` (inspect) | `events`, `properties`, `values`, `info`, `tables`, `schema`, `drop` |

### User Stories

1. **Manage authentication** (P1)
   - Add/remove/switch accounts
   - Test credentials

2. **Fetch data** (P1)
   - Fetch events with date range and filters
   - Show progress bars

3. **Query data** (P1)
   - Execute SQL queries
   - Run live Mixpanel queries

4. **Inspect data** (P2)
   - List events, properties, values
   - Show table info and schema

### Tasks (Estimated: 45-50)

**Setup:**
- [ ] Create `cli/main.py` with Typer app
- [ ] Register entry point in `pyproject.toml`
- [ ] Create command group structure

**Auth Commands:**
- [ ] Implement `mp auth list`
- [ ] Implement `mp auth add` with options
- [ ] Implement `mp auth remove`
- [ ] Implement `mp auth switch`
- [ ] Implement `mp auth show`
- [ ] Implement `mp auth test`

**Fetch Commands:**
- [ ] Implement `mp fetch events` with progress bar
- [ ] Implement `mp fetch profiles` with progress bar

**Query Commands:**
- [ ] Implement `mp sql` with format options
- [ ] Implement `mp segmentation`
- [ ] Implement `mp funnel`
- [ ] Implement `mp retention`
- [ ] Implement `mp jql`

**Inspect Commands:**
- [ ] Implement `mp events`
- [ ] Implement `mp properties`
- [ ] Implement `mp values`
- [ ] Implement `mp info`
- [ ] Implement `mp tables`
- [ ] Implement `mp schema`
- [ ] Implement `mp drop`

**Formatters:**
- [ ] Implement JSON formatter
- [ ] Implement Table formatter (Rich)
- [ ] Implement CSV formatter
- [ ] Implement JSONL formatter

**Polish:**
- [ ] Global options: `--account`, `--format`, `--quiet`, `--verbose`
- [ ] Error handling with exit codes
- [ ] Help text for all commands
- [ ] Shell completion generation

### Success Criteria

- [ ] All commands exit with documented codes
- [ ] Data goes to stdout, status to stderr
- [ ] Progress bars work in interactive mode
- [ ] All output formats work correctly
- [ ] `--help` on every command

---

## Phase 009: Polish & Release ⏳

**Status:** PENDING
**Branch:** `009-polish`
**Dependencies:** All previous phases

### Overview

Final polish, documentation, agent skill, and PyPI release.

### Components to Build

| Component | Location | Description |
|-----------|----------|-------------|
| SKILL.md | `docs/SKILL.md` | Agent usage guide |
| README | `README.md` | User documentation |
| API Docs | (generated) | Sphinx/mkdocs |
| PyPI Config | `pyproject.toml` | Release metadata |

### User Stories

1. **AI agents use the library effectively** (P1)
   - SKILL.md teaches patterns and workflows
   - Clear guidance on live vs local paths

2. **Humans can install and use easily** (P1)
   - PyPI package
   - Clear README with examples

### Tasks (Estimated: 25-30)

**Documentation:**
- [ ] Create comprehensive SKILL.md
- [ ] Write README with quick start
- [ ] Add API documentation (docstrings)
- [ ] Create usage examples

**Quality:**
- [ ] Full test coverage audit (90%+ all modules)
- [ ] Type checking passes (mypy --strict)
- [ ] Linting passes (ruff)
- [ ] Security audit (no secrets in code/logs)

**Release:**
- [ ] Version 0.1.0 tagging
- [ ] PyPI metadata in pyproject.toml
- [ ] GitHub Actions CI/CD
- [ ] PyPI publish workflow

### Success Criteria

- [ ] `pip install mixpanel_data` works
- [ ] Agents can follow SKILL.md patterns
- [ ] README enables 5-minute quick start
- [ ] All tests pass in CI

---

## Appendix: Spec-Kit Workflow

Each phase follows this workflow:

### 1. Initialize Phase

```bash
# Create feature branch
git checkout -b XXX-phase-name

# Initialize spec
/speckit init "Phase description"
```

### 2. Write Specification

```bash
/speckit spec
```

Creates:
- User stories with acceptance criteria
- Functional requirements
- Success criteria

### 3. Create Plan

```bash
/speckit plan
```

Creates:
- Technical context
- Constitution check
- Project structure
- Complexity tracking

### 4. Generate Tasks

```bash
/speckit tasks
```

Creates:
- Ordered task list
- Dependency graph
- Effort estimates

### 5. Implement

Execute tasks in order, running tests continuously.

### 6. Verify & Merge

```bash
/speckit analyze  # Cross-artifact consistency
pytest            # All tests pass
# Create PR, merge to main
```

---

## Appendix: Constitution Principles

Every phase must comply with these principles from [docs/mixpanel_data-design.md](docs/mixpanel_data-design.md):

| # | Principle | Requirement |
|---|-----------|-------------|
| I | Library-First | CLI wraps library; every capability accessible programmatically |
| II | Agent-Native | Non-interactive; structured output; composable |
| III | Context Window Efficiency | Fetch once, query many; precise answers; introspection first |
| IV | Two Data Paths | Live queries for quick answers; local for deep analysis |
| V | Explicit Over Implicit | No global state; table creation fails if exists |
| VI | Unix Philosophy | Single purpose; compose with other tools |
| VII | Secure by Default | Credentials in config/env, never in code; secrets redacted |

---

*This is the living implementation plan for mixpanel_data. Update phase statuses as work progresses.*
