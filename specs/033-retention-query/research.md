# Research: Retention Query (`query_retention()`)

**Date**: 2026-04-06
**Status**: Complete — all decisions resolved

## Overview

All design decisions for the retention query system were resolved during the unified bookmark query design phase (see `context/unified-bookmark-query-design.md` §4, §9). This research document consolidates the findings and confirms implementation-level details through codebase analysis.

## Decision 1: API Endpoint

**Decision**: Reuse the existing `/insights` endpoint via `insights_query()` API client method.

**Rationale**: The Mixpanel insights API internally detects `behavior.type == "retention"` in the bookmark params and routes to the retention query engine. This is confirmed by the design document (§4.6) and consistent with how `query_funnel()` already works — both funnel and retention bookmarks use `/insights`, not separate endpoints.

**Alternatives considered**:
- Direct `/retention` endpoint: Not available — Mixpanel's retention service is accessed only through the insights dispatcher.
- New API client method: Unnecessary — `insights_query()` accepts any bookmark params dict; the behavior type determines routing.

## Decision 2: Bookmark JSON Structure

**Decision**: Use `sections`-based structure with `behavior.type = "retention"` containing exactly 2 behaviors (born event, return event) and retention-specific fields.

**Rationale**: Confirmed by design document §4.5 (Appendix A.3). The retention behavior block differs from funnel in:
- Exactly 2 behaviors (born + return) vs N steps
- `retentionUnit` instead of `conversionWindowDuration`/`conversionWindowUnit`
- `retentionCustomBucketSizes` instead of exclusions
- `retentionAlignmentType` instead of `funnelOrder`
- No `aggregateBy` (holding constant is funnel-only)

**Alternatives considered**: None — the bookmark format is dictated by the Mixpanel API.

## Decision 3: Shared Infrastructure

**Decision**: Reuse all shared builders and validators without modification.

**Rationale**: Verified through codebase analysis:
- `build_time_section()` (bookmark_builders.py:19-74): Works for all `sections.time[]` formats — retention uses same structure.
- `build_filter_section()` / `build_filter_entry()` (bookmark_builders.py:120-253): Works for `sections.filter[]` — retention uses same structure.
- `build_group_section()` (bookmark_builders.py:148-217): Works for `sections.group[]` — retention uses same structure.
- `validate_time_args()` (validation.py:169-305): Validates V7-V10, V15, V20 — all apply to retention.
- `validate_group_by_args()` (validation.py:308-423): Validates V11-V12, V18, V24 — all apply to retention.
- `validate_bookmark()` (validation.py:1143-1257): Already accepts `bookmark_type` parameter. Currently branches on `"funnels"` to select `VALID_MATH_FUNNELS`; adding `"retention"` → `VALID_MATH_RETENTION` is a single conditional.

**Alternatives considered**: None — reuse is the entire design principle of the shared infrastructure.

## Decision 4: Retention-Specific Enums

**Decision**: Use existing enum constants in `bookmark_enums.py`.

**Rationale**: All required constants already exist:
- `VALID_MATH_RETENTION` (L118-126): `{"unique", "retention_rate", "total", "average"}`
- `VALID_RETENTION_UNITS` (L426): `{"day", "week", "month"}`
- `VALID_RETENTION_ALIGNMENT` (L429-430): `{"birth", "interval_start"}`
- `VALID_CHART_TYPES` (L262-275): Already includes `"retention-curve"` and `"frequency-curve"`
- `VALID_METRIC_TYPES` (L242-255): Already includes `"retention"`

No new enum constants are needed.

## Decision 5: RetentionMathType Scope

**Decision**: Expose `Literal["retention_rate", "unique"]` as `RetentionMathType` — a 2-value type alias.

**Rationale**: The design document (§4.3) specifies these two values. While `VALID_MATH_RETENTION` in bookmark_enums also includes `"total"` and `"average"`, those are internal bookmark-level math types used by the L2 validator. The public-facing `RetentionMathType` should expose only the user-meaningful values:
- `"retention_rate"` — percentage of cohort retained (default)
- `"unique"` — raw unique user count per bucket

**Alternatives considered**:
- Include `"total"` and `"average"`: These are less useful for retention queries and could confuse users. The L2 validator still accepts them in the bookmark params if users construct params manually.

## Decision 6: Response Format

**Decision**: Parse cohort data from the `series` field of the insights API response, handling multiple format variations.

**Rationale**: Based on the funnel precedent (`_extract_funnel_steps_from_series` handles 5+ format variations), the retention response parser should handle:
1. Direct cohort dict: `series = {cohort_date: {first, counts, rates}}`
2. Nested with `$overall`: `series = {"$overall": {cohort_data}}`
3. Segmented format: `series = {segment_value: {cohort_data}}`
4. Insights API wrapper: `series = {metric_name: {nested_data}}`

The transformer will extract the `$average` synthetic cohort separately.

## Decision 7: DataFrame Shape

**Decision**: `cohort_date, bucket, count, rate` — one row per (cohort, bucket) pair.

**Rationale**: This is the most flexible shape for downstream analysis. Users can pivot, filter, or aggregate as needed. Consistent with the funnel DataFrame pattern (one row per step) and the insights DataFrame pattern (one row per date/metric).

**Alternatives considered**:
- Wide format (one column per bucket): Harder to filter and less composable with pandas operations.
- Separate DataFrames for counts and rates: Unnecessarily splits related data.

## Decision 8: Custom Bucket Sizes Validation

**Decision**: Validate that `bucket_sizes` is a list of positive integers in strictly ascending order.

**Rationale**: Design document §9.5 specifies this. Duplicate values would create overlapping buckets. Non-positive values are meaningless for retention periods. Non-ascending order contradicts the natural progression of retention periods.

**Validation rules**:
- R5: Each value must be a positive integer (`> 0`)
- R6: Values must be in strictly ascending order (no duplicates)
