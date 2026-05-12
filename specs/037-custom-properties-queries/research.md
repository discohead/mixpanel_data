# Research: Custom Properties in Queries

**Feature**: 037-custom-properties-queries
**Date**: 2026-04-07

## R1: How should custom properties be represented in the type system?

**Decision**: Three frozen dataclasses — `PropertyInput`, `InlineCustomProperty`, `CustomPropertyRef` — plus a `PropertySpec` type alias for the union.

**Rationale**: Follows the established pattern from 036-cohort-behaviors where `CohortBreakdown` and `CohortMetric` are frozen dataclasses. Frozen dataclasses provide immutability, fail-fast `__post_init__` validation, and are compatible with mypy --strict. The three-type split mirrors Mixpanel's own distinction: raw property inputs (composedProperties entries), inline formulas (ephemeral custom properties), and saved references (customPropertyId).

**Alternatives considered**:
- Single `CustomProperty` class with discriminated union: Rejected because saved refs and inline definitions have fundamentally different fields and JSON outputs.
- Subclassing `GroupBy`/`Filter`/`Metric`: Rejected because custom properties are orthogonal to these types — they're a property specification, not a query dimension.
- Plain dicts: Rejected because they lack type safety, discoverability, and validation.

## R2: How should existing types be widened to accept custom properties?

**Decision**: Widen the `property` field type on `Metric`, `GroupBy`, and `Filter` from `str` to `str | CustomPropertyRef | InlineCustomProperty`. Use `isinstance()` dispatch in builders.

**Rationale**: Union type widening is the same approach used for `Filter._value` in 036 (widened to accept `list[dict[str, Any]]` for cohort filters). It's backward-compatible (existing `str` calls still work), requires no API changes for consumers, and `isinstance()` dispatch in builders is the established pattern.

**Alternatives considered**:
- Separate methods (e.g., `query_with_custom_property()`): Rejected — breaks the unified query API design.
- Wrapper types (e.g., `CustomGroupBy`): Rejected — creates parallel hierarchies; custom properties are a property spec, not a new dimension type.
- String encoding (e.g., `"custom:42"`): Rejected — not type-safe, not discoverable, error-prone.

## R3: Where should bookmark JSON generation live?

**Decision**: Extend existing builder functions in `_internal/bookmark_builders.py` with three-branch `isinstance()` dispatch. Add a shared `_build_composed_properties()` helper for `PropertyInput` → JSON conversion.

**Rationale**: Follows the same pattern as 036 which extended `build_filter_entry()` and `build_group_section()` with cohort branches. Keeping builder logic in the existing functions maintains the single-responsibility principle — each builder function owns its section of the bookmark JSON. The `_build_composed_properties()` helper is DRY (used in filters, group-by, and measurements).

**Alternatives considered**:
- Separate builder module for custom properties: Rejected — fragments bookmark generation across modules.
- Method on the types themselves (e.g., `InlineCustomProperty.to_bookmark_dict()`): Rejected — types should be pure data; bookmark format is an infrastructure concern.

## R4: How should validation be structured?

**Decision**: A single `_validate_custom_property()` helper in `validation.py` with 6 rules (CP1-CP6), called from `validate_query_args()`, `validate_funnel_args()`, and `validate_retention_args()`.

**Rationale**: Follows the exact pattern of `_validate_cohort_args()` from 036. Central helper with coded rules (CP1-CP6) provides structured error reporting, machine-readable codes, and consistent validation across all pipelines. Fail-fast at query-build time (before API call) follows the established two-layer validation architecture.

**Alternatives considered**:
- Validation in `__post_init__()`: Partially used — `CustomPropertyRef(0)` could fail at construction. But validation of a custom property *in context* (e.g., "is this in a valid position?") requires the query-level validator. Design doc specifies validation at query-build time.
- No client-side validation: Rejected — server errors are opaque and waste API calls.

## R5: What bookmark JSON format do custom properties use?

**Decision**: Three distinct JSON shapes based on property type:
- Plain string: `{"value": "prop_name", "propertyName": "prop_name", "resourceType": "events", ...}` (unchanged)
- `CustomPropertyRef`: `{"customPropertyId": 42, "propertyType": "number", ...}` (no `value`/`propertyName`)
- `InlineCustomProperty`: `{"customProperty": {"displayFormula": "...", "composedProperties": {...}, "propertyType": "...", "resourceType": "..."}, ...}` (no `value`/`propertyName`)

**Rationale**: Based on the analytics reference implementation (`arb_selector.py`, `bookmark.ts`). The Mixpanel webapp uses these exact JSON shapes when users create custom property breakdowns, filters, and measurements. Verified against the reference codebase.

**Alternatives considered**: None — the bookmark format is dictated by the Mixpanel API server.

## R6: Should `PropertyInput.resource_type` use singular or plural?

**Decision**: `PropertyInput.resource_type` uses singular (`"event"`, `"user"`) while `InlineCustomProperty.resource_type` uses plural (`"events"`, `"people"`).

**Rationale**: This matches Mixpanel's schema convention at each level. The `composedProperties` entries (derived from `PropertyInput`) use singular `"event"`/`"user"` in the `resourceType` field. The top-level `customProperty` dict (derived from `InlineCustomProperty`) uses plural `"events"`/`"people"`. This inconsistency exists in the Mixpanel API itself — the library faithfully reflects it rather than papering over it.

**Alternatives considered**:
- Normalize to one convention: Rejected — would produce incorrect bookmark JSON that the server rejects.

## R7: How should `InlineCustomProperty.property_type` interact with `GroupBy.property_type`?

**Decision**: When `InlineCustomProperty.property_type` is set, it takes precedence over `GroupBy.property_type`. When it's `None`, the builder falls back to `GroupBy.property_type`.

**Rationale**: The inline custom property knows its own result type better than the containing GroupBy. For example, `IFS(A > 1000, "Enterprise", A > 100, "Pro", TRUE, "Free")` produces a string even if used in a GroupBy with `property_type="number"`. The fallback to GroupBy's type when `property_type` is `None` provides a reasonable default when the user doesn't specify the result type.

**Alternatives considered**:
- Always require `property_type`: Rejected — adds friction for the common case where the type matches the containing dimension.
- Always use GroupBy's type: Rejected — would produce incorrect types for formulas that change the type (e.g., numeric input → string bucketing).
