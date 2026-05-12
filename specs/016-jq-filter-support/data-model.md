# Data Model: JQ Filter Support

**Feature**: 016-jq-filter-support
**Date**: 2026-01-04

## Type Definitions

### New Types

```python
# cli/options.py

JqOption = Annotated[
    str | None,
    typer.Option(
        "--jq",
        help="Apply jq filter to JSON output (requires --format json or jsonl).",
    ),
]
```

### Modified Function Signatures

```python
# cli/utils.py

def _apply_jq_filter(json_str: str, filter_expr: str) -> str:
    """Apply jq filter to JSON string.

    Args:
        json_str: JSON string to filter.
        filter_expr: jq filter expression.

    Returns:
        Filtered JSON string (pretty-printed).

    Raises:
        typer.Exit: If filter syntax invalid or runtime error occurs.
    """
    ...

def output_result(
    ctx: typer.Context,
    data: dict[str, Any] | list[Any],
    columns: list[str] | None = None,
    *,
    format: str | None = None,
    jq_filter: str | None = None,  # NEW PARAMETER
) -> None:
    """Output data in the requested format.

    Args:
        ctx: Typer context with global options in obj dict.
        data: Data to output (dict or list).
        columns: Column names for table/csv format (auto-detected if None).
        format: Output format. If None, falls back to ctx.obj["format"] or "json".
        jq_filter: Optional jq filter expression. Only valid with json/jsonl format.

    Raises:
        typer.Exit: If jq_filter used with incompatible format.
    """
    ...

def present_result(
    ctx: typer.Context,
    result: ResultWithTableAndDict,
    format: str,
    *,
    jq_filter: str | None = None,  # NEW PARAMETER
) -> None:
    """Select appropriate dict format and output the result.

    Args:
        ctx: Typer context with global options in obj dict.
        result: Result object with to_table_dict() and to_dict() methods.
        format: Output format (e.g., "table", "json", "jsonl", "csv", "plain").
        jq_filter: Optional jq filter expression.
    """
    ...
```

## Data Flow

```
Command invocation
    │
    ▼
get_workspace() / execute query
    │
    ▼
result data (dict | list)
    │
    ▼
output_result(data, format=format, jq_filter=jq_filter)
    │
    ├─► format != json/jsonl AND jq_filter?
    │       └─► ERROR: Exit(INVALID_ARGS)
    │
    ├─► format_json(data) or format_jsonl(data)
    │       │
    │       ▼
    │   json_str (formatted JSON)
    │       │
    │       ▼
    │   jq_filter provided?
    │       ├─► NO: print(json_str)
    │       └─► YES: _apply_jq_filter(json_str, jq_filter)
    │               │
    │               ├─► SUCCESS: print(filtered_result)
    │               └─► ERROR: Exit(INVALID_ARGS)
    │
    └─► other formats: proceed as before
```

## Error States

| State | Condition | Exit Code | Error Message |
|-------|-----------|-----------|---------------|
| Incompatible format | `--jq` with `--format table/csv/plain` | 3 | "jq filter requires --format json or jsonl" |
| Invalid syntax | jq.compile() fails | 3 | "jq filter error: {error}" |
| Runtime error | jq.input() fails | 3 | "jq filter error: {error}" |

## Result Handling

| jq Result | Output |
|-----------|--------|
| Zero items | `[]` |
| One item (scalar) | Scalar value (e.g., `42`, `"text"`) |
| One item (object/array) | Pretty-printed object/array |
| Multiple items | Pretty-printed array of items |

## Command Parameters

All commands with `format: FormatOption` gain:

```python
jq_filter: JqOption = None
```

### Commands to Update

**inspect.py**:
- `events`, `properties`, `values`, `funnels`, `cohorts`
- `top_events`, `bookmarks`
- `lexicon_schemas`, `lexicon_schema`
- `distribution`, `numeric`, `daily`, `engagement`, `coverage`
- `info`, `tables`, `schema`, `sample`, `summarize`, `breakdown`, `keys`, `column`

**query.py**:
- `sql`, `segmentation`, `funnel`, `retention`, `jql`

**fetch.py**:
- `events`, `profiles`

### Example Command Signature

```python
@inspect_app.command("events")
@handle_errors
def inspect_events(
    ctx: typer.Context,
    format: FormatOption = "json",
    jq_filter: JqOption = None,  # NEW
) -> None:
    """List all event names from Mixpanel project.

    Examples:
        mp inspect events
        mp inspect events --format json --jq '.[0:5]'
    """
    workspace = get_workspace(ctx, read_only=True)
    with status_spinner(ctx, "Fetching events..."):
        events = workspace.events()
    output_result(ctx, events, format=format, jq_filter=jq_filter)
```
