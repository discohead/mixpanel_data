# Feature Specification: Streaming API

**Feature Branch**: `011-streaming-api`
**Created**: 2024-12-24
**Status**: Draft
**Input**: User description: "Add streaming API capability to bypass database and return raw data directly from Mixpanel API, enabling the library and CLI to function as a pure SDK for the Mixpanel HTTP API without local storage."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Stream Events for ETL Pipeline (Priority: P1)

A data engineer needs to export Mixpanel events to their data warehouse without creating local files. They want to iterate through events one-by-one and send each to their ingestion pipeline, processing millions of events without exhausting memory.

**Why this priority**: This is the core use case—enabling the library to function as a pure API SDK for data pipelines, which is currently impossible since all fetches require database storage.

**Independent Test**: Can be fully tested by calling the streaming method and iterating over results while verifying no database files are created. Delivers immediate value for ETL workflows.

**Acceptance Scenarios**:

1. **Given** valid credentials are configured, **When** user calls the event streaming method with a date range, **Then** events are yielded one at a time without creating any database files
2. **Given** a streaming operation is in progress, **When** 1 million events are processed, **Then** memory usage remains constant (not proportional to dataset size)
3. **Given** valid credentials, **When** user streams events with event name filters, **Then** only matching events are returned
4. **Given** valid credentials, **When** user streams events with a WHERE filter, **Then** only events matching the filter expression are returned

---

### User Story 2 - CLI Export to Standard Output (Priority: P1)

A developer wants to export Mixpanel data and pipe it to other command-line tools (jq, grep, custom scripts) or redirect to a file. They need the CLI to output data to stdout in a format suitable for streaming.

**Why this priority**: CLI streaming is essential for Unix-style workflows and automation scripts. It enables integration with the broader command-line ecosystem.

**Independent Test**: Can be fully tested by running the CLI with streaming output and piping to standard tools like `jq` or redirecting to a file. Delivers value for automation and scripting.

**Acceptance Scenarios**:

1. **Given** valid credentials, **When** user runs the fetch command with stdout mode, **Then** events are output line-by-line to stdout
2. **Given** stdout mode is enabled, **When** output is piped to another tool, **Then** each line is valid JSON that can be parsed independently
3. **Given** stdout mode is enabled, **When** user redirects output to a file, **Then** the resulting file contains one JSON object per line
4. **Given** stdout mode is enabled, **When** no table name is provided, **Then** the operation succeeds (table name is not required for streaming)

---

### User Story 3 - Stream User Profiles (Priority: P2)

A data analyst needs to export user profiles for processing in an external system. Similar to events, they want to stream profiles without local storage.

**Why this priority**: Profiles are the second major data type in Mixpanel. Enabling streaming for both events and profiles provides complete coverage.

**Independent Test**: Can be fully tested by calling the profile streaming method and verifying profiles are returned without database files. Delivers value for user data export workflows.

**Acceptance Scenarios**:

1. **Given** valid credentials, **When** user calls the profile streaming method, **Then** profiles are yielded one at a time without creating any database files
2. **Given** valid credentials, **When** user streams profiles with a WHERE filter, **Then** only profiles matching the filter expression are returned
3. **Given** a project with many profiles, **When** user streams all profiles, **Then** memory usage remains constant regardless of profile count

---

### User Story 4 - Choose Output Format (Priority: P2)

A developer integrating with a legacy system needs events in Mixpanel's exact API format. Another developer wants the normalized format that matches stored data. Both should be supported.

**Why this priority**: Format flexibility enables integration with diverse downstream systems. The normalized format provides consistency with stored data while raw format enables direct API pass-through.

**Independent Test**: Can be fully tested by streaming with each format option and verifying the output structure matches expectations. Delivers value for integration flexibility.

**Acceptance Scenarios**:

1. **Given** default settings, **When** user streams events, **Then** events are returned in normalized format with extracted standard fields and converted timestamps
2. **Given** raw format is requested, **When** user streams events, **Then** events are returned in exact Mixpanel API format with nested properties
3. **Given** default settings, **When** user streams profiles, **Then** profiles are returned in normalized format
4. **Given** raw format is requested, **When** user streams profiles, **Then** profiles are returned in exact Mixpanel API format with `$distinct_id` and `$properties` keys

---

### Edge Cases

- What happens when streaming is interrupted mid-operation? The iterator stops yielding; already-processed records are not lost since they were consumed in real-time
- How does system handle rate limiting during streaming? Same as fetch operations—automatic retry with backoff (transparent to user)
- What happens when credentials are invalid? Authentication error is raised immediately, before any data is yielded
- What happens when the date range returns zero events? The iterator completes immediately with no items yielded (not an error)
- How does CLI streaming handle progress display? Progress goes to stderr so stdout remains clean for piping
- What happens when stdout mode is combined with a table name argument? The table name is ignored when streaming to stdout

## Requirements *(mandatory)*

### Functional Requirements

**Library Streaming Methods:**

- **FR-001**: System MUST provide a method to stream events directly from the API without storing locally
- **FR-002**: System MUST provide a method to stream profiles directly from the API without storing locally
- **FR-003**: Streaming methods MUST accept the same filter parameters as fetch methods (date range, event names, WHERE clause)
- **FR-004**: Streaming methods MUST yield records one at a time (not buffer the entire response)
- **FR-005**: Streaming methods MUST NOT create any database files or tables
- **FR-006**: Streaming methods MUST support two output formats: normalized (default) and raw API format
- **FR-007**: Normalized format MUST match the structure of data stored by fetch methods
- **FR-008**: Raw format MUST return data exactly as received from the Mixpanel API

**CLI Streaming Support:**

- **FR-009**: CLI fetch commands MUST support an option to output to stdout instead of storing
- **FR-010**: CLI stdout mode MUST output one JSON object per line (JSONL format)
- **FR-011**: CLI stdout mode MUST make the table name argument optional
- **FR-012**: CLI MUST support selecting between normalized and raw output formats
- **FR-013**: CLI MUST send progress information to stderr when stdout mode is enabled

**Error Handling:**

- **FR-014**: Streaming MUST handle authentication errors by raising an error before yielding any data
- **FR-015**: Streaming MUST handle rate limiting transparently with automatic retry
- **FR-016**: Streaming MUST handle network errors consistently with fetch operations

**Backward Compatibility:**

- **FR-017**: All existing fetch functionality MUST remain unchanged
- **FR-018**: Default behavior of fetch commands (without stdout flag) MUST continue to store data

### Key Entities

- **Streamed Event**: A single event record from Mixpanel, either in normalized format (event_name, event_time, distinct_id, insert_id, properties) or raw API format (event, properties with embedded fields)
- **Streamed Profile**: A single user profile record from Mixpanel, either in normalized format (distinct_id, last_seen, properties) or raw API format ($distinct_id, $properties)
- **JSONL Output**: A text stream where each line is a complete, valid JSON object representing one record

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Users can process 1 million events with constant memory usage (no growth proportional to dataset size)
- **SC-002**: Streaming operation completes without any database files being created on disk
- **SC-003**: CLI output can be successfully piped to `jq` and parsed without errors
- **SC-004**: 100% of filter parameters available in fetch methods work identically in streaming methods
- **SC-005**: Existing fetch operations continue to work without any changes to user code
- **SC-006**: Users can switch between fetch (store) and stream modes using the same credential configuration
- **SC-007**: Both normalized and raw output formats produce valid, parseable data structures

## Assumptions

- The underlying API client already supports streaming responses (iterators) without buffering
- Transformation functions for normalizing event/profile data are already implemented and reusable
- Rate limiting and retry logic from fetch operations can be reused for streaming
- CLI framework supports sending output to stdout while keeping progress on stderr
- JSONL is an acceptable output format for CLI streaming (no request for CSV, XML, or other formats)
