# Implementation Plan: Storage Engine

**Branch**: `003-storage-engine` | **Date**: 2025-12-21 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/003-storage-engine/spec.md`

**Note**: This plan provides implementation guidance for the Storage Engine component of mixpanel_data.

## Summary

The Storage Engine provides DuckDB-based local storage for Mixpanel events and profiles, enabling memory-efficient data ingestion, persistent querying, and ephemeral analysis workflows. It implements three core capabilities:

1. **Persistent Storage**: Database files that survive sessions, supporting repeated queries without API re-fetches
2. **Streaming Ingestion**: Memory-efficient batch inserts handling 1M+ events within 500MB memory
3. **Ephemeral Workflows**: Auto-cleanup temporary databases for one-off analysis

Technical approach leverages DuckDB's embedded analytical database with JSON column support, pandas DataFrame integration, and Python's context manager protocol for resource cleanup.

## Technical Context

**Language/Version**: Python 3.10+ (matches project requirement)
**Primary Dependencies**: DuckDB 1.0+, pandas 2.0+, Pydantic 2.0 (for TableMetadata validation)
**Storage**: DuckDB embedded database (single-file, serverless, ACID-compliant)
**Testing**: pytest (unit + integration), pytest-cov (coverage tracking), memory_profiler (memory benchmarks)
**Target Platform**: Cross-platform (Linux, macOS, Windows) - DuckDB is platform-agnostic
**Project Type**: Single library (`src/mixpanel_data/_internal/storage.py`)
**Performance Goals**: Ingest 1M events with peak memory <500MB, batch insert 1000-5000 rows/batch
**Constraints**: Ephemeral cleanup 100% reliable (atexit handlers), streaming-only ingestion (no in-memory buffering), TableExistsError on duplicates
**Scale/Scope**: Internal library component serving FetcherService and Workspace facade

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

### Principle I: Library-First ✅ PASS

- StorageEngine is a pure library component (`_internal/storage.py`)
- All methods programmatically accessible before CLI exposure
- CLI will delegate to Workspace, which delegates to StorageEngine
- Full type hints and docstrings required per quality gates

### Principle II: Agent-Native Design ✅ PASS

- No interactive operations - all methods are deterministic functions
- Error conditions raise typed exceptions (TableExistsError, QueryError, TableNotFoundError)
- Query results return structured data (DataFrames, scalars, tuples)
- Progress callbacks are optional and non-blocking

### Principle III: Context Window Efficiency ✅ PASS

- **Core purpose**: Enable "fetch once, query many times" pattern
- Introspection methods (`list_tables()`, `get_schema()`, `get_metadata()`) support agent discovery
- Streaming ingestion prevents large datasets from consuming agent context
- Query execution returns precise results, not raw database dumps

### Principle IV: Two Data Paths ✅ PASS

- StorageEngine implements the **local analysis path**
- Works in coordination with LiveQueryService (handles live queries)
- Both paths share Credentials from ConfigManager
- Users choose path via Workspace methods (`fetch_events()` vs `segmentation()`)

### Principle V: Explicit Over Implicit ✅ PASS

- **Critical requirement**: `create_events_table()` raises `TableExistsError` if table exists
- No implicit overwrites - users must call `drop_table()` first
- `table_exists()` method enables explicit checking before creation
- Metadata immutable once created (stored in `_metadata` table)

### Principle VI: Unix Philosophy ✅ PASS

- Does one thing: DuckDB database operations
- No awareness of Mixpanel API (accepts generic iterators)
- No awareness of higher-level services (FetcherService provides data, not StorageEngine)
- Composable: accepts iterators, returns standard Python types (DataFrames, lists, scalars)

### Principle VII: Secure by Default ⚠️ N/A

- Storage layer does not handle credentials (ConfigManager responsibility)
- Database files stored unencrypted (documented in spec as out of scope)
- Future enhancement: encryption at rest (not blocking for this phase)

**Gate Status**: ✅ PASSED - All applicable principles satisfied

## Project Structure

### Documentation (this feature)

```text
specs/003-storage-engine/
├── spec.md              # Feature specification (completed)
├── plan.md              # This file (implementation plan)
├── research.md          # Phase 0 output (DuckDB patterns, cleanup strategies)
├── data-model.md        # Phase 1 output (table schemas, data structures)
├── quickstart.md        # Phase 1 output (API usage examples)
├── contracts/           # Phase 1 output (type definitions, interfaces)
│   ├── storage_engine.py    # StorageEngine class signature
│   ├── data_types.py        # TableMetadata, TableInfo, TableSchema
│   └── examples.py          # Usage patterns
└── tasks.md             # Phase 2 output (NOT created by /speckit.plan)
```

### Source Code (repository root)

```text
src/mixpanel_data/
├── _internal/
│   └── storage.py                # StorageEngine class (NEW)
├── exceptions.py                 # TableExistsError, TableNotFoundError, QueryError (existing)
└── types.py                      # Add TableMetadata, TableInfo, TableSchema (extend existing)

tests/
├── unit/
│   └── test_storage.py           # StorageEngine unit tests (NEW)
│       ├── test_database_lifecycle
│       ├── test_table_creation
│       ├── test_query_execution
│       ├── test_introspection
│       └── test_error_handling
└── integration/
    └── test_storage_integration.py   # End-to-end storage tests (NEW)
        ├── test_persistent_storage
        ├── test_ephemeral_cleanup
        ├── test_large_dataset_ingestion
        └── test_session_persistence
```

**Structure Decision**: Single project structure (Option 1). The StorageEngine is an internal library component within the existing `mixpanel_data` package. Implementation goes in `_internal/storage.py` to maintain clear separation between public API (`Workspace`) and implementation details. Supporting types extend existing `types.py` for centralized result type management.

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

No violations. All constitutional principles are satisfied by the Storage Engine design.

---

## Phase 0: Research (Complete)

**Deliverable**: [research.md](research.md)

**Key Research Areas**:
1. ✅ DuckDB embedded database patterns → Single connection, JSON column support, pandas integration
2. ✅ Streaming batch ingestion → Iterator-based with 1000-5000 rows/batch, executemany()
3. ✅ Ephemeral database cleanup → tempfile.NamedTemporaryFile + atexit handlers
4. ✅ Default path resolution → `~/.mixpanel_data/{project_id}.db` with auto-directory creation
5. ✅ Table schema design → Fixed schemas with JSON properties column
6. ✅ Query error wrapping → Catch duckdb.Error, wrap in QueryError with context
7. ✅ Context manager protocol → __enter__/__exit__ for automatic cleanup

**Decisions Made**:
- DuckDB over SQLite/PostgreSQL (better JSON support, analytics performance)
- Batch size 1000-5000 rows (empirical testing will refine)
- Single-process access (multi-process deferred)
- No automatic indexes beyond primary keys (columnar storage provides good scan performance)

---

## Phase 1: Design & Contracts (Complete)

**Deliverables**:
- ✅ [data-model.md](data-model.md) - Database schemas and Python data structures
- ✅ [contracts/](contracts/) - Type definitions and interface contracts
  - [storage_engine.py](contracts/storage_engine.py) - StorageEngine class signature
  - [data_types.py](contracts/data_types.py) - TableMetadata, TableInfo, TableSchema, ColumnInfo
  - [examples.py](contracts/examples.py) - 8 usage patterns with complete examples
- ✅ [quickstart.md](quickstart.md) - API usage examples and integration patterns
- ✅ Agent context updated in [CLAUDE.md](../../CLAUDE.md)

**Data Structures Defined**:
- `TableMetadata` - Fetch operation metadata (frozen dataclass)
- `TableInfo` - Table summary for list_tables() (frozen dataclass)
- `TableSchema` - Table structure with ColumnInfo list (frozen dataclass)
- `ColumnInfo` - Column definition (name, type, nullable)

**Database Tables**:
- Events table: event_name, event_time, distinct_id, insert_id (PK), properties (JSON)
- Profiles table: distinct_id (PK), properties (JSON), last_seen
- _metadata table: table_name (PK), type, fetched_at, from_date, to_date, row_count

**API Contract**:
- Construction: `__init__()`, `ephemeral()`, `open_existing()`
- Table management: `create_events_table()`, `create_profiles_table()`, `drop_table()`, `table_exists()`
- Query execution: `execute()`, `execute_df()`, `execute_scalar()`, `execute_rows()`
- Introspection: `list_tables()`, `get_schema()`, `get_metadata()`
- Lifecycle: `close()`, `cleanup()`, context manager protocol
- Properties: `connection`, `path`

---

## Re-evaluated Constitution Check (Post-Design)

*Re-check required after Phase 1 design completion*

### Principle I: Library-First ✅ PASS (Unchanged)

- Design confirms StorageEngine as internal library component
- All methods are Python functions (no CLI-specific logic)
- Workspace facade will delegate to StorageEngine for all operations

### Principle II: Agent-Native Design ✅ PASS (Unchanged)

- All methods confirmed non-interactive (deterministic functions)
- Error handling via typed exceptions (no prompts or confirmations)
- Progress callbacks are optional and async-safe

### Principle III: Context Window Efficiency ✅ PASS (Enhanced)

- Introspection API (`list_tables()`, `get_schema()`, `get_metadata()`) enables agents to discover data without raw queries
- Query methods return precise results (DataFrame, scalar, rows) - no verbose dumps
- **Enhanced**: JSON query syntax documented for efficient property extraction

### Principle IV: Two Data Paths ✅ PASS (Unchanged)

- StorageEngine implements local analysis path as designed
- No overlap with LiveQueryService (clear separation)

### Principle V: Explicit Over Implicit ✅ PASS (Confirmed)

- **Verified**: `create_events_table()` raises `TableExistsError` if table exists
- **Verified**: `table_exists()` enables explicit pre-checks
- **Verified**: `drop_table()` required before replacement
- **Verified**: Metadata immutability enforced by frozen dataclasses

### Principle VI: Unix Philosophy ✅ PASS (Unchanged)

- Design confirms single responsibility (database operations only)
- No dependency on Mixpanel API or higher-level services
- Composable with standard Python ecosystem (accepts iterators, returns pandas/standard types)

### Principle VII: Secure by Default ⚠️ N/A (Unchanged)

- Storage layer does not handle credentials (ConfigManager responsibility)
- Database files unencrypted (documented as future enhancement)

**Post-Design Gate Status**: ✅ PASSED - All constitutional principles satisfied. Design phase validated and confirmed all initial architectural decisions.

---

## Implementation Readiness

**Status**: ✅ READY FOR IMPLEMENTATION

The Storage Engine design is complete and validated against constitutional principles. All required artifacts have been generated:

1. ✅ Research completed (technology choices validated)
2. ✅ Data model defined (schemas, structures, validation rules)
3. ✅ API contracts documented (complete interface specification)
4. ✅ Usage examples provided (8 patterns covering all use cases)
5. ✅ Agent context updated (technology stack recorded)

**Next Step**: `/speckit.tasks` to break down implementation into atomic tasks

**Estimated Implementation Scope**:
- Core class: ~500-700 lines (StorageEngine with all methods)
- Data types: ~100-150 lines (TableMetadata, TableInfo, TableSchema in types.py)
- Unit tests: ~800-1000 lines (comprehensive coverage of all methods)
- Integration tests: ~400-500 lines (end-to-end workflows)
- **Total estimate**: ~1800-2350 lines of code
