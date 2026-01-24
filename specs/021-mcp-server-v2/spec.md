# Feature Specification: MCP Server v2 - Intelligent Analytics Platform

**Feature Branch**: `021-mcp-server-v2`
**Created**: 2026-01-13
**Status**: Draft
**Input**: Transform mp_mcp from thin API wrapper into intelligent analytics platform with sampling-powered tools, elicitation workflows, composed tools, enhanced resources, framework prompts, middleware, and task-enabled operations.

---

## User Scenarios & Testing _(mandatory)_

### User Story 1 - Diagnose Metric Drop with AI Synthesis (Priority: P1)

An analyst notices signups dropped last Tuesday and wants to understand why without manually running multiple queries and interpreting results.

**Why this priority**: This is the flagship intelligent tool that demonstrates the platform's core value proposition - transforming raw data into actionable insights through AI synthesis.

**Independent Test**: Can be fully tested by asking "Why did signups drop on Tuesday?" and receiving a synthesized analysis with root cause identification and recommendations.

**Acceptance Scenarios**:

1. **Given** a user asks about a metric drop, **When** they invoke the diagnose tool with event name and date, **Then** the system executes baseline comparison, segments by key dimensions, and returns a structured analysis with drop confirmation, primary driver, and recommendations.

2. **Given** sampling is unavailable on the client, **When** the diagnose tool is invoked, **Then** the system returns raw data with manual analysis hints instead of AI synthesis.

3. **Given** the metric did not actually drop, **When** the tool analyzes the data, **Then** it reports that no significant drop was detected with supporting evidence.

---

### User Story 2 - Natural Language Analytics Queries (Priority: P1)

An analyst wants to ask analytics questions in plain English without knowing which specific tools or query parameters to use.

**Why this priority**: Natural language interface dramatically lowers the barrier to analytics, enabling non-technical users to extract insights.

**Independent Test**: Can be fully tested by asking "What features do our best users engage with?" and receiving a comprehensive answer with supporting data.

**Acceptance Scenarios**:

1. **Given** a user asks a natural language question, **When** the system processes it, **Then** it interprets the intent, generates an execution plan, runs appropriate queries, and synthesizes a human-readable answer.

2. **Given** a question that requires multiple query types, **When** processed, **Then** the system orchestrates segmentation, retention, and property analysis as needed.

3. **Given** sampling is unavailable, **When** a natural language query is attempted, **Then** the system returns the execution plan and raw query results for manual interpretation.

---

### User Story 3 - Complete Product Health Dashboard (Priority: P1)

A product manager wants a comprehensive view of product health across all AARRR (Acquisition, Activation, Retention, Revenue, Referral) metrics in one request.

**Why this priority**: Provides immediate, actionable value by consolidating what would otherwise require 5+ separate queries into a single cohesive dashboard.

**Independent Test**: Can be fully tested by requesting a product health dashboard and receiving metrics for each AARRR category with trends.

**Acceptance Scenarios**:

1. **Given** a user requests a product health dashboard, **When** they specify key events (signup, activation, etc.), **Then** the system returns metrics for all applicable AARRR categories.

2. **Given** some AARRR events are not specified, **When** the dashboard is generated, **Then** the system infers likely events from available data or omits those categories with explanation.

3. **Given** a date range is specified, **When** the dashboard is generated, **Then** all metrics reflect that time period with appropriate trend data.

---

### User Story 4 - Structured GQM Investigation (Priority: P2)

An analyst has a high-level goal ("understand why retention is declining") and needs a systematic investigation framework.

**Why this priority**: The GQM (Goal-Question-Metric) framework provides structured methodology for open-ended investigations, building on top of primitive tools.

**Independent Test**: Can be fully tested by stating a goal and receiving decomposed questions with corresponding queries and synthesized findings.

**Acceptance Scenarios**:

1. **Given** a user provides a high-level goal, **When** the investigation runs, **Then** the system classifies the AARRR category, generates 3-5 sub-questions, executes relevant queries, and provides findings with next steps.

2. **Given** a goal related to retention, **When** investigated, **Then** the system generates retention-specific questions about magnitude, segments, behavioral differences, and acquisition mix.

3. **Given** queries fail for some dimensions, **When** the investigation completes, **Then** it reports partial results with clear indication of what succeeded and failed.

---

### User Story 5 - Funnel Optimization Report (Priority: P2)

A growth analyst wants to understand funnel performance, identify the biggest drop-off, and get recommendations for improvement.

**Why this priority**: Funnel optimization is a core analytics use case that benefits significantly from AI-powered synthesis.

**Independent Test**: Can be fully tested by requesting optimization for a saved funnel and receiving step-by-step analysis with actionable recommendations.

**Acceptance Scenarios**:

1. **Given** a funnel ID and date range, **When** the optimization report runs, **Then** it identifies the worst-performing step, segments by key dimensions, and provides prioritized recommendations.

2. **Given** sampling is available, **When** the report is generated, **Then** it includes an executive summary and expected impact for each recommendation.

---

### User Story 6 - Safe Large Data Fetch with Confirmation (Priority: P2)

A user wants to fetch a large date range of events but needs awareness of the data volume before proceeding.

**Why this priority**: Prevents accidental large fetches that could consume significant time and resources without user awareness.

**Independent Test**: Can be fully tested by requesting a large fetch and receiving an estimate with confirmation prompt before execution.

**Acceptance Scenarios**:

1. **Given** a fetch request estimated to exceed 100,000 events, **When** the tool runs, **Then** it presents the estimate and requests confirmation before proceeding.

2. **Given** the user confirms, **When** the fetch proceeds, **Then** it executes with progress reporting.

3. **Given** the user cancels or requests reduced scope, **When** responded, **Then** the fetch is cancelled or adjusted accordingly.

---

### User Story 7 - Interactive Guided Analysis (Priority: P3)

A user wants to explore their data but isn't sure where to start or what questions to ask.

**Why this priority**: Provides an on-ramp for users unfamiliar with their data, though less critical than direct query tools.

**Independent Test**: Can be fully tested by starting an analysis session and being guided through focus selection, initial results, and drill-down choices.

**Acceptance Scenarios**:

1. **Given** a user starts guided analysis without a goal, **When** the session begins, **Then** the system prompts for focus area (conversion, retention, engagement, revenue) and time period.

2. **Given** initial analysis completes, **When** segments are identified, **Then** the user is prompted to select which segment to investigate further.

3. **Given** the user cancels mid-session, **When** responded, **Then** partial results are returned with clear indication of completion status.

---

### User Story 8 - Cohort Comparison Across Dimensions (Priority: P3)

An analyst wants to compare two user cohorts (e.g., premium vs free users) across multiple behavioral dimensions.

**Why this priority**: Cohort comparison is valuable but builds on simpler primitives and requires less frequent use.

**Independent Test**: Can be fully tested by defining two cohorts and receiving comparative analysis of event frequency, retention, and top events.

**Acceptance Scenarios**:

1. **Given** two cohort filter expressions, **When** comparison runs, **Then** the system returns side-by-side metrics for retention, event frequency, and top events.

2. **Given** comparison dimensions are specified, **When** run, **Then** only those dimensions are analyzed.

---

### User Story 9 - Long-Running Operations with Progress (Priority: P2)

A user initiates a large data fetch and wants visibility into progress and the ability to cancel if needed.

**Why this priority**: Progress reporting and cancellation are essential for user experience during operations that take minutes to complete.

**Independent Test**: Can be fully tested by starting a multi-day fetch and observing progress updates, then optionally cancelling mid-operation.

**Acceptance Scenarios**:

1. **Given** a fetch operation spanning multiple days, **When** it executes, **Then** progress updates are reported (e.g., "Fetching day 3 of 14: 45,000 events").

2. **Given** the user cancels mid-operation, **When** cancellation is requested, **Then** partial results are preserved with metadata about completion status.

3. **Given** a client that doesn't support tasks, **When** a task-enabled tool runs, **Then** it executes synchronously (blocking) without error.

---

### User Story 10 - Framework-Embedded Analysis Prompts (Priority: P3)

A user wants to apply proven analytics frameworks (GQM, AARRR, experiment analysis) to structure their investigation.

**Why this priority**: Prompts encode domain expertise and methodology, but are supplementary to the primary tools.

**Independent Test**: Can be fully tested by loading a framework prompt and receiving structured guidance for investigation.

**Acceptance Scenarios**:

1. **Given** a user requests the GQM decomposition prompt with a goal, **When** loaded, **Then** they receive structured guidance for breaking down the goal into questions and metrics.

2. **Given** a user requests the growth accounting prompt, **When** loaded, **Then** they receive AARRR framework guidance with benchmark comparisons.

3. **Given** a user requests the experiment analysis prompt with cohort details, **When** loaded, **Then** they receive statistical analysis framework guidance.

---

### User Story 11 - Dynamic Resource Templates (Priority: P3)

A user wants quick access to pre-computed analytics views like weekly retention or event trends without running full queries.

**Why this priority**: Resource templates provide convenience but are less critical than the core intelligent tools.

**Independent Test**: Can be fully tested by requesting a retention resource for a specific event and receiving pre-formatted retention data.

**Acceptance Scenarios**:

1. **Given** a user requests `analysis://retention/{event}/weekly`, **When** accessed, **Then** they receive 12-week retention curve data for that event.

2. **Given** a user requests `analysis://trends/{event}/{days}`, **When** accessed, **Then** they receive daily event counts for the specified period.

3. **Given** a user requests `users://{id}/journey`, **When** accessed, **Then** they receive the user's complete event journey with summary.

---

### Edge Cases

- What happens when Mixpanel API rate limits are exceeded? (System queues requests and reports wait time)
- How does the system handle events or properties that don't exist? (Graceful error with clear message)
- What if date ranges span periods with no data? (Return empty results with explanation, not error)
- How are malformed natural language queries handled? (Return parsing failure with suggestions for rephrasing)
- What if a composed tool partially fails? (Return partial results with clear indication of failures)

---

## Requirements _(mandatory)_

### Functional Requirements

#### Tier 3: Intelligent Tools (Sampling-Powered)

- **FR-001**: System MUST provide a `diagnose_metric_drop` tool that analyzes metric declines by comparing baseline periods, segmenting by dimensions, and synthesizing findings.
- **FR-002**: System MUST provide an `ask_mixpanel` tool that interprets natural language questions, generates execution plans, runs queries, and synthesizes answers.
- **FR-003**: System MUST provide a `funnel_optimization_report` tool that analyzes funnels, identifies bottlenecks, and generates recommendations.
- **FR-004**: Intelligent tools MUST gracefully degrade when sampling is unavailable, returning raw data with manual analysis hints.

#### Tier 2: Composed Tools

- **FR-005**: System MUST provide a `gqm_investigation` tool that decomposes goals into questions and metrics using the GQM framework.
- **FR-006**: System MUST provide a `product_health_dashboard` tool that computes all AARRR metrics in a single request.
- **FR-007**: System MUST provide a `cohort_comparison` tool that compares two user cohorts across behavioral dimensions.

#### Elicitation Workflows

- **FR-008**: System MUST provide a `safe_large_fetch` tool that estimates data volume and requests confirmation before large fetches.
- **FR-009**: System MUST provide a `guided_analysis` tool that interactively guides users through analysis with structured prompts.

#### Task-Enabled Operations

- **FR-010**: The `fetch_events` tool MUST support progress reporting with day-by-day updates for multi-day fetches.
- **FR-011**: The `fetch_profiles` tool MUST support progress reporting with page-by-page updates.
- **FR-012**: Composed tools that execute multiple queries MUST report progress for each query.
- **FR-013**: All task-enabled tools MUST support cancellation with partial result preservation.
- **FR-014**: Task-enabled tools MUST fall back to synchronous execution for clients that don't support tasks.

#### Enhanced Resources

- **FR-015**: System MUST provide dynamic resource templates for retention analysis (`analysis://retention/{event}/weekly`).
- **FR-016**: System MUST provide dynamic resource templates for trend analysis (`analysis://trends/{event}/{days}`).
- **FR-017**: System MUST provide user journey resources (`users://{id}/journey`).
- **FR-018**: System MUST provide recipe resources for reusable analysis patterns.

#### Framework Prompts

- **FR-019**: System MUST provide a GQM decomposition prompt that guides structured investigation.
- **FR-020**: System MUST provide a growth accounting (AARRR) prompt with industry benchmarks.
- **FR-021**: System MUST provide an experiment analysis prompt for A/B test evaluation.
- **FR-022**: System MUST provide a data quality audit prompt for implementation assessment.

#### Middleware Layer

- **FR-023**: System MUST implement caching middleware for expensive discovery operations with configurable TTL.
- **FR-024**: System MUST implement rate limiting middleware respecting Mixpanel's Query API limits (60/hour, 5 concurrent).
- **FR-025**: System MUST implement rate limiting middleware respecting Mixpanel's Export API limits (60/hour, 3/second, 100 concurrent).
- **FR-026**: System MUST implement audit logging middleware that records all tool invocations with timing and outcomes.
- **FR-027**: Middleware MUST use in-memory storage (no external dependencies).

#### Graceful Degradation

- **FR-028**: System MUST detect client sampling capability and adjust tool behavior accordingly.
- **FR-029**: When rate limited, system MUST report wait time and queue requests automatically.
- **FR-030**: All Tier 2 and Tier 3 tools MUST be available without feature flags.

### Key Entities

- **AnalysisResult**: Structured output from intelligent tools containing findings, recommendations, confidence level, and raw data.
- **ExecutionPlan**: Query plan generated from natural language, containing intent classification, query specifications, and reasoning.
- **ProgressUpdate**: Status report during long-running operations containing percentage, message, and cancellation status.
- **Middleware**: Request interceptor for caching, rate limiting, or logging with configurable behavior.

---

## Success Criteria _(mandatory)_

### Measurable Outcomes

- **SC-001**: Users can answer complex analytics questions (e.g., "Why did signups drop?") with a single tool invocation instead of 5+ manual queries.
- **SC-002**: Natural language queries successfully interpret user intent and return relevant results for 80% of common analytics questions.
- **SC-003**: Product health dashboard returns complete AARRR metrics in under 30 seconds for typical data volumes.
- **SC-004**: Long-running fetches (>1 minute) provide progress updates at least every 10 seconds.
- **SC-005**: Cancellation of in-progress operations completes within 2 seconds and preserves partial results.
- **SC-006**: Cache hit rate for discovery operations exceeds 50% during typical analysis sessions.
- **SC-007**: Rate limiting prevents 100% of Mixpanel API quota exhaustion errors during normal usage.
- **SC-008**: All intelligent tools return usable results (raw data with hints) when sampling is unavailable.
- **SC-009**: Guided analysis sessions reduce time-to-first-insight by 50% for new users compared to manual tool usage.
- **SC-010**: Framework prompts receive positive feedback (useful/very useful) from 70% of users who apply them.

---

## Assumptions

- FastMCP supports `ctx.sample()`, `ctx.elicit()`, `@mcp.tool(task=True)`, and middleware APIs as documented.
- Existing 27 primitive tools (Tier 1) remain unchanged and functional.
- The `mixpanel_data.Workspace` facade provides all necessary query capabilities.
- Client applications vary in their support for MCP sampling and task features.
- In-memory caching is sufficient for single-server deployments (no horizontal scaling requirement).
- Mixpanel API rate limits are as documented: Query API (60/hour, 5 concurrent), Export API (60/hour, 3/second, 100 concurrent).

---

## Dependencies

- FastMCP library with sampling, elicitation, task, and middleware support.
- Existing `mp_mcp` codebase with 27 primitive tools.
- `mixpanel_data` Python library for Workspace operations.
- Mixpanel API access with valid credentials.

---

## Out of Scope

- Redis or external storage for task persistence.
- Feature flags to toggle Tier 2/3 tools.
- Horizontal scaling or multi-instance coordination.
- Custom LLM configuration for sampling (uses client's default).
- Real-time streaming analytics (batch queries only).
