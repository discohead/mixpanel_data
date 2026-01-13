"""Tests for discovery tools.

These tests verify the schema discovery tools are registered and return
correct data from the Workspace.
"""

from unittest.mock import MagicMock


class TestListEventsTools:
    """Tests for the list_events tool."""

    def test_list_events_tool_registered(self) -> None:
        """list_events tool should be registered with the MCP server."""
        from mp_mcp_server.server import mcp

        tool_names = list(mcp._tool_manager._tools.keys())
        assert "list_events" in tool_names

    def test_list_events_returns_event_names(self, mock_context: MagicMock) -> None:
        """list_events should return event names from Workspace."""
        from mp_mcp_server.tools.discovery import list_events

        result = list_events.fn(mock_context)
        assert result == ["signup", "login", "purchase"]


class TestListPropertiesTools:
    """Tests for the list_properties tool."""

    def test_list_properties_tool_registered(self) -> None:
        """list_properties tool should be registered with the MCP server."""
        from mp_mcp_server.server import mcp

        tool_names = list(mcp._tool_manager._tools.keys())
        assert "list_properties" in tool_names

    def test_list_properties_returns_property_names(
        self, mock_context: MagicMock
    ) -> None:
        """list_properties should return property info from Workspace."""
        from mp_mcp_server.tools.discovery import list_properties

        result = list_properties.fn(mock_context, event="signup")
        assert len(result) == 2
        assert result[0]["name"] == "browser"


class TestListPropertyValuesTools:
    """Tests for the list_property_values tool."""

    def test_list_property_values_returns_values(self, mock_context: MagicMock) -> None:
        """list_property_values should return sample values."""
        from mp_mcp_server.tools.discovery import list_property_values

        result = list_property_values.fn(
            mock_context, event="signup", property_name="browser"
        )
        assert result == ["Chrome", "Firefox", "Safari"]


class TestListFunnelsTools:
    """Tests for the list_funnels tool."""

    def test_list_funnels_returns_funnel_info(self, mock_context: MagicMock) -> None:
        """list_funnels should return funnel metadata."""
        from mp_mcp_server.tools.discovery import list_funnels

        result = list_funnels.fn(mock_context)
        assert len(result) == 1
        assert result[0]["name"] == "Signup Funnel"


class TestListCohortsTools:
    """Tests for the list_cohorts tool."""

    def test_list_cohorts_returns_cohort_info(self, mock_context: MagicMock) -> None:
        """list_cohorts should return cohort metadata."""
        from mp_mcp_server.tools.discovery import list_cohorts

        result = list_cohorts.fn(mock_context)
        assert len(result) == 1
        assert result[0]["name"] == "Active Users"


class TestListBookmarksTools:
    """Tests for the list_bookmarks tool."""

    def test_list_bookmarks_returns_bookmark_info(
        self, mock_context: MagicMock
    ) -> None:
        """list_bookmarks should return saved report metadata with pagination info."""
        from mp_mcp_server.tools.discovery import list_bookmarks

        result = list_bookmarks.fn(mock_context)
        # New format returns dict with bookmarks list and pagination metadata
        assert "bookmarks" in result
        assert "truncated" in result
        assert "total_count" in result
        assert len(result["bookmarks"]) == 1
        assert result["bookmarks"][0]["name"] == "Daily Signups"
        assert result["truncated"] is False
        assert result["total_count"] == 1


class TestTopEventsTools:
    """Tests for the top_events tool."""

    def test_top_events_returns_event_activity(self, mock_context: MagicMock) -> None:
        """top_events should return events ranked by activity."""
        from mp_mcp_server.tools.discovery import top_events

        result = top_events.fn(mock_context)
        assert len(result) == 2
        assert result[0]["event"] == "login"
        assert result[0]["count"] == 5000


class TestWorkspaceInfoTools:
    """Tests for the workspace_info tool."""

    def test_workspace_info_returns_state(self, mock_context: MagicMock) -> None:
        """workspace_info should return current workspace state."""
        from mp_mcp_server.tools.discovery import workspace_info

        result = workspace_info.fn(mock_context)
        assert result["project_id"] == 123456
        assert result["region"] == "us"
