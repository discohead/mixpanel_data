# Feature Specification: Storage Engine

**Feature Branch**: `003-storage-engine`
**Created**: 2025-12-21
**Status**: Draft
**Input**: User description: "Phase 003 (Storage Engine)"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Persistent Data Storage (Priority: P1)

Library users need to fetch Mixpanel data once and query it repeatedly without re-fetching. The storage engine must persist events and profiles in a local database file that survives between sessions.

**Why this priority**: Core value proposition of the library. Without persistent storage, users would need to re-fetch data from Mixpanel's API for every analysis, consuming API quota and context window tokens.

**Independent Test**: Can be fully tested by creating a database, inserting sample data, closing the connection, reopening the same database file, and verifying all data is still queryable. Delivers standalone value as a local data cache.

**Acceptance Scenarios**:

1. **Given** a library user specifies a database path, **When** they create a StorageEngine instance, **Then** a database file is created at that location and is ready to accept data
2. **Given** a database file exists at a path, **When** a user creates a StorageEngine pointing to that path, **Then** the existing database is opened and all previously stored tables are accessible
3. **Given** events are inserted into a table, **When** the database is closed and reopened later, **Then** all events remain queryable with exact same values
4. **Given** no explicit path is provided, **When** a StorageEngine is created with project credentials, **Then** a default database file is created at `~/.mixpanel_data/{project_id}.db`

---

### User Story 2 - Memory-Efficient Data Ingestion (Priority: P1)

Library users need to fetch large datasets (100K+ events) from Mixpanel without running out of memory. The storage engine must accept streaming data and insert it in batches.

**Why this priority**: Essential for real-world use cases. Mixpanel projects can have millions of events. Without streaming ingestion, the library would be limited to small datasets and fail with out-of-memory errors on production data.

**Independent Test**: Can be fully tested by creating a generator that yields 1M+ event dictionaries, passing it to create_events_table(), and verifying all events are inserted while memory usage stays constant. Delivers standalone value for large dataset handling.

**Acceptance Scenarios**:

1. **Given** an iterator yielding event dictionaries, **When** a user calls create_events_table() with this iterator, **Then** events are inserted in batches without loading entire dataset into memory
2. **Given** a dataset of 1 million events provided as an iterator, **When** ingestion completes, **Then** all 1 million events are queryable and memory usage never exceeded reasonable limits (e.g., 500MB)
3. **Given** an event iterator and table metadata, **When** create_events_table() is called, **Then** fetch metadata (date range, row count, timestamp) is recorded in the _metadata table
4. **Given** streaming ingestion is in progress, **When** the user provides an optional progress callback, **Then** the callback is invoked periodically with row count updates

---

### User Story 3 - Ephemeral Analysis Workflows (Priority: P1)

Library users need to perform quick exploratory analysis without leaving database files behind. The storage engine must support temporary databases that are automatically cleaned up when done.

**Why this priority**: Core workflow for AI agents and exploratory analysis. Agents need to fetch data, analyze it briefly, and exit cleanly without manual cleanup. Critical for automation and preventing disk bloat.

**Independent Test**: Can be fully tested by creating an ephemeral StorageEngine, inserting data, querying it, closing it, and verifying the temporary file is deleted. Delivers standalone value for one-off analysis tasks.

**Acceptance Scenarios**:

1. **Given** a user calls StorageEngine.ephemeral(), **When** the instance is created, **Then** a temporary database file is created in system temp directory
2. **Given** an ephemeral database is in use, **When** the user closes it or the process exits normally, **Then** the temporary database file is automatically deleted
3. **Given** an ephemeral database is in use, **When** the process crashes or is killed, **Then** the temporary file is still cleaned up on next process start or via OS temp cleanup
4. **Given** an ephemeral database is active, **When** the user performs queries and table operations, **Then** functionality is identical to persistent databases (only cleanup behavior differs)

---

### User Story 4 - Flexible Query Execution (Priority: P2)

Library users need to query stored data in different formats depending on their use case. The storage engine must support returning results as DataFrames, scalars, row tuples, or raw database objects.

**Why this priority**: Enables different consumption patterns. Pandas DataFrames for data science workflows, scalars for simple counts, rows for programmatic access, raw relations for advanced DuckDB features.

**Independent Test**: Can be fully tested by creating a table with known data, executing the same query via each method (execute_df, execute_scalar, execute_rows, execute), and verifying each returns correct results in expected format. Delivers standalone value for query flexibility.

**Acceptance Scenarios**:

1. **Given** a table contains event data, **When** a user executes SQL via execute_df(), **Then** results are returned as a pandas DataFrame with correct columns and types
2. **Given** a query returns a single numeric value, **When** a user executes it via execute_scalar(), **Then** the raw value is returned (not wrapped in a DataFrame or list)
3. **Given** a query returns multiple rows, **When** a user executes it via execute_rows(), **Then** results are returned as a list of tuples
4. **Given** a SQL error occurs, **When** any query execution method is called, **Then** a QueryError exception is raised with the original SQL error message wrapped for context

---

### User Story 5 - Database Introspection (Priority: P2)

Library users need to discover what data has been fetched and understand table structure before writing queries. The storage engine must provide methods to list tables, view schemas, and retrieve fetch metadata.

**Why this priority**: Essential for discoverability and self-documentation. Users can't write effective queries without knowing what tables exist and what columns they contain. Particularly important for AI agents that need to explore available data.

**Independent Test**: Can be fully tested by creating multiple tables with different schemas and metadata, then calling list_tables(), get_schema(), and get_metadata() to verify correct information is returned. Delivers standalone value for exploration workflows.

**Acceptance Scenarios**:

1. **Given** multiple tables exist in the database, **When** a user calls list_tables(), **Then** all user-created tables are returned with names, types, and row counts (excluding internal _metadata table)
2. **Given** an events table exists, **When** a user calls get_schema() for that table, **Then** column names and types are returned (event_name, event_time, distinct_id, insert_id, properties)
3. **Given** a table was created with fetch metadata, **When** a user calls get_metadata() for that table, **Then** the original fetch parameters (date range, filters, timestamp) are returned
4. **Given** a user requests schema for a non-existent table, **When** get_schema() is called, **Then** a TableNotFoundError is raised with the table name

---

### User Story 6 - Explicit Table Management (Priority: P2)

Library users need predictable table creation behavior to avoid accidentally overwriting data. The storage engine must prevent implicit overwrites and require explicit drop operations.

**Why this priority**: Data safety and predictability. Prevents accidental data loss and makes library behavior deterministic for automation. Essential for production use and AI agent reliability.

**Independent Test**: Can be fully tested by creating a table, attempting to create it again, verifying TableExistsError is raised, then explicitly dropping and recreating successfully. Delivers standalone value for safe data management.

**Acceptance Scenarios**:

1. **Given** a table named "events_jan" already exists, **When** a user attempts to create_events_table() with the same name, **Then** a TableExistsError is raised without modifying the existing table
2. **Given** a user wants to replace a table, **When** they call drop_table() followed by create_events_table(), **Then** the old table is deleted and the new table is created successfully
3. **Given** a user calls table_exists() with a table name, **When** the table exists, **Then** True is returned; when it doesn't exist, False is returned
4. **Given** a table is dropped, **When** drop_table() completes, **Then** both the table and its entry in _metadata are removed

---

### Edge Cases

- What happens when disk space runs out during table creation? System should raise a clear error indicating disk space issue, not a cryptic database error.
- How does the system handle malformed data in the iterator? Each batch should be validated, and errors should indicate which record caused the problem.
- What happens when an ephemeral database's temp file is manually deleted while in use? Subsequent operations should detect the missing file and raise appropriate errors.
- How does the system handle concurrent access to the same database file? Default behavior should prevent corruption, with clear errors if multiple processes attempt simultaneous writes.
- What happens when a user provides an empty iterator to create_events_table()? A valid but empty table should be created (0 rows), not an error.
- How are large JSON property values handled in the properties column? Values should be stored as-is; it's the user's responsibility to ensure they fit Mixpanel's limits.
- What happens when the user queries a table that was created in a previous session? All functionality works identically - no session-specific state.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST create persistent database files at user-specified paths that survive process restarts
- **FR-002**: System MUST create default database files at `~/.mixpanel_data/{project_id}.db` when no path is specified
- **FR-003**: System MUST support opening existing database files for read-only or read-write access
- **FR-004**: System MUST create ephemeral databases in temporary directories that are automatically cleaned up when closed
- **FR-005**: System MUST handle ephemeral cleanup via both normal close operations and atexit handlers to ensure cleanup on unexpected termination
- **FR-006**: System MUST accept iterators (not lists) for data ingestion to enable memory-efficient processing of large datasets
- **FR-007**: System MUST insert data in batches to maintain constant memory usage regardless of dataset size
- **FR-008**: System MUST support ingesting 1 million events without exceeding 500MB memory usage
- **FR-009**: System MUST create events tables with schema: event_name (VARCHAR), event_time (TIMESTAMP), distinct_id (VARCHAR), insert_id (VARCHAR), properties (JSON)
- **FR-010**: System MUST create profiles tables with schema: distinct_id (VARCHAR), properties (JSON), last_seen (TIMESTAMP)
- **FR-011**: System MUST record fetch metadata in a _metadata table including: table_name, type, fetched_at, from_date, to_date, row_count
- **FR-012**: System MUST raise TableExistsError when attempting to create a table that already exists, without modifying the existing table
- **FR-013**: System MUST provide table_exists() method to check if a table exists before attempting creation
- **FR-014**: System MUST provide drop_table() method that removes both the table and its metadata entry
- **FR-015**: System MUST execute SQL queries and return results as pandas DataFrames via execute_df()
- **FR-016**: System MUST execute SQL queries and return single scalar values via execute_scalar()
- **FR-017**: System MUST execute SQL queries and return list of tuples via execute_rows()
- **FR-018**: System MUST execute SQL queries and return raw DuckDB relation objects via execute()
- **FR-019**: System MUST wrap all SQL errors in QueryError exceptions with descriptive messages
- **FR-020**: System MUST provide list_tables() method returning table names, types, and row counts
- **FR-021**: System MUST provide get_schema() method returning column names and types for a specified table
- **FR-022**: System MUST provide get_metadata() method returning fetch parameters for a specified table
- **FR-023**: System MUST raise TableNotFoundError when get_schema() or get_metadata() is called for non-existent tables
- **FR-024**: System MUST support optional progress callbacks during data ingestion for user feedback
- **FR-025**: System MUST implement context manager protocol (__enter__/__exit__) for automatic resource cleanup
- **FR-026**: System MUST close database connections cleanly via close() method
- **FR-027**: System MUST prevent listing the internal _metadata table in list_tables() results (implementation detail, not user data)

### Key Entities *(include if feature involves data)*

- **Events Table**: Stores timestamped user actions fetched from Mixpanel. Core columns include event name, timestamp, user identifier, unique insert ID for deduplication, and a JSON column containing all event properties as flexible key-value pairs.

- **Profiles Table**: Stores current state of user attributes fetched from Mixpanel. Core columns include user identifier (distinct_id), last activity timestamp, and a JSON column containing all profile properties.

- **Metadata Table (_metadata)**: Internal tracking table that records information about fetch operations. Stores which tables were created, when they were fetched, what date ranges were requested, and how many rows were inserted. Used for introspection and debugging.

- **TableMetadata**: Data structure representing fetch operation metadata. Contains fetch timestamp, date range (for events), filter criteria used, and data type (events or profiles). Passed to table creation methods and stored in _metadata table.

- **TableInfo**: Data structure representing summary information about a table. Contains table name, type (events/profiles), and row count. Returned by list_tables() for database exploration.

- **TableSchema**: Data structure representing table structure. Contains column names and their data types. Returned by get_schema() to help users understand table structure before querying.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Library users can ingest 1 million events with peak memory usage under 500MB (measured via memory profiling during batch inserts)
- **SC-002**: Ephemeral databases are cleaned up 100% of the time across normal exit, exception exit, and atexit scenarios (measured via integration tests)
- **SC-003**: Attempting to create a duplicate table raises TableExistsError 100% of the time without data modification (measured via unit tests)
- **SC-004**: All SQL errors are wrapped in QueryError with original error message preserved (measured via error handling tests)
- **SC-005**: Users can query stored data without re-fetching from Mixpanel API across multiple sessions (measured via integration tests with database file persistence)
- **SC-006**: Database operations (table creation, querying, introspection) complete with consistent performance regardless of existing database size (measured via performance benchmarks)
- **SC-007**: Test coverage for storage engine exceeds 90% (measured via pytest-cov)
- **SC-008**: Users can discover all available tables and their schemas through introspection without prior knowledge of database contents (measured via API completeness tests)

## Assumptions

- **DuckDB as Implementation**: While the spec focuses on behavior, this feature assumes DuckDB as the embedded database because it's already specified in project dependencies and design documents. The behaviors described (JSON column support, DataFrame integration, in-process embedding) are DuckDB-specific capabilities.

- **Default Path Convention**: The default database location `~/.mixpanel_data/{project_id}.db` follows Unix convention of dot-directories in home directory for application data. Users on Windows will have paths like `C:\Users\{user}\.mixpanel_data\{project_id}.db`.

- **Batch Size**: While not specified, batch inserts will use reasonable defaults (likely 1000-5000 rows per batch) to balance memory efficiency and insert performance. This can be tuned based on empirical testing.

- **Concurrent Access**: Initial implementation assumes single-process access. DuckDB supports concurrent reads but has limitations on concurrent writes. Multi-process scenarios will be addressed if they become requirements.

- **Data Type Mapping**: Mixpanel's data types map to DuckDB types as follows: timestamps to TIMESTAMP, strings to VARCHAR, properties to JSON. Type coercion follows DuckDB's standard behavior.

- **Property Column Size Limits**: The JSON properties column has no explicit size limit in the spec. This relies on DuckDB's JSON support and users respecting Mixpanel's property size limits (already enforced by Mixpanel's API).

- **Cleanup Reliability**: Ephemeral cleanup uses Python's atexit handlers, which work reliably for normal termination but cannot handle SIGKILL (kill -9). The spec accepts that extremely forceful termination may leave temp files, relying on OS temp cleanup policies.

- **Read-Only Access**: The spec mentions "read-only or read-write access" for opening existing databases but doesn't detail read-only mode behavior. This is assumed to be a future enhancement when needed for safety in production scenarios.

## Dependencies

- DuckDB library (already in project dependencies) for embedded database functionality
- Pandas library (already in project dependencies) for DataFrame conversion
- Python tempfile module for ephemeral database creation
- Python atexit module for cleanup handlers
- Existing exception classes (TableExistsError, TableNotFoundError, QueryError) from mixpanel_data.exceptions

## Out of Scope

- **Query Optimization**: This spec focuses on correctness and memory efficiency, not query performance tuning. Query optimization is a future enhancement based on real-world usage patterns.

- **Schema Migrations**: The initial version creates tables with fixed schemas. Handling schema evolution (adding columns, changing types) is out of scope.

- **Data Encryption**: Database files are stored unencrypted. Encryption at rest is a security enhancement for future consideration.

- **Multi-Process Coordination**: Concurrent access from multiple processes is not addressed. Single-process use (the primary use case for library users and AI agents) is the focus.

- **Backup and Recovery**: Automatic backup, point-in-time recovery, or disaster recovery features are not included. Users manage database files as regular files.

- **Data Validation**: The storage engine accepts whatever data is provided by the fetcher service. It doesn't validate that events conform to Mixpanel's data model - that's the responsibility of earlier layers.

- **Query Builder or ORM**: Users write raw SQL. Query building helpers or ORM-style abstractions are not part of the storage engine.

- **Compression**: Database file compression or column compression is left to DuckDB's defaults. Explicit compression tuning is out of scope.
