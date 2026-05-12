# Research: Operational Tooling — Alerts, Annotations, and Webhooks

**Branch**: `026-operational-tooling` | **Date**: 2026-03-31

## Research Questions & Findings

### RQ-1: What URL patterns do alerts, annotations, and webhooks use?

**Decision**: All three domains use `maybe_scoped_path()` (project-scoped, optionally workspace-scoped).

**Rationale**: The Rust reference implementation uses `maybe_scoped_path()` for all three domains, matching the pattern used by dashboards, reports, and cohorts. None of these domains use `require_scoped_path()` (which is reserved for feature flags and experiments that are always workspace-nested).

**Endpoint paths**:
- Alerts: `alerts/custom/`, `alerts/custom/{id}/`, `alerts/custom/bulk-delete/`, `alerts/custom/alert-count/`, `alerts/custom/{id}/history/`, `alerts/custom/test/`, `alerts/custom/screenshot/`, `alerts/custom/validate-alerts-for-bookmark/`
- Annotations: `annotations/`, `annotations/{id}/`, `annotations/tags/`, `annotations/tags/`
- Webhooks: `webhooks/`, `webhooks/{id}/`, `webhooks/test/`

**Alternatives considered**: `require_scoped_path()` — rejected because these domains are project-level, not workspace-nested.

### RQ-2: What are the special response patterns?

**Decision**: Three non-standard response patterns require special handling:

1. **Alert list** returns `list[dict]` directly (no envelope), consistent with dashboard list.
2. **Alert history** returns `{"results": [...], "pagination": {...}}` — a compound response that maps to `AlertHistoryResponse` model.
3. **Webhook create/update** returns `WebhookMutationResult` (`{id, name}`) rather than the full `ProjectWebhook` object. This is a different return type from dashboard/report CRUD which returns the full entity.

**Rationale**: These patterns are established by the Mixpanel App API and documented in the Rust reference.

**Alternatives considered**: Fetching the full entity after webhook create/update — rejected to avoid unnecessary API calls and to match Rust behavior.

### RQ-3: How should webhook passwords be handled securely?

**Decision**: Use regular `str | None` fields for `CreateWebhookParams`, `UpdateWebhookParams`, and `WebhookTestParams`. Do not use `SecretStr`.

**Rationale**: The Rust implementation uses plain `Option<String>` for webhook passwords. These values are only used in outbound API requests (write-only). The API never returns passwords in responses — the `ProjectWebhook` response model has no password field. Since the values are ephemeral (passed to the API and discarded), `SecretStr` protection adds complexity without security benefit. The existing pattern in `types.py` does not use `SecretStr` for any create/update params.

**Alternatives considered**: Pydantic `SecretStr` — rejected because passwords are write-only (never returned by API), so there's nothing to mask in repr/logging.

### RQ-4: What query parameter casing does the annotations endpoint use?

**Decision**: The annotations list endpoint uses `fromDate` and `toDate` (camelCase) as query parameters, while the Python method signature uses `from_date` and `to_date` (snake_case).

**Rationale**: The Rust reference explicitly maps these: query params are `fromDate`/`toDate` in the HTTP request. The API client method must translate from snake_case to camelCase when constructing the request params dict.

**Alternatives considered**: None — this is dictated by the Mixpanel API.

### RQ-4b: How does alert history pagination work on the initial request?

**Decision**: The initial alert history request should omit both `next_cursor` and `previous_cursor` parameters. The API returns the first page of results along with a `next_cursor` value in the pagination metadata. Subsequent requests pass `next_cursor` to retrieve the next page.

**Rationale**: This follows the standard cursor-based pagination pattern used across the Mixpanel App API. The Rust reference passes `Option<&str>` for both cursor params, meaning `None` is the default for the initial request.

### RQ-5: What ID type does each domain use?

**Decision**:
- Alerts: `int` (i64 in Rust)
- Annotations: `int` (i64 in Rust)
- Annotation tags: `int` (i64 in Rust)
- Webhooks: `str` (String in Rust — UUIDs)

**Rationale**: Matches the Rust reference. Webhook IDs are strings (UUIDs) while alert and annotation IDs are integers. This affects CLI argument types and Pydantic model field types.

### RQ-6: What does the alert `test` endpoint accept?

**Decision**: The test endpoint accepts `CreateAlertParams` (same params as create) and returns opaque `Value` (JSON). It evaluates the alert configuration without persisting it.

**Rationale**: The Rust reference uses `CreateAlertParams` for the test endpoint. The test action is essentially a "dry run" of alert creation.

### RQ-7: How should the annotation tags subcommand be structured in the CLI?

**Decision**: Use a nested Typer sub-app: `mp annotations tags list` and `mp annotations tags create --name <NAME>`.

**Rationale**: Matches the Rust CLI structure which has a `tags` subcommand group under `annotations`. This keeps tag operations namespaced under their parent domain.

**Alternatives considered**: Flat commands like `mp annotations list-tags` — rejected for consistency with Rust CLI and cleaner command organization.

### RQ-8: What validation does the Rust implementation perform?

**Decision**: The Rust implementation validates:
- Alert names (non-empty, reasonable length)
- Annotation dates (ISO format validation)
- Webhook URLs (valid URL format)
- Webhook names (non-empty)

The Python implementation should perform equivalent validation in the Workspace layer before calling the API client, raising `ValueError` for invalid inputs. This matches the existing pattern where Workspace methods validate before delegating.

**Alternatives considered**: Server-side only validation — rejected because early validation provides better error messages and follows existing Python patterns.
