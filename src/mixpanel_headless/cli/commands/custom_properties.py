"""Custom property management commands.

This module provides commands for managing Mixpanel custom properties:

- list: List all custom properties
- get: Get a single custom property
- create: Create a new custom property
- update: Update an existing custom property (PUT)
- delete: Delete a custom property
- validate: Validate a custom property formula
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

custom_properties_app = typer.Typer(
    name="custom-properties",
    help="Manage custom properties.",
    no_args_is_help=True,
)


@custom_properties_app.command("list")
@handle_errors
def custom_properties_list(
    ctx: typer.Context,
    format: FormatOption = "json",
    jq_filter: JqOption = None,
) -> None:
    """List all custom properties for the current project.

    Retrieves all custom properties defined in the project.

    Args:
        ctx: Typer context with global options.
        format: Output format.
        jq_filter: Optional jq filter expression.
    """
    workspace = get_workspace(ctx)
    with status_spinner(ctx, "Fetching custom properties..."):
        result = workspace.list_custom_properties()
    output_result(
        ctx,
        [p.model_dump() for p in result],
        format=format,
        jq_filter=jq_filter,
    )


@custom_properties_app.command("get")
@handle_errors
def custom_properties_get(
    ctx: typer.Context,
    id: Annotated[
        str,
        typer.Option("--id", help="Custom property ID (required)."),
    ],
    format: FormatOption = "json",
    jq_filter: JqOption = None,
) -> None:
    """Get a single custom property by ID.

    Retrieves the full custom property object including its formula,
    composed properties, and metadata.

    Args:
        ctx: Typer context with global options.
        id: Custom property ID (string).
        format: Output format.
        jq_filter: Optional jq filter expression.
    """
    workspace = get_workspace(ctx)
    with status_spinner(ctx, "Fetching custom property..."):
        result = workspace.get_custom_property(id)
    output_result(ctx, result.model_dump(), format=format, jq_filter=jq_filter)


@custom_properties_app.command("create")
@handle_errors
def custom_properties_create(
    ctx: typer.Context,
    name: Annotated[
        str,
        typer.Option("--name", help="Property name (required)."),
    ],
    resource_type: Annotated[
        str,
        typer.Option(
            "--resource-type",
            help="Resource type: events, people, group_profiles (required).",
        ),
    ],
    display_formula: Annotated[
        str | None,
        typer.Option(
            "--display-formula",
            help="Formula expression (mutually exclusive with --behavior).",
        ),
    ] = None,
    composed_properties: Annotated[
        str | None,
        typer.Option(
            "--composed-properties",
            help="Referenced properties as JSON string.",
        ),
    ] = None,
    behavior: Annotated[
        str | None,
        typer.Option(
            "--behavior",
            help="Behavior specification as JSON string (mutually exclusive with --display-formula).",
        ),
    ] = None,
    description: Annotated[
        str | None,
        typer.Option("--description", help="Property description."),
    ] = None,
    format: FormatOption = "json",
    jq_filter: JqOption = None,
) -> None:
    """Create a new custom property.

    Creates a custom property with either a display formula or behavior
    specification. The --display-formula and --behavior options are
    mutually exclusive. When using --display-formula, --composed-properties
    is required.

    Args:
        ctx: Typer context with global options.
        name: Property name.
        resource_type: Resource type (events, people, group_profiles).
        display_formula: Formula expression.
        composed_properties: Referenced properties as JSON string.
        behavior: Behavior specification as JSON string.
        description: Property description.
        format: Output format.
        jq_filter: Optional jq filter expression.
    """
    from mixpanel_headless.types import CreateCustomPropertyParams

    kwargs: dict[str, Any] = {
        "name": name,
        "resource_type": resource_type,
    }

    if display_formula is not None:
        kwargs["display_formula"] = display_formula
    if description is not None:
        kwargs["description"] = description

    if composed_properties is not None:
        try:
            kwargs["composed_properties"] = json.loads(composed_properties)
        except json.JSONDecodeError as exc:
            err_console.print(
                f"[red]Invalid JSON for --composed-properties:[/red] {exc}"
            )
            raise typer.Exit(code=ExitCode.INVALID_ARGS) from None

    if behavior is not None:
        try:
            kwargs["behavior"] = json.loads(behavior)
        except json.JSONDecodeError as exc:
            err_console.print(f"[red]Invalid JSON for --behavior:[/red] {exc}")
            raise typer.Exit(code=ExitCode.INVALID_ARGS) from None

    params = CreateCustomPropertyParams(**kwargs)
    workspace = get_workspace(ctx)
    with status_spinner(ctx, "Creating custom property..."):
        result = workspace.create_custom_property(params)
    output_result(ctx, result.model_dump(), format=format, jq_filter=jq_filter)


@custom_properties_app.command("update")
@handle_errors
def custom_properties_update(
    ctx: typer.Context,
    id: Annotated[
        str,
        typer.Option("--id", help="Custom property ID (required)."),
    ],
    name: Annotated[
        str | None,
        typer.Option("--name", help="New property name."),
    ] = None,
    description: Annotated[
        str | None,
        typer.Option("--description", help="New property description."),
    ] = None,
    display_formula: Annotated[
        str | None,
        typer.Option("--display-formula", help="New formula expression."),
    ] = None,
    composed_properties: Annotated[
        str | None,
        typer.Option(
            "--composed-properties",
            help="New referenced properties as JSON string.",
        ),
    ] = None,
    is_locked: Annotated[
        bool | None,
        typer.Option("--is-locked/--no-is-locked", help="Lock or unlock the property."),
    ] = None,
    is_visible: Annotated[
        bool | None,
        typer.Option("--is-visible/--no-is-visible", help="Show or hide the property."),
    ] = None,
    format: FormatOption = "json",
    jq_filter: JqOption = None,
) -> None:
    """Update an existing custom property (PUT semantics).

    Updates a custom property by ID. Note that resource_type and
    data_group_id are immutable and cannot be changed.

    Args:
        ctx: Typer context with global options.
        id: Custom property ID.
        name: New property name.
        description: New property description.
        display_formula: New formula expression.
        composed_properties: New referenced properties as JSON string.
        is_locked: Lock or unlock the property.
        is_visible: Show or hide the property.
        format: Output format.
        jq_filter: Optional jq filter expression.
    """
    from mixpanel_headless.types import UpdateCustomPropertyParams

    kwargs: dict[str, Any] = {}
    if name is not None:
        kwargs["name"] = name
    if description is not None:
        kwargs["description"] = description
    if display_formula is not None:
        kwargs["display_formula"] = display_formula
    if composed_properties is not None:
        try:
            kwargs["composed_properties"] = json.loads(composed_properties)
        except json.JSONDecodeError as exc:
            err_console.print(
                f"[red]Invalid JSON for --composed-properties:[/red] {exc}"
            )
            raise typer.Exit(code=ExitCode.INVALID_ARGS) from None
    if is_locked is not None:
        kwargs["is_locked"] = is_locked
    if is_visible is not None:
        kwargs["is_visible"] = is_visible

    params = UpdateCustomPropertyParams(**kwargs)
    workspace = get_workspace(ctx)
    with status_spinner(ctx, "Updating custom property..."):
        result = workspace.update_custom_property(id, params)
    output_result(ctx, result.model_dump(), format=format, jq_filter=jq_filter)


@custom_properties_app.command("delete")
@handle_errors
def custom_properties_delete(
    ctx: typer.Context,
    id: Annotated[
        str,
        typer.Option("--id", help="Custom property ID (required)."),
    ],
) -> None:
    """Delete a custom property.

    Permanently deletes a custom property by ID. This action cannot be undone.

    Args:
        ctx: Typer context with global options.
        id: Custom property ID (string).
    """
    workspace = get_workspace(ctx)
    with status_spinner(ctx, "Deleting custom property..."):
        workspace.delete_custom_property(id)
    err_console.print(f"[green]Deleted custom property {id}.[/green]")


@custom_properties_app.command("validate")
@handle_errors
def custom_properties_validate(
    ctx: typer.Context,
    name: Annotated[
        str,
        typer.Option("--name", help="Property name (required)."),
    ],
    resource_type: Annotated[
        str,
        typer.Option(
            "--resource-type",
            help="Resource type: events, people, group_profiles (required).",
        ),
    ],
    display_formula: Annotated[
        str | None,
        typer.Option("--display-formula", help="Formula expression to validate."),
    ] = None,
    composed_properties: Annotated[
        str | None,
        typer.Option(
            "--composed-properties",
            help="Referenced properties as JSON string.",
        ),
    ] = None,
    behavior: Annotated[
        str | None,
        typer.Option(
            "--behavior",
            help="Behavior specification as JSON string.",
        ),
    ] = None,
    format: FormatOption = "json",
    jq_filter: JqOption = None,
) -> None:
    """Validate a custom property formula without creating it.

    Checks whether the provided custom property definition is valid.
    Does not create the property.

    Args:
        ctx: Typer context with global options.
        name: Property name.
        resource_type: Resource type (events, people, group_profiles).
        display_formula: Formula expression to validate.
        composed_properties: Referenced properties as JSON string.
        behavior: Behavior specification as JSON string.
        format: Output format.
        jq_filter: Optional jq filter expression.
    """
    from mixpanel_headless.types import CreateCustomPropertyParams

    kwargs: dict[str, Any] = {
        "name": name,
        "resource_type": resource_type,
    }

    if display_formula is not None:
        kwargs["display_formula"] = display_formula

    if composed_properties is not None:
        try:
            kwargs["composed_properties"] = json.loads(composed_properties)
        except json.JSONDecodeError as exc:
            err_console.print(
                f"[red]Invalid JSON for --composed-properties:[/red] {exc}"
            )
            raise typer.Exit(code=ExitCode.INVALID_ARGS) from None

    if behavior is not None:
        try:
            kwargs["behavior"] = json.loads(behavior)
        except json.JSONDecodeError as exc:
            err_console.print(f"[red]Invalid JSON for --behavior:[/red] {exc}")
            raise typer.Exit(code=ExitCode.INVALID_ARGS) from None

    params = CreateCustomPropertyParams(**kwargs)
    workspace = get_workspace(ctx)
    with status_spinner(ctx, "Validating custom property..."):
        result = workspace.validate_custom_property(params)
    output_result(ctx, result, format=format, jq_filter=jq_filter)
