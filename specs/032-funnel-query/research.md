# Research: Funnel Query (`query_funnel()`)

**Date**: 2026-04-05  
**Feature**: 032-funnel-query

## Research Questions

### RQ-1: Can funnel bookmark params reuse the existing `insights_query()` API path?

**Decision**: Yes — reuse `insights_query()` without modification.

**Rationale**: The Mixpanel insights API detects `behavior.type == "funnel"` in the bookmark params and internally delegates to the funnels query engine (`arb_funnels` service). This is confirmed in the design document (Section 3.6) and by the existing `_transform_saved_report()` logic in `live_query.py` which already handles funnel responses from the insights endpoint.

**Alternatives considered**:
- New `funnel_insights_query()` API client method — rejected because the endpoint and request format are identical; only the bookmark params structure differs.

### RQ-2: Should `FunnelQueryResult` reuse or replace the existing `FunnelResult` type?

**Decision**: Create a new `FunnelQueryResult` type alongside the existing `FunnelResult`.

**Rationale**: The two serve different purposes:
- `FunnelResult` (existing, `types.py:400-465`) wraps the legacy funnel API response from `ws.funnel(funnel_id)`. It has `funnel_id`, `funnel_name`, and uses a `FunnelStep` dataclass with `step_number`, `event`, `count`, `conversion_rate` fields.
- `FunnelQueryResult` (new) wraps the bookmark-based insights API response with richer structure: `steps_data`, `series`, `computed_at`, timing data (`avg_time`, `avg_time_from_start`), and the `.params` dict for debugging.

**Note**: The existing `FunnelStep` in `types.py` is a *result* step (step number, event name, count, conversion rate). The new `FunnelStep` from the design doc is an *input* step (event name, label, per-step filters, ordering). These are semantically different and should have different names to avoid confusion.

**Name resolution**: The new input type will be `FunnelStep` (matching the design doc). The existing result-step class will need to be checked — if it's also named `FunnelStep`, one must be renamed. Based on research, the existing result step is a nested dataclass inside `FunnelResult` and can be referenced as-is since the new `FunnelStep` is a top-level public type.

### RQ-3: What is the exact response format for funnel bookmark queries via the insights API?

**Decision**: The response follows the standard insights wrapper but `series` contains funnel step data.

**Rationale**: From the design document (Section 7.1) and `_transform_saved_report()` in `live_query.py`:
- Response shape: `{computed_at, date_range, headers, series, meta}`
- `series` contains step arrays with `count`, `step_conv_ratio`, `overall_conv_ratio`, `avg_time` per step
- The `date_range` dict has `from_date` and `to_date` strings
- `meta` may contain `sampling_factor`, `is_cached`, etc.

The transform function needs to extract step data from `series` and populate `FunnelQueryResult.steps_data`.

### RQ-4: How should `_build_funnel_params()` generate the behavior structure?

**Decision**: Build the behavior dict directly in `_build_funnel_params()`, reusing shared builders for sections.

**Rationale**: The funnel behavior structure (design doc Appendix A.2) has a unique shape that doesn't share enough with insights to warrant a generic builder. The key structure is:
```python
{
    "sections": {
        "show": [{
            "behavior": {
                "type": "funnel",
                "behaviors": [...],  # per-step entries
                "conversionWindowDuration": N,
                "conversionWindowUnit": "day",
                "funnelOrder": "loose",
                "exclusions": [...],
                "aggregateBy": [...],
                ...
            },
            "measurement": {"math": "conversion_rate_unique", ...},
        }],
        "filter": build_filter_section(where),   # reuse
        "group": build_group_section(group_by),   # reuse
        "time": build_time_section(...),          # reuse
        "formula": [],
    },
    "displayOptions": {"chartType": "funnel-steps", ...},
}
```

### RQ-5: Where should `validate_funnel_args()` live?

**Decision**: Add to `validation.py` alongside `validate_query_args()`.

**Rationale**: All Layer 1 validators live in `validation.py`. The funnel validator will reuse `validate_time_args()` and `validate_group_by_args()` (already extracted) and add funnel-specific rules F1-F6.

### RQ-6: How should the `_resolve_and_build_funnel_params()` pipeline work?

**Decision**: Follow the same pattern as `_resolve_and_build_params()` but with funnel-specific validation and builder.

**Pipeline**:
1. Normalize `steps` (strings → `FunnelStep` objects)
2. Normalize `where`, `exclusions`, `holding_constant`
3. Layer 1: `validate_funnel_args()` — rules F1-F6 + reused time/group-by validators
4. Build: `_build_funnel_params()` — generates funnel bookmark JSON
5. Layer 2: `validate_bookmark(params, bookmark_type="funnels")`
6. Return validated params

### RQ-7: What `displayOptions.chartType` values map to each funnel `mode`?

**Decision**: Map based on design document Section A.6:
- `mode="steps"` → `chartType="funnel-steps"` (default)
- `mode="trends"` → `chartType="line"`
- `mode="table"` → `chartType="table"`

## Summary

No unresolved questions. All design decisions are confirmed by existing codebase patterns and the unified bookmark query design document.
