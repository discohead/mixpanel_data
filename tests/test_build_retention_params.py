"""Tests for Workspace.build_retention_params().

Exercises the retention bookmark param-building pipeline: normalization,
validation, and bookmark JSON structure generation.
Uses ``build_retention_params()`` as the public entry point since it delegates
through ``_build_retention_params()`` without requiring API credentials.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from pydantic import SecretStr

from mixpanel_headless import Workspace
from mixpanel_headless._internal.auth.account import ServiceAccount
from mixpanel_headless._internal.auth.session import Project, Session

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
# T015: Default structure tests
# =============================================================================


class TestBuildRetentionParamsDefaults:
    """Tests for default bookmark structure (T015).

    Verifies that ``build_retention_params("Signup", "Login")`` produces
    the correct bookmark JSON with all default values.
    """

    def test_behavior_type_is_retention(self, ws: Workspace) -> None:
        """Verify sections.show[0].behavior.type is 'retention'."""
        result = ws.build_retention_params("Signup", "Login")
        behavior = result["sections"]["show"][0]["behavior"]
        assert behavior["type"] == "retention"

    def test_behaviors_has_two_entries(self, ws: Workspace) -> None:
        """Verify behaviors list has exactly 2 entries (born + return)."""
        result = ws.build_retention_params("Signup", "Login")
        behaviors = result["sections"]["show"][0]["behavior"]["behaviors"]
        assert len(behaviors) == 2

    def test_behavior_names_match_events(self, ws: Workspace) -> None:
        """Verify behavior names match born_event and return_event."""
        result = ws.build_retention_params("Signup", "Login")
        behaviors = result["sections"]["show"][0]["behavior"]["behaviors"]
        assert behaviors[0]["name"] == "Signup"
        assert behaviors[1]["name"] == "Login"

    def test_retention_unit_defaults_to_week(self, ws: Workspace) -> None:
        """Verify retentionUnit defaults to 'week'."""
        result = ws.build_retention_params("Signup", "Login")
        behavior = result["sections"]["show"][0]["behavior"]
        assert behavior["retentionUnit"] == "week"

    def test_alignment_defaults_to_birth(self, ws: Workspace) -> None:
        """Verify retentionAlignmentType defaults to 'birth'."""
        result = ws.build_retention_params("Signup", "Login")
        behavior = result["sections"]["show"][0]["behavior"]
        assert behavior["retentionAlignmentType"] == "birth"

    def test_measurement_math_defaults_to_retention_rate(self, ws: Workspace) -> None:
        """Verify measurement.math defaults to 'retention_rate'."""
        result = ws.build_retention_params("Signup", "Login")
        measurement = result["sections"]["show"][0]["measurement"]
        assert measurement["math"] == "retention_rate"

    def test_chart_type_defaults_to_retention_curve(self, ws: Workspace) -> None:
        """Verify displayOptions.chartType defaults to 'retention-curve' (mode='curve')."""
        result = ws.build_retention_params("Signup", "Login")
        assert result["displayOptions"]["chartType"] == "retention-curve"

    def test_sorting_object_present(self, ws: Workspace) -> None:
        """Verify sorting object is included with expected chart-type keys.

        The Mixpanel UI requires a sorting object to render retention
        reports on dashboards without crashing.
        """
        result = ws.build_retention_params("Signup", "Login")
        sorting = result["sorting"]
        assert "bar" in sorting
        assert "line" in sorting
        assert "table" in sorting
        assert sorting["bar"]["sortBy"] == "column"

    def test_column_widths_present(self, ws: Workspace) -> None:
        """Verify columnWidths object is included.

        Required by the Mixpanel UI for dashboard rendering.
        """
        result = ws.build_retention_params("Signup", "Login")
        assert result["columnWidths"] == {"bar": {}}

    def test_custom_bucket_sizes_defaults_to_empty_list(self, ws: Workspace) -> None:
        """Verify retentionCustomBucketSizes defaults to empty list."""
        result = ws.build_retention_params("Signup", "Login")
        behavior = result["sections"]["show"][0]["behavior"]
        assert behavior["retentionCustomBucketSizes"] == []

    def test_has_sections_with_expected_keys(self, ws: Workspace) -> None:
        """Verify sections dict contains show, time, filter, group, formula."""
        result = ws.build_retention_params("Signup", "Login")
        sections = result["sections"]
        assert "show" in sections
        assert "time" in sections
        assert "filter" in sections
        assert "group" in sections
        assert "formula" in sections

    def test_has_display_options_key(self, ws: Workspace) -> None:
        """Verify result has 'displayOptions' key."""
        result = ws.build_retention_params("Signup", "Login")
        assert "displayOptions" in result


# =============================================================================
# T016: Shared builder tests (time, filter, group sections)
# =============================================================================


class TestBuildRetentionParamsTimeSections:
    """Tests for shared section builders (T016).

    Verifies that the time, filter, and group sections use the shared
    bookmark builder infrastructure correctly.
    """

    def test_default_time_section_is_in_the_last(self, ws: Workspace) -> None:
        """Verify default time section uses 'in the last' with last=30."""
        result = ws.build_retention_params("Signup", "Login")
        time_section = result["sections"]["time"]
        assert len(time_section) > 0
        time_entry = time_section[0]
        assert time_entry["dateRangeType"] == "in the last"
        assert time_entry["window"]["value"] == 30
        assert time_entry["window"]["unit"] == "day"

    def test_explicit_dates_produce_between_range(self, ws: Workspace) -> None:
        """Verify from_date/to_date produces a 'between' dateRangeType."""
        result = ws.build_retention_params(
            "Signup",
            "Login",
            from_date="2025-01-01",
            to_date="2025-03-31",
        )
        time_section = result["sections"]["time"]
        assert len(time_section) > 0
        time_entry = time_section[0]
        assert time_entry["dateRangeType"] == "between"
        assert time_entry["value"] == ["2025-01-01", "2025-03-31"]

    def test_filter_section_is_empty_list_when_no_where(self, ws: Workspace) -> None:
        """Verify sections.filter is empty list when no where filter provided."""
        result = ws.build_retention_params("Signup", "Login")
        assert result["sections"]["filter"] == []

    def test_group_section_is_empty_list_when_no_group_by(self, ws: Workspace) -> None:
        """Verify sections.group is empty list when no group_by provided."""
        result = ws.build_retention_params("Signup", "Login")
        assert result["sections"]["group"] == []


# =============================================================================
# T-US2: Per-event filters
# =============================================================================


class TestBuildRetentionParamsPerEventFilters:
    """Tests for per-event filter handling in retention bookmark params."""

    def test_retention_event_with_filters(self, ws: Workspace) -> None:
        """RetentionEvent with filters must populate behavior[0].filters as non-empty list."""
        from mixpanel_headless.types import Filter, RetentionEvent

        born = RetentionEvent("Signup", filters=[Filter.equals("source", "organic")])
        result = ws.build_retention_params(born, RetentionEvent("Login"))
        behaviors = result["sections"]["show"][0]["behavior"]["behaviors"]
        assert isinstance(behaviors[0]["filters"], list)
        assert len(behaviors[0]["filters"]) > 0

    def test_filters_combinator_maps_to_determiner(self, ws: Workspace) -> None:
        """filters_combinator='any' must map to filtersDeterminer='any' in behavior."""
        from mixpanel_headless.types import Filter, RetentionEvent

        born = RetentionEvent(
            "Signup",
            filters=[Filter.equals("source", "organic")],
            filters_combinator="any",
        )
        result = ws.build_retention_params(born, RetentionEvent("Login"))
        behaviors = result["sections"]["show"][0]["behavior"]["behaviors"]
        assert behaviors[0]["filtersDeterminer"] == "any"

    def test_no_filters_produces_empty_array(self, ws: Workspace) -> None:
        """Default RetentionEvent must have an empty filters array in behavior."""
        from mixpanel_headless.types import RetentionEvent

        result = ws.build_retention_params(
            RetentionEvent("Signup"), RetentionEvent("Login")
        )
        behaviors = result["sections"]["show"][0]["behavior"]["behaviors"]
        assert behaviors[0]["filters"] == []
        assert behaviors[1]["filters"] == []


# =============================================================================
# T-US2: Global filters and group-by
# =============================================================================


class TestBuildRetentionParamsGlobalFilters:
    """Tests for global where filter and group_by in retention bookmark params."""

    def test_where_filter_populates_filter_section(self, ws: Workspace) -> None:
        """Passing where=Filter.equals(...) must populate sections.filter as non-empty."""
        from mixpanel_headless.types import Filter

        result = ws.build_retention_params(
            "Signup",
            "Login",
            where=Filter.equals("platform", "iOS"),
        )
        assert len(result["sections"]["filter"]) > 0

    def test_group_by_string_populates_group_section(self, ws: Workspace) -> None:
        """Passing group_by='platform' must populate sections.group as non-empty."""
        result = ws.build_retention_params(
            "Signup",
            "Login",
            group_by="platform",
        )
        assert len(result["sections"]["group"]) > 0


# =============================================================================
# T-US3: Custom bucket sizes
# =============================================================================


class TestBuildRetentionParamsBucketSizes:
    """Tests for custom bucket sizes in retention bookmark params."""

    def test_bucket_sizes_populates_custom_field(self, ws: Workspace) -> None:
        """Explicit bucket_sizes must populate retentionCustomBucketSizes."""
        result = ws.build_retention_params(
            "Signup",
            "Login",
            bucket_sizes=[1, 3, 7, 14, 30],
        )
        behavior = result["sections"]["show"][0]["behavior"]
        assert behavior["retentionCustomBucketSizes"] == [1, 3, 7, 14, 30]

    def test_none_bucket_sizes_produces_empty_list(self, ws: Workspace) -> None:
        """Default (None) bucket_sizes must produce retentionCustomBucketSizes == []."""
        result = ws.build_retention_params("Signup", "Login")
        behavior = result["sections"]["show"][0]["behavior"]
        assert behavior["retentionCustomBucketSizes"] == []


# =============================================================================
# T-US6: Display modes
# =============================================================================


class TestBuildRetentionParamsMode:
    """Tests for display mode → chartType mapping in retention bookmark params."""

    def test_mode_curve_produces_retention_curve_chart(self, ws: Workspace) -> None:
        """mode='curve' must produce chartType 'retention-curve'."""
        result = ws.build_retention_params("Signup", "Login", mode="curve")
        assert result["displayOptions"]["chartType"] == "retention-curve"

    def test_mode_trends_produces_line_chart(self, ws: Workspace) -> None:
        """mode='trends' must produce chartType 'line'."""
        result = ws.build_retention_params("Signup", "Login", mode="trends")
        assert result["displayOptions"]["chartType"] == "line"

    def test_mode_table_produces_table_chart(self, ws: Workspace) -> None:
        """mode='table' must produce chartType 'table'."""
        result = ws.build_retention_params("Signup", "Login", mode="table")
        assert result["displayOptions"]["chartType"] == "table"


# =============================================================================
# T005: New retention math types
# =============================================================================


class TestBuildRetentionParamsNewMathTypes:
    """T005: New retention math types total and average are accepted."""

    def test_math_total_accepted(self, ws: Workspace) -> None:
        """build_retention_params accepts math='total' and sets measurement correctly."""
        result = ws.build_retention_params("Signup", "Login", math="total")
        measurement = result["sections"]["show"][0]["measurement"]
        assert measurement["math"] == "total"

    def test_math_average_accepted(self, ws: Workspace) -> None:
        """build_retention_params accepts math='average' and sets measurement correctly."""
        result = ws.build_retention_params("Signup", "Login", math="average")
        measurement = result["sections"]["show"][0]["measurement"]
        assert measurement["math"] == "average"


# =============================================================================
# T009: Retention unbounded_mode and retention_cumulative parameters
# =============================================================================


class TestBuildRetentionParamsUnboundedMode:
    """T009: Tests for unbounded_mode parameter in build_retention_params."""

    def test_unbounded_mode_carry_forward(self, ws: Workspace) -> None:
        """build_retention_params with unbounded_mode='carry_forward' produces retentionUnboundedMode."""
        result = ws.build_retention_params(
            "Signup",
            "Login",
            unbounded_mode="carry_forward",
        )
        behavior = result["sections"]["show"][0]["behavior"]
        assert behavior["retentionUnboundedMode"] == "carry_forward"

    def test_unbounded_mode_carry_back(self, ws: Workspace) -> None:
        """build_retention_params with unbounded_mode='carry_back' produces retentionUnboundedMode."""
        result = ws.build_retention_params(
            "Signup",
            "Login",
            unbounded_mode="carry_back",
        )
        behavior = result["sections"]["show"][0]["behavior"]
        assert behavior["retentionUnboundedMode"] == "carry_back"

    def test_unbounded_mode_none_value(self, ws: Workspace) -> None:
        """build_retention_params with unbounded_mode='none' produces retentionUnboundedMode."""
        result = ws.build_retention_params(
            "Signup",
            "Login",
            unbounded_mode="none",
        )
        behavior = result["sections"]["show"][0]["behavior"]
        assert behavior["retentionUnboundedMode"] == "none"

    def test_unbounded_mode_consecutive_forward(self, ws: Workspace) -> None:
        """build_retention_params with unbounded_mode='consecutive_forward' produces retentionUnboundedMode."""
        result = ws.build_retention_params(
            "Signup",
            "Login",
            unbounded_mode="consecutive_forward",
        )
        behavior = result["sections"]["show"][0]["behavior"]
        assert behavior["retentionUnboundedMode"] == "consecutive_forward"

    def test_no_unbounded_mode_omits_key(self, ws: Workspace) -> None:
        """build_retention_params without unbounded_mode omits retentionUnboundedMode (backward compat)."""
        result = ws.build_retention_params("Signup", "Login")
        behavior = result["sections"]["show"][0]["behavior"]
        assert "retentionUnboundedMode" not in behavior


class TestBuildRetentionParamsCumulative:
    """T009: Tests for retention_cumulative parameter in build_retention_params."""

    def test_retention_cumulative_true(self, ws: Workspace) -> None:
        """build_retention_params with retention_cumulative=True produces retentionCumulative."""
        result = ws.build_retention_params(
            "Signup",
            "Login",
            retention_cumulative=True,
        )
        measurement = result["sections"]["show"][0]["measurement"]
        assert measurement["retentionCumulative"] is True

    def test_retention_cumulative_false_omits_key(self, ws: Workspace) -> None:
        """build_retention_params with retention_cumulative=False omits retentionCumulative (backward compat)."""
        result = ws.build_retention_params("Signup", "Login")
        measurement = result["sections"]["show"][0]["measurement"]
        assert "retentionCumulative" not in measurement

    def test_retention_cumulative_explicit_false_omits_key(self, ws: Workspace) -> None:
        """build_retention_params with explicit retention_cumulative=False omits retentionCumulative."""
        result = ws.build_retention_params(
            "Signup",
            "Login",
            retention_cumulative=False,
        )
        measurement = result["sections"]["show"][0]["measurement"]
        assert "retentionCumulative" not in measurement

    def test_no_new_params_backward_compat(self, ws: Workspace) -> None:
        """build_retention_params without new params produces NO retentionUnboundedMode or retentionCumulative."""
        result = ws.build_retention_params("Signup", "Login")
        behavior = result["sections"]["show"][0]["behavior"]
        measurement = result["sections"]["show"][0]["measurement"]
        assert "retentionUnboundedMode" not in behavior
        assert "retentionCumulative" not in measurement


# =============================================================================
# T032: data_group_id on retention query engine
# =============================================================================


class TestDataGroupIdRetention:
    """Tests for data_group_id parameter on retention query engine (T032)."""

    def test_build_retention_params_with_data_group_id(self, ws: Workspace) -> None:
        """build_retention_params with data_group_id=5 includes dataGroupId: 5 in sections."""
        result = ws.build_retention_params("Signup", "Login", data_group_id=5)
        assert result["sections"]["dataGroupId"] == 5

    def test_build_retention_params_without_data_group_id(self, ws: Workspace) -> None:
        """build_retention_params without data_group_id omits dataGroupId key (backward compat)."""
        result = ws.build_retention_params("Signup", "Login")
        assert "dataGroupId" not in result["sections"]
