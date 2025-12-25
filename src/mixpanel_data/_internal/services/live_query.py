"""Live Query Service for Mixpanel analytics queries.

Provides methods to execute live queries against the Mixpanel Query API
and transform responses into typed result objects with DataFrame support.

Unlike DiscoveryService, this service does not cache results because
analytics data changes frequently and queries should return fresh data.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, Literal

from mixpanel_data._literal_types import CountType, HourDayUnit, TimeUnit
from mixpanel_data.types import (
    ActivityFeedResult,
    CohortInfo,
    EventCountsResult,
    FrequencyResult,
    FunnelResult,
    FunnelStep,
    InsightsResult,
    JQLResult,
    NumericAverageResult,
    NumericBucketResult,
    NumericSumResult,
    PropertyCountsResult,
    RetentionResult,
    SegmentationResult,
    UserEvent,
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

    Conversion rate calculation:
        - Step 0: Always 1.0 (100% of users start the funnel)
        - Step N: count[N] / count[N-1] (percentage who continued from previous step)
        - Overall: last_step_count / first_step_count

    Edge cases:
        - Empty steps: Returns 0.0 conversion rate
        - Previous step count = 0: Returns 0.0 to avoid division by zero

    Args:
        raw: Raw API response dictionary with data[date][steps] structure.
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
    unit: TimeUnit,
) -> RetentionResult:
    """Transform raw retention API response into RetentionResult.

    Calculates retention percentages from raw counts for each cohort.

    Retention calculation:
        retention[i] = counts[i] / cohort_size
        Where counts[i] is users who returned in period i after their birth date.

    Edge cases:
        - Cohort size = 0: Returns 0.0 for all retention periods (no division by zero)
        - Empty counts: Returns empty retention list

    API response structure:
        {date: {"first": cohort_size, "counts": [period_0_count, period_1_count, ...]}}

    Args:
        raw: Raw API response dictionary keyed by cohort date.
        born_event: Event that defines cohort membership.
        return_event: Event that defines return.
        from_date: Query start date.
        to_date: Query end date.
        unit: Retention period unit.

    Returns:
        Typed RetentionResult with cohorts sorted by date (ascending).
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
        unit=unit,
        cohorts=cohorts,
    )


def _transform_segmentation(
    raw: dict[str, Any],
    event: str,
    from_date: str,
    to_date: str,
    unit: TimeUnit,
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
        unit=unit,
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
        ```python
        from mixpanel_data._internal.api_client import MixpanelAPIClient
        from mixpanel_data._internal.services.live_query import LiveQueryService

        client = MixpanelAPIClient(credentials)
        with client:
            live_query = LiveQueryService(client)
            result = live_query.segmentation("Sign Up", "2024-01-01", "2024-01-31")
            print(result.total)
        ```
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
        unit: TimeUnit = "day",
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
            ```python
            result = live_query.segmentation(
                event="Sign Up",
                from_date="2024-01-01",
                to_date="2024-01-31",
                on='properties["country"]',
            )
            print(f"Total: {result.total}")
            print(result.df.head())
            ```
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
            ```python
            result = live_query.funnel(
                funnel_id=12345,
                from_date="2024-01-01",
                to_date="2024-01-31",
            )
            print(f"Overall conversion: {result.conversion_rate:.1%}")
            for step in result.steps:
                print(f"{step.event}: {step.count}")
            ```
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
        unit: TimeUnit = "day",
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
            ```python
            result = live_query.retention(
                born_event="Sign Up",
                return_event="Purchase",
                from_date="2024-01-01",
                to_date="2024-01-31",
            )
            for cohort in result.cohorts:
                print(f"{cohort.date}: {cohort.retention}")
            ```
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
            ```python
            result = live_query.jql(
                script='''
                function main() {
                  return Events({from_date: params.from, to_date: params.to})
                    .groupBy(["name"], mixpanel.reducer.count())
                }
                ''',
                params={"from": "2024-01-01", "to": "2024-01-31"},
            )
            print(result.raw)
            print(result.df)
            ```
        """
        raw = self._api_client.jql(script=script, params=params)
        return JQLResult(_raw=raw)

    def event_counts(
        self,
        events: list[str],
        from_date: str,
        to_date: str,
        *,
        type: Literal["general", "unique", "average"] = "general",
        unit: Literal["day", "week", "month"] = "day",
    ) -> EventCountsResult:
        """Query aggregate counts for multiple events over time.

        Executes a multi-event query against the Mixpanel API and returns
        a typed result with time-series data for each event.

        Args:
            events: List of event names to query.
            from_date: Start date (YYYY-MM-DD).
            to_date: End date (YYYY-MM-DD).
            type: Counting method - "general", "unique", or "average".
            unit: Time unit - "day", "week", or "month".

        Returns:
            EventCountsResult with time-series data and lazy DataFrame.

        Raises:
            AuthenticationError: Invalid credentials.
            QueryError: Invalid parameters.
            RateLimitError: Rate limit exceeded.

        Example:
            ```python
            result = live_query.event_counts(
                events=["Sign Up", "Purchase"],
                from_date="2024-01-01",
                to_date="2024-01-31",
            )
            print(result.series["Sign Up"])
            print(result.df.head())
            ```
        """
        raw = self._api_client.event_counts(
            events=events,
            from_date=from_date,
            to_date=to_date,
            type=type,
            unit=unit,
        )
        return EventCountsResult(
            events=events,
            from_date=from_date,
            to_date=to_date,
            unit=unit,
            type=type,
            series=raw.get("data", {}).get("values", {}),
        )

    def property_counts(
        self,
        event: str,
        property_name: str,
        from_date: str,
        to_date: str,
        *,
        type: Literal["general", "unique", "average"] = "general",
        unit: Literal["day", "week", "month"] = "day",
        values: list[str] | None = None,
        limit: int | None = None,
    ) -> PropertyCountsResult:
        """Query aggregate counts by property values over time.

        Executes a property breakdown query against the Mixpanel API and returns
        a typed result with time-series data for each property value.

        Args:
            event: Event name to query.
            property_name: Property to segment by.
            from_date: Start date (YYYY-MM-DD).
            to_date: End date (YYYY-MM-DD).
            type: Counting method - "general", "unique", or "average".
            unit: Time unit - "day", "week", or "month".
            values: Optional list of specific property values to include.
            limit: Maximum property values to return (default: 255).

        Returns:
            PropertyCountsResult with time-series data and lazy DataFrame.

        Raises:
            AuthenticationError: Invalid credentials.
            QueryError: Invalid parameters.
            RateLimitError: Rate limit exceeded.

        Example:
            ```python
            result = live_query.property_counts(
                event="Purchase",
                property_name="country",
                from_date="2024-01-01",
                to_date="2024-01-31",
            )
            print(result.series["US"])
            print(result.df.head())
            ```
        """
        raw = self._api_client.property_counts(
            event=event,
            property_name=property_name,
            from_date=from_date,
            to_date=to_date,
            type=type,
            unit=unit,
            values=values,
            limit=limit,
        )
        return PropertyCountsResult(
            event=event,
            property_name=property_name,
            from_date=from_date,
            to_date=to_date,
            unit=unit,
            type=type,
            series=raw.get("data", {}).get("values", {}),
        )

    # =========================================================================
    # Phase 008: Query Service Enhancements
    # =========================================================================

    def activity_feed(
        self,
        distinct_ids: list[str],
        *,
        from_date: str | None = None,
        to_date: str | None = None,
    ) -> ActivityFeedResult:
        """Query activity feed for specific users.

        Retrieves chronological event history for one or more users,
        returning a typed result with lazy DataFrame conversion.

        Args:
            distinct_ids: User identifiers to query.
            from_date: Optional start date (YYYY-MM-DD).
            to_date: Optional end date (YYYY-MM-DD).

        Returns:
            ActivityFeedResult with user events and lazy DataFrame.

        Raises:
            AuthenticationError: Invalid credentials.
            QueryError: Invalid parameters.
            RateLimitError: Rate limit exceeded.

        Example:
            ```python
            result = live_query.activity_feed(
                distinct_ids=["user_123", "user_456"],
                from_date="2024-01-01",
                to_date="2024-01-31",
            )
            print(f"Found {len(result.events)} events")
            print(result.df.head())
            ```
        """
        raw = self._api_client.activity_feed(
            distinct_ids=distinct_ids,
            from_date=from_date,
            to_date=to_date,
        )
        return _transform_activity_feed(raw, distinct_ids, from_date, to_date)

    def insights(
        self,
        bookmark_id: int,
    ) -> InsightsResult:
        """Query a saved Insights report.

        Retrieves data from a pre-configured Insights report by its
        bookmark ID, returning a typed result with lazy DataFrame conversion.

        Args:
            bookmark_id: Saved report identifier (from Mixpanel URL).

        Returns:
            InsightsResult with time-series data and metadata.

        Raises:
            AuthenticationError: Invalid credentials.
            QueryError: Invalid bookmark_id or report not found.
            RateLimitError: Rate limit exceeded.

        Example:
            ```python
            result = live_query.insights(bookmark_id=12345678)
            print(f"Report computed at: {result.computed_at}")
            print(result.df.pivot(index='date', columns='event', values='count'))
            ```
        """
        raw = self._api_client.insights(bookmark_id=bookmark_id)
        return _transform_insights(raw, bookmark_id)

    def frequency(
        self,
        from_date: str,
        to_date: str,
        *,
        unit: TimeUnit = "day",
        addiction_unit: HourDayUnit = "hour",
        event: str | None = None,
        where: str | None = None,
    ) -> FrequencyResult:
        """Query event frequency distribution (addiction analysis).

        Analyzes how frequently users perform events, returning arrays
        showing the number of users active in N time periods.

        Args:
            from_date: Start date (YYYY-MM-DD).
            to_date: End date (YYYY-MM-DD).
            unit: Overall time period. Default: "day".
            addiction_unit: Measurement granularity. Default: "hour".
            event: Optional event name to filter (None = all events).
            where: Optional filter expression.

        Returns:
            FrequencyResult with frequency arrays and lazy DataFrame.

        Raises:
            AuthenticationError: Invalid credentials.
            QueryError: Invalid parameters.
            RateLimitError: Rate limit exceeded.

        Example:
            ```python
            result = live_query.frequency(
                from_date="2024-01-01",
                to_date="2024-01-07",
                event="App Open",
            )
            # counts[0] = users active 1+ hours, counts[1] = 2+ hours, etc.
            for date, counts in result.data.items():
                print(f"{date}: {counts[:3]}")
            ```
        """
        raw = self._api_client.frequency(
            from_date=from_date,
            to_date=to_date,
            unit=unit,
            addiction_unit=addiction_unit,
            event=event,
            where=where,
        )
        return _transform_frequency(
            raw, event, from_date, to_date, unit, addiction_unit
        )

    def segmentation_numeric(
        self,
        event: str,
        from_date: str,
        to_date: str,
        on: str,
        *,
        unit: HourDayUnit = "day",
        where: str | None = None,
        type: CountType = "general",
    ) -> NumericBucketResult:
        """Query events bucketed by numeric property ranges.

        Segments events into automatically determined numeric ranges,
        returning time-series data for each bucket.

        Args:
            event: Event name to analyze.
            from_date: Start date (YYYY-MM-DD).
            to_date: End date (YYYY-MM-DD).
            on: Numeric property expression to bucket.
            unit: Time aggregation unit. Default: "day".
            where: Optional filter expression.
            type: Counting method. Default: "general".

        Returns:
            NumericBucketResult with bucketed time-series and lazy DataFrame.

        Raises:
            AuthenticationError: Invalid credentials.
            QueryError: Invalid parameters or non-numeric property.
            RateLimitError: Rate limit exceeded.

        Example:
            ```python
            result = live_query.segmentation_numeric(
                event="Purchase",
                from_date="2024-01-01",
                to_date="2024-01-31",
                on='properties["amount"]',
            )
            for bucket, series in result.series.items():
                print(f"{bucket}: {sum(series.values())} events")
            ```
        """
        raw = self._api_client.segmentation_numeric(
            event=event,
            from_date=from_date,
            to_date=to_date,
            on=on,
            unit=unit,
            where=where,
            type=type,
        )
        return _transform_numeric_bucket(raw, event, from_date, to_date, on, unit)

    def segmentation_sum(
        self,
        event: str,
        from_date: str,
        to_date: str,
        on: str,
        *,
        unit: HourDayUnit = "day",
        where: str | None = None,
    ) -> NumericSumResult:
        """Query sum of numeric property values.

        Calculates daily or hourly sum totals for a numeric property,
        returning time-series data with lazy DataFrame conversion.

        Args:
            event: Event name to analyze.
            from_date: Start date (YYYY-MM-DD).
            to_date: End date (YYYY-MM-DD).
            on: Numeric property expression to sum.
            unit: Time aggregation unit. Default: "day".
            where: Optional filter expression.

        Returns:
            NumericSumResult with sum values and lazy DataFrame.

        Raises:
            AuthenticationError: Invalid credentials.
            QueryError: Invalid parameters or non-numeric property.
            RateLimitError: Rate limit exceeded.

        Example:
            ```python
            result = live_query.segmentation_sum(
                event="Purchase",
                from_date="2024-01-01",
                to_date="2024-01-31",
                on='properties["amount"]',
            )
            total = sum(result.results.values())
            print(f"Total revenue: ${total:,.2f}")
            ```
        """
        raw = self._api_client.segmentation_sum(
            event=event,
            from_date=from_date,
            to_date=to_date,
            on=on,
            unit=unit,
            where=where,
        )
        return _transform_numeric_sum(raw, event, from_date, to_date, on, unit)

    def segmentation_average(
        self,
        event: str,
        from_date: str,
        to_date: str,
        on: str,
        *,
        unit: HourDayUnit = "day",
        where: str | None = None,
    ) -> NumericAverageResult:
        """Query average of numeric property values.

        Calculates daily or hourly average values for a numeric property,
        returning time-series data with lazy DataFrame conversion.

        Args:
            event: Event name to analyze.
            from_date: Start date (YYYY-MM-DD).
            to_date: End date (YYYY-MM-DD).
            on: Numeric property expression to average.
            unit: Time aggregation unit. Default: "day".
            where: Optional filter expression.

        Returns:
            NumericAverageResult with average values and lazy DataFrame.

        Raises:
            AuthenticationError: Invalid credentials.
            QueryError: Invalid parameters or non-numeric property.
            RateLimitError: Rate limit exceeded.

        Example:
            ```python
            result = live_query.segmentation_average(
                event="Purchase",
                from_date="2024-01-01",
                to_date="2024-01-31",
                on='properties["amount"]',
            )
            avg = sum(result.results.values()) / len(result.results)
            print(f"Average order value: ${avg:.2f}")
            ```
        """
        raw = self._api_client.segmentation_average(
            event=event,
            from_date=from_date,
            to_date=to_date,
            on=on,
            unit=unit,
            where=where,
        )
        return _transform_numeric_average(raw, event, from_date, to_date, on, unit)


# =============================================================================
# Phase 008: Transformation Functions
# =============================================================================


def _transform_activity_feed(
    raw: dict[str, Any],
    distinct_ids: list[str],
    from_date: str | None,
    to_date: str | None,
) -> ActivityFeedResult:
    """Transform raw activity feed API response into ActivityFeedResult.

    Converts Unix timestamps to datetime objects and builds UserEvent list.

    Args:
        raw: Raw API response dictionary.
        distinct_ids: Queried user identifiers.
        from_date: Query start date.
        to_date: Query end date.

    Returns:
        Typed ActivityFeedResult with chronological events.
    """
    results = raw.get("results", {})
    raw_events = results.get("events", [])

    events: list[UserEvent] = []
    for event_data in raw_events:
        event_name = event_data.get("event", "")
        props = event_data.get("properties", {})

        # Convert Unix timestamp to datetime
        # Mixpanel events should always have a time field (server-side if not client-side).
        # Missing timestamps indicate API format changes or data corruption.
        timestamp = props.get("time")
        if timestamp is None:
            raise ValueError(
                f"Event missing required 'time' field: {event_data.get('event', 'unknown')}"
            )
        event_time = datetime.fromtimestamp(timestamp, tz=UTC)

        events.append(
            UserEvent(
                event=event_name,
                time=event_time,
                properties=props,
            )
        )

    return ActivityFeedResult(
        distinct_ids=distinct_ids,
        from_date=from_date,
        to_date=to_date,
        events=events,
    )


def _transform_insights(
    raw: dict[str, Any],
    bookmark_id: int,
) -> InsightsResult:
    """Transform raw insights API response into InsightsResult.

    Extracts date range and time-series data from the response.

    Args:
        raw: Raw API response dictionary.
        bookmark_id: Saved report identifier.

    Returns:
        Typed InsightsResult with metadata and time-series.
    """
    computed_at = raw.get("computed_at", "")
    date_range = raw.get("date_range", {})
    from_date = date_range.get("from_date", "")
    to_date = date_range.get("to_date", "")
    headers = raw.get("headers", [])
    series = raw.get("series", {})

    return InsightsResult(
        bookmark_id=bookmark_id,
        computed_at=computed_at,
        from_date=from_date,
        to_date=to_date,
        headers=headers,
        series=series,
    )


def _transform_frequency(
    raw: dict[str, Any],
    event: str | None,
    from_date: str,
    to_date: str,
    unit: TimeUnit,
    addiction_unit: HourDayUnit,
) -> FrequencyResult:
    """Transform raw frequency API response into FrequencyResult.

    Args:
        raw: Raw API response dictionary.
        event: Filtered event name.
        from_date: Query start date.
        to_date: Query end date.
        unit: Overall time period.
        addiction_unit: Measurement granularity.

    Returns:
        Typed FrequencyResult with frequency arrays.
    """
    data = raw.get("data", {})

    return FrequencyResult(
        event=event,
        from_date=from_date,
        to_date=to_date,
        unit=unit,
        addiction_unit=addiction_unit,
        data=data,
    )


def _transform_numeric_bucket(
    raw: dict[str, Any],
    event: str,
    from_date: str,
    to_date: str,
    on: str,
    unit: HourDayUnit,
) -> NumericBucketResult:
    """Transform raw numeric segmentation API response into NumericBucketResult.

    Args:
        raw: Raw API response dictionary.
        event: Event name queried.
        from_date: Query start date.
        to_date: Query end date.
        on: Property expression used for bucketing.
        unit: Time aggregation unit.

    Returns:
        Typed NumericBucketResult with bucketed time-series.
    """
    data = raw.get("data", {})
    values = data.get("values", {})

    return NumericBucketResult(
        event=event,
        from_date=from_date,
        to_date=to_date,
        property_expr=on,
        unit=unit,
        series=values,
    )


def _transform_numeric_sum(
    raw: dict[str, Any],
    event: str,
    from_date: str,
    to_date: str,
    on: str,
    unit: HourDayUnit,
) -> NumericSumResult:
    """Transform raw sum API response into NumericSumResult.

    Args:
        raw: Raw API response dictionary.
        event: Event name queried.
        from_date: Query start date.
        to_date: Query end date.
        on: Property expression summed.
        unit: Time aggregation unit.

    Returns:
        Typed NumericSumResult with sum values.
    """
    results = raw.get("results", {})
    computed_at = raw.get("computed_at")

    return NumericSumResult(
        event=event,
        from_date=from_date,
        to_date=to_date,
        property_expr=on,
        unit=unit,
        results=results,
        computed_at=computed_at,
    )


def _transform_numeric_average(
    raw: dict[str, Any],
    event: str,
    from_date: str,
    to_date: str,
    on: str,
    unit: HourDayUnit,
) -> NumericAverageResult:
    """Transform raw average API response into NumericAverageResult.

    Args:
        raw: Raw API response dictionary.
        event: Event name queried.
        from_date: Query start date.
        to_date: Query end date.
        on: Property expression averaged.
        unit: Time aggregation unit.

    Returns:
        Typed NumericAverageResult with average values.
    """
    results = raw.get("results", {})

    return NumericAverageResult(
        event=event,
        from_date=from_date,
        to_date=to_date,
        property_expr=on,
        unit=unit,
        results=results,
    )
