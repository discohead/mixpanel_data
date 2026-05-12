"""Property-based tests for query-validator delegation and aggregation.

Verifies that ``validate_query_args()`` includes the same time- and
group-by-related validation errors produced by ``validate_time_args()``
and ``validate_group_by_args()`` for the same inputs. These checks
validate wiring between the composed validator and the extracted helpers.
"""

from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from mixpanel_headless._internal.validation import (
    validate_group_by_args,
    validate_query_args,
    validate_time_args,
)
from mixpanel_headless.types import GroupBy

# =============================================================================
# Strategies
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

# GroupBy strategies
property_names = st.text(
    min_size=1, max_size=30, alphabet=st.characters(categories=("L", "N"))
)
property_types: st.SearchStrategy[str] = st.sampled_from(
    ["string", "number", "boolean", "datetime"]
)
bucket_sizes = st.one_of(
    st.none(),
    st.floats(min_value=-10, max_value=100),
    st.just(float("nan")),
    st.just(float("inf")),
)
bucket_bounds = st.one_of(
    st.none(),
    st.floats(min_value=-1000, max_value=1000),
    st.just(float("nan")),
    st.just(float("inf")),
)

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

# GroupBy-related error codes that validate_group_by_args handles
GROUP_ERROR_CODES = frozenset(
    {
        "V11_BUCKET_REQUIRES_SIZE",
        "V12_BUCKET_SIZE_POSITIVE",
        "V12B_BUCKET_REQUIRES_NUMBER",
        "V12C_BUCKET_REQUIRES_BOUNDS",
        "V18_BUCKET_ORDER",
        "V24_BUCKET_NOT_FINITE",
    }
)


# =============================================================================
# Time Validation Equivalence
# =============================================================================


class TestTimeValidationEquivalence:
    """Verify validate_time_args() produces same errors as validate_query_args()."""

    @given(
        from_date=maybe_dates,
        to_date=maybe_dates,
        last=last_values,
    )
    @settings(max_examples=100)
    def test_time_errors_match(
        self,
        from_date: str | None,
        to_date: str | None,
        last: int,
    ) -> None:
        """Time error codes from standalone function match monolithic function.

        Args:
            from_date: Start date (may be invalid).
            to_date: End date (may be invalid).
            last: Days for relative range (may be invalid).
        """
        # Get errors from standalone function
        standalone_errors = validate_time_args(
            from_date=from_date,
            to_date=to_date,
            last=last,
        )
        standalone_codes = {e.code for e in standalone_errors}

        # Get errors from monolithic function (only time-related)
        monolithic_errors = validate_query_args(
            events=["TestEvent"],
            math="total",
            math_property=None,
            per_user=None,
            from_date=from_date,
            to_date=to_date,
            last=last,
            has_formula=False,
            rolling=None,
            cumulative=False,
            group_by=None,
        )
        monolithic_time_codes = {
            e.code for e in monolithic_errors if e.code in TIME_ERROR_CODES
        }

        assert standalone_codes == monolithic_time_codes, (
            f"Mismatch for from_date={from_date!r}, to_date={to_date!r}, "
            f"last={last}: standalone={standalone_codes}, "
            f"monolithic={monolithic_time_codes}"
        )


# =============================================================================
# GroupBy Validation Equivalence
# =============================================================================


class TestGroupByValidationEquivalence:
    """Verify validate_group_by_args() produces same errors as validate_query_args()."""

    @given(
        prop=property_names,
        prop_type=property_types,
        bucket_size=bucket_sizes,
        bucket_min=bucket_bounds,
        bucket_max=bucket_bounds,
    )
    @settings(max_examples=100)
    def test_groupby_errors_match(
        self,
        prop: str,
        prop_type: str,
        bucket_size: float | None,
        bucket_min: float | None,
        bucket_max: float | None,
    ) -> None:
        """GroupBy error codes from standalone function match monolithic function.

        Inputs that violate __post_init__ constraints (bucket_size <= 0,
        bucket_min >= bucket_max) are expected to raise ValueError at
        construction time and are verified separately.

        Args:
            prop: Property name.
            prop_type: Property type.
            bucket_size: Bucket size (may be invalid).
            bucket_min: Bucket minimum (may be invalid).
            bucket_max: Bucket maximum (may be invalid).
        """
        try:
            g = GroupBy(
                prop,
                property_type=prop_type,  # type: ignore[arg-type]
                bucket_size=bucket_size,
                bucket_min=bucket_min,
                bucket_max=bucket_max,
            )
        except ValueError:
            # __post_init__ rejected this combination (bucket_size <= 0,
            # bucket_min >= bucket_max, or empty property). These are
            # now caught at construction time, not by the validator.
            return

        # Get errors from standalone function
        standalone_errors = validate_group_by_args(group_by=g)
        standalone_codes = {e.code for e in standalone_errors}

        # Get errors from monolithic function (only groupby-related)
        monolithic_errors = validate_query_args(
            events=["TestEvent"],
            math="total",
            math_property=None,
            per_user=None,
            from_date=None,
            to_date=None,
            last=30,
            has_formula=False,
            rolling=None,
            cumulative=False,
            group_by=g,
        )
        monolithic_group_codes = {
            e.code for e in monolithic_errors if e.code in GROUP_ERROR_CODES
        }

        assert standalone_codes == monolithic_group_codes, (
            f"Mismatch for GroupBy({prop!r}, type={prop_type!r}, "
            f"size={bucket_size}, min={bucket_min}, max={bucket_max}): "
            f"standalone={standalone_codes}, "
            f"monolithic={monolithic_group_codes}"
        )

    def test_none_groupby_no_errors(self) -> None:
        """None group_by produces no errors from standalone function."""
        errors = validate_group_by_args(group_by=None)
        assert errors == []

    def test_string_groupby_no_errors(self) -> None:
        """String group_by produces no errors from standalone function."""
        errors = validate_group_by_args(group_by="country")
        assert errors == []
