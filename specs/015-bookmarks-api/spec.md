# Feature Specification: Bookmarks API for Saved Reports

**Feature Branch**: `015-bookmarks-api`
**Created**: 2025-12-25
**Status**: Draft
**Input**: User description: "Implement Bookmarks API for listing and querying saved reports"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - List Saved Reports (Priority: P1)

As a data analyst, I want to list all saved reports (bookmarks) in my Mixpanel project so I can discover what reports exist and find their IDs for querying.

**Why this priority**: This is the foundational capability that enables all other bookmark features. Without being able to discover saved reports and their IDs, users cannot query them programmatically.

**Independent Test**: Can be fully tested by listing bookmarks and verifying the returned metadata matches what's visible in the Mixpanel UI. Delivers immediate value by enabling programmatic discovery of saved reports.

**Acceptance Scenarios**:

1. **Given** a project with saved reports, **When** I request a list of all bookmarks, **Then** I receive a list containing each report's ID, name, type, creation date, and modification date.

2. **Given** a project with multiple report types, **When** I filter bookmarks by type (e.g., "insights", "retention", "funnels", "flows"), **Then** I receive only bookmarks matching that type.

3. **Given** valid credentials, **When** I list bookmarks, **Then** each bookmark includes sufficient metadata to identify and query it (ID, name, type, timestamps).

4. **Given** invalid or missing credentials, **When** I attempt to list bookmarks, **Then** I receive a clear authentication error.

---

### User Story 2 - Query Saved Reports (Priority: P1)

As a data analyst, I want to query saved Insights, Retention, and Funnel reports by their bookmark ID so I can retrieve report data programmatically without recreating the query configuration.

**Why this priority**: This is the core data retrieval capability. It enables users to execute saved reports and get results, which is the primary use case for the Bookmarks API.

**Independent Test**: Can be fully tested by querying a known saved report by ID and verifying the returned data matches the report visible in the Mixpanel UI.

**Acceptance Scenarios**:

1. **Given** a valid bookmark ID for an Insights report, **When** I query that saved report, **Then** I receive the report data including computed timestamp, date range, and series data.

2. **Given** a valid bookmark ID for a Retention report, **When** I query that saved report, **Then** I receive cohort retention data with counts and rates, and I can identify it as a retention report.

3. **Given** a valid bookmark ID for a Funnel report, **When** I query that saved report, **Then** I receive funnel step conversion data, and I can identify it as a funnel report.

4. **Given** an invalid or non-existent bookmark ID, **When** I attempt to query, **Then** I receive a clear error indicating the report was not found.

5. **Given** a bookmark ID for a report I don't have permission to access, **When** I attempt to query, **Then** I receive a clear permission error.

---

### User Story 3 - Query Saved Flows Reports (Priority: P2)

As a data analyst, I want to query saved Flows reports by their bookmark ID so I can retrieve user navigation path data programmatically.

**Why this priority**: Flows reports require a different query approach than other report types. While valuable, this is a specialized report type with fewer saved instances.

**Independent Test**: Can be fully tested by querying a known Flows bookmark and verifying the returned path data and conversion rates match the report in the Mixpanel UI.

**Acceptance Scenarios**:

1. **Given** a valid bookmark ID for a Flows report, **When** I query that flows report, **Then** I receive step data, breakdown data, and overall conversion rate.

2. **Given** a non-flows bookmark ID, **When** I attempt to query it as a flows report, **Then** I receive a clear error indicating the bookmark type mismatch.

---

### User Story 4 - CLI Access to Bookmarks (Priority: P2)

As a developer or analyst using the command line, I want CLI commands to list and query saved reports so I can integrate bookmark data into scripts and automation pipelines.

**Why this priority**: CLI access extends the programmatic API to command-line workflows, enabling scripting and automation. Important for power users but builds on the core API functionality.

**Independent Test**: Can be fully tested by running CLI commands and verifying output matches expected formats (JSON, table).

**Acceptance Scenarios**:

1. **Given** the CLI is configured with valid credentials, **When** I run the command to list bookmarks, **Then** I see a list of saved reports in the specified format (JSON or table).

2. **Given** a valid bookmark ID, **When** I run the command to query a saved report, **Then** I receive the report data in the specified output format.

3. **Given** a valid flows bookmark ID, **When** I run the command to query flows, **Then** I receive the flows data in the specified output format.

4. **Given** I want to filter bookmarks, **When** I specify a type filter in the CLI, **Then** only bookmarks of that type are returned.

---

### Edge Cases

- What happens when a bookmark exists but the underlying data has been deleted? System returns an appropriate error message.
- How does the system handle bookmarks with restricted visibility? Users receive a permission error for reports they cannot access.
- What happens when querying a bookmark during report computation? System returns the most recently computed results or indicates the report is being computed.
- How are bookmarks in different workspaces handled? Bookmarks are scoped to the authenticated project; workspace-scoped bookmarks include workspace metadata.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST provide a method to list all saved reports (bookmarks) for the authenticated project.
- **FR-002**: System MUST support filtering the bookmark list by report type (insights, funnels, retention, flows).
- **FR-003**: System MUST return bookmark metadata including: unique ID, user-defined name, report type, project ID, creation timestamp, and modification timestamp.
- **FR-004**: System MUST return optional bookmark metadata when available: workspace ID, dashboard ID, description, creator information.
- **FR-005**: System MUST provide a method to query saved Insights, Retention, and Funnel reports using their bookmark ID.
- **FR-006**: System MUST indicate the report type in query results so users can determine how to interpret the data (insights, retention, or funnel).
- **FR-007**: System MUST provide a separate method to query saved Flows reports using their bookmark ID.
- **FR-008**: System MUST return flows-specific data: step data, breakdown data, overall conversion rate, and computation timestamp.
- **FR-009**: System MUST propagate authentication errors when credentials are invalid or missing.
- **FR-010**: System MUST propagate query errors when bookmark IDs are invalid, not found, or inaccessible.
- **FR-011**: System MUST provide CLI commands for listing bookmarks and querying saved reports.
- **FR-012**: CLI commands MUST support multiple output formats (JSON, table).

### Key Entities

- **BookmarkInfo**: Represents metadata about a saved report. Contains: unique identifier, user-defined name, report type, project association, timestamps (created/modified), and optional workspace/dashboard associations.

- **SavedReportResult**: Represents data returned from querying a saved Insights, Retention, or Funnel report. Contains: bookmark ID, computation timestamp, date range, column headers, and series data. The report type can be determined from the data structure.

- **FlowsResult**: Represents data returned from querying a saved Flows report. Contains: bookmark ID, computation timestamp, step data, breakdown data, and overall conversion rate.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Users can discover all saved reports in their project within a single operation.
- **SC-002**: Users can filter saved reports by type to quickly find specific report categories.
- **SC-003**: Users can query any saved Insights, Retention, or Funnel report using only its bookmark ID.
- **SC-004**: Users can query any saved Flows report using only its bookmark ID.
- **SC-005**: Users can determine the report type (insights, retention, funnel) from the query result without prior knowledge.
- **SC-006**: CLI users can list bookmarks and query saved reports with output in JSON or table format.
- **SC-007**: All bookmark operations provide clear, actionable error messages for authentication failures, permission issues, and invalid bookmark IDs.
- **SC-008**: Bookmark listing and querying work correctly across all supported data residency regions (US, EU, India).

## Assumptions

- Users have valid service account credentials configured for their Mixpanel project.
- Bookmark IDs are stable identifiers that persist across API calls.
- The API version parameter (v=2) provides the expected response format for bookmark listing.
- Saved reports retain their bookmark IDs even when modified.
- The "launch-analysis" bookmark type exists but may be excluded from initial implementation scope as it's less commonly used.
