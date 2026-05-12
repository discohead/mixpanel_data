# Tasks: OAuth PKCE & App API Infrastructure

**Input**: Design documents from `/specs/023-oauth-app-api-infra/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/library-api.md

**Tests**: Included — project CLAUDE.md mandates strict TDD (tests FIRST, then implementation).

**Organization**: Tasks grouped by user story for independent implementation and testing.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

- **Library**: `src/mixpanel_data/`
- **Internal**: `src/mixpanel_data/_internal/`
- **Auth module**: `src/mixpanel_data/_internal/auth/`
- **CLI**: `src/mixpanel_data/cli/`
- **Tests**: `tests/`

---

## Phase 1: Setup

**Purpose**: Create auth module structure and new exception types

- [x] T001 Create auth module package with `__init__.py` in `src/mixpanel_data/_internal/auth/__init__.py`
- [x] T002 [P] Add `OAuthError` exception class to `src/mixpanel_data/exceptions.py` (inherits `MixpanelDataError`, codes: OAUTH_TOKEN_ERROR, OAUTH_REFRESH_ERROR, OAUTH_REGISTRATION_ERROR, OAUTH_TIMEOUT, OAUTH_PORT_ERROR, OAUTH_BROWSER_ERROR)
- [x] T003 [P] Add `WorkspaceScopeError` exception class to `src/mixpanel_data/exceptions.py` (inherits `MixpanelDataError`, codes: NO_WORKSPACES, AMBIGUOUS_WORKSPACE, WORKSPACE_NOT_FOUND)
- [x] T004 [P] Add `PublicWorkspace` frozen Pydantic model to `src/mixpanel_data/types.py` (fields: id, name, project_id, is_default, description, is_global, is_restricted, is_visible, created_iso, creator_name; `extra="allow"`)
- [x] T005 [P] Add `CursorPagination` and `PaginatedResponse[T]` frozen Pydantic models to `src/mixpanel_data/types.py` (CursorPagination: page_size, next_cursor, previous_cursor; PaginatedResponse: status, results, pagination)
- [x] T006 Export new types (`OAuthError`, `WorkspaceScopeError`, `PublicWorkspace`) from `src/mixpanel_data/__init__.py`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: PKCE, token model, and storage — core building blocks all OAuth stories depend on

**CRITICAL**: No user story work can begin until this phase is complete

### Tests for Foundational Phase

- [x] T007 [P] Write tests for PKCE challenge generation in `tests/test_auth_pkce.py` — verify: verifier is 86 chars, base64url no-pad, challenge is SHA-256 of verifier in base64url no-pad, deterministic for same input, different per generation
- [x] T008 [P] Write tests for OAuthTokens model in `tests/test_auth_token.py` — verify: frozen immutable, `is_expired()` returns True when within 30s of expires_at, `is_expired()` returns False when >30s from expires_at, SecretStr redaction in repr, JSON round-trip serialization/deserialization, project_id preservation
- [x] T009 [P] Write tests for OAuthStorage in `tests/test_auth_storage.py` — verify: save/load token round-trip, save/load client info round-trip, file permissions (0o600 for files, 0o700 for dir), `MP_OAUTH_STORAGE_DIR` override, region-specific file naming (`tokens_{region}.json`, `client_{region}.json`), missing file returns None, delete removes files
- [x] T010 [P] Write tests for `AuthMethod` enum and extended credential resolution in `tests/test_config_oauth.py` — verify: existing Basic Auth resolution unchanged, `AuthMethod.basic` and `AuthMethod.oauth` values, `auth_header()` returns correct header for each method

### Implementation for Foundational Phase

- [x] T011 [P] Implement `PkceChallenge` class in `src/mixpanel_data/_internal/auth/pkce.py` — `generate()` classmethod: 64 random bytes → base64url no-pad verifier, SHA-256 → base64url no-pad challenge. Use stdlib `secrets`, `hashlib`, `base64`
- [x] T012 [P] Implement `OAuthTokens` frozen Pydantic model in `src/mixpanel_data/_internal/auth/token.py` — fields: access_token (SecretStr), refresh_token (Optional[SecretStr]), expires_at (datetime UTC), scope (str), token_type (str), project_id (Optional[str]). Method: `is_expired()` with 30s buffer. Class method: `from_token_response(data, project_id)` to compute `expires_at` from `expires_in`
- [x] T013 [P] Implement `OAuthClientInfo` frozen Pydantic model in `src/mixpanel_data/_internal/auth/token.py` — fields: client_id, region, redirect_uri, scope, created_at
- [x] T014 Implement `OAuthStorage` class in `src/mixpanel_data/_internal/auth/storage.py` — methods: `save_tokens(tokens, region)`, `load_tokens(region)`, `save_client_info(info)`, `load_client_info(region)`, `delete_tokens(region)`, `delete_all()`. Path: `~/.mp/oauth/` or `MP_OAUTH_STORAGE_DIR`. Permissions: dir 0o700, files 0o600
- [x] T015 Add `AuthMethod` enum (`basic`, `oauth`) to `src/mixpanel_data/_internal/config.py` and add `auth_header()` method to `Credentials` that returns `"Basic ..."` or `"Bearer ..."` based on auth method. Preserve all existing credential resolution behavior unchanged
- [x] T016 Update auth module `__init__.py` in `src/mixpanel_data/_internal/auth/__init__.py` — re-export: PkceChallenge, OAuthTokens, OAuthClientInfo, OAuthStorage

**Checkpoint**: Foundation ready — PKCE, tokens, storage, and auth method dispatch all working and tested

---

## Phase 3: User Story 1 — Interactive OAuth Login (Priority: P1) MVP

**Goal**: Users can run `mp auth login` to authenticate via browser-based OAuth PKCE flow, storing tokens locally

**Independent Test**: Run `mp auth login`, complete browser flow, verify tokens saved at `~/.mp/oauth/tokens_{region}.json` with correct permissions

### Tests for User Story 1

- [x] T017 [P] [US1] Write tests for callback server in `tests/test_auth_callback.py` — verify: binds to first available port in [19284-19287], returns code+state from query params, validates state match, handles error params, times out after configured duration, sends HTML response to browser, uses `localhost` in redirect URI
- [x] T018 [P] [US1] Write tests for Dynamic Client Registration in `tests/test_auth_registration.py` — verify: POST to `{base_url}mcp/register/` with correct body (redirect_uris, client_name, scope, grant_types, token_endpoint_auth_method), parses client_id from response, caches result per region, re-registers if redirect_uri changes, handles 429 rate limit
- [x] T019 [P] [US1] Write tests for OAuthFlow orchestrator in `tests/test_auth_flow.py` — verify: full login sequence (generate PKCE → bind callback → register client → build auth URL → exchange code → save tokens), token exchange POST with correct form params, handles missing refresh_token, preserves project_id through flow, region-specific OAuth base URLs (us/eu/in)

### Implementation for User Story 1

- [x] T020 [US1] Implement callback server in `src/mixpanel_data/_internal/auth/callback_server.py` — function: `start_callback_server(state, timeout=300)` returns `(CallbackResult, port)`. Uses stdlib `http.server` + `threading`. Tries ports [19284, 19285, 19286, 19287]. Validates state. Returns HTML success/error page. Binds `127.0.0.1`, uses `localhost` in redirect URI
- [x] T021 [US1] Implement Dynamic Client Registration in `src/mixpanel_data/_internal/auth/client_registration.py` — function: `ensure_client_registered(http_client, region, redirect_uri)` returns `OAuthClientInfo`. POST to `{oauth_base}/mcp/register/`. Cache via `OAuthStorage`. Scope: "projects analysis events insights segmentation retention data:read funnels flows data_definitions dashboard_reports bookmarks"
- [x] T022 [US1] Implement `OAuthFlow` orchestrator in `src/mixpanel_data/_internal/auth/flow.py` — class with methods: `login(project_id=None)` → full PKCE flow, `exchange_code(code, verifier, client_id, redirect_uri)` → OAuthTokens, `refresh_tokens(tokens, client_id)` → OAuthTokens. OAuth base URLs: US `https://mixpanel.com/oauth/`, EU `https://eu.mixpanel.com/oauth/`, IN `https://in.mixpanel.com/oauth/`. Wrap `httpx` calls in try/except to catch `httpx.ConnectError`, `httpx.TimeoutException` → raise `OAuthError(code="OAUTH_TOKEN_ERROR", message="Network error during token exchange: {details}")` with actionable message. Map token endpoint error responses to specific OAuthError codes: `{"error": "invalid_grant"}` → `OAuthError(code="OAUTH_TOKEN_ERROR")`, `{"error": "invalid_scope"}` → `OAuthError(code="OAUTH_TOKEN_ERROR", details={"scope_error": ...})`, `{"error": "unauthorized_client"}` → `OAuthError(code="OAUTH_REGISTRATION_ERROR")`. Parse `error_description` from response into exception message
- [x] T023 [US1] Update auth module exports in `src/mixpanel_data/_internal/auth/__init__.py` — add: OAuthFlow, CallbackResult, ensure_client_registered

**Checkpoint**: OAuth login flow works end-to-end (PKCE → browser → callback → token exchange → storage)

---

## Phase 4: User Story 2 — Automatic Token Lifecycle Management (Priority: P1)

**Goal**: Token refresh happens transparently — expired access tokens are automatically refreshed using the refresh token before API requests

**Independent Test**: Authenticate, simulate token expiry (set expires_at to past), make an App API request, verify token was auto-refreshed and new tokens persisted

### Tests for User Story 2

- [x] T024 [P] [US2] Write tests for `get_valid_token()` in `tests/test_auth_flow.py` (extend existing) — verify: returns current token if not expired, auto-refreshes if expired, persists refreshed tokens, raises OAuthError if refresh fails, raises OAuthError if no tokens exist

### Implementation for User Story 2

- [x] T025 [US2] Add `get_valid_token(region)` method to `OAuthFlow` in `src/mixpanel_data/_internal/auth/flow.py` — loads tokens from storage, checks `is_expired()`, refreshes if needed via `refresh_tokens()`, saves new tokens, returns valid access token string. Raises `OAuthError(code="OAUTH_REFRESH_ERROR")` if refresh fails

**Checkpoint**: Token lifecycle is fully automatic — expired tokens refresh transparently

---

## Phase 5: User Story 3 — App API Requests with Workspace Scoping (Priority: P1)

**Goal**: API client can make App API requests with Bearer auth, workspace scoping (optional and required patterns), and cursor-based pagination

**Independent Test**: Call `list_workspaces()` via the API client, verify it returns workspace data with correct auth headers and URL construction

### Tests for User Story 3

- [x] T026 [P] [US3] Write tests for `app_request()` in `tests/test_app_api_client.py` — verify: uses Bearer auth header, builds correct URL from ENDPOINTS["app"], unwraps `results` field from response, handles 204 No Content, maps 404 to error, maps 422 to error, passes through existing 4xx/5xx error handling
- [x] T027 [P] [US3] Write tests for workspace scoping in `tests/test_app_api_client.py` — verify: `maybe_scoped_path()` returns unscoped path when no workspace set, returns `/workspaces/{wid}/{path}` when workspace set; `require_scoped_path()` auto-discovers workspace ID via `list_workspaces()`, raises WorkspaceScopeError if no workspaces found, caches resolved workspace ID
- [x] T028 [P] [US3] Write tests for cursor pagination in `tests/test_pagination.py` — verify: `paginate_all()` yields all results across pages, follows next_cursor until None, handles empty results, handles missing pagination field (single page), respects page_size parameter

### Implementation for User Story 3

- [x] T029 [US3] Add `app_request()` method to `MixpanelAPIClient` in `src/mixpanel_data/_internal/api_client.py` — method signature: `app_request(method, path, *, params=None, json_body=None)`. Uses Bearer auth from OAuth tokens. Builds URL via `_build_url("app", scoped_path)`. Unwraps `results` from response JSON. Handles 204 → `{"status": "ok"}`
- [x] T030 [US3] Add workspace scoping methods to `MixpanelAPIClient` in `src/mixpanel_data/_internal/api_client.py` — methods: `set_workspace_id(id)`, `resolve_workspace_id()` (explicit → auto-discover default → error), `maybe_scoped_path(path)` (optional workspace, top-level pattern), `require_scoped_path(path)` (required workspace, project-nested pattern). Add `workspace_id` and `_cached_workspace_id` instance variables
- [x] T031 [US3] Add `list_workspaces()` method to `MixpanelAPIClient` in `src/mixpanel_data/_internal/api_client.py` — `GET /api/app/projects/{pid}/workspaces/public` → `list[PublicWorkspace]`
- [x] T032 [US3] Create pagination helper in `src/mixpanel_data/_internal/pagination.py` — function: `paginate_all(client, path, *, params=None, page_size=100)` → `Iterator[T]`. Follows `next_cursor` until None. Uses `app_request("GET", path, params={..., "cursor": next_cursor})`

**Checkpoint**: App API infrastructure complete — Bearer auth, workspace scoping, and pagination all working

---

## Phase 6: User Story 4 — Credential Resolution with OAuth Support (Priority: P2)

**Goal**: Credential resolution seamlessly supports OAuth alongside Basic Auth, selecting the appropriate method per endpoint category

**Independent Test**: Set env vars for Basic Auth AND have OAuth tokens stored — verify query endpoints use Basic Auth, App API endpoints use Bearer

### Tests for User Story 4

- [x] T033 [P] [US4] Write tests for extended credential resolution in `tests/test_config_oauth.py` (extend existing) — verify: env vars still resolve to Basic Auth (no regression), stored OAuth tokens resolve when no env vars set, resolution order: env > OAuth > named > default, auth method selection by endpoint type (query/export → Basic, app → Bearer)
- [x] T034 [P] [US4] Write integration tests in `tests/test_workspace_oauth.py` — verify: Workspace construction with OAuth tokens, `list_workspaces()` on Workspace class, `resolve_workspace_id()` on Workspace class, backward compatibility with existing Basic Auth Workspace usage

### Implementation for User Story 4

- [x] T035 [US4] Extend credential resolution in `src/mixpanel_data/_internal/config.py` — update `ConfigManager.resolve_credentials()` to check for stored OAuth tokens (via `OAuthStorage.load_tokens(region)`) after env vars. If OAuth tokens found, return Credentials with `auth_method=AuthMethod.oauth`. Preserve existing env var and named account resolution unchanged
- [x] T036 [US4] Add Workspace OAuth integration in `src/mixpanel_data/workspace.py` — add `list_workspaces()`, `resolve_workspace_id()`, `set_workspace_id()`, `workspace_id` property. Wire through to `MixpanelAPIClient` methods. Add `workspace_id` parameter to constructor (optional)
- [x] T037 [US4] Update `MixpanelAPIClient` in `src/mixpanel_data/_internal/api_client.py` to use `credentials.auth_header()` for auth header dispatch instead of hardcoded Basic Auth in `_get_auth_header()`. Ensure `_request()` (existing) uses Basic Auth, `app_request()` (new) uses `auth_header()` from credentials

**Checkpoint**: Both auth methods work seamlessly — existing workflows unaffected, OAuth available for App API

---

## Phase 7: User Story 5 — CLI Workspace Selection (Priority: P2)

**Goal**: CLI users can specify `--workspace-id` globally and use `mp auth login/logout/status/token` commands

**Independent Test**: Run `mp auth status` to see auth state, run `mp --workspace-id 123 auth status` to verify workspace targeting

### Tests for User Story 5

- [x] T038 [P] [US5] Write CLI auth command tests in `tests/test_cli_auth.py` — verify: `mp auth login` triggers OAuth flow (mocked), `mp auth logout` removes tokens, `mp auth status` shows auth state (authenticated/not authenticated), `mp auth token` outputs raw access token to stdout, exit codes (0 success, 2 auth error)
- [x] T039 [P] [US5] Write CLI workspace option tests in `tests/test_cli_auth.py` (extend) — verify: `--workspace-id` global option is available, value passes through `ctx.obj` to Workspace construction, `MP_WORKSPACE_ID` env var works as alternative

### Implementation for User Story 5

- [x] T040 [US5] Add `--workspace-id` global option to `src/mixpanel_data/cli/main.py` — add to `main()` callback as `typer.Option("--workspace-id", envvar="MP_WORKSPACE_ID", help="Workspace ID for App API operations")`, store in `ctx.obj["workspace_id"]`
- [x] T041 [US5] Implement `mp auth login` command in `src/mixpanel_data/cli/commands/auth.py` — creates `OAuthFlow(region)`, calls `flow.login(project_id)`, outputs JSON success confirmation. Opens browser via `webbrowser.open()`, prints fallback URL to stderr if browser fails
- [x] T042 [US5] Implement `mp auth logout` command in `src/mixpanel_data/cli/commands/auth.py` — creates `OAuthStorage()`, calls `storage.delete_tokens(region)` or `storage.delete_all()` if no region specified. Outputs JSON confirmation
- [x] T043 [US5] Implement `mp auth status` command in `src/mixpanel_data/cli/commands/auth.py` — checks for stored tokens per region, displays: auth method, token expiry, project_id, region, is_expired. Supports `--format` (json/table/plain)
- [x] T044 [US5] Implement `mp auth token` command in `src/mixpanel_data/cli/commands/auth.py` — loads tokens via `OAuthFlow.get_valid_token(region)`, prints raw access token to stdout (for piping). Exit code 2 if no valid token

**Checkpoint**: Full CLI auth workflow operational — login, logout, status, token, workspace selection

---

## Phase 8: User Story 6 — Secure Token Storage (Priority: P2)

**Goal**: Token files have correct Unix permissions, secrets are redacted everywhere except `mp auth token`

**Independent Test**: Run `mp auth login`, check file permissions with `stat`, verify no tokens in logs/stderr

### Tests for User Story 6

- [x] T045 [P] [US6] Write security tests in `tests/test_auth_storage.py` (extend existing) — verify: directory created with 0o700, files created with 0o600, `repr()` of OAuthTokens redacts access_token and refresh_token, `str()` of OAuthTokens redacts secrets, token values never appear in log output (mock logger, check messages)

### Implementation for User Story 6

- [x] T046 [US6] Audit and harden `OAuthStorage` in `src/mixpanel_data/_internal/auth/storage.py` — ensure `os.chmod()` called after every file write, ensure `os.makedirs()` with `mode=0o700` for directory, add `umask` handling for new file creation, verify `delete_tokens()` removes files completely. Add `_check_and_fix_permissions()` helper: on `load_tokens()`, check directory/file permissions; if incorrect, attempt `os.chmod()` to repair; if repair fails (e.g., not owner), log warning to stderr with actionable message ("Token storage permissions are too open: {path} has {actual}, expected {expected}. Run: chmod 600 {path}")
- [x] T047 [US6] Audit `OAuthTokens` repr/str in `src/mixpanel_data/_internal/auth/token.py` — ensure `__repr__` shows `access_token=***`, `refresh_token=***`. Verify Pydantic `SecretStr` integration works for JSON serialization (expose value only in `save_tokens()`)
- [x] T048 [US6] Audit logging across auth module — grep all auth files for any logging of token values. Ensure `logger.debug/info/warning/error` calls never include raw token strings. Add redaction where needed

**Checkpoint**: All token handling passes security audit — correct permissions, no secret leaks

---

## Phase 9: Polish & Cross-Cutting Concerns

**Purpose**: Quality gates, type checking, full test coverage verification

- [x] T049 Run `ruff format` and `ruff check` on all new and modified files
- [x] T050 Run `mypy --strict` on all new and modified files — fix any type errors
- [x] T051 Run `just test-cov` to verify 90%+ coverage on new code
- [x] T052 [P] Add property-based tests (Hypothesis) for PKCE and OAuthTokens round-trip in `tests/test_types_pbt.py`
- [x] T053 Run `just check` (full lint + typecheck + test suite) — ensure zero failures
- [x] T054 Validate quickstart.md scenarios work end-to-end (manual/mocked verification)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: No dependencies — can start immediately
- **Phase 2 (Foundational)**: Depends on Phase 1 — BLOCKS all user stories
- **Phase 3 (US1 - OAuth Login)**: Depends on Phase 2
- **Phase 4 (US2 - Token Lifecycle)**: Depends on Phase 3 (needs OAuthFlow)
- **Phase 5 (US3 - App API)**: Depends on Phase 2 (needs token model, not full flow)
- **Phase 6 (US4 - Credential Resolution)**: Depends on Phase 3 + Phase 5 (needs both auth and app_request)
- **Phase 7 (US5 - CLI)**: Depends on Phase 3 + Phase 4 (needs OAuthFlow with get_valid_token)
- **Phase 8 (US6 - Security)**: Depends on Phase 3 (audits existing auth code)
- **Phase 9 (Polish)**: Depends on all previous phases

### User Story Dependencies

- **US1 (OAuth Login)**: No story dependencies — first implementable after foundation
- **US2 (Token Lifecycle)**: Depends on US1 (extends OAuthFlow)
- **US3 (App API)**: Independent of US1/US2 — only needs foundational token model
- **US4 (Credential Resolution)**: Depends on US1 + US3 (integrates both)
- **US5 (CLI)**: Depends on US1 + US2 (needs full auth flow + auto-refresh)
- **US6 (Security)**: Depends on US1 (audits auth module)

### Parallel Opportunities

**After Phase 2 completes, these can run in parallel:**
- US1 (OAuth Login) and US3 (App API) — completely independent code paths

**After US1 completes:**
- US2 (Token Lifecycle), US6 (Security), and US3 (if not started) — all independent

**Within each phase**, tasks marked [P] can run in parallel.

---

## Parallel Example: Phase 2 (Foundational)

```bash
# Launch all tests in parallel (different files):
Task: T007 "PKCE tests in tests/test_auth_pkce.py"
Task: T008 "Token model tests in tests/test_auth_token.py"
Task: T009 "Storage tests in tests/test_auth_storage.py"
Task: T010 "Config OAuth tests in tests/test_config_oauth.py"

# Then launch parallel implementations:
Task: T011 "PkceChallenge in _internal/auth/pkce.py"
Task: T012 "OAuthTokens in _internal/auth/token.py"
Task: T013 "OAuthClientInfo in _internal/auth/token.py"  # same file as T012, sequence after
```

## Parallel Example: US1 + US3 (after Phase 2)

```bash
# These two stories can run completely in parallel:
# Agent A: US1 (OAuth Login)
Task: T017-T023 "Callback server, DCR, OAuthFlow"

# Agent B: US3 (App API)
Task: T026-T032 "app_request, workspace scoping, pagination"
```

---

## Implementation Strategy

### MVP First (US1 + US3 = OAuth + App API)

1. Complete Phase 1: Setup (T001-T006)
2. Complete Phase 2: Foundational (T007-T016)
3. Complete Phase 3: US1 OAuth Login (T017-T023)
4. Complete Phase 5: US3 App API (T026-T032) — can parallel with US1
5. **STOP and VALIDATE**: OAuth login works, App API requests work with workspace scoping
6. This is the minimum viable infrastructure for all future CRUD phases

### Incremental Delivery

1. Setup + Foundational → Core building blocks ready
2. US1 (OAuth Login) → Can authenticate (**MVP auth**)
3. US3 (App API) → Can make App API requests (**MVP infra**)
4. US2 (Token Lifecycle) → Auto-refresh works
5. US4 (Credential Resolution) → Seamless auth selection
6. US5 (CLI) → Full CLI workflow
7. US6 (Security) → Hardened storage
8. Polish → Quality gates pass

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Each user story is independently completable and testable
- TDD is mandatory: write tests FIRST, ensure they FAIL, then implement
- Commit after each task or logical group
- Run `just check` at each checkpoint
- Total: 54 tasks across 9 phases
