# Feature Specification: Funnel Query — `query_funnel()`

**Feature Branch**: `032-funnel-query`  
**Created**: 2026-04-05  
**Status**: Draft  
**Input**: Phase 2 of the unified bookmark query system. Add typed funnel query support via `query_funnel()` and `build_funnel_params()`, building on the shared infrastructure extracted in Phase 1 (PR #88).

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Simple Funnel Analysis (Priority: P1)

A data analyst or AI agent wants to measure conversion between two or more sequential events without needing to create a saved report in the Mixpanel UI. They call `query_funnel()` with a list of event name strings and receive a typed result containing step-level conversion data.

**Why this priority**: This is the core value proposition — the simplest possible funnel query that covers the majority of use cases. Without this, no other funnel capability matters.

**Independent Test**: Can be fully tested by calling `ws.query_funnel(["Signup", "Purchase"])` and verifying the result contains step counts, step conversion ratios, overall conversion rate, and a DataFrame with one row per step.

**Acceptance Scenarios**:

1. **Given** a configured Workspace with valid credentials, **When** the user calls `query_funnel(["Signup", "Purchase"])`, **Then** the system returns a `FunnelQueryResult` with step-level data for each event, including counts and conversion ratios.
2. **Given** a list of 3+ event names, **When** the user calls `query_funnel(["Signup", "Add to Cart", "Checkout", "Purchase"])`, **Then** the result contains data for all 4 steps with both step-to-step and overall conversion ratios.
3. **Given** the result object, **When** the user accesses `.df`, **Then** they receive a DataFrame with columns: `step`, `event`, `count`, `step_conv_ratio`, `overall_conv_ratio`, `avg_time`, `avg_time_from_start`, with one row per funnel step.
4. **Given** the result object, **When** the user accesses `.overall_conversion_rate`, **Then** they receive a float representing the end-to-end conversion rate from step 1 to the last step.
5. **Given** the result object, **When** the user accesses `.params`, **Then** they receive the generated bookmark JSON dict that was sent to the API.

---

### User Story 2 — Funnel with Configuration Options (Priority: P1)

A data analyst wants to customize funnel behavior — adjusting the conversion window (how long users have to complete the funnel), the step ordering mode (strict sequence vs. any order), time range, and aggregation math type.

**Why this priority**: Conversion window and ordering are fundamental to correct funnel analysis. Without these controls, the simple funnel from Story 1 may produce misleading results for many real-world use cases.

**Independent Test**: Can be tested by calling `query_funnel()` with keyword arguments for conversion window, order, time range, and math type, and verifying the generated bookmark params contain the correct configuration values.

**Acceptance Scenarios**:

1. **Given** default parameters, **When** the user calls `query_funnel(["A", "B"])` without specifying a conversion window, **Then** the system uses a 14-day conversion window by default.
2. **Given** explicit configuration, **When** the user calls `query_funnel(["A", "B"], conversion_window=7, conversion_window_unit="day", order="any")`, **Then** the generated params reflect a 7-day window with any-order step matching.
3. **Given** an absolute date range, **When** the user calls `query_funnel(["A", "B"], from_date="2026-01-01", to_date="2026-03-31")`, **Then** the result covers exactly that date range.
4. **Given** a relative date range, **When** the user calls `query_funnel(["A", "B"], last=90, unit="day")`, **Then** the result covers the last 90 days.
5. **Given** a math type, **When** the user calls `query_funnel(["A", "B"], math="unique")`, **Then** the result contains raw unique user counts per step rather than conversion rates.

---

### User Story 3 — Per-Step Filters and Labels (Priority: P2)

A data analyst wants to add filters to individual funnel steps — for example, requiring the "Purchase" step to have `amount > 50` — or apply custom labels to steps for readability.

**Why this priority**: Per-step filtering is essential for meaningful funnel analysis (e.g., filtering by platform, plan tier, or transaction amount at specific steps), but the core funnel works without it.

**Independent Test**: Can be tested by constructing `FunnelStep` objects with filters and labels, passing them to `query_funnel()`, and verifying the generated params contain per-step filter entries and custom labels.

**Acceptance Scenarios**:

1. **Given** a mix of strings and `FunnelStep` objects, **When** the user calls `query_funnel(["Signup", FunnelStep("Purchase", filters=[Filter.greater_than("amount", 50)])])`, **Then** the system accepts both formats and applies the filter only to the Purchase step.
2. **Given** a `FunnelStep` with a label, **When** the user calls `query_funnel([FunnelStep("Purchase", label="First Purchase")])`, **Then** the generated params use "First Purchase" as the step label.
3. **Given** a `FunnelStep` with multiple filters, **When** `filters_combinator="any"` is set, **Then** the filters are combined with OR logic (any filter matching is sufficient).
4. **Given** a `FunnelStep` with `filters_combinator="all"` (default), **Then** all filters must match simultaneously (AND logic).

---

### User Story 4 — Global Filters and Group-By Breakdown (Priority: P2)

A data analyst wants to filter the entire funnel by a condition (e.g., country = "US") and/or break down the funnel by a property (e.g., platform) to compare conversion rates across segments.

**Why this priority**: Segmentation and filtering are standard analytics operations that reuse shared infrastructure from Phase 1. They significantly increase analytical value but are not required for basic funnel operation.

**Independent Test**: Can be tested by passing `where` and `group_by` parameters to `query_funnel()` and verifying the generated params contain the correct `sections.filter[]` and `sections.group[]` entries.

**Acceptance Scenarios**:

1. **Given** a global filter, **When** the user calls `query_funnel(["A", "B"], where=Filter.equals("country", "US"))`, **Then** the funnel only includes users matching the filter.
2. **Given** a group-by, **When** the user calls `query_funnel(["A", "B"], group_by="platform")`, **Then** the result contains separate conversion data for each platform segment.
3. **Given** both filters and group-by, **When** combined in a single call, **Then** both are applied correctly — filtered first, then broken down.

---

### User Story 5 — Funnel Exclusions (Priority: P3)

A data analyst wants to exclude users who performed a specific event between funnel steps — for example, excluding users who "Logged Out" between "Add to Cart" and "Purchase".

**Why this priority**: Exclusions are an advanced funnel feature that refines analysis quality. Most basic funnels work without them.

**Independent Test**: Can be tested by passing exclusion strings or `Exclusion` objects and verifying the generated params contain the correct exclusion entries with step ranges.

**Acceptance Scenarios**:

1. **Given** a string exclusion, **When** the user calls `query_funnel(["A", "B", "C"], exclusions=["Logout"])`, **Then** users who performed "Logout" between any steps are excluded from the funnel.
2. **Given** a step-range exclusion, **When** the user calls `query_funnel(["A", "B", "C"], exclusions=[Exclusion("Refund", from_step=1, to_step=2)])`, **Then** only users who performed "Refund" between steps 1 and 2 are excluded.
3. **Given** a default `Exclusion` object with no step range, **Then** the exclusion applies between all steps (same as string shorthand).

---

### User Story 6 — Holding Property Constant (Priority: P3)

A data analyst wants to hold a property constant across all funnel steps — for example, ensuring the same "platform" value applies at every step, so a user who signed up on iOS and purchased on web is not counted as converting.

**Why this priority**: Hold-property-constant (HPC) is an advanced funnel feature that improves accuracy for cross-platform analysis. Most funnels work correctly without it.

**Independent Test**: Can be tested by passing `holding_constant` strings or `HoldingConstant` objects and verifying the generated params contain the correct `aggregateBy` entries.

**Acceptance Scenarios**:

1. **Given** a string, **When** the user calls `query_funnel(["A", "B"], holding_constant="platform")`, **Then** the funnel only counts conversions where the user had the same platform value at every step.
2. **Given** a `HoldingConstant` with `resource_type="people"`, **Then** the system holds a user-profile property constant (rather than an event property).
3. **Given** a list of holding constants, **Then** all specified properties are held constant simultaneously.

---

### User Story 7 — Build Params Without Execution (Priority: P2)

A developer or AI agent wants to inspect the generated funnel bookmark JSON without making an API call — for debugging, persisting as a saved report, or testing validation logic.

**Why this priority**: Debuggability is a core design principle. `build_funnel_params()` mirrors the existing `build_params()` pattern and enables testing without credentials.

**Independent Test**: Can be tested by calling `build_funnel_params()` and verifying the returned dict matches the expected bookmark JSON structure without any network calls.

**Acceptance Scenarios**:

1. **Given** the same arguments as `query_funnel()`, **When** the user calls `build_funnel_params(["A", "B"])`, **Then** they receive a valid bookmark params dict with the correct funnel behavior structure.
2. **Given** invalid arguments (e.g., fewer than 2 steps), **When** the user calls `build_funnel_params(["A"])`, **Then** a `BookmarkValidationError` is raised with actionable error messages — same as `query_funnel()` would produce.
3. **Given** valid params output, **When** the user passes it to `create_bookmark()`, **Then** a saved funnel report is created in Mixpanel.

---

### User Story 8 — Fail-Fast Validation with Actionable Errors (Priority: P1)

A user (human or AI agent) constructs an invalid funnel query — too few steps, invalid math type, negative conversion window, etc. The system must catch these errors before making any API call and return structured, actionable error messages.

**Why this priority**: Fail-fast validation is a core design principle and critical for AI agent usability. Without it, users waste time debugging opaque API errors.

**Independent Test**: Can be tested by passing invalid arguments to `query_funnel()` or `build_funnel_params()` and verifying the correct `BookmarkValidationError` is raised with specific validation error codes.

**Acceptance Scenarios**:

1. **Given** fewer than 2 steps, **When** the user calls `query_funnel(["A"])`, **Then** a `BookmarkValidationError` is raised with error code F1 and message indicating at least 2 steps are required.
2. **Given** an empty string in the steps list, **When** the user calls `query_funnel(["Signup", ""])`, **Then** a `BookmarkValidationError` is raised with error code F2.
3. **Given** a negative conversion window, **When** the user calls `query_funnel(["A", "B"], conversion_window=-1)`, **Then** a `BookmarkValidationError` is raised with error code F3.
4. **Given** an invalid math type string, **When** the user calls `query_funnel(["A", "B"], math="invalid")`, **Then** a validation error is raised with a suggestion of valid math types.
5. **Given** multiple validation errors in a single call, **Then** all errors are collected and reported together (not just the first one).

---

### Edge Cases

- What happens when the user passes exactly 2 steps (the minimum)? The system must handle this as the simplest valid funnel.
- What happens when a `FunnelStep` has an empty `filters` list vs. `None`? Both should produce the same output (no filters applied).
- What happens when `from_date` and `to_date` are the same date? The system should allow single-day funnels.
- What happens when `exclusions` reference an event not in the steps list? This is valid — exclusion events are intentionally different from funnel step events. No validation error; the API processes the exclusion normally.
- What happens when `Exclusion.to_step` exceeds the number of funnel steps? Validation should catch and report the out-of-range step index.
- What happens when `conversion_window=0`? Should be rejected (must be positive).
- What happens when both `from_date`/`to_date` and `last` are provided? Existing time range validation (V7-V11) handles this conflict.
- What happens when `holding_constant` references a property that doesn't exist? This is not validated locally — the API will return an error. The system should pass through the API error.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST accept funnel queries with a list of 2 or more event names (strings) as the minimal input, using sensible defaults for all other parameters.
- **FR-002**: System MUST accept `FunnelStep` objects in the steps list interchangeably with plain strings, allowing per-step filters, labels, and ordering overrides.
- **FR-003**: System MUST support configurable conversion windows via `conversion_window` (positive integer) and `conversion_window_unit` (second, minute, hour, day, week, month, session), defaulting to 14 days.
- **FR-004**: System MUST support funnel step ordering via `order` parameter: `"loose"` (steps in order, other events allowed between) and `"any"` (steps in any order), defaulting to `"loose"`.
- **FR-005**: System MUST support time range specification via `from_date`/`to_date` (absolute) or `last`/`unit` (relative), reusing the shared time range infrastructure.
- **FR-006**: System MUST support funnel math types: conversion rates (unique, total, session), raw counts (unique, total), and property aggregations (average, median, min, max, p25, p75, p90, p99).
- **FR-007**: System MUST support global filters via `where` parameter using the shared `Filter` type, applied to the entire funnel.
- **FR-008**: System MUST support group-by breakdown via `group_by` parameter using the shared `GroupBy` type, producing segmented funnel results.
- **FR-009**: System MUST support funnel exclusions via `exclusions` parameter, accepting both plain strings (exclude between all steps) and `Exclusion` objects (exclude between specific step ranges).
- **FR-010**: System MUST support holding properties constant via `holding_constant` parameter, accepting both plain strings (event properties) and `HoldingConstant` objects (event or user properties).
- **FR-011**: System MUST support result mode selection via `mode` parameter: `"steps"` (default step-level view), `"trends"` (conversion over time), and `"table"` (tabular breakdown).
- **FR-012**: System MUST return a `FunnelQueryResult` containing: `computed_at`, `from_date`, `to_date`, `steps_data` (list of step dicts), `series` (raw API data), `params` (generated bookmark JSON), and `meta` (response metadata).
- **FR-013**: `FunnelQueryResult` MUST provide an `overall_conversion_rate` property returning the end-to-end conversion rate as a float.
- **FR-014**: `FunnelQueryResult` MUST provide a lazy `.df` property returning a DataFrame. In `mode="steps"` (default), columns are: `step`, `event`, `count`, `step_conv_ratio`, `overall_conv_ratio`, `avg_time`, `avg_time_from_start` (one row per step). In `mode="trends"`, columns are: `date`, `step`, `count` (one row per date/step pair). In `mode="table"`, columns match the segmented breakdown.
- **FR-015**: System MUST provide a `build_funnel_params()` method that generates validated bookmark params without executing the query, enabling debugging and persistence via `create_bookmark()`.
- **FR-016**: System MUST validate all inputs before making any API call (fail-fast), using the two-layer validation engine: Layer 1 validates arguments (rules F1-F6), Layer 2 validates the generated bookmark structure.
- **FR-017**: Validation errors MUST be raised as `BookmarkValidationError` containing a list of `ValidationError` objects, each with path, message, error code, severity, and optional suggestion.
- **FR-018**: Layer 2 bookmark validation MUST correctly select funnel-specific valid math types when `bookmark_type="funnels"` is passed.

### Key Entities

- **FunnelStep**: A single step in a funnel query — an event name with optional label, per-step filters, filter combinator, and per-step ordering override.
- **Exclusion**: An event to exclude between funnel steps — an event name with optional start/end step range for targeted exclusion.
- **HoldingConstant**: A property to hold constant across all funnel steps — a property name with resource type (event or user property).
- **FunnelQueryResult**: The result of a funnel query — contains step-level conversion data, timing information, the generated bookmark params, and a lazy DataFrame conversion.
- **FunnelMathType**: The set of valid aggregation math types for funnel queries — conversion rates, raw counts, and property aggregations.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A user can express the simplest funnel query in a single line — `ws.query_funnel(["Signup", "Purchase"])` — and receive a complete, typed result.
- **SC-002**: All 6 Layer 1 validation rules (F1-F6) reject invalid inputs before any network call, with error messages that include what was wrong and how to fix it.
- **SC-003**: The generated bookmark JSON for any valid `query_funnel()` call matches the canonical Mixpanel funnel bookmark format (as specified in the design document Appendix A.2), producing correct results when POSTed to the insights API.
- **SC-004**: `build_funnel_params()` produces identical bookmark JSON to `query_funnel()` for the same inputs, and that JSON can be passed to `create_bookmark()` to persist as a saved report.
- **SC-005**: All new types (`FunnelStep`, `Exclusion`, `HoldingConstant`, `FunnelQueryResult`) are immutable (frozen dataclasses) and fully type-annotated, passing `mypy --strict`.
- **SC-006**: `FunnelQueryResult.df` produces a correctly shaped DataFrame with one row per funnel step and all expected columns populated from the API response.
- **SC-007**: Test coverage for all new code meets or exceeds the project's 90% coverage threshold.
- **SC-008**: All existing tests continue to pass — no regressions in `query()`, `build_params()`, or shared infrastructure.

## Assumptions

- The shared infrastructure from Phase 1 (PR #88) — `build_time_section()`, `build_filter_section()`, `build_group_section()`, `build_filter_entry()`, `validate_time_args()`, `validate_group_by_args()`, and funnel-specific enum constants — is merged and available on the working branch.
- Funnel bookmarks POST to the same `/insights` endpoint as insights bookmarks. The Mixpanel insights API internally detects the funnel behavior type and delegates to the funnels query engine. No new API endpoint is required.
- The existing `insights_query()` API client method can be reused without modification for funnel queries.
- The existing `FunnelResult` type (used by the saved-funnel `funnel()` method) is a separate type from the new `FunnelQueryResult`. The two serve different purposes: `FunnelResult` wraps the legacy funnel API response, while `FunnelQueryResult` wraps the bookmark-based insights API response with richer structure.
- Per-step filter entries reuse the existing `_build_filter_entry()` / `build_filter_entry()` function from the shared builders — no new filter format is needed for funnels (unlike flows, which require segfilter conversion).
- Property existence validation for `holding_constant` is not performed locally — invalid property names will produce API-level errors that are passed through to the caller.
