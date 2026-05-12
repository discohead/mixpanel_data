# Implementation Plan: Foundation Layer

**Branch**: `001-foundation-layer` | **Date**: 2025-12-19 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/001-foundation-layer/spec.md`

## Summary

Implement the foundational infrastructure layer for mixpanel_data including:

1. **ConfigManager** - Credential storage, resolution (env vars → named account → default), and validation using TOML configuration files
2. **Exceptions** - Typed exception hierarchy with a common base class for all library errors
3. **Result Types** - Immutable dataclasses for operation outcomes (FetchResult, QueryResult) with DataFrame conversion

This layer has no external dependencies beyond core libraries and forms the base upon which all other components (API client, storage engine, services) will be built.

## Technical Context

**Language/Version**: Python 3.10+ (per constitution)
**Primary Dependencies**: Pydantic v2 (validation), tomli/tomllib (TOML parsing), pandas (DataFrame conversion)
**Storage**: File-based TOML configuration at `~/.mp/config.toml`
**Testing**: pytest with pytest-cov
**Target Platform**: Cross-platform (macOS, Linux, Windows)
**Project Type**: Single project - Python library with CLI
**Performance Goals**: Configuration loading < 50ms, result serialization < 10ms
**Constraints**: No network calls in this layer, all operations are local
**Scale/Scope**: Supports unlimited named accounts, result types handle up to 1M rows lazily

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Evidence |
| --------- | ------ | -------- |
| I. Library-First | PASS | ConfigManager, exceptions, and types are pure library components with no CLI dependencies |
| II. Agent-Native | PASS | All components are non-interactive; exceptions provide structured error info |
| III. Context Window Efficiency | PASS | Result types support lazy DataFrame conversion to avoid memory bloat |
| IV. Two Data Paths | N/A | Foundation layer; data paths built on top of this |
| V. Explicit Over Implicit | PASS | Credentials resolved once and frozen; no global state |
| VI. Unix Philosophy | PASS | Single-purpose components; result types serializable to JSON |
| VII. Secure by Default | PASS | FR-007 requires secrets never appear in logs/errors; config file permissions enforced |

**Gate Status**: PASSED - No violations requiring justification.

## Project Structure

### Documentation (this feature)

```text
specs/001-foundation-layer/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output (internal API contracts)
└── checklists/          # Quality validation checklists
```

### Source Code (repository root)

```text
src/mixpanel_data/
├── __init__.py              # Public API exports
├── exceptions.py            # All exception classes (FR-008 to FR-011)
├── types.py                 # Result types: FetchResult, QueryResult, etc. (FR-012 to FR-015)
├── _internal/
│   └── config.py            # ConfigManager implementation (FR-001 to FR-007)
└── py.typed                 # PEP 561 marker

tests/
├── conftest.py              # Shared fixtures
├── unit/
│   ├── test_config.py       # ConfigManager tests
│   ├── test_exceptions.py   # Exception tests
│   └── test_types.py        # Result type tests
└── integration/
    └── test_config_file.py  # File I/O tests with temp directories
```

**Structure Decision**: Single project structure per constitution. Foundation layer creates the initial package skeleton. ConfigManager is in `_internal/` as it's not part of public API; exceptions and types are public.

## Complexity Tracking

> No violations to justify - constitution check passed.

| Violation | Why Needed | Simpler Alternative Rejected Because |
| --------- | ---------- | ------------------------------------ |
| None | - | - |
