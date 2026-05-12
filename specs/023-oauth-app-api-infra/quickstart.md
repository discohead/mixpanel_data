# Quickstart: OAuth PKCE & App API Infrastructure

**Feature**: 023-oauth-app-api-infra | **Date**: 2026-03-25

## Prerequisites

- Python 3.10+ with `mixpanel_data` installed
- A Mixpanel account with project access
- A web browser (for OAuth consent screen)

## 1. Authenticate via OAuth

### CLI

```bash
# Login (opens browser for OAuth consent)
mp auth login

# Check authentication status
mp auth status

# Get raw access token (for debugging / external tools)
mp auth token

# Logout (remove stored tokens)
mp auth logout
```

### Library

```python
from mixpanel_data._internal.auth.flow import OAuthFlow

# Interactive login (opens browser)
flow = OAuthFlow(region="us")
tokens = flow.login()
# Tokens are persisted automatically to ~/.mp/oauth/tokens_us.json
```

## 2. Use App API Endpoints

### CLI (with workspace)

```bash
# Auto-discover workspace (single-workspace projects)
mp auth status --format json

# Explicit workspace ID
mp --workspace-id 12345 auth status

# Set via environment variable
export MP_WORKSPACE_ID=12345
```

### Library

```python
from mixpanel_data import Workspace

# Create workspace — OAuth tokens used automatically if available
ws = Workspace()

# List available workspaces
workspaces = ws.list_workspaces()
for w in workspaces:
    print(f"{w.id}: {w.name} (default={w.is_default})")

# Set explicit workspace for App API calls
ws.set_workspace_id(12345)

# Or let it auto-discover
workspace_id = ws.resolve_workspace_id()
```

## 3. Credential Resolution Order

The system resolves credentials in this order:

1. **Environment variables**: `MP_USERNAME`, `MP_SECRET`, `MP_PROJECT_ID`, `MP_REGION`
2. **OAuth tokens**: Stored at `~/.mp/oauth/tokens_{region}.json`
3. **Named account**: `Workspace(account="staging")`
4. **Default account**: From `~/.mp/config.toml`

For App API endpoints, OAuth Bearer auth is preferred. For query/export endpoints, Basic Auth is used.

## 4. Token Lifecycle

Tokens are managed automatically:
- **Access tokens** expire after ~10 hours. The library refreshes them transparently.
- **Refresh tokens** are long-lived. If they expire, re-run `mp auth login`.
- **Storage**: `~/.mp/oauth/` (override with `MP_OAUTH_STORAGE_DIR`)

## 5. Error Handling

```python
from mixpanel_data.exceptions import OAuthError, WorkspaceScopeError

try:
    ws.list_workspaces()
except OAuthError as e:
    print(f"Auth issue: {e.message} (code: {e.code})")
    # Re-authenticate: mp auth login
except WorkspaceScopeError as e:
    print(f"Workspace issue: {e.message}")
    # Set workspace: ws.set_workspace_id(12345)
```
