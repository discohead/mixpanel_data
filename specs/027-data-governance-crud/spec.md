# Feature Specification: Data Governance CRUD

**Feature Branch**: `027-data-governance-crud`  
**Created**: 2026-04-01  
**Status**: Draft  
**Input**: User description: "Phase 4: Data Governance (Lexicon + Custom + Drop Filters + Lookup Tables) — Domains 9-13 from Rust parity gap analysis"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Manage Event and Property Definitions (Priority: P1)

A data governance lead needs to view, update, and delete event and property definitions (the "Lexicon") to maintain a clean, well-documented data taxonomy. They update display names, descriptions, mark events as hidden or dropped, assign tags, and bulk-update definitions across dozens of events at once.

**Why this priority**: Data definitions are the foundation of data governance. Every other domain (custom properties, drop filters, lookup tables) builds on a well-maintained taxonomy. This is the highest-value capability for data teams.

**Independent Test**: Can be fully tested by updating an event definition's description and verifying the change persists, then bulk-updating multiple event definitions and confirming all changes applied. Delivers immediate value for data catalog management.

**Acceptance Scenarios**:

1. **Given** a project with tracked events, **When** the user retrieves event definitions by name, **Then** the system returns definition details including display name, description, hidden/dropped status, and tags.
2. **Given** an event definition, **When** the user updates its description and marks it as verified, **Then** the definition reflects the new description and verified status.
3. **Given** an event that is no longer relevant, **When** the user deletes the event definition, **Then** it is removed from the project's data catalog.
4. **Given** a property definition, **When** the user retrieves it by name and resource type, **Then** the system returns the property's metadata including sensitivity and drop status.
5. **Given** a property definition, **When** the user updates it to mark it as sensitive, **Then** the property is flagged as sensitive in the catalog.
6. **Given** 20 event definitions needing tag updates, **When** the user bulk-updates all 20 with new tags, **Then** all 20 definitions reflect the updated tags.
7. **Given** 15 property definitions needing description changes, **When** the user bulk-updates all 15, **Then** all 15 reflect the new descriptions.

---

### User Story 2 - Manage Lexicon Tags (Priority: P1)

A data governance lead needs to create and manage tags used to organize event and property definitions. Tags provide categorization (e.g., "core-metrics", "deprecated", "pii") that helps teams navigate large data catalogs.

**Why this priority**: Tags are integral to definition management (Story 1) — they're used in bulk updates and definition organization. Without tag management, the definition workflow is incomplete.

**Independent Test**: Can be tested by creating a tag, listing all tags to verify it appears, then updating and deleting it. Delivers value as a standalone catalog organization feature.

**Acceptance Scenarios**:

1. **Given** a project, **When** the user lists all lexicon tags, **Then** the system returns all tags with their IDs and names.
2. **Given** a project, **When** the user creates a tag named "core-metrics", **Then** the tag is created and available for assignment to definitions.
3. **Given** an existing tag, **When** the user renames it, **Then** the tag name is updated across the system.
4. **Given** an existing tag no longer needed, **When** the user deletes it, **Then** the tag is removed.

---

### User Story 3 - Manage Drop Filters (Priority: P2)

A data engineer needs to create and manage event drop filters to prevent unwanted event data from being ingested. Drop filters reduce data volume and costs by filtering events at the ingestion layer before they're stored.

**Why this priority**: Drop filters directly impact data quality and cost. They are a critical governance tool but are less frequently used than definition management.

**Independent Test**: Can be tested by creating a drop filter for a specific event, listing filters to confirm it exists, then updating and deleting it. Delivers immediate cost-saving value.

**Acceptance Scenarios**:

1. **Given** a project, **When** the user lists all drop filters, **Then** the system returns all filters with event names, filter conditions, and active status.
2. **Given** a project, **When** the user creates a drop filter for event "debug_log" with specific property conditions, **Then** matching events are filtered at ingestion.
3. **Given** an existing drop filter, **When** the user updates it to change filter conditions or toggle active status, **Then** the filter behavior changes accordingly.
4. **Given** an existing drop filter, **When** the user deletes it, **Then** events matching the former filter resume normal ingestion.
5. **Given** a project approaching its filter limit, **When** the user checks drop filter limits, **Then** the system returns the current count and maximum allowed.

---

### User Story 4 - Manage Custom Properties (Priority: P2)

A data analyst needs to create and manage custom computed properties — derived fields calculated from existing properties using formulas. Custom properties extend the data model without modifying the tracking implementation.

**Why this priority**: Custom properties enable advanced analysis without requiring engineering changes to tracking code. They're used frequently by analytics teams but depend on a well-maintained taxonomy (Story 1).

**Independent Test**: Can be tested by creating a custom property with a formula, validating the formula, retrieving the property, then updating and deleting it. Delivers analytical flexibility.

**Acceptance Scenarios**:

1. **Given** a project, **When** the user lists all custom properties, **Then** the system returns all properties with names, descriptions, resource types, and formulas.
2. **Given** a project, **When** the user creates a custom property with a valid formula, **Then** the property is available for use in queries and reports.
3. **Given** a custom property, **When** the user retrieves it by ID, **Then** the system returns full details including formula and composed properties.
4. **Given** a custom property, **When** the user updates its formula or description, **Then** the property reflects the changes.
5. **Given** a custom property no longer needed, **When** the user deletes it, **Then** it is removed from the project.
6. **Given** a formula expression, **When** the user validates it before creating a custom property, **Then** the system reports whether the formula is valid or identifies errors.

---

### User Story 5 - Manage Lookup Tables (Priority: P2)

A data engineer needs to upload and manage lookup tables — CSV-based reference data that enriches events and profiles with additional attributes (e.g., mapping product IDs to product names, SKU to category).

**Why this priority**: Lookup tables are essential for data enrichment but involve a more complex workflow (upload to cloud storage, then register). They're used less frequently than definitions or custom properties.

**Independent Test**: Can be tested by listing existing lookup tables, uploading a new CSV file, checking upload status, then downloading and deleting it. Delivers data enrichment capability.

**Acceptance Scenarios**:

1. **Given** a project, **When** the user lists all lookup tables, **Then** the system returns all tables with names, IDs, and metadata.
2. **Given** a CSV file, **When** the user uploads a new lookup table, **Then** the system completes the multi-step upload (obtain upload URL, upload file, register table).
3. **Given** an uploaded lookup table, **When** the user checks upload status, **Then** the system reports whether the upload is complete or still processing.
4. **Given** a lookup table, **When** the user updates its name, **Then** the name is changed.
5. **Given** a lookup table, **When** the user downloads it, **Then** the system returns the table data as CSV.
6. **Given** a lookup table no longer needed, **When** the user deletes it, **Then** it is removed from the project.
7. **Given** a lookup table, **When** the user requests a download URL, **Then** the system returns a signed URL for direct download.

---

### User Story 6 - Manage Custom Events (Priority: P3)

A data analyst needs to list, update, and delete custom events — composite events defined as combinations of existing events. Custom events simplify complex analyses by grouping related actions under a single event name.

**Why this priority**: Custom events are managed through the same data definitions infrastructure as Story 1 but are a less common operation. Most teams use the Mixpanel UI for custom event creation.

**Independent Test**: Can be tested by listing custom events, updating one's definition, and deleting one. Delivers catalog management capability.

**Acceptance Scenarios**:

1. **Given** a project with custom events, **When** the user lists all custom events, **Then** the system returns all custom events with names and definitions.
2. **Given** a custom event, **When** the user updates its definition, **Then** the custom event reflects the changes.
3. **Given** a custom event no longer needed, **When** the user deletes it, **Then** it is removed from the project.

---

### User Story 7 - View Tracking Metadata and Definition History (Priority: P3)

A data governance lead needs to inspect tracking metadata for events (which SDKs track them, sample payloads) and review the change history of event and property definitions to audit who changed what and when.

**Why this priority**: Tracking metadata and history are read-only audit capabilities. They support governance workflows but don't modify data, making them lower risk and lower urgency.

**Independent Test**: Can be tested by retrieving tracking metadata for a known event and viewing its definition history. Delivers audit and debugging capability.

**Acceptance Scenarios**:

1. **Given** an event being tracked, **When** the user requests its tracking metadata, **Then** the system returns SDK information and recent tracking details.
2. **Given** an event definition, **When** the user requests its change history, **Then** the system returns a chronological list of changes with timestamps and authors.
3. **Given** a property definition, **When** the user requests its change history by name and entity type, **Then** the system returns the property's change history.

---

### User Story 8 - Export Lexicon Definitions (Priority: P3)

A data governance lead needs to export the complete data catalog (event definitions, property definitions, or both) for documentation, compliance, or migration purposes.

**Why this priority**: Export is a read-only bulk operation used occasionally for documentation or compliance. Low frequency but important when needed.

**Independent Test**: Can be tested by exporting all event definitions and verifying the export contains the expected data. Delivers compliance and documentation capability.

**Acceptance Scenarios**:

1. **Given** a project with tracked events, **When** the user exports event definitions, **Then** the system returns a complete export of all event definitions.
2. **Given** a project, **When** the user exports property definitions, **Then** the system returns a complete export of all property definitions.
3. **Given** a project, **When** the user exports both event and property definitions, **Then** the system returns a combined export.

---

### Edge Cases

- What happens when a user tries to delete an event definition that is referenced by a custom property or drop filter?
- How does the system handle bulk updates where some entries succeed and others fail (partial failure)?
- What happens when a user tries to upload a lookup table CSV that exceeds the maximum file size?
- What happens when a user checks upload status for a lookup table upload that has expired or been cleaned up?
- How does the system handle creating a drop filter when the account has reached its filter limit?
- What happens when a user tries to create a custom property with a formula referencing a non-existent property?
- How does the system handle network interruption during the multi-step lookup table upload process?

## Requirements *(mandatory)*

### Functional Requirements

**Data Definitions (Lexicon)**

- **FR-001**: System MUST retrieve event definitions by name, returning display name, description, hidden/dropped status, and tags.
- **FR-002**: System MUST update individual event definitions with changes to hidden, dropped, merged, verified status, tags, and description.
- **FR-003**: System MUST delete individual event definitions by name.
- **FR-004**: System MUST retrieve property definitions by name and resource type (event, user profile, or group profile), returning description, hidden/dropped/sensitive status.
- **FR-005**: System MUST update individual property definitions with changes to hidden, dropped, merged, sensitive status, and description.
- **FR-006**: System MUST bulk-update multiple event definitions in a single operation with changes to tags, descriptions, and status fields.
- **FR-007**: System MUST bulk-update multiple property definitions in a single operation.
- **FR-008**: System MUST retrieve tracking metadata for a named event.
- **FR-009**: System MUST retrieve change history for a named event definition.
- **FR-010**: System MUST retrieve change history for a named property definition filtered by entity type.
- **FR-011**: System MUST export lexicon definitions filtered by export type (events, properties, or both).

**Lexicon Tags**

- **FR-012**: System MUST list all lexicon tags in a project.
- **FR-013**: System MUST create new lexicon tags by name.
- **FR-014**: System MUST update existing lexicon tags by ID.
- **FR-015**: System MUST delete lexicon tags by name.

**Drop Filters**

- **FR-016**: System MUST list all event drop filters in a project.
- **FR-017**: System MUST create drop filters specifying event name and filter conditions.
- **FR-018**: System MUST update existing drop filters including event name, conditions, and active status.
- **FR-019**: System MUST delete drop filters by ID.
- **FR-020**: System MUST retrieve drop filter account limits showing current usage and maximum allowed.

**Custom Properties**

- **FR-021**: System MUST list all custom properties in a project.
- **FR-022**: System MUST create custom properties with name, resource type, formula, composed properties, and behavior.
- **FR-023**: System MUST retrieve individual custom properties by ID.
- **FR-024**: System MUST update custom properties including name, description, formula, and composed properties.
- **FR-025**: System MUST delete custom properties by ID.
- **FR-026**: System MUST validate custom property formulas before creation, returning validity status and error details.

**Custom Events**

- **FR-027**: System MUST list all custom events in a project.
- **FR-028**: System MUST update custom event definitions.
- **FR-029**: System MUST delete custom events.

**Lookup Tables**

- **FR-030**: System MUST list all lookup tables in a project, optionally filtered by data group ID.
- **FR-031**: System MUST support multi-step lookup table upload: obtain a signed upload URL, upload CSV to that URL, then register/mark the table as ready.
- **FR-032**: System MUST check lookup table upload status by upload ID.
- **FR-033**: System MUST update lookup table metadata (e.g., name).
- **FR-034**: System MUST delete lookup tables by data group ID(s).
- **FR-035**: System MUST retrieve signed upload URLs for lookup table CSV uploads.
- **FR-036**: System MUST download lookup table data as CSV.
- **FR-037**: System MUST retrieve signed download URLs for lookup tables.

**CLI**

- **FR-038**: System MUST provide CLI commands for all lexicon operations grouped under `mp lexicon`.
- **FR-039**: System MUST provide CLI commands for custom property operations grouped under `mp custom-properties`.
- **FR-040**: System MUST provide CLI commands for custom event operations grouped under `mp custom-events`.
- **FR-041**: System MUST provide CLI commands for drop filter operations grouped under `mp drop-filters`.
- **FR-042**: System MUST provide CLI commands for lookup table operations grouped under `mp lookup-tables`.
- **FR-043**: All CLI commands MUST support the standard output formats (json, jsonl, table, csv, plain).

### Key Entities

- **Event Definition**: Metadata about a tracked event — display name, description, hidden/dropped/verified status, tags. Identified by event name.
- **Property Definition**: Metadata about an event or profile property — description, hidden/dropped/sensitive/merged status, resource type (event, user profile, group profile). Identified by name and resource type.
- **Lexicon Tag**: A named label for organizing event and property definitions. Has an ID and a name.
- **Drop Filter**: A rule that prevents specific events from being ingested based on event name and property conditions. Has an ID, event name, filter conditions, active status, and display name.
- **Custom Property**: A computed property derived from existing properties via a formula. Has an ID, name, description, resource type, display formula, composed properties, and behavior.
- **Custom Event**: A composite event defined as a combination of existing events. Managed through the data definitions infrastructure.
- **Lookup Table**: A CSV-based reference table for enriching events and profiles. Has an ID, name, token, creation date, and mapped properties flag. Upload involves a multi-step signed-URL workflow.
- **Tracking Metadata**: Read-only information about how an event is being tracked — SDK details, sample payloads.
- **Definition History**: A chronological record of changes to an event or property definition, including timestamps and authors.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Users can retrieve, update, and delete event and property definitions individually and in bulk through both the library and CLI.
- **SC-002**: Users can manage lexicon tags (create, list, update, delete) to organize their data catalog.
- **SC-003**: Users can create, update, delete, and check limits on drop filters to control data ingestion.
- **SC-004**: Users can create, validate, update, and delete custom properties with formula-based definitions.
- **SC-005**: Users can list, update, and delete custom events.
- **SC-006**: Users can upload, download, update, and delete lookup tables including the multi-step upload workflow.
- **SC-007**: Users can view tracking metadata and definition change history for audit purposes.
- **SC-008**: Users can export the full data catalog (events, properties, or both) for compliance and documentation.
- **SC-009**: All operations are accessible via CLI commands with consistent output formatting across all 5 supported formats.
- **SC-010**: All operations maintain parity with the equivalent Rust implementation across all 5 domains (Domains 9-13 from gap analysis).

## Assumptions

- OAuth 2.0 PKCE authentication and App API infrastructure (Domains 0a and 0b) are already implemented and working. This feature builds on that foundation.
- The existing `app_request()` method, workspace scoping via `maybe_scoped_path()`, and cursor-based pagination infrastructure are available and functional.
- The lookup table upload workflow uses signed URLs to an external cloud storage service. The library handles the full 3-step flow (get URL, upload, register) but the user is responsible for providing a valid CSV file.
- Custom events are managed through the data definitions API endpoints — they don't have their own separate API domain. The CLI groups them separately for discoverability.
- All new types follow the existing frozen BaseModel pattern with forward-compatible extra field handling.
- All new CLI commands follow the existing command group pattern with standard error handling, workspace resolution, output formatting, and progress indicators.
- Bulk operations may have server-side limits on the number of entries per request. The library passes entries through without client-side batching.
- The export lexicon endpoint returns data in the API's native format. The library does not transform the export format.
