# Feature Specification: Phase 1 — Shared Infrastructure Extraction

**Feature Branch**: `031-shared-infra-extraction`
**Created**: 2026-04-05
**Status**: Draft
**Input**: User description: "Phase 1: Shared Infrastructure Extraction — Extract shared components from the existing query() pipeline for reuse by funnels, retention, and flows query methods"

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Reusable Time Range Building (Priority: P1)

A library developer building the funnel, retention, or flows query method needs to generate the correct time section JSON without duplicating the logic already embedded in `_build_query_params()`. They call a shared time-builder that accepts the same `from_date`, `to_date`, `last`, and `unit` parameters and produces either a `sections.time[]` entry (for insights/funnels/retention) or a flat `date_range` dict (for flows).

**Why this priority**: Every query method requires time range handling. Without this extraction, every new report type would copy-paste ~25 lines of date logic, creating divergence risk across four code paths.

**Independent Test**: Can be fully tested by calling the extracted time builder with various date combinations and asserting the output dict structure matches the expected bookmark JSON. No API credentials or network access needed.

**Acceptance Scenarios**:

1. **Given** `from_date="2026-01-01"` and `to_date="2026-01-31"` and `unit="day"`, **When** the sections-based time builder is called, **Then** it returns `{"dateRangeType": "between", "unit": "day", "value": ["2026-01-01", "2026-01-31"]}`.
2. **Given** `from_date="2026-01-01"` and `to_date=None` and `unit="day"`, **When** the sections-based time builder is called, **Then** it returns a `"between"` entry spanning from `from_date` through today's date.
3. **Given** `from_date=None` and `to_date=None` and `last=30` and `unit="day"`, **When** the sections-based time builder is called, **Then** it returns `{"dateRangeType": "in the last", "unit": "day", "window": {"unit": "day", "value": 30}}`.
4. **Given** `from_date=None` and `last=30`, **When** the flows date-range builder is called, **Then** it returns `{"type": "in the last", "from_date": {"unit": "day", "value": 30}, "to_date": "$now"}`.
5. **Given** `from_date="2026-01-01"` and `to_date="2026-01-31"`, **When** the flows date-range builder is called, **Then** it returns `{"type": "between", "from_date": "2026-01-01", "to_date": "2026-01-31"}`.
6. **Given** `where=Filter.equals("country", "US")`, **When** the filter-section builder is called, **Then** it returns a single-element list containing the filter entry dict with `filterOperator: "equals"` and `filterValue: ["US"]`.
7. **Given** `where=[Filter.equals("country", "US"), Filter.greater_than("amount", 50)]`, **When** the filter-section builder is called, **Then** it returns a two-element list with both filter entries.
8. **Given** `where=None`, **When** the filter-section builder is called, **Then** it returns an empty list.
9. **Given** `group_by="country"`, **When** the group-section builder is called, **Then** it returns a single-element list with `value: "country"`, `propertyName: "country"`, `resourceType: "events"`, and `propertyType: "string"`.
10. **Given** `group_by=GroupBy("amount", property_type="number", bucket_size=10, bucket_min=0, bucket_max=100)`, **When** the group-section builder is called, **Then** it returns a list with `customBucket: {"bucketSize": 10, "min": 0, "max": 100}`.

---

### User Story 2 — Reusable Time and GroupBy Validation (Priority: P1)

A library developer building funnel or retention validation needs to apply the same time-range rules (V7-V10, V15, V20) and group-by rules (V11-V12, V18, V24) without duplicating ~175 lines of validation code. They call extracted validation helpers that return a list of `ValidationError` objects, which they combine with report-specific errors.

**Why this priority**: Tied with Story 1. Every new `validate_*_args()` function needs these shared rules. Extracting them first prevents divergence and ensures consistent error messages and codes across all report types.

**Independent Test**: Can be fully tested by calling each extracted validator with valid and invalid inputs and asserting the expected `ValidationError` objects are returned. Existing tests for `validate_query_args()` confirm the extraction didn't change behavior.

**Acceptance Scenarios**:

1. **Given** `last=-1`, **When** time validation is called, **Then** it returns a `ValidationError` with code `V7_LAST_POSITIVE`.
2. **Given** `to_date="2026-01-01"` and `from_date=None`, **When** time validation is called, **Then** it returns a `ValidationError` with code `V9_TO_REQUIRES_FROM`.
3. **Given** `from_date="2026-02-01"` and `to_date="2026-01-01"`, **When** time validation is called, **Then** it returns a `ValidationError` with code `V15_DATE_ORDER`.
4. **Given** a `GroupBy` with `bucket_size=10` but `property_type="string"`, **When** group-by validation is called, **Then** it returns a `ValidationError` with code `V12B_BUCKET_REQUIRES_NUMBER`.
5. **Given** identical arguments, **When** `validate_query_args()` is called before and after refactoring, **Then** it produces identical error lists (no behavioral regression).

---

### User Story 3 — Filter-to-Segfilter Conversion for Flows (Priority: P2)

A library developer building the flows query method needs to convert `Filter` objects (used throughout the library) to the legacy "segfilter" format required by the flows `/arb_funnels` endpoint. They call a converter that translates operator names, property locations, value formatting, and date formats from the bookmark format to the segfilter format.

**Why this priority**: Only flows uses the segfilter format, so this is not blocking funnels or retention. However, it is the single most complex new piece of infrastructure with numerous operator-specific edge cases, so building and testing it in Phase 1 de-risks Phase 4 (Flows).

**Independent Test**: Can be fully tested by creating `Filter` objects with every supported operator and asserting the segfilter output matches the canonical reference (TypeScript round-trip test cases from `analytics/` repo). No API access needed.

**Acceptance Scenarios**:

1. **Given** `Filter.equals("country", "US")`, **When** the segfilter converter is called, **Then** it returns a dict with `filter.operator: "=="`, `filter.operand: ["US"]`, and `property.name: "country"`.
2. **Given** `Filter.greater_than("amount", 50)`, **When** the segfilter converter is called, **Then** it returns `filter.operator: ">"` and `filter.operand: "50"` (stringified number).
3. **Given** `Filter.is_set("email")`, **When** the segfilter converter is called, **Then** it returns `filter.operator: "set"` with `filter.operand: ""` (empty string).
4. **Given** `Filter.contains("name", "john")`, **When** the segfilter converter is called, **Then** it returns `filter.operator: "in"` with `filter.operand: "john"`.
5. **Given** a `Filter` with `resource_type="people"`, **When** the segfilter converter is called, **Then** `property.source` is `"user"` (mapped from `"people"` via `RESOURCE_TYPE_MAP`).

---

### User Story 4 — Extended Bookmark Enum Constants (Priority: P2)

A library developer building funnel or retention validation needs canonical enum sets for funnel math types, retention math types, funnel ordering modes, retention units, conversion window units, and related constants. These are used for O(1) membership checks and fuzzy-matched error suggestions in the validation engine.

**Why this priority**: The enum constants file already contains partial funnel/retention entries. This story completes coverage and adds new constants. Required before Phase 2/3 validation can be implemented, but the constants alone don't block any execution path.

**Independent Test**: Can be fully tested by asserting that each new frozenset contains the expected members. Cross-reference with the canonical values from the Mixpanel `analytics/` reference repo.

**Acceptance Scenarios**:

1. **Given** the funnel math types constant, **When** checking membership, **Then** it contains `"conversion_rate_unique"`, `"conversion_rate_total"`, `"conversion_rate_session"`, `"unique"`, `"total"`, and property aggregation types (`"average"`, `"median"`, `"min"`, `"max"`, `"p25"`, `"p75"`, `"p90"`, `"p99"`).
2. **Given** the retention math types constant, **When** checking membership, **Then** it contains `"retention_rate"` and `"unique"`.
3. **Given** the chart types constant, **When** checking membership, **Then** it contains `"funnel-steps"`, `"funnel-top-paths"`, and `"retention-curve"`.
4. **Given** a new funnel ordering constant, **When** checking membership, **Then** it contains `"loose"` and `"any"`.
5. **Given** a new conversion window units constant, **When** checking membership, **Then** it contains `"second"`, `"minute"`, `"hour"`, `"day"`, `"week"`, `"month"`, and `"session"`.

---

### User Story 5 — Existing query() Remains Unchanged (Priority: P1)

After all extractions and refactoring, the existing `query()` and `build_params()` methods produce identical bookmark JSON for all inputs. No existing test fails. No public API signature changes.

**Why this priority**: This is a non-regression constraint. The extraction must be invisible to existing callers.

**Independent Test**: Run the full existing test suite. All tests pass with zero modifications. Additionally, property-based tests generate random valid inputs and assert the output before and after refactoring is identical.

**Acceptance Scenarios**:

1. **Given** any valid call to `query()` or `build_params()`, **When** executed against the refactored code, **Then** the returned params dict is identical to the pre-refactoring output.
2. **Given** any invalid call to `query()` or `build_params()`, **When** executed against the refactored code, **Then** the raised `BookmarkValidationError` contains the same error codes and messages.
3. **Given** the full existing test suite, **When** run after refactoring, **Then** all tests pass without modification.

---

### Edge Cases

- What happens when `from_date` is provided but `to_date` is `None`? The time builder produces a `"between"` range from `from_date` through today.
- What happens when `last` exceeds the 3650-day cap? The time validator returns `V20_LAST_TOO_LARGE`.
- What happens when a `Filter` uses a date operator with a relative date unit? The segfilter converter must translate the `filterDateUnit` field correctly.
- What happens when `GroupBy.bucket_min` equals `GroupBy.bucket_max`? The group-by validator returns `V18_BUCKET_ORDER`.
- What happens when `Filter` uses an operator not mappable to segfilter format? The converter raises a clear error identifying the unsupported operator.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST provide a shared time-section builder that accepts `from_date`, `to_date`, `last`, and `unit` parameters and returns a `sections.time[]` entry dict for use by insights, funnels, and retention bookmark builders.
- **FR-002**: System MUST provide a flows-specific date-range builder that accepts `from_date`, `to_date`, and `last` parameters and returns a flat `date_range` dict matching the flows bookmark format.
- **FR-003**: System MUST provide extracted time-argument validation (rules V7-V10, V15, V20) as a callable that returns a list of `ValidationError` objects.
- **FR-004**: System MUST provide extracted group-by-argument validation (rules V11-V12, V18, V24) as a callable that returns a list of `ValidationError` objects.
- **FR-005**: System MUST refactor `validate_query_args()` to delegate to the extracted time and group-by validators without changing its external behavior or error output.
- **FR-006**: System MUST refactor `_build_query_params()` to delegate to the extracted time-section and group-section builders without changing its output.
- **FR-007**: System MUST provide a segfilter converter that translates `Filter` objects to the legacy segfilter format used by flows step filters, handling all supported operator types.
- **FR-008**: System MUST extend the bookmark enums module with frozenset constants for funnel ordering modes, conversion window units, retention units, retention alignment types, and any missing funnel/retention/flows-specific values.
- **FR-009**: System MUST maintain full backward compatibility — no changes to public API signatures, return types, or exception behavior for existing `query()`, `build_params()`, or validation functions.
- **FR-010**: System MUST provide a shared group-section builder that accepts `group_by` parameter(s) and returns a `sections.group[]` list for use by insights, funnels, and retention bookmark builders.
- **FR-011**: System MUST provide a shared filter-section builder that accepts `where` parameter(s) and returns a `sections.filter[]` list for use by insights, funnels, and retention bookmark builders.

### Key Entities

- **Time Section Entry**: A dict representing one `sections.time[]` element with `dateRangeType`, `unit`, and either `value` (date pair) or `window` (relative range).
- **Flows Date Range**: A flat dict with `type`, `from_date`, and `to_date` fields matching the flows bookmark format.
- **Segfilter Entry**: A dict with `property` (name, source, type), `type`, `selected_property_type`, and `filter` (operator, operand) fields matching the legacy Mixpanel segfilter format.
- **Bookmark Enum Constants**: Immutable frozenset collections of valid string values for O(1) membership checks.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: All existing tests pass without modification after refactoring (zero regressions).
- **SC-002**: The extracted time builder produces identical output to the inline code it replaces, verified by property-based tests across randomized date inputs.
- **SC-003**: The extracted validators produce identical error lists to the inline code they replace, verified by property-based tests across randomized invalid inputs.
- **SC-004**: The segfilter converter correctly handles all operator types supported by `Filter`, verified against the canonical TypeScript reference test cases.
- **SC-005**: Code coverage for the new extracted functions meets the project's 90% minimum threshold.
- **SC-006**: The refactored `validate_query_args()` and `_build_query_params()` have no duplicated logic — they delegate entirely to the extracted helpers for time and group-by concerns.

## Assumptions

- The existing `Filter` type supports all operators needed for the segfilter converter; no new `Filter` constructors are required in this phase.
- The `analytics/` reference repository is available for cross-referencing canonical segfilter format and round-trip test cases.
- The `VALID_MATH_FUNNELS` and `VALID_MATH_RETENTION` frozensets already exist in `bookmark_enums.py` and need only extension/verification, not creation from scratch.
- The `VALID_CHART_TYPES` frozenset already includes `"funnel-steps"`, `"funnel-top-paths"`, and `"retention-curve"`.
- Flows `group_by` support is explicitly out of scope for this phase (per design document section 6.3).
- No new public types (e.g., `FunnelStep`, `RetentionEvent`) are introduced in this phase — those belong to Phases 2-4.
- The segfilter converter only needs to support the operators that `Filter` currently exposes, not the full set of legacy segfilter operators.
