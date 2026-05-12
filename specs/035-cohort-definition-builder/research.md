# Research: Cohort Definition Builder

**Date**: 2026-04-07  
**Status**: Complete — all decisions resolved by design document

## Summary

No NEEDS CLARIFICATION items exist. The design document (`context/cohort-behaviors-design.md`) thoroughly researched the Mixpanel analytics codebase and resolved all technical decisions before this feature specification was created.

## Decisions

### 1. Cohort Definition Format

**Decision**: Generate the legacy `selector` + `behaviors` format.  
**Rationale**: Universal compatibility — works in both `create_cohort()` and inline `raw_cohort` query references. The backend parses it natively without conversion. The modern `groups` format is a UI abstraction that the backend converts to `selector` + `behaviors` anyway.  
**Alternatives considered**: Modern `groups` format — rejected because it's not accepted in all code paths (particularly `raw_cohort` inline references).

### 2. Behavior Count Type

**Decision**: Default to `"absolute"` (total count across window).  
**Rationale**: Covers the vast majority of use cases. Per-day frequency (`"day"`) is a niche feature that can be added later without breaking changes.  
**Alternatives considered**: Supporting both `"absolute"` and `"day"` in v1 — rejected to minimize scope.

### 3. Behavior Key Strategy

**Decision**: Use `bhvr_N` keys with global re-indexing during `to_dict()`.  
**Rationale**: Each `CohortCriteria.did_event()` creates a placeholder key. When `CohortDefinition.to_dict()` serializes the tree, it re-indexes all behavior keys sequentially (`bhvr_0`, `bhvr_1`, ...) and updates the corresponding selector node references. This ensures uniqueness across arbitrary nesting.  
**Alternatives considered**: UUID-based keys — rejected because Mixpanel's backend expects `bhvr_N` pattern. Pre-allocated sequential keys — rejected because nesting makes pre-allocation impractical.

### 4. Filter-to-Event-Selector Conversion

**Decision**: Read `Filter` internal fields (`_property`, `_operator`, `_value`, `_property_type`) and map to event selector expression tree format.  
**Rationale**: Reuses the existing `Filter` class without modification. The operator mapping is a simple dict lookup (e.g., `"equals"` → `"=="`, `"is greater than"` → `">`).  
**Alternatives considered**: Adding a `to_selector()` method to `Filter` — rejected to avoid coupling Filter to cohort-specific concerns.

### 5. Validation Strategy

**Decision**: Fail-fast at construction time using `ValueError`, not the `ValidationError` collector pattern.  
**Rationale**: Follows the `Filter._validate_date()` precedent. The collector pattern (`validate_query_args()`) is for Layer 1/Layer 2 bookmark validation where multiple errors are useful. For type construction, immediate `ValueError` is simpler and more Pythonic.  
**Alternatives considered**: Using `ValidationError` with codes — deferred to Phases 1-3 where cohort parameters are validated as part of bookmark construction.

### 6. Class Placement

**Decision**: Both classes go in `types.py` after `GroupBy` (~line 7649).  
**Rationale**: Follows the established pattern — `Metric`, `Formula`, `Filter`, `GroupBy` are all in `types.py`. No new modules needed. Helper functions (`_build_selector_tree`, `_build_event_selector`) are private module-level functions in the same file.  
**Alternatives considered**: Separate `cohort_types.py` module — rejected because it breaks the single-import pattern and creates artificial separation.

### 7. Operator Mapping Table

**Decision**: Use a module-level `_PROPERTY_OPERATOR_MAP` dict for `has_property()` operator-to-selector mapping.

| `CohortCriteria` operator | Selector operator |
|---------------------------|-------------------|
| `"equals"` | `"=="` |
| `"not_equals"` | `"!="` |
| `"contains"` | `"in"` |
| `"not_contains"` | `"not in"` |
| `"greater_than"` | `">"` |
| `"less_than"` | `"<"` |
| `"is_set"` | `"defined"` |
| `"is_not_set"` | `"not defined"` |

**Rationale**: Explicit mapping dict is testable and discoverable. Follows the pattern of `VALID_FILTER_OPERATORS` in `bookmark_enums.py`.

### 8. Filter Operator Mapping for Event Selectors

**Decision**: Use a separate `_FILTER_TO_SELECTOR_MAP` dict for converting `Filter._operator` strings to event selector operators.

| `Filter._operator` | Event selector operator |
|---------------------|------------------------|
| `"equals"` | `"=="` |
| `"does not equal"` | `"!="` |
| `"contains"` | `"in"` |
| `"does not contain"` | `"not in"` |
| `"is greater than"` | `">"` |
| `"is less than"` | `"<"` |
| `"is set"` | `"defined"` |
| `"is not set"` | `"not defined"` |
| `"is between"` | `"between"` |

**Rationale**: `Filter` uses human-readable operator strings (e.g., `"is greater than"`) while event selectors use symbolic operators (e.g., `">"`). The mapping is a direct translation.
