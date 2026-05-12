"""Unit tests for filter-to-selector translation (user_builders).

Tests for ``filter_to_selector()``, ``filters_to_selector()``, and
``extract_cohort_filter()`` which translate ``Filter`` objects to engage
API selector strings.

Task ID: T004
"""

from __future__ import annotations

from mixpanel_headless._internal.query.user_builders import (
    extract_cohort_filter,
    filter_to_selector,
    filters_to_selector,
)
from mixpanel_headless.types import CohortCriteria, CohortDefinition, Filter

# =============================================================================
# filter_to_selector — individual operator mapping
# =============================================================================


class TestFilterToSelectorEquals:
    """Tests for equals operator translation."""

    def test_single_string_value(self) -> None:
        """Equals with a single string produces ``properties["p"] == "v"``."""
        f = Filter.equals("plan", "premium")
        result = filter_to_selector(f)
        assert result == 'properties["plan"] == "premium"'

    def test_multi_value_produces_or_chain(self) -> None:
        """Equals with multiple values produces OR-chained equality checks."""
        f = Filter.equals("country", ["US", "CA", "UK"])
        result = filter_to_selector(f)
        assert result == (
            '(properties["country"] == "US"'
            " or "
            'properties["country"] == "CA"'
            " or "
            'properties["country"] == "UK")'
        )

    def test_two_values_or(self) -> None:
        """Equals with exactly two values produces a single OR."""
        f = Filter.equals("status", ["active", "trial"])
        result = filter_to_selector(f)
        assert result == (
            '(properties["status"] == "active" or properties["status"] == "trial")'
        )

    def test_single_value_in_list(self) -> None:
        """Equals with a one-element list produces simple equality (no OR)."""
        f = Filter.equals("plan", ["premium"])
        result = filter_to_selector(f)
        assert result == 'properties["plan"] == "premium"'


class TestFilterToSelectorNotEquals:
    """Tests for does-not-equal operator translation."""

    def test_single_value(self) -> None:
        """Not-equals with a single value produces ``!=``."""
        f = Filter.not_equals("plan", "free")
        result = filter_to_selector(f)
        assert result == 'properties["plan"] != "free"'

    def test_multi_value(self) -> None:
        """Not-equals with multiple values produces AND-chained inequalities."""
        f = Filter.not_equals("status", ["banned", "deleted"])
        result = filter_to_selector(f)
        # Each value must not match -- AND semantics for not-equals
        assert 'properties["status"] != "banned"' in result
        assert 'properties["status"] != "deleted"' in result


class TestFilterToSelectorContains:
    """Tests for contains operator translation."""

    def test_contains_string(self) -> None:
        """Contains produces ``"v" in properties["p"]``."""
        f = Filter.contains("email", "gmail")
        result = filter_to_selector(f)
        assert result == '"gmail" in properties["email"]'


class TestFilterToSelectorNotContains:
    """Tests for does-not-contain operator translation."""

    def test_not_contains_string(self) -> None:
        """Not-contains produces ``not "v" in properties["p"]``."""
        f = Filter.not_contains("email", "spam")
        result = filter_to_selector(f)
        assert result == 'not "spam" in properties["email"]'


class TestFilterToSelectorGreaterThan:
    """Tests for greater-than operator translation."""

    def test_integer_value(self) -> None:
        """Greater-than with int produces ``properties["p"] > n``."""
        f = Filter.greater_than("age", 18)
        result = filter_to_selector(f)
        assert result == 'properties["age"] > 18'

    def test_float_value(self) -> None:
        """Greater-than with float produces ``properties["p"] > n.n``."""
        f = Filter.greater_than("score", 9.5)
        result = filter_to_selector(f)
        assert result == 'properties["score"] > 9.5'


class TestFilterToSelectorLessThan:
    """Tests for less-than operator translation."""

    def test_integer_value(self) -> None:
        """Less-than with int produces ``properties["p"] < n``."""
        f = Filter.less_than("age", 65)
        result = filter_to_selector(f)
        assert result == 'properties["age"] < 65'

    def test_float_value(self) -> None:
        """Less-than with float produces ``properties["p"] < n.n``."""
        f = Filter.less_than("price", 19.99)
        result = filter_to_selector(f)
        assert result == 'properties["price"] < 19.99'


class TestFilterToSelectorBetween:
    """Tests for between (inclusive range) operator translation."""

    def test_integer_range(self) -> None:
        """Between with ints produces ``>= a and <= b``."""
        f = Filter.between("age", 18, 65)
        result = filter_to_selector(f)
        assert result == 'properties["age"] >= 18 and properties["age"] <= 65'

    def test_float_range(self) -> None:
        """Between with floats produces ``>= a and <= b``."""
        f = Filter.between("score", 1.5, 9.5)
        result = filter_to_selector(f)
        assert result == 'properties["score"] >= 1.5 and properties["score"] <= 9.5'

    def test_mixed_int_float(self) -> None:
        """Between with mixed int/float values."""
        f = Filter.between("amount", 0, 99.99)
        result = filter_to_selector(f)
        assert result == 'properties["amount"] >= 0 and properties["amount"] <= 99.99'


class TestFilterToSelectorIsSet:
    """Tests for is-set (property existence) operator translation."""

    def test_is_set(self) -> None:
        """Is-set produces ``defined(properties["p"])``."""
        f = Filter.is_set("email")
        result = filter_to_selector(f)
        assert result == 'defined(properties["email"])'


class TestFilterToSelectorIsNotSet:
    """Tests for is-not-set (property non-existence) operator translation."""

    def test_is_not_set(self) -> None:
        """Is-not-set produces ``not defined(properties["p"])``."""
        f = Filter.is_not_set("phone")
        result = filter_to_selector(f)
        assert result == 'not defined(properties["phone"])'


class TestFilterToSelectorBooleans:
    """Tests for boolean (true/false) operator translation."""

    def test_is_true(self) -> None:
        """True operator produces ``properties["p"] == true`` (no quotes)."""
        f = Filter.is_true("verified")
        result = filter_to_selector(f)
        assert result == 'properties["verified"] == true'

    def test_is_false(self) -> None:
        """False operator produces ``properties["p"] == false`` (no quotes)."""
        f = Filter.is_false("opted_out")
        result = filter_to_selector(f)
        assert result == 'properties["opted_out"] == false'


# =============================================================================
# filter_to_selector — value formatting
# =============================================================================


class TestFilterToSelectorValueFormatting:
    """Tests for correct value formatting in selectors."""

    def test_string_value_quoted(self) -> None:
        """String values are wrapped in double quotes."""
        f = Filter.equals("city", "New York")
        result = filter_to_selector(f)
        assert result == 'properties["city"] == "New York"'

    def test_integer_value_unquoted(self) -> None:
        """Integer values appear without quotes."""
        f = Filter.greater_than("count", 100)
        result = filter_to_selector(f)
        assert "100" in result
        assert '"100"' not in result

    def test_float_value_unquoted(self) -> None:
        """Float values appear without quotes."""
        f = Filter.less_than("ratio", 0.5)
        result = filter_to_selector(f)
        assert "0.5" in result
        assert '"0.5"' not in result

    def test_boolean_true_unquoted(self) -> None:
        """Boolean true is lowercase and unquoted."""
        f = Filter.is_true("active")
        result = filter_to_selector(f)
        assert "true" in result
        assert '"true"' not in result

    def test_boolean_false_unquoted(self) -> None:
        """Boolean false is lowercase and unquoted."""
        f = Filter.is_false("disabled")
        result = filter_to_selector(f)
        assert "false" in result
        assert '"false"' not in result

    def test_zero_integer(self) -> None:
        """Zero integer is formatted correctly."""
        f = Filter.greater_than("balance", 0)
        result = filter_to_selector(f)
        assert result == 'properties["balance"] > 0'

    def test_negative_integer(self) -> None:
        """Negative integer is formatted correctly."""
        f = Filter.greater_than("offset", -10)
        result = filter_to_selector(f)
        assert result == 'properties["offset"] > -10'


# =============================================================================
# filter_to_selector — edge cases
# =============================================================================


class TestFilterToSelectorEdgeCases:
    """Tests for edge cases in filter-to-selector translation."""

    def test_property_name_with_dollar_prefix(self) -> None:
        """Dollar-prefixed properties (Mixpanel builtins) are handled."""
        f = Filter.equals("$city", "London")
        result = filter_to_selector(f)
        assert result == 'properties["$city"] == "London"'

    def test_property_name_with_spaces(self) -> None:
        """Property names containing spaces are handled."""
        f = Filter.equals("first name", "Alice")
        result = filter_to_selector(f)
        assert result == 'properties["first name"] == "Alice"'

    def test_value_with_double_quotes(self) -> None:
        """String values containing double quotes are escaped."""
        f = Filter.contains("description", 'say "hello"')
        result = filter_to_selector(f)
        # The value must be present in the selector without breaking syntax
        assert "say" in result
        assert "hello" in result

    def test_value_with_backslash(self) -> None:
        """String values containing backslashes are handled."""
        f = Filter.contains("path", "C:\\Users")
        result = filter_to_selector(f)
        assert "C:\\" in result or "C:\\\\Users" in result

    def test_empty_string_value(self) -> None:
        """Empty string value is represented as empty quoted string."""
        f = Filter.equals("tag", "")
        result = filter_to_selector(f)
        assert '""' in result


# =============================================================================
# filters_to_selector — AND combination
# =============================================================================


class TestFiltersToSelector:
    """Tests for combining multiple filters with AND."""

    def test_empty_list_returns_empty_string(self) -> None:
        """Empty filter list produces empty string."""
        result = filters_to_selector([])
        assert result == ""

    def test_single_filter(self) -> None:
        """Single filter produces its selector without AND."""
        result = filters_to_selector([Filter.equals("plan", "premium")])
        assert result == 'properties["plan"] == "premium"'

    def test_two_filters_and_combined(self) -> None:
        """Two filters are combined with `` and ``."""
        result = filters_to_selector(
            [
                Filter.equals("plan", "premium"),
                Filter.is_set("email"),
            ]
        )
        assert result == (
            'properties["plan"] == "premium" and defined(properties["email"])'
        )

    def test_three_filters_and_combined(self) -> None:
        """Three filters produce two AND operators."""
        result = filters_to_selector(
            [
                Filter.equals("plan", "premium"),
                Filter.greater_than("age", 18),
                Filter.is_set("email"),
            ]
        )
        assert " and " in result
        assert result.count(" and ") == 2
        assert 'properties["plan"] == "premium"' in result
        assert 'properties["age"] > 18' in result
        assert 'defined(properties["email"])' in result

    def test_preserves_filter_order(self) -> None:
        """Filters appear in the selector in the order they were provided."""
        result = filters_to_selector(
            [
                Filter.is_set("a"),
                Filter.is_set("b"),
                Filter.is_set("c"),
            ]
        )
        parts = result.split(" and ")
        assert parts[0] == 'defined(properties["a"])'
        assert parts[1] == 'defined(properties["b"])'
        assert parts[2] == 'defined(properties["c"])'

    def test_mixed_operator_types(self) -> None:
        """Different operator types combine correctly."""
        result = filters_to_selector(
            [
                Filter.equals("country", "US"),
                Filter.greater_than("age", 21),
                Filter.is_true("verified"),
                Filter.is_not_set("banned_at"),
            ]
        )
        parts = result.split(" and ")
        assert len(parts) == 4


# =============================================================================
# extract_cohort_filter
# =============================================================================


class TestExtractCohortFilter:
    """Tests for separating cohort filters from property filters."""

    def test_no_cohort_filter(self) -> None:
        """List without cohort filter returns all filters and None."""
        filters = [
            Filter.equals("plan", "premium"),
            Filter.is_set("email"),
        ]
        remaining, cohort = extract_cohort_filter(filters)
        assert len(remaining) == 2
        assert cohort is None

    def test_empty_list(self) -> None:
        """Empty list returns empty list and None."""
        remaining, cohort = extract_cohort_filter([])
        assert remaining == []
        assert cohort is None

    def test_only_cohort_filter(self) -> None:
        """List with only a cohort filter returns empty remaining and the filter."""
        filters = [Filter.in_cohort(123, "Power Users")]
        remaining, cohort = extract_cohort_filter(filters)
        assert remaining == []
        assert cohort is not None

    def test_cohort_filter_with_saved_id(self) -> None:
        """Cohort filter with saved ID is correctly extracted."""
        filters = [
            Filter.equals("plan", "premium"),
            Filter.in_cohort(456, "VIPs"),
            Filter.is_set("email"),
        ]
        remaining, cohort = extract_cohort_filter(filters)
        assert len(remaining) == 2
        assert cohort is not None
        # Remaining should not contain the cohort filter
        for f in remaining:
            assert f._property != "$cohorts"

    def test_cohort_filter_with_inline_definition(self) -> None:
        """Cohort filter with inline CohortDefinition is extracted."""
        cohort_def = CohortDefinition.all_of(
            CohortCriteria.did_event("Purchase", at_least=1, within_days=30),
        )
        filters = [
            Filter.equals("plan", "premium"),
            Filter.in_cohort(cohort_def, name="Buyers"),
        ]
        remaining, cohort = extract_cohort_filter(filters)
        assert len(remaining) == 1
        assert cohort is not None

    def test_not_in_cohort_extracted(self) -> None:
        """Not-in-cohort filter is also extracted as a cohort filter."""
        filters = [
            Filter.equals("plan", "free"),
            Filter.not_in_cohort(789, "Bots"),
        ]
        remaining, cohort = extract_cohort_filter(filters)
        assert len(remaining) == 1
        assert cohort is not None

    def test_remaining_filters_preserve_order(self) -> None:
        """Non-cohort filters maintain their original order."""
        f1 = Filter.equals("plan", "premium")
        f2 = Filter.greater_than("age", 18)
        f3 = Filter.is_set("email")
        filters = [f1, Filter.in_cohort(123), f2, f3]
        remaining, _ = extract_cohort_filter(filters)
        assert remaining == [f1, f2, f3]

    def test_cohort_filter_identity_preserved(self) -> None:
        """Extracted cohort filter is the same object from the input list."""
        cohort_filter = Filter.in_cohort(123, "Power Users")
        filters = [Filter.equals("plan", "free"), cohort_filter]
        _, cohort = extract_cohort_filter(filters)
        assert cohort is cohort_filter

    def test_original_list_not_mutated(self) -> None:
        """Input filter list is not modified by extraction."""
        filters = [
            Filter.equals("plan", "premium"),
            Filter.in_cohort(123),
            Filter.is_set("email"),
        ]
        original_len = len(filters)
        extract_cohort_filter(filters)
        assert len(filters) == original_len


# =============================================================================
# PR #118 review fixes — property escaping and between bounds
# =============================================================================


class TestFilterToSelectorPropertyEscaping:
    """Tests for property name escaping in selectors."""

    def test_property_with_double_quote(self) -> None:
        """Property name containing double quote is escaped."""
        f = Filter.equals('weird"prop', "val")
        result = filter_to_selector(f)
        assert result == 'properties["weird\\"prop"] == "val"'

    def test_property_with_backslash(self) -> None:
        """Property name containing backslash is escaped."""
        f = Filter.equals("back\\slash", "val")
        result = filter_to_selector(f)
        assert result == 'properties["back\\\\slash"] == "val"'


class TestFilterToSelectorBetweenBoundsValidation:
    """Tests for between operator bound type validation."""

    def test_string_lower_bound_rejected(self) -> None:
        """String lower bound raises ValueError."""
        f = Filter("prop", "is between", ["low", 10])  # type: ignore[arg-type]
        import pytest

        with pytest.raises(ValueError, match="int or float for lower bound"):
            filter_to_selector(f)

    def test_string_upper_bound_rejected(self) -> None:
        """String upper bound raises ValueError."""
        f = Filter("prop", "is between", [0, "high"])  # type: ignore[arg-type]
        import pytest

        with pytest.raises(ValueError, match="int or float for upper bound"):
            filter_to_selector(f)


class TestNotEqualsErrorMessage:
    """Tests for not_equals error message correctness."""

    def test_error_references_correct_method_name(self) -> None:
        """Error message references Filter.not_equals(), not does_not_equal()."""
        f = Filter("prop", "does not equal", [{"nested": True}])
        import pytest

        with pytest.raises(ValueError, match="Filter.not_equals"):
            filter_to_selector(f)
