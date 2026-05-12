# Library API Contract: OAuth & App API Infrastructure

**Feature**: 023-oauth-app-api-infra | **Date**: 2026-03-25

This document defines the public API surface added by this feature. All methods below become part of the stable `mixpanel_data` public API.

## Workspace Class Extensions

### OAuth Authentication

```python
# No new public methods on Workspace for auth — auth is handled via:
# 1. OAuthFlow class (for CLI login)
# 2. Credential resolution (automatic for library users)
```

### Workspace Discovery

```python
class Workspace:
    def list_workspaces(self) -> list[PublicWorkspace]:
        """List all workspaces in the current project.

        Returns:
            List of PublicWorkspace objects with id, name, is_default.

        Raises:
            OAuthError: If OAuth tokens are missing or expired.
            AuthenticationError: If credentials are invalid.
            APIError: If the API request fails.
        """

    def resolve_workspace_id(self) -> int:
        """Resolve the workspace ID for App API requests.

        Resolution order:
        1. Explicit workspace_id (set via constructor or set_workspace_id())
        2. Auto-discover default workspace from project

        Returns:
            Integer workspace ID.

        Raises:
            WorkspaceScopeError: If no workspace can be resolved.
            OAuthError: If OAuth tokens are missing or expired.
        """

    def set_workspace_id(self, workspace_id: int | None) -> None:
        """Set explicit workspace ID for App API requests.

        Args:
            workspace_id: Workspace ID, or None to use auto-discovery.
        """

    @property
    def workspace_id(self) -> int | None:
        """Currently set workspace ID, or None if using auto-discovery."""
```

## New Public Types

### PublicWorkspace

```python
class PublicWorkspace(BaseModel):
    """A workspace within a Mixpanel project."""
    model_config = ConfigDict(frozen=True, extra="allow")

    id: int
    name: str
    project_id: int
    is_default: bool
    description: str | None = None
    is_global: bool | None = None
    is_restricted: bool | None = None
    is_visible: bool | None = None
    created_iso: str | None = None
    creator_name: str | None = None
```

### PaginatedResponse (Generic)

```python
class CursorPagination(BaseModel):
    """Cursor-based pagination metadata."""
    model_config = ConfigDict(frozen=True)

    page_size: int
    next_cursor: str | None = None
    previous_cursor: str | None = None

class PaginatedResponse(BaseModel, Generic[T]):
    """Paginated App API response wrapper."""
    model_config = ConfigDict(frozen=True)

    status: str
    results: list[T]
    pagination: CursorPagination | None = None
```

## New Exception Types

```python
class OAuthError(MixpanelDataError):
    """OAuth authentication flow error."""
    # code: str — one of OAUTH_TOKEN_ERROR, OAUTH_REFRESH_ERROR,
    #   OAUTH_REGISTRATION_ERROR, OAUTH_TIMEOUT, OAUTH_PORT_ERROR, OAUTH_BROWSER_ERROR

class WorkspaceScopeError(MixpanelDataError):
    """Workspace resolution error."""
    # code: str — one of NO_WORKSPACES, AMBIGUOUS_WORKSPACE, WORKSPACE_NOT_FOUND
```

## CLI Command Contract

### `mp auth login`

```
Usage: mp auth login [OPTIONS]

  Authenticate with Mixpanel via OAuth 2.0 PKCE flow.

Options:
  --region TEXT  Region (us, eu, in) [default: from config]
  --help         Show this message and exit.

Exit codes:
  0  Login successful
  1  General error
  2  Authentication error (OAuth flow failed)

Output (stderr): Progress messages during flow
Output (stdout): JSON confirmation on success
```

### `mp auth logout`

```
Usage: mp auth logout [OPTIONS]

  Remove stored OAuth tokens.

Options:
  --region TEXT  Region (us, eu, in) [default: all regions]
  --help         Show this message and exit.

Exit codes:
  0  Tokens removed
  1  General error
```

### `mp auth status`

```
Usage: mp auth status [OPTIONS]

  Show current authentication status.

Options:
  --format TEXT  Output format (json, table, plain) [default: table]
  --help         Show this message and exit.

Exit codes:
  0  Status displayed
  1  General error

Output (stdout): Auth method, token expiry, project ID, region
```

### `mp auth token`

```
Usage: mp auth token [OPTIONS]

  Output current OAuth access token.

Options:
  --region TEXT  Region [default: from config]
  --help         Show this message and exit.

Exit codes:
  0  Token printed to stdout
  1  General error
  2  No valid token available

Output (stdout): Raw access token string (for piping to other tools)
```

### Global Option Addition

```
--workspace-id INTEGER  Workspace ID for App API operations [env: MP_WORKSPACE_ID]
```

Added to the `main()` callback, available to all commands.

## Internal API Contract (for domain implementors)

These methods are on `MixpanelAPIClient` (internal, but stable for domain extensions):

```python
class MixpanelAPIClient:
    def app_request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, str] | None = None,
        json_body: dict[str, Any] | None = None,
    ) -> Any:
        """Make an authenticated App API request.

        Handles auth header selection, workspace scoping, and result unwrapping.
        """

    def app_request_paginated(
        self,
        path: str,
        *,
        params: dict[str, str] | None = None,
        page_size: int = 100,
    ) -> Iterator[T]:
        """Make a paginated App API GET request, yielding all results."""

    def maybe_scoped_path(self, domain_path: str) -> str:
        """Optionally scope path with workspace ID (top-level pattern)."""

    def require_scoped_path(self, domain_path: str) -> str:
        """Always scope path with workspace ID (project-nested pattern).
        Raises WorkspaceScopeError if workspace cannot be resolved.
        """

    def set_workspace_id(self, workspace_id: int | None) -> None:
        """Set explicit workspace ID."""

    def resolve_workspace_id(self) -> int:
        """Resolve workspace ID (explicit or auto-discovered)."""
```
