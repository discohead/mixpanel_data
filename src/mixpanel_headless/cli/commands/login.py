"""``mp login`` Typer command.

Thin wrapper over :func:`accounts.login_unified` that adds the
TTY-aware project / org pickers and the structured stdout success line.
The two-shot ``--start`` / ``--finish`` / ``--resume`` flow added on top
emits machine-parseable JSON envelopes on stdout (rather than the
single-line success summary) so the slash command and other programmatic
consumers can drive it without parsing prose.

Reference: ``specs/043-frictionless-auth/contracts/cli-commands.md`` §1
plus the two-shot extension in the implementation plan.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Annotated, Any

import typer

from mixpanel_headless import accounts as accounts_ns
from mixpanel_headless.cli.utils import (
    ExitCode,
    console,
    err_console,
    handle_errors,
    status_spinner,
)
from mixpanel_headless.exceptions import InvalidArgumentError, NeedsRegionSwitchError

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


_SCHEMA_VERSION = 1
"""Response envelope schema version for ``--start`` / ``--finish`` / ``--resume``.

Bumped only on non-additive changes that would break a slash command
parser compiled against the older shape. Adding fields is fine; removing
or renaming requires a bump."""

_PROJECT_NEXT = [
    {"command": "mp project list", "label": "See all accessible projects"},
    {"command": "mp project use <id>", "label": "Switch to a different project"},
]
"""Verbatim mirror of ``auth_manager.py:_PROJECT_NEXT`` so the slash
command's existing renderer works against the success envelope without
new branches."""


def _build_start_envelope(start: accounts_ns.LoginStartResult) -> dict[str, Any]:
    """Build the ``mp login --start`` JSON envelope.

    Args:
        start: The :class:`accounts_ns.LoginStartResult` from
            :func:`accounts.login_unified_start`.

    Returns:
        Dict serializable as the documented ``state: ok`` start envelope.
    """
    from mixpanel_headless._internal.auth.inflight import inflight_path

    inflight = start.inflight
    return {
        "schema_version": _SCHEMA_VERSION,
        "state": "ok",
        "authorize_url": start.authorize_url,
        "redirect_uri": inflight.redirect_uri,
        "expires_at": inflight.expires_at,
        "region": inflight.region,
        "inflight_path": str(inflight_path()),
    }


def _build_finish_envelope(result: accounts_ns._PublishResult) -> dict[str, Any]:
    """Build the ``state: ok`` envelope for ``--finish`` / ``--resume``.

    Args:
        result: :class:`accounts._PublishResult` from
            :func:`accounts.login_unified_finish` or
            :func:`accounts.login_unified_resume`.

    Returns:
        Dict matching the §9 ``state: ok`` envelope shape.
    """
    summary = result.summary
    pick = result.pick
    project_block: dict[str, Any] | None = None
    if summary.project_id is not None:
        project_block = {
            "id": summary.project_id,
            "name": summary.project_name,
        }
    user_block: dict[str, Any] | None = None
    if summary.user_email is not None:
        user_block = {"email": summary.user_email}
    return {
        "schema_version": _SCHEMA_VERSION,
        "state": "ok",
        "account": {
            "name": summary.name,
            "type": summary.type,
            "region": summary.region,
        },
        "user": user_block,
        "project": project_block,
        "project_pick": {
            "auto_picked": pick.method not in ("explicit", "tty_picker"),
            "method": pick.method,
            "primary_org_id": pick.primary_org_id,
            "primary_org_name": pick.primary_org_name,
            "primary_org_survivor_count": pick.primary_org_survivor_count,
            "accessible_project_count": pick.accessible_project_count,
            "region_compatible_count": pick.region_compatible_count,
            "filtered_count": pick.filtered_count,
            "demo_excluded": pick.demo_excluded,
            "unintegrated_excluded": pick.unintegrated_excluded,
        },
        "next": _PROJECT_NEXT,
    }


def _build_region_switch_envelope(exc: NeedsRegionSwitchError) -> dict[str, Any]:
    """Build the ``state: error code: NEEDS_REGION_SWITCH`` envelope.

    Args:
        exc: The :class:`NeedsRegionSwitchError` raised by the auto-pick
            algorithm when 0 region-compatible projects exist.

    Returns:
        Dict matching the §9 ``state: error`` envelope shape.
    """
    pick = exc.pick
    cross = pick.cross_region_projects or []
    return {
        "schema_version": _SCHEMA_VERSION,
        "state": "error",
        "error": {
            "code": "NEEDS_REGION_SWITCH",
            "message": exc.message,
            "actionable": True,
            "details": {
                "auth_region": pick.auth_region,
                "cross_region_projects": [
                    {"id": pid, "name": name, "domain": domain}
                    for pid, name, domain in cross
                ],
            },
        },
    }


def _emit_json(payload: dict[str, Any]) -> None:
    """Print ``payload`` as a single line of compact JSON to stdout.

    Single-line so the slash command's ``json.loads(stdout)`` works
    without scanning for object boundaries. ``default=str`` lets
    ``datetime`` and ``Path`` instances slip through untouched.

    Args:
        payload: The envelope dict to serialize.
    """
    print(json.dumps(payload, default=str))


def _validate_two_shot_flag_combos(
    *,
    start: bool,
    finish: str | None,
    resume: Path | None,
    service_account: bool,
    token_env: str | None,
    secret_stdin: bool,
    no_browser: bool,
    name: str | None,
    project: str | None,
) -> None:
    """Reject incompatible flag combinations BEFORE any I/O.

    Mirrors the ``InvalidArgumentError`` patterns the orchestrator already
    uses for the legacy paths so the slash command sees the same exit 3
    behavior whether the user mismatches a legacy flag or a new flag.

    Args:
        start: ``--start`` flag value.
        finish: ``--finish URL`` flag value.
        resume: ``--resume PATH`` flag value.
        service_account: ``--service-account`` flag value.
        token_env: ``--token-env`` flag value.
        secret_stdin: ``--secret-stdin`` flag value.
        no_browser: ``--no-browser`` flag value.
        name: ``--name`` flag value (only invalid for ``--start``).
        project: ``--project`` flag value (only invalid for ``--start``).

    Raises:
        InvalidArgumentError: Any of the documented invalid combinations.
    """
    two_shot_set = sum(1 for f in (start, finish is not None, resume is not None) if f)
    if two_shot_set > 1:
        raise InvalidArgumentError(
            "Pick exactly one of --start, --finish URL, --resume PATH "
            "(they are mutually exclusive).",
            violation="mutually_exclusive",
        )
    in_two_shot_mode = two_shot_set == 1
    if not in_two_shot_mode:
        return

    # Two-shot is oauth_browser-only — none of the legacy auth-type flags apply.
    bad: list[str] = []
    if service_account:
        bad.append("--service-account")
    if token_env is not None:
        bad.append("--token-env")
    if secret_stdin:
        bad.append("--secret-stdin")
    if no_browser:
        bad.append("--no-browser")
    if bad:
        raise InvalidArgumentError(
            f"--start / --finish / --resume are oauth_browser-only and "
            f"incompatible with: {', '.join(bad)}.",
            violation="mutually_exclusive",
            detected_auth_type="oauth_browser",
        )

    if start and (name is not None or project is not None):
        # --start emits the authorize URL only; name + project decisions
        # happen at --finish time when /me is available.
        raise InvalidArgumentError(
            "--start cannot accept --name or --project (those decisions "
            "happen at --finish time, after /me runs).",
            violation="mutually_exclusive",
        )


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
    start: Annotated[
        bool,
        typer.Option(
            "--start",
            help=(
                "Two-shot flow: emit authorize URL + persist PKCE verifier, "
                "then exit. Run `mp login --finish URL` after the user "
                "authorizes in their browser. For Cowork / CI / "
                "non-TTY environments where the loopback callback can't "
                "reach the user's host browser."
            ),
        ),
    ] = False,
    finish: Annotated[
        str | None,
        typer.Option(
            "--finish",
            metavar="URL",
            help=(
                "Two-shot flow: complete login using the redirect URL "
                "pasted from the user's browser. Reads the inflight "
                "session, exchanges the code, runs /me + auto-pick + "
                "publish."
            ),
        ),
    ] = None,
    resume: Annotated[
        Path | None,
        typer.Option(
            "--resume",
            metavar="PATH",
            help=(
                "Two-shot flow: post-publish-failure recovery. PATH is "
                "the .tmp-* placeholder dir left in ~/.mp/accounts/ by "
                "a failed `mp login --finish`. Re-runs only the publish "
                "tail (no PKCE, no code exchange)."
            ),
        ),
    ] = None,
) -> None:
    """Add a Mixpanel account with guided region / project / name resolution.

    Composes the 043 helpers (region probe, /me-driven project + name
    derivation, atomic publish for browser auth) into a single
    conversational command. All progress narration goes to stderr; the
    success summary goes to stdout as a single line.

    The two-shot ``--start`` / ``--finish`` / ``--resume`` flow extends
    this for headless environments (Cowork sandboxes, CI runners,
    devcontainers, browserless SSH) where the loopback OAuth callback
    can't reach the user's host browser. The two-shot path emits machine-
    parseable JSON envelopes on stdout instead of the single-line
    success summary so slash commands and scripted wrappers can drive it.

    Examples:

        mp login                                    # browser, single project
        MP_USERNAME=svc MP_SECRET=$(cat s) mp login # SA, region auto-probed
        cat secret | mp login --service-account --secret-stdin --name prod-sa
        MY_TOKEN=eyJ... mp login --token-env MY_TOKEN
        mp login --project 3713224                  # browser, skip prompt
        mp login --no-browser                       # same-machine SSH paste-back
        mp login --start --region eu                # Cowork: print URL, exit
        mp login --finish 'http://localhost:.../callback?code=...&state=...'
        mp login --resume ~/.mp/accounts/.tmp-abc12345

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
        start: Two-shot flow: emit authorize URL + persist verifier, exit.
        finish: Two-shot flow: complete using the pasted redirect URL.
        resume: Two-shot flow: recover from a post-publish failure.
    """
    # Region is the only flag the orchestrator can't validate (it
    # accepts a Region literal, not an arbitrary string). Reject early
    # so a typo never reaches the placeholder dir / probe loop.
    if region is not None and region not in ("us", "eu", "in"):
        err_console.print(
            f"[red]ERROR:[/red] Invalid --region: {region!r} (use us / eu / in)."
        )
        raise typer.Exit(ExitCode.INVALID_ARGS)

    _validate_two_shot_flag_combos(
        start=start,
        finish=finish,
        resume=resume,
        service_account=service_account,
        token_env=token_env,
        secret_stdin=secret_stdin,
        no_browser=no_browser,
        name=name,
        project=project,
    )

    if start:
        start_result = accounts_ns.login_unified_start(region=region)  # type: ignore[arg-type]
        _emit_json(_build_start_envelope(start_result))
        return

    if finish is not None:
        try:
            result = accounts_ns.login_unified_finish(
                pasted_url=finish,
                name=name,
                project=project,
                project_picker=_project_picker_tty if sys.stdin.isatty() else None,
                progress=lambda msg: status_spinner(ctx, msg),
            )
        except NeedsRegionSwitchError as exc:
            _emit_json(_build_region_switch_envelope(exc))
            raise typer.Exit(ExitCode.NEEDS_SELECTION) from None
        _emit_json(_build_finish_envelope(result))
        return

    if resume is not None:
        try:
            result = accounts_ns.login_unified_resume(
                placeholder_dir=resume,
                name=name,
                project=project,
                project_picker=_project_picker_tty if sys.stdin.isatty() else None,
                progress=lambda msg: status_spinner(ctx, msg),
            )
        except NeedsRegionSwitchError as exc:
            _emit_json(_build_region_switch_envelope(exc))
            raise typer.Exit(ExitCode.NEEDS_SELECTION) from None
        _emit_json(_build_finish_envelope(result))
        return

    # Legacy single-shot path — unchanged behavior.
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

    user_email = summary.user_email or "(unknown user)"
    project_label = summary.project_name or "(no project)"
    console.print(f"Logged in as {user_email} → {summary.name} · {project_label}")
