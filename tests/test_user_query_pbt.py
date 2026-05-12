"""Property-based tests for user query engine types using Hypothesis.

These tests verify invariants of Filter-to-selector translation,
UserQueryResult DataFrame construction, and aggregate value semantics
that should hold for all possible inputs, catching edge cases that
example-based tests miss.

Usage:
    # Run with default profile (100 examples)
    pytest tests/test_user_query_pbt.py

    # Run with dev profile (10 examples, verbose)
    HYPOTHESIS_PROFILE=dev pytest tests/test_user_query_pbt.py

    # Run with CI profile (200 examples, deterministic)
    HYPOTHESIS_PROFILE=ci pytest tests/test_user_query_pbt.py
"""

from __future__ import annotations

from typing import Any

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from mixpanel_headless._internal.query.user_builders import filter_to_selector
from mixpanel_headless.types import Filter, UserQueryResult

# =============================================================================
# Custom Strategies
# =============================================================================

# Property names: non-empty alphanumeric strings (letters + digits).
# Avoids special characters that would complicate selector parsing validation.
property_names: st.SearchStrategy[str] = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N")),
    min_size=1,
    max_size=20,
)

# String values for filter comparisons.
# Restricted to letters, numbers, and spaces to avoid generating
# operator-like substrings (e.g. "==", "!=", " or ", " and ") that would break
# selector-counting assertions in multi-value filter tests.
string_values: st.SearchStrategy[str] = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N", "Zs")),
    min_size=1,
    max_size=20,
)

# Numeric values for filter comparisons.
numeric_values: st.SearchStrategy[int | float] = st.one_of(
    st.integers(min_value=-1000, max_value=1000),
    st.floats(
        min_value=-1000.0,
        max_value=1000.0,
        allow_nan=False,
        allow_infinity=False,
    ),
)


@st.composite
def filter_strategy(draw: st.DrawFn) -> Filter:
    """Generate random valid Filter objects across all supported operators.

    Draws a property name and randomly selects one of the eleven
    supported filter operators, constructing the Filter via the
    appropriate class method with valid argument types.

    Args:
        draw: Hypothesis draw function for composing strategies.

    Returns:
        A randomly generated Filter instance.
    """
    prop = draw(property_names)
    op = draw(
        st.sampled_from(
            [
                "equals",
                "not_equals",
                "contains",
                "not_contains",
                "greater_than",
                "less_than",
                "between",
                "is_set",
                "is_not_set",
                "is_true",
                "is_false",
            ]
        )
    )

    if op == "equals":
        val = draw(
            st.one_of(string_values, st.lists(string_values, min_size=1, max_size=3))
        )
        return Filter.equals(prop, val)
    elif op == "not_equals":
        val = draw(
            st.one_of(string_values, st.lists(string_values, min_size=1, max_size=3))
        )
        return Filter.not_equals(prop, val)
    elif op == "contains":
        return Filter.contains(prop, draw(string_values))
    elif op == "not_contains":
        return Filter.not_contains(prop, draw(string_values))
    elif op == "greater_than":
        return Filter.greater_than(prop, draw(numeric_values))
    elif op == "less_than":
        return Filter.less_than(prop, draw(numeric_values))
    elif op == "between":
        lo = draw(numeric_values)
        hi = draw(numeric_values)
        return Filter.between(prop, lo, hi)
    elif op == "is_set":
        return Filter.is_set(prop)
    elif op == "is_not_set":
        return Filter.is_not_set(prop)
    elif op == "is_true":
        return Filter.is_true(prop)
    else:  # is_false
        return Filter.is_false(prop)


@st.composite
def profile_strategy(draw: st.DrawFn) -> dict[str, Any]:
    """Generate a random valid profile dict matching the normalized format.

    Each profile has a ``distinct_id``, ``last_seen`` timestamp, and a
    ``properties`` dict with zero to five random key-value pairs.

    Args:
        draw: Hypothesis draw function for composing strategies.

    Returns:
        A profile dict suitable for ``UserQueryResult.profiles``.
    """
    distinct_id = draw(st.text(min_size=1, max_size=30))
    num_props = draw(st.integers(min_value=0, max_value=5))
    props: dict[str, Any] = {}
    for _ in range(num_props):
        key = draw(
            st.text(
                alphabet=st.characters(whitelist_categories=("L", "N")),
                min_size=1,
                max_size=15,
            )
        )
        value = draw(
            st.one_of(
                st.text(max_size=20),
                st.integers(-100, 100),
                st.floats(
                    min_value=-100.0,
                    max_value=100.0,
                    allow_nan=False,
                    allow_infinity=False,
                ),
            )
        )
        props[key] = value
    return {
        "distinct_id": distinct_id,
        "last_seen": "2025-01-01T00:00:00",
        "properties": props,
    }


@st.composite
def profile_list_strategy(draw: st.DrawFn) -> list[dict[str, Any]]:
    """Generate a list of profile dicts.

    Args:
        draw: Hypothesis draw function for composing strategies.

    Returns:
        A list of 0 to 10 profile dicts.
    """
    return draw(st.lists(profile_strategy(), min_size=0, max_size=10))


@st.composite
def user_query_result_profiles_strategy(
    draw: st.DrawFn,
) -> UserQueryResult:
    """Generate a UserQueryResult in profiles mode with total == len(profiles).

    The ``total`` field always equals the number of profiles returned,
    since the API's total reflects the count of profiles in the response.

    Args:
        draw: Hypothesis draw function for composing strategies.

    Returns:
        A UserQueryResult in profiles mode.
    """
    profiles = draw(profile_list_strategy())
    extra = 0  # total == len(profiles)
    total = len(profiles) + extra
    return UserQueryResult(
        computed_at="2025-01-15T10:00:00",
        total=total,
        profiles=profiles,
        params={},
        meta={},
        mode="profiles",
        aggregate_data=None,
    )


@st.composite
def user_query_result_aggregate_strategy(
    draw: st.DrawFn,
) -> UserQueryResult:
    """Generate a UserQueryResult in aggregate mode with a scalar value.

    Produces unsegmented aggregates where ``aggregate_data`` is an ``int``
    or ``float``, suitable for testing the ``.value`` property invariant.

    Args:
        draw: Hypothesis draw function for composing strategies.

    Returns:
        A UserQueryResult in aggregate mode with scalar aggregate_data.
    """
    agg_value: int | float = draw(
        st.one_of(
            st.integers(min_value=0, max_value=100000),
            st.floats(
                min_value=0.0,
                max_value=100000.0,
                allow_nan=False,
                allow_infinity=False,
            ),
        )
    )
    total = draw(st.integers(min_value=0, max_value=100000))
    return UserQueryResult(
        computed_at="2025-01-15T10:00:00",
        total=total,
        profiles=[],
        params={},
        meta={},
        mode="aggregate",
        aggregate_data=agg_value,
    )


# =============================================================================
# Invariant 1: filter_to_selector() always produces a syntactically valid
# selector string for any Filter
# =============================================================================


class TestFilterToSelectorPBT:
    """Property-based tests for filter_to_selector().

    Verifies that the function always produces a non-empty string
    containing the expected structural elements for every supported
    Filter operator.
    """

    @given(f=filter_strategy())
    @settings(max_examples=100)
    def test_always_returns_nonempty_string(self, f: Filter) -> None:
        """filter_to_selector() never returns an empty string for any valid Filter.

        The selector must always contain at least some content
        regardless of the filter operator or property name.
        """
        result = filter_to_selector(f)
        assert isinstance(result, str)
        assert len(result) > 0

    @given(f=filter_strategy())
    @settings(max_examples=100)
    def test_contains_properties_reference(self, f: Filter) -> None:
        """Selector always contains 'properties[' for property-based filters.

        Every filter references a property via the ``properties["name"]``
        syntax, so the output must always contain this substring.
        """
        result = filter_to_selector(f)
        assert "properties[" in result

    @given(prop=property_names, val=string_values)
    @settings(max_examples=100)
    def test_equals_produces_double_equals(self, prop: str, val: str) -> None:
        """Equals filter always produces a selector with '==' operator.

        The engage API equality check uses ``==`` syntax.
        """
        f = Filter.equals(prop, val)
        result = filter_to_selector(f)
        assert "==" in result

    @given(prop=property_names, val=string_values)
    @settings(max_examples=100)
    def test_not_equals_produces_not_equals_operator(self, prop: str, val: str) -> None:
        """Not-equals filter always produces a selector with '!=' operator.

        The engage API inequality check uses ``!=`` syntax.
        """
        f = Filter.not_equals(prop, val)
        result = filter_to_selector(f)
        assert "!=" in result

    @given(prop=property_names, val=string_values)
    @settings(max_examples=100)
    def test_contains_produces_in_keyword(self, prop: str, val: str) -> None:
        """Contains filter always produces a selector with 'in' keyword.

        The engage API substring check uses ``"value" in properties["name"]``.
        """
        f = Filter.contains(prop, val)
        result = filter_to_selector(f)
        assert " in " in result

    @given(prop=property_names, val=string_values)
    @settings(max_examples=100)
    def test_not_contains_produces_not_in(self, prop: str, val: str) -> None:
        """Not-contains filter always produces 'not ... in' in the selector.

        The engage API uses ``not "value" in properties["name"]``.
        """
        f = Filter.not_contains(prop, val)
        result = filter_to_selector(f)
        assert "not " in result
        assert " in " in result

    @given(prop=property_names, val=numeric_values)
    @settings(max_examples=100)
    def test_greater_than_produces_gt_operator(
        self, prop: str, val: int | float
    ) -> None:
        """Greater-than filter always produces '>' in the selector.

        The engage API uses standard comparison operator syntax.
        """
        f = Filter.greater_than(prop, val)
        result = filter_to_selector(f)
        assert " > " in result

    @given(prop=property_names, val=numeric_values)
    @settings(max_examples=100)
    def test_less_than_produces_lt_operator(self, prop: str, val: int | float) -> None:
        """Less-than filter always produces '<' in the selector.

        The engage API uses standard comparison operator syntax.
        """
        f = Filter.less_than(prop, val)
        result = filter_to_selector(f)
        assert " < " in result

    @given(prop=property_names, lo=numeric_values, hi=numeric_values)
    @settings(max_examples=100)
    def test_between_produces_range_operators(
        self, prop: str, lo: int | float, hi: int | float
    ) -> None:
        """Between filter always produces '>=' and '<=' in the selector.

        The engage API between check uses ``prop >= lo and prop <= hi``.
        """
        f = Filter.between(prop, lo, hi)
        result = filter_to_selector(f)
        assert ">=" in result
        assert "<=" in result
        assert " and " in result

    @given(prop=property_names)
    @settings(max_examples=100)
    def test_is_set_produces_defined(self, prop: str) -> None:
        """Is-set filter always produces 'defined(' in the selector.

        The engage API uses ``defined(properties["name"])`` syntax.
        """
        f = Filter.is_set(prop)
        result = filter_to_selector(f)
        assert "defined(" in result

    @given(prop=property_names)
    @settings(max_examples=100)
    def test_is_not_set_produces_not_defined(self, prop: str) -> None:
        """Is-not-set filter always produces 'not defined(' in the selector.

        The engage API uses ``not defined(properties["name"])`` syntax.
        """
        f = Filter.is_not_set(prop)
        result = filter_to_selector(f)
        assert "not defined(" in result

    @given(prop=property_names)
    @settings(max_examples=100)
    def test_is_true_produces_true_literal(self, prop: str) -> None:
        """Is-true filter always produces '== true' in the selector.

        The engage API uses ``properties["name"] == true`` syntax.
        """
        f = Filter.is_true(prop)
        result = filter_to_selector(f)
        assert "== true" in result

    @given(prop=property_names)
    @settings(max_examples=100)
    def test_is_false_produces_false_literal(self, prop: str) -> None:
        """Is-false filter always produces '== false' in the selector.

        The engage API uses ``properties["name"] == false`` syntax.
        """
        f = Filter.is_false(prop)
        result = filter_to_selector(f)
        assert "== false" in result

    @given(prop=property_names, val=string_values)
    @settings(max_examples=100)
    def test_property_name_appears_in_selector(self, prop: str, val: str) -> None:
        """The property name always appears within the selector output.

        Regardless of operator, the property name must be embedded in
        the ``properties["<name>"]`` reference.
        """
        f = Filter.equals(prop, val)
        result = filter_to_selector(f)
        assert prop in result

    @given(
        prop=property_names,
        vals=st.lists(string_values, min_size=2, max_size=4),
    )
    @settings(max_examples=100)
    def test_multi_value_equals_produces_or_joined(
        self, prop: str, vals: list[str]
    ) -> None:
        """Multi-value equals filter produces 'or'-joined selector parts.

        When ``Filter.equals()`` receives a list of values, each value
        generates a separate ``==`` clause joined with `` or ``.
        """
        f = Filter.equals(prop, vals)
        result = filter_to_selector(f)
        assert " or " in result
        assert result.count("==") == len(vals)

    @given(
        prop=property_names,
        vals=st.lists(string_values, min_size=2, max_size=4),
    )
    @settings(max_examples=100)
    def test_multi_value_not_equals_produces_and_joined(
        self, prop: str, vals: list[str]
    ) -> None:
        """Multi-value not-equals filter produces 'and'-joined selector parts.

        When ``Filter.not_equals()`` receives a list of values, each
        value generates a separate ``!=`` clause joined with `` and ``.
        """
        f = Filter.not_equals(prop, vals)
        result = filter_to_selector(f)
        assert " and " in result
        assert result.count("!=") == len(vals)


# =============================================================================
# Invariant 2: .df has exactly len(profiles) rows for any profile list
# =============================================================================


class TestUserQueryResultDfRowCountPBT:
    """Property-based tests for UserQueryResult.df row count invariant.

    Verifies that the DataFrame always has exactly as many rows as
    there are profiles in the input list.
    """

    @given(result=user_query_result_profiles_strategy())
    @settings(
        max_examples=100,
        suppress_health_check=[HealthCheck.too_slow],
    )
    def test_df_row_count_equals_profile_count(self, result: UserQueryResult) -> None:
        """DataFrame row count always equals len(profiles) for any profile list.

        This invariant must hold regardless of the number of profiles,
        whether they have properties or not, and regardless of property
        key overlap between profiles.
        """
        df = result.df
        assert len(df) == len(result.profiles)


# =============================================================================
# Invariant 3: distinct_id column is always present in profiles mode DataFrame
# =============================================================================


class TestUserQueryResultDistinctIdColumnPBT:
    """Property-based tests for distinct_id column presence.

    Verifies that the ``distinct_id`` column is always present in the
    DataFrame when the result is in profiles mode.
    """

    @given(result=user_query_result_profiles_strategy())
    @settings(
        max_examples=100,
        suppress_health_check=[HealthCheck.too_slow],
    )
    def test_distinct_id_always_present(self, result: UserQueryResult) -> None:
        """distinct_id column is always present in profiles mode DataFrame.

        Whether the profiles list is empty or populated, the DataFrame
        must always contain a ``distinct_id`` column.
        """
        df = result.df
        assert "distinct_id" in df.columns

    @given(result=user_query_result_profiles_strategy())
    @settings(
        max_examples=100,
        suppress_health_check=[HealthCheck.too_slow],
    )
    def test_last_seen_always_present(self, result: UserQueryResult) -> None:
        """last_seen column is always present in profiles mode DataFrame.

        The ``last_seen`` column is a required structural column that
        must always appear alongside ``distinct_id``.
        """
        df = result.df
        assert "last_seen" in df.columns

    @given(result=user_query_result_profiles_strategy())
    @settings(
        max_examples=100,
        suppress_health_check=[HealthCheck.too_slow],
    )
    def test_distinct_id_is_first_column(self, result: UserQueryResult) -> None:
        """distinct_id is always the first column in profiles mode DataFrame.

        Column ordering places ``distinct_id`` first, ``last_seen``
        second, then remaining property columns in alphabetical order.
        """
        df = result.df
        assert list(df.columns)[0] == "distinct_id"


# =============================================================================
# Invariant 4: properties param limits columns to selection + distinct_id + last_seen
# =============================================================================


class TestUserQueryResultPropertySelectionPBT:
    """Property-based tests for property column limiting.

    Verifies that when profiles have specific properties, the resulting
    DataFrame columns are exactly ``distinct_id``, ``last_seen``, plus
    the property names from the profiles (with ``$`` prefix stripped).
    """

    @given(
        prop_names=st.lists(
            st.text(
                alphabet=st.characters(whitelist_categories=["L"]),
                min_size=1,
                max_size=10,
            ),
            min_size=1,
            max_size=5,
            unique=True,
        ),
    )
    @settings(
        max_examples=100,
        suppress_health_check=[HealthCheck.too_slow],
    )
    def test_columns_are_distinct_id_last_seen_plus_properties(
        self, prop_names: list[str]
    ) -> None:
        """DataFrame columns are exactly distinct_id + last_seen + property names.

        When all profiles share the same set of property keys, the
        resulting DataFrame columns must be exactly those keys plus
        ``distinct_id`` and ``last_seen``, with no extras.
        """
        profiles = [
            {
                "distinct_id": f"user_{i}",
                "last_seen": "2025-01-01T00:00:00",
                "properties": dict.fromkeys(prop_names, f"val_{i}"),
            }
            for i in range(3)
        ]
        result = UserQueryResult(
            computed_at="2025-01-15T10:00:00",
            total=3,
            profiles=profiles,
            params={},
            meta={},
            mode="profiles",
            aggregate_data=None,
        )
        df = result.df
        expected_cols = {"distinct_id", "last_seen"} | set(prop_names)
        assert set(df.columns) == expected_cols

    @given(
        prop_names=st.lists(
            st.text(
                alphabet=st.characters(whitelist_categories=["L"]),
                min_size=1,
                max_size=10,
            ).map(lambda s: f"${s}"),
            min_size=1,
            max_size=5,
            unique=True,
        ),
    )
    @settings(
        max_examples=100,
        suppress_health_check=[HealthCheck.too_slow],
    )
    def test_dollar_prefixed_properties_are_stripped(
        self, prop_names: list[str]
    ) -> None:
        """$-prefixed property names have their $ stripped in DataFrame columns.

        Built-in Mixpanel properties use a ``$`` prefix (e.g. ``$email``).
        The DataFrame strips this prefix so columns use clean names.
        """
        profiles = [
            {
                "distinct_id": "user_1",
                "last_seen": "2025-01-01T00:00:00",
                "properties": dict.fromkeys(prop_names, "value"),
            }
        ]
        result = UserQueryResult(
            computed_at="2025-01-15T10:00:00",
            total=1,
            profiles=profiles,
            params={},
            meta={},
            mode="profiles",
            aggregate_data=None,
        )
        df = result.df
        for name in prop_names:
            stripped = name[1:]  # Remove $
            assert stripped in df.columns
            assert name not in df.columns


# =============================================================================
# Invariant 5: total == len(profiles) always holds
# =============================================================================


class TestUserQueryResultTotalInvariantPBT:
    """Property-based tests for the total == len(profiles) invariant.

    Verifies that the ``total`` field always equals the number of
    profiles, since ``total`` reflects the count of profiles returned
    by the API (not the full population).
    """

    @given(result=user_query_result_profiles_strategy())
    @settings(max_examples=100)
    def test_total_equals_profile_count(self, result: UserQueryResult) -> None:
        """total always equals len(profiles) for any generated result.

        The strategy enforces ``total = len(profiles)`` since the API's
        total field reflects the number of profiles returned.
        """
        assert result.total == len(result.profiles)

    @given(
        profiles=profile_list_strategy(),
    )
    @settings(
        max_examples=100,
        suppress_health_check=[HealthCheck.too_slow],
    )
    def test_total_equals_df_row_count(self, profiles: list[dict[str, Any]]) -> None:
        """total always equals len(df) since df rows come from profiles.

        The DataFrame has exactly ``len(profiles)`` rows, and
        ``total == len(profiles)``, so ``total == len(df)`` must hold.
        """
        total = len(profiles)
        result = UserQueryResult(
            computed_at="2025-01-15T10:00:00",
            total=total,
            profiles=profiles,
            params={},
            meta={},
            mode="profiles",
            aggregate_data=None,
        )
        assert result.total == len(result.df)


# =============================================================================
# Invariant 6: aggregate .value matches first row of .df for unsegmented aggregates
# =============================================================================


class TestUserQueryResultAggregateValueDfPBT:
    """Property-based tests for aggregate value/DataFrame consistency.

    Verifies that for unsegmented aggregates, the ``.value`` property
    matches the value in the first row of the ``.df`` DataFrame.
    """

    @given(result=user_query_result_aggregate_strategy())
    @settings(max_examples=100)
    def test_value_matches_df_first_row(self, result: UserQueryResult) -> None:
        """Aggregate .value matches .df first row value for unsegmented aggregates.

        When ``aggregate_data`` is a scalar (``int`` or ``float``),
        ``.value`` returns that scalar and ``.df`` has a single row
        with a ``value`` column containing the same number.
        """
        assert result.value is not None
        df = result.df
        assert len(df) == 1
        assert df["value"].iloc[0] == result.value

    @given(result=user_query_result_aggregate_strategy())
    @settings(max_examples=100)
    def test_aggregate_df_has_metric_and_value_columns(
        self, result: UserQueryResult
    ) -> None:
        """Unsegmented aggregate DataFrame always has metric and value columns.

        The column set must be exactly ``["metric", "value"]`` for
        unsegmented scalar aggregates.
        """
        df = result.df
        assert list(df.columns) == ["metric", "value"]

    @given(result=user_query_result_aggregate_strategy())
    @settings(max_examples=100)
    def test_aggregate_value_type_preserved(self, result: UserQueryResult) -> None:
        """Aggregate .value preserves the numeric type (int or float).

        The ``.value`` property must return the same type as the
        ``aggregate_data`` field.
        """
        val = result.value
        assert isinstance(val, (int, float))

    @given(
        segments=st.dictionaries(
            keys=st.text(min_size=1, max_size=15),
            values=st.one_of(
                st.integers(min_value=0, max_value=10000),
                st.floats(
                    min_value=0.0,
                    max_value=10000.0,
                    allow_nan=False,
                    allow_infinity=False,
                ),
            ),
            min_size=1,
            max_size=5,
        ),
    )
    @settings(max_examples=100)
    def test_segmented_aggregate_value_is_none(self, segments: dict[str, Any]) -> None:
        """Segmented aggregate .value is None (not a scalar).

        When ``aggregate_data`` is a dict (segmented result), the
        ``.value`` property returns ``None`` because there is no
        single scalar to report.
        """
        total: int = int(
            sum(v for v in segments.values() if isinstance(v, (int, float)))
        )
        result = UserQueryResult(
            computed_at="2025-01-15T10:00:00",
            total=total,
            profiles=[],
            params={},
            meta={},
            mode="aggregate",
            aggregate_data=segments,
        )
        assert result.value is None

    @given(
        segments=st.dictionaries(
            keys=st.text(min_size=1, max_size=15),
            values=st.integers(min_value=0, max_value=10000),
            min_size=1,
            max_size=5,
        ),
    )
    @settings(max_examples=100)
    def test_segmented_aggregate_df_row_count_matches_segments(
        self, segments: dict[str, int]
    ) -> None:
        """Segmented aggregate DataFrame has one row per segment.

        The number of rows in the DataFrame matches the number of
        entries in the ``aggregate_data`` dict. The ``meta`` dict
        must include ``"segmented": True`` so the ``df`` property
        uses the segmented code path rather than treating the dict
        as an unsegmented structured result (e.g. extremes output).
        """
        result = UserQueryResult(
            computed_at="2025-01-15T10:00:00",
            total=sum(segments.values()),
            profiles=[],
            params={},
            meta={"segmented": True},
            mode="aggregate",
            aggregate_data=segments,
        )
        df = result.df
        assert len(df) == len(segments)
        assert list(df.columns) == ["segment", "value"]
