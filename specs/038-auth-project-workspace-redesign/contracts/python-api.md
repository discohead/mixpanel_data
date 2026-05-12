# Python API Contracts: Auth, Project & Workspace Management

**Phase 1 Output** | **Date**: 2026-04-07

## Public API Surface

### Workspace Class (Extended)

```python
class Workspace:
    """Unified facade for all Mixpanel data operations."""

    def __init__(
        self,
        # Existing (backward compatible)
        account: str | None = None,
        project_id: str | None = None,
        region: str | None = None,
        workspace_id: int | None = None,
        # New
        credential: str | None = None,
        session: ResolvedSession | None = None,
        # DI
        _config_manager: ConfigManager | None = None,
        _api_client: MixpanelAPIClient | None = None,
    ) -> None: ...

    # --- Discovery ---

    def me(self, *, force_refresh: bool = False) -> MeResponse:
        """Get /me response for current credentials (cached 24h)."""

    def discover_projects(self) -> list[tuple[str, MeProjectInfo]]:
        """List all accessible projects. Returns [(project_id, info), ...]."""

    def discover_workspaces(
        self, project_id: str | None = None,
    ) -> list[MeWorkspaceInfo]:
        """List workspaces for a project. Defaults to current project."""

    # --- Context Switching ---

    def switch_project(
        self, project_id: str, workspace_id: int | None = None,
    ) -> None:
        """Switch to a different project. Clears discovery cache."""

    def switch_workspace(self, workspace_id: int) -> None:
        """Switch workspace within current project."""

    # --- Context Inspection ---

    @property
    def current_project(self) -> ProjectContext:
        """Current project context (project_id, workspace_id, names)."""

    @property
    def current_credential(self) -> AuthCredential:
        """Current auth credential (name, type, region)."""
```

### New Public Types

```python
# From mixpanel_data.auth (re-exported from _internal.auth_credential)

class AuthCredential:
    """Pure authentication identity — no project binding."""
    name: str
    type: CredentialType      # service_account | oauth
    region: RegionType        # us | eu | in
    def auth_header(self) -> str: ...

class ProjectContext:
    """Project + optional workspace selection."""
    project_id: str
    workspace_id: int | None
    project_name: str | None
    workspace_name: str | None

class ResolvedSession:
    """Fully resolved session: auth + project."""
    auth: AuthCredential
    project: ProjectContext
    project_id: str           # property
    region: RegionType        # property
    def auth_header(self) -> str: ...

class CredentialType(str, Enum):
    service_account = "service_account"
    oauth = "oauth"
```

### Me Response Types

```python
# From mixpanel_data._internal.me (public use via Workspace.me())

class MeResponse:
    user_id: int | None
    user_email: str | None
    user_name: str | None
    organizations: dict[str, MeOrgInfo]
    projects: dict[str, MeProjectInfo]
    workspaces: dict[str, MeWorkspaceInfo]

class MeProjectInfo:
    name: str
    organization_id: int
    timezone: str | None
    has_workspaces: bool
    permissions: list[str]

class MeWorkspaceInfo:
    id: int
    name: str
    project_id: int
    is_default: bool

class MeOrgInfo:
    id: int
    name: str
    role: str | None
    permissions: list[str]
```

### ConfigManager (Extended)

```python
class ConfigManager:
    # --- Existing (preserved) ---
    def resolve_credentials(self, account: str | None = None) -> Credentials: ...
    def list_accounts(self) -> list[AccountInfo]: ...
    def add_account(self, name, username, secret, project_id, region) -> None: ...
    def remove_account(self, name: str) -> None: ...
    def set_default(self, name: str) -> None: ...
    def get_account(self, name: str) -> AccountInfo: ...

    # --- New: Session Resolution ---
    def resolve_session(
        self,
        credential: str | None = None,
        project_id: str | None = None,
        workspace_id: int | None = None,
    ) -> ResolvedSession: ...

    # --- New: Credential Management ---
    def list_credentials(self) -> list[CredentialInfo]: ...
    def add_credential(
        self, name: str, type: str,
        username: str | None = None,
        secret: str | None = None,
        region: str = "us",
    ) -> None: ...
    def remove_credential(self, name: str) -> None: ...

    # --- New: Project Alias Management ---
    def list_project_aliases(self) -> list[ProjectAlias]: ...
    def add_project_alias(
        self, name: str, project_id: str,
        credential: str | None = None,
        workspace_id: int | None = None,
    ) -> None: ...
    def remove_project_alias(self, name: str) -> None: ...

    # --- New: Active Context ---
    def get_active_context(self) -> ActiveContext: ...
    def set_active_credential(self, name: str) -> None: ...
    def set_active_project(
        self, project_id: str, workspace_id: int | None = None,
    ) -> None: ...
    def set_active_workspace(self, workspace_id: int) -> None: ...

    # --- New: Migration ---
    def config_version(self) -> int: ...
    def migrate_v1_to_v2(self) -> MigrationResult: ...
```

### MixpanelAPIClient (Extended)

```python
class MixpanelAPIClient:
    def __init__(
        self,
        credentials: Credentials | ResolvedSession,
        *,
        timeout: float = 120.0,
        export_timeout: float = 600.0,
        max_retries: int = 3,
        _transport: httpx.BaseTransport | None = None,
    ) -> None: ...

    def with_project(
        self, project_id: str, workspace_id: int | None = None,
    ) -> MixpanelAPIClient:
        """New client for different project, same auth + HTTP transport."""

    def me(self) -> dict[str, Any]:
        """Call GET /api/app/me (not project-scoped)."""
```

### Credentials (Extended for Bridge)

```python
class Credentials:
    # ... all existing fields unchanged ...

    def to_resolved_session(self) -> ResolvedSession:
        """Convert legacy Credentials to ResolvedSession."""
```

## Error Contracts

### New Exceptions

```python
class ProjectNotFoundError(ConfigError):
    """Raised when a specified project is not accessible."""
    project_id: str
    available_projects: list[str]
```

### Existing Exceptions (Unchanged)

All existing exceptions (`ConfigError`, `AccountNotFoundError`, `AuthenticationError`, etc.) continue to be raised in the same scenarios.

## Credential Resolution Priority

```
resolve_session(credential?, project_id?, workspace_id?) → ResolvedSession

  Priority 1: ENV VARS (MP_USERNAME + MP_SECRET + MP_PROJECT_ID + MP_REGION)
  Priority 2: EXPLICIT PARAMS (credential + project_id + workspace_id)
  Priority 3: LEGACY ACCOUNT (account param → v1 accounts or v2 aliases)
  Priority 4: ACTIVE CONTEXT (config [active] section)
  Priority 5: OAUTH FALLBACK (valid token + active.project_id)
  Priority 6: FIRST AVAILABLE (first credential + first known project)
```
