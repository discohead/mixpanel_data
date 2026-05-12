"""Property-based tests for Query API type invariants.

Uses Hypothesis to verify:
- Valid Metric → valid params (no exception from _build_query_params)
- Valid Filter → correct filterValue format
- Validation exhaustiveness (no invalid combination passes through)
- build_params with comprehensive inputs → passes validate_bookmark
- Filter factory → _build_filter_entry produces valid enum values
- Metric-level overrides propagate into bookmark show clauses
- Formula position validation: in-bounds accepted, out-of-bounds rejected
"""

from __future__ import annotations

from unittest.mock import MagicMock

from hypothesis import assume, given
from hypothesis import strategies as st
from pydantic import SecretStr

from mixpanel_headless import Workspace
from mixpanel_headless._internal.auth.account import ServiceAccount
from mixpanel_headless._internal.auth.session import Project, Session
from mixpanel_headless._internal.bookmark_builders import build_filter_entry
from mixpanel_headless._internal.bookmark_enums import (
    MATH_REQUIRING_PROPERTY,
    VALID_FILTER_OPERATORS,
    VALID_PROPERTY_TYPES,
    VALID_RESOURCE_TYPES,
)
from mixpanel_headless._internal.validation import (
    validate_bookmark,
    validate_query_args,
)
from mixpanel_headless.types import (
    Filter,
    Formula,
    GroupBy,
    Metric,
    QueryResult,
)
from tests.conftest import make_session

# ---- 042 redesign: canonical fake Session for Workspace(session=…) ----
_TEST_SESSION = Session(
    account=ServiceAccount(
        name="test_account",
        region="us",
        username="test_user",
        secret=SecretStr("test_secret"),
        default_project="12345",
    ),
    project=Project(id="12345"),
)

# =============================================================================
# Strategies
# =============================================================================

event_names = st.text(
    min_size=1, max_size=50, alphabet=st.characters(categories=("L", "N", "P"))
)
non_property_math = st.sampled_from(["total", "unique", "dau", "wau", "mau"])
property_math = st.sampled_from(
    ["average", "median", "min", "max", "p25", "p75", "p90", "p99"]
)
all_math = st.sampled_from(
    [
        "total",
        "unique",
        "dau",
        "wau",
        "mau",
        "average",
        "median",
        "min",
        "max",
        "p25",
        "p75",
        "p90",
        "p99",
    ]
)
per_user_agg = st.sampled_from(["unique_values", "total", "average", "min", "max"])
units = st.sampled_from(["hour", "day", "week", "month", "quarter"])
modes = st.sampled_from(["timeseries", "total", "table"])
positive_ints = st.integers(min_value=1, max_value=365)


# =============================================================================
# Helpers
# =============================================================================


def _make_ws() -> Workspace:
    """Create Workspace with mocked config for PBT (inline, not fixture)."""
    creds = make_session(
        username="test",
        secret="secret",
        project_id="12345",
        region="us",
    )
    mgr = MagicMock()
    mgr.config_version.return_value = 1
    mgr.resolve_credentials.return_value = creds
    return Workspace(session=_TEST_SESSION)


# =============================================================================
# T053: Property-based tests
# =============================================================================


class TestMetricParamsInvariant:
    """Valid Metric always produces valid bookmark params."""

    @given(
        event=event_names,
        math=non_property_math,
        unit=units,
        last=positive_ints,
        mode=modes,
    )
    def test_non_property_metric_produces_valid_params(
        self,
        event: str,
        math: str,
        unit: str,
        last: int,
        mode: str,
    ) -> None:
        """Any non-property math Metric produces valid params without exception."""
        ws = _make_ws()
        assume(math not in MATH_REQUIRING_PROPERTY)
        params = ws._build_query_params(
            events=[event],
            math=math,  # type: ignore[arg-type]
            math_property=None,
            per_user=None,
            from_date=None,
            to_date=None,
            last=last,
            unit=unit,  # type: ignore[arg-type]
            group_by=None,
            where=None,
            formulas=[],
            rolling=None,
            cumulative=False,
            mode=mode,
        )
        assert "sections" in params
        assert "displayOptions" in params
        assert len(params["sections"]["show"]) == 1

    @given(
        event=event_names,
        math=property_math,
        prop=event_names,
    )
    def test_property_metric_produces_valid_params(
        self,
        event: str,
        math: str,
        prop: str,
    ) -> None:
        """Any property math with property produces valid params."""
        ws = _make_ws()
        params = ws._build_query_params(
            events=[event],
            math=math,  # type: ignore[arg-type]
            math_property=prop,
            per_user=None,
            from_date=None,
            to_date=None,
            last=30,
            unit="day",
            group_by=None,
            where=None,
            formulas=[],
            rolling=None,
            cumulative=False,
            mode="timeseries",
        )
        m = params["sections"]["show"][0]["measurement"]
        assert m["property"]["name"] == prop


class TestFilterInvariant:
    """Valid Filter always produces correct filterValue format."""

    @given(prop=event_names, value=st.text(min_size=1, max_size=20))
    def test_equals_always_produces_list(self, prop: str, value: str) -> None:
        """Filter.equals always wraps single string in a list."""
        f = Filter.equals(prop, value)
        assert isinstance(f._value, list)
        assert len(f._value) == 1

    @given(prop=event_names, value=st.integers(min_value=-1000, max_value=1000))
    def test_greater_than_always_produces_scalar(self, prop: str, value: int) -> None:
        """Filter.greater_than always produces scalar numeric value."""
        f = Filter.greater_than(prop, value)
        assert isinstance(f._value, (int, float))

    @given(
        prop=event_names,
        min_val=st.integers(min_value=-100, max_value=100),
        max_val=st.integers(min_value=-100, max_value=100),
    )
    def test_between_always_produces_two_element_list(
        self,
        prop: str,
        min_val: int,
        max_val: int,
    ) -> None:
        """Filter.between always produces [min, max] list."""
        f = Filter.between(prop, min_val, max_val)
        assert isinstance(f._value, list)
        assert len(f._value) == 2


class TestValidationExhaustiveness:
    """Validation rules catch all invalid combinations."""

    @given(math=property_math)
    def test_property_math_without_property_always_fails(
        self,
        math: str,
    ) -> None:
        """Any property math without math_property always produces error."""
        errors = validate_query_args(
            events=["E"],
            math=math,  # type: ignore[arg-type]
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
        assert any("requires math_property" in e.message for e in errors)

    @given(math=st.sampled_from(["dau", "wau", "mau"]), per_user=per_user_agg)
    def test_per_user_with_dau_wau_mau_always_fails(
        self,
        math: str,
        per_user: str,
    ) -> None:
        """per_user with DAU/WAU/MAU always produces error."""
        errors = validate_query_args(
            events=["E"],
            math=math,  # type: ignore[arg-type]
            math_property=None,
            per_user=per_user,  # type: ignore[arg-type]
            from_date=None,
            to_date=None,
            last=30,
            has_formula=False,
            rolling=None,
            cumulative=False,
            group_by=None,
        )
        assert any("per_user is incompatible" in e.message for e in errors)


class TestQueryResultDfInvariant:
    """QueryResult.df always returns a DataFrame for valid responses."""

    @given(
        n_metrics=st.integers(min_value=1, max_value=5),
        n_dates=st.integers(min_value=1, max_value=10),
    )
    def test_timeseries_df_always_valid(self, n_metrics: int, n_dates: int) -> None:
        """Timeseries QueryResult.df always returns valid DataFrame."""
        series: dict[str, dict[str, int]] = {}
        for i in range(n_metrics):
            dates = {f"2024-01-{d + 1:02d}": d * 10 + i for d in range(n_dates)}
            series[f"Metric {i}"] = dates

        qr = QueryResult(
            computed_at="",
            from_date="",
            to_date="",
            series=series,
            params={},
            meta={},
        )
        df = qr.df
        assert len(df) == n_metrics * n_dates
        assert list(df.columns) == ["date", "event", "count"]


# =============================================================================
# T054e: build_params() invariants
# =============================================================================


class TestBuildParamsInvariant:
    """T054e: build_params() always produces structurally valid bookmark."""

    @given(
        event=event_names,
        math=non_property_math,
        unit=units,
        last=positive_ints,
        mode=modes,
    )
    def test_build_params_produces_valid_structure(
        self,
        event: str,
        math: str,
        unit: str,
        last: int,
        mode: str,
    ) -> None:
        """build_params() always returns dict with sections and displayOptions."""
        ws = _make_ws()
        result = ws.build_params(
            event,
            math=math,  # type: ignore[arg-type]
            unit=unit,  # type: ignore[arg-type]
            last=last,
            mode=mode,  # type: ignore[arg-type]
        )
        assert isinstance(result, dict)
        assert "sections" in result
        assert "displayOptions" in result
        assert result["sections"]["show"][0]["measurement"]["math"] == math


# =============================================================================
# T059: Date filter invariants
# =============================================================================

date_units = st.sampled_from(["hour", "day", "week", "month"])
positive_quantity = st.integers(min_value=1, max_value=365)


class TestDateFilterInvariant:
    """T059: Date filter property-based invariants."""

    @given(prop=event_names, quantity=positive_quantity, unit=date_units)
    def test_in_the_last_always_has_date_unit(
        self, prop: str, quantity: int, unit: str
    ) -> None:
        """Filter.in_the_last always sets _date_unit."""
        f = Filter.in_the_last(prop, quantity, unit)  # type: ignore[arg-type]
        assert f._date_unit == unit
        assert f._value == quantity
        assert f._property_type == "datetime"

    @given(prop=event_names, quantity=positive_quantity, unit=date_units)
    def test_not_in_the_last_always_has_date_unit(
        self, prop: str, quantity: int, unit: str
    ) -> None:
        """Filter.not_in_the_last always sets _date_unit."""
        f = Filter.not_in_the_last(prop, quantity, unit)  # type: ignore[arg-type]
        assert f._date_unit == unit
        assert f._property_type == "datetime"

    @given(prop=event_names, quantity=positive_quantity, unit=date_units)
    def test_relative_date_filter_serializes_date_unit(
        self, prop: str, quantity: int, unit: str
    ) -> None:
        """Relative date filters always emit filterDateUnit in bookmark."""
        f = Filter.in_the_last(prop, quantity, unit)  # type: ignore[arg-type]
        entry = build_filter_entry(f)
        assert entry["filterDateUnit"] == unit
        assert entry["filterValue"] == quantity


# =============================================================================
# T066: Percentile invariants
# =============================================================================

percentile_values = st.one_of(
    st.integers(min_value=1, max_value=99),
    st.floats(min_value=0.1, max_value=99.9, allow_nan=False, allow_infinity=False),
)


class TestPercentileInvariant:
    """T066: Percentile property-based invariants."""

    @given(event=event_names, prop=event_names, pv=percentile_values)
    def test_percentile_always_maps_to_custom_percentile(
        self, event: str, prop: str, pv: float
    ) -> None:
        """math='percentile' always maps to 'custom_percentile' in bookmark."""
        ws = _make_ws()
        params = ws.build_params(
            event,
            math="percentile",
            math_property=prop,
            percentile_value=pv,
        )
        m = params["sections"]["show"][0]["measurement"]
        assert m["math"] == "custom_percentile"
        assert m["percentile"] == pv


# =============================================================================
# T070: Histogram invariants
# =============================================================================


class TestHistogramInvariant:
    """T070: Histogram property-based invariant."""

    @given(event=event_names, prop=event_names)
    def test_histogram_always_has_property(self, event: str, prop: str) -> None:
        """Histogram bookmark always has property and perUserAggregation."""
        ws = _make_ws()
        params = ws.build_params(
            event, math="histogram", math_property=prop, per_user="total"
        )
        m = params["sections"]["show"][0]["measurement"]
        assert m["math"] == "histogram"
        assert m["property"]["name"] == prop
        assert m["perUserAggregation"] == "total"


# =============================================================================
# Comprehensive build_params → validate_bookmark consistency
# =============================================================================

# Strategies for comprehensive bookmark generation
filter_strategies = st.one_of(
    st.builds(
        Filter.equals, property=event_names, value=st.text(min_size=1, max_size=10)
    ),
    st.builds(
        Filter.greater_than,
        property=event_names,
        value=st.integers(min_value=-1000, max_value=1000),
    ),
    st.builds(
        Filter.between,
        property=event_names,
        min_val=st.integers(min_value=-100, max_value=0),
        max_val=st.integers(min_value=1, max_value=100),
    ),
    st.builds(Filter.is_set, property=event_names),
    st.builds(Filter.is_true, property=event_names),
)

group_by_strategies = st.one_of(
    event_names,  # plain string group-by
    st.builds(GroupBy, property=event_names),
    st.builds(
        GroupBy,
        property=event_names,
        property_type=st.just("number"),
        bucket_size=st.floats(
            min_value=0.1, max_value=100, allow_nan=False, allow_infinity=False
        ),
        bucket_min=st.floats(
            min_value=-1000, max_value=0, allow_nan=False, allow_infinity=False
        ),
        bucket_max=st.floats(
            min_value=0.1, max_value=1000, allow_nan=False, allow_infinity=False
        ),
    ),
)

metric_strategies = st.one_of(
    # Non-property math Metric
    st.builds(
        Metric,
        event=event_names,
        math=non_property_math,
    ),
    # Property math Metric
    st.builds(
        Metric,
        event=event_names,
        math=property_math,
        property=event_names,
    ),
    # Metric with per-user aggregation
    st.builds(
        Metric,
        event=event_names,
        math=st.just("total"),
        property=event_names,
        per_user=per_user_agg,
    ),
    # Metric with per-metric filters
    st.builds(
        Metric,
        event=event_names,
        math=non_property_math,
        filters=st.lists(filter_strategies, min_size=1, max_size=3),
    ),
)


class TestBuildParamsBookmarkConsistency:
    """build_params with any valid input always produces a valid bookmark.

    This is the most important invariant: the builder's output must always
    pass the validator. Tests the contract between _build_query_params
    (Layer 0) and validate_bookmark (Layer 2) across the full input space.
    """

    @given(
        metrics=st.lists(metric_strategies, min_size=1, max_size=4),
        unit=units,
        last=positive_ints,
        mode=modes,
        where=st.one_of(st.none(), filter_strategies),
        group_by=st.one_of(st.none(), group_by_strategies),
        rolling=st.one_of(st.none(), st.integers(min_value=1, max_value=30)),
    )
    def test_valid_metrics_always_produce_valid_bookmark(
        self,
        metrics: list[Metric],
        unit: str,
        last: int,
        mode: str,
        where: Filter | None,
        group_by: str | GroupBy | None,
        rolling: int | None,
    ) -> None:
        """Any list of valid Metrics produces a bookmark passing validate_bookmark."""
        ws = _make_ws()
        params = ws.build_params(
            metrics,
            unit=unit,  # type: ignore[arg-type]
            last=last,
            mode=mode,  # type: ignore[arg-type]
            where=where,
            group_by=group_by,
            rolling=rolling,
            cumulative=False,
        )
        errors = validate_bookmark(params)
        hard_errors = [e for e in errors if e.severity == "error"]
        assert hard_errors == [], (
            f"Valid inputs produced bookmark errors: {hard_errors}"
        )

    @given(
        events=st.lists(event_names, min_size=2, max_size=4),
        formula_expr=st.sampled_from(["A + B", "(B / A) * 100", "A - B"]),
    )
    def test_formula_always_produces_valid_bookmark(
        self,
        events: list[str],
        formula_expr: str,
    ) -> None:
        """Formula queries always produce valid bookmarks."""
        ws = _make_ws()
        params = ws.build_params(
            events,
            formula=formula_expr,
            formula_label="Test Formula",
        )
        errors = validate_bookmark(params)
        hard_errors = [e for e in errors if e.severity == "error"]
        assert hard_errors == [], f"Formula bookmark produced errors: {hard_errors}"


# =============================================================================
# Filter factory → _build_filter_entry produces valid enum values
# =============================================================================


class TestFilterSerializationEnumConsistency:
    """Every Filter factory method serializes to bookmark-valid enum values.

    Catches drift between Filter._operator / _property_type / _resource_type
    and the authoritative enum sets in bookmark_enums.py.

    Date filter operators ("was on", "was in the", etc.) are intentionally
    different from the bookmark enum values ("on", "in the last") — the
    validator treats these as warnings, not errors. This test verifies
    the non-date filters produce exact enum matches and that all filters
    produce valid filterType and resourceType.
    """

    @given(prop=event_names, value=st.text(min_size=1, max_size=20))
    def test_equals_produces_valid_enums(self, prop: str, value: str) -> None:
        """Filter.equals serializes with valid operator, type, and resourceType."""
        f = Filter.equals(prop, value)
        entry = build_filter_entry(f)
        assert entry["filterOperator"] in VALID_FILTER_OPERATORS
        assert entry["filterType"] in VALID_PROPERTY_TYPES
        assert entry["resourceType"] in VALID_RESOURCE_TYPES

    @given(prop=event_names, value=st.integers(min_value=-1000, max_value=1000))
    def test_numeric_filters_produce_valid_enums(self, prop: str, value: int) -> None:
        """Filter.greater_than and less_than serialize with valid enums."""
        for factory in [Filter.greater_than, Filter.less_than]:
            f = factory(prop, value)
            entry = build_filter_entry(f)
            assert entry["filterOperator"] in VALID_FILTER_OPERATORS
            assert entry["filterType"] in VALID_PROPERTY_TYPES
            assert entry["resourceType"] in VALID_RESOURCE_TYPES

    @given(
        prop=event_names,
        min_val=st.integers(min_value=-100, max_value=0),
        max_val=st.integers(min_value=1, max_value=100),
    )
    def test_between_produces_valid_enums(
        self, prop: str, min_val: int, max_val: int
    ) -> None:
        """Filter.between serializes with valid operator enum."""
        f = Filter.between(prop, min_val, max_val)
        entry = build_filter_entry(f)
        assert entry["filterOperator"] in VALID_FILTER_OPERATORS
        assert entry["filterType"] in VALID_PROPERTY_TYPES

    @given(prop=event_names)
    def test_existence_filters_produce_valid_enums(self, prop: str) -> None:
        """Filter.is_set/is_not_set serialize with valid enums."""
        for factory in [Filter.is_set, Filter.is_not_set]:
            f = factory(prop)
            entry = build_filter_entry(f)
            assert entry["filterOperator"] in VALID_FILTER_OPERATORS
            assert entry["filterType"] in VALID_PROPERTY_TYPES

    @given(prop=event_names)
    def test_boolean_filters_produce_valid_enums(self, prop: str) -> None:
        """Filter.is_true/is_false serialize with valid enums."""
        for factory in [Filter.is_true, Filter.is_false]:
            f = factory(prop)
            entry = build_filter_entry(f)
            assert entry["filterOperator"] in VALID_FILTER_OPERATORS
            assert entry["filterType"] in VALID_PROPERTY_TYPES


# =============================================================================
# Metric-level overrides propagate into bookmark show clauses
# =============================================================================


class TestMetricOverridePropagation:
    """Metric-level math/property/per_user override top-level defaults.

    When agents compose Metric objects, each Metric's settings must appear
    in its corresponding show clause — never silently replaced by top-level
    defaults. This property is critical for multi-metric queries where
    different events use different aggregation functions.
    """

    @given(
        event=event_names,
        metric_math=property_math,
        metric_prop=event_names,
        top_math=non_property_math,
    )
    def test_metric_math_overrides_top_level(
        self,
        event: str,
        metric_math: str,
        metric_prop: str,
        top_math: str,
    ) -> None:
        """Metric.math appears in bookmark, not the top-level math default."""
        assume(metric_math != top_math)
        ws = _make_ws()
        m = Metric(event=event, math=metric_math, property=metric_prop)  # type: ignore[arg-type]
        params = ws.build_params(
            [m],
            math=top_math,  # type: ignore[arg-type]
        )
        bookmark_math = params["sections"]["show"][0]["measurement"]["math"]
        # "percentile" maps to "custom_percentile" in bookmark
        expected = "custom_percentile" if metric_math == "percentile" else metric_math
        assert bookmark_math == expected

    @given(
        event=event_names,
        metric_prop=event_names,
        top_prop=event_names,
    )
    def test_metric_property_overrides_top_level(
        self,
        event: str,
        metric_prop: str,
        top_prop: str,
    ) -> None:
        """Metric.property appears in bookmark, not top-level math_property."""
        assume(metric_prop != top_prop)
        ws = _make_ws()
        m = Metric(event=event, math="average", property=metric_prop)
        params = ws.build_params(
            [m],
            math="average",
            math_property=top_prop,
        )
        assert (
            params["sections"]["show"][0]["measurement"]["property"]["name"]
            == metric_prop
        )

    @given(
        event=event_names,
        prop=event_names,
        metric_per_user=per_user_agg,
    )
    def test_metric_per_user_overrides_top_level(
        self,
        event: str,
        prop: str,
        metric_per_user: str,
    ) -> None:
        """Metric.per_user appears in bookmark, not top-level per_user."""
        ws = _make_ws()
        m = Metric(
            event=event,
            math="total",
            property=prop,
            per_user=metric_per_user,  # type: ignore[arg-type]
        )
        params = ws.build_params([m])
        assert (
            params["sections"]["show"][0]["measurement"]["perUserAggregation"]
            == metric_per_user
        )

    @given(
        events=st.lists(metric_strategies, min_size=2, max_size=4),
    )
    def test_each_metric_gets_own_show_clause(
        self,
        events: list[Metric],
    ) -> None:
        """N Metrics produce exactly N show clauses, each with its own math."""
        ws = _make_ws()
        params = ws.build_params(events)
        show = params["sections"]["show"]
        assert len(show) == len(events)
        for i, m in enumerate(events):
            expected = "custom_percentile" if m.math == "percentile" else m.math
            assert show[i]["measurement"]["math"] == expected


# =============================================================================
# Formula position validation: metamorphic property
# =============================================================================


class TestFormulaPositionValidation:
    """Formula position letters must match event count.

    For N events, positions A..chr(A+N-1) are valid. Any position
    beyond that should be caught by validation. This metamorphic
    property tests the relationship between event count and valid
    formula positions.
    """

    @given(n_events=st.integers(min_value=2, max_value=6))
    def test_max_valid_position_accepted(self, n_events: int) -> None:
        """Formula referencing the last valid position passes validation."""
        max_letter = chr(ord("A") + n_events - 1)
        events = [f"Event_{i}" for i in range(n_events)]
        # Formula using the last valid position
        expr = f"A + {max_letter}"
        errors = validate_query_args(
            events=events,
            math="total",
            math_property=None,
            per_user=None,
            from_date=None,
            to_date=None,
            last=30,
            has_formula=True,
            rolling=None,
            cumulative=False,
            group_by=None,
            formulas=[Formula(expression=expr)],
        )
        formula_errors = [e for e in errors if "V19" in e.code]
        assert formula_errors == [], (
            f"Position {max_letter} with {n_events} events should be valid"
        )

    @given(n_events=st.integers(min_value=2, max_value=6))
    def test_one_past_max_position_rejected(self, n_events: int) -> None:
        """Formula referencing one position beyond event count fails validation."""
        out_of_bounds = chr(ord("A") + n_events)
        events = [f"Event_{i}" for i in range(n_events)]
        expr = f"A + {out_of_bounds}"
        errors = validate_query_args(
            events=events,
            math="total",
            math_property=None,
            per_user=None,
            from_date=None,
            to_date=None,
            last=30,
            has_formula=True,
            rolling=None,
            cumulative=False,
            group_by=None,
            formulas=[Formula(expression=expr)],
        )
        formula_errors = [e for e in errors if "V19" in e.code]
        assert len(formula_errors) == 1, (
            f"Position {out_of_bounds} with {n_events} events should be rejected"
        )

    @given(n_events=st.integers(min_value=2, max_value=6))
    def test_position_validation_is_monotonic(self, n_events: int) -> None:
        """Adding an event should never make a previously valid position invalid.

        If position X is valid with N events, it must also be valid with N+1.
        """
        max_letter = chr(ord("A") + n_events - 1)
        expr = f"A + {max_letter}"
        formula = Formula(expression=expr)

        # Valid with n_events
        events_n = [f"Event_{i}" for i in range(n_events)]
        errors_n = validate_query_args(
            events=events_n,
            math="total",
            math_property=None,
            per_user=None,
            from_date=None,
            to_date=None,
            last=30,
            has_formula=True,
            rolling=None,
            cumulative=False,
            group_by=None,
            formulas=[formula],
        )

        # Still valid with n_events + 1
        events_n1 = events_n + [f"Event_{n_events}"]
        errors_n1 = validate_query_args(
            events=events_n1,
            math="total",
            math_property=None,
            per_user=None,
            from_date=None,
            to_date=None,
            last=30,
            has_formula=True,
            rolling=None,
            cumulative=False,
            group_by=None,
            formulas=[formula],
        )

        bounds_errors_n = [e for e in errors_n if "V19" in e.code]
        bounds_errors_n1 = [e for e in errors_n1 if "V19" in e.code]
        # If valid with N events, must be valid with N+1
        if not bounds_errors_n:
            assert not bounds_errors_n1, (
                f"Position {max_letter} valid with {n_events} events "
                f"but invalid with {n_events + 1}"
            )
