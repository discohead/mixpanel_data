---
name: mixpanel-headless:setup
description: This skill installs mixpanel_headless, pandas, numpy, matplotlib, seaborn, networkx, anytree, scipy (and pyarrow on Python 3.11+), then verifies Mixpanel credentials. It should be invoked when setting up a new environment for Mixpanel data analysis, when dependencies are missing, or when configuring service account or OAuth credentials for the first time.
disable-model-invocation: true
allowed-tools: Bash
---

# mixpanel-headless — Setup

Install dependencies and verify credentials for CodeMode analytics.

## Run Setup

```bash
bash ${CLAUDE_SKILL_DIR}/scripts/setup.sh
```

This will:
1. Verify Python 3.10+ is available
2. Install `mixpanel_headless`, `pandas`, `numpy`, `matplotlib`, `seaborn`, `networkx>=3.0`, `anytree>=2.8.0`, `scipy`, and `pyarrow>=17.0` on Python 3.11+ (tries uv, pip in order)
3. Verify all packages import successfully (including pyarrow on 3.11+, networkx, anytree, and scipy)
4. Check for configured Mixpanel credentials (single schema — Account → Project → Workspace)

## Check Credentials

After installation, check the active session:

```bash
python3 ${CLAUDE_SKILL_DIR}/../mixpanelyst/scripts/auth_manager.py session
```

Parse the JSON `state` field:
- **`ok`** — credentials configured. Show `account.name` → project `project.id` and proceed to verification.
- **`needs_account`** — no account configured. Read `next` for onboarding suggestions and follow "If Credentials Are Missing" below.
- **`needs_project`** — account configured but no project pinned. Suggest `mp project list` then `mp project use <id>`.
- **`error`** — show `error.message`. If `error.actionable` is true, the message names a concrete next command.

## If Credentials Are Missing

If no credentials are configured, guide the user to one of these methods:

### Recommended: Guided Setup

Tell the user to run `/mixpanel-headless:auth account add` for a step-by-step
walkthrough that securely collects credentials. The slash command never
prompts for secrets in conversation — it instructs the user to run
`! mp account add ...` themselves so the secret is read with hidden input.

### Alternative: OAuth Login

For OAuth browser auth (laptops with a usable browser):

```
! mp account add personal --type oauth_browser --region us
! mp account login personal     # opens browser for PKCE flow
```

The first `mp account add` registers the account; `mp account login` runs
the PKCE dance, persists tokens to `~/.mp/accounts/personal/tokens.json`,
and backfills the account's default project from the post-login `/me` probe.

### Alternative: Service-Account Environment Variables (temporary)

For quick testing, set all four variables in the shell:

```bash
export MP_USERNAME="service-account-username"
export MP_SECRET="service-account-secret"
export MP_PROJECT_ID="12345"
export MP_REGION="us"  # or "eu", "in"
```

### Alternative: Raw OAuth Bearer Token (best for agents / CI)

If the user has an OAuth 2.0 access token from another source, they can use
it directly without the PKCE browser flow:

```bash
export MP_OAUTH_TOKEN="<bearer-token>"
export MP_PROJECT_ID="12345"
export MP_REGION="us"  # or "eu", "in"
```

This is the recommended mode for non-interactive contexts. The full
service-account env-var set (`MP_USERNAME` + `MP_SECRET` + `MP_PROJECT_ID`
+ `MP_REGION`) takes precedence when both sets are complete.

## Cowork Environment

If running inside Claude Cowork (detected automatically), credentials work differently:

- **OAuth login and interactive account setup are NOT available** (no browser, no host terminal access)
- Credentials must be configured on the **host machine** before starting a Cowork session

### If No Credentials Found in Cowork

Tell the user:

> No Mixpanel credentials found in this Cowork session.
>
> On your **host machine** (outside Cowork), run:
> ```
> mp account export-bridge --to ~/.claude/mixpanel/auth.json
> ```
> This writes a v2 bridge file embedding your account record (and any
> oauth_browser tokens) so the Cowork session can read your credentials
> at startup.
>
> Then **start a new Cowork session** — credentials will be available automatically.

Do NOT suggest `/mixpanel-headless:auth account login`, `/mixpanel-headless:auth account add`, or interactive flows — these won't work inside Cowork.

### If Bridge File Found But Token Expired

The library will auto-refresh the OAuth token via the on-disk refresh
token (no browser needed). If refresh fails:

> Your OAuth session has expired and could not be refreshed.
> On your host machine, run:
> ```
> mp account login personal           # re-authenticate
> mp account export-bridge --to ~/.claude/mixpanel/auth.json
> ```
> Then start a new Cowork session.

## Verify Everything Works

```bash
python3 ${CLAUDE_SKILL_DIR}/../mixpanelyst/scripts/auth_manager.py account test
```

The subcommand never raises — read `result.ok` to determine outcome.
- `result.ok: true` → setup is complete; the user can ask analytics questions.
- `result.ok: false` → suggest `/mixpanel-headless:auth account test` for detailed diagnostics.

## Post-Setup: Explore Your Data

Once authenticated, these slash commands help orient the user:

- `/mixpanel-headless:auth project list` — discover all accessible projects via `/me`
- `/mixpanel-headless:auth session` — see active account / project / workspace
- `/mixpanel-headless:auth project use <id>` — switch to a different project
- `/mixpanel-headless:auth target add NAME --account A --project P` — save a named cursor position

The user can also construct a Workspace targeting a specific account / project /
workspace directly:

```python
import mixpanel_headless as mp

ws = mp.Workspace()                                  # default session
ws = mp.Workspace(account="team")                    # named account
ws = mp.Workspace(project="67890")                   # explicit project (active account)
ws = mp.Workspace(account="team", project="67890")   # both axes
ws.use(project="98765").events()                     # in-session switch (no re-auth)
```

_The mixpanelyst skill auto-triggers on analytics questions. For the analytical frameworks that guide investigations, see [analytical-frameworks.md](../mixpanelyst/references/analytical-frameworks.md). For the complete Python API, see [python-api.md](../mixpanelyst/references/python-api.md)._
