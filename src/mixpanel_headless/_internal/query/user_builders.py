"""Filter-to-selector translation for the Engage API.

Converts ``Filter`` objects to engage API selector strings. This is the
third translation path alongside ``bookmark_builders.build_filter_entry()``
(bookmark dicts for insights/funnels/retention) and
``segfilter.build_segfilter_entry()`` (segfilter entries for flows).

The engage API uses selector strings like ``properties["plan"] == "premium"``
rather than bookmark filter dicts or segfilter entries.

Functions:
    filter_to_selector: Convert a single Filter to a selector string.
    filters_to_selector: Convert multiple Filters to an AND-combined selector.
    extract_cohort_filter: Extract cohort filter from a Filter list.
"""

from __future__ import annotations

import logging

from mixpanel_headless.types import Filter

logger = logging.getLogger(__name__)


def _format_value(value: str | int | float) -> str:
    """Format a scalar value for use in a selector expression.

    Strings are wrapped in double quotes (with internal quotes escaped).
    Numbers are rendered without quotes.

    Args:
        value: The scalar value to format.

    Returns:
        Formatted string suitable for embedding in a selector expression.
    """
    if isinstance(value, str):
        escaped = value.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'
    return str(value)


def _prop_ref(f: Filter) -> str:
    """Build the ``properties["name"]`` reference for a Filter.

    Args:
        f: Filter whose property name to reference.

    Returns:
        String of the form ``properties["<name>"]``.
    """
    if not isinstance(f._property, str):
        raise ValueError(
            f"Engage selector requires a string property name, "
            f"got {type(f._property).__name__}. Custom properties "
            f"are not supported in query_user() filters."
        )
    escaped = f._property.replace("\\", "\\\\").replace('"', '\\"')
    return f'properties["{escaped}"]'


def _is_cohort_filter(f: Filter) -> bool:
    """Return True if *f* is a cohort filter (in_cohort / not_in_cohort).

    Cohort filters store their value as a list of dicts (from
    ``CohortDefinition.to_dict()``), unlike regular filters which use
    str, number, list-of-str, or None. This shape heuristic is safe
    because ``Filter`` only produces list-of-dict values for
    ``in_cohort()`` / ``not_in_cohort()``.

    Args:
        f: Filter to test.

    Returns:
        True when the filter's ``_value`` is a non-empty list of dicts.
    """
    val = f._value
    return isinstance(val, list) and len(val) > 0 and isinstance(val[0], dict)


def filter_to_selector(f: Filter) -> str:
    """Convert a single Filter to an engage API selector string.

    Translates the Filter's internal operator to the equivalent engage
    selector syntax. Each operator maps to a specific selector pattern.

    Args:
        f: A Filter object (constructed via class methods like
            ``Filter.equals()``, ``Filter.greater_than()``, etc.).

    Returns:
        Selector string for the engage API ``where`` parameter.

    Raises:
        ValueError: If the Filter has an unsupported operator.

    Example:
        ```python
        from mixpanel_headless.types import Filter
        from mixpanel_headless._internal.query.user_builders import filter_to_selector

        selector = filter_to_selector(Filter.equals("plan", "premium"))
        # 'properties["plan"] == "premium"'
        ```
    """
    op = f._operator
    prop = _prop_ref(f)
    value = f._value

    if op == "equals":
        if not isinstance(value, list):
            raise ValueError(
                f"Expected list for 'equals' operator, got {type(value).__name__}"
            )
        parts = [
            f"{prop} == {_format_value(v)}"
            for v in value
            if isinstance(v, (str, int, float))
        ]
        dropped = [v for v in value if not isinstance(v, (str, int, float))]
        if dropped:
            logger.warning(
                "Filter.equals() dropped %d non-scalar value(s): %r",
                len(dropped),
                dropped,
            )
        if not parts:
            raise ValueError(
                f"Filter.equals() produced no valid selector terms. "
                f"All values were non-scalar: {value!r}"
            )
        if len(parts) > 1:
            return f"({' or '.join(parts)})"
        return parts[0]

    if op == "does not equal":
        if not isinstance(value, list):
            raise ValueError(
                f"Expected list for 'does not equal' operator, got {type(value).__name__}"
            )
        parts = [
            f"{prop} != {_format_value(v)}"
            for v in value
            if isinstance(v, (str, int, float))
        ]
        dropped = [v for v in value if not isinstance(v, (str, int, float))]
        if dropped:
            logger.warning(
                "Filter.not_equals() dropped %d non-scalar value(s): %r",
                len(dropped),
                dropped,
            )
        if not parts:
            raise ValueError(
                f"Filter.not_equals() produced no valid selector terms. "
                f"All values were non-scalar: {value!r}"
            )
        # AND-combine: "!= a AND != b" means "not in [a, b]"
        # (contrast: equals uses OR — "== a OR == b" means "in [a, b]")
        return " and ".join(parts)

    if op == "contains":
        if not isinstance(value, str):
            raise ValueError(
                f"Expected str for 'contains' operator, got {type(value).__name__}"
            )
        return f"{_format_value(value)} in {prop}"

    if op == "does not contain":
        if not isinstance(value, str):
            raise ValueError(
                f"Expected str for 'does not contain' operator, got {type(value).__name__}"
            )
        return f"not {_format_value(value)} in {prop}"

    if op == "is greater than":
        if not isinstance(value, (int, float)):
            raise ValueError(
                f"Expected int or float for 'is greater than' operator, got {type(value).__name__}"
            )
        return f"{prop} > {_format_value(value)}"

    if op == "is less than":
        if not isinstance(value, (int, float)):
            raise ValueError(
                f"Expected int or float for 'is less than' operator, got {type(value).__name__}"
            )
        return f"{prop} < {_format_value(value)}"

    if op == "is between":
        if not isinstance(value, list) or len(value) != 2:
            raise ValueError(
                f"Expected list of length 2 for 'is between' operator, got {type(value).__name__}"
            )
        lo, hi = value[0], value[1]
        if not isinstance(lo, (int, float)):
            raise ValueError(
                f"Expected int or float for lower bound, got {type(lo).__name__}"
            )
        if not isinstance(hi, (int, float)):
            raise ValueError(
                f"Expected int or float for upper bound, got {type(hi).__name__}"
            )
        return f"{prop} >= {_format_value(lo)} and {prop} <= {_format_value(hi)}"

    if op == "is set":
        return f"defined({prop})"

    if op == "is not set":
        return f"not defined({prop})"

    if op == "true":
        return f"{prop} == true"

    if op == "false":
        return f"{prop} == false"

    raise ValueError(f"Unsupported filter operator: {op!r}")


def filters_to_selector(filters: list[Filter]) -> str:
    """Convert multiple Filters to an AND-combined selector string.

    Each Filter is translated individually via ``filter_to_selector()``,
    then combined with `` and `` operators.

    Args:
        filters: List of Filter objects to AND-combine.

    Returns:
        AND-combined selector string. Returns empty string if list is empty.

    Example:
        ```python
        from mixpanel_headless.types import Filter
        from mixpanel_headless._internal.query.user_builders import filters_to_selector

        selector = filters_to_selector([
            Filter.equals("plan", "premium"),
            Filter.is_set("email"),
        ])
        # 'properties["plan"] == "premium" and defined(properties["email"])'
        ```
    """
    if not filters:
        return ""
    return " and ".join(filter_to_selector(f) for f in filters)


def extract_cohort_filter(
    filters: list[Filter],
) -> tuple[list[Filter], Filter | None]:
    """Extract a cohort filter from a list of Filters.

    Separates ``Filter.in_cohort()`` entries from regular property filters.
    At most one cohort filter is expected (validated by U13).

    Args:
        filters: List of Filter objects, possibly containing a cohort filter.

    Returns:
        Tuple of (remaining_filters, cohort_filter_or_none).

    Example:
        ```python
        from mixpanel_headless.types import Filter
        from mixpanel_headless._internal.query.user_builders import extract_cohort_filter

        filters = [
            Filter.equals("plan", "premium"),
            Filter.in_cohort(123),
        ]
        remaining, cohort = extract_cohort_filter(filters)
        # remaining = [Filter.equals("plan", "premium")]
        # cohort = Filter.in_cohort(123)
        ```
    """
    remaining: list[Filter] = []
    cohort: Filter | None = None
    for f in filters:
        if _is_cohort_filter(f):
            if cohort is None:
                cohort = f
            else:
                # U13 guarantees at most one cohort filter; extra
                # cohorts stay in remaining as a defensive measure
                logger.warning(
                    "Multiple cohort filters found; first used as cohort, "
                    "extras moved to remaining filters"
                )
                remaining.append(f)
        else:
            remaining.append(f)
    return remaining, cohort
