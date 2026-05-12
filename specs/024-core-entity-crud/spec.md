# Feature Specification: Core Entity CRUD (Dashboards, Reports, Cohorts)

**Feature Branch**: `024-core-entity-crud`
**Created**: 2026-03-26
**Status**: Draft
**Input**: User description: "Phase 1: Core Entity CRUD - Add full CRUD operations for Dashboards, Reports/Bookmarks, and Cohorts to the Python library, mirroring Rust implementation. Includes ~14 Pydantic types, ~35 API client methods, ~27 Workspace methods, and 34 CLI subcommands across 3 new command groups."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Dashboard Management via Library (Priority: P1)

A developer using the `mixpanel_data` Python library wants to programmatically manage Mixpanel dashboards — listing existing dashboards, creating new ones, updating their configuration, and deleting them. This enables automation of dashboard provisioning across projects and environments.

**Why this priority**: Dashboards are the primary organizational unit in Mixpanel. Most automation workflows start with dashboard management (e.g., provisioning standard dashboards for new projects, backing up dashboard configurations, bulk updates).

**Independent Test**: Can be fully tested by creating a Workspace instance with valid credentials, calling `list_dashboards()`, `create_dashboard()`, `get_dashboard()`, `update_dashboard()`, and `delete_dashboard()`, and verifying the returned data models match expected structures.

**Acceptance Scenarios**:

1. **Given** a configured Workspace with App API credentials, **When** the user calls `list_dashboards()`, **Then** the system returns a list of Dashboard objects with id, title, description, creator info, and timestamps.
2. **Given** a configured Workspace, **When** the user calls `create_dashboard(title="Q1 Metrics", description="Quarterly KPIs")`, **Then** the system creates the dashboard and returns a Dashboard object with a valid id.
3. **Given** an existing dashboard id, **When** the user calls `get_dashboard(id)`, **Then** the system returns the full Dashboard object including filters, breakdowns, and layout information.
4. **Given** an existing dashboard id, **When** the user calls `update_dashboard(id, title="Q1 Metrics Updated")`, **Then** the system updates the dashboard and returns the updated Dashboard object.
5. **Given** an existing dashboard id, **When** the user calls `delete_dashboard(id)`, **Then** the dashboard is removed and subsequent `get_dashboard(id)` raises an appropriate error.

---

### User Story 2 - Report/Bookmark Management via Library (Priority: P1)

A developer wants to programmatically manage saved reports (bookmarks) — listing, creating, updating, and deleting reports. Reports are the building blocks placed on dashboards, so managing them is equally critical.

**Why this priority**: Reports and dashboards are tightly coupled. Developers automating dashboard workflows also need to manage the reports within them. Bulk operations (update, delete) are common for cleanup and migration tasks.

**Independent Test**: Can be fully tested by calling `list_bookmarks()`, `create_bookmark()`, `get_bookmark()`, `update_bookmark()`, `delete_bookmark()`, and verifying returned Bookmark objects.

**Acceptance Scenarios**:

1. **Given** a configured Workspace, **When** the user calls `list_bookmarks()`, **Then** the system returns a paginated list of Bookmark objects with id, name, type, description, and creator info.
2. **Given** a configured Workspace, **When** the user calls `create_bookmark(name="Signup Funnel", bookmark_type="funnels", params={...})`, **Then** the system creates the bookmark and returns a Bookmark object.
3. **Given** an existing bookmark id, **When** the user calls `update_bookmark(id, name="Updated Funnel")`, **Then** the bookmark is updated and the change is reflected on retrieval.
4. **Given** multiple bookmark ids, **When** the user calls `bulk_delete_bookmarks(ids=[id1, id2])`, **Then** all specified bookmarks are deleted in a single operation.
5. **Given** a bookmark id, **When** the user calls `bookmark_linked_dashboard_ids(id)`, **Then** the system returns a list of dashboard ids that contain this report.

---

### User Story 3 - Cohort CRUD via Library (Priority: P1)

A developer wants to programmatically manage cohorts — listing, creating behavioral/static cohorts, updating definitions, and deleting them. The Python library already supports read-only cohort listing via discovery; this adds full CRUD through the App API.

**Why this priority**: Cohorts are foundational for segmentation and targeting. Automated cohort management is essential for workflows like syncing cohorts across projects, creating standard cohort sets for new workspaces, and programmatic cleanup.

**Independent Test**: Can be fully tested by calling `list_cohorts_full()`, `create_cohort()`, `get_cohort()`, `update_cohort()`, `delete_cohort()`, and verifying Cohort objects.

**Acceptance Scenarios**:

1. **Given** a configured Workspace, **When** the user calls `list_cohorts_full()`, **Then** the system returns a list of Cohort objects via the App API with full detail (id, name, description, count, visibility, permissions).
2. **Given** a configured Workspace, **When** the user calls `create_cohort(name="Power Users", definition={...})`, **Then** the system creates the cohort and returns a Cohort object with a valid id.
3. **Given** an existing cohort id, **When** the user calls `update_cohort(id, name="Super Power Users")`, **Then** the cohort is updated.
4. **Given** multiple cohort ids, **When** the user calls `bulk_delete_cohorts(ids=[id1, id2])`, **Then** all specified cohorts are deleted.
5. **Given** multiple cohort entries, **When** the user calls `bulk_update_cohorts(entries=[...])`, **Then** all specified cohorts are updated in a single operation.

---

### User Story 4 - Dashboard Advanced Operations (Priority: P2)

A developer wants to perform advanced dashboard operations — favoriting/unfavoriting, pinning/unpinning, removing reports from dashboards, bulk deletion, and working with blueprint templates.

**Why this priority**: These operations are important for organizational workflows but secondary to basic CRUD. Favoriting/pinning helps with dashboard organization, blueprints enable standardized dashboard creation, and bulk operations support cleanup workflows.

**Independent Test**: Can be fully tested by calling `favorite_dashboard()`, `pin_dashboard()`, `remove_report_from_dashboard()`, `bulk_delete_dashboards()`, and `list_blueprint_templates()`.

**Acceptance Scenarios**:

1. **Given** an existing dashboard, **When** the user calls `favorite_dashboard(id)`, **Then** the dashboard is marked as a favorite.
2. **Given** a favorited dashboard, **When** the user calls `unfavorite_dashboard(id)`, **Then** the favorite marker is removed.
3. **Given** a dashboard with reports, **When** the user calls `remove_report_from_dashboard(dashboard_id, bookmark_id)`, **Then** the report is removed from the dashboard.
4. **Given** multiple dashboard ids, **When** the user calls `bulk_delete_dashboards(ids)`, **Then** all specified dashboards are deleted.
5. **Given** a Workspace, **When** the user calls `list_blueprint_templates()`, **Then** the system returns available blueprint templates for dashboard creation.

---

### User Story 5 - CLI Command Access (Priority: P2)

A developer or DevOps engineer wants to manage dashboards, reports, and cohorts from the command line using the `mp` CLI tool, enabling scripting and automation without writing Python code.

**Why this priority**: CLI access enables shell-based automation, CI/CD integration, and quick ad-hoc operations. It wraps the library functionality with consistent output formatting.

**Independent Test**: Can be fully tested by running `mp dashboards list`, `mp reports list`, `mp cohorts list` and verifying structured output in all supported formats (json, jsonl, table, csv, plain).

**Acceptance Scenarios**:

1. **Given** valid credentials, **When** the user runs `mp dashboards list`, **Then** the system outputs dashboards in the selected format (default: json).
2. **Given** valid credentials, **When** the user runs `mp dashboards create --title "New Dashboard"`, **Then** a dashboard is created and its details are output.
3. **Given** valid credentials, **When** the user runs `mp reports list --format table`, **Then** reports are displayed in a rich table format.
4. **Given** valid credentials, **When** the user runs `mp cohorts get <id> --format json`, **Then** the full cohort details are output as JSON.
5. **Given** valid credentials, **When** the user runs `mp dashboards delete <id>`, **Then** the dashboard is deleted and a confirmation is output.

---

### User Story 6 - Report History and Dashboard Linkage (Priority: P3)

A developer wants to view report change history and track which dashboards contain a specific report, enabling audit trails and impact analysis before modifying or deleting reports.

**Why this priority**: History and linkage are audit/analysis features that enhance the core CRUD but are not essential for basic workflows.

**Independent Test**: Can be tested by calling `get_bookmark_history(id)` and `get_bookmark_dashboard_ids(bookmark_id)`.

**Acceptance Scenarios**:

1. **Given** an existing bookmark id, **When** the user calls `get_bookmark_history(id)`, **Then** the system returns a paginated list of change history entries.
2. **Given** a bookmark that appears on multiple dashboards, **When** the user calls `get_bookmark_dashboard_ids(bookmark_id)`, **Then** the system returns all dashboard ids containing that bookmark.

---

### User Story 7 - Dashboard ERF, RCA, and Blueprint Workflows (Priority: P3)

A developer wants to work with specialized dashboard features — ERF metrics, RCA (Root Cause Analysis) dashboards, blueprint configuration, and text card/report link updates.

**Why this priority**: These are specialized features used by advanced users. They enhance dashboard capabilities but are not needed for standard CRUD workflows.

**Independent Test**: Can be tested by calling `get_dashboard_erf()`, `create_rca_dashboard()`, `get_blueprint_config()`, `update_text_card()`, and `update_report_link()`.

**Acceptance Scenarios**:

1. **Given** a dashboard id, **When** the user calls `get_dashboard_erf(dashboard_id)`, **Then** the system returns ERF metrics for that dashboard.
2. **Given** RCA source data, **When** the user calls `create_rca_dashboard(params)`, **Then** an RCA dashboard is created.
3. **Given** a blueprint dashboard id, **When** the user calls `get_blueprint_config(dashboard_id)`, **Then** the system returns the blueprint configuration.
4. **Given** a dashboard with a text card, **When** the user calls `update_text_card(dashboard_id, text_card_id, markdown="# Updated")`, **Then** the text card content is updated.

---

### Edge Cases

- What happens when a user tries to delete a dashboard that contains reports? The system should delete the dashboard without affecting the underlying reports (reports are linked, not owned).
- What happens when a user tries to create a bookmark with an invalid `bookmark_type`? The system should raise a validation error before making the API call.
- What happens when bulk operations contain a mix of valid and invalid IDs? The system should report which operations succeeded and which failed, consistent with the Mixpanel API behavior.
- What happens when pagination reaches the end of results? The system should return an empty list or the final page without errors.
- What happens when the user has no workspace ID configured? The system should raise a clear error indicating workspace scoping is required for App API operations.
- What happens when the API returns a 404 for a non-existent entity? The system should raise a specific error (e.g., `NotFoundError`) with the entity type and id in the message.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST provide full CRUD operations for Dashboards (list, create, get, update, delete) through both the Python library and CLI.
- **FR-002**: System MUST provide full CRUD operations for Reports/Bookmarks (list, create, get, update, delete) through both the Python library and CLI.
- **FR-003**: System MUST provide full CRUD operations for Cohorts (list, create, get, update, delete) through both the Python library and CLI.
- **FR-004**: System MUST support bulk operations for all three entity types (bulk delete for dashboards, bulk delete and bulk update for bookmarks, bulk delete and bulk update for cohorts).
- **FR-005**: System MUST support dashboard organization operations: favorite/unfavorite, pin/unpin, and remove report from dashboard.
- **FR-006**: System MUST support report linkage queries: get linked dashboard IDs for a bookmark, and get dashboards containing a specific bookmark.
- **FR-007**: System MUST support report change history retrieval with cursor-based pagination.
- **FR-008**: System MUST support dashboard blueprint operations: list templates, create from template, get config, update cohorts, and finalize.
- **FR-009**: System MUST support specialized dashboard operations: RCA dashboard creation, ERF metrics retrieval, report link updates, and text card updates.
- **FR-010**: System MUST return strongly-typed result objects for all operations (immutable data models).
- **FR-011**: All CLI commands MUST support the existing 5 output formats: json, jsonl, table, csv, plain.
- **FR-012**: System MUST use workspace-scoped App API endpoints with appropriate authentication for all operations.
- **FR-013**: System MUST support cursor-based pagination for list operations that return paginated results.
- **FR-014**: System MUST provide clear error messages when operations fail, including entity type, operation attempted, and error details.
- **FR-015**: All list operations MUST support optional filtering parameters (e.g., list bookmarks by type, list cohorts by data group ID, list dashboards by IDs).

### Key Entities

- **Dashboard**: Represents a Mixpanel dashboard with title, description, visibility (public/private), access control, layout configuration, filters, breakdowns, time filters, and creator metadata. Dashboards contain reports (bookmarks) and can be favorited, pinned, and organized with blueprints.
- **Bookmark (Report)**: Represents a saved Mixpanel report (insight, funnel, flow, retention, etc.) with a name, type, query parameters, description, and creator metadata. Bookmarks can be linked to multiple dashboards and have change history.
- **Cohort**: Represents a behavioral or static user segment with a name, description, behavioral definition, count, visibility settings, and permissions. Cohorts can be used for targeting in feature flags, experiments, and report filtering.
- **Blueprint Template**: Represents a pre-built dashboard template with a title, description, and number of included reports. Used to create standardized dashboards.
- **Bookmark History Entry**: Represents a change record for a bookmark, capturing who made the change, when, and what changed. Supports audit trails.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: All 36 Workspace methods for the three entity domains (20 dashboard + 9 bookmark + 7 cohort) are callable and return correctly-typed results.
- **SC-002**: All 34 CLI subcommands across 3 command groups execute successfully and produce valid output in all 5 formats.
- **SC-003**: Bulk operations handle batches of entities in a single call without requiring client-side iteration.
- **SC-004**: Paginated list operations retrieve all pages of results without data loss when using the pagination helper.
- **SC-005**: Error responses from the API are translated into meaningful, actionable error messages with entity context.
- **SC-006**: All new code passes the project's quality gates: linting, type checking, formatting, and 90% test coverage.
- **SC-007**: A developer can complete a full dashboard CRUD lifecycle (create, read, update, delete) in under 10 lines of code.

## Assumptions

- OAuth 2.0 PKCE authentication and App API infrastructure (Bearer auth, workspace scoping, cursor-based pagination) are already implemented as part of Phase 0 (spec 023).
- The existing API client has methods for making authenticated App API requests with workspace-scoped URL construction.
- Cursor-based pagination helpers are available from the Phase 0 implementation.
- The Mixpanel App API endpoints for dashboards, bookmarks, and cohorts follow the patterns documented in the Rust implementation and the Django reference codebase.
- All new data model types will be added to the existing types module (not split into separate files) since the total model count remains manageable.
- The existing CLI output formatters (json, jsonl, table, csv, plain) work with any data model and do not need modification.
- Workspace ID resolution (auto-discover or explicit) is already handled by the Phase 0 infrastructure.
