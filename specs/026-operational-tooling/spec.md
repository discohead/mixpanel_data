# Feature Specification: Operational Tooling — Alerts, Annotations, and Webhooks

**Feature Branch**: `026-operational-tooling`  
**Created**: 2026-03-31  
**Status**: Draft  
**Input**: User description: "Phase 3: Operational Tooling (Alerts + Annotations + Webhooks) — Domains 6, 7, 8 from Rust parity gap analysis. Add full CRUD for custom alerts, timeline annotations, and project webhooks to the Python library and CLI."

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Manage Custom Alerts (Priority: P1)

A Mixpanel project administrator wants to create, configure, and manage automated alerts that trigger when metric conditions are met. They need to associate alerts with saved reports (bookmarks), define trigger conditions and notification frequencies, and receive notifications via configured subscriptions (email, Slack, etc.). They also need to view alert trigger history, test alert configurations before activating them, check account alert limits, and bulk-delete obsolete alerts.

**Why this priority**: Alerts are the most operationally critical domain — they enable proactive monitoring. Without alerts, users can only discover anomalies by manually checking dashboards. Alert management also has the most API surface (11 methods) and the most complex data model (conditions, frequencies, subscriptions, history, screenshots, validation).

**Independent Test**: Can be fully tested by creating an alert linked to an existing bookmark, listing alerts, retrieving its history, testing the alert config, and deleting it. Delivers immediate value by enabling programmatic alert management.

**Acceptance Scenarios**:

1. **Given** a workspace with saved reports, **When** the user lists alerts, **Then** the system returns all custom alerts with their configuration, status, and linked bookmark details.
2. **Given** a valid bookmark ID and alert parameters, **When** the user creates an alert, **Then** the system returns the created alert with its assigned ID and all configured fields.
3. **Given** an existing alert ID, **When** the user retrieves the alert, **Then** the system returns the complete alert configuration including condition, frequency, subscriptions, and validity status.
4. **Given** an existing alert ID and update parameters, **When** the user updates the alert, **Then** the system applies the partial update and returns the updated alert.
5. **Given** an existing alert ID, **When** the user deletes the alert, **Then** the alert is removed and no longer appears in the list.
6. **Given** a list of alert IDs, **When** the user bulk-deletes alerts, **Then** all specified alerts are removed.
7. **Given** an optional alert type filter, **When** the user requests alert counts, **Then** the system returns the current count, account limit, and whether the account is below the limit.
8. **Given** an existing alert ID, **When** the user requests alert history, **Then** the system returns paginated trigger history with timestamps and results.
9. **Given** alert configuration parameters, **When** the user tests an alert, **Then** the system evaluates the configuration and returns test results without creating a persistent alert.
10. **Given** a GCS key from alert history, **When** the user requests a screenshot URL, **Then** the system returns a signed URL for the alert screenshot.
11. **Given** alert IDs and a bookmark type, **When** the user validates alerts for a bookmark, **Then** the system returns validation results indicating which alerts are compatible.

---

### User Story 2 — Manage Timeline Annotations (Priority: P2)

A data analyst wants to mark significant events on the Mixpanel timeline (product launches, marketing campaigns, incidents) so that metric changes can be correlated with known events. They need to create annotations with dates, descriptions, and tags; list annotations filtered by date range or tags; update or delete existing annotations; and manage annotation tags for organizational consistency.

**Why this priority**: Annotations are simpler than alerts (7 methods, lightweight data model) and provide immediate analytical value. They enhance every dashboard and report by providing context for metric movements. Tag management adds organizational capabilities.

**Independent Test**: Can be fully tested by creating an annotation tag, creating an annotation with that tag, listing annotations by date range, updating the description, and deleting the annotation. Delivers value by enabling timeline context management.

**Acceptance Scenarios**:

1. **Given** optional date range and tag filters, **When** the user lists annotations, **Then** the system returns all matching annotations with their dates, descriptions, users, and tags.
2. **Given** a date, description, and optional tags, **When** the user creates an annotation, **Then** the system returns the created annotation with its assigned ID.
3. **Given** an existing annotation ID, **When** the user retrieves the annotation, **Then** the system returns the complete annotation with user and tag details.
4. **Given** an existing annotation ID and update parameters, **When** the user updates the annotation, **Then** the system applies the partial update and returns the updated annotation.
5. **Given** an existing annotation ID, **When** the user deletes the annotation, **Then** the annotation is removed.
6. **Given** no parameters, **When** the user lists annotation tags, **Then** the system returns all tags available in the project.
7. **Given** a tag name, **When** the user creates an annotation tag, **Then** the system returns the created tag with its assigned ID.

---

### User Story 3 — Manage Project Webhooks (Priority: P3)

A DevOps engineer wants to configure project webhooks so that Mixpanel can send event notifications to external systems (internal APIs, monitoring services, data pipelines). They need to create webhooks with URLs and optional authentication, enable/disable webhooks, update webhook configurations, test connectivity before activation, and remove obsolete webhooks.

**Why this priority**: Webhooks are the smallest domain (5 methods) with the simplest data model. While operationally useful for integrations, they affect fewer users than alerts or annotations. The test-connectivity feature is valuable for validating configurations before going live.

**Independent Test**: Can be fully tested by creating a webhook with a test URL, testing its connectivity, updating its configuration, and deleting it. Delivers value by enabling programmatic webhook lifecycle management.

**Acceptance Scenarios**:

1. **Given** no parameters, **When** the user lists webhooks, **Then** the system returns all project webhooks with their configuration, status, and auth details.
2. **Given** a webhook name, URL, and optional auth configuration, **When** the user creates a webhook, **Then** the system returns a mutation result with the webhook ID and name.
3. **Given** an existing webhook ID and update parameters, **When** the user updates the webhook, **Then** the system applies the changes and returns a mutation result.
4. **Given** an existing webhook ID, **When** the user deletes the webhook, **Then** the webhook is removed.
5. **Given** a URL and optional auth configuration, **When** the user tests webhook connectivity, **Then** the system returns a test result with success status, HTTP status code, and message.

---

### Edge Cases

- What happens when creating an alert for a non-existent bookmark ID? The API returns an error; the system surfaces it as a clear error message.
- What happens when listing annotations with an invalid date range (from_date > to_date)? The system validates input and returns an appropriate error.
- What happens when testing a webhook against an unreachable URL? The test result indicates failure with a descriptive message and HTTP status code.
- What happens when bulk-deleting alerts with some invalid IDs in the list? The API processes valid IDs and reports errors for invalid ones.
- What happens when creating a webhook with Basic auth but missing username/password? The system requires both fields when auth_type is Basic.
- What happens when requesting alert history for an alert with no trigger events? The system returns an empty results list with pagination metadata.
- What happens when the account has reached its alert limit? The alert count endpoint reports the limit exceeded status, and creation attempts return an appropriate error.

## Requirements *(mandatory)*

### Functional Requirements

**Alerts (Domain 6)**

- **FR-001**: System MUST support listing all custom alerts, optionally filtered by bookmark ID, with the option to skip user filtering.
- **FR-002**: System MUST support creating a custom alert linked to a bookmark with configurable condition, frequency, pause state, and notification subscriptions.
- **FR-003**: System MUST support retrieving a single alert by its numeric ID.
- **FR-004**: System MUST support updating an existing alert with partial field changes (name, condition, frequency, pause state, subscriptions).
- **FR-005**: System MUST support deleting a single alert by ID.
- **FR-006**: System MUST support bulk-deleting multiple alerts by a list of IDs.
- **FR-007**: System MUST support retrieving alert counts and account limits, optionally filtered by alert type.
- **FR-008**: System MUST support retrieving paginated alert trigger history for a given alert, with configurable cursor and page size.
- **FR-009**: System MUST support testing an alert configuration without persisting it, returning evaluation results.
- **FR-010**: System MUST support retrieving signed screenshot URLs from GCS keys found in alert history.
- **FR-011**: System MUST support validating whether specific alerts are compatible with a given bookmark type.

**Annotations (Domain 7)**

- **FR-012**: System MUST support listing annotations, optionally filtered by date range (from_date, to_date) and tags.
- **FR-013**: System MUST support creating an annotation with a required date and description, plus optional tag IDs and user ID.
- **FR-014**: System MUST support retrieving a single annotation by its numeric ID.
- **FR-015**: System MUST support updating an existing annotation with partial field changes (description, tags).
- **FR-016**: System MUST support deleting a single annotation by ID.
- **FR-017**: System MUST support listing all annotation tags in the project.
- **FR-018**: System MUST support creating a new annotation tag with a name.

**Webhooks (Domain 8)**

- **FR-019**: System MUST support listing all project webhooks.
- **FR-020**: System MUST support creating a webhook with a name, URL, and optional authentication configuration (auth type, username, password).
- **FR-021**: System MUST support updating an existing webhook with partial field changes (name, URL, auth type, enabled state).
- **FR-022**: System MUST support deleting a webhook by its string ID.
- **FR-023**: System MUST support testing webhook connectivity by sending a test request to a URL with optional authentication, returning success status, HTTP status code, and descriptive message.

**Cross-Cutting**

- **FR-024**: All operations MUST be available both as Python library methods and as CLI commands.
- **FR-025**: All CLI commands MUST support the standard output formats (json, jsonl, table, csv, plain) and jq filtering.
- **FR-026**: All operations MUST use the existing App API infrastructure (authentication, workspace scoping, error handling).
- **FR-027**: All response data MUST be represented as immutable, validated data models that tolerate additional unknown fields from the API for forward compatibility.

### Key Entities

- **CustomAlert**: A monitoring rule linked to a saved report (bookmark) that triggers notifications when defined metric conditions are met. Key attributes: ID, name, linked bookmark, condition expression, frequency (seconds), pause state, notification subscriptions, creator, validity status, last checked/fired timestamps.
- **AlertCount**: Summary of current alert usage against account limits. Key attributes: anomaly alert count, alert limit, whether below limit.
- **AlertHistory**: A paginated record of when an alert was triggered. Contains trigger results with timestamps and optional screenshot references.
- **Annotation**: A timestamped text marker on the project timeline. Key attributes: ID, project ID, date, description, creator user, associated tags.
- **AnnotationUser**: The user who created an annotation. Key attributes: ID, first name, last name.
- **AnnotationTag**: A label for organizing annotations. Key attributes: ID, name, project ID.
- **ProjectWebhook**: An HTTP endpoint configuration for receiving event notifications. Key attributes: ID, name, URL, enabled state, auth type, creator, created/modified timestamps.
- **WebhookTestResult**: The outcome of a connectivity test. Key attributes: success boolean, HTTP status code, descriptive message.
- **WebhookMutationResult**: The response from webhook create/update operations. Key attributes: webhook ID, name.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Users can perform all 11 alert operations (list, create, get, update, delete, bulk-delete, count, history, test, screenshot, validate) through both the library and CLI.
- **SC-002**: Users can perform all 7 annotation operations (list, create, get, update, delete, list-tags, create-tag) through both the library and CLI.
- **SC-003**: Users can perform all 5 webhook operations (list, create, update, delete, test) through both the library and CLI.
- **SC-004**: All operations complete within the same latency envelope as existing CRUD operations (dashboards, reports, cohorts), since they use the same transport layer.
- **SC-005**: All new data models handle unexpected fields from the API without errors, preserving forward compatibility.
- **SC-006**: All new code achieves 90% or higher test coverage.
- **SC-007**: All CLI commands produce correctly formatted output in all five output modes and support jq filtering.

## Assumptions

- The existing App API infrastructure (OAuth Bearer auth, Basic Auth, workspace scoping, cursor-based pagination) is stable and sufficient for all three domains. No new transport-layer changes are needed.
- Alert, annotation, and webhook endpoints follow the same App API URL pattern (`/api/app/projects/{pid}/...`) with workspace-scoped routing, consistent with dashboards, reports, and cohorts.
- Alert conditions and subscriptions are opaque JSON structures — the library passes them through without interpreting or validating their internal schema.
- Webhook passwords are sensitive data handled consistently with the existing credential handling patterns in the project.
- The GCS screenshot URL feature for alerts uses the same signed-URL pattern as existing API operations — no direct GCS client is needed.
- All three domains are independent of each other and can be implemented and tested separately.
- The Rust implementation serves as the authoritative reference for field names, types, and API endpoint shapes.
