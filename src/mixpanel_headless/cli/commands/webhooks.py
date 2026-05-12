"""Webhook management commands.

This module provides commands for managing Mixpanel project webhooks:

- list: List all project webhooks
- create: Create a new webhook
- update: Update an existing webhook
- delete: Delete a webhook
- test: Test webhook connectivity
"""

from __future__ import annotations

from typing import Annotated, Any

import typer

from mixpanel_headless.cli.options import FormatOption, JqOption
from mixpanel_headless.cli.utils import (
    err_console,
    get_workspace,
    handle_errors,
    output_result,
    status_spinner,
)

webhooks_app = typer.Typer(
    name="webhooks",
    help="Manage project webhooks.",
    no_args_is_help=True,
)


# =============================================================================
# Basic CRUD
# =============================================================================


@webhooks_app.command("list")
@handle_errors
def webhooks_list(
    ctx: typer.Context,
    format: FormatOption = "json",
    jq_filter: JqOption = None,
) -> None:
    """List all project webhooks.

    Retrieves all webhooks configured for the current project.

    Args:
        ctx: Typer context with global options.
        format: Output format.
        jq_filter: Optional jq filter expression.
    """
    workspace = get_workspace(ctx)
    with status_spinner(ctx, "Fetching webhooks..."):
        result = workspace.list_webhooks()
    output_result(
        ctx,
        [wh.model_dump() for wh in result],
        format=format,
        jq_filter=jq_filter,
    )


@webhooks_app.command("create")
@handle_errors
def webhooks_create(
    ctx: typer.Context,
    name: Annotated[
        str,
        typer.Option("--name", help="Webhook name."),
    ],
    url: Annotated[
        str,
        typer.Option("--url", help="Webhook URL."),
    ],
    auth_type: Annotated[
        str | None,
        typer.Option("--auth-type", help="Auth type (e.g. 'basic')."),
    ] = None,
    username: Annotated[
        str | None,
        typer.Option("--username", help="Basic auth username."),
    ] = None,
    password: Annotated[
        str | None,
        typer.Option("--password", help="Basic auth password."),
    ] = None,
    format: FormatOption = "json",
    jq_filter: JqOption = None,
) -> None:
    """Create a new webhook.

    Creates a webhook with the specified name and URL. Optional
    authentication parameters can be provided for secured endpoints.

    Args:
        ctx: Typer context with global options.
        name: Webhook name (required).
        url: Webhook URL (required).
        auth_type: Authentication type (e.g. 'basic').
        username: Basic auth username.
        password: Basic auth password.
        format: Output format.
        jq_filter: Optional jq filter expression.
    """
    from mixpanel_headless.types import CreateWebhookParams

    kwargs: dict[str, Any] = {"name": name, "url": url}
    if auth_type is not None:
        kwargs["auth_type"] = auth_type
    if username is not None:
        kwargs["username"] = username
    if password is not None:
        kwargs["password"] = password

    params = CreateWebhookParams(**kwargs)
    workspace = get_workspace(ctx)
    with status_spinner(ctx, "Creating webhook..."):
        result = workspace.create_webhook(params)
    output_result(ctx, result.model_dump(), format=format, jq_filter=jq_filter)


@webhooks_app.command("update")
@handle_errors
def webhooks_update(
    ctx: typer.Context,
    webhook_id: Annotated[
        str,
        typer.Argument(help="Webhook ID (UUID)."),
    ],
    name: Annotated[
        str | None,
        typer.Option("--name", help="New webhook name."),
    ] = None,
    url: Annotated[
        str | None,
        typer.Option("--url", help="New webhook URL."),
    ] = None,
    auth_type: Annotated[
        str | None,
        typer.Option("--auth-type", help="New auth type."),
    ] = None,
    username: Annotated[
        str | None,
        typer.Option("--username", help="New basic auth username."),
    ] = None,
    password: Annotated[
        str | None,
        typer.Option("--password", help="New basic auth password."),
    ] = None,
    enabled: Annotated[
        bool | None,
        typer.Option("--enabled/--no-enabled", help="Enable or disable webhook."),
    ] = None,
    format: FormatOption = "json",
    jq_filter: JqOption = None,
) -> None:
    """Update an existing webhook.

    Updates webhook fields using PATCH semantics. Only provided
    fields are modified.

    Args:
        ctx: Typer context with global options.
        webhook_id: Webhook UUID string.
        name: New webhook name.
        url: New webhook URL.
        auth_type: New authentication type.
        username: New basic auth username.
        password: New basic auth password.
        enabled: Enable or disable the webhook.
        format: Output format.
        jq_filter: Optional jq filter expression.
    """
    from mixpanel_headless.types import UpdateWebhookParams

    kwargs: dict[str, Any] = {}
    if name is not None:
        kwargs["name"] = name
    if url is not None:
        kwargs["url"] = url
    if auth_type is not None:
        kwargs["auth_type"] = auth_type
    if username is not None:
        kwargs["username"] = username
    if password is not None:
        kwargs["password"] = password
    if enabled is not None:
        kwargs["is_enabled"] = enabled

    params = UpdateWebhookParams(**kwargs)
    workspace = get_workspace(ctx)
    with status_spinner(ctx, "Updating webhook..."):
        result = workspace.update_webhook(webhook_id, params)
    output_result(ctx, result.model_dump(), format=format, jq_filter=jq_filter)


@webhooks_app.command("delete")
@handle_errors
def webhooks_delete(
    ctx: typer.Context,
    webhook_id: Annotated[
        str,
        typer.Argument(help="Webhook ID (UUID)."),
    ],
) -> None:
    """Delete a webhook.

    Permanently deletes a webhook by ID. This action cannot be undone.

    Args:
        ctx: Typer context with global options.
        webhook_id: Webhook UUID string.
    """
    workspace = get_workspace(ctx)
    with status_spinner(ctx, "Deleting webhook..."):
        workspace.delete_webhook(webhook_id)
    err_console.print(f"[green]Deleted webhook {webhook_id}.[/green]")


@webhooks_app.command("test")
@handle_errors
def webhooks_test(
    ctx: typer.Context,
    url: Annotated[
        str,
        typer.Option("--url", help="Webhook URL to test."),
    ],
    name: Annotated[
        str | None,
        typer.Option("--name", help="Webhook name."),
    ] = None,
    auth_type: Annotated[
        str | None,
        typer.Option("--auth-type", help="Auth type."),
    ] = None,
    username: Annotated[
        str | None,
        typer.Option("--username", help="Basic auth username."),
    ] = None,
    password: Annotated[
        str | None,
        typer.Option("--password", help="Basic auth password."),
    ] = None,
    format: FormatOption = "json",
    jq_filter: JqOption = None,
) -> None:
    """Test webhook connectivity.

    Sends a test request to the specified URL and reports the result.

    Args:
        ctx: Typer context with global options.
        url: Webhook URL to test (required).
        name: Optional webhook name.
        auth_type: Authentication type.
        username: Basic auth username.
        password: Basic auth password.
        format: Output format.
        jq_filter: Optional jq filter expression.
    """
    from mixpanel_headless.types import WebhookTestParams

    kwargs: dict[str, Any] = {"url": url}
    if name is not None:
        kwargs["name"] = name
    if auth_type is not None:
        kwargs["auth_type"] = auth_type
    if username is not None:
        kwargs["username"] = username
    if password is not None:
        kwargs["password"] = password

    params = WebhookTestParams(**kwargs)
    workspace = get_workspace(ctx)
    with status_spinner(ctx, "Testing webhook..."):
        result = workspace.test_webhook(params)
    output_result(ctx, result.model_dump(), format=format, jq_filter=jq_filter)
