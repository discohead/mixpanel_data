"""MCP resources for accessing Mixpanel schema and workspace state.

Resources provide read-only access to cacheable data like schema information
and workspace state. MCP clients can read these for context.

Example:
    MCP clients can read schema://events to get the list of tracked events
    without making a tool call.
"""

import json
import logging
from collections.abc import Callable
from functools import wraps
from typing import ParamSpec, TypeVar

from fastmcp import Context
from mcp.shared.exceptions import McpError
from mcp.types import INTERNAL_ERROR, ErrorData

from mixpanel_data.exceptions import MixpanelDataError
from mp_mcp_server.context import get_workspace
from mp_mcp_server.server import mcp

logger = logging.getLogger(__name__)

P = ParamSpec("P")
R = TypeVar("R", bound=str)


def handle_resource_errors(func: Callable[P, R]) -> Callable[P, R]:
    """Decorator to handle errors in MCP resources.

    Raises McpError with structured error data that agents can parse
    for self-correction. The error data includes error codes, messages,
    and actionable suggestions.

    Args:
        func: The resource function to wrap.

    Returns:
        The wrapped function that raises McpError on failure.

    Raises:
        McpError: When the resource fails, with structured error data
            in the `data` field for agent recovery.

    Example:
        ```python
        @mcp.resource("schema://events")
        @handle_resource_errors
        def events_resource(ctx: Context) -> str:
            ws = get_workspace(ctx)
            return json.dumps(ws.events())
        ```
    """

    @wraps(func)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> str:
        try:
            return func(*args, **kwargs)
        except MixpanelDataError as e:
            logger.warning("Resource error: %s", e, exc_info=True)
            raise McpError(
                ErrorData(
                    code=INTERNAL_ERROR,
                    message=str(e),
                    data=e.to_dict(),
                )
            ) from e
        except Exception as e:
            logger.exception("Unexpected resource error: %s", e)
            raise McpError(
                ErrorData(
                    code=INTERNAL_ERROR,
                    message=str(e),
                    data={
                        "code": "INTERNAL_ERROR",
                        "message": str(e),
                        "details": {"error_type": type(e).__name__},
                    },
                )
            ) from e

    return wrapper  # type: ignore[return-value]


@mcp.resource("workspace://info")
@handle_resource_errors
def workspace_info_resource(ctx: Context) -> str:
    """Workspace configuration and connection status.

    Returns project_id, region, and current session state.

    Args:
        ctx: FastMCP context with workspace access.

    Returns:
        JSON string with workspace info.
    """
    ws = get_workspace(ctx)
    workspace_info = ws.info()
    info = {
        "project_id": workspace_info.project_id,
        "region": workspace_info.region,
        "account": workspace_info.account,
        "path": str(workspace_info.path) if workspace_info.path else None,
        "size_mb": workspace_info.size_mb,
        "created_at": (
            workspace_info.created_at.isoformat() if workspace_info.created_at else None
        ),
        "tables": [t.to_dict() for t in ws.tables()],
    }
    return json.dumps(info, indent=2)


@mcp.resource("workspace://tables")
@handle_resource_errors
def tables_resource(ctx: Context) -> str:
    """List of locally stored tables.

    Returns table names, row counts, and types for all fetched data.

    Args:
        ctx: FastMCP context with workspace access.

    Returns:
        JSON string with table list.
    """
    ws = get_workspace(ctx)
    tables = [t.to_dict() for t in ws.tables()]
    return json.dumps(tables, indent=2)


@mcp.resource("schema://events")
@handle_resource_errors
def events_resource(ctx: Context) -> str:
    """List of event names tracked in the project.

    Returns all event names for schema exploration.

    Args:
        ctx: FastMCP context with workspace access.

    Returns:
        JSON string with event list.
    """
    ws = get_workspace(ctx)
    events = ws.events()
    return json.dumps(events, indent=2)


@mcp.resource("schema://funnels")
@handle_resource_errors
def funnels_resource(ctx: Context) -> str:
    """Saved funnel definitions.

    Returns funnel IDs, names, and step counts.

    Args:
        ctx: FastMCP context with workspace access.

    Returns:
        JSON string with funnel list.
    """
    ws = get_workspace(ctx)
    funnels = [f.to_dict() for f in ws.funnels()]
    return json.dumps(funnels, indent=2)


@mcp.resource("schema://cohorts")
@handle_resource_errors
def cohorts_resource(ctx: Context) -> str:
    """Saved cohort definitions.

    Returns cohort IDs, names, and user counts.

    Args:
        ctx: FastMCP context with workspace access.

    Returns:
        JSON string with cohort list.
    """
    ws = get_workspace(ctx)
    cohorts = [c.to_dict() for c in ws.cohorts()]
    return json.dumps(cohorts, indent=2)


@mcp.resource("schema://bookmarks")
@handle_resource_errors
def bookmarks_resource(ctx: Context) -> str:
    """Saved report bookmarks.

    Returns bookmark IDs, names, and report types.

    Args:
        ctx: FastMCP context with workspace access.

    Returns:
        JSON string with bookmark list.
    """
    ws = get_workspace(ctx)
    bookmarks = [b.to_dict() for b in ws.list_bookmarks()]
    return json.dumps(bookmarks, indent=2)
