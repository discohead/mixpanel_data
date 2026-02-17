"""Feature flag management commands.

This module provides commands for managing Mixpanel feature flags:
- list: List all feature flags
- get: Get a single feature flag by ID
- create: Create a new feature flag from JSON config
- update: Update an existing feature flag from JSON config
- delete: Delete a feature flag
- archive: Archive a feature flag (soft delete)
- restore: Restore an archived feature flag
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Annotated, Any

import typer

from mixpanel_data.cli.options import FormatOption, JqOption
from mixpanel_data.cli.utils import (
    err_console,
    get_workspace,
    handle_errors,
    output_result,
    status_spinner,
)

flags_app = typer.Typer(
    name="flags",
    help="Manage feature flags.",
    epilog="""CRUD operations for Mixpanel feature flags.

  mp flags list              List all flags
  mp flags get FLAG_ID       Get a single flag
  mp flags create -c file    Create from JSON config
  mp flags update ID -c file Update from JSON config
  mp flags delete FLAG_ID    Delete a flag
  mp flags archive FLAG_ID   Archive a flag
  mp flags restore FLAG_ID   Restore an archived flag""",
    no_args_is_help=True,
    rich_markup_mode="markdown",
)


def _read_config_file(config_file: Path) -> dict[str, Any]:
    """Read and parse a JSON configuration file.

    Supports reading from a file path or stdin (when path is "-").

    Args:
        config_file: Path to JSON file, or Path("-") for stdin.

    Returns:
        Parsed JSON dictionary.

    Raises:
        typer.Exit: If the file cannot be read or parsed.
    """
    try:
        if str(config_file) == "-":
            content = sys.stdin.read()
        else:
            if not config_file.exists():
                err_console.print(
                    f"[red]Error:[/red] Config file not found: {config_file}"
                )
                raise typer.Exit(4)
            content = config_file.read_text()
    except OSError as e:
        err_console.print(f"[red]Error:[/red] Cannot read config file: {e}")
        raise typer.Exit(1) from None

    try:
        data: dict[str, Any] = json.loads(content)
    except json.JSONDecodeError as e:
        err_console.print(f"[red]Error:[/red] Invalid JSON in config file: {e.msg}")
        raise typer.Exit(3) from None

    if not isinstance(data, dict):
        err_console.print("[red]Error:[/red] Config file must contain a JSON object")
        raise typer.Exit(3)

    return data


@flags_app.command("list")
@handle_errors
def flags_list(
    ctx: typer.Context,
    include_archived: Annotated[
        bool,
        typer.Option(
            "--include-archived",
            help="Include archived flags in the listing.",
        ),
    ] = False,
    format: FormatOption = "json",
    jq_filter: JqOption = None,
) -> None:
    """List all feature flags in the project.

    **Output Structure (JSON):**

        [
          {"id": "abc-123", "name": "Dark Mode", "key": "dark_mode", "status": "active", ...},
          {"id": "def-456", "name": "New Checkout", "key": "new_checkout", "status": "draft", ...}
        ]

    **Examples:**

        mp flags list
        mp flags list --include-archived
        mp flags list --format table
        mp flags list --jq '.[].key'
    """
    workspace = get_workspace(ctx)

    with status_spinner(ctx, "Listing feature flags..."):
        result = workspace.feature_flags(include_archived=include_archived)

    data = result.to_table_dict() if format == "table" else result.to_dict()
    output_result(ctx, data, format=format, jq_filter=jq_filter)


@flags_app.command("get")
@handle_errors
def flags_get(
    ctx: typer.Context,
    flag_id: Annotated[
        str,
        typer.Argument(help="Feature flag UUID."),
    ],
    format: FormatOption = "json",
    jq_filter: JqOption = None,
) -> None:
    """Get a single feature flag by ID.

    **Output Structure (JSON):**

        {"id": "abc-123", "name": "Dark Mode", "key": "dark_mode", "status": "active", ...}

    **Examples:**

        mp flags get abc-123-def
        mp flags get abc-123-def --format table
        mp flags get abc-123-def --jq '.ruleset'
    """
    workspace = get_workspace(ctx)

    with status_spinner(ctx, "Fetching feature flag..."):
        result = workspace.feature_flag(flag_id)

    output_result(ctx, result.to_dict(), format=format, jq_filter=jq_filter)


@flags_app.command("create")
@handle_errors
def flags_create(
    ctx: typer.Context,
    config_file: Annotated[
        Path,
        typer.Option(
            "--config-file",
            "-c",
            help='Path to JSON config file (use "-" for stdin).',
        ),
    ],
    name: Annotated[
        str | None,
        typer.Option("--name", help="Override flag name from config."),
    ] = None,
    key: Annotated[
        str | None,
        typer.Option("--key", help="Override flag key from config."),
    ] = None,
    description: Annotated[
        str | None,
        typer.Option("--description", help="Override flag description from config."),
    ] = None,
    format: FormatOption = "json",
    jq_filter: JqOption = None,
) -> None:
    """Create a new feature flag from a JSON configuration file.

    The config file should contain the flag definition as a JSON object.
    Use --name, --key, or --description to override values from the file.

    **Examples:**

        mp flags create --config-file flag.json
        echo '{"name":"Test","key":"test"}' | mp flags create -c -
        mp flags create -c flag.json --name "Override Name"
    """
    payload = _read_config_file(config_file)

    if name is not None:
        payload["name"] = name
    if key is not None:
        payload["key"] = key
    if description is not None:
        payload["description"] = description

    workspace = get_workspace(ctx)

    with status_spinner(ctx, "Creating feature flag..."):
        result = workspace.create_feature_flag(payload)

    output_result(ctx, result.to_dict(), format=format, jq_filter=jq_filter)


@flags_app.command("update")
@handle_errors
def flags_update(
    ctx: typer.Context,
    flag_id: Annotated[
        str,
        typer.Argument(help="Feature flag UUID to update."),
    ],
    config_file: Annotated[
        Path,
        typer.Option(
            "--config-file",
            "-c",
            help='Path to JSON config file (use "-" for stdin).',
        ),
    ],
    name: Annotated[
        str | None,
        typer.Option("--name", help="Override flag name from config."),
    ] = None,
    key: Annotated[
        str | None,
        typer.Option("--key", help="Override flag key from config."),
    ] = None,
    status: Annotated[
        str | None,
        typer.Option("--status", help="Override flag status from config."),
    ] = None,
    description: Annotated[
        str | None,
        typer.Option("--description", help="Override flag description from config."),
    ] = None,
    format: FormatOption = "json",
    jq_filter: JqOption = None,
) -> None:
    """Update an existing feature flag from a JSON configuration file.

    This performs a full replacement (PUT). The config file should contain
    the complete flag definition. Use override flags for quick edits.

    **Examples:**

        mp flags update abc-123-def --config-file flag.json
        mp flags update abc-123-def -c flag.json --name "New Name"
        mp flags update abc-123-def -c flag.json --status disabled
    """
    payload = _read_config_file(config_file)

    if name is not None:
        payload["name"] = name
    if key is not None:
        payload["key"] = key
    if status is not None:
        payload["status"] = status
    if description is not None:
        payload["description"] = description

    workspace = get_workspace(ctx)

    with status_spinner(ctx, "Updating feature flag..."):
        result = workspace.update_feature_flag(flag_id, payload)

    output_result(ctx, result.to_dict(), format=format, jq_filter=jq_filter)


@flags_app.command("delete")
@handle_errors
def flags_delete(
    ctx: typer.Context,
    flag_id: Annotated[
        str,
        typer.Argument(help="Feature flag UUID to delete."),
    ],
) -> None:
    """Delete a feature flag.

    Cannot delete flags that are currently enabled. Disable the flag first,
    or use 'mp flags archive' for a soft delete.

    **Examples:**

        mp flags delete abc-123-def
    """
    workspace = get_workspace(ctx)

    with status_spinner(ctx, "Deleting feature flag..."):
        workspace.delete_feature_flag(flag_id)

    err_console.print("[green]Feature flag deleted.[/green]")


@flags_app.command("archive")
@handle_errors
def flags_archive(
    ctx: typer.Context,
    flag_id: Annotated[
        str,
        typer.Argument(help="Feature flag UUID to archive."),
    ],
) -> None:
    """Archive a feature flag (soft delete).

    Archived flags are hidden by default but can be restored later
    with 'mp flags restore'. Use --include-archived with 'mp flags list'
    to see archived flags.

    **Examples:**

        mp flags archive abc-123-def
    """
    workspace = get_workspace(ctx)

    with status_spinner(ctx, "Archiving feature flag..."):
        workspace.archive_feature_flag(flag_id)

    err_console.print("[green]Feature flag archived.[/green]")


@flags_app.command("restore")
@handle_errors
def flags_restore(
    ctx: typer.Context,
    flag_id: Annotated[
        str,
        typer.Argument(help="Feature flag UUID to restore."),
    ],
) -> None:
    """Restore an archived feature flag.

    Undoes a previous archive operation, making the flag visible again.

    **Examples:**

        mp flags restore abc-123-def
    """
    workspace = get_workspace(ctx)

    with status_spinner(ctx, "Restoring feature flag..."):
        workspace.restore_feature_flag(flag_id)

    err_console.print("[green]Feature flag restored.[/green]")
