# Feature Specification: Mixpanel API Client

**Feature Branch**: `002-api-client`
**Created**: 2025-12-20
**Status**: Draft
**Input**: User description: "Phase 002: API Client - HTTP client for Mixpanel API with authentication, rate limiting, and streaming export"

## Overview

The Mixpanel API Client provides a unified interface for communicating with all Mixpanel APIs. It handles authentication, regional endpoint routing, rate limiting with automatic retry, and response parsing. This component is the foundation for all remote data operations in the library.

The client operates as a pure HTTP layer with no knowledge of local storage—it fetches data from Mixpanel and returns it to callers, who decide what to do with it.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Make Authenticated API Requests (Priority: P1)

A developer using the library needs to make authenticated requests to Mixpanel APIs using their service account credentials. The client should handle authentication transparently so developers can focus on what data they need, not how to authenticate.

**Why this priority**: Without authentication working, no other API operations are possible. This is the foundational capability that enables all other features.

**Independent Test**: Can be fully tested by making a simple API request (e.g., listing events) and verifying the response contains expected data. Delivers immediate value by proving credentials work.

**Acceptance Scenarios**:

1. **Given** valid service account credentials, **When** making any API request, **Then** the request includes proper Basic authentication headers and the project_id parameter
2. **Given** invalid credentials, **When** making any API request, **Then** the system raises an AuthenticationError with a clear message
3. **Given** credentials with wrong permissions, **When** accessing a protected resource, **Then** the system raises an AuthenticationError indicating insufficient permissions

---

### User Story 2 - Handle Rate Limiting Gracefully (Priority: P1)

A developer running data fetches should not need to worry about Mixpanel's rate limits. The client should automatically detect rate limit responses and retry with appropriate backoff, only raising an error when retries are exhausted.

**Why this priority**: Rate limiting affects all API operations. Without automatic handling, every user would need to implement their own retry logic, leading to inconsistent behavior and poor user experience.

**Independent Test**: Can be tested by simulating 429 responses and verifying the client retries with exponential backoff before eventually succeeding or raising RateLimitError.

**Acceptance Scenarios**:

1. **Given** an API request that receives a 429 response, **When** the Retry-After header is present, **Then** the client waits for the specified duration before retrying
2. **Given** an API request that receives a 429 response, **When** no Retry-After header is present, **Then** the client uses exponential backoff with jitter
3. **Given** an API request that exceeds maximum retry attempts, **When** still receiving 429 responses, **Then** the client raises RateLimitError with retry timing information
4. **Given** an API request that receives a 429 and then succeeds on retry, **When** the operation completes, **Then** the caller receives the successful response with no indication of the retry

---

### User Story 3 - Stream Large Event Exports (Priority: P1)

A developer needs to export millions of events from Mixpanel without running out of memory. The client should stream events one at a time so the caller can process them incrementally.

**Why this priority**: Event export is a core use case for the library. Without streaming, large exports would exhaust memory, making the library unusable for production workloads.

**Independent Test**: Can be tested by exporting events for a date range and verifying events are yielded as an iterator without loading all into memory. Delivers value by enabling large-scale data analysis.

**Acceptance Scenarios**:

1. **Given** a date range with events, **When** calling export_events, **Then** the client returns an iterator that yields individual event dictionaries
2. **Given** a large export with millions of events, **When** iterating through results, **Then** memory usage remains constant regardless of total event count
3. **Given** an export in progress, **When** providing an on_batch callback, **Then** the callback is invoked periodically with batch counts for progress reporting
4. **Given** optional event name filters, **When** calling export_events with events parameter, **Then** only matching events are returned

---

### User Story 4 - Query Segmentation Data (Priority: P2)

A developer needs to run segmentation queries to understand event trends over time, optionally segmented by a property. The client should provide the raw API response for the service layer to transform.

**Why this priority**: Segmentation is the most common live query type. It enables quick trend analysis without fetching raw events.

**Independent Test**: Can be tested by running a segmentation query for a known event and verifying the response contains time-series data.

**Acceptance Scenarios**:

1. **Given** an event name and date range, **When** calling segmentation, **Then** the client returns a dictionary with time-series counts
2. **Given** a segmentation query with "on" parameter, **When** the query executes, **Then** results are segmented by the specified property
3. **Given** a segmentation query with "where" filter, **When** the query executes, **Then** only matching events are counted

---

### User Story 5 - Discover Available Events and Properties (Priority: P2)

A developer exploring a Mixpanel project needs to discover what events exist and what properties they have. The client should provide methods to list events, properties, and sample property values.

**Why this priority**: Discovery enables users to explore data before querying. It's essential for building interactive tools and for agents to understand available data.

**Independent Test**: Can be tested by listing events and verifying the response contains event names from the project.

**Acceptance Scenarios**:

1. **Given** a valid project, **When** calling get_events, **Then** the client returns a list of event names
2. **Given** an event name, **When** calling get_event_properties, **Then** the client returns a list of property names for that event
3. **Given** an event and property name, **When** calling get_property_values, **Then** the client returns sample values for that property

---

### User Story 6 - Export User Profiles (Priority: P2)

A developer needs to export user profiles from Mixpanel for local analysis. Unlike events, profiles use pagination rather than streaming.

**Why this priority**: Profile data complements event data for user-level analysis. It's a common use case but secondary to event export.

**Independent Test**: Can be tested by exporting profiles and verifying user records are returned as an iterator.

**Acceptance Scenarios**:

1. **Given** a project with user profiles, **When** calling export_profiles, **Then** the client returns an iterator of profile dictionaries
2. **Given** a large profile dataset, **When** iterating through results, **Then** the client handles pagination automatically
3. **Given** a "where" filter, **When** calling export_profiles, **Then** only matching profiles are returned

---

### User Story 7 - Run Funnel and Retention Queries (Priority: P3)

A developer needs to run funnel conversion analysis and retention cohort analysis. The client should provide raw API responses for these query types.

**Why this priority**: Funnel and retention are important analytics but less frequently used than segmentation. They follow similar patterns.

**Independent Test**: Can be tested by running funnel/retention queries and verifying structured responses.

**Acceptance Scenarios**:

1. **Given** a funnel ID and date range, **When** calling funnel, **Then** the client returns step-by-step conversion data
2. **Given** born/return events and date range, **When** calling retention, **Then** the client returns cohort retention data

---

### User Story 8 - Execute Custom JQL Queries (Priority: P3)

A developer with complex analysis needs can write custom JavaScript queries using Mixpanel's JQL. The client should execute these scripts and return results.

**Why this priority**: JQL is a power-user feature. Most users will use the standard query methods, but JQL enables advanced use cases.

**Independent Test**: Can be tested by executing a simple JQL script and verifying results.

**Acceptance Scenarios**:

1. **Given** a valid JQL script, **When** calling jql, **Then** the client returns the script execution results as a list
2. **Given** a JQL script with parameters, **When** providing params dictionary, **Then** parameters are passed to the script

---

### Edge Cases

- **Network interruption during export**: The export iterator raises an appropriate exception; caller can retry from scratch
- **Malformed JSON in JSONL export**: The client skips malformed lines and logs a warning; continues processing valid events
- **Credential expiration during long export**: The client raises AuthenticationError; caller must refresh credentials and retry
- **Mixpanel API maintenance/downtime**: 5xx errors trigger retries with backoff; persistent failures raise MixpanelDataError
- **Empty date range**: Export returns empty iterator; query methods return empty results structure
- **Invalid event/property names**: QueryError raised with details about what was invalid

## Requirements *(mandatory)*

### Functional Requirements

**Authentication & Routing**
- **FR-001**: Client MUST authenticate all requests using HTTP Basic authentication with service account credentials
- **FR-002**: Client MUST include project_id as a query parameter on all requests
- **FR-003**: Client MUST route requests to the correct regional endpoint based on credentials.region (US, EU, India)
- **FR-004**: Client MUST NOT expose credentials in error messages, logs, or exceptions

**Rate Limiting**
- **FR-005**: Client MUST detect HTTP 429 responses and automatically retry with backoff
- **FR-006**: Client MUST respect Retry-After headers when present in 429 responses
- **FR-007**: Client MUST implement exponential backoff with random jitter for retries
- **FR-008**: Client MUST raise RateLimitError after configurable maximum retry attempts (default: 3)

**Export API**
- **FR-009**: Client MUST stream event exports as an iterator, not loading all events into memory
- **FR-010**: Client MUST parse JSONL (newline-delimited JSON) response format for event exports
- **FR-011**: Client MUST support optional gzip decompression for export responses
- **FR-012**: Client MUST support on_batch callback for export progress reporting

**Profile API**
- **FR-013**: Client MUST handle paginated profile responses using session_id mechanism
- **FR-014**: Client MUST expose profiles as an iterator despite underlying pagination

**Discovery API**
- **FR-015**: Client MUST provide method to list all event names in a project
- **FR-016**: Client MUST provide method to list properties for a specific event
- **FR-017**: Client MUST provide method to list sample values for a property

**Query API**
- **FR-018**: Client MUST provide methods for segmentation, funnel, retention, and JQL queries
- **FR-019**: Client MUST return raw API responses (dict/list) for query methods
- **FR-020**: Client MUST support all standard query parameters for each query type

**Error Handling**
- **FR-021**: Client MUST map HTTP 401 responses to AuthenticationError
- **FR-022**: Client MUST map HTTP 400 responses to QueryError with error details
- **FR-023**: Client MUST map HTTP 429 responses to automatic retry or RateLimitError
- **FR-024**: Client MUST map HTTP 5xx responses to MixpanelDataError with retry suggestion

**Lifecycle**
- **FR-025**: Client MUST support context manager protocol for resource cleanup
- **FR-026**: Client MUST provide configurable request timeout (default: 30 seconds, export: 300 seconds)

### Key Entities

- **Credentials**: Immutable authentication data including username, secret, project_id, and region (already implemented in Phase 001)
- **API Response**: Raw dictionary or list returned from Mixpanel API endpoints
- **Export Event**: Single event dictionary with event name, timestamp, distinct_id, and properties
- **Profile**: Single user profile dictionary with distinct_id and properties

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: All Mixpanel API endpoints (export, query, discovery) are accessible via single client instance
- **SC-002**: Rate limiting is transparent to callers—automatic retry succeeds without caller intervention in 95%+ of rate-limited requests
- **SC-003**: Event exports of 1 million+ records complete without memory exhaustion (constant memory usage)
- **SC-004**: 90%+ of API errors are mapped to appropriate exception types with actionable messages
- **SC-005**: Credentials never appear in exception messages, log output, or error details
- **SC-006**: Test coverage reaches 90%+ for all client methods

## Assumptions

1. **Service accounts only**: The client assumes service account authentication (not project secrets or OAuth)
2. **Synchronous operation**: The client is synchronous; async support may be added in a future phase
3. **Credentials provided externally**: The client receives resolved Credentials from ConfigManager; it does not resolve credentials itself
4. **Regional consistency**: All requests for a client instance use the same region; switching regions requires a new client
5. **Standard rate limits**: Default rate limits follow Mixpanel's documented limits (60/hour for most endpoints)

## Dependencies

- **Phase 001 (Foundation Layer)**: Credentials class, exception hierarchy (AuthenticationError, RateLimitError, QueryError, MixpanelDataError)
- **httpx library**: HTTP client with connection pooling (already in pyproject.toml dependencies)

## Out of Scope

- Local storage (handled by Phase 003: Storage Engine)
- Response transformation to result types (handled by service layer)
- CLI integration (handled by Phase 008: CLI)
- Async/await support (potential future enhancement)
