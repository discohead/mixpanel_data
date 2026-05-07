"""Result types for mixpanel_headless operations.

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

import copy
import json
import math
import re
import warnings
from dataclasses import dataclass, field
from datetime import date as dt_date
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Annotated, Any, Generic, Literal, TypedDict, TypeVar

from mixpanel_headless._literal_types import (
    CohortAggregationType as CohortAggregationType,
)
from mixpanel_headless._literal_types import (
    ConversionWindowUnit as ConversionWindowUnit,
)
from mixpanel_headless._literal_types import CustomPropertyType as CustomPropertyType
from mixpanel_headless._literal_types import FilterDateUnit as FilterDateUnit
from mixpanel_headless._literal_types import FilterOperator as FilterOperator
from mixpanel_headless._literal_types import FilterPropertyType as FilterPropertyType
from mixpanel_headless._literal_types import FiltersCombinator as FiltersCombinator
from mixpanel_headless._literal_types import (
    FlowAnchorType,
    FlowNodeType,
    FlowSessionEvent,
)
from mixpanel_headless._literal_types import FlowChartType as FlowChartType
from mixpanel_headless._literal_types import (
    FlowConversionWindowUnit as FlowConversionWindowUnit,
)
from mixpanel_headless._literal_types import (
    FrequencyFilterOperator as FrequencyFilterOperator,
)
from mixpanel_headless._literal_types import FunnelMathType as FunnelMathType
from mixpanel_headless._literal_types import FunnelMode as FunnelMode
from mixpanel_headless._literal_types import FunnelOrder as FunnelOrder
from mixpanel_headless._literal_types import InsightsMode as InsightsMode
from mixpanel_headless._literal_types import MathType as MathType
from mixpanel_headless._literal_types import PerUserAggregation as PerUserAggregation
from mixpanel_headless._literal_types import RetentionAlignment as RetentionAlignment
from mixpanel_headless._literal_types import RetentionMathType as RetentionMathType
from mixpanel_headless._literal_types import RetentionMode as RetentionMode
from mixpanel_headless._literal_types import SegmentMethod as SegmentMethod
from mixpanel_headless._literal_types import TimeComparisonType as TimeComparisonType
from mixpanel_headless._literal_types import TimeComparisonUnit as TimeComparisonUnit
from mixpanel_headless.auth_types import (
    AccountName,
    AccountType,
    ProjectId,
    Region,
    TargetName,
    WorkspaceId,
)

if TYPE_CHECKING:
    import networkx as nx
import pandas as pd
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    computed_field,
    field_validator,
    model_validator,
)
from pydantic.alias_generators import to_camel

T = TypeVar("T")

# =============================================================================
# Query API Type Aliases and Constants (Phase 029)
# =============================================================================

# MathType, PerUserAggregation, FilterPropertyType, FilterDateUnit are
# re-exported from _literal_types (imported above) for backward compatibility.

# =============================================================================
# Base Class for Result Types with DataFrame Conversion
# =============================================================================


@dataclass(frozen=True)
class ResultWithDataFrame:
    """Base class for result types with lazy DataFrame conversion and table output.

    This base class provides common functionality for result types that:
    1. Store data in nested dict/list structures
    2. Support conversion to normalized DataFrames via a `df` property
    3. Need readable table output for CLI `--format table` option

    Attributes:
        _df_cache: Internal cache for lazy DataFrame conversion. Not part of
            the public API. Subclasses should not access this directly.
            This field is keyword-only to allow subclasses to define required
            fields without defaults.

    Methods:
        df: Property that must be implemented by subclasses to return a
            normalized DataFrame.
        to_table_dict: Converts the DataFrame to a list of dicts suitable
            for table formatting.

    Usage:
        Subclasses must implement the `df` property to normalize their data
        into a flat DataFrame structure. The base class handles caching and
        table serialization automatically.

    Example:
        ```python
        @dataclass(frozen=True)
        class MyResult(ResultWithDataFrame):
            data: dict[str, dict[str, int]]

            @property
            def df(self) -> pd.DataFrame:
                if self._df_cache is not None:
                    return self._df_cache

                rows = [{"key": k, "date": d, "count": c}
                        for k, dates in self.data.items()
                        for d, c in dates.items()]
                result_df = pd.DataFrame(rows)
                object.__setattr__(self, "_df_cache", result_df)
                return result_df

        result = MyResult(data={"A": {"2024-01-01": 10}})
        result.to_table_dict()
        # [{"key": "A", "date": "2024-01-01", "count": 10}]
        ```
    """

    _df_cache: pd.DataFrame | None = field(default=None, repr=False, kw_only=True)

    @property
    def df(self) -> pd.DataFrame:
        """Convert result data to normalized DataFrame.

        This property must be implemented by subclasses to convert their
        specific data structure into a flat, normalized DataFrame suitable
        for analysis and table display.

        The implementation should:
        1. Check if _df_cache is not None and return it (for performance)
        2. Build rows as list[dict[str, Any]] from the result's data
        3. Create a DataFrame from the rows (or empty DataFrame with columns)
        4. Cache the result using object.__setattr__(self, "_df_cache", result_df)
        5. Return the DataFrame

        Returns:
            Normalized DataFrame with flat columns suitable for analysis.
            Column names should be lowercase, descriptive, and consistent
            across result types where possible (e.g., "date", "count", "event").

        Raises:
            NotImplementedError: If subclass doesn't implement this property.

        Example:
            ```python
            df = result.df
            df.columns
            # Index(['date', 'segment', 'count'], dtype='object')
            ```
        """
        raise NotImplementedError(
            f"{self.__class__.__name__} must implement df property"
        )

    def to_table_dict(self) -> list[dict[str, Any]]:
        """Convert DataFrame rows to list of dicts for table formatting.

        This method uses the `df` property which normalizes nested data
        structures into flat tabular form, then converts to a list of
        records (one dict per row). This provides readable output for
        CLI `--format table` option.

        The normalized table format is much more readable than displaying
        nested dict/list structures as JSON blobs in table cells.

        Returns:
            List of dictionaries with normalized row data, one dict per row.
            Each dict has keys matching the DataFrame column names.
            Returns empty list if DataFrame is empty.

        Example:
            Without to_table_dict (unreadable table):
                ┃ SERIES                                              ┃
                ┃ {"US": {"2024-01-01": 100, "2024-01-02": 150}, ...} ┃

            With to_table_dict (readable table):
                ┃ DATE       ┃ SEGMENT ┃ COUNT ┃
                ┃ 2024-01-01 ┃ US      ┃ 100   ┃
                ┃ 2024-01-02 ┃ US      ┃ 150   ┃

        Note:
            This method is used automatically by CLI commands when
            `--format table` is specified. For other formats (json, jsonl, csv),
            use the `to_dict()` method which preserves the original structure.
        """
        from typing import cast

        df = self.df
        if df.empty:
            return []

        # Cast required because pandas to_dict("records") returns
        # list[dict[Hashable, Any]] but we know our columns are strings
        return cast(list[dict[str, Any]], df.to_dict("records"))


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

SavedReportType = Literal["insights", "retention", "funnel", "flows"]
"""Report type detected from saved report query results.

Derived from headers array in the API response:
    - retention: Headers contain "$retention"
    - funnel: Headers contain "$funnel"
    - flows: Headers contain "$flows"
    - insights: Default when no special headers present
"""


@dataclass(frozen=True)
class SegmentationResult(ResultWithDataFrame):
    """Result of a segmentation query.

    Contains time-series data for an event, optionally segmented by a property.

    Inherits from ResultWithDataFrame to provide:
    - Lazy DataFrame caching via _df_cache field
    - Normalized table output via to_table_dict() method
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
class FunnelResultStep:
    """Single step result in a legacy funnel query response."""

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
class FunnelResult(ResultWithDataFrame):
    """Result of a funnel query.

    Contains step-by-step conversion data for a funnel.

    Inherits from ResultWithDataFrame to provide:
    - Lazy DataFrame caching via _df_cache field
    - Normalized table output via to_table_dict() method
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

    steps: list[FunnelResultStep] = field(default_factory=list)
    """Step-by-step breakdown."""

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
class RetentionResult(ResultWithDataFrame):
    """Result of a retention query.

    Contains cohort-based retention data.

    Inherits from ResultWithDataFrame to provide:
    - Lazy DataFrame caching via _df_cache field
    - Normalized table output via to_table_dict() method
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
class JQLResult(ResultWithDataFrame):
    """Result of a JQL query.

    JQL (JavaScript Query Language) allows custom queries against Mixpanel data.

    Inherits from ResultWithDataFrame to provide:
    - Lazy DataFrame caching via _df_cache field
    - Normalized table output via to_table_dict() method

    The df property intelligently detects JQL result patterns (groupBy, percentiles,
    simple dicts) and converts them to clean tabular format.
    """

    _raw: list[Any] = field(default_factory=list, repr=False)
    """Raw result data from JQL execution."""

    @property
    def raw(self) -> list[Any]:
        """Raw result data from JQL execution."""
        return self._raw

    @property
    def df(self) -> pd.DataFrame:
        """Convert result to DataFrame with intelligent structure detection.

        The conversion strategy depends on the detected JQL result pattern:

        **groupBy results** (detected by {key: [...], value: X} structure):
            - Keys expanded to columns: key_0, key_1, key_2, ...
            - Single value: "value" column
            - Multiple reducers (value array): value_0, value_1, value_2, ...
            - Additional fields (from .map()): preserved as-is
            - Example: {"key": ["US"], "value": 100, "name": "USA"}
              -> columns: key_0, value, name

        **Nested percentile results** ([[{percentile: X, value: Y}, ...]]):
            - Outer list unwrapped, inner dicts converted directly

        **Simple list of dicts** (already well-structured):
            - Converted directly to DataFrame preserving all fields

        **Fallback for other structures** (scalars, mixed types, incompatible dicts):
            - Safely wrapped in single "value" column to prevent data loss
            - Used when structure doesn't match known patterns

        Raises:
            ValueError: If groupBy structure has inconsistent value types across rows
                (some scalar, some array) which indicates malformed query results.

        Returns:
            DataFrame representation, cached after first access.
        """
        if self._df_cache is not None:
            return self._df_cache

        result_df = self._convert_to_dataframe(self._raw)
        object.__setattr__(self, "_df_cache", result_df)
        return result_df

    def _convert_to_dataframe(self, raw: list[Any]) -> pd.DataFrame:
        """Convert raw JQL results to DataFrame.

        Args:
            raw: Raw JQL result data.

        Returns:
            DataFrame representation.
        """
        if not raw:
            return pd.DataFrame()

        # Detect groupBy structure: {key: [...], value: X}
        if self._is_groupby_structure(raw):
            return self._expand_groupby_structure(raw)

        # Special case: nested list of dicts (e.g., from percentiles after flatten)
        # Structure: [[{percentile: 50, value: 118}, ...]]
        if (
            len(raw) == 1
            and isinstance(raw[0], list)
            and raw[0]
            and isinstance(raw[0][0], dict)
        ):
            return pd.DataFrame(raw[0])

        # Handle list of dicts (already good structure or after .map())
        # But first check if ALL items are dicts to avoid pandas errors
        if isinstance(raw[0], dict) and all(isinstance(item, dict) for item in raw):
            try:
                return pd.DataFrame(raw)
            except (ValueError, TypeError):
                # Mixed dict structures, wrap safely
                return pd.DataFrame({"value": raw})

        # For other structures (lists, scalars, mixed types), wrap in value column
        return pd.DataFrame({"value": raw})

    def _is_groupby_structure(self, raw: list[Any]) -> bool:
        """Check if raw data has groupBy structure {key: [...], value: X}.

        Validates that ALL elements match the pattern to prevent KeyError
        during expansion. Allows additional fields (e.g., from .map()).

        Args:
            raw: Raw JQL result data.

        Returns:
            True if ALL elements match groupBy pattern.
        """
        if not raw:
            return False

        # Check ALL elements for consistent structure
        return all(
            isinstance(item, dict)
            and set(item.keys()) >= {"key", "value"}  # Allow additional fields!
            and isinstance(item.get("key"), list)
            for item in raw
        )

    def _expand_groupby_structure(self, raw: list[dict[str, Any]]) -> pd.DataFrame:
        """Expand groupBy {key: [...], value: X} structure to columns.

        Preserves additional fields (e.g., from .map()) and validates
        value type consistency across all rows.

        Args:
            raw: List of groupBy result objects.

        Returns:
            DataFrame with expanded key and value columns.

        Raises:
            ValueError: If value types are inconsistent across rows.
        """
        # Validate consistent value types
        value_is_list = [isinstance(item["value"], list) for item in raw]
        if not (all(value_is_list) or not any(value_is_list)):
            raise ValueError(
                "Inconsistent value types in groupBy results: "
                "some rows have scalar values, others have arrays. "
                "This typically indicates a malformed JQL query result."
            )

        rows = []
        for item in raw:
            row_dict: dict[str, Any] = {}

            # FIRST: Preserve all additional fields (anything except key/value)
            for k, v in item.items():
                if k not in {"key", "value"}:
                    row_dict[k] = v

            # THEN: Expand key array into key_0, key_1, key_2, ...
            keys = item["key"]
            for i, key_val in enumerate(keys):
                row_dict[f"key_{i}"] = key_val

            # THEN: Handle value - could be scalar or array (multiple reducers)
            value = item["value"]
            if isinstance(value, list):
                # Multiple reducers: expand to value_0, value_1, value_2
                for i, val in enumerate(value):
                    row_dict[f"value_{i}"] = val
            else:
                # Single reducer: just "value"
                row_dict["value"] = value

            rows.append(row_dict)

        return pd.DataFrame(rows)

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
    that can be queried using query_saved_report() or query_saved_flows().

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
class SubPropertyInfo:
    """Discovered subproperty of a list-of-object event property.

    Returned by :meth:`Workspace.subproperties` to describe the inner
    structure of properties whose values are lists of objects (e.g.
    ``cart`` is a list of ``{"Brand": str, "Category": str, "Price":
    int}`` items). Use the ``name`` and ``type`` to construct
    :meth:`GroupBy.list_item` and :meth:`Filter.list_contains` calls.

    Attributes:
        name: Subproperty name as it appears inside each object.
        type: Inferred data type. Mixed sub-value types collapse to
            ``"string"`` (a ``UserWarning`` is emitted at discovery
            time).
        sample_values: Up to 5 distinct sample values observed across
            the sampled rows.

    Example:
        ```python
        for sp in ws.subproperties("cart", event="Cart Viewed"):
            print(sp.name, sp.type, sp.sample_values)
        # Brand string ('nike', 'puma', 'h&m')
        # Category string ('hats', 'jeans', 'shoes')
        # Item ID number (35317, 35318)
        # Price number (51, 87, 102)
        ```
    """

    name: str
    """Subproperty name as it appears inside each object."""

    type: CustomPropertyType
    """Inferred data type, suitable for ``GroupBy.list_item(sub_type=...)``."""

    sample_values: tuple[str | int | float | bool, ...]
    """Up to 5 distinct sample values observed across the sampled rows."""

    def to_dict(self) -> dict[str, Any]:
        """Serialize the subproperty info as a plain dict for JSON output.

        Returns:
            Dict with ``name`` (str), ``type`` (str), and
            ``sample_values`` (list of scalars) keys, suitable for
            JSON serialization.
        """
        return {
            "name": self.name,
            "type": self.type,
            "sample_values": list(self.sample_values),
        }


@dataclass(frozen=True)
class TopEvent:
    """Today's event activity data.

    Represents an event's current activity including count and trend.

    Attributes:
        event: Event name.
        count: Today's event count.
        percent_change: Change vs yesterday (-1.0 to +infinity).

    Example:
        ```python
        top = ws.top_events(limit=10)
        for t in top:
            print(f"{t.event}: {t.count:,} ({t.percent_change:+.1%})")
        ```
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
class EventCountsResult(ResultWithDataFrame):
    """Time-series event count data.

    Contains aggregate counts for multiple events over time with
    lazy DataFrame conversion support.

    Inherits from ResultWithDataFrame to provide:
    - Lazy DataFrame caching via _df_cache field
    - Normalized table output via to_table_dict() method
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
class PropertyCountsResult(ResultWithDataFrame):
    """Time-series property value distribution data.

    Contains aggregate counts by property values over time with
    lazy DataFrame conversion support.

    Inherits from ResultWithDataFrame to provide:
    - Lazy DataFrame caching via _df_cache field
    - Normalized table output via to_table_dict() method
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
class ActivityFeedResult(ResultWithDataFrame):
    """Collection of user events from activity feed query.

    Contains chronological event history for one or more users
    with lazy DataFrame conversion support.

    Inherits from ResultWithDataFrame to provide:
    - Lazy DataFrame caching via _df_cache field
    - Normalized table output via to_table_dict() method
    """

    distinct_ids: list[str]
    """Queried user identifiers."""

    from_date: str | None
    """Start date filter (YYYY-MM-DD), None if not specified."""

    to_date: str | None
    """End date filter (YYYY-MM-DD), None if not specified."""

    events: list[UserEvent] = field(default_factory=list)
    """Event history (chronological order)."""

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
            'flows' if headers contain '$flows',
            'insights' otherwise.
        """
        for header in self.headers:
            if "$retention" in header.lower():
                return "retention"
            if "$funnel" in header.lower():
                return "funnel"
            if "$flows" in header.lower():
                return "flows"
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


@dataclass(frozen=True)
class FlowsResult(ResultWithDataFrame):
    """Data from a saved Flows report.

    Contains user path/navigation data from a pre-configured Flows report
    with lazy DataFrame conversion support.

    Inherits from ResultWithDataFrame to provide:
    - Lazy DataFrame caching via _df_cache field
    - Normalized table output via to_table_dict() method

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
class FrequencyResult(ResultWithDataFrame):
    """Event frequency distribution (addiction analysis).

    Contains frequency arrays showing how many users performed events
    in N time periods, with lazy DataFrame conversion support.

    Inherits from ResultWithDataFrame to provide:
    - Lazy DataFrame caching via _df_cache field
    - Normalized table output via to_table_dict() method
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
class NumericBucketResult(ResultWithDataFrame):
    """Events segmented into numeric property ranges.

    Contains time-series data bucketed by automatically determined
    numeric ranges, with lazy DataFrame conversion support.

    Inherits from ResultWithDataFrame to provide:
    - Lazy DataFrame caching via _df_cache field
    - Normalized table output via to_table_dict() method
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
class NumericSumResult(ResultWithDataFrame):
    """Sum of numeric property values per time unit.

    Contains daily or hourly sum totals for a numeric property
    with lazy DataFrame conversion support.

    Inherits from ResultWithDataFrame to provide:
    - Lazy DataFrame caching via _df_cache field
    - Normalized table output via to_table_dict() method
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
class NumericAverageResult(ResultWithDataFrame):
    """Average of numeric property values per time unit.

    Contains daily or hourly average values for a numeric property
    with lazy DataFrame conversion support.

    Inherits from ResultWithDataFrame to provide:
    - Lazy DataFrame caching via _df_cache field
    - Normalized table output via to_table_dict() method
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
    enabling quick understanding of property value distribution without processing
    all raw events.

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
    without processing all raw events.

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
    user engagement patterns without processing all raw events.

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


# =============================================================================
# App API Types (OAuth & Workspace Scoping)
# =============================================================================


class PublicWorkspace(BaseModel):
    """A workspace within a Mixpanel project.

    Represents a workspace as returned by the Mixpanel App API
    ``GET /api/app/projects/{pid}/workspaces/public`` endpoint.
    Extra fields from the API response are preserved via ``extra="allow"``.

    Attributes:
        id: Workspace identifier.
        name: Human-readable workspace name.
        project_id: Parent project identifier.
        is_default: Whether this is the default workspace.
        description: Workspace description, if set.
        is_global: Whether workspace is global.
        is_restricted: Whether workspace has restrictions.
        is_visible: Whether workspace is visible.
        created_iso: ISO 8601 creation timestamp.
        creator_name: Name of workspace creator.

    Example:
        ```python
        ws = PublicWorkspace(
            id=1, name="Main", project_id=12345, is_default=True
        )
        assert ws.is_default is True
        ```
    """

    model_config = ConfigDict(frozen=True, extra="allow")

    id: int
    """Workspace identifier."""

    name: str
    """Human-readable workspace name."""

    project_id: int
    """Parent project identifier."""

    is_default: bool
    """Whether this is the default workspace."""

    description: str | None = None
    """Workspace description, if set."""

    is_global: bool | None = None
    """Whether workspace is global."""

    is_restricted: bool | None = None
    """Whether workspace has restrictions."""

    is_visible: bool | None = None
    """Whether workspace is visible."""

    created_iso: str | None = None
    """ISO 8601 creation timestamp."""

    creator_name: str | None = None
    """Name of workspace creator."""


class CursorPagination(BaseModel):
    """Cursor-based pagination metadata from App API responses.

    Attributes:
        page_size: Number of items per page.
        next_cursor: Cursor for next page, or None if last page.
        previous_cursor: Cursor for previous page.

    Example:
        ```python
        pagination = CursorPagination(page_size=100, next_cursor="abc123")
        assert pagination.next_cursor == "abc123"
        ```
    """

    model_config = ConfigDict(frozen=True)

    page_size: int
    """Number of items per page."""

    next_cursor: str | None = None
    """Cursor for next page (None = last page)."""

    previous_cursor: str | None = None
    """Cursor for previous page."""


class PaginatedResponse(BaseModel, Generic[T]):
    """Paginated App API response wrapper.

    Generic wrapper for paginated responses from the Mixpanel App API.
    Contains the results list, status, and optional pagination metadata.

    Attributes:
        status: Response status (typically "ok").
        results: Page of results.
        pagination: Pagination metadata, or None for single-page responses.

    Example:
        ```python
        response = PaginatedResponse[dict](
            status="ok",
            results=[{"id": 1}],
            pagination=CursorPagination(page_size=100),
        )
        assert len(response.results) == 1
        ```
    """

    model_config = ConfigDict(frozen=True)

    status: str
    """Response status (typically "ok")."""

    results: list[T]
    """Page of results."""

    pagination: CursorPagination | None = None
    """Pagination metadata, or None for single-page responses."""


# =============================================================================
# Dashboard Types (Phase 024)
# =============================================================================


class Dashboard(BaseModel):
    """A Mixpanel dashboard as returned by the App API.

    Represents the full dashboard entity including metadata, permissions,
    and optional layout/content fields. Extra fields from API evolution
    are preserved via ``extra="allow"``.

    Attributes:
        id: Unique dashboard identifier.
        title: Dashboard title.
        description: Dashboard description.
        is_private: Whether the dashboard is private.
        is_restricted: Whether the dashboard has restricted access.
        creator_id: ID of the dashboard creator.
        creator_name: Name of the dashboard creator.
        creator_email: Email of the dashboard creator.
        created: Creation timestamp (lenient parsing).
        modified: Last modification timestamp.
        is_favorited: Whether the current user has favorited this dashboard.
        pinned_date: Date the dashboard was pinned, if any.
        layout_version: Layout version metadata.
        unique_view_count: Number of unique viewers.
        total_view_count: Total view count.
        last_modified_by_id: ID of the last modifier.
        last_modified_by_name: Name of the last modifier.
        last_modified_by_email: Email of the last modifier.
        filters: Dashboard-level filters.
        breakdowns: Dashboard-level breakdowns.
        time_filter: Dashboard-level time filter.
        generation_type: How the dashboard was generated.
        parent_dashboard_id: Parent dashboard ID for nested dashboards.
        child_dashboards: Child dashboard references.
        can_update_basic: Permission flag.
        can_share: Permission flag.
        can_view: Permission flag.
        can_update_restricted: Permission flag.
        can_update_visibility: Permission flag.
        is_superadmin: Whether current user is superadmin.
        allow_staff_override: Whether staff override is allowed.
        can_pin: Whether current user can pin.
        is_shared_with_project: Whether shared with the project.
        creator: Creator identifier string.
        ancestors: Ancestor dashboard references.
        layout: Dashboard layout data.
        contents: Dashboard contents data.
        num_active_public_links: Number of active public links.
        new_content: New content data.
        template_type: Template type if created from a template.

    Example:
        ```python
        dashboard = Dashboard(
            id=1, title="Q1 Metrics", is_private=False,
            is_restricted=False, is_favorited=False,
            can_update_basic=True, can_share=True, can_view=True,
            can_update_restricted=False, can_update_visibility=False,
            is_superadmin=False, allow_staff_override=False,
            can_pin=True, is_shared_with_project=True, ancestors=[],
        )
        assert dashboard.title == "Q1 Metrics"
        ```
    """

    model_config = ConfigDict(frozen=True, extra="allow")

    id: int
    """Unique dashboard identifier."""

    title: str
    """Dashboard title."""

    description: str | None = None
    """Dashboard description."""

    is_private: bool = False
    """Whether the dashboard is private."""

    is_restricted: bool = False
    """Whether the dashboard has restricted access."""

    creator_id: int | None = None
    """ID of the dashboard creator."""

    creator_name: str | None = None
    """Name of the dashboard creator."""

    creator_email: str | None = None
    """Email of the dashboard creator."""

    created: datetime | None = None
    """Creation timestamp."""

    modified: datetime | None = None
    """Last modification timestamp."""

    is_favorited: bool = False
    """Whether the current user has favorited this dashboard."""

    pinned_date: str | None = None
    """Date the dashboard was pinned, if any."""

    layout_version: Any | None = None
    """Layout version metadata."""

    unique_view_count: int | None = None
    """Number of unique viewers."""

    total_view_count: int | None = None
    """Total view count."""

    last_modified_by_id: int | None = None
    """ID of the last modifier."""

    last_modified_by_name: str | None = None
    """Name of the last modifier."""

    last_modified_by_email: str | None = None
    """Email of the last modifier."""

    filters: list[Any] | None = None
    """Dashboard-level filters."""

    breakdowns: list[Any] | None = None
    """Dashboard-level breakdowns."""

    time_filter: Any | None = None
    """Dashboard-level time filter."""

    generation_type: str | None = None
    """How the dashboard was generated."""

    parent_dashboard_id: int | None = None
    """Parent dashboard ID for nested dashboards."""

    child_dashboards: list[Any] | None = None
    """Child dashboard references."""

    can_update_basic: bool = False
    """Permission: can update basic fields."""

    can_share: bool = False
    """Permission: can share."""

    can_view: bool = False
    """Permission: can view."""

    can_update_restricted: bool = False
    """Permission: can update restricted fields."""

    can_update_visibility: bool = False
    """Permission: can update visibility."""

    is_superadmin: bool = False
    """Whether current user is superadmin."""

    allow_staff_override: bool = False
    """Whether staff override is allowed."""

    can_pin: bool = False
    """Whether current user can pin."""

    is_shared_with_project: bool = False
    """Whether shared with the project."""

    creator: str | None = None
    """Creator identifier string."""

    ancestors: list[Any] = Field(default_factory=list)
    """Ancestor dashboard references."""

    layout: Any | None = None
    """Dashboard layout data."""

    contents: Any | None = None
    """Dashboard contents data."""

    num_active_public_links: int | None = None
    """Number of active public links."""

    new_content: Any | None = None
    """New content data."""

    template_type: str | None = None
    """Template type if created from a template."""


class DashboardRowContent(BaseModel):
    """A single content item within a dashboard row.

    Attributes:
        content_type: Type of content — ``"text"`` or ``"report"``.
        content_params: Parameters for the content. Shape depends on
            ``content_type``:

            - **text**: ``{"markdown": "<h2>Title</h2><p>Description</p>"}``
            - **report**: ``{"bookmark": {"name": "...", "type": "insights",
              "params": json.dumps(result.params)}}``

    Example:
        ```python
        # Text card
        DashboardRowContent(
            content_type="text",
            content_params={"markdown": "<h2>Overview</h2>"},
        )

        # Report (inline bookmark)
        DashboardRowContent(
            content_type="report",
            content_params={
                "bookmark": {
                    "name": "DAU (90d)",
                    "type": "insights",
                    "params": json.dumps(result.params),
                }
            },
        )
        ```
    """

    content_type: Literal["text", "report"]
    """Type of content: ``"text"`` for text cards, ``"report"`` for reports."""

    content_params: dict[str, Any]
    """Content parameters. Shape depends on ``content_type``."""


class DashboardRow(BaseModel):
    """A row of content items for a dashboard.

    Each row can contain 1-4 content items. Items in the same row share the
    row and have their widths auto-distributed (12-column grid).

    Attributes:
        contents: List of content items in this row (max 4).

    Example:
        ```python
        # Row with 3 KPI cards (auto-distributed to width 4 each)
        DashboardRow(contents=[
            DashboardRowContent(content_type="report", content_params={
                "bookmark": {"name": "DAU", "type": "insights",
                             "params": json.dumps(dau.params)}}),
            DashboardRowContent(content_type="report", content_params={
                "bookmark": {"name": "Signups", "type": "insights",
                             "params": json.dumps(signups.params)}}),
            DashboardRowContent(content_type="report", content_params={
                "bookmark": {"name": "Purchases", "type": "insights",
                             "params": json.dumps(purchases.params)}}),
        ])
        ```
    """

    contents: list[DashboardRowContent]
    """Content items in this row (max 4)."""


class CreateDashboardParams(BaseModel):
    """Parameters for creating a new dashboard.

    Attributes:
        title: Dashboard title (required).
        description: Dashboard description.
        is_private: Whether the dashboard should be private.
        is_restricted: Whether the dashboard should have restricted access.
        filters: Dashboard-level filters.
        breakdowns: Dashboard-level breakdowns.
        time_filter: Dashboard-level time filter.
        duplicate: ID of dashboard to duplicate.
        rows: Initial dashboard content with layout. Each row contains 1-4
            content items (text cards or reports). Items in the same row are
            placed side-by-side with auto-distributed widths. This is the
            recommended way to create dashboards with proper layout — adding
            content after creation via ``update_dashboard()`` places each item
            in its own full-width row, and layout restructuring (merging items
            into shared rows) is not supported via PATCH.

    Example:
        ```python
        import json

        params = CreateDashboardParams(
            title="Product Health",
            rows=[
                DashboardRow(contents=[
                    DashboardRowContent(
                        content_type="text",
                        content_params={"markdown": "<h2>Overview</h2>"},
                    ),
                ]),
                DashboardRow(contents=[
                    DashboardRowContent(
                        content_type="report",
                        content_params={"bookmark": {
                            "name": "DAU", "type": "insights",
                            "params": json.dumps(dau_result.params),
                        }},
                    ),
                    DashboardRowContent(
                        content_type="report",
                        content_params={"bookmark": {
                            "name": "Signups", "type": "insights",
                            "params": json.dumps(signup_result.params),
                        }},
                    ),
                ]),
            ],
        )
        ```
    """

    title: str
    """Dashboard title (required)."""

    description: str | None = None
    """Dashboard description."""

    is_private: bool | None = None
    """Whether the dashboard should be private."""

    is_restricted: bool | None = None
    """Whether the dashboard should have restricted access."""

    filters: list[Any] | None = None
    """Dashboard-level filters."""

    breakdowns: list[Any] | None = None
    """Dashboard-level breakdowns."""

    time_filter: Any | None = None
    """Dashboard-level time filter."""

    duplicate: int | None = None
    """ID of dashboard to duplicate."""

    rows: list[DashboardRow] | None = None
    """Initial content rows with layout. Each row has 1-4 content items."""


class UpdateDashboardParams(BaseModel):
    """Parameters for updating an existing dashboard.

    All fields are optional — only provided fields are sent to the API.

    Attributes:
        title: New dashboard title.
        description: New dashboard description.
        is_private: New privacy setting.
        is_restricted: New restriction setting.
        filters: New dashboard-level filters.
        breakdowns: New dashboard-level breakdowns.
        time_filter: New dashboard-level time filter.
        layout: New dashboard layout data.
        content: New dashboard content data.

    Example:
        ```python
        params = UpdateDashboardParams(title="Q1 Metrics v2")
        data = params.model_dump(exclude_none=True)
        # {"title": "Q1 Metrics v2"}
        ```
    """

    title: str | None = None
    """New dashboard title."""

    description: str | None = None
    """New dashboard description."""

    is_private: bool | None = None
    """New privacy setting."""

    is_restricted: bool | None = None
    """New restriction setting."""

    filters: list[Any] | None = None
    """New dashboard-level filters."""

    breakdowns: list[Any] | None = None
    """New dashboard-level breakdowns."""

    time_filter: Any | None = None
    """New dashboard-level time filter."""

    layout: Any | None = None
    """New dashboard layout data."""

    content: Any | None = None
    """New dashboard content data."""


# =============================================================================
# Blueprint Types (Phase 024)
# =============================================================================


class BlueprintTemplate(BaseModel):
    """A dashboard blueprint template.

    Attributes:
        title_key: Template title key.
        description_key: Template description key.
        alternative_description_key: Alternative description key.
        number_of_reports: Number of reports in the template.

    Example:
        ```python
        template = BlueprintTemplate(
            title_key="onboarding", description_key="Get started"
        )
        ```
    """

    model_config = ConfigDict(frozen=True, extra="allow")

    title_key: str
    """Template title key."""

    description_key: str
    """Template description key."""

    alternative_description_key: str | None = None
    """Alternative description key."""

    number_of_reports: int | None = None
    """Number of reports in the template."""


class BlueprintConfig(BaseModel):
    """Configuration for a dashboard blueprint.

    Attributes:
        variables: Template variable mappings.

    Example:
        ```python
        config = BlueprintConfig(variables={"event": "Signup"})
        ```
    """

    model_config = ConfigDict(frozen=True, extra="allow")

    variables: dict[str, str]
    """Template variable mappings."""


class BlueprintCard(BaseModel):
    """A card in a blueprint dashboard.

    Attributes:
        card_type: Card type (serialized as ``"type"``).
        text_card_id: Text card ID, if applicable.
        bookmark_id: Bookmark ID, if applicable.
        markdown: Markdown content for text cards.
        name: Card name.
        params: Card parameters.

    Example:
        ```python
        card = BlueprintCard(card_type="report", bookmark_id=123)
        data = card.model_dump(by_alias=True, exclude_none=True)
        # {"type": "report", "bookmark_id": 123}
        ```
    """

    model_config = ConfigDict(populate_by_name=True, extra="allow")

    card_type: str = Field(alias="type")
    """Card type (serialized as ``"type"``)."""

    text_card_id: int | None = None
    """Text card ID, if applicable."""

    bookmark_id: int | None = None
    """Bookmark ID, if applicable."""

    markdown: str | None = None
    """Markdown content for text cards."""

    name: str | None = None
    """Card name."""

    params: dict[str, Any] | None = None
    """Card parameters."""


class BlueprintFinishParams(BaseModel):
    """Parameters for finalizing a blueprint dashboard.

    Attributes:
        dashboard_id: ID of the blueprint dashboard to finalize.
        cards: List of cards to include.

    Example:
        ```python
        params = BlueprintFinishParams(
            dashboard_id=1,
            cards=[BlueprintCard(card_type="report", bookmark_id=123)],
        )
        ```
    """

    dashboard_id: int
    """ID of the blueprint dashboard to finalize."""

    cards: list[BlueprintCard]
    """List of cards to include."""


class RcaSourceData(BaseModel):
    """Source data for RCA dashboard creation.

    Attributes:
        source_type: Source type (serialized as ``"type"``).
        date: Date string.
        metric_source: Whether this is a metric source.

    Example:
        ```python
        data = RcaSourceData(source_type="anomaly", date="2025-01-01")
        dumped = data.model_dump(by_alias=True, exclude_none=True)
        # {"type": "anomaly", "date": "2025-01-01"}
        ```
    """

    model_config = ConfigDict(populate_by_name=True, extra="allow")

    source_type: str = Field(alias="type")
    """Source type (serialized as ``"type"``)."""

    date: str | None = None
    """Date string."""

    metric_source: bool | None = None
    """Whether this is a metric source."""


class CreateRcaDashboardParams(BaseModel):
    """Parameters for creating an RCA dashboard.

    Attributes:
        rca_source_id: Source ID for RCA analysis.
        rca_source_data: Source data configuration.

    Example:
        ```python
        params = CreateRcaDashboardParams(
            rca_source_id=42,
            rca_source_data=RcaSourceData(source_type="anomaly"),
        )
        ```
    """

    rca_source_id: int
    """Source ID for RCA analysis."""

    rca_source_data: RcaSourceData
    """Source data configuration."""


class UpdateReportLinkParams(BaseModel):
    """Parameters for updating a report link on a dashboard.

    Attributes:
        link_type: Link type (serialized as ``"type"``).

    Example:
        ```python
        params = UpdateReportLinkParams(link_type="embedded")
        data = params.model_dump(by_alias=True, exclude_none=True)
        # {"type": "embedded"}
        ```
    """

    model_config = ConfigDict(populate_by_name=True, extra="allow")

    link_type: str = Field(alias="type")
    """Link type (serialized as ``"type"``)."""


class UpdateTextCardParams(BaseModel):
    """Parameters for updating a text card on a dashboard.

    Attributes:
        markdown: Markdown content for the text card.

    Example:
        ```python
        params = UpdateTextCardParams(markdown="# Hello")
        ```
    """

    model_config = ConfigDict(extra="allow")

    markdown: str | None = None
    """Markdown content for the text card."""


# =============================================================================
# Bookmark/Report Types (Phase 024)
# =============================================================================


# Mirrors `get_root_model_for_bookmark_type` dispatch in
# `mixpanel_headless._internal.bookmark_schema`. Pydantic rejects construction
# with any other value, catching typos like "insightz" at the API surface.
BookmarkTypeLiteral = Literal["insights", "funnels", "retention", "flows", "user"]
"""Valid bookmark/report types accepted by the Mixpanel v2 API."""


class BookmarkMetadata(BaseModel):
    """Metadata associated with a bookmark/report.

    Contains optional display and calculation settings that vary by
    bookmark type (insights, funnels, retention, etc.).

    Attributes:
        table_display_mode: Table display mode setting.
        compare_enabled: Whether comparison is enabled.
        compare_filters: Comparison filter settings.
        retention_calculation_type: Retention calculation method.
        event_name: Associated event name.
        funnel_conversion_window: Funnel conversion window in days.
        funnel_breakdown_limit: Maximum funnel breakdown count.

    Example:
        ```python
        meta = BookmarkMetadata(
            table_display_mode="linear",
            compare_enabled=True,
        )
        ```
    """

    model_config = ConfigDict(frozen=True, extra="allow")

    table_display_mode: str | None = None
    """Table display mode setting."""

    compare_enabled: bool | None = None
    """Whether comparison is enabled."""

    compare_filters: list[Any] | None = None
    """Comparison filter settings."""

    retention_calculation_type: str | None = None
    """Retention calculation method."""

    event_name: str | None = None
    """Associated event name."""

    funnel_conversion_window: int | None = None
    """Funnel conversion window in days."""

    funnel_breakdown_limit: int | None = None
    """Maximum funnel breakdown count."""


class Bookmark(BaseModel):
    """A Mixpanel bookmark (saved report) as returned by the App API.

    Represents the full bookmark entity including query parameters,
    metadata, and permissions. The ``bookmark_type`` field is aliased
    from ``"type"`` in the API response.

    Attributes:
        id: Unique bookmark identifier.
        project_id: Parent project identifier.
        name: Bookmark name.
        bookmark_type: Report type (aliased from ``"type"``).
        description: Bookmark description.
        icon: Bookmark icon.
        params: Query parameters (JSON value defining the report).
        dashboard_id: Associated dashboard ID.
        include_in_dashboard: Whether included in dashboard.
        is_default: Whether this is a default bookmark.
        creator_id: ID of the creator.
        creator_name: Name of the creator.
        creator_email: Email of the creator.
        created: Creation timestamp.
        modified: Last modification timestamp.
        last_modified_by_id: ID of the last modifier.
        last_modified_by_name: Name of the last modifier.
        last_modified_by_email: Email of the last modifier.
        metadata: Report-specific metadata.
        is_visibility_restricted: Visibility restriction flag.
        is_modification_restricted: Modification restriction flag.
        can_update_basic: Permission flag.
        can_view: Permission flag.
        can_share: Permission flag.
        generation_type: How the bookmark was generated.
        original_type: Original report type before conversion.
        unique_view_count: Number of unique viewers.
        total_view_count: Total view count.

    Example:
        ```python
        bookmark = Bookmark(
            id=1, name="Signup Funnel", bookmark_type="funnels",
            params={"events": [{"event": "Signup"}]},
        )
        assert bookmark.bookmark_type == "funnels"
        ```
    """

    model_config = ConfigDict(frozen=True, extra="allow", populate_by_name=True)

    id: int
    """Unique bookmark identifier."""

    project_id: int | None = None
    """Parent project identifier."""

    name: str
    """Bookmark name."""

    bookmark_type: str = Field(alias="type")
    """Report type (aliased from ``"type"``)."""

    description: str | None = None
    """Bookmark description."""

    icon: str | None = None
    """Bookmark icon."""

    params: dict[str, Any] | None = None
    """Query parameters (JSON value defining the report)."""

    dashboard_id: int | None = None
    """Associated dashboard ID."""

    include_in_dashboard: bool | None = None
    """Whether included in dashboard."""

    is_default: bool | None = None
    """Whether this is a default bookmark."""

    creator_id: int | None = None
    """ID of the creator."""

    creator_name: str | None = None
    """Name of the creator."""

    creator_email: str | None = None
    """Email of the creator."""

    created: datetime | None = None
    """Creation timestamp."""

    modified: datetime | None = None
    """Last modification timestamp."""

    last_modified_by_id: int | None = None
    """ID of the last modifier."""

    last_modified_by_name: str | None = None
    """Name of the last modifier."""

    last_modified_by_email: str | None = None
    """Email of the last modifier."""

    metadata: BookmarkMetadata | None = None
    """Report-specific metadata."""

    is_visibility_restricted: bool | None = None
    """Visibility restriction flag."""

    is_modification_restricted: bool | None = None
    """Modification restriction flag."""

    can_update_basic: bool | None = None
    """Permission: can update basic fields."""

    can_view: bool | None = None
    """Permission: can view."""

    can_share: bool | None = None
    """Permission: can share."""

    generation_type: str | None = None
    """How the bookmark was generated."""

    original_type: str | None = None
    """Original report type before conversion."""

    unique_view_count: int | None = None
    """Number of unique viewers."""

    total_view_count: int | None = None
    """Total view count."""


class CreateBookmarkParams(BaseModel):
    """Parameters for creating a new bookmark/report.

    Attributes:
        name: Bookmark name (required).
        bookmark_type: Report type (required, serialized as ``"type"``).
        params: Query parameters (required).
        description: Bookmark description.
        icon: Bookmark icon.
        dashboard_id: Dashboard to associate with.  Required by
            ``Workspace.create_bookmark()`` — the Mixpanel v2 API
            requires every bookmark to belong to a dashboard.
        is_visibility_restricted: Visibility restriction flag.
        is_modification_restricted: Modification restriction flag.

    Example:
        ```python
        params = CreateBookmarkParams(
            name="Signup Funnel",
            bookmark_type="funnels",
            params={"events": [{"event": "Signup"}]},
            dashboard_id=12345,
        )
        data = params.model_dump(by_alias=True, exclude_none=True)
        ```
    """

    model_config = ConfigDict(populate_by_name=True)

    name: str
    """Bookmark name (required)."""

    bookmark_type: BookmarkTypeLiteral = Field(alias="type")
    """Report type (required, serialized as ``"type"``).

    Pydantic-validated against the canonical set on construction —
    typos like ``"insightz"`` are rejected before any API call.
    """

    params: dict[str, Any]
    """Query parameters (required)."""

    description: str | None = None
    """Bookmark description."""

    icon: str | None = None
    """Bookmark icon."""

    dashboard_id: int | None = None
    """Dashboard to associate with."""

    is_visibility_restricted: bool | None = None
    """Visibility restriction flag."""

    is_modification_restricted: bool | None = None
    """Modification restriction flag."""


class UpdateBookmarkParams(BaseModel):
    """Parameters for updating an existing bookmark/report.

    All fields are optional — only provided fields are sent to the API.

    Attributes:
        name: New bookmark name.
        params: New query parameters.
        description: New bookmark description.
        icon: New bookmark icon.
        dashboard_id: New associated dashboard ID.
        is_visibility_restricted: New visibility restriction.
        is_modification_restricted: New modification restriction.
        deleted: Soft-delete flag.

    Example:
        ```python
        params = UpdateBookmarkParams(name="Updated Funnel")
        data = params.model_dump(exclude_none=True)
        # {"name": "Updated Funnel"}
        ```
    """

    name: str | None = None
    """New bookmark name."""

    params: dict[str, Any] | None = None
    """New query parameters."""

    description: str | None = None
    """New bookmark description."""

    icon: str | None = None
    """New bookmark icon."""

    dashboard_id: int | None = None
    """New associated dashboard ID."""

    is_visibility_restricted: bool | None = None
    """New visibility restriction."""

    is_modification_restricted: bool | None = None
    """New modification restriction."""

    deleted: bool | None = None
    """Soft-delete flag."""


class BulkUpdateBookmarkEntry(BaseModel):
    """Entry for bulk-updating bookmarks.

    Attributes:
        id: Bookmark ID to update (required).
        name: New bookmark name.
        params: New query parameters.
        description: New bookmark description.
        icon: New bookmark icon.
        is_visibility_restricted: New visibility restriction.
        is_modification_restricted: New modification restriction.

    Example:
        ```python
        entry = BulkUpdateBookmarkEntry(id=123, name="Renamed")
        ```
    """

    id: int
    """Bookmark ID to update (required)."""

    name: str | None = None
    """New bookmark name."""

    params: dict[str, Any] | None = None
    """New query parameters."""

    description: str | None = None
    """New bookmark description."""

    icon: str | None = None
    """New bookmark icon."""

    is_visibility_restricted: bool | None = None
    """New visibility restriction."""

    is_modification_restricted: bool | None = None
    """New modification restriction."""


class BookmarkHistoryPagination(BaseModel):
    """Pagination metadata for bookmark history responses.

    Attributes:
        next_cursor: Cursor for next page.
        previous_cursor: Cursor for previous page.
        page_size: Number of items per page.

    Example:
        ```python
        pagination = BookmarkHistoryPagination(page_size=20)
        ```
    """

    model_config = ConfigDict(frozen=True, extra="allow")

    next_cursor: str | None = None
    """Cursor for next page."""

    previous_cursor: str | None = None
    """Cursor for previous page."""

    page_size: int = 0
    """Number of items per page."""


class BookmarkHistoryResponse(BaseModel):
    """Response from the bookmark history endpoint.

    Attributes:
        results: List of history entries.
        pagination: Pagination metadata.

    Example:
        ```python
        response = BookmarkHistoryResponse(results=[{"action": "created"}])
        ```
    """

    model_config = ConfigDict(frozen=True, extra="allow")

    results: list[Any] = Field(default_factory=list)
    """List of history entries."""

    pagination: BookmarkHistoryPagination | None = None
    """Pagination metadata."""


# =============================================================================
# Cohort Types (Phase 024)
# =============================================================================


class CohortCreator(BaseModel):
    """Creator information for a cohort.

    Attributes:
        id: Creator user ID.
        name: Creator name.
        email: Creator email.

    Example:
        ```python
        creator = CohortCreator(id=1, name="Alice", email="alice@example.com")
        ```
    """

    model_config = ConfigDict(frozen=True, extra="allow")

    id: int | None = None
    """Creator user ID."""

    name: str | None = None
    """Creator name."""

    email: str | None = None
    """Creator email."""


class Cohort(BaseModel):
    """A Mixpanel cohort as returned by the App API.

    Represents the full cohort entity with definition, metadata, and
    cross-references. Extra fields from API evolution are preserved
    via ``extra="allow"``.

    Attributes:
        id: Unique cohort identifier.
        name: Cohort name.
        description: Cohort description.
        count: Number of users in the cohort.
        is_visible: Whether the cohort is visible.
        is_locked: Whether the cohort is locked.
        data_group_id: Data group identifier.
        last_edited: Last edited timestamp string.
        created_by: Creator information.
        referenced_by: IDs of entities referencing this cohort.
        verified: Whether the cohort is verified.
        last_queried: Last queried timestamp string.
        referenced_directly_by: IDs of entities directly referencing this cohort.
        active_integrations: Active integration IDs.

    Example:
        ```python
        cohort = Cohort(id=1, name="Power Users")
        assert cohort.name == "Power Users"
        ```
    """

    model_config = ConfigDict(frozen=True, extra="allow")

    id: int
    """Unique cohort identifier."""

    name: str
    """Cohort name."""

    description: str | None = None
    """Cohort description."""

    count: int | None = None
    """Number of users in the cohort."""

    is_visible: bool | None = None
    """Whether the cohort is visible."""

    is_locked: bool | None = None
    """Whether the cohort is locked."""

    data_group_id: str | None = None
    """Data group identifier."""

    last_edited: str | None = None
    """Last edited timestamp string."""

    created_by: CohortCreator | None = None
    """Creator information."""

    referenced_by: list[int] | None = None
    """IDs of entities referencing this cohort."""

    verified: bool = False
    """Whether the cohort is verified."""

    last_queried: str | None = None
    """Last queried timestamp string."""

    referenced_directly_by: list[int] = Field(default_factory=list)
    """IDs of entities directly referencing this cohort."""

    active_integrations: list[int] = Field(default_factory=list)
    """Active integration IDs."""


class _DefinitionFlatteningModel(BaseModel):
    """Base model that flattens a ``definition`` dict into the top-level payload.

    Subclasses must declare a ``definition: dict[str, Any] | None`` field.
    During serialization, the definition's keys are merged into the
    top-level dict and the ``definition`` key is removed.
    """

    definition: dict[str, Any] | None = None
    """Definition dict (flattened into payload during serialization)."""

    def model_dump(self, **kwargs: Any) -> dict[str, Any]:
        """Serialize with ``definition`` flattened into the top level.

        Args:
            **kwargs: Keyword arguments passed to ``BaseModel.model_dump()``.

        Returns:
            Dict with ``definition`` fields merged into the top level.
        """
        data = super().model_dump(**kwargs)
        definition = data.pop("definition", None)
        if definition:
            data.update(definition)
        return data


class CreateCohortParams(_DefinitionFlatteningModel):
    """Parameters for creating a new cohort.

    The ``definition`` dict is flattened into the top-level JSON payload
    at serialization time — its keys become top-level fields in the request body.

    Attributes:
        name: Cohort name (required).
        description: Cohort description.
        data_group_id: Data group identifier.
        is_locked: Whether the cohort should be locked.
        is_visible: Whether the cohort should be visible.
        deleted: Soft-delete flag.

    Example:
        ```python
        params = CreateCohortParams(name="Power Users")
        data = params.model_dump(exclude_none=True)
        # {"name": "Power Users"}
        ```
    """

    name: str
    """Cohort name (required)."""

    description: str | None = None
    """Cohort description."""

    data_group_id: str | None = None
    """Data group identifier."""

    is_locked: bool | None = None
    """Whether the cohort should be locked."""

    is_visible: bool | None = None
    """Whether the cohort should be visible."""

    deleted: bool | None = None
    """Soft-delete flag."""


class UpdateCohortParams(_DefinitionFlatteningModel):
    """Parameters for updating an existing cohort.

    All fields are optional — only provided fields are sent to the API.
    The ``definition`` dict is flattened into the payload.

    Attributes:
        name: New cohort name.
        description: New cohort description.
        data_group_id: New data group identifier.
        is_locked: New lock setting.
        is_visible: New visibility setting.
        deleted: Soft-delete flag.

    Example:
        ```python
        params = UpdateCohortParams(name="Updated Cohort")
        data = params.model_dump(exclude_none=True)
        # {"name": "Updated Cohort"}
        ```
    """

    name: str | None = None
    """New cohort name."""

    description: str | None = None
    """New cohort description."""

    data_group_id: str | None = None
    """New data group identifier."""

    is_locked: bool | None = None
    """New lock setting."""

    is_visible: bool | None = None
    """New visibility setting."""

    deleted: bool | None = None
    """Soft-delete flag."""


class BulkUpdateCohortEntry(_DefinitionFlatteningModel):
    """Entry for bulk-updating cohorts.

    Attributes:
        id: Cohort ID to update (required).
        name: New cohort name.
        description: New cohort description.

    Example:
        ```python
        entry = BulkUpdateCohortEntry(id=1, name="Renamed")
        ```
    """

    id: int
    """Cohort ID to update (required)."""

    name: str | None = None
    """New cohort name."""

    description: str | None = None
    """New cohort description."""


# =============================================================================
# Feature Flag & Experiment Types (Phase 025)
# =============================================================================


class FeatureFlagStatus(str, Enum):
    """Lifecycle state of a feature flag.

    Attributes:
        ENABLED: Flag is active and serving variants.
        DISABLED: Flag is inactive (default state).
        ARCHIVED: Flag is soft-deleted, excluded from default listings.

    Example:
        ```python
        status = FeatureFlagStatus.ENABLED
        assert status.value == "enabled"
        ```
    """

    ENABLED = "enabled"
    DISABLED = "disabled"
    ARCHIVED = "archived"


class ServingMethod(str, Enum):
    """Controls how flag values are delivered to clients.

    Attributes:
        CLIENT: Client-side evaluation (default).
        SERVER: Server-side evaluation only.
        REMOTE_OR_LOCAL: Remote preferred, local fallback.
        REMOTE_ONLY: Remote evaluation only.

    Example:
        ```python
        method = ServingMethod.CLIENT
        assert method.value == "client"
        ```
    """

    CLIENT = "client"
    SERVER = "server"
    REMOTE_OR_LOCAL = "remote_or_local"
    REMOTE_ONLY = "remote_only"


class FlagContractStatus(str, Enum):
    """Account-level flag contract status.

    Attributes:
        ACTIVE: Active contract.
        GRACE_PERIOD: Contract in grace period.
        EXPIRED: Contract expired.

    Example:
        ```python
        status = FlagContractStatus.ACTIVE
        assert status.value == "active"
        ```
    """

    ACTIVE = "active"
    GRACE_PERIOD = "grace_period"
    EXPIRED = "expired"


class ExperimentStatus(str, Enum):
    """Lifecycle state of an experiment.

    State transitions: ``draft`` → ``active`` (launch) → ``concluded``
    (conclude) → ``success`` | ``fail`` (decide).

    Attributes:
        DRAFT: Experiment created but not started.
        ACTIVE: Experiment running, collecting data.
        CONCLUDED: Experiment stopped, awaiting decision.
        SUCCESS: Experiment decided as successful.
        FAIL: Experiment decided as failed.

    Example:
        ```python
        status = ExperimentStatus.DRAFT
        assert status.value == "draft"
        ```
    """

    DRAFT = "draft"
    ACTIVE = "active"
    CONCLUDED = "concluded"
    SUCCESS = "success"
    FAIL = "fail"


class ExperimentCreator(BaseModel):
    """Creator metadata for an experiment.

    Attributes:
        id: Creator's user ID.
        first_name: Creator's first name.
        last_name: Creator's last name.

    Example:
        ```python
        creator = ExperimentCreator(id=1, first_name="Alice", last_name="Smith")
        ```
    """

    model_config = ConfigDict(frozen=True, extra="allow")

    id: int | None = None
    """Creator's user ID."""

    first_name: str | None = None
    """Creator's first name."""

    last_name: str | None = None
    """Creator's last name."""


class FeatureFlag(BaseModel):
    """A Mixpanel feature flag as returned by the App API.

    Represents the full feature flag entity including configuration,
    metadata, and permissions. Extra fields from API evolution are
    preserved via ``extra="allow"``.

    Attributes:
        id: Unique identifier (UUID).
        project_id: Project this flag belongs to.
        name: Human-readable name.
        key: Machine-readable key (unique per project).
        description: Optional description.
        status: Current lifecycle status.
        tags: Tags for organization.
        experiment_id: Linked experiment ID if flag backs an experiment.
        context: Flag context identifier.
        data_group_id: Data group identifier.
        serving_method: How flag values are delivered.
        ruleset: Variants, rollout rules, and test overrides.
        hash_salt: Salt for deterministic variant assignment.
        workspace_id: Workspace this flag belongs to.
        content_type: Content type identifier.
        created: ISO 8601 creation timestamp.
        modified: ISO 8601 last-modified timestamp.
        enabled_at: Timestamp when flag was last enabled.
        deleted: Timestamp when flag was deleted.
        creator_id: Creator's user ID.
        creator_name: Creator's display name.
        creator_email: Creator's email.
        last_modified_by_id: Last modifier's user ID.
        last_modified_by_name: Last modifier's display name.
        last_modified_by_email: Last modifier's email.
        is_favorited: Whether current user has favorited.
        pinned_date: Date flag was pinned.
        can_edit: Permission: can current user edit.

    Example:
        ```python
        flag = FeatureFlag(
            id="abc-123",
            project_id=12345,
            name="Dark Mode",
            key="dark_mode",
            status=FeatureFlagStatus.DISABLED,
            context="default",
            serving_method=ServingMethod.CLIENT,
            ruleset={"variants": []},
            created="2026-01-01T00:00:00Z",
            modified="2026-01-01T00:00:00Z",
        )
        assert flag.key == "dark_mode"
        ```
    """

    model_config = ConfigDict(frozen=True, extra="allow", populate_by_name=True)

    id: str
    """Unique identifier (UUID)."""

    project_id: int
    """Project this flag belongs to."""

    name: str
    """Human-readable name."""

    key: str
    """Machine-readable key (unique per project)."""

    description: str | None = None
    """Optional description."""

    status: FeatureFlagStatus = FeatureFlagStatus.DISABLED
    """Current lifecycle status."""

    tags: list[str] = Field(default_factory=list)
    """Tags for organization."""

    experiment_id: str | None = None
    """Linked experiment ID if flag backs an experiment."""

    context: str = ""
    """Flag context identifier."""

    data_group_id: str | None = None
    """Data group identifier."""

    serving_method: ServingMethod = ServingMethod.CLIENT
    """How flag values are delivered."""

    ruleset: dict[str, Any] = Field(default_factory=dict)
    """Variants, rollout rules, and test overrides."""

    hash_salt: str | None = None
    """Salt for deterministic variant assignment."""

    workspace_id: int | None = None
    """Workspace this flag belongs to."""

    content_type: str | None = None
    """Content type identifier."""

    created: str = ""
    """ISO 8601 creation timestamp."""

    modified: str = ""
    """ISO 8601 last-modified timestamp."""

    enabled_at: str | None = None
    """Timestamp when flag was last enabled."""

    deleted: str | None = None
    """Timestamp when flag was deleted."""

    creator_id: int | None = None
    """Creator's user ID."""

    creator_name: str | None = None
    """Creator's display name."""

    creator_email: str | None = None
    """Creator's email."""

    last_modified_by_id: int | None = None
    """Last modifier's user ID."""

    last_modified_by_name: str | None = None
    """Last modifier's display name."""

    last_modified_by_email: str | None = None
    """Last modifier's email."""

    is_favorited: bool | None = None
    """Whether current user has favorited."""

    pinned_date: str | None = None
    """Date flag was pinned."""

    can_edit: bool = False
    """Permission: can current user edit."""


class CreateFeatureFlagParams(BaseModel):
    """Parameters for creating a new feature flag.

    The Mixpanel API requires ``name``, ``key``, ``context``,
    ``serving_method``, ``tags``, and ``ruleset`` (with ``variants``
    and ``rollout`` sub-fields). Sensible defaults are provided for
    the non-obvious required fields so that minimal usage works::

        CreateFeatureFlagParams(name="Dark Mode", key="dark_mode")

    Attributes:
        name: Flag name (required).
        key: Unique machine-readable key (required).
        description: Optional description.
        status: Initial status (defaults to disabled).
        tags: Tags for organization (required by API, defaults to empty list).
        context: Flag context identifier (required by API, defaults
            to ``"distinct_id"``).
        serving_method: How flag values are delivered (required by API,
            defaults to ``ServingMethod.CLIENT``).
        ruleset: Ruleset with ``variants`` and ``rollout`` keys
            (required by API, defaults to a simple On/Off toggle).

    Example:
        ```python
        params = CreateFeatureFlagParams(name="Dark Mode", key="dark_mode")
        data = params.model_dump(exclude_none=True)
        ```
    """

    name: str
    """Flag name (required)."""

    key: str
    """Unique machine-readable key (required)."""

    description: str | None = None
    """Optional description."""

    status: FeatureFlagStatus | None = None
    """Initial status (defaults to disabled)."""

    tags: list[str] = Field(default_factory=list)
    """Tags for organization (required by API, defaults to empty list)."""

    context: str = "distinct_id"
    """Flag context identifier (required by API)."""

    serving_method: ServingMethod = ServingMethod.CLIENT
    """How flag values are delivered (required by API)."""

    ruleset: dict[str, Any] = Field(
        default_factory=lambda: {
            "variants": [
                {
                    "key": "On",
                    "value": True,
                    "is_control": False,
                    "split": 1.0,
                    "is_sticky": False,
                },
                {
                    "key": "Off",
                    "value": False,
                    "is_control": True,
                    "split": 0.0,
                    "is_sticky": False,
                },
            ],
            "rollout": [],
        }
    )
    """Ruleset with variants and rollout (required by API)."""


class UpdateFeatureFlagParams(BaseModel):
    """Parameters for updating an existing feature flag (PUT semantics).

    All required fields must always be provided since this performs a
    full replacement, not a partial update. The API requires ``tags``,
    ``context``, and ``serving_method`` in addition to ``name``, ``key``,
    ``status``, and ``ruleset``.

    Attributes:
        name: Flag name (required).
        key: Unique key (required).
        status: Target status (required).
        ruleset: Complete ruleset — replaces existing (required).
        description: Optional description.
        tags: Tags for organization (required by API, defaults to empty list).
        context: Flag context identifier (required by API, defaults
            to ``"distinct_id"``).
        serving_method: How flag values are delivered (required by API,
            defaults to ``ServingMethod.CLIENT``).

    Example:
        ```python
        params = UpdateFeatureFlagParams(
            name="Dark Mode",
            key="dark_mode",
            status=FeatureFlagStatus.ENABLED,
            ruleset={"variants": [], "rollout": []},
        )
        ```
    """

    name: str
    """Flag name (required)."""

    key: str
    """Unique key (required)."""

    status: FeatureFlagStatus
    """Target status (required)."""

    ruleset: dict[str, Any]
    """Complete ruleset — replaces existing (required)."""

    description: str | None = None
    """Optional description."""

    tags: list[str] = Field(default_factory=list)
    """Tags for organization (required by API, defaults to empty list)."""

    context: str = "distinct_id"
    """Flag context identifier (required by API)."""

    serving_method: ServingMethod = ServingMethod.CLIENT
    """How flag values are delivered (required by API)."""


class SetTestUsersParams(BaseModel):
    """Parameters for setting test user variant overrides on a flag.

    Attributes:
        users: Mapping of variant keys to user distinct IDs.

    Example:
        ```python
        params = SetTestUsersParams(users={"on": "user-1", "off": "user-2"})
        ```
    """

    users: dict[str, str]
    """Mapping of variant keys to user distinct IDs."""


class FlagHistoryParams(BaseModel):
    """Parameters for querying feature flag change history.

    Attributes:
        page: Pagination cursor.
        page_size: Results per page.

    Example:
        ```python
        params = FlagHistoryParams(page_size=50)
        ```
    """

    page: str | None = None
    """Pagination cursor."""

    page_size: int | None = None
    """Results per page."""


class FlagHistoryResponse(BaseModel):
    """Paginated change history for a feature flag.

    Attributes:
        events: Array of event arrays.
        count: Total number of events.

    Example:
        ```python
        response = FlagHistoryResponse(events=[[1, "change"]], count=1)
        assert response.count == 1
        ```
    """

    model_config = ConfigDict(frozen=True, extra="allow")

    events: list[list[Any]]
    """Array of event arrays."""

    count: int
    """Total number of events."""


class FlagLimitsResponse(BaseModel):
    """Account-level feature flag usage and limits.

    Attributes:
        limit: Maximum allowed flags.
        is_trial: Whether account is on trial.
        current_usage: Current number of flags.
        contract_status: Contract status.

    Example:
        ```python
        limits = FlagLimitsResponse(
            limit=100, is_trial=False, current_usage=42,
            contract_status=FlagContractStatus.ACTIVE,
        )
        assert limits.current_usage == 42
        ```
    """

    model_config = ConfigDict(frozen=True, extra="allow")

    limit: int
    """Maximum allowed flags."""

    is_trial: bool
    """Whether account is on trial."""

    current_usage: int
    """Current number of flags."""

    contract_status: FlagContractStatus
    """Contract status."""


class Experiment(BaseModel):
    """A Mixpanel A/B experiment as returned by the App API.

    Represents the full experiment entity including lifecycle state,
    variants, metrics, and metadata. Extra fields from API evolution
    are preserved via ``extra="allow"``.

    Attributes:
        id: Unique identifier (UUID).
        name: Human-readable name.
        description: Optional description.
        hypothesis: Experiment hypothesis.
        status: Current lifecycle status.
        variants: Variant configuration.
        metrics: Success metrics.
        settings: Experiment settings.
        exposures_cache: Cached exposure data.
        results_cache: Cached result data.
        start_date: ISO 8601 start date.
        end_date: ISO 8601 end date.
        created: ISO 8601 creation timestamp.
        updated: ISO 8601 last-updated timestamp.
        creator: Creator metadata.
        feature_flag: Linked feature flag data.
        is_favorited: Whether current user has favorited.
        pinned_date: Date experiment was pinned.
        tags: Tags for organization.
        can_edit: Permission: can current user edit.
        last_modified_by_id: Last modifier's user ID.
        last_modified_by_name: Last modifier's display name.
        last_modified_by_email: Last modifier's email.

    Example:
        ```python
        exp = Experiment(id="xyz-456", name="Checkout Flow Test")
        assert exp.name == "Checkout Flow Test"
        ```
    """

    model_config = ConfigDict(frozen=True, extra="allow", populate_by_name=True)

    id: str
    """Unique identifier (UUID)."""

    name: str
    """Human-readable name."""

    description: str | None = None
    """Optional description."""

    hypothesis: str | None = None
    """Experiment hypothesis."""

    status: ExperimentStatus | None = None
    """Current lifecycle status."""

    variants: list[Any] | dict[str, Any] | None = None
    """Variant configuration (list from API, may also be dict)."""

    metrics: list[Any] | dict[str, Any] | None = None
    """Success metrics (list from API, may also be dict)."""

    settings: dict[str, Any] | None = None
    """Experiment settings."""

    exposures_cache: dict[str, Any] | None = None
    """Cached exposure data."""

    results_cache: dict[str, Any] | None = None
    """Cached result data."""

    start_date: str | None = None
    """ISO 8601 start date."""

    end_date: str | None = None
    """ISO 8601 end date."""

    created: str | None = None
    """ISO 8601 creation timestamp."""

    updated: str | None = None
    """ISO 8601 last-updated timestamp."""

    creator: ExperimentCreator | None = None
    """Creator metadata."""

    feature_flag: dict[str, Any] | None = None
    """Linked feature flag data."""

    is_favorited: bool | None = None
    """Whether current user has favorited."""

    pinned_date: str | None = None
    """Date experiment was pinned."""

    tags: list[str] | None = None
    """Tags for organization."""

    can_edit: bool | None = None
    """Permission: can current user edit."""

    last_modified_by_id: int | None = None
    """Last modifier's user ID."""

    last_modified_by_name: str | None = None
    """Last modifier's display name."""

    last_modified_by_email: str | None = None
    """Last modifier's email."""


class CreateExperimentParams(BaseModel):
    """Parameters for creating a new experiment.

    Attributes:
        name: Experiment name (required).
        description: Optional description.
        hypothesis: Experiment hypothesis.
        settings: Experiment settings.
        access_type: Access control type.
        can_edit: Edit permission.

    Example:
        ```python
        params = CreateExperimentParams(name="Checkout Flow Test")
        data = params.model_dump(exclude_none=True)
        # {"name": "Checkout Flow Test"}
        ```
    """

    name: str
    """Experiment name (required)."""

    description: str | None = None
    """Optional description."""

    hypothesis: str | None = None
    """Experiment hypothesis."""

    settings: dict[str, Any] | None = None
    """Experiment settings."""

    access_type: str | None = None
    """Access control type."""

    can_edit: bool | None = None
    """Edit permission."""


class UpdateExperimentParams(BaseModel):
    """Parameters for updating an existing experiment (PATCH semantics).

    All fields optional — only provided fields are updated.

    Attributes:
        name: Updated name.
        description: Updated description.
        hypothesis: Updated hypothesis.
        variants: Updated variant config.
        metrics: Updated metrics.
        settings: Updated settings.
        start_date: Updated start date.
        end_date: Updated end date.
        tags: Updated tags.
        exposures_cache: Updated exposures cache.
        results_cache: Updated results cache.
        status: Updated status.
        global_access_type: Updated access type.

    Example:
        ```python
        params = UpdateExperimentParams(description="Updated")
        data = params.model_dump(exclude_none=True)
        # {"description": "Updated"}
        ```
    """

    name: str | None = None
    """Updated name."""

    description: str | None = None
    """Updated description."""

    hypothesis: str | None = None
    """Updated hypothesis."""

    variants: list[Any] | dict[str, Any] | None = None
    """Updated variant config (list or dict)."""

    metrics: list[Any] | dict[str, Any] | None = None
    """Updated metrics (list or dict)."""

    settings: dict[str, Any] | None = None
    """Updated settings."""

    start_date: str | None = None
    """Updated start date."""

    end_date: str | None = None
    """Updated end date."""

    tags: list[str] | None = None
    """Updated tags."""

    exposures_cache: dict[str, Any] | None = None
    """Updated exposures cache."""

    results_cache: dict[str, Any] | None = None
    """Updated results cache."""

    status: ExperimentStatus | None = None
    """Updated status."""

    global_access_type: str | None = None
    """Updated access type."""


class ExperimentConcludeParams(BaseModel):
    """Parameters for concluding an experiment.

    Attributes:
        end_date: Override end date (ISO 8601).

    Example:
        ```python
        params = ExperimentConcludeParams(end_date="2026-04-01")
        ```
    """

    end_date: str | None = None
    """Override end date (ISO 8601)."""


class ExperimentDecideParams(BaseModel):
    """Parameters for recording an experiment decision.

    Attributes:
        success: Whether the experiment succeeded (required).
        variant: Winning variant key.
        message: Decision summary message.

    Example:
        ```python
        params = ExperimentDecideParams(success=True, variant="simplified")
        ```
    """

    success: bool
    """Whether the experiment succeeded (required)."""

    variant: str | None = None
    """Winning variant key."""

    message: str | None = None
    """Decision summary message."""


class DuplicateExperimentParams(BaseModel):
    """Parameters for duplicating an experiment.

    Attributes:
        name: Name for the duplicated experiment (required).

    Example:
        ```python
        params = DuplicateExperimentParams(name="Checkout Flow Test v2")
        ```
    """

    name: str
    """Name for the duplicated experiment (required)."""


# =============================================================================
# Operational Tooling — Annotations (Phase 026)
# =============================================================================


class AnnotationUser(BaseModel):
    """Nested user info for annotation creator.

    Attributes:
        id: User ID.
        first_name: First name.
        last_name: Last name.

    Example:
        ```python
        user = AnnotationUser(id=1, first_name="Alice", last_name="Smith")
        ```
    """

    model_config = ConfigDict(frozen=True, extra="allow")

    id: int
    """User ID."""

    first_name: str
    """First name."""

    last_name: str
    """Last name."""


class AnnotationTag(BaseModel):
    """Annotation tag for categorization.

    Attributes:
        id: Tag ID.
        name: Tag name.
        project_id: Project ID.
        has_annotations: Whether tag has annotations.

    Example:
        ```python
        tag = AnnotationTag(id=1, name="releases")
        ```
    """

    model_config = ConfigDict(frozen=True, extra="allow")

    id: int
    """Tag ID."""

    name: str
    """Tag name."""

    project_id: int | None = None
    """Project ID."""

    has_annotations: bool | None = None
    """Whether tag has annotations."""


class Annotation(BaseModel):
    """Response model for a timeline annotation.

    Attributes:
        id: Annotation ID.
        project_id: Project ID.
        date: Annotation date (ISO format).
        description: Annotation text.
        user: Creator user info.
        tags: Associated tags.

    Example:
        ```python
        annotation = Annotation.model_validate(api_response)
        ```
    """

    model_config = ConfigDict(frozen=True, extra="allow")

    id: int
    """Annotation ID."""

    project_id: int
    """Project ID."""

    date: str
    """Annotation date (``%Y-%m-%d %H:%M:%S`` format)."""

    description: str
    """Annotation text."""

    user: AnnotationUser | None = None
    """Creator user info."""

    tags: list[AnnotationTag] = Field(default_factory=list)
    """Associated tags."""


class CreateAnnotationParams(BaseModel):
    """Parameters for creating a new annotation.

    Attributes:
        date: Date string in ``%Y-%m-%d %H:%M:%S`` format (required).
        description: Annotation text (max 512 characters, required).
        tags: Tag IDs to associate.
        user_id: Creator user ID.

    Example:
        ```python
        params = CreateAnnotationParams(
            date="2026-03-31 00:00:00", description="v2.5 release"
        )
        ```
    """

    date: str
    """Date string in ``%Y-%m-%d %H:%M:%S`` format."""

    description: str = Field(max_length=512)
    """Annotation text (max 512 characters)."""

    tags: list[int] | None = None
    """Tag IDs to associate."""

    user_id: int | None = None
    """Creator user ID."""


class UpdateAnnotationParams(BaseModel):
    """Parameters for updating an annotation (PATCH semantics).

    Only ``description`` and ``tags`` can be changed after creation;
    the annotation date is immutable.

    Attributes:
        description: New description (max 512 characters).
        tags: New tag IDs.

    Example:
        ```python
        params = UpdateAnnotationParams(description="Updated text")
        ```
    """

    description: str | None = Field(default=None, max_length=512)
    """New description (max 512 characters)."""

    tags: list[int] | None = None
    """New tag IDs."""


class CreateAnnotationTagParams(BaseModel):
    """Parameters for creating an annotation tag.

    Attributes:
        name: Tag name (required).

    Example:
        ```python
        params = CreateAnnotationTagParams(name="releases")
        ```
    """

    name: str
    """Tag name."""


# =============================================================================
# Operational Tooling — Webhooks (Phase 026)
# =============================================================================


class WebhookAuthType(str, Enum):
    """Authentication type for webhooks.

    Values:
        BASIC: HTTP Basic authentication.
    """

    BASIC = "basic"


class ProjectWebhook(BaseModel):
    """Response model for a project webhook.

    Attributes:
        id: Webhook ID (UUID string).
        name: Webhook name.
        url: Webhook URL.
        is_enabled: Whether enabled.
        auth_type: Authentication type.
        created: Creation timestamp.
        modified: Last modified timestamp.
        creator_id: Creator user ID.
        creator_name: Creator name.

    Example:
        ```python
        webhook = ProjectWebhook.model_validate(api_response)
        ```
    """

    model_config = ConfigDict(frozen=True, extra="allow")

    id: str
    """Webhook ID (UUID string)."""

    name: str
    """Webhook name."""

    url: str
    """Webhook URL."""

    is_enabled: bool
    """Whether enabled."""

    auth_type: WebhookAuthType | None = None
    """Authentication type."""

    created: str | None = None
    """Creation timestamp."""

    modified: str | None = None
    """Last modified timestamp."""

    creator_id: int | None = None
    """Creator user ID."""

    creator_name: str | None = None
    """Creator name."""


class CreateWebhookParams(BaseModel):
    """Parameters for creating a webhook.

    Attributes:
        name: Webhook name (required).
        url: Webhook URL (required).
        auth_type: Auth type ("basic" or None).
        username: Basic auth username.
        password: Basic auth password.

    Example:
        ```python
        params = CreateWebhookParams(
            name="Pipeline webhook",
            url="https://example.com/webhook",
        )
        ```
    """

    name: str
    """Webhook name."""

    url: str
    """Webhook URL."""

    auth_type: WebhookAuthType | None = None
    """Auth type (e.g. WebhookAuthType.BASIC)."""

    username: str | None = None
    """Basic auth username."""

    password: str | None = None
    """Basic auth password."""


class UpdateWebhookParams(BaseModel):
    """Parameters for updating a webhook (PATCH semantics).

    Attributes:
        name: New name.
        url: New URL.
        auth_type: New auth type.
        username: New username.
        password: New password.
        is_enabled: New enabled state.

    Example:
        ```python
        params = UpdateWebhookParams(name="Updated name")
        ```
    """

    name: str | None = None
    """New name."""

    url: str | None = None
    """New URL."""

    auth_type: WebhookAuthType | None = None
    """New auth type."""

    username: str | None = None
    """New username."""

    password: str | None = None
    """New password."""

    is_enabled: bool | None = None
    """New enabled state."""


class WebhookTestParams(BaseModel):
    """Parameters for testing webhook connectivity.

    Attributes:
        url: URL to test (required).
        name: Webhook name.
        auth_type: Auth type.
        username: Username for auth.
        password: Password for auth.

    Example:
        ```python
        params = WebhookTestParams(url="https://example.com/webhook")
        ```
    """

    url: str
    """URL to test."""

    name: str | None = None
    """Webhook name."""

    auth_type: WebhookAuthType | None = None
    """Auth type."""

    username: str | None = None
    """Username for auth."""

    password: str | None = None
    """Password for auth."""


class WebhookTestResult(BaseModel):
    """Response model for webhook connectivity test.

    Attributes:
        success: Whether test succeeded.
        status_code: HTTP status code.
        message: Descriptive message.

    Example:
        ```python
        result = WebhookTestResult.model_validate(api_response)
        if result.success:
            print("Webhook is reachable")
        ```
    """

    model_config = ConfigDict(frozen=True, extra="allow")

    success: bool
    """Whether test succeeded."""

    status_code: int
    """HTTP status code."""

    message: str
    """Descriptive message."""


class WebhookMutationResult(BaseModel):
    """Response model for webhook create/update (returns id + name only).

    Attributes:
        id: Webhook ID.
        name: Webhook name.

    Example:
        ```python
        result = WebhookMutationResult.model_validate(api_response)
        ```
    """

    model_config = ConfigDict(frozen=True, extra="allow")

    id: str
    """Webhook ID."""

    name: str
    """Webhook name."""


# =============================================================================
# Operational Tooling — Alerts (Phase 026)
# =============================================================================


class AlertFrequencyPreset(int, Enum):
    """Preset frequency values for alert check intervals.

    Values:
        HOURLY: Check every hour (3600 seconds).
        DAILY: Check every day (86400 seconds).
        WEEKLY: Check every week (604800 seconds).
    """

    HOURLY = 3600
    DAILY = 86400
    WEEKLY = 604800


class AlertBookmark(BaseModel):
    """Nested bookmark info for an alert.

    Attributes:
        id: Bookmark ID.
        name: Bookmark name.
        type: Bookmark type.

    Example:
        ```python
        bookmark = AlertBookmark(id=1, name="Daily Signups")
        ```
    """

    model_config = ConfigDict(frozen=True, extra="allow")

    id: int
    """Bookmark ID."""

    name: str | None = None
    """Bookmark name."""

    type: str | None = None
    """Bookmark type."""


class AlertCreator(BaseModel):
    """Nested creator info for an alert.

    Attributes:
        id: User ID.
        first_name: First name.
        last_name: Last name.
        email: Email.

    Example:
        ```python
        creator = AlertCreator(id=1, email="alice@example.com")
        ```
    """

    model_config = ConfigDict(frozen=True, extra="allow")

    id: int
    """User ID."""

    first_name: str | None = None
    """First name."""

    last_name: str | None = None
    """Last name."""

    email: str | None = None
    """Email."""


class AlertWorkspace(BaseModel):
    """Nested workspace info for an alert.

    Attributes:
        id: Workspace ID.
        name: Workspace name.

    Example:
        ```python
        ws = AlertWorkspace(id=100, name="Production")
        ```
    """

    model_config = ConfigDict(frozen=True, extra="allow")

    id: int
    """Workspace ID."""

    name: str | None = None
    """Workspace name."""


class AlertProject(BaseModel):
    """Nested project info for an alert.

    Attributes:
        id: Project ID.
        name: Project name.

    Example:
        ```python
        proj = AlertProject(id=12345, name="My App")
        ```
    """

    model_config = ConfigDict(frozen=True, extra="allow")

    id: int
    """Project ID."""

    name: str | None = None
    """Project name."""


class CustomAlert(BaseModel):
    """Response model for a custom alert.

    Attributes:
        id: Alert ID.
        name: Alert name.
        bookmark: Linked saved report.
        condition: Trigger condition (opaque JSON).
        frequency: Check frequency in seconds.
        paused: Whether alert is paused.
        subscriptions: Notification targets.
        notification_windows: Notification window config.
        creator: Creator user info.
        workspace: Workspace metadata.
        project: Project metadata.
        created: Creation timestamp.
        modified: Last modified timestamp.
        last_checked: Last check timestamp.
        last_fired: Last trigger timestamp.
        valid: Whether alert is valid.
        results: Latest evaluation results.

    Example:
        ```python
        alert = CustomAlert.model_validate(api_response)
        ```
    """

    model_config = ConfigDict(frozen=True, extra="allow")

    id: int
    """Alert ID."""

    name: str
    """Alert name."""

    bookmark: AlertBookmark | None = None
    """Linked saved report."""

    condition: dict[str, Any] = Field(default_factory=dict)
    """Trigger condition (opaque JSON)."""

    frequency: int = 0
    """Check frequency in seconds."""

    paused: bool = False
    """Whether alert is paused."""

    subscriptions: list[dict[str, Any]] = Field(default_factory=list)
    """Notification targets."""

    notification_windows: dict[str, Any] | None = None
    """Notification window config."""

    creator: AlertCreator | None = None
    """Creator user info."""

    workspace: AlertWorkspace | None = None
    """Workspace metadata."""

    project: AlertProject | None = None
    """Project metadata."""

    created: str = ""
    """Creation timestamp."""

    modified: str = ""
    """Last modified timestamp."""

    last_checked: str | None = None
    """Last check timestamp."""

    last_fired: str | None = None
    """Last trigger timestamp."""

    valid: bool = True
    """Whether alert is valid."""

    results: dict[str, Any] | None = None
    """Latest evaluation results."""


class CreateAlertParams(BaseModel):
    """Parameters for creating a new alert.

    Attributes:
        bookmark_id: ID of linked bookmark (required).
        name: Alert name (required).
        condition: Trigger condition JSON (required).
        frequency: Check frequency in seconds (required).
        paused: Start paused or active (required).
        subscriptions: Notification targets (required).
        notification_windows: Notification window config.

    Example:
        ```python
        params = CreateAlertParams(
            bookmark_id=12345,
            name="Daily signups drop",
            condition={
                "keys": [{"header": "Signup", "value": "Signup"}],
                "type": "absolute",
                "op": "<",
                "value": 100,
            },
            frequency=AlertFrequencyPreset.DAILY,
            paused=False,
            subscriptions=[{"type": "email", "value": "team@example.com"}],
        )
        ```
    """

    bookmark_id: int
    """ID of linked bookmark."""

    name: str = Field(max_length=50)
    """Alert name (max 50 characters)."""

    condition: dict[str, Any]
    """Trigger condition JSON."""

    frequency: int
    """Check frequency in seconds. See ``AlertFrequencyPreset`` for common values."""

    paused: bool
    """Start paused or active."""

    subscriptions: list[dict[str, Any]]
    """Notification targets."""

    notification_windows: dict[str, Any] | None = None
    """Notification window config."""


class UpdateAlertParams(BaseModel):
    """Parameters for updating an alert (PATCH semantics).

    Attributes:
        name: New name.
        bookmark_id: New bookmark ID.
        condition: New condition.
        frequency: New frequency.
        paused: New pause state.
        subscriptions: New subscriptions.
        notification_windows: New notification windows.

    Example:
        ```python
        params = UpdateAlertParams(name="Updated alert", paused=True)
        ```
    """

    name: str | None = None
    """New name."""

    bookmark_id: int | None = None
    """New bookmark ID."""

    condition: dict[str, Any] | None = None
    """New condition."""

    frequency: int | None = None
    """New frequency."""

    paused: bool | None = None
    """New pause state."""

    subscriptions: list[dict[str, Any]] | None = None
    """New subscriptions."""

    notification_windows: dict[str, Any] | None = None
    """New notification windows."""


class AlertCount(BaseModel):
    """Response model for alert count and limits.

    Attributes:
        anomaly_alerts_count: Current alert count.
        alert_limit: Account limit.
        is_below_limit: Whether below limit.

    Example:
        ```python
        count = AlertCount.model_validate(api_response)
        if count.is_below_limit:
            print(f"{count.anomaly_alerts_count}/{count.alert_limit}")
        ```
    """

    model_config = ConfigDict(frozen=True, extra="allow")

    anomaly_alerts_count: int
    """Current alert count."""

    alert_limit: int
    """Account limit."""

    is_below_limit: bool
    """Whether below limit."""


class AlertHistoryPagination(BaseModel):
    """Pagination metadata for alert history.

    Attributes:
        next_cursor: Next page cursor.
        previous_cursor: Previous page cursor.
        page_size: Page size.

    Example:
        ```python
        pagination = AlertHistoryPagination(page_size=20)
        ```
    """

    model_config = ConfigDict(frozen=True, extra="allow")

    next_cursor: str | None = None
    """Next page cursor."""

    previous_cursor: str | None = None
    """Previous page cursor."""

    page_size: int = 20
    """Page size."""


class AlertHistoryResponse(BaseModel):
    """Response model for alert history (paginated).

    Attributes:
        results: History entries.
        pagination: Pagination metadata.

    Example:
        ```python
        history = AlertHistoryResponse.model_validate(api_response)
        for entry in history.results:
            print(entry)
        ```
    """

    model_config = ConfigDict(frozen=True, extra="allow")

    results: list[dict[str, Any]] = Field(default_factory=list)
    """History entries."""

    pagination: AlertHistoryPagination | None = None
    """Pagination metadata."""


class AlertScreenshotResponse(BaseModel):
    """Response model for alert screenshot URL.

    Attributes:
        signed_url: Signed GCS URL for screenshot.

    Example:
        ```python
        resp = AlertScreenshotResponse.model_validate(api_response)
        print(resp.signed_url)
        ```
    """

    model_config = ConfigDict(frozen=True, extra="allow")

    signed_url: str
    """Signed GCS URL for screenshot."""


class AlertValidation(BaseModel):
    """Per-alert validation result.

    Attributes:
        alert_id: Alert ID.
        alert_name: Alert name.
        valid: Whether valid.
        reason: Reason if invalid.

    Example:
        ```python
        v = AlertValidation(alert_id=1, alert_name="Test", valid=True)
        ```
    """

    model_config = ConfigDict(frozen=True, extra="allow")

    alert_id: int
    """Alert ID."""

    alert_name: str
    """Alert name."""

    valid: bool
    """Whether valid."""

    reason: str | None = None
    """Reason if invalid."""


class ValidateAlertsForBookmarkParams(BaseModel):
    """Parameters for validating alerts against a bookmark.

    Attributes:
        alert_ids: Alert IDs to validate (required).
        bookmark_type: Bookmark type to validate against (required).
        bookmark_params: Bookmark params JSON (required).

    Example:
        ```python
        params = ValidateAlertsForBookmarkParams(
            alert_ids=[1, 2],
            bookmark_type="insights",
            bookmark_params={"event": "Signup"},
        )
        ```
    """

    alert_ids: list[int] = Field(min_length=1)
    """Alert IDs to validate (must not be empty)."""

    bookmark_type: Literal["insights", "funnels"]
    """Bookmark type to validate against."""

    bookmark_params: dict[str, Any]
    """Bookmark params JSON."""


class ValidateAlertsForBookmarkResponse(BaseModel):
    """Response model for alert-bookmark validation.

    Attributes:
        alert_validations: Per-alert validation results.
        invalid_count: Count of invalid alerts.

    Example:
        ```python
        resp = ValidateAlertsForBookmarkResponse.model_validate(api_response)
        if resp.invalid_count > 0:
            for v in resp.alert_validations:
                if not v.valid:
                    print(f"{v.alert_name}: {v.reason}")
        ```
    """

    model_config = ConfigDict(frozen=True, extra="allow")

    alert_validations: list[AlertValidation] = Field(default_factory=list)
    """Per-alert validation results."""

    invalid_count: int = 0
    """Count of invalid alerts."""


# =============================================================================
# Data Governance — Data Definitions / Lexicon (Phase 027)
# =============================================================================


class PropertyResourceType(str, Enum):
    """Resource type for property definitions.

    Values:
        EVENT: Event property.
        USER: User profile property.
        GROUPPROFILE: Group profile property (wire format: ``groupprofile``).
    """

    EVENT = "event"
    USER = "user"
    GROUPPROFILE = "groupprofile"


class EventDefinition(BaseModel):
    """A Mixpanel event definition from the Lexicon.

    Attributes:
        id: Server-assigned event ID.
        name: Event name (unique identifier).
        display_name: Human-readable name.
        description: Event description.
        hidden: Whether hidden from UI.
        dropped: Whether data is dropped at ingestion.
        merged: Whether merged into another event.
        verified: Whether verified by governance team.
        tags: Assigned tag names.
        custom_event_id: Links to custom event.
        last_modified: ISO 8601 timestamp.
        status: Event status.
        platforms: Tracking platforms.
        created_utc: ISO 8601 creation timestamp.
        modified_utc: ISO 8601 modification timestamp.

    Example:
        ```python
        ev = EventDefinition(id=1, name="Purchase")
        ```
    """

    model_config = ConfigDict(
        frozen=True, extra="allow", alias_generator=to_camel, populate_by_name=True
    )

    id: int
    """Server-assigned event ID."""

    name: str
    """Event name (unique identifier)."""

    display_name: str | None = None
    """Human-readable name."""

    description: str | None = None
    """Event description."""

    hidden: bool | None = None
    """Whether hidden from UI."""

    dropped: bool | None = None
    """Whether data is dropped at ingestion."""

    merged: bool | None = None
    """Whether merged into another event."""

    verified: bool | None = None
    """Whether verified by governance team."""

    tags: list[str] | None = None
    """Assigned tag names."""

    custom_event_id: int | None = None
    """Links to custom event."""

    last_modified: str | None = None
    """ISO 8601 timestamp."""

    status: str | None = None
    """Event status."""

    platforms: list[str] | None = None
    """Tracking platforms."""

    created_utc: str | None = None
    """ISO 8601 creation timestamp."""

    modified_utc: str | None = None
    """ISO 8601 modification timestamp."""


class PropertyDefinition(BaseModel):
    """A Mixpanel property definition from the Lexicon.

    Attributes:
        id: Server-assigned property ID.
        name: Property name.
        resource_type: Property resource type (event, user, groupprofile).
        description: Property description.
        hidden: Whether hidden from UI.
        dropped: Whether data is dropped.
        merged: Whether merged into another property.
        sensitive: PII flag.
        data_group_id: Data group identifier.

    Example:
        ```python
        prop = PropertyDefinition(id=1, name="$browser")
        ```
    """

    model_config = ConfigDict(
        frozen=True, extra="allow", alias_generator=to_camel, populate_by_name=True
    )

    id: int | None = None
    """Server-assigned property ID (may be absent for custom properties)."""

    name: str
    """Property name."""

    resource_type: str | None = None
    """Property resource type (event, user, groupprofile)."""

    description: str | None = None
    """Property description."""

    hidden: bool | None = None
    """Whether hidden from UI."""

    dropped: bool | None = None
    """Whether data is dropped."""

    merged: bool | None = None
    """Whether merged into another property."""

    sensitive: bool | None = None
    """PII flag."""

    data_group_id: str | None = None
    """Data group identifier."""


class UpdateEventDefinitionParams(BaseModel):
    """Parameters for updating an event definition (PATCH semantics).

    All fields are optional; only set fields are sent.

    Attributes:
        hidden: Whether hidden from UI.
        dropped: Whether data is dropped.
        merged: Whether merged.
        verified: Whether verified.
        tags: Tag names to assign.
        description: Event description.

    Example:
        ```python
        params = UpdateEventDefinitionParams(
            description="User completed a purchase", verified=True
        )
        ```
    """

    hidden: bool | None = None
    """Whether hidden from UI."""

    dropped: bool | None = None
    """Whether data is dropped."""

    merged: bool | None = None
    """Whether merged."""

    verified: bool | None = None
    """Whether verified."""

    tags: list[str] | None = None
    """Tag names to assign."""

    description: str | None = None
    """Event description."""


class CustomEventAlternative(BaseModel):
    """An underlying event aliased by a custom event.

    A Mixpanel custom event groups one or more underlying events under a single
    name. Each ``CustomEventAlternative`` names one such underlying event.

    Attributes:
        event: Name of the underlying event being aliased.

    Example:
        ```python
        CustomEventAlternative(event="Home Page Viewed")
        ```
    """

    model_config = ConfigDict(frozen=True, extra="allow")

    event: str = Field(min_length=1)
    """Name of the underlying event being aliased (must be non-empty)."""


class CustomEvent(BaseModel):
    """A Mixpanel custom event composed of one or more underlying events.

    Returned by the ``/custom_events/`` endpoint family (e.g. by
    :meth:`Workspace.create_custom_event`). Distinct from
    :class:`EventDefinition`, which represents the lexicon (governance) view
    of an event.

    Attributes:
        id: Server-assigned custom event ID.
        name: Display name shown in the Mixpanel UI and queries.
        alternatives: Underlying events aliased by this custom event.

    Example:
        ```python
        ce = CustomEvent(
            id=42,
            name="Page View",
            alternatives=[CustomEventAlternative(event="Home Viewed")],
        )
        ```
    """

    model_config = ConfigDict(frozen=True, extra="allow")

    id: int
    """Server-assigned custom event ID."""

    name: str
    """Display name shown in the Mixpanel UI and queries."""

    alternatives: list[CustomEventAlternative] = Field(default_factory=list)
    """Underlying events aliased by this custom event."""


class CreateCustomEventParams(BaseModel):
    """Parameters for creating a custom event.

    The ``alternatives`` field accepts a list of bare event names for
    ergonomics; :meth:`to_form_body` serializes them to the
    ``[{"event": <name>}, ...]`` shape the Mixpanel API expects.

    Attributes:
        name: Display name for the custom event (must be non-empty).
        alternatives: Underlying event names to alias. Must be non-empty,
            contain no empty/whitespace-only entries, and contain no
            duplicates.

    Example:
        ```python
        params = CreateCustomEventParams(
            name="Metric Tree Opened",
            alternatives=["Enter room"],
        )
        ws.create_custom_event(params)
        ```
    """

    model_config = ConfigDict(frozen=True)

    name: str = Field(min_length=1)
    """Display name for the custom event (must be non-empty)."""

    alternatives: list[str] = Field(min_length=1)
    """Underlying event names to alias (must be non-empty)."""

    @field_validator("alternatives")
    @classmethod
    def _validate_alternatives(cls, v: list[str]) -> list[str]:
        """Reject empty/whitespace-only entries and duplicates.

        Args:
            v: List of alternative event names supplied by the caller.

        Returns:
            The validated list, unchanged.

        Raises:
            ValueError: An entry is empty, whitespace-only, or duplicated.
        """
        if any(not s or not s.strip() for s in v):
            raise ValueError(
                "alternatives must not contain empty or whitespace-only strings"
            )
        if len(set(v)) != len(v):
            raise ValueError("alternatives must be unique")
        return v

    def to_form_body(self) -> dict[str, str]:
        """Serialize to the form-encoded body the Mixpanel API expects.

        Returns:
            A dict with two string fields:

            - ``name``: the custom event display name.
            - ``alternatives``: a JSON-encoded list of ``{"event": <name>}``
              dicts, one per underlying event.
        """
        return {
            "name": self.name,
            "alternatives": json.dumps([{"event": e} for e in self.alternatives]),
        }


class UpdatePropertyDefinitionParams(BaseModel):
    """Parameters for updating a property definition (PATCH semantics).

    All fields are optional; only set fields are sent.

    Attributes:
        hidden: Whether hidden from UI.
        dropped: Whether data is dropped.
        merged: Whether merged.
        sensitive: PII flag.
        description: Property description.

    Example:
        ```python
        params = UpdatePropertyDefinitionParams(sensitive=True)
        ```
    """

    hidden: bool | None = None
    """Whether hidden from UI."""

    dropped: bool | None = None
    """Whether data is dropped."""

    merged: bool | None = None
    """Whether merged."""

    sensitive: bool | None = None
    """PII flag."""

    description: str | None = None
    """Property description."""


class BulkEventUpdate(BaseModel):
    """A single event update entry for bulk operations.

    Attributes:
        name: Event name (identifier).
        id: Alternative identifier.
        hidden: Whether hidden from UI.
        dropped: Whether data is dropped.
        merged: Whether merged.
        verified: Whether verified.
        tags: Tag names.
        contacts: Contact emails.
        team_contacts: Team contact emails.

    Example:
        ```python
        entry = BulkEventUpdate(name="OldEvent", hidden=True)
        ```
    """

    name: str | None = None
    """Event name (identifier)."""

    id: int | None = None
    """Alternative identifier."""

    hidden: bool | None = None
    """Whether hidden from UI."""

    dropped: bool | None = None
    """Whether data is dropped."""

    merged: bool | None = None
    """Whether merged."""

    verified: bool | None = None
    """Whether verified."""

    tags: list[str] | None = None
    """Tag names."""

    contacts: list[str] | None = None
    """Contact emails."""

    team_contacts: list[str] | None = None
    """Team contact emails."""


class BulkUpdateEventsParams(BaseModel):
    """Parameters for bulk-updating event definitions.

    Attributes:
        events: List of event update entries (required).

    Example:
        ```python
        params = BulkUpdateEventsParams(
            events=[BulkEventUpdate(name="E1", hidden=True)]
        )
        ```
    """

    events: list[BulkEventUpdate]
    """List of event update entries."""


class BulkPropertyUpdate(BaseModel):
    """A single property update entry for bulk operations.

    Uses camelCase serialization to match the Django API contract.

    Attributes:
        name: Property name (required).
        resource_type: Resource type (required).
        id: Property ID.
        hidden: Whether hidden from UI.
        dropped: Whether data is dropped.
        sensitive: PII flag.
        data_group_id: Data group identifier.

    Example:
        ```python
        entry = BulkPropertyUpdate(name="$browser", resource_type="event")
        ```
    """

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    name: str
    """Property name."""

    resource_type: str
    """Resource type (event, user, groupprofile)."""

    id: int | None = None
    """Property ID."""

    hidden: bool | None = None
    """Whether hidden from UI."""

    dropped: bool | None = None
    """Whether data is dropped."""

    sensitive: bool | None = None
    """PII flag."""

    data_group_id: str | None = None
    """Data group identifier."""


class BulkUpdatePropertiesParams(BaseModel):
    """Parameters for bulk-updating property definitions.

    Attributes:
        properties: List of property update entries (required).

    Example:
        ```python
        params = BulkUpdatePropertiesParams(
            properties=[BulkPropertyUpdate(name="$browser", resource_type="event")]
        )
        ```
    """

    properties: list[BulkPropertyUpdate]
    """List of property update entries."""


class LexiconTag(BaseModel):
    """A Lexicon tag for categorizing event/property definitions.

    Attributes:
        id: Server-assigned tag ID.
        name: Tag name.

    Example:
        ```python
        tag = LexiconTag(id=1, name="core-metrics")
        ```
    """

    model_config = ConfigDict(
        frozen=True, extra="allow", alias_generator=to_camel, populate_by_name=True
    )

    id: int
    """Server-assigned tag ID."""

    name: str
    """Tag name."""


class CreateTagParams(BaseModel):
    """Parameters for creating a Lexicon tag.

    Attributes:
        name: Tag name (required, non-empty).

    Example:
        ```python
        params = CreateTagParams(name="core-metrics")
        ```
    """

    name: str
    """Tag name."""


class UpdateTagParams(BaseModel):
    """Parameters for updating a Lexicon tag.

    Attributes:
        name: New tag name.

    Example:
        ```python
        params = UpdateTagParams(name="key-metrics")
        ```
    """

    name: str | None = None
    """New tag name."""


# =============================================================================
# Data Governance — Drop Filters (Phase 027)
# =============================================================================


class DropFilter(BaseModel):
    """A drop filter for discarding events at ingestion.

    Attributes:
        id: Server-assigned filter ID.
        event_name: Event name to filter.
        filters: Filter condition JSON.
        active: Whether the filter is active.
        display_name: Human-readable name.
        created: ISO 8601 creation timestamp.

    Example:
        ```python
        df = DropFilter(id=1, event_name="debug_log")
        ```
    """

    model_config = ConfigDict(
        frozen=True, extra="allow", alias_generator=to_camel, populate_by_name=True
    )

    id: int
    """Server-assigned filter ID."""

    event_name: str
    """Event name to filter."""

    filters: list[Any] | None = None
    """Filter condition JSON."""

    active: bool | None = None
    """Whether the filter is active."""

    display_name: str | None = None
    """Human-readable name."""

    created: str | None = None
    """ISO 8601 creation timestamp."""


class CreateDropFilterParams(BaseModel):
    """Parameters for creating a drop filter.

    Attributes:
        event_name: Event name to filter (required).
        filters: Filter condition JSON (required).

    Example:
        ```python
        params = CreateDropFilterParams(
            event_name="debug_log",
            filters={"property": "env", "operator": "equals", "value": "test"},
        )
        ```
    """

    event_name: str
    """Event name to filter."""

    filters: Any  # Any justified: API accepts polymorphic filter JSON
    """Filter condition JSON."""


class UpdateDropFilterParams(BaseModel):
    """Parameters for updating a drop filter.

    Attributes:
        id: Drop filter ID (required).
        event_name: New event name.
        filters: New filter condition JSON.
        active: Whether the filter is active.

    Example:
        ```python
        params = UpdateDropFilterParams(id=123, active=False)
        ```
    """

    id: int
    """Drop filter ID."""

    event_name: str | None = None
    """New event name."""

    filters: Any | None = None  # Any justified: API accepts polymorphic filter JSON
    """New filter condition JSON."""

    active: bool | None = None
    """Whether the filter is active."""


class DropFilterLimitsResponse(BaseModel):
    """Response model for drop filter limits.

    Attributes:
        filter_limit: Maximum allowed filters.

    Example:
        ```python
        limits = DropFilterLimitsResponse(filter_limit=10)
        ```
    """

    model_config = ConfigDict(
        frozen=True, extra="allow", alias_generator=to_camel, populate_by_name=True
    )

    filter_limit: int
    """Maximum allowed filters."""


# =============================================================================
# Data Governance — Custom Properties (Phase 027)
# =============================================================================


class CustomPropertyResourceType(str, Enum):
    """Resource type for custom properties.

    Values:
        EVENTS: Event-level custom property.
        PEOPLE: User profile custom property.
        GROUP_PROFILES: Group profile custom property.
    """

    EVENTS = "events"
    PEOPLE = "people"
    GROUP_PROFILES = "group_profiles"


class ComposedPropertyValue(BaseModel):
    """A composed property reference within a custom property formula.

    Attributes:
        type: Property type.
        type_cast: Type cast instruction.
        resource_type: Resource type (required).
        behavior: Behavior specification.
        join_property_type: Join property type.

    Example:
        ```python
        cpv = ComposedPropertyValue(resource_type="event")
        ```
    """

    model_config = ConfigDict(
        frozen=True, extra="allow", alias_generator=to_camel, populate_by_name=True
    )

    type: str | None = None
    """Property type."""

    type_cast: str | None = None
    """Type cast instruction."""

    resource_type: str
    """Resource type. Uses singular form (event, user, groupprofile) from the
    Mixpanel API composed property schema — distinct from
    ``CustomPropertyResourceType`` which uses plural form."""

    value: str | None = None
    """Property name in the project (e.g. ``"deal_name"``)."""

    label: str | None = None
    """Human-readable label for the property (e.g. ``"Deal Name"``)."""

    property_default_type: CustomPropertyType | None = None
    """Default property type hint (e.g. ``"string"``, ``"number"``)."""

    behavior: Any | None = (
        None  # Any justified: API behavior spec varies by resource type
    )
    """Behavior specification."""

    join_property_type: str | None = None
    """Join property type."""


class CustomProperty(BaseModel):
    """A Mixpanel custom property (computed/formula property).

    Attributes:
        custom_property_id: Server-assigned property ID.
        name: Property name.
        description: Property description.
        resource_type: Resource type (events, people, group_profiles).
        property_type: Property type.
        display_formula: Formula expression.
        composed_properties: Referenced properties in formula.
        is_locked: Whether the property is locked.
        is_visible: Whether the property is visible.
        data_group_id: Data group identifier.
        created: ISO 8601 creation timestamp.
        modified: ISO 8601 modification timestamp.
        example_value: Example value.

    Example:
        ```python
        cp = CustomProperty(
            custom_property_id=1, name="Revenue", resource_type="events"
        )
        ```
    """

    model_config = ConfigDict(
        frozen=True, extra="allow", alias_generator=to_camel, populate_by_name=True
    )

    custom_property_id: int
    """Server-assigned property ID."""

    name: str
    """Property name."""

    description: str | None = None
    """Property description."""

    resource_type: CustomPropertyResourceType
    """Resource type (events, people, group_profiles)."""

    property_type: str | None = None
    """Property type."""

    display_formula: str | None = None
    """Formula expression."""

    composed_properties: dict[str, ComposedPropertyValue] | None = None
    """Referenced properties in formula."""

    is_locked: bool | None = None
    """Whether the property is locked."""

    is_visible: bool | None = None
    """Whether the property is visible."""

    data_group_id: str | None = None
    """Data group identifier."""

    created: str | None = None
    """ISO 8601 creation timestamp."""

    modified: str | None = None
    """ISO 8601 modification timestamp."""

    example_value: str | None = None
    """Example value."""


class CreateCustomPropertyParams(BaseModel):
    """Parameters for creating a custom property.

    Validation rules:
    - ``display_formula`` and ``behavior`` are mutually exclusive.
    - ``behavior`` and ``composed_properties`` are mutually exclusive.
    - ``display_formula`` requires ``composed_properties``.
    - One of ``display_formula`` or ``behavior`` must be set.

    Attributes:
        name: Property name (required).
        resource_type: Resource type (required).
        description: Property description.
        display_formula: Formula expression (mutually exclusive with behavior).
        composed_properties: Referenced properties (required if display_formula set).
        is_locked: Whether the property is locked.
        is_visible: Whether the property is visible.
        data_group_id: Data group identifier.
        behavior: Behavior specification (mutually exclusive with display_formula).

    Example:
        ```python
        params = CreateCustomPropertyParams(
            name="Revenue Per User",
            resource_type="events",
            display_formula='number(properties["amount"])',
            composed_properties={"amount": ComposedPropertyValue(resource_type="event")},
        )
        ```
    """

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    name: str
    """Property name."""

    resource_type: CustomPropertyResourceType
    """Resource type (events, people, group_profiles)."""

    description: str | None = None
    """Property description."""

    display_formula: str | None = None
    """Formula expression (mutually exclusive with behavior)."""

    composed_properties: dict[str, ComposedPropertyValue] | None = None
    """Referenced properties (required if display_formula set)."""

    is_locked: bool | None = None
    """Whether the property is locked."""

    is_visible: bool | None = None
    """Whether the property is visible."""

    property_type: CustomPropertyType | None = None
    """Output type of the custom property (string, number, boolean, datetime).
    Auto-inferred by the API from the formula if not set."""

    example_value: str | None = None
    """Example output value for documentation purposes."""

    data_group_id: str | None = None
    """Data group identifier."""

    behavior: Any | None = (
        None  # Any justified: API behavior spec varies by resource type
    )
    """Behavior specification (mutually exclusive with display_formula)."""

    @model_validator(mode="after")
    def _validate_formula_behavior(self) -> CreateCustomPropertyParams:
        """Validate mutual exclusion of display_formula and behavior.

        Returns:
            The validated instance.

        Raises:
            ValueError: If validation rules are violated.
        """
        if self.display_formula is not None and self.behavior is not None:
            msg = "display_formula and behavior are mutually exclusive"
            raise ValueError(msg)

        if self.behavior is not None and self.composed_properties is not None:
            msg = "behavior and composed_properties are mutually exclusive"
            raise ValueError(msg)

        if self.display_formula is not None and self.composed_properties is None:
            msg = "display_formula requires composed_properties"
            raise ValueError(msg)

        if self.display_formula is None and self.behavior is None:
            msg = "one of display_formula or behavior must be set"
            raise ValueError(msg)

        return self


class UpdateCustomPropertyParams(BaseModel):
    """Parameters for updating a custom property (PUT — full replacement).

    Note: ``resource_type`` and ``data_group_id`` are immutable.

    Attributes:
        name: Property name.
        description: Property description.
        display_formula: Formula expression.
        composed_properties: Referenced properties.
        is_locked: Whether the property is locked.
        is_visible: Whether the property is visible.

    Example:
        ```python
        params = UpdateCustomPropertyParams(name="Updated Name")
        ```
    """

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    name: str | None = None
    """Property name."""

    description: str | None = None
    """Property description."""

    display_formula: str | None = None
    """Formula expression."""

    composed_properties: dict[str, ComposedPropertyValue] | None = None
    """Referenced properties."""

    is_locked: bool | None = None
    """Whether the property is locked."""

    is_visible: bool | None = None
    """Whether the property is visible."""


# =============================================================================
# Data Governance — Lookup Tables (Phase 027)
# =============================================================================


class LookupTable(BaseModel):
    """A Mixpanel lookup table.

    Attributes:
        id: Server-assigned table ID.
        name: Table name.
        token: Table token.
        created_at: ISO 8601 creation timestamp.
        last_modified_at: ISO 8601 modification timestamp.
        has_mapped_properties: Whether the table has mapped properties.

    Example:
        ```python
        lt = LookupTable(id=1, name="Product Catalog")
        ```
    """

    model_config = ConfigDict(
        frozen=True, extra="allow", alias_generator=to_camel, populate_by_name=True
    )

    id: int
    """Server-assigned table ID."""

    name: str
    """Table name."""

    token: str | None = None
    """Table token."""

    created_at: str | None = None
    """ISO 8601 creation timestamp."""

    last_modified_at: str | None = None
    """ISO 8601 modification timestamp."""

    has_mapped_properties: bool | None = None
    """Whether the table has mapped properties."""


class UploadLookupTableParams(BaseModel):
    """Parameters for uploading a lookup table CSV.

    The upload is a 3-step process handled by the workspace method:
    1. Get a signed upload URL
    2. Upload CSV to signed URL
    3. Register the table

    Attributes:
        name: Table name (1-255 characters, required).
        file_path: Path to local CSV file (required).
        data_group_id: For replacing an existing table.

    Example:
        ```python
        params = UploadLookupTableParams(
            name="Product Catalog", file_path="/path/to/products.csv"
        )
        ```
    """

    name: str = Field(min_length=1, max_length=255)
    """Table name (1-255 characters)."""

    file_path: str
    """Path to local CSV file."""

    data_group_id: int | None = None
    """For replacing an existing table."""


class MarkLookupTableReadyParams(BaseModel):
    """Parameters for marking a lookup table as ready.

    Attributes:
        name: Table name (required).
        key: Primary key column name (required).
        data_group_id: For replacing an existing table.

    Example:
        ```python
        params = MarkLookupTableReadyParams(name="Products", key="product_id")
        ```
    """

    name: str
    """Table name."""

    key: str
    """Primary key column name."""

    data_group_id: int | None = None
    """For replacing an existing table."""


class LookupTableUploadUrl(BaseModel):
    """Response model for lookup table upload URL request.

    Attributes:
        url: Signed GCS upload URL.
        path: GCS path for registration.
        key: Primary key column name.

    Example:
        ```python
        upload = LookupTableUploadUrl(
            url="https://storage.googleapis.com/...",
            path="gs://bucket/path",
            key="id",
        )
        ```
    """

    model_config = ConfigDict(
        frozen=True, extra="allow", alias_generator=to_camel, populate_by_name=True
    )

    url: str
    """Signed GCS upload URL."""

    path: str
    """GCS path for registration."""

    key: str
    """Primary key column name."""


class UpdateLookupTableParams(BaseModel):
    """Parameters for updating a lookup table.

    Attributes:
        name: New table name.

    Example:
        ```python
        params = UpdateLookupTableParams(name="Updated Catalog")
        ```
    """

    name: str | None = None
    """New table name."""


# =============================================================================
# Schema Registry Types (Phase 028)
# =============================================================================


class SchemaEntry(BaseModel):
    """A schema registry entry for an event, custom event, or profile.

    Represents a JSON Schema Draft 7 definition registered in the
    Mixpanel schema registry. Used for both API responses and as entries
    in bulk create/update operations.

    Attributes:
        entity_type: Entity type ("event", "custom_event", "profile").
        name: Entity name (event name or "$user" for profile).
        version: Schema version in YYYY-MM-DD format.
        schema_definition: JSON Schema Draft 7 definition (API field: schemaJson).

    Example:
        ```python
        entry = SchemaEntry(
            entity_type="event",
            name="Purchase",
            schema_definition={"properties": {"amount": {"type": "number"}}},
        )
        # Or using the API alias:
        entry = SchemaEntry(
            entityType="event", name="Purchase",
            schemaJson={"properties": {"amount": {"type": "number"}}},
        )
        ```
    """

    model_config = ConfigDict(
        frozen=True, extra="allow", alias_generator=to_camel, populate_by_name=True
    )

    entity_type: str
    """Entity type: "event", "custom_event", or "profile"."""

    name: str
    """Entity name (event name or "$user" for profile)."""

    version: str | None = None
    """Schema version in YYYY-MM-DD format."""

    schema_definition: dict[str, Any] = Field(alias="schemaJson")
    """JSON Schema Draft 7 definition (API field: schemaJson)."""


class BulkCreateSchemasParams(BaseModel):
    """Parameters for bulk-creating schemas in the registry.

    Attributes:
        entries: Schema entries to create.
        truncate: If true, delete all existing schemas of entity_type
            before inserting.
        entity_type: Entity type for all entries (only "event" supported
            for batch operations).

    Example:
        ```python
        params = BulkCreateSchemasParams(
            entries=[
                SchemaEntry(name="Login", entity_type="event", schema_definition={...}),
            ],
            truncate=True,
            entity_type="event",
        )
        ```
    """

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    entries: list[SchemaEntry]
    """Schema entries to create."""

    truncate: bool | None = None
    """If true, delete all existing schemas of entity_type before inserting."""

    entity_type: str | None = None
    """Entity type for all entries (only "event" supported for batch)."""


class BulkCreateSchemasResponse(BaseModel):
    """Response from a bulk schema creation operation.

    Attributes:
        added: Number of schemas added.
        deleted: Number of schemas deleted (from truncate).

    Example:
        ```python
        resp = BulkCreateSchemasResponse(added=5, deleted=3)
        ```
    """

    model_config = ConfigDict(frozen=True, extra="allow")

    added: int
    """Number of schemas added."""

    deleted: int
    """Number of schemas deleted (from truncate)."""


class BulkPatchResult(BaseModel):
    """Per-entry result from a bulk schema update operation.

    Attributes:
        entity_type: Entity type processed.
        name: Entity name processed.
        status: Result status ("ok" or "error").
        error: Error message if status is "error".

    Example:
        ```python
        result = BulkPatchResult(
            entity_type="event", name="Login", status="ok"
        )
        ```
    """

    model_config = ConfigDict(
        frozen=True, extra="allow", alias_generator=to_camel, populate_by_name=True
    )

    entity_type: str
    """Entity type processed."""

    name: str
    """Entity name processed."""

    status: str
    """Result status ("ok" or "error")."""

    error: str | None = None
    """Error message if status is "error"."""


class DeleteSchemasResponse(BaseModel):
    """Response from a schema deletion operation.

    Attributes:
        delete_count: Number of schemas deleted.

    Example:
        ```python
        resp = DeleteSchemasResponse(delete_count=3)
        ```
    """

    model_config = ConfigDict(
        frozen=True, extra="allow", alias_generator=to_camel, populate_by_name=True
    )

    delete_count: int
    """Number of schemas deleted."""


# =============================================================================
# Schema Enforcement Types (Phase 028)
# =============================================================================


class SchemaEnforcementConfig(BaseModel):
    """Schema enforcement configuration for a project.

    Controls how Mixpanel handles events that don't match defined schemas.

    Attributes:
        id: Config ID.
        last_modified: Last modification timestamp.
        last_modified_by: User who last modified.
        rule_event: Enforcement action ("Warn and Accept", "Warn and Hide",
            "Warn and Drop").
        notification_emails: Notification recipients.
        events: Event enforcement rules.
        common_properties: Common property rules.
        user_properties: User property rules.
        initialized_by: User who initialized.
        initialized_from: Initialization start date.
        initialized_to: Initialization end date.
        state: Enforcement state ("planned" or "ingested").

    Example:
        ```python
        config = SchemaEnforcementConfig(
            id=1, rule_event="Warn and Accept", state="ingested"
        )
        ```
    """

    model_config = ConfigDict(
        frozen=True, extra="allow", alias_generator=to_camel, populate_by_name=True
    )

    id: int | None = None
    """Config ID."""

    last_modified: str | None = None
    """Last modification timestamp."""

    last_modified_by: dict[str, Any] | None = None
    """User who last modified."""

    rule_event: str | None = None
    """Enforcement action: "Warn and Accept", "Warn and Hide", "Warn and Drop"."""

    notification_emails: list[str] | None = None
    """Notification recipients."""

    events: list[dict[str, Any]] | None = None
    """Event enforcement rules."""

    common_properties: list[dict[str, Any]] | None = None
    """Common property rules."""

    user_properties: list[dict[str, Any]] | None = None
    """User property rules."""

    initialized_by: dict[str, Any] | None = None
    """User who initialized."""

    initialized_from: str | None = None
    """Initialization start date."""

    initialized_to: str | None = None
    """Initialization end date."""

    state: str | None = None
    """Enforcement state ("planned" or "ingested")."""


class InitSchemaEnforcementParams(BaseModel):
    """Parameters for initializing schema enforcement.

    Attributes:
        rule_event: Enforcement action ("Warn and Accept", "Warn and Hide",
            "Warn and Drop").

    Example:
        ```python
        params = InitSchemaEnforcementParams(rule_event="Warn and Accept")
        ```
    """

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    rule_event: str
    """Enforcement action."""


class UpdateSchemaEnforcementParams(BaseModel):
    """Parameters for partially updating schema enforcement.

    Attributes:
        notification_emails: Updated notification recipients.
        rule_event: Updated enforcement action.
        events: Updated event list.
        properties: Updated property map.

    Example:
        ```python
        params = UpdateSchemaEnforcementParams(
            rule_event="Warn and Drop",
            notification_emails=["data-team@example.com"],
        )
        ```
    """

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    notification_emails: list[str] | None = None
    """Updated notification recipients."""

    rule_event: str | None = None
    """Updated enforcement action."""

    events: list[str] | None = None
    """Updated event list."""

    properties: dict[str, list[str]] | None = None
    """Updated property map."""


class ReplaceSchemaEnforcementParams(BaseModel):
    """Parameters for fully replacing schema enforcement configuration.

    All fields are required since this is a full replacement.

    Attributes:
        common_properties: Full common property rules.
        user_properties: Full user property rules.
        events: Full event rules.
        rule_event: Enforcement action.
        notification_emails: Notification recipients.
        schema_id: Schema definition ID.

    Example:
        ```python
        params = ReplaceSchemaEnforcementParams(
            events=[...],
            common_properties=[...],
            user_properties=[...],
            rule_event="Warn and Hide",
            notification_emails=["admin@example.com"],
        )
        ```
    """

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    common_properties: list[dict[str, Any]]
    """Full common property rules."""

    user_properties: list[dict[str, Any]]
    """Full user property rules."""

    events: list[dict[str, Any]]
    """Full event rules."""

    rule_event: str
    """Enforcement action."""

    notification_emails: list[str]
    """Notification recipients."""

    schema_id: int | None = None
    """Schema definition ID."""


# =============================================================================
# Data Audit Types (Phase 028)
# =============================================================================


class AuditViolation(BaseModel):
    """A single violation found during a data audit.

    Attributes:
        violation: Violation type (e.g., "Unexpected Event",
            "Missing Property", "Unexpected Type for Property").
        name: Property or event name.
        platform: Platform ("iOS", "Android", "Web").
        version: Version string.
        count: Number of occurrences.
        event: Event name (for property violations).
        sensitive: Whether property is marked sensitive.
        property_type_error: Type mismatch description.

    Example:
        ```python
        v = AuditViolation(
            violation="Unexpected Event", name="DebugLog", count=42
        )
        ```
    """

    model_config = ConfigDict(
        frozen=True, extra="allow", alias_generator=to_camel, populate_by_name=True
    )

    violation: str
    """Violation type."""

    name: str
    """Property or event name."""

    platform: str | None = None
    """Platform: "iOS", "Android", "Web"."""

    version: str | None = None
    """Version string."""

    count: int
    """Number of occurrences."""

    event: str | None = None
    """Event name (for property violations)."""

    sensitive: bool | None = None
    """Whether property is marked sensitive."""

    property_type_error: str | None = None
    """Type mismatch description."""


class AuditResponse(BaseModel):
    """Response from a data audit operation.

    Contains a list of schema violations and the timestamp when
    the audit was computed.

    Attributes:
        violations: List of audit violations.
        computed_at: Timestamp of audit computation.

    Example:
        ```python
        resp = AuditResponse(
            violations=[
                AuditViolation(violation="Unexpected Event", name="Debug", count=1)
            ],
            computed_at="2026-04-01T12:00:00Z",
        )
        ```
    """

    model_config = ConfigDict(frozen=True, extra="allow")

    violations: list[AuditViolation]
    """List of audit violations."""

    computed_at: str
    """Timestamp of audit computation."""


# =============================================================================
# Data Volume Anomaly Types (Phase 028)
# =============================================================================


class DataVolumeAnomaly(BaseModel):
    """A detected data volume anomaly.

    Attributes:
        id: Anomaly ID.
        timestamp: Detection timestamp.
        actual_count: Actual observed count.
        predicted_upper: Upper bound of prediction.
        predicted_lower: Lower bound of prediction.
        percent_variance: Variance percentage.
        status: Anomaly status ("open" or "dismissed").
        project: Project ID.
        event: Event ID.
        event_name: Event name.
        property: Property ID.
        property_name: Property name.
        metric: Metric ID.
        metric_name: Metric name.
        metric_type: Metric type.
        primary_type: Primary anomaly type.
        drift_types: Drift type details.
        anomaly_class: Anomaly class ("Event", "Property",
            "PropertyTypeDrift", "Metric").

    Example:
        ```python
        anomaly = DataVolumeAnomaly(
            id=1, actual_count=1000, predicted_upper=500,
            predicted_lower=100, percent_variance="100%",
            status="open", project=12345, anomaly_class="Event",
        )
        ```
    """

    model_config = ConfigDict(
        frozen=True, extra="allow", alias_generator=to_camel, populate_by_name=True
    )

    id: int
    """Anomaly ID."""

    timestamp: str | None = None
    """Detection timestamp."""

    actual_count: int
    """Actual observed count."""

    predicted_upper: int
    """Upper bound of prediction."""

    predicted_lower: int
    """Lower bound of prediction."""

    percent_variance: str
    """Variance percentage."""

    status: str
    """Anomaly status ("open" or "dismissed")."""

    project: int
    """Project ID."""

    event: int | None = None
    """Event ID."""

    event_name: str | None = None
    """Event name."""

    property: int | None = None
    """Property ID."""

    property_name: str | None = None
    """Property name."""

    metric: int | None = None
    """Metric ID."""

    metric_name: str | None = None
    """Metric name."""

    metric_type: str | None = None
    """Metric type."""

    primary_type: str | None = None
    """Primary anomaly type."""

    drift_types: dict[str, Any] | None = None
    """Drift type details."""

    anomaly_class: str
    """Anomaly class: "Event", "Property", "PropertyTypeDrift", "Metric"."""


class UpdateAnomalyParams(BaseModel):
    """Parameters for updating a single anomaly status.

    Attributes:
        id: Anomaly ID.
        status: New status ("open" or "dismissed").
        anomaly_class: Anomaly class.

    Example:
        ```python
        params = UpdateAnomalyParams(
            id=123, status="dismissed", anomaly_class="Event"
        )
        ```
    """

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    id: int
    """Anomaly ID."""

    status: str
    """New status: "open" or "dismissed"."""

    anomaly_class: str
    """Anomaly class."""


class BulkAnomalyEntry(BaseModel):
    """A single entry in a bulk anomaly update.

    Attributes:
        id: Anomaly ID.
        anomaly_class: Anomaly class.

    Example:
        ```python
        entry = BulkAnomalyEntry(id=123, anomaly_class="Event")
        ```
    """

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    id: int
    """Anomaly ID."""

    anomaly_class: str
    """Anomaly class."""


class BulkUpdateAnomalyParams(BaseModel):
    """Parameters for bulk-updating anomaly statuses.

    Attributes:
        anomalies: Anomalies to update.
        status: New status for all ("open" or "dismissed").

    Example:
        ```python
        params = BulkUpdateAnomalyParams(
            anomalies=[BulkAnomalyEntry(id=1, anomaly_class="Event")],
            status="dismissed",
        )
        ```
    """

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    anomalies: list[BulkAnomalyEntry]
    """Anomalies to update."""

    status: str
    """New status for all."""


# =============================================================================
# Event Deletion Request Types (Phase 028)
# =============================================================================


class EventDeletionRequest(BaseModel):
    """An event deletion request with lifecycle status.

    Attributes:
        id: Request ID.
        display_name: Display name.
        event_name: Event to delete.
        from_date: Start date.
        to_date: End date.
        filters: Deletion filters.
        status: Request status ("Submitted", "Processing", "Completed", "Failed").
        deleted_events_count: Count of deleted events.
        created: Creation timestamp.
        requesting_user: User who requested.

    Example:
        ```python
        req = EventDeletionRequest(
            id=1, event_name="Test", from_date="2026-01-01",
            to_date="2026-01-31", status="Submitted",
            deleted_events_count=0, created="2026-04-01",
            requesting_user={"id": 1},
        )
        ```
    """

    model_config = ConfigDict(
        frozen=True, extra="allow", alias_generator=to_camel, populate_by_name=True
    )

    id: int
    """Request ID."""

    display_name: str | None = None
    """Display name."""

    event_name: str
    """Event to delete."""

    from_date: str
    """Start date."""

    to_date: str
    """End date."""

    filters: dict[str, Any] | None = None
    """Deletion filters (dict when populated, None when absent)."""

    @field_validator("filters", mode="before")
    @classmethod
    def _normalize_filters(
        cls,
        v: dict[str, Any] | list[Any] | None,
    ) -> dict[str, Any] | None:
        """Coerce empty list from API to None."""
        if not isinstance(v, list):
            return v
        if len(v) == 0:
            return None
        # Non-empty list is unexpected; wrap in dict for forward compatibility.
        return {"items": v}

    status: str
    """Request status: "Submitted", "Processing", "Completed", "Failed"."""

    deleted_events_count: int
    """Count of deleted events."""

    created: str
    """Creation timestamp."""

    requesting_user: dict[str, Any]
    """User who requested."""


class CreateDeletionRequestParams(BaseModel):
    """Parameters for creating an event deletion request.

    Attributes:
        from_date: Start date (YYYY-MM-DD or datetime).
        to_date: End date.
        event_name: Event name to delete.
        filters: Optional deletion filters.

    Example:
        ```python
        params = CreateDeletionRequestParams(
            event_name="Test Event",
            from_date="2026-01-01",
            to_date="2026-01-31",
        )
        ```
    """

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    from_date: str
    """Start date (YYYY-MM-DD or datetime)."""

    to_date: str
    """End date."""

    event_name: str
    """Event name to delete."""

    filters: dict[str, Any] | None = None
    """Optional deletion filters."""


class PreviewDeletionFiltersParams(BaseModel):
    """Parameters for previewing event deletion filters.

    This is a read-only operation that shows what events would match.

    Attributes:
        event_name: Event name.
        from_date: Start date.
        to_date: End date.
        filters: Optional filters.

    Example:
        ```python
        params = PreviewDeletionFiltersParams(
            event_name="Test Event",
            from_date="2026-01-01",
            to_date="2026-01-31",
        )
        ```
    """

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    event_name: str
    """Event name."""

    from_date: str
    """Start date."""

    to_date: str
    """End date."""

    filters: dict[str, Any] | None = None
    """Optional filters."""


# =============================================================================
# Profile Page Result (API pagination)
# =============================================================================


@dataclass(frozen=True)
class ProfilePageResult:
    """Result from fetching a single page of profiles.

    Contains the profiles from one page of the Engage API along with
    pagination metadata for fetching subsequent pages.

    Attributes:
        profiles: List of profile dictionaries from this page.
        session_id: Session ID for fetching next page, None if no more pages.
        page: Zero-based page index that was fetched.
        has_more: True if there are more pages to fetch.
        total: Total number of profiles matching the query across all pages.
        page_size: Number of profiles per page (typically 1000).

    Example:
        ```python
        # Fetch first page to get pagination metadata
        result = api_client.export_profiles_page(page=0)
        all_profiles = list(result.profiles)

        # Pre-compute total pages for parallel fetching
        total_pages = result.num_pages
        print(f"Fetching {total_pages} pages ({result.total} profiles)")

        # Continue fetching if more pages
        while result.has_more:
            result = api_client.export_profiles_page(
                page=result.page + 1,
                session_id=result.session_id,
            )
            all_profiles.extend(result.profiles)
        ```
    """

    profiles: list[dict[str, Any]]
    """List of profile dictionaries from this page."""

    session_id: str | None
    """Session ID for fetching next page, None if no more pages."""

    page: int
    """Zero-based page index that was fetched."""

    has_more: bool
    """True if there are more pages to fetch."""

    total: int
    """Total number of profiles matching the query across all pages."""

    page_size: int
    """Number of profiles per page (typically 1000)."""

    @property
    def num_pages(self) -> int:
        """Calculate total number of pages needed.

        Uses ceiling division to ensure partial pages are counted.

        Returns:
            Total pages needed to fetch all profiles.
            Returns 0 if total is 0 (empty result set).

        Example:
            ```python
            result = api_client.export_profiles_page(page=0)
            # If total=5432 and page_size=1000, num_pages=6
            for page_idx in range(1, result.num_pages):
                # Fetch remaining pages...
            ```
        """
        if self.total == 0:
            return 0
        return math.ceil(self.total / self.page_size)

    def to_dict(self) -> dict[str, Any]:
        """Serialize for JSON output.

        Returns:
            Dictionary with all page result fields including pagination metadata.
        """
        return {
            "profiles": self.profiles,
            "session_id": self.session_id,
            "page": self.page,
            "has_more": self.has_more,
            "profile_count": len(self.profiles),
            "total": self.total,
            "page_size": self.page_size,
            "num_pages": self.num_pages,
        }


# =============================================================================
# Custom Property Query Types (Phase 037)
# =============================================================================


@dataclass(frozen=True)
class PropertyInput:
    """A raw property reference mapping a formula variable to a named property.

    Used as an entry in :attr:`InlineCustomProperty.inputs` to bind a
    formula variable (A-Z) to a concrete Mixpanel event or user property.

    Attributes:
        name: The raw property name (e.g., ``"price"``, ``"$browser"``).
        type: Property data type. Default: ``"string"``.
        resource_type: Property domain — ``"event"`` or ``"user"``.
            Uses singular form to match Mixpanel's ``composedProperties``
            schema. Default: ``"event"``.

    Example:
        ```python
        from mixpanel_headless import PropertyInput

        pi = PropertyInput("price", type="number")
        pi_user = PropertyInput("email", resource_type="user")
        ```
    """

    name: str
    """The raw property name."""

    type: Literal["string", "number", "boolean", "datetime", "list"] = "string"
    """Property data type."""

    resource_type: Literal["event", "user"] = "event"
    """Property domain (singular form for composedProperties schema)."""


@dataclass(frozen=True)
class InlineCustomProperty:
    """An ephemeral computed property defined by a formula and input references.

    Defines a custom property inline at query time without persisting it
    to Mixpanel. The formula uses variables (A-Z) that map to concrete
    properties via the ``inputs`` dict.

    Can be used in ``GroupBy.property``, ``Filter`` class methods, and
    ``Metric.property`` to compute derived values on the fly.

    Attributes:
        formula: Expression in Mixpanel's formula language (max 20,000 chars).
        inputs: Mapping from single uppercase letters (A-Z) to property
            references.
        property_type: Result type of the formula. ``None`` defers to
            the containing type (e.g., ``GroupBy.property_type``).
            Default: ``None``.
        resource_type: Data domain — ``"events"`` or ``"people"``.
            Uses plural form to match Mixpanel's top-level
            ``customProperty`` schema. Default: ``"events"``.

    Example:
        ```python
        from mixpanel_headless import InlineCustomProperty, PropertyInput

        # Explicit construction
        icp = InlineCustomProperty(
            formula="A * B",
            inputs={
                "A": PropertyInput("price", type="number"),
                "B": PropertyInput("quantity", type="number"),
            },
            property_type="number",
        )

        # Convenience constructor for all-numeric inputs
        icp = InlineCustomProperty.numeric("A * B", A="price", B="quantity")
        ```
    """

    formula: str
    """Expression in Mixpanel's formula language."""

    inputs: dict[str, PropertyInput]
    """Mapping from single uppercase letters (A-Z) to property references."""

    property_type: Literal["string", "number", "boolean", "datetime"] | None = None
    """Result type of the formula; None defers to containing type."""

    resource_type: Literal["events", "people"] = "events"
    """Data domain (plural form for top-level customProperty schema)."""

    @classmethod
    def numeric(
        cls,
        formula: str,
        /,
        **properties: str,
    ) -> InlineCustomProperty:
        """Create an all-numeric-input inline custom property.

        Convenience constructor that creates ``PropertyInput`` entries
        with ``type="number"`` and ``resource_type="event"`` for each
        keyword argument, and sets ``property_type="number"``.

        Args:
            formula: Expression in Mixpanel's formula language.
            **properties: Mapping of variable letters to property names.
                Each key becomes an input key, each value becomes the
                property name.

        Returns:
            InlineCustomProperty with all-numeric inputs and
            ``property_type="number"``.

        Example:
            ```python
            # Revenue = price * quantity
            icp = InlineCustomProperty.numeric("A * B", A="price", B="quantity")
            assert icp.inputs["A"].type == "number"
            assert icp.property_type == "number"
            ```
        """
        inputs = {
            key: PropertyInput(name=value, type="number")
            for key, value in properties.items()
        }
        return cls(
            formula=formula,
            inputs=inputs,
            property_type="number",
        )


@dataclass(frozen=True)
class CustomPropertyRef:
    """A reference to a persisted custom property by its integer ID.

    Used in ``GroupBy.property``, ``Filter`` class methods, and
    ``Metric.property`` to reference a custom property that was
    previously created and saved in Mixpanel.

    Attributes:
        id: The custom property's server-assigned ID (must be positive).

    Example:
        ```python
        from mixpanel_headless import CustomPropertyRef, GroupBy

        ref = CustomPropertyRef(42)
        g = GroupBy(property=ref, property_type="number")
        ```
    """

    id: int
    """The custom property's server-assigned ID."""


PropertySpec = str | CustomPropertyRef | InlineCustomProperty
"""Union type for property specifications in query parameters.

Accepted wherever a property can be specified: ``Metric.property``,
``GroupBy.property``, and ``Filter`` class method ``property`` parameters.
"""


# =============================================================================
# Query API Types (Phase 029)
# =============================================================================

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
"""Regex for YYYY-MM-DD date format validation."""


@dataclass(frozen=True)
class TimeComparison:
    """Overlay a comparison time period on insights, funnel, or retention queries.

    Enables period-over-period analysis by specifying how the comparison
    window is determined. Three modes are supported:

    - **relative**: Compare against a prior period offset by ``unit``
      (e.g. previous month, previous week).
    - **absolute-start**: Compare against a window starting on a fixed
      date (``date``), running the same duration as the primary range.
    - **absolute-end**: Compare against a window ending on a fixed date.

    Use the factory class methods rather than constructing directly:

    - ``TimeComparison.relative(unit)``
    - ``TimeComparison.absolute_start(date)``
    - ``TimeComparison.absolute_end(date)``

    Attributes:
        type: Discriminant — ``"relative"``, ``"absolute-start"``, or
            ``"absolute-end"``.
        unit: Time unit for relative comparison. Required when
            ``type="relative"``, must be ``None`` otherwise.
        date: ISO date (YYYY-MM-DD) for absolute comparison. Required
            when ``type`` is ``"absolute-start"`` or ``"absolute-end"``,
            must be ``None`` otherwise.

    Raises:
        ValueError: If validation rules TC1-TC3 are violated during
            construction.

    Example:
        ```python
        from mixpanel_headless.types import TimeComparison

        # Compare against previous month
        tc = TimeComparison.relative("month")

        # Compare against window starting on a fixed date
        tc = TimeComparison.absolute_start("2026-01-01")

        # Compare against window ending on a fixed date
        tc = TimeComparison.absolute_end("2026-12-31")
        ```
    """

    type: TimeComparisonType
    """Discriminant — ``"relative"``, ``"absolute-start"``, or ``"absolute-end"``."""

    unit: TimeComparisonUnit | None = None
    """Time unit for relative comparison (day, week, month, quarter, year)."""

    date: str | None = None
    """ISO date (YYYY-MM-DD) for absolute comparison."""

    def __post_init__(self) -> None:
        """Validate construction arguments (rules TC1-TC3).

        Raises:
            ValueError: If type="relative" and unit is None (TC1),
                or type="relative" and date is set (TC1),
                or type is absolute and date is None (TC2),
                or type is absolute and unit is set (TC2),
                or date does not match YYYY-MM-DD format (TC3).
        """
        # TC0: type must be a valid TimeComparisonType
        valid_types = {"relative", "absolute-start", "absolute-end"}
        if self.type not in valid_types:
            raise ValueError(
                f"TimeComparison type must be one of {sorted(valid_types)}, "
                f"got {self.type!r}"
            )
        if self.type == "relative":
            # TC1: relative requires unit, rejects date
            if self.unit is None:
                raise ValueError(
                    "TimeComparison type='relative' requires unit to be set "
                    "(e.g., TimeComparison.relative('month'))"
                )
            # TC1b: unit must be a valid TimeComparisonUnit
            valid_units = {"day", "week", "month", "quarter", "year"}
            if self.unit not in valid_units:
                raise ValueError(
                    f"TimeComparison unit must be one of {sorted(valid_units)}, "
                    f"got {self.unit!r}"
                )
            if self.date is not None:
                raise ValueError(
                    "TimeComparison type='relative' does not accept date; "
                    "use absolute-start or absolute-end for date-based comparison"
                )
        else:
            # TC2: absolute-start / absolute-end requires date, rejects unit
            if self.date is None:
                raise ValueError(
                    f"TimeComparison type={self.type!r} requires date to be set "
                    f"(e.g., TimeComparison.absolute_start('2026-01-01'))"
                )
            if self.unit is not None:
                raise ValueError(
                    f"TimeComparison type={self.type!r} does not accept unit; "
                    f"unit is only valid for type='relative'"
                )
            # TC3: date must be a valid YYYY-MM-DD calendar date
            if not _DATE_RE.match(self.date):
                raise ValueError(
                    f"TimeComparison date must be in YYYY-MM-DD format, "
                    f"got {self.date!r}"
                )
            # TC3b: verify it's a real calendar date (e.g. reject 2026-02-30)
            try:
                import datetime

                datetime.date.fromisoformat(self.date)
            except ValueError:
                raise ValueError(
                    f"TimeComparison date is not a valid calendar date: {self.date!r}"
                ) from None

    @classmethod
    def relative(cls, unit: TimeComparisonUnit) -> TimeComparison:
        """Create a relative time comparison.

        Compares against a prior period offset by the given unit
        (e.g. previous month, previous week).

        Args:
            unit: Time unit for the comparison offset. One of
                ``"day"``, ``"week"``, ``"month"``, ``"quarter"``,
                ``"year"``.

        Returns:
            A ``TimeComparison`` with ``type="relative"`` and the
            specified ``unit``.

        Example:
            ```python
            tc = TimeComparison.relative("month")
            # type="relative", unit="month", date=None
            ```
        """
        return cls(type="relative", unit=unit)

    @classmethod
    def absolute_start(cls, date: str) -> TimeComparison:
        """Create an absolute-start time comparison.

        Compares against a window that starts on the given date,
        running the same duration as the primary query range.

        Args:
            date: Start date in YYYY-MM-DD format.

        Returns:
            A ``TimeComparison`` with ``type="absolute-start"`` and
            the specified ``date``.

        Raises:
            ValueError: If date is not in YYYY-MM-DD format (TC3).

        Example:
            ```python
            tc = TimeComparison.absolute_start("2026-01-01")
            # type="absolute-start", unit=None, date="2026-01-01"
            ```
        """
        return cls(type="absolute-start", date=date)

    @classmethod
    def absolute_end(cls, date: str) -> TimeComparison:
        """Create an absolute-end time comparison.

        Compares against a window that ends on the given date,
        running the same duration as the primary query range.

        Args:
            date: End date in YYYY-MM-DD format.

        Returns:
            A ``TimeComparison`` with ``type="absolute-end"`` and
            the specified ``date``.

        Raises:
            ValueError: If date is not in YYYY-MM-DD format (TC3).

        Example:
            ```python
            tc = TimeComparison.absolute_end("2026-12-31")
            # type="absolute-end", unit=None, date="2026-12-31"
            ```
        """
        return cls(type="absolute-end", date=date)


@dataclass(frozen=True)
class Metric:
    """Encapsulates a single event to query with its aggregation settings.

    Used with ``Workspace.query()`` to specify per-event math, property,
    per-user aggregation, and filters. Plain event name strings inherit
    top-level query defaults; Metric objects override them.

    Attributes:
        event: Mixpanel event name.
        math: Aggregation function. Default: ``"total"``.
        property: Property for property-based math types (name, ref, or inline).
        per_user: Per-user pre-aggregation (average, total, min, max).
        filters: Per-metric filters (applied in addition to global ``where``).
        filters_combinator: How per-metric filters combine.
            ``"all"`` = AND (default), ``"any"`` = OR.

    Example:
        ```python
        from mixpanel_headless import Metric

        # Simple event with defaults
        m1 = Metric("Login")

        # With aggregation
        m2 = Metric("Purchase", math="average", property="amount")

        # With per-user aggregation
        m3 = Metric("Purchase", math="total", per_user="average")
        ```
    """

    event: str
    """Mixpanel event name."""

    math: MathType = "total"
    """Aggregation function."""

    property: str | CustomPropertyRef | InlineCustomProperty | None = None
    """Property for property-based math types (name, ref, or inline)."""

    per_user: PerUserAggregation | None = None
    """Per-user pre-aggregation type."""

    percentile_value: int | float | None = None
    """Custom percentile value (e.g. 95 for p95).

    Required when ``math="percentile"``. Ignored for other math types.
    Maps to ``percentile`` in bookmark JSON.
    """

    filters: list[Filter] | None = None
    """Per-metric filters (list of Filter objects)."""

    filters_combinator: FiltersCombinator = "all"
    """How per-metric filters combine (``"all"`` = AND, ``"any"`` = OR)."""

    segment_method: SegmentMethod | None = None
    """Segment method for counting qualifying events.

    Controls how events are counted per user: ``"all"`` counts every
    qualifying event (default server behavior), ``"first"`` counts
    only the first qualifying event per user.

    Maps to ``segmentMethod`` in the bookmark measurement block.
    """

    def __post_init__(self) -> None:
        """Validate construction arguments.

        Raises:
            ValueError: If event is empty or contains control characters
                (M1), math requires a property but none is set (M2),
                or math="percentile" but percentile_value is missing (M3).
        """
        _validate_event_name(self.event, "Metric")
        if self.math in _MATH_REQUIRING_PROPERTY and self.property is None:
            raise ValueError(
                f"Metric math={self.math!r} requires a property "
                f"to be set (e.g., Metric({self.event!r}, math={self.math!r}, "
                f'property="your_property"))'
            )
        if self.math == "percentile" and self.percentile_value is None:
            raise ValueError(
                'Metric math="percentile" requires percentile_value '
                "(e.g., Metric(event, math='percentile', percentile_value=95))"
            )
        # M4: segment_method must be valid if set
        if self.segment_method is not None:
            valid_segments = {"all", "first"}
            if self.segment_method not in valid_segments:
                raise ValueError(
                    f"Metric segment_method must be one of {sorted(valid_segments)}, "
                    f"got {self.segment_method!r}"
                )


@dataclass(frozen=True)
class Formula:
    """A formula expression referencing events by position letter (A, B, C...).

    Letters map to event positions in the list passed to
    ``Workspace.query()``. A is the first event, B the second, etc.

    Can be passed as an element of the events list alongside strings
    and ``Metric`` objects, or use the top-level ``formula`` parameter
    for single-formula convenience.

    Attributes:
        expression: Formula expression, e.g. ``"(B / A) * 100"``.
        label: Optional display label for the formula result.

    Example:
        ```python
        from mixpanel_headless import Formula, Metric

        # Formula in the events list
        result = ws.query(
            [Metric("Signup", math="unique"),
             Metric("Purchase", math="unique"),
             Formula("(B / A) * 100", label="Conversion %")],
        )

        # Equivalent using top-level parameter
        result = ws.query(
            [Metric("Signup", math="unique"),
             Metric("Purchase", math="unique")],
            formula="(B / A) * 100",
            formula_label="Conversion %",
        )
        ```
    """

    expression: str
    """Formula expression referencing events by letter."""

    label: str | None = None
    """Optional display label for the formula result."""

    def __post_init__(self) -> None:
        """Validate construction arguments.

        Raises:
            ValueError: If expression is empty (FM1).
        """
        if not self.expression or not self.expression.strip():
            raise ValueError("Formula.expression must be a non-empty string")


@dataclass(frozen=True)
class Filter:
    """Represents a typed filter condition on a property.

    Constructed exclusively via class methods — never instantiated directly.
    Each class method maps to specific filterType, filterOperator, and
    filterValue format in the bookmark JSON.

    Example:
        ```python
        from mixpanel_headless import Filter

        f1 = Filter.equals("country", "US")
        f2 = Filter.greater_than("age", 18)
        f3 = Filter.between("amount", 10, 100)
        f4 = Filter.is_set("email")
        ```
    """

    _property: str | CustomPropertyRef | InlineCustomProperty
    """Property to filter on (name, ref, or inline)."""

    _operator: FilterOperator
    """Internal operator string. Must be one of the values in :data:`FilterOperator`."""

    _value: (
        str | int | float | list[str] | list[int | float] | list[dict[str, Any]] | None
    )
    """Value(s) to compare against.

    Shape varies by operator: list for equals/not_equals, str for
    contains/not_contains, numeric for greater_than/less_than,
    two-element list for between, None for is_set/is_not_set/is_true/is_false,
    list of dicts for cohort filters (in_cohort/not_in_cohort).
    """

    _property_type: FilterPropertyType = "string"
    """Data type of the property."""

    _resource_type: Literal["events", "people"] = "events"
    """Resource type to filter."""

    _date_unit: FilterDateUnit | None = None
    """Time unit for relative date filters (hour, day, week, month).

    Set by ``in_the_last()``, ``not_in_the_last()``, and ``in_the_next()`` factory methods.
    Maps to ``filterDateUnit`` in bookmark JSON. ``None`` for non-date
    and absolute date filters.
    """

    _list_item_filters: tuple[Filter, ...] | None = None
    """Sub-filters for ``list_contains``, evaluated per-item against a list-of-objects property."""

    _list_item_quantifier: Literal["any", "all"] | None = None
    """Quantifier for ``list_contains``: ``"any"`` (≥1 item matches) or ``"all"`` (every item matches)."""

    def __post_init__(self) -> None:
        """Validate Filter mode invariants.

        Only validates the ``list_contains`` mode today. Other operator
        modes rely on classmethod-only validation; expanding this
        coverage is a separate concern from this PR's list_contains
        feature.

        Raises:
            ValueError: If ``_operator == "list_contains"`` but
                ``_list_item_filters`` or ``_list_item_quantifier`` is
                ``None``. List-contains filters must be constructed
                via ``Filter.list_contains(...)``.
        """
        if self._operator == "list_contains":
            if self._list_item_filters is None:
                raise ValueError(
                    "list_contains Filter requires _list_item_filters; "
                    "construct via Filter.list_contains(...)"
                )
            if self._list_item_quantifier is None:
                raise ValueError(
                    "list_contains Filter requires _list_item_quantifier; "
                    "construct via Filter.list_contains(...)"
                )

    @classmethod
    def equals(
        cls,
        property: str | CustomPropertyRef | InlineCustomProperty,
        value: str | list[str],
        *,
        resource_type: Literal["events", "people"] = "events",
    ) -> Filter:
        """Create an equality filter.

        Args:
            property: Property name, CustomPropertyRef, or InlineCustomProperty.
            value: Value or list of values.
            resource_type: Resource type. Default: ``"events"``.

        Returns:
            Filter for string equality.
        """
        val = [value] if isinstance(value, str) else value
        return cls(
            _property=property,
            _operator="equals",
            _value=val,
            _property_type="string",
            _resource_type=resource_type,
        )

    @classmethod
    def not_equals(
        cls,
        property: str | CustomPropertyRef | InlineCustomProperty,
        value: str | list[str],
        *,
        resource_type: Literal["events", "people"] = "events",
    ) -> Filter:
        """Create a not-equals filter.

        Args:
            property: Property name, CustomPropertyRef, or InlineCustomProperty.
            value: Value or list of values.
            resource_type: Resource type. Default: ``"events"``.

        Returns:
            Filter for string inequality.
        """
        val = [value] if isinstance(value, str) else value
        return cls(
            _property=property,
            _operator="does not equal",
            _value=val,
            _property_type="string",
            _resource_type=resource_type,
        )

    @classmethod
    def contains(
        cls,
        property: str | CustomPropertyRef | InlineCustomProperty,
        value: str,
        *,
        resource_type: Literal["events", "people"] = "events",
    ) -> Filter:
        """Create a contains (substring) filter.

        Args:
            property: Property name, CustomPropertyRef, or InlineCustomProperty.
            value: Substring to match.
            resource_type: Resource type. Default: ``"events"``.

        Returns:
            Filter for substring containment.
        """
        return cls(
            _property=property,
            _operator="contains",
            _value=value,
            _property_type="string",
            _resource_type=resource_type,
        )

    @classmethod
    def not_contains(
        cls,
        property: str | CustomPropertyRef | InlineCustomProperty,
        value: str,
        *,
        resource_type: Literal["events", "people"] = "events",
    ) -> Filter:
        """Create a not-contains filter.

        Args:
            property: Property name, CustomPropertyRef, or InlineCustomProperty.
            value: Substring that must not match.
            resource_type: Resource type. Default: ``"events"``.

        Returns:
            Filter for substring non-containment.
        """
        return cls(
            _property=property,
            _operator="does not contain",
            _value=value,
            _property_type="string",
            _resource_type=resource_type,
        )

    @classmethod
    def greater_than(
        cls,
        property: str | CustomPropertyRef | InlineCustomProperty,
        value: int | float,
        *,
        resource_type: Literal["events", "people"] = "events",
    ) -> Filter:
        """Create a greater-than filter.

        Args:
            property: Property name, CustomPropertyRef, or InlineCustomProperty.
            value: Numeric threshold.
            resource_type: Resource type. Default: ``"events"``.

        Returns:
            Filter for numeric greater-than.
        """
        return cls(
            _property=property,
            _operator="is greater than",
            _value=value,
            _property_type="number",
            _resource_type=resource_type,
        )

    @classmethod
    def less_than(
        cls,
        property: str | CustomPropertyRef | InlineCustomProperty,
        value: int | float,
        *,
        resource_type: Literal["events", "people"] = "events",
    ) -> Filter:
        """Create a less-than filter.

        Args:
            property: Property name, CustomPropertyRef, or InlineCustomProperty.
            value: Numeric threshold.
            resource_type: Resource type. Default: ``"events"``.

        Returns:
            Filter for numeric less-than.
        """
        return cls(
            _property=property,
            _operator="is less than",
            _value=value,
            _property_type="number",
            _resource_type=resource_type,
        )

    @classmethod
    def between(
        cls,
        property: str | CustomPropertyRef | InlineCustomProperty,
        min_val: int | float,
        max_val: int | float,
        *,
        resource_type: Literal["events", "people"] = "events",
    ) -> Filter:
        """Create a between (inclusive range) filter.

        Args:
            property: Property name, CustomPropertyRef, or InlineCustomProperty.
            min_val: Minimum value (inclusive).
            max_val: Maximum value (inclusive).
            resource_type: Resource type. Default: ``"events"``.

        Returns:
            Filter for numeric range.
        """
        return cls(
            _property=property,
            _operator="is between",
            _value=[min_val, max_val],
            _property_type="number",
            _resource_type=resource_type,
        )

    @classmethod
    def not_between(
        cls,
        property: str | CustomPropertyRef | InlineCustomProperty,
        min_val: int | float,
        max_val: int | float,
        *,
        resource_type: Literal["events", "people"] = "events",
    ) -> Filter:
        """Create a not-between (exclusive range) filter.

        Args:
            property: Property name, CustomPropertyRef, or InlineCustomProperty.
            min_val: Minimum value (exclusive).
            max_val: Maximum value (exclusive).
            resource_type: Resource type. Default: ``"events"``.

        Returns:
            Filter for numeric values outside the range.

        Example:
            ```python
            f = Filter.not_between("age", 18, 65)
            ```
        """
        return cls(
            _property=property,
            _operator="not between",
            _value=[min_val, max_val],
            _property_type="number",
            _resource_type=resource_type,
        )

    @classmethod
    def at_least(
        cls,
        property: str | CustomPropertyRef | InlineCustomProperty,
        value: int | float,
        *,
        resource_type: Literal["events", "people"] = "events",
    ) -> Filter:
        """Create a greater-than-or-equal filter.

        Args:
            property: Property name, CustomPropertyRef, or InlineCustomProperty.
            value: Numeric threshold (inclusive).
            resource_type: Resource type. Default: ``"events"``.

        Returns:
            Filter for numeric greater-than-or-equal.

        Example:
            ```python
            f = Filter.at_least("score", 80)
            ```
        """
        return cls(
            _property=property,
            _operator="is at least",
            _value=value,
            _property_type="number",
            _resource_type=resource_type,
        )

    @classmethod
    def at_most(
        cls,
        property: str | CustomPropertyRef | InlineCustomProperty,
        value: int | float,
        *,
        resource_type: Literal["events", "people"] = "events",
    ) -> Filter:
        """Create a less-than-or-equal filter.

        Args:
            property: Property name, CustomPropertyRef, or InlineCustomProperty.
            value: Numeric threshold (inclusive).
            resource_type: Resource type. Default: ``"events"``.

        Returns:
            Filter for numeric less-than-or-equal.

        Example:
            ```python
            f = Filter.at_most("errors", 5)
            ```
        """
        return cls(
            _property=property,
            _operator="is at most",
            _value=value,
            _property_type="number",
            _resource_type=resource_type,
        )

    @classmethod
    def is_set(
        cls,
        property: str | CustomPropertyRef | InlineCustomProperty,
        *,
        resource_type: Literal["events", "people"] = "events",
    ) -> Filter:
        """Create a property-existence filter.

        Args:
            property: Property name, CustomPropertyRef, or InlineCustomProperty.
            resource_type: Resource type. Default: ``"events"``.

        Returns:
            Filter for property existence.
        """
        return cls(
            _property=property,
            _operator="is set",
            _value=None,
            _property_type="string",
            _resource_type=resource_type,
        )

    @classmethod
    def is_not_set(
        cls,
        property: str | CustomPropertyRef | InlineCustomProperty,
        *,
        resource_type: Literal["events", "people"] = "events",
    ) -> Filter:
        """Create a property-nonexistence filter.

        Args:
            property: Property name, CustomPropertyRef, or InlineCustomProperty.
            resource_type: Resource type. Default: ``"events"``.

        Returns:
            Filter for property non-existence.
        """
        return cls(
            _property=property,
            _operator="is not set",
            _value=None,
            _property_type="string",
            _resource_type=resource_type,
        )

    @classmethod
    def starts_with(
        cls,
        property: str | CustomPropertyRef | InlineCustomProperty,
        prefix: str,
        *,
        resource_type: Literal["events", "people"] = "events",
    ) -> Filter:
        """Create a starts-with (prefix match) filter.

        Args:
            property: Property name, CustomPropertyRef, or InlineCustomProperty.
            prefix: String prefix to match.
            resource_type: Resource type. Default: ``"events"``.

        Returns:
            Filter for string prefix matching.

        Example:
            ```python
            f = Filter.starts_with("url", "https://")
            ```
        """
        return cls(
            _property=property,
            _operator="starts with",
            _value=prefix,
            _property_type="string",
            _resource_type=resource_type,
        )

    @classmethod
    def ends_with(
        cls,
        property: str | CustomPropertyRef | InlineCustomProperty,
        suffix: str,
        *,
        resource_type: Literal["events", "people"] = "events",
    ) -> Filter:
        """Create an ends-with (suffix match) filter.

        Args:
            property: Property name, CustomPropertyRef, or InlineCustomProperty.
            suffix: String suffix to match.
            resource_type: Resource type. Default: ``"events"``.

        Returns:
            Filter for string suffix matching.

        Example:
            ```python
            f = Filter.ends_with("email", "@example.com")
            ```
        """
        return cls(
            _property=property,
            _operator="ends with",
            _value=suffix,
            _property_type="string",
            _resource_type=resource_type,
        )

    @classmethod
    def is_true(
        cls,
        property: str | CustomPropertyRef | InlineCustomProperty,
        *,
        resource_type: Literal["events", "people"] = "events",
    ) -> Filter:
        """Create a boolean true filter.

        Args:
            property: Property name, CustomPropertyRef, or InlineCustomProperty.
            resource_type: Resource type. Default: ``"events"``.

        Returns:
            Filter for boolean true.
        """
        return cls(
            _property=property,
            _operator="true",
            _value=None,
            _property_type="boolean",
            _resource_type=resource_type,
        )

    @classmethod
    def is_false(
        cls,
        property: str | CustomPropertyRef | InlineCustomProperty,
        *,
        resource_type: Literal["events", "people"] = "events",
    ) -> Filter:
        """Create a boolean false filter.

        Args:
            property: Property name, CustomPropertyRef, or InlineCustomProperty.
            resource_type: Resource type. Default: ``"events"``.

        Returns:
            Filter for boolean false.
        """
        return cls(
            _property=property,
            _operator="false",
            _value=None,
            _property_type="boolean",
            _resource_type=resource_type,
        )

    # --- Cohort filters ---

    @classmethod
    def in_cohort(
        cls,
        cohort: int | CohortDefinition,
        name: str | None = None,
    ) -> Filter:
        """Create a filter restricting to users in a cohort.

        Accepts either a saved cohort ID (``int``) or an inline
        ``CohortDefinition``. The filter can be passed to ``where=``
        on any query method (``query``, ``query_funnel``,
        ``query_retention``, ``query_flow``).

        Args:
            cohort: Saved cohort ID (positive integer) or inline
                ``CohortDefinition``.
            name: Display name for the cohort. Optional for saved
                cohorts; recommended for inline definitions.

        Returns:
            Filter for cohort membership (contains).

        Raises:
            ValueError: If cohort ID is not positive (CF1) or name
                is empty when provided (CF2).

        Example:
            ```python
            from mixpanel_headless import Filter

            # Saved cohort
            f = Filter.in_cohort(123, "Power Users")

            # Inline cohort
            f = Filter.in_cohort(cohort_def, name="Frequent Buyers")
            ```
        """
        return cls._build_cohort_filter(cohort, name, negated=False)

    @classmethod
    def not_in_cohort(
        cls,
        cohort: int | CohortDefinition,
        name: str | None = None,
    ) -> Filter:
        """Create a filter excluding users in a cohort.

        Accepts either a saved cohort ID (``int``) or an inline
        ``CohortDefinition``. The filter can be passed to ``where=``
        on any query method.

        Args:
            cohort: Saved cohort ID (positive integer) or inline
                ``CohortDefinition``.
            name: Display name for the cohort. Optional for saved
                cohorts; recommended for inline definitions.

        Returns:
            Filter for cohort exclusion (does not contain).

        Raises:
            ValueError: If cohort ID is not positive (CF1) or name
                is empty when provided (CF2).

        Example:
            ```python
            from mixpanel_headless import Filter

            f = Filter.not_in_cohort(789, "Bots")
            ```
        """
        return cls._build_cohort_filter(cohort, name, negated=True)

    @classmethod
    def _build_cohort_filter(
        cls,
        cohort: int | CohortDefinition,
        name: str | None,
        *,
        negated: bool,
    ) -> Filter:
        """Build a cohort filter (shared by in_cohort/not_in_cohort).

        Args:
            cohort: Saved cohort ID or inline definition.
            name: Display name.
            negated: Whether this is a "does not contain" filter.

        Returns:
            Constructed Filter with cohort-specific internal fields.

        Raises:
            ValueError: On CF1 or CF2 violations.
        """
        _validate_cohort_args(cohort, name)

        operator: FilterOperator = "does not contain" if negated else "contains"

        # Build the cohort value structure
        cohort_entry: dict[str, Any] = {"negated": negated, "name": name or ""}
        if isinstance(cohort, int):
            cohort_entry["id"] = cohort
        else:
            cohort_entry["raw_cohort"] = _sanitize_raw_cohort(cohort.to_dict())

        value: list[dict[str, Any]] = [{"cohort": cohort_entry}]

        return cls(
            _property="$cohorts",
            _operator=operator,
            _value=value,
            _property_type="list",
            _resource_type="events",
        )

    # --- Date/datetime filters ---

    @staticmethod
    def _validate_date(date_str: str) -> dt_date:
        """Validate a date string is YYYY-MM-DD and return parsed date.

        Args:
            date_str: Date string to validate.

        Returns:
            Parsed ``datetime.date`` object.

        Raises:
            ValueError: If format is wrong or date is invalid.
        """
        if not re.match(r"^\d{4}-\d{2}-\d{2}$", date_str):
            raise ValueError(f"Date must be YYYY-MM-DD format (got '{date_str}')")
        try:
            return dt_date.fromisoformat(date_str)
        except ValueError:
            raise ValueError(f"'{date_str}' is not a valid calendar date") from None

    @classmethod
    def on(
        cls,
        property: str | CustomPropertyRef | InlineCustomProperty,
        date: str,
        *,
        resource_type: Literal["events", "people"] = "events",
    ) -> Filter:
        """Create a date equality filter (exact date match).

        Args:
            property: Property name, CustomPropertyRef, or InlineCustomProperty (e.g. ``"$time"``, ``"created"``).
            date: Date in YYYY-MM-DD format.
            resource_type: Resource type. Default: ``"events"``.

        Returns:
            Filter for exact date match.

        Raises:
            ValueError: If date is not valid YYYY-MM-DD.
        """
        cls._validate_date(date)
        return cls(
            _property=property,
            _operator="was on",
            _value=date,
            _property_type="datetime",
            _resource_type=resource_type,
        )

    @classmethod
    def not_on(
        cls,
        property: str | CustomPropertyRef | InlineCustomProperty,
        date: str,
        *,
        resource_type: Literal["events", "people"] = "events",
    ) -> Filter:
        """Create a date inequality filter (not on date).

        Args:
            property: Property name, CustomPropertyRef, or InlineCustomProperty.
            date: Date in YYYY-MM-DD format.
            resource_type: Resource type. Default: ``"events"``.

        Returns:
            Filter for date inequality.

        Raises:
            ValueError: If date is not valid YYYY-MM-DD.
        """
        cls._validate_date(date)
        return cls(
            _property=property,
            _operator="was not on",
            _value=date,
            _property_type="datetime",
            _resource_type=resource_type,
        )

    @classmethod
    def before(
        cls,
        property: str | CustomPropertyRef | InlineCustomProperty,
        date: str,
        *,
        resource_type: Literal["events", "people"] = "events",
    ) -> Filter:
        """Create a date before filter.

        Args:
            property: Property name, CustomPropertyRef, or InlineCustomProperty.
            date: Date in YYYY-MM-DD format.
            resource_type: Resource type. Default: ``"events"``.

        Returns:
            Filter for dates before the specified date.

        Raises:
            ValueError: If date is not valid YYYY-MM-DD.
        """
        cls._validate_date(date)
        return cls(
            _property=property,
            _operator="was before",
            _value=date,
            _property_type="datetime",
            _resource_type=resource_type,
        )

    @classmethod
    def since(
        cls,
        property: str | CustomPropertyRef | InlineCustomProperty,
        date: str,
        *,
        resource_type: Literal["events", "people"] = "events",
    ) -> Filter:
        """Create a date since filter (from date onward).

        Args:
            property: Property name, CustomPropertyRef, or InlineCustomProperty.
            date: Date in YYYY-MM-DD format.
            resource_type: Resource type. Default: ``"events"``.

        Returns:
            Filter for dates on or after the specified date.

        Raises:
            ValueError: If date is not valid YYYY-MM-DD.
        """
        cls._validate_date(date)
        return cls(
            _property=property,
            _operator="was since",
            _value=date,
            _property_type="datetime",
            _resource_type=resource_type,
        )

    @classmethod
    def in_the_last(
        cls,
        property: str | CustomPropertyRef | InlineCustomProperty,
        quantity: int,
        date_unit: FilterDateUnit,
        *,
        resource_type: Literal["events", "people"] = "events",
    ) -> Filter:
        """Create a relative date filter (in the last N units).

        Args:
            property: Property name, CustomPropertyRef, or InlineCustomProperty.
            quantity: Number of time units (must be positive).
            date_unit: Time unit (``"hour"``, ``"day"``, ``"week"``,
                ``"month"``).
            resource_type: Resource type. Default: ``"events"``.

        Returns:
            Filter for events within the last N units.

        Raises:
            ValueError: If quantity is not positive.
        """
        if quantity <= 0:
            raise ValueError(f"quantity must be a positive integer (got {quantity})")
        return cls(
            _property=property,
            _operator="was in the",
            _value=quantity,
            _property_type="datetime",
            _resource_type=resource_type,
            _date_unit=date_unit,
        )

    @classmethod
    def not_in_the_last(
        cls,
        property: str | CustomPropertyRef | InlineCustomProperty,
        quantity: int,
        date_unit: FilterDateUnit,
        *,
        resource_type: Literal["events", "people"] = "events",
    ) -> Filter:
        """Create a relative date exclusion filter (not in the last N units).

        Args:
            property: Property name, CustomPropertyRef, or InlineCustomProperty.
            quantity: Number of time units (must be positive).
            date_unit: Time unit (``"hour"``, ``"day"``, ``"week"``,
                ``"month"``).
            resource_type: Resource type. Default: ``"events"``.

        Returns:
            Filter for events NOT within the last N units.

        Raises:
            ValueError: If quantity is not positive.
        """
        if quantity <= 0:
            raise ValueError(f"quantity must be a positive integer (got {quantity})")
        return cls(
            _property=property,
            _operator="was not in the",
            _value=quantity,
            _property_type="datetime",
            _resource_type=resource_type,
            _date_unit=date_unit,
        )

    @classmethod
    def date_between(
        cls,
        property: str | CustomPropertyRef | InlineCustomProperty,
        from_date: str,
        to_date: str,
        *,
        resource_type: Literal["events", "people"] = "events",
    ) -> Filter:
        """Create a date range filter (between two dates, inclusive).

        Args:
            property: Property name, CustomPropertyRef, or InlineCustomProperty.
            from_date: Start date in YYYY-MM-DD format.
            to_date: End date in YYYY-MM-DD format.
            resource_type: Resource type. Default: ``"events"``.

        Returns:
            Filter for dates within the range.

        Raises:
            ValueError: If dates are not valid YYYY-MM-DD or
                from_date is after to_date.
        """
        from_parsed = cls._validate_date(from_date)
        to_parsed = cls._validate_date(to_date)
        if from_parsed > to_parsed:
            raise ValueError(
                f"from_date must be before to_date (got '{from_date}' > '{to_date}')"
            )
        return cls(
            _property=property,
            _operator="was between",
            _value=[from_date, to_date],
            _property_type="datetime",
            _resource_type=resource_type,
        )

    @classmethod
    def date_not_between(
        cls,
        property: str | CustomPropertyRef | InlineCustomProperty,
        from_date: str,
        to_date: str,
        *,
        resource_type: Literal["events", "people"] = "events",
    ) -> Filter:
        """Create a date exclusion range filter (not between two dates).

        Args:
            property: Property name, CustomPropertyRef, or InlineCustomProperty.
            from_date: Start date in YYYY-MM-DD format.
            to_date: End date in YYYY-MM-DD format.
            resource_type: Resource type. Default: ``"events"``.

        Returns:
            Filter for dates outside the range.

        Raises:
            ValueError: If dates are not valid YYYY-MM-DD or
                from_date is after to_date.

        Example:
            ```python
            f = Filter.date_not_between("created", "2024-01-01", "2024-06-30")
            ```
        """
        from_parsed = cls._validate_date(from_date)
        to_parsed = cls._validate_date(to_date)
        if from_parsed > to_parsed:
            raise ValueError(
                f"from_date must be before to_date (got '{from_date}' > '{to_date}')"
            )
        return cls(
            _property=property,
            _operator="was not between",
            _value=[from_date, to_date],
            _property_type="datetime",
            _resource_type=resource_type,
        )

    @classmethod
    def in_the_next(
        cls,
        property: str | CustomPropertyRef | InlineCustomProperty,
        quantity: int,
        date_unit: FilterDateUnit,
        *,
        resource_type: Literal["events", "people"] = "events",
    ) -> Filter:
        """Create a relative date filter (in the next N units).

        Args:
            property: Property name, CustomPropertyRef, or InlineCustomProperty.
            quantity: Number of time units (must be positive).
            date_unit: Time unit (``"hour"``, ``"day"``, ``"week"``,
                ``"month"``).
            resource_type: Resource type. Default: ``"events"``.

        Returns:
            Filter for events within the next N units.

        Raises:
            ValueError: If quantity is not positive.

        Example:
            ```python
            f = Filter.in_the_next("expires", 7, "day")
            ```
        """
        if quantity <= 0:
            raise ValueError(f"quantity must be a positive integer (got {quantity})")
        return cls(
            _property=property,
            _operator="was in the next",
            _value=quantity,
            _property_type="datetime",
            _resource_type=resource_type,
            _date_unit=date_unit,
        )

    # --- List-of-object subproperty filters ---

    @classmethod
    def list_contains(
        cls,
        property: str,
        *item_filters: Filter,
        quantifier: Literal["any", "all"] = "any",
        resource_type: Literal["events", "people"] = "events",
        **equals: str | list[str],
    ) -> Filter:
        """Match events whose list-of-object property contains items satisfying inner conditions.

        Used to filter on subproperties of objects nested inside a list
        property (e.g. ``cart`` is a list of ``{"Brand": str, "Category":
        str, "Price": int}``). Each inner condition is evaluated
        per-item; the ``quantifier`` controls whether at least one item
        (``"any"``, the default) or every item (``"all"``) must satisfy
        all inner conditions.

        Two ways to specify inner conditions:

        - **Keyword shorthand** for the common equality case:
          ``Filter.list_contains("cart", Brand="nike", Category="hats")``.
          Inner equality filters inherit the outer ``resource_type``.
        - **Explicit Filter instances** for any wire-format operator:
          ``Filter.list_contains("cart", Filter.equals("Brand", "nike"),
          Filter.greater_than("Price", 50))``. Each inner Filter carries
          its own ``resource_type`` from its own factory call — pass
          ``resource_type=`` explicitly on each inner factory if you
          want them to match the outer.

        Mixing the two shapes in one call raises ``ValueError``.

        Args:
            property: Name of the list-of-object property to filter on.
            *item_filters: Inner ``Filter`` instances applied per list
                item. Mutually exclusive with ``**equals``.
            quantifier: ``"any"`` (≥1 item must match all inner
                conditions) or ``"all"`` (every item must). Default:
                ``"any"``.
            resource_type: Resource type. Default: ``"events"``.
            **equals: Keyword shorthand — each ``key=value`` becomes
                ``Filter.equals(key, value, resource_type=resource_type)``.
                Mutually exclusive with ``*item_filters``. Values must
                be ``str`` or ``list[str]``; keys must be non-empty.

        Returns:
            Filter that emits the ``listItemFilters`` bookmark structure
            on serialization.

        Raises:
            ValueError: If both ``*item_filters`` and ``**equals`` are
                provided, if ``quantifier`` is not ``"any"`` or
                ``"all"``, if a kwarg key is empty, if no inner
                conditions are given, or if any inner filter is itself
                a ``list_contains`` (nesting is not supported).
            TypeError: If a ``**equals`` value is not ``str`` or
                ``list[str]`` (the wire format only supports string
                equality; numeric/boolean comparisons require explicit
                ``Filter.equals(...)`` / ``Filter.greater_than(...)``
                positional inner filters).

        Example:
            ```python
            from mixpanel_headless import Filter

            # Cart contains a nike-branded hat
            f1 = Filter.list_contains("cart", Brand="nike", Category="hats")

            # Every cart item costs more than $50
            f2 = Filter.list_contains(
                "cart",
                Filter.greater_than("Price", 50),
                quantifier="all",
            )
            ```
        """
        if item_filters and equals:
            raise ValueError(
                "Filter.list_contains: pass either positional Filter instances "
                "OR keyword equals shorthand, not both"
            )
        if quantifier not in ("any", "all"):
            raise ValueError(
                f"Filter.list_contains quantifier must be 'any' or 'all', "
                f"got {quantifier!r}"
            )
        for k, v in equals.items():
            if not k.strip():
                raise ValueError(
                    "Filter.list_contains: kwarg keys must be non-empty strings"
                )
            if not isinstance(v, (str, list)):
                raise TypeError(
                    f"Filter.list_contains kwarg {k!r}: value must be str or "
                    f"list[str], got {type(v).__name__}"
                )
        sub_filters: tuple[Filter, ...] = (
            tuple(item_filters)
            if item_filters
            else tuple(
                cls.equals(k, v, resource_type=resource_type) for k, v in equals.items()
            )
        )
        if not sub_filters:
            raise ValueError(
                "Filter.list_contains requires at least one inner condition"
            )
        for sub in sub_filters:
            if sub._operator == "list_contains":
                raise ValueError(
                    "Filter.list_contains does not support nested list_contains filters"
                )
        return cls(
            _property=property,
            _operator="list_contains",
            _value=None,
            _property_type="object",
            _resource_type=resource_type,
            _list_item_filters=sub_filters,
            _list_item_quantifier=quantifier,
        )


@dataclass(frozen=True)
class ListItemGroupMode:
    """Discriminator for ``GroupBy.list_item`` — sub-property name + scalar type.

    Pairs the subproperty name with its inferred scalar type so they
    cannot be set independently. Used as the optional ``_list_item_mode``
    field on ``GroupBy``; presence of this field marks a GroupBy as a
    list-item breakdown.

    Attributes:
        sub: Subproperty name (must be non-empty after stripping).
        sub_type: Subproperty data type. One of the four
            ``CustomPropertyType`` values.

    Example:
        ```python
        from mixpanel_headless import GroupBy, ListItemGroupMode

        # Constructed indirectly via the classmethod (preferred)
        g = GroupBy.list_item("cart", "Brand")
        assert g._list_item_mode == ListItemGroupMode(sub="Brand", sub_type="string")
        ```
    """

    sub: str
    """Subproperty name as it appears inside each object."""

    sub_type: CustomPropertyType
    """Subproperty data type, matching :data:`CustomPropertyType`."""

    def __post_init__(self) -> None:
        """Validate sub is non-empty and sub_type is a known scalar type.

        Raises:
            ValueError: If ``sub`` is empty after stripping or
                ``sub_type`` is not one of the four
                ``CustomPropertyType`` values.
        """
        if not self.sub.strip():
            raise ValueError("ListItemGroupMode.sub must be a non-empty string")
        if self.sub_type not in ("string", "number", "boolean", "datetime"):
            raise ValueError(
                "ListItemGroupMode.sub_type must be one of "
                "'string'/'number'/'boolean'/'datetime', "
                f"got {self.sub_type!r}"
            )


@dataclass(frozen=True)
class GroupBy:
    """Specifies a property breakdown with optional numeric bucketing.

    Used with ``Workspace.query()`` to break down results by property values.
    String properties are broken down by distinct values; numeric properties
    can be bucketed into ranges.

    Attributes:
        property: Property to break down by (name, ref, or inline).
        property_type: Data type of the property. Default: ``"string"``.
        bucket_size: Bucket width for numeric properties.
        bucket_min: Minimum value for numeric buckets.
        bucket_max: Maximum value for numeric buckets.

    Example:
        ```python
        from mixpanel_headless import GroupBy

        # String breakdown
        g1 = GroupBy("country")

        # Numeric bucketed breakdown
        g2 = GroupBy(
            "revenue",
            property_type="number",
            bucket_size=50,
            bucket_min=0,
            bucket_max=500,
        )
        ```
    """

    property: str | CustomPropertyRef | InlineCustomProperty
    """Property to break down by (name, ref, or inline)."""

    property_type: CustomPropertyType = "string"
    """Data type of the property. One of the four scalar types.

    Note: list-item breakdowns set ``_list_item_mode`` instead — the
    wire builder hardcodes ``propertyType: "object"`` for that branch
    independently of this field.
    """

    bucket_size: int | float | None = None
    """Bucket width for numeric properties."""

    bucket_min: int | float | None = None
    """Minimum value for numeric buckets."""

    bucket_max: int | float | None = None
    """Maximum value for numeric buckets."""

    _list_item_mode: ListItemGroupMode | None = None
    """List-item breakdown discriminator. Set by :meth:`list_item`."""

    def __post_init__(self) -> None:
        """Validate construction arguments.

        Raises:
            ValueError: If property is an empty string (GB1),
                bucket_size is not positive (GB2),
                bucket_min >= bucket_max (GB3),
                ``_list_item_mode`` is combined with bucketing (GB4),
                or ``_list_item_mode`` is set but ``property`` is not a
                plain ``str`` (GB5).
        """
        if isinstance(self.property, str) and not self.property.strip():
            raise ValueError("GroupBy.property must be a non-empty string")
        if self.bucket_size is not None and self.bucket_size <= 0:
            raise ValueError(
                f"GroupBy.bucket_size must be positive, got {self.bucket_size}"
            )
        if (
            self.bucket_min is not None
            and self.bucket_max is not None
            and self.bucket_min >= self.bucket_max
        ):
            raise ValueError(
                f"GroupBy.bucket_min ({self.bucket_min}) must be less than "
                f"bucket_max ({self.bucket_max})"
            )
        if self._list_item_mode is not None:
            if any(
                b is not None
                for b in (self.bucket_size, self.bucket_min, self.bucket_max)
            ):
                raise ValueError("GroupBy.list_item is incompatible with bucketing")
            if not isinstance(self.property, str):
                raise ValueError(
                    "GroupBy.list_item requires property to be a plain str, "
                    f"got {type(self.property).__name__}"
                )

    @classmethod
    def list_item(
        cls,
        property: str,
        sub: str,
        *,
        sub_type: CustomPropertyType = "string",
    ) -> GroupBy:
        """Break down by a subproperty of objects inside a list property.

        Mirrors the Mixpanel UI's ``cart.Brand`` / ``cart.Category``
        breakdown for list-of-object properties (e.g. ``cart`` is a
        list of ``{"Brand": str, "Category": str, "Price": int}``
        items). Each list item contributes one count per distinct
        subproperty value it carries.

        Args:
            property: Name of the list-of-object property.
            sub: Subproperty name to break down by.
            sub_type: Data type of the subproperty. Default:
                ``"string"``.

        Returns:
            ``GroupBy`` whose serialization emits a ``listItemGroup``
            structure in the bookmark JSON.

        Raises:
            ValueError: If ``sub`` is empty after stripping (via
                ``ListItemGroupMode.__post_init__``), if ``sub_type``
                is not one of the four ``CustomPropertyType`` values,
                or if any ``GroupBy.__post_init__`` invariant fails
                (see :meth:`__post_init__` Raises section).

        Example:
            ```python
            from mixpanel_headless import GroupBy

            # Break down Cart Viewed events by cart.Brand
            g1 = GroupBy.list_item("cart", "Brand")

            # Break down by a numeric subproperty
            g2 = GroupBy.list_item("cart", "Price", sub_type="number")
            ```
        """
        return cls(
            property=property,
            _list_item_mode=ListItemGroupMode(sub=sub, sub_type=sub_type),
        )


# =============================================================================
# Cohort Definition Builder Types
# =============================================================================

_PROPERTY_OPERATOR_MAP: dict[str, str] = {
    "equals": "==",
    "not_equals": "!=",
    "contains": "in",
    "not_contains": "not in",
    "greater_than": ">",
    "less_than": "<",
    "is_set": "defined",
    "is_not_set": "not defined",
}
"""Maps ``CohortCriteria.has_property()`` operator names to selector tree operators."""

_FILTER_TO_SELECTOR_SUPPORTED: frozenset[str] = frozenset(
    {
        "equals",
        "does not equal",
        "contains",
        "does not contain",
        "is greater than",
        "is less than",
        "is set",
        "is not set",
        "is between",
    }
)
"""Set of ``Filter._operator`` values accepted by ``_build_event_selector``.

These operators are emitted verbatim in the Insights bookmark filter
format (``filterOperator`` key) — no mapping is needed because the
server's ``output_leaf_node`` routes ``filterOperator`` nodes through
``filter_to_arb_selector_string``, which understands these names
natively.
"""


def _validate_cohort_date(date_str: str) -> None:
    """Validate that a date string is in YYYY-MM-DD format.

    Args:
        date_str: Date string to validate.

    Raises:
        ValueError: If format is not YYYY-MM-DD or date is invalid.
    """
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", date_str):
        raise ValueError("dates must be YYYY-MM-DD format")
    try:
        dt_date.fromisoformat(date_str)
    except ValueError:
        raise ValueError(
            f"date '{date_str}' has correct format but is not a valid calendar date"
        ) from None


def _build_event_selector(
    filters: Filter | list[Filter],
) -> dict[str, Any]:
    """Convert Filter objects to an event selector expression tree.

    Each ``Filter`` is emitted as an **Insights bookmark filter** node
    (``filterOperator`` / ``filterValue`` / ``filterType`` keys) rather
    than the legacy selector-tree format (``operator`` / ``operand``).
    The server's ``output_leaf_node`` routes ``filterOperator`` nodes
    through ``filter_to_arb_selector_string``, which handles all
    operators correctly.

    Args:
        filters: Single Filter or list of Filters to convert.

    Returns:
        Expression tree dict with ``operator`` and ``children`` keys.
        Each child is an Insights bookmark filter node.

    Raises:
        ValueError: If a filter uses an unsupported operator.
    """
    filter_list = [filters] if isinstance(filters, Filter) else filters
    children: list[dict[str, Any]] = []
    for f in filter_list:
        if f._operator not in _FILTER_TO_SELECTOR_SUPPORTED:
            supported = ", ".join(sorted(_FILTER_TO_SELECTOR_SUPPORTED))
            msg = (
                f"unsupported filter operator for cohort selector: {f._operator!r}. "
                f"Supported operators: {supported}"
            )
            raise ValueError(msg)
        prop = f._property
        node: dict[str, Any] = {
            "resourceType": f._resource_type,
            "filterType": f._property_type,
            "defaultType": f._property_type,
            "filterOperator": f._operator,
        }
        if isinstance(prop, CustomPropertyRef):
            node["customPropertyId"] = prop.id
            node["dataset"] = "$mixpanel"
        elif isinstance(prop, InlineCustomProperty):
            effective_type = (
                prop.property_type
                if prop.property_type is not None
                else f._property_type
            )
            node["customProperty"] = {
                "displayFormula": prop.formula,
                "composedProperties": {
                    letter: {
                        "value": pi.name,
                        "type": pi.type,
                        "resourceType": pi.resource_type,
                    }
                    for letter, pi in prop.inputs.items()
                },
                "name": "",
                "description": "",
                "propertyType": effective_type,
                "resourceType": prop.resource_type,
            }
            node["filterType"] = effective_type
            node["defaultType"] = effective_type
            node["dataset"] = "$mixpanel"
            node["resourceType"] = prop.resource_type
        else:
            node["value"] = prop
        if f._value is not None:
            node["filterValue"] = f._value
        children.append(node)
    return {"operator": "and", "children": children}


@dataclass(frozen=True)
class CohortCriteria:
    """A single atomic condition for cohort membership.

    Constructed exclusively via class methods — never instantiate directly.
    Produces selector nodes and behavior entries for the Mixpanel cohort
    definition format (legacy ``selector`` + ``behaviors`` JSON).

    Example:
        ```python
        from mixpanel_headless import CohortCriteria

        # Behavioral criterion
        c = CohortCriteria.did_event("Purchase", at_least=3, within_days=30)

        # Property criterion
        c = CohortCriteria.has_property("plan", "premium")

        # Cohort reference
        c = CohortCriteria.in_cohort(456)
        ```
    """

    _selector_node: dict[str, Any]
    """Expression tree leaf node (behavioral, property, or cohort reference)."""

    _behavior_key: str | None
    """Placeholder behavior key (e.g., ``"bhvr_0"``). ``None`` for non-behavioral."""

    _behavior: dict[str, Any] | None
    """Behavior dict entry (event selector + window/dates). ``None`` for non-behavioral."""

    @classmethod
    def did_event(
        cls,
        event: str,
        *,
        at_least: int | None = None,
        at_most: int | None = None,
        exactly: int | None = None,
        within_days: int | None = None,
        within_weeks: int | None = None,
        within_months: int | None = None,
        from_date: str | None = None,
        to_date: str | None = None,
        where: Filter | list[Filter] | None = None,
        aggregation: CohortAggregationType | None = None,
        aggregation_property: str | None = None,
    ) -> CohortCriteria:
        """Create a behavioral criterion based on event frequency.

        Args:
            event: Event name (must be non-empty).
            at_least: Minimum event count (``>=``).
            at_most: Maximum event count (``<=``).
            exactly: Exact event count (``==``).
            within_days: Rolling window in days.
            within_weeks: Rolling window in weeks.
            within_months: Rolling window in months.
            from_date: Absolute start date (YYYY-MM-DD).
            to_date: Absolute end date (YYYY-MM-DD).
            where: Event property filter(s).
            aggregation: Aggregation operator for property-based thresholds
                (total, unique, average, min, max, median). Must be paired
                with ``aggregation_property``.
            aggregation_property: Event property to aggregate (e.g.,
                ``"amount"``). Must be paired with ``aggregation``.

        Returns:
            CohortCriteria with behavioral selector node and behavior entry.

        Raises:
            ValueError: If no frequency param or multiple are set, frequency is
                negative, event name is empty/whitespace, time constraints are
                missing or conflicting, dates are malformed/misordered, or
                aggregation and aggregation_property are not both set or both
                None (CA1/CA2).
        """
        # CD4: Event name must be non-empty
        if not event or not event.strip():
            raise ValueError("event name must be non-empty")

        # CA1/CA2: aggregation and aggregation_property must both be set or both None
        if (aggregation is None) != (aggregation_property is None):
            raise ValueError(
                "aggregation and aggregation_property must both be set or both be None"
            )

        if aggregation_property is not None and not aggregation_property.strip():
            raise ValueError("aggregation_property must be a non-empty string")

        # CD1: Exactly one frequency param required
        freq_params = {
            "at_least": at_least,
            "at_most": at_most,
            "exactly": exactly,
        }
        set_freqs = {k: v for k, v in freq_params.items() if v is not None}
        if len(set_freqs) != 1:
            raise ValueError("exactly one of at_least, at_most, exactly must be set")

        freq_name, freq_value = next(iter(set_freqs.items()))

        # CD2: Frequency param must be non-negative
        if freq_value < 0:
            raise ValueError("frequency value must be >= 0")

        # Map frequency param to selector operator
        freq_operator_map = {
            "at_least": ">=",
            "at_most": "<=",
            "exactly": "==",
        }
        selector_operator = freq_operator_map[freq_name]

        # CD3: Exactly one time constraint required
        rolling_params = {
            "within_days": within_days,
            "within_weeks": within_weeks,
            "within_months": within_months,
        }
        set_rolling = {k: v for k, v in rolling_params.items() if v is not None}
        has_date_range = from_date is not None or to_date is not None

        if not set_rolling and not has_date_range:
            raise ValueError(
                "exactly one time constraint required "
                "(within_days/weeks/months or from_date+to_date)"
            )
        if set_rolling and has_date_range:
            raise ValueError(
                "exactly one time constraint required "
                "(within_days/weeks/months or from_date+to_date)"
            )
        if len(set_rolling) > 1:
            raise ValueError(
                "exactly one time constraint required "
                "(within_days/weeks/months or from_date+to_date)"
            )

        # Build behavior entry
        behavior_key = "bhvr_0"  # placeholder, re-indexed by to_dict()

        event_selector: dict[str, Any] = {
            "event": event,
            "selector": None,
        }
        if where is not None:
            where_list = [where] if isinstance(where, Filter) else where
            if where_list:
                event_selector["selector"] = _build_event_selector(where_list)

        count_dict: dict[str, Any] = {
            "event_selector": event_selector,
            "type": "absolute",
        }

        # Add aggregation fields when set
        if aggregation is not None and aggregation_property is not None:
            count_dict["aggregationOperator"] = aggregation
            count_dict["property"] = aggregation_property

        behavior: dict[str, Any] = {
            "count": count_dict,
        }

        if set_rolling:
            rolling_name, rolling_value = next(iter(set_rolling.items()))
            if rolling_value <= 0:
                raise ValueError("time window value must be positive")
            unit_map = {
                "within_days": "day",
                "within_weeks": "week",
                "within_months": "month",
            }
            behavior["window"] = {
                "unit": unit_map[rolling_name],
                "value": rolling_value,
            }
        else:
            # Absolute date range
            # CD5: from_date requires to_date (and vice versa)
            if from_date is not None and to_date is None:
                raise ValueError("from_date requires to_date")
            if to_date is not None and from_date is None:
                raise ValueError("to_date requires from_date")

            # CD6: Dates must be YYYY-MM-DD
            # from_date and to_date are guaranteed non-None here:
            # has_date_range is True and CD5 guards above reject mismatched pairs.
            if from_date is None or to_date is None:  # pragma: no cover
                raise ValueError(
                    "exactly one time constraint required "
                    "(within_days/weeks/months or from_date+to_date)"
                )
            _validate_cohort_date(from_date)
            _validate_cohort_date(to_date)
            if dt_date.fromisoformat(from_date) > dt_date.fromisoformat(to_date):
                raise ValueError("from_date must be before or equal to to_date")

            behavior["from_date"] = from_date
            behavior["to_date"] = to_date

        selector_node: dict[str, Any] = {
            "property": "behaviors",
            "value": behavior_key,
            "operator": selector_operator,
            "operand": freq_value,
        }

        return cls(
            _selector_node=selector_node,
            _behavior_key=behavior_key,
            _behavior=behavior,
        )

    @classmethod
    def did_not_do_event(
        cls,
        event: str,
        *,
        within_days: int | None = None,
        within_weeks: int | None = None,
        within_months: int | None = None,
        from_date: str | None = None,
        to_date: str | None = None,
    ) -> CohortCriteria:
        """Create a criterion for users who did NOT perform an event.

        Shorthand for ``did_event(event, exactly=0, ...)``.

        Args:
            event: Event name.
            within_days: Rolling window in days.
            within_weeks: Rolling window in weeks.
            within_months: Rolling window in months.
            from_date: Absolute start date (YYYY-MM-DD).
            to_date: Absolute end date (YYYY-MM-DD).

        Returns:
            CohortCriteria equivalent to ``did_event(event, exactly=0, ...)``.

        Raises:
            ValueError: On constraint violations.
        """
        return cls.did_event(
            event,
            exactly=0,
            within_days=within_days,
            within_weeks=within_weeks,
            within_months=within_months,
            from_date=from_date,
            to_date=to_date,
        )

    @classmethod
    def has_property(
        cls,
        property: str,
        value: str | int | float | bool | list[str],
        *,
        operator: Literal[
            "equals",
            "not_equals",
            "contains",
            "not_contains",
            "greater_than",
            "less_than",
            "is_set",
            "is_not_set",
        ] = "equals",
        property_type: Literal[
            "string",
            "number",
            "boolean",
            "datetime",
            "list",
        ] = "string",
    ) -> CohortCriteria:
        """Create a property-based criterion.

        Args:
            property: Property name (must be non-empty).
            value: Value to compare against.
            operator: Comparison operator. Default: ``"equals"``.
            property_type: Data type of the property. Default: ``"string"``.

        Returns:
            CohortCriteria with property selector node.

        Raises:
            ValueError: If property name is empty (CD7).
        """
        # CD7: Property name must be non-empty
        if not property or not property.strip():
            raise ValueError("property name must be non-empty")

        selector_operator = _PROPERTY_OPERATOR_MAP[operator]

        selector_node: dict[str, Any] = {
            "property": "user",
            "value": property,
            "operator": selector_operator,
            "operand": value,
            "type": property_type,
        }

        return cls(
            _selector_node=selector_node,
            _behavior_key=None,
            _behavior=None,
        )

    @classmethod
    def property_is_set(cls, property: str) -> CohortCriteria:
        """Check if a user property exists.

        Shorthand for ``has_property(property, "", operator="is_set")``.

        Args:
            property: Property name.

        Returns:
            CohortCriteria checking property existence.

        Raises:
            ValueError: If property name is empty (CD7).
        """
        return cls.has_property(property, "", operator="is_set")

    @classmethod
    def property_is_not_set(cls, property: str) -> CohortCriteria:
        """Check if a user property does not exist.

        Shorthand for ``has_property(property, "", operator="is_not_set")``.

        Args:
            property: Property name.

        Returns:
            CohortCriteria checking property non-existence.

        Raises:
            ValueError: If property name is empty (CD7).
        """
        return cls.has_property(property, "", operator="is_not_set")

    @classmethod
    def in_cohort(cls, cohort_id: int) -> CohortCriteria:
        """Create a criterion for membership in a saved cohort.

        Args:
            cohort_id: Cohort ID (must be positive integer).

        Returns:
            CohortCriteria with cohort reference selector node.

        Raises:
            ValueError: If cohort_id is not a positive integer (CD8).
        """
        if cohort_id <= 0:
            raise ValueError("cohort_id must be a positive integer")

        selector_node: dict[str, Any] = {
            "property": "cohort",
            "value": cohort_id,
            "operator": "in",
        }

        return cls(
            _selector_node=selector_node,
            _behavior_key=None,
            _behavior=None,
        )

    @classmethod
    def not_in_cohort(cls, cohort_id: int) -> CohortCriteria:
        """Create a criterion for non-membership in a saved cohort.

        Args:
            cohort_id: Cohort ID (must be positive integer).

        Returns:
            CohortCriteria with cohort exclusion selector node.

        Raises:
            ValueError: If cohort_id is not a positive integer (CD8).
        """
        if cohort_id <= 0:
            raise ValueError("cohort_id must be a positive integer")

        selector_node: dict[str, Any] = {
            "property": "cohort",
            "value": cohort_id,
            "operator": "not in",
        }

        return cls(
            _selector_node=selector_node,
            _behavior_key=None,
            _behavior=None,
        )


_CONTROL_CHAR_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
"""Control character regex for __post_init__ validation.

Duplicated from validation.py to avoid circular imports.
"""

_MATH_REQUIRING_PROPERTY: frozenset[str] = frozenset(
    {
        "average",
        "median",
        "min",
        "max",
        "p25",
        "p75",
        "p90",
        "p99",
        "percentile",
        "histogram",
        # Advanced property-requiring types
        "unique_values",
        "most_frequent",
        "first_value",
        "multi_attribution",
        "numeric_summary",
    }
)
"""Math types that require a measurement property (for Metric.__post_init__)."""


def _validate_event_name(event: str, class_name: str) -> None:
    """Validate that an event name is non-empty and has no control chars.

    Args:
        event: The event name to validate.
        class_name: Name of the containing class (for error messages).

    Raises:
        ValueError: If event is empty or contains control characters.
    """
    if not event or not event.strip():
        raise ValueError(f"{class_name}.event must be a non-empty string")
    if _CONTROL_CHAR_RE.search(event):
        raise ValueError(f"{class_name}.event contains control characters: {event!r}")


def _validate_cohort_args(
    cohort: int | CohortDefinition,
    name: str | None,
) -> None:
    """Validate cohort ID and name shared by CohortBreakdown, CohortMetric, and Filter.

    Args:
        cohort: Saved cohort ID or inline definition.
        name: Display name for the cohort.

    Raises:
        ValueError: If cohort ID is not positive or name is empty
            when provided.
    """
    if isinstance(cohort, int) and cohort <= 0:
        raise ValueError("cohort must be a positive integer")
    if name is not None and not name.strip():
        raise ValueError("cohort name must be non-empty when provided")


def _sanitize_raw_cohort(raw: dict[str, Any]) -> dict[str, Any]:
    """Remove null ``selector`` keys from behavioral event_selector entries.

    The Mixpanel API calls ``postorder_traverse`` on nested ``selector``
    fields within ``event_selector`` blocks. A ``None`` root causes a
    crash. This function deep-copies the raw cohort dict and removes
    any ``selector: None`` entries from behavioral event_selectors.

    Args:
        raw: Output of ``CohortDefinition.to_dict()``.

    Returns:
        Sanitized deep copy safe for API submission.
    """
    result = copy.deepcopy(raw)
    for _bkey, bval in result.get("behaviors", {}).items():
        count = bval.get("count")
        if isinstance(count, dict):
            es = count.get("event_selector")
            if isinstance(es, dict) and es.get("selector") is None:
                del es["selector"]
    return result


@dataclass(frozen=True, init=False)
class CohortDefinition:
    """A composed set of criteria combined with AND/OR logic.

    Produces valid Mixpanel cohort definition JSON (legacy ``selector`` +
    ``behaviors`` format) via ``to_dict()``. Behavior keys are globally
    re-indexed to ensure uniqueness across arbitrary nesting.

    Example:
        ```python
        from mixpanel_headless import CohortCriteria, CohortDefinition

        cohort = CohortDefinition.all_of(
            CohortCriteria.has_property("plan", "premium"),
            CohortCriteria.did_event("Purchase", at_least=3, within_days=30),
        )
        result = cohort.to_dict()
        # {"selector": {...}, "behaviors": {"bhvr_0": {...}}}
        ```
    """

    _criteria: tuple[CohortCriteria | CohortDefinition, ...]
    """One or more criteria or nested definitions."""

    _operator: Literal["and", "or"]
    """Boolean combinator."""

    def __init__(
        self,
        *criteria: CohortCriteria | CohortDefinition,
    ) -> None:
        """Create a definition combining criteria with AND logic.

        Equivalent to ``CohortDefinition.all_of(*criteria)``.

        Args:
            *criteria: One or more criteria or nested definitions.

        Raises:
            ValueError: If no criteria are provided (CD9).
        """
        if not criteria:
            raise ValueError("CohortDefinition requires at least one criterion")
        object.__setattr__(self, "_criteria", criteria)
        object.__setattr__(self, "_operator", "and")

    @classmethod
    def all_of(
        cls,
        *criteria: CohortCriteria | CohortDefinition,
    ) -> CohortDefinition:
        """Combine criteria and/or definitions with AND logic.

        Args:
            *criteria: One or more criteria or nested definitions.

        Returns:
            CohortDefinition with AND combinator.

        Raises:
            ValueError: If no criteria are provided (CD9).
        """
        if not criteria:
            raise ValueError("CohortDefinition requires at least one criterion")
        instance = cls.__new__(cls)
        object.__setattr__(instance, "_criteria", criteria)
        object.__setattr__(instance, "_operator", "and")
        return instance

    @classmethod
    def any_of(
        cls,
        *criteria: CohortCriteria | CohortDefinition,
    ) -> CohortDefinition:
        """Combine criteria and/or definitions with OR logic.

        Args:
            *criteria: One or more criteria or nested definitions.

        Returns:
            CohortDefinition with OR combinator.

        Raises:
            ValueError: If no criteria are provided (CD9).
        """
        if not criteria:
            raise ValueError("CohortDefinition requires at least one criterion")
        instance = cls.__new__(cls)
        object.__setattr__(instance, "_criteria", criteria)
        object.__setattr__(instance, "_operator", "or")
        return instance

    def to_dict(self) -> dict[str, Any]:
        """Serialize to Mixpanel cohort definition format.

        Produces ``{"selector": {...}, "behaviors": {...}}`` with globally
        re-indexed behavior keys (``bhvr_0``, ``bhvr_1``, ...) ensuring
        uniqueness across arbitrary nesting depth.

        Returns:
            Dict with ``selector`` expression tree and ``behaviors`` map.

        Example:
            ```python
            cohort = CohortDefinition.all_of(
                CohortCriteria.has_property("plan", "premium"),
                CohortCriteria.did_event("Purchase", at_least=3, within_days=30),
            )
            data = cohort.to_dict()
            # {"selector": {"operator": "and", "children": [...]},
            #  "behaviors": {"bhvr_0": {...}}}

            # Pass directly to cohort CRUD:
            ws.create_cohort(CreateCohortParams(
                name="Premium Purchasers",
                definition=data,
            ))
            ```
        """
        # CD10: Behavior key uniqueness is enforced by sequential re-indexing
        # (bhvr_0, bhvr_1, ...) during tree traversal below.
        behaviors: dict[str, Any] = {}
        counter = [0]  # mutable container for closure

        def _collect_and_build(
            item: CohortCriteria | CohortDefinition,
        ) -> dict[str, Any]:
            """Recursively build selector tree and collect behaviors.

            Args:
                item: Criterion or nested definition to process.

            Returns:
                Selector node dict (leaf or combinator).
            """
            if isinstance(item, CohortCriteria):
                # Deep copy: operand may be a mutable list (e.g. has_property
                # with list value), so shallow dict() is not sufficient.
                node = copy.deepcopy(item._selector_node)
                if item._behavior_key is not None and item._behavior is not None:
                    new_key = f"bhvr_{counter[0]}"
                    counter[0] += 1
                    behaviors[new_key] = copy.deepcopy(item._behavior)
                    node["value"] = new_key
                return node
            # CohortDefinition: recurse into children
            children = [_collect_and_build(c) for c in item._criteria]
            return {
                "operator": item._operator,
                "children": children,
            }

        selector = _collect_and_build(self)
        return {"selector": selector, "behaviors": behaviors}


@dataclass(frozen=True)
class CohortBreakdown:
    """Break down query results by cohort membership.

    Represents a cohort-based breakdown dimension for use in the
    ``group_by=`` parameter of ``query()``, ``query_funnel()``,
    and ``query_retention()``.

    Accepts either a saved cohort ID (``int``) or an inline
    ``CohortDefinition``. When ``include_negated=True`` (default),
    both "In Cohort" and "Not In Cohort" segments are shown.

    Attributes:
        cohort: Saved cohort ID (positive integer) or inline
            ``CohortDefinition``.
        name: Display name. Optional for saved cohorts; recommended
            for inline definitions.
        include_negated: Whether to include a "Not In" segment.
            Default: ``True``.

    Example:
        ```python
        from mixpanel_headless import CohortBreakdown

        # Segment by saved cohort
        result = ws.query("Purchase", group_by=CohortBreakdown(123, "Power Users"))

        # Without "Not In" segment
        result = ws.query(
            "Purchase",
            group_by=CohortBreakdown(123, "Power Users", include_negated=False),
        )
        ```
    """

    cohort: int | CohortDefinition
    """Saved cohort ID or inline definition."""

    name: str | None = None
    """Display name for the cohort."""

    include_negated: bool = True
    """Whether to include a 'Not In' segment."""

    def __post_init__(self) -> None:
        """Validate construction arguments.

        Raises:
            ValueError: If cohort ID is not positive (CB1) or name
                is empty when provided (CB2).
        """
        _validate_cohort_args(self.cohort, self.name)


@dataclass(frozen=True)
class CohortMetric:
    """Track cohort size over time as an event metric.

    Represents a cohort size metric for use in the ``events=``
    parameter of ``query()`` (insights only). Produces a show clause
    with ``behavior.type: "cohort"`` in the bookmark JSON.

    Cannot be used with ``query_funnel()``, ``query_retention()``,
    or ``query_flow()`` (CM4 — insights only).

    Inline ``CohortDefinition`` is not supported (CM5 — server returns
    500). Use a saved cohort ID instead. This is enforced at construction.

    Attributes:
        cohort: Saved cohort ID (positive integer) or inline
            ``CohortDefinition``.
        name: Display name / series label. Optional for saved
            cohorts; recommended for inline definitions.

    Example:
        ```python
        from mixpanel_headless import CohortMetric, Metric, Formula

        # Track cohort growth
        result = ws.query(CohortMetric(123, "Power Users"), last=90, unit="week")

        # Mix with event metrics and formulas
        result = ws.query(
            [Metric("Login", math="unique"), CohortMetric(123, "Power Users")],
            formula="(B / A) * 100",
            formula_label="Power User %",
        )
        ```
    """

    cohort: int | CohortDefinition
    """Saved cohort ID or inline definition."""

    name: str | None = None
    """Display name / series label."""

    def __post_init__(self) -> None:
        """Validate construction arguments.

        Raises:
            ValueError: If cohort ID is not positive (CM1), name
                is empty when provided (CM2), or cohort is an inline
                ``CohortDefinition`` (CM5 — server returns 500).
        """
        _validate_cohort_args(self.cohort, self.name)
        # CM5: Inline CohortDefinition causes server-side 500.
        if isinstance(self.cohort, CohortDefinition):
            raise ValueError(
                "CohortMetric does not support inline CohortDefinition "
                "(server returns 500). Use a saved cohort ID instead."
            )


@dataclass(frozen=True)
class FrequencyBreakdown:
    """Break down query results by how often users performed an event.

    Used with ``Workspace.query()`` / ``build_params()`` in the
    ``group_by=`` parameter to segment users by event frequency.

    Attributes:
        event: Event name to count frequency for.
        bucket_size: Width of each frequency bucket. Default: ``1``.
        bucket_min: Minimum frequency value. Default: ``0``.
        bucket_max: Maximum frequency value. Default: ``10``.
        label: Display label for the breakdown. ``None`` generates
            ``"<event> Frequency"`` (e.g., ``"Purchase Frequency"``).

    Raises:
        ValueError: If validation rules FB1-FB4 are violated.

    Example:
        ```python
        from mixpanel_headless import FrequencyBreakdown

        # How often users purchased (0-10 in increments of 1)
        result = ws.query("Login", group_by=FrequencyBreakdown("Purchase"))

        # Custom buckets: 0-50 in increments of 5
        result = ws.query(
            "Login",
            group_by=FrequencyBreakdown(
                "Purchase", bucket_size=5, bucket_min=0, bucket_max=50
            ),
        )
        ```
    """

    event: str
    """Event name to count frequency for."""

    bucket_size: int = 1
    """Width of each frequency bucket."""

    bucket_min: int = 0
    """Minimum frequency value."""

    bucket_max: int = 10
    """Maximum frequency value."""

    label: str | None = None
    """Display label for the breakdown."""

    def __post_init__(self) -> None:
        """Validate construction arguments (rules FB1-FB4).

        Raises:
            ValueError: If event is empty (FB1), bucket_size is not
                positive (FB2), bucket_min >= bucket_max (FB3), or
                bucket_min is negative (FB4).
        """
        # FB1: event must be non-empty
        if not self.event.strip():
            raise ValueError("FrequencyBreakdown.event must be a non-empty string")
        # FB2: bucket_size must be positive
        if self.bucket_size <= 0:
            raise ValueError(
                f"FrequencyBreakdown.bucket_size must be positive, "
                f"got {self.bucket_size}"
            )
        # FB4: bucket_min must be non-negative (check before FB3 for clarity)
        if self.bucket_min < 0:
            raise ValueError(
                f"FrequencyBreakdown.bucket_min must be non-negative, "
                f"got {self.bucket_min}"
            )
        # FB3: bucket_min must be < bucket_max
        if self.bucket_min >= self.bucket_max:
            raise ValueError(
                f"FrequencyBreakdown.bucket_min ({self.bucket_min}) must be "
                f"less than bucket_max ({self.bucket_max})"
            )


@dataclass(frozen=True)
class FrequencyFilter:
    """Filter query results by how often users performed an event.

    Used with ``Workspace.query()`` / ``build_params()`` in the
    ``where=`` parameter to restrict results to users meeting a
    frequency threshold.

    Attributes:
        event: Event name to count frequency for.
        operator: Comparison operator. Default: ``"is at least"``.
        value: Threshold value for the comparison.
        date_range_value: Lookback window size. Must be paired with
            ``date_range_unit``.
        date_range_unit: Lookback window unit (``"day"``, ``"week"``,
            ``"month"``). Must be paired with ``date_range_value``.
        event_filters: Property filters applied to the frequency event
            before counting.
        label: Display label for the filter.

    Raises:
        ValueError: If validation rules FF1-FF5 are violated.

    Example:
        ```python
        from mixpanel_headless import FrequencyFilter

        # Users who logged in at least 5 times
        result = ws.query("Purchase", where=FrequencyFilter("Login", value=5))

        # Users who purchased 3+ times in the last 30 days
        result = ws.query(
            "Login",
            where=FrequencyFilter(
                "Purchase",
                value=3,
                date_range_value=30,
                date_range_unit="day",
            ),
        )
        ```
    """

    event: str
    """Event name to count frequency for."""

    value: int | float
    """Threshold value for the comparison."""

    operator: FrequencyFilterOperator = "is at least"
    """Comparison operator."""

    date_range_value: int | None = None
    """Lookback window size."""

    date_range_unit: Literal["day", "week", "month"] | None = None
    """Lookback window unit."""

    event_filters: list[Filter] | None = None
    """Property filters applied to the frequency event."""

    label: str | None = None
    """Display label for the filter."""

    def __post_init__(self) -> None:
        """Validate construction arguments (rules FF1-FF5).

        Raises:
            ValueError: If event is empty (FF1), operator is invalid
                (FF2), value is negative (FF3), date_range_value and
                date_range_unit are not both set or both None (FF4),
                or date_range_value is not positive when set (FF5).
        """
        from mixpanel_headless._internal.bookmark_enums import (
            VALID_FREQUENCY_FILTER_OPERATORS,
        )

        # FF1: event must be non-empty
        if not self.event.strip():
            raise ValueError("FrequencyFilter.event must be a non-empty string")
        # FF2: operator must be valid
        if self.operator not in VALID_FREQUENCY_FILTER_OPERATORS:
            valid = ", ".join(sorted(VALID_FREQUENCY_FILTER_OPERATORS))
            raise ValueError(
                f"FrequencyFilter.operator must be one of: {valid}; "
                f"got {self.operator!r}"
            )
        # FF3: value must be non-negative
        if self.value < 0:
            raise ValueError(
                f"FrequencyFilter.value must be non-negative, got {self.value}"
            )
        # FF4: date_range_value and date_range_unit must both be set or both None
        has_value = self.date_range_value is not None
        has_unit = self.date_range_unit is not None
        if has_value != has_unit:
            raise ValueError(
                "FrequencyFilter.date_range_value and date_range_unit must "
                "both be set or both be None; got date_range_value="
                f"{self.date_range_value!r}, date_range_unit="
                f"{self.date_range_unit!r}"
            )
        # FF5: date_range_value must be positive if set
        if self.date_range_value is not None and self.date_range_value <= 0:
            raise ValueError(
                f"FrequencyFilter.date_range_value must be positive when set, "
                f"got {self.date_range_value}"
            )


def _normalize_date_key(date_key: str) -> str:
    """Strip timezone offset from ISO timestamps.

    Args:
        date_key: Date string from API response.

    Returns:
        Date string with timezone offset removed if present.
        ``"2024-01-01T00:00:00-07:00"`` → ``"2024-01-01T00:00:00"``,
        ``"2024-01-01T00:00:00"`` → unchanged (hourly),
        ``"2024-01-01"`` → unchanged (daily).
    """
    if len(date_key) > 19 and "T" in date_key:
        return date_key[:19]
    return date_key


@dataclass(frozen=True)
class QueryResult(ResultWithDataFrame):
    """Structured output from a Workspace.query() execution.

    Contains the query response data with lazy DataFrame conversion.
    The series structure varies by query mode:

    - Timeseries: ``{metric_name: {date_string: value}}``
    - Total: ``{metric_name: {"all": value}}``

    Attributes:
        computed_at: When the query was computed (ISO format).
        from_date: Effective start date from response.
        to_date: Effective end date from response.
        headers: Column headers from the insights response.
        series: Query result data (structure varies by mode).
        params: Generated bookmark params sent to API (for debugging/persistence).
        meta: Response metadata (sampling factor, limits hit).

    Example:
        ```python
        result = ws.query("Login", math="unique", last=7)

        # DataFrame access
        print(result.df.head())

        # Inspect generated params
        print(result.params)

        # Save as a report
        ws.create_bookmark(CreateBookmarkParams(
            name="Login Uniques (7d)",
            bookmark_type="insights",
            params=result.params,
        ))
        ```
    """

    computed_at: str
    """When the query was computed (ISO format)."""

    from_date: str
    """Effective start date from response."""

    to_date: str
    """Effective end date from response."""

    headers: list[str] = field(default_factory=list)
    """Column headers from the insights response."""

    series: dict[str, Any] = field(default_factory=dict)
    """Query result data.

    For timeseries: ``{metric_name: {date_string: value}}``
    For total: ``{metric_name: {"all": value}}``
    """

    params: dict[str, Any] = field(default_factory=dict)
    """Generated bookmark params sent to API (for debugging/persistence)."""

    meta: dict[str, Any] = field(default_factory=dict)
    """Response metadata. Conforms to :class:`QueryMeta`
    (sampling_factor, is_cached, computation_time, query_id)."""

    @property
    def df(self) -> pd.DataFrame:
        """Convert to DataFrame.

        For timeseries mode: columns are ``date``, ``event``, ``count``.
        For total mode: columns are ``event``, ``count``.
        For segmented timeseries (with ``group_by``): columns are
        ``date``, ``event``, ``segment``, ``count``.
        For segmented total (with ``group_by``): columns are
        ``event``, ``segment``, ``count``.

        Returns:
            Normalized DataFrame with one row per (date, metric, segment)
            combination. Segmented responses are detected automatically
            by checking whether inner values are dicts (segment nesting)
            or scalars (flat response).
        """
        if self._df_cache is not None:
            return self._df_cache

        rows: list[dict[str, Any]] = []
        has_segments = False
        has_dates = False

        for metric_name, date_values in self.series.items():
            if not isinstance(date_values, dict):
                continue

            # Detect segmented response: if any value is a dict,
            # the structure is {segment: {date_or_"all": scalar}}
            first_value = next(iter(date_values.values()), None)
            if isinstance(first_value, dict):
                has_segments = True
                for segment_name, segment_data in date_values.items():
                    if not isinstance(segment_data, dict):
                        continue
                    for date_key, value in segment_data.items():
                        if date_key == "all":
                            rows.append(
                                {
                                    "event": metric_name,
                                    "segment": segment_name,
                                    "count": value,
                                }
                            )
                        else:
                            has_dates = True
                            normalized_date = _normalize_date_key(date_key)
                            rows.append(
                                {
                                    "date": normalized_date,
                                    "event": metric_name,
                                    "segment": segment_name,
                                    "count": value,
                                }
                            )
            else:
                # Flat response: {date_or_"all": scalar}
                for date_key, value in date_values.items():
                    if date_key == "all":
                        rows.append({"event": metric_name, "count": value})
                    else:
                        has_dates = True
                        normalized_date = _normalize_date_key(date_key)
                        rows.append(
                            {
                                "date": normalized_date,
                                "event": metric_name,
                                "count": value,
                            }
                        )

        if has_segments and has_dates:
            cols = ["date", "event", "segment", "count"]
        elif has_segments:
            cols = ["event", "segment", "count"]
        elif has_dates:
            cols = ["date", "event", "count"]
        else:
            cols = ["event", "count"]

        result_df = (
            pd.DataFrame(rows, columns=cols)
            if rows
            else pd.DataFrame(columns=["date", "event", "count"])
        )

        object.__setattr__(self, "_df_cache", result_df)
        return result_df

    def to_dict(self) -> dict[str, Any]:
        """Serialize for JSON output.

        Returns:
            Dictionary with all QueryResult fields.
        """
        return {
            "computed_at": self.computed_at,
            "from_date": self.from_date,
            "to_date": self.to_date,
            "headers": self.headers,
            "series": self.series,
            "params": self.params,
            "meta": self.meta,
        }


# =============================================================================
# Typed Result Structures (TypedDicts for agent-friendly result access)
# =============================================================================


class QueryMeta(TypedDict, total=False):
    """Response metadata shared across all query result types.

    All fields are optional since the API may omit them depending on
    the query type and server-side configuration.

    Attributes:
        sampling_factor: Fraction of data sampled (1.0 = no sampling).
        is_cached: Whether the result was served from cache.
        computation_time: Server-side computation time in milliseconds.
        query_id: Unique identifier for this query execution.
    """

    sampling_factor: float
    is_cached: bool
    computation_time: float
    query_id: str


class FunnelStepData(TypedDict):
    """Step-level data in a funnel query result.

    Each element in ``FunnelQueryResult.steps_data`` conforms to this
    structure. Provides per-step conversion metrics and timing data.

    Attributes:
        event: Event name for this funnel step.
        count: Number of users/events that reached this step.
        step_conv_ratio: Conversion rate from the previous step (0.0-1.0).
        overall_conv_ratio: Conversion rate from the first step (0.0-1.0).
        avg_time: Average time from the previous step (seconds).
        avg_time_from_start: Average time from the first step (seconds).
    """

    event: str
    count: int
    step_conv_ratio: float
    overall_conv_ratio: float
    avg_time: float
    avg_time_from_start: float


class RetentionCohortData(TypedDict):
    """Cohort-level data in a retention query result.

    Each value in ``RetentionQueryResult.cohorts`` and related segment
    dicts conforms to this structure. Contains the cohort size and
    per-bucket retention counts and rates.

    Attributes:
        first: Size of the cohort (number of users who performed the
            born event in this period).
        counts: List of retained user counts per retention bucket.
            Index 0 is the born bucket (always equals ``first``).
        rates: List of retention rates per bucket (0.0-1.0).
            Index 0 is always 1.0 (100% retention at birth).
    """

    first: int
    counts: list[int]
    rates: list[float]


class FlowStepNode(TypedDict, total=False):
    """Node data in a flow query result.

    Each element in ``FlowQueryResult.steps`` conforms to this
    structure. Represents a single node in the flow graph.

    Attributes:
        event: Event name for this flow node.
        totalCount: Total count as a string (API returns string,
            parsed to int by ``nodes_df``).
        type: Node type (ANCHOR, NORMAL, DROPOFF, PRUNED, etc.).
        anchorType: Anchor classification (NORMAL, RELATIVE_REVERSE,
            RELATIVE_FORWARD).
        isCustomEvent: Whether this is a custom event.
        conversionRateChange: Change in conversion rate at this node.
    """

    event: str
    totalCount: str
    type: FlowNodeType
    anchorType: FlowAnchorType
    isCustomEvent: bool
    conversionRateChange: float | None


class FlowEdge(TypedDict, total=False):
    """Edge data in a flow query result.

    Each element in ``FlowQueryResult.flows`` conforms to this
    structure. Represents a transition between nodes in the flow.

    Attributes:
        source: Source event name.
        target: Target event name.
        count: Number of users/events traversing this edge.
        step: Step index in the flow.
    """

    source: str
    target: str
    count: int
    step: int


# =============================================================================
# Funnel Query Types (Phase 032)
# =============================================================================

# FunnelMathType is re-exported from _literal_types (imported above)
# for backward compatibility.


@dataclass(frozen=True)
class FunnelStep:
    """A single step in a funnel query.

    Use plain event-name strings for simple funnels. Use ``FunnelStep``
    objects when you need per-step filters, labels, or ordering overrides.

    Attributes:
        event: Mixpanel event name for this funnel step.
        label: Display label for this step. Defaults to the event name
            when ``None``.
        filters: Per-step filter conditions. Each ``Filter`` restricts
            which events count for this step. ``None`` means no filters.
        filters_combinator: How per-step filters combine.
            ``"all"`` requires all filters to match (AND logic).
            ``"any"`` requires any filter to match (OR logic).
        order: Per-step ordering override. Only meaningful when the
            top-level funnel ``order`` is ``"any"``. ``None`` inherits
            the top-level order.

    Example:
        ```python
        from mixpanel_headless import FunnelStep, Filter

        # Simple step (equivalent to just using "Signup" string)
        step1 = FunnelStep("Signup")

        # Step with per-step filter and label
        step2 = FunnelStep(
            "Purchase",
            label="High-Value Purchase",
            filters=[Filter.greater_than("amount", 50)],
        )

        ws.query_funnel([step1, step2])
        ```
    """

    event: str
    """Mixpanel event name for this funnel step."""

    label: str | None = None
    """Display label for this step (defaults to event name)."""

    filters: list[Filter] | None = None
    """Per-step filter conditions."""

    filters_combinator: FiltersCombinator = "all"
    """How per-step filters combine (AND/OR)."""

    order: FunnelOrder | None = None
    """Per-step ordering override (only meaningful with top-level order='any')."""

    def __post_init__(self) -> None:
        """Validate construction arguments.

        Raises:
            ValueError: If event is empty or contains control characters (FS1).
        """
        _validate_event_name(self.event, "FunnelStep")


@dataclass(frozen=True)
class Exclusion:
    """An event to exclude between funnel steps.

    Users who perform the excluded event within the specified step range
    are removed from the funnel. Use plain strings for full-range
    exclusions; use ``Exclusion`` objects when you need to target
    specific step ranges.

    Attributes:
        event: Event name to exclude between steps.
        from_step: Start of exclusion range (0-indexed, inclusive).
            Defaults to 0 (first step).
        to_step: End of exclusion range (0-indexed, inclusive).
            ``None`` means up to the last step in the funnel.

    Example:
        ```python
        from mixpanel_headless import Exclusion

        # Exclude between all steps (same as using string "Logout")
        ex1 = Exclusion("Logout")

        # Exclude only between steps 1 and 2
        ex2 = Exclusion("Refund", from_step=1, to_step=2)

        ws.query_funnel(
            ["Signup", "Add to Cart", "Purchase"],
            exclusions=[ex1, ex2],
        )
        ```
    """

    event: str
    """Event name to exclude between steps."""

    from_step: int = 0
    """Start of exclusion range (0-indexed, inclusive)."""

    to_step: int | None = None
    """End of exclusion range (0-indexed, inclusive). None = last step."""

    def __post_init__(self) -> None:
        """Validate construction arguments.

        Raises:
            ValueError: If event is empty (EX1), from_step is negative
                (EX2), or to_step < from_step (EX3).
        """
        _validate_event_name(self.event, "Exclusion")
        if self.from_step < 0:
            raise ValueError(f"Exclusion.from_step must be >= 0, got {self.from_step}")
        if self.to_step is not None and self.to_step < self.from_step:
            raise ValueError(
                f"Exclusion.to_step ({self.to_step}) must be >= "
                f"from_step ({self.from_step})"
            )


@dataclass(frozen=True)
class HoldingConstant:
    """A property to hold constant across all funnel steps.

    When a property is held constant, only users whose property value
    is the same at every funnel step are counted as converting. For
    example, holding ``"platform"`` constant means a user who signed up
    on iOS but purchased on web is not counted as converting.

    Attributes:
        property: Property name to hold constant across steps.
        resource_type: Whether this is an event property or a
            user-profile property. Defaults to ``"events"``.

    Example:
        ```python
        from mixpanel_headless import HoldingConstant

        # Hold an event property constant (default)
        hc1 = HoldingConstant("platform")

        # Hold a user-profile property constant
        hc2 = HoldingConstant("plan_tier", resource_type="people")

        ws.query_funnel(
            ["Signup", "Purchase"],
            holding_constant=[hc1, hc2],
        )
        ```
    """

    property: str
    """Property name to hold constant across steps."""

    resource_type: Literal["events", "people"] = "events"
    """Whether this is an event property or user-profile property."""

    def __post_init__(self) -> None:
        """Validate construction arguments.

        Raises:
            ValueError: If property is empty (HC1).
        """
        if not self.property or not self.property.strip():
            raise ValueError("HoldingConstant.property must be a non-empty string")


@dataclass(frozen=True)
class FunnelQueryResult(ResultWithDataFrame):
    """Result of a funnel query via the insights API.

    Contains step-level conversion data, timing information, the
    generated bookmark params (for debugging or persisting as a saved
    report), and a lazy DataFrame conversion.

    Unlike ``FunnelResult`` (which wraps the legacy funnel API), this
    type wraps the richer bookmark-based insights API response and
    provides additional fields like ``avg_time``, ``avg_time_from_start``,
    and the ``params`` dict.

    Attributes:
        computed_at: When the query was computed (ISO format).
        from_date: Effective start date from the response.
        to_date: Effective end date from the response.
        steps_data: Step-level results. Each dict contains keys:
            ``event``, ``count``, ``step_conv_ratio``,
            ``overall_conv_ratio``, ``avg_time``,
            ``avg_time_from_start``.
        series: Raw series data from the API (for advanced use).
        params: Generated bookmark params sent to the API
            (for debugging or persistence via ``create_bookmark``).
        meta: Response metadata (e.g. ``sampling_factor``,
            ``is_cached``).

    Example:
        ```python
        result = ws.query_funnel(["Signup", "Purchase"])

        # Overall conversion
        print(result.overall_conversion_rate)  # e.g. 0.12

        # DataFrame view
        print(result.df)
        #   step  event   count  step_conv_ratio  overall_conv_ratio  ...

        # Save as a report
        ws.create_bookmark(CreateBookmarkParams(
            name="Signup → Purchase Funnel",
            bookmark_type="funnels",
            params=result.params,
        ))
        ```
    """

    computed_at: str
    """When the query was computed (ISO format)."""

    from_date: str
    """Effective start date from the response."""

    to_date: str
    """Effective end date from the response."""

    steps_data: list[dict[str, Any]] = field(default_factory=list)
    """Step-level results. Each dict conforms to :class:`FunnelStepData`
    (event, count, step_conv_ratio, overall_conv_ratio, avg_time,
    avg_time_from_start)."""

    series: dict[str, Any] = field(default_factory=dict)
    """Raw series data from the API."""

    params: dict[str, Any] = field(default_factory=dict)
    """Generated bookmark params sent to API."""

    meta: dict[str, Any] = field(default_factory=dict)
    """Response metadata. Conforms to :class:`QueryMeta`
    (sampling_factor, is_cached, computation_time, query_id)."""

    @property
    def overall_conversion_rate(self) -> float:
        """End-to-end conversion rate from first to last step.

        Returns:
            Float between 0.0 and 1.0 representing the fraction of
            users who completed all funnel steps. Returns 0.0 if
            ``steps_data`` is empty.
        """
        if not self.steps_data:
            return 0.0
        last = self.steps_data[-1]
        return float(last.get("overall_conv_ratio", 0.0))

    @property
    def df(self) -> pd.DataFrame:
        """Convert to DataFrame with one row per funnel step.

        Columns: ``step``, ``event``, ``count``, ``step_conv_ratio``,
        ``overall_conv_ratio``, ``avg_time``, ``avg_time_from_start``.

        Returns:
            Normalized DataFrame with one row per step.
        """
        if self._df_cache is not None:
            return self._df_cache

        cols = [
            "step",
            "event",
            "count",
            "step_conv_ratio",
            "overall_conv_ratio",
            "avg_time",
            "avg_time_from_start",
        ]

        rows: list[dict[str, Any]] = []
        for i, step in enumerate(self.steps_data, start=1):
            rows.append(
                {
                    "step": i,
                    "event": step.get("event", f"Step {i}"),
                    "count": step.get("count", 0),
                    "step_conv_ratio": step.get("step_conv_ratio", 0.0),
                    "overall_conv_ratio": step.get("overall_conv_ratio", 0.0),
                    "avg_time": step.get("avg_time", 0.0),
                    "avg_time_from_start": step.get("avg_time_from_start", 0.0),
                }
            )

        result_df = (
            pd.DataFrame(rows, columns=cols) if rows else pd.DataFrame(columns=cols)
        )

        object.__setattr__(self, "_df_cache", result_df)
        return result_df

    def to_dict(self) -> dict[str, Any]:
        """Serialize for JSON output.

        Returns:
            Dictionary with all FunnelQueryResult fields.
        """
        return {
            "computed_at": self.computed_at,
            "from_date": self.from_date,
            "to_date": self.to_date,
            "steps_data": self.steps_data,
            "series": self.series,
            "params": self.params,
            "meta": self.meta,
        }


# =============================================================================
# Retention Query Types (Phase 033)
# =============================================================================

# RetentionAlignment, RetentionMode, RetentionMathType are re-exported
# from _literal_types (imported above) for backward compatibility.


@dataclass(frozen=True)
class RetentionEvent:
    """An event specification for retention queries.

    Wraps an event name with optional per-event filters. Use plain
    event-name strings for simple retention queries. Use ``RetentionEvent``
    objects when you need per-event filter conditions.

    Attributes:
        event: Mixpanel event name.
        filters: Per-event filter conditions. Each ``Filter`` restricts
            which events count. ``None`` means no filters.
        filters_combinator: How per-event filters combine.
            ``"all"`` requires all filters to match (AND logic).
            ``"any"`` requires any filter to match (OR logic).

    Example:
        ```python
        from mixpanel_headless import RetentionEvent, Filter

        # Simple event (equivalent to just using "Signup" string)
        born = RetentionEvent("Signup")

        # Event with per-event filter
        born = RetentionEvent(
            "Signup",
            filters=[Filter.equals("source", "organic")],
        )

        ws.query_retention(born, "Login")
        ```
    """

    event: str
    """Mixpanel event name."""

    filters: list[Filter] | None = None
    """Per-event filter conditions."""

    filters_combinator: FiltersCombinator = "all"
    """How per-event filters combine (AND/OR)."""

    def __post_init__(self) -> None:
        """Validate construction arguments.

        Raises:
            ValueError: If event is empty or contains control characters (RE1).
        """
        _validate_event_name(self.event, "RetentionEvent")


@dataclass(frozen=True)
class RetentionQueryResult(ResultWithDataFrame):
    """Result of a retention query via the insights API.

    Contains cohort-level retention data, the generated bookmark params
    (for debugging or persisting as a saved report), and a lazy
    DataFrame conversion. Supports both unsegmented and segmented
    (``group_by``) queries.

    Attributes:
        computed_at: When the query was computed (ISO format).
        from_date: Effective start date from the response.
        to_date: Effective end date from the response.
        cohorts: Aggregate cohort-level retention data. Keys are cohort
            date strings (``YYYY-MM-DD``), values are dicts with
            ``first`` (cohort size), ``counts`` (list of retained user
            counts per bucket), and ``rates`` (list of retention rates
            per bucket). For segmented queries, this contains the
            ``$overall`` aggregate.
        average: Synthetic ``$average`` cohort data. Same structure
            as individual cohort entries.
        params: Generated bookmark params sent to the API
            (for debugging or persistence via ``create_bookmark``).
        meta: Response metadata (e.g. ``sampling_factor``,
            ``is_cached``).
        segments: Per-segment cohort data. Maps segment name to a dict
            of cohort_date → {first, counts, rates}. Empty for
            unsegmented queries.
        segment_averages: Per-segment ``$average`` cohort data. Maps
            segment name to {first, counts, rates}. Empty for
            unsegmented queries.

    Example:
        ```python
        # Unsegmented retention
        result = ws.query_retention("Signup", "Login")
        print(result.df)
        #   cohort_date  bucket  count  rate

        # Segmented retention
        result = ws.query_retention(
            "Signup", "Login", group_by="platform"
        )
        print(result.df)
        #   segment  cohort_date  bucket  count  rate
        for name, cohorts in result.segments.items():
            print(f"{name}: {len(cohorts)} cohorts")
        ```
    """

    computed_at: str
    """When the query was computed (ISO format)."""

    from_date: str
    """Effective start date from the response."""

    to_date: str
    """Effective end date from the response."""

    cohorts: dict[str, dict[str, Any]] = field(default_factory=dict)
    """Cohort-level retention data. Each value conforms to
    :class:`RetentionCohortData` (first, counts, rates).

    For segmented queries, this contains the ``$overall`` aggregate.
    """

    average: dict[str, Any] = field(default_factory=dict)
    """Synthetic $average cohort data. Conforms to :class:`RetentionCohortData`."""

    params: dict[str, Any] = field(default_factory=dict)
    """Generated bookmark params sent to API."""

    meta: dict[str, Any] = field(default_factory=dict)
    """Response metadata. Conforms to :class:`QueryMeta`."""

    segments: dict[str, dict[str, dict[str, Any]]] = field(default_factory=dict)
    """Per-segment cohort data. Each inner value conforms to
    :class:`RetentionCohortData` (first, counts, rates).

    Empty for unsegmented queries. Populated when ``group_by`` is used
    and the API returns breakdown segments alongside ``$overall``.
    """

    segment_averages: dict[str, dict[str, Any]] = field(default_factory=dict)
    """Per-segment $average cohort data. Each value conforms to
    :class:`RetentionCohortData`.

    Empty for unsegmented queries.
    """

    @property
    def df(self) -> pd.DataFrame:
        """Convert to DataFrame with one row per (cohort_date, bucket) pair.

        For unsegmented queries, columns are:
        ``cohort_date``, ``bucket``, ``count``, ``rate``.

        For segmented queries (when ``segments`` is non-empty), columns are:
        ``segment``, ``cohort_date``, ``bucket``, ``count``, ``rate``.

        Returns:
            Normalized DataFrame. Empty DataFrame with correct columns
            if data is empty.
        """
        if self._df_cache is not None:
            return self._df_cache

        rows: list[dict[str, Any]] = []

        if self.segments:
            cols = ["segment", "cohort_date", "bucket", "count", "rate"]
            for segment_name in sorted(self.segments.keys()):
                segment_cohorts = self.segments[segment_name]
                for cohort_date in sorted(segment_cohorts.keys()):
                    cohort = segment_cohorts[cohort_date]
                    counts = cohort.get("counts", [])
                    rates = cohort.get("rates", [])
                    for i, count in enumerate(counts):
                        rows.append(
                            {
                                "segment": segment_name,
                                "cohort_date": cohort_date,
                                "bucket": i,
                                "count": count,
                                "rate": rates[i] if i < len(rates) else 0.0,
                            }
                        )
        else:
            cols = ["cohort_date", "bucket", "count", "rate"]
            for cohort_date in sorted(self.cohorts.keys()):
                cohort = self.cohorts[cohort_date]
                counts = cohort.get("counts", [])
                rates = cohort.get("rates", [])
                for i, count in enumerate(counts):
                    rows.append(
                        {
                            "cohort_date": cohort_date,
                            "bucket": i,
                            "count": count,
                            "rate": rates[i] if i < len(rates) else 0.0,
                        }
                    )

        result_df = (
            pd.DataFrame(rows, columns=cols) if rows else pd.DataFrame(columns=cols)
        )

        object.__setattr__(self, "_df_cache", result_df)
        return result_df

    def to_dict(self) -> dict[str, Any]:
        """Serialize for JSON output.

        Returns:
            Dictionary with all RetentionQueryResult fields.
            Includes ``segments`` and ``segment_averages`` only
            when non-empty.
        """
        d: dict[str, Any] = {
            "computed_at": self.computed_at,
            "from_date": self.from_date,
            "to_date": self.to_date,
            "cohorts": self.cohorts,
            "average": self.average,
            "params": self.params,
            "meta": self.meta,
        }
        if self.segments:
            d["segments"] = self.segments
        if self.segment_averages:
            d["segment_averages"] = self.segment_averages
        return d


def _safe_int(value: Any, default: int = 0) -> int:
    """Parse a value to int, returning *default* on failure.

    The Mixpanel flows API returns ``totalCount`` as a string.
    Some edge cases (empty string, ``None``, non-numeric) would
    crash a bare ``int()`` call.  Emits a warning when unexpected
    types or non-numeric strings are encountered so that silent
    data corruption is detectable.

    Args:
        value: Value to parse (typically a string like ``"100"``).
        default: Fallback when parsing fails. Default: ``0``.

    Returns:
        Parsed integer, or *default* if parsing fails.
    """
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            warnings.warn(
                f"Non-numeric string for count field: {value!r}; "
                f"using default {default}",
                stacklevel=2,
            )
            return default
    if value is None:
        return default
    warnings.warn(
        f"Unexpected type for count field: "
        f"{type(value).__name__} ({value!r}); using default {default}",
        stacklevel=2,
    )
    return default


# =============================================================================
# Flow Query Types (Phase 034)
# =============================================================================


@dataclass(frozen=True)
class FlowStep:
    """An anchor event in a flow query with per-step configuration.

    Each flow step identifies a specific event and optional constraints
    (forward/reverse step counts, filters) that define a node in the
    flow analysis.

    Attributes:
        event: The event name to anchor this step on.
        forward: Maximum number of forward steps to trace from this event.
            ``None`` means use the query-level default.
        reverse: Maximum number of reverse steps to trace from this event.
            ``None`` means use the query-level default.
        label: Optional display label for this step. If ``None``, the event
            name is used as the label.
        filters: Optional list of ``Filter`` conditions to narrow the events
            matching this step. ``None`` means no per-step filtering.
        filters_combinator: How to combine multiple filters — ``"all"``
            requires every filter to match (AND), ``"any"`` requires at
            least one (OR). Defaults to ``"all"``.
        session_event: Optional session anchor type — ``"start"`` or
            ``"end"``. When set, the ``event`` field must match the
            corresponding session event name (``"$session_start"`` or
            ``"$session_end"``). ``None`` means this is a regular event
            step. Default: ``None``.

    Example:
        ```python
        step = FlowStep(
            "Purchase",
            forward=5,
            reverse=3,
            label="Buy",
            filters=[Filter.equals("country", "US")],
            filters_combinator="all",
        )

        # Session anchor step
        session_step = FlowStep(
            "$session_start",
            session_event="start",
        )
        ```
    """

    event: str
    forward: int | None = None
    reverse: int | None = None
    label: str | None = None
    filters: list[Filter] | None = None
    filters_combinator: FiltersCombinator = "all"
    session_event: FlowSessionEvent | None = None

    def __post_init__(self) -> None:
        """Validate construction arguments.

        Raises:
            ValueError: If event is empty or contains control characters
                (FL1), forward/reverse is outside 0-5 range (FL2), or
                session_event conflicts with event name (FS1).
        """
        _validate_event_name(self.event, "FlowStep")
        if self.forward is not None and not 0 <= self.forward <= 5:
            raise ValueError(
                f"FlowStep.forward must be in range 0-5, got {self.forward}"
            )
        if self.reverse is not None and not 0 <= self.reverse <= 5:
            raise ValueError(
                f"FlowStep.reverse must be in range 0-5, got {self.reverse}"
            )
        # FS1: Validate session_event / event consistency
        if self.session_event is not None:
            expected_event = (
                "$session_start" if self.session_event == "start" else "$session_end"
            )
            if self.event != expected_event:
                raise ValueError(
                    f"FlowStep.session_event={self.session_event!r} requires "
                    f"event={expected_event!r}, got {self.event!r}"
                )


@dataclass(frozen=True)
class FlowTreeNode:
    """A node in a recursive flow prefix tree.

    Represents a single event in a flow path tree returned by the Mixpanel
    Flows API when using ``mode="tree"``. Each node tracks aggregate counts
    (total, drop-off, converted) and optionally timing percentiles. Children
    represent subsequent events in the flow.

    The tree preserves full path context — unlike the sankey graph which
    merges nodes at the same step position, each tree node is unique to
    its specific path from root.

    Attributes:
        event: The event name at this position in the flow.
        type: Node type — ``"ANCHOR"``, ``"NORMAL"``, ``"DROPOFF"``,
            ``"PRUNED"``, ``"FORWARD"``, or ``"REVERSE"``.
        step_number: Zero-based step index in the flow.
        total_count: Total number of users reaching this node.
        drop_off_count: Number of users who dropped off at this node.
        converted_count: Number of users who continued past this node.
        anchor_type: Anchor classification — ``"NORMAL"``,
            ``"RELATIVE_REVERSE"``, or ``"RELATIVE_FORWARD"``.
        is_computed: Whether this is a computed/custom event.
        children: Child nodes representing subsequent events. Defaults
            to an empty tuple.
        time_percentiles_from_start: Timing percentile data from flow
            start to this node. Empty dict if timing data is not enabled.
        time_percentiles_from_prev: Timing percentile data from the
            previous node to this node. Empty dict if timing data is
            not enabled.

    Example:
        ```python
        root = FlowTreeNode(
            event="Login", type="ANCHOR", step_number=0,
            total_count=1000, drop_off_count=50, converted_count=950,
            children=(
                FlowTreeNode(
                    event="Search", type="NORMAL", step_number=1,
                    total_count=600,
                ),
            ),
        )
        root.depth          # 1
        root.conversion_rate  # 0.95
        root.all_paths()    # [[root, search_node]]
        ```
    """

    event: str
    type: FlowNodeType
    step_number: int
    total_count: int
    drop_off_count: int = 0
    converted_count: int = 0
    anchor_type: FlowAnchorType = "NORMAL"
    is_computed: bool = False
    children: tuple[FlowTreeNode, ...] = ()
    time_percentiles_from_start: dict[str, Any] = field(default_factory=dict)
    time_percentiles_from_prev: dict[str, Any] = field(default_factory=dict)

    @property
    def depth(self) -> int:
        """Maximum depth of the subtree rooted at this node.

        A leaf node has depth 0. A node with one level of children
        has depth 1, and so on.

        Returns:
            Non-negative integer representing the longest path from
            this node to any leaf descendant.

        Example:
            ```python
            leaf = FlowTreeNode(
                event="Purchase", type="ANCHOR",
                step_number=0, total_count=100,
            )
            leaf.depth  # 0
            ```
        """
        if not self.children:
            return 0
        return 1 + max(c.depth for c in self.children)

    @property
    def node_count(self) -> int:
        """Total number of nodes in the subtree including this node.

        Returns:
            Positive integer (always >= 1).

        Example:
            ```python
            node.node_count  # 7
            ```
        """
        return 1 + sum(c.node_count for c in self.children)

    @property
    def leaf_count(self) -> int:
        """Number of leaf nodes (nodes with no children) in the subtree.

        Returns:
            Positive integer (always >= 1).

        Example:
            ```python
            node.leaf_count  # 4
            ```
        """
        if not self.children:
            return 1
        return sum(c.leaf_count for c in self.children)

    @property
    def conversion_rate(self) -> float:
        """Fraction of users who converted at this node.

        Computed as ``converted_count / total_count``. Returns ``0.0``
        when ``total_count`` is zero to avoid division errors.

        Returns:
            Float in ``[0.0, 1.0]``.

        Example:
            ```python
            node.conversion_rate  # 0.95
            ```
        """
        if self.total_count == 0:
            return 0.0
        return self.converted_count / self.total_count

    @property
    def drop_off_rate(self) -> float:
        """Fraction of users who dropped off at this node.

        Computed as ``drop_off_count / total_count``. Returns ``0.0``
        when ``total_count`` is zero to avoid division errors.

        Returns:
            Float in ``[0.0, 1.0]``.

        Example:
            ```python
            node.drop_off_rate  # 0.05
            ```
        """
        if self.total_count == 0:
            return 0.0
        return self.drop_off_count / self.total_count

    def all_paths(self) -> list[list[FlowTreeNode]]:
        """Return all root-to-leaf paths through this subtree.

        Each path is a list of ``FlowTreeNode`` objects from this node
        down to a leaf, preserving the full node chain so callers can
        inspect counts, rates, and timing along each path.

        Returns:
            List of paths, where each path is a list of nodes. The
            number of paths equals ``leaf_count``.

        Example:
            ```python
            for path in root.all_paths():
                events = [n.event for n in path]
                print(" -> ".join(events))
            # Login -> Search -> Purchase
            # Login -> Search -> DROPOFF
            # Login -> Browse -> Purchase
            # Login -> DROPOFF
            ```
        """
        if not self.children:
            return [[self]]
        paths: list[list[FlowTreeNode]] = []
        for child in self.children:
            for child_path in child.all_paths():
                paths.append([self, *child_path])
        return paths

    def find(self, event: str) -> list[FlowTreeNode]:
        """Find all nodes matching an event name via depth-first search.

        Args:
            event: The event name to search for.

        Returns:
            List of matching ``FlowTreeNode`` objects. Empty list if
            no nodes match.

        Example:
            ```python
            purchases = root.find("Purchase")
            # [FlowTreeNode(event="Purchase", ...), ...]
            ```
        """
        results: list[FlowTreeNode] = []
        if self.event == event:
            results.append(self)
        for child in self.children:
            results.extend(child.find(event))
        return results

    def flatten(self) -> list[FlowTreeNode]:
        """Return all nodes in pre-order (depth-first) traversal.

        The root node appears first, followed by its children's subtrees
        in order.

        Returns:
            List of all nodes in the subtree. Length equals
            ``node_count``.

        Example:
            ```python
            for node in root.flatten():
                print(f"{node.event}: {node.total_count}")
            ```
        """
        result: list[FlowTreeNode] = [self]
        for child in self.children:
            result.extend(child.flatten())
        return result

    def to_dict(self) -> dict[str, Any]:
        """Serialize the tree node recursively to a dictionary.

        Returns:
            Dictionary with all node attributes and recursively
            serialized children. Suitable for JSON serialization.

        Example:
            ```python
            d = node.to_dict()
            d["event"]     # "Login"
            d["children"]  # [{"event": "Search", ...}, ...]
            ```
        """
        return {
            "event": self.event,
            "type": self.type,
            "step_number": self.step_number,
            "total_count": self.total_count,
            "drop_off_count": self.drop_off_count,
            "converted_count": self.converted_count,
            "anchor_type": self.anchor_type,
            "is_computed": self.is_computed,
            "children": [c.to_dict() for c in self.children],
            "time_percentiles_from_start": self.time_percentiles_from_start,
            "time_percentiles_from_prev": self.time_percentiles_from_prev,
        }

    def render(
        self,
        _prefix: str = "",
        _is_last: bool = True,
        _is_root: bool = True,
    ) -> str:
        """Render the tree as an ASCII string for debugging.

        Uses box-drawing characters (``\u251c\u2500\u2500``, ``\u2514\u2500\u2500``, ``\u2502``) to display
        the tree hierarchy with event names and counts.

        Args:
            _prefix: Internal prefix for recursive indentation.
                Do not pass this argument directly.
            _is_last: Internal flag for connector selection.
                Do not pass this argument directly.
            _is_root: Internal flag distinguishing the root call
                from recursive children. Do not pass directly.

        Returns:
            Multi-line string representation of the tree.

        Example:
            ```python
            print(root.render())
            # Login (1000)
            # \u251c\u2500\u2500 Search (600)
            # \u2502   \u251c\u2500\u2500 Purchase (400)
            # \u2502   \u2514\u2500\u2500 DROPOFF (100)
            # \u251c\u2500\u2500 Browse (300)
            # \u2502   \u2514\u2500\u2500 Purchase (200)
            # \u2514\u2500\u2500 DROPOFF (50)
            ```
        """
        if _is_root:
            line = f"{self.event} ({self.total_count})\n"
            child_prefix = ""
        else:
            connector = "\u2514\u2500\u2500 " if _is_last else "\u251c\u2500\u2500 "
            line = f"{_prefix}{connector}{self.event} ({self.total_count})\n"
            child_prefix = _prefix + ("    " if _is_last else "\u2502   ")

        for i, child in enumerate(self.children):
            is_last_child = i == len(self.children) - 1
            line += child.render(
                _prefix=child_prefix, _is_last=is_last_child, _is_root=False
            )

        return line

    def to_anytree(self) -> Any:
        """Convert to an ``anytree.AnyNode`` tree with parent references.

        Creates a parallel anytree representation of this subtree. Each
        anytree node carries the same attributes (event, type, counts,
        etc.) and gains parent references, path resolution, and rendering
        capabilities from the anytree library.

        Returns:
            An ``anytree.AnyNode`` root with the full subtree attached.
            Use ``node.parent``, ``node.path``, ``node.children``,
            and ``anytree.RenderTree`` for navigation and display.

        Example:
            ```python
            from anytree import RenderTree, findall

            at = root.to_anytree()
            print(RenderTree(at))

            # Parent references
            purchase = findall(at, filter_=lambda n: n.event == "Purchase")[0]
            purchase.parent.event  # "Search"
            [n.event for n in purchase.path]  # ["Login", "Search", "Purchase"]
            ```
        """
        return self._build_anytree_node(parent=None)

    def _build_anytree_node(self, parent: Any) -> Any:
        """Recursively build an anytree node tree.

        Args:
            parent: The parent ``AnyNode``, or ``None`` for the root.

        Returns:
            An ``anytree.AnyNode`` with children attached.
        """
        from anytree import AnyNode

        node = AnyNode(
            parent=parent,
            event=self.event,
            type=self.type,
            step_number=self.step_number,
            total_count=self.total_count,
            drop_off_count=self.drop_off_count,
            converted_count=self.converted_count,
            anchor_type=self.anchor_type,
            is_computed=self.is_computed,
        )
        for child in self.children:
            child._build_anytree_node(parent=node)
        return node


@dataclass(frozen=True)
class FlowQueryResult(ResultWithDataFrame):
    """Result of an ad-hoc flow query.

    Holds the raw flow analysis data returned by the Mixpanel API,
    including step nodes, flow edges, breakdowns, and overall conversion.

    Attributes:
        computed_at: ISO-8601 timestamp when the query was computed.
        steps: List of step-node dicts from the API response.
        flows: List of flow-edge dicts describing transitions between steps.
        breakdowns: List of breakdown dicts when a breakdown property is used.
        overall_conversion_rate: Overall conversion rate across the flow
            (0.0 to 1.0).
        params: The query parameters that produced this result.
        meta: API metadata (sampling factor, request timing, etc.).
        mode: The flow visualization mode — ``"sankey"`` for Sankey diagrams,
            ``"paths"`` for top-paths analysis, or ``"tree"`` for prefix
            tree analysis.

    Example:
        ```python
        result = FlowQueryResult(
            computed_at="2025-01-15T10:00:00",
            steps=[{"event": "Login", "count": 100}],
            flows=[{"path": ["Login", "Purchase"], "count": 30}],
            overall_conversion_rate=0.3,
        )
        result.to_dict()
        # {"computed_at": "2025-01-15T10:00:00", ...}
        ```
    """

    computed_at: str
    steps: list[dict[str, Any]] = field(default_factory=list)
    """Step-node dicts. Each conforms to :class:`FlowStepNode`."""
    flows: list[dict[str, Any]] = field(default_factory=list)
    """Flow-edge dicts. Each conforms to :class:`FlowEdge`."""
    breakdowns: list[dict[str, Any]] = field(default_factory=list)
    overall_conversion_rate: float = 0.0
    params: dict[str, Any] = field(default_factory=dict)
    meta: dict[str, Any] = field(default_factory=dict)
    """Response metadata. Conforms to :class:`QueryMeta`."""
    mode: Literal["sankey", "paths", "tree"] = "sankey"
    trees: list[FlowTreeNode] = field(default_factory=list)
    _nodes_df_cache: pd.DataFrame | None = field(default=None, repr=False, kw_only=True)
    _edges_df_cache: pd.DataFrame | None = field(default=None, repr=False, kw_only=True)
    _graph_cache: nx.DiGraph[str] | None = field(default=None, repr=False, kw_only=True)
    """Internal cache for networkx graph (optional dependency)."""
    _trees_df_cache: pd.DataFrame | None = field(default=None, repr=False, kw_only=True)
    _anytree_cache: list[object] | None = field(default=None, repr=False, kw_only=True)
    """Internal cache for anytree nodes (optional dependency)."""

    @property
    def nodes_df(self) -> pd.DataFrame:
        """Extract a flat DataFrame of nodes from sankey step data.

        Each row represents a single node in the flow graph, with columns
        for step index, event name, node type, count, anchor type,
        custom event flag, and conversion rate change.

        The ``totalCount`` field in the API response is a string and is
        parsed to ``int`` here.

        Returns:
            DataFrame with columns: ``step``, ``event``, ``type``,
            ``count``, ``anchor_type``, ``is_custom_event``,
            ``conversion_rate_change``. Returns an empty DataFrame with
            the correct columns when ``steps`` is empty.

        Example:
            ```python
            result = workspace.query_flow(steps=[FlowStep("Login")])
            result.nodes_df
            #    step   event   type  count anchor_type  ...
            # 0     0   Login  ANCHOR   100      NORMAL  ...
            ```
        """
        if self._nodes_df_cache is not None:
            return self._nodes_df_cache
        rows: list[dict[str, Any]] = []
        for step_idx, step in enumerate(self.steps):
            for node in step.get("nodes", []):
                rows.append(
                    {
                        "step": step_idx,
                        "event": node.get("event", ""),
                        "type": node.get("type", ""),
                        "count": _safe_int(node.get("totalCount", "0")),
                        "anchor_type": node.get("anchorType", ""),
                        "is_custom_event": node.get("isCustomEvent", False),
                        "conversion_rate_change": node.get("conversionRateChange", 0.0),
                    }
                )
        cols = [
            "step",
            "event",
            "type",
            "count",
            "anchor_type",
            "is_custom_event",
            "conversion_rate_change",
        ]
        result_df = pd.DataFrame(rows, columns=cols)
        object.__setattr__(self, "_nodes_df_cache", result_df)
        return result_df

    @property
    def edges_df(self) -> pd.DataFrame:
        """Extract a flat DataFrame of edges from sankey step data.

        Each row represents a directed edge between two nodes in the flow
        graph, with columns for source step/event, target step/event,
        edge count, and target node type.

        The ``totalCount`` field in the API response is a string and is
        parsed to ``int`` here.

        Returns:
            DataFrame with columns: ``source_step``, ``source_event``,
            ``target_step``, ``target_event``, ``count``, ``target_type``.
            Returns an empty DataFrame with the correct columns when
            ``steps`` is empty.

        Example:
            ```python
            result = workspace.query_flow(steps=[FlowStep("Login")])
            result.edges_df
            #    source_step source_event  target_step target_event  count target_type
            # 0            0        Login            1       Search     80      NORMAL
            ```
        """
        if self._edges_df_cache is not None:
            return self._edges_df_cache
        rows: list[dict[str, Any]] = []
        for step_idx, step in enumerate(self.steps):
            for node in step.get("nodes", []):
                for edge in node.get("edges", []):
                    rows.append(
                        {
                            "source_step": step_idx,
                            "source_event": node.get("event", ""),
                            "target_step": _safe_int(
                                edge.get("step", step_idx + 1), default=step_idx + 1
                            ),
                            "target_event": edge.get("event", ""),
                            "count": _safe_int(edge.get("totalCount", "0")),
                            "target_type": edge.get("type", ""),
                        }
                    )
        cols = [
            "source_step",
            "source_event",
            "target_step",
            "target_event",
            "count",
            "target_type",
        ]
        result_df = pd.DataFrame(rows, columns=cols)
        object.__setattr__(self, "_edges_df_cache", result_df)
        return result_df

    @property
    def graph(self) -> nx.DiGraph:
        """Build a networkx directed graph from sankey step data.

        Nodes are keyed as ``"{event}@{step}"`` to distinguish the same
        event appearing at different steps (e.g. ``"Login@0"`` vs
        ``"Login@2"``). Each node carries ``step``, ``event``, ``type``,
        ``count``, and ``anchor_type`` attributes. Each edge carries
        ``count`` and ``type`` attributes.

        The graph is lazily constructed on first access and cached for
        subsequent calls.

        Returns:
            A ``networkx.DiGraph`` representing the flow. Returns an
            empty graph when ``steps`` is empty.

        Example:
            ```python
            result = workspace.query_flow(steps=[FlowStep("Login")])
            G = result.graph
            G.nodes["Login@0"]["count"]
            # 100
            ```
        """
        import networkx as nx  # lazy — only paid when graph is accessed

        if self._graph_cache is not None:
            return self._graph_cache
        graph: nx.DiGraph = nx.DiGraph()
        for step_idx, step in enumerate(self.steps):
            for node in step.get("nodes", []):
                node_id = f"{node.get('event', '')}@{step_idx}"
                graph.add_node(
                    node_id,
                    step=step_idx,
                    event=node.get("event", ""),
                    type=node.get("type", ""),
                    count=_safe_int(node.get("totalCount", "0")),
                    anchor_type=node.get("anchorType", ""),
                )
                for edge in node.get("edges", []):
                    target_step = _safe_int(
                        edge.get("step", step_idx + 1), default=step_idx + 1
                    )
                    target_id = f"{edge.get('event', '')}@{target_step}"
                    graph.add_edge(
                        node_id,
                        target_id,
                        count=_safe_int(edge.get("totalCount", "0")),
                        type=edge.get("type", ""),
                    )
        object.__setattr__(self, "_graph_cache", graph)
        return graph

    @property
    def df(self) -> pd.DataFrame:
        """Mode-aware DataFrame from flow data.

        For ``sankey`` mode, returns the same DataFrame as ``nodes_df``
        (one row per node with step, event, type, count, etc.).

        For ``paths`` mode, returns a tabular DataFrame with one row per
        step in each flow path, including ``path_index``, ``step``,
        ``event``, ``type``, and ``count`` columns.

        Returns:
            DataFrame built from nodes (sankey) or flow paths (paths).
            Returns an empty DataFrame if no data is available.

        Example:
            ```python
            result = workspace.query_flow(
                steps=[FlowStep("Login")], mode="sankey"
            )
            result.df.columns
            # Index(['step', 'event', 'type', 'count', ...])
            ```
        """
        if self.mode == "sankey":
            return self.nodes_df
        if self.mode == "tree":
            return self._build_tree_df()
        # paths mode
        if self._df_cache is not None:
            return self._df_cache
        rows: list[dict[str, Any]] = []
        for path_idx, flow in enumerate(self.flows):
            for step_idx, fs in enumerate(flow.get("flowSteps", [])):
                rows.append(
                    {
                        "path_index": path_idx,
                        "step": step_idx,
                        "event": fs.get("event", ""),
                        "type": fs.get("type", ""),
                        "count": _safe_int(fs.get("totalCount", "0")),
                    }
                )
        cols = ["path_index", "step", "event", "type", "count"]
        result_df = pd.DataFrame(rows, columns=cols)
        object.__setattr__(self, "_df_cache", result_df)
        return result_df

    def _build_tree_df(self) -> pd.DataFrame:
        """Flatten tree data into a DataFrame for tree mode.

        Each row represents a single node in the tree, with a ``path``
        column showing the full event chain from root to that node
        (e.g., ``"Login > Search > Purchase"``).

        Returns:
            DataFrame with columns: ``tree_index``, ``depth``, ``path``,
            ``event``, ``type``, ``step_number``, ``total_count``,
            ``drop_off_count``, ``converted_count``. Returns an empty
            DataFrame with correct columns when ``trees`` is empty.
        """
        if self._trees_df_cache is not None:
            return self._trees_df_cache
        cols = [
            "tree_index",
            "depth",
            "path",
            "event",
            "type",
            "step_number",
            "total_count",
            "drop_off_count",
            "converted_count",
        ]
        rows: list[dict[str, Any]] = []
        for tree_idx, tree in enumerate(self.trees):
            self._flatten_tree_node(tree, tree_idx, [], rows)
        result_df = pd.DataFrame(rows, columns=cols)
        object.__setattr__(self, "_trees_df_cache", result_df)
        return result_df

    @staticmethod
    def _flatten_tree_node(
        node: FlowTreeNode,
        tree_index: int,
        ancestors: list[str],
        rows: list[dict[str, Any]],
    ) -> None:
        """Recursively flatten a FlowTreeNode into DataFrame rows.

        Args:
            node: The current tree node to flatten.
            tree_index: Index of the tree this node belongs to.
            ancestors: List of ancestor event names for path building.
            rows: Accumulator list for row dicts (mutated in place).
        """
        path_parts = [*ancestors, node.event]
        rows.append(
            {
                "tree_index": tree_index,
                "depth": len(ancestors),
                "path": " > ".join(path_parts),
                "event": node.event,
                "type": node.type,
                "step_number": node.step_number,
                "total_count": node.total_count,
                "drop_off_count": node.drop_off_count,
                "converted_count": node.converted_count,
            }
        )
        for child in node.children:
            FlowQueryResult._flatten_tree_node(child, tree_index, path_parts, rows)

    def top_transitions(self, n: int = 10) -> list[tuple[str, str, int]]:
        """Return the N highest-traffic transitions between events.

        Uses the edges DataFrame to find the most common transitions,
        sorted by count descending.

        Args:
            n: Maximum number of transitions to return. Default: 10.

        Returns:
            List of (source_node, target_node, count) tuples sorted
            by count descending, where each node is formatted as
            ``"{event}@{step}"`` (e.g. ``"Login@0"``). Returns empty
            list if no edges exist.

        Example:
            ```python
            result = ws.query_flow("Login", forward=3)
            for src, tgt, count in result.top_transitions(n=5):
                print(f"{src} -> {tgt}: {count}")
            # Login@0 -> Search@1: 150
            ```
        """
        edf = self.edges_df
        if edf.empty:
            return []
        sorted_df = edf.sort_values("count", ascending=False).head(n)
        return [
            (f"{se}@{ss}", f"{te}@{ts}", int(c))
            for se, ss, te, ts, c in zip(
                sorted_df["source_event"],
                sorted_df["source_step"],
                sorted_df["target_event"],
                sorted_df["target_step"],
                sorted_df["count"],
                strict=True,
            )
        ]

    def drop_off_summary(self) -> dict[str, Any]:
        """Per-step drop-off counts and rates.

        Analyzes each step to identify drop-off nodes (type == "DROPOFF")
        and calculates the drop-off rate relative to total traffic at
        that step.

        Returns:
            Dict mapping step keys (e.g., "step_0") to dicts with:
            - total: Total count at that step
            - dropoff: Count of users who dropped off
            - rate: Drop-off rate (0.0 to 1.0)
            Returns empty dict if no steps exist.

        Example:
            ```python
            result = ws.query_flow("Login", forward=3)
            for step, info in result.drop_off_summary().items():
                print(f"{step}: {info['rate']:.0%} drop-off")
            ```
        """
        if not self.steps:
            return {}
        summary: dict[str, Any] = {}
        for step_idx, step in enumerate(self.steps):
            total = 0
            dropoff = 0
            for node in step.get("nodes", []):
                count = _safe_int(node.get("totalCount", "0"))
                node_type = node.get("type", "")
                total += count
                # Count dropoff edges only from non-DROPOFF nodes.
                # DROPOFF nodes represent prior-step dropoffs carried
                # forward; their self-edges would double-count.
                if node_type != "DROPOFF":
                    for edge in node.get("edges", []):
                        if edge.get("type") == "DROPOFF":
                            dropoff += _safe_int(edge.get("totalCount", "0"))
            rate = dropoff / total if total > 0 else 0.0
            summary[f"step_{step_idx}"] = {
                "total": total,
                "dropoff": dropoff,
                "rate": rate,
            }
        return summary

    def to_dict(self) -> dict[str, Any]:
        """Serialize the flow query result for JSON output.

        Returns:
            Dictionary with all FlowQueryResult fields suitable for
            JSON serialization.
        """
        return {
            "computed_at": self.computed_at,
            "steps": self.steps,
            "flows": self.flows,
            "breakdowns": self.breakdowns,
            "overall_conversion_rate": self.overall_conversion_rate,
            "params": self.params,
            "meta": self.meta,
            "mode": self.mode,
            "trees": [t.to_dict() for t in self.trees],
        }

    @property
    def anytree(self) -> list[Any]:
        """Lazily-cached list of ``anytree.AnyNode`` roots from tree data.

        Each ``FlowTreeNode`` in ``trees`` is converted to an anytree
        node tree via ``to_anytree()``, enabling parent references,
        path resolution, and ``RenderTree`` display.

        Returns:
            List of ``anytree.AnyNode`` root nodes. Empty list when
            ``trees`` is empty.

        Example:
            ```python
            result = ws.query_flow("Login", mode="tree")
            for root in result.anytree:
                from anytree import RenderTree
                print(RenderTree(root))
            ```
        """
        if self._anytree_cache is not None:
            return self._anytree_cache
        roots = [t.to_anytree() for t in self.trees]
        object.__setattr__(self, "_anytree_cache", roots)
        return roots


# =============================================================================
# User / Engage Query Result (Phase 039)
# =============================================================================


@dataclass(frozen=True)
class UserQueryResult(ResultWithDataFrame):
    """Structured output from a Workspace.query_user() execution.

    Contains profile query results with lazy DataFrame conversion.
    Supports two output modes:

    - **profiles**: Returns individual user profiles with their properties.
    - **aggregate**: Returns aggregate statistics (counts, sums, etc.)
      optionally segmented by cohort.

    Attributes:
        computed_at: When the query was computed (ISO format).
        total: Number of profiles in this result (equals ``len(profiles)``).
        profiles: Normalized profile dicts; empty list for aggregate mode.
        params: Engage API params used for the query (for debugging).
        meta: Execution metadata (timing, sampling, etc.).
        mode: Output mode — ``"profiles"`` or ``"aggregate"``.
        aggregate_data: Raw aggregate result; ``None`` for profiles mode.
            For unsegmented aggregates this is an ``int`` or ``float``.
            For segmented aggregates this is a ``dict[str, Any]``.

    Example:
        ```python
        # Profiles mode
        result = ws.query_user(
            where='properties["plan"] == "premium"',
            properties=["$email", "$last_seen"],
        )
        print(result.total)          # 1532
        print(result.df.head())      # DataFrame with distinct_id, last_seen, email
        print(result.distinct_ids)   # ["abc123", "def456", ...]

        # Aggregate mode
        result = ws.query_user(
            where='properties["plan"] == "premium"',
            mode="aggregate",
        )
        print(result.value)          # 1532
        ```
    """

    computed_at: str
    """When the query was computed (ISO format)."""

    total: int
    """Number of profiles returned in this response.

    Equals ``len(self.profiles)`` in profile mode. For non-count
    aggregates (extremes, percentile, numeric_summary), total is 0
    because the API returns the aggregate value, not a profile count.
    Use ``mode='aggregate', aggregate='count'`` for the full population
    count.
    """

    profiles: list[dict[str, Any]] = field(default_factory=list)
    """Normalized profile dicts; empty list for aggregate mode."""

    params: dict[str, Any] = field(default_factory=dict)
    """Engage API params used for the query (for debugging)."""

    meta: dict[str, Any] = field(default_factory=dict)
    """Execution metadata (pagination, parallelism, or aggregation details)."""

    mode: Literal["profiles", "aggregate"] = "aggregate"
    """Output mode — ``"profiles"`` or ``"aggregate"``."""

    aggregate_data: dict[str, Any] | int | float | None = None
    """Raw aggregate result; ``None`` for profiles mode.

    For unsegmented aggregates this is an ``int`` or ``float``.
    For segmented aggregates this is a ``dict[str, Any]``.
    """

    @property
    def df(self) -> pd.DataFrame:
        """Convert result to a normalized DataFrame.

        The DataFrame structure depends on the query mode:

        - **profiles mode**: One row per profile. Columns are ``distinct_id``
          (first), ``last_seen`` (second), then remaining property columns in
          alphabetical order. Built-in Mixpanel properties have their ``$``
          prefix stripped (e.g., ``$email`` becomes ``email``). Missing
          properties across profiles become ``NaN``.
        - **aggregate unsegmented scalar** (``count()``): Single row with
          columns ``metric`` and ``value``.
        - **aggregate unsegmented structured** (``extremes``,
          ``percentile``, ``numeric_summary``): Single row with ``metric``
          column plus one column per result key (e.g., ``max``, ``min``).
        - **aggregate segmented scalar**: Rows with ``segment`` and
          ``value`` columns.
        - **aggregate segmented structured**: Rows with ``segment``
          column plus one column per result key.

        Returns:
            Normalized DataFrame. For empty profiles, returns an empty
            DataFrame with columns ``["distinct_id", "last_seen"]``.

        Example:
            ```python
            result = ws.query_user(
                where='properties["plan"] == "premium"',
                properties=["$email", "$city"],
            )
            df = result.df
            # columns: distinct_id, last_seen, city, email
            ```
        """
        if self._df_cache is not None:
            return self._df_cache

        if self.mode == "profiles":
            result_df = self._build_profiles_df()
        elif isinstance(self.aggregate_data, dict):
            if self.meta.get("segmented"):
                # Segmented aggregate — one row per cohort
                rows: list[dict[str, Any]] = []
                for seg, val in self.aggregate_data.items():
                    if isinstance(val, dict):
                        rows.append({"segment": seg, **val})
                    else:
                        rows.append({"segment": seg, "value": val})
                if rows:
                    result_df = pd.DataFrame(rows)
                else:
                    result_df = pd.DataFrame(columns=["segment", "value"])
            else:
                # Unsegmented structured result (extremes, percentile,
                # numeric_summary) — single row with metric + dict keys
                action = self.params.get("action", "aggregate")
                result_df = pd.DataFrame(
                    [{"metric": action, **self.aggregate_data}],
                )
        elif self.aggregate_data is not None:
            result_df = pd.DataFrame(
                [
                    {
                        "metric": self.params.get("action", "aggregate"),
                        "value": self.aggregate_data,
                    }
                ],
                columns=["metric", "value"],
            )
        else:
            result_df = pd.DataFrame(columns=["metric", "value"])

        object.__setattr__(self, "_df_cache", result_df)
        return result_df

    def _build_profiles_df(self) -> pd.DataFrame:
        """Build a DataFrame from profile dicts with normalized columns.

        Strips the ``$`` prefix from built-in Mixpanel property names,
        places ``distinct_id`` first and ``last_seen`` second, then
        sorts remaining columns alphabetically.

        Returns:
            DataFrame with one row per profile. Empty DataFrame with
            columns ``["distinct_id", "last_seen"]`` when no profiles.
        """
        if not self.profiles:
            return pd.DataFrame(columns=["distinct_id", "last_seen"])

        normalized: list[dict[str, Any]] = []
        for profile in self.profiles:
            row: dict[str, Any] = {
                "distinct_id": profile.get("distinct_id", ""),
                "last_seen": profile.get("last_seen"),
            }
            # Flatten properties dict, stripping $ prefix from keys
            props = profile.get("properties", {})
            if isinstance(props, dict):
                for key, val in props.items():
                    clean_key = key[1:] if key.startswith("$") else key
                    row[clean_key] = val
            normalized.append(row)

        result_df = pd.DataFrame(normalized)

        # Reorder: distinct_id first, last_seen second, rest alphabetical
        cols = list(result_df.columns)
        priority = ["distinct_id", "last_seen"]
        ordered: list[str] = [c for c in priority if c in cols]
        remaining = sorted(c for c in cols if c not in priority)
        ordered.extend(remaining)
        return pd.DataFrame(result_df[ordered])

    @property
    def distinct_ids(self) -> list[str]:
        """Return distinct IDs from profile results.

        Returns:
            List of ``distinct_id`` strings from each profile dict for
            profiles mode. Empty list for aggregate mode.

        Example:
            ```python
            result = ws.query_user(
                where='properties["plan"] == "premium"',
            )
            ids = result.distinct_ids
            # ["user_abc123", "user_def456", ...]
            ```
        """
        if self.mode != "profiles":
            return []
        return [p.get("distinct_id", "") for p in self.profiles]

    @property
    def value(self) -> int | float | None:
        """Return the scalar aggregate value for unsegmented aggregates.

        Returns:
            The aggregate scalar (``int`` or ``float``) when mode is
            ``"aggregate"`` and ``aggregate_data`` is not a dict.
            Returns ``None`` for profiles mode or segmented aggregates
            (where ``aggregate_data`` is a dict).

        Example:
            ```python
            result = ws.query_user(
                where='properties["plan"] == "premium"',
                mode="aggregate",
            )
            print(result.value)  # 1532
            ```
        """
        if self.mode != "aggregate":
            return None
        if isinstance(self.aggregate_data, dict):
            return None
        if isinstance(self.aggregate_data, (int, float)):
            return self.aggregate_data
        return None

    def to_dict(self) -> dict[str, Any]:
        """Serialize for JSON output.

        Returns all fields except the internal ``_df_cache``.

        Returns:
            Dictionary with keys: ``computed_at``, ``total``,
            ``profiles``, ``params``, ``meta``, ``mode``,
            ``aggregate_data``.

        Example:
            ```python
            result = ws.query_user(
                where='properties["plan"] == "premium"',
            )
            import json
            print(json.dumps(result.to_dict(), indent=2))
            ```
        """
        return {
            "computed_at": self.computed_at,
            "total": self.total,
            "profiles": self.profiles,
            "params": self.params,
            "meta": self.meta,
            "mode": self.mode,
            "aggregate_data": self.aggregate_data,
        }


# =============================================================================
# Business Context
# =============================================================================
# Markdown documentation that grounds AI assistants in an organization's
# structure and goals. Two scopes — "organization" (shared across all projects)
# and "project" (per-project). Stored as plain markdown text (no images,
# structured data, or links). The 50,000-character cap is enforced both
# server-side and client-side.


BUSINESS_CONTEXT_MAX_CHARS: int = 50_000
"""Maximum allowed content length for business context, in characters.

Mirrors the server's ``MAX_CONTENT_LENGTH`` constant — the API returns
HTTP 400 with ``"content exceeds maximum length of 50000 characters"``
above this threshold."""


class BusinessContext(BaseModel):
    """Business context content at a single scope.

    Returned by ``Workspace.get_business_context()`` and
    ``Workspace.set_business_context()``. The ``organization_id`` field
    is populated for ``level="organization"`` and ``project_id`` for
    ``level="project"`` so callers can identify which scope a value
    came from when handling both in the same code path.

    Attributes:
        level: ``"organization"`` (org-wide) or ``"project"``
            (project-specific).
        content: The markdown content. Empty string when no context is
            set at this scope.
        organization_id: Owning organization ID — populated when
            ``level="organization"``, ``None`` otherwise.
        project_id: Owning project ID — populated when ``level="project"``,
            ``None`` otherwise.
        is_empty: Computed — ``True`` when ``content == ""``. Visible
            in ``model_dump()`` output so JSON consumers can use it
            directly (no need to recompute).
        character_count: Computed — ``len(content)``. Visible in
            ``model_dump()`` output. Compare against
            ``BUSINESS_CONTEXT_MAX_CHARS`` (50,000) to check headroom.

    Example:
        ```python
        ws = Workspace()
        ctx = ws.get_business_context(level="project")
        if not ctx.is_empty:
            print(ctx.content[:200], "...")
            print(f"({ctx.character_count} characters)")
        ```
    """

    model_config = ConfigDict(frozen=True, extra="allow")

    level: Literal["organization", "project"]
    """Which scope this context belongs to."""

    content: str
    """Markdown content. Empty string when no context is set."""

    organization_id: int | None = None
    """Owning organization ID (set when ``level="organization"``)."""

    project_id: str | None = None
    """Owning project ID (set when ``level="project"``)."""

    @computed_field  # type: ignore[prop-decorator]
    @property
    def is_empty(self) -> bool:
        """``True`` when no content has been set at this scope.

        Computed field — appears in ``model_dump()`` so JSON / CLI
        consumers can ``--jq '.is_empty'`` directly.

        Returns:
            ``True`` if ``content`` is the empty string, ``False`` otherwise.
        """
        return not self.content

    @computed_field  # type: ignore[prop-decorator]
    @property
    def character_count(self) -> int:
        """Length of ``content`` in characters.

        Computed field — appears in ``model_dump()`` so JSON / CLI
        consumers can ``--jq '.character_count'`` directly.

        Returns:
            Number of Unicode characters in ``content``. Compare against
            ``BUSINESS_CONTEXT_MAX_CHARS`` (50,000) to check headroom.
        """
        return len(self.content)


class BusinessContextChain(BaseModel):
    """Both organization and project business context returned together.

    Returned by ``Workspace.get_business_context_chain()``, which calls
    the project-scoped ``/business-context/chain`` endpoint and resolves
    both scopes in a single round-trip.

    Attributes:
        organization: Organization-level context (shared across projects).
        project: Project-level context (specific to the active project).

    Example:
        ```python
        ws = Workspace()
        chain = ws.get_business_context_chain()
        print("ORG:", chain.organization.content)
        print("PROJECT:", chain.project.content)
        ```
    """

    model_config = ConfigDict(frozen=True)

    organization: BusinessContext
    """Organization-level context (``level="organization"``)."""

    project: BusinessContext
    """Project-level context (``level="project"``)."""


# =============================================================================
# Auth Architecture Redesign Types (Phase 042)
# =============================================================================
# Read-only summary types for the redesigned auth subsystem. These are the
# user-facing shapes returned by `mp.accounts.list()`, `mp.targets.list()`,
# `mp.accounts.test()`, and `mp.accounts.login()`. The underlying frozen
# Account / Project / WorkspaceRef / Session models live in
# src/mixpanel_headless/_internal/auth/.


# ``AccountType`` and ``Region`` are imported above from ``auth_types`` —
# the canonical source of truth. The legacy ``_AccountTypeLiteral`` /
# ``_RegionLiteral`` mirrors that lived here are gone (B3 / Fix 27).


class AccountSummary(BaseModel):
    """Read-only summary of a configured account for ``mp account list``.

    Fields are derived from the persisted ``[accounts.NAME]`` block plus
    runtime context (``is_active``, ``referenced_by_targets``). Status
    reflects the most recent ``mp account test`` outcome — ``"untested"``
    is the default for accounts that have never been tested in this session.

    Example:
        ```python
        summary = AccountSummary(
            name="team", type="service_account", region="us",
            status="ok", is_active=True,
        )
        ```
    """

    model_config = ConfigDict(frozen=True)

    name: str
    """Local config name (matches the TOML block key)."""

    type: AccountType
    """Discriminator value of the underlying ``Account`` variant."""

    region: Region
    """Mixpanel region — ``us``, ``eu``, or ``in``."""

    status: Literal["ok", "needs_login", "needs_token", "untested"] = "untested"
    """Result of the most recent ``mp account test`` (or ``"untested"``)."""

    is_active: bool = False
    """``True`` if ``[active].account == name``."""

    referenced_by_targets: list[str] = Field(default_factory=list)
    """Names of targets that reference this account."""


class MeUserInfo(BaseModel):
    """Subset of the ``/api/app/me`` response identifying the principal.

    The full ``/me`` payload is much larger; this trimmed shape captures
    just the fields callers consistently need to confirm "logged in as
    X" or "user Y has access".
    """

    model_config = ConfigDict(frozen=True, extra="ignore")

    id: int
    """Numeric user ID assigned by Mixpanel."""

    email: str
    """Email address of the authenticated user."""


class AccountTestResult(BaseModel):
    """Outcome of ``mp account test NAME`` — captures the ``/me`` probe.

    Never raises — error context is captured in ``error`` so the CLI can
    print structured failure messages and ``mp account list`` can color
    accounts as ``needs_login`` / ``needs_token`` based on the error code.

    The ``ok``/``error`` fields are paired by an invariant: ``ok=True``
    iff ``error is None``. Constructing the model with both ``ok=True``
    and a non-empty ``error`` (or ``ok=False`` and ``error=None``) raises
    :class:`pydantic.ValidationError` to prevent ambiguous result states
    that would force callers to guess the right field to read.

    When the underlying failure is a :class:`MixpanelHeadlessError`,
    ``error_code`` and ``error_details`` carry the structured fields
    so downstream callers (the plugin's ``auth_manager.py``, JSON
    consumers) can dispatch on the code instead of parsing the
    ``error`` message string. Both default to ``None`` for the
    success path and for failures captured from a non-library
    exception (network OSError, programming bug, etc.).
    """

    model_config = ConfigDict(frozen=True)

    account_name: str
    """Account that was tested."""

    ok: bool
    """``True`` if the ``/me`` request succeeded with valid credentials."""

    user: MeUserInfo | None = None
    """Authenticated principal identity, when ``ok`` is ``True``."""

    accessible_project_count: int | None = None
    """Number of projects the account can read from ``/me``."""

    error: str | None = None
    """Human-readable failure reason when ``ok`` is ``False``."""

    error_code: str | None = None
    """Machine-readable error code (only set when the cause was a ``MixpanelHeadlessError``)."""

    error_details: dict[str, Any] | None = None
    """Structured ``details`` payload from the underlying ``MixpanelHeadlessError``, if any."""

    @model_validator(mode="after")
    def _ok_iff_no_error(self) -> AccountTestResult:
        """Enforce ``ok=True`` ⟺ ``error is None``.

        Returns:
            ``self`` (no mutation).

        Raises:
            ValueError: When ``ok``/``error`` disagree, or when
                ``ok=True`` is paired with a non-None error_code /
                error_details (those fields belong to the failure
                arm only).
        """
        if self.ok and self.error is not None:
            raise ValueError("AccountTestResult: ok=True implies error is None.")
        if not self.ok and self.error is None:
            raise ValueError("AccountTestResult: ok=False requires a non-empty error.")
        if self.ok and (self.error_code is not None or self.error_details is not None):
            raise ValueError(
                "AccountTestResult: error_code/error_details only meaningful "
                "when ok=False."
            )
        return self


class Target(BaseModel):
    """A saved (account, project, workspace?) triple persisted in ``[targets.NAME]``.

    Targets are named cursor positions: ``mp target use prod`` writes all
    three axes to ``[active]`` in a single config save. Workspace is
    optional — when omitted, the target resolves to the project's default
    workspace at use time (per FR-025 lazy resolution).
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: TargetName
    """Local target name (matches the TOML block key)."""

    account: AccountName
    """Local config name of the referenced account (must exist)."""

    project: Annotated[ProjectId, Field(min_length=1, pattern=r"^\d+$")]
    """Numeric project ID (Mixpanel's wire format)."""

    workspace: Annotated[WorkspaceId, Field(gt=0)] | None = None
    """Optional workspace ID (must be a positive integer when set);
    ``None`` defers to lazy resolution. Mirrors ``WorkspaceRef.id``'s
    ``PositiveInt`` constraint so bad values fail at construction rather
    than corrupting downstream config."""


class OAuthLoginResult(BaseModel):
    """Outcome of ``mp.accounts.login(name)`` — captures the PKCE flow result.

    Returned after a successful OAuth browser flow. ``user`` is populated
    from the immediate ``/me`` probe issued after the token exchange so
    callers can confirm "you are now logged in as ``alice@example.com``"
    without needing a follow-up call.
    """

    model_config = ConfigDict(frozen=True, extra="ignore")

    account_name: str
    """Account that was authenticated."""

    user: MeUserInfo | None = None
    """Authenticated principal identity from the post-login ``/me`` probe."""

    expires_at: datetime | None = None
    """Access-token expiry (UTC) from the token endpoint response."""

    tokens_path: Path
    """Where the tokens were persisted (``~/.mp/accounts/{name}/tokens.json``)."""

    client_path: Path
    """Where the DCR client info was persisted (``~/.mp/accounts/{name}/client.json``)."""
