"""Shared Literal type aliases for parameter validation.

These types are exported from the public API and can be used by
library consumers for their own type hints.

Example:
    from mixpanel_headless import TimeUnit, Workspace

    def my_query(ws: Workspace, unit: TimeUnit) -> None:
        result = ws.segmentation(
            "event", from_date="2024-01-01", to_date="2024-01-31", unit=unit
        )
"""

from __future__ import annotations

from typing import Literal

# =============================================================================
# Time Units
# =============================================================================

# Time units for segmentation, retention, event_counts, property_counts, frequency
TimeUnit = Literal["day", "week", "month"]

# Time units for numeric aggregations (segmentation_numeric, sum, average)
HourDayUnit = Literal["hour", "day"]

# Time units for bookmark query API (query, build_params, build_time_section)
QueryTimeUnit = Literal["hour", "day", "week", "month", "quarter"]

# =============================================================================
# Count / Aggregation Types
# =============================================================================

# Count/aggregation methods
CountType = Literal["general", "unique", "average"]

# Counting methods for flows analysis
FlowCountType = Literal["unique", "total", "session"]

# =============================================================================
# Insights Math Types
# =============================================================================

MathType = Literal[
    "total",
    "unique",
    "dau",
    "wau",
    "mau",
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
    "cumulative_unique",
    "sessions",
    "unique_values",
    "most_frequent",
    "first_value",
    "multi_attribution",
    "numeric_summary",
]
"""Aggregation function for query metrics.

+-------------------+------------------------------------------------------------------+--------------------+
| Value             | Meaning                                                          | Requires property? |
+===================+==================================================================+====================+
| total             | Count events, or sum a numeric property if ``property`` is set   | Optional           |
+-------------------+------------------------------------------------------------------+--------------------+
| unique            | Count distinct users                                             | No                 |
+-------------------+------------------------------------------------------------------+--------------------+
| dau               | Daily Active Users (unique users per day)                        | No                 |
+-------------------+------------------------------------------------------------------+--------------------+
| wau               | Weekly Active Users (unique users per 7-day window)              | No                 |
+-------------------+------------------------------------------------------------------+--------------------+
| mau               | Monthly Active Users (unique users per 28-day window)            | No                 |
+-------------------+------------------------------------------------------------------+--------------------+
| average           | Mean of a numeric property's values                              | Yes                |
+-------------------+------------------------------------------------------------------+--------------------+
| median            | Median (50th percentile) of a numeric property                   | Yes                |
+-------------------+------------------------------------------------------------------+--------------------+
| min               | Minimum value of a numeric property                              | Yes                |
+-------------------+------------------------------------------------------------------+--------------------+
| max               | Maximum value of a numeric property                              | Yes                |
+-------------------+------------------------------------------------------------------+--------------------+
| p25               | 25th percentile of a numeric property                            | Yes                |
+-------------------+------------------------------------------------------------------+--------------------+
| p75               | 75th percentile of a numeric property                            | Yes                |
+-------------------+------------------------------------------------------------------+--------------------+
| p90               | 90th percentile of a numeric property                            | Yes                |
+-------------------+------------------------------------------------------------------+--------------------+
| p99               | 99th percentile of a numeric property                            | Yes                |
+-------------------+------------------------------------------------------------------+--------------------+
| percentile        | Custom percentile (requires ``percentile_value``)                | Yes                |
+-------------------+------------------------------------------------------------------+--------------------+
| histogram         | Distribution of a numeric property's values                      | Yes                |
+-------------------+------------------------------------------------------------------+--------------------+
| cumulative_unique | Running count of distinct users over time                        | No                 |
+-------------------+------------------------------------------------------------------+--------------------+
| sessions          | Count sessions (not events or users)                             | No                 |
+-------------------+------------------------------------------------------------------+--------------------+
| unique_values     | Count of distinct values of a property                           | Yes                |
+-------------------+------------------------------------------------------------------+--------------------+
| most_frequent     | Most commonly occurring value of a property                      | Yes                |
+-------------------+------------------------------------------------------------------+--------------------+
| first_value       | First observed value of a property per user                      | Yes                |
+-------------------+------------------------------------------------------------------+--------------------+
| multi_attribution | Multi-touch attribution across a property                        | Yes                |
+-------------------+------------------------------------------------------------------+--------------------+
| numeric_summary   | Summary stats (count, mean, variance) of a property              | Yes                |
+-------------------+------------------------------------------------------------------+--------------------+

Note: Mixpanel has no ``"sum"`` math type. Use ``math="total"`` with
a ``property`` to sum a numeric property's values.

``dau``, ``wau``, ``mau``, and ``unique`` are incompatible with ``per_user``.

``percentile`` maps to ``custom_percentile`` in bookmark JSON and requires
``percentile_value`` on Metric (or as a top-level param on ``query()``/``build_params()``).
``histogram`` maps directly to ``histogram`` in bookmark JSON.
"""

PerUserAggregation = Literal["unique_values", "total", "average", "min", "max"]
"""Per-user pre-aggregation type.

Requires ``math_property`` to be set. The query first computes the
per-user aggregate, then applies the top-level ``math`` across users.

+-----------------+---------------------------------------------------------------+
| Value           | Meaning                                                       |
+=================+===============================================================+
| total           | Sum of the property value per user (then aggregate)           |
+-----------------+---------------------------------------------------------------+
| average         | Mean of the property value per user (then aggregate)          |
+-----------------+---------------------------------------------------------------+
| min             | Minimum property value per user (then aggregate)              |
+-----------------+---------------------------------------------------------------+
| max             | Maximum property value per user (then aggregate)              |
+-----------------+---------------------------------------------------------------+
| unique_values   | Count of distinct property values per user (then aggregate)   |
+-----------------+---------------------------------------------------------------+

Maps to ``perUserAggregation`` in the bookmark measurement block.
"""

# =============================================================================
# Funnel Types
# =============================================================================

FunnelMathType = Literal[
    "conversion_rate_unique",
    "conversion_rate_total",
    "conversion_rate_session",
    "unique",
    "total",
    "average",
    "median",
    "min",
    "max",
    "p25",
    "p75",
    "p90",
    "p99",
    "histogram",
]
"""Aggregation function for funnel query metrics.

+---------------------------+------------------------------------------------------+--------------------+
| Value                     | Meaning                                              | Requires property? |
+===========================+======================================================+====================+
| conversion_rate_unique    | Unique-user conversion rate (default)                | No                 |
+---------------------------+------------------------------------------------------+--------------------+
| conversion_rate_total     | Total-event conversion rate                          | No                 |
+---------------------------+------------------------------------------------------+--------------------+
| conversion_rate_session   | Session-based conversion rate                        | No                 |
+---------------------------+------------------------------------------------------+--------------------+
| unique                    | Raw count of unique users per step                   | No                 |
+---------------------------+------------------------------------------------------+--------------------+
| total                     | Raw total event count per step                       | No                 |
+---------------------------+------------------------------------------------------+--------------------+
| average                   | Mean of a numeric property per step                  | Yes                |
+---------------------------+------------------------------------------------------+--------------------+
| median                    | Median of a numeric property per step                | Yes                |
+---------------------------+------------------------------------------------------+--------------------+
| min                       | Minimum of a numeric property per step               | Yes                |
+---------------------------+------------------------------------------------------+--------------------+
| max                       | Maximum of a numeric property per step               | Yes                |
+---------------------------+------------------------------------------------------+--------------------+
| p25                       | 25th percentile of a numeric property per step       | Yes                |
+---------------------------+------------------------------------------------------+--------------------+
| p75                       | 75th percentile of a numeric property per step       | Yes                |
+---------------------------+------------------------------------------------------+--------------------+
| p90                       | 90th percentile of a numeric property per step       | Yes                |
+---------------------------+------------------------------------------------------+--------------------+
| p99                       | 99th percentile of a numeric property per step       | Yes                |
+---------------------------+------------------------------------------------------+--------------------+
| histogram                 | Distribution of a numeric property per step          | Yes                |
+---------------------------+------------------------------------------------------+--------------------+

These 14 values are the public-facing funnel math types. The Mixpanel API
also accepts internal aliases (``"general"``, ``"session"``,
``"conversion_rate"``) but those are not exposed in the public API.
"""

ConversionWindowUnit = Literal[
    "second", "minute", "hour", "day", "week", "month", "session"
]
"""Time unit for funnel conversion window.

+----------+----------------------------------------------+
| Value    | Meaning                                      |
+==========+==============================================+
| second   | Conversion window in seconds (max 31708800)  |
+----------+----------------------------------------------+
| minute   | Conversion window in minutes (max 528480)    |
+----------+----------------------------------------------+
| hour     | Conversion window in hours (max 8808)        |
+----------+----------------------------------------------+
| day      | Conversion window in days (max 367)          |
+----------+----------------------------------------------+
| week     | Conversion window in weeks (max 52)          |
+----------+----------------------------------------------+
| month    | Conversion window in months (max 12)         |
+----------+----------------------------------------------+
| session  | Conversion window in sessions (max 12)       |
+----------+----------------------------------------------+
"""

FunnelOrder = Literal["loose", "any"]
"""Funnel step ordering mode.

+--------+----------------------------------------------+
| Value  | Meaning                                      |
+========+==============================================+
| loose  | Steps must occur in order but other events   |
|        | may happen between them (default)            |
+--------+----------------------------------------------+
| any    | Steps may occur in any order                 |
+--------+----------------------------------------------+
"""

FunnelMode = Literal["steps", "trends", "table"]
"""Display mode for funnel query results.

+--------+----------------------------------------------+
| Value  | Meaning                                      |
+========+==============================================+
| steps  | Step-by-step conversion view (default)       |
+--------+----------------------------------------------+
| trends | Conversion trend over time                   |
+--------+----------------------------------------------+
| table  | Tabular conversion data                      |
+--------+----------------------------------------------+
"""

# =============================================================================
# Retention Types
# =============================================================================

RetentionAlignment = Literal["birth", "interval_start"]
"""Retention alignment mode.

+------------------+----------------------------------------------+
| Value            | Meaning                                      |
+==================+==============================================+
| birth            | Align to each cohort's born date (default)   |
+------------------+----------------------------------------------+
| interval_start   | Align all cohorts to the same start date     |
+------------------+----------------------------------------------+
"""

RetentionMode = Literal["curve", "trends", "table"]
"""Display mode for retention query results.

+--------+----------------------------------------------+
| Value  | Meaning                                      |
+========+==============================================+
| curve  | Retention curve (default)                    |
+--------+----------------------------------------------+
| trends | Trend lines over time                        |
+--------+----------------------------------------------+
| table  | Tabular cohort x bucket grid                 |
+--------+----------------------------------------------+
"""

RetentionMathType = Literal["retention_rate", "unique", "total", "average"]
"""Aggregation function for retention query metrics.

+----------------+----------------------------------------------+
| Value          | Meaning                                      |
+================+==============================================+
| retention_rate | Percentage of users retained (default)       |
+----------------+----------------------------------------------+
| unique         | Raw count of retained users                  |
+----------------+----------------------------------------------+
| total          | Total event count per retention bucket       |
+----------------+----------------------------------------------+
| average        | Average of a numeric property per bucket     |
+----------------+----------------------------------------------+

Maps directly to the ``measurement.math`` field in bookmark JSON.
"""

# =============================================================================
# Advanced Query Types
# =============================================================================

SegmentMethod = Literal["all", "first"]
"""Method for counting qualifying events in segmentation.

+--------+------------------------------------------------------+
| Value  | Meaning                                              |
+========+======================================================+
| all    | Count all qualifying events (default)                |
+--------+------------------------------------------------------+
| first  | Count only the first qualifying event per user       |
+--------+------------------------------------------------------+
"""

FunnelReentryMode = Literal["default", "basic", "aggressive", "optimized"]
"""Re-entry mode for funnel queries.

+------------+------------------------------------------------------+
| Value      | Meaning                                              |
+============+======================================================+
| default    | Server default behavior                              |
+------------+------------------------------------------------------+
| basic      | Users re-enter at steps after first                  |
+------------+------------------------------------------------------+
| aggressive | Each re-entry generates additional conversion        |
+------------+------------------------------------------------------+
| optimized  | Optimized re-entry counting                          |
+------------+------------------------------------------------------+
"""

RetentionUnboundedMode = Literal[
    "none", "carry_back", "carry_forward", "consecutive_forward"
]
"""Unbounded retention mode for retention queries.

+----------------------+------------------------------------------------------+
| Value                | Meaning                                              |
+======================+======================================================+
| none                 | No unbounded retention (default)                     |
+----------------------+------------------------------------------------------+
| carry_back           | Count users in all prior buckets                     |
+----------------------+------------------------------------------------------+
| carry_forward        | Count users in all subsequent buckets                |
+----------------------+------------------------------------------------------+
| consecutive_forward  | Count users in consecutive subsequent buckets        |
+----------------------+------------------------------------------------------+
"""

TimeComparisonType = Literal["relative", "absolute-start", "absolute-end"]
"""Type of time comparison for query results.

+----------------+------------------------------------------------------+
| Value          | Meaning                                              |
+================+======================================================+
| relative       | Compare against previous period of same length       |
+----------------+------------------------------------------------------+
| absolute-start | Compare against period starting from a specific date |
+----------------+------------------------------------------------------+
| absolute-end   | Compare against period ending at a specific date     |
+----------------+------------------------------------------------------+
"""

TimeComparisonUnit = Literal["day", "week", "month", "quarter", "year"]
"""Time unit for period-over-period comparisons.

+---------+----------------------------------------------+
| Value   | Meaning                                      |
+=========+==============================================+
| day     | Compare against previous day                 |
+---------+----------------------------------------------+
| week    | Compare against previous week                |
+---------+----------------------------------------------+
| month   | Compare against previous month               |
+---------+----------------------------------------------+
| quarter | Compare against previous quarter             |
+---------+----------------------------------------------+
| year    | Compare against previous year                |
+---------+----------------------------------------------+
"""

CohortAggregationType = Literal["total", "unique", "average", "min", "max", "median"]
"""Aggregation type for cohort behavior criteria.

+---------+----------------------------------------------+
| Value   | Meaning                                      |
+=========+==============================================+
| total   | Sum of property values                       |
+---------+----------------------------------------------+
| unique  | Count of distinct property values            |
+---------+----------------------------------------------+
| average | Mean of property values                      |
+---------+----------------------------------------------+
| min     | Minimum property value                       |
+---------+----------------------------------------------+
| max     | Maximum property value                       |
+---------+----------------------------------------------+
| median  | Median property value                        |
+---------+----------------------------------------------+
"""

FlowSessionEvent = Literal["start", "end"]
"""Session anchor event type for flow queries.

+--------+----------------------------------------------+
| Value  | Meaning                                      |
+========+==============================================+
| start  | Session start anchor ($session_start)        |
+--------+----------------------------------------------+
| end    | Session end anchor ($session_end)            |
+--------+----------------------------------------------+
"""

FrequencyFilterOperator = Literal[
    "is at least",
    "is at most",
    "is greater than",
    "is less than",
    "is equal to",
]
"""Comparison operator for frequency filters.

+------------------+----------------------------------------------+
| Value            | Meaning                                      |
+==================+==============================================+
| is at least      | Count >= threshold (default)                 |
+------------------+----------------------------------------------+
| is at most       | Count <= threshold                           |
+------------------+----------------------------------------------+
| is greater than  | Count > threshold                            |
+------------------+----------------------------------------------+
| is less than     | Count < threshold                            |
+------------------+----------------------------------------------+
| is equal to      | Count == threshold                           |
+------------------+----------------------------------------------+

Note: ``"is between"`` is excluded because ``FrequencyFilter.value``
is typed as ``int | float`` (single scalar) and cannot represent
the two-bound range that "between" requires.
"""

# =============================================================================
# Flow Types
# =============================================================================

# Chart types for flows visualization
FlowChartType = Literal["sankey", "paths", "tree"]

FlowConversionWindowUnit = Literal["day", "week", "month", "session"]
"""Time unit for flow conversion window.

Subset of ``ConversionWindowUnit`` — flows do not support
second, minute, or hour granularity.

+----------+----------------------------------------------+
| Value    | Meaning                                      |
+==========+==============================================+
| day      | Conversion window in days (default)          |
+----------+----------------------------------------------+
| week     | Conversion window in weeks                   |
+----------+----------------------------------------------+
| month    | Conversion window in months                  |
+----------+----------------------------------------------+
| session  | Conversion window in sessions                |
+----------+----------------------------------------------+
"""

# Node types in a flow tree response
FlowNodeType = Literal["ANCHOR", "NORMAL", "DROPOFF", "PRUNED", "FORWARD", "REVERSE"]

# Anchor types in a flow tree response
FlowAnchorType = Literal["NORMAL", "RELATIVE_REVERSE", "RELATIVE_FORWARD"]

# =============================================================================
# Insights Display Mode
# =============================================================================

InsightsMode = Literal["timeseries", "total", "table"]
"""Display mode for insights query results.

+------------+----------------------------------------------+
| Value      | Meaning                                      |
+============+==============================================+
| timeseries | Time-series data with date-indexed values     |
|            | (default)                                    |
+------------+----------------------------------------------+
| total      | Single aggregate value per metric             |
+------------+----------------------------------------------+
| table      | Tabular data view                            |
+------------+----------------------------------------------+
"""

# =============================================================================
# Filter Types
# =============================================================================

FilterPropertyType = Literal[
    "string", "number", "boolean", "datetime", "list", "object"
]
"""Property data type for filter conditions.

Includes ``"datetime"`` and ``"list"`` for API compatibility, and
``"object"`` for ``Filter.list_contains`` (filtering on subproperties of
objects nested inside a list-of-objects property). Datetime factory
methods (``Filter.on``, ``Filter.before``, etc.) produce filters with
``filterType="datetime"``.
"""

CustomPropertyType = Literal["string", "number", "boolean", "datetime"]
"""Output type for custom property definitions.

Unlike ``FilterPropertyType``, excludes ``"list"`` which is not valid
for custom property output types. Also reused by ``SubPropertyInfo``
and ``GroupBy.list_item`` since those operate on the same scalar
type space.
"""

FilterOperator = Literal[
    "contains",
    "does not contain",
    "does not equal",
    "ends with",
    "equals",
    "false",
    "is at least",
    "is at most",
    "is between",
    "is greater than",
    "is less than",
    "is not set",
    "is set",
    "list_contains",
    "not between",
    "starts with",
    "true",
    "was before",
    "was between",
    "was in the",
    "was in the next",
    "was not between",
    "was not in the",
    "was not on",
    "was on",
    "was since",
]
"""All recognized values of ``Filter._operator``.

Centralized so additions/removals stay in lockstep with the bookmark
wire format and so mypy catches typos at every Filter classmethod
factory call site.
"""

FilterDateUnit = Literal["hour", "day", "week", "month"]
"""Time unit for relative date filters.

Used by ``Filter.in_the_last()`` and ``Filter.not_in_the_last()``
to specify the granularity of the relative time window.
Maps to ``filterDateUnit`` in bookmark JSON.
"""

FiltersCombinator = Literal["all", "any"]
"""How multiple filters combine.

+-------+----------------------------------------------+
| Value | Meaning                                      |
+=======+==============================================+
| all   | All filters must match (AND logic, default)  |
+-------+----------------------------------------------+
| any   | Any filter may match (OR logic)              |
+-------+----------------------------------------------+
"""

__all__ = [
    # Time units
    "TimeUnit",
    "HourDayUnit",
    "QueryTimeUnit",
    # Count types
    "CountType",
    "FlowCountType",
    # Insights math
    "MathType",
    "PerUserAggregation",
    # Funnel types
    "FunnelMathType",
    "ConversionWindowUnit",
    "FunnelOrder",
    "FunnelMode",
    # Retention types
    "RetentionAlignment",
    "RetentionMode",
    "RetentionMathType",
    # Advanced query types
    "SegmentMethod",
    "FunnelReentryMode",
    "RetentionUnboundedMode",
    "TimeComparisonType",
    "TimeComparisonUnit",
    "CohortAggregationType",
    "FlowSessionEvent",
    "FrequencyFilterOperator",
    # Flow types
    "FlowChartType",
    "FlowConversionWindowUnit",
    "FlowNodeType",
    "FlowAnchorType",
    # Insights mode
    "InsightsMode",
    # Filter types
    "CustomPropertyType",
    "FilterOperator",
    "FilterPropertyType",
    "FilterDateUnit",
    "FiltersCombinator",
]
