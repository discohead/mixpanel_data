"""Context helpers for accessing MCP server state.

This module provides utility functions for extracting the Workspace
and other state from the FastMCP context object.

Example:
    ```python
    @mcp.tool
    def list_events(ctx: Context) -> list[str]:
        ws = get_workspace(ctx)
        return ws.events()
    ```
"""

from typing import TYPE_CHECKING, cast

if TYPE_CHECKING:
    from fastmcp import Context

    from mixpanel_data import Workspace


def get_workspace(ctx: "Context") -> "Workspace":
    """Extract the Workspace from the FastMCP context.

    Args:
        ctx: The FastMCP Context injected into tool functions.

    Returns:
        The Workspace instance created by the lifespan.

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
    # FastMCP 2.x stores lifespan state in server._lifespan_result
    lifespan_state = ctx.fastmcp._lifespan_result

    if lifespan_state is None or "workspace" not in lifespan_state:
        raise RuntimeError(
            "Workspace not initialized. "
            "Ensure the server is running with the lifespan context."
        )

    from mixpanel_data import Workspace

    return cast(Workspace, lifespan_state["workspace"])
