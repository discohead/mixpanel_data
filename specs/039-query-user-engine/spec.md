# Feature Specification: User Profile Query Engine

**Feature Branch**: `039-query-user-engine`  
**Created**: 2026-04-13  
**Status**: Draft  
**Input**: User description: "query_user() Design Document - The 5th Query Engine"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Query and Filter User Profiles (Priority: P1)

An analyst wants to find users matching specific criteria and examine their profile data. They use the same filtering vocabulary they already know from other query engines (insights, funnels, retention, flows) to query individual user records. The system returns structured tabular results showing profile properties like email, plan, city, and lifetime value.

**Why this priority**: This is the core capability. Without profile querying, no other user-level analysis is possible. It bridges the gap between aggregated analytics ("how many users did X?") and individual-level understanding ("which users match these criteria and what do I know about them?").

**Independent Test**: Can be fully tested by filtering users with property criteria and verifying the returned records contain correct profile data in tabular format. Delivers immediate value for user lookup, segmentation analysis, and data exploration.

**Acceptance Scenarios**:

1. **Given** a project with user profiles, **When** the analyst queries for users matching a property filter (e.g., plan equals "premium"), **Then** the system returns matching user records as a table with distinct ID, last seen timestamp, and requested properties.
2. **Given** a query with no explicit result limit, **When** the query executes, **Then** the system returns 1 sample profile with `total=1` (safe default to prevent unbounded data transfer). Use `mode='aggregate', aggregate='count'` for the full population count.
3. **Given** a query with an explicit limit of 500, **When** the query executes, **Then** the system returns at most 500 profiles with `total` equal to `len(profiles)`.
4. **Given** a query requesting specific properties (e.g., email, plan, LTV), **When** the query executes, **Then** only the requested properties appear in the result columns (plus distinct ID and last seen, which are always included).
5. **Given** a query with sort criteria (e.g., sort by LTV descending), **When** the query executes, **Then** results are ordered by the specified property in the specified direction.
6. **Given** a full-text search term, **When** the query executes, **Then** results are filtered to profiles containing the search term across searchable fields.
7. **Given** a specific distinct ID or list of distinct IDs, **When** the query executes, **Then** the system returns only those specific user profiles.
8. **Given** a group identifier (e.g., "companies"), **When** the query executes, **Then** the system returns group-level profiles instead of user profiles.
9. **Given** a point-in-time date, **When** the query executes, **Then** the system returns profile state as it existed at that historical point.

---

### User Story 2 - Compute Aggregate Statistics Across Profiles (Priority: P2)

An analyst wants to answer questions like "how many premium users do we have?", "what is the average LTV?", or "what are the min/max ages?" without fetching individual records. The system computes aggregate statistics (count, extremes, percentile, numeric_summary) across all matching profiles and returns a concise summary.

**Why this priority**: Aggregate analytics complement profile listing. Many analytical questions need population-level statistics rather than individual records. This avoids the overhead of fetching thousands of profiles just to compute a count or average.

**Independent Test**: Can be tested by requesting a count of users matching a filter and verifying the returned scalar value matches expectations. Delivers value for quick population sizing and metric computation.

**Acceptance Scenarios**:

1. **Given** a set of filter criteria, **When** the analyst requests a count, **Then** the system returns the total number of matching profiles as a single value.
2. **Given** a numeric property (e.g., LTV) and a set of filter criteria, **When** the analyst requests a numeric_summary, **Then** the system returns count, mean, and variance of that property across matching profiles.
3. **Given** a numeric property, **When** the analyst requests extremes or percentile, **Then** the system returns the corresponding aggregate value(s).
4. **Given** aggregate criteria and a list of cohort IDs for segmentation, **When** the query executes, **Then** the system returns the aggregate value broken down by each cohort segment in tabular form.
5. **Given** a request for sum/mean/min/max without specifying which property to aggregate, **When** the query is submitted, **Then** the system rejects the query with a clear validation error before any data is fetched.

---

### User Story 3 - Filter Users by Behavioral Criteria (Priority: P2)

An analyst wants to find users based on their actions (e.g., "users who purchased at least 3 times in the last 30 days") using fully typed criteria rather than raw query strings. The system accepts behavioral criteria expressed through a structured builder and routes them correctly to the underlying platform.

**Why this priority**: Behavioral filtering is essential for advanced segmentation and is one of the most common analyst workflows. Typed criteria prevent errors and hallucination risks when AI agents construct queries programmatically.

**Independent Test**: Can be tested by defining a behavioral cohort (e.g., users who performed an event N times within a time window) and verifying returned profiles match the criteria. Delivers value for behavioral analysis and targeted user identification.

**Acceptance Scenarios**:

1. **Given** behavioral criteria specifying an event, minimum occurrence count, and time window, **When** the query executes, **Then** only users matching the behavioral criteria are returned.
2. **Given** multiple behavioral criteria combined with AND logic (e.g., purchased 3+ times AND viewed pricing page), **When** the query executes, **Then** only users satisfying all criteria are returned.
3. **Given** multiple behavioral criteria combined with OR logic (e.g., purchased OR added to cart), **When** the query executes, **Then** users satisfying any of the criteria are returned.
4. **Given** a saved cohort ID, **When** used as a filter, **Then** only members of that cohort are returned.
5. **Given** both a cohort filter and a separate property filter in the same query, **When** the system detects conflicting cohort specifications, **Then** the query is rejected with a clear validation error.

---

### User Story 4 - Retrieve Large Profile Sets Efficiently (Priority: P3)

An analyst needs to fetch thousands of user profiles (e.g., all premium users for a DataFrame analysis). The system supports concurrent retrieval across multiple pages, reducing total fetch time by up to 5x compared to sequential retrieval.

**Why this priority**: Large-scale profile retrieval is a common need for analysis and data export, but the underlying platform paginates results. Parallel fetching significantly improves the experience without requiring the analyst to manage pagination manually.

**Independent Test**: Can be tested by requesting 5,000+ profiles with parallel mode enabled and measuring that retrieval completes significantly faster than sequential mode. Delivers value for bulk analysis and data export workflows.

**Acceptance Scenarios**:

1. **Given** a query for 10,000 profiles with parallel mode enabled, **When** the query executes, **Then** the system fetches pages concurrently and returns all profiles as a single result set.
2. **Given** a parallel query where one page fails, **When** the remaining pages succeed, **Then** the system returns partial results and reports failed pages in the result metadata.
3. **Given** a query where a single page of results satisfies the request, **When** parallel mode is enabled, **Then** the system completes normally without unnecessary parallel overhead.
4. **Given** a query requiring more than 48 pages, **When** the system detects this, **Then** it warns about approaching the platform's rate limit.

---

### User Story 5 - Compose Profile Queries with Other Analytics (Priority: P3)

An analyst runs a segmentation or funnel query to identify interesting patterns, then drills down into the user profiles behind those patterns. The profile query results compose naturally with other engine outputs through shared identifiers and tabular data operations.

**Why this priority**: The value of a unified query system is composition. Profile queries become dramatically more useful when combined with insights from other engines (e.g., "show me the profiles of users who dropped off at step 3 of the onboarding funnel").

**Independent Test**: Can be tested by running an insights query, extracting a segment value, and using it as a filter in a profile query. Delivers value by connecting aggregated analytics to individual-level understanding.

**Acceptance Scenarios**:

1. **Given** results from an insights query identifying the top-performing plan, **When** the analyst uses that plan value as a filter in a profile query, **Then** the system returns profiles matching that plan with full property details.
2. **Given** a saved cohort representing a funnel step, **When** the analyst queries profiles filtered by that cohort, **Then** the result includes profile data for users who reached that funnel step.
3. **Given** profile query results, **When** the analyst accesses the list of distinct IDs, **Then** those IDs can be used for downstream operations or cross-referenced with other data sources.

---

### Edge Cases

- What happens when a query matches zero profiles? The system returns an empty result set with total count of 0.
- What happens when the user requests a property that doesn't exist on any profile? The column appears in results with missing/null values.
- What happens when `limit=None` is set on a project with millions of profiles? The system fetches all matching profiles via pagination (explicit opt-in required).
- What happens when both a direct cohort filter and a cohort-based property filter are specified in the same query? The system rejects the query with a validation error before execution.
- What happens when an aggregate function other than "count" is requested without specifying a property? The system rejects the query with a validation error.
- What happens when sort or search parameters are used with aggregate mode? The system rejects the query with a validation error (these only apply to profile listing mode).
- What happens when the parallel worker count exceeds the platform's concurrency limit? The system rejects the query with a validation error (U23: workers must be between 1 and 5).
- What happens when a point-in-time date is in the future? The system rejects the query with a validation error.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST accept the same filter vocabulary used by other query engines (insights, funnels, retention, flows) for filtering user profiles by property values.
- **FR-002**: System MUST return profile query results as structured tabular data with one row per user, consistent with the result format of other query engines.
- **FR-003**: System MUST default to returning 1 sample profile with `total=1` when no explicit limit is specified (safe default).
- **FR-004**: System MUST support selecting specific output properties to control which columns appear in the result and reduce response size.
- **FR-005**: System MUST support sorting results by a profile property in ascending or descending order.
- **FR-006**: System MUST support full-text search across profile fields.
- **FR-007**: System MUST support looking up specific users by distinct ID (single or batch).
- **FR-008**: System MUST support filtering by saved cohort ID.
- **FR-009**: System MUST support filtering by inline behavioral criteria expressed through the typed cohort definition builder (no raw query strings).
- **FR-010**: System MUST support querying group-level profiles (e.g., companies, accounts) in addition to user profiles.
- **FR-011**: System MUST support point-in-time queries to retrieve historical profile state.
- **FR-012**: System MUST support aggregate mode returning count, extremes, percentile, or numeric_summary across matching profiles.
- **FR-013**: System MUST support cohort-segmented aggregation, breaking down aggregate values by cohort membership.
- **FR-014**: System MUST support concurrent page fetching for large result sets with configurable worker count (capped at platform limit).
- **FR-015**: System MUST validate all inputs before executing any query, collecting all validation errors and reporting them together.
- **FR-016**: System MUST enforce mutual exclusions between conflicting parameters (e.g., single distinct ID vs. batch, cohort filter vs. inline cohort in property filters).
- **FR-017**: System MUST enforce mode-specific parameter restrictions (e.g., sort/search/limit only in profile mode; aggregate property only in aggregate mode).
- **FR-018**: System MUST provide a parameter preview capability that generates the query parameters without executing the query.
- **FR-019**: System MUST include `total` in the result, equal to `len(profiles)` (the number of profiles actually returned).
- **FR-020**: System MUST normalize built-in property names in tabular output by stripping the `$` prefix (e.g., `$email` becomes `email`).
- **FR-021**: System MUST handle partial failures in parallel mode gracefully, returning successfully fetched results with failed pages reported in metadata.
- **FR-022**: System MUST expose the result type as a public export from the library.

### Key Entities

- **UserQueryResult**: The result container for profile queries. Contains the count of returned profiles (`total = len(profiles)`), a list of normalized profile records, query parameters used, execution metadata, and mode-aware tabular data access. For aggregate mode, contains the computed statistic value(s) instead of individual profiles.
- **Filter**: The unified filter type shared across all query engines. Supports property comparisons (equals, not equals, greater than, less than, between, contains), existence checks (is set, is not set), boolean checks, and cohort membership.
- **CohortDefinition**: A typed builder for expressing behavioral and property-based cohort criteria with AND/OR composition. Used for inline behavioral filtering without raw query strings.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Analysts can query user profiles using the identical filter syntax they use for insights, funnels, retention, and flow queries, with zero new syntax to learn for basic filtering.
- **SC-002**: A bare query with no parameters returns a total count and 1 sample profile in a single lightweight operation, making it safe and cheap to call without configuration.
- **SC-003**: Aggregate statistics (count, extremes, percentile, numeric_summary) across matching profiles are available in a single query call without fetching individual records.
- **SC-004**: Large profile retrievals (5,000+ records) complete up to 5x faster with parallel fetching compared to sequential retrieval.
- **SC-005**: All input validation errors are caught and reported before any data is fetched from the platform, preventing wasted API calls.
- **SC-006**: Profile query results compose naturally with other engine outputs through shared identifiers and standard tabular data operations.
- **SC-007**: 100% of validation rules have corresponding automated tests, and all query modes (profile listing, aggregate, parallel) have integration-level test coverage.
- **SC-008**: The feature achieves at least 90% code coverage and 80% mutation testing score, consistent with project quality standards.

## Assumptions

- Users have an active Mixpanel project with user profile data and valid authentication credentials configured.
- The existing `stream_profiles()` method and underlying API client infrastructure (pagination, rate limiting, exponential backoff) are stable and reusable.
- The existing `Filter` type and `CohortDefinition` builder are complete and their serialization formats are compatible with the engage API's `where` and `filter_by_cohort` parameters respectively.
- The platform's engage API rate limit of 60 queries/hour and max 5 concurrent queries are hard constraints that cannot be changed.
- The `$` prefix stripping for built-in property names in tabular output is the correct default for ergonomics; users needing raw names can access the underlying profile list directly.
- Cohort segment identifiers in aggregate results use the cohort ID format (e.g., `cohort_123`) rather than looking up cohort names, for simplicity and reliability.
- Partial results with failed page metadata are preferable to failing the entire query when individual pages fail during parallel fetching.
