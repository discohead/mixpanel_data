"""Service layer for mixpanel_headless.

This package contains high-level service classes that orchestrate
operations using the lower-level API client.
"""

from mixpanel_headless._internal.services.discovery import DiscoveryService
from mixpanel_headless._internal.services.live_query import LiveQueryService

__all__ = ["DiscoveryService", "LiveQueryService"]
