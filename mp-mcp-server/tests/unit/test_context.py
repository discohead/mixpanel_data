"""Tests for context helper functions.

These tests verify the get_workspace helper correctly retrieves
the Workspace wrapped in RateLimitedWorkspace from the lifespan state
or raises appropriate errors.
"""

from unittest.mock import MagicMock

import pytest


class TestGetWorkspace:
    """Tests for the get_workspace context helper."""

    def test_get_workspace_returns_rate_limited_wrapper(
        self, mock_context: MagicMock, mock_workspace: MagicMock
    ) -> None:
        """get_workspace should return a RateLimitedWorkspace wrapping the Workspace."""
        from mp_mcp_server.context import get_workspace
        from mp_mcp_server.middleware.rate_limiting import RateLimitedWorkspace

        result = get_workspace(mock_context)

        # Should return a RateLimitedWorkspace wrapper
        assert isinstance(result, RateLimitedWorkspace)

        # The wrapper should proxy calls to the underlying workspace
        mock_workspace.events.return_value = ["test_event"]
        assert result.events() == ["test_event"]
        mock_workspace.events.assert_called_once()

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

    def test_get_workspace_raises_without_rate_limiter_key(
        self, mock_workspace: MagicMock
    ) -> None:
        """get_workspace should raise RuntimeError if rate_limiter key is missing."""
        from mp_mcp_server.context import get_workspace

        ctx = MagicMock()
        # Has workspace but no rate_limiter
        ctx.fastmcp._lifespan_result = {"workspace": mock_workspace}

        with pytest.raises(RuntimeError, match="Rate limiter not initialized"):
            get_workspace(ctx)
