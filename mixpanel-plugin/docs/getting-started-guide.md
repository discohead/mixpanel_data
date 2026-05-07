# Getting Started with mixpanel_headless

A step-by-step guide to installing, configuring, and using `mixpanel_headless` — the Python library, CLI, and Claude Code plugin for Mixpanel analytics.

This guide is for anyone who wants to explore their Mixpanel data programmatically, whether through the command line, Python scripts, or conversational analytics with Claude.

---

## Table of Contents

- [What You'll Need](#what-youll-need)
- [Part 1: Install the Package](#part-1-install-the-package)
- [Part 2: Authenticate with Mixpanel](#part-2-authenticate-with-mixpanel)
- [Part 3: Explore Your Data with the CLI](#part-3-explore-your-data-with-the-cli)
- [Part 4: Run Analytics Queries](#part-4-run-analytics-queries)
- [Part 5: Use the Python API](#part-5-use-the-python-api)
- [Part 6: Set Up the Claude Code Plugin](#part-6-set-up-the-claude-code-plugin)
- [Part 7: Set Up Claude Cowork](#part-7-set-up-claude-cowork)
- [Quick Reference](#quick-reference)
- [Troubleshooting](#troubleshooting)
- [Next Steps](#next-steps)

---

## What You'll Need

Before you begin, make sure you have:

- **Python 3.10 or later** — Check with `python3 --version`
- **pip or uv** — A Python package installer (`pip` comes with Python; [uv](https://docs.astral.sh/uv/) is faster)
- **A Mixpanel account** with access to a project
- **One of the following** for authentication:
  - A **service account** (username + secret) from your Mixpanel project settings, OR
  - A browser for **OAuth login** (interactive — your project is auto-discovered)

For service accounts, you'll also need your **Mixpanel Project ID**, which you can find in your Mixpanel project settings under "Project Details." For OAuth login, your projects are discovered automatically.

---

## Part 1: Install the Package

The `mixpanel_headless` package installs both the Python library and the `mp` command-line tool.

### Option A: Install with pip

```bash
pip install git+https://github.com/mixpanel/mixpanel-headless.git
```

### Option B: Install with uv (faster)

```bash
uv pip install git+https://github.com/mixpanel/mixpanel-headless.git
```

### Verify the Installation

```bash
mp --version
```

You should see a version number printed. If you get "command not found," make sure your Python scripts directory is on your `PATH`. You can also run the CLI with:

```bash
python3 -m mixpanel_headless --version
```

---

## Part 2: Authenticate with Mixpanel

You need to connect `mixpanel_headless` to your Mixpanel project. There are two ways to do this: **OAuth login** (interactive, opens your browser) or **service account** (for scripts and automation).

### Option A: OAuth Login (Recommended for Personal Use)

Register an OAuth browser account, then run the PKCE login flow — the second command opens your browser so you can authenticate with Mixpanel:

```bash
mp account add personal --type oauth_browser --region us
mp account login personal
```

After logging in, `mixpanel_headless` automatically backfills the account's `default_project` from the post-login `/me` probe. If you have multiple accessible projects and want to switch:

```bash
mp project list                # See all your accessible projects
mp project use YOUR_PROJECT_ID # Switch to a different project
```

You can also pin a specific project at registration time by passing `--project YOUR_PROJECT_ID` to `mp account add`.

**Region options:**

| Region | Flag | When to use |
|--------|------|-------------|
| United States | `--region us` | Most projects (default) |
| Europe | `--region eu` | EU data residency |
| India | `--region in` | India data residency |

Verify the connection:

```bash
mp session
```

### Option B: Service Account (Recommended for Scripts & CI/CD)

Service accounts are ideal for automation. You'll need a **service account username** and **secret** from your Mixpanel project settings (Settings > Service Accounts).

Add the credentials (you'll be prompted for the secret securely):

```bash
mp account add my-project --type service_account \
    --username YOUR_SA_USERNAME --project YOUR_PROJECT_ID --region us
```

You'll see a hidden input prompt for the secret — paste it and press Enter. (For non-interactive use, prefer `export MP_SECRET=...` before the command, or pipe the secret via `--secret-stdin`.)

Then verify the connection:

```bash
mp account test
```

You should see a success message confirming the credentials work.

### Option C: Environment Variables (Quick Setup)

For a quick, temporary setup (useful for trying things out), you can export environment variables:

```bash
export MP_USERNAME="your-service-account-username"
export MP_SECRET="your-service-account-secret"
export MP_PROJECT_ID="12345"
export MP_REGION="us"
```

These take effect immediately for any `mp` command or Python script in the same terminal session. For an OAuth bearer token instead of a service account, set `MP_OAUTH_TOKEN` + `MP_PROJECT_ID` + `MP_REGION` (the service-account quad takes precedence when both sets are complete).

### Where Credentials Are Stored

Account records and the active session live in `~/.mp/config.toml`. OAuth browser tokens are stored per-account at `~/.mp/accounts/<name>/tokens.json` (mode `0o600`) and refreshed automatically on expiry. These files are created automatically when you run `mp account add` or `mp account login` — you should never need to edit them by hand.

---

## Part 3: Explore Your Data with the CLI

Now that you're authenticated, explore what's in your Mixpanel project.

### List All Events

```bash
mp inspect events
```

This shows every event type being tracked in your project.

### View Properties for a Specific Event

```bash
mp inspect properties --event "Signup"
```

Replace `"Signup"` with any event name from the previous command.

### See Saved Funnels and Cohorts

```bash
mp inspect funnels
mp inspect cohorts
```

### Change the Output Format

All commands support `--format` to control how results are displayed:

```bash
mp inspect events --format table    # Human-readable table
mp inspect events --format json     # Machine-readable JSON
mp inspect events --format csv      # Spreadsheet-friendly CSV
```

---

## Part 4: Run Analytics Queries

### Segmentation Query (Event Trends)

See how often an event occurred over a date range:

```bash
mp query segmentation --event "Signup" --from YYYY-MM-DD --to YYYY-MM-DD
```

### Break Down by Property

Add `--on` to break results down by a property:

```bash
mp query segmentation --event "Purchase" --from YYYY-MM-DD --to YYYY-MM-DD --on country
```

### Funnel Conversion

Query a saved funnel by its ID (find IDs with `mp inspect funnels`):

```bash
mp query funnel 12345 --from YYYY-MM-DD --to YYYY-MM-DD
```

### Filter JSON Output with --jq

Commands that return JSON support `--jq` for inline filtering:

```bash
# Get only the first 5 events
mp inspect events --format json --jq '.[:5]'

# Extract just event names
mp inspect events --format json --jq '.[].name'
```

### Format as a Table

```bash
mp query segmentation --event "Login" --from YYYY-MM-DD --to YYYY-MM-DD --format table
```

---

## Part 5: Use the Python API

The Python library gives you the full power of `mixpanel_headless` with pandas DataFrames for analysis.

### Basic Setup

```python
import mixpanel_headless as mp

# Creates a Workspace using your saved credentials
ws = mp.Workspace()
```

### Discover Your Data

```python
# List all events in your project
events = ws.events()
print(events)

# List properties for a specific event
props = ws.properties("Purchase")
print(props)
```

### Run an Insights Query

```python
# Simple event count over the last 30 days
result = ws.query("Signup", last=30, unit="day")
print(result.df)  # pandas DataFrame
```

### Insights with Breakdown and Filter

```python
from mixpanel_headless import Filter, GroupBy

# Purchase revenue by plan type, filtered to US customers
result = ws.query(
    "Purchase",
    math="total",
    math_property="amount",
    where=Filter.equals("country", "US"),
    group_by="plan_type",
    last=30,
)
print(result.df)
```

### Funnel Query

```python
# Define funnel steps inline — no saved funnel needed
funnel = ws.query_funnel(
    ["Signup", "Onboarding Complete", "First Purchase"],
    conversion_window=7,
    last=90,
)
print(f"Overall conversion: {funnel.overall_conversion_rate:.1%}")
print(funnel.df)
```

### Retention Query

```python
# How many users who signed up came back to log in?
retention = ws.query_retention(
    "Signup",
    "Login",
    retention_unit="week",
    last=90,
)
print(retention.df.head())  # cohort_date | bucket | count | rate
```

### Flow Query (User Paths)

```python
# What do users do after signing up?
flow = ws.query_flow("Signup", forward=4)
print(flow.top_transitions(5))     # Top 5 most common paths
print(flow.drop_off_summary())     # Where users drop off
```

### User Profile Query

```python
from mixpanel_headless import Filter

# Pull profile fields for high-value users
result = ws.query_user(
    where=Filter.greater_than("purchase_count", 10),
    properties=["$name", "$email", "plan"],
    limit=None,                      # fetch every match (None = no cap)
)
print(result.df.head())              # distinct_id | $name | $email | plan
```

### Stream Events

For processing large datasets without loading everything into memory:

```python
for event in ws.stream_events(from_date="2025-06-01", to_date="2025-06-30"):
    print(event["event"], event["properties"]["distinct_id"])
```

---

## Part 6: Set Up the Claude Code Plugin

The Claude Code plugin turns Claude into a Mixpanel data analyst. Instead of writing queries yourself, you ask questions in plain English and Claude writes and runs the Python code for you.

### Prerequisites

- [Claude Code](https://docs.anthropic.com/en/docs/claude-code) installed (CLI, desktop app, or web app)
- Plugins enabled in Claude Code

### Install the Plugin

In your Claude Code session, run:

```
/plugin marketplace add mixpanel/mixpanel-headless
/plugin install mixpanel-headless@mixpanel-headless-marketplace
```

### Run the Setup Skill

After installing, run the setup skill to install dependencies and verify authentication:

```
/mixpanel-headless:setup
```

This will:

1. Check that Python 3.10+ is available
2. Install the `mixpanel_headless` package and its dependencies (pandas, numpy, matplotlib, networkx, etc.)
3. Verify that your Mixpanel credentials are configured
4. Report the status of your connection

### Configure Credentials (If Not Already Done)

If the setup skill reports that no credentials are found, use the `/mixpanel-headless:auth` command:

```
/mixpanel-headless:auth account add my-project
```

Claude will guide you through entering your service account username, project ID, and region. You'll be prompted to run a shell command that securely collects your secret. For OAuth, use `/mixpanel-headless:auth account add personal --type oauth_browser --region us` followed by `/mixpanel-headless:auth account login personal`.

### Ask Analytics Questions

Once authenticated, just ask Claude questions in natural language:

```
"How many signups did we get last week?"

"Where do users drop off in the checkout funnel?"

"Do users who complete onboarding retain better than those who don't?"

"What's the most common path after a user signs up?"

"Build me a weekly KPI dashboard for the product team."
```

Claude will choose the right query engine (Insights, Funnels, Retention, Flows, or Users), write and execute the Python code, and explain the results.

### What's in the Plugin

The plugin ships three skills that Claude loads automatically when relevant:

| Skill | Trigger | What It Does |
|-------|---------|--------------|
| **setup** | `/mixpanel-headless:setup` (manual) | Installs `mixpanel_headless` + analytics dependencies and verifies credentials. |
| **mixpanelyst** | Auto-loads on analytics questions | Distilled `Workspace` API reference, discovery workflow, exploratory analysis playbook, and live `help.py` lookup for method signatures, types, and enums. |
| **dashboard-expert** | Auto-loads on dashboard questions | Four-mode workflow (Analyze, Build, Modify, Explain) for Mixpanel dashboards, with 9 design templates, chart-type selection, and layout reference. |

The `/mixpanel-headless:auth` slash command provides a guided wrapper around `mp account / project / workspace / target / session / bridge` for managing credentials without leaving the conversation.

---

## Part 7: Set Up Claude Cowork

[Claude Cowork](https://docs.anthropic.com/en/docs/claude-code/cowork) lets multiple Claude agents collaborate on tasks in sandboxed virtual machines. To use `mixpanel_headless` in Cowork, you need to export your credentials from your local machine so the Cowork VM can access them.

### Step 1: Set Up the Credential Bridge (On Your Local Machine)

On your **local machine** (not inside Cowork), export the active account into a v2 bridge file at the default Cowork-readable path:

```bash
mp account export-bridge --to ~/.claude/mixpanel/auth.json
```

This writes a v2 `auth.json` bridge file embedding your full `Account` record (and any `oauth_browser` tokens) so the Cowork session can read your credentials at startup. The default search path inside Cowork is `~/.claude/mixpanel/auth.json` — override with `MP_AUTH_FILE` if you need a custom location.

**Options:**

```bash
# Export a specific named account (defaults to the active account)
mp account export-bridge --to ~/.claude/mixpanel/auth.json --account production

# Pin a project ID into the bridge (overrides the account's default_project)
mp account export-bridge --to ~/.claude/mixpanel/auth.json --project 12345

# Pin a workspace ID into the bridge (needed for dashboard/entity management)
mp account export-bridge --to ~/.claude/mixpanel/auth.json --workspace 3448413
```

### Step 2: Verify the Bridge (Anywhere)

Check that the bridge resolves correctly:

```bash
mp session --bridge
```

This shows the resolved account, project, workspace, and any pinned headers from the bridge file.

### Step 3: Use mixpanel_headless in Cowork

Inside a Cowork session, run the setup skill:

```
/mixpanel-headless:setup
```

The setup script automatically detects the Cowork environment and reads credentials from the bridge file. No additional configuration is needed.

### Step 4: Clean Up (When Done)

When you no longer need Cowork access, remove the bridge file:

```bash
mp account remove-bridge          # removes the default ~/.claude/mixpanel/auth.json
mp account remove-bridge --at /custom/path/auth.json
```

### OAuth Token Refresh

If you authenticated with OAuth, the bridge file embeds your refresh token. The library automatically refreshes expired access tokens inside Cowork — no browser interaction needed. If the refresh token itself is rejected (e.g., revoked at the IdP), you'll need to re-authenticate on your local machine (`mp account login <name>`) and re-run `mp account export-bridge --to ~/.claude/mixpanel/auth.json` to pick up the fresh tokens.

---

## Quick Reference

### CLI Commands at a Glance

| Command | What It Does |
|---------|-------------|
| `mp account add <name> --type oauth_browser --region us` | Register an OAuth browser account |
| `mp account login <name>` | Run the PKCE browser flow for an OAuth account |
| `mp account add <name> --type service_account --username ... --project ... --region ...` | Register a service account |
| `mp account test [name]` | Test credentials for an account (defaults to active) |
| `mp session` | Show the resolved active session (account / project / workspace) |
| `mp account use <name>` | Switch the active account |
| `mp project list` / `mp project use <id>` | List accessible projects / switch active project |
| `mp workspace list` / `mp workspace use <id>` | List workspaces / pin one to the active session |
| `mp target add <name> --account A --project P [--workspace W]` | Save a named (account, project, workspace?) cursor |
| `mp target use <name>` | Apply a saved target atomically |
| `mp account export-bridge --to PATH` | Write a v2 Cowork bridge file |
| `mp account remove-bridge [--at PATH]` | Remove the bridge file |
| `mp inspect events` | List all tracked events |
| `mp inspect properties --event <name>` | List properties for an event |
| `mp query segmentation --event <name> --from <date> --to <date>` | Run a segmentation query |
| `mp query funnel <id> --from <date> --to <date>` | Query a saved funnel |
| `mp --help` | Show all available commands |
| `mp <command> --help` | Show help for a specific command |

### Python API at a Glance

```python
import mixpanel_headless as mp

ws = mp.Workspace()

ws.events()                              # List events
ws.properties("EventName")              # List properties
ws.query("Event", last=30)              # Insights query
ws.query_funnel(["A", "B", "C"])        # Funnel query
ws.query_retention("A", "B")            # Retention query
ws.query_flow("Event", forward=3)       # Flow query
ws.query_user(properties=["$email"])    # User profile query
ws.stream_events(from_date="...", to_date="...")  # Stream events
```

### Environment Variables

| Variable | Purpose |
|----------|---------|
| `MP_USERNAME` | Service account username |
| `MP_SECRET` | Service account secret |
| `MP_OAUTH_TOKEN` | Raw OAuth 2.0 bearer token (alternative to service account; requires `MP_PROJECT_ID` + `MP_REGION`; the full service-account quad takes precedence when both sets are complete) |
| `MP_PROJECT_ID` | Your Mixpanel project ID |
| `MP_REGION` | Data residency region (`us`, `eu`, or `in`) |
| `MP_WORKSPACE_ID` | Workspace ID (for dashboard and entity management) |
| `MP_ACCOUNT` | Override the active account name |
| `MP_TARGET` | Apply a saved target (mutually exclusive with `MP_ACCOUNT`/`MP_PROJECT_ID`/`MP_WORKSPACE_ID`) |
| `MP_AUTH_FILE` | Override path to the v2 Cowork bridge file |
| `MP_CONFIG_PATH` | Override config file location |

### Output Formats

Every CLI command supports `--format`:

| Format | Flag | Best For |
|--------|------|----------|
| JSON | `--format json` | Scripting, piping to other tools |
| JSON Lines | `--format jsonl` | Streaming, log processing |
| Table | `--format table` | Human-readable terminal output |
| CSV | `--format csv` | Spreadsheets, data import |
| Plain | `--format plain` | Minimal text output |

---

## Troubleshooting

### "command not found: mp"

Your Python scripts directory isn't on your `PATH`. Try running with the full path:

```bash
python3 -m mixpanel_headless --version
```

Or find where pip installed it:

```bash
pip show mixpanel_headless
```

If using `uv`, make sure the virtual environment is activated.

### "Authentication failed" or "401 Unauthorized"

- Double-check your service account username and secret in Mixpanel (Settings > Service Accounts)
- Verify your project ID matches the project the service account has access to
- Make sure the region flag matches your project's data residency
- Run `mp account test <name>` to see the specific error message

### "No credentials configured"

Run one of:

```bash
# OAuth browser (interactive PKCE flow)
mp account add personal --type oauth_browser --region us
mp account login personal

# Service account
mp account add my-project --type service_account \
    --username YOUR_USERNAME --project YOUR_PROJECT_ID --region us
```

### OAuth Token Expired

```bash
# Re-authenticate (refresh token revoked or expired)
mp account login <name>
```

### Plugin Not Working in Claude Code

1. Make sure plugins are enabled in your Claude Code settings
2. Run `/mixpanel-headless:setup` to install dependencies
3. Check auth with `/mixpanel-headless:auth session`
4. If the plugin doesn't appear, try restarting Claude Code

### Cowork VM Can't Find Credentials

1. On your **local machine**, run: `mp account export-bridge --to ~/.claude/mixpanel/auth.json`
2. Verify with: `mp session --bridge`
3. Inside the Cowork session, run: `/mixpanel-headless:setup`

---

## Next Steps

Now that you're set up, here's where to go next:

- **Full documentation**: [mixpanel.github.io/mixpanel-headless](https://mixpanel.github.io/mixpanel-headless/)
- **Insights query guide**: [Query documentation](https://mixpanel.github.io/mixpanel-headless/guide/query/)
- **Funnel queries**: [Funnel documentation](https://mixpanel.github.io/mixpanel-headless/guide/query-funnels/)
- **Retention queries**: [Retention documentation](https://mixpanel.github.io/mixpanel-headless/guide/query-retention/)
- **Flow queries**: [Flow documentation](https://mixpanel.github.io/mixpanel-headless/guide/query-flows/)
- **CLI reference**: [CLI documentation](https://mixpanel.github.io/mixpanel-headless/cli/)
- **Python API reference**: [API documentation](https://mixpanel.github.io/mixpanel-headless/api/)
- **DeepWiki**: [![Ask DeepWiki](https://deepwiki.com/badge.svg)](https://deepwiki.com/mixpanel/mixpanel-headless)

For every CLI command, `--help` shows complete usage information:

```bash
mp query --help
mp query segmentation --help
mp inspect events --help
```

In the Python API, all return values are typed dataclasses — your IDE will show you every available field and method.
