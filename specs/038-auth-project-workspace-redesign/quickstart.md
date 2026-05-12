# Quickstart: Auth, Project & Workspace Management

**Phase 1 Output** | **Date**: 2026-04-07

## For New Users

### 1. Add credentials

```bash
mp auth add my-sa -u "your-username.abc123.mp-service-account"
# Enter secret when prompted
```

### 2. Discover your projects

```bash
mp projects list
```

### 3. Select a project

```bash
mp projects switch 3713224
```

### 4. Start querying

```bash
mp query segmentation -e Login --from 2025-01-01 --to 2025-01-31
```

## For Existing Users

### Migrate from v1 config (optional)

```bash
# Preview what will change
mp auth migrate --dry-run

# Run migration (backs up original config)
mp auth migrate
```

### Everything still works

```bash
# Existing commands work unchanged
mp auth list
mp query segmentation -e Login --from 2025-01-01 --to 2025-01-31

# Existing Python API works unchanged
ws = Workspace(account="ai-demo")
```

## For Python Users

### Discover and switch projects

```python
import mixpanel_data as mp

ws = mp.Workspace()

# See all accessible projects
for pid, info in ws.discover_projects():
    print(f"{pid}: {info.name}")

# Switch to a project
ws.switch_project("3713224")

# See workspaces
for w in ws.discover_workspaces():
    print(f"  {w.id}: {w.name} {'(default)' if w.is_default else ''}")

# Query
result = ws.segmentation(event="Login", from_date="2025-01-01", to_date="2025-01-31")
```

### Direct construction

```python
# New style: credential + project
ws = mp.Workspace(credential="demo-sa", project_id="3713224")

# Legacy style: still works
ws = mp.Workspace(account="ai-demo")

# Env vars: still highest priority
# MP_USERNAME + MP_SECRET + MP_PROJECT_ID + MP_REGION
ws = mp.Workspace()
```

## For AI Agents

### Programmatic discovery

```python
ws = mp.Workspace()

# List all projects
projects = ws.discover_projects()

# Pick the one you need
ws.switch_project(projects[0][0])

# Work with it
events = ws.events()
result = ws.segmentation(event=events[0], from_date="2025-01-01", to_date="2025-01-31")

# Switch to another project (same credentials, instant)
ws.switch_project(projects[1][0])
```

## Quick Reference

| Task | CLI | Python |
|------|-----|--------|
| Add credentials | `mp auth add <name> -u <user>` | `ConfigManager().add_credential(...)` |
| List projects | `mp projects list` | `ws.discover_projects()` |
| Switch project | `mp projects switch <id>` | `ws.switch_project("id")` |
| List workspaces | `mp workspaces list` | `ws.discover_workspaces()` |
| Switch workspace | `mp workspaces switch <id>` | `ws.switch_workspace(id)` |
| Show context | `mp context show` | `ws.current_project`, `ws.current_credential` |
| Create alias | `mp projects alias add <n>` | `ConfigManager().add_project_alias(...)` |
| Switch by alias | `mp context switch <alias>` | via ConfigManager |
| Refresh cache | `mp projects refresh` | `ws.me(force_refresh=True)` |
| Migrate config | `mp auth migrate` | `ConfigManager().migrate_v1_to_v2()` |
