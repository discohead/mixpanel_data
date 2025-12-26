"""Tests for LiveQueryService bookmark methods.

Phase 015: Bookmarks API - Tests for query_flows() and related methods.
"""

from __future__ import annotations

from unittest.mock import MagicMock

from mixpanel_data._internal.services.live_query import LiveQueryService
from mixpanel_data.types import FlowsResult


class TestQueryFlows:
    """Tests for LiveQueryService.query_flows()."""

    def test_query_flows_returns_flows_result(self) -> None:
        """query_flows() should return FlowsResult."""
        mock_api_client = MagicMock()
        mock_api_client.query_flows.return_value = {
            "steps": [{"step": 1, "event": "Page View", "count": 1000}],
            "breakdowns": [{"path": "A -> B", "count": 500}],
            "overallConversionRate": 0.5,
            "computed_at": "2024-01-15T10:00:00",
        }

        service = LiveQueryService(mock_api_client)
        result = service.query_flows(bookmark_id=12345)

        assert isinstance(result, FlowsResult)
        assert result.bookmark_id == 12345

    def test_query_flows_parses_steps(self) -> None:
        """query_flows() should parse steps from response."""
        mock_api_client = MagicMock()
        mock_api_client.query_flows.return_value = {
            "steps": [
                {"step": 1, "event": "Page View", "count": 1000},
                {"step": 2, "event": "Add to Cart", "count": 500},
                {"step": 3, "event": "Purchase", "count": 250},
            ],
            "breakdowns": [],
            "overallConversionRate": 0.25,
            "computed_at": "2024-01-15T10:00:00",
        }

        service = LiveQueryService(mock_api_client)
        result = service.query_flows(bookmark_id=12345)

        assert len(result.steps) == 3
        assert result.steps[0]["event"] == "Page View"
        assert result.steps[2]["count"] == 250

    def test_query_flows_parses_breakdowns(self) -> None:
        """query_flows() should parse breakdowns from response."""
        mock_api_client = MagicMock()
        mock_api_client.query_flows.return_value = {
            "steps": [],
            "breakdowns": [
                {"path": "Page View -> Add to Cart", "count": 500},
                {"path": "Add to Cart -> Purchase", "count": 250},
            ],
            "overallConversionRate": 0.5,
            "computed_at": "2024-01-15T10:00:00",
        }

        service = LiveQueryService(mock_api_client)
        result = service.query_flows(bookmark_id=12345)

        assert len(result.breakdowns) == 2
        assert result.breakdowns[0]["path"] == "Page View -> Add to Cart"

    def test_query_flows_parses_conversion_rate(self) -> None:
        """query_flows() should parse overall conversion rate."""
        mock_api_client = MagicMock()
        mock_api_client.query_flows.return_value = {
            "steps": [],
            "breakdowns": [],
            "overallConversionRate": 0.75,
            "computed_at": "2024-01-15T10:00:00",
        }

        service = LiveQueryService(mock_api_client)
        result = service.query_flows(bookmark_id=12345)

        assert result.overall_conversion_rate == 0.75

    def test_query_flows_parses_computed_at(self) -> None:
        """query_flows() should parse computed_at timestamp."""
        mock_api_client = MagicMock()
        mock_api_client.query_flows.return_value = {
            "steps": [],
            "breakdowns": [],
            "overallConversionRate": 0.0,
            "computed_at": "2024-01-15T10:30:45",
        }

        service = LiveQueryService(mock_api_client)
        result = service.query_flows(bookmark_id=12345)

        assert result.computed_at == "2024-01-15T10:30:45"

    def test_query_flows_parses_metadata(self) -> None:
        """query_flows() should parse optional metadata."""
        mock_api_client = MagicMock()
        mock_api_client.query_flows.return_value = {
            "steps": [],
            "breakdowns": [],
            "overallConversionRate": 0.0,
            "computed_at": "2024-01-15T10:00:00",
            "metadata": {"version": "2.0", "custom": "value"},
        }

        service = LiveQueryService(mock_api_client)
        result = service.query_flows(bookmark_id=12345)

        assert result.metadata == {"version": "2.0", "custom": "value"}

    def test_query_flows_empty_metadata_default(self) -> None:
        """query_flows() should default to empty metadata when not present."""
        mock_api_client = MagicMock()
        mock_api_client.query_flows.return_value = {
            "steps": [],
            "breakdowns": [],
            "overallConversionRate": 0.0,
            "computed_at": "2024-01-15T10:00:00",
        }

        service = LiveQueryService(mock_api_client)
        result = service.query_flows(bookmark_id=12345)

        assert result.metadata == {}

    def test_query_flows_calls_api_client(self) -> None:
        """query_flows() should call api_client.query_flows with bookmark_id."""
        mock_api_client = MagicMock()
        mock_api_client.query_flows.return_value = {
            "steps": [],
            "breakdowns": [],
            "overallConversionRate": 0.0,
            "computed_at": "2024-01-15T10:00:00",
        }

        service = LiveQueryService(mock_api_client)
        service.query_flows(bookmark_id=12345)

        mock_api_client.query_flows.assert_called_once_with(bookmark_id=12345)
