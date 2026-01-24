"""Authentication and account management tools for MCP server.

This module provides MCP tools for managing Mixpanel accounts without
modifying credentials (read-only operations plus switch_account which
only changes the default, not the credential values).

Unlike other MCP tools, auth tools do NOT use the workspace from the
lifespan context. They create their own ConfigManager instance to
read from the config file directly.

Example:
    ```python
    # List all configured accounts
    result = list_accounts(ctx)
    # [{"name": "prod", "username": "svc-prod", ...}]

    # Show account details (secret always redacted)
    result = show_account(ctx, name="prod")
    # {"name": "prod", "secret": "********", ...}

    # Switch default account
    result = switch_account(ctx, name="staging")
    # {"default": "staging"}

    # Test credentials
    result = test_credentials(ctx, account="prod")
    # {"success": True, "events_found": 42, ...}
    ```
"""

from typing import Any

from fastmcp import Context

from mixpanel_data import Workspace
from mixpanel_data.auth import ConfigManager
from mp_mcp.errors import handle_errors
from mp_mcp.server import mcp


@mcp.tool
@handle_errors
def list_accounts(ctx: Context) -> list[dict[str, Any]]:
    """List all configured Mixpanel accounts.

    Returns information about all accounts stored in ~/.mp/config.toml,
    including which one is set as the default. Secrets are never exposed.

    Args:
        ctx: FastMCP context (unused, required by MCP tool signature).

    Returns:
        List of account dictionaries with name, username, project_id,
        region, and is_default fields.

    Example:
        ```python
        result = list_accounts(ctx)
        # [
        #     {"name": "prod", "username": "svc-prod", "project_id": "123",
        #      "region": "us", "is_default": True},
        #     {"name": "dev", "username": "svc-dev", "project_id": "456",
        #      "region": "eu", "is_default": False}
        # ]
        ```
    """
    _ = ctx  # Unused but required by MCP signature
    config = ConfigManager()
    accounts = config.list_accounts()
    return [
        {
            "name": acc.name,
            "username": acc.username,
            "project_id": acc.project_id,
            "region": acc.region,
            "is_default": acc.is_default,
        }
        for acc in accounts
    ]


@mcp.tool
@handle_errors
def show_account(ctx: Context, name: str) -> dict[str, Any]:
    """Show details for a specific Mixpanel account.

    Returns account configuration with the secret redacted for security.

    Args:
        ctx: FastMCP context (unused, required by MCP tool signature).
        name: Account name to show.

    Returns:
        Dictionary with name, username, secret (redacted), project_id,
        region, and is_default fields.

    Raises:
        AccountNotFoundError: If the account doesn't exist.

    Example:
        ```python
        result = show_account(ctx, name="production")
        # {"name": "production", "username": "svc-prod",
        #  "secret": "********", "project_id": "123456",
        #  "region": "us", "is_default": True}
        ```
    """
    _ = ctx
    config = ConfigManager()
    account = config.get_account(name)
    return {
        "name": account.name,
        "username": account.username,
        "secret": "********",  # Always redacted
        "project_id": account.project_id,
        "region": account.region,
        "is_default": account.is_default,
    }


@mcp.tool
@handle_errors
def switch_account(ctx: Context, name: str) -> dict[str, str]:
    """Set a Mixpanel account as the default.

    Changes which account is used by default when no account is
    specified. This modifies ~/.mp/config.toml but does not change
    any credential values.

    Note: This only affects future operations. The current MCP session
    will continue using whatever account was active when it started.
    Restart the MCP server to use the new default.

    Args:
        ctx: FastMCP context (unused, required by MCP tool signature).
        name: Account name to set as default.

    Returns:
        Dictionary confirming the new default account.

    Raises:
        AccountNotFoundError: If the account doesn't exist.

    Example:
        ```python
        result = switch_account(ctx, name="staging")
        # {"default": "staging"}
        ```
    """
    _ = ctx
    config = ConfigManager()
    config.set_default(name)
    return {"default": name}


@mcp.tool
@handle_errors
def test_credentials(ctx: Context, account: str | None = None) -> dict[str, Any]:
    """Test Mixpanel account credentials by pinging the API.

    Validates that credentials are correct and can access the
    Mixpanel API. Uses a lightweight API call (list events) to
    verify authentication without consuming significant quota.

    Args:
        ctx: FastMCP context (unused, required by MCP tool signature).
        account: Optional account name to test. If None, tests the
            default account or environment variable credentials.

    Returns:
        Dictionary with success status, account name, project_id,
        region, and count of events found.

    Raises:
        AccountNotFoundError: If named account doesn't exist.
        AuthenticationError: If credentials are invalid.
        ConfigError: If no credentials can be resolved.

    Example:
        ```python
        result = test_credentials(ctx, account="production")
        # {"success": True, "account": "production",
        #  "project_id": "123456", "region": "us",
        #  "events_found": 42}
        ```
    """
    _ = ctx
    return Workspace.test_credentials(account=account)
