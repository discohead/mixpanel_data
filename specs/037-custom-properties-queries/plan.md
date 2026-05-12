# Implementation Plan: Custom Properties in Queries

**Branch**: `037-custom-properties-queries` | **Date**: 2026-04-07 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/037-custom-properties-queries/spec.md`

## Summary

Add first-class support for custom properties (saved and inline/ad-hoc) in the unified query system. Three new types (`PropertyInput`, `InlineCustomProperty`, `CustomPropertyRef`) enable custom properties in three query positions: group-by breakdowns, filter conditions, and metric aggregations. All changes are backward-compatible union extensions to existing types (`GroupBy.property`, `Filter._property`, `Metric.property`). Includes 6 validation rules (CP1-CP6), comprehensive test coverage (unit, PBT, mutation), and modular bookmark builders following the established 036-cohort-behaviors patterns.

## Technical Context

**Language/Version**: Python 3.10+ (mypy --strict compliant)
**Primary Dependencies**: Pydantic v2 (validation), httpx (HTTP client), Hypothesis (PBT), mutmut (mutation testing)
**Storage**: N/A — pure query-building types, no persistence
**Testing**: pytest, Hypothesis (property-based), mutmut (mutation testing)
**Target Platform**: Cross-platform Python library + CLI
**Project Type**: Library + CLI
**Performance Goals**: N/A — type construction and JSON generation are negligible cost
**Constraints**: Backward-compatible with all existing code; `just check` must pass (ruff + mypy --strict + pytest)
**Scale/Scope**: ~480 lines production code, ~1,000 lines tests across 4 new test files

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Library-First | PASS | All types are library constructs; no CLI changes needed |
| II. Agent-Native | PASS | Types are self-documenting frozen dataclasses; structured output |
| III. Context Window Efficiency | PASS | Inline definitions avoid round-trip to create/fetch saved CPs |
| IV. Two Data Paths | PASS | Custom properties work in live query path; no storage path changes |
| V. Explicit Over Implicit | PASS | All custom property specs are explicit constructor args; no magic inference |
| VI. Unix Philosophy | PASS | Types compose with existing Filter/GroupBy/Metric ecosystem |
| VII. Secure by Default | PASS | No credentials involved; pure data types |

**Quality Gates**:
- [x] All public functions will have type hints (mypy --strict)
- [x] All public functions will have docstrings with examples
- [x] All new code will pass `ruff check` and `ruff format`
- [x] Tests will exist for all new functionality
- [x] Backward compatibility preserved (union type extensions only)

## Project Structure

### Documentation (this feature)

```text
specs/037-custom-properties-queries/
├── spec.md              # Feature specification
├── plan.md              # This file
├── research.md          # Phase 0: Design decisions and rationale
├── data-model.md        # Phase 1: Entity definitions and bookmark JSON mappings
├── quickstart.md        # Phase 1: Usage examples
├── contracts/
│   └── public-api.md    # Phase 1: Public API surface contract
├── checklists/
│   └── requirements.md  # Specification quality checklist
└── tasks.md             # Phase 2 output (created by /speckit.tasks)
```

### Source Code (repository root)

```text
src/mixpanel_data/
├── __init__.py                    # MODIFIED: Add exports
├── types.py                       # MODIFIED: Add 3 new types + widen existing type signatures
├── workspace.py                   # MODIFIED: Update measurement property builders
└── _internal/
    ├── bookmark_builders.py       # MODIFIED: Add _build_composed_properties(), update filter/group builders
    └── validation.py              # MODIFIED: Add _validate_custom_property(), integrate into 3 pipelines

tests/
├── test_custom_property_types.py      # NEW: Type construction + validation (CP1-CP6)
├── test_custom_property_builders.py   # NEW: Builder output verification
├── test_custom_property_query.py      # NEW: End-to-end query method tests
└── test_custom_property_pbt.py        # NEW: Property-based tests (Hypothesis)
```

**Structure Decision**: Single project extending existing files. Follows the established pattern from 036-cohort-behaviors (no new modules, modular additions to existing files).

## Implementation Phases

### Phase 1: New Types (~150 lines impl, ~200 lines tests)

**Goal**: Establish the three new frozen dataclasses and the PropertySpec type alias.

**Files**: `src/mixpanel_data/types.py`
**Tests first**: `tests/test_custom_property_types.py` — `TestPropertyInput`, `TestInlineCustomProperty`, `TestCustomPropertyRef`

1. Add `PropertyInput` frozen dataclass (name, type, resource_type with defaults)
2. Add `InlineCustomProperty` frozen dataclass (formula, inputs, property_type, resource_type) with `numeric()` classmethod
3. Add `CustomPropertyRef` frozen dataclass (id)
4. Add `PropertySpec` type alias (`str | CustomPropertyRef | InlineCustomProperty`)

**Verify**: All type construction tests pass. Freeze/immutability tests pass.

### Phase 2: Modified Types (~50 lines changes)

**Goal**: Widen type signatures on existing types to accept custom properties.

**Files**: `src/mixpanel_data/types.py`

1. `Metric.property`: `str | None` → `str | CustomPropertyRef | InlineCustomProperty | None`
2. `GroupBy.property`: `str` → `str | CustomPropertyRef | InlineCustomProperty`
3. `Filter._property`: `str` → `str | CustomPropertyRef | InlineCustomProperty`
4. All 18 `Filter` class methods: `property: str` → `property: str | CustomPropertyRef | InlineCustomProperty`

**Verify**: `just typecheck` passes (mypy). Existing tests still pass (backward-compatible).

### Phase 3: Builders (~150 lines impl, ~250 lines tests)

**Goal**: Update bookmark builders to produce correct JSON for all three property types.

**Files**: `src/mixpanel_data/_internal/bookmark_builders.py`, `src/mixpanel_data/workspace.py`
**Tests first**: `tests/test_custom_property_builders.py`

1. Add `_build_composed_properties()` helper function
2. Update `build_filter_entry()` — three-branch isinstance dispatch (str, CustomPropertyRef, InlineCustomProperty)
3. Update `build_group_section()` — three-branch isinstance dispatch in GroupBy case
4. Update measurement property construction in `_build_query_params()` — three-branch isinstance dispatch
5. Update measurement property construction in `_build_funnel_params()` — same pattern
6. Update imports in both files

**Verify**: All builder output tests pass. Existing builder tests still pass.

### Phase 4: Validation (~100 lines impl, ~200 lines tests)

**Goal**: Add 6 validation rules (CP1-CP6) and integrate into all query pipelines.

**Files**: `src/mixpanel_data/_internal/validation.py`
**Tests first**: `tests/test_custom_property_types.py` — `TestCustomPropertyValidation`

1. Add `_validate_custom_property()` helper (CP1-CP6 checks)
2. Integrate into `validate_query_args()` — scan group_by, where, and Metric.property
3. Integrate into `validate_funnel_args()` — scan group_by and where
4. Integrate into `validate_retention_args()` — scan group_by and where
5. Update imports

**Verify**: All validation tests (CP1-CP6) pass. Position-specific validation tests pass.

### Phase 5: End-to-End & Exports (~30 lines impl, ~200 lines tests)

**Goal**: Wire everything together and export new types from the public API.

**Files**: `src/mixpanel_data/__init__.py`
**Tests first**: `tests/test_custom_property_query.py`

1. Add `CustomPropertyRef`, `InlineCustomProperty`, `PropertyInput` to `__init__.py` exports
2. Verify `_resolve_and_build_params()` type guards work with new union types
3. Same for `_resolve_and_build_funnel_params()` and `_resolve_and_build_retention_params()`

**Verify**: All end-to-end tests pass. All existing tests still pass. `just check` green.

### Phase 6: PBT & Polish (~150 lines tests)

**Goal**: Property-based tests, mutation testing, and final quality gate.

**Files**: `tests/test_custom_property_pbt.py`

1. Implement Hypothesis strategies for valid PropertyInput, InlineCustomProperty, CustomPropertyRef
2. Property-based tests for type construction invariants
3. Property-based tests for `_build_composed_properties()` output invariants
4. Run `just test-pbt` — verify PBT passes
5. Run `just test-cov` — verify coverage >= 90%
6. Run `just mutate` on new code — target 80%+ mutation score
7. Final `just check` — all green

## Dependency Graph

```
Phase 1: New Types
    │
    ├─── Phase 2: Modified Types (depends on Phase 1 types)
    │        │
    │        └─── Phase 4: Validation (depends on modified types)
    │
    └─── Phase 3: Builders (depends on Phase 1 types)
             │
             └─── Phase 5: E2E & Exports (depends on builders + validation)
                      │
                      └─── Phase 6: PBT & Polish (depends on everything)
```

Phases 2 and 3 can proceed in parallel after Phase 1 is complete.

## Complexity Tracking

No constitution violations. All changes follow established patterns from 036-cohort-behaviors.
