"""Property-based tests for validation delegation and cross-validator consistency.

Extends the proven delegation equivalence pattern from
``test_query_validation_pbt.py`` to funnel and retention validators.
Also tests the math/property compatibility matrix exhaustively and
verifies event name validation consistency across all four query types.
"""

from __future__ import annotations

from typing import cast

from hypothesis import given, settings
from hypothesis import strategies as st

from mixpanel_headless._internal.bookmark_enums import (
    MATH_PROPERTY_OPTIONAL,
    MATH_REQUIRING_PROPERTY,
    VALID_MATH_FUNNELS,
    VALID_MATH_INSIGHTS,
)
from mixpanel_headless._internal.validation import (
    validate_flow_args,
    validate_funnel_args,
    validate_query_args,
    validate_retention_args,
    validate_time_args,
)
from mixpanel_headless._literal_types import ConversionWindowUnit, FunnelMathType

# =============================================================================
# Strategies (reused from test_query_validation_pbt.py)
# =============================================================================

# Dates: mix of valid, invalid-format, and edge-case strings
valid_dates = st.from_regex(
    r"20[2-3][0-9]-(0[1-9]|1[0-2])-(0[1-9]|[12][0-9]|3[01])", fullmatch=True
)
invalid_dates = st.sampled_from(
    [
        "01/01/2024",
        "Jan 15 2025",
        "2024-13-01",
        "2024-02-30",
        "not-a-date",
        "",
        "2024/01/01",
    ]
)
maybe_dates = st.one_of(valid_dates, invalid_dates, st.none())
last_values = st.integers(min_value=-100, max_value=5000)

# Time-related error codes that validate_time_args handles
TIME_ERROR_CODES = frozenset(
    {
        "V7_LAST_POSITIVE",
        "V8_DATE_FORMAT",
        "V8_DATE_INVALID",
        "V9_TO_REQUIRES_FROM",
        "V10_DATE_LAST_EXCLUSIVE",
        "V15_DATE_ORDER",
        "V20_LAST_TOO_LARGE",
    }
)

# Control characters as defined by _CONTROL_CHAR_RE in validation.py
_CONTROL_CHARS = (
    [chr(c) for c in range(0x00, 0x09)]
    + ["\x0b", "\x0c"]
    + [chr(c) for c in range(0x0E, 0x20)]
    + ["\x7f"]
)

# Invisible-only characters (from _INVISIBLE_RE)
_INVISIBLE_CHARS = [" ", "\u200b", "\u200c", "\u200d", "\ufeff", "\u00ad", "\u2060"]

# Safe text for prefixes/suffixes (no control chars)
safe_text = st.text(
    max_size=10,
    alphabet=st.characters(categories=("L", "N")),
)

# Math types from the Insights Literal type (MathType)
insights_math_types = st.sampled_from(sorted(VALID_MATH_INSIGHTS))

# Property names for math_property
property_names = st.text(
    alphabet=st.characters(categories=("L", "N")),
    min_size=1,
    max_size=20,
)

# Funnel math types from FunnelMathType Literal
funnel_math_types = st.sampled_from(sorted(VALID_MATH_FUNNELS))


# =============================================================================
# Funnel/Retention Delegation Equivalence
# =============================================================================


class TestFunnelDelegation:
    """Verify validate_funnel_args() delegates time validation correctly."""

    @given(
        from_date=maybe_dates,
        to_date=maybe_dates,
        last=last_values,
    )
    @settings(max_examples=100)
    def test_funnel_time_errors_match(
        self,
        from_date: str | None,
        to_date: str | None,
        last: int,
    ) -> None:
        """Time error codes from standalone match funnel validator.

        Args:
            from_date: Start date (may be invalid).
            to_date: End date (may be invalid).
            last: Days for relative range (may be invalid).
        """
        standalone_errors = validate_time_args(
            from_date=from_date,
            to_date=to_date,
            last=last,
        )
        standalone_codes = {e.code for e in standalone_errors}

        funnel_errors = validate_funnel_args(
            steps=["Signup", "Purchase"],
            conversion_window=14,
            exclusions=None,
            holding_constant=None,
            from_date=from_date,
            to_date=to_date,
            last=last,
            group_by=None,
        )
        funnel_time_codes = {
            e.code for e in funnel_errors if e.code in TIME_ERROR_CODES
        }

        assert standalone_codes == funnel_time_codes, (
            f"Mismatch for from_date={from_date!r}, to_date={to_date!r}, "
            f"last={last}: standalone={standalone_codes}, "
            f"funnel={funnel_time_codes}"
        )


class TestRetentionDelegation:
    """Verify validate_retention_args() delegates time validation correctly."""

    @given(
        from_date=maybe_dates,
        to_date=maybe_dates,
        last=last_values,
    )
    @settings(max_examples=100)
    def test_retention_time_errors_match(
        self,
        from_date: str | None,
        to_date: str | None,
        last: int,
    ) -> None:
        """Time error codes from standalone match retention validator.

        Args:
            from_date: Start date (may be invalid).
            to_date: End date (may be invalid).
            last: Days for relative range (may be invalid).
        """
        standalone_errors = validate_time_args(
            from_date=from_date,
            to_date=to_date,
            last=last,
        )
        standalone_codes = {e.code for e in standalone_errors}

        retention_errors = validate_retention_args(
            born_event="Signup",
            return_event="Login",
            from_date=from_date,
            to_date=to_date,
            last=last,
        )
        retention_time_codes = {
            e.code for e in retention_errors if e.code in TIME_ERROR_CODES
        }

        assert standalone_codes == retention_time_codes, (
            f"Mismatch for from_date={from_date!r}, to_date={to_date!r}, "
            f"last={last}: standalone={standalone_codes}, "
            f"retention={retention_time_codes}"
        )


# =============================================================================
# Math/Property Compatibility Matrix
# =============================================================================


class TestMathPropertyMatrix:
    """Exhaustively test math/property/per_user compatibility rules."""

    @given(
        math=insights_math_types,
        has_property=st.booleans(),
    )
    @settings(max_examples=100)
    def test_insights_math_property_compatibility(
        self,
        math: str,
        has_property: bool,
    ) -> None:
        """V1 fires iff math requires property and none given; V2 fires iff math rejects property and one given.

        Args:
            math: An insights math type from VALID_MATH_INSIGHTS.
            has_property: Whether to provide a math_property.
        """
        math_property = "revenue" if has_property else None

        # Skip percentile/histogram — they have additional constraints
        # beyond math/property compatibility (V26/V27)
        if math in ("percentile", "histogram"):
            return

        errors = validate_query_args(
            events=["TestEvent"],
            math=math,  # type: ignore[arg-type]
            math_property=math_property,
            per_user=None,
            from_date=None,
            to_date=None,
            last=30,
            has_formula=False,
            rolling=None,
            cumulative=False,
            group_by=None,
        )
        codes = {e.code for e in errors}

        # V1: property-requiring math without property
        if math in MATH_REQUIRING_PROPERTY and not has_property:
            assert "V1_MATH_REQUIRES_PROPERTY" in codes, (
                f"math={math!r} requires property but V1 not fired"
            )
        else:
            assert "V1_MATH_REQUIRES_PROPERTY" not in codes, (
                f"V1 should not fire for math={math!r}, has_property={has_property}"
            )

        # V2: non-property math with property
        rejects_property = (
            math not in MATH_REQUIRING_PROPERTY and math not in MATH_PROPERTY_OPTIONAL
        )
        if rejects_property and has_property:
            assert "V2_MATH_REJECTS_PROPERTY" in codes, (
                f"math={math!r} should reject property but V2 not fired"
            )
        else:
            assert "V2_MATH_REJECTS_PROPERTY" not in codes, (
                f"V2 should not fire for math={math!r}, has_property={has_property}"
            )

    @given(
        math=funnel_math_types,
        has_property=st.booleans(),
    )
    @settings(max_examples=100)
    def test_funnel_math_property_compatibility(
        self,
        math: str,
        has_property: bool,
    ) -> None:
        """F10 fires iff math requires property and none given; F11 fires iff math rejects property and one given.

        Args:
            math: A funnel math type from VALID_MATH_FUNNELS.
            has_property: Whether to provide a math_property.
        """
        math_property = "revenue" if has_property else None

        # Handle session math coupling — cast to Literal types for mypy
        cw_unit: ConversionWindowUnit = (
            "session" if math == "conversion_rate_session" else "day"
        )
        funnel_math = cast(FunnelMathType, math)
        cw = 1 if cw_unit == "session" else 14

        errors = validate_funnel_args(
            steps=["Signup", "Purchase"],
            conversion_window=cw,
            conversion_window_unit=cw_unit,
            math=funnel_math,
            math_property=math_property,
            exclusions=None,
            holding_constant=None,
            from_date=None,
            to_date=None,
            last=30,
            group_by=None,
        )
        codes = {e.code for e in errors}

        # F10: property-requiring math without property
        if math in MATH_REQUIRING_PROPERTY and not has_property:
            assert "F10_MATH_MISSING_PROPERTY" in codes, (
                f"funnel math={math!r} requires property but F10 not fired"
            )
        else:
            assert "F10_MATH_MISSING_PROPERTY" not in codes, (
                f"F10 should not fire for math={math!r}, has_property={has_property}"
            )

        # F11: non-property math with property
        rejects_property = (
            math not in MATH_REQUIRING_PROPERTY and math not in MATH_PROPERTY_OPTIONAL
        )
        if rejects_property and has_property:
            assert "F11_MATH_REJECTS_PROPERTY" in codes, (
                f"funnel math={math!r} should reject property but F11 not fired"
            )
        else:
            assert "F11_MATH_REJECTS_PROPERTY" not in codes, (
                f"F11 should not fire for math={math!r}, has_property={has_property}"
            )


# =============================================================================
# Event Name Validation Consistency
# =============================================================================


class TestEventNameConsistency:
    """Verify event name validation is consistent across all four query types.

    All validators (V22, F2, R1/R2, FL2) should detect control characters
    and invisible-only names identically.
    """

    @given(
        prefix=safe_text,
        ctrl=st.sampled_from(_CONTROL_CHARS),
        suffix=safe_text,
    )
    @settings(max_examples=100)
    def test_control_chars_detected_across_validators(
        self,
        prefix: str,
        ctrl: str,
        suffix: str,
    ) -> None:
        """All four validators detect control chars in event names.

        Args:
            prefix: Safe text before the control character.
            ctrl: A single control character.
            suffix: Safe text after the control character.
        """
        name = prefix + ctrl + suffix
        if not name.strip():
            # Empty-after-strip names trigger different rules; skip
            return

        # Insights (V22)
        insights_errors = validate_query_args(
            events=[name],
            math="total",
            math_property=None,
            per_user=None,
            from_date=None,
            to_date=None,
            last=30,
            has_formula=False,
            rolling=None,
            cumulative=False,
            group_by=None,
        )
        insights_codes = {e.code for e in insights_errors}
        assert "V22_CONTROL_CHAR_EVENT" in insights_codes, (
            f"Insights missed control char in {name!r}"
        )

        # Funnel (F2)
        funnel_errors = validate_funnel_args(
            steps=[name, "ValidStep"],
            conversion_window=14,
            exclusions=None,
            holding_constant=None,
            from_date=None,
            to_date=None,
            last=30,
            group_by=None,
        )
        funnel_codes = {e.code for e in funnel_errors}
        assert "F2_CONTROL_CHAR_STEP_EVENT" in funnel_codes, (
            f"Funnel missed control char in {name!r}"
        )

        # Retention born_event (R1)
        retention_errors = validate_retention_args(
            born_event=name,
            return_event="ValidReturn",
        )
        retention_codes = {e.code for e in retention_errors}
        assert "R1_CONTROL_CHAR_BORN_EVENT" in retention_codes, (
            f"Retention missed control char in {name!r}"
        )

        # Flow (FL2)
        flow_errors = validate_flow_args(
            steps=[name],
        )
        flow_codes = {e.code for e in flow_errors}
        assert "FL2_CONTROL_CHAR_STEP_EVENT" in flow_codes, (
            f"Flow missed control char in {name!r}"
        )

    @given(
        chars=st.lists(
            st.sampled_from(_INVISIBLE_CHARS),
            min_size=1,
            max_size=10,
        ),
    )
    @settings(max_examples=100)
    def test_invisible_names_detected_across_validators(
        self,
        chars: list[str],
    ) -> None:
        """All four validators detect invisible-only event names.

        Args:
            chars: List of invisible characters to form the name.
        """
        name = "".join(chars)
        if not name:
            return

        # Insights — invisible-only names that are whitespace-only
        # trigger V17_EMPTY_EVENT (stripped to empty), not V22_INVISIBLE.
        # Only test the name-is-caught property, not the specific code.
        insights_errors = validate_query_args(
            events=[name],
            math="total",
            math_property=None,
            per_user=None,
            from_date=None,
            to_date=None,
            last=30,
            has_formula=False,
            rolling=None,
            cumulative=False,
            group_by=None,
        )
        insights_codes = {e.code for e in insights_errors}
        assert insights_codes & {
            "V17_EMPTY_EVENT",
            "V22_INVISIBLE_EVENT",
        }, f"Insights missed invisible name {name!r}, codes={insights_codes}"

        # Funnel
        funnel_errors = validate_funnel_args(
            steps=[name, "ValidStep"],
            conversion_window=14,
            exclusions=None,
            holding_constant=None,
            from_date=None,
            to_date=None,
            last=30,
            group_by=None,
        )
        funnel_codes = {e.code for e in funnel_errors}
        assert funnel_codes & {
            "F2_EMPTY_STEP_EVENT",
            "F2_INVISIBLE_STEP_EVENT",
        }, f"Funnel missed invisible name {name!r}, codes={funnel_codes}"

        # Retention born_event
        retention_errors = validate_retention_args(
            born_event=name,
            return_event="ValidReturn",
        )
        retention_codes = {e.code for e in retention_errors}
        assert retention_codes & {
            "R1_EMPTY_BORN_EVENT",
            "R1_INVISIBLE_BORN_EVENT",
        }, f"Retention missed invisible name {name!r}, codes={retention_codes}"

        # Flow
        flow_errors = validate_flow_args(
            steps=[name],
        )
        flow_codes = {e.code for e in flow_errors}
        assert flow_codes & {
            "FL2_EMPTY_STEP_EVENT",
            "FL2_INVISIBLE_STEP_EVENT",
        }, f"Flow missed invisible name {name!r}, codes={flow_codes}"
