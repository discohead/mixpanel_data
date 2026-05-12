# Tasks: Typed Flow Query API

**Input**: Design documents from `/specs/034-flow-query/`  
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/public-api.md  
**Tests**: Included — project mandates strict TDD (CLAUDE.md)

**Organization**: Tasks grouped by user story for independent implementation and testing.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2)
- Include exact file paths in descriptions

---

## Phase 1: Setup

**Purpose**: Add new dependency and type infrastructure

- [x] T001 Add `networkx>=3.0` dependency in pyproject.toml
- [x] T002 [P] Add `FlowCountType` and `FlowChartType` Literal type aliases in src/mixpanel_data/_literal_types.py
- [x] T003 [P] Extend flows constants in src/mixpanel_data/_internal/bookmark_enums.py — add `VALID_FLOWS_MODES`, `VALID_FLOWS_CONVERSION_WINDOW_UNITS`, and any missing enum sets needed by validation

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Rename existing method and add segfilter converter — MUST complete before user story work

**Caution**: No user story work can begin until this phase is complete

### Rename query_flows → query_saved_flows

- [x] T004 Rename `query_flows()` to `query_saved_flows()` in src/mixpanel_data/_internal/api_client.py (method name only, same signature and behavior)
- [x] T005 [P] Rename `query_flows()` to `query_saved_flows()` in src/mixpanel_data/_internal/services/live_query.py (method name and internal call to api_client)
- [x] T006 [P] Rename `query_flows()` to `query_saved_flows()` in src/mixpanel_data/workspace.py (public method and docstring)
- [x] T007 Update CLI `flows` command in src/mixpanel_data/cli/commands/query.py to call `query_saved_flows()` instead of `query_flows()`
- [x] T008 Update all existing tests: rename `query_flows` references to `query_saved_flows` in tests/unit/test_live_query_bookmarks.py and tests/integration/cli/test_bookmark_commands.py
- [x] T009 Run `just check` to verify rename is complete with zero breakage

### Segfilter Converter

- [x] T010 Write tests for `build_segfilter_entry()` in tests/unit/test_bookmark_builders_segfilter.py — cover string equals, number gt/lt/between, boolean, datetime (MM/DD/YYYY conversion), is_set/is_not_set, contains/does_not_contain, resource type mapping (events→properties, people→user), and value serialization (numbers stringified, dates reformatted)
- [x] T011 Implement `build_segfilter_entry(f: Filter) -> dict[str, Any]` in src/mixpanel_data/_internal/bookmark_builders.py — operator mapping table, property structure mapping, value serialization per research.md Section 1

**Checkpoint**: Foundation ready — all rename and segfilter tests pass, `just check` green

---

## Phase 3: User Story 1 + User Story 2 — Core Flow Query Pipeline (Priority: P1) MVP

**Goal**: Users can execute ad-hoc flow queries with typed arguments, per-step filters, and configuration options, receiving a basic typed result. This combines US1 (simple query) and US2 (filters/config) because the params builder inherently handles both.

**Independent Test**: Call `build_flow_params("Purchase", forward=3)` and verify generated bookmark JSON. Call with `FlowStep` filters and verify segfilter conversion. Mock API and verify `query_flow()` round-trip.

### Types

- [x] T012 [P] [US1] Write tests for `FlowStep` in tests/test_types_flow.py — construction, defaults, frozen immutability, field preservation, string normalization
- [x] T013 [P] [US1] Write tests for `FlowQueryResult` basic behavior in tests/test_types_flow.py — construction, defaults, `to_dict()`, frozen immutability (graph/DataFrame tests deferred to US3)
- [x] T014 [US1] Implement `FlowStep` frozen dataclass in src/mixpanel_data/types.py — `event`, `forward`, `reverse`, `label`, `filters`, `filters_combinator` fields with docstring per contracts/public-api.md
- [x] T015 [US1] Implement `FlowQueryResult` frozen dataclass in src/mixpanel_data/types.py — `computed_at`, `steps`, `flows`, `breakdowns`, `overall_conversion_rate`, `params`, `meta`, `mode` fields; stub `df` property returning basic DataFrame; `to_dict()` method

### Validation (Layer 1 — Argument Validation)

- [x] T016 [P] [US1] Write tests for `validate_flow_args()` in tests/test_validation_flow.py — rules FL1 (empty steps), FL2 (empty event name), FL3 (forward 0-5), FL4 (reverse 0-5), FL5 (forward+reverse>0), FL6 (cardinality 1-50), FL7 (conversion_window positive), FL8 (last positive via shared V7), enum validation for count_type and mode with fuzzy suggestions, multi-error collection
- [x] T017 [US1] Implement `validate_flow_args()` in src/mixpanel_data/_internal/validation.py — follow `validate_retention_args()` pattern, delegate time args to shared `validate_time_args()`, use `_enum_error()` for fuzzy suggestions

### Validation (Layer 2 — Flat Bookmark Validation)

- [x] T018 [P] [US1] Write tests for `validate_flow_bookmark()` in tests/test_validation_flow.py — rules FLB1 (steps non-empty), FLB2 (step event non-empty), FLB3 (count_type valid), FLB4 (chartType valid), FLB5 (date_range present), FLB6 (version==2)
- [x] T019 [US1] Implement `validate_flow_bookmark()` in src/mixpanel_data/_internal/validation.py — separate function (not extending `validate_bookmark()`) since flows have flat structure without `sections`

### Params Builder

- [x] T020 [P] [US1] Write tests for `_build_flow_params()` in tests/test_types_flow.py or tests/unit/test_workspace_flow.py — verify flat bookmark structure (no sections wrapper), steps array with event/forward/reverse/step_label/bool_op/property_filter_params_list, date_range via `build_date_range()`, chartType/flows_merge_type mapping from mode, count_type, cardinality_threshold, conversion_window, version=2, anchor_position, collapse_repeated, show_custom_events, hidden_events, exclusions
- [x] T021 [P] [US2] Write tests for per-step filter integration — `FlowStep` with `filters=[Filter.greater_than("amount", 50)]` produces correct segfilter in `property_filter_params_list`; `filters_combinator="any"` maps to `bool_op="or"`
- [x] T022 [US1] Implement `_build_flow_params()` private method in src/mixpanel_data/workspace.py — builds flat bookmark dict using `build_date_range()` from bookmark_builders, `build_segfilter_entry()` for per-step filters, configuration mapping
- [x] T023 [US1] Implement `_resolve_and_build_flow_params()` private method in src/mixpanel_data/workspace.py — normalize str→FlowStep, apply top-level forward/reverse defaults to steps with None, Layer 1 validate, build params, Layer 2 validate, raise BookmarkValidationError on errors

### API Client

- [x] T024 [P] [US1] Write tests for `arb_funnels_query()` in tests/unit/test_live_query_flow.py — verify POST to `/arb_funnels` with body `{"bookmark": params, "project_id": id, "query_type": "flows_sankey"}`, verify `query_type` switches to `"flows_top_paths"` for paths mode
- [x] T025 [US1] Implement `arb_funnels_query(body: dict) -> dict` in src/mixpanel_data/_internal/api_client.py — POST to `_build_url("query", "/arb_funnels")` with `inject_project_id=False`

### Service Layer

- [x] T026 [P] [US1] Write tests for `query_flow()` service method and `_transform_flow_result()` in tests/unit/test_live_query_flow.py — mock API client, verify sankey response transformation (steps, breakdowns, overallConversionRate, computed_at, metadata), verify top-paths response transformation (flows field), verify error-as-200 handling
- [x] T027 [US1] Implement `query_flow(bookmark_params, project_id, mode)` and `_transform_flow_result(raw, bookmark_params, mode)` in src/mixpanel_data/_internal/services/live_query.py — follow `_transform_retention_result()` pattern for error handling, extract fields from both sankey and top-paths responses

### Workspace Public Methods

- [x] T028 [P] [US1] Write tests for `query_flow()` and `build_flow_params()` workspace methods in tests/test_types_flow.py — verify credential check, verify delegation to `_resolve_and_build_flow_params` then service, verify `build_flow_params()` returns dict without API call
- [x] T029 [US1] Implement `query_flow()` and `build_flow_params()` public methods in src/mixpanel_data/workspace.py — follow `query_retention()`/`build_retention_params()` pattern exactly
- [x] T030 [US1] Run `just check` to verify full pipeline works end-to-end

**Checkpoint**: Core flow query pipeline complete — `build_flow_params()` generates valid params, `query_flow()` executes with mocked API, validation catches invalid args. US1 and US2 independently testable.

---

## Phase 4: User Story 3 — Graph-Based Flow Result Analysis (Priority: P1)

**Goal**: `FlowQueryResult` provides `nodes_df`, `edges_df`, and `graph` (NetworkX DiGraph) properties for rich flow analysis, plus mode-aware `df` for top-paths.

**Independent Test**: Construct `FlowQueryResult` from sample sankey/top-paths data and verify all DataFrame shapes and graph structure.

### DataFrames

- [x] T031 [P] [US3] Write tests for `nodes_df` property in tests/test_types_flow.py — verify columns (step, event, type, count, anchor_type, is_custom_event, conversion_rate_change), one row per node, empty steps→empty DataFrame, totalCount string→int parsing
- [x] T032 [P] [US3] Write tests for `edges_df` property in tests/test_types_flow.py — verify columns (source_step, source_event, target_step, target_event, count, target_type), one row per edge, empty→empty DataFrame
- [x] T033 [P] [US3] Write tests for mode-aware `df` property in tests/test_types_flow.py — sankey mode returns `nodes_df`, paths mode returns tabular paths DataFrame from `flows` field
- [x] T034 [US3] Implement `nodes_df` property on `FlowQueryResult` in src/mixpanel_data/types.py — lazy-cached via `_df_cache` pattern, parse `totalCount` strings to int
- [x] T035 [US3] Implement `edges_df` property on `FlowQueryResult` in src/mixpanel_data/types.py — lazy-cached via separate `_edges_df_cache` field
- [x] T036 [US3] Update `df` property on `FlowQueryResult` in src/mixpanel_data/types.py — mode-aware: return `nodes_df` for sankey, paths DataFrame for top-paths

### NetworkX Graph

- [x] T037 [P] [US3] Write tests for `graph` property in tests/test_types_flow.py — verify DiGraph construction, node keys as `"{event}@{step}"`, node attributes (step, event, type, count, anchor_type), edge attributes (count, type), lazy caching, empty steps→empty graph, same event at multiple steps produces distinct nodes
- [x] T038 [US3] Implement `graph` property on `FlowQueryResult` in src/mixpanel_data/types.py — lazy-cached NetworkX DiGraph built from `steps[].nodes[].edges[]`, using `object.__setattr__` for frozen dataclass cache
- [x] T039 [US3] Run `just check` to verify all graph and DataFrame tests pass

**Checkpoint**: `FlowQueryResult` provides three complementary views (nodes_df, edges_df, graph) for flow analysis. US3 independently testable.

---

## Phase 5: User Story 4 — Multi-Step Anchor Flow Query (Priority: P2)

**Goal**: Users can pass multiple `FlowStep` objects (or mixed string/FlowStep lists) as anchor events in a single flow query.

**Independent Test**: Call `build_flow_params([FlowStep("A", forward=3), FlowStep("B", reverse=2)])` and verify both steps appear in params with correct per-step forward/reverse.

- [x] T040 [P] [US4] Write tests for multi-step normalization in tests/test_types_flow.py — list of strings, list of FlowStep objects, mixed list, single string→list, single FlowStep→list, string steps get top-level forward/reverse defaults, FlowStep with explicit forward/reverse overrides defaults
- [x] T041 [US4] Ensure `_resolve_and_build_flow_params()` handles `Sequence[str | FlowStep]` normalization in src/mixpanel_data/workspace.py — verify single event wrapped in list, mixed inputs normalized, per-step forward/reverse preserved when set
- [x] T042 [US4] Write test for multi-step anchor_position calculation in tests/test_types_flow.py — verify `anchor_position` is set correctly based on step positions
- [x] T043 [US4] Run `just check`

**Checkpoint**: Multi-step anchor queries work. US4 independently testable.

---

## Phase 6: User Story 6 — Rename Verification (Priority: P2)

**Goal**: Verify the rename from Phase 2 is complete and the old name is fully removed.

**Independent Test**: `query_saved_flows(bookmark_id=123)` works; `query_flows` raises AttributeError.

- [x] T044 [US6] Write test in tests/test_types_flow.py verifying `query_flows` attribute does not exist on Workspace (AttributeError)
- [x] T045 [US6] Write test verifying `query_saved_flows(bookmark_id=123)` returns `FlowsResult` (same behavior as old method)
- [x] T046 [US6] Run `just check`

**Checkpoint**: Rename fully verified. US6 independently testable.

---

## Phase 7: User Story 7 — Convenience Methods (Priority: P3)

**Goal**: `FlowQueryResult` provides `top_transitions()` and `drop_off_summary()` for quick answers without graph API knowledge.

**Independent Test**: Construct `FlowQueryResult` from sample data, call convenience methods, verify structured output.

- [x] T047 [P] [US7] Write tests for `top_transitions(n)` in tests/test_types_flow.py — returns list of (source_event, target_event, count) tuples sorted by count descending, respects `n` limit, empty edges→empty list
- [x] T048 [P] [US7] Write tests for `drop_off_summary()` in tests/test_types_flow.py — returns dict with per-step total, dropoff count, dropoff rate; handles empty steps
- [x] T049 [US7] Implement `top_transitions(n=10)` on `FlowQueryResult` in src/mixpanel_data/types.py — use `edges_df` sorted by count
- [x] T050 [US7] Implement `drop_off_summary()` on `FlowQueryResult` in src/mixpanel_data/types.py — iterate nodes, identify DROPOFF type, compute rates
- [x] T051 [US7] Run `just check`

**Checkpoint**: Convenience methods work. US7 independently testable.

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Exports, property-based tests, documentation validation

- [x] T052 [P] Export `FlowStep`, `FlowQueryResult`, `FlowCountType`, `FlowChartType` from src/mixpanel_data/__init__.py — add to imports and `__all__`
- [x] T053 [P] Write property-based tests in tests/test_types_flow_pbt.py — FlowStep immutability, FlowQueryResult DataFrame shape invariants, build_flow_params structure invariants (always has steps/date_range/chartType/version), segfilter round-trip properties
- [x] T054 [P] Update src/mixpanel_data/CLAUDE.md and src/mixpanel_data/_internal/CLAUDE.md with new methods if needed
- [x] T055 Run `just check` — all tests pass, lint clean, typecheck clean, coverage >= 90%
- [x] T056 Validate quickstart.md examples match implemented API signatures

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — can start immediately
- **Foundational (Phase 2)**: Depends on Phase 1 — BLOCKS all user stories
- **US1+US2 (Phase 3)**: Depends on Phase 2 — core pipeline
- **US3 (Phase 4)**: Depends on Phase 3 (needs FlowQueryResult type)
- **US4 (Phase 5)**: Depends on Phase 3 (needs _resolve_and_build_flow_params)
- **US6 (Phase 6)**: Depends on Phase 2 (rename already done, just verification)
- **US7 (Phase 7)**: Depends on Phase 4 (needs nodes_df/edges_df)
- **Polish (Phase 8)**: Depends on all prior phases

### User Story Dependencies

- **US1+US2 (P1)**: Start after Phase 2 — no dependencies on other stories
- **US3 (P1)**: Depends on US1 FlowQueryResult type being defined
- **US4 (P2)**: Depends on US1 normalization pipeline
- **US5 (P2)**: Delivered as part of US1 (validation is baked into the pipeline)
- **US6 (P2)**: Can run after Phase 2 independently
- **US7 (P3)**: Depends on US3 DataFrame properties

### Parallel Opportunities

- T002 + T003 in Phase 1 (different files)
- T004 + T005 + T006 in Phase 2 (different files, same rename)
- T010 + T012 + T013 in Phase 3 (different test/source files)
- T016 + T018 + T020 + T021 in Phase 3 (different test files)
- T024 + T026 + T028 in Phase 3 (different test files)
- T031 + T032 + T033 + T037 in Phase 4 (different test sections)
- T047 + T048 in Phase 7 (different test sections)
- T052 + T053 + T054 in Phase 8 (different files)

---

## Parallel Example: Phase 3 (US1+US2 Core Pipeline)

```text
# Wave 1: Tests for types (parallel)
T012: "Write tests for FlowStep in tests/test_types_flow.py"
T013: "Write tests for FlowQueryResult in tests/test_types_flow.py"

# Wave 2: Implement types (sequential after tests)
T014: "Implement FlowStep in src/mixpanel_data/types.py"
T015: "Implement FlowQueryResult in src/mixpanel_data/types.py"

# Wave 3: Validation + builder tests (parallel)
T016: "Write tests for validate_flow_args in tests/test_validation_flow.py"
T018: "Write tests for validate_flow_bookmark in tests/test_validation_flow.py"
T020: "Write tests for _build_flow_params"
T021: "Write tests for per-step filter integration"

# Wave 4: Implement validation + builder (sequential)
T017: "Implement validate_flow_args"
T019: "Implement validate_flow_bookmark"
T022: "Implement _build_flow_params"
T023: "Implement _resolve_and_build_flow_params"

# Wave 5: API + service tests (parallel)
T024: "Write tests for arb_funnels_query"
T026: "Write tests for query_flow service method"
T028: "Write tests for workspace public methods"

# Wave 6: Implement API + service + workspace (sequential)
T025: "Implement arb_funnels_query"
T027: "Implement query_flow service + _transform_flow_result"
T029: "Implement query_flow/build_flow_params workspace"
```

---

## Implementation Strategy

### MVP First (Phase 1-3 Only)

1. Complete Phase 1: Setup (deps, type aliases)
2. Complete Phase 2: Foundational (rename, segfilter converter)
3. Complete Phase 3: US1+US2 core pipeline
4. **STOP and VALIDATE**: `build_flow_params()` generates valid params, `query_flow()` works with mocked API
5. This alone delivers the primary value: programmatic ad-hoc flow queries

### Incremental Delivery

1. Setup + Foundational → Infrastructure ready
2. Add US1+US2 → Core flow query works (MVP!)
3. Add US3 → Graph and DataFrame analysis (major UX upgrade)
4. Add US4 → Multi-step anchors (power feature)
5. Add US6 → Rename verified (housekeeping)
6. Add US7 → Convenience methods (polish)
7. Polish → Exports, PBT, docs

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- US5 (validation UX) is delivered as part of US1 — validation is baked into `_resolve_and_build_flow_params()`
- TDD is strict: write tests FIRST, verify they FAIL, then implement
- Commit after each task or logical group
- Run `just check` at each checkpoint
