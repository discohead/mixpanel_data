"""Tests for LiveQueryService bookmark methods.

Phase 015: Bookmarks API - Tests for query_flows() and related methods.
Phase 016: Smart routing for query_saved_report with bookmark_type parameter.
"""

from __future__ import annotations

from unittest.mock import MagicMock

from mixpanel_data._internal.services.live_query import LiveQueryService
from mixpanel_data.types import FlowsResult, SavedReportResult


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


class TestQuerySavedReportNormalization:
    """Tests for LiveQueryService.query_saved_report() response normalization."""

    def test_insights_normalization_preserves_headers_and_series(self) -> None:
        """Insights responses should preserve headers and series from API."""
        mock_api_client = MagicMock()
        mock_api_client.query_saved_report.return_value = {
            "headers": ["$metric"],
            "computed_at": "2024-01-15T10:00:00",
            "date_range": {"from_date": "2024-01-01", "to_date": "2024-01-15"},
            "series": {"Event A": {"2024-01-01": 100, "2024-01-02": 150}},
        }

        service = LiveQueryService(mock_api_client)
        result = service.query_saved_report(bookmark_id=12345, bookmark_type="insights")

        assert isinstance(result, SavedReportResult)
        assert result.headers == ["$metric"]
        assert result.series == {"Event A": {"2024-01-01": 100, "2024-01-02": 150}}

    def test_funnels_normalization_adds_funnel_header(self) -> None:
        """Funnels responses should normalize to SavedReportResult with $funnel header."""
        mock_api_client = MagicMock()
        mock_api_client.query_saved_report.return_value = {
            "computed_at": "2024-01-15T10:00:00",
            "data": {"2024-01-15": {"steps": [{"count": 100}]}},
            "meta": {},
        }

        service = LiveQueryService(mock_api_client)
        result = service.query_saved_report(bookmark_id=12345, bookmark_type="funnels")

        assert isinstance(result, SavedReportResult)
        assert result.headers == ["$funnel"]
        assert result.report_type == "funnel"

    def test_funnels_normalization_extracts_dates_from_data_keys(self) -> None:
        """Funnels responses should extract from_date/to_date from data keys."""
        mock_api_client = MagicMock()
        mock_api_client.query_saved_report.return_value = {
            "computed_at": "2024-01-15T10:00:00",
            "data": {
                "2024-01-10": {"steps": []},
                "2024-01-11": {"steps": []},
                "2024-01-15": {"steps": []},
            },
            "meta": {},
        }

        service = LiveQueryService(mock_api_client)
        result = service.query_saved_report(bookmark_id=12345, bookmark_type="funnels")

        assert result.from_date == "2024-01-10"
        assert result.to_date == "2024-01-15"

    def test_funnels_normalization_stores_data_in_series(self) -> None:
        """Funnels responses should store data in series field."""
        mock_api_client = MagicMock()
        funnel_data = {"2024-01-15": {"steps": [{"count": 100}]}}
        mock_api_client.query_saved_report.return_value = {
            "computed_at": "2024-01-15T10:00:00",
            "data": funnel_data,
            "meta": {},
        }

        service = LiveQueryService(mock_api_client)
        result = service.query_saved_report(bookmark_id=12345, bookmark_type="funnels")

        assert result.series == funnel_data

    def test_retention_normalization_adds_retention_header(self) -> None:
        """Retention responses should normalize to SavedReportResult with $retention header."""
        mock_api_client = MagicMock()
        mock_api_client.query_saved_report.return_value = {
            "2024-01-01": {
                "first": 100,
                "counts": [100, 80, 60],
                "rates": [1.0, 0.8, 0.6],
            },
            "2024-01-02": {"first": 120, "counts": [120, 90], "rates": [1.0, 0.75]},
        }

        service = LiveQueryService(mock_api_client)
        result = service.query_saved_report(
            bookmark_id=12345, bookmark_type="retention"
        )

        assert isinstance(result, SavedReportResult)
        assert result.headers == ["$retention"]
        assert result.report_type == "retention"

    def test_retention_normalization_uses_raw_as_series(self) -> None:
        """Retention responses should use entire raw response as series."""
        mock_api_client = MagicMock()
        retention_data = {
            "2024-01-01": {"first": 100, "counts": [100, 80], "rates": [1.0, 0.8]},
        }
        mock_api_client.query_saved_report.return_value = retention_data

        service = LiveQueryService(mock_api_client)
        result = service.query_saved_report(
            bookmark_id=12345, bookmark_type="retention"
        )

        assert result.series == retention_data

    def test_retention_normalization_extracts_dates_from_keys(self) -> None:
        """Retention responses should extract from_date/to_date from data keys."""
        mock_api_client = MagicMock()
        mock_api_client.query_saved_report.return_value = {
            "2024-01-05": {"first": 100, "counts": [100], "rates": [1.0]},
            "2024-01-01": {"first": 100, "counts": [100], "rates": [1.0]},
            "2024-01-10": {"first": 100, "counts": [100], "rates": [1.0]},
        }

        service = LiveQueryService(mock_api_client)
        result = service.query_saved_report(
            bookmark_id=12345, bookmark_type="retention"
        )

        assert result.from_date == "2024-01-01"
        assert result.to_date == "2024-01-10"

    def test_flows_normalization_adds_flows_header(self) -> None:
        """Flows responses should normalize to SavedReportResult with $flows header."""
        mock_api_client = MagicMock()
        mock_api_client.query_saved_report.return_value = {
            "computed_at": "2024-01-15T10:00:00",
            "steps": [{"step": 1, "event": "Page View"}],
            "breakdowns": [{"path": "A -> B"}],
            "overallConversionRate": 0.5,
        }

        service = LiveQueryService(mock_api_client)
        result = service.query_saved_report(bookmark_id=12345, bookmark_type="flows")

        assert isinstance(result, SavedReportResult)
        assert result.headers == ["$flows"]

    def test_flows_normalization_structures_series_correctly(self) -> None:
        """Flows responses should structure series with steps, breakdowns, conversionRate."""
        mock_api_client = MagicMock()
        mock_api_client.query_saved_report.return_value = {
            "computed_at": "2024-01-15T10:00:00",
            "steps": [{"step": 1, "event": "Page View"}],
            "breakdowns": [{"path": "A -> B", "count": 100}],
            "overallConversionRate": 0.75,
        }

        service = LiveQueryService(mock_api_client)
        result = service.query_saved_report(bookmark_id=12345, bookmark_type="flows")

        assert "steps" in result.series
        assert "breakdowns" in result.series
        assert "overallConversionRate" in result.series
        assert result.series["overallConversionRate"] == 0.75

    def test_service_passes_bookmark_type_to_api_client(self) -> None:
        """LiveQueryService should pass bookmark_type to API client."""
        mock_api_client = MagicMock()
        mock_api_client.query_saved_report.return_value = {
            "headers": ["$metric"],
            "computed_at": "",
            "date_range": {"from_date": "", "to_date": ""},
            "series": {},
        }

        service = LiveQueryService(mock_api_client)
        service.query_saved_report(bookmark_id=12345, bookmark_type="insights")

        mock_api_client.query_saved_report.assert_called_once_with(
            bookmark_id=12345,
            bookmark_type="insights",
            from_date=None,
            to_date=None,
        )

    def test_service_passes_dates_for_funnels(self) -> None:
        """LiveQueryService should pass from_date/to_date for funnels."""
        mock_api_client = MagicMock()
        mock_api_client.query_saved_report.return_value = {
            "computed_at": "",
            "data": {},
            "meta": {},
        }

        service = LiveQueryService(mock_api_client)
        service.query_saved_report(
            bookmark_id=12345,
            bookmark_type="funnels",
            from_date="2024-06-01",
            to_date="2024-06-30",
        )

        mock_api_client.query_saved_report.assert_called_once_with(
            bookmark_id=12345,
            bookmark_type="funnels",
            from_date="2024-06-01",
            to_date="2024-06-30",
        )
