"""Live Query Service for Mixpanel analytics queries.

Provides methods to execute live queries against the Mixpanel Query API
and transform responses into typed result objects with DataFrame support.

Unlike DiscoveryService, this service does not cache results because
analytics data changes frequently and queries should return fresh data.
"""

from __future__ import annotations

import re
import warnings
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Literal

from mixpanel_headless._internal.expressions import normalize_on_expression
from mixpanel_headless._literal_types import CountType, HourDayUnit, TimeUnit
from mixpanel_headless.exceptions import QueryError
from mixpanel_headless.types import (
    ActivityFeedResult,
    CohortInfo,
    DailyCount,
    DailyCountsResult,
    EngagementBucket,
    EngagementDistributionResult,
    EventCountsResult,
    FlowQueryResult,
    FlowsResult,
    FlowTreeNode,
    FrequencyResult,
    FunnelQueryResult,
    FunnelResult,
    FunnelResultStep,
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
    QueryResult,
    RetentionQueryResult,
    RetentionResult,
    SavedReportResult,
    SegmentationResult,
    UserEvent,
    _safe_int,
)

if TYPE_CHECKING:
    from mixpanel_headless._internal.api_client import MixpanelAPIClient

_STEP_PREFIX_RE = re.compile(r"^(\d+)\.\s*(.+)$")
"""Matches step names like ``"1. Signup"`` and captures (index, event_name)."""


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

    # Build FunnelResultStep list with recalculated conversion rates
    steps: list[FunnelResultStep] = []
    prev_count = 0
    for idx in sorted(aggregated_counts.keys()):
        event, count = aggregated_counts[idx]
        conv_rate = 1.0 if idx == 0 else (count / prev_count if prev_count > 0 else 0.0)
        steps.append(
            FunnelResultStep(event=event, count=count, conversion_rate=conv_rate)
        )
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


def _transform_query_result(
    raw: dict[str, Any],
    bookmark_params: dict[str, Any],
) -> QueryResult:
    """Transform raw insights query response into QueryResult.

    Extracts nested date_range fields, copies computed_at, headers,
    series, and meta from the raw response. Validates that the response
    contains expected fields and is not an error-as-200.

    Args:
        raw: Raw API response dictionary from insights query.
        bookmark_params: The bookmark params dict sent to the API.

    Returns:
        Typed QueryResult with all fields populated.

    Raises:
        QueryError: If the response contains an error or is missing
            required fields.
    """
    # Check for error responses that leaked through as HTTP 200
    if "error" in raw:
        raise QueryError(
            f"Insights query failed: {raw['error']}",
            status_code=200,
            response_body=raw,
            request_body=bookmark_params,
        )

    if "series" not in raw:
        raise QueryError(
            "Insights query returned unexpected response shape "
            f"(missing 'series' key). Keys present: {sorted(raw.keys())}",
            status_code=200,
            response_body=raw,
            request_body=bookmark_params,
        )

    date_range = raw.get("date_range", {})
    return QueryResult(
        computed_at=raw.get("computed_at", ""),
        from_date=date_range.get("from_date", ""),
        to_date=date_range.get("to_date", ""),
        headers=raw.get("headers", []),
        series=raw["series"],
        params=bookmark_params,
        meta=raw.get("meta", {}),
    )


def _extract_funnel_steps_from_series(
    series: Any,
) -> list[dict[str, Any]]:
    """Extract step-level data from funnel series response.

    The insights API returns funnel data organized by metric type,
    with step names as keys (e.g. ``"1. Signup"``). This function
    pivots that structure into a flat list of step dicts.

    The response format is::

        {
          "Signup through Purchase": {
            "count": {"1. Signup": {"all": 1000}, "2. Purchase": {"all": 120}},
            "step_conv_ratio": {"1. Signup": {"all": 1.0}, ...},
            "overall_conv_ratio": {...},
            "avg_time": {...},
            "avg_time_from_start": {...},
          }
        }

    Args:
        series: Raw series data from insights API response.

    Returns:
        List of step dicts with keys: ``event``, ``count``,
        ``step_conv_ratio``, ``overall_conv_ratio``, ``avg_time``,
        ``avg_time_from_start``.
    """
    if isinstance(series, list):
        return series

    if not isinstance(series, dict):
        return []

    # Direct "steps" key (alternative format)
    if "steps" in series:
        steps = series["steps"]
        if isinstance(steps, list):
            return steps

    # Top-level "$overall" key (legacy/alternative format)
    if "$overall" in series:
        overall = series["$overall"]
        if isinstance(overall, dict) and "steps" in overall:
            overall_steps = overall["steps"]
            if isinstance(overall_steps, list):
                return overall_steps
        if isinstance(overall, list):
            result_list: list[dict[str, Any]] = overall
            return result_list

    # Insights API funnel format: series is {funnel_key: {metric: {step: {seg: val}}}}
    # With group_by: {funnel_key: {$overall: {metric: ...}, segment: {metric: ...}}}
    # With trends:   {funnel_key: {date: {metric: ...}, date: {metric: ...}}}
    # Find the first funnel key and resolve to the metrics dict
    funnel_data: dict[str, Any] | None = None
    for _key, value in series.items():
        if not isinstance(value, dict):
            continue
        # Direct metrics format (no group_by, mode=steps)
        if "count" in value:
            funnel_data = value
            break
        # Segmented format (group_by): look for $overall
        if "$overall" in value:
            overall_val = value["$overall"]
            if isinstance(overall_val, dict) and "count" in overall_val:
                funnel_data = overall_val
                break
        # Trends format: look for first date-like key with metrics
        for _sub_key, sub_val in value.items():
            if isinstance(sub_val, dict) and "count" in sub_val:
                funnel_data = sub_val
                break
        if funnel_data is not None:
            break

    if funnel_data is None:
        if series:
            warnings.warn(
                "Funnel query returned data in an unrecognized format "
                f"(series keys: {sorted(series.keys())}). "
                "The raw response is available in the 'series' field.",
                stacklevel=2,
            )
        return []

    # Extract step names from the "count" metric (always present)
    count_data = funnel_data.get("count", {})
    if not isinstance(count_data, dict):
        return []

    # Step names are like "1. Signup", "2. Purchase" — sort by numeric prefix
    # to handle 10+ steps correctly (lexicographic sort would put "10." before "2.")

    def _step_sort_key(name: str) -> tuple[int, str]:
        m = _STEP_PREFIX_RE.match(name)
        return (int(m.group(1)), name) if m else (2**31, name)

    step_names = sorted(count_data.keys(), key=_step_sort_key)

    # Helper to get a metric value for a step (handles "all" segment)
    def _get_val(metric: str, step_name: str) -> Any:
        metric_data = funnel_data.get(metric, {})
        step_data = metric_data.get(step_name, {})
        if isinstance(step_data, dict):
            return step_data.get("all", 0)
        return step_data if step_data is not None else 0

    # Build step dicts
    result: list[dict[str, Any]] = []
    for step_name in step_names:
        match = _STEP_PREFIX_RE.match(step_name)
        event = match.group(2) if match else step_name

        result.append(
            {
                "event": event,
                "count": _get_val("count", step_name),
                "step_conv_ratio": _get_val("step_conv_ratio", step_name),
                "overall_conv_ratio": _get_val("overall_conv_ratio", step_name),
                "avg_time": _get_val("avg_time", step_name),
                "avg_time_from_start": _get_val("avg_time_from_start", step_name),
            }
        )

    return result


def _transform_funnel_result(
    raw: dict[str, Any],
    bookmark_params: dict[str, Any],
) -> FunnelQueryResult:
    """Transform raw insights query funnel response into FunnelQueryResult.

    Extracts computed_at, date_range, step data from the series, and
    raw metadata. The response follows the standard insights response
    envelope but the ``series`` field contains funnel step data.

    Args:
        raw: Raw API response dictionary from insights query.
        bookmark_params: The bookmark params dict sent to the API
            (preserved in the result for debugging/persistence).

    Returns:
        Typed FunnelQueryResult with step data and metadata.

    Raises:
        QueryError: If the response contains an error or is missing
            required fields.
    """
    # Check for error responses that leaked through as HTTP 200
    if "error" in raw:
        raise QueryError(
            f"Funnel query failed: {raw['error']}",
            status_code=200,
            response_body=raw,
            request_body=bookmark_params,
        )

    if "series" not in raw:
        raise QueryError(
            "Funnel query returned unexpected response shape "
            f"(missing 'series' key). Keys present: {sorted(raw.keys())}",
            status_code=200,
            response_body=raw,
            request_body=bookmark_params,
        )

    date_range = raw.get("date_range", {})
    series = raw["series"]
    steps_data = _extract_funnel_steps_from_series(series)

    return FunnelQueryResult(
        computed_at=raw.get("computed_at", ""),
        from_date=date_range.get("from_date", ""),
        to_date=date_range.get("to_date", ""),
        steps_data=steps_data,
        series=series,
        params=bookmark_params,
        meta=raw.get("meta", {}),
    )


def _normalize_cohort_date(key: str) -> str:
    """Normalize an ISO timestamp cohort key to YYYY-MM-DD.

    The insights API may return cohort date keys as full ISO timestamps
    (e.g. ``2025-01-01T00:00:00+00:00``). This truncates to the first
    10 characters to produce a plain ``YYYY-MM-DD`` date string.

    Args:
        key: Cohort date key from the API response.

    Returns:
        Normalized date string (``YYYY-MM-DD``).
    """
    return key[:10] if "T" in key else key


def _extract_cohorts_and_average(
    data: dict[str, Any],
) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    """Extract date-keyed cohorts and $average from a cohort data dict.

    Normalizes cohort date keys to ``YYYY-MM-DD`` format.

    Args:
        data: Cohort data dict (date keys + optional ``$average``).

    Returns:
        Tuple of (cohorts dict, average dict).
    """
    average: dict[str, Any] = {}
    cohorts: dict[str, dict[str, Any]] = {}
    for key, value in data.items():
        if key == "$average":
            average = value if isinstance(value, dict) else {}
        elif isinstance(value, dict):
            cohorts[_normalize_cohort_date(key)] = value
    return cohorts, average


def _transform_retention_result(
    raw: dict[str, Any],
    bookmark_params: dict[str, Any],
) -> RetentionQueryResult:
    """Transform raw insights query retention response into RetentionQueryResult.

    Extracts computed_at, date_range, cohort data from the series, and
    the synthetic ``$average`` cohort. Validates that the response
    contains expected fields and is not an error-as-200.

    The insights API always wraps retention data in a metric name key::

        series = {
            "EventA and then EventB": {
                "2025-01-01T00:00:00+00:00": {"first": 100, "counts": [...], "rates": [...]},
                "$average": {"first": 90, "counts": [...], "rates": [...]},
            }
        }

    For segmented (``group_by``) queries, the response nests segments
    alongside ``$overall``::

        series = {
            "EventA and then EventB": {
                "$overall": {"2025-01-01": {...}, "$average": {...}},
                "iOS":      {"2025-01-01": {...}, "$average": {...}},
                "Android":  {"2025-01-01": {...}, "$average": {...}},
            }
        }

    This function unwraps the outer metric key and extracts both
    aggregate (``$overall``) and per-segment cohort data.

    Args:
        raw: Raw API response dictionary from insights query.
        bookmark_params: The bookmark params dict sent to the API
            (preserved in the result for debugging/persistence).

    Returns:
        Typed RetentionQueryResult with cohort data and metadata.

    Raises:
        QueryError: If the response contains an error or is missing
            required fields.
    """
    # Check for error responses that leaked through as HTTP 200
    if "error" in raw:
        raise QueryError(
            f"Retention query failed: {raw['error']}",
            status_code=200,
            response_body=raw,
            request_body=bookmark_params,
        )

    if "series" not in raw:
        raise QueryError(
            "Retention query returned unexpected response shape "
            f"(missing 'series' key). Keys present: {sorted(raw.keys())}",
            status_code=200,
            response_body=raw,
            request_body=bookmark_params,
        )

    date_range = raw.get("date_range", {})
    series = raw.get("series", {})

    if not isinstance(series, dict):
        raise QueryError(
            f"Retention query 'series' field is {type(series).__name__}, "
            "expected dict.",
            status_code=200,
            response_body=raw,
            request_body=bookmark_params,
        )

    # Unwrap the metric name key: series = {"metric_name": {date_cohorts}}
    # The API returns exactly one top-level key (the metric name).
    # Multiple top-level keys indicate a genuinely malformed response.
    cohort_data: dict[str, Any] = {}
    if series:
        if len(series) > 1:
            raise QueryError(
                "Retention query returned segmented series with "
                f"{len(series)} keys that cannot be represented as a "
                "single RetentionQueryResult without losing data. "
                f"Keys: {sorted(series.keys())}",
                status_code=200,
                response_body=raw,
                request_body=bookmark_params,
            )
        for _metric_key, value in series.items():
            if isinstance(value, dict):
                cohort_data = value
                break
        else:
            # No dict value found — the metric key maps to a non-dict
            metric_key = next(iter(series))
            raise QueryError(
                f"Retention series value for key {metric_key!r} is not a "
                f"dict (got {type(series[metric_key]).__name__}). "
                "Expected cohort data dictionary.",
                status_code=200,
                response_body=raw,
                request_body=bookmark_params,
            )

    # Handle segmented responses: $overall + named segments
    segments: dict[str, dict[str, dict[str, Any]]] = {}
    segment_averages: dict[str, dict[str, Any]] = {}

    if "$overall" in cohort_data and isinstance(cohort_data["$overall"], dict):
        # Extract aggregate from $overall
        overall_data = cohort_data["$overall"]
        cohorts, average = _extract_cohorts_and_average(overall_data)

        # Extract named segments (everything except $overall)
        for seg_key, seg_value in cohort_data.items():
            if seg_key == "$overall" or not isinstance(seg_value, dict):
                continue
            seg_cohorts, seg_avg = _extract_cohorts_and_average(seg_value)
            segments[seg_key] = seg_cohorts
            if seg_avg:
                segment_averages[seg_key] = seg_avg
    else:
        # Unsegmented: extract $average and date-keyed cohorts directly
        cohorts, average = _extract_cohorts_and_average(cohort_data)

    return RetentionQueryResult(
        computed_at=raw.get("computed_at", ""),
        from_date=date_range.get("from_date", ""),
        to_date=date_range.get("to_date", ""),
        cohorts=cohorts,
        average=average,
        params=bookmark_params,
        meta=raw.get("meta", {}),
        segments=segments,
        segment_averages=segment_averages,
    )


class LiveQueryService:
    """Service for executing live queries against the Mixpanel Query API.

    Transforms raw API responses into typed result objects with DataFrame support.
    Unlike DiscoveryService, results are not cached because analytics data
    changes frequently and queries should return fresh data.

    Example:
        ```python
        from mixpanel_headless._internal.api_client import MixpanelAPIClient
        from mixpanel_headless._internal.services.live_query import LiveQueryService

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

    def query(
        self,
        bookmark_params: dict[str, Any],
        project_id: int,
    ) -> QueryResult:
        """Execute an inline insights query with pre-built bookmark params.

        Posts bookmark params directly to the insights query endpoint,
        transforms the response into a QueryResult with lazy DataFrame.

        Args:
            bookmark_params: Pre-built bookmark params dict.
            project_id: Mixpanel project ID.

        Returns:
            QueryResult with series data and metadata.

        Raises:
            AuthenticationError: Invalid credentials.
            QueryError: Invalid bookmark params.
            RateLimitError: Rate limit exceeded.

        Example:
            ```python
            result = live_query.query(
                bookmark_params={"sections": {...}, "displayOptions": {...}},
                project_id=12345,
            )
            print(result.df.head())
            ```
        """
        body: dict[str, Any] = {
            "bookmark": bookmark_params,
            "project_id": project_id,
            "queryLimits": {"limit": 3000},
        }
        raw = self._api_client.insights_query(body)
        return _transform_query_result(raw, bookmark_params)

    def query_funnel(
        self,
        bookmark_params: dict[str, Any],
        project_id: int,
    ) -> FunnelQueryResult:
        """Execute an inline funnel query with pre-built bookmark params.

        Posts funnel bookmark params to the insights query endpoint
        (the API detects ``behavior.type == "funnel"`` and delegates
        to the funnels query engine), then transforms the response
        into a FunnelQueryResult with lazy DataFrame.

        Args:
            bookmark_params: Pre-built funnel bookmark params dict.
            project_id: Mixpanel project ID.

        Returns:
            FunnelQueryResult with step data, conversion rates,
            and metadata.

        Raises:
            AuthenticationError: Invalid credentials.
            QueryError: Invalid bookmark params.
            RateLimitError: Rate limit exceeded.

        Example:
            ```python
            result = live_query.query_funnel(
                bookmark_params={"sections": {...}, "displayOptions": {...}},
                project_id=12345,
            )
            print(result.overall_conversion_rate)
            ```
        """
        body: dict[str, Any] = {
            "bookmark": bookmark_params,
            "project_id": project_id,
            "queryLimits": {"limit": 3000},
        }
        raw = self._api_client.insights_query(body)
        return _transform_funnel_result(raw, bookmark_params)

    def query_retention(
        self,
        bookmark_params: dict[str, Any],
        project_id: int,
    ) -> RetentionQueryResult:
        """Execute an inline retention query with pre-built bookmark params.

        Posts retention bookmark params to the insights query endpoint
        (the API detects ``behavior.type == "retention"`` and delegates
        to the retention query engine), then transforms the response
        into a RetentionQueryResult with lazy DataFrame.

        Args:
            bookmark_params: Pre-built retention bookmark params dict.
            project_id: Mixpanel project ID.

        Returns:
            RetentionQueryResult with cohort data, DataFrame,
            and metadata.

        Raises:
            AuthenticationError: Invalid credentials.
            QueryError: Invalid bookmark params.
            RateLimitError: Rate limit exceeded.

        Example:
            ```python
            result = live_query.query_retention(
                bookmark_params={"sections": {...}, "displayOptions": {...}},
                project_id=12345,
            )
            print(result.cohorts)
            ```
        """
        body: dict[str, Any] = {
            "bookmark": bookmark_params,
            "project_id": project_id,
            "queryLimits": {"limit": 3000},
        }
        raw = self._api_client.insights_query(body)
        return _transform_retention_result(raw, bookmark_params)

    def query_flow(
        self,
        bookmark_params: dict[str, Any],
        project_id: int,
        mode: str = "sankey",
    ) -> FlowQueryResult:
        """Execute an inline flow query with pre-built bookmark params.

        Posts flow bookmark params to the ``/arb_funnels`` endpoint with
        the appropriate ``query_type`` (``flows_sankey`` or
        ``flows_top_paths``), then transforms the response into a
        structured ``FlowQueryResult``.

        Args:
            bookmark_params: Pre-built flow bookmark params dict (flat
                structure with ``steps``, ``date_range``, ``chartType``,
                ``count_type``, and ``version`` keys).
            project_id: Mixpanel project ID.
            mode: Flow visualization mode — ``"sankey"`` for Sankey
                diagrams, ``"paths"`` for top-paths analysis, or
                ``"tree"`` for prefix tree analysis.
                Default: ``"sankey"``.

        Returns:
            FlowQueryResult with steps, flows, breakdowns, conversion
            rate, and metadata.

        Raises:
            AuthenticationError: Invalid credentials.
            QueryError: Invalid bookmark params or error-as-200.
            RateLimitError: Rate limit exceeded.

        Example:
            ```python
            result = live_query.query_flow(
                bookmark_params={"steps": [...], "chartType": "sankey", ...},
                project_id=12345,
                mode="sankey",
            )
            print(f"Conversion: {result.overall_conversion_rate:.1%}")
            ```
        """
        if mode == "paths":
            query_type = "flows_top_paths"
        elif mode == "tree":
            query_type = "flows"
        else:
            query_type = "flows_sankey"
        body: dict[str, Any] = {
            "bookmark": bookmark_params,
            "project_id": project_id,
            "query_type": query_type,
        }
        raw = self._api_client.arb_funnels_query(body)
        return _transform_flow_result(raw, bookmark_params, mode=mode)

    def query_saved_flows(
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
            result = live_query.query_saved_flows(bookmark_id=12345678)
            print(f"Conversion rate: {result.overall_conversion_rate:.1%}")
            print(result.df.head())
            ```
        """
        raw = self._api_client.query_saved_flows(bookmark_id=bookmark_id)
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


def _transform_flow_result(
    raw: dict[str, Any],
    bookmark_params: dict[str, Any],
    mode: str,
) -> FlowQueryResult:
    """Transform raw arb_funnels flow response into FlowQueryResult.

    Extracts computed_at, steps, flows, breakdowns, and overall
    conversion rate from the API response. Handles sankey, top-paths,
    and tree modes. Detects error-as-200 responses and raises
    ``QueryError``.

    Args:
        raw: Raw API response dictionary from arb_funnels query.
        bookmark_params: The bookmark params dict sent to the API
            (preserved in the result for debugging/persistence).
        mode: Flow visualization mode — ``"sankey"``, ``"paths"``,
            or ``"tree"``.

    Returns:
        Typed FlowQueryResult with steps, flows, breakdowns,
        conversion rate, and metadata.

    Raises:
        QueryError: If the response contains an error field
            (error-as-200 pattern).

    Example:
        ```python
        result = _transform_flow_result(
            raw={"computed_at": "...", "steps": [...], ...},
            bookmark_params={"steps": [...], ...},
            mode="sankey",
        )
        print(result.overall_conversion_rate)
        ```
    """
    # Check for error responses that leaked through as HTTP 200
    if "error" in raw:
        raise QueryError(
            f"Flow query failed: {raw['error']}",
            status_code=200,
            response_body=raw,
            request_body=bookmark_params,
        )

    # Validate expected response shape (consistent with insights/funnel transforms).
    # Tree mode may legitimately return only metadata with no trees key,
    # so only sankey/paths modes enforce structural presence.
    _expected_keys = {"steps", "flows", "trees", "computed_at", "metadata"}
    if (
        mode != "tree"
        and "steps" not in raw
        and "flows" not in raw
        and not _expected_keys.intersection(raw.keys())
    ):
        raise QueryError(
            "Flow query returned unexpected response shape "
            f"(missing 'steps' and 'flows' keys). "
            f"Keys present: {sorted(raw.keys())}",
            status_code=200,
            response_body=raw,
            request_body=bookmark_params,
        )

    computed_at: str = raw.get("computed_at", "")
    steps: list[dict[str, Any]] = raw.get("steps", [])
    flows: list[dict[str, Any]] = raw.get("flows", [])
    breakdowns: list[dict[str, Any]] = raw.get("breakdowns", [])
    overall_conversion_rate: float = raw.get("overallConversionRate", 0.0)
    metadata: dict[str, Any] = raw.get("metadata", {})

    # Parse tree data when in tree mode
    trees: list[FlowTreeNode] = []
    if mode == "tree":
        for tree_dict in raw.get("trees", []):
            root_dict = tree_dict.get("root", {})
            if root_dict:
                parsed_root = _parse_tree_node(root_dict)
                # The API returns a virtual root node with step=null.
                # The actual anchor events are its children. If the
                # root has no event (virtual), unwrap the children
                # as separate trees. If the root has an event (e.g.
                # from test fixtures), keep it as-is.
                if parsed_root.event:
                    trees.append(parsed_root)
                else:
                    trees.extend(parsed_root.children)

    # Determine the result mode literal
    result_mode: Literal["sankey", "paths", "tree"]
    if mode == "tree":
        result_mode = "tree"
    elif mode == "paths":
        result_mode = "paths"
    else:
        result_mode = "sankey"

    return FlowQueryResult(
        computed_at=computed_at,
        steps=steps,
        flows=flows,
        breakdowns=breakdowns,
        overall_conversion_rate=overall_conversion_rate,
        params=bookmark_params,
        meta=metadata,
        mode=result_mode,
        trees=trees,
    )


def _parse_tree_node(raw: dict[str, Any]) -> FlowTreeNode:
    """Parse a recursive raw dict into a FlowTreeNode.

    Extracts step metadata (event, type, step_number) from the ``step``
    sub-dict and count data from the top level. Recursively parses
    child nodes.

    Handles both camelCase (live API: ``stepNumber``, ``totalCount``,
    ``dropOffTotalCount``, ``convertedTotalCount``) and snake_case
    (``step_number``, ``total_count``, ``drop_off_total_count``,
    ``converted_total_count``) field names.

    Args:
        raw: Raw dict from the API response representing a single tree
            node with ``step``, ``children``, and count fields.

    Returns:
        A frozen ``FlowTreeNode`` with recursively parsed children.

    Example:
        ```python
        node = _parse_tree_node({
            "step": {"event": "Login", "type": "ANCHOR", ...},
            "children": [...],
            "totalCount": 100,
            ...
        })
        node.event  # "Login"
        ```
    """
    step: dict[str, Any] = raw.get("step") or {}
    children = tuple(_parse_tree_node(c) for c in raw.get("children", []))

    # Support both camelCase (live API) and snake_case (test fixtures)
    step_number_raw = step.get("stepNumber", step.get("step_number", 0))
    total_count = raw.get("totalCount", raw.get("total_count", 0))
    drop_off_count = raw.get("dropOffTotalCount", raw.get("drop_off_total_count", 0))
    converted_count = raw.get(
        "convertedTotalCount", raw.get("converted_total_count", 0)
    )
    anchor_type = step.get("anchorType", step.get("anchor_type", "NORMAL"))
    is_computed = step.get("isComputed", step.get("is_computed", False))

    # Time percentiles: camelCase or snake_case, may be null
    tp_start = (
        raw.get("timePercentilesFromStart")
        or raw.get("time_percentiles_from_start")
        or {}
    )
    tp_prev = (
        raw.get("timePercentilesFromPrev")
        or raw.get("time_percentiles_from_prev")
        or {}
    )

    return FlowTreeNode(
        event=step.get("event", ""),
        type=step.get("type", ""),
        step_number=_safe_int(step_number_raw),
        total_count=_safe_int(total_count),
        drop_off_count=_safe_int(drop_off_count),
        converted_count=_safe_int(converted_count),
        anchor_type=anchor_type,
        is_computed=is_computed,
        children=children,
        time_percentiles_from_start=tp_start if isinstance(tp_start, dict) else {},
        time_percentiles_from_prev=tp_prev if isinstance(tp_prev, dict) else {},
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
    data: dict[str, Any] = raw[0] if raw else {"total": 0, "properties": {}}
    total_events: int = int(data.get("total", 0))
    prop_counts: dict[str, int] = data.get("properties", {})

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
