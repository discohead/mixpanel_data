"""Schema registry management commands.

Commands for managing Mixpanel schema registry definitions:
- list: List schema entries (all or by entity type)
- create: Create a single schema
- create-bulk: Bulk create schemas
- update: Update a single schema (merge semantics)
- update-bulk: Bulk update schemas
- delete: Delete schemas
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

schemas_app = typer.Typer(
    name="schemas",
    help="Manage schema registry definitions.",
    no_args_is_help=True,
)


@schemas_app.command("list")
@handle_errors
def schemas_list(
    ctx: typer.Context,
    entity_type: Annotated[
        str | None,
        typer.Option(
            "--entity-type",
            help="Filter by entity type (event, custom_event, or profile).",
        ),
    ] = None,
    format: FormatOption = "json",
    jq_filter: JqOption = None,
) -> None:
    """List schema registry entries.

    Retrieves all schema entries, optionally filtered by entity type.

    Args:
        ctx: Typer context with global options.
        entity_type: Optional entity type filter.
        format: Output format.
        jq_filter: Optional jq filter expression.
    """
    workspace = get_workspace(ctx)
    with status_spinner(ctx, "Fetching schema registry entries..."):
        result = workspace.list_schema_registry(entity_type=entity_type)
    output_result(
        ctx,
        [s.model_dump(by_alias=True) for s in result],
        format=format,
        jq_filter=jq_filter,
    )


@schemas_app.command("create")
@handle_errors
def schemas_create(
    ctx: typer.Context,
    entity_type: Annotated[
        str,
        typer.Option(
            "--entity-type", help="Entity type (event, custom_event, or profile)."
        ),
    ],
    entity_name: Annotated[
        str,
        typer.Option("--entity-name", help="Entity name for the schema."),
    ],
    schema_json: Annotated[
        str,
        typer.Option(
            "--schema-json",
            help="Schema definition as a JSON string.",
        ),
    ],
    format: FormatOption = "json",
    jq_filter: JqOption = None,
) -> None:
    """Create a single schema entry.

    Creates a new schema definition for the specified entity type and name.

    Args:
        ctx: Typer context with global options.
        entity_type: Entity type (event, custom_event, or profile).
        entity_name: Entity name for the schema.
        schema_json: Schema definition as a JSON string.
        format: Output format.
        jq_filter: Optional jq filter expression.
    """
    try:
        parsed: dict[str, Any] = json.loads(schema_json)
    except json.JSONDecodeError as exc:
        err_console.print(f"[red]Invalid JSON for --schema-json:[/red] {exc}")
        raise typer.Exit(code=ExitCode.INVALID_ARGS) from None

    workspace = get_workspace(ctx)
    with status_spinner(ctx, "Creating schema entry..."):
        result = workspace.create_schema(entity_type, entity_name, parsed)
    output_result(ctx, result, format=format, jq_filter=jq_filter)


@schemas_app.command("create-bulk")
@handle_errors
def schemas_create_bulk(
    ctx: typer.Context,
    entries: Annotated[
        str,
        typer.Option(
            "--entries",
            help="JSON array of schema entries for bulk creation.",
        ),
    ],
    truncate: Annotated[
        bool,
        typer.Option(
            "--truncate/--no-truncate",
            help="Truncate existing schemas before creating.",
        ),
    ] = False,
    entity_type: Annotated[
        str | None,
        typer.Option(
            "--entity-type",
            help="Entity type filter for truncation scope.",
        ),
    ] = None,
    format: FormatOption = "json",
    jq_filter: JqOption = None,
) -> None:
    """Bulk create schema entries.

    Creates multiple schema entries in a single request. Optionally
    truncates existing schemas before creating.

    Args:
        ctx: Typer context with global options.
        entries: JSON array of schema entries.
        truncate: Whether to truncate existing schemas before creating.
        entity_type: Entity type filter for truncation scope.
        format: Output format.
        jq_filter: Optional jq filter expression.
    """
    from mixpanel_headless.types import BulkCreateSchemasParams

    try:
        parsed: Any = json.loads(entries)
    except json.JSONDecodeError as exc:
        err_console.print(f"[red]Invalid JSON for --entries:[/red] {exc}")
        raise typer.Exit(code=ExitCode.INVALID_ARGS) from None

    kwargs: dict[str, Any] = {"entries": parsed}
    if truncate:
        kwargs["truncate"] = truncate
    if entity_type is not None:
        kwargs["entity_type"] = entity_type

    params = BulkCreateSchemasParams(**kwargs)
    workspace = get_workspace(ctx)
    with status_spinner(ctx, "Bulk creating schema entries..."):
        result = workspace.create_schemas_bulk(params)
    output_result(
        ctx,
        result.model_dump(by_alias=True),
        format=format,
        jq_filter=jq_filter,
    )


@schemas_app.command("update")
@handle_errors
def schemas_update(
    ctx: typer.Context,
    entity_type: Annotated[
        str,
        typer.Option(
            "--entity-type", help="Entity type (event, custom_event, or profile)."
        ),
    ],
    entity_name: Annotated[
        str,
        typer.Option("--entity-name", help="Entity name for the schema."),
    ],
    schema_json: Annotated[
        str,
        typer.Option(
            "--schema-json",
            help="Schema updates as a JSON string (merge semantics).",
        ),
    ],
    format: FormatOption = "json",
    jq_filter: JqOption = None,
) -> None:
    """Update a single schema entry (merge semantics).

    Updates an existing schema definition. Fields provided in the JSON
    are merged with the existing schema.

    Args:
        ctx: Typer context with global options.
        entity_type: Entity type (event, custom_event, or profile).
        entity_name: Entity name for the schema.
        schema_json: Schema updates as a JSON string.
        format: Output format.
        jq_filter: Optional jq filter expression.
    """
    try:
        parsed: dict[str, Any] = json.loads(schema_json)
    except json.JSONDecodeError as exc:
        err_console.print(f"[red]Invalid JSON for --schema-json:[/red] {exc}")
        raise typer.Exit(code=ExitCode.INVALID_ARGS) from None

    workspace = get_workspace(ctx)
    with status_spinner(ctx, "Updating schema entry..."):
        result = workspace.update_schema(entity_type, entity_name, parsed)
    output_result(ctx, result, format=format, jq_filter=jq_filter)


@schemas_app.command("update-bulk")
@handle_errors
def schemas_update_bulk(
    ctx: typer.Context,
    entries: Annotated[
        str,
        typer.Option(
            "--entries",
            help="JSON array of schema entries for bulk update.",
        ),
    ],
    format: FormatOption = "json",
    jq_filter: JqOption = None,
) -> None:
    """Bulk update schema entries.

    Updates multiple schema entries in a single request.

    Args:
        ctx: Typer context with global options.
        entries: JSON array of schema entries for bulk update.
        format: Output format.
        jq_filter: Optional jq filter expression.
    """
    from mixpanel_headless.types import BulkCreateSchemasParams

    try:
        parsed: Any = json.loads(entries)
    except json.JSONDecodeError as exc:
        err_console.print(f"[red]Invalid JSON for --entries:[/red] {exc}")
        raise typer.Exit(code=ExitCode.INVALID_ARGS) from None

    params = BulkCreateSchemasParams(entries=parsed)
    workspace = get_workspace(ctx)
    with status_spinner(ctx, "Bulk updating schema entries..."):
        result = workspace.update_schemas_bulk(params)
    output_result(
        ctx,
        [r.model_dump(by_alias=True) for r in result],
        format=format,
        jq_filter=jq_filter,
    )


@schemas_app.command("delete")
@handle_errors
def schemas_delete(
    ctx: typer.Context,
    entity_type: Annotated[
        str | None,
        typer.Option(
            "--entity-type",
            help="Entity type filter for deletion.",
        ),
    ] = None,
    entity_name: Annotated[
        str | None,
        typer.Option(
            "--entity-name",
            help="Entity name filter for deletion.",
        ),
    ] = None,
    format: FormatOption = "json",
    jq_filter: JqOption = None,
) -> None:
    """Delete schema entries.

    Deletes schema entries, optionally filtered by entity type and/or
    entity name. Without filters, deletes all schemas.

    Args:
        ctx: Typer context with global options.
        entity_type: Optional entity type filter for deletion.
        entity_name: Optional entity name filter for deletion.
        format: Output format.
        jq_filter: Optional jq filter expression.
    """
    if entity_type is None and entity_name is None:
        typer.confirm("This will delete ALL schemas. Continue?", abort=True)
    workspace = get_workspace(ctx)
    with status_spinner(ctx, "Deleting schema entries..."):
        result = workspace.delete_schemas(
            entity_type=entity_type, entity_name=entity_name
        )
    output_result(
        ctx,
        result.model_dump(by_alias=True),
        format=format,
        jq_filter=jq_filter,
    )
