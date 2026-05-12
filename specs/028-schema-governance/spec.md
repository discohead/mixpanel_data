# Feature Specification: Schema Registry & Data Governance

**Feature Branch**: `028-schema-governance`  
**Created**: 2026-04-02  
**Status**: Draft  
**Input**: User description: "Phase 5: Schema & Advanced — Schema Registry CRUD + Schema Enforcement & Data Governance (Domains 14 + 15)"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Schema Registry Management (Priority: P1)

A data engineer managing event schemas needs to create, update, and delete schema definitions for their Mixpanel project. They want to define expected schemas for events and properties, enforce data quality at the source, and keep schemas in sync as their tracking plan evolves. Bulk operations are critical for managing schemas across dozens of events efficiently.

**Why this priority**: Schema registry is the foundation for all governance features. Without schema definitions, enforcement, auditing, and anomaly detection have nothing to enforce against. This is the prerequisite for all other stories.

**Independent Test**: Can be fully tested by creating a schema for an event, listing schemas to confirm it exists, updating it, and deleting it. Delivers immediate value by allowing programmatic schema management without the Mixpanel webapp.

**Acceptance Scenarios**:

1. **Given** an authenticated user with a valid workspace, **When** they list schemas by entity type, **Then** they receive all schema definitions for that entity type in the project.
2. **Given** an authenticated user, **When** they create a schema for a specific event or property, **Then** the schema is persisted and retrievable by entity type and name.
3. **Given** multiple schemas to create, **When** they use bulk create with a list of entries, **Then** all schemas are created in a single operation, and the response reports how many were added.
4. **Given** an existing schema, **When** they update it with a new definition, **Then** the schema is modified and the updated version is returned.
5. **Given** multiple schemas to update, **When** they use bulk update, **Then** all specified schemas are updated in one operation.
6. **Given** existing schemas, **When** they delete schemas by entity type and name, **Then** the schemas are removed and the response reports the delete count.
7. **Given** a bulk create with the truncate option, **When** executed, **Then** existing schemas of that entity type are removed before the new ones are inserted.

---

### User Story 2 - Schema Enforcement Configuration (Priority: P2)

A data governance lead wants to configure how strictly Mixpanel enforces event schemas in their project. They need to initialize enforcement rules, adjust enforcement behavior (e.g., warn vs. reject non-conforming events), and fully replace or remove enforcement configuration as policies evolve.

**Why this priority**: Enforcement acts on the schemas defined in Story 1. Once schemas exist, enforcement is the next logical step to ensure data quality. Without enforcement, schemas are documentation only.

**Independent Test**: Can be fully tested by initializing enforcement with a configuration, reading it back, updating it, replacing it entirely, and deleting it. Delivers value by enabling programmatic control over data quality policies.

**Acceptance Scenarios**:

1. **Given** a project without enforcement configured, **When** the user initializes enforcement with a configuration, **Then** enforcement is active and the configuration is retrievable.
2. **Given** active enforcement, **When** the user retrieves the configuration with specific fields, **Then** only the requested fields are returned.
3. **Given** active enforcement, **When** the user partially updates the configuration, **Then** only the specified fields change; other settings remain unchanged.
4. **Given** active enforcement, **When** the user fully replaces the configuration, **Then** all fields are overwritten with the new values.
5. **Given** active enforcement, **When** the user deletes the configuration, **Then** enforcement is disabled and the configuration is removed.

---

### User Story 3 - Data Auditing (Priority: P3)

A data quality analyst wants to run audits against their Mixpanel project to identify schema violations, undocumented events, or properties that don't match their tracking plan. They need both a full audit (events + properties) and an events-only audit for faster, targeted checks.

**Why this priority**: Auditing is the diagnostic complement to enforcement. While enforcement prevents bad data going forward, auditing reveals existing data quality issues. Depends on schemas (Story 1) but not on enforcement (Story 2).

**Independent Test**: Can be fully tested by running a full audit and an events-only audit against a project with known schema violations. Delivers value by surfacing data quality issues programmatically.

**Acceptance Scenarios**:

1. **Given** a project with schemas defined, **When** the user runs a full audit, **Then** the response contains violation details for both events and properties.
2. **Given** a project with schemas defined, **When** the user runs an events-only audit, **Then** the response contains violation details for events only, completing faster than a full audit.
3. **Given** a project with no schema violations, **When** the user runs an audit, **Then** the response indicates no violations found.

---

### User Story 4 - Data Volume Anomaly Management (Priority: P4)

A data operations engineer monitors data volume anomalies detected by Mixpanel — unexpected spikes or drops in event volumes that may indicate tracking issues, broken implementations, or data pipeline problems. They need to list anomalies with filtering, update individual anomaly statuses (e.g., acknowledge, dismiss), and perform bulk status updates across many anomalies.

**Why this priority**: Anomaly detection is an independent monitoring capability. While it benefits from schema context, it operates on volume patterns rather than schema definitions.

**Independent Test**: Can be fully tested by listing anomalies with query filters, updating a single anomaly's status, and bulk-updating multiple anomalies. Delivers value by enabling programmatic anomaly triage.

**Acceptance Scenarios**:

1. **Given** a project with detected anomalies, **When** the user lists anomalies with optional query parameters (date range, status, event name), **Then** matching anomalies are returned with details (event name, expected volume, actual volume, detection date, status).
2. **Given** a detected anomaly, **When** the user updates its status (e.g., marks as acknowledged or dismissed), **Then** the anomaly's status is updated and the change is reflected on subsequent retrieval.
3. **Given** multiple anomalies to triage, **When** the user performs a bulk status update, **Then** all specified anomalies are updated in a single operation.

---

### User Story 5 - Event Deletion Requests (Priority: P5)

A compliance officer or data engineer needs to request deletion of specific event data from Mixpanel — for GDPR compliance, data hygiene, or correcting tracking mistakes. They need to preview what a deletion filter would match before committing, create deletion requests, list pending/completed requests, and cancel pending requests if needed.

**Why this priority**: Event deletion is a destructive, compliance-critical operation. It's the least frequently used but most consequential capability in this feature set. The preview capability is essential to prevent accidental data loss.

**Independent Test**: Can be fully tested by previewing a deletion filter, creating a deletion request, listing requests to confirm it appears, and canceling it while still pending. Delivers value by enabling programmatic compliance operations.

**Acceptance Scenarios**:

1. **Given** a deletion filter specification, **When** the user previews it, **Then** the response shows what events would be affected without actually deleting anything.
2. **Given** a valid deletion filter, **When** the user creates a deletion request, **Then** the request is created with a pending status and a unique identifier.
3. **Given** existing deletion requests, **When** the user lists them, **Then** all requests are returned with their current status (pending, in-progress, completed, cancelled).
4. **Given** a pending deletion request, **When** the user cancels it, **Then** the request is cancelled and no data is deleted.
5. **Given** a deletion request that is already in-progress or completed, **When** the user attempts to cancel it, **Then** an appropriate error is returned indicating the request cannot be cancelled.

---

### Edge Cases

- What happens when creating a schema for an entity that already has one? (Should update or error based on API behavior)
- What happens when bulk-creating schemas with `truncate=true` and no new entries? (Should delete all existing schemas of that type)
- What happens when deleting enforcement that was never initialized? (Should return appropriate error)
- What happens when previewing deletion filters that match zero events? (Should return empty match set, not error)
- What happens when canceling an already-completed deletion request? (Should return clear error indicating the request has already been processed)
- What happens when listing anomalies for a project with no anomaly detection history? (Should return empty list, not error)
- What happens when bulk operations contain duplicate entries? (Should follow API's deduplication behavior)

## Requirements *(mandatory)*

### Functional Requirements

**Schema Registry (Domain 14)**

- **FR-001**: System MUST list all schema definitions for a given entity type (event or property).
- **FR-002**: System MUST create a schema for a specific entity type and entity name with a schema definition.
- **FR-003**: System MUST support bulk creation of schemas, accepting multiple entries and an optional truncate flag to replace existing schemas of the same entity type.
- **FR-004**: System MUST update an existing schema for a specific entity type and entity name.
- **FR-005**: System MUST support bulk updating of schemas, accepting multiple entries in a single operation.
- **FR-006**: System MUST delete schemas by entity type and entity name, returning the count of deleted schemas.

**Schema Enforcement (Domain 15 — Enforcement)**

- **FR-007**: System MUST retrieve the current schema enforcement configuration, optionally filtered to specific fields.
- **FR-008**: System MUST initialize schema enforcement with a provided configuration when none exists.
- **FR-009**: System MUST partially update an existing enforcement configuration, modifying only specified fields.
- **FR-010**: System MUST fully replace an existing enforcement configuration with a new one.
- **FR-011**: System MUST delete the enforcement configuration, disabling enforcement.

**Data Auditing (Domain 15 — Audit)**

- **FR-012**: System MUST run a full data audit covering both events and properties, returning violation details.
- **FR-013**: System MUST run an events-only audit, returning event-specific violation details.

**Data Volume Anomalies (Domain 15 — Anomalies)**

- **FR-014**: System MUST list data volume anomalies with optional query parameters for filtering.
- **FR-015**: System MUST update the status of a single data volume anomaly.
- **FR-016**: System MUST bulk-update the status of multiple anomalies in a single operation.

**Event Deletion Requests (Domain 15 — Deletions)**

- **FR-017**: System MUST list all event deletion requests with their current status.
- **FR-018**: System MUST create a new event deletion request with a filter specification.
- **FR-019**: System MUST cancel a pending event deletion request.
- **FR-020**: System MUST preview what events a deletion filter would match without performing the deletion.

**CLI Commands**

- **FR-021**: CLI MUST expose schema registry operations as a `schemas` command group with `list`, `create`, `create-bulk`, `update`, `update-bulk`, and `delete` subcommands.
- **FR-022**: CLI MUST expose enforcement operations under the existing `lexicon` command group with `enforcement get`, `enforcement init`, `enforcement update`, `enforcement replace`, and `enforcement delete` subcommands.
- **FR-023**: CLI MUST expose audit operations under `lexicon` as an `audit` subcommand with an `--events-only` flag for lightweight event-only audits.
- **FR-024**: CLI MUST expose anomaly operations under `lexicon` as `anomalies list`, `anomalies update`, and `anomalies bulk-update` subcommands.
- **FR-025**: CLI MUST expose deletion request operations under `lexicon` as `deletion-requests list`, `deletion-requests create`, `deletion-requests cancel`, and `deletion-requests preview` subcommands.
- **FR-026**: All new CLI commands MUST support the standard output formats (json, jsonl, table, csv, plain) and the `--jq` filter option.

**Cross-Cutting**

- **FR-027**: All operations MUST require valid authentication (service account or OAuth).
- **FR-028**: All operations MUST support workspace-scoped access where the API requires it.
- **FR-029**: All response data MUST be returned as typed, immutable result objects.
- **FR-030**: All bulk operations MUST report operation counts (added, updated, deleted) in their responses.

### Key Entities

- **SchemaEntry**: A schema definition for a named entity (event or property), including the entity type, entity name, version, and the schema definition itself (a structured specification of expected fields and types).
- **SchemaEnforcementConfig**: Configuration controlling how strictly the project enforces schemas — including enforcement mode, behavior for non-conforming events, and scope of enforcement.
- **AuditResponse**: The output of a data audit, containing violation details grouped by event and/or property, with counts and descriptions of non-conforming data.
- **DataVolumeAnomaly**: A detected deviation from expected data volume patterns, including the event name, expected vs. actual volumes, detection timestamp, and current triage status.
- **EventDeletionRequest**: A request to permanently delete event data matching specified filters, with lifecycle states (pending, in-progress, completed, cancelled) and filter criteria.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Users can manage the full lifecycle of schema definitions (create, read, update, delete) for any entity type through both the library and CLI.
- **SC-002**: Users can manage bulk schema operations (create and update) processing multiple entries in a single call, reducing round-trips compared to individual operations.
- **SC-003**: Users can configure, modify, and remove schema enforcement policies without accessing the Mixpanel webapp.
- **SC-004**: Users can run data audits and receive violation reports within a single command or method call.
- **SC-005**: Users can triage data volume anomalies (list, filter, update status, bulk update) through the library and CLI.
- **SC-006**: Users can manage the full lifecycle of event deletion requests (preview, create, list, cancel) through the library and CLI.
- **SC-007**: All new operations complete successfully with valid credentials and return typed results consistent with existing library patterns.
- **SC-008**: All new CLI commands produce output in all five supported formats (json, jsonl, table, csv, plain) and support jq filtering.

## Assumptions

- OAuth or service account authentication is already implemented and functional (completed in earlier phases).
- App API infrastructure (Bearer auth, workspace scoping, cursor pagination) is already available from prior phases.
- The existing `lexicon` CLI command group is the appropriate home for enforcement, audit, anomaly, and deletion subcommands, matching the Rust CLI structure.
- Schema registry operations use workspace-scoped App API endpoints with the optional workspace scoping pattern (workspace ID optional but recommended).
- The Mixpanel App API's schema, enforcement, audit, anomaly, and deletion endpoints are stable and match the Rust implementation's endpoint paths.
- Bulk operations follow the same request/response patterns as existing bulk operations (e.g., bulk cohort updates, bulk bookmark updates) already implemented in earlier phases.
- Event deletion is a privileged operation — the API itself enforces permission checks; the library does not need to add additional authorization gates beyond what the API requires.
- Deletion request preview is a read-only operation that does not modify any data.
