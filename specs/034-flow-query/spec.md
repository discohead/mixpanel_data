# Feature Specification: Typed Flow Query API

**Feature Branch**: `034-flow-query`  
**Created**: 2026-04-06  
**Status**: Draft  
**Input**: Phase 4 of Unified Bookmark Query System — add `query_flow()`, `build_flow_params()`, typed `FlowStep`/`FlowQueryResult` types, two-layer validation, segfilter converter, inline POST to `/arb_funnels`, and graph-based result representation with NetworkX.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Simple Ad-Hoc Flow Query (Priority: P1)

A library consumer wants to discover what users do after a key event without creating a saved report in the Mixpanel UI. They call `query_flow("Purchase", forward=3)` and receive a typed result with graph data showing the most common paths users take after purchasing.

**Why this priority**: This is the core value proposition — programmatic ad-hoc flow queries that bypass the UI. Without this, users must create saved reports in Mixpanel first and query them by bookmark_id.

**Independent Test**: Can be fully tested by building flow params with `build_flow_params()` and verifying the generated bookmark JSON matches the canonical Mixpanel format. API execution can be tested with mocked responses.

**Acceptance Scenarios**:

1. **Given** a Workspace with valid credentials, **When** the user calls `ws.query_flow("Purchase", forward=3)`, **Then** the system builds valid flat bookmark params, POSTs them to the flows endpoint, and returns a `FlowQueryResult` with step/node/edge data.
2. **Given** a Workspace with valid credentials, **When** the user calls `ws.query_flow("Signup", forward=2, reverse=1)`, **Then** the result contains both forward and reverse path data from the anchor event.
3. **Given** a Workspace with valid credentials, **When** the user calls `ws.build_flow_params("Purchase", forward=3)`, **Then** the system returns a dict of valid bookmark params without executing a query, suitable for inspection or persistence via `create_bookmark()`.

---

### User Story 2 - Flow Query with Per-Step Filters and Configuration (Priority: P1)

A library consumer wants to analyze flows with specific constraints — per-step filters (e.g., only purchases over $50), conversion windows, counting methods, and hidden events. They use `FlowStep` objects and keyword arguments for fine-grained control.

**Why this priority**: Per-step filters and configuration options are essential for meaningful flow analysis. Without them, users can only query raw unfiltered flows which are rarely actionable.

**Independent Test**: Can be tested by constructing `FlowStep` objects with filters, calling `build_flow_params()`, and verifying the generated bookmark contains correctly formatted segfilter entries for each step.

**Acceptance Scenarios**:

1. **Given** a `FlowStep` with per-step filters, **When** the user calls `ws.query_flow(FlowStep("Purchase", forward=3, filters=[Filter.greater_than("amount", 50)]))`, **Then** the generated bookmark contains the filter converted to legacy segfilter format in `property_filter_params_list`.
2. **Given** configuration options, **When** the user calls `ws.query_flow("Checkout", forward=5, conversion_window=14, count_type="unique", collapse_repeated=True)`, **Then** the generated bookmark includes `conversion_window`, `count_type`, and `collapse_repeated` fields at the top level.
3. **Given** hidden events, **When** the user calls `ws.query_flow("Login", forward=3, hidden_events=["Page View", "Session Start"])`, **Then** the generated bookmark includes the hidden events list and the API response excludes those events from the flow.

---

### User Story 3 - Graph-Based Flow Result Analysis (Priority: P1)

A library consumer wants to analyze the flow results as a graph — finding paths between events, identifying bottlenecks, and computing drop-off rates. The `FlowQueryResult` provides a NetworkX DiGraph alongside structured DataFrames for both graph traversal and tabular analysis.

**Why this priority**: The flow response data is inherently a directed acyclic graph. Without graph representation, users must manually implement BFS/DFS to answer basic questions like "what paths lead from Login to Purchase?" The existing `FlowsResult.df` (which simply dumps raw steps into a DataFrame) is not useful.

**Independent Test**: Can be tested by constructing a `FlowQueryResult` from sample API response data and verifying that `nodes_df`, `edges_df`, and `graph` properties produce correct, well-structured outputs.

**Acceptance Scenarios**:

1. **Given** a `FlowQueryResult` from a sankey query, **When** the user accesses `.nodes_df`, **Then** they receive a DataFrame with columns `step`, `event`, `type`, `count`, `anchor_type`, `is_custom_event`, `conversion_rate_change` — one row per node.
2. **Given** a `FlowQueryResult` from a sankey query, **When** the user accesses `.edges_df`, **Then** they receive a DataFrame with columns `source_step`, `source_event`, `target_step`, `target_event`, `count`, `target_type` — one row per edge.
3. **Given** a `FlowQueryResult` from a sankey query, **When** the user accesses `.graph`, **Then** they receive a NetworkX DiGraph where nodes are keyed as `"{event}@{step}"`, node attributes include `count`, `type`, `step`, and edge attributes include `count`. The graph is lazily built on first access and cached.
4. **Given** a `FlowQueryResult` from a top-paths query, **When** the user accesses `.df`, **Then** they receive a DataFrame with flow path data — one row per path with step-level columns.

---

### User Story 4 - Multi-Step Anchor Flow Query (Priority: P2)

A library consumer wants to define multiple anchor events in a single flow to see how users navigate between key waypoints. They pass a list of `FlowStep` objects, each with independent forward/reverse counts.

**Why this priority**: Multi-anchor flows are a power feature that enables journey mapping across multiple touchpoints. Most users will start with single-anchor flows (P1), but multi-anchor is important for advanced analysis.

**Independent Test**: Can be tested by passing a list of `FlowStep` objects to `build_flow_params()` and verifying each step appears in the bookmark's `steps` array with correct per-step forward/reverse values.

**Acceptance Scenarios**:

1. **Given** multiple FlowStep objects, **When** the user calls `ws.query_flow([FlowStep("Signup", forward=3, reverse=0), FlowStep("Purchase", forward=0, reverse=3)])`, **Then** the bookmark contains two entries in the `steps` array, each with its own forward/reverse counts.
2. **Given** a mix of string and FlowStep inputs, **When** the user calls `ws.query_flow(["Login", FlowStep("Purchase", forward=2)])`, **Then** string events are normalized to FlowStep objects using the top-level `forward`/`reverse` defaults.

---

### User Story 5 - Fail-Fast Validation with Actionable Errors (Priority: P2)

A library consumer makes a mistake in their flow query — invalid forward/reverse range, empty event name, or invalid count type. The system catches these errors before any API call and returns structured error messages with suggestions.

**Why this priority**: Fail-fast validation prevents wasted API calls and provides a better developer experience. This pattern is already established for insights, funnels, and retention queries.

**Independent Test**: Can be tested by calling `build_flow_params()` with invalid arguments and verifying that `BookmarkValidationError` is raised with the correct error codes, messages, and fuzzy-matched suggestions.

**Acceptance Scenarios**:

1. **Given** an empty event list, **When** the user calls `ws.query_flow([])`, **Then** a `BookmarkValidationError` is raised with code `FL1` and message indicating at least one event is required.
2. **Given** `forward=6` (out of range 0-5), **When** the user calls `ws.query_flow("Login", forward=6)`, **Then** a `BookmarkValidationError` is raised with code `FL3`.
3. **Given** `forward=0, reverse=0`, **When** the user calls `ws.query_flow(FlowStep("Login", forward=0, reverse=0))`, **Then** a `BookmarkValidationError` is raised with code `FL5` indicating at least one direction must be nonzero.
4. **Given** `count_type="invalid"`, **When** the user calls `ws.query_flow("Login", count_type="invalid")`, **Then** a `BookmarkValidationError` is raised with fuzzy-matched suggestions for valid count types.

---

### User Story 6 - Rename Existing Saved-Report Flow Method (Priority: P2)

A library consumer currently uses `ws.query_flows(bookmark_id=123)` to query saved flows reports. This method is renamed to `ws.query_saved_flows()` to avoid confusion with the new `query_flow()` method that builds params inline.

**Why this priority**: Naming clarity is important for discoverability. The old method queries pre-saved reports; the new method builds and executes queries programmatically. They serve different purposes and need distinct names.

**Independent Test**: Can be tested by verifying that `query_saved_flows()` still works identically to the old `query_flows()` — same arguments, same return type, same behavior.

**Acceptance Scenarios**:

1. **Given** a saved flows report with bookmark_id, **When** the user calls `ws.query_saved_flows(bookmark_id=123)`, **Then** the system retrieves and returns the saved report as a `FlowsResult` (unchanged behavior).
2. **Given** code that previously called `ws.query_flows(bookmark_id=123)`, **When** the method is renamed, **Then** the old name is no longer available and users must update to the new name.

---

### User Story 7 - Flow Result Convenience Methods (Priority: P3)

A library consumer wants quick answers without graph API knowledge — top transitions, drop-off summary, or path listing. The `FlowQueryResult` provides convenience methods that wrap common graph operations.

**Why this priority**: These are quality-of-life improvements that make the API more accessible to users who don't know NetworkX. The core graph and DataFrame properties (P1) already enable all these analyses manually.

**Independent Test**: Can be tested by constructing a `FlowQueryResult` from sample data and verifying that convenience methods return correctly structured results.

**Acceptance Scenarios**:

1. **Given** a `FlowQueryResult`, **When** the user calls `.top_transitions(n=5)`, **Then** they receive the 5 highest-traffic (source_event, target_event, count) transitions.
2. **Given** a `FlowQueryResult`, **When** the user calls `.drop_off_summary()`, **Then** they receive per-step drop-off counts and percentages.

---

### Edge Cases

- What happens when a flow query returns zero nodes (empty result)? The `FlowQueryResult` returns empty DataFrames and an empty DiGraph.
- How does the system handle the same event appearing at multiple step positions? Nodes are keyed as `"{event}@{step}"` to disambiguate (e.g., `"Login@0"` vs `"Login@2"`).
- What happens when a flow step has `forward=0` and `reverse=0`? Validation rule FL5 catches this before any API call.
- How does the system handle extremely large cardinality values? Validation rule FL6 caps cardinality at 1-50.
- What happens when per-step filters use operators not supported by segfilter format? The converter handles the full set of Filter operators that the library supports, mapping each to its segfilter equivalent.
- How does the system behave when the API returns a top-paths response but the user expected sankey? The `mode` parameter controls `query_type` and `flows_merge_type`; the result type handles both response shapes.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST provide a `query_flow()` method on `Workspace` that accepts typed arguments (event names, FlowStep objects, forward/reverse counts, filters, conversion window, count type, cardinality, mode) and returns a `FlowQueryResult`.
- **FR-002**: System MUST provide a `build_flow_params()` method on `Workspace` that generates the flat bookmark params dict without executing a query, enabling inspection, debugging, and persistence via `create_bookmark()`.
- **FR-003**: System MUST provide a `FlowStep` frozen dataclass with fields: `event` (str), `forward` (int or None), `reverse` (int or None), `label` (str or None), `filters` (list of Filter or None), `filters_combinator` ("all" or "any").
- **FR-004**: System MUST provide a `FlowQueryResult` frozen dataclass with: `computed_at`, `steps` (raw), `breakdowns` (raw), `overall_conversion_rate`, `params` (generated bookmark), `meta`, and lazy-cached `nodes_df`, `edges_df`, `graph` (NetworkX DiGraph), and `df` properties.
- **FR-005**: System MUST convert `Filter` objects to legacy segfilter format via a converter function for per-step filters in flow bookmarks, mapping bookmark-style operators to symbolic operators, stringifying numeric values, and converting date formats.
- **FR-006**: System MUST validate flow arguments in two layers: Layer 1 validates arguments before bookmark construction (rules FL1-FL8); Layer 2 validates the generated flat bookmark structure after construction.
- **FR-007**: System MUST provide an API client method that POSTs inline bookmark params to the `/arb_funnels` endpoint with `query_type` set to `"flows_sankey"` or `"flows_top_paths"` based on the mode parameter.
- **FR-008**: System MUST rename the existing `query_flows(bookmark_id)` method to `query_saved_flows(bookmark_id)` across all layers (Workspace, service, API client) to distinguish saved-report queries from inline ad-hoc queries.
- **FR-009**: System MUST normalize string event inputs to `FlowStep` objects, applying top-level `forward`/`reverse` defaults to steps that don't specify their own.
- **FR-010**: System MUST support both single events (string or FlowStep) and sequences of events as input to `query_flow()`.
- **FR-011**: System MUST generate flat (non-sections-wrapped) bookmark JSON for flows, including `steps`, `date_range`, `chartType`, `flows_merge_type`, `count_type`, `cardinality_threshold`, `version`, `conversion_window`, `anchor_position`, `collapse_repeated`, `show_custom_events`, `hidden_events`, and `exclusions` at the top level.
- **FR-012**: System MUST add a graph analysis library as a project dependency for graph-based flow result representation.
- **FR-013**: System MUST export all new public types (`FlowStep`, `FlowQueryResult`) from the package's public API.
- **FR-014**: System MUST handle both sankey and top-paths response structures within `FlowQueryResult`, providing mode-appropriate data access.

### Key Entities

- **FlowStep**: An anchor event in a flow query with per-step forward/reverse counts, optional label, optional per-step filters, and filter combinator. Simple string event names are normalized to FlowStep objects.
- **FlowQueryResult**: The result of an ad-hoc flow query containing raw step/breakdown data, generated params, and lazy-cached graph/DataFrame views. Represents either a sankey graph or a list of top paths depending on query mode.
- **Segfilter**: The legacy filter format used by flows steps, structurally different from bookmark filters — symbolic operators, nested property objects, stringified operands. Internal only; users interact via Filter objects.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Users can execute a flow query with a single method call and receive typed results, without needing to create a saved report in the Mixpanel UI first.
- **SC-002**: Generated flow bookmark params produce correct results from the Mixpanel API for all supported configurations (single/multi-step, filters, conversion windows, count types, modes).
- **SC-003**: Invalid flow query arguments are caught before any API call with structured error messages including error codes and suggestions for misspelled values.
- **SC-004**: Flow results provide a graph representation that supports standard graph operations (path finding, traversal, node/edge queries) on the flow data.
- **SC-005**: Flow results provide structured DataFrames (`nodes_df`, `edges_df`) that expose all node and edge data from the API response in a tabular format usable for filtering and aggregation.
- **SC-006**: Per-step filter objects are correctly converted to legacy segfilter format, producing bookmark params that the Mixpanel API accepts and processes correctly.
- **SC-007**: All new code achieves 90%+ test coverage with unit tests, property-based tests, and mutation testing (80%+ kill rate).

## Assumptions

- The Mixpanel `/arb_funnels` endpoint accepts inline `bookmark` dicts in POST body (confirmed via source code analysis of the canonical implementation).
- The segfilter format used by flows is stable and matches the canonical reference implementation.
- The graph analysis dependency is compatible with all supported Python versions (3.10+) and has no transitive dependencies.
- Flows `group_by` is intentionally excluded from v1 scope — users needing segmented flows can use `create_bookmark()` + `query_saved_flows()`.
- The existing `FlowsResult` type (for saved-report queries) remains unchanged; `FlowQueryResult` is a new, separate type for ad-hoc queries.
- The flat date range builder already extracted in Phase 1 shared infrastructure is used for flows date range construction.
- The `version: 2` field in flows bookmark params is the current and correct version for the flows API.
