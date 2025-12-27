"""Fetcher Service for Mixpanel data ingestion.

Coordinates data fetches from Mixpanel API to local DuckDB storage,
handling data transformation and progress reporting.
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import Callable, Iterator
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from mixpanel_data.exceptions import DateRangeTooLargeError
from mixpanel_data.types import FetchResult, TableMetadata

if TYPE_CHECKING:
    from mixpanel_data._internal.api_client import MixpanelAPIClient
    from mixpanel_data._internal.storage import StorageEngine

_logger = logging.getLogger(__name__)

# Reserved keys that _transform_event extracts from properties.
# These are standard Mixpanel fields that become top-level columns in storage.
_RESERVED_EVENT_KEYS = frozenset({"distinct_id", "time", "$insert_id"})

# Reserved keys that _transform_profile extracts from properties.
# These are standard Mixpanel fields that become top-level columns in storage.
_RESERVED_PROFILE_KEYS = frozenset({"$last_seen"})


def _transform_event(event: dict[str, Any]) -> dict[str, Any]:
    """Transform API event to storage format.

    Args:
        event: Raw event from Mixpanel Export API with 'event' and 'properties' keys.

    Returns:
        Transformed event dict with event_name, event_time, distinct_id,
        insert_id, and properties keys.
    """
    properties = event.get("properties", {})

    # Extract and remove standard fields from properties (shallow copy to avoid mutation)
    remaining_props = dict(properties)
    distinct_id = remaining_props.pop("distinct_id", "")
    event_time_raw = remaining_props.pop("time", 0)
    insert_id = remaining_props.pop("$insert_id", None)

    # Convert Unix timestamp to datetime
    # Mixpanel Export API returns time as Unix timestamp in seconds (integer)
    event_time = datetime.fromtimestamp(event_time_raw, tz=UTC)

    # Generate UUID if $insert_id is missing
    if insert_id is None:
        insert_id = str(uuid.uuid4())
        _logger.debug("Generated insert_id for event missing $insert_id")

    return {
        "event_name": event.get("event", ""),
        "event_time": event_time,
        "distinct_id": distinct_id,
        "insert_id": insert_id,
        "properties": remaining_props,
    }


def _transform_profile(profile: dict[str, Any]) -> dict[str, Any]:
    """Transform API profile to storage format.

    Args:
        profile: Raw profile from Mixpanel Engage API with '$distinct_id'
            and '$properties' keys.

    Returns:
        Transformed profile dict with distinct_id, last_seen, and properties keys.
    """
    distinct_id = profile.get("$distinct_id", "")
    properties = profile.get("$properties", {})

    # Extract and remove $last_seen from properties (shallow copy to avoid mutation)
    remaining_props = dict(properties)
    last_seen = remaining_props.pop("$last_seen", None)

    return {
        "distinct_id": distinct_id,
        "last_seen": last_seen,
        "properties": remaining_props,
    }


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
        progress_callback: Callable[[int], None] | None = None,
    ) -> FetchResult:
        """Fetch events from Mixpanel and store in local database.

        Args:
            name: Table name to create (alphanumeric + underscore, no leading _).
            from_date: Start date (YYYY-MM-DD, inclusive).
            to_date: End date (YYYY-MM-DD, inclusive).
            events: Optional list of event names to filter.
            where: Optional filter expression.
            progress_callback: Optional callback invoked with row count during fetch.

        Returns:
            FetchResult with table name, row count, duration, and metadata.

        Raises:
            TableExistsError: If table with given name already exists.
            AuthenticationError: If API credentials are invalid.
            RateLimitError: If Mixpanel rate limit is exceeded.
            QueryError: If filter expression is invalid.
            ValueError: If table name or date format is invalid.
            DateRangeTooLargeError: If date range exceeds 100 days.
        """
        # Validate date range before making API calls
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
            on_batch=on_api_batch,
        )

        # Transform events as they stream through
        def transform_iterator() -> Iterator[dict[str, Any]]:
            for event in events_iter:
                yield _transform_event(event)

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

        # Store in database (handles TableExistsError, transactions, etc.)
        row_count = self._storage.create_events_table(
            name=name,
            data=transform_iterator(),
            metadata=metadata,
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
        progress_callback: Callable[[int], None] | None = None,
    ) -> FetchResult:
        """Fetch user profiles from Mixpanel and store in local database.

        Args:
            name: Table name to create (alphanumeric + underscore, no leading _).
            where: Optional filter expression.
            progress_callback: Optional callback invoked with row count during fetch.

        Returns:
            FetchResult with table name, row count, duration, and metadata.
            The date_range field will be None for profiles.

        Raises:
            TableExistsError: If table with given name already exists.
            AuthenticationError: If API credentials are invalid.
            RateLimitError: If Mixpanel rate limit is exceeded.
            ValueError: If table name is invalid.
        """
        start_time = datetime.now(UTC)

        # Wrap progress callback for API client
        def on_api_batch(count: int) -> None:
            if progress_callback:
                progress_callback(count)

        # Stream profiles from API
        profiles_iter = self._api_client.export_profiles(
            where=where,
            on_batch=on_api_batch,
        )

        # Transform profiles as they stream through
        def transform_iterator() -> Iterator[dict[str, Any]]:
            for profile in profiles_iter:
                yield _transform_profile(profile)

        # Construct metadata
        fetched_at = datetime.now(UTC)
        metadata = TableMetadata(
            type="profiles",
            fetched_at=fetched_at,
            from_date=None,
            to_date=None,
            filter_events=None,
            filter_where=where,
        )

        # Store in database (handles TableExistsError, transactions, etc.)
        row_count = self._storage.create_profiles_table(
            name=name,
            data=transform_iterator(),
            metadata=metadata,
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
