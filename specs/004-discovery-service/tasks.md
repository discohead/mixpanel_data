# Tasks: Discovery Service

**Input**: Design documents from `/specs/004-discovery-service/`
**Prerequisites**: plan.md (required), spec.md (required), research.md, data-model.md, contracts/

**Tests**: Unit tests included per constitution quality gates (pytest with mocked API client).

**Organization**: Tasks grouped by user story to enable independent implementation and testing.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3, US4)
- Include exact file paths in descriptions

## Path Conventions

- **Single project**: `src/mixpanel_data/_internal/services/`, `tests/unit/`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Create services directory structure

- [X] T001 Create services package directory at src/mixpanel_data/_internal/services/
- [X] T002 Create package marker at src/mixpanel_data/_internal/services/__init__.py

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core DiscoveryService class with cache infrastructure

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [X] T003 Create DiscoveryService class skeleton in src/mixpanel_data/_internal/services/discovery.py with:
  - Module docstring and imports
  - Class definition with `__init__(self, api_client: MixpanelAPIClient)`
  - Private `_cache: dict[tuple, list[str]]` attribute
  - Private `_api_client` attribute
  - Module-level logger: `_logger = logging.getLogger(__name__)`
- [X] T004 Create test file skeleton at tests/unit/test_discovery.py with:
  - Imports for pytest, httpx.MockTransport, and discovery service
  - Fixtures for mock API client (reuse pattern from tests/unit/test_api_client.py)
  - TestDiscoveryService class placeholder

**Checkpoint**: Foundation ready - user story implementation can now begin

---

## Phase 3: User Story 1 - Discover Available Events (Priority: P1) 🎯 MVP

**Goal**: List all event names in a Mixpanel project with caching

**Independent Test**: Request list of events, verify complete alphabetically-sorted list returned; verify caching on second call

### Tests for User Story 1

- [X] T005 [P] [US1] Unit test for list_events() returns sorted list in tests/unit/test_discovery.py
- [X] T006 [P] [US1] Unit test for list_events() caching behavior in tests/unit/test_discovery.py
- [X] T007 [P] [US1] Unit test for list_events() with authentication error in tests/unit/test_discovery.py
- [X] T008 [P] [US1] Unit test for list_events() with empty result in tests/unit/test_discovery.py

### Implementation for User Story 1

- [X] T009 [US1] Implement list_events() method in src/mixpanel_data/_internal/services/discovery.py:
  - Check cache for key `("list_events",)`
  - If miss: call `self._api_client.get_events()`
  - Sort result alphabetically with `sorted()`
  - Store in cache and return
- [X] T010 [US1] Run tests for User Story 1 and verify all pass

**Checkpoint**: User Story 1 fully functional - can list all events with caching

---

## Phase 4: User Story 2 - Explore Event Properties (Priority: P1)

**Goal**: List all properties for a specific event with caching

**Independent Test**: Provide valid event name, verify sorted properties returned; verify error on invalid event

### Tests for User Story 2

- [X] T011 [P] [US2] Unit test for list_properties() returns sorted list in tests/unit/test_discovery.py
- [X] T012 [P] [US2] Unit test for list_properties() caching per event in tests/unit/test_discovery.py
- [X] T013 [P] [US2] Unit test for list_properties() with QueryError on invalid event in tests/unit/test_discovery.py
- [X] T014 [P] [US2] Unit test for list_properties() with empty result in tests/unit/test_discovery.py

### Implementation for User Story 2

- [X] T015 [US2] Implement list_properties(event: str) method in src/mixpanel_data/_internal/services/discovery.py:
  - Check cache for key `("list_properties", event)`
  - If miss: call `self._api_client.get_event_properties(event)`
  - Sort result alphabetically with `sorted()`
  - Store in cache and return
- [X] T016 [US2] Run tests for User Story 2 and verify all pass

**Checkpoint**: User Stories 1 AND 2 both work independently

---

## Phase 5: User Story 3 - Sample Property Values (Priority: P2)

**Goal**: Get sample values for a property with optional event scope and limit

**Independent Test**: Provide property name, verify values returned; verify scoping to event; verify limit respected

### Tests for User Story 3

- [X] T017 [P] [US3] Unit test for list_property_values() basic call in tests/unit/test_discovery.py
- [X] T018 [P] [US3] Unit test for list_property_values() with event scope in tests/unit/test_discovery.py
- [X] T019 [P] [US3] Unit test for list_property_values() with custom limit in tests/unit/test_discovery.py
- [X] T020 [P] [US3] Unit test for list_property_values() caching per (property, event, limit) in tests/unit/test_discovery.py
- [X] T021 [P] [US3] Unit test for list_property_values() with empty result in tests/unit/test_discovery.py

### Implementation for User Story 3

- [X] T022 [US3] Implement list_property_values(property_name: str, *, event: str | None = None, limit: int = 100) method in src/mixpanel_data/_internal/services/discovery.py:
  - Check cache for key `("list_property_values", property_name, event, limit)`
  - If miss: call `self._api_client.get_property_values(property_name, event=event, limit=limit)`
  - Return result (no sorting per research.md - values are not alphabetically ordered)
  - Store in cache and return
- [X] T023 [US3] Run tests for User Story 3 and verify all pass

**Checkpoint**: User Stories 1, 2, AND 3 all work independently

---

## Phase 6: User Story 4 - Clear Discovery Cache (Priority: P3)

**Goal**: Manually clear cached discovery results

**Independent Test**: Populate cache, clear it, verify next request fetches fresh data

### Tests for User Story 4

- [X] T024 [P] [US4] Unit test for clear_cache() clears all cached results in tests/unit/test_discovery.py
- [X] T025 [P] [US4] Unit test for clear_cache() on empty cache does not error in tests/unit/test_discovery.py
- [X] T026 [P] [US4] Unit test for clear_cache() causes next request to hit API in tests/unit/test_discovery.py

### Implementation for User Story 4

- [X] T027 [US4] Implement clear_cache() method in src/mixpanel_data/_internal/services/discovery.py:
  - Set `self._cache = {}`
- [X] T028 [US4] Run tests for User Story 4 and verify all pass

**Checkpoint**: All user stories now independently functional

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Quality gates and documentation

- [X] T029 [P] Add module docstring and class docstring to src/mixpanel_data/_internal/services/discovery.py per Google style
- [X] T030 [P] Add method docstrings to all public methods (list_events, list_properties, list_property_values, clear_cache)
- [X] T031 Run mypy --strict on src/mixpanel_data/_internal/services/discovery.py and fix any type errors
- [X] T032 Run ruff check on src/mixpanel_data/_internal/services/discovery.py and fix any linting issues
- [X] T033 Run full test suite: pytest tests/unit/test_discovery.py -v
- [X] T034 Validate against quickstart.md examples (manual verification)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - BLOCKS all user stories
- **User Stories (Phase 3-6)**: All depend on Foundational phase completion
  - US1 and US2 can proceed in parallel (both P1, different methods)
  - US3 can start after Foundational (independent of US1/US2)
  - US4 can start after Foundational (independent of all others)
- **Polish (Phase 7)**: Depends on all user stories being complete

### User Story Dependencies

- **User Story 1 (P1)**: Can start after Foundational - No dependencies on other stories
- **User Story 2 (P1)**: Can start after Foundational - No dependencies on other stories (can parallel with US1)
- **User Story 3 (P2)**: Can start after Foundational - No dependencies on other stories
- **User Story 4 (P3)**: Can start after Foundational - No dependencies on other stories

### Within Each User Story

- Tests written first (TDD approach)
- Implementation follows tests
- Verify tests pass before marking story complete

### Parallel Opportunities

Within each user story phase, all test tasks marked [P] can run in parallel:
- US1: T005, T006, T007, T008 can run in parallel
- US2: T011, T012, T013, T014 can run in parallel
- US3: T017, T018, T019, T020, T021 can run in parallel
- US4: T024, T025, T026 can run in parallel

Different user stories can be worked on in parallel by different developers after Foundational completes.

---

## Parallel Example: All US1 Tests

```bash
# Launch all tests for User Story 1 together:
Task: "Unit test for list_events() returns sorted list in tests/unit/test_discovery.py"
Task: "Unit test for list_events() caching behavior in tests/unit/test_discovery.py"
Task: "Unit test for list_events() with authentication error in tests/unit/test_discovery.py"
Task: "Unit test for list_events() with empty result in tests/unit/test_discovery.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (T001-T002)
2. Complete Phase 2: Foundational (T003-T004)
3. Complete Phase 3: User Story 1 (T005-T010)
4. **STOP and VALIDATE**: Test list_events() independently
5. Can deploy/demo with basic event discovery

### Incremental Delivery

1. Setup + Foundational → Foundation ready
2. Add User Story 1 → Test → Deploy (MVP: event listing)
3. Add User Story 2 → Test → Deploy (property listing)
4. Add User Story 3 → Test → Deploy (value sampling)
5. Add User Story 4 → Test → Deploy (cache management)
6. Polish → Final release

### Single Developer Strategy (Recommended)

Since this is a single service class, work sequentially by priority:
1. Setup + Foundational
2. US1 (P1) - Complete with tests
3. US2 (P1) - Complete with tests
4. US3 (P2) - Complete with tests
5. US4 (P3) - Complete with tests
6. Polish

---

## Notes

- All user story methods are in the same file (discovery.py) but can be implemented independently
- Cache key format: tuple of (method_name, *args) for unique identification
- Sorting applies to events and properties but NOT to property values
- Error handling is pass-through from API client (no wrapping needed)
- Default limit for property values is 100 (per spec A-003)
