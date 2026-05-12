"""Single-function resolver for ``Session`` construction.

Replaces the six-layer fallback chain in the legacy ``ConfigManager`` with
one pure-functional ``resolve_session`` that consults independent priority
axes:

    Account axis:    env → param → target → bridge → [active].account
    Project axis:    env → param → target → bridge → account.default_project
    Workspace axis:  env → param → target → bridge → [active].workspace

Each axis is independent — perturbing one input never affects the others
(verified by Hypothesis property tests). The project axis chain ends at the
resolved account (its ``default_project`` field) — there is no
``[active].project`` fallback. Switching accounts implicitly switches
projects (FR-033).

The resolver does no I/O beyond optionally reading the config and bridge
file (both passed in by the caller); never reads OAuth tokens (those are
fetched lazily by ``MixpanelAPIClient`` at request time); never mutates
``os.environ``.

Per spec FR-024, when an axis cannot be resolved, the raised
``ConfigError`` lists every fix path the user can try.

Reference: specs/042-auth-architecture-redesign/contracts/python-api.md §1.
"""

from __future__ import annotations

import os
import typing

from pydantic import SecretStr, ValidationError

from mixpanel_headless._internal.auth.account import (
    Account,
    OAuthTokenAccount,
    Region,
    ServiceAccount,
)
from mixpanel_headless._internal.auth.bridge import BridgeFile, load_bridge
from mixpanel_headless._internal.auth.session import (
    Project,
    Session,
    WorkspaceRef,
)
from mixpanel_headless._internal.config import ConfigManager
from mixpanel_headless.exceptions import ConfigError

# Derive from the ``Region`` Literal so adding a new region (e.g. ``"jp"``)
# happens in exactly one place — the type — and every runtime check picks
# it up automatically.
_VALID_REGIONS: frozenset[str] = frozenset(typing.get_args(Region))


def _env_region() -> Region | None:
    """Return ``MP_REGION`` if it's a valid region literal, else ``None``.

    Returns:
        The region value (``us`` / ``eu`` / ``in``) when set, or ``None``
        when the env var is absent.

    Raises:
        ConfigError: When ``MP_REGION`` is set to a value outside the
            allowed set. Silently dropping an invalid region would route
            requests to the wrong data residency (or fall through to a
            different auth source) without telling the user — surface
            the typo loudly instead.
    """
    val = os.environ.get("MP_REGION")
    if not val:
        return None
    if val not in _VALID_REGIONS:
        raise ConfigError(
            f"MP_REGION={val!r} is not one of {sorted(_VALID_REGIONS)}.",
            details={"env_var": "MP_REGION", "value": val},
        )
    return val  # type: ignore[return-value]


def _env_account_from_service_quad() -> Account | None:
    """Synthesize a ``ServiceAccount`` if the full SA env quad is present.

    The SA quad is ``MP_USERNAME`` + ``MP_SECRET`` + ``MP_PROJECT_ID`` +
    ``MP_REGION``. When all four are set, returns an in-memory
    ``ServiceAccount`` with a synthetic name; ``MP_PROJECT_ID`` itself is
    only used by the project axis (the account synthesis only needs region).

    Returns:
        A synthesized ``ServiceAccount``, or ``None`` if any quad member
        is missing or invalid.
    """
    username = os.environ.get("MP_USERNAME")
    secret = os.environ.get("MP_SECRET")
    project = os.environ.get("MP_PROJECT_ID")
    region = _env_region()
    if not username or not secret or not project or region is None:
        return None
    try:
        return ServiceAccount(
            name="env-service-account",
            region=region,
            username=username,
            secret=SecretStr(secret),
        )
    except ValidationError:  # pragma: no cover — defensive
        return None


def _env_account_from_oauth_token() -> Account | None:
    """Synthesize an ``OAuthTokenAccount`` from ``MP_OAUTH_TOKEN`` env.

    Requires ``MP_OAUTH_TOKEN`` + ``MP_PROJECT_ID`` + ``MP_REGION``. The
    SA quad takes precedence (per PR #125 — preserved by this resolver).

    Returns:
        A synthesized ``OAuthTokenAccount``, or ``None`` if any required
        env var is missing or invalid.
    """
    token = os.environ.get("MP_OAUTH_TOKEN")
    project = os.environ.get("MP_PROJECT_ID")
    region = _env_region()
    if not token or not project or region is None:
        return None
    try:
        return OAuthTokenAccount(
            name="env-oauth-token",
            region=region,
            token=SecretStr(token),
        )
    except ValidationError:  # pragma: no cover — defensive
        return None


def resolve_account_axis(
    *,
    explicit: str | None,
    target_account_name: str | None,
    bridge: BridgeFile | None,
    config: ConfigManager,
) -> Account | None:
    """Resolve the account axis per the documented priority order.

    Order:
        1. Env: SA quad first (PR #125), then OAuth-token env.
        2. Explicit ``account=NAME`` param → load from config.
        3. ``--target NAME`` → load the target's referenced account.
        4. Bridge file's account.
        5. ``[active].account`` from config.

    Args:
        explicit: Value of ``account=`` kwarg (or env-var override).
        target_account_name: When ``--target NAME`` was applied, the
            account name from that target block.
        bridge: Loaded bridge file, if any.
        config: ConfigManager (may have an empty ``[active]`` block).

    Returns:
        The resolved ``Account``, or ``None`` if no source produced a value.
    """
    sa = _env_account_from_service_quad()
    if sa is not None:
        return sa
    ot = _env_account_from_oauth_token()
    if ot is not None:
        return ot
    if explicit is not None:
        return config.get_account(explicit)
    if target_account_name is not None:
        return config.get_account(target_account_name)
    if bridge is not None:
        return bridge.account
    active = config.get_active()
    if active.account is not None:
        return config.get_account(active.account)
    return None


def resolve_project_axis(
    *,
    explicit: str | None,
    target_project: str | None,
    bridge: BridgeFile | None,
    account: Account | None,
) -> str | None:
    """Resolve the project axis per the documented priority order.

    Order (per FR-017): env > param > target > bridge > ``account.default_project``.

    The chain ends at the resolved account; there is no ``[active].project``
    fallback. Project lives on the account itself (``Account.default_project``)
    rather than in the global ``[active]`` block — switching accounts implicitly
    switches projects (FR-033).

    Args:
        explicit: Value of ``project=`` kwarg.
        target_project: Project from ``--target NAME``, if applied.
        bridge: Loaded bridge file, if any.
        account: The resolved account whose ``default_project`` is consulted as
            the bottom layer of the chain.

    Returns:
        Project ID (digit string), or ``None`` if no source resolves.
    """
    env_val = os.environ.get("MP_PROJECT_ID")
    if env_val:
        if not env_val.isdigit():
            raise ConfigError(
                f"MP_PROJECT_ID={env_val!r} must be a digit string.",
                details={"env_var": "MP_PROJECT_ID", "value": env_val},
            )
        return env_val
    if explicit is not None:
        return explicit
    if target_project is not None:
        return target_project
    if bridge is not None and bridge.project is not None:
        return bridge.project
    if account is not None:
        return account.default_project
    return None


def env_workspace_id() -> int | None:
    """Return ``MP_WORKSPACE_ID`` as a validated positive int, or ``None``.

    Centralises the env validation so every caller — :func:`resolve_workspace_axis`
    and the in-session ``Workspace.use(account=...)`` path that intentionally
    skips the ``[active]`` fallback per FR-033 — surfaces identical errors
    on malformed input.

    Returns:
        Parsed positive integer, or ``None`` if the env var is unset.

    Raises:
        ConfigError: ``MP_WORKSPACE_ID`` is set but not a positive integer.
    """
    env_val = os.environ.get("MP_WORKSPACE_ID")
    if not env_val:
        return None
    try:
        parsed = int(env_val)
    except ValueError as exc:
        raise ConfigError(
            f"MP_WORKSPACE_ID={env_val!r} is not a positive integer.",
            details={"env_var": "MP_WORKSPACE_ID", "value": env_val},
        ) from exc
    if parsed <= 0:
        raise ConfigError(
            f"MP_WORKSPACE_ID={env_val!r} is not a positive integer.",
            details={"env_var": "MP_WORKSPACE_ID", "value": env_val},
        )
    return parsed


def resolve_workspace_axis(
    *,
    explicit: int | None,
    target_workspace: int | None,
    bridge: BridgeFile | None,
    config: ConfigManager,
) -> int | None:
    """Resolve the workspace axis per the documented priority order.

    Order (per FR-017): env > param > target > bridge > ``[active].workspace``.

    ``None`` is a valid terminal value (lazy resolution on first
    workspace-scoped API call per FR-025).

    Args:
        explicit: Value of ``workspace=`` kwarg.
        target_workspace: Workspace from ``--target NAME``, if applied.
        bridge: Loaded bridge file, if any.
        config: ConfigManager.

    Returns:
        Workspace ID, or ``None`` (lazy-resolve later).
    """
    env_val = env_workspace_id()
    if env_val is not None:
        return env_val
    if explicit is not None:
        return explicit
    if target_workspace is not None:
        return target_workspace
    if bridge is not None and bridge.workspace is not None:
        return bridge.workspace
    active = config.get_active()
    return active.workspace


def _resolve_headers(
    *, bridge: BridgeFile | None, config: ConfigManager
) -> dict[str, str]:
    """Collect custom HTTP headers from settings + bridge.

    ``[settings].custom_header`` contributes a single ``{name: value}``
    entry; the bridge contributes a multi-entry map. Bridge wins on
    collision (highest priority among header sources, matching the
    bridge's general "ephemeral override" role).

    Args:
        bridge: Loaded bridge file, if any.
        config: ConfigManager.

    Returns:
        Headers map ready to attach to ``Session.headers``.
    """
    headers: dict[str, str] = {}
    setting = config.get_custom_header()
    if setting is not None:
        headers[setting[0]] = setting[1]
    if bridge is not None and bridge.headers:
        headers.update(bridge.headers)
    return headers


def format_no_account_error() -> str:
    """Return the multi-line FR-024 error for an unresolvable account axis."""
    return (
        "No account configured.\n"
        "\n"
        "Fix one of the following:\n"
        "  - Set MP_USERNAME, MP_SECRET, MP_PROJECT_ID, MP_REGION\n"
        "  - Set MP_OAUTH_TOKEN, MP_PROJECT_ID, MP_REGION\n"
        "  - Run `mp account add NAME ...` then `mp account use NAME`\n"
        "  - Run `mp account login NAME` for OAuth\n"
        "  - Use `--account NAME` per command\n"
        "  - Use `--target NAME` per command\n"
    )


def format_no_project_error(account: Account | None = None) -> str:
    """Return the multi-line FR-024 error for an unresolvable project axis.

    Args:
        account: The resolved account (when available) so the error can name
            it explicitly — helps the user know which account needs a project.
    """
    if account is not None:
        return (
            f"No project configured for account {account.name!r}.\n"
            "\n"
            "Fix one of the following:\n"
            "  - Set MP_PROJECT_ID\n"
            f"  - Run `mp account update {account.name} --project ID`\n"
            "  - Use `--project ID` per command\n"
            "  - Use `--target NAME` per command (target supplies project)\n"
        )
    return (
        "No project configured.\n"
        "\n"
        "Fix one of the following:\n"
        "  - Set MP_PROJECT_ID\n"
        "  - Run `mp account update NAME --project ID` for an existing account\n"
        "  - Add an account with a project: `mp account add NAME ... --project ID`\n"
        "  - Use `--project ID` per command\n"
        "  - Use `--target NAME` per command (target supplies project)\n"
    )


def resolve_session(
    *,
    account: str | None = None,
    project: str | None = None,
    workspace: int | None = None,
    target: str | None = None,
    config: ConfigManager | None = None,
    bridge: BridgeFile | None = None,
) -> Session:
    """Resolve a :class:`Session` from per-axis inputs and config sources.

    Per FR-016: the three axes resolve independently. Per FR-017: each
    axis consults env → param → target → bridge → config in priority
    order. The resolver is pure-functional: no token I/O, no env
    mutation, no network.

    Args:
        account: Explicit account name (e.g., from ``--account NAME``).
        project: Explicit project ID (e.g., from ``--project ID``).
        workspace: Explicit workspace ID (e.g., from ``--workspace ID``).
        target: Named target whose three axes apply (mutually exclusive
            with ``account=``/``project=``/``workspace=``).
        config: ConfigManager. Defaults to a freshly constructed
            ``ConfigManager()`` reading ``MP_CONFIG_PATH`` or
            ``~/.mp/config.toml``.
        bridge: Pre-loaded bridge file. If ``None``, the resolver loads
            via :func:`load_bridge` (which honors ``MP_AUTH_FILE`` + the
            default search paths).

    Returns:
        A frozen :class:`Session` with account, project, optional
        workspace, and any custom headers attached.

    Raises:
        ValueError: ``target`` combined with any axis kwarg.
        ConfigError: An axis cannot be resolved or refers to an unknown
            account / target.
    """
    if target is not None and (
        account is not None or project is not None or workspace is not None
    ):
        raise ValueError(
            "`target=` is mutually exclusive with `account=`/`project=`/`workspace=`."
        )

    cfg = config if config is not None else ConfigManager()
    br = bridge if bridge is not None else load_bridge()

    target_account_name: str | None = None
    target_project: str | None = None
    target_workspace: int | None = None
    if target is not None:
        t = cfg.get_target(target)
        target_account_name = t.account
        target_project = t.project
        target_workspace = t.workspace

    account_obj = resolve_account_axis(
        explicit=account,
        target_account_name=target_account_name,
        bridge=br,
        config=cfg,
    )
    if account_obj is None:
        raise ConfigError(format_no_account_error())

    project_id = resolve_project_axis(
        explicit=project,
        target_project=target_project,
        bridge=br,
        account=account_obj,
    )
    if project_id is None:
        raise ConfigError(format_no_project_error(account_obj))
    try:
        project_obj = Project(id=project_id)
    except ValidationError as exc:
        raise ConfigError(
            f"Invalid project ID: {project_id!r}. Must match `^\\d+$`."
        ) from exc

    workspace_id = resolve_workspace_axis(
        explicit=workspace,
        target_workspace=target_workspace,
        bridge=br,
        config=cfg,
    )
    workspace_obj: WorkspaceRef | None = None
    if workspace_id is not None:
        try:
            workspace_obj = WorkspaceRef(id=workspace_id)
        except ValidationError as exc:
            raise ConfigError(
                f"Invalid workspace ID: {workspace_id!r}. Must be > 0."
            ) from exc

    headers = _resolve_headers(bridge=br, config=cfg)

    return Session(
        account=account_obj,
        project=project_obj,
        workspace=workspace_obj,
        headers=headers,
    )


__all__ = [
    "format_no_account_error",
    "format_no_project_error",
    "resolve_account_axis",
    "resolve_project_axis",
    "resolve_session",
]
