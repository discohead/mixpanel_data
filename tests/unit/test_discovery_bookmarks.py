"""Tests for DiscoveryService.list_bookmarks() method.

Phase 015: Bookmarks API - Tests for bookmark discovery service.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from mixpanel_data._internal.services.discovery import DiscoveryService
from mixpanel_data.types import BookmarkInfo


@pytest.fixture
def mock_api_client() -> MagicMock:
    """Create a mock API client."""
    return MagicMock()


@pytest.fixture
def discovery_service(mock_api_client: MagicMock) -> DiscoveryService:
    """Create a DiscoveryService with mock API client."""
    return DiscoveryService(mock_api_client)


class TestListBookmarks:
    """Tests for DiscoveryService.list_bookmarks()."""

    def test_list_bookmarks_returns_bookmark_info_list(
        self,
        discovery_service: DiscoveryService,
        mock_api_client: MagicMock,
    ) -> None:
        """list_bookmarks() should return list[BookmarkInfo]."""
        mock_api_client.list_bookmarks.return_value = {
            "results": [
                {
                    "id": 63877017,
                    "name": "Weekly Active Users",
                    "type": "insights",
                    "project_id": 12345,
                    "created": "2024-01-01T00:00:00",
                    "modified": "2024-06-15T10:30:00",
                }
            ]
        }

        result = discovery_service.list_bookmarks()

        assert isinstance(result, list)
        assert len(result) == 1
        assert isinstance(result[0], BookmarkInfo)

    def test_list_bookmarks_parses_required_fields(
        self,
        discovery_service: DiscoveryService,
        mock_api_client: MagicMock,
    ) -> None:
        """list_bookmarks() should parse all required BookmarkInfo fields."""
        mock_api_client.list_bookmarks.return_value = {
            "results": [
                {
                    "id": 63877017,
                    "name": "Monthly Revenue",
                    "type": "insights",
                    "project_id": 12345,
                    "created": "2024-01-01T00:00:00",
                    "modified": "2024-06-15T10:30:00",
                }
            ]
        }

        result = discovery_service.list_bookmarks()
        bookmark = result[0]

        assert bookmark.id == 63877017
        assert bookmark.name == "Monthly Revenue"
        assert bookmark.type == "insights"
        assert bookmark.project_id == 12345
        assert bookmark.created == "2024-01-01T00:00:00"
        assert bookmark.modified == "2024-06-15T10:30:00"

    def test_list_bookmarks_parses_optional_fields(
        self,
        discovery_service: DiscoveryService,
        mock_api_client: MagicMock,
    ) -> None:
        """list_bookmarks() should parse optional BookmarkInfo fields."""
        mock_api_client.list_bookmarks.return_value = {
            "results": [
                {
                    "id": 63877017,
                    "name": "Monthly Revenue",
                    "type": "insights",
                    "project_id": 12345,
                    "created": "2024-01-01T00:00:00",
                    "modified": "2024-06-15T10:30:00",
                    "workspace_id": 100,
                    "dashboard_id": 200,
                    "description": "Track monthly revenue",
                    "creator_id": 42,
                    "creator_name": "John Doe",
                }
            ]
        }

        result = discovery_service.list_bookmarks()
        bookmark = result[0]

        assert bookmark.workspace_id == 100
        assert bookmark.dashboard_id == 200
        assert bookmark.description == "Track monthly revenue"
        assert bookmark.creator_id == 42
        assert bookmark.creator_name == "John Doe"

    def test_list_bookmarks_optional_fields_default_to_none(
        self,
        discovery_service: DiscoveryService,
        mock_api_client: MagicMock,
    ) -> None:
        """list_bookmarks() should default optional fields to None when missing."""
        mock_api_client.list_bookmarks.return_value = {
            "results": [
                {
                    "id": 63877017,
                    "name": "Monthly Revenue",
                    "type": "insights",
                    "project_id": 12345,
                    "created": "2024-01-01T00:00:00",
                    "modified": "2024-06-15T10:30:00",
                }
            ]
        }

        result = discovery_service.list_bookmarks()
        bookmark = result[0]

        assert bookmark.workspace_id is None
        assert bookmark.dashboard_id is None
        assert bookmark.description is None
        assert bookmark.creator_id is None
        assert bookmark.creator_name is None

    def test_list_bookmarks_multiple_bookmarks(
        self,
        discovery_service: DiscoveryService,
        mock_api_client: MagicMock,
    ) -> None:
        """list_bookmarks() should handle multiple bookmarks."""
        mock_api_client.list_bookmarks.return_value = {
            "results": [
                {
                    "id": 1,
                    "name": "Report A",
                    "type": "insights",
                    "project_id": 12345,
                    "created": "2024-01-01T00:00:00",
                    "modified": "2024-01-01T00:00:00",
                },
                {
                    "id": 2,
                    "name": "Report B",
                    "type": "funnels",
                    "project_id": 12345,
                    "created": "2024-01-01T00:00:00",
                    "modified": "2024-01-01T00:00:00",
                },
                {
                    "id": 3,
                    "name": "Report C",
                    "type": "retention",
                    "project_id": 12345,
                    "created": "2024-01-01T00:00:00",
                    "modified": "2024-01-01T00:00:00",
                },
            ]
        }

        result = discovery_service.list_bookmarks()

        assert len(result) == 3
        assert result[0].name == "Report A"
        assert result[1].type == "funnels"
        assert result[2].id == 3

    def test_list_bookmarks_empty_results(
        self,
        discovery_service: DiscoveryService,
        mock_api_client: MagicMock,
    ) -> None:
        """list_bookmarks() should handle empty results."""
        mock_api_client.list_bookmarks.return_value = {"results": []}

        result = discovery_service.list_bookmarks()

        assert result == []

    def test_list_bookmarks_with_type_filter(
        self,
        discovery_service: DiscoveryService,
        mock_api_client: MagicMock,
    ) -> None:
        """list_bookmarks() should pass bookmark_type to API client."""
        mock_api_client.list_bookmarks.return_value = {"results": []}

        discovery_service.list_bookmarks(bookmark_type="insights")

        mock_api_client.list_bookmarks.assert_called_once_with(bookmark_type="insights")

    def test_list_bookmarks_all_bookmark_types(
        self,
        discovery_service: DiscoveryService,
        mock_api_client: MagicMock,
    ) -> None:
        """list_bookmarks() should correctly parse all bookmark types."""
        bookmark_types = [
            "insights",
            "funnels",
            "retention",
            "flows",
            "launch-analysis",
        ]

        for bm_type in bookmark_types:
            mock_api_client.list_bookmarks.return_value = {
                "results": [
                    {
                        "id": 1,
                        "name": f"{bm_type} report",
                        "type": bm_type,
                        "project_id": 12345,
                        "created": "2024-01-01T00:00:00",
                        "modified": "2024-01-01T00:00:00",
                    }
                ]
            }

            result = discovery_service.list_bookmarks()

            assert result[0].type == bm_type

    def test_list_bookmarks_null_optional_fields(
        self,
        discovery_service: DiscoveryService,
        mock_api_client: MagicMock,
    ) -> None:
        """list_bookmarks() should handle explicit null values for optional fields."""
        mock_api_client.list_bookmarks.return_value = {
            "results": [
                {
                    "id": 1,
                    "name": "Report",
                    "type": "insights",
                    "project_id": 12345,
                    "created": "2024-01-01T00:00:00",
                    "modified": "2024-01-01T00:00:00",
                    "workspace_id": None,
                    "dashboard_id": None,
                    "description": None,
                    "creator_id": None,
                    "creator_name": None,
                }
            ]
        }

        result = discovery_service.list_bookmarks()
        bookmark = result[0]

        assert bookmark.workspace_id is None
        assert bookmark.dashboard_id is None
        assert bookmark.description is None
        assert bookmark.creator_id is None
        assert bookmark.creator_name is None
