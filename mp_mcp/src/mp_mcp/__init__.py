"""MCP server exposing mixpanel_data analytics capabilities to AI assistants.

This package provides an MCP (Model Context Protocol) server that wraps the
mixpanel_data library, enabling AI assistants like Claude Desktop to perform
Mixpanel analytics through natural language.

Example:
    Run the server for Claude Desktop:

    ```bash
    mp_mcp
    ```

    Run with a specific account:

    ```bash
    mp_mcp --account production
    ```
"""

from mp_mcp.server import mcp

__all__ = ["mcp"]
__version__ = "0.1.0"
