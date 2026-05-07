"""Public ``mp.accounts`` namespace.

Thin wrapper around :class:`~mixpanel_headless._internal.config.ConfigManager`
exposing account CRUD, switching, and probing operations as the canonical
Python API for ``mp account ...`` CLI commands and the plugin's
``auth_manager.py``.

Reference: specs/042-auth-architecture-redesign/contracts/python-api.md §5.
"""

from __future__ import annotations

import builtins
import logging
import shutil
from pathlib import Path

from pydantic import SecretStr

from mixpanel_headless._internal.auth.account import (
    Account,
    AccountType,
    OAuthBrowserAccount,
    OAuthTokenAccount,
    ProjectId,
    Region,
    ServiceAccount,
)
from mixpanel_headless._internal.auth.storage import (
    account_dir,
    accounts_root,
    ensure_account_dir,
)
from mixpanel_headless._internal.auth.token import OAuthTokens, token_payload_bytes
from mixpanel_headless._internal.auth.token_resolver import OnDiskTokenResolver
from mixpanel_headless._internal.config import ConfigManager
from mixpanel_headless._internal.io_utils import atomic_write_bytes
from mixpanel_headless.exceptions import ConfigError, OAuthError
from mixpanel_headless.types import (
    AccountSummary,
    AccountTestResult,
    MeUserInfo,
    OAuthLoginResult,
)

logger = logging.getLogger(__name__)


def _config() -> ConfigManager:
    """Return a fresh ConfigManager honoring ``MP_CONFIG_PATH`` / ``$HOME``."""
    return ConfigManager()


def _safe_rmtree_warn(path: Path) -> None:
    """``shutil.rmtree(path)`` that logs a warning on failure instead of swallowing it.

    Used to clean up credential-bearing placeholder / rolled-back account
    directories. The prior ``shutil.rmtree(..., ignore_errors=True)`` was
    silent, leaving OAuth tokens on disk under a directory the user
    couldn't easily locate when cleanup itself failed (NFS lag, locked
    file, permission anomaly).

    Args:
        path: Directory to remove. Missing-path is a no-op.
    """
    if not path.exists():
        return
    try:
        shutil.rmtree(path)
    except OSError as cleanup_exc:
        logger.warning(
            "Failed to clean up %s containing OAuth tokens: %s. "
            "Run `rm -rf %s` manually to remove them.",
            path,
            cleanup_exc,
            path,
        )


def _domain_to_region(domain: str) -> Region | None:
    """Map a Mixpanel project ``domain`` string to its region.

    The ``MeProjectInfo.domain`` field carries the project's cluster
    hostname (e.g. ``eu.mixpanel.com``). Returns ``None`` for unknown
    or unparsable values so callers can skip the cross-check rather
    than misclassify.

    Args:
        domain: Project domain string (host, optionally with protocol).

    Returns:
        ``"us"`` / ``"eu"`` / ``"in"`` for recognized hosts, ``None``
        otherwise.

    Example:
        ```python
        _domain_to_region("eu.mixpanel.com")  # "eu"
        _domain_to_region("https://mixpanel.com/path")  # "us"
        _domain_to_region("data-eu.mixpanel.com")  # "eu"
        _domain_to_region("foo.example.com")  # None
        ```
    """
    if not domain:
        return None
    host = domain.lower().strip()
    if "://" in host:
        host = host.split("://", 1)[1]
    host = host.split("/", 1)[0]
    # Export hosts carry a "data-" or "data." prefix; normalize to the
    # canonical query-host form so the same lookup table works.
    if host.startswith("data-"):
        host = host[len("data-") :]
    elif host == "data.mixpanel.com":
        host = "mixpanel.com"
    table: dict[str, Region] = {
        "mixpanel.com": "us",
        "eu.mixpanel.com": "eu",
        "in.mixpanel.com": "in",
    }
    return table.get(host)


def list() -> builtins.list[AccountSummary]:  # noqa: A001 — public namespace shadow
    """Return all configured accounts as ``AccountSummary`` records.

    Returns:
        Sorted-by-name list of summaries.
    """
    return _config().list_accounts()


def add(
    name: str | None = None,
    *,
    type: AccountType,  # noqa: A002 — matches contracts/python-api.md
    region: Region | None = None,
    default_project: str | None = None,
    username: str | None = None,
    secret: SecretStr | str | None = None,
    token: SecretStr | str | None = None,
    token_env: str | None = None,
    derive_name: bool = False,
) -> AccountSummary:
    """Add a new account.

    Per 043 FR-001, ``default_project`` is OPTIONAL for every account
    type at add-time. Service-account and oauth_token callers can
    backfill it later via ``mp project use ID`` (or the ``mp login``
    orchestrator's project picker). For ``oauth_browser`` the value is
    additionally backfilled by ``login(name)`` from the ``/me`` lookup
    when no explicit project was set at add-time.

    Per FR-045, the first account added auto-promotes to
    ``[active].account``. Subsequent accounts do not.

    ## Derived naming (043 / AIE-116)

    Pass ``derive_name=True`` (and leave ``name=None``) to have the
    function fetch ``/me`` against the supplied credentials and pick a
    name from the first organization via
    :func:`naming.default_account_name`. ``derive_name=True`` together
    with an explicit ``name=`` is a logic error and raises
    ``TypeError`` to surface the conflict at the caller. Derivation is
    only supported for ``service_account`` and ``oauth_token`` — the
    ``oauth_browser`` path needs the PKCE flow to obtain credentials,
    which lives in ``mp login`` / ``login_unified`` (not here).

    Args:
        name: Account name (must match ``^[a-zA-Z0-9_-]{1,64}$``).
            Required unless ``derive_name=True``.
        type: One of ``service_account`` / ``oauth_browser`` / ``oauth_token``.
        region: One of ``us`` / ``eu`` / ``in``. May be omitted only for
            ``oauth_browser`` (the PKCE flow commits to the account's
            stored region at login time). For ``service_account`` and
            ``oauth_token``, ``region=None`` raises ``ConfigError`` —
            the Python API does not probe; pass ``--region`` to the CLI
            or use ``mp login`` for the guided probing flow.
        default_project: Numeric project ID. Optional for every type;
            populated later via ``mp project use`` or ``mp login``.
        username: Required for ``service_account``.
        secret: Required for ``service_account``.
        token: For ``oauth_token`` (mutually exclusive with ``token_env``).
        token_env: For ``oauth_token`` (mutually exclusive with ``token``).
        derive_name: When ``True``, fetch ``/me`` and pick a name via
            :func:`naming.default_account_name`. Mutually exclusive with
            ``name=`` (passing both raises ``TypeError``). Not supported
            for ``oauth_browser``.

    Returns:
        :class:`AccountSummary` for the new account.

    Raises:
        TypeError: ``derive_name=True`` with explicit ``name=...``, or
            ``derive_name=False`` with ``name=None``.
        ConfigError: Validation failure, duplicate name,
            ``region=None`` for a non-browser type, or ``derive_name=True``
            for ``oauth_browser``.
    """
    if derive_name and name is not None:
        raise TypeError(
            "`derive_name=True` and explicit `name=` are mutually exclusive."
        )
    if not derive_name and name is None:
        raise TypeError("`name` is required unless `derive_name=True`.")
    cm = _config()
    # Per 043 plan §"Library-First": region probing lives in the CLI
    # layer (where the per-attempt stderr narration is appropriate).
    # The Python API stays pure — it refuses to invent a region.
    if region is None and type != "oauth_browser":
        raise ConfigError(
            f"Account type {type!r} requires `region`. Pass region= "
            "explicitly, or use `mp login` for the guided probing flow."
        )
    # ``oauth_browser`` may default to ``us`` when no explicit region is
    # supplied — the PKCE flow commits to the account's stored region at
    # login time, and the post-callback ``/me`` cross-check (T022) will
    # surface a mismatch with an actionable error if the user picks a
    # project from a different cluster.
    resolved_region: Region = region if region is not None else "us"

    if derive_name:
        if type == "oauth_browser":
            raise ConfigError(
                "`derive_name=True` is not supported for oauth_browser. "
                "Use `mp login` (or `accounts.login_unified`) — the "
                "browser flow needs PKCE before /me can be reached."
            )
        name = _derive_account_name_for_credential(
            cm,
            account_type=type,
            region=resolved_region,
            username=username,
            secret=secret,
            token=token,
            token_env=token_env,
        )
    # ``derive_name`` and the ``not derive_name`` branch both leave
    # ``name`` populated by this point; the assert is a guard for the
    # static checker so the downstream call sites typecheck against
    # ``name: str`` rather than ``str | None``.
    assert name is not None

    # Compose the add-and-promote-as-active sequence in a single _mutate()
    # transaction so a fresh process never sees the new account without its
    # promoted [active].account when it was the first account added.
    with cm._mutate() as raw:
        is_first = not (raw.get("accounts") or {})
        cm._apply_add_account(
            raw,
            name,
            type=type,
            region=resolved_region,
            default_project=default_project,
            username=username,
            secret=secret,
            token=token,
            token_env=token_env,
        )
        if is_first:
            cm._apply_set_active(raw, account=name)
    return show(name)


def _derive_account_name_for_credential(
    cm: ConfigManager,
    *,
    account_type: AccountType,
    region: Region,
    username: str | None,
    secret: SecretStr | str | None,
    token: SecretStr | str | None,
    token_env: str | None,
) -> str:
    """Build a temporary Account, fetch ``/me``, and derive a unique name.

    Used by :func:`add` when ``derive_name=True``. Constructs an
    in-memory :class:`Account` with a placeholder name (never persisted),
    issues one ``/me`` call against the resolved region, and returns
    the slug picked by :func:`naming.default_account_name` against the
    set of currently-configured account names.

    Args:
        cm: The config manager (used to enumerate existing names).
        account_type: ``"service_account"`` or ``"oauth_token"``
            (``oauth_browser`` is rejected upstream — it needs PKCE).
        region: Resolved region (probed or supplied by the caller).
        username: SA username (required for service_account).
        secret: SA secret (required for service_account).
        token: oauth_token inline bearer (one of ``token`` / ``token_env``).
        token_env: oauth_token env-var name.

    Returns:
        A unique account name suitable for persistence.

    Raises:
        ConfigError: Credential collection failed or ``/me`` did not
            return parseable orgs.
    """
    from mixpanel_headless._internal.api_client import MixpanelAPIClient
    from mixpanel_headless._internal.auth.account import (
        OAuthTokenAccount,
        ProjectId,
        ServiceAccount,
    )
    from mixpanel_headless._internal.auth.naming import default_account_name
    from mixpanel_headless._internal.auth.session import Project, Session
    from mixpanel_headless._internal.me import MeResponse

    placeholder_name = "_tmp_naming_"
    placeholder_project = ProjectId("0")

    temp_account: ServiceAccount | OAuthTokenAccount
    if account_type == "service_account":
        if username is None or secret is None:
            raise ConfigError(
                "service_account requires `username` and `secret` to derive a name."
            )
        secret_value = secret if isinstance(secret, SecretStr) else SecretStr(secret)
        temp_account = ServiceAccount(
            name=placeholder_name,
            region=region,
            username=username,
            secret=secret_value,
            default_project=placeholder_project,
        )
    elif account_type == "oauth_token":
        if token is not None:
            token_value = token if isinstance(token, SecretStr) else SecretStr(token)
            temp_account = OAuthTokenAccount(
                name=placeholder_name,
                region=region,
                token=token_value,
                default_project=placeholder_project,
            )
        elif token_env is not None:
            temp_account = OAuthTokenAccount(
                name=placeholder_name,
                region=region,
                token_env=token_env,
                default_project=placeholder_project,
            )
        else:
            raise ConfigError(
                "oauth_token requires `token` or `token_env` to derive a name."
            )
    else:  # pragma: no cover — control-flow invariant
        raise ConfigError(
            f"derive_name not supported for account type {account_type!r}."
        )

    probe_session = Session(
        account=temp_account, project=Project(id=placeholder_project)
    )
    api_client = MixpanelAPIClient(session=probe_session)
    try:
        me_raw = api_client.me()
        me_resp = MeResponse.model_validate(me_raw)
    finally:
        api_client.close()

    existing_names: set[str] = {summary.name for summary in cm.list_accounts()}
    return default_account_name(me_resp, existing_names)


def update(
    name: str,
    *,
    region: Region | None = None,
    default_project: str | None = None,
    username: str | None = None,
    secret: SecretStr | str | None = None,
    token: SecretStr | str | None = None,
    token_env: str | None = None,
) -> AccountSummary:
    """Update fields on an existing account in place.

    Type cannot be changed via this function (remove + re-add for that).
    Type-incompatible fields raise ``ConfigError``.

    Args:
        name: Account to update.
        region: New region.
        default_project: New ``default_project`` (digit string).
        username: New username (service_account only).
        secret: New secret (service_account only).
        token: New inline token (oauth_token only).
        token_env: New env-var name (oauth_token only).

    Returns:
        Updated :class:`AccountSummary`.

    Raises:
        ConfigError: Account not found, type-incompatible field, or
            validation failure.
    """
    _config().update_account(
        name,
        region=region,
        default_project=default_project,
        username=username,
        secret=secret,
        token=token,
        token_env=token_env,
    )
    return show(name)


def remove(name: str, *, force: bool = False) -> builtins.list[str]:
    """Remove an account.

    Args:
        name: Account name.
        force: When ``True``, remove even if referenced by targets.

    Returns:
        List of orphaned target names (empty unless ``force=True`` and
        the account had references).

    Raises:
        ConfigError: Missing account.
        AccountInUseError: Referenced and ``force=False``.
    """
    return _config().remove_account(name, force=force)


def use(name: str) -> None:
    """Switch the active account, clearing any prior workspace pin.

    The new account becomes ``[active].account`` and any prior
    ``[active].workspace`` is dropped — workspaces are project-scoped, so
    a leftover workspace ID from a different account would resolve to a
    foreign workspace (or a 404) on the next ``Workspace()`` construction.
    Project lives on the account itself as
    :attr:`Account.default_project`, so it travels with the new account
    automatically — no separate project axis to reset.

    Both writes happen in a single ``_mutate()`` transaction so the
    next process never sees a half-swapped state.

    Args:
        name: Account to make active.

    Raises:
        ConfigError: Account does not exist.
    """
    cm = _config()
    with cm._mutate() as raw:
        cm._apply_set_active(raw, account=name)
        cm._apply_clear_active(raw, workspace=True)


def show(name: str | None = None) -> AccountSummary:
    """Return the named account summary, or the active one if no name given.

    Args:
        name: Account name; if ``None``, the active account is shown.

    Returns:
        :class:`AccountSummary`.

    Raises:
        ConfigError: Account not found OR no active account configured.
    """
    cm = _config()
    if name is None:
        active = cm.get_active().account
        if not active:
            raise ConfigError("No active account configured.")
        name = active
    summaries = {s.name: s for s in cm.list_accounts()}
    if name not in summaries:
        raise ConfigError(f"Account '{name}' not found.")
    return summaries[name]


def test(name: str | None = None) -> AccountTestResult:
    """Probe ``/me`` for the named account and return the structured result.

    Resolves the named account (or active account when ``name`` is None),
    constructs a short-lived :class:`MixpanelAPIClient` against ``/me``,
    and reports whether the credentials are accepted plus the
    authenticated user identity / accessible-project count from the
    response body.

    Never raises — every failure mode (account not found, missing
    credentials, OAuth refresh failure, HTTP error) is captured in
    ``result.error`` so the CLI can render a structured failure message
    and downstream tooling can color accounts as
    ``needs_login`` / ``needs_token`` based on the error string.

    Args:
        name: Account to test; ``None`` means the active account.

    Returns:
        :class:`AccountTestResult` — ``ok=True`` with ``user`` populated
        on success, or ``ok=False`` with ``error`` describing the failure.
    """
    try:
        summary = show(name)
    except ConfigError as exc:
        return AccountTestResult(
            account_name=name or "(none)", ok=False, error=str(exc)
        )

    cm = _config()
    try:
        account = cm.get_account(summary.name)
    except ConfigError as exc:  # pragma: no cover — show() already validated
        return AccountTestResult(account_name=summary.name, ok=False, error=str(exc))

    # Lazy imports to keep import-time cheap (httpx + threading pull in lots).
    from mixpanel_headless._internal.api_client import MixpanelAPIClient
    from mixpanel_headless._internal.auth.session import Project, Session
    from mixpanel_headless._internal.me import MeResponse

    # ``MixpanelAPIClient`` requires a project to construct a Session even
    # though ``/me`` itself is project-agnostic. Use the account's default
    # when present, falling back to ``"0"`` so probes still work for fresh
    # ``oauth_browser`` accounts that have not yet been login'd.
    placeholder_project = account.default_project or "0"
    probe_session = Session(
        account=account,
        project=Project(id=placeholder_project),
    )

    api_client = MixpanelAPIClient(session=probe_session)
    try:
        try:
            me_raw = api_client.me()
        except Exception as exc:  # noqa: BLE001 — capture every failure mode
            return AccountTestResult(
                account_name=summary.name,
                ok=False,
                error=f"/me probe failed: {exc}",
            )
        try:
            me_resp = MeResponse.model_validate(me_raw)
        except Exception as exc:  # noqa: BLE001 — malformed payload
            return AccountTestResult(
                account_name=summary.name,
                ok=False,
                error=f"/me response could not be parsed: {exc}",
            )
        user: MeUserInfo | None = None
        if me_resp.user_id is not None and me_resp.user_email is not None:
            user = MeUserInfo(id=me_resp.user_id, email=me_resp.user_email)
        project_count = len(me_resp.projects) if me_resp.projects else 0
        return AccountTestResult(
            account_name=summary.name,
            ok=True,
            user=user,
            accessible_project_count=project_count,
        )
    finally:
        api_client.close()


def login(
    name: str,
    *,
    open_browser: bool = True,
) -> OAuthLoginResult:
    """Run the OAuth browser flow for an ``oauth_browser`` account.

    Drives the full PKCE login dance:

    1. Validate ``name`` resolves to an ``oauth_browser`` account.
    2. Run :meth:`OAuthFlow.login` (PKCE + browser callback + token exchange).
    3. Persist the resulting tokens atomically to
       ``~/.mp/accounts/{name}/tokens.json``.
    4. Probe ``/me`` to capture the authenticated user identity and
       (when missing) backfill ``account.default_project`` with the first
       accessible project.

    The browser is opened by default; pass ``open_browser=False`` to
    skip the call (useful for headless environments where the user copies
    the authorization URL manually).

    Args:
        name: Account name (must be ``oauth_browser`` type).
        open_browser: Whether to launch the system browser. When False,
            the authorize URL is printed to stderr for manual copy
            (CLI flag: ``mp account login NAME --no-browser``).

    Returns:
        An :class:`OAuthLoginResult` describing the persistence paths,
        token expiry, and (best-effort) authenticated user identity.

    Raises:
        ConfigError: ``name`` is not configured or is not ``oauth_browser``.
        OAuthError: Any leg of the PKCE flow fails (registration, browser,
            callback, token exchange).
    """
    cm = _config()
    account = cm.get_account(name)
    if not isinstance(account, OAuthBrowserAccount):
        raise ConfigError(
            f"`mp account login` is only valid for oauth_browser accounts; "
            f"'{name}' is type '{account.type}'."
        )

    # Lazy imports — pull in OAuthFlow / Workspace only when actually logging in.
    from mixpanel_headless._internal.api_client import MixpanelAPIClient
    from mixpanel_headless._internal.auth.flow import OAuthFlow
    from mixpanel_headless._internal.auth.session import Project, Session
    from mixpanel_headless._internal.me import MeResponse

    flow = OAuthFlow(region=account.region)
    # ``persist=False`` skips the v2 ``~/.mp/oauth/tokens_{region}.json``
    # write — v3 owns ``~/.mp/accounts/{name}/tokens.json`` exclusively.
    tokens = flow.login(persist=False, open_browser=open_browser)

    tokens_path = _persist_browser_tokens(name, tokens)

    # /me probe: validates the freshly minted bearer + backfills the
    # account's default_project on first login.
    user: MeUserInfo | None = None
    chosen_project = account.default_project
    placeholder_project = chosen_project or "0"
    probe_session = Session(
        account=account,
        project=Project(id=placeholder_project),
    )
    api_client = MixpanelAPIClient(session=probe_session)
    try:
        try:
            me_raw = api_client.me()
            me_resp = MeResponse.model_validate(me_raw)
        except Exception as exc:  # noqa: BLE001 — re-raise as OAuthError below
            raise OAuthError(
                f"Login succeeded but `/me` probe failed: {exc}",
                code="OAUTH_TOKEN_ERROR",
                details={"account_name": name, "region": account.region},
            ) from exc
        if me_resp.user_id is not None and me_resp.user_email is not None:
            user = MeUserInfo(id=me_resp.user_id, email=me_resp.user_email)
        if chosen_project is None and me_resp.projects:
            # ``me_resp.projects`` keys are str at runtime; cast to ProjectId
            # to satisfy the typed contract on ``Account.default_project``.
            chosen_project = ProjectId(next(iter(sorted(me_resp.projects))))
            cm.update_account(name, default_project=chosen_project)
        # 043 / AIE-114: cross-check the picked project's cluster against
        # the auth region. The bearer is region-bound, so a mismatch
        # would surface on every subsequent request as a confusing 401.
        # Catching it here lets us print error catalog E-2 with the
        # specific re-run command.
        if chosen_project is not None and chosen_project in me_resp.projects:
            proj_info = me_resp.projects[chosen_project]
            if proj_info.domain:
                project_region = _domain_to_region(proj_info.domain)
                if project_region is not None and project_region != account.region:
                    raise ConfigError(
                        f"Region mismatch.\n\n"
                        f"You authenticated against the {account.region} "
                        f"cluster, but project {chosen_project} "
                        f"({proj_info.name}) lives in the "
                        f"{project_region} cluster ({proj_info.domain}).\n\n"
                        f"Re-run with the correct region:\n"
                        f"    mp login --region {project_region}"
                    )
    finally:
        api_client.close()

    return OAuthLoginResult(
        account_name=name,
        user=user,
        expires_at=tokens.expires_at,
        tokens_path=tokens_path,
        client_path=_client_info_path(account.region),
    )


def _persist_browser_tokens(name: str, tokens: OAuthTokens) -> Path:
    """Write ``tokens`` to the per-account ``tokens.json`` atomically (mode 0o600).

    Args:
        name: Account name (locates ``~/.mp/accounts/{name}/``).
        tokens: A :class:`OAuthTokens` instance just returned from
            :meth:`OAuthFlow.login`.

    Returns:
        The path that was written.
    """
    path = ensure_account_dir(name) / "tokens.json"
    atomic_write_bytes(path, token_payload_bytes(tokens))
    return path


def _client_info_path(region: Region) -> Path:
    """Return where ``OAuthFlow`` cached the DCR client info for ``region``.

    The v3 layout still shares DCR client metadata across accounts in the
    same region (every Mixpanel ``oauth_browser`` account speaks to the
    same authorization server, so there is one DCR client per region).
    Recorded for ``OAuthLoginResult.client_path`` so callers can find it.

    Args:
        region: Mixpanel data residency region.

    Returns:
        Absolute path to the client info JSON (may not exist yet).
    """
    return Path.home() / ".mp" / "oauth" / f"client_{region}.json"


def logout(name: str) -> None:
    """Remove the on-disk OAuth tokens for an ``oauth_browser`` account.

    Args:
        name: Account name.

    Raises:
        ConfigError: Account not found.
    """
    summary = show(name)  # raises if missing
    tokens_path = account_dir(summary.name) / "tokens.json"
    if tokens_path.exists():
        tokens_path.unlink()


def token(name: str | None = None) -> str | None:
    """Return the current bearer token for an OAuth account.

    Args:
        name: Account name; ``None`` means the active account.

    Returns:
        For ``service_account``: ``None`` (no bearer).
        For ``oauth_browser``: the on-disk access token (raises ``OAuthError``
        via the resolver if unavailable).
        For ``oauth_token``: the inline / env-resolved token.

    Raises:
        ConfigError: Account not found.
        OAuthError: OAuth token cannot be resolved (missing tokens, missing
            env var, etc.).
    """
    cm = _config()
    summary = show(name)
    account = cm.get_account(summary.name)
    resolver = OnDiskTokenResolver()
    if isinstance(account, ServiceAccount):
        return None
    if isinstance(account, OAuthBrowserAccount):
        return resolver.get_browser_token(account.name, account.region)
    if isinstance(account, OAuthTokenAccount):
        return resolver.get_static_token(account)
    raise ConfigError(  # pragma: no cover — Literal exhaustiveness
        f"Unknown account type for {summary.name!r}"
    )


def export_bridge(
    *,
    to: Path,
    account: str | None = None,
    project: str | None = None,
    workspace: int | None = None,
) -> Path:
    """Export the named (or active) account as a v2 bridge file.

    Resolves the account, attaches any ``[settings].custom_header`` as
    ``bridge.headers`` (B5 — header attaches in memory at resolution time
    for the consumer), and writes a 0o600 file at ``to`` via
    :func:`bridge.export_bridge`.

    Args:
        to: Destination path for the bridge file.
        account: Account to export; ``None`` means the active account.
        project: Optional pinned project ID. ``None`` omits the field.
        workspace: Optional pinned workspace ID. ``None`` omits the field.

    Returns:
        The path that was written (same as ``to``).

    Raises:
        ConfigError: Account not found, no active account, or
            ``BridgeFile`` validation failure.
        OAuthError: ``account.type == "oauth_browser"`` but no on-disk
            tokens are available.
    """
    from mixpanel_headless._internal.auth.bridge import (
        export_bridge as _bridge_export,
    )

    cm = _config()
    name = account or cm.get_active().account
    if name is None:
        raise ConfigError("No account specified and no active account configured.")
    acct = cm.get_account(name)
    header = cm.get_custom_header()
    headers = {header[0]: header[1]} if header is not None else None
    return _bridge_export(
        acct,
        to=to,
        project=project,
        workspace=workspace,
        headers=headers,
        token_resolver=OnDiskTokenResolver(),
    )


def remove_bridge(*, at: Path | None = None) -> bool:
    """Remove the v2 bridge file at ``at`` (or the default path).

    Args:
        at: Bridge file path; ``None`` means ``MP_AUTH_FILE`` then the
            default search paths.

    Returns:
        ``True`` if a file was deleted; ``False`` if none was found.
    """
    from mixpanel_headless._internal.auth.bridge import (
        remove_bridge as _bridge_remove,
    )

    return _bridge_remove(at=at)


def login_unified(
    *,
    name: str | None = None,
    region: Region | None = None,
    project: str | None = None,
    account_type: AccountType | None = None,
    no_browser: bool = False,
    secret_stdin: bool = False,
    token_env: str | None = None,
    project_picker: ProjectPicker | None = None,
    org_picker: OrgPicker | None = None,  # noqa: ARG001 — reserved for multi-org expansion in a follow-on iteration
) -> AccountSummary:
    """Add and activate a Mixpanel account in one orchestrated call (043 / AIE-117).

    The conversational entry point for ``mp login``. Composes the helpers
    landed in earlier 043 commits (region probe, name derivation, SA
    project relaxation) with the existing PKCE flow into a single call
    that goes from "no config" to "ready to query".

    ## Auth-type detection priority

    1. ``account_type`` parameter (explicit override).
    2. ``token_env`` set → ``oauth_token``.
    3. ``MP_USERNAME`` + ``MP_SECRET`` env both set → ``service_account``.
    4. ``MP_OAUTH_TOKEN`` env set → ``oauth_token``.
    5. Default → ``oauth_browser``.

    ## Project-selection priority (applied AFTER ``/me``)

    1. ``project`` parameter (must exist in ``/me``).
    2. ``MP_PROJECT_ID`` env (warn-and-fall-through if missing from ``/me``).
    3. Single project in ``/me`` → auto-pick.
    4. Caller-supplied ``project_picker`` callback (CLI provides one;
       library raises ``ConfigError`` E-8 when no callback is supplied).

    ## Region resolution

    - ``oauth_browser``: ``region`` (default ``"us"``) committed before
      the PKCE redirect; cross-checked against the picked project's
      ``domain`` after the callback.
    - ``service_account`` / ``oauth_token``: when ``region is None``,
      probes ``us → eu → in`` against ``/me`` until first 200.

    ## Re-login (when an existing account matches the resolved name)

    - Refreshes tokens (oauth_browser) or updates credentials (SA / token).
    - ``default_project`` is preserved; ``project`` / ``MP_PROJECT_ID``
      are ignored on this path (E-5 informational stderr note).
    - Region change → refused (E-3).
    - Auth-type change → refused (E-4).

    Args:
        name: Explicit local account name. Wins over derived names.
        region: Explicit region. ``None`` triggers the probe (SA / token)
            or defaults to ``us`` (oauth_browser).
        project: Explicit project ID. Must exist in ``/me``.
        account_type: Explicit auth-type override.
        no_browser: For oauth_browser, print the authorize URL instead
            of launching the browser.
        secret_stdin: For service_account, read the secret from stdin.
        token_env: For oauth_token, env-var name carrying the bearer.
            Defaults to ``MP_OAUTH_TOKEN`` when not set.
        project_picker: Callable invoked with ``(MeResponse, sorted_projects)``
            when ``len(me.projects) > 1`` and no other project source
            resolves. Returns the chosen project ID. The CLI supplies a
            TTY-aware picker; library callers can supply their own or
            leave it ``None`` to fail-fast non-interactively.
        org_picker: Analogous picker for org selection when
            ``len(me.organizations) > 1`` AND no explicit ``name`` was
            supplied. Returns the chosen org ID.

    Returns:
        :class:`AccountSummary` for the newly added (or refreshed) account.

    Raises:
        TypeError: ``account_type`` set to an unknown literal.
        ConfigError: Project not visible (E-6), region mismatch (E-2 / E-3),
            type mismatch (E-4), missing required env (cred collection),
            or non-interactive context with no project / org default
            (E-8 / E-9).
        OAuthError: PKCE failure or all-region probe failure
            (raised as :class:`RegionProbeError` subclass).

    Example:
        ```python
        # Browser login, single project, derived name from /me org
        result = login_unified()
        # AccountSummary(name="acme-corp", type="oauth_browser", ...)

        # Service account from env, region auto-detected
        os.environ["MP_USERNAME"] = "svc"
        os.environ["MP_SECRET"] = "..."
        result = login_unified()  # detects SA, probes region

        # Re-login: refresh tokens for an existing account
        result = login_unified(name="acme-corp")
        ```
    """
    detected_type = _detect_login_type(account_type, token_env)

    # Re-login path: when name is explicit AND the account already exists,
    # refresh credentials and bail before the new-account machinery runs.
    cm = _config()
    if name is not None:
        try:
            existing = cm.get_account(name)
        except ConfigError:
            existing = None
        if existing is not None:
            return _login_unified_relogin(
                cm,
                existing=existing,
                requested_type=detected_type,
                requested_region=region,
                project=project,
                no_browser=no_browser,
                secret_stdin=secret_stdin,
                token_env=token_env,
            )

    # New-account flow.
    if detected_type == "oauth_browser":
        return _login_unified_new_browser(
            cm,
            name=name,
            region=region,
            project=project,
            no_browser=no_browser,
            project_picker=project_picker,
        )
    return _login_unified_new_credential(
        cm,
        name=name,
        detected_type=detected_type,
        region=region,
        project=project,
        secret_stdin=secret_stdin,
        token_env=token_env,
        project_picker=project_picker,
    )


# Type aliases for the picker callbacks. The CLI supplies TTY-aware
# implementations; library callers can supply their own.
from collections.abc import Callable  # noqa: E402
from typing import TYPE_CHECKING  # noqa: E402

if TYPE_CHECKING:
    from mixpanel_headless._internal.me import MeProjectInfo, MeResponse

    ProjectPicker = Callable[
        ["MeResponse", builtins.list[tuple[str, "MeProjectInfo"]]], str
    ]
    OrgPicker = Callable[["MeResponse"], str]


def _detect_login_type(
    account_type: AccountType | None,
    token_env: str | None,
) -> AccountType:
    """Resolve which auth flow to drive based on inputs and environment.

    Args:
        account_type: Explicit override (priority 1).
        token_env: When set, forces ``oauth_token`` (priority 2).

    Returns:
        The detected auth type, never ``None``.
    """
    import os

    if account_type is not None:
        return account_type
    if token_env is not None:
        return "oauth_token"
    if os.environ.get("MP_USERNAME") and os.environ.get("MP_SECRET"):
        return "service_account"
    if os.environ.get("MP_OAUTH_TOKEN"):
        return "oauth_token"
    return "oauth_browser"


def _login_unified_relogin(
    cm: ConfigManager,
    *,
    existing: Account,
    requested_type: AccountType,
    requested_region: Region | None,
    project: str | None,
    no_browser: bool,
    secret_stdin: bool,
    token_env: str | None,
) -> AccountSummary:
    """Refresh an existing account's credentials per the re-login state machine.

    Implements the re-login row of ``data-model.md`` §4 plus the credential-
    update behavior promised in ``research.md``: oauth_browser re-runs PKCE,
    while service_account / oauth_token rotate the persisted credential
    fields from the same env / stdin sources the new-account flow uses.

    Args:
        cm: The config manager. Used to persist updated credentials via
            :meth:`ConfigManager.update_account` for non-browser types.
        existing: The :class:`Account` already on disk.
        requested_type: The auth-type the caller wants to (re-)authenticate as.
        requested_region: Explicit ``--region`` from the caller (rejected on mismatch).
        project: Explicit ``--project`` from the caller (ignored on re-login).
        no_browser: Forwarded to :func:`login` for oauth_browser refresh.
        secret_stdin: For service_account, read the new secret from stdin
            instead of ``MP_SECRET``.
        token_env: For oauth_token, env-var name carrying the new bearer.
            ``None`` falls back to ``MP_OAUTH_TOKEN`` and persists the
            value inline; explicit ``--token-env NAME`` persists the name.

    Returns:
        :class:`AccountSummary` for the refreshed account.

    Raises:
        ConfigError: Region change (E-3), auth-type change (E-4), or
            missing credentials in env / stdin on the SA / oauth_token
            re-login path.
    """
    import os
    import sys

    existing_account = existing
    name = existing_account.name

    # E-4: refuse auth-type change.
    if requested_type != existing_account.type:
        existing_type = existing_account.type
        flag_map = {
            "service_account": "--service-account",
            "oauth_browser": "(no flag)",
            "oauth_token": "--token-env MP_OAUTH_TOKEN",
        }
        raise ConfigError(
            f"Account '{name}' is type '{existing_type}'; cannot re-login as "
            f"type '{requested_type}'.\n\n"
            f"To change the auth type, remove the existing account first:\n"
            f"    mp account remove {name}\n"
            f"    mp login {flag_map.get(requested_type, '')}".rstrip()
        )

    # E-3: refuse region change.
    if requested_region is not None and requested_region != existing_account.region:
        existing_region = existing_account.region
        raise ConfigError(
            f"Account '{name}' is bound to region '{existing_region}'; "
            f"cannot change to '{requested_region}' on re-login.\n\n"
            f"To switch regions, remove the existing account first:\n"
            f"    mp account remove {name}\n"
            f"    mp login --region {requested_region}"
        )

    # E-5: emit informational note when --project / MP_PROJECT_ID is set.
    if project is not None:
        existing_project = existing_account.default_project
        sys.stderr.write(
            f"note: --project ignored on re-login; use 'mp project use "
            f"{project}' to change the active project (currently "
            f"{existing_project}).\n"
        )

    # Refresh path branches per type. Browser → re-run PKCE. SA / oauth_token
    # → re-collect credential material from env / stdin and persist via
    # update_account so a rotated MP_SECRET / MP_OAUTH_TOKEN actually takes
    # effect for callers that read the resolved value from disk (as opposed
    # to relying on env at request time).
    if requested_type == "oauth_browser":
        login(name, open_browser=not no_browser)
    elif requested_type == "service_account":
        username = os.environ.get("MP_USERNAME")
        if not username:
            raise ConfigError(
                "MP_USERNAME is not set. Re-login for service_account requires "
                "MP_USERNAME in the environment."
            )
        if secret_stdin:
            from mixpanel_headless._internal.io_utils import (
                read_capped_secret_from_stdin,
            )

            secret_raw = read_capped_secret_from_stdin()
        else:
            secret_raw = os.environ.get("MP_SECRET", "")
        if not secret_raw:
            raise ConfigError(
                "MP_SECRET is not set (or stdin is empty). Pipe the secret "
                "via --secret-stdin or set MP_SECRET in the environment."
            )
        cm.update_account(name, username=username, secret=SecretStr(secret_raw))
    elif requested_type == "oauth_token":
        env_name = token_env or "MP_OAUTH_TOKEN"
        bearer = os.environ.get(env_name)
        if not bearer:
            raise ConfigError(
                f"Env var {env_name!r} is unset. Pass --token-env NAME with "
                f"the bearer in NAME, or set {env_name} in the environment."
            )
        if token_env is not None:
            cm.update_account(name, token_env=token_env)
        else:
            cm.update_account(name, token=SecretStr(bearer))

    return show(name)


def _login_unified_new_browser(
    cm: ConfigManager,
    *,
    name: str | None,
    region: Region | None,
    project: str | None,
    no_browser: bool,
    project_picker: ProjectPicker | None,
) -> AccountSummary:
    """Run the oauth_browser new-account flow with placeholder-then-rename.

    Implements the data-model.md §5 atomic-publish pattern: PKCE writes
    tokens to a hidden ``.tmp-{nonce}/`` directory, ``/me`` populates
    the cache there, and only after the final name is resolved does the
    placeholder rename to ``~/.mp/accounts/{final_name}/``. Failure
    before the rename removes the placeholder.

    Args:
        cm: The config manager.
        name: Explicit name (skips derivation when supplied).
        region: Auth region (defaults to ``us``).
        project: Explicit project ID; ``None`` triggers the picker chain.
        no_browser: When ``True``, print the authorize URL.
        project_picker: TTY-gated picker callback.

    Returns:
        :class:`AccountSummary` for the new account.
    """
    import os
    import secrets

    from mixpanel_headless._internal.api_client import MixpanelAPIClient
    from mixpanel_headless._internal.auth.flow import OAuthFlow
    from mixpanel_headless._internal.auth.naming import default_account_name
    from mixpanel_headless._internal.auth.session import Project, Session
    from mixpanel_headless._internal.io_utils import atomic_write_bytes
    from mixpanel_headless._internal.me import MeResponse

    auth_region: Region = region if region is not None else "us"

    # Placeholder dir: hidden so `mp account list` doesn't enumerate it.
    # Routed through accounts_root() so MP_OAUTH_STORAGE_DIR overrides reach
    # the placeholder tree — otherwise tokens land under $HOME but the
    # resolver looks under the override and the new account never works.
    nonce = secrets.token_hex(4)
    accounts_root_dir = accounts_root()
    accounts_root_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    placeholder_dir = accounts_root_dir / f".tmp-{nonce}"
    placeholder_dir.mkdir(mode=0o700)

    try:
        # PKCE flow → in-memory tokens (persist=False keeps OAuthFlow from
        # writing to its own region-scoped store).
        flow = OAuthFlow(region=auth_region)
        tokens = flow.login(persist=False, open_browser=not no_browser)

        # Persist tokens to placeholder (mode 0o600).
        from mixpanel_headless._internal.auth.token import token_payload_bytes

        atomic_write_bytes(placeholder_dir / "tokens.json", token_payload_bytes(tokens))

        # /me probe via temporary OAuthBrowserAccount with placeholder name.
        temp_account = OAuthBrowserAccount(
            name="_tmp_login_unified_",
            region=auth_region,
            default_project=ProjectId("0"),
        )
        # Bypass the on-disk resolver for the probe — we have the
        # freshly minted bearer in memory, and the placeholder dir is
        # not yet wired to OnDiskTokenResolver's lookup path. Inject a
        # one-shot resolver that returns the bearer directly.
        access_token = tokens.access_token.get_secret_value()
        probe_session = Session(
            account=temp_account,
            project=Project(id=ProjectId("0")),
        )

        class _StaticBearer:
            """One-shot token resolver yielding the freshly minted PKCE bearer."""

            def get_browser_token(self, name: str, region: Region) -> str:  # noqa: ARG002
                return access_token

            def get_static_token(self, account: OAuthTokenAccount) -> str:  # noqa: ARG002
                return access_token

        api_client = MixpanelAPIClient(
            session=probe_session, token_resolver=_StaticBearer()
        )
        try:
            me_raw = api_client.me()
            me_resp = MeResponse.model_validate(me_raw)
        finally:
            api_client.close()

        # Resolve the project (priority chain).
        chosen_project = _resolve_project(
            me_resp=me_resp,
            explicit_project=project,
            project_picker=project_picker,
        )

        # Cross-check region against picked project's domain (E-2).
        if chosen_project is not None and chosen_project in me_resp.projects:
            proj_info = me_resp.projects[chosen_project]
            if proj_info.domain:
                project_region = _domain_to_region(proj_info.domain)
                if project_region is not None and project_region != auth_region:
                    raise ConfigError(
                        f"Region mismatch.\n\n"
                        f"You authenticated against the {auth_region} cluster, "
                        f"but project {chosen_project} ({proj_info.name}) lives "
                        f"in the {project_region} cluster ({proj_info.domain}).\n\n"
                        f"Re-run with the correct region:\n"
                        f"    mp login --region {project_region}"
                    )

        # Resolve the account name (--name wins; otherwise derive).
        existing_names = {s.name for s in cm.list_accounts()}
        final_name = (
            name if name is not None else default_account_name(me_resp, existing_names)
        )
        if final_name in existing_names:
            raise ConfigError(
                f"Derived account name {final_name!r} collides with an existing "
                f"account. Pass --name explicitly to disambiguate."
            )

        # Atomic publish: validate the name first so a malicious or
        # path-traversal value (`../foo`, absolute path, etc.) raises BEFORE
        # os.rename publishes tokens outside the accounts tree. account_dir()
        # enforces the same `^[a-zA-Z0-9_-]{1,64}$` regex the Pydantic
        # Account model uses; the surrounding except-clause cleans up the
        # placeholder when this raises.
        try:
            final_dir = account_dir(final_name)
        except ValueError as exc:
            raise ConfigError(
                f"Invalid account name {final_name!r}: must match "
                f"`^[a-zA-Z0-9_-]{{1,64}}$`."
            ) from exc
        if final_dir.exists():
            raise ConfigError(
                f"Final account directory {final_dir} already exists. Run "
                f"`mp account remove {final_name}` first or pass --name."
            )
        os.rename(placeholder_dir, final_dir)
        placeholder_dir = final_dir

        # Persist the account record. If add() raises (a race added the
        # same name between list_accounts() and now, the TOML write
        # failed, etc.), roll back the on-disk publish so the user is
        # not left with tokens at the user-visible name and no
        # [accounts.NAME] block — that combination breaks
        # `mp account remove` and blocks the next `mp login`.
        try:
            return add(
                final_name,
                type="oauth_browser",
                region=auth_region,
                default_project=chosen_project,
            )
        except Exception:
            _safe_rmtree_warn(final_dir)
            raise

    except Exception:
        # Failure before the rename — placeholder still has the
        # ``.tmp-`` prefix. (The post-rename rollback above handles
        # add() failure inline; this branch only fires when something
        # earlier in the try block raised.)
        if placeholder_dir.name.startswith(".tmp-"):
            _safe_rmtree_warn(placeholder_dir)
        raise


def _login_unified_new_credential(
    cm: ConfigManager,
    *,
    name: str | None,
    detected_type: AccountType,
    region: Region | None,
    project: str | None,
    secret_stdin: bool,
    token_env: str | None,
    project_picker: ProjectPicker | None,
) -> AccountSummary:
    """Run the SA / oauth_token new-account flow.

    Args:
        cm: The config manager.
        name: Explicit name (or ``None`` to derive).
        detected_type: ``"service_account"`` or ``"oauth_token"``.
        region: Explicit region (or ``None`` to probe).
        project: Explicit project ID (or ``None`` for picker chain).
        secret_stdin: SA-only: read secret from stdin.
        token_env: oauth_token-only: env-var name (default ``MP_OAUTH_TOKEN``).
        project_picker: TTY-gated picker callback.

    Returns:
        :class:`AccountSummary` for the new account.
    """
    import os
    import sys

    from mixpanel_headless._internal.api_client import MixpanelAPIClient
    from mixpanel_headless._internal.auth.session import Project, Session
    from mixpanel_headless._internal.me import MeResponse

    # Credential collection.
    username: str | None = None
    secret: SecretStr | None = None
    token: SecretStr | None = None
    resolved_token_env: str | None = None
    if detected_type == "service_account":
        username = os.environ.get("MP_USERNAME")
        if not username:
            raise ConfigError(
                "MP_USERNAME is not set. Pass --service-account with "
                "MP_USERNAME=... in the environment, or use "
                "`mp account add NAME --type service_account --username U` "
                "to supply explicit credentials."
            )
        if secret_stdin:
            from mixpanel_headless._internal.io_utils import (
                read_capped_secret_from_stdin,
            )

            secret_raw = read_capped_secret_from_stdin()
        else:
            secret_raw = os.environ.get("MP_SECRET", "")
        if not secret_raw:
            raise ConfigError(
                "MP_SECRET is not set (or stdin is empty). Pipe the secret "
                "via --secret-stdin or set MP_SECRET in the environment."
            )
        secret = SecretStr(secret_raw)
    elif detected_type == "oauth_token":
        env_name = token_env or "MP_OAUTH_TOKEN"
        bearer = os.environ.get(env_name)
        if not bearer:
            raise ConfigError(
                f"Env var {env_name!r} is unset. Pass --token-env NAME with the "
                f"bearer in NAME, or set {env_name} in the environment."
            )
        if token_env is not None:
            resolved_token_env = token_env
        else:
            token = SecretStr(bearer)

    # Region resolution (probe when None).
    resolved_region: Region
    if region is not None:
        resolved_region = region
    else:
        import httpx

        from mixpanel_headless._internal.api_client import ENDPOINTS
        from mixpanel_headless._internal.auth.region_probe import probe_region

        if detected_type == "service_account":
            import base64

            assert username is not None and secret is not None
            raw = f"{username}:{secret.get_secret_value()}".encode()
            headers = {
                "Authorization": f"Basic {base64.b64encode(raw).decode('ascii')}"
            }
        else:  # oauth_token
            bearer_value = (
                token.get_secret_value()
                if token is not None
                else os.environ.get(resolved_token_env or "", "")
            )
            headers = {"Authorization": f"Bearer {bearer_value}"}

        def _factory(probe_region_arg: Region) -> httpx.Client:
            app_url = ENDPOINTS[probe_region_arg]["app"]
            base = app_url[: app_url.index("/api/app")]
            return httpx.Client(base_url=base)

        sys.stderr.write("Probing regions for /me access ...\n")
        result = probe_region(_factory, headers)
        for region_name, status in result.attempts:
            marker = "✓" if status == 200 else "✗"
            sys.stderr.write(f"  {region_name}: {status} {marker}\n")
        resolved_region = result.region

    # /me lookup using temporary credentialed account.
    placeholder_name = "_tmp_login_unified_"
    temp_account: ServiceAccount | OAuthTokenAccount
    if detected_type == "service_account":
        assert username is not None and secret is not None
        temp_account = ServiceAccount(
            name=placeholder_name,
            region=resolved_region,
            username=username,
            secret=secret,
            default_project=ProjectId("0"),
        )
    else:
        if token is not None:
            temp_account = OAuthTokenAccount(
                name=placeholder_name,
                region=resolved_region,
                token=token,
                default_project=ProjectId("0"),
            )
        else:
            assert resolved_token_env is not None
            temp_account = OAuthTokenAccount(
                name=placeholder_name,
                region=resolved_region,
                token_env=resolved_token_env,
                default_project=ProjectId("0"),
            )

    probe_session = Session(account=temp_account, project=Project(id=ProjectId("0")))
    api_client = MixpanelAPIClient(session=probe_session)
    try:
        me_raw = api_client.me()
        me_resp = MeResponse.model_validate(me_raw)
    finally:
        api_client.close()

    chosen_project = _resolve_project(
        me_resp=me_resp,
        explicit_project=project,
        project_picker=project_picker,
    )

    # Resolve final name (--name wins; otherwise derive from /me).
    if name is None:
        from mixpanel_headless._internal.auth.naming import default_account_name

        existing_names = {s.name for s in cm.list_accounts()}
        final_name = default_account_name(me_resp, existing_names)
    else:
        final_name = name

    return add(
        final_name,
        type=detected_type,
        region=resolved_region,
        default_project=chosen_project,
        username=username,
        secret=secret,
        token=token,
        token_env=resolved_token_env,
    )


def _resolve_project(
    *,
    me_resp: MeResponse,
    explicit_project: str | None,
    project_picker: ProjectPicker | None,
) -> str | None:
    """Apply the project-selection priority chain.

    Args:
        me_resp: Parsed :class:`MeResponse`.
        explicit_project: ``--project`` argument (priority 1).
        project_picker: Picker callback for multi-project case.

    Returns:
        The resolved project ID, or ``None`` when the user has zero projects.

    Raises:
        ConfigError: ``--project N`` not in /me (E-6), ``MP_PROJECT_ID``
            stale (warning emitted but does not raise), or non-interactive
            multi-project context with no picker (E-8).
    """
    import os
    import sys

    projects = me_resp.projects
    project_keys = builtins.list(projects.keys())

    # Priority 1: explicit --project.
    if explicit_project is not None:
        if explicit_project in projects:
            return explicit_project
        accessible_lines = "\n".join(
            f"  - {pid} : {info.name} ({info.domain or '(no domain)'})"
            for pid, info in projects.items()
        )
        raise ConfigError(
            f"Project ID {explicit_project} is not visible to this account.\n\n"
            f"Accessible projects:\n{accessible_lines}\n\n"
            f"Pick one and re-run:\n"
            f"    mp login --project {project_keys[0] if project_keys else 'ID'}"
        )

    # Priority 2: MP_PROJECT_ID env (soft default; warn-and-fall-through).
    env_project = os.environ.get("MP_PROJECT_ID")
    if env_project:
        if env_project in projects:
            return env_project
        sys.stderr.write(
            f"note: MP_PROJECT_ID={env_project} is not visible to this account; "
            f"falling through to project picker.\n"
        )

    # Priority 3: single-project auto-pick.
    if len(projects) == 1:
        return project_keys[0]
    if not projects:
        # No projects at all → leave default_project unset; caller can set
        # it later via `mp project use ID` once one becomes accessible.
        return None

    # Priority 4: picker callback (raises E-8 if absent).
    if project_picker is None:
        accessible_lines = "\n".join(
            f"  - {pid} : {info.name} ({info.domain or '(no domain)'})"
            for pid, info in projects.items()
        )
        raise ConfigError(
            f"Multiple projects accessible to this account; no default could "
            f"be picked.\n\n"
            f"Accessible projects:\n{accessible_lines}\n\n"
            f"Pass --project ID to select one explicitly, or set MP_PROJECT_ID."
        )
    sorted_projects = sorted(projects.items(), key=lambda kv: kv[1].name.lower())
    return project_picker(me_resp, sorted_projects)


__all__ = [
    "add",
    "export_bridge",
    "list",
    "login",
    "login_unified",
    "logout",
    "remove",
    "remove_bridge",
    "show",
    "test",
    "token",
    "update",
    "use",
]
