"""Public authentication and configuration module.

This module provides public access to credential management functionality.
It re-exports the ConfigManager and related types for public use.

Example usage:
    from mixpanel_data.auth import ConfigManager, Credentials

    config = ConfigManager()
    creds = config.resolve_credentials()
"""

from mixpanel_data._internal.config import (
    AccountInfo,
    ConfigManager,
    Credentials,
)

__all__ = [
    "ConfigManager",
    "Credentials",
    "AccountInfo",
]
