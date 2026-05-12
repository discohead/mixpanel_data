# Implementation Plan: Cohort Behaviors in Unified Query System

**Branch**: `036-cohort-behaviors` | **Date**: 2026-04-06 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/036-cohort-behaviors/spec.md`

## Summary

Add three cross-cutting cohort capabilities to the unified query system: cohort filters (`Filter.in_cohort()`), cohort breakdowns (`CohortBreakdown`), and cohort metrics (`CohortMetric`). Each accepts both saved cohort IDs (`int`) and inline `CohortDefinition` objects. Extends shared infrastructure (`bookmark_builders.py`, `validation.py`, `workspace.py`, `types.py`) so all existing query methods gain cohort capabilities simultaneously.

## Technical Context

**Language/Version**: Python 3.10+ (mypy --strict)
**Primary Dependencies**: Pydantic v2 (validation), httpx (HTTP), pandas (DataFrames), Hypothesis (PBT)
**Storage**: N/A — live query only, no local persistence
**Testing**: pytest, Hypothesis (property-based), mutmut (mutation)
**Target Platform**: Cross-platform Python library + CLI
**Project Type**: Library + CLI
**Performance Goals**: N/A — type construction and JSON serialization only; no API latency concerns
**Constraints**: Must maintain backward compatibility with all existing query method signatures
**Scale/Scope**: ~4 files modified, ~2 new types added, ~15 new validation rules

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Library-First | PASS | All cohort capabilities are library types/methods; CLI is unaffected |
| II. Agent-Native | PASS | New types are non-interactive frozen dataclasses; structured output |
| III. Context Window Efficiency | PASS | Types produce minimal JSON; no data dumps |
| IV. Two Data Paths | PASS | Extends live query path only; no storage changes |
| V. Explicit Over Implicit | PASS | Fail-fast validation; no hidden defaults; `CohortMetric` always uses `math="unique"` explicitly |
| VI. Unix Philosophy | PASS | Composable types; output unchanged |
| VII. Secure by Default | PASS | No credential handling; pure type construction |
| Quality Gates | PASS | All code will have type hints, docstrings, ruff/mypy compliance, tests |

No violations. No complexity tracking needed.

## Project Structure

### Documentation (this feature)

```text
specs/036-cohort-behaviors/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
└── tasks.md             # Phase 2 output (via /speckit.tasks)
```

### Source Code (repository root)

```text
src/mixpanel_data/
├── types.py                    # CohortBreakdown, CohortMetric types + Filter extensions
├── workspace.py                # query method signature updates, _build_query_params extension
├── _internal/
│   ├── bookmark_builders.py    # build_filter_entry + build_group_section extensions
│   └── validation.py           # CF1-CF2, CB1-CB3, CM1-CM4, B22-B26 rules
└── __init__.py                 # Export CohortBreakdown, CohortMetric

tests/
├── test_types.py               # CohortBreakdown, CohortMetric unit tests
├── test_workspace.py            # Integration tests for query methods with cohort types
├── test_bookmark_builders.py    # Filter entry + group section builder tests
├── test_validation.py           # Validation rule tests
└── test_types_pbt.py            # Property-based tests for new types
```

**Structure Decision**: Single project, extending existing files. No new modules — all changes fit within the existing layered architecture.
