"""Experiment management commands.

This module provides commands for managing Mixpanel experiments:

Basic CRUD:
- list: List experiments for the current project
- create: Create a new experiment
- get: Get a single experiment by ID
- update: Update an existing experiment
- delete: Delete an experiment

Lifecycle:
- launch: Launch a draft experiment
- conclude: Conclude a running experiment
- decide: Decide the outcome of a concluded experiment

Organization:
- archive: Archive an experiment
- restore: Restore an archived experiment
- duplicate: Duplicate an experiment

Advanced:
- erf: List ERF experiments
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

experiments_app = typer.Typer(
    name="experiments",
    help="Manage Mixpanel experiments.",
    no_args_is_help=True,
)


# =============================================================================
# Basic CRUD
# =============================================================================


@experiments_app.command("list")
@handle_errors
def experiments_list(
    ctx: typer.Context,
    include_archived: Annotated[
        bool,
        typer.Option(
            "--include-archived", help="Include archived experiments in results."
        ),
    ] = False,
    format: FormatOption = "json",
    jq_filter: JqOption = None,
) -> None:
    """List experiments for the current project.

    Retrieves all experiments visible to the authenticated user,
    optionally including archived experiments.

    Args:
        ctx: Typer context with global options.
        include_archived: Whether to include archived experiments.
        format: Output format.
        jq_filter: Optional jq filter expression.
    """
    workspace = get_workspace(ctx)
    with status_spinner(ctx, "Fetching experiments..."):
        result = workspace.list_experiments(include_archived=include_archived)
    output_result(
        ctx,
        [e.model_dump() for e in result],
        format=format,
        jq_filter=jq_filter,
    )


@experiments_app.command("create")
@handle_errors
def experiments_create(
    ctx: typer.Context,
    name: Annotated[
        str,
        typer.Option("--name", help="Experiment name."),
    ],
    description: Annotated[
        str | None,
        typer.Option("--description", help="Experiment description."),
    ] = None,
    hypothesis: Annotated[
        str | None,
        typer.Option("--hypothesis", help="Experiment hypothesis."),
    ] = None,
    settings: Annotated[
        str | None,
        typer.Option(
            "--settings",
            help="Experiment settings as JSON string (e.g. '{\"confidence_level\": 0.95}').",
        ),
    ] = None,
    format: FormatOption = "json",
    jq_filter: JqOption = None,
) -> None:
    """Create a new experiment.

    Creates an experiment with the specified name and optional settings.

    Args:
        ctx: Typer context with global options.
        name: Experiment name (required).
        description: Optional experiment description.
        hypothesis: Optional experiment hypothesis.
        settings: Optional experiment settings as a JSON string.
        format: Output format.
        jq_filter: Optional jq filter expression.
    """
    from mixpanel_headless.types import CreateExperimentParams

    parsed_settings: dict[str, Any] | None = None
    if settings is not None:
        try:
            parsed_settings = json.loads(settings)
        except json.JSONDecodeError as exc:
            err_console.print(f"[red]Invalid JSON for --settings:[/red] {exc}")
            raise typer.Exit(code=1) from None

    params = CreateExperimentParams(
        name=name,
        description=description,
        hypothesis=hypothesis,
        settings=parsed_settings,
    )
    workspace = get_workspace(ctx)
    with status_spinner(ctx, "Creating experiment..."):
        result = workspace.create_experiment(params)
    output_result(ctx, result.model_dump(), format=format, jq_filter=jq_filter)


@experiments_app.command("get")
@handle_errors
def experiments_get(
    ctx: typer.Context,
    experiment_id: Annotated[
        str,
        typer.Argument(help="Experiment ID."),
    ],
    format: FormatOption = "json",
    jq_filter: JqOption = None,
) -> None:
    """Get a single experiment by ID.

    Retrieves the full experiment object including metadata,
    variants, metrics, and status.

    Args:
        ctx: Typer context with global options.
        experiment_id: Experiment identifier.
        format: Output format.
        jq_filter: Optional jq filter expression.
    """
    workspace = get_workspace(ctx)
    with status_spinner(ctx, "Fetching experiment..."):
        result = workspace.get_experiment(experiment_id)
    output_result(ctx, result.model_dump(), format=format, jq_filter=jq_filter)


@experiments_app.command("update")
@handle_errors
def experiments_update(
    ctx: typer.Context,
    experiment_id: Annotated[
        str,
        typer.Argument(help="Experiment ID."),
    ],
    name: Annotated[
        str | None,
        typer.Option("--name", help="New experiment name."),
    ] = None,
    description: Annotated[
        str | None,
        typer.Option("--description", help="New experiment description."),
    ] = None,
    hypothesis: Annotated[
        str | None,
        typer.Option("--hypothesis", help="New experiment hypothesis."),
    ] = None,
    variants: Annotated[
        str | None,
        typer.Option(
            "--variants",
            help='Variants as JSON object string (e.g. \'{"control": {"weight": 50}}\').',
        ),
    ] = None,
    metrics: Annotated[
        str | None,
        typer.Option(
            "--metrics",
            help='Metrics as JSON object string (e.g. \'{"primary": "Purchase"}\').',
        ),
    ] = None,
    settings: Annotated[
        str | None,
        typer.Option(
            "--settings",
            help="Settings as JSON string (e.g. '{\"confidence_level\": 0.95}').",
        ),
    ] = None,
    tags: Annotated[
        str | None,
        typer.Option("--tags", help="Comma-separated tags."),
    ] = None,
    format: FormatOption = "json",
    jq_filter: JqOption = None,
) -> None:
    """Update an existing experiment.

    Updates the specified fields on an experiment. Only provided
    options are sent to the API; omitted fields are unchanged.

    Args:
        ctx: Typer context with global options.
        experiment_id: Experiment identifier.
        name: New name for the experiment.
        description: New description for the experiment.
        hypothesis: New hypothesis for the experiment.
        variants: Variants as a JSON string.
        metrics: Metrics as a JSON string.
        settings: Settings as a JSON string.
        tags: Comma-separated tags.
        format: Output format.
        jq_filter: Optional jq filter expression.
    """
    from mixpanel_headless.types import UpdateExperimentParams

    parsed_variants: dict[str, Any] | None = None
    parsed_metrics: dict[str, Any] | None = None
    parsed_settings: dict[str, Any] | None = None
    tag_list: list[str] | None = None

    if variants is not None:
        try:
            parsed_variants = json.loads(variants)
        except json.JSONDecodeError as exc:
            err_console.print(f"[red]Invalid JSON for --variants:[/red] {exc}")
            raise typer.Exit(code=1) from None

    if metrics is not None:
        try:
            parsed_metrics = json.loads(metrics)
        except json.JSONDecodeError as exc:
            err_console.print(f"[red]Invalid JSON for --metrics:[/red] {exc}")
            raise typer.Exit(code=1) from None

    if settings is not None:
        try:
            parsed_settings = json.loads(settings)
        except json.JSONDecodeError as exc:
            err_console.print(f"[red]Invalid JSON for --settings:[/red] {exc}")
            raise typer.Exit(code=1) from None

    if tags is not None:
        tag_list = [t.strip() for t in tags.split(",") if t.strip()]

    params = UpdateExperimentParams(
        name=name,
        description=description,
        hypothesis=hypothesis,
        variants=parsed_variants,
        metrics=parsed_metrics,
        settings=parsed_settings,
        tags=tag_list,
    )
    workspace = get_workspace(ctx)
    with status_spinner(ctx, "Updating experiment..."):
        result = workspace.update_experiment(experiment_id, params)
    output_result(ctx, result.model_dump(), format=format, jq_filter=jq_filter)


@experiments_app.command("delete")
@handle_errors
def experiments_delete(
    ctx: typer.Context,
    experiment_id: Annotated[
        str,
        typer.Argument(help="Experiment ID."),
    ],
) -> None:
    """Delete an experiment.

    Permanently deletes an experiment by ID. This action cannot be undone.

    Args:
        ctx: Typer context with global options.
        experiment_id: Experiment identifier.
    """
    workspace = get_workspace(ctx)
    with status_spinner(ctx, "Deleting experiment..."):
        workspace.delete_experiment(experiment_id)
    err_console.print(f"[green]Deleted experiment {experiment_id}.[/green]")


# =============================================================================
# Lifecycle
# =============================================================================


@experiments_app.command("launch")
@handle_errors
def experiments_launch(
    ctx: typer.Context,
    experiment_id: Annotated[
        str,
        typer.Argument(help="Experiment ID."),
    ],
    format: FormatOption = "json",
    jq_filter: JqOption = None,
) -> None:
    """Launch a draft experiment.

    Transitions an experiment from draft to active status.

    Args:
        ctx: Typer context with global options.
        experiment_id: Experiment identifier.
        format: Output format.
        jq_filter: Optional jq filter expression.
    """
    workspace = get_workspace(ctx)
    with status_spinner(ctx, "Launching experiment..."):
        result = workspace.launch_experiment(experiment_id)
    output_result(ctx, result.model_dump(), format=format, jq_filter=jq_filter)


@experiments_app.command("conclude")
@handle_errors
def experiments_conclude(
    ctx: typer.Context,
    experiment_id: Annotated[
        str,
        typer.Argument(help="Experiment ID."),
    ],
    end_date: Annotated[
        str | None,
        typer.Option("--end-date", help="End date for the experiment (YYYY-MM-DD)."),
    ] = None,
    format: FormatOption = "json",
    jq_filter: JqOption = None,
) -> None:
    """Conclude an active experiment.

    Transitions an experiment from active to concluded status,
    optionally specifying an end date.

    Args:
        ctx: Typer context with global options.
        experiment_id: Experiment identifier.
        end_date: Optional end date in YYYY-MM-DD format.
        format: Output format.
        jq_filter: Optional jq filter expression.
    """
    from mixpanel_headless.types import ExperimentConcludeParams

    params: ExperimentConcludeParams | None = None
    if end_date is not None:
        params = ExperimentConcludeParams(end_date=end_date)

    workspace = get_workspace(ctx)
    with status_spinner(ctx, "Concluding experiment..."):
        result = workspace.conclude_experiment(experiment_id, params=params)
    output_result(ctx, result.model_dump(), format=format, jq_filter=jq_filter)


@experiments_app.command("decide")
@handle_errors
def experiments_decide(
    ctx: typer.Context,
    experiment_id: Annotated[
        str,
        typer.Argument(help="Experiment ID."),
    ],
    success: Annotated[
        bool,
        typer.Option(
            "--success/--no-success",
            help="Whether the experiment was successful.",
        ),
    ],
    variant: Annotated[
        str | None,
        typer.Option("--variant", help="Winning variant name."),
    ] = None,
    message: Annotated[
        str | None,
        typer.Option("--message", help="Decision message or rationale."),
    ] = None,
    format: FormatOption = "json",
    jq_filter: JqOption = None,
) -> None:
    """Decide the outcome of a concluded experiment.

    Records the decision for a concluded experiment, including
    whether it was successful and which variant won.

    Args:
        ctx: Typer context with global options.
        experiment_id: Experiment identifier.
        success: Whether the experiment was successful.
        variant: Optional winning variant name.
        message: Optional decision message or rationale.
        format: Output format.
        jq_filter: Optional jq filter expression.
    """
    from mixpanel_headless.types import ExperimentDecideParams

    params = ExperimentDecideParams(
        success=success,
        variant=variant,
        message=message,
    )
    workspace = get_workspace(ctx)
    with status_spinner(ctx, "Recording experiment decision..."):
        result = workspace.decide_experiment(experiment_id, params)
    output_result(ctx, result.model_dump(), format=format, jq_filter=jq_filter)


# =============================================================================
# Organization
# =============================================================================


@experiments_app.command("archive")
@handle_errors
def experiments_archive(
    ctx: typer.Context,
    experiment_id: Annotated[
        str,
        typer.Argument(help="Experiment ID."),
    ],
) -> None:
    """Archive an experiment.

    Marks the specified experiment as archived. Archived experiments
    are hidden from default listings.

    Args:
        ctx: Typer context with global options.
        experiment_id: Experiment identifier.
    """
    workspace = get_workspace(ctx)
    with status_spinner(ctx, "Archiving experiment..."):
        workspace.archive_experiment(experiment_id)
    err_console.print(f"[green]Archived experiment {experiment_id}.[/green]")


@experiments_app.command("restore")
@handle_errors
def experiments_restore(
    ctx: typer.Context,
    experiment_id: Annotated[
        str,
        typer.Argument(help="Experiment ID."),
    ],
    format: FormatOption = "json",
    jq_filter: JqOption = None,
) -> None:
    """Restore an archived experiment.

    Restores a previously archived experiment back to its prior state.

    Args:
        ctx: Typer context with global options.
        experiment_id: Experiment identifier.
        format: Output format.
        jq_filter: Optional jq filter expression.
    """
    workspace = get_workspace(ctx)
    with status_spinner(ctx, "Restoring experiment..."):
        result = workspace.restore_experiment(experiment_id)
    output_result(ctx, result.model_dump(), format=format, jq_filter=jq_filter)


@experiments_app.command("duplicate")
@handle_errors
def experiments_duplicate(
    ctx: typer.Context,
    experiment_id: Annotated[
        str,
        typer.Argument(help="Experiment ID."),
    ],
    name: Annotated[
        str,
        typer.Option("--name", help="Name for the duplicated experiment (required)."),
    ],
    format: FormatOption = "json",
    jq_filter: JqOption = None,
) -> None:
    """Duplicate an experiment.

    Creates a copy of the specified experiment with a new name.
    A name is required because the Mixpanel API does not support
    duplication without one.

    Args:
        ctx: Typer context with global options.
        experiment_id: Experiment identifier.
        name: Name for the duplicated experiment (required).
        format: Output format.
        jq_filter: Optional jq filter expression.
    """
    from mixpanel_headless.types import DuplicateExperimentParams

    workspace = get_workspace(ctx)
    params = DuplicateExperimentParams(name=name)
    with status_spinner(ctx, "Duplicating experiment..."):
        result = workspace.duplicate_experiment(experiment_id, params)
    output_result(ctx, result.model_dump(), format=format, jq_filter=jq_filter)


# =============================================================================
# Advanced
# =============================================================================


@experiments_app.command("erf")
@handle_errors
def experiments_erf(
    ctx: typer.Context,
    format: FormatOption = "json",
    jq_filter: JqOption = None,
) -> None:
    """List ERF experiments.

    Retrieves ERF experiment data for the current project.

    Args:
        ctx: Typer context with global options.
        format: Output format.
        jq_filter: Optional jq filter expression.
    """
    workspace = get_workspace(ctx)
    with status_spinner(ctx, "Fetching ERF experiments..."):
        result = workspace.list_erf_experiments()
    output_result(ctx, result, format=format, jq_filter=jq_filter)
