# Research: Unified Query Engine Completeness

**Date**: 2026-04-14
**Feature**: 040-query-engine-completeness

## Summary

All NEEDS CLARIFICATION items are resolved. Codebase exploration and power-tools reference analysis confirm all 29 gaps and their implementations. One discrepancy found and resolved.

---

## Decision Log

### D1: TimeComparison JSON Location

**Decision**: Place in `displayOptions.timeComparison`
**Rationale**: Power-tools (`bookmark-validator.js:761-790`, `mixpanel-bookmark-typedefs.d.ts:62-77`) consistently places `timeComparison` inside `displayOptions`. The audit report states "params.timeComparison (top-level, alongside sections)" which may reflect an older or alternative server parsing path. The power-tools implementation is the canonical, battle-tested reference.
**Alternatives considered**: Top-level `params.timeComparison` per audit report. Rejected because power-tools' validator tests confirm `displayOptions` location.
**Action**: Implement in `displayOptions`. Add a test that verifies the server accepts it.

### D2: Segment Method Values

**Decision**: Support only `"all"` and `"first"` (2 values)
**Rationale**: Server-side `_validate_segment_method()` in `analytics/backend/arb/params.py` explicitly rejects any value other than "first" and "all". Power-tools incorrectly accepts "last" — this is a confirmed bug in power-tools, not a feature.
**Alternatives considered**: Including "last" for power-tools compatibility. Rejected because the server rejects it.

### D3: FunnelReentryMode Default

**Decision**: Default to `None` (omit from JSON) rather than `"basic"` or `"default"`
**Rationale**: Power-tools builders default to `"basic"`, but the server documentation indicates that if the field is absent, server assumes `"default"` behavior. Using `None` preserves backward compatibility — existing queries produce identical JSON. Users explicitly opt in.
**Alternatives considered**: Default to `"basic"` (power-tools pattern). Rejected to maintain backward compatibility per FR-029.

### D4: MATH_REQUIRING_PROPERTY Updates

**Decision**: Add `unique_values`, `most_frequent`, `first_value`, `multi_attribution`, `numeric_summary` to `MATH_REQUIRING_PROPERTY`
**Rationale**: Audit report confirms all 5 require a property. The existing `MATH_REQUIRING_PROPERTY` set in `bookmark_enums.py` is missing these because the MathType Literal didn't include them — expanding the Literal means the validation set must also expand.
**Alternatives considered**: None. This is a factual correctness update.

### D5: FrequencyBreakdown vs Extending GroupBy

**Decision**: Create a dedicated `FrequencyBreakdown` frozen dataclass rather than extending `GroupBy`
**Rationale**: Frequency breakdowns have fundamentally different semantics from property breakdowns: they require an event name (not a property name), use `behaviorType: "$frequency"`, force `resourceType: "people"`, and have a different JSON structure. Extending GroupBy would conflate two distinct concepts.
**Alternatives considered**: Adding `behavior_type` field to `GroupBy`. Rejected because it would weaken the type's semantics and require complex conditional validation.

### D6: FrequencyFilter vs Extending Filter

**Decision**: Create a dedicated `FrequencyFilter` frozen dataclass rather than extending `Filter`
**Rationale**: Frequency filters have a `customProperty` block with behavioral semantics that doesn't map to Filter's property-operator-value model. The JSON structure is significantly different (nested `customProperty.behavior` with event, aggregation, date range). A dedicated type keeps the Filter class focused.
**Alternatives considered**: Adding frequency-specific factory methods to Filter. Rejected because the internal structure diverges too much from Filter's model.

### D7: FlowStep Session Events

**Decision**: Add a `session_event` field to `FlowStep` as `Literal["start", "end"] | None`
**Rationale**: Power-tools uses `SESSION_EVENT_MAP` to translate `$session_start` → `"start"` and `$session_end` → `"end"`, setting `session_event` instead of `event`. The two fields are mutually exclusive. Adding a dedicated field keeps the type explicit.
**Alternatives considered**: Auto-detecting `$session_start`/`$session_end` event names and mapping them. Rejected because implicit magic violates Constitution Principle V (Explicit Over Implicit).

### D8: Flow Global Property Filters Implementation

**Decision**: Accept property filters in `where` parameter alongside cohort filters for flows, using `filter_by_event` key in params
**Rationale**: Currently `where` on flows only accepts cohort filters (via `build_flow_cohort_filter()`). Power-tools supports both `filter_by_cohort` and `filter_by_event`. Property filters use a different structure: `{"operator": "and", "children": [...]}`.
**Alternatives considered**: Separate `property_filter` parameter. Rejected to keep the API surface consistent — `where` already serves as the filter parameter.

### D9: CohortCriteria Aggregation Property Type

**Decision**: `aggregation_property: str` (plain property name)
**Rationale**: Power-tools' `buildRawCohort()` uses a plain event property name string in the `behavior.property` field. Custom property references are not supported in cohort behavioral conditions.
**Alternatives considered**: Supporting `CustomPropertyRef` for aggregation property. Rejected because cohort behavioral conditions don't support custom properties on the server.

---

## Codebase Findings

### Current State of Key Files

| File | Current State | Changes Needed |
|------|--------------|---------------|
| `_literal_types.py` | MathType: 15 values, RetentionMathType: 2, FunnelMathType: 13 | +7 to MathType, +2 to RetentionMathType, +1 to FunnelMathType, +5 new Literal types |
| `types.py` | Metric (7 fields), Filter (22 factory methods), CohortCriteria.did_event (13 params), FlowStep (6 fields) | +1 Metric field, +7 Filter methods, +2 CohortCriteria params, +1 FlowStep field, +3 new dataclasses |
| `workspace.py` | query (20 params), query_funnel (16 params), query_retention (13 params), query_flow (15 params) | +1-3 params per method, same for build_* variants |
| `bookmark_builders.py` | 5 dataGroupId=None hardcodings, no time comparison, no frequency builders | Thread data_group_id, add time comparison builder, add frequency builders |
| `bookmark_enums.py` | MATH_REQUIRING_PROPERTY missing 5 values, no reentry/unbounded enums | Update MATH_REQUIRING_PROPERTY, add new enum sets |
| `validation.py` | validate_query_args, validate_funnel_args, validate_retention_args, validate_flow_args | Add validation for new params in each function |

### Power-Tools Reference Summary

| Feature | JSON Path | Valid Values | Default |
|---------|-----------|-------------|---------|
| Funnel reentry mode | `show[0].behavior.funnelReentryMode` | default, basic, aggressive, optimized | None (server assumes default) |
| Retention unbounded mode | `show[0].behavior.retentionUnboundedMode` | none, carry_back, carry_forward, consecutive_forward | None (server assumes none) |
| Retention cumulative | `show[0].measurement.retentionCumulative` | true, false | false |
| Segment method | `show[0].measurement.segmentMethod` | all, first | None (server assumes all) |
| Time comparison | `displayOptions.timeComparison` | Discriminated union (3 types) | None (no comparison) |
| Frequency breakdown | `group[].behavior.behaviorType` | "$frequency" sentinel | N/A (new type) |
| Frequency filter | `filter[].customProperty.behavior` | Behavioral filter structure | N/A (new type) |
| Flow session event | `steps[].session_event` | start, end | N/A (use event field) |
| Cohort aggregation | `behavior.aggregationOperator` | total, unique, average, min, max, median | total |

---

## Dependency Analysis

### No External Dependencies Required

All changes are type expansions, parameter additions, and builder updates. No new pip dependencies needed.

### Internal Dependencies (Build Order)

```
Phase A: _literal_types.py → bookmark_enums.py → types.py → bookmark_builders.py → validation.py → workspace.py
Phase B: types.py (new classes) → bookmark_builders.py (new builders) → validation.py → workspace.py  
Phase C: bookmark_builders.py (threading) → workspace.py (threading)
```

Within each phase, the dependency chain is: Literal types → Enum constants → Dataclasses/types → Builders → Validators → Workspace methods.
