# Tasks: Mixpanel API Client

**Input**: Design documents from `/specs/002-api-client/`
**Prerequisites**: plan.md, spec.md, data-model.md, contracts/api_client.py, research.md

**Tests**: Included per SC-006 requirement (90%+ test coverage)

**Organization**: Tasks grouped by user story for independent implementation and testing

## Format: `[ID] [P?] [Story?] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1-US8)
- File paths are relative to repository root

---

## Phase 1: Setup

**Purpose**: Project initialization - verify dependencies and create file structure

- [X] T001 Verify httpx and pydantic dependencies in pyproject.toml
- [X] T002 [P] Create empty src/mixpanel_data/_internal/api_client.py with module docstring
- [X] T003 [P] Create tests/unit/test_api_client.py with module docstring

---

## Phase 2: Foundational (Core Client Infrastructure)

**Purpose**: Core client class structure that ALL user stories depend on

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [X] T004 Define ENDPOINTS dict with regional URL routing in src/mixpanel_data/_internal/api_client.py
- [X] T005 Implement MixpanelAPIClient.__init__() with Credentials injection in src/mixpanel_data/_internal/api_client.py
- [X] T006 Implement _get_auth_header() for HTTP Basic auth in src/mixpanel_data/_internal/api_client.py
- [X] T007 Implement _build_url() for regional endpoint routing in src/mixpanel_data/_internal/api_client.py
- [X] T008 Implement close(), __enter__(), __exit__() lifecycle methods in src/mixpanel_data/_internal/api_client.py
- [X] T009 Implement _handle_response() for error mapping in src/mixpanel_data/_internal/api_client.py
- [X] T010 Add mock client fixtures to tests/conftest.py for httpx.MockTransport

**Checkpoint**: Core client structure ready - user story implementation can begin

---

## Phase 3: User Story 1 - Make Authenticated API Requests (Priority: P1) 🎯 MVP

**Goal**: Enable authenticated requests to Mixpanel APIs with proper Basic auth and regional routing

**Independent Test**: Make a simple API request and verify auth headers are present

### Tests for User Story 1

- [X] T011 [P] [US1] Test auth header generation in tests/unit/test_api_client.py
- [X] T012 [P] [US1] Test regional endpoint routing for US/EU/IN in tests/unit/test_api_client.py
- [X] T013 [P] [US1] Test project_id included in query params in tests/unit/test_api_client.py
- [X] T014 [P] [US1] Test AuthenticationError on 401 response in tests/unit/test_api_client.py
- [X] T015 [P] [US1] Test credentials not in error messages in tests/unit/test_api_client.py

### Implementation for User Story 1

- [X] T016 [US1] Implement _request() method with auth headers in src/mixpanel_data/_internal/api_client.py
- [X] T017 [US1] Add project_id to all request params in src/mixpanel_data/_internal/api_client.py
- [X] T018 [US1] Map HTTP 401 to AuthenticationError in src/mixpanel_data/_internal/api_client.py
- [X] T019 [US1] Ensure credentials redacted in all exception messages in src/mixpanel_data/_internal/api_client.py

**Checkpoint**: Client can make authenticated requests to any Mixpanel endpoint

---

## Phase 4: User Story 2 - Handle Rate Limiting Gracefully (Priority: P1)

**Goal**: Automatic retry with exponential backoff on 429 responses

**Independent Test**: Simulate 429 responses and verify retry behavior

### Tests for User Story 2

- [X] T020 [P] [US2] Test retry on 429 with Retry-After header in tests/unit/test_api_client.py
- [X] T021 [P] [US2] Test exponential backoff without Retry-After in tests/unit/test_api_client.py
- [X] T022 [P] [US2] Test RateLimitError after max retries in tests/unit/test_api_client.py
- [X] T023 [P] [US2] Test successful response after retry in tests/unit/test_api_client.py

### Implementation for User Story 2

- [X] T024 [US2] Implement _calculate_backoff() with jitter in src/mixpanel_data/_internal/api_client.py
- [X] T025 [US2] Implement retry loop in _request() method in src/mixpanel_data/_internal/api_client.py
- [X] T026 [US2] Parse Retry-After header when present in src/mixpanel_data/_internal/api_client.py
- [X] T027 [US2] Raise RateLimitError with retry_after when retries exhausted in src/mixpanel_data/_internal/api_client.py

**Checkpoint**: All requests automatically retry on rate limits

---

## Phase 5: User Story 3 - Stream Large Event Exports (Priority: P1)

**Goal**: Stream events as iterator without memory exhaustion

**Independent Test**: Export events for a date range and verify iterator behavior

### Tests for User Story 3

- [X] T028 [P] [US3] Test export_events returns iterator in tests/unit/test_api_client.py
- [X] T029 [P] [US3] Test JSONL parsing line by line in tests/unit/test_api_client.py
- [X] T030 [P] [US3] Test on_batch callback invocation in tests/unit/test_api_client.py
- [X] T031 [P] [US3] Test event name filtering in tests/unit/test_api_client.py
- [X] T032 [P] [US3] Test malformed JSON skipped with warning in tests/unit/test_api_client.py

### Implementation for User Story 3

- [X] T033 [US3] Implement export_events() with streaming in src/mixpanel_data/_internal/api_client.py
- [X] T034 [US3] Parse JSONL with iter_lines() in src/mixpanel_data/_internal/api_client.py
- [X] T035 [US3] Add on_batch callback support in src/mixpanel_data/_internal/api_client.py
- [X] T036 [US3] Handle malformed JSON lines gracefully in src/mixpanel_data/_internal/api_client.py
- [X] T037 [US3] Add gzip decompression support in src/mixpanel_data/_internal/api_client.py

**Checkpoint**: Can export millions of events without memory exhaustion

---

## Phase 6: User Story 4 - Query Segmentation Data (Priority: P2)

**Goal**: Run segmentation queries and return raw API response

**Independent Test**: Run segmentation query and verify response structure

### Tests for User Story 4

- [X] T038 [P] [US4] Test segmentation() basic call in tests/unit/test_api_client.py
- [X] T039 [P] [US4] Test segmentation with "on" parameter in tests/unit/test_api_client.py
- [X] T040 [P] [US4] Test segmentation with "where" filter in tests/unit/test_api_client.py

### Implementation for User Story 4

- [X] T041 [US4] Implement segmentation() method in src/mixpanel_data/_internal/api_client.py
- [X] T042 [US4] Add all query parameters (unit, type, on, where) in src/mixpanel_data/_internal/api_client.py

**Checkpoint**: Segmentation queries work with all parameters

---

## Phase 7: User Story 5 - Discover Available Events and Properties (Priority: P2)

**Goal**: List events, properties, and property values for project exploration

**Independent Test**: List events and verify response contains event names

### Tests for User Story 5

- [X] T043 [P] [US5] Test get_events() returns list in tests/unit/test_api_client.py
- [X] T044 [P] [US5] Test get_event_properties() in tests/unit/test_api_client.py
- [X] T045 [P] [US5] Test get_property_values() with limit in tests/unit/test_api_client.py

### Implementation for User Story 5

- [X] T046 [US5] Implement get_events() in src/mixpanel_data/_internal/api_client.py
- [X] T047 [US5] Implement get_event_properties() in src/mixpanel_data/_internal/api_client.py
- [X] T048 [US5] Implement get_property_values() in src/mixpanel_data/_internal/api_client.py

**Checkpoint**: Can explore project data schema

---

## Phase 8: User Story 6 - Export User Profiles (Priority: P2)

**Goal**: Export profiles with automatic pagination as iterator

**Independent Test**: Export profiles and verify pagination handling

### Tests for User Story 6

- [X] T049 [P] [US6] Test export_profiles() returns iterator in tests/unit/test_api_client.py
- [X] T050 [P] [US6] Test pagination with session_id in tests/unit/test_api_client.py
- [X] T051 [P] [US6] Test "where" filter for profiles in tests/unit/test_api_client.py

### Implementation for User Story 6

- [X] T052 [US6] Implement export_profiles() with pagination in src/mixpanel_data/_internal/api_client.py
- [X] T053 [US6] Handle session_id pagination loop in src/mixpanel_data/_internal/api_client.py
- [X] T054 [US6] Add on_batch callback for profile export in src/mixpanel_data/_internal/api_client.py

**Checkpoint**: Can export all profiles with automatic pagination

---

## Phase 9: User Story 7 - Run Funnel and Retention Queries (Priority: P3)

**Goal**: Run funnel and retention analysis queries

**Independent Test**: Run funnel/retention query and verify response structure

### Tests for User Story 7

- [X] T055 [P] [US7] Test funnel() method in tests/unit/test_api_client.py
- [X] T056 [P] [US7] Test retention() method in tests/unit/test_api_client.py

### Implementation for User Story 7

- [X] T057 [US7] Implement funnel() method in src/mixpanel_data/_internal/api_client.py
- [X] T058 [US7] Implement retention() method in src/mixpanel_data/_internal/api_client.py

**Checkpoint**: Funnel and retention analysis working

---

## Phase 10: User Story 8 - Execute Custom JQL Queries (Priority: P3)

**Goal**: Execute JQL scripts with parameters

**Independent Test**: Execute JQL script and verify results

### Tests for User Story 8

- [X] T059 [P] [US8] Test jql() basic execution in tests/unit/test_api_client.py
- [X] T060 [P] [US8] Test jql() with params in tests/unit/test_api_client.py

### Implementation for User Story 8

- [X] T061 [US8] Implement jql() method in src/mixpanel_data/_internal/api_client.py
- [X] T062 [US8] Pass params to JQL script in src/mixpanel_data/_internal/api_client.py

**Checkpoint**: JQL queries working with parameters

---

## Phase 11: Polish & Cross-Cutting Concerns

**Purpose**: Final quality improvements

- [X] T063 [P] Add type hints to all public methods in src/mixpanel_data/_internal/api_client.py
- [X] T064 [P] Add docstrings (Google style) to all public methods in src/mixpanel_data/_internal/api_client.py
- [X] T065 Run ruff check on src/mixpanel_data/_internal/api_client.py
- [X] T066 Run mypy --strict on src/mixpanel_data/_internal/api_client.py
- [X] T067 Run pytest with coverage report
- [X] T068 Validate quickstart.md examples work
- [X] T069 Export MixpanelAPIClient from src/mixpanel_data/_internal/__init__.py

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: No dependencies - start immediately
- **Phase 2 (Foundational)**: Depends on Phase 1 - **BLOCKS all user stories**
- **Phases 3-10 (User Stories)**: All depend on Phase 2 completion
  - P1 stories (US1-US3): Should complete first for MVP
  - P2 stories (US4-US6): Can start after P1 or in parallel
  - P3 stories (US7-US8): Can start after P2 or in parallel
- **Phase 11 (Polish)**: Depends on all user stories complete

### User Story Dependencies

| Story | Depends On | Can Run In Parallel With |
|-------|------------|-------------------------|
| US1 (Auth) | Phase 2 only | - |
| US2 (Rate Limit) | US1 (uses _request) | - |
| US3 (Export) | US1, US2 | - |
| US4 (Segmentation) | US1, US2 | US5, US6 |
| US5 (Discovery) | US1, US2 | US4, US6 |
| US6 (Profiles) | US1, US2 | US4, US5 |
| US7 (Funnel/Retention) | US1, US2 | US8 |
| US8 (JQL) | US1, US2 | US7 |

### Within Each User Story

1. Write tests FIRST (all [P] tests can run in parallel)
2. Verify tests FAIL
3. Implement code to make tests pass
4. Verify story works independently

---

## Parallel Execution Examples

### Phase 2 (Foundational) - All in parallel:
```bash
T004 "Define ENDPOINTS dict..."
T005 "Implement __init__()..."
T006 "Implement _get_auth_header()..."
T007 "Implement _build_url()..."
T008 "Implement lifecycle methods..."
T009 "Implement _handle_response()..."
T010 "Add mock client fixtures..."
```

### User Story 1 Tests - All in parallel:
```bash
T011 "Test auth header generation..."
T012 "Test regional endpoint routing..."
T013 "Test project_id in query params..."
T014 "Test AuthenticationError on 401..."
T015 "Test credentials not in errors..."
```

### P2 Stories (US4, US5, US6) - All in parallel after US1-3:
```bash
# Developer A: US4 (Segmentation)
T038-T042

# Developer B: US5 (Discovery)
T043-T048

# Developer C: US6 (Profiles)
T049-T054
```

---

## Implementation Strategy

### MVP First (User Stories 1-3 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (**CRITICAL GATE**)
3. Complete Phase 3: US1 - Authenticated Requests
4. Complete Phase 4: US2 - Rate Limiting
5. Complete Phase 5: US3 - Event Export
6. **STOP and VALIDATE**: All P1 stories working independently
7. Run tests: `pytest tests/unit/test_api_client.py -v`

### Incremental Delivery

| Checkpoint | What's Working |
|------------|---------------|
| After US1 | Auth + regional routing |
| After US2 | + Rate limit handling |
| After US3 | + Event streaming (MVP!) |
| After US4 | + Segmentation queries |
| After US5 | + Data discovery |
| After US6 | + Profile export |
| After US7 | + Funnel/retention |
| After US8 | + JQL (full feature) |

---

## Summary

| Phase | Task Count | Parallel Opportunities |
|-------|-----------|----------------------|
| Setup | 3 | 2 |
| Foundational | 7 | 6 |
| US1 (P1) | 9 | 5 tests |
| US2 (P1) | 8 | 4 tests |
| US3 (P1) | 10 | 5 tests |
| US4 (P2) | 5 | 3 tests |
| US5 (P2) | 6 | 3 tests |
| US6 (P2) | 6 | 3 tests |
| US7 (P3) | 4 | 2 tests |
| US8 (P3) | 4 | 2 tests |
| Polish | 7 | 2 |
| **Total** | **69** | **37** |

**MVP Scope**: Phases 1-5 (US1-US3) = 37 tasks
**Full Feature**: All phases = 69 tasks

---

## Notes

- All tests use httpx.MockTransport for deterministic behavior
- Credentials from Phase 001 (Credentials class) are injected
- Exceptions from Phase 001 are reused (no new exception types)
- Client is in _internal/ - not exported publicly (for now)
- Each user story is independently testable per spec requirements
