"""Cohort management commands.

This module provides CRUD commands for managing Mixpanel cohorts via the
App API:

- list: List cohorts with optional filters
- create: Create a new cohort
- get: Get a single cohort by ID
- update: Update an existing cohort
- delete: Delete a single cohort
- bulk-delete: Delete multiple cohorts
- bulk-update: Update multiple cohorts
"""

from __future__ import annotations

import json
from typing import Annotated

import typer

from mixpanel_headless.cli.options import FormatOption, JqOption
from mixpanel_headless.cli.utils import (
    err_console,
    get_workspace,
    handle_errors,
    output_result,
    status_spinner,
)

cohorts_app = typer.Typer(
    name="cohorts",
    help="Manage Mixpanel cohorts.",
    no_args_is_help=True,
)


@cohorts_app.command("list")
@handle_errors
def list_cohorts(
    ctx: typer.Context,
    data_group_id: Annotated[
        str | None,
        typer.Option(
            "--data-group-id",
            help="Filter cohorts by data group ID.",
        ),
    ] = None,
    ids: Annotated[
        str | None,
        typer.Option(
            "--ids",
            help="Comma-separated list of cohort IDs to filter by.",
        ),
    ] = None,
    format: FormatOption = "json",
    jq_filter: JqOption = None,
) -> None:
    """List cohorts from the Mixpanel App API.

    Returns full cohort objects with all metadata. Optionally filter
    by data group ID or a specific set of cohort IDs.

    Args:
        ctx: Typer context with global options.
        data_group_id: Optional data group filter.
        ids: Comma-separated cohort IDs to retrieve.
        format: Output format (json, jsonl, table, csv, plain).
        jq_filter: Optional jq filter for JSON output.
    """
    workspace = get_workspace(ctx)

    parsed_ids: list[int] | None = None
    if ids is not None:
        parsed_ids = [int(i.strip()) for i in ids.split(",")]

    with status_spinner(ctx, "Listing cohorts..."):
        cohorts = workspace.list_cohorts_full(
            data_group_id=data_group_id,
            ids=parsed_ids,
        )

    output_result(
        ctx,
        [c.model_dump() for c in cohorts],
        format=format,
        jq_filter=jq_filter,
    )


@cohorts_app.command("create")
@handle_errors
def create_cohort(
    ctx: typer.Context,
    name: Annotated[
        str,
        typer.Option(
            "--name",
            help="Cohort name (required).",
        ),
    ],
    description: Annotated[
        str | None,
        typer.Option(
            "--description",
            help="Cohort description.",
        ),
    ] = None,
    data_group_id: Annotated[
        str | None,
        typer.Option(
            "--data-group-id",
            help="Data group identifier.",
        ),
    ] = None,
    definition: Annotated[
        str | None,
        typer.Option(
            "--definition",
            help="Cohort definition as a JSON string.",
        ),
    ] = None,
    format: FormatOption = "json",
    jq_filter: JqOption = None,
) -> None:
    """Create a new cohort.

    Creates a cohort with the given name and optional description,
    data group, and behavioral definition.

    Args:
        ctx: Typer context with global options.
        name: Cohort name.
        description: Optional cohort description.
        data_group_id: Optional data group identifier.
        definition: Optional cohort definition as a JSON string.
        format: Output format (json, jsonl, table, csv, plain).
        jq_filter: Optional jq filter for JSON output.
    """
    from mixpanel_headless.types import CreateCohortParams

    parsed_definition: dict[str, object] | None = None
    if definition is not None:
        try:
            parsed_definition = json.loads(definition)
        except json.JSONDecodeError as exc:
            err_console.print(f"[red]Invalid JSON for --definition:[/red] {exc.msg}")
            raise typer.Exit(code=1) from None

    params = CreateCohortParams(
        name=name,
        description=description,
        data_group_id=data_group_id,
        definition=parsed_definition,
    )

    workspace = get_workspace(ctx)

    with status_spinner(ctx, "Creating cohort..."):
        cohort = workspace.create_cohort(params)

    output_result(
        ctx,
        cohort.model_dump(),
        format=format,
        jq_filter=jq_filter,
    )


@cohorts_app.command("get")
@handle_errors
def get_cohort(
    ctx: typer.Context,
    cohort_id: Annotated[
        int,
        typer.Argument(help="Cohort ID to retrieve."),
    ],
    format: FormatOption = "json",
    jq_filter: JqOption = None,
) -> None:
    """Get a single cohort by ID.

    Retrieves full cohort details including metadata, definition,
    and creator information.

    Args:
        ctx: Typer context with global options.
        cohort_id: The cohort identifier.
        format: Output format (json, jsonl, table, csv, plain).
        jq_filter: Optional jq filter for JSON output.
    """
    workspace = get_workspace(ctx)

    with status_spinner(ctx, "Fetching cohort..."):
        cohort = workspace.get_cohort(cohort_id)

    output_result(
        ctx,
        cohort.model_dump(),
        format=format,
        jq_filter=jq_filter,
    )


@cohorts_app.command("update")
@handle_errors
def update_cohort(
    ctx: typer.Context,
    cohort_id: Annotated[
        int,
        typer.Argument(help="Cohort ID to update."),
    ],
    name: Annotated[
        str | None,
        typer.Option(
            "--name",
            help="New cohort name.",
        ),
    ] = None,
    description: Annotated[
        str | None,
        typer.Option(
            "--description",
            help="New cohort description.",
        ),
    ] = None,
    definition: Annotated[
        str | None,
        typer.Option(
            "--definition",
            help="New cohort definition as a JSON string.",
        ),
    ] = None,
    format: FormatOption = "json",
    jq_filter: JqOption = None,
) -> None:
    """Update an existing cohort.

    Updates the specified cohort with any provided fields. Only fields
    that are explicitly set will be sent to the API.

    Args:
        ctx: Typer context with global options.
        cohort_id: The cohort identifier.
        name: Optional new cohort name.
        description: Optional new cohort description.
        definition: Optional new cohort definition as a JSON string.
        format: Output format (json, jsonl, table, csv, plain).
        jq_filter: Optional jq filter for JSON output.
    """
    from mixpanel_headless.types import UpdateCohortParams

    parsed_definition: dict[str, object] | None = None
    if definition is not None:
        try:
            parsed_definition = json.loads(definition)
        except json.JSONDecodeError as exc:
            err_console.print(f"[red]Invalid JSON for --definition:[/red] {exc.msg}")
            raise typer.Exit(code=1) from None

    params = UpdateCohortParams(
        name=name,
        description=description,
        definition=parsed_definition,
    )

    workspace = get_workspace(ctx)

    with status_spinner(ctx, "Updating cohort..."):
        cohort = workspace.update_cohort(cohort_id, params)

    output_result(
        ctx,
        cohort.model_dump(),
        format=format,
        jq_filter=jq_filter,
    )


@cohorts_app.command("delete")
@handle_errors
def delete_cohort(
    ctx: typer.Context,
    cohort_id: Annotated[
        int,
        typer.Argument(help="Cohort ID to delete."),
    ],
) -> None:
    """Delete a single cohort.

    Permanently removes the cohort with the given ID.

    Args:
        ctx: Typer context with global options.
        cohort_id: The cohort identifier.
    """
    workspace = get_workspace(ctx)

    with status_spinner(ctx, "Deleting cohort..."):
        workspace.delete_cohort(cohort_id)

    err_console.print(f"[green]Deleted cohort {cohort_id}.[/green]")


@cohorts_app.command("bulk-delete")
@handle_errors
def bulk_delete_cohorts(
    ctx: typer.Context,
    ids: Annotated[
        str,
        typer.Option(
            "--ids",
            help="Comma-separated list of cohort IDs to delete (required).",
        ),
    ],
) -> None:
    """Delete multiple cohorts at once.

    Permanently removes all cohorts whose IDs are provided.

    Args:
        ctx: Typer context with global options.
        ids: Comma-separated cohort IDs to delete.
    """
    parsed_ids = [int(i.strip()) for i in ids.split(",")]
    workspace = get_workspace(ctx)

    with status_spinner(ctx, "Deleting cohorts..."):
        workspace.bulk_delete_cohorts(parsed_ids)

    err_console.print(f"[green]Deleted {len(parsed_ids)} cohort(s).[/green]")


@cohorts_app.command("bulk-update")
@handle_errors
def bulk_update_cohorts(
    ctx: typer.Context,
    entries: Annotated[
        str,
        typer.Option(
            "--entries",
            help=(
                "JSON string containing a list of cohort update entries. "
                'Each entry must have an "id" field and optional "name", '
                '"description", and "definition" fields.'
            ),
        ),
    ],
) -> None:
    """Update multiple cohorts at once.

    Accepts a JSON array of update entries. Each entry must include an
    ``id`` field and may include ``name``, ``description``, and
    ``definition`` fields.

    Args:
        ctx: Typer context with global options.
        entries: JSON string with a list of update entries.

    Example usage::

        mp cohorts bulk-update --entries '[{"id": 1, "name": "Renamed"}]'
    """
    from mixpanel_headless.types import BulkUpdateCohortEntry

    try:
        raw_entries: list[dict[str, object]] = json.loads(entries)
    except json.JSONDecodeError as exc:
        err_console.print(f"[red]Invalid JSON for --entries:[/red] {exc.msg}")
        raise typer.Exit(code=1) from None
    parsed_entries = [BulkUpdateCohortEntry.model_validate(e) for e in raw_entries]

    workspace = get_workspace(ctx)

    with status_spinner(ctx, "Updating cohorts..."):
        workspace.bulk_update_cohorts(parsed_entries)

    err_console.print(f"[green]Updated {len(parsed_entries)} cohort(s).[/green]")
