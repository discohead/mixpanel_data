# Research: Core Entity CRUD

**Phase**: 0 — Outline & Research
**Feature**: 024-core-entity-crud
**Date**: 2026-03-26

## Research Tasks

### R1: Existing App API Infrastructure

**Decision**: Use existing `app_request()` method on `MixpanelAPIClient` for all CRUD operations.

**Rationale**: The Phase 0 implementation (spec 023) already provides:
- `app_request()` method (api_client.py:664-703) — handles Bearer/Basic auth dispatch
- `set_workspace_id()` / `resolve_workspace_id()` — workspace scoping
- `paginate_all()` (pagination.py) — cursor-based pagination with rate limit handling
- `PublicWorkspace` and `CursorPagination` Pydantic models in types.py

**Alternatives considered**: Creating a separate `AppApiClient` class was rejected because `app_request()` already integrates with the existing auth and endpoint infrastructure.

### R2: Type Model Pattern for CRUD Entities

**Decision**: Use frozen Pydantic `BaseModel` with `ConfigDict(frozen=True, extra="allow")` for API response types; use non-frozen `BaseModel` for parameter/input types.

**Rationale**:
- Existing `PublicWorkspace` already uses `ConfigDict(frozen=True, extra="allow")` — the `extra="allow"` catches unknown fields from API evolution without breaking.
- Existing result types use frozen dataclasses with `ResultWithDataFrame` base, but CRUD response types don't need DataFrame conversion — they're entity objects, not analytical results.
- Param types (Create/Update) should NOT be frozen because users construct them mutably before passing to API methods.
- The Rust types use `#[serde(flatten)]` with `HashMap<String, Value>` for forward compatibility — Pydantic's `extra="allow"` achieves the same.

**Alternatives considered**:
- Frozen dataclasses (existing pattern for results) — rejected because Pydantic provides better JSON serialization, validation, and `model_dump(exclude_none=True)` for skip-if-none behavior.
- TypedDict — rejected because no validation, no serialization helpers.

### R3: Serde Attribute Mapping (Rust → Python)

**Decision**: Map Rust serde attributes to Pydantic field configuration:

| Rust Serde | Pydantic Equivalent |
|------------|-------------------|
| `#[serde(rename = "type")]` | `Field(alias="type")` + `model_config = ConfigDict(populate_by_name=True)` |
| `#[serde(default)]` | `field: type = default_value` or `field: Optional[type] = None` |
| `#[serde(skip_serializing_if = "Option::is_none")]` | `model_dump(exclude_none=True)` at serialization time |
| `#[serde(skip_serializing_if = "Vec::is_empty")]` | Custom serializer or `exclude_defaults=True` |
| `#[serde(with = "lenient_datetime")]` | `datetime | None = None` with Pydantic's built-in datetime parsing |
| `#[serde(flatten)]` | `model_config = ConfigDict(extra="allow")` for catch-all; explicit fields for known flattened structs |

**Rationale**: Pydantic v2 natively handles most serde patterns. The `exclude_none=True` on `model_dump()` replaces per-field skip-if-none.

### R4: CLI Command Pattern

**Decision**: Follow existing Typer command pattern with `@handle_errors` decorator and `output_result()` formatter.

**Rationale**: The existing CLI commands (auth.py, fetch.py, inspect.py, query.py) establish a consistent pattern:
1. Define Typer app: `app = typer.Typer(name="dashboards", help="...")`
2. Each subcommand is a decorated function
3. `get_workspace()` utility creates the Workspace instance
4. `output_result()` handles all 5 output formats
5. `@handle_errors` decorator provides consistent error handling

**Alternatives considered**: None — consistency with existing patterns is required.

### R5: Bulk Operation Pattern

**Decision**: Bulk operations accept lists and delegate to single API calls. Errors are returned as-is from the API (partial success is possible).

**Rationale**: The Rust implementation passes bulk IDs/entries directly to the API endpoint. The Mixpanel App API handles partial failures server-side. Client-side should not retry or split batches.

**Alternatives considered**: Client-side batch splitting with individual retries — rejected because the API supports bulk natively and partial failure semantics are server-defined.

### R6: Bookmark Type Enum

**Decision**: Define `BookmarkType` as a string enum (or Literal type) matching the Rust `BookmarkType` from `literal_types.rs`.

**Rationale**: The Rust codebase defines bookmark types as an enum. In Python, using `Literal["insights", "funnels", "flows", "retention", ...]` provides type safety at the library API level while remaining compatible with API strings.

**Alternatives considered**: Plain `str` — rejected because it loses type safety and IDE completion benefits.

### R7: Dashboard Blueprint Workflow

**Decision**: Implement blueprints as individual methods (list_templates, create, get_config, update_cohorts, finalize) rather than a single orchestrated workflow.

**Rationale**: Each step may require user decisions (choosing template, configuring cohorts). A monolithic method would violate Principle II (Agent-Native Design) by making assumptions about the workflow. Individual methods let the caller (human or agent) orchestrate.

**Alternatives considered**: Single `create_dashboard_from_blueprint()` convenience method — could be added later as a higher-level orchestration on top of the individual methods.

## All NEEDS CLARIFICATION: Resolved

No unresolved items. The feature builds entirely on established infrastructure and patterns.
