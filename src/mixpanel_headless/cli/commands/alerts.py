"""Custom alert management commands.

This module provides commands for managing Mixpanel custom alerts:

Basic CRUD:
- list: List custom alerts
- create: Create a new custom alert
- get: Get a single alert by ID
- update: Update an existing alert
- delete: Delete a custom alert
- bulk-delete: Bulk-delete alerts by IDs

Monitoring:
- count: Get alert count and limits
- history: View trigger history for an alert
- test: Send a test alert notification
- screenshot: Get a signed URL for an alert screenshot
- validate: Validate alerts against a bookmark
"""

from __future__ import annotations

import json
from typing import Annotated, Any

import typer

from mixpanel_headless.cli.options import FormatOption, JqOption
from mixpanel_headless.cli.utils import (
    ExitCode,
    err_console,
    get_workspace,
    handle_errors,
    output_result,
    status_spinner,
)

alerts_app = typer.Typer(
    name="alerts",
    help="Manage Mixpanel custom alerts.",
    no_args_is_help=True,
)


# =============================================================================
# Basic CRUD
# =============================================================================


@alerts_app.command("list")
@handle_errors
def alerts_list(
    ctx: typer.Context,
    bookmark_id: Annotated[
        int | None,
        typer.Option("--bookmark-id", help="Filter by linked bookmark ID."),
    ] = None,
    skip_user_filter: Annotated[
        bool,
        typer.Option("--skip-user-filter", help="List alerts for all users."),
    ] = False,
    format: FormatOption = "json",
    jq_filter: JqOption = None,
) -> None:
    """List custom alerts for the current project.

    Retrieves all custom alerts visible to the authenticated user.
    Optionally filter by linked bookmark or list alerts for all users.

    Args:
        ctx: Typer context with global options.
        bookmark_id: Filter by linked bookmark ID.
        skip_user_filter: Whether to list alerts for all users.
        format: Output format.
        jq_filter: Optional jq filter expression.
    """
    workspace = get_workspace(ctx)
    kwargs: dict[str, Any] = {}
    if bookmark_id is not None:
        kwargs["bookmark_id"] = bookmark_id
    if skip_user_filter:
        kwargs["skip_user_filter"] = True
    with status_spinner(ctx, "Fetching alerts..."):
        result = workspace.list_alerts(**kwargs)
    output_result(
        ctx,
        [a.model_dump() for a in result],
        format=format,
        jq_filter=jq_filter,
    )


@alerts_app.command("create")
@handle_errors
def alerts_create(
    ctx: typer.Context,
    bookmark_id: Annotated[
        int,
        typer.Option("--bookmark-id", help="Linked bookmark ID (required)."),
    ],
    name: Annotated[
        str,
        typer.Option("--name", help="Alert name (required)."),
    ],
    condition: Annotated[
        str,
        typer.Option(
            "--condition", help="Trigger condition as JSON string (required)."
        ),
    ],
    frequency: Annotated[
        int,
        typer.Option("--frequency", help="Check frequency in seconds (required)."),
    ],
    paused: Annotated[
        bool,
        typer.Option("--paused/--no-paused", help="Start paused or active."),
    ] = False,
    subscriptions: Annotated[
        str | None,
        typer.Option("--subscriptions", help="Notification targets as JSON string."),
    ] = None,
    notification_windows: Annotated[
        str | None,
        typer.Option(
            "--notification-windows", help="Notification windows as JSON string."
        ),
    ] = None,
    format: FormatOption = "json",
    jq_filter: JqOption = None,
) -> None:
    """Create a new custom alert.

    Creates a custom alert linked to a saved report (bookmark).
    The condition, subscriptions, and notification-windows options
    accept JSON strings.

    Args:
        ctx: Typer context with global options.
        bookmark_id: Linked bookmark ID.
        name: Alert name.
        condition: Trigger condition as JSON string.
        frequency: Check frequency in seconds.
        paused: Whether to start paused.
        subscriptions: Notification targets as JSON string.
        notification_windows: Notification windows as JSON string.
        format: Output format.
        jq_filter: Optional jq filter expression.
    """
    from mixpanel_headless.types import CreateAlertParams

    try:
        parsed_condition: dict[str, Any] = json.loads(condition)
    except json.JSONDecodeError as exc:
        err_console.print(f"[red]Invalid JSON for --condition:[/red] {exc}")
        raise typer.Exit(code=ExitCode.INVALID_ARGS) from None

    parsed_subscriptions: list[dict[str, Any]] = []
    if subscriptions is not None:
        try:
            parsed_subscriptions = json.loads(subscriptions)
        except json.JSONDecodeError as exc:
            err_console.print(f"[red]Invalid JSON for --subscriptions:[/red] {exc}")
            raise typer.Exit(code=ExitCode.INVALID_ARGS) from None

    kwargs: dict[str, Any] = {
        "bookmark_id": bookmark_id,
        "name": name,
        "condition": parsed_condition,
        "frequency": frequency,
        "paused": paused,
        "subscriptions": parsed_subscriptions,
    }

    if notification_windows is not None:
        try:
            kwargs["notification_windows"] = json.loads(notification_windows)
        except json.JSONDecodeError as exc:
            err_console.print(
                f"[red]Invalid JSON for --notification-windows:[/red] {exc}"
            )
            raise typer.Exit(code=ExitCode.INVALID_ARGS) from None

    params = CreateAlertParams(**kwargs)
    workspace = get_workspace(ctx)
    with status_spinner(ctx, "Creating alert..."):
        result = workspace.create_alert(params)
    output_result(ctx, result.model_dump(), format=format, jq_filter=jq_filter)


@alerts_app.command("get")
@handle_errors
def alerts_get(
    ctx: typer.Context,
    alert_id: Annotated[
        int,
        typer.Argument(help="Alert ID."),
    ],
    format: FormatOption = "json",
    jq_filter: JqOption = None,
) -> None:
    """Get a single custom alert by ID.

    Retrieves the full alert object including condition, subscriptions,
    and metadata.

    Args:
        ctx: Typer context with global options.
        alert_id: Alert ID (integer).
        format: Output format.
        jq_filter: Optional jq filter expression.
    """
    workspace = get_workspace(ctx)
    with status_spinner(ctx, "Fetching alert..."):
        result = workspace.get_alert(alert_id)
    output_result(ctx, result.model_dump(), format=format, jq_filter=jq_filter)


@alerts_app.command("update")
@handle_errors
def alerts_update(
    ctx: typer.Context,
    alert_id: Annotated[
        int,
        typer.Argument(help="Alert ID."),
    ],
    name: Annotated[
        str | None,
        typer.Option("--name", help="New alert name."),
    ] = None,
    bookmark_id: Annotated[
        int | None,
        typer.Option("--bookmark-id", help="New linked bookmark ID."),
    ] = None,
    condition: Annotated[
        str | None,
        typer.Option("--condition", help="New condition as JSON string."),
    ] = None,
    frequency: Annotated[
        int | None,
        typer.Option("--frequency", help="New check frequency in seconds."),
    ] = None,
    paused: Annotated[
        bool | None,
        typer.Option("--paused/--no-paused", help="Pause or unpause alert."),
    ] = None,
    subscriptions: Annotated[
        str | None,
        typer.Option(
            "--subscriptions", help="New notification targets as JSON string."
        ),
    ] = None,
    notification_windows: Annotated[
        str | None,
        typer.Option(
            "--notification-windows", help="New notification windows as JSON string."
        ),
    ] = None,
    format: FormatOption = "json",
    jq_filter: JqOption = None,
) -> None:
    """Update an existing custom alert (PATCH semantics).

    Only fields provided will be updated. Accepts JSON strings for
    condition, subscriptions, and notification-windows.

    Args:
        ctx: Typer context with global options.
        alert_id: Alert ID (integer).
        name: New alert name.
        bookmark_id: New linked bookmark ID.
        condition: New condition as JSON string.
        frequency: New check frequency in seconds.
        paused: Pause or unpause alert.
        subscriptions: New notification targets as JSON string.
        notification_windows: New notification windows as JSON string.
        format: Output format.
        jq_filter: Optional jq filter expression.
    """
    from mixpanel_headless.types import UpdateAlertParams

    kwargs: dict[str, Any] = {}
    if name is not None:
        kwargs["name"] = name
    if bookmark_id is not None:
        kwargs["bookmark_id"] = bookmark_id
    if condition is not None:
        try:
            kwargs["condition"] = json.loads(condition)
        except json.JSONDecodeError as exc:
            err_console.print(f"[red]Invalid JSON for --condition:[/red] {exc}")
            raise typer.Exit(code=ExitCode.INVALID_ARGS) from None
    if frequency is not None:
        kwargs["frequency"] = frequency
    if paused is not None:
        kwargs["paused"] = paused
    if subscriptions is not None:
        try:
            kwargs["subscriptions"] = json.loads(subscriptions)
        except json.JSONDecodeError as exc:
            err_console.print(f"[red]Invalid JSON for --subscriptions:[/red] {exc}")
            raise typer.Exit(code=ExitCode.INVALID_ARGS) from None
    if notification_windows is not None:
        try:
            kwargs["notification_windows"] = json.loads(notification_windows)
        except json.JSONDecodeError as exc:
            err_console.print(
                f"[red]Invalid JSON for --notification-windows:[/red] {exc}"
            )
            raise typer.Exit(code=ExitCode.INVALID_ARGS) from None

    params = UpdateAlertParams(**kwargs)
    workspace = get_workspace(ctx)
    with status_spinner(ctx, "Updating alert..."):
        result = workspace.update_alert(alert_id, params)
    output_result(ctx, result.model_dump(), format=format, jq_filter=jq_filter)


@alerts_app.command("delete")
@handle_errors
def alerts_delete(
    ctx: typer.Context,
    alert_id: Annotated[
        int,
        typer.Argument(help="Alert ID."),
    ],
) -> None:
    """Delete a custom alert.

    Permanently deletes a custom alert by ID. This action cannot be undone.

    Args:
        ctx: Typer context with global options.
        alert_id: Alert ID (integer).
    """
    workspace = get_workspace(ctx)
    with status_spinner(ctx, "Deleting alert..."):
        workspace.delete_alert(alert_id)
    err_console.print(f"[green]Deleted alert {alert_id}.[/green]")


@alerts_app.command("bulk-delete")
@handle_errors
def alerts_bulk_delete(
    ctx: typer.Context,
    ids: Annotated[
        str,
        typer.Option("--ids", help="Comma-separated alert IDs to delete."),
    ],
) -> None:
    """Bulk-delete custom alerts by IDs.

    Permanently deletes multiple alerts. Provide IDs as a
    comma-separated string.

    Args:
        ctx: Typer context with global options.
        ids: Comma-separated alert IDs.
    """
    try:
        id_list = [int(x.strip()) for x in ids.split(",") if x.strip()]
    except ValueError as exc:
        err_console.print(f"[red]Invalid alert IDs:[/red] {exc}")
        raise typer.Exit(code=ExitCode.INVALID_ARGS) from None

    if not id_list:
        err_console.print("[red]No valid alert IDs provided.[/red]")
        raise typer.Exit(code=ExitCode.INVALID_ARGS) from None

    workspace = get_workspace(ctx)
    with status_spinner(ctx, "Deleting alerts..."):
        workspace.bulk_delete_alerts(id_list)
    err_console.print(f"[green]Deleted {len(id_list)} alert(s).[/green]")


# =============================================================================
# Monitoring
# =============================================================================


@alerts_app.command("count")
@handle_errors
def alerts_count(
    ctx: typer.Context,
    alert_type: Annotated[
        str | None,
        typer.Option("--type", help="Filter by alert type."),
    ] = None,
    format: FormatOption = "json",
    jq_filter: JqOption = None,
) -> None:
    """Get alert count and limits.

    Retrieves the current alert count, account limit, and whether
    the account is below its limit.

    Args:
        ctx: Typer context with global options.
        alert_type: Filter by alert type.
        format: Output format.
        jq_filter: Optional jq filter expression.
    """
    workspace = get_workspace(ctx)
    with status_spinner(ctx, "Fetching alert count..."):
        result = workspace.get_alert_count(alert_type=alert_type)
    output_result(ctx, result.model_dump(), format=format, jq_filter=jq_filter)


@alerts_app.command("history")
@handle_errors
def alerts_history(
    ctx: typer.Context,
    alert_id: Annotated[
        int,
        typer.Argument(help="Alert ID."),
    ],
    page_size: Annotated[
        int | None,
        typer.Option("--page-size", help="Results per page."),
    ] = None,
    cursor: Annotated[
        str | None,
        typer.Option("--cursor", help="Pagination cursor for next page."),
    ] = None,
    format: FormatOption = "json",
    jq_filter: JqOption = None,
) -> None:
    """View trigger history for a custom alert.

    Retrieves the paginated trigger history for the specified alert.

    Args:
        ctx: Typer context with global options.
        alert_id: Alert ID (integer).
        page_size: Number of results per page.
        cursor: Pagination cursor for next page.
        format: Output format.
        jq_filter: Optional jq filter expression.
    """
    workspace = get_workspace(ctx)
    with status_spinner(ctx, "Fetching alert history..."):
        result = workspace.get_alert_history(
            alert_id, page_size=page_size, next_cursor=cursor
        )
    output_result(ctx, result.model_dump(), format=format, jq_filter=jq_filter)


@alerts_app.command("test")
@handle_errors
def alerts_test(
    ctx: typer.Context,
    bookmark_id: Annotated[
        int,
        typer.Option("--bookmark-id", help="Linked bookmark ID."),
    ],
    name: Annotated[
        str,
        typer.Option("--name", help="Alert name."),
    ],
    condition: Annotated[
        str,
        typer.Option("--condition", help="Trigger condition as JSON string."),
    ],
    frequency: Annotated[
        int,
        typer.Option("--frequency", help="Check frequency in seconds."),
    ],
    subscriptions: Annotated[
        str | None,
        typer.Option("--subscriptions", help="Notification targets as JSON string."),
    ] = None,
    format: FormatOption = "json",
    jq_filter: JqOption = None,
) -> None:
    """Send a test alert notification.

    Sends a test notification using the provided alert parameters
    without actually creating the alert.

    Args:
        ctx: Typer context with global options.
        bookmark_id: Linked bookmark ID.
        name: Alert name.
        condition: Trigger condition as JSON string.
        frequency: Check frequency in seconds.
        subscriptions: Notification targets as JSON string.
        format: Output format.
        jq_filter: Optional jq filter expression.
    """
    from mixpanel_headless.types import CreateAlertParams

    try:
        parsed_condition: dict[str, Any] = json.loads(condition)
    except json.JSONDecodeError as exc:
        err_console.print(f"[red]Invalid JSON for --condition:[/red] {exc}")
        raise typer.Exit(code=ExitCode.INVALID_ARGS) from None

    parsed_subscriptions: list[dict[str, Any]] = []
    if subscriptions is not None:
        try:
            parsed_subscriptions = json.loads(subscriptions)
        except json.JSONDecodeError as exc:
            err_console.print(f"[red]Invalid JSON for --subscriptions:[/red] {exc}")
            raise typer.Exit(code=ExitCode.INVALID_ARGS) from None

    params = CreateAlertParams(
        bookmark_id=bookmark_id,
        name=name,
        condition=parsed_condition,
        frequency=frequency,
        paused=False,
        subscriptions=parsed_subscriptions,
    )
    workspace = get_workspace(ctx)
    with status_spinner(ctx, "Sending test alert..."):
        result = workspace.test_alert(params)
    output_result(ctx, result, format=format, jq_filter=jq_filter)


@alerts_app.command("screenshot")
@handle_errors
def alerts_screenshot(
    ctx: typer.Context,
    gcs_key: Annotated[
        str,
        typer.Option("--gcs-key", help="GCS object key for the screenshot."),
    ],
    format: FormatOption = "json",
    jq_filter: JqOption = None,
) -> None:
    """Get a signed URL for an alert screenshot.

    Retrieves a signed GCS URL that can be used to view the
    alert screenshot image.

    Args:
        ctx: Typer context with global options.
        gcs_key: GCS object key for the screenshot.
        format: Output format.
        jq_filter: Optional jq filter expression.
    """
    workspace = get_workspace(ctx)
    with status_spinner(ctx, "Fetching screenshot URL..."):
        result = workspace.get_alert_screenshot_url(gcs_key)
    output_result(ctx, result.model_dump(), format=format, jq_filter=jq_filter)


@alerts_app.command("validate")
@handle_errors
def alerts_validate(
    ctx: typer.Context,
    alert_ids: Annotated[
        str,
        typer.Option("--alert-ids", help="Comma-separated alert IDs to validate."),
    ],
    bookmark_type: Annotated[
        str,
        typer.Option("--bookmark-type", help="Bookmark type to validate against."),
    ],
    bookmark_params: Annotated[
        str,
        typer.Option("--bookmark-params", help="Bookmark params as JSON string."),
    ],
    format: FormatOption = "json",
    jq_filter: JqOption = None,
) -> None:
    """Validate alerts against a bookmark configuration.

    Checks whether the specified alerts are compatible with the
    given bookmark type and parameters.

    Args:
        ctx: Typer context with global options.
        alert_ids: Comma-separated alert IDs.
        bookmark_type: Bookmark type to validate against.
        bookmark_params: Bookmark params as JSON string.
        format: Output format.
        jq_filter: Optional jq filter expression.
    """
    from mixpanel_headless.types import ValidateAlertsForBookmarkParams

    try:
        id_list = [int(x.strip()) for x in alert_ids.split(",") if x.strip()]
    except ValueError as exc:
        err_console.print(f"[red]Invalid alert IDs:[/red] {exc}")
        raise typer.Exit(code=ExitCode.INVALID_ARGS) from None

    if not id_list:
        err_console.print("[red]No valid alert IDs provided.[/red]")
        raise typer.Exit(code=ExitCode.INVALID_ARGS) from None

    try:
        parsed_params: dict[str, Any] = json.loads(bookmark_params)
    except json.JSONDecodeError as exc:
        err_console.print(f"[red]Invalid JSON for --bookmark-params:[/red] {exc}")
        raise typer.Exit(code=ExitCode.INVALID_ARGS) from None

    params = ValidateAlertsForBookmarkParams(
        alert_ids=id_list,
        bookmark_type=bookmark_type,
        bookmark_params=parsed_params,
    )
    workspace = get_workspace(ctx)
    with status_spinner(ctx, "Validating alerts..."):
        result = workspace.validate_alerts_for_bookmark(params)
    output_result(ctx, result.model_dump(), format=format, jq_filter=jq_filter)
