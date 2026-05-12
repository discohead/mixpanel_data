# Tasks: Data Governance CRUD

**Input**: Design documents from `/specs/027-data-governance-crud/`
**Prerequisites**: plan.md (required), spec.md (required for user stories), research.md, data-model.md, contracts/

**Tests**: This project follows strict TDD (per CLAUDE.md). Tests are written FIRST for each layer.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Phase 1: Setup

**Purpose**: No new project setup needed — this feature adds to an existing codebase. Phase 1 is a no-op.

**Checkpoint**: Existing project structure verified, ready for foundational types.

---

## Phase 2: Foundational (Pydantic Types — All Domains)

**Purpose**: All Pydantic models MUST exist before API client, workspace, or CLI layers can be implemented. Types are shared across all user stories.

**CRITICAL**: No user story work can begin until this phase is complete.

### Tests for Foundational Types

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [X] T001 [P] Write type tests for EventDefinition, PropertyDefinition, LexiconTag frozen models in tests/unit/test_types_data_governance.py
- [X] T002 [P] Write type tests for UpdateEventDefinitionParams, UpdatePropertyDefinitionParams serialization (exclude_none) in tests/unit/test_types_data_governance.py
- [X] T003 [P] Write type tests for BulkEventUpdate, BulkUpdateEventsParams, BulkPropertyUpdate, BulkUpdatePropertiesParams in tests/unit/test_types_data_governance.py
- [X] T004 [P] Write type tests for CreateTagParams, UpdateTagParams in tests/unit/test_types_data_governance.py
- [X] T005 [P] Write type tests for DropFilter, CreateDropFilterParams, UpdateDropFilterParams, DropFilterLimitsResponse in tests/unit/test_types_data_governance.py
- [X] T006 [P] Write type tests for ComposedPropertyValue, CustomProperty, CreateCustomPropertyParams (incl. validation rules), UpdateCustomPropertyParams in tests/unit/test_types_data_governance.py
- [X] T007 [P] Write type tests for LookupTable, UploadLookupTableParams, MarkLookupTableReadyParams, LookupTableUploadUrl, UpdateLookupTableParams in tests/unit/test_types_data_governance.py
- [X] T008 [P] Write property-based tests for all data governance types round-trip serialization in tests/unit/test_types_data_governance_pbt.py

### Implementation for Foundational Types

- [X] T009 Add EventDefinition and PropertyDefinition frozen models (with PropertyResourceType) to src/mixpanel_data/types.py
- [X] T010 Add UpdateEventDefinitionParams and UpdatePropertyDefinitionParams to src/mixpanel_data/types.py
- [X] T011 [P] Add BulkEventUpdate, BulkUpdateEventsParams, BulkPropertyUpdate, BulkUpdatePropertiesParams to src/mixpanel_data/types.py
- [X] T012 [P] Add LexiconTag, CreateTagParams, UpdateTagParams to src/mixpanel_data/types.py
- [X] T013 [P] Add DropFilter, CreateDropFilterParams, UpdateDropFilterParams, DropFilterLimitsResponse to src/mixpanel_data/types.py
- [X] T014 [P] Add ComposedPropertyValue, CustomProperty, CreateCustomPropertyParams (with mutual exclusion validation), UpdateCustomPropertyParams to src/mixpanel_data/types.py
- [X] T015 [P] Add LookupTable, UploadLookupTableParams, MarkLookupTableReadyParams, LookupTableUploadUrl, UpdateLookupTableParams to src/mixpanel_data/types.py
- [X] T016 Export all new types from src/mixpanel_data/__init__.py

**Checkpoint**: All 25 Pydantic models exist, all type tests pass. `just typecheck` passes.

---

## Phase 3: User Story 1 — Manage Event and Property Definitions (Priority: P1) MVP

**Goal**: Users can get, update, delete, and bulk-update event and property definitions via library and CLI.

**Independent Test**: Update an event definition's description, verify change persists. Bulk-update 20 events with new tags, confirm all applied.

### Tests for User Story 1

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [X] T017 [P] [US1] Write API client tests for get_event_definitions, update_event_definition, delete_event_definition, bulk_update_event_definitions in tests/unit/test_api_client_data_governance.py
- [X] T018 [P] [US1] Write API client tests for get_property_definitions, update_property_definition, bulk_update_property_definitions in tests/unit/test_api_client_data_governance.py
- [X] T019 [P] [US1] Write workspace tests for get_event_definitions, update_event_definition, delete_event_definition, bulk_update_event_definitions in tests/unit/test_workspace_data_governance.py
- [X] T020 [P] [US1] Write workspace tests for get_property_definitions, update_property_definition, bulk_update_property_definitions in tests/unit/test_workspace_data_governance.py

### Implementation for User Story 1

- [X] T021 [P] [US1] Add get_event_definitions, update_event_definition, delete_event_definition, bulk_update_event_definitions to src/mixpanel_data/_internal/api_client.py
- [X] T022 [P] [US1] Add get_property_definitions, update_property_definition, bulk_update_property_definitions to src/mixpanel_data/_internal/api_client.py
- [X] T023 [US1] Add get_event_definitions, update_event_definition, delete_event_definition, bulk_update_event_definitions to src/mixpanel_data/workspace.py
- [X] T024 [US1] Add get_property_definitions, update_property_definition, bulk_update_property_definitions to src/mixpanel_data/workspace.py
- [X] T025 [US1] Create lexicon CLI commands for events (get, update, delete, bulk-update) and properties (get, update, bulk-update) in src/mixpanel_data/cli/commands/lexicon.py
- [X] T026 [US1] Register lexicon_app in src/mixpanel_data/cli/main.py
- [X] T027 [P] [US1] Write CLI tests for lexicon events and properties subcommands in tests/unit/cli/test_lexicon.py

**Checkpoint**: Event and property definition CRUD works end-to-end. `mp lexicon events get --names Purchase` returns data.

---

## Phase 4: User Story 2 — Manage Lexicon Tags (Priority: P1)

**Goal**: Users can list, create, update, and delete lexicon tags via library and CLI.

**Independent Test**: Create a tag, list to verify, rename it, then delete it.

### Tests for User Story 2

- [X] T028 [P] [US2] Write API client tests for list_lexicon_tags, create_lexicon_tag, update_lexicon_tag, delete_lexicon_tag in tests/unit/test_api_client_data_governance.py
- [X] T029 [P] [US2] Write workspace tests for list_lexicon_tags, create_lexicon_tag, update_lexicon_tag, delete_lexicon_tag in tests/unit/test_workspace_data_governance.py

### Implementation for User Story 2

- [X] T030 [P] [US2] Add list_lexicon_tags, create_lexicon_tag, update_lexicon_tag, delete_lexicon_tag to src/mixpanel_data/_internal/api_client.py
- [X] T031 [US2] Add list_lexicon_tags, create_lexicon_tag, update_lexicon_tag, delete_lexicon_tag to src/mixpanel_data/workspace.py
- [X] T032 [US2] Add lexicon tags subcommands (list, create, update, delete) to src/mixpanel_data/cli/commands/lexicon.py
- [X] T033 [P] [US2] Write CLI tests for lexicon tags subcommands in tests/unit/cli/test_lexicon.py

**Checkpoint**: Tag management works end-to-end. `mp lexicon tags list` returns tags.

---

## Phase 5: User Story 3 — Manage Drop Filters (Priority: P2)

**Goal**: Users can list, create, update, delete drop filters and check limits.

**Independent Test**: Create a drop filter for "debug_log", list to confirm, update to deactivate, delete it, check limits.

### Tests for User Story 3

- [X] T034 [P] [US3] Write API client tests for list_drop_filters, create_drop_filter, update_drop_filter, delete_drop_filter, get_drop_filter_limits in tests/unit/test_api_client_data_governance.py
- [X] T035 [P] [US3] Write workspace tests for all drop filter methods in tests/unit/test_workspace_data_governance.py

### Implementation for User Story 3

- [X] T036 [P] [US3] Add list_drop_filters, create_drop_filter, update_drop_filter, delete_drop_filter, get_drop_filter_limits to src/mixpanel_data/_internal/api_client.py
- [X] T037 [US3] Add list_drop_filters, create_drop_filter, update_drop_filter, delete_drop_filter, get_drop_filter_limits to src/mixpanel_data/workspace.py
- [X] T038 [US3] Create drop filters CLI commands (list, create, update, delete, limits) in src/mixpanel_data/cli/commands/drop_filters.py
- [X] T039 [US3] Register drop_filters_app in src/mixpanel_data/cli/main.py
- [X] T040 [P] [US3] Write CLI tests for drop filter subcommands in tests/unit/cli/test_drop_filters.py

**Checkpoint**: Drop filter management works end-to-end. `mp drop-filters list` returns filters.

---

## Phase 6: User Story 4 — Manage Custom Properties (Priority: P2)

**Goal**: Users can list, create, get, update, delete, and validate custom properties.

**Independent Test**: Validate a formula, create a custom property, retrieve by ID, update, then delete.

### Tests for User Story 4

- [X] T041 [P] [US4] Write API client tests for list_custom_properties, create_custom_property, get_custom_property, update_custom_property, delete_custom_property, validate_custom_property in tests/unit/test_api_client_data_governance.py
- [X] T042 [P] [US4] Write workspace tests for all custom property methods in tests/unit/test_workspace_data_governance.py

### Implementation for User Story 4

- [X] T043 [P] [US4] Add list_custom_properties, create_custom_property, get_custom_property, update_custom_property (PUT), delete_custom_property, validate_custom_property to src/mixpanel_data/_internal/api_client.py
- [X] T044 [US4] Add list_custom_properties, create_custom_property, get_custom_property, update_custom_property, delete_custom_property, validate_custom_property to src/mixpanel_data/workspace.py
- [X] T045 [US4] Create custom properties CLI commands (list, get, create, update, delete, validate) in src/mixpanel_data/cli/commands/custom_properties.py
- [X] T046 [US4] Register custom_properties_app in src/mixpanel_data/cli/main.py
- [X] T047 [P] [US4] Write CLI tests for custom property subcommands in tests/unit/cli/test_custom_properties.py

**Checkpoint**: Custom property management works end-to-end. `mp custom-properties list` returns properties.

---

## Phase 7: User Story 5 — Manage Lookup Tables (Priority: P2)

**Goal**: Users can list, upload (3-step), check status, update, download, and delete lookup tables.

**Independent Test**: List tables, upload a CSV, check status, download it, then delete.

### Tests for User Story 5

- [X] T048 [P] [US5] Write API client tests for list_lookup_tables, get_lookup_upload_url, upload_to_signed_url, register_lookup_table, mark_lookup_table_ready, get_lookup_upload_status in tests/unit/test_api_client_data_governance.py
- [X] T049 [P] [US5] Write API client tests for update_lookup_table, delete_lookup_tables, download_lookup_table, get_lookup_download_url in tests/unit/test_api_client_data_governance.py
- [X] T050 [P] [US5] Write workspace tests for all lookup table methods including upload_lookup_table 3-step orchestration in tests/unit/test_workspace_data_governance.py

### Implementation for User Story 5

- [X] T051 [P] [US5] Add list_lookup_tables, get_lookup_upload_url, upload_to_signed_url, register_lookup_table, get_lookup_upload_status to src/mixpanel_data/_internal/api_client.py
- [X] T052 [P] [US5] Add mark_lookup_table_ready, update_lookup_table, delete_lookup_tables, download_lookup_table, get_lookup_download_url to src/mixpanel_data/_internal/api_client.py
- [X] T053 [US5] Add list_lookup_tables, upload_lookup_table (3-step orchestration with polling), mark_lookup_table_ready, get_lookup_upload_url, get_lookup_upload_status to src/mixpanel_data/workspace.py
- [X] T054 [US5] Add update_lookup_table, delete_lookup_tables, download_lookup_table, get_lookup_download_url to src/mixpanel_data/workspace.py
- [X] T055 [US5] Create lookup tables CLI commands (list, upload, update, delete, upload-url, download, download-url) in src/mixpanel_data/cli/commands/lookup_tables.py
- [X] T056 [US5] Register lookup_tables_app in src/mixpanel_data/cli/main.py
- [X] T057 [P] [US5] Write CLI tests for lookup table subcommands in tests/unit/cli/test_lookup_tables.py

**Checkpoint**: Lookup table management works end-to-end including multi-step upload. `mp lookup-tables list` returns tables.

---

## Phase 8: User Story 6 — Manage Custom Events (Priority: P3)

**Goal**: Users can list, update, and delete custom events via library and CLI.

**Independent Test**: List custom events, update one, delete one.

### Tests for User Story 6

- [X] T058 [P] [US6] Write API client tests for list_custom_events, update_custom_event, delete_custom_event in tests/unit/test_api_client_data_governance.py
- [X] T059 [P] [US6] Write workspace tests for all custom event methods in tests/unit/test_workspace_data_governance.py

### Implementation for User Story 6

- [X] T060 [US6] Add list_custom_events, update_custom_event, delete_custom_event to src/mixpanel_data/_internal/api_client.py (reuses data-definitions/events/ endpoints with custom_event filter)
- [X] T061 [US6] Add list_custom_events, update_custom_event, delete_custom_event to src/mixpanel_data/workspace.py
- [X] T062 [US6] Create custom events CLI commands (list, update, delete) in src/mixpanel_data/cli/commands/custom_events.py
- [X] T063 [US6] Register custom_events_app in src/mixpanel_data/cli/main.py
- [X] T064 [P] [US6] Write CLI tests for custom event subcommands in tests/unit/cli/test_custom_events.py

**Checkpoint**: Custom event management works end-to-end. `mp custom-events list` returns custom events.

---

## Phase 9: User Story 7 — View Tracking Metadata and Definition History (Priority: P3)

**Goal**: Users can view tracking metadata and definition change history for audit.

**Independent Test**: Retrieve tracking metadata for a known event, view its change history.

### Tests for User Story 7

- [X] T065 [P] [US7] Write API client tests for get_tracking_metadata, get_event_history, get_property_history in tests/unit/test_api_client_data_governance.py
- [X] T066 [P] [US7] Write workspace tests for tracking metadata and history methods in tests/unit/test_workspace_data_governance.py

### Implementation for User Story 7

- [X] T067 [P] [US7] Add get_tracking_metadata, get_event_history, get_property_history to src/mixpanel_data/_internal/api_client.py
- [X] T068 [US7] Add get_tracking_metadata, get_event_history, get_property_history to src/mixpanel_data/workspace.py
- [X] T069 [US7] Add lexicon tracking-metadata, event-history, property-history subcommands to src/mixpanel_data/cli/commands/lexicon.py
- [X] T070 [P] [US7] Write CLI tests for tracking metadata and history subcommands in tests/unit/cli/test_lexicon.py

**Checkpoint**: Audit and metadata queries work end-to-end. `mp lexicon event-history --event-name Purchase` returns history.

---

## Phase 10: User Story 8 — Export Lexicon Definitions (Priority: P3)

**Goal**: Users can export the full data catalog for compliance and documentation.

**Independent Test**: Export all event definitions, verify export contains expected data.

### Tests for User Story 8

- [X] T071 [P] [US8] Write API client test for export_lexicon in tests/unit/test_api_client_data_governance.py
- [X] T072 [P] [US8] Write workspace test for export_lexicon in tests/unit/test_workspace_data_governance.py

### Implementation for User Story 8

- [X] T073 [US8] Add export_lexicon to src/mixpanel_data/_internal/api_client.py
- [X] T074 [US8] Add export_lexicon to src/mixpanel_data/workspace.py
- [X] T075 [US8] Add lexicon export subcommand to src/mixpanel_data/cli/commands/lexicon.py
- [X] T076 [P] [US8] Write CLI test for lexicon export subcommand in tests/unit/cli/test_lexicon.py

**Checkpoint**: Lexicon export works end-to-end. `mp lexicon export --types events,properties` returns full export.

---

## Phase 11: Polish & Cross-Cutting Concerns

**Purpose**: Quality gates and final verification across all stories.

- [X] T077 Run `just lint` and fix any lint errors across all new code
- [X] T078 Run `just typecheck` and fix any mypy --strict errors across all new code
- [X] T079 Run `just test` and verify all tests pass
- [X] T080 Run `just test-cov` and verify coverage >= 90% for new code
- [X] T081 [P] Run `just mutate` on data governance modules and verify mutation score >= 80%
- [X] T082 Verify all CLI commands have `--help` with complete descriptions and test `--format table`, `--format csv`, `--format jsonl` on one command per CLI group (lexicon, custom-properties, custom-events, drop-filters, lookup-tables)
- [X] T083 Run quickstart.md validation — execute code examples from specs/027-data-governance-crud/quickstart.md against mock transport

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No-op for this feature
- **Foundational (Phase 2)**: Types MUST be complete before any user story — BLOCKS all stories
- **User Stories (Phases 3-10)**: All depend on Phase 2 completion
  - US1 + US2 are P1 (both can proceed in parallel after Phase 2)
  - US3 + US4 + US5 are P2 (can proceed in parallel after Phase 2, independent of US1/US2)
  - US6 + US7 + US8 are P3 (can proceed in parallel, US6/US7/US8 share lexicon.py CLI file so serialize CLI tasks)
- **Polish (Phase 11)**: Depends on all user stories being complete

### User Story Dependencies

- **US1 (P1)**: No story dependencies. Uses data-definitions/events/ and data-definitions/properties/ endpoints.
- **US2 (P1)**: No story dependencies. Uses data-definitions/tags/ endpoint. Shares lexicon.py CLI with US1.
- **US3 (P2)**: No story dependencies. Uses data-definitions/events/drop-filters/ endpoint.
- **US4 (P2)**: No story dependencies. Uses custom_properties/ endpoint.
- **US5 (P2)**: No story dependencies. Uses data-definitions/lookup-tables/ endpoint.
- **US6 (P3)**: Reuses EventDefinition type from US1 but is otherwise independent.
- **US7 (P3)**: No story dependencies. Shares lexicon.py CLI with US1/US2.
- **US8 (P3)**: No story dependencies. Shares lexicon.py CLI with US1/US2.

### Within Each User Story

- Tests MUST be written and FAIL before implementation
- API client methods before workspace methods
- Workspace methods before CLI commands
- CLI registration after CLI commands implemented

### Parallel Opportunities

- All Phase 2 type tests (T001-T008) can run in parallel
- All Phase 2 type implementations (T011-T015) can run in parallel (different model groups)
- US1 and US2 can be implemented in parallel (different endpoints, but share lexicon.py — serialize CLI tasks)
- US3, US4, US5 can be implemented fully in parallel (separate endpoints, separate CLI files)
- Within each story: API client tests + workspace tests can run in parallel

---

## Parallel Example: Phase 2 (Foundational Types)

```bash
# Launch all type tests in parallel:
Task: "Write type tests for EventDefinition, PropertyDefinition, LexiconTag" (T001)
Task: "Write type tests for UpdateEventDefinitionParams, UpdatePropertyDefinitionParams" (T002)
Task: "Write type tests for BulkEventUpdate, BulkUpdateEventsParams" (T003)
Task: "Write type tests for CreateTagParams, UpdateTagParams" (T004)
Task: "Write type tests for DropFilter, CreateDropFilterParams" (T005)
Task: "Write type tests for CustomProperty, CreateCustomPropertyParams" (T006)
Task: "Write type tests for LookupTable, UploadLookupTableParams" (T007)
Task: "Write PBT tests for all data governance types" (T008)
```

## Parallel Example: P2 Stories (after Phase 2 complete)

```bash
# Launch all P2 stories in parallel (independent endpoints and CLI files):
Task: "US3 - Drop filters API client" (T036)
Task: "US4 - Custom properties API client" (T043)
Task: "US5 - Lookup tables API client" (T051, T052)
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 2: Foundational types (all 25 models)
2. Complete Phase 3: User Story 1 (event/property definitions)
3. **STOP and VALIDATE**: Test US1 independently — `mp lexicon events get --names Purchase`
4. This alone delivers significant value for data governance teams

### Incremental Delivery

1. Phase 2 (types) → Foundation ready
2. US1 (definitions) + US2 (tags) → Core lexicon management (MVP!)
3. US3 (drop filters) + US4 (custom properties) + US5 (lookup tables) → Full governance toolkit
4. US6 (custom events) + US7 (metadata/history) + US8 (export) → Audit and compliance
5. Each story adds value without breaking previous stories

### Parallel Team Strategy

With multiple developers:

1. Everyone completes Phase 2 (types) together
2. Once types are done:
   - Developer A: US1 (definitions) + US2 (tags) — P1 priority
   - Developer B: US3 (drop filters) + US4 (custom properties) — P2 priority
   - Developer C: US5 (lookup tables) — P2 priority (most complex)
3. Then P3 stories (US6, US7, US8) can be distributed

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Each user story is independently completable and testable
- Tests must fail before implementing (TDD per CLAUDE.md)
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
- US6, US7, US8 share lexicon.py CLI — serialize CLI tasks within those stories
- Drop filter mutations return full list (unique API pattern)
- Lookup table upload is 3-step with optional polling (most complex single method)
- Custom property update uses PUT not PATCH (full replacement)
- Tag deletion uses POST with {"delete": true} (unusual pattern)
- Edge cases from spec (partial bulk failure, upload size limits, filter limit exceeded, formula referencing non-existent property, network interruption during upload) are server-side behaviors. The existing `@handle_errors` decorator and API error hierarchy (QueryError, ServerError, RateLimitError) handle these transparently. No dedicated edge case tasks needed — verify error propagation in workspace tests for each story.
