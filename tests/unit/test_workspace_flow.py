"""Tests for flow query workspace methods.

Tests cover params builder, filter integration, and workspace public methods.
Follows the established TDD patterns from test_workspace_bookmarks.py.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any
from unittest.mock import MagicMock

import pytest
from pydantic import SecretStr

from mixpanel_headless import Workspace
from mixpanel_headless._internal.auth.account import ServiceAccount
from mixpanel_headless._internal.auth.session import Project, Session
from mixpanel_headless.exceptions import BookmarkValidationError
from mixpanel_headless.types import (
    Filter,
    FlowQueryResult,
    FlowStep,
    FlowTreeNode,
    GroupBy,
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

# =========================================================================
# Fixtures
# =========================================================================


@pytest.fixture
def mock_api_client() -> MagicMock:
    """Create mock API client for testing."""
    from mixpanel_headless._internal.api_client import MixpanelAPIClient

    client = MagicMock(spec=MixpanelAPIClient)
    client.close = MagicMock()
    return client


@pytest.fixture
def workspace_factory(
    mock_api_client: MagicMock,
) -> Callable[..., Workspace]:
    """Factory for creating Workspace instances with mocked dependencies."""

    def factory(**kwargs: Any) -> Workspace:
        defaults: dict[str, Any] = {
            "session": _TEST_SESSION,
            "_api_client": mock_api_client,
        }
        defaults.update(kwargs)
        return Workspace(**defaults)

    return factory


# =========================================================================
# T020: TestBuildFlowParams — _build_flow_params private method
# =========================================================================


class TestBuildFlowParams:
    """Tests for Workspace._build_flow_params() private method."""

    def test_basic_single_event(
        self,
        workspace_factory: Callable[..., Workspace],
    ) -> None:
        """Single-step flow produces flat structure with required keys."""
        ws = workspace_factory()
        try:
            params = ws._build_flow_params(
                steps=[FlowStep("Login")],
                from_date=None,
                to_date=None,
                last=30,
                conversion_window=7,
                conversion_window_unit="day",
                count_type="unique",
                cardinality=3,
                collapse_repeated=False,
                hidden_events=None,
                mode="sankey",
            )

            # Flat structure — no "sections" wrapper
            assert "sections" not in params
            assert "steps" in params
            assert "date_range" in params
            assert "chartType" in params
            assert "count_type" in params
            assert params["version"] == 2
            assert "cardinality_threshold" in params
            assert "conversion_window" in params
            assert "anchor_position" in params
        finally:
            ws.close()

    def test_date_range_relative(
        self,
        workspace_factory: Callable[..., Workspace],
    ) -> None:
        """Default last=30 produces relative date range."""
        ws = workspace_factory()
        try:
            params = ws._build_flow_params(
                steps=[FlowStep("Login")],
                from_date=None,
                to_date=None,
                last=30,
                conversion_window=7,
                conversion_window_unit="day",
                count_type="unique",
                cardinality=3,
                collapse_repeated=False,
                hidden_events=None,
                mode="sankey",
            )

            dr = params["date_range"]
            assert dr["type"] == "in the last"
            assert dr["from_date"] == {"unit": "day", "value": 30}
            assert dr["to_date"] == "$now"
        finally:
            ws.close()

    def test_date_range_absolute(
        self,
        workspace_factory: Callable[..., Workspace],
    ) -> None:
        """Absolute from_date/to_date produces between date range."""
        ws = workspace_factory()
        try:
            params = ws._build_flow_params(
                steps=[FlowStep("Login")],
                from_date="2025-01-01",
                to_date="2025-01-31",
                last=30,
                conversion_window=7,
                conversion_window_unit="day",
                count_type="unique",
                cardinality=3,
                collapse_repeated=False,
                hidden_events=None,
                mode="sankey",
            )

            dr = params["date_range"]
            assert dr["type"] == "between"
            assert dr["from_date"] == "2025-01-01"
            assert dr["to_date"] == "2025-01-31"
        finally:
            ws.close()

    def test_chart_type_sankey(
        self,
        workspace_factory: Callable[..., Workspace],
    ) -> None:
        """mode='sankey' maps to chartType='sankey' and flows_merge_type='graph'."""
        ws = workspace_factory()
        try:
            params = ws._build_flow_params(
                steps=[FlowStep("Login")],
                from_date=None,
                to_date=None,
                last=30,
                conversion_window=7,
                conversion_window_unit="day",
                count_type="unique",
                cardinality=3,
                collapse_repeated=False,
                hidden_events=None,
                mode="sankey",
            )

            assert params["chartType"] == "sankey"
            assert params["flows_merge_type"] == "graph"
        finally:
            ws.close()

    def test_chart_type_paths(
        self,
        workspace_factory: Callable[..., Workspace],
    ) -> None:
        """mode='paths' maps to chartType='top-paths' and flows_merge_type='list'."""
        ws = workspace_factory()
        try:
            params = ws._build_flow_params(
                steps=[FlowStep("Login")],
                from_date=None,
                to_date=None,
                last=30,
                conversion_window=7,
                conversion_window_unit="day",
                count_type="unique",
                cardinality=3,
                collapse_repeated=False,
                hidden_events=None,
                mode="paths",
            )

            assert params["chartType"] == "top-paths"
            assert params["flows_merge_type"] == "list"
        finally:
            ws.close()

    def test_chart_type_tree(
        self,
        workspace_factory: Callable[..., Workspace],
    ) -> None:
        """mode='tree' maps to chartType='sankey' and flows_merge_type='tree'."""
        ws = workspace_factory()
        try:
            params = ws._build_flow_params(
                steps=[FlowStep("Login")],
                from_date=None,
                to_date=None,
                last=30,
                conversion_window=7,
                conversion_window_unit="day",
                count_type="unique",
                cardinality=3,
                collapse_repeated=False,
                hidden_events=None,
                mode="tree",
            )

            assert params["chartType"] == "sankey"
            assert params["flows_merge_type"] == "tree"
        finally:
            ws.close()

    def test_step_structure(
        self,
        workspace_factory: Callable[..., Workspace],
    ) -> None:
        """Each step dict has required keys: event, step_label, forward, reverse, bool_op, property_filter_params_list."""
        ws = workspace_factory()
        try:
            params = ws._build_flow_params(
                steps=[FlowStep("Purchase", forward=2, reverse=1, label="Buy")],
                from_date=None,
                to_date=None,
                last=30,
                conversion_window=7,
                conversion_window_unit="day",
                count_type="unique",
                cardinality=3,
                collapse_repeated=False,
                hidden_events=None,
                mode="sankey",
            )

            step = params["steps"][0]
            assert step["event"] == "Purchase"
            assert step["step_label"] == "Buy"
            assert step["forward"] == 2
            assert step["reverse"] == 1
            assert step["bool_op"] == "and"
            assert step["property_filter_params_list"] == []
        finally:
            ws.close()

    def test_collapse_repeated(
        self,
        workspace_factory: Callable[..., Workspace],
    ) -> None:
        """collapse_repeated=True shows in output params."""
        ws = workspace_factory()
        try:
            params = ws._build_flow_params(
                steps=[FlowStep("Login")],
                from_date=None,
                to_date=None,
                last=30,
                conversion_window=7,
                conversion_window_unit="day",
                count_type="unique",
                cardinality=3,
                collapse_repeated=True,
                hidden_events=None,
                mode="sankey",
            )

            assert params["collapse_repeated"] is True
        finally:
            ws.close()

    def test_hidden_events(
        self,
        workspace_factory: Callable[..., Workspace],
    ) -> None:
        """hidden_events list shows in output params."""
        ws = workspace_factory()
        try:
            params = ws._build_flow_params(
                steps=[FlowStep("Login")],
                from_date=None,
                to_date=None,
                last=30,
                conversion_window=7,
                conversion_window_unit="day",
                count_type="unique",
                cardinality=3,
                collapse_repeated=False,
                hidden_events=["X"],
                mode="sankey",
            )

            assert params["hidden_events"] == ["X"]
        finally:
            ws.close()

    def test_conversion_window_custom(
        self,
        workspace_factory: Callable[..., Workspace],
    ) -> None:
        """Custom conversion_window and unit show in output."""
        ws = workspace_factory()
        try:
            params = ws._build_flow_params(
                steps=[FlowStep("Login")],
                from_date=None,
                to_date=None,
                last=30,
                conversion_window=14,
                conversion_window_unit="week",
                count_type="unique",
                cardinality=3,
                collapse_repeated=False,
                hidden_events=None,
                mode="sankey",
            )

            assert params["conversion_window"] == {"unit": "week", "value": 14}
        finally:
            ws.close()


# =========================================================================
# T021: TestBuildFlowParamsFilters — filter integration
# =========================================================================


class TestBuildFlowParamsFilters:
    """Tests for filter integration in _build_flow_params."""

    def test_filter_produces_segfilter(
        self,
        workspace_factory: Callable[..., Workspace],
    ) -> None:
        """FlowStep with filters produces correct property_filter_params_list."""
        ws = workspace_factory()
        try:
            step = FlowStep(
                "Purchase",
                forward=3,
                reverse=0,
                filters=[Filter.greater_than("amount", 50)],
            )
            params = ws._build_flow_params(
                steps=[step],
                from_date=None,
                to_date=None,
                last=30,
                conversion_window=7,
                conversion_window_unit="day",
                count_type="unique",
                cardinality=3,
                collapse_repeated=False,
                hidden_events=None,
                mode="sankey",
            )

            pf = params["steps"][0]["property_filter_params_list"]
            assert len(pf) == 1
            assert pf[0]["property"]["name"] == "amount"
            assert "filter" in pf[0]
        finally:
            ws.close()

    def test_filters_combinator_any_maps_to_or(
        self,
        workspace_factory: Callable[..., Workspace],
    ) -> None:
        """filters_combinator='any' maps to bool_op='or'."""
        ws = workspace_factory()
        try:
            step = FlowStep(
                "Purchase",
                forward=3,
                reverse=0,
                filters=[
                    Filter.equals("country", "US"),
                    Filter.equals("country", "UK"),
                ],
                filters_combinator="any",
            )
            params = ws._build_flow_params(
                steps=[step],
                from_date=None,
                to_date=None,
                last=30,
                conversion_window=7,
                conversion_window_unit="day",
                count_type="unique",
                cardinality=3,
                collapse_repeated=False,
                hidden_events=None,
                mode="sankey",
            )

            assert params["steps"][0]["bool_op"] == "or"
        finally:
            ws.close()

    def test_filters_combinator_all_maps_to_and(
        self,
        workspace_factory: Callable[..., Workspace],
    ) -> None:
        """filters_combinator='all' (default) maps to bool_op='and'."""
        ws = workspace_factory()
        try:
            step = FlowStep("Purchase", forward=3, reverse=0)
            params = ws._build_flow_params(
                steps=[step],
                from_date=None,
                to_date=None,
                last=30,
                conversion_window=7,
                conversion_window_unit="day",
                count_type="unique",
                cardinality=3,
                collapse_repeated=False,
                hidden_events=None,
                mode="sankey",
            )

            assert params["steps"][0]["bool_op"] == "and"
        finally:
            ws.close()

    def test_no_filters_empty_list(
        self,
        workspace_factory: Callable[..., Workspace],
    ) -> None:
        """FlowStep without filters has empty property_filter_params_list."""
        ws = workspace_factory()
        try:
            step = FlowStep("Purchase", forward=3, reverse=0)
            params = ws._build_flow_params(
                steps=[step],
                from_date=None,
                to_date=None,
                last=30,
                conversion_window=7,
                conversion_window_unit="day",
                count_type="unique",
                cardinality=3,
                collapse_repeated=False,
                hidden_events=None,
                mode="sankey",
            )

            assert params["steps"][0]["property_filter_params_list"] == []
        finally:
            ws.close()


# =========================================================================
# T028-T029: TestWorkspaceFlowPublicMethods — workspace public methods
# =========================================================================


class TestWorkspaceFlowPublicMethods:
    """Tests for Workspace.query_flow() and Workspace.build_flow_params()."""

    def test_query_flow_delegates_to_service(
        self,
        workspace_factory: Callable[..., Workspace],
    ) -> None:
        """query_flow() delegates to LiveQueryService.query_flow()."""
        ws = workspace_factory()
        try:
            mock_live_query = MagicMock()
            mock_live_query.query_flow.return_value = FlowQueryResult(
                computed_at="2025-01-15T10:00:00",
                steps=[{"event": "Login", "count": 100}],
                flows=[],
                overall_conversion_rate=0.5,
                params={},
                meta={},
                mode="sankey",
            )
            ws._live_query = mock_live_query

            result = ws.query_flow("Login")

            assert isinstance(result, FlowQueryResult)
            assert result.computed_at == "2025-01-15T10:00:00"
            mock_live_query.query_flow.assert_called_once()

            call_kwargs = mock_live_query.query_flow.call_args
            assert call_kwargs.kwargs["project_id"] == 12345
            assert call_kwargs.kwargs["mode"] == "sankey"
            assert "bookmark_params" in call_kwargs.kwargs
        finally:
            ws.close()

    def test_build_flow_params_returns_dict(
        self,
        workspace_factory: Callable[..., Workspace],
    ) -> None:
        """build_flow_params() returns a dict without making API calls."""
        ws = workspace_factory()
        try:
            params = ws.build_flow_params("Login")

            assert isinstance(params, dict)
            assert "steps" in params
            assert "date_range" in params
            assert "chartType" in params
            assert params["version"] == 2
        finally:
            ws.close()

    # test_query_flow_raises_on_no_credentials removed in B1 (Fix 10):
    # Workspace.__init__ now always populates _credentials via the v3
    # session shim, so the "no credentials" branch is unreachable.

    def test_query_flow_with_flow_step(
        self,
        workspace_factory: Callable[..., Workspace],
    ) -> None:
        """query_flow() accepts FlowStep objects directly."""
        ws = workspace_factory()
        try:
            mock_live_query = MagicMock()
            mock_live_query.query_flow.return_value = FlowQueryResult(
                computed_at="2025-01-15T10:00:00",
                steps=[],
                flows=[],
                overall_conversion_rate=0.0,
                params={},
                meta={},
                mode="sankey",
            )
            ws._live_query = mock_live_query

            result = ws.query_flow(FlowStep("Login", forward=5, reverse=2))

            assert isinstance(result, FlowQueryResult)
            mock_live_query.query_flow.assert_called_once()
        finally:
            ws.close()

    def test_query_flow_with_list_of_events(
        self,
        workspace_factory: Callable[..., Workspace],
    ) -> None:
        """query_flow() accepts a list of event name strings."""
        ws = workspace_factory()
        try:
            mock_live_query = MagicMock()
            mock_live_query.query_flow.return_value = FlowQueryResult(
                computed_at="2025-01-15T10:00:00",
                steps=[],
                flows=[],
                overall_conversion_rate=0.0,
                params={},
                meta={},
                mode="paths",
            )
            ws._live_query = mock_live_query

            result = ws.query_flow(["Login", "Purchase"], mode="paths")

            assert isinstance(result, FlowQueryResult)
            call_kwargs = mock_live_query.query_flow.call_args
            assert call_kwargs.kwargs["mode"] == "paths"
        finally:
            ws.close()


# =========================================================================
# T040-T042: TestMultiStepNormalization — multi-step input normalization
# =========================================================================


class TestMultiStepNormalization:
    """Tests for _resolve_and_build_flow_params multi-step normalization.

    Verifies that build_flow_params correctly normalizes various
    ``event`` argument forms (strings, FlowStep objects, mixed lists)
    into a list of fully-resolved steps with proper defaults applied.
    """

    def test_list_of_strings(
        self,
        workspace_factory: Callable[..., Workspace],
    ) -> None:
        """List of strings produces N steps with correct defaults applied."""
        ws = workspace_factory()
        try:
            params = ws.build_flow_params(["A", "B"])

            assert len(params["steps"]) == 2
            assert params["steps"][0]["event"] == "A"
            assert params["steps"][1]["event"] == "B"
            # Top-level defaults: forward=3, reverse=0
            assert params["steps"][0]["forward"] == 3
            assert params["steps"][0]["reverse"] == 0
            assert params["steps"][1]["forward"] == 3
            assert params["steps"][1]["reverse"] == 0
        finally:
            ws.close()

    def test_list_of_flow_steps(
        self,
        workspace_factory: Callable[..., Workspace],
    ) -> None:
        """List of FlowStep objects preserves per-step forward/reverse."""
        ws = workspace_factory()
        try:
            params = ws.build_flow_params(
                [FlowStep("A", forward=3), FlowStep("B", reverse=2)]
            )

            assert len(params["steps"]) == 2
            assert params["steps"][0]["event"] == "A"
            assert params["steps"][0]["forward"] == 3
            assert params["steps"][1]["event"] == "B"
            assert params["steps"][1]["reverse"] == 2
        finally:
            ws.close()

    def test_mixed_list(
        self,
        workspace_factory: Callable[..., Workspace],
    ) -> None:
        """Mixed list of strings and FlowStep objects works correctly."""
        ws = workspace_factory()
        try:
            params = ws.build_flow_params(["A", FlowStep("B", forward=1)])

            assert len(params["steps"]) == 2
            assert params["steps"][0]["event"] == "A"
            # String "A" gets top-level defaults (forward=3, reverse=0)
            assert params["steps"][0]["forward"] == 3
            assert params["steps"][0]["reverse"] == 0
            # FlowStep("B", forward=1) keeps forward=1
            assert params["steps"][1]["event"] == "B"
            assert params["steps"][1]["forward"] == 1
        finally:
            ws.close()

    def test_single_string_wrapped(
        self,
        workspace_factory: Callable[..., Workspace],
    ) -> None:
        """Single string 'Purchase' produces a single-element step list."""
        ws = workspace_factory()
        try:
            params = ws.build_flow_params("Purchase")

            assert len(params["steps"]) == 1
            assert params["steps"][0]["event"] == "Purchase"
        finally:
            ws.close()

    def test_single_flow_step_wrapped(
        self,
        workspace_factory: Callable[..., Workspace],
    ) -> None:
        """Single FlowStep produces a single-element step list."""
        ws = workspace_factory()
        try:
            params = ws.build_flow_params(FlowStep("A", forward=3))

            assert len(params["steps"]) == 1
            assert params["steps"][0]["event"] == "A"
            assert params["steps"][0]["forward"] == 3
        finally:
            ws.close()

    def test_string_steps_get_top_level_defaults(
        self,
        workspace_factory: Callable[..., Workspace],
    ) -> None:
        """String steps inherit top-level forward/reverse defaults."""
        ws = workspace_factory()
        try:
            params = ws.build_flow_params(["X", "Y"], forward=5, reverse=2)

            # Both string steps should get forward=5, reverse=2
            for step in params["steps"]:
                assert step["forward"] == 5
                assert step["reverse"] == 2
        finally:
            ws.close()

    def test_flow_step_explicit_overrides_defaults(
        self,
        workspace_factory: Callable[..., Workspace],
    ) -> None:
        """FlowStep with explicit forward/reverse keeps them, ignoring top-level."""
        ws = workspace_factory()
        try:
            params = ws.build_flow_params(
                FlowStep("A", forward=5, reverse=4),
                forward=3,
                reverse=0,
            )

            assert params["steps"][0]["forward"] == 5
            assert params["steps"][0]["reverse"] == 4
        finally:
            ws.close()

    def test_flow_step_none_inherits_defaults(
        self,
        workspace_factory: Callable[..., Workspace],
    ) -> None:
        """FlowStep with forward=None gets top-level default applied."""
        ws = workspace_factory()
        try:
            params = ws.build_flow_params(
                FlowStep("A"),  # forward=None, reverse=None
                forward=5,
                reverse=2,
            )

            assert params["steps"][0]["forward"] == 5
            assert params["steps"][0]["reverse"] == 2
        finally:
            ws.close()


# =========================================================================
# T042: TestMultiStepAnchorPosition — anchor_position in built params
# =========================================================================


class TestMultiStepAnchorPosition:
    """Tests for anchor_position in built flow params."""

    def test_anchor_position_default(
        self,
        workspace_factory: Callable[..., Workspace],
    ) -> None:
        """anchor_position is set to 1 in built params."""
        ws = workspace_factory()
        try:
            params = ws.build_flow_params("Login")

            assert params["anchor_position"] == 1
        finally:
            ws.close()


# =========================================================================
# T043: TestPerStepDirectionValidation — FL5 respects per-step overrides
# =========================================================================


class TestPerStepDirectionValidation:
    """Tests that FL5 validation uses effective per-step direction values."""

    def test_per_step_direction_overrides_bypass_fl5(
        self,
        workspace_factory: Callable[..., Workspace],
    ) -> None:
        """Per-step forward override is not rejected when top-level is 0."""
        ws = workspace_factory()
        try:
            params = ws.build_flow_params(
                FlowStep("Login", forward=3),
                forward=0,
                reverse=0,
            )

            assert params["steps"][0]["forward"] == 3
            assert params["steps"][0]["reverse"] == 0
        finally:
            ws.close()

    def test_all_zero_direction_still_rejected(
        self,
        workspace_factory: Callable[..., Workspace],
    ) -> None:
        """FL5 still rejects when no step has a non-zero direction."""
        ws = workspace_factory()
        try:
            with pytest.raises(
                BookmarkValidationError, match="forward or reverse must be > 0"
            ):
                ws.build_flow_params(
                    FlowStep("Login"),  # forward=None, reverse=None → 0, 0
                    forward=0,
                    reverse=0,
                )
        finally:
            ws.close()

    def test_mixed_step_directions_pass(
        self,
        workspace_factory: Callable[..., Workspace],
    ) -> None:
        """Mixed per-step overrides pass when at least one direction > 0."""
        ws = workspace_factory()
        try:
            params = ws.build_flow_params(
                [FlowStep("A", forward=3), FlowStep("B", reverse=2)],
                forward=0,
                reverse=0,
            )

            assert params["steps"][0]["forward"] == 3
            assert params["steps"][0]["reverse"] == 0
            assert params["steps"][1]["forward"] == 0
            assert params["steps"][1]["reverse"] == 2
        finally:
            ws.close()


# =========================================================================
# T044: TestFlowStepDatetimeFilters — segfilter datetime operator mapping
# =========================================================================


class TestFlowStepDatetimeFilters:
    """Tests that datetime filters produce correct segfilter operators."""

    def test_flow_step_datetime_before_filter(
        self,
        workspace_factory: Callable[..., Workspace],
    ) -> None:
        """Filter.before() produces segfilter operator '>' (not '<')."""
        ws = workspace_factory()
        try:
            params = ws.build_flow_params(
                FlowStep(
                    "Login",
                    filters=[Filter.before("$time", "2026-01-15")],
                ),
            )

            segfilter = params["steps"][0]["property_filter_params_list"][0]
            assert segfilter["filter"]["operator"] == ">"
            assert segfilter["filter"]["operand"] == "01/15/2026"
        finally:
            ws.close()

    def test_flow_step_relative_date_filter(
        self,
        workspace_factory: Callable[..., Workspace],
    ) -> None:
        """Filter.in_the_last() produces segfilter with operator, operand, and unit."""
        ws = workspace_factory()
        try:
            params = ws.build_flow_params(
                FlowStep(
                    "Login",
                    filters=[Filter.in_the_last("$time", 7, "day")],
                ),
            )

            segfilter = params["steps"][0]["property_filter_params_list"][0]
            assert segfilter["filter"]["operator"] == ">"
            assert segfilter["filter"]["operand"] == 7
            assert segfilter["filter"]["unit"] == "days"
        finally:
            ws.close()


# =========================================================================
# T053: End-to-end tree mode integration test
# =========================================================================


def _sample_tree_api_response() -> dict[str, Any]:
    """Build a sample tree flow API response for integration tests."""
    return {
        "computed_at": "2025-01-15T10:00:00",
        "trees": [
            {
                "root": {
                    "step": {
                        "type": "ANCHOR",
                        "step_number": 0,
                        "event": "Login",
                        "is_computed": False,
                        "anchor_type": "NORMAL",
                    },
                    "children": [
                        {
                            "step": {
                                "type": "NORMAL",
                                "step_number": 1,
                                "event": "Search",
                                "is_computed": False,
                                "anchor_type": "NORMAL",
                            },
                            "children": [],
                            "total_count": 80,
                            "drop_off_total_count": 10,
                            "converted_total_count": 70,
                        },
                    ],
                    "total_count": 100,
                    "drop_off_total_count": 20,
                    "converted_total_count": 80,
                },
                "num_steps": 2,
                "segments": {"segments": []},
            }
        ],
        "metadata": {"min_sampling_factor": 1},
    }


class TestQueryFlowTreeIntegration:
    """End-to-end integration test for tree mode flow query."""

    def test_query_flow_tree_round_trip(
        self,
        mock_api_client: MagicMock,
        workspace_factory: Callable[..., Workspace],
    ) -> None:
        """Full round-trip: query_flow(mode='tree') returns structured result."""
        mock_api_client.arb_funnels_query.return_value = _sample_tree_api_response()
        ws = workspace_factory()
        try:
            result = ws.query_flow("Login", mode="tree")

            assert isinstance(result, FlowQueryResult)
            assert result.mode == "tree"
            assert len(result.trees) == 1

            root = result.trees[0]
            assert isinstance(root, FlowTreeNode)
            assert root.event == "Login"
            assert root.total_count == 100
            assert root.drop_off_count == 20
            assert root.converted_count == 80

            assert len(root.children) == 1
            assert root.children[0].event == "Search"
            assert root.children[0].total_count == 80

            # DataFrame works
            df = result.df
            assert len(df) == root.node_count
            assert "path" in df.columns
            assert "Login > Search" in df["path"].tolist()

            # to_dict is JSON-serializable
            d = result.to_dict()
            assert len(d["trees"]) == 1
            assert d["trees"][0]["event"] == "Login"

            # anytree view works
            at_roots = result.anytree
            assert len(at_roots) == 1
            assert at_roots[0].event == "Login"
            assert len(at_roots[0].children) == 1
        finally:
            ws.close()


# =========================================================================
# T032: data_group_id on flow query engine
# =========================================================================


class TestDataGroupIdFlow:
    """Tests for data_group_id parameter on flow query engine (T032)."""

    def test_build_flow_params_with_data_group_id(
        self,
        workspace_factory: Callable[..., Workspace],
    ) -> None:
        """build_flow_params with data_group_id=5 includes data_group_id: 5 (snake_case for flows)."""
        ws = workspace_factory()
        result = ws.build_flow_params("Login", data_group_id=5)
        assert result["data_group_id"] == 5

    def test_build_flow_params_without_data_group_id(
        self,
        workspace_factory: Callable[..., Workspace],
    ) -> None:
        """build_flow_params without data_group_id omits the key entirely."""
        ws = workspace_factory()
        result = ws.build_flow_params("Login")
        assert "data_group_id" not in result


# =========================================================================
# T038: Advanced Flow Features — session_event, segments, exclusions, where
# =========================================================================


class TestFlowSessionEvent:
    """Tests for session_event in built flow params (T038)."""

    def test_session_event_in_step_output(
        self,
        workspace_factory: Callable[..., Workspace],
    ) -> None:
        """build_flow_params with session_event='start' emits session_event in step dict."""
        ws = workspace_factory()
        try:
            params = ws.build_flow_params(
                FlowStep(event="$session_start", session_event="start"),
            )
            step = params["steps"][0]
            assert step["session_event"] == "start"
        finally:
            ws.close()

    def test_session_event_end_in_step_output(
        self,
        workspace_factory: Callable[..., Workspace],
    ) -> None:
        """build_flow_params with session_event='end' emits session_event in step dict."""
        ws = workspace_factory()
        try:
            params = ws.build_flow_params(
                FlowStep(event="$session_end", session_event="end"),
            )
            step = params["steps"][0]
            assert step["session_event"] == "end"
        finally:
            ws.close()

    def test_no_session_event_omitted_from_step(
        self,
        workspace_factory: Callable[..., Workspace],
    ) -> None:
        """Regular FlowStep does not include session_event key in step dict."""
        ws = workspace_factory()
        try:
            params = ws.build_flow_params("Login")
            step = params["steps"][0]
            assert "session_event" not in step
        finally:
            ws.close()


class TestFlowSegments:
    """Tests for segments parameter on flow queries (T038)."""

    def test_segments_single_groupby(
        self,
        workspace_factory: Callable[..., Workspace],
    ) -> None:
        """build_flow_params with segments=GroupBy('country') produces segments in output."""
        ws = workspace_factory()
        try:
            params = ws.build_flow_params(
                "Login",
                segments=GroupBy("country"),
            )
            assert "segments" in params
            assert isinstance(params["segments"], list)
            assert len(params["segments"]) == 1
            assert params["segments"][0]["value"] == "country"
        finally:
            ws.close()

    def test_segments_string_shorthand(
        self,
        workspace_factory: Callable[..., Workspace],
    ) -> None:
        """build_flow_params with segments='country' produces segments in output."""
        ws = workspace_factory()
        try:
            params = ws.build_flow_params(
                "Login",
                segments="country",
            )
            assert "segments" in params
            assert len(params["segments"]) == 1
        finally:
            ws.close()

    def test_segments_list_of_groupby(
        self,
        workspace_factory: Callable[..., Workspace],
    ) -> None:
        """build_flow_params with list of GroupBy produces multiple segments."""
        ws = workspace_factory()
        try:
            params = ws.build_flow_params(
                "Login",
                segments=[GroupBy("country"), GroupBy("platform")],
            )
            assert len(params["segments"]) == 2
        finally:
            ws.close()

    def test_segments_none_not_in_output(
        self,
        workspace_factory: Callable[..., Workspace],
    ) -> None:
        """build_flow_params without segments does not include segments key."""
        ws = workspace_factory()
        try:
            params = ws.build_flow_params("Login")
            assert "segments" not in params
        finally:
            ws.close()


class TestFlowExclusions:
    """Tests for exclusions parameter on flow queries (T038)."""

    def test_exclusions_single_event(
        self,
        workspace_factory: Callable[..., Workspace],
    ) -> None:
        """build_flow_params with exclusions=['Error'] produces exclusions list."""
        ws = workspace_factory()
        try:
            params = ws.build_flow_params(
                "Login",
                exclusions=["Error Event"],
            )
            assert params["exclusions"] == ["Error Event"]
        finally:
            ws.close()

    def test_exclusions_multiple_events(
        self,
        workspace_factory: Callable[..., Workspace],
    ) -> None:
        """build_flow_params with multiple exclusions produces them all."""
        ws = workspace_factory()
        try:
            params = ws.build_flow_params(
                "Login",
                exclusions=["Error", "Debug", "Test"],
            )
            assert params["exclusions"] == ["Error", "Debug", "Test"]
        finally:
            ws.close()

    def test_exclusions_none_produces_empty_list(
        self,
        workspace_factory: Callable[..., Workspace],
    ) -> None:
        """build_flow_params without exclusions produces empty exclusions list (default)."""
        ws = workspace_factory()
        try:
            params = ws.build_flow_params("Login")
            assert params["exclusions"] == []
        finally:
            ws.close()


class TestFlowPropertyFilters:
    """Tests for property filters (filter_by_event) on flow queries (T038)."""

    def test_property_filter_produces_filter_by_event(
        self,
        workspace_factory: Callable[..., Workspace],
    ) -> None:
        """build_flow_params with where=Filter.equals produces filter_by_event."""
        ws = workspace_factory()
        try:
            params = ws.build_flow_params(
                "Login",
                where=Filter.equals("country", "US"),
            )
            assert "filter_by_event" in params
            fbe = params["filter_by_event"]
            assert fbe["operator"] == "and"
            assert len(fbe["children"]) == 1
            child = fbe["children"][0]
            assert child["filterOperator"] == "equals"
            assert child["propertyName"] == "country"
            assert child["filterValue"] == ["US"]
        finally:
            ws.close()

    def test_multiple_property_filters(
        self,
        workspace_factory: Callable[..., Workspace],
    ) -> None:
        """build_flow_params with list of property filters produces children array."""
        ws = workspace_factory()
        try:
            params = ws.build_flow_params(
                "Login",
                where=[
                    Filter.equals("country", "US"),
                    Filter.greater_than("age", 18),
                ],
            )
            fbe = params["filter_by_event"]
            assert len(fbe["children"]) == 2
        finally:
            ws.close()

    def test_cohort_filter_still_produces_filter_by_cohort(
        self,
        workspace_factory: Callable[..., Workspace],
    ) -> None:
        """build_flow_params with cohort filter still produces filter_by_cohort."""
        ws = workspace_factory()
        try:
            params = ws.build_flow_params(
                "Login",
                where=Filter.in_cohort(123, "Power Users"),
            )
            assert "filter_by_cohort" in params
            assert "filter_by_event" not in params
        finally:
            ws.close()

    def test_no_where_no_filter_keys(
        self,
        workspace_factory: Callable[..., Workspace],
    ) -> None:
        """build_flow_params without where has no filter_by_event or filter_by_cohort."""
        ws = workspace_factory()
        try:
            params = ws.build_flow_params("Login")
            assert "filter_by_event" not in params
            assert "filter_by_cohort" not in params
        finally:
            ws.close()
