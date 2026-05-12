# Phase 1 Data Model: Authentication Architecture Redesign

**Spec**: [spec.md](spec.md) · **Plan**: [plan.md](plan.md) · **Source design**: [`context/auth-architecture-redesign.md`](../../context/auth-architecture-redesign.md)

This document captures the type system that will live in `src/mixpanel_data/_internal/auth/account.py`, `src/mixpanel_data/_internal/auth/session.py`, and the public re-exports from `src/mixpanel_data/__init__.py` and `src/mixpanel_data/auth.py`. All models are Pydantic v2 unless otherwise noted.

## Type hierarchy at a glance

```
Region                  Literal["us", "eu", "in"]
AccountType             Literal["service_account", "oauth_browser", "oauth_token"]

Account                 Annotated[Union[
                          ServiceAccount,
                          OAuthBrowserAccount,
                          OAuthTokenAccount,
                        ], Field(discriminator="type")]

  ┌── ServiceAccount      type=service_account, name, region, username, secret
  ├── OAuthBrowserAccount type=oauth_browser, name, region
  └── OAuthTokenAccount   type=oauth_token, name, region, (token XOR token_env)

Project                 id: str, name?, organization_id?
WorkspaceRef            id: PositiveInt, name?
Session                 account: Account, project: Project, workspace: WorkspaceRef | None

ActiveSession           account?: str, project?: str, workspace?: int
Target                  name: str, account: str, project: str, workspace?: int

AccountSummary          name, type, region, status (read-only summary)
AccountTestResult       ok: bool, user?, project_count?, error?

OAuthTokens             access_token, refresh_token?, expires_at?, client_id?, scope?
                        (project_id field DROPPED from current model)
OAuthClientInfo         client_id, client_secret?, registration_endpoint?, ...

MeResponse, MeProjectInfo, MeWorkspaceInfo, MeOrgInfo  (unchanged from v2)

BridgeFile              version: 2, account: Account, project?: str, workspace?: int, headers?: dict
```

---

## 1. Region & AccountType

```python
# src/mixpanel_data/_internal/auth/account.py

from typing import Literal

Region = Literal["us", "eu", "in"]
AccountType = Literal["service_account", "oauth_browser", "oauth_token"]
```

**Validation rules**:
- `Region` constrained at type level; pydantic raises on any other value.
- `AccountType` is the discriminator field for the `Account` union; pydantic dispatches construction by exact match.

---

## 2. Account discriminated union

```python
class _AccountBase(BaseModel):
    """Shared base — never instantiated directly."""
    model_config = ConfigDict(frozen=True, extra="forbid")
    name: Annotated[str, Field(min_length=1, max_length=64, pattern=r"^[a-zA-Z0-9_-]+$")]
    region: Region


class ServiceAccount(_AccountBase):
    type: Literal["service_account"] = "service_account"
    username: Annotated[str, Field(min_length=1)]
    secret: SecretStr  # Pydantic redacts in repr/str

    def auth_header(self, *, token_resolver: TokenResolver | None = None) -> str:
        raw = f"{self.username}:{self.secret.get_secret_value()}"
        encoded = base64.b64encode(raw.encode()).decode("ascii")
        return f"Basic {encoded}"

    def is_long_lived(self) -> bool:
        return True


class OAuthBrowserAccount(_AccountBase):
    """OAuth via PKCE browser flow. Tokens stored on disk and refreshed
    automatically. The Account itself carries no secret — secrets live at
    ~/.mp/accounts/{name}/tokens.json."""
    type: Literal["oauth_browser"] = "oauth_browser"

    def auth_header(self, *, token_resolver: TokenResolver) -> str:
        token = token_resolver.get_browser_token(self.name, self.region)
        return f"Bearer {token}"

    def is_long_lived(self) -> bool:
        return True  # refresh-token-driven


class OAuthTokenAccount(_AccountBase):
    """Static OAuth bearer (CI, agents, ephemeral environments).
    Either inline `token` or `token_env` must be set; never both, never neither."""
    type: Literal["oauth_token"] = "oauth_token"
    token: SecretStr | None = None
    token_env: str | None = None

    @model_validator(mode="after")
    def _validate_exactly_one_token_source(self) -> Self:
        has_inline = self.token is not None
        has_env = self.token_env is not None
        if has_inline == has_env:  # both set or neither set
            raise ValueError(
                "OAuthTokenAccount requires exactly one of `token` or `token_env`"
            )
        return self

    def auth_header(self, *, token_resolver: TokenResolver) -> str:
        token = token_resolver.get_static_token(self)
        return f"Bearer {token}"

    def is_long_lived(self) -> bool:
        return False  # caller-controlled; no refresh


Account = Annotated[
    ServiceAccount | OAuthBrowserAccount | OAuthTokenAccount,
    Field(discriminator="type"),
]
```

**Validation rules**:
- `name` matches `^[a-zA-Z0-9_-]+$` and is 1–64 chars; rejects names that would collide with directory traversal characters.
- `region` is one of `us`, `eu`, `in`.
- `secret` and `token` are `SecretStr` — repr shows `'**********'`, never the value.
- `OAuthTokenAccount` enforces XOR(`token`, `token_env`) at construction time.
- Account models are `frozen=True, extra="forbid"` — immutable and reject unknown fields.

**State transitions**:
- `Account` instances are immutable. Switching accounts means swapping the Account reference held by `Workspace` and `Session`.
- Token rotation for `OAuthBrowserAccount` happens in the `TokenResolver` (which writes to `~/.mp/accounts/{name}/tokens.json`); the `Account` itself never changes.

---

## 3. Project & WorkspaceRef

```python
# src/mixpanel_data/_internal/auth/session.py

class Project(BaseModel):
    model_config = ConfigDict(frozen=True)
    id: Annotated[str, Field(min_length=1, pattern=r"^\d+$")]
    name: str | None = None
    organization_id: int | None = None
    timezone: str | None = None  # populated from /me when available


class WorkspaceRef(BaseModel):
    model_config = ConfigDict(frozen=True)
    id: PositiveInt
    name: str | None = None
    is_default: bool | None = None  # populated from /api/.../workspaces/public when known
```

**Validation rules**:
- `Project.id` is a non-empty digit string (Mixpanel returns numeric project IDs as strings).
- `WorkspaceRef.id` is a positive integer (Mixpanel workspace IDs are ints).
- Both are frozen.

**Naming note**: The data type is `WorkspaceRef`, not `Workspace`, to avoid collision with the facade class `mixpanel_data.Workspace`. Public re-export keeps the `WorkspaceRef` name. (Per source design §6.2.)

---

## 4. Session

```python
class Session(BaseModel):
    model_config = ConfigDict(frozen=True)
    account: Account
    project: Project
    workspace: WorkspaceRef | None = None
    headers: dict[str, str] = {}   # global custom headers from [settings].custom_header
                                    # and/or bridge.headers; attached at resolution time;
                                    # never mutates os.environ (FR-014, FR-052)

    @property
    def project_id(self) -> str:
        return self.project.id

    @property
    def workspace_id(self) -> int | None:
        return self.workspace.id if self.workspace else None

    @property
    def region(self) -> Region:
        return self.account.region

    def auth_header(self, *, token_resolver: TokenResolver) -> str:
        return self.account.auth_header(token_resolver=token_resolver)

    def replace(
        self,
        *,
        account: Account | None = None,
        project: Project | None = None,
        workspace: WorkspaceRef | None | _Sentinel = _SENTINEL,
        headers: dict[str, str] | _Sentinel = _SENTINEL,
    ) -> "Session":
        """Pydantic-style copier producing an immutable derived Session.
        
        `workspace` uses a sentinel because `None` is a valid replacement value
        meaning "clear workspace; lazy-resolve on next workspace-scoped call".
        Omitting `workspace=` preserves the current value. `headers` follows
        the same sentinel pattern (`{}` is a valid "clear all headers" value).
        """
        return self.model_copy(update={
            **({"account": account} if account is not None else {}),
            **({"project": project} if project is not None else {}),
            **({"workspace": workspace} if workspace is not _SENTINEL else {}),
            **({"headers": headers} if headers is not _SENTINEL else {}),
        })
```

**Validation rules**:
- `Session` is frozen — once constructed, its fields cannot be reassigned.
- `workspace=None` is valid and means "lazy-resolve on first workspace-scoped API call".
- `headers` defaults to `{}` (no custom headers); populated by the resolver from `[settings].custom_header` (single-header convention) or `bridge.headers` (multi-header dict). `MixpanelAPIClient` injects each entry into outbound requests.
- `replace(...)` produces a *new* Session; original is unchanged.

**State transitions**:
- The `Workspace` facade holds *one* current `Session`. `ws.use(account=A, project=B)` replaces it (atomic swap on auth construction success).
- For parallel iteration, `Session.replace(...)` produces snapshots; each `Workspace(session=snap)` is independent.

---

## 5. ActiveSession (config persistence)

```python
class ActiveSession(BaseModel):
    """Persisted state in `[active]` block of ~/.mp/config.toml.
    All fields optional — env vars or per-command flags can supply each axis."""
    model_config = ConfigDict(extra="forbid")
    account: str | None = None  # references [accounts.NAME]
    project: str | None = None  # numeric Mixpanel project ID, stored as string
    workspace: int | None = None
```

**Validation rules**:
- `account` is the local config name (matches `^[a-zA-Z0-9_-]+$` if non-null, but the model itself doesn't enforce — `ConfigManager` validates referential integrity).
- `project` is a string (matches Mixpanel's wire format).
- `workspace` is an int or None.

**State transitions**:
- Written by `mp account use NAME`, `mp project use ID`, `mp workspace use ID`, `mp target use NAME`, and `Workspace.use(..., persist=True)`.
- Read by the resolver on the config axis (lowest priority — env, params, target, bridge all win first).

---

## 6. Target (config persistence)

```python
class Target(BaseModel):
    """Persisted in [targets.NAME] blocks — a saved (account, project, workspace?) triple."""
    model_config = ConfigDict(extra="forbid")
    name: str  # matches the config block key
    account: str  # references [accounts.NAME]; required
    project: Annotated[str, Field(min_length=1, pattern=r"^\d+$")]
    workspace: int | None = None
```

**Validation rules**:
- `account` and `project` required; `workspace` optional (omit → resolves to project's default workspace at use time).
- Referenced account must exist when `mp target use NAME` runs (verified at load by `ConfigManager`); deletion of an account leaves the target as-is and surfaces a `ConfigError` only if the target is later applied.

**State transitions**:
- Created by `mp target add NAME --account A --project P [--workspace W]`.
- Applied by `mp target use NAME` (writes to `[active]`) or `--target NAME` flag (one-off resolution, no config write).
- Deleted by `mp target remove NAME`.

---

## 7. AccountSummary & AccountTestResult (read-only views)

```python
class AccountSummary(BaseModel):
    """Read-only summary for `mp account list` output."""
    name: str
    type: AccountType
    region: Region
    status: Literal["ok", "needs_login", "needs_token", "untested"] = "untested"
    is_active: bool = False  # True if [active].account == name
    referenced_by_targets: list[str] = []  # target names that reference this account


class AccountTestResult(BaseModel):
    """Result of `mp account test NAME` — captures /me probe outcome."""
    account_name: str
    ok: bool
    user: dict[str, Any] | None = None  # subset of /me response (id, email)
    accessible_project_count: int | None = None
    error: str | None = None


class OAuthLoginResult(BaseModel):
    """Result of `mp.accounts.login(name)` — captures PKCE flow outcome.

    Returned by `mp.accounts.login()` after a successful OAuth browser flow.
    `user` is populated from the immediate /me probe after token issuance.
    """
    model_config = ConfigDict(extra="ignore")
    account_name: str
    user: dict[str, Any] | None = None    # subset of /me response (id, email)
    expires_at: datetime | None = None    # access_token expiry from token response
    tokens_path: Path                      # ~/.mp/accounts/{name}/tokens.json
    client_path: Path                      # ~/.mp/accounts/{name}/client.json
```

**Validation rules**: None beyond Pydantic defaults; these are output structures.

---

## 8. OAuthTokens (modified — drops project_id)

```python
# src/mixpanel_data/_internal/auth/token.py — MODIFIED

class OAuthTokens(BaseModel):
    """Persisted at ~/.mp/accounts/{name}/tokens.json (mode 0o600)."""
    model_config = ConfigDict(extra="ignore")  # forward-compat with future fields
    access_token: SecretStr
    refresh_token: SecretStr | None = None
    expires_at: datetime | None = None
    token_type: Literal["Bearer"] = "Bearer"
    scope: str | None = None
    # project_id field REMOVED — no longer used; conversion script drops it from
    # legacy token files when migrating to ~/.mp/accounts/{name}/tokens.json.
```

**Migration rule**: `mp config convert` reads legacy `~/.mp/oauth/tokens_{region}.json`, drops the `project_id` field, and writes to `~/.mp/accounts/{name}/tokens.json`. The destination account name is determined per Research R1.

---

## 9. OAuthClientInfo (unchanged shape, new path)

```python
# src/mixpanel_data/_internal/auth/client_registration.py — path change only

class OAuthClientInfo(BaseModel):
    """DCR client metadata. Persisted at ~/.mp/accounts/{name}/client.json (0o600)."""
    model_config = ConfigDict(extra="ignore")
    client_id: str
    client_secret: SecretStr | None = None
    registration_endpoint: str | None = None
    issued_at: datetime | None = None
    redirect_uris: list[str] = []
    scopes: list[str] = []
```

**Migration rule**: Legacy `~/.mp/oauth/client_{region}.json` → `~/.mp/accounts/{name}/client.json` alongside the token file (per Research R1).

---

## 10. BridgeFile v2

```python
# src/mixpanel_data/_internal/auth/bridge.py

class BridgeFile(BaseModel):
    """Cowork credential courier. Written 0o600.
    Loaded as a synthetic config source by the resolver."""
    model_config = ConfigDict(extra="forbid")
    version: Literal[2] = 2
    account: Account  # full discriminated union with secrets inline (incl. refresh token for oauth_browser)
    project: str | None = None  # OPTIONAL — bridge is a credential courier, not a project lock
    workspace: int | None = None  # OPTIONAL
    headers: dict[str, str] = {}  # global custom headers (e.g., X-Mixpanel-Cluster)
    tokens: OAuthTokens | None = None  # only present for account.type == "oauth_browser"


def load_bridge(path: Path) -> BridgeFile | None:
    """Returns None if the file does not exist; raises ConfigError if malformed."""
```

**Validation rules**:
- `version` is exactly 2 (literal).
- `account` is a full Account record; if `account.type == "oauth_browser"`, `tokens` MUST also be present.
- `project` and `workspace` optional — bridge no longer locks the Cowork session to a project.
- `headers` map attaches to the account in memory; never mutates `os.environ`.

**State transitions**:
- Written by `mp account export-bridge --to PATH`.
- Read by the resolver when `MP_AUTH_FILE` is set or the default path exists.
- Removed by `mp account remove-bridge [--at PATH]`.

---

## 11. Public re-exports

```python
# src/mixpanel_data/__init__.py — added/removed exports

# ADDED:
from mixpanel_data._internal.auth.account import (
    Account,
    AccountType,
    OAuthBrowserAccount,
    OAuthTokenAccount,
    Region,
    ServiceAccount,
)
from mixpanel_data._internal.auth.session import (
    Project,
    Session,
    WorkspaceRef,
)
from mixpanel_data.types import (
    AccountSummary,
    AccountTestResult,
    Target,
)
from mixpanel_data import accounts, targets, session as session_namespace
# `session` namespace shadows the type — public access is `mp.session.show()` vs `mp.Session(...)`.
# We use `session as session_namespace` internally and let public users access via `mixpanel_data.session`.

# REMOVED:
# from mixpanel_data.auth import Credentials  -- DELETED
# from mixpanel_data.auth import AccountInfo  -- DELETED
# from mixpanel_data.auth import CredentialInfo -- DELETED
# from mixpanel_data.auth import AuthCredential -- DELETED
# from mixpanel_data.auth import CredentialType -- DELETED
# from mixpanel_data.auth import ProjectContext -- DELETED
# from mixpanel_data.auth import ResolvedSession -- DELETED
# from mixpanel_data.auth import ProjectAlias -- DELETED
# from mixpanel_data.auth import MigrationResult -- DELETED
# from mixpanel_data.auth import ActiveContext -- DELETED
# from mixpanel_data.auth import AuthMethod -- DELETED
```

```python
# src/mixpanel_data/auth.py — MODIFIED to be a thin re-export

"""Public auth module — re-exports the unified Account model and related types.

Importable surface:
    from mixpanel_data.auth import Account, ServiceAccount, OAuthBrowserAccount, OAuthTokenAccount
    from mixpanel_data.auth import Project, WorkspaceRef, Session
    from mixpanel_data.auth import AccountSummary, Target
"""
from mixpanel_data._internal.auth.account import (
    Account,
    AccountType,
    OAuthBrowserAccount,
    OAuthTokenAccount,
    Region,
    ServiceAccount,
)
from mixpanel_data._internal.auth.session import (
    Project,
    Session,
    WorkspaceRef,
)
from mixpanel_data.types import (
    AccountSummary,
    Target,
)

__all__ = [
    "Account",
    "AccountSummary",
    "AccountType",
    "OAuthBrowserAccount",
    "OAuthTokenAccount",
    "Project",
    "Region",
    "ServiceAccount",
    "Session",
    "Target",
    "WorkspaceRef",
]
```

---

## 12. Type relationships diagram

```
                                    Workspace (facade)
                                         │
                               holds 1 ──┴─── consumes
                                         │
                                      Session ──────────────┐
                                     /   │   \              │
                                Account Project WorkspaceRef? (lazy)
                                  │
                ┌─────────────────┼─────────────────┐
                │                 │                 │
        ServiceAccount   OAuthBrowserAccount   OAuthTokenAccount
                │                 │                 │
                │             reads/writes      reads from env or
                │           ~/.mp/accounts/      inline token field
                │             {name}/tokens.json
                │                 │
            no on-disk            └─→ TokenResolver dispatches by Account.type
            state needed                       │
                                               └─→ /me cache at
                                                   ~/.mp/accounts/{name}/me.json
```

```
~/.mp/config.toml (single schema)
  ├─ [active]              ──────→ ActiveSession (account?, project?, workspace?)
  ├─ [accounts.NAME] × N   ──────→ Account discriminated union (loaded lazily by resolver)
  ├─ [targets.NAME]  × M   ──────→ Target (account, project, workspace?)
  └─ [settings]            ──────→ global headers, etc.
```

---

## 13. Mapping: old types → new types

| Old type / location | New location | Notes |
|---|---|---|
| `Credentials` (`config.py`) | (deleted) | Replaced by `Session` |
| `AuthMethod` enum | (deleted) | Replaced by `Account.type` Literal |
| `AccountInfo` dataclass | `AccountSummary` (`types.py`) | No `project_id` field |
| `CredentialInfo` dataclass | `AccountSummary` (`types.py`) | Merged with above |
| `AuthCredential` (`auth_credential.py`) | `Account` discriminated union (`_internal/auth/account.py`) | Discriminated union replaces validator-soup model |
| `CredentialType` enum | `AccountType` Literal | Same idea, simpler |
| `ProjectContext` (`auth_credential.py`) | `Project` + `WorkspaceRef` (`_internal/auth/session.py`) | Split apart; no "context" wrapper |
| `ResolvedSession` (`auth_credential.py`) | `Session` (`_internal/auth/session.py`) | Renamed for brevity |
| `ProjectAlias` dataclass | `Target` (`types.py`) | Renamed; same shape |
| `MigrationResult` dataclass | (deleted) | No migrations |
| `ActiveContext` dataclass | `ActiveSession` (internal) | Renamed for clarity |
| `OAuthTokens.project_id` field | (dropped) | Legacy artifact; conversion script drops it |
| `~/.mp/oauth/tokens_{region}.json` | `~/.mp/accounts/{name}/tokens.json` | Per-account directory |
| `~/.mp/oauth/client_{region}.json` | `~/.mp/accounts/{name}/client.json` | Per-account directory |
| `~/.mp/oauth/me_{region}_{name}.json` | `~/.mp/accounts/{name}/me.json` | Per-account directory; region-scoped naming dropped (region is per-account now) |

---

## 14. Invariants

These hold throughout the codebase and are enforced via tests:

- **I1** — Every `Account` instance is frozen and immutable.
- **I2** — `Account` never contains a `project_id` field. (Verified via mypy + a test that introspects fields.)
- **I3** — `Session.workspace == None` is a valid Session; lazy-resolves on first workspace-scoped API call.
- **I4** — `Session.replace(workspace=None)` clears the workspace (re-triggers lazy resolve); omitting `workspace=` preserves it.
- **I5** — `OAuthTokenAccount` always satisfies XOR(`token`, `token_env`); enforced by Pydantic validator.
- **I6** — `~/.mp/accounts/{name}/` is `0o700`; files within are `0o600`. Verified by file stat in storage tests.
- **I7** — `BridgeFile.version == 2` always; bumping requires a new schema migration plan.
- **I8** — `MeService` is invokable for every `Account.type` (verified by parametrized tests).
- **I9** — No `Account` mutation occurs across `Workspace.use(...)` calls; switching produces a new Account reference, never an in-place edit.
- **I10** — `Session.headers` is attached at resolution time from `[settings].custom_header` and/or `bridge.headers`; never read from `os.environ` after resolution. The resolver populates `headers` deterministically from the loaded config + bridge state.
