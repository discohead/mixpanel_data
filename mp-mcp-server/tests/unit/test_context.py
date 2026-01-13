"""Tests for context helper functions.

These tests verify the get_workspace helper correctly retrieves
the Workspace from the lifespan state or raises appropriate errors.
"""

from unittest.mock import MagicMock

import pytest


class TestGetWorkspace:
    """Tests for the get_workspace context helper."""

    def test_get_workspace_returns_workspace(
        self, mock_context: MagicMock, mock_workspace: MagicMock
    ) -> None:
        """get_workspace should return the Workspace from lifespan state."""
        from mp_mcp_server.context import get_workspace

        result = get_workspace(mock_context)
        assert result is mock_workspace

    def test_get_workspace_raises_without_lifespan(self) -> None:
        """get_workspace should raise RuntimeError if lifespan state is missing."""
        from mp_mcp_server.context import get_workspace

        ctx = MagicMock()
        # FastMCP 2.x stores lifespan state in server._lifespan_result
        ctx.fastmcp._lifespan_result = None

        with pytest.raises(RuntimeError, match="Workspace not initialized"):
            get_workspace(ctx)

    def test_get_workspace_raises_without_workspace_key(self) -> None:
        """get_workspace should raise RuntimeError if workspace key is missing."""
        from mp_mcp_server.context import get_workspace

        ctx = MagicMock()
        # FastMCP 2.x stores lifespan state in server._lifespan_result
        ctx.fastmcp._lifespan_result = {}

        with pytest.raises(RuntimeError, match="Workspace not initialized"):
            get_workspace(ctx)
