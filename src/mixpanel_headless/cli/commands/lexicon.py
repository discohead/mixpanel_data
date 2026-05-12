"""Lexicon data-definition management commands.

This module provides commands for managing Mixpanel Lexicon data definitions:

Event definitions:
- events get: Get event definitions by name
- events update: Update a single event definition
- events delete: Delete an event definition
- events bulk-update: Bulk-update event definitions

Property definitions:
- properties get: Get property definitions by name
- properties update: Update a single property definition
- properties bulk-update: Bulk-update property definitions

Tags:
- tags list: List all Lexicon tags
- tags create: Create a new tag
- tags update: Update an existing tag
- tags delete: Delete a tag

Enforcement:
- enforcement get: Get schema enforcement settings
- enforcement init: Initialize schema enforcement
- enforcement update: Update schema enforcement (PATCH)
- enforcement replace: Replace schema enforcement (PUT)
- enforcement delete: Delete schema enforcement

Anomalies:
- anomalies list: List data volume anomalies
- anomalies update: Update a single anomaly
- anomalies bulk-update: Bulk-update anomalies

Deletion requests:
- deletion-requests list: List event deletion requests
- deletion-requests create: Create an event deletion request
- deletion-requests cancel: Cancel a pending deletion request
- deletion-requests preview: Preview deletion filter results

Top-level:
- tracking-metadata: Get tracking metadata for an event
- event-history: Get change history for an event definition
- property-history: Get change history for a property definition
- export: Export Lexicon data definitions
- audit: Run schema audit to find violations
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

lexicon_app = typer.Typer(
    name="lexicon",
    help="Manage Lexicon data definitions.",
    no_args_is_help=True,
)

events_app = typer.Typer(
    name="events",
    help="Manage event definitions.",
    no_args_is_help=True,
)
lexicon_app.add_typer(events_app, name="events")

properties_app = typer.Typer(
    name="properties",
    help="Manage property definitions.",
    no_args_is_help=True,
)
lexicon_app.add_typer(properties_app, name="properties")

tags_app = typer.Typer(
    name="tags",
    help="Manage Lexicon tags.",
    no_args_is_help=True,
)
lexicon_app.add_typer(tags_app, name="tags")


# =============================================================================
# Event Definitions
# =============================================================================


@events_app.command("get")
@handle_errors
def events_get(
    ctx: typer.Context,
    names: Annotated[
        str,
        typer.Option("--names", help="Comma-separated event names."),
    ],
    format: FormatOption = "json",
    jq_filter: JqOption = None,
) -> None:
    """Get event definitions by name.

    Retrieves metadata (description, tags, visibility, etc.) for the
    specified events from the Mixpanel Lexicon.

    Args:
        ctx: Typer context with global options.
        names: Comma-separated event names.
        format: Output format.
        jq_filter: Optional jq filter expression.
    """
    workspace = get_workspace(ctx)
    name_list = [n.strip() for n in names.split(",") if n.strip()]
    if not name_list:
        err_console.print("[red]No valid event names provided.[/red]")
        raise typer.Exit(code=ExitCode.INVALID_ARGS)
    with status_spinner(ctx, "Fetching event definitions..."):
        result = workspace.get_event_definitions(names=name_list)
    output_result(
        ctx,
        [r.model_dump() for r in result],
        format=format,
        jq_filter=jq_filter,
    )


@events_app.command("update")
@handle_errors
def events_update(
    ctx: typer.Context,
    name: Annotated[
        str,
        typer.Option("--name", help="Event name to update."),
    ],
    hidden: Annotated[
        bool | None,
        typer.Option("--hidden/--no-hidden", help="Hide or unhide event."),
    ] = None,
    dropped: Annotated[
        bool | None,
        typer.Option("--dropped/--no-dropped", help="Drop or undrop event data."),
    ] = None,
    verified: Annotated[
        bool | None,
        typer.Option(
            "--verified/--no-verified", help="Mark event as verified or unverified."
        ),
    ] = None,
    description: Annotated[
        str | None,
        typer.Option("--description", help="New event description."),
    ] = None,
    tags: Annotated[
        str | None,
        typer.Option("--tags", help="Comma-separated tag names to assign."),
    ] = None,
    format: FormatOption = "json",
    jq_filter: JqOption = None,
) -> None:
    """Update an event definition (PATCH semantics).

    Only fields provided will be updated. Use boolean flags like
    ``--hidden/--no-hidden`` to toggle visibility.

    Args:
        ctx: Typer context with global options.
        name: Event name to update.
        hidden: Whether to hide the event.
        dropped: Whether to drop event data at ingestion.
        verified: Whether to mark the event as verified.
        description: New description text.
        tags: Comma-separated tag names to assign.
        format: Output format.
        jq_filter: Optional jq filter expression.
    """
    from mixpanel_headless.types import UpdateEventDefinitionParams

    kwargs: dict[str, Any] = {}
    if hidden is not None:
        kwargs["hidden"] = hidden
    if dropped is not None:
        kwargs["dropped"] = dropped
    if verified is not None:
        kwargs["verified"] = verified
    if description is not None:
        kwargs["description"] = description
    if tags is not None:
        kwargs["tags"] = [t.strip() for t in tags.split(",") if t.strip()]

    params = UpdateEventDefinitionParams(**kwargs)
    workspace = get_workspace(ctx)
    with status_spinner(ctx, "Updating event definition..."):
        result = workspace.update_event_definition(name, params)
    output_result(ctx, result.model_dump(), format=format, jq_filter=jq_filter)


@events_app.command("delete")
@handle_errors
def events_delete(
    ctx: typer.Context,
    name: Annotated[
        str,
        typer.Option("--name", help="Event name to delete."),
    ],
) -> None:
    """Delete an event definition from Lexicon.

    Permanently removes the event definition. This action cannot be undone.

    Args:
        ctx: Typer context with global options.
        name: Event name to delete.
    """
    workspace = get_workspace(ctx)
    with status_spinner(ctx, "Deleting event definition..."):
        workspace.delete_event_definition(name)
    err_console.print(f"[green]Deleted event definition '{name}'.[/green]")


@events_app.command("bulk-update")
@handle_errors
def events_bulk_update(
    ctx: typer.Context,
    data: Annotated[
        str,
        typer.Option(
            "--data",
            help="Bulk update payload as JSON string (list of event updates).",
        ),
    ],
    format: FormatOption = "json",
    jq_filter: JqOption = None,
) -> None:
    """Bulk-update event definitions.

    Accepts a JSON string with a list of event updates. Each entry
    should include ``name`` and any fields to change.

    Args:
        ctx: Typer context with global options.
        data: JSON string containing bulk update payload.
        format: Output format.
        jq_filter: Optional jq filter expression.
    """
    from mixpanel_headless.types import BulkUpdateEventsParams

    try:
        parsed: dict[str, Any] = json.loads(data)
    except json.JSONDecodeError as exc:
        err_console.print(f"[red]Invalid JSON for --data:[/red] {exc}")
        raise typer.Exit(code=ExitCode.INVALID_ARGS) from None

    params = BulkUpdateEventsParams(**parsed)
    workspace = get_workspace(ctx)
    with status_spinner(ctx, "Bulk-updating event definitions..."):
        result = workspace.bulk_update_event_definitions(params)
    output_result(
        ctx,
        [r.model_dump() for r in result],
        format=format,
        jq_filter=jq_filter,
    )


# =============================================================================
# Property Definitions
# =============================================================================


@properties_app.command("get")
@handle_errors
def properties_get(
    ctx: typer.Context,
    names: Annotated[
        str,
        typer.Option("--names", help="Comma-separated property names."),
    ],
    resource_type: Annotated[
        str | None,
        typer.Option(
            "--resource-type",
            help="Resource type filter (event, user, groupprofile).",
        ),
    ] = None,
    format: FormatOption = "json",
    jq_filter: JqOption = None,
) -> None:
    """Get property definitions by name.

    Retrieves metadata (description, tags, visibility, etc.) for the
    specified properties from the Mixpanel Lexicon.

    Args:
        ctx: Typer context with global options.
        names: Comma-separated property names.
        resource_type: Optional resource type filter.
        format: Output format.
        jq_filter: Optional jq filter expression.
    """
    workspace = get_workspace(ctx)
    name_list = [n.strip() for n in names.split(",") if n.strip()]
    if not name_list:
        err_console.print("[red]No valid property names provided.[/red]")
        raise typer.Exit(code=ExitCode.INVALID_ARGS)
    kwargs: dict[str, Any] = {"names": name_list}
    if resource_type is not None:
        kwargs["resource_type"] = resource_type
    with status_spinner(ctx, "Fetching property definitions..."):
        result = workspace.get_property_definitions(**kwargs)
    output_result(
        ctx,
        [r.model_dump() for r in result],
        format=format,
        jq_filter=jq_filter,
    )


@properties_app.command("update")
@handle_errors
def properties_update(
    ctx: typer.Context,
    name: Annotated[
        str,
        typer.Option("--name", help="Property name to update."),
    ],
    hidden: Annotated[
        bool | None,
        typer.Option("--hidden/--no-hidden", help="Hide or unhide property."),
    ] = None,
    dropped: Annotated[
        bool | None,
        typer.Option("--dropped/--no-dropped", help="Drop or undrop property data."),
    ] = None,
    sensitive: Annotated[
        bool | None,
        typer.Option(
            "--sensitive/--no-sensitive", help="Mark property as PII sensitive."
        ),
    ] = None,
    description: Annotated[
        str | None,
        typer.Option("--description", help="New property description."),
    ] = None,
    format: FormatOption = "json",
    jq_filter: JqOption = None,
) -> None:
    """Update a property definition (PATCH semantics).

    Only fields provided will be updated. Use boolean flags like
    ``--hidden/--no-hidden`` to toggle visibility.

    Args:
        ctx: Typer context with global options.
        name: Property name to update.
        hidden: Whether to hide the property.
        dropped: Whether to drop property data.
        sensitive: Whether to mark the property as PII sensitive.
        description: New description text.
        format: Output format.
        jq_filter: Optional jq filter expression.
    """
    from mixpanel_headless.types import UpdatePropertyDefinitionParams

    kwargs: dict[str, Any] = {}
    if hidden is not None:
        kwargs["hidden"] = hidden
    if dropped is not None:
        kwargs["dropped"] = dropped
    if sensitive is not None:
        kwargs["sensitive"] = sensitive
    if description is not None:
        kwargs["description"] = description

    params = UpdatePropertyDefinitionParams(**kwargs)
    workspace = get_workspace(ctx)
    with status_spinner(ctx, "Updating property definition..."):
        result = workspace.update_property_definition(name, params)
    output_result(ctx, result.model_dump(), format=format, jq_filter=jq_filter)


@properties_app.command("bulk-update")
@handle_errors
def properties_bulk_update(
    ctx: typer.Context,
    data: Annotated[
        str,
        typer.Option(
            "--data",
            help="Bulk update payload as JSON string (list of property updates).",
        ),
    ],
    format: FormatOption = "json",
    jq_filter: JqOption = None,
) -> None:
    """Bulk-update property definitions.

    Accepts a JSON string with a list of property updates. Each entry
    should include ``name`` and any fields to change.

    Args:
        ctx: Typer context with global options.
        data: JSON string containing bulk update payload.
        format: Output format.
        jq_filter: Optional jq filter expression.
    """
    from mixpanel_headless.types import BulkUpdatePropertiesParams

    try:
        parsed: dict[str, Any] = json.loads(data)
    except json.JSONDecodeError as exc:
        err_console.print(f"[red]Invalid JSON for --data:[/red] {exc}")
        raise typer.Exit(code=ExitCode.INVALID_ARGS) from None

    params = BulkUpdatePropertiesParams(**parsed)
    workspace = get_workspace(ctx)
    with status_spinner(ctx, "Bulk-updating property definitions..."):
        result = workspace.bulk_update_property_definitions(params)
    output_result(
        ctx,
        [r.model_dump() for r in result],
        format=format,
        jq_filter=jq_filter,
    )


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
    """List all Lexicon tags.

    Retrieves all tags available for categorizing event and property
    definitions.

    Args:
        ctx: Typer context with global options.
        format: Output format.
        jq_filter: Optional jq filter expression.
    """
    workspace = get_workspace(ctx)
    with status_spinner(ctx, "Fetching tags..."):
        result = workspace.list_lexicon_tags()
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
        typer.Option("--name", help="Tag name to create."),
    ],
    format: FormatOption = "json",
    jq_filter: JqOption = None,
) -> None:
    """Create a new Lexicon tag.

    Creates a tag that can be assigned to event and property definitions.

    Args:
        ctx: Typer context with global options.
        name: Tag name to create.
        format: Output format.
        jq_filter: Optional jq filter expression.
    """
    from mixpanel_headless.types import CreateTagParams

    params = CreateTagParams(name=name)
    workspace = get_workspace(ctx)
    with status_spinner(ctx, "Creating tag..."):
        result = workspace.create_lexicon_tag(params)
    output_result(ctx, result.model_dump(), format=format, jq_filter=jq_filter)


@tags_app.command("update")
@handle_errors
def tags_update(
    ctx: typer.Context,
    id: Annotated[
        int,
        typer.Option("--id", help="Tag ID to update."),
    ],
    name: Annotated[
        str,
        typer.Option("--name", help="New tag name."),
    ],
    format: FormatOption = "json",
    jq_filter: JqOption = None,
) -> None:
    """Update an existing Lexicon tag.

    Renames an existing tag by its ID.

    Args:
        ctx: Typer context with global options.
        id: Tag ID (integer).
        name: New tag name.
        format: Output format.
        jq_filter: Optional jq filter expression.
    """
    from mixpanel_headless.types import UpdateTagParams

    params = UpdateTagParams(name=name)
    workspace = get_workspace(ctx)
    with status_spinner(ctx, "Updating tag..."):
        result = workspace.update_lexicon_tag(id, params)
    output_result(ctx, result.model_dump(), format=format, jq_filter=jq_filter)


@tags_app.command("delete")
@handle_errors
def tags_delete(
    ctx: typer.Context,
    name: Annotated[
        str,
        typer.Option("--name", help="Tag name to delete."),
    ],
) -> None:
    """Delete a Lexicon tag by name.

    Permanently removes the tag. This action cannot be undone.

    Args:
        ctx: Typer context with global options.
        name: Tag name to delete.
    """
    workspace = get_workspace(ctx)
    with status_spinner(ctx, "Deleting tag..."):
        workspace.delete_lexicon_tag(name)
    err_console.print(f"[green]Deleted tag '{name}'.[/green]")


# =============================================================================
# Top-level Commands
# =============================================================================


@lexicon_app.command("tracking-metadata")
@handle_errors
def tracking_metadata(
    ctx: typer.Context,
    event_name: Annotated[
        str,
        typer.Option("--event-name", help="Event name to get metadata for."),
    ],
    format: FormatOption = "json",
    jq_filter: JqOption = None,
) -> None:
    """Get tracking metadata for an event.

    Retrieves information about how an event is being tracked
    (sources, SDKs, volume, etc.).

    Args:
        ctx: Typer context with global options.
        event_name: Event name.
        format: Output format.
        jq_filter: Optional jq filter expression.
    """
    workspace = get_workspace(ctx)
    with status_spinner(ctx, "Fetching tracking metadata..."):
        result = workspace.get_tracking_metadata(event_name)
    output_result(ctx, result, format=format, jq_filter=jq_filter)


@lexicon_app.command("event-history")
@handle_errors
def event_history(
    ctx: typer.Context,
    event_name: Annotated[
        str,
        typer.Option("--event-name", help="Event name to get history for."),
    ],
    format: FormatOption = "json",
    jq_filter: JqOption = None,
) -> None:
    """Get change history for an event definition.

    Retrieves a chronological list of changes made to the event
    definition over time.

    Args:
        ctx: Typer context with global options.
        event_name: Event name.
        format: Output format.
        jq_filter: Optional jq filter expression.
    """
    workspace = get_workspace(ctx)
    with status_spinner(ctx, "Fetching event history..."):
        result = workspace.get_event_history(event_name)
    output_result(ctx, result, format=format, jq_filter=jq_filter)


@lexicon_app.command("property-history")
@handle_errors
def property_history(
    ctx: typer.Context,
    property_name: Annotated[
        str,
        typer.Option("--property-name", help="Property name to get history for."),
    ],
    entity_type: Annotated[
        str,
        typer.Option("--entity-type", help="Entity type (event, user, group)."),
    ],
    format: FormatOption = "json",
    jq_filter: JqOption = None,
) -> None:
    """Get change history for a property definition.

    Retrieves a chronological list of changes made to the property
    definition over time.

    Args:
        ctx: Typer context with global options.
        property_name: Property name.
        entity_type: Entity type (event, user, group).
        format: Output format.
        jq_filter: Optional jq filter expression.
    """
    workspace = get_workspace(ctx)
    with status_spinner(ctx, "Fetching property history..."):
        result = workspace.get_property_history(property_name, entity_type)
    output_result(ctx, result, format=format, jq_filter=jq_filter)


@lexicon_app.command("export")
@handle_errors
def lexicon_export(
    ctx: typer.Context,
    types: Annotated[
        str | None,
        typer.Option(
            "--types",
            help="Comma-separated export types (events, event_properties, user_properties).",
        ),
    ] = None,
    format: FormatOption = "json",
    jq_filter: JqOption = None,
) -> None:
    """Export Lexicon data definitions.

    Exports event and property definitions, optionally filtered by type.

    Args:
        ctx: Typer context with global options.
        types: Comma-separated export types to include.
        format: Output format.
        jq_filter: Optional jq filter expression.
    """
    workspace = get_workspace(ctx)
    kwargs: dict[str, Any] = {}
    if types is not None:
        kwargs["export_types"] = [t.strip() for t in types.split(",") if t.strip()]
    with status_spinner(ctx, "Exporting Lexicon definitions..."):
        result = workspace.export_lexicon(**kwargs)
    if isinstance(result, dict) and result.get("status") == "pending":
        err_console.print(
            f"[yellow]Export is processing asynchronously:[/yellow] "
            f"{result.get('message', 'Check back later.')}"
        )
    output_result(ctx, result, format=format, jq_filter=jq_filter)


# =============================================================================
# Audit
# =============================================================================


@lexicon_app.command("audit")
@handle_errors
def lexicon_audit(
    ctx: typer.Context,
    events_only: Annotated[
        bool,
        typer.Option(
            "--events-only",
            help="Run audit for events only (faster, fewer results).",
        ),
    ] = False,
    format: FormatOption = "json",
    jq_filter: JqOption = None,
) -> None:
    """Run schema audit to find violations.

    Audits the project schema for violations such as unexpected events,
    missing properties, or unexpected property types. Use ``--events-only``
    for a faster, event-scoped audit.

    Args:
        ctx: Typer context with global options.
        events_only: If True, audit events only instead of full schema.
        format: Output format.
        jq_filter: Optional jq filter expression.
    """
    workspace = get_workspace(ctx)
    with status_spinner(ctx, "Running schema audit..."):
        if events_only:
            result = workspace.run_audit_events_only()
        else:
            result = workspace.run_audit()
    output_result(
        ctx,
        result.model_dump(by_alias=True),
        format=format,
        jq_filter=jq_filter,
    )


# =============================================================================
# Enforcement
# =============================================================================

enforcement_app = typer.Typer(
    name="enforcement",
    help="Manage schema enforcement.",
    no_args_is_help=True,
)
lexicon_app.add_typer(enforcement_app, name="enforcement")


@enforcement_app.command("get")
@handle_errors
def enforcement_get(
    ctx: typer.Context,
    fields: Annotated[
        str | None,
        typer.Option("--fields", help="Comma-separated fields to include."),
    ] = None,
    format: FormatOption = "json",
    jq_filter: JqOption = None,
) -> None:
    """Get schema enforcement settings.

    Retrieves the current schema enforcement configuration for the project.
    Use ``--fields`` to limit the response to specific fields.

    Args:
        ctx: Typer context with global options.
        fields: Optional comma-separated field names to include.
        format: Output format.
        jq_filter: Optional jq filter expression.
    """
    workspace = get_workspace(ctx)
    kwargs: dict[str, Any] = {}
    if fields is not None:
        kwargs["fields"] = fields
    with status_spinner(ctx, "Fetching schema enforcement settings..."):
        result = workspace.get_schema_enforcement(**kwargs)
    output_result(
        ctx,
        result.model_dump(by_alias=True),
        format=format,
        jq_filter=jq_filter,
    )


@enforcement_app.command("init")
@handle_errors
def enforcement_init(
    ctx: typer.Context,
    rule_event: Annotated[
        str,
        typer.Option(
            "--rule-event",
            help="Enforcement action (e.g. 'Warn and Accept', 'Warn and Hide', 'Warn and Drop').",
        ),
    ],
    format: FormatOption = "json",
    jq_filter: JqOption = None,
) -> None:
    """Initialize schema enforcement.

    Sets up schema enforcement for the project with the given rule event
    as the initial enforcement target.

    Args:
        ctx: Typer context with global options.
        rule_event: Enforcement action ("Warn and Accept", "Warn and Hide", or "Warn and Drop").
        format: Output format.
        jq_filter: Optional jq filter expression.
    """
    from mixpanel_headless.types import InitSchemaEnforcementParams

    params = InitSchemaEnforcementParams(rule_event=rule_event)
    workspace = get_workspace(ctx)
    with status_spinner(ctx, "Initializing schema enforcement..."):
        result = workspace.init_schema_enforcement(params)
    output_result(ctx, result, format=format, jq_filter=jq_filter)


@enforcement_app.command("update")
@handle_errors
def enforcement_update(
    ctx: typer.Context,
    body: Annotated[
        str,
        typer.Option(
            "--body",
            help="Schema enforcement update payload as JSON string.",
        ),
    ],
    format: FormatOption = "json",
    jq_filter: JqOption = None,
) -> None:
    """Update schema enforcement settings (PATCH semantics).

    Applies a partial update to the schema enforcement configuration.
    Accepts a JSON string with the fields to update.

    Args:
        ctx: Typer context with global options.
        body: JSON string containing the update payload.
        format: Output format.
        jq_filter: Optional jq filter expression.
    """
    from mixpanel_headless.types import UpdateSchemaEnforcementParams

    try:
        parsed: dict[str, Any] = json.loads(body)
    except json.JSONDecodeError as exc:
        err_console.print(f"[red]Invalid JSON for --body:[/red] {exc}")
        raise typer.Exit(code=ExitCode.INVALID_ARGS) from None

    params = UpdateSchemaEnforcementParams(**parsed)
    workspace = get_workspace(ctx)
    with status_spinner(ctx, "Updating schema enforcement..."):
        result = workspace.update_schema_enforcement(params)
    output_result(ctx, result, format=format, jq_filter=jq_filter)


@enforcement_app.command("replace")
@handle_errors
def enforcement_replace(
    ctx: typer.Context,
    body: Annotated[
        str,
        typer.Option(
            "--body",
            help="Schema enforcement replacement payload as JSON string.",
        ),
    ],
    format: FormatOption = "json",
    jq_filter: JqOption = None,
) -> None:
    """Replace schema enforcement settings (PUT semantics).

    Replaces the entire schema enforcement configuration with the
    provided payload. All existing settings will be overwritten.

    Args:
        ctx: Typer context with global options.
        body: JSON string containing the full replacement payload.
        format: Output format.
        jq_filter: Optional jq filter expression.
    """
    from mixpanel_headless.types import ReplaceSchemaEnforcementParams

    try:
        parsed: dict[str, Any] = json.loads(body)
    except json.JSONDecodeError as exc:
        err_console.print(f"[red]Invalid JSON for --body:[/red] {exc}")
        raise typer.Exit(code=ExitCode.INVALID_ARGS) from None

    params = ReplaceSchemaEnforcementParams(**parsed)
    workspace = get_workspace(ctx)
    with status_spinner(ctx, "Replacing schema enforcement..."):
        result = workspace.replace_schema_enforcement(params)
    output_result(ctx, result, format=format, jq_filter=jq_filter)


@enforcement_app.command("delete")
@handle_errors
def enforcement_delete(
    ctx: typer.Context,
) -> None:
    """Delete schema enforcement settings.

    Removes all schema enforcement configuration for the project.
    This action cannot be undone.

    Args:
        ctx: Typer context with global options.
    """
    typer.confirm(
        "Delete all schema enforcement settings? This cannot be undone.",
        abort=True,
    )
    workspace = get_workspace(ctx)
    with status_spinner(ctx, "Deleting schema enforcement..."):
        workspace.delete_schema_enforcement()
    err_console.print("[green]Deleted schema enforcement settings.[/green]")


# =============================================================================
# Anomalies
# =============================================================================

anomalies_app = typer.Typer(
    name="anomalies",
    help="Manage data volume anomalies.",
    no_args_is_help=True,
)
lexicon_app.add_typer(anomalies_app, name="anomalies")


@anomalies_app.command("list")
@handle_errors
def anomalies_list(
    ctx: typer.Context,
    status: Annotated[
        str | None,
        typer.Option("--status", help="Filter by anomaly status."),
    ] = None,
    limit: Annotated[
        int | None,
        typer.Option("--limit", help="Maximum number of anomalies to return."),
    ] = None,
    format: FormatOption = "json",
    jq_filter: JqOption = None,
) -> None:
    """List data volume anomalies.

    Retrieves anomalies detected in data volume patterns. Optionally
    filter by status or limit the number of results.

    Args:
        ctx: Typer context with global options.
        status: Optional status filter (e.g. 'open', 'dismissed').
        limit: Optional maximum number of results.
        format: Output format.
        jq_filter: Optional jq filter expression.
    """
    workspace = get_workspace(ctx)
    query_params: dict[str, str] = {}
    if status is not None:
        query_params["status"] = status
    if limit is not None:
        query_params["limit"] = str(limit)
    with status_spinner(ctx, "Fetching data volume anomalies..."):
        result = workspace.list_data_volume_anomalies(query_params=query_params)
    output_result(
        ctx,
        [a.model_dump(by_alias=True) for a in result],
        format=format,
        jq_filter=jq_filter,
    )


@anomalies_app.command("update")
@handle_errors
def anomalies_update(
    ctx: typer.Context,
    id: Annotated[
        int,
        typer.Option("--id", help="Anomaly ID to update."),
    ],
    status: Annotated[
        str,
        typer.Option("--status", help="New anomaly status."),
    ],
    anomaly_class: Annotated[
        str,
        typer.Option("--anomaly-class", help="Anomaly classification."),
    ],
    format: FormatOption = "json",
    jq_filter: JqOption = None,
) -> None:
    """Update a single data volume anomaly.

    Changes the status and classification of a specific anomaly by ID.

    Args:
        ctx: Typer context with global options.
        id: Anomaly ID (integer).
        status: New status value.
        anomaly_class: Anomaly classification string.
        format: Output format.
        jq_filter: Optional jq filter expression.
    """
    from mixpanel_headless.types import UpdateAnomalyParams

    params = UpdateAnomalyParams(id=id, status=status, anomaly_class=anomaly_class)
    workspace = get_workspace(ctx)
    with status_spinner(ctx, "Updating anomaly..."):
        result = workspace.update_anomaly(params)
    output_result(ctx, result, format=format, jq_filter=jq_filter)


@anomalies_app.command("bulk-update")
@handle_errors
def anomalies_bulk_update(
    ctx: typer.Context,
    body: Annotated[
        str,
        typer.Option(
            "--body",
            help="Bulk anomaly update payload as JSON string.",
        ),
    ],
    format: FormatOption = "json",
    jq_filter: JqOption = None,
) -> None:
    """Bulk-update data volume anomalies.

    Accepts a JSON string with parameters for updating multiple
    anomalies at once.

    Args:
        ctx: Typer context with global options.
        body: JSON string containing the bulk update payload.
        format: Output format.
        jq_filter: Optional jq filter expression.
    """
    from mixpanel_headless.types import BulkUpdateAnomalyParams

    try:
        parsed: dict[str, Any] = json.loads(body)
    except json.JSONDecodeError as exc:
        err_console.print(f"[red]Invalid JSON for --body:[/red] {exc}")
        raise typer.Exit(code=ExitCode.INVALID_ARGS) from None

    params = BulkUpdateAnomalyParams(**parsed)
    workspace = get_workspace(ctx)
    with status_spinner(ctx, "Bulk-updating anomalies..."):
        result = workspace.bulk_update_anomalies(params)
    output_result(ctx, result, format=format, jq_filter=jq_filter)


# =============================================================================
# Deletion Requests
# =============================================================================

deletion_requests_app = typer.Typer(
    name="deletion-requests",
    help="Manage event deletion requests.",
    no_args_is_help=True,
)
lexicon_app.add_typer(deletion_requests_app, name="deletion-requests")


@deletion_requests_app.command("list")
@handle_errors
def deletion_requests_list(
    ctx: typer.Context,
    format: FormatOption = "json",
    jq_filter: JqOption = None,
) -> None:
    """List event deletion requests.

    Retrieves all event deletion requests for the project.

    Args:
        ctx: Typer context with global options.
        format: Output format.
        jq_filter: Optional jq filter expression.
    """
    workspace = get_workspace(ctx)
    with status_spinner(ctx, "Fetching deletion requests..."):
        result = workspace.list_deletion_requests()
    output_result(
        ctx,
        [r.model_dump(by_alias=True) for r in result],
        format=format,
        jq_filter=jq_filter,
    )


@deletion_requests_app.command("create")
@handle_errors
def deletion_requests_create(
    ctx: typer.Context,
    event_name: Annotated[
        str,
        typer.Option("--event-name", help="Event name to delete data for."),
    ],
    from_date: Annotated[
        str,
        typer.Option("--from-date", help="Start date (YYYY-MM-DD)."),
    ],
    to_date: Annotated[
        str,
        typer.Option("--to-date", help="End date (YYYY-MM-DD)."),
    ],
    filters: Annotated[
        str | None,
        typer.Option(
            "--filters",
            help="Optional property filters as JSON string.",
        ),
    ] = None,
    format: FormatOption = "json",
    jq_filter: JqOption = None,
) -> None:
    """Create an event deletion request.

    Submits a request to delete event data matching the specified event
    name, date range, and optional property filters.

    Args:
        ctx: Typer context with global options.
        event_name: Event name to delete data for.
        from_date: Start date in YYYY-MM-DD format.
        to_date: End date in YYYY-MM-DD format.
        filters: Optional JSON string with property filters.
        format: Output format.
        jq_filter: Optional jq filter expression.
    """
    from mixpanel_headless.types import CreateDeletionRequestParams

    kwargs: dict[str, Any] = {
        "event_name": event_name,
        "from_date": from_date,
        "to_date": to_date,
    }
    if filters is not None:
        try:
            parsed_filters: Any = json.loads(filters)
        except json.JSONDecodeError as exc:
            err_console.print(f"[red]Invalid JSON for --filters:[/red] {exc}")
            raise typer.Exit(code=ExitCode.INVALID_ARGS) from None
        kwargs["filters"] = parsed_filters

    params = CreateDeletionRequestParams(**kwargs)
    workspace = get_workspace(ctx)
    with status_spinner(ctx, "Creating deletion request..."):
        result = workspace.create_deletion_request(params)
    output_result(
        ctx,
        [r.model_dump(by_alias=True) for r in result],
        format=format,
        jq_filter=jq_filter,
    )


@deletion_requests_app.command("cancel")
@handle_errors
def deletion_requests_cancel(
    ctx: typer.Context,
    id: Annotated[
        int,
        typer.Argument(help="Deletion request ID to cancel."),
    ],
    format: FormatOption = "json",
    jq_filter: JqOption = None,
) -> None:
    """Cancel a pending deletion request.

    Cancels a previously submitted deletion request by its ID. Only
    pending requests can be cancelled.

    Args:
        ctx: Typer context with global options.
        id: Deletion request ID (positional argument).
        format: Output format.
        jq_filter: Optional jq filter expression.
    """
    workspace = get_workspace(ctx)
    with status_spinner(ctx, "Cancelling deletion request..."):
        result = workspace.cancel_deletion_request(request_id=id)
    output_result(
        ctx,
        [r.model_dump(by_alias=True) for r in result],
        format=format,
        jq_filter=jq_filter,
    )


@deletion_requests_app.command("preview")
@handle_errors
def deletion_requests_preview(
    ctx: typer.Context,
    event_name: Annotated[
        str,
        typer.Option("--event-name", help="Event name to preview deletion for."),
    ],
    from_date: Annotated[
        str,
        typer.Option("--from-date", help="Start date (YYYY-MM-DD)."),
    ],
    to_date: Annotated[
        str,
        typer.Option("--to-date", help="End date (YYYY-MM-DD)."),
    ],
    filters: Annotated[
        str | None,
        typer.Option(
            "--filters",
            help="Optional property filters as JSON string.",
        ),
    ] = None,
    format: FormatOption = "json",
    jq_filter: JqOption = None,
) -> None:
    """Preview deletion filter results.

    Shows what data would be affected by a deletion request without
    actually creating one. Useful for validating filters before
    submitting a real deletion request.

    Args:
        ctx: Typer context with global options.
        event_name: Event name to preview deletion for.
        from_date: Start date in YYYY-MM-DD format.
        to_date: End date in YYYY-MM-DD format.
        filters: Optional JSON string with property filters.
        format: Output format.
        jq_filter: Optional jq filter expression.
    """
    from mixpanel_headless.types import PreviewDeletionFiltersParams

    kwargs: dict[str, Any] = {
        "event_name": event_name,
        "from_date": from_date,
        "to_date": to_date,
    }
    if filters is not None:
        try:
            parsed_filters: Any = json.loads(filters)
        except json.JSONDecodeError as exc:
            err_console.print(f"[red]Invalid JSON for --filters:[/red] {exc}")
            raise typer.Exit(code=ExitCode.INVALID_ARGS) from None
        kwargs["filters"] = parsed_filters

    params = PreviewDeletionFiltersParams(**kwargs)
    workspace = get_workspace(ctx)
    with status_spinner(ctx, "Previewing deletion filters..."):
        result = workspace.preview_deletion_filters(params)
    output_result(ctx, result, format=format, jq_filter=jq_filter)
