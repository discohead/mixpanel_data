# Implementation Plan: Query Service Enhancements

**Branch**: `008-query-service-enhancements` | **Date**: 2024-12-23 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/008-query-service-enhancements/spec.md`

## Summary

Extend the LiveQueryService with 6 new Mixpanel Query API methods: activity feed (user event history), insights (saved reports), frequency analysis (addiction reports), numeric bucketing, numeric sum, and numeric average. Each method follows the established pattern of: API client method (raw HTTP) → transformation function → typed result object with lazy DataFrame conversion.

## Technical Context

**Language/Version**: Python 3.11+ (type hints required per constitution)
**Primary Dependencies**: httpx (HTTP client), Pydantic v2 (validation), pandas (DataFrame conversion)
**Storage**: N/A (live queries only, no local storage)
**Testing**: pytest with fixtures and mocked HTTP responses
**Target Platform**: Cross-platform Python library
**Project Type**: Single package library
**Performance Goals**: Standard API response times (network-bound)
**Constraints**: Rate limit handling via exponential backoff (existing infrastructure)
**Scale/Scope**: 6 new methods, 7 new result types, ~40 new tests

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Evidence |
|-----------|--------|----------|
| I. Library-First | PASS | All methods implemented in library first; no CLI in this phase |
| II. Agent-Native Design | PASS | Returns typed results with `.to_dict()` for JSON serialization |
| III. Context Window Efficiency | PASS | Returns structured results, not raw API dumps |
| IV. Two Data Paths | PASS | Extends live query path (not local storage) |
| V. Explicit Over Implicit | PASS | All parameters explicit; Literal types for enums |
| VI. Unix Philosophy | PASS | Single-purpose methods; composable output |
| VII. Secure by Default | PASS | Uses existing credential handling; no new secrets |

**Technology Stack Compliance**:

| Component | Required | Used | Status |
|-----------|----------|------|--------|
| Language | Python 3.11+ | Python 3.11+ | PASS |
| HTTP Client | httpx | httpx | PASS |
| Validation | Pydantic v2 | Pydantic v2 | PASS |
| DataFrames | pandas | pandas | PASS |
| Type Hints | Required | Full coverage | PASS |

## Project Structure

### Documentation (this feature)

```text
specs/008-query-service-enhancements/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
│   ├── activity-feed.yaml
│   ├── insights.yaml
│   ├── frequency.yaml
│   ├── segmentation-numeric.yaml
│   ├── segmentation-sum.yaml
│   └── segmentation-average.yaml
└── tasks.md             # Phase 2 output
```

### Source Code (repository root)

```text
src/mixpanel_data/
├── types.py                    # Add 7 new result types
├── __init__.py                 # Export new types
└── _internal/
    ├── api_client.py           # Add 6 new API methods
    └── services/
        └── live_query.py       # Add 6 new service methods + transformers

tests/
├── unit/
│   ├── test_types_phase008.py  # Unit tests for new result types
│   ├── test_api_client_phase008.py  # Unit tests for new API methods
│   └── test_live_query_phase008.py  # Unit tests for service methods
└── fixtures/
    └── phase008/               # Mock API response fixtures
        ├── activity_feed.json
        ├── insights.json
        ├── frequency.json
        ├── segmentation_numeric.json
        ├── segmentation_sum.json
        └── segmentation_average.json
```

**Structure Decision**: Single project structure following existing layout. New code integrates into existing modules (`types.py`, `api_client.py`, `live_query.py`) rather than creating new files, maintaining cohesion.

## Complexity Tracking

> No constitution violations requiring justification. All design choices align with established patterns.

| Decision | Rationale |
|----------|-----------|
| Single module per layer | Follow existing pattern (types.py, api_client.py, live_query.py) |
| Frozen dataclasses | Immutability per Principle V (Explicit Over Implicit) |
| Literal types for enums | Compile-time validation per constitution |
| No caching | Live queries return fresh data per design |
