# Implementation Plan: Typed Flow Query API

**Branch**: `034-flow-query` | **Date**: 2026-04-06 | **Spec**: [spec.md](spec.md)  
**Input**: Feature specification from `/specs/034-flow-query/spec.md`

## Summary

Add `query_flow()` and `build_flow_params()` to the Workspace, enabling ad-hoc flow queries without creating saved reports. Flows differ fundamentally from insights/funnels/retention: flat bookmark structure (no `sections` wrapper), different endpoint (POST `/arb_funnels`), legacy segfilter filter format, and graph-shaped response data. The implementation adds a segfilter converter, two-layer validation, a new API client method, and a `FlowQueryResult` type with NetworkX graph and DataFrame views.

## Technical Context

**Language/Version**: Python 3.10+ (mypy --strict)  
**Primary Dependencies**: httpx (HTTP), Pydantic v2 (validation), pandas (DataFrames), networkx>=3.0 (NEW — graph representation)  
**Storage**: N/A — live query only, no local persistence  
**Testing**: pytest, Hypothesis (PBT), mutmut (mutation testing)  
**Target Platform**: PyPI library (cross-platform)  
**Project Type**: Library + CLI  
**Performance Goals**: N/A — flows graphs have <50 nodes; no performance-critical paths  
**Constraints**: Follow retention query pattern exactly for consistency; segfilter format must match canonical TypeScript reference  
**Scale/Scope**: ~10 modified files, ~1500 lines new code, ~1000 lines new tests

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Library-First | PASS | `query_flow()` and `build_flow_params()` are library methods; CLI wraps them |
| II. Agent-Native | PASS | Non-interactive, returns typed structured results with `.to_dict()` |
| III. Context Window Efficiency | PASS | Results are precise typed objects, not raw dumps; `.graph`/`.df` provide multiple views |
| IV. Two Data Paths | PASS | Live query path; no local storage needed |
| V. Explicit Over Implicit | PASS | No global state; all config via Workspace constructor |
| VI. Unix Philosophy | PASS | Composable types with `.to_dict()` for JSON output |
| VII. Secure by Default | PASS | Credentials resolved from config/env, never in code |
| Technology Stack | PASS | Uses httpx, pandas, adds networkx (justified: 2.1MB, zero deps, data IS a graph) |
| Quality Gates | PASS | Type hints, docstrings, ruff, mypy, pytest, 90% coverage target |

**New dependency justification**: `networkx>=3.0` — 2.1 MB pure Python wheel, zero transitive dependencies, lighter than httpx. The flows response is literally a DAG with nodes and edges; representing it as a graph is semantically correct, not an imposed abstraction. Enables one-liner path queries, bottleneck analysis, and subgraph extraction.

## Project Structure

### Documentation (this feature)

```text
specs/034-flow-query/
├── plan.md              # This file
├── spec.md              # Feature specification
├── research.md          # Phase 0 research findings
├── data-model.md        # Phase 1 data model
├── quickstart.md        # Phase 1 usage examples
├── contracts/
│   └── public-api.md    # Public API contract
├── checklists/
│   └── requirements.md  # Spec quality checklist
└── tasks.md             # Phase 2 output (via /speckit.tasks)
```

### Source Code (files to modify/create)

```text
src/mixpanel_data/
├── __init__.py                          # MODIFY — export FlowStep, FlowQueryResult
├── _literal_types.py                    # MODIFY — add FlowCountType, FlowChartType
├── types.py                             # MODIFY — add FlowStep, FlowQueryResult
├── workspace.py                         # MODIFY — rename query_flows, add query_flow, build_flow_params
├── _internal/
│   ├── bookmark_builders.py             # MODIFY — add build_segfilter_entry()
│   ├── bookmark_enums.py                # MODIFY — extend flows constants
│   ├── api_client.py                    # MODIFY — rename query_flows, add arb_funnels_query()
│   ├── validation.py                    # MODIFY — add validate_flow_args(), validate_flow_bookmark()
│   └── services/
│       └── live_query.py                # MODIFY — rename query_flows, add query_flow(), _transform_flow_result()
└── cli/
    └── commands/
        └── query.py                     # MODIFY — update flows command to call query_saved_flows()

tests/
├── test_types_flow.py                   # NEW — FlowStep, FlowQueryResult unit tests
├── test_types_flow_pbt.py               # NEW — property-based tests
├── test_validation_flow.py              # NEW — FL1-FL8, FLB1-FLB6 validation tests
├── unit/
│   ├── test_bookmark_builders_segfilter.py  # NEW — segfilter converter tests
│   └── test_live_query_flow.py          # NEW — service layer tests with mocked API
└── integration/
    └── cli/
        └── test_bookmark_commands.py    # MODIFY — rename TestQueryFlows

pyproject.toml                           # MODIFY — add networkx>=3.0
```

**Structure Decision**: Follows existing project layout exactly. All new code goes in existing modules. No new files except test files. This is consistent with how funnels (Phase 2) and retention (Phase 3) were implemented.

## Complexity Tracking

No constitution violations. No complexity justifications needed.
