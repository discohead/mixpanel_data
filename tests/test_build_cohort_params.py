"""Tests for cohort behavior bookmark param building.

Exercises the bookmark JSON generation pipeline for cohort filters
(T003, T005, T006), cohort breakdowns (T020, T021), and cohort metrics
(T038-T041) using ``build_params()``, ``build_funnel_params()``,
``build_retention_params()``, and ``build_flow_params()`` as entry points.

Uses the same Workspace fixture pattern as ``test_build_funnel_params.py``.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from pydantic import SecretStr

from mixpanel_headless import Workspace
from mixpanel_headless._internal.auth.account import ServiceAccount
from mixpanel_headless._internal.auth.session import Project, Session
from mixpanel_headless.exceptions import BookmarkValidationError
from mixpanel_headless.types import (
    CohortBreakdown,
    CohortCriteria,
    CohortDefinition,
    CohortMetric,
    Filter,
    Formula,
    GroupBy,
    Metric,
)

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
# Helpers
# =============================================================================


def _simple_cohort_def() -> CohortDefinition:
    """Create a minimal CohortDefinition for testing.

    Returns:
        CohortDefinition with a single ``did_event`` criterion.
    """
    return CohortDefinition(
        CohortCriteria.did_event("Purchase", at_least=1, within_days=30)
    )


# =============================================================================
# T003: build_filter_entry — cohort filter JSON
# =============================================================================


class TestBuildFilterEntryCohort:
    """Tests for cohort filter entry JSON structure (T003).

    Verifies that ``Filter.in_cohort()`` and ``Filter.not_in_cohort()``
    produce correct bookmark filter entries in ``sections.filter``.
    """

    def test_saved_cohort_filter_entry_resource_type(self, ws: Workspace) -> None:
        """Verify filter entry has resourceType='events'."""
        result = ws.build_params("Login", where=Filter.in_cohort(123, "Power Users"))
        entry = result["sections"]["filter"][0]
        assert entry["resourceType"] == "events"

    def test_saved_cohort_filter_entry_filter_type(self, ws: Workspace) -> None:
        """Verify filter entry has filterType='list'."""
        result = ws.build_params("Login", where=Filter.in_cohort(123, "Power Users"))
        entry = result["sections"]["filter"][0]
        assert entry["filterType"] == "list"

    def test_saved_cohort_filter_entry_value_is_cohorts(self, ws: Workspace) -> None:
        """Verify filter entry has value='$cohorts'."""
        result = ws.build_params("Login", where=Filter.in_cohort(123, "PU"))
        entry = result["sections"]["filter"][0]
        assert entry["value"] == "$cohorts"

    def test_saved_cohort_filter_entry_operator_contains(self, ws: Workspace) -> None:
        """Verify filter entry has filterOperator='contains' for in_cohort."""
        result = ws.build_params("Login", where=Filter.in_cohort(123, "PU"))
        entry = result["sections"]["filter"][0]
        assert entry["filterOperator"] == "contains"

    def test_saved_cohort_filter_entry_filter_value_structure(
        self, ws: Workspace
    ) -> None:
        """Verify filterValue contains cohort entry with id and name."""
        result = ws.build_params("Login", where=Filter.in_cohort(123, "Power Users"))
        entry = result["sections"]["filter"][0]
        fv = entry["filterValue"]
        assert isinstance(fv, list)
        assert len(fv) == 1
        cohort = fv[0]["cohort"]
        assert cohort["id"] == 123
        assert cohort["name"] == "Power Users"
        assert cohort["negated"] is False

    def test_inline_cohort_filter_entry_has_raw_cohort(self, ws: Workspace) -> None:
        """Verify inline CohortDefinition produces raw_cohort in filterValue."""
        cohort_def = _simple_cohort_def()
        result = ws.build_params(
            "Login", where=Filter.in_cohort(cohort_def, name="Buyers")
        )
        entry = result["sections"]["filter"][0]
        fv = entry["filterValue"]
        cohort = fv[0]["cohort"]
        assert "raw_cohort" in cohort
        assert "id" not in cohort
        assert cohort["name"] == "Buyers"

    def test_not_in_cohort_filter_entry_operator(self, ws: Workspace) -> None:
        """Verify not_in_cohort produces filterOperator='does not contain'."""
        result = ws.build_params("Login", where=Filter.not_in_cohort(789, "Bots"))
        entry = result["sections"]["filter"][0]
        assert entry["filterOperator"] == "does not contain"

    def test_not_in_cohort_filter_value_negated(self, ws: Workspace) -> None:
        """Verify not_in_cohort sets negated=True in filterValue."""
        result = ws.build_params("Login", where=Filter.not_in_cohort(789, "Bots"))
        entry = result["sections"]["filter"][0]
        cohort = entry["filterValue"][0]["cohort"]
        assert cohort["negated"] is True


# =============================================================================
# T005: build_filter_section — mixed cohort + property filters
# =============================================================================


class TestBuildFilterSectionMixed:
    """Tests for mixed cohort and property filters in sections.filter (T005)."""

    def test_mixed_filters_produce_two_entries(self, ws: Workspace) -> None:
        """Verify mix of cohort and property filters produces two filter entries."""
        result = ws.build_params(
            "Login",
            where=[
                Filter.in_cohort(123, "PU"),
                Filter.equals("country", "US"),
            ],
        )
        filter_section = result["sections"]["filter"]
        assert len(filter_section) == 2

    def test_mixed_filters_cohort_entry_first(self, ws: Workspace) -> None:
        """Verify cohort filter appears in filter section."""
        result = ws.build_params(
            "Login",
            where=[
                Filter.in_cohort(123, "PU"),
                Filter.equals("country", "US"),
            ],
        )
        filter_section = result["sections"]["filter"]
        values = [e["value"] for e in filter_section]
        assert "$cohorts" in values
        assert "country" in values


# =============================================================================
# T006: build_flow_params — flow cohort filter (filter_by_cohort)
# =============================================================================


class TestBuildFlowCohortFilter:
    """Tests for flow-specific filter_by_cohort format (T006).

    Verifies that ``build_flow_params()`` with ``where=Filter.in_cohort()``
    produces the legacy ``filter_by_cohort`` top-level key.
    """

    def test_flow_cohort_filter_has_filter_by_cohort_key(self, ws: Workspace) -> None:
        """Verify build_flow_params produces filter_by_cohort key."""
        result = ws.build_flow_params(
            "Login", where=Filter.in_cohort(123, "Power Users")
        )
        assert "filter_by_cohort" in result

    def test_flow_cohort_filter_id(self, ws: Workspace) -> None:
        """Verify filter_by_cohort has correct id."""
        result = ws.build_flow_params(
            "Login", where=Filter.in_cohort(123, "Power Users")
        )
        fbc = result["filter_by_cohort"]
        assert fbc["id"] == 123

    def test_flow_cohort_filter_name(self, ws: Workspace) -> None:
        """Verify filter_by_cohort has correct name."""
        result = ws.build_flow_params(
            "Login", where=Filter.in_cohort(123, "Power Users")
        )
        fbc = result["filter_by_cohort"]
        assert fbc["name"] == "Power Users"

    def test_flow_cohort_filter_negated_false(self, ws: Workspace) -> None:
        """Verify filter_by_cohort has negated=False for in_cohort."""
        result = ws.build_flow_params("Login", where=Filter.in_cohort(123, "PU"))
        fbc = result["filter_by_cohort"]
        assert fbc["negated"] is False

    def test_flow_property_filter_produces_filter_by_event(self, ws: Workspace) -> None:
        """Verify property filter in flow where= produces filter_by_event."""
        result = ws.build_flow_params("Login", where=Filter.equals("country", "US"))
        assert "filter_by_event" in result
        assert result["filter_by_event"]["operator"] == "and"
        assert len(result["filter_by_event"]["children"]) == 1


# =============================================================================
# T020: build_group_section — CohortBreakdown
# =============================================================================


class TestBuildGroupSectionCohort:
    """Tests for CohortBreakdown in sections.group (T020).

    Verifies that ``CohortBreakdown`` produces correct cohort group
    entries with optional negated counterpart.
    """

    def test_cohort_breakdown_produces_group_entry(self, ws: Workspace) -> None:
        """Verify CohortBreakdown produces a non-empty sections.group."""
        result = ws.build_params(
            "Login",
            group_by=CohortBreakdown(123, "Power Users"),
        )
        group_section = result["sections"]["group"]
        assert len(group_section) > 0

    def test_cohort_breakdown_entry_has_cohorts_key(self, ws: Workspace) -> None:
        """Verify group entry has 'cohorts' key."""
        result = ws.build_params(
            "Login",
            group_by=CohortBreakdown(123, "Power Users"),
        )
        group_entry = result["sections"]["group"][0]
        assert "cohorts" in group_entry

    def test_cohort_breakdown_include_negated_true_has_two_cohort_entries(
        self, ws: Workspace
    ) -> None:
        """Verify include_negated=True produces two cohort entries."""
        result = ws.build_params(
            "Login",
            group_by=CohortBreakdown(123, "Power Users", include_negated=True),
        )
        group_entry = result["sections"]["group"][0]
        cohorts = group_entry["cohorts"]
        assert len(cohorts) == 2
        assert cohorts[0]["negated"] is False
        assert cohorts[1]["negated"] is True

    def test_cohort_breakdown_include_negated_false_has_one_entry(
        self, ws: Workspace
    ) -> None:
        """Verify include_negated=False produces one cohort entry."""
        result = ws.build_params(
            "Login",
            group_by=CohortBreakdown(123, "Power Users", include_negated=False),
        )
        group_entry = result["sections"]["group"][0]
        cohorts = group_entry["cohorts"]
        assert len(cohorts) == 1
        assert cohorts[0]["negated"] is False

    def test_cohort_breakdown_value_has_names(self, ws: Workspace) -> None:
        """Verify group entry 'value' contains cohort names."""
        result = ws.build_params(
            "Login",
            group_by=CohortBreakdown(123, "Power Users", include_negated=True),
        )
        group_entry = result["sections"]["group"][0]
        value = group_entry["value"]
        assert isinstance(value, list)
        assert "Power Users" in value

    def test_cohort_breakdown_inline_has_raw_cohort(self, ws: Workspace) -> None:
        """Verify inline CohortDefinition uses raw_cohort in cohorts entry."""
        cohort_def = _simple_cohort_def()
        result = ws.build_params(
            "Login",
            group_by=CohortBreakdown(cohort_def, "Active"),
        )
        group_entry = result["sections"]["group"][0]
        cohort = group_entry["cohorts"][0]
        assert "raw_cohort" in cohort

    def test_cohort_breakdown_resource_type_events(self, ws: Workspace) -> None:
        """Verify group entry has resourceType='events'."""
        result = ws.build_params(
            "Login",
            group_by=CohortBreakdown(123, "PU"),
        )
        group_entry = result["sections"]["group"][0]
        assert group_entry["resourceType"] == "events"


# =============================================================================
# T021: Mixed CohortBreakdown + GroupBy/str
# =============================================================================


class TestBuildGroupSectionMixed:
    """Tests for mixed CohortBreakdown and GroupBy in group_by list (T021)."""

    def test_mixed_breakdown_and_string_produces_two_entries(
        self, ws: Workspace
    ) -> None:
        """Verify mix of CohortBreakdown and string produces two group entries."""
        result = ws.build_params(
            "Login",
            group_by=[CohortBreakdown(123, "PU"), "country"],
        )
        group_section = result["sections"]["group"]
        assert len(group_section) == 2

    def test_mixed_breakdown_and_groupby_produces_two_entries(
        self, ws: Workspace
    ) -> None:
        """Verify mix of CohortBreakdown and GroupBy produces two group entries."""
        result = ws.build_params(
            "Login",
            group_by=[CohortBreakdown(123, "PU"), GroupBy("platform")],
        )
        group_section = result["sections"]["group"]
        assert len(group_section) == 2


# =============================================================================
# T009: build_params — cohort filter in insights
# =============================================================================


class TestBuildParamsCohortFilter:
    """Tests for cohort filters in build_params() (T009).

    Verifies that ``where=Filter.in_cohort()`` populates sections.filter
    in insights bookmark params.
    """

    def test_cohort_filter_populates_filter_section(self, ws: Workspace) -> None:
        """Verify cohort filter appears in sections.filter."""
        result = ws.build_params("Login", where=Filter.in_cohort(123, "PU"))
        assert len(result["sections"]["filter"]) > 0

    def test_cohort_filter_entry_value_is_cohorts(self, ws: Workspace) -> None:
        """Verify the filter entry targets $cohorts property."""
        result = ws.build_params("Login", where=Filter.in_cohort(123, "PU"))
        entry = result["sections"]["filter"][0]
        assert entry["value"] == "$cohorts"


# =============================================================================
# T010: build_funnel_params — cohort filter in funnels
# =============================================================================


class TestBuildFunnelParamsCohortFilter:
    """Tests for cohort filters in build_funnel_params() (T010)."""

    def test_cohort_filter_populates_filter_section(self, ws: Workspace) -> None:
        """Verify cohort filter appears in funnel sections.filter."""
        result = ws.build_funnel_params(
            ["Signup", "Purchase"],
            where=Filter.in_cohort(123, "PU"),
        )
        filter_section = result["sections"]["filter"]
        assert len(filter_section) > 0

    def test_cohort_filter_entry_value_is_cohorts(self, ws: Workspace) -> None:
        """Verify the filter entry targets $cohorts in funnel params."""
        result = ws.build_funnel_params(
            ["Signup", "Purchase"],
            where=Filter.in_cohort(123, "PU"),
        )
        entry = result["sections"]["filter"][0]
        assert entry["value"] == "$cohorts"


# =============================================================================
# T011: build_retention_params — cohort filter in retention
# =============================================================================


class TestBuildRetentionParamsCohortFilter:
    """Tests for cohort filters in build_retention_params() (T011)."""

    def test_cohort_filter_populates_filter_section(self, ws: Workspace) -> None:
        """Verify cohort filter appears in retention sections.filter."""
        result = ws.build_retention_params(
            "Signup",
            "Login",
            where=Filter.in_cohort(123, "PU"),
        )
        filter_section = result["sections"]["filter"]
        assert len(filter_section) > 0

    def test_cohort_filter_entry_value_is_cohorts(self, ws: Workspace) -> None:
        """Verify the filter entry targets $cohorts in retention params."""
        result = ws.build_retention_params(
            "Signup",
            "Login",
            where=Filter.in_cohort(123, "PU"),
        )
        entry = result["sections"]["filter"][0]
        assert entry["value"] == "$cohorts"


# =============================================================================
# T024: build_params — CohortBreakdown in insights
# =============================================================================


class TestBuildParamsCohortBreakdown:
    """Tests for CohortBreakdown in build_params() group_by (T024)."""

    def test_cohort_breakdown_populates_group_section(self, ws: Workspace) -> None:
        """Verify CohortBreakdown appears in sections.group."""
        result = ws.build_params(
            "Login",
            group_by=CohortBreakdown(123, "PU"),
        )
        assert len(result["sections"]["group"]) > 0

    def test_cohort_breakdown_entry_has_cohorts(self, ws: Workspace) -> None:
        """Verify the group entry has cohorts key."""
        result = ws.build_params(
            "Login",
            group_by=CohortBreakdown(123, "PU"),
        )
        entry = result["sections"]["group"][0]
        assert "cohorts" in entry


# =============================================================================
# T025: build_funnel_params — CohortBreakdown in funnels
# =============================================================================


class TestBuildFunnelParamsCohortBreakdown:
    """Tests for CohortBreakdown in build_funnel_params() group_by (T025)."""

    def test_cohort_breakdown_populates_group_section(self, ws: Workspace) -> None:
        """Verify CohortBreakdown appears in funnel sections.group."""
        result = ws.build_funnel_params(
            ["Signup", "Purchase"],
            group_by=CohortBreakdown(123, "PU"),
        )
        assert len(result["sections"]["group"]) > 0

    def test_cohort_breakdown_entry_has_cohorts(self, ws: Workspace) -> None:
        """Verify the funnel group entry has cohorts key."""
        result = ws.build_funnel_params(
            ["Signup", "Purchase"],
            group_by=CohortBreakdown(123, "PU"),
        )
        entry = result["sections"]["group"][0]
        assert "cohorts" in entry


# =============================================================================
# T026: build_retention_params — CohortBreakdown in retention
# =============================================================================


class TestBuildRetentionParamsCohortBreakdown:
    """Tests for CohortBreakdown in build_retention_params() group_by (T026).

    Also tests CB3: mutual exclusivity with property GroupBy.
    """

    def test_cohort_breakdown_alone_accepted(self, ws: Workspace) -> None:
        """Verify CohortBreakdown alone works in retention group_by."""
        result = ws.build_retention_params(
            "Signup",
            "Login",
            group_by=CohortBreakdown(123, "PU"),
        )
        assert len(result["sections"]["group"]) > 0

    def test_cb3_mixed_with_groupby_raises(self, ws: Workspace) -> None:
        """CB3: CohortBreakdown mixed with GroupBy in retention raises."""
        with pytest.raises(BookmarkValidationError):
            ws.build_retention_params(
                "Signup",
                "Login",
                group_by=[CohortBreakdown(123, "PU"), GroupBy("platform")],
            )

    def test_cb3_mixed_with_string_raises(self, ws: Workspace) -> None:
        """CB3: CohortBreakdown mixed with string in retention raises."""
        with pytest.raises(BookmarkValidationError):
            ws.build_retention_params(
                "Signup",
                "Login",
                group_by=[CohortBreakdown(123, "PU"), "platform"],
            )


# =============================================================================
# T038: build_params — CohortMetric in events
# =============================================================================


class TestBuildParamsCohortMetric:
    """Tests for CohortMetric in build_params() events parameter (T038).

    Verifies that ``CohortMetric`` produces correct ``sections.show[]``
    entries with ``behavior.type: "cohort"``.
    """

    def test_cohort_metric_produces_show_entry(self, ws: Workspace) -> None:
        """Verify CohortMetric produces a non-empty sections.show."""
        result = ws.build_params(CohortMetric(123, "Power Users"))
        assert len(result["sections"]["show"]) > 0

    def test_cohort_metric_show_type_is_metric(self, ws: Workspace) -> None:
        """Verify show entry has type='metric'."""
        result = ws.build_params(CohortMetric(123, "Power Users"))
        entry = result["sections"]["show"][0]
        assert entry.get("type") == "metric"

    def test_cohort_metric_behavior_type_is_cohort(self, ws: Workspace) -> None:
        """Verify behavior.type is 'cohort'."""
        result = ws.build_params(CohortMetric(123, "Power Users"))
        behavior = result["sections"]["show"][0]["behavior"]
        assert behavior["type"] == "cohort"

    def test_cohort_metric_behavior_name(self, ws: Workspace) -> None:
        """Verify behavior.name matches the provided name."""
        result = ws.build_params(CohortMetric(123, "Power Users"))
        behavior = result["sections"]["show"][0]["behavior"]
        assert behavior["name"] == "Power Users"

    def test_cohort_metric_behavior_id(self, ws: Workspace) -> None:
        """Verify behavior.id matches the cohort ID."""
        result = ws.build_params(CohortMetric(123, "Power Users"))
        behavior = result["sections"]["show"][0]["behavior"]
        assert behavior["id"] == 123

    def test_cohort_metric_behavior_resource_type(self, ws: Workspace) -> None:
        """Verify behavior.resourceType is 'cohorts'."""
        result = ws.build_params(CohortMetric(123, "Power Users"))
        behavior = result["sections"]["show"][0]["behavior"]
        assert behavior["resourceType"] == "cohorts"

    def test_cohort_metric_behavior_dataset(self, ws: Workspace) -> None:
        """Verify behavior.dataset is '$mixpanel'."""
        result = ws.build_params(CohortMetric(123, "Power Users"))
        behavior = result["sections"]["show"][0]["behavior"]
        assert behavior["dataset"] == "$mixpanel"

    def test_cohort_metric_measurement_math_unique(self, ws: Workspace) -> None:
        """Verify measurement.math is 'unique' for cohort metrics."""
        result = ws.build_params(CohortMetric(123, "Power Users"))
        measurement = result["sections"]["show"][0]["measurement"]
        assert measurement["math"] == "unique"

    def test_cohort_metric_measurement_property_none(self, ws: Workspace) -> None:
        """Verify measurement.property is None for cohort metrics."""
        result = ws.build_params(CohortMetric(123, "Power Users"))
        measurement = result["sections"]["show"][0]["measurement"]
        assert measurement["property"] is None

    def test_cohort_metric_inline_rejected_cm5(self) -> None:
        """CM5: Inline CohortDefinition in CohortMetric raises at construction."""
        cohort_def = _simple_cohort_def()
        with pytest.raises(
            ValueError,
            match="CohortMetric does not support inline CohortDefinition",
        ):
            CohortMetric(cohort_def, "Active")


# =============================================================================
# T039: build_params — CohortMetric mixed with Metric and Formula
# =============================================================================


class TestBuildParamsCohortMetricMixed:
    """Tests for CohortMetric mixed with Metric and Formula (T039)."""

    def test_mixed_cohort_metric_and_metric(self, ws: Workspace) -> None:
        """Verify CohortMetric and Metric together produce two show entries."""
        result = ws.build_params(
            [
                CohortMetric(123, "Power Users"),
                Metric("Login"),
            ]
        )
        assert len(result["sections"]["show"]) == 2

    def test_mixed_cohort_metric_and_string(self, ws: Workspace) -> None:
        """Verify CohortMetric and string event together produce two show entries."""
        result = ws.build_params(
            [
                CohortMetric(123, "PU"),
                "Login",
            ]
        )
        assert len(result["sections"]["show"]) == 2

    def test_mixed_cohort_metric_and_formula(self, ws: Workspace) -> None:
        """Verify CohortMetric and Formula together work."""
        result = ws.build_params(
            [
                CohortMetric(123, "PU"),
                Metric("Login"),
                Formula("A/B", label="Rate"),
            ]
        )
        show = result["sections"]["show"]
        # Should have at least the cohort metric and metric entries
        assert len(show) >= 2


# =============================================================================
# T040: build_params — CM3 math/math_property/per_user ignored
# =============================================================================


class TestBuildParamsCohortMetricMathIgnored:
    """Tests for CM3: math/math_property/per_user ignored for CohortMetric (T040).

    When ``CohortMetric`` is the only event, top-level ``math``,
    ``math_property``, and ``per_user`` should not affect the cohort
    metric show entry.
    """

    def test_math_total_does_not_override_cohort_math(self, ws: Workspace) -> None:
        """Verify math='total' does not change cohort metric's math='unique'."""
        result = ws.build_params(
            CohortMetric(123, "PU"),
            math="total",
        )
        measurement = result["sections"]["show"][0]["measurement"]
        assert measurement["math"] == "unique"

    def test_math_property_does_not_apply(self, ws: Workspace) -> None:
        """Verify math_property does not appear in cohort metric measurement."""
        result = ws.build_params(
            CohortMetric(123, "PU"),
            math="average",
            math_property="amount",
        )
        measurement = result["sections"]["show"][0]["measurement"]
        assert measurement["property"] is None

    def test_property_math_without_property_ignored_for_cohort_only(
        self, ws: Workspace
    ) -> None:
        """Verify CohortMetric-only query with property-math and no math_property succeeds.

        Top-level math is only consumed by plain string events.  When all
        events are CohortMetric, math/math_property/per_user are irrelevant
        and must not trigger V1/V2/V3/V26/V27 validation errors (FR-020).
        """
        # math="average" normally requires math_property — but should be
        # ignored when the only consumer is CohortMetric.
        result = ws.build_params(
            CohortMetric(123, "PU"),
            math="average",
        )
        measurement = result["sections"]["show"][0]["measurement"]
        assert measurement["math"] == "unique"

    def test_percentile_math_without_value_ignored_for_cohort_only(
        self, ws: Workspace
    ) -> None:
        """Verify CohortMetric-only query with math='percentile' succeeds.

        V26 (percentile requires percentile_value) must not fire when
        there are no plain string events to consume the parameter.
        """
        result = ws.build_params(
            CohortMetric(123, "PU"),
            math="percentile",
        )
        measurement = result["sections"]["show"][0]["measurement"]
        assert measurement["math"] == "unique"

    def test_histogram_math_without_per_user_ignored_for_cohort_only(
        self, ws: Workspace
    ) -> None:
        """Verify CohortMetric-only query with math='histogram' succeeds.

        V27 (histogram requires per_user) must not fire when there are
        no plain string events to consume the parameter.
        """
        result = ws.build_params(
            CohortMetric(123, "PU"),
            math="histogram",
        )
        measurement = result["sections"]["show"][0]["measurement"]
        assert measurement["math"] == "unique"

    def test_per_user_incompatible_math_ignored_for_cohort_only(
        self, ws: Workspace
    ) -> None:
        """Verify CohortMetric-only query with per_user + math='unique' succeeds.

        V3 (per_user incompatible with unique/DAU/WAU/MAU) must not fire
        when there are no plain string events to consume the parameter.
        """
        result = ws.build_params(
            CohortMetric(123, "PU"),
            math="unique",
            per_user="average",
        )
        measurement = result["sections"]["show"][0]["measurement"]
        assert measurement["math"] == "unique"

    def test_mixed_events_still_validate_math(self, ws: Workspace) -> None:
        """Verify mixed CohortMetric + plain event still validates top-level math.

        When a plain string event is present, it consumes top-level math,
        so V1 must still fire for math='average' without math_property.
        """
        with pytest.raises(BookmarkValidationError, match="requires math_property"):
            ws.build_params(
                [CohortMetric(123, "PU"), "Login"],
                math="average",
            )

    def test_per_user_does_not_apply(self, ws: Workspace) -> None:
        """Verify per_user does not appear in cohort metric measurement.

        CohortMetric always uses ``math="unique"`` with no perUserAggregation,
        regardless of top-level per_user. We test by building params with
        a CohortMetric alongside a regular Metric that uses per_user, and
        verifying the CohortMetric show entry has no perUserAggregation.
        """
        result = ws.build_params(
            [
                CohortMetric(123, "PU"),
                Metric("Login", math="average", property="amount", per_user="average"),
            ],
        )
        # CohortMetric is first in the show list
        cm_measurement = result["sections"]["show"][0]["measurement"]
        assert cm_measurement.get("perUserAggregation") is None
        assert cm_measurement["math"] == "unique"


# =============================================================================
# T007: query_flow where= parameter — cohort filter
# =============================================================================


class TestQueryFlowCohortFilter:
    """Tests for query_flow where= parameter (T007).

    Verifies that flow queries accept cohort filters and reject
    non-cohort filters in the ``where=`` parameter.
    """

    def test_flow_params_with_cohort_filter_has_filter_by_cohort(
        self, ws: Workspace
    ) -> None:
        """Verify build_flow_params with cohort filter produces filter_by_cohort."""
        result = ws.build_flow_params("Login", where=Filter.in_cohort(123, "PU"))
        assert "filter_by_cohort" in result

    def test_flow_params_without_where_has_no_filter_by_cohort(
        self, ws: Workspace
    ) -> None:
        """Verify build_flow_params without where= has no filter_by_cohort."""
        result = ws.build_flow_params("Login")
        assert "filter_by_cohort" not in result

    def test_flow_property_filter_produces_filter_by_event(self, ws: Workspace) -> None:
        """Verify property filter in flow where= produces filter_by_event."""
        result = ws.build_flow_params("Login", where=Filter.equals("country", "US"))
        assert "filter_by_event" in result
        assert result["filter_by_event"]["operator"] == "and"
        assert len(result["filter_by_event"]["children"]) == 1

    def test_flow_multiple_cohort_filters_raises_value_error(
        self, ws: Workspace
    ) -> None:
        """Verify multiple cohort filters in flow where= raises ValueError."""
        with pytest.raises(
            ValueError,
            match="query_flow supports a single cohort filter, but 2",
        ):
            ws.build_flow_params(
                "Login",
                where=[
                    Filter.in_cohort(123, "A"),
                    Filter.in_cohort(456, "B"),
                ],
            )


# =============================================================================
# build_flow_cohort_filter — direct unit tests
# =============================================================================


class TestBuildFlowCohortFilterDirect:
    """Direct tests for build_flow_cohort_filter()."""

    def test_saved_cohort_filter(self) -> None:
        """Saved cohort filter produces dict with id."""
        from mixpanel_headless._internal.bookmark_builders import (
            build_flow_cohort_filter,
        )

        result = build_flow_cohort_filter(Filter.in_cohort(123, "PU"))
        assert result is not None
        assert result["id"] == 123
        assert result["name"] == "PU"
        assert result["negated"] is False

    def test_inline_cohort_filter(self) -> None:
        """Inline cohort filter produces dict with raw_cohort."""
        from mixpanel_headless._internal.bookmark_builders import (
            build_flow_cohort_filter,
        )

        cohort_def = _simple_cohort_def()
        result = build_flow_cohort_filter(Filter.in_cohort(cohort_def, name="Active"))
        assert result is not None
        assert "raw_cohort" in result
        assert result["name"] == "Active"
        assert result["negated"] is False

    def test_not_in_cohort_negated(self) -> None:
        """not_in_cohort filter produces negated=True."""
        from mixpanel_headless._internal.bookmark_builders import (
            build_flow_cohort_filter,
        )

        result = build_flow_cohort_filter(Filter.not_in_cohort(123, "Bots"))
        assert result is not None
        assert result["negated"] is True

    def test_non_cohort_filter_raises(self) -> None:
        """Non-cohort filter raises ValueError."""
        from mixpanel_headless._internal.bookmark_builders import (
            build_flow_cohort_filter,
        )

        with pytest.raises(ValueError, match="only accepts cohort filters"):
            build_flow_cohort_filter(Filter.equals("country", "US"))

    def test_multiple_filters_raises(self) -> None:
        """Multiple cohort filters raises ValueError."""
        from mixpanel_headless._internal.bookmark_builders import (
            build_flow_cohort_filter,
        )

        with pytest.raises(ValueError, match="single cohort filter, but 2"):
            build_flow_cohort_filter(
                [Filter.in_cohort(1, "A"), Filter.in_cohort(2, "B")]
            )
