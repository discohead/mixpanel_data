"""API Contract: Workspace Introspection Methods

This file defines the method signatures and contracts for the 5 introspection
methods to be added to the Workspace class.

Note: This is a contract specification, not implementation code.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import pandas as pd

    from mixpanel_data.types import (
        ColumnStatsResult,
        EventBreakdownResult,
        SummaryResult,
    )


class WorkspaceIntrospectionMixin:
    """Mixin defining introspection method contracts for Workspace class."""

    def sample(self, table: str, n: int = 10) -> pd.DataFrame:
        """Return random sample rows from a table.

        Uses DuckDB's reservoir sampling for representative results.
        Unlike LIMIT, sampling returns rows from throughout the table.

        Args:
            table: Table name to sample from.
            n: Number of rows to return (default: 10).

        Returns:
            DataFrame with n random rows. If table has fewer than n rows,
            returns all available rows.

        Raises:
            TableNotFoundError: If table doesn't exist.

        Example:
            >>> ws = Workspace()
            >>> ws.sample("events")  # 10 random rows
            >>> ws.sample("events", n=5)  # 5 random rows
        """
        ...

    def summarize(self, table: str) -> SummaryResult:
        """Get statistical summary of all columns in a table.

        Uses DuckDB's SUMMARIZE command to compute min/max, quartiles,
        null percentage, and approximate distinct counts for each column.

        Args:
            table: Table name to summarize.

        Returns:
            SummaryResult with per-column statistics and total row count.

        Raises:
            TableNotFoundError: If table doesn't exist.

        Example:
            >>> result = ws.summarize("events")
            >>> result.row_count         # 1234567
            >>> result.columns[0].null_percentage  # 0.5
            >>> result.df                # Full summary as DataFrame
        """
        ...

    def event_breakdown(self, table: str) -> EventBreakdownResult:
        """Analyze event distribution in a table.

        Computes per-event counts, unique users, date ranges, and
        percentage of total for each event type.

        Args:
            table: Table name containing events. Must have columns:
                   event_name, event_time, distinct_id.

        Returns:
            EventBreakdownResult with per-event statistics.

        Raises:
            TableNotFoundError: If table doesn't exist.
            QueryError: If table lacks required columns (event_name,
                       event_time, distinct_id). Error message lists
                       the specific missing columns.

        Example:
            >>> breakdown = ws.event_breakdown("events")
            >>> breakdown.total_events           # 1234567
            >>> breakdown.events[0].event_name   # "Page View"
            >>> breakdown.events[0].pct_of_total # 45.2
        """
        ...

    def property_keys(
        self,
        table: str,
        event: str | None = None,
    ) -> list[str]:
        """List all JSON property keys in a table.

        Extracts distinct keys from the 'properties' JSON column.
        Useful for discovering queryable fields in event properties.

        Args:
            table: Table name with a 'properties' JSON column.
            event: Optional event name to filter by. If provided, only
                   returns keys present in events of that type.

        Returns:
            Alphabetically sorted list of property key names.
            Empty list if no keys found.

        Raises:
            TableNotFoundError: If table doesn't exist.
            QueryError: If table lacks 'properties' column.

        Example:
            >>> # All keys across all events
            >>> ws.property_keys("events")
            ['$browser', '$city', 'page', 'referrer', 'user_plan']

            >>> # Keys for specific event type
            >>> ws.property_keys("events", event="Purchase")
            ['amount', 'currency', 'product_id', 'quantity']
        """
        ...

    def column_stats(
        self,
        table: str,
        column: str,
        *,
        top_n: int = 10,
    ) -> ColumnStatsResult:
        """Get detailed statistics for a single column.

        Performs deep analysis including null rates, cardinality,
        top values, and numeric statistics (for numeric columns).

        The column parameter supports JSON path expressions for
        analyzing properties stored in JSON columns:
        - `properties->>'$.country'` for string extraction
        - `CAST(properties->>'$.amount' AS DOUBLE)` for numeric

        Args:
            table: Table name to analyze.
            column: Column name or expression to analyze.
            top_n: Number of top values to return (default: 10).

        Returns:
            ColumnStatsResult with comprehensive column statistics.

        Raises:
            TableNotFoundError: If table doesn't exist.
            QueryError: If column expression is invalid.

        Example:
            >>> # Analyze standard column
            >>> stats = ws.column_stats("events", "event_name")
            >>> stats.unique_count      # 47
            >>> stats.top_values[:3]    # [('Page View', 45230), ...]

            >>> # Analyze JSON property
            >>> stats = ws.column_stats("events", "properties->>'$.country'")
        """
        ...
