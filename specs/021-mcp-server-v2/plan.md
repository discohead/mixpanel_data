# Implementation Plan: MCP Server v2 - Intelligent Analytics Platform

**Branch**: `021-mcp-server-v2` | **Date**: 2026-01-13 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/021-mcp-server-v2/spec.md`

## Summary

Transform the existing `mp-mcp-server` from a thin API wrapper (27 primitive tools) into an intelligent analytics platform with:
- **Tier 3**: Sampling-powered intelligent tools (`diagnose_metric_drop`, `ask_mixpanel`, `funnel_optimization_report`) using `ctx.sample()` for LLM synthesis with graceful degradation
- **Tier 2**: Composed tools (`gqm_investigation`, `product_health_dashboard`, `cohort_comparison`) orchestrating multiple primitives
- **Interactive**: Elicitation workflows (`guided_analysis`, `safe_large_fetch`) using `ctx.elicit()`
- **Task-Enabled**: Progress reporting and cancellation for long-running operations
- **Infrastructure**: Middleware layer (caching, rate limiting, audit logging) with in-memory storage
- **Enhanced Resources**: Dynamic templates and recipe resources
- **Framework Prompts**: GQM, AARRR, experiment analysis, data quality audit

## Technical Context

**Language/Version**: Python 3.10+
**Primary Dependencies**: FastMCP 2.x, mixpanel_data, Pydantic v2
**Storage**: DuckDB (via mixpanel_data.Workspace), in-memory for middleware caches
**Testing**: pytest, pytest-asyncio, pytest-cov, mypy --strict
**Target Platform**: Local MCP server (stdio transport for Claude Desktop, SSE for web clients)
**Project Type**: Single project (extending existing mp-mcp-server)
**Performance Goals**: <5s for primitive tools, <30s for composed tools, <60s for intelligent tools with sampling
**Constraints**: In-memory storage only (no Redis), graceful degradation when sampling unavailable
**Scale/Scope**: Single-server deployment, 27 existing tools + ~15 new tools

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Library-First | **PASS** | MCP server wraps `mixpanel_data` library; all logic in library or composed from it |
| II. Agent-Native Design | **PASS** | All tools produce structured JSON output; no interactive prompts in default path |
| III. Context Window Efficiency | **PASS** | Intelligent tools synthesize results to reduce token usage vs. raw data dumps |
| IV. Two Data Paths | **PASS** | Live queries via Mixpanel API; local analysis via DuckDB; both paths supported |
| V. Explicit Over Implicit | **PASS** | No magic; explicit table management, explicit degradation behavior |
| VI. Unix Philosophy | **PASS** | Tools compose; middleware is separate concern; single responsibility |
| VII. Secure by Default | **PASS** | Credentials managed by mixpanel_data config; no secrets in logs or output |

**Technology Stack Compliance**:
- Python 3.10+: ✅
- Pydantic v2: ✅ (used by FastMCP)
- DuckDB: ✅ (via mixpanel_data)
- Type hints: ✅ (mypy --strict enforced)

**GATE RESULT**: PASS - No violations to track.

### Post-Design Re-evaluation

*Re-checked after Phase 1 design artifacts (data-model.md, contracts/tools.yaml, quickstart.md).*

| Principle | Status | Phase 1 Verification |
|-----------|--------|---------------------|
| I. Library-First | **PASS** | All data types support Workspace method results |
| II. Agent-Native Design | **PASS** | All result types are structured dataclasses with JSON serialization |
| III. Context Window Efficiency | **PASS** | AnalysisResult includes synthesis fields to reduce token usage |
| IV. Two Data Paths | **PASS** | Tool contracts support both live and local query modes |
| V. Explicit Over Implicit | **PASS** | Status fields explicitly indicate success/partial/sampling_unavailable |
| VI. Unix Philosophy | **PASS** | Each tool has single responsibility; composed tools orchestrate |
| VII. Secure by Default | **PASS** | No credential fields in data models; raw_data excludes secrets |

**POST-DESIGN RESULT**: PASS - Design phase introduces no violations.

## Project Structure

### Documentation (this feature)

```text
specs/021-mcp-server-v2/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output (tool schemas)
└── tasks.md             # Phase 2 output (via /speckit.tasks)
```

### Source Code (repository root)

```text
mp-mcp-server/
├── src/mp_mcp_server/
│   ├── __init__.py
│   ├── server.py                    # FastMCP server with lifespan
│   ├── cli.py                       # CLI entry point
│   ├── context.py                   # Context utilities (get_workspace)
│   ├── errors.py                    # Error handling
│   ├── prompts.py                   # Existing prompts (extend)
│   ├── resources.py                 # Existing resources (extend)
│   ├── middleware/                  # NEW: Middleware layer
│   │   ├── __init__.py
│   │   ├── caching.py               # CachingMiddleware
│   │   ├── rate_limiting.py         # RateLimitMiddleware
│   │   └── audit.py                 # AuditMiddleware
│   ├── tools/
│   │   ├── __init__.py
│   │   ├── discovery.py             # Existing discovery tools
│   │   ├── fetch.py                 # Existing fetch tools (add task support)
│   │   ├── live_query.py            # Existing live query tools
│   │   ├── local.py                 # Existing local SQL tools
│   │   ├── intelligent/             # NEW: Tier 3 tools
│   │   │   ├── __init__.py
│   │   │   ├── diagnose.py          # diagnose_metric_drop
│   │   │   ├── ask.py               # ask_mixpanel
│   │   │   └── funnel_report.py     # funnel_optimization_report
│   │   ├── composed/                # NEW: Tier 2 tools
│   │   │   ├── __init__.py
│   │   │   ├── gqm.py               # gqm_investigation
│   │   │   ├── dashboard.py         # product_health_dashboard
│   │   │   └── cohort.py            # cohort_comparison
│   │   └── interactive/             # NEW: Elicitation tools
│   │       ├── __init__.py
│   │       ├── guided.py            # guided_analysis
│   │       └── safe_fetch.py        # safe_large_fetch
│   └── types.py                     # NEW: Shared types for results
├── tests/
│   ├── unit/
│   │   ├── test_middleware/
│   │   ├── test_intelligent/
│   │   ├── test_composed/
│   │   └── test_interactive/
│   └── integration/
│       └── test_workflows.py
└── pyproject.toml
```

**Structure Decision**: Extend existing single-project structure with new subdirectories for organized tool categories (intelligent, composed, interactive) and middleware layer.

## Complexity Tracking

> No Constitution violations to justify.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| *None* | - | - |
