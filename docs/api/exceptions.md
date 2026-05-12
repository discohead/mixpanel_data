# Exceptions

All library exceptions inherit from `MixpanelHeadlessError`, enabling callers to catch all library errors with a single except clause.

!!! tip "Explore on DeepWiki"
    🤖 **[Error Handling Guide →](https://deepwiki.com/mixpanel/mixpanel-headless/7.4-error-codes-and-exceptions)**

    Ask questions about specific exceptions, error recovery patterns, or debugging strategies.

## Exception Hierarchy

```
MixpanelHeadlessError
├── ConfigError
│   ├── AccountNotFoundError
│   ├── AccountExistsError
│   ├── AccountInUseError
│   ├── InvalidArgumentError
│   └── ProjectNotFoundError
├── APIError
│   ├── AuthenticationError
│   ├── RateLimitError
│   ├── QueryError
│   ├── ServerError
│   └── JQLSyntaxError
├── OAuthError
│   └── RegionProbeError
│       └── RegionProbeNetworkError
├── WorkspaceScopeError
└── BusinessContextValidationError
```

## Catching Errors

```python
import mixpanel_headless as mp

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
except mp.MixpanelHeadlessError as e:
    print(f"Error [{e.code}]: {e.message}")
```

## Base Exception

::: mixpanel_headless.MixpanelHeadlessError
    options:
      show_root_heading: true
      show_root_toc_entry: true

## API Exceptions

::: mixpanel_headless.APIError
    options:
      show_root_heading: true
      show_root_toc_entry: true

::: mixpanel_headless.AuthenticationError
    options:
      show_root_heading: true
      show_root_toc_entry: true

::: mixpanel_headless.RateLimitError
    options:
      show_root_heading: true
      show_root_toc_entry: true

::: mixpanel_headless.QueryError
    options:
      show_root_heading: true
      show_root_toc_entry: true

::: mixpanel_headless.ServerError
    options:
      show_root_heading: true
      show_root_toc_entry: true

::: mixpanel_headless.JQLSyntaxError
    options:
      show_root_heading: true
      show_root_toc_entry: true

## Configuration Exceptions

::: mixpanel_headless.ConfigError
    options:
      show_root_heading: true
      show_root_toc_entry: true

::: mixpanel_headless.AccountNotFoundError
    options:
      show_root_heading: true
      show_root_toc_entry: true

::: mixpanel_headless.AccountExistsError
    options:
      show_root_heading: true
      show_root_toc_entry: true

::: mixpanel_headless.AccountInUseError
    options:
      show_root_heading: true
      show_root_toc_entry: true

::: mixpanel_headless.ProjectNotFoundError
    options:
      show_root_heading: true
      show_root_toc_entry: true

### InvalidArgumentError

Raised by `accounts.login_unified` (and the CLI's `mp login`) when a public-API call combines mutually incompatible arguments. Subclass of `ConfigError`. The CLI maps this to exit code 3 (`INVALID_ARGS`) instead of the generic 1.

| `violation` | Raised When |
|-------------|-------------|
| `mutually_exclusive` | `--service-account` + `--token-env` (or equivalent kwargs) |
| `no_browser_misuse` | `--no-browser` against a non-browser auth type |
| `secret_stdin_misuse` | `--secret-stdin` against a non-SA auth type |

The `details` dict carries `violation` and (when detection ran) `detected_auth_type`. Pattern-match by class so non-CLI callers (Cowork's `auth_manager.py`, JSON consumers) can dispatch without parsing the human message.

::: mixpanel_headless.InvalidArgumentError
    options:
      show_root_heading: true
      show_root_toc_entry: true

## OAuth Exceptions

Raised during OAuth 2.0 PKCE authentication flows and the `mp login` region probe.

| Error Code | Raised When |
|------------|-------------|
| `OAUTH_TOKEN_ERROR` | Token exchange fails |
| `OAUTH_REFRESH_ERROR` | Token refresh fails (transient) |
| `OAUTH_REFRESH_REVOKED` | Refresh token rejected by IdP as `invalid_grant` (re-run `mp login --name NAME`) |
| `OAUTH_REGISTRATION_ERROR` | Dynamic client registration fails |
| `OAUTH_TIMEOUT` | Callback server times out waiting for authorization |
| `OAUTH_PORT_ERROR` | Cannot bind to a local port for the callback server |
| `OAUTH_BROWSER_ERROR` | Cannot open the authorization URL in the browser |
| `OAUTH_REGION_PROBE_FAILED` | `mp login` probed every region and none accepted the credential — see `RegionProbeError` below |
| `OAUTH_NETWORK_UNREACHABLE` | Every region probe failed at the network layer (DNS / TLS / connect refused) — see `RegionProbeNetworkError` below |

::: mixpanel_headless.OAuthError
    options:
      show_root_heading: true
      show_root_toc_entry: true

### RegionProbeError

Raised by `mp login` (and `accounts.login_unified`) when the `us → eu → in` region probe fails for every region. Subclass of `OAuthError`. The `attempts` attribute carries the full `(region, status_code, error_body)` list; status `0` indicates a network-layer failure (DNS / TLS / connect refused) — those cases raise `RegionProbeNetworkError` (subclass) so the CLI can render a different remediation hint.

```python
import mixpanel_headless as mp

try:
    mp.accounts.login_unified()
except mp.RegionProbeNetworkError as exc:
    print("Could not reach any Mixpanel region. Check connectivity.")
    for region, status, body in exc.attempts:
        print(f"  {region}: {body}")
except mp.RegionProbeError as exc:
    print("Credential not valid in any region.")
    for region, status, body in exc.attempts:
        print(f"  {region}: {status} {body}")
```

::: mixpanel_headless.RegionProbeError
    options:
      show_root_heading: true
      show_root_toc_entry: true

::: mixpanel_headless.RegionProbeNetworkError
    options:
      show_root_heading: true
      show_root_toc_entry: true

## Workspace / Organization Scope Exceptions

Raised when an auth-axis identifier (workspace or organization) cannot be resolved during App API requests.

| Error Code | Raised When |
|------------|-------------|
| `NO_WORKSPACES` | No workspaces found for the project |
| `AMBIGUOUS_WORKSPACE` | Multiple workspaces found and none is marked as default |
| `WORKSPACE_NOT_FOUND` | Specified workspace ID does not exist |
| `ORGANIZATION_AMBIGUOUS` | An org-scoped business-context call could not auto-resolve the organization (active project absent from `/me` AND >1 accessible organization). `details` carries `project_id` and `available_organizations`. Pass `organization_id=N` explicitly to bypass auto-resolution. |

::: mixpanel_headless.WorkspaceScopeError
    options:
      show_root_heading: true
      show_root_toc_entry: true

## Business Context Exceptions

Raised by `Workspace.set_business_context()` when content exceeds the 50,000-character cap. The check runs **before** the HTTP call, so callers fail fast and don't waste a round-trip; the server enforces the same limit and would otherwise return `QueryError` (HTTP 400). See the [Business Context guide](../guide/business-context.md) for usage.

| Error Code | Raised When |
|------------|-------------|
| `BUSINESS_CONTEXT_TOO_LONG` | `len(content) > BUSINESS_CONTEXT_MAX_CHARS` (50,000) |

The `details` dict carries `length` (the actual content length) and `max` (the configured limit) for programmatic recovery.

::: mixpanel_headless.BusinessContextValidationError
    options:
      show_root_heading: true
      show_root_toc_entry: true

