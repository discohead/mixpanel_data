"""Authentication and account management commands.

This module provides commands for managing Mixpanel accounts:
- list: List configured accounts
- add: Add a new account
- remove: Remove an account
- switch: Set default account
- show: Display account details
- test: Test account credentials
"""

from __future__ import annotations

from typing import Annotated

import typer

from mixpanel_data._internal.config import AccountInfo, ConfigManager
from mixpanel_data.cli.utils import (
    err_console,
    get_config,
    handle_errors,
    output_result,
)

auth_app = typer.Typer(
    name="auth",
    help="Manage authentication and accounts.",
    no_args_is_help=True,
)


@auth_app.command("list")
@handle_errors
def list_accounts(ctx: typer.Context) -> None:
    """List all configured accounts.

    Shows account name, username, project ID, region, and default status.
    """
    config = get_config(ctx)
    accounts = config.list_accounts()

    data = [
        {
            "name": acc.name,
            "username": acc.username,
            "project_id": acc.project_id,
            "region": acc.region,
            "is_default": acc.is_default,
        }
        for acc in accounts
    ]

    output_result(
        ctx, data, columns=["name", "username", "project_id", "region", "is_default"]
    )


@auth_app.command("add")
@handle_errors
def add_account(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Account name (identifier).")],
    username: Annotated[
        str | None,
        typer.Option("--username", "-u", help="Service account username."),
    ] = None,
    secret: Annotated[
        str | None,
        typer.Option("--secret", "-s", help="Service account secret."),
    ] = None,
    project: Annotated[
        str | None,
        typer.Option("--project", "-p", help="Project ID."),
    ] = None,
    region: Annotated[
        str,
        typer.Option("--region", "-r", help="Region: us, eu, or in."),
    ] = "us",
    default: Annotated[
        bool,
        typer.Option("--default", "-d", help="Set as default account."),
    ] = False,
    interactive: Annotated[
        bool,
        typer.Option("--interactive", "-i", help="Prompt for credentials."),
    ] = False,
) -> None:
    """Add a new account to the configuration.

    Credentials can be provided via options or interactively with --interactive.
    """
    # Handle interactive mode
    if interactive:
        if username is None:
            username = typer.prompt("Service account username")
        if secret is None:
            secret = typer.prompt("Service account secret", hide_input=True)
        if project is None:
            project = typer.prompt("Project ID")

    # Validate required fields
    if not username:
        err_console.print("[red]Error:[/red] --username is required")
        raise typer.Exit(3)
    if not secret:
        err_console.print("[red]Error:[/red] --secret is required")
        raise typer.Exit(3)
    if not project:
        err_console.print("[red]Error:[/red] --project is required")
        raise typer.Exit(3)
    if region not in ("us", "eu", "in"):
        err_console.print(
            f"[red]Error:[/red] Invalid region: {region}. Use us, eu, or in."
        )
        raise typer.Exit(3)

    config = get_config(ctx)
    config.add_account(
        name=name,
        username=username,
        secret=secret,
        project_id=project,
        region=region,
    )

    # Set as default if requested
    if default:
        config.set_default(name)

    output_result(ctx, {"added": name, "is_default": default})


@auth_app.command("remove")
@handle_errors
def remove_account(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Account name to remove.")],
    force: Annotated[
        bool,
        typer.Option("--force", help="Skip confirmation prompt."),
    ] = False,
) -> None:
    """Remove an account from the configuration."""
    if not force:
        confirm = typer.confirm(f"Remove account '{name}'?")
        if not confirm:
            err_console.print("[yellow]Cancelled[/yellow]")
            raise typer.Exit(2)

    config = get_config(ctx)
    config.remove_account(name)

    output_result(ctx, {"removed": name})


@auth_app.command("switch")
@handle_errors
def switch_account(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Account name to set as default.")],
) -> None:
    """Set an account as the default."""
    config = get_config(ctx)
    config.set_default(name)

    output_result(ctx, {"default": name})


def _find_default_account(config: ConfigManager) -> AccountInfo | None:
    """Find the default account from accounts list."""
    accounts = config.list_accounts()
    for acc in accounts:
        if acc.is_default:
            return acc
    return None


@auth_app.command("show")
@handle_errors
def show_account(
    ctx: typer.Context,
    name: Annotated[
        str | None,
        typer.Argument(help="Account name (default if omitted)."),
    ] = None,
) -> None:
    """Show account details (secret is redacted)."""
    config = get_config(ctx)

    account: AccountInfo
    if name is None:
        # Get default account
        default_account = _find_default_account(config)
        if default_account is None:
            err_console.print("[red]Error:[/red] No default account configured.")
            raise typer.Exit(1)
        account = default_account
    else:
        account = config.get_account(name)

    data = {
        "name": account.name,
        "username": account.username,
        "secret": "********",
        "project_id": account.project_id,
        "region": account.region,
        "is_default": account.is_default,
    }

    output_result(ctx, data)


@auth_app.command("test")
@handle_errors
def test_account(
    ctx: typer.Context,
    name: Annotated[
        str | None,
        typer.Argument(help="Account name to test (default if omitted)."),
    ] = None,
) -> None:
    """Test account credentials by pinging the API.

    Verifies that the credentials are valid and can access the project.
    """
    from mixpanel_data._internal.api_client import MixpanelAPIClient

    config = get_config(ctx)

    account: AccountInfo
    if name is None:
        default_account = _find_default_account(config)
        if default_account is None:
            err_console.print("[red]Error:[/red] No default account configured.")
            raise typer.Exit(1)
        account = default_account
    else:
        account = config.get_account(name)

    # Resolve credentials (includes secret)
    credentials = config.resolve_credentials(account.name)

    client = MixpanelAPIClient(credentials)

    # Make a simple API call to test credentials
    # Use list_events as a lightweight test endpoint
    try:
        events = client.get_events()
        event_count = len(list(events)) if events else 0

        output_result(
            ctx,
            {
                "success": True,
                "account": account.name,
                "project_id": account.project_id,
                "region": account.region,
                "events_found": event_count,
            },
        )
    except Exception as e:
        output_result(
            ctx,
            {
                "success": False,
                "account": account.name,
                "error": str(e),
            },
        )
        raise typer.Exit(1) from None
