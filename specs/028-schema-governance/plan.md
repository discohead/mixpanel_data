# Implementation Plan: Schema Registry & Data Governance

**Branch**: `028-schema-governance` | **Date**: 2026-04-02 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/028-schema-governance/spec.md`

## Summary

Add schema registry CRUD (Domain 14) and data governance operations (Domain 15) to the Python library and CLI. This includes schema management (list, create, update, delete with bulk variants), schema enforcement configuration (get/init/update/replace/delete), data auditing (full and events-only), data volume anomaly management (list/update/bulk-update), and event deletion requests (list/create/cancel/preview). All operations use the existing App API infrastructure with workspace scoping and Bearer/Basic auth.

## Technical Context

**Language/Version**: Python 3.10+ (mypy --strict)
**Primary Dependencies**: httpx (HTTP), Pydantic v2 (validation), Typer (CLI), Rich (output)
**Storage**: N/A (remote CRUD via Mixpanel App API; no local DuckDB involvement)
**Testing**: pytest + respx (HTTP mocking) + Hypothesis (property-based)
**Target Platform**: Cross-platform (macOS, Linux, Windows)
**Project Type**: Library + CLI
**Performance Goals**: Standard HTTP round-trip latency; bulk operations reduce API calls
**Constraints**: Rate limits — schema writes: 5/m per org; properties/entities: 4000/m per org, 12000/m global; truncate deletions: 3000 max per request
**Scale/Scope**: ~20 new API client methods, ~20 new workspace methods, ~16 new Pydantic types, 2 CLI command groups (~20 subcommands)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Library-First | PASS | All CRUD operations exposed as Workspace methods; CLI wraps library |
| II. Agent-Native | PASS | All commands non-interactive, structured output (JSON/CSV/table/plain), exit codes |
| III. Context Efficiency | PASS | No local storage changes; focused API responses |
| IV. Two Data Paths | N/A | These are remote-only CRUD operations |
| V. Explicit Over Implicit | PASS | Destructive operations (delete, truncate) require explicit parameters; no hidden behavior |
| VI. Unix Philosophy | PASS | All output supports --jq filtering and piping |
| VII. Secure by Default | PASS | Uses existing credential system; no new credential handling |

**Technology Stack Compliance**:
- Pydantic v2 for all response models: PASS
- httpx for HTTP: PASS (via existing `app_request()`)
- Typer for CLI: PASS
- Rich for output: PASS (via existing formatters)

**Quality Gates**:
- Type hints: Will enforce mypy --strict on all new code
- Docstrings: Google style on all public and private functions
- Tests: Unit + integration + PBT; coverage >=90%
- CLI --help: All subcommands with descriptions and examples

## Project Structure

### Documentation (this feature)

```text
specs/028-schema-governance/
├── plan.md              # This file
├── spec.md              # Feature specification
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
│   ├── schema-registry.md
│   └── data-governance.md
└── checklists/
    └── requirements.md  # Spec quality checklist
```

### Source Code (repository root)

```text
src/mixpanel_data/
├── types.py                          # Add ~16 new Pydantic models
├── workspace.py                      # Add ~20 new methods
├── _internal/
│   └── api_client.py                 # Add ~20 new API methods
└── cli/
    └── commands/
        ├── schemas.py                # NEW — 6 subcommands (list, create, create-bulk, update, update-bulk, delete)
        └── lexicon.py                # MODIFY — add enforcement, audit, anomalies, deletion-requests subgroups

tests/
├── test_api_client_schemas.py        # NEW — API client schema methods
├── test_api_client_governance.py     # NEW — API client governance methods
├── test_workspace_schemas.py         # NEW — Workspace schema methods
├── test_workspace_governance.py      # NEW — Workspace governance methods
├── test_types_schemas_pbt.py         # NEW — PBT for schema types
├── test_types_governance_pbt.py      # NEW — PBT for governance types
└── cli/
    ├── test_schemas_cli.py           # NEW — schemas CLI
    └── test_lexicon_governance_cli.py # NEW — lexicon governance CLI
```

**Structure Decision**: Follows existing single-project layout. New CLI command file `schemas.py` for Domain 14. Domain 15 extends existing `lexicon.py` with nested subgroups (enforcement, anomalies, deletion-requests), matching the Rust CLI structure.

## Complexity Tracking

No constitution violations. All new code follows established patterns.
