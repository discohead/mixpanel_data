"""Result types for mixpanel_data operations.

All result types are immutable frozen dataclasses with:
- Lazy DataFrame conversion via the `df` property
- JSON serialization via the `to_dict()` method
- Full type hints for IDE/mypy support
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal

import pandas as pd


@dataclass(frozen=True)
class FetchResult:
    """Result of a data fetch operation.

    Represents the outcome of fetching events or profiles from Mixpanel
    and storing them in the local database.
    """

    table: str
    """Name of the created table."""

    rows: int
    """Number of rows fetched."""

    type: Literal["events", "profiles"]
    """Type of data fetched."""

    duration_seconds: float
    """Time taken to complete the fetch."""

    date_range: tuple[str, str] | None
    """Date range for events (None for profiles)."""

    fetched_at: datetime
    """Timestamp when fetch completed."""

    # Internal field for caching DataFrame (not part of public API)
    _data: list[dict[str, Any]] = field(default_factory=list, repr=False)
    _df_cache: pd.DataFrame | None = field(default=None, repr=False)

    @property
    def df(self) -> pd.DataFrame:
        """Convert result data to pandas DataFrame.

        Conversion is lazy - computed on first access and cached.

        Returns:
            DataFrame with fetched data.
        """
        if self._df_cache is not None:
            return self._df_cache

        result_df = pd.DataFrame(self._data) if self._data else pd.DataFrame()

        # Cache using object.__setattr__ for frozen dataclass
        object.__setattr__(self, "_df_cache", result_df)
        return result_df

    def to_dict(self) -> dict[str, Any]:
        """Serialize result for JSON output.

        Returns:
            Dictionary representation (excludes raw data).
            datetime values are converted to ISO format strings.
        """
        return {
            "table": self.table,
            "rows": self.rows,
            "type": self.type,
            "duration_seconds": self.duration_seconds,
            "date_range": self.date_range,
            "fetched_at": self.fetched_at.isoformat(),
        }


@dataclass(frozen=True)
class SegmentationResult:
    """Result of a segmentation query.

    Contains time-series data for an event, optionally segmented by a property.
    """

    event: str
    """Queried event name."""

    from_date: str
    """Query start date (YYYY-MM-DD)."""

    to_date: str
    """Query end date (YYYY-MM-DD)."""

    unit: Literal["day", "week", "month"]
    """Time unit for aggregation."""

    segment_property: str | None
    """Property used for segmentation (None if total only)."""

    total: int
    """Total count across all segments and time periods."""

    series: dict[str, dict[str, int]] = field(default_factory=dict)
    """Time series data by segment.

    Structure: {segment_name: {date_string: count}}
    Example: {"US": {"2024-01-01": 150, "2024-01-02": 200}, "EU": {...}}
    For unsegmented queries, segment_name is "total".
    """

    _df_cache: pd.DataFrame | None = field(default=None, repr=False)

    @property
    def df(self) -> pd.DataFrame:
        """Convert to DataFrame with columns: date, segment, count.

        For unsegmented queries, segment column is 'total'.
        """
        if self._df_cache is not None:
            return self._df_cache

        rows: list[dict[str, Any]] = []

        for segment_name, date_counts in self.series.items():
            for date_str, count in date_counts.items():
                rows.append(
                    {
                        "date": date_str,
                        "segment": segment_name,
                        "count": count,
                    }
                )

        result_df = (
            pd.DataFrame(rows)
            if rows
            else pd.DataFrame(columns=["date", "segment", "count"])
        )

        object.__setattr__(self, "_df_cache", result_df)
        return result_df

    def to_dict(self) -> dict[str, Any]:
        """Serialize for JSON output."""
        return {
            "event": self.event,
            "from_date": self.from_date,
            "to_date": self.to_date,
            "unit": self.unit,
            "segment_property": self.segment_property,
            "total": self.total,
            "series": self.series,
        }


@dataclass(frozen=True)
class FunnelStep:
    """Single step in a funnel."""

    event: str
    """Event name for this step."""

    count: int
    """Number of users at this step."""

    conversion_rate: float
    """Conversion rate from previous step (0.0 to 1.0)."""

    def to_dict(self) -> dict[str, Any]:
        """Serialize for JSON output."""
        return {
            "event": self.event,
            "count": self.count,
            "conversion_rate": self.conversion_rate,
        }


@dataclass(frozen=True)
class FunnelResult:
    """Result of a funnel query.

    Contains step-by-step conversion data for a funnel.
    """

    funnel_id: int
    """Funnel identifier."""

    funnel_name: str
    """Funnel display name."""

    from_date: str
    """Query start date."""

    to_date: str
    """Query end date."""

    conversion_rate: float
    """Overall conversion rate (0.0 to 1.0)."""

    steps: list[FunnelStep] = field(default_factory=list)
    """Step-by-step breakdown."""

    _df_cache: pd.DataFrame | None = field(default=None, repr=False)

    @property
    def df(self) -> pd.DataFrame:
        """Convert to DataFrame with columns: step, event, count, conversion_rate."""
        if self._df_cache is not None:
            return self._df_cache

        rows: list[dict[str, Any]] = []

        for i, step in enumerate(self.steps, start=1):
            rows.append(
                {
                    "step": i,
                    "event": step.event,
                    "count": step.count,
                    "conversion_rate": step.conversion_rate,
                }
            )

        result_df = (
            pd.DataFrame(rows)
            if rows
            else pd.DataFrame(columns=["step", "event", "count", "conversion_rate"])
        )

        object.__setattr__(self, "_df_cache", result_df)
        return result_df

    def to_dict(self) -> dict[str, Any]:
        """Serialize for JSON output."""
        return {
            "funnel_id": self.funnel_id,
            "funnel_name": self.funnel_name,
            "from_date": self.from_date,
            "to_date": self.to_date,
            "conversion_rate": self.conversion_rate,
            "steps": [step.to_dict() for step in self.steps],
        }


@dataclass(frozen=True)
class CohortInfo:
    """Retention data for a single cohort."""

    date: str
    """Cohort date (when users were 'born')."""

    size: int
    """Number of users in cohort."""

    retention: list[float] = field(default_factory=list)
    """Retention percentages by period (0.0 to 1.0)."""

    def to_dict(self) -> dict[str, Any]:
        """Serialize for JSON output."""
        return {
            "date": self.date,
            "size": self.size,
            "retention": self.retention,
        }


@dataclass(frozen=True)
class RetentionResult:
    """Result of a retention query.

    Contains cohort-based retention data.
    """

    born_event: str
    """Event that defines cohort membership."""

    return_event: str
    """Event that defines return."""

    from_date: str
    """Query start date."""

    to_date: str
    """Query end date."""

    unit: Literal["day", "week", "month"]
    """Time unit for retention periods."""

    cohorts: list[CohortInfo] = field(default_factory=list)
    """Cohort retention data."""

    _df_cache: pd.DataFrame | None = field(default=None, repr=False)

    @property
    def df(self) -> pd.DataFrame:
        """Convert to DataFrame with columns: cohort_date, cohort_size, period_N."""
        if self._df_cache is not None:
            return self._df_cache

        rows: list[dict[str, Any]] = []

        for cohort in self.cohorts:
            row: dict[str, Any] = {
                "cohort_date": cohort.date,
                "cohort_size": cohort.size,
            }
            for i, retention_value in enumerate(cohort.retention):
                row[f"period_{i}"] = retention_value
            rows.append(row)

        result_df = (
            pd.DataFrame(rows)
            if rows
            else pd.DataFrame(columns=["cohort_date", "cohort_size"])
        )

        object.__setattr__(self, "_df_cache", result_df)
        return result_df

    def to_dict(self) -> dict[str, Any]:
        """Serialize for JSON output."""
        return {
            "born_event": self.born_event,
            "return_event": self.return_event,
            "from_date": self.from_date,
            "to_date": self.to_date,
            "unit": self.unit,
            "cohorts": [cohort.to_dict() for cohort in self.cohorts],
        }


@dataclass(frozen=True)
class JQLResult:
    """Result of a JQL query.

    JQL (JavaScript Query Language) allows custom queries against Mixpanel data.
    """

    _raw: list[Any] = field(default_factory=list, repr=False)
    """Raw result data from JQL execution."""

    _df_cache: pd.DataFrame | None = field(default=None, repr=False)

    @property
    def raw(self) -> list[Any]:
        """Raw result data from JQL execution."""
        return self._raw

    @property
    def df(self) -> pd.DataFrame:
        """Convert result to DataFrame.

        The structure depends on the JQL query results.
        """
        if self._df_cache is not None:
            return self._df_cache

        # If raw is a list of dicts, convert directly
        if self._raw and isinstance(self._raw[0], dict):
            result_df = pd.DataFrame(self._raw)
        elif self._raw:
            # For other structures, wrap in a DataFrame
            result_df = pd.DataFrame({"value": self._raw})
        else:
            result_df = pd.DataFrame()

        object.__setattr__(self, "_df_cache", result_df)
        return result_df

    def to_dict(self) -> dict[str, Any]:
        """Serialize for JSON output."""
        return {
            "raw": self._raw,
            "row_count": len(self._raw),
        }


# Discovery Types


@dataclass(frozen=True)
class FunnelInfo:
    """A saved funnel definition.

    Represents a funnel saved in Mixpanel that can be queried
    using the funnel() method.
    """

    funnel_id: int
    """Unique identifier for funnel queries."""

    name: str
    """Human-readable funnel name."""

    def to_dict(self) -> dict[str, Any]:
        """Serialize for JSON output."""
        return {
            "funnel_id": self.funnel_id,
            "name": self.name,
        }


@dataclass(frozen=True)
class SavedCohort:
    """A saved cohort definition.

    Represents a user cohort saved in Mixpanel for profile filtering.
    """

    id: int
    """Unique identifier for profile filtering."""

    name: str
    """Human-readable cohort name."""

    count: int
    """Current number of users in cohort."""

    description: str
    """Optional description (may be empty string)."""

    created: str
    """Creation timestamp (YYYY-MM-DD HH:mm:ss)."""

    is_visible: bool
    """Whether cohort is visible in Mixpanel UI."""

    def to_dict(self) -> dict[str, Any]:
        """Serialize for JSON output."""
        return {
            "id": self.id,
            "name": self.name,
            "count": self.count,
            "description": self.description,
            "created": self.created,
            "is_visible": self.is_visible,
        }


@dataclass(frozen=True)
class TopEvent:
    """Today's event activity data.

    Represents an event's current activity including count and trend.
    """

    event: str
    """Event name."""

    count: int
    """Today's event count."""

    percent_change: float
    """Change vs yesterday (-1.0 to +infinity)."""

    def to_dict(self) -> dict[str, Any]:
        """Serialize for JSON output."""
        return {
            "event": self.event,
            "count": self.count,
            "percent_change": self.percent_change,
        }


@dataclass(frozen=True)
class EventCountsResult:
    """Time-series event count data.

    Contains aggregate counts for multiple events over time with
    lazy DataFrame conversion support.
    """

    events: list[str]
    """Queried event names."""

    from_date: str
    """Query start date (YYYY-MM-DD)."""

    to_date: str
    """Query end date (YYYY-MM-DD)."""

    unit: Literal["day", "week", "month"]
    """Time unit for aggregation."""

    type: Literal["general", "unique", "average"]
    """Counting method used."""

    series: dict[str, dict[str, int]]
    """Time series data: {event_name: {date: count}}."""

    _df_cache: pd.DataFrame | None = field(default=None, repr=False)

    @property
    def df(self) -> pd.DataFrame:
        """Convert to DataFrame with columns: date, event, count.

        Conversion is lazy - computed on first access and cached.
        """
        if self._df_cache is not None:
            return self._df_cache

        rows: list[dict[str, Any]] = []
        for event_name, date_counts in self.series.items():
            for date_str, count in date_counts.items():
                rows.append(
                    {
                        "date": date_str,
                        "event": event_name,
                        "count": count,
                    }
                )

        result_df = (
            pd.DataFrame(rows)
            if rows
            else pd.DataFrame(columns=["date", "event", "count"])
        )

        object.__setattr__(self, "_df_cache", result_df)
        return result_df

    def to_dict(self) -> dict[str, Any]:
        """Serialize for JSON output."""
        return {
            "events": self.events,
            "from_date": self.from_date,
            "to_date": self.to_date,
            "unit": self.unit,
            "type": self.type,
            "series": self.series,
        }


@dataclass(frozen=True)
class PropertyCountsResult:
    """Time-series property value distribution data.

    Contains aggregate counts by property values over time with
    lazy DataFrame conversion support.
    """

    event: str
    """Queried event name."""

    property_name: str
    """Property used for segmentation."""

    from_date: str
    """Query start date (YYYY-MM-DD)."""

    to_date: str
    """Query end date (YYYY-MM-DD)."""

    unit: Literal["day", "week", "month"]
    """Time unit for aggregation."""

    type: Literal["general", "unique", "average"]
    """Counting method used."""

    series: dict[str, dict[str, int]]
    """Time series data: {property_value: {date: count}}."""

    _df_cache: pd.DataFrame | None = field(default=None, repr=False)

    @property
    def df(self) -> pd.DataFrame:
        """Convert to DataFrame with columns: date, value, count.

        Conversion is lazy - computed on first access and cached.
        """
        if self._df_cache is not None:
            return self._df_cache

        rows: list[dict[str, Any]] = []
        for value, date_counts in self.series.items():
            for date_str, count in date_counts.items():
                rows.append(
                    {
                        "date": date_str,
                        "value": value,
                        "count": count,
                    }
                )

        result_df = (
            pd.DataFrame(rows)
            if rows
            else pd.DataFrame(columns=["date", "value", "count"])
        )

        object.__setattr__(self, "_df_cache", result_df)
        return result_df

    def to_dict(self) -> dict[str, Any]:
        """Serialize for JSON output."""
        return {
            "event": self.event,
            "property_name": self.property_name,
            "from_date": self.from_date,
            "to_date": self.to_date,
            "unit": self.unit,
            "type": self.type,
            "series": self.series,
        }


# Phase 008: Query Service Enhancement Types


@dataclass(frozen=True)
class UserEvent:
    """Single event in a user's activity feed.

    Represents one event from a user's event history with timestamp
    and all associated properties.
    """

    event: str
    """Event name."""

    time: datetime
    """Event timestamp (UTC)."""

    properties: dict[str, Any] = field(default_factory=dict)
    """All event properties including system properties."""

    def to_dict(self) -> dict[str, Any]:
        """Serialize for JSON output."""
        return {
            "event": self.event,
            "time": self.time.isoformat(),
            "properties": self.properties,
        }


@dataclass(frozen=True)
class ActivityFeedResult:
    """Collection of user events from activity feed query.

    Contains chronological event history for one or more users
    with lazy DataFrame conversion support.
    """

    distinct_ids: list[str]
    """Queried user identifiers."""

    from_date: str | None
    """Start date filter (YYYY-MM-DD), None if not specified."""

    to_date: str | None
    """End date filter (YYYY-MM-DD), None if not specified."""

    events: list[UserEvent] = field(default_factory=list)
    """Event history (chronological order)."""

    _df_cache: pd.DataFrame | None = field(default=None, repr=False)

    @property
    def df(self) -> pd.DataFrame:
        """Convert to DataFrame with columns: event, time, distinct_id, + properties.

        Flattens event properties into individual columns.
        Conversion is lazy - computed on first access and cached.
        """
        if self._df_cache is not None:
            return self._df_cache

        rows: list[dict[str, Any]] = []
        for user_event in self.events:
            row: dict[str, Any] = {
                "event": user_event.event,
                "time": user_event.time,
                "distinct_id": user_event.properties.get("$distinct_id", ""),
            }
            # Flatten properties (excluding $distinct_id to avoid duplication)
            for key, value in user_event.properties.items():
                if key != "$distinct_id":
                    row[key] = value
            rows.append(row)

        result_df = (
            pd.DataFrame(rows)
            if rows
            else pd.DataFrame(columns=["event", "time", "distinct_id"])
        )

        object.__setattr__(self, "_df_cache", result_df)
        return result_df

    def to_dict(self) -> dict[str, Any]:
        """Serialize for JSON output."""
        return {
            "distinct_ids": self.distinct_ids,
            "from_date": self.from_date,
            "to_date": self.to_date,
            "event_count": len(self.events),
            "events": [e.to_dict() for e in self.events],
        }


@dataclass(frozen=True)
class InsightsResult:
    """Data from a saved Insights report.

    Contains time-series data from a pre-configured Insights report
    with lazy DataFrame conversion support.
    """

    bookmark_id: int
    """Saved report identifier."""

    computed_at: str
    """When report was computed (ISO format)."""

    from_date: str
    """Report start date."""

    to_date: str
    """Report end date."""

    headers: list[str] = field(default_factory=list)
    """Report column headers."""

    series: dict[str, dict[str, int]] = field(default_factory=dict)
    """Time-series data: {event_name: {date: count}}."""

    _df_cache: pd.DataFrame | None = field(default=None, repr=False)

    @property
    def df(self) -> pd.DataFrame:
        """Convert to DataFrame with columns: date, event, count.

        Conversion is lazy - computed on first access and cached.
        """
        if self._df_cache is not None:
            return self._df_cache

        rows: list[dict[str, Any]] = []
        for event_name, date_counts in self.series.items():
            for date_str, count in date_counts.items():
                rows.append(
                    {
                        "date": date_str,
                        "event": event_name,
                        "count": count,
                    }
                )

        result_df = (
            pd.DataFrame(rows)
            if rows
            else pd.DataFrame(columns=["date", "event", "count"])
        )

        object.__setattr__(self, "_df_cache", result_df)
        return result_df

    def to_dict(self) -> dict[str, Any]:
        """Serialize for JSON output."""
        return {
            "bookmark_id": self.bookmark_id,
            "computed_at": self.computed_at,
            "from_date": self.from_date,
            "to_date": self.to_date,
            "headers": self.headers,
            "series": self.series,
        }


@dataclass(frozen=True)
class FrequencyResult:
    """Event frequency distribution (addiction analysis).

    Contains frequency arrays showing how many users performed events
    in N time periods, with lazy DataFrame conversion support.
    """

    event: str | None
    """Filtered event name (None = all events)."""

    from_date: str
    """Query start date (YYYY-MM-DD)."""

    to_date: str
    """Query end date (YYYY-MM-DD)."""

    unit: Literal["day", "week", "month"]
    """Overall time period."""

    addiction_unit: Literal["hour", "day"]
    """Measurement granularity."""

    data: dict[str, list[int]] = field(default_factory=dict)
    """Frequency arrays: {date: [count_1, count_2, ...]}."""

    _df_cache: pd.DataFrame | None = field(default=None, repr=False)

    @property
    def df(self) -> pd.DataFrame:
        """Convert to DataFrame with columns: date, period_1, period_2, ...

        Each period_N column shows users active in at least N time periods.
        Conversion is lazy - computed on first access and cached.
        """
        if self._df_cache is not None:
            return self._df_cache

        rows: list[dict[str, Any]] = []
        for date_str, counts in self.data.items():
            row: dict[str, Any] = {"date": date_str}
            for i, count in enumerate(counts, start=1):
                row[f"period_{i}"] = count
            rows.append(row)

        result_df = pd.DataFrame(rows) if rows else pd.DataFrame(columns=["date"])

        object.__setattr__(self, "_df_cache", result_df)
        return result_df

    def to_dict(self) -> dict[str, Any]:
        """Serialize for JSON output."""
        return {
            "event": self.event,
            "from_date": self.from_date,
            "to_date": self.to_date,
            "unit": self.unit,
            "addiction_unit": self.addiction_unit,
            "data": self.data,
        }


@dataclass(frozen=True)
class NumericBucketResult:
    """Events segmented into numeric property ranges.

    Contains time-series data bucketed by automatically determined
    numeric ranges, with lazy DataFrame conversion support.
    """

    event: str
    """Queried event name."""

    from_date: str
    """Query start date (YYYY-MM-DD)."""

    to_date: str
    """Query end date (YYYY-MM-DD)."""

    property_expr: str
    """The 'on' expression used for bucketing."""

    unit: Literal["hour", "day"]
    """Time aggregation unit."""

    series: dict[str, dict[str, int]] = field(default_factory=dict)
    """Bucket data: {range_string: {date: count}}."""

    _df_cache: pd.DataFrame | None = field(default=None, repr=False)

    @property
    def df(self) -> pd.DataFrame:
        """Convert to DataFrame with columns: date, bucket, count.

        Conversion is lazy - computed on first access and cached.
        """
        if self._df_cache is not None:
            return self._df_cache

        rows: list[dict[str, Any]] = []
        for bucket, date_counts in self.series.items():
            for date_str, count in date_counts.items():
                rows.append(
                    {
                        "date": date_str,
                        "bucket": bucket,
                        "count": count,
                    }
                )

        result_df = (
            pd.DataFrame(rows)
            if rows
            else pd.DataFrame(columns=["date", "bucket", "count"])
        )

        object.__setattr__(self, "_df_cache", result_df)
        return result_df

    def to_dict(self) -> dict[str, Any]:
        """Serialize for JSON output."""
        return {
            "event": self.event,
            "from_date": self.from_date,
            "to_date": self.to_date,
            "property_expr": self.property_expr,
            "unit": self.unit,
            "series": self.series,
        }


@dataclass(frozen=True)
class NumericSumResult:
    """Sum of numeric property values per time unit.

    Contains daily or hourly sum totals for a numeric property
    with lazy DataFrame conversion support.
    """

    event: str
    """Queried event name."""

    from_date: str
    """Query start date (YYYY-MM-DD)."""

    to_date: str
    """Query end date (YYYY-MM-DD)."""

    property_expr: str
    """The 'on' expression summed."""

    unit: Literal["hour", "day"]
    """Time aggregation unit."""

    results: dict[str, float] = field(default_factory=dict)
    """Sum values: {date: sum}."""

    computed_at: str | None = None
    """Computation timestamp (if provided by API)."""

    _df_cache: pd.DataFrame | None = field(default=None, repr=False)

    @property
    def df(self) -> pd.DataFrame:
        """Convert to DataFrame with columns: date, sum.

        Conversion is lazy - computed on first access and cached.
        """
        if self._df_cache is not None:
            return self._df_cache

        rows: list[dict[str, Any]] = [
            {"date": date_str, "sum": value} for date_str, value in self.results.items()
        ]

        result_df = (
            pd.DataFrame(rows) if rows else pd.DataFrame(columns=["date", "sum"])
        )

        object.__setattr__(self, "_df_cache", result_df)
        return result_df

    def to_dict(self) -> dict[str, Any]:
        """Serialize for JSON output."""
        result: dict[str, Any] = {
            "event": self.event,
            "from_date": self.from_date,
            "to_date": self.to_date,
            "property_expr": self.property_expr,
            "unit": self.unit,
            "results": self.results,
        }
        if self.computed_at is not None:
            result["computed_at"] = self.computed_at
        return result


@dataclass(frozen=True)
class NumericAverageResult:
    """Average of numeric property values per time unit.

    Contains daily or hourly average values for a numeric property
    with lazy DataFrame conversion support.
    """

    event: str
    """Queried event name."""

    from_date: str
    """Query start date (YYYY-MM-DD)."""

    to_date: str
    """Query end date (YYYY-MM-DD)."""

    property_expr: str
    """The 'on' expression averaged."""

    unit: Literal["hour", "day"]
    """Time aggregation unit."""

    results: dict[str, float] = field(default_factory=dict)
    """Average values: {date: average}."""

    _df_cache: pd.DataFrame | None = field(default=None, repr=False)

    @property
    def df(self) -> pd.DataFrame:
        """Convert to DataFrame with columns: date, average.

        Conversion is lazy - computed on first access and cached.
        """
        if self._df_cache is not None:
            return self._df_cache

        rows: list[dict[str, Any]] = [
            {"date": date_str, "average": value}
            for date_str, value in self.results.items()
        ]

        result_df = (
            pd.DataFrame(rows) if rows else pd.DataFrame(columns=["date", "average"])
        )

        object.__setattr__(self, "_df_cache", result_df)
        return result_df

    def to_dict(self) -> dict[str, Any]:
        """Serialize for JSON output."""
        return {
            "event": self.event,
            "from_date": self.from_date,
            "to_date": self.to_date,
            "property_expr": self.property_expr,
            "unit": self.unit,
            "results": self.results,
        }


# Storage Types


@dataclass(frozen=True)
class TableMetadata:
    """Metadata for a data fetch operation.

    This metadata is passed to table creation methods and stored in the
    database's internal _metadata table for tracking fetch operations.
    """

    type: Literal["events", "profiles"]
    """Type of data fetched."""

    fetched_at: datetime
    """When the fetch completed (UTC)."""

    from_date: str | None = None
    """Start date for events (YYYY-MM-DD), None for profiles."""

    to_date: str | None = None
    """End date for events (YYYY-MM-DD), None for profiles."""

    filter_events: list[str] | None = None
    """Event names filtered (if applicable)."""

    filter_where: str | None = None
    """WHERE clause filter (if applicable)."""

    def to_dict(self) -> dict[str, Any]:
        """Serialize for JSON output."""
        return {
            "type": self.type,
            "fetched_at": self.fetched_at.isoformat(),
            "from_date": self.from_date,
            "to_date": self.to_date,
            "filter_events": self.filter_events,
            "filter_where": self.filter_where,
        }


@dataclass(frozen=True)
class TableInfo:
    """Information about a table in the database.

    Returned by list_tables() to provide summary information about
    available tables without retrieving full schemas.
    """

    name: str
    """Table name."""

    type: Literal["events", "profiles"]
    """Table type."""

    row_count: int
    """Number of rows."""

    fetched_at: datetime
    """When data was fetched (UTC)."""

    def to_dict(self) -> dict[str, Any]:
        """Serialize for JSON output."""
        return {
            "name": self.name,
            "type": self.type,
            "row_count": self.row_count,
            "fetched_at": self.fetched_at.isoformat(),
        }


@dataclass(frozen=True)
class ColumnInfo:
    """Information about a table column.

    Describes a single column's schema, including name, type,
    nullability constraints, and primary key status.
    """

    name: str
    """Column name."""

    type: str
    """DuckDB type (VARCHAR, TIMESTAMP, JSON, INTEGER, etc.)."""

    nullable: bool
    """Whether column allows NULL values."""

    primary_key: bool = False
    """Whether column is a primary key."""

    def to_dict(self) -> dict[str, Any]:
        """Serialize for JSON output."""
        return {
            "name": self.name,
            "type": self.type,
            "nullable": self.nullable,
            "primary_key": self.primary_key,
        }


@dataclass(frozen=True)
class TableSchema:
    """Schema information for a table.

    Returned by get_schema() to describe the structure of a table,
    including all column definitions.
    """

    table_name: str
    """Table name."""

    columns: list[ColumnInfo]
    """Column definitions."""

    def to_dict(self) -> dict[str, Any]:
        """Serialize for JSON output."""
        return {
            "table_name": self.table_name,
            "columns": [col.to_dict() for col in self.columns],
        }
