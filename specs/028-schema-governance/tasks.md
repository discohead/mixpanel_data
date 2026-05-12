# Tasks: Schema Registry & Data Governance

**Input**: Design documents from `/specs/028-schema-governance/`
**Prerequisites**: plan.md (required), spec.md (required), research.md, data-model.md, contracts/

**Tests**: Included per project TDD requirement (CLAUDE.md mandates strict TDD).

**Organization**: Tasks grouped by user story for independent implementation and testing.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

- Source: `src/mixpanel_data/`
- Tests: `tests/`
- Types: `src/mixpanel_data/types.py`
- API Client: `src/mixpanel_data/_internal/api_client.py`
- Workspace: `src/mixpanel_data/workspace.py`
- CLI Commands: `src/mixpanel_data/cli/commands/`

---

## Phase 1: Setup

**Purpose**: Verify existing infrastructure and study patterns for new code

- [X] T001 Verify existing `app_request()` and `maybe_scoped_path()` methods work in src/mixpanel_data/_internal/api_client.py — read existing schema methods (`get_schemas`, `get_schema`) and bulk operation patterns (`bulk_delete_cohorts`, `bulk_update_bookmarks`) to confirm patterns
- [X] T002 [P] Study existing test patterns: read tests for similar domains (e.g., tests/test_workspace_cohorts.py, tests/test_api_client_cohorts.py) to understand respx mocking, fixture setup, and assertion patterns
- [X] T003 [P] Study existing CLI test patterns: read tests for similar CLI commands (e.g., tests/cli/) to understand subprocess testing patterns

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: No new shared infrastructure needed — existing App API infrastructure (Bearer auth, workspace scoping, `app_request()`, `maybe_scoped_path()`) is complete from prior phases. All foundational code is already in place.

**Checkpoint**: Existing infrastructure confirmed — user story implementation can begin.

---

## Phase 3: User Story 1 — Schema Registry Management (Priority: P1) MVP

**Goal**: Full CRUD for schema registry definitions (list, create, create-bulk, update, update-bulk, delete) via library and CLI.

**Independent Test**: Create a schema for an event, list schemas to confirm, update it, delete it. Bulk create/update multiple schemas.

### Tests for User Story 1

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [X] T004 [P] [US1] Write API client tests for schema registry methods (list, create, create_bulk, update, update_bulk, delete) with respx mocks in tests/test_api_client_schemas.py — mock endpoints: GET/POST/PATCH/DELETE `schemas/`, `schemas/{et}/`, `schemas/{et}/{en}/` — include edge cases: create schema for entity that already exists, bulk create with truncate=true and empty entries, bulk with duplicate entries
- [X] T005 [P] [US1] Write workspace tests for schema registry methods in tests/test_workspace_schemas.py — test list_schema_registry, create_schema, create_schemas_bulk, update_schema, update_schemas_bulk, delete_schemas with mocked API client
- [X] T006 [P] [US1] Write PBT tests for schema registry types (SchemaEntry, BulkCreateSchemasParams, BulkCreateSchemasResponse, BulkPatchResult, DeleteSchemasResponse) in tests/test_types_schemas_pbt.py — round-trip serialization, frozen immutability, extra field preservation

### Implementation for User Story 1

- [X] T007 [P] [US1] Add schema registry Pydantic types to src/mixpanel_data/types.py — SchemaEntry (frozen, extra=allow, camelCase alias), BulkCreateSchemasParams, BulkCreateSchemasResponse (frozen), BulkPatchResult (frozen, extra=allow, camelCase alias), DeleteSchemasResponse (frozen) — follow existing patterns (Dashboard, Bookmark models)
- [X] T008 [US1] Add 6 schema registry API client methods to src/mixpanel_data/_internal/api_client.py — list_schema_registry(entity_type), create_schema(entity_type, entity_name, schema_json), create_schemas_bulk(params), update_schema(entity_type, entity_name, schema_json), update_schemas_bulk(params), delete_schemas(entity_type, entity_name) — use `maybe_scoped_path()`, percent-encode path segments with `urllib.parse.quote(segment, safe="")`
- [X] T009 [US1] Add 6 schema registry workspace methods to src/mixpanel_data/workspace.py — list_schema_registry, create_schema, create_schemas_bulk, update_schema, update_schemas_bulk, delete_schemas — delegate to API client, validate model responses with Pydantic
- [X] T010 [US1] Create CLI command file src/mixpanel_data/cli/commands/schemas.py — schemas_app Typer group with 6 subcommands: list (--entity-type), create (--entity-type, --entity-name, --schema-json), create-bulk (--entries, --truncate, --entity-type), update (--entity-type, --entity-name, --schema-json), update-bulk (--entries), delete (--entity-type, --entity-name) — follow existing pattern from lexicon.py
- [X] T011 [US1] Register schemas_app in src/mixpanel_data/cli/main.py — add `app.add_typer(schemas_app, name="schemas")` and import
- [X] T012 [US1] Write CLI tests for schemas commands in tests/cli/test_schemas_cli.py — test all 6 subcommands with --format json/table/csv, --jq filter, error cases

**Checkpoint**: Schema registry fully functional — can create, list, update, delete schemas via library and CLI.

---

## Phase 4: User Story 2 — Schema Enforcement Configuration (Priority: P2)

**Goal**: Full lifecycle management of schema enforcement rules (get, init, update, replace, delete) via library and CLI.

**Independent Test**: Initialize enforcement with a rule, read it back, update it, replace it, delete it.

### Tests for User Story 2

- [X] T013 [P] [US2] Write API client tests for enforcement methods (get, init, update, replace, delete) with respx mocks in tests/test_api_client_governance.py — mock endpoints: GET/POST/PATCH/PUT/DELETE `data-definitions/schema/` — include edge case: delete enforcement that was never initialized (expect error)
- [X] T014 [P] [US2] Write workspace tests for enforcement methods in tests/test_workspace_governance.py — test get_schema_enforcement, init_schema_enforcement, update_schema_enforcement, replace_schema_enforcement, delete_schema_enforcement

### Implementation for User Story 2

- [X] T015 [P] [US2] Add enforcement Pydantic types to src/mixpanel_data/types.py — SchemaEnforcementConfig (frozen, extra=allow, camelCase alias), InitSchemaEnforcementParams (camelCase alias), UpdateSchemaEnforcementParams (camelCase alias), ReplaceSchemaEnforcementParams (camelCase alias)
- [X] T016 [US2] Add 5 enforcement API client methods to src/mixpanel_data/_internal/api_client.py — get_schema_enforcement(fields), init_schema_enforcement(params), update_schema_enforcement(params), replace_schema_enforcement(params), delete_schema_enforcement() — use `maybe_scoped_path("data-definitions/schema/")`
- [X] T017 [US2] Add 5 enforcement workspace methods to src/mixpanel_data/workspace.py — delegate to API client, return typed SchemaEnforcementConfig for get, dict[str, Any] for mutations
- [X] T018 [US2] Add enforcement subgroup to src/mixpanel_data/cli/commands/lexicon.py — create enforcement_app Typer with 5 subcommands: get (--fields), init (--rule-event), update (--body), replace (--body), delete — add via `lexicon_app.add_typer(enforcement_app, name="enforcement")`
- [X] T019 [US2] Write CLI tests for enforcement commands in tests/cli/test_lexicon_governance_cli.py — test all 5 subcommands with various formats and error cases

**Checkpoint**: Schema enforcement fully functional — can manage enforcement lifecycle via library and CLI.

---

## Phase 5: User Story 3 — Data Auditing (Priority: P3)

**Goal**: Run full and events-only data audits to identify schema violations.

**Independent Test**: Run a full audit and events-only audit, receive violation reports.

### Tests for User Story 3

- [X] T020 [P] [US3] Write API client tests for audit methods (run_audit, run_audit_events_only) with respx mocks in tests/test_api_client_governance.py — mock GET `data-definitions/audit/` and `data-definitions/audit-events-only/` — test special 2-element array response parsing with `_raw=True`
- [X] T021 [P] [US3] Write workspace tests for audit methods in tests/test_workspace_governance.py — test run_audit, run_audit_events_only return typed AuditResponse
- [X] T022 [P] [US3] Write PBT tests for audit types (AuditResponse, AuditViolation) in tests/test_types_governance_pbt.py — round-trip serialization, frozen immutability

### Implementation for User Story 3

- [X] T023 [P] [US3] Add audit Pydantic types to src/mixpanel_data/types.py — AuditResponse (frozen, violations: list[AuditViolation], computed_at: str), AuditViolation (frozen, extra=allow, camelCase alias for property_type_error)
- [X] T024 [US3] Add 2 audit API client methods to src/mixpanel_data/_internal/api_client.py — run_audit(), run_audit_events_only() — use `app_request("GET", path, _raw=True)` and manually parse 2-element array response: results[0]=violations, results[1]=metadata with computed_at
- [X] T025 [US3] Add 2 audit workspace methods to src/mixpanel_data/workspace.py — run_audit, run_audit_events_only returning AuditResponse
- [X] T026 [US3] Add audit command to src/mixpanel_data/cli/commands/lexicon.py — single `audit` command with `--events-only` flag
- [X] T027 [US3] Write CLI tests for audit command in tests/cli/test_lexicon_governance_cli.py — test with and without --events-only, various output formats

**Checkpoint**: Data auditing fully functional — can run audits and view violations via library and CLI.

---

## Phase 6: User Story 4 — Data Volume Anomaly Management (Priority: P4)

**Goal**: List, update, and bulk-update data volume anomaly statuses.

**Independent Test**: List anomalies with filters, update a single anomaly status, bulk-update multiple.

### Tests for User Story 4

- [X] T028 [P] [US4] Write API client tests for anomaly methods (list, update, bulk_update) with respx mocks in tests/test_api_client_governance.py — mock GET/PATCH `data-definitions/data-volume-anomalies/` and `data-definitions/data-volume-anomalies/bulk/` — test response extraction from `results.anomalies` — include edge case: list anomalies for project with no anomaly history (expect empty list)
- [X] T029 [P] [US4] Write workspace tests for anomaly methods in tests/test_workspace_governance.py — test list_data_volume_anomalies, update_anomaly, bulk_update_anomalies

### Implementation for User Story 4

- [X] T030 [P] [US4] Add anomaly Pydantic types to src/mixpanel_data/types.py — DataVolumeAnomaly (frozen, extra=allow), UpdateAnomalyParams, BulkUpdateAnomalyParams, BulkAnomalyEntry (camelCase alias)
- [X] T031 [US4] Add 3 anomaly API client methods to src/mixpanel_data/_internal/api_client.py — list_data_volume_anomalies(query_params), update_anomaly(params), bulk_update_anomalies(params) — list method extracts from `results["anomalies"]` using `_raw=True`
- [X] T032 [US4] Add 3 anomaly workspace methods to src/mixpanel_data/workspace.py — delegate to API client, return typed DataVolumeAnomaly list for list, dict for mutations
- [X] T033 [US4] Add anomalies subgroup to src/mixpanel_data/cli/commands/lexicon.py — create anomalies_app Typer with 3 subcommands: list (--status, --limit), update (--id, --status, --anomaly-class), bulk-update (--body) — add via `lexicon_app.add_typer(anomalies_app, name="anomalies")`
- [X] T034 [US4] Write CLI tests for anomalies commands in tests/cli/test_lexicon_governance_cli.py — test list with filters, update, bulk-update

**Checkpoint**: Anomaly management fully functional — can triage anomalies via library and CLI.

---

## Phase 7: User Story 5 — Event Deletion Requests (Priority: P5)

**Goal**: Full lifecycle management of event deletion requests (preview, create, list, cancel).

**Independent Test**: Preview a deletion filter, create a request, list requests, cancel a pending request.

### Tests for User Story 5

- [X] T035 [P] [US5] Write API client tests for deletion request methods (list, create, cancel, preview) with respx mocks in tests/test_api_client_governance.py — mock GET/POST/DELETE `data-definitions/events/deletion-requests/` and POST `data-definitions/events/deletion-requests/preview-filters/` — include edge cases: preview filters matching zero events (expect empty set), cancel already-completed request (expect error)
- [X] T036 [P] [US5] Write workspace tests for deletion request methods in tests/test_workspace_governance.py — test list_deletion_requests, create_deletion_request, cancel_deletion_request, preview_deletion_filters

### Implementation for User Story 5

- [X] T037 [P] [US5] Add deletion request Pydantic types to src/mixpanel_data/types.py — EventDeletionRequest (frozen, extra=allow), CreateDeletionRequestParams, PreviewDeletionFiltersParams
- [X] T038 [US5] Add 4 deletion request API client methods to src/mixpanel_data/_internal/api_client.py — list_deletion_requests(), create_deletion_request(params), cancel_deletion_request(id) with JSON body {"id": id}, preview_deletion_filters(params)
- [X] T039 [US5] Add 4 deletion request workspace methods to src/mixpanel_data/workspace.py — delegate to API client, return typed lists
- [X] T040 [US5] Add deletion-requests subgroup to src/mixpanel_data/cli/commands/lexicon.py — create deletion_requests_app Typer with 4 subcommands: list, create (--event-name, --from-date, --to-date, --filters), cancel (positional ID), preview (--event-name, --from-date, --to-date, --filters) — add via `lexicon_app.add_typer(deletion_requests_app, name="deletion-requests")`
- [X] T041 [US5] Write CLI tests for deletion-requests commands in tests/cli/test_lexicon_governance_cli.py — test all 4 subcommands, especially preview as read-only operation

**Checkpoint**: Deletion request management fully functional — can manage deletion lifecycle via library and CLI.

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Quality, docs, and cross-story validation

- [X] T042 [P] Run `just check` (lint + typecheck + test) and fix any failures across all new code
- [X] T043 [P] Run `just test-cov` and ensure coverage >=90% for new modules — add tests for any uncovered branches
- [X] T044 [P] Run `just test-pbt` to verify all property-based tests pass with default profile (100 examples)
- [X] T045 Validate quickstart.md examples work end-to-end against the implementation — fix any discrepancies between contracts and actual behavior
- [X] T046 [P] Add new types to `__init__.py` public exports in src/mixpanel_data/__init__.py — export SchemaEntry, BulkCreateSchemasParams, BulkCreateSchemasResponse, BulkPatchResult, DeleteSchemasResponse, SchemaEnforcementConfig, InitSchemaEnforcementParams, UpdateSchemaEnforcementParams, ReplaceSchemaEnforcementParams, AuditResponse, AuditViolation, DataVolumeAnomaly, UpdateAnomalyParams, BulkUpdateAnomalyParams, BulkAnomalyEntry, EventDeletionRequest, CreateDeletionRequestParams, PreviewDeletionFiltersParams

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — can start immediately
- **Foundational (Phase 2)**: Depends on Setup — confirms infrastructure is ready
- **User Stories (Phases 3–7)**: All depend on Setup/Foundational confirmation
  - Each user story is independently implementable after Phase 2
  - User stories can proceed in parallel or sequentially in priority order
- **Polish (Phase 8)**: Depends on all desired user stories being complete

### User Story Dependencies

- **US1 (P1) — Schema Registry**: No dependencies on other stories. Foundation for all governance features (schemas must exist before enforcement, auditing). **Start here for MVP.**
- **US2 (P2) — Enforcement**: Logically depends on schemas existing (US1), but technically independent — enforcement API works regardless of whether schemas exist yet.
- **US3 (P3) — Auditing**: Logically depends on schemas (US1) for meaningful results, but API works independently.
- **US4 (P4) — Anomalies**: Fully independent of all other stories. Can be implemented in any order.
- **US5 (P5) — Deletion Requests**: Fully independent of all other stories. Can be implemented in any order.

### Within Each User Story

1. Tests MUST be written and FAIL before implementation (TDD)
2. Types before API client (types are imported by API client)
3. API client before workspace (workspace delegates to API client)
4. Workspace before CLI (CLI delegates to workspace)
5. CLI tests after CLI implementation

### Parallel Opportunities

**Within US1**: T004, T005, T006 (tests) in parallel → T007 (types) → T008 (API) → T009 (workspace) → T010, T011 (CLI) → T012 (CLI tests)

**Across stories**: Once Phase 2 confirmed, US1–US5 can all run in parallel since they modify different sections of the same files. In practice, types.py changes should be sequenced to avoid merge conflicts, but API client, workspace, and CLI changes are additive and safe to parallelize.

**Safe parallel pairs** (no file conflicts):
- US4 (anomalies) + US5 (deletion requests) — different endpoints, different types, different CLI subgroups

---

## Parallel Example: User Story 1

```bash
# Launch all tests for US1 together (TDD - write first, watch fail):
Agent: "Write API client schema tests in tests/test_api_client_schemas.py"
Agent: "Write workspace schema tests in tests/test_workspace_schemas.py"
Agent: "Write PBT schema type tests in tests/test_types_schemas_pbt.py"

# Then launch types (independent of other files):
Agent: "Add schema registry Pydantic types to src/mixpanel_data/types.py"

# Then sequential: API client → workspace → CLI (dependency chain)
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (verify infrastructure)
2. Skip Phase 2: Foundational (nothing needed)
3. Complete Phase 3: User Story 1 — Schema Registry
4. **STOP and VALIDATE**: Test schema CRUD independently
5. Run `just check` to confirm quality gates pass

### Incremental Delivery

1. US1 (Schema Registry) → MVP with full schema CRUD
2. US2 (Enforcement) → Add governance policy management
3. US3 (Auditing) → Add data quality diagnostics
4. US4 (Anomalies) → Add operational monitoring
5. US5 (Deletion Requests) → Add compliance operations
6. Polish → Cross-cutting quality, exports, coverage

Each story adds independent value without breaking previous stories.

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- TDD is mandatory: write tests first, watch them fail, then implement
- Study existing test patterns before writing new tests (T002, T003)
- All new Pydantic types use `ConfigDict(frozen=True, extra="allow")` for response models
- All new Pydantic types use camelCase alias where API uses camelCase field names
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
