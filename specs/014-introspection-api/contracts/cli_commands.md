# CLI Contract: Introspection Commands

**Feature**: 014-introspection-api
**Date**: 2024-12-25

## Overview

Add 5 new commands to the `mp inspect` command group. All commands follow existing patterns:
- Use `@handle_errors` decorator for consistent error handling
- Use `output_result()` for format conversion (table, json, csv, jsonl)
- Delegate to Workspace methods for all logic

---

## Commands

### 1. `mp inspect sample`

Show random sample rows from a table.

**Options**:
| Option | Short | Type | Default | Description |
|--------|-------|------|---------|-------------|
| `--table` | `-t` | str | required | Table name |
| `--rows` | `-n` | int | 10 | Number of rows |
| `--format` | | str | table | Output format |

**Examples**:
```bash
mp inspect sample -t events
mp inspect sample -t events -n 5 --format json
```

**Exit Codes**:
- 0: Success
- 4: Table not found

---

### 2. `mp inspect summarize`

Show statistical summary of all columns.

**Options**:
| Option | Short | Type | Default | Description |
|--------|-------|------|---------|-------------|
| `--table` | `-t` | str | required | Table name |
| `--format` | | str | table | Output format |

**Examples**:
```bash
mp inspect summarize -t events
mp inspect summarize -t events --format json
```

**Exit Codes**:
- 0: Success
- 4: Table not found

---

### 3. `mp inspect breakdown`

Show event distribution in a table.

**Options**:
| Option | Short | Type | Default | Description |
|--------|-------|------|---------|-------------|
| `--table` | `-t` | str | required | Table name |
| `--format` | | str | table | Output format |

**Examples**:
```bash
mp inspect breakdown -t events
mp inspect breakdown -t events --format json
```

**Exit Codes**:
- 0: Success
- 1: Missing required columns (error message lists missing columns)
- 4: Table not found

---

### 4. `mp inspect keys`

List JSON property keys in a table.

**Options**:
| Option | Short | Type | Default | Description |
|--------|-------|------|---------|-------------|
| `--table` | `-t` | str | required | Table name |
| `--event` | `-e` | str | None | Filter to specific event |
| `--format` | | str | json | Output format |

**Examples**:
```bash
mp inspect keys -t events
mp inspect keys -t events -e "Purchase"
mp inspect keys -t events --format table
```

**Exit Codes**:
- 0: Success
- 1: Missing properties column
- 4: Table not found

---

### 5. `mp inspect column`

Show detailed statistics for a column.

**Options**:
| Option | Short | Type | Default | Description |
|--------|-------|------|---------|-------------|
| `--table` | `-t` | str | required | Table name |
| `--column` | `-c` | str | required | Column name or expression |
| `--top` | | int | 10 | Number of top values |
| `--format` | | str | json | Output format |

**Examples**:
```bash
mp inspect column -t events -c event_name
mp inspect column -t events -c "properties->>'$.country'"
mp inspect column -t events -c distinct_id --top 20
```

**Exit Codes**:
- 0: Success
- 1: Invalid column expression
- 4: Table not found

---

## Output Format Examples

### Sample (table format)
```
┌────────────┬─────────────────────┬─────────────┬────────────────────────┐
│ event_name │ event_time          │ distinct_id │ properties             │
├────────────┼─────────────────────┼─────────────┼────────────────────────┤
│ Page View  │ 2024-01-15 10:23:45 │ user_abc123 │ {"page": "/home", ...} │
│ Click      │ 2024-01-15 10:24:12 │ user_def456 │ {"button": "signup"}   │
└────────────┴─────────────────────┴─────────────┴────────────────────────┘
```

### Summarize (table format)
```
┌─────────────┬─────────────┬─────────┬─────────┬───────────────┬───────────────────┬───────┐
│ column_name │ column_type │ min     │ max     │ approx_unique │ null_percentage   │ count │
├─────────────┼─────────────┼─────────┼─────────┼───────────────┼───────────────────┼───────┤
│ event_name  │ VARCHAR     │ Click   │ View    │            47 │               0.0 │ 10000 │
│ event_time  │ TIMESTAMP   │ 2024-01 │ 2024-01 │         10000 │               0.0 │ 10000 │
└─────────────┴─────────────┴─────────┴─────────┴───────────────┴───────────────────┴───────┘
```

### Breakdown (JSON format)
```json
{
  "table": "events",
  "total_events": 125000,
  "total_users": 8432,
  "date_range": ["2024-01-01T00:00:00", "2024-01-31T23:59:59"],
  "events": [
    {
      "event_name": "Page View",
      "count": 56000,
      "unique_users": 7500,
      "first_seen": "2024-01-01T00:01:23",
      "last_seen": "2024-01-31T23:58:45",
      "pct_of_total": 44.8
    }
  ]
}
```

### Keys (JSON format)
```json
["$browser", "$city", "$os", "page", "referrer", "user_plan"]
```

### Column (JSON format)
```json
{
  "table": "events",
  "column": "event_name",
  "dtype": "VARCHAR",
  "count": 125000,
  "null_count": 0,
  "null_pct": 0.0,
  "unique_count": 47,
  "unique_pct": 0.04,
  "top_values": [
    ["Page View", 56000],
    ["Click", 34000],
    ["Sign Up", 12000]
  ],
  "min": null,
  "max": null,
  "mean": null,
  "std": null
}
```
