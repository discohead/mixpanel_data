# Data Model: CLI Application

**Date**: 2025-12-23
**Purpose**: Define data structures used by the CLI layer

## Overview

The CLI is a thin wrapper that transforms between:
1. **Input**: Command-line arguments/options → Method parameters
2. **Output**: Library result types → Formatted terminal output

The CLI introduces no new domain entities. It uses existing types from `mixpanel_data.types` and `mixpanel_data.auth`.

## CLI Context Model

### ContextOptions

Runtime context passed to all commands via Typer's context object (`ctx.obj`).

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| account | str | None | Override account name (-a/--account) |
| quiet | bool | False | Suppress progress (-q/--quiet) |
| verbose | bool | False | Debug output (-v/--verbose) |
| workspace | Workspace | None | Lazy-initialized workspace instance |
| config | ConfigManager | None | Lazy-initialized config manager |

Note: The `--format` option is per-command (not global) and is passed directly to each command's function, not via `ctx.obj`.

### OutputFormat (Enum)

Supported output formats with their characteristics.

| Value | Description | Use Case | MIME Type |
|-------|-------------|----------|-----------|
| json | Pretty-printed JSON | Programmatic parsing, jq | application/json |
| jsonl | Newline-delimited JSON | Streaming, large datasets | application/x-ndjson |
| table | ASCII table with Rich | Human terminal viewing | text/plain |
| csv | Comma-separated values | Spreadsheets, data tools | text/csv |
| plain | Minimal text | Log parsing, simple scripts | text/plain |

### ExitCode (Enum)

Standardized exit codes with mapping to exception types.

| Code | Name | Exception Source | Meaning |
|------|------|------------------|---------|
| 0 | SUCCESS | None | Command completed successfully |
| 1 | GENERAL_ERROR | MixpanelDataError | Unspecified error |
| 2 | AUTH_ERROR | AuthenticationError | Invalid/missing credentials |
| 3 | INVALID_ARGS | ValidationError | Invalid arguments/options |
| 4 | NOT_FOUND | AccountNotFoundError, TableNotFoundError | Resource not found |
| 5 | RATE_LIMIT | RateLimitError | API rate limit exceeded |
| 130 | INTERRUPTED | KeyboardInterrupt, SIGINT | User cancelled (Ctrl+C) |

## Input Transformation

### Date Parsing

CLI accepts dates as strings; library expects strings. Validation occurs at CLI layer.

| CLI Input | Validation | Library Parameter |
|-----------|------------|-------------------|
| "2024-01-01" | ISO format check | "2024-01-01" |
| "today" | Resolve to date | "2024-12-23" |
| "7 days ago" | Relative date | "2024-12-16" |

### List Arguments

Comma-separated strings are parsed to lists.

| CLI Input | Parsing | Library Parameter |
|-----------|---------|-------------------|
| "Signup,Purchase" | Split on comma | ["Signup", "Purchase"] |
| "user_1,user_2" | Split on comma | ["user_1", "user_2"] |

### Boolean Flags

Typer's built-in boolean option handling.

| CLI Input | Library Parameter |
|-----------|-------------------|
| --quiet | quiet=True |
| --no-progress | progress=False |
| --force | (skip confirmation) |

## Output Transformation

### Result Type to Output Format

All library result types implement `.to_dict()` for serialization.

| Result Type | .to_dict() Structure | Formats Supported |
|-------------|---------------------|-------------------|
| FetchResult | {table, rows, from_date, to_date, duration} | json, table, plain |
| SegmentationResult | {event, data, from_date, to_date, unit} | json, table, csv |
| FunnelResult | {funnel_id, steps: [{name, count, conversion}]} | json, table, csv |
| RetentionResult | {cohorts: [{date, size, retention: [...]}]} | json, table, csv |
| WorkspaceInfo | {path, project_id, region, tables, size_mb} | json, table |
| TableInfo | {name, type, row_count, fetched_at} | json, table |
| list[str] | ["event1", "event2", ...] | json, plain, table |
| list[AccountInfo] | [{name, username, project_id, region, is_default}] | json, table |

### Format-Specific Rendering

#### JSON Format
```python
# Input: result.to_dict()
# Output: Pretty-printed JSON
{
  "table": "events",
  "rows": 15234,
  "from_date": "2024-01-01",
  "to_date": "2024-01-31"
}
```

#### Table Format
```python
# Input: list of dicts
# Output: Rich Table
┌────────┬───────────┬────────┐
│ NAME   │ PROJECT   │ REGION │
├────────┼───────────┼────────┤
│ prod   │ 12345     │ us     │
│ stage  │ 67890     │ eu     │
└────────┴───────────┴────────┘
```

#### CSV Format
```python
# Input: list of dicts
# Output: CSV with headers
name,project,region
prod,12345,us
stage,67890,eu
```

#### JSONL Format
```python
# Input: list of dicts
# Output: One JSON object per line
{"name":"prod","project":"12345","region":"us"}
{"name":"stage","project":"67890","region":"eu"}
```

#### Plain Format
```python
# Input: list of strings or single value
# Output: One item per line
prod
stage
```

## State Management

### No Persistent CLI State

The CLI is stateless between invocations. State is managed by:
- **Configuration**: ~/.mp/config.toml (via ConfigManager)
- **Database**: ~/.mixpanel_data/{project_id}.db (via StorageEngine)

### Within-Command State

During command execution, state flows through Typer's Context:

```
CLI Invocation
    ↓
Parse Global Options → GlobalOptions in ctx.obj
    ↓
Parse Command Options → Command parameters
    ↓
Create Workspace (lazy) → ctx.obj["workspace"]
    ↓
Execute Library Method
    ↓
Format Result → stdout
```

## Validation Rules

### Date Validation
- Must be valid ISO 8601 date (YYYY-MM-DD)
- from_date must be ≤ to_date
- Cannot be in the future (for most commands)

### Account Name Validation
- Must exist in config (except for `mp auth add`)
- Case-sensitive matching

### Table Name Validation
- Must exist in database (for query/inspect commands)
- Valid SQL identifier (alphanumeric + underscore)

### Event Name Validation
- Server-side validation (forwarded to API)
- CLI does not pre-validate event existence

## Error Response Structure

Error output goes to stderr with consistent format:

```
[red]Error type:[/red] Human-readable message

Details:
  key: value
  key: value

Hint: Suggested remediation
```

JSON error format (when --format json and error occurs):

```json
{
  "error": {
    "code": "AUTH_ERROR",
    "message": "Invalid credentials",
    "details": {
      "account": "production"
    }
  }
}
```
