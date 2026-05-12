# Contract: Plugin `auth_manager.py` JSON Output

**Spec**: [../spec.md](../spec.md) · **Plan**: [../plan.md](../plan.md) · **Research**: [../research.md](../research.md) (R4)

This document defines the stable JSON output contract for `mixpanel-plugin/skills/mixpanelyst/scripts/auth_manager.py`. Changes to top-level shape require a `schema_version` bump; changes to nested shape are additive only (Pydantic `extra="ignore"` semantics on the consumer side).

---

## 1. Subcommand inventory

```
python auth_manager.py session                     # session state
python auth_manager.py account list                # AccountSummary[]
python auth_manager.py account add NAME ...        # add (JSON stdin or args)
python auth_manager.py account use NAME            # set active account
python auth_manager.py account login NAME          # OAuth PKCE
python auth_manager.py account test NAME           # /me probe
python auth_manager.py project list [--remote]     # Project[]
python auth_manager.py project use ID              # set active project
python auth_manager.py workspace list              # WorkspaceRef[]
python auth_manager.py workspace use ID            # set active workspace
python auth_manager.py target list                 # Target[]
python auth_manager.py target add NAME ...         # add
python auth_manager.py target use NAME             # apply target
python auth_manager.py bridge status               # bridge file present?
```

Every subcommand emits exactly one JSON object to stdout. Errors emit JSON to stdout (not stderr), with `state == "error"` per the convention below.

---

## 2. `session` subcommand contract

### 2.1 State: ok (account + project + (workspace OR auto-resolved))

```json
{
  "schema_version": 1,
  "state": "ok",
  "account": {
    "name": "personal",
    "type": "oauth_browser",
    "region": "us"
  },
  "project": {
    "id": "3713224",
    "name": "AI Demo",
    "organization_id": 12
  },
  "workspace": {
    "id": 3448413,
    "name": "Default",
    "is_default": true
  },
  "user": {
    "id": 42,
    "email": "jared@example.com"
  },
  "source": {
    "account": "config",
    "project": "config",
    "workspace": "config"
  }
}
```

- `workspace` MAY be `null` if `[active].workspace` is unset and no workspace-scoped call has triggered lazy resolution; in that case `state` remains `"ok"`.
- `user` MAY be `null` if no `/me` cache exists (e.g., right after `mp account add` and before any `/me` call).
- `source` documents which axis came from where. Values: `"env"` | `"param"` | `"target"` | `"bridge"` | `"config"`.

### 2.2 State: needs_account

```json
{
  "schema_version": 1,
  "state": "needs_account",
  "next": [
    { "command": "mp account add personal --type oauth_browser --region us", "label": "OAuth (recommended)" },
    { "command": "mp account add team --type service_account --username '<service-account-username>' --region us", "label": "Service account" },
    { "command": "export MP_OAUTH_TOKEN=<bearer> MP_REGION=us MP_PROJECT_ID=<id>", "label": "Static bearer (CI)" }
  ]
}
```

### 2.3 State: needs_project

```json
{
  "schema_version": 1,
  "state": "needs_project",
  "account": {
    "name": "personal",
    "type": "oauth_browser",
    "region": "us"
  },
  "next": [
    { "command": "mp project list", "label": "List accessible projects" },
    { "command": "mp project use <id>", "label": "Select a project" }
  ]
}
```

### 2.4 State: error

```json
{
  "schema_version": 1,
  "state": "error",
  "error": {
    "code": "OAuthError",
    "message": "Refresh token expired; please run `mp account login personal`",
    "actionable": true
  }
}
```

`error.code` matches the exception class name from the public hierarchy (`AuthenticationError`, `OAuthError`, `ConfigError`, etc.). `actionable: true` means the message names a concrete next command for the user.

---

## 3. List subcommand contracts

### 3.1 `account list`

```json
{
  "schema_version": 1,
  "state": "ok",
  "items": [
    {
      "name": "personal",
      "type": "oauth_browser",
      "region": "us",
      "status": "ok",
      "is_active": true,
      "referenced_by_targets": []
    },
    {
      "name": "team",
      "type": "service_account",
      "region": "us",
      "status": "untested",
      "is_active": false,
      "referenced_by_targets": ["ecom"]
    }
  ]
}
```

`items` is always present (may be empty). Empty config returns `items: []` AND a `next` array suggesting onboarding (mirroring `state: needs_account`).

### 3.2 `project list`

```json
{
  "schema_version": 1,
  "state": "ok",
  "items": [
    { "id": "3713224", "name": "AI Demo", "organization_id": 12, "is_active": true },
    { "id": "3018488", "name": "E-Commerce Demo", "organization_id": 12, "is_active": false }
  ]
}
```

### 3.3 `workspace list`

```json
{
  "schema_version": 1,
  "state": "ok",
  "project": { "id": "3713224", "name": "AI Demo" },
  "items": [
    { "id": 3448413, "name": "Default", "is_default": true, "is_active": true },
    { "id": 3448414, "name": "Staging", "is_default": false, "is_active": false }
  ]
}
```

### 3.4 `target list`

```json
{
  "schema_version": 1,
  "state": "ok",
  "items": [
    { "name": "ecom", "account": "team", "project": "3018488", "workspace": 3448414 },
    { "name": "prod", "account": "personal", "project": "8", "workspace": null }
  ]
}
```

---

## 4. Mutation subcommand contracts

### 4.1 `account add`

Input: NAME via positional arg + flags, OR full JSON record via stdin (`--from-stdin`).

```json
{
  "schema_version": 1,
  "state": "ok",
  "added": {
    "name": "team",
    "type": "service_account",
    "region": "us",
    "is_active": true   // because first account on fresh install
  }
}
```

### 4.2 `account remove`

```json
{
  "schema_version": 1,
  "state": "ok",
  "removed": "team",
  "orphaned_targets": ["ecom"]   // empty array if none
}
```

### 4.3 `account use` / `project use` / `workspace use` / `target use`

```json
{
  "schema_version": 1,
  "state": "ok",
  "active": {
    "account": "team",
    "project": "3018488",
    "workspace": 3448414
  }
}
```

For `account use`, only `active.account` reflects the change; the other fields show their current values (which may have been unchanged). Same for `project use` and `workspace use`. For `target use`, all three reflect the target's values.

### 4.4 `account login`

```json
{
  "schema_version": 1,
  "state": "ok",
  "logged_in_as": {
    "name": "personal",
    "user": { "id": 42, "email": "jared@example.com" },
    "expires_at": "2026-04-22T12:00:00Z"
  }
}
```

### 4.5 `account test`

```json
{
  "schema_version": 1,
  "state": "ok",
  "result": {
    "account_name": "team",
    "ok": true,
    "user": { "id": 99, "email": "team@acme.com" },
    "accessible_project_count": 7
  }
}
```

For failure:

```json
{
  "schema_version": 1,
  "state": "ok",
  "result": {
    "account_name": "team",
    "ok": false,
    "error": "401 Unauthorized — service account secret invalid"
  }
}
```

(Note: the *test* succeeded in producing a result; the *credentials* failed. Top-level `state: ok` indicates the subcommand itself worked.)

---

## 5. `bridge status` subcommand

### 5.1 Bridge present

```json
{
  "schema_version": 1,
  "state": "ok",
  "bridge": {
    "path": "/Users/.../.claude/mixpanel/auth.json",
    "version": 2,
    "account": { "name": "personal", "type": "oauth_browser", "region": "us" },
    "project": "3713224",
    "workspace": null,
    "headers": { "X-Mixpanel-Cluster": "internal-1" }
  }
}
```

### 5.2 Bridge absent

```json
{
  "schema_version": 1,
  "state": "ok",
  "bridge": null
}
```

---

## 6. Stable shape invariants

- **P1** — Every response has `schema_version: 1` at the top level.
- **P2** — Every response has `state` at the top level: one of `"ok"` | `"needs_account"` | `"needs_project"` | `"error"`.
- **P3** — Every error response has `error: {code, message, actionable}`.
- **P4** — List responses always have `items: [...]` (possibly empty).
- **P5** — Account objects always have `{name, type, region}`. Other fields (`status`, `is_active`, `referenced_by_targets`) MAY be omitted when irrelevant to the subcommand context.
- **P6** — Project objects always have `{id}`. Other fields (`name`, `organization_id`, `is_active`, `is_default`) MAY be omitted when not yet known.
- **P7** — Workspace objects always have `{id}` (when non-null). `is_default`, `is_active`, `name` MAY be omitted.
- **P8** — `null` is distinguished from omitted: `null` means "explicitly known to be absent"; omitted means "not yet computed". Consumers should treat both as "not available now".
- **P9** — All timestamps are ISO 8601 in UTC with explicit `Z` or `+00:00` offset.
- **P10** — Secret material never appears in any output. Tokens, refresh tokens, secrets — all redacted.

---

## 7. Versioning

- `schema_version: 1` is the initial version shipping with `mixpanel_data 0.4.0` and plugin `5.0.0`.
- Additive changes (new optional fields) do NOT bump the schema version.
- Breaking changes (new top-level state, removed fields, changed semantics) bump to `schema_version: 2` with parallel-version support in plugin code for one minor release before deprecating v1.

---

## 8. Consumer guidance for the `/mixpanel-data:auth` slash command

The slash command's handler is a thin wrapper:

```python
result = json.loads(subprocess.check_output(["python", "auth_manager.py", "session"]))
match result["state"]:
    case "ok":
        return f"Active: {result['account']['name']} → {result['project']['name']} ({result['project']['id']})"
    case "needs_account":
        return f"No account configured. Try: {result['next'][0]['command']}"
    case "needs_project":
        return f"Account: {result['account']['name']}. Try: mp project list"
    case "error":
        return f"Error: {result['error']['message']}"
```

No `if version >= 2` branches. No secret handling in conversation. The slash command produces a 1–2 line summary plus a single suggested next action.

---

## 9. Test surface

Per FR-071, `tests/integration/test_plugin_auth_manager.py` runs each subcommand via subprocess against fixture configs. Each test:

1. Sets up a fixture config (e.g., empty, single-account, multi-target).
2. Runs `python auth_manager.py <subcommand>`.
3. Parses stdout as JSON.
4. Asserts the response shape matches the contract above (using a JSON Schema validator or model parser).
5. Asserts side effects on the config file match expectations.

Snapshot fixtures live in `tests/fixtures/auth_manager_outputs/` (one `.json` per (subcommand, fixture-config) pair). Test failures show diff between actual and snapshot.
