"""CLI entry point for the MCP server.

Provides a command-line interface to run the Mixpanel MCP server
with configurable options for account, transport, and port.

Example:
    Run with default settings (stdio transport):

    ```bash
    mp-mcp-server
    ```

    Run with a specific account:

    ```bash
    mp-mcp-server --account production
    ```

    Run with HTTP transport:

    ```bash
    mp-mcp-server --transport http --port 8000
    ```
"""

import argparse
from collections.abc import Sequence

from mp_mcp_server.server import mcp, set_account


def parse_args(args: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments.

    Args:
        args: Command-line arguments to parse. Uses sys.argv if None.

    Returns:
        Parsed arguments namespace.
    """
    parser = argparse.ArgumentParser(
        prog="mp-mcp-server",
        description="MCP server for Mixpanel analytics",
    )

    parser.add_argument(
        "--account",
        type=str,
        default=None,
        help="Named account from ~/.mp/config.toml",
    )

    parser.add_argument(
        "--transport",
        type=str,
        default="stdio",
        choices=["stdio", "http"],
        help="Transport type (default: stdio)",
    )

    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="HTTP port (only used with --transport http)",
    )

    return parser.parse_args(args)


def main() -> None:
    """Run the MCP server with configured options.

    Entry point for the `mp-mcp-server` command.
    """
    args = parse_args()

    # Configure the account before starting
    if args.account:
        set_account(args.account)

    # Run the server with the specified transport
    if args.transport == "http":
        mcp.run(transport="sse", port=args.port)
    else:
        mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
