# Public API Contract: Funnel Query

**Date**: 2026-04-05  
**Feature**: 032-funnel-query

## New Public Types

### FunnelStep

```
FunnelStep(event, label=None, filters=None, filters_combinator="all", order=None)
```

- Frozen dataclass, importable from `mixpanel_data`
- `event`: non-empty string (required)
- `label`: optional string
- `filters`: optional list of `Filter`
- `filters_combinator`: `"all"` or `"any"`
- `order`: `"loose"`, `"any"`, or `None`

### Exclusion

```
Exclusion(event, from_step=0, to_step=None)
```

- Frozen dataclass, importable from `mixpanel_data`
- `event`: non-empty string (required)
- `from_step`: non-negative integer, default 0
- `to_step`: non-negative integer or None (None = last step)

### HoldingConstant

```
HoldingConstant(property, resource_type="events")
```

- Frozen dataclass, importable from `mixpanel_data`
- `property`: non-empty string (required)
- `resource_type`: `"events"` or `"people"`

### FunnelMathType

Type alias (Literal) for valid funnel math types:
`"conversion_rate_unique"`, `"conversion_rate_total"`, `"conversion_rate_session"`, `"unique"`, `"total"`, `"average"`, `"median"`, `"min"`, `"max"`, `"p25"`, `"p75"`, `"p90"`, `"p99"`

### FunnelQueryResult

```
FunnelQueryResult(computed_at, from_date, to_date, steps_data=[], series={}, params={}, meta={})
```

- Frozen dataclass extending `ResultWithDataFrame`
- `.overall_conversion_rate` → float (computed property)
- `.df` → DataFrame with columns: step, event, count, step_conv_ratio, overall_conv_ratio, avg_time, avg_time_from_start

## New Public Methods on Workspace

### query_funnel()

```
ws.query_funnel(
    steps,                              # list[str | FunnelStep], 2+ required
    *,
    conversion_window=14,               # positive int
    conversion_window_unit="day",       # second|minute|hour|day|week|month|session
    order="loose",                      # loose|any
    from_date=None,                     # str (YYYY-MM-DD) or None
    to_date=None,                       # str (YYYY-MM-DD) or None
    last=30,                            # positive int (days)
    unit="day",                         # hour|day|week|month|quarter
    math="conversion_rate_unique",      # FunnelMathType
    group_by=None,                      # str|GroupBy|list or None
    where=None,                         # Filter|list[Filter] or None
    exclusions=None,                    # list[str|Exclusion] or None
    holding_constant=None,              # str|HoldingConstant|list or None
    mode="steps",                       # steps|trends|table
) -> FunnelQueryResult
```

**Error behavior**: Raises `BookmarkValidationError` for invalid inputs (before API call).

### build_funnel_params()

```
ws.build_funnel_params(
    steps, *, ...same keyword args as query_funnel...
) -> dict
```

Same signature as `query_funnel()` but returns validated bookmark params dict without executing. Raises `BookmarkValidationError` for invalid inputs.

## Exports

All new types and type aliases MUST be added to `__init__.py` and `__all__`:
- `FunnelStep`, `Exclusion`, `HoldingConstant`
- `FunnelMathType`
- `FunnelQueryResult`

## Error Contract

All validation errors raise `BookmarkValidationError` (existing type) containing a list of `ValidationError` objects (existing type). Each error has:
- `path`: location in params where error was found
- `message`: human-readable description
- `code`: error code (F1-F6 for funnel args, B1-B19 for bookmark structure)
- `severity`: `"error"` or `"warning"`
- `suggestion`: optional fix suggestion

## Backward Compatibility

- No existing public methods are modified
- No existing types are renamed or removed
- The existing `FunnelResult` and `Workspace.funnel()` continue to work unchanged
- The existing `QueryResult` and `Workspace.query()` continue to work unchanged
