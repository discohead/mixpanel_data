"""Expression normalization utilities for Mixpanel filter expressions.

This module provides functions to normalize user input into valid
Mixpanel filter expression syntax. Filter expressions use property
accessor syntax (properties["name"], user["name"], event["name"])
and are distinct from JQL (JavaScript Query Language).
"""

from __future__ import annotations

# Accessor patterns that indicate a full filter expression.
# These are the three accessor types supported by Mixpanel's filter expression syntax.
_FILTER_EXPR_ACCESSORS = ('properties["', 'user["', 'event["')


def normalize_on_expression(on: str) -> str:
    """Wrap bare property names in properties[] accessor syntax.

    The Mixpanel segmentation API requires property references to use
    filter expression syntax (e.g., properties["Source"]). This function
    normalizes bare property names by wrapping them, while passing through
    expressions that already use accessor syntax.

    Args:
        on: The segmentation property expression. Can be a bare property name
            (e.g., "Source") or a full expression (e.g., 'properties["Source"]').

    Returns:
        The normalized expression. Bare names are wrapped in properties["..."],
        while existing expressions pass through unchanged. Double quotes and
        backslashes in bare property names are escaped to produce valid syntax.

    Examples:
        >>> normalize_on_expression("Source")
        'properties["Source"]'
        >>> normalize_on_expression('properties["Source"]')
        'properties["Source"]'
        >>> normalize_on_expression('properties["Type"] == "Event"')
        'properties["Type"] == "Event"'
        >>> normalize_on_expression('my"property')
        'properties["my\\\\"property"]'
    """
    if any(accessor in on for accessor in _FILTER_EXPR_ACCESSORS):
        return on
    # Escape backslashes first, then double quotes, to produce valid syntax.
    # Order matters: escaping quotes first would double-escape the backslash.
    escaped = on.replace("\\", "\\\\").replace('"', '\\"')
    return f'properties["{escaped}"]'
