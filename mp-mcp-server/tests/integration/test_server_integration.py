"""Integration tests for the MCP server.

These tests use FastMCP's in-memory Client to test the server
end-to-end with mocked Mixpanel data.
"""

from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def mock_workspace() -> MagicMock:
    """Create a mock workspace for integration tests."""
    workspace = MagicMock()

    # Discovery methods
    workspace.events.return_value = ["signup", "login", "purchase"]
    workspace.properties.return_value = [{"name": "browser", "type": "string"}]
    workspace.funnels.return_value = [{"funnel_id": 1, "name": "Signup"}]
    workspace.cohorts.return_value = [{"cohort_id": 1, "name": "Active"}]
    workspace.bookmarks.return_value = [{"bookmark_id": 1, "name": "Report"}]
    workspace.top_events.return_value = [{"event": "login", "count": 100}]

    # Live query methods
    workspace.segmentation.return_value = MagicMock(
        to_dict=lambda: {"data": {"values": {}}}
    )
    workspace.funnel.return_value = MagicMock(to_dict=lambda: {"data": {"steps": []}})
    workspace.retention.return_value = MagicMock(
        to_dict=lambda: {"data": {"cohorts": []}}
    )
    workspace.jql.return_value = []

    # Fetch methods
    workspace.fetch_events.return_value = MagicMock(
        to_dict=lambda: {"table_name": "events", "row_count": 100}
    )

    # Local methods
    workspace.sql_rows.return_value = []
    workspace.sql_scalar.return_value = 0
    workspace.tables.return_value = []
    workspace.table_schema.return_value = []
    workspace.sample.return_value = []
    workspace.summarize.return_value = {}

    # Info
    workspace.project_id = 123456
    workspace.region = "us"
    workspace.close = MagicMock()

    return workspace


class TestDiscoveryWorkflow:
    """Integration tests for discovery workflow."""

    @pytest.mark.asyncio
    async def test_discovery_workflow(self, mock_workspace: MagicMock) -> None:
        """Test complete discovery workflow through MCP client."""
        from fastmcp import Client

        from mp_mcp_server.server import mcp

        with patch("mp_mcp_server.server.Workspace", return_value=mock_workspace):
            async with Client(mcp) as client:
                # List tools to verify registration
                tools = await client.list_tools()
                tool_names = [t.name for t in tools]

                assert "list_events" in tool_names
                assert "list_properties" in tool_names
                assert "list_funnels" in tool_names


class TestLiveQueryWorkflow:
    """Integration tests for live query workflow."""

    @pytest.mark.asyncio
    async def test_segmentation_workflow(self, mock_workspace: MagicMock) -> None:
        """Test segmentation query through MCP client."""
        from fastmcp import Client

        from mp_mcp_server.server import mcp

        with patch("mp_mcp_server.server.Workspace", return_value=mock_workspace):
            async with Client(mcp) as client:
                # Verify segmentation tool is available
                tools = await client.list_tools()
                tool_names = [t.name for t in tools]

                assert "segmentation" in tool_names
                assert "funnel" in tool_names
                assert "retention" in tool_names


class TestResourceAccess:
    """Integration tests for MCP resources."""

    @pytest.mark.asyncio
    async def test_resource_access(self, mock_workspace: MagicMock) -> None:
        """Test accessing MCP resources."""
        from fastmcp import Client

        from mp_mcp_server.server import mcp

        with patch("mp_mcp_server.server.Workspace", return_value=mock_workspace):
            async with Client(mcp) as client:
                # List resources to verify registration
                resources = await client.list_resources()
                resource_uris = [str(r.uri) for r in resources]

                assert "schema://events" in resource_uris
                assert "schema://funnels" in resource_uris
                assert "workspace://info" in resource_uris


class TestPromptAccess:
    """Integration tests for MCP prompts."""

    @pytest.mark.asyncio
    async def test_prompt_access(self, mock_workspace: MagicMock) -> None:
        """Test accessing MCP prompts."""
        from fastmcp import Client

        from mp_mcp_server.server import mcp

        with patch("mp_mcp_server.server.Workspace", return_value=mock_workspace):
            async with Client(mcp) as client:
                # List prompts to verify registration
                prompts = await client.list_prompts()
                prompt_names = [p.name for p in prompts]

                assert "analytics_workflow" in prompt_names
                assert "funnel_analysis" in prompt_names
                assert "retention_analysis" in prompt_names
