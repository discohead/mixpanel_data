# Data Model: OAuth PKCE & App API Infrastructure

**Feature**: 023-oauth-app-api-infra | **Date**: 2026-03-25

## Entities

### 1. AuthMethod (Enum)

Discriminator for authentication strategy.

| Value | Description |
|-------|-------------|
| `basic` | Service account Basic Auth (username + secret) |
| `oauth` | OAuth 2.0 Bearer token |

**Relationships**: Referenced by `Credentials` to determine which auth header to generate.

---

### 2. Credentials (Extended)

Immutable authentication container. Extended to support both Basic Auth and OAuth.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `username` | string | Yes (basic) | Service account username |
| `secret` | secret string | Yes (basic) | Service account secret (redacted) |
| `project_id` | string | Yes | Mixpanel project identifier |
| `region` | "us" \| "eu" \| "in" | Yes | Data residency region |
| `auth_method` | AuthMethod | Yes | Which auth strategy to use |
| `oauth_tokens` | OAuthTokens \| None | No | OAuth tokens (when auth_method=oauth) |

**Validation**:
- `username` and `project_id` must be non-empty strings
- `region` must be one of: us, eu, in
- If `auth_method=basic`, `username` and `secret` are required
- If `auth_method=oauth`, `oauth_tokens` must be present

**State transitions**: None (immutable after construction)

---

### 3. OAuthTokens

Immutable token set from an OAuth 2.0 token response.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `access_token` | secret string | Yes | Bearer token for API requests (redacted) |
| `refresh_token` | secret string \| None | No | Token for refreshing access (redacted) |
| `expires_at` | datetime (UTC) | Yes | When the access token expires |
| `scope` | string | Yes | Space-separated list of granted scopes |
| `token_type` | string | Yes | Always "Bearer" |
| `project_id` | string \| None | No | Associated project (preserved through refresh) |

**Validation**:
- `access_token` must be non-empty
- `expires_at` must be a valid UTC datetime
- `token_type` must be "Bearer"

**Derived behavior**:
- `is_expired()`: Returns true if `now + 30 seconds >= expires_at`

**State transitions**: Immutable. Token refresh produces a new `OAuthTokens` instance.

**Persistence**: JSON file at `~/.mp/oauth/tokens_{region}.json`

---

### 4. PkceChallenge

Single-use PKCE verifier/challenge pair for one authorization flow.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `verifier` | string | Yes | 86-char base64url string (from 64 random bytes) |
| `challenge` | string | Yes | base64url SHA-256 hash of verifier |

**Validation**:
- `verifier` length must be 43–128 characters (RFC 7636)
- `challenge` must be base64url-encoded

**State transitions**: None (immutable, ephemeral — used once per flow, never persisted)

---

### 5. OAuthClientInfo

Cached Dynamic Client Registration result.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `client_id` | string | Yes | Registered client identifier |
| `region` | "us" \| "eu" \| "in" | Yes | Region this registration is for |
| `redirect_uri` | string | Yes | Callback URI used during registration |
| `scope` | string | Yes | Requested scope string |
| `created_at` | datetime (UTC) | Yes | When registration occurred |

**Validation**:
- `client_id` must be non-empty
- `redirect_uri` must start with `http://localhost:`

**Persistence**: JSON file at `~/.mp/oauth/client_{region}.json`

**Cache invalidation**: Re-register if `redirect_uri` doesn't match (port changed)

---

### 6. CallbackResult

Result from the ephemeral OAuth callback server.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `code` | string | Yes | Authorization code from Mixpanel |
| `state` | string | Yes | State token for CSRF validation |

**Validation**:
- Both fields must be non-empty
- `state` must match the value sent in the authorization request

**State transitions**: None (ephemeral, consumed immediately by token exchange)

---

### 7. PublicWorkspace

Organizational unit within a Mixpanel project.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | integer | Yes | Workspace identifier |
| `name` | string | Yes | Human-readable workspace name |
| `project_id` | integer | Yes | Parent project identifier |
| `is_default` | boolean | Yes | Whether this is the default workspace |
| `description` | string \| None | No | Workspace description |
| `is_global` | boolean \| None | No | Whether workspace is global |
| `is_restricted` | boolean \| None | No | Whether workspace has restrictions |
| `is_visible` | boolean \| None | No | Whether workspace is visible |
| `created_iso` | string \| None | No | ISO 8601 creation timestamp |
| `creator_name` | string \| None | No | Name of workspace creator |

**Relationships**: A project has one or more workspaces. One workspace is `is_default=true`.

---

### 8. PaginatedResponse

Generic wrapper for paginated App API responses.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `status` | string | Yes | Response status (typically "ok") |
| `results` | list[T] | Yes | Page of results |
| `pagination` | CursorPagination \| None | No | Pagination metadata |

---

### 9. CursorPagination

Cursor-based pagination metadata.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `page_size` | integer | Yes | Number of items per page |
| `next_cursor` | string \| None | No | Cursor for next page (None = last page) |
| `previous_cursor` | string \| None | No | Cursor for previous page |

---

## Entity Relationship Diagram

```
Credentials ──has──> AuthMethod
    │
    └──has (optional)──> OAuthTokens ──persisted as──> tokens_{region}.json

OAuthFlow ──generates──> PkceChallenge (ephemeral)
    │
    ├──uses──> OAuthClientInfo ──persisted as──> client_{region}.json
    │
    ├──starts──> CallbackServer ──produces──> CallbackResult
    │
    └──exchanges──> authorization code ──for──> OAuthTokens

MixpanelAPIClient ──uses──> Credentials
    │
    ├──discovers──> PublicWorkspace (via list_workspaces)
    │
    └──returns──> PaginatedResponse<T> ──contains──> CursorPagination
```

## Exception Types

### OAuthError

Inherits from `MixpanelDataError`. Raised for OAuth-specific failures.

| Scenario | Error Code | Description |
|----------|------------|-------------|
| Token exchange fails | `OAUTH_TOKEN_ERROR` | Invalid grant, expired code |
| Token refresh fails | `OAUTH_REFRESH_ERROR` | Refresh token expired/revoked |
| DCR fails | `OAUTH_REGISTRATION_ERROR` | Client registration rejected |
| Callback timeout | `OAUTH_TIMEOUT` | No callback received within timeout |
| Port unavailable | `OAUTH_PORT_ERROR` | All callback ports occupied |
| Browser open fails | `OAUTH_BROWSER_ERROR` | Could not open browser (URL printed as fallback) |

### WorkspaceScopeError

Inherits from `MixpanelDataError`. Raised when workspace resolution fails.

| Scenario | Error Code | Description |
|----------|------------|-------------|
| No workspaces found | `NO_WORKSPACES` | Project has no accessible workspaces |
| Multiple workspaces, none default | `AMBIGUOUS_WORKSPACE` | Must specify `--workspace-id` |
| Workspace ID not found | `WORKSPACE_NOT_FOUND` | Explicit ID doesn't match any workspace |
