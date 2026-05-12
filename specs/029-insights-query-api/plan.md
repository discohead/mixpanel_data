# Implementation Plan: Workspace.query() — Typed Insights Query API

**Branch**: `029-insights-query-api` | **Date**: 2026-04-04 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/029-insights-query-api/spec.md`

## Summary

Add a typed `Workspace.query()` method that generates valid Mixpanel insights bookmark params from Python keyword arguments, POSTs them inline to `/api/query/insights`, and returns a structured `QueryResult` with lazy DataFrame conversion. This unlocks ~60% of the insights engine's capabilities (multi-metric, formulas, DAU/WAU/MAU, per-user aggregation, rolling windows, percentiles) that currently require raw JSON construction.

## Technical Context

**Language/Version**: Python 3.10+ with full type hints (mypy --strict)  
**Primary Dependencies**: httpx (HTTP client), Pydantic v2 (validation), pandas (DataFrames)  
**Storage**: N/A — live query only, no local persistence  
**Testing**: pytest, Hypothesis (PBT), mutmut (mutation testing)  
**Target Platform**: Cross-platform Python library + CLI  
**Project Type**: Library (with CLI wrapper)  
**Performance Goals**: N/A — network-bound; single API call per query  
**Constraints**: Must work with Basic Auth (service accounts) and OAuth; must match existing architectural patterns  
**Scale/Scope**: ~4 new types, ~1 new result type, ~1 new workspace method, ~3 internal methods, ~14 validation rules

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Evidence |
|-----------|--------|----------|
| I. Library-First | PASS | `query()` is a library method on Workspace. CLI can wrap it later as a thin formatting layer. |
| II. Agent-Native Design | PASS | Returns structured QueryResult with .df property. No interactive prompts. Fail-fast validation with descriptive errors. |
| III. Context Window Efficiency | PASS | Returns precise computed results, not raw data dumps. Mode parameter controls result shape (timeseries vs single KPI). |
| IV. Two Data Paths | PASS | This is a live query path. Results can be persisted via `create_bookmark(params=result.params)`. |
| V. Explicit Over Implicit | PASS | Fail-fast validation — no silent fallbacks. All parameter combinations validated before API call. Descriptive ValueError messages. |
| VI. Unix Philosophy | PASS | Returns structured data composable with pandas. `.params` enables piping to `create_bookmark()`. |
| VII. Secure by Default | PASS | Uses existing credential system. No new credential handling. No secrets in params or results. |

**Result**: All gates pass. No violations to track.

## Project Structure

### Documentation (this feature)

```text
specs/029-insights-query-api/
├── plan.md              # This file
├── spec.md              # Feature specification
├── research.md          # Phase 0 output — execution path, response format, architecture
├── data-model.md        # Phase 1 output — entity definitions, type aliases, relationships
├── quickstart.md        # Phase 1 output — usage examples
├── contracts/
│   └── public-api.md    # Phase 1 output — method signature, types, error contract
├── checklists/
│   └── requirements.md  # Spec quality checklist
└── tasks.md             # Phase 2 output (created by /speckit.tasks)
```

### Source Code (repository root)

```text
src/mixpanel_data/
├── __init__.py              # Add exports: Metric, Filter, GroupBy, QueryResult, MathType, PerUserAggregation
├── types.py                 # Add: Metric, Filter, GroupBy, QueryResult dataclasses + type aliases
├── workspace.py             # Add: query() method + _build_query_params() + _validate_query_args()
├── _internal/
│   ├── api_client.py        # Add: insights_query() method
│   └── services/
│       └── live_query.py    # Add: query() method + _transform_query_result()

tests/
├── test_query_types.py      # Unit tests for Metric, Filter, GroupBy, QueryResult
├── test_query_validation.py # Unit tests for all 14 validation rules
├── test_query_params.py     # Unit tests for bookmark params generation
├── test_query_integration.py # Integration tests with wiremock-style mocked API
├── test_query_pbt.py        # Property-based tests for type invariants
```

**Structure Decision**: Single project layout matching existing codebase. All new code goes into existing modules — no new directories or packages needed. Test files follow existing naming convention (`test_*.py` in `tests/`).

## Complexity Tracking

> No constitution violations. No complexity tracking needed.

## Phase Details

### Phase 1: Types & Validation (Foundation)

**Goal**: Define all public types and validation logic. No API calls yet.

**Files to create/modify**:
- `src/mixpanel_data/types.py` — Add `MathType`, `PerUserAggregation`, `FilterPropertyType`, `PROPERTY_MATH_TYPES`, `NO_PER_USER_MATH_TYPES`, `Metric`, `Filter`, `GroupBy`, `QueryResult`
- `tests/test_query_types.py` — Tests for type construction, defaults, immutability
- `tests/test_query_validation.py` — Tests for all 14 validation rules (V1-V14)

**Key decisions**:
- Types are frozen dataclasses (matching existing result types)
- Filter uses class methods for construction (type-safe, self-documenting)
- Validation is a standalone function testable without API access
- QueryResult extends ResultWithDataFrame with lazy .df caching

### Phase 2: Bookmark Params Building (Core Logic)

**Goal**: Generate valid bookmark JSON from typed arguments. No API calls yet.

**Files to create/modify**:
- `src/mixpanel_data/workspace.py` — Add `_build_query_params()` private method
- `tests/test_query_params.py` — Tests for params generation against known-good JSON

**Key decisions**:
- Params building is a pure function (dict in, dict out) — highly testable
- Test against the two reference examples from the design doc (simple + complex)
- Formula metrics go in `sections.show[]` (NOT `sections.formula`)
- `queryLimits` stays at top level of request body, NOT inside bookmark
- Hidden metrics (`isHidden: true`) when formula is present

### Phase 3: API Integration (Execution Path)

**Goal**: Wire up the API call and response parsing. End-to-end functionality.

**Files to create/modify**:
- `src/mixpanel_data/_internal/api_client.py` — Add `insights_query()` method
- `src/mixpanel_data/_internal/services/live_query.py` — Add `query()` + `_transform_query_result()`
- `src/mixpanel_data/workspace.py` — Add public `query()` method
- `src/mixpanel_data/__init__.py` — Add exports
- `tests/test_query_integration.py` — Integration tests with mocked HTTP responses

**Key decisions**:
- API client POSTs to `/api/query/insights` with `inject_project_id=False` (project_id goes in body)
- Request body: `{"bookmark": <params>, "project_id": <id>, "queryLimits": {"limit": 3000}}`
- Response parsing extracts nested `date_range.from_date` / `date_range.to_date`
- `_transform_query_result()` follows the same pattern as `_transform_saved_report()`

### Phase 4: Property-Based Tests & Polish

**Goal**: Comprehensive testing, edge cases, exports verification.

**Files to create/modify**:
- `tests/test_query_pbt.py` — Property-based tests for type invariants
- Verify all exports in `__init__.py`
- Run full test suite with coverage check

**Key invariants to test**:
- Any valid Metric produces valid bookmark JSON
- Any valid Filter produces valid filter JSON with correct filterValue format
- Validation rules are exhaustive — no invalid combination passes through
- QueryResult.df always returns a DataFrame (never raises for valid responses)
