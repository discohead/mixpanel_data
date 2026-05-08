"""``mp login`` Typer command (043 / AIE-117).

Thin wrapper over :func:`accounts.login_unified` that adds the
TTY-aware project / org pickers and the structured stdout success line.
All other orchestration (auth-type detection, region probe, name
derivation, atomic publish, re-login state machine) lives in the
library.

Reference: ``specs/043-frictionless-auth/contracts/cli-commands.md`` §1.
"""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING, Annotated

import typer

from mixpanel_headless import accounts as accounts_ns
from mixpanel_headless.cli.utils import (
    ExitCode,
    console,
    err_console,
    handle_errors,
    status_spinner,
)

if TYPE_CHECKING:
    from mixpanel_headless._internal.me import MeProjectInfo, MeResponse


def _project_picker_tty(
    me: MeResponse,
    sorted_projects: list[tuple[str, MeProjectInfo]],
) -> str:
    """Render the project picker prompt to stderr and return the chosen ID.

    Per cli-commands.md §1.6.1: prints the numbered list, accepts ``[1]``
    as default, and re-prompts up to 3 times on invalid input.

    Args:
        me: Parsed /me response (used to detect multi-org context).
        sorted_projects: Pre-sorted ``[(project_id, MeProjectInfo)]``.

    Returns:
        The chosen project ID.

    Raises:
        ConfigError: Non-TTY context (E-9), stdin closed mid-prompt
            (``EOFError`` re-raised as ``ConfigError`` so the
            ``@handle_errors`` decorator can render a structured
            message instead of a Python traceback), or three
            consecutive invalid responses (E-14).
    """
    from mixpanel_headless.exceptions import ConfigError

    org_count = len(me.organizations)
    err_console.print(
        f"\nFound {len(sorted_projects)} project(s) "
        f"across {org_count} organization(s):\n"
    )
    for idx, (pid, info) in enumerate(sorted_projects, start=1):
        if org_count > 1:
            org = me.organizations.get(str(info.organization_id))
            org_name = org.name if org else f"org {info.organization_id}"
            label = f"{org_name} · {info.name}"
        else:
            label = info.name
        domain = info.domain or "(no domain)"
        err_console.print(f"  {idx}) {label:<40} (id {pid}, {domain})")
    err_console.print("")

    if not sys.stdin.isatty():
        accessible_lines = "\n".join(
            f"  - {pid} : {info.name} ({info.domain or '(no domain)'})"
            for pid, info in sorted_projects
        )
        raise ConfigError(
            f"Multiple projects accessible to this account; no default "
            f"could be picked.\n\n"
            f"Accessible projects:\n{accessible_lines}\n\n"
            f"Pass --project ID to select one explicitly, or set MP_PROJECT_ID."
        )

    for _attempt in range(3):
        # Route the prompt itself through err_console so stdout stays
        # clean for `mp login | tee log.txt` (cli-commands.md §1.4).
        # Bare ``input(prompt)`` would write the prompt to stdout. Use
        # ``end=""`` so the cursor sits beside the prompt instead of
        # dropping to the next line.
        err_console.print("Which project? [1]: ", end="")
        line = sys.stdin.readline()
        if line == "":
            # readline() returns "" only on EOF — preserves the original
            # EOFError handling so callers redirecting `< /dev/null`
            # after the isatty() snapshot still get a structured exit.
            raise ConfigError(
                "stdin closed during project picker prompt. "
                "Pass --project ID or set MP_PROJECT_ID and re-run."
            )
        raw = line.rstrip("\n").strip()
        if not raw:
            return sorted_projects[0][0]
        # ``str.isdigit`` is True for Unicode digits (²,٣) that
        # ``int()`` rejects with ValueError. Wrap so a paste of an
        # exotic codepoint re-prompts via the loop instead of bubbling
        # up to ``@handle_errors`` as a generic Exception.
        try:
            choice = int(raw)
        except ValueError:
            choice = None
        if choice is not None and 1 <= choice <= len(sorted_projects):
            return sorted_projects[choice - 1][0]
        err_console.print(
            f"[red]Invalid input: {raw!r}.[/red] Enter a number from 1 to "
            f"{len(sorted_projects)} (or press Enter for the default)."
        )
    raise ConfigError("Could not pick a project after 3 attempts. Aborting.")


@handle_errors
def login(
    ctx: typer.Context,
    name: Annotated[
        str | None,
        typer.Option(
            "--name",
            help="Local account name. Wins over derived names.",
        ),
    ] = None,
    region: Annotated[
        str | None,
        typer.Option(
            "--region",
            help="Force a specific region (us | eu | in).",
        ),
    ] = None,
    project: Annotated[
        str | None,
        typer.Option(
            "--project",
            help="Project ID to bind to the new account. Hard-fails if not visible.",
        ),
    ] = None,
    service_account: Annotated[
        bool,
        typer.Option(
            "--service-account",
            "-S",
            help="Force the service_account auth path.",
        ),
    ] = False,
    token_env: Annotated[
        str | None,
        typer.Option(
            "--token-env",
            help=(
                "Force oauth_token auth from the named env var "
                "(e.g. --token-env MY_TOKEN). When omitted, MP_OAUTH_TOKEN "
                "is consulted automatically."
            ),
        ),
    ] = None,
    no_browser: Annotated[
        bool,
        typer.Option(
            "--no-browser",
            help="For oauth_browser, print the authorization URL instead of opening the browser.",
        ),
    ] = False,
    secret_stdin: Annotated[
        bool,
        typer.Option(
            "--secret-stdin",
            help="For service_account, read the secret from stdin.",
        ),
    ] = False,
) -> None:
    """Add a Mixpanel account with guided region / project / name resolution.

    Composes the 043 helpers (region probe, /me-driven project + name
    derivation, atomic publish for browser auth) into a single
    conversational command. All progress narration goes to stderr; the
    success summary goes to stdout as a single line.

    Examples:

        mp login                                    # browser, single project
        MP_USERNAME=svc MP_SECRET=$(cat s) mp login # SA, region auto-probed
        cat secret | mp login --service-account --secret-stdin --name prod-sa
        MY_TOKEN=eyJ... mp login --token-env MY_TOKEN
        mp login --project 3713224                  # browser, skip prompt
        mp login --no-browser                       # headless oauth flow

    Args:
        ctx: Typer context. Used to wire ``--quiet`` into the spinner
            wrapped around the orchestrator's ``/me`` round-trip.
        name: Local account name. Wins over derived names.
        region: Forces a specific region.
        project: Project ID to bind to. Hard-fails if not visible to /me.
        service_account: Force service_account auth path (E-11 if also --token-env).
        token_env: Env-var name carrying the bearer (oauth_token).
        no_browser: For oauth_browser, print the URL instead of launching.
        secret_stdin: For service_account, read the secret from stdin.
    """
    # Region is the only flag the orchestrator can't validate (it
    # accepts a Region literal, not an arbitrary string). Reject early
    # so a typo never reaches the placeholder dir / probe loop.
    if region is not None and region not in ("us", "eu", "in"):
        err_console.print(
            f"[red]ERROR:[/red] Invalid --region: {region!r} (use us / eu / in)."
        )
        raise typer.Exit(ExitCode.INVALID_ARGS)

    # All other flag-combination validation lives in
    # ``accounts.login_unified`` and surfaces as
    # ``InvalidArgumentError`` (subclass of ``ConfigError``) with a
    # ``violation`` discriminator the @handle_errors decorator maps to
    # exit 3. Keeping the rules in the orchestrator means non-CLI
    # callers (Cowork, JSON consumers) get the same protection without
    # having to re-implement the matrix.
    # Wrap the orchestrator's /me fetch in a Rich spinner. /me is the
    # slowest single call in the login flow (multi-second when an
    # account spans many projects across orgs); without this hook the
    # terminal looks hung between region-probe narration and the
    # project picker. ``status_spinner`` honors --quiet and falls back
    # to a no-op in non-TTY contexts so piped invocations stay clean.
    summary = accounts_ns.login_unified(
        name=name,
        region=region,  # type: ignore[arg-type]  # validated above
        project=project,
        no_browser=no_browser,
        secret_stdin=secret_stdin,
        token_env=token_env,
        service_account=service_account,
        project_picker=_project_picker_tty,
        progress=lambda msg: status_spinner(ctx, msg),
    )

    # Stdout success line (single line, structured for `mp login | tee log.txt`).
    # cli-commands.md §1.4 fixes the format as
    # ``Logged in as {user_email} → {account_name} · {project_name}``.
    # Each /me-derived field falls back to a literal "(unknown ...)" when
    # absent so the line stays parseable even on partial /me payloads.
    user_email = summary.user_email or "(unknown user)"
    project_label = summary.project_name or "(no project)"
    console.print(f"Logged in as {user_email} → {summary.name} · {project_label}")
