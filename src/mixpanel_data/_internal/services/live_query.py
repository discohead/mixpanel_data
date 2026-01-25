"""Live Query Service for Mixpanel analytics queries.

Provides methods to execute live queries against the Mixpanel Query API
and transform responses into typed result objects with DataFrame support.

Unlike DiscoveryService, this service does not cache results because
analytics data changes frequently and queries should return fresh data.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Literal

from mixpanel_data._internal.expressions import normalize_on_expression
from mixpanel_data._literal_types import CountType, HourDayUnit, TimeUnit
from mixpanel_data.types import (
    ActivityFeedResult,
    CohortInfo,
    DailyCount,
    DailyCountsResult,
    EngagementBucket,
    EngagementDistributionResult,
    EventCountsResult,
    FlowsResult,
    FrequencyResult,
    FunnelResult,
    FunnelStep,
    JQLResult,
    NumericAverageResult,
    NumericBucketResult,
    NumericPropertySummaryResult,
    NumericSumResult,
    PropertyCountsResult,
    PropertyCoverage,
    PropertyCoverageResult,
    PropertyDistributionResult,
    PropertyValueCount,
    RetentionResult,
    SavedReportResult,
    SegmentationResult,
    UserEvent,
)

if TYPE_CHECKING:
    from mixpanel_data._internal.api_client import MixpanelAPIClient


def _extract_steps_from_date_data(date_data: dict[str, Any]) -> list[dict[str, Any]]:
    """Extract steps from date data, handling both regular and segmented formats.

    API response formats:
        - Without 'on' param: {"steps": [step1, step2, ...]}
        - With 'on' param: {"$overall": [step1, ...], "Chrome": [...], ...}

    For segmented responses, uses "$overall" which contains aggregate data.

    Args:
        date_data: Single date's data from the funnel response.

    Returns:
        List of step dictionaries.
    """
    # Non-segmented format: data has "steps" key
    if "steps" in date_data:
        steps = date_data.get("steps", [])
        return steps if isinstance(steps, list) else []

    # Segmented format: use $overall for aggregate data
    if "$overall" in date_data:
        overall = date_data.get("$overall", [])
        return overall if isinstance(overall, list) else []

    # Fallback: no recognized format
    return []


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

    Segmented responses (when 'on' parameter is used):
        - Uses the '$overall' segment which contains aggregate data
        - Individual segment breakdowns are not included in FunnelResult

    Args:
        raw: Raw API response dictionary with data[date] structure.
            Non-segmented: data[date]["steps"] = list of steps
            Segmented: data[date]["$overall"] = list of steps
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
        steps_data = _extract_steps_from_date_data(date_data)
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
        # Normalize bare property names to filter expression syntax
        normalized_on = normalize_on_expression(on) if on else None

        raw = self._api_client.segmentation(
            event=event,
            from_date=from_date,
            to_date=to_date,
            on=normalized_on,
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

    def query_saved_report(
        self,
        bookmark_id: int,
        *,
        bookmark_type: Literal[
            "insights", "funnels", "retention", "flows"
        ] = "insights",
        from_date: str | None = None,
        to_date: str | None = None,
    ) -> SavedReportResult:
        """Query a saved report by bookmark type.

        Retrieves data from a pre-configured saved report by its
        bookmark ID, returning a typed result with automatic report type
        detection and lazy DataFrame conversion.

        Args:
            bookmark_id: Saved report identifier (from Mixpanel URL or list_bookmarks).
            bookmark_type: Type of bookmark to query. Determines which API endpoint
                is called. Defaults to 'insights'.
            from_date: Start date (YYYY-MM-DD). Required for funnels, optional otherwise.
            to_date: End date (YYYY-MM-DD). Required for funnels, optional otherwise.

        Returns:
            SavedReportResult with time-series data, metadata, and report_type.

        Raises:
            AuthenticationError: Invalid credentials.
            QueryError: Invalid bookmark_id or report not found.
            RateLimitError: Rate limit exceeded.

        Example:
            ```python
            result = live_query.query_saved_report(bookmark_id=12345678)
            print(f"Report type: {result.report_type}")
            print(f"Report computed at: {result.computed_at}")
            print(result.df.head())
            ```
        """
        raw = self._api_client.query_saved_report(
            bookmark_id=bookmark_id,
            bookmark_type=bookmark_type,
            from_date=from_date,
            to_date=to_date,
        )
        return _transform_saved_report(raw, bookmark_id, bookmark_type)

    def query_flows(
        self,
        bookmark_id: int,
    ) -> FlowsResult:
        """Query a saved Flows report.

        Retrieves data from a saved Flows report by its bookmark ID,
        returning step data, breakdowns, and conversion rates.

        Args:
            bookmark_id: Saved flows report identifier.

        Returns:
            FlowsResult with steps, breakdowns, and conversion rate.

        Raises:
            AuthenticationError: Invalid credentials.
            QueryError: Invalid bookmark_id or report not found.
            RateLimitError: Rate limit exceeded.

        Example:
            ```python
            result = live_query.query_flows(bookmark_id=12345678)
            print(f"Conversion rate: {result.overall_conversion_rate:.1%}")
            print(result.df.head())
            ```
        """
        raw = self._api_client.query_flows(bookmark_id=bookmark_id)
        return _transform_flows(raw, bookmark_id)

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
        # Normalize bare property names to filter expression syntax
        normalized_on = normalize_on_expression(on)

        raw = self._api_client.segmentation_numeric(
            event=event,
            from_date=from_date,
            to_date=to_date,
            on=normalized_on,
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
        # Normalize bare property names to filter expression syntax
        normalized_on = normalize_on_expression(on)

        raw = self._api_client.segmentation_sum(
            event=event,
            from_date=from_date,
            to_date=to_date,
            on=normalized_on,
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
        # Normalize bare property names to filter expression syntax
        normalized_on = normalize_on_expression(on)

        raw = self._api_client.segmentation_average(
            event=event,
            from_date=from_date,
            to_date=to_date,
            on=normalized_on,
            unit=unit,
            where=where,
        )
        return _transform_numeric_average(raw, event, from_date, to_date, on, unit)

    # =========================================================================
    # JQL-Based Remote Discovery Methods
    # =========================================================================

    def property_distribution(
        self,
        event: str,
        property: str,
        from_date: str,
        to_date: str,
        *,
        limit: int = 20,
    ) -> PropertyDistributionResult:
        """Get distribution of values for a property.

        Uses JQL to count occurrences of each property value, returning
        counts and percentages sorted by frequency.

        Args:
            event: Event name to analyze.
            property: Property name to get distribution for.
            from_date: Start date (YYYY-MM-DD).
            to_date: End date (YYYY-MM-DD).
            limit: Maximum number of values to return. Default: 20.

        Returns:
            PropertyDistributionResult with value counts and percentages.

        Raises:
            AuthenticationError: Invalid credentials.
            QueryError: Script execution error.
            RateLimitError: Rate limit exceeded.

        Example:
            ```python
            result = live_query.property_distribution(
                event="Purchase",
                property="country",
                from_date="2024-01-01",
                to_date="2024-01-31",
            )
            for v in result.values:
                print(f"{v.value}: {v.count} ({v.percentage:.1f}%)")
            ```
        """
        script = """
function main() {
    return Events({
        from_date: params.from_date,
        to_date: params.to_date,
        event_selectors: [{event: params.event}]
    })
    .filter(function(e) { return e.properties[params.property] !== undefined; })
    .groupBy(['properties.' + params.property], mixpanel.reducer.count())
    .map(function(item) {
        return {value: item.key[0], count: item.value};
    })
    .sortDesc('count');
}
"""
        params = {
            "event": event,
            "property": property,
            "from_date": from_date,
            "to_date": to_date,
            "limit": limit,
        }
        raw = self._api_client.jql(script=script, params=params)
        return _transform_property_distribution(
            raw, event, property, from_date, to_date, limit
        )

    def numeric_summary(
        self,
        event: str,
        property: str,
        from_date: str,
        to_date: str,
        *,
        percentiles: list[int] | None = None,
    ) -> NumericPropertySummaryResult:
        """Get statistical summary for a numeric property.

        Uses JQL to compute count, min, max, avg, stddev, and percentiles
        for a numeric property.

        Args:
            event: Event name to analyze.
            property: Numeric property name.
            from_date: Start date (YYYY-MM-DD).
            to_date: End date (YYYY-MM-DD).
            percentiles: Percentiles to compute. Default: [25, 50, 75, 90, 95, 99].

        Returns:
            NumericPropertySummaryResult with statistics.

        Raises:
            AuthenticationError: Invalid credentials.
            QueryError: Script execution error or non-numeric property.
            RateLimitError: Rate limit exceeded.

        Example:
            ```python
            result = live_query.numeric_summary(
                event="Purchase",
                property="amount",
                from_date="2024-01-01",
                to_date="2024-01-31",
            )
            print(f"Avg: {result.avg}, Median: {result.percentiles[50]}")
            ```
        """
        if percentiles is None:
            percentiles = [25, 50, 75, 90, 95, 99]

        script = """
function main() {
    var propPath = 'properties.' + params.property;
    return Events({
        from_date: params.from_date,
        to_date: params.to_date,
        event_selectors: [{event: params.event}]
    })
    .filter(function(e) {
        var val = e.properties[params.property];
        return val !== undefined && val !== null && typeof val === 'number';
    })
    .reduce([
        mixpanel.reducer.numeric_summary(propPath),
        mixpanel.reducer.numeric_percentiles(propPath, params.percentiles),
        mixpanel.reducer.min(propPath),
        mixpanel.reducer.max(propPath)
    ]);
}
"""
        params = {
            "event": event,
            "property": property,
            "from_date": from_date,
            "to_date": to_date,
            "percentiles": percentiles,
        }
        raw = self._api_client.jql(script=script, params=params)
        return _transform_numeric_summary(raw, event, property, from_date, to_date)

    def daily_counts(
        self,
        from_date: str,
        to_date: str,
        *,
        events: list[str] | None = None,
    ) -> DailyCountsResult:
        """Get daily event counts.

        Uses JQL to count events by day, optionally filtered to specific events.

        Args:
            from_date: Start date (YYYY-MM-DD).
            to_date: End date (YYYY-MM-DD).
            events: Optional list of events to count. None = all events.

        Returns:
            DailyCountsResult with date/event/count tuples.

        Raises:
            AuthenticationError: Invalid credentials.
            QueryError: Script execution error.
            RateLimitError: Rate limit exceeded.

        Example:
            ```python
            result = live_query.daily_counts(
                from_date="2024-01-01",
                to_date="2024-01-07",
                events=["Purchase", "Signup"],
            )
            for c in result.counts:
                print(f"{c.date} {c.event}: {c.count}")
            ```
        """
        script = """
function main() {
    var selectors = params.events ?
        params.events.map(function(e) { return {event: e}; }) :
        [];
    return Events({
        from_date: params.from_date,
        to_date: params.to_date,
        event_selectors: selectors.length > 0 ? selectors : undefined
    })
    .groupBy([
        mixpanel.numeric_bucket('time', mixpanel.daily_time_buckets),
        'name'
    ], mixpanel.reducer.count())
    .map(function(item) {
        return {
            date: new Date(item.key[0]).toISOString().split('T')[0],
            event: item.key[1],
            count: item.value
        };
    })
    .sortAsc('date');
}
"""
        params: dict[str, Any] = {
            "from_date": from_date,
            "to_date": to_date,
            "events": events,
        }
        raw = self._api_client.jql(script=script, params=params)
        return _transform_daily_counts(raw, from_date, to_date, events)

    def engagement_distribution(
        self,
        from_date: str,
        to_date: str,
        *,
        events: list[str] | None = None,
        buckets: list[int] | None = None,
    ) -> EngagementDistributionResult:
        """Get user engagement distribution.

        Uses JQL to bucket users by their event count, showing how many
        users performed N events.

        Args:
            from_date: Start date (YYYY-MM-DD).
            to_date: End date (YYYY-MM-DD).
            events: Optional list of events to count. None = all events.
            buckets: Bucket boundaries. Default: [1, 2, 5, 10, 25, 50, 100].

        Returns:
            EngagementDistributionResult with user counts per bucket.

        Raises:
            AuthenticationError: Invalid credentials.
            QueryError: Script execution error.
            RateLimitError: Rate limit exceeded.

        Example:
            ```python
            result = live_query.engagement_distribution(
                from_date="2024-01-01",
                to_date="2024-01-31",
            )
            for b in result.buckets:
                print(f"{b.bucket_label}: {b.user_count} ({b.percentage:.1f}%)")
            ```
        """
        if buckets is None:
            buckets = [1, 2, 5, 10, 25, 50, 100]

        script = """
function main() {
    var selectors = params.events ?
        params.events.map(function(e) { return {event: e}; }) :
        [];
    return Events({
        from_date: params.from_date,
        to_date: params.to_date,
        event_selectors: selectors.length > 0 ? selectors : undefined
    })
    .groupByUser(mixpanel.reducer.count())
    .groupBy([
        mixpanel.numeric_bucket('value', params.buckets)
    ], mixpanel.reducer.count())
    .map(function(item) {
        return {bucket_min: item.key[0], user_count: item.value};
    })
    .sortAsc('bucket_min');
}
"""
        params: dict[str, Any] = {
            "from_date": from_date,
            "to_date": to_date,
            "events": events,
            "buckets": buckets,
        }
        raw = self._api_client.jql(script=script, params=params)
        return _transform_engagement_distribution(
            raw, from_date, to_date, events, buckets
        )

    def property_coverage(
        self,
        event: str,
        properties: list[str],
        from_date: str,
        to_date: str,
    ) -> PropertyCoverageResult:
        """Get property coverage statistics.

        Uses JQL to count how often each property is defined (non-null)
        vs undefined for the specified event.

        Args:
            event: Event name to analyze.
            properties: List of property names to check.
            from_date: Start date (YYYY-MM-DD).
            to_date: End date (YYYY-MM-DD).

        Returns:
            PropertyCoverageResult with coverage statistics per property.

        Raises:
            AuthenticationError: Invalid credentials.
            QueryError: Script execution error.
            RateLimitError: Rate limit exceeded.

        Example:
            ```python
            result = live_query.property_coverage(
                event="Purchase",
                properties=["coupon_code", "referrer"],
                from_date="2024-01-01",
                to_date="2024-01-31",
            )
            for c in result.coverage:
                print(f"{c.property}: {c.coverage_percentage:.1f}% defined")
            ```
        """
        script = """
function main() {
    return Events({
        from_date: params.from_date,
        to_date: params.to_date,
        event_selectors: [{event: params.event}]
    })
    .reduce(function(accumulators, items) {
        // JQL reduce pattern: accumulators[0] is the running accumulated result,
        // while accumulators[1:] are partial results from parallel worker shards
        // that need to be merged. We initialize from [0] then merge [1:] to avoid
        // double-counting the accumulated value.
        var result = accumulators[0] || {total: 0, properties: {}};
        for (var i = 1; i < accumulators.length; i++) {
            result.total += accumulators[i].total || 0;
            for (var prop in accumulators[i].properties) {
                result.properties[prop] = (result.properties[prop] || 0) +
                    accumulators[i].properties[prop];
            }
        }
        items.forEach(function(e) {
            result.total++;
            params.properties.forEach(function(prop) {
                if (e.properties[prop] !== undefined && e.properties[prop] !== null) {
                    result.properties[prop] = (result.properties[prop] || 0) + 1;
                }
            });
        });
        return result;
    });
}
"""
        params = {
            "event": event,
            "properties": properties,
            "from_date": from_date,
            "to_date": to_date,
        }
        raw = self._api_client.jql(script=script, params=params)
        return _transform_property_coverage(raw, event, properties, from_date, to_date)


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
        event_time = datetime.fromtimestamp(timestamp, tz=timezone.utc)

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


def _transform_saved_report(
    raw: dict[str, Any],
    bookmark_id: int,
    bookmark_type: Literal["insights", "funnels", "retention", "flows"] = "insights",
) -> SavedReportResult:
    """Transform raw saved report API response into SavedReportResult.

    Normalizes responses from different API endpoints (insights, funnels,
    retention, flows) into a consistent SavedReportResult structure.

    Args:
        raw: Raw API response dictionary.
        bookmark_id: Saved report identifier.
        bookmark_type: Type of bookmark that was queried.

    Returns:
        Typed SavedReportResult with metadata, time-series, and report_type.
    """
    if bookmark_type == "insights":
        # Insights: {computed_at, date_range: {from_date, to_date}, headers, series}
        computed_at = raw.get("computed_at", "")
        date_range = raw.get("date_range", {})
        from_date = date_range.get("from_date", "")
        to_date = date_range.get("to_date", "")
        headers = raw.get("headers", [])
        series = raw.get("series", {})
    elif bookmark_type == "funnels":
        # Funnels: {computed_at, data: {date: {steps}}, meta}
        computed_at = raw.get("computed_at", "")
        data = raw.get("data", {})
        # Extract dates from data keys
        date_keys = sorted(data.keys()) if data else []
        from_date = date_keys[0] if date_keys else ""
        to_date = date_keys[-1] if date_keys else ""
        headers = ["$funnel"]  # Synthetic header for type detection
        series = data
    elif bookmark_type == "retention":
        # Retention: {date: {first, counts, rates}} - entire response is the data
        computed_at = ""  # Not provided by retention API
        # Response keys are dates
        date_keys = sorted(raw.keys()) if raw else []
        from_date = date_keys[0] if date_keys else ""
        to_date = date_keys[-1] if date_keys else ""
        headers = ["$retention"]  # Synthetic header for type detection
        series = raw  # Entire response is the data
    elif bookmark_type == "flows":
        # Flows: {computed_at, steps, breakdowns, overallConversionRate, metadata}
        computed_at = raw.get("computed_at", "")
        from_date = ""  # Not provided by flows API
        to_date = ""
        headers = ["$flows"]  # Synthetic header for type detection
        series = {
            "steps": raw.get("steps", []),
            "breakdowns": raw.get("breakdowns", []),
            "overallConversionRate": raw.get("overallConversionRate", 0.0),
        }
    else:
        # Fallback to insights behavior
        computed_at = raw.get("computed_at", "")
        date_range = raw.get("date_range", {})
        from_date = date_range.get("from_date", "")
        to_date = date_range.get("to_date", "")
        headers = raw.get("headers", [])
        series = raw.get("series", {})

    return SavedReportResult(
        bookmark_id=bookmark_id,
        computed_at=computed_at,
        from_date=from_date,
        to_date=to_date,
        headers=headers,
        series=series,
    )


def _transform_flows(
    raw: dict[str, Any],
    bookmark_id: int,
) -> FlowsResult:
    """Transform raw flows API response into FlowsResult.

    Extracts steps, breakdowns, and conversion rate from the response.

    Args:
        raw: Raw API response dictionary.
        bookmark_id: Saved flows report identifier.

    Returns:
        Typed FlowsResult with steps, breakdowns, and conversion rate.
    """
    computed_at = raw.get("computed_at", "")
    steps = raw.get("steps", [])
    breakdowns = raw.get("breakdowns", [])
    overall_conversion_rate = raw.get("overallConversionRate", 0.0)
    metadata = raw.get("metadata", {})

    return FlowsResult(
        bookmark_id=bookmark_id,
        computed_at=computed_at,
        steps=steps,
        breakdowns=breakdowns,
        overall_conversion_rate=overall_conversion_rate,
        metadata=metadata,
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


# =============================================================================
# JQL-Based Remote Discovery Transformation Functions
# =============================================================================


def _transform_property_distribution(
    raw: list[dict[str, Any]],
    event: str,
    property: str,
    from_date: str,
    to_date: str,
    limit: int,
) -> PropertyDistributionResult:
    """Transform raw JQL property distribution response.

    Calculates percentages for each value based on total count.

    Args:
        raw: Raw JQL response (list of {value, count} dicts).
        event: Event name queried.
        property: Property name analyzed.
        from_date: Query start date.
        to_date: Query end date.
        limit: Maximum number of values to include.

    Returns:
        Typed PropertyDistributionResult with values and percentages.
    """
    # Total count is computed from all results for accurate percentages
    total_count = sum(item.get("count", 0) for item in raw)

    # Apply limit after computing total (percentages are relative to full data)
    limited_raw = raw[:limit]

    def make_value_count(item: dict[str, Any]) -> PropertyValueCount:
        count = item.get("count", 0)
        return PropertyValueCount(
            value=item.get("value"),
            count=count,
            percentage=(count / total_count * 100) if total_count > 0 else 0.0,
        )

    values = tuple(make_value_count(item) for item in limited_raw)

    return PropertyDistributionResult(
        event=event,
        property_name=property,
        from_date=from_date,
        to_date=to_date,
        total_count=total_count,
        values=values,
    )


def _transform_numeric_summary(
    raw: list[Any],
    event: str,
    property: str,
    from_date: str,
    to_date: str,
) -> NumericPropertySummaryResult:
    """Transform raw JQL numeric summary response.

    JQL reduce with multiple reducers returns a nested list structure:
    [[{summary_dict}, [{percentile_obj}, ...]]]

    Args:
        raw: Raw JQL response (nested list with summary and percentiles).
        event: Event name queried.
        property: Property name analyzed.
        from_date: Query start date.
        to_date: Query end date.

    Returns:
        Typed NumericPropertySummaryResult with statistics.
    """
    # JQL returns [[summary_dict, percentiles_list]] for multiple reducers
    if not raw or not raw[0]:
        return NumericPropertySummaryResult(
            event=event,
            property_name=property,
            from_date=from_date,
            to_date=to_date,
            count=0,
            min=0.0,
            max=0.0,
            sum=0.0,
            avg=0.0,
            stddev=0.0,
            percentiles={},
        )

    inner = raw[0]

    # Extract results from the inner array:
    # [summary_dict, percentiles_list, min_value, max_value]
    summary_data: dict[str, Any] = inner[0] if len(inner) > 0 else {}
    percentiles_list: list[dict[str, Any]] = inner[1] if len(inner) > 1 else []
    min_value: float = (
        float(inner[2]) if len(inner) > 2 and inner[2] is not None else 0.0
    )
    max_value: float = (
        float(inner[3]) if len(inner) > 3 and inner[3] is not None else 0.0
    )

    # Parse percentiles from list of {percentile: N, value: V} objects
    percentiles = {
        int(p.get("percentile", 0)): float(p.get("value", 0.0))
        for p in percentiles_list
    }

    return NumericPropertySummaryResult(
        event=event,
        property_name=property,
        from_date=from_date,
        to_date=to_date,
        count=summary_data.get("count", 0),
        min=min_value,
        max=max_value,
        sum=float(summary_data.get("sum", 0.0)),
        avg=float(summary_data.get("avg", 0.0)),
        stddev=float(summary_data.get("stddev", 0.0)),
        percentiles=percentiles,
    )


def _transform_daily_counts(
    raw: list[dict[str, Any]],
    from_date: str,
    to_date: str,
    events: list[str] | None,
) -> DailyCountsResult:
    """Transform raw JQL daily counts response.

    Args:
        raw: Raw JQL response (list of {date, event, count} dicts).
        from_date: Query start date.
        to_date: Query end date.
        events: Events filter (or None for all).

    Returns:
        Typed DailyCountsResult with date/event/count tuples.
    """
    counts = tuple(
        DailyCount(
            date=item.get("date", ""),
            event=item.get("event", ""),
            count=item.get("count", 0),
        )
        for item in raw
    )

    return DailyCountsResult(
        from_date=from_date,
        to_date=to_date,
        events=tuple(events) if events else None,
        counts=counts,
    )


def _transform_engagement_distribution(
    raw: list[dict[str, Any]],
    from_date: str,
    to_date: str,
    events: list[str] | None,
    buckets: list[int],
) -> EngagementDistributionResult:
    """Transform raw JQL engagement distribution response.

    Calculates percentages and labels for each bucket.

    Args:
        raw: Raw JQL response (list of {bucket_min, user_count} dicts).
        from_date: Query start date.
        to_date: Query end date.
        events: Events filter (or None for all).
        buckets: Bucket boundaries used in query.

    Returns:
        Typed EngagementDistributionResult with buckets.
    """
    total_users = sum(item.get("user_count", 0) for item in raw)

    def make_label(bucket_min: int, idx: int) -> str:
        """Generate human-readable bucket label."""
        if idx < len(buckets) - 1:
            next_bucket = buckets[idx + 1]
            if next_bucket == bucket_min + 1:
                return str(bucket_min)
            return f"{bucket_min}-{next_bucket - 1}"
        return f"{bucket_min}+"

    # Build bucket labels based on bucket boundaries
    bucket_list = tuple(
        EngagementBucket(
            bucket_min=item.get("bucket_min", 0),
            bucket_label=make_label(
                item.get("bucket_min", 0),
                next(
                    (
                        i
                        for i, b in enumerate(buckets)
                        if b == item.get("bucket_min", 0)
                    ),
                    len(buckets) - 1,
                ),
            ),
            user_count=item.get("user_count", 0),
            percentage=(item.get("user_count", 0) / total_users * 100)
            if total_users > 0
            else 0.0,
        )
        for item in raw
    )

    return EngagementDistributionResult(
        from_date=from_date,
        to_date=to_date,
        events=tuple(events) if events else None,
        total_users=total_users,
        buckets=bucket_list,
    )


def _transform_property_coverage(
    raw: list[dict[str, Any]],
    event: str,
    properties: list[str],
    from_date: str,
    to_date: str,
) -> PropertyCoverageResult:
    """Transform raw JQL property coverage response.

    Calculates null counts and coverage percentages for each property.

    Args:
        raw: Raw JQL response (list with single {total, properties} dict).
        event: Event name queried.
        properties: Property names checked.
        from_date: Query start date.
        to_date: Query end date.

    Returns:
        Typed PropertyCoverageResult with coverage statistics.
    """
    # JQL reduce returns a list with one element
    data = raw[0] if raw else {"total": 0, "properties": {}}
    total_events = data.get("total", 0)
    prop_counts = data.get("properties", {})

    coverage = tuple(
        PropertyCoverage(
            property=prop,
            defined_count=prop_counts.get(prop, 0),
            null_count=total_events - prop_counts.get(prop, 0),
            coverage_percentage=(prop_counts.get(prop, 0) / total_events * 100)
            if total_events > 0
            else 0.0,
        )
        for prop in properties
    )

    return PropertyCoverageResult(
        event=event,
        from_date=from_date,
        to_date=to_date,
        total_events=total_events,
        coverage=coverage,
    )
