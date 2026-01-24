"""Context helpers for accessing MCP server state.

This module provides utility functions for extracting the Workspace
and other state from the FastMCP context object.

The get_workspace function returns a RateLimitedWorkspace wrapper that
applies rate limiting to all Workspace API method calls. This ensures
that composed and intelligent tools (which call Workspace methods directly)
still respect Mixpanel's API rate limits.

Example:
    ```python
    @mcp.tool
    def list_events(ctx: Context) -> list[str]:
        ws = get_workspace(ctx)
        return ws.events()
    ```
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fastmcp import Context

from mp_mcp.middleware.rate_limiting import (
    MixpanelRateLimitMiddleware,
    RateLimitedWorkspace,
)


def get_workspace(ctx: "Context") -> RateLimitedWorkspace:
    """Extract the Workspace from the FastMCP context.

    Returns a RateLimitedWorkspace wrapper that applies rate limiting
    to all API method calls, ensuring composed and intelligent tools
    respect Mixpanel's rate limits even when calling Workspace methods
    directly.

    Args:
        ctx: The FastMCP Context injected into tool functions.

    Returns:
        A RateLimitedWorkspace wrapper around the Workspace instance.

    Raises:
        RuntimeError: If the Workspace is not initialized (lifespan not running).

    Example:
        ```python
        @mcp.tool
        def list_events(ctx: Context) -> list[str]:
            ws = get_workspace(ctx)
            return ws.events()
        ```
    """
    # FastMCP 3.0 uses public lifespan_context property
    lifespan_state = ctx.lifespan_context

    if lifespan_state is None or "workspace" not in lifespan_state:
        raise RuntimeError(
            "Workspace not initialized. "
            "Ensure the server is running with the lifespan context."
        )

    if "rate_limiter" not in lifespan_state:
        raise RuntimeError(
            "Rate limiter not initialized. "
            "Ensure the server is running with the lifespan context."
        )

    from mixpanel_data import Workspace

    workspace: Workspace = lifespan_state["workspace"]
    rate_limiter: MixpanelRateLimitMiddleware = lifespan_state["rate_limiter"]

    return RateLimitedWorkspace(workspace, rate_limiter)
