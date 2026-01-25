"""Schema discovery tools for exploring Mixpanel project structure.

This module provides MCP tools for discovering events, properties,
funnels, cohorts, and bookmarks in a Mixpanel project.

Example:
    Ask Claude: "What events are tracked in my project?"
    Claude uses: list_events() -> ["signup", "login", "purchase", ...]
"""

from typing import Any, Literal

from fastmcp import Context

from mixpanel_data import BookmarkType, EntityType
from mp_mcp.context import get_workspace
from mp_mcp.errors import handle_errors
from mp_mcp.server import mcp

# Type aliases
TopEventsType = Literal["general", "average", "unique"]


@mcp.tool
@handle_errors
def list_events(ctx: Context) -> list[str]:
    """List all event names tracked in the Mixpanel project.

    Returns a list of event names that have been tracked, useful for
    understanding what data is available for analysis.

    Args:
        ctx: FastMCP context with workspace access.

    Returns:
        List of event names sorted alphabetically.

    Example:
        Ask: "What events do I have?"
        Returns: ["login", "purchase", "signup", ...]
    """
    ws = get_workspace(ctx)
    return ws.events()


@mcp.tool
@handle_errors
def list_properties(
    ctx: Context,
    event: str,
) -> list[dict[str, Any]]:
    """List properties for a specific event.

    Returns property names captured for the specified event. Note that
    the Mixpanel API only returns property names, not types, so the
    type field is always "unknown".

    Args:
        ctx: FastMCP context with workspace access.
        event: Event name to get properties for.

    Returns:
        List of property definitions with name and type. Type is always
        "unknown" as Mixpanel does not expose property type metadata.

    Example:
        Ask: "What properties does the signup event have?"
        Returns: [{"name": "browser", "type": "unknown"}, ...]
    """
    ws = get_workspace(ctx)
    property_names = ws.properties(event=event)
    return [{"name": name, "type": "unknown"} for name in property_names]


@mcp.tool
@handle_errors
def list_property_values(
    ctx: Context,
    event: str,
    property_name: str,
    limit: int = 100,
) -> list[Any]:
    """List sample values for a specific property.

    Returns example values that have been recorded for a property,
    useful for understanding the data format and possible values.

    Args:
        ctx: FastMCP context with workspace access.
        event: Event name containing the property.
        property_name: Property name to get values for.
        limit: Maximum number of values to return (default 100).

    Returns:
        List of sample values for the property.

    Example:
        Ask: "What values does the browser property have?"
        Returns: ["Chrome", "Firefox", "Safari", ...]
    """
    ws = get_workspace(ctx)
    return ws.property_values(event=event, property_name=property_name, limit=limit)


@mcp.tool
@handle_errors
def list_funnels(ctx: Context) -> list[dict[str, Any]]:
    """List saved funnels in the Mixpanel project.

    Returns metadata about saved funnel definitions including
    funnel ID, name, and step count.

    Args:
        ctx: FastMCP context with workspace access.

    Returns:
        List of funnel metadata dictionaries.

    Example:
        Ask: "Show me my saved funnels"
        Returns: [{"funnel_id": 1, "name": "Signup Funnel", "steps": 3}, ...]
    """
    ws = get_workspace(ctx)
    return [f.to_dict() for f in ws.funnels()]


@mcp.tool
@handle_errors
def list_cohorts(ctx: Context) -> list[dict[str, Any]]:
    """List saved cohorts (user segments) in the Mixpanel project.

    Returns metadata about saved cohort definitions including
    cohort ID, name, and user count.

    Args:
        ctx: FastMCP context with workspace access.

    Returns:
        List of cohort metadata dictionaries.

    Example:
        Ask: "What cohorts do I have?"
        Returns: [{"cohort_id": 1, "name": "Active Users", "count": 1000}, ...]
    """
    ws = get_workspace(ctx)
    return [c.to_dict() for c in ws.cohorts()]


@mcp.tool
@handle_errors
def list_bookmarks(
    ctx: Context,
    bookmark_type: BookmarkType | None = None,
    limit: int = 100,
) -> dict[str, Any]:
    """List saved reports (bookmarks) in the Mixpanel project.

    Returns metadata about saved reports including bookmark ID,
    name, report type, and URL.

    Note: Projects with many bookmarks may experience slow response times.
    Use the bookmark_type filter to reduce response size and latency.

    Args:
        ctx: FastMCP context with workspace access.
        bookmark_type: Optional filter by type
            (insights, funnels, retention, flows, launch-analysis).
            RECOMMENDED for large projects to reduce latency.
        limit: Maximum number of bookmarks to return (default 100).
            Set to 0 for unlimited (may timeout for large projects).

    Returns:
        Dictionary with bookmarks list and metadata about truncation.

    Example:
        Ask: "Show me my saved funnel reports"
        Uses: list_bookmarks(bookmark_type="funnels")

        Ask: "Show first 50 saved reports"
        Uses: list_bookmarks(limit=50)
    """
    ws = get_workspace(ctx)
    bookmarks = [b.to_dict() for b in ws.list_bookmarks(bookmark_type=bookmark_type)]

    # Apply limit to prevent overwhelming context windows and timeouts
    if limit > 0 and len(bookmarks) > limit:
        return {
            "bookmarks": bookmarks[:limit],
            "truncated": True,
            "total_count": len(bookmarks),
            "note": "Use bookmark_type filter to reduce results, or increase limit.",
        }

    return {
        "bookmarks": bookmarks,
        "truncated": False,
        "total_count": len(bookmarks),
    }


@mcp.tool
@handle_errors
def top_events(
    ctx: Context,
    limit: int = 10,
    type: TopEventsType = "general",
) -> list[dict[str, Any]]:
    """List events ranked by activity volume.

    Returns the most frequently tracked events, useful for
    identifying the most important events in the project.

    Args:
        ctx: FastMCP context with workspace access.
        limit: Maximum number of events to return (default 10).
        type: Count type - general (total), average, or unique users.

    Returns:
        List of events with their activity counts, sorted by volume.

    Example:
        Ask: "What are my most popular events by unique users?"
        Uses: top_events(limit=10, type="unique")
    """
    ws = get_workspace(ctx)
    return [e.to_dict() for e in ws.top_events(limit=limit, type=type)]


@mcp.tool
@handle_errors
def workspace_info(ctx: Context) -> dict[str, Any]:
    """Get current workspace state and configuration.

    Returns information about the connected Mixpanel project
    and any locally stored tables.

    Args:
        ctx: FastMCP context with workspace access.

    Returns:
        Dictionary with project_id, region, and table information.

    Example:
        Ask: "What project am I connected to?"
        Returns: {"project_id": 123456, "region": "us", "tables": [...]}
    """
    ws = get_workspace(ctx)
    info = ws.info()
    return {
        "project_id": info.project_id,
        "region": info.region,
        "tables": [t.to_dict() for t in ws.tables()],
    }


@mcp.tool
@handle_errors
def lexicon_schemas(
    ctx: Context,
    entity_type: EntityType | None = None,
) -> list[dict[str, Any]]:
    """List Lexicon schemas (data dictionary) in the project.

    Returns documented event and profile property schemas from the
    Mixpanel Lexicon. Useful for understanding what data is tracked
    and how it's defined.

    Note: The Lexicon API has a strict 5 requests/minute rate limit.
    Results are cached to avoid hitting this limit.

    Args:
        ctx: FastMCP context with workspace access.
        entity_type: Optional filter by type ("event" or "profile").
            If None, returns all schemas.

    Returns:
        List of schema definitions with name, description, and metadata.

    Example:
        Ask: "What events are documented in the Lexicon?"
        Uses: lexicon_schemas(entity_type="event")

        Ask: "Show me all documented schemas"
        Uses: lexicon_schemas()
    """
    ws = get_workspace(ctx)
    return [s.to_dict() for s in ws.lexicon_schemas(entity_type=entity_type)]


@mcp.tool
@handle_errors
def lexicon_schema(
    ctx: Context,
    entity_type: EntityType,
    name: str,
) -> dict[str, Any]:
    """Get a single Lexicon schema by entity type and name.

    Returns the documented schema for a specific event or profile property
    from the Mixpanel Lexicon (data dictionary).

    Note: The Lexicon API has a strict 5 requests/minute rate limit.
    Results are cached to avoid hitting this limit.

    Args:
        ctx: FastMCP context with workspace access.
        entity_type: Entity type ("event" or "profile").
        name: Entity name to look up.

    Returns:
        Schema definition with name, description, properties, and metadata.

    Raises:
        QueryError: If schema not found.

    Example:
        Ask: "What is the schema for the signup event?"
        Uses: lexicon_schema(entity_type="event", name="signup")

        Ask: "Show me the profile property schema for email"
        Uses: lexicon_schema(entity_type="profile", name="$email")
    """
    ws = get_workspace(ctx)
    return ws.lexicon_schema(entity_type=entity_type, name=name).to_dict()


@mcp.tool
@handle_errors
def clear_discovery_cache(ctx: Context) -> dict[str, str]:
    """Clear cached discovery results to fetch fresh data.

    Discovery operations (events, properties, funnels, cohorts, schemas)
    are cached for performance. Use this tool when you need to see
    recently added events or updated schemas.

    Args:
        ctx: FastMCP context with workspace access.

    Returns:
        Dictionary with success status and message.

    Example:
        Ask: "I just added a new event, refresh the cache"
        Uses: clear_discovery_cache()
    """
    ws = get_workspace(ctx)
    ws.clear_discovery_cache()
    return {"status": "success", "message": "Discovery cache cleared"}
