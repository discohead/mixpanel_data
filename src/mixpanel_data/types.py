"""Result types for mixpanel_data operations.

All result types are immutable frozen dataclasses with:
- Lazy DataFrame conversion via the `df` property (computed once, then cached)
- JSON serialization via the `to_dict()` method (all values JSON-serializable)
- Full type hints for IDE/mypy support

Immutability: These dataclasses are frozen, meaning their attributes cannot be
modified after construction. This ensures data integrity and thread-safety.
If you need to modify a result, create a new instance with the desired values.

DataFrame caching: The `.df` property computes the DataFrame on first access
and caches it internally. Subsequent accesses return the cached DataFrame
without recomputation.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

import pandas as pd

# =============================================================================
# Bookmark Type Aliases (Phase 015)
# =============================================================================

BookmarkType = Literal["insights", "funnels", "retention", "flows", "launch-analysis"]
"""Bookmark type values from the Mixpanel Bookmarks API.

Valid values:
    - insights: Standard metrics/events reports
    - funnels: Funnel conversion reports
    - retention: Cohort retention reports
    - flows: User path/navigation reports
    - launch-analysis: Impact/experiment reports
"""

SavedReportType = Literal["insights", "retention", "funnel"]
"""Report type detected from saved report query results.

Derived from headers array in the API response:
    - retention: Headers contain "$retention"
    - funnel: Headers contain "$funnel"
    - insights: Default when no special headers present
"""


# =============================================================================
# SQL Query Result Type
# =============================================================================


@dataclass(frozen=True)
class SQLResult:
    """Result from a SQL query with column metadata.

    Provides structured access to SQL query results including column names
    and row data. Supports conversion to list of dicts for JSON serialization
    and CLI output formatting.

    Attributes:
        columns: List of column names from the query.
        rows: List of row tuples containing the data.

    Example:
        ```python
        result = ws.sql_rows("SELECT name, age FROM users")
        print(result.columns)  # ['name', 'age']
        for row in result.rows:
            print(dict(zip(result.columns, row)))

        # Or convert to dicts directly:
        for row in result.to_dicts():
            print(row)  # {'name': 'Alice', 'age': 30}
        ```
    """

    columns: list[str]
    """List of column names from the query."""

    rows: list[tuple[Any, ...]]
    """List of row tuples containing the data."""

    def to_dicts(self) -> list[dict[str, Any]]:
        """Convert rows to list of dicts with column names as keys.

        Returns:
            List of dictionaries, one per row, with column names as keys.

        Example:
            ```python
            result = SQLResult(columns=["x", "y"], rows=[(1, 2), (3, 4)])
            dicts = result.to_dicts()
            # [{"x": 1, "y": 2}, {"x": 3, "y": 4}]
            ```
        """
        return [dict(zip(self.columns, row, strict=True)) for row in self.rows]

    def to_dict(self) -> dict[str, Any]:
        """Serialize result for JSON output.

        Returns:
            Dictionary with columns, rows (as lists), and row_count.
        """
        return {
            "columns": self.columns,
            "rows": [list(row) for row in self.rows],
            "row_count": len(self.rows),
        }

    def __len__(self) -> int:
        """Return number of rows.

        Returns:
            Count of rows in the result.
        """
        return len(self.rows)

    def __iter__(self) -> Iterator[tuple[Any, ...]]:
        """Iterate over rows.

        Yields:
            Row tuples from the result.
        """
        return iter(self.rows)


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
class BookmarkInfo:
    """Metadata for a saved report (bookmark) from the Mixpanel Bookmarks API.

    Represents a saved Insights, Funnel, Retention, or Flows report
    that can be queried using query_saved_report() or query_flows().

    Attributes:
        id: Unique bookmark identifier.
        name: User-defined report name.
        type: Report type (insights, funnels, retention, flows, launch-analysis).
        project_id: Parent Mixpanel project ID.
        created: Creation timestamp (ISO format).
        modified: Last modification timestamp (ISO format).
        workspace_id: Optional workspace ID if scoped to a workspace.
        dashboard_id: Optional parent dashboard ID if linked to a dashboard.
        description: Optional user-provided description.
        creator_id: Optional creator's user ID.
        creator_name: Optional creator's display name.
    """

    id: int
    """Unique bookmark identifier."""

    name: str
    """User-defined report name."""

    type: BookmarkType
    """Report type."""

    project_id: int
    """Parent Mixpanel project ID."""

    created: str
    """Creation timestamp (ISO format)."""

    modified: str
    """Last modification timestamp (ISO format)."""

    workspace_id: int | None = None
    """Workspace ID if scoped to a workspace."""

    dashboard_id: int | None = None
    """Parent dashboard ID if linked to a dashboard."""

    description: str | None = None
    """User-provided description."""

    creator_id: int | None = None
    """Creator's user ID."""

    creator_name: str | None = None
    """Creator's display name."""

    def to_dict(self) -> dict[str, Any]:
        """Serialize for JSON output.

        Returns:
            Dictionary with all bookmark metadata fields.
        """
        result: dict[str, Any] = {
            "id": self.id,
            "name": self.name,
            "type": self.type,
            "project_id": self.project_id,
            "created": self.created,
            "modified": self.modified,
        }
        if self.workspace_id is not None:
            result["workspace_id"] = self.workspace_id
        if self.dashboard_id is not None:
            result["dashboard_id"] = self.dashboard_id
        if self.description is not None:
            result["description"] = self.description
        if self.creator_id is not None:
            result["creator_id"] = self.creator_id
        if self.creator_name is not None:
            result["creator_name"] = self.creator_name
        return result


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
    """Time series data by property value.

    Structure: {property_value: {date: count}}
    Example: {"US": {"2024-01-01": 150, "2024-01-02": 200}, "EU": {...}}
    """

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
class SavedReportResult:
    """Data from a saved report (Insights, Retention, or Funnel).

    Contains data from a pre-configured saved report with automatic
    report type detection and lazy DataFrame conversion support.

    The report_type property automatically detects the report type based on
    headers: "$retention" indicates retention, "$funnel" indicates funnel,
    otherwise it's an insights report.

    Attributes:
        bookmark_id: Saved report identifier.
        computed_at: When report was computed (ISO format).
        from_date: Report start date.
        to_date: Report end date.
        headers: Report column headers (used for type detection).
        series: Report data (structure varies by report type).
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
    """Report column headers (used for type detection)."""

    series: dict[str, Any] = field(default_factory=dict)
    """Report data (structure varies by report type).

    For Insights reports: {event_name: {date: count}}
    For Retention reports: {series_name: {date: {segment: {first, counts, rates}}}}
    For Funnel reports: {count: {...}, overall_conv_ratio: {...}, ...}
    """

    _df_cache: pd.DataFrame | None = field(default=None, repr=False)

    @property
    def report_type(self) -> SavedReportType:
        """Detect the report type from headers.

        Returns:
            'retention' if headers contain '$retention',
            'funnel' if headers contain '$funnel',
            'insights' otherwise.
        """
        for header in self.headers:
            if "$retention" in header.lower():
                return "retention"
            if "$funnel" in header.lower():
                return "funnel"
        return "insights"

    @property
    def df(self) -> pd.DataFrame:
        """Convert to DataFrame.

        For Insights reports: columns are date, event, count.
        For Retention/Funnel reports: flattens the nested structure.

        Conversion is lazy - computed on first access and cached.
        """
        if self._df_cache is not None:
            return self._df_cache

        rows: list[dict[str, Any]] = []
        report_type = self.report_type

        if report_type == "insights":
            # Insights: {event_name: {date: count}}
            for event_name, date_counts in self.series.items():
                if isinstance(date_counts, dict):
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
        else:
            # Retention and funnel reports have complex nested structures that vary
            # by report configuration. We preserve the full structure for direct
            # access via .series property. Users can navigate the nested dict as
            # needed for their specific report type.
            result_df = pd.DataFrame([{"series": self.series}])

        object.__setattr__(self, "_df_cache", result_df)
        return result_df

    def to_dict(self) -> dict[str, Any]:
        """Serialize for JSON output.

        Returns:
            Dictionary with all report fields including detected report_type.
        """
        return {
            "bookmark_id": self.bookmark_id,
            "computed_at": self.computed_at,
            "from_date": self.from_date,
            "to_date": self.to_date,
            "headers": self.headers,
            "series": self.series,
            "report_type": self.report_type,
        }


# Backward compatibility alias (will be removed in future version)
InsightsResult = SavedReportResult


@dataclass(frozen=True)
class FlowsResult:
    """Data from a saved Flows report.

    Contains user path/navigation data from a pre-configured Flows report
    with lazy DataFrame conversion support.

    Attributes:
        bookmark_id: Saved report identifier.
        computed_at: When report was computed (ISO format).
        steps: Flow step data with event sequences and counts.
        breakdowns: Path breakdown data showing user flow distribution.
        overall_conversion_rate: End-to-end conversion rate (0.0 to 1.0).
        metadata: Additional API metadata from the response.
    """

    bookmark_id: int
    """Saved report identifier."""

    computed_at: str
    """When report was computed (ISO format)."""

    steps: list[dict[str, Any]] = field(default_factory=list)
    """Flow step data with event sequences and counts."""

    breakdowns: list[dict[str, Any]] = field(default_factory=list)
    """Path breakdown data showing user flow distribution."""

    overall_conversion_rate: float = 0.0
    """End-to-end conversion rate (0.0 to 1.0)."""

    metadata: dict[str, Any] = field(default_factory=dict)
    """Additional API metadata from the response."""

    _df_cache: pd.DataFrame | None = field(default=None, repr=False)

    @property
    def df(self) -> pd.DataFrame:
        """Convert steps to DataFrame.

        Returns DataFrame with columns derived from step data structure.
        Conversion is lazy - computed on first access and cached.
        """
        if self._df_cache is not None:
            return self._df_cache

        result_df = pd.DataFrame(self.steps) if self.steps else pd.DataFrame()

        object.__setattr__(self, "_df_cache", result_df)
        return result_df

    def to_dict(self) -> dict[str, Any]:
        """Serialize for JSON output.

        Returns:
            Dictionary with all flows report fields.
        """
        return {
            "bookmark_id": self.bookmark_id,
            "computed_at": self.computed_at,
            "steps": self.steps,
            "breakdowns": self.breakdowns,
            "overall_conversion_rate": self.overall_conversion_rate,
            "metadata": self.metadata,
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
    """Frequency arrays by date.

    Structure: {date: [count_1, count_2, ...]}
    Example: {"2024-01-01": [100, 50, 25, 10]}

    Each array shows user counts by frequency:
    - Index 0: users active exactly 1 time
    - Index 1: users active exactly 2 times
    - Index N: users active exactly N+1 times
    """

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

    filter_cohort_id: str | None = None
    """Cohort ID filter for profiles (if applicable)."""

    filter_output_properties: list[str] | None = None
    """Property names to include in output (if applicable)."""

    def to_dict(self) -> dict[str, Any]:
        """Serialize for JSON output."""
        return {
            "type": self.type,
            "fetched_at": self.fetched_at.isoformat(),
            "from_date": self.from_date,
            "to_date": self.to_date,
            "filter_events": self.filter_events,
            "filter_where": self.filter_where,
            "filter_cohort_id": self.filter_cohort_id,
            "filter_output_properties": self.filter_output_properties,
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


# Workspace Types


@dataclass(frozen=True)
class WorkspaceInfo:
    """Information about a Workspace instance.

    Returned by Workspace.info() to provide metadata about the workspace
    including database location, connection details, and table summary.
    """

    path: Path | None
    """Database file path (None for ephemeral or in-memory workspaces)."""

    project_id: str
    """Mixpanel project ID."""

    region: str
    """Data residency region (us, eu, in)."""

    account: str | None
    """Named account used (None if credentials from environment)."""

    tables: list[str]
    """Names of tables in the database."""

    size_mb: float
    """Database file size in megabytes (0.0 for in-memory workspaces)."""

    created_at: datetime | None
    """When database was created (None if unknown)."""

    def to_dict(self) -> dict[str, Any]:
        """Serialize for JSON output."""
        return {
            "path": str(self.path) if self.path else None,
            "project_id": self.project_id,
            "region": self.region,
            "account": self.account,
            "tables": self.tables,
            "size_mb": self.size_mb,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


# Lexicon Schemas Types

EntityType = Literal["event", "profile"]
"""Type alias for Lexicon entity types accepted as input parameters.

Valid input types:
    - event: Standard tracked events
    - profile: User profile properties

Note: The Mixpanel API may return additional entity types in responses
(custom_event, group, lookup, collect_everything_event) which are accepted
but not supported as input filters.
"""


@dataclass(frozen=True)
class LexiconMetadata:
    """Mixpanel-specific metadata for Lexicon schemas and properties.

    Contains platform-specific information about how schemas and properties
    are displayed and organized in the Mixpanel UI.
    """

    source: str | None
    """Origin of the schema definition (e.g., 'api', 'csv', 'ui')."""

    display_name: str | None
    """Human-readable display name in Mixpanel UI."""

    tags: list[str]
    """Categorization tags for organization."""

    hidden: bool
    """Whether hidden from Mixpanel UI."""

    dropped: bool
    """Whether data is dropped/ignored."""

    contacts: list[str]
    """Owner email addresses."""

    team_contacts: list[str]
    """Team ownership labels."""

    def to_dict(self) -> dict[str, Any]:
        """Serialize for JSON output.

        Returns:
            Dictionary with all metadata fields.
        """
        return {
            "source": self.source,
            "display_name": self.display_name,
            "tags": self.tags,
            "hidden": self.hidden,
            "dropped": self.dropped,
            "contacts": self.contacts,
            "team_contacts": self.team_contacts,
        }


@dataclass(frozen=True)
class LexiconProperty:
    """Schema definition for a single property in a Lexicon schema.

    Describes the type and metadata for an event or profile property.
    """

    type: str
    """JSON Schema type (string, number, boolean, array, object, integer, null)."""

    description: str | None
    """Human-readable description of the property."""

    metadata: LexiconMetadata | None
    """Optional Mixpanel-specific metadata."""

    def to_dict(self) -> dict[str, Any]:
        """Serialize for JSON output.

        Returns:
            Dictionary with type, and optionally description and metadata.
        """
        result: dict[str, Any] = {"type": self.type}
        if self.description is not None:
            result["description"] = self.description
        if self.metadata is not None:
            result["metadata"] = self.metadata.to_dict()
        return result


@dataclass(frozen=True)
class LexiconDefinition:
    """Full schema definition for an event or profile property in Lexicon.

    Contains the structural definition including description, properties,
    and platform-specific metadata.
    """

    description: str | None
    """Human-readable description of the entity."""

    properties: dict[str, LexiconProperty]
    """Property definitions keyed by property name."""

    metadata: LexiconMetadata | None
    """Optional Mixpanel-specific metadata for the entity."""

    def to_dict(self) -> dict[str, Any]:
        """Serialize for JSON output.

        Returns:
            Dictionary with properties, and optionally description and metadata.
        """
        result: dict[str, Any] = {
            "properties": {k: v.to_dict() for k, v in self.properties.items()},
        }
        if self.description is not None:
            result["description"] = self.description
        if self.metadata is not None:
            result["metadata"] = self.metadata.to_dict()
        return result


@dataclass(frozen=True)
class LexiconSchema:
    """Complete schema definition from Mixpanel Lexicon.

    Represents a documented event or profile property definition
    from the Mixpanel data dictionary.
    """

    entity_type: str
    """Type of entity (e.g., 'event', 'profile', 'custom_event', 'group', etc.)."""

    name: str
    """Name of the event or profile property."""

    schema_json: LexiconDefinition
    """Full schema definition."""

    def to_dict(self) -> dict[str, Any]:
        """Serialize for JSON output.

        Returns:
            Dictionary with entity_type, name, and schema_json.
        """
        return {
            "entity_type": self.entity_type,
            "name": self.name,
            "schema_json": self.schema_json.to_dict(),
        }


# Introspection Types


@dataclass(frozen=True)
class ColumnSummary:
    """Statistical summary of a single column from DuckDB's SUMMARIZE command.

    Contains per-column statistics including min/max, quartiles, null percentage,
    and approximate distinct counts. Numeric columns include additional stats
    like average and standard deviation.
    """

    column_name: str
    """Name of the column."""

    column_type: str
    """DuckDB data type (VARCHAR, TIMESTAMP, INTEGER, JSON, etc.)."""

    min: Any
    """Minimum value (type varies by column type)."""

    max: Any
    """Maximum value (type varies by column type)."""

    approx_unique: int
    """Approximate count of distinct values (HyperLogLog)."""

    avg: float | None
    """Mean value (None for non-numeric columns)."""

    std: float | None
    """Standard deviation (None for non-numeric columns)."""

    q25: Any
    """25th percentile value (None for non-numeric)."""

    q50: Any
    """Median / 50th percentile (None for non-numeric)."""

    q75: Any
    """75th percentile value (None for non-numeric)."""

    count: int
    """Number of non-null values."""

    null_percentage: float
    """Percentage of null values (0.0 to 100.0)."""

    def to_dict(self) -> dict[str, Any]:
        """Serialize for JSON output.

        Returns:
            Dictionary with all column statistics.
        """
        return {
            "column_name": self.column_name,
            "column_type": self.column_type,
            "min": self.min,
            "max": self.max,
            "approx_unique": self.approx_unique,
            "avg": self.avg,
            "std": self.std,
            "q25": self.q25,
            "q50": self.q50,
            "q75": self.q75,
            "count": self.count,
            "null_percentage": self.null_percentage,
        }


@dataclass(frozen=True)
class SummaryResult:
    """Statistical summary of all columns in a table.

    Contains row count and per-column statistics from DuckDB's SUMMARIZE command.
    Provides both structured access via the columns list and DataFrame conversion
    via the df property.
    """

    table: str
    """Name of the summarized table."""

    row_count: int
    """Total number of rows in the table."""

    columns: list[ColumnSummary] = field(default_factory=list)
    """Per-column statistics."""

    _df_cache: pd.DataFrame | None = field(default=None, repr=False)

    @property
    def df(self) -> pd.DataFrame:
        """Convert to DataFrame with one row per column.

        Conversion is lazy - computed on first access and cached.

        Returns:
            DataFrame with column statistics.
        """
        if self._df_cache is not None:
            return self._df_cache

        rows: list[dict[str, Any]] = [col.to_dict() for col in self.columns]

        result_df = (
            pd.DataFrame(rows)
            if rows
            else pd.DataFrame(
                columns=[
                    "column_name",
                    "column_type",
                    "min",
                    "max",
                    "approx_unique",
                    "avg",
                    "std",
                    "q25",
                    "q50",
                    "q75",
                    "count",
                    "null_percentage",
                ]
            )
        )

        object.__setattr__(self, "_df_cache", result_df)
        return result_df

    def to_dict(self) -> dict[str, Any]:
        """Serialize for JSON output.

        Returns:
            Dictionary with table name, row count, and column statistics.
        """
        return {
            "table": self.table,
            "row_count": self.row_count,
            "columns": [col.to_dict() for col in self.columns],
        }


@dataclass(frozen=True)
class EventStats:
    """Statistics for a single event type.

    Contains count, unique users, date range, and percentage of total
    for a specific event in an events table.
    """

    event_name: str
    """Name of the event."""

    count: int
    """Total occurrences of this event."""

    unique_users: int
    """Count of distinct users who triggered this event."""

    first_seen: datetime
    """Earliest occurrence timestamp."""

    last_seen: datetime
    """Latest occurrence timestamp."""

    pct_of_total: float
    """Percentage of all events (0.0 to 100.0)."""

    def to_dict(self) -> dict[str, Any]:
        """Serialize for JSON output.

        Returns:
            Dictionary with event statistics (datetimes as ISO strings).
        """
        return {
            "event_name": self.event_name,
            "count": self.count,
            "unique_users": self.unique_users,
            "first_seen": self.first_seen.isoformat(),
            "last_seen": self.last_seen.isoformat(),
            "pct_of_total": self.pct_of_total,
        }


@dataclass(frozen=True)
class EventBreakdownResult:
    """Distribution of events in a table.

    Contains aggregate statistics and per-event breakdown with counts,
    unique users, date ranges, and percentages.
    """

    table: str
    """Name of the analyzed table."""

    total_events: int
    """Total number of events in the table."""

    total_users: int
    """Total distinct users across all events."""

    date_range: tuple[datetime, datetime]
    """(earliest, latest) event timestamps."""

    events: list[EventStats] = field(default_factory=list)
    """Per-event statistics, ordered by count descending."""

    _df_cache: pd.DataFrame | None = field(default=None, repr=False)

    @property
    def df(self) -> pd.DataFrame:
        """Convert to DataFrame with one row per event type.

        Conversion is lazy - computed on first access and cached.

        Returns:
            DataFrame with event statistics.
        """
        if self._df_cache is not None:
            return self._df_cache

        rows: list[dict[str, Any]] = []
        for event in self.events:
            rows.append(
                {
                    "event_name": event.event_name,
                    "count": event.count,
                    "unique_users": event.unique_users,
                    "first_seen": event.first_seen,
                    "last_seen": event.last_seen,
                    "pct_of_total": event.pct_of_total,
                }
            )

        result_df = (
            pd.DataFrame(rows)
            if rows
            else pd.DataFrame(
                columns=[
                    "event_name",
                    "count",
                    "unique_users",
                    "first_seen",
                    "last_seen",
                    "pct_of_total",
                ]
            )
        )

        object.__setattr__(self, "_df_cache", result_df)
        return result_df

    def to_dict(self) -> dict[str, Any]:
        """Serialize for JSON output.

        Returns:
            Dictionary with table info and event statistics.
        """
        return {
            "table": self.table,
            "total_events": self.total_events,
            "total_users": self.total_users,
            "date_range": [
                self.date_range[0].isoformat(),
                self.date_range[1].isoformat(),
            ],
            "events": [event.to_dict() for event in self.events],
        }


@dataclass(frozen=True)
class ColumnStatsResult:
    """Deep statistical analysis of a single column.

    Provides detailed statistics including null rates, cardinality,
    top values, and numeric statistics (for numeric columns).
    Supports JSON path expressions for analyzing properties.
    """

    table: str
    """Name of the source table."""

    column: str
    """Column expression analyzed (may include JSON path)."""

    dtype: str
    """DuckDB data type of the column."""

    count: int
    """Number of non-null values."""

    null_count: int
    """Number of null values."""

    null_pct: float
    """Percentage of null values (0.0 to 100.0)."""

    unique_count: int
    """Approximate count of distinct values."""

    unique_pct: float
    """Percentage of values that are unique (0.0 to 100.0)."""

    top_values: list[tuple[Any, int]] = field(default_factory=list)
    """Most frequent (value, count) pairs."""

    min: float | None = None
    """Minimum value (None for non-numeric)."""

    max: float | None = None
    """Maximum value (None for non-numeric)."""

    mean: float | None = None
    """Mean value (None for non-numeric)."""

    std: float | None = None
    """Standard deviation (None for non-numeric)."""

    _df_cache: pd.DataFrame | None = field(default=None, repr=False)

    @property
    def df(self) -> pd.DataFrame:
        """Convert top values to DataFrame with columns: value, count.

        Conversion is lazy - computed on first access and cached.

        Returns:
            DataFrame with top values and their counts.
        """
        if self._df_cache is not None:
            return self._df_cache

        rows: list[dict[str, Any]] = [
            {"value": value, "count": count} for value, count in self.top_values
        ]

        result_df = (
            pd.DataFrame(rows) if rows else pd.DataFrame(columns=["value", "count"])
        )

        object.__setattr__(self, "_df_cache", result_df)
        return result_df

    def to_dict(self) -> dict[str, Any]:
        """Serialize for JSON output.

        Returns:
            Dictionary with all column statistics.
        """
        return {
            "table": self.table,
            "column": self.column,
            "dtype": self.dtype,
            "count": self.count,
            "null_count": self.null_count,
            "null_pct": self.null_pct,
            "unique_count": self.unique_count,
            "unique_pct": self.unique_pct,
            "top_values": [[value, count] for value, count in self.top_values],
            "min": self.min,
            "max": self.max,
            "mean": self.mean,
            "std": self.std,
        }


# =============================================================================
# JQL-Based Discovery Types (Phase 016)
# =============================================================================


@dataclass(frozen=True)
class PropertyValueCount:
    """A single value and its count from property distribution analysis.

    Represents one row in a property value distribution, showing the value,
    its occurrence count, and percentage of total.

    Attributes:
        value: The property value (can be string, number, bool, or None).
        count: Number of occurrences of this value.
        percentage: Percentage of total events (0.0 to 100.0).
    """

    value: str | int | float | bool | None
    """The property value."""

    count: int
    """Number of occurrences."""

    percentage: float
    """Percentage of total (0.0 to 100.0)."""

    def to_dict(self) -> dict[str, Any]:
        """Serialize for JSON output.

        Returns:
            Dictionary with value, count, and percentage.
        """
        return {
            "value": self.value,
            "count": self.count,
            "percentage": self.percentage,
        }


@dataclass(frozen=True)
class PropertyDistributionResult:
    """Distribution of values for a property from JQL analysis.

    Contains the top N values for a property with their counts and percentages,
    enabling quick understanding of property value distribution without fetching
    all data locally.

    Attributes:
        event: The event type analyzed.
        property_name: The property name analyzed.
        from_date: Query start date (YYYY-MM-DD).
        to_date: Query end date (YYYY-MM-DD).
        total_count: Total number of events with this property defined.
        values: Top values with counts and percentages.
    """

    event: str
    """Event type analyzed."""

    property_name: str
    """Property name analyzed."""

    from_date: str
    """Query start date (YYYY-MM-DD)."""

    to_date: str
    """Query end date (YYYY-MM-DD)."""

    total_count: int
    """Total events with this property defined."""

    values: tuple[PropertyValueCount, ...]
    """Top values with counts and percentages."""

    _df_cache: pd.DataFrame | None = field(default=None, repr=False)

    @property
    def df(self) -> pd.DataFrame:
        """Convert to DataFrame with columns: value, count, percentage.

        Conversion is lazy - computed on first access and cached.

        Returns:
            DataFrame with value distribution data.
        """
        if self._df_cache is not None:
            return self._df_cache

        rows: list[dict[str, Any]] = [v.to_dict() for v in self.values]

        result_df = (
            pd.DataFrame(rows)
            if rows
            else pd.DataFrame(columns=["value", "count", "percentage"])
        )

        object.__setattr__(self, "_df_cache", result_df)
        return result_df

    def to_dict(self) -> dict[str, Any]:
        """Serialize for JSON output.

        Returns:
            Dictionary with all distribution data.
        """
        return {
            "event": self.event,
            "property_name": self.property_name,
            "from_date": self.from_date,
            "to_date": self.to_date,
            "total_count": self.total_count,
            "values": [v.to_dict() for v in self.values],
        }


@dataclass(frozen=True)
class NumericPropertySummaryResult:
    """Statistical summary of a numeric property from JQL analysis.

    Contains min, max, sum, average, standard deviation, and percentiles
    for a numeric property, enabling understanding of value distributions
    without fetching all data locally.

    Attributes:
        event: The event type analyzed.
        property_name: The property name analyzed.
        from_date: Query start date (YYYY-MM-DD).
        to_date: Query end date (YYYY-MM-DD).
        count: Number of events with this property defined.
        min: Minimum value.
        max: Maximum value.
        sum: Sum of all values.
        avg: Average value.
        stddev: Standard deviation.
        percentiles: Percentile values keyed by percentile number.
    """

    event: str
    """Event type analyzed."""

    property_name: str
    """Property name analyzed."""

    from_date: str
    """Query start date (YYYY-MM-DD)."""

    to_date: str
    """Query end date (YYYY-MM-DD)."""

    count: int
    """Number of events with this property defined."""

    min: float
    """Minimum value."""

    max: float
    """Maximum value."""

    sum: float
    """Sum of all values."""

    avg: float
    """Average value."""

    stddev: float
    """Standard deviation."""

    percentiles: dict[int, float]
    """Percentile values keyed by percentile number (e.g., {50: 98.0})."""

    def to_dict(self) -> dict[str, Any]:
        """Serialize for JSON output.

        Returns:
            Dictionary with all numeric summary data.
        """
        return {
            "event": self.event,
            "property_name": self.property_name,
            "from_date": self.from_date,
            "to_date": self.to_date,
            "count": self.count,
            "min": self.min,
            "max": self.max,
            "sum": self.sum,
            "avg": self.avg,
            "stddev": self.stddev,
            "percentiles": {str(k): v for k, v in self.percentiles.items()},
        }


@dataclass(frozen=True)
class DailyCount:
    """Event count for a single date from daily counts analysis.

    Represents one row in a daily counts result, showing date, event, and count.

    Attributes:
        date: Date string (YYYY-MM-DD).
        event: Event name.
        count: Number of occurrences on this date.
    """

    date: str
    """Date string (YYYY-MM-DD)."""

    event: str
    """Event name."""

    count: int
    """Number of occurrences."""

    def to_dict(self) -> dict[str, Any]:
        """Serialize for JSON output.

        Returns:
            Dictionary with date, event, and count.
        """
        return {
            "date": self.date,
            "event": self.event,
            "count": self.count,
        }


@dataclass(frozen=True)
class DailyCountsResult:
    """Time-series event counts by day from JQL analysis.

    Contains daily event counts for quick activity trend analysis
    without complex segmentation setup.

    Attributes:
        from_date: Query start date (YYYY-MM-DD).
        to_date: Query end date (YYYY-MM-DD).
        events: Event types included (None for all events).
        counts: Daily counts for each event.
    """

    from_date: str
    """Query start date (YYYY-MM-DD)."""

    to_date: str
    """Query end date (YYYY-MM-DD)."""

    events: tuple[str, ...] | None
    """Event types included (None for all events)."""

    counts: tuple[DailyCount, ...]
    """Daily counts for each event."""

    _df_cache: pd.DataFrame | None = field(default=None, repr=False)

    @property
    def df(self) -> pd.DataFrame:
        """Convert to DataFrame with columns: date, event, count.

        Conversion is lazy - computed on first access and cached.

        Returns:
            DataFrame with daily counts data.
        """
        if self._df_cache is not None:
            return self._df_cache

        rows: list[dict[str, Any]] = [c.to_dict() for c in self.counts]

        result_df = (
            pd.DataFrame(rows)
            if rows
            else pd.DataFrame(columns=["date", "event", "count"])
        )

        object.__setattr__(self, "_df_cache", result_df)
        return result_df

    def to_dict(self) -> dict[str, Any]:
        """Serialize for JSON output.

        Returns:
            Dictionary with all daily counts data.
        """
        return {
            "from_date": self.from_date,
            "to_date": self.to_date,
            "events": list(self.events) if self.events else None,
            "counts": [c.to_dict() for c in self.counts],
        }


@dataclass(frozen=True)
class EngagementBucket:
    """User count in an engagement bucket from engagement analysis.

    Represents one bucket in a user engagement distribution, showing
    how many users performed events in a certain frequency range.

    Attributes:
        bucket_min: Minimum events in this bucket.
        bucket_label: Human-readable label (e.g., "1", "2-5", "100+").
        user_count: Number of users in this bucket.
        percentage: Percentage of total users (0.0 to 100.0).
    """

    bucket_min: int
    """Minimum events in this bucket."""

    bucket_label: str
    """Human-readable label (e.g., '1', '2-5', '100+')."""

    user_count: int
    """Number of users in this bucket."""

    percentage: float
    """Percentage of total users (0.0 to 100.0)."""

    def to_dict(self) -> dict[str, Any]:
        """Serialize for JSON output.

        Returns:
            Dictionary with bucket data.
        """
        return {
            "bucket_min": self.bucket_min,
            "bucket_label": self.bucket_label,
            "user_count": self.user_count,
            "percentage": self.percentage,
        }


@dataclass(frozen=True)
class EngagementDistributionResult:
    """User engagement distribution from JQL analysis.

    Shows how many users performed N events, helping understand
    user engagement patterns without fetching all data locally.

    Attributes:
        from_date: Query start date (YYYY-MM-DD).
        to_date: Query end date (YYYY-MM-DD).
        events: Event types included (None for all events).
        total_users: Total number of distinct users.
        buckets: Engagement buckets with user counts.
    """

    from_date: str
    """Query start date (YYYY-MM-DD)."""

    to_date: str
    """Query end date (YYYY-MM-DD)."""

    events: tuple[str, ...] | None
    """Event types included (None for all events)."""

    total_users: int
    """Total number of distinct users."""

    buckets: tuple[EngagementBucket, ...]
    """Engagement buckets with user counts."""

    _df_cache: pd.DataFrame | None = field(default=None, repr=False)

    @property
    def df(self) -> pd.DataFrame:
        """Convert to DataFrame with engagement bucket columns.

        Conversion is lazy - computed on first access and cached.

        Returns:
            DataFrame with engagement distribution data.
        """
        if self._df_cache is not None:
            return self._df_cache

        rows: list[dict[str, Any]] = [b.to_dict() for b in self.buckets]

        result_df = (
            pd.DataFrame(rows)
            if rows
            else pd.DataFrame(
                columns=["bucket_min", "bucket_label", "user_count", "percentage"]
            )
        )

        object.__setattr__(self, "_df_cache", result_df)
        return result_df

    def to_dict(self) -> dict[str, Any]:
        """Serialize for JSON output.

        Returns:
            Dictionary with all engagement distribution data.
        """
        return {
            "from_date": self.from_date,
            "to_date": self.to_date,
            "events": list(self.events) if self.events else None,
            "total_users": self.total_users,
            "buckets": [b.to_dict() for b in self.buckets],
        }


@dataclass(frozen=True)
class PropertyCoverage:
    """Coverage statistics for a single property from coverage analysis.

    Shows how often a property is defined vs null for a given event type.

    Attributes:
        property: Property name.
        defined_count: Number of events with this property defined.
        null_count: Number of events with this property null/undefined.
        coverage_percentage: Percentage of events with property defined (0.0-100.0).
    """

    property: str
    """Property name."""

    defined_count: int
    """Number of events with property defined."""

    null_count: int
    """Number of events with property null/undefined."""

    coverage_percentage: float
    """Percentage with property defined (0.0 to 100.0)."""

    def to_dict(self) -> dict[str, Any]:
        """Serialize for JSON output.

        Returns:
            Dictionary with coverage data.
        """
        return {
            "property": self.property,
            "defined_count": self.defined_count,
            "null_count": self.null_count,
            "coverage_percentage": self.coverage_percentage,
        }


@dataclass(frozen=True)
class PropertyCoverageResult:
    """Property coverage analysis result from JQL.

    Shows which properties are consistently populated vs sparse,
    helping understand data quality before writing queries.

    Attributes:
        event: The event type analyzed.
        from_date: Query start date (YYYY-MM-DD).
        to_date: Query end date (YYYY-MM-DD).
        total_events: Total number of events analyzed.
        coverage: Coverage statistics for each property.
    """

    event: str
    """Event type analyzed."""

    from_date: str
    """Query start date (YYYY-MM-DD)."""

    to_date: str
    """Query end date (YYYY-MM-DD)."""

    total_events: int
    """Total number of events analyzed."""

    coverage: tuple[PropertyCoverage, ...]
    """Coverage statistics for each property."""

    _df_cache: pd.DataFrame | None = field(default=None, repr=False)

    @property
    def df(self) -> pd.DataFrame:
        """Convert to DataFrame with property coverage columns.

        Conversion is lazy - computed on first access and cached.

        Returns:
            DataFrame with property coverage data.
        """
        if self._df_cache is not None:
            return self._df_cache

        rows: list[dict[str, Any]] = [c.to_dict() for c in self.coverage]

        result_df = (
            pd.DataFrame(rows)
            if rows
            else pd.DataFrame(
                columns=[
                    "property",
                    "defined_count",
                    "null_count",
                    "coverage_percentage",
                ]
            )
        )

        object.__setattr__(self, "_df_cache", result_df)
        return result_df

    def to_dict(self) -> dict[str, Any]:
        """Serialize for JSON output.

        Returns:
            Dictionary with all coverage data.
        """
        return {
            "event": self.event,
            "from_date": self.from_date,
            "to_date": self.to_date,
            "total_events": self.total_events,
            "coverage": [c.to_dict() for c in self.coverage],
        }
