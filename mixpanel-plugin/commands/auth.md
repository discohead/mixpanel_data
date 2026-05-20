---
name: mixpanel-headless:auth
description: Manage Mixpanel authentication — check session, list/add/use accounts, OAuth login (frictionless `mp login` or two-step), switch projects/workspaces, manage targets, check the Cowork bridge. Use with no arguments for a one-line session summary.
argument-hint: [session|login|account|project|workspace|target|bridge] [...]
---

# Mixpanel Authentication Management

You manage Mixpanel credentials by shelling out to `auth_manager.py`. Every
subcommand emits exactly one JSON object to stdout — parse it and present the
result conversationally.

**Script path:** `python3 ${CLAUDE_PLUGIN_ROOT}/skills/mixpanelyst/scripts/auth_manager.py`

**Schema:** Every response has `schema_version: 1` and a discriminated `state`
of `ok` | `needs_account` | `needs_project` | `error`. Errors emit JSON to
stdout (exit 0) so you can `json.loads` unconditionally — no try/except needed.

## Security Rules (NON-NEGOTIABLE)

- **NEVER ask for secrets (passwords, API secrets) in conversation** — they would be visible in history
- **NEVER pass secrets as CLI arguments** — visible in process list
- For account creation, guide the user to run `! mp account add <name> --type service_account -u <username> -p <project_id> -r <region>` themselves — this prompts for the secret with hidden input

## Routing

Parse `$ARGUMENTS` and route to the appropriate subcommand. With no
arguments, run `session`.

### "login"

Two routing paths — same-machine vs headless. Detect the environment
first:

- **Same-machine** (you can launch the user's browser from the terminal
  the user is in — typical Claude Code CLI setup): run `mp login`
  directly and let the user complete the flow in their browser.
- **Headless** (Claude Cowork sandbox, devcontainer, browserless SSH —
  `$DISPLAY` unset, `$BROWSER` unset, or you know you're in Cowork): use
  the two-shot `--start` / `--finish` flow that emits machine-parseable
  JSON envelopes. The CLI process can't reach the user's host browser
  via loopback, so the flow runs in two CLI invocations bridged by the
  user pasting the redirect URL back into chat.

#### Same-machine path

For first-time setup, the frictionless one-shot path is `mp login`. It
runs the right auth flow for the environment, derives the account name
from `/me`, and pins a default project. Tell the user to run:

```
! mp login
```

Region behavior is auth-type-specific:
- `service_account` and `oauth_token` paths: probes `us → eu → in` and
  uses the first 200.
- `oauth_browser` path (the bare-`mp login` default): commits to `us`
  unless the user passes `--region eu` or `--region in`.

Optional flags they may want:
- `--name NAME` — override the derived account name
- `--region us|eu|in` — set the region explicitly (required for EU / India browser users)
- `--project ID` — skip the project picker
- `--service-account` — force the SA path (requires `MP_USERNAME` + `MP_SECRET` in env)
- `--token-env VAR` — force the static-bearer path (reads token from `$VAR`)
- `--no-browser` — print the authorization URL instead of launching a browser (still requires a TTY for paste-back)

After the user confirms they ran it, verify with `account test`:
`python3 ${CLAUDE_PLUGIN_ROOT}/skills/mixpanelyst/scripts/auth_manager.py account test`

#### Headless path (Claude Cowork, devcontainers, browserless remote)

The two-shot `mp login --start` / `--finish` flow exists for environments
where the loopback OAuth callback can't reach the user's host browser.
You drive the dance directly via `Bash` calls and `AskUserQuestion`:

1. **Start.** Run:
   ```
   ! mp login --start
   ```
   For EU / India users, append `--region eu` or `--region in`. The CLI
   prints a single-line JSON envelope to stdout. Parse it as
   `json.loads(stdout)`.

   Expected shape:
   ```json
   {
     "schema_version": 1,
     "state": "ok",
     "authorize_url": "https://mixpanel.com/oauth/authorize/?...",
     "redirect_uri": "http://localhost:19284/callback",
     "expires_at": <unix-ts>,
     "region": "us",
     "inflight_path": "/home/.../inflight.json"
   }
   ```

2. **Present the URL.** Show `authorize_url` to the user with this
   exact framing:

   > Open this URL in your browser, complete login, then copy the URL
   > from your browser's address bar back here. The page will fail to
   > load with "site can't be reached" — that's expected; copy the URL
   > anyway. Tested on Chrome, Firefox, and Safari.

   Use `AskUserQuestion` to collect the pasted URL.

3. **Finish.** Pass the pasted URL verbatim to `--finish`. Quote it so
   shell metacharacters in the query string don't break the call:
   ```
   ! mp login --finish '<pasted URL>'
   ```

   Expected `state: ok` envelope:
   ```json
   {
     "schema_version": 1,
     "state": "ok",
     "account": {"name": "...", "type": "oauth_browser", "region": "us"},
     "user": {"email": "..."},
     "project": {"id": "...", "name": "..."},
     "project_pick": {
       "auto_picked": true,
       "method": "primary_org_lowest_id",
       "primary_org_name": "...",
       "primary_org_survivor_count": <int>,
       "accessible_project_count": <int>,
       ...
     },
     "next": [
       {"command": "mp project list", "label": "See all accessible projects"},
       {"command": "mp project use <id>", "label": "Switch to a different project"}
     ]
   }
   ```

   Render based on `project_pick.method`:
   - `"explicit"` → "✓ Logged in to project `<id>` as requested."
   - `"sole_survivor"` → "✓ Logged in to project `<name>` (your only
     active project)."
   - `"sole_survivor_filtered"` → "✓ Logged in to project `<name>` —
     the only non-demo, integrated project among your
     `<region_compatible_count>` projects in this region. The others
     are demos or have never received events. Run `mp project list` if
     you want to pick a different one."
   - `"primary_org_lowest_id"` → "✓ Logged in to project `<name>` —
     auto-picked from `<primary_org_name>` (your most-active org;
     `<primary_org_survivor_count>` projects there). Want a different
     one?" If yes, run `mp project list` then `mp project use <id>`.
   - `"fallback_with_unintegrated"` → "✓ Logged in to project `<name>`
     — note: this project hasn't received events. Verify before running
     queries."
   - `"fallback_with_demos"` → "✓ Logged in to project `<name>` — note:
     all your projects are demos. Pass `--project ID` next time if you
     want a specific one."

4. **Handle the `cross_region_only` error.** If `--finish` exits 6 with
   `state: error` and `error.code: NEEDS_REGION_SWITCH`, the user
   authenticated against the wrong region. Show:

   > Your account doesn't have any projects in `<auth_region>`. The
   > `error.details.cross_region_projects` list shows projects in other
   > regions. Want to retry with one of those?

   Then offer to re-run `mp login --start --region eu` (or `--region in`)
   based on the cross-region list.

5. **Recovery.** If `--finish` fails AFTER token exchange (e.g., `/me`
   timed out, name collision), the CLI leaves a `.tmp-*` placeholder dir
   in `~/.mp/accounts/`. Re-run with `--resume <PATH>` to retry the
   publish without re-running PKCE. The error message will include the
   placeholder path.

After the dance completes, verify with `account test`:
`python3 ${CLAUDE_PLUGIN_ROOT}/skills/mixpanelyst/scripts/auth_manager.py account test`

**Inflight TTL is 10 minutes.** If the user takes longer than that to
complete browser auth and paste back, `--finish` returns
`OAUTH_INFLIGHT_EXPIRED`. Re-run `mp login --start` to begin again.

### No arguments or "session"

Run: `python3 ${CLAUDE_PLUGIN_ROOT}/skills/mixpanelyst/scripts/auth_manager.py session`

Switch on `state`:
- **`ok`** — show one line: "Active: `account.name` → project `project.id`"
  (add workspace `workspace.id` if non-null). Mention that
  `/mixpanel-headless:auth account list` and `/mixpanel-headless:auth project list`
  exist if the user wants to switch.
- **`needs_account`** — no account configured. Show the first
  `next[0].command` as the recommended onboarding step (the frictionless
  `mp login` orchestrator); list the alternatives in `next[1]` (explicit
  account add) and `next[2]` (`MP_OAUTH_TOKEN` env triple — best for
  non-interactive contexts like CI or agents).
- **`needs_project`** — account configured but no project pinned. Tell the
  user to run `mp project list` then `mp project use <id>`.
- **`error`** — show `error.message`. If `error.actionable` is true, the
  message names a concrete next command.

### "account list"

Run: `python3 ${CLAUDE_PLUGIN_ROOT}/skills/mixpanelyst/scripts/auth_manager.py account list`

Present `items` as a clean table: `name`, `type`, `region`, `is_active`.
Mark the active account with a star. If `referenced_by_targets` is non-empty
for any account, mention it ("`team` is referenced by targets: `ecom`").

If `items` is empty, show the `next` onboarding hints (same as `needs_account`).

### "account add"

This is a guided wizard. Do NOT run any script that handles secrets.

1. Ask for the **account name** (e.g., "personal", "team", "ci")
2. Ask for the **type** — `oauth_browser` (recommended for laptops),
   `service_account` (long-lived), or `oauth_token` (CI/agents)
3. Ask for the **region** (us, eu, or in — default us)
4. For `service_account`: ask for username and project ID (numeric).
   For `oauth_token`: ask for project ID and the env-var name holding the bearer.
   For `oauth_browser`: project ID is OPTIONAL — `mp account login` will
   backfill it after the PKCE flow.
5. Then instruct the user to run the appropriate command. For service accounts:

```
Now run this command — it will prompt for your service account secret with hidden input:

! mp account add <NAME> --type service_account --username <USERNAME> --project <PROJECT_ID> --region <REGION>
```

For OAuth browser, prefer the one-shot `mp login` (covered by the "login"
branch above):

```
! mp login --name <NAME> --region <REGION>
```

For full control over registration before the PKCE flow, the explicit
two-step is still available:

```
! mp account add <NAME> --type oauth_browser --region <REGION>
! mp account login <NAME>      # opens browser for PKCE flow
```

Replace placeholders with the values collected above. The `!` prefix runs the
command in the user's terminal session.

6. After the user confirms they ran it, verify with `account test`:
   `python3 ${CLAUDE_PLUGIN_ROOT}/skills/mixpanelyst/scripts/auth_manager.py account test <NAME>`
7. Report success or failure based on the `result.ok` field.

### "account use" or "account use <name>"

If a name is provided:
- Run: `python3 ${CLAUDE_PLUGIN_ROOT}/skills/mixpanelyst/scripts/auth_manager.py account use <name>`

If no name:
- First run `account list` to show available accounts
- Ask which to switch to
- Then run `account use` with the chosen name

On `state: ok`, show one line: "Switched to `active.account` (project `active.project`)".
On `state: error`, show `error.message`.

### "account login" or "account login <name>"

Run: `python3 ${CLAUDE_PLUGIN_ROOT}/skills/mixpanelyst/scripts/auth_manager.py account login <name>`

Tell the user a browser window will open for Mixpanel authentication.
Wait for the JSON response.

On `state: ok`: "OAuth login successful! `logged_in_as.user.email`, token
valid until `logged_in_as.expires_at`."
On `state: error`: Show `error.message` and suggest retrying.

### "account test" or "account test <name>"

Run: `python3 ${CLAUDE_PLUGIN_ROOT}/skills/mixpanelyst/scripts/auth_manager.py account test [name]`

The subcommand never raises — `state` is always `ok`. Read `result.ok` to
determine whether the credentials worked:
- `result.ok: true` → "Connected as `result.user.email` ·
  `result.accessible_project_count` accessible projects."
- `result.ok: false` → "Test failed: `result.error`."

### "project list"

Run: `python3 ${CLAUDE_PLUGIN_ROOT}/skills/mixpanelyst/scripts/auth_manager.py project list`

Present `items` as a table: organization, project name, project ID. Mark the
active project (`is_active: true`) with a star. Suggest
`/mixpanel-headless:auth project use <id>` to switch.

### "project use <id>"

If no ID: run `project list` first, then ask which to switch to.

Run: `python3 ${CLAUDE_PLUGIN_ROOT}/skills/mixpanelyst/scripts/auth_manager.py project use <PROJECT_ID>`

On `state: ok`: "Switched to project `active.project`."
On `state: error`: Show `error.message`.

### "workspace list"

Run: `python3 ${CLAUDE_PLUGIN_ROOT}/skills/mixpanelyst/scripts/auth_manager.py workspace list`

Present `items` as a table: workspace ID, name, `is_default`. Mark the
active workspace with a star. Mention the parent project from
`project.name` (`project.id`).

### "workspace use <id>"

Run: `python3 ${CLAUDE_PLUGIN_ROOT}/skills/mixpanelyst/scripts/auth_manager.py workspace use <WORKSPACE_ID>`

On `state: ok`: "Pinned workspace `active.workspace`."

### "target list"

Run: `python3 ${CLAUDE_PLUGIN_ROOT}/skills/mixpanelyst/scripts/auth_manager.py target list`

Targets are saved (account, project, workspace?) triples — named cursor
positions. Present as a table: name, account, project, workspace.

### "target add"

Guided wizard — collect target name, account name, project ID, optional
workspace ID. Then either invoke the auth_manager directly:

```
python3 ${CLAUDE_PLUGIN_ROOT}/skills/mixpanelyst/scripts/auth_manager.py target add <NAME> --account <ACCT> --project <PROJ> [--workspace <WS>]
```

Or guide the user to `! mp target add <NAME> --account <ACCT> --project <PROJ> [--workspace <WS>]`.

### "target use <name>"

Run: `python3 ${CLAUDE_PLUGIN_ROOT}/skills/mixpanelyst/scripts/auth_manager.py target use <name>`

Applies all three axes (`account` / `project` / `workspace`) to `[active]`
in a single atomic config write.

### "bridge status"

Run: `python3 ${CLAUDE_PLUGIN_ROOT}/skills/mixpanelyst/scripts/auth_manager.py bridge status`

Parse the JSON:
- If `bridge` is null → "No Cowork bridge file found. To create one, run
  `mp account export-bridge --to <path>` on your host machine."
- If `bridge` is non-null → show `bridge.path`, `bridge.account.name`
  (`bridge.account.type`), pinned `bridge.project` / `bridge.workspace` if set,
  and any custom `bridge.headers`.

## Bearer-token env vars (`MP_OAUTH_TOKEN`)

For non-interactive contexts (CI, agents, ephemeral environments) where the
PKCE browser flow isn't viable, set:

```
export MP_OAUTH_TOKEN=<bearer-token>
export MP_PROJECT_ID=<project-id>
export MP_REGION=<us|eu|in>
```

The library builds an `Authorization: Bearer <token>` header for every
Mixpanel endpoint. The full service-account env-var set (`MP_USERNAME` +
`MP_SECRET` + `MP_PROJECT_ID` + `MP_REGION`) takes precedence when both
sets are complete, so this is safe to add to a shell that already exports
the service-account vars.

## Presentation Style

- Be concise — show status in 1–2 lines, not a wall of JSON
- Use tables for lists of accounts, projects, workspaces, targets
- Always suggest a next action when something is missing
- On errors, show `error.message` verbatim — it names the fix
