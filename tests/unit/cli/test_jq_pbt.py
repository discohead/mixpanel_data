"""Property-based tests for jq filter functionality using Hypothesis.

These tests verify invariants that should hold for all possible inputs,
catching edge cases that example-based tests might miss.

Properties tested:
- Identity filter '.' preserves structure (T073)
- 'length' filter returns correct count (T074)
- select filter never increases size (T075)
"""

from __future__ import annotations

import json
from typing import Any

from hypothesis import given, settings
from hypothesis import strategies as st

from mixpanel_data.cli.utils import _apply_jq_filter

# =============================================================================
# Custom Strategies
# =============================================================================

# JSON-safe integer range: JavaScript's MAX_SAFE_INTEGER is 2^53 - 1
# Integers outside this range may lose precision during JSON roundtrip
JSON_SAFE_INT_MAX = 2**53 - 1
JSON_SAFE_INT_MIN = -(2**53 - 1)

# Strategy for JSON-serializable primitive values (no datetime/date)
json_primitives = st.one_of(
    st.none(),
    st.booleans(),
    st.integers(min_value=JSON_SAFE_INT_MIN, max_value=JSON_SAFE_INT_MAX),
    st.floats(allow_nan=False, allow_infinity=False),
    st.text(),
)

# Strategy for JSON-serializable values (recursive: primitives, lists, dicts)
json_values: st.SearchStrategy[Any] = st.recursive(
    json_primitives,
    lambda children: st.one_of(
        st.lists(children, max_size=5),
        st.dictionaries(st.text(), children, max_size=5),
    ),
    max_leaves=20,
)

# Strategy for JSON objects (dicts with string keys)
json_objects = st.dictionaries(st.text(), json_values, max_size=10)

# Strategy for lists of JSON objects (common input for CLI commands)
json_object_lists = st.lists(json_objects, max_size=10)

# Strategy for lists of numbers (for arithmetic tests)
number_lists = st.lists(
    st.one_of(st.integers(), st.floats(allow_nan=False, allow_infinity=False)),
    min_size=0,
    max_size=20,
)

# Strategy for lists of items with numeric 'value' field
items_with_values = st.lists(
    st.fixed_dictionaries(
        {"value": st.integers(min_value=-1000, max_value=1000)},
        optional={"name": st.text(max_size=10)},
    ),
    min_size=0,
    max_size=15,
)


# =============================================================================
# Identity Filter Property Tests (T073)
# =============================================================================


class TestIdentityFilterProperties:
    """Property-based tests for identity filter '.' (T073)."""

    @given(data=json_objects)
    @settings(max_examples=100)
    def test_identity_preserves_dict_structure(self, data: dict[str, Any]) -> None:
        """Identity filter '.' should preserve dict structure exactly.

        The identity filter should return the input unchanged, maintaining
        all keys, values, and nested structures.

        Args:
            data: A dictionary with string keys and JSON-serializable values.
        """
        json_str = json.dumps(data)
        result = _apply_jq_filter(json_str, ".")
        # Result is a list with single element for identity filter
        assert len(result) == 1
        assert result[0] == data

    @given(data=json_object_lists)
    @settings(max_examples=100)
    def test_identity_preserves_list_structure(
        self, data: list[dict[str, Any]]
    ) -> None:
        """Identity filter '.' should preserve list structure exactly.

        The identity filter should return the input list unchanged,
        maintaining order and all nested structures.

        Args:
            data: A list of dictionaries with JSON-serializable values.
        """
        json_str = json.dumps(data)
        result = _apply_jq_filter(json_str, ".")
        # Result is a list with single element for identity filter
        assert len(result) == 1
        assert result[0] == data

    @given(data=json_values)
    @settings(max_examples=100)
    def test_identity_preserves_any_json_value(self, data: Any) -> None:
        """Identity filter '.' should preserve any JSON-serializable value.

        This tests the identity filter with primitives, nested objects,
        and deeply nested structures.

        Args:
            data: Any JSON-serializable value.
        """
        json_str = json.dumps(data)
        result = _apply_jq_filter(json_str, ".")
        # Result is a list with single element for identity filter
        assert len(result) == 1
        assert result[0] == data


# =============================================================================
# Length Filter Property Tests (T074)
# =============================================================================


class TestLengthFilterProperties:
    """Property-based tests for 'length' filter (T074)."""

    @given(data=json_object_lists)
    @settings(max_examples=100)
    def test_length_returns_correct_list_count(
        self, data: list[dict[str, Any]]
    ) -> None:
        """Length filter should return exact list length.

        The length filter on a list should return the number of elements,
        matching Python's len() function.

        Args:
            data: A list of dictionaries.
        """
        json_str = json.dumps(data)
        result = _apply_jq_filter(json_str, "length")
        # Result is a list containing the length value
        assert len(result) == 1
        assert result[0] == len(data)

    @given(data=json_objects)
    @settings(max_examples=100)
    def test_length_returns_correct_dict_key_count(self, data: dict[str, Any]) -> None:
        """Length filter should return dict key count.

        The length filter on an object should return the number of keys,
        matching Python's len() on the dict.

        Args:
            data: A dictionary with string keys.
        """
        json_str = json.dumps(data)
        result = _apply_jq_filter(json_str, "length")
        # Result is a list containing the length value
        assert len(result) == 1
        assert result[0] == len(data)

    @given(text=st.text())
    @settings(max_examples=100)
    def test_length_returns_correct_string_length(self, text: str) -> None:
        """Length filter should return string length.

        The length filter on a string should return the number of characters.

        Args:
            text: A string value.
        """
        json_str = json.dumps(text)
        result = _apply_jq_filter(json_str, "length")
        # Result is a list containing the length value
        assert len(result) == 1
        assert result[0] == len(text)

    @given(data=number_lists)
    @settings(max_examples=100)
    def test_length_is_non_negative(self, data: list[Any]) -> None:
        """Length should always be non-negative.

        Regardless of content, length should never return a negative value.

        Args:
            data: A list of numbers.
        """
        json_str = json.dumps(data)
        result = _apply_jq_filter(json_str, "length")
        # Result is a list containing the length value
        assert len(result) == 1
        assert result[0] >= 0


# =============================================================================
# Select Filter Property Tests (T075)
# =============================================================================


class TestSelectFilterProperties:
    """Property-based tests for select filter (T075)."""

    @given(
        data=items_with_values, threshold=st.integers(min_value=-1000, max_value=1000)
    )
    @settings(max_examples=100)
    def test_select_never_increases_size(
        self, data: list[dict[str, Any]], threshold: int
    ) -> None:
        """Select filter should never return more items than input.

        Filtering with select() should always produce a result set
        that is equal to or smaller than the original list.

        Args:
            data: A list of dicts with 'value' key.
            threshold: Integer threshold for filtering.
        """
        json_str = json.dumps(data)
        filter_expr = f".[] | select(.value > {threshold})"
        result = _apply_jq_filter(json_str, filter_expr)
        # Result is already a list of matching items
        assert len(result) <= len(data)

    @given(data=items_with_values)
    @settings(max_examples=100)
    def test_select_with_always_true_preserves_all(
        self, data: list[dict[str, Any]]
    ) -> None:
        """Select with always-true condition should preserve all items.

        When the select condition matches everything, the output should
        equal the input.

        Args:
            data: A list of dicts with 'value' key.
        """
        if not data:
            return  # Skip empty lists

        json_str = json.dumps(data)
        # Select everything (value > -infinity effectively)
        result = _apply_jq_filter(json_str, ".[] | select(.value != null)")
        # Result is a list of matching items
        assert len(result) == len(data)

    @given(data=items_with_values)
    @settings(max_examples=100)
    def test_select_with_always_false_returns_empty(
        self, data: list[dict[str, Any]]
    ) -> None:
        """Select with impossible condition should return empty list.

        When the select condition matches nothing, the output should
        be an empty list.

        Args:
            data: A list of dicts with 'value' key.
        """
        json_str = json.dumps(data)
        # Value is integer, so checking type == "string" is always false
        result = _apply_jq_filter(json_str, '.[] | select(.value | type == "string")')
        assert result == []

    @given(data=items_with_values)
    @settings(max_examples=100)
    def test_select_result_items_match_predicate(
        self, data: list[dict[str, Any]]
    ) -> None:
        """All items returned by select should match the predicate.

        Every item in the result should satisfy the select condition.

        Args:
            data: A list of dicts with 'value' key.
        """
        json_str = json.dumps(data)
        filter_expr = ".[] | select(.value > 0)"
        result = _apply_jq_filter(json_str, filter_expr)
        # Result is a list of matching items
        # All returned items should have value > 0
        for item in result:
            assert item["value"] > 0


# =============================================================================
# Additional Property Tests
# =============================================================================


class TestMapFilterProperties:
    """Property-based tests for map filter."""

    @given(data=number_lists)
    @settings(max_examples=100)
    def test_map_preserves_length(self, data: list[Any]) -> None:
        """Map transformation should preserve list length.

        Mapping over a list should produce a result with the same
        number of elements as the input.

        Args:
            data: A list of numbers.
        """
        if not data:
            return  # Skip empty lists

        json_str = json.dumps(data)
        result = _apply_jq_filter(json_str, "map(. + 1)")
        # map returns single array result wrapped in list
        assert len(result) == 1
        assert len(result[0]) == len(data)

    @given(
        data=st.lists(
            st.integers(min_value=-100, max_value=100), min_size=1, max_size=20
        )
    )
    @settings(max_examples=100)
    def test_map_identity_preserves_values(self, data: list[int]) -> None:
        """Map with identity function should preserve all values.

        Args:
            data: A list of integers.
        """
        json_str = json.dumps(data)
        result = _apply_jq_filter(json_str, "map(.)")
        # map returns single array result wrapped in list
        assert len(result) == 1
        assert result[0] == data


class TestKeysFilterProperties:
    """Property-based tests for keys filter."""

    @given(data=json_objects)
    @settings(max_examples=100)
    def test_keys_returns_all_dict_keys(self, data: dict[str, Any]) -> None:
        """Keys filter should return all dict keys.

        The keys filter should return every key present in the object.

        Args:
            data: A dictionary with string keys.
        """
        json_str = json.dumps(data)
        result = _apply_jq_filter(json_str, "keys")
        # keys returns single array result wrapped in list
        assert len(result) == 1
        assert set(result[0]) == set(data.keys())

    @given(data=json_objects)
    @settings(max_examples=100)
    def test_keys_count_matches_length(self, data: dict[str, Any]) -> None:
        """Number of keys should match length.

        The keys filter result length should equal the object length.

        Args:
            data: A dictionary with string keys.
        """
        json_str = json.dumps(data)
        keys_result = _apply_jq_filter(json_str, "keys")
        length_result = _apply_jq_filter(json_str, "length")

        # keys returns single array wrapped in list
        assert len(keys_result) == 1
        keys = keys_result[0]
        # length returns single value wrapped in list
        assert len(length_result) == 1
        length = length_result[0]

        assert len(keys) == length


class TestSliceFilterProperties:
    """Property-based tests for slice operations."""

    @given(
        data=st.lists(
            st.integers(min_value=JSON_SAFE_INT_MIN, max_value=JSON_SAFE_INT_MAX),
            min_size=0,
            max_size=20,
        ),
        n=st.integers(min_value=0, max_value=25),
    )
    @settings(max_examples=100)
    def test_slice_first_n_bounds(self, data: list[int], n: int) -> None:
        """Slicing first n items should return at most n items.

        The result length should be min(n, len(data)).

        Args:
            data: A list of integers.
            n: Number of items to take.
        """
        json_str = json.dumps(data)
        result = _apply_jq_filter(json_str, f".[:{n}]")
        # slice returns single array wrapped in list
        assert len(result) == 1
        parsed = result[0]

        expected_length = min(n, len(data))
        assert len(parsed) == expected_length

    @given(
        data=st.lists(
            st.integers(min_value=JSON_SAFE_INT_MIN, max_value=JSON_SAFE_INT_MAX),
            min_size=1,
            max_size=20,
        )
    )
    @settings(max_examples=100)
    def test_slice_preserves_elements(self, data: list[int]) -> None:
        """Sliced elements should match original list elements.

        Args:
            data: A list of integers.
        """
        n = len(data)
        json_str = json.dumps(data)
        result = _apply_jq_filter(json_str, f".[0:{n}]")
        # slice returns single array wrapped in list
        assert len(result) == 1
        assert result[0] == data
