"""Report (bookmark) management commands.

This module provides commands for managing Mixpanel reports/bookmarks
via the App API:

- list: List bookmarks with optional type/ID filters
- create: Create a new bookmark
- get: Get a single bookmark by ID
- update: Update an existing bookmark
- delete: Delete a bookmark
- bulk-delete: Delete multiple bookmarks
- bulk-update: Update multiple bookmarks
- linked-dashboards: Get dashboard IDs linked to a bookmark
- dashboard-ids: Get dashboard IDs containing a bookmark
- history: Get bookmark change history
"""

from __future__ import annotations

import json
from typing import Annotated, cast

import typer

from mixpanel_headless.cli.options import FormatOption, JqOption
from mixpanel_headless.cli.utils import (
    err_console,
    get_workspace,
    handle_errors,
    output_result,
    status_spinner,
)

reports_app = typer.Typer(
    name="reports",
    help="Manage Mixpanel reports (bookmarks).",
    no_args_is_help=True,
)


@reports_app.command("list")
@handle_errors
def list_reports(
    ctx: typer.Context,
    bookmark_type: Annotated[
        str | None,
        typer.Option(
            "--type",
            "-t",
            help="Filter by bookmark type (e.g., insights, funnels, flows, retention).",
        ),
    ] = None,
    ids: Annotated[
        str | None,
        typer.Option(
            "--ids",
            help="Comma-separated list of bookmark IDs to retrieve.",
        ),
    ] = None,
    format: FormatOption = "json",
    jq_filter: JqOption = None,
) -> None:
    """List bookmarks/reports with optional filters.

    Retrieves bookmarks from the Mixpanel App API. Optionally filter by
    report type or specific IDs.

    Args:
        ctx: Typer context with global options.
        bookmark_type: Optional report type filter (e.g., ``"funnels"``).
        ids: Comma-separated bookmark IDs to filter by.
        format: Output format (json, jsonl, table, csv, plain).
        jq_filter: Optional jq filter expression for JSON output.

    Example:
        ```bash
        mp reports list --type funnels
        mp reports list --ids 1,2,3 --format table
        ```
    """
    workspace = get_workspace(ctx)
    parsed_ids: list[int] | None = None
    if ids:
        parsed_ids = [int(i.strip()) for i in ids.split(",")]
    from typing import get_args

    from mixpanel_headless.types import BookmarkType

    typed_bt: BookmarkType | None = None
    if bookmark_type:
        valid_types = get_args(BookmarkType)
        if bookmark_type not in valid_types:
            err_console.print(
                f"[red]Invalid --type:[/red] '{bookmark_type}'. "
                f"Valid types: {', '.join(valid_types)}"
            )
            raise typer.Exit(code=1)
        typed_bt = cast(BookmarkType, bookmark_type)
    with status_spinner(ctx, "Fetching bookmarks..."):
        bookmarks = workspace.list_bookmarks_v2(bookmark_type=typed_bt, ids=parsed_ids)
    output_result(
        ctx,
        [b.model_dump() for b in bookmarks],
        format=format,
        jq_filter=jq_filter,
    )


@reports_app.command("create")
@handle_errors
def create_report(
    ctx: typer.Context,
    name: Annotated[
        str,
        typer.Option("--name", "-n", help="Name for the new report."),
    ],
    bookmark_type: Annotated[
        str,
        typer.Option("--type", "-t", help="Report type (e.g., insights, funnels)."),
    ],
    params: Annotated[
        str,
        typer.Option(
            "--params",
            "-p",
            help="Report parameters as a JSON string.",
        ),
    ],
    description: Annotated[
        str | None,
        typer.Option("--description", "-d", help="Optional description."),
    ] = None,
    dashboard_id: Annotated[
        int | None,
        typer.Option("--dashboard-id", help="Dashboard ID to add the report to."),
    ] = None,
    format: FormatOption = "json",
    jq_filter: JqOption = None,
) -> None:
    """Create a new bookmark (saved report).

    Creates a bookmark in the Mixpanel App API with the given name,
    type, and query parameters.

    Args:
        ctx: Typer context with global options.
        name: Name for the new report.
        bookmark_type: Report type (e.g., ``"insights"``, ``"funnels"``).
        params: Report parameters as a JSON string.
        description: Optional description for the report.
        dashboard_id: Optional dashboard ID to add the report to.
        format: Output format (json, jsonl, table, csv, plain).
        jq_filter: Optional jq filter expression for JSON output.

    Example:
        ```bash
        mp reports create --name "Signup Funnel" --type funnels \\
            --params '{"events": [{"event": "Signup"}]}'
        ```
    """
    from mixpanel_headless.types import CreateBookmarkParams

    workspace = get_workspace(ctx)
    try:
        parsed_params = json.loads(params)
    except json.JSONDecodeError as exc:
        err_console.print(f"[red]Invalid JSON for --params:[/red] {exc.msg}")
        raise typer.Exit(code=1) from None
    create_params = CreateBookmarkParams(
        name=name,
        bookmark_type=bookmark_type,
        params=parsed_params,
        description=description,
        dashboard_id=dashboard_id,
    )
    with status_spinner(ctx, "Creating bookmark..."):
        bookmark = workspace.create_bookmark(create_params)
    output_result(
        ctx,
        bookmark.model_dump(),
        format=format,
        jq_filter=jq_filter,
    )


@reports_app.command("get")
@handle_errors
def get_report(
    ctx: typer.Context,
    bookmark_id: Annotated[
        int,
        typer.Argument(help="Bookmark ID to retrieve."),
    ],
    format: FormatOption = "json",
    jq_filter: JqOption = None,
) -> None:
    """Get a single bookmark by ID.

    Retrieves the full bookmark object from the Mixpanel App API.

    Args:
        ctx: Typer context with global options.
        bookmark_id: The bookmark identifier.
        format: Output format (json, jsonl, table, csv, plain).
        jq_filter: Optional jq filter expression for JSON output.

    Example:
        ```bash
        mp reports get 12345
        mp reports get 12345 --format table
        ```
    """
    workspace = get_workspace(ctx)
    with status_spinner(ctx, "Fetching bookmark..."):
        bookmark = workspace.get_bookmark(bookmark_id)
    output_result(
        ctx,
        bookmark.model_dump(),
        format=format,
        jq_filter=jq_filter,
    )


@reports_app.command("update")
@handle_errors
def update_report(
    ctx: typer.Context,
    bookmark_id: Annotated[
        int,
        typer.Argument(help="Bookmark ID to update."),
    ],
    name: Annotated[
        str | None,
        typer.Option("--name", "-n", help="New name for the report."),
    ] = None,
    params: Annotated[
        str | None,
        typer.Option(
            "--params",
            "-p",
            help="Updated report parameters as a JSON string.",
        ),
    ] = None,
    description: Annotated[
        str | None,
        typer.Option("--description", "-d", help="Updated description."),
    ] = None,
    format: FormatOption = "json",
    jq_filter: JqOption = None,
) -> None:
    """Update an existing bookmark.

    Patches the specified bookmark with the provided fields. Only
    supplied fields are updated; omitted fields remain unchanged.

    Args:
        ctx: Typer context with global options.
        bookmark_id: The bookmark identifier.
        name: New name for the report.
        params: Updated report parameters as a JSON string.
        description: Updated description.
        format: Output format (json, jsonl, table, csv, plain).
        jq_filter: Optional jq filter expression for JSON output.

    Example:
        ```bash
        mp reports update 12345 --name "Renamed Report"
        mp reports update 12345 --params '{"events": [{"event": "Login"}]}'
        ```
    """
    from mixpanel_headless.types import UpdateBookmarkParams

    workspace = get_workspace(ctx)
    if params:
        try:
            parsed_params = json.loads(params)
        except json.JSONDecodeError as exc:
            err_console.print(f"[red]Invalid JSON for --params:[/red] {exc.msg}")
            raise typer.Exit(code=1) from None
    else:
        parsed_params = None
    update_params = UpdateBookmarkParams(
        name=name,
        params=parsed_params,
        description=description,
    )
    with status_spinner(ctx, "Updating bookmark..."):
        bookmark = workspace.update_bookmark(bookmark_id, update_params)
    output_result(
        ctx,
        bookmark.model_dump(),
        format=format,
        jq_filter=jq_filter,
    )


@reports_app.command("delete")
@handle_errors
def delete_report(
    ctx: typer.Context,
    bookmark_id: Annotated[
        int,
        typer.Argument(help="Bookmark ID to delete."),
    ],
) -> None:
    """Delete a bookmark.

    Permanently removes the specified bookmark from the project.

    Args:
        ctx: Typer context with global options.
        bookmark_id: The bookmark identifier.

    Example:
        ```bash
        mp reports delete 12345
        ```
    """
    workspace = get_workspace(ctx)
    with status_spinner(ctx, "Deleting bookmark..."):
        workspace.delete_bookmark(bookmark_id)
    err_console.print(f"[green]Deleted bookmark {bookmark_id}.[/green]")


@reports_app.command("bulk-delete")
@handle_errors
def bulk_delete_reports(
    ctx: typer.Context,
    ids: Annotated[
        str,
        typer.Option(
            "--ids",
            help="Comma-separated list of bookmark IDs to delete.",
        ),
    ],
) -> None:
    """Delete multiple bookmarks at once.

    Permanently removes all specified bookmarks from the project.

    Args:
        ctx: Typer context with global options.
        ids: Comma-separated bookmark IDs to delete.

    Example:
        ```bash
        mp reports bulk-delete --ids 1,2,3
        ```
    """
    workspace = get_workspace(ctx)
    parsed_ids = [int(i.strip()) for i in ids.split(",")]
    with status_spinner(ctx, f"Deleting {len(parsed_ids)} bookmarks..."):
        workspace.bulk_delete_bookmarks(parsed_ids)
    err_console.print(f"[green]Deleted {len(parsed_ids)} bookmark(s).[/green]")


@reports_app.command("bulk-update")
@handle_errors
def bulk_update_reports(
    ctx: typer.Context,
    entries: Annotated[
        str,
        typer.Option(
            "--entries",
            "-e",
            help='JSON string: list of objects with "id" and fields to update.',
        ),
    ],
) -> None:
    """Update multiple bookmarks at once.

    Accepts a JSON array of update entries. Each entry must include
    an ``id`` field and any fields to update (e.g., ``name``).

    Args:
        ctx: Typer context with global options.
        entries: JSON string containing a list of update entries.

    Example:
        ```bash
        mp reports bulk-update --entries '[{"id": 1, "name": "Renamed"}]'
        ```
    """
    from mixpanel_headless.types import BulkUpdateBookmarkEntry

    workspace = get_workspace(ctx)
    try:
        parsed_entries = json.loads(entries)
    except json.JSONDecodeError as exc:
        err_console.print(f"[red]Invalid JSON for --entries:[/red] {exc.msg}")
        raise typer.Exit(code=1) from None
    entry_objs = [BulkUpdateBookmarkEntry.model_validate(e) for e in parsed_entries]
    with status_spinner(ctx, f"Updating {len(entry_objs)} bookmarks..."):
        workspace.bulk_update_bookmarks(entry_objs)
    err_console.print(f"[green]Updated {len(entry_objs)} bookmark(s).[/green]")


@reports_app.command("linked-dashboards")
@handle_errors
def linked_dashboards(
    ctx: typer.Context,
    bookmark_id: Annotated[
        int,
        typer.Argument(help="Bookmark ID to look up."),
    ],
    format: FormatOption = "json",
    jq_filter: JqOption = None,
) -> None:
    """Get dashboard IDs linked to a bookmark.

    Returns a list of dashboard IDs that reference the specified
    bookmark via the ``bookmark_linked_dashboard_ids`` API.

    Args:
        ctx: Typer context with global options.
        bookmark_id: The bookmark identifier.
        format: Output format (json, jsonl, table, csv, plain).
        jq_filter: Optional jq filter expression for JSON output.

    Example:
        ```bash
        mp reports linked-dashboards 12345
        ```
    """
    workspace = get_workspace(ctx)
    with status_spinner(ctx, "Fetching linked dashboards..."):
        dash_ids = workspace.bookmark_linked_dashboard_ids(bookmark_id)
    output_result(
        ctx,
        dash_ids,
        format=format,
        jq_filter=jq_filter,
    )


@reports_app.command("dashboard-ids")
@handle_errors
def dashboard_ids(
    ctx: typer.Context,
    bookmark_id: Annotated[
        int,
        typer.Argument(help="Bookmark ID to look up."),
    ],
    format: FormatOption = "json",
    jq_filter: JqOption = None,
) -> None:
    """Get dashboard IDs containing a bookmark.

    Returns a list of dashboard IDs that contain the specified
    bookmark. Uses the ``get_bookmark_dashboard_ids`` workspace method.

    Args:
        ctx: Typer context with global options.
        bookmark_id: The bookmark identifier.
        format: Output format (json, jsonl, table, csv, plain).
        jq_filter: Optional jq filter expression for JSON output.

    Example:
        ```bash
        mp reports dashboard-ids 12345
        ```
    """
    workspace = get_workspace(ctx)
    with status_spinner(ctx, "Fetching dashboard IDs..."):
        dash_ids = workspace.get_bookmark_dashboard_ids(bookmark_id)
    output_result(
        ctx,
        dash_ids,
        format=format,
        jq_filter=jq_filter,
    )


@reports_app.command("history")
@handle_errors
def report_history(
    ctx: typer.Context,
    bookmark_id: Annotated[
        int,
        typer.Argument(help="Bookmark ID to get history for."),
    ],
    cursor: Annotated[
        str | None,
        typer.Option("--cursor", help="Pagination cursor for next page."),
    ] = None,
    page_size: Annotated[
        int | None,
        typer.Option("--page-size", help="Maximum entries per page."),
    ] = None,
    format: FormatOption = "json",
    jq_filter: JqOption = None,
) -> None:
    """Get change history for a bookmark.

    Returns a paginated list of changes made to the specified bookmark,
    including who made the change and when.

    Args:
        ctx: Typer context with global options.
        bookmark_id: The bookmark identifier.
        cursor: Opaque pagination cursor for fetching subsequent pages.
        page_size: Maximum number of entries per page.
        format: Output format (json, jsonl, table, csv, plain).
        jq_filter: Optional jq filter expression for JSON output.

    Example:
        ```bash
        mp reports history 12345
        mp reports history 12345 --page-size 10
        mp reports history 12345 --cursor "abc123"
        ```
    """
    workspace = get_workspace(ctx)
    with status_spinner(ctx, "Fetching bookmark history..."):
        history = workspace.get_bookmark_history(
            bookmark_id, cursor=cursor, page_size=page_size
        )
    output_result(
        ctx,
        history.model_dump(),
        format=format,
        jq_filter=jq_filter,
    )
