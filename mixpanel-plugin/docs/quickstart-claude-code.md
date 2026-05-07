# Quick Start: mixpanel_headless + Claude Code

Get Claude answering questions about your Mixpanel data in under 5 minutes. No coding required — Claude writes and runs the Python for you.

---

## What You'll Need

- **Claude Code** — [CLI](https://docs.anthropic.com/en/docs/claude-code/overview), [desktop app](https://docs.anthropic.com/en/docs/claude-code/desktop), [web app](https://claude.ai/code), or [IDE extension](https://docs.anthropic.com/en/docs/claude-code/ide-integrations) (VS Code, JetBrains)
- **A Mixpanel account** with access to a project
- **Your Project ID** — find it in Mixpanel under Settings > Project Details
- **A service account** (username + secret) from Mixpanel under Settings > Service Accounts, OR a browser available for OAuth login

---

## Step 1: Install the Plugin

Open Claude Code and run:

```
/plugin marketplace add mixpanel/mixpanel-headless
/plugin install mixpanel-headless@mixpanel-headless-marketplace
```

This installs the `mixpanel-headless` plugin, which teaches Claude how to be a Mixpanel analytics expert.

---

## Step 2: Run Setup

```
/mixpanel-headless:setup
```

This installs the `mixpanel_headless` Python package and all analysis dependencies (pandas, matplotlib, networkx, etc.). It takes about a minute.

At the end, setup checks for Mixpanel credentials. If you see a warning about missing credentials, continue to Step 3.

---

## Step 3: Authenticate

You only need to do this once. Choose the method that works best for you.

### Option A: Service Account (Recommended)

Run the `/mixpanel-headless:auth` command:

```
/mixpanel-headless:auth account add my-project
```

Claude will walk you through it step by step:

1. You provide your **account name** (any label you want, like "production")
2. You provide your **service account username** (starts with something like `sa.`)
3. You provide your **project ID** (a number)
4. You provide your **region** (`us`, `eu`, or `in`)
5. Claude gives you a command to run that securely collects your secret with hidden input

Your secret is never visible in the conversation.

> If your account has access to multiple projects, you can switch later with `/mixpanel-headless:auth project use <id>`. Run `/mixpanel-headless:auth project list` to see what's available.

### Option B: OAuth Login (Browser-Based)

```
/mixpanel-headless:auth account add personal --type oauth_browser --region us
/mixpanel-headless:auth account login personal
```

The first command registers an OAuth browser account; the second opens a browser window where you log in with your Mixpanel credentials. After login, your default project is backfilled automatically from the post-login `/me` probe. Use `/mixpanel-headless:auth project list` then `/mixpanel-headless:auth project use <id>` to switch if you have multiple projects.

### Option C: Raw OAuth Bearer Token (CI / Agents)

If a managed OAuth client (e.g., a CI pipeline) hands you a pre-obtained access token, inject it via env vars without going through the browser:

```bash
export MP_OAUTH_TOKEN="<bearer-token>"
export MP_PROJECT_ID="12345"
export MP_REGION="us"  # or "eu", "in"
```

The full service-account env-var set (`MP_USERNAME` + `MP_SECRET` + `MP_PROJECT_ID` + `MP_REGION`) takes precedence when both sets are complete.

### Verify It Worked

```
/mixpanel-headless:auth account test
```

You should see confirmation that Claude connected successfully and found events in your project.

---

## Step 4: Start Asking Questions

That's it — you're ready. Just ask questions in plain English:

```
How many signups did we get last week?
```

```
Where do users drop off in our onboarding flow?
```

```
Show me daily active users for the past 90 days, broken down by platform.
```

```
Do users who complete the tutorial retain better than those who skip it?
```

```
What's the most common path users take after signing up?
```

```
Build me a weekly KPI dashboard showing signups, activation, and revenue.
```

Claude automatically:
- Discovers your events and properties
- Chooses the right query engine (Insights, Funnels, Retention, or Flows)
- Writes and runs Python code using `mixpanel_headless` + `pandas`
- Explains the results in plain language

---

## What's Happening Under the Hood

When you ask a question, Claude writes Python like this:

```python
import mixpanel_headless as mp

ws = mp.Workspace()

# Insights: "How many signups last week?"
result = ws.query("Signup", last=7, unit="day")
print(result.df)

# Funnels: "Where do users drop off?"
funnel = ws.query_funnel(["Signup", "Onboarding", "Purchase"], last=30)
print(funnel.overall_conversion_rate)

# Retention: "Do users come back?"
retention = ws.query_retention("Signup", "Login", retention_unit="week", last=90)
print(retention.df)

# Flows: "What paths do users take?"
flow = ws.query_flow("Signup", forward=4)
print(flow.top_transitions(5))
```

You never need to write this yourself, but it's helpful to know what's possible. Claude uses five query engines:

| Engine | Method | Answers |
|--------|--------|---------|
| Insights | `ws.query()` | How many? How much? What's trending? |
| Funnels | `ws.query_funnel()` | Do users convert through a sequence? |
| Retention | `ws.query_retention()` | Do users come back after an action? |
| Flows | `ws.query_flow()` | What paths do users take? |
| Users | `ws.query_user()` | Who are they? What do they look like? |

---

## Managing Accounts

### Check current session (active account / project / workspace)

```
/mixpanel-headless:auth session
```

### Switch between accounts

```
/mixpanel-headless:auth account list
/mixpanel-headless:auth account use production
```

### Discover accessible projects

```
/mixpanel-headless:auth project list
```

### Switch projects

```
/mixpanel-headless:auth project use 67890
```

### Switch workspaces

```
/mixpanel-headless:auth workspace list
/mixpanel-headless:auth workspace use 3448414
```

### Remove an account

The slash command focuses on read + onboarding flows; destructive lifecycle
operations stay on the CLI. Run them in your terminal (or via the `!`
shell prefix inside Claude Code):

```
! mp account remove my-old-project
```

### Revoke OAuth tokens

```
! mp account logout my-account-name
```

### Save a named target (account + project + optional workspace)

```
/mixpanel-headless:auth target add ecom --account team --project 3018488
/mixpanel-headless:auth target use ecom
```

---

## Troubleshooting

### "No credentials configured"

Run `/mixpanel-headless:auth account add my-project` and follow the prompts, or `/mixpanel-headless:auth account add personal --type oauth_browser --region us` followed by `/mixpanel-headless:auth account login personal` for OAuth.

### "Authentication failed"

- Check that your service account username and secret are correct (Mixpanel Settings > Service Accounts)
- Verify your project ID matches the project the service account has access to
- Make sure the region matches your project's data residency
- Run `/mixpanel-headless:auth account test` for detailed error information

### "OAuth token expired" or OAuth login stopped working

Run `/mixpanel-headless:auth account login <name>` again to refresh your tokens. If you switch to a service account instead, run `/mixpanel-headless:auth account add <name> --type service_account ...` — service account credentials don't expire.

### Plugin not appearing

1. Make sure plugins are enabled in your Claude Code settings
2. Restart Claude Code after installing the plugin
3. Run `/mixpanel-headless:setup` again

### Setup fails to install packages

If you're behind a corporate proxy or firewall, you may need to configure `pip` or `uv` with your proxy settings before running setup.

---

## Next Steps

- **Full documentation**: [mixpanel.github.io/mixpanel-headless](https://mixpanel.github.io/mixpanel-headless/)
- **Plugin details**: [Plugin README](https://github.com/mixpanel/mixpanel-headless/blob/main/mixpanel-plugin/README.md)
- **Comprehensive getting started guide**: [Getting Started Guide](getting-started-guide.md) — covers the Python library and CLI in depth
- **Using with Cowork**: [Cowork Quick Start](quickstart-claude-cowork.md)
