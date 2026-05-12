"""Drop filter management commands.

This module provides commands for managing Mixpanel drop filters:

- list: List all drop filters
- create: Create a new drop filter
- update: Update an existing drop filter
- delete: Delete a drop filter
- limits: Get drop filter usage limits
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

drop_filters_app = typer.Typer(
    name="drop-filters",
    help="Manage drop filters.",
    no_args_is_help=True,
)


@drop_filters_app.command("list")
@handle_errors
def drop_filters_list(
    ctx: typer.Context,
    format: FormatOption = "json",
    jq_filter: JqOption = None,
) -> None:
    """List all drop filters for the current project.

    Retrieves all drop filters configured for the project.

    Args:
        ctx: Typer context with global options.
        format: Output format.
        jq_filter: Optional jq filter expression.
    """
    workspace = get_workspace(ctx)
    with status_spinner(ctx, "Fetching drop filters..."):
        result = workspace.list_drop_filters()
    output_result(
        ctx,
        [f.model_dump() for f in result],
        format=format,
        jq_filter=jq_filter,
    )


@drop_filters_app.command("create")
@handle_errors
def drop_filters_create(
    ctx: typer.Context,
    event_name: Annotated[
        str,
        typer.Option("--event-name", help="Event name to filter (required)."),
    ],
    filters: Annotated[
        str,
        typer.Option("--filters", help="Filter condition as JSON string (required)."),
    ],
    format: FormatOption = "json",
    jq_filter: JqOption = None,
) -> None:
    """Create a new drop filter.

    Creates a drop filter for the specified event with the given
    filter conditions. Returns the full list of drop filters after creation.

    Args:
        ctx: Typer context with global options.
        event_name: Event name to filter.
        filters: Filter condition as JSON string.
        format: Output format.
        jq_filter: Optional jq filter expression.
    """
    from mixpanel_headless.types import CreateDropFilterParams

    try:
        parsed_filters: Any = json.loads(filters)
    except json.JSONDecodeError as exc:
        err_console.print(f"[red]Invalid JSON for --filters:[/red] {exc}")
        raise typer.Exit(code=ExitCode.INVALID_ARGS) from None

    params = CreateDropFilterParams(
        event_name=event_name,
        filters=parsed_filters,
    )
    workspace = get_workspace(ctx)
    with status_spinner(ctx, "Creating drop filter..."):
        result = workspace.create_drop_filter(params)
    output_result(
        ctx,
        [f.model_dump() for f in result],
        format=format,
        jq_filter=jq_filter,
    )


@drop_filters_app.command("update")
@handle_errors
def drop_filters_update(
    ctx: typer.Context,
    id: Annotated[
        int,
        typer.Option("--id", help="Drop filter ID (required)."),
    ],
    event_name: Annotated[
        str | None,
        typer.Option("--event-name", help="New event name."),
    ] = None,
    filters: Annotated[
        str | None,
        typer.Option("--filters", help="New filter condition as JSON string."),
    ] = None,
    active: Annotated[
        bool | None,
        typer.Option("--active/--no-active", help="Enable or disable the filter."),
    ] = None,
    format: FormatOption = "json",
    jq_filter: JqOption = None,
) -> None:
    """Update an existing drop filter.

    Updates a drop filter by ID. Only provided fields are changed.
    Returns the full list of drop filters after update.

    Args:
        ctx: Typer context with global options.
        id: Drop filter ID.
        event_name: New event name.
        filters: New filter condition as JSON string.
        active: Enable or disable the filter.
        format: Output format.
        jq_filter: Optional jq filter expression.
    """
    from mixpanel_headless.types import UpdateDropFilterParams

    kwargs: dict[str, Any] = {"id": id}
    if event_name is not None:
        kwargs["event_name"] = event_name
    if filters is not None:
        try:
            kwargs["filters"] = json.loads(filters)
        except json.JSONDecodeError as exc:
            err_console.print(f"[red]Invalid JSON for --filters:[/red] {exc}")
            raise typer.Exit(code=ExitCode.INVALID_ARGS) from None
    if active is not None:
        kwargs["active"] = active

    params = UpdateDropFilterParams(**kwargs)
    workspace = get_workspace(ctx)
    with status_spinner(ctx, "Updating drop filter..."):
        result = workspace.update_drop_filter(params)
    output_result(
        ctx,
        [f.model_dump() for f in result],
        format=format,
        jq_filter=jq_filter,
    )


@drop_filters_app.command("delete")
@handle_errors
def drop_filters_delete(
    ctx: typer.Context,
    id: Annotated[
        int,
        typer.Option("--id", help="Drop filter ID (required)."),
    ],
    format: FormatOption = "json",
    jq_filter: JqOption = None,
) -> None:
    """Delete a drop filter.

    Permanently deletes a drop filter by ID. Returns the remaining
    list of drop filters.

    Args:
        ctx: Typer context with global options.
        id: Drop filter ID.
        format: Output format.
        jq_filter: Optional jq filter expression.
    """
    workspace = get_workspace(ctx)
    with status_spinner(ctx, "Deleting drop filter..."):
        result = workspace.delete_drop_filter(id)
    output_result(
        ctx,
        [f.model_dump() for f in result],
        format=format,
        jq_filter=jq_filter,
    )


@drop_filters_app.command("limits")
@handle_errors
def drop_filters_limits(
    ctx: typer.Context,
    format: FormatOption = "json",
    jq_filter: JqOption = None,
) -> None:
    """Get drop filter usage limits.

    Retrieves the current count and maximum allowed drop filters
    for the project.

    Args:
        ctx: Typer context with global options.
        format: Output format.
        jq_filter: Optional jq filter expression.
    """
    workspace = get_workspace(ctx)
    with status_spinner(ctx, "Fetching drop filter limits..."):
        result = workspace.get_drop_filter_limits()
    output_result(ctx, result.model_dump(), format=format, jq_filter=jq_filter)
