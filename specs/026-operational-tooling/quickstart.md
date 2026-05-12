# Quickstart: Operational Tooling — Alerts, Annotations, and Webhooks

**Branch**: `026-operational-tooling` | **Date**: 2026-03-31

## Implementation Order

The three domains are independent and can be implemented in any order. Recommended order by complexity (simplest first):

1. **Annotations** (7 methods, 6 models) — simplest data model, establishes pattern
2. **Webhooks** (5 methods, 7 models) — small but introduces `str` ID and mutation result pattern
3. **Alerts** (11 methods, 13 models) — most complex, largest model set, pagination

## Per-Domain Implementation Checklist

For each domain, implement in this order (matches TDD workflow):

### Step 1: Types (`src/mixpanel_data/types.py`)

Add Pydantic models. Follow existing patterns:
- Response models: `ConfigDict(frozen=True, extra="allow")`
- Request params: plain `BaseModel`
- Write unit tests in `tests/test_types_{domain}.py`

### Step 2: API Client (`src/mixpanel_data/_internal/api_client.py`)

Add HTTP methods. Follow existing patterns:
- Use `self.maybe_scoped_path(...)` for URL construction
- Use `self.app_request(METHOD, path, ...)` for HTTP
- Validate response types (`isinstance(result, dict/list)`)
- Write tests in `tests/test_api_client_{domain}.py` using `respx`

### Step 3: Workspace (`src/mixpanel_data/workspace.py`)

Add facade methods. Follow existing patterns:
- `client = self._require_api_client()`
- Convert params: `params.model_dump(exclude_none=True)`
- Validate response: `Model.model_validate(raw)`
- Write tests in `tests/test_workspace_{domain}.py`

### Step 4: CLI (`src/mixpanel_data/cli/commands/{domain}.py`)

Add Typer commands. Follow existing patterns:
- Create `{domain}_app = typer.Typer(...)`
- Use `@handle_errors` decorator on all commands
- Use `get_workspace(ctx)` + `status_spinner(ctx, ...)` + `output_result(ctx, ...)`
- Register in `cli/main.py`
- Write tests in `tests/integration/cli/test_{domain}_commands.py`

## Key Patterns Reference

```python
# API Client pattern
def list_{entities}(self, ...) -> list[dict[str, Any]]:
    path = self.maybe_scoped_path("{entities}/")
    result = self.app_request("GET", path, params=...)
    if not isinstance(result, list):
        raise MixpanelDataError(...)
    return result

# Workspace pattern
def list_{entities}(self, ...) -> list[{Entity}]:
    client = self._require_api_client()
    raw = client.list_{entities}(...)
    return [{Entity}.model_validate(d) for d in raw]

# CLI pattern
@{domain}_app.command("list")
@handle_errors
def {domain}_list(ctx: typer.Context, format: FormatOption = "json", jq_filter: JqOption = None) -> None:
    workspace = get_workspace(ctx)
    with status_spinner(ctx, "Fetching..."):
        result = workspace.list_{entities}()
    output_result(ctx, [d.model_dump() for d in result], format=format, jq_filter=jq_filter)
```

## Special Cases

1. **Annotations list**: Query params use camelCase (`fromDate`, `toDate`) — translate in API client
2. **Webhook IDs**: String type (UUIDs), not int
3. **Webhook create/update**: Returns `WebhookMutationResult` (id + name), not full entity
4. **Alert history**: Returns compound `AlertHistoryResponse` with embedded pagination
5. **Alert test**: Reuses `CreateAlertParams` — returns opaque dict
6. **Annotation tags**: Nested Typer sub-app under annotations
