"""Business context commands.

This module provides commands for reading and writing the markdown
documentation that grounds AI assistants in your organization's
structure and goals.

Subcommands:

- ``get``:   Read context at a given scope (org or project).
- ``set``:   Replace context at a given scope. Accepts content from
  ``--content``, ``--file``, or stdin (mutually exclusive). Empty
  stdin is rejected — use ``clear`` to deliberately clear.
- ``clear``: Convenience for ``set`` with empty content.
- ``chain``: Read both org-level and project-level context together
  in a single round-trip via the ``/business-context/chain`` endpoint.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Annotated, Literal, cast

import click
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

business_context_app = typer.Typer(
    name="business-context",
    help="Read and write project / organization business context.",
    no_args_is_help=True,
)


# ``LevelOption`` mirrors the codebase pattern in ``cli/options.py::FormatOption``:
# accept a ``str`` with ``click_type=click.Choice([...])`` so Click validates the
# value and produces nice ``--help`` like ``[organization|project]``. We use
# this here rather than a Python ``Enum`` because some Typer versions raise on
# ``Literal`` annotations and the project already standardizes on ``click.Choice``.
LevelOption = Annotated[
    str,
    typer.Option(
        "--level",
        help="Which scope to operate on.",
        click_type=click.Choice(["organization", "project"]),
    ),
]

_ORG_ID_HELP = (
    "Organization ID for --level organization. When omitted, auto-resolved "
    "from the current session's project via the cached /me response."
)


def _read_set_content(
    content: str | None,
    file: Path | None,
) -> str:
    """Resolve the markdown content to send for the ``set`` command.

    Precedence: ``--content`` > ``--file`` > stdin (when piped).
    ``--content`` and ``--file`` are mutually exclusive — passing both
    is a usage error. Stdin is read only when both flags are absent
    AND stdin is not a TTY (i.e. content was actually piped in). An
    empty / whitespace-only stdin is rejected — clearing context must
    be explicit (``mp business-context clear`` or
    ``--content ""``) to prevent silent data loss in CI / cron where
    stdin may be redirected from ``/dev/null``.

    Args:
        content: Inline content from ``--content``, or ``None``.
        file: Path from ``--file``, or ``None``.

    Returns:
        The markdown content to send to the API.

    Raises:
        typer.Exit: Both ``--content`` and ``--file`` were provided,
            the file does not exist, no content source was supplied,
            or the piped stdin was empty / whitespace-only. Exits
            with ``ExitCode.INVALID_ARGS``.
    """
    if content is not None and file is not None:
        err_console.print("[red]--content and --file are mutually exclusive.[/red]")
        raise typer.Exit(code=ExitCode.INVALID_ARGS)

    if content is not None:
        return content
    if file is not None:
        if not file.exists():
            err_console.print(f"[red]File not found:[/red] {file}")
            raise typer.Exit(code=ExitCode.INVALID_ARGS)
        return file.read_text(encoding="utf-8")
    if not sys.stdin.isatty():
        payload = sys.stdin.read()
        if not payload.strip():
            # Defend against the CI/cron `</dev/null` footgun: an empty
            # stdin would otherwise full-replace the stored context with
            # the empty string — a silent destructive write. Force the
            # caller to be explicit.
            err_console.print(
                "[red]Empty stdin.[/red] Refusing to write empty content "
                "implicitly. To clear, use `mp business-context clear` "
                'or pass `--content ""` explicitly.'
            )
            raise typer.Exit(code=ExitCode.INVALID_ARGS)
        return payload
    err_console.print(
        "[red]No content provided.[/red] Pass --content TEXT, --file PATH, "
        "or pipe content via stdin."
    )
    raise typer.Exit(code=ExitCode.INVALID_ARGS)


@business_context_app.command("get")
@handle_errors
def business_context_get(
    ctx: typer.Context,
    level: LevelOption = "project",
    organization_id: Annotated[
        int | None,
        typer.Option("--organization-id", help=_ORG_ID_HELP),
    ] = None,
    format: FormatOption = "json",
    jq_filter: JqOption = None,
) -> None:
    """Read business context content at the given scope.

    Outputs a ``BusinessContext`` JSON document with ``level``,
    ``content``, and the matching ``organization_id`` or ``project_id``.

    Args:
        ctx: Typer context with global options.
        level: ``project`` (default) or ``organization``.
        organization_id: Optional explicit org ID for org-level reads.
        format: Output format.
        jq_filter: Optional jq filter expression.
    """
    # ``LevelOption`` (click.Choice) guarantees one of the two literals at
    # runtime, so the cast is safe.
    typed_level = cast("Literal['organization', 'project']", level)
    workspace = get_workspace(ctx)
    with status_spinner(ctx, f"Fetching {typed_level} business context..."):
        result = workspace.get_business_context(
            level=typed_level,
            organization_id=organization_id,
        )
    output_result(ctx, result.model_dump(), format=format, jq_filter=jq_filter)


@business_context_app.command("set")
@handle_errors
def business_context_set(
    ctx: typer.Context,
    level: LevelOption = "project",
    organization_id: Annotated[
        int | None,
        typer.Option("--organization-id", help=_ORG_ID_HELP),
    ] = None,
    content: Annotated[
        str | None,
        typer.Option(
            "--content",
            help="Inline markdown content. Mutually exclusive with --file / stdin.",
        ),
    ] = None,
    file: Annotated[
        Path | None,
        typer.Option(
            "--file",
            help="Read markdown content from a file. Mutually exclusive with --content / stdin.",
        ),
    ] = None,
    format: FormatOption = "json",
    jq_filter: JqOption = None,
) -> None:
    """Replace business context content at the given scope.

    Content can come from ``--content``, ``--file``, or piped stdin
    (when neither flag is given and stdin is not a TTY). Empty /
    whitespace-only stdin is rejected — use ``mp business-context clear``
    or pass ``--content ""`` explicitly to clear, to prevent silent
    destructive writes in CI / cron.

    The 50,000-character limit is enforced client-side BEFORE the HTTP
    call so over-long input fails immediately rather than wasting a
    round-trip.

    Args:
        ctx: Typer context with global options.
        level: ``project`` (default) or ``organization``.
        organization_id: Optional explicit org ID for org-level writes.
        content: Inline content. Mutually exclusive with ``--file`` / stdin.
        file: Path to a file containing the content. Mutually exclusive
            with ``--content`` / stdin.
        format: Output format.
        jq_filter: Optional jq filter expression.
    """
    typed_level = cast("Literal['organization', 'project']", level)
    payload = _read_set_content(content, file)
    workspace = get_workspace(ctx)
    with status_spinner(ctx, f"Updating {typed_level} business context..."):
        result = workspace.set_business_context(
            payload,
            level=typed_level,
            organization_id=organization_id,
        )
    output_result(ctx, result.model_dump(), format=format, jq_filter=jq_filter)


@business_context_app.command("clear")
@handle_errors
def business_context_clear(
    ctx: typer.Context,
    level: LevelOption = "project",
    organization_id: Annotated[
        int | None,
        typer.Option("--organization-id", help=_ORG_ID_HELP),
    ] = None,
    format: FormatOption = "json",
    jq_filter: JqOption = None,
) -> None:
    """Clear business context at the given scope.

    Equivalent to ``mp business-context set --content ""``. Documents
    intent and avoids accidental clearing when stdin is unexpectedly
    empty.

    Args:
        ctx: Typer context with global options.
        level: ``project`` (default) or ``organization``.
        organization_id: Optional explicit org ID for org-level clears.
        format: Output format.
        jq_filter: Optional jq filter expression.
    """
    typed_level = cast("Literal['organization', 'project']", level)
    workspace = get_workspace(ctx)
    with status_spinner(ctx, f"Clearing {typed_level} business context..."):
        result = workspace.clear_business_context(
            level=typed_level,
            organization_id=organization_id,
        )
    output_result(ctx, result.model_dump(), format=format, jq_filter=jq_filter)


@business_context_app.command("chain")
@handle_errors
def business_context_chain(
    ctx: typer.Context,
    format: FormatOption = "json",
    jq_filter: JqOption = None,
) -> None:
    """Read both org-level and project-level context in one call.

    Calls the project-scoped ``/business-context/chain`` endpoint and
    returns a ``BusinessContextChain`` JSON document with both scopes
    populated. ``organization.organization_id`` is populated only when
    a cached ``/me`` response is available — this preserves the chain
    endpoint's single-network-round-trip guarantee.

    Args:
        ctx: Typer context with global options.
        format: Output format.
        jq_filter: Optional jq filter expression.
    """
    workspace = get_workspace(ctx)
    with status_spinner(ctx, "Fetching business context chain..."):
        result = workspace.get_business_context_chain()
    output_result(ctx, result.model_dump(), format=format, jq_filter=jq_filter)
