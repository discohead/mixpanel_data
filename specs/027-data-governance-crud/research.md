# Research: Data Governance CRUD

**Feature**: 027-data-governance-crud | **Date**: 2026-04-01

## R1: Existing Codebase Patterns

### Decision: Follow established CRUD patterns exactly
**Rationale**: The project has 6+ CRUD domains already implemented (dashboards, bookmarks, cohorts, alerts, annotations, webhooks) with consistent patterns across all layers. Following these patterns ensures consistency and reduces cognitive load.

**Alternatives considered**:
- Creating a generic CRUD base class — rejected because the existing pattern is simple and explicit
- Using a decorator-based approach — rejected because it would add abstraction without benefit

### Key Patterns Identified

**File sizes (current)**:
- `workspace.py`: 5,171 lines
- `api_client.py`: 5,045 lines
- `types.py`: 6,176 lines

**Workspace method pattern**:
```python
def create_{entity}(self, params: Create{Entity}Params) -> {Entity}:
    client = self._require_api_client()
    body = params.model_dump(exclude_none=True)
    raw = client.create_{entity}(body)
    return {Entity}.model_validate(raw)
```

**API client method pattern**:
```python
def create_{entity}(self, body: dict[str, Any]) -> dict[str, Any]:
    path = self.maybe_scoped_path("{endpoint}/")
    result = self.app_request("POST", path, json_body=body)
    if not isinstance(result, (dict, list)):
        raise MixpanelDataError(...)
    return result
```

**CLI command pattern**:
```python
@{domain}_app.command("create")
@handle_errors
def {domain}_create(ctx: typer.Context, ..., format: FormatOption = "json", jq_filter: JqOption = None) -> None:
    workspace = get_workspace(ctx)
    params = Create{Entity}Params(...)
    with status_spinner(ctx, "Creating..."):
        result = workspace.create_{entity}(params)
    output_result(ctx, result.model_dump(), format=format, jq_filter=jq_filter)
```

## R2: Rust Reference Type Mapping

### Decision: Map Rust types to Python Pydantic models with camelCase aliasing
**Rationale**: The Mixpanel App API uses camelCase in JSON responses. Rust handles this with `#[serde(rename_all = "camelCase")]`. Python will use Pydantic's `alias` or `alias_generator` to match.

**Key mapping decisions**:
- Rust `HashMap<String, Value>` extra fields → Pydantic `extra="allow"` on ConfigDict
- Rust `Option<T>` → Python `T | None = None`
- Rust enums with Unknown variant → Python `Literal` types or string enums
- Rust `deserialize_string_or_int` → Pydantic validator

## R3: API Endpoint Patterns

### Decision: Use `maybe_scoped_path()` for all data governance endpoints
**Rationale**: All data governance endpoints (data-definitions, custom_properties) use project-level scoping with optional workspace scoping, matching the `maybe_scoped_path()` pattern used by dashboards, alerts, annotations, etc.

### Special Endpoint Patterns

**Tag deletion uses POST (not DELETE)**:
```
POST /data-definitions/tags/ with body {"delete": true, "name": "tag-name"}
```

**Drop filter mutations return the full list**:
- POST/PATCH/DELETE on drop-filters/ all return `Vec<DropFilter>` (the complete list after mutation)

**Lookup table registration uses form-encoded POST (not JSON)**:
```
POST /data-definitions/lookup-tables/
Content-Type: application/x-www-form-urlencoded
Body: name={name}&path={gcs_path}&key={column_name}
```

**Custom property update uses PUT (not PATCH)**:
- Full replacement semantics — must send all mutable fields

**Custom property validation endpoint**:
```
POST /custom_properties/validate/
```
Same body as create, but returns validation result without creating.

## R4: Lookup Table Upload Flow

### Decision: Implement 3-step upload with optional async polling
**Rationale**: The Mixpanel API uses signed GCS URLs for upload. The flow is:

1. **GET upload-url**: Returns `{url, path, key}` — signed GCS URL
2. **PUT to GCS**: Upload raw CSV bytes to signed URL (no Mixpanel auth)
3. **POST register**: Form-encoded registration with `{name, path, key, data-group-id?}`
   - Returns `{id: N}` (sync) or `{uploadId: "xyz"}` (async)
   - If async: poll `upload-status?upload-id=xyz` until SUCCESS/FAILURE

**Polling parameters** (from Rust): max 60 attempts, 5-second intervals.

## R5: Test Patterns

### Decision: Follow the 3-layer test pattern (types, api_client, workspace) + CLI tests
**Rationale**: Every existing CRUD domain has:
- `test_types_{domain}.py` — Pydantic model tests (frozen, extra fields, serialization)
- `test_api_client_{domain}.py` — HTTP mock tests (URL construction, request bodies)
- `test_workspace_{domain}.py` — Integration tests (end-to-end with mocked transport)
- CLI tests in `tests/unit/cli/`

**Mock pattern**: `httpx.MockTransport` with handler functions that capture requests and return canned responses.

## R6: types.py Size Decision

### Decision: Keep types in `types.py` (already at 6,176 lines, ~25 new models will add ~1,000-1,500 lines)
**Rationale**: The constitution's package structure specifies `types.py` as the location. The file is already large but well-organized with clear section headers. Adding ~25 models brings it to ~7,500 lines which is manageable. A split to `types/` package is deferred per architectural decision #5 from the gap analysis.

**Alternative considered**: Split now into `types/` package — rejected because it would be a refactoring task that changes imports across the entire codebase, better done as a separate PR.
