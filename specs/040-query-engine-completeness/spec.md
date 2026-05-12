# Feature Specification: Unified Query Engine Completeness

**Feature Branch**: `040-query-engine-completeness`
**Created**: 2026-04-14
**Status**: Draft
**Input**: User description: "All phases and tiers of unified-query-engine-audit-report.md"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Complete Math Type Coverage (Priority: P1)

A developer building an insights query needs to measure cumulative unique users over time, count sessions, find the most frequent property value, or get a numeric summary of a property. Currently, the library's type system prevents them from specifying these 7 valid math types even though the Mixpanel server accepts them.

Similarly, a developer building a retention query needs to measure total event counts or average property values per retention bucket, but the retention math type only exposes 2 of the 4 server-supported values. A developer building a funnel query cannot use histogram math.

**Why this priority**: Math types are the foundation of every analytics query. Missing types mean entire categories of analysis are impossible through the library, forcing developers to use raw API calls or untyped workarounds.

**Independent Test**: Can be tested by constructing queries with each newly supported math type and verifying the library accepts them without type errors and produces valid query parameters.

**Acceptance Scenarios**:

1. **Given** a developer building an insights query, **When** they specify `cumulative_unique` as the math type, **Then** the library accepts the value and produces valid query parameters
2. **Given** a developer building an insights query, **When** they specify any of `sessions`, `unique_values`, `most_frequent`, `first_value`, `multi_attribution`, or `numeric_summary`, **Then** the library accepts the value and produces valid query parameters
3. **Given** a developer using a math type that requires a property (e.g. `unique_values`, `most_frequent`, `first_value`, `multi_attribution`, `numeric_summary`), **When** they omit the property, **Then** the library raises ValueError during Metric construction
4. **Given** a developer building a retention query, **When** they specify `total` or `average` as the math type, **Then** the library accepts the value and produces valid query parameters
5. **Given** a developer building a funnel query, **When** they specify `histogram` as the math type, **Then** the library accepts the value and produces valid query parameters

---

### User Story 2 - Advanced Funnel and Retention Modes (Priority: P1)

A developer building a funnel query needs to control how users re-entering the funnel are counted — for example, counting each re-entry as a separate conversion ("aggressive") versus only counting the first completion ("default"). Currently there is no way to specify funnel reentry mode.

A developer building a retention query needs to control how users are counted across retention buckets — for example, carrying forward users who return after gaps as retained in intermediate buckets. They also need to switch between cumulative and period-over-period retention views. Neither retention unbounded mode nor cumulative mode is currently exposed.

A developer also needs to control attribution method (first-touch vs all-touch) via segment method for retention and funnel queries.

**Why this priority**: These parameters fundamentally change how queries are calculated. Without them, developers cannot reproduce analyses that are possible in the Mixpanel UI, making the library incomplete for serious analytics work.

**Independent Test**: Can be tested by constructing funnel and retention queries with each mode value and verifying the parameters appear correctly in the generated query output.

**Acceptance Scenarios**:

1. **Given** a developer building a funnel query, **When** they specify a reentry mode of "default", "basic", "aggressive", or "optimized", **Then** the query output includes the correct reentry mode setting
2. **Given** a developer building a funnel query, **When** they specify an invalid reentry mode, **Then** the library raises ValueError listing valid reentry modes
3. **Given** a developer building a retention query, **When** they specify an unbounded mode of "none", "carry_back", "carry_forward", or "consecutive_forward", **Then** the query output includes the correct unbounded mode setting
4. **Given** a developer building a retention query, **When** they set cumulative mode to true, **Then** the query output reflects cumulative retention rather than period-over-period
5. **Given** a developer building a retention or funnel query, **When** they specify a segment method of "first" or "all", **Then** the query output includes the correct attribution setting
6. **Given** a developer specifying segment method for an insights-only query, **When** they submit the query, **Then** the library raises ValueError explaining segment method is only valid for funnels, retention, and frequency queries

---

### User Story 3 - Period-Over-Period Time Comparison (Priority: P2)

A developer wants to compare current metrics against a previous period — such as this month's signups versus last month's, or this week's revenue versus the same week last year. Time comparison overlays a second time window on any insights, funnel, or retention query, enabling trend analysis and anomaly detection without running multiple queries.

**Why this priority**: Period-over-period comparison is one of the most common analytics workflows. Without it, developers must run two separate queries and manually align the results, a tedious and error-prone process.

**Independent Test**: Can be tested by adding a time comparison parameter to an insights query and verifying the generated query output contains the correct comparison configuration alongside the primary time range.

**Acceptance Scenarios**:

1. **Given** a developer building an insights query, **When** they add a relative time comparison with a unit such as "month", **Then** the query output includes a comparison configuration specifying the relative offset
2. **Given** a developer building a funnel or retention query, **When** they add a time comparison, **Then** the query output includes the same comparison structure
3. **Given** a developer specifying an absolute-start time comparison with a date, **When** they submit the query, **Then** the comparison period begins at the specified date with its end inferred from the primary period length
4. **Given** a developer specifying an absolute-end time comparison with a date, **When** they submit the query, **Then** the comparison period ends at the specified date with its start inferred backward
5. **Given** a developer building a flow query, **When** they attempt to add a time comparison, **Then** the library raises ValueError explaining flows do not support time comparison
6. **Given** a developer specifying a relative time comparison, **When** they omit the unit, **Then** the library raises ValueError during TimeComparison construction
7. **Given** a developer specifying an absolute time comparison, **When** they provide an invalid date format, **Then** the library raises ValueError during TimeComparison construction

---

### User Story 4 - Frequency Analysis in Bookmark Queries (Priority: P2)

A developer wants to understand how often users perform events — for example, breaking down a signup funnel by how many times users viewed a product, or filtering to users who performed a specific action at least 5 times. The library has a legacy frequency method but does not support frequency as a first-class concept in the modern query system, meaning it cannot be composed with other query features like breakdowns, filters, and time comparisons.

**Why this priority**: Frequency analysis answers "how often" questions that are fundamental to engagement and habit-formation analysis. The legacy method is isolated from the modern query engine and cannot benefit from its composability.

**Independent Test**: Can be tested by adding a frequency breakdown or frequency filter to an insights query and verifying the generated query output contains the correct frequency-specific structures.

**Acceptance Scenarios**:

1. **Given** a developer building a query, **When** they add a frequency breakdown for an event, **Then** the query output includes a group entry with frequency-specific behavior type and people-scoped resource type
2. **Given** a developer building a query, **When** they add a frequency filter (e.g., "Login frequency is at least 5"), **Then** the query output includes a filter entry with the frequency behavior and numeric threshold
3. **Given** a developer specifying a frequency breakdown, **When** they configure custom bucket boundaries (min, max, bucket size), **Then** the query output includes the bucket configuration
4. **Given** a developer using a frequency filter, **When** they use any valid frequency filter operator ("is at least", "is at most", "is greater than", "is less than", "is equal to", "is between"), **Then** the library accepts it and produces correct query output

---

### User Story 5 - Enhanced Behavioral Cohorts with Property Aggregations (Priority: P2)

A developer creating a behavioral cohort wants to define criteria based on property aggregations — for example, "users whose average purchase value exceeds $50" or "users whose maximum session duration exceeds 30 minutes." Currently, cohort behavioral criteria only support count-based thresholds (at least N, at most N, exactly N events), which limits the expressiveness of cohort definitions.

**Why this priority**: Property-based behavioral segmentation is essential for identifying high-value, at-risk, or power-user segments. Count-only cohorts miss behavioral quality signals that distinguish user segments.

**Independent Test**: Can be tested by creating a cohort criterion with an aggregation operator and property, and verifying the serialized cohort definition includes the aggregation operator and target property.

**Acceptance Scenarios**:

1. **Given** a developer building a cohort criterion, **When** they specify an aggregation of "average" with a target property and threshold, **Then** the criterion serializes with the correct aggregation operator and property reference
2. **Given** a developer, **When** they use any of the 6 aggregation operators (total, unique, average, min, max, median), **Then** the library accepts and correctly serializes each
3. **Given** a developer specifying an aggregation operator, **When** they omit the aggregation property, **Then** the library raises ValueError during CohortCriteria construction
4. **Given** a developer using count-based frequency without aggregation, **When** they build the criterion as before, **Then** existing behavior is preserved with no regressions

---

### User Story 6 - Complete Filter Operator Coverage (Priority: P3)

A developer building query filters needs operators that are currently missing from the filter builder — such as `not_between` for numeric range negation, `starts_with` and `ends_with` for string matching, `date_not_between` for date exclusion, `in_the_next` for future-relative dates, and inclusive numeric bounds (`at_least`, `at_most`). They must currently construct raw filter dictionaries to use these operators, which is error-prone and breaks the fluent API pattern.

**Why this priority**: While workarounds exist, missing filter methods break the fluent API pattern, increase the chance of typos in hand-constructed filter dictionaries, and make queries harder to read and maintain.

**Independent Test**: Can be tested by calling each new filter method and verifying it produces the correct operator string and value structure.

**Acceptance Scenarios**:

1. **Given** a developer, **When** they create a `not_between` filter with min and max values, **Then** the filter produces the "not between" operator with the correct value structure
2. **Given** a developer, **When** they create a `starts_with` filter with a prefix, **Then** the filter produces the "starts with" operator
3. **Given** a developer, **When** they create an `ends_with` filter with a suffix, **Then** the filter produces the "ends with" operator
4. **Given** a developer, **When** they create a `date_not_between` filter with start and end dates, **Then** the filter produces the "was not between" operator
5. **Given** a developer, **When** they create an `in_the_next` filter with a value and unit, **Then** the filter produces the "was in the next" operator
6. **Given** a developer, **When** they create `at_least` or `at_most` filters with a value, **Then** the filters produce "is at least" and "is at most" operators respectively

---

### User Story 7 - Group Analytics Scoping (Priority: P3)

A developer using Mixpanel's group analytics feature needs to scope queries to a specific data group (e.g., companies, accounts, workspaces) so that metrics are calculated at the group level rather than the user level. Currently, the data group identifier is hardcoded to null in all query engines, making group-level analysis impossible through the library.

**Why this priority**: Group analytics is a paid Mixpanel feature used by B2B companies. Without scoping support, these customers cannot use the library for their primary analytics use case.

**Independent Test**: Can be tested by passing a data group identifier to a query method and verifying it appears in the generated query output.

**Acceptance Scenarios**:

1. **Given** a developer with a group analytics project, **When** they specify a data group identifier on an insights query, **Then** the generated query output includes the group identifier in the appropriate locations
2. **Given** a developer, **When** they specify a data group identifier on funnel, retention, and flow queries, **Then** each engine threads the value through to the query output
3. **Given** a developer, **When** they omit the data group identifier, **Then** existing behavior is preserved (defaults to user-level analytics)

---

### User Story 8 - Advanced Flow Features (Priority: P3)

A developer building flow analyses needs capabilities beyond basic step sequencing: breaking down flow paths by a user property (e.g., "show flows segmented by country"), excluding specific events between steps, using session start/end as flow anchors, and applying global property filters to flow queries.

**Why this priority**: Flow analysis without segmentation or filtering produces overly broad results. These features are needed to answer targeted "how do users navigate" questions for specific user populations.

**Independent Test**: Can be tested by adding segments, exclusions, session events, or global filters to a flow query and verifying the generated parameters include the correct structures.

**Acceptance Scenarios**:

1. **Given** a developer building a flow query, **When** they add a breakdown by a user property, **Then** the generated parameters include the segments array with the property specification
2. **Given** a developer building a flow query, **When** they specify events to exclude between steps, **Then** the generated parameters include the exclusions array
3. **Given** a developer building a flow query, **When** they use session start or session end as a flow step, **Then** the library maps these to the correct session event format expected by the server
4. **Given** a developer building a flow query, **When** they add a global property filter, **Then** the generated parameters include the property filter alongside any cohort filters

---

### Edge Cases

- Math types requiring a property must validate that the property is provided; math types that do not accept a property must reject it if provided
- Segment method must be rejected for insights-only queries but accepted for funnels, retention, and frequency queries
- Time comparison must be rejected for flow queries with a clear engine-specific error message
- Frequency breakdowns must enforce people-scoped resource type and frequency-specific behavior type
- Frequency filter operators must be restricted to the 6 valid numeric operators; non-numeric operators must be rejected
- Aggregation-based cohort criteria must require an aggregation property; count-based criteria must reject aggregation properties
- Date-based filter values must validate format where applicable (e.g., in_the_next requires a positive integer and valid unit)
- Flow session events must map session start/end sentinel values to the server's session event format rather than treating them as regular event names
- All new parameters must be optional with backward-compatible defaults so existing code is unaffected
- Existing tests must continue to pass without modification (strict backward compatibility)
- Invalid enum values must produce clear error messages listing all valid options

## Requirements *(mandatory)*

### Functional Requirements

**Phase A — Type Expansions and Core Parameters (Tier 1)**

- **FR-001**: System MUST accept `cumulative_unique`, `sessions`, `unique_values`, `most_frequent`, `first_value`, `multi_attribution`, and `numeric_summary` as valid insights math types
- **FR-002**: System MUST enforce that `unique_values`, `most_frequent`, `first_value`, `multi_attribution`, and `numeric_summary` require a property parameter
- **FR-003**: System MUST accept `total` and `average` as valid retention math types in addition to existing `retention_rate` and `unique`
- **FR-004**: System MUST accept `histogram` as a valid funnel math type in addition to existing funnel math types
- **FR-005**: System MUST accept a segment method parameter on metrics with values "all" (default) or "first"
- **FR-006**: System MUST reject segment method on insights-only queries and accept it on funnel, retention, and frequency queries
- **FR-007**: System MUST accept a reentry mode parameter on funnel queries with values "default", "basic", "aggressive", or "optimized"
- **FR-008**: System MUST accept a retention unbounded mode parameter on retention queries with values "none" (default), "carry_back", "carry_forward", or "consecutive_forward"
- **FR-009**: System MUST accept a cumulative boolean parameter on retention queries defaulting to false
- **FR-010**: System MUST provide 7 additional filter factory methods: `not_between`, `starts_with`, `ends_with`, `date_not_between`, `in_the_next`, `at_least`, and `at_most`

**Phase B — New Feature Types (Tier 2)**

- **FR-011**: System MUST accept a time comparison parameter on insights, funnel, and retention queries
- **FR-012**: System MUST support 3 time comparison modes: relative (with unit: day, week, month, quarter, year), absolute-start (with date), and absolute-end (with date)
- **FR-013**: System MUST reject time comparison on flow queries
- **FR-014**: System MUST validate time comparison parameters: relative requires a valid unit; absolute modes require a valid date
- **FR-015**: System MUST accept a frequency breakdown in the group-by parameter, producing query output with frequency-specific behavior type and people-scoped resource type
- **FR-016**: System MUST accept configurable bucket boundaries (min, max, bucket size) on frequency breakdowns
- **FR-017**: System MUST accept a frequency filter in the where parameter, supporting numeric filter operators ("is at least", "is at most", "is greater than", "is less than", "is equal to", "is between")
- **FR-018**: System MUST accept an aggregation parameter on behavioral cohort criteria with values "total", "unique", "average", "min", "max", or "median"
- **FR-019**: System MUST require an aggregation property when an aggregation operator is specified on a cohort criterion
- **FR-020**: System MUST serialize aggregation-based cohort criteria with the aggregation operator in the behavioral condition output

**Phase C — Completeness (Tier 3)**

- **FR-021**: System MUST accept a data group identifier parameter on all query methods (insights, funnel, retention, flow) and include it in the generated query output
- **FR-022**: System MUST accept a segments/breakdowns parameter on flow queries for property-based flow path segmentation
- **FR-023**: System MUST accept an exclusions parameter on flow queries for excluding events between specific steps
- **FR-024**: System MUST map session start and session end sentinel values to the server's session event format when used as flow steps
- **FR-025**: System MUST accept global property filters on flow queries in addition to existing cohort filters

**Cross-Cutting**

- **FR-026**: All new parameters MUST be optional with backward-compatible defaults
- **FR-027**: All new parameter values MUST be validated against server-accepted values before query submission, with clear error messages listing valid options
- **FR-028**: All new types MUST be fully typed and pass strict type checking
- **FR-029**: Existing queries without new parameters MUST continue to produce identical output (backward compatibility)

### Key Entities

- **MathType**: Constrained set of valid mathematical operations for insights queries, expanded to include cumulative_unique, sessions, unique_values, most_frequent, first_value, multi_attribution, and numeric_summary
- **RetentionMathType**: Constrained set of valid math operations for retention queries, expanded to include total and average
- **FunnelMathType**: Constrained set of valid math operations for funnel queries, expanded to include histogram
- **SegmentMethod**: Attribution control specifying first-touch ("first") or all-touch ("all") event counting, applicable to funnels, retention, and frequency queries
- **FunnelReentryMode**: Controls how funnel re-entries are counted, with 4 modes: default, basic, aggressive, optimized
- **RetentionUnboundedMode**: Controls how users are counted across retention time buckets, with 4 modes: none, carry_back, carry_forward, consecutive_forward
- **TimeComparison**: Discriminated union of 3 comparison types (relative, absolute-start, absolute-end) for period-over-period overlay analysis
- **FrequencyBreakdown**: Frequency-based group-by concept that segments queries by how many times users perform a specified event, with configurable bucketing
- **FrequencyFilter**: Filter concept that restricts queries to users based on event frequency thresholds using numeric comparison operators
- **CohortAggregation**: Extended cohort criterion concept supporting property aggregation operators (total, unique, average, min, max, median) beyond count-based thresholds

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Developers can specify all server-supported insights math types without type errors or raw dictionary workarounds — 7 previously inaccessible math types (cumulative_unique, sessions, unique_values, most_frequent, first_value, multi_attribution, numeric_summary) become available
- **SC-002**: Developers can configure funnel reentry mode, retention unbounded mode, retention cumulative mode, and segment method using named parameters — 4 previously impossible query configurations become available
- **SC-003**: Developers can overlay a comparison time period on any insights, funnel, or retention query in a single call — period-over-period analysis that previously required 2 queries and manual alignment becomes a single operation
- **SC-004**: Developers can break down and filter queries by event frequency using the modern query system — frequency analysis joins the composable query engine rather than being isolated in a legacy method
- **SC-005**: Developers can create behavioral cohorts using property aggregations (total, unique, average, min, max, median) — 6 aggregation operators expand cohort definitions beyond count-only thresholds
- **SC-006**: Developers can use all server-supported filter operators through the fluent filter builder — 7 previously missing filter methods become available
- **SC-007**: Developers can scope any query to a specific data group for group-level analytics — B2B group analytics customers can use the library for their primary use case
- **SC-008**: Developers can segment, exclude, filter, and configure flow queries with breakdowns, exclusions, session events, and global property filters — 4 flow capabilities reach parity with the Mixpanel UI
- **SC-009**: All existing queries continue to work identically — zero regressions in generated output
- **SC-010**: All 29 confirmed gaps from the capability audit are closed, verified by query acceptance tests covering every new parameter and type value

## Assumptions

- The Mixpanel server's accepted values for these capabilities are stable and will not change during implementation
- The existing query builder architecture is extensible enough to accommodate all new parameters without structural refactoring
- Developers using the library have access to Mixpanel project configurations that support the features they invoke (e.g., group analytics requires a paid plan; session replay requires the feature to be enabled)
- The legacy `frequency()` method will be preserved for backward compatibility; the new frequency capability in the modern query engine is additive
- The `PerUserAggregation` session_replay_id_value gap (priority matrix item #17) is excluded from this scope due to its niche use case and low agent value; it can be addressed in a future iteration if needed
- All parameter names follow the library's existing naming conventions, mapped to the server's expected format by the query builders
- Validation errors provide clear, actionable messages identifying the invalid parameter and listing all valid options
- The implementation is phased (A → B → C) to allow incremental delivery and testing, but all phases are in scope for this feature
- The frequency show clause (audit section 2.2.3 — `type: "addiction"` behavior in `sections.show[]`) is excluded from scope; the existing legacy `frequency()` method covers standalone frequency metrics. This feature adds frequency as a composable breakdown (group_by) and filter (where) in the modern query engine, not as a standalone metric type.
