# Feature Specification: Foundation Layer

**Feature Branch**: `001-foundation-layer`
**Created**: 2025-12-19
**Status**: Draft
**Input**: User description: "Implement the Foundation layer including ConfigManager, exceptions, and result types"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Configure Mixpanel Credentials (Priority: P1)

A developer or AI agent needs to configure Mixpanel project credentials so they can authenticate with the Mixpanel API. They want to store credentials securely and switch between multiple projects (e.g., production, staging) without modifying code.

**Why this priority**: Without credential configuration, no other functionality can work. This is the foundational prerequisite for all API access.

**Independent Test**: Can be fully tested by adding a project configuration and verifying credentials can be retrieved. Delivers immediate value by enabling API authentication.

**Acceptance Scenarios**:

1. **Given** no configuration exists, **When** a user adds credentials for a project named "production", **Then** the credentials are stored securely and can be retrieved by name.

2. **Given** credentials exist for multiple projects, **When** a user requests the default project, **Then** the system returns the designated default project's credentials.

3. **Given** environment variables are set for credentials, **When** a user requests credentials, **Then** environment variables take precedence over stored configuration.

4. **Given** a named project doesn't exist, **When** a user requests credentials for it, **Then** the system provides a clear error indicating the project was not found.

---

### User Story 2 - Receive Clear Error Messages (Priority: P2)

A developer or AI agent encounters an error while using the library. They need to understand what went wrong and how to fix it without digging through stack traces. Error types should be predictable and programmatically handleable.

**Why this priority**: Good error handling enables developers and agents to build robust applications and debug issues quickly. Critical for adoption and usability.

**Independent Test**: Can be fully tested by triggering various error conditions and verifying the error messages are clear, specific, and actionable.

**Acceptance Scenarios**:

1. **Given** invalid credentials are provided, **When** an authentication attempt fails, **Then** the system raises a specific authentication error with a message explaining the failure.

2. **Given** a user attempts to create a table that already exists, **When** the operation is attempted, **Then** the system raises a specific error indicating the table exists (not a generic error).

3. **Given** any library error occurs, **When** the error is caught, **Then** all errors share a common base type for easy catch-all handling.

4. **Given** an API rate limit is exceeded, **When** the operation fails, **Then** the system raises a specific rate limit error with retry guidance.

---

### User Story 3 - Work with Structured Operation Results (Priority: P3)

A developer or AI agent performs operations like fetching data or running queries. They need to receive structured results that include both the data and metadata about the operation (timing, counts, date ranges) for logging, monitoring, and decision-making.

**Why this priority**: Structured results enable better observability, debugging, and programmatic handling of operation outcomes. Important for production use.

**Independent Test**: Can be fully tested by performing operations and verifying results contain expected metadata fields alongside the data.

**Acceptance Scenarios**:

1. **Given** a data fetch operation completes, **When** the result is returned, **Then** it includes the table name, row count, operation duration, and timestamp.

2. **Given** a query result is returned, **When** the result is accessed, **Then** it can be converted to common data formats (dictionary, tabular data) on demand.

3. **Given** any operation result, **When** the result is inspected, **Then** all result types share common fields (success status, timing, errors if any) for consistent handling.

---

### Edge Cases

- What happens when the config file is malformed or corrupted?
- What happens when environment variables contain invalid values?
- How does the system handle credentials with special characters?
- What happens when file permissions prevent reading/writing config?
- How are concurrent access attempts to the config file handled?

## Requirements *(mandatory)*

### Functional Requirements

#### Configuration Management

- **FR-001**: System MUST support storing credentials for multiple named projects (e.g., "production", "staging").
- **FR-002**: System MUST support designating one project as the default.
- **FR-003**: System MUST resolve credentials in order: environment variables, then named project, then default project.
- **FR-004**: System MUST validate that required credential fields (username, secret, project ID, region) are present before returning credentials.
- **FR-005**: System MUST support listing all configured project names.
- **FR-006**: System MUST support removing a named project configuration.
- **FR-007**: Credential secrets MUST never appear in logs, error messages, or string representations.

#### Error Handling

- **FR-008**: System MUST provide a base exception type that all library-specific errors inherit from.
- **FR-009**: System MUST provide specific exception types for: authentication failures, missing resources, configuration problems, rate limiting, and query errors.
- **FR-010**: All exception messages MUST be human-readable and actionable.
- **FR-011**: Exceptions MUST be serializable for logging purposes.

#### Result Types

- **FR-012**: System MUST provide structured result types for data fetch operations including: table name, row count, data type, duration, date range (if applicable), and timestamp.
- **FR-013**: System MUST provide structured result types for live query operations including: query parameters, total count, and data conversion methods.
- **FR-014**: All result types MUST support conversion to dictionary format.
- **FR-015**: Result types containing tabular data MUST support lazy conversion to data frames.

### Key Entities

- **Credentials**: Represents authentication information for a Mixpanel project. Contains username, secret, project ID, and region. Immutable once created.

- **AccountInfo**: Represents a named project configuration. Contains name, credentials, and whether it's the default. Used for listing and management.

- **FetchResult**: Represents the outcome of a data fetch operation. Contains table name, row count, data type, duration, date range, and timestamp.

- **Query Results**: Live query operations return specialized result types depending on the query type:
  - `SegmentationResult`: For segmentation queries (event counts over time, optionally segmented by property)
  - `FunnelResult`: For funnel queries (step-by-step conversion analysis)
  - `RetentionResult`: For retention queries (cohort-based return behavior)
  - `JQLResult`: For custom JQL queries (raw result data)

  All query result types share common behaviors: `to_dict()` for serialization and a lazy `df` property for DataFrame conversion.

### Assumptions

- Configuration files use a standard location (`~/.mp/config.toml`) following XDG conventions.
- File-based configuration is acceptable; database-backed configuration is not required.
- Single-user access patterns are sufficient; multi-user concurrent access is out of scope.
- Environment variable names follow the pattern `MP_*` (e.g., `MP_USERNAME`, `MP_SECRET`).
- Region values are limited to known Mixpanel regions: US, EU, India.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Developers can configure and retrieve credentials for a new project in under 30 seconds.
- **SC-002**: 100% of error scenarios produce specific, actionable error messages (no generic "something went wrong" errors).
- **SC-003**: All operation results include timing information accurate to the millisecond.
- **SC-004**: Zero credential leakage in logs or error output (verified through security testing).
- **SC-005**: Library consumers can catch all library-specific errors with a single exception type.
- **SC-006**: Result types support common data science workflows without additional transformation code.
