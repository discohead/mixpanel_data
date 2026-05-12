# CLI Interface Contract

**Date**: 2025-12-23
**Purpose**: Define the command-line interface contract for the `mp` CLI

## Entry Point

**Command**: `mp`
**Module**: `mixpanel_data.cli.main:app`
**Installation**: `pip install mixpanel_data`

## Global Options Contract

Global options are placed before the command name:

| Option | Short | Type | Default | Description |
|--------|-------|------|---------|-------------|
| --account | -a | string | (default account) | Account name to use |
| --quiet | -q | flag | false | Suppress progress output |
| --verbose | -v | flag | false | Enable debug output |
| --help | -h | flag | - | Show help |
| --version | | flag | - | Show version |

## Per-Command Options Contract

The `--format` option is available on all commands and is placed after the command name:

| Option | Short | Type | Default | Description |
|--------|-------|------|---------|-------------|
| --format | -f | enum | json | Output format |

### Format Enum Values

| Value | Description |
|-------|-------------|
| json | Pretty-printed JSON |
| jsonl | Newline-delimited JSON |
| table | Rich ASCII table |
| csv | Comma-separated values |
| plain | Minimal text output |

## Command Groups

### mp auth

Authentication and account management commands.

#### mp auth list

**Synopsis**: `mp auth list [--format FORMAT]`

**Output Schema (JSON)**:
```json
[
  {
    "name": "string",
    "username": "string",
    "project_id": "string",
    "region": "us|eu|in",
    "is_default": true
  }
]
```

**Exit Codes**: 0 (success), 1 (config error)

---

#### mp auth add

**Synopsis**: `mp auth add NAME [OPTIONS]`

**Arguments**:
| Argument | Required | Description |
|----------|----------|-------------|
| NAME | yes | Account name |

**Options**:
| Option | Short | Required | Description |
|--------|-------|----------|-------------|
| --username | -u | yes* | Service account username |
| --project | -p | yes* | Project ID |
| --region | -r | no | Region (us, eu, in) default: us |
| --default | -d | no | Set as default account |
| --interactive | -i | no | Prompt for all credentials |
| --secret-stdin | | no | Read secret from stdin |

*Required unless --interactive

**Secret Handling** (secure by default):
1. `--secret-stdin`: Read from stdin (e.g., `echo $SECRET | mp auth add ...`)
2. `MP_SECRET` environment variable (for CI/CD)
3. Interactive prompt with hidden input (default)

**Output**: Success message or error
**Exit Codes**: 0 (success), 1 (already exists), 3 (missing required/invalid region)

---

#### mp auth remove

**Synopsis**: `mp auth remove NAME [--force]`

**Arguments**:
| Argument | Required | Description |
|----------|----------|-------------|
| NAME | yes | Account name to remove |

**Options**:
| Option | Description |
|--------|-------------|
| --force | Skip confirmation |

**Exit Codes**: 0 (success), 1 (not found), 2 (cancelled)

---

#### mp auth switch

**Synopsis**: `mp auth switch NAME`

**Exit Codes**: 0 (success), 1 (not found)

---

#### mp auth show

**Synopsis**: `mp auth show NAME [--format FORMAT]`

**Output Schema (JSON)**:
```json
{
  "name": "string",
  "username": "string",
  "secret": "********",
  "project_id": "string",
  "region": "string",
  "is_default": true
}
```

**Exit Codes**: 0 (success), 1 (not found)

---

#### mp auth test

**Synopsis**: `mp auth test [NAME] [--format FORMAT]`

**Arguments**:
| Argument | Required | Description |
|----------|----------|-------------|
| NAME | no | Account to test (default if omitted) |

**Output Schema (JSON)**:
```json
{
  "success": true,
  "account": "string",
  "project_name": "string",
  "project_id": "string",
  "region": "string"
}
```

**Exit Codes**: 0 (success), 1 (auth failed), 2 (not found)

---

### mp fetch

Data fetching commands.

#### mp fetch events

**Synopsis**: `mp fetch events [NAME] --from DATE --to DATE [OPTIONS]`

**Arguments**:
| Argument | Required | Default | Description |
|----------|----------|---------|-------------|
| NAME | no | events | Table name |

**Options**:
| Option | Short | Required | Description |
|--------|-------|----------|-------------|
| --from | | yes | Start date (YYYY-MM-DD) |
| --to | | yes | End date (YYYY-MM-DD) |
| --events | -e | no | Comma-separated event filter |
| --where | -w | no | Mixpanel filter expression |
| --replace | | no | Replace existing table |
| --no-progress | | no | Hide progress bar |

**Output Schema (JSON)**:
```json
{
  "table": "string",
  "rows": 12345,
  "from_date": "YYYY-MM-DD",
  "to_date": "YYYY-MM-DD",
  "duration_seconds": 12.3
}
```

**Exit Codes**: 0 (success), 1 (table exists), 2 (auth), 3 (invalid date), 4 (invalid filter), 5 (rate limit)

---

#### mp fetch profiles

**Synopsis**: `mp fetch profiles [NAME] [OPTIONS]`

**Arguments**:
| Argument | Required | Default | Description |
|----------|----------|---------|-------------|
| NAME | no | profiles | Table name |

**Options**:
| Option | Short | Required | Description |
|--------|-------|----------|-------------|
| --where | -w | no | Mixpanel filter expression |
| --replace | | no | Replace existing table |
| --no-progress | | no | Hide progress bar |

**Output Schema (JSON)**:
```json
{
  "table": "string",
  "rows": 12345,
  "duration_seconds": 12.3
}
```

**Exit Codes**: 0 (success), 1 (table exists), 2 (auth), 4 (invalid filter), 5 (rate limit)

---

### mp query

Query commands (local SQL and live API queries).

#### mp query sql

**Synopsis**: `mp query sql QUERY [OPTIONS]`

**Arguments**:
| Argument | Required | Description |
|----------|----------|-------------|
| QUERY | yes* | SQL query string |

**Options**:
| Option | Short | Description |
|--------|-------|-------------|
| --file | -F | Read query from file |
| --scalar | -s | Return single value |
| --format | -f | Output format |

*Required unless --file

**Output Schema (JSON)**: Array of row objects
```json
[
  {"column1": "value1", "column2": 123},
  {"column1": "value2", "column2": 456}
]
```

**Scalar Output**: Raw value only
```
12345
```

**Exit Codes**: 0 (success), 1 (SQL error), 2 (table not found), 3 (file not found)

---

#### mp query segmentation

**Synopsis**: `mp query segmentation --event EVENT --from DATE --to DATE [OPTIONS]`

**Options**:
| Option | Short | Required | Description |
|--------|-------|----------|-------------|
| --event | -e | yes | Event name |
| --from | | yes | Start date |
| --to | | yes | End date |
| --on | -o | no | Property to segment by |
| --unit | -u | no | Time unit (day, week, month) |
| --where | -w | no | Filter expression |

**Output Schema (JSON)**:
```json
{
  "event": "string",
  "from_date": "YYYY-MM-DD",
  "to_date": "YYYY-MM-DD",
  "unit": "day",
  "total": 12345,
  "data": {
    "YYYY-MM-DD": {"segment": 123}
  }
}
```

**Exit Codes**: 0, 1 (auth), 2 (invalid date), 3 (event not found), 4 (invalid filter)

---

#### mp query funnel

**Synopsis**: `mp query funnel ID --from DATE --to DATE [OPTIONS]`

**Arguments**:
| Argument | Required | Description |
|----------|----------|-------------|
| ID | yes | Funnel ID |

**Options**:
| Option | Short | Required | Description |
|--------|-------|----------|-------------|
| --from | | yes | Start date |
| --to | | yes | End date |
| --unit | -u | no | Time unit |
| --on | -o | no | Property to segment by |

**Output Schema (JSON)**:
```json
{
  "funnel_id": 123,
  "from_date": "YYYY-MM-DD",
  "to_date": "YYYY-MM-DD",
  "steps": [
    {"name": "string", "count": 1000, "conversion": 100.0, "overall": 100.0}
  ]
}
```

**Exit Codes**: 0, 1 (auth), 2 (funnel not found), 3 (invalid date)

---

#### mp query retention

**Synopsis**: `mp query retention --born EVENT --return EVENT --from DATE --to DATE [OPTIONS]`

**Options**:
| Option | Short | Required | Description |
|--------|-------|----------|-------------|
| --born | -b | yes | Birth event |
| --return | -r | yes | Return event |
| --from | | yes | Start date |
| --to | | yes | End date |
| --born-where | | no | Birth event filter |
| --return-where | | no | Return event filter |
| --interval | -i | no | Bucket size |
| --intervals | -n | no | Number of buckets |
| --unit | -u | no | Time unit |

**Output Schema (JSON)**:
```json
{
  "born_event": "string",
  "return_event": "string",
  "from_date": "YYYY-MM-DD",
  "to_date": "YYYY-MM-DD",
  "cohorts": [
    {"date": "YYYY-MM-DD", "size": 100, "retention": [100.0, 45.0, 38.0]}
  ]
}
```

**Exit Codes**: 0, 1 (auth), 2 (invalid date), 3 (event not found), 4 (invalid filter)

---

#### mp query jql

**Synopsis**: `mp query jql FILE [OPTIONS]` or `mp query jql --script SCRIPT [OPTIONS]`

**Arguments**:
| Argument | Required | Description |
|----------|----------|-------------|
| FILE | no | JQL script file |

**Options**:
| Option | Short | Description |
|--------|-------|-------------|
| --script | -c | Inline JQL script |
| --param | -P | Parameter (key=value), repeatable |

**Output Schema (JSON)**: JQL result (varies by script)

**Exit Codes**: 0, 1 (auth), 2 (file not found), 3 (syntax error), 4 (execution error)

---

### mp inspect

Inspection and discovery commands.

#### mp inspect events

**Synopsis**: `mp inspect events [--format FORMAT]`

**Output Schema (JSON)**:
```json
["Event1", "Event2", "Event3"]
```

**Exit Codes**: 0, 1 (auth)

---

#### mp inspect properties

**Synopsis**: `mp inspect properties --event EVENT [--format FORMAT]`

**Output Schema (JSON)**:
```json
["property1", "property2", "property3"]
```

**Exit Codes**: 0, 1 (auth), 2 (event not found)

---

#### mp inspect values

**Synopsis**: `mp inspect values --property PROPERTY [--event EVENT] [--limit N] [--format FORMAT]`

**Output Schema (JSON)**:
```json
["value1", "value2", "value3"]
```

**Exit Codes**: 0, 1 (auth), 2 (event not found), 3 (property not found)

---

#### mp inspect funnels

**Synopsis**: `mp inspect funnels [--format FORMAT]`

**Output Schema (JSON)**:
```json
[
  {"funnel_id": 123, "name": "string"}
]
```

**Exit Codes**: 0, 1 (auth)

---

#### mp inspect cohorts

**Synopsis**: `mp inspect cohorts [--format FORMAT]`

**Output Schema (JSON)**:
```json
[
  {"id": 123, "name": "string", "count": 1000, "description": "string"}
]
```

**Exit Codes**: 0, 1 (auth)

---

#### mp inspect top-events

**Synopsis**: `mp inspect top-events [--type TYPE] [--limit N] [--format FORMAT]`

**Options**:
| Option | Short | Description |
|--------|-------|-------------|
| --type | -t | Count type: general, average, unique |
| --limit | -l | Max events to return |

**Output Schema (JSON)**:
```json
[
  {"event": "string", "count": 12345, "percent_change": 5.2}
]
```

**Exit Codes**: 0, 1 (auth)

---

#### mp inspect info

**Synopsis**: `mp inspect info [--format FORMAT]`

**Output Schema (JSON)**:
```json
{
  "path": "string",
  "account": "string",
  "project_id": "string",
  "region": "string",
  "tables": 3,
  "size_mb": 12.4
}
```

**Exit Codes**: 0

---

#### mp inspect tables

**Synopsis**: `mp inspect tables [--format FORMAT]`

**Output Schema (JSON)**:
```json
[
  {
    "name": "string",
    "type": "events|profiles",
    "row_count": 12345,
    "fetched_at": "YYYY-MM-DDTHH:MM:SSZ"
  }
]
```

**Exit Codes**: 0

---

#### mp inspect schema

**Synopsis**: `mp inspect schema --table TABLE [--format FORMAT]`

**Options**:
| Option | Description |
|--------|-------------|
| --sample | Include sample property values |

**Output Schema (JSON)**:
```json
{
  "table": "string",
  "row_count": 12345,
  "columns": [
    {"name": "string", "type": "string", "nullable": true}
  ]
}
```

**Exit Codes**: 0, 1 (table not found)

---

#### mp inspect drop

**Synopsis**: `mp inspect drop --table TABLE [--force]`

**Options**:
| Option | Description |
|--------|-------------|
| --force | Skip confirmation |

**Output**: Success message
**Exit Codes**: 0 (success), 1 (table not found), 2 (cancelled)

---

## Exit Code Contract

| Code | Constant | Meaning |
|------|----------|---------|
| 0 | SUCCESS | Command completed successfully |
| 1 | GENERAL_ERROR | General/unspecified error |
| 2 | AUTH_ERROR | Authentication failed |
| 3 | INVALID_ARGS | Invalid arguments or options |
| 4 | NOT_FOUND | Resource not found |
| 5 | RATE_LIMIT | API rate limit exceeded |
| 130 | INTERRUPTED | User interrupted (Ctrl+C) |

## I/O Contract

### Standard Output (stdout)
- **Contains**: Data output only (query results, command output)
- **Format**: Controlled by --format option
- **Encoding**: UTF-8

### Standard Error (stderr)
- **Contains**: Progress bars, status messages, errors, debug output
- **Format**: Human-readable text with optional Rich styling
- **Encoding**: UTF-8

### Pipe Behavior
- When stdout is piped, progress output is automatically disabled
- When NO_COLOR is set, styling is disabled
- JSON output is always valid (no mixed content)
