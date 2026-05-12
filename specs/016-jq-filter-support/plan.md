# Implementation Plan: JQ Filter Support for CLI Output

**Branch**: `016-jq-filter-support` | **Date**: 2026-01-04 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/016-jq-filter-support/spec.md`

## Summary

Add `--jq` option to all CLI commands that support `--format json/jsonl`, enabling client-side JSON filtering using jq syntax. Uses jq.py library for cross-platform compatibility with pre-built wheels (no compilation needed). Integration at post-formatter pipeline in `cli/utils.py`.

## Technical Context

**Language/Version**: Python 3.10+
**Primary Dependencies**: jq>=1.9.0 (new), typer, rich, pydantic
**Storage**: N/A (output filtering only)
**Testing**: pytest, hypothesis
**Target Platform**: Linux, macOS, Windows (pre-built wheels for all)
**Project Type**: Single library with CLI
**Performance Goals**: Negligible overhead for typical output sizes
**Constraints**: Must work without external jq binary; no interactive prompts

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Library-First | ✅ Pass | `_apply_jq_filter()` is a library function; CLI wraps it |
| II. Agent-Native Design | ✅ Pass | No interactive prompts; structured JSON output; meaningful exit codes |
| III. Context Window Efficiency | ✅ Pass | Enables precise output filtering, reducing tokens |
| IV. Two Data Paths | ✅ Pass | Works with both live queries and local SQL output |
| V. Explicit Over Implicit | ✅ Pass | User explicitly provides `--jq` filter; no magic |
| VI. Unix Philosophy | ✅ Pass | Extends composability without requiring external jq binary |
| VII. Secure by Default | ✅ Pass | No credential exposure; jq sandbox is read-only |

**Quality Gates**:
- [ ] All public functions have type hints
- [ ] All public functions have docstrings (Google style)
- [ ] All new code passes `ruff check` and `ruff format`
- [ ] All new code passes `mypy --strict`
- [ ] Tests exist for new functionality (pytest)
- [ ] CLI commands have `--help` with examples

## Project Structure

### Documentation (this feature)

```text
specs/016-jq-filter-support/
├── plan.md              # This file
├── research.md          # Phase 0 output (library selection)
├── data-model.md        # Phase 1 output (type definitions)
├── quickstart.md        # Phase 1 output (usage examples)
├── contracts/           # N/A for this feature (no API changes)
└── tasks.md             # Phase 2 output (/speckit.tasks command)
```

### Source Code (repository root)

```text
src/mixpanel_data/cli/
├── options.py           # Add JqOption type alias
├── utils.py             # Add _apply_jq_filter(), update output_result()
└── commands/
    ├── inspect.py       # Add jq_filter param to commands
    ├── query.py         # Add jq_filter param to commands
    └── fetch.py         # Add jq_filter param to commands

tests/unit/cli/
├── test_utils.py        # Tests for _apply_jq_filter()
├── test_jq_integration.py  # NEW: CLI integration tests
└── test_jq_pbt.py       # NEW: Property-based tests
```

**Structure Decision**: Single project structure. Changes are localized to CLI layer (`src/mixpanel_data/cli/`). No new modules needed—extending existing `utils.py` and `options.py`.

## Complexity Tracking

> No Constitution violations. All changes align with existing patterns.

| Item | Decision | Rationale |
|------|----------|-----------|
| Required dependency | jq.py as required (not optional) | Pre-built wheels for all platforms; already have heavy native deps (pandas, duckdb); better UX |
| Post-formatter integration | Filter applied after JSON formatting | Simpler than modifying formatters; consistent behavior |
| Exit code | INVALID_ARGS (3) for all jq errors | Consistent with other syntax errors (JQL, date validation) |
