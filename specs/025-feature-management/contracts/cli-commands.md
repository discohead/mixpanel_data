# CLI Command Contract: Feature Management

**Branch**: `025-feature-management` | **Date**: 2026-03-31

All commands follow the established pattern: Typer command group, `@handle_errors` decorator, `get_workspace(ctx)`, `status_spinner()`, `output_result()`.

## `mp flags` — Feature Flag Management

### `mp flags list`

```
mp flags list [--include-archived] [--format FORMAT] [--jq EXPR]
```

Lists all feature flags. With `--include-archived`, includes archived flags.

### `mp flags create`

```
mp flags create --name NAME --key KEY [--description DESC] [--status STATUS] [--tags T1,T2] [--serving-method METHOD] [--ruleset JSON] [--format FORMAT]
```

Creates a new feature flag. `--name` and `--key` are required.

### `mp flags get`

```
mp flags get FLAG_ID [--format FORMAT] [--jq EXPR]
```

Gets a single flag by UUID.

### `mp flags update`

```
mp flags update FLAG_ID --name NAME --key KEY --status STATUS --ruleset JSON [--description DESC] [--tags T1,T2] [--serving-method METHOD] [--format FORMAT]
```

Replaces a flag's full configuration (PUT semantics). `--name`, `--key`, `--status`, and `--ruleset` are required.

### `mp flags delete`

```
mp flags delete FLAG_ID
```

Permanently deletes a flag. Prints success confirmation to stderr.

### `mp flags archive`

```
mp flags archive FLAG_ID
```

Archives (soft-deletes) a flag. Prints success confirmation to stderr.

### `mp flags restore`

```
mp flags restore FLAG_ID [--format FORMAT]
```

Restores an archived flag. Outputs the restored flag.

### `mp flags duplicate`

```
mp flags duplicate FLAG_ID [--format FORMAT]
```

Duplicates a flag. Outputs the new flag.

### `mp flags set-test-users`

```
mp flags set-test-users FLAG_ID --users JSON
```

Sets test user overrides. `--users` is a JSON object mapping variant keys to user IDs.

### `mp flags history`

```
mp flags history FLAG_ID [--page CURSOR] [--page-size N] [--format FORMAT] [--jq EXPR]
```

Gets change history for a flag. Supports pagination.

### `mp flags limits`

```
mp flags limits [--format FORMAT] [--jq EXPR]
```

Gets account-level flag limits and usage.

## `mp experiments` — Experiment Management

### `mp experiments list`

```
mp experiments list [--include-archived] [--format FORMAT] [--jq EXPR]
```

Lists all experiments. With `--include-archived`, includes archived experiments.

### `mp experiments create`

```
mp experiments create --name NAME [--description DESC] [--hypothesis TEXT] [--settings JSON] [--format FORMAT]
```

Creates a new experiment in Draft status. `--name` is required.

### `mp experiments get`

```
mp experiments get EXPERIMENT_ID [--format FORMAT] [--jq EXPR]
```

Gets a single experiment by UUID.

### `mp experiments update`

```
mp experiments update EXPERIMENT_ID [--name NAME] [--description DESC] [--hypothesis TEXT] [--variants JSON] [--metrics JSON] [--settings JSON] [--tags T1,T2] [--format FORMAT]
```

Partially updates an experiment. All fields are optional (PATCH semantics).

### `mp experiments delete`

```
mp experiments delete EXPERIMENT_ID
```

Permanently deletes an experiment. Prints success confirmation to stderr.

### `mp experiments launch`

```
mp experiments launch EXPERIMENT_ID [--format FORMAT]
```

Launches an experiment (Draft → Active). Outputs the launched experiment.

### `mp experiments conclude`

```
mp experiments conclude EXPERIMENT_ID [--end-date DATE] [--format FORMAT]
```

Concludes an experiment (Active → Concluded). Optional end date override.

### `mp experiments decide`

```
mp experiments decide EXPERIMENT_ID --success/--no-success [--variant KEY] [--message TEXT] [--format FORMAT]
```

Decides the experiment outcome. `--success` or `--no-success` is required.

### `mp experiments archive`

```
mp experiments archive EXPERIMENT_ID
```

Archives an experiment. Prints success confirmation to stderr.

### `mp experiments restore`

```
mp experiments restore EXPERIMENT_ID [--format FORMAT]
```

Restores an archived experiment. Outputs the restored experiment.

### `mp experiments duplicate`

```
mp experiments duplicate EXPERIMENT_ID [--name NAME] [--format FORMAT]
```

Duplicates an experiment. Optional `--name` for the copy.

### `mp experiments erf`

```
mp experiments erf [--format FORMAT] [--jq EXPR]
```

Lists experiments in ERF (Experiment Results Framework) format.

## Common Options

All commands support:
- `--format {json,jsonl,table,csv,plain}` — Output format (default: json)
- `--jq EXPR` — JQ filter expression applied to JSON output

All commands use:
- `@handle_errors` decorator for consistent error handling
- `get_workspace(ctx)` for workspace resolution
- `status_spinner(ctx, message)` for progress indication
- `output_result(ctx, data, format=format, jq_filter=jq_filter)` for output formatting

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | Configuration error (missing credentials) |
| 2 | Authentication error (invalid credentials) |
| 3 | Query/validation error (bad request) |
| 4 | Not found |
| 5 | Rate limit exceeded |
