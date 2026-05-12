"""Custom event management commands.

This module provides commands for managing Mixpanel custom events:

- list: List all custom events
- create: Create a new custom event aliasing one or more underlying events
- update: Update a custom event definition
- delete: Delete a custom event
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated, Any

import typer
from pydantic import ValidationError

from mixpanel_headless.cli.options import FormatOption, JqOption
from mixpanel_headless.cli.utils import (
    err_console,
    get_workspace,
    handle_errors,
    output_result,
    status_spinner,
)

if TYPE_CHECKING:
    from mixpanel_headless.workspace import Workspace

custom_events_app = typer.Typer(
    name="custom-events",
    help="Manage custom events.",
    no_args_is_help=True,
)


def _resolve_custom_event_id_from_name(workspace: Workspace, name: str) -> int:
    """Resolve a custom event display name to its ``custom_event_id``.

    Loads the custom-event lexicon via :meth:`Workspace.list_custom_events`
    and filters by ``name``, ignoring auto-derived orphan entries
    (``custom_event_id is None`` or ``== 0`` — Mixpanel's sentinel for
    entries that don't link back to a real custom event).

    Args:
        workspace: Workspace to query.
        name: Display name of the custom event.

    Returns:
        The unique ``custom_event_id`` for the named custom event.

    Raises:
        typer.BadParameter: Zero matches, all matches are orphan entries,
            or multiple distinct custom events share the name.
    """
    all_named = [e for e in workspace.list_custom_events() if e.name == name]
    # Filter on `> 0` (not just truthiness) because customEventId=0 is
    # Mixpanel's sentinel for orphan / auto-derived lexicon entries — never
    # a valid custom event id.
    matches = [
        e for e in all_named if e.custom_event_id is not None and e.custom_event_id > 0
    ]
    if not matches:
        if all_named:
            count = len(all_named)
            noun = "entry" if count == 1 else "entries"
            raise typer.BadParameter(
                f"Found {count} lexicon {noun} named {name!r} but none have "
                f"a valid custom_event_id (likely orphan / auto-derived "
                f"entries). Use --id with the desired entry's id directly."
            )
        raise typer.BadParameter(f"No custom event found with name {name!r}.")
    if len(matches) > 1:
        ids = sorted(
            e.custom_event_id for e in matches if e.custom_event_id is not None
        )
        raise typer.BadParameter(
            f"Multiple custom events named {name!r} (ids: {ids}). "
            f"Use --id to disambiguate."
        )
    resolved_id = matches[0].custom_event_id
    assert resolved_id is not None  # narrowed by filter above
    return resolved_id


@custom_events_app.command("list")
@handle_errors
def custom_events_list(
    ctx: typer.Context,
    format: FormatOption = "json",
    jq_filter: JqOption = None,
) -> None:
    """List all custom events for the current project.

    Retrieves all custom event definitions in the project.

    Args:
        ctx: Typer context with global options.
        format: Output format.
        jq_filter: Optional jq filter expression.
    """
    workspace = get_workspace(ctx)
    with status_spinner(ctx, "Fetching custom events..."):
        result = workspace.list_custom_events()
    output_result(
        ctx,
        [e.model_dump() for e in result],
        format=format,
        jq_filter=jq_filter,
    )


@custom_events_app.command("create")
@handle_errors
def custom_events_create(
    ctx: typer.Context,
    name: Annotated[
        str,
        typer.Option("--name", help="Display name for the new custom event."),
    ],
    alternative: Annotated[
        list[str],
        typer.Option(
            "--alternative",
            help=(
                "Underlying event name to alias. Pass --alternative "
                "multiple times to alias more than one event."
            ),
        ),
    ],
    format: FormatOption = "json",
    jq_filter: JqOption = None,
) -> None:
    """Create a new custom event.

    A custom event aliases one or more underlying events under a single
    display name. For example::

        mp custom-events create --name "Page View" \\
            --alternative "Home Viewed" --alternative "Product Viewed"

    Args:
        ctx: Typer context with global options.
        name: Display name for the new custom event.
        alternative: Underlying event names to alias. Repeatable.
        format: Output format.
        jq_filter: Optional jq filter expression.
    """
    from mixpanel_headless.types import CreateCustomEventParams

    try:
        params = CreateCustomEventParams(name=name, alternatives=alternative)
    except ValidationError as e:
        # Surface user-input validation as a Typer-style argument error
        # rather than handle_errors's "API response parsing error", which
        # is misleading for client-side input that never reached the API.
        raise typer.BadParameter(str(e)) from e
    workspace = get_workspace(ctx)
    with status_spinner(ctx, "Creating custom event..."):
        result = workspace.create_custom_event(params)
    output_result(ctx, result.model_dump(), format=format, jq_filter=jq_filter)


@custom_events_app.command("update")
@handle_errors
def custom_events_update(
    ctx: typer.Context,
    custom_event_id: Annotated[
        int | None,
        typer.Option(
            "--id",
            "--custom-event-id",
            help="Custom event ID. Use this OR --name. Prefer --id when known.",
        ),
    ] = None,
    name: Annotated[
        str | None,
        typer.Option(
            "--name",
            help=(
                "Custom event name. Resolved to an ID via list_custom_events; "
                "errors if zero or multiple custom events share the name."
            ),
        ),
    ] = None,
    hidden: Annotated[
        bool | None,
        typer.Option("--hidden/--no-hidden", help="Hide or show the event."),
    ] = None,
    dropped: Annotated[
        bool | None,
        typer.Option("--dropped/--no-dropped", help="Drop or undrop the event."),
    ] = None,
    description: Annotated[
        str | None,
        typer.Option("--description", help="New event description."),
    ] = None,
    verified: Annotated[
        bool | None,
        typer.Option("--verified/--no-verified", help="Mark as verified or not."),
    ] = None,
    format: FormatOption = "json",
    jq_filter: JqOption = None,
) -> None:
    """Update a custom event's lexicon entry.

    Identify the custom event by either ``--id`` (preferred) or ``--name``.
    Name lookup uses :meth:`Workspace.list_custom_events` and errors if the
    name is ambiguous or unknown.

    Args:
        ctx: Typer context with global options.
        custom_event_id: Custom event ID. Mutually exclusive with name.
        name: Custom event name. Resolved to an ID via list_custom_events.
        hidden: Hide or show the event.
        dropped: Drop or undrop the event.
        description: New event description.
        verified: Mark as verified or not.
        format: Output format.
        jq_filter: Optional jq filter expression.
    """
    from mixpanel_headless.types import UpdateEventDefinitionParams

    if custom_event_id is None and name is None:
        raise typer.BadParameter("Must specify --id or --name.")
    if custom_event_id is not None and name is not None:
        raise typer.BadParameter("Specify --id or --name, not both.")

    kwargs: dict[str, Any] = {}
    if hidden is not None:
        kwargs["hidden"] = hidden
    if dropped is not None:
        kwargs["dropped"] = dropped
    if description is not None:
        kwargs["description"] = description
    if verified is not None:
        kwargs["verified"] = verified

    try:
        params = UpdateEventDefinitionParams(**kwargs)
    except ValidationError as e:
        # Surface user-input validation as a Typer-style argument error
        # rather than handle_errors's "API response parsing error", which
        # is misleading for client-side input that never reached the API.
        raise typer.BadParameter(str(e)) from e
    workspace = get_workspace(ctx)

    if custom_event_id is None:
        assert name is not None  # narrowed by mutual-exclusion check above
        with status_spinner(ctx, f"Resolving custom event {name!r}..."):
            custom_event_id = _resolve_custom_event_id_from_name(workspace, name)

    with status_spinner(ctx, "Updating custom event..."):
        result = workspace.update_custom_event(custom_event_id, params)
    output_result(ctx, result.model_dump(), format=format, jq_filter=jq_filter)


@custom_events_app.command("delete")
@handle_errors
def custom_events_delete(
    ctx: typer.Context,
    custom_event_id: Annotated[
        int | None,
        typer.Option(
            "--id",
            "--custom-event-id",
            help="Custom event ID. Use this OR --name. Prefer --id when known.",
        ),
    ] = None,
    name: Annotated[
        str | None,
        typer.Option(
            "--name",
            help=(
                "Custom event name. Resolved to an ID via list_custom_events; "
                "errors if zero or multiple custom events share the name."
            ),
        ),
    ] = None,
) -> None:
    """Delete a custom event.

    Identify the custom event by either ``--id`` (preferred) or ``--name``.
    Name lookup uses :meth:`Workspace.list_custom_events` and errors if the
    name is ambiguous or unknown. The DELETE always targets the resolved
    ``custom_event_id`` so the data-definitions endpoint cannot silently
    delete the wrong entry or a stray orphan lexicon row.

    Permanently deletes a custom event. This action cannot be undone.

    Args:
        ctx: Typer context with global options.
        custom_event_id: Custom event ID. Mutually exclusive with name.
        name: Custom event name. Resolved to an ID via list_custom_events.
    """
    if custom_event_id is None and name is None:
        raise typer.BadParameter("Must specify --id or --name.")
    if custom_event_id is not None and name is not None:
        raise typer.BadParameter("Specify --id or --name, not both.")

    workspace = get_workspace(ctx)

    if custom_event_id is None:
        assert name is not None  # narrowed by mutual-exclusion check above
        with status_spinner(ctx, f"Resolving custom event {name!r}..."):
            custom_event_id = _resolve_custom_event_id_from_name(workspace, name)

    with status_spinner(ctx, "Deleting custom event..."):
        workspace.delete_custom_event(custom_event_id)
    err_console.print(f"[green]Deleted custom event id={custom_event_id}.[/green]")
