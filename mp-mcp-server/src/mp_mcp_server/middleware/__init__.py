"""Middleware components for the MCP server.

This package provides middleware for request processing:

- caching: Response caching for discovery operations
- rate_limiting: Mixpanel API rate limit enforcement
- audit: Audit logging with timing and outcomes

Example:
    ```python
    from mp_mcp_server.middleware import (
        create_audit_middleware,
        create_caching_middleware,
        MixpanelRateLimitMiddleware,
    )

    # Order: Logging (outermost) -> Rate Limiting -> Caching (innermost)
    mcp.add_middleware(create_audit_middleware())
    mcp.add_middleware(MixpanelRateLimitMiddleware())
    mcp.add_middleware(create_caching_middleware())
    ```
"""

from mp_mcp_server.middleware.audit import (
    AuditConfig,
    AuditMiddleware,
    create_audit_middleware,
)
from mp_mcp_server.middleware.caching import (
    CACHEABLE_DISCOVERY_TOOLS,
    DEFAULT_DISCOVERY_TTL,
    create_caching_middleware,
)
from mp_mcp_server.middleware.rate_limiting import (
    EXPORT_API_TOOLS,
    QUERY_API_TOOLS,
    MixpanelRateLimitMiddleware,
    RateLimitConfig,
    create_export_rate_limiter,
    create_query_rate_limiter,
)

__all__ = [
    # Audit
    "AuditConfig",
    "AuditMiddleware",
    "create_audit_middleware",
    # Caching
    "CACHEABLE_DISCOVERY_TOOLS",
    "DEFAULT_DISCOVERY_TTL",
    "create_caching_middleware",
    # Rate Limiting
    "EXPORT_API_TOOLS",
    "QUERY_API_TOOLS",
    "MixpanelRateLimitMiddleware",
    "RateLimitConfig",
    "create_export_rate_limiter",
    "create_query_rate_limiter",
]
