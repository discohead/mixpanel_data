# Research: Schema Registry & Data Governance

**Feature**: 028-schema-governance | **Date**: 2026-04-02

## Research Summary

All technical questions resolved. No NEEDS CLARIFICATION items remain. Research drew from three sources:
1. **Python codebase** — existing patterns, types, API client, workspace, CLI
2. **Rust reference** — target API surface, type definitions, endpoint paths
3. **Django reference** — canonical API implementation, request/response schemas, validation rules, permissions

---

## Decision 1: Schema Registry Type Modeling

**Decision**: Use Pydantic `BaseModel` with `ConfigDict(frozen=True, extra="allow")` for response types; plain `BaseModel` for parameter types. Use `dict[str, Any]` (JSON Value equivalent) for `schema_json` fields.

**Rationale**: Matches existing patterns in types.py (Dashboard, Bookmark, Alert, etc.). The `extra="allow"` catch-all preserves forward compatibility when Mixpanel adds new fields. Schema JSON is inherently unstructured (JSON Schema Draft 7), so `dict[str, Any]` is the correct Python equivalent of Rust's `serde_json::Value`.

**Alternatives considered**:
- Frozen dataclasses (used for older types like `LexiconSchema`) — rejected because newer types consistently use Pydantic BaseModel
- Strict schema_json typing — rejected because JSON Schema is arbitrarily nested

---

## Decision 2: Schema Registry vs Existing LexiconSchema

**Decision**: New schema registry types (`SchemaEntry`, `BulkCreateSchemasParams`, etc.) are separate from the existing `LexiconSchema` dataclass. The existing `lexicon_schemas()`/`lexicon_schema()` read methods (which go through DiscoveryService) remain unchanged.

**Rationale**: The existing `LexiconSchema` is a discovery-oriented read model used by `DiscoveryService.list_schemas()`. The new schema registry CRUD operates on different endpoints (`/schemas/` vs what discovery uses) with different request/response shapes. Keeping them separate avoids breaking existing code.

**Alternatives considered**:
- Unifying into one type — rejected because the read model (LexiconSchema) has a different structure than the CRUD model (SchemaEntry), and the endpoints are different

---

## Decision 3: Enforcement Config Response Handling

**Decision**: Return `dict[str, Any]` from enforcement init/update/replace/delete operations (matching Rust's `Result<Value>`). Return typed `SchemaEnforcementConfig` from get.

**Rationale**: The enforcement mutation endpoints return raw JSON responses that vary by operation type. Only the GET endpoint has a well-defined schema worth typing. This matches the Rust implementation's pattern of `Result<Value>` for mutations vs `Result<SchemaEnforcementConfig>` for get.

**Alternatives considered**:
- Fully typed responses for all operations — rejected because the API response shape for mutations is not well-defined and varies

---

## Decision 4: Audit Response Parsing

**Decision**: The audit API returns a 2-element array: `results[0]` contains violations, `results[1]` contains metadata with `computed_at`. Parse this into an `AuditResponse` with `violations: list[AuditViolation]` and `computed_at: str`. Use `_raw=True` on `app_request()` to bypass automatic `results` unwrapping, then manually parse the tuple.

**Rationale**: The standard `app_request()` unwraps `results` automatically, but the audit endpoint returns a tuple (array), not a dict. The `_raw=True` flag (already supported) lets us handle this special case. This matches the Rust implementation's manual parsing.

**Alternatives considered**:
- Adding a special case in `app_request()` — rejected because it would add complexity for a single endpoint

---

## Decision 5: Anomaly List Query Parameters

**Decision**: Accept query parameters as `dict[str, str] | None` for `list_data_volume_anomalies()`, matching the Rust pattern of `Option<&[(&str, &str)]>`. Supported filters include `status`, `limit`, `event_id`, `prop_id`, `include_property_anomalies`, `include_metric_anomalies`.

**Rationale**: The Django reference shows multiple optional query parameters. Using a dict provides flexibility without requiring a dedicated params type for read-only filtering.

**Alternatives considered**:
- Named keyword arguments for each filter — rejected because the filter set may expand and this adds API surface without proportional value
- A typed Pydantic params model — rejected as over-engineering for query filters

---

## Decision 6: Deletion Request Lifecycle

**Decision**: Create/cancel operations return the updated full list of deletion requests (`list[EventDeletionRequest]`), matching the Rust implementation and Django behavior.

**Rationale**: The Django API returns the complete list after mutations so clients don't need a separate list call to see current state. This is the canonical behavior.

**Alternatives considered**:
- Returning only the created/cancelled request — rejected because the API doesn't work that way

---

## Decision 7: CLI Command Structure

**Decision**:
- **New file**: `cli/commands/schemas.py` with `schemas_app` Typer group containing: `list`, `create`, `create-bulk`, `update`, `update-bulk`, `delete`
- **Modified file**: `cli/commands/lexicon.py` — add 4 new nested Typer sub-apps:
  - `enforcement_app` (get, init, update, replace, delete)
  - `audit` command (with `--events-only` flag)
  - `anomalies_app` (list, update, bulk-update)
  - `deletion_requests_app` (list, create, cancel, preview)

**Rationale**: Matches the Rust CLI structure. Schema registry is a top-level command group (like dashboards, reports). Enforcement/audit/anomalies/deletion-requests are Lexicon subgroups (they operate on data definitions). Using `--events-only` flag on audit (rather than separate subcommand) simplifies the CLI surface.

**Alternatives considered**:
- Separate `audit` command group — rejected because auditing is part of data definitions/Lexicon
- `governance` top-level group — rejected because it would diverge from the Rust CLI structure

---

## Decision 8: URL Path Encoding

**Decision**: Use `urllib.parse.quote(segment, safe="")` for entity type and entity name path segments in schema CRUD operations. This provides the same UTF-8 percent encoding as Rust's `utf8_percent_encode(segment, NON_ALPHANUMERIC)`.

**Rationale**: Event and property names can contain special characters (spaces, colons, etc.) that must be encoded in URL path segments. The Django reference validates names but doesn't sanitize them in URLs, so the client must encode.

**Alternatives considered**:
- No encoding (relying on httpx) — rejected because httpx doesn't percent-encode path segments by default
- Custom encoding function — rejected because `urllib.parse.quote` with `safe=""` is equivalent

---

## Decision 9: Workspace Scoping Pattern

**Decision**: All schema registry and governance endpoints use `maybe_scoped_path()` (optional workspace scoping), not `require_scoped_path()`.

**Rationale**: Confirmed by both Rust reference and Django auth decorators. These endpoints use `@require_workspace_membership(is_api=True)` but don't require workspace ID in the URL path (unlike feature flags which use `require_scoped_path()`). The `maybe_scoped_path()` method is already implemented in the Python API client.

**Alternatives considered**:
- `require_scoped_path()` — incorrect; only feature flags and experiments use the project-nested URL pattern

---

## Decision 10: Permissions and Authorization

**Decision**: The library does not perform client-side permission checks. The API enforces permissions server-side. Document required permissions in docstrings for user reference.

**Rationale**: The Django reference shows extensive permission decorators (`write_data_definitions`, `write_data_definition_schema`, `event_deletion`, `manage_data_volume_monitoring`, etc.), but these are enforced server-side. Duplicating them client-side would be fragile and would diverge when permissions change. The API returns clear 403 errors with descriptive messages.

**Key permissions** (for documentation only):
- Schema registry write: `write_data_definitions`
- Schema enforcement write: `write_data_definition_schema`
- Event deletion: `event_deletion`
- Anomaly management: `manage_data_volume_monitoring`

---

## Rate Limiting Reference

From Django source, confirmed rate limits:
- Schema writes: **5/minute** per organization
- Properties/entities: **4000/minute** per organization, **12000/minute** global
- Truncate deletions: **3000 max entities** per request, **9000/minute** global
- Event deletions: **10 requests/month** (unless bypassed), **5 billion events/month** max
- Deletion time window: max **180 days** in the past

The existing `app_request()` already handles 429 responses with retry logic, so no new rate limit handling is needed.
