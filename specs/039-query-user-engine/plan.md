# Implementation Plan: User Profile Query Engine

**Branch**: `039-query-user-engine` | **Date**: 2026-04-13 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/039-query-user-engine/spec.md`

## Summary

Add `query_user()` as the 5th query engine in the unified query system. Enables querying individual user profiles and computing aggregate statistics (count/sum/mean/min/max) across the user base, using the same `Filter` vocabulary as existing engines. Key capabilities: profile listing with sorting/search/limiting, aggregate mode with cohort segmentation, parallel page fetching for large result sets, and typed behavioral filtering via `CohortDefinition`.

## Technical Context

**Language/Version**: Python 3.10+ (mypy --strict)  
**Primary Dependencies**: httpx (HTTP), Pydantic v2 (validation), pandas (DataFrames), Hypothesis (PBT)  
**Storage**: N/A — live query only, no local persistence  
**Testing**: pytest, Hypothesis (property-based), mutmut (mutation)  
**Target Platform**: Python library (PyPI package)  
**Project Type**: Library  
**Performance Goals**: Parallel fetching up to 5x speedup for multi-page results (5,000+ profiles)  
**Constraints**: Engage API rate limit 60 queries/hour, max 5 concurrent queries per page  
**Scale/Scope**: Projects with millions of user profiles; default limit=1 ensures safe bare calls

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Evidence |
|-----------|--------|----------|
| I. Library-First | PASS | `query_user()` is a library method on `Workspace`; no CLI dependency |
| II. Agent-Native | PASS | Structured output (DataFrames), no interactive prompts, composable results |
| III. Context Window Efficiency | PASS | `limit=1` default (minimal tokens), property selection, `build_user_params()` for introspection |
| IV. Two Data Paths | PASS | Live query path (direct API call); `stream_profiles()` remains for streaming path |
| V. Explicit Over Implicit | PASS | Safe `limit=1` default, explicit `limit=None` opt-in for all profiles, explicit `parallel=True` |
| VI. Unix Philosophy | PASS | Composable DataFrame results, works with pandas ecosystem, `distinct_ids` for cross-engine joins |
| VII. Secure by Default | PASS | Uses existing credential infrastructure; no new credential handling |

**Result**: All gates pass. No violations. No complexity tracking needed.

**Post-Phase 1 Re-check**: All gates still pass. No implementation details introduced constitutional violations.

## Project Structure

### Documentation (this feature)

```text
specs/039-query-user-engine/
├── plan.md              # This file
├── research.md          # Phase 0 output — 8 research decisions
├── data-model.md        # Phase 1 output — entities, schemas, validation codes
├── quickstart.md        # Phase 1 output — usage examples
├── contracts/           # Phase 1 output
│   └── workspace_query_user.py  # Public API contract
└── tasks.md             # Phase 2 output (created by /speckit.tasks)
```

### Source Code (repository root)

```text
src/mixpanel_data/
├── __init__.py                          # Export UserQueryResult
├── types.py                             # UserQueryResult frozen dataclass
├── workspace.py                         # query_user(), build_user_params(), private helpers
├── _internal/
│   ├── api_client.py                    # extend export_profiles_page(), add engage_stats()
│   └── query/
│       ├── user_builders.py             # NEW: filter_to_selector(), extract_cohort_filter()
│       └── user_validators.py           # NEW: validate_user_args(), validate_user_params()

tests/
├── test_types_user_query_result.py      # NEW: UserQueryResult unit tests
├── test_user_builders.py                # NEW: filter→selector translation tests
├── test_user_validators.py              # NEW: validation rule tests (U1-U24, UP1-UP4)
├── test_api_client_engage_stats.py      # NEW: engage_stats() tests
├── test_workspace_build_user_params.py  # NEW: parameter building tests
├── test_workspace_query_user.py         # NEW: sequential query execution tests
├── test_workspace_query_user_parallel.py # NEW: parallel execution tests
├── test_workspace_query_user_aggregate.py # NEW: aggregate mode tests
├── test_workspace_query_user_integration.py # NEW: end-to-end integration tests
└── test_user_query_pbt.py              # NEW: property-based tests
```

**Structure Decision**: Single project layout matching existing codebase. New files in `_internal/query/` follow the pattern established by other builder/validator modules. All test files are at the top level of `tests/` consistent with existing test organization.

## Key Architecture Decisions

### AD1: Direct Workspace Implementation (No Service Layer)

Unlike other engines that delegate to `LiveQueryService` → `insights_query()`, `query_user()` calls `api_client.export_profiles_page()` and `api_client.engage_stats()` directly from workspace.py. The engage API uses form-encoded params (not bookmark JSON), a different endpoint (`/engage` not `/query/insights`), and session-based pagination — routing through `LiveQueryService` would require an awkward adapter with no benefit.

### AD2: New Filter Translation Path

A new `filter_to_selector()` function translates `Filter` objects to engage API selector strings. This is the third translation format alongside `build_filter_entry()` (bookmark dicts) and `build_segfilter_entry()` (segfilter entries). Each API expects its own format; double-converting would add complexity.

### AD3: Extended API Client

New parameters added to `export_profiles_page()` (sort_key, sort_order, search, limit, filter_by_cohort) and a new `engage_stats()` method. This maintains the typed parameter pattern rather than passing raw dicts.

### AD4: Mode-Aware Single Result Type

`UserQueryResult` handles both profiles and aggregate modes with a mode-aware `df` property. This avoids forcing callers to handle two distinct result types for what is conceptually one query.

## Implementation Phases

All features ship in a single phase. Tasks organized by dependency:

```
Task 1 (Types) ─────────────────────────────┐
Task 2 (Filter Translation) ──► Task 4 ─────┤
Task 3 (Validation) ──────────► (Param   ───┤
                                 Builder)    │
Task 5 (API Client) ──────────────────────┐  │
                                          │  │
                          ┌── Task 6 (Sequential) ──┐
               Task 4 ───┤                          ├─► Task 9 (Public API) ─► Task 10
                          ├── Task 7 (Parallel) ────┤
                          └── Task 8 (Aggregate) ───┘

Task 11 (PBT) — after Tasks 1, 2
```

**Parallelizable**: Tasks 1, 2, 3, 5 have no interdependencies.

### Task Breakdown

| Task | File(s) | Dependencies | Test File(s) |
|------|---------|--------------|-------------|
| 1. UserQueryResult type | `types.py` | None | `test_types_user_query_result.py` |
| 2. Filter → selector translation | `_internal/query/user_builders.py` | None | `test_user_builders.py` |
| 3. Argument validation (U1-U24) | `_internal/query/user_validators.py` | None | `test_user_validators.py` |
| 4. Parameter builder | `workspace.py` | Tasks 2, 3 | `test_workspace_build_user_params.py` |
| 5. API client engage_stats() | `_internal/api_client.py` | None | `test_api_client_engage_stats.py` |
| 6. Sequential query execution | `workspace.py` | Tasks 1, 4 | `test_workspace_query_user.py` |
| 7. Parallel query execution | `workspace.py` | Tasks 1, 4 | `test_workspace_query_user_parallel.py` |
| 8. Aggregate query execution | `workspace.py` | Tasks 1, 4, 5 | `test_workspace_query_user_aggregate.py` |
| 9. Public query_user() method | `workspace.py` | Tasks 6, 7, 8 | `test_workspace_query_user_integration.py` |
| 10. Public API exports | `__init__.py` | Task 1 | Existing import tests |
| 11. Property-based tests | — | Tasks 1, 2 | `test_user_query_pbt.py` |

### Testing Strategy

| Level | Scope | Tools |
|-------|-------|-------|
| Unit | Filter translation, validation, types, aggregate parsing | pytest, mocked |
| Unit | Parameter building, DataFrame construction | pytest, mocked |
| Integration | End-to-end query_user() with mocked API client | pytest, dependency injection |
| Integration | Parallel execution with mocked page responses | pytest, ThreadPoolExecutor |
| PBT | Filter translation invariants, DataFrame schema invariants | Hypothesis |

**PBT invariants**:
- For any Filter, `filter_to_selector()` produces a syntactically valid selector string
- For any list of profiles, `.df` has exactly `len(profiles)` rows
- `distinct_id` column is always present and matches profile data
- When `properties` specified, only those columns (plus `distinct_id`, `last_seen`) appear
- `total >= len(profiles)` always holds
- For aggregate mode, `.value` matches first row of `.df`
