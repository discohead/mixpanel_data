# Feature Specification: Fetch Service

**Feature Branch**: `005-fetch-service`
**Created**: 2025-12-22
**Status**: Draft
**Input**: User description: "Phase 005 Fetch Service"

## Overview

The Fetch Service enables users to retrieve event and profile data from Mixpanel's Export API and store it in a local database for offline analysis. This service bridges the gap between the API client (which streams raw data) and the storage engine (which persists transformed data), handling data transformation, progress reporting, and result metadata.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Fetch Events into Local Database (Priority: P1)

As a data analyst, I want to fetch a date range of events from Mixpanel into my local database so that I can query them repeatedly with SQL without consuming API calls or waiting for network requests.

**Why this priority**: This is the core use case of the entire mixpanel_data library. Events are the primary data type in Mixpanel, and local storage enables fast, iterative analysis that preserves context window for AI agents.

**Independent Test**: Can be fully tested by fetching events for a date range and verifying they are queryable via SQL, delivering immediate analytical value.

**Acceptance Scenarios**:

1. **Given** valid credentials and a date range, **When** the user fetches events, **Then** all events within that date range are stored in a new table with the specified name
2. **Given** valid credentials and a date range, **When** the user fetches events with an event name filter, **Then** only events matching the specified names are stored
3. **Given** valid credentials and a date range, **When** the user fetches events with a where filter, **Then** only events matching the filter expression are stored
4. **Given** an ongoing fetch operation, **When** progress is made, **Then** the progress callback is invoked with the current count
5. **Given** a completed fetch operation, **When** the result is returned, **Then** it includes the table name, row count, duration, date range, and completion timestamp

---

### User Story 2 - Fetch User Profiles into Local Database (Priority: P2)

As a data analyst, I want to fetch user profiles from Mixpanel into my local database so that I can join profile attributes with event data for enriched analysis.

**Why this priority**: Profiles are the second most important data type. While events are essential, profiles enable richer analysis by providing user attributes for segmentation and cohort analysis.

**Independent Test**: Can be fully tested by fetching profiles and verifying they are queryable via SQL, delivering user attribute data for analysis.

**Acceptance Scenarios**:

1. **Given** valid credentials, **When** the user fetches profiles, **Then** all profiles are stored in a new table with the specified name
2. **Given** valid credentials, **When** the user fetches profiles with a where filter, **Then** only profiles matching the filter expression are stored
3. **Given** an ongoing fetch operation, **When** progress is made, **Then** the progress callback is invoked with the current count
4. **Given** a completed fetch operation, **When** the result is returned, **Then** it includes the table name, row count, duration, and completion timestamp (with no date range since profiles are not time-bounded)

---

### User Story 3 - Explicit Table Management (Priority: P1)

As a developer, I want the system to prevent accidental data overwrites so that I don't lose previously fetched data by mistake.

**Why this priority**: Data integrity is critical. Accidental overwrites could lose hours of fetched data. This safety mechanism is essential for reliable operation.

**Independent Test**: Can be tested by attempting to fetch into an existing table name and verifying the appropriate error is raised.

**Acceptance Scenarios**:

1. **Given** a table with the specified name already exists, **When** the user attempts to fetch events, **Then** an error is raised indicating the table exists
2. **Given** a table with the specified name already exists, **When** the user attempts to fetch profiles, **Then** an error is raised indicating the table exists
3. **Given** the error message, **When** the user reads it, **Then** it clearly indicates they must explicitly drop the existing table before refetching

---

### User Story 4 - Progress Monitoring for Long Operations (Priority: P3)

As a user running a large data fetch, I want to see progress updates so that I know the operation is working and can estimate completion time.

**Why this priority**: While not required for basic functionality, progress feedback significantly improves user experience for operations that may take minutes or longer.

**Independent Test**: Can be tested by fetching a dataset and verifying the progress callback receives incremental updates throughout the operation.

**Acceptance Scenarios**:

1. **Given** a fetch operation with a progress callback provided, **When** data is being fetched, **Then** the callback is invoked periodically with the cumulative count
2. **Given** a fetch operation without a progress callback, **When** data is being fetched, **Then** the operation completes successfully without errors

---

### Edge Cases

- What happens when the API returns zero events for the date range? (Empty table should be created with zero rows)
- What happens when the API returns zero profiles? (Empty table should be created with zero rows)
- What happens when an event is missing the $insert_id field? (Should handle gracefully with a generated or default value)
- What happens when a profile is missing the $last_seen field? (Should handle gracefully with null or current timestamp)
- What happens when the API connection fails mid-fetch? (Transaction should rollback, no partial table created)
- What happens when the storage engine fails during ingestion? (Transaction should rollback, error should propagate)
- What happens when invalid date format is provided? (Clear validation error before API call)

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST fetch events from Mixpanel Export API and store them in the local database
- **FR-002**: System MUST fetch user profiles from Mixpanel Engage API and store them in the local database
- **FR-003**: System MUST transform event data from API format to storage format:
  - Extract `event` field to `event_name`
  - Extract `properties.time` to `event_time`
  - Extract `properties.distinct_id` to `distinct_id`
  - Extract `properties.$insert_id` to `insert_id`
  - Store remaining properties as JSON in `properties` column
- **FR-004**: System MUST transform profile data from API format to storage format:
  - Extract `$distinct_id` to `distinct_id`
  - Extract `$properties.$last_seen` to `last_seen`
  - Store remaining `$properties` as JSON in `properties` column
- **FR-005**: System MUST support filtering events by event names (list of strings)
- **FR-006**: System MUST support filtering events and profiles by where expression
- **FR-007**: System MUST support progress callbacks that receive the current row count
- **FR-008**: System MUST return a result object containing: table name, row count, data type, duration, date range (for events), and completion timestamp
- **FR-009**: System MUST raise an error if the target table already exists
- **FR-010**: System MUST rollback the transaction if any error occurs during the fetch operation
- **FR-011**: System MUST stream data from API to storage without loading entire dataset into memory
- **FR-012**: System MUST record metadata about the fetch operation (type, dates, filters) in the database

### Key Entities

- **FetchResult**: The outcome of a fetch operation, containing the table name, row count, data type (events/profiles), duration in seconds, date range (for events only), and completion timestamp
- **TableMetadata**: Information about a fetch operation stored in the database, including type, fetch timestamp, date range, and applied filters
- **Event Record**: A transformed event containing event_name, event_time, distinct_id, insert_id, and properties (JSON)
- **Profile Record**: A transformed profile containing distinct_id, last_seen timestamp, and properties (JSON)

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Users can fetch and store 100,000 events in a single operation without memory issues
- **SC-002**: Fetch operations complete with accurate duration timing (within 1 second of actual elapsed time)
- **SC-003**: Progress callbacks are invoked at regular intervals during fetch operations (not less frequently than every 2,000 records)
- **SC-004**: All fetched data is queryable via SQL immediately after fetch completion
- **SC-005**: Zero data loss when fetch operations complete successfully (all records from API appear in database)
- **SC-006**: Zero partial tables when fetch operations fail (complete rollback on any error)
- **SC-007**: Clear, actionable error messages when table already exists (user understands how to resolve)

## Assumptions

- The MixpanelAPIClient (Phase 002) is fully implemented and provides streaming iterators for export_events() and export_profiles()
- The StorageEngine (Phase 003) is fully implemented and provides create_events_table() and create_profiles_table() methods
- The FetchResult and TableMetadata types are already defined in the types module
- Events always have an `event` field and `properties` dict containing `distinct_id`, `time`, and `$insert_id`
- Profiles always have a `$distinct_id` field and `$properties` dict (which may or may not contain `$last_seen`)
- Date parameters are provided in YYYY-MM-DD format
- Progress callbacks are optional and may be None

## Dependencies

- Phase 002: API Client (provides MixpanelAPIClient with export_events and export_profiles methods)
- Phase 003: Storage Engine (provides StorageEngine with create_events_table and create_profiles_table methods)
- Phase 001: Foundation Layer (provides exception types and result types)
