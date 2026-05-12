# Implementation Plan: Cohort Definition Builder

**Branch**: `035-cohort-definition-builder` | **Date**: 2026-04-07 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/035-cohort-definition-builder/spec.md`

## Summary

Add `CohortCriteria` and `CohortDefinition` frozen dataclasses to `types.py` that produce valid Mixpanel cohort definition JSON (legacy `selector` + `behaviors` format). These types are the foundation for cohort filter, breakdown, and metric capabilities in Phases 1-3. Phase 0 is standalone — no query method integration yet.

## Technical Context

**Language/Version**: Python 3.10+ (mypy --strict)  
**Primary Dependencies**: Pydantic v2 (for existing `CreateCohortParams`), pandas (existing), Hypothesis (PBT)  
**Storage**: N/A — pure types, no persistence  
**Testing**: pytest + Hypothesis (property-based testing)  
**Target Platform**: Library (PyPI package `mixpanel_data`)  
**Project Type**: Library  
**Performance Goals**: N/A — construction-time only, no runtime performance concerns  
**Constraints**: Must pass `mypy --strict`, `ruff check`, `ruff format`; 90%+ test coverage  
**Scale/Scope**: ~2 new classes, ~7 class methods on `CohortCriteria`, ~4 methods on `CohortDefinition`, ~10 validation rules

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Library-First | Pass | Pure library types — no CLI in Phase 0 |
| II. Agent-Native | Pass | Frozen dataclasses, structured `to_dict()` output, no interactivity |
| III. Context Window Efficiency | Pass | Typed builders reduce token cost vs raw dict construction |
| IV. Two Data Paths | N/A | Type definitions only, no data retrieval |
| V. Explicit Over Implicit | Pass | Fail-fast validation at construction, immutable after creation |
| VI. Unix Philosophy | Pass | Composable building blocks, single responsibility per class |
| VII. Secure by Default | N/A | No credentials involved |

**Result**: All applicable gates pass. No violations to justify.

## Project Structure

### Documentation (this feature)

```text
specs/035-cohort-definition-builder/
├── plan.md              # This file
├── research.md          # Phase 0 output (minimal — design doc covers all decisions)
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
└── contracts/           # Phase 1 output (public API contract)
```

### Source Code (repository root)

```text
src/mixpanel_data/
├── __init__.py              # Add CohortCriteria, CohortDefinition exports
└── types.py                 # Add CohortCriteria, CohortDefinition classes
                             # (after GroupBy at ~line 7649)

tests/
├── unit/
│   └── test_cohort_definition.py    # Unit tests for both classes
└── test_cohort_definition_pbt.py    # Property-based tests (Hypothesis)
```

**Structure Decision**: Minimal footprint — two new classes in existing `types.py`, two new test files. No new modules, packages, or infrastructure changes.
