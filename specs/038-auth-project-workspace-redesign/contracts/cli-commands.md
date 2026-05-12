# CLI Command Contracts: Auth, Project & Workspace Management

**Phase 1 Output** | **Date**: 2026-04-07

## New Command Groups

### mp projects

```
mp projects list [--refresh] [--format json|table|csv]
  Description: List all accessible projects for current credentials
  Source: /me API (cached 24h)
  Output fields: project_id, name, organization_id, timezone, has_workspaces, type
  Exit codes: 0=success, 2=auth error

mp projects switch <project-id>
  Description: Set active project (persists to config)
  Side effects: Updates [active].project_id in config; auto-selects default workspace
  Output: Confirmation with project name
  Exit codes: 0=success, 4=project not found

mp projects show
  Description: Show current active project
  Output fields: project_id, name, organization_id, timezone, workspace_id
  Exit codes: 0=success, 0=no project set (prints message to stderr)

mp projects refresh
  Description: Force-refresh the /me cache
  Side effects: Invalidates cache, calls /me API, stores new response
  Output: Confirmation with project count
  Exit codes: 0=success, 2=auth error

mp projects alias add <name> --project <id> [--credential <name>] [--workspace <id>]
  Description: Create a named project alias for quick switching
  Side effects: Adds entry to [projects] section in config
  Exit codes: 0=success, 1=alias already exists

mp projects alias remove <name>
  Description: Remove a project alias
  Exit codes: 0=success, 4=alias not found

mp projects alias list [--format json|table|csv]
  Description: List all project aliases
  Output fields: name, project_id, credential, workspace_id
  Exit codes: 0=success
```

### mp workspaces

```
mp workspaces list [--project <id>] [--format json|table|csv]
  Description: List workspaces for a project (defaults to active project)
  Source: /me API cache or /projects/{id}/workspaces/public fallback
  Output fields: id, name, is_default, is_global, description
  Exit codes: 0=success, 4=project not found, 0=no workspaces (message to stderr)

mp workspaces switch <workspace-id>
  Description: Set active workspace (persists to config)
  Side effects: Updates [active].workspace_id in config
  Output: Confirmation with workspace name
  Exit codes: 0=success, 4=workspace not found

mp workspaces show
  Description: Show current active workspace
  Output fields: id, name, project_id, is_default
  Exit codes: 0=success, 0=no workspace set (message to stderr)
```

### mp context

```
mp context show [--format json|table]
  Description: Display full current context
  Output fields: credential (name, type, region), project (id, name), workspace (id, name)
  Exit codes: 0=success

mp context switch <alias>
  Description: Switch to a named project alias (updates credential + project + workspace)
  Side effects: Updates all three [active] fields from the alias definition
  Exit codes: 0=success, 4=alias not found
```

## Modified Existing Commands

### mp auth add (simplified)

```
mp auth add <name> -u <username> [--region <region>] [--project <id>] [--default] [--interactive] [--secret-stdin]
  Change: --project is now OPTIONAL (was required)
  Without --project: Creates [credentials.name] only (v2 mode)
  With --project: Creates [credentials.name] AND [projects.name] (backward compat)
  Secret input: Interactive prompt (default), --secret-stdin, or MP_SECRET env var
```

### mp auth list

```
mp auth list [--format json|table]
  Change: Shows credentials (v2) or accounts (v1) depending on config version
  v2 output fields: name, type, region, is_active
  v1 output fields: name, username, project_id, region, is_default (unchanged)
```

### mp auth status (enhanced)

```
mp auth status [--format json|table]
  Change: Enhanced to show active context alongside auth info
  Additional output: active credential, active project, active workspace
  Unchanged: OAuth token status per region
```

### mp auth migrate (new subcommand)

```
mp auth migrate [--dry-run]
  Description: Migrate v1 config to v2 format
  Side effects: Backs up to config.toml.v1.bak, writes v2 config
  --dry-run: Show what would change without writing
  Output: Migration summary (credentials created, aliases created, active context)
  Exit codes: 0=success, 1=already v2, 1=migration error
```

## New Global Options

```
--credential, -c <name>    Override active credential for this command only
--project, -p <id>         Override active project for this command only
--account, -a <name>       Legacy: named account (unchanged, backward compat)
--workspace-id <id>        Override workspace (unchanged)
--region <region>          Override region (unchanged)
```

**Priority when combining flags**: `--account` is mutually exclusive with `--credential`/`--project`. If both are provided, error with clear message.

## Output Format Contracts

All new commands support `--format` with these options:

| Format | Description | Default for |
|--------|-------------|------------|
| `json` | Pretty-printed JSON object/array | All commands |
| `table` | Rich table (human-readable) | - |
| `csv` | CSV with headers | - |

JSON is the default format for all new commands (agent-native design).

## Exit Code Contracts

| Code | Meaning | When |
|------|---------|------|
| 0 | Success | Normal completion |
| 1 | General error | Migration failed, alias exists, etc. |
| 2 | Authentication error | Invalid/expired credentials |
| 3 | Invalid arguments | Bad flags, missing required args |
| 4 | Not found | Project/workspace/alias doesn't exist |
| 5 | Rate limit | /me API rate limited |
