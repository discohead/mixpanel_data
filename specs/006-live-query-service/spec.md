# Feature Specification: Live Query Service

**Feature Branch**: `006-live-query-service`
**Created**: 2025-12-22
**Status**: Draft
**Input**: User description: "Phase 006 Live Query Service"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Run Segmentation Queries (Priority: P1)

Data analysts need to analyze event counts over time, optionally segmented by a property. This is the most common analytics query type - understanding how user behavior trends over time and differs across segments.

**Why this priority**: Segmentation is the most fundamental analytics query. It enables time-series analysis of any event, which is the foundation of product analytics. Without this, users cannot answer basic questions like "How many signups per day last month?" or "How do purchases differ by country?"

**Independent Test**: Can be fully tested by running a segmentation query for a specific event over a date range and verifying the result contains time-series data. Delivers immediate value by enabling trend analysis.

**Acceptance Scenarios**:

1. **Given** valid credentials and an event name, **When** the user runs a segmentation query with a date range, **Then** they receive time-series counts for that event organized by time unit (day/week/month).

2. **Given** valid credentials and an event name with a segment property, **When** the user runs a segmentation query with the "on" parameter set to a property name, **Then** they receive time-series counts broken down by each distinct value of that property.

3. **Given** valid credentials and an event name with a filter, **When** the user runs a segmentation query with a "where" clause, **Then** only events matching the filter are included in the counts.

4. **Given** segmentation results, **When** the user requests a tabular view, **Then** they receive a structured table with columns for date, segment, and count.

---

### User Story 2 - Run Funnel Analysis (Priority: P1)

Data analysts need to understand conversion through multi-step user flows. Funnel analysis shows how many users complete each step of a defined sequence and where users drop off.

**Why this priority**: Funnel analysis is essential for understanding conversion and identifying optimization opportunities. It's the second most critical query type after segmentation.

**Independent Test**: Can be fully tested by querying an existing funnel and verifying the result contains step-by-step conversion data. Delivers immediate value by enabling conversion analysis.

**Acceptance Scenarios**:

1. **Given** valid credentials and a funnel ID, **When** the user runs a funnel query with a date range, **Then** they receive step-by-step conversion data showing user counts and conversion rates at each step.

2. **Given** funnel results, **When** the user examines the overall conversion rate, **Then** they see the percentage of users who completed all steps from the first step.

3. **Given** funnel results, **When** the user requests a tabular view, **Then** they receive a structured table with columns for step number, event name, user count, and conversion rate from previous step.

---

### User Story 3 - Run Retention Analysis (Priority: P2)

Data analysts need to understand how well the product retains users over time. Retention analysis shows what percentage of users who performed a "born" event return to perform a "return" event in subsequent time periods.

**Why this priority**: Retention is critical for understanding product health and user engagement, but is less frequently used than segmentation and funnels. Still essential for growth analysis.

**Independent Test**: Can be fully tested by running a retention query with born and return events and verifying the result contains cohort retention percentages. Delivers value by enabling retention curve analysis.

**Acceptance Scenarios**:

1. **Given** valid credentials and born/return event names, **When** the user runs a retention query with a date range, **Then** they receive cohort-based retention data showing the percentage of users retained in each subsequent period.

2. **Given** retention query parameters, **When** the user specifies the time unit and interval count, **Then** the retention data is organized by that unit (day/week/month) for the specified number of periods.

3. **Given** retention results, **When** the user requests a tabular view, **Then** they receive a structured table with cohort date, cohort size, and retention percentages for each period.

---

### User Story 4 - Run Custom JQL Queries (Priority: P3)

Power users need to run custom queries when standard query types don't meet their needs. JQL (JavaScript Query Language) allows arbitrary queries against Mixpanel data.

**Why this priority**: JQL is a power-user feature for edge cases that standard queries can't handle. Most users will use segmentation, funnels, or retention instead.

**Independent Test**: Can be fully tested by executing a JQL script and verifying the result contains the query output. Delivers value by enabling custom analytics that aren't possible with standard queries.

**Acceptance Scenarios**:

1. **Given** valid credentials and a JQL script, **When** the user runs a JQL query, **Then** they receive the raw results of the script execution.

2. **Given** JQL results containing structured data, **When** the user requests a tabular view, **Then** they receive a structured table derived from the query output.

3. **Given** a JQL script with parameters, **When** the user provides parameter values, **Then** those values are substituted into the script before execution.

---

### Edge Cases

- What happens when the query date range has no data? (Return empty results with zero counts)
- What happens when authentication fails? (Propagate authentication error with clear message)
- What happens when the query parameters are invalid (e.g., invalid event name)? (Propagate query error with API error details)
- What happens when the API rate limit is exceeded? (Propagate rate limit error with retry information)
- What happens when the funnel ID doesn't exist? (Propagate query error indicating funnel not found)
- What happens when JQL script has syntax errors? (Propagate query error with script error details)

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST execute segmentation queries against Mixpanel and return structured time-series results
- **FR-002**: System MUST support segmentation by event property (the "on" parameter)
- **FR-003**: System MUST support filtering segmentation queries with a "where" clause
- **FR-004**: System MUST support multiple time units for segmentation: day, week, and month
- **FR-005**: System MUST execute funnel queries for saved funnels and return step-by-step conversion data
- **FR-006**: System MUST calculate overall funnel conversion rate from step data
- **FR-007**: System MUST execute retention queries with configurable born and return events
- **FR-008**: System MUST support retention filters for both born and return events
- **FR-009**: System MUST support configurable retention intervals and period counts
- **FR-010**: System MUST calculate retention percentages for each cohort and period
- **FR-011**: System MUST execute arbitrary JQL scripts and return raw results
- **FR-012**: System MUST support JQL parameter substitution
- **FR-013**: System MUST provide tabular views of all query results
- **FR-014**: System MUST propagate authentication errors from the underlying API
- **FR-015**: System MUST propagate query errors with meaningful error details
- **FR-016**: System MUST propagate rate limit errors with retry information

### Key Entities

- **Segmentation Result**: Time-series event counts, optionally segmented by property. Contains event name, date range, time unit, segment property (if any), total count, and series data mapping segments to date-count pairs.

- **Funnel Result**: Step-by-step conversion data for a saved funnel. Contains funnel identifier, funnel name, date range, overall conversion rate, and list of steps with event name, user count, and step conversion rate.

- **Funnel Step**: Single step in a funnel with event name, user count at that step, and conversion rate from the previous step.

- **Retention Result**: Cohort-based retention data. Contains born event, return event, date range, time unit, and list of cohorts.

- **Cohort Info**: Retention data for a single cohort with cohort date, cohort size, and list of retention percentages for each period.

- **JQL Result**: Raw results from JQL script execution with support for conversion to tabular format.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Users can retrieve segmentation data for any event within 5 seconds for typical date ranges (30 days)
- **SC-002**: All query result types provide accurate tabular representations that match the underlying data
- **SC-003**: 100% of API errors are surfaced to users with actionable error messages
- **SC-004**: Users can segment events by any property and receive correctly grouped results
- **SC-005**: Funnel results accurately reflect the conversion rates at each step as reported by the source system
- **SC-006**: Retention percentages are calculated correctly as the ratio of returning users to cohort size
- **SC-007**: JQL queries execute successfully and return results that match direct API execution

## Assumptions

- Users have valid Mixpanel credentials configured prior to using query features
- Saved funnels are pre-configured in Mixpanel before querying (this service queries existing funnels, not creates them)
- JQL scripts are syntactically correct - the service passes through JQL errors but doesn't validate scripts
- Query results are not cached by this service - each query executes against the live API
- Date formats follow Mixpanel convention (YYYY-MM-DD)
- The underlying API client handles rate limiting and retries transparently

## Dependencies

- Requires authenticated access to Mixpanel Query API (Phase 002 API Client)
- Result types must be pre-defined for type-safe returns
