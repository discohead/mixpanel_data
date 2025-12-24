# Implementation Plan: Streaming API

**Branch**: `011-streaming-api` | **Date**: 2024-12-24 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/011-streaming-api/spec.md`

## Summary

Add streaming methods (`stream_events()`, `stream_profiles()`) to the Workspace class that return iterators of event/profile dictionaries directly from the Mixpanel API, bypassing local DuckDB storage. Also add `--stdout` and `--raw` flags to CLI fetch commands for JSONL output to stdout.

**Technical Approach**: Reuse existing `MixpanelAPIClient.export_events()` and `export_profiles()` iterators, and existing `_transform_event()` / `_transform_profile()` functions from the fetcher service. New methods simply wire these together without the storage step.

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: Typer (CLI), httpx (HTTP), Rich (progress to stderr)
**Storage**: N/A for streaming (bypasses DuckDB entirely)
**Testing**: pytest with mocked API responses
**Target Platform**: Linux/macOS/Windows (cross-platform Python)
**Project Type**: Single project (library + CLI)
**Performance Goals**: Constant memory usage regardless of dataset size (true streaming)
**Constraints**: Must not buffer entire response; must maintain backward compatibility
**Scale/Scope**: Support datasets of 1M+ events without memory issues

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Evidence |
|-----------|--------|----------|
| I. Library-First | ✅ PASS | Streaming methods added to Workspace class first; CLI delegates to library |
| II. Agent-Native Design | ✅ PASS | No interactive prompts; JSONL output; progress to stderr; meaningful exit codes |
| III. Context Window Efficiency | ✅ PASS | Streaming enables precise data retrieval without local storage overhead |
| IV. Two Data Paths | ✅ PASS | Extends "live queries" path; complements existing local storage path |
| V. Explicit Over Implicit | ✅ PASS | `raw=False` default is explicit; no hidden state changes |
| VI. Unix Philosophy | ✅ PASS | JSONL pipes to jq/grep; progress to stderr; composable |
| VII. Secure by Default | ✅ PASS | No credential exposure; uses existing auth infrastructure |

**Gate Result**: PASS - All principles satisfied

## Project Structure

### Documentation (this feature)

```text
specs/011-streaming-api/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
│   └── workspace-streaming.md
└── tasks.md             # Phase 2 output (created by /speckit.tasks)
```

### Source Code (repository root)

```text
src/mixpanel_data/
├── workspace.py              # Add stream_events(), stream_profiles() methods
├── _internal/
│   └── services/
│       └── fetcher.py        # No changes (reuse _transform_event, _transform_profile)
└── cli/
    └── commands/
        └── fetch.py          # Add --stdout, --raw options

tests/
├── unit/
│   └── test_workspace_streaming.py    # Unit tests for streaming methods
└── cli/
    └── test_fetch_streaming.py        # CLI tests for --stdout flag
```

**Structure Decision**: Single project structure (existing). No new directories needed—streaming is a surgical addition to existing modules.

## Complexity Tracking

> No Constitution violations requiring justification.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| N/A | N/A | N/A |

## Implementation Notes

### Key Implementation Details

1. **Workspace.stream_events()**: Call `self._require_api_client().export_events()` directly, optionally transform with `_transform_event()` based on `raw` parameter.

2. **Workspace.stream_profiles()**: Call `self._require_api_client().export_profiles()` directly, optionally transform with `_transform_profile()` based on `raw` parameter.

3. **CLI --stdout flag**: When enabled, iterate over `workspace.stream_events()` and print each dict as JSON line. Use `sys.stdout` for data, `err_console` for progress.

4. **CLI --raw flag**: Pass through to streaming method; only valid with `--stdout`.

5. **Table name handling**: When `--stdout` is set, the table name argument becomes optional (use `typer.Argument(default=None)`).

### Dependencies Between Tasks

```
stream_events() ──┐
                  ├──> CLI --stdout flag ──> Integration tests
stream_profiles() ┘
```

Events and profiles streaming can be implemented in parallel. CLI depends on both. Tests depend on all.
