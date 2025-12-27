"""Property-based tests for Workspace using Hypothesis.

These tests verify invariants that should hold for all possible inputs,
catching edge cases that example-based tests might miss.

Properties tested:
- _try_float: Never raises exceptions, returns float or None
"""

from __future__ import annotations

from typing import Any

from hypothesis import given
from hypothesis import strategies as st

from mixpanel_data.workspace import Workspace

# =============================================================================
# Custom Strategies
# =============================================================================

# Strategy for values that should convert to float
numeric_values = st.one_of(
    st.integers(),
    st.floats(allow_nan=False, allow_infinity=False),
    # String representations of numbers
    st.integers().map(str),
    st.floats(allow_nan=False, allow_infinity=False).map(str),
)

# Strategy for values that should NOT convert to float
non_numeric_values = st.one_of(
    st.none(),
    st.text().filter(lambda s: not _is_numeric_string(s)),
    st.lists(st.integers()),
    st.dictionaries(st.text(), st.integers()),
    st.binary(),
)

# Strategy for any value - tests that _try_float never raises
any_value: st.SearchStrategy[Any] = st.one_of(
    st.none(),
    st.booleans(),
    st.integers(),
    st.floats(),  # includes NaN and Inf
    st.text(),
    st.binary(),
    st.lists(st.integers(), max_size=3),
    st.dictionaries(st.text(), st.integers(), max_size=3),
)


def _is_numeric_string(s: str) -> bool:
    """Check if a string can be converted to float."""
    try:
        float(s)
        return True
    except (ValueError, TypeError):
        return False


# =============================================================================
# _try_float Property Tests
# =============================================================================


class TestTryFloatProperties:
    """Property-based tests for Workspace._try_float method.

    The _try_float method is a safety wrapper used in summarize() to handle
    DuckDB SUMMARIZE output where avg/std columns may contain non-numeric
    values for certain column types (e.g., timestamps).
    """

    @given(value=any_value)
    def test_try_float_never_raises(self, value: Any) -> None:
        """_try_float should never raise an exception for any input.

        This property is critical because _try_float is used to safely
        handle arbitrary values from DuckDB's SUMMARIZE output, which
        may contain non-numeric values for certain column types.

        Args:
            value: Any value that might be passed to _try_float.
        """
        # Should not raise any exception
        result = Workspace._try_float(value)

        # Result should be either float or None
        assert result is None or isinstance(result, float)

    @given(value=st.integers())
    def test_try_float_converts_integers(self, value: int) -> None:
        """_try_float should convert integers to floats.

        Args:
            value: Any integer value.
        """
        result = Workspace._try_float(value)
        assert result == float(value)

    @given(value=st.floats(allow_nan=False, allow_infinity=False))
    def test_try_float_returns_floats_unchanged(self, value: float) -> None:
        """_try_float should return finite floats unchanged.

        Args:
            value: Any finite float value.
        """
        result = Workspace._try_float(value)
        assert result == value

    @given(value=st.none())
    def test_try_float_returns_none_for_none(self, value: None) -> None:
        """_try_float should return None when given None.

        This matches the documented behavior for handling NULL values
        from DuckDB.

        Args:
            value: None.
        """
        result = Workspace._try_float(value)
        assert result is None

    @given(value=st.text().filter(lambda s: not _is_numeric_string(s)))
    def test_try_float_returns_none_for_non_numeric_strings(self, value: str) -> None:
        """_try_float should return None for strings that aren't numbers.

        Args:
            value: A string that cannot be converted to float.
        """
        result = Workspace._try_float(value)
        assert result is None

    @given(value=st.integers().map(str))
    def test_try_float_converts_numeric_strings(self, value: str) -> None:
        """_try_float should convert string representations of numbers.

        Args:
            value: A string representation of an integer.
        """
        result = Workspace._try_float(value)
        assert result == float(value)
