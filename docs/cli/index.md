# CLI Overview

The `mp` command provides full access to mixpanel_headless functionality from the command line.

!!! tip "Explore on DeepWiki"
    🤖 **[CLI Usage Guide →](https://deepwiki.com/mixpanel/mixpanel-headless/3.1-cli-usage)**

    Ask questions about CLI commands, explore options, or get help with specific workflows.

## Installation

The CLI is installed automatically with the package:

```bash
pip install mixpanel_headless
```

Verify installation:

```bash
mp --version
```

## Global Options

| Option | Short | Description |
|--------|-------|-------------|
| `--account` | `-a` | Account name to use (env: `MP_ACCOUNT`) |
| `--project` | `-p` | Project ID override (env: `MP_PROJECT_ID`) |
| `--workspace` | `-w` | Workspace ID override (env: `MP_WORKSPACE_ID`) |
| `--target` | `-t` | Apply a saved target (env: `MP_TARGET`) — mutually exclusive with `-a`/`-p`/`-w` |
| `--quiet` | `-q` | Suppress progress output |
| `--verbose` | `-v` | Enable debug output |
| `--version` | | Show version and exit |
| `--help` | | Show help and exit |

These resolve via the priority chain `env > param > target > bridge > [active] > default_project`. See [Configuration → Credential Resolution Chain](../getting-started/configuration.md#credential-resolution-chain).

## Command Groups

### login — Frictionless Authentication

`mp login` is the recommended starter command. It composes auth-type detection, `/me` lookup, project picker, and account-name derivation into a single call:

| Command | Description |
|---------|-------------|
| `mp login` | One-shot login (browser PKCE by default; auto-detects SA / static-bearer paths from env) |

Useful flags: `--region {us\|eu\|in}` sets the region (required for EU / India when using the browser path; SA and oauth_token paths probe automatically when `--region` is omitted), `--project ID` skips the picker, `--name NAME` overrides the derived account name, `--service-account` / `--token-env VAR` force a non-browser path, `--no-browser` prints the authorization URL instead of launching a browser, `--secret-stdin` reads the SA secret from stdin.

The auth-type detection ladder (in priority order): explicit `--service-account` / `--token-env` flag → `MP_USERNAME` + `MP_SECRET` set → `MP_OAUTH_TOKEN` set → otherwise `oauth_browser`. Region behavior: SA and oauth_token paths probe `us → eu → in` when `--region` is omitted; the browser path defaults to `us`. See [Configuration → Quick Start](../getting-started/configuration.md#quick-start-mp-login) for examples.

### account — Account Management

Manage configured accounts (service accounts, OAuth browser, OAuth token) and the active account. For first-time setup, prefer `mp login` above; the `account` group is for explicit registration, rotation, and lifecycle management.

| Command | Description |
|---------|-------------|
| `mp account list` | List configured accounts (active marked with `*`) |
| `mp account add` | Register a new account (`--type {service_account, oauth_browser, oauth_token}`) |
| `mp account update` | Rotate region / secret / token / default_project on an existing account |
| `mp account remove` | Delete an account (`--force` orphans dependent targets) |
| `mp account use` | Switch the active account (clears workspace) |
| `mp account show` | Display account metadata (omit name for active) |
| `mp account test` | Probe `/me`; returns `AccountTestResult` |
| `mp account login` | Run the OAuth browser PKCE flow (oauth_browser only) — `mp login --name NAME` is the unified equivalent |
| `mp account logout` | Delete on-disk OAuth tokens (oauth_browser only) |
| `mp account token` | Print the bearer token (for piping to curl etc.) |
| `mp account export-bridge` | Write a v2 Cowork bridge file |
| `mp account remove-bridge` | Delete the bridge file (idempotent) |

### project — Project Switching

Discover and switch the active Mixpanel project (resolved against the active account's `/me` response).

| Command | Description |
|---------|-------------|
| `mp project list` | List accessible projects |
| `mp project use` | Persist the active project (writes to the active account's `default_project`) |
| `mp project show` | Show the active project |

### workspace — Workspace Switching

Discover and switch the active workspace within the current project.

| Command | Description |
|---------|-------------|
| `mp workspace list` | List workspaces for the current project |
| `mp workspace use` | Persist the active workspace (writes to `[active].workspace`) |
| `mp workspace show` | Show the active workspace |

### target — Saved Targets

A target is a saved (account, project, optional workspace) bundle — a named cursor position you can apply with one command.

| Command | Description |
|---------|-------------|
| `mp target list` | List configured targets |
| `mp target add` | Register a new target (`--account A --project P [--workspace W]`) |
| `mp target use` | Apply a target atomically (writes all three `[active]` axes in one save) |
| `mp target show` | Show target details |
| `mp target remove` | Delete a target |

### session — Active Session Inspection

Show the resolved active session — account, project, workspace, user.

| Command | Description |
|---------|-------------|
| `mp session` | Print the active session (`-f json` for machine-readable output) |
| `mp session --bridge` | Show bridge-resolved state (Cowork integration) |

### query — Query Operations

Execute live analytics queries against the Mixpanel API.

| Command | Description |
|---------|-------------|
| `mp query segmentation` | Time-series event counts |
| `mp query funnel` | Funnel conversion analysis |
| `mp query retention` | Cohort retention analysis |
| `mp query jql` | Execute JQL scripts |
| `mp query event-counts` | Multi-event time series |
| `mp query property-counts` | Property breakdown time series |
| `mp query activity-feed` | User event history |
| `mp query saved-report` | Query saved reports (Insights, Retention, Funnel) |
| `mp query flows` | Query saved Flows reports |
| `mp query frequency` | Event frequency distribution |
| `mp query segmentation-numeric` | Numeric property bucketing |
| `mp query segmentation-sum` | Numeric property sum |
| `mp query segmentation-average` | Numeric property average |

!!! tip "Saved Reports Workflow"
    Use `mp inspect bookmarks` to list available saved reports and get their IDs, then query them with `mp query saved-report` or `mp query flows`.

### inspect — Schema Discovery

Explore your Mixpanel project schema.

| Command | Description |
|---------|-------------|
| `mp inspect events` | List event names |
| `mp inspect properties` | List properties for an event |
| `mp inspect values` | List values for a property |
| `mp inspect funnels` | List saved funnels |
| `mp inspect cohorts` | List saved cohorts |
| `mp inspect bookmarks` | List saved reports (bookmarks) |
| `mp inspect top-events` | List today's top events |
| `mp inspect lexicon-schemas` | List Lexicon schemas from data dictionary |
| `mp inspect lexicon-schema` | Get a single Lexicon schema |
| `mp inspect distribution` | Property value distribution (JQL) |
| `mp inspect numeric` | Numeric property statistics (JQL) |
| `mp inspect daily` | Daily event counts (JQL) |
| `mp inspect engagement` | User engagement distribution (JQL) |
| `mp inspect coverage` | Property coverage analysis (JQL) |

### dashboards — Dashboard Management

Manage Mixpanel dashboards via the App API.

| Command | Description |
|---------|-------------|
| `mp dashboards list` | List dashboards |
| `mp dashboards create` | Create a new dashboard |
| `mp dashboards get` | Get dashboard by ID |
| `mp dashboards update` | Update a dashboard |
| `mp dashboards delete` | Delete a dashboard |
| `mp dashboards bulk-delete` | Delete multiple dashboards |
| `mp dashboards favorite` | Favorite a dashboard |
| `mp dashboards unfavorite` | Unfavorite a dashboard |
| `mp dashboards pin` | Pin a dashboard |
| `mp dashboards unpin` | Unpin a dashboard |
| `mp dashboards add-report` | Add a report to a dashboard |
| `mp dashboards remove-report` | Remove a report from a dashboard |
| `mp dashboards blueprints` | List blueprint templates |
| `mp dashboards blueprint-create` | Create dashboard from blueprint |
| `mp dashboards rca` | Create RCA dashboard |
| `mp dashboards erf` | Get dashboard ERF metrics |
| `mp dashboards update-report-link` | Update a report link on a dashboard |
| `mp dashboards update-text-card` | Update a text card on a dashboard |

### reports — Report Management

Manage Mixpanel reports (bookmarks) via the App API.

| Command | Description |
|---------|-------------|
| `mp reports list` | List reports with optional type/ID filters |
| `mp reports create` | Create a new report |
| `mp reports get` | Get report by ID |
| `mp reports update` | Update a report |
| `mp reports delete` | Delete a report |
| `mp reports bulk-delete` | Delete multiple reports |
| `mp reports bulk-update` | Update multiple reports |
| `mp reports linked-dashboards` | Get dashboards containing a report |
| `mp reports dashboard-ids` | Get dashboard IDs for a report |
| `mp reports history` | Get report change history |

### cohorts — Cohort Management

Manage Mixpanel cohorts via the App API.

| Command | Description |
|---------|-------------|
| `mp cohorts list` | List cohorts with optional filters |
| `mp cohorts create` | Create a new cohort |
| `mp cohorts get` | Get cohort by ID |
| `mp cohorts update` | Update a cohort |
| `mp cohorts delete` | Delete a cohort |
| `mp cohorts bulk-delete` | Delete multiple cohorts |
| `mp cohorts bulk-update` | Update multiple cohorts |

### flags — Feature Flag Management

Manage Mixpanel feature flags via the App API. Feature flags are project-scoped (no workspace ID required).

| Command | Description |
|---------|-------------|
| `mp flags list` | List feature flags |
| `mp flags create` | Create a new feature flag |
| `mp flags get` | Get feature flag by ID |
| `mp flags update` | Update a feature flag (full replacement) |
| `mp flags delete` | Delete a feature flag |
| `mp flags archive` | Archive a feature flag |
| `mp flags restore` | Restore an archived feature flag |
| `mp flags duplicate` | Duplicate a feature flag |
| `mp flags set-test-users` | Set test user variant overrides |
| `mp flags history` | View flag change history |
| `mp flags limits` | View account-level flag usage and limits |

### experiments — Experiment Management

Manage Mixpanel experiments via the App API. Experiments are project-scoped (no workspace ID required).

| Command | Description |
|---------|-------------|
| `mp experiments list` | List experiments |
| `mp experiments create` | Create a new experiment |
| `mp experiments get` | Get experiment by ID |
| `mp experiments update` | Update an experiment |
| `mp experiments delete` | Delete an experiment |
| `mp experiments launch` | Launch a draft experiment |
| `mp experiments conclude` | Conclude an active experiment |
| `mp experiments decide` | Decide experiment outcome |
| `mp experiments archive` | Archive an experiment |
| `mp experiments restore` | Restore an archived experiment |
| `mp experiments duplicate` | Duplicate an experiment |
| `mp experiments erf` | List ERF experiments |

### alerts — Alert Management

Manage Mixpanel custom alerts via the App API.

| Command | Description |
|---------|-------------|
| `mp alerts list` | List custom alerts |
| `mp alerts create` | Create a new alert |
| `mp alerts get` | Get alert by ID |
| `mp alerts update` | Update an alert |
| `mp alerts delete` | Delete an alert |
| `mp alerts bulk-delete` | Delete multiple alerts |
| `mp alerts count` | Get alert count and limits |
| `mp alerts history` | View alert trigger history |
| `mp alerts test` | Send a test notification |
| `mp alerts screenshot` | Get alert screenshot URL |
| `mp alerts validate` | Validate alerts against a bookmark |

### annotations — Annotation Management

Manage timeline annotations via the App API.

| Command | Description |
|---------|-------------|
| `mp annotations list` | List annotations with optional date/tag filters |
| `mp annotations create` | Create a new annotation |
| `mp annotations get` | Get annotation by ID |
| `mp annotations update` | Update an annotation |
| `mp annotations delete` | Delete an annotation |
| `mp annotations tags list` | List annotation tags |
| `mp annotations tags create` | Create a new annotation tag |

### webhooks — Webhook Management

Manage project webhooks via the App API.

| Command | Description |
|---------|-------------|
| `mp webhooks list` | List project webhooks |
| `mp webhooks create` | Create a new webhook |
| `mp webhooks update` | Update a webhook |
| `mp webhooks delete` | Delete a webhook |
| `mp webhooks test` | Test webhook connectivity |

### lexicon — Data Governance: Lexicon Management, Enforcement, Auditing & Deletion

Manage Lexicon data definitions, tags, metadata, schema enforcement, data auditing, volume anomalies, and event deletion requests via the App API.

| Command | Description |
|---------|-------------|
| `mp lexicon events get` | Get event definitions by name |
| `mp lexicon events update` | Update an event definition |
| `mp lexicon events delete` | Delete an event definition |
| `mp lexicon events bulk-update` | Bulk-update event definitions |
| `mp lexicon properties get` | Get property definitions by name |
| `mp lexicon properties update` | Update a property definition |
| `mp lexicon properties bulk-update` | Bulk-update property definitions |
| `mp lexicon tags list` | List all Lexicon tags |
| `mp lexicon tags create` | Create a new tag |
| `mp lexicon tags update` | Update a tag |
| `mp lexicon tags delete` | Delete a tag |
| `mp lexicon tracking-metadata` | Get tracking metadata for an event |
| `mp lexicon event-history` | Get change history for an event |
| `mp lexicon property-history` | Get change history for a property |
| `mp lexicon export` | Export Lexicon data definitions |
| `mp lexicon audit` | Run schema audit to find violations |
| `mp lexicon enforcement get` | Get schema enforcement settings |
| `mp lexicon enforcement init` | Initialize schema enforcement |
| `mp lexicon enforcement update` | Update schema enforcement (PATCH) |
| `mp lexicon enforcement replace` | Replace schema enforcement (PUT) |
| `mp lexicon enforcement delete` | Delete schema enforcement settings |
| `mp lexicon anomalies list` | List data volume anomalies |
| `mp lexicon anomalies update` | Update a data volume anomaly |
| `mp lexicon anomalies bulk-update` | Bulk-update data volume anomalies |
| `mp lexicon deletion-requests list` | List event deletion requests |
| `mp lexicon deletion-requests create` | Create an event deletion request |
| `mp lexicon deletion-requests cancel` | Cancel a pending deletion request |
| `mp lexicon deletion-requests preview` | Preview deletion filter results |

### drop-filters — Data Governance: Drop Filter Management

Manage event drop filters via the App API.

| Command | Description |
|---------|-------------|
| `mp drop-filters list` | List all drop filters |
| `mp drop-filters create` | Create a new drop filter |
| `mp drop-filters update` | Update a drop filter |
| `mp drop-filters delete` | Delete a drop filter |
| `mp drop-filters limits` | Get drop filter usage limits |

### custom-properties — Data Governance: Custom Property Management

Manage custom computed properties via the App API.

| Command | Description |
|---------|-------------|
| `mp custom-properties list` | List all custom properties |
| `mp custom-properties get` | Get a custom property by ID |
| `mp custom-properties create` | Create a new custom property |
| `mp custom-properties update` | Update a custom property |
| `mp custom-properties delete` | Delete a custom property |
| `mp custom-properties validate` | Validate a custom property definition |

### custom-events — Data Governance: Custom Event Management

Manage custom composite events via the App API.

| Command | Description |
|---------|-------------|
| `mp custom-events list` | List all custom events |
| `mp custom-events update` | Update a custom event |
| `mp custom-events delete` | Delete a custom event |

### lookup-tables — Data Governance: Lookup Table Management

Manage CSV-based lookup tables for property enrichment via the App API.

| Command | Description |
|---------|-------------|
| `mp lookup-tables list` | List lookup tables |
| `mp lookup-tables upload` | Upload a CSV as a new lookup table |
| `mp lookup-tables update` | Update a lookup table |
| `mp lookup-tables delete` | Delete lookup tables |
| `mp lookup-tables download` | Download lookup table data as CSV |
| `mp lookup-tables upload-url` | Get a signed upload URL |
| `mp lookup-tables download-url` | Get a signed download URL |

### schemas — Data Governance: Schema Registry Management

Manage JSON Schema Draft 7 definitions in the schema registry via the App API.

| Command | Description |
|---------|-------------|
| `mp schemas list` | List schema registry entries |
| `mp schemas create` | Create a single schema entry |
| `mp schemas create-bulk` | Bulk create schema entries |
| `mp schemas update` | Update a schema entry (merge semantics) |
| `mp schemas update-bulk` | Bulk update schema entries |
| `mp schemas delete` | Delete schema entries |

## Output Formats

All commands support the `--format` option:

| Format | Description | Use Case |
|--------|-------------|----------|
| `json` | Pretty-printed JSON | Default, human-readable |
| `jsonl` | JSON Lines | Streaming, large datasets |
| `table` | Rich formatted table | Terminal viewing |
| `csv` | CSV with headers | Spreadsheet export |
| `plain` | Minimal text | Scripting |

## Filtering with --jq

Commands that output JSON also support the `--jq` option for client-side filtering using jq syntax. This enables powerful transformations without external tools.

```bash
# Get first 5 events
mp inspect events --format json --jq '.[:5]'

# Filter events by name pattern
mp inspect events --format json --jq '.[] | select(startswith("User"))'

# Count results
mp inspect events --format json --jq 'length'

# Extract specific fields from query results
mp query segmentation --event Purchase --from 2025-01-01 --to 2025-01-31 \
  --format json --jq '.series | to_entries | map({date: .key, count: .value})'

```

!!! note "--jq requires JSON format"
    The `--jq` option only works with `--format json` or `--format jsonl`. Using it with other formats produces an error.

See the [jq manual](https://jqlang.org/manual/) for filter syntax.

### Format Examples

Given this query result:

**json** (default) — Pretty-printed, easy to read:

```json
[
  {
    "event_name": "Purchase",
    "count": 1523
  },
  {
    "event_name": "Signup",
    "count": 892
  },
  {
    "event_name": "Login",
    "count": 4201
  }
]
```

**jsonl** — One object per line, ideal for streaming:

```
{"event_name": "Purchase", "count": 1523}
{"event_name": "Signup", "count": 892}
{"event_name": "Login", "count": 4201}
```

**table** — Rich ASCII table for terminal viewing:

```
┏━━━━━━━━━━━━━┳━━━━━━━┓
┃ EVENT NAME  ┃ COUNT ┃
┡━━━━━━━━━━━━━╇━━━━━━━┩
│ Purchase    │ 1523  │
│ Signup      │ 892   │
│ Login       │ 4201  │
└─────────────┴───────┘
```

**csv** — Headers plus comma-separated values:

```csv
event_name,count
Purchase,1523
Signup,892
Login,4201
```

**plain** — Minimal output, one value per line:

```
Purchase
Signup
Login
```

### Choosing a Format

```bash
# Terminal viewing
mp inspect events --format table

# Pipe to jq for processing
mp query segmentation "Purchase" --from 2025-01-01 --format json | jq '.values'

# Count results
mp inspect events --format plain | wc -l
```

## Exit Codes

| Code | Meaning | Exception |
|------|---------|-----------|
| 0 | Success | — |
| 1 | General error | `MixpanelHeadlessError`, `WorkspaceScopeError`, `AccountInUseError` |
| 2 | Authentication error | `AuthenticationError`, `OAuthError` |
| 3 | Invalid arguments | `ConfigError`, validation errors |
| 4 | Resource not found | `AccountNotFoundError`, `ProjectNotFoundError` |
| 5 | Rate limit exceeded | `RateLimitError` |
| 130 | Interrupted | Ctrl+C |

## Environment Variables

These resolve via `env > param > target > bridge > [active] > default_project` — see [Configuration → Credential Resolution Chain](../getting-started/configuration.md#credential-resolution-chain).

| Variable | Description |
|----------|-------------|
| `MP_ACCOUNT` | Active account override |
| `MP_PROJECT_ID` | Project override |
| `MP_WORKSPACE_ID` | Workspace override |
| `MP_TARGET` | Apply a saved target (mutually exclusive with `MP_ACCOUNT`/`MP_PROJECT_ID`/`MP_WORKSPACE_ID`) |
| `MP_OAUTH_TOKEN` | Static bearer token (alternative to a registered account; env-var path requires `MP_PROJECT_ID` + `MP_REGION`) |
| `MP_USERNAME` | Service-account username (requires `MP_SECRET`, `MP_PROJECT_ID`, `MP_REGION`) |
| `MP_SECRET` | Service-account secret (paired with `MP_USERNAME`) |
| `MP_REGION` | Data residency region (`us`, `eu`, `in`) |
| `MP_AUTH_FILE` | Override path to the v2 Cowork bridge file |
| `MP_CONFIG_PATH` | Override config file path (`~/.mp/config.toml`) |
| `MP_OAUTH_STORAGE_DIR` | Override storage root (`~/.mp`) |

## Examples

### Complete Workflow

```bash
# 1. Authenticate (browser PKCE; picks project, derives name from /me)
mp login

# 2. Explore schema
mp inspect events
mp inspect properties --event Purchase

# 3. Run live queries
mp query segmentation --event Purchase --from 2025-01-01 --to 2025-01-31 --format table
```

For explicit account names or non-browser flows, use `mp login --name personal --region us` or the two-step `mp account add` + `mp account login` (see [account — Account Management](#account-account-management) above).

### Piping and Scripting

```bash
# Built-in jq filtering (no external tools needed)
mp query segmentation --event Login --from 2025-01-01 --to 2025-01-31 \
    --format json --jq '.series | keys | length'

# Or pipe to external jq
mp query segmentation --event Login --from 2025-01-01 --to 2025-01-31 --format json \
    | jq '.values."$overall"'
```

### Streaming Data

Streaming is available through the Python API:

```python
import mixpanel_headless as mp

ws = mp.Workspace()

# Stream events
for event in ws.stream_events(from_date="2025-01-01", to_date="2025-01-31"):
    print(event)

# Stream profiles
for profile in ws.stream_profiles():
    print(profile)
```

## Full Command Reference

See [Commands](commands.md) for the complete auto-generated reference.
