"""Unit tests for Query API types: Metric, Formula, QueryResult.

Tests Metric dataclass construction, defaults, immutability (T006),
Formula dataclass, and QueryResult.df behavior per mode (T045, T049).
"""

from __future__ import annotations

from typing import Any

import pytest

from mixpanel_headless._internal.bookmark_enums import (
    MATH_NO_PER_USER,
    MATH_PROPERTY_OPTIONAL,
    MATH_REQUIRING_PROPERTY,
)
from mixpanel_headless.types import (
    Filter,
    Formula,
    Metric,
    QueryResult,
)

# =============================================================================
# T006: Metric dataclass tests
# =============================================================================


class TestMetricConstruction:
    """Tests for Metric frozen dataclass construction and defaults."""

    def test_event_only_uses_defaults(self) -> None:
        """Metric("Login") uses default math="total" and None for optional fields."""
        m = Metric("Login")
        assert m.event == "Login"
        assert m.math == "total"
        assert m.property is None
        assert m.per_user is None
        assert m.filters is None

    def test_all_fields_set(self) -> None:
        """Metric with all fields explicitly set."""
        m = Metric(
            "Purchase",
            math="average",
            property="amount",
            per_user="total",
            filters=[],
        )
        assert m.event == "Purchase"
        assert m.math == "average"
        assert m.property == "amount"
        assert m.per_user == "total"
        assert m.filters == []

    def test_keyword_construction(self) -> None:
        """Metric can be constructed with keyword arguments."""
        m = Metric(event="Login", math="unique")
        assert m.event == "Login"
        assert m.math == "unique"

    def test_immutability(self) -> None:
        """Metric is frozen and cannot be modified after construction."""
        m = Metric("Login")
        with pytest.raises(AttributeError):
            m.event = "Signup"  # type: ignore[misc]

    def test_equality_same_fields(self) -> None:
        """Two Metrics with identical fields are equal."""
        m1 = Metric("Login", math="unique")
        m2 = Metric("Login", math="unique")
        assert m1 == m2

    def test_inequality_different_event(self) -> None:
        """Metrics with different events are not equal."""
        assert Metric("Login") != Metric("Signup")

    def test_inequality_different_math(self) -> None:
        """Metrics with different math are not equal."""
        assert Metric("Login", math="total") != Metric("Login", math="unique")


class TestTypeConstants:
    """Tests for query type aliases and constants."""

    def test_math_requiring_property_contents(self) -> None:
        """MATH_REQUIRING_PROPERTY contains all property-based aggregations."""
        expected = {
            "average",
            "median",
            "min",
            "max",
            "p25",
            "p75",
            "p90",
            "p99",
            "custom_percentile",
            "percentile",
            "histogram",
            # Advanced property-requiring types
            "unique_values",
            "most_frequent",
            "first_value",
            "multi_attribution",
            "numeric_summary",
        }
        assert expected == MATH_REQUIRING_PROPERTY

    def test_math_property_optional_contents(self) -> None:
        """MATH_PROPERTY_OPTIONAL contains types that optionally accept property."""
        assert {"total"} == MATH_PROPERTY_OPTIONAL

    def test_math_no_per_user_contents(self) -> None:
        """MATH_NO_PER_USER contains DAU/WAU/MAU/unique."""
        assert {"dau", "wau", "mau", "unique"} == MATH_NO_PER_USER

    def test_math_requiring_property_immutable(self) -> None:
        """MATH_REQUIRING_PROPERTY is a frozenset."""
        assert isinstance(MATH_REQUIRING_PROPERTY, frozenset)

    def test_math_no_per_user_immutable(self) -> None:
        """MATH_NO_PER_USER is a frozenset."""
        assert isinstance(MATH_NO_PER_USER, frozenset)


# =============================================================================
# QueryResult tests
# =============================================================================


class TestQueryResultConstruction:
    """Tests for QueryResult dataclass construction."""

    def test_basic_construction(self) -> None:
        """QueryResult with all required fields."""
        qr = QueryResult(
            computed_at="2024-01-01T00:00:00Z",
            from_date="2024-01-01",
            to_date="2024-01-31",
            headers=["$metric"],
            series={"Login [Total Events]": {"2024-01-01": 100}},
            params={"test": True},
            meta={"min_sampling_factor": 1.0},
        )
        assert qr.computed_at == "2024-01-01T00:00:00Z"
        assert qr.from_date == "2024-01-01"
        assert qr.to_date == "2024-01-31"

    def test_immutability(self) -> None:
        """QueryResult is frozen."""
        qr = QueryResult(
            computed_at="",
            from_date="",
            to_date="",
            params={},
            meta={},
        )
        with pytest.raises(AttributeError):
            qr.computed_at = "changed"  # type: ignore[misc]

    def test_params_preserved(self) -> None:
        """QueryResult.params contains the bookmark dict sent to API."""
        params: dict[str, Any] = {"sections": {"show": []}, "displayOptions": {}}
        qr = QueryResult(
            computed_at="",
            from_date="",
            to_date="",
            params=params,
            meta={},
        )
        assert qr.params is params

    def test_meta_preserved(self) -> None:
        """QueryResult.meta contains response metadata."""
        meta: dict[str, Any] = {
            "min_sampling_factor": 1.0,
            "is_segmentation_limit_hit": False,
        }
        qr = QueryResult(
            computed_at="",
            from_date="",
            to_date="",
            params={},
            meta=meta,
        )
        assert qr.meta is meta


class TestQueryResultDataFrame:
    """Tests for QueryResult.df property."""

    def test_timeseries_columns(self) -> None:
        """Timeseries mode produces date, event, count columns."""
        qr = QueryResult(
            computed_at="",
            from_date="",
            to_date="",
            series={
                "Login [Total Events]": {
                    "2024-01-01": 100,
                    "2024-01-02": 200,
                },
            },
            params={},
            meta={},
        )
        df = qr.df
        assert list(df.columns) == ["date", "event", "count"]
        assert len(df) == 2

    def test_timeseries_values(self) -> None:
        """Timeseries DataFrame has correct values."""
        qr = QueryResult(
            computed_at="",
            from_date="",
            to_date="",
            series={
                "Login [Total Events]": {
                    "2024-01-01": 100,
                    "2024-01-02": 200,
                },
            },
            params={},
            meta={},
        )
        df = qr.df
        row0 = df.iloc[0]
        assert row0["date"] == "2024-01-01"
        assert row0["event"] == "Login [Total Events]"
        assert row0["count"] == 100

    def test_hourly_timestamps_preserved(self) -> None:
        """Hourly timestamp keys are preserved (not truncated to date)."""
        qr = QueryResult(
            computed_at="",
            from_date="",
            to_date="",
            series={
                "Login [Total Events]": {
                    "2024-01-01T00:00:00": 100,
                    "2024-01-01T01:00:00": 110,
                    "2024-01-01T02:00:00": 120,
                },
            },
            params={},
            meta={},
        )
        df = qr.df
        assert len(df) == 3
        dates = list(df["date"])
        assert dates[0] == "2024-01-01T00:00:00"
        assert dates[1] == "2024-01-01T01:00:00"
        assert dates[2] == "2024-01-01T02:00:00"

    def test_total_mode_columns(self) -> None:
        """Total mode produces event, count columns (no date)."""
        qr = QueryResult(
            computed_at="",
            from_date="",
            to_date="",
            series={"Login [Unique Users]": {"all": 500}},
            params={},
            meta={},
        )
        df = qr.df
        assert list(df.columns) == ["event", "count"]
        assert len(df) == 1
        assert df.iloc[0]["count"] == 500

    def test_empty_series(self) -> None:
        """Empty series returns empty DataFrame with expected columns."""
        qr = QueryResult(
            computed_at="",
            from_date="",
            to_date="",
            series={},
            params={},
            meta={},
        )
        df = qr.df
        assert len(df) == 0
        assert "date" in df.columns

    def test_multi_metric_timeseries(self) -> None:
        """Multiple metrics in timeseries produce rows for each."""
        qr = QueryResult(
            computed_at="",
            from_date="",
            to_date="",
            series={
                "Login [Total]": {"2024-01-01": 100},
                "Signup [Total]": {"2024-01-01": 50},
            },
            params={},
            meta={},
        )
        df = qr.df
        assert len(df) == 2
        events = set(df["event"])
        assert events == {"Login [Total]", "Signup [Total]"}

    def test_df_caching(self) -> None:
        """DataFrame is cached on first access."""
        qr = QueryResult(
            computed_at="",
            from_date="",
            to_date="",
            series={"A": {"2024-01-01": 1}},
            params={},
            meta={},
        )
        df1 = qr.df
        df2 = qr.df
        assert df1 is df2


class TestQueryResultSegmentedDataFrame:
    """Tests for QueryResult.df with group_by (segmented) responses."""

    def test_segmented_total_columns(self) -> None:
        """Segmented total mode produces event, segment, count columns."""
        qr = QueryResult(
            computed_at="",
            from_date="",
            to_date="",
            series={
                "Login [Total Events]": {
                    "$overall": {"all": 500},
                    "US": {"all": 300},
                    "EU": {"all": 200},
                },
            },
            params={},
            meta={},
        )
        df = qr.df
        assert "segment" in df.columns
        assert "count" in df.columns
        assert "event" in df.columns
        assert "date" not in df.columns

    def test_segmented_total_scalar_counts(self) -> None:
        """Segmented total mode count column contains scalar integers, not dicts."""
        qr = QueryResult(
            computed_at="",
            from_date="",
            to_date="",
            series={
                "Login [Total Events]": {
                    "$overall": {"all": 500},
                    "US": {"all": 300},
                    "EU": {"all": 200},
                },
            },
            params={},
            meta={},
        )
        df = qr.df
        for val in df["count"]:
            assert isinstance(val, (int, float)), (
                f"count should be scalar, got {type(val)}: {val}"
            )

    def test_segmented_total_values(self) -> None:
        """Segmented total mode has correct segment names and counts."""
        qr = QueryResult(
            computed_at="",
            from_date="",
            to_date="",
            series={
                "Login [Total Events]": {
                    "$overall": {"all": 500},
                    "US": {"all": 300},
                    "EU": {"all": 200},
                },
            },
            params={},
            meta={},
        )
        df = qr.df
        # $overall + US + EU = 3 rows
        assert len(df) == 3
        us_rows = df[df["segment"] == "US"]
        assert len(us_rows) == 1
        assert us_rows.iloc[0]["count"] == 300

    def test_segmented_timeseries_columns(self) -> None:
        """Segmented timeseries produces date, event, segment, count columns."""
        qr = QueryResult(
            computed_at="",
            from_date="",
            to_date="",
            series={
                "Login [Total Events]": {
                    "$overall": {"2024-01-01": 100, "2024-01-02": 120},
                    "US": {"2024-01-01": 60, "2024-01-02": 72},
                    "EU": {"2024-01-01": 40, "2024-01-02": 48},
                },
            },
            params={},
            meta={},
        )
        df = qr.df
        assert list(df.columns) == ["date", "event", "segment", "count"]

    def test_segmented_timeseries_scalar_counts(self) -> None:
        """Segmented timeseries count column contains scalar integers."""
        qr = QueryResult(
            computed_at="",
            from_date="",
            to_date="",
            series={
                "Login [Total Events]": {
                    "$overall": {"2024-01-01": 100},
                    "US": {"2024-01-01": 60},
                },
            },
            params={},
            meta={},
        )
        df = qr.df
        for val in df["count"]:
            assert isinstance(val, (int, float)), (
                f"count should be scalar, got {type(val)}: {val}"
            )

    def test_segmented_timeseries_values(self) -> None:
        """Segmented timeseries has correct date, segment, count values."""
        qr = QueryResult(
            computed_at="",
            from_date="",
            to_date="",
            series={
                "Login [Total Events]": {
                    "US": {"2024-01-01": 60, "2024-01-02": 72},
                    "EU": {"2024-01-01": 40, "2024-01-02": 48},
                },
            },
            params={},
            meta={},
        )
        df = qr.df
        assert len(df) == 4
        us_jan1 = df[(df["segment"] == "US") & (df["date"] == "2024-01-01")]
        assert len(us_jan1) == 1
        assert us_jan1.iloc[0]["count"] == 60

    def test_segmented_timeseries_strips_timezone(self) -> None:
        """Segmented timeseries normalizes timezone offsets from ISO timestamps."""
        qr = QueryResult(
            computed_at="",
            from_date="",
            to_date="",
            series={
                "Login [Total Events]": {
                    "US": {"2024-01-01T00:00:00-07:00": 60},
                },
            },
            params={},
            meta={},
        )
        df = qr.df
        assert df.iloc[0]["date"] == "2024-01-01T00:00:00"

    def test_segmented_multi_metric(self) -> None:
        """Multiple metrics each with segments produce correct rows."""
        qr = QueryResult(
            computed_at="",
            from_date="",
            to_date="",
            series={
                "Login [Total]": {
                    "US": {"all": 300},
                    "EU": {"all": 200},
                },
                "Signup [Total]": {
                    "US": {"all": 50},
                    "EU": {"all": 30},
                },
            },
            params={},
            meta={},
        )
        df = qr.df
        assert len(df) == 4
        login_us = df[(df["event"] == "Login [Total]") & (df["segment"] == "US")]
        assert login_us.iloc[0]["count"] == 300


class TestQueryResultToDict:
    """Tests for QueryResult.to_dict() serialization."""

    def test_to_dict_contains_all_fields(self) -> None:
        """to_dict() returns all QueryResult fields."""
        qr = QueryResult(
            computed_at="ts",
            from_date="f",
            to_date="t",
            headers=["h"],
            series={"s": {}},
            params={"p": 1},
            meta={"m": 2},
        )
        d = qr.to_dict()
        assert d["computed_at"] == "ts"
        assert d["from_date"] == "f"
        assert d["to_date"] == "t"
        assert d["headers"] == ["h"]
        assert d["series"] == {"s": {}}
        assert d["params"] == {"p": 1}
        assert d["meta"] == {"m": 2}


# =============================================================================
# T022: Filter class method tests (US3)
# =============================================================================


class TestFilterConstruction:
    """Tests for Filter class method construction."""

    def test_equals_string(self) -> None:
        """Filter.equals creates correct filter."""
        from mixpanel_headless.types import Filter

        f = Filter.equals("country", "US")
        assert f._property == "country"
        assert f._operator == "equals"
        assert f._value == ["US"]
        assert f._property_type == "string"

    def test_equals_list(self) -> None:
        """Filter.equals with list preserves list."""
        from mixpanel_headless.types import Filter

        f = Filter.equals("country", ["US", "CA"])
        assert f._value == ["US", "CA"]

    def test_not_equals(self) -> None:
        """Filter.not_equals creates correct filter."""
        from mixpanel_headless.types import Filter

        f = Filter.not_equals("browser", "IE")
        assert f._operator == "does not equal"

    def test_contains(self) -> None:
        """Filter.contains uses plain string value."""
        from mixpanel_headless.types import Filter

        f = Filter.contains("browser", "Chrome")
        assert f._operator == "contains"
        assert f._value == "Chrome"

    def test_not_contains(self) -> None:
        """Filter.not_contains creates correct filter."""
        from mixpanel_headless.types import Filter

        f = Filter.not_contains("url", "test")
        assert f._operator == "does not contain"

    def test_greater_than(self) -> None:
        """Filter.greater_than creates numeric filter."""
        from mixpanel_headless.types import Filter

        f = Filter.greater_than("age", 18)
        assert f._operator == "is greater than"
        assert f._value == 18
        assert f._property_type == "number"

    def test_less_than(self) -> None:
        """Filter.less_than creates numeric filter."""
        from mixpanel_headless.types import Filter

        f = Filter.less_than("amount", 100)
        assert f._operator == "is less than"
        assert f._value == 100

    def test_between(self) -> None:
        """Filter.between creates range filter."""
        from mixpanel_headless.types import Filter

        f = Filter.between("age", 18, 65)
        assert f._operator == "is between"
        assert f._value == [18, 65]

    def test_is_set(self) -> None:
        """Filter.is_set creates existence filter."""
        from mixpanel_headless.types import Filter

        f = Filter.is_set("email")
        assert f._operator == "is set"
        assert f._value is None

    def test_is_not_set(self) -> None:
        """Filter.is_not_set creates non-existence filter."""
        from mixpanel_headless.types import Filter

        f = Filter.is_not_set("phone")
        assert f._operator == "is not set"

    def test_is_true(self) -> None:
        """Filter.is_true creates boolean filter."""
        from mixpanel_headless.types import Filter

        f = Filter.is_true("verified")
        assert f._operator == "true"
        assert f._property_type == "boolean"

    def test_is_false(self) -> None:
        """Filter.is_false creates boolean filter."""
        from mixpanel_headless.types import Filter

        f = Filter.is_false("opted_out")
        assert f._operator == "false"

    def test_immutability(self) -> None:
        """Filter is frozen."""
        from mixpanel_headless.types import Filter

        f = Filter.equals("country", "US")
        with pytest.raises(AttributeError):
            f._property = "browser"  # type: ignore[misc]

    def test_resource_type_default(self) -> None:
        """Default resource_type is 'events'."""
        from mixpanel_headless.types import Filter

        f = Filter.equals("country", "US")
        assert f._resource_type == "events"

    def test_resource_type_people(self) -> None:
        """resource_type='people' is supported."""
        from mixpanel_headless.types import Filter

        f = Filter.equals("city", "SF", resource_type="people")
        assert f._resource_type == "people"


# =============================================================================
# T023: GroupBy construction tests (US3)
# =============================================================================


class TestGroupByConstruction:
    """Tests for GroupBy frozen dataclass construction."""

    def test_string_property_defaults(self) -> None:
        """GroupBy with property only uses string type default."""
        from mixpanel_headless.types import GroupBy

        g = GroupBy("country")
        assert g.property == "country"
        assert g.property_type == "string"
        assert g.bucket_size is None

    def test_numeric_with_buckets(self) -> None:
        """GroupBy with full numeric bucketing."""
        from mixpanel_headless.types import GroupBy

        g = GroupBy(
            "revenue",
            property_type="number",
            bucket_size=50,
            bucket_min=0,
            bucket_max=500,
        )
        assert g.property_type == "number"
        assert g.bucket_size == 50
        assert g.bucket_min == 0
        assert g.bucket_max == 500

    def test_immutability(self) -> None:
        """GroupBy is frozen."""
        from mixpanel_headless.types import GroupBy

        g = GroupBy("country")
        with pytest.raises(AttributeError):
            g.property = "city"  # type: ignore[misc]

    def test_equality(self) -> None:
        """Two GroupBys with same fields are equal."""
        from mixpanel_headless.types import GroupBy

        g1 = GroupBy("country")
        g2 = GroupBy("country")
        assert g1 == g2


# =============================================================================
# Metric.filters_combinator tests
# =============================================================================


class TestMetricFiltersCombinator:
    """Tests for Metric.filters_combinator field."""

    def test_default_is_all(self) -> None:
        """filters_combinator defaults to 'all'."""
        m = Metric("Login")
        assert m.filters_combinator == "all"

    def test_set_to_any(self) -> None:
        """filters_combinator can be set to 'any'."""
        m = Metric("Login", filters_combinator="any")
        assert m.filters_combinator == "any"

    def test_equality_includes_combinator(self) -> None:
        """Metrics with different filters_combinator are not equal."""
        m1 = Metric("Login", filters_combinator="all")
        m2 = Metric("Login", filters_combinator="any")
        assert m1 != m2


# =============================================================================
# Formula dataclass tests
# =============================================================================


class TestFormulaConstruction:
    """Tests for Formula frozen dataclass construction and defaults."""

    def test_expression_only(self) -> None:
        """Formula with expression only uses None label."""
        f = Formula("(B / A) * 100")
        assert f.expression == "(B / A) * 100"
        assert f.label is None

    def test_expression_with_label(self) -> None:
        """Formula with expression and label."""
        f = Formula("(B / A) * 100", label="Conversion %")
        assert f.expression == "(B / A) * 100"
        assert f.label == "Conversion %"

    def test_immutability(self) -> None:
        """Formula is frozen."""
        f = Formula("A + B")
        with pytest.raises(AttributeError):
            f.expression = "C + D"  # type: ignore[misc]

    def test_equality(self) -> None:
        """Two Formulas with same fields are equal."""
        f1 = Formula("A + B", label="Sum")
        f2 = Formula("A + B", label="Sum")
        assert f1 == f2

    def test_inequality(self) -> None:
        """Formulas with different expressions are not equal."""
        assert Formula("A + B") != Formula("A - B")


# =============================================================================
# T055: Date filter factory methods
# =============================================================================


class TestDateFilterConstruction:
    """T055: Date filter factory methods on Filter class."""

    def test_on_creates_datetime_filter(self) -> None:
        """Filter.on() creates absolute date equality filter."""
        f = Filter.on("created", "2024-06-15")
        assert f._property == "created"
        assert f._operator == "was on"
        assert f._value == "2024-06-15"
        assert f._property_type == "datetime"
        assert f._date_unit is None

    def test_not_on(self) -> None:
        """Filter.not_on() creates date inequality filter."""
        f = Filter.not_on("created", "2024-06-15")
        assert f._operator == "was not on"
        assert f._value == "2024-06-15"
        assert f._property_type == "datetime"

    def test_before(self) -> None:
        """Filter.before() creates date before filter."""
        f = Filter.before("created", "2024-01-01")
        assert f._operator == "was before"
        assert f._value == "2024-01-01"
        assert f._property_type == "datetime"
        assert f._date_unit is None

    def test_since(self) -> None:
        """Filter.since() creates date since filter."""
        f = Filter.since("created", "2024-01-01")
        assert f._operator == "was since"
        assert f._value == "2024-01-01"
        assert f._property_type == "datetime"

    def test_in_the_last(self) -> None:
        """Filter.in_the_last() creates relative date filter with date_unit."""
        f = Filter.in_the_last("created", 7, "day")
        assert f._operator == "was in the"
        assert f._value == 7
        assert f._date_unit == "day"
        assert f._property_type == "datetime"

    def test_not_in_the_last(self) -> None:
        """Filter.not_in_the_last() creates relative negation filter."""
        f = Filter.not_in_the_last("created", 30, "day")
        assert f._operator == "was not in the"
        assert f._value == 30
        assert f._date_unit == "day"
        assert f._property_type == "datetime"

    def test_date_between(self) -> None:
        """Filter.date_between() creates date range filter."""
        f = Filter.date_between("created", "2024-01-01", "2024-06-30")
        assert f._operator == "was between"
        assert f._value == ["2024-01-01", "2024-06-30"]
        assert f._property_type == "datetime"
        assert f._date_unit is None

    def test_in_the_last_hour_unit(self) -> None:
        """Filter.in_the_last() supports hour unit."""
        f = Filter.in_the_last("ts", 24, "hour")
        assert f._date_unit == "hour"

    def test_in_the_last_month_unit(self) -> None:
        """Filter.in_the_last() supports month unit."""
        f = Filter.in_the_last("ts", 3, "month")
        assert f._date_unit == "month"

    def test_in_the_last_week_unit(self) -> None:
        """Filter.in_the_last() supports week unit."""
        f = Filter.in_the_last("ts", 2, "week")
        assert f._date_unit == "week"

    def test_immutability_date_filter(self) -> None:
        """Date filter is frozen."""
        f = Filter.on("created", "2024-01-01")
        with pytest.raises(AttributeError):
            f._date_unit = "day"  # type: ignore[misc]

    def test_resource_type_on_date_filter(self) -> None:
        """Date filters support resource_type parameter."""
        f = Filter.on("$created", "2024-01-01", resource_type="people")
        assert f._resource_type == "people"


# =============================================================================
# T056: Date filter input validation
# =============================================================================


class TestDateFilterValidation:
    """T056: Date filter factory method input validation."""

    def test_on_rejects_invalid_date_format(self) -> None:
        """Filter.on() rejects non-YYYY-MM-DD date string."""
        with pytest.raises(ValueError, match="YYYY-MM-DD"):
            Filter.on("created", "06/15/2024")

    def test_on_rejects_invalid_calendar_date(self) -> None:
        """Filter.on() rejects impossible calendar date."""
        with pytest.raises(ValueError, match="valid calendar date"):
            Filter.on("created", "2024-02-30")

    def test_before_rejects_invalid_date(self) -> None:
        """Filter.before() rejects invalid date string."""
        with pytest.raises(ValueError, match="YYYY-MM-DD"):
            Filter.before("created", "bad-date")

    def test_since_rejects_invalid_date(self) -> None:
        """Filter.since() rejects invalid date string."""
        with pytest.raises(ValueError, match="YYYY-MM-DD"):
            Filter.since("created", "2024/01/01")

    def test_date_between_rejects_invalid_from(self) -> None:
        """Filter.date_between() rejects invalid from_date."""
        with pytest.raises(ValueError, match="YYYY-MM-DD"):
            Filter.date_between("created", "bad", "2024-06-30")

    def test_date_between_rejects_invalid_to(self) -> None:
        """Filter.date_between() rejects invalid to_date."""
        with pytest.raises(ValueError, match="YYYY-MM-DD"):
            Filter.date_between("created", "2024-01-01", "bad")

    def test_date_between_rejects_reversed_dates(self) -> None:
        """Filter.date_between() rejects from > to."""
        with pytest.raises(ValueError, match="must be before"):
            Filter.date_between("created", "2024-12-31", "2024-01-01")

    def test_in_the_last_rejects_zero(self) -> None:
        """Filter.in_the_last() rejects non-positive quantity."""
        with pytest.raises(ValueError, match="positive"):
            Filter.in_the_last("created", 0, "day")

    def test_in_the_last_rejects_negative(self) -> None:
        """Filter.in_the_last() rejects negative quantity."""
        with pytest.raises(ValueError, match="positive"):
            Filter.in_the_last("created", -5, "day")

    def test_not_in_the_last_rejects_zero(self) -> None:
        """Filter.not_in_the_last() rejects non-positive quantity."""
        with pytest.raises(ValueError, match="positive"):
            Filter.not_in_the_last("created", 0, "week")


# =============================================================================
# T063: Custom percentile type support
# =============================================================================


class TestPercentileType:
    """T063: Custom percentile support."""

    def test_math_type_accepts_percentile(self) -> None:
        """MathType literal accepts 'percentile'."""
        m = Metric("Login", math="percentile", property="duration", percentile_value=95)
        assert m.math == "percentile"

    def test_percentile_value_default_none(self) -> None:
        """Metric.percentile_value defaults to None."""
        assert Metric("Login").percentile_value is None

    def test_percentile_value_int(self) -> None:
        """Metric.percentile_value accepts int."""
        m = Metric("Login", math="percentile", property="duration", percentile_value=95)
        assert m.percentile_value == 95

    def test_percentile_value_float(self) -> None:
        """Metric.percentile_value accepts float."""
        m = Metric("X", math="percentile", property="d", percentile_value=99.9)
        assert m.percentile_value == 99.9

    def test_percentile_immutable(self) -> None:
        """percentile_value is frozen."""
        m = Metric("Login", math="percentile", property="d", percentile_value=95)
        with pytest.raises(AttributeError):
            m.percentile_value = 50  # type: ignore[misc]


# =============================================================================
# T067: Histogram math type
# =============================================================================


class TestHistogramType:
    """T067: Histogram math type."""

    def test_math_type_accepts_histogram(self) -> None:
        """MathType literal accepts 'histogram'."""
        m = Metric("Purchase", math="histogram", property="amount")
        assert m.math == "histogram"

    def test_histogram_in_requiring_property(self) -> None:
        """'histogram' is in MATH_REQUIRING_PROPERTY."""
        assert "histogram" in MATH_REQUIRING_PROPERTY


# =============================================================================
# T004: New math types — non-property-requiring
# =============================================================================


class TestNewMathTypesNoProperty:
    """T004: cumulative_unique and sessions math types need no property."""

    @pytest.mark.parametrize("math_type", ["cumulative_unique", "sessions"])
    def test_new_math_no_property_succeeds(self, math_type: str) -> None:
        """Metric with math={math_type} succeeds without property."""
        m = Metric("Login", math=math_type)  # type: ignore[arg-type]
        assert m.math == math_type
        assert m.property is None

    @pytest.mark.parametrize("math_type", ["cumulative_unique", "sessions"])
    def test_new_math_no_property_with_property_also_works(
        self, math_type: str
    ) -> None:
        """Metric with math={math_type} also accepts an optional property."""
        m = Metric("Login", math=math_type, property="duration")  # type: ignore[arg-type]
        assert m.math == math_type
        assert m.property == "duration"


# =============================================================================
# T004: New math types — property-requiring
# =============================================================================


class TestNewMathTypesPropertyRequired:
    """T004: unique_values, most_frequent, first_value, multi_attribution, numeric_summary require property."""

    @pytest.mark.parametrize(
        "math_type",
        [
            "unique_values",
            "most_frequent",
            "first_value",
            "multi_attribution",
            "numeric_summary",
        ],
    )
    def test_new_math_with_property_succeeds(self, math_type: str) -> None:
        """Metric with math={math_type} and property set succeeds."""
        m = Metric("Login", math=math_type, property="amount")  # type: ignore[arg-type]
        assert m.math == math_type
        assert m.property == "amount"

    @pytest.mark.parametrize(
        "math_type",
        [
            "unique_values",
            "most_frequent",
            "first_value",
            "multi_attribution",
            "numeric_summary",
        ],
    )
    def test_new_math_without_property_raises(self, math_type: str) -> None:
        """Metric with math={math_type} but no property raises ValueError."""
        with pytest.raises(ValueError, match="requires a property"):
            Metric("Login", math=math_type)  # type: ignore[arg-type]

    @pytest.mark.parametrize(
        "math_type",
        [
            "unique_values",
            "most_frequent",
            "first_value",
            "multi_attribution",
            "numeric_summary",
        ],
    )
    def test_new_math_in_requiring_property_set(self, math_type: str) -> None:
        """New property-requiring math type is in MATH_REQUIRING_PROPERTY."""
        assert math_type in MATH_REQUIRING_PROPERTY


# =============================================================================
# T008: Metric with segment_method
# =============================================================================


class TestMetricSegmentMethod:
    """T008: Tests for Metric.segment_method field."""

    def test_segment_method_first_construction(self) -> None:
        """Metric('evt', segment_method='first') construction succeeds."""
        m = Metric("evt", segment_method="first")
        assert m.segment_method == "first"

    def test_segment_method_all_construction(self) -> None:
        """Metric('evt', segment_method='all') construction succeeds."""
        m = Metric("evt", segment_method="all")
        assert m.segment_method == "all"

    def test_segment_method_default_none(self) -> None:
        """Metric('evt') has segment_method=None by default."""
        m = Metric("evt")
        assert m.segment_method is None

    def test_segment_method_immutable(self) -> None:
        """Metric.segment_method is frozen."""
        m = Metric("evt", segment_method="first")
        with pytest.raises(AttributeError):
            m.segment_method = "all"  # type: ignore[misc]

    def test_segment_method_equality(self) -> None:
        """Metrics with different segment_method are not equal."""
        m1 = Metric("evt", segment_method="first")
        m2 = Metric("evt", segment_method="all")
        assert m1 != m2

    def test_segment_method_none_vs_unset_equal(self) -> None:
        """Metric with segment_method=None equals Metric without segment_method."""
        m1 = Metric("evt", segment_method=None)
        m2 = Metric("evt")
        assert m1 == m2


# =============================================================================
# T014: TimeComparison dataclass tests
# =============================================================================


class TestTimeComparison:
    """Tests for TimeComparison frozen dataclass construction and validation."""

    def test_relative_factory_creates_correct_instance(self) -> None:
        """TimeComparison.relative('month') creates type='relative', unit='month'."""
        from mixpanel_headless.types import TimeComparison

        tc = TimeComparison.relative("month")
        assert tc.type == "relative"
        assert tc.unit == "month"
        assert tc.date is None

    def test_absolute_start_factory_creates_correct_instance(self) -> None:
        """TimeComparison.absolute_start('2026-01-01') creates correct instance."""
        from mixpanel_headless.types import TimeComparison

        tc = TimeComparison.absolute_start("2026-01-01")
        assert tc.type == "absolute-start"
        assert tc.date == "2026-01-01"
        assert tc.unit is None

    def test_absolute_end_factory_creates_correct_instance(self) -> None:
        """TimeComparison.absolute_end('2026-12-31') creates correct instance."""
        from mixpanel_headless.types import TimeComparison

        tc = TimeComparison.absolute_end("2026-12-31")
        assert tc.type == "absolute-end"
        assert tc.date == "2026-12-31"
        assert tc.unit is None

    def test_tc1_relative_requires_unit(self) -> None:
        """TC1: type='relative' requires unit to be set."""
        from mixpanel_headless.types import TimeComparison

        with pytest.raises(ValueError, match="unit"):
            TimeComparison(type="relative", unit=None, date=None)

    def test_tc1_relative_rejects_date(self) -> None:
        """TC1: type='relative' rejects date being set."""
        from mixpanel_headless.types import TimeComparison

        with pytest.raises(ValueError, match="date"):
            TimeComparison(type="relative", unit="month", date="2026-01-01")

    def test_tc2_absolute_start_requires_date(self) -> None:
        """TC2: type='absolute-start' requires date to be set."""
        from mixpanel_headless.types import TimeComparison

        with pytest.raises(ValueError, match="date"):
            TimeComparison(type="absolute-start", unit=None, date=None)

    def test_tc2_absolute_start_rejects_unit(self) -> None:
        """TC2: type='absolute-start' rejects unit being set."""
        from mixpanel_headless.types import TimeComparison

        with pytest.raises(ValueError, match="unit"):
            TimeComparison(type="absolute-start", unit="month", date="2026-01-01")

    def test_tc2_absolute_end_requires_date(self) -> None:
        """TC2: type='absolute-end' requires date to be set."""
        from mixpanel_headless.types import TimeComparison

        with pytest.raises(ValueError, match="date"):
            TimeComparison(type="absolute-end", unit=None, date=None)

    def test_tc2_absolute_end_rejects_unit(self) -> None:
        """TC2: type='absolute-end' rejects unit being set."""
        from mixpanel_headless.types import TimeComparison

        with pytest.raises(ValueError, match="unit"):
            TimeComparison(type="absolute-end", unit="month", date="2026-12-31")

    def test_tc3_invalid_date_format_raises(self) -> None:
        """TC3: date must match YYYY-MM-DD format."""
        from mixpanel_headless.types import TimeComparison

        with pytest.raises(ValueError, match="YYYY-MM-DD"):
            TimeComparison.absolute_start("01-01-2026")

    def test_tc3_invalid_date_format_partial(self) -> None:
        """TC3: date='2026-1-1' (missing leading zeros) is rejected."""
        from mixpanel_headless.types import TimeComparison

        with pytest.raises(ValueError, match="YYYY-MM-DD"):
            TimeComparison.absolute_start("2026-1-1")

    def test_frozen_immutable(self) -> None:
        """TimeComparison is frozen and cannot be modified after construction."""
        from mixpanel_headless.types import TimeComparison

        tc = TimeComparison.relative("month")
        with pytest.raises(AttributeError):
            tc.type = "absolute-start"  # type: ignore[misc]

    def test_equality_same_fields(self) -> None:
        """Two TimeComparisons with identical fields are equal."""
        from mixpanel_headless.types import TimeComparison

        tc1 = TimeComparison.relative("month")
        tc2 = TimeComparison.relative("month")
        assert tc1 == tc2

    def test_inequality_different_type(self) -> None:
        """TimeComparisons with different types are not equal."""
        from mixpanel_headless.types import TimeComparison

        tc1 = TimeComparison.relative("month")
        tc2 = TimeComparison.absolute_start("2026-01-01")
        assert tc1 != tc2

    def test_relative_all_valid_units(self) -> None:
        """All valid TimeComparisonUnit values create successfully."""
        from mixpanel_headless.types import TimeComparison

        for unit in ("day", "week", "month", "quarter", "year"):
            tc = TimeComparison.relative(unit)
            assert tc.unit == unit


# =============================================================================
# T021: FrequencyBreakdown dataclass tests (US4)
# =============================================================================


class TestFrequencyBreakdownConstruction:
    """Tests for FrequencyBreakdown frozen dataclass construction and defaults."""

    def test_event_only_uses_defaults(self) -> None:
        """FrequencyBreakdown('Purchase') uses default bucket params."""
        from mixpanel_headless.types import FrequencyBreakdown

        fb = FrequencyBreakdown("Purchase")
        assert fb.event == "Purchase"
        assert fb.bucket_size == 1
        assert fb.bucket_min == 0
        assert fb.bucket_max == 10
        assert fb.label is None

    def test_all_fields_set(self) -> None:
        """FrequencyBreakdown with all fields explicitly set."""
        from mixpanel_headless.types import FrequencyBreakdown

        fb = FrequencyBreakdown(
            "Purchase",
            bucket_size=5,
            bucket_min=0,
            bucket_max=50,
            label="Purchase Frequency",
        )
        assert fb.event == "Purchase"
        assert fb.bucket_size == 5
        assert fb.bucket_min == 0
        assert fb.bucket_max == 50
        assert fb.label == "Purchase Frequency"

    def test_immutability(self) -> None:
        """FrequencyBreakdown is frozen and cannot be modified."""
        from mixpanel_headless.types import FrequencyBreakdown

        fb = FrequencyBreakdown("Purchase")
        with pytest.raises(AttributeError):
            fb.event = "Login"  # type: ignore[misc]

    def test_equality_same_fields(self) -> None:
        """Two FrequencyBreakdowns with identical fields are equal."""
        from mixpanel_headless.types import FrequencyBreakdown

        fb1 = FrequencyBreakdown("Purchase")
        fb2 = FrequencyBreakdown("Purchase")
        assert fb1 == fb2

    def test_inequality_different_event(self) -> None:
        """FrequencyBreakdowns with different events are not equal."""
        from mixpanel_headless.types import FrequencyBreakdown

        assert FrequencyBreakdown("Purchase") != FrequencyBreakdown("Login")


class TestFrequencyBreakdownValidation:
    """Tests for FrequencyBreakdown validation rules FB1-FB4."""

    def test_fb1_empty_event_raises(self) -> None:
        """FB1: event must be non-empty."""
        from mixpanel_headless.types import FrequencyBreakdown

        with pytest.raises(ValueError, match="non-empty"):
            FrequencyBreakdown("")

    def test_fb1_whitespace_event_raises(self) -> None:
        """FB1: whitespace-only event must be rejected."""
        from mixpanel_headless.types import FrequencyBreakdown

        with pytest.raises(ValueError, match="non-empty"):
            FrequencyBreakdown("   ")

    def test_fb2_zero_bucket_size_raises(self) -> None:
        """FB2: bucket_size must be positive (> 0)."""
        from mixpanel_headless.types import FrequencyBreakdown

        with pytest.raises(ValueError, match="positive"):
            FrequencyBreakdown("Purchase", bucket_size=0)

    def test_fb2_negative_bucket_size_raises(self) -> None:
        """FB2: negative bucket_size must be rejected."""
        from mixpanel_headless.types import FrequencyBreakdown

        with pytest.raises(ValueError, match="positive"):
            FrequencyBreakdown("Purchase", bucket_size=-1)

    def test_fb3_bucket_min_equals_max_raises(self) -> None:
        """FB3: bucket_min must be < bucket_max."""
        from mixpanel_headless.types import FrequencyBreakdown

        with pytest.raises(ValueError, match="less than"):
            FrequencyBreakdown("Purchase", bucket_min=10, bucket_max=10)

    def test_fb3_bucket_min_greater_than_max_raises(self) -> None:
        """FB3: bucket_min > bucket_max must be rejected."""
        from mixpanel_headless.types import FrequencyBreakdown

        with pytest.raises(ValueError, match="less than"):
            FrequencyBreakdown("Purchase", bucket_min=20, bucket_max=10)

    def test_fb4_negative_bucket_min_raises(self) -> None:
        """FB4: bucket_min must be >= 0."""
        from mixpanel_headless.types import FrequencyBreakdown

        with pytest.raises(ValueError, match="non-negative"):
            FrequencyBreakdown("Purchase", bucket_min=-1)


# =============================================================================
# T021: FrequencyFilter dataclass tests (US4)
# =============================================================================


class TestFrequencyFilterConstruction:
    """Tests for FrequencyFilter frozen dataclass construction and defaults."""

    def test_event_and_value_uses_defaults(self) -> None:
        """FrequencyFilter('Login', value=5) uses default operator."""
        from mixpanel_headless.types import FrequencyFilter

        ff = FrequencyFilter("Login", value=5)
        assert ff.event == "Login"
        assert ff.operator == "is at least"
        assert ff.value == 5
        assert ff.date_range_value is None
        assert ff.date_range_unit is None
        assert ff.event_filters is None
        assert ff.label is None

    def test_all_fields_set(self) -> None:
        """FrequencyFilter with all fields explicitly set."""
        from mixpanel_headless.types import FrequencyFilter

        ff = FrequencyFilter(
            "Login",
            operator="is greater than",
            value=10,
            date_range_value=30,
            date_range_unit="day",
            event_filters=[Filter.equals("country", "US")],
            label="Active Users",
        )
        assert ff.event == "Login"
        assert ff.operator == "is greater than"
        assert ff.value == 10
        assert ff.date_range_value == 30
        assert ff.date_range_unit == "day"
        assert ff.event_filters is not None
        assert len(ff.event_filters) == 1
        assert ff.label == "Active Users"

    def test_immutability(self) -> None:
        """FrequencyFilter is frozen and cannot be modified."""
        from mixpanel_headless.types import FrequencyFilter

        ff = FrequencyFilter("Login", value=5)
        with pytest.raises(AttributeError):
            ff.event = "Signup"  # type: ignore[misc]

    def test_equality_same_fields(self) -> None:
        """Two FrequencyFilters with identical fields are equal."""
        from mixpanel_headless.types import FrequencyFilter

        ff1 = FrequencyFilter("Login", value=5)
        ff2 = FrequencyFilter("Login", value=5)
        assert ff1 == ff2

    def test_float_value(self) -> None:
        """FrequencyFilter value accepts float."""
        from mixpanel_headless.types import FrequencyFilter

        ff = FrequencyFilter("Login", value=3.5)
        assert ff.value == 3.5

    def test_event_filters_list(self) -> None:
        """FrequencyFilter accepts multiple event_filters."""
        from mixpanel_headless.types import FrequencyFilter

        ff = FrequencyFilter(
            "Purchase",
            value=1,
            event_filters=[
                Filter.equals("country", "US"),
                Filter.greater_than("amount", 10),
            ],
        )
        assert ff.event_filters is not None
        assert len(ff.event_filters) == 2


class TestFrequencyFilterValidation:
    """Tests for FrequencyFilter validation rules FF1-FF5."""

    def test_ff1_empty_event_raises(self) -> None:
        """FF1: event must be non-empty."""
        from mixpanel_headless.types import FrequencyFilter

        with pytest.raises(ValueError, match="non-empty"):
            FrequencyFilter("", value=5)

    def test_ff1_whitespace_event_raises(self) -> None:
        """FF1: whitespace-only event must be rejected."""
        from mixpanel_headless.types import FrequencyFilter

        with pytest.raises(ValueError, match="non-empty"):
            FrequencyFilter("   ", value=5)

    def test_ff2_invalid_operator_raises(self) -> None:
        """FF2: operator must be in VALID_FREQUENCY_FILTER_OPERATORS."""
        from mixpanel_headless.types import FrequencyFilter

        with pytest.raises(ValueError, match="operator"):
            FrequencyFilter("Login", operator="invalid_op", value=5)  # type: ignore[arg-type]

    def test_ff2_all_valid_operators_accepted(self) -> None:
        """FF2: all valid operators are accepted."""
        from mixpanel_headless.types import FrequencyFilter

        valid_ops = [
            "is at least",
            "is at most",
            "is greater than",
            "is less than",
            "is equal to",
        ]
        for op in valid_ops:
            ff = FrequencyFilter("Login", operator=op, value=5)  # type: ignore[arg-type]
            assert ff.operator == op

    def test_ff3_negative_value_raises(self) -> None:
        """FF3: value must be non-negative (>= 0)."""
        from mixpanel_headless.types import FrequencyFilter

        with pytest.raises(ValueError, match="non-negative"):
            FrequencyFilter("Login", value=-1)

    def test_ff3_zero_value_accepted(self) -> None:
        """FF3: value=0 is valid."""
        from mixpanel_headless.types import FrequencyFilter

        ff = FrequencyFilter("Login", value=0)
        assert ff.value == 0

    def test_ff4_date_range_value_without_unit_raises(self) -> None:
        """FF4: date_range_value without date_range_unit raises."""
        from mixpanel_headless.types import FrequencyFilter

        with pytest.raises(ValueError, match="both.*set or both.*None"):
            FrequencyFilter("Login", value=5, date_range_value=30)

    def test_ff4_date_range_unit_without_value_raises(self) -> None:
        """FF4: date_range_unit without date_range_value raises."""
        from mixpanel_headless.types import FrequencyFilter

        with pytest.raises(ValueError, match="both.*set or both.*None"):
            FrequencyFilter("Login", value=5, date_range_unit="day")

    def test_ff4_both_none_accepted(self) -> None:
        """FF4: both date_range_value and date_range_unit None is valid."""
        from mixpanel_headless.types import FrequencyFilter

        ff = FrequencyFilter("Login", value=5)
        assert ff.date_range_value is None
        assert ff.date_range_unit is None

    def test_ff4_both_set_accepted(self) -> None:
        """FF4: both date_range_value and date_range_unit set is valid."""
        from mixpanel_headless.types import FrequencyFilter

        ff = FrequencyFilter(
            "Login", value=5, date_range_value=30, date_range_unit="day"
        )
        assert ff.date_range_value == 30
        assert ff.date_range_unit == "day"

    def test_ff5_zero_date_range_value_raises(self) -> None:
        """FF5: date_range_value must be positive if set."""
        from mixpanel_headless.types import FrequencyFilter

        with pytest.raises(ValueError, match="positive"):
            FrequencyFilter("Login", value=5, date_range_value=0, date_range_unit="day")

    def test_ff5_negative_date_range_value_raises(self) -> None:
        """FF5: negative date_range_value must be rejected."""
        from mixpanel_headless.types import FrequencyFilter

        with pytest.raises(ValueError, match="positive"):
            FrequencyFilter(
                "Login", value=5, date_range_value=-7, date_range_unit="day"
            )


# =============================================================================
# T029: New Filter factory methods (US6 — Complete Filter Operator Coverage)
# =============================================================================


class TestNewFilterFactoryMethods:
    """T029: Tests for 7 new Filter factory methods."""

    # --- not_between ---

    def test_not_between_operator(self) -> None:
        """Filter.not_between() uses 'not between' operator."""
        f = Filter.not_between("age", 18, 65)
        assert f._operator == "not between"

    def test_not_between_property_type(self) -> None:
        """Filter.not_between() sets property_type to 'number'."""
        f = Filter.not_between("age", 18, 65)
        assert f._property_type == "number"

    def test_not_between_value(self) -> None:
        """Filter.not_between() stores [min, max] as value."""
        f = Filter.not_between("amount", 10, 100)
        assert f._value == [10, 100]

    def test_not_between_property(self) -> None:
        """Filter.not_between() stores property name."""
        f = Filter.not_between("age", 18, 65)
        assert f._property == "age"

    def test_not_between_resource_type_default(self) -> None:
        """Filter.not_between() defaults to resource_type='events'."""
        f = Filter.not_between("age", 18, 65)
        assert f._resource_type == "events"

    def test_not_between_resource_type_people(self) -> None:
        """Filter.not_between() accepts resource_type='people'."""
        f = Filter.not_between("age", 18, 65, resource_type="people")
        assert f._resource_type == "people"

    # --- starts_with ---

    def test_starts_with_operator(self) -> None:
        """Filter.starts_with() uses 'starts with' operator."""
        f = Filter.starts_with("url", "https://")
        assert f._operator == "starts with"

    def test_starts_with_property_type(self) -> None:
        """Filter.starts_with() sets property_type to 'string'."""
        f = Filter.starts_with("url", "https://")
        assert f._property_type == "string"

    def test_starts_with_value(self) -> None:
        """Filter.starts_with() stores prefix as value."""
        f = Filter.starts_with("url", "https://")
        assert f._value == "https://"

    def test_starts_with_resource_type_people(self) -> None:
        """Filter.starts_with() accepts resource_type='people'."""
        f = Filter.starts_with("email", "admin@", resource_type="people")
        assert f._resource_type == "people"

    # --- ends_with ---

    def test_ends_with_operator(self) -> None:
        """Filter.ends_with() uses 'ends with' operator."""
        f = Filter.ends_with("email", "@example.com")
        assert f._operator == "ends with"

    def test_ends_with_property_type(self) -> None:
        """Filter.ends_with() sets property_type to 'string'."""
        f = Filter.ends_with("email", "@example.com")
        assert f._property_type == "string"

    def test_ends_with_value(self) -> None:
        """Filter.ends_with() stores suffix as value."""
        f = Filter.ends_with("email", "@example.com")
        assert f._value == "@example.com"

    def test_ends_with_resource_type_people(self) -> None:
        """Filter.ends_with() accepts resource_type='people'."""
        f = Filter.ends_with("email", ".edu", resource_type="people")
        assert f._resource_type == "people"

    # --- date_not_between ---

    def test_date_not_between_operator(self) -> None:
        """Filter.date_not_between() uses 'was not between' operator."""
        f = Filter.date_not_between("created", "2024-01-01", "2024-06-30")
        assert f._operator == "was not between"

    def test_date_not_between_property_type(self) -> None:
        """Filter.date_not_between() sets property_type to 'datetime'."""
        f = Filter.date_not_between("created", "2024-01-01", "2024-06-30")
        assert f._property_type == "datetime"

    def test_date_not_between_value(self) -> None:
        """Filter.date_not_between() stores [from, to] as value."""
        f = Filter.date_not_between("created", "2024-01-01", "2024-06-30")
        assert f._value == ["2024-01-01", "2024-06-30"]

    def test_date_not_between_no_date_unit(self) -> None:
        """Filter.date_not_between() has no date_unit."""
        f = Filter.date_not_between("created", "2024-01-01", "2024-06-30")
        assert f._date_unit is None

    def test_date_not_between_resource_type_people(self) -> None:
        """Filter.date_not_between() accepts resource_type='people'."""
        f = Filter.date_not_between(
            "$created", "2024-01-01", "2024-06-30", resource_type="people"
        )
        assert f._resource_type == "people"

    def test_date_not_between_rejects_invalid_from(self) -> None:
        """Filter.date_not_between() rejects invalid from_date."""
        with pytest.raises(ValueError, match="YYYY-MM-DD"):
            Filter.date_not_between("created", "bad", "2024-06-30")

    def test_date_not_between_rejects_invalid_to(self) -> None:
        """Filter.date_not_between() rejects invalid to_date."""
        with pytest.raises(ValueError, match="YYYY-MM-DD"):
            Filter.date_not_between("created", "2024-01-01", "bad")

    def test_date_not_between_rejects_reversed_dates(self) -> None:
        """Filter.date_not_between() rejects from > to."""
        with pytest.raises(ValueError, match="must be before"):
            Filter.date_not_between("created", "2024-12-31", "2024-01-01")

    # --- in_the_next ---

    def test_in_the_next_operator(self) -> None:
        """Filter.in_the_next() uses 'was in the next' operator."""
        f = Filter.in_the_next("expires", 7, "day")
        assert f._operator == "was in the next"

    def test_in_the_next_property_type(self) -> None:
        """Filter.in_the_next() sets property_type to 'datetime'."""
        f = Filter.in_the_next("expires", 7, "day")
        assert f._property_type == "datetime"

    def test_in_the_next_value(self) -> None:
        """Filter.in_the_next() stores quantity as value."""
        f = Filter.in_the_next("expires", 7, "day")
        assert f._value == 7

    def test_in_the_next_date_unit(self) -> None:
        """Filter.in_the_next() sets _date_unit correctly."""
        f = Filter.in_the_next("expires", 7, "day")
        assert f._date_unit == "day"

    def test_in_the_next_hour_unit(self) -> None:
        """Filter.in_the_next() supports hour unit."""
        f = Filter.in_the_next("expires", 24, "hour")
        assert f._date_unit == "hour"

    def test_in_the_next_week_unit(self) -> None:
        """Filter.in_the_next() supports week unit."""
        f = Filter.in_the_next("expires", 2, "week")
        assert f._date_unit == "week"

    def test_in_the_next_month_unit(self) -> None:
        """Filter.in_the_next() supports month unit."""
        f = Filter.in_the_next("expires", 3, "month")
        assert f._date_unit == "month"

    def test_in_the_next_resource_type_people(self) -> None:
        """Filter.in_the_next() accepts resource_type='people'."""
        f = Filter.in_the_next("renewal", 30, "day", resource_type="people")
        assert f._resource_type == "people"

    def test_in_the_next_rejects_zero(self) -> None:
        """Filter.in_the_next() rejects non-positive quantity."""
        with pytest.raises(ValueError, match="positive"):
            Filter.in_the_next("expires", 0, "day")

    def test_in_the_next_rejects_negative(self) -> None:
        """Filter.in_the_next() rejects negative quantity."""
        with pytest.raises(ValueError, match="positive"):
            Filter.in_the_next("expires", -5, "day")

    # --- at_least ---

    def test_at_least_operator(self) -> None:
        """Filter.at_least() uses 'is at least' operator."""
        f = Filter.at_least("score", 80)
        assert f._operator == "is at least"

    def test_at_least_property_type(self) -> None:
        """Filter.at_least() sets property_type to 'number'."""
        f = Filter.at_least("score", 80)
        assert f._property_type == "number"

    def test_at_least_value(self) -> None:
        """Filter.at_least() stores numeric value."""
        f = Filter.at_least("score", 80)
        assert f._value == 80

    def test_at_least_float_value(self) -> None:
        """Filter.at_least() accepts float value."""
        f = Filter.at_least("score", 79.5)
        assert f._value == 79.5

    def test_at_least_resource_type_people(self) -> None:
        """Filter.at_least() accepts resource_type='people'."""
        f = Filter.at_least("purchases", 10, resource_type="people")
        assert f._resource_type == "people"

    # --- at_most ---

    def test_at_most_operator(self) -> None:
        """Filter.at_most() uses 'is at most' operator."""
        f = Filter.at_most("errors", 5)
        assert f._operator == "is at most"

    def test_at_most_property_type(self) -> None:
        """Filter.at_most() sets property_type to 'number'."""
        f = Filter.at_most("errors", 5)
        assert f._property_type == "number"

    def test_at_most_value(self) -> None:
        """Filter.at_most() stores numeric value."""
        f = Filter.at_most("errors", 5)
        assert f._value == 5

    def test_at_most_float_value(self) -> None:
        """Filter.at_most() accepts float value."""
        f = Filter.at_most("latency", 99.9)
        assert f._value == 99.9

    def test_at_most_resource_type_people(self) -> None:
        """Filter.at_most() accepts resource_type='people'."""
        f = Filter.at_most("complaints", 3, resource_type="people")
        assert f._resource_type == "people"
