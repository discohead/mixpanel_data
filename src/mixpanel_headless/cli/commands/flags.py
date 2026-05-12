"""Feature flag management commands.

This module provides commands for managing Mixpanel feature flags:

Basic CRUD:
- list: List feature flags for the current project
- create: Create a new feature flag
- get: Get a single feature flag by ID
- update: Update an existing feature flag (full replacement)
- delete: Delete a feature flag

Lifecycle:
- archive: Archive a feature flag
- restore: Restore an archived feature flag
- duplicate: Duplicate an existing feature flag

Advanced:
- set-test-users: Set test user variant overrides
- history: View change history for a feature flag
- limits: View account-level flag usage and limits
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

flags_app = typer.Typer(
    name="flags",
    help="Manage Mixpanel feature flags.",
    no_args_is_help=True,
)


# =============================================================================
# Basic CRUD
# =============================================================================


@flags_app.command("list")
@handle_errors
def flags_list(
    ctx: typer.Context,
    include_archived: Annotated[
        bool,
        typer.Option(
            "--include-archived", help="Include archived flags in the listing."
        ),
    ] = False,
    format: FormatOption = "json",
    jq_filter: JqOption = None,
) -> None:
    """List feature flags for the current project.

    Retrieves all feature flags visible to the authenticated user.
    By default, archived flags are excluded.

    Args:
        ctx: Typer context with global options.
        include_archived: Whether to include archived flags.
        format: Output format.
        jq_filter: Optional jq filter expression.
    """
    workspace = get_workspace(ctx)
    with status_spinner(ctx, "Fetching feature flags..."):
        result = workspace.list_feature_flags(include_archived=include_archived)
    output_result(
        ctx,
        [f.model_dump() for f in result],
        format=format,
        jq_filter=jq_filter,
    )


@flags_app.command("create")
@handle_errors
def flags_create(
    ctx: typer.Context,
    name: Annotated[
        str,
        typer.Option("--name", help="Flag name."),
    ],
    key: Annotated[
        str,
        typer.Option("--key", help="Unique machine-readable key."),
    ],
    description: Annotated[
        str | None,
        typer.Option("--description", help="Flag description."),
    ] = None,
    status: Annotated[
        str | None,
        typer.Option("--status", help="Initial status (enabled, disabled, archived)."),
    ] = None,
    tags: Annotated[
        str | None,
        typer.Option("--tags", help="Comma-separated tags."),
    ] = None,
    serving_method: Annotated[
        str | None,
        typer.Option(
            "--serving-method",
            help="Serving method (client, server, remote_or_local, remote_only).",
        ),
    ] = None,
    ruleset: Annotated[
        str | None,
        typer.Option("--ruleset", help="Ruleset as JSON string."),
    ] = None,
    format: FormatOption = "json",
    jq_filter: JqOption = None,
) -> None:
    """Create a new feature flag.

    Creates a feature flag with the specified name and key.
    Optional parameters allow setting description, status, tags,
    serving method, and initial ruleset.

    Args:
        ctx: Typer context with global options.
        name: Flag name (required).
        key: Unique machine-readable key (required).
        description: Optional flag description.
        status: Initial status (enabled, disabled, archived).
        tags: Comma-separated tags.
        serving_method: Serving method (client, server, remote_or_local, remote_only).
        ruleset: Ruleset as a JSON string.
        format: Output format.
        jq_filter: Optional jq filter expression.
    """
    from mixpanel_headless.types import (
        CreateFeatureFlagParams,
        FeatureFlagStatus,
        ServingMethod,
    )

    kwargs: dict[str, Any] = {"name": name, "key": key}
    if description is not None:
        kwargs["description"] = description
    if status is not None:
        kwargs["status"] = FeatureFlagStatus(status.lower())
    if tags is not None:
        kwargs["tags"] = [t.strip() for t in tags.split(",") if t.strip()]
    if serving_method is not None:
        kwargs["serving_method"] = ServingMethod(serving_method)
    if ruleset is not None:
        try:
            kwargs["ruleset"] = json.loads(ruleset)
        except json.JSONDecodeError as exc:
            err_console.print(f"[red]Invalid JSON for --ruleset:[/red] {exc}")
            raise typer.Exit(code=1) from None

    params = CreateFeatureFlagParams(**kwargs)
    workspace = get_workspace(ctx)
    with status_spinner(ctx, "Creating feature flag..."):
        result = workspace.create_feature_flag(params)
    output_result(ctx, result.model_dump(), format=format, jq_filter=jq_filter)


@flags_app.command("get")
@handle_errors
def flags_get(
    ctx: typer.Context,
    flag_id: Annotated[
        str,
        typer.Argument(help="Feature flag ID."),
    ],
    format: FormatOption = "json",
    jq_filter: JqOption = None,
) -> None:
    """Get a single feature flag by ID.

    Retrieves the full feature flag object including configuration,
    metadata, and permissions.

    Args:
        ctx: Typer context with global options.
        flag_id: Feature flag identifier.
        format: Output format.
        jq_filter: Optional jq filter expression.
    """
    workspace = get_workspace(ctx)
    with status_spinner(ctx, "Fetching feature flag..."):
        result = workspace.get_feature_flag(flag_id)
    output_result(ctx, result.model_dump(), format=format, jq_filter=jq_filter)


@flags_app.command("update")
@handle_errors
def flags_update(
    ctx: typer.Context,
    flag_id: Annotated[
        str,
        typer.Argument(help="Feature flag ID."),
    ],
    name: Annotated[
        str,
        typer.Option("--name", help="Flag name (required for full replacement)."),
    ],
    key: Annotated[
        str,
        typer.Option("--key", help="Unique machine-readable key (required)."),
    ],
    status: Annotated[
        str,
        typer.Option(
            "--status", help="Target status (enabled, disabled, archived) (required)."
        ),
    ],
    ruleset: Annotated[
        str,
        typer.Option("--ruleset", help="Complete ruleset as JSON string (required)."),
    ],
    description: Annotated[
        str | None,
        typer.Option("--description", help="Flag description."),
    ] = None,
    tags: Annotated[
        str | None,
        typer.Option("--tags", help="Comma-separated tags."),
    ] = None,
    context: Annotated[
        str | None,
        typer.Option("--context", help="Flag context identifier (e.g. 'distinct_id')."),
    ] = None,
    serving_method: Annotated[
        str | None,
        typer.Option(
            "--serving-method",
            help="Serving method (client, server, remote_or_local, remote_only).",
        ),
    ] = None,
    format: FormatOption = "json",
    jq_filter: JqOption = None,
) -> None:
    """Update an existing feature flag (full replacement).

    Performs a full replacement of the feature flag. All required fields
    (name, key, status, ruleset) must be provided.

    Args:
        ctx: Typer context with global options.
        flag_id: Feature flag identifier.
        name: Flag name (required).
        key: Unique machine-readable key (required).
        status: Target status (required).
        ruleset: Complete ruleset as JSON string (required).
        description: Optional flag description.
        tags: Comma-separated tags.
        context: Optional flag context identifier.
        serving_method: Serving method.
        format: Output format.
        jq_filter: Optional jq filter expression.
    """
    from mixpanel_headless.types import (
        FeatureFlagStatus,
        ServingMethod,
        UpdateFeatureFlagParams,
    )

    try:
        parsed_ruleset: dict[str, Any] = json.loads(ruleset)
    except json.JSONDecodeError as exc:
        err_console.print(f"[red]Invalid JSON for --ruleset:[/red] {exc}")
        raise typer.Exit(code=1) from None

    kwargs: dict[str, Any] = {
        "name": name,
        "key": key,
        "status": FeatureFlagStatus(status.lower()),
        "ruleset": parsed_ruleset,
    }
    if description is not None:
        kwargs["description"] = description
    if tags is not None:
        kwargs["tags"] = [t.strip() for t in tags.split(",") if t.strip()]
    if context is not None:
        kwargs["context"] = context
    if serving_method is not None:
        kwargs["serving_method"] = ServingMethod(serving_method)

    params = UpdateFeatureFlagParams(**kwargs)
    workspace = get_workspace(ctx)
    with status_spinner(ctx, "Updating feature flag..."):
        result = workspace.update_feature_flag(flag_id, params)
    output_result(ctx, result.model_dump(), format=format, jq_filter=jq_filter)


@flags_app.command("delete")
@handle_errors
def flags_delete(
    ctx: typer.Context,
    flag_id: Annotated[
        str,
        typer.Argument(help="Feature flag ID."),
    ],
) -> None:
    """Delete a feature flag.

    Permanently deletes a feature flag by ID. This action cannot be undone.

    Args:
        ctx: Typer context with global options.
        flag_id: Feature flag identifier.
    """
    workspace = get_workspace(ctx)
    with status_spinner(ctx, "Deleting feature flag..."):
        workspace.delete_feature_flag(flag_id)
    err_console.print(f"[green]Deleted flag {flag_id}.[/green]")


# =============================================================================
# Lifecycle
# =============================================================================


@flags_app.command("archive")
@handle_errors
def flags_archive(
    ctx: typer.Context,
    flag_id: Annotated[
        str,
        typer.Argument(help="Feature flag ID."),
    ],
) -> None:
    """Archive a feature flag.

    Soft-deletes a feature flag by moving it to the archived state.
    Archived flags are excluded from default listings.

    Args:
        ctx: Typer context with global options.
        flag_id: Feature flag identifier.
    """
    workspace = get_workspace(ctx)
    with status_spinner(ctx, "Archiving feature flag..."):
        workspace.archive_feature_flag(flag_id)
    err_console.print(f"[green]Archived flag {flag_id}.[/green]")


@flags_app.command("restore")
@handle_errors
def flags_restore(
    ctx: typer.Context,
    flag_id: Annotated[
        str,
        typer.Argument(help="Feature flag ID."),
    ],
    format: FormatOption = "json",
    jq_filter: JqOption = None,
) -> None:
    """Restore an archived feature flag.

    Restores a previously archived feature flag, returning
    it to its prior state.

    Args:
        ctx: Typer context with global options.
        flag_id: Feature flag identifier.
        format: Output format.
        jq_filter: Optional jq filter expression.
    """
    workspace = get_workspace(ctx)
    with status_spinner(ctx, "Restoring feature flag..."):
        result = workspace.restore_feature_flag(flag_id)
    output_result(ctx, result.model_dump(), format=format, jq_filter=jq_filter)


@flags_app.command("duplicate")
@handle_errors
def flags_duplicate(
    ctx: typer.Context,
    flag_id: Annotated[
        str,
        typer.Argument(help="Feature flag ID."),
    ],
    format: FormatOption = "json",
    jq_filter: JqOption = None,
) -> None:
    """Duplicate an existing feature flag.

    Creates a copy of the specified feature flag with a new ID.

    Args:
        ctx: Typer context with global options.
        flag_id: Feature flag identifier.
        format: Output format.
        jq_filter: Optional jq filter expression.
    """
    workspace = get_workspace(ctx)
    with status_spinner(ctx, "Duplicating feature flag..."):
        result = workspace.duplicate_feature_flag(flag_id)
    output_result(ctx, result.model_dump(), format=format, jq_filter=jq_filter)


# =============================================================================
# Advanced
# =============================================================================


@flags_app.command("set-test-users")
@handle_errors
def flags_set_test_users(
    ctx: typer.Context,
    flag_id: Annotated[
        str,
        typer.Argument(help="Feature flag ID."),
    ],
    users: Annotated[
        str,
        typer.Option(
            "--users",
            help='Test users as JSON string (e.g. \'{"on": "user-1", "off": "user-2"}\').',
        ),
    ],
) -> None:
    """Set test user variant overrides on a feature flag.

    Assigns specific users to specific variants for testing purposes.
    The users parameter is a JSON mapping of variant keys to user
    distinct IDs.

    Args:
        ctx: Typer context with global options.
        flag_id: Feature flag identifier.
        users: Test users as a JSON string mapping variant keys to user IDs.
    """
    from mixpanel_headless.types import SetTestUsersParams

    try:
        parsed_users: dict[str, str] = json.loads(users)
    except json.JSONDecodeError as exc:
        err_console.print(f"[red]Invalid JSON for --users:[/red] {exc}")
        raise typer.Exit(code=1) from None

    params = SetTestUsersParams(users=parsed_users)
    workspace = get_workspace(ctx)
    with status_spinner(ctx, "Setting test users..."):
        workspace.set_flag_test_users(flag_id, params)
    err_console.print(f"[green]Set test users for flag {flag_id}.[/green]")


@flags_app.command("history")
@handle_errors
def flags_history(
    ctx: typer.Context,
    flag_id: Annotated[
        str,
        typer.Argument(help="Feature flag ID."),
    ],
    page: Annotated[
        str | None,
        typer.Option("--page", help="Pagination cursor."),
    ] = None,
    page_size: Annotated[
        int | None,
        typer.Option("--page-size", help="Results per page."),
    ] = None,
    format: FormatOption = "json",
    jq_filter: JqOption = None,
) -> None:
    """View change history for a feature flag.

    Retrieves the paginated change history for the specified
    feature flag, including status changes, rule updates, etc.

    Args:
        ctx: Typer context with global options.
        flag_id: Feature flag identifier.
        page: Pagination cursor for next page.
        page_size: Number of results per page.
        format: Output format.
        jq_filter: Optional jq filter expression.
    """
    workspace = get_workspace(ctx)
    with status_spinner(ctx, "Fetching flag history..."):
        result = workspace.get_flag_history(flag_id, page=page, page_size=page_size)
    output_result(ctx, result.model_dump(), format=format, jq_filter=jq_filter)


@flags_app.command("limits")
@handle_errors
def flags_limits(
    ctx: typer.Context,
    format: FormatOption = "json",
    jq_filter: JqOption = None,
) -> None:
    """View account-level feature flag usage and limits.

    Retrieves the current flag usage, maximum limit, trial status,
    and contract status for the account.

    Args:
        ctx: Typer context with global options.
        format: Output format.
        jq_filter: Optional jq filter expression.
    """
    workspace = get_workspace(ctx)
    with status_spinner(ctx, "Fetching flag limits..."):
        result = workspace.get_flag_limits()
    output_result(ctx, result.model_dump(), format=format, jq_filter=jq_filter)
