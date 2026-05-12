# Data Model: Funnel Query (`query_funnel()`)

**Date**: 2026-04-05  
**Feature**: 032-funnel-query

## Input Types

### FunnelStep

A single step in a funnel query. Use plain event name strings when no per-step configuration is needed.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| event | str | (required) | Mixpanel event name |
| label | str or None | None | Display label for this step (defaults to event name) |
| filters | list[Filter] or None | None | Per-step filters |
| filters_combinator | "all" or "any" | "all" | How per-step filters combine (AND/OR) |
| order | "loose" or "any" or None | None | Per-step ordering override (only meaningful with top-level `order="any"`) |

**Immutability**: Frozen dataclass  
**Relationships**: Contains zero or more `Filter` objects (existing type)

### Exclusion

An event to exclude between funnel steps.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| event | str | (required) | Event name to exclude |
| from_step | int | 0 | Start of exclusion range (0-indexed) |
| to_step | int or None | None | End of exclusion range (None = last step) |

**Immutability**: Frozen dataclass  
**Validation**: `from_step` >= 0; `to_step` >= `from_step` when specified

### HoldingConstant

A property to hold constant across all funnel steps.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| property | str | (required) | Property name to hold constant |
| resource_type | "events" or "people" | "events" | Whether this is an event property or user property |

**Immutability**: Frozen dataclass

### FunnelMathType

Type alias for valid funnel aggregation math types.

**Values**: `"conversion_rate_unique"`, `"conversion_rate_total"`, `"conversion_rate_session"`, `"unique"`, `"total"`, `"average"`, `"median"`, `"min"`, `"max"`, `"p25"`, `"p75"`, `"p90"`, `"p99"`

## Output Types

### FunnelQueryResult

Result of a funnel query. Extends `ResultWithDataFrame`.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| computed_at | str | (required) | When the query was computed (ISO format) |
| from_date | str | (required) | Effective start date |
| to_date | str | (required) | Effective end date |
| steps_data | list[dict] | [] | Step-level results: count, step_conv_ratio, overall_conv_ratio, avg_time, avg_time_from_start |
| series | dict | {} | Raw series data from API (for advanced use) |
| params | dict | {} | Generated bookmark params (for debugging/persistence) |
| meta | dict | {} | Response metadata (sampling_factor, is_cached, etc.) |

**Immutability**: Frozen dataclass  
**Computed properties**:
- `overall_conversion_rate` → float: End-to-end conversion from step 1 to last step
- `df` → DataFrame: One row per step with columns: step, event, count, step_conv_ratio, overall_conv_ratio, avg_time, avg_time_from_start

## Entity Relationships

```
FunnelStep (input)
  └── contains → Filter (existing, 0..N)

Exclusion (input, standalone)

HoldingConstant (input, standalone)

query_funnel() accepts:
  ├── steps: list[str | FunnelStep]  (2+ required)
  ├── exclusions: list[str | Exclusion] | None
  ├── holding_constant: str | HoldingConstant | list[...] | None
  ├── where: Filter | list[Filter] | None  (existing)
  ├── group_by: str | GroupBy | list[...] | None  (existing)
  └── returns → FunnelQueryResult (output)
```

## Validation Rules

| Code | Entity | Rule |
|------|--------|------|
| F1 | steps | At least 2 steps required |
| F2 | FunnelStep | Each step event must be non-empty string |
| F3 | conversion_window | Must be positive integer |
| F4 | Exclusion | Exclusion event name must be non-empty |
| F5 | time args | Reuses V7-V11, V15, V20 from shared validators |
| F6 | group_by args | Reuses V11-V12 from shared validators |

## Coexistence with Existing Types

| Existing Type | Purpose | Relationship to New Types |
|---------------|---------|---------------------------|
| `FunnelResult` | Legacy funnel API result (`ws.funnel()`) | Separate — different API path, different response format |
| `FunnelResult.FunnelStep` (nested) | Step in legacy result (step_number, event, count, rate) | Different concept — result step vs. input step |
| `Filter` | Shared filter type | Reused in `FunnelStep.filters` and `query_funnel(where=...)` |
| `GroupBy` | Shared group-by type | Reused in `query_funnel(group_by=...)` |
| `QueryResult` | Insights bookmark result | Sibling — `FunnelQueryResult` follows same pattern |
