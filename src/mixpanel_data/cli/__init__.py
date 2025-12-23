"""CLI package for mixpanel_data.

This module provides the `mp` command-line interface for interacting
with Mixpanel data. All commands delegate to the Workspace facade or
ConfigManager, adding only I/O formatting.
"""

from mixpanel_data.cli.main import app

__all__ = ["app"]
