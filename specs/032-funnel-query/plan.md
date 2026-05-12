# Implementation Plan: Funnel Query (`query_funnel()`)

**Branch**: `032-funnel-query` | **Date**: 2026-04-05 | **Spec**: [spec.md](spec.md)  
**Input**: Feature specification from `/specs/032-funnel-query/spec.md`

## Summary

Add typed funnel query support to `mixpanel_data` via `query_funnel()` and `build_funnel_params()` on the `Workspace` class. Builds on the shared infrastructure extracted in Phase 1 (PR #88): reuses `build_time_section()`, `build_filter_section()`, `build_group_section()`, `build_filter_entry()`, `validate_time_args()`, `validate_group_by_args()`, and funnel enum constants. Introduces three new input types (`FunnelStep`, `Exclusion`, `HoldingConstant`), one new result type (`FunnelQueryResult`), funnel-specific validation (`validate_funnel_args()`), a funnel bookmark builder (`_build_funnel_params()`), and a response transformer (`_transform_funnel_result()`).

## Technical Context

**Language/Version**: Python 3.10+ (mypy --strict)  
**Primary Dependencies**: httpx (HTTP), Pydantic v2 (validation), pandas (DataFrames)  
**Storage**: N/A — live query only  
**Testing**: pytest, Hypothesis (property-based), mutmut (mutation)  
**Target Platform**: Library (PyPI package) + CLI  
**Project Type**: Library  
**Performance Goals**: N/A — constrained by Mixpanel API latency  
**Constraints**: All code must pass mypy --strict, ruff check, ruff format. 90% test coverage. All public APIs require complete docstrings.  
**Scale/Scope**: 5 new types, 2 new public methods, ~6 new internal functions, ~15 test files affected

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Evidence |
|-----------|--------|----------|
| I. Library-First | PASS | `query_funnel()` and `build_funnel_params()` are library methods; CLI wrapping is out of scope for this phase |
| II. Agent-Native Design | PASS | Non-interactive, returns typed result with `.df` and `.params`; raises structured `BookmarkValidationError` |
| III. Context Window Efficiency | PASS | Returns precise typed results, not raw data dumps; `.df` provides normalized view |
| IV. Two Data Paths | PASS | This is a live query path; consistent with existing `query()` pattern |
| V. Explicit Over Implicit | PASS | All parameters are keyword-only with documented defaults; no hidden state |
| VI. Unix Philosophy | PASS | Composable — results can be piped via `.df` to pandas, or `.params` to `create_bookmark()` |
| VII. Secure by Default | PASS | Reuses existing credential resolution; no new credential handling |

**Quality Gates**:
- [ ] All public functions have type hints — enforced by mypy --strict
- [ ] All public functions have docstrings — required by CLAUDE.md
- [ ] All new code passes ruff check and ruff format — enforced by `just check`
- [ ] All new code passes mypy --strict — enforced by `just check`
- [ ] Tests exist for new functionality — TDD workflow required
- [ ] CLI commands have --help — CLI is out of scope for this phase

**Post-Phase 1 Re-check**: All principles remain satisfied. No complexity violations.

## Project Structure

### Documentation (this feature)

```text
specs/032-funnel-query/
├── spec.md              # Feature specification
├── plan.md              # This file
├── research.md          # Phase 0: research decisions
├── data-model.md        # Phase 1: entity definitions
├── quickstart.md        # Phase 1: usage examples
├── contracts/
│   └── public-api.md    # Phase 1: public API contract
├── checklists/
│   └── requirements.md  # Spec quality checklist
└── tasks.md             # Phase 2: task breakdown (created by /speckit.tasks)
```

### Source Code (repository root)

```text
src/mixpanel_data/
├── __init__.py                     # ADD: FunnelStep, Exclusion, HoldingConstant,
│                                   #      FunnelMathType, FunnelQueryResult exports
├── types.py                        # ADD: FunnelStep, Exclusion, HoldingConstant,
│                                   #      FunnelMathType, FunnelQueryResult
├── workspace.py                    # ADD: query_funnel(), build_funnel_params(),
│                                   #      _resolve_and_build_funnel_params(),
│                                   #      _build_funnel_params()
├── _internal/
│   ├── validation.py               # ADD: validate_funnel_args()
│   │                               # MODIFY: _validate_measurement() to branch on
│   │                               #          bookmark_type="funnels"
│   ├── bookmark_enums.py           # (no changes — constants already exist)
│   ├── bookmark_builders.py        # (no changes — shared builders already exist)
│   └── services/
│       └── live_query.py           # ADD: query_funnel(), _transform_funnel_result()

tests/
├── test_types_funnel.py            # NEW: FunnelStep, Exclusion, HoldingConstant,
│                                   #      FunnelQueryResult unit tests
├── test_validation_funnel.py       # NEW: validate_funnel_args() unit tests
├── test_build_funnel_params.py     # NEW: _build_funnel_params() unit tests
├── test_workspace_funnel.py        # NEW: query_funnel(), build_funnel_params()
│                                   #      integration tests
├── test_transform_funnel.py        # NEW: _transform_funnel_result() unit tests
├── test_validation.py              # MODIFY: add tests for _validate_measurement
│                                   #          with bookmark_type="funnels"
└── test_types_funnel_pbt.py        # NEW: Hypothesis property-based tests
```

**Structure Decision**: Follows existing single-project layout. New test files per component to keep test files focused. No new directories needed.

## Complexity Tracking

No constitution violations. No complexity justifications needed.
