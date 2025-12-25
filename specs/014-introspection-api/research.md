# Research: Local Introspection API

**Feature**: 014-introspection-api
**Date**: 2024-12-25

## Research Questions

This feature adds introspection methods using DuckDB's built-in capabilities. Research focused on:
1. DuckDB SUMMARIZE output format
2. DuckDB sampling syntax
3. JSON key extraction patterns
4. Existing codebase patterns for result types

---

## 1. DuckDB SUMMARIZE Command

**Decision**: Use DuckDB's built-in `SUMMARIZE` command for table statistics.

**Rationale**:
- Native DuckDB command optimized for analytical workloads
- Returns comprehensive per-column statistics in a single query
- Includes HyperLogLog-based approximate distinct counts (fast for large tables)

**Output Format Confirmed**:
```sql
SUMMARIZE table_name;
```
Returns columns:
- `column_name` (VARCHAR)
- `column_type` (VARCHAR)
- `min` (VARCHAR - stringified value)
- `max` (VARCHAR - stringified value)
- `approx_unique` (BIGINT)
- `avg` (DOUBLE or NULL for non-numeric)
- `std` (DOUBLE or NULL for non-numeric)
- `q25` (VARCHAR or NULL)
- `q50` (VARCHAR or NULL)
- `q75` (VARCHAR or NULL)
- `count` (BIGINT)
- `null_percentage` (DOUBLE)

**Alternatives Considered**:
- Manual aggregation queries: More complex, less performant
- pandas describe(): Requires loading all data into memory

---

## 2. DuckDB Sampling Syntax

**Decision**: Use `USING SAMPLE` clause with reservoir sampling.

**Rationale**:
- DuckDB's reservoir sampling returns representative rows from throughout the table
- Syntax: `SELECT * FROM table USING SAMPLE n`
- Unlike `LIMIT n`, sampling doesn't just return first n rows

**Syntax Confirmed**:
```sql
-- Exact count sampling (reservoir)
SELECT * FROM events USING SAMPLE 10;

-- Also supports percentage
SELECT * FROM events USING SAMPLE 1%;
```

**Alternatives Considered**:
- `ORDER BY RANDOM() LIMIT n`: Much slower, requires full table scan + sort
- `LIMIT n`: Not random, just first n rows

---

## 3. JSON Key Extraction

**Decision**: Use `json_keys()` with `unnest()` for property discovery.

**Rationale**:
- DuckDB's `json_keys()` returns array of top-level keys
- `unnest()` expands arrays for aggregation across rows
- Combined with `DISTINCT` provides all unique keys

**Pattern Confirmed**:
```sql
SELECT DISTINCT unnest(json_keys(properties)) as key
FROM events
ORDER BY key;

-- With event filter (parameterized)
SELECT DISTINCT unnest(json_keys(properties)) as key
FROM events
WHERE event_name = ?
ORDER BY key;
```

**Alternatives Considered**:
- Recursive JSON traversal: More complex, not needed for top-level keys
- Schema introspection: Properties stored as JSON, not typed columns

---

## 4. Existing Codebase Patterns

**Decision**: Follow established frozen dataclass pattern with lazy DataFrame caching.

**Rationale**:
- Consistency with existing result types (`FetchResult`, `SegmentationResult`, etc.)
- Immutability ensures thread-safety and predictable behavior
- Lazy caching avoids unnecessary DataFrame construction

**Pattern from `types.py`**:
```python
@dataclass(frozen=True)
class SomeResult:
    """Docstring."""

    field: type
    """Field docstring."""

    _df_cache: pd.DataFrame | None = field(default=None, repr=False)

    @property
    def df(self) -> pd.DataFrame:
        """Convert to DataFrame."""
        if self._df_cache is not None:
            return self._df_cache

        # Build DataFrame
        result_df = pd.DataFrame(...)

        # Cache using object.__setattr__ for frozen dataclass
        object.__setattr__(self, "_df_cache", result_df)
        return result_df

    def to_dict(self) -> dict[str, Any]:
        """Serialize for JSON output."""
        return {...}
```

**StorageEngine Methods Available**:
- `execute_df(sql)` → pandas DataFrame
- `execute_scalar(sql)` → single value
- `execute_rows(sql)` → list of tuples
- `get_schema(table)` → TableSchema (raises `TableNotFoundError`)

**Error Handling Pattern**:
- `TableNotFoundError`: When table doesn't exist
- `QueryError`: For invalid queries or missing columns

---

## 5. CLI Integration Pattern

**Decision**: Add commands to existing `inspect_app` Typer group.

**Rationale**:
- Introspection commands belong with other inspect commands
- Existing `handle_errors` decorator handles error formatting
- Existing `output_result` function handles format conversion

**Pattern from `inspect.py`**:
```python
@inspect_app.command("command-name")
@handle_errors
def inspect_command(
    ctx: typer.Context,
    table: Annotated[str, typer.Option("--table", "-t", help="Table name.")],
    format: FormatOption = "json",
) -> None:
    """Command help text."""
    workspace = get_workspace(ctx)
    result = workspace.method(table)
    output_result(ctx, result.to_dict(), format=format)
```

---

## Summary

All technical questions resolved. Implementation can proceed using:

| Feature | DuckDB Feature | Notes |
|---------|---------------|-------|
| `sample()` | `USING SAMPLE n` | Reservoir sampling |
| `summarize()` | `SUMMARIZE table` | Built-in statistics |
| `event_breakdown()` | Standard SQL aggregation | GROUP BY with window function |
| `property_keys()` | `json_keys()` + `unnest()` | Parameterized for event filter |
| `column_stats()` | Mixed queries | Type detection + aggregation |

No external dependencies required. All functionality uses existing DuckDB capabilities and codebase patterns.
