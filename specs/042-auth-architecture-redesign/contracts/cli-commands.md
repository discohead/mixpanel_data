# Contract: CLI Commands

**Spec**: [../spec.md](../spec.md) · **Plan**: [../plan.md](../plan.md) · **Python API**: [python-api.md](python-api.md)

This document defines the user-visible CLI command surface. Any change to a verb, flag, or output shape listed here is a breaking change requiring a major version bump.

---

## 1. Top-level structure

```
mp <command-group> <verb> [args] [global-flags]

Identity-related groups:
  mp account     manage authentication accounts
  mp project     manage active project + discovery
  mp workspace   manage active workspace + discovery
  mp target      manage saved (account, project, workspace) triples
  mp session     show the active session

(Existing query/inspect/dashboards/etc. groups unchanged.)

# DESCOPED: `mp config` group (and its sole `mp config convert` command)
# was descoped under "alpha free to break". See spec.md post-implementation
# notes and §8 of this document for the original contract preserved for
# historical context.
```

---

## 2. Global flags (apply to every command)

| Flag | Short | Env var | Purpose |
|---|---|---|---|
| `--account NAME` | `-a` | `MP_ACCOUNT` | Override account for this command |
| `--project ID` | `-p` | `MP_PROJECT_ID` | Override project for this command |
| `--workspace ID` | `-w` | `MP_WORKSPACE_ID` | Override workspace for this command |
| `--target NAME` | — | `MP_TARGET` | Apply target for this command |

**Mutual exclusion**: `--target` MUST NOT combine with `--account`/`--project`/`--workspace`. Combining exits with code 3 ("invalid args") and a clear error.

**Removed flags**:
- `--workspace-id` → renamed to `--workspace`
- `--credential` → use `--account`

---

## 3. `mp account` group

### 3.1 `mp account list`

```
Usage: mp account list [-f FORMAT]

Options:
  -f, --format [json|jsonl|table|csv|plain]   default: table

Output: AccountSummary[]
  - name
  - type (service_account | oauth_browser | oauth_token)
  - region
  - status (ok | needs_login | needs_token | untested)
  - is_active
  - referenced_by_targets (list of target names)
```

**Empty config behavior**: emits a multi-line message listing all three onboarding paths with exact commands (per FR-044). Exit code 0.

### 3.2 `mp account add`

```
Usage: mp account add NAME --type TYPE [options]

Options (all):
  --type [service_account|oauth_browser|oauth_token]   required
  --region [us|eu|in]                                  required (or MP_REGION)
  --project ID                                         see per-type rules below
                                                       (sets the account's default_project)

Options (--type service_account):
  --project ID                                         REQUIRED at add-time (or MP_PROJECT_ID)
  --username USERNAME                                  required (or MP_USERNAME)
  --secret SECRET                                      discouraged inline; prefer:
  --secret-stdin                                       read secret from stdin
  (env var fallback: MP_SECRET)

Options (--type oauth_browser):
  --project ID                                         OPTIONAL at add-time; if omitted,
                                                       backfilled by `mp account login NAME`
                                                       via /me discovery
  (no other extra options; tokens come from `mp account login NAME`)

Options (--type oauth_token):
  --project ID                                         REQUIRED at add-time (or MP_PROJECT_ID)
  --token TOKEN                                        discouraged inline
  --token-env ENV_VAR                                  preferred — name of env var
                                                       (mutually exclusive with --token)

Output: confirmation line + writes [accounts.NAME] block to ~/.mp/config.toml
        First account on a fresh install becomes [active].account automatically (FR-045).
```

**Exit codes**:
- 0 — added successfully
- 3 — invalid args (e.g., missing --username for service_account, missing --project for service_account/oauth_token, both --token and --token-env)
- 1 — name already exists (offers `mp account remove NAME` then retry)

### 3.2a `mp account update`

```
Usage: mp account update NAME [options]

Options (any subset):
  --region [us|eu|in]
  --project ID                                         updates the account's default_project
  --username USERNAME                                  service_account only
  --secret-stdin                                       service_account only
  --token TOKEN                                        oauth_token only
  --token-env ENV_VAR                                  oauth_token only

Effect: in-place update of the named account; only supplied fields are changed.

Output: confirmation listing the changed fields.
```

**Exit codes**:
- 0 — updated
- 3 — invalid args (e.g., field doesn't apply to this account type)
- 4 — name not found

### 3.3 `mp account remove`

```
Usage: mp account remove NAME [--force]

Options:
  --force         remove even if referenced by targets; reports orphaned target names

Output: confirmation. With --force, lists orphaned targets.
```

**Exit codes**:
- 0 — removed successfully
- 4 — name not found
- 1 — referenced by targets and --force not set; lists targets

### 3.4 `mp account use`

```
Usage: mp account use NAME

Effect: writes [active].account = NAME (does NOT modify project/workspace per FR-016)
Output: single-line confirmation
```

**Exit codes**:
- 0 — set successfully
- 4 — name not found

### 3.5 `mp account show`

```
Usage: mp account show [NAME] [-f FORMAT]

Without NAME: shows the active account.
With NAME: shows the named account.

Output: AccountSummary plus extended details (token expiry for OAuth, tokens path, etc.)
```

### 3.6 `mp account test`

```
Usage: mp account test [NAME] [-f FORMAT]

Hits /me with the named (or active) account's credentials and reports success or error.

Output: AccountTestResult
  - account_name
  - ok (bool)
  - user (id, email — when ok)
  - accessible_project_count (when ok)
  - error (when not ok)

Exit codes:
  0 — ok
  2 — auth failed (with details in `error`)
  4 — name not found
```

### 3.7 `mp account login`

```
Usage: mp account login NAME [--no-browser]

Runs the OAuth PKCE browser flow for NAME (must be type=oauth_browser).

Options:
  --no-browser    print the auth URL instead of opening a browser

Effect: writes ~/.mp/accounts/NAME/tokens.json (and client.json on first run)

Exit codes:
  0 — login successful
  2 — login failed or canceled
  3 — NAME is not an oauth_browser account
  4 — NAME not found
```

### 3.8 `mp account logout`

```
Usage: mp account logout NAME

Effect: deletes ~/.mp/accounts/NAME/tokens.json (does NOT remove the account from config).
        Does NOT delete client.json (DCR registration is reusable for the next login).

Exit codes:
  0 — tokens removed (or already absent)
  3 — NAME is not an oauth_browser account
  4 — NAME not found
```

### 3.9 `mp account token`

```
Usage: mp account token [NAME] [-f FORMAT]

Output: current bearer token (for OAuth accounts) or 'N/A' for service accounts

Exit codes:
  0 — token printed
  2 — token unavailable (needs login or env var unset)
```

### 3.10 `mp account export-bridge`

```
Usage: mp account export-bridge --to PATH [--account NAME] [--project ID] [--workspace ID]

Effect: writes a v2 bridge file at PATH (mode 0o600) containing the named (or active) account's full record + optional project/workspace defaults.

Output: confirmation with the bridge file path and a summary of what was included.

Exit codes:
  0 — exported successfully
  2 — auth materials unavailable (e.g., no tokens for oauth_browser)
  3 — invalid args
  4 — account not found
```

### 3.11 `mp account remove-bridge`

```
Usage: mp account remove-bridge [--at PATH]

Effect: deletes the bridge file. Default PATH is ~/.claude/mixpanel/auth.json (or $MP_AUTH_FILE).

Exit codes:
  0 — bridge removed (or already absent)
```

---

## 4. `mp project` group

### 4.1 `mp project list`

```
Usage: mp project list [--remote] [--refresh] [-f FORMAT]

Options:
  --remote     ignore local /me cache; fetch fresh
  --refresh    alias for --remote (provided for ergonomic continuity with `mp account test --refresh`)

Output: list of Project objects (id, name, organization_id, accessible_workspace_count)
        Active project is marked.

Exit codes:
  0 — listed successfully
  2 — auth failure
```

### 4.2 `mp project use`

```
Usage: mp project use ID

Effect: updates the active account's default_project = ID (project lives on the
        account in v3, not in [active]). Equivalent to:
            mp account update <active-account-name> --project ID

Output: confirmation line: "Set default_project for account 'NAME' to 'ID'"
        (plus the project name from /me cache if available)

Exit codes:
  0 — set successfully
  3 — invalid args (ID does not match ^\d+$)
  4 — no active account configured
```

### 4.3 `mp project show`

```
Usage: mp project show [-f FORMAT]

Output: active project details (id, name, organization_id, workspace count)

Exit codes:
  0 — shown
  4 — no active project
```

---

## 5. `mp workspace` group

### 5.1 `mp workspace list`

```
Usage: mp workspace list [--project ID] [--refresh] [-f FORMAT]

Options:
  --project ID    list workspaces in a specific project (else: active project)
  --refresh       bypass workspace cache (per FR-047)

Output: list of WorkspaceRef objects (id, name, is_default).
        Active workspace is marked.
```

### 5.2 `mp workspace use`

```
Usage: mp workspace use ID

Effect: writes [active].workspace = ID (must be a positive integer)

Exit codes:
  0 — set successfully
  3 — invalid args
```

### 5.3 `mp workspace show`

```
Usage: mp workspace show [-f FORMAT]

Output: active workspace details.
        If [active].workspace is unset, output indicates "auto-resolved on first workspace-scoped call".
```

---

## 6. `mp target` group

### 6.1 `mp target list`

```
Usage: mp target list [-f FORMAT]

Output: list of Target objects (name, account, project, workspace?).
```

### 6.2 `mp target add`

```
Usage: mp target add NAME --account ACCOUNT --project ID [--workspace ID]

Effect: writes [targets.NAME] block.

Exit codes:
  0 — added
  1 — name already exists
  3 — invalid args
  4 — referenced account not found
```

### 6.3 `mp target remove`

```
Usage: mp target remove NAME

Effect: deletes [targets.NAME] block.

Exit codes:
  0 — removed (or already absent)
```

### 6.4 `mp target use`

```
Usage: mp target use NAME

Effect: writes [active].account, [active].project, and [active].workspace from the target,
        in a single config save.

Output: single-line confirmation showing all three values.

Exit codes:
  0 — applied
  4 — name not found, or referenced account not found
```

### 6.5 `mp target show`

```
Usage: mp target show NAME [-f FORMAT]

Output: Target object details.
```

---

## 7. `mp session` command

```
Usage: mp session [--bridge] [-f FORMAT]

Without flag: shows resolved session (account + project + workspace).
With --bridge: shows bridge file source if MP_AUTH_FILE is set or default bridge exists.

Output (no --bridge):
  Account:   <name> (<type>, <region>)
  Project:   <name> (<id>) [organization: <org>]
  Workspace: <name> (<id>)  OR  auto-resolved on first workspace-scoped call
  User:      <email>  (from /me cache; "(uncached)" if not yet fetched)

Output (--bridge):
  Bridge:    <path>
  Account:   (as above, source: bridge)
  Project:   (if bridge.project set, else "from config/env")
  Workspace: (similar)
  Headers:   <list>

Exit codes:
  0 — shown
  4 — no resolvable session (no account configured)
```

---

## 8. `mp config` group  **[DESCOPED — see spec.md post-implementation notes]**

> **Status: DESCOPED.** The `mp config` command group was never shipped.
> Legacy v1/v2 configs raise a Pydantic validation error on first load and
> the user wipes `~/.mp/config.toml` and re-adds accounts via
> `mp account add ...`. The migration recipe is in
> [`../../../RELEASE_NOTES_0.4.0.md`](../../../RELEASE_NOTES_0.4.0.md).
> The contract below describes the original intent and is retained for
> historical context only.

### 8.1 `mp config convert`

```
Usage: mp config convert [--dry-run] [-f FORMAT]

Effect: reads ~/.mp/config.toml, detects schema (v1, v2, or v3), and:
  - If v3: exits with friendly "already converted" message; no changes.
  - If v1 or v2: writes the new schema to ~/.mp/config.toml and archives the original
    to ~/.mp/config.toml.legacy. Migrates OAuth token files from
    ~/.mp/oauth/tokens_{region}.json to ~/.mp/accounts/{name}/tokens.json per
    research R1 mapping rules.

Options:
  --dry-run    show what WOULD change without writing anything

Output (table or json):
  - source_schema: v1 | v2 | v3
  - actions:
    - account_renamed: list of {old, new}
    - account_deduplicated: list of {old_names, new_name}
    - target_created: list of target names
    - tokens_moved: list of {from, to}
    - active_set: {account, project, workspace?}
  - warnings: list of human-readable warnings (e.g., orphaned token file)

Exit codes:
  0 — converted successfully (or already on v3)
  1 — conversion failed (with detail)
  2 — auth-related error during token migration
```

---

## 9. Verbs that no longer exist

Per FR-065, these commands MUST NOT exist after Phase 4:

| Old command | Replacement |
|---|---|
| `mp auth list` | `mp account list` |
| `mp auth add NAME ...` | `mp account add NAME --type ...` |
| `mp auth remove NAME` | `mp account remove NAME` |
| `mp auth switch NAME` | `mp account use NAME` |
| `mp auth show [NAME]` | `mp account show [NAME]` |
| `mp auth test [NAME]` | `mp account test [NAME]` |
| `mp auth login` | `mp account login NAME` |
| `mp auth logout` | `mp account logout NAME` |
| `mp auth status` | `mp session` |
| `mp auth token` | `mp account token [NAME]` |
| `mp auth migrate` | (deleted) |
| `mp auth cowork-setup` | `mp account export-bridge` |
| `mp auth cowork-teardown` | `mp account remove-bridge` |
| `mp auth cowork-status` | `mp session --bridge` |
| `mp projects list` | `mp project list` |
| `mp projects switch ID` | `mp project use ID` |
| `mp projects show` | `mp project show` |
| `mp projects refresh` | `mp project list --refresh` |
| `mp projects alias add NAME ...` | `mp target add NAME ...` |
| `mp projects alias remove NAME` | `mp target remove NAME` |
| `mp projects alias list` | `mp target list` |
| `mp workspaces list` | `mp workspace list` |
| `mp workspaces switch ID` | `mp workspace use ID` |
| `mp workspaces show` | `mp workspace show` |
| `mp context show` | `mp session` |
| `mp context switch NAME` | `mp target use NAME` |

Running any of these emits Typer's standard "unknown command" error. There is no compatibility shim.

---

## 10. Output formats

All commands support `-f FORMAT` (or `--format FORMAT`) with one of:

- `json` — pretty-printed JSON (default for read commands that return rich data)
- `jsonl` — JSON Lines (one record per line; default for streaming-shaped commands)
- `table` — Rich table (default for human-facing list commands)
- `csv` — CSV with header row
- `plain` — minimal whitespace-delimited output

Default formats per command are noted above. The `-f` flag overrides the default.

---

## 11. Exit codes

Per the existing convention from the constitution (Principle II: Agent-Native):

| Code | Meaning |
|---|---|
| 0 | success |
| 1 | error (general / config) |
| 2 | auth failure |
| 3 | invalid args |
| 4 | not found (account/target/project) |
| 5 | rate limit |

These are honored consistently across all new commands.

---

## 12. Behavioral contracts

### 12.1 Determinism & idempotency

- Any read command (`list`, `show`, `test`) is idempotent and side-effect-free except for cache I/O.
- Any write command (`add`, `remove`, `use`) is idempotent at the same input.
- ~~`mp config convert` is idempotent~~ — descoped (see §8).

### 12.2 stdout vs stderr

- Data goes to stdout.
- Progress messages, status indicators, warnings, and errors go to stderr.
- This matches Constitution Principle II.

### 12.3 Non-interactive

- No command prompts the user except `mp account add --type service_account` when `--secret`/`--secret-stdin`/`MP_SECRET` are all unset (and even then, the prompt goes to stderr; the secret read is from a TTY only).
- `mp account login` opens a browser (or prints a URL with `--no-browser`) — this is the only command that requires user interaction by design.
