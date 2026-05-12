"""API Client Contract - Type stubs for MixpanelAPIClient.

This file defines the public interface that MixpanelAPIClient must implement.
It serves as a contract between the client and its consumers (services).

DO NOT import this file in production code. It is for documentation and
type checking reference only.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from typing import Any, Protocol

from mixpanel_data._internal.config import Credentials


class MixpanelAPIClientProtocol(Protocol):
    """Protocol defining the MixpanelAPIClient interface.

    All methods must be implemented by the concrete MixpanelAPIClient class.
    """

    def __init__(
        self,
        credentials: Credentials,
        *,
        timeout: float = 120.0,
        export_timeout: float = 600.0,
        max_retries: int = 3,
    ) -> None:
        """Initialize the API client.

        Args:
            credentials: Immutable authentication credentials.
            timeout: Request timeout in seconds for regular requests.
            export_timeout: Request timeout for export operations.
            max_retries: Maximum retry attempts for rate-limited requests.
        """
        ...

    # =========================================================================
    # Lifecycle
    # =========================================================================

    def close(self) -> None:
        """Close the HTTP client and release resources."""
        ...

    def __enter__(self) -> MixpanelAPIClientProtocol:
        """Enter context manager."""
        ...

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: Any,
    ) -> None:
        """Exit context manager, closing client."""
        ...

    # =========================================================================
    # Export API - Streaming
    # =========================================================================

    def export_events(
        self,
        from_date: str,
        to_date: str,
        *,
        events: list[str] | None = None,
        where: str | None = None,
        on_batch: Callable[[int], None] | None = None,
    ) -> Iterator[dict[str, Any]]:
        """Stream events from the Export API.

        Args:
            from_date: Start date (YYYY-MM-DD, inclusive).
            to_date: End date (YYYY-MM-DD, inclusive).
            events: Optional list of event names to filter.
            where: Optional filter expression.
            on_batch: Optional callback invoked with count after each batch.

        Yields:
            Event dictionaries with 'event' and 'properties' keys.

        Raises:
            AuthenticationError: Invalid credentials.
            RateLimitError: Rate limit exceeded after max retries.
            QueryError: Invalid parameters.
        """
        ...

    def export_profiles(
        self,
        *,
        where: str | None = None,
        on_batch: Callable[[int], None] | None = None,
    ) -> Iterator[dict[str, Any]]:
        """Stream profiles from the Engage API.

        Args:
            where: Optional filter expression.
            on_batch: Optional callback invoked with count after each page.

        Yields:
            Profile dictionaries with '$distinct_id' and '$properties' keys.

        Raises:
            AuthenticationError: Invalid credentials.
            RateLimitError: Rate limit exceeded after max retries.
        """
        ...

    # =========================================================================
    # Discovery API
    # =========================================================================

    def get_events(self) -> list[str]:
        """List all event names in the project.

        Returns:
            List of event name strings.

        Raises:
            AuthenticationError: Invalid credentials.
        """
        ...

    def get_event_properties(self, event: str) -> list[str]:
        """List properties for a specific event.

        Args:
            event: Event name.

        Returns:
            List of property name strings.

        Raises:
            AuthenticationError: Invalid credentials.
            QueryError: Invalid event name.
        """
        ...

    def get_property_values(
        self,
        property_name: str,
        *,
        event: str | None = None,
        limit: int = 255,
    ) -> list[str]:
        """List sample values for a property.

        Args:
            property_name: Property name.
            event: Optional event name to scope the property.
            limit: Maximum number of values to return.

        Returns:
            List of property value strings.

        Raises:
            AuthenticationError: Invalid credentials.
        """
        ...

    # =========================================================================
    # Query API - Raw Responses
    # =========================================================================

    def segmentation(
        self,
        event: str,
        from_date: str,
        to_date: str,
        *,
        on: str | None = None,
        unit: str = "day",
        type: str = "general",
        where: str | None = None,
    ) -> dict[str, Any]:
        """Run a segmentation query.

        Args:
            event: Event name to segment.
            from_date: Start date (YYYY-MM-DD).
            to_date: End date (YYYY-MM-DD).
            on: Optional property to segment by.
            unit: Time unit (minute, hour, day, week, month).
            type: Aggregation type (general, unique, average).
            where: Optional filter expression.

        Returns:
            Raw API response dictionary.

        Raises:
            AuthenticationError: Invalid credentials.
            QueryError: Invalid query parameters.
            RateLimitError: Rate limit exceeded.
        """
        ...

    def funnel(
        self,
        funnel_id: int,
        from_date: str,
        to_date: str,
        *,
        unit: str | None = None,
        on: str | None = None,
        where: str | None = None,
        length: int | None = None,
        length_unit: str | None = None,
    ) -> dict[str, Any]:
        """Run a funnel analysis query.

        Args:
            funnel_id: Funnel identifier.
            from_date: Start date (YYYY-MM-DD).
            to_date: End date (YYYY-MM-DD).
            unit: Time unit for grouping.
            on: Optional property to segment by.
            where: Optional filter expression.
            length: Conversion window length.
            length_unit: Conversion window unit.

        Returns:
            Raw API response dictionary.

        Raises:
            AuthenticationError: Invalid credentials.
            QueryError: Invalid funnel ID or parameters.
            RateLimitError: Rate limit exceeded.
        """
        ...

    def retention(
        self,
        born_event: str,
        event: str,
        from_date: str,
        to_date: str,
        *,
        retention_type: str = "birth",
        born_where: str | None = None,
        where: str | None = None,
        interval: int = 1,
        interval_count: int = 8,
        unit: str = "day",
    ) -> dict[str, Any]:
        """Run a retention analysis query.

        Args:
            born_event: Event that defines cohort membership.
            event: Event that defines return.
            from_date: Start date (YYYY-MM-DD).
            to_date: End date (YYYY-MM-DD).
            retention_type: Retention type (birth, compounded).
            born_where: Optional filter for born event.
            where: Optional filter for return event.
            interval: Retention interval size.
            interval_count: Number of intervals to track.
            unit: Interval unit (day, week, month).

        Returns:
            Raw API response dictionary.

        Raises:
            AuthenticationError: Invalid credentials.
            QueryError: Invalid parameters.
            RateLimitError: Rate limit exceeded.
        """
        ...

    def jql(
        self,
        script: str,
        *,
        params: dict[str, Any] | None = None,
    ) -> list[Any]:
        """Execute a JQL (JavaScript Query Language) script.

        Args:
            script: JQL script code.
            params: Optional parameters to pass to the script.

        Returns:
            List of results from script execution.

        Raises:
            AuthenticationError: Invalid credentials.
            QueryError: Script execution error.
            RateLimitError: Rate limit exceeded.
        """
        ...
