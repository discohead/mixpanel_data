# Tasks: Operational Tooling — Alerts, Annotations, and Webhooks

**Input**: Design documents from `/specs/026-operational-tooling/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: Tests are included per project CLAUDE.md requirements (TDD, 90% coverage).

**Organization**: Tasks are grouped by user story. Each story implements a complete vertical slice (types → API client → workspace → CLI → tests) and is independently testable.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Export new types and register CLI command groups — shared scaffolding that all three domains need.

- [x] T001 Add public re-exports for all new alert, annotation, and webhook types in `src/mixpanel_data/__init__.py`
- [x] T002 Register `alerts_app`, `annotations_app`, and `webhooks_app` command groups in `src/mixpanel_data/cli/main.py`

---

## Phase 2: User Story 2 — Manage Timeline Annotations (Priority: P2, implemented first as simplest)

**Goal**: Full CRUD for timeline annotations and annotation tags (7 operations) through library and CLI.

**Independent Test**: Create a tag, create an annotation with that tag, list by date range, update, delete. All verifiable independently.

### Tests for User Story 2

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [x] T003 [P] [US2] Write Pydantic model tests for Annotation, AnnotationUser, AnnotationTag, CreateAnnotationParams, UpdateAnnotationParams, CreateAnnotationTagParams in `tests/test_types_annotations.py`
- [x] T004 [P] [US2] Write API client tests for list_annotations, create_annotation, get_annotation, update_annotation, delete_annotation, list_annotation_tags, create_annotation_tag using respx in `tests/test_api_client_annotations.py`
- [x] T005 [P] [US2] Write workspace method tests for all 7 annotation operations in `tests/test_workspace_annotations.py`
- [x] T006 [P] [US2] Write CLI integration tests for all 7 annotation subcommands (including nested tags) in `tests/integration/cli/test_annotation_commands.py`

### Implementation for User Story 2

- [x] T007 [P] [US2] Add Annotation, AnnotationUser, AnnotationTag response models and CreateAnnotationParams, UpdateAnnotationParams, CreateAnnotationTagParams request models in `src/mixpanel_data/types.py`
- [x] T008 [US2] Add list_annotations, create_annotation, get_annotation, update_annotation, delete_annotation, list_annotation_tags, create_annotation_tag methods to `src/mixpanel_data/_internal/api_client.py` (note: list uses camelCase params `fromDate`/`toDate`)
- [x] T009 [US2] Add list_annotations, create_annotation, get_annotation, update_annotation, delete_annotation, list_annotation_tags, create_annotation_tag methods to `src/mixpanel_data/workspace.py`
- [x] T010 [US2] Create `src/mixpanel_data/cli/commands/annotations.py` with list, create, get, update, delete commands plus nested `tags` sub-app with list and create subcommands

**Checkpoint**: Annotations fully functional — `mp annotations list`, `mp annotations create`, `mp annotations tags list` all work. Tests pass.

---

## Phase 3: User Story 3 — Manage Project Webhooks (Priority: P3, implemented second)

**Goal**: Full CRUD for project webhooks plus connectivity testing (5 operations) through library and CLI.

**Independent Test**: Create a webhook, test connectivity, update config, delete. All verifiable independently.

### Tests for User Story 3

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [x] T011 [P] [US3] Write Pydantic model tests for ProjectWebhook, WebhookMutationResult, WebhookTestResult, WebhookAuthType, CreateWebhookParams, UpdateWebhookParams, WebhookTestParams in `tests/test_types_webhooks.py`
- [x] T012 [P] [US3] Write API client tests for list_webhooks, create_webhook, update_webhook, delete_webhook, test_webhook using respx in `tests/test_api_client_webhooks.py`
- [x] T013 [P] [US3] Write workspace method tests for all 5 webhook operations in `tests/test_workspace_webhooks.py`
- [x] T014 [P] [US3] Write CLI integration tests for all 5 webhook subcommands in `tests/integration/cli/test_webhook_commands.py`

### Implementation for User Story 3

- [x] T015 [P] [US3] Add ProjectWebhook, WebhookMutationResult, WebhookTestResult response models, WebhookAuthType enum, and CreateWebhookParams, UpdateWebhookParams, WebhookTestParams request models in `src/mixpanel_data/types.py`
- [x] T016 [US3] Add list_webhooks, create_webhook, update_webhook, delete_webhook, test_webhook methods to `src/mixpanel_data/_internal/api_client.py` (note: webhook IDs are strings, create/update return WebhookMutationResult not full entity)
- [x] T017 [US3] Add list_webhooks, create_webhook, update_webhook, delete_webhook, test_webhook methods to `src/mixpanel_data/workspace.py`
- [x] T018 [US3] Create `src/mixpanel_data/cli/commands/webhooks.py` with list, create, update, delete, test subcommands

**Checkpoint**: Webhooks fully functional — `mp webhooks list`, `mp webhooks test --url ...` all work. Tests pass.

---

## Phase 4: User Story 1 — Manage Custom Alerts (Priority: P1, implemented last as most complex)

**Goal**: Full CRUD for custom alerts plus history, testing, screenshots, validation, bulk operations, and count (11 operations) through library and CLI.

**Independent Test**: Create an alert linked to a bookmark, list, get history, test config, get count, delete. All verifiable independently.

### Tests for User Story 1

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [x] T019 [P] [US1] Write Pydantic model tests for CustomAlert, AlertBookmark, AlertCreator, AlertWorkspace, AlertProject, AlertCount, AlertHistoryResponse, AlertHistoryPagination, AlertScreenshotResponse, ValidateAlertsForBookmarkResponse, AlertValidation, AlertFrequencyPreset, CreateAlertParams, UpdateAlertParams, ValidateAlertsForBookmarkParams in `tests/test_types_alerts.py`
- [x] T020 [P] [US1] Write API client tests for all 11 alert methods (list, create, get, update, delete, bulk_delete, get_count, get_history, test, screenshot_url, validate_for_bookmark) using respx in `tests/test_api_client_alerts.py`
- [x] T021 [P] [US1] Write workspace method tests for all 11 alert operations in `tests/test_workspace_alerts.py`
- [x] T022 [P] [US1] Write CLI integration tests for all 11 alert subcommands in `tests/integration/cli/test_alert_commands.py`

### Implementation for User Story 1

- [x] T023 [P] [US1] Add all alert response models (CustomAlert, AlertBookmark, AlertCreator, AlertWorkspace, AlertProject, AlertCount, AlertHistoryResponse, AlertHistoryPagination, AlertScreenshotResponse, ValidateAlertsForBookmarkResponse, AlertValidation), request models (CreateAlertParams, UpdateAlertParams, ValidateAlertsForBookmarkParams), and AlertFrequencyPreset enum in `src/mixpanel_data/types.py`
- [x] T024 [US1] Add all 11 alert API client methods to `src/mixpanel_data/_internal/api_client.py` (list_alerts, create_alert, get_alert, update_alert, delete_alert, bulk_delete_alerts, get_alert_count, get_alert_history, test_alert, get_alert_screenshot_url, validate_alerts_for_bookmark)
- [x] T025 [US1] Add all 11 alert workspace methods to `src/mixpanel_data/workspace.py` (list_alerts, create_alert, get_alert, update_alert, delete_alert, bulk_delete_alerts, get_alert_count, get_alert_history, test_alert, get_alert_screenshot_url, validate_alerts_for_bookmark)
- [x] T026 [US1] Create `src/mixpanel_data/cli/commands/alerts.py` with all 11 subcommands (list, create, get, update, delete, bulk-delete, count, history, test, screenshot, validate)

**Checkpoint**: Alerts fully functional — all 11 operations work via library and CLI. Tests pass.

---

## Phase 5: Polish & Cross-Cutting Concerns

**Purpose**: Quality gates, integration verification, and documentation consistency.

- [x] T027 Run `just check` (lint + typecheck + test) and fix any failures across all modified files
- [x] T028 Run `just test-cov` and verify 90%+ coverage for all new code; add missing test cases if needed
- [x] T029 Verify all 23 CLI commands produce correct output in all 5 formats (json, jsonl, table, csv, plain) and support `--jq` filtering
- [x] T030 Update `src/mixpanel_data/__init__.py` `__all__` exports to include all new public types
- [x] T031 Add alerts, annotations, and webhooks operational tooling reference to context documentation in `context/CLAUDE.md` if needed

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — can start immediately
- **Annotations (Phase 2)**: Depends on Setup (Phase 1) for CLI registration
- **Webhooks (Phase 3)**: Depends on Setup (Phase 1) for CLI registration; independent of Annotations
- **Alerts (Phase 4)**: Depends on Setup (Phase 1) for CLI registration; independent of Annotations and Webhooks
- **Polish (Phase 5)**: Depends on all user stories being complete

### User Story Dependencies

- **User Story 2 (Annotations)**: Can start after Setup — no dependencies on other stories
- **User Story 3 (Webhooks)**: Can start after Setup — no dependencies on other stories
- **User Story 1 (Alerts)**: Can start after Setup — no dependencies on other stories
- All three stories are **fully independent** and can run in parallel

### Within Each User Story

1. Tests MUST be written and FAIL before implementation (TDD)
2. Types before API client (API client references types)
3. API client before Workspace (Workspace calls API client)
4. Workspace before CLI (CLI calls Workspace)
5. All tests marked [P] within a story can run in parallel

### Parallel Opportunities

- All test tasks within a story (T003-T006, T011-T014, T019-T022) can run in parallel
- Type tasks across stories (T007, T015, T023) can run in parallel (different sections of same file — coordinate with merge)
- All three user stories can run in parallel after Setup completes
- Polish tasks T027-T031 are sequential (each may fix issues affecting the next)

---

## Parallel Example: User Story 2 (Annotations)

```bash
# Launch all tests in parallel (write first, all FAIL):
Agent: "Write annotation Pydantic model tests in tests/test_types_annotations.py"
Agent: "Write annotation API client tests in tests/test_api_client_annotations.py"
Agent: "Write annotation workspace tests in tests/test_workspace_annotations.py"
Agent: "Write annotation CLI tests in tests/integration/cli/test_annotation_commands.py"

# Then implement sequentially (each makes more tests pass):
# T007: types.py → type tests pass
# T008: api_client.py → API client tests pass
# T009: workspace.py → workspace tests pass
# T010: annotations.py CLI → CLI tests pass
```

---

## Implementation Strategy

### MVP First (Annotations Only)

1. Complete Phase 1: Setup (T001-T002)
2. Complete Phase 2: Annotations (T003-T010)
3. **STOP and VALIDATE**: `mp annotations list`, `mp annotations create`, `mp annotations tags list` all work
4. Run `just check` — all tests pass

### Incremental Delivery

1. Setup → Foundation ready
2. Add Annotations → Test independently → Working (simplest domain proves pattern)
3. Add Webhooks → Test independently → Working (introduces string IDs, mutation results)
4. Add Alerts → Test independently → Working (most complex — history, pagination, validation)
5. Polish → Full quality gates pass

### Parallel Team Strategy

With multiple developers:

1. All complete Setup together (2 tasks)
2. Once Setup is done:
   - Developer A: Annotations (Phase 2)
   - Developer B: Webhooks (Phase 3)
   - Developer C: Alerts (Phase 4)
3. All stories complete and integrate independently
4. Everyone contributes to Polish (Phase 5)

---

## Notes

- Implementation order differs from spec priority: P2 → P3 → P1 (simplest first to establish patterns before tackling the most complex domain)
- All types go into the existing `src/mixpanel_data/types.py` file — coordinate if implementing stories in parallel
- Annotation list API uses camelCase query params (`fromDate`, `toDate`) — must translate from snake_case in API client
- Webhook IDs are strings (UUIDs), unlike alert/annotation IDs which are ints
- Webhook create/update returns `WebhookMutationResult` (id + name only), not the full `ProjectWebhook`
- Alert test endpoint reuses `CreateAlertParams` and returns opaque `dict[str, Any]`
- Annotation tags CLI uses nested Typer sub-app: `mp annotations tags list` / `mp annotations tags create`
- Commit after each task or logical group completes
