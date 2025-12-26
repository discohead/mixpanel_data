"""Tests for Workspace bookmark methods.

Phase 015: Bookmarks API - Tests for Workspace.list_bookmarks() and related methods.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any
from unittest.mock import MagicMock

import pytest
from pydantic import SecretStr

from mixpanel_data import Workspace
from mixpanel_data._internal.config import ConfigManager, Credentials
from mixpanel_data._internal.storage import StorageEngine
from mixpanel_data.types import BookmarkInfo


@pytest.fixture
def mock_credentials() -> Credentials:
    """Create mock credentials for testing."""
    return Credentials(
        username="test_user",
        secret=SecretStr("test_secret"),
        project_id="12345",
        region="us",
    )


@pytest.fixture
def mock_config_manager(mock_credentials: Credentials) -> MagicMock:
    """Create mock ConfigManager that returns credentials."""
    manager = MagicMock(spec=ConfigManager)
    manager.resolve_credentials.return_value = mock_credentials
    return manager


@pytest.fixture
def mock_storage() -> StorageEngine:
    """Create ephemeral storage for testing."""
    return StorageEngine.ephemeral()


@pytest.fixture
def mock_api_client() -> MagicMock:
    """Create mock API client for testing."""
    from mixpanel_data._internal.api_client import MixpanelAPIClient

    client = MagicMock(spec=MixpanelAPIClient)
    client.close = MagicMock()
    return client


@pytest.fixture
def workspace_factory(
    mock_config_manager: MagicMock,
    mock_storage: StorageEngine,
    mock_api_client: MagicMock,
) -> Callable[..., Workspace]:
    """Factory for creating Workspace instances with mocked dependencies."""

    def factory(**kwargs: Any) -> Workspace:
        defaults: dict[str, Any] = {
            "_config_manager": mock_config_manager,
            "_storage": mock_storage,
            "_api_client": mock_api_client,
        }
        defaults.update(kwargs)
        return Workspace(**defaults)

    return factory


class TestListBookmarks:
    """Tests for Workspace.list_bookmarks()."""

    def test_list_bookmarks_delegation(
        self,
        workspace_factory: Callable[..., Workspace],
    ) -> None:
        """list_bookmarks() should delegate to DiscoveryService."""
        ws = workspace_factory()
        try:
            mock_discovery = MagicMock()
            mock_discovery.list_bookmarks.return_value = [
                BookmarkInfo(
                    id=12345,
                    name="Test Report",
                    type="insights",
                    project_id=100,
                    created="2024-01-01T00:00:00",
                    modified="2024-01-01T00:00:00",
                )
            ]
            ws._discovery = mock_discovery

            result = ws.list_bookmarks()

            assert len(result) == 1
            assert result[0].id == 12345
            mock_discovery.list_bookmarks.assert_called_once()
        finally:
            ws.close()

    def test_list_bookmarks_with_type_filter(
        self,
        workspace_factory: Callable[..., Workspace],
    ) -> None:
        """list_bookmarks() should pass bookmark_type filter to service."""
        ws = workspace_factory()
        try:
            mock_discovery = MagicMock()
            mock_discovery.list_bookmarks.return_value = []
            ws._discovery = mock_discovery

            ws.list_bookmarks(bookmark_type="funnels")

            mock_discovery.list_bookmarks.assert_called_once_with(
                bookmark_type="funnels"
            )
        finally:
            ws.close()

    def test_list_bookmarks_returns_list_of_bookmark_info(
        self,
        workspace_factory: Callable[..., Workspace],
    ) -> None:
        """list_bookmarks() should return list[BookmarkInfo]."""
        ws = workspace_factory()
        try:
            mock_discovery = MagicMock()
            mock_discovery.list_bookmarks.return_value = [
                BookmarkInfo(
                    id=1,
                    name="Report A",
                    type="insights",
                    project_id=100,
                    created="2024-01-01T00:00:00",
                    modified="2024-01-01T00:00:00",
                ),
                BookmarkInfo(
                    id=2,
                    name="Report B",
                    type="funnels",
                    project_id=100,
                    created="2024-01-01T00:00:00",
                    modified="2024-01-01T00:00:00",
                ),
            ]
            ws._discovery = mock_discovery

            result = ws.list_bookmarks()

            assert isinstance(result, list)
            assert len(result) == 2
            assert all(isinstance(b, BookmarkInfo) for b in result)
        finally:
            ws.close()

    def test_list_bookmarks_empty_results(
        self,
        workspace_factory: Callable[..., Workspace],
    ) -> None:
        """list_bookmarks() should handle empty results."""
        ws = workspace_factory()
        try:
            mock_discovery = MagicMock()
            mock_discovery.list_bookmarks.return_value = []
            ws._discovery = mock_discovery

            result = ws.list_bookmarks()

            assert result == []
        finally:
            ws.close()

    def test_list_bookmarks_without_type_filter(
        self,
        workspace_factory: Callable[..., Workspace],
    ) -> None:
        """list_bookmarks() should call service without filter when not specified."""
        ws = workspace_factory()
        try:
            mock_discovery = MagicMock()
            mock_discovery.list_bookmarks.return_value = []
            ws._discovery = mock_discovery

            ws.list_bookmarks()

            mock_discovery.list_bookmarks.assert_called_once_with(bookmark_type=None)
        finally:
            ws.close()

    def test_list_bookmarks_all_type_filters(
        self,
        workspace_factory: Callable[..., Workspace],
    ) -> None:
        """list_bookmarks() should accept all valid bookmark type filters."""
        bookmark_types = [
            "insights",
            "funnels",
            "retention",
            "flows",
            "launch-analysis",
        ]

        for bm_type in bookmark_types:
            ws = workspace_factory()
            try:
                mock_discovery = MagicMock()
                mock_discovery.list_bookmarks.return_value = []
                ws._discovery = mock_discovery

                ws.list_bookmarks(bookmark_type=bm_type)  # type: ignore[arg-type]

                mock_discovery.list_bookmarks.assert_called_once_with(
                    bookmark_type=bm_type
                )
            finally:
                ws.close()


class TestQuerySavedReport:
    """Tests for Workspace.query_saved_report()."""

    def test_query_saved_report_delegation(
        self,
        workspace_factory: Callable[..., Workspace],
    ) -> None:
        """query_saved_report() should delegate to LiveQueryService."""
        from mixpanel_data.types import SavedReportResult

        ws = workspace_factory()
        try:
            mock_live_query = MagicMock()
            mock_live_query.query_saved_report.return_value = SavedReportResult(
                bookmark_id=12345,
                computed_at="2024-01-15T10:00:00",
                from_date="2024-01-01",
                to_date="2024-01-14",
                headers=["$event"],
                series={"Page View": {"2024-01-01": 100}},
            )
            ws._live_query = mock_live_query

            result = ws.query_saved_report(bookmark_id=12345)

            assert result.bookmark_id == 12345
            mock_live_query.query_saved_report.assert_called_once_with(
                bookmark_id=12345
            )
        finally:
            ws.close()

    def test_query_saved_report_insights_type(
        self,
        workspace_factory: Callable[..., Workspace],
    ) -> None:
        """query_saved_report() should return insights report_type for standard reports."""
        from mixpanel_data.types import SavedReportResult

        ws = workspace_factory()
        try:
            mock_live_query = MagicMock()
            mock_live_query.query_saved_report.return_value = SavedReportResult(
                bookmark_id=12345,
                computed_at="2024-01-15T10:00:00",
                from_date="2024-01-01",
                to_date="2024-01-14",
                headers=["$event", "Date"],
                series={"Page View": {"2024-01-01": 100}},
            )
            ws._live_query = mock_live_query

            result = ws.query_saved_report(bookmark_id=12345)

            assert result.report_type == "insights"
        finally:
            ws.close()

    def test_query_saved_report_retention_type(
        self,
        workspace_factory: Callable[..., Workspace],
    ) -> None:
        """query_saved_report() should return retention report_type for retention reports."""
        from mixpanel_data.types import SavedReportResult

        ws = workspace_factory()
        try:
            mock_live_query = MagicMock()
            mock_live_query.query_saved_report.return_value = SavedReportResult(
                bookmark_id=12345,
                computed_at="2024-01-15T10:00:00",
                from_date="2024-01-01",
                to_date="2024-01-14",
                headers=["$retention"],
                series={"cohort": {"2024-01-01": {"first": 100, "counts": [80, 60]}}},
            )
            ws._live_query = mock_live_query

            result = ws.query_saved_report(bookmark_id=12345)

            assert result.report_type == "retention"
        finally:
            ws.close()

    def test_query_saved_report_funnel_type(
        self,
        workspace_factory: Callable[..., Workspace],
    ) -> None:
        """query_saved_report() should return funnel report_type for funnel reports."""
        from mixpanel_data.types import SavedReportResult

        ws = workspace_factory()
        try:
            mock_live_query = MagicMock()
            mock_live_query.query_saved_report.return_value = SavedReportResult(
                bookmark_id=12345,
                computed_at="2024-01-15T10:00:00",
                from_date="2024-01-01",
                to_date="2024-01-14",
                headers=["$funnel"],
                series={"count": 1000, "overall_conv_ratio": 0.5},
            )
            ws._live_query = mock_live_query

            result = ws.query_saved_report(bookmark_id=12345)

            assert result.report_type == "funnel"
        finally:
            ws.close()

    def test_query_saved_report_returns_saved_report_result(
        self,
        workspace_factory: Callable[..., Workspace],
    ) -> None:
        """query_saved_report() should return SavedReportResult instance."""
        from mixpanel_data.types import SavedReportResult

        ws = workspace_factory()
        try:
            mock_live_query = MagicMock()
            mock_live_query.query_saved_report.return_value = SavedReportResult(
                bookmark_id=12345,
                computed_at="2024-01-15T10:00:00",
                from_date="2024-01-01",
                to_date="2024-01-14",
                headers=[],
                series={},
            )
            ws._live_query = mock_live_query

            result = ws.query_saved_report(bookmark_id=12345)

            assert isinstance(result, SavedReportResult)
        finally:
            ws.close()


class TestQueryFlows:
    """Tests for Workspace.query_flows()."""

    def test_query_flows_delegation(
        self,
        workspace_factory: Callable[..., Workspace],
    ) -> None:
        """query_flows() should delegate to LiveQueryService."""
        from mixpanel_data.types import FlowsResult

        ws = workspace_factory()
        try:
            mock_live_query = MagicMock()
            mock_live_query.query_flows.return_value = FlowsResult(
                bookmark_id=12345,
                computed_at="2024-01-15T10:00:00",
                steps=[{"step": 1, "event": "Page View", "count": 1000}],
                breakdowns=[],
                overall_conversion_rate=0.5,
            )
            ws._live_query = mock_live_query

            result = ws.query_flows(bookmark_id=12345)

            assert result.bookmark_id == 12345
            mock_live_query.query_flows.assert_called_once_with(bookmark_id=12345)
        finally:
            ws.close()

    def test_query_flows_returns_flows_result(
        self,
        workspace_factory: Callable[..., Workspace],
    ) -> None:
        """query_flows() should return FlowsResult instance."""
        from mixpanel_data.types import FlowsResult

        ws = workspace_factory()
        try:
            mock_live_query = MagicMock()
            mock_live_query.query_flows.return_value = FlowsResult(
                bookmark_id=12345,
                computed_at="2024-01-15T10:00:00",
            )
            ws._live_query = mock_live_query

            result = ws.query_flows(bookmark_id=12345)

            assert isinstance(result, FlowsResult)
        finally:
            ws.close()

    def test_query_flows_with_steps_and_breakdowns(
        self,
        workspace_factory: Callable[..., Workspace],
    ) -> None:
        """query_flows() should return steps and breakdowns data."""
        from mixpanel_data.types import FlowsResult

        ws = workspace_factory()
        try:
            mock_live_query = MagicMock()
            mock_live_query.query_flows.return_value = FlowsResult(
                bookmark_id=12345,
                computed_at="2024-01-15T10:00:00",
                steps=[
                    {"step": 1, "event": "Page View", "count": 1000},
                    {"step": 2, "event": "Add to Cart", "count": 500},
                ],
                breakdowns=[
                    {"path": "Page View -> Add to Cart", "count": 500},
                ],
                overall_conversion_rate=0.5,
            )
            ws._live_query = mock_live_query

            result = ws.query_flows(bookmark_id=12345)

            assert len(result.steps) == 2
            assert len(result.breakdowns) == 1
            assert result.overall_conversion_rate == 0.5
        finally:
            ws.close()
