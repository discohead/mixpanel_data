# Feature Specification: MCP Server for mixpanel_data

**Feature Branch**: `020-mcp-server`
**Created**: 2026-01-12
**Status**: Draft
**Input**: User description: "FastMCP Server for mixpanel_data"

## Overview

Enable AI assistants (Claude Desktop, other MCP-compatible clients) to perform Mixpanel analytics through the Model Context Protocol (MCP). Users will be able to discover their Mixpanel schema, run live analytics queries, fetch data for local analysis, and execute SQL queries—all through natural language conversation with an AI assistant.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Schema Discovery (Priority: P1)

As a data analyst using an AI assistant, I want to explore my Mixpanel project's schema so I can understand what events, properties, funnels, and cohorts are available for analysis.

**Why this priority**: Discovery is the foundation of any analytics workflow. Users must first understand what data exists before they can query it. This is the entry point for all subsequent analysis.

**Independent Test**: Can be fully tested by connecting the AI assistant to the MCP server and asking "What events are tracked in my Mixpanel project?" The assistant should return a list of event names.

**Acceptance Scenarios**:

1. **Given** a connected AI assistant, **When** user asks "What events do I have?", **Then** the assistant lists all tracked event names alphabetically
2. **Given** a connected AI assistant, **When** user asks "What properties does the signup event have?", **Then** the assistant lists all properties for that event
3. **Given** a connected AI assistant, **When** user asks "Show me my saved funnels", **Then** the assistant lists all saved funnels with their names and step counts
4. **Given** a connected AI assistant, **When** user asks "What cohorts exist?", **Then** the assistant lists all saved cohorts with their names and sizes

---

### User Story 2 - Live Analytics Queries (Priority: P1)

As a product manager, I want to ask analytical questions about user behavior and get answers from live Mixpanel data so I can make data-driven decisions without writing code.

**Why this priority**: Live queries provide immediate business value by answering questions about user behavior, conversions, and retention without requiring data exports or local analysis.

**Independent Test**: Can be fully tested by asking "How many users signed up last week?" and receiving a time-series breakdown of signup counts.

**Acceptance Scenarios**:

1. **Given** a connected AI assistant, **When** user asks "How many logins happened each day last month?", **Then** the assistant runs a segmentation query and returns daily counts
2. **Given** a connected AI assistant, **When** user asks "What's the conversion rate for my checkout funnel?", **Then** the assistant queries the funnel and returns step-by-step conversion percentages
3. **Given** a connected AI assistant, **When** user asks "What's our day-7 retention for users who signed up last month?", **Then** the assistant runs a retention query and returns cohort retention curves
4. **Given** a connected AI assistant, **When** user asks "Break down purchases by country", **Then** the assistant segments the data by the country property

---

### User Story 3 - Data Fetching for Local Analysis (Priority: P2)

As a data scientist, I want to fetch raw event data into a local database so I can run custom SQL queries and perform analysis that isn't possible through Mixpanel's standard APIs.

**Why this priority**: While live queries handle most use cases, power users need access to raw data for custom analysis. This enables complex joins, aggregations, and exploratory analysis.

**Independent Test**: Can be fully tested by asking "Fetch all events from last week" and then running SQL queries against the local data.

**Acceptance Scenarios**:

1. **Given** a connected AI assistant, **When** user asks "Fetch events from January 1-7", **Then** events are downloaded and stored locally for querying
2. **Given** events have been fetched, **When** user asks "Show me a sample of the data", **Then** the assistant displays random rows from the local table
3. **Given** events have been fetched, **When** user asks "Count events by name", **Then** the assistant runs a SQL query and returns event counts
4. **Given** user asks to fetch data that already exists, **Then** the assistant informs them and suggests how to replace or query existing data

---

### User Story 4 - Local SQL Analysis (Priority: P2)

As a data analyst, I want to run custom SQL queries against locally fetched data so I can perform complex analysis, create custom aggregations, and explore data patterns.

**Why this priority**: SQL provides unlimited analytical flexibility. Once data is fetched locally, users can run any query they need without API constraints.

**Independent Test**: Can be fully tested by fetching data and asking "Write a SQL query to find the top 10 users by event count."

**Acceptance Scenarios**:

1. **Given** fetched event data, **When** user asks for a specific SQL query, **Then** the assistant executes it and returns results
2. **Given** a local table, **When** user asks "What columns does this table have?", **Then** the assistant shows the table schema
3. **Given** a local table, **When** user asks "Summarize this data", **Then** the assistant returns column statistics (counts, nulls, min, max, etc.)
4. **Given** JSON property data, **When** user asks "What properties are stored?", **Then** the assistant extracts and lists all JSON property keys

---

### User Story 5 - Session Persistence (Priority: P3)

As an analyst conducting a multi-step investigation, I want my session state to persist across multiple questions so I can build on previous queries without re-fetching data.

**Why this priority**: Analytics workflows often involve iterative exploration. Maintaining session state enables natural, conversational analysis without repetitive setup.

**Independent Test**: Can be tested by fetching data, running a query, then running another query that references the same data without re-fetching.

**Acceptance Scenarios**:

1. **Given** data was fetched in a previous question, **When** user asks a follow-up query, **Then** the assistant can access the previously fetched data
2. **Given** multiple tables exist from different fetches, **When** user asks "What tables do I have?", **Then** the assistant lists all tables with their metadata
3. **Given** an active session, **When** user asks to drop a table, **Then** the table is removed and the assistant confirms

---

### User Story 6 - Guided Analytics Workflows (Priority: P3)

As a new user, I want to be guided through analytics workflows so I can learn how to effectively explore my data without being an analytics expert.

**Why this priority**: Prompts reduce the learning curve and help users discover capabilities they might not know exist.

**Independent Test**: Can be tested by invoking a guided workflow and following the suggested steps to complete an analysis.

**Acceptance Scenarios**:

1. **Given** a connected AI assistant, **When** user requests the "analytics workflow" prompt, **Then** the assistant guides them through discovery, exploration, and analysis steps
2. **Given** a connected AI assistant, **When** user requests a "funnel analysis" prompt for a specific funnel, **Then** the assistant provides step-by-step guidance for analyzing that funnel
3. **Given** a connected AI assistant, **When** user requests a "retention analysis" prompt, **Then** the assistant guides them through cohort retention analysis

---

### Edge Cases

- What happens when credentials are not configured? The system provides a clear error message with instructions for configuring authentication.
- What happens when a query exceeds Mixpanel rate limits? The system informs the user of the rate limit and when they can retry.
- What happens when a user tries to fetch a very large date range? The system warns about potential long duration and offers parallel fetching for faster downloads.
- What happens when a table already exists? The system does not silently overwrite; instead informs the user and suggests using the drop command first.
- What happens when a SQL query has syntax errors? The system returns the error message in a user-friendly format.
- What happens when the Mixpanel project has no data? The system informs the user that no events/properties/funnels exist yet.

## Requirements *(mandatory)*

### Functional Requirements

**Discovery Capabilities**
- **FR-001**: System MUST list all event names tracked in the Mixpanel project
- **FR-002**: System MUST list all properties for a specific event
- **FR-003**: System MUST provide sample values for any property
- **FR-004**: System MUST list all saved funnels with their metadata
- **FR-005**: System MUST list all saved cohorts with their metadata
- **FR-006**: System MUST list all saved bookmarks/reports
- **FR-007**: System MUST show the most active events in real-time

**Live Query Capabilities**
- **FR-008**: System MUST execute segmentation queries with time-series results
- **FR-009**: System MUST execute funnel queries with step-by-step conversion data
- **FR-010**: System MUST execute retention queries with cohort retention curves
- **FR-011**: System MUST support JQL (JavaScript Query Language) for complex queries
- **FR-012**: System MUST support multi-event comparison queries
- **FR-013**: System MUST support property value distribution analysis
- **FR-014**: System MUST support user activity feed lookup
- **FR-015**: System MUST support event frequency distribution analysis
- **FR-016**: System MUST support numeric property aggregations (sum, average, buckets)

**Data Fetching Capabilities**
- **FR-017**: System MUST fetch events from Mixpanel into local storage for a specified date range
- **FR-018**: System MUST fetch user profiles from Mixpanel into local storage
- **FR-019**: System MUST support streaming events without storage for quick exploration
- **FR-020**: System MUST support parallel fetching for faster downloads of large date ranges
- **FR-021**: System MUST reject fetching into an existing table name (explicit table management)

**Local Analysis Capabilities**
- **FR-022**: System MUST execute SQL queries against locally stored data
- **FR-023**: System MUST return scalar values from single-value SQL queries
- **FR-024**: System MUST provide table metadata (row count, size, creation time)
- **FR-025**: System MUST provide table schema (column names and types)
- **FR-026**: System MUST provide random sample rows from any table
- **FR-027**: System MUST provide statistical summaries of table columns
- **FR-028**: System MUST count events by name in event tables
- **FR-029**: System MUST extract JSON property keys from property columns
- **FR-030**: System MUST provide detailed statistics for specific columns
- **FR-031**: System MUST support dropping individual tables
- **FR-032**: System MUST support dropping all tables (with optional type filter)

**Session & State Management**
- **FR-033**: System MUST maintain session state across multiple tool calls
- **FR-034**: System MUST provide workspace information (database state, configuration)
- **FR-035**: System MUST properly clean up resources when session ends

**Error Handling**
- **FR-036**: System MUST convert authentication errors to user-friendly messages
- **FR-037**: System MUST include retry guidance for rate limit errors
- **FR-038**: System MUST provide actionable error messages for all failure modes

**Authentication**
- **FR-039**: System MUST resolve credentials from environment variables
- **FR-040**: System MUST resolve credentials from configuration file
- **FR-041**: System MUST support named accounts for multi-project access

### Key Entities

- **Workspace**: The central analytics session containing connection to Mixpanel and local database state
- **Event**: A tracked user action with name, timestamp, distinct_id, and properties
- **Property**: A key-value attribute attached to an event or user profile
- **Funnel**: A saved sequence of events measuring conversion through steps
- **Cohort**: A saved group of users defined by criteria
- **Bookmark**: A saved report configuration (insights, flows, etc.)
- **Table**: A locally stored collection of fetched events or profiles

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Users can discover their complete Mixpanel schema (events, properties, funnels, cohorts) within a single conversation turn (typically <5 seconds per discovery call)
- **SC-002**: Users can execute live analytics queries (segmentation, funnel, retention) and receive results within the same response (within Mixpanel API latency bounds, typically <30 seconds)
- **SC-003**: Users can fetch up to 90 days of event data and query it locally within a single session
- **SC-004**: All 35+ analytics operations are accessible through natural language conversation
- **SC-005**: Error messages include actionable guidance that enables users to self-resolve issues
- **SC-006**: Session state persists across all tool calls within a single conversation
- **SC-007**: Rate limit errors include specific retry timing information
- **SC-008**: Authentication configuration takes less than 5 minutes following documentation

## Assumptions

- Users have valid Mixpanel credentials (service account username/secret and project ID)
- Users are using an MCP-compatible AI assistant (Claude Desktop or similar)
- The Mixpanel project has existing data to query (events, profiles, etc.)
- Users have basic familiarity with analytics concepts (events, funnels, retention)
- Local storage is available for fetched data (in-memory or file-based)

## Scope Boundaries

**In Scope:**
- All read operations from Mixpanel (discovery, queries, data export)
- Local data storage and SQL analysis
- Single Mixpanel project per server session
- Standard MCP transport protocols (stdio for local, HTTP for remote)

**Out of Scope:**
- Writing data to Mixpanel (sending events, updating profiles)
- Multi-project support within a single session
- Real-time streaming of live events
- OAuth/API key authentication for MCP protocol layer
- Shared state across multiple MCP clients
- Caching layer for multi-session data sharing
