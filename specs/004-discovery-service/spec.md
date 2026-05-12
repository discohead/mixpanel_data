# Feature Specification: Discovery Service

**Feature Branch**: `004-discovery-service`
**Created**: 2025-12-21
**Status**: Draft
**Input**: User description: "Phase 004 Discovery Service"

## Overview

The Discovery Service enables users to explore and understand the schema of their Mixpanel data before querying or fetching it. This is critical for AI coding agents and data analysts who need to understand what events exist, what properties those events have, and what values those properties contain—all without consuming context window tokens on raw data exploration.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Discover Available Events (Priority: P1)

As an AI coding agent or data analyst, I want to list all event names in a Mixpanel project so I can understand what data is available before writing queries or fetching data.

**Why this priority**: This is the foundational discovery operation. Without knowing what events exist, users cannot proceed with any meaningful data analysis. Every other discovery operation depends on knowing valid event names first.

**Independent Test**: Can be fully tested by requesting the list of events and verifying a complete, sorted list is returned. Delivers immediate value by revealing the data vocabulary.

**Acceptance Scenarios**:

1. **Given** valid Mixpanel credentials, **When** I request the list of events, **Then** I receive a complete alphabetically-sorted list of all event names in the project.
2. **Given** valid credentials, **When** I request events multiple times within a session, **Then** subsequent requests return cached results without additional network calls.
3. **Given** invalid or missing credentials, **When** I request the list of events, **Then** I receive a clear authentication error.

---

### User Story 2 - Explore Event Properties (Priority: P1)

As an AI coding agent or data analyst, I want to list all properties associated with a specific event so I can understand the data structure and write accurate queries.

**Why this priority**: Understanding event properties is essential for building queries. This is equally important as listing events because users need both to construct meaningful analyses.

**Independent Test**: Can be fully tested by providing a valid event name and verifying all associated properties are returned in a sorted list.

**Acceptance Scenarios**:

1. **Given** a valid event name, **When** I request properties for that event, **Then** I receive an alphabetically-sorted list of all property names associated with that event.
2. **Given** an event name that doesn't exist, **When** I request its properties, **Then** I receive a clear error indicating the event was not found.
3. **Given** valid credentials and event, **When** I request properties multiple times for the same event, **Then** subsequent requests return cached results.

---

### User Story 3 - Sample Property Values (Priority: P2)

As an AI coding agent or data analyst, I want to see sample values for a specific property so I can understand the data distribution and format before writing filter conditions.

**Why this priority**: While valuable for understanding data shape, this is secondary to knowing what events and properties exist. Users can proceed with basic queries without sample values, but sample values improve query accuracy.

**Independent Test**: Can be fully tested by providing a property name (and optionally an event scope) and verifying sample values are returned.

**Acceptance Scenarios**:

1. **Given** a valid property name, **When** I request sample values, **Then** I receive a list of actual values that property contains in the data.
2. **Given** a property name and specific event, **When** I request sample values scoped to that event, **Then** I receive values only from that event's data.
3. **Given** a request for sample values, **When** I specify a limit, **Then** the returned list contains at most that many values.
4. **Given** valid parameters, **When** I request sample values multiple times, **Then** subsequent requests return cached results.

---

### User Story 4 - Clear Discovery Cache (Priority: P3)

As a user working with evolving data, I want to clear cached discovery results so I can see the latest schema information when my Mixpanel project has changed.

**Why this priority**: Cache management is a convenience feature. Most users will create new sessions when they need fresh data. However, for long-running sessions where the underlying data evolves, manual cache clearing provides flexibility.

**Independent Test**: Can be fully tested by populating the cache, clearing it, and verifying the next request fetches fresh data.

**Acceptance Scenarios**:

1. **Given** cached discovery results exist, **When** I clear the cache, **Then** subsequent discovery requests fetch fresh data from the source.
2. **Given** no cached results exist, **When** I clear the cache, **Then** the operation completes without error.

---

### Edge Cases

- What happens when the Mixpanel project has no events? → Return an empty list, not an error.
- What happens when an event has no custom properties? → Return an empty list (or only system properties if applicable).
- What happens when a property has no recorded values? → Return an empty list.
- How does the system handle rate limiting from the data source? → Respect rate limits with appropriate waiting and retry, surfacing clear errors if limits are exceeded.
- What happens when credentials become invalid mid-session? → Surface authentication errors clearly on the next discovery request.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST provide a method to list all event names in a Mixpanel project.
- **FR-002**: System MUST return event lists in alphabetical order for consistent, predictable output.
- **FR-003**: System MUST provide a method to list all properties for a specified event.
- **FR-004**: System MUST return property lists in alphabetical order.
- **FR-005**: System MUST provide a method to retrieve sample values for a specified property.
- **FR-006**: System MUST support scoping property value queries to a specific event.
- **FR-007**: System MUST support limiting the number of sample values returned.
- **FR-008**: System MUST cache discovery results within a session to avoid redundant network requests.
- **FR-009**: System MUST provide a method to clear the discovery cache.
- **FR-010**: System MUST surface authentication errors clearly when credentials are invalid.
- **FR-011**: System MUST surface clear errors when referencing non-existent events.
- **FR-012**: System MUST handle empty results gracefully, returning empty lists rather than errors.

### Key Entities

- **Event**: A named action tracked in Mixpanel (e.g., "Sign Up", "Purchase"). Key attributes: name.
- **Property**: A data field associated with events (e.g., "country", "plan_type"). Key attributes: name, associated event(s).
- **Property Value**: An actual value recorded for a property (e.g., "US", "premium"). Key attributes: value as string.
- **Discovery Cache**: Temporary storage of discovery results to avoid redundant requests. Key attributes: cache key (method + parameters), cached result, session scope.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Users can retrieve the complete list of events in under 3 seconds for typical projects (up to 1,000 events).
- **SC-002**: Cached discovery requests return results in under 100 milliseconds.
- **SC-003**: All discovery results are returned in consistent alphabetical order across repeated requests.
- **SC-004**: 100% of discovery operations that encounter errors provide actionable error messages identifying the cause (authentication, invalid event, rate limit, etc.).
- **SC-005**: Repeated discovery requests within a session result in zero additional network calls when cache is populated.
- **SC-006**: The discovery feature reduces AI agent context window consumption by enabling schema exploration before data fetching.

## Assumptions

- **A-001**: Discovery results are relatively stable within a session. Events and properties don't change frequently enough to require real-time updates during typical usage.
- **A-002**: Session-scoped caching is sufficient. Users who need fresh data can create a new session or manually clear the cache.
- **A-003**: The default limit for sample property values (when not specified) will be a reasonable number that balances completeness with performance (assumed: 100 values).
- **A-004**: All string values (event names, property names, property values) will be returned as-is from the data source without transformation.
- **A-005**: The discovery service operates in read-only mode and does not modify any Mixpanel project data.

## Dependencies

- **D-001**: Requires valid Mixpanel credentials (service account with read access).
- **D-002**: Depends on the existing authentication/configuration system (Phase 001).
- **D-003**: Depends on the existing API client for network communication (Phase 002).

## Out of Scope

- Property type information (string, number, boolean, etc.) - not reliably available from discovery endpoints.
- Event metadata beyond names (descriptions, tags, schemas).
- Profile property discovery (separate from event properties).
- Cross-project discovery.
- Persistent caching across sessions.
- Real-time cache invalidation when Mixpanel data changes.
