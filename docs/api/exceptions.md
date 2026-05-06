# Exceptions

All library exceptions inherit from `MixpanelDataError`, enabling callers to catch all library errors with a single except clause.

!!! tip "Explore on DeepWiki"
    🤖 **[Error Handling Guide →](https://deepwiki.com/jaredmcfarland/mixpanel_data/7.4-error-codes-and-exceptions)**

    Ask questions about specific exceptions, error recovery patterns, or debugging strategies.

## Exception Hierarchy

```
MixpanelDataError
├── ConfigError
│   ├── AccountNotFoundError
│   ├── AccountExistsError
│   ├── AccountInUseError
│   └── ProjectNotFoundError
├── APIError
│   ├── AuthenticationError
│   ├── RateLimitError
│   ├── QueryError
│   ├── ServerError
│   └── JQLSyntaxError
├── OAuthError
├── WorkspaceScopeError
└── BusinessContextValidationError
```

## Catching Errors

```python
import mixpanel_data as mp

try:
    ws = mp.Workspace()
    result = ws.segmentation(event="Purchase", from_date="2025-01-01", to_date="2025-01-31")
except mp.AuthenticationError as e:
    print(f"Auth failed: {e.message}")
except mp.RateLimitError as e:
    print(f"Rate limited, retry after {e.retry_after}s")
except mp.OAuthError as e:
    print(f"OAuth error [{e.code}]: {e.message}")
except mp.WorkspaceScopeError as e:
    print(f"Workspace error [{e.code}]: {e.message}")
except mp.AccountInUseError as e:
    print(f"Account '{e.account_name}' referenced by targets: {e.referenced_by}")
except mp.MixpanelDataError as e:
    print(f"Error [{e.code}]: {e.message}")
```

## Base Exception

::: mixpanel_data.MixpanelDataError
    options:
      show_root_heading: true
      show_root_toc_entry: true

## API Exceptions

::: mixpanel_data.APIError
    options:
      show_root_heading: true
      show_root_toc_entry: true

::: mixpanel_data.AuthenticationError
    options:
      show_root_heading: true
      show_root_toc_entry: true

::: mixpanel_data.RateLimitError
    options:
      show_root_heading: true
      show_root_toc_entry: true

::: mixpanel_data.QueryError
    options:
      show_root_heading: true
      show_root_toc_entry: true

::: mixpanel_data.ServerError
    options:
      show_root_heading: true
      show_root_toc_entry: true

::: mixpanel_data.JQLSyntaxError
    options:
      show_root_heading: true
      show_root_toc_entry: true

## Configuration Exceptions

::: mixpanel_data.ConfigError
    options:
      show_root_heading: true
      show_root_toc_entry: true

::: mixpanel_data.AccountNotFoundError
    options:
      show_root_heading: true
      show_root_toc_entry: true

::: mixpanel_data.AccountExistsError
    options:
      show_root_heading: true
      show_root_toc_entry: true

::: mixpanel_data.AccountInUseError
    options:
      show_root_heading: true
      show_root_toc_entry: true

::: mixpanel_data.ProjectNotFoundError
    options:
      show_root_heading: true
      show_root_toc_entry: true

## OAuth Exceptions

Raised during OAuth 2.0 PKCE authentication flows.

| Error Code | Raised When |
|------------|-------------|
| `OAUTH_TOKEN_ERROR` | Token exchange fails |
| `OAUTH_REFRESH_ERROR` | Token refresh fails (transient) |
| `OAUTH_REFRESH_REVOKED` | Refresh token rejected by IdP as `invalid_grant` (re-run `mp account login NAME`) |
| `OAUTH_REGISTRATION_ERROR` | Dynamic client registration fails |
| `OAUTH_TIMEOUT` | Callback server times out waiting for authorization |
| `OAUTH_PORT_ERROR` | Cannot bind to a local port for the callback server |
| `OAUTH_BROWSER_ERROR` | Cannot open the authorization URL in the browser |

::: mixpanel_data.OAuthError
    options:
      show_root_heading: true
      show_root_toc_entry: true

## Workspace Exceptions

Raised when workspace resolution fails for App API endpoints.

| Error Code | Raised When |
|------------|-------------|
| `NO_WORKSPACES` | No workspaces found for the project |
| `AMBIGUOUS_WORKSPACE` | Multiple workspaces found and none is marked as default |
| `WORKSPACE_NOT_FOUND` | Specified workspace ID does not exist |

::: mixpanel_data.WorkspaceScopeError
    options:
      show_root_heading: true
      show_root_toc_entry: true

## Business Context Exceptions

Raised by `Workspace.set_business_context()` when content exceeds the 50,000-character cap. The check runs **before** the HTTP call, so callers fail fast and don't waste a round-trip; the server enforces the same limit and would otherwise return `QueryError` (HTTP 400). See the [Business Context guide](../guide/business-context.md) for usage.

| Error Code | Raised When |
|------------|-------------|
| `BUSINESS_CONTEXT_TOO_LONG` | `len(content) > BUSINESS_CONTEXT_MAX_CHARS` (50,000) |

The `details` dict carries `length` (the actual content length) and `max` (the configured limit) for programmatic recovery.

::: mixpanel_data.BusinessContextValidationError
    options:
      show_root_heading: true
      show_root_toc_entry: true

