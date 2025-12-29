# Bug Report: SQL Query CLI Output Formatting

**Date**: 2025-12-29
**Severity**: Medium (functionality works, but output is unusable for table/CSV formats)
**Component**: CLI `mp query sql` command
**Status**: Open

## Summary

The `mp query sql` command produces malformed output for `--format table`, `--format csv`, and `--format json` when queries return multiple columns. Results are displayed as Python tuple strings rather than properly formatted columnar data.

---

## Issue 1: SQL Query Results Display as Tuple Strings

### Reproduction

```bash
# Expected: Table with two columns (payment_method, cnt)
# Actual: Single "VALUE" column containing tuple strings
mp query sql "SELECT properties->>'$.Payment Method' as payment, COUNT(*) as cnt FROM purchase_events GROUP BY 1 ORDER BY 2 DESC" --format table

# Output:
# ┏━━━━━━━━━━━━━━━━━━━━━━━┓
# ┃ VALUE                 ┃
# ┡━━━━━━━━━━━━━━━━━━━━━━━┩
# │ ('Credit card', 2265) │   ← Should be two columns
# │ ('PayPal', 1248)      │
# └───────────────────────┘
```

```bash
# CSV output contains tuple repr strings
mp query sql "SELECT DATE_TRUNC('day', event_time) as day, COUNT(*) FROM purchase_events GROUP BY 1" --format csv

# Output:
# value
# "(datetime.date(2023, 1, 1), 245)"   ← Should be: 2023-01-01,245
```

```bash
# JSON output lacks column names
mp query sql "SELECT COUNT(*) as total FROM purchase_events" --format json

# Output:
# [[4174]]   ← Should be: [{"total": 4174}]
```

### Root Cause Analysis

#### Data Flow

```
mp query sql
    ↓
query.py:query_sql() line 113
    ↓
workspace.sql_rows(query)  →  Returns: list[tuple[Any, ...]]
    ↓
output_result(ctx, result)
    ↓
formatters.format_table(data)  →  Expects: list[dict[str, Any]]
```

#### The Problem

1. **`workspace.sql_rows()`** ([workspace.py:1163](src/mixpanel_data/workspace.py#L1163)) returns `list[tuple]` without column names:
   ```python
   def sql_rows(self, query: str) -> list[tuple[Any, ...]]:
       return self.storage.execute_rows(query)
   ```

2. **`storage.execute_rows()`** ([storage.py:1252](src/mixpanel_data/_internal/storage.py#L1252)) discards column metadata:
   ```python
   return self.connection.execute(sql).fetchall()  # Column names in .description are lost
   ```

3. **`format_table()`** ([formatters.py:96-109](src/mixpanel_data/cli/formatters.py#L96)) expects dicts:
   ```python
   if columns is None:
       first_item = data[0]
       columns = list(first_item.keys()) if isinstance(first_item, dict) else ["value"]
       #                                    ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
       #                                    Falls back to single "value" column

   for item in data:
       if isinstance(item, dict):
           row = [_format_cell(item.get(col, "")) for col in columns]
       else:
           row = [_format_cell(item)]  # Tuple becomes str(tuple) → "('x', 1)"
   ```

#### Why Other Commands Work Correctly

The `inspect sample` command ([inspect.py:506-509](src/mixpanel_data/cli/commands/inspect.py#L506)) properly converts DataFrame to dicts:

```python
df = workspace.sample(table, n=rows)
# Convert DataFrame to list of dicts for output
data = df.to_dict(orient="records")  # ← This is the correct approach
output_result(ctx, data, format=format)
```

Similarly, `inspect tables` manually constructs dicts with column names.

### Impact

- **Table format**: Completely unusable for multi-column queries
- **CSV format**: Produces invalid CSV with tuple strings as values
- **JSON format**: Returns arrays of arrays without column semantics
- **Plain format**: Partially affected (uses first value, but loses structure)

The Python library's `ws.sql()` method works correctly because it returns a pandas DataFrame.

### Recommended Fix: Enhance `sql_rows()` to Return Column Names

Since this package is not yet released, breaking changes are acceptable. The cleanest solution is to have `sql_rows()` return a structured result that includes column metadata.

#### Step 1: Add `SQLResult` Type

Create a new result type in [types.py](src/mixpanel_data/types.py):

```python
from dataclasses import dataclass
from typing import Any

@dataclass(frozen=True)
class SQLResult:
    """Result from a SQL query with column metadata.

    Attributes:
        columns: List of column names from the query.
        rows: List of row tuples containing the data.

    Example:
        ```python
        result = ws.sql_rows("SELECT name, age FROM users")
        print(result.columns)  # ['name', 'age']
        for row in result.rows:
            print(dict(zip(result.columns, row)))
        ```
    """
    columns: list[str]
    rows: list[tuple[Any, ...]]

    def to_dicts(self) -> list[dict[str, Any]]:
        """Convert rows to list of dicts with column names as keys."""
        return [dict(zip(self.columns, row)) for row in self.rows]

    def __len__(self) -> int:
        """Return number of rows."""
        return len(self.rows)

    def __iter__(self):
        """Iterate over rows."""
        return iter(self.rows)
```

#### Step 2: Update `StorageEngine.execute_rows()`

Modify [storage.py:1214-1259](src/mixpanel_data/_internal/storage.py#L1214):

```python
def execute_rows(self, sql: str) -> SQLResult:
    """Execute SQL and return structured result with column names.

    Args:
        sql: SQL query string.

    Returns:
        SQLResult with columns and rows.

    Raises:
        QueryError: If query execution fails.
    """
    try:
        result = self.connection.execute(sql)
        columns = [desc[0] for desc in result.description]
        rows = result.fetchall()
        return SQLResult(columns=columns, rows=rows)
    except duckdb.Error as e:
        raise QueryError(
            f"Query execution failed: {e}",
            status_code=0,
            response_body={"query": sql, "error": str(e)},
        ) from e
```

#### Step 3: Update `Workspace.sql_rows()`

Modify [workspace.py:1163-1175](src/mixpanel_data/workspace.py#L1163):

```python
def sql_rows(self, query: str) -> SQLResult:
    """Execute SQL query and return structured result.

    Args:
        query: SQL query string.

    Returns:
        SQLResult with column names and row tuples.

    Raises:
        QueryError: If query is invalid.

    Example:
        ```python
        result = ws.sql_rows("SELECT event_name, COUNT(*) as cnt FROM events GROUP BY 1")
        for name, count in result.rows:
            print(f"{name}: {count}")

        # Or convert to dicts:
        for row in result.to_dicts():
            print(row)  # {'event_name': 'Login', 'cnt': 42}
        ```
    """
    return self.storage.execute_rows(query)
```

#### Step 4: Update CLI `query_sql` Command

Modify [query.py:112-114](src/mixpanel_data/cli/commands/query.py#L112):

```python
else:
    result = workspace.sql_rows(sql_query)
    output_result(ctx, result.to_dicts(), format=format)
```

#### Step 5: Export `SQLResult` from Public API

Add to [__init__.py](src/mixpanel_data/__init__.py):

```python
from mixpanel_data.types import SQLResult

__all__ = [
    # ... existing exports
    "SQLResult",
]
```

### Test Cases

```python
def test_sql_rows_returns_sql_result():
    """Verify sql_rows returns SQLResult with columns and rows."""
    ws = Workspace.ephemeral()
    ws.storage.connection.execute("CREATE TABLE test (name VARCHAR, age INT)")
    ws.storage.connection.execute("INSERT INTO test VALUES ('Alice', 30), ('Bob', 25)")

    result = ws.sql_rows("SELECT name, age FROM test ORDER BY name")

    assert isinstance(result, SQLResult)
    assert result.columns == ["name", "age"]
    assert result.rows == [("Alice", 30), ("Bob", 25)]
    assert len(result) == 2


def test_sql_result_to_dicts():
    """Verify SQLResult.to_dicts() converts to list of dicts."""
    result = SQLResult(columns=["x", "y"], rows=[(1, 2), (3, 4)])

    dicts = result.to_dicts()

    assert dicts == [{"x": 1, "y": 2}, {"x": 3, "y": 4}]


def test_sql_query_table_format_multiple_columns(cli_runner):
    """Verify table format shows proper column headers and values."""
    result = cli_runner.invoke(app, [
        "query", "sql",
        "SELECT 'foo' as name, 123 as count",
        "--format", "table"
    ])

    assert "NAME" in result.output
    assert "COUNT" in result.output
    assert "foo" in result.output
    assert "123" in result.output
    assert "('foo', 123)" not in result.output  # No tuple strings


def test_sql_query_csv_format_proper_columns(cli_runner):
    """Verify CSV format has proper headers and comma-separated values."""
    result = cli_runner.invoke(app, [
        "query", "sql",
        "SELECT 'bar' as x, 456 as y",
        "--format", "csv"
    ])

    lines = result.output.strip().split('\n')
    assert lines[0] == "x,y"
    assert lines[1] == "bar,456"


def test_sql_query_json_format_with_column_names(cli_runner):
    """Verify JSON format includes column semantics."""
    result = cli_runner.invoke(app, [
        "query", "sql",
        "SELECT 'baz' as col1, 789 as col2",
        "--format", "json"
    ])

    data = json.loads(result.output)
    assert data[0]["col1"] == "baz"
    assert data[0]["col2"] == 789
```

### Files to Modify

1. [src/mixpanel_data/types.py](src/mixpanel_data/types.py) - Add `SQLResult` dataclass
2. [src/mixpanel_data/__init__.py](src/mixpanel_data/__init__.py) - Export `SQLResult`
3. [src/mixpanel_data/_internal/storage.py](src/mixpanel_data/_internal/storage.py) - Update `execute_rows()` return type
4. [src/mixpanel_data/workspace.py](src/mixpanel_data/workspace.py) - Update `sql_rows()` return type and docstring
5. [src/mixpanel_data/cli/commands/query.py](src/mixpanel_data/cli/commands/query.py) - Use `result.to_dicts()`
6. [tests/test_types.py](tests/test_types.py) - Add `SQLResult` tests
7. [tests/test_workspace.py](tests/test_workspace.py) - Update `sql_rows` tests
8. [tests/cli/test_query.py](tests/cli/test_query.py) - Add CLI format tests

---

## Issue 2: Column Inspection Table Truncation

### Reproduction

```bash
mp inspect column -t purchase_events -c event_time --format table

# Output:
# ┏━━━━━┳━━━━━┳━━━━━┳━━━━━┳━━━━━┳━━━━━┳━━━━━┳━━━━━┳━━━━━━┳━━━━━┳━━━━━┳━━━━━┳━━━━━┓
# ┃     ┃     ┃     ┃     ┃ NU… ┃ NU… ┃ UN… ┃ UN… ┃ TOP  ┃     ┃     ┃     ┃     ┃
# ┃ TA… ┃ CO… ┃ DT… ┃ CO… ┃ CO… ┃ PCT ┃ CO… ┃ PCT ┃ VAL… ┃ MIN ┃ MAX ┃ ME… ┃ STD ┃
```

### Root Cause

The `mp inspect column` command returns data with many columns (13+), and Rich's table auto-sizing truncates headers to fit terminal width. The result is unreadable abbreviated headers like "TA…", "CO…", "DT…".

### Impact

- Column statistics are effectively unusable in table format
- Users must use `--format json` to see full data

### Recommended Fix

Two options:

#### Option A: Transpose to Key-Value Format

For single-column inspection, display as vertical key-value pairs:

```
┏━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ PROPERTY        ┃ VALUE                        ┃
┡━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
│ Table           │ purchase_events              │
│ Column          │ event_time                   │
│ Type            │ TIMESTAMP                    │
│ Count           │ 4174                         │
│ Null Count      │ 0                            │
│ Null %          │ 0.0                          │
│ Unique Count    │ 4770                         │
│ Min             │ 2023-01-01 00:01:39          │
│ Max             │ 2023-01-31 23:58:11          │
└─────────────────┴──────────────────────────────┘
```

#### Option B: Use Rich's `overflow="fold"` or Wider Columns

Configure Rich table to wrap content or use minimum column widths:

```python
table = Table(show_header=True, header_style="bold")
table.add_column("TABLE", min_width=15, overflow="fold")
table.add_column("COLUMN", min_width=15, overflow="fold")
# ...
```

### Recommendation

**Option A (transpose)** is preferred for `inspect column` since it displays statistics for a single column. Vertical layout is more readable for this use case.

### Files to Modify

1. [src/mixpanel_data/cli/commands/inspect.py](src/mixpanel_data/cli/commands/inspect.py) - `inspect_column` function
2. [src/mixpanel_data/cli/formatters.py](src/mixpanel_data/cli/formatters.py) - Add `format_key_value_table()` helper (optional)

---

## Issue 3: JSON Output Lacks Schema Information

### Reproduction

```bash
mp query sql "SELECT COUNT(*) as total, AVG(subtotal) as avg FROM purchase_events" --format json

# Output:
# [[4174, 103.21]]
```

### Root Cause

The current JSON output returns raw arrays of arrays, losing column name information. Users cannot programmatically determine which value corresponds to which column without knowing the query structure.

### Impact

- JSON output requires out-of-band knowledge of query structure
- Cannot be reliably parsed by downstream tools
- Inconsistent with how other commands return JSON (as objects with named keys)

### Recommended Fix

This issue is resolved by Issue 1's fix. When `sql_rows()` returns `SQLResult` and the CLI uses `result.to_dicts()`, JSON output becomes:

```json
[
  {"total": 4174, "avg": 103.21}
]
```

For users who need the columnar format (e.g., for streaming large results), consider adding a `--json-format` option:

```bash
mp query sql "..." --format json --json-format records  # Default: [{"col": val}, ...]
mp query sql "..." --format json --json-format arrays   # Legacy: [[val, ...], ...]
mp query sql "..." --format json --json-format split    # {"columns": [...], "data": [[...], ...]}
```

### Files to Modify

No additional changes needed beyond Issue 1 fix. Optional `--json-format` flag could be added to [query.py](src/mixpanel_data/cli/commands/query.py).

---

## Summary of All Changes

| File | Changes |
|------|---------|
| [src/mixpanel_data/types.py](src/mixpanel_data/types.py) | Add `SQLResult` dataclass |
| [src/mixpanel_data/__init__.py](src/mixpanel_data/__init__.py) | Export `SQLResult` |
| [src/mixpanel_data/_internal/storage.py](src/mixpanel_data/_internal/storage.py) | Update `execute_rows()` to return `SQLResult` |
| [src/mixpanel_data/workspace.py](src/mixpanel_data/workspace.py) | Update `sql_rows()` signature and docstring |
| [src/mixpanel_data/cli/commands/query.py](src/mixpanel_data/cli/commands/query.py) | Use `result.to_dicts()` for output |
| [src/mixpanel_data/cli/commands/inspect.py](src/mixpanel_data/cli/commands/inspect.py) | Transpose column stats to key-value format |
| [tests/test_types.py](tests/test_types.py) | Add `SQLResult` tests |
| [tests/test_workspace.py](tests/test_workspace.py) | Update `sql_rows` tests |
| [tests/test_storage.py](tests/test_storage.py) | Update `execute_rows` tests |
| [tests/cli/test_query.py](tests/cli/test_query.py) | Add CLI format tests |
| [tests/cli/test_inspect.py](tests/cli/test_inspect.py) | Add column format tests |
