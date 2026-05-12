"""CLI package for mixpanel_headless.

This module provides the `mp` command-line interface for interacting
with Mixpanel data. All commands delegate to the Workspace facade or
ConfigManager, adding only I/O formatting.
"""

from mixpanel_headless.cli.main import app

__all__ = ["app"]
