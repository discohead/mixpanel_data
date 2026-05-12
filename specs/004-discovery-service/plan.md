# Implementation Plan: Discovery Service

**Branch**: `004-discovery-service` | **Date**: 2025-12-21 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/004-discovery-service/spec.md`

## Summary

The Discovery Service provides schema introspection for Mixpanel projects—listing events, properties, and sample values. It wraps the existing `MixpanelAPIClient` discovery methods with an in-memory cache layer to avoid redundant API calls within a session. This is a thin service layer following the established patterns from Phase 001-003.

## Technical Context

**Language/Version**: Python 3.10+
**Primary Dependencies**: httpx (via MixpanelAPIClient from Phase 002)
**Storage**: N/A (read-only service, in-memory cache only)
**Testing**: pytest with mocked API client
**Target Platform**: Python library (cross-platform)
**Project Type**: Single project (library)
**Performance Goals**: <3s uncached, <100ms cached (per SC-001, SC-002)
**Constraints**: Session-scoped caching, no persistence
**Scale/Scope**: Typical Mixpanel projects with up to 1,000 events

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Evidence |
|-----------|--------|----------|
| I. Library-First | ✅ PASS | Service is a Python class; no CLI in this phase |
| II. Agent-Native | ✅ PASS | Returns sorted lists (structured); no interactivity |
| III. Context Window Efficiency | ✅ PASS | Core purpose: introspection before querying |
| IV. Two Data Paths | ✅ PASS | Discovery is a "live query" path operation |
| V. Explicit Over Implicit | ✅ PASS | Cache is session-scoped with explicit clear method |
| VI. Unix Philosophy | ✅ PASS | Single responsibility: schema discovery only |
| VII. Secure by Default | ✅ PASS | Uses existing credential system; no new auth paths |

**Gate Status**: PASSED - No violations. Proceed to Phase 0.

## Project Structure

### Documentation (this feature)

```text
specs/004-discovery-service/
├── spec.md              # Feature specification
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
│   └── discovery_service.py  # Service interface contract
├── checklists/
│   └── requirements.md  # Specification quality checklist
└── tasks.md             # Phase 2 output (created by /speckit.tasks)
```

### Source Code (repository root)

```text
src/mixpanel_data/
├── _internal/
│   └── services/
│       ├── __init__.py      # NEW: Package marker
│       └── discovery.py     # NEW: DiscoveryService class
└── ...existing modules...

tests/
├── unit/
│   └── test_discovery.py    # NEW: Unit tests with mocked client
└── integration/
    └── test_discovery_integration.py  # NEW: Integration tests (optional)
```

**Structure Decision**: Single project structure following existing `_internal/` pattern. The `services/` directory is new but matches the design doc's planned layout.

## Complexity Tracking

> No violations to track. Implementation follows established patterns.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| None | - | - |
