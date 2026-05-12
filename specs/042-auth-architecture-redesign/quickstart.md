# Quickstart: Authentication Architecture Redesign

**Spec**: [spec.md](spec.md) · **Plan**: [plan.md](plan.md) · **Contracts**: [contracts/](contracts/)

This quickstart shows the post-redesign user experience for the most common workflows. Every example is non-interactive and agent-runnable except where browser interaction is explicitly required.

---

## Fresh install (zero-state to first query in 5 commands)

```bash
# 1. Register an OAuth account (recommended) — no secrets in the command
$ mp account add personal --type oauth_browser --region us
Added account 'personal' (oauth_browser, us). Set as active.

# 2. Run the OAuth browser flow
$ mp account login personal
Opening browser...
✓ Authenticated as jared@example.com

# 3. Discover accessible projects
$ mp project list
ID        NAME              ORG       WORKSPACES
3713224   AI Demo           Acme      ✓
3018488   E-Commerce Demo   Acme      ✓
8         P8                Acme      ✓

# 4. Select a project
$ mp project use 3713224
Active project: AI Demo (3713224)

# 5. First query
$ mp query segmentation -e Login --from 2026-04-01 --to 2026-04-21
{ ... results ... }
```

That's it. No `mp auth migrate`, no `--config-version`, no decision between SA and OAuth at install time.

---

## Service account onboarding (CI / scripted)

```bash
# Set the secret via env var (preferred)
$ export MP_SECRET="aQUXhKokwLywLoxE3AxLt0g9dXC2G7bT"
$ mp account add team --type service_account \
    --username "team-mp.292e7c.mp-service-account" \
    --region us
Added account 'team' (service_account, us). Set as active.

# Or read secret from stdin
$ echo "aQUXhKokwLywLoxE3AxLt0g9dXC2G7bT" | \
    mp account add team --type service_account \
      --username "team-mp.292e7c.mp-service-account" \
      --region us \
      --secret-stdin

# Verify
$ mp account test team
{ "account_name": "team", "ok": true, "user": {...}, "accessible_project_count": 7 }

$ mp project list
$ mp project use 3713224
```

---

## Static bearer (CI bot / agent)

```bash
# No persistent state needed — pure env-var path
$ export MP_OAUTH_TOKEN="ey..."
$ export MP_REGION=us
$ export MP_PROJECT_ID=3713224
$ mp query segmentation -e Login --from 2026-04-01 --to 2026-04-21
```

For repeated CI use, register a named account that pulls from env at request time:

```bash
$ mp account add ci --type oauth_token --token-env MP_CI_TOKEN --region us
$ mp account use ci
$ MP_CI_TOKEN=ey... mp query ...
```

---

## Switching between accounts / projects / workspaces

### CLI

```bash
# Switch the active account (persists)
$ mp account use team

# Switch the active project (persists)
$ mp project use 3018488

# Switch the active workspace (persists)
$ mp workspace use 3448414

# One-off override (does NOT modify [active])
$ mp --account team --project 3018488 query segmentation -e Login --from 2026-04-01

# Multi-axis one-off via target
$ mp target add ecom --account team --project 3018488 --workspace 3448414
$ mp --target ecom query segmentation -e Login --from 2026-04-01

# Multi-axis persistent via target
$ mp target use ecom
Active: team → E-Commerce Demo (3018488), workspace 3448414
```

### Python

```python
import mixpanel_data as mp

ws = mp.Workspace()                                # active session

# In-session switching (returns self for chaining)
ws.use(account="team")                              # implicitly clears project
ws.use(project="3018488")
ws.use(workspace=3448414)
ws.use(target="ecom")                               # apply all three at once

# Persist the new state
ws.use(project="3018488", persist=True)             # writes [active].project

# Fluent chain
result = ws.use(project="3018488").segmentation("Login", from_date="2026-04-01", to_date="2026-04-21")
```

---

## Cross-cutting iteration

### Sequential (Python)

```python
import mixpanel_data as mp

ws = mp.Workspace()
for project in ws.projects():
    ws.use(project=project.id)
    print(project.name, len(ws.events()))
```

### Parallel (Python, snapshot mode)

```python
from concurrent.futures import ThreadPoolExecutor
import mixpanel_data as mp

ws = mp.Workspace()
sessions = [
    ws.session.replace(project=mp.Project(id=p.id))
    for p in ws.projects()
]

def event_count(s: mp.Session) -> int:
    return len(mp.Workspace(session=s).events())

with ThreadPoolExecutor(max_workers=4) as pool:
    counts = list(pool.map(event_count, sessions))

for s, c in zip(sessions, counts):
    print(s.project.id, c)
```

### CLI shell loop

```bash
# Sequential cross-project query
$ mp project list -f jsonl | jq -r .id | \
    xargs -I{} mp --project {} query event-counts --events Login --from 2026-04-01

# Parallel via xargs
$ mp project list -f jsonl | jq -r .id | \
    xargs -P 4 -I{} sh -c 'echo "=== {} ==="; mp --project {} query event-counts --events Login --from 2026-04-01'
```

---

## Multi-account workflows

```bash
# Switch credential type without changing project
$ mp account use personal       # OAuth identity
$ mp query segmentation -e Login --from 2026-04-01

$ mp account use team           # SA identity (same project still active)
$ mp query segmentation -e Login --from 2026-04-01

$ mp account use ci             # static bearer
$ MP_CI_TOKEN=ey... mp query segmentation -e Login --from 2026-04-01
```

```python
# Same in Python
import mixpanel_data as mp
ws = mp.Workspace()

for account_name in ["personal", "team", "ci"]:
    ws.use(account=account_name)
    print(account_name, ws.account.region, len(ws.projects()))
```

---

## Inspecting current state

```bash
# Active session summary
$ mp session
Account:   personal (oauth_browser, us)
Project:   AI Demo (3713224)
Workspace: Default (3448413)
User:      jared@example.com

# JSON for agents
$ mp session -f json
{
  "account":   { "name": "personal", "type": "oauth_browser", "region": "us" },
  "project":   { "id": "3713224", "name": "AI Demo", "organization_id": 12 },
  "workspace": { "id": 3448413, "name": "Default", "is_default": true },
  "user":      { "id": 42, "email": "jared@example.com" }
}

# Bridge status (Cowork)
$ mp session --bridge
Bridge:    /Users/.../.claude/mixpanel/auth.json
Account:   personal (oauth_browser, us, source: bridge)
Project:   3713224 (source: bridge)
Workspace: (auto-resolve on first call)
Headers:   X-Mixpanel-Cluster=internal-1
```

---

## Cowork / remote VM setup

```bash
# On the host
$ mp account export-bridge --to ~/.claude/mixpanel/auth.json
Wrote bridge: ~/.claude/mixpanel/auth.json
  Account:  personal (oauth_browser, us)
  Tokens:   included (refresh-capable)
  Project:  not pinned
  Workspace: not pinned
  Headers:  X-Mixpanel-Cluster=internal-1

# In the VM (bridge picked up automatically; or explicit env var)
$ export MP_AUTH_FILE=/host/.claude/mixpanel/auth.json
$ mp project list                # works without further setup
$ mp project use 3713224         # selects project locally; bridge unchanged
$ mp query segmentation ...
```

```bash
# Tear down on the host
$ mp account remove-bridge
Removed bridge: ~/.claude/mixpanel/auth.json
```

---

## Migrating an existing config (alpha tester)  **[REVISED — `mp config convert` descoped]**

> The original plan was to ship `mp config convert` as a one-shot legacy
> → v3 conversion. That command was **descoped** under "alpha free to break"
> (see [`spec.md`](spec.md) post-implementation notes). The shipped
> behavior is a hard cutover: the new schema rejects the old shape on
> load, and the user wipes the file and re-adds accounts.

```bash
# Existing user upgrades to mixpanel_data 0.4.0
$ pip install -U mixpanel_data

# First command surfaces a Pydantic validation error against the new schema
$ mp account list
ConfigError: ~/.mp/config.toml does not match the v3 schema.
  - extra fields not permitted: 'config_version', 'credentials', 'projects'
  - [accounts.X].project_id is no longer a field; project lives on the account
    as `default_project`

# Hard cutover recipe (full walkthrough in RELEASE_NOTES_0.4.0.md)
$ mv ~/.mp/config.toml ~/.mp/config.toml.bak    # keep a backup
$ mp account add personal --type oauth_browser --region us
$ mp account login personal                     # re-PKCE; new tokens at ~/.mp/accounts/personal/

# Verify
$ mp session
Account:   personal (oauth_browser, us)
Project:   AI Demo (3713224)
Workspace: (auto-resolve on first call)
User:      jared@example.com
```

The legacy `~/.mp/oauth/` directory is left untouched (and may be deleted
manually). Service-account migration follows the same pattern: re-add via
`mp account add team --type service_account ... --project ID --region us`.

---

## Common patterns for agents

### Stable JSON output for parsing

```bash
# Agents prefer JSON
$ python auth_manager.py session
{ "schema_version": 1, "state": "ok", "account": {...}, "project": {...}, ... }

# All commands support -f json
$ mp account list -f json
$ mp project list -f json
$ mp target list -f json
```

### State-discriminated agent flow

```python
import json
import subprocess

result = json.loads(subprocess.check_output(["python", "auth_manager.py", "session"]))

match result["state"]:
    case "ok":
        # ready to run queries
        ...
    case "needs_account":
        # suggest the first onboarding command
        suggested = result["next"][0]["command"]
        print(f"To get started: {suggested}")
    case "needs_project":
        # suggest project selection
        print("Account is set. Run `mp project list` to see projects, then `mp project use <id>`.")
    case "error":
        print(f"Error: {result['error']['message']}")
```

---

## Troubleshooting

### "No account configured"

```bash
$ mp project list
ConfigError: No account configured.

Configure one of:
  • Service account:  mp account add <name> --type service_account --username "..." --region us
  • OAuth (browser):  mp account add <name> --type oauth_browser --region us
                      mp account login <name>
  • OAuth (token):    mp account add <name> --type oauth_token --token-env MY_TOKEN --region us
  • Env vars:         export MP_USERNAME=... MP_SECRET=... MP_REGION=us
                  OR: export MP_OAUTH_TOKEN=... MP_REGION=us
```

### "No project selected"

```bash
$ mp query segmentation -e Login --from 2026-04-01
ConfigError: No project selected.

Run `mp project list` to see available projects, then
`mp project use <id>` to select one.
```

### "Account in use"

```bash
$ mp account remove team
ConfigError: Account 'team' is referenced by targets: ['ecom', 'prod']
Use --force to remove anyway (orphans the targets).

$ mp account remove team --force
Removed account 'team'.
Orphaned targets: ['ecom', 'prod']
```

### "OAuth refresh failed"

```bash
$ mp project list
OAuthError: Refresh token expired for account 'personal'.
Run `mp account login personal` to re-authenticate.

$ mp account login personal
Opening browser...
✓ Re-authenticated as jared@example.com
```

### Bridge file present but stale

```bash
$ mp session --bridge
Bridge:    /Users/.../.claude/mixpanel/auth.json
Account:   personal (oauth_browser, us, source: bridge)
WARNING:   Refresh token expired in bridge file. Re-export from host:
             mp account export-bridge --to /Users/.../.claude/mixpanel/auth.json
```

---

## Reference table — verb mapping

| You want to... | Command |
|---|---|
| Add an OAuth identity | `mp account add NAME --type oauth_browser --region us` then `mp account login NAME` |
| Add a service account | `mp account add NAME --type service_account --username "..." --region us` |
| Add a CI bearer | `mp account add NAME --type oauth_token --token-env MP_CI_TOKEN --region us` |
| List your accounts | `mp account list` |
| Switch the active account | `mp account use NAME` |
| Test an account | `mp account test [NAME]` |
| Remove an account | `mp account remove NAME [--force]` |
| Discover projects | `mp project list` |
| Switch the active project | `mp project use ID` |
| Discover workspaces | `mp workspace list` |
| Switch the active workspace | `mp workspace use ID` |
| Save a triple as a target | `mp target add NAME --account A --project P --workspace W` |
| Apply a target | `mp target use NAME` |
| Apply a target for one command | `mp --target NAME <command>` |
| Show current state | `mp session` |
| Show bridge state | `mp session --bridge` |
| Generate a Cowork bridge | `mp account export-bridge --to PATH` |
| Remove a bridge | `mp account remove-bridge [--at PATH]` |
| Migrate legacy config | *(descoped)* — `rm ~/.mp/config.toml` and re-add via `mp account add ...` (see RELEASE_NOTES_0.4.0.md) |
