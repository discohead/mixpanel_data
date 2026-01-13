"""MCP server exposing mixpanel_data analytics capabilities to AI assistants.

This package provides an MCP (Model Context Protocol) server that wraps the
mixpanel_data library, enabling AI assistants like Claude Desktop to perform
Mixpanel analytics through natural language.

Example:
    Run the server for Claude Desktop:

    ```bash
    mp-mcp-server
    ```

    Run with a specific account:

    ```bash
    mp-mcp-server --account production
    ```
"""

from mp_mcp_server.server import mcp

__all__ = ["mcp"]
__version__ = "0.1.0"
