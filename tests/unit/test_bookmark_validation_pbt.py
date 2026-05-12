"""Property-based tests for Layer 2 bookmark validation enum consistency.

Proves that every valid enum value passes validation and every invalid
value fails, for math types (across insights/funnels/retention contexts),
filter operators, and chart types.

Tests ``validate_bookmark()`` and ``validate_flow_bookmark()`` directly
without going through the builder pipeline.
"""

from __future__ import annotations

from typing import Any

from hypothesis import given, settings
from hypothesis import strategies as st

from mixpanel_headless._internal.bookmark_enums import (
    VALID_CHART_TYPES,
    VALID_FILTER_OPERATORS,
    VALID_MATH_FUNNELS,
    VALID_MATH_INSIGHTS,
    VALID_MATH_RETENTION,
)
from mixpanel_headless._internal.validation import (
    validate_bookmark,
)

# =============================================================================
# Strategies
# =============================================================================

# Arbitrary strings that are NOT in a given enum set
_all_valid_math = VALID_MATH_INSIGHTS | VALID_MATH_FUNNELS | VALID_MATH_RETENTION
invalid_math_strings = st.text(min_size=1, max_size=30).filter(
    lambda s: s not in _all_valid_math
)

invalid_filter_operators = st.text(min_size=1, max_size=30).filter(
    lambda s: s not in VALID_FILTER_OPERATORS
)

invalid_chart_types = st.text(min_size=1, max_size=30).filter(
    lambda s: s not in VALID_CHART_TYPES
)


# =============================================================================
# Helpers
# =============================================================================


def _minimal_bookmark(**overrides: Any) -> dict[str, Any]:
    """Return a minimal valid bookmark params dict with optional overrides.

    Produces a bookmark that passes all B-series rules when unmodified.
    Individual fields can be overridden to test specific validation rules.

    Args:
        **overrides: Keys to override in the top-level bookmark dict.

    Returns:
        Bookmark params dict suitable for ``validate_bookmark()``.
    """
    bookmark: dict[str, Any] = {
        "sections": {
            "show": [
                {
                    "behavior": {
                        "type": "event",
                        "resourceType": "events",
                        "value": {"name": "Login"},
                    },
                    "measurement": {
                        "math": "total",
                    },
                }
            ],
            "time": [{"unit": "day", "dateRangeType": "in the last", "value": 30}],
            "filter": [],
            "group": [],
        },
        "displayOptions": {
            "chartType": "line",
            "analysis": "linear",
        },
    }
    bookmark.update(overrides)
    return bookmark


def _bookmark_with_math(math: str) -> dict[str, Any]:
    """Return a minimal bookmark with the given math type in show[0].measurement.

    Args:
        math: Math type string to set.

    Returns:
        Bookmark params dict with the specified math type.
    """
    bm = _minimal_bookmark()
    bm["sections"]["show"][0]["measurement"]["math"] = math
    return bm


def _bookmark_with_filter(operator: str) -> dict[str, Any]:
    """Return a minimal bookmark with a filter clause using the given operator.

    Args:
        operator: Filter operator string to set.

    Returns:
        Bookmark params dict with the specified filter operator.
    """
    bm = _minimal_bookmark()
    bm["sections"]["filter"] = [
        {
            "filterType": "string",
            "filterOperator": operator,
            "value": "country",
            "filterValue": ["US"],
            "resourceType": "events",
        }
    ]
    return bm


def _bookmark_with_chart_type(chart_type: str) -> dict[str, Any]:
    """Return a minimal bookmark with the given chartType in displayOptions.

    Args:
        chart_type: Chart type string to set.

    Returns:
        Bookmark params dict with the specified chart type.
    """
    bm = _minimal_bookmark()
    bm["displayOptions"]["chartType"] = chart_type
    return bm


# =============================================================================
# Math Type Dispatch
# =============================================================================


class TestMathTypeDispatch:
    """Verify math type enum validation is correct per bookmark context.

    The B9 rule checks math type against a context-dependent enum set:
    ``VALID_MATH_INSIGHTS`` for insights, ``VALID_MATH_FUNNELS`` for funnels,
    ``VALID_MATH_RETENTION`` for retention.
    """

    @given(math=st.sampled_from(sorted(VALID_MATH_INSIGHTS)))
    @settings(max_examples=100)
    def test_insights_valid_math_passes(self, math: str) -> None:
        """Every value in VALID_MATH_INSIGHTS must not produce B9 error.

        Args:
            math: A valid insights math type.
        """
        errors = validate_bookmark(_bookmark_with_math(math), bookmark_type="insights")
        b9_errors = [e for e in errors if e.code == "B9_INVALID_MATH"]
        assert b9_errors == [], (
            f"Valid insights math {math!r} produced B9 error: "
            f"{[e.message for e in b9_errors]}"
        )

    @given(math=invalid_math_strings)
    @settings(max_examples=100)
    def test_insights_invalid_math_fails(self, math: str) -> None:
        """Any string NOT in VALID_MATH_INSIGHTS must produce B9 error.

        Args:
            math: A string not in any valid math set.
        """
        errors = validate_bookmark(_bookmark_with_math(math), bookmark_type="insights")
        b9_codes = {e.code for e in errors}
        assert "B9_INVALID_MATH" in b9_codes, (
            f"Invalid insights math {math!r} should produce B9 error, got {b9_codes}"
        )

    @given(math=st.sampled_from(sorted(VALID_MATH_FUNNELS)))
    @settings(max_examples=100)
    def test_funnel_valid_math_passes(self, math: str) -> None:
        """Every value in VALID_MATH_FUNNELS must not produce B9 error.

        Args:
            math: A valid funnel math type.
        """
        errors = validate_bookmark(_bookmark_with_math(math), bookmark_type="funnels")
        b9_errors = [e for e in errors if e.code == "B9_INVALID_MATH"]
        assert b9_errors == [], (
            f"Valid funnel math {math!r} produced B9 error: "
            f"{[e.message for e in b9_errors]}"
        )

    @given(math=st.sampled_from(sorted(VALID_MATH_RETENTION)))
    @settings(max_examples=100)
    def test_retention_valid_math_passes(self, math: str) -> None:
        """Every value in VALID_MATH_RETENTION must not produce B9 error.

        Args:
            math: A valid retention math type.
        """
        errors = validate_bookmark(_bookmark_with_math(math), bookmark_type="retention")
        b9_errors = [e for e in errors if e.code == "B9_INVALID_MATH"]
        assert b9_errors == [], (
            f"Valid retention math {math!r} produced B9 error: "
            f"{[e.message for e in b9_errors]}"
        )


# =============================================================================
# Filter Enum Consistency
# =============================================================================


class TestFilterEnumConsistency:
    """Verify filter operator enum validation is correct."""

    @given(op=st.sampled_from(sorted(VALID_FILTER_OPERATORS)))
    @settings(max_examples=100)
    def test_valid_filter_operators_pass(self, op: str) -> None:
        """Every operator in VALID_FILTER_OPERATORS must not produce B15 error.

        Args:
            op: A valid filter operator string.
        """
        errors = validate_bookmark(_bookmark_with_filter(op))
        b15_errors = [e for e in errors if e.code == "B15_INVALID_FILTER_OPERATOR"]
        assert b15_errors == [], (
            f"Valid filter operator {op!r} produced B15 error: "
            f"{[e.message for e in b15_errors]}"
        )

    @given(op=invalid_filter_operators)
    @settings(max_examples=100)
    def test_invalid_filter_operators_fail(self, op: str) -> None:
        """Any string NOT in VALID_FILTER_OPERATORS must produce B15 error.

        Args:
            op: An invalid filter operator string.
        """
        errors = validate_bookmark(_bookmark_with_filter(op))
        b15_codes = {e.code for e in errors}
        assert "B15_INVALID_FILTER_OPERATOR" in b15_codes, (
            f"Invalid filter operator {op!r} should produce B15 error, got {b15_codes}"
        )


# =============================================================================
# Chart Type Consistency
# =============================================================================


class TestChartTypeConsistency:
    """Verify chart type enum validation is correct."""

    @given(ct=st.sampled_from(sorted(VALID_CHART_TYPES)))
    @settings(max_examples=100)
    def test_valid_chart_types_pass(self, ct: str) -> None:
        """Every value in VALID_CHART_TYPES must not produce B5 error.

        Args:
            ct: A valid chart type string.
        """
        errors = validate_bookmark(_bookmark_with_chart_type(ct))
        b5_errors = [e for e in errors if e.code == "B5_INVALID_CHART_TYPE"]
        assert b5_errors == [], (
            f"Valid chart type {ct!r} produced B5 error: "
            f"{[e.message for e in b5_errors]}"
        )

    @given(ct=invalid_chart_types)
    @settings(max_examples=100)
    def test_invalid_chart_types_fail(self, ct: str) -> None:
        """Any string NOT in VALID_CHART_TYPES must produce B5 error.

        Args:
            ct: An invalid chart type string.
        """
        errors = validate_bookmark(_bookmark_with_chart_type(ct))
        b5_codes = {e.code for e in errors}
        assert "B5_INVALID_CHART_TYPE" in b5_codes, (
            f"Invalid chart type {ct!r} should produce B5 error, got {b5_codes}"
        )
