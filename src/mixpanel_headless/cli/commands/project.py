"""``mp project`` Typer command group.

Replaces ``mp projects`` with the singular form. Three subcommands:
``list``, ``use``, ``show``. Note: project lives on the active account as
``Account.default_project`` (FR-012); ``mp project use ID`` updates that
field rather than writing to ``[active]``. Reference:
contracts/cli-commands.md §4.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING, Annotated, Any

import typer

from mixpanel_headless import session as session_ns
from mixpanel_headless._internal.config import ConfigManager
from mixpanel_headless.cli.utils import (
    ExitCode,
    console,
    err_console,
    handle_errors,
)
from mixpanel_headless.exceptions import ConfigError

if TYPE_CHECKING:
    from mixpanel_headless.workspace import Workspace

project_app = typer.Typer(
    name="project",
    help="Manage active Mixpanel project.",
    no_args_is_help=True,
)


def _active_account_default_project() -> tuple[str | None, str | None]:
    """Return ``(active_account_name, default_project)`` or ``(None, None)``.

    Returns:
        Tuple of (active account name, the account's default_project).
        Each element is ``None`` when not configured.
    """
    active = session_ns.show()
    if active.account is None:
        return (None, None)
    try:
        account = ConfigManager().get_account(active.account)
    except ConfigError:
        return (active.account, None)
    return (active.account, account.default_project)


def _open_account_scoped_workspace() -> Workspace:
    """Build a Workspace tolerant of a missing project axis.

    ``/me`` is account-scoped, so ``mp project list`` MUST work when
    only auth is configured (FR-047). The standard ``Workspace()``
    resolver requires a project, so when none is available we fall
    back to a probe Session with a placeholder project ID — same
    pattern as ``accounts.login()``'s ``/me`` probe.

    Returns:
        A Workspace bound to the resolved account; project axis may be
        a placeholder (``"0"``) when none is configured.

    Raises:
        ConfigError: No account could be resolved from any source.
    """
    from mixpanel_headless._internal.auth.bridge import load_bridge
    from mixpanel_headless._internal.auth.resolver import (
        resolve_account_axis,
        resolve_session,
    )
    from mixpanel_headless._internal.auth.session import Project, Session
    from mixpanel_headless.workspace import Workspace

    cm = ConfigManager()
    bridge = load_bridge()
    try:
        return Workspace(session=resolve_session(config=cm, bridge=bridge))
    except ConfigError:
        # Resolver failed — most likely the project axis is missing.
        # Re-resolve account alone; if that also fails, surface the
        # original "no account" error to the caller.
        account = resolve_account_axis(
            explicit=None,
            target_account_name=None,
            bridge=bridge,
            config=cm,
        )
        if account is None:
            raise
        probe = Session(account=account, project=Project(id="0"))
        return Workspace(session=probe)


@project_app.command("list")
@handle_errors
def list_projects(
    ctx: typer.Context,
    refresh: Annotated[
        bool,
        typer.Option(
            "--refresh",
            help="Bypass the local /me cache and refetch.",
        ),
    ] = False,
    format: Annotated[  # noqa: A002
        str,
        typer.Option(
            "--format",
            "-f",
            help="Output format: table | json | jsonl.",
        ),
    ] = "table",
) -> None:
    """List projects accessible by the active account.

    Always enumerates from ``/me`` (24h cached). The active project is
    marked. ``--refresh`` bypasses the local cache and refetches. Works
    with only authentication configured — no project axis required
    (FR-047).

    Args:
        ctx: Typer context.
        refresh: Bypass the local /me cache and refetch.
        format: Output format (``table`` / ``json`` / ``jsonl``).
    """
    from mixpanel_headless.cli.formatters import emit_records

    _, active_project = _active_account_default_project()

    with _open_account_scoped_workspace() as ws:
        projects = ws.projects(refresh=refresh)

    def _to_dict(p: Any) -> dict[str, Any]:
        return {
            "id": p.id,
            "name": p.name,
            "organization_id": p.organization_id,
            "timezone": p.timezone,
            "is_active": p.id == active_project,
        }

    def _render_table(items: Sequence[Any]) -> str:
        if not items:
            return "(no projects accessible via /me)"
        lines = ["  ID              NAME                              ORG"]
        for p in items:
            marker = "*" if p.id == active_project else " "
            name = (p.name or "")[:33]
            lines.append(f"{marker} {p.id:<15} {name:<33} {p.organization_id}")
        return "\n".join(lines)

    emit_records(
        projects,
        format=format,
        console=console,
        to_dict=_to_dict,
        table_renderer=_render_table,
    )


@project_app.command("use")
@handle_errors
def use_project(
    ctx: typer.Context,
    project_id: Annotated[str, typer.Argument(help="Numeric Mixpanel project ID.")],
) -> None:
    """Update the active account's ``default_project``.

    Project lives on the account, not in ``[active]``. This command is
    equivalent to ``mp account update <active-account> --project ID``.

    Args:
        ctx: Typer context.
        project_id: Mixpanel project ID (numeric string).
    """
    active = session_ns.show()
    if active.account is None:
        err_console.print(
            "[red]No active account configured.[/red] Run `mp account use NAME` first."
        )
        raise typer.Exit(ExitCode.NOT_FOUND)
    ConfigManager().update_account(active.account, default_project=project_id)
    console.print(
        f"Set default_project for account '{active.account}' to '{project_id}'"
    )


@project_app.command("show")
@handle_errors
def show_project(ctx: typer.Context) -> None:
    """Show the currently active project (active account's ``default_project``).

    Args:
        ctx: Typer context.
    """
    _account, project = _active_account_default_project()
    if project is None:
        console.print("(no active project)")
    else:
        console.print(project)
