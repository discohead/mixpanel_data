# Feature Specification: Custom Properties in Queries

**Feature Branch**: `037-custom-properties-queries`  
**Created**: 2026-04-07  
**Status**: Draft  
**Input**: User description: "ALL 6 Phases of this design — custom-properties-in-queries-design.md"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Break Down Results by Custom Properties (Priority: P1)

As a data analyst, I want to segment my query results by a custom computed property so that I can discover patterns that raw properties alone cannot reveal. For example, I want to break down purchases by a "revenue tier" computed from price and quantity, or by a saved custom property that classifies users into segments.

I can use either a **saved custom property** (referenced by its integer ID from the project) or an **inline custom property** (defined ad-hoc with a formula and input properties). Both work in the `group_by` parameter of `query()`, `query_funnel()`, and `query_retention()`.

**Why this priority**: Group-by is the most common custom property use case. It enables segmentation by computed dimensions that don't exist as raw properties, which is the core value of custom properties in analytics.

**Independent Test**: Can be fully tested by passing a custom property reference or inline definition to `group_by` in any query method and verifying the results are segmented by the computed property.

**Acceptance Scenarios**:

1. **Given** a saved custom property with ID 42 exists in the project, **When** I pass `GroupBy(property=CustomPropertyRef(42), property_type="number")` to `query()`, **Then** results are segmented by that custom property and the bookmark JSON contains `customPropertyId: 42` in the group section.
2. **Given** I define an inline formula `"A * B"` with inputs mapping A to "price" (number) and B to "quantity" (number), **When** I pass this as `GroupBy(property=InlineCustomProperty(...), property_type="number")` to `query()`, **Then** results are segmented by the computed revenue value and the bookmark JSON contains a `customProperty` dict with `displayFormula`, `composedProperties`, `propertyType`, and `resourceType`.
3. **Given** an inline custom property used as a group-by dimension, **When** I also specify bucketing (e.g., `bucket_size=100`), **Then** the bucketing configuration is applied to the custom property group entry.
4. **Given** an `InlineCustomProperty` with an explicit `property_type`, **When** used in a `GroupBy` that also has its own `property_type`, **Then** the inline custom property's `property_type` takes precedence in the bookmark output.
5. **Given** a list of mixed group-by dimensions (plain string, `CustomPropertyRef`, `InlineCustomProperty`), **When** I pass them all to `group_by`, **Then** each produces its correct bookmark JSON format and all coexist in the group section.
6. **Given** a saved custom property reference, **When** I use it in `query_funnel()` group_by, **Then** the funnel results are segmented by that custom property.
7. **Given** a saved custom property reference, **When** I use it in `query_retention()` group_by, **Then** the retention results are segmented by that custom property.

---

### User Story 2 - Filter Results by Custom Properties (Priority: P1)

As a data analyst, I want to filter my query results using a custom property condition so that I can restrict analysis to events matching a computed criterion. For example, I want to filter to only events where computed revenue (price * quantity) exceeds 1000, or where a saved custom property value equals "Premium".

I can use either a saved custom property reference or an inline definition in any of the 18 existing `Filter` class methods (e.g., `Filter.equals()`, `Filter.greater_than()`, `Filter.between()`).

**Why this priority**: Filtering is equally fundamental to group-by. Together they cover the two most common custom property positions in analytics queries.

**Independent Test**: Can be fully tested by passing a custom property to any `Filter` class method and verifying the filter is applied correctly in the bookmark JSON.

**Acceptance Scenarios**:

1. **Given** a saved custom property with ID 42, **When** I pass `Filter.greater_than(property=CustomPropertyRef(42), value=100)` to `query()` via `where=`, **Then** the bookmark filter entry contains `customPropertyId: 42` and no `value` field (the property name field).
2. **Given** an inline formula `"A * B"` computing revenue, **When** I pass `Filter.greater_than(property=InlineCustomProperty.numeric("A * B", A="price", B="qty"), value=1000)` to `where=`, **Then** the bookmark filter entry contains a `customProperty` dict with the formula and composed properties.
3. **Given** a plain string property used in a filter, **When** the query is built, **Then** the filter entry is unchanged from the current format (backward compatibility).
4. **Given** a `CustomPropertyRef` used in a filter with `resource_type="people"`, **When** the filter entry is built, **Then** the `resourceType` field reflects "people".
5. **Given** an `InlineCustomProperty` with `resource_type="people"`, **When** used in a filter, **Then** the filter entry's `resourceType` is "people" and the `customProperty` dict's `resourceType` is also "people".
6. **Given** an `InlineCustomProperty` with an explicit `property_type="string"`, **When** used in a filter, **Then** the `filterType` and `defaultType` fields in the bookmark entry reflect "string".
7. **Given** all 18 `Filter` class methods, **When** any of them receives a `CustomPropertyRef` or `InlineCustomProperty` as the `property` argument, **Then** the filter is constructed successfully without errors.

---

### User Story 3 - Aggregate Metrics on Custom Properties (Priority: P2)

As a data analyst, I want to compute aggregations (average, median, min, max, percentiles) on a custom property so that I can measure computed values over time. For example, I want the average revenue per purchase where revenue is price * quantity, using either a saved custom property or an inline formula.

**Why this priority**: Metric aggregation on custom properties is powerful but used less frequently than group-by and filter. It applies only to property-based math types (average, median, min, max, p25, p75, p90, p99).

**Independent Test**: Can be fully tested by passing a custom property to `Metric.property` with a property-based math type and verifying the measurement section of the bookmark JSON.

**Acceptance Scenarios**:

1. **Given** a saved custom property with ID 42, **When** I pass `Metric("Purchase", math="average", property=CustomPropertyRef(42))` to `query()`, **Then** the measurement property in the bookmark JSON contains `customPropertyId: 42` and `resourceType: "events"`.
2. **Given** an inline formula `"A * B"` computing revenue, **When** I pass `Metric("Purchase", math="average", property=InlineCustomProperty.numeric("A * B", A="price", B="quantity"))` to `query()`, **Then** the measurement property contains a `customProperty` dict with the formula and composed properties.
3. **Given** a plain string used as `Metric.property`, **When** the query is built, **Then** the measurement property contains `name` and `resourceType` as before (backward compatibility).
4. **Given** a `CustomPropertyRef` in `Metric.property`, **When** used in `query_funnel()` via a per-step metric, **Then** the funnel measurement property contains `customPropertyId`.
5. **Given** a top-level `math_property` as a plain string, **When** the query is built, **Then** the measurement property is unchanged from the current format (backward compatibility).

---

### User Story 4 - Define Inline Custom Properties with Formulas (Priority: P2)

As a data analyst, I want to define ad-hoc computed properties directly in my queries using a formula language so that I can perform computed analysis without saving a custom property to the project first. This is especially valuable for one-off explorations and for AI agents that can reason about property transformations programmatically.

The formula language supports arithmetic, string manipulation, conditionals, type checking, date operations, and list operations. Formulas use single-letter variables (A-Z) that map to raw property inputs.

**Why this priority**: Inline definitions are the key differentiator over simply referencing saved IDs. They enable ad-hoc exploration without project-level side effects.

**Independent Test**: Can be fully tested by constructing an `InlineCustomProperty` with various formulas and input configurations, then verifying the composed bookmark JSON.

**Acceptance Scenarios**:

1. **Given** a formula `"A * B"` with inputs A="price" (number) and B="quantity" (number), **When** I construct an `InlineCustomProperty`, **Then** the object stores the formula, inputs, and property_type correctly.
2. **Given** the convenience constructor `InlineCustomProperty.numeric("A * B", A="price", B="quantity")`, **When** I construct it, **Then** all inputs are typed as "number" with `resource_type="event"` and the `property_type` is "number".
3. **Given** inputs with mixed resource types (event and user properties), **When** I construct an `InlineCustomProperty`, **Then** each input preserves its individual `resource_type`.
4. **Given** a formula referencing a single property `"A"`, **When** I use `InlineCustomProperty.numeric("A", A="amount")`, **Then** it works as a simple numeric property reference with formula support.
5. **Given** a `PropertyInput` with just a name, **When** constructed, **Then** it defaults to `type="string"` and `resource_type="event"`.
6. **Given** all five property types (string, number, boolean, datetime, list), **When** used in a `PropertyInput`, **Then** each is accepted and preserved.
7. **Given** constructed custom property types, **When** I attempt to modify any field, **Then** a `FrozenInstanceError` is raised (immutability guarantee).

---

### User Story 5 - Fail-Fast Validation for Custom Properties (Priority: P3)

As a developer using the library, I want invalid custom property specifications to be caught immediately at query-build time so that I get clear error messages before any API call is made. This prevents wasted API calls and provides actionable diagnostics.

**Why this priority**: Validation is a quality-of-life improvement that prevents confusing API errors. The feature is functional without it, but validation makes it robust.

**Independent Test**: Can be fully tested by constructing invalid custom property specifications and verifying that specific, descriptive validation errors are raised.

**Acceptance Scenarios**:

1. **Given** a `CustomPropertyRef` with ID 0 or negative, **When** used in any query position (group_by, where, or Metric.property), **Then** a validation error is raised with a message containing "positive integer".
2. **Given** an `InlineCustomProperty` with an empty or whitespace-only formula, **When** used in any query position, **Then** a validation error is raised with a message containing "non-empty".
3. **Given** an `InlineCustomProperty` with an empty inputs dict, **When** used in any query position, **Then** a validation error is raised with a message containing "at least one input".
4. **Given** an `InlineCustomProperty` with a lowercase, multi-character, or numeric input key, **When** used in any query position, **Then** a validation error is raised with a message containing "uppercase".
5. **Given** an `InlineCustomProperty` with a formula exceeding 20,000 characters, **When** used in any query position, **Then** a validation error is raised with a message containing "20,000".
6. **Given** an `InlineCustomProperty` with a `PropertyInput` that has an empty name, **When** used in any query position, **Then** a validation error is raised with a message containing "empty property name".
7. **Given** valid custom property specifications in any query position, **When** the query is built, **Then** no validation errors are raised.
8. **Given** custom properties in `query_funnel()` and `query_retention()`, **When** invalid, **Then** the same validation rules apply as in `query()`.

---

### User Story 6 - Quality Assurance and Robustness (Priority: P3)

As a library maintainer, I want property-based tests and mutation testing to verify that custom property types and builders are robust across a wide range of inputs, so that edge cases are caught automatically and test quality is quantifiably high.

**Why this priority**: Quality assurance is essential for long-term maintainability but can be layered on after the core feature is functional.

**Independent Test**: Can be tested by running the property-based test suite and mutation testing against the custom property code and verifying the target scores are met.

**Acceptance Scenarios**:

1. **Given** randomly generated valid `PropertyInput` values, **When** constructed, **Then** all field values survive round-trip (construction preserves inputs).
2. **Given** randomly generated valid `InlineCustomProperty` values, **When** constructed, **Then** formula and inputs are preserved exactly.
3. **Given** randomly generated valid inputs dicts, **When** passed to the composed properties builder, **Then** output keys match input keys exactly and each entry contains the required fields (value, type, resourceType).
4. **Given** the full test suite, **When** coverage is measured, **Then** total coverage is at or above 90%.
5. **Given** the custom property code, **When** mutation testing is run, **Then** the mutation score is at or above 80%.

---

### Edge Cases

- What happens when an `InlineCustomProperty` formula references variables not present in the inputs dict? The library does not validate formula-to-input consistency; the server returns an error at query time.
- What happens when a `CustomPropertyRef` references an ID that doesn't exist in the project? The server returns an error at query time; client-side validation only checks positivity.
- What happens when multiple custom properties of different types (saved ref, inline, plain string) are mixed in the same `group_by` list? All three forms coexist; each produces its own bookmark JSON format.
- What happens when an `InlineCustomProperty` has `property_type=None`? The builder falls back to the containing type's property_type (e.g., `GroupBy.property_type` or `Filter._property_type`).
- What happens when `InlineCustomProperty.numeric()` is called with no keyword arguments? An `InlineCustomProperty` with an empty inputs dict is created, which fails CP3 validation at query-build time.
- What happens when a custom property is used in `query_flow()`? Flows use a different filter format and do not support custom properties in breakdowns; this is out of scope.
- What happens when existing code passes plain strings to all property fields? All changes are additive union extensions; existing code works unchanged.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST provide a `PropertyInput` type that represents a raw property reference with name, data type, and resource domain
- **FR-002**: System MUST provide an `InlineCustomProperty` type that defines a computed property via a formula and a mapping of letter variables (A-Z) to `PropertyInput` references
- **FR-003**: System MUST provide a `CustomPropertyRef` type that references a saved custom property by its integer ID
- **FR-004**: System MUST provide a convenience constructor (`InlineCustomProperty.numeric()`) that creates an all-numeric-input inline custom property from keyword arguments
- **FR-005**: All three new types MUST be immutable (frozen)
- **FR-006**: `GroupBy.property` MUST accept plain strings, `CustomPropertyRef`, and `InlineCustomProperty`
- **FR-007**: All 18 `Filter` class methods MUST accept plain strings, `CustomPropertyRef`, and `InlineCustomProperty` as the property argument
- **FR-008**: `Metric.property` MUST accept plain strings, `CustomPropertyRef`, and `InlineCustomProperty` (in addition to `None`)
- **FR-009**: The filter bookmark builder MUST produce `customPropertyId` for saved refs and `customProperty` dict for inline definitions
- **FR-010**: The group-by bookmark builder MUST produce `customPropertyId` for saved refs and `customProperty` dict for inline definitions
- **FR-011**: The measurement property builder MUST produce `customPropertyId` for saved refs and `customProperty` dict for inline definitions
- **FR-012**: The composed properties builder MUST translate `PropertyInput.name` to `value` and `PropertyInput.resource_type` to `resourceType` in the bookmark JSON
- **FR-013**: Bucketing (`bucket_size`, `bucket_min`, `bucket_max`) MUST work with all three property types in group-by
- **FR-014**: When `InlineCustomProperty.property_type` is set, it MUST take precedence over the containing type's property_type in bookmark output
- **FR-015**: When `InlineCustomProperty.property_type` is `None`, the builder MUST fall back to the containing type's property_type
- **FR-016**: Custom property validation MUST check: positive ID (CP1), non-empty formula (CP2), non-empty inputs (CP3), single uppercase letter keys (CP4), formula length <= 20,000 (CP5), non-empty input property names (CP6)
- **FR-017**: Validation MUST run in all three query pipelines: insights, funnels, and retention
- **FR-018**: Validation errors MUST be raised before any API call is made (fail-fast)
- **FR-019**: All existing code using plain string properties MUST continue to work without modification (backward compatibility)
- **FR-020**: The three new types MUST be exported from the package's public API
- **FR-021**: All new types and modified methods MUST have complete docstrings with examples
- **FR-022**: Custom properties in `query_funnel()` measurement MUST follow the same bookmark format as insights
- **FR-023**: The filter builder MUST NOT emit a `value` field (property name) when a custom property is used; instead it emits `customPropertyId` or `customProperty`
- **FR-024**: The group-by builder MUST NOT emit `value` or `propertyName` fields when a custom property is used
- **FR-025**: `InlineCustomProperty` resource_type MUST default to `"events"` and `PropertyInput` resource_type MUST default to `"event"`
- **FR-026**: `PropertyInput` type MUST default to `"string"` and accept all five valid types (string, number, boolean, datetime, list)

### Key Entities

- **PropertyInput**: A raw property reference mapping a formula variable to a named property with a data type and domain (event or user). Becomes one entry in the bookmark's `composedProperties` dict.
- **InlineCustomProperty**: An ephemeral computed property defined by a formula expression and a set of property inputs. Computed at query time without being saved to the project. Contains a formula string, inputs mapping, optional result type, and resource domain.
- **CustomPropertyRef**: A reference to a persisted custom property by its integer ID. The query engine fetches the full definition from the project at execution time.
- **PropertySpec**: A type alias representing the union of plain string, `CustomPropertyRef`, and `InlineCustomProperty`. Used as the accepted type for property fields across the query API.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: All three query positions (group-by, filter, measurement) accept both saved custom property references and inline custom property definitions without errors
- **SC-002**: All existing queries using plain string properties continue to produce identical results (zero regressions)
- **SC-003**: 6 validation rules catch all invalid custom property inputs with descriptive, actionable error messages before any API call
- **SC-004**: All quality gates pass: formatting, linting, type checking, and tests
- **SC-005**: Test coverage remains at or above 90%
- **SC-006**: Mutation testing score for new code is at or above 80%
- **SC-007**: Property-based tests verify type construction invariants across randomized inputs
- **SC-008**: Custom properties work consistently across insights, funnel, and retention query engines

## Assumptions

- Saved custom properties referenced by `CustomPropertyRef` already exist in the Mixpanel project (created via `create_custom_property()` or the Mixpanel UI)
- The Mixpanel API's bookmark format for custom properties is stable and follows the patterns documented in the design (based on the analytics reference implementation)
- Formula-to-input variable consistency is not validated client-side; the server handles formula parsing and reports errors for undefined variables
- `query_flow()` does not support custom properties in breakdowns (Mixpanel limitation) and is explicitly out of scope
- Custom events (`CustomEventRef`) are a separate feature and out of scope for this specification
- Behavior-based inline custom properties are a v2 enhancement and out of scope
- The `PropertyInput` resource_type uses `"event"`/`"user"` (singular) while `InlineCustomProperty` resource_type uses `"events"`/`"people"` (plural), matching Mixpanel's existing schema conventions at each level
- The convenience constructor `InlineCustomProperty.numeric()` covers the most common use case (all-numeric event properties); other combinations require the full constructor
