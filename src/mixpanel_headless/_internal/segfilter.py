"""Filter-to-segfilter conversion for flows step filters.

Converts ``Filter`` objects from the public types module into the legacy
segfilter dict format consumed by the Mixpanel flows API. Each segfilter
entry encodes a property constraint with type-specific operator and operand
encoding.

The segfilter format differs from the bookmark filter format in operator
names, value encoding (e.g. stringified numbers, MM/DD/YYYY dates), and
structural layout (nested ``property``/``filter`` dicts).

Example:
    ```python
    from mixpanel_headless.types import Filter
    from mixpanel_headless._internal.segfilter import build_segfilter_entry

    f = Filter.equals("country", "US")
    entry = build_segfilter_entry(f)
    # {
    #     "property": {"name": "country", "source": "properties", "type": "string"},
    #     "type": "string",
    #     "selected_property_type": "string",
    #     "filter": {"operator": "==", "operand": ["US"]},
    # }
    ```
"""

from __future__ import annotations

from typing import Any

from mixpanel_headless.types import Filter

# =============================================================================
# Constants
# =============================================================================

RESOURCE_TYPE_MAP: dict[str, str] = {
    "events": "properties",
    "people": "user",
    "cohorts": "cohort",
    "other": "other",
}
"""Maps ``Filter._resource_type`` to segfilter ``property.source``."""

STRING_OPERATOR_MAP: dict[str, str] = {
    "equals": "==",
    "does not equal": "!=",
    "contains": "in",
    "does not contain": "not in",
    "is set": "set",
    "is not set": "not set",
}
"""Maps string-typed Filter operators to segfilter operators."""

NUMBER_OPERATOR_MAP: dict[str, str] = {
    "is greater than": ">",
    "is less than": "<",
    "is equal to": "==",
    "equals": "==",
    "does not equal": "!=",
    "is at least": ">=",
    "is at most": "<=",
    "is between": "><",
    "between": "><",
    "not between": "!><",
    "is set": "is set",
    "is not set": "is not set",
}
"""Maps number-typed Filter operators to segfilter operators."""

DATETIME_OPERATOR_MAP: dict[str, str] = {
    "was on": "==",
    "was not on": "!=",
    # Segfilter operators describe the operand's relation to matching values,
    # not the event's relation to the operand. So "was before <date>" becomes
    # ">" because the operand date is greater than the matching event dates.
    "was before": ">",
    "was since": "<",
    "was in the": ">",
    "was not in the": ">",
    "was between": "><",
    "was not between": "!><",
}
"""Maps datetime-typed Filter operators to segfilter operators."""

# Operators that take no value (set/unset checks) — shared across string and number types
_SETNESS_OPS: frozenset[str] = frozenset({"is set", "is not set"})

# Number operators that take a two-element list
_NUMBER_RANGE_OPS: frozenset[str] = frozenset({"is between", "between", "not between"})

# Datetime operators that use relative time (quantity + unit)
_DATETIME_RELATIVE_OPS: frozenset[str] = frozenset({"was in the", "was not in the"})

# Datetime operators that take a two-date range
_DATETIME_RANGE_OPS: frozenset[str] = frozenset({"was between", "was not between"})


# =============================================================================
# Helpers
# =============================================================================


def _convert_date_format(date_str: str) -> str:
    """Convert a date string from YYYY-MM-DD to MM/DD/YYYY format.

    Args:
        date_str: Date in YYYY-MM-DD format (e.g. ``"2026-01-15"``).

    Returns:
        Date in MM/DD/YYYY format (e.g. ``"01/15/2026"``).

    Example:
        ```python
        _convert_date_format("2026-01-15")
        # "01/15/2026"
        ```
    """
    year, month, day = date_str.split("-")
    return f"{month.zfill(2)}/{day.zfill(2)}/{year}"


# =============================================================================
# Type-specific filter builders
# =============================================================================


def _build_string_filter(operator: str, value: Any) -> dict[str, Any]:
    """Build the ``filter`` dict for a string-typed property.

    Args:
        operator: The ``Filter._operator`` value (e.g. ``"equals"``).
        value: The ``Filter._value`` (list, str, or None).

    Returns:
        Dict with ``operator`` and ``operand`` keys.

    Raises:
        ValueError: If ``operator`` is not in ``STRING_OPERATOR_MAP``.
    """
    if operator not in STRING_OPERATOR_MAP:
        raise ValueError(
            f"Unknown string operator '{operator}'. "
            f"Valid operators: {sorted(STRING_OPERATOR_MAP)}"
        )

    seg_op = STRING_OPERATOR_MAP[operator]

    if operator in _SETNESS_OPS:
        operand: Any = ""
    else:
        operand = value

    return {"operator": seg_op, "operand": operand}


def _build_number_filter(operator: str, value: Any) -> dict[str, Any]:
    """Build the ``filter`` dict for a number-typed property.

    Args:
        operator: The ``Filter._operator`` value (e.g. ``"is greater than"``).
        value: The ``Filter._value`` (numeric, list, or None).

    Returns:
        Dict with ``operator`` and ``operand`` keys.

    Raises:
        ValueError: If ``operator`` is not in ``NUMBER_OPERATOR_MAP``.
    """
    if operator not in NUMBER_OPERATOR_MAP:
        raise ValueError(
            f"Unknown number operator '{operator}'. "
            f"Valid operators: {sorted(NUMBER_OPERATOR_MAP)}"
        )

    seg_op = NUMBER_OPERATOR_MAP[operator]

    if operator in _SETNESS_OPS:
        operand: Any = ""
    elif operator in _NUMBER_RANGE_OPS:
        operand = [str(v) for v in value]
    else:
        operand = str(value)

    return {"operator": seg_op, "operand": operand}


def _build_boolean_filter(operator: str) -> dict[str, Any]:
    """Build the ``filter`` dict for a boolean-typed property.

    Boolean segfilters have NO ``operator`` key -- only ``operand``.

    Args:
        operator: The ``Filter._operator`` value (``"true"`` or ``"false"``).

    Returns:
        Dict with only an ``operand`` key (no ``operator``).
    """
    return {"operand": operator}


def _build_datetime_filter(
    operator: str, value: Any, date_unit: str | None
) -> dict[str, Any]:
    """Build the ``filter`` dict for a datetime-typed property.

    Handles three date sub-types:
    - Absolute single date: operand is MM/DD/YYYY string
    - Absolute date range: operand is [MM/DD/YYYY, MM/DD/YYYY] list
    - Relative date: operand is integer quantity, plus ``unit`` key

    Args:
        operator: The ``Filter._operator`` value (e.g. ``"was on"``).
        value: The ``Filter._value`` (date string, list of date strings,
            or integer quantity for relative dates).
        date_unit: The ``Filter._date_unit`` (e.g. ``"day"``), or ``None``
            for absolute date filters.

    Returns:
        Dict with ``operator``, ``operand``, and optionally ``unit`` keys.

    Raises:
        ValueError: If ``operator`` is not in ``DATETIME_OPERATOR_MAP``.
    """
    if operator not in DATETIME_OPERATOR_MAP:
        raise ValueError(
            f"Unknown datetime operator '{operator}'. "
            f"Valid operators: {sorted(DATETIME_OPERATOR_MAP)}"
        )

    seg_op = DATETIME_OPERATOR_MAP[operator]
    result: dict[str, Any] = {"operator": seg_op}

    if operator in _DATETIME_RELATIVE_OPS:
        result["operand"] = value
        if date_unit is not None:
            result["unit"] = f"{date_unit}s"
    elif operator in _DATETIME_RANGE_OPS:
        result["operand"] = [_convert_date_format(d) for d in value]
    else:
        result["operand"] = _convert_date_format(str(value))

    return result


# =============================================================================
# Public API
# =============================================================================


def build_segfilter_entry(f: Filter) -> dict[str, Any]:
    """Convert a Filter to segfilter format for flows step filters.

    Transforms a typed ``Filter`` object into the legacy segfilter dict
    structure expected by the Mixpanel flows API. The output structure
    includes property metadata, type information, and a filter dict
    with type-specific operator/operand encoding.

    Args:
        f: A ``Filter`` instance created via one of its class methods
            (e.g. ``Filter.equals()``, ``Filter.greater_than()``).

    Returns:
        A dict with the segfilter structure:

        - ``property``: dict with ``name``, ``source``, ``type``
        - ``type``: property type string
        - ``selected_property_type``: property type string (same as ``type``)
        - ``filter``: dict with ``operator``/``operand`` (and optionally ``unit``)

    Raises:
        ValueError: If the filter's property type or operator is not
            recognized.

    Example:
        ```python
        from mixpanel_headless.types import Filter
        from mixpanel_headless._internal.segfilter import build_segfilter_entry

        f = Filter.equals("country", "US")
        entry = build_segfilter_entry(f)
        assert entry["filter"]["operator"] == "=="
        assert entry["filter"]["operand"] == ["US"]
        ```
    """
    prop_type = f._property_type
    source = RESOURCE_TYPE_MAP.get(f._resource_type, f._resource_type)

    if prop_type == "string":
        filter_dict = _build_string_filter(f._operator, f._value)
    elif prop_type == "number":
        filter_dict = _build_number_filter(f._operator, f._value)
    elif prop_type == "boolean":
        filter_dict = _build_boolean_filter(f._operator)
    elif prop_type == "datetime":
        filter_dict = _build_datetime_filter(f._operator, f._value, f._date_unit)
    else:
        raise ValueError(
            f"Unsupported property type '{prop_type}'. "
            f"Supported types: string, number, boolean, datetime"
        )

    return {
        "property": {
            "name": f._property,
            "source": source,
            "type": prop_type,
        },
        "type": prop_type,
        "selected_property_type": prop_type,
        "filter": filter_dict,
    }
