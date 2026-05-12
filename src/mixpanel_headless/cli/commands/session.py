"""``mp session`` Typer command.

Flat command (no subcommand by default — ``mp session`` prints the
active session state). With ``--bridge``, prints the bridge file source
(if any) instead.

Reference: contracts/cli-commands.md §7.
"""

from __future__ import annotations

import json as _json
from typing import Annotated

import typer

from mixpanel_headless import session as session_ns
from mixpanel_headless.cli.utils import console, handle_errors

session_app = typer.Typer(
    name="session",
    help="Show / update the active session.",
    invoke_without_command=True,
)


def _print_bridge_status(format: str) -> None:
    """Print bridge file source per § 7 of the CLI contract.

    Resolves the bridge via :func:`load_bridge` (honors ``MP_AUTH_FILE``
    + the default search paths) and prints either a one-line "no bridge
    found" message or a multi-line bridge summary (path, account,
    project/workspace pins, headers).

    Args:
        format: Output format; ``json`` emits the parsed bridge payload.
    """
    import os

    from mixpanel_headless._internal.auth.bridge import (
        default_bridge_search_paths,
        load_bridge,
    )

    bridge = load_bridge()
    if bridge is None:
        if format == "json":
            console.print(_json.dumps({"bridge": None}, indent=2))
            return
        console.print("No bridge file found.")
        return

    candidates = (
        [os.environ["MP_AUTH_FILE"]] if os.environ.get("MP_AUTH_FILE") else []
    ) + [str(p) for p in default_bridge_search_paths()]
    path = next((p for p in candidates if os.path.exists(p)), None)

    if format == "json":
        console.print(
            _json.dumps(
                {
                    "bridge": {
                        "path": path,
                        "version": bridge.version,
                        "account": {
                            "name": bridge.account.name,
                            "type": bridge.account.type,
                            "region": bridge.account.region,
                        },
                        "project": bridge.project,
                        "workspace": bridge.workspace,
                        "headers": dict(bridge.headers),
                    }
                },
                indent=2,
            )
        )
        return
    parts = [
        f"Bridge:    {path}",
        f"Account:   {bridge.account.name} ({bridge.account.type}, "
        f"{bridge.account.region}, source: bridge)",
        f"Project:   {bridge.project or '(from config/env)'}",
        f"Workspace: {bridge.workspace if bridge.workspace is not None else '(auto)'}",
    ]
    if bridge.headers:
        parts.append("Headers:")
        for k, v in sorted(bridge.headers.items()):
            parts.append(f"  {k}: {v}")
    console.print("\n".join(parts))


@session_app.callback()
@handle_errors
def session_command(
    ctx: typer.Context,
    bridge: Annotated[
        bool,
        typer.Option("--bridge", help="Show bridge file source (Cowork)."),
    ] = False,
    format: Annotated[  # noqa: A002
        str,
        typer.Option("--format", "-f", help="Output format: text | json"),
    ] = "text",
) -> None:
    """Print the persisted ``[active]`` session, or bridge state with ``--bridge``.

    Renders the contract-defined four-line summary (account / project /
    workspace / user) per ``contracts/cli-commands.md §7``: account is
    annotated with type+region; project and workspace are enriched with
    their human names from the ``/me`` cache; user identity is read from
    the same cache. The cache is consulted read-only — fields fall back
    to ``(uncached)`` rather than triggering a network call so the
    command stays fast offline.

    Args:
        ctx: Typer context.
        bridge: When True, show the bridge file source instead of ``[active]``.
        format: Output format.
    """
    if ctx.invoked_subcommand is not None:
        return  # let subcommands handle it (none currently)
    if bridge:
        _print_bridge_status(format)
        return

    from mixpanel_headless._internal.config import ConfigManager
    from mixpanel_headless._internal.me import MeCache
    from mixpanel_headless.exceptions import ConfigError

    active = session_ns.show()

    account_type: str | None = None
    account_region: str | None = None
    project_id: str | None = None
    project_name: str | None = None
    project_org: str | None = None
    workspace_id: int | None = active.workspace
    workspace_name: str | None = None
    user_email: str | None = None
    me_cached = False

    if active.account is not None:
        try:
            account_obj = ConfigManager().get_account(active.account)
        except ConfigError:
            account_obj = None
        if account_obj is not None:
            account_type = account_obj.type
            account_region = account_obj.region
            project_id = account_obj.default_project

            me = MeCache(account_name=active.account).get()
            if me is not None:
                me_cached = True
                if me.user_email is not None:
                    user_email = me.user_email
                if project_id is not None and project_id in me.projects:
                    proj_info = me.projects[project_id]
                    project_name = proj_info.name
                    org_id = proj_info.organization_id
                    org_info = me.organizations.get(str(org_id))
                    project_org = org_info.name if org_info is not None else str(org_id)
                if workspace_id is not None and str(workspace_id) in me.workspaces:
                    workspace_name = me.workspaces[str(workspace_id)].name

    if format == "json":
        payload: dict[str, object] = {
            "account": (
                None
                if active.account is None
                else {
                    "name": active.account,
                    "type": account_type,
                    "region": account_region,
                }
            ),
            "project": (
                None
                if project_id is None
                else {
                    "id": project_id,
                    "name": project_name,
                    "organization": project_org,
                }
            ),
            "workspace": (
                None
                if workspace_id is None
                else {
                    "id": workspace_id,
                    "name": workspace_name,
                }
            ),
            "user": {"email": user_email} if user_email is not None else None,
            "me_cached": me_cached,
        }
        console.print(_json.dumps(payload, indent=2))
        return

    def _project_line() -> str:
        """Render the contract-formatted ``Project:`` line."""
        if project_id is None:
            return "(none)"
        name = project_name or ("(uncached)" if not me_cached else "(unknown)")
        org_part = f" [organization: {project_org}]" if project_org else ""
        return f"{name} ({project_id}){org_part}"

    def _workspace_line() -> str:
        """Render the contract-formatted ``Workspace:`` line."""
        if workspace_id is None:
            return "auto-resolved on first workspace-scoped call"
        name = workspace_name or ("(uncached)" if not me_cached else "(unknown)")
        return f"{name} ({workspace_id})"

    def _account_line() -> str:
        """Render the contract-formatted ``Account:`` line."""
        if active.account is None:
            return "(none)"
        annotation = f" ({account_type}, {account_region})" if account_type else ""
        return f"{active.account}{annotation}"

    user_line = user_email if user_email is not None else "(uncached)"

    parts = [
        f"Account:   {_account_line()}",
        f"Project:   {_project_line()}",
        f"Workspace: {_workspace_line()}",
        f"User:      {user_line}",
    ]
    console.print("\n".join(parts))
