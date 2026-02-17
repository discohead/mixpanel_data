---
description: Manage Mixpanel feature flags (list, create, update, archive, delete)
allowed-tools: Bash(mp flags:*)
argument-hint: [list|get|create|update|delete|archive|restore] [flag-id]
---

# Mixpanel Feature Flags

Manage feature flags in your Mixpanel project.

## Operation Selection

Determine operation based on arguments:
- **No arguments or $1 = "list"**: List all feature flags
- **$1 = "get"**: Get a single flag (use $2 for flag ID)
- **$1 = "create"**: Create a new flag interactively
- **$1 = "update"**: Update an existing flag (use $2 for flag ID)
- **$1 = "delete"**: Delete a flag (use $2 for flag ID)
- **$1 = "archive"**: Archive a flag (use $2 for flag ID)
- **$1 = "restore"**: Restore an archived flag (use $2 for flag ID)

## Pre-flight Check

Verify credentials are configured:

```bash
!$(mp auth list --format table 2>&1)
```

If no accounts are configured, direct the user to run `/mp-auth` first.

---

## Operation: List

List all feature flags in the project.

```bash
!$(mp flags list --format table)
```

Ask if they want to include archived flags:

```bash
!$(mp flags list --include-archived --format table)
```

### Next Steps

- **View flag details**: Run `/mp-flags get <flag-id>`
- **Create a new flag**: Run `/mp-flags create`
- **Update a flag**: Run `/mp-flags update <flag-id>`

---

## Operation: Get

Get details for a single feature flag.

### 1. Determine Flag ID

- Use `$2` if provided
- Otherwise, list flags and ask user to pick one:

```bash
!$(mp flags list --format table)
```

### 2. Fetch Flag Details

```bash
!$(mp flags get <flag-id> --format json)
```

Display the flag's name, key, status, description, variants, and rollout configuration.

### Next Steps

- **Update this flag**: Run `/mp-flags update <flag-id>`
- **Archive this flag**: Run `/mp-flags archive <flag-id>`

---

## Operation: Create

Create a new feature flag interactively.

### 1. Collect Basic Information

Use AskUserQuestion to collect:
- **Name**: Human-readable flag name (1-255 characters)
- **Key**: Programmatic key used in code (1-255 characters, must be unique)
- **Description**: Optional description of the flag's purpose
- **Context**: Evaluation context (e.g., "user")
- **Serving method**: How the flag is served — "client", "server", "remote_or_local", or "remote_only"

### 2. Configure Variants

Guide through variant setup. A flag needs at least one variant.

Ask for each variant:
- **Key**: Variant identifier (e.g., "on", "off", "control", "treatment")
- **Value**: Variant value (boolean, string, or object)
- **Is control**: Whether this is the control variant
- **Split**: Traffic split percentage (0.0-1.0, all splits must sum to 1.0)
- **Is sticky**: Whether users stay in the same variant across sessions

A typical boolean flag has two variants:
```json
[
  {"key": "off", "value": false, "is_control": true, "split": 0.5, "is_sticky": true},
  {"key": "on", "value": true, "is_control": false, "split": 0.5, "is_sticky": true}
]
```

### 3. Configure Rollout

Ask for rollout configuration:
- **Rollout percentage**: What percentage of matching users see this flag (0.0-1.0)
- **Variant splits**: How traffic is split across variants (must sum to 1.0)
- **Cohort targeting**: Optional cohort definition for targeted rollout

### 4. Build and Create Flag

Assemble the JSON payload and write to a temporary file:

```json
{
  "name": "<name>",
  "key": "<key>",
  "tags": [],
  "status": "disabled",
  "context": "<context>",
  "serving_method": "<serving_method>",
  "description": "<description>",
  "ruleset": {
    "variants": [...],
    "rollout": [{"rollout_percentage": <pct>, "variant_splits": {...}}]
  }
}
```

Write the config to a temporary file and create the flag:

```bash
!$(mp flags create -c /tmp/flag_config.json --format json)
```

Show the created flag details. Note: flags are created with status "disabled" by default.

### 5. Next Steps

- **Enable the flag**: Run `/mp-flags update <flag-id>` and set status to "enabled"
- **View all flags**: Run `/mp-flags list`

---

## Operation: Update

Update an existing feature flag.

### 1. Determine Flag ID

- Use `$2` if provided
- Otherwise, list flags and ask user to pick one

### 2. Get Current Flag State

```bash
!$(mp flags get <flag-id> --format json)
```

Display the current flag configuration so the user can see what they're changing.

### 3. Determine Changes

Ask the user what they want to change:
- Name, key, description, status
- Variants (add, remove, modify splits)
- Rollout configuration

**Important**: Update uses PUT semantics—the entire flag configuration is replaced. Start with the current flag state and modify the fields the user wants to change.

### 4. Build Updated Payload

Construct the complete updated payload. Write to a temporary file.

For quick single-field changes, use override flags:

```bash
!$(mp flags update <flag-id> -c /tmp/flag_config.json --status disabled)
```

For full updates:

```bash
!$(mp flags update <flag-id> -c /tmp/flag_config.json --format json)
```

### Next Steps

- **Verify the update**: Run `/mp-flags get <flag-id>`
- **View all flags**: Run `/mp-flags list`

---

## Operation: Delete

Delete a feature flag permanently.

### 1. Determine Flag ID

- Use `$2` if provided
- Otherwise, list flags and ask user to pick one

### 2. Check Flag Status

```bash
!$(mp flags get <flag-id> --format json)
```

**Warning**: Cannot delete enabled flags. If the flag is enabled, inform the user they must disable it first (`mp flags update <id> -c config.json --status disabled`) or use archive instead.

### 3. Confirm Deletion

Ask user to confirm. This action is permanent and cannot be undone.

### 4. Execute Deletion

```bash
!$(mp flags delete <flag-id>)
```

---

## Operation: Archive

Archive a feature flag (soft delete).

### 1. Determine Flag ID

- Use `$2` if provided
- Otherwise, list flags and ask user to pick one

### 2. Confirm Archive

Explain that archived flags are hidden by default but can be restored later.

### 3. Execute Archive

```bash
!$(mp flags archive <flag-id>)
```

### Next Steps

- **View archived flags**: Run `mp flags list --include-archived`
- **Restore later**: Run `/mp-flags restore <flag-id>`

---

## Operation: Restore

Restore an archived feature flag.

### 1. Determine Flag ID

- Use `$2` if provided
- Otherwise, list archived flags:

```bash
!$(mp flags list --include-archived --format table)
```

### 2. Execute Restore

```bash
!$(mp flags restore <flag-id>)
```

### 3. Verify

```bash
!$(mp flags get <flag-id> --format json)
```

---

## Troubleshooting

### "Cannot delete enabled flag"
Flags must be disabled before deletion. Update the flag status to "disabled" first, or use archive for a reversible soft delete.

### "Duplicate key"
Feature flag keys must be unique within a project. Choose a different key or check existing flags with `mp flags list`.

### "Invalid payload"
The JSON config must be a valid object. Check that:
- Required fields are present (name, key, ruleset)
- Variant splits sum to 1.0
- Rollout percentage is between 0.0 and 1.0
- Key is 1-255 characters

### Authentication errors
Run `/mp-auth test` to verify credentials. Run `/mp-auth` to reconfigure if needed.
