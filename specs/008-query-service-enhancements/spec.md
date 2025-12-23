# Feature Specification: Query Service Enhancements

**Feature Branch**: `008-query-service-enhancements`
**Created**: 2024-12-23
**Status**: Draft
**Input**: Extend the Live Query Service with 6 additional Mixpanel Query API endpoints: activity feed (user event history), insights (saved reports), frequency analysis, numeric bucketing, numeric sum, and numeric average

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Query User Activity Feed (Priority: P1)

As an AI coding agent debugging user-specific issues, I want to retrieve a user's complete event history so that I can understand their journey and identify problems.

**Why this priority**: Activity feeds are essential for debugging individual user issues and building customer success timelines. This is the most common use case for user-level analysis.

**Independent Test**: Can be fully tested by querying activity for a known user ID and verifying the returned events match their expected history.

**Acceptance Scenarios**:

1. **Given** a valid distinct_id, **When** I query the activity feed, **Then** I receive a chronologically ordered list of events for that user
2. **Given** multiple distinct_ids, **When** I query the activity feed, **Then** I receive combined events for all specified users
3. **Given** a date range, **When** I query the activity feed, **Then** I receive only events within that date range
4. **Given** a user with no events, **When** I query the activity feed, **Then** I receive an empty result without error

---

### User Story 2 - Sum Numeric Property Values (Priority: P1)

As an AI coding agent tracking revenue or quantities, I want to sum numeric property values over time so that I can calculate daily totals.

**Why this priority**: Summing values like revenue, items purchased, or points earned is a fundamental analytics operation for business metrics.

**Independent Test**: Can be fully tested by summing a known numeric property (e.g., purchase amount) and verifying daily totals match expected values.

**Acceptance Scenarios**:

1. **Given** an event with a numeric property, **When** I request a sum, **Then** I receive daily totals for that property
2. **Given** hourly granularity requested, **When** I request a sum, **Then** I receive hourly totals instead of daily
3. **Given** a filter expression, **When** I request a sum, **Then** only matching events are included in the sum
4. **Given** events with non-numeric values for the property, **When** I request a sum, **Then** those events contribute zero to the total

---

### User Story 3 - Average Numeric Property Values (Priority: P1)

As a data analyst tracking mean metrics, I want to average numeric property values over time so that I can understand typical values per time period.

**Why this priority**: Averages complement sums for complete numeric analysis (average order value, average session duration, etc.).

**Independent Test**: Can be fully tested by averaging a known numeric property and verifying daily averages match expected calculations.

**Acceptance Scenarios**:

1. **Given** an event with a numeric property, **When** I request an average, **Then** I receive daily averages for that property
2. **Given** hourly granularity requested, **When** I request an average, **Then** I receive hourly averages instead of daily
3. **Given** a filter expression, **When** I request an average, **Then** only matching events are included in the average
4. **Given** events with non-numeric values for the property, **When** I request an average, **Then** those events are excluded from the calculation

---

### User Story 4 - Analyze Event Frequency (Priority: P1)

As an AI coding agent measuring engagement depth, I want to understand how frequently users perform events so that I can identify power users versus casual users.

**Why this priority**: Frequency analysis reveals engagement patterns that simple event counts cannot show.

**Independent Test**: Can be fully tested by querying frequency data for a known event and verifying the distribution matches expected user behavior patterns.

**Acceptance Scenarios**:

1. **Given** a date range and granularity settings, **When** I query frequency, **Then** I receive a distribution showing how many users performed the event N times
2. **Given** an event filter, **When** I query frequency, **Then** only that event's frequency is analyzed
3. **Given** a property segmentation, **When** I query frequency, **Then** frequency distributions are broken down by that property
4. **Given** no events in the date range, **When** I query frequency, **Then** I receive an empty distribution without error

---

### User Story 5 - Bucket Events by Numeric Properties (Priority: P2)

As a data analyst understanding value distributions, I want to segment events by numeric property ranges so that I can see how values cluster.

**Why this priority**: Numeric bucketing provides distribution insights but is less commonly needed than direct sums/averages.

**Independent Test**: Can be fully tested by bucketing a known numeric property and verifying the bucket ranges and counts match expected distributions.

**Acceptance Scenarios**:

1. **Given** an event with a numeric property, **When** I request numeric bucketing, **Then** I receive event counts grouped into automatically determined ranges
2. **Given** different counting types (general, unique, average), **When** I request bucketing, **Then** the counts reflect the specified counting method
3. **Given** a filter expression, **When** I request bucketing, **Then** only matching events are included in buckets
4. **Given** a property with widely varying values, **When** I request bucketing, **Then** ranges are appropriately scaled

---

### User Story 6 - Query Saved Insights Reports (Priority: P2)

As a data analyst automating report extraction, I want to programmatically access pre-configured Insights reports so that I can build dashboards from saved queries.

**Why this priority**: Requires knowing the bookmark ID in advance, making it secondary to ad-hoc queries for most use cases.

**Independent Test**: Can be fully tested by querying a known saved report by bookmark ID and verifying the returned data matches the saved report configuration.

**Acceptance Scenarios**:

1. **Given** a valid bookmark ID, **When** I query the insights report, **Then** I receive the time-series data from that saved report
2. **Given** an invalid bookmark ID, **When** I query the insights report, **Then** I receive an appropriate error
3. **Given** a saved report with multiple events, **When** I query, **Then** I receive series data for all events in the report

---

### Edge Cases

- What happens when the activity feed request includes an invalid distinct_id format?
- How does the system handle API rate limiting during large activity feed requests?
- What happens when a saved Insights report has been deleted?
- How are null or missing numeric values treated in sum and average calculations?
- What happens when the date range spans no data for frequency analysis?
- How does numeric bucketing handle extreme outliers in the data?

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST provide an activity feed query that accepts one or more distinct_ids and optional date range
- **FR-002**: System MUST return activity feed events as structured objects with event name, timestamp, and properties
- **FR-003**: System MUST provide an insights query that accepts a bookmark ID for saved reports
- **FR-004**: System MUST return insights data including computed timestamp, date range, headers, and time-series data
- **FR-005**: System MUST provide a frequency query that accepts date range, overall period unit, and granularity unit
- **FR-006**: System MUST return frequency data as a distribution array showing user counts at each frequency level
- **FR-007**: System MUST provide numeric bucketing that accepts an event, date range, and numeric property expression
- **FR-008**: System MUST automatically determine appropriate bucket ranges for numeric values
- **FR-009**: System MUST provide numeric sum aggregation that accepts an event, date range, and numeric property expression
- **FR-010**: System MUST return sum results as date-to-value mappings
- **FR-011**: System MUST provide numeric average aggregation with the same parameters as sum
- **FR-012**: System MUST return average results as date-to-value mappings
- **FR-013**: All query results MUST be convertible to tabular format for analysis
- **FR-014**: All query results MUST be serializable for programmatic use
- **FR-015**: System MUST support filtering via expression syntax on all applicable queries
- **FR-016**: System MUST support hourly or daily granularity for numeric and bucketing queries
- **FR-017**: System MUST validate parameter types at query time (e.g., unit values restricted to valid options)
- **FR-018**: System MUST map API errors to appropriate error types (authentication, rate limit, query errors)

### Key Entities

- **UserEvent**: Represents a single event in a user's activity feed - contains event name, timestamp, and properties dictionary
- **ActivityFeedResult**: Collection of user events with query metadata (distinct_ids, date range)
- **InsightsResult**: Saved report data with computation metadata and time-series by event
- **FrequencyResult**: Distribution data showing user counts at each frequency level per date
- **NumericBucketResult**: Event counts grouped by automatically determined numeric ranges per date
- **NumericSumResult**: Daily or hourly sum values for a numeric expression
- **NumericAverageResult**: Daily or hourly average values for a numeric expression

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: All 6 new query methods return typed results that can be converted to tabular format
- **SC-002**: Query results include all metadata needed to understand the data context (dates, parameters used, computation time where applicable)
- **SC-003**: Invalid parameters are rejected with clear error messages before making external API calls
- **SC-004**: All existing library functionality continues to work without regression
- **SC-005**: Each query method handles empty results gracefully without errors
- **SC-006**: Query methods support all documented parameter combinations from the underlying API

## Assumptions

- The underlying Mixpanel API endpoints are stable and match the documented behavior
- Activity feed queries may be rate-limited for users with extensive event histories
- Saved Insights reports retain their bookmark IDs unless explicitly deleted
- Numeric bucketing range determination is handled by the API, not the library
- Non-numeric values in numeric fields are treated as zero for sums and excluded from averages
- The library operates as a thin layer over the API without local caching for these live queries

## Dependencies

- Phase 002 (API Client): HTTP request infrastructure must be in place
- Phase 006 (Live Query Service): Existing patterns and service structure to follow

## Out of Scope

- Workspace facade integration (separate phase)
- CLI commands for new methods (separate phase)
- Caching for any of these endpoints (live data only)
- Profile/Engage query enhancements
- Custom bucket range specification (API determines ranges)
