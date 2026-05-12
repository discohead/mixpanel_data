"""Dashboard management commands.

This module provides commands for managing Mixpanel dashboards:

Basic CRUD:
- list: List dashboards for the current project
- create: Create a new dashboard
- get: Get a single dashboard by ID
- update: Update an existing dashboard
- delete: Delete a dashboard
- bulk-delete: Delete multiple dashboards

Organization:
- favorite: Favorite a dashboard
- unfavorite: Unfavorite a dashboard
- pin: Pin a dashboard
- unpin: Unpin a dashboard
- remove-report: Remove a report from a dashboard

Blueprints:
- blueprints: List available blueprint templates
- blueprint-create: Create a dashboard from a blueprint template

Advanced:
- rca: Create an RCA (Root Cause Analysis) dashboard
- erf: Get ERF metrics for a dashboard
- update-report-link: Update a report link on a dashboard
- update-text-card: Update a text card on a dashboard
"""

from __future__ import annotations

import json
from typing import Annotated, Any

import typer

from mixpanel_headless.cli.options import FormatOption, JqOption
from mixpanel_headless.cli.utils import (
    err_console,
    get_workspace,
    handle_errors,
    output_result,
    status_spinner,
)

dashboards_app = typer.Typer(
    name="dashboards",
    help="Manage Mixpanel dashboards.",
    no_args_is_help=True,
)


# =============================================================================
# Basic CRUD
# =============================================================================


@dashboards_app.command("list")
@handle_errors
def dashboards_list(
    ctx: typer.Context,
    ids: Annotated[
        str | None,
        typer.Option("--ids", help="Comma-separated dashboard IDs to filter by."),
    ] = None,
    format: FormatOption = "json",
    jq_filter: JqOption = None,
) -> None:
    """List dashboards for the current project.

    Retrieves all dashboards visible to the authenticated user,
    optionally filtered by specific IDs.

    Args:
        ctx: Typer context with global options.
        ids: Optional comma-separated dashboard IDs to filter by.
        format: Output format.
        jq_filter: Optional jq filter expression.
    """
    workspace = get_workspace(ctx)
    id_list = [int(x.strip()) for x in ids.split(",")] if ids else None
    with status_spinner(ctx, "Fetching dashboards..."):
        result = workspace.list_dashboards(ids=id_list)
    output_result(
        ctx,
        [d.model_dump() for d in result],
        format=format,
        jq_filter=jq_filter,
    )


@dashboards_app.command("create")
@handle_errors
def dashboards_create(
    ctx: typer.Context,
    title: Annotated[
        str,
        typer.Option("--title", help="Dashboard title."),
    ],
    description: Annotated[
        str | None,
        typer.Option("--description", help="Dashboard description."),
    ] = None,
    private: Annotated[
        bool | None,
        typer.Option("--private/--no-private", help="Set privacy (default: not set)."),
    ] = None,
    restricted: Annotated[
        bool | None,
        typer.Option(
            "--restricted/--no-restricted", help="Set restriction (default: not set)."
        ),
    ] = None,
    duplicate: Annotated[
        int | None,
        typer.Option("--duplicate", help="ID of dashboard to duplicate."),
    ] = None,
    format: FormatOption = "json",
    jq_filter: JqOption = None,
) -> None:
    """Create a new dashboard.

    Creates a dashboard with the specified title and optional settings.
    Use --duplicate to clone an existing dashboard.

    Args:
        ctx: Typer context with global options.
        title: Dashboard title (required).
        description: Optional dashboard description.
        private: Whether to make the dashboard private.
        restricted: Whether to restrict dashboard access.
        duplicate: ID of an existing dashboard to duplicate.
        format: Output format.
        jq_filter: Optional jq filter expression.
    """
    from mixpanel_headless.types import CreateDashboardParams

    params = CreateDashboardParams(
        title=title,
        description=description,
        is_private=private,
        is_restricted=restricted,
        duplicate=duplicate,
    )
    workspace = get_workspace(ctx)
    with status_spinner(ctx, "Creating dashboard..."):
        result = workspace.create_dashboard(params)
    output_result(ctx, result.model_dump(), format=format, jq_filter=jq_filter)


@dashboards_app.command("get")
@handle_errors
def dashboards_get(
    ctx: typer.Context,
    dashboard_id: Annotated[
        int,
        typer.Argument(help="Dashboard ID."),
    ],
    format: FormatOption = "json",
    jq_filter: JqOption = None,
) -> None:
    """Get a single dashboard by ID.

    Retrieves the full dashboard object including metadata,
    permissions, and layout.

    Args:
        ctx: Typer context with global options.
        dashboard_id: Dashboard identifier.
        format: Output format.
        jq_filter: Optional jq filter expression.
    """
    workspace = get_workspace(ctx)
    with status_spinner(ctx, "Fetching dashboard..."):
        result = workspace.get_dashboard(dashboard_id)
    output_result(ctx, result.model_dump(), format=format, jq_filter=jq_filter)


@dashboards_app.command("update")
@handle_errors
def dashboards_update(
    ctx: typer.Context,
    dashboard_id: Annotated[
        int,
        typer.Argument(help="Dashboard ID."),
    ],
    title: Annotated[
        str | None,
        typer.Option("--title", help="New dashboard title."),
    ] = None,
    description: Annotated[
        str | None,
        typer.Option("--description", help="New dashboard description."),
    ] = None,
    private: Annotated[
        bool | None,
        typer.Option("--private/--no-private", help="Set privacy."),
    ] = None,
    restricted: Annotated[
        bool | None,
        typer.Option("--restricted/--no-restricted", help="Set restriction."),
    ] = None,
    format: FormatOption = "json",
    jq_filter: JqOption = None,
) -> None:
    """Update an existing dashboard.

    Updates the specified fields on a dashboard. Only provided
    options are sent to the API; omitted fields are unchanged.

    Args:
        ctx: Typer context with global options.
        dashboard_id: Dashboard identifier.
        title: New title for the dashboard.
        description: New description for the dashboard.
        private: Set privacy (use --no-private to unset).
        restricted: Set restriction (use --no-restricted to unset).
        format: Output format.
        jq_filter: Optional jq filter expression.
    """
    from mixpanel_headless.types import UpdateDashboardParams

    params = UpdateDashboardParams(
        title=title,
        description=description,
        is_private=private,
        is_restricted=restricted,
    )
    workspace = get_workspace(ctx)
    with status_spinner(ctx, "Updating dashboard..."):
        result = workspace.update_dashboard(dashboard_id, params)
    output_result(ctx, result.model_dump(), format=format, jq_filter=jq_filter)


@dashboards_app.command("delete")
@handle_errors
def dashboards_delete(
    ctx: typer.Context,
    dashboard_id: Annotated[
        int,
        typer.Argument(help="Dashboard ID."),
    ],
) -> None:
    """Delete a dashboard.

    Permanently deletes a dashboard by ID. This action cannot be undone.

    Args:
        ctx: Typer context with global options.
        dashboard_id: Dashboard identifier.
    """
    workspace = get_workspace(ctx)
    with status_spinner(ctx, "Deleting dashboard..."):
        workspace.delete_dashboard(dashboard_id)
    err_console.print(f"[green]Deleted dashboard {dashboard_id}.[/green]")


@dashboards_app.command("bulk-delete")
@handle_errors
def dashboards_bulk_delete(
    ctx: typer.Context,
    ids: Annotated[
        str,
        typer.Option("--ids", help="Comma-separated dashboard IDs to delete."),
    ],
) -> None:
    """Delete multiple dashboards.

    Permanently deletes all specified dashboards. This action cannot be undone.

    Args:
        ctx: Typer context with global options.
        ids: Comma-separated dashboard IDs to delete (required).
    """
    id_list = [int(x.strip()) for x in ids.split(",")]
    workspace = get_workspace(ctx)
    with status_spinner(ctx, "Deleting dashboards..."):
        workspace.bulk_delete_dashboards(id_list)
    err_console.print(f"[green]Deleted {len(id_list)} dashboard(s).[/green]")


# =============================================================================
# Organization
# =============================================================================


@dashboards_app.command("favorite")
@handle_errors
def dashboards_favorite(
    ctx: typer.Context,
    dashboard_id: Annotated[
        int,
        typer.Argument(help="Dashboard ID."),
    ],
) -> None:
    """Favorite a dashboard.

    Marks the specified dashboard as a favorite for the current user.

    Args:
        ctx: Typer context with global options.
        dashboard_id: Dashboard identifier.
    """
    workspace = get_workspace(ctx)
    with status_spinner(ctx, "Favoriting dashboard..."):
        workspace.favorite_dashboard(dashboard_id)
    err_console.print(f"[green]Favorited dashboard {dashboard_id}.[/green]")


@dashboards_app.command("unfavorite")
@handle_errors
def dashboards_unfavorite(
    ctx: typer.Context,
    dashboard_id: Annotated[
        int,
        typer.Argument(help="Dashboard ID."),
    ],
) -> None:
    """Unfavorite a dashboard.

    Removes the specified dashboard from the current user's favorites.

    Args:
        ctx: Typer context with global options.
        dashboard_id: Dashboard identifier.
    """
    workspace = get_workspace(ctx)
    with status_spinner(ctx, "Unfavoriting dashboard..."):
        workspace.unfavorite_dashboard(dashboard_id)
    err_console.print(f"[green]Unfavorited dashboard {dashboard_id}.[/green]")


@dashboards_app.command("pin")
@handle_errors
def dashboards_pin(
    ctx: typer.Context,
    dashboard_id: Annotated[
        int,
        typer.Argument(help="Dashboard ID."),
    ],
) -> None:
    """Pin a dashboard.

    Pins the specified dashboard for the current project.

    Args:
        ctx: Typer context with global options.
        dashboard_id: Dashboard identifier.
    """
    workspace = get_workspace(ctx)
    with status_spinner(ctx, "Pinning dashboard..."):
        workspace.pin_dashboard(dashboard_id)
    err_console.print(f"[green]Pinned dashboard {dashboard_id}.[/green]")


@dashboards_app.command("unpin")
@handle_errors
def dashboards_unpin(
    ctx: typer.Context,
    dashboard_id: Annotated[
        int,
        typer.Argument(help="Dashboard ID."),
    ],
) -> None:
    """Unpin a dashboard.

    Unpins the specified dashboard from the current project.

    Args:
        ctx: Typer context with global options.
        dashboard_id: Dashboard identifier.
    """
    workspace = get_workspace(ctx)
    with status_spinner(ctx, "Unpinning dashboard..."):
        workspace.unpin_dashboard(dashboard_id)
    err_console.print(f"[green]Unpinned dashboard {dashboard_id}.[/green]")


@dashboards_app.command("remove-report")
@handle_errors
def dashboards_remove_report(
    ctx: typer.Context,
    dashboard_id: Annotated[
        int,
        typer.Argument(help="Dashboard ID."),
    ],
    bookmark_id: Annotated[
        int,
        typer.Argument(help="Bookmark/report ID to remove."),
    ],
    format: FormatOption = "json",
    jq_filter: JqOption = None,
) -> None:
    """Remove a report from a dashboard.

    Removes the specified bookmark/report from the dashboard and
    returns the updated dashboard.

    Args:
        ctx: Typer context with global options.
        dashboard_id: Dashboard identifier.
        bookmark_id: Bookmark/report identifier to remove.
        format: Output format.
        jq_filter: Optional jq filter expression.
    """
    workspace = get_workspace(ctx)
    with status_spinner(ctx, "Removing report from dashboard..."):
        result = workspace.remove_report_from_dashboard(dashboard_id, bookmark_id)
    output_result(ctx, result.model_dump(), format=format, jq_filter=jq_filter)


@dashboards_app.command("add-report")
@handle_errors
def dashboards_add_report(
    ctx: typer.Context,
    dashboard_id: Annotated[
        int,
        typer.Argument(help="Dashboard ID."),
    ],
    bookmark_id: Annotated[
        int,
        typer.Argument(help="Bookmark/report ID to add."),
    ],
    format: FormatOption = "json",
    jq_filter: JqOption = None,
) -> None:
    """Add a report to a dashboard.

    Clones the specified bookmark/report onto the dashboard and
    returns the updated dashboard.

    Args:
        ctx: Typer context with global options.
        dashboard_id: Dashboard identifier.
        bookmark_id: Bookmark/report identifier to add.
        format: Output format.
        jq_filter: Optional jq filter expression.
    """
    workspace = get_workspace(ctx)
    with status_spinner(ctx, "Adding report to dashboard..."):
        result = workspace.add_report_to_dashboard(dashboard_id, bookmark_id)
    output_result(ctx, result.model_dump(), format=format, jq_filter=jq_filter)


# =============================================================================
# Blueprints
# =============================================================================


@dashboards_app.command("blueprints")
@handle_errors
def dashboards_blueprints(
    ctx: typer.Context,
    include_reports: Annotated[
        bool,
        typer.Option("--include-reports", help="Include report details in templates."),
    ] = False,
    format: FormatOption = "json",
    jq_filter: JqOption = None,
) -> None:
    """List available dashboard blueprint templates.

    Retrieves the catalog of blueprint templates that can be used
    to create pre-configured dashboards.

    Args:
        ctx: Typer context with global options.
        include_reports: Whether to include report details.
        format: Output format.
        jq_filter: Optional jq filter expression.
    """
    workspace = get_workspace(ctx)
    with status_spinner(ctx, "Fetching blueprint templates..."):
        result = workspace.list_blueprint_templates(include_reports=include_reports)
    output_result(
        ctx,
        [t.model_dump() for t in result],
        format=format,
        jq_filter=jq_filter,
    )


@dashboards_app.command("blueprint-create")
@handle_errors
def dashboards_blueprint_create(
    ctx: typer.Context,
    template_type: Annotated[
        str,
        typer.Argument(help="Blueprint template type identifier."),
    ],
    format: FormatOption = "json",
    jq_filter: JqOption = None,
) -> None:
    """Create a dashboard from a blueprint template.

    Creates a new dashboard using the specified blueprint template type.

    Args:
        ctx: Typer context with global options.
        template_type: Blueprint template type identifier.
        format: Output format.
        jq_filter: Optional jq filter expression.
    """
    workspace = get_workspace(ctx)
    with status_spinner(ctx, "Creating blueprint dashboard..."):
        result = workspace.create_blueprint(template_type)
    output_result(ctx, result.model_dump(), format=format, jq_filter=jq_filter)


# =============================================================================
# Advanced
# =============================================================================


@dashboards_app.command("rca")
@handle_errors
def dashboards_rca(
    ctx: typer.Context,
    source_id: Annotated[
        int,
        typer.Option("--source-id", help="Source ID for RCA analysis."),
    ],
    source_data: Annotated[
        str,
        typer.Option(
            "--source-data",
            help='RCA source data as JSON string (e.g. \'{"type": "anomaly"}\').',
        ),
    ],
    format: FormatOption = "json",
    jq_filter: JqOption = None,
) -> None:
    """Create an RCA (Root Cause Analysis) dashboard.

    Creates a dashboard for root cause analysis using the specified
    source ID and source data configuration.

    Args:
        ctx: Typer context with global options.
        source_id: Source ID for RCA analysis (required).
        source_data: RCA source data as a JSON string (required).
        format: Output format.
        jq_filter: Optional jq filter expression.
    """
    from mixpanel_headless.types import CreateRcaDashboardParams, RcaSourceData

    try:
        parsed_data: dict[str, Any] = json.loads(source_data)
    except json.JSONDecodeError as exc:
        err_console.print(f"[red]Invalid JSON for --source-data:[/red] {exc.msg}")
        raise typer.Exit(code=1) from None
    rca_source = RcaSourceData.model_validate(parsed_data)
    params = CreateRcaDashboardParams(
        rca_source_id=source_id,
        rca_source_data=rca_source,
    )
    workspace = get_workspace(ctx)
    with status_spinner(ctx, "Creating RCA dashboard..."):
        result = workspace.create_rca_dashboard(params)
    output_result(ctx, result.model_dump(), format=format, jq_filter=jq_filter)


@dashboards_app.command("erf")
@handle_errors
def dashboards_erf(
    ctx: typer.Context,
    dashboard_id: Annotated[
        int,
        typer.Argument(help="Dashboard ID."),
    ],
    format: FormatOption = "json",
    jq_filter: JqOption = None,
) -> None:
    """Get ERF data for a dashboard.

    Retrieves the ERF metrics data associated with the specified dashboard.

    Args:
        ctx: Typer context with global options.
        dashboard_id: Dashboard identifier.
        format: Output format.
        jq_filter: Optional jq filter expression.
    """
    workspace = get_workspace(ctx)
    with status_spinner(ctx, "Fetching ERF metrics..."):
        result = workspace.get_dashboard_erf(dashboard_id)
    output_result(ctx, result, format=format, jq_filter=jq_filter)


@dashboards_app.command("update-report-link")
@handle_errors
def dashboards_update_report_link(
    ctx: typer.Context,
    dashboard_id: Annotated[
        int,
        typer.Argument(help="Dashboard ID."),
    ],
    report_link_id: Annotated[
        int,
        typer.Argument(help="Report link ID."),
    ],
    link_type: Annotated[
        str,
        typer.Option("--type", help="Link type (e.g. 'embedded')."),
    ],
) -> None:
    """Update a report link on a dashboard.

    Changes the type of a report link on the specified dashboard.

    Args:
        ctx: Typer context with global options.
        dashboard_id: Dashboard identifier.
        report_link_id: Report link identifier.
        link_type: Link type value (required).
    """
    from mixpanel_headless.types import UpdateReportLinkParams

    params = UpdateReportLinkParams(link_type=link_type)
    workspace = get_workspace(ctx)
    with status_spinner(ctx, "Updating report link..."):
        workspace.update_report_link(dashboard_id, report_link_id, params)
    err_console.print(
        f"[green]Updated report link {report_link_id} on dashboard {dashboard_id}.[/green]"
    )


@dashboards_app.command("update-text-card")
@handle_errors
def dashboards_update_text_card(
    ctx: typer.Context,
    dashboard_id: Annotated[
        int,
        typer.Argument(help="Dashboard ID."),
    ],
    text_card_id: Annotated[
        int,
        typer.Argument(help="Text card ID."),
    ],
    markdown: Annotated[
        str | None,
        typer.Option("--markdown", help="Markdown content for the text card."),
    ] = None,
) -> None:
    """Update a text card on a dashboard.

    Updates the markdown content of a text card on the specified dashboard.

    Args:
        ctx: Typer context with global options.
        dashboard_id: Dashboard identifier.
        text_card_id: Text card identifier.
        markdown: Markdown content for the text card.
    """
    from mixpanel_headless.types import UpdateTextCardParams

    params = UpdateTextCardParams(markdown=markdown)
    workspace = get_workspace(ctx)
    with status_spinner(ctx, "Updating text card..."):
        workspace.update_text_card(dashboard_id, text_card_id, params)
    err_console.print(
        f"[green]Updated text card {text_card_id} on dashboard {dashboard_id}.[/green]"
    )
