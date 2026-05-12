# Contract: Python Public API

**Spec**: [../spec.md](../spec.md) · **Plan**: [../plan.md](../plan.md) · **Data model**: [../data-model.md](../data-model.md)

This document defines the user-visible Python API contracts. Any change to a method signature, return type, or behavior listed here is a breaking change requiring a major version bump.

---

## Top-level imports

```python
import mixpanel_data as mp

# Construction
mp.Workspace                                    # facade class
mp.Account, mp.ServiceAccount,                  # type system
   mp.OAuthBrowserAccount, mp.OAuthTokenAccount,
   mp.Project, mp.WorkspaceRef, mp.Session,
   mp.Region, mp.AccountType,
   mp.AccountSummary, mp.Target, mp.AccountTestResult

# Configuration namespaces
mp.accounts                                     # module: list/add/remove/use/show/test/login/logout
mp.targets                                      # module: list/add/remove/use/show
mp.session                                      # module: show/use
mp.config                                       # module: convert

# Exceptions (re-exported)
mp.AuthenticationError, mp.OAuthError, mp.ConfigError, mp.AccountAccessError
```

---

## 1. `mp.Workspace` construction

```python
class Workspace:
    def __init__(
        self,
        *,
        account: str | None = None,
        project: str | None = None,
        workspace: int | None = None,
        target: str | None = None,
        session: Session | None = None,
    ) -> None: ...
```

**Resolution behavior**:
- With no arguments: resolves the active session via env → config (`[active]`) → bridge file (per FR-017 priority).
- With `account=`/`project=`/`workspace=`: each acts as an explicit param on the corresponding axis (per FR-017).
- With `target=`: applies all three axes from `[targets.NAME]`. **Mutually exclusive** with `account=`/`project=`/`workspace=`; combining raises `ValueError`.
- With `session=`: full bypass — uses the provided Session directly; all other arguments are ignored.

**Raises**:
- `ValueError` — `target=` combined with any of `account=`/`project=`/`workspace=`.
- `ConfigError` — account axis fails to resolve (no env, no param, no target, no bridge, no `[active].account`).
- `ConfigError` — project axis fails to resolve.
- `OAuthError` — auth header construction fails (e.g., expired refresh token).

**Example**:
```python
ws = mp.Workspace()                                       # active session
ws = mp.Workspace(account="demo-sa")                      # override account
ws = mp.Workspace(project="3713224")                      # override project
ws = mp.Workspace(account="demo-sa", project="3713224")   # override both
ws = mp.Workspace(target="ecom")                          # apply target
ws = mp.Workspace(session=my_session)                     # full bypass
```

---

## 2. `Workspace` properties

```python
@property
def account(self) -> Account: ...
@property
def project(self) -> Project: ...
@property
def workspace(self) -> WorkspaceRef | None: ...
@property
def session(self) -> Session: ...
```

**Behavior**:
- All four are read-only; assignment raises `AttributeError`.
- `account`, `project`, and `session` are always non-None for a successfully constructed Workspace.
- `workspace` may be None until the first workspace-scoped API call triggers lazy auto-resolution (per FR-025).

**Removed properties** (per FR-038):
- `current_credential` → use `account`
- `current_project` → use `project`
- `workspace_id` → use `workspace.id if workspace else None`

---

## 3. `Workspace.use()`

```python
def use(
    self,
    *,
    account: str | None = None,
    project: str | None = None,
    workspace: int | None = None,
    target: str | None = None,
    persist: bool = False,
) -> Self: ...
```

**Behavior**:
- Returns `self` for fluent chaining.
- `target=` mutually exclusive with `account=`/`project=`/`workspace=` (raises `ValueError`).
- `account=NAME` without `project=`: re-resolves the project axis through the FR-017 chain (env > param > target > bridge > `account.default_project`); the prior session's project is never carried forward (per FR-033). If no source provides a project, raises `ConfigError`. The workspace axis is also cleared and lazy-resolves on the next workspace-scoped API call.
- `project=ID`: validates the new project ID is non-empty and matches `^\d+$`; does NOT verify access rights (deferred to first API call, where access is naturally checked).
- `workspace=ID`: in-memory field update only.
- `persist=True`: also writes the new state to `~/.mp/config.toml [active]`.
- Preserves the underlying `httpx.Client` instance across all switches.

**Raises**:
- `ValueError` — invalid axis combination, or `account=NAME` not in config, or `target=NAME` not in config.
- `OAuthError` — auth header construction fails for the new account.

**Cost contract** (per spec SC-006/SC-007/SC-008):

| Switch | Cost | Caches cleared |
|---|---|---|
| `ws.use(workspace=N)` | <1 ms (in-memory field update) | none |
| `ws.use(project=P)` | <5 ms (no API call) | resolved-workspace cache, discovery (events/properties) |
| `ws.use(account=A)` | <10 ms (auth header rebuild, atomic swap) | resolved-workspace, discovery, account-scoped /me reference |
| `ws.use(target=T)` | <10 ms (most-expensive of above) | as above |

**Example**:
```python
# Cross-project loop
for p in ws.projects():
    ws.use(project=p.id)
    print(p.id, len(ws.events()))

# Fluent chain
result = ws.use(project="3018488").segmentation("Login", from_date="2026-04-01", to_date="2026-04-21")

# Persist active state
ws.use(account="team", project="8", persist=True)
```

---

## 4. `Workspace` discovery methods

```python
def projects(self, *, refresh: bool = False) -> list[Project]: ...
def workspaces(self, *, project_all: bool = False, refresh: bool = False) -> list[WorkspaceRef]: ...
def me(self, *, refresh: bool = False) -> MeResponse: ...
```

**Behavior**:
- `projects()` returns all accessible projects via `/me`, cached at `~/.mp/accounts/{account.name}/me.json` with 24 h TTL.
- `workspaces()` returns workspaces in the current project; `project_all=True` returns workspaces across all accessible projects.
- `me()` returns the raw `/me` response for advanced use cases.
- `refresh=True` bypasses the cache.

**Raises**:
- `OAuthError` / `AuthenticationError` — auth fails.
- `httpx.HTTPStatusError` — the API rejects the request.

**Removed methods** (per FR-038):
- `discover_projects()` → use `projects()`
- `discover_workspaces()` → use `workspaces()`
- `set_workspace_id()` → use `use(workspace=N)`
- `switch_project()` → use `use(project=P)`
- `switch_workspace()` → use `use(workspace=W)`
- `test_credentials()` (static) → use `mp.accounts.test(NAME)`

---

## 5. `mp.accounts` namespace

```python
# src/mixpanel_data/accounts.py — public namespace module

def list() -> list[AccountSummary]: ...
def add(
    name: str,
    *,
    type: AccountType,
    region: Region,
    default_project: str | None = None,
    username: str | None = None,
    secret: SecretStr | str | None = None,
    token: SecretStr | str | None = None,
    token_env: str | None = None,
) -> AccountSummary: ...
def update(
    name: str,
    *,
    region: Region | None = None,
    default_project: str | None = None,
    username: str | None = None,
    secret: SecretStr | str | None = None,
    token: SecretStr | str | None = None,
    token_env: str | None = None,
) -> AccountSummary: ...
def remove(name: str, *, force: bool = False) -> list[str]: ...   # returns orphaned target names
def use(name: str) -> None: ...                                    # writes [active].account
def show(name: str | None = None) -> AccountSummary: ...           # active if name is None
def test(name: str | None = None) -> AccountTestResult: ...
def login(name: str, *, open_browser: bool = True) -> OAuthLoginResult: ...
def logout(name: str) -> None: ...
def token(name: str | None = None) -> str | None: ...              # current bearer for OAuth accounts
def export_bridge(*, to: Path, account: str | None = None) -> Path: ...
def remove_bridge(*, at: Path | None = None) -> bool: ...
```

**Behavior**:
- All functions accept keyword arguments only; positional args other than `name` are not supported (forward-compatible signatures).
- `add()` validates the `type`-specific fields:
  - `service_account` requires `username` + `secret` + `default_project`.
  - `oauth_browser` requires no extra fields; `default_project` is OPTIONAL at add-time and gets backfilled by `login()` post-PKCE via `/me`.
  - `oauth_token` requires exactly one of `token` / `token_env` + `default_project`.
- `update()` mutates an existing account in place — only the supplied fields are changed. `default_project` is the most common field to update post-creation (e.g., switching the home project for a long-lived service account).
- `remove()` raises `AccountInUseError` (a subclass of `ConfigError`) if the account is referenced by targets and `force=False`. With `force=True`, deletes the account and returns the orphaned target names.
- `use()` writes `[active].account = name` only; does NOT touch `[active].workspace`.
- `test()` hits `/me` and returns structured `AccountTestResult`; never raises (errors captured in `result.error`).
- `remove_bridge()` returns `True` if the bridge file existed and was removed; `False` if no file existed at the resolved path. Idempotent — never raises for absence.

**Raises** (where applicable):
- `ConfigError` — name already exists in `add()`; name not found in `remove`/`use`/`show`/`token`/`logout`/`export_bridge`.
- `AccountInUseError` — see above.
- `OAuthError` — `login()` flow fails.

---

## 6. `mp.targets` namespace

```python
def list() -> list[Target]: ...
def add(
    name: str,
    *,
    account: str,
    project: str,
    workspace: int | None = None,
) -> Target: ...
def remove(name: str) -> None: ...
def use(name: str) -> None: ...                  # writes [active] from target
def show(name: str) -> Target: ...
```

**Behavior**:
- `add()` validates `account` references an existing account.
- `use()` writes all three `[active]` fields from the target in a single config save.
- Removing an account does not auto-remove referenced targets — they remain and surface a `ConfigError` only when applied (per FR-049 edge case).

**Raises**:
- `ConfigError` — name already exists in `add()`; name not found in `remove`/`use`/`show`; referenced account not found in `add()`/`use()`.

---

## 7. `mp.session` namespace

```python
def show() -> ActiveSession: ...                 # current [active] state (account?, workspace?)
def use(
    *,
    account: str | None = None,
    project: str | None = None,
    workspace: int | None = None,
    target: str | None = None,
) -> None: ...                                   # writes account/workspace to [active]; project to active account's default_project
```

**Behavior**:
- `show()` returns the persisted `[active]` block (`account?`, `workspace?` — project is on the account, not in `[active]`). For the resolved Session, construct a Workspace and read `ws.session`.
- `use()` is mutually exclusive: `target=` cannot combine with `account=`/`project=`/`workspace=`.
- `account=` and `workspace=` write to `[active]`; `project=` writes to the active account's `default_project` (since project lives on the account, not in `[active]`). `target=` writes account+workspace to `[active]` and the target's project to that account's `default_project`.
- Each axis is updated independently if provided; unset axes remain unchanged.

**Raises**:
- `ValueError` — illegal arg combination.
- `ConfigError` — referenced name not found.

---

## 7.5 `mp.config` namespace  **[DESCOPED — see ../spec.md post-implementation notes]**

> **Status: DESCOPED.** The `mp.config` Python namespace and its sole
> `convert(...)` entry point were never shipped. The contract below
> describes the original intent and is retained for historical context
> only. The shipped behavior is a hard cutover: legacy configs raise on
> load; users wipe `~/.mp/config.toml` and re-add accounts.

```python
def convert(*, dry_run: bool = False) -> ConversionResult: ...
```

**Behavior**:
- One-shot legacy v1/v2 → v3 conversion as a programmatic entry point (companion to the `mp config convert` CLI command per [cli-commands.md §8.1](cli-commands.md)).
- Idempotent — returns `ConversionResult` with `source_schema="v3"` and empty `actions` when the config is already on v3.
- With `dry_run=True` — computes the conversion result without writing any files.
- Reads from `~/.mp/config.toml` (or `MP_CONFIG_PATH`); writes to the same location with the legacy archived to `~/.mp/config.toml.legacy`.

**Returns**: `ConversionResult` with fields `source_schema`, `actions` (`account_renamed`, `account_deduplicated`, `target_created`, `tokens_moved`, `active_set`), `warnings`.

**Raises**:
- `ConfigError` — malformed source config that cannot be parsed.
- `OSError` — file system errors during write or token migration.

---

## 8. Exception hierarchy

```python
# Existing exceptions remain; only the message text changes per FR-024.

class MixpanelDataError(Exception): ...
class AuthenticationError(MixpanelDataError): ...
class OAuthError(AuthenticationError): ...
class ConfigError(MixpanelDataError): ...
class AccountAccessError(ConfigError): ...        # account doesn't have access to requested project
class AccountInUseError(ConfigError): ...         # NEW — remove() blocked by referenced targets
class WorkspaceScopeError(MixpanelDataError): ... # NEW — lazy resolve fails (project has no workspaces, shouldn't happen)
```

**Removed exceptions** (none — all existing exception types survive per FR-063 spirit).

---

## 9. Behavioral contracts

### 9.1 Idempotency

- `mp.accounts.use(name)` called twice with the same name is a no-op for the second call.
- `mp.targets.use(name)` called twice with the same name is a no-op.
- `Workspace.use(...)` with the same axis values is a no-op (no cache invalidation, no auth rebuild).

### 9.2 Atomicity

- `Workspace.use(account=A)` is atomic: either the new auth header is constructed successfully and the swap completes, or the original auth header is preserved and an exception is raised. The intermediate state (new account reference but old header) never exists.
- `mp.accounts.add(name, ...)` is atomic at the file level: a `ConfigError` mid-write rolls back the TOML.

### 9.3 Determinism

- Every public function produces identical results given identical inputs (env + config snapshot + arguments).
- Caches (`/me`, OAuth tokens) are bypassable via `refresh=True` parameters.

### 9.4 Thread safety

- A single `Workspace` instance is **not** thread-safe (mutable session state).
- For parallel iteration, use `Session.replace(...)` to produce snapshots and construct one Workspace per snapshot. (See spec US7 example.)
- Reads from `mp.accounts.list()` etc. are safe (they touch only the immutable config snapshot loaded from disk).

### 9.5 Backward compatibility

- **None.** This is a clean-break redesign. Code calling `Credentials`, `AuthCredential`, `ProjectContext`, `ResolvedSession`, `ProjectAlias`, etc. **will fail with ImportError**. There is no shim or alias.
- Legacy configs (v1 or v2) **will fail with ConfigError** (Pydantic validation error) at any operation that reads the config. ~~The error message points at `mp config convert`.~~ **[REVISED — `mp config convert` descoped; see ../spec.md post-implementation notes]** Recovery is `rm ~/.mp/config.toml` + `mp account add ...` per `RELEASE_NOTES_0.4.0.md`.

---

## 10. What's removed from the public surface

| Removed | Reason |
|---|---|
| `mixpanel_data.Credentials` | Replaced by `Session` |
| `mixpanel_data.AccountInfo` | Replaced by `AccountSummary` |
| `mixpanel_data.CredentialInfo` | Merged into `AccountSummary` |
| `mixpanel_data.AuthCredential` | Replaced by `Account` discriminated union |
| `mixpanel_data.CredentialType` | Replaced by `AccountType` Literal |
| `mixpanel_data.ProjectContext` | Replaced by `Project` + `WorkspaceRef` |
| `mixpanel_data.ResolvedSession` | Renamed to `Session` |
| `mixpanel_data.ProjectAlias` | Renamed to `Target` |
| `mixpanel_data.MigrationResult` | No more migrations |
| `mixpanel_data.ActiveContext` | Renamed to `ActiveSession` (internal) |
| `mixpanel_data.AuthMethod` | Replaced by `AccountType` |
| `Workspace.discover_projects()` | Renamed to `Workspace.projects()` |
| `Workspace.discover_workspaces()` | Renamed to `Workspace.workspaces()` |
| `Workspace.switch_project()` | Replaced by `Workspace.use(project=)` |
| `Workspace.switch_workspace()` | Replaced by `Workspace.use(workspace=)` |
| `Workspace.set_workspace_id()` | Replaced by `Workspace.use(workspace=)` |
| `Workspace.current_project` | Replaced by `Workspace.project` |
| `Workspace.current_credential` | Replaced by `Workspace.account` |
| `Workspace.workspace_id` | Replaced by `Workspace.workspace.id if Workspace.workspace else None` |
| `Workspace.test_credentials(...)` | Replaced by `mp.accounts.test(NAME)` |
| `Credentials.from_oauth_token(...)` | Replaced by `OAuthTokenAccount(token=...)` constructor |

---

## 11. Versioning

- Public surface defined here is stable across `mixpanel_data 0.4.x` patches.
- Any breaking change requires bump to `0.5.0` (or `1.0.0` after stabilization).
- New optional parameters with sensible defaults can land in patch releases.
