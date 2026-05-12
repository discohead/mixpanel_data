# Feature Specification: Discovery & Query API Enhancements

**Feature Branch**: `007-discovery-enhancements`
**Created**: 2025-12-23
**Status**: Draft
**Input**: Extend Discovery Service and Live Query Service to provide complete coverage of Mixpanel Query API discovery and event breakdown endpoints

---

## Overview

This feature extends the existing project discovery and live query capabilities to provide complete coverage of Mixpanel's analytics exploration endpoints. The enhancements enable AI agents and analysts to:

1. **Discover project resources** — List saved funnels and cohorts before querying them
2. **Explore event activity** — See today's most active events with volume and trend data
3. **Analyze multi-event trends** — Query time-series counts for multiple events simultaneously
4. **Analyze property distributions** — Query time-series breakdowns by property values

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Discover Available Funnels (Priority: P1)

As an AI coding agent or analyst, I want to list all saved funnels in a project so that I can identify which funnels are available to query and understand the conversion flows already defined by the team.

**Why this priority**: Funnels are pre-configured conversion analyses critical for business metrics. Users must be able to discover existing funnels before querying them, making this foundational to funnel analysis workflows.

**Independent Test**: Can be fully tested by requesting a list of funnels for a project and verifying the response contains funnel identifiers and names that can be used in subsequent funnel queries.

**Acceptance Scenarios**:

1. **Given** valid project credentials, **When** I request the list of funnels, **Then** I receive a list of funnel entries sorted alphabetically by name.
2. **Given** a project with no saved funnels, **When** I request the list of funnels, **Then** I receive an empty list (not an error).
3. **Given** valid credentials, **When** I request funnels multiple times in the same session, **Then** subsequent requests return cached results without additional network delays.
4. **Given** each funnel entry in the response, **Then** it contains a unique funnel identifier and human-readable name.

---

### User Story 2 - Discover Available Cohorts (Priority: P1)

As an AI coding agent or analyst, I want to list all saved cohorts in a project so that I can identify which user segments are available for filtering profiles and targeting analyses.

**Why this priority**: Cohorts represent pre-defined user segments essential for targeted analysis. Users must discover existing cohorts before using them in profile filtering or engagement queries.

**Independent Test**: Can be fully tested by requesting a list of cohorts for a project and verifying the response contains cohort details usable for profile filtering.

**Acceptance Scenarios**:

1. **Given** valid project credentials, **When** I request the list of cohorts, **Then** I receive a list of cohort entries sorted alphabetically by name.
2. **Given** a project with no saved cohorts, **When** I request the list of cohorts, **Then** I receive an empty list (not an error).
3. **Given** valid credentials, **When** I request cohorts multiple times in the same session, **Then** subsequent requests return cached results.
4. **Given** each cohort entry in the response, **Then** it contains: unique identifier, name, user count, description, creation date, and visibility status.

---

### User Story 3 - Explore Today's Top Events (Priority: P2)

As an AI coding agent or analyst, I want to see today's most active events with counts and trends so that I can quickly understand current activity patterns and identify what's happening right now.

**Why this priority**: Real-time activity awareness helps users quickly orient themselves in a project's data. While valuable for exploration, it's not a prerequisite for other queries.

**Independent Test**: Can be fully tested by requesting today's top events and verifying the response shows event names, counts, and trend indicators.

**Acceptance Scenarios**:

1. **Given** valid credentials, **When** I request today's top events, **Then** I receive a list of events with activity data.
2. **Given** each event entry, **Then** it contains: event name, today's count, and percentage change versus yesterday.
3. **Given** the real-time nature of this data, **When** I request top events, **Then** results are always fetched fresh (not cached).
4. **Given** optional counting method (total/unique/average), **When** I specify it, **Then** the appropriate metric is returned.
5. **Given** optional result limit, **When** I specify it, **Then** at most that many events are returned.

---

### User Story 4 - Analyze Multi-Event Time Series (Priority: P2)

As an AI coding agent or analyst, I want to query aggregate counts for multiple events over a date range so that I can compare event volumes over time on a single view.

**Why this priority**: Multi-event comparison enables trend analysis and correlation discovery across different user actions. Important for data exploration but builds on basic discovery capabilities.

**Independent Test**: Can be fully tested by requesting counts for multiple events over a date range and verifying the response contains time-series data for each event.

**Acceptance Scenarios**:

1. **Given** a list of event names and date range, **When** I request event counts, **Then** I receive time-series data for each event.
2. **Given** the response, **Then** it contains counts organized by event name and date.
3. **Given** the response, **Then** it can be converted to a tabular format with columns: date, event, count.
4. **Given** optional time unit (day/week/month), **When** I specify it, **Then** data is aggregated accordingly.
5. **Given** optional counting method (total/unique/average), **When** I specify it, **Then** the appropriate metric is returned.

---

### User Story 5 - Analyze Property Value Distributions Over Time (Priority: P2)

As an AI coding agent or analyst, I want to query aggregate counts broken down by property values over time so that I can analyze how a metric varies across different segments.

**Why this priority**: Property-based segmentation reveals patterns in user behavior by category (e.g., by platform, country, plan type). Essential for detailed analysis but requires prior event/property discovery.

**Independent Test**: Can be fully tested by requesting property breakdown for an event over a date range and verifying the response segments counts by property values.

**Acceptance Scenarios**:

1. **Given** an event name, property name, and date range, **When** I request property counts, **Then** I receive time-series data segmented by property values.
2. **Given** the response, **Then** it contains counts organized by property value and date.
3. **Given** the response, **Then** it can be converted to a tabular format with columns: date, value, count.
4. **Given** optional list of specific property values, **When** specified, **Then** only those values are included in results.
5. **Given** optional result limit, **When** specified, **Then** at most that many property values are included.

---

### Edge Cases

- **Empty project**: Requests for funnels, cohorts, or top events on a project with no data return empty lists, not errors.
- **No events in date range**: Time-series queries for a date range with no matching events return results with empty series, not errors.
- **Invalid credentials**: All operations return a clear authentication error when credentials are invalid.
- **Rate limiting**: If the service is rate-limited, operations automatically retry with appropriate delays before surfacing an error.
- **Property with no values**: Property count queries for properties with no recorded values return results with empty series.

---

## Requirements *(mandatory)*

### Functional Requirements

**Discovery Operations**

- **FR-001**: System MUST provide a way to list all saved funnels in a project, returning funnel identifier and name for each.
- **FR-002**: System MUST provide a way to list all saved cohorts in a project, returning identifier, name, user count, description, creation date, and visibility status for each.
- **FR-003**: System MUST provide a way to list today's top events with count and trend data.
- **FR-004**: Funnel and cohort listings MUST be cached within a session to avoid redundant requests.
- **FR-005**: Today's top events MUST NOT be cached (data changes throughout the day).
- **FR-006**: All discovery list results MUST be sorted alphabetically by name.

**Query Operations**

- **FR-007**: System MUST provide a way to query aggregate counts for multiple events over a specified date range.
- **FR-008**: System MUST provide a way to query aggregate counts broken down by property values over a specified date range.
- **FR-009**: Time-series query results MUST support conversion to tabular format for analysis.
- **FR-010**: Query operations MUST NOT be cached (live data should always be fresh).

**Configuration Options**

- **FR-011**: Top events listing MUST support optional counting method selection (total, unique, average).
- **FR-012**: Top events listing MUST support optional result limit.
- **FR-013**: Event count queries MUST support optional time unit selection (day, week, month).
- **FR-014**: Event count queries MUST support optional counting method selection.
- **FR-015**: Property count queries MUST support optional filtering to specific property values.
- **FR-016**: Property count queries MUST support optional result limit for property values.

**Error Handling**

- **FR-017**: System MUST return clear authentication errors when credentials are invalid.
- **FR-018**: System MUST handle rate limiting with automatic retry and backoff.
- **FR-019**: System MUST return empty results (not errors) when no data matches the query criteria.

---

### Key Entities

- **Funnel Info**: Represents a saved funnel definition. Contains a unique identifier (for use in funnel queries) and a human-readable name.

- **Saved Cohort**: Represents a saved user segment. Contains identifier, name, current user count, optional description, creation timestamp, and visibility flag.

- **Top Event**: Represents an event's current activity. Contains event name, today's count, and percentage change compared to yesterday (-100% to +infinity).

- **Event Counts Result**: Represents time-series event data. Contains list of queried events, date range, aggregation unit, and series data mapping each event to date-count pairs. Supports tabular conversion.

- **Property Counts Result**: Represents time-series property breakdown data. Contains event name, property name, date range, aggregation unit, and series data mapping each property value to date-count pairs. Supports tabular conversion.

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Users can list all funnels in a project with a single request, receiving results in under 2 seconds.
- **SC-002**: Users can list all cohorts in a project with a single request, receiving results in under 2 seconds.
- **SC-003**: Users can view today's top events with counts and trends in under 2 seconds.
- **SC-004**: Users can query time-series counts for up to 10 events simultaneously.
- **SC-005**: Users can query property value distributions for any event property.
- **SC-006**: All time-series results can be converted to tabular format for further analysis.
- **SC-007**: Cached discovery operations (funnels, cohorts) respond instantly on subsequent requests within the same session.
- **SC-008**: 100% of operations return empty results (not errors) when no data matches criteria.
- **SC-009**: All 5 new capabilities pass automated verification tests.

---

## Dependencies

- Existing project discovery capabilities (event listing, property listing, property value sampling)
- Existing live query capabilities (segmentation, funnel, retention queries)
- Valid project credentials with appropriate permissions

---

## Assumptions

- **A-1**: Funnel and cohort definitions change infrequently, making session-scoped caching appropriate.
- **A-2**: Today's top events data changes frequently throughout the day, requiring fresh fetches.
- **A-3**: Time-series query results should support tabular conversion for analysis workflows.
- **A-4**: Discovery operations (listing resources) are distinct from query operations (analyzing data over time).
- **A-5**: All new operations follow the same credential and error handling patterns as existing capabilities.

---

## Out of Scope

- Creating, modifying, or deleting funnels or cohorts (read-only discovery only)
- Timeline annotations
- Data pipeline management
- Schema/lexicon management
- Profile property discovery (separate from event property discovery)
