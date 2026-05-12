# Contract: Configuration Schema

**Spec**: [../spec.md](../spec.md) · **Plan**: [../plan.md](../plan.md) · **Data model**: [../data-model.md](../data-model.md)

This document defines the on-disk schemas for `~/.mp/config.toml` (the new schema, no version label) and the v2 bridge file. Any change to a key, type, or invariant is a breaking change.

---

## 1. `~/.mp/config.toml` schema

### 1.1 Top-level structure

```toml
# ~/.mp/config.toml
# No config_version field. There is only one schema.

[active]
account   = "demo-sa"          # references [accounts.demo-sa]; OPTIONAL
workspace = 3448413            # numeric workspace ID, integer; OPTIONAL
# NOTE: project is NOT in [active] — it lives on the account as default_project.

[accounts.demo-sa]             # at least one [accounts.X] block expected for normal use
type            = "service_account"
region          = "us"
default_project = "3713224"    # the account's home project; required for SA at add-time
username        = "user.x.mp-service-account"
secret          = "..."

[accounts.personal]
type            = "oauth_browser"
region          = "us"
default_project = "9999999"    # populated by `mp account login` after PKCE completes
# (no inline secret; tokens at ~/.mp/accounts/personal/tokens.json)

[accounts.ci]
type            = "oauth_token"
region          = "us"
default_project = "1111111"    # required at add-time for oauth_token
token_env       = "MP_CI_TOKEN"
# OR (mutually exclusive):
# token         = "ey..."

[targets.ecom]                 # OPTIONAL — any number of [targets.X] blocks
account   = "demo-sa"
project   = "3018488"
workspace = 3448414

[settings]                     # OPTIONAL
custom_header = { name = "X-Mixpanel-Cluster", value = "internal-1" }
```

### 1.2 Block specifications

#### `[active]`

| Key | Type | Required | Notes |
|---|---|---|---|
| `account` | string | optional | must reference an existing `[accounts.X]` |
| `workspace` | integer | optional | positive integer |

`[active]` does NOT contain a `project` field. Project lives on the account itself as `default_project` — switching accounts implicitly switches projects (per FR-033). Empty `[active]` is valid; resolution falls through to env vars or fails with `ConfigError("No account configured")`.

#### `[accounts.NAME]` (any number)

NAME constraint: `^[a-zA-Z0-9_-]{1,64}$`

Common keys (all account types):

| Key | Type | Required | Notes |
|---|---|---|---|
| `type` | string | required | `service_account` \| `oauth_browser` \| `oauth_token` |
| `region` | string | required | `us` \| `eu` \| `in` |
| `default_project` | string | optional at the schema level | matches `^\d+$`. Required at add-time for `service_account` and `oauth_token` (the user knows the project up-front). For `oauth_browser`, populated by `mp account login NAME` post-PKCE via `/me`; until that runs, the account has no default project and operations needing one will raise `ConfigError`. |

Type-specific keys:

**`type = "service_account"`**:

| Key | Type | Required |
|---|---|---|
| `username` | string | required |
| `secret` | string | required |

**`type = "oauth_browser"`**: no extra keys beyond the common set; tokens & client info live at `~/.mp/accounts/NAME/`.

**`type = "oauth_token"`**:

| Key | Type | Required |
|---|---|---|
| `token` | string | EITHER |
| `token_env` | string | OR (mutually exclusive) |

Exactly one MUST be set.

#### `[targets.NAME]` (any number)

NAME constraint: `^[a-zA-Z0-9_-]{1,64}$`

| Key | Type | Required | Notes |
|---|---|---|---|
| `account` | string | required | must reference an existing `[accounts.X]` |
| `project` | string | required | matches `^\d+$` |
| `workspace` | integer | optional | positive integer |

#### `[settings]` (optional)

| Key | Type | Required | Notes |
|---|---|---|---|
| `custom_header` | inline table `{name, value}` | optional | applied per-account in memory; never mutates `os.environ` |

Future settings may be added here. `extra="allow"` semantics for forward compatibility.

### 1.3 Schema invariants

- **I1** — Every `[accounts.NAME]` block has `type` + `region`. Type-specific required fields enforced at load.
- **I2** — `[active].account` (if set) MUST reference an existing `[accounts.X]`; otherwise raise `ConfigError` at load.
- **I3** — `[accounts.NAME].default_project` (if set) is a string matching `^\d+$`; otherwise raise `ConfigError` at load. `[active]` does NOT have a `project` field — presence is treated as a legacy marker (see §1.4).
- **I4** — `[active].workspace` (if set) is a positive integer; otherwise raise `ConfigError` at load.
- **I5** — `[targets.NAME]` MUST reference an existing `[accounts.X]` for `account`; otherwise raise `ConfigError` at load (deferred to use-time per FR-049 edge case if needed; choice is "fail at load" per Principle V Explicit Over Implicit).
- **I6** — File mode MUST be `0o600`; parent dir `~/.mp/` MUST be `0o700`. Verified at every read.
- **I7** — No `config_version` key. Presence of `config_version` triggers the legacy-detection branch.
- **I8** — No `default = "X"` key (v1 marker). Presence triggers legacy-detection.
- **I9** — No `[credentials]` or `[projects]` sections (v2 markers). Presence triggers legacy-detection.

### 1.4 Legacy detection  **[REVISED — `mp config convert` descoped; see ../spec.md post-implementation notes]**

The original contract had `ConfigManager.load()` raise `ConfigError` with a
message pointing at `mp config convert`. Under the descope, **the dedicated
legacy-detection helper was deleted**: legacy configs now surface as
Pydantic validation errors (`extra="forbid"` rejects v1/v2 fields like
`config_version`, `default`, `[credentials]`, `[projects]`,
`[accounts.X].project_id`, `[active].project`) at the moment
`ConfigManager.load()` parses the TOML.

The detection rules below are still load-bearing as the de facto rejection
surface — the error just comes from Pydantic's standard model-validation
machinery instead of a hand-written message. Recovery is documented in
`RELEASE_NOTES_0.4.0.md`: `rm ~/.mp/config.toml` + `mp account add ...`.

Detection rules (any one triggers a validation error on load):
- presence of `config_version` field
- presence of `default = "..."` field at root
- presence of `[credentials]` section
- presence of `[projects]` section
- presence of `project_id` inside any `[accounts.X]` block (v1 marker)
- presence of `project` inside the `[active]` table (v3-pre-redesign marker — project moved onto the account as `default_project`)

---

## 2. Bridge file schema (v2)

Path: `~/.claude/mixpanel/auth.json` (default) or any path set via `MP_AUTH_FILE`.

### 2.1 Structure

```json
{
  "version": 2,
  "account": {
    "type": "oauth_browser",
    "name": "personal",
    "region": "us"
  },
  "tokens": {
    "access_token": "ey...",
    "refresh_token": "...",
    "expires_at": "2026-04-22T12:00:00Z",
    "token_type": "Bearer",
    "scope": "..."
  },
  "project": "3713224",
  "workspace": 3448413,
  "headers": {
    "X-Mixpanel-Cluster": "internal-1"
  }
}
```

### 2.2 Top-level keys

| Key | Type | Required | Notes |
|---|---|---|---|
| `version` | integer | required | MUST be `2` |
| `account` | Account discriminated union | required | full record incl. secrets for SA / token for oauth_token |
| `tokens` | OAuthTokens (see data-model §8) | required iff `account.type == "oauth_browser"` | otherwise omitted |
| `project` | string | optional | matches `^\d+$` |
| `workspace` | integer | optional | positive integer |
| `headers` | object | optional | string-to-string map |

### 2.3 Bridge invariants

- **B1** — `version == 2` always; future versions require schema migration plan.
- **B2** — File mode `0o600`; parent dir created with `0o700` if not present.
- **B3** — `account` is a full Account record; secrets live inline by design (Cowork crosses a trust boundary).
- **B4** — `project` and `workspace` are optional; the bridge is a credential courier.
- **B5** — `headers` (if present) attach to the account in memory at resolution time; resolver MUST NOT mutate `os.environ`.

### 2.4 Loading semantics

When `MP_AUTH_FILE` is set, OR the default path exists, OR `mp session --bridge` is invoked, the bridge is loaded and consumed by the resolver as a synthetic config source:

| Axis | Bridge contribution |
|---|---|
| account | Loaded from `bridge.account` (and `bridge.tokens` for `oauth_browser`) |
| project | Loaded from `bridge.project` if present |
| workspace | Loaded from `bridge.workspace` if present |

Per axis priority (FR-017):
- account: env > param > target > **bridge** > `[active].account`
- project: env > param > target > **bridge** > `account.default_project`
- workspace: env > param > target > **bridge** > `[active].workspace`

---

## 3. Conversion mappings (legacy → v3)  **[DESCOPED — see ../spec.md post-implementation notes]**

> **Status: DESCOPED.** The mapping tables below describe the conversion
> contract that `mp config convert` would have implemented. The command
> was descoped under "alpha free to break"; alpha testers wipe
> `~/.mp/config.toml` and re-add accounts via `mp account add ...`
> (recipe in `RELEASE_NOTES_0.4.0.md`). The mappings below are retained
> for historical context only.

`mp config convert` would have applied these mappings:

### 3.1 v1 → v3

| v1 source | v3 destination |
|---|---|
| `default = "X"` | `[active].account = "X"` |
| `[accounts.X]` (with `type = "service_account"` implicit) | `[accounts.X]` (new shape; `type = "service_account"` explicit) |
| `[accounts.X].project_id` | `[accounts.X].default_project` (project lives on the account in v3, not in `[active]`); ALSO emits a `[targets.X]` block for cross-project context preservation |
| `[accounts.X].region` | `[accounts.X].region` (unchanged) |
| `[accounts.X].username` | `[accounts.X].username` (unchanged) |
| `[accounts.X].secret` | `[accounts.X].secret` (unchanged) |

Deduplication: when multiple v1 `[accounts.X]` blocks share identical `(username, secret, region)`, they collapse to a single v3 `[accounts.X]` block (using the lexicographically first old name); the deduplicated account's `default_project` is set from the lexicographically-first source's `project_id`. Each original old name produces a target `[targets.OLD_NAME]` pointing at the deduplicated account + the original `project_id`.

### 3.2 v2 → v3

| v2 source | v3 destination |
|---|---|
| `config_version = 2` | (deleted) |
| `[credentials.X]` | `[accounts.X]` (renamed key; type field unchanged) |
| `[credentials.X].type = "oauth"` | `[accounts.X].type = "oauth_browser"` (renamed value) |
| `[credentials.X].type = "service_account"` | unchanged |
| `[projects.X]` | `[targets.X]` (renamed key; same fields) |
| `[active].credential` | `[active].account` |
| `[active].project_id` | active account's `default_project` (project moved to the account in the redesign) |
| `[active].workspace_id` | `[active].workspace` |
| `[settings].custom_header` | `[settings].custom_header` (unchanged) |

OAuth token files migrate per Research R1 mapping rules (the implementation document for the converter).

### 3.3 Edge cases

- A v2 config that has `[active].credential` referencing a credential without a matching `[projects.X]` alias still converts; the active account's `default_project` is left unset and the user runs `mp account update NAME --project ID` post-conversion (or `mp project use ID`).
- A v1 config with no `default` field promotes the lexicographically-first account name to `[active].account`; that account's `default_project` is set from its old `project_id`.
- A v2 config with `[settings]` containing keys other than `custom_header` (forward-compat) preserves them as-is in the new `[settings]` block.

---

## 4. File path conventions

| Purpose | Path |
|---|---|
| Main config | `~/.mp/config.toml` |
| ~~Legacy archive (post-conversion)~~ — descoped | ~~`~/.mp/config.toml.legacy`~~ — never written |
| Per-account state | `~/.mp/accounts/{name}/` |
| OAuth tokens | `~/.mp/accounts/{name}/tokens.json` |
| OAuth client info | `~/.mp/accounts/{name}/client.json` |
| `/me` cache | `~/.mp/accounts/{name}/me.json` |
| Bridge file (default) | `~/.claude/mixpanel/auth.json` |
| Bridge file (workspace-root alternate) | `<workspace>/mixpanel_auth.json` |

Override paths:
- `MP_CONFIG_PATH` → overrides main config path (existing convention)
- `MP_AUTH_FILE` → overrides bridge file path

---

## 5. Forward compatibility

- `[settings]` block uses `extra="allow"` semantics — future settings can land in patch releases.
- `OAuthTokens` model uses `extra="ignore"` — Mixpanel can add fields to its OAuth response without breaking us.
- `OAuthClientInfo` similarly `extra="ignore"`.
- `MeResponse` and friends already use `extra="allow"` (existing v2 convention).

The `[accounts.X]` and `[targets.X]` blocks use `extra="forbid"` — typos in account/target keys must fail loudly so the user can correct them. This matches the strict validation principle (V).

---

## 6. Security

- **All files** at `~/.mp/` and `~/.mp/accounts/{name}/` are created with mode `0o600`; parent dir `0o700`.
- **Secrets** in TOML appear as plain strings (necessary for the user to paste in setup); reads via `Pydantic SecretStr` immediately wrap them and redact in repr.
- **Bridge file** is `0o600`; the host writes it for the VM to consume. The VM and host share user identity (Cowork is per-user); cross-user leaks are out of scope by design.
- **No secrets in CLI args**: secrets enter via env, stdin, or interactive TTY only. `--secret VALUE` exists but emits a warning to stderr and is documented as discouraged.
- **No secrets in stdout/stderr**: SecretStr redaction in all output formatters.

---

## 7. JSON Schema (informative)

The TOML schema is mirrored as a JSON Schema for documentation purposes (not enforced by code beyond the Pydantic model definitions). See `data-model.md` for the canonical model definitions; this section is informative only.

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "mixpanel_data v3 config",
  "type": "object",
  "additionalProperties": false,
  "properties": {
    "active":   { "$ref": "#/definitions/ActiveSession" },
    "accounts": { "type": "object", "additionalProperties": { "$ref": "#/definitions/Account" } },
    "targets":  { "type": "object", "additionalProperties": { "$ref": "#/definitions/Target" } },
    "settings": { "type": "object" }
  },
  "definitions": { /* see data-model.md */ }
}
```
