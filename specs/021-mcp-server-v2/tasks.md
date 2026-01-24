# Tasks: MCP Server v2 - Intelligent Analytics Platform

**Input**: Design documents from `/specs/021-mcp-server-v2/`
**Prerequisites**: plan.md (required), spec.md (required), research.md, data-model.md, contracts/tools.yaml

**Tests**: Not explicitly requested in spec. Tests should be added per project standards but are not included as dedicated tasks.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

Based on plan.md structure:

- **Source**: `mp_mcp/src/mp_mcp/`
- **Tests**: `mp_mcp/tests/`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Create project structure for new tool categories and middleware

- [x] T001 Create directory structure: `mp_mcp/src/mp_mcp/tools/intelligent/`
- [x] T002 [P] Create directory structure: `mp_mcp/src/mp_mcp/tools/composed/`
- [x] T003 [P] Create directory structure: `mp_mcp/src/mp_mcp/tools/interactive/`
- [x] T004 [P] Create directory structure: `mp_mcp/src/mp_mcp/middleware/`
- [x] T005 Create `mp_mcp/src/mp_mcp/types.py` with all result dataclasses from data-model.md

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Middleware layer and package initialization that MUST be complete before ANY user story

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

### Middleware Layer

- [x] T006 Implement caching middleware in `mp_mcp/src/mp_mcp/middleware/caching.py` using ResponseCachingMiddleware for discovery operations (TTL=300s)
- [x] T007 [P] Implement Query API rate limiter in `mp_mcp/src/mp_mcp/middleware/rate_limiting.py` (60/hour, 5 concurrent)
- [x] T008 [P] Implement Export API rate limiter in `mp_mcp/src/mp_mcp/middleware/rate_limiting.py` (60/hour, 3/sec, 100 concurrent)
- [x] T009 [P] Implement audit logging middleware in `mp_mcp/src/mp_mcp/middleware/audit.py` with timing and outcomes
- [x] T010 Create middleware package init in `mp_mcp/src/mp_mcp/middleware/__init__.py` exporting all middleware classes

### Tool Package Initialization

- [x] T011 [P] Create `mp_mcp/src/mp_mcp/tools/intelligent/__init__.py` with tool registration
- [x] T012 [P] Create `mp_mcp/src/mp_mcp/tools/composed/__init__.py` with tool registration
- [x] T013 [P] Create `mp_mcp/src/mp_mcp/tools/interactive/__init__.py` with tool registration

### Server Integration

- [x] T014 Register middleware in `mp_mcp/src/mp_mcp/server.py` (order: Logging → Rate Limiting → Caching)
- [x] T015 Import and register new tool packages in `mp_mcp/src/mp_mcp/server.py`

**Checkpoint**: Foundation ready - user story implementation can now begin in parallel

---

## Phase 3: User Story 1 - Diagnose Metric Drop with AI Synthesis (Priority: P1) 🎯 MVP

**Goal**: Enable analysts to diagnose metric drops with a single tool invocation that synthesizes findings via AI

**Independent Test**: Invoke `diagnose_metric_drop(event="signup", date="2026-01-07")` and receive structured analysis with drop confirmation, primary driver, and recommendations (or raw data with hints if sampling unavailable)

### Implementation for User Story 1

- [x] T016 [US1] Create helper function `gather_diagnosis_data()` in `mp_mcp/src/mp_mcp/tools/intelligent/diagnose.py` that executes baseline comparison and segment analysis
- [x] T017 [US1] Create synthesis prompt template for metric drop analysis in `mp_mcp/src/mp_mcp/tools/intelligent/diagnose.py`
- [x] T018 [US1] Implement `diagnose_metric_drop` tool with ctx.sample() and graceful degradation in `mp_mcp/src/mp_mcp/tools/intelligent/diagnose.py`
- [x] T019 [US1] Add structured output parsing for DiagnosisResult in `mp_mcp/src/mp_mcp/tools/intelligent/diagnose.py`

**Checkpoint**: User Story 1 should be fully functional - test by asking about a metric drop

---

## Phase 4: User Story 2 - Natural Language Analytics Queries (Priority: P1)

**Goal**: Enable analysts to ask questions in plain English and receive synthesized answers

**Independent Test**: Ask "What features do our best users engage with?" and receive a comprehensive answer with supporting data

### Implementation for User Story 2

- [x] T020 [US2] Create `generate_execution_plan()` function that interprets natural language questions in `mp_mcp/src/mp_mcp/tools/intelligent/ask.py`
- [x] T021 [US2] Create query executor that runs queries from ExecutionPlan in `mp_mcp/src/mp_mcp/tools/intelligent/ask.py`
- [x] T022 [US2] Create synthesis prompt template for query results in `mp_mcp/src/mp_mcp/tools/intelligent/ask.py`
- [x] T023 [US2] Implement `ask_mixpanel` tool with ctx.sample() and graceful degradation in `mp_mcp/src/mp_mcp/tools/intelligent/ask.py`

**Checkpoint**: User Story 2 should be fully functional - test with natural language questions

---

## Phase 5: User Story 3 - Complete Product Health Dashboard (Priority: P1)

**Goal**: Provide comprehensive AARRR metrics in a single request

**Independent Test**: Request product health dashboard with signup event and receive metrics for all applicable AARRR categories with trends

### Implementation for User Story 3

- [x] T024 [P] [US3] Create `compute_acquisition()` helper in `mp_mcp/src/mp_mcp/tools/composed/dashboard.py`
- [x] T025 [P] [US3] Create `compute_activation()` helper in `mp_mcp/src/mp_mcp/tools/composed/dashboard.py`
- [x] T026 [P] [US3] Create `compute_retention()` helper in `mp_mcp/src/mp_mcp/tools/composed/dashboard.py`
- [x] T027 [P] [US3] Create `compute_revenue()` helper in `mp_mcp/src/mp_mcp/tools/composed/dashboard.py`
- [x] T028 [P] [US3] Create `compute_referral()` helper in `mp_mcp/src/mp_mcp/tools/composed/dashboard.py`
- [x] T029 [US3] Implement `product_health_dashboard` tool composing all AARRR helpers in `mp_mcp/src/mp_mcp/tools/composed/dashboard.py`
- [x] T030 [US3] Add health score computation (1-10 per category) in `mp_mcp/src/mp_mcp/tools/composed/dashboard.py`

**Checkpoint**: User Story 3 should be fully functional - test with dashboard request

---

## Phase 6: User Story 4 - Structured GQM Investigation (Priority: P2)

**Goal**: Provide systematic investigation framework using Goal-Question-Metric methodology

**Independent Test**: State goal "understand why retention is declining" and receive decomposed questions with queries and findings

### Implementation for User Story 4

- [x] T031 [US4] Create `classify_aarrr_category()` function in `mp_mcp/src/mp_mcp/tools/composed/gqm.py`
- [x] T032 [US4] Create `generate_questions()` function that produces 3-5 sub-questions in `mp_mcp/src/mp_mcp/tools/composed/gqm.py`
- [x] T033 [US4] Create `execute_question_queries()` function in `mp_mcp/src/mp_mcp/tools/composed/gqm.py`
- [x] T034 [US4] Implement `gqm_investigation` tool with synthesis in `mp_mcp/src/mp_mcp/tools/composed/gqm.py`

**Checkpoint**: User Story 4 should be fully functional - test with high-level goals

---

## Phase 7: User Story 5 - Funnel Optimization Report (Priority: P2)

**Goal**: Analyze funnel performance, identify bottlenecks, and generate recommendations

**Independent Test**: Request optimization for a saved funnel and receive step-by-step analysis with recommendations

### Implementation for User Story 5

- [x] T035 [US5] Create `analyze_funnel_steps()` function that identifies bottleneck in `mp_mcp/src/mp_mcp/tools/intelligent/funnel_report.py`
- [x] T036 [US5] Create `segment_funnel_performance()` function in `mp_mcp/src/mp_mcp/tools/intelligent/funnel_report.py`
- [x] T037 [US5] Create synthesis prompt template for funnel optimization in `mp_mcp/src/mp_mcp/tools/intelligent/funnel_report.py`
- [x] T038 [US5] Implement `funnel_optimization_report` tool with ctx.sample() and graceful degradation in `mp_mcp/src/mp_mcp/tools/intelligent/funnel_report.py`

**Checkpoint**: User Story 5 should be fully functional - test with saved funnel ID

---

## Phase 8: User Story 6 - Safe Large Data Fetch with Confirmation (Priority: P2)

**Goal**: Prevent accidental large fetches by requesting confirmation before proceeding

**Independent Test**: Request large date range fetch and receive estimate with confirmation prompt before execution

### Implementation for User Story 6

- [x] T039 [US6] Create `estimate_event_count()` function using top_events or historical data in `mp_mcp/src/mp_mcp/tools/interactive/safe_fetch.py`
- [x] T040 [US6] Create FetchConfirmation dataclass for elicitation response in `mp_mcp/src/mp_mcp/tools/interactive/safe_fetch.py`
- [x] T041 [US6] Implement `safe_large_fetch` tool with ctx.elicit() in `mp_mcp/src/mp_mcp/tools/interactive/safe_fetch.py`
- [x] T042 [US6] Handle confirmation responses (proceed, cancel, reduce scope) in `mp_mcp/src/mp_mcp/tools/interactive/safe_fetch.py`

**Checkpoint**: User Story 6 should be fully functional - test with large date range request

---

## Phase 9: User Story 9 - Long-Running Operations with Progress (Priority: P2)

**Goal**: Add progress reporting and cancellation support to existing fetch tools

**Independent Test**: Start multi-day fetch and observe progress updates, then optionally cancel mid-operation

### Implementation for User Story 9

- [x] T043 [US9] Add `@mcp.tool(task=True)` decorator and Progress dependency to `fetch_events` in `mp_mcp/src/mp_mcp/tools/fetch.py`
- [x] T044 [US9] Implement day-by-day progress reporting in `fetch_events` in `mp_mcp/src/mp_mcp/tools/fetch.py`
- [x] T045 [US9] Add cancellation handling with partial result preservation in `fetch_events` in `mp_mcp/src/mp_mcp/tools/fetch.py`
- [x] T046 [P] [US9] Add `@mcp.tool(task=True)` decorator and Progress dependency to `fetch_profiles` in `mp_mcp/src/mp_mcp/tools/fetch.py`
- [x] T047 [US9] Implement page-by-page progress reporting in `fetch_profiles` in `mp_mcp/src/mp_mcp/tools/fetch.py`
- [x] T048 [US9] Add cancellation handling with partial result preservation in `fetch_profiles` in `mp_mcp/src/mp_mcp/tools/fetch.py`

**Checkpoint**: User Story 9 should be fully functional - test with long-running fetches

---

## Phase 10: User Story 7 - Interactive Guided Analysis (Priority: P3)

**Goal**: Guide users through analysis with structured prompts and choices

**Independent Test**: Start analysis session and be guided through focus selection, initial results, and drill-down choices

### Implementation for User Story 7

- [x] T049 [US7] Create AnalysisChoice and SegmentChoice dataclasses in `mp_mcp/src/mp_mcp/tools/interactive/guided.py`
- [x] T050 [US7] Create `prompt_focus_selection()` function using ctx.elicit() in `mp_mcp/src/mp_mcp/tools/interactive/guided.py`
- [x] T051 [US7] Create `run_initial_analysis()` function in `mp_mcp/src/mp_mcp/tools/interactive/guided.py`
- [x] T052 [US7] Create `prompt_segment_selection()` function using ctx.elicit() in `mp_mcp/src/mp_mcp/tools/interactive/guided.py`
- [x] T053 [US7] Implement `guided_analysis` tool with multi-step elicitation in `mp_mcp/src/mp_mcp/tools/interactive/guided.py`

**Checkpoint**: User Story 7 should be fully functional - test with interactive session

---

## Phase 11: User Story 8 - Cohort Comparison Across Dimensions (Priority: P3)

**Goal**: Compare two user cohorts across behavioral dimensions

**Independent Test**: Define two cohorts and receive comparative analysis of event frequency, retention, and top events

### Implementation for User Story 8

- [x] T054 [US8] Create `compare_event_frequency()` function in `mp_mcp/src/mp_mcp/tools/composed/cohort.py`
- [x] T055 [P] [US8] Create `compare_retention()` function in `mp_mcp/src/mp_mcp/tools/composed/cohort.py`
- [x] T056 [P] [US8] Create `compare_top_events()` function in `mp_mcp/src/mp_mcp/tools/composed/cohort.py`
- [x] T057 [US8] Implement `cohort_comparison` tool composing all comparison functions in `mp_mcp/src/mp_mcp/tools/composed/cohort.py`
- [x] T058 [US8] Add optional statistical significance calculation in `mp_mcp/src/mp_mcp/tools/composed/cohort.py`

**Checkpoint**: User Story 8 should be fully functional - test with two cohort filters

---

## Phase 12: User Story 10 - Framework-Embedded Analysis Prompts (Priority: P3)

**Goal**: Provide reusable analytics framework prompts

**Independent Test**: Load GQM decomposition prompt with a goal and receive structured investigation guidance

### Implementation for User Story 10

- [x] T059 [US10] Add `gqm_decomposition` prompt in `mp_mcp/src/mp_mcp/prompts.py`
- [x] T060 [P] [US10] Add `growth_accounting` (AARRR) prompt with benchmarks in `mp_mcp/src/mp_mcp/prompts.py`
- [x] T061 [P] [US10] Add `experiment_analysis` prompt for A/B test evaluation in `mp_mcp/src/mp_mcp/prompts.py`
- [x] T062 [P] [US10] Add `data_quality_audit` prompt for implementation assessment in `mp_mcp/src/mp_mcp/prompts.py`

**Checkpoint**: User Story 10 should be fully functional - test by loading each prompt

---

## Phase 13: User Story 11 - Dynamic Resource Templates (Priority: P3)

**Goal**: Provide quick access to pre-computed analytics views

**Independent Test**: Request `analysis://retention/{event}/weekly` and receive 12-week retention curve data

### Implementation for User Story 11

- [x] T063 [US11] Add `analysis://retention/{event}/weekly` resource template in `mp_mcp/src/mp_mcp/resources.py`
- [x] T064 [P] [US11] Add `analysis://trends/{event}/{days}` resource template in `mp_mcp/src/mp_mcp/resources.py`
- [x] T065 [P] [US11] Add `users://{id}/journey` resource template in `mp_mcp/src/mp_mcp/resources.py`
- [x] T066 [P] [US11] Add `recipes://weekly-review` resource in `mp_mcp/src/mp_mcp/resources.py`
- [x] T067 [P] [US11] Add `recipes://churn-investigation` resource in `mp_mcp/src/mp_mcp/resources.py`

**Checkpoint**: User Story 11 should be fully functional - test by accessing each resource

---

## Phase 14: Polish & Cross-Cutting Concerns

**Purpose**: Final validation and improvements affecting multiple user stories

- [x] T068 Run `just check` to verify linting, type checking, and existing tests pass
- [x] T069 [P] Run mypy --strict on all new modules in `mp_mcp/src/mp_mcp/`
- [x] T070 [P] Add docstrings to all new functions and classes per project standards
- [ ] T071 Validate all intelligent tools work with and without sampling
- [ ] T072 Validate all elicitation tools work with and without elicitation support
- [ ] T073 Validate all task-enabled tools work with and without task support
- [ ] T074 Run quickstart.md validation scenarios end-to-end
- [ ] T075 Update `mp_mcp/README.md` with new tool documentation

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - BLOCKS all user stories
- **User Stories (Phases 3-13)**: All depend on Foundational phase completion
  - P1 stories (US1, US2, US3) can proceed in parallel after Foundational
  - P2 stories (US4, US5, US6, US9) can proceed in parallel after Foundational
  - P3 stories (US7, US8, US10, US11) can proceed in parallel after Foundational
- **Polish (Phase 14)**: Depends on all user stories being complete

### User Story Dependencies

| Story               | Dependencies      | Can Parallel With |
| ------------------- | ----------------- | ----------------- |
| US1 (diagnose)      | Foundational only | US2, US3          |
| US2 (ask)           | Foundational only | US1, US3          |
| US3 (dashboard)     | Foundational only | US1, US2          |
| US4 (GQM)           | Foundational only | US5, US6, US9     |
| US5 (funnel report) | Foundational only | US4, US6, US9     |
| US6 (safe fetch)    | Foundational only | US4, US5, US9     |
| US9 (task-enabled)  | Foundational only | US4, US5, US6     |
| US7 (guided)        | Foundational only | US8, US10, US11   |
| US8 (cohort)        | Foundational only | US7, US10, US11   |
| US10 (prompts)      | Foundational only | US7, US8, US11    |
| US11 (resources)    | Foundational only | US7, US8, US10    |

### Within Each User Story

- Helper functions before main tool
- Prompt templates before tool implementation
- Core functionality before optional features
- Story complete before moving to next priority

### Parallel Opportunities

- All Setup tasks (T002-T004) can run in parallel
- All package init tasks (T011-T013) can run in parallel
- Middleware tasks T007-T009 can run in parallel
- P1 stories (US1, US2, US3) can all run in parallel after Foundational
- P2 stories (US4, US5, US6, US9) can all run in parallel
- P3 stories (US7, US8, US10, US11) can all run in parallel
- Within US3: AARRR helper functions (T024-T028) can run in parallel
- Within US11: All resource templates can run in parallel

---

## Parallel Example: Phase 2 (Foundational)

```bash
# Launch all package init tasks together:
Task: "Create mp_mcp/src/mp_mcp/tools/intelligent/__init__.py with tool registration"
Task: "Create mp_mcp/src/mp_mcp/tools/composed/__init__.py with tool registration"
Task: "Create mp_mcp/src/mp_mcp/tools/interactive/__init__.py with tool registration"

# Launch all middleware implementations together:
Task: "Implement Query API rate limiter in middleware/rate_limiting.py"
Task: "Implement Export API rate limiter in middleware/rate_limiting.py"
Task: "Implement audit logging middleware in middleware/audit.py"
```

## Parallel Example: P1 User Stories

```bash
# After Foundational phase, launch all P1 stories together:
# Developer A: User Story 1 (diagnose_metric_drop)
Task: "Implement diagnose_metric_drop tool in tools/intelligent/diagnose.py"

# Developer B: User Story 2 (ask_mixpanel)
Task: "Implement ask_mixpanel tool in tools/intelligent/ask.py"

# Developer C: User Story 3 (product_health_dashboard)
Task: "Implement product_health_dashboard tool in tools/composed/dashboard.py"
```

---

## Implementation Strategy

### MVP First (P1 User Stories Only)

1. Complete Phase 1: Setup (T001-T005)
2. Complete Phase 2: Foundational (T006-T015)
3. Complete Phase 3: User Story 1 - Diagnose Metric Drop
4. **STOP and VALIDATE**: Test diagnose_metric_drop independently
5. Complete Phase 4: User Story 2 - Natural Language Queries
6. Complete Phase 5: User Story 3 - Product Health Dashboard
7. **STOP and VALIDATE**: All P1 stories functional - Deploy/Demo

### Incremental Delivery

1. Setup + Foundational → Foundation ready
2. Add P1 stories (US1, US2, US3) → Test independently → Deploy/Demo (MVP!)
3. Add P2 stories (US4, US5, US6, US9) → Test independently → Deploy/Demo
4. Add P3 stories (US7, US8, US10, US11) → Test independently → Deploy/Demo
5. Polish phase → Final validation and documentation

### Parallel Team Strategy

With multiple developers:

1. Team completes Setup + Foundational together
2. Once Foundational is done:
   - Developer A: US1 (diagnose_metric_drop)
   - Developer B: US2 (ask_mixpanel)
   - Developer C: US3 (product_health_dashboard)
3. Then continue with P2 stories:
   - Developer A: US4 + US5 (GQM + funnel)
   - Developer B: US6 + US9 (safe fetch + task-enabled)
4. Finally P3 stories in parallel

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Each user story is independently completable and testable
- Graceful degradation is required for all Tier 3 tools (sampling unavailable)
- Elicitation fallback is required for all interactive tools
- Task fallback (synchronous execution) is required for all task-enabled tools
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
