"""Annotation management commands.

This module provides commands for managing Mixpanel timeline annotations:

Basic CRUD:
- list: List annotations with optional date/tag filters
- create: Create a new annotation
- get: Get a single annotation by ID
- update: Update an existing annotation
- delete: Delete an annotation

Tags:
- tags list: List annotation tags
- tags create: Create a new annotation tag
"""

from __future__ import annotations

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

annotations_app = typer.Typer(
    name="annotations",
    help="Manage timeline annotations.",
    no_args_is_help=True,
)

tags_app = typer.Typer(
    name="tags",
    help="Manage annotation tags.",
    no_args_is_help=True,
)
annotations_app.add_typer(tags_app, name="tags")


# =============================================================================
# Basic CRUD
# =============================================================================


@annotations_app.command("list")
@handle_errors
def annotations_list(
    ctx: typer.Context,
    from_date: Annotated[
        str | None,
        typer.Option("--from", help="Start date filter (ISO format)."),
    ] = None,
    to_date: Annotated[
        str | None,
        typer.Option("--to", help="End date filter (ISO format)."),
    ] = None,
    tags: Annotated[
        str | None,
        typer.Option("--tags", help="Comma-separated tag IDs to filter by."),
    ] = None,
    format: FormatOption = "json",
    jq_filter: JqOption = None,
) -> None:
    """List timeline annotations.

    Retrieves annotations for the project, optionally filtered by
    date range or tag IDs.

    Args:
        ctx: Typer context with global options.
        from_date: Start date filter (ISO format).
        to_date: End date filter (ISO format).
        tags: Comma-separated tag IDs.
        format: Output format.
        jq_filter: Optional jq filter expression.
    """
    tag_ids: list[int] | None = None
    if tags:
        try:
            tag_ids = [int(t.strip()) for t in tags.split(",") if t.strip()]
        except ValueError as exc:
            err_console.print(f"[red]Invalid tag IDs:[/red] {exc}")
            raise typer.Exit(code=ExitCode.INVALID_ARGS) from None

    workspace = get_workspace(ctx)
    with status_spinner(ctx, "Fetching annotations..."):
        result = workspace.list_annotations(
            from_date=from_date, to_date=to_date, tags=tag_ids
        )
    output_result(
        ctx,
        [a.model_dump() for a in result],
        format=format,
        jq_filter=jq_filter,
    )


@annotations_app.command("create")
@handle_errors
def annotations_create(
    ctx: typer.Context,
    date: Annotated[
        str,
        typer.Option("--date", help="Annotation date (ISO format, required)."),
    ],
    description: Annotated[
        str,
        typer.Option("--description", help="Annotation text (required)."),
    ],
    tags: Annotated[
        str | None,
        typer.Option("--tags", help="Comma-separated tag IDs to associate."),
    ] = None,
    user_id: Annotated[
        int | None,
        typer.Option("--user-id", help="Creator user ID."),
    ] = None,
    format: FormatOption = "json",
    jq_filter: JqOption = None,
) -> None:
    """Create a new timeline annotation.

    Creates an annotation at the specified date with the given description.
    Optionally associate tag IDs and a creator user ID.

    Args:
        ctx: Typer context with global options.
        date: Annotation date (ISO format, required).
        description: Annotation text (required).
        tags: Comma-separated tag IDs.
        user_id: Creator user ID.
        format: Output format.
        jq_filter: Optional jq filter expression.
    """
    from mixpanel_headless.types import CreateAnnotationParams

    kwargs: dict[str, Any] = {"date": date, "description": description}
    if tags is not None:
        try:
            kwargs["tags"] = [int(t.strip()) for t in tags.split(",") if t.strip()]
        except ValueError as exc:
            err_console.print(f"[red]Invalid tag IDs:[/red] {exc}")
            raise typer.Exit(code=ExitCode.INVALID_ARGS) from None
    if user_id is not None:
        kwargs["user_id"] = user_id

    params = CreateAnnotationParams(**kwargs)
    workspace = get_workspace(ctx)
    with status_spinner(ctx, "Creating annotation..."):
        result = workspace.create_annotation(params)
    output_result(ctx, result.model_dump(), format=format, jq_filter=jq_filter)


@annotations_app.command("get")
@handle_errors
def annotations_get(
    ctx: typer.Context,
    annotation_id: Annotated[
        int,
        typer.Argument(help="Annotation ID."),
    ],
    format: FormatOption = "json",
    jq_filter: JqOption = None,
) -> None:
    """Get a single annotation by ID.

    Retrieves the full annotation object including tags and user info.

    Args:
        ctx: Typer context with global options.
        annotation_id: Annotation identifier.
        format: Output format.
        jq_filter: Optional jq filter expression.
    """
    workspace = get_workspace(ctx)
    with status_spinner(ctx, "Fetching annotation..."):
        result = workspace.get_annotation(annotation_id)
    output_result(ctx, result.model_dump(), format=format, jq_filter=jq_filter)


@annotations_app.command("update")
@handle_errors
def annotations_update(
    ctx: typer.Context,
    annotation_id: Annotated[
        int,
        typer.Argument(help="Annotation ID."),
    ],
    description: Annotated[
        str | None,
        typer.Option("--description", help="New description."),
    ] = None,
    tags: Annotated[
        str | None,
        typer.Option("--tags", help="Comma-separated tag IDs (replaces existing)."),
    ] = None,
    format: FormatOption = "json",
    jq_filter: JqOption = None,
) -> None:
    """Update an existing annotation.

    Updates the specified annotation using PATCH semantics.
    Only provided fields are changed.

    Args:
        ctx: Typer context with global options.
        annotation_id: Annotation identifier.
        description: New description.
        tags: Comma-separated tag IDs (replaces existing).
        format: Output format.
        jq_filter: Optional jq filter expression.
    """
    from mixpanel_headless.types import UpdateAnnotationParams

    kwargs: dict[str, Any] = {}
    if description is not None:
        kwargs["description"] = description
    if tags is not None:
        try:
            kwargs["tags"] = [int(t.strip()) for t in tags.split(",") if t.strip()]
        except ValueError as exc:
            err_console.print(f"[red]Invalid tag IDs:[/red] {exc}")
            raise typer.Exit(code=ExitCode.INVALID_ARGS) from None

    params = UpdateAnnotationParams(**kwargs)
    workspace = get_workspace(ctx)
    with status_spinner(ctx, "Updating annotation..."):
        result = workspace.update_annotation(annotation_id, params)
    output_result(ctx, result.model_dump(), format=format, jq_filter=jq_filter)


@annotations_app.command("delete")
@handle_errors
def annotations_delete(
    ctx: typer.Context,
    annotation_id: Annotated[
        int,
        typer.Argument(help="Annotation ID."),
    ],
) -> None:
    """Delete an annotation.

    Permanently deletes an annotation by ID. This action cannot be undone.

    Args:
        ctx: Typer context with global options.
        annotation_id: Annotation identifier.
    """
    workspace = get_workspace(ctx)
    with status_spinner(ctx, "Deleting annotation..."):
        workspace.delete_annotation(annotation_id)
    err_console.print(f"[green]Deleted annotation {annotation_id}.[/green]")


# =============================================================================
# Tags
# =============================================================================


@tags_app.command("list")
@handle_errors
def tags_list(
    ctx: typer.Context,
    format: FormatOption = "json",
    jq_filter: JqOption = None,
) -> None:
    """List annotation tags.

    Retrieves all annotation tags for the project.

    Args:
        ctx: Typer context with global options.
        format: Output format.
        jq_filter: Optional jq filter expression.
    """
    workspace = get_workspace(ctx)
    with status_spinner(ctx, "Fetching annotation tags..."):
        result = workspace.list_annotation_tags()
    output_result(
        ctx,
        [t.model_dump() for t in result],
        format=format,
        jq_filter=jq_filter,
    )


@tags_app.command("create")
@handle_errors
def tags_create(
    ctx: typer.Context,
    name: Annotated[
        str,
        typer.Option("--name", help="Tag name (required)."),
    ],
    format: FormatOption = "json",
    jq_filter: JqOption = None,
) -> None:
    """Create a new annotation tag.

    Creates a tag that can be associated with annotations.

    Args:
        ctx: Typer context with global options.
        name: Tag name (required).
        format: Output format.
        jq_filter: Optional jq filter expression.
    """
    from mixpanel_headless.types import CreateAnnotationTagParams

    params = CreateAnnotationTagParams(name=name)
    workspace = get_workspace(ctx)
    with status_spinner(ctx, "Creating annotation tag..."):
        result = workspace.create_annotation_tag(params)
    output_result(ctx, result.model_dump(), format=format, jq_filter=jq_filter)
