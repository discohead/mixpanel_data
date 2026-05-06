"""Bookmark validation engine for mixpanel_data.

Two validation layers:

- ``validate_query_args()``: Validates Python-level arguments before
  bookmark construction (Layer 1, rules V0-V27, CF1-CF2, CB1-CB3,
  CM1-CM5).
- ``validate_bookmark()``: Validates the bookmark JSON dict after
  construction (Layer 2, rules B1-B26).

Both return ``list[ValidationError]``. Callers decide whether to raise
``BookmarkValidationError``.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from difflib import get_close_matches
from typing import Any, Literal

from mixpanel_data._internal.bookmark_enums import (
    _MAX_FUNNEL_STEPS,
    _MAX_HOLDING_CONSTANT,
    MATH_NO_PER_USER,
    MATH_PROPERTY_OPTIONAL,
    MATH_REQUIRING_PROPERTY,
    MAX_CONVERSION_WINDOW,
    VALID_CHART_TYPES,
    VALID_CONVERSION_WINDOW_UNITS,
    VALID_FILTER_OPERATORS,
    VALID_FILTERS_DETERMINER,
    VALID_FLOWS_CHART_TYPES,
    VALID_FLOWS_CONVERSION_WINDOW_UNITS,
    VALID_FLOWS_COUNT_TYPES,
    VALID_FLOWS_MODES,
    VALID_FUNNEL_REENTRY_MODES,
    VALID_MATH_FUNNELS,
    VALID_MATH_INSIGHTS,
    VALID_MATH_RETENTION,
    VALID_METRIC_TYPES,
    VALID_PER_USER_AGGREGATIONS,
    VALID_PROPERTY_TYPES,
    VALID_RESOURCE_TYPES,
    VALID_RETENTION_ALIGNMENT,
    VALID_RETENTION_UNBOUNDED_MODES,
    VALID_RETENTION_UNITS,
    VALID_TIME_UNITS,
)
from mixpanel_data._internal.bookmark_schema import (
    InsightsBookmarkSortConfig,
    _sorting_code_mapper,
    validate_with_pydantic,
)

# Import specific types needed for isinstance checks at runtime.
from mixpanel_data._literal_types import (
    ConversionWindowUnit,
    FlowChartType,
    FlowConversionWindowUnit,
    FlowCountType,
    FunnelMathType,
    QueryTimeUnit,
    RetentionAlignment,
    RetentionMathType,
    RetentionMode,
    TimeUnit,
)
from mixpanel_data.exceptions import ValidationError
from mixpanel_data.types import (
    CohortBreakdown,
    CohortDefinition,
    CohortMetric,
    CustomPropertyRef,
    Exclusion,
    Filter,
    FlowStep,
    Formula,
    FrequencyBreakdown,
    FrequencyFilter,
    FunnelStep,
    GroupBy,
    HoldingConstant,
    InlineCustomProperty,
    MathType,
    Metric,
    PerUserAggregation,
    RetentionEvent,
)

_CP_INPUT_KEY_RE = re.compile(r"^[A-Z]$")
_CP_MAX_FORMULA_LENGTH = 20_000


def _validate_custom_property(
    prop: CustomPropertyRef | InlineCustomProperty,
    path: str,
) -> list[ValidationError]:
    """Validate a custom property specification (rules CP1-CP6).

    Args:
        prop: A ``CustomPropertyRef`` or ``InlineCustomProperty`` to validate.
        path: JSONPath-like location for error reporting.

    Returns:
        List of validation errors. Empty list means the property is valid.

    Raises:
        This function does not raise exceptions. Validation failures are
        returned as ``ValidationError`` objects in the result list.
    """
    errors: list[ValidationError] = []

    if isinstance(prop, CustomPropertyRef):
        # CP1: id must be a positive integer
        if prop.id <= 0:
            errors.append(
                ValidationError(
                    path=path,
                    message=(
                        f"custom property ID must be a positive integer (got {prop.id})"
                    ),
                    code="CP1_INVALID_ID",
                )
            )
    elif isinstance(prop, InlineCustomProperty):
        # CP2: formula must be non-empty
        if not prop.formula.strip():
            errors.append(
                ValidationError(
                    path=path,
                    message="inline custom property formula must be non-empty",
                    code="CP2_EMPTY_FORMULA",
                )
            )

        # CP3: inputs must have at least one entry
        if len(prop.inputs) == 0:
            errors.append(
                ValidationError(
                    path=path,
                    message=("inline custom property must have at least one input"),
                    code="CP3_EMPTY_INPUTS",
                )
            )

        # CP4: input keys must be single uppercase letters A-Z
        for key in prop.inputs:
            if not _CP_INPUT_KEY_RE.match(key):
                errors.append(
                    ValidationError(
                        path=path,
                        message=(
                            f"inline custom property input keys must be "
                            f"single uppercase letters (A-Z), got {key!r}"
                        ),
                        code="CP4_INVALID_INPUT_KEY",
                    )
                )

        # CP5: formula must not exceed max length
        if len(prop.formula) > _CP_MAX_FORMULA_LENGTH:
            errors.append(
                ValidationError(
                    path=path,
                    message=(
                        f"inline custom property formula exceeds maximum "
                        f"length of 20,000 characters (got {len(prop.formula)})"
                    ),
                    code="CP5_FORMULA_TOO_LONG",
                )
            )

        # CP6: each PropertyInput.name must be non-empty
        for key, pi in prop.inputs.items():
            if not pi.name.strip():
                errors.append(
                    ValidationError(
                        path=path,
                        message=(
                            f"inline custom property input {key!r} has an "
                            f"empty property name"
                        ),
                        code="CP6_EMPTY_INPUT_NAME",
                    )
                )

    return errors


def _scan_filters_for_custom_properties(
    filters: list[Filter],
    base_path: str,
) -> list[ValidationError]:
    """Scan a list of Filter objects for custom property references.

    Used by ``_scan_custom_properties()`` to validate custom properties
    inside filter lists attached to metrics and steps, including
    ``Metric.filters``, ``FunnelStep.filters``, ``FlowStep.filters``,
    and ``RetentionEvent.filters``.

    Args:
        filters: Filter objects to scan.
        base_path: JSONPath prefix for error reporting
            (e.g. ``"events[0]"`` or ``"steps[1]"``).

    Returns:
        List of validation errors for any invalid custom properties.
    """
    errors: list[ValidationError] = []
    for i, f in enumerate(filters):
        if isinstance(f._property, (CustomPropertyRef, InlineCustomProperty)):
            fpath = f"{base_path}.filters[{i}]"
            errors.extend(_validate_custom_property(f._property, fpath))
    return errors


def _scan_custom_properties(
    *,
    group_by: str
    | GroupBy
    | CohortBreakdown
    | FrequencyBreakdown
    | Sequence[str | GroupBy | CohortBreakdown | FrequencyBreakdown]
    | None = None,
    where: Filter | FrequencyFilter | Sequence[Filter | FrequencyFilter] | None = None,
    events: Sequence[str | Metric | CohortMetric] | None = None,
    funnel_steps: Sequence[str | FunnelStep] | None = None,
    flow_steps: Sequence[FlowStep] | None = None,
    retention_events: Sequence[RetentionEvent] | None = None,
) -> list[ValidationError]:
    """Scan all query positions for custom properties and validate.

    Collects all ``CustomPropertyRef`` and ``InlineCustomProperty`` values
    from group_by, filter, measurement, per-metric filter, per-funnel-step
    filter, per-flow-step filter, and per-retention-event filter positions
    and runs ``_validate_custom_property()`` on each.

    Note:
        ``where`` filters and some step/event filters are scanned from
        ``workspace.py`` rather than from the standalone validators
        because ``validate_query_args`` / ``validate_funnel_args`` /
        ``validate_retention_args`` do not receive the ``where`` parameter
        or the full step/event objects.  Flow step filters and retention
        event filters are scanned from ``workspace.py`` for the same reason.

    Args:
        group_by: Breakdown specification (may contain custom properties).
        where: Filter specification (may contain custom properties).
        events: Event specifications (Metric.property and Metric.filters
            may contain custom properties).
        funnel_steps: Funnel step specifications (FunnelStep.filters
            may contain custom properties).
        flow_steps: Flow step specifications (FlowStep.filters
            may contain custom properties).
        retention_events: Retention event specifications
            (RetentionEvent.filters may contain custom properties).

    Returns:
        List of validation errors. Empty list means all custom
        properties are valid.
    """
    errors: list[ValidationError] = []

    # Scan group_by
    if group_by is not None:
        groups = list(group_by) if isinstance(group_by, (list, tuple)) else [group_by]
        for i, g in enumerate(groups):
            if isinstance(g, GroupBy) and isinstance(
                g.property, (CustomPropertyRef, InlineCustomProperty)
            ):
                gpath = f"group_by[{i}]" if len(groups) > 1 else "group_by"
                errors.extend(_validate_custom_property(g.property, gpath))

    # Scan where (filters) — skip FrequencyFilter instances (no _property)
    if where is not None:
        filters = list(where) if isinstance(where, (list, tuple)) else [where]
        for i, f in enumerate(filters):
            if isinstance(f, FrequencyFilter):
                if f.event_filters:
                    for fi, ef in enumerate(f.event_filters):
                        if isinstance(
                            ef._property, (CustomPropertyRef, InlineCustomProperty)
                        ):
                            fpath = f"where[{i}].event_filters[{fi}]"
                            errors.extend(
                                _validate_custom_property(ef._property, fpath)
                            )
                continue
            if isinstance(f, Filter) and isinstance(
                f._property, (CustomPropertyRef, InlineCustomProperty)
            ):
                fpath = f"where[{i}]" if len(filters) > 1 else "where"
                errors.extend(_validate_custom_property(f._property, fpath))

    # Scan events (Metric.property AND Metric.filters)
    if events is not None:
        for idx, item in enumerate(events):
            if isinstance(item, Metric):
                if isinstance(item.property, (CustomPropertyRef, InlineCustomProperty)):
                    errors.extend(
                        _validate_custom_property(item.property, f"events[{idx}]")
                    )
                if item.filters:
                    errors.extend(
                        _scan_filters_for_custom_properties(
                            item.filters, f"events[{idx}]"
                        )
                    )

    # Scan funnel steps (FunnelStep.filters)
    if funnel_steps is not None:
        for idx, step in enumerate(funnel_steps):
            if isinstance(step, FunnelStep) and step.filters:
                errors.extend(
                    _scan_filters_for_custom_properties(step.filters, f"steps[{idx}]")
                )

    # Scan flow steps (FlowStep.filters)
    if flow_steps is not None:
        for idx, fstep in enumerate(flow_steps):
            if fstep.filters:
                errors.extend(
                    _scan_filters_for_custom_properties(fstep.filters, f"steps[{idx}]")
                )

    # Scan retention events (RetentionEvent.filters)
    # retention_events is always [born_event, return_event] — see workspace.py
    if retention_events is not None:
        for idx, rev in enumerate(retention_events):
            if rev.filters:
                label = "born_event" if idx == 0 else "return_event"
                errors.extend(_scan_filters_for_custom_properties(rev.filters, label))

    return errors


_SESSION_MATH: frozenset[str] = frozenset({"conversion_rate_session"})
"""Session-based math types requiring conversion_window_unit='session'."""

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_FORMULA_POSITION_RE = re.compile(r"[A-Z]")
_CONTROL_CHAR_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def contains_control_chars(s: str) -> bool:
    """Check whether a string contains ASCII control characters.

    Detects characters in the ranges ``\\x00-\\x08``, ``\\x0b``,
    ``\\x0c``, ``\\x0e-\\x1f``, and ``\\x7f`` (DEL). These characters
    are almost never intentional in event or property names and can
    cause silent issues in API queries.

    Args:
        s: The string to check.

    Returns:
        ``True`` if *s* contains at least one control character.
    """
    return bool(_CONTROL_CHAR_RE.search(s))


_INVISIBLE_RE = re.compile(r"^[\s\u200b\u200c\u200d\ufeff\u00ad\u2060]*$")
_MAX_LAST_DAYS = 3650  # 10 years — generous but sane upper bound
_MAX_ROLLING = 365  # rolling window sanity cap
_MAX_FILTER_VALUES = 1000  # server rejects queries with very large filter value lists


def _is_valid_date(date_str: str) -> bool:
    """Check if a YYYY-MM-DD string is a valid calendar date.

    Args:
        date_str: Date string in YYYY-MM-DD format (regex-validated).

    Returns:
        True if the date is a valid calendar date.
    """
    import datetime

    try:
        datetime.date.fromisoformat(date_str)
        return True
    except ValueError:
        return False


def _is_finite(value: int | float | None) -> bool:
    """Check if a numeric value is finite (not NaN, not Inf).

    Args:
        value: Numeric value to check.

    Returns:
        True if finite or None.
    """
    if value is None:
        return True
    if isinstance(value, float):
        import math as _math

        return _math.isfinite(value)
    return True


# =============================================================================
# Fuzzy matching helpers
# =============================================================================


def _suggest(
    value: str,
    valid: frozenset[str],
    n: int = 3,
    cutoff: float = 0.5,
) -> tuple[str, ...] | None:
    """Find closest matches for a mistyped enum value.

    Args:
        value: The invalid value to match against.
        valid: Set of valid values.
        n: Maximum number of suggestions.
        cutoff: Minimum similarity ratio (0.0-1.0).

    Returns:
        Tuple of closest matches, or None if no matches found.
    """
    matches = get_close_matches(value, sorted(valid), n=n, cutoff=cutoff)
    return tuple(matches) if matches else None


def _enum_error(
    path: str,
    field: str,
    value: str,
    valid: frozenset[str],
    code: str,
    severity: Literal["error", "warning"] = "error",
) -> ValidationError:
    """Build a validation error for an invalid enum value with suggestions.

    Args:
        path: JSONPath-like location.
        field: Human-readable field name.
        value: The invalid value.
        valid: Set of valid values.
        code: Machine-readable error code.
        severity: Error severity level.

    Returns:
        ValidationError with fuzzy-matched suggestions.
    """
    suggestion = _suggest(value, valid)
    if suggestion:
        msg = f"Invalid {field} '{value}'"
    else:
        sample = sorted(valid)[:5]
        msg = f"Invalid {field} '{value}'. Valid ({len(valid)} total): {sample}"
    return ValidationError(
        path=path,
        message=msg,
        code=code,
        severity=severity,
        suggestion=suggestion,
    )


# =============================================================================
# Reusable sub-validators (data_group_id, time, group-by)
# =============================================================================


def _validate_data_group_id(
    data_group_id: int | None,
) -> list[ValidationError]:
    """Validate data_group_id parameter if provided.

    When ``data_group_id`` is not ``None``, it must be a positive
    integer (> 0). Returns a list containing at most one error.

    Args:
        data_group_id: Data group ID to validate, or ``None``.

    Returns:
        List with one ``ValidationError`` if invalid, empty otherwise.
    """
    if data_group_id is not None:
        if isinstance(data_group_id, bool) or not isinstance(data_group_id, int):
            return [
                ValidationError(
                    path="data_group_id",
                    message=(
                        f"data_group_id must be a positive integer, "
                        f"got {type(data_group_id).__name__}"
                    ),
                    code="DG1_INVALID_DATA_GROUP_ID",
                )
            ]
        if data_group_id <= 0:
            return [
                ValidationError(
                    path="data_group_id",
                    message=(
                        f"data_group_id must be a positive integer (got {data_group_id})"
                    ),
                    code="DG1_INVALID_DATA_GROUP_ID",
                )
            ]
    return []


def validate_time_args(
    *,
    from_date: str | None,
    to_date: str | None,
    last: int,
) -> list[ValidationError]:
    """Validate time-range arguments (rules V7-V10, V15, V20).

    Extracted from ``validate_query_args()`` so callers building
    non-Insights bookmark types can reuse the same date/last checks
    without pulling in the full query-arg validator.

    Args:
        from_date: Start date in YYYY-MM-DD format, or ``None``.
        to_date: End date in YYYY-MM-DD format, or ``None``.
        last: Number of days for a relative date range. The default
            value used by ``Workspace.query()`` is ``30``.

    Returns:
        List of validation errors. Empty list means all time
        arguments are valid.

    Example:
        ```python
        from mixpanel_data._internal.validation import validate_time_args

        errors = validate_time_args(
            from_date="2024-01-01",
            to_date="2024-01-31",
            last=30,
        )
        assert errors == []
        ```
    """
    errors: list[ValidationError] = []

    # V7: last must be positive
    if last <= 0:
        errors.append(
            ValidationError(
                path="last",
                message="last must be a positive integer",
                code="V7_LAST_POSITIVE",
            )
        )

    # V8: Date format and calendar validation
    if from_date is not None:
        if not _DATE_RE.match(from_date):
            errors.append(
                ValidationError(
                    path="from_date",
                    message=f"from_date must be YYYY-MM-DD format (got '{from_date}')",
                    code="V8_DATE_FORMAT",
                )
            )
        elif not _is_valid_date(from_date):
            errors.append(
                ValidationError(
                    path="from_date",
                    message=f"from_date '{from_date}' is not a valid calendar date",
                    code="V8_DATE_INVALID",
                )
            )
    if to_date is not None:
        if not _DATE_RE.match(to_date):
            errors.append(
                ValidationError(
                    path="to_date",
                    message=f"to_date must be YYYY-MM-DD format (got '{to_date}')",
                    code="V8_DATE_FORMAT",
                )
            )
        elif not _is_valid_date(to_date):
            errors.append(
                ValidationError(
                    path="to_date",
                    message=f"to_date '{to_date}' is not a valid calendar date",
                    code="V8_DATE_INVALID",
                )
            )

    # V9: to_date requires from_date
    if to_date is not None and from_date is None:
        errors.append(
            ValidationError(
                path="to_date",
                message="to_date requires from_date",
                code="V9_TO_REQUIRES_FROM",
            )
        )

    # V10: Cannot combine explicit dates with non-default last
    if from_date is not None and last != 30:
        errors.append(
            ValidationError(
                path="last",
                message=(
                    f"Cannot combine last={last} with explicit dates; "
                    f"use either last or from_date/to_date"
                ),
                code="V10_DATE_LAST_EXCLUSIVE",
            )
        )

    # V15: Date ordering — from_date must be <= to_date
    if (
        from_date is not None
        and to_date is not None
        and _DATE_RE.match(from_date)
        and _DATE_RE.match(to_date)
        and from_date > to_date
    ):
        errors.append(
            ValidationError(
                path="from_date",
                message=(
                    f"from_date '{from_date}' is after to_date '{to_date}'; "
                    f"dates must be in chronological order"
                ),
                code="V15_DATE_ORDER",
            )
        )

    # V20: last must not be absurdly large
    if last > _MAX_LAST_DAYS:
        errors.append(
            ValidationError(
                path="last",
                message=(
                    f"last={last} exceeds maximum of {_MAX_LAST_DAYS} days (~10 years)"
                ),
                code="V20_LAST_TOO_LARGE",
            )
        )

    return errors


def validate_group_by_args(
    *,
    group_by: str
    | GroupBy
    | CohortBreakdown
    | FrequencyBreakdown
    | Sequence[str | GroupBy | CohortBreakdown | FrequencyBreakdown]
    | None,
) -> list[ValidationError]:
    """Validate group-by arguments (rules V11-V12, V18, V24).

    Extracted from ``validate_query_args()`` so callers building
    non-Insights bookmark types can reuse the same bucket checks
    without pulling in the full query-arg validator.

    Args:
        group_by: Breakdown specification — a property name string,
            a ``GroupBy`` object with optional bucket config,
            a ``CohortBreakdown`` object, a list of any mix,
            or ``None`` for no breakdown.

    Returns:
        List of validation errors. Empty list means all group-by
        arguments are valid.

    Example:
        ```python
        from mixpanel_data._internal.validation import validate_group_by_args
        from mixpanel_data.types import GroupBy

        errors = validate_group_by_args(
            group_by=GroupBy(
                "revenue",
                property_type="number",
                bucket_size=50,
                bucket_min=0,
                bucket_max=500,
            ),
        )
        assert errors == []
        ```
    """
    errors: list[ValidationError] = []

    if group_by is None:
        return errors

    groups = list(group_by) if isinstance(group_by, (list, tuple)) else [group_by]
    for i, g in enumerate(groups):
        if isinstance(g, GroupBy):
            gpath = f"group_by[{i}]" if len(groups) > 1 else "group_by"

            # V24: Bucket values must be finite (not NaN or Inf)
            for fname, fval in [
                ("bucket_size", g.bucket_size),
                ("bucket_min", g.bucket_min),
                ("bucket_max", g.bucket_max),
            ]:
                if not _is_finite(fval):
                    errors.append(
                        ValidationError(
                            path=gpath,
                            message=f"{fname} must be a finite number, got {fval}",
                            code="V24_BUCKET_NOT_FINITE",
                        )
                    )

            if (
                g.bucket_min is not None or g.bucket_max is not None
            ) and g.bucket_size is None:
                errors.append(
                    ValidationError(
                        path=gpath,
                        message="bucket_min/bucket_max require bucket_size",
                        code="V11_BUCKET_REQUIRES_SIZE",
                    )
                )
            if g.bucket_size is not None and g.bucket_size <= 0:
                errors.append(
                    ValidationError(
                        path=gpath,
                        message="bucket_size must be positive",
                        code="V12_BUCKET_SIZE_POSITIVE",
                    )
                )
            if g.bucket_size is not None and g.property_type != "number":
                errors.append(
                    ValidationError(
                        path=gpath,
                        message="bucket_size requires property_type='number'",
                        code="V12B_BUCKET_REQUIRES_NUMBER",
                    )
                )
            if g.bucket_size is not None and (
                g.bucket_min is None or g.bucket_max is None
            ):
                errors.append(
                    ValidationError(
                        path=gpath,
                        message="bucket_size requires both bucket_min and bucket_max",
                        code="V12C_BUCKET_REQUIRES_BOUNDS",
                    )
                )

            # V18: bucket_min must be < bucket_max
            if (
                g.bucket_min is not None
                and g.bucket_max is not None
                and g.bucket_min >= g.bucket_max
            ):
                errors.append(
                    ValidationError(
                        path=gpath,
                        message=(
                            f"bucket_min ({g.bucket_min}) must be less than "
                            f"bucket_max ({g.bucket_max})"
                        ),
                        code="V18_BUCKET_ORDER",
                    )
                )

    return errors


# =============================================================================
# Funnel argument validation (F1-F6)
# =============================================================================


def validate_funnel_args(
    *,
    steps: Sequence[str | FunnelStep],
    conversion_window: int,
    conversion_window_unit: ConversionWindowUnit = "day",
    math: FunnelMathType = "conversion_rate_unique",
    math_property: str | None = None,
    exclusions: list[Exclusion] | None,
    holding_constant: Sequence[str | HoldingConstant] | None = None,
    from_date: str | None,
    to_date: str | None,
    last: int,
    group_by: str
    | GroupBy
    | CohortBreakdown
    | list[str | GroupBy | CohortBreakdown]
    | None,
    reentry_mode: str | None = None,
    data_group_id: int | None = None,
) -> list[ValidationError]:
    """Validate funnel query arguments before bookmark construction (Layer 1).

    Implements funnel-specific validation rules F1-F12 plus reused
    time and group-by validators. Returns all errors found so callers
    can fix multiple issues in a single pass.

    Args:
        steps: Funnel step specifications (event names or FunnelStep objects).
        conversion_window: Conversion window size (must be positive).
        conversion_window_unit: Time unit for conversion window.
            Must be one of: second, minute, hour, day, week, month,
            session. Default: ``"day"``.
        math: Funnel aggregation function. Default:
            ``"conversion_rate_unique"``.
        math_property: Numeric property name for property-aggregation
            math types (average, median, min, max, p25, p75, p90, p99).
            Required when ``math`` is a property-aggregation type;
            must be ``None`` otherwise. Default: ``None``.
        exclusions: Events to exclude between steps, or ``None``.
        holding_constant: Properties to hold constant, or ``None``.
        from_date: Start date (YYYY-MM-DD) or ``None``.
        to_date: End date (YYYY-MM-DD) or ``None``.
        last: Number of days for relative date range.
        group_by: Breakdown specification.
        reentry_mode: Funnel reentry mode. Must be one of:
            default, basic, aggressive, optimized, or ``None``.
            Default: ``None``.
        data_group_id: Optional data group ID for group-level analytics.
            Must be a positive integer if provided. Default: ``None``.

    Returns:
        List of validation errors. Empty list means all arguments are valid.

    Example:
        ```python
        from mixpanel_data._internal.validation import validate_funnel_args

        errors = validate_funnel_args(
            steps=["Signup", "Purchase"],
            conversion_window=14,
            exclusions=None,
            from_date=None,
            to_date=None,
            last=30,
            group_by=None,
        )
        assert errors == []
        ```
    """
    errors: list[ValidationError] = []

    # DG1: data_group_id must be positive if provided
    errors.extend(_validate_data_group_id(data_group_id))

    # F1: At least 2 steps required
    if len(steps) < 2:
        errors.append(
            ValidationError(
                path="steps",
                message=f"At least 2 steps are required (got {len(steps)})",
                code="F1_MIN_STEPS",
            )
        )

    # F1b: Maximum 100 steps
    if len(steps) > _MAX_FUNNEL_STEPS:
        errors.append(
            ValidationError(
                path="steps",
                message=(
                    f"Maximum {_MAX_FUNNEL_STEPS} steps allowed (got {len(steps)})"
                ),
                code="F1_MAX_STEPS",
            )
        )

    # F2: Each step event must be non-empty string, no control/invisible chars
    for i, step in enumerate(steps):
        event = step.event if isinstance(step, FunnelStep) else step
        if not isinstance(event, str) or not event.strip():
            errors.append(
                ValidationError(
                    path=f"steps[{i}]",
                    message="Step event name must be a non-empty string",
                    code="F2_EMPTY_STEP_EVENT",
                )
            )
            continue
        # F2b: No control characters
        if _CONTROL_CHAR_RE.search(event):
            errors.append(
                ValidationError(
                    path=f"steps[{i}]",
                    message=(f"Step event name contains control characters: {event!r}"),
                    code="F2_CONTROL_CHAR_STEP_EVENT",
                )
            )
        # F2c: No invisible-only names
        if _INVISIBLE_RE.match(event):
            errors.append(
                ValidationError(
                    path=f"steps[{i}]",
                    message="Step event name contains only invisible characters",
                    code="F2_INVISIBLE_STEP_EVENT",
                )
            )

    # F3: Positive integer conversion window
    _valid_window = isinstance(conversion_window, int) and not isinstance(
        conversion_window, bool
    )
    if not _valid_window:
        errors.append(
            ValidationError(
                path="conversion_window",
                message=(
                    f"conversion_window must be an integer, "
                    f"got {type(conversion_window).__name__}"
                ),
                code="F3_CONVERSION_WINDOW_TYPE",
            )
        )
    elif conversion_window <= 0:
        errors.append(
            ValidationError(
                path="conversion_window",
                message="conversion_window must be a positive integer",
                code="F3_CONVERSION_WINDOW_POSITIVE",
            )
        )

    # F3b: Maximum conversion window per unit (requires valid int)
    if (
        _valid_window
        and conversion_window_unit in MAX_CONVERSION_WINDOW
        and conversion_window > 0
    ):
        max_val = MAX_CONVERSION_WINDOW[conversion_window_unit]
        if conversion_window > max_val:
            errors.append(
                ValidationError(
                    path="conversion_window",
                    message=(
                        f"conversion_window={conversion_window} exceeds "
                        f"maximum of {max_val} for unit "
                        f"'{conversion_window_unit}'"
                    ),
                    code="F3_CONVERSION_WINDOW_MAX",
                )
            )

    # F7: Conversion window unit validation
    if conversion_window_unit not in VALID_CONVERSION_WINDOW_UNITS:
        errors.append(
            _enum_error(
                path="conversion_window_unit",
                field="conversion_window_unit",
                value=conversion_window_unit,
                valid=VALID_CONVERSION_WINDOW_UNITS,
                code="F7_INVALID_WINDOW_UNIT",
            )
        )

    if _valid_window:
        # F7b: Minimum conversion window per unit (second requires >=2)
        if conversion_window_unit == "second" and 0 < conversion_window < 2:
            errors.append(
                ValidationError(
                    path="conversion_window",
                    message=(
                        f"conversion_window must be at least 2 when "
                        f"conversion_window_unit='second' (got {conversion_window})"
                    ),
                    code="F7_SECOND_MIN_WINDOW",
                    suggestion=("2",),
                )
            )

        # F9: Session math requires session window
        if math in _SESSION_MATH and conversion_window_unit != "session":
            errors.append(
                ValidationError(
                    path="math",
                    message=(
                        f"math='{math}' requires conversion_window_unit='session'"
                    ),
                    code="F9_SESSION_MATH_REQUIRES_SESSION_WINDOW",
                )
            )
        if (
            conversion_window_unit == "session"
            and math not in _SESSION_MATH
            and conversion_window != 1
        ):
            errors.append(
                ValidationError(
                    path="conversion_window",
                    message=(
                        "conversion_window_unit='session' requires conversion_window=1"
                    ),
                    code="F9_SESSION_WINDOW_REQUIRES_ONE",
                )
            )

    # F10: Property math requires math_property
    if math in MATH_REQUIRING_PROPERTY and math_property is None:
        errors.append(
            ValidationError(
                path="math_property",
                message=(
                    f"math='{math}' requires a math_property "
                    f"(numeric property name to aggregate)"
                ),
                code="F10_MATH_MISSING_PROPERTY",
            )
        )

    # F11: Non-property math rejects math_property
    if (
        math not in MATH_REQUIRING_PROPERTY
        and math not in MATH_PROPERTY_OPTIONAL
        and math_property is not None
    ):
        valid = sorted(MATH_REQUIRING_PROPERTY | MATH_PROPERTY_OPTIONAL)
        errors.append(
            ValidationError(
                path="math_property",
                message=(
                    f"math='{math}' does not support math_property; "
                    f"valid math types for property aggregation: {valid}"
                ),
                code="F11_MATH_REJECTS_PROPERTY",
            )
        )

    # F4: Non-empty exclusion event names and step range validation
    if exclusions is not None:
        for i, ex in enumerate(exclusions):
            if not ex.event or not ex.event.strip():
                errors.append(
                    ValidationError(
                        path=f"exclusions[{i}]",
                        message="Exclusion event name must be a non-empty string",
                        code="F4_EMPTY_EXCLUSION_EVENT",
                    )
                )
            # F4 control char check on exclusion events
            elif _CONTROL_CHAR_RE.search(ex.event):
                errors.append(
                    ValidationError(
                        path=f"exclusions[{i}]",
                        message=(
                            f"Exclusion event name contains control "
                            f"characters: {ex.event!r}"
                        ),
                        code="F4_CONTROL_CHAR_EXCLUSION",
                    )
                )
            # F4e: from_step must be non-negative
            if ex.from_step < 0:
                errors.append(
                    ValidationError(
                        path=f"exclusions[{i}]",
                        message=(
                            f"Exclusion from_step must be >= 0 (got {ex.from_step})"
                        ),
                        code="F4_EXCLUSION_NEGATIVE_STEP",
                    )
                )
            # F4b: to_step must be > from_step (server requires strict from < to)
            if ex.to_step is not None and ex.to_step <= ex.from_step:
                errors.append(
                    ValidationError(
                        path=f"exclusions[{i}]",
                        message=(
                            f"Exclusion to_step ({ex.to_step}) must be > "
                            f"from_step ({ex.from_step})"
                        ),
                        code="F4_EXCLUSION_STEP_ORDER",
                    )
                )
            # F4c: to_step must not exceed step count
            if ex.to_step is not None and ex.to_step >= len(steps):
                errors.append(
                    ValidationError(
                        path=f"exclusions[{i}]",
                        message=(
                            f"Exclusion to_step ({ex.to_step}) exceeds "
                            f"step count ({len(steps)})"
                        ),
                        code="F4_EXCLUSION_STEP_BOUNDS",
                    )
                )
            # F4d: from_step must not exceed step count
            if ex.from_step >= len(steps):
                errors.append(
                    ValidationError(
                        path=f"exclusions[{i}]",
                        message=(
                            f"Exclusion from_step ({ex.from_step}) exceeds "
                            f"step count ({len(steps)})"
                        ),
                        code="F4_EXCLUSION_STEP_BOUNDS",
                    )
                )

    # F8: Holding constant validation
    if holding_constant is not None:
        # F8b: Each holding constant property must be a non-empty string
        for i, hc in enumerate(holding_constant):
            prop = hc.property if isinstance(hc, HoldingConstant) else hc
            if not isinstance(prop, str) or not prop.strip():
                errors.append(
                    ValidationError(
                        path=f"holding_constant[{i}]",
                        message="Holding constant property name must be a non-empty string",
                        code="F8_EMPTY_HOLDING_CONSTANT_PROPERTY",
                    )
                )

    if holding_constant is not None and len(holding_constant) > _MAX_HOLDING_CONSTANT:
        errors.append(
            ValidationError(
                path="holding_constant",
                message=(
                    f"Maximum {_MAX_HOLDING_CONSTANT} holding_constant "
                    f"properties allowed (got {len(holding_constant)})"
                ),
                code="F8_MAX_HOLDING_CONSTANT",
            )
        )

    # F5: Time argument validation (delegated)
    errors.extend(validate_time_args(from_date=from_date, to_date=to_date, last=last))

    # F6: GroupBy validation (delegated)
    errors.extend(validate_group_by_args(group_by=group_by))

    # CP1-CP6: Custom property validation (group_by and per-step filters)
    errors.extend(_scan_custom_properties(group_by=group_by, funnel_steps=steps))

    # F12: reentry_mode validation
    if reentry_mode is not None and reentry_mode not in VALID_FUNNEL_REENTRY_MODES:
        suggestion = _suggest(reentry_mode, VALID_FUNNEL_REENTRY_MODES)
        errors.append(
            ValidationError(
                path="reentry_mode",
                message=(
                    f"Invalid reentry_mode '{reentry_mode}'; "
                    f"valid values: {sorted(VALID_FUNNEL_REENTRY_MODES)}"
                ),
                code="F12_INVALID_REENTRY_MODE",
                suggestion=suggestion,
            )
        )

    return errors


# =============================================================================
# Retention argument validation (R1-R12)
# =============================================================================

_VALID_RETENTION_MATH_PUBLIC: frozenset[str] = frozenset(
    {"retention_rate", "unique", "total", "average"}
)
"""Public-facing retention math types (Layer 1).

Expanded in Phase 040 to include ``"total"`` and ``"average"`` — previously
L1 incorrectly rejected these even though L2 (via ``VALID_MATH_RETENTION``
in bookmark_enums.py) accepted them. Now L1 and L2 use the same set.
"""

_VALID_RETENTION_MODES: frozenset[str] = frozenset({"curve", "trends", "table"})
"""Valid display modes for retention queries."""

_MAX_RETENTION_BUCKETS = 730
"""Maximum number of custom retention buckets allowed by the API."""


def validate_retention_args(
    *,
    born_event: str,
    return_event: str,
    retention_unit: TimeUnit = "week",
    alignment: RetentionAlignment = "birth",
    bucket_sizes: list[int] | None = None,
    math: RetentionMathType = "retention_rate",
    mode: RetentionMode = "curve",
    unit: QueryTimeUnit = "day",
    from_date: str | None = None,
    to_date: str | None = None,
    last: int = 30,
    group_by: str
    | GroupBy
    | CohortBreakdown
    | list[str | GroupBy | CohortBreakdown]
    | None = None,
    unbounded_mode: str | None = None,
    data_group_id: int | None = None,
) -> list[ValidationError]:
    """Validate retention query arguments before bookmark construction (Layer 1).

    Implements retention-specific validation rules R1-R13 plus reused
    time and group-by validators. Returns all errors found so callers
    can fix multiple issues in a single pass.

    Args:
        born_event: Event name that defines cohort membership.
        return_event: Event name that defines return.
        retention_unit: Retention period unit. Must be one of:
            day, week, month. Default: ``"week"``.
        alignment: Retention alignment mode. Must be one of:
            birth, interval_start. Default: ``"birth"``.
        bucket_sizes: Custom bucket sizes (positive ints in ascending
            order), or ``None`` for default uniform buckets.
        math: Retention aggregation function. Must be one of:
            retention_rate, unique. Default: ``"retention_rate"``.
        mode: Display mode for retention results. Must be one of:
            curve, trends, table. Default: ``"curve"``.
        unit: Time unit for retention buckets. Must be one of:
            day, week, month. Default: ``"day"``.
        from_date: Start date (YYYY-MM-DD) or ``None``.
        to_date: End date (YYYY-MM-DD) or ``None``.
        last: Number of days for relative date range.
        group_by: Breakdown specification.
        unbounded_mode: Retention unbounded mode. Must be one of:
            none, carry_back, carry_forward, consecutive_forward,
            or ``None``. Default: ``None``.
        data_group_id: Optional data group ID for group-level analytics.
            Must be a positive integer if provided. Default: ``None``.

    Returns:
        List of validation errors. Empty list means all arguments are valid.

    Example:
        ```python
        from mixpanel_data._internal.validation import validate_retention_args

        errors = validate_retention_args(
            born_event="Signup",
            return_event="Login",
        )
        assert errors == []
        ```
    """
    errors: list[ValidationError] = []

    # DG1: data_group_id must be positive if provided
    errors.extend(_validate_data_group_id(data_group_id))

    # R1: born_event must be non-empty string
    if not born_event.strip():
        errors.append(
            ValidationError(
                path="born_event",
                message="born_event must be a non-empty string",
                code="R1_EMPTY_BORN_EVENT",
            )
        )
    else:
        # R1b: No control characters
        if _CONTROL_CHAR_RE.search(born_event):
            errors.append(
                ValidationError(
                    path="born_event",
                    message=(f"born_event contains control characters: {born_event!r}"),
                    code="R1_CONTROL_CHAR_BORN_EVENT",
                )
            )
        # R1c: No invisible-only names
        if _INVISIBLE_RE.match(born_event):
            errors.append(
                ValidationError(
                    path="born_event",
                    message="born_event contains only invisible characters",
                    code="R1_INVISIBLE_BORN_EVENT",
                )
            )

    # R2: return_event must be non-empty string
    if not return_event.strip():
        errors.append(
            ValidationError(
                path="return_event",
                message="return_event must be a non-empty string",
                code="R2_EMPTY_RETURN_EVENT",
            )
        )
    else:
        # R2b: No control characters
        if _CONTROL_CHAR_RE.search(return_event):
            errors.append(
                ValidationError(
                    path="return_event",
                    message=(
                        f"return_event contains control characters: {return_event!r}"
                    ),
                    code="R2_CONTROL_CHAR_RETURN_EVENT",
                )
            )
        # R2c: No invisible-only names
        if _INVISIBLE_RE.match(return_event):
            errors.append(
                ValidationError(
                    path="return_event",
                    message="return_event contains only invisible characters",
                    code="R2_INVISIBLE_RETURN_EVENT",
                )
            )

    # R3: Time argument validation (delegated)
    errors.extend(validate_time_args(from_date=from_date, to_date=to_date, last=last))

    # R4: GroupBy validation (delegated)
    errors.extend(validate_group_by_args(group_by=group_by))

    # R5: bucket_sizes values must be positive integers
    all_valid_ints = True
    if bucket_sizes is not None:
        for i, val in enumerate(bucket_sizes):
            if isinstance(val, float):
                all_valid_ints = False
                errors.append(
                    ValidationError(
                        path=f"bucket_sizes[{i}]",
                        message=f"bucket_sizes[{i}] must be an integer, got float",
                        code="R5_BUCKET_SIZES_INTEGER",
                    )
                )
            elif not isinstance(val, int) or isinstance(val, bool) or val <= 0:
                all_valid_ints = False
                errors.append(
                    ValidationError(
                        path="bucket_sizes",
                        message="bucket_sizes values must be positive integers",
                        code="R5_BUCKET_SIZES_POSITIVE",
                    )
                )

        # R5c: Maximum bucket count
        if len(bucket_sizes) > _MAX_RETENTION_BUCKETS:
            errors.append(
                ValidationError(
                    path="bucket_sizes",
                    message=(
                        f"bucket_sizes has {len(bucket_sizes)} entries, "
                        f"maximum is {_MAX_RETENTION_BUCKETS}"
                    ),
                    code="R5_BUCKET_SIZES_TOO_MANY",
                )
            )

        # R6: bucket_sizes must be in strictly ascending order
        # Only check when all elements are valid positive ints to avoid
        # TypeError on comparison with non-numeric values.
        if all_valid_ints and len(bucket_sizes) >= 2:
            for i in range(1, len(bucket_sizes)):
                if bucket_sizes[i] <= bucket_sizes[i - 1]:
                    errors.append(
                        ValidationError(
                            path="bucket_sizes",
                            message="bucket_sizes must be in strictly ascending order",
                            code="R6_BUCKET_SIZES_ASCENDING",
                        )
                    )
                    break

    # R7: retention_unit validation
    if retention_unit not in VALID_RETENTION_UNITS:
        errors.append(
            _enum_error(
                path="retention_unit",
                field="retention_unit",
                value=retention_unit,
                valid=VALID_RETENTION_UNITS,
                code="R7_INVALID_RETENTION_UNIT",
            )
        )

    # R8: alignment validation
    if alignment not in VALID_RETENTION_ALIGNMENT:
        errors.append(
            _enum_error(
                path="alignment",
                field="alignment",
                value=alignment,
                valid=VALID_RETENTION_ALIGNMENT,
                code="R8_INVALID_ALIGNMENT",
            )
        )

    # R9: math validation (public-facing subset)
    if math not in _VALID_RETENTION_MATH_PUBLIC:
        errors.append(
            _enum_error(
                path="math",
                field="math",
                value=math,
                valid=_VALID_RETENTION_MATH_PUBLIC,
                code="R9_INVALID_MATH",
            )
        )

    # R10: mode validation
    if mode not in _VALID_RETENTION_MODES:
        errors.append(
            _enum_error(
                path="mode",
                field="mode",
                value=str(mode),
                valid=_VALID_RETENTION_MODES,
                code="R10_INVALID_MODE",
            )
        )

    # R11: unit must be valid for retention context (day, week, month only)
    if unit not in VALID_RETENTION_UNITS:
        errors.append(
            _enum_error(
                path="unit",
                field="unit",
                value=str(unit),
                valid=VALID_RETENTION_UNITS,
                code="R11_INVALID_UNIT",
            )
        )

    # R12: group_by strings must be non-empty
    # CB3: CohortBreakdown and GroupBy are mutually exclusive in retention
    if group_by is not None:
        gb_list = group_by if isinstance(group_by, list) else [group_by]
        for i, g in enumerate(gb_list):
            if isinstance(g, str) and not g.strip():
                gpath = f"group_by[{i}]" if len(gb_list) > 1 else "group_by"
                errors.append(
                    ValidationError(
                        path=gpath,
                        message="group_by property name must be a non-empty string",
                        code="R12_EMPTY_GROUP_BY",
                    )
                )

        has_cohort = any(isinstance(g, CohortBreakdown) for g in gb_list)
        has_property = any(isinstance(g, (str, GroupBy)) for g in gb_list)
        if has_cohort and has_property:
            errors.append(
                ValidationError(
                    path="group_by",
                    message=(
                        "query_retention does not support mixing "
                        "CohortBreakdown with property GroupBy"
                    ),
                    code="CB3_RETENTION_MIXED_BREAKDOWN",
                )
            )

    # CP1-CP6: Custom property validation
    errors.extend(_scan_custom_properties(group_by=group_by))

    # R13: unbounded_mode validation
    if (
        unbounded_mode is not None
        and unbounded_mode not in VALID_RETENTION_UNBOUNDED_MODES
    ):
        suggestion = _suggest(unbounded_mode, VALID_RETENTION_UNBOUNDED_MODES)
        errors.append(
            ValidationError(
                path="unbounded_mode",
                message=(
                    f"Invalid unbounded_mode '{unbounded_mode}'; "
                    f"valid values: {sorted(VALID_RETENTION_UNBOUNDED_MODES)}"
                ),
                code="R13_INVALID_UNBOUNDED_MODE",
                suggestion=suggestion,
            )
        )

    return errors


# =============================================================================
# Flow argument validation (FL1-FL10)
# =============================================================================

_MAX_FLOW_STEPS_DIRECTION = 5
"""Maximum number of forward or reverse steps in a flow query (0-5)."""

_MAX_FLOW_CARDINALITY = 50
"""Maximum cardinality (number of top paths shown) in a flow query."""

_FLOW_MAX_WINDOW: dict[str, int] = {
    "month": 12,
    "week": 52,
    "day": 366,
}
"""Maximum conversion window per unit (366-day equivalent for a leap year)."""


def validate_flow_args(
    *,
    steps: list[str],
    forward: int = 3,
    reverse: int = 0,
    count_type: FlowCountType = "unique",
    mode: FlowChartType = "sankey",
    cardinality: int = 3,
    conversion_window: int = 7,
    conversion_window_unit: FlowConversionWindowUnit = "day",
    from_date: str | None = None,
    to_date: str | None = None,
    last: int = 30,
    time_comparison: object | None = None,
    data_group_id: int | None = None,
) -> list[ValidationError]:
    """Validate flow query arguments before bookmark construction (Layer 1).

    Implements flow-specific validation rules FL1-FL10, DG1
    (data_group_id validation), time_comparison rejection, plus enum
    checks and reused time validators. Returns all errors found so
    callers can fix multiple issues in a single pass.

    Args:
        steps: List of event names that define the flow anchor points.
            Must contain at least one event.
        forward: Number of steps to show after the anchor event.
            Must be in range 0-5. Default: ``3``.
        reverse: Number of steps to show before the anchor event.
            Must be in range 0-5. Default: ``0``.
        count_type: Counting method for flow analysis. Must be one of:
            unique, total, session. Default: ``"unique"``.
        mode: Display mode for flow results. Must be one of:
            sankey, paths. Default: ``"sankey"``.
        cardinality: Number of top paths to display. Must be in
            range 1-50. Default: ``3``.
        conversion_window: Conversion window size. Must be a positive
            integer. Default: ``7``.
        conversion_window_unit: Time unit for conversion window. Must
            be one of: day, week, month, session. Default: ``"day"``.
        from_date: Start date (YYYY-MM-DD) or ``None``.
        to_date: End date (YYYY-MM-DD) or ``None``.
        last: Number of days for relative date range. Default: ``30``.
        time_comparison: Time comparison object. Must be ``None`` for
            flows — flows do not support period-over-period comparison.
            Default: ``None``.
        data_group_id: Optional data group ID for group-level analytics.
            Must be a positive integer if provided. Default: ``None``.

    Returns:
        List of validation errors. Empty list means all arguments are valid.

    Example:
        ```python
        from mixpanel_data._internal.validation import validate_flow_args

        errors = validate_flow_args(
            steps=["Purchase"],
            forward=3,
            reverse=0,
        )
        assert errors == []
        ```
    """
    errors: list[ValidationError] = []

    # DG1: data_group_id must be positive if provided
    errors.extend(_validate_data_group_id(data_group_id))

    # Flows do not support time comparison
    if time_comparison is not None:
        errors.append(
            ValidationError(
                path="time_comparison",
                message=(
                    "Flows do not support time comparison; "
                    "remove the time_comparison parameter"
                ),
                code="FL_TIME_COMPARISON_NOT_SUPPORTED",
            )
        )

    # FL1: steps must be non-empty
    if len(steps) == 0:
        errors.append(
            ValidationError(
                path="steps",
                message="At least one step event is required",
                code="FL1_EMPTY_STEPS",
            )
        )

    # FL2: Each step event must be non-empty string, no control/invisible chars
    for i, event in enumerate(steps):
        if not isinstance(event, str) or not event.strip():
            errors.append(
                ValidationError(
                    path=f"steps[{i}]",
                    message="Step event name must be a non-empty string",
                    code="FL2_EMPTY_STEP_EVENT",
                )
            )
            continue
        # FL2b: No control characters
        if _CONTROL_CHAR_RE.search(event):
            errors.append(
                ValidationError(
                    path=f"steps[{i}]",
                    message=(f"Step event name contains control characters: {event!r}"),
                    code="FL2_CONTROL_CHAR_STEP_EVENT",
                )
            )
        # FL2c: No invisible-only names
        if _INVISIBLE_RE.match(event):
            errors.append(
                ValidationError(
                    path=f"steps[{i}]",
                    message="Step event name contains only invisible characters",
                    code="FL2_INVISIBLE_STEP_EVENT",
                )
            )

    # FL3: forward must be in range 0-5
    if forward < 0 or forward > _MAX_FLOW_STEPS_DIRECTION:
        errors.append(
            ValidationError(
                path="forward",
                message=(
                    f"forward must be between 0 and {_MAX_FLOW_STEPS_DIRECTION} "
                    f"(got {forward})"
                ),
                code="FL3_FORWARD_RANGE",
            )
        )

    # FL4: reverse must be in range 0-5
    if reverse < 0 or reverse > _MAX_FLOW_STEPS_DIRECTION:
        errors.append(
            ValidationError(
                path="reverse",
                message=(
                    f"reverse must be between 0 and {_MAX_FLOW_STEPS_DIRECTION} "
                    f"(got {reverse})"
                ),
                code="FL4_REVERSE_RANGE",
            )
        )

    # FL5: forward + reverse must be > 0 (at least one direction)
    if forward + reverse == 0:
        errors.append(
            ValidationError(
                path="forward",
                message=(
                    "At least one of forward or reverse must be > 0; "
                    "both are currently 0"
                ),
                code="FL5_NO_DIRECTION",
            )
        )

    # FL6: cardinality must be in range 1-50
    if cardinality < 1 or cardinality > _MAX_FLOW_CARDINALITY:
        errors.append(
            ValidationError(
                path="cardinality",
                message=(
                    f"cardinality must be between 1 and {_MAX_FLOW_CARDINALITY} "
                    f"(got {cardinality})"
                ),
                code="FL6_CARDINALITY_RANGE",
            )
        )

    # FL7: conversion_window must be positive
    if conversion_window <= 0:
        errors.append(
            ValidationError(
                path="conversion_window",
                message="conversion_window must be a positive integer",
                code="FL7_CONVERSION_WINDOW_POSITIVE",
            )
        )

    # FL7b: conversion_window max per unit (366-day equivalent)
    if (
        conversion_window > 0
        and conversion_window_unit in _FLOW_MAX_WINDOW
        and conversion_window > _FLOW_MAX_WINDOW[conversion_window_unit]
    ):
        max_val = _FLOW_MAX_WINDOW[conversion_window_unit]
        errors.append(
            ValidationError(
                path="conversion_window",
                message=(
                    f"conversion_window={conversion_window} exceeds "
                    f"maximum of {max_val} for unit "
                    f"'{conversion_window_unit}'"
                ),
                code="FL7_CONVERSION_WINDOW_MAX",
            )
        )

    # Enum: count_type validation
    if count_type not in VALID_FLOWS_COUNT_TYPES:
        errors.append(
            _enum_error(
                path="count_type",
                field="count_type",
                value=count_type,
                valid=VALID_FLOWS_COUNT_TYPES,
                code="FL_INVALID_COUNT_TYPE",
            )
        )

    # Enum: mode validation
    if mode not in VALID_FLOWS_MODES:
        errors.append(
            _enum_error(
                path="mode",
                field="mode",
                value=mode,
                valid=VALID_FLOWS_MODES,
                code="FL_INVALID_MODE",
            )
        )

    # Enum: conversion_window_unit validation
    if conversion_window_unit not in VALID_FLOWS_CONVERSION_WINDOW_UNITS:
        errors.append(
            _enum_error(
                path="conversion_window_unit",
                field="conversion_window_unit",
                value=conversion_window_unit,
                valid=VALID_FLOWS_CONVERSION_WINDOW_UNITS,
                code="FL_INVALID_WINDOW_UNIT",
            )
        )

    # FL9: count_type='session' requires conversion_window_unit='session'
    if count_type == "session" and conversion_window_unit != "session":
        errors.append(
            ValidationError(
                path="count_type",
                message=(
                    "count_type='session' requires conversion_window_unit='session'"
                ),
                code="FL9_SESSION_REQUIRES_SESSION_WINDOW",
            )
        )

    # FL10: conversion_window_unit='session' requires conversion_window=1
    if conversion_window_unit == "session" and conversion_window != 1:
        errors.append(
            ValidationError(
                path="conversion_window",
                message=(
                    "conversion_window_unit='session' requires conversion_window=1"
                ),
                code="FL10_SESSION_WINDOW_REQUIRES_ONE",
            )
        )

    # FL8: Time argument validation (delegated)
    errors.extend(validate_time_args(from_date=from_date, to_date=to_date, last=last))

    return errors


# =============================================================================
# Flow bookmark validation (FLB1-FLB6)
# =============================================================================


def validate_flow_bookmark(
    params: dict[str, Any],
) -> list[ValidationError]:
    """Validate a flat flow bookmark params dict after construction (Layer 2).

    Validates the structural integrity and enum values of a built
    flow bookmark params dict before it is sent to the Mixpanel API.
    Flows use a flat structure without ``sections``/``displayOptions``,
    so this is a separate function from ``validate_bookmark()``.

    Args:
        params: The flow bookmark params dict (flat structure with
            ``steps``, ``date_range``, ``chartType``, ``count_type``,
            and ``version`` keys).

    Returns:
        List of validation errors. Empty list means the bookmark is valid.

    Example:
        ```python
        from mixpanel_data._internal.validation import validate_flow_bookmark

        errors = validate_flow_bookmark({
            "steps": [{"event": "Purchase", "forward": 3, "reverse": 0}],
            "date_range": {"type": "in the last", "from_date": {"unit": "day", "value": 30}, "to_date": "$now"},
            "chartType": "sankey",
            "count_type": "unique",
            "version": 2,
        })
        assert errors == []
        ```
    """
    errors: list[ValidationError] = []

    # FLB1: steps must be present and non-empty
    steps = params.get("steps")
    if not isinstance(steps, list) or len(steps) == 0:
        errors.append(
            ValidationError(
                path="steps",
                message="Flow bookmark must have at least one step",
                code="FLB1_EMPTY_STEPS",
            )
        )
    else:
        # FLB2: Each step event must be non-empty
        for i, step in enumerate(steps):
            if isinstance(step, dict):
                event = step.get("event")
                if not isinstance(event, str) or not event.strip():
                    errors.append(
                        ValidationError(
                            path=f"steps[{i}].event",
                            message="Step event name must be a non-empty string",
                            code="FLB2_EMPTY_STEP_EVENT",
                        )
                    )

    # FLB3: count_type validation
    count_type = params.get("count_type")
    if count_type is not None and count_type not in VALID_FLOWS_COUNT_TYPES:
        errors.append(
            _enum_error(
                path="count_type",
                field="count_type",
                value=str(count_type),
                valid=VALID_FLOWS_COUNT_TYPES,
                code="FLB3_INVALID_COUNT_TYPE",
            )
        )

    # FLB4: chartType validation
    chart_type = params.get("chartType")
    if chart_type is not None and chart_type not in VALID_FLOWS_CHART_TYPES:
        errors.append(
            _enum_error(
                path="chartType",
                field="chartType",
                value=str(chart_type),
                valid=VALID_FLOWS_CHART_TYPES,
                code="FLB4_INVALID_CHART_TYPE",
            )
        )

    # FLB5: date_range must be present
    if "date_range" not in params:
        errors.append(
            ValidationError(
                path="date_range",
                message="Flow bookmark requires a date_range",
                code="FLB5_MISSING_DATE_RANGE",
            )
        )

    # FLB6: version must be 2
    version = params.get("version")
    if version != 2:
        errors.append(
            ValidationError(
                path="version",
                message=f"Flow bookmark version must be 2 (got {version})",
                code="FLB6_INVALID_VERSION",
            )
        )

    return errors


# =============================================================================
# Layer 1: Argument Validation (V0-V14)
# =============================================================================


def validate_query_args(
    *,
    events: Sequence[str | Metric | CohortMetric],
    math: MathType,
    math_property: str | None,
    per_user: PerUserAggregation | None,
    percentile_value: int | float | None = None,
    from_date: str | None,
    to_date: str | None,
    last: int,
    has_formula: bool,
    rolling: int | None,
    cumulative: bool,
    group_by: str
    | GroupBy
    | CohortBreakdown
    | FrequencyBreakdown
    | Sequence[str | GroupBy | CohortBreakdown | FrequencyBreakdown]
    | None,
    formulas: Sequence[Any] | None = None,
    data_group_id: int | None = None,
) -> list[ValidationError]:
    """Validate query arguments before bookmark construction (Layer 1).

    Implements validation rules V0-V27, delegating time (V7-V10, V15,
    V20) and group-by (V11-V12, V18, V24) to extracted helpers.
    Returns all errors found, not just the first, so callers can
    fix multiple issues in a single pass.

    Args:
        events: Event names or Metric objects.
        math: Top-level aggregation function.
        math_property: Property for property-based math.
        per_user: Per-user pre-aggregation.
        from_date: Start date (YYYY-MM-DD).
        to_date: End date (YYYY-MM-DD).
        last: Number of days for relative date range.
        has_formula: Whether any formula is present.
        rolling: Rolling window size.
        cumulative: Cumulative analysis mode.
        group_by: Breakdown specification.
        formulas: Resolved Formula objects (for expression validation).
        data_group_id: Optional data group ID for group-level analytics.
            Must be a positive integer if provided. Default: ``None``.

    Returns:
        List of validation errors. Empty list means all arguments are valid.
    """
    errors: list[ValidationError] = []

    # DG1: data_group_id must be positive if provided
    errors.extend(_validate_data_group_id(data_group_id))

    # V0: At least one event required
    if not events:
        errors.append(
            ValidationError(
                path="events",
                message="At least one event is required",
                code="V0_NO_EVENTS",
            )
        )

    # V17/V21/V22: Event validation — type, empty, control chars, invisible
    for idx, item in enumerate(events):
        epath = f"events[{idx}]"

        # V21: Type guard — must be str, Metric, or CohortMetric
        if not isinstance(item, (str, Metric, CohortMetric)):
            errors.append(
                ValidationError(
                    path=epath,
                    message=(
                        f"Event must be a string, Metric, or CohortMetric, "
                        f"got {type(item).__name__}"
                    ),
                    code="V21_INVALID_EVENT_TYPE",
                )
            )
            continue

        # CohortMetric: validate cohort type, then skip event-name validation
        if isinstance(item, CohortMetric):
            # CM5: Inline CohortDefinition in CohortMetric triggers a
            # server-side 500. Only saved cohort IDs are supported.
            if isinstance(item.cohort, CohortDefinition):
                errors.append(
                    ValidationError(
                        path=epath,
                        message=(
                            "CohortMetric does not support inline CohortDefinition "
                            "(server returns 500). Use a saved cohort ID instead."
                        ),
                        code="CM5_INLINE_COHORT_METRIC",
                    )
                )
            continue

        name = item.event if isinstance(item, Metric) else item

        # V17: Non-empty after stripping whitespace
        if not name.strip():
            errors.append(
                ValidationError(
                    path=epath,
                    message="Event name must be a non-empty string",
                    code="V17_EMPTY_EVENT",
                )
            )
            continue

        # V22a: No control characters (null bytes, etc.)
        if _CONTROL_CHAR_RE.search(name):
            errors.append(
                ValidationError(
                    path=epath,
                    message=(
                        f"Event name contains control characters "
                        f"(e.g. null bytes): {name!r}"
                    ),
                    code="V22_CONTROL_CHAR_EVENT",
                )
            )

        # V22b: No invisible-only names (zero-width spaces, etc.)
        if _INVISIBLE_RE.match(name):
            errors.append(
                ValidationError(
                    path=epath,
                    message="Event name contains only invisible characters",
                    code="V22_INVISIBLE_EVENT",
                )
            )

    # CM3/FR-020: Top-level math/math_property/per_user only apply to plain
    # string events.  When all events are CohortMetric (or Metric, which
    # carries its own math), there are no consumers — skip V1/V2/V3/V26/V27.
    has_plain_events = any(isinstance(item, str) for item in events)

    # V1: Property math requires property
    if has_plain_events and math in MATH_REQUIRING_PROPERTY and math_property is None:
        errors.append(
            ValidationError(
                path="math",
                message=f"math='{math}' requires math_property to be set",
                code="V1_MATH_REQUIRES_PROPERTY",
            )
        )

    # V2: Non-property math rejects property
    if has_plain_events and (
        math not in MATH_REQUIRING_PROPERTY
        and math not in MATH_PROPERTY_OPTIONAL
        and math_property is not None
    ):
        valid = sorted(MATH_REQUIRING_PROPERTY | MATH_PROPERTY_OPTIONAL)
        errors.append(
            ValidationError(
                path="math_property",
                message=(
                    f"math_property is only valid with property-based math types "
                    f"({', '.join(valid)}), not '{math}'"
                ),
                code="V2_MATH_REJECTS_PROPERTY",
            )
        )

    # V26: percentile math requires percentile_value
    if has_plain_events and math == "percentile" and percentile_value is None:
        errors.append(
            ValidationError(
                path="percentile_value",
                message=("math='percentile' requires percentile_value to be set"),
                code="V26_PERCENTILE_REQUIRES_VALUE",
            )
        )

    # V27: histogram math requires per_user
    if has_plain_events and math == "histogram" and per_user is None:
        errors.append(
            ValidationError(
                path="per_user",
                message=(
                    "math='histogram' requires per_user to be set "
                    "(e.g. per_user='total')"
                ),
                code="V27_HISTOGRAM_REQUIRES_PER_USER",
            )
        )

    # V3: per_user incompatible with DAU/WAU/MAU/unique
    if has_plain_events and per_user is not None and math in MATH_NO_PER_USER:
        errors.append(
            ValidationError(
                path="per_user",
                message=f"per_user is incompatible with math='{math}'",
                code="V3_PER_USER_INCOMPATIBLE",
            )
        )

    # V3b: per_user requires a property
    if has_plain_events and per_user is not None and math_property is None:
        errors.append(
            ValidationError(
                path="per_user",
                message="per_user requires math_property to be set",
                code="V3B_PER_USER_REQUIRES_PROPERTY",
            )
        )

    # V4: Formula requires 2+ events
    if has_formula and len(events) < 2:
        errors.append(
            ValidationError(
                path="formula",
                message=f"formula requires at least 2 events (got {len(events)})",
                code="V4_FORMULA_MIN_EVENTS",
            )
        )

    # V16/V19: Formula expression validation
    resolved = formulas or []
    for fi, f in enumerate(resolved):
        if isinstance(f, Formula):
            expr = f.expression
            fpath = f"formula[{fi}]" if len(resolved) > 1 else "formula"

            # V16: Formula must contain at least one position letter
            positions = set(_FORMULA_POSITION_RE.findall(expr))
            if not positions:
                errors.append(
                    ValidationError(
                        path=fpath,
                        message=(
                            f"Formula '{expr}' must reference at least one "
                            f"event position (A, B, C, ...)"
                        ),
                        code="V16_FORMULA_SYNTAX",
                    )
                )

            # V19: Position letters must not exceed event count
            if positions and events:
                max_letter = chr(ord("A") + len(events) - 1)
                out_of_bounds = {p for p in positions if p > max_letter}
                if out_of_bounds:
                    errors.append(
                        ValidationError(
                            path=fpath,
                            message=(
                                f"Formula references position(s) "
                                f"{sorted(out_of_bounds)} but only "
                                f"{len(events)} event(s) defined "
                                f"(A-{max_letter})"
                            ),
                            code="V19_FORMULA_BOUNDS",
                        )
                    )

    # V5: Rolling and cumulative are mutually exclusive
    if rolling is not None and cumulative:
        errors.append(
            ValidationError(
                path="rolling",
                message="rolling and cumulative are mutually exclusive",
                code="V5_ROLLING_CUMULATIVE_EXCLUSIVE",
            )
        )

    # V6: Rolling must be positive
    if rolling is not None and rolling <= 0:
        errors.append(
            ValidationError(
                path="rolling",
                message="rolling must be a positive integer",
                code="V6_ROLLING_POSITIVE",
            )
        )

    # V23: Rolling window sanity cap
    if rolling is not None and rolling > _MAX_ROLLING:
        errors.append(
            ValidationError(
                path="rolling",
                message=(
                    f"rolling={rolling} exceeds maximum of {_MAX_ROLLING} periods"
                ),
                code="V23_ROLLING_TOO_LARGE",
            )
        )

    # V7-V10, V15, V20: Time argument validation (delegated)
    errors.extend(validate_time_args(from_date=from_date, to_date=to_date, last=last))

    # V11-V12, V18, V24: GroupBy validation (delegated)
    errors.extend(validate_group_by_args(group_by=group_by))

    # CP1-CP6: Custom property validation
    errors.extend(
        _scan_custom_properties(
            group_by=group_by,
            where=None,
            events=events,
        )
    )

    # V13-V14: Per-Metric validation
    for idx, item in enumerate(events):
        if isinstance(item, Metric):
            mpath = f"events[{idx}]"
            m_math = item.math
            m_prop = item.property
            m_per_user = item.per_user

            if m_math in MATH_REQUIRING_PROPERTY and m_prop is None:
                errors.append(
                    ValidationError(
                        path=mpath,
                        message=(
                            f"Metric('{item.event}'): math='{m_math}' "
                            f"requires property to be set"
                        ),
                        code="V13_METRIC_MATH_PROPERTY",
                    )
                )

            if (
                m_math not in MATH_REQUIRING_PROPERTY
                and m_math not in MATH_PROPERTY_OPTIONAL
                and m_prop is not None
            ):
                valid = sorted(MATH_REQUIRING_PROPERTY | MATH_PROPERTY_OPTIONAL)
                errors.append(
                    ValidationError(
                        path=mpath,
                        message=(
                            f"Metric('{item.event}'): property is only valid with "
                            f"property-based math types "
                            f"({', '.join(valid)}), not '{m_math}'"
                        ),
                        code="V14_METRIC_REJECTS_PROPERTY",
                    )
                )

            # V27: Per-Metric histogram requires per_user
            if m_math == "histogram" and m_per_user is None:
                errors.append(
                    ValidationError(
                        path=mpath,
                        message=(
                            f"Metric('{item.event}'): math='histogram' "
                            f"requires per_user to be set "
                            f"(e.g. per_user='total')"
                        ),
                        code="V27_HISTOGRAM_REQUIRES_PER_USER",
                    )
                )

            # V26: Per-Metric percentile requires percentile_value
            if m_math == "percentile" and item.percentile_value is None:
                errors.append(
                    ValidationError(
                        path=mpath,
                        message=(
                            f"Metric('{item.event}'): math='percentile' "
                            f"requires percentile_value to be set"
                        ),
                        code="V26_PERCENTILE_REQUIRES_VALUE",
                    )
                )

            if m_per_user is not None and m_math in MATH_NO_PER_USER:
                errors.append(
                    ValidationError(
                        path=mpath,
                        message=(
                            f"Metric('{item.event}'): per_user is incompatible "
                            f"with math='{m_math}'"
                        ),
                        code="V3_PER_USER_INCOMPATIBLE",
                    )
                )

            if m_per_user is not None and m_prop is None:
                errors.append(
                    ValidationError(
                        path=mpath,
                        message=(
                            f"Metric('{item.event}'): per_user requires "
                            f"property to be set"
                        ),
                        code="V3B_PER_USER_REQUIRES_PROPERTY",
                    )
                )

    return errors


# =============================================================================
# Layer 2: Bookmark Structure Validation (B1-B19)
# =============================================================================


def validate_bookmark(
    params: dict[str, Any],
    *,
    bookmark_type: str = "insights",
) -> list[ValidationError]:
    """Validate bookmark params dict after construction (Layer 2).

    Validates the structural integrity and enum values of a built
    bookmark params dict before it is sent to the Mixpanel API.
    Returns all errors found so callers can fix multiple issues at once.

    Args:
        params: The bookmark params dict (with ``sections`` and
            ``displayOptions`` keys).
        bookmark_type: The bookmark type context. Default ``"insights"``.
            Affects which math types are considered valid.

    Returns:
        List of validation errors. Empty list means the bookmark is valid.

    Note:
        Layer 2 hand-written sub-validators emit granular ``B*`` / ``S*``
        codes for the build-path. The sorting subset is now a thin
        wrapper over the Pydantic mirror in ``bookmark_schema`` (single
        source of truth — Layer 1 and Layer 2 cannot drift on sorting).
        The Pydantic mirror is also invoked at the API boundary by
        ``Workspace.create_bookmark`` / ``update_bookmark`` for strict
        1:1 fidelity with Mixpanel's server schema (drift-checked via
        ``scripts/validate_corpus.py``).

    Example:
        ```python
        from mixpanel_data._internal.validation import validate_bookmark

        errors = validate_bookmark(my_params)
        if errors:
            for e in errors:
                print(e)
        ```
    """
    errors: list[ValidationError] = []

    # B1: Required top-level field: sections
    if "sections" not in params:
        errors.append(
            ValidationError(
                path="params",
                message="Missing required field 'sections'",
                code="B1_MISSING_SECTIONS",
            )
        )

    # B2: Required top-level field: displayOptions
    if "displayOptions" not in params:
        errors.append(
            ValidationError(
                path="params",
                message="Missing required field 'displayOptions'",
                code="B2_MISSING_DISPLAY_OPTIONS",
            )
        )

    # Can't validate further without sections
    if "sections" not in params:
        return errors

    sections = params["sections"]
    if not isinstance(sections, dict):
        errors.append(
            ValidationError(
                path="sections",
                message="'sections' must be a dict",
                code="B1_MISSING_SECTIONS",
            )
        )
        return errors

    # B3: Required sections field: show
    show = sections.get("show")
    if show is None:
        errors.append(
            ValidationError(
                path="sections",
                message="Missing required field 'show'",
                code="B3_MISSING_SHOW",
            )
        )
    elif not isinstance(show, list) or len(show) == 0:
        # B4: show must be non-empty list
        errors.append(
            ValidationError(
                path="sections.show",
                message="'show' must be a non-empty list",
                code="B4_SHOW_EMPTY",
            )
        )
    else:
        for i, clause in enumerate(show):
            errors.extend(_validate_show_clause(clause, i, bookmark_type))

    # Validate displayOptions
    display = params.get("displayOptions")
    if isinstance(display, dict):
        errors.extend(_validate_display_options(display))

    # Validate time section
    time_section = sections.get("time")
    if isinstance(time_section, list):
        for i, t in enumerate(time_section):
            errors.extend(_validate_time_clause(t, i))

    # Validate filter section
    filter_section = sections.get("filter")
    if isinstance(filter_section, list):
        for i, f in enumerate(filter_section):
            errors.extend(_validate_filter_clause(f, f"sections.filter[{i}]"))

    # Validate group section
    group_section = sections.get("group")
    if isinstance(group_section, list):
        for i, g in enumerate(group_section):
            errors.extend(_validate_group_clause(g, i))

    # Validate optional top-level sorting block
    if "sorting" in params:
        errors.extend(validate_sorting_block(params["sorting"]))

    return errors


# =============================================================================
# Layer 2: Sub-validators
# =============================================================================


def _validate_show_clause(
    clause: dict[str, Any],
    index: int,
    bookmark_type: str,
) -> list[ValidationError]:
    """Validate a single sections.show[] entry.

    Handles both multi-metric (behavior+measurement) and formula show clauses.

    Args:
        clause: The show clause dict.
        index: Index in the show array.
        bookmark_type: Context for math type validation.

    Returns:
        List of validation errors for this clause.
    """
    errors: list[ValidationError] = []
    path = f"sections.show[{index}]"

    if not isinstance(clause, dict):
        errors.append(
            ValidationError(
                path=path,
                message="Show clause must be a dict",
                code="B6_MISSING_BEHAVIOR",
            )
        )
        return errors

    # Formula show clause — minimal validation (only for pure formula clauses)
    is_formula = "formula" in clause or clause.get("type") == "formula"
    if is_formula and "behavior" not in clause:
        return errors

    # Multi-metric show clause: requires behavior
    behavior = clause.get("behavior")
    if behavior is None:
        # B6: Missing behavior
        errors.append(
            ValidationError(
                path=path,
                message="Show clause missing 'behavior'",
                code="B6_MISSING_BEHAVIOR",
            )
        )
        return errors

    if not isinstance(behavior, dict):
        errors.append(
            ValidationError(
                path=f"{path}.behavior",
                message="'behavior' must be a dict",
                code="B6_MISSING_BEHAVIOR",
            )
        )
        return errors

    # B7: Validate behavior.type
    btype = behavior.get("type")
    if btype is not None and btype not in VALID_METRIC_TYPES:
        errors.append(
            _enum_error(
                path=f"{path}.behavior.type",
                field="behavior type",
                value=str(btype),
                valid=VALID_METRIC_TYPES,
                code="B7_INVALID_BEHAVIOR_TYPE",
                severity="warning",
            )
        )

    # B8: Event behaviors need a name
    if btype in ("event", "simple", "custom-event"):
        value = behavior.get("value", {})
        has_name = (
            isinstance(value, dict) and value.get("name") is not None
        ) or behavior.get("name") is not None
        if not has_name:
            errors.append(
                ValidationError(
                    path=f"{path}.behavior",
                    message="Event behavior requires a 'name'",
                    code="B8_MISSING_EVENT_NAME",
                    fix={"value": {"name": "<EVENT_NAME>"}},
                )
            )

    # B22-B23: Cohort behavior validation
    if btype == "cohort":
        # B22: Cohort behavior requires positive int id (for saved cohorts)
        cohort_id = behavior.get("id")
        if cohort_id is not None and (not isinstance(cohort_id, int) or cohort_id <= 0):
            errors.append(
                ValidationError(
                    path=f"{path}.behavior.id",
                    message="Cohort behavior id must be a positive integer",
                    code="B22_COHORT_BEHAVIOR_ID",
                )
            )
        # B22b: Cohort behavior must have either id or raw_cohort
        if cohort_id is None and behavior.get("raw_cohort") is None:
            errors.append(
                ValidationError(
                    path=f"{path}.behavior",
                    message="Cohort behavior must have either 'id' (saved cohort) "
                    "or 'raw_cohort' (inline definition)",
                    code="B22_COHORT_MISSING_IDENTIFIER",
                )
            )
        # B23: Cohort behavior resourceType must be "cohorts"
        cohort_rt = behavior.get("resourceType")
        if cohort_rt is not None and cohort_rt != "cohorts":
            errors.append(
                ValidationError(
                    path=f"{path}.behavior.resourceType",
                    message=(
                        f"Cohort behavior resourceType must be 'cohorts' "
                        f"(got '{cohort_rt}')"
                    ),
                    code="B23_COHORT_RESOURCE_TYPE",
                )
            )

    # B19: Validate filtersDeterminer
    fd = behavior.get("filtersDeterminer")
    if fd is not None and fd not in VALID_FILTERS_DETERMINER:
        errors.append(
            _enum_error(
                path=f"{path}.behavior.filtersDeterminer",
                field="filtersDeterminer",
                value=str(fd),
                valid=VALID_FILTERS_DETERMINER,
                code="B19_INVALID_FILTERS_DETERMINER",
                severity="warning",
            )
        )

    # Validate per-metric behavior.filters[]
    bfilters = behavior.get("filters")
    if isinstance(bfilters, list):
        for fi, bf in enumerate(bfilters):
            errors.extend(_validate_filter_clause(bf, f"{path}.behavior.filters[{fi}]"))

    # Validate measurement
    measurement = clause.get("measurement")
    if isinstance(measurement, dict):
        errors.extend(_validate_measurement(measurement, path, bookmark_type))

        # B24: Cohort behavior math must be "unique"
        if btype == "cohort":
            m_math = measurement.get("math")
            if m_math is not None and m_math != "unique":
                errors.append(
                    ValidationError(
                        path=f"{path}.measurement.math",
                        message=(
                            f"Cohort behavior math must be 'unique' (got '{m_math}')"
                        ),
                        code="B24_COHORT_MATH",
                    )
                )

    return errors


def _validate_measurement(
    measurement: dict[str, Any],
    show_path: str,
    bookmark_type: str = "insights",
) -> list[ValidationError]:
    """Validate a measurement block within a show clause.

    Args:
        measurement: The measurement dict.
        show_path: Parent show clause path for error reporting.
        bookmark_type: Context for math type validation. When
            ``"funnels"``, validates against funnel-specific math types;
            defaults to insights math types otherwise.

    Returns:
        List of validation errors for this measurement.
    """
    errors: list[ValidationError] = []
    path = f"{show_path}.measurement"

    # B9: Validate math type (context-dependent for funnel/retention)
    math = measurement.get("math")
    if math is not None:
        if bookmark_type == "funnels":
            valid_math = VALID_MATH_FUNNELS
        elif bookmark_type == "retention":
            valid_math = VALID_MATH_RETENTION
        else:
            valid_math = VALID_MATH_INSIGHTS
        if math not in valid_math:
            errors.append(
                _enum_error(
                    path=f"{path}.math",
                    field="math",
                    value=str(math),
                    valid=valid_math,
                    code="B9_INVALID_MATH",
                )
            )

        # B10: Math requiring property
        if math in MATH_REQUIRING_PROPERTY and measurement.get("property") is None:
            errors.append(
                ValidationError(
                    path=f"{path}.property",
                    message=f"Math type '{math}' requires 'measurement.property'",
                    code="B10_MATH_MISSING_PROPERTY",
                    severity="warning",
                    fix={
                        "name": "<PROPERTY_NAME>",
                        "type": "number",
                        "resourceType": "events",
                    },
                )
            )

    # B11: Validate perUserAggregation
    per_user = measurement.get("perUserAggregation")
    if per_user is not None and per_user not in VALID_PER_USER_AGGREGATIONS:
        errors.append(
            _enum_error(
                path=f"{path}.perUserAggregation",
                field="perUserAggregation",
                value=str(per_user),
                valid=VALID_PER_USER_AGGREGATIONS,
                code="B11_INVALID_PER_USER",
            )
        )

    # Validate measurement.property if present
    prop = measurement.get("property")
    if isinstance(prop, dict):
        prop_type = prop.get("type")
        if prop_type is not None and prop_type not in VALID_PROPERTY_TYPES:
            errors.append(
                _enum_error(
                    path=f"{path}.property.type",
                    field="property type",
                    value=str(prop_type),
                    valid=VALID_PROPERTY_TYPES,
                    code="B17_INVALID_PROPERTY_TYPE",
                    severity="warning",
                )
            )
        prop_rt = prop.get("resourceType")
        if prop_rt is not None and prop_rt not in VALID_RESOURCE_TYPES:
            errors.append(
                _enum_error(
                    path=f"{path}.property.resourceType",
                    field="resourceType",
                    value=str(prop_rt),
                    valid=VALID_RESOURCE_TYPES,
                    code="B16_INVALID_RESOURCE_TYPE",
                    severity="warning",
                )
            )

    return errors


def _validate_display_options(
    display: dict[str, Any],
) -> list[ValidationError]:
    """Validate the displayOptions block.

    Args:
        display: The displayOptions dict.

    Returns:
        List of validation errors.
    """
    errors: list[ValidationError] = []

    # B5: chartType is required and must be valid
    chart_type = display.get("chartType")
    if chart_type is None:
        errors.append(
            ValidationError(
                path="displayOptions",
                message="Missing required 'chartType'",
                code="B5_INVALID_CHART_TYPE",
            )
        )
    elif chart_type not in VALID_CHART_TYPES:
        errors.append(
            _enum_error(
                path="displayOptions.chartType",
                field="chartType",
                value=str(chart_type),
                valid=VALID_CHART_TYPES,
                code="B5_INVALID_CHART_TYPE",
            )
        )

    return errors


def _validate_time_clause(
    clause: Any,
    index: int,
) -> list[ValidationError]:
    """Validate a single sections.time[] entry.

    Args:
        clause: The time clause (expected to be a dict).
        index: Index in the time array.

    Returns:
        List of validation errors for this clause.
    """
    errors: list[ValidationError] = []
    path = f"sections.time[{index}]"

    if not isinstance(clause, dict):
        errors.append(
            ValidationError(
                path=path,
                message="Time clause must be a dict",
                code="B12_INVALID_TIME_UNIT",
            )
        )
        return errors

    # B12: Validate unit
    unit = clause.get("unit")
    if unit is not None and unit not in VALID_TIME_UNITS:
        errors.append(
            _enum_error(
                path=f"{path}.unit",
                field="time unit",
                value=str(unit),
                valid=VALID_TIME_UNITS,
                code="B12_INVALID_TIME_UNIT",
            )
        )

    # B13: Validate dateRangeType
    drt = clause.get("dateRangeType")
    if drt is not None and drt not in {
        "in the last",
        "between",
        "since",
        "on",
        "relative_after",
    }:
        errors.append(
            ValidationError(
                path=f"{path}.dateRangeType",
                message=f"Invalid dateRangeType '{drt}'",
                code="B13_INVALID_DATE_RANGE_TYPE",
                severity="warning",
            )
        )

    return errors


def _validate_filter_clause(
    clause: Any,
    path: str,
) -> list[ValidationError]:
    """Validate a single filter clause.

    Args:
        clause: The filter clause (expected to be a dict).
        path: JSONPath-like location for error reporting.

    Returns:
        List of validation errors for this clause.
    """
    errors: list[ValidationError] = []

    if not isinstance(clause, dict):
        errors.append(
            ValidationError(
                path=path,
                message="Filter clause must be a dict",
                code="B14_INVALID_FILTER_TYPE",
            )
        )
        return errors

    # B18: Must have property identification (value/propertyName or custom property)
    has_property_id = (
        clause.get("value")
        or clause.get("propertyName")
        or (clause.get("customPropertyId") is not None)
        or (clause.get("customProperty") is not None)
    )
    if not has_property_id:
        errors.append(
            ValidationError(
                path=path,
                message=(
                    "Filter missing property identifier "
                    "('value', 'propertyName', 'customPropertyId', "
                    "or 'customProperty')"
                ),
                code="B18_MISSING_FILTER_PROPERTY",
            )
        )

    # B18B: customPropertyId must be a positive integer (defense-in-depth)
    cp_id = clause.get("customPropertyId")
    if cp_id is not None and (
        isinstance(cp_id, bool) or not isinstance(cp_id, int) or cp_id <= 0
    ):
        errors.append(
            ValidationError(
                path=f"{path}.customPropertyId",
                message=(f"customPropertyId must be a positive integer (got {cp_id})"),
                code="B18B_INVALID_CP_ID",
            )
        )

    # B16: Validate resourceType
    rt = clause.get("resourceType")
    if rt is not None and rt not in VALID_RESOURCE_TYPES:
        errors.append(
            _enum_error(
                path=f"{path}.resourceType",
                field="resourceType",
                value=str(rt),
                valid=VALID_RESOURCE_TYPES,
                code="B16_INVALID_RESOURCE_TYPE",
                severity="warning",
            )
        )

    # B14: Validate filterType
    ft = clause.get("filterType")
    if ft is not None and ft not in VALID_PROPERTY_TYPES:
        errors.append(
            _enum_error(
                path=f"{path}.filterType",
                field="filterType",
                value=str(ft),
                valid=VALID_PROPERTY_TYPES,
                code="B14_INVALID_FILTER_TYPE",
            )
        )

    # B15: Validate filterOperator
    fo = clause.get("filterOperator")
    if fo is not None and fo not in VALID_FILTER_OPERATORS:
        errors.append(
            _enum_error(
                path=f"{path}.filterOperator",
                field="filterOperator",
                value=str(fo),
                valid=VALID_FILTER_OPERATORS,
                code="B15_INVALID_FILTER_OPERATOR",
                severity="warning",
            )
        )

    # B25: Cohort filter must have value == "$cohorts"
    if clause.get("filterType") == "list" and clause.get("filterOperator") in (
        "contains",
        "does not contain",
    ):
        fv_cohort = clause.get("filterValue")
        if isinstance(fv_cohort, list) and len(fv_cohort) > 0:
            first = fv_cohort[0]
            if (
                isinstance(first, dict)
                and "cohort" in first
                and clause.get("value") != "$cohorts"
            ):
                errors.append(
                    ValidationError(
                        path=f"{path}.value",
                        message=("Cohort filter value must be '$cohorts'"),
                        code="B25_COHORT_FILTER_VALUE",
                    )
                )

    # B20: Validate filterValue is non-empty when present
    fv = clause.get("filterValue")
    if isinstance(fv, list) and len(fv) == 0:
        errors.append(
            ValidationError(
                path=f"{path}.filterValue",
                message="filterValue must not be an empty list",
                code="B20_EMPTY_FILTER_VALUE",
            )
        )

    # B21: Validate filterValue list length
    if isinstance(fv, list) and len(fv) > _MAX_FILTER_VALUES:
        errors.append(
            ValidationError(
                path=f"{path}.filterValue",
                message=(
                    f"filterValue has {len(fv)} entries, "
                    f"maximum is {_MAX_FILTER_VALUES}"
                ),
                code="B21_FILTER_VALUE_TOO_MANY",
            )
        )

    # B20B: Numeric filter values must be finite (not NaN/Inf)
    if isinstance(fv, float) and not _is_finite(fv):
        errors.append(
            ValidationError(
                path=f"{path}.filterValue",
                message=f"filterValue must be a finite number (got {fv})",
                code="B20B_FILTER_VALUE_NOT_FINITE",
            )
        )
    elif isinstance(fv, list):
        for vi, v in enumerate(fv):
            if isinstance(v, float) and not _is_finite(v):
                errors.append(
                    ValidationError(
                        path=f"{path}.filterValue[{vi}]",
                        message=(f"filterValue must be a finite number (got {v})"),
                        code="B20B_FILTER_VALUE_NOT_FINITE",
                    )
                )

    return errors


def _validate_group_clause(
    clause: Any,
    index: int,
) -> list[ValidationError]:
    """Validate a single sections.group[] entry.

    Args:
        clause: The group clause (expected to be a dict).
        index: Index in the group array.

    Returns:
        List of validation errors for this clause.
    """
    errors: list[ValidationError] = []
    path = f"sections.group[{index}]"

    if not isinstance(clause, dict):
        errors.append(
            ValidationError(
                path=path,
                message="Group clause must be a dict",
                code="B17_INVALID_PROPERTY_TYPE",
            )
        )
        return errors

    # B17: Validate propertyType
    pt = clause.get("propertyType")
    if pt is not None and pt not in VALID_PROPERTY_TYPES:
        errors.append(
            _enum_error(
                path=f"{path}.propertyType",
                field="propertyType",
                value=str(pt),
                valid=VALID_PROPERTY_TYPES,
                code="B17_INVALID_PROPERTY_TYPE",
                severity="warning",
            )
        )

    # B16: Validate resourceType
    rt = clause.get("resourceType")
    if rt is not None and rt not in VALID_RESOURCE_TYPES:
        errors.append(
            _enum_error(
                path=f"{path}.resourceType",
                field="resourceType",
                value=str(rt),
                valid=VALID_RESOURCE_TYPES,
                code="B16_INVALID_RESOURCE_TYPE",
                severity="warning",
            )
        )

    # B26: Cohort group entry must have non-empty cohorts array
    cohorts = clause.get("cohorts")
    if cohorts is not None and (not isinstance(cohorts, list) or len(cohorts) == 0):
        errors.append(
            ValidationError(
                path=f"{path}.cohorts",
                message="Cohort group entry must have non-empty cohorts array",
                code="B26_EMPTY_COHORTS",
            )
        )

    return errors


# =============================================================================
# Layer 2: sorting block validator
#
# This is now a thin wrapper over the Pydantic mirror in bookmark_schema:
# the FlatOrColumnSortConfig discriminator + extra="forbid" do all the
# structural work. The wrapper adds two things on top:
#
#   1. S4_UNKNOWN_CHART_TYPE warnings (Pydantic would emit an error for
#      unknown chart-type keys; we want a warning + suggestion instead).
#   2. The S* code translation (via _sorting_code_mapper in bookmark_schema).
#
# By construction, validation here cannot drift from the canonical mirror.
# =============================================================================


def validate_sorting_block(sorting: Any) -> list[ValidationError]:
    """Validate the optional ``params['sorting']`` block.

    Wraps ``validate_with_pydantic(InsightsBookmarkSortConfig, ...)``
    with a sorting-aware code mapper that recovers the package's stable
    ``S*`` codes. Unknown chart-type keys are filtered out and reported
    as ``S4_UNKNOWN_CHART_TYPE`` warnings (rather than ``extra_forbidden``
    errors) so callers can keep producing best-effort output for partial
    chart-type coverage.

    Args:
        sorting: The raw value at ``params['sorting']``. May be any type;
            this function reports a structural error if it is not a dict.

    Returns:
        List of validation errors. Empty when the block is well-formed
        (or omitted at the call site — callers gate on key presence).
    """
    if not isinstance(sorting, dict):
        return [
            ValidationError(
                path="sorting",
                message="'sorting' must be a dict",
                code="S5_NOT_A_DICT",
            )
        ]

    errors: list[ValidationError] = []
    known: dict[str, Any] = {}
    for chart_type, config in sorting.items():
        if chart_type not in VALID_CHART_TYPES:
            errors.append(
                _enum_error(
                    path=f"sorting.{chart_type}",
                    field="chart type",
                    value=str(chart_type),
                    valid=VALID_CHART_TYPES,
                    code="S4_UNKNOWN_CHART_TYPE",
                    severity="warning",
                )
            )
        else:
            known[chart_type] = config

    if known:
        errors.extend(
            validate_with_pydantic(
                InsightsBookmarkSortConfig,
                known,
                path_prefix="sorting",
                code_mapper=_sorting_code_mapper,
            )
        )

    return errors
