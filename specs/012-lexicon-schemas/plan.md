# Implementation Plan: Lexicon Schemas API (Read Operations)

**Branch**: `012-lexicon-schemas` | **Date**: 2025-12-24 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/012-lexicon-schemas/spec.md`

## Summary

Extend DiscoveryService to support Mixpanel's Lexicon Schemas API for retrieving data dictionary definitions. This adds:
- New `"app"` endpoint type in regional endpoint configuration (for `/api/app` base path, shared by multiple APIs)
- 4 new frozen dataclass types for schema representations (`LexiconSchema`, `LexiconDefinition`, `LexiconProperty`, `LexiconMetadata`)
- 3 new API client methods for schema retrieval
- 2 new DiscoveryService methods with caching
- 2 new Workspace facade methods (`lexicon_schemas()`, `lexicon_schema()`)
- 1 new CLI command (`mp inspect lexicon`) for Lexicon schema inspection

**Refactoring (Breaking Change)**: Rename existing `Workspace.schema(table)` to `Workspace.table_schema(table)` to disambiguate from Lexicon schema methods. This is a breaking change, but the library has not yet been released.

## Technical Context

**Language/Version**: Python 3.10+
**Primary Dependencies**: httpx (HTTP client), Typer (CLI), Rich (output formatting), Pydantic v2 (validation)
**Storage**: N/A (read-only API operations, no local persistence)
**Testing**: pytest with mocked HTTP responses
**Target Platform**: Cross-platform Python library and CLI
**Project Type**: Single project with layered architecture
**Performance Goals**: Standard API response times; caching to minimize API calls
**Constraints**: Strict 5 requests/minute rate limit on Lexicon API
**Scale/Scope**: Small feature addition to existing service

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Compliance Notes |
|-----------|--------|------------------|
| I. Library-First | ✅ PASS | Workspace.lexicon_schemas()/lexicon_schema() methods before CLI exposure |
| II. Agent-Native Design | ✅ PASS | No interactive prompts; JSON/table output; structured types |
| III. Context Window Efficiency | ✅ PASS | Session caching reduces API calls; typed results not raw dumps |
| IV. Two Data Paths | ✅ PASS | Live query path only (schemas are metadata, not bulk data) |
| V. Explicit Over Implicit | ✅ PASS | Cache must be explicitly cleared; no auto-invalidation |
| VI. Unix Philosophy | ✅ PASS | Output composable; single responsibility (schema discovery) |
| VII. Secure by Default | ✅ PASS | Uses existing credential handling; no new security surface |

**Technology Stack Compliance:**
- ✅ Python 3.10+ with type hints
- ✅ Typer for CLI (no Click/argparse)
- ✅ Rich for output formatting
- ✅ httpx for HTTP (no requests)
- ✅ Frozen dataclasses for result types

**No violations requiring justification.**

## Project Structure

### Documentation (this feature)

```text
specs/012-lexicon-schemas/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output (API contracts)
└── tasks.md             # Phase 2 output (created by /speckit.tasks)
```

### Source Code (repository root)

```text
src/mixpanel_data/
├── __init__.py              # Export new types: LexiconSchema, LexiconDefinition, LexiconProperty, LexiconMetadata
├── types.py                 # Add 4 new frozen dataclasses
├── workspace.py             # Add lexicon_schemas(), lexicon_schema() methods; rename schema() → table_schema()
├── _internal/
│   ├── api_client.py        # Add "app" endpoint; add 3 schema methods
│   └── services/
│       └── discovery.py     # Add list_schemas(), get_schema() with caching
└── cli/
    └── commands/
        └── inspect.py       # Add "lexicon" command

tests/
├── unit/
│   ├── test_api_client.py   # Tests for schema API methods
│   ├── test_discovery.py    # Tests for discovery service schema methods
│   └── test_workspace.py    # Tests for Lexicon workspace methods + table_schema rename
└── integration/             # (optional integration tests)
```

**Structure Decision**: Single project layout following existing patterns. New code integrates into existing modules at appropriate layers.

## Complexity Tracking

> No violations requiring justification.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| None | N/A | N/A |
