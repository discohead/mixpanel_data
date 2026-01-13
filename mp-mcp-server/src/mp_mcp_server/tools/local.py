"""Local SQL analysis tools for querying fetched data.

This module provides MCP tools for executing SQL queries against
locally stored data in the DuckDB database.

Example:
    Ask Claude: "Find the top 10 users by event count"
    Claude uses: sql(query="SELECT distinct_id, COUNT(*) ... LIMIT 10")
"""

import re
from typing import Any, Literal, cast

from fastmcp import Context

from mp_mcp_server.context import get_workspace
from mp_mcp_server.errors import handle_errors
from mp_mcp_server.server import mcp

# Type alias for unit parameter
UnitType = Literal["day", "week", "month"]

# SQL injection prevention patterns
# These patterns are checked case-insensitively in column expressions
DANGEROUS_SQL_PATTERNS: list[str] = [
    # Statement terminators and comments
    ";",
    "--",
    "/*",
    "*/",
    # DDL/DML keywords
    "DROP",
    "DELETE",
    "INSERT",
    "UPDATE",
    "ALTER",
    "CREATE",
    "TRUNCATE",
    "GRANT",
    "REVOKE",
    # Query manipulation keywords
    "UNION",
    "SELECT",
    "WHERE",
    "EXEC",
    "EXECUTE",
]

# Valid table name pattern: starts with letter/underscore, followed by alphanumeric/underscore
TABLE_NAME_PATTERN = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")


def _validate_table_name(table: str) -> None:
    """Validate table name to prevent SQL injection.

    Table names must be valid SQL identifiers: start with a letter or
    underscore, followed by letters, digits, or underscores.

    Args:
        table: The table name to validate.

    Raises:
        ValueError: If the table name contains invalid characters.
    """
    if not TABLE_NAME_PATTERN.match(table):
        raise ValueError(
            f"Invalid table name: '{table}'. "
            "Table names must start with a letter or underscore "
            "and contain only letters, digits, and underscores."
        )


def _validate_column_expression(column: str) -> None:
    """Validate column expression to prevent SQL injection.

    Column expressions can include JSON path syntax (e.g., properties->>'$.field')
    but must not contain dangerous SQL patterns.

    Args:
        column: The column expression to validate.

    Raises:
        ValueError: If the column contains dangerous SQL patterns.
    """
    col_upper = column.upper()
    for pattern in DANGEROUS_SQL_PATTERNS:
        if pattern in col_upper:
            raise ValueError(
                f"Invalid column expression: '{column}'. "
                f"Contains disallowed pattern: '{pattern}'."
            )


@mcp.tool
@handle_errors
def sql(
    ctx: Context,
    query: str,
) -> list[dict[str, Any]]:
    """Execute a SQL query against local data.

    Runs SQL against the DuckDB database containing fetched events
    and profiles. Returns results as a list of dictionaries.

    Args:
        ctx: FastMCP context with workspace access.
        query: SQL query to execute.

    Returns:
        List of result rows as dictionaries.

    Example:
        Ask: "Count events by name"
        Uses: sql(query="SELECT name, COUNT(*) as cnt FROM events GROUP BY name")
    """
    ws = get_workspace(ctx)
    return ws.sql_rows(query).to_dicts()


@mcp.tool
@handle_errors
def sql_scalar(
    ctx: Context,
    query: str,
) -> int | float | str | bool | None:
    """Execute a SQL query that returns a single value.

    Optimized for queries that return one value like COUNT, SUM, etc.

    Args:
        ctx: FastMCP context with workspace access.
        query: SQL query returning a single value.

    Returns:
        The scalar result value.

    Example:
        Ask: "How many events are there?"
        Uses: sql_scalar(query="SELECT COUNT(*) FROM events")
    """
    ws = get_workspace(ctx)
    result = ws.sql_scalar(query)
    return cast(int | float | str | bool | None, result)


@mcp.tool
@handle_errors
def list_tables(ctx: Context) -> list[dict[str, Any]]:
    """List all tables in the local database.

    Returns metadata about locally stored tables including
    name, row count, and type.

    Args:
        ctx: FastMCP context with workspace access.

    Returns:
        List of table metadata dictionaries.

    Example:
        Ask: "What tables do I have?"
        Uses: list_tables()
    """
    ws = get_workspace(ctx)
    return [t.to_dict() for t in ws.tables()]


@mcp.tool
@handle_errors
def table_schema(
    ctx: Context,
    table: str,
) -> list[dict[str, Any]]:
    """Get the schema (column definitions) for a table.

    Returns column names and types for the specified table.

    Args:
        ctx: FastMCP context with workspace access.
        table: Name of the table.

    Returns:
        List of column definitions.

    Example:
        Ask: "What columns does the events table have?"
        Uses: table_schema(table="events")
    """
    ws = get_workspace(ctx)
    schema = ws.table_schema(table)
    return [col.to_dict() for col in schema.columns]


@mcp.tool
@handle_errors
def sample(
    ctx: Context,
    table: str,
    limit: int = 10,
) -> list[dict[str, Any]]:
    """Get a random sample of rows from a table.

    Useful for understanding the data format and content.

    Args:
        ctx: FastMCP context with workspace access.
        table: Name of the table.
        limit: Number of rows to return.

    Returns:
        List of sample rows.

    Example:
        Ask: "Show me some events"
        Uses: sample(table="events", limit=5)
    """
    ws = get_workspace(ctx)
    df = ws.sample(table, n=limit)
    return cast(list[dict[str, Any]], df.to_dict(orient="records"))


@mcp.tool
@handle_errors
def summarize(
    ctx: Context,
    table: str,
) -> dict[str, Any]:
    """Get summary statistics for a table.

    Returns row count, column count, and other metadata.

    Args:
        ctx: FastMCP context with workspace access.
        table: Name of the table.

    Returns:
        Dictionary with table statistics.

    Example:
        Ask: "How much data is in the events table?"
        Uses: summarize(table="events")
    """
    ws = get_workspace(ctx)
    result = ws.summarize(table)
    return {
        "table": result.table,
        "row_count": result.row_count,
        "columns": [col.to_dict() for col in result.columns],
    }


@mcp.tool
@handle_errors
def event_breakdown(
    ctx: Context,
    table: str,
) -> list[dict[str, Any]]:
    """Get event counts by name from a local table.

    Quick way to see the distribution of events in fetched data.

    Args:
        ctx: FastMCP context with workspace access.
        table: Name of the events table.

    Returns:
        List of event names with counts.

    Raises:
        ToolError: If the table name is invalid or query fails.

    Example:
        Ask: "What events are in my data?"
        Uses: event_breakdown(table="events")
    """
    ws = get_workspace(ctx)
    # Validate table name to prevent SQL injection
    _validate_table_name(table)
    return ws.sql_rows(
        f'SELECT event_name, COUNT(*) as count FROM "{table}" GROUP BY event_name ORDER BY count DESC'
    ).to_dicts()


@mcp.tool
@handle_errors
def property_keys(
    ctx: Context,
    table: str,
    event: str | None = None,
) -> list[str]:
    """Extract unique property keys from event properties.

    Discovers what properties are present in the stored events.

    Args:
        ctx: FastMCP context with workspace access.
        table: Name of the events table.
        event: Optional event name to filter by.

    Returns:
        List of unique property key names.

    Example:
        Ask: "What properties are in my login events?"
        Uses: property_keys(table="events", event="login")
    """
    ws = get_workspace(ctx)
    return ws.property_keys(table=table, event=event)


@mcp.tool
@handle_errors
def column_stats(
    ctx: Context,
    table: str,
    column: str,
) -> dict[str, Any]:
    """Get detailed statistics for a specific column.

    Returns min, max, count, distinct count for the column.

    Args:
        ctx: FastMCP context with workspace access.
        table: Name of the table.
        column: Name of the column or JSON path expression
            (e.g., "properties->>'$.field'").

    Returns:
        Dictionary with column statistics including count, distinct_count,
        min_value, and max_value. If the table is empty, returns zeros
        with a note field explaining the result.

    Raises:
        ToolError: If the table name or column expression is invalid.

    Example:
        Ask: "What's the range of the time column?"
        Uses: column_stats(table="events", column="time")
    """
    ws = get_workspace(ctx)
    # Validate identifiers to prevent SQL injection
    _validate_table_name(table)
    _validate_column_expression(column)

    rows = ws.sql_rows(
        f"""
        SELECT
            COUNT(*) as count,
            COUNT(DISTINCT {column}) as distinct_count,
            MIN({column}) as min_value,
            MAX({column}) as max_value
        FROM "{table}"
        """
    ).to_dicts()

    if not rows:
        return {
            "count": 0,
            "distinct_count": 0,
            "min_value": None,
            "max_value": None,
            "note": "Table is empty or column has no values",
        }
    return rows[0]


@mcp.tool
@handle_errors
def drop_table(
    ctx: Context,
    table: str,
) -> dict[str, Any]:
    """Remove a table from the local database.

    Frees up space by removing fetched data you no longer need.

    Args:
        ctx: FastMCP context with workspace access.
        table: Name of the table to drop.

    Returns:
        Dictionary with success status.

    Example:
        Ask: "Delete the old events table"
        Uses: drop_table(table="old_events")
    """
    ws = get_workspace(ctx)
    ws.drop(table)
    return {"success": True, "message": f"Table '{table}' dropped"}


@mcp.tool
@handle_errors
def drop_all_tables(ctx: Context) -> dict[str, Any]:
    """Remove all tables from the local database.

    Clears all fetched data. Use with caution.

    Args:
        ctx: FastMCP context with workspace access.

    Returns:
        Dictionary with success status.

    Example:
        Ask: "Clear all my local data"
        Uses: drop_all_tables()
    """
    ws = get_workspace(ctx)
    ws.drop_all()
    return {"success": True, "message": "All tables dropped"}
