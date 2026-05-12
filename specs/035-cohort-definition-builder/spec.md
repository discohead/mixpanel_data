# Feature Specification: Cohort Definition Builder

**Feature Branch**: `035-cohort-definition-builder`  
**Created**: 2026-04-07  
**Status**: Draft  
**Input**: User description: "Phase 0: Cohort Definition Builder — Add CohortCriteria and CohortDefinition frozen dataclasses for constructing valid Mixpanel cohort definition JSON. Foundation for cohort filter, breakdown, and metric query capabilities."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Define a Behavioral Cohort Criterion (Priority: P1)

A developer or LLM agent needs to define a cohort based on event behavior — for example, "users who purchased at least 3 times in the last 30 days." They construct this using a typed class method rather than manually building raw JSON dicts.

**Why this priority**: Behavioral criteria (event frequency within a time window) are the most common cohort definition pattern in Mixpanel. Without this, the builder has no core capability.

**Independent Test**: Can be fully tested by constructing a `CohortCriteria.did_event("Purchase", at_least=3, within_days=30)` and verifying the internal state is correctly set. Delivers value as a validated building block.

**Acceptance Scenarios**:

1. **Given** a developer wants to define a behavioral criterion, **When** they call `CohortCriteria.did_event("Purchase", at_least=3, within_days=30)`, **Then** a frozen `CohortCriteria` is returned with a valid selector node referencing a behavior entry, and a behavior dict containing the event count and rolling window.
2. **Given** a developer specifies conflicting frequency params (e.g., both `at_least` and `at_most`), **When** they call `did_event()`, **Then** a `ValueError` is raised immediately with a clear message indicating exactly one frequency param is required.
3. **Given** a developer omits all time constraints, **When** they call `did_event("Purchase", at_least=1)`, **Then** a `ValueError` is raised indicating exactly one time constraint is required.
4. **Given** a developer provides event property filters via `where=`, **When** they call `did_event("Purchase", at_least=1, within_days=30, where=Filter.equals("plan", "premium"))`, **Then** the behavior's event selector includes the filter as an expression tree.

---

### User Story 2 - Compose a Multi-Criteria Cohort Definition (Priority: P1)

A developer needs to combine multiple criteria with boolean logic — for example, "premium users who purchased 3+ times in 30 days" (AND) or "users who signed up recently OR are in the Power Users cohort" (OR). They compose criteria into a `CohortDefinition` and serialize it to valid JSON.

**Why this priority**: Composition is the core value proposition of the builder. Without it, individual criteria are isolated building blocks with no way to produce complete cohort definitions.

**Independent Test**: Can be fully tested by constructing `CohortDefinition.all_of(criterion_a, criterion_b)`, calling `.to_dict()`, and verifying the output dict has valid `selector` and `behaviors` keys with correct structure.

**Acceptance Scenarios**:

1. **Given** a developer has two criteria, **When** they call `CohortDefinition.all_of(criteria_a, criteria_b)`, **Then** a frozen `CohortDefinition` is returned. Calling `.to_dict()` produces `{"selector": {"operator": "and", "children": [...]}, "behaviors": {...}}` with all behavior entries merged and behavior keys globally unique.
2. **Given** a developer uses `any_of()`, **When** the definition is serialized, **Then** the selector tree uses `"operator": "or"`.
3. **Given** nested definitions like `any_of(all_of(A, B), C)`, **When** serialized, **Then** the selector tree correctly nests AND inside OR, and all behavior keys across the tree are unique (no collisions).
4. **Given** zero criteria are provided, **When** constructing a `CohortDefinition`, **Then** a `ValueError` is raised indicating at least one criterion is required.

---

### User Story 3 - Define a Property-Based Cohort Criterion (Priority: P2)

A developer defines a cohort based on user profile properties — for example, "users on the premium plan" or "users whose age is greater than 18."

**Why this priority**: Property criteria are simpler than behavioral criteria (no behavior dict needed) and cover a common use case, but are less complex to implement.

**Independent Test**: Can be fully tested by constructing `CohortCriteria.has_property("plan", "premium")` and verifying the selector node has the correct property, value, operator, and type fields.

**Acceptance Scenarios**:

1. **Given** a developer wants a simple property match, **When** they call `CohortCriteria.has_property("plan", "premium")`, **Then** the returned criterion has a selector node with `property: "user"`, `value: "plan"`, `operator: "=="`, `operand: "premium"`, `type: "string"`.
2. **Given** a developer uses a comparison operator, **When** they call `CohortCriteria.has_property("age", 18, operator="greater_than", property_type="number")`, **Then** the selector node has `operator: ">"`, `operand: 18`, `type: "number"`.
3. **Given** a developer calls `CohortCriteria.property_is_set("email")`, **Then** the selector node uses `operator: "defined"`.
4. **Given** an empty property name is provided, **When** calling `has_property("", "value")`, **Then** a `ValueError` is raised.

---

### User Story 4 - Reference a Saved Cohort in a Definition (Priority: P2)

A developer builds a cohort that references another saved cohort — for example, "users who are in the Enterprise cohort AND purchased recently."

**Why this priority**: Cohort composition (referencing other cohorts) is a powerful feature but depends on the behavioral and property criteria being established first.

**Independent Test**: Can be fully tested by constructing `CohortCriteria.in_cohort(456)` and verifying the selector node references the cohort ID correctly.

**Acceptance Scenarios**:

1. **Given** a developer wants to reference a saved cohort, **When** they call `CohortCriteria.in_cohort(456)`, **Then** the selector node has `property: "cohort"`, `value: 456`, `operator: "in"`.
2. **Given** a developer wants the negation, **When** they call `CohortCriteria.not_in_cohort(456)`, **Then** the selector node has `operator: "not in"`.
3. **Given** an invalid cohort ID (zero or negative), **When** calling `in_cohort(0)`, **Then** a `ValueError` is raised.

---

### User Story 5 - Use Definition with Cohort CRUD (Priority: P2)

A developer creates a saved cohort in Mixpanel using the typed builder instead of hand-crafting JSON, passing `CohortDefinition.to_dict()` as the `definition` parameter to `CreateCohortParams`.

**Why this priority**: Integration with the existing CRUD system validates that the builder produces JSON the API accepts. This is the primary consumption path for Phase 0.

**Independent Test**: Can be fully tested by constructing a `CohortDefinition`, calling `.to_dict()`, passing it to `CreateCohortParams(name="Test", definition=def.to_dict())`, and verifying `model_dump()` produces a valid flattened payload with `selector` and `behaviors` at the top level.

**Acceptance Scenarios**:

1. **Given** a `CohortDefinition` with behavioral and property criteria, **When** its `.to_dict()` output is passed to `CreateCohortParams(definition=...)`, **Then** `model_dump(exclude_none=True)` produces a dict with `name`, `selector`, and `behaviors` keys at the top level (definition is flattened).
2. **Given** a definition with nested boolean logic, **When** serialized and passed to CRUD, **Then** the `selector` tree and `behaviors` dict are structurally valid per Mixpanel's legacy format.

---

### User Story 6 - Convenience Shorthand for "Did Not Do" (Priority: P3)

A developer uses the `did_not_do_event()` shorthand for the common pattern of defining inactive users (event count = 0 within a window).

**Why this priority**: This is syntactic sugar over `did_event(exactly=0)` — useful but not essential.

**Independent Test**: Can be fully tested by verifying `CohortCriteria.did_not_do_event("Login", within_days=30)` produces the same internal state as `CohortCriteria.did_event("Login", exactly=0, within_days=30)`.

**Acceptance Scenarios**:

1. **Given** a developer wants inactive users, **When** they call `CohortCriteria.did_not_do_event("Login", within_days=30)`, **Then** the result is equivalent to `did_event("Login", exactly=0, within_days=30)`.

---

### Edge Cases

- What happens when a developer provides both a rolling window AND absolute dates to `did_event()`? A `ValueError` is raised — exactly one time constraint is required.
- What happens when `from_date` is provided without `to_date`? A `ValueError` is raised — `from_date` requires `to_date`.
- What happens when dates are not in YYYY-MM-DD format? A `ValueError` is raised with a format hint.
- What happens when `did_event()` receives a negative frequency value? A `ValueError` is raised — frequency must be non-negative.
- What happens when an empty event name is passed? A `ValueError` is raised.
- What happens when a `CohortDefinition` contains only non-behavioral criteria? `to_dict()` produces a `behaviors` dict that is empty `{}` — the selector tree stands alone.
- What happens when deeply nested definitions (3+ levels) are serialized? Behavior keys remain globally unique across all nesting levels via re-indexing during `to_dict()`.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST provide a `CohortCriteria` type with class methods for constructing behavioral criteria (`did_event`, `did_not_do_event`), property criteria (`has_property`, `property_is_set`, `property_is_not_set`), and cohort reference criteria (`in_cohort`, `not_in_cohort`).
- **FR-002**: System MUST provide a `CohortDefinition` type that combines one or more `CohortCriteria` (or nested `CohortDefinition`) with AND or OR logic via `all_of()` and `any_of()` class methods.
- **FR-003**: `CohortDefinition.to_dict()` MUST produce a dict with `selector` (expression tree) and `behaviors` (behavior dictionary) keys in Mixpanel's legacy cohort definition format.
- **FR-004**: Behavioral criteria MUST accept exactly one frequency parameter (`at_least`, `at_most`, or `exactly`) and exactly one time constraint (`within_days`, `within_weeks`, `within_months`, or `from_date`+`to_date`).
- **FR-005**: Behavioral criteria MUST support event property filters via an optional `where` parameter that accepts `Filter` or `list[Filter]` objects from the existing query system.
- **FR-006**: Property criteria MUST support operators: `equals`, `not_equals`, `contains`, `not_contains`, `greater_than`, `less_than`, `is_set`, `is_not_set`, mapping to the corresponding selector tree operators.
- **FR-007**: Cohort reference criteria MUST accept a positive integer cohort ID and produce `in`/`not in` selector nodes.
- **FR-008**: Both `CohortCriteria` and `CohortDefinition` MUST be frozen (immutable after construction).
- **FR-009**: All validation MUST happen at construction time (fail-fast), raising `ValueError` with clear messages per rules CD1-CD10.
- **FR-010**: `CohortDefinition.to_dict()` MUST produce globally unique behavior keys (`bhvr_0`, `bhvr_1`, ...) across the entire definition tree, including nested sub-definitions.
- **FR-011**: Both types MUST be exported from the package's public API.
- **FR-012**: `CohortDefinition.to_dict()` output MUST be directly usable as the `definition` parameter of the existing `CreateCohortParams` for cohort CRUD operations.
- **FR-013**: Behavioral criteria MUST support both rolling windows (`within_days/weeks/months`) and absolute date ranges (`from_date`+`to_date`), but not both simultaneously.

### Key Entities

- **CohortCriteria**: A single atomic condition for cohort membership. Contains an internal selector node (expression tree leaf) and optionally a behavior key + behavior dict (for event-based criteria). Constructed exclusively via class methods.
- **CohortDefinition**: A composed set of one or more criteria or nested definitions, combined with AND/OR logic. Produces the complete `selector` + `behaviors` JSON via `to_dict()`.
- **Selector Node**: A dict representing one leaf in the expression tree — references either a behavior (`property: "behaviors"`), a user property (`property: "user"`), or a cohort (`property: "cohort"`).
- **Behavior Entry**: A dict describing an event count condition with event selector, count type, and time window. Keyed by `bhvr_N` in the behaviors dictionary.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: All 7 `CohortCriteria` class methods (`did_event`, `did_not_do_event`, `has_property`, `property_is_set`, `property_is_not_set`, `in_cohort`, `not_in_cohort`) produce valid, inspectable criterion objects.
- **SC-002**: `CohortDefinition.to_dict()` produces structurally valid JSON for single criteria, AND-combined criteria, OR-combined criteria, and nested boolean expressions (3+ levels deep).
- **SC-003**: All 10 validation rules (CD1-CD10) are enforced at construction or serialization time with clear error messages, and every rule has at least one test exercising the error path.
- **SC-004**: `CohortDefinition.to_dict()` output is accepted by `CreateCohortParams(definition=...)` without modification — verified by `model_dump()` producing a valid flattened payload.
- **SC-005**: Behavior keys are globally unique across arbitrarily nested definitions — verified by property-based tests with randomized nesting structures.
- **SC-006**: Test coverage for new code meets or exceeds the project's 90% threshold.
- **SC-007**: All new code passes `mypy --strict` type checking with zero errors.
- **SC-008**: Property-based tests (Hypothesis) verify serialization invariants across randomized inputs — no crashes, no duplicate keys, valid JSON structure.

## Assumptions

- The builder generates Mixpanel's **legacy `selector` + `behaviors` format** (not the modern `groups` format). This format is universally accepted by both `create_cohort()` and inline query references.
- **Behavior count type** defaults to `"absolute"` (total count across window). Per-day frequency (`"day"`) is deferred to a future version.
- **B2B group analytics** (`data_group_id`) is out of scope — all generated JSON uses `null` for group identifiers.
- Report-based cohort criteria (funnel, retention, addiction, flows report references) are out of scope for this phase.
- The existing `Filter` class is consumed read-only — `CohortCriteria.did_event(where=...)` reads Filter's internal `_property`, `_operator`, `_value`, and `_property_type` fields to construct event selector expressions, but does not modify Filter.
- `CohortCriteria` and `CohortDefinition` are standalone types in Phase 0 — they do not yet integrate with `query()`, `query_funnel()`, `query_retention()`, or `query_flow()`. That integration happens in Phases 1-3.
- `did_not_do_event()` is a pure convenience shorthand that delegates to `did_event(exactly=0, ...)`.
