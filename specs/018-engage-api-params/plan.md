# Implementation Plan: Engage API Full Parameter Support

**Branch**: `018-engage-api-params` | **Date**: 2026-01-04 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/018-engage-api-params/spec.md`

## Summary

Add support for 6 missing Mixpanel Engage Query API parameters (`distinct_id`, `distinct_ids`, `data_group_id`, `behaviors`, `as_of_timestamp`, `include_all_users`) across all 4 architectural layers: API Client → Fetcher Service → Workspace → CLI.

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: Typer (CLI), Rich (output), httpx (HTTP), Pydantic v2 (validation)
**Storage**: DuckDB (local storage for fetched profiles)
**Testing**: pytest, Hypothesis (property-based), mutmut (mutation testing)
**Target Platform**: Cross-platform CLI (Linux, macOS, Windows)
**Project Type**: Single project (library + CLI)
**Performance Goals**: Stream profiles without loading all into memory; handle 100k+ profiles
**Constraints**: Maintain 90%+ code coverage, 80%+ mutation score, mypy --strict compliance
**Scale/Scope**: 4 layers to update, 6 new parameters, ~12 functional requirements

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Evidence |
|-----------|--------|----------|
| I. Library-First | ✅ PASS | Parameters added to library API (Workspace) before CLI |
| II. Agent-Native | ✅ PASS | No interactive prompts; structured JSON output; clear exit codes |
| III. Context Window Efficiency | ✅ PASS | Profile streaming unchanged; targeted ID lookup reduces data |
| IV. Two Data Paths | ✅ PASS | Parameters available for both fetch-to-local and streaming |
| V. Explicit Over Implicit | ✅ PASS | Mutual exclusivity validation makes invalid states unrepresentable |
| VI. Unix Philosophy | ✅ PASS | CLI flags compose with existing pipelines; data to stdout |
| VII. Secure by Default | ✅ PASS | No new credential handling; uses existing auth flow |

**Gate Status**: PASS - All principles satisfied. Proceed to Phase 0.

## Project Structure

### Documentation (this feature)

```text
specs/018-engage-api-params/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
│   └── engage-params.yaml
└── tasks.md             # Phase 2 output (via /speckit.tasks)
```

### Source Code (repository root)

```text
src/mixpanel_data/
├── _internal/
│   ├── api_client.py      # export_profiles() - add 6 parameters
│   └── services/
│       └── fetcher.py     # fetch_profiles() - propagate 6 parameters
├── workspace.py           # fetch_profiles(), stream_profiles() - public API
└── cli/
    └── commands/
        └── fetch.py       # mp fetch profiles - add CLI flags

tests/
├── unit/
│   ├── test_api_client.py        # New parameter tests
│   └── test_fetcher_service.py   # Service layer tests
└── integration/
    └── test_fetch_service.py     # End-to-end tests
```

**Structure Decision**: Single project structure. Changes propagate bottom-up through the existing 4-layer architecture.

## Complexity Tracking

No constitution violations requiring justification. The feature adds parameters to existing methods without architectural changes.
