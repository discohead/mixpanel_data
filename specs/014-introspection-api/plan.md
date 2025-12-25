# Implementation Plan: Local Introspection API

**Branch**: `014-introspection-api` | **Date**: 2024-12-25 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/014-introspection-api/spec.md`

## Summary

Add 5 introspection methods to the `Workspace` class (`sample()`, `summarize()`, `event_breakdown()`, `property_keys()`, `column_stats()`) that expose DuckDB's built-in analytical capabilities through typed, discoverable APIs. These methods enable users and AI agents to quickly understand local database contents before writing queries, following existing patterns of frozen dataclass results with lazy `.df` property and JSON serialization.

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: DuckDB (analytical queries), pandas (DataFrame conversion), Typer (CLI), Rich (output formatting)
**Storage**: DuckDB (existing `StorageEngine` class)
**Testing**: pytest (existing test infrastructure)
**Target Platform**: Cross-platform (Linux, macOS, Windows)
**Project Type**: Single Python package with CLI
**Performance Goals**: <1s for sample, <5s for summarize/breakdown/keys, <2s for column_stats on 1M row tables
**Constraints**: Must follow existing frozen dataclass patterns, immutable results, lazy DataFrame caching
**Scale/Scope**: Local tables up to millions of rows (typical Mixpanel exports)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Evidence |
|-----------|--------|----------|
| I. Library-First | PASS | All methods added to `Workspace` class first; CLI commands delegate to library |
| II. Agent-Native Design | PASS | Non-interactive, structured output (JSON/DataFrame), no prompts |
| III. Context Window Efficiency | PASS | Core feature purpose: enable agents to understand data without raw dumps |
| IV. Two Data Paths | PASS | Local analysis path only (appropriate for local introspection) |
| V. Explicit Over Implicit | PASS | Clear error messages for missing tables/columns, no hidden behavior |
| VI. Unix Philosophy | PASS | CLI outputs composable JSON/table formats; errors to stderr |
| VII. Secure by Default | PASS | No credentials involved (local database operations only) |

**Technology Stack Compliance**:
- [x] Python 3.11+ with type hints
- [x] Typer for CLI commands
- [x] Rich for output formatting (via existing formatters)
- [x] DuckDB for queries (existing StorageEngine)
- [x] pandas for DataFrame support

## Project Structure

### Documentation (this feature)

```text
specs/014-introspection-api/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output (internal Python API)
└── tasks.md             # Phase 2 output (/speckit.tasks command)
```

### Source Code (repository root)

```text
src/mixpanel_data/
├── workspace.py         # Add 5 introspection methods
├── types.py             # Add ColumnSummary, SummaryResult, EventStats,
│                        #     EventBreakdownResult, ColumnStatsResult
├── __init__.py          # Export new types
└── cli/
    └── commands/
        └── inspect.py   # Add 5 CLI commands: sample, summarize, breakdown, keys, column

tests/
├── unit/
│   ├── test_workspace.py      # Unit tests for Workspace methods
│   └── test_types.py          # Unit tests for new result types
└── integration/
    └── test_introspection.py  # Integration test for full workflow
```

**Structure Decision**: Single project structure (existing). New code follows established patterns:
- Methods in `workspace.py`
- Types in `types.py`
- CLI commands in `cli/commands/inspect.py`
- Tests in corresponding test files

## Complexity Tracking

> No Constitution violations. All features follow existing patterns with minimal complexity.

| Aspect | Approach | Why Appropriate |
|--------|----------|-----------------|
| Result types | Frozen dataclasses with `_df_cache` | Existing pattern in codebase (see `FetchResult`, `SegmentationResult`) |
| SQL execution | Existing `StorageEngine` methods | `execute_df()`, `execute_scalar()`, `execute_rows()` already available |
| Error handling | Existing exception types | `TableNotFoundError`, `QueryError` already defined |
| CLI integration | Add to existing `inspect_app` | Consistent with other inspection commands |
