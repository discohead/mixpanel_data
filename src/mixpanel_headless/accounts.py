"""Public ``mp.accounts`` namespace.

Thin wrapper around :class:`~mixpanel_headless._internal.config.ConfigManager`
exposing account CRUD, switching, and probing operations as the canonical
Python API for ``mp account ...`` CLI commands and the plugin's
``auth_manager.py``.

Reference: specs/042-auth-architecture-redesign/contracts/python-api.md §5.
"""

from __future__ import annotations

import builtins
import contextlib
import logging
import os
import shutil
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

from pydantic import SecretStr

from mixpanel_headless._internal.auth.account import (
    Account,
    AccountType,
    OAuthBrowserAccount,
    OAuthTokenAccount,
    ProjectId,
    Region,
    ServiceAccount,
    TokenResolver,
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
from mixpanel_headless.exceptions import (
    AccountExistsError,
    ConfigError,
    InvalidArgumentError,
    LoginFinishPublishError,
    MixpanelHeadlessError,
    NeedsRegionSwitchError,
    OAuthError,
    ProjectNotFoundError,
)
from mixpanel_headless.types import (
    AccountSummary,
    AccountTestResult,
    MeUserInfo,
    OAuthLoginResult,
)

if TYPE_CHECKING:
    from mixpanel_headless._internal.auth.inflight import InflightSession
    from mixpanel_headless._internal.me import MeProjectInfo, MeResponse


PickMethod = Literal[
    "explicit",
    "tty_picker",
    "sole_survivor",
    "sole_survivor_filtered",
    "primary_org_lowest_id",
    "fallback_with_unintegrated",
    "fallback_with_demos",
    "cross_region_only",
    "no_projects",
]
"""Discriminator for how :func:`_resolve_project` arrived at its pick.

The CLI uses this to render the right confirmation language ("auto-picked
from your most-active org" vs "your only active project" vs
"unintegrated — verify first") so the user can tell whether the choice
needs a sanity check. Programmatic consumers (the slash command, future
``auth_manager.py login_finish`` wrapper) branch on it without parsing
the human message.

``sole_survivor`` means the user really has only one region-compatible
project (the funnel's ``region_compatible_count`` is 1).
``sole_survivor_filtered`` means there are multiple region-compatible
projects but only one survived the demo / unintegrated filters — the
distinction matters for the user-facing message ("your only active
project" vs "the only non-demo, integrated project")."""


@dataclass(frozen=True)
class ProjectPickResult:
    """Structured result of :func:`_resolve_project`.

    Replaces the bare ``str | None`` return so the CLI can announce the
    auto-pick method, the funnel counts, and the primary-org context in
    the response envelope. Frozen so callers can pass it through layers
    without worrying about accidental mutation.

    Attributes:
        project_id: The chosen project ID, or ``None`` when ``method ==
            "no_projects"`` (account has zero accessible projects) or
            ``"cross_region_only"`` (raised before the result is returned,
            but populated on the carried instance for the envelope).
        method: How the choice was made — see :data:`PickMethod`.
        auth_region: Region the credential authenticated against. Mirrored
            here so :class:`NeedsRegionSwitchError` and the envelope can
            surface it without an extra parameter on every call site.
        primary_org_id: ID of the org from which ``project_id`` was
            picked (only populated when ``method`` is one of the
            ``primary_org_*`` / ``fallback_*`` / ``sole_survivor`` paths).
        primary_org_name: Human-readable name of the primary org.
        primary_org_survivor_count: How many projects in the primary org
            survived the filter chain. Lets the CLI render "picked from
            your most-active org (28 projects)" instead of just naming
            the org.
        accessible_project_count: Total ``len(me_resp.projects)`` before
            any filter — anchors the funnel display.
        region_compatible_count: Count after the region filter only.
        filtered_count: Count after region + ``is_demo=False`` +
            ``has_integrated=True``.
        demo_excluded: How many region-compatible projects were dropped
            for ``is_demo=True``.
        unintegrated_excluded: How many were dropped for
            ``has_integrated`` not being ``True``.
        cross_region_projects: Populated only when ``method ==
            "cross_region_only"``. List of ``(project_id, project_name,
            domain)`` tuples so the envelope can suggest "run with
            ``--region eu``".
    """

    project_id: str | None
    method: PickMethod
    auth_region: str
    primary_org_id: str | None = None
    primary_org_name: str | None = None
    primary_org_survivor_count: int | None = None
    accessible_project_count: int = 0
    region_compatible_count: int = 0
    filtered_count: int = 0
    demo_excluded: int = 0
    unintegrated_excluded: int = 0
    cross_region_projects: builtins.list[tuple[str, str, str]] | None = None


@dataclass(frozen=True)
class LoginFinishResult:
    """Public return type of :func:`login_unified_finish` / :func:`login_unified_resume`.

    Bundles the published :class:`AccountSummary` with the
    :class:`ProjectPickResult` so the CLI's ``--finish`` / ``--resume``
    handlers can render the §9 envelope including ``project_pick``
    metadata without re-running ``/me`` or re-deriving the algorithm.

    Also returned by the internal
    :func:`_publish_account_from_tokens` helper that powers both flows.

    Attributes:
        summary: The published account, with ``user_email`` /
            ``project_id`` / ``project_name`` populated from ``/me``.
        pick: The pick result (auto-pick metadata + funnel counts).
    """

    summary: AccountSummary
    pick: ProjectPickResult


@dataclass(frozen=True)
class LoginStartResult:
    """Return value of :func:`login_unified_start`.

    Bundles the persisted :class:`InflightSession` (also written to disk
    at ``~/.mp/oauth/inflight.json``) with the freshly-built
    ``authorize_url`` so the CLI can print the URL to the user without
    re-deriving it. The URL is intentionally NOT persisted in the
    inflight file — it's purely a function of the other fields, and the
    on-disk shape stays minimal.

    Attributes:
        inflight: The persisted session state.
        authorize_url: Full ``mixpanel.com/oauth/authorize/?...`` URL the
            user opens in their host browser.
    """

    inflight: InflightSession
    authorize_url: str


# Picker callback contract. The CLI supplies a TTY-aware implementation;
# library callers can supply their own or pass ``None`` to fail-fast in
# non-interactive contexts (E-8).
ProjectPicker = Callable[
    ["MeResponse", builtins.list[tuple[str, "MeProjectInfo"]]], str
]

# Progress factory contract. ``mp login`` wraps the (slow) ``/me`` round-trip
# in this CM so the CLI can render a Rich spinner. Library callers leave it
# ``None`` and the orchestrator substitutes ``contextlib.nullcontext``.
ProgressFactory = Callable[[str], "contextlib.AbstractContextManager[None]"]

_FETCH_ME_PROGRESS_MESSAGE = "Fetching your projects from Mixpanel..."
"""Shown by the CLI's spinner while the orchestrator awaits ``/me``.

Kept module-level so a future copy tweak is one edit, not three (the
relogin + new-browser + new-credential paths all share this string).
Intentionally free of duration estimates — ``/me`` latency depends on
how many projects + orgs the user can see, and we would rather under-
promise than print a misleading "this may take 30s" line.
"""

logger = logging.getLogger(__name__)


def _config() -> ConfigManager:
    """Return a fresh ConfigManager honoring ``MP_CONFIG_PATH`` / ``$HOME``."""
    return ConfigManager()


class _FreshBrowserBearer:
    """One-shot :class:`TokenResolver` returning a freshly minted PKCE bearer.

    Used by both the legacy :func:`login` and the new
    :func:`_login_unified_new_browser` flows to run the post-PKCE
    ``/me`` probe BEFORE the access token is persisted to disk. Going
    through :class:`OnDiskTokenResolver` would require persisting
    first, which is exactly what we want to avoid (the probe might
    surface a region mismatch — wrong-region tokens should never land
    at the user-visible account path).

    Annotated as :class:`TokenResolver` so mypy verifies protocol
    conformance at the definition site rather than relying on
    structural typing at the call site.
    """

    def __init__(self, access_token: str) -> None:
        """Capture the in-memory bearer for the resolver methods.

        Args:
            access_token: The plaintext PKCE bearer just returned from
                :meth:`OAuthFlow.login`.
        """
        self._access_token = access_token

    def get_browser_token(self, name: str, region: Region) -> str:  # noqa: ARG002
        """Return the captured bearer; ``name`` and ``region`` are unused."""
        return self._access_token

    def get_static_token(self, account: OAuthTokenAccount) -> str:  # noqa: ARG002
        """Return the captured bearer; ``account`` is unused."""
        return self._access_token


# Runtime check that _FreshBrowserBearer satisfies the protocol — fails
# at import if a future TokenResolver method is added without updating
# this class. Cheaper than waiting for the call site mypy error.
_: TokenResolver = _FreshBrowserBearer("_")
del _


def _narrate(msg: str) -> None:
    """Write ``msg`` to stderr with a trailing newline.

    Single chokepoint for the ``mp login`` orchestrator's progress
    narration (region-probe attempts, re-login informational notes).
    Concentrating the writes here means a future ``narrate=False``
    kwarg or a Rich console swap stays a one-line change. Library
    callers who don't want stderr noise can redirect ``2>/dev/null``;
    this is documented on :func:`login_unified`.

    Args:
        msg: Single-line message. The trailing newline is appended.
    """
    import sys

    sys.stderr.write(f"{msg}\n")


def _fetch_me(
    account: Account,
    *,
    token_resolver: TokenResolver | None = None,
    placeholder_project: str = "0",
) -> MeResponse:
    """Run a one-shot ``/me`` probe against ``account`` and return the parsed response.

    Five different orchestrator paths (derive-name, ``test``, legacy
    ``login``, the two ``_login_unified_new_*`` flows) used to inline
    the same ``Session/MixpanelAPIClient/try-me-finally-close`` block.
    Concentrating it here keeps the lifecycle (always close the
    client) and the placeholder-project handling consistent.

    Args:
        account: The account to authenticate as. ``account.default_project``
            is used as the session project if set; otherwise
            ``placeholder_project`` (default ``"0"``).
        token_resolver: Override the resolver used by
            :class:`MixpanelAPIClient`. Pass :class:`_FreshBrowserBearer`
            for the post-PKCE pre-persist case so the bearer comes from
            memory, not from disk.
        placeholder_project: Fallback project ID when
            ``account.default_project`` is unset (e.g. brand-new
            ``oauth_browser`` accounts before their first /me).

    Returns:
        The parsed :class:`MeResponse`.

    Raises:
        AuthenticationError / OAuthError / QueryError: Propagated from
            the underlying ``api_client.me()`` call.
        pydantic.ValidationError: Propagated from
            ``MeResponse.model_validate``.
    """
    from mixpanel_headless._internal.api_client import MixpanelAPIClient
    from mixpanel_headless._internal.auth.session import Project, Session
    from mixpanel_headless._internal.me import MeResponse as _MeResponse

    project_id = account.default_project or placeholder_project
    probe_session = Session(account=account, project=Project(id=project_id))
    kwargs: dict[str, Any] = {}
    if token_resolver is not None:
        kwargs["token_resolver"] = token_resolver
    api_client = MixpanelAPIClient(session=probe_session, **kwargs)
    try:
        return _MeResponse.model_validate(api_client.me())
    finally:
        api_client.close()


def _assert_project_region_matches(
    me_resp: MeResponse,
    chosen_project: str | None,
    auth_region: Region,
) -> None:
    """Raise ``ConfigError`` E-2 when a project lives in a different cluster.

    The OAuth bearer is region-bound, so a successful ``/me`` plus a
    project from a different cluster would surface as a confusing 401
    on every subsequent request. Catching it here lets the caller
    print a structured error with the specific re-run command. No-op
    when ``chosen_project`` is unset, missing from ``/me``, or carries
    no ``domain`` field (older payloads).

    Args:
        me_resp: Parsed :class:`MeResponse`.
        chosen_project: The project ID the orchestrator selected.
        auth_region: The region the credential authenticated against.

    Raises:
        ConfigError: Mismatch between ``auth_region`` and the project's
            cluster (E-2 catalog wording).
    """
    if chosen_project is None or chosen_project not in me_resp.projects:
        return
    proj_info = me_resp.projects[chosen_project]
    if not proj_info.domain:
        return
    project_region = _domain_to_region(proj_info.domain)
    if project_region is None or project_region == auth_region:
        return
    raise ConfigError(
        f"Region mismatch.\n\n"
        f"You authenticated against the {auth_region} cluster, but project "
        f"{chosen_project} ({proj_info.name}) lives in the "
        f"{project_region} cluster ({proj_info.domain}).\n\n"
        f"Re-run with the correct region:\n"
        f"    mp login --region {project_region}"
    )


def _build_test_failure_result(
    account_name: str, prefix: str, exc: BaseException
) -> AccountTestResult:
    """Build an ``AccountTestResult`` for a failed ``/me`` probe.

    Preserves the structured ``code`` / ``details`` payload when ``exc``
    is a :class:`MixpanelHeadlessError` so downstream consumers can
    branch on the code rather than parse the human-readable message.
    For non-library exceptions (network ``OSError``, programming
    bugs caught by the broad ``except Exception``) ``error_code`` /
    ``error_details`` stay ``None`` — only the ``error`` string carries
    diagnostic information.

    Args:
        account_name: The account that was tested.
        prefix: Short context prefix prepended to ``str(exc)`` in the
            human-readable ``error`` field (e.g. ``"/me probe failed"``).
        exc: The exception that was caught.

    Returns:
        A populated :class:`AccountTestResult` with ``ok=False``.
    """
    error_code: str | None = None
    error_details: dict[str, Any] | None = None
    if isinstance(exc, MixpanelHeadlessError):
        error_code = exc.code
        error_details = dict(exc.details) if exc.details else None
    return AccountTestResult(
        account_name=account_name,
        ok=False,
        error=f"{prefix}: {exc}",
        error_code=error_code,
        error_details=error_details,
    )


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


_DOMAIN_TO_REGION: dict[str, Region] = {
    "mixpanel.com": "us",
    "eu.mixpanel.com": "eu",
    "in.mixpanel.com": "in",
}
"""Lookup table for :func:`_domain_to_region` — module-level so we don't
rebuild it on every call. Lives here (rather than in ``ENDPOINTS``) so
the cross-check stays decoupled from the API host configuration."""


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
    return _DOMAIN_TO_REGION.get(host)


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

    ## Derived naming (specs/043-frictionless-auth)

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
    # login time, and the post-callback ``/me`` cross-check will
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
        ConfigError: Credential collection failed (missing ``username``
            / ``secret`` for ``service_account``, missing ``token`` /
            ``token_env`` for ``oauth_token``).
        AuthenticationError / OAuthError / QueryError: Propagated from
            the underlying ``/me`` call when the supplied credential is
            rejected or the API errors out. (Empty ``/me.organizations``
            is NOT an error here — :func:`naming.default_account_name`
            falls back to the literal ``"account"``.)
        pydantic.ValidationError: Propagated when ``/me`` returns a
            payload that doesn't match :class:`MeResponse`.
    """
    from mixpanel_headless._internal.auth.account import (
        OAuthTokenAccount,
        ProjectId,
        ServiceAccount,
    )
    from mixpanel_headless._internal.auth.naming import default_account_name

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

    me_resp = _fetch_me(temp_account)
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
            # Preserve the structured error context when the underlying
            # failure was a library exception. Plain ``str(exc)`` loses
            # the machine-readable code that downstream tooling
            # (auth_manager.py, JSON consumers) uses to color accounts
            # as needs_login / needs_token / etc.
            return _build_test_failure_result(summary.name, "/me probe failed", exc)
        try:
            me_resp = MeResponse.model_validate(me_raw)
        except Exception as exc:  # noqa: BLE001 — malformed payload
            return _build_test_failure_result(
                summary.name, "/me response could not be parsed", exc
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

    # Lazy import — OAuthFlow pulls in browser / threading machinery.
    from mixpanel_headless._internal.auth.flow import OAuthFlow

    flow = OAuthFlow(region=account.region)
    # ``persist=False`` skips the v2 ``~/.mp/oauth/tokens_{region}.json``
    # write — v3 owns ``~/.mp/accounts/{name}/tokens.json`` exclusively.
    tokens = flow.login(persist=False, open_browser=open_browser)

    # /me probe: validates the freshly minted bearer + backfills the
    # account's default_project on first login. The probe runs against
    # the in-memory token via _FreshBrowserBearer so a cross-check
    # failure (e.g. user authed to us but the picked project lives in
    # eu) does not leave wrong-region tokens at the user-visible
    # ``~/.mp/accounts/{name}/tokens.json``. Tokens persist only after
    # validation succeeds — same atomic-publish discipline as
    # ``_login_unified_new_browser``.
    user: MeUserInfo | None = None
    chosen_project = account.default_project
    bearer = _FreshBrowserBearer(tokens.access_token.get_secret_value())
    try:
        me_resp = _fetch_me(account, token_resolver=bearer)
    except Exception as exc:  # noqa: BLE001 — re-raise as OAuthError below
        raise OAuthError(
            f"Login succeeded but `/me` probe failed: {exc}",
            code="OAUTH_TOKEN_ERROR",
            details={"account_name": name, "region": account.region},
        ) from exc
    if me_resp.user_id is not None and me_resp.user_email is not None:
        user = MeUserInfo(id=me_resp.user_id, email=me_resp.user_email)
    if chosen_project is None and me_resp.projects:
        chosen_project = ProjectId(next(iter(sorted(me_resp.projects))))
    # E-2 cross-check: the picked project must live in the same
    # cluster the bearer was minted against, otherwise every
    # subsequent request 401s with no obvious connection back to
    # the region choice.
    _assert_project_region_matches(me_resp, chosen_project, account.region)

    # Validation passed — safe to persist. Backfill default_project too
    # if the cross-check picked one. Both writes go to disk only now.
    tokens_path = _persist_browser_tokens(name, tokens)
    if chosen_project is not None and chosen_project != account.default_project:
        cm.update_account(name, default_project=chosen_project)

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
        Honors ``MP_OAUTH_STORAGE_DIR`` so a hermetic test environment
        or Cowork-style sandbox sees the override-path; the prior
        hard-coded ``~/.mp/oauth/`` lied to callers under override.
    """
    from mixpanel_headless._internal.auth.storage import OAuthStorage

    return OAuthStorage._default_storage_dir() / f"client_{region}.json"  # noqa: SLF001


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
    service_account: bool = False,
    project_picker: ProjectPicker | None = None,
    progress: ProgressFactory | None = None,
) -> AccountSummary:
    """Add and activate a Mixpanel account in one orchestrated call.

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

    ## Output

    Progress narration (region-probe attempts, the E-5 re-login note)
    is written to ``stderr`` via :func:`_narrate`. Library callers who
    want it suppressed can redirect the parent process's ``stderr``;
    the function does not currently expose a programmatic
    ``narrate=False`` toggle.

    Args:
        name: Explicit local account name. Wins over derived names.
        region: Explicit region. ``None`` triggers the probe (SA / token)
            or defaults to ``us`` (oauth_browser).
        project: Explicit project ID. Must exist in ``/me``.
        account_type: Explicit auth-type override.
        no_browser: For oauth_browser, print the authorize URL instead
            of launching the browser. Combined with a non-browser
            ``account_type`` raises :class:`InvalidArgumentError`
            (``violation="no_browser_misuse"``).
        secret_stdin: For service_account, read the secret from stdin.
            Combined with a non-SA ``account_type`` raises
            :class:`InvalidArgumentError`
            (``violation="secret_stdin_misuse"``).
        token_env: For oauth_token, env-var name carrying the bearer.
            Defaults to ``MP_OAUTH_TOKEN`` when not set.
        service_account: When ``True``, forces ``account_type =
            "service_account"`` (mirrors the CLI ``--service-account``
            flag). Combined with ``token_env`` raises
            :class:`InvalidArgumentError`
            (``violation="mutually_exclusive"``). Library callers can
            instead pass ``account_type="service_account"`` directly;
            this flag exists so the CLI can forward its raw arguments
            without per-flag remapping.
        project_picker: Callable invoked with ``(MeResponse, sorted_projects)``
            when ``len(me.projects) > 1`` and no other project source
            resolves. Returns the chosen project ID. The CLI supplies a
            TTY-aware picker; library callers can supply their own or
            leave it ``None`` to fail-fast non-interactively.
        progress: Optional CM factory wrapped around the ``/me`` round-
            trip. The CLI passes a Rich-spinner-backed factory so the
            terminal does not appear hung while ``/me`` runs. Library
            callers leave ``None`` and the orchestrator substitutes
            :class:`contextlib.nullcontext`.

    Returns:
        :class:`AccountSummary` for the newly added (or refreshed)
        account, with ``user_email`` / ``project_id`` / ``project_name``
        populated from the ``/me`` lookup.

    Raises:
        InvalidArgumentError: Mutually-incompatible flag combinations
            (``service_account`` + ``token_env``; ``no_browser`` against
            non-browser; ``secret_stdin`` against non-SA). Carries a
            ``violation`` discriminator and ``detected_auth_type`` in
            ``details``. Maps to CLI exit 3.
        ConfigError: Project not visible (E-6), region mismatch (E-2 / E-3),
            type mismatch (E-4), missing required env (cred collection),
            or non-interactive context with no project / org default
            (E-8 / E-9).
        AccountExistsError: Derived account name collides with an
            existing account (browser flow); pass ``name=`` to
            disambiguate.
        ProjectNotFoundError: Explicit ``project=`` not visible to
            ``/me``.
        OAuthError: PKCE failure or all-region probe failure
            (raised as :class:`RegionProbeError` subclass).
        RegionProbeNetworkError: All probe attempts failed at the
            network layer (subclass of :class:`RegionProbeError`).

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
    # Fold the CLI's --service-account flag into the explicit
    # ``account_type`` parameter so flag-combination validation has a
    # single source of truth. Library callers that pass
    # ``account_type="service_account"`` directly can leave
    # ``service_account=False``; both spellings produce identical
    # downstream behavior.
    if service_account:
        if account_type is not None and account_type != "service_account":
            # Two explicit but conflicting account-type signals — treat
            # as mutually-exclusive misuse.
            raise InvalidArgumentError(
                f"--service-account conflicts with explicit account_type="
                f"{account_type!r}.",
                violation="mutually_exclusive",
                detected_auth_type=account_type,
            )
        if token_env is not None:
            raise InvalidArgumentError(
                "--service-account and --token-env are mutually exclusive.\n\n"
                "Pick one auth type:\n"
                "    mp login --service-account\n"
                "    mp login --token-env MY_OAUTH_TOKEN_VAR",
                violation="mutually_exclusive",
                detected_auth_type="service_account",
            )
        account_type = "service_account"

    detected_type = _detect_login_type(account_type, token_env)

    # Per-flag misuse: --no-browser is meaningful only for oauth_browser;
    # --secret-stdin is meaningful only for service_account. Surface these
    # before any I/O so callers fail fast.
    if no_browser and detected_type != "oauth_browser":
        raise InvalidArgumentError(
            f"--no-browser is only meaningful for the oauth_browser auth "
            f"type.\n\nDetected auth type: {detected_type}.",
            violation="no_browser_misuse",
            detected_auth_type=detected_type,
        )
    if secret_stdin and detected_type != "service_account":
        raise InvalidArgumentError(
            f"--secret-stdin is only meaningful for the service_account "
            f"auth type.\n\nDetected auth type: {detected_type}.",
            violation="secret_stdin_misuse",
            detected_auth_type=detected_type,
        )

    # Default progress to nullcontext so library callers (Cowork, scripts,
    # tests) do not have to thread a CM through every invocation. The CLI
    # passes a Rich-spinner factory; everyone else gets the no-op.
    if progress is None:
        progress = lambda _msg: contextlib.nullcontext()  # noqa: E731

    # Re-login path: when name is explicit AND the account already exists,
    # refresh credentials and bail before the new-account machinery runs.
    cm = _config()
    if name is not None:
        try:
            existing = cm.get_account(name)
        except ConfigError:
            existing = None
        if existing is not None:
            summary = _login_unified_relogin(
                cm,
                existing=existing,
                requested_type=detected_type,
                requested_region=region,
                project=project,
                no_browser=no_browser,
                secret_stdin=secret_stdin,
                token_env=token_env,
                progress=progress,
            )
        else:
            summary = _login_unified_new(
                cm,
                detected_type=detected_type,
                name=name,
                region=region,
                project=project,
                no_browser=no_browser,
                secret_stdin=secret_stdin,
                token_env=token_env,
                project_picker=project_picker,
                progress=progress,
            )
    else:
        summary = _login_unified_new(
            cm,
            detected_type=detected_type,
            name=None,
            region=region,
            project=project,
            no_browser=no_browser,
            secret_stdin=secret_stdin,
            token_env=token_env,
            project_picker=project_picker,
            progress=progress,
        )

    # Activate the (new or refreshed) account so library callers — not
    # just the CLI — see the documented "Add and activate" semantics.
    # ``add()`` only auto-activates the FIRST account; subsequent adds
    # and the relogin path leave ``[active].account`` untouched without
    # this explicit promotion. A single ``_mutate()`` transaction keeps
    # the next process from observing a half-swapped state.
    use(summary.name)
    return summary


def _login_unified_new(
    cm: ConfigManager,
    *,
    detected_type: AccountType,
    name: str | None,
    region: Region | None,
    project: str | None,
    no_browser: bool,
    secret_stdin: bool,
    token_env: str | None,
    project_picker: ProjectPicker | None,
    progress: ProgressFactory,
) -> AccountSummary:
    """Dispatch to the new-account browser or credential flow.

    Thin router so :func:`login_unified` itself stays focused on the
    re-login pre-check + post-activation. Both downstream helpers
    populate the ``user_email`` / ``project_id`` / ``project_name``
    fields on the returned :class:`AccountSummary` from ``/me``.

    Args:
        cm: Shared config manager.
        detected_type: Resolved auth type (``oauth_browser`` /
            ``service_account`` / ``oauth_token``).
        name: Explicit ``--name`` override (``None`` to derive).
        region: Explicit ``--region`` (``None`` for browser default
            ``us`` / SA + token probe).
        project: Explicit ``--project`` (``None`` for picker chain).
        no_browser: Forwarded to oauth_browser flow only.
        secret_stdin: Forwarded to SA flow only.
        token_env: Forwarded to oauth_token flow only.
        project_picker: TTY-gated picker callback.
        progress: CM factory wrapped around the ``/me`` round-trip in
            both downstream flows. Forwarded as-is.

    Returns:
        :class:`AccountSummary` populated with ``user_email`` /
        ``project_id`` / ``project_name`` from the orchestrator's ``/me``
        round-trip.
    """
    if detected_type == "oauth_browser":
        return _login_unified_new_browser(
            cm,
            name=name,
            region=region,
            project=project,
            no_browser=no_browser,
            project_picker=project_picker,
            progress=progress,
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
        progress=progress,
    )


def _persist_me_cache(account_name: str, me_resp: MeResponse) -> None:
    """Write ``me.json`` for the named account, honoring the storage root.

    Wraps :class:`MeCache` so the orchestrator does not have to reason
    about ``MP_OAUTH_STORAGE_DIR`` overrides — passes ``storage_dir=
    account_dir(name)`` so the cache lands alongside ``tokens.json`` /
    ``client.json`` in the same per-account directory.

    Args:
        account_name: The account whose cache to populate.
        me_resp: Parsed ``/me`` response (the same payload used to
            resolve the project / derive the name).
    """
    from mixpanel_headless._internal.me import MeCache

    cache = MeCache(account_name=account_name, storage_dir=account_dir(account_name))
    cache.put(me_resp)


def _summary_with_me(
    summary: AccountSummary,
    *,
    me_resp: MeResponse,
    project_id: str | None,
) -> AccountSummary:
    """Return a copy of ``summary`` with ``/me``-derived fields filled in.

    The 043 contract requires the orchestrator's returned summary to
    carry ``user_email``, ``project_id``, and ``project_name`` so the
    CLI can render the structured success line without a second
    ``ConfigManager`` round-trip. Existing :func:`show` doesn't see the
    ``/me`` payload, so we bolt the fields on here.

    Args:
        summary: The base summary returned by :func:`add` / :func:`show`.
        me_resp: Parsed ``/me`` response.
        project_id: Resolved project ID (or ``None`` when no project is set).

    Returns:
        A new :class:`AccountSummary` with the three optional fields
        populated when the data is available.
    """
    project_name: str | None = None
    if project_id is not None and project_id in me_resp.projects:
        project_name = me_resp.projects[project_id].name
    return summary.model_copy(
        update={
            "user_email": me_resp.user_email,
            "project_id": project_id,
            "project_name": project_name,
        }
    )


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
    progress: ProgressFactory,
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
        progress: CM factory wrapped around the post-refresh ``/me``
            round-trip so the CLI can render a spinner during the
            slowest step of re-login.

    Returns:
        :class:`AccountSummary` for the refreshed account.

    Raises:
        ConfigError: Region change (E-3), auth-type change (E-4), or
            missing credentials in env / stdin on the SA / oauth_token
            re-login path.
    """
    existing_account = existing
    name = existing_account.name

    # Refuse auth-type change on re-login (cross-account swaps).
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

    # Refuse region change on re-login.
    if requested_region is not None and requested_region != existing_account.region:
        existing_region = existing_account.region
        raise ConfigError(
            f"Account '{name}' is bound to region '{existing_region}'; "
            f"cannot change to '{requested_region}' on re-login.\n\n"
            f"To switch regions, remove the existing account first:\n"
            f"    mp account remove {name}\n"
            f"    mp login --region {requested_region}"
        )

    # Informational note when --project is passed but ignored.
    if project is not None:
        existing_project = existing_account.default_project
        _narrate(
            f"note: --project ignored on re-login; use 'mp project use "
            f"{project}' to change the active project (currently "
            f"{existing_project})."
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
        # When the caller did not pass --token-env, prefer the
        # already-persisted env-var pointer so a re-login that just wants
        # to refresh the bearer does not silently switch the storage
        # mode from "env reference" to "inline string". The previous
        # behavior overwrote ``token_env=MP_OAUTH_TOKEN`` with an inline
        # ``SecretStr(bearer)`` on every re-login, which broke the next
        # rotation of MP_OAUTH_TOKEN with no warning. Pass --token-env
        # NAME explicitly to switch modes (or to point at a different
        # env var).
        existing_token_env = getattr(existing_account, "token_env", None)
        if token_env is not None:
            env_name = token_env
        elif existing_token_env is not None:
            env_name = existing_token_env
        else:
            env_name = "MP_OAUTH_TOKEN"
        bearer = os.environ.get(env_name)
        if not bearer:
            raise ConfigError(
                f"Env var {env_name!r} is unset. Pass --token-env NAME with "
                f"the bearer in NAME, or set {env_name} in the environment."
            )
        if token_env is not None:
            # Caller explicitly named the env var → persist the pointer.
            cm.update_account(name, token_env=token_env)
        elif existing_token_env is not None:
            # Existing storage was env-ref; preserve the mode by re-
            # writing the same pointer (the value is read live from env
            # at request time, no config rewrite would actually change
            # behavior — but writing the same value keeps the relogin
            # path idempotent for tests asserting on update_account).
            cm.update_account(name, token_env=existing_token_env)
        else:
            # Existing storage was inline; honor that and persist the
            # rotated bearer inline too.
            cm.update_account(name, token=SecretStr(bearer))

    # Fetch /me so the success line and cache reflect the refreshed
    # session. Per python-api.md §1, login_unified() promises to write
    # the /me cache as a side effect; the relogin path was previously
    # the one branch that skipped it.
    refreshed = cm.get_account(name)
    with progress(_FETCH_ME_PROGRESS_MESSAGE):
        me_resp = _fetch_me(refreshed)
    _persist_me_cache(name, me_resp)
    project_id = refreshed.default_project
    return _summary_with_me(show(name), me_resp=me_resp, project_id=project_id)


def _login_unified_new_browser(
    cm: ConfigManager,
    *,
    name: str | None,
    region: Region | None,
    project: str | None,
    no_browser: bool,
    project_picker: ProjectPicker | None,
    progress: ProgressFactory,
) -> AccountSummary:
    """Run the oauth_browser new-account flow with placeholder-then-rename.

    Implements the data-model.md §5 atomic-publish pattern: PKCE writes
    tokens to a hidden ``.tmp-{nonce}/`` directory, ``/me`` is probed
    in memory via :class:`_FreshBrowserBearer` to resolve the project
    and account name, and only after the cross-check passes does the
    placeholder rename to ``~/.mp/accounts/{final_name}/``. Failure
    before the rename removes the placeholder; failure inside ``add()``
    after the rename rolls ``final_dir`` back via ``_safe_rmtree_warn``.

    Once the rename succeeds, the ``/me`` response is persisted to
    ``me.json`` under the account dir (per python-api.md §1) so the
    next :class:`MeService` call hits the warm cache. Cache write
    failures fall through to the ``add()`` rollback above.

    Args:
        cm: The config manager.
        name: Explicit name (skips derivation when supplied).
        region: Auth region (defaults to ``us``).
        project: Explicit project ID; ``None`` triggers the picker chain.
        no_browser: When ``True``, print the authorize URL.
        project_picker: TTY-gated picker callback.
        progress: CM factory wrapped around the in-memory ``/me`` probe
            so the CLI's spinner stays active during the slow step.

    Returns:
        :class:`AccountSummary` for the new account, with ``user_email``
        / ``project_id`` / ``project_name`` populated from ``/me``.
    """
    import secrets

    from mixpanel_headless._internal.auth.flow import OAuthFlow
    from mixpanel_headless._internal.io_utils import atomic_write_bytes

    auth_region: Region = region if region is not None else "us"

    # Placeholder dir: hidden so `mp account list` doesn't enumerate it.
    # Routed through accounts_root() so MP_OAUTH_STORAGE_DIR overrides reach
    # the placeholder tree — otherwise tokens land under $HOME but the
    # resolver looks under the override and the new account never works.
    # Wrap in os.umask(0o077) so any intermediate parent (typically
    # ``~/.mp/`` on a fresh machine) is created with restrictive
    # permissions too — ``mkdir(mode=0o700)`` only applies the mode
    # to the leaf, leaving intermediate parents at the process umask.
    nonce = secrets.token_hex(4)
    accounts_root_dir = accounts_root()
    old_umask = os.umask(0o077)
    try:
        accounts_root_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        placeholder_dir = accounts_root_dir / f".tmp-{nonce}"
        placeholder_dir.mkdir(mode=0o700)
    finally:
        os.umask(old_umask)

    try:
        # PKCE flow → in-memory tokens (persist=False keeps OAuthFlow from
        # writing to its own region-scoped store).
        flow = OAuthFlow(region=auth_region)
        tokens = flow.login(persist=False, open_browser=not no_browser)

        # Persist tokens to placeholder (mode 0o600).
        from mixpanel_headless._internal.auth.token import token_payload_bytes

        atomic_write_bytes(placeholder_dir / "tokens.json", token_payload_bytes(tokens))
        # Save region into placeholder meta so a future ``mp login --resume``
        # can recover it without falling back to "read whichever
        # client_X.json exists" — the prior prototype's hack failed for
        # users with multiple regions registered.
        from mixpanel_headless._internal.auth.inflight import save_placeholder_meta

        save_placeholder_meta(placeholder_dir, region=auth_region)

        # Hand off to the shared post-token tail. auto_pick=False
        # preserves the existing same-machine behavior (TTY picker fires
        # for multi-project; ConfigError E-8 for non-TTY without picker).
        # The new --finish/--resume paths pass auto_pick=True for the
        # headless case.
        result = _publish_account_from_tokens(
            cm,
            tokens=tokens,
            region=auth_region,
            placeholder_dir=placeholder_dir,
            name=name,
            project=project,
            project_picker=project_picker,
            auto_pick=False,
            cached_me=None,
            progress=progress,
        )
        return result.summary

    except Exception:
        # Failure before the rename — placeholder still has the
        # ``.tmp-`` prefix. The new contract: keep the placeholder when
        # ``tokens.json`` exists in it, so ``mp login --resume PLACEHOLDER``
        # can finish the publish without re-running PKCE. Cleanup only
        # fires for failures that landed before the token write.
        tokens_path = placeholder_dir / "tokens.json"
        if (
            placeholder_dir.exists()
            and placeholder_dir.name.startswith(".tmp-")
            and not tokens_path.exists()
        ):
            _safe_rmtree_warn(placeholder_dir)
        raise


def _publish_account_from_tokens(
    cm: ConfigManager,
    *,
    tokens: OAuthTokens,
    region: Region,
    placeholder_dir: Path,
    name: str | None,
    project: str | None,
    project_picker: ProjectPicker | None,
    auto_pick: bool,
    cached_me: MeResponse | None,
    progress: ProgressFactory,
) -> LoginFinishResult:
    """Shared post-token tail of the oauth_browser login flows.

    Precondition: ``placeholder_dir`` exists, contains ``tokens.json`` matching
    ``tokens``, and is named ``.tmp-{nonce}``.

    Runs ``/me`` (or reuses ``cached_me`` when fresh), resolves the project via
    :func:`_resolve_project`, asserts the project's region matches ``region``,
    derives the account name (``--name`` wins; otherwise via
    :func:`default_account_name`), atomic-renames the placeholder to its final
    dir, registers the account in the TOML, and persists the ``/me`` cache.

    Three callers use this:

    1. :func:`_login_unified_new_browser` — same-machine ``mp login`` (passes
       ``project_picker=tty_picker``, ``auto_pick=False``, ``cached_me=None``).
    2. :func:`login_unified_finish` — ``mp login --finish URL`` headless
       (passes ``project_picker=None``, ``auto_pick=True``, ``cached_me=None``).
    3. :func:`login_unified_resume` — ``mp login --resume PATH`` recovery
       (passes ``cached_me=<from placeholder>`` to skip the slow /me round-trip
       when the cache is still fresh).

    Rollback contract: on any failure BEFORE the rename, the placeholder is
    left on disk as long as ``tokens.json`` exists in it (so the caller can
    ``mp login --resume PLACEHOLDER``). The post-rename failure path keeps
    today's behavior — ``add()`` failure rmtrees the published ``final_dir``
    so the user isn't left with tokens at the user-visible name and no TOML
    block.

    Args:
        cm: The config manager.
        tokens: The freshly-exchanged tokens. ``access_token`` is read for
            the in-memory ``/me`` probe via :class:`_FreshBrowserBearer`.
        region: Auth region the credential is bound to.
        placeholder_dir: Pre-existing ``.tmp-{nonce}`` directory.
        name: Explicit account name (``None`` to derive from ``/me``).
        project: Explicit project ID (``None`` to use picker / auto-pick).
        project_picker: TTY-gated picker callback (``None`` to skip the
            picker priority — the only valid combo with ``project_picker=None``
            is ``auto_pick=True``, ``project is not None``, or a single-
            project account; otherwise :func:`_resolve_project` raises E-8).
        auto_pick: Enable the filter-then-sort fallback when no explicit
            project and no picker. ``True`` for headless ``--finish`` /
            ``--resume``.
        cached_me: When supplied, skip the ``/me`` HTTP call. Used by
            ``--resume`` after a publish failure when the placeholder
            already carries a fresh ``me.json``.
        progress: CM factory wrapped around the (optional) ``/me``
            round-trip so the CLI's spinner / heartbeat stays active.

    Returns:
        :class:`LoginFinishResult` carrying the published
        :class:`AccountSummary` plus the :class:`ProjectPickResult` so
        the CLI can render the §9 envelope.

    Raises:
        AccountExistsError: Final name collides with an existing account.
        ConfigError: Invalid name (regex), final dir already exists, or
            the picker-or-raise priority chain raised E-8.
        NeedsRegionSwitchError: ``/me`` returned 0 region-compatible projects.
        ProjectNotFoundError: Explicit ``project`` not visible to ``/me``.
    """
    from mixpanel_headless._internal.auth.inflight import cache_me_in_placeholder
    from mixpanel_headless._internal.auth.naming import default_account_name

    # /me probe — skipped when --resume supplies a fresh cached payload.
    if cached_me is not None:
        me_resp = cached_me
    else:
        temp_account = OAuthBrowserAccount(
            name="_tmp_login_unified_",
            region=region,
            default_project=ProjectId("0"),
        )
        with progress(_FETCH_ME_PROGRESS_MESSAGE):
            me_resp = _fetch_me(
                temp_account,
                token_resolver=_FreshBrowserBearer(
                    tokens.access_token.get_secret_value()
                ),
            )
        # Cache /me in the placeholder so a future ``--resume`` can skip
        # the round-trip. Failures here aren't fatal — the cache is an
        # optimization, not a correctness requirement.
        try:
            cache_me_in_placeholder(placeholder_dir, me_resp)
        except OSError as exc:
            logger.warning("Could not cache /me in %s: %s", placeholder_dir, exc)

    # Resolve project (priority chain). May raise NeedsRegionSwitchError
    # for cross-region-only accounts; the placeholder stays on disk so
    # the user can retry with --region after fixing the input.
    pick = _resolve_project(
        me_resp=me_resp,
        explicit_project=project,
        project_picker=project_picker,
        auto_pick=auto_pick,
        region=region,
    )
    chosen_project = pick.project_id

    # E-2 cross-check (defense in depth — auto-pick already region-filters,
    # but explicit / TTY paths can still pick a wrong-region project).
    _assert_project_region_matches(me_resp, chosen_project, region)

    # Resolve final account name.
    existing_names = {s.name for s in cm.list_accounts()}
    final_name = (
        name if name is not None else default_account_name(me_resp, existing_names)
    )
    if final_name in existing_names:
        raise AccountExistsError(final_name)

    # Validate name regex BEFORE rename (defense against path traversal).
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
    # Note: placeholder_dir is now the same directory as final_dir, but
    # the ``placeholder_dir`` Python variable is NOT rebound. This is
    # the symbol the OUTER except in callers checks via ``.startswith(".tmp-")``;
    # leaving it pointing at the (now-non-existent) ``.tmp-*`` path is
    # correct — it tells the outer handler "we already published, your
    # rollback semantic doesn't apply."

    # Persist the account record. If add() raises, roll back final_dir
    # so the user isn't left with tokens at the user-visible name and no
    # [accounts.NAME] block.
    try:
        summary = add(
            final_name,
            type="oauth_browser",
            region=region,
            default_project=chosen_project,
        )
        _persist_me_cache(final_name, me_resp)
        return LoginFinishResult(
            summary=_summary_with_me(
                summary, me_resp=me_resp, project_id=chosen_project
            ),
            pick=pick,
        )
    except Exception:
        _safe_rmtree_warn(final_dir)
        raise


def login_unified_start(
    *,
    region: Region | None = None,
) -> LoginStartResult:
    """Two-shot oauth_browser flow — start step.

    Generates PKCE + state, ensures DCR client registration for ``region``,
    builds the authorize URL, persists the verifier to
    ``~/.mp/oauth/inflight.json`` (mode 0o600, 10-min TTL), and returns
    a :class:`LoginStartResult` carrying both the persisted session and
    the freshly-built authorize URL. Does NOT open a browser, does NOT
    start a callback server, does NOT block.

    The caller is responsible for displaying the ``authorize_url`` to the
    user (slash command, MCP server, scripted wrapper) and then invoking
    :func:`login_unified_finish` with the redirect URL the user pastes back.

    Region defaults to ``"us"`` since PKCE commits to a region before
    ``/me`` runs (no probe). EU / India users pass ``region`` explicitly.

    Args:
        region: Mixpanel region to authenticate against. Defaults to
            ``"us"``. Locked into the inflight file — ``--finish`` cannot
            switch.

    Returns:
        :class:`LoginStartResult` carrying the persisted
        :class:`InflightSession` and the full authorize URL.

    Raises:
        OAuthError: PKCE / DCR / port-binding failure.
    """
    import time
    from urllib.parse import urlencode

    from mixpanel_headless._internal.auth.client_registration import (
        OAUTH_BASE_URLS,
        ensure_client_registered,
    )
    from mixpanel_headless._internal.auth.flow import OAuthFlow
    from mixpanel_headless._internal.auth.inflight import (
        INFLIGHT_SCHEMA_VERSION,
        INFLIGHT_TTL_SECONDS,
        InflightSession,
        find_available_callback_port,
        save_inflight,
    )
    from mixpanel_headless._internal.auth.pkce import PkceChallenge
    from mixpanel_headless._internal.auth.storage import OAuthStorage

    auth_region: Region = region if region is not None else "us"
    pkce = PkceChallenge.generate()
    import secrets as _secrets

    state = _secrets.token_urlsafe(32)
    port = find_available_callback_port()
    redirect_uri = f"http://localhost:{port}/callback"

    # Construct OAuthFlow purely to share its bumped-timeout httpx.Client
    # for the DCR round-trip. The flow itself is not driven — we just
    # need a client with the correct timeout for the cold SOCKS handshake
    # that bites every first-time Cowork run. The `with` block ensures
    # the client is closed even if DCR or URL building raises.
    with OAuthFlow(region=auth_region, storage=OAuthStorage()) as flow:
        client_info = ensure_client_registered(
            http_client=flow.http_client,
            region=auth_region,
            redirect_uri=redirect_uri,
            storage=flow.storage,
        )

    base_url = OAUTH_BASE_URLS[auth_region]
    authorize_url = f"{base_url}authorize/?" + urlencode(
        {
            "response_type": "code",
            "client_id": client_info.client_id,
            "redirect_uri": redirect_uri,
            "state": state,
            "code_challenge": pkce.challenge,
            "code_challenge_method": "S256",
        }
    )

    now = int(time.time())
    session = InflightSession(
        schema_version=INFLIGHT_SCHEMA_VERSION,
        region=auth_region,
        client_id=client_info.client_id,
        redirect_uri=redirect_uri,
        pkce_verifier=pkce.verifier,
        state=state,
        created_at=now,
        expires_at=now + INFLIGHT_TTL_SECONDS,
    )
    save_inflight(session)
    return LoginStartResult(inflight=session, authorize_url=authorize_url)


def login_unified_finish(
    *,
    pasted_url: str,
    name: str | None = None,
    project: str | None = None,
    project_picker: ProjectPicker | None = None,
    progress: ProgressFactory | None = None,
) -> LoginFinishResult:
    """Two-shot oauth_browser flow — finish step.

    Reads ``~/.mp/oauth/inflight.json``, validates the pasted URL's state
    against the inflight, exchanges the authorization code for tokens,
    writes tokens to a fresh placeholder dir, then delegates to
    :func:`_publish_account_from_tokens` with ``auto_pick=True``.

    On success: clears the inflight file, returns :class:`LoginFinishResult`
    so the CLI can render the §9 envelope. On failure (including
    state mismatch, /me errors, region mismatch, account name collision):
    leaves the inflight in place so the user can retry without re-running
    PKCE; leaves the placeholder in place when ``tokens.json`` was
    already written so the user can ``mp login --resume PLACEHOLDER``.

    Args:
        pasted_url: The redirect URL (or ``code=...&state=...`` query
            string) the user pasted from their browser address bar.
        name: Explicit account name (``None`` to derive from /me).
        project: Explicit project ID (``None`` to auto-pick).
        project_picker: Optional TTY picker. CLI sets this when
            ``sys.stdin.isatty()``; ``None`` for headless callers.
        progress: CM factory wrapped around the slow ``/me`` call.

    Returns:
        :class:`LoginFinishResult` for the new account.

    Raises:
        OAuthError: ``OAUTH_INFLIGHT_*`` (missing / expired / corrupt
            inflight), ``OAUTH_STATE_MISMATCH`` / ``OAUTH_PASTE_ERROR``
            (bad pasted URL), or any error from
            :meth:`OAuthFlow.exchange_code` / ``/me`` / publish.
        NeedsRegionSwitchError: 0 region-compatible projects.
        ProjectNotFoundError: Explicit ``project`` not visible.
        AccountExistsError: Derived name collides; pass ``name=`` to override.
    """
    from mixpanel_headless._internal.auth.flow import (
        OAuthFlow,
        _parse_pasted_redirect,
    )
    from mixpanel_headless._internal.auth.inflight import (
        clear_inflight,
        load_inflight,
        new_placeholder_dir,
        save_placeholder_meta,
    )
    from mixpanel_headless._internal.auth.storage import OAuthStorage

    if progress is None:
        progress = lambda _msg: contextlib.nullcontext()  # noqa: E731

    inflight = load_inflight()
    cb = _parse_pasted_redirect(pasted_url, expected_state=inflight.state)

    with OAuthFlow(region=inflight.region, storage=OAuthStorage()) as flow:
        tokens = flow.exchange_code(
            code=cb.code,
            verifier=inflight.pkce_verifier,
            client_id=inflight.client_id,
            redirect_uri=inflight.redirect_uri,
        )

    placeholder_dir = new_placeholder_dir(accounts_root())
    atomic_write_bytes(placeholder_dir / "tokens.json", token_payload_bytes(tokens))
    save_placeholder_meta(placeholder_dir, region=inflight.region)

    cm = _config()
    try:
        result = _publish_account_from_tokens(
            cm,
            tokens=tokens,
            region=inflight.region,  # type: ignore[arg-type]
            placeholder_dir=placeholder_dir,
            name=name,
            project=project,
            project_picker=project_picker,
            auto_pick=True,
            cached_me=None,
            progress=progress,
        )
    except NeedsRegionSwitchError:
        # Cross-region is fundamental, not transient — re-running
        # --resume against this placeholder would hit the same error.
        # Clean up the placeholder + inflight so the user can run
        # `mp login --start --region eu` (or whichever region) without
        # an orphan .tmp-* dir lingering forever.
        _safe_rmtree_warn(placeholder_dir)
        clear_inflight()
        raise
    except Exception as exc:
        # Token exchange already consumed the OAuth code, so re-running
        # --finish with the same paste will fail at the IdP. Clear the
        # inflight (it's useless now). If the placeholder still has
        # tokens.json, wrap as LoginFinishPublishError so the CLI can
        # surface the resume command. Post-rename failures (handled by
        # the inner except in _publish_account_from_tokens) leave the
        # placeholder gone, in which case the original exception
        # propagates unchanged.
        clear_inflight()
        if (placeholder_dir / "tokens.json").exists():
            raise LoginFinishPublishError(
                placeholder_dir=placeholder_dir,
                cause=exc,
            ) from exc
        raise

    clear_inflight()
    use(result.summary.name)
    return result


def login_unified_resume(
    *,
    placeholder_dir: Path,
    name: str | None = None,
    project: str | None = None,
    project_picker: ProjectPicker | None = None,
    progress: ProgressFactory | None = None,
) -> LoginFinishResult:
    """Two-shot oauth_browser flow — post-publish-failure recovery.

    Reads ``tokens.json`` (and optionally a fresh ``me.json``) from
    ``placeholder_dir``, then runs only the publish tail. No PKCE, no
    code exchange — the tokens already exist. Clears the inflight file
    on success.

    Used when ``mp login --finish`` succeeded at token exchange but
    failed at publish (e.g., ``/me`` timed out, ``add()`` collision,
    transient network blip during the ``add()`` write). The user re-runs
    ``mp login --resume <PLACEHOLDER>`` and we pick up where we left off.

    Args:
        placeholder_dir: The ``.tmp-{nonce}`` directory left behind by a
            failed ``--finish`` attempt. Must exist and contain
            ``tokens.json``.
        name: Explicit account name (``None`` to derive).
        project: Explicit project ID (``None`` to auto-pick).
        project_picker: Optional TTY picker.
        progress: CM factory.

    Returns:
        :class:`LoginFinishResult` for the recovered account.

    Raises:
        ConfigError: ``placeholder_dir`` is not under
            :func:`accounts_root`, doesn't look like a placeholder
            (wrong name pattern), doesn't contain ``tokens.json``, or
            its ``meta.json`` carries an invalid ``region``.
        OAuthError: ``tokens.json`` is malformed, or
            ``meta.json`` exists but is corrupt
            (``OAUTH_PLACEHOLDER_META_CORRUPT``).
        Plus all the failure modes of :func:`_publish_account_from_tokens`.
    """
    from mixpanel_headless._internal.auth.inflight import (
        clear_inflight,
        load_cached_me_from_placeholder,
        read_placeholder_meta,
        read_tokens_from_placeholder,
    )
    from mixpanel_headless._internal.auth.storage import accounts_root as _accounts_root

    if progress is None:
        progress = lambda _msg: contextlib.nullcontext()  # noqa: E731

    placeholder_dir = placeholder_dir.resolve()
    # Guard against arbitrary on-disk paths. ``--resume`` will rename the
    # placeholder into ``accounts_root()``; if a caller hands us
    # ``/tmp/.tmp-foo``, we'd silently exfiltrate whoever's tokens are
    # sitting there. Keep ``--resume`` strictly under the accounts root.
    root = _accounts_root().resolve()
    if not placeholder_dir.is_relative_to(root):
        raise ConfigError(
            f"--resume placeholder must live under {root}; got "
            f"{placeholder_dir}. Pass the path printed by the failed "
            f"`mp login --finish` invocation."
        )
    if not placeholder_dir.exists():
        raise ConfigError(f"Placeholder directory {placeholder_dir} does not exist.")
    if not placeholder_dir.name.startswith(".tmp-"):
        raise ConfigError(
            f"--resume expects a .tmp-* placeholder directory; got "
            f"{placeholder_dir.name}. Pass the path printed by the failed "
            f"`mp login --finish` invocation."
        )
    if not (placeholder_dir / "tokens.json").exists():
        raise ConfigError(
            f"No tokens.json in {placeholder_dir}. Nothing to resume — "
            f"run `mp login --start` to begin a fresh login."
        )

    tokens = read_tokens_from_placeholder(placeholder_dir)

    # Region detection: prefer the placeholder's meta.json (written at
    # --finish time). ``read_placeholder_meta`` returns ``None`` ONLY
    # when meta.json is absent (legacy placeholders predating the
    # meta-writing code) — corrupt / unreadable meta now raises
    # ``OAUTH_PLACEHOLDER_META_CORRUPT``. The "us" default is therefore
    # only reached for legacy placeholders, never for a modern EU/IN
    # placeholder with a busted meta.json (which would otherwise hit
    # the NeedsRegionSwitchError cleanup path below and destroy
    # recoverable tokens).
    meta = read_placeholder_meta(placeholder_dir)
    region: Region = "us"
    if meta is not None:
        meta_region = meta.get("region")
        if isinstance(meta_region, str) and meta_region in ("us", "eu", "in"):
            region = meta_region  # type: ignore[assignment]
        else:
            raise ConfigError(
                f"Placeholder {placeholder_dir} has invalid region "
                f"{meta_region!r} in meta.json. Repair meta.json by hand "
                f"or re-run `mp login --start --region <us|eu|in>`."
            )

    cached_me = load_cached_me_from_placeholder(placeholder_dir)

    cm = _config()
    try:
        result = _publish_account_from_tokens(
            cm,
            tokens=tokens,
            region=region,
            placeholder_dir=placeholder_dir,
            name=name,
            project=project,
            project_picker=project_picker,
            auto_pick=True,
            cached_me=cached_me,  # type: ignore[arg-type]  # runtime MeResponse cast
            progress=progress,
        )
    except NeedsRegionSwitchError:
        # Same as --finish: cross-region is unrecoverable via --resume.
        # Clean up the placeholder so the user can `mp login --start
        # --region eu` cleanly.
        _safe_rmtree_warn(placeholder_dir)
        clear_inflight()
        raise
    except Exception as exc:
        # Tokens still exist on disk; wrap so the slash command can
        # render the resume command (same path the user passed in).
        if (placeholder_dir / "tokens.json").exists():
            raise LoginFinishPublishError(
                placeholder_dir=placeholder_dir,
                cause=exc,
            ) from exc
        raise

    clear_inflight()
    use(result.summary.name)
    return result


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
    progress: ProgressFactory,
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
        progress: CM factory wrapped around the ``/me`` round-trip so the
            CLI's spinner stays active during the slow step.

    Returns:
        :class:`AccountSummary` for the new account, with ``user_email``
        / ``project_id`` / ``project_name`` populated from ``/me``.
    """
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

    # Region resolution (probe when None). The shared helper handles
    # the SA / oauth_token header construction and per-attempt
    # narration; this site just supplies the credentials and the
    # narrate callback.
    resolved_region: Region
    if region is not None:
        resolved_region = region
    else:
        from mixpanel_headless._internal.auth.region_probe import (
            probe_region_for_credential,
        )

        resolved_region = probe_region_for_credential(
            account_type=detected_type,
            username=username,
            secret=secret,
            token=token,
            token_env=resolved_token_env,
            narrate=_narrate,
        )

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

    with progress(_FETCH_ME_PROGRESS_MESSAGE):
        me_resp = _fetch_me(temp_account)

    pick = _resolve_project(
        me_resp=me_resp,
        explicit_project=project,
        project_picker=project_picker,
        auto_pick=False,
        region=resolved_region,
    )
    chosen_project = pick.project_id

    # Resolve final name (--name wins; otherwise derive from /me).
    final_name: str
    if name is None:
        from mixpanel_headless._internal.auth.naming import default_account_name

        existing_names = {s.name for s in cm.list_accounts()}
        # ``default_account_name`` returns ``AccountName`` (a str
        # NewType); add() accepts plain str, so widen explicitly here.
        final_name = str(default_account_name(me_resp, existing_names))
    else:
        final_name = name

    summary = add(
        final_name,
        type=detected_type,
        region=resolved_region,
        default_project=chosen_project,
        username=username,
        secret=secret,
        token=token,
        token_env=resolved_token_env,
    )
    # Persist /me cache so the next MeService call hits the warm cache
    # (python-api.md §1 contract). Failures bubble — at this point the
    # account record is already on disk, so a cache-write error doesn't
    # need a tokens rollback (unlike the browser path's atomic publish).
    _persist_me_cache(final_name, me_resp)
    return _summary_with_me(summary, me_resp=me_resp, project_id=chosen_project)


def _resolve_project(
    *,
    me_resp: MeResponse,
    explicit_project: str | None,
    project_picker: ProjectPicker | None,
    auto_pick: bool = False,
    region: Region = "us",
) -> ProjectPickResult:
    """Apply the project-selection priority chain.

    Returns a :class:`ProjectPickResult` carrying the chosen project ID
    plus structured metadata (method, primary-org info, funnel counts) so
    callers can announce how the choice was made. Replaces the prior
    bare ``str | None`` return.

    The selection chain is:

    1. ``explicit_project`` set → validate visibility, return
       ``method="explicit"``.
    2. ``MP_PROJECT_ID`` env set → validate visibility (hard-fail if
       stale), return ``method="explicit"``.
    3. Region filter — drop projects whose ``domain`` doesn't match
       ``region`` per :data:`DOMAIN_FOR_REGION`. If 0 region-compatible
       projects remain, raise :class:`NeedsRegionSwitchError`.
    4. ``project_picker`` set → invoke against the region-compatible
       list (interactive users may want a demo or unintegrated project),
       return ``method="tty_picker"``.
    5. ``auto_pick=True`` → run the filter-then-sort algorithm:
       drop ``is_demo`` and ``has_integrated=False`` projects; pick from
       the highest-survivor-count org, lowest project ID within. Falls
       back through unintegrated → demos when no project survives the
       aggressive filter.
    6. ``auto_pick=False`` → existing E-8 behavior: raise ``ConfigError``
       when the user has multiple region-compatible projects and no picker.

    Args:
        me_resp: Parsed :class:`MeResponse`.
        explicit_project: ``--project`` argument (priority 1).
        project_picker: Picker callback for the TTY case.
        auto_pick: Enable the filter-then-sort fallback when no picker
            and no explicit pick. ``True`` for ``mp login --finish`` /
            ``--resume`` (the headless paths). ``False`` for same-machine
            ``mp login`` (preserves today's picker-or-raise behavior).
        region: Region the credential authenticated against. Used to
            filter ``MeProjectInfo.domain`` and to populate
            ``ProjectPickResult.auth_region``.

    Returns:
        :class:`ProjectPickResult` with ``project_id`` set on success
        (``None`` when ``method == "no_projects"``).

    Raises:
        ProjectNotFoundError: ``explicit_project`` not in ``/me``.
        ConfigError: ``MP_PROJECT_ID`` set in env but not visible, or
            multi-project context with no picker and ``auto_pick=False``
            (E-8).
        NeedsRegionSwitchError: Zero region-compatible projects after
            region filter.
    """
    projects = me_resp.projects
    accessible_n = len(projects)

    # No projects at all — nothing to pick. Caller leaves default_project
    # unset; the user runs ``mp project use ID`` once one becomes accessible.
    if accessible_n == 0:
        return ProjectPickResult(
            project_id=None,
            method="no_projects",
            auth_region=region,
            accessible_project_count=0,
        )

    # Priority 1: explicit --project. Skips all filtering — the user knows
    # what they want; ``_assert_project_region_matches`` catches cross-region
    # picks downstream with a more actionable error.
    if explicit_project is not None:
        if explicit_project not in projects:
            raise ProjectNotFoundError(
                explicit_project,
                available_projects=builtins.list(projects.keys()),
            )
        return ProjectPickResult(
            project_id=explicit_project,
            method="explicit",
            auth_region=region,
            accessible_project_count=accessible_n,
            region_compatible_count=accessible_n,
            filtered_count=accessible_n,
        )

    # Priority 2: MP_PROJECT_ID env. Treated as user-explicit — hard-fail
    # if not visible (the resolver reads MP_PROJECT_ID first on every
    # subsequent CLI call, so a stale value would silently shadow the
    # picker's choice).
    env_project = os.environ.get("MP_PROJECT_ID")
    if env_project:
        if env_project not in projects:
            accessible_lines = "\n".join(
                f"  - {pid} : {info.name} ({info.domain or '(no domain)'})"
                for pid, info in projects.items()
            )
            raise ConfigError(
                f"MP_PROJECT_ID={env_project} is not visible to this account.\n\n"
                f"Accessible projects:\n{accessible_lines}\n\n"
                f"Either unset MP_PROJECT_ID, or pass --project ID with a "
                f"visible value. (Subsequent `mp` calls would otherwise read "
                f"MP_PROJECT_ID first and silently fail with auth errors.)"
            )
        return ProjectPickResult(
            project_id=env_project,
            method="explicit",
            auth_region=region,
            accessible_project_count=accessible_n,
            region_compatible_count=accessible_n,
            filtered_count=accessible_n,
        )

    # Legacy path: when auto_pick=False, preserve the existing
    # same-machine behavior precisely. No region pre-filter (the picker
    # sees all projects; ``_assert_project_region_matches`` catches
    # wrong-region picks after the fact). This keeps the behavior
    # documented as "TTY picker fires for multi-project, E-8 raises for
    # non-TTY without picker" intact for ``mp login`` (no --finish flag).
    if not auto_pick:
        return _resolve_project_legacy(
            me_resp=me_resp,
            project_picker=project_picker,
            region=region,
            accessible_n=accessible_n,
        )

    # Auto-pick path (--finish / --resume). Region-filter first, then
    # apply the aggressive filter cascade with primary-org / lowest-id
    # tiebreak. TTY picker (if present) preempts auto-pick; same-machine
    # SSH-into-Cowork users still get to choose interactively.
    from mixpanel_headless._internal.auth.client_registration import DOMAIN_FOR_REGION

    auth_domain = DOMAIN_FOR_REGION.get(region)
    region_compat: dict[str, MeProjectInfo] = {}
    if auth_domain is None:
        # Unknown region (shouldn't happen under the Region literal) —
        # don't filter, treat all as region-compat.
        region_compat = dict(projects)
    else:
        for pid, info in projects.items():
            # Projects with no ``domain`` (older payloads) are kept —
            # better to surface them than to silently exclude on missing data.
            if info.domain is None or info.domain == auth_domain:
                region_compat[pid] = info
    region_n = len(region_compat)

    if region_n == 0:
        # All projects in a different cluster. Refuse to publish a
        # wrong-region account; surface alternatives.
        cross = [
            (pid, info.name, info.domain or "(no domain)")
            for pid, info in projects.items()
        ]
        per_region: dict[str, int] = {}
        for _pid, _name, domain in cross:
            r = _domain_to_region(domain) or "(unknown)"
            per_region[r] = per_region.get(r, 0) + 1
        breakdown = ", ".join(
            f"{count} in {r}" for r, count in sorted(per_region.items())
        )
        suggestion = ""
        for r in ("eu", "in", "us"):
            if r != region and per_region.get(r):
                suggestion = (
                    f"\n\nRun `mp login --start --region {r}` to create a "
                    f"separate account for that region."
                )
                break
        pick = ProjectPickResult(
            project_id=None,
            method="cross_region_only",
            auth_region=region,
            accessible_project_count=accessible_n,
            region_compatible_count=0,
            filtered_count=0,
            cross_region_projects=cross,
        )
        raise NeedsRegionSwitchError(
            f"No projects in region {region} accessible to this account "
            f"({breakdown}).{suggestion}",
            pick=pick,
        )

    # Aggressive filter chain: drop demos, then drop unintegrated. Both
    # fields are undeclared on MeProjectInfo (live API returns them via
    # model_extra).
    def _is_demo(info: MeProjectInfo) -> bool:
        """True if ``info`` is a Mixpanel demo project.

        Read from the live ``/me`` payload's ``is_demo`` field via
        ``model_extra`` (the field is not declared on
        :class:`MeProjectInfo` so it travels through pydantic's extras).
        Demo projects are excluded from auto-pick unless every
        region-compatible project is a demo (the
        ``fallback_with_demos`` last resort).
        """
        return bool((info.model_extra or {}).get("is_demo"))

    def _is_integrated(info: MeProjectInfo) -> bool:
        """True if ``info`` has received events at some point.

        ``has_integrated == True`` means the project has data;
        anything else (missing, ``False``, ``None``) means
        "abandoned / never-shipped" for auto-pick purposes. Same
        ``model_extra`` story as :func:`_is_demo`. Unintegrated
        projects are excluded unless every non-demo project is
        unintegrated (the ``fallback_with_unintegrated`` cascade
        step).
        """
        return (info.model_extra or {}).get("has_integrated") is True

    no_demos = {pid: info for pid, info in region_compat.items() if not _is_demo(info)}
    demo_excluded = region_n - len(no_demos)
    filtered = {pid: info for pid, info in no_demos.items() if _is_integrated(info)}
    unintegrated_excluded = len(no_demos) - len(filtered)

    # Sole-survivor short-circuit at the region-compat level.
    if region_n == 1:
        only = next(iter(region_compat))
        only_info = region_compat[only]
        org = me_resp.organizations.get(str(only_info.organization_id))
        return ProjectPickResult(
            project_id=only,
            method="sole_survivor",
            auth_region=region,
            primary_org_id=str(only_info.organization_id),
            primary_org_name=org.name if org is not None else None,
            primary_org_survivor_count=1,
            accessible_project_count=accessible_n,
            region_compatible_count=region_n,
            filtered_count=len(filtered),
            demo_excluded=demo_excluded,
            unintegrated_excluded=unintegrated_excluded,
        )

    # TTY picker preempts auto-pick. Operates on region-compat (NOT the
    # aggressive filter) so interactive users can still pick a demo or
    # unintegrated project if they want.
    if project_picker is not None:

        def _sort_key(item: tuple[str, MeProjectInfo]) -> tuple[str, str]:
            """Build (org_name, project_name) sort key, both case-folded."""
            _pid, info = item
            org = me_resp.organizations.get(str(info.organization_id))
            org_name = org.name if org is not None else f"~org {info.organization_id}"
            return (org_name.lower(), info.name.lower())

        sorted_projects = sorted(region_compat.items(), key=_sort_key)
        chosen = project_picker(me_resp, sorted_projects)
        return ProjectPickResult(
            project_id=chosen,
            method="tty_picker",
            auth_region=region,
            accessible_project_count=accessible_n,
            region_compatible_count=region_n,
            filtered_count=len(filtered),
            demo_excluded=demo_excluded,
            unintegrated_excluded=unintegrated_excluded,
        )

    # No picker, no explicit, auto_pick=True → run the algorithm.
    return _auto_pick_from_filtered(
        me_resp=me_resp,
        region=region,
        accessible_n=accessible_n,
        region_compat=region_compat,
        no_demos=no_demos,
        filtered=filtered,
        demo_excluded=demo_excluded,
        unintegrated_excluded=unintegrated_excluded,
    )


def _resolve_project_legacy(
    *,
    me_resp: MeResponse,
    project_picker: ProjectPicker | None,
    region: Region,
    accessible_n: int,
) -> ProjectPickResult:
    """Legacy ``auto_pick=False`` path — preserves pre-043 same-machine behavior.

    No region filter (the picker sees all projects; the post-pick
    ``_assert_project_region_matches`` cross-check raises E-2 on wrong
    region). Single-project auto-pick when there's exactly one project.
    Picker fires for multi-project. Raises ``ConfigError`` (E-8) when
    multi-project and no picker.

    Args:
        me_resp: Parsed ``/me``.
        project_picker: TTY picker callback.
        region: Auth region (carried into the result for the envelope).
        accessible_n: Total project count (already computed by caller).

    Returns:
        :class:`ProjectPickResult` with method ``"explicit"`` (single
        project) or ``"tty_picker"`` (after picker fires).

    Raises:
        ConfigError: Multi-project context with no picker (E-8).
    """
    projects = me_resp.projects
    if accessible_n == 1:
        only = next(iter(projects))
        only_info = projects[only]
        org = me_resp.organizations.get(str(only_info.organization_id))
        return ProjectPickResult(
            project_id=only,
            method="sole_survivor",
            auth_region=region,
            primary_org_id=str(only_info.organization_id),
            primary_org_name=org.name if org is not None else None,
            primary_org_survivor_count=1,
            accessible_project_count=accessible_n,
            region_compatible_count=accessible_n,
            filtered_count=accessible_n,
        )

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

    def _sort_key(item: tuple[str, MeProjectInfo]) -> tuple[str, str]:
        """Build (org_name, project_name) sort key, both case-folded."""
        _pid, info = item
        org = me_resp.organizations.get(str(info.organization_id))
        org_name = org.name if org is not None else f"~org {info.organization_id}"
        return (org_name.lower(), info.name.lower())

    sorted_projects = sorted(projects.items(), key=_sort_key)
    chosen = project_picker(me_resp, sorted_projects)
    return ProjectPickResult(
        project_id=chosen,
        method="tty_picker",
        auth_region=region,
        accessible_project_count=accessible_n,
        region_compatible_count=accessible_n,
        filtered_count=accessible_n,
    )


def _auto_pick_from_filtered(
    *,
    me_resp: MeResponse,
    region: Region,
    accessible_n: int,
    region_compat: dict[str, MeProjectInfo],
    no_demos: dict[str, MeProjectInfo],
    filtered: dict[str, MeProjectInfo],
    demo_excluded: int,
    unintegrated_excluded: int,
) -> ProjectPickResult:
    """Apply the auto-pick filter cascade and return the structured result.

    Tries the aggressively-filtered set (region + non-demo + integrated)
    first. Falls back to ``no_demos`` (re-include unintegrated), then to
    ``region_compat`` (re-include demos). The method enum tells the CLI
    which fallback fired so it can surface the appropriate caveat.

    Args:
        me_resp: Parsed ``/me`` response (used to look up org names).
        region: Region the credential authenticated against.
        accessible_n: Total ``len(me_resp.projects)`` (for the funnel).
        region_compat: Projects after region filter (the broadest pool).
        no_demos: Projects after region + ``is_demo=False``.
        filtered: Projects after region + ``is_demo=False`` +
            ``has_integrated=True``.
        demo_excluded: Count of region-compat projects dropped for is_demo.
        unintegrated_excluded: Count of non-demo projects dropped for
            ``has_integrated`` not being True.

    Returns:
        The :class:`ProjectPickResult` carrying the pick + funnel counts.
    """
    region_n = len(region_compat)
    filtered_n = len(filtered)

    if filtered:
        chosen, primary_org_id, survivor_count = _pick_from_primary_org(
            filtered, me_resp.organizations
        )
        org = me_resp.organizations.get(str(primary_org_id))
        return ProjectPickResult(
            project_id=chosen,
            method=(
                "primary_org_lowest_id" if filtered_n > 1 else "sole_survivor_filtered"
            ),
            auth_region=region,
            primary_org_id=str(primary_org_id),
            primary_org_name=org.name if org is not None else None,
            primary_org_survivor_count=survivor_count,
            accessible_project_count=accessible_n,
            region_compatible_count=region_n,
            filtered_count=filtered_n,
            demo_excluded=demo_excluded,
            unintegrated_excluded=unintegrated_excluded,
        )

    if no_demos:
        chosen, primary_org_id, survivor_count = _pick_from_primary_org(
            no_demos, me_resp.organizations
        )
        org = me_resp.organizations.get(str(primary_org_id))
        return ProjectPickResult(
            project_id=chosen,
            method="fallback_with_unintegrated",
            auth_region=region,
            primary_org_id=str(primary_org_id),
            primary_org_name=org.name if org is not None else None,
            primary_org_survivor_count=survivor_count,
            accessible_project_count=accessible_n,
            region_compatible_count=region_n,
            filtered_count=filtered_n,
            demo_excluded=demo_excluded,
            unintegrated_excluded=unintegrated_excluded,
        )

    # Last resort: re-include demos.
    chosen, primary_org_id, survivor_count = _pick_from_primary_org(
        region_compat, me_resp.organizations
    )
    org = me_resp.organizations.get(str(primary_org_id))
    return ProjectPickResult(
        project_id=chosen,
        method="fallback_with_demos",
        auth_region=region,
        primary_org_id=str(primary_org_id),
        primary_org_name=org.name if org is not None else None,
        primary_org_survivor_count=survivor_count,
        accessible_project_count=accessible_n,
        region_compatible_count=region_n,
        filtered_count=filtered_n,
        demo_excluded=demo_excluded,
        unintegrated_excluded=unintegrated_excluded,
    )


def _pick_from_primary_org(
    pool: dict[str, MeProjectInfo],
    orgs: dict[str, Any],
) -> tuple[str, int, int]:
    """Pick the org with the most ``pool`` survivors, then lowest project ID.

    Tiebreak across orgs: lowest org ID (deterministic; orgs with equal
    survivor counts get sorted by integer ID). Tiebreak within an org:
    lowest project ID (numeric). Both rules are stable across runs so a
    re-run on the same ``/me`` produces the same auto-pick.

    Returns ``(project_id, primary_org_id, survivor_count)``.

    Args:
        pool: Project subset to pick from. Must be non-empty.
        orgs: ``me_resp.organizations``. Currently unconsulted by the
            tiebreak rules (which use IDs only); accepted as a parameter
            for symmetry with the caller and so the algorithm can be
            extended with name-based heuristics without breaking the call
            site.

    Returns:
        Tuple of (chosen project ID, the primary org ID, survivor count
        in that org).
    """
    del orgs  # unused — see docstring
    counts: dict[int, int] = {}
    for info in pool.values():
        counts[info.organization_id] = counts.get(info.organization_id, 0) + 1
    # Highest count wins; tiebreak by lowest org ID.
    primary_org_id = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[0][0]
    survivor_count = counts[primary_org_id]
    in_primary = [
        pid for pid, info in pool.items() if info.organization_id == primary_org_id
    ]
    # Lowest project ID (numeric) wins. Numeric IDs are guaranteed by the
    # /me response shape; non-numeric IDs would TypeError here, which is
    # the right surface signal — silent fallback to lex-sort would mask a
    # schema regression.
    chosen = min(in_primary, key=lambda pid: int(pid))
    return chosen, primary_org_id, survivor_count


__all__ = [
    "LoginFinishResult",
    "LoginStartResult",
    "PickMethod",
    "ProjectPickResult",
    "add",
    "export_bridge",
    "list",
    "login",
    "login_unified",
    "login_unified_finish",
    "login_unified_resume",
    "login_unified_start",
    "logout",
    "remove",
    "remove_bridge",
    "show",
    "test",
    "token",
    "update",
    "use",
]
