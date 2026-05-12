# Configuration

`mixpanel_headless` organizes auth around three independent axes: **Account → Project → Workspace**.

- **Account** — *who* is authenticating. Three first-class types managed through one surface: `service_account` (Basic Auth), `oauth_browser` (PKCE flow with auto-refreshed tokens), and `oauth_token` (static bearer for CI / agents).
- **Project** — *which* Mixpanel project the calls run against. Lives on the active account as `default_project`; can be overridden per call.
- **Workspace** — *which* workspace inside the project. Optional; lazy-resolves to the project's default workspace on first workspace-scoped call.

In-session switching is a one-line operation: `Workspace.use(account=..., project=..., workspace=..., target=...)`. The underlying HTTP client and per-account `/me` cache are preserved across switches, so cross-project / cross-account iteration is O(1) per turn.

!!! tip "Explore on DeepWiki"
    🤖 **[Authentication Setup →](https://deepwiki.com/mixpanel/mixpanel-headless/2.2-authentication-setup)**

    Ask questions about service accounts, OAuth, environment variables, or multi-account configuration.

## Quick Start: `mp login`

The fastest way to authenticate is the top-level `mp login` command. It runs the right auth flow for your environment, derives an account name from `/me`, and pins a default project — all in one call:

```bash
mp login
# Logged in as jared@example.com → acme · AI Demo
```

Auth-type detection is env-driven:

1. Explicit `--service-account` / `--token-env VAR` flag.
2. `MP_USERNAME` + `MP_SECRET` set → `service_account`.
3. `MP_OAUTH_TOKEN` set → `oauth_token`.
4. Otherwise → `oauth_browser` (PKCE).

Region behavior depends on the auth type:

- `service_account` and `oauth_token`: probes `us → eu → in` against `/me` and uses the first 200.
- `oauth_browser`: defaults to `us` when `--region` is not passed. EU and India users must pass `--region eu` or `--region in` explicitly (the PKCE flow commits to a single region before the post-login `/me` probe runs).

Useful flags: `--region {us|eu|in}` sets the region explicitly, `--project ID` skips the picker, `--name NAME` overrides the derived name.

The rest of this page covers the underlying account model, env-var precedence, and the explicit setup paths for users who want more control than `mp login` provides.

## Account Types

| Type | Best For | Storage |
|---|---|---|
| `service_account` | CI / scripts / unattended automation | `~/.mp/config.toml` (Basic Auth username + secret) |
| `oauth_browser` | Interactive personal use | `~/.mp/accounts/{name}/tokens.json` (auto-refreshed) |
| `oauth_token` | CI bots / agents (no browser) | Inline secret OR `--token-env VAR` indirection |

Service accounts are the right default for unattended automation. OAuth browser is the right default for personal/interactive use. OAuth token (static bearer) is the right default when a managed OAuth client (Claude Code plugin, CI pipeline) hands you a pre-obtained access token.

## Environment Variables

| Variable | Purpose |
|---|---|
| `MP_ACCOUNT` | Active account override (CLI: `--account` / `-a`) |
| `MP_PROJECT_ID` | Project override (CLI: `--project` / `-p`) |
| `MP_WORKSPACE_ID` | Workspace override (CLI: `--workspace` / `-w`) |
| `MP_TARGET` | Apply a saved target (CLI: `--target` / `-t`) |
| `MP_OAUTH_TOKEN` | Static bearer token (alternative to a registered account; env-var path requires `MP_PROJECT_ID` + `MP_REGION`) |
| `MP_USERNAME` | Service-account username (requires `MP_SECRET`, `MP_PROJECT_ID`, `MP_REGION`) |
| `MP_SECRET` | Service-account secret (paired with `MP_USERNAME`) |
| `MP_REGION` | Data residency region (`us`, `eu`, `in`) |
| `MP_AUTH_FILE` | Override path to the Cowork bridge file |
| `MP_CONFIG_PATH` | Override config file path (`~/.mp/config.toml`) |
| `MP_OAUTH_STORAGE_DIR` | Override storage root (`~/.mp`) |

These map onto the [credential resolution chain](#credential-resolution-chain) below.

!!! note "Service-account env quad takes precedence over `MP_OAUTH_TOKEN`"
    If `MP_USERNAME` + `MP_SECRET` + `MP_PROJECT_ID` + `MP_REGION` are all set, the service-account quad wins even when `MP_OAUTH_TOKEN` is also present. This is safe to add to a shell that already exports the service-account vars.

!!! note "`mp login` auth-type detection"
    The same env presence drives `mp login`'s auth-type detection: `MP_USERNAME` + `MP_SECRET` set → `service_account`; `MP_OAUTH_TOKEN` set → `oauth_token`; otherwise the browser PKCE flow. Pass `--service-account` or `--token-env VAR` to force a non-browser path.

## Setting Up an Account

### Service account (Basic Auth)

```bash
# Set the secret via env var (preferred)
export MP_SECRET="aQUXhKokwLywLoxE3AxLt0g9dXC2G7bT"
mp account add team --type service_account \
    --username "team-mp.292e7c.mp-service-account" \
    --project 3018488 \
    --region us
# Added account 'team' (service_account, us). Set as active.
```

Or read the secret from stdin (useful when it lives in a shell variable):

```bash
echo "$SECRET" | mp account add team --type service_account \
    --username "team-mp..." --project 3018488 --region us --secret-stdin
```

Verify:

```bash
mp account test team
# { "account_name": "team", "ok": true, "user": {...}, "accessible_project_count": 7 }
```

### OAuth (browser, PKCE)

The recommended path is `mp login` (see [Quick Start](#quick-start-mp-login) above), which derives a name from `/me`. The browser path defaults to `us`; pass `--region eu|in` for other clusters:

```bash
mp login --name personal
# Logged in as jared@example.com → personal · AI Demo
```

Tokens land at `~/.mp/accounts/personal/tokens.json` (mode `0o600`) and refresh automatically before each call. The `default_project` is set from the post-login `/me` probe.

<details><summary>Advanced: explicit account creation (two-step)</summary>

For full control over the account name and region at registration time:

```bash
mp account add personal --type oauth_browser --region us
# Added account 'personal' (oauth_browser, us). Set as active.

mp account login personal
# Opening browser...
# ✓ Authenticated as jared@example.com
```

`mp account add` registers the account; `mp account login` runs the PKCE flow. `mp login --name personal --region us` collapses both into one call.

</details>

### OAuth (static bearer / CI)

```bash
# Pure env-var path — no persistent state
export MP_OAUTH_TOKEN="ey..."
export MP_REGION=us
export MP_PROJECT_ID=3713224
mp query segmentation -e Login --from 2026-04-01 --to 2026-04-21
```

Or register a named account that pulls the token from an env var at request time:

```bash
mp account add ci --type oauth_token --token-env MP_CI_TOKEN \
    --project 3713224 --region us
mp account use ci
MP_CI_TOKEN=ey... mp query segmentation -e Login --from 2026-04-01
```

`--project` is required when registering an `oauth_token` account (it becomes the account's `default_project`).

Static bearers are not persisted (no refresh capability — pass a fresh token when the previous one expires).

## Config File

Persistent state lives in `~/.mp/config.toml` (mode `0o600`), with a single schema and four section types:

```toml
[active]
account = "personal"
workspace = 3448414       # optional

[accounts.personal]
type = "oauth_browser"
region = "us"
default_project = "3713224"

[accounts.team]
type = "service_account"
region = "us"
default_project = "3018488"
username = "team-mp..."
secret = "..."

[accounts.ci]
type = "oauth_token"
region = "us"
default_project = "3713224"
token_env = "MP_CI_TOKEN"  # XOR with `token = "..."`

[targets.ecom]
account = "team"
project = "3018488"
workspace = 3448414
```

The `[active]` block stores only `account` and (optionally) `workspace` — project lives on the active account as `default_project`. Targets are saved cursor positions (see [Saved Targets](#saved-targets) below).

## Managing Accounts via CLI

```bash
mp account list                           # All accounts; active marked with *
mp account show [NAME]                    # Account details (omit NAME for active)
mp account use NAME                       # Switch active account (clears workspace)
mp account test [NAME]                    # Probe /me; returns AccountTestResult
mp account login NAME                     # Run PKCE flow (oauth_browser only)
mp account logout NAME                    # Delete on-disk tokens (oauth_browser only)
mp account token [NAME]                   # Print bearer (for piping to curl etc.)
mp account update NAME --region eu        # Rotate region/secret/token/etc.
mp account remove NAME [--force]          # Delete; --force orphans dependent targets
```

The first account added auto-promotes to active.

## Managing Accounts via Python

The public surface lives in three functional namespaces:

```python
import mixpanel_headless as mp

# Add a service account
mp.accounts.add(
    "team",
    type="service_account",
    region="us",
    default_project="3018488",
    username="team-mp...",
    secret="...",
)

# Add an OAuth account and run the browser flow
mp.accounts.add("personal", type="oauth_browser", region="us")
result = mp.accounts.login("personal")          # OAuthLoginResult
print(result.user.email, result.expires_at)

# List + switch + probe
for s in mp.accounts.list():                    # list[AccountSummary]
    print(s.name, s.type, s.region, "*" if s.is_active else "")
mp.accounts.use("team")
probe = mp.accounts.test()                      # AccountTestResult
print(probe.ok, probe.accessible_project_count)
```

See [API → Auth](../api/auth.md) for the full namespace reference.

## OAuth (browser) — token storage

OAuth browser tokens are stored per account; OAuth client metadata (Dynamic Client Registration) is shared per region:

```
~/.mp/
├── config.toml                        # accounts, targets, [active]
├── accounts/
│   ├── personal/
│   │   ├── tokens.json                # access + refresh tokens (0o600)
│   │   └── me.json                    # cached /me response (0o600)
│   └── team/
│       └── me.json
└── oauth/
    ├── client_us.json                 # shared DCR client per region
    ├── client_eu.json
    └── client_in.json
```

Tokens auto-refresh on expiry. If the refresh token is rejected (e.g., revoked at the IdP), the next call raises `OAuthError(code="OAUTH_REFRESH_REVOKED")` — re-run `mp login --name NAME` to recover (or the legacy `mp account login NAME`).

```bash
mp account token personal                          # Print the active access token
curl -H "Authorization: Bearer $(mp account token personal)" \
    https://mixpanel.com/api/app/me
```

## Credential Resolution Chain

When constructing a `Workspace` (or running a CLI command), each axis is resolved independently. The general chain is:

1. **Environment variables** — direct env reads inside the resolver.
2. **Constructor / CLI param** — `Workspace(account="...")`, `mp -a NAME ...`.
3. **Saved target** — `Workspace(target="ecom")`, `mp -t ecom ...`.
4. **Bridge file** — `MP_AUTH_FILE` or `~/.claude/mixpanel/auth.json` (Cowork integration).
5. **Persisted active session** — the `[active]` block in `config.toml`.
6. **Account default** — `account.default_project` for the project axis.

Per-axis details:

- **Account** — the resolver reads the **service-account env quad** (`MP_USERNAME` + `MP_SECRET` + `MP_PROJECT_ID` + `MP_REGION`) and the **OAuth-token env triple** (`MP_OAUTH_TOKEN` + `MP_PROJECT_ID` + `MP_REGION`) directly. The SA quad wins over the OAuth triple. `MP_ACCOUNT` is wired as the `envvar=` default for `--account` / `-a` by Typer — it is **not** read directly by the resolver's env step (unlike `MP_USERNAME` / `MP_OAUTH_TOKEN`). An explicit `--account NAME` or `Workspace(account="...")` overrides it normally.
- **Project** — `MP_PROJECT_ID` is read directly by the resolver (env layer), then `--project` / `Workspace(project=...)` (param), then target, bridge, and finally the active account's `default_project`.
- **Workspace** — `MP_WORKSPACE_ID` is read directly by the resolver (env layer), then `--workspace` / `Workspace(workspace=...)` (param), then target, bridge, and `[active].workspace`.

There is **no silent cross-axis fallback**: switching the active account clears the workspace (workspaces are project-scoped), and project doesn't carry forward to a new account. If an axis can't be resolved, the resolver raises `ConfigError` rather than silently falling back to a default.

```python
import mixpanel_headless as mp

# Default — resolve everything from config + env
ws = mp.Workspace()

# Explicit per-axis overrides
ws = mp.Workspace(account="team", project="3713224")
ws = mp.Workspace(target="ecom")
```

## Workspace Axis (in-session switching)

Workspaces are project-scoped. Set the workspace via env var, CLI flag, constructor arg, or `Workspace.use()`:

```bash
mp --workspace 3448414 inspect events     # one-off override
mp workspace use 3448414                  # persist to [active].workspace
export MP_WORKSPACE_ID=3448414            # env-var override
```

```python
import mixpanel_headless as mp

ws = mp.Workspace(workspace=3448414)      # at construction
ws.use(workspace=3448414)                 # in-session switch (returns self)
ws.use(workspace=3448414, persist=True)   # also write to [active]
```

If no workspace is specified, workspace-scoped endpoints lazy-resolve to the project's default workspace on first use.

## Saved Targets

A **target** is a saved (account, project, optional workspace) bundle — a named cursor position you can apply with one command:

```bash
mp target add ecom --account team --project 3018488 --workspace 3448414
mp target list

# One-off application (CLI override only)
mp --target ecom query segmentation -e Login --from 2026-04-01

# Persistent application (writes [active] atomically)
mp target use ecom
# Active: team → E-Commerce Demo (3018488), workspace 3448414
```

Python:

```python
import mixpanel_headless as mp

mp.targets.add("ecom", account="team", project="3018488", workspace=3448414)
mp.targets.use("ecom")                            # writes [active] atomically

ws = mp.Workspace(target="ecom")                  # apply at construction
ws.use(target="ecom")                             # apply in-session
```

`--target` is mutually exclusive with `--account` / `--project` / `--workspace` (and the equivalent constructor kwargs).

## Bridge Files (Cowork integration)

The Cowork bridge is a v2 JSON file that lets a remote VM (or any environment that doesn't have your `~/.mp/config.toml`) authenticate against Mixpanel using your host machine's account and tokens.

```bash
# On the host — write the bridge
mp account export-bridge --to ~/.claude/mixpanel/auth.json
# Wrote bridge: ~/.claude/mixpanel/auth.json
#   Account:  personal (oauth_browser, us)
#   Tokens:   included (refresh-capable)

# In the VM — bridge is auto-discovered, or override with env var
export MP_AUTH_FILE=/host/.claude/mixpanel/auth.json
mp project list                # works without `mp account add`
mp session --bridge            # show bridge-resolved state

# On the host — tear down
mp account remove-bridge
# Removed bridge: ~/.claude/mixpanel/auth.json
```

The bridge file embeds the full `Account` (with secrets), optional OAuth tokens (for `oauth_browser` accounts), and optional pinned project/workspace/headers. Default search order: `MP_AUTH_FILE` → `~/.claude/mixpanel/auth.json` → `./mixpanel_auth.json`.

```python
from pathlib import Path

import mixpanel_headless as mp

mp.accounts.export_bridge(to=Path("~/.claude/mixpanel/auth.json").expanduser())
mp.accounts.remove_bridge()
```

## Data Residency Regions

Mixpanel stores data in regional data centers. Use the correct region for your project:

| Region | Code | API Endpoint |
|---|---|---|
| United States | `us` | `mixpanel.com` |
| European Union | `eu` | `eu.mixpanel.com` |
| India | `in` | `in.mixpanel.com` |

!!! warning "Region mismatch"
    Using the wrong region results in authentication errors or empty data. The region lives on the account (`account.region`); change it via `mp account update NAME --region eu`.

## Next Steps

- [Quick Start](quickstart.md) — Run your first queries
- [API → Auth](../api/auth.md) — Full Python API reference for accounts, sessions, and targets
- [CLI Reference](../cli/index.md) — Complete CLI command reference
