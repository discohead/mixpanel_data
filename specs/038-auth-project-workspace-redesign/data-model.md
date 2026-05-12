# Data Model: Auth, Project & Workspace Management Redesign

**Phase 1 Output** | **Date**: 2026-04-07

## Entities

### AuthCredential

A standalone authentication identity — "who you are" — independent of any project.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| name | string | Yes | Unique identifier within config (e.g., "demo-sa") |
| type | enum | Yes | "service_account" or "oauth" |
| region | enum | Yes | "us", "eu", or "in" |
| username | string | SA only | Service account username |
| secret | redacted string | SA only | Service account secret (never exposed in output) |
| oauth_access_token | redacted string | OAuth only | Bearer token (loaded from token storage) |

**Validation rules**:
- `name` must be non-empty and unique within config
- `type` must be one of the two enum values
- `region` must be one of "us", "eu", "in"
- For service_account: `username` and `secret` must be non-empty
- For oauth: `oauth_access_token` must be non-empty when resolved
- Immutable after construction

**Relationships**: One AuthCredential can access many Projects (via /me discovery). Referenced by ProjectAlias and ActiveContext.

---

### ProjectContext

What you're working on — a project with an optional workspace selection.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| project_id | string | Yes | Mixpanel project identifier |
| workspace_id | integer | No | Workspace within the project |
| project_name | string | No | Human-readable name (from /me cache) |
| workspace_name | string | No | Human-readable name (from /me cache) |

**Validation rules**:
- `project_id` must be non-empty
- `workspace_id` must be a positive integer if present
- Immutable after construction

**Relationships**: Always paired with an AuthCredential to form a ResolvedSession.

---

### ResolvedSession

The composition of authentication + project context. This is what the API client uses to make requests.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| auth | AuthCredential | Yes | Authentication identity |
| project | ProjectContext | Yes | Project and workspace selection |

**Derived properties**:
- `project_id` → from `project.project_id`
- `region` → from `auth.region`
- `auth_header()` → delegates to `auth.auth_header()`

**Validation rules**:
- Both `auth` and `project` must be valid
- Immutable after construction

**Relationships**: Created by ConfigManager.resolve_session(). Consumed by MixpanelAPIClient.

---

### ProjectAlias

A named shortcut for quick context switching.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| name | string | Yes | Alias name (e.g., "ecom", "ai-demo") |
| project_id | string | Yes | Target project ID |
| credential | string | No | Credential name to use (defaults to active) |
| workspace_id | integer | No | Default workspace for this alias |

**Validation rules**:
- `name` must be non-empty and unique within config
- `project_id` must be non-empty
- If `credential` is specified, it must reference an existing credential

**Relationships**: References an AuthCredential by name. Used by `mp context switch <alias>`.

---

### ActiveContext

The currently selected credential + project + workspace, persisted in config.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| credential | string | No | Active credential name |
| project_id | string | No | Active project ID |
| workspace_id | integer | No | Active workspace ID |

**Validation rules**:
- All fields are optional (allows partial configuration)
- If `credential` is specified, it should reference an existing credential
- If `project_id` is specified, the credential should have access to it

**State transitions**:
- `set_active_credential(name)` → updates `credential`
- `set_active_project(id, workspace_id?)` → updates `project_id` and optionally `workspace_id`
- `set_active_workspace(id)` → updates `workspace_id` only

**Relationships**: Stored in config `[active]` section. Read by resolve_session() as fallback.

---

### MeResponse

Cached response from the Mixpanel /me API.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| user_id | integer | No | Authenticated user's ID |
| user_email | string | No | User's email |
| user_name | string | No | User's display name |
| organizations | map[string → MeOrgInfo] | No | Accessible organizations, keyed by org ID |
| projects | map[string → MeProjectInfo] | No | Accessible projects, keyed by project ID |
| workspaces | map[string → MeWorkspaceInfo] | No | Accessible workspaces, keyed by workspace ID |
| cached_at | datetime | No | When this response was cached (added by client) |
| cached_region | string | No | Which region this cache is for (added by client) |

**Validation rules**:
- All fields optional (forward-compatible deserialization)
- Unknown fields are preserved (extra="allow")
- `cached_at` is added by the caching layer, not the API

**Relationships**: Contains MeOrgInfo, MeProjectInfo, MeWorkspaceInfo. Stored by MeCache.

---

### MeProjectInfo

Project information within a /me response.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| name | string | Yes | Project display name |
| organization_id | integer | Yes | Owning organization |
| timezone | string | No | Project timezone |
| has_workspaces | boolean | No | Whether project uses workspaces |
| domain | string | No | Mixpanel domain for the project's cluster |
| type | string | No | "PROJECT" or "ROLLUP" |
| role | object | No | User's role in this project (id + name) |
| permissions | list[string] | No | User's permissions in this project |

**Validation rules**: Unknown fields preserved (extra="allow").

---

### MeWorkspaceInfo

Workspace information within a /me response.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| id | integer | Yes | Workspace ID |
| name | string | Yes | Workspace display name |
| project_id | integer | Yes | Parent project ID |
| is_default | boolean | No | Whether this is the project's default workspace |
| is_global | boolean | No | Whether this is a global workspace |
| is_restricted | boolean | No | Whether access is restricted |
| is_visible | boolean | No | Whether workspace is visible |
| description | string | No | Workspace description |
| creator_name | string | No | Who created the workspace |

**Validation rules**: Unknown fields preserved (extra="allow").

---

### MeOrgInfo

Organization information within a /me response.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| id | integer | Yes | Organization ID |
| name | string | Yes | Organization display name |
| role | string | No | User's role in this organization |
| permissions | list[string] | No | User's permissions in this organization |

**Validation rules**: Unknown fields preserved (extra="allow").

---

## Config File Schema (v2)

### Structure

```toml
config_version = 2

[active]
credential = "demo-sa"
project_id = "3713224"
workspace_id = 3448413

[credentials.demo-sa]
type = "service_account"
username = "jared-mp-demo.292e7c.mp-service-account"
secret = "aQUXhKokwLywLoxE3AxLt0g9dXC2G7bT"
region = "us"

[credentials.my-oauth]
type = "oauth"
region = "us"

[projects.ai-demo]
project_id = "3713224"
credential = "demo-sa"
workspace_id = 3448413

[projects.ecommerce]
project_id = "3018488"
credential = "demo-sa"
```

### Version Detection

| Key Present | Schema Version |
|-------------|---------------|
| `config_version = 2` | v2 (new) |
| No `config_version` key | v1 (legacy) |

### Migration Mapping (v1 → v2)

| v1 Concept | v2 Concept |
|-----------|-----------|
| `[accounts.X]` (all fields) | `[credentials.Y]` (auth fields) + `[projects.X]` (project alias) |
| `default = "X"` | `[active].credential` + `[active].project_id` from account X |
| N/A | `[active].workspace_id` (new) |
