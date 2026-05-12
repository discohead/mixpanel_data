# Implementation Plan: Phase 1 — Shared Infrastructure Extraction

**Branch**: `031-shared-infra-extraction` | **Date**: 2026-04-05 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/031-shared-infra-extraction/spec.md`

## Summary

Extract shared time-range building, filter/group-section building, and validation logic from the existing `query()` / `_build_query_params()` / `validate_query_args()` pipeline into reusable helpers. Add a new `_build_segfilter_entry()` converter for flows. Extend bookmark enum constants for funnel/retention/flows domains. All existing behavior must remain unchanged (zero regressions).

## Technical Context

**Language/Version**: Python 3.10+ (mypy --strict)
**Primary Dependencies**: httpx (HTTP), Pydantic v2 (validation), pandas (DataFrames)
**Storage**: N/A — live query only
**Testing**: pytest, Hypothesis (property-based), mutmut (mutation)
**Target Platform**: Cross-platform Python library + CLI
**Project Type**: Library + CLI
**Performance Goals**: N/A — infrastructure extraction, no new API calls
**Constraints**: Zero behavioral regressions; 90% code coverage; mypy --strict
**Scale/Scope**: ~5 new internal functions, ~1 new internal module (~100 lines), ~15 new enum constants

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Library-First | PASS | All new functions are library-internal; no CLI changes |
| II. Agent-Native | PASS | No interactive elements; pure function extraction |
| III. Context Window Efficiency | PASS | No new data retrieval; infrastructure only |
| IV. Two Data Paths | PASS | Affects live query path only (shared builders) |
| V. Explicit Over Implicit | PASS | No hidden behavior; same explicit parameters |
| VI. Unix Philosophy | PASS | Composable internal functions |
| VII. Secure by Default | PASS | No credential handling in extracted functions |

**Quality Gates**:
- [x] Type hints on all new functions (mypy --strict)
- [x] Docstrings on all new functions (Google style)
- [x] ruff check + ruff format
- [x] Tests for all new functionality (pytest + Hypothesis)
- [x] No CLI changes needed

All gates pass. No violations to justify.

## Project Structure

### Documentation (this feature)

```text
specs/031-shared-infra-extraction/
├── plan.md              # This file
├── spec.md              # Feature specification
├── research.md          # Phase 0: segfilter research + design decisions
├── data-model.md        # Phase 1: entity definitions
├── quickstart.md        # Phase 1: usage guide for extracted functions
├── checklists/
│   └── requirements.md  # Specification quality checklist
└── tasks.md             # Phase 2 output (from /speckit.tasks)
```

### Source Code (repository root)

```text
src/mixpanel_data/
├── workspace.py                    # MODIFY: delegate to extracted helpers
├── _internal/
│   ├── validation.py               # MODIFY: extract time/group_by validators
│   ├── bookmark_enums.py           # MODIFY: add funnel/retention/flows constants
│   ├── bookmark_builders.py        # NEW: shared time/filter/group section builders
│   └── segfilter.py                # NEW: Filter → segfilter converter

tests/
├── unit/
│   ├── test_bookmark_builders.py   # NEW: tests for extracted builders
│   ├── test_segfilter.py           # NEW: tests for segfilter converter
│   ├── test_query_validation.py    # EXISTING: must pass unchanged
│   ├── test_bookmark_enums.py      # NEW: tests for new enum constants
│   └── test_query_validation_pbt.py # EXISTING: must pass unchanged
```

**Structure Decision**: Two new internal modules (`bookmark_builders.py`, `segfilter.py`) alongside existing internal modules. This keeps the segfilter converter isolated (flows-specific complexity) and groups the section builders together (shared across insights/funnels/retention). The existing `validation.py` is refactored in-place to delegate to extracted helpers.

## Implementation Phases

### Phase A: Extract Shared Builders (FR-001, FR-002, FR-006, FR-010, FR-011)

Create `_internal/bookmark_builders.py` with:

1. **`build_time_section()`** — Extract lines 1704-1728 from `workspace.py:_build_query_params()`. Accepts `from_date`, `to_date`, `last`, `unit`. Returns `list[dict]` (the `sections.time` array).
2. **`build_date_range()`** — New function for flows. Accepts `from_date`, `to_date`, `last`. Returns flat `date_range` dict.
3. **`build_filter_section()`** — Extract lines 1731-1734 from `workspace.py:_build_query_params()`. Accepts `where: Filter | list[Filter] | None`. Returns `list[dict]` (the `sections.filter` array). Delegates to `_build_filter_entry()`.
4. **`build_group_section()`** — Extract lines 1737-1772 from `workspace.py:_build_query_params()`. Accepts `group_by: str | GroupBy | list[str | GroupBy] | None`. Returns `list[dict]` (the `sections.group` array).

Then refactor `_build_query_params()` to call these helpers. Verify all existing tests pass.

### Phase B: Extract Shared Validators (FR-003, FR-004, FR-005)

In `_internal/validation.py`:

1. **`validate_time_args()`** — Extract rules V7-V10, V15, V20 (lines 414-512). Accepts `from_date`, `to_date`, `last`. Returns `list[ValidationError]`.
2. **`validate_group_by_args()`** — Extract rules V11-V12, V18, V24 (lines 514-588). Accepts `group_by`. Returns `list[ValidationError]`.

Then refactor `validate_query_args()` to call these helpers. Verify all existing tests pass identically.

### Phase C: Segfilter Converter (FR-007)

Create `_internal/segfilter.py` with:

1. **`build_segfilter_entry()`** — Convert a `Filter` object to segfilter format. Handles all 15+ operator types currently exposed by `Filter`. Reference: `analytics/iron/common/widgets/property-filter-menu/models/segfilter.ts:toSegfilterFilter()`.

Key translations:
- Operator mapping: `"equals"` → `"=="`, `"does not equal"` → `"!="`, `"contains"` → `"in"`, `"is greater than"` → `">"`, etc.
- Value formatting: numbers stringified, dates `YYYY-MM-DD` → `MM/DD/YYYY`
- Property structure: `{"name": prop, "source": resource_type, "type": property_type}`
- Existence operators: `"is set"` / `"is not set"` with correct empty operand

### Phase D: Extend Bookmark Enums (FR-008)

In `_internal/bookmark_enums.py`, add:

1. **`VALID_FUNNEL_ORDER`** — `frozenset({"loose", "any"})`
2. **`VALID_CONVERSION_WINDOW_UNITS`** — `frozenset({"second", "minute", "hour", "day", "week", "month", "session"})`
3. **`VALID_RETENTION_UNITS`** — `frozenset({"day", "week", "month"})`
4. **`VALID_RETENTION_ALIGNMENT`** — `frozenset({"birth", "interval_start"})`
5. **`VALID_FLOWS_COUNT_TYPES`** — `frozenset({"unique", "total", "session"})`
6. Verify existing `VALID_MATH_FUNNELS`, `VALID_MATH_RETENTION` are complete per design doc
7. Extend `VALID_MATH_FUNNELS` if needed (add percentile/property-aggregation math types)

### Phase E: Non-Regression Verification (FR-009)

1. Run full test suite — zero failures
2. Property-based tests comparing pre/post refactoring output
3. Mutation testing on new code — 80%+ kill rate
4. Code coverage check — 90%+ on new modules

## Complexity Tracking

No constitution violations. No complexity justifications needed.
