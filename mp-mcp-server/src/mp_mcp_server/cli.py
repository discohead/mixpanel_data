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

    Run with SSE transport (HTTP Server-Sent Events):

    ```bash
    mp-mcp-server --transport sse --port 8000
    ```
"""

import argparse
import sys
from collections.abc import Sequence

from mp_mcp_server.server import mcp, set_account


def _validate_account(account: str) -> bool:
    """Validate that an account exists in the configuration.

    Args:
        account: The account name to validate.

    Returns:
        True if the account exists.

    Raises:
        SystemExit: If the account does not exist.
    """
    from mixpanel_data import Workspace
    from mixpanel_data.exceptions import AccountNotFoundError

    try:
        # Create a workspace with the account to validate it exists
        Workspace(account=account)
        return True
    except AccountNotFoundError as e:
        # Provide helpful error message
        msg = f"Error: Account '{account}' not found."
        if e.available_accounts:
            msg += f"\nAvailable accounts: {', '.join(e.available_accounts)}"
        msg += "\n\nCheck ~/.mp/config.toml for configured accounts."
        sys.stderr.write(msg + "\n")
        sys.exit(1)


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
        choices=["stdio", "sse", "http"],
        help="Transport type (default: stdio). 'sse' uses HTTP Server-Sent Events. 'http' uses Streamable HTTP.",
    )

    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="HTTP port (only used with --transport sse or http)",
    )

    return parser.parse_args(args)


def main() -> None:
    """Run the MCP server with configured options.

    Entry point for the `mp-mcp-server` command.

    Validates the account exists before starting the server to provide
    immediate feedback on configuration errors.
    """
    args = parse_args()

    # Configure the account before starting
    if args.account:
        # Validate account exists before starting server
        _validate_account(args.account)
        set_account(args.account)

    # Run the server with the specified transport
    if args.transport == "http":
        mcp.run(transport="http", host="0.0.0.0", port=args.port)
    elif args.transport == "sse":
        mcp.run(transport="sse", port=args.port)
    else:
        mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
