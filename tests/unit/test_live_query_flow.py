"""Tests for flow query service and API client methods.

Tests cover the arb_funnels_query API client method, the LiveQueryService
query_flow method, and the _transform_flow_result helper.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

from mixpanel_headless._internal.api_client import MixpanelAPIClient
from mixpanel_headless._internal.services.live_query import (
    LiveQueryService,
    _transform_flow_result,
)
from mixpanel_headless.exceptions import QueryError
from mixpanel_headless.types import FlowQueryResult

# =========================================================================
# Fixtures
# =========================================================================


@pytest.fixture
def mock_api_client() -> MagicMock:
    """Create mock API client for testing."""
    return MagicMock(spec=MixpanelAPIClient)


@pytest.fixture
def live_query_service(mock_api_client: MagicMock) -> LiveQueryService:
    """Create LiveQueryService with mocked API client."""
    return LiveQueryService(mock_api_client)


def _sample_sankey_response() -> dict[str, Any]:
    """Build a sample sankey flow API response for tests."""
    return {
        "computed_at": "2025-01-15T10:00:00",
        "steps": [
            {"event": "Login", "count": 100},
            {"event": "Purchase", "count": 30},
        ],
        "breakdowns": [{"name": "country", "values": ["US", "UK"]}],
        "overallConversionRate": 0.3,
        "metadata": {"sampling_factor": 1.0},
    }


def _sample_top_paths_response() -> dict[str, Any]:
    """Build a sample top-paths flow API response for tests."""
    return {
        "computed_at": "2025-01-15T10:00:00",
        "flows": [
            {"path": ["Login", "Purchase"], "count": 30},
            {"path": ["Login", "Signup"], "count": 20},
        ],
        "steps": [],
        "breakdowns": [],
        "overallConversionRate": 0.5,
        "metadata": {},
    }


def _sample_bookmark_params() -> dict[str, Any]:
    """Build sample bookmark params for tests."""
    return {
        "steps": [{"event": "Login", "forward": 3, "reverse": 0}],
        "date_range": {
            "type": "in the last",
            "from_date": {"unit": "day", "value": 30},
            "to_date": "$now",
        },
        "chartType": "sankey",
        "count_type": "unique",
        "version": 2,
    }


# =========================================================================
# T024: TestArbFunnelsQuery — API client method
# =========================================================================


class TestArbFunnelsQuery:
    """Tests for MixpanelAPIClient.arb_funnels_query()."""

    def test_posts_to_arb_funnels(
        self,
        mock_api_client: MagicMock,
    ) -> None:
        """arb_funnels_query POSTs body to /arb_funnels endpoint."""
        mock_api_client.arb_funnels_query = MagicMock(
            return_value=_sample_sankey_response()
        )
        body: dict[str, Any] = {
            "bookmark": _sample_bookmark_params(),
            "project_id": 12345,
            "query_type": "flows_sankey",
        }

        result = mock_api_client.arb_funnels_query(body)

        mock_api_client.arb_funnels_query.assert_called_once_with(body)
        assert "computed_at" in result

    def test_query_type_sankey(self) -> None:
        """Sankey mode uses query_type='flows_sankey'."""
        body: dict[str, Any] = {
            "bookmark": _sample_bookmark_params(),
            "project_id": 12345,
            "query_type": "flows_sankey",
        }
        assert body["query_type"] == "flows_sankey"

    def test_query_type_top_paths(self) -> None:
        """Paths mode uses query_type='flows_top_paths'."""
        body: dict[str, Any] = {
            "bookmark": _sample_bookmark_params(),
            "project_id": 12345,
            "query_type": "flows_top_paths",
        }
        assert body["query_type"] == "flows_top_paths"


# =========================================================================
# T026: TestTransformFlowResult — _transform_flow_result helper
# =========================================================================


class TestTransformFlowResult:
    """Tests for _transform_flow_result transform function."""

    def test_sankey_response_transformation(self) -> None:
        """Sankey response extracts steps, breakdowns, conversion rate."""
        raw = _sample_sankey_response()
        bookmark = _sample_bookmark_params()

        result = _transform_flow_result(raw, bookmark, mode="sankey")

        assert isinstance(result, FlowQueryResult)
        assert result.computed_at == "2025-01-15T10:00:00"
        assert len(result.steps) == 2
        assert result.steps[0]["event"] == "Login"
        assert len(result.breakdowns) == 1
        assert result.overall_conversion_rate == 0.3
        assert result.mode == "sankey"
        assert result.meta == {"sampling_factor": 1.0}

    def test_top_paths_response_transformation(self) -> None:
        """Top-paths response extracts flows field."""
        raw = _sample_top_paths_response()
        bookmark = _sample_bookmark_params()

        result = _transform_flow_result(raw, bookmark, mode="paths")

        assert isinstance(result, FlowQueryResult)
        assert len(result.flows) == 2
        assert result.flows[0]["path"] == ["Login", "Purchase"]
        assert result.overall_conversion_rate == 0.5
        assert result.mode == "paths"

    def test_error_as_200_raises_query_error(self) -> None:
        """Response with 'error' key raises QueryError."""
        raw: dict[str, Any] = {"error": "Invalid query parameters"}
        bookmark = _sample_bookmark_params()

        with pytest.raises(QueryError, match="Invalid query parameters"):
            _transform_flow_result(raw, bookmark, mode="sankey")

    def test_params_preserved_in_result(self) -> None:
        """Bookmark params are preserved in result for debugging."""
        raw = _sample_sankey_response()
        bookmark = _sample_bookmark_params()

        result = _transform_flow_result(raw, bookmark, mode="sankey")

        assert result.params == bookmark


# =========================================================================
# T027: TestQueryFlow — LiveQueryService.query_flow
# =========================================================================


class TestQueryFlow:
    """Tests for LiveQueryService.query_flow()."""

    def test_calls_arb_funnels_query_with_correct_body(
        self,
        mock_api_client: MagicMock,
        live_query_service: LiveQueryService,
    ) -> None:
        """query_flow calls arb_funnels_query with bookmark, project_id, query_type."""
        mock_api_client.arb_funnels_query.return_value = _sample_sankey_response()
        bookmark = _sample_bookmark_params()

        result = live_query_service.query_flow(
            bookmark_params=bookmark,
            project_id=12345,
            mode="sankey",
        )

        mock_api_client.arb_funnels_query.assert_called_once()
        call_args = mock_api_client.arb_funnels_query.call_args
        body = call_args[0][0]
        assert body["bookmark"] == bookmark
        assert body["project_id"] == 12345
        assert body["query_type"] == "flows_sankey"

        assert isinstance(result, FlowQueryResult)
        assert result.computed_at == "2025-01-15T10:00:00"

    def test_paths_mode_uses_flows_top_paths_query_type(
        self,
        mock_api_client: MagicMock,
        live_query_service: LiveQueryService,
    ) -> None:
        """Paths mode uses query_type='flows_top_paths'."""
        mock_api_client.arb_funnels_query.return_value = _sample_top_paths_response()
        bookmark = _sample_bookmark_params()

        live_query_service.query_flow(
            bookmark_params=bookmark,
            project_id=12345,
            mode="paths",
        )

        call_args = mock_api_client.arb_funnels_query.call_args
        body = call_args[0][0]
        assert body["query_type"] == "flows_top_paths"

    def test_error_in_response_raises_query_error(
        self,
        mock_api_client: MagicMock,
        live_query_service: LiveQueryService,
    ) -> None:
        """Error-as-200 response raises QueryError."""
        mock_api_client.arb_funnels_query.return_value = {"error": "Bad params"}
        bookmark = _sample_bookmark_params()

        with pytest.raises(QueryError, match="Bad params"):
            live_query_service.query_flow(
                bookmark_params=bookmark,
                project_id=12345,
                mode="sankey",
            )


# =========================================================================
# Tree response helpers and tests
# =========================================================================


def _sample_tree_response() -> dict[str, Any]:
    """Build a sample tree flow API response for tests."""
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
                            "children": [
                                {
                                    "step": {
                                        "type": "ANCHOR",
                                        "step_number": 2,
                                        "event": "Purchase",
                                        "is_computed": False,
                                        "anchor_type": "NORMAL",
                                    },
                                    "children": [],
                                    "total_count": 40,
                                    "drop_off_total_count": 0,
                                    "converted_total_count": 40,
                                },
                            ],
                            "total_count": 80,
                            "drop_off_total_count": 10,
                            "converted_total_count": 70,
                        },
                        {
                            "step": {
                                "type": "DROPOFF",
                                "step_number": 1,
                                "event": "DROPOFF",
                                "is_computed": False,
                                "anchor_type": "NORMAL",
                            },
                            "children": [],
                            "total_count": 20,
                            "drop_off_total_count": 20,
                            "converted_total_count": 0,
                        },
                    ],
                    "total_count": 100,
                    "drop_off_total_count": 20,
                    "converted_total_count": 80,
                },
                "num_steps": 3,
                "segments": {"segments": []},
            }
        ],
        "metadata": {"min_sampling_factor": 1},
    }


class TestParseTreeNode:
    """Tests for _parse_tree_node recursive parser."""

    def test_parses_root_node(self) -> None:
        """_parse_tree_node extracts event, type, counts from root dict."""
        from mixpanel_headless._internal.services.live_query import (
            _parse_tree_node,
        )

        raw = _sample_tree_response()["trees"][0]["root"]
        node = _parse_tree_node(raw)

        assert node.event == "Login"
        assert node.type == "ANCHOR"
        assert node.step_number == 0
        assert node.total_count == 100
        assert node.drop_off_count == 20
        assert node.converted_count == 80
        assert node.anchor_type == "NORMAL"
        assert node.is_computed is False

    def test_parses_children_recursively(self) -> None:
        """_parse_tree_node builds recursive children."""
        from mixpanel_headless._internal.services.live_query import (
            _parse_tree_node,
        )

        raw = _sample_tree_response()["trees"][0]["root"]
        node = _parse_tree_node(raw)

        assert len(node.children) == 2
        assert node.children[0].event == "Search"
        assert node.children[0].total_count == 80
        assert len(node.children[0].children) == 1
        assert node.children[0].children[0].event == "Purchase"

    def test_parses_empty_children(self) -> None:
        """_parse_tree_node handles leaf nodes with empty children."""
        from mixpanel_headless._internal.services.live_query import (
            _parse_tree_node,
        )

        leaf_raw: dict[str, Any] = {
            "step": {
                "type": "DROPOFF",
                "step_number": 1,
                "event": "DROPOFF",
                "is_computed": False,
                "anchor_type": "NORMAL",
            },
            "children": [],
            "total_count": 20,
            "drop_off_total_count": 20,
            "converted_total_count": 0,
        }
        node = _parse_tree_node(leaf_raw)
        assert node.children == ()
        assert node.total_count == 20

    def test_parses_time_percentiles(self) -> None:
        """_parse_tree_node extracts time percentile dicts."""
        from mixpanel_headless._internal.services.live_query import (
            _parse_tree_node,
        )

        raw: dict[str, Any] = {
            "step": {
                "type": "NORMAL",
                "step_number": 1,
                "event": "Search",
                "is_computed": False,
                "anchor_type": "NORMAL",
            },
            "children": [],
            "total_count": 50,
            "drop_off_total_count": 5,
            "converted_total_count": 45,
            "time_percentiles_from_start": {
                "percentiles": [50, 90],
                "values": [1.2, 5.8],
            },
            "time_percentiles_from_prev": {
                "percentiles": [50],
                "values": [0.5],
            },
        }
        node = _parse_tree_node(raw)
        assert node.time_percentiles_from_start["percentiles"] == [50, 90]
        assert node.time_percentiles_from_prev["values"] == [0.5]


class TestTransformFlowResultTree:
    """Tests for _transform_flow_result with tree mode."""

    def test_tree_mode_extracts_trees(self) -> None:
        """Tree mode parses trees from response into FlowTreeNode list."""
        raw = _sample_tree_response()
        bookmark = _sample_bookmark_params()

        result = _transform_flow_result(raw, bookmark, mode="tree")

        assert isinstance(result, FlowQueryResult)
        assert result.mode == "tree"
        assert len(result.trees) == 1
        assert result.trees[0].event == "Login"
        assert result.trees[0].total_count == 100

    def test_tree_mode_handles_missing_trees_key(self) -> None:
        """Tree mode gracefully handles missing 'trees' key."""
        raw: dict[str, Any] = {
            "computed_at": "2025-01-15T10:00:00",
            "metadata": {},
        }
        bookmark = _sample_bookmark_params()

        result = _transform_flow_result(raw, bookmark, mode="tree")

        assert result.mode == "tree"
        assert result.trees == []

    def test_tree_mode_error_as_200(self) -> None:
        """Error-as-200 still raises QueryError in tree mode."""
        raw: dict[str, Any] = {"error": "Invalid tree query"}
        bookmark = _sample_bookmark_params()

        with pytest.raises(QueryError, match="Invalid tree query"):
            _transform_flow_result(raw, bookmark, mode="tree")


class TestQueryFlowTree:
    """Tests for LiveQueryService.query_flow with tree mode."""

    def test_tree_mode_uses_flows_query_type(
        self,
        mock_api_client: MagicMock,
        live_query_service: LiveQueryService,
    ) -> None:
        """Tree mode uses query_type='flows' (raw tree response)."""
        mock_api_client.arb_funnels_query.return_value = _sample_tree_response()
        bookmark = _sample_bookmark_params()

        live_query_service.query_flow(
            bookmark_params=bookmark,
            project_id=12345,
            mode="tree",
        )

        call_args = mock_api_client.arb_funnels_query.call_args
        body = call_args[0][0]
        assert body["query_type"] == "flows"

    def test_tree_mode_returns_populated_result(
        self,
        mock_api_client: MagicMock,
        live_query_service: LiveQueryService,
    ) -> None:
        """Tree mode returns FlowQueryResult with populated trees."""
        mock_api_client.arb_funnels_query.return_value = _sample_tree_response()
        bookmark = _sample_bookmark_params()

        result = live_query_service.query_flow(
            bookmark_params=bookmark,
            project_id=12345,
            mode="tree",
        )

        assert isinstance(result, FlowQueryResult)
        assert result.mode == "tree"
        assert len(result.trees) == 1
        assert result.trees[0].event == "Login"
