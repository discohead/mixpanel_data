# Research: OAuth PKCE & App API Infrastructure

**Feature**: 023-oauth-app-api-infra | **Date**: 2026-03-25

## R1: OAuth 2.0 PKCE Flow Implementation

**Decision**: Implement RFC 7636 Authorization Code + PKCE using S256, with Dynamic Client Registration (RFC 7591).

**Rationale**: The Rust reference implementation uses this exact flow. Mixpanel's OAuth provider (`/oauth/`) supports DCR at `/oauth/mcp/register/`. PKCE eliminates the need for a client secret, making it safe for CLI/desktop apps.

**Alternatives considered**:
- Device Authorization Grant (RFC 8628) — simpler UX but Mixpanel doesn't support it
- Pre-registered client ID — would work but DCR allows per-installation registration and port flexibility

### Flow Sequence (from Rust `auth/flow.rs`)

1. Generate PKCE verifier (64 random bytes → base64url no-pad) and S256 challenge
2. Generate state token (UUID v4) for CSRF protection
3. Bind callback server to first available port in `[19284, 19285, 19286, 19287]`
4. Register public client via DCR (`POST /oauth/mcp/register/`) — cache result per region
5. Build authorization URL with params: `client_id`, `redirect_uri`, `response_type=code`, `code_challenge`, `code_challenge_method=S256`, `state` (omit `scope` to get all scopes)
6. Open browser (fallback: print URL to stderr)
7. Wait for callback (5 min timeout)
8. Validate state matches (CSRF check)
9. Exchange code for tokens (`POST /oauth/token/`)
10. Save tokens with optional `project_id`

### OAuth Endpoints (region-dependent)

| Region | Base URL |
|--------|----------|
| US | `https://mixpanel.com/oauth/` |
| EU | `https://eu.mixpanel.com/oauth/` |
| IN | `https://in.mixpanel.com/oauth/` |

### DCR Request

```
POST {base_url}mcp/register/
Content-Type: application/json

{
  "redirect_uris": ["http://localhost:{port}/callback"],
  "client_name": "Mixpanel CLI - {YYYY-MM-DD}",
  "scope": "projects analysis events insights segmentation retention data:read funnels flows data_definitions dashboard_reports bookmarks",
  "grant_types": ["authorization_code", "refresh_token"],
  "token_endpoint_auth_method": "none"
}
```

Response: `{ "client_id": "...", "client_id_issued_at": 1709568000, "redirect_uris": [...] }`

**Critical**: Django OAuth Toolkit treats empty scope as "all scopes allowed" — omit `scope` from auth URL.

### Token Exchange

```
POST {base_url}token/
Content-Type: application/x-www-form-urlencoded

grant_type=authorization_code&code={code}&redirect_uri={redirect_uri}&client_id={client_id}&code_verifier={code_verifier}
```

Response: `{ "access_token": "...", "token_type": "Bearer", "expires_in": 36000, "refresh_token": "...", "scope": "..." }`

### Token Refresh

```
POST {base_url}token/
Content-Type: application/x-www-form-urlencoded

grant_type=refresh_token&refresh_token={refresh_token}&client_id={client_id}
```

---

## R2: PKCE Algorithm

**Decision**: 64 random bytes → base64url (no padding) for verifier; SHA-256 of verifier → base64url (no padding) for challenge.

**Rationale**: Matches Rust implementation exactly. 64 bytes → 86 base64url chars (within RFC 7636's 43-128 range).

**Python implementation**: `secrets.token_bytes(64)` → `base64.urlsafe_b64encode().rstrip(b'=')` → `hashlib.sha256(verifier).digest()` → `base64.urlsafe_b64encode().rstrip(b'=')`

---

## R3: Token Storage

**Decision**: JSON files at `~/.mp/oauth/` with Unix permissions (dir: 0o700, files: 0o600).

**Rationale**: Matches Rust implementation. JSON is human-readable and debuggable.

**File naming**:
- `tokens_{region}.json` — OAuth tokens per region
- `client_{region}.json` — Cached DCR client info per region

**Token JSON format**:
```json
{
  "access_token": "...",
  "refresh_token": "...",
  "expires_at": "2026-03-25T10:30:00Z",
  "scope": "projects analysis ...",
  "token_type": "Bearer",
  "project_id": "optional"
}
```

**Client info JSON format**:
```json
{
  "client_id": "...",
  "region": "us",
  "redirect_uri": "http://localhost:19284/callback",
  "scope": "projects analysis ...",
  "created_at": "2026-03-25T10:30:00Z"
}
```

**Override**: `MP_OAUTH_STORAGE_DIR` environment variable.

---

## R4: Callback Server

**Decision**: Ephemeral `http.server`-based TCP listener on localhost, trying ports 19284–19287.

**Rationale**: stdlib `http.server` + `threading` avoids external dependencies. Port list matches Rust.

**Key details**:
- Bind to `127.0.0.1` but use `localhost` in redirect URI (Mixpanel webapp regex expects `localhost`)
- 5-minute timeout for callback
- Parse query params: `code`, `state`, `error`, `error_description`
- Validate `state` matches (CSRF protection)
- Respond with HTML success/error page, then shut down
- 8KB buffer for HTTP request parsing

---

## R5: Credential Resolution Extension

**Decision**: Extend resolution order to: env vars > OAuth tokens > named account > default.

**Rationale**: Backward compatible — env vars still win. OAuth slots in naturally for users who've run `mp auth login`.

**Auth method selection**:
- Query/Export/Engage endpoints → Basic Auth (service accounts)
- App API endpoints → Bearer token (OAuth) preferred, Basic Auth accepted as fallback
- The `@auth_required` decorator in Mixpanel's Django accepts both

**Implementation**: Add `AuthMethod` enum (`basic`, `oauth`) to `Credentials` or create parallel `OAuthCredentials` type. The API client selects auth header based on endpoint category.

---

## R6: App API Request Infrastructure

**Decision**: Extend `MixpanelAPIClient` with `app_request()` method using Bearer auth, workspace scoping, and automatic result unwrapping.

**Rationale**: The `"app"` URLs already exist in `ENDPOINTS` dict. Extending the existing client avoids duplication.

### Workspace Scoping Patterns

Two URL patterns exist in the Rust implementation:

1. **Top-level (optional workspace)** — `maybe_scoped_path()`:
   - With workspace: `/api/app/workspaces/{wid}/{domain}/...`
   - Without workspace: `/api/app/projects/{pid}/{domain}/...`
   - Used by: dashboards, cohorts, alerts, annotations, bookmarks, webhooks, lexicon, etc.

2. **Project-nested (required workspace)** — `require_scoped_path()`:
   - Always: `/api/app/projects/{pid}/workspaces/{wid}/{domain}/...`
   - Auto-discovers workspace ID if not set
   - Used by: feature flags only

### Workspace Resolution

1. Return explicit workspace ID if set (via `--workspace-id` or `set_workspace_id()`)
2. Auto-discover: `GET /api/app/projects/{pid}/workspaces/public` → find `is_default: true`
3. Cache result for lifetime of client instance (Python: simple instance variable with sentinel)

### Result Unwrapping

App API responses have two shapes:
- `{ "status": "ok", "results": [...] }` — unwrap `results`
- `{ "status": "ok", ... }` — return full response (for non-list endpoints)

### Error Handling

- 204 No Content → synthetic `{"status": "ok"}`
- 404 → `ResourceNotFoundError` (new, or reuse existing `QueryError`)
- 422 → `ValidationError` (for bad request bodies)
- Other 4xx/5xx → existing `APIError` hierarchy

---

## R7: Cursor-Based Pagination

**Decision**: Generic `PaginatedResponse` model with `CursorPagination` support.

**Rationale**: Matches Rust's `PaginatedResponse<T>` pattern. All App API list endpoints use consistent pagination.

**Response format**:
```json
{
  "status": "ok",
  "results": [...],
  "pagination": {
    "page_size": 100,
    "next_cursor": "abc123",
    "previous_cursor": "xyz789"
  }
}
```

**Pagination helper**: `paginate_all()` generator that follows `next_cursor` until `None`.

---

## R8: Token Expiry Buffer

**Decision**: 30-second buffer before expiry (tokens considered expired if within 30s of `expires_at`).

**Rationale**: Matches Rust implementation. Prevents race conditions where a token expires mid-request.

**Implementation**: `is_expired()` checks `datetime.now(UTC) + timedelta(seconds=30) >= expires_at`

---

## R9: Existing Python Patterns to Follow

**API Client**: `_build_url(api_type, path)` + `_request(method, url, params, ...)` with `_execute_with_retry()` for rate limiting.

**Workspace**: Lazy service initialization via properties. Dependency injection for testing (`_api_client`, `_config_manager` params).

**Types**: `@dataclass(frozen=True)` inheriting `ResultWithDataFrame` for query results. Pydantic `BaseModel` with `ConfigDict(frozen=True)` for API response models.

**CLI**: Typer command groups via `app.add_typer()`. `@handle_errors` decorator. `get_workspace(ctx)` helper. `output_result(ctx, data, format=format)` for output.

**Docstrings**: Google-style with Args/Returns/Raises/Example sections. Markdown code fences (not doctest `>>>`).

**Strict typing**: `mypy --strict` compliant. No untyped `Any`. `Literal` for constrained strings.
