# Phase 1 Data Model: Frictionless Auth

**Feature**: 043-frictionless-auth
**Date**: 2026-05-06

The frictionless-auth feature is **schema-additive only**: every new fact lives in existing types. The on-disk representation of `~/.mp/config.toml`, `~/.mp/accounts/{name}/tokens.json`, and `~/.mp/accounts/{name}/me.json` is unchanged. This document describes the in-memory data flow, the new pure functions, and the state-transition table for `mp login`'s persistence handoff.

---

## 1. Reused entities (no changes)

| Entity | Source | Notes |
|--------|--------|-------|
| `Account` (discriminated union) | `_internal/auth/account.py` | `ServiceAccount` / `OAuthBrowserAccount` / `OAuthTokenAccount`. `region` field stays required (FR-009). `default_project` stays optional (FR-012). |
| `Region` | `_internal/auth/account.py` | `Literal["us", "eu", "in"]`. Unchanged. |
| `MeResponse` | `_internal/me.py:163` | Pydantic model. The new code reads `me.organizations` (dict by org_id) and `me.projects` (dict by project_id). |
| `MeProjectInfo` | `_internal/me.py:65` | Already carries `domain: str | None = None` (line 102). The frictionless feature uses this field as the per-project region marker. |
| `MeOrgInfo` | `_internal/me.py` | Already carries `name: str`. The frictionless feature uses this field as the slug source. |
| `OAuthTokens` | `_internal/auth/token.py` | Unchanged; reused for the placeholder-then-rename atomic publish step. |
| `MeService`, `MeCache` | `_internal/me.py` | Unchanged. Reused for `/me` lookup and the resulting cache write. |
| `OAuthFlow` | `_internal/auth/flow.py` | Unchanged. Reused for the PKCE flow. |
| `ConfigManager` | `_internal/config.py` | Unchanged for schema; `add_account()` and `list_accounts()` reused. |
| `AccountSummary` | `types.py` | Unchanged; returned by `accounts.login_unified()`. |

---

## 2. New pure types

Defined in `_internal/auth/region_probe.py` and `_internal/auth/naming.py`. Both modules are pure-functional (no I/O caller-side; the probe takes a `client_factory` callable so the tests can inject a fake).

### 2.1 `RegionProbeResult`

```python
from dataclasses import dataclass
from mixpanel_headless._internal.auth.account import Region


@dataclass(frozen=True)
class RegionProbeResult:
    """Outcome of a sequential region probe.

    Attributes:
        region: The first region whose `/me` returned 200.
        attempts: Ordered list of (region, status_code) tuples for every
            probe attempt up to and including the successful one. Useful
            for telemetry and error context. Always non-empty.
    """

    region: Region
    attempts: list[tuple[Region, int]]
```

### 2.2 `RegionProbeError`

Subclass of `OAuthError` (existing). Raised when no region returns 200. Carries the full `attempts` list so the consolidated error message names every status code.

```python
class RegionProbeError(OAuthError):
    """Raised when no region accepts the credential.

    Attributes:
        attempts: Ordered list of (region, status_code, error_body) for
            all three probe attempts. Used to build the consolidated
            error message ("us: 401 Unauthorized; eu: 401 Unauthorized;
            in: 401 Unauthorized").
    """

    attempts: list[tuple[Region, int, str]]
```

### 2.3 `naming.slugify` and `naming.default_account_name`

Pure functions; no new types. Signatures and exact behavior in [contracts/python-api.md](contracts/python-api.md) §2.

---

## 3. Data flow

### 3.1 `oauth_browser` happy path

```text
user runs `mp login`
      │
      ▼
auth-type detector → oauth_browser
      │
      ▼
region committed: --region | default us
      │
      ▼
PKCE flow (existing OAuthFlow.login)
      │  writes tokens to ~/.mp/accounts/.tmp-{nonce}/tokens.json (placeholder dir)
      ▼
MeService.fetch() against committed region
      │  populates ~/.mp/accounts/.tmp-{nonce}/me.json
      ▼
project_picker(me, --project, MP_PROJECT_ID, isatty) → ProjectId
      │
      ▼
region cross-check: me.projects[picked].domain region == committed region?
      │  on mismatch → cleanup placeholder dir, raise ConfigError
      ▼
naming.default_account_name(me, existing) → final_name
      │  unless --name override
      ▼
os.rename(~/.mp/accounts/.tmp-{nonce}/, ~/.mp/accounts/{final_name}/)
      │
      ▼
ConfigManager.add_account(Account(name=final_name, region=committed,
                                  default_project=picked, type=oauth_browser))
      │
      ▼
ConfigManager.use_account(final_name)
      │
      ▼
print success summary to stdout
```

### 3.2 `service_account` happy path

```text
user runs `mp login --service-account`
      │
      ▼
secret collection: --secret-stdin | MP_SECRET | interactive getpass
      │
      ▼
region_probe.probe_region(client_factory, ServiceAccountCred)
      │  walks us → eu → in until first 200
      ▼
MeService.fetch() reuses the resolved-region cache from the probe
      │
      ▼
project_picker / naming / persist
      │  (same as oauth_browser from this point on)
      ▼
ConfigManager.add_account(ServiceAccount(name=final_name, region=resolved,
                                          default_project=picked, ...))
```

### 3.3 `oauth_token` happy path

```text
user runs `mp login --token-env MY_TOKEN_VAR`
      │
      ▼
token read from os.environ[token_env_name]
      │
      ▼
region_probe.probe_region(client_factory, OAuthTokenCred)
      │
      ▼
project_picker / naming / persist
      │  (same as service_account from this point on)
```

---

## 4. State transitions (re-login idempotency table)

`accounts.login_unified()` resolves whether to create a new account or refresh an existing one by checking if the resolved name (post-derivation) matches an existing entry in `~/.mp/config.toml`.

| Input | Existing account state | Action | Persisted state after |
|-------|-----------------------|--------|----------------------|
| `mp login --name foo` (oauth_browser), `foo` does not exist | none | Run PKCE → /me → persist new account `foo` with `default_project = picked`. Promote `foo` to `[active].account`. | New account `foo` exists with fresh tokens. |
| `mp login` (oauth_browser, derives `acme-corp`), no existing account | none | Same as above with `final_name = acme-corp`. | New account `acme-corp` exists. |
| `mp login --name foo` (oauth_browser), `foo` exists, same user, same region | `foo` exists with `default_project=42` | Run PKCE; refresh `foo`'s `tokens.json` in place. **Do not** modify `default_project`. | `foo` still has `default_project=42` and refreshed tokens. |
| `mp login --name foo --project 99`, `foo` exists | `foo` exists with `default_project=42` | Refresh tokens; print stderr note `note: --project ignored on re-login; use 'mp project use ID' to change`. | `foo` still has `default_project=42`. |
| `mp login --name foo --region eu`, `foo` exists with `region=us` | `foo` exists region=us | Abort with `ConfigError`: `Account 'foo' is bound to region 'us'; cannot change to 'eu' on re-login. Use 'mp account remove foo && mp login --region eu' to re-create.` | Unchanged. |
| `mp login --service-account --name foo`, `foo` exists as oauth_browser | `foo` exists, type=oauth_browser | Abort with `ConfigError`: `Account 'foo' is type 'oauth_browser'; cannot re-login as type 'service_account'. Use 'mp account remove foo && mp login --service-account' to re-create.` | Unchanged. |
| `mp login`, `MP_PROJECT_ID=999` set, `999` not in `/me` projects | none | Print stderr warning, fall through to project picker. | New account with `default_project = whatever picker resolved`. |
| `mp login --project 999`, `999` not in `/me` projects | none | Abort with `ConfigError` listing accessible project IDs. | Unchanged. |

---

## 5. Filesystem state machine (placeholder dir)

```text
state: clean
  │  mp login --type oauth_browser starts
  ▼
state: placeholder-created
  │  ~/.mp/accounts/.tmp-{nonce}/ exists, dir mode 0o700
  │  PKCE writes tokens.json + client.json (mode 0o600)
  ▼
state: tokens-published
  │  /me lookup populates me.json
  │  project picker resolves
  │  naming resolves final_name
  ▼
state: rename-pending
  │  os.rename(~/.mp/accounts/.tmp-{nonce}/, ~/.mp/accounts/{final_name}/)
  │  on rename failure (EEXIST, EACCES) → cleanup + raise
  ▼
state: published
  │  ConfigManager.add_account writes ~/.mp/config.toml
  │  ConfigManager.use_account promotes to [active]
  ▼
state: active

failure paths:
- placeholder-created → clean : on PKCE failure, remove ~/.mp/accounts/.tmp-{nonce}/
- tokens-published → clean : on /me failure, remove ~/.mp/accounts/.tmp-{nonce}/
- tokens-published → clean : on region mismatch, remove ~/.mp/accounts/.tmp-{nonce}/
- rename-pending → tokens-published : on rename failure, leave placeholder for manual recovery
                                       and raise with the placeholder path in the error message
```

The `.tmp-{nonce}` prefix begins with `.` so the placeholder is hidden from `mp account list` (which only enumerates entries listed in `~/.mp/config.toml`). The nonce is 8 hex chars from `secrets.token_hex(4)` to allow concurrent `mp login` invocations from different shells (rare but real).

A startup-time cleanup pass is **not** added in v1: the rare `rename-pending → tokens-published` orphan is left for manual recovery so the user is alerted by the visible disk state. If this becomes a real maintenance burden, add `mp doctor` cleanup as a follow-up.

---

## 6. Validation rules summary

| Rule | Source FR | Enforced in |
|------|-----------|-------------|
| Account name matches `^[a-zA-Z0-9_-]{1,64}$` | (existing 042) | `_AccountBase.name` Pydantic constraint |
| Slug output matches `^[a-z0-9-]{0,32}$` | FR-015 | `naming.slugify` (post-condition tested in PBT) |
| Slug output, when non-empty, satisfies the account-name constraint | FR-015 | `naming.slugify` (PBT: every non-empty output is a valid name) |
| Collision suffix is monotonically increasing | FR-016 | `naming.default_account_name` (PBT: never returns a name ≤ any existing match) |
| Region is one of `us` / `eu` / `in` | FR-009 | `Region` Literal type |
| `--project ID` MUST be in `/me`, otherwise error with project list | FR-010 | `accounts.login_unified` body |
| `MP_PROJECT_ID` MUST fall through with warning if not in `/me` | FR-010 | `accounts.login_unified` body |
| Re-login MUST NOT modify `default_project` | FR-020 | `accounts.login_unified` body (state-transition table §4) |
| Re-login with different region MUST refuse | FR-022 | `accounts.login_unified` body |
| Browser auth region MUST match picked project's `domain` | FR-006 | `accounts.login_unified` body, after `/me` returns |
| Service account 403 on `/me` MUST surface scope hint | FR-014 | `cli/commands/account.py::project_list` (existing 403 → ConfigError mapping extended) |
