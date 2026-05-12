# Implementation Plan: Core Entity CRUD (Dashboards, Reports, Cohorts)

**Branch**: `024-core-entity-crud` | **Date**: 2026-03-26 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/024-core-entity-crud/spec.md`

## Summary

Add full CRUD operations for Dashboards, Reports/Bookmarks, and Cohorts to the `mixpanel_data` Python library and `mp` CLI, achieving parity with the Rust implementation. This requires ~14 Pydantic types, ~35 API client methods, 36 Workspace methods (20 dashboard + 9 bookmark + 7 cohort), and 34 CLI subcommands across 3 new command groups. The implementation builds on Phase 0's OAuth + App API infrastructure (Bearer auth, workspace scoping, cursor-based pagination).

## Technical Context

**Language/Version**: Python 3.10+ with full type hints (mypy --strict)
**Primary Dependencies**: httpx (HTTP), Pydantic v2 (validation), Typer (CLI), Rich (output)
**Storage**: DuckDB (local analysis), Mixpanel App API (remote CRUD)
**Testing**: pytest + respx (HTTP mocking) + Hypothesis (property-based) + mutmut (mutation)
**Target Platform**: Cross-platform (macOS, Linux, Windows)
**Project Type**: Library + CLI
**Performance Goals**: Standard web API response times; bulk operations handle 100+ entities per call
**Constraints**: 90% test coverage, mypy --strict, ruff format/check compliance
**Scale/Scope**: ~14 new types, ~35 API methods, ~27 Workspace methods, 34 CLI subcommands

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Library-First | PASS | All CRUD operations exposed as Workspace methods first; CLI wraps them |
| II. Agent-Native Design | PASS | All methods return typed objects; CLI outputs structured formats (json/jsonl/csv/table/plain); no interactive prompts |
| III. Context Window Efficiency | PASS | Paginated results; filtering parameters on list operations; typed responses (not raw data dumps) |
| IV. Two Data Paths | PASS | CRUD operations are live API calls (appropriate for entity management); local storage not needed for CRUD |
| V. Explicit Over Implicit | PASS | All mutations are explicit method calls; no implicit side effects; delete requires explicit ID |
| VI. Unix Philosophy | PASS | CLI outputs clean data to stdout; errors to stderr; composable with jq/grep/awk |
| VII. Secure by Default | PASS | Credentials resolved from config/env; Bearer tokens handled internally; no secrets in output |

| Quality Gate | Status | Notes |
|--------------|--------|-------|
| Type hints on all public functions | REQUIRED | All new methods fully typed |
| Docstrings (Google style) | REQUIRED | All new classes and methods |
| ruff check + ruff format | REQUIRED | Pre-commit enforcement |
| mypy --strict | REQUIRED | No Any types without justification |
| Tests for new functionality | REQUIRED | 90% coverage target |
| CLI --help with examples | REQUIRED | All 34 subcommands |

**Gate Result**: ALL PASS — no violations to justify.

## Project Structure

### Documentation (this feature)

```text
specs/024-core-entity-crud/
├── plan.md              # This file
├── spec.md              # Feature specification
├── research.md          # Phase 0: research findings
├── data-model.md        # Phase 1: entity models
├── quickstart.md        # Phase 1: developer quickstart
├── contracts/           # Phase 1: public API contracts
│   ├── workspace-api.md # Workspace method signatures
│   └── cli-commands.md  # CLI command specifications
├── checklists/
│   └── requirements.md  # Spec quality checklist
└── tasks.md             # Phase 2 output (from /speckit.tasks)
```

### Source Code (repository root)

```text
src/mixpanel_data/
├── types.py                    # MODIFY: Add ~14 Pydantic models (Dashboard, Bookmark, Cohort + params)
├── workspace.py                # MODIFY: Add ~27 CRUD methods
├── _internal/
│   └── api_client.py           # MODIFY: Add ~35 API methods using existing app_request()
└── cli/
    ├── main.py                 # MODIFY: Register 3 new command groups
    └── commands/
        ├── dashboards.py       # CREATE: 17 subcommands
        ├── reports.py          # CREATE: 10 subcommands
        └── cohorts.py          # CREATE: 7 subcommands

tests/
├── test_types.py               # MODIFY: Add type round-trip tests
├── test_workspace.py           # MODIFY: Add CRUD method tests
├── test_api_client.py          # MODIFY: Add API method tests with respx mocks
├── test_types_pbt.py           # MODIFY: Add Hypothesis property tests for new types
└── cli/
    ├── test_dashboards_cli.py  # CREATE: CLI integration tests
    ├── test_reports_cli.py     # CREATE: CLI integration tests
    └── test_cohorts_cli.py     # CREATE: CLI integration tests
```

**Structure Decision**: Extends existing library structure. No new directories needed beyond CLI command files and their test counterparts. Types stay in `types.py` (total model count remains manageable at ~44 models).

## Complexity Tracking

No constitution violations to justify. All design decisions align with established principles and patterns.
