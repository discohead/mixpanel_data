"""
Workspace API Contract

This file defines the complete public interface for the Workspace class.
It serves as the contract between the specification and implementation.

NOTE: This is a contract specification, not the actual implementation.
The implementation will be in src/mixpanel_data/workspace.py
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

import pandas as pd

if TYPE_CHECKING:
    import duckdb
    from mixpanel_data._internal.api_client import MixpanelAPIClient
    from mixpanel_data._internal.config import ConfigManager
    from mixpanel_data._internal.storage import StorageEngine
    from mixpanel_data.types import (
        ActivityFeedResult,
        EventCountsResult,
        FetchResult,
        FrequencyResult,
        FunnelInfo,
        FunnelResult,
        InsightsResult,
        JQLResult,
        NumericAverageResult,
        NumericBucketResult,
        NumericSumResult,
        PropertyCountsResult,
        RetentionResult,
        SavedCohort,
        SegmentationResult,
        TableInfo,
        TableSchema,
        TopEvent,
        WorkspaceInfo,
    )


class Workspace:
    """Unified entry point for Mixpanel data operations.

    The Workspace class is a facade that orchestrates all services:
    - DiscoveryService for schema exploration
    - FetcherService for data ingestion
    - LiveQueryService for real-time analytics
    - StorageEngine for local SQL queries

    Examples:
        Basic usage with credentials from config::

            ws = Workspace()
            ws.fetch_events(from_date="2024-01-01", to_date="2024-01-31")
            df = ws.sql("SELECT * FROM events LIMIT 10")

        Ephemeral workspace for temporary analysis::

            with Workspace.ephemeral() as ws:
                ws.fetch_events(from_date="2024-01-01", to_date="2024-01-31")
                total = ws.sql_scalar("SELECT COUNT(*) FROM events")
            # Database automatically deleted

        Query-only access to existing database::

            ws = Workspace.open("path/to/database.db")
            df = ws.sql("SELECT * FROM events")
    """

    # =========================================================================
    # LIFECYCLE & CONSTRUCTION
    # =========================================================================

    def __init__(
        self,
        account: str | None = None,
        project_id: str | None = None,
        region: str | None = None,
        path: str | Path | None = None,
        # Dependency injection for testing
        _config_manager: ConfigManager | None = None,
        _api_client: MixpanelAPIClient | None = None,
        _storage: StorageEngine | None = None,
    ) -> None:
        """Create a new Workspace with credentials and optional database path.

        Credentials are resolved in priority order:
        1. Environment variables (MP_USERNAME, MP_SECRET, MP_PROJECT_ID, MP_REGION)
        2. Named account from config file (if account parameter specified)
        3. Default account from config file

        Args:
            account: Named account from config file to use.
            project_id: Override project ID from credentials.
            region: Override region from credentials (us, eu, in).
            path: Path to database file. If None, uses default location.
            _config_manager: Injected ConfigManager for testing.
            _api_client: Injected MixpanelAPIClient for testing.
            _storage: Injected StorageEngine for testing.

        Raises:
            ConfigError: If no credentials can be resolved.
            AccountNotFoundError: If named account doesn't exist.
        """
        ...

    @classmethod
    @contextmanager
    def ephemeral(
        cls,
        account: str | None = None,
        project_id: str | None = None,
        region: str | None = None,
        _config_manager: ConfigManager | None = None,
        _api_client: MixpanelAPIClient | None = None,
    ) -> Iterator[Workspace]:
        """Create a temporary workspace that auto-deletes on exit.

        Args:
            account: Named account from config file to use.
            project_id: Override project ID from credentials.
            region: Override region from credentials.
            _config_manager: Injected ConfigManager for testing.
            _api_client: Injected MixpanelAPIClient for testing.

        Yields:
            Workspace: A workspace with temporary database.

        Example::

            with Workspace.ephemeral() as ws:
                ws.fetch_events(from_date="2024-01-01", to_date="2024-01-31")
                print(ws.sql_scalar("SELECT COUNT(*) FROM events"))
            # Database file automatically deleted
        """
        ...

    @classmethod
    def open(cls, path: str | Path) -> Workspace:
        """Open an existing database for query-only access.

        This method opens a database without requiring API credentials.
        Discovery, fetching, and live query methods will be unavailable.

        Args:
            path: Path to existing database file.

        Returns:
            Workspace: A workspace with read-only access to stored data.

        Raises:
            FileNotFoundError: If database file doesn't exist.

        Example::

            ws = Workspace.open("my_data.db")
            df = ws.sql("SELECT * FROM events")
            ws.close()
        """
        ...

    def __enter__(self) -> Workspace:
        """Enter context manager."""
        ...

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: Any,
    ) -> None:
        """Exit context manager, closing all resources."""
        ...

    def close(self) -> None:
        """Close all resources (database connection, HTTP client).

        This method is idempotent and safe to call multiple times.
        """
        ...

    # =========================================================================
    # DISCOVERY METHODS
    # =========================================================================

    def events(self) -> list[str]:
        """List all event names in the Mixpanel project.

        Results are cached for the lifetime of the Workspace.

        Returns:
            Alphabetically sorted list of event names.

        Raises:
            ConfigError: If API credentials not available.
            AuthenticationError: If credentials are invalid.
        """
        ...

    def properties(self, event: str) -> list[str]:
        """List all property names for an event.

        Results are cached per event for the lifetime of the Workspace.

        Args:
            event: Event name to get properties for.

        Returns:
            Alphabetically sorted list of property names.

        Raises:
            ConfigError: If API credentials not available.
        """
        ...

    def property_values(
        self,
        property_name: str,
        *,
        event: str | None = None,
        limit: int = 100,
    ) -> list[str]:
        """Get sample values for a property.

        Results are cached per (property, event, limit) for the lifetime of the Workspace.

        Args:
            property_name: Property to get values for.
            event: Optional event to filter by.
            limit: Maximum number of values to return.

        Returns:
            List of sample property values as strings.

        Raises:
            ConfigError: If API credentials not available.
        """
        ...

    def funnels(self) -> list[FunnelInfo]:
        """List saved funnels in the Mixpanel project.

        Results are cached for the lifetime of the Workspace.

        Returns:
            List of FunnelInfo objects (funnel_id, name).

        Raises:
            ConfigError: If API credentials not available.
        """
        ...

    def cohorts(self) -> list[SavedCohort]:
        """List saved cohorts in the Mixpanel project.

        Results are cached for the lifetime of the Workspace.

        Returns:
            List of SavedCohort objects.

        Raises:
            ConfigError: If API credentials not available.
        """
        ...

    def top_events(
        self,
        *,
        type: Literal["general", "average", "unique"] = "general",
        limit: int | None = None,
    ) -> list[TopEvent]:
        """Get today's most active events.

        This method is NOT cached (returns real-time data).

        Args:
            type: Counting method (general, average, unique).
            limit: Maximum number of events to return.

        Returns:
            List of TopEvent objects (event, count, percent_change).

        Raises:
            ConfigError: If API credentials not available.
        """
        ...

    def clear_discovery_cache(self) -> None:
        """Clear cached discovery results.

        Subsequent discovery calls will fetch fresh data from the API.
        """
        ...

    # =========================================================================
    # FETCHING METHODS
    # =========================================================================

    def fetch_events(
        self,
        name: str = "events",
        *,
        from_date: str,
        to_date: str,
        events: list[str] | None = None,
        where: str | None = None,
        progress: bool = True,
    ) -> FetchResult:
        """Fetch events from Mixpanel and store in local database.

        Args:
            name: Table name to create (default: "events").
            from_date: Start date (YYYY-MM-DD).
            to_date: End date (YYYY-MM-DD).
            events: Optional list of event names to filter.
            where: Optional WHERE clause for filtering.
            progress: Show progress bar (default: True).

        Returns:
            FetchResult with table name, row count, duration.

        Raises:
            TableExistsError: If table already exists.
            ConfigError: If API credentials not available.
            AuthenticationError: If credentials are invalid.
        """
        ...

    def fetch_profiles(
        self,
        name: str = "profiles",
        *,
        where: str | None = None,
        progress: bool = True,
    ) -> FetchResult:
        """Fetch user profiles from Mixpanel and store in local database.

        Args:
            name: Table name to create (default: "profiles").
            where: Optional WHERE clause for filtering.
            progress: Show progress bar (default: True).

        Returns:
            FetchResult with table name, row count, duration.

        Raises:
            TableExistsError: If table already exists.
            ConfigError: If API credentials not available.
        """
        ...

    # =========================================================================
    # LOCAL QUERY METHODS
    # =========================================================================

    def sql(self, query: str) -> pd.DataFrame:
        """Execute SQL query and return results as DataFrame.

        Args:
            query: SQL query string.

        Returns:
            pandas DataFrame with query results.

        Raises:
            QueryError: If query is invalid.
        """
        ...

    def sql_scalar(self, query: str) -> Any:
        """Execute SQL query and return single scalar value.

        Args:
            query: SQL query that returns a single value.

        Returns:
            The scalar result (int, float, str, etc.).

        Raises:
            QueryError: If query is invalid or returns multiple values.
        """
        ...

    def sql_rows(self, query: str) -> list[tuple[Any, ...]]:
        """Execute SQL query and return results as list of tuples.

        Args:
            query: SQL query string.

        Returns:
            List of row tuples.

        Raises:
            QueryError: If query is invalid.
        """
        ...

    # =========================================================================
    # LIVE QUERY METHODS
    # =========================================================================

    def segmentation(
        self,
        event: str,
        *,
        from_date: str,
        to_date: str,
        on: str | None = None,
        unit: Literal["day", "week", "month"] = "day",
        where: str | None = None,
    ) -> SegmentationResult:
        """Run a segmentation query against Mixpanel API.

        Args:
            event: Event name to query.
            from_date: Start date (YYYY-MM-DD).
            to_date: End date (YYYY-MM-DD).
            on: Optional property to segment by.
            unit: Time unit for aggregation.
            where: Optional WHERE clause.

        Returns:
            SegmentationResult with time-series data.

        Raises:
            ConfigError: If API credentials not available.
        """
        ...

    def funnel(
        self,
        funnel_id: int,
        *,
        from_date: str,
        to_date: str,
        unit: str | None = None,
        on: str | None = None,
    ) -> FunnelResult:
        """Run a funnel analysis query.

        Args:
            funnel_id: ID of saved funnel.
            from_date: Start date (YYYY-MM-DD).
            to_date: End date (YYYY-MM-DD).
            unit: Optional time unit.
            on: Optional property to segment by.

        Returns:
            FunnelResult with step conversion rates.

        Raises:
            ConfigError: If API credentials not available.
        """
        ...

    def retention(
        self,
        *,
        born_event: str,
        return_event: str,
        from_date: str,
        to_date: str,
        born_where: str | None = None,
        return_where: str | None = None,
        interval: int = 1,
        interval_count: int = 10,
        unit: Literal["day", "week", "month"] = "day",
    ) -> RetentionResult:
        """Run a retention analysis query.

        Args:
            born_event: Event that defines cohort entry.
            return_event: Event that defines return.
            from_date: Start date (YYYY-MM-DD).
            to_date: End date (YYYY-MM-DD).
            born_where: Optional filter for born event.
            return_where: Optional filter for return event.
            interval: Retention interval.
            interval_count: Number of intervals.
            unit: Time unit.

        Returns:
            RetentionResult with cohort retention data.

        Raises:
            ConfigError: If API credentials not available.
        """
        ...

    def jql(self, script: str, params: dict[str, Any] | None = None) -> JQLResult:
        """Execute a custom JQL script.

        Args:
            script: JQL script code.
            params: Optional parameters to pass to script.

        Returns:
            JQLResult with raw query results.

        Raises:
            ConfigError: If API credentials not available.
            JQLSyntaxError: If script has syntax errors.
        """
        ...

    def event_counts(
        self,
        events: list[str],
        *,
        from_date: str,
        to_date: str,
        type: Literal["general", "unique", "average"] = "general",
        unit: Literal["day", "week", "month"] = "day",
    ) -> EventCountsResult:
        """Get event counts for multiple events.

        Args:
            events: List of event names.
            from_date: Start date (YYYY-MM-DD).
            to_date: End date (YYYY-MM-DD).
            type: Counting method.
            unit: Time unit.

        Returns:
            EventCountsResult with time-series per event.

        Raises:
            ConfigError: If API credentials not available.
        """
        ...

    def property_counts(
        self,
        event: str,
        property_name: str,
        *,
        from_date: str,
        to_date: str,
        type: Literal["general", "unique", "average"] = "general",
        unit: Literal["day", "week", "month"] = "day",
        values: list[str] | None = None,
        limit: int | None = None,
    ) -> PropertyCountsResult:
        """Get event counts broken down by property values.

        Args:
            event: Event name.
            property_name: Property to break down by.
            from_date: Start date (YYYY-MM-DD).
            to_date: End date (YYYY-MM-DD).
            type: Counting method.
            unit: Time unit.
            values: Optional list of property values to include.
            limit: Maximum number of property values.

        Returns:
            PropertyCountsResult with time-series per property value.

        Raises:
            ConfigError: If API credentials not available.
        """
        ...

    def activity_feed(
        self,
        distinct_ids: list[str],
        *,
        from_date: str | None = None,
        to_date: str | None = None,
    ) -> ActivityFeedResult:
        """Get activity feed for specific users.

        Args:
            distinct_ids: List of user identifiers.
            from_date: Optional start date filter.
            to_date: Optional end date filter.

        Returns:
            ActivityFeedResult with user events.

        Raises:
            ConfigError: If API credentials not available.
        """
        ...

    def insights(self, bookmark_id: int) -> InsightsResult:
        """Query a saved Insights report.

        Args:
            bookmark_id: ID of saved report.

        Returns:
            InsightsResult with report data.

        Raises:
            ConfigError: If API credentials not available.
        """
        ...

    def frequency(
        self,
        *,
        from_date: str,
        to_date: str,
        unit: Literal["day", "week", "month"] = "day",
        addiction_unit: Literal["hour", "day"] = "hour",
        event: str | None = None,
        where: str | None = None,
    ) -> FrequencyResult:
        """Analyze event frequency distribution.

        Args:
            from_date: Start date (YYYY-MM-DD).
            to_date: End date (YYYY-MM-DD).
            unit: Overall time unit.
            addiction_unit: Measurement granularity.
            event: Optional event filter.
            where: Optional WHERE clause.

        Returns:
            FrequencyResult with frequency distribution.

        Raises:
            ConfigError: If API credentials not available.
        """
        ...

    def segmentation_numeric(
        self,
        event: str,
        *,
        from_date: str,
        to_date: str,
        on: str,
        unit: Literal["hour", "day"] = "day",
        where: str | None = None,
        type: Literal["general", "unique", "average"] = "general",
    ) -> NumericBucketResult:
        """Bucket events by numeric property ranges.

        Args:
            event: Event name.
            from_date: Start date.
            to_date: End date.
            on: Numeric property expression.
            unit: Time unit.
            where: Optional filter.
            type: Counting method.

        Returns:
            NumericBucketResult with bucketed data.

        Raises:
            ConfigError: If API credentials not available.
        """
        ...

    def segmentation_sum(
        self,
        event: str,
        *,
        from_date: str,
        to_date: str,
        on: str,
        unit: Literal["hour", "day"] = "day",
        where: str | None = None,
    ) -> NumericSumResult:
        """Calculate sum of numeric property over time.

        Args:
            event: Event name.
            from_date: Start date.
            to_date: End date.
            on: Numeric property expression.
            unit: Time unit.
            where: Optional filter.

        Returns:
            NumericSumResult with sum values per period.

        Raises:
            ConfigError: If API credentials not available.
        """
        ...

    def segmentation_average(
        self,
        event: str,
        *,
        from_date: str,
        to_date: str,
        on: str,
        unit: Literal["hour", "day"] = "day",
        where: str | None = None,
    ) -> NumericAverageResult:
        """Calculate average of numeric property over time.

        Args:
            event: Event name.
            from_date: Start date.
            to_date: End date.
            on: Numeric property expression.
            unit: Time unit.
            where: Optional filter.

        Returns:
            NumericAverageResult with average values per period.

        Raises:
            ConfigError: If API credentials not available.
        """
        ...

    # =========================================================================
    # INTROSPECTION METHODS
    # =========================================================================

    def info(self) -> WorkspaceInfo:
        """Get metadata about this workspace.

        Returns:
            WorkspaceInfo with path, project_id, region, account, tables, size.
        """
        ...

    def tables(self) -> list[TableInfo]:
        """List tables in the local database.

        Returns:
            List of TableInfo objects (name, type, row_count, fetched_at).
        """
        ...

    def schema(self, table: str) -> TableSchema:
        """Get schema for a table.

        Args:
            table: Table name.

        Returns:
            TableSchema with column definitions.

        Raises:
            TableNotFoundError: If table doesn't exist.
        """
        ...

    # =========================================================================
    # TABLE MANAGEMENT METHODS
    # =========================================================================

    def drop(self, *names: str) -> None:
        """Drop specified tables.

        Args:
            *names: Table names to drop.

        Raises:
            TableNotFoundError: If any table doesn't exist.
        """
        ...

    def drop_all(self, type: Literal["events", "profiles"] | None = None) -> None:
        """Drop all tables, optionally filtered by type.

        Args:
            type: If specified, only drop tables of this type.
        """
        ...

    # =========================================================================
    # ESCAPE HATCHES
    # =========================================================================

    @property
    def connection(self) -> duckdb.DuckDBPyConnection:
        """Direct access to the DuckDB connection.

        Use this for operations not covered by the Workspace API.

        Returns:
            The underlying DuckDB connection.
        """
        ...

    @property
    def api(self) -> MixpanelAPIClient:
        """Direct access to the Mixpanel API client.

        Use this for API operations not covered by the Workspace API.

        Returns:
            The underlying MixpanelAPIClient.

        Raises:
            ConfigError: If API credentials not available.
        """
        ...
