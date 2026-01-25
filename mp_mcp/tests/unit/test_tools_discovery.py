"""Tests for discovery tools.

These tests verify the schema discovery tools are registered and return
correct data from the Workspace.
"""

from unittest.mock import MagicMock


class TestListEventsTools:
    """Tests for the list_events tool."""

    def test_list_events_tool_registered(
        self, registered_tool_names: list[str]
    ) -> None:
        """list_events tool should be registered with the MCP server."""
        assert "list_events" in registered_tool_names

    def test_list_events_returns_event_names(self, mock_context: MagicMock) -> None:
        """list_events should return event names from Workspace."""
        from mp_mcp.tools.discovery import list_events

        result = list_events(mock_context)  # type: ignore[operator]
        assert result == ["signup", "login", "purchase"]


class TestListPropertiesTools:
    """Tests for the list_properties tool."""

    def test_list_properties_tool_registered(
        self, registered_tool_names: list[str]
    ) -> None:
        """list_properties tool should be registered with the MCP server."""
        assert "list_properties" in registered_tool_names

    def test_list_properties_returns_property_names(
        self, mock_context: MagicMock
    ) -> None:
        """list_properties should return property info from Workspace."""
        from mp_mcp.tools.discovery import list_properties

        result = list_properties(mock_context, event="signup")  # type: ignore[operator]
        assert len(result) == 2
        assert result[0]["name"] == "browser"


class TestListPropertyValuesTools:
    """Tests for the list_property_values tool."""

    def test_list_property_values_returns_values(self, mock_context: MagicMock) -> None:
        """list_property_values should return sample values."""
        from mp_mcp.tools.discovery import list_property_values

        result = list_property_values(  # type: ignore[operator]
            mock_context, event="signup", property_name="browser"
        )
        assert result == ["Chrome", "Firefox", "Safari"]


class TestListFunnelsTools:
    """Tests for the list_funnels tool."""

    def test_list_funnels_returns_funnel_info(self, mock_context: MagicMock) -> None:
        """list_funnels should return funnel metadata."""
        from mp_mcp.tools.discovery import list_funnels

        result = list_funnels(mock_context)  # type: ignore[operator]
        assert len(result) == 1
        assert result[0]["name"] == "Signup Funnel"


class TestListCohortsTools:
    """Tests for the list_cohorts tool."""

    def test_list_cohorts_returns_cohort_info(self, mock_context: MagicMock) -> None:
        """list_cohorts should return cohort metadata."""
        from mp_mcp.tools.discovery import list_cohorts

        result = list_cohorts(mock_context)  # type: ignore[operator]
        assert len(result) == 1
        assert result[0]["name"] == "Active Users"


class TestListBookmarksTools:
    """Tests for the list_bookmarks tool."""

    def test_list_bookmarks_returns_bookmark_info(
        self, mock_context: MagicMock
    ) -> None:
        """list_bookmarks should return saved report metadata with pagination info."""
        from mp_mcp.tools.discovery import list_bookmarks

        result = list_bookmarks(mock_context)  # type: ignore[operator]
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
        from mp_mcp.tools.discovery import top_events

        result = top_events(mock_context)  # type: ignore[operator]
        assert len(result) == 2
        assert result[0]["event"] == "login"
        assert result[0]["count"] == 5000


class TestWorkspaceInfoTools:
    """Tests for the workspace_info tool."""

    def test_workspace_info_returns_state(self, mock_context: MagicMock) -> None:
        """workspace_info should return current workspace state."""
        from mp_mcp.tools.discovery import workspace_info

        result = workspace_info(mock_context)  # type: ignore[operator]
        assert result["project_id"] == 123456
        assert result["region"] == "us"


class TestLexiconSchemasTools:
    """Tests for the lexicon_schemas tool."""

    def test_lexicon_schemas_tool_registered(
        self, registered_tool_names: list[str]
    ) -> None:
        """lexicon_schemas tool should be registered with the MCP server."""
        assert "lexicon_schemas" in registered_tool_names

    def test_lexicon_schemas_returns_schemas(self, mock_context: MagicMock) -> None:
        """lexicon_schemas should return schema metadata from Workspace."""
        from mp_mcp.tools.discovery import lexicon_schemas

        result = lexicon_schemas(mock_context)  # type: ignore[operator]
        assert len(result) == 1
        assert result[0]["name"] == "signup"
        assert result[0]["entity_type"] == "event"


class TestLexiconSchemaTools:
    """Tests for the lexicon_schema tool."""

    def test_lexicon_schema_tool_registered(
        self, registered_tool_names: list[str]
    ) -> None:
        """lexicon_schema tool should be registered with the MCP server."""
        assert "lexicon_schema" in registered_tool_names

    def test_lexicon_schema_returns_single_schema(
        self, mock_context: MagicMock
    ) -> None:
        """lexicon_schema should return a single schema from Workspace."""
        from mp_mcp.tools.discovery import lexicon_schema

        result = lexicon_schema(  # type: ignore[operator]
            mock_context, entity_type="event", name="signup"
        )
        assert result["name"] == "signup"
        assert result["entity_type"] == "event"
        assert result["description"] == "User signed up"


class TestClearDiscoveryCacheTools:
    """Tests for the clear_discovery_cache tool."""

    def test_clear_discovery_cache_tool_registered(
        self, registered_tool_names: list[str]
    ) -> None:
        """clear_discovery_cache tool should be registered with the MCP server."""
        assert "clear_discovery_cache" in registered_tool_names

    def test_clear_discovery_cache_returns_success(
        self, mock_context: MagicMock
    ) -> None:
        """clear_discovery_cache should return success status."""
        from mp_mcp.tools.discovery import clear_discovery_cache

        result = clear_discovery_cache(mock_context)  # type: ignore[operator]
        assert result["status"] == "success"
        assert "cache" in result["message"].lower()
