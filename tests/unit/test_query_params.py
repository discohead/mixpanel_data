"""Unit tests for bookmark params generation.

Tests _build_query_params() in Workspace for US1 (basic params),
US2 (aggregation), US3 (filters/groups), US4 (multi-event),
US5 (formula), US6 (analysis mode), US7 (result mode).
Also tests build_params() public helper (T054).
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from pydantic import SecretStr

from mixpanel_headless import Filter, Formula, GroupBy, Metric, Workspace
from mixpanel_headless._internal.auth.account import ServiceAccount
from mixpanel_headless._internal.auth.session import Project, Session
from mixpanel_headless._internal.bookmark_builders import build_filter_entry

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
# Fixtures
# =============================================================================


@pytest.fixture
def ws(mock_config_manager: MagicMock) -> Workspace:
    """Create Workspace with mocked dependencies for params testing."""
    return Workspace(session=_TEST_SESSION)


# =============================================================================
# T008: Basic bookmark params generation (US1)
# =============================================================================


class TestBasicParams:
    """Tests for basic bookmark params generation (single event, time range)."""

    def test_single_event_default_params(self, ws: Workspace) -> None:
        """Single event string produces correct sections.show entry."""
        params = ws._build_query_params(
            events=["Login"],
            math="total",
            math_property=None,
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
        # Verify sections.show has one entry
        show = params["sections"]["show"]
        assert len(show) == 1
        assert show[0]["behavior"]["name"] == "Login"

    def test_relative_time_last_n(self, ws: Workspace) -> None:
        """last=N produces dateRange with 'in the last N days' format."""
        params = ws._build_query_params(
            events=["Login"],
            math="total",
            math_property=None,
            per_user=None,
            from_date=None,
            to_date=None,
            last=7,
            unit="day",
            group_by=None,
            where=None,
            formulas=[],
            rolling=None,
            cumulative=False,
            mode="timeseries",
        )
        time_section = params["sections"]["time"][0]
        assert time_section["dateRangeType"] == "in the last"
        assert time_section["window"]["value"] == 7
        assert time_section["unit"] == "day"

    def test_absolute_time_range(self, ws: Workspace) -> None:
        """from_date/to_date produces dateRange with explicit dates."""
        params = ws._build_query_params(
            events=["Login"],
            math="total",
            math_property=None,
            per_user=None,
            from_date="2024-01-01",
            to_date="2024-01-31",
            last=30,
            unit="day",
            group_by=None,
            where=None,
            formulas=[],
            rolling=None,
            cumulative=False,
            mode="timeseries",
        )
        time_section = params["sections"]["time"][0]
        assert time_section["dateRangeType"] == "between"
        assert time_section["value"] == ["2024-01-01", "2024-01-31"]

    def test_from_date_only(self, ws: Workspace) -> None:
        """from_date without to_date uses 'since' range type."""
        params = ws._build_query_params(
            events=["Login"],
            math="total",
            math_property=None,
            per_user=None,
            from_date="2024-01-01",
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
        time_section = params["sections"]["time"][0]
        assert time_section["dateRangeType"] == "between"
        assert time_section["value"][0] == "2024-01-01"
        assert len(time_section["value"]) == 2

    def test_unit_mapping(self, ws: Workspace) -> None:
        """Unit parameter maps correctly to time section."""
        for unit in ("hour", "day", "week", "month", "quarter"):
            params = ws._build_query_params(
                events=["Login"],
                math="total",
                math_property=None,
                per_user=None,
                from_date=None,
                to_date=None,
                last=30,
                unit=unit,
                group_by=None,
                where=None,
                formulas=[],
                rolling=None,
                cumulative=False,
                mode="timeseries",
            )
            assert params["sections"]["time"][0]["unit"] == unit

    def test_default_display_options(self, ws: Workspace) -> None:
        """Default mode='timeseries' produces chartType='line' and analysis='linear'."""
        params = ws._build_query_params(
            events=["Login"],
            math="total",
            math_property=None,
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
        display = params["displayOptions"]
        assert display["chartType"] == "line"
        assert display["analysis"] == "linear"

    def test_show_entry_measurement_defaults(self, ws: Workspace) -> None:
        """Default measurement is total event count."""
        params = ws._build_query_params(
            events=["Login"],
            math="total",
            math_property=None,
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
        show_entry = params["sections"]["show"][0]
        assert show_entry["type"] == "metric"
        assert show_entry["measurement"]["math"] == "total"


# =============================================================================
# T017: Aggregation params (US2)
# =============================================================================


class TestAggregationParams:
    """Tests for aggregation params generation."""

    def test_math_unique(self, ws: Workspace) -> None:
        """math='unique' maps to event_type='unique'."""
        params = ws._build_query_params(
            events=["Login"],
            math="unique",
            math_property=None,
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
        assert params["sections"]["show"][0]["measurement"]["math"] == "unique"

    def test_math_dau(self, ws: Workspace) -> None:
        """math='dau' maps to event_type='dau'."""
        params = ws._build_query_params(
            events=["Login"],
            math="dau",
            math_property=None,
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
        assert params["sections"]["show"][0]["measurement"]["math"] == "dau"

    def test_math_property_mapping(self, ws: Workspace) -> None:
        """math_property maps to measurement.property."""
        params = ws._build_query_params(
            events=["Purchase"],
            math="average",
            math_property="amount",
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
        assert m["math"] == "average"
        assert m["property"]["name"] == "amount"

    def test_per_user_mapping(self, ws: Workspace) -> None:
        """per_user maps to measurement.perUserAggregation."""
        params = ws._build_query_params(
            events=["Purchase"],
            math="total",
            math_property="revenue",
            per_user="average",
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
        assert m["perUserAggregation"] == "average"

    def test_metric_overrides_top_level(self, ws: Workspace) -> None:
        """Metric objects override top-level math/property/per_user."""
        from mixpanel_headless import Metric

        params = ws._build_query_params(
            events=[Metric("Purchase", math="average", property="revenue")],
            math="total",
            math_property=None,
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
        assert m["math"] == "average"
        assert m["property"]["name"] == "revenue"


# =============================================================================
# T024-T025: Filter and Group params (US3)
# =============================================================================


class TestFilterParams:
    """Tests for filter params generation."""

    def test_string_filter_format(self, ws: Workspace) -> None:
        """Filter.equals produces correct filter entry."""
        from mixpanel_headless import Filter

        params = ws._build_query_params(
            events=["Login"],
            math="total",
            math_property=None,
            per_user=None,
            from_date=None,
            to_date=None,
            last=30,
            unit="day",
            group_by=None,
            where=[Filter.equals("country", "US")],
            formulas=[],
            rolling=None,
            cumulative=False,
            mode="timeseries",
        )
        f = params["sections"]["filter"][0]
        assert f["value"] == "country"
        assert f["filterOperator"] == "equals"
        assert f["filterValue"] == ["US"]
        assert f["filterType"] == "string"

    def test_numeric_filter_scalar_value(self, ws: Workspace) -> None:
        """Filter.greater_than produces scalar filterValue."""
        from mixpanel_headless import Filter

        params = ws._build_query_params(
            events=["Purchase"],
            math="total",
            math_property=None,
            per_user=None,
            from_date=None,
            to_date=None,
            last=30,
            unit="day",
            group_by=None,
            where=[Filter.greater_than("age", 18)],
            formulas=[],
            rolling=None,
            cumulative=False,
            mode="timeseries",
        )
        f = params["sections"]["filter"][0]
        assert f["filterValue"] == 18
        assert f["filterType"] == "number"

    def test_contains_filter_plain_string(self, ws: Workspace) -> None:
        """Filter.contains produces plain string filterValue."""
        from mixpanel_headless import Filter

        params = ws._build_query_params(
            events=["Login"],
            math="total",
            math_property=None,
            per_user=None,
            from_date=None,
            to_date=None,
            last=30,
            unit="day",
            group_by=None,
            where=[Filter.contains("browser", "Chrome")],
            formulas=[],
            rolling=None,
            cumulative=False,
            mode="timeseries",
        )
        f = params["sections"]["filter"][0]
        assert f["filterValue"] == "Chrome"

    def test_multiple_filters(self, ws: Workspace) -> None:
        """Multiple filters produce multiple entries."""
        from mixpanel_headless import Filter

        params = ws._build_query_params(
            events=["Purchase"],
            math="total",
            math_property=None,
            per_user=None,
            from_date=None,
            to_date=None,
            last=30,
            unit="day",
            group_by=None,
            where=[Filter.equals("country", "US"), Filter.greater_than("amount", 10)],
            formulas=[],
            rolling=None,
            cumulative=False,
            mode="timeseries",
        )
        assert len(params["sections"]["filter"]) == 2

    def test_empty_filter_section_when_none(self, ws: Workspace) -> None:
        """Empty filter section when where=None."""
        params = ws._build_query_params(
            events=["Login"],
            math="total",
            math_property=None,
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
        assert params["sections"]["filter"] == []

    def test_list_contains_filter_through_build_query_params(
        self, ws: Workspace
    ) -> None:
        """Filter.list_contains threads through _build_query_params end-to-end."""
        from mixpanel_headless import Filter

        params = ws._build_query_params(
            events=["Purchase Completed"],
            math="total",
            math_property=None,
            per_user=None,
            from_date=None,
            to_date=None,
            last=90,
            unit="day",
            group_by=None,
            where=[Filter.list_contains("cart", Brand="nike", Category="hats")],
            formulas=[],
            rolling=None,
            cumulative=False,
            mode="total",
        )
        assert len(params["sections"]["filter"]) == 1
        f = params["sections"]["filter"][0]
        assert f["filterType"] == "object"
        assert f["filterJoinType"] == "list"
        assert f["listQuantifier"] == "any"
        assert len(f["listItemFilters"]) == 2


class TestGroupParams:
    """Tests for group params generation."""

    def test_string_shorthand(self, ws: Workspace) -> None:
        """String group_by produces correct group entry."""
        params = ws._build_query_params(
            events=["Login"],
            math="total",
            math_property=None,
            per_user=None,
            from_date=None,
            to_date=None,
            last=30,
            unit="day",
            group_by="platform",
            where=None,
            formulas=[],
            rolling=None,
            cumulative=False,
            mode="timeseries",
        )
        g = params["sections"]["group"][0]
        assert g["value"] == "platform"
        assert g["propertyType"] == "string"

    def test_typed_groupby(self, ws: Workspace) -> None:
        """GroupBy object produces correct group entry."""
        from mixpanel_headless import GroupBy

        params = ws._build_query_params(
            events=["Purchase"],
            math="total",
            math_property=None,
            per_user=None,
            from_date=None,
            to_date=None,
            last=30,
            unit="day",
            group_by=GroupBy("amount", property_type="number"),
            where=None,
            formulas=[],
            rolling=None,
            cumulative=False,
            mode="timeseries",
        )
        g = params["sections"]["group"][0]
        assert g["value"] == "amount"
        assert g["propertyType"] == "number"

    def test_numeric_bucketing(self, ws: Workspace) -> None:
        """GroupBy with bucket_size produces customBucket."""
        from mixpanel_headless import GroupBy

        params = ws._build_query_params(
            events=["Purchase"],
            math="total",
            math_property=None,
            per_user=None,
            from_date=None,
            to_date=None,
            last=30,
            unit="day",
            group_by=GroupBy(
                "revenue",
                property_type="number",
                bucket_size=50,
                bucket_min=0,
                bucket_max=500,
            ),
            where=None,
            formulas=[],
            rolling=None,
            cumulative=False,
            mode="timeseries",
        )
        g = params["sections"]["group"][0]
        assert g["customBucket"]["bucketSize"] == 50
        assert g["customBucket"]["min"] == 0
        assert g["customBucket"]["max"] == 500

    def test_multiple_breakdowns(self, ws: Workspace) -> None:
        """List of group_by produces multiple entries."""
        params = ws._build_query_params(
            events=["Login"],
            math="total",
            math_property=None,
            per_user=None,
            from_date=None,
            to_date=None,
            last=30,
            unit="day",
            group_by=["platform", "country"],
            where=None,
            formulas=[],
            rolling=None,
            cumulative=False,
            mode="timeseries",
        )
        assert len(params["sections"]["group"]) == 2

    def test_list_item_groupby_through_build_query_params(self, ws: Workspace) -> None:
        """GroupBy.list_item threads through _build_query_params end-to-end."""
        from mixpanel_headless import GroupBy

        params = ws._build_query_params(
            events=["Cart Viewed"],
            math="total",
            math_property=None,
            per_user=None,
            from_date=None,
            to_date=None,
            last=30,
            unit="day",
            group_by=GroupBy.list_item("cart", "Brand"),
            where=None,
            formulas=[],
            rolling=None,
            cumulative=False,
            mode="timeseries",
        )
        g = params["sections"]["group"][0]
        assert g["joinPropertyType"] == "list"
        assert g["propertyType"] == "object"
        assert g["listItemGroup"]["propertyName"] == "Brand"
        assert g["listItemGroup"]["propertyType"] == "string"


# =============================================================================
# T032: Multi-event params (US4)
# =============================================================================


class TestMultiEventParams:
    """Tests for multi-event params generation."""

    def test_list_of_strings(self, ws: Workspace) -> None:
        """List of event strings produces multiple show entries."""
        params = ws._build_query_params(
            events=["Signup", "Login", "Purchase"],
            math="unique",
            math_property=None,
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
        assert len(params["sections"]["show"]) == 3
        events = [e["behavior"]["name"] for e in params["sections"]["show"]]
        assert events == ["Signup", "Login", "Purchase"]

    def test_list_of_metrics(self, ws: Workspace) -> None:
        """List of Metric objects produces show entries with per-event math."""
        from mixpanel_headless import Metric

        params = ws._build_query_params(
            events=[Metric("Signup", math="unique"), Metric("Purchase", math="total")],
            math="total",
            math_property=None,
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
        assert params["sections"]["show"][0]["measurement"]["math"] == "unique"
        assert params["sections"]["show"][1]["measurement"]["math"] == "total"

    def test_mixed_strings_and_metrics(self, ws: Workspace) -> None:
        """Mixed strings and Metrics: strings inherit top-level math."""
        from mixpanel_headless import Metric

        params = ws._build_query_params(
            events=["Login", Metric("Purchase", math="total", property="amount")],
            math="unique",
            math_property=None,
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
        assert params["sections"]["show"][0]["measurement"]["math"] == "unique"
        assert params["sections"]["show"][1]["measurement"]["math"] == "total"


# =============================================================================
# T036: Formula params (US5)
# =============================================================================


class TestFormulaParams:
    """Tests for formula params generation."""

    def test_formula_appended_to_show(self, ws: Workspace) -> None:
        """Formula entry appended to sections.show[]."""
        from mixpanel_headless import Metric

        params = ws._build_query_params(
            events=[Metric("Signup", math="unique"), Metric("Purchase", math="unique")],
            math="total",
            math_property=None,
            per_user=None,
            from_date=None,
            to_date=None,
            last=30,
            unit="day",
            group_by=None,
            where=None,
            formulas=[Formula("(B / A) * 100", label="Conversion Rate")],
            rolling=None,
            cumulative=False,
            mode="timeseries",
        )
        # 2 metrics + 1 formula = 3 show entries
        assert len(params["sections"]["show"]) == 3
        formula_entry = params["sections"]["show"][2]
        assert formula_entry["type"] == "formula"
        assert formula_entry["definition"] == "(B / A) * 100"
        assert formula_entry["name"] == "Conversion Rate"

    def test_formula_hides_input_metrics(self, ws: Workspace) -> None:
        """Input metrics are marked isHidden when formula is present."""
        from mixpanel_headless import Metric

        params = ws._build_query_params(
            events=[Metric("A", math="unique"), Metric("B", math="unique")],
            math="total",
            math_property=None,
            per_user=None,
            from_date=None,
            to_date=None,
            last=30,
            unit="day",
            group_by=None,
            where=None,
            formulas=[Formula("B / A")],
            rolling=None,
            cumulative=False,
            mode="timeseries",
        )
        assert params["sections"]["show"][0]["isHidden"] is True
        assert params["sections"]["show"][1]["isHidden"] is True

    def test_no_formula_no_hidden(self, ws: Workspace) -> None:
        """Without formula, metrics are not hidden."""
        params = ws._build_query_params(
            events=["Login"],
            math="total",
            math_property=None,
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
        assert params["sections"]["show"][0].get("isHidden") is not True


# =============================================================================
# T041: Analysis mode params (US6)
# =============================================================================


class TestAnalysisModeParams:
    """Tests for analysis mode params generation."""

    def test_rolling_mode(self, ws: Workspace) -> None:
        """rolling=7 produces analysis='rolling' + rollingWindowSize=7."""
        params = ws._build_query_params(
            events=["Signup"],
            math="unique",
            math_property=None,
            per_user=None,
            from_date=None,
            to_date=None,
            last=30,
            unit="day",
            group_by=None,
            where=None,
            formulas=[],
            rolling=7,
            cumulative=False,
            mode="timeseries",
        )
        d = params["displayOptions"]
        assert d["analysis"] == "rolling"
        assert d["rollingWindowSize"] == 7

    def test_cumulative_mode(self, ws: Workspace) -> None:
        """cumulative=True produces analysis='cumulative'."""
        params = ws._build_query_params(
            events=["Signup"],
            math="unique",
            math_property=None,
            per_user=None,
            from_date=None,
            to_date=None,
            last=30,
            unit="day",
            group_by=None,
            where=None,
            formulas=[],
            rolling=None,
            cumulative=True,
            mode="timeseries",
        )
        assert params["displayOptions"]["analysis"] == "cumulative"

    def test_default_linear_mode(self, ws: Workspace) -> None:
        """Neither rolling nor cumulative produces analysis='linear'."""
        params = ws._build_query_params(
            events=["Login"],
            math="total",
            math_property=None,
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
        assert params["displayOptions"]["analysis"] == "linear"


# =============================================================================
# T044: Mode→chartType mapping (US7)
# =============================================================================


class TestModeParams:
    """Tests for mode parameter mapping."""

    def test_timeseries_to_line(self, ws: Workspace) -> None:
        """mode='timeseries' maps to chartType='line'."""
        params = ws._build_query_params(
            events=["Login"],
            math="total",
            math_property=None,
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
        assert params["displayOptions"]["chartType"] == "line"

    def test_total_to_bar(self, ws: Workspace) -> None:
        """mode='total' maps to chartType='bar'."""
        params = ws._build_query_params(
            events=["Login"],
            math="total",
            math_property=None,
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
            mode="total",
        )
        assert params["displayOptions"]["chartType"] == "bar"

    def test_table_to_table(self, ws: Workspace) -> None:
        """mode='table' maps to chartType='table'."""
        params = ws._build_query_params(
            events=["Login"],
            math="total",
            math_property=None,
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
            mode="table",
        )
        assert params["displayOptions"]["chartType"] == "table"


# =============================================================================
# Per-metric filters in params generation
# =============================================================================


class TestPerMetricFilters:
    """Tests for per-metric filters in _build_query_params."""

    def test_per_metric_filter_in_behavior(self, ws: Workspace) -> None:
        """Metric.filters appear in behavior.filters, not sections.filter."""
        from mixpanel_headless import Filter, Metric

        params = ws._build_query_params(
            events=[Metric("Purchase", filters=[Filter.equals("country", "US")])],
            math="total",
            math_property=None,
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
        show = params["sections"]["show"]
        assert len(show) == 1
        behavior = show[0]["behavior"]
        assert "filters" in behavior
        assert len(behavior["filters"]) == 1
        f = behavior["filters"][0]
        assert f["value"] == "country"
        assert f["filterValue"] == ["US"]
        assert f["filterOperator"] == "equals"

    def test_per_metric_filter_separate_from_global(self, ws: Workspace) -> None:
        """Per-metric filters and global where are in different locations."""
        from mixpanel_headless import Filter, Metric

        params = ws._build_query_params(
            events=[Metric("Purchase", filters=[Filter.equals("country", "US")])],
            math="total",
            math_property=None,
            per_user=None,
            from_date=None,
            to_date=None,
            last=30,
            unit="day",
            group_by=None,
            where=Filter.greater_than("age", 18),
            formulas=[],
            rolling=None,
            cumulative=False,
            mode="timeseries",
        )
        # Global filter in sections.filter
        global_filters = params["sections"]["filter"]
        assert len(global_filters) == 1
        assert global_filters[0]["value"] == "age"

        # Per-metric filter in show[0].behavior.filters
        per_metric_filters = params["sections"]["show"][0]["behavior"]["filters"]
        assert len(per_metric_filters) == 1
        assert per_metric_filters[0]["value"] == "country"


# =============================================================================
# group_by type validation in params building
# =============================================================================


class TestGroupByTypeError:
    """Tests for group_by element type validation."""

    def test_invalid_group_by_type_raises(self, ws: Workspace) -> None:
        """Non-str, non-GroupBy group_by element raises TypeError."""
        with pytest.raises(
            TypeError,
            match="group_by elements must be str, GroupBy, CohortBreakdown, or FrequencyBreakdown",
        ):
            ws._build_query_params(
                events=["Login"],
                math="total",
                math_property=None,
                per_user=None,
                from_date=None,
                to_date=None,
                last=30,
                unit="day",
                group_by=[42],  # type: ignore[list-item]
                where=None,
                formulas=[],
                rolling=None,
                cumulative=False,
                mode="timeseries",
            )


# =============================================================================
# filters_combinator in params building
# =============================================================================


class TestFiltersCombinatorParams:
    """Tests for Metric.filters_combinator in _build_query_params."""

    def test_default_combinator_is_all(self, ws: Workspace) -> None:
        """Default filters_combinator='all' emits filtersDeterminer='all'."""
        from mixpanel_headless import Metric

        params = ws._build_query_params(
            events=[Metric("Login")],
            math="total",
            math_property=None,
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
        behavior = params["sections"]["show"][0]["behavior"]
        assert behavior["filtersDeterminer"] == "all"

    def test_any_combinator(self, ws: Workspace) -> None:
        """filters_combinator='any' emits filtersDeterminer='any'."""
        from mixpanel_headless import Filter, Metric

        params = ws._build_query_params(
            events=[
                Metric(
                    "Login",
                    filters=[Filter.equals("$browser", "Chrome")],
                    filters_combinator="any",
                )
            ],
            math="total",
            math_property=None,
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
        behavior = params["sections"]["show"][0]["behavior"]
        assert behavior["filtersDeterminer"] == "any"

    def test_string_event_uses_all(self, ws: Workspace) -> None:
        """Plain string events always use filtersDeterminer='all'."""
        params = ws._build_query_params(
            events=["Login"],
            math="total",
            math_property=None,
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
        behavior = params["sections"]["show"][0]["behavior"]
        assert behavior["filtersDeterminer"] == "all"


# =============================================================================
# Formula objects in _build_query_params
# =============================================================================


class TestFormulaObjectParams:
    """Tests for Formula objects passed via formulas parameter."""

    def test_single_formula_object(self, ws: Workspace) -> None:
        """A Formula object produces a formula show clause."""
        from mixpanel_headless import Metric

        params = ws._build_query_params(
            events=[Metric("Signup", math="unique"), Metric("Purchase", math="unique")],
            math="total",
            math_property=None,
            per_user=None,
            from_date=None,
            to_date=None,
            last=30,
            unit="day",
            group_by=None,
            where=None,
            formulas=[Formula("(B / A) * 100", label="Conv %")],
            rolling=None,
            cumulative=False,
            mode="timeseries",
        )
        show = params["sections"]["show"]
        assert len(show) == 3
        assert show[2]["type"] == "formula"
        assert show[2]["definition"] == "(B / A) * 100"
        assert show[2]["name"] == "Conv %"

    def test_formula_without_label(self, ws: Workspace) -> None:
        """Formula without label omits name from show clause."""
        from mixpanel_headless import Metric

        params = ws._build_query_params(
            events=[Metric("A"), Metric("B")],
            math="total",
            math_property=None,
            per_user=None,
            from_date=None,
            to_date=None,
            last=30,
            unit="day",
            group_by=None,
            where=None,
            formulas=[Formula("A + B")],
            rolling=None,
            cumulative=False,
            mode="timeseries",
        )
        formula_clause = params["sections"]["show"][2]
        assert formula_clause["type"] == "formula"
        assert "name" not in formula_clause

    def test_multiple_formulas(self, ws: Workspace) -> None:
        """Multiple Formula objects produce multiple formula show clauses."""
        from mixpanel_headless import Metric

        params = ws._build_query_params(
            events=[Metric("A"), Metric("B")],
            math="total",
            math_property=None,
            per_user=None,
            from_date=None,
            to_date=None,
            last=30,
            unit="day",
            group_by=None,
            where=None,
            formulas=[
                Formula("A + B", label="Sum"),
                Formula("A / B", label="Ratio"),
            ],
            rolling=None,
            cumulative=False,
            mode="timeseries",
        )
        show = params["sections"]["show"]
        assert len(show) == 4  # 2 metrics + 2 formulas
        assert show[2]["definition"] == "A + B"
        assert show[3]["definition"] == "A / B"

    def test_formula_hides_metrics(self, ws: Workspace) -> None:
        """Metrics are hidden when formulas are present."""
        from mixpanel_headless import Metric

        params = ws._build_query_params(
            events=[Metric("A"), Metric("B")],
            math="total",
            math_property=None,
            per_user=None,
            from_date=None,
            to_date=None,
            last=30,
            unit="day",
            group_by=None,
            where=None,
            formulas=[Formula("A / B")],
            rolling=None,
            cumulative=False,
            mode="timeseries",
        )
        assert params["sections"]["show"][0]["isHidden"] is True
        assert params["sections"]["show"][1]["isHidden"] is True


# =============================================================================
# T054: build_params() public helper
# =============================================================================


class TestBuildParams:
    """T054: build_params() returns bookmark params without API call."""

    def test_build_params_returns_dict(self, ws: Workspace) -> None:
        """T054a: build_params() returns a dict with sections and displayOptions."""
        result = ws.build_params("Login")
        assert isinstance(result, dict)
        assert "sections" in result
        assert "displayOptions" in result

    def test_build_params_accepts_all_query_kwargs(self, ws: Workspace) -> None:
        """T054b: build_params() accepts the full query() signature."""
        result = ws.build_params(
            [Metric("Login", math="unique"), Metric("Purchase")],
            from_date="2024-01-01",
            to_date="2024-01-31",
            unit="week",
            group_by=GroupBy("country"),
            where=Filter.equals("region", "US"),
            formula="A + B",
            formula_label="Combined",
            mode="total",
        )
        assert result["sections"]["show"][0]["behavior"]["name"] == "Login"
        assert result["sections"]["show"][0]["measurement"]["math"] == "unique"
        assert result["displayOptions"]["chartType"] == "bar"

    def test_build_params_output_matches_query_params(self, ws: Workspace) -> None:
        """T054c: build_params() output matches _build_query_params() for same input."""
        build_result = ws.build_params("Login", math="unique", last=7, unit="day")
        internal_result = ws._build_query_params(
            events=["Login"],
            math="unique",
            math_property=None,
            per_user=None,
            from_date=None,
            to_date=None,
            last=7,
            unit="day",
            group_by=None,
            where=None,
            formulas=[],
            rolling=None,
            cumulative=False,
            mode="timeseries",
        )
        assert build_result == internal_result


# =============================================================================
# T057: Date filter bookmark params
# =============================================================================


class TestDateFilterParams:
    """T057: Date filter bookmark params generation."""

    def test_absolute_date_omits_date_unit(self) -> None:
        """Absolute date filter (on) omits filterDateUnit."""
        entry = build_filter_entry(Filter.on("created", "2024-06-15"))
        assert entry["filterType"] == "datetime"
        assert entry["filterOperator"] == "was on"
        assert entry["filterValue"] == "2024-06-15"
        assert "filterDateUnit" not in entry

    def test_relative_date_includes_date_unit(self) -> None:
        """Relative date filter (in_the_last) includes filterDateUnit."""
        entry = build_filter_entry(Filter.in_the_last("created", 7, "day"))
        assert entry["filterDateUnit"] == "day"
        assert entry["filterValue"] == 7
        assert entry["filterType"] == "datetime"

    def test_date_between_value_is_list(self) -> None:
        """Date between filter value is a two-element list."""
        entry = build_filter_entry(
            Filter.date_between("created", "2024-01-01", "2024-06-30")
        )
        assert entry["filterValue"] == ["2024-01-01", "2024-06-30"]
        assert entry["filterOperator"] == "was between"
        assert "filterDateUnit" not in entry

    def test_existing_filters_unaffected(self) -> None:
        """Non-date filters still omit filterDateUnit (backward compat)."""
        entry = build_filter_entry(Filter.equals("country", "US"))
        assert "filterDateUnit" not in entry

    def test_date_filter_in_where_clause(self, ws: Workspace) -> None:
        """Date filter works in sections.filter when passed as where=."""
        params = ws.build_params(
            "Login",
            where=Filter.in_the_last("created", 7, "day"),
        )
        filt = params["sections"]["filter"][0]
        assert filt["filterDateUnit"] == "day"
        assert filt["filterType"] == "datetime"

    def test_before_filter_params(self) -> None:
        """Filter.before() produces correct bookmark entry."""
        entry = build_filter_entry(Filter.before("created", "2024-01-01"))
        assert entry["filterOperator"] == "was before"
        assert entry["filterValue"] == "2024-01-01"
        assert entry["filterType"] == "datetime"

    def test_since_filter_params(self) -> None:
        """Filter.since() produces correct bookmark entry."""
        entry = build_filter_entry(Filter.since("created", "2024-01-01"))
        assert entry["filterOperator"] == "was since"
        assert entry["filterValue"] == "2024-01-01"

    def test_not_in_the_last_includes_date_unit(self) -> None:
        """Filter.not_in_the_last() includes filterDateUnit."""
        entry = build_filter_entry(Filter.not_in_the_last("created", 30, "day"))
        assert entry["filterDateUnit"] == "day"
        assert entry["filterOperator"] == "was not in the"


# =============================================================================
# T060: Multiple formulas via events list
# =============================================================================


class TestMultiFormulaParams:
    """T060: Multiple formulas via events list."""

    def test_two_formulas_produce_two_entries(self, ws: Workspace) -> None:
        """Two Formula objects in events list produce two formula show entries."""
        params = ws.build_params(
            [
                Metric("Signup", math="unique"),
                Metric("Purchase", math="unique"),
                Formula("B / A", label="Conv Rate"),
                Formula("A + B", label="Total"),
            ],
        )
        formulas = [e for e in params["sections"]["show"] if e.get("type") == "formula"]
        assert len(formulas) == 2
        assert formulas[0]["definition"] == "B / A"
        assert formulas[0]["name"] == "Conv Rate"
        assert formulas[1]["definition"] == "A + B"
        assert formulas[1]["name"] == "Total"

    def test_metrics_hidden_with_multiple_formulas(self, ws: Workspace) -> None:
        """All metrics get isHidden=True when formulas are present."""
        params = ws.build_params(
            [
                Metric("A"),
                Metric("B"),
                Formula("A+B"),
                Formula("A-B"),
            ],
        )
        metrics = [e for e in params["sections"]["show"] if e.get("type") == "metric"]
        assert all(e["isHidden"] is True for e in metrics)

    def test_three_formulas_with_three_events(self, ws: Workspace) -> None:
        """Three formulas referencing three events all produce entries."""
        params = ws.build_params(
            [
                Metric("A", math="unique"),
                Metric("B", math="unique"),
                Metric("C", math="unique"),
                Formula("A + B", label="AB"),
                Formula("B + C", label="BC"),
                Formula("(A + B + C) / 3", label="Avg"),
            ],
        )
        show = params["sections"]["show"]
        assert len(show) == 6  # 3 metrics + 3 formulas
        formulas = [e for e in show if e.get("type") == "formula"]
        assert len(formulas) == 3


# =============================================================================
# T065: Custom percentile bookmark params
# =============================================================================


class TestPercentileParams:
    """T065: Custom percentile bookmark params."""

    def test_maps_to_custom_percentile(self, ws: Workspace) -> None:
        """math='percentile' maps to measurement.math='custom_percentile'."""
        params = ws.build_params(
            "Login",
            math="percentile",
            math_property="duration",
            percentile_value=95,
        )
        m = params["sections"]["show"][0]["measurement"]
        assert m["math"] == "custom_percentile"
        assert m["percentile"] == 95
        assert m["property"]["name"] == "duration"

    def test_metric_percentile_maps_correctly(self, ws: Workspace) -> None:
        """Metric(math='percentile') maps to custom_percentile in bookmark."""
        params = ws.build_params(
            Metric(
                "Login",
                math="percentile",
                property="duration",
                percentile_value=95,
            ),
        )
        m = params["sections"]["show"][0]["measurement"]
        assert m["math"] == "custom_percentile"
        assert m["percentile"] == 95

    def test_percentile_float_value(self, ws: Workspace) -> None:
        """Percentile value supports float (e.g. 99.9)."""
        params = ws.build_params(
            "Login",
            math="percentile",
            math_property="duration",
            percentile_value=99.9,
        )
        assert params["sections"]["show"][0]["measurement"]["percentile"] == 99.9


# =============================================================================
# T069: Histogram bookmark params
# =============================================================================


class TestHistogramParams:
    """T069: Histogram bookmark params."""

    def test_histogram_math_in_bookmark(self, ws: Workspace) -> None:
        """math='histogram' maps directly to measurement.math='histogram'."""
        params = ws.build_params(
            "Purchase",
            math="histogram",
            math_property="amount",
            per_user="total",
        )
        m = params["sections"]["show"][0]["measurement"]
        assert m["math"] == "histogram"
        assert m["property"]["name"] == "amount"
        assert m["perUserAggregation"] == "total"

    def test_histogram_metric_in_bookmark(self, ws: Workspace) -> None:
        """Metric(math='histogram') maps correctly."""
        params = ws.build_params(
            Metric(
                "Purchase",
                math="histogram",
                property="amount",
                per_user="total",
            ),
        )
        m = params["sections"]["show"][0]["measurement"]
        assert m["math"] == "histogram"
        assert m["perUserAggregation"] == "total"


# =============================================================================
# T005: New math types in build_params
# =============================================================================


class TestNewMathTypesInBuildParams:
    """T005: New math types produce correct measurement blocks in build_params."""

    def test_cumulative_unique_in_build_params(self, ws: Workspace) -> None:
        """build_params with math='cumulative_unique' produces correct measurement."""
        params = ws.build_params("Login", math="cumulative_unique")
        m = params["sections"]["show"][0]["measurement"]
        assert m["math"] == "cumulative_unique"

    def test_sessions_in_build_params(self, ws: Workspace) -> None:
        """build_params with math='sessions' produces correct measurement."""
        params = ws.build_params("Login", math="sessions")
        m = params["sections"]["show"][0]["measurement"]
        assert m["math"] == "sessions"

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
    def test_property_requiring_math_in_build_params(
        self, ws: Workspace, math_type: str
    ) -> None:
        """build_params with property-requiring math produces correct measurement."""
        params = ws.build_params(
            "Purchase",
            math=math_type,  # type: ignore[arg-type]
            math_property="amount",
        )
        m = params["sections"]["show"][0]["measurement"]
        assert m["math"] == math_type
        assert m["property"]["name"] == "amount"


# =============================================================================
# T009: Metric.segment_method in build_params
# =============================================================================


class TestSegmentMethodInBuildParams:
    """T009: Metric.segment_method produces segmentMethod in measurement block."""

    def test_segment_method_first_in_measurement(self, ws: Workspace) -> None:
        """build_params with Metric(event, segment_method='first') produces segmentMethod='first'."""
        params = ws.build_params(
            Metric("Login", segment_method="first"),
        )
        m = params["sections"]["show"][0]["measurement"]
        assert m["segmentMethod"] == "first"

    def test_segment_method_all_in_measurement(self, ws: Workspace) -> None:
        """build_params with Metric(event, segment_method='all') produces segmentMethod='all'."""
        params = ws.build_params(
            Metric("Login", segment_method="all"),
        )
        m = params["sections"]["show"][0]["measurement"]
        assert m["segmentMethod"] == "all"

    def test_segment_method_none_omits_key(self, ws: Workspace) -> None:
        """build_params with Metric(event) omits segmentMethod (backward compat)."""
        params = ws.build_params(Metric("Login"))
        m = params["sections"]["show"][0]["measurement"]
        assert "segmentMethod" not in m

    def test_segment_method_string_event_omits_key(self, ws: Workspace) -> None:
        """build_params with plain string event omits segmentMethod."""
        params = ws.build_params("Login")
        m = params["sections"]["show"][0]["measurement"]
        assert "segmentMethod" not in m


# =============================================================================
# T023: FrequencyBreakdown in build_params group_by (US4)
# =============================================================================


class TestFrequencyBreakdownInBuildParams:
    """T023: FrequencyBreakdown accepted in build_params group_by."""

    def test_frequency_breakdown_in_group_section(self, ws: Workspace) -> None:
        """build_params with FrequencyBreakdown produces frequency group entry."""
        from mixpanel_headless.types import FrequencyBreakdown

        params = ws.build_params(
            "Login",
            group_by=FrequencyBreakdown("Purchase"),
        )
        group = params["sections"]["group"]
        assert len(group) == 1
        assert group[0]["resourceType"] == "people"
        assert group[0]["behavior"]["behaviorType"] == "$frequency"
        assert group[0]["behavior"]["event"] == {
            "label": "Purchase",
            "value": "Purchase",
        }

    def test_frequency_breakdown_with_label(self, ws: Workspace) -> None:
        """build_params with labeled FrequencyBreakdown includes label in value."""
        from mixpanel_headless.types import FrequencyBreakdown

        params = ws.build_params(
            "Login",
            group_by=FrequencyBreakdown("Purchase", label="Buy Freq"),
        )
        group = params["sections"]["group"]
        assert group[0]["value"] == "Buy Freq"

    def test_frequency_breakdown_mixed_with_string(self, ws: Workspace) -> None:
        """build_params with mixed string and FrequencyBreakdown in list."""
        from mixpanel_headless.types import FrequencyBreakdown

        params = ws.build_params(
            "Login",
            group_by=["country", FrequencyBreakdown("Purchase")],
        )
        group = params["sections"]["group"]
        assert len(group) == 2
        assert group[0]["value"] == "country"
        assert group[1]["behavior"]["behaviorType"] == "$frequency"

    def test_existing_groupby_still_works(self, ws: Workspace) -> None:
        """Backward compat: existing GroupBy usage still works."""
        params = ws.build_params(
            "Login",
            group_by=GroupBy("country"),
        )
        group = params["sections"]["group"]
        assert len(group) == 1
        assert group[0]["value"] == "country"


# =============================================================================
# T023: FrequencyFilter in build_params where (US4)
# =============================================================================


class TestFrequencyFilterInBuildParams:
    """T023: FrequencyFilter accepted in build_params where."""

    def test_frequency_filter_in_filter_section(self, ws: Workspace) -> None:
        """build_params with FrequencyFilter produces frequency filter entry."""
        from mixpanel_headless.types import FrequencyFilter

        params = ws.build_params(
            "Login",
            where=FrequencyFilter("Login", value=5),
        )
        filt = params["sections"]["filter"]
        assert len(filt) == 1
        assert filt[0]["resourceType"] == "people"
        assert filt[0]["behaviorType"] == "$frequency"

    def test_frequency_filter_mixed_with_filter(self, ws: Workspace) -> None:
        """build_params with mixed Filter and FrequencyFilter in list."""
        from mixpanel_headless.types import FrequencyFilter

        params = ws.build_params(
            "Login",
            where=[
                Filter.equals("country", "US"),
                FrequencyFilter("Login", value=5),
            ],
        )
        filt = params["sections"]["filter"]
        assert len(filt) == 2
        assert filt[0]["value"] == "country"
        assert filt[1]["behaviorType"] == "$frequency"

    def test_existing_filter_still_works(self, ws: Workspace) -> None:
        """Backward compat: existing Filter usage still works."""
        params = ws.build_params(
            "Login",
            where=Filter.equals("country", "US"),
        )
        filt = params["sections"]["filter"]
        assert len(filt) == 1
        assert filt[0]["value"] == "country"


# =============================================================================
# T032: data_group_id on insights query engine
# =============================================================================


class TestDataGroupIdInsights:
    """Tests for data_group_id parameter on insights query engine (T032)."""

    def test_build_params_with_data_group_id(self, ws: Workspace) -> None:
        """build_params with data_group_id=5 includes dataGroupId: 5 in output."""
        params = ws.build_params("Login", data_group_id=5)
        assert params["sections"]["dataGroupId"] == 5

    def test_build_params_without_data_group_id(self, ws: Workspace) -> None:
        """build_params without data_group_id omits dataGroupId key (backward compat)."""
        params = ws.build_params("Login")
        assert "dataGroupId" not in params["sections"]

    def test_build_query_params_with_data_group_id(self, ws: Workspace) -> None:
        """_build_query_params with data_group_id=3 includes dataGroupId: 3."""
        params = ws._build_query_params(
            events=["Login"],
            math="total",
            math_property=None,
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
            data_group_id=3,
        )
        assert params["sections"]["dataGroupId"] == 3

    def test_build_query_params_default_data_group_id_none(self, ws: Workspace) -> None:
        """_build_query_params without data_group_id defaults to None."""
        params = ws._build_query_params(
            events=["Login"],
            math="total",
            math_property=None,
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
        assert "dataGroupId" not in params["sections"]
