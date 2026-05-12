"""``mp workspace`` Typer command group.

Replaces ``mp workspaces`` with the singular form. Reference:
contracts/cli-commands.md §5.
"""

from __future__ import annotations

from typing import Annotated

import typer

from mixpanel_headless import session as session_ns
from mixpanel_headless.cli.utils import console, handle_errors

workspace_app = typer.Typer(
    name="workspace",
    help="Manage active Mixpanel workspace.",
    no_args_is_help=True,
)


@workspace_app.command("list")
@handle_errors
def list_workspaces(
    ctx: typer.Context,
    project: Annotated[
        str | None,
        typer.Option(
            "--project", "-p", help="Project ID (defaults to active project)."
        ),
    ] = None,
    refresh: Annotated[
        bool,
        typer.Option("--refresh", help="Bypass the local /me cache (FR-047)."),
    ] = False,
    format: Annotated[  # noqa: A002
        str,
        typer.Option("--format", "-f", help="Output format: table | json | jsonl."),
    ] = "table",
) -> None:
    """List workspaces in the current (or specified) project via /me.

    Constructs a short-lived :class:`Workspace` against the resolved
    session, then pulls the workspace list from the cached ``/me``
    response (24h TTL) for ``--project`` (or the active project when
    ``--project`` is omitted). ``--refresh`` bypasses the cache.

    Args:
        ctx: Typer context.
        project: Project to query (defaults to the active project).
        refresh: Bypass the local ``/me`` cache and refetch.
        format: Output format (``table`` / ``json`` / ``jsonl``).
    """
    from collections.abc import Sequence
    from typing import Any as _Any

    from mixpanel_headless.cli.formatters import emit_records
    from mixpanel_headless.workspace import Workspace

    with Workspace(project=project) as ws:
        workspaces = ws.workspaces(project_id=project, refresh=refresh)

    def _to_dict(w: _Any) -> dict[str, _Any]:
        return {"id": w.id, "name": w.name, "is_default": w.is_default}

    def _render_table(items: Sequence[_Any]) -> str:
        if not items:
            return "(no workspaces accessible via /me)"
        lines = ["ID              NAME                              DEFAULT"]
        for w in items:
            marker = "*" if w.is_default else ""
            name = (w.name or "")[:33]
            lines.append(f"{w.id:<15} {name:<33} {marker}")
        return "\n".join(lines)

    emit_records(
        workspaces,
        format=format,
        console=console,
        to_dict=_to_dict,
        table_renderer=_render_table,
    )


@workspace_app.command("use")
@handle_errors
def use_workspace(
    ctx: typer.Context,
    workspace_id: Annotated[
        int, typer.Argument(help="Numeric workspace ID (positive int).")
    ],
) -> None:
    """Set the active workspace ID.

    Args:
        ctx: Typer context.
        workspace_id: Mixpanel workspace ID (positive int).
    """
    session_ns.use(workspace=workspace_id)
    console.print(f"Active workspace: {workspace_id}")


@workspace_app.command("show")
@handle_errors
def show_workspace(ctx: typer.Context) -> None:
    """Show the currently active workspace.

    When the active workspace is unset, prints
    ``(workspace will be auto-resolved on first use)``.

    Args:
        ctx: Typer context.
    """
    active = session_ns.show()
    if active.workspace is None:
        console.print("(workspace will be auto-resolved on first use)")
    else:
        console.print(str(active.workspace))
