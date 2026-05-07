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
)

if TYPE_CHECKING:
    from mixpanel_headless._internal.auth.account import AccountType
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
        try:
            raw = input("Which project? [1]: ").strip()
        except EOFError:
            # stdin closed between the isatty() check above and the read
            # (e.g. shell redirected `< /dev/null` after the harness
            # snapshotted isatty). Surface as ConfigError so
            # @handle_errors renders a structured exit instead of a
            # bare Python traceback.
            raise ConfigError(
                "stdin closed during project picker prompt. "
                "Pass --project ID or set MP_PROJECT_ID and re-run."
            ) from None
        if not raw:
            return sorted_projects[0][0]
        if raw.isdigit() and 1 <= int(raw) <= len(sorted_projects):
            return sorted_projects[int(raw) - 1][0]
        err_console.print(
            f"[red]Invalid input: {raw!r}.[/red] Enter a number from 1 to "
            f"{len(sorted_projects)} (or press Enter for the default)."
        )
    raise ConfigError("Could not pick a project after 3 attempts. Aborting.")


def _flag_to_account_type(
    service_account: bool, token_env: str | None
) -> AccountType | None:
    """Map ``mp login`` CLI flags to the explicit ``account_type`` literal.

    Returns ``None`` when neither flag is set so the orchestrator falls
    through to env-var detection. Used both by the argument-validation
    step (to render E-12 / E-13 with the right ``Detected auth type``)
    and by the call into ``login_unified``.

    Args:
        service_account: Value of the ``--service-account`` flag.
        token_env: Value of the ``--token-env`` flag (``None`` if unset).

    Returns:
        ``"service_account"``, ``"oauth_token"``, or ``None``.
    """
    if service_account:
        return "service_account"
    if token_env is not None:
        return "oauth_token"
    return None


@handle_errors
def login(
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
                "Force oauth_token auth from the named env var. Defaults to "
                "MP_OAUTH_TOKEN when --token-env is passed without a value."
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
        name: Local account name. Wins over derived names.
        region: Forces a specific region.
        project: Project ID to bind to. Hard-fails if not visible to /me.
        service_account: Force service_account auth path (E-11 if also --token-env).
        token_env: Env-var name carrying the bearer (oauth_token).
        no_browser: For oauth_browser, print the URL instead of launching.
        secret_stdin: For service_account, read the secret from stdin.
    """
    # Argument validation (runs before any network I/O).
    if service_account and token_env is not None:
        err_console.print(
            "[red]ERROR:[/red] --service-account and --token-env are "
            "mutually exclusive.\n\n"
            "Pick one auth type:\n"
            "    mp login --service-account\n"
            "    mp login --token-env MY_OAUTH_TOKEN_VAR"
        )
        raise typer.Exit(ExitCode.INVALID_ARGS)

    # Detection runs through the orchestrator's own helper so the CLI's
    # argument-validation messages stay aligned with what `login_unified`
    # ultimately resolves. Two implementations would drift on the next
    # priority-order tweak.
    account_type = _flag_to_account_type(service_account, token_env)
    detected = accounts_ns._detect_login_type(account_type, token_env)  # noqa: SLF001

    if no_browser and detected != "oauth_browser":
        err_console.print(
            f"[red]ERROR:[/red] --no-browser is only meaningful for the "
            f"oauth_browser auth type.\n\n"
            f"Detected auth type: {detected}."
        )
        raise typer.Exit(ExitCode.INVALID_ARGS)

    if secret_stdin and detected != "service_account":
        err_console.print(
            f"[red]ERROR:[/red] --secret-stdin is only meaningful for the "
            f"service_account auth type.\n\n"
            f"Detected auth type: {detected}."
        )
        raise typer.Exit(ExitCode.INVALID_ARGS)

    # Region must be a valid Literal value when supplied.
    if region is not None and region not in ("us", "eu", "in"):
        err_console.print(
            f"[red]ERROR:[/red] Invalid --region: {region!r} (use us / eu / in)."
        )
        raise typer.Exit(ExitCode.INVALID_ARGS)

    summary = accounts_ns.login_unified(
        name=name,
        region=region,  # type: ignore[arg-type]  # validated above
        project=project,
        account_type=account_type,
        no_browser=no_browser,
        secret_stdin=secret_stdin,
        token_env=token_env,
        project_picker=_project_picker_tty,
    )

    # Activate the new (or refreshed) account so subsequent calls inherit it.
    accounts_ns.use(summary.name)

    # Stdout success line (single line, structured for `mp login | tee log.txt`).
    # AccountSummary doesn't carry default_project; pull it from the live Account.
    from mixpanel_headless._internal.config import ConfigManager

    account = ConfigManager().get_account(summary.name)
    project_label = account.default_project or "(no project)"
    console.print(f"Logged in → {summary.name} · {project_label}")
