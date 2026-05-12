"""Authoritative Mixpanel bookmark enum constants.

All values are sourced from the server-side validation at
``analytics/bookmark_parser/insights/validate.py``,
``analytics/bookmark_parser/common/schema/property_selectors/operator_expr.json``,
and the canonical Pydantic definitions in
``analytics/lib/common/mxpnl/report/bookmarks/{common,insights}/definitions.py``.

These constants define every valid value the Mixpanel insights query API
accepts for each bookmark field. Used by the validation engine to catch
invalid values client-side before they reach the server.

Organized by domain for clarity. Each constant is a ``frozenset[str]``
for O(1) membership checks and immutability.
"""

from __future__ import annotations

# =============================================================================
# Math / Aggregation Types
# =============================================================================

VALID_MATH_TYPES: frozenset[str] = frozenset(
    {
        # Core counting
        "total",
        "unique",
        "cumulative_unique",
        "sessions",
        # Active users
        "dau",
        "wau",
        "mau",
        # Property aggregation
        "average",
        "median",
        "min",
        "max",
        # Percentiles
        "p25",
        "p75",
        "p90",
        "p99",
        "custom_percentile",
        # Advanced
        "histogram",
        "unique_values",
        "most_frequent",
        "first_value",
        "multi_attribution",
        "numeric_summary",
        # Per-user-only aggregation operator (canonical
        # PER_USER_AGGREGATIONS includes this; included in the union here)
        "session_replay_id_value",
        # Legacy / context-specific
        "general",
        "session",
        # Conversion (funnel/retention context)
        "conversion_rate",
        "conversion_rate_unique",
        "conversion_rate_total",
        "conversion_rate_session",
        "retention_rate",
    }
)
"""All valid math/aggregation operators across all contexts (insights, funnels, retention).

Mirrors the canonical ``MATH_TYPE`` union of
``PRIMITIVE_MATH_TYPES``, ``NUMERIC_MATH_TYPES``, ``XAU_MATH_TYPES``,
``PER_USER_AGGREGATIONS``, ``FUNNELS_MATH_TYPES``, ``RETENTION_MATH_TYPES``
in ``analytics/lib/common/mxpnl/report/bookmarks/common/definitions.py``.
"""

VALID_MATH_INSIGHTS: frozenset[str] = frozenset(
    {
        "total",
        "unique",
        "cumulative_unique",
        "sessions",
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
        "custom_percentile",
        "histogram",
        "unique_values",
        "most_frequent",
        "first_value",
        "multi_attribution",
        "numeric_summary",
    }
)
"""Valid math types for insights context (excludes funnel/retention-specific)."""

VALID_MATH_FUNNELS: frozenset[str] = frozenset(
    {
        "general",
        "unique",
        "session",
        "total",
        "conversion_rate",
        "conversion_rate_unique",
        "conversion_rate_total",
        "conversion_rate_session",
        # Property aggregation types (funnel measure on property)
        "average",
        "median",
        "min",
        "max",
        "p25",
        "p75",
        "p90",
        "p99",
        "histogram",
    }
)
"""Valid math types for funnel context.

Includes counting/conversion types and property aggregation types
(average, median, min, max, percentiles) for funnel measure-on-property.
"""

VALID_MATH_RETENTION: frozenset[str] = frozenset(
    {
        "unique",
        "retention_rate",
        "total",
        "average",
    }
)
"""Valid math types for retention context."""

MATH_REQUIRING_PROPERTY: frozenset[str] = frozenset(
    {
        "average",
        "median",
        "min",
        "max",
        "p25",
        "p75",
        "p90",
        "p99",
        "custom_percentile",
        "percentile",
        "histogram",
        # Advanced
        "unique_values",
        "most_frequent",
        "first_value",
        "multi_attribution",
        "numeric_summary",
    }
)
"""Math types that require a measurement property to be specified."""

MATH_PROPERTY_OPTIONAL: frozenset[str] = frozenset({"total"})
"""Math types that optionally accept a property.

``"total"`` without a property counts events; with a property it sums
the property's numeric values.
"""

MATH_NO_PER_USER: frozenset[str] = frozenset({"dau", "wau", "mau", "unique"})
"""Math types incompatible with per-user aggregation."""

# =============================================================================
# Per-User Aggregation
# =============================================================================

VALID_PER_USER_AGGREGATIONS: frozenset[str] = frozenset(
    {
        "average",
        "max",
        "min",
        "session_replay_id_value",
        "total",
        "unique_values",
    }
)
"""Valid per-user aggregation types (maps to ``perUserAggregation`` in bookmark)."""

# =============================================================================
# Property Types
# =============================================================================

VALID_PROPERTY_TYPES: frozenset[str] = frozenset(
    {
        "string",
        "number",
        "datetime",
        "boolean",
        "list",
        "object",
        "undefined",
        # Canonical additions (insights/definitions.py PropertyType)
        "dimension",  # property is a dimension join key
        "other",  # NonProperty
        "unknown",
    }
)
"""Valid property data types for filter and group-by clauses.

Mirrors ``PropertyType`` in
``analytics/lib/common/mxpnl/report/bookmarks/insights/definitions.py``.
``"undefined"`` retained as legacy alias for ``"unknown"`` for back-compat
with older bookmarks.
"""

# =============================================================================
# Time Units
# =============================================================================

VALID_TIME_UNITS: frozenset[str] = frozenset(
    {
        # BaseTimeUnit
        "hour",
        "day",
        "week",
        "month",
        # ExtendedTimeUnit
        "second",
        "minute",
        "quarter",
        "year",
        # NonStandardTimeUnit
        "session",
        # SpecialTimeUnit (canonical TimeUnit union includes these)
        "hour_of_day",
        "day_of_week",
    }
)
"""Valid time units for time section aggregation.

Mirrors ``TimeUnit`` (union of ``BaseTimeUnit``, ``ExtendedTimeUnit``,
``NonStandardTimeUnit``, ``SpecialTimeUnit``) in
``analytics/lib/common/mxpnl/report/bookmarks/common/definitions.py``.
"""

VALID_QUERY_TIME_UNITS: frozenset[str] = frozenset(
    {
        "second",
        "minute",
        "hour",
        "day",
        "week",
        "month",
        "year",
        "quarter",
        "session",
        "day_of_week",
        "hour_of_day",
    }
)
"""Valid time units for query contexts (includes special grouping units)."""

# =============================================================================
# Resource Types
# =============================================================================

VALID_RESOURCE_TYPES: frozenset[str] = frozenset(
    {
        "events",
        "people",
        "cohorts",
        "other",
        # Legacy aliases (still accepted by server)
        "event",
        "user",
        "cohort",
        # Canonical additions (insights/definitions.py InsightsResourceType)
        "all",
        "formulas",
    }
)
"""Valid resource types for filters, groups, and show clauses.

Mirrors ``InsightsResourceType`` in
``analytics/lib/common/mxpnl/report/bookmarks/insights/definitions.py``,
plus legacy singular aliases (``"event"``, ``"user"``, ``"cohort"``)
the server still accepts.
"""

# =============================================================================
# Metric / Behavior Types
# =============================================================================

VALID_METRIC_TYPES: frozenset[str] = frozenset(
    {
        "event",
        "simple",
        "custom-event",
        "cohort",
        "people",
        "funnel",
        "retention",
        "formula",
        # Canonical additions (insights/definitions.py MetricType)
        "retention-frequency",
        "saved-metric",
        "verified",
        # Legacy values still observed in older bookmarks (kept for back-compat)
        "addiction",
        "metric",
    }
)
"""Valid behavior/metric types in show clause behavior blocks.

Mirrors ``MetricType`` in
``analytics/lib/common/mxpnl/report/bookmarks/insights/definitions.py``.
Includes ``"addiction"`` and ``"metric"`` as legacy values that may appear
in older saved bookmarks.
"""

# =============================================================================
# Chart Types
# =============================================================================

VALID_CHART_TYPES: frozenset[str] = frozenset(
    {
        # Insights chart types
        "bar",
        "line",
        "pie",
        "bar-stacked",
        "stacked-line",
        "table",
        "insights-metric",
        "column",
        "stacked-column",
        # Legacy dashboards-only metric (still saved on the backend)
        "metric",
        # Flows chart types
        "sankey",
        "flows",  # alias for sankey
        "paths",
        # Funnel chart types
        "funnel-top-paths",
        "funnel-steps",
        "funnel-steps-metric",
        "funnel-trend",
        "funnel-frequency-line",
        "funnel-frequency-bar",
        "funnel-ttc-line",
        "funnel-ttc-bar",
        "funnel-median-ttc",
        # Retention chart types
        "line-retention",  # deprecated retention curve
        "retention-trend",
        "retention-trend-metric",
        "retention-table",  # AKA retention curve
        "retention-curve",
        "frequency",
        # Impact chart types
        "impact-adoption",
        "impact-trends",
        "impact-propensity",
        # Legacy local additions (kept for back-compat with older bookmarks)
        "frequency-curve",
    }
)
"""Valid chart types for displayOptions.chartType.

Mirrors ``ChartType`` in
``analytics/lib/common/mxpnl/report/bookmarks/common/definitions.py``,
plus ``"frequency-curve"`` retained as a legacy local addition for
back-compat.
"""

# =============================================================================
# Filter Operators
# =============================================================================

VALID_FILTER_OPERATORS: frozenset[str] = frozenset(
    {
        # String operators
        "contains",
        "does not contain",
        "equals",
        "does not equal",
        "is equal to",
        "starts with",
        "ends with",
        # Existence operators
        "is set",
        "is not set",
        # Numeric comparison operators
        "is at least",
        "is at most",
        "is between",
        "between",
        "not between",
        "is greater than",
        "is less than",
        "is greater than or equal to",
        "is less than or equal to",
        # Boolean operators
        "true",
        "false",
        # Date operators (legacy segfilter format — DateRangeType)
        "on",
        "not on",
        "in the last",
        "not in the last",
        "before the last",
        "before",
        "in the next",
        "since",
        # Date operators (canonical bookmark sections — InsightsDateRangeType)
        "was on",
        "was not on",
        "was in the",
        "was not in the",
        "was between",
        "was not between",
        "was less than",
        "was before",
        "was since",
        "was in the next",
    }
)
"""Valid filter operators from the canonical operator expression schema.

Includes both legacy ``DateRangeType`` operators (``"on"``, ``"in the last"``,
etc.) and canonical ``InsightsDateRangeType`` operators (``"was on"``,
``"was in the"``, etc.).  The ``InsightsDateRangeType`` form is what the
Mixpanel webapp writes into bookmark ``sections.filter[]`` entries; the
legacy form appears in old v2 bookmarks and segfilter-based params.  Both
are accepted by the Mixpanel API.

Reference: ``analytics/bookmark_parser/common/segfilter/
segfilter_to_property_filter.py`` — ``InsightsDateRangeType`` class.
"""

# =============================================================================
# Filters Determiner
# =============================================================================

VALID_FILTERS_DETERMINER: frozenset[str] = frozenset({"any", "all"})
"""Valid values for filtersDeterminer (AND/OR logic for multiple filters)."""

# =============================================================================
# Analysis Types
# =============================================================================

VALID_ANALYSIS_TYPES: frozenset[str] = frozenset(
    {
        "linear",
        "logarithmic",
        "rolling",
        "cumulative",
    }
)
"""Valid analysis types for displayOptions."""

# =============================================================================
# Date Range Types
# =============================================================================

VALID_DATE_RANGE_TYPES: frozenset[str] = frozenset(
    {
        "in the last",
        "between",
        "since",
        "on",
        "relative_after",
    }
)
"""Valid date range types for time section clauses."""

# =============================================================================
# Funnel-Specific Constants
# =============================================================================

VALID_FUNNEL_ORDER: frozenset[str] = frozenset({"loose", "any"})
"""Valid funnel step ordering modes.

``"loose"`` requires steps in order but allows other events between.
``"any"`` allows steps in any order.
"""

VALID_CONVERSION_WINDOW_UNITS: frozenset[str] = frozenset(
    {
        "second",
        "minute",
        "hour",
        "day",
        "week",
        "month",
        "session",
    }
)
"""Valid time units for funnel conversion window."""

MAX_CONVERSION_WINDOW: dict[str, int] = {
    "month": 12,
    "session": 12,
    "week": 52,
    "day": 367,
    "hour": 8808,
    "minute": 528480,
    "second": 31708800,
}
"""Maximum conversion window duration per unit.

Sourced from ``analytics/api/version_2_0/arb_funnels/validate.py``
``_MAX_LENGTHS`` dict. All values correspond to approximately 366 days.
"""

_MAX_FUNNEL_STEPS = 100
"""Maximum number of steps allowed in a funnel query."""

_MAX_HOLDING_CONSTANT = 3
"""Maximum number of holding-constant properties allowed."""

# =============================================================================
# Retention-Specific Constants
# =============================================================================

VALID_RETENTION_UNITS: frozenset[str] = frozenset({"day", "week", "month"})
"""Valid time units for retention period grouping."""

VALID_RETENTION_ALIGNMENT: frozenset[str] = frozenset({"birth", "interval_start"})
"""Valid retention alignment modes.

``"birth"`` aligns each user to their first qualifying event.
``"interval_start"`` aligns to the start of each calendar period.
"""

# =============================================================================
# Flows-Specific Constants
# =============================================================================

VALID_FLOWS_COUNT_TYPES: frozenset[str] = frozenset({"unique", "total", "session"})
"""Valid counting methods for flows analysis."""

VALID_FLOWS_CHART_TYPES: frozenset[str] = frozenset({"sankey", "top-paths", "tree"})
"""Valid chart types for flows visualization."""

VALID_FLOWS_MODES: frozenset[str] = frozenset({"sankey", "paths", "tree"})
"""Valid user-facing mode values for flow queries.

Maps to chart types internally: ``"sankey"`` → ``"sankey"``,
``"paths"`` → ``"top-paths"`` (API uses ``"top-paths"``).
"""

VALID_FLOWS_CONVERSION_WINDOW_UNITS: frozenset[str] = frozenset(
    {"day", "week", "month", "session"}
)
"""Valid time units for flows conversion window.

Includes ``"session"`` for session-based counting
(requires ``count_type="session"`` and ``conversion_window=1``).
"""

# =============================================================================
# Advanced Query Mode Constants
# =============================================================================

VALID_FUNNEL_REENTRY_MODES: frozenset[str] = frozenset(
    {"default", "basic", "aggressive", "optimized"}
)
"""Valid funnel reentry modes for behavior.funnelReentryMode."""

VALID_RETENTION_UNBOUNDED_MODES: frozenset[str] = frozenset(
    {"none", "carry_back", "carry_forward", "consecutive_forward"}
)
"""Valid retention unbounded modes for behavior.retentionUnboundedMode."""

VALID_SEGMENT_METHODS: frozenset[str] = frozenset({"all", "first"})
"""Valid segment method values for measurement.segmentMethod."""

VALID_TIME_COMPARISON_TYPES: frozenset[str] = frozenset(
    {"relative", "absolute-start", "absolute-end"}
)
"""Valid time comparison type values for displayOptions.timeComparison."""

VALID_TIME_COMPARISON_UNITS: frozenset[str] = frozenset(
    {"day", "week", "month", "quarter", "year"}
)
"""Valid time comparison unit values for relative time comparisons."""

VALID_COHORT_AGGREGATION_OPERATORS: frozenset[str] = frozenset(
    {"total", "unique", "average", "min", "max", "median"}
)
"""Valid cohort aggregation operators for behavioral cohort conditions."""

VALID_FREQUENCY_FILTER_OPERATORS: frozenset[str] = frozenset(
    {
        "is at least",
        "is at most",
        "is greater than",
        "is less than",
        "is equal to",
    }
)
"""Valid operators for frequency-based filters.

Note: ``"is between"`` excluded — ``FrequencyFilter.value`` is a single
scalar and cannot represent the two-bound range that "between" requires.
"""
