# Research: Cohort Behaviors in Unified Query System

**Date**: 2026-04-06 | **Status**: Complete

## Research Questions

### R1: How to widen `Filter._value` type for cohort filter values?

**Decision**: Widen the `_value` field annotation from `str | int | float | list[str] | list[int | float] | None` to include `list[dict[str, Any]]`.

**Rationale**: Cohort filters require `filterValue: [{cohort: {id, name, negated}}]` — a list of dicts. The `_value` field is internal (underscore-prefixed) and only consumed by `build_filter_entry()`. Widening the union is safe because:
1. No external code accesses `_value` directly
2. `build_filter_entry()` is the single consumer and will branch on `_property == "$cohorts"`
3. The frozen dataclass prevents mutation

**Alternatives considered**:
- (A) Separate `_cohort_value` field — rejected because it adds a field that's `None` for 18 of 20 factory methods
- (B) Subclass `CohortFilter(Filter)` — rejected because it breaks `isinstance(f, Filter)` checks and `where: Filter | list[Filter]` signatures

### R2: How should `query_flow()` accept cohort filters?

**Decision**: Add a `where: Filter | list[Filter] | None = None` parameter to `query_flow()`, restricted to cohort filters only. Non-cohort filters in `where=` raise `ValueError` (flows use per-step `FlowStep.filters` for property filters).

**Rationale**: The design doc specifies cohort filters in flows use the legacy `filter_by_cohort` top-level key. This requires a new entry point on `query_flow()`. Restricting `where=` to cohort filters avoids confusion with per-step property filters (which use a different format — `build_segfilter_entry()` not `build_filter_entry()`).

**Alternatives considered**:
- (A) Embed cohort filter in `FlowStep` — rejected because `filter_by_cohort` is a top-level field, not per-step
- (B) Add a separate `cohort_filter=` parameter — rejected for inconsistency with other query methods that use `where=`

### R3: How to handle `CohortBreakdown` in `build_group_section()`?

**Decision**: Extend the existing `build_group_section()` function to accept `CohortBreakdown` alongside `str` and `GroupBy`. The function's type signature widens to `str | GroupBy | CohortBreakdown | list[str | GroupBy | CohortBreakdown] | None`. An `isinstance(g, CohortBreakdown)` branch generates the cohort-specific group entry.

**Rationale**: This follows the same pattern used for `GroupBy` — the builder detects the type and produces the appropriate dict structure. No subclassing or new builder functions needed.

**Alternatives considered**:
- (A) Separate `build_cohort_group_section()` function — rejected because it duplicates list normalization logic and requires callers to merge results
- (B) Make `CohortBreakdown` a subclass of `GroupBy` — rejected because they share zero fields

### R4: How to handle `CohortMetric` in `_build_query_params()`?

**Decision**: Extend the show-clause loop in `_build_query_params()` to detect `CohortMetric` via `isinstance()` and generate the cohort-specific `behavior` dict (`type: "cohort"`, `resourceType: "cohorts"`, `id`/`raw_cohort`). The `events` parameter type widens to include `CohortMetric`.

**Rationale**: The existing loop already branches on `isinstance(item, Metric)` vs `str`. Adding a `CohortMetric` branch is a natural extension. `CohortMetric` is a separate type (not a `Metric` subclass) because it shares no fields with `Metric`.

### R5: Inline `CohortDefinition` — `raw_cohort` field format

**Decision**: When a `CohortDefinition` is passed as the `cohort` argument (instead of `int`), the builder calls `cohort.to_dict()` and places the result in a `raw_cohort` field within the appropriate JSON structure:
- Filters: `filterValue: [{cohort: {raw_cohort: <dict>, name: <str>, negated: false}}]`
- Breakdowns: `cohorts: [{raw_cohort: <dict>, name: <str>, negated: false, ...}]`
- Metrics: `behavior: {raw_cohort: <dict>, ...}` (no `id` field)

**Rationale**: This matches the Mixpanel analytics codebase's `CohortsClause` interface which has both `id` (for saved) and `raw_cohort` (for inline) fields. The `raw_cohort` field is documented in `iron/common/types/reports/bookmark.ts:517-552`.

### R6: Retention mutual exclusivity enforcement

**Decision**: Enforce CB3 (no mixing `CohortBreakdown` with `GroupBy` in retention) in `validate_retention_args()` at Layer 1. The check inspects the `group_by` list and raises if both types are present.

**Rationale**: The Mixpanel API raises an error server-side (`analytics/api/version_2_0/retention/util.py:270-271`), but fail-fast client-side validation provides better error messages and prevents wasted API calls.

### R7: `CohortMetric` — insights-only enforcement

**Decision**: Enforce CM4 via type signatures (CohortMetric is not in `query_funnel()`/`query_retention()`/`query_flow()` parameter types) and via `validate_query_args()` which already type-checks events. If a user bypasses the type system, `_resolve_and_build_params()` will catch it at the type guard.

**Rationale**: Double enforcement (types + runtime) follows the project's fail-fast principle. The type system catches it at IDE time; the runtime guard catches it at execution time.
