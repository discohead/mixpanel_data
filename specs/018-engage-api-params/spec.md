# Feature Specification: Engage API Full Parameter Support

**Feature Branch**: `018-engage-api-params`
**Created**: 2026-01-04
**Status**: Draft
**Input**: User description: "Add support for missing Mixpanel Engage Query API parameters: distinct_id, distinct_ids, data_group_id, behaviors, as_of_timestamp, and include_all_users"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Fetch Specific Profiles by ID (Priority: P1)

As a data analyst, I want to fetch specific user profiles by their distinct ID(s) so that I can retrieve targeted profile data without querying the entire user base.

**Why this priority**: This is the most common use case for profile queries. Analysts frequently need to look up specific users for debugging, customer support, or targeted analysis rather than scanning all profiles.

**Independent Test**: Can be fully tested by fetching a known user's profile by ID and verifying the correct profile data is returned.

**Acceptance Scenarios**:

1. **Given** a valid distinct_id, **When** I request that profile, **Then** I receive the profile data for that specific user
2. **Given** a list of distinct_ids, **When** I request those profiles, **Then** I receive profile data for all specified users in a single response
3. **Given** I specify both distinct_id and distinct_ids, **When** I submit the request, **Then** the system rejects the request with a clear error explaining these are mutually exclusive
4. **Given** a distinct_id that doesn't exist, **When** I request that profile, **Then** I receive an empty result set (not an error)

---

### User Story 2 - Query Group Profiles (Priority: P2)

As a B2B product analyst, I want to query group profiles (companies, accounts, organizations) so that I can analyze account-level data separately from individual user data.

**Why this priority**: Group analytics is essential for B2B products but applies to a subset of Mixpanel users who have configured group analytics.

**Independent Test**: Can be fully tested by specifying a group type (e.g., "companies") and verifying that group profiles are returned instead of user profiles.

**Acceptance Scenarios**:

1. **Given** a valid data_group_id (e.g., "companies"), **When** I query profiles, **Then** I receive group profiles for that entity type
2. **Given** an invalid data_group_id, **When** I query profiles, **Then** I receive a clear error indicating the group type is not recognized
3. **Given** a data_group_id with filtering criteria, **When** I query, **Then** the filter applies to group profiles correctly

---

### User Story 3 - Filter Profiles by Event Behavior (Priority: P2)

As a growth analyst, I want to filter profiles based on user behavior (events they performed) so that I can segment users by their actions (e.g., "users who completed onboarding in the last 7 days").

**Why this priority**: Behavior-based segmentation is a core analytics capability, enabling powerful user cohort analysis based on actual product usage.

**Independent Test**: Can be fully tested by specifying a behavior filter expression and verifying only profiles matching that behavior criteria are returned.

**Acceptance Scenarios**:

1. **Given** a behavior filter expression, **When** I query profiles, **Then** only profiles matching the behavior criteria are returned
2. **Given** I specify both behaviors and cohort_id, **When** I submit the request, **Then** the system rejects with a clear error explaining these are mutually exclusive
3. **Given** a behavior query returning more than 1000 profiles, **When** pagination is needed, **Then** the system requires as_of_timestamp for consistent pagination
4. **Given** an as_of_timestamp value, **When** I paginate through behavior-filtered results, **Then** the results are consistent across pages

---

### User Story 4 - Control Cohort Profile Inclusion (Priority: P3)

As a data analyst using cohort filtering, I want to control whether cohort members without profile data are included in results so that I can choose between complete cohort membership lists versus only users with profile attributes.

**Why this priority**: This is an edge case refinement for cohort filtering, which is already supported. It affects a subset of cohort queries where some members lack profile data.

**Independent Test**: Can be fully tested by querying a cohort with known members lacking profiles and verifying inclusion/exclusion based on the flag.

**Acceptance Scenarios**:

1. **Given** a cohort with some members lacking profiles and include_all_users=true, **When** I query, **Then** all cohort members appear (even those without profile data)
2. **Given** a cohort with some members lacking profiles and include_all_users=false, **When** I query, **Then** only cohort members with profile data appear
3. **Given** include_all_users specified without cohort_id, **When** I submit the request, **Then** the system rejects with a clear error explaining include_all_users requires cohort filtering
4. **Given** no include_all_users specified with cohort_id, **When** I query, **Then** the default behavior includes all users (API default)

---

### Edge Cases

- What happens when distinct_ids list is empty? System should return empty results, not error.
- What happens when distinct_ids list contains duplicates? System should handle gracefully (dedupe or return duplicates based on API behavior).
- What happens when behaviors expression is syntactically invalid? System should return a clear validation error.
- How does pagination work when fetching by distinct_ids? With a fixed list, pagination should iterate through the specified IDs only.
- What happens when as_of_timestamp is in the future? API should reject or use current time.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST allow fetching a single profile by specifying distinct_id
- **FR-002**: System MUST allow fetching multiple profiles by specifying a list of distinct_ids
- **FR-003**: System MUST reject requests specifying both distinct_id and distinct_ids with a clear error message
- **FR-004**: System MUST serialize distinct_ids as a JSON array in API requests
- **FR-005**: System MUST allow querying group profiles by specifying data_group_id (maps to group_id in user-facing interfaces)
- **FR-006**: System MUST support behavior-based profile filtering via a behaviors expression parameter
- **FR-007**: System MUST reject requests specifying both behaviors and cohort_id with a clear error message
- **FR-008**: System MUST support as_of_timestamp parameter for consistent pagination with behavior filtering
- **FR-009**: System MUST support include_all_users parameter for cohort filtering
- **FR-010**: System MUST reject include_all_users when cohort_id is not specified
- **FR-011**: All new parameters MUST be available across all interface layers (library API and command-line interface)
- **FR-012**: System MUST provide appropriate default values matching Mixpanel API defaults

### Key Entities

- **Profile**: A user or group profile containing properties/attributes stored in Mixpanel
- **Distinct ID**: Unique identifier for a user profile
- **Group Profile**: A non-user entity profile (company, account, organization) identified by data_group_id
- **Behavior Filter**: An expression describing event-based criteria for profile selection (similar to existing "where" filter syntax)
- **Cohort**: A predefined segment of users, referenced by cohort_id

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Users can retrieve a specific profile by ID in a single request without scanning all profiles
- **SC-002**: Users can retrieve up to 2000 profiles by ID list in a single request
- **SC-003**: Users can query group profiles (companies, accounts) with the same filtering capabilities as user profiles
- **SC-004**: Users can filter profiles by behavior expressions with consistent pagination for large result sets
- **SC-005**: Users can control cohort member inclusion when some members lack profile data
- **SC-006**: All new parameters are documented and accessible via both library and CLI interfaces
- **SC-007**: Invalid parameter combinations produce clear, actionable error messages within 1 second
- **SC-008**: Existing profile query functionality remains unaffected (no breaking changes)

## Assumptions

- The behaviors parameter follows the same selector syntax as existing "where" and "on" parameters in the codebase
- Mixpanel API documentation accurately describes parameter behavior and constraints
- The API's default for include_all_users is true (include all cohort members)
- Maximum distinct_ids list size follows Mixpanel API limits (assumed reasonable limit, not requiring local validation)
- as_of_timestamp uses Unix epoch format consistent with other Mixpanel timestamp parameters
