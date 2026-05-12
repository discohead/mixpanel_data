# Implementation Plan: Retention Query (`query_retention()`)

**Branch**: `033-retention-query` | **Date**: 2026-04-06 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/033-retention-query/spec.md`

## Summary

Add typed retention querying to `mixpanel_data` via `query_retention()` and `build_retention_params()`, following the same two-layer validation and bookmark-params architecture established by `query()` (insights) and `query_funnel()` (funnels). New types (`RetentionEvent`, `RetentionMathType`, `RetentionQueryResult`), validation rules (R1-R6), a retention bookmark JSON builder, and a response transformer complete the system. All shared infrastructure (time/filter/group builders, `insights_query()` API client, `validate_bookmark()` L2) is reused without modification.

## Technical Context

**Language/Version**: Python 3.10+ (mypy --strict)
**Primary Dependencies**: httpx (HTTP client), Pydantic v2 (validation), pandas (DataFrames)
**Storage**: N/A — live query only, no local persistence
**Testing**: pytest, Hypothesis (property-based), mutmut (mutation)
**Target Platform**: Cross-platform Python library + CLI
**Project Type**: Library (with CLI wrapper)
**Performance Goals**: N/A — thin client over Mixpanel API; latency dominated by API response time
**Constraints**: Must pass mypy --strict, ruff check, 90%+ test coverage, 80%+ mutation score
**Scale/Scope**: ~800-1200 new lines of production code, ~1500-2000 lines of tests, across 5 files

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Evidence |
|-----------|--------|----------|
| I. Library-First | PASS | `query_retention()` and `build_retention_params()` are library methods on Workspace; CLI wrapping is out of scope for this phase |
| II. Agent-Native | PASS | Method returns typed `RetentionQueryResult` with `.df` and `.params`; no interactive prompts; structured errors with codes |
| III. Context Window Efficiency | PASS | Result includes `.df` for compact DataFrame view; `.params` for debugging; introspectable types |
| IV. Two Data Paths | PASS | This is a live query path; local storage is separate concern |
| V. Explicit Over Implicit | PASS | All parameters are keyword-only with explicit defaults; validation is fail-fast before API call; credentials resolved at construction |
| VI. Unix Philosophy | PASS | Method does one thing (retention query); results are composable (DataFrame, dict serialization) |
| VII. Secure by Default | PASS | Reuses existing credential handling; no new credential paths |

**Gate Result**: PASS — no violations.

## Project Structure

### Documentation (this feature)

```text
specs/033-retention-query/
├── plan.md              # This file
├── spec.md              # Feature specification
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
│   └── public-api.md    # Public method signatures and types
├── checklists/
│   └── requirements.md  # Spec quality checklist
└── tasks.md             # Phase 2 output (created by /speckit.tasks)
```

### Source Code (repository root)

```text
src/mixpanel_data/
├── __init__.py                          # MODIFY — add RetentionEvent, RetentionMathType, RetentionQueryResult exports
├── workspace.py                         # MODIFY — add query_retention(), build_retention_params(), _resolve_and_build_retention_params(), _build_retention_params()
├── types.py                             # MODIFY — add RetentionEvent, RetentionMathType, RetentionQueryResult
├── _internal/
│   ├── validation.py                    # MODIFY — add validate_retention_args(), extend validate_bookmark() for bookmark_type="retention"
│   ├── bookmark_enums.py                # NO CHANGE — VALID_MATH_RETENTION, VALID_RETENTION_UNITS, VALID_RETENTION_ALIGNMENT already exist
│   ├── bookmark_builders.py             # NO CHANGE — build_time_section, build_filter_section, build_group_section, build_filter_entry reused as-is
│   ├── api_client.py                    # NO CHANGE — insights_query() reused as-is
│   └── services/
│       └── live_query.py                # MODIFY — add query_retention(), _transform_retention_result()

tests/
├── test_types_retention.py              # NEW — RetentionEvent, RetentionQueryResult unit tests
├── test_types_retention_pbt.py          # NEW — Hypothesis property-based tests
├── test_validation_retention.py         # NEW — R1-R6 validation rule tests
├── test_build_retention_params.py       # NEW — bookmark JSON builder tests
├── test_transform_retention.py          # NEW — response transformer tests
└── test_workspace_retention.py          # NEW — integration tests (validation + execution + build_params consistency)
```

**Structure Decision**: Single-project library structure, extending existing modules. No new files in `src/` — all production code is added to existing modules. Six new test files follow the established per-concern test organization pattern from the funnel implementation.
