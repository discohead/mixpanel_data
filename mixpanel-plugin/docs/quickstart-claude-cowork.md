# Quick Start: mixpanel_headless + Claude Cowork

Get your Mixpanel credentials working inside [Claude Cowork](https://docs.anthropic.com/en/docs/claude-code/cowork) sessions so Claude agents can query your analytics data autonomously.

Cowork runs Claude agents in sandboxed virtual machines. The CLI has two ways to authenticate inside Cowork:

1. **Two-shot login (`mp login --start` / `--finish`)** — the simplest path if you don't have `mp` installed locally. Runs entirely inside Cowork; you paste a URL into your host browser, then paste the redirect URL back. No host-side setup.
2. **Bridge file** — if you already have credentials configured on your laptop (e.g., from regular `mp` use), export them into a "bridge file" Cowork can read. One-time setup, lasts across Cowork sessions.

Both paths work. Pick the one that fits your situation.

---

## What You'll Need

- **Claude Desktop** with Cowork access
- **A Mixpanel account** with access to a project
- **A browser** on your laptop for OAuth login (works for both paths)

---

## Path A: Two-shot login inside Cowork (recommended for first-time users)

This path requires nothing on your laptop. Everything happens inside Cowork.

### Step A1: Start a Cowork session and run setup

Open a Cowork session and run:

```
/mixpanel-headless:setup
```

This installs the `mp` CLI in the Cowork VM.

### Step A2: Run the login slash command

```
/mixpanel-headless:auth login
```

Claude detects the headless environment and runs the two-shot flow:

1. Claude runs `mp login --start` and shows you a URL to open.
2. You open the URL in your laptop's browser, complete Mixpanel login.
3. Your browser redirects to `localhost:19284/callback?...` and shows "site can't be reached" — **that's expected**.
4. You copy the URL from your browser's address bar and paste it back into chat.
5. Claude runs `mp login --finish '<URL>'`. The CLI exchanges the code for tokens, fetches `/me`, auto-picks a project, and writes the account to `~/.mp/accounts/` inside the VM.

The 10-minute inflight TTL is generous — switch tabs, complete login, come back, paste. If you take longer, just run `/mixpanel-headless:auth login` again to begin a fresh attempt.

### Step A3: Start asking questions

```
How many signups did we get last week?

What's our funnel conversion rate from signup to purchase?
```

### When this path is best

- You don't have `mp` installed on your laptop yet.
- You only need access from this one Cowork session (or a few — the VM persists tokens between sessions, but if Cowork rebuilds the VM you'll re-login).
- You're OK with the manual paste-back per fresh VM (one-time cost; auto-refresh handles token rotation thereafter).

### Tested browsers

The "site can't be reached" page must preserve `?code=...&state=...` in the address bar so you can copy it. Verified working on Chrome, Firefox, and Safari (default settings).

---

## Path B: Credential bridge from your laptop

If you already have `mp` configured on your laptop, this path is faster: one host-side export, then every Cowork session auto-discovers your credentials.

### Step B1: Install the CLI and set up credentials

On your **local machine** (not inside Cowork), install the `mp` command-line tool:

```bash
pip install git+https://github.com/mixpanel/mixpanel-headless.git
```

Then configure your Mixpanel credentials. The recommended path is the one-shot `mp login`:

```bash
mp login
# Opens browser for PKCE (defaults to us; pass --region eu|in for other
# clusters), derives the account name from /me, and pins your default
# project.
```

For explicit control over the account name, type, or region, use the two-step add instead:

```bash
# Service account (set MP_SECRET first, then register)
export MP_SECRET="your-secret-here"
mp account add my-project --type service_account \
    --username YOUR_SA_USERNAME --project YOUR_PROJECT_ID --region us

# Or explicit OAuth browser registration
mp account add personal --type oauth_browser --region us
mp account login personal
```

Verify the credentials work:

```bash
mp account test
```

You should see a success message confirming the connection.

---

### Step B2: Export credentials for Cowork

On your **local machine**, export the active account into a v2 bridge file at the default Cowork-readable path:

```bash
mp account export-bridge --to ~/.claude/mixpanel/auth.json
```

This writes a v2 `auth.json` bridge file embedding your full `Account` record (and any `oauth_browser` tokens). The Cowork VM auto-discovers it on session start. Override the location with the `MP_AUTH_FILE` env var if you need a custom path.

The CLI prints:

```
Wrote bridge file to ~/.claude/mixpanel/auth.json
```

### Options

```bash
# Export a specific named account (defaults to the active account)
mp account export-bridge --to ~/.claude/mixpanel/auth.json --account YOUR_ACCOUNT_NAME

# Pin a project ID into the bridge (overrides the account's default_project)
mp account export-bridge --to ~/.claude/mixpanel/auth.json --project YOUR_PROJECT_ID

# Pin a workspace ID into the bridge (needed for dashboard/entity management)
mp account export-bridge --to ~/.claude/mixpanel/auth.json --workspace YOUR_WORKSPACE_ID
```

---

### Step B3: Start a Cowork session and run setup

Open a Cowork session and run the setup skill:

```
/mixpanel-headless:setup
```

The setup script automatically detects the Cowork environment and reads credentials from the bridge file. No additional configuration is needed inside Cowork.

### Step B4: Start asking questions

You're ready. Ask Claude questions in natural language, just like in regular Claude Code:

```
How many signups did we get last week?

What's our funnel conversion rate from signup to purchase?

Show me weekly retention for users who completed onboarding.
```

---

## Managing the Credential Bridge

All bridge management commands run on your **local machine**, not inside Cowork.

### Check bridge status

Works both locally and inside Cowork:

```bash
mp session --bridge
```

Shows the bridge-resolved account, project, workspace, and any pinned headers. (For OAuth browser accounts, the library refreshes expired tokens automatically; refresh failure surfaces as `OAuthError(code="OAUTH_REFRESH_REVOKED")`.)

### Update credentials

If you change your credentials or switch projects, re-export to the same path:

```bash
mp account export-bridge --to ~/.claude/mixpanel/auth.json
```

Then start a **new Cowork session** for the changes to take effect.

### Remove the bridge

When you no longer need Cowork access to your Mixpanel data:

```bash
mp account remove-bridge          # removes ~/.claude/mixpanel/auth.json
mp account remove-bridge --at /custom/path/auth.json
```

---

## OAuth and Token Refresh

If you authenticated with OAuth (rather than a service account), the bridge file includes both an access token and a refresh token.

- **Automatic refresh**: The `mixpanel_headless` library refreshes expired OAuth tokens automatically inside Cowork — no browser needed
- **Refresh token rejected**: If the refresh token itself is rejected (e.g., revoked at the IdP), the library surfaces `OAuthError(code="OAUTH_REFRESH_REVOKED")`. You need to re-authenticate on your local machine and re-export:

```bash
# On your local machine
mp login --name personal             # or `mp account login personal` (legacy)
mp account export-bridge --to ~/.claude/mixpanel/auth.json
```

Then start a new Cowork session.

---

## How the Bridge Works

The credential bridge is a v2 JSON file that maps your local credentials into a format Cowork VMs can consume:

```
Your machine                                         Cowork VM
┌─────────────────────────┐                          ┌─────────────────────────┐
│ ~/.mp/config.toml       │                          │ ~/.claude/mixpanel/     │
│  (account records)      │                          │   auth.json             │
│ ~/.mp/accounts/<name>/  │──account export-bridge──▶│ (v2 bridge: full        │
│  (tokens + me cache)    │   --to <path>            │  Account + tokens)      │
└─────────────────────────┘                          └─────────────────────────┘
                                                              │
                                                       resolve_session() reads
                                                       bridge during construction
                                                              │
                                                       ┌──────▼──────────────┐
                                                       │ mp.Workspace()      │
                                                       │ (authenticated)     │
                                                       └─────────────────────┘
```

The bridge file is searched in this priority order:

1. `MP_AUTH_FILE` environment variable (if set)
2. `~/.claude/mixpanel/auth.json` (default location)
3. `./mixpanel_auth.json` in the current working directory

---

## Troubleshooting

### "No auth bridge file found" in Cowork

**Cause**: The bridge file wasn't created or isn't in a location Cowork can see.

**Fix**: On your local machine:
```bash
mp account export-bridge --to ~/.claude/mixpanel/auth.json
mp session --bridge   # verify the bridge resolves
```
Then start a **new** Cowork session (existing sessions won't pick up the new file).

### "Authentication failed" inside Cowork

**Cause**: The credentials in the bridge file are invalid or the service account was rotated.

**Fix**: On your local machine:
```bash
mp account test            # verify local credentials still work
mp account export-bridge --to ~/.claude/mixpanel/auth.json   # re-export fresh credentials
```

### OAuth token expired and won't refresh

**Cause**: The refresh token was rejected (typically `OAuthError(code="OAUTH_REFRESH_REVOKED")`).

**Fix**: On your local machine:
```bash
mp login --name personal             # or `mp account login personal` (legacy)
mp account export-bridge --to ~/.claude/mixpanel/auth.json
```
Then start a new Cowork session.

### Can't run `mp account export-bridge` — "command not found"

**Cause**: The `mixpanel_headless` package isn't installed on your local machine.

**Fix**:
```bash
pip install git+https://github.com/mixpanel/mixpanel-headless.git
mp --version   # verify
```

### Setup says "Cowork environment detected" but no credentials

**Cause**: You're inside Cowork without a bridge file AND haven't done the two-shot login.

**Fix**: Two options:
- Use Path A (two-shot login from inside Cowork): run `/mixpanel-headless:auth login` inside Cowork.
- Use Path B (bridge from your laptop): run `mp account export-bridge --to ~/.claude/mixpanel/auth.json` on your local machine, then start a new Cowork session.

### Two-shot login: "site can't be reached" page

**Cause**: When the OAuth provider redirects your browser to `localhost:19284/callback`, no server is listening (the loopback is the Cowork VM, not your laptop). The browser shows "site can't be reached."

**Fix**: This is the expected behavior. Copy the URL from your browser's address bar (it contains `?code=...&state=...`) and paste it back into chat. Verified to work on Chrome, Firefox, and Safari with default settings.

### Two-shot login: inflight expired

**Cause**: You took longer than 10 minutes between `mp login --start` and pasting the redirect URL.

**Fix**: Re-run `/mixpanel-headless:auth login`. The CLI clobbers the prior inflight and starts fresh.

### Two-shot login: post-publish failure

**Cause**: `mp login --finish` succeeded at token exchange but failed at publish (e.g., `/me` timed out, name collision, network blip).

**Fix**: The CLI leaves a `.tmp-*` placeholder dir in `~/.mp/accounts/`. Re-run `mp login --resume <PATH>` to retry the publish without re-running PKCE. The error message includes the placeholder path.

### Bridge path: commands that need to run on your laptop

These bridge-management commands require host-side resources and **must run on your local machine**:

- `mp account export-bridge --to <path>` (reads host credentials, writes the bridge file)
- `mp account remove-bridge [--at <path>]` (removes the bridge file from the host)

Note: `mp login` itself works **inside** Cowork via the two-shot flow (Path A). Only the bridge-export commands above are host-only.

---

## Next Steps

- **Claude Code quick start**: [Claude Code Quick Start](quickstart-claude-code.md) — plugin setup and authentication
- **Full getting started guide**: [Getting Started Guide](getting-started-guide.md) — Python library, CLI, and more
- **Full documentation**: [mixpanel.github.io/mixpanel-headless](https://mixpanel.github.io/mixpanel-headless/)
