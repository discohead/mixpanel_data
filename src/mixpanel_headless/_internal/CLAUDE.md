# Internal Implementation

Private infrastructure powering `mixpanel_headless`'s programmable interface to Mixpanel analytics. Do not import directly — use the public API from `mixpanel_headless` (`Workspace`, `mp.accounts`, `mp.targets`, `mp.session`, `Account`, `Session`, etc.).

## Files

| File | Purpose |
|------|---------|
| `config.py` | `ConfigManager` for `~/.mp/config.toml` — single schema (`[accounts.NAME]` / `[active]` / `[targets.NAME]` / `[settings]`); unknown keys are rejected with a clear error |
| `api_client.py` | `MixpanelAPIClient` — HTTP client; takes a `Session`; preserves the underlying `httpx.Client` across in-session axis switches; stamps `User-Agent` and `query_origin` from `client_metadata.py` on every request |
| `client_metadata.py` | `QUERY_ORIGIN` constant + `get_user_agent()` / `set_entry_point()` helpers — single source of truth for outbound client identification |
| `me.py` | `MeService` + per-account `MeCache` (`~/.mp/accounts/{name}/me.json`) |
| `pagination.py` | Cursor-based App API pagination |
| `io_utils.py` | `atomic_write_bytes` — `O_EXCL` + `os.replace` writes with explicit mode bits |
| `auth/` | The auth subsystem — see [`../auth_types.py`](../auth_types.py) for the public re-export and [`../../../context/auth-architecture-redesign.md`](../../../context/auth-architecture-redesign.md) for the design |
| `auth/account.py` | `Account` discriminated union (`ServiceAccount` / `OAuthBrowserAccount` / `OAuthTokenAccount`) + `TokenResolver` protocol |
| `auth/session.py` | `Session`, `Project`, `WorkspaceRef`, `ActiveSession` |
| `auth/resolver.py` | `resolve_session(...)` — single resolver with three independent axes (env → param → target → bridge → config) |
| `auth/token_resolver.py` | `OnDiskTokenResolver` — refreshes browser tokens, reads inline / env-var bearers |
| `auth/flow.py` | OAuth PKCE flow (browser tokens) |
| `auth/pkce.py` | PKCE challenge generation (RFC 7636) |
| `auth/callback_server.py` | Local HTTP callback server for the OAuth redirect |
| `auth/client_registration.py` | Dynamic Client Registration (RFC 7591) |
| `auth/storage.py` | `account_dir` / `ensure_account_dir` (per-account `~/.mp/accounts/{name}/` at `0o700`; files at `0o600`) |
| `auth/token.py` | `OAuthTokens`, `OAuthClientInfo` |
| `auth/bridge.py` | `BridgeFile` v2 schema + `load_bridge` / `export_bridge` / `remove_bridge` (Cowork credential courier) |
| `query/` | Query engine builders and validators (`user_builders.py`, `user_validators.py`) |
| `services/` | Domain services: `DiscoveryService` (events, properties, funnels, cohorts, bookmarks, lexicon), `LiveQueryService` (segmentation, retention, JQL) |

## Auth Resolution

A single function — `auth/resolver.py::resolve_session(...)` — returns a `Session` by walking three independent axes:

| Axis | Priority order |
|------|----------------|
| Account | env (`MP_USERNAME`+`MP_SECRET`+`MP_REGION` for SA; `MP_OAUTH_TOKEN`+`MP_REGION` for static bearer) → explicit param → target → bridge → `[active].account` |
| Project | env (`MP_PROJECT_ID`) → explicit param → target → bridge → `account.default_project` |
| Workspace | env (`MP_WORKSPACE_ID`) → explicit param → target → bridge → `[active].workspace` (may resolve to `None` and lazy-resolve later) |

Service-account env vars win over `MP_OAUTH_TOKEN` when both sets are complete (preserves PR #125 behavior). The resolver is pure-functional: no network I/O, no `os.environ` mutation, deterministic on repeat invocations with identical inputs.

## Error Handling

`MixpanelAPIClient` maps HTTP errors to exceptions:
- 401 → `AuthenticationError`
- 429 → `RateLimitError`
- 400 → `QueryError`
- 5xx → `ServerError`

All exceptions include request/response context for debugging.

## Testing

Components accept dependencies via constructor injection:

```python
config = ConfigManager(_config_path=tmp_path)
session = resolve_session(config=config)
client = MixpanelAPIClient(session=session, http_client=mock_http)
```

For the auth subsystem specifically:
- `tests/unit/test_resolver.py` and `tests/pbt/test_resolver_pbt.py` lock the per-axis priority order
- `tests/integration/test_cross_project_iteration.py` and `test_cross_account_iteration.py` lock `httpx.Client` preservation across `Workspace.use(...)` swaps
- `tests/unit/test_loc_budget.py` is the LoC regression guard for the auth surface
