# Feature Specification: Workspace.query() — Typed Insights Query API

**Feature Branch**: `029-insights-query-api`  
**Created**: 2026-04-04  
**Status**: Draft  
**Input**: User description: "Workspace.query() — typed insights query API"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Simple Event Query (Priority: P1)

A developer queries a single event with minimal configuration and receives structured results. This is the most common analytics question: "how many times did X happen recently?" The method should work with just an event name — all other parameters use sensible defaults (last 30 days, daily granularity, total event count).

**Why this priority**: This is the entry point for every user. If the simplest case isn't frictionless, adoption fails. It also validates the entire pipeline: parameter construction, query execution, and result parsing.

**Independent Test**: Can be fully tested by calling the method with a single event name string and verifying that structured results are returned with date, event name, and count columns.

**Acceptance Scenarios**:

1. **Given** a connected workspace, **When** the user queries with just an event name, **Then** the system returns daily event counts for the last 30 days in a tabular format.
2. **Given** a connected workspace, **When** the user queries with an event name and a custom lookback period, **Then** the system returns daily event counts for that period.
3. **Given** a connected workspace, **When** the user queries with explicit start and end dates, **Then** the system returns event counts for the specified date range.
4. **Given** a connected workspace, **When** the user queries with a custom time granularity (weekly, monthly), **Then** results are grouped by the specified time unit.
5. **Given** a connected workspace, **When** the user queries an event name that does not exist in the project, **Then** the system returns an empty result set with zero rows (not an error).

---

### User Story 2 - Aggregation Control (Priority: P1)

A developer controls how events are counted: total occurrences, unique users, daily/weekly/monthly active users, or property-based aggregations (average purchase amount, median response time, percentiles). This unlocks metrics that are currently impossible without raw JSON construction.

**Why this priority**: DAU/WAU/MAU and property aggregations are among the most requested capabilities that have no existing typed method. They are core to product analytics workflows.

**Independent Test**: Can be tested by querying with different aggregation types and verifying that result values change appropriately (e.g., unique counts are always less than or equal to total counts).

**Acceptance Scenarios**:

1. **Given** a connected workspace, **When** the user queries with unique-user counting, **Then** results reflect deduplicated user counts per period.
2. **Given** a connected workspace, **When** the user queries for daily active users, **Then** results reflect DAU metrics that are not available through other methods.
3. **Given** a connected workspace, **When** the user queries for average of a numeric property, **Then** the system requires a property name and returns the averaged values.
4. **Given** a connected workspace, **When** the user queries with a percentile aggregation (p90, p99), **Then** results reflect the specified percentile of the property values.
5. **Given** a connected workspace, **When** the user queries with per-user pre-aggregation, **Then** the system first aggregates per user then across all users (e.g., average purchases per user).

---

### User Story 3 - Filtering and Breakdown (Priority: P1)

A developer filters results by property conditions and/or breaks down results by property values. Filters narrow the dataset (e.g., "only US users on iOS"). Breakdowns split results into segments (e.g., "by platform" or "by revenue bucket").

**Why this priority**: Filtering and segmentation are fundamental to every analytics workflow. Without them, queries return undifferentiated totals that lack actionable insight.

**Independent Test**: Can be tested by querying with filters and verifying that results only include matching data, and by querying with breakdowns and verifying that results contain per-segment rows.

**Acceptance Scenarios**:

1. **Given** a connected workspace, **When** the user adds a string equality filter (e.g., country equals "US"), **Then** results include only events matching the filter.
2. **Given** a connected workspace, **When** the user adds a numeric comparison filter (e.g., amount greater than 100), **Then** results include only events matching the condition.
3. **Given** a connected workspace, **When** the user adds multiple filters, **Then** all filters are combined with AND logic.
4. **Given** a connected workspace, **When** the user adds a property breakdown, **Then** results are split into one series per distinct property value.
5. **Given** a connected workspace, **When** the user adds a numeric property breakdown with bucket configuration, **Then** results are grouped into the specified numeric ranges.
6. **Given** a connected workspace, **When** the user checks for property existence, **Then** results correctly filter for events where the property is/is not set.
7. **Given** a connected workspace, **When** the user adds multiple breakdowns, **Then** results reflect all breakdown dimensions simultaneously.

---

### User Story 4 - Multi-Metric Comparison (Priority: P2)

A developer compares multiple events on the same query — for example, signups vs. logins vs. purchases over time. Each event can optionally have its own aggregation settings.

**Why this priority**: Comparing multiple metrics side-by-side is one of the most common analytics tasks that currently requires manual JSON construction. It builds on Story 1 by accepting a list of events.

**Independent Test**: Can be tested by querying with multiple event names and verifying that results contain one series per event.

**Acceptance Scenarios**:

1. **Given** a connected workspace, **When** the user queries with multiple event names, **Then** results contain one series per event, all sharing the same time range and granularity.
2. **Given** a connected workspace, **When** the user queries with a mix of default and custom aggregation per event, **Then** each event uses its own aggregation while defaults apply to unspecified events.
3. **Given** a connected workspace, **When** the user queries with per-event filters, **Then** each event's filters apply only to that event (in addition to any global filters).

---

### User Story 5 - Formula-Based Computed Metrics (Priority: P2)

A developer defines a computed metric using a formula that references other metrics by position (A, B, C...). For example, computing a conversion rate as (purchases / signups) * 100. The raw metrics used by the formula are hidden from results — only the computed value appears.

**Why this priority**: Formulas enable derived metrics (conversion rates, ratios, custom KPIs) that are a core product analytics capability. They require multi-metric queries (Story 4) as a foundation.

**Independent Test**: Can be tested by querying with two events and a formula, then verifying that results contain only the computed metric (not the raw inputs).

**Acceptance Scenarios**:

1. **Given** a connected workspace with multiple events, **When** the user provides a formula expression referencing events by letter, **Then** results contain the computed metric with server-calculated values.
2. **Given** a connected workspace, **When** the user provides a formula with a custom label, **Then** the computed metric uses the provided label in results.
3. **Given** a connected workspace, **When** the user provides a formula, **Then** the raw input metrics are hidden from the result output.

---

### User Story 6 - Advanced Analysis Modes (Priority: P2)

A developer applies rolling window averages or cumulative analysis to any query. For example, a 7-day rolling average of daily signups smooths out day-of-week effects.

**Why this priority**: Rolling averages and cumulative views are standard analytical tools that are currently impossible without raw JSON. They build on all previous stories.

**Independent Test**: Can be tested by querying with rolling window enabled and verifying that result values reflect the smoothed average rather than raw daily counts.

**Acceptance Scenarios**:

1. **Given** a connected workspace, **When** the user enables a rolling window analysis with a specified window size, **Then** results reflect rolling averages over the specified period.
2. **Given** a connected workspace, **When** the user enables cumulative analysis, **Then** results reflect running totals that increase monotonically.
3. **Given** a connected workspace, **When** the user attempts to enable both rolling and cumulative, **Then** the system rejects the request with a clear error explaining they are mutually exclusive.

---

### User Story 7 - Result Mode Selection (Priority: P2)

A developer controls whether results are returned as a time series (per-period values), an aggregate total (single number per metric), or a table. The choice affects how data is aggregated — a total-mode unique-user count deduplicates across the entire date range, while a timeseries-mode count shows per-period unique users that are not additive.

**Why this priority**: Mode selection changes query semantics, not just presentation. Users need to understand and control whether they get time-series data or aggregate KPIs.

**Independent Test**: Can be tested by querying the same event in timeseries and total modes and verifying that the total mode returns a single aggregate number while timeseries returns per-period data.

**Acceptance Scenarios**:

1. **Given** a connected workspace, **When** the user selects timeseries mode (default), **Then** results contain one value per time period per metric.
2. **Given** a connected workspace, **When** the user selects total mode, **Then** results contain a single aggregate value per metric across the entire date range.
3. **Given** a connected workspace, **When** the user selects table mode, **Then** results are returned in tabular format.

---

### User Story 8 - Query Debugging and Persistence (Priority: P3)

A developer inspects the generated query parameters for debugging purposes and optionally saves the query as a persistent report. The query parameters are returned alongside results so users can understand what was sent to the server, reproduce issues, or persist queries for reuse.

**Why this priority**: Debuggability is essential for a system that generates complex queries. Persistence enables the workflow of "explore interactively, then save what works." This is a value-add on top of core query functionality.

**Independent Test**: Can be tested by running any query and verifying that the result object contains the generated query parameters, and that those parameters can be used to create a saved report.

**Acceptance Scenarios**:

1. **Given** a completed query, **When** the user inspects the result, **Then** the generated query parameters are available for examination.
2. **Given** a completed query result with parameters, **When** the user passes those parameters to the bookmark creation method, **Then** a saved report is created that reproduces the same query.
3. **Given** a completed query, **When** the user inspects the result, **Then** metadata about the query execution (computation time, date range, sampling) is available.

---

### Edge Cases

- What happens when the user queries an event name that doesn't exist? The system should return empty results, not an error.
- What happens when the user provides conflicting time parameters (e.g., both explicit dates and a lookback period with a non-default value)? The system should reject the request with a clear error message.
- What happens when the user specifies a property aggregation (average, sum, etc.) without naming the property? The system should reject the request immediately with a descriptive error.
- What happens when the user provides a formula but only a single event? The system should reject because formulas require at least two metrics to reference.
- What happens when per-user aggregation is combined with an incompatible aggregation type (DAU, WAU, MAU)? The system should reject with a clear error.
- What happens when the user provides a negative or zero lookback period? The system should reject with a clear error.
- What happens when the user provides only an end date without a start date? The system should reject because the time range is ambiguous.
- What happens when numeric bucket configuration includes min/max but no bucket size? The system should reject.
- What happens when the API returns a rate limit error (429)? The system should retry automatically with backoff (existing behavior) and raise a rate limit error if retries are exhausted.
- What happens when credentials are invalid or expired? The system should raise an authentication error immediately.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST accept a single event name as the minimum required input and return structured results using sensible defaults (30-day lookback, daily granularity, total event count).
- **FR-002**: System MUST accept multiple events and return one result series per event, enabling side-by-side comparison.
- **FR-003**: System MUST support the following counting aggregations: total event count, unique users, daily active users, weekly active users, and monthly active users.
- **FR-004**: System MUST support property-based aggregations (average, median, minimum, maximum, sum, and percentiles at p25, p75, p90, p99) when a property name is provided.
- **FR-005**: System MUST support per-user pre-aggregation (average, total, min, max per user first, then across users).
- **FR-006**: System MUST support global filter conditions using typed filter constructors for: string equality/inequality, string containment, numeric comparisons (greater than, less than, between), existence checks (is set, is not set), and boolean checks.
- **FR-007**: System MUST support per-event filter conditions that apply only to individual events in a multi-event query.
- **FR-008**: System MUST support property breakdown (segmentation) by string, number, boolean, and datetime properties, including numeric bucketing with configurable bucket size and range.
- **FR-009**: System MUST support multiple simultaneous property breakdowns.
- **FR-010**: System MUST support formula-based computed metrics referencing events by positional letter (A, B, C...), with an optional custom label, and automatically hide raw input metrics from results.
- **FR-011**: System MUST support three time range modes: relative lookback (last N units), absolute date range (start and end dates), and partial absolute (start date to today).
- **FR-012**: System MUST support time granularity selection: hour, day, week, month, quarter.
- **FR-013**: System MUST support three result modes: timeseries (per-period values), total (single aggregate per metric), and table (tabular detail).
- **FR-014**: System MUST support rolling window analysis with a configurable window size.
- **FR-015**: System MUST support cumulative analysis mode.
- **FR-016**: System MUST validate all parameter combinations before executing the query and reject invalid combinations with descriptive error messages (see Validation Rules below).
- **FR-017**: System MUST return structured results that include: the query data (time series or aggregates), the generated query parameters, execution metadata (computation timestamp, effective date range, sampling information), and a tabular data representation.
- **FR-018**: System MUST allow default aggregation settings to apply to events specified as plain strings, while events specified with explicit per-event configuration override those defaults.
- **FR-019**: System MUST propagate API errors (authentication failures, rate limits, server errors) using the existing exception hierarchy without suppressing or wrapping them, so callers can handle each error type distinctly.

### Validation Rules

- **VR-001**: Property-based aggregation types (average, median, min, max, sum, p25, p75, p90, p99) MUST require a property name.
- **VR-002**: Non-property aggregation types MUST reject a property name if provided.
- **VR-003**: Per-user aggregation MUST be incompatible with DAU, WAU, and MAU aggregations.
- **VR-004**: Formulas MUST require at least two events.
- **VR-005**: Rolling window and cumulative analysis MUST be mutually exclusive.
- **VR-006**: Rolling window size MUST be a positive integer.
- **VR-007**: Lookback period MUST be a positive integer.
- **VR-008**: End date without start date MUST be rejected.
- **VR-009**: Explicit dates combined with a non-default lookback period MUST be rejected.
- **VR-010**: Date values MUST be in YYYY-MM-DD format.
- **VR-011**: Numeric bucket min/max without bucket size MUST be rejected.
- **VR-012**: Bucket size MUST be positive.
- **VR-013**: Per-event configurations MUST be validated individually using the same rules as global aggregation settings.

### Key Entities

- **Event Metric**: Represents a single event to query, with its aggregation method, optional property, optional per-user aggregation, and optional per-event filters.
- **Filter Condition**: Represents a typed filter on a property — includes the property name, comparison operator, comparison value(s), and property data type.
- **Property Breakdown**: Represents a dimension to segment results by — includes the property name, data type, and optional numeric bucketing configuration.
- **Query Result**: The structured output containing the data series, generated query parameters, effective date range, computation metadata, and tabular representation.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Users can execute a single-event query with one required argument and receive results — zero additional configuration needed for the most common case.
- **SC-002**: All in-scope query patterns (event counts, unique users, segmentation, filtered aggregation, multi-metric comparison, conversion rate formulas, property aggregation, DAU/WAU/MAU, per-user aggregation, rolling averages, multiple breakdowns) can be expressed through this single method.
- **SC-003**: Invalid parameter combinations are caught and reported with actionable error messages before any network request is made.
- **SC-004**: Query results include the generated query parameters, enabling users to debug unexpected results or persist the query as a saved report without additional method calls.
- **SC-005**: The tabular data representation from results is usable for immediate analysis — correctly normalized with one row per (date, metric) pair for time series, or one row per metric for totals.
- **SC-006**: Existing test coverage threshold (90%) is maintained after adding this feature.
- **SC-007**: All validation rules are enforced with descriptive messages that name the conflicting parameters and explain the constraint.

## Assumptions

- Users have a connected workspace with valid credentials (Basic Auth service account or OAuth). Authentication is handled by the existing credential system.
- The Mixpanel insights query endpoint accepts inline query parameters without requiring a saved report to be created first. This has been confirmed through live testing.
- The target users are developers and LLM agents who are comfortable with function calls and keyword arguments. The method is not designed for non-technical users.
- Flows queries are out of scope — they use a fundamentally different data structure and are served by the existing `query_flows()` method.
- Ad-hoc funnel and retention queries are out of scope for this version. They are structurally different and better served by dedicated future methods.
- A single formula per query is sufficient for the initial version. Multiple formulas can be added later without breaking changes.
- Session-based math, custom percentile configuration, and histogram math are excluded from the initial version due to insufficient documentation of their exact semantics.
- The method will return results in the same structured format used by existing query methods, including tabular data representation.
- Filter conditions combine with AND logic at the global level. OR logic across filter groups is achievable through per-event filters.
