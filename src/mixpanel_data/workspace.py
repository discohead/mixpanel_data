"""Workspace facade for Mixpanel data operations.

The Workspace class is the unified entry point for all Mixpanel data operations,
orchestrating DiscoveryService, FetcherService, LiveQueryService, and StorageEngine.

Example:
    Basic usage with credentials from config::

        ws = Workspace()
        ws.fetch_events(from_date="2024-01-01", to_date="2024-01-31")
        df = ws.sql("SELECT * FROM events LIMIT 10")
        ws.close()

    Ephemeral workspace for temporary analysis::

        with Workspace.ephemeral() as ws:
            ws.fetch_events(from_date="2024-01-01", to_date="2024-01-31")
            total = ws.sql_scalar("SELECT COUNT(*) FROM events")
        # Database automatically deleted

    Query-only access to existing database::

        ws = Workspace.open("path/to/database.db")
        df = ws.sql("SELECT * FROM events")
        ws.close()
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

import duckdb
import pandas as pd

from mixpanel_data._internal.api_client import MixpanelAPIClient
from mixpanel_data._internal.config import ConfigManager, Credentials
from mixpanel_data._internal.services.discovery import DiscoveryService
from mixpanel_data._internal.services.fetcher import FetcherService
from mixpanel_data._internal.services.live_query import LiveQueryService
from mixpanel_data._internal.storage import StorageEngine
from mixpanel_data.exceptions import ConfigError
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
        # Store injected or create default ConfigManager
        self._config_manager = _config_manager or ConfigManager()

        # Resolve credentials
        self._credentials: Credentials | None = None
        self._account_name: str | None = account

        # Resolve credentials (may raise ConfigError or AccountNotFoundError)
        self._credentials = self._config_manager.resolve_credentials(account)

        # Apply overrides if provided
        if project_id or region:
            from typing import cast

            from pydantic import SecretStr

            from mixpanel_data._internal.config import RegionType

            resolved_region = region or self._credentials.region
            self._credentials = Credentials(
                username=self._credentials.username,
                secret=SecretStr(self._credentials.secret.get_secret_value()),
                project_id=project_id or self._credentials.project_id,
                region=cast(RegionType, resolved_region),
            )

        # Initialize storage
        if _storage is not None:
            self._storage = _storage
        else:
            # Determine database path
            if path is not None:
                db_path = Path(path) if isinstance(path, str) else path
            else:
                # Default path: ~/.mp/data/{project_id}.db
                db_path = (
                    Path.home() / ".mp" / "data" / f"{self._credentials.project_id}.db"
                )
            self._storage = StorageEngine(path=db_path)

        # Lazy-initialized services (None until first use)
        self._api_client: MixpanelAPIClient | None = _api_client
        self._discovery: DiscoveryService | None = None
        self._fetcher: FetcherService | None = None
        self._live_query: LiveQueryService | None = None

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
        storage = StorageEngine.ephemeral()
        ws = cls(
            account=account,
            project_id=project_id,
            region=region,
            _config_manager=_config_manager,
            _api_client=_api_client,
            _storage=storage,
        )
        try:
            yield ws
        finally:
            ws.close()

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
        db_path = Path(path) if isinstance(path, str) else path
        storage = StorageEngine.open_existing(db_path)

        # Create instance without credential resolution
        instance = object.__new__(cls)
        instance._config_manager = ConfigManager()
        instance._credentials = None
        instance._account_name = None
        instance._storage = storage
        instance._api_client = None
        instance._discovery = None
        instance._fetcher = None
        instance._live_query = None

        return instance

    def __enter__(self) -> Workspace:
        """Enter context manager."""
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: Any,
    ) -> None:
        """Exit context manager, closing all resources."""
        self.close()

    def close(self) -> None:
        """Close all resources (database connection, HTTP client).

        This method is idempotent and safe to call multiple times.
        """
        # Close storage
        if self._storage is not None:
            self._storage.close()

        # Close API client if we created one
        if self._api_client is not None:
            self._api_client.close()
            self._api_client = None

    # =========================================================================
    # PRIVATE HELPERS
    # =========================================================================

    def _get_api_client(self) -> MixpanelAPIClient:
        """Get or create the API client (lazy initialization).

        Returns:
            MixpanelAPIClient instance.
        """
        if self._api_client is None:
            if self._credentials is None:
                raise ConfigError(
                    "API access requires credentials. "
                    "Use Workspace() with credentials instead of Workspace.open()."
                )
            self._api_client = MixpanelAPIClient(self._credentials)
        return self._api_client

    def _require_api_client(self) -> MixpanelAPIClient:
        """Get API client or raise if unavailable.

        Returns:
            MixpanelAPIClient instance.

        Raises:
            ConfigError: If credentials are not available.
        """
        if self._credentials is None:
            raise ConfigError(
                "API access requires credentials. "
                "Use Workspace() with credentials instead of Workspace.open()."
            )
        return self._get_api_client()

    @property
    def _discovery_service(self) -> DiscoveryService:
        """Get or create discovery service (lazy initialization)."""
        if self._discovery is None:
            self._discovery = DiscoveryService(self._require_api_client())
        return self._discovery

    @property
    def _fetcher_service(self) -> FetcherService:
        """Get or create fetcher service (lazy initialization)."""
        if self._fetcher is None:
            self._fetcher = FetcherService(
                self._require_api_client(),
                self._storage,
            )
        return self._fetcher

    @property
    def _live_query_service(self) -> LiveQueryService:
        """Get or create live query service (lazy initialization)."""
        if self._live_query is None:
            self._live_query = LiveQueryService(self._require_api_client())
        return self._live_query

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
        return self._discovery_service.list_events()

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
        return self._discovery_service.list_properties(event)

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
        return self._discovery_service.list_property_values(
            property_name, event=event, limit=limit
        )

    def funnels(self) -> list[FunnelInfo]:
        """List saved funnels in the Mixpanel project.

        Results are cached for the lifetime of the Workspace.

        Returns:
            List of FunnelInfo objects (funnel_id, name).

        Raises:
            ConfigError: If API credentials not available.
        """
        return self._discovery_service.list_funnels()

    def cohorts(self) -> list[SavedCohort]:
        """List saved cohorts in the Mixpanel project.

        Results are cached for the lifetime of the Workspace.

        Returns:
            List of SavedCohort objects.

        Raises:
            ConfigError: If API credentials not available.
        """
        return self._discovery_service.list_cohorts()

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
        return self._discovery_service.list_top_events(type=type, limit=limit)

    def clear_discovery_cache(self) -> None:
        """Clear cached discovery results.

        Subsequent discovery calls will fetch fresh data from the API.
        """
        if self._discovery is not None:
            self._discovery.clear_cache()

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
        # Create progress callback if requested
        progress_callback = None
        pbar = None
        if progress:
            try:
                from rich.progress import Progress, SpinnerColumn, TextColumn

                pbar = Progress(
                    SpinnerColumn(),
                    TextColumn("[progress.description]{task.description}"),
                    TextColumn("{task.completed} rows"),
                )
                task = pbar.add_task("Fetching events...", total=None)
                pbar.start()

                def callback(count: int) -> None:
                    pbar.update(task, completed=count)

                progress_callback = callback
            except Exception:
                # Progress bar unavailable or failed to initialize, skip silently
                pass

        try:
            result = self._fetcher_service.fetch_events(
                name=name,
                from_date=from_date,
                to_date=to_date,
                events=events,
                where=where,
                progress_callback=progress_callback,
            )
        finally:
            if pbar is not None:
                pbar.stop()

        return result

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
        # Create progress callback if requested
        progress_callback = None
        pbar = None
        if progress:
            try:
                from rich.progress import Progress, SpinnerColumn, TextColumn

                pbar = Progress(
                    SpinnerColumn(),
                    TextColumn("[progress.description]{task.description}"),
                    TextColumn("{task.completed} rows"),
                )
                task = pbar.add_task("Fetching profiles...", total=None)
                pbar.start()

                def callback(count: int) -> None:
                    pbar.update(task, completed=count)

                progress_callback = callback
            except Exception:
                # Progress bar unavailable or failed to initialize, skip silently
                pass

        try:
            result = self._fetcher_service.fetch_profiles(
                name=name,
                where=where,
                progress_callback=progress_callback,
            )
        finally:
            if pbar is not None:
                pbar.stop()

        return result

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
        return self._storage.execute_df(query)

    def sql_scalar(self, query: str) -> Any:
        """Execute SQL query and return single scalar value.

        Args:
            query: SQL query that returns a single value.

        Returns:
            The scalar result (int, float, str, etc.).

        Raises:
            QueryError: If query is invalid or returns multiple values.
        """
        return self._storage.execute_scalar(query)

    def sql_rows(self, query: str) -> list[tuple[Any, ...]]:
        """Execute SQL query and return results as list of tuples.

        Args:
            query: SQL query string.

        Returns:
            List of row tuples.

        Raises:
            QueryError: If query is invalid.
        """
        return self._storage.execute_rows(query)

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
        return self._live_query_service.segmentation(
            event=event,
            from_date=from_date,
            to_date=to_date,
            on=on,
            unit=unit,
            where=where,
        )

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
        return self._live_query_service.funnel(
            funnel_id=funnel_id,
            from_date=from_date,
            to_date=to_date,
            unit=unit,
            on=on,
        )

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
        return self._live_query_service.retention(
            born_event=born_event,
            return_event=return_event,
            from_date=from_date,
            to_date=to_date,
            born_where=born_where,
            return_where=return_where,
            interval=interval,
            interval_count=interval_count,
            unit=unit,
        )

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
        return self._live_query_service.jql(script=script, params=params)

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
        return self._live_query_service.event_counts(
            events=events,
            from_date=from_date,
            to_date=to_date,
            type=type,
            unit=unit,
        )

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
        return self._live_query_service.property_counts(
            event=event,
            property_name=property_name,
            from_date=from_date,
            to_date=to_date,
            type=type,
            unit=unit,
            values=values,
            limit=limit,
        )

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
        return self._live_query_service.activity_feed(
            distinct_ids=distinct_ids,
            from_date=from_date,
            to_date=to_date,
        )

    def insights(self, bookmark_id: int) -> InsightsResult:
        """Query a saved Insights report.

        Args:
            bookmark_id: ID of saved report.

        Returns:
            InsightsResult with report data.

        Raises:
            ConfigError: If API credentials not available.
        """
        return self._live_query_service.insights(bookmark_id=bookmark_id)

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
        return self._live_query_service.frequency(
            from_date=from_date,
            to_date=to_date,
            unit=unit,
            addiction_unit=addiction_unit,
            event=event,
            where=where,
        )

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
        return self._live_query_service.segmentation_numeric(
            event=event,
            from_date=from_date,
            to_date=to_date,
            on=on,
            unit=unit,
            where=where,
            type=type,
        )

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
        return self._live_query_service.segmentation_sum(
            event=event,
            from_date=from_date,
            to_date=to_date,
            on=on,
            unit=unit,
            where=where,
        )

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
        return self._live_query_service.segmentation_average(
            event=event,
            from_date=from_date,
            to_date=to_date,
            on=on,
            unit=unit,
            where=where,
        )

    # =========================================================================
    # INTROSPECTION METHODS
    # =========================================================================

    def info(self) -> WorkspaceInfo:
        """Get metadata about this workspace.

        Returns:
            WorkspaceInfo with path, project_id, region, account, tables, size.
        """
        path = self._storage.path
        tables = [t.name for t in self._storage.list_tables()]

        # Calculate database size and creation time
        size_mb = 0.0
        created_at: datetime | None = None
        if path is not None and path.exists():
            try:
                stat = path.stat()
                size_mb = stat.st_size / 1_000_000
                created_at = datetime.fromtimestamp(stat.st_ctime)
            except (OSError, PermissionError):
                # File became inaccessible, use defaults
                pass

        return WorkspaceInfo(
            path=path,
            project_id=self._credentials.project_id if self._credentials else "unknown",
            region=self._credentials.region if self._credentials else "unknown",
            account=self._account_name,
            tables=tables,
            size_mb=size_mb,
            created_at=created_at,
        )

    def tables(self) -> list[TableInfo]:
        """List tables in the local database.

        Returns:
            List of TableInfo objects (name, type, row_count, fetched_at).
        """
        return self._storage.list_tables()

    def schema(self, table: str) -> TableSchema:
        """Get schema for a table.

        Args:
            table: Table name.

        Returns:
            TableSchema with column definitions.

        Raises:
            TableNotFoundError: If table doesn't exist.
        """
        return self._storage.get_schema(table)

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
        for name in names:
            self._storage.drop_table(name)

    def drop_all(self, type: Literal["events", "profiles"] | None = None) -> None:
        """Drop all tables, optionally filtered by type.

        Args:
            type: If specified, only drop tables of this type.
        """
        tables = self._storage.list_tables()
        for table in tables:
            if type is None or table.type == type:
                self._storage.drop_table(table.name)

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
        return self._storage.connection

    @property
    def api(self) -> MixpanelAPIClient:
        """Direct access to the Mixpanel API client.

        Use this for API operations not covered by the Workspace API.

        Returns:
            The underlying MixpanelAPIClient.

        Raises:
            ConfigError: If API credentials not available.
        """
        return self._require_api_client()
