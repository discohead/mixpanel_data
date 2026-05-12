"""Property-based tests for validation engine pure functions.

Verifies invariants of core validation helpers using Hypothesis:

- ``_suggest``: fuzzy matching results are always valid subsets
- ``contains_control_chars``: agrees with reference character-set check
- ``validate_time_args``: well-formed date inputs produce no errors
- ``_validate_custom_property``: CustomPropertyRef boundary behavior
"""

from __future__ import annotations

import re

from hypothesis import given, settings
from hypothesis import strategies as st

from mixpanel_headless._internal.validation import (
    _suggest,
    _validate_custom_property,
    contains_control_chars,
    validate_time_args,
)
from mixpanel_headless.types import (
    CustomPropertyRef,
    InlineCustomProperty,
    PropertyInput,
)

# =============================================================================
# Strategies
# =============================================================================

# Control characters as defined by _CONTROL_CHAR_RE in validation.py
_CONTROL_CHARS = (
    [chr(c) for c in range(0x00, 0x09)]  # \x00-\x08
    + ["\x0b", "\x0c"]  # \x0b, \x0c
    + [chr(c) for c in range(0x0E, 0x20)]  # \x0e-\x1f
    + ["\x7f"]  # DEL
)

# Valid YYYY-MM-DD dates that are real calendar dates
_VALID_YEAR = st.integers(min_value=2000, max_value=2030)
_VALID_MONTH = st.integers(min_value=1, max_value=12)
_VALID_DAY = st.integers(min_value=1, max_value=28)  # 28 always valid

valid_date_strs = st.builds(
    lambda y, m, d: f"{y:04d}-{m:02d}-{d:02d}",
    _VALID_YEAR,
    _VALID_MONTH,
    _VALID_DAY,
)

# Enum-like valid sets for fuzzy matching tests
valid_sets = st.frozensets(
    st.text(min_size=1, max_size=15, alphabet=st.characters(categories=("L", "N"))),
    min_size=1,
    max_size=30,
)

# Arbitrary strings for fuzzy matching queries
query_strings = st.text(min_size=0, max_size=20)

# Single uppercase letter keys for InlineCustomProperty inputs
uppercase_keys = st.from_regex(r"^[A-Z]$", fullmatch=True)

# Non-empty property names for PropertyInput
property_names = st.text(
    min_size=1, max_size=30, alphabet=st.characters(categories=("L", "N"))
)

# Non-whitespace-only formula strings
nonempty_formulas = st.text(min_size=1, max_size=100).filter(lambda s: s.strip())


# =============================================================================
# _suggest invariants
# =============================================================================


class TestSuggestInvariants:
    """Verify fuzzy matching helper always returns valid results."""

    @given(value=query_strings, valid=valid_sets)
    @settings(max_examples=100)
    def test_results_are_subset_of_valid(
        self,
        value: str,
        valid: frozenset[str],
    ) -> None:
        """Every suggestion must be a member of the valid set.

        Args:
            value: The query string to match against.
            valid: The set of valid values.
        """
        result = _suggest(value, valid)
        if result is not None:
            assert set(result) <= valid, (
                f"Suggestions {result} not subset of valid {valid}"
            )

    @given(
        value=query_strings, valid=valid_sets, n=st.integers(min_value=1, max_value=10)
    )
    @settings(max_examples=100)
    def test_result_length_bounded_by_n(
        self,
        value: str,
        valid: frozenset[str],
        n: int,
    ) -> None:
        """Result tuple length must never exceed n.

        Args:
            value: The query string to match against.
            valid: The set of valid values.
            n: Maximum number of suggestions.
        """
        result = _suggest(value, valid, n=n)
        if result is not None:
            assert len(result) <= n, f"Got {len(result)} suggestions but n={n}"

    @given(valid=valid_sets)
    @settings(max_examples=100)
    def test_exact_match_always_found(
        self,
        valid: frozenset[str],
    ) -> None:
        """An exact match must always appear in suggestions.

        Args:
            valid: The set of valid values (one is picked as the query).
        """
        # Pick an element from the valid set as the query
        value = sorted(valid)[0]
        result = _suggest(value, valid)
        assert result is not None, f"Exact match {value!r} not found in {valid}"
        assert value in result, (
            f"Exact match {value!r} missing from suggestions {result}"
        )


# =============================================================================
# contains_control_chars reference implementation
# =============================================================================

_CONTROL_CHAR_RE_REF = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


class TestContainsControlChars:
    """Verify regex-based function agrees with reference implementation."""

    @given(s=st.text(max_size=100))
    @settings(max_examples=100)
    def test_agrees_with_reference(self, s: str) -> None:
        """contains_control_chars must agree with direct regex search.

        This is a metamorphic property: two implementations of the same
        specification must produce identical results for all inputs.

        Args:
            s: Arbitrary unicode string.
        """
        expected = bool(_CONTROL_CHAR_RE_REF.search(s))
        assert contains_control_chars(s) == expected, (
            f"Disagreement on {s!r}: function={contains_control_chars(s)}, "
            f"reference={expected}"
        )

    @given(
        prefix=st.text(max_size=20, alphabet=st.characters(categories=("L", "N", "P"))),
        ctrl=st.sampled_from(_CONTROL_CHARS),
        suffix=st.text(max_size=20, alphabet=st.characters(categories=("L", "N", "P"))),
    )
    @settings(max_examples=100)
    def test_detects_embedded_control_chars(
        self, prefix: str, ctrl: str, suffix: str
    ) -> None:
        """A string with any embedded control character must be detected.

        Args:
            prefix: Safe text before the control character.
            ctrl: A single control character.
            suffix: Safe text after the control character.
        """
        s = prefix + ctrl + suffix
        assert contains_control_chars(s) is True, (
            f"Failed to detect control char {ctrl!r} in {s!r}"
        )

    @given(
        s=st.text(
            max_size=50,
            alphabet=st.characters(
                categories=("L", "N", "P", "Z", "S"),
                exclude_characters="".join(_CONTROL_CHARS),
            ),
        )
    )
    @settings(max_examples=100)
    def test_clean_strings_pass(self, s: str) -> None:
        """Strings without control characters must not be flagged.

        Args:
            s: String composed only of safe character categories.
        """
        assert contains_control_chars(s) is False, (
            f"False positive on clean string {s!r}"
        )


# =============================================================================
# validate_time_args valid-inputs soundness
# =============================================================================


class TestValidateTimeArgsSoundness:
    """Verify well-formed time arguments produce no validation errors."""

    @given(
        from_date=valid_date_strs,
        to_date=valid_date_strs,
    )
    @settings(max_examples=100)
    def test_valid_ordered_dates_no_errors(self, from_date: str, to_date: str) -> None:
        """Chronologically ordered valid dates with default last produce no errors.

        Args:
            from_date: Valid YYYY-MM-DD date string.
            to_date: Valid YYYY-MM-DD date string (swapped if needed).
        """
        # Ensure chronological order
        if from_date > to_date:
            from_date, to_date = to_date, from_date

        errors = validate_time_args(
            from_date=from_date,
            to_date=to_date,
            last=30,  # default — not combined with explicit dates
        )
        assert errors == [], (
            f"Unexpected errors for valid dates {from_date} to {to_date}: "
            f"{[e.code for e in errors]}"
        )

    @given(last=st.integers(min_value=1, max_value=3650))
    @settings(max_examples=100)
    def test_valid_last_no_dates_no_errors(self, last: int) -> None:
        """Valid last value with no explicit dates produces no errors.

        Args:
            last: Positive integer within the allowed range.
        """
        errors = validate_time_args(
            from_date=None,
            to_date=None,
            last=last,
        )
        assert errors == [], (
            f"Unexpected errors for last={last}: {[e.code for e in errors]}"
        )

    @given(last=st.integers(max_value=0))
    @settings(max_examples=100)
    def test_nonpositive_last_always_errors(self, last: int) -> None:
        """Non-positive last value always produces V7_LAST_POSITIVE error.

        Args:
            last: Non-positive integer.
        """
        errors = validate_time_args(
            from_date=None,
            to_date=None,
            last=last,
        )
        codes = {e.code for e in errors}
        assert "V7_LAST_POSITIVE" in codes, (
            f"Expected V7_LAST_POSITIVE for last={last}, got {codes}"
        )


# =============================================================================
# _validate_custom_property boundary behavior
# =============================================================================


class TestCustomPropertyRefValidation:
    """Verify CustomPropertyRef validation boundary at id=0."""

    @given(prop_id=st.integers(min_value=1, max_value=10_000))
    @settings(max_examples=100)
    def test_positive_id_no_errors(self, prop_id: int) -> None:
        """Positive IDs must always pass validation.

        Args:
            prop_id: A positive integer ID.
        """
        ref = CustomPropertyRef(id=prop_id)
        errors = _validate_custom_property(ref, "test")
        assert errors == [], (
            f"Unexpected errors for id={prop_id}: {[e.code for e in errors]}"
        )

    @given(prop_id=st.integers(max_value=0))
    @settings(max_examples=100)
    def test_nonpositive_id_produces_cp1(self, prop_id: int) -> None:
        """Non-positive IDs must always produce exactly the CP1 error.

        Args:
            prop_id: A non-positive integer ID.
        """
        ref = CustomPropertyRef(id=prop_id)
        errors = _validate_custom_property(ref, "test")
        assert len(errors) == 1, (
            f"Expected exactly 1 error for id={prop_id}, got {len(errors)}"
        )
        assert errors[0].code == "CP1_INVALID_ID"


class TestInlineCustomPropertyValidation:
    """Verify InlineCustomProperty validation with valid inputs."""

    @given(
        formula=nonempty_formulas,
        keys=st.lists(uppercase_keys, min_size=1, max_size=5, unique=True),
        names=st.lists(property_names, min_size=5, max_size=5),
    )
    @settings(max_examples=100)
    def test_valid_inline_no_errors(
        self,
        formula: str,
        keys: list[str],
        names: list[str],
    ) -> None:
        """Valid InlineCustomProperty specs must produce no errors.

        Args:
            formula: Non-empty, non-whitespace-only formula string.
            keys: Unique single uppercase letter keys (A-Z).
            names: Non-empty property name strings for inputs.
        """
        inputs = {k: PropertyInput(name=names[i]) for i, k in enumerate(keys)}
        prop = InlineCustomProperty(formula=formula, inputs=inputs)
        errors = _validate_custom_property(prop, "test")
        assert errors == [], (
            f"Unexpected errors for valid InlineCustomProperty: "
            f"{[e.code for e in errors]}"
        )

    @given(
        keys=st.lists(uppercase_keys, min_size=1, max_size=3, unique=True),
        names=st.lists(property_names, min_size=3, max_size=3),
    )
    @settings(max_examples=100)
    def test_whitespace_formula_produces_cp2(
        self,
        keys: list[str],
        names: list[str],
    ) -> None:
        """Whitespace-only formulas must always produce CP2 error.

        Args:
            keys: Valid input keys.
            names: Valid property names.
        """
        inputs = {k: PropertyInput(name=names[i]) for i, k in enumerate(keys)}
        prop = InlineCustomProperty(formula="   ", inputs=inputs)
        errors = _validate_custom_property(prop, "test")
        codes = {e.code for e in errors}
        assert "CP2_EMPTY_FORMULA" in codes, (
            f"Expected CP2_EMPTY_FORMULA for whitespace formula, got {codes}"
        )
