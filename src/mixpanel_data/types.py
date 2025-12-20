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
