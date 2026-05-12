"""``mp target`` Typer command group.

Targets are saved (account, project, workspace?) triples used as named
cursor positions. ``mp target use ecom`` swaps all three axes in
``[active]`` atomically (and updates the target account's
``default_project``) — no need to remember individual axis values.

The CLI delegates to the :mod:`mixpanel_headless.targets` Python namespace,
which in turn delegates to :class:`ConfigManager`. The CLI is purely a
thin presentation layer: input parsing + output formatting.

Reference: specs/042-auth-architecture-redesign/contracts/cli-commands.md §6.
"""

from __future__ import annotations

import json as _json
from typing import Annotated

import typer

from mixpanel_headless import targets as targets_ns
from mixpanel_headless.cli.utils import (
    console,
    err_console,
    handle_errors,
)
from mixpanel_headless.types import Target

target_app = typer.Typer(
    name="target",
    help="Manage saved (account, project, workspace?) target triples.",
    no_args_is_help=True,
)


def _format_target_table(targets: list[Target]) -> str:
    """Render a compact table for ``mp target list``.

    Args:
        targets: Sorted list of :class:`Target` records.

    Returns:
        Multi-line string ready for stdout.
    """
    if not targets:
        return "(no targets configured)"
    lines = ["NAME            ACCOUNT         PROJECT      WORKSPACE"]
    for t in targets:
        ws = str(t.workspace) if t.workspace is not None else "-"
        lines.append(f"{t.name:<15} {t.account:<15} {t.project:<12} {ws}")
    return "\n".join(lines)


def _format_target_json(target: Target) -> str:
    """Render a single :class:`Target` as compact JSON.

    Args:
        target: The target record to serialize.

    Returns:
        One-line JSON object.
    """
    return _json.dumps(
        {
            "name": target.name,
            "account": target.account,
            "project": target.project,
            "workspace": target.workspace,
        }
    )


@target_app.command("add")
@handle_errors
def add_target(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Target name (block key).")],
    account: Annotated[
        str, typer.Option("--account", "-a", help="Referenced account name.")
    ],
    project: Annotated[
        str, typer.Option("--project", "-p", help="Project ID (digit string).")
    ],
    workspace: Annotated[
        int | None,
        typer.Option("--workspace", "-w", help="Optional workspace ID."),
    ] = None,
) -> None:
    """Add a new saved target triple.

    Args:
        ctx: Typer context.
        name: Target name (must not already exist).
        account: Referenced account (must exist).
        project: Project ID (digit string).
        workspace: Optional positive workspace ID.
    """
    target = targets_ns.add(name, account=account, project=project, workspace=workspace)
    console.print(f"Added target: {target.name}")


@target_app.command("use")
@handle_errors
def use_target(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Target to apply.")],
) -> None:
    """Apply the target — write all three axes to ``[active]`` atomically.

    Also updates the target account's ``default_project`` to the target's
    project, so a fresh ``Workspace()`` reproduces the same session.

    Args:
        ctx: Typer context.
        name: Target to apply.
    """
    targets_ns.use(name)
    console.print(f"Active target: {name}")


@target_app.command("list")
@handle_errors
def list_targets(
    ctx: typer.Context,
    format: Annotated[  # noqa: A002
        str,
        typer.Option(
            "--format",
            "-f",
            help="Output format: table | json | jsonl.",
        ),
    ] = "table",
) -> None:
    """List all configured targets.

    Args:
        ctx: Typer context.
        format: Output format.
    """
    from mixpanel_headless.cli.formatters import emit_records

    emit_records(
        targets_ns.list(),
        format=format,
        console=console,
        to_dict=lambda t: {
            "name": t.name,
            "account": t.account,
            "project": t.project,
            "workspace": t.workspace,
        },
        table_renderer=lambda items: _format_target_table(list(items)),
    )


@target_app.command("show")
@handle_errors
def show_target(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Target name.")],
    format: Annotated[  # noqa: A002
        str,
        typer.Option(
            "--format",
            "-f",
            help="Output format: table | json.",
        ),
    ] = "table",
) -> None:
    """Show a single target's details.

    Args:
        ctx: Typer context.
        name: Target name.
        format: Output format.
    """
    target = targets_ns.show(name)
    if format == "json":
        console.print(_format_target_json(target))
    else:
        ws = target.workspace if target.workspace is not None else "-"
        console.print(
            f"name:      {target.name}\n"
            f"account:   {target.account}\n"
            f"project:   {target.project}\n"
            f"workspace: {ws}"
        )


@target_app.command("remove")
@handle_errors
def remove_target(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Target to remove.")],
    yes: Annotated[
        bool,
        typer.Option("--yes", "-y", help="Skip confirmation prompt."),
    ] = False,
) -> None:
    """Remove a target block.

    Args:
        ctx: Typer context.
        name: Target name.
        yes: Skip confirmation prompt.
    """
    if not yes and not typer.confirm(f"Remove target '{name}'?"):
        err_console.print("Aborted.")
        return
    targets_ns.remove(name)
    console.print(f"Removed target: {name}")
