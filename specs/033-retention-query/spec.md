# Feature Specification: Retention Query (`query_retention()`)

**Feature Branch**: `033-retention-query`  
**Created**: 2026-04-06  
**Status**: Draft  
**Input**: Phase 3 of the Unified Bookmark Query System — add typed retention querying to `mixpanel_data`, following the same architecture as the existing `query()` (insights) and `query_funnel()` (funnels) methods.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Simple Retention Query (Priority: P1)

A data analyst wants to measure how many users who performed a "birth" event (e.g., Signup) come back to perform a "return" event (e.g., Login) over subsequent time periods. They call a single method with two event names and get back structured retention data with cohort-level rates and a DataFrame for analysis.

**Why this priority**: This is the core value proposition — running a retention query with minimal configuration. Without this, nothing else works.

**Independent Test**: Can be fully tested by calling `query_retention("Signup", "Login")` with default parameters and verifying the result contains cohort data, retention rates, and a well-shaped DataFrame.

**Acceptance Scenarios**:

1. **Given** a configured Workspace with valid credentials, **When** the user calls `query_retention("Signup", "Login")`, **Then** the system returns a `RetentionQueryResult` containing cohort-level retention data with rates per bucket, an average retention row, and a DataFrame with columns `cohort_date, bucket, count, rate`.
2. **Given** a configured Workspace, **When** the user calls `query_retention("Signup", "Login", retention_unit="week", last=90)`, **Then** the system returns weekly retention cohorts over a 90-day window.
3. **Given** a configured Workspace, **When** the user calls `query_retention("Signup", "Login")`, **Then** the returned result includes a `.params` attribute containing the bookmark JSON that was sent, enabling debugging and persistence via `create_bookmark()`.

---

### User Story 2 - Retention with Filters and Segmentation (Priority: P2)

A product manager wants to compare retention across user segments — for example, iOS vs Android users, or organic vs paid signups. They add global filters and group-by breakdowns to their retention query.

**Why this priority**: Segmented retention is critical for understanding which user cohorts retain best, but depends on the core query working first.

**Independent Test**: Can be tested by calling `query_retention()` with `group_by="platform"` and `where=[Filter.equals("country", "US")]` and verifying the result reflects the segmentation.

**Acceptance Scenarios**:

1. **Given** a configured Workspace, **When** the user calls `query_retention("Signup", "Login", group_by="platform")`, **Then** the result contains retention data segmented by platform values.
2. **Given** a configured Workspace, **When** the user calls `query_retention("Signup", "Login", where=[Filter.equals("source", "organic")])`, **Then** the result contains only users matching the filter condition.
3. **Given** a configured Workspace, **When** the user calls `query_retention()` with per-event filters via `RetentionEvent` objects, **Then** each event's filters are applied independently — the birth event filter restricts who enters the cohort, and the return event filter restricts what counts as a return.

---

### User Story 3 - Retention with Custom Bucket Sizes (Priority: P2)

A growth analyst wants non-uniform retention periods — for example, checking retention at day 1, day 3, day 7, day 14, and day 30 instead of every single day. They pass custom bucket sizes to see retention at specific intervals.

**Why this priority**: Custom buckets are commonly needed for "day 1 / day 7 / day 30" style retention reports, but the feature works fine with uniform buckets by default.

**Independent Test**: Can be tested by calling `query_retention("Signup", "Login", retention_unit="day", bucket_sizes=[1, 3, 7, 14, 30])` and verifying the result has exactly 5 retention buckets.

**Acceptance Scenarios**:

1. **Given** a configured Workspace, **When** the user calls `query_retention("Signup", "Login", retention_unit="day", bucket_sizes=[1, 3, 7, 14, 30])`, **Then** the result contains exactly 5 retention buckets corresponding to the specified intervals.
2. **Given** a configured Workspace, **When** the user calls `query_retention()` without `bucket_sizes`, **Then** the system uses uniform buckets based on `retention_unit` (the default behavior).

---

### User Story 4 - Build Params Without Executing (Priority: P3)

A developer wants to inspect or persist the generated retention bookmark JSON without actually querying the API. They use `build_retention_params()` to get the raw params dict.

**Why this priority**: Useful for debugging, testing, and saving reports via `create_bookmark()`, but not essential for querying.

**Independent Test**: Can be tested by calling `build_retention_params("Signup", "Login")` and verifying it returns a dict with the correct structure, without making any API calls.

**Acceptance Scenarios**:

1. **Given** a configured Workspace, **When** the user calls `build_retention_params("Signup", "Login")`, **Then** the system returns a dict (not a result object) containing the bookmark JSON structure, and no API call is made.
2. **Given** a configured Workspace, **When** the user calls `build_retention_params()` and then `query_retention()` with the same arguments, **Then** the bookmark params inside the query result match the params returned by `build_retention_params()`.

---

### User Story 5 - Fail-Fast Validation with Actionable Errors (Priority: P3)

A user provides invalid inputs — fewer than two events, invalid bucket sizes, or invalid retention unit. The system catches the errors before any API call and returns structured, actionable error messages with suggestions.

**Why this priority**: Good error messages dramatically improve developer experience, but they're polish on top of working functionality.

**Independent Test**: Can be tested by calling `query_retention()` with invalid inputs and verifying that `BookmarkValidationError` is raised with the correct error codes, messages, and suggestions.

**Acceptance Scenarios**:

1. **Given** a configured Workspace, **When** the user calls `query_retention("", "Login")`, **Then** the system raises a `BookmarkValidationError` with error code `R1` indicating the born event must be non-empty, and no API call is made.
2. **Given** a configured Workspace, **When** the user calls `query_retention("Signup", "Login", bucket_sizes=[7, 3, 1])`, **Then** the system raises a `BookmarkValidationError` with error code `R6` indicating bucket sizes must be in ascending order.
3. **Given** a configured Workspace, **When** the user provides multiple invalid inputs simultaneously, **Then** all validation errors are collected and returned together (not just the first one), so the user can fix everything in one pass.

---

### User Story 6 - Result Display Modes (Priority: P3)

An analyst wants to view retention data in different formats — the default retention curve, a trends-over-time view, or a tabular format.

**Why this priority**: Alternative display modes add flexibility but the default curve mode covers the primary use case.

**Independent Test**: Can be tested by calling `query_retention()` with `mode="trends"` and `mode="table"` and verifying different chart types are generated.

**Acceptance Scenarios**:

1. **Given** a configured Workspace, **When** the user calls `query_retention("Signup", "Login", mode="curve")`, **Then** the bookmark params specify a retention curve chart type.
2. **Given** a configured Workspace, **When** the user calls `query_retention("Signup", "Login", mode="trends")`, **Then** the bookmark params specify a line chart type for time-series trends.
3. **Given** a configured Workspace, **When** the user calls `query_retention("Signup", "Login", mode="table")`, **Then** the bookmark params specify a table chart type.

---

### Edge Cases

- What happens when the born event and return event are the same? The system should accept this — it measures "users who did X and came back to do X again."
- What happens when the API returns an empty cohorts structure (no data in date range)? The result should contain empty cohorts and an empty DataFrame with the correct column schema.
- What happens when the API returns an error response (e.g., invalid event name, rate limit)? The system should raise the appropriate exception (`QueryError`, `RateLimitError`) with context.
- What happens when `bucket_sizes` contains duplicate values (e.g., `[1, 3, 3, 7]`)? The system should reject this with a validation error.
- What happens when `bucket_sizes` contains non-positive values (e.g., `[0, 3, 7]`)? The system should reject this with a validation error.
- What happens when `from_date` is after `to_date`? The shared time validation should catch this (reused from existing infrastructure).
- What happens when the API response contains a segmented structure (`$overall` key) vs a direct cohort list? The response parser should handle both formats robustly.

## Requirements *(mandatory)*

### Functional Requirements

#### Input Types

- **FR-001**: System MUST provide a `RetentionEvent` type that wraps an event name with optional per-event filters and filter combinator (AND/OR), enabling filtered retention events without changing the simple string interface for common cases.
- **FR-002**: System MUST provide a `RetentionMathType` that constrains valid retention aggregation functions to the set supported by Mixpanel's retention engine (retention rate and unique user count).
- **FR-003**: System MUST accept plain event name strings for the `born_event` and `return_event` parameters, automatically converting them to the structured format internally (progressive disclosure).

#### Result Type

- **FR-004**: System MUST provide a `RetentionQueryResult` type containing cohort-level retention data: a mapping of cohort dates to their sizes, counts per bucket, and rates per bucket.
- **FR-005**: The result MUST include an `average` field containing the synthetic average retention across all cohorts.
- **FR-006**: The result MUST provide a `.df` property that returns a DataFrame with columns `cohort_date`, `bucket`, `count`, `rate` — one row per (cohort, bucket) pair.
- **FR-007**: The DataFrame MUST be lazily computed and cached after first access (consistent with the existing `ResultWithDataFrame` pattern).
- **FR-008**: The result MUST include the generated `.params` dict for debugging and persistence via `create_bookmark()`.
- **FR-009**: The result MUST include `.computed_at`, `.from_date`, `.to_date`, and `.meta` fields from the API response.

#### Validation (Layer 1 — Argument Validation)

- **FR-010**: System MUST validate that `born_event` is a non-empty string or `RetentionEvent` with a non-empty event name (rule R1).
- **FR-011**: System MUST validate that `return_event` is a non-empty string or `RetentionEvent` with a non-empty event name (rule R2).
- **FR-012**: System MUST reuse existing shared time range validation rules (V7-V11, V15, V20) for `from_date`, `to_date`, `last` parameters (rule R3).
- **FR-013**: System MUST reuse existing shared GroupBy validation rules (V11-V12, V18, V24) for the `group_by` parameter (rule R4).
- **FR-014**: System MUST validate that `bucket_sizes`, when provided, contains only positive integers (rule R5).
- **FR-015**: System MUST validate that `bucket_sizes`, when provided, is in strictly ascending order (rule R6).
- **FR-016**: System MUST validate that `retention_unit` is one of the valid retention units (`day`, `week`, `month`), with fuzzy-matched suggestions for invalid values (rule R7).
- **FR-017**: System MUST validate that `alignment` is one of the valid alignment types (`birth`, `interval_start`), with fuzzy-matched suggestions for invalid values (rule R8).
- **FR-018**: System MUST validate that `math` is one of the valid retention math types (`retention_rate`, `unique`), with fuzzy-matched suggestions for invalid values (rule R9).
- **FR-019**: System MUST collect all validation errors and return them together, not stopping at the first error.
- **FR-020**: Validation errors MUST include error codes (R1-R9), human-readable messages, JSONPath-like field locations, and fuzzy-matched suggestions where applicable.

#### Validation (Layer 2 — Bookmark Structure)

- **FR-021**: System MUST extend the existing bookmark structure validator to recognize `bookmark_type="retention"` and validate retention-specific math types against the retention-valid set.
- **FR-022**: Layer 2 validation MUST verify the bookmark JSON structure (sections, show, time, filter, group, displayOptions) using the same rules as insights and funnels.

#### Bookmark JSON Builder

- **FR-023**: System MUST generate valid retention bookmark JSON with `behavior.type = "retention"`, two behaviors (born event and return event), and retention-specific fields (`retentionUnit`, `retentionCustomBucketSizes`, `retentionAlignmentType`).
- **FR-024**: System MUST reuse shared bookmark builders for time section, filter section, and group section construction.
- **FR-025**: Per-event filters from `RetentionEvent` objects MUST be converted to the bookmark filter format using the existing `build_filter_entry()` function.
- **FR-026**: The measurement block MUST include the `math` field. Retention-specific fields (`retentionBucketIndex`, `retentionSegmentationEvent`) are optional and only needed for advanced segmented retention views; they MAY be omitted for standard retention queries.

#### Public Methods

- **FR-027**: System MUST provide `query_retention(born_event, return_event, **kwargs)` that validates inputs, builds bookmark params, queries the API, and returns a `RetentionQueryResult`.
- **FR-028**: System MUST provide `build_retention_params(born_event, return_event, **kwargs)` that validates inputs, builds bookmark params, and returns the raw dict without querying the API.
- **FR-029**: Both methods MUST accept the same set of keyword arguments: `retention_unit`, `alignment`, `bucket_sizes`, `from_date`, `to_date`, `last`, `unit`, `math`, `group_by`, `where`, `mode`.
- **FR-030**: All validation MUST occur before any API call — invalid inputs never reach the network.

#### Response Parsing

- **FR-031**: System MUST parse the API response and extract cohort-level data: cohort dates, cohort sizes, per-bucket user counts, and per-bucket retention rates.
- **FR-032**: System MUST extract the `$average` synthetic cohort from the response and populate the result's `average` field.
- **FR-033**: System MUST handle multiple response format variations (direct cohort list, nested series structure, segmented responses with `$overall` key) robustly.
- **FR-034**: System MUST raise `QueryError` when the API response contains an `error` key or is missing required fields (`series`).

#### Exports

- **FR-035**: The public package MUST export `RetentionEvent`, `RetentionMathType`, and `RetentionQueryResult` from the top-level `__init__.py`.

### Key Entities

- **RetentionEvent**: An event specification for retention queries. Wraps an event name with optional per-event filters and filter combinator. Used for both born (cohort entry) and return (retention signal) events.
- **RetentionQueryResult**: The result of a retention query. Contains cohort-level data (dates mapped to sizes, counts, and rates), an average retention summary, the generated bookmark params, and response metadata. Provides lazy DataFrame conversion.
- **RetentionMathType**: A constrained set of valid aggregation functions for retention queries (retention rate, unique count).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Users can run a simple retention query with just two event names (`query_retention("Signup", "Login")`) and receive structured results — no more than 2 required arguments for the simplest case.
- **SC-002**: The retention query interface follows the same patterns as the existing `query()` and `query_funnel()` methods — users familiar with one can use the others without learning a new paradigm.
- **SC-003**: All invalid inputs are caught before any network request, with actionable error messages that include the field path, error code, and suggestions for valid values.
- **SC-004**: The result DataFrame contains the correct number of rows (one per cohort-bucket pair) and all expected columns (`cohort_date`, `bucket`, `count`, `rate`).
- **SC-005**: `build_retention_params()` returns identical bookmark params to what `query_retention()` sends to the API, enabling inspect-then-query workflows.
- **SC-006**: Generated bookmark params can be saved via `create_bookmark()` to persist retention reports in Mixpanel.
- **SC-007**: All new code meets existing project quality standards: 90%+ test coverage, passes mypy --strict, passes ruff linting, includes comprehensive docstrings.
- **SC-008**: Property-based tests verify type invariants (immutability, field preservation, DataFrame shape consistency) across randomly generated inputs.

## Assumptions

- The existing `insights_query()` API client method works for retention queries without modification — the Mixpanel `/insights` endpoint routes internally based on `behavior.type == "retention"` in the bookmark params.
- The shared bookmark builders (`build_time_section`, `build_filter_section`, `build_group_section`, `build_filter_entry`) work correctly for retention queries — they have been validated by the insights and funnel implementations.
- The shared validation helpers (`validate_time_args`, `validate_group_by_args`) are reusable for retention without modification.
- The `VALID_MATH_RETENTION` enum in `bookmark_enums.py` already contains the correct set of valid math types for retention.
- The `VALID_RETENTION_UNITS` and `VALID_RETENTION_ALIGNMENT` enums in `bookmark_enums.py` already contain the correct valid values.
- The `validate_bookmark()` function already accepts a `bookmark_type` parameter and can be extended to use `VALID_MATH_RETENTION` when `bookmark_type="retention"`.
- Retention queries use the same authentication and rate-limiting behavior as insights and funnel queries.
- The `LiveQueryService` can be extended with a `query_retention()` method following the same pattern as `query()` and `query_funnel()`.
- The response format for retention queries through the `/insights` endpoint follows the same envelope structure (`computed_at`, `date_range`, `headers`, `series`, `meta`) as insights and funnel responses, with retention-specific data nested in `series`.
