# Implementation Plan: Discovery & Query API Enhancements

**Branch**: `007-discovery-enhancements` | **Date**: 2025-12-23 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/007-discovery-enhancements/spec.md`

## Summary

Extend the existing DiscoveryService and LiveQueryService to provide complete coverage of Mixpanel's Query API discovery and event breakdown endpoints. This adds 5 new capabilities:

1. **List saved funnels** — Discover funnel IDs for use with `funnel()` queries
2. **List saved cohorts** — Discover cohort IDs for profile filtering
3. **Today's top events** — Real-time event activity with counts and trends
4. **Multi-event time series** — Aggregate counts for multiple events over time
5. **Property value distributions** — Time-series breakdowns by property values

## Technical Context

**Language/Version**: Python 3.10+ (type hints required per constitution)
**Primary Dependencies**: httpx (HTTP client), Pydantic v2 (validation), pandas (DataFrame conversion)
**Storage**: N/A (live queries only, no local storage)
**Testing**: pytest with mocked API responses
**Target Platform**: Python library + CLI
**Project Type**: Single project (src/mixpanel_data)
**Performance Goals**: <2 second response time for all discovery operations
**Constraints**: Must follow existing service patterns; frozen dataclasses for all new types
**Scale/Scope**: 5 new API methods, 5 new result types, 3 discovery methods, 2 live query methods

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Evidence |
|-----------|--------|----------|
| I. Library-First | ✅ Pass | All methods on service classes, accessible programmatically before CLI |
| II. Agent-Native Design | ✅ Pass | All methods non-interactive; result types have `to_dict()` for JSON output |
| III. Context Window Efficiency | ✅ Pass | Discovery results cached; supports limits; returns precise answers |
| IV. Two Data Paths | ✅ Pass | Extends live query path; discovery is introspection, not analysis |
| V. Explicit Over Implicit | ✅ Pass | Caching behavior explicit (funnels/cohorts cached, top_events not); no magic |
| VI. Unix Philosophy | ✅ Pass | Returns clean data; composable with other tools; focused scope |
| VII. Secure by Default | ✅ Pass | Uses existing credential patterns; no new credential handling |

**Technology Stack Compliance**:

| Component | Required | Used | Status |
|-----------|----------|------|--------|
| Python 3.10+ | Type hints throughout | Yes | ✅ |
| httpx | All HTTP | Existing in api_client | ✅ |
| Pydantic v2 | API response models | N/A (frozen dataclasses per existing pattern) | ✅ |
| pandas | DataFrame conversion | Lazy `.df` property | ✅ |

## Project Structure

### Documentation (this feature)

```text
specs/007-discovery-enhancements/
├── spec.md              # Feature specification
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output (API contracts)
└── checklists/
    └── requirements.md  # Quality checklist
```

### Source Code (repository root)

```text
src/mixpanel_data/
├── __init__.py              # Export new types
├── types.py                 # Add 5 new result types
└── _internal/
    ├── api_client.py        # Add 5 low-level API methods
    └── services/
        ├── discovery.py     # Add 3 discovery methods
        └── live_query.py    # Add 2 live query methods

tests/
├── unit/
│   ├── test_discovery.py    # Discovery service tests
│   └── test_live_query.py   # Live query service tests
└── integration/
    └── test_discovery_integration.py  # Optional integration tests
```

**Structure Decision**: Extends existing single-project structure. New types in `types.py`, new API methods in `api_client.py`, new service methods in existing service modules.

## Complexity Tracking

> No violations. All changes follow existing patterns.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| (none) | — | — |
