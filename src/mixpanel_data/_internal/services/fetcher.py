"""Fetcher Service for Mixpanel data ingestion.

Coordinates data fetches from Mixpanel API to local DuckDB storage,
handling data transformation and progress reporting.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable, Iterator
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from mixpanel_data._internal.transforms import transform_event, transform_profile
from mixpanel_data.exceptions import DateRangeTooLargeError
from mixpanel_data.types import (
    BatchProgress,
    FetchResult,
    ParallelFetchResult,
    ParallelProfileResult,
    ProfileProgress,
    TableMetadata,
)

if TYPE_CHECKING:
    from mixpanel_data._internal.api_client import MixpanelAPIClient
    from mixpanel_data._internal.storage import StorageEngine

_logger = logging.getLogger(__name__)


class FetcherService:
    """Coordinates data fetches from Mixpanel API to local storage.

    This service bridges the MixpanelAPIClient and StorageEngine,
    handling data transformation and progress reporting.

    Example:
        ```python
        from mixpanel_data._internal.api_client import MixpanelAPIClient
        from mixpanel_data._internal.storage import StorageEngine
        from mixpanel_data._internal.services.fetcher import FetcherService

        client = MixpanelAPIClient(credentials)
        storage = StorageEngine(path)
        fetcher = FetcherService(client, storage)

        result = fetcher.fetch_events(
            name="events",
            from_date="2024-01-01",
            to_date="2024-01-31",
        )
        print(f"Fetched {result.rows} events")
        ```
    """

    def __init__(
        self,
        api_client: MixpanelAPIClient,
        storage: StorageEngine,
    ) -> None:
        """Initialize the fetcher service.

        Args:
            api_client: Authenticated Mixpanel API client.
            storage: DuckDB storage engine for persisting data.
        """
        self._api_client = api_client
        self._storage = storage

    def _validate_date_range(
        self,
        from_date: str,
        to_date: str,
        max_days: int = 100,
    ) -> None:
        """Validate date range format and constraints.

        Mixpanel Export API limits requests to 100 days maximum.
        This method validates the date range before making API calls.

        Args:
            from_date: Start date (YYYY-MM-DD format).
            to_date: End date (YYYY-MM-DD format).
            max_days: Maximum allowed days (default: 100).

        Raises:
            ValueError: If date format is invalid or from_date > to_date.
            DateRangeTooLargeError: If range exceeds max_days.
        """
        try:
            from_dt = datetime.strptime(from_date, "%Y-%m-%d")
            to_dt = datetime.strptime(to_date, "%Y-%m-%d")
        except ValueError as e:
            raise ValueError(f"Invalid date format. Use YYYY-MM-DD. Error: {e}") from e

        if from_dt > to_dt:
            raise ValueError(
                f"from_date ({from_date}) must be before or equal to to_date ({to_date})"
            )

        # Calculate days inclusive (+1 because both dates are inclusive)
        days = (to_dt - from_dt).days + 1
        if days > max_days:
            raise DateRangeTooLargeError(
                from_date=from_date,
                to_date=to_date,
                days_requested=days,
                max_days=max_days,
            )

    def fetch_events(
        self,
        name: str,
        from_date: str,
        to_date: str,
        *,
        events: list[str] | None = None,
        where: str | None = None,
        limit: int | None = None,
        progress_callback: Callable[[int], None] | None = None,
        append: bool = False,
        batch_size: int = 1000,
        parallel: bool = False,
        max_workers: int | None = None,
        on_batch_complete: Callable[[BatchProgress], None] | None = None,
        chunk_days: int = 7,
    ) -> FetchResult | ParallelFetchResult:
        """Fetch events from Mixpanel and store in local database.

        Args:
            name: Table name to create or append to.
            from_date: Start date (YYYY-MM-DD, inclusive).
            to_date: End date (YYYY-MM-DD, inclusive).
            events: Optional list of event names to filter.
            where: Optional filter expression.
            limit: Optional maximum number of events to return (max 100000).
            progress_callback: Optional callback invoked with row count during fetch.
            append: If True, append to existing table. If False (default), create new.
            batch_size: Number of rows per INSERT/COMMIT cycle. Controls the
                memory/IO tradeoff: smaller values use less memory but more
                disk IO; larger values use more memory but less IO.
                Default: 1000.
            parallel: If True, use parallel fetching with multiple threads.
                Splits date range into 7-day chunks and fetches concurrently.
                Default: False.
            max_workers: Maximum concurrent fetch threads when parallel=True.
                Default: 10. Ignored when parallel=False.
            on_batch_complete: Callback invoked when each batch completes
                during parallel fetch. Receives BatchProgress with status.
                Ignored when parallel=False.
            chunk_days: Days per chunk for parallel date range splitting.
                Default: 7. Ignored when parallel=False.

        Returns:
            FetchResult when parallel=False, ParallelFetchResult when parallel=True.

        Raises:
            TableExistsError: If table exists and append=False.
            TableNotFoundError: If table doesn't exist and append=True.
            AuthenticationError: If API credentials are invalid.
            RateLimitError: If Mixpanel rate limit is exceeded.
            QueryError: If filter expression is invalid.
            ValueError: If table name or date format is invalid.
            DateRangeTooLargeError: If date range exceeds 100 days (sequential only).
        """
        # Delegate to parallel fetcher if requested
        if parallel:
            from mixpanel_data._internal.services.parallel_fetcher import (
                ParallelFetcherService,
            )

            parallel_fetcher = ParallelFetcherService(
                api_client=self._api_client,
                storage=self._storage,
            )
            return parallel_fetcher.fetch_events(
                name=name,
                from_date=from_date,
                to_date=to_date,
                events=events,
                where=where,
                max_workers=max_workers,
                on_batch_complete=on_batch_complete,
                append=append,
                batch_size=batch_size,
                chunk_days=chunk_days,
            )

        # Sequential fetch - validate date range (100-day limit)
        self._validate_date_range(from_date, to_date)

        start_time = datetime.now(UTC)

        # Wrap progress callback for API client
        def on_api_batch(count: int) -> None:
            if progress_callback:
                progress_callback(count)

        # Stream events from API
        events_iter = self._api_client.export_events(
            from_date=from_date,
            to_date=to_date,
            events=events,
            where=where,
            limit=limit,
            on_batch=on_api_batch,
        )

        # Transform events as they stream through
        def transform_iterator() -> Iterator[dict[str, Any]]:
            for event in events_iter:
                yield transform_event(event)

        # Construct metadata
        fetched_at = datetime.now(UTC)
        metadata = TableMetadata(
            type="events",
            fetched_at=fetched_at,
            from_date=from_date,
            to_date=to_date,
            filter_events=events,
            filter_where=where,
        )

        # Store in database (handles TableExistsError/TableNotFoundError, transactions)
        if append:
            row_count = self._storage.append_events_table(
                name=name,
                data=transform_iterator(),
                metadata=metadata,
                batch_size=batch_size,
            )
        else:
            row_count = self._storage.create_events_table(
                name=name,
                data=transform_iterator(),
                metadata=metadata,
                batch_size=batch_size,
            )

        # Calculate final timing (use distinct variable to avoid confusion with metadata timestamp)
        completed_at = datetime.now(UTC)
        duration_seconds = (completed_at - start_time).total_seconds()

        return FetchResult(
            table=name,
            rows=row_count,
            type="events",
            duration_seconds=duration_seconds,
            date_range=(from_date, to_date),
            fetched_at=completed_at,
        )

    def fetch_profiles(
        self,
        name: str,
        *,
        where: str | None = None,
        cohort_id: str | None = None,
        output_properties: list[str] | None = None,
        progress_callback: Callable[[int], None] | None = None,
        append: bool = False,
        batch_size: int = 1000,
        distinct_id: str | None = None,
        distinct_ids: list[str] | None = None,
        group_id: str | None = None,
        behaviors: list[dict[str, Any]] | None = None,
        as_of_timestamp: int | None = None,
        include_all_users: bool = False,
        parallel: bool = False,
        max_workers: int | None = None,
        on_page_complete: Callable[[ProfileProgress], None] | None = None,
    ) -> FetchResult | ParallelProfileResult:
        """Fetch user profiles from Mixpanel and store in local database.

        Args:
            name: Table name to create or append to.
            where: Optional filter expression.
            cohort_id: Optional cohort ID to filter by. Only profiles that are
                members of this cohort will be returned.
            output_properties: Optional list of property names to include in
                the response. If None, all properties are returned.
            progress_callback: Optional callback invoked with row count during fetch.
            append: If True, append to existing table. If False (default), create new.
            batch_size: Number of rows per INSERT/COMMIT cycle. Controls the
                memory/IO tradeoff: smaller values use less memory but more
                disk IO; larger values use more memory but less IO.
                Default: 1000.
            distinct_id: Optional single user ID to fetch. Mutually exclusive
                with distinct_ids.
            distinct_ids: Optional list of user IDs to fetch. Mutually exclusive
                with distinct_id. Duplicates are automatically removed.
            group_id: Optional group type identifier (e.g., "companies") to fetch
                group profiles instead of user profiles.
            behaviors: Optional list of behavioral filters. Each dict should have
                'window' (e.g., "30d"), 'name' (identifier), and 'event_selectors'
                (list of {"event": "Name"}). Use with `where` parameter to filter,
                e.g., where='(behaviors["name"] > 0)'. Mutually exclusive with
                cohort_id.
            as_of_timestamp: Optional Unix timestamp to query profile state at
                a specific point in time. Must be in the past.
            include_all_users: If True, include all users and mark cohort membership.
                Only valid when cohort_id is provided.
            parallel: If True, use parallel fetching with multiple threads.
                Uses page-based parallelism for concurrent profile fetching.
                Default: False.
            max_workers: Maximum concurrent fetch threads when parallel=True.
                Default: 5, capped at 5. Ignored when parallel=False.
            on_page_complete: Callback invoked when each page completes during
                parallel fetch. Receives ProfileProgress with status.
                Ignored when parallel=False.

        Returns:
            FetchResult when parallel=False, ParallelProfileResult when parallel=True.
            The date_range field will be None for profiles.

        Raises:
            TableExistsError: If table exists and append=False.
            TableNotFoundError: If table doesn't exist and append=True.
            AuthenticationError: If API credentials are invalid.
            RateLimitError: If Mixpanel rate limit is exceeded.
            ValueError: If table name is invalid or parameters are mutually exclusive.
        """
        # Delegate to parallel fetcher if requested
        # Note: distinct_id/distinct_ids are not supported by page-based API,
        # so we fall back to sequential mode if those are specified
        if parallel and not distinct_id and not distinct_ids:
            from mixpanel_data._internal.services.parallel_profile_fetcher import (
                ParallelProfileFetcherService,
            )

            parallel_fetcher = ParallelProfileFetcherService(
                api_client=self._api_client,
                storage=self._storage,
            )
            return parallel_fetcher.fetch_profiles(
                name=name,
                where=where,
                cohort_id=cohort_id,
                output_properties=output_properties,
                group_id=group_id,
                behaviors=behaviors,
                as_of_timestamp=as_of_timestamp,
                include_all_users=include_all_users,
                max_workers=max_workers,
                on_page_complete=on_page_complete,
                append=append,
                batch_size=batch_size,
            )

        start_time = datetime.now(UTC)

        # Wrap progress callback for API client
        def on_api_batch(count: int) -> None:
            if progress_callback:
                progress_callback(count)

        # Stream profiles from API
        profiles_iter = self._api_client.export_profiles(
            where=where,
            cohort_id=cohort_id,
            output_properties=output_properties,
            on_batch=on_api_batch,
            distinct_id=distinct_id,
            distinct_ids=distinct_ids,
            group_id=group_id,
            behaviors=behaviors,
            as_of_timestamp=as_of_timestamp,
            include_all_users=include_all_users,
        )

        # Transform profiles as they stream through
        def transform_iterator() -> Iterator[dict[str, Any]]:
            for profile in profiles_iter:
                yield transform_profile(profile)

        # Serialize behaviors for metadata storage
        filter_behaviors = json.dumps(behaviors) if behaviors else None

        # Construct metadata
        fetched_at = datetime.now(UTC)
        metadata = TableMetadata(
            type="profiles",
            fetched_at=fetched_at,
            from_date=None,
            to_date=None,
            filter_events=None,
            filter_where=where,
            filter_cohort_id=cohort_id,
            filter_output_properties=output_properties,
            filter_group_id=group_id,
            filter_behaviors=filter_behaviors,
        )

        # Store in database (handles TableExistsError/TableNotFoundError, transactions)
        if append:
            row_count = self._storage.append_profiles_table(
                name=name,
                data=transform_iterator(),
                metadata=metadata,
                batch_size=batch_size,
            )
        else:
            row_count = self._storage.create_profiles_table(
                name=name,
                data=transform_iterator(),
                metadata=metadata,
                batch_size=batch_size,
            )

        # Calculate final timing (use distinct variable to avoid confusion with metadata timestamp)
        completed_at = datetime.now(UTC)
        duration_seconds = (completed_at - start_time).total_seconds()

        return FetchResult(
            table=name,
            rows=row_count,
            type="profiles",
            duration_seconds=duration_seconds,
            date_range=None,
            fetched_at=completed_at,
        )
