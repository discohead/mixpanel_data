"""Lookup table management commands.

This module provides commands for managing Mixpanel lookup tables:

- list: List lookup tables
- upload: Upload a CSV file as a new lookup table
- update: Update a lookup table
- delete: Delete lookup tables
- upload-url: Get a signed upload URL
- download: Download lookup table data
- download-url: Get a signed download URL
"""

from __future__ import annotations

from pathlib import Path
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

lookup_tables_app = typer.Typer(
    name="lookup-tables",
    help="Manage lookup tables.",
    no_args_is_help=True,
)


@lookup_tables_app.command("list")
@handle_errors
def lookup_tables_list(
    ctx: typer.Context,
    data_group_id: Annotated[
        int | None,
        typer.Option("--data-group-id", help="Filter by data group ID."),
    ] = None,
    format: FormatOption = "json",
    jq_filter: JqOption = None,
) -> None:
    """List lookup tables for the current project.

    Retrieves all lookup tables, optionally filtered by data group ID.

    Args:
        ctx: Typer context with global options.
        data_group_id: Optional filter by data group ID.
        format: Output format.
        jq_filter: Optional jq filter expression.
    """
    workspace = get_workspace(ctx)
    with status_spinner(ctx, "Fetching lookup tables..."):
        result = workspace.list_lookup_tables(data_group_id=data_group_id)
    output_result(
        ctx,
        [t.model_dump() for t in result],
        format=format,
        jq_filter=jq_filter,
    )


@lookup_tables_app.command("upload")
@handle_errors
def lookup_tables_upload(
    ctx: typer.Context,
    name: Annotated[
        str,
        typer.Option("--name", help="Table name (required)."),
    ],
    file: Annotated[
        str,
        typer.Option("--file", help="Path to CSV file to upload (required)."),
    ],
    data_group_id: Annotated[
        int | None,
        typer.Option(
            "--data-group-id", help="Data group ID (for replacing an existing table)."
        ),
    ] = None,
    format: FormatOption = "json",
    jq_filter: JqOption = None,
) -> None:
    """Upload a CSV file as a new lookup table.

    Performs a 3-step upload: obtains a signed URL, uploads the CSV,
    then registers the table.

    Args:
        ctx: Typer context with global options.
        name: Table name.
        file: Path to the local CSV file.
        data_group_id: Data group ID for replacing an existing table.
        format: Output format.
        jq_filter: Optional jq filter expression.
    """
    from mixpanel_headless.types import UploadLookupTableParams

    file_path = Path(file)
    if not file_path.exists():
        err_console.print(f"[red]File not found:[/red] {file}")
        raise typer.Exit(code=ExitCode.INVALID_ARGS) from None

    kwargs: dict[str, Any] = {
        "name": name,
        "file_path": str(file_path),
    }
    if data_group_id is not None:
        kwargs["data_group_id"] = data_group_id

    params = UploadLookupTableParams(**kwargs)
    workspace = get_workspace(ctx)
    with status_spinner(ctx, "Uploading lookup table..."):
        result = workspace.upload_lookup_table(params)
    output_result(ctx, result.model_dump(), format=format, jq_filter=jq_filter)


@lookup_tables_app.command("update")
@handle_errors
def lookup_tables_update(
    ctx: typer.Context,
    data_group_id: Annotated[
        int,
        typer.Option("--data-group-id", help="Data group ID (required)."),
    ],
    name: Annotated[
        str,
        typer.Option("--name", help="New table name (required)."),
    ],
    format: FormatOption = "json",
    jq_filter: JqOption = None,
) -> None:
    """Update a lookup table.

    Updates the name of an existing lookup table identified by its
    data group ID.

    Args:
        ctx: Typer context with global options.
        data_group_id: Data group ID of the lookup table.
        name: New table name.
        format: Output format.
        jq_filter: Optional jq filter expression.
    """
    from mixpanel_headless.types import UpdateLookupTableParams

    params = UpdateLookupTableParams(name=name)
    workspace = get_workspace(ctx)
    with status_spinner(ctx, "Updating lookup table..."):
        result = workspace.update_lookup_table(data_group_id, params)
    output_result(ctx, result.model_dump(), format=format, jq_filter=jq_filter)


@lookup_tables_app.command("delete")
@handle_errors
def lookup_tables_delete(
    ctx: typer.Context,
    data_group_ids: Annotated[
        str,
        typer.Option(
            "--data-group-ids",
            help="Comma-separated data group IDs to delete (required).",
        ),
    ],
) -> None:
    """Delete one or more lookup tables.

    Permanently deletes lookup tables by their data group IDs. Provide
    IDs as a comma-separated string.

    Args:
        ctx: Typer context with global options.
        data_group_ids: Comma-separated data group IDs.
    """
    try:
        id_list = [int(x.strip()) for x in data_group_ids.split(",") if x.strip()]
    except ValueError as exc:
        err_console.print(f"[red]Invalid data group IDs:[/red] {exc}")
        raise typer.Exit(code=ExitCode.INVALID_ARGS) from None

    if not id_list:
        err_console.print("[red]No valid data group IDs provided.[/red]")
        raise typer.Exit(code=ExitCode.INVALID_ARGS) from None

    workspace = get_workspace(ctx)
    with status_spinner(ctx, "Deleting lookup tables..."):
        workspace.delete_lookup_tables(id_list)
    err_console.print(f"[green]Deleted {len(id_list)} lookup table(s).[/green]")


@lookup_tables_app.command("upload-url")
@handle_errors
def lookup_tables_upload_url(
    ctx: typer.Context,
    content_type: Annotated[
        str,
        typer.Option("--content-type", help="MIME type of the file."),
    ] = "text/csv",
    format: FormatOption = "json",
    jq_filter: JqOption = None,
) -> None:
    """Get a signed URL for uploading lookup table data.

    Returns a signed upload URL, path, and key that can be used
    to upload data directly.

    Args:
        ctx: Typer context with global options.
        content_type: MIME type of the file to upload.
        format: Output format.
        jq_filter: Optional jq filter expression.
    """
    workspace = get_workspace(ctx)
    with status_spinner(ctx, "Fetching upload URL..."):
        result = workspace.get_lookup_upload_url(content_type)
    output_result(ctx, result.model_dump(), format=format, jq_filter=jq_filter)


@lookup_tables_app.command("download")
@handle_errors
def lookup_tables_download(
    ctx: typer.Context,
    data_group_id: Annotated[
        int,
        typer.Option("--data-group-id", help="Data group ID (required)."),
    ],
    file_name: Annotated[
        str | None,
        typer.Option("--file-name", help="Optional file name filter."),
    ] = None,
    limit: Annotated[
        int | None,
        typer.Option("--limit", help="Optional row limit."),
    ] = None,
    output: Annotated[
        str | None,
        typer.Option("--output", help="Output file path (writes CSV to file)."),
    ] = None,
) -> None:
    """Download lookup table data as CSV.

    Downloads the lookup table data. If --output is specified, writes
    the CSV to the given file path. Otherwise, prints CSV to stdout.

    Args:
        ctx: Typer context with global options.
        data_group_id: Data group ID of the lookup table.
        file_name: Optional file name filter.
        limit: Optional row limit.
        output: Output file path.
    """
    workspace = get_workspace(ctx)
    with status_spinner(ctx, "Downloading lookup table..."):
        csv_bytes = workspace.download_lookup_table(
            data_group_id, file_name=file_name, limit=limit
        )

    if output is not None:
        output_path = Path(output)
        output_path.write_bytes(csv_bytes)
        err_console.print(
            f"[green]Downloaded to {output_path} ({len(csv_bytes)} bytes).[/green]"
        )
    else:
        typer.echo(csv_bytes.decode("utf-8", errors="replace"))


@lookup_tables_app.command("download-url")
@handle_errors
def lookup_tables_download_url(
    ctx: typer.Context,
    data_group_id: Annotated[
        int,
        typer.Option("--data-group-id", help="Data group ID (required)."),
    ],
    format: FormatOption = "json",
    jq_filter: JqOption = None,
) -> None:
    """Get a signed download URL for a lookup table.

    Returns a signed URL that can be used to download the lookup
    table data directly.

    Args:
        ctx: Typer context with global options.
        data_group_id: Data group ID of the lookup table.
        format: Output format.
        jq_filter: Optional jq filter expression.
    """
    workspace = get_workspace(ctx)
    with status_spinner(ctx, "Fetching download URL..."):
        url = workspace.get_lookup_download_url(data_group_id)
    output_result(ctx, {"url": url}, format=format, jq_filter=jq_filter)
