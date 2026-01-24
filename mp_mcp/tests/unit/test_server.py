"""Tests for FastMCP server configuration and lifespan.

These tests verify the server is correctly configured with name, instructions,
and proper lifespan management for the Workspace instance.
"""

from unittest.mock import MagicMock, patch

import pytest


class TestServerConfiguration:
    """Tests for server metadata and configuration."""

    def test_server_has_name(self) -> None:
        """Server should have a descriptive name for MCP clients."""
        from mp_mcp.server import mcp

        assert mcp.name == "mixpanel"

    def test_server_has_instructions(self) -> None:
        """Server should have instructions describing its capabilities."""
        from mp_mcp.server import mcp

        assert mcp.instructions is not None
        assert len(mcp.instructions) > 0
        assert "Mixpanel" in mcp.instructions


class TestLifespan:
    """Tests for server lifespan management."""

    @pytest.mark.asyncio
    async def test_lifespan_creates_workspace(self) -> None:
        """Lifespan should create a Workspace instance on startup."""
        from mp_mcp.server import lifespan, mcp

        with patch("mp_mcp.server.Workspace") as mock_workspace_cls:
            mock_workspace = MagicMock()
            mock_workspace_cls.return_value = mock_workspace

            async with lifespan(mcp) as state:
                assert "workspace" in state
                mock_workspace_cls.assert_called_once()

    @pytest.mark.asyncio
    async def test_lifespan_closes_workspace(self) -> None:
        """Lifespan should close the Workspace on shutdown."""
        from mp_mcp.server import lifespan, mcp

        with patch("mp_mcp.server.Workspace") as mock_workspace_cls:
            mock_workspace = MagicMock()
            mock_workspace_cls.return_value = mock_workspace

            async with lifespan(mcp):
                pass

            mock_workspace.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_lifespan_with_account(self) -> None:
        """Lifespan should pass account parameter to Workspace."""
        from mp_mcp.server import lifespan, mcp, set_account

        with patch("mp_mcp.server.Workspace") as mock_workspace_cls:
            mock_workspace = MagicMock()
            mock_workspace_cls.return_value = mock_workspace

            set_account("production")

            async with lifespan(mcp):
                pass

            mock_workspace_cls.assert_called_once()
            call_kwargs = mock_workspace_cls.call_args.kwargs
            assert call_kwargs.get("account") == "production"

            # Reset for other tests
            set_account(None)
