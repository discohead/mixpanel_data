# Implementation Plan: CLI Application

**Branch**: `010-cli-application` | **Date**: 2025-12-23 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/010-cli-application/spec.md`

## Summary

Implement the `mp` command-line interface as a thin wrapper around the Workspace facade, providing 31 commands across 4 groups (auth, fetch, query, inspect). The CLI uses Typer for argument parsing and Rich for output formatting, with support for multiple output formats (json, table, csv, jsonl, plain), global options (--account, --quiet, --verbose), per-command format option (--format), and structured exit codes.

The CLI adheres to the Library-First principle: every command delegates to an existing Workspace or ConfigManager method, adding only I/O formatting. No business logic resides in the CLI layer.

## Technical Context

**Language/Version**: Python 3.10+ (per constitution, with full type hints)
**Primary Dependencies**: Typer (CLI framework), Rich (output formatting), existing mixpanel_data library
**Storage**: DuckDB (via existing StorageEngine, already implemented)
**Testing**: pytest with unit tests for formatters/helpers, integration tests for command execution
**Target Platform**: Linux, macOS, Windows (cross-platform CLI)
**Project Type**: Single project (CLI module within existing library)
**Performance Goals**: Auth operations < 2s, inspect operations < 5s, queries display first results < 3s
**Constraints**: Non-interactive by default, structured output, exit codes per spec
**Scale/Scope**: 31 commands, ~50-60 implementation tasks

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

### Pre-Design Evaluation

| Principle | Status | Evidence |
|-----------|--------|----------|
| I. Library-First | PASS | CLI commands map 1:1 to Workspace/ConfigManager methods; CLI handles only I/O formatting |
| II. Agent-Native Design | PASS | Non-interactive by default, JSON output, structured exit codes (0-5, 130), stderr for progress |
| III. Context Window Efficiency | PASS | Local SQL queries avoid API calls; introspection commands exist; streaming output supported |
| IV. Two Data Paths | PASS | Both live queries (segmentation, funnel, retention) and local analysis (fetch + sql) exposed |
| V. Explicit Over Implicit | PASS | Tables fail if exist, --force for destructive ops, --replace for overwrites |
| VI. Unix Philosophy | PASS | JSON/CSV/JSONL output for piping, data→stdout, progress→stderr, composable commands |
| VII. Secure by Default | PASS | Credentials from config/env, secrets redacted in all output, no CLI secret args |

**Gate Result**: PASS - All 7 principles satisfied. Proceeding to Phase 0.

### Post-Design Evaluation

| Principle | Status | Evidence |
|-----------|--------|----------|
| I. Library-First | PASS | CLI commands delegate to Workspace/ConfigManager; formatters only transform output |
| II. Agent-Native Design | PASS | Contracts specify JSON schemas; exit codes documented per command; --quiet suppresses progress |
| III. Context Window Efficiency | PASS | sql command with --scalar returns single values; all results serializable via .to_dict() |
| IV. Two Data Paths | PASS | fetch commands for local storage; query commands for live API; both groups documented |
| V. Explicit Over Implicit | PASS | --replace for overwrites; --force for destructive ops; confirmation prompts by default |
| VI. Unix Philosophy | PASS | Contracts specify stdout/stderr separation; format options enable piping; composable commands |
| VII. Secure by Default | PASS | --interactive for credential input; secrets shown as "********"; no CLI secret arguments |

**Post-Design Gate Result**: PASS - Design artifacts maintain full compliance with all 7 principles.

## Project Structure

### Documentation (this feature)

```text
specs/010-cli-application/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output (CLI contracts)
└── tasks.md             # Phase 2 output (/speckit.tasks command)
```

### Source Code (repository root)

```text
src/mixpanel_data/
├── __init__.py              # Public API exports (existing)
├── workspace.py             # Workspace facade (existing, CLI wraps this)
├── auth.py                  # Public auth module (existing)
├── exceptions.py            # Exception hierarchy (existing)
├── types.py                 # Result types with .to_dict() (existing)
├── _internal/               # Private implementation (existing)
│   ├── config.py            # ConfigManager (existing)
│   ├── api_client.py        # MixpanelAPIClient (existing)
│   ├── storage.py           # StorageEngine (existing)
│   └── services/            # Service layer (existing)
└── cli/                     # NEW: CLI implementation
    ├── __init__.py          # CLI package init
    ├── main.py              # Typer app entry point, global options
    ├── formatters.py        # Output formatters (json, table, csv, jsonl, plain)
    ├── utils.py             # Shared utilities (error handling, exit codes)
    └── commands/            # Command group modules
        ├── __init__.py      # Commands package
        ├── auth.py          # mp auth (list, add, remove, switch, show, test)
        ├── fetch.py         # mp fetch (events, profiles)
        ├── query.py         # mp query (sql, segmentation, funnel, retention, jql, ...)
        └── inspect.py       # mp inspect (events, properties, values, funnels, ...)

tests/
├── unit/
│   └── cli/                 # NEW: CLI unit tests
│       ├── test_formatters.py
│       ├── test_utils.py
│       └── test_commands/   # Per-command unit tests
└── integration/
    └── cli/                 # NEW: CLI integration tests
        ├── test_auth_commands.py
        ├── test_fetch_commands.py
        ├── test_query_commands.py
        └── test_inspect_commands.py
```

**Structure Decision**: Single project structure extending existing `src/mixpanel_data/` with new `cli/` module. Tests follow existing pattern with `unit/` and `integration/` separation.

## Complexity Tracking

No constitution violations requiring justification. The implementation follows all 7 principles without exception.
