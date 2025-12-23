"""Live Query Service for Mixpanel analytics queries.

Provides methods to execute live queries against the Mixpanel Query API
and transform responses into typed result objects with DataFrame support.

Unlike DiscoveryService, this service does not cache results because
analytics data changes frequently and queries should return fresh data.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from mixpanel_data.types import (
    CohortInfo,
    FunnelResult,
    FunnelStep,
    JQLResult,
    RetentionResult,
    SegmentationResult,
)

if TYPE_CHECKING:
    from mixpanel_data._internal.api_client import MixpanelAPIClient


def _transform_funnel(
    raw: dict[str, Any],
    funnel_id: int,
    from_date: str,
    to_date: str,
) -> FunnelResult:
    """Transform raw funnel API response into FunnelResult.

    Aggregates step counts across all dates and recalculates conversion rates.

    Args:
        raw: Raw API response dictionary.
        funnel_id: Funnel identifier.
        from_date: Query start date.
        to_date: Query end date.

    Returns:
        Typed FunnelResult with aggregated steps and conversion rates.
    """
    data = raw.get("data", {})

    # Aggregate steps across all dates
    aggregated_counts: dict[
        int, tuple[str, int]
    ] = {}  # step_idx -> (event, total_count)

    for date_data in data.values():
        steps_data = date_data.get("steps", [])
        for idx, step in enumerate(steps_data):
            event = step.get("event", step.get("goal", f"Step {idx + 1}"))
            count = step.get("count", 0)
            if idx in aggregated_counts:
                _, existing = aggregated_counts[idx]
                aggregated_counts[idx] = (event, existing + count)
            else:
                aggregated_counts[idx] = (event, count)

    # Build FunnelStep list with recalculated conversion rates
    steps: list[FunnelStep] = []
    prev_count = 0
    for idx in sorted(aggregated_counts.keys()):
        event, count = aggregated_counts[idx]
        conv_rate = 1.0 if idx == 0 else (count / prev_count if prev_count > 0 else 0.0)
        steps.append(FunnelStep(event=event, count=count, conversion_rate=conv_rate))
        prev_count = count

    # Overall conversion rate: last step / first step
    if steps:
        overall_rate = steps[-1].count / steps[0].count if steps[0].count > 0 else 0.0
    else:
        overall_rate = 0.0

    return FunnelResult(
        funnel_id=funnel_id,
        funnel_name="",  # Not available from API
        from_date=from_date,
        to_date=to_date,
        conversion_rate=overall_rate,
        steps=steps,
    )


def _transform_retention(
    raw: dict[str, Any],
    born_event: str,
    return_event: str,
    from_date: str,
    to_date: str,
    unit: str,
) -> RetentionResult:
    """Transform raw retention API response into RetentionResult.

    Calculates retention percentages from raw counts for each cohort.

    Args:
        raw: Raw API response dictionary.
        born_event: Event that defines cohort membership.
        return_event: Event that defines return.
        from_date: Query start date.
        to_date: Query end date.
        unit: Retention period unit.

    Returns:
        Typed RetentionResult with cohorts sorted by date.
    """
    cohorts: list[CohortInfo] = []

    # Sort by date for consistent ordering
    for date in sorted(raw.keys()):
        cohort_data = raw[date]
        size = cohort_data.get("first", 0)
        counts = cohort_data.get("counts", [])

        # Calculate retention percentages
        retention = [count / size if size > 0 else 0.0 for count in counts]

        cohorts.append(
            CohortInfo(
                date=date,
                size=size,
                retention=retention,
            )
        )

    return RetentionResult(
        born_event=born_event,
        return_event=return_event,
        from_date=from_date,
        to_date=to_date,
        unit=unit,  # type: ignore[arg-type]
        cohorts=cohorts,
    )


def _transform_segmentation(
    raw: dict[str, Any],
    event: str,
    from_date: str,
    to_date: str,
    unit: str,
    on: str | None,
) -> SegmentationResult:
    """Transform raw segmentation API response into SegmentationResult.

    Args:
        raw: Raw API response dictionary.
        event: Event name that was queried.
        from_date: Query start date.
        to_date: Query end date.
        unit: Time aggregation unit.
        on: Property used for segmentation (or None).

    Returns:
        Typed SegmentationResult with calculated total.
    """
    data = raw.get("data", {})
    values = data.get("values", {})

    # Calculate total by summing all counts
    total = sum(
        count for segment_values in values.values() for count in segment_values.values()
    )

    return SegmentationResult(
        event=event,
        from_date=from_date,
        to_date=to_date,
        unit=unit,  # type: ignore[arg-type]
        segment_property=on,
        total=total,
        series=values,
    )


class LiveQueryService:
    """Service for executing live queries against the Mixpanel Query API.

    Transforms raw API responses into typed result objects with DataFrame support.
    Unlike DiscoveryService, results are not cached because analytics data
    changes frequently and queries should return fresh data.

    Example:
        >>> from mixpanel_data._internal.api_client import MixpanelAPIClient
        >>> from mixpanel_data._internal.services.live_query import LiveQueryService
        >>>
        >>> client = MixpanelAPIClient(credentials)
        >>> with client:
        ...     live_query = LiveQueryService(client)
        ...     result = live_query.segmentation("Sign Up", "2024-01-01", "2024-01-31")
        ...     print(result.total)
    """

    def __init__(self, api_client: MixpanelAPIClient) -> None:
        """Initialize live query service.

        Args:
            api_client: Authenticated Mixpanel API client.
        """
        self._api_client = api_client

    def segmentation(
        self,
        event: str,
        from_date: str,
        to_date: str,
        *,
        on: str | None = None,
        unit: str = "day",
        where: str | None = None,
    ) -> SegmentationResult:
        """Run a segmentation query.

        Executes a segmentation query against the Mixpanel API and returns
        a typed result with time-series data and optional property segmentation.

        Args:
            event: Event name to segment.
            from_date: Start date (YYYY-MM-DD).
            to_date: End date (YYYY-MM-DD).
            on: Optional property to segment by (e.g., 'properties["country"]').
            unit: Time unit for aggregation (day, week, month). Default: "day".
            where: Optional filter expression.

        Returns:
            SegmentationResult with time-series data and calculated total.

        Raises:
            AuthenticationError: Invalid credentials.
            QueryError: Invalid query parameters.
            RateLimitError: Rate limit exceeded.

        Example:
            >>> result = live_query.segmentation(
            ...     event="Sign Up",
            ...     from_date="2024-01-01",
            ...     to_date="2024-01-31",
            ...     on='properties["country"]',
            ... )
            >>> print(f"Total: {result.total}")
            >>> print(result.df.head())
        """
        raw = self._api_client.segmentation(
            event=event,
            from_date=from_date,
            to_date=to_date,
            on=on,
            unit=unit,
            where=where,
        )
        return _transform_segmentation(raw, event, from_date, to_date, unit, on)

    def funnel(
        self,
        funnel_id: int,
        from_date: str,
        to_date: str,
        *,
        unit: str | None = None,
        on: str | None = None,
    ) -> FunnelResult:
        """Run a funnel analysis query.

        Executes a funnel query against the Mixpanel API and returns
        a typed result with step-by-step conversion data aggregated
        across the date range.

        Args:
            funnel_id: Funnel identifier.
            from_date: Start date (YYYY-MM-DD).
            to_date: End date (YYYY-MM-DD).
            unit: Optional time unit for grouping.
            on: Optional property to segment by.

        Returns:
            FunnelResult with aggregated steps and conversion rates.

        Raises:
            AuthenticationError: Invalid credentials.
            QueryError: Invalid funnel ID or parameters.
            RateLimitError: Rate limit exceeded.

        Example:
            >>> result = live_query.funnel(
            ...     funnel_id=12345,
            ...     from_date="2024-01-01",
            ...     to_date="2024-01-31",
            ... )
            >>> print(f"Overall conversion: {result.conversion_rate:.1%}")
            >>> for step in result.steps:
            ...     print(f"{step.event}: {step.count}")
        """
        raw = self._api_client.funnel(
            funnel_id=funnel_id,
            from_date=from_date,
            to_date=to_date,
            unit=unit,
            on=on,
        )
        return _transform_funnel(raw, funnel_id, from_date, to_date)

    def retention(
        self,
        born_event: str,
        return_event: str,
        from_date: str,
        to_date: str,
        *,
        born_where: str | None = None,
        return_where: str | None = None,
        interval: int = 1,
        interval_count: int = 10,
        unit: str = "day",
    ) -> RetentionResult:
        """Run a retention analysis query.

        Executes a retention query against the Mixpanel API and returns
        a typed result with cohort retention percentages.

        Args:
            born_event: Event that defines cohort membership.
            return_event: Event that defines return.
            from_date: Start date (YYYY-MM-DD).
            to_date: End date (YYYY-MM-DD).
            born_where: Optional filter for born event.
            return_where: Optional filter for return event.
            interval: Retention interval size. Default: 1.
            interval_count: Number of intervals to track. Default: 10.
            unit: Interval unit (day, week, month). Default: "day".

        Returns:
            RetentionResult with cohorts sorted by date.

        Raises:
            AuthenticationError: Invalid credentials.
            QueryError: Invalid parameters.
            RateLimitError: Rate limit exceeded.

        Example:
            >>> result = live_query.retention(
            ...     born_event="Sign Up",
            ...     return_event="Purchase",
            ...     from_date="2024-01-01",
            ...     to_date="2024-01-31",
            ... )
            >>> for cohort in result.cohorts:
            ...     print(f"{cohort.date}: {cohort.retention}")
        """
        raw = self._api_client.retention(
            born_event=born_event,
            event=return_event,
            from_date=from_date,
            to_date=to_date,
            born_where=born_where,
            where=return_where,
            interval=interval,
            interval_count=interval_count,
            unit=unit,
        )
        return _transform_retention(
            raw, born_event, return_event, from_date, to_date, unit
        )

    def jql(
        self,
        script: str,
        params: dict[str, Any] | None = None,
    ) -> JQLResult:
        """Execute a JQL (JavaScript Query Language) script.

        Executes a custom JQL script against the Mixpanel API and returns
        a typed result with the raw script output.

        Args:
            script: JQL script code.
            params: Optional parameters to pass to the script.

        Returns:
            JQLResult with raw data from script execution.

        Raises:
            AuthenticationError: Invalid credentials.
            QueryError: Script execution error.
            RateLimitError: Rate limit exceeded.

        Example:
            >>> result = live_query.jql(
            ...     script='''
            ...     function main() {
            ...       return Events({from_date: params.from, to_date: params.to})
            ...         .groupBy(["name"], mixpanel.reducer.count())
            ...     }
            ...     ''',
            ...     params={"from": "2024-01-01", "to": "2024-01-31"},
            ... )
            >>> print(result.raw)
            >>> print(result.df)
        """
        raw = self._api_client.jql(script=script, params=params)
        return JQLResult(_raw=raw)
