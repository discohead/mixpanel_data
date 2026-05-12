# Implementation Plan: Bookmarks API for Saved Reports

**Branch**: `015-bookmarks-api` | **Date**: 2025-12-25 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/015-bookmarks-api/spec.md`

## Summary

Implement Bookmarks API support for listing saved reports and querying them by bookmark ID. This adds three capabilities: (1) `list_bookmarks()` to discover saved reports with metadata, (2) `query_saved_report()` to execute Insights/Retention/Funnel reports, and (3) `query_flows()` for Flows reports. Includes CLI commands for all operations. The existing `insights()` method will be renamed to `query_saved_report()` to accurately reflect its broader capability.

## Technical Context

**Language/Version**: Python 3.10+ with full type hints (mypy --strict compliant)
**Primary Dependencies**: httpx (HTTP client), Typer (CLI), Rich (output formatting), Pydantic v2 (validation), pandas (DataFrame conversion)
**Storage**: N/A (live queries only - no local persistence for bookmark operations)
**Testing**: pytest with httpx.MockTransport for API client mocking
**Target Platform**: Cross-platform Python library and CLI (Linux, macOS, Windows)
**Project Type**: Single project (Python library with CLI)
**Performance Goals**: API response times dependent on Mixpanel; library adds <10ms overhead
**Constraints**: Must support all three data residency regions (US, EU, India)
**Scale/Scope**: Typical projects have 100-2000+ bookmarks; listing should handle pagination gracefully

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Evidence |
|-----------|--------|----------|
| I. Library-First | PASS | All methods implemented in Workspace class first; CLI delegates to library |
| II. Agent-Native Design | PASS | No interactive prompts; structured JSON output; meaningful exit codes |
| III. Context Window Efficiency | PASS | Bookmark listing returns metadata only; detailed data on-demand via query |
| IV. Two Data Paths | PASS | This is a "live query" feature; integrates with existing authentication |
| V. Explicit Over Implicit | PASS | Explicit bookmark IDs required; no hidden state; clear error messages |
| VI. Unix Philosophy | PASS | JSON/table output; composable with jq/grep; errors to stderr |
| VII. Secure by Default | PASS | Uses existing credential system; no credentials in output |

**Technology Stack Compliance**:
- Python 3.10+ with type hints: PASS
- Typer for CLI: PASS
- Rich for output: PASS
- Pydantic v2 for validation: PASS
- httpx for HTTP: PASS
- pandas for DataFrame: PASS (result types support .df property)

**Quality Gates**: All new code will have type hints, docstrings, ruff/mypy compliance, and pytest tests.

## Project Structure

### Documentation (this feature)

```text
specs/015-bookmarks-api/
├── plan.md              # This file
├── research.md          # Phase 0: API research and patterns
├── data-model.md        # Phase 1: Entity definitions
├── quickstart.md        # Phase 1: Usage examples
├── contracts/           # Phase 1: API contracts
│   └── bookmarks-api.yaml
└── tasks.md             # Phase 2 output (/speckit.tasks command)
```

### Source Code (repository root)

```text
src/mixpanel_data/
├── __init__.py                    # Add BookmarkInfo, SavedReportResult, FlowsResult exports
├── types.py                       # Add BookmarkInfo, BookmarkType, SavedReportResult, FlowsResult
├── workspace.py                   # Add list_bookmarks(), query_saved_report(), query_flows()
├── _internal/
│   ├── api_client.py              # Add list_bookmarks(), query_flows(); rename insights()
│   └── services/
│       ├── discovery.py           # Add list_bookmarks() method
│       └── live_query.py          # Rename insights() → query_saved_report(); add query_flows()
└── cli/
    └── commands/
        ├── inspect.py             # Add 'bookmarks' command
        └── query.py               # Rename 'insights' → 'saved-report'; add 'flows' command

tests/
├── unit/
│   ├── test_types_bookmarks.py    # New: BookmarkInfo, SavedReportResult, FlowsResult tests
│   ├── test_api_client_bookmarks.py # New: API client bookmark method tests
│   ├── test_discovery_bookmarks.py  # New: Discovery service bookmark tests
│   ├── test_live_query_bookmarks.py # New: LiveQuery service bookmark tests
│   └── test_workspace_bookmarks.py  # New: Workspace bookmark method tests
└── integration/
    └── cli/
        └── test_bookmark_commands.py # New: CLI command integration tests
```

**Structure Decision**: Single project structure following existing patterns. New code is added to existing modules at appropriate layers (types → api_client → services → workspace → CLI). Test files follow the pattern of grouping related tests by domain (bookmarks).

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

No violations. All constitution principles are satisfied by the design.
