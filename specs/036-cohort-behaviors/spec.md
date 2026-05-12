# Feature Specification: Cohort Behaviors in Unified Query System

**Feature Branch**: `036-cohort-behaviors`  
**Created**: 2026-04-06  
**Status**: Draft  
**Input**: User description: "Add cohort filters, breakdowns, and metrics to the unified query system"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Filter Queries by Cohort Membership (Priority: P1)

A developer or LLM agent wants to restrict any analytics query (insights, funnels, retention, flows) to only users who belong to a specific cohort. They pass a cohort filter alongside existing property filters using the familiar `where=` parameter, referencing either a saved cohort by ID or an inline ad-hoc cohort definition.

**Why this priority**: Cohort filtering is the highest-value integration point because it works across all four query types and uses the existing `where=` parameter pattern that users already know. It unblocks the most common cohort use case: "show me metrics for this user segment."

**Independent Test**: Can be fully tested by constructing `Filter.in_cohort(123)` and verifying it produces correct bookmark JSON, independently of breakdown or metric features.

**Acceptance Scenarios**:

1. **Given** a saved cohort with ID 123, **When** a developer passes `where=Filter.in_cohort(123, "Power Users")` to `query()`, **Then** the generated bookmark params contain a `sections.filter[]` entry with `value: "$cohorts"`, `filterOperator: "contains"`, and `filterValue: [{cohort: {id: 123, name: "Power Users", negated: false}}]`.

2. **Given** an inline `CohortDefinition`, **When** a developer passes `where=Filter.in_cohort(cohort_def, name="Frequent Buyers")` to `query()`, **Then** the generated bookmark params contain a cohort filter entry with `filterValue: [{cohort: {raw_cohort: <definition dict>, name: "Frequent Buyers", negated: false}}]`.

3. **Given** a cohort filter and a property filter, **When** both are passed as `where=[Filter.in_cohort(123), Filter.equals("platform", "iOS")]`, **Then** both filters appear in `sections.filter[]` — the cohort filter with its special structure and the property filter with its standard structure.

4. **Given** `Filter.not_in_cohort(789, "Bots")`, **When** used in any query method, **Then** the generated filter entry has `filterOperator: "does not contain"`.

5. **Given** a cohort filter, **When** used with `query_funnel()` or `query_retention()`, **Then** it produces the same `sections.filter[]` structure as with `query()`.

6. **Given** a cohort filter, **When** used with `query_flow()`, **Then** it produces a top-level `filter_by_cohort` entry in the flat flow params (not inside `sections`), as a flat dict with `name`, `negated`, and either `id` (saved) or `raw_cohort` (inline).

7. **Given** a non-positive integer or non-integer value passed as `cohort` to `Filter.in_cohort()`, **When** the filter is constructed, **Then** a `ValueError` is raised immediately (fail-fast validation).

8. **Given** an inline `CohortDefinition` without a `name`, **When** used in `Filter.in_cohort()`, **Then** an empty string is used as the name (the API resolves display labels).

---

### User Story 2 - Break Down Results by Cohort Membership (Priority: P2)

A developer wants to segment query results by whether users belong to a cohort. They pass a `CohortBreakdown` in the `group_by=` parameter, producing "in cohort" and "not in cohort" segments in the results. This works with insights, funnels, and retention (but not flows).

**Why this priority**: Cohort breakdowns enable comparative analysis ("how do Power Users differ from everyone else?") which is the second most common cohort use case after filtering.

**Independent Test**: Can be fully tested by constructing `CohortBreakdown(123, "Power Users")` and verifying it produces correct `sections.group[]` JSON with `cohorts` array, independently of filter or metric features.

**Acceptance Scenarios**:

1. **Given** a saved cohort ID 123, **When** a developer passes `group_by=CohortBreakdown(123, "Power Users")` to `query()`, **Then** the generated `sections.group[]` entry has `cohorts: [{id: 123, name: "Power Users", negated: false, ...}, {id: 123, name: "Power Users", negated: true, ...}]` and `value: ["Power Users", "Not In Power Users"]`.

2. **Given** `CohortBreakdown(123, "Power Users", include_negated=False)`, **When** the group entry is built, **Then** only the non-negated cohort entry appears in the `cohorts` array and `value` has a single label.

3. **Given** an inline `CohortDefinition`, **When** used as `CohortBreakdown(cohort_def, name="Active Users")`, **Then** the `cohorts` array entries contain `raw_cohort: <definition dict>` instead of `id`.

4. **Given** a mixed `group_by` list containing both `CohortBreakdown` and `GroupBy` objects, **When** used with `query()` or `query_funnel()`, **Then** both cohort group entries and property group entries appear in `sections.group[]`.

5. **Given** a mixed `group_by` list containing both `CohortBreakdown` and `GroupBy`, **When** used with `query_retention()`, **Then** a `ValueError` is raised because retention does not support mixing cohort and property breakdowns.

6. **Given** `CohortBreakdown` alone (no `GroupBy`), **When** used with `query_retention()`, **Then** it works correctly without error.

7. **Given** a non-positive integer passed as `cohort` to `CohortBreakdown`, **When** constructed, **Then** a `ValueError` is raised.

---

### User Story 3 - Track Cohort Size Over Time (Priority: P3)

A developer wants to track how a cohort's size changes over time, or compare cohort sizes. They pass a `CohortMetric` in the `events=` parameter of `query()`, producing a time series of cohort member counts. This is insights-only and can be mixed with event metrics and formulas.

**Why this priority**: Cohort metrics enable "Cohorts Over Time" analysis, the third use case. It's insights-only and builds on the same infrastructure as the first two stories.

**Independent Test**: Can be fully tested by constructing `CohortMetric(123, "Power Users")` and verifying it produces a `sections.show[]` entry with `behavior.type: "cohort"` and `measurement.math: "unique"`, independently of filter or breakdown features.

**Acceptance Scenarios**:

1. **Given** a saved cohort ID 123, **When** a developer passes `events=CohortMetric(123, "Power Users")` to `query()`, **Then** the generated `sections.show[]` entry has `behavior.type: "cohort"`, `behavior.resourceType: "cohorts"`, `behavior.id: 123`, `behavior.name: "Power Users"`, and `measurement.math: "unique"`.

2. **Given** an inline `CohortDefinition`, **When** used as `CohortMetric(cohort_def, name="Active Premium")`, **Then** the show entry has `behavior.raw_cohort: <definition dict>` instead of `behavior.id`.

3. **Given** a list mixing `CohortMetric` and `Metric` objects, **When** passed to `query()`, **Then** both cohort and event show entries appear in `sections.show[]`, each with the correct behavior structure.

4. **Given** a `CohortMetric` and event metrics with a `Formula`, **When** queried together, **Then** the formula can reference both cohort and event metrics by letter (A, B, C...) and all show entries are marked `isHidden: true`.

5. **Given** top-level `math` or `math_property` parameters alongside a `CohortMetric`, **When** the query is validated, **Then** those parameters are ignored for the `CohortMetric` entries (cohorts always use `math="unique"`).

6. **Given** a `CohortMetric` passed to `query_funnel()` or `query_retention()`, **Then** a type error or validation error is raised because cohort metrics are insights-only.

7. **Given** a non-positive integer passed as `cohort` to `CohortMetric`, **When** constructed, **Then** a `ValueError` is raised.

---

### User Story 4 - Comprehensive Quality Assurance (Priority: P4)

A maintainer wants confidence that the new cohort types are robust against edge cases and that all validation rules are load-bearing (not dead code). Property-based tests exercise invariants across random inputs, and mutation testing verifies that tests actually catch introduced defects.

**Why this priority**: Quality assurance follows implementation. PBT and mutation testing catch edge cases that example-based tests miss.

**Independent Test**: Can be run independently via `just test-pbt` and `just mutate` after all implementation phases are complete.

**Acceptance Scenarios**:

1. **Given** random valid inputs for `CohortBreakdown` and `CohortMetric`, **When** property-based tests generate thousands of examples, **Then** all invariants hold (e.g., bookmark JSON always has correct structure, validation never raises on valid input).

2. **Given** the new validation rules (CF1-CF2, CB1-CB3, CM1-CM3, B22-B26), **When** mutation testing introduces code changes, **Then** at least 80% of mutants are killed by existing tests.

3. **Given** all new public types (`CohortBreakdown`, `CohortMetric`), **When** checked, **Then** they are exported from the public API and have complete docstrings with examples.

---

### Edge Cases

- What happens when `Filter.in_cohort()` receives a `CohortDefinition` with no name and no `name=` argument? Empty string is used as the name fallback.
- What happens when multiple cohort filters are combined in `where=`? Each generates a separate `sections.filter[]` entry; AND logic applies between them.
- What happens when `CohortBreakdown` and `GroupBy` are mixed in `query_retention()`? Validation error is raised — they are mutually exclusive in retention.
- What happens when a `CohortMetric` is the only item in `events=` with no event metrics? Valid — produces a cohort-only insights query.
- What happens when `CohortMetric` is used with `formula=`? Works correctly — formula can reference cohort metrics by letter.
- What happens when `CohortBreakdown` has `include_negated=False`? Only the "in cohort" segment appears; no "Not In" segment is generated.
- What happens when `query_flow()` receives cohort filters alongside per-step filters? Cohort filter goes to top-level `filter_by_cohort`; step filters remain in `steps[].property_filter_params_list`.

## Requirements *(mandatory)*

### Functional Requirements

**Phase 1 — Cohort Filters**

- **FR-001**: `Filter` MUST provide `in_cohort(cohort, name)` and `not_in_cohort(cohort, name)` class methods that accept either a saved cohort ID (positive integer) or an inline `CohortDefinition`.
- **FR-002**: Cohort filter construction MUST validate that integer cohort IDs are positive (CF1) and that names, if provided, are non-empty strings (CF2).
- **FR-003**: The filter-to-bookmark builder MUST detect cohort filters (by `_property == "$cohorts"`) and generate the cohort-specific JSON structure with `filterType: "list"`, `filterOperator: "contains"/"does not contain"`, and `filterValue: [{cohort: {...}}]`.
- **FR-004**: For inline `CohortDefinition` cohort filters, the builder MUST include `raw_cohort` containing the definition's serialized output in the `filterValue` cohort entry.
- **FR-005**: Cohort filters MUST work with `query()`, `query_funnel()`, `query_retention()`, and `query_flow()`.
- **FR-006**: For `query_flow()`, cohort filters MUST be converted to the legacy `filter_by_cohort` tree format at the top level of flow params.
- **FR-007**: Layer 2 bookmark validation MUST accept cohort filter entries as valid (B25).

**Phase 2 — Cohort Breakdowns**

- **FR-008**: The system MUST provide a `CohortBreakdown` type with `cohort` (int or `CohortDefinition`), `name` (optional string), and `include_negated` (boolean, default true) fields.
- **FR-009**: `CohortBreakdown` construction MUST validate that integer cohort IDs are positive (CB1) and names are non-empty when provided (CB2).
- **FR-010**: The `group_by` parameter on `query()`, `query_funnel()`, and `query_retention()` MUST accept `CohortBreakdown` alongside `str` and `GroupBy`.
- **FR-011**: The group-section builder MUST generate cohort-specific group entries with `cohorts` array, `value` labels, and `propertyType: null` for `CohortBreakdown` items.
- **FR-012**: For inline `CohortDefinition` breakdowns, group entries MUST include `raw_cohort` in each cohort array entry.
- **FR-013**: `query_retention()` MUST reject mixed `CohortBreakdown` and `GroupBy` in the same `group_by` list (CB3 — mutual exclusivity).
- **FR-014**: Layer 2 bookmark validation MUST validate that cohort group entries have a non-empty `cohorts` array (B26).

**Phase 3 — Cohort Metrics**

- **FR-015**: The system MUST provide a `CohortMetric` type with `cohort` (int or `CohortDefinition`) and `name` (optional string) fields.
- **FR-016**: `CohortMetric` construction MUST validate that integer cohort IDs are positive (CM1) and names are non-empty when provided (CM2).
- **FR-017**: The `events` parameter on `query()` MUST accept `CohortMetric` alongside `str`, `Metric`, and `Formula`.
- **FR-018**: The show-clause builder MUST generate entries with `behavior.type: "cohort"`, `behavior.resourceType: "cohorts"`, and `measurement.math: "unique"` for `CohortMetric` items.
- **FR-019**: For saved cohorts, the show entry MUST include `behavior.id`. For inline definitions, it MUST include `behavior.raw_cohort`.
- **FR-020**: Top-level `math`, `math_property`, and `per_user` parameters MUST be ignored for `CohortMetric` entries (CM3 — cohorts always use `math="unique"`).
- **FR-021**: `CohortMetric` MUST NOT be accepted by `query_funnel()`, `query_retention()`, or `query_flow()` (CM4 — insights only).
- **FR-022**: Layer 2 bookmark validation MUST validate cohort show entries: `behavior.id` is a positive integer (B22), `behavior.resourceType` is `"cohorts"` (B23), and `measurement.math` is `"unique"` (B24).

**Phase 4 — Polish**

- **FR-023**: All new public types (`CohortBreakdown`, `CohortMetric`) MUST be exported from the package's public API.
- **FR-024**: Property-based tests MUST verify invariants for all new types across random valid inputs.
- **FR-025**: Mutation testing MUST achieve at least 80% kill rate on new validation rules.
- **FR-026**: All new classes and methods MUST have complete docstrings with examples.

### Key Entities

- **`Filter`** (extended): Gains `in_cohort()` and `not_in_cohort()` class methods. Internally uses `_property="$cohorts"` to signal cohort filter mode to the bookmark builder.
- **`CohortBreakdown`**: New frozen dataclass representing a cohort-based breakdown dimension. Accepted in `group_by=` parameter alongside `str` and `GroupBy`.
- **`CohortMetric`**: New frozen dataclass representing a cohort size metric. Accepted in `events=` parameter of `query()` only.
- **`CohortDefinition`** (existing, from Phase 0): Used as the `cohort` argument type (alongside `int`) across all three new capabilities for inline ad-hoc cohorts.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: All three cohort capabilities (filter, breakdown, metric) produce bookmark JSON that matches the structure documented in the design specification, verified by unit tests comparing against known-good JSON fixtures.
- **SC-002**: Cohort filters work identically across all four query methods (`query`, `query_funnel`, `query_retention`, `query_flow`), verified by tests for each method.
- **SC-003**: Every validation rule (CF1-CF2, CB1-CB3, CM1-CM4, B22-B26) has at least one test that triggers it and verifies the correct error message.
- **SC-004**: Invalid inputs (non-positive IDs, empty names, mixed retention breakdowns) are caught at construction or validation time before any API call, verified by fail-fast tests.
- **SC-005**: Both saved cohort references (by integer ID) and inline `CohortDefinition` objects produce correct output at every integration point, verified by parallel test cases for each.
- **SC-006**: Property-based tests generate at least 100 examples per invariant (200 in CI) without failures.
- **SC-007**: Mutation testing achieves at least 80% kill rate on new validation code.
- **SC-008**: Overall test coverage remains above 90% after all changes.

## Assumptions

- Phase 0 (`CohortCriteria` and `CohortDefinition`) is complete and merged. These types are available for use as inline cohort references.
- The `Filter._value` field type will need to be widened to accommodate cohort filter values (list of dicts). This is an internal implementation detail that does not affect the public API surface.
- `query_flow()` currently has no `where=` parameter. Adding cohort filter support to flows requires introducing a `where=` parameter to `query_flow()` specifically for cohort filters.
- The `filter_by_cohort` legacy format is used only for flows. All other query types use the modern `sections.filter[]` format.
- `data_group_id` is always `null` (no B2B group analytics support in this version).
- Response format does not change — existing result types handle cohort-enhanced responses without modification.
- The existing bookmark enum sets already include `"cohort"` in metric types and `"cohorts"` in resource types, so no enum changes are needed.
