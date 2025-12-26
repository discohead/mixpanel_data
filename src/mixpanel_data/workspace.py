"""Workspace facade for Mixpanel data operations.

The Workspace class is the unified entry point for all Mixpanel data operations,
orchestrating DiscoveryService, FetcherService, LiveQueryService, and StorageEngine.

Example:
    Basic usage with credentials from config:

    ```python
    ws = Workspace()
    ws.fetch_events(from_date="2024-01-01", to_date="2024-01-31")
    df = ws.sql("SELECT * FROM events LIMIT 10")
    ws.close()
    ```

    Ephemeral workspace for temporary analysis:

    ```python
    with Workspace.ephemeral() as ws:
        ws.fetch_events(from_date="2024-01-01", to_date="2024-01-31")
        total = ws.sql_scalar("SELECT COUNT(*) FROM events")
    # Database automatically deleted
    ```

    Query-only access to existing database:

    ```python
    ws = Workspace.open("path/to/database.db")
    df = ws.sql("SELECT * FROM events")
    ws.close()
    ```
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
from mixpanel_data._internal.services.fetcher import (
    FetcherService,
    _transform_event,
    _transform_profile,
)
from mixpanel_data._internal.services.live_query import LiveQueryService
from mixpanel_data._internal.storage import StorageEngine
from mixpanel_data.exceptions import ConfigError, QueryError
from mixpanel_data.types import (
    ActivityFeedResult,
    BookmarkInfo,
    BookmarkType,
    ColumnStatsResult,
    ColumnSummary,
    EntityType,
    EventBreakdownResult,
    EventCountsResult,
    EventStats,
    FetchResult,
    FlowsResult,
    FrequencyResult,
    FunnelInfo,
    FunnelResult,
    JQLResult,
    LexiconSchema,
    NumericAverageResult,
    NumericBucketResult,
    NumericSumResult,
    PropertyCountsResult,
    RetentionResult,
    SavedCohort,
    SavedReportResult,
    SegmentationResult,
    SummaryResult,
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
        Basic usage with credentials from config:

        ```python
        ws = Workspace()
        ws.fetch_events(from_date="2024-01-01", to_date="2024-01-31")
        df = ws.sql("SELECT * FROM events LIMIT 10")
        ```

        Ephemeral workspace for temporary analysis:

        ```python
        with Workspace.ephemeral() as ws:
            ws.fetch_events(from_date="2024-01-01", to_date="2024-01-31")
            total = ws.sql_scalar("SELECT COUNT(*) FROM events")
        # Database automatically deleted
        ```

        Query-only access to existing database:

        ```python
        ws = Workspace.open("path/to/database.db")
        df = ws.sql("SELECT * FROM events")
        ```
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

        # Initialize storage lazily
        # Store path for lazy initialization, or use injected storage directly
        self._db_path: Path | None = None
        self._storage: StorageEngine | None = None

        if _storage is not None:
            # Injected storage - use directly
            self._storage = _storage
        else:
            # Determine database path for lazy initialization
            if path is not None:
                self._db_path = Path(path) if isinstance(path, str) else path
            else:
                # Default path: ~/.mp/data/{project_id}.db
                self._db_path = (
                    Path.home() / ".mp" / "data" / f"{self._credentials.project_id}.db"
                )
            # NOTE: StorageEngine is NOT created here - see storage property

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

        Example:
            ```python
            with Workspace.ephemeral() as ws:
                ws.fetch_events(from_date="2024-01-01", to_date="2024-01-31")
                print(ws.sql_scalar("SELECT COUNT(*) FROM events"))
            # Database file automatically deleted
            ```
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
    @contextmanager
    def memory(
        cls,
        account: str | None = None,
        project_id: str | None = None,
        region: str | None = None,
        _config_manager: ConfigManager | None = None,
        _api_client: MixpanelAPIClient | None = None,
    ) -> Iterator[Workspace]:
        """Create a workspace with true in-memory database.

        The database exists only in RAM with zero disk footprint.
        All data is lost when the context manager exits.

        Best for:
        - Small datasets where zero disk footprint is required
        - Unit tests without filesystem side effects
        - Quick exploratory queries

        For large datasets, prefer ephemeral() which benefits from
        DuckDB's compression (can be 8x faster for large workloads).

        Args:
            account: Named account from config file to use.
            project_id: Override project ID from credentials.
            region: Override region from credentials.
            _config_manager: Injected ConfigManager for testing.
            _api_client: Injected MixpanelAPIClient for testing.

        Yields:
            Workspace: A workspace with in-memory database.

        Example:
            ```python
            with Workspace.memory() as ws:
                ws.fetch_events(from_date="2024-01-01", to_date="2024-01-01")
                total = ws.sql_scalar("SELECT COUNT(*) FROM events")
            # Database gone - no cleanup needed, no files left behind
            ```
        """
        storage = StorageEngine.memory()
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

        Example:
            ```python
            ws = Workspace.open("my_data.db")
            df = ws.sql("SELECT * FROM events")
            ws.close()
            ```
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
        """Enter context manager.

        Returns:
            Self for use in 'with' statement.
        """
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: Any,
    ) -> None:
        """Exit context manager, closing all resources.

        Closes the database connection and HTTP client. Exceptions are
        NOT suppressed - they propagate normally after cleanup.
        """
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

    @staticmethod
    def test_credentials(account: str | None = None) -> dict[str, Any]:
        """Test account credentials by making a lightweight API call.

        This method verifies that credentials are valid and can access the
        Mixpanel API. It's useful for validating configuration before
        attempting more expensive operations.

        Args:
            account: Named account to test. If None, tests the default account
                or credentials from environment variables.

        Returns:
            Dict containing:
                - success: bool - Whether the test succeeded
                - account: str | None - Account name tested
                - project_id: str - Project ID from credentials
                - region: str - Region from credentials
                - events_found: int - Number of events found (validation metric)

        Raises:
            AccountNotFoundError: If named account doesn't exist.
            AuthenticationError: If credentials are invalid.
            ConfigError: If no credentials can be resolved.

        Example:
            ```python
            # Test default account
            result = Workspace.test_credentials()
            if result["success"]:
                print(f"Authenticated to project {result['project_id']}")

            # Test specific account
            result = Workspace.test_credentials("production")
            ```
        """
        config_manager = ConfigManager()
        credentials = config_manager.resolve_credentials(account)

        # Get account info if we used a named account
        account_info = None
        if account is not None:
            account_info = config_manager.get_account(account)
        else:
            # Check if credentials came from a default account
            accounts = config_manager.list_accounts()
            for acc in accounts:
                if acc.is_default:
                    account_info = acc
                    break

        # Create API client and test with a lightweight call
        api_client = MixpanelAPIClient(credentials)
        try:
            events = api_client.get_events()
            event_count = len(list(events)) if events else 0

            return {
                "success": True,
                "account": account_info.name if account_info else None,
                "project_id": credentials.project_id,
                "region": credentials.region,
                "events_found": event_count,
            }
        finally:
            api_client.close()

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

    @staticmethod
    def _try_float(value: Any) -> float | None:
        """Attempt to convert a value to float, returning None if not possible.

        Used for handling DuckDB SUMMARIZE output where avg/std may be
        non-numeric for certain column types (e.g., timestamps).

        Args:
            value: Value to convert.

        Returns:
            Float value if conversion succeeds, None otherwise.
        """
        if value is None:
            return None
        try:
            return float(value)
        except (ValueError, TypeError):
            return None

    @property
    def _discovery_service(self) -> DiscoveryService:
        """Get or create discovery service (lazy initialization)."""
        if self._discovery is None:
            self._discovery = DiscoveryService(self._require_api_client())
        return self._discovery

    @property
    def storage(self) -> StorageEngine:
        """Get or create storage engine (lazy initialization).

        Only connects to database when first accessed. API-only operations
        (discovery, live queries, streaming) don't touch the database.

        Returns:
            StorageEngine instance.

        Raises:
            DatabaseLockedError: If database is locked by another process.
            RuntimeError: If no database path configured (shouldn't happen
                in normal use).
        """
        if self._storage is None:
            if self._db_path is None:
                raise RuntimeError("No database path configured")
            self._storage = StorageEngine(path=self._db_path)
        return self._storage

    @property
    def _fetcher_service(self) -> FetcherService:
        """Get or create fetcher service (lazy initialization)."""
        if self._fetcher is None:
            self._fetcher = FetcherService(
                self._require_api_client(),
                self.storage,  # Uses lazy storage property
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

    def list_bookmarks(
        self,
        bookmark_type: BookmarkType | None = None,
    ) -> list[BookmarkInfo]:
        """List all saved reports (bookmarks) in the project.

        Retrieves metadata for all saved Insights, Funnel, Retention, and
        Flows reports in the project.

        Args:
            bookmark_type: Optional filter by report type. Valid values are
                'insights', 'funnels', 'retention', 'flows', 'launch-analysis'.
                If None, returns all bookmark types.

        Returns:
            List of BookmarkInfo objects with report metadata.
            Empty list if no bookmarks exist.

        Raises:
            ConfigError: If API credentials not available.
            QueryError: Permission denied or invalid type parameter.
        """
        return self._discovery_service.list_bookmarks(bookmark_type=bookmark_type)

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
    # LEXICON SCHEMA METHODS
    # =========================================================================

    def lexicon_schemas(
        self,
        *,
        entity_type: EntityType | None = None,
    ) -> list[LexiconSchema]:
        """List Lexicon schemas in the project.

        Retrieves documented event and profile property schemas from the
        Mixpanel Lexicon (data dictionary).

        Results are cached for the lifetime of the Workspace.

        Args:
            entity_type: Optional filter by type ("event" or "profile").
                If None, returns all schemas.

        Returns:
            Alphabetically sorted list of LexiconSchema objects.

        Raises:
            ConfigError: If API credentials not available.
            AuthenticationError: If credentials are invalid.

        Note:
            The Lexicon API has a strict 5 requests/minute rate limit.
            Caching helps avoid hitting this limit; call clear_discovery_cache()
            only when fresh data is needed.
        """
        return self._discovery_service.list_schemas(entity_type=entity_type)

    def lexicon_schema(
        self,
        entity_type: EntityType,
        name: str,
    ) -> LexiconSchema:
        """Get a single Lexicon schema by entity type and name.

        Retrieves a documented schema for a specific event or profile property
        from the Mixpanel Lexicon (data dictionary).

        Results are cached for the lifetime of the Workspace.

        Args:
            entity_type: Entity type ("event" or "profile").
            name: Entity name.

        Returns:
            LexiconSchema for the specified entity.

        Raises:
            ConfigError: If API credentials not available.
            AuthenticationError: If credentials are invalid.
            QueryError: If schema not found.

        Note:
            The Lexicon API has a strict 5 requests/minute rate limit.
            Caching helps avoid hitting this limit; call clear_discovery_cache()
            only when fresh data is needed.
        """
        return self._discovery_service.get_schema(entity_type, name)

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
    # STREAMING METHODS
    # =========================================================================

    def stream_events(
        self,
        *,
        from_date: str,
        to_date: str,
        events: list[str] | None = None,
        where: str | None = None,
        raw: bool = False,
    ) -> Iterator[dict[str, Any]]:
        """Stream events directly from Mixpanel API without storing.

        Yields events one at a time as they are received from the API.
        No database files or tables are created.

        Args:
            from_date: Start date inclusive (YYYY-MM-DD format).
            to_date: End date inclusive (YYYY-MM-DD format).
            events: Optional list of event names to filter. If None, all events returned.
            where: Optional Mixpanel filter expression (e.g., 'properties["country"]=="US"').
            raw: If True, return events in raw Mixpanel API format.
                 If False (default), return normalized format with datetime objects.

        Yields:
            dict[str, Any]: Event dictionaries in normalized or raw format.

        Raises:
            ConfigError: If API credentials are not available.
            AuthenticationError: If credentials are invalid.
            RateLimitError: If rate limit exceeded after max retries.
            QueryError: If filter expression is invalid.

        Example:
            ```python
            ws = Workspace()
            for event in ws.stream_events(from_date="2024-01-01", to_date="2024-01-31"):
                process(event)
            ws.close()
            ```

            With raw format:

            ```python
            for event in ws.stream_events(
                from_date="2024-01-01", to_date="2024-01-31", raw=True
            ):
                legacy_system.ingest(event)
            ```
        """
        api_client = self._require_api_client()
        event_iterator = api_client.export_events(
            from_date=from_date,
            to_date=to_date,
            events=events,
            where=where,
        )

        if raw:
            yield from event_iterator
        else:
            for event in event_iterator:
                yield _transform_event(event)

    def stream_profiles(
        self,
        *,
        where: str | None = None,
        raw: bool = False,
    ) -> Iterator[dict[str, Any]]:
        """Stream user profiles directly from Mixpanel API without storing.

        Yields profiles one at a time as they are received from the API.
        No database files or tables are created.

        Args:
            where: Optional Mixpanel filter expression for profile properties.
            raw: If True, return profiles in raw Mixpanel API format.
                 If False (default), return normalized format.

        Yields:
            dict[str, Any]: Profile dictionaries in normalized or raw format.

        Raises:
            ConfigError: If API credentials are not available.
            AuthenticationError: If credentials are invalid.
            RateLimitError: If rate limit exceeded after max retries.

        Example:
            ```python
            ws = Workspace()
            for profile in ws.stream_profiles():
                sync_to_crm(profile)
            ws.close()
            ```

            Filter to premium users:

            ```python
            for profile in ws.stream_profiles(where='properties["plan"]=="premium"'):
                send_survey(profile)
            ```
        """
        api_client = self._require_api_client()
        profile_iterator = api_client.export_profiles(where=where)

        if raw:
            yield from profile_iterator
        else:
            for profile in profile_iterator:
                yield _transform_profile(profile)

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
        return self.storage.execute_df(query)

    def sql_scalar(self, query: str) -> Any:
        """Execute SQL query and return single scalar value.

        Args:
            query: SQL query that returns a single value.

        Returns:
            The scalar result (int, float, str, etc.).

        Raises:
            QueryError: If query is invalid or returns multiple values.
        """
        return self.storage.execute_scalar(query)

    def sql_rows(self, query: str) -> list[tuple[Any, ...]]:
        """Execute SQL query and return results as list of tuples.

        Args:
            query: SQL query string.

        Returns:
            List of row tuples.

        Raises:
            QueryError: If query is invalid.
        """
        return self.storage.execute_rows(query)

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

    def query_saved_report(self, bookmark_id: int) -> SavedReportResult:
        """Query a saved report (Insights, Retention, or Funnel).

        Executes a saved report by its bookmark ID. The report type is
        automatically detected from the response headers.

        Args:
            bookmark_id: ID of saved report (from list_bookmarks or Mixpanel URL).

        Returns:
            SavedReportResult with report data and report_type property.

        Raises:
            ConfigError: If API credentials not available.
            QueryError: If bookmark_id is invalid or report not found.
        """
        return self._live_query_service.query_saved_report(bookmark_id=bookmark_id)

    def query_flows(self, bookmark_id: int) -> FlowsResult:
        """Query a saved Flows report.

        Executes a saved Flows report by its bookmark ID, returning
        step data, breakdowns, and conversion rates.

        Args:
            bookmark_id: ID of saved flows report (from list_bookmarks or Mixpanel URL).

        Returns:
            FlowsResult with steps, breakdowns, and conversion rate.

        Raises:
            ConfigError: If API credentials not available.
            QueryError: If bookmark_id is invalid or report not found.
        """
        return self._live_query_service.query_flows(bookmark_id=bookmark_id)

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
        path = self.storage.path
        tables = [t.name for t in self.storage.list_tables()]

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
        return self.storage.list_tables()

    def table_schema(self, table: str) -> TableSchema:
        """Get schema for a table in the local database.

        Args:
            table: Table name.

        Returns:
            TableSchema with column definitions.

        Raises:
            TableNotFoundError: If table doesn't exist.
        """
        return self.storage.get_schema(table)

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
            ```python
            ws = Workspace()
            ws.sample("events")  # 10 random rows
            ws.sample("events", n=5)  # 5 random rows
            ```
        """
        # Validate table exists
        self.storage.get_schema(table)

        # Use DuckDB's reservoir sampling
        sql = f'SELECT * FROM "{table}" USING SAMPLE {n}'
        return self.storage.execute_df(sql)

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
            ```python
            result = ws.summarize("events")
            result.row_count         # 1234567
            result.columns[0].null_percentage  # 0.5
            result.df                # Full summary as DataFrame
            ```
        """
        # Validate table exists
        self.storage.get_schema(table)

        # Get row count
        row_count = self.storage.execute_scalar(f'SELECT COUNT(*) FROM "{table}"')

        # Get column statistics using SUMMARIZE
        summary_df = self.storage.execute_df(f'SUMMARIZE "{table}"')

        # Convert to ColumnSummary objects (to_dict is more efficient than iterrows)
        columns: list[ColumnSummary] = []
        for row in summary_df.to_dict("records"):
            columns.append(
                ColumnSummary(
                    column_name=str(row["column_name"]),
                    column_type=str(row["column_type"]),
                    min=row["min"],
                    max=row["max"],
                    approx_unique=int(row["approx_unique"]),
                    avg=self._try_float(row["avg"]),
                    std=self._try_float(row["std"]),
                    q25=row["q25"],
                    q50=row["q50"],
                    q75=row["q75"],
                    count=int(row["count"]),
                    null_percentage=float(row["null_percentage"]),
                )
            )

        return SummaryResult(
            table=table,
            row_count=int(row_count),
            columns=columns,
        )

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
            ```python
            breakdown = ws.event_breakdown("events")
            breakdown.total_events           # 1234567
            breakdown.events[0].event_name   # "Page View"
            breakdown.events[0].pct_of_total # 45.2
            ```
        """
        # Validate table exists and get schema
        schema = self.storage.get_schema(table)
        column_names = {col.name for col in schema.columns}

        # Check for required columns
        required_columns = {"event_name", "event_time", "distinct_id"}
        missing = required_columns - column_names
        if missing:
            raise QueryError(
                f"event_breakdown() requires columns {required_columns}, "
                f"but '{table}' is missing: {missing}",
                status_code=0,
            )

        # Get aggregate statistics
        agg_sql = f"""
            SELECT
                COUNT(*) as total_events,
                COUNT(DISTINCT distinct_id) as total_users,
                MIN(event_time) as min_time,
                MAX(event_time) as max_time
            FROM "{table}"
        """
        agg_result = self.storage.execute_rows(agg_sql)
        total_events, total_users, min_time, max_time = agg_result[0]

        # Handle empty table
        if total_events == 0:
            return EventBreakdownResult(
                table=table,
                total_events=0,
                total_users=0,
                date_range=(datetime.min, datetime.min),
                events=[],
            )

        # Get per-event statistics
        breakdown_sql = f"""
            SELECT
                event_name,
                COUNT(*) as count,
                COUNT(DISTINCT distinct_id) as unique_users,
                MIN(event_time) as first_seen,
                MAX(event_time) as last_seen,
                ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 2) as pct_of_total
            FROM "{table}"
            GROUP BY event_name
            ORDER BY count DESC
        """
        breakdown_rows = self.storage.execute_rows(breakdown_sql)

        events: list[EventStats] = []
        for row in breakdown_rows:
            event_name, count, unique_users, first_seen, last_seen, pct = row
            events.append(
                EventStats(
                    event_name=str(event_name),
                    count=int(count),
                    unique_users=int(unique_users),
                    first_seen=first_seen
                    if isinstance(first_seen, datetime)
                    else datetime.fromisoformat(str(first_seen)),
                    last_seen=last_seen
                    if isinstance(last_seen, datetime)
                    else datetime.fromisoformat(str(last_seen)),
                    pct_of_total=float(pct),
                )
            )

        return EventBreakdownResult(
            table=table,
            total_events=int(total_events),
            total_users=int(total_users),
            date_range=(
                min_time
                if isinstance(min_time, datetime)
                else datetime.fromisoformat(str(min_time)),
                max_time
                if isinstance(max_time, datetime)
                else datetime.fromisoformat(str(max_time)),
            ),
            events=events,
        )

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
            All keys across all events:

            ```python
            ws.property_keys("events")
            # ['$browser', '$city', 'page', 'referrer', 'user_plan']
            ```

            Keys for specific event type:

            ```python
            ws.property_keys("events", event="Purchase")
            # ['amount', 'currency', 'product_id', 'quantity']
            ```
        """
        # Validate table exists and get schema
        schema = self.storage.get_schema(table)
        column_names = {col.name for col in schema.columns}

        # Check for required column
        if "properties" not in column_names:
            raise QueryError(
                f"property_keys() requires a 'properties' column, "
                f"but '{table}' does not have one",
                status_code=0,
            )

        # Build query with optional event filter
        if event is not None:
            # Check if event_name column exists
            if "event_name" not in column_names:
                raise QueryError(
                    f"Cannot filter by event: '{table}' lacks 'event_name' column",
                    status_code=0,
                )
            sql = f"""
                SELECT DISTINCT unnest(json_keys(properties)) as key
                FROM "{table}"
                WHERE event_name = ?
                ORDER BY key
            """
            rows = self.storage.connection.execute(sql, [event]).fetchall()
        else:
            sql = f"""
                SELECT DISTINCT unnest(json_keys(properties)) as key
                FROM "{table}"
                ORDER BY key
            """
            rows = self.storage.execute_rows(sql)

        return [str(row[0]) for row in rows]

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
            Analyze standard column:

            ```python
            stats = ws.column_stats("events", "event_name")
            stats.unique_count      # 47
            stats.top_values[:3]    # [('Page View', 45230), ...]
            ```

            Analyze JSON property:

            ```python
            stats = ws.column_stats("events", "properties->>'$.country'")
            ```

        Security:
            The column parameter is interpolated directly into SQL queries
            to allow expression syntax. Only use with trusted input from
            developers or AI coding agents. Do not pass untrusted user input.
        """
        # Validate table exists
        self.storage.get_schema(table)

        # Get total row count
        total_rows = self.storage.execute_scalar(f'SELECT COUNT(*) FROM "{table}"')

        # Get basic stats: count, null_count, approx unique
        stats_sql = f"""
            SELECT
                COUNT({column}) as count,
                COUNT(*) - COUNT({column}) as null_count,
                APPROX_COUNT_DISTINCT({column}) as unique_count
            FROM "{table}"
        """
        try:
            stats_result = self.storage.execute_rows(stats_sql)
        except Exception as e:
            raise QueryError(
                f"Invalid column expression: {column}. Error: {e}",
                status_code=0,
            ) from e

        count, null_count, unique_count = stats_result[0]

        # Calculate percentages
        null_pct = (null_count / total_rows * 100) if total_rows > 0 else 0.0
        unique_pct = (unique_count / count * 100) if count > 0 else 0.0

        # Get top values
        top_sql = f"""
            SELECT {column} as value, COUNT(*) as cnt
            FROM "{table}"
            WHERE {column} IS NOT NULL
            GROUP BY {column}
            ORDER BY cnt DESC
            LIMIT {top_n}
        """
        top_rows = self.storage.execute_rows(top_sql)
        top_values: list[tuple[Any, int]] = [(row[0], int(row[1])) for row in top_rows]

        # Detect column type to determine if numeric stats apply
        type_sql = (
            f'SELECT typeof({column}) FROM "{table}" WHERE {column} IS NOT NULL LIMIT 1'
        )
        try:
            type_result = self.storage.execute_rows(type_sql)
            dtype = str(type_result[0][0]) if type_result else "UNKNOWN"
        except Exception:
            dtype = "UNKNOWN"

        # Get numeric stats if applicable
        min_val: float | None = None
        max_val: float | None = None
        mean_val: float | None = None
        std_val: float | None = None

        numeric_types = {
            "INTEGER",
            "BIGINT",
            "DOUBLE",
            "FLOAT",
            "DECIMAL",
            "HUGEINT",
            "SMALLINT",
            "TINYINT",
            "UBIGINT",
            "UINTEGER",
            "USMALLINT",
            "UTINYINT",
        }
        if dtype.upper() in numeric_types:
            numeric_sql = f"""
                SELECT
                    MIN({column}) as min_val,
                    MAX({column}) as max_val,
                    AVG({column}) as mean_val,
                    STDDEV({column}) as std_val
                FROM "{table}"
            """
            try:
                numeric_result = self.storage.execute_rows(numeric_sql)
                if numeric_result:
                    min_val = (
                        float(numeric_result[0][0])
                        if numeric_result[0][0] is not None
                        else None
                    )
                    max_val = (
                        float(numeric_result[0][1])
                        if numeric_result[0][1] is not None
                        else None
                    )
                    mean_val = (
                        float(numeric_result[0][2])
                        if numeric_result[0][2] is not None
                        else None
                    )
                    std_val = (
                        float(numeric_result[0][3])
                        if numeric_result[0][3] is not None
                        else None
                    )
            except Exception:
                # Not numeric, skip
                pass

        return ColumnStatsResult(
            table=table,
            column=column,
            dtype=dtype,
            count=int(count),
            null_count=int(null_count),
            null_pct=round(null_pct, 2),
            unique_count=int(unique_count),
            unique_pct=round(unique_pct, 2),
            top_values=top_values,
            min=min_val,
            max=max_val,
            mean=mean_val,
            std=std_val,
        )

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
            self.storage.drop_table(name)

    def drop_all(self, type: Literal["events", "profiles"] | None = None) -> None:
        """Drop all tables, optionally filtered by type.

        Args:
            type: If specified, only drop tables of this type.
        """
        tables = self.storage.list_tables()
        for table in tables:
            if type is None or table.type == type:
                self.storage.drop_table(table.name)

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
        return self.storage.connection

    @property
    def api(self) -> MixpanelAPIClient:
        """Direct access to the Mixpanel API client.

        Use this escape hatch for Mixpanel API operations not covered by the
        Workspace class. The client handles authentication automatically.

        The client provides:
            - ``request(method, url, **kwargs)``: Make authenticated requests
              to any Mixpanel API endpoint.
            - ``project_id``: The configured project ID for constructing URLs.
            - ``region``: The configured region ('us', 'eu', or 'in').

        Returns:
            The underlying MixpanelAPIClient.

        Raises:
            ConfigError: If API credentials not available.

        Example:
            Fetch event schema from the Lexicon Schemas API::

                import mixpanel_data as mp
                from urllib.parse import quote

                ws = mp.Workspace()
                client = ws.api

                # Build the URL with proper encoding
                event_name = quote("Added To Cart", safe="")
                url = f"https://mixpanel.com/api/app/projects/{client.project_id}/schemas/event/{event_name}"

                # Make the authenticated request
                schema = client.request("GET", url)
                print(schema)
        """
        return self._require_api_client()
