"""Tests for Workspace.build_funnel_params() and Workspace._build_funnel_params().

Exercises the full funnel bookmark param-building pipeline: normalization,
validation (Layer 1 + Layer 2), and bookmark JSON structure generation.
Uses ``build_funnel_params()`` as the public entry point since it delegates
through ``_resolve_and_build_funnel_params()`` into ``_build_funnel_params()``
without requiring API credentials.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from pydantic import SecretStr

from mixpanel_headless import Workspace
from mixpanel_headless._internal.auth.account import ServiceAccount
from mixpanel_headless._internal.auth.session import Project, Session
from mixpanel_headless.exceptions import BookmarkValidationError
from mixpanel_headless.types import Exclusion, Filter, FunnelStep, HoldingConstant

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
def mock_api_client() -> MagicMock:
    """Create mock API client for Workspace construction."""
    from mixpanel_headless._internal.api_client import MixpanelAPIClient

    client = MagicMock(spec=MixpanelAPIClient)
    client.close = MagicMock()
    return client


@pytest.fixture
def ws(mock_api_client: MagicMock) -> Workspace:
    """Create a Workspace instance with mocked dependencies.

    Uses dependency injection so no real credentials or network access
    are needed.
    """
    return Workspace(
        session=_TEST_SESSION,
        _api_client=mock_api_client,
    )


# =============================================================================
# T018: Basic bookmark structure tests
# =============================================================================


class TestBuildFunnelParamsDefaults:
    """Tests for default bookmark structure (T018).

    Verifies that ``build_funnel_params(["Signup", "Purchase"])`` produces
    the correct bookmark JSON with all default values.
    """

    def test_behavior_type_is_funnel(self, ws: Workspace) -> None:
        """Verify sections.show[0].behavior.type is 'funnel'."""
        result = ws.build_funnel_params(["Signup", "Purchase"])
        behavior = result["sections"]["show"][0]["behavior"]
        assert behavior["type"] == "funnel"

    def test_behaviors_has_two_elements(self, ws: Workspace) -> None:
        """Verify behaviors list has one entry per step."""
        result = ws.build_funnel_params(["Signup", "Purchase"])
        behaviors = result["sections"]["show"][0]["behavior"]["behaviors"]
        assert len(behaviors) == 2

    def test_behavior_names_match_steps(self, ws: Workspace) -> None:
        """Verify each behavior name matches the corresponding step event."""
        result = ws.build_funnel_params(["Signup", "Purchase"])
        behaviors = result["sections"]["show"][0]["behavior"]["behaviors"]
        assert behaviors[0]["name"] == "Signup"
        assert behaviors[1]["name"] == "Purchase"

    def test_behavior_resource_type_is_events(self, ws: Workspace) -> None:
        """Verify parent behavior has resourceType='events'."""
        result = ws.build_funnel_params(["Signup", "Purchase"])
        behavior = result["sections"]["show"][0]["behavior"]
        assert behavior["resourceType"] == "events"

    def test_default_conversion_window_duration(self, ws: Workspace) -> None:
        """Verify default conversionWindowDuration is 14."""
        result = ws.build_funnel_params(["Signup", "Purchase"])
        behavior = result["sections"]["show"][0]["behavior"]
        assert behavior["conversionWindowDuration"] == 14

    def test_default_conversion_window_unit(self, ws: Workspace) -> None:
        """Verify default conversionWindowUnit is 'day'."""
        result = ws.build_funnel_params(["Signup", "Purchase"])
        behavior = result["sections"]["show"][0]["behavior"]
        assert behavior["conversionWindowUnit"] == "day"

    def test_default_funnel_order(self, ws: Workspace) -> None:
        """Verify default funnelOrder is 'loose'."""
        result = ws.build_funnel_params(["Signup", "Purchase"])
        behavior = result["sections"]["show"][0]["behavior"]
        assert behavior["funnelOrder"] == "loose"

    def test_default_measurement_math(self, ws: Workspace) -> None:
        """Verify default measurement.math is 'conversion_rate_unique'."""
        result = ws.build_funnel_params(["Signup", "Purchase"])
        measurement = result["sections"]["show"][0]["measurement"]
        assert measurement["math"] == "conversion_rate_unique"

    def test_default_chart_type_for_steps_mode(self, ws: Workspace) -> None:
        """Verify default displayOptions.chartType is 'funnel-steps'."""
        result = ws.build_funnel_params(["Signup", "Purchase"])
        assert result["displayOptions"]["chartType"] == "funnel-steps"

    def test_formula_is_empty_list(self, ws: Workspace) -> None:
        """Verify sections.formula is an empty list."""
        result = ws.build_funnel_params(["Signup", "Purchase"])
        assert result["sections"]["formula"] == []

    def test_time_section_is_list(self, ws: Workspace) -> None:
        """Verify sections.time is a list."""
        result = ws.build_funnel_params(["Signup", "Purchase"])
        assert isinstance(result["sections"]["time"], list)

    def test_filter_section_is_list(self, ws: Workspace) -> None:
        """Verify sections.filter is a list."""
        result = ws.build_funnel_params(["Signup", "Purchase"])
        assert isinstance(result["sections"]["filter"], list)

    def test_group_section_is_list(self, ws: Workspace) -> None:
        """Verify sections.group is a list."""
        result = ws.build_funnel_params(["Signup", "Purchase"])
        assert isinstance(result["sections"]["group"], list)

    def test_three_step_funnel(self, ws: Workspace) -> None:
        """Verify a three-step funnel produces three behaviors."""
        result = ws.build_funnel_params(["Signup", "Add to Cart", "Purchase"])
        behaviors = result["sections"]["show"][0]["behavior"]["behaviors"]
        assert len(behaviors) == 3
        assert behaviors[0]["name"] == "Signup"
        assert behaviors[1]["name"] == "Add to Cart"
        assert behaviors[2]["name"] == "Purchase"

    def test_funnel_step_objects_accepted(self, ws: Workspace) -> None:
        """Verify FunnelStep objects are accepted alongside strings."""
        result = ws.build_funnel_params([FunnelStep("Signup"), FunnelStep("Purchase")])
        behaviors = result["sections"]["show"][0]["behavior"]["behaviors"]
        assert len(behaviors) == 2
        assert behaviors[0]["name"] == "Signup"
        assert behaviors[1]["name"] == "Purchase"


# =============================================================================
# T019: Configuration options tests
# =============================================================================


class TestBuildFunnelParamsConfiguration:
    """Tests for configuration options (T019).

    Verifies that keyword arguments are correctly mapped into the
    bookmark JSON structure.
    """

    def test_conversion_window_override(self, ws: Workspace) -> None:
        """Verify custom conversion_window is applied."""
        result = ws.build_funnel_params(
            ["Signup", "Purchase"],
            conversion_window=7,
            conversion_window_unit="day",
        )
        behavior = result["sections"]["show"][0]["behavior"]
        assert behavior["conversionWindowDuration"] == 7
        assert behavior["conversionWindowUnit"] == "day"

    def test_conversion_window_unit_hour(self, ws: Workspace) -> None:
        """Verify conversion_window_unit='hour' is applied."""
        result = ws.build_funnel_params(
            ["Signup", "Purchase"],
            conversion_window=2,
            conversion_window_unit="hour",
        )
        behavior = result["sections"]["show"][0]["behavior"]
        assert behavior["conversionWindowDuration"] == 2
        assert behavior["conversionWindowUnit"] == "hour"

    def test_order_any(self, ws: Workspace) -> None:
        """Verify order='any' sets funnelOrder='any'."""
        result = ws.build_funnel_params(
            ["Signup", "Purchase"],
            order="any",
        )
        behavior = result["sections"]["show"][0]["behavior"]
        assert behavior["funnelOrder"] == "any"

    def test_per_step_order_override(self, ws: Workspace) -> None:
        """Verify per-step order override sets funnelOrder on that behavior entry."""
        result = ws.build_funnel_params(
            [
                FunnelStep("Signup"),
                FunnelStep("Browse"),
                FunnelStep("Purchase", order="any"),
            ],
            order="loose",
        )
        behaviors = result["sections"]["show"][0]["behavior"]["behaviors"]
        assert behaviors[0]["funnelOrder"] == "loose"
        assert behaviors[1]["funnelOrder"] == "loose"
        assert behaviors[2]["funnelOrder"] == "any"

    def test_from_date_to_date_time_section(self, ws: Workspace) -> None:
        """Verify from_date/to_date produces a 'between' time section."""
        result = ws.build_funnel_params(
            ["Signup", "Purchase"],
            from_date="2025-01-01",
            to_date="2025-03-31",
        )
        time_section = result["sections"]["time"]
        assert len(time_section) > 0
        time_entry = time_section[0]
        assert time_entry["dateRangeType"] == "between"
        assert time_entry["value"] == ["2025-01-01", "2025-03-31"]

    def test_last_days_time_section(self, ws: Workspace) -> None:
        """Verify last=90 produces a window-based time section."""
        result = ws.build_funnel_params(
            ["Signup", "Purchase"],
            last=90,
        )
        time_section = result["sections"]["time"]
        assert len(time_section) > 0
        time_entry = time_section[0]
        assert time_entry["dateRangeType"] == "in the last"
        assert time_entry["window"]["value"] == 90
        assert time_entry["window"]["unit"] == "day"

    def test_math_unique(self, ws: Workspace) -> None:
        """Verify math='unique' sets measurement.math."""
        result = ws.build_funnel_params(
            ["Signup", "Purchase"],
            math="unique",
        )
        measurement = result["sections"]["show"][0]["measurement"]
        assert measurement["math"] == "unique"

    def test_math_property_none_by_default(self, ws: Workspace) -> None:
        """Verify measurement.property is None when math_property not provided."""
        result = ws.build_funnel_params(["Signup", "Purchase"])
        measurement = result["sections"]["show"][0]["measurement"]
        assert measurement["property"] is None

    def test_math_property_populates_measurement(self, ws: Workspace) -> None:
        """Verify math_property populates measurement.property dict."""
        result = ws.build_funnel_params(
            ["Signup", "Purchase"],
            math="average",
            math_property="amount",
        )
        measurement = result["sections"]["show"][0]["measurement"]
        assert measurement["property"] == {
            "name": "amount",
            "type": "number",
            "resourceType": "events",
        }

    def test_math_property_with_median(self, ws: Workspace) -> None:
        """Verify math_property works with median math type."""
        result = ws.build_funnel_params(
            ["Signup", "Purchase"],
            math="median",
            math_property="duration",
        )
        measurement = result["sections"]["show"][0]["measurement"]
        assert measurement["math"] == "median"
        assert measurement["property"]["name"] == "duration"

    def test_mode_steps_chart_type(self, ws: Workspace) -> None:
        """Verify mode='steps' produces chartType='funnel-steps'."""
        result = ws.build_funnel_params(
            ["Signup", "Purchase"],
            mode="steps",
        )
        assert result["displayOptions"]["chartType"] == "funnel-steps"

    def test_mode_trends_chart_type(self, ws: Workspace) -> None:
        """Verify mode='trends' produces chartType='line'."""
        result = ws.build_funnel_params(
            ["Signup", "Purchase"],
            mode="trends",
        )
        assert result["displayOptions"]["chartType"] == "line"

    def test_mode_table_chart_type(self, ws: Workspace) -> None:
        """Verify mode='table' produces chartType='table'."""
        result = ws.build_funnel_params(
            ["Signup", "Purchase"],
            mode="table",
        )
        assert result["displayOptions"]["chartType"] == "table"

    def test_multiple_options_combined(self, ws: Workspace) -> None:
        """Verify multiple configuration options work together."""
        result = ws.build_funnel_params(
            ["Signup", "Add to Cart", "Checkout", "Purchase"],
            conversion_window=7,
            conversion_window_unit="day",
            order="any",
            math="unique",
            last=90,
            mode="trends",
        )
        behavior = result["sections"]["show"][0]["behavior"]
        assert behavior["conversionWindowDuration"] == 7
        assert behavior["conversionWindowUnit"] == "day"
        assert behavior["funnelOrder"] == "any"

        measurement = result["sections"]["show"][0]["measurement"]
        assert measurement["math"] == "unique"

        assert result["displayOptions"]["chartType"] == "line"

        time_entry = result["sections"]["time"][0]
        assert time_entry["window"]["value"] == 90


# =============================================================================
# T023: build_funnel_params returns dict, not FunnelQueryResult
# =============================================================================


class TestBuildFunnelParamsPublicMethod:
    """Tests for build_funnel_params() public method (T023).

    Verifies return type, top-level keys, and validation error behavior
    without making any API calls.
    """

    def test_returns_dict(self, ws: Workspace) -> None:
        """Verify return type is dict."""
        result = ws.build_funnel_params(["Signup", "Purchase"])
        assert isinstance(result, dict)

    def test_has_sections_key(self, ws: Workspace) -> None:
        """Verify result has 'sections' key."""
        result = ws.build_funnel_params(["Signup", "Purchase"])
        assert "sections" in result

    def test_has_display_options_key(self, ws: Workspace) -> None:
        """Verify result has 'displayOptions' key."""
        result = ws.build_funnel_params(["Signup", "Purchase"])
        assert "displayOptions" in result

    def test_no_api_call_made(self, ws: Workspace, mock_api_client: MagicMock) -> None:
        """Verify no API call is made during param building."""
        ws.build_funnel_params(["Signup", "Purchase"])
        # The API client should not have been called for any request methods
        mock_api_client.request.assert_not_called()

    def test_single_step_raises_validation_error(self, ws: Workspace) -> None:
        """Verify a single-step funnel raises BookmarkValidationError."""
        with pytest.raises(BookmarkValidationError):
            ws.build_funnel_params(["OnlyOneStep"])

    def test_empty_steps_raises_validation_error(self, ws: Workspace) -> None:
        """Verify empty steps list raises BookmarkValidationError."""
        with pytest.raises(BookmarkValidationError):
            ws.build_funnel_params([])

    def test_sections_contains_expected_keys(self, ws: Workspace) -> None:
        """Verify sections dict contains show, time, filter, group, formula."""
        result = ws.build_funnel_params(["Signup", "Purchase"])
        sections = result["sections"]
        assert "show" in sections
        assert "time" in sections
        assert "filter" in sections
        assert "group" in sections
        assert "formula" in sections

    def test_show_has_one_entry(self, ws: Workspace) -> None:
        """Verify sections.show contains exactly one entry."""
        result = ws.build_funnel_params(["Signup", "Purchase"])
        assert len(result["sections"]["show"]) == 1

    def test_show_entry_has_behavior_and_measurement(self, ws: Workspace) -> None:
        """Verify sections.show[0] has both behavior and measurement keys."""
        result = ws.build_funnel_params(["Signup", "Purchase"])
        show_entry = result["sections"]["show"][0]
        assert "behavior" in show_entry
        assert "measurement" in show_entry


# =============================================================================
# T031: Per-step filters and labels tests
# =============================================================================


class TestBuildFunnelParamsPerStepFilters:
    """Tests for per-step filters and labels (T031).

    Verifies that ``FunnelStep`` objects with filters and labels
    produce correct behavior entries in the bookmark JSON.
    """

    def test_step_without_filters_has_empty_filters(self, ws: Workspace) -> None:
        """Verify a step with no filters produces an empty filters list."""
        result = ws.build_funnel_params(
            [
                FunnelStep("Signup"),
                FunnelStep("Purchase", filters=[Filter.greater_than("amount", 50)]),
            ]
        )
        behaviors = result["sections"]["show"][0]["behavior"]["behaviors"]
        assert behaviors[0]["filters"] == []

    def test_step_with_filter_has_nonempty_filters(self, ws: Workspace) -> None:
        """Verify a step with a filter produces a non-empty filters list."""
        result = ws.build_funnel_params(
            [
                FunnelStep("Signup"),
                FunnelStep("Purchase", filters=[Filter.greater_than("amount", 50)]),
            ]
        )
        behaviors = result["sections"]["show"][0]["behavior"]["behaviors"]
        assert len(behaviors[1]["filters"]) > 0

    def test_filter_entry_has_correct_value(self, ws: Workspace) -> None:
        """Verify the filter entry has value='amount' for the property name."""
        result = ws.build_funnel_params(
            [
                FunnelStep("Signup"),
                FunnelStep("Purchase", filters=[Filter.greater_than("amount", 50)]),
            ]
        )
        behaviors = result["sections"]["show"][0]["behavior"]["behaviors"]
        filter_entry = behaviors[1]["filters"][0]
        assert filter_entry["value"] == "amount"

    def test_filter_entry_has_correct_operator(self, ws: Workspace) -> None:
        """Verify the filter entry has the correct filterOperator."""
        result = ws.build_funnel_params(
            [
                FunnelStep("Signup"),
                FunnelStep("Purchase", filters=[Filter.greater_than("amount", 50)]),
            ]
        )
        behaviors = result["sections"]["show"][0]["behavior"]["behaviors"]
        filter_entry = behaviors[1]["filters"][0]
        assert filter_entry["filterOperator"] == "is greater than"

    def test_default_filters_determiner_is_all(self, ws: Workspace) -> None:
        """Verify default filtersDeterminer is 'all' when no combinator set."""
        result = ws.build_funnel_params(
            [
                FunnelStep("Signup"),
                FunnelStep("Purchase", filters=[Filter.greater_than("amount", 50)]),
            ]
        )
        behaviors = result["sections"]["show"][0]["behavior"]["behaviors"]
        assert behaviors[1]["filtersDeterminer"] == "all"

    def test_filters_combinator_any(self, ws: Workspace) -> None:
        """Verify filters_combinator='any' sets filtersDeterminer='any'."""
        result = ws.build_funnel_params(
            [
                FunnelStep("Signup"),
                FunnelStep(
                    "Purchase",
                    filters=[Filter.greater_than("amount", 50)],
                    filters_combinator="any",
                ),
            ]
        )
        behaviors = result["sections"]["show"][0]["behavior"]["behaviors"]
        assert behaviors[1]["filtersDeterminer"] == "any"

    def test_funnel_step_label_is_set(self, ws: Workspace) -> None:
        """Verify FunnelStep.label appears as 'renamed' in the behavior entry."""
        result = ws.build_funnel_params(
            [
                FunnelStep("Signup"),
                FunnelStep("Purchase", label="High-Value Purchase"),
            ]
        )
        behaviors = result["sections"]["show"][0]["behavior"]["behaviors"]
        assert behaviors[1]["renamed"] == "High-Value Purchase"

    def test_step_without_label_has_no_renamed_key(self, ws: Workspace) -> None:
        """Verify a step without a label does not have a 'renamed' key."""
        result = ws.build_funnel_params(
            [
                FunnelStep("Signup"),
                FunnelStep("Purchase"),
            ]
        )
        behaviors = result["sections"]["show"][0]["behavior"]["behaviors"]
        assert "renamed" not in behaviors[0]

    def test_empty_filters_list_same_as_none(self, ws: Workspace) -> None:
        """Verify FunnelStep with filters=[] produces same output as filters=None."""
        result_empty = ws.build_funnel_params(
            [FunnelStep("Signup", filters=[]), FunnelStep("Purchase", filters=[])]
        )
        result_none = ws.build_funnel_params(
            [FunnelStep("Signup", filters=None), FunnelStep("Purchase", filters=None)]
        )
        behaviors_empty = result_empty["sections"]["show"][0]["behavior"]["behaviors"]
        behaviors_none = result_none["sections"]["show"][0]["behavior"]["behaviors"]
        assert behaviors_empty[0]["filters"] == behaviors_none[0]["filters"]
        assert behaviors_empty[1]["filters"] == behaviors_none[1]["filters"]


# =============================================================================
# T032: Global filter and group-by tests
# =============================================================================


class TestBuildFunnelParamsGlobalFilterGroupBy:
    """Tests for global where and group_by parameters (T032).

    Verifies that ``where`` and ``group_by`` parameters produce correct
    sections.filter and sections.group entries in the bookmark JSON.
    """

    def test_where_produces_filter_section(self, ws: Workspace) -> None:
        """Verify where filter populates sections.filter."""
        result = ws.build_funnel_params(
            ["Signup", "Purchase"],
            where=[Filter.equals("country", "US")],
        )
        filter_section = result["sections"]["filter"]
        assert len(filter_section) > 0

    def test_group_by_produces_group_section(self, ws: Workspace) -> None:
        """Verify group_by populates sections.group."""
        result = ws.build_funnel_params(
            ["Signup", "Purchase"],
            group_by="platform",
        )
        group_section = result["sections"]["group"]
        assert len(group_section) > 0

    def test_where_and_group_by_together(self, ws: Workspace) -> None:
        """Verify both where and group_by work together."""
        result = ws.build_funnel_params(
            ["Signup", "Purchase"],
            where=[Filter.equals("country", "US")],
            group_by="platform",
        )
        assert len(result["sections"]["filter"]) > 0
        assert len(result["sections"]["group"]) > 0

    def test_filter_section_entry_has_correct_value(self, ws: Workspace) -> None:
        """Verify filter section entry references the correct property."""
        result = ws.build_funnel_params(
            ["Signup", "Purchase"],
            where=[Filter.equals("country", "US")],
        )
        filter_entry = result["sections"]["filter"][0]
        assert filter_entry["value"] == "country"

    def test_group_section_entry_has_correct_value(self, ws: Workspace) -> None:
        """Verify group section entry references the correct property."""
        result = ws.build_funnel_params(
            ["Signup", "Purchase"],
            group_by="platform",
        )
        group_entry = result["sections"]["group"][0]
        assert group_entry["value"] == "platform"


# =============================================================================
# T033: Mixed steps (strings and FunnelStep objects) tests
# =============================================================================


class TestBuildFunnelParamsMixedSteps:
    """Tests for mixed string and FunnelStep step lists (T033).

    Verifies that lists mixing plain strings and ``FunnelStep`` objects
    produce correct behavior entries.
    """

    def test_mixed_list_has_two_behaviors(self, ws: Workspace) -> None:
        """Verify a mixed list produces the correct number of behaviors."""
        result = ws.build_funnel_params(
            [
                "Signup",
                FunnelStep("Purchase", filters=[Filter.greater_than("amount", 50)]),
            ]
        )
        behaviors = result["sections"]["show"][0]["behavior"]["behaviors"]
        assert len(behaviors) == 2

    def test_string_step_has_no_filters(self, ws: Workspace) -> None:
        """Verify behavior from a string step has empty filters."""
        result = ws.build_funnel_params(
            [
                "Signup",
                FunnelStep("Purchase", filters=[Filter.greater_than("amount", 50)]),
            ]
        )
        behaviors = result["sections"]["show"][0]["behavior"]["behaviors"]
        assert behaviors[0]["filters"] == []

    def test_funnel_step_has_filters(self, ws: Workspace) -> None:
        """Verify behavior from a FunnelStep with filters has non-empty filters."""
        result = ws.build_funnel_params(
            [
                "Signup",
                FunnelStep("Purchase", filters=[Filter.greater_than("amount", 50)]),
            ]
        )
        behaviors = result["sections"]["show"][0]["behavior"]["behaviors"]
        assert len(behaviors[1]["filters"]) > 0

    def test_funnel_step_empty_filters_same_as_none(self, ws: Workspace) -> None:
        """Verify FunnelStep(event, filters=[]) and FunnelStep(event, filters=None) match."""
        result_empty = ws.build_funnel_params(
            ["Signup", FunnelStep("Purchase", filters=[])]
        )
        result_none = ws.build_funnel_params(
            ["Signup", FunnelStep("Purchase", filters=None)]
        )
        b_empty = result_empty["sections"]["show"][0]["behavior"]["behaviors"][1]
        b_none = result_none["sections"]["show"][0]["behavior"]["behaviors"][1]
        assert b_empty["filters"] == b_none["filters"]


# =============================================================================
# T038: Exclusions tests
# =============================================================================


class TestBuildFunnelParamsExclusions:
    """Tests for exclusion handling (T038).

    Verifies that string and ``Exclusion`` object exclusions produce
    correct exclusion entries in the behavior block.
    """

    def test_string_exclusion_produces_exclusions(self, ws: Workspace) -> None:
        """Verify a string exclusion produces a non-empty exclusions list."""
        result = ws.build_funnel_params(
            ["A", "B", "C"],
            exclusions=["Logout"],
        )
        behavior = result["sections"]["show"][0]["behavior"]
        assert len(behavior["exclusions"]) > 0

    def test_string_exclusion_has_correct_name(self, ws: Workspace) -> None:
        """Verify string exclusion entry has event='Logout'."""
        result = ws.build_funnel_params(
            ["A", "B", "C"],
            exclusions=["Logout"],
        )
        ex_entry = result["sections"]["show"][0]["behavior"]["exclusions"][0]
        assert ex_entry["event"] == "Logout"

    def test_exclusion_parent_behavior_has_events_resource_type(
        self, ws: Workspace
    ) -> None:
        """Verify parent behavior has resourceType='events' when exclusions are set."""
        result = ws.build_funnel_params(
            ["A", "B", "C"],
            exclusions=["Logout"],
        )
        behavior = result["sections"]["show"][0]["behavior"]
        assert behavior["resourceType"] == "events"

    def test_string_exclusion_covers_all_steps(self, ws: Workspace) -> None:
        """Verify string exclusion covers from 1 to len(steps) (1-indexed)."""
        result = ws.build_funnel_params(
            ["A", "B", "C"],
            exclusions=["Logout"],
        )
        ex_entry = result["sections"]["show"][0]["behavior"]["exclusions"][0]
        assert ex_entry["steps"]["from"] == 1
        assert ex_entry["steps"]["to"] == 3  # len(["A", "B", "C"])

    def test_exclusion_with_step_range(self, ws: Workspace) -> None:
        """Verify Exclusion with from_step and to_step produces correct 1-indexed range."""
        result = ws.build_funnel_params(
            ["A", "B", "C"],
            exclusions=[Exclusion("Refund", from_step=1, to_step=2)],
        )
        ex_entry = result["sections"]["show"][0]["behavior"]["exclusions"][0]
        assert ex_entry["steps"]["from"] == 2
        assert ex_entry["steps"]["to"] == 3

    def test_default_exclusion_no_range_covers_all(self, ws: Workspace) -> None:
        """Verify Exclusion with no range covers 1 to len(steps) (1-indexed)."""
        result = ws.build_funnel_params(
            ["A", "B", "C", "D"],
            exclusions=[Exclusion("Cancel")],
        )
        ex_entry = result["sections"]["show"][0]["behavior"]["exclusions"][0]
        assert ex_entry["steps"]["from"] == 1
        assert ex_entry["steps"]["to"] == 4  # len(["A", "B", "C", "D"])

    def test_no_exclusions_produces_empty_list(self, ws: Workspace) -> None:
        """Verify no exclusions param produces an empty exclusions list."""
        result = ws.build_funnel_params(["A", "B"])
        behavior = result["sections"]["show"][0]["behavior"]
        assert behavior["exclusions"] == []


# =============================================================================
# T039: Holding constant tests
# =============================================================================


class TestBuildFunnelParamsHoldingConstant:
    """Tests for holding-constant handling (T039).

    Verifies that string and ``HoldingConstant`` object holding-constant
    specs produce correct aggregateBy entries in the behavior block.
    """

    def test_string_holding_constant_produces_aggregate_by(self, ws: Workspace) -> None:
        """Verify a string holding_constant produces a non-empty aggregateBy."""
        result = ws.build_funnel_params(
            ["A", "B"],
            holding_constant="platform",
        )
        behavior = result["sections"]["show"][0]["behavior"]
        assert len(behavior["aggregateBy"]) > 0

    def test_string_holding_constant_has_correct_value(self, ws: Workspace) -> None:
        """Verify string holding_constant entry has value='platform'."""
        result = ws.build_funnel_params(
            ["A", "B"],
            holding_constant="platform",
        )
        agg_entry = result["sections"]["show"][0]["behavior"]["aggregateBy"][0]
        assert agg_entry["value"] == "platform"

    def test_string_holding_constant_has_events_resource_type(
        self, ws: Workspace
    ) -> None:
        """Verify string holding_constant defaults to resourceType='events'."""
        result = ws.build_funnel_params(
            ["A", "B"],
            holding_constant="platform",
        )
        agg_entry = result["sections"]["show"][0]["behavior"]["aggregateBy"][0]
        assert agg_entry["resourceType"] == "events"

    def test_holding_constant_with_people_resource_type(self, ws: Workspace) -> None:
        """Verify HoldingConstant with resource_type='people' is correct."""
        result = ws.build_funnel_params(
            ["A", "B"],
            holding_constant=HoldingConstant("plan_tier", resource_type="people"),
        )
        agg_entry = result["sections"]["show"][0]["behavior"]["aggregateBy"][0]
        assert agg_entry["resourceType"] == "people"

    def test_list_of_holding_constants(self, ws: Workspace) -> None:
        """Verify a list of holding constants produces multiple aggregateBy entries."""
        result = ws.build_funnel_params(
            ["A", "B"],
            holding_constant=[
                HoldingConstant("platform"),
                HoldingConstant("plan_tier", resource_type="people"),
            ],
        )
        agg = result["sections"]["show"][0]["behavior"]["aggregateBy"]
        assert len(agg) == 2
        assert agg[0]["value"] == "platform"
        assert agg[1]["value"] == "plan_tier"

    def test_no_holding_constant_produces_empty_list(self, ws: Workspace) -> None:
        """Verify no holding_constant produces an empty aggregateBy list."""
        result = ws.build_funnel_params(["A", "B"])
        behavior = result["sections"]["show"][0]["behavior"]
        assert behavior["aggregateBy"] == []


# =============================================================================
# T005: New funnel math types
# =============================================================================


class TestBuildFunnelParamsNewMathTypes:
    """T005: New funnel math type histogram is accepted."""

    def test_math_histogram_accepted(self, ws: Workspace) -> None:
        """build_funnel_params accepts math='histogram' and sets measurement correctly."""
        result = ws.build_funnel_params(
            ["Signup", "Purchase"],
            math="histogram",
            math_property="amount",
        )
        measurement = result["sections"]["show"][0]["measurement"]
        assert measurement["math"] == "histogram"
        assert measurement["property"]["name"] == "amount"


# =============================================================================
# T009: Funnel reentry_mode parameter
# =============================================================================


class TestBuildFunnelParamsReentryMode:
    """T009: Tests for reentry_mode parameter in build_funnel_params."""

    def test_reentry_mode_aggressive(self, ws: Workspace) -> None:
        """build_funnel_params with reentry_mode='aggressive' produces funnelReentryMode."""
        result = ws.build_funnel_params(
            ["Signup", "Purchase"],
            reentry_mode="aggressive",
        )
        behavior = result["sections"]["show"][0]["behavior"]
        assert behavior["funnelReentryMode"] == "aggressive"

    def test_reentry_mode_default(self, ws: Workspace) -> None:
        """build_funnel_params with reentry_mode='default' produces funnelReentryMode."""
        result = ws.build_funnel_params(
            ["Signup", "Purchase"],
            reentry_mode="default",
        )
        behavior = result["sections"]["show"][0]["behavior"]
        assert behavior["funnelReentryMode"] == "default"

    def test_reentry_mode_basic(self, ws: Workspace) -> None:
        """build_funnel_params with reentry_mode='basic' produces funnelReentryMode."""
        result = ws.build_funnel_params(
            ["Signup", "Purchase"],
            reentry_mode="basic",
        )
        behavior = result["sections"]["show"][0]["behavior"]
        assert behavior["funnelReentryMode"] == "basic"

    def test_reentry_mode_optimized(self, ws: Workspace) -> None:
        """build_funnel_params with reentry_mode='optimized' produces funnelReentryMode."""
        result = ws.build_funnel_params(
            ["Signup", "Purchase"],
            reentry_mode="optimized",
        )
        behavior = result["sections"]["show"][0]["behavior"]
        assert behavior["funnelReentryMode"] == "optimized"

    def test_no_reentry_mode_omits_key(self, ws: Workspace) -> None:
        """build_funnel_params without reentry_mode omits funnelReentryMode (backward compat)."""
        result = ws.build_funnel_params(["Signup", "Purchase"])
        behavior = result["sections"]["show"][0]["behavior"]
        assert "funnelReentryMode" not in behavior


# =============================================================================
# T032: data_group_id on funnel query engine
# =============================================================================


class TestDataGroupIdFunnel:
    """Tests for data_group_id parameter on funnel query engine (T032)."""

    def test_build_funnel_params_with_data_group_id(self, ws: Workspace) -> None:
        """build_funnel_params with data_group_id=5 includes dataGroupId: 5 in sections."""
        result = ws.build_funnel_params(["Signup", "Purchase"], data_group_id=5)
        assert result["sections"]["dataGroupId"] == 5

    def test_build_funnel_params_without_data_group_id(self, ws: Workspace) -> None:
        """build_funnel_params without data_group_id omits dataGroupId key (backward compat)."""
        result = ws.build_funnel_params(["Signup", "Purchase"])
        assert "dataGroupId" not in result["sections"]
