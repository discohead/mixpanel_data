# Research: Feature Management (Flags + Experiments)

**Branch**: `025-feature-management` | **Date**: 2026-03-31

## Research Questions & Decisions

### R1: Feature flag URL scoping pattern

**Decision**: Feature flags use `require_scoped_path("feature-flags")` — always workspace-scoped.

**Rationale**: The Rust reference uses `require_scoped_path()` for all feature flag endpoints, producing paths like `/projects/{pid}/workspaces/{wid}/feature-flags/`. This differs from dashboards/bookmarks/cohorts which use `maybe_scoped_path()`. The Python `require_scoped_path()` method already exists in `api_client.py:935` and auto-discovers workspace ID if not set.

**Alternatives considered**: Using `maybe_scoped_path()` — rejected because the Mixpanel API requires workspace scoping for feature flags (the endpoint doesn't work without it).

### R2: Experiment URL scoping pattern

**Decision**: Experiments use `maybe_scoped_path("experiments")` — optionally workspace-scoped.

**Rationale**: The Rust reference uses `maybe_scoped_path()` for all experiment endpoints. Experiments work both with and without workspace scoping, similar to dashboards.

**Alternatives considered**: None — the Rust reference is clear.

### R3: Feature flag update semantics (PUT vs PATCH)

**Decision**: Feature flag update uses PUT (full replacement), unlike other domains that use PATCH.

**Rationale**: The Rust reference uses `Method::PUT` for `update_feature_flag()` (api_client.rs line 1559). The `UpdateFeatureFlagParams` has required fields (`name`, `key`, `status`, `ruleset`) — not all-optional like PATCH params. This means the client must send the complete flag state, not just changed fields.

**Alternatives considered**: Using PATCH for consistency with dashboards/bookmarks — rejected because the Mixpanel API requires PUT for flag updates.

**Implication**: The Python `UpdateFeatureFlagParams` model will have `name`, `key`, `status`, and `ruleset` as required fields, unlike other update params where everything is optional.

### R4: Experiment entry endpoint trailing slash

**Decision**: Experiment entry endpoints (get, update, delete, launch, conclude, decide, archive, restore, duplicate) do NOT have trailing slashes. List and create DO have trailing slashes.

**Rationale**: The Rust reference explicitly documents this at api_client.rs line 1668 — experiment entry endpoints omit the trailing slash while collection endpoints include it. This matches Django's URL routing for experiments.

**Alternatives considered**: Adding trailing slashes everywhere — rejected because it would cause 301 redirects or 404s depending on Django's `APPEND_SLASH` setting.

### R5: Experiment conclude requires body even when empty

**Decision**: The `conclude_experiment()` method always sends a JSON body, defaulting to `{}` when no params are provided.

**Rationale**: The Rust reference (api_client.rs conclude_experiment) always sends `serde_json::json!({})` as the body for conclude requests, even when `ExperimentConcludeParams` is None. The Mixpanel API apparently requires a body for PUT requests to the force_conclude endpoint.

**Alternatives considered**: Sending no body — rejected because it may cause 400 errors.

### R6: Feature flag ID type (string vs int)

**Decision**: Feature flag IDs are strings (UUIDs), unlike dashboards/bookmarks/cohorts which use integers.

**Rationale**: The Rust `FeatureFlag` struct has `id: String`, and the workspace methods accept `id: &str`. This is because Mixpanel uses UUIDs for feature flags and experiments, not auto-incrementing integers.

**Implication**: CLI arguments for flag/experiment IDs will be `str` type, not `int`. The workspace methods will accept `str` for ID parameters.

### R7: Experiment ID type

**Decision**: Experiment IDs are also strings (UUIDs), matching feature flags.

**Rationale**: The Rust `Experiment` struct has `id: String`.

### R8: FeatureFlagStatus enum values

**Decision**: Three statuses: `enabled`, `disabled`, `archived` (snake_case in JSON).

**Rationale**: Rust enum `FeatureFlagStatus` with variants Enabled, Disabled (default), Archived. Serialized as snake_case.

### R9: ExperimentStatus enum values

**Decision**: Five statuses: `draft`, `active`, `concluded`, `success`, `fail` (snake_case in JSON).

**Rationale**: Rust enum `ExperimentStatus` with five variants. Represents the full lifecycle.

### R10: ServingMethod enum values

**Decision**: Four methods: `client` (default), `server`, `remote_or_local`, `remote_only`.

**Rationale**: Rust enum `ServingMethod` with these four variants.

### R11: Complex nested types (ruleset, variants, metrics, settings)

**Decision**: Use `dict[str, Any]` (Python equivalent of `serde_json::Value`) for complex nested structures like flag rulesets, experiment variants, metrics, and settings.

**Rationale**: The Rust reference uses `Value` for these fields rather than fully typed structs. The API schemas for these nested objects are complex and evolving. Using `dict[str, Any]` provides flexibility and forward compatibility, matching the Rust approach.

**Alternatives considered**: Creating fully typed Pydantic models for FlagRuleset, FlagVariant, FlagRollout — rejected because the Rust reference itself uses `Value` for many of these, indicating the schemas are too fluid for strict typing. Users who need type safety can validate against their own schemas.

### R12: Forward compatibility pattern

**Decision**: All response models use `model_config = ConfigDict(frozen=True, extra="allow", populate_by_name=True)` to preserve unknown API fields.

**Rationale**: The Rust reference uses `#[serde(flatten)] extra: HashMap<String, Value>` on all response types. The Pydantic `extra="allow"` achieves the same — unknown fields are preserved in `model_extra` rather than rejected.

### R13: Flag history response shape

**Decision**: `FlagHistoryResponse` contains `events: list[list[Any]]` and `count: int`.

**Rationale**: The Rust type has `events: Vec<Vec<Value>>` — each event is an array of values (not a structured object). This unusual shape is what the API returns.

### R14: Test user overrides shape

**Decision**: `SetTestUsersParams` contains `users: dict[str, str]` mapping variant keys to user distinct IDs.

**Rationale**: The Rust type has `users: HashMap<String, String>`.

### R15: Existing infrastructure readiness

**Decision**: All prerequisites are met. No new infrastructure needed.

**Verification**:
- OAuth auth module: `_internal/auth/` exists with all 6 files (pkce, token, storage, callback_server, client_registration, flow)
- `app_request()`: exists at `api_client.py:664`
- `maybe_scoped_path()`: exists at `api_client.py:906`
- `require_scoped_path()`: exists at `api_client.py:935`
- Pagination module: `_internal/pagination.py` exists
- Workspace scoping: `workspace_id` property exists
- CLI utils: `handle_errors`, `get_workspace`, `output_result`, `status_spinner` all available
