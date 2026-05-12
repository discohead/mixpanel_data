# Implementation Plan: Unified Query Engine Completeness

**Branch**: `040-query-engine-completeness` | **Date**: 2026-04-14 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/040-query-engine-completeness/spec.md`

## Summary

Close all 29 confirmed gaps in the unified query engine identified by the Mixpanel Query API Capability Audit. The work expands existing Literal types (MathType +7, RetentionMathType +2, FunnelMathType +1), adds core query parameters (segment method, funnel reentry mode, retention unbounded/cumulative modes), introduces new feature types (time comparison, frequency analysis, cohort aggregations), and fills completeness gaps (filter methods, data group scoping, flow features). All changes are additive with backward-compatible defaults.

## Technical Context

**Language/Version**: Python 3.10+
**Primary Dependencies**: httpx, Pydantic v2, Typer, Rich, pandas, Hypothesis
**Storage**: N/A — query parameter types only, no persistence
**Testing**: pytest + Hypothesis (PBT) + mutmut (mutation testing)
**Target Platform**: Library (PyPI) + CLI
**Project Type**: library + cli
**Performance Goals**: N/A — type expansions and parameter additions
**Constraints**: mypy --strict, ruff check/format, 90% test coverage, 80% mutation score
**Scale/Scope**: 29 gaps across 17 implementation steps in 3 phases

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Evidence |
|-----------|--------|----------|
| I. Library-First | PASS | All changes are to library types and builders; CLI wraps library |
| II. Agent-Native Design | PASS | No interactive elements added; output remains structured JSON |
| III. Context Window Efficiency | PASS | No changes to data retrieval patterns; type annotations only |
| IV. Two Data Paths | PASS | Query param changes apply to live queries via bookmark API |
| V. Explicit Over Implicit | PASS | All new params are explicit, keyword-only, optional with defaults |
| VI. Unix Philosophy | PASS | No change to composability or output formatting |
| VII. Secure by Default | PASS | No credential or auth changes |

**Quality Gates**:
- [x] All new types will have type hints (mypy --strict)
- [x] All new types will have docstrings (Google style)
- [x] ruff check + ruff format enforced
- [x] Tests will exist for all new functionality
- [x] No new CLI commands (param expansions flow through existing commands)

**Post-Design Re-check**: All principles still PASS. No new architectural decisions required — all changes follow established patterns (frozen dataclasses, factory methods, builder functions, validation rules).

## Project Structure

### Documentation (this feature)

```text
specs/040-query-engine-completeness/
├── spec.md              # Feature specification (8 user stories, 29 FRs)
├── plan.md              # This file
├── research.md          # Phase 0: codebase + power-tools research
├── data-model.md        # Phase 1: entity definitions
├── quickstart.md        # Phase 1: usage examples
├── contracts/
│   └── public-api.md    # Phase 1: API contract changes
├── checklists/
│   └── requirements.md  # Spec quality checklist
└── tasks.md             # Phase 2 output (/speckit.tasks)
```

### Source Code (repository root)

```text
src/mixpanel_data/
├── _literal_types.py           # Phase A: expand MathType, RetentionMathType, FunnelMathType
│                                #          add SegmentMethod, FunnelReentryMode, RetentionUnboundedMode,
│                                #          TimeComparisonType, TimeComparisonUnit, CohortAggregationType,
│                                #          FlowSessionEvent
├── types.py                    # Phase A: add segment_method to Metric, 7 Filter factory methods
│                                # Phase B: add TimeComparison, FrequencyBreakdown, FrequencyFilter,
│                                #          add aggregation to CohortCriteria.did_event()
│                                # Phase C: add session_event to FlowStep
├── __init__.py                 # All phases: export new types
├── workspace.py                # Phase A: thread segment_method, reentry_mode, unbounded_mode, cumulative
│                                # Phase B: add time_comparison param to 3 query methods
│                                # Phase C: add data_group_id to all query methods, enhance flow where
├── _internal/
│   ├── bookmark_builders.py    # Phase A: thread segment_method, reentry_mode, unbounded_mode, cumulative
│   │                            # Phase B: add time_comparison builder, frequency builders
│   │                            # Phase C: thread data_group_id, add flow property filter builder
│   ├── bookmark_enums.py       # Phase A: update MATH_REQUIRING_PROPERTY, add new enum constants
│   │                            # Phase B: add frequency and time comparison enums
│   └── validation.py           # Phase A: add reentry_mode, unbounded_mode, segment_method validation
│                                # Phase B: add time_comparison, frequency, aggregation validation
│                                # Phase C: add data_group_id, flow filter validation

tests/
├── test_literal_types.py       # Phase A: new math type coverage
├── test_types.py               # All phases: new type construction and validation
├── test_types_pbt.py           # All phases: property-based tests for new types
├── test_bookmark_builders.py   # All phases: builder output verification
├── test_validation.py          # All phases: validation rule coverage
├── test_workspace.py           # All phases: query method integration tests
└── test_bookmark_enums.py      # Phase A: enum constant coverage
```

**Structure Decision**: No new files or directories in `src/`. All changes are modifications to existing files following established patterns. New test files may be needed for PBT coverage of new types.

## Complexity Tracking

No violations. All changes follow established patterns:
- Literal type expansion: same pattern as existing types
- Frozen dataclass addition: same pattern as Metric, GroupBy, FlowStep
- Factory method addition: same pattern as existing Filter methods
- Builder function addition: same pattern as build_filter_section, build_group_section
- Validation rule addition: same pattern as existing validate_* functions
- Workspace parameter addition: same pattern as existing query method params

## Phase A: Type Expansions and Core Parameters (Tier 1)

### A1: Expand MathType Literal (+7 values)

**Files**: `_literal_types.py`
**Effort**: TRIVIAL

Add `cumulative_unique`, `sessions`, `unique_values`, `most_frequent`, `first_value`, `multi_attribution`, `numeric_summary` to `MathType` Literal. Update docstring table.

### A2: Expand RetentionMathType Literal (+2 values)

**Files**: `_literal_types.py`
**Effort**: TRIVIAL

Add `total`, `average` to `RetentionMathType` Literal. Update docstring table.

### A3: Expand FunnelMathType Literal (+1 value)

**Files**: `_literal_types.py`
**Effort**: TRIVIAL

Add `histogram` to `FunnelMathType` Literal. Update docstring table.

### A4: Update MATH_REQUIRING_PROPERTY (+5 values)

**Files**: `bookmark_enums.py`
**Effort**: TRIVIAL

Add `unique_values`, `most_frequent`, `first_value`, `multi_attribution`, `numeric_summary` to `MATH_REQUIRING_PROPERTY`. These 5 new math types all require a property parameter.

### A5: Add SegmentMethod + Metric field

**Files**: `_literal_types.py`, `types.py`, `bookmark_builders.py`, `workspace.py`, `validation.py`
**Effort**: SMALL

1. Add `SegmentMethod = Literal["all", "first"]` to `_literal_types.py`
2. Add `VALID_SEGMENT_METHODS` to `bookmark_enums.py`
3. Add `segment_method: SegmentMethod | None = None` field to `Metric` dataclass
4. Thread `segmentMethod` into measurement block in `_build_query_params()`
5. Add validation: reject segment_method for insights-only queries (valid for funnels, retention, frequency)

### A6: Add FunnelReentryMode parameter

**Files**: `_literal_types.py`, `bookmark_enums.py`, `workspace.py`, `bookmark_builders.py`, `validation.py`
**Effort**: SMALL

1. Add `FunnelReentryMode = Literal["default", "basic", "aggressive", "optimized"]` to `_literal_types.py`
2. Add `VALID_FUNNEL_REENTRY_MODES` to `bookmark_enums.py`
3. Add `reentry_mode: FunnelReentryMode | None = None` to `query_funnel()` and `build_funnel_params()`
4. Thread `funnelReentryMode` into behavior block in `_build_funnel_params()`
5. Add validation in `validate_funnel_args()`

### A7: Add RetentionUnboundedMode + retentionCumulative parameters

**Files**: `_literal_types.py`, `bookmark_enums.py`, `workspace.py`, `bookmark_builders.py`, `validation.py`
**Effort**: SMALL

1. Add `RetentionUnboundedMode = Literal["none", "carry_back", "carry_forward", "consecutive_forward"]` to `_literal_types.py`
2. Add `VALID_RETENTION_UNBOUNDED_MODES` to `bookmark_enums.py`
3. Add `unbounded_mode: RetentionUnboundedMode | None = None` and `retention_cumulative: bool = False` to `query_retention()` and `build_retention_params()`
4. Thread `retentionUnboundedMode` into behavior block and `retentionCumulative` into measurement block in `_build_retention_params()`
5. Add validation in `validate_retention_args()`

### A8: Add missing Filter factory methods (7 methods)

**Files**: `types.py`
**Effort**: SMALL

Add 7 factory methods following existing patterns:
- `not_between(prop, min, max)` → operator `"not between"`, property_type `"number"`
- `starts_with(prop, prefix)` → operator `"starts with"`, property_type `"string"`
- `ends_with(prop, suffix)` → operator `"ends with"`, property_type `"string"`
- `date_not_between(prop, from, to)` → operator `"was not between"`, property_type `"datetime"`
- `in_the_next(prop, qty, unit)` → operator `"was in the next"`, property_type `"datetime"`, with `_date_unit`
- `at_least(prop, val)` → operator `"is at least"`, property_type `"number"`
- `at_most(prop, val)` → operator `"is at most"`, property_type `"number"`

Each follows the exact same pattern as existing methods like `between()`, `greater_than()`, `in_the_last()`.

## Phase B: New Feature Types (Tier 2)

### B1: Add TimeComparison types + parameter

**Files**: `_literal_types.py`, `types.py`, `bookmark_builders.py`, `workspace.py`, `validation.py`
**Effort**: MEDIUM

1. Add `TimeComparisonType` and `TimeComparisonUnit` Literals to `_literal_types.py`
2. Add `VALID_TIME_COMPARISON_TYPES` and `VALID_TIME_COMPARISON_UNITS` to `bookmark_enums.py`
3. Create `TimeComparison` frozen dataclass in `types.py` with factory methods (`relative()`, `absolute_start()`, `absolute_end()`)
4. Add `build_time_comparison()` builder to `bookmark_builders.py` — serializes to `displayOptions.timeComparison`
5. Add `time_comparison: TimeComparison | None = None` to `query()`, `query_funnel()`, `query_retention()` and their `build_*` variants
6. Add validation: reject for flows, validate unit/date based on type
7. Thread into `displayOptions` block in all 3 `_build_*_params()` methods

### B2: Add FrequencyBreakdown type + builder

**Files**: `types.py`, `bookmark_builders.py`, `workspace.py`
**Effort**: MEDIUM

1. Create `FrequencyBreakdown` frozen dataclass in `types.py`
2. Add `build_frequency_group_entry()` to `bookmark_builders.py` — produces `sections.group[]` entry with `behaviorType: "$frequency"`, `resourceType: "people"`
3. Update `build_group_section()` to accept `FrequencyBreakdown` in type union
4. Update `group_by` parameter type annotations on `query()` and `build_params()`
5. Add validation for frequency breakdown fields

### B3: Add FrequencyFilter type + builder

**Files**: `types.py`, `bookmark_builders.py`, `workspace.py`
**Effort**: MEDIUM

1. Create `FrequencyFilter` frozen dataclass in `types.py`
2. Add `build_frequency_filter_entry()` to `bookmark_builders.py` — produces `sections.filter[]` entry with `customProperty.behavior` containing frequency definition
3. Update `build_filter_section()` to accept `FrequencyFilter` in type union
4. Update `where` parameter type annotations on `query()` and `build_params()`
5. Add validation: operator must be in `VALID_FREQUENCY_FILTER_OPERATORS`

### B4: Add aggregation operators to CohortCriteria.did_event()

**Files**: `types.py`, `bookmark_enums.py`
**Effort**: MEDIUM

1. Add `CohortAggregationType = Literal[...]` to `_literal_types.py`
2. Add `VALID_COHORT_AGGREGATION_OPERATORS` to `bookmark_enums.py`
3. Add `aggregation: CohortAggregationType | None = None` and `aggregation_property: str | None = None` to `did_event()`
4. Add validation: aggregation requires aggregation_property and vice versa
5. Update behavior serialization to include `aggregationOperator` in the behavioral condition
6. Update selector structure for aggregation-based criteria

## Phase C: Completeness (Tier 3)

### C1: Add data_group_id to all query engines

**Files**: `workspace.py`, `bookmark_builders.py`
**Effort**: SMALL

1. Add `data_group_id: int | None = None` to `query()`, `query_funnel()`, `query_retention()`, `query_flow()` and their `build_*` variants
2. Thread through to all `_build_*_params()` methods
3. Replace 5 hardcoded `dataGroupId: None` / `data_group_id: None` in `bookmark_builders.py` with the parameter value
4. Add validation: must be positive integer if provided

### C2: Add flow breakdowns/segments

**Files**: `workspace.py`, `bookmark_builders.py`, `types.py`
**Effort**: MEDIUM

1. Add `segments` parameter to `query_flow()` and `build_flow_params()` — accepts property-based breakdown spec
2. Add `build_flow_segments()` builder to `bookmark_builders.py`
3. Thread into `_build_flow_params()` → adds `segments` array to flow params

### C3: Add flow exclusions (enhanced)

**Files**: `workspace.py`
**Effort**: SMALL

Flow exclusions are already partially supported (the `exclusions` key exists in `_build_flow_params()` as empty list). Add parameter to accept exclusion events and thread them through.

### C4: Add FlowStep session_event support

**Files**: `types.py`, `workspace.py`
**Effort**: SMALL

1. Add `FlowSessionEvent = Literal["start", "end"]` to `_literal_types.py`
2. Add `session_event: FlowSessionEvent | None = None` to `FlowStep` dataclass
3. Add validation: session_event and event are mutually exclusive
4. Update `_build_flow_params()` to emit `session_event` field when set

### C5: Add flow global property filters

**Files**: `workspace.py`, `bookmark_builders.py`
**Effort**: SMALL

1. Update flow `where` parameter to accept property filters (currently only cohort filters)
2. Add `build_flow_property_filter()` builder for `filter_by_event` structure
3. Update `_build_flow_params()` to check filter type and route to `filter_by_cohort` or `filter_by_event`

## Implementation Dependencies

```
Phase A (can be parallelized within phase):
  A1, A2, A3, A4: Independent — just literal/enum expansions
  A5: Depends on A1 (new MathType values affect validation)
  A6: Independent
  A7: Depends on A2 (new RetentionMathType values)
  A8: Independent

Phase B (requires Phase A complete):
  B1: Independent
  B2: Independent
  B3: Independent
  B4: Independent
  (All B items are independent of each other)

Phase C (requires Phase B complete for full validation):
  C1: Independent
  C2: Independent
  C3: Independent  
  C4: Independent
  C5: Independent
  (All C items are independent of each other)
```

## Testing Strategy

### Unit Tests (per step)

Each implementation step includes tests for:
1. **Happy path**: New type/parameter accepted, produces correct output
2. **Validation**: Invalid values rejected with clear error messages
3. **Backward compatibility**: Omitting new param produces identical output to pre-change behavior
4. **Edge cases**: Boundary values, mutually exclusive params, type combinations

### Property-Based Tests (Hypothesis)

New PBT tests for:
- `TimeComparison` construction: arbitrary valid/invalid type+unit+date combinations
- `FrequencyBreakdown` construction: arbitrary bucket configurations
- `FrequencyFilter` construction: arbitrary operator+value combinations
- Expanded `MathType` values: all 22 values accepted by builder
- New `Filter` factory methods: operator string correctness

### Integration Tests

- End-to-end: `Workspace.build_*_params()` with new parameters → validate against `validate_bookmark()`
- Roundtrip: Build params with new features → validate structure matches power-tools reference JSON

### Mutation Testing

- Target 80%+ mutation score on new code
- Focus on validation logic (where mutations are most dangerous)
