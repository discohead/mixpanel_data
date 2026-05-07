# Quick Start: mixpanel_headless + Claude Cowork

Get your Mixpanel credentials working inside [Claude Cowork](https://docs.anthropic.com/en/docs/claude-code/cowork) sessions so Claude agents can query your analytics data autonomously.

Cowork runs Claude agents in sandboxed virtual machines. These VMs don't have access to your local config files or browser, so credentials need to be exported from your machine into a "bridge file" that Cowork can read.

---

## What You'll Need

- **Claude Desktop** with Cowork access
- **A Mixpanel account** with access to a project
- **One of the following** for authentication:
  - A **service account** (username + secret) from your Mixpanel project settings, OR
  - A browser for **OAuth login** (interactive — your project is auto-discovered)

---

## Step 1: Install the CLI and Set Up Credentials

On your **local machine** (not inside Cowork), install the `mp` command-line tool:

```bash
pip install git+https://github.com/mixpanel/mixpanel-headless.git
```

Then configure your Mixpanel credentials:

```bash
# OAuth browser (PKCE flow — opens browser)
mp account add personal --type oauth_browser --region us
mp account login personal

# OR service account (prompts for secret securely)
mp account add my-project --type service_account \
    --username YOUR_SA_USERNAME --project YOUR_PROJECT_ID --region us
```

Verify the credentials work:

```bash
mp account test
```

You should see a success message confirming the connection.

---

## Step 2: Export Credentials for Cowork

On your **local machine**, export the active account into a v2 bridge file at the default Cowork-readable path:

```bash
mp account export-bridge --to ~/.claude/mixpanel/auth.json
```

This writes a v2 `auth.json` bridge file embedding your full `Account` record (and any `oauth_browser` tokens). The Cowork VM auto-discovers it on session start. Override the location with the `MP_AUTH_FILE` env var if you need a custom path.

You'll see a brief confirmation, then the bridge is ready:

```
Wrote bridge: ~/.claude/mixpanel/auth.json
  Account:  personal (oauth_browser, us)
  Tokens:   included (refresh-capable)
```

### Options

```bash
# Export a specific named account (defaults to the active account)
mp account export-bridge --to ~/.claude/mixpanel/auth.json --account production

# Pin a project ID into the bridge (overrides the account's default_project)
mp account export-bridge --to ~/.claude/mixpanel/auth.json --project 12345

# Pin a workspace ID into the bridge (needed for dashboard/entity management)
mp account export-bridge --to ~/.claude/mixpanel/auth.json --workspace 3448413
```

---

## Step 3: Start a Cowork Session and Run Setup

Open a Cowork session and run the setup skill:

```
/mixpanel-headless:setup
```

The setup script automatically detects the Cowork environment and reads credentials from the bridge file. You'll see output like:

```
Cowork environment detected.
✓ Auth bridge file found: ~/.claude/mixpanel/auth.json
  Account:  personal (oauth_browser, us)
  Project:  12345
  Tokens:   included (refresh-capable)
```

No additional configuration is needed inside Cowork.

---

## Step 4: Start Asking Questions

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
mp account login personal
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
│ ~/.mp/accounts/<name>/  │──account export-bridge──▶│   auth.json             │
│ (account + tokens)      │   --to <path>            │ (v2 bridge: full        │
│                         │                          │  Account + tokens)      │
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
mp account login personal
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

**Cause**: You're inside Cowork but the bridge file is missing.

**Fix**: You cannot configure credentials from inside Cowork (no browser, no host terminal). Exit Cowork, run `mp account export-bridge --to ~/.claude/mixpanel/auth.json` on your local machine, then start a new Cowork session.

### Important: What Doesn't Work Inside Cowork

These commands require a browser or host terminal and **should be run on your local machine**, not inside Cowork:

- `mp account login <name>` (needs a browser for the PKCE OAuth flow)
- `mp account add` for `service_account` (prompts for secret interactively by default; `--secret-stdin` and `MP_SECRET` env var work non-interactively, but the credential bridge is the recommended approach for Cowork)
- `mp account export-bridge --to <path>` (reads host credentials, writes the bridge file)
- `mp account remove-bridge [--at <path>]` (removes the bridge file from the host)

Always run these on your **local machine** before starting a Cowork session.

---

## Next Steps

- **Claude Code quick start**: [Claude Code Quick Start](quickstart-claude-code.md) — plugin setup and authentication
- **Full getting started guide**: [Getting Started Guide](getting-started-guide.md) — Python library, CLI, and more
- **Full documentation**: [mixpanel.github.io/mixpanel-headless](https://mixpanel.github.io/mixpanel-headless/)
