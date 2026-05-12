# Feature Specification: Workspace Facade

**Feature Branch**: `009-workspace`
**Created**: 2025-12-23
**Status**: Draft
**Input**: User description: "Phase 009 Workspace Facade - Implement the Workspace class as the unified public API facade that orchestrates all services (DiscoveryService, FetcherService, LiveQueryService, StorageEngine) and provides 30+ methods for Mixpanel data operations including discovery, fetching, local SQL queries, live analytics, and table management."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Basic Data Analysis Workflow (Priority: P1)

A data analyst wants to fetch Mixpanel events, store them locally, and run SQL queries to analyze patterns without repeatedly calling the Mixpanel API.

**Why this priority**: This is the core value proposition - fetch once, query many times. Preserves context window for AI agents and enables iterative analysis without API round-trips.

**Independent Test**: Can be fully tested by creating a Workspace, calling fetch_events(), and then running sql() queries against the stored data. Delivers immediate value by enabling offline analysis.

**Acceptance Scenarios**:

1. **Given** valid credentials are configured, **When** user creates a Workspace and calls fetch_events() with a date range, **Then** events are stored in the local database and a FetchResult is returned with row count and duration
2. **Given** events have been fetched, **When** user calls sql() with a valid query, **Then** a pandas DataFrame is returned with the query results
3. **Given** events have been fetched, **When** user calls sql_scalar() with an aggregation query, **Then** a single value is returned (e.g., COUNT(*))
4. **Given** a Workspace with data, **When** user closes and reopens the Workspace with the same path, **Then** previously fetched data is still accessible

---

### User Story 2 - Ephemeral Analysis Session (Priority: P1)

An AI agent needs to perform a quick, one-time analysis on Mixpanel data without leaving persistent files behind.

**Why this priority**: AI agents often need temporary workspaces that automatically clean up. This pattern is essential for CI/CD pipelines and automated analysis scripts.

**Independent Test**: Can be fully tested by using Workspace.ephemeral() context manager, performing operations, and verifying cleanup after exit. Delivers value by enabling zero-cleanup analysis workflows.

**Acceptance Scenarios**:

1. **Given** valid credentials, **When** user enters an ephemeral workspace context, **Then** a temporary database is created
2. **Given** an ephemeral workspace, **When** user fetches and queries data within the context, **Then** all operations work normally
3. **Given** an ephemeral workspace, **When** user exits the context (normally or via exception), **Then** the temporary database file is automatically deleted
4. **Given** an ephemeral workspace is created, **When** an exception occurs during operations, **Then** cleanup still happens and resources are released

---

### User Story 3 - Live Analytics Queries (Priority: P1)

A data analyst needs to run real-time Mixpanel reports (segmentation, funnels, retention) without storing data locally.

**Why this priority**: Live queries complement local storage by providing fresh data for questions that don't require historical analysis.

**Independent Test**: Can be fully tested by creating a Workspace and calling live query methods (segmentation, funnel, retention). Delivers value by providing typed access to Mixpanel's analytics APIs.

**Acceptance Scenarios**:

1. **Given** valid credentials, **When** user calls segmentation() with an event and date range, **Then** a SegmentationResult is returned with time-series data
2. **Given** a saved funnel exists in Mixpanel, **When** user calls funnel() with the funnel_id, **Then** a FunnelResult is returned with step conversion rates
3. **Given** valid credentials, **When** user calls retention() with born_event and return_event, **Then** a RetentionResult is returned with cohort retention data
4. **Given** valid credentials, **When** user calls any live query method, **Then** the result object has a .df property that returns a pandas DataFrame

---

### User Story 4 - Schema Discovery (Priority: P2)

A data analyst needs to explore what events, properties, and values exist in their Mixpanel project before writing queries.

**Why this priority**: Discovery enables informed query writing and is essential for AI agents to understand data shape before analysis.

**Independent Test**: Can be fully tested by creating a Workspace and calling discovery methods (events, properties, property_values). Delivers value by enabling schema exploration.

**Acceptance Scenarios**:

1. **Given** valid credentials, **When** user calls events(), **Then** a sorted list of event names is returned
2. **Given** valid credentials, **When** user calls properties() with an event name, **Then** a sorted list of property names is returned
3. **Given** valid credentials, **When** user calls property_values() with a property name, **Then** sample values for that property are returned
4. **Given** discovery methods have been called, **When** user calls the same method again, **Then** cached results are returned without additional API calls
5. **Given** cached discovery data exists, **When** user calls clear_discovery_cache(), **Then** subsequent discovery calls fetch fresh data from the API

---

### User Story 5 - Credential Resolution (Priority: P2)

A developer needs flexible credential configuration that supports environment variables, named accounts, and default accounts.

**Why this priority**: Proper credential handling enables deployment flexibility across development, CI/CD, and production environments.

**Independent Test**: Can be fully tested by configuring different credential sources and verifying Workspace construction resolves correctly. Delivers value by supporting multiple deployment scenarios.

**Acceptance Scenarios**:

1. **Given** all four environment variables are set (MP_USERNAME, MP_SECRET, MP_PROJECT_ID, MP_REGION), **When** user creates a Workspace without parameters, **Then** environment credentials are used
2. **Given** a named account exists in the config file, **When** user creates Workspace(account="staging"), **Then** credentials from that account are used
3. **Given** a default account is configured, **When** user creates Workspace without parameters and no env vars are set, **Then** the default account credentials are used
4. **Given** no credentials are available, **When** user attempts to create a Workspace, **Then** a ConfigError is raised with a helpful message

---

### User Story 6 - Query-Only Access to Existing Database (Priority: P2)

A data analyst wants to open an existing database file without API credentials to run SQL queries on previously fetched data.

**Why this priority**: Enables sharing databases and offline analysis without requiring API access.

**Independent Test**: Can be fully tested by opening an existing database with Workspace.open() and running queries. Delivers value by enabling credential-free data access.

**Acceptance Scenarios**:

1. **Given** an existing database file with fetched data, **When** user calls Workspace.open(path), **Then** a Workspace is returned with access to the stored data
2. **Given** an opened Workspace, **When** user calls sql(), tables(), or schema(), **Then** the operations succeed without API credentials
3. **Given** an opened Workspace without API credentials, **When** user attempts to call discovery or live query methods, **Then** an appropriate error is raised indicating API access is unavailable

---

### User Story 7 - Table Introspection and Management (Priority: P3)

A data analyst needs to understand what data exists in their Workspace and manage tables (view schemas, drop tables).

**Why this priority**: Essential for understanding workspace state and managing storage, but less frequently used than core analysis workflows.

**Independent Test**: Can be fully tested by fetching data, then using info(), tables(), schema(), and drop() methods. Delivers value by enabling workspace management.

**Acceptance Scenarios**:

1. **Given** a Workspace with fetched data, **When** user calls info(), **Then** WorkspaceInfo is returned with path, project_id, region, account, tables list, and size
2. **Given** a Workspace with tables, **When** user calls tables(), **Then** a list of TableInfo objects is returned with name, type, row_count, and fetched_at
3. **Given** a Workspace with a table, **When** user calls schema(table_name), **Then** a TableSchema is returned with column definitions
4. **Given** a Workspace with a table, **When** user calls drop(table_name), **Then** the table and its metadata are removed
5. **Given** a table does not exist, **When** user calls drop(table_name), **Then** TableNotFoundError is raised

---

### User Story 8 - Advanced Access (Priority: P3)

A power user needs direct access to the underlying DuckDB connection or API client for operations not covered by the Workspace API.

**Why this priority**: Escape hatches are important for advanced use cases but most users won't need them.

**Independent Test**: Can be fully tested by accessing .connection and .api properties and verifying they return working objects. Delivers value by enabling advanced operations.

**Acceptance Scenarios**:

1. **Given** a Workspace, **When** user accesses the .connection property, **Then** a DuckDB connection is returned that can execute raw SQL
2. **Given** a Workspace, **When** user accesses the .api property, **Then** the underlying MixpanelAPIClient is returned for direct API calls

---

### Edge Cases

- What happens when fetching events to a table that already exists? System raises TableExistsError; user must call drop() first
- How does system handle rate limiting during fetch operations? Automatic retry with exponential backoff (handled by underlying API client)
- What happens when credentials expire mid-operation? AuthenticationError is raised with details for recovery
- How does system handle concurrent access to the same database file? DuckDB handles file locking; concurrent writes may fail
- What happens when ephemeral workspace creation fails due to disk space? Appropriate system error is raised; no cleanup needed
- What happens when a live query method is called without API credentials (opened workspace)? ConfigError or AuthenticationError is raised
- How does drop_all() behave with type filter? Only tables of specified type ("events" or "profiles") are dropped

## Requirements *(mandatory)*

### Functional Requirements

**Lifecycle & Construction:**

- **FR-001**: System MUST provide a Workspace class that accepts optional account name, project_id, region, and database path parameters
- **FR-002**: System MUST resolve credentials in priority order: environment variables, named account, default account
- **FR-003**: System MUST provide an ephemeral() class method that returns a context manager for temporary workspaces
- **FR-004**: System MUST provide an open() class method for opening existing databases without credentials
- **FR-005**: System MUST implement context manager protocol (__enter__, __exit__) for resource management
- **FR-006**: System MUST provide a close() method that releases all resources (connections, temporary files)
- **FR-007**: System MUST automatically clean up ephemeral databases on context exit, even when exceptions occur

**Discovery Methods:**

- **FR-008**: System MUST provide events() method returning sorted list of event names
- **FR-009**: System MUST provide properties(event) method returning sorted list of property names for an event
- **FR-010**: System MUST provide property_values(property, event, limit) method returning sample values
- **FR-011**: System MUST provide funnels() method returning list of saved funnel definitions
- **FR-012**: System MUST provide cohorts() method returning list of saved cohort definitions
- **FR-013**: System MUST provide top_events(type, limit) method returning today's most active events
- **FR-014**: System MUST provide clear_discovery_cache() method to invalidate cached discovery data

**Fetching Methods:**

- **FR-015**: System MUST provide fetch_events(name, from_date, to_date, events, where, progress) method that fetches and stores events
- **FR-016**: System MUST provide fetch_profiles(name, where, progress) method that fetches and stores user profiles
- **FR-017**: System MUST raise TableExistsError when attempting to fetch into an existing table name
- **FR-018**: System MUST return FetchResult with table name, row count, duration, and metadata

**Local Query Methods:**

- **FR-019**: System MUST provide sql(query) method returning pandas DataFrame
- **FR-020**: System MUST provide sql_scalar(query) method returning a single value
- **FR-021**: System MUST provide sql_rows(query) method returning list of tuples

**Live Query Methods:**

- **FR-022**: System MUST provide segmentation(event, from_date, to_date, on, unit, where) method
- **FR-023**: System MUST provide funnel(funnel_id, from_date, to_date, unit, on) method
- **FR-024**: System MUST provide retention(born_event, return_event, ...) method
- **FR-025**: System MUST provide jql(script, params) method for custom JQL queries
- **FR-026**: System MUST provide event_counts(events, from_date, to_date, type, unit) method
- **FR-027**: System MUST provide property_counts(event, property_name, from_date, to_date, ...) method
- **FR-028**: System MUST provide activity_feed(distinct_ids, from_date, to_date) method
- **FR-029**: System MUST provide insights(bookmark_id) method
- **FR-030**: System MUST provide frequency(from_date, to_date, unit, addiction_unit, event, where) method
- **FR-031**: System MUST provide segmentation_numeric(event, from_date, to_date, on, ...) method
- **FR-032**: System MUST provide segmentation_sum(event, from_date, to_date, on, ...) method
- **FR-033**: System MUST provide segmentation_average(event, from_date, to_date, on, ...) method

**Introspection Methods:**

- **FR-034**: System MUST provide info() method returning WorkspaceInfo with path, project_id, region, account, tables, size_mb, created_at
- **FR-035**: System MUST provide tables() method returning list of TableInfo objects
- **FR-036**: System MUST provide schema(table) method returning TableSchema with column definitions

**Table Management Methods:**

- **FR-037**: System MUST provide drop(*names) method to remove specified tables
- **FR-038**: System MUST provide drop_all(type) method to remove all tables, optionally filtered by type
- **FR-039**: System MUST raise TableNotFoundError when dropping non-existent tables

**Escape Hatches:**

- **FR-040**: System MUST provide connection property exposing the underlying DuckDB connection
- **FR-041**: System MUST provide api property exposing the underlying MixpanelAPIClient

**Dependency Injection:**

- **FR-042**: System MUST accept optional _config_manager, _api_client, and _storage parameters for testing

### Key Entities

- **Workspace**: The primary facade class that orchestrates all Mixpanel data operations. Holds references to credentials, API client, storage engine, and service instances.
- **WorkspaceInfo**: Immutable metadata about a workspace including database path, project configuration, table list, and storage size.
- **Credentials**: Immutable authentication details (username, secret, project_id, region) resolved at workspace construction.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Users can complete a full fetch-query-analyze workflow in under 5 minutes for datasets up to 100,000 events
- **SC-002**: All 30+ Workspace methods are accessible and documented
- **SC-003**: 100% of existing service functionality is accessible through Workspace methods
- **SC-004**: Ephemeral workspaces successfully clean up in 100% of cases (including exceptions)
- **SC-005**: Users can switch between environment variables and config file credentials without code changes
- **SC-006**: All result objects from Workspace methods have working .df and .to_dict() methods
- **SC-007**: Users can open an existing database and query it without any API credentials
- **SC-008**: Type hints provide complete IDE autocompletion for all Workspace methods
- **SC-009**: Test coverage reaches 90% for the Workspace class and its method delegations

## Assumptions

- All underlying services (DiscoveryService, FetcherService, LiveQueryService, StorageEngine) are fully implemented and tested
- The existing exception hierarchy covers all error scenarios the Workspace may encounter
- WorkspaceInfo type is already defined in types.py
- ConfigManager and Credentials classes are fully functional
- MixpanelAPIClient handles rate limiting and retries transparently
- DuckDB handles file locking for concurrent access scenarios
