# Feature Specification: Feature Management (Flags + Experiments)

**Feature Branch**: `025-feature-management`
**Created**: 2026-03-31
**Status**: Draft
**Input**: User description: "Phase 2: Feature Management — Feature Flags and Experiments CRUD with full lifecycle management via App API"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Feature Flag CRUD (Priority: P1)

A developer or product manager needs to manage feature flags programmatically — listing existing flags, creating new ones, reading flag details, updating flag configuration (targeting rules, variants, rollout percentages), and deleting flags they no longer need. This is the core value: enabling automated feature flag management without the Mixpanel webapp.

**Why this priority**: Feature flag CRUD is the foundational capability. Without it, no other flag operations (lifecycle, test users, history) are possible. It delivers immediate value for CI/CD automation and infrastructure-as-code workflows.

**Independent Test**: Can be fully tested by creating a flag, reading it back, updating its name, listing all flags to confirm presence, and deleting it — verifying each operation returns the expected data.

**Acceptance Scenarios**:

1. **Given** an authenticated workspace with valid credentials, **When** the user lists feature flags, **Then** the system returns all flags for the project including their status, name, key, and targeting rules.
2. **Given** an authenticated workspace, **When** the user creates a feature flag with a name, key, and optional description, **Then** the system returns the newly created flag with a unique identifier.
3. **Given** an existing feature flag, **When** the user retrieves it by ID, **Then** the system returns the full flag details including variants, rollout rules, and metadata.
4. **Given** an existing feature flag, **When** the user updates its name, description, status, or ruleset, **Then** the system persists the changes and returns the updated flag.
5. **Given** an existing feature flag, **When** the user deletes it, **Then** the flag is permanently removed and no longer appears in listings.

---

### User Story 2 - Experiment Lifecycle Management (Priority: P1)

A product team needs to manage A/B experiments end-to-end: creating experiments, launching them (moving from draft to active), concluding them when enough data is collected, and deciding a winner variant. This lifecycle is the core value for experiment management.

**Why this priority**: Experiment lifecycle (create, launch, conclude, decide) is equally fundamental to flag CRUD. Experiments without lifecycle transitions are incomplete. This enables teams to automate their experimentation workflows.

**Independent Test**: Can be tested by creating an experiment, launching it, concluding it, and deciding a winner — verifying each state transition succeeds and the experiment status updates correctly.

**Acceptance Scenarios**:

1. **Given** an authenticated workspace, **When** the user creates an experiment with a name and hypothesis, **Then** the system returns the new experiment in Draft status.
2. **Given** a Draft experiment, **When** the user launches it, **Then** the experiment transitions to Active status.
3. **Given** an Active experiment, **When** the user concludes it with an end date, **Then** the experiment transitions to Concluded status.
4. **Given** a Concluded experiment, **When** the user decides a winner variant, **Then** the experiment records the decision and transitions to a terminal state.
5. **Given** an authenticated workspace, **When** the user lists experiments, **Then** the system returns all experiments with their current status and metadata.

---

### User Story 3 - Flag Lifecycle Operations (Priority: P2)

A developer needs to manage the lifecycle of feature flags beyond basic CRUD — archiving flags that are no longer active (soft delete), restoring archived flags, and duplicating existing flags as templates for new ones.

**Why this priority**: Lifecycle operations extend the core CRUD with important operational capabilities. Archiving prevents accidental deletion while keeping the flag list clean. Duplication saves time when creating similar flags.

**Independent Test**: Can be tested by creating a flag, archiving it, confirming it no longer appears in default listings, restoring it, and duplicating it — verifying each operation succeeds.

**Acceptance Scenarios**:

1. **Given** an existing feature flag, **When** the user archives it, **Then** the flag is marked as archived and excluded from default listings.
2. **Given** an archived feature flag, **When** the user restores it, **Then** the flag returns to its previous state and appears in default listings.
3. **Given** an existing feature flag, **When** the user duplicates it, **Then** a new flag is created with the same configuration but a distinct identifier.
4. **Given** an authenticated workspace, **When** the user lists flags with the "include archived" option, **Then** both active and archived flags are returned.

---

### User Story 4 - Flag Test Users and History (Priority: P2)

A QA engineer needs to override flag values for specific test users during development, and a product manager needs to review the change history of a flag to understand when and how it was modified.

**Why this priority**: Test user overrides are essential for QA workflows. Change history provides auditability. Both extend the core CRUD with high-value operational capabilities.

**Independent Test**: Can be tested by setting test user overrides on a flag and reading them back, then querying the flag's change history and verifying entries are returned.

**Acceptance Scenarios**:

1. **Given** an existing feature flag, **When** the user sets test user overrides with variant-to-user mappings (variant keys mapped to user distinct IDs), **Then** the overrides are persisted and returned in the flag details.
2. **Given** a feature flag with change history, **When** the user queries its history, **Then** the system returns a paginated list of change events with timestamps and details.
3. **Given** an authenticated workspace, **When** the user queries account flag limits, **Then** the system returns the current usage count and maximum allowed flags.

---

### User Story 5 - Experiment Extended Operations (Priority: P2)

A product manager needs to archive completed experiments, restore them for review, and duplicate experiments to rerun with modified parameters. They also need to list ERF experiments for results framework integration.

**Why this priority**: These operations complete the experiment management surface. Archive/restore/duplicate provide the same operational value as for flags. ERF listing enables results framework workflows.

**Independent Test**: Can be tested by archiving an experiment, restoring it, duplicating it, and listing ERF experiments — verifying each operation succeeds.

**Acceptance Scenarios**:

1. **Given** an existing experiment, **When** the user archives it, **Then** it is excluded from default listings.
2. **Given** an archived experiment, **When** the user restores it, **Then** it reappears in default listings.
3. **Given** an existing experiment, **When** the user duplicates it with a new name, **Then** a new experiment is created with the same configuration.
4. **Given** an authenticated workspace, **When** the user lists ERF experiments, **Then** the system returns experiments in the ERF format.

---

### User Story 6 - CLI Commands for Flags and Experiments (Priority: P3)

A developer or DevOps engineer needs command-line access to all flag and experiment operations for scripting, CI/CD pipelines, and quick terminal-based management.

**Why this priority**: CLI commands wrap the library API and are the last layer to build. The library must work correctly before CLI commands can be added. CLI access is essential for automation but depends on all prior stories.

**Independent Test**: Can be tested by running each CLI subcommand and verifying it produces correct output in all supported formats (JSON, table, CSV, plain).

**Acceptance Scenarios**:

1. **Given** a configured CLI environment, **When** the user runs `mp flags list`, **Then** the system outputs all feature flags in the requested format.
2. **Given** a configured CLI environment, **When** the user runs `mp flags create --name "My Flag" --key "my_flag"`, **Then** a new flag is created and its details are output.
3. **Given** a configured CLI environment, **When** the user runs `mp experiments launch <id>`, **Then** the experiment is launched and a success confirmation is output.
4. **Given** any CLI command, **When** the user specifies `--format table`, **Then** the output is rendered as a human-readable Rich table.
5. **Given** any CLI command that fails, **When** an error occurs (auth, not found, validation), **Then** a clear error message is displayed with the appropriate exit code.

---

### Edge Cases

- What happens when a user tries to launch an experiment that is not in Draft status?
- What happens when a user tries to conclude an experiment that is not Active?
- What happens when a user tries to decide a winner on an experiment that is not Concluded?
- What happens when a user tries to restore a flag that is not archived?
- What happens when a user tries to create a feature flag with a duplicate key?
- What happens when the account has reached its flag limit?
- What happens when a user tries to delete a flag that is referenced by an active experiment?
- What happens when workspace ID is not configured for feature flag operations (which require workspace-scoped URLs)?
- What happens when paginated flag history results exceed a single page?

## Requirements *(mandatory)*

### Functional Requirements

#### Feature Flags

- **FR-001**: System MUST list all feature flags for a project, with an option to include archived flags.
- **FR-002**: System MUST create a new feature flag given a name, key, and optional description, status, tags, and ruleset.
- **FR-003**: System MUST retrieve a single feature flag by its unique identifier, returning all details including variants, rollout configuration, and metadata.
- **FR-004**: System MUST update a feature flag by replacing its full configuration (PUT semantics) given the flag ID and updated parameters.
- **FR-005**: System MUST delete a feature flag permanently by its ID.
- **FR-006**: System MUST archive a feature flag (soft delete) by its ID.
- **FR-007**: System MUST restore an archived feature flag by its ID.
- **FR-008**: System MUST duplicate a feature flag by its ID, creating a new flag with the same configuration.
- **FR-009**: System MUST set test user overrides for a feature flag, accepting a list of user-variant mappings.
- **FR-010**: System MUST retrieve the change history for a feature flag, supporting pagination.
- **FR-011**: System MUST retrieve account-level flag limits (current usage and maximum).

#### Experiments

- **FR-012**: System MUST list all experiments for a project, with an option to include archived experiments.
- **FR-013**: System MUST create a new experiment given a name, description, hypothesis, and settings.
- **FR-014**: System MUST retrieve a single experiment by its unique identifier, returning all details.
- **FR-015**: System MUST update an experiment's mutable fields (name, description, variants, metrics, settings, status).
- **FR-016**: System MUST delete an experiment permanently by its ID.
- **FR-017**: System MUST launch an experiment, transitioning it from Draft to Active status.
- **FR-018**: System MUST conclude an experiment, transitioning it from Active to Concluded status.
- **FR-019**: System MUST decide an experiment winner, recording the success status, winning variant, and message.
- **FR-020**: System MUST archive an experiment by its ID.
- **FR-021**: System MUST restore an archived experiment by its ID.
- **FR-022**: System MUST duplicate an experiment by its ID, optionally with a new name.
- **FR-023**: System MUST list ERF (Experiment Results Framework) experiments.

#### CLI

- **FR-024**: System MUST provide an `mp flags` command group with subcommands: list, create, get, update, delete, archive, restore, duplicate, set-test-users, history, limits.
- **FR-025**: System MUST provide an `mp experiments` command group with subcommands: list, create, get, update, delete, launch, conclude, decide, archive, restore, duplicate, erf.
- **FR-026**: All CLI commands MUST support `--format` (json, jsonl, table, csv, plain) and `--jq` filtering options consistent with existing commands.

#### Cross-Cutting

- **FR-027**: Feature flag CRUD and lifecycle operations MUST use workspace-scoped URL paths (`/workspaces/{wid}/feature-flags/`), requiring a resolved workspace ID. The limits endpoint uses standard project scoping.
- **FR-028**: Experiment operations MUST use the standard App API URL pattern (top-level scoping via `maybe_scoped_path`).
- **FR-029**: All operations MUST propagate appropriate errors (authentication, not found, validation) with clear messages.
- **FR-030**: All new types MUST be immutable (frozen) and support forward compatibility via extra fields.

### Key Entities

- **Feature Flag**: A toggleable configuration that controls feature visibility. Key attributes: unique identifier, project ID, name, unique key, description, enabled/disabled/archived status, tags, serving method (client/server/remote), ruleset containing variants (key, value, description, control flag, traffic split), rollout rules (name, cohort definition, percentage, variant splits), and test user overrides. Flags use a hash salt for deterministic assignment.
- **Feature Flag Variant**: A named value option within a flag's ruleset. Attributes: key, JSON value, description, whether it is the control variant, and its traffic split percentage.
- **Feature Flag Rollout**: A targeting rule within a flag that defines which users see which variant. Attributes: name, cohort-based targeting definition, rollout percentage, and per-variant split overrides.
- **Experiment**: An A/B test with a defined hypothesis and measurable outcomes. Key attributes: unique identifier, name, description, hypothesis, status (Draft/Active/Concluded/Success/Fail), variants with traffic allocation, success metrics, settings, start/end dates, and creator metadata.
- **Experiment Decision**: The outcome of an experiment, recording whether it succeeded or failed, which variant won, and a summary message.
- **Flag History Event**: A change log entry for a feature flag, recording what changed, when, and by whom. Supports pagination for flags with extensive history.
- **Flag Limits**: Account-level metadata showing the current number of flags, the maximum allowed, and whether the account is on a trial plan.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Users can perform all 11 feature flag operations (list, create, get, update, delete, archive, restore, duplicate, set-test-users, history, limits) through both the library and CLI.
- **SC-002**: Users can manage the full experiment lifecycle (create, launch, conclude, decide) through both the library and CLI.
- **SC-003**: All 23 new library methods follow the established patterns (parameter objects, return types, error handling) consistent with existing dashboard/report/cohort methods.
- **SC-004**: All 23 new CLI subcommands produce correct output in all 5 supported formats (json, jsonl, table, csv, plain).
- **SC-005**: All new operations correctly handle error conditions (invalid state transitions, missing workspace ID, not found, authentication failures) with clear error messages.
- **SC-006**: All new functionality achieves 90% or higher test coverage.
- **SC-007**: All new types pass round-trip serialization tests (construct, serialize, deserialize, compare).

## Assumptions

- OAuth 2.0 PKCE authentication and App API infrastructure (Phase 0, spec 023) are fully implemented and working. All feature management operations will use the existing `app_request()` method with Bearer auth.
- Workspace ID resolution is available and functional. Feature flag operations require workspace-scoped URLs; experiment operations use standard App API scoping.
- The existing Phase 1 patterns (dashboard, report, cohort CRUD) establish the conventions for this phase. Method signatures, type definitions, CLI command structure, error handling, and testing patterns will be replicated exactly.
- Feature flag update uses PUT semantics (full replacement) unlike other domains that use PATCH (partial update). This matches the Rust implementation and the Mixpanel API behavior.
- Experiment state transitions are enforced server-side. The client sends the request and handles the error if the transition is invalid (e.g., launching a non-Draft experiment returns a 400 error).
- The Rust implementation in `mixpanel_data_rust` serves as the canonical reference for endpoint paths, request/response shapes, and behavior. The Django reference in `analytics/` is the ultimate authority for any discrepancies.
- All new Pydantic models use `ConfigDict(frozen=True, extra="allow", populate_by_name=True)` for forward compatibility and immutability, consistent with existing types.
- Flag history and experiment listings use cursor-based pagination via the existing `PaginatedResponse` infrastructure.
