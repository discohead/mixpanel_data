"""Mixpanel /me API types, caching, and service layer.

Provides models for the ``/api/app/me`` response along with a disk-based
cache (``MeCache``) and orchestration service (``MeService``) for project
and workspace discovery.

Types use ``extra="allow"`` for forward compatibility with API changes.
"""

from __future__ import annotations

import json
import logging
import os
import stat
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pydantic
from pydantic import BaseModel, ConfigDict

from mixpanel_headless._internal.io_utils import atomic_write_bytes
from mixpanel_headless.exceptions import AuthenticationError, ConfigError, QueryError

if TYPE_CHECKING:
    from mixpanel_headless._internal.api_client import MixpanelAPIClient
    from mixpanel_headless._internal.auth.account import AccountType

logger = logging.getLogger(__name__)


class MeOrgInfo(BaseModel):
    """Organization information within a /me response.

    Uses ``extra="allow"`` for forward compatibility — unknown fields
    from the API are preserved in ``model_extra``.

    Args:
        id: Organization ID.
        name: Organization display name.
        role: User's role in this organization (optional).
        permissions: User's permissions in this organization (optional).

    Example:
        ```python
        org = MeOrgInfo(id=100, name="Acme Corp", role="admin")
        ```
    """

    model_config = ConfigDict(extra="allow", frozen=True)

    id: int
    """Organization ID."""

    name: str
    """Organization display name."""

    role: str | None = None
    """User's role in this organization."""

    permissions: list[str] | None = None
    """User's permissions in this organization."""


class MeProjectInfo(BaseModel):
    """Project information within a /me response.

    Uses ``extra="allow"`` for forward compatibility.

    Args:
        name: Project display name.
        organization_id: Owning organization ID.
        timezone: Project timezone (optional).
        has_workspaces: Whether project uses workspaces (optional).
        domain: Mixpanel domain for the project's cluster (optional).
        type: Project type — string (e.g. "PROJECT", "ROLLUP") or integer code (optional).

    Example:
        ```python
        project = MeProjectInfo(
            name="AI Demo",
            organization_id=100,
            timezone="US/Pacific",
        )
        ```
    """

    model_config = ConfigDict(extra="allow", frozen=True)

    name: str
    """Project display name."""

    organization_id: int
    """Owning organization ID."""

    timezone: str | None = None
    """Project timezone."""

    has_workspaces: bool | None = None
    """Whether project uses workspaces."""

    domain: str | None = None
    """Mixpanel domain for the project's cluster."""

    type: str | int | None = None
    """Project type (e.g., 'PROJECT', 'ROLLUP', or integer type code)."""


class MeWorkspaceInfo(BaseModel):
    """Workspace information within a /me response.

    Uses ``extra="allow"`` for forward compatibility.

    Args:
        id: Workspace ID.
        name: Workspace display name.
        project_id: Parent project ID.
        is_default: Whether this is the project's default workspace (optional).
        is_global: Whether this is a global workspace (optional).
        is_restricted: Whether access is restricted (optional).
        is_visible: Whether workspace is visible (optional).
        description: Workspace description (optional).
        creator_name: Who created the workspace (optional).

    Example:
        ```python
        ws = MeWorkspaceInfo(
            id=3448413, name="Default", project_id=3713224, is_default=True,
        )
        ```
    """

    model_config = ConfigDict(extra="allow", frozen=True)

    id: int
    """Workspace ID."""

    name: str
    """Workspace display name."""

    project_id: int
    """Parent project ID."""

    is_default: bool | None = None
    """Whether this is the project's default workspace."""

    is_global: bool | None = None
    """Whether this is a global workspace."""

    is_restricted: bool | None = None
    """Whether access is restricted."""

    is_visible: bool | None = None
    """Whether workspace is visible."""

    description: str | None = None
    """Workspace description."""

    creator_name: str | None = None
    """Who created the workspace."""


class MeResponse(BaseModel):
    """Model for the Mixpanel /me API response.

    All fields are optional for forward-compatible deserialization.
    Unknown fields are preserved via ``extra="allow"``.

    Args:
        user_id: Authenticated user's ID (optional).
        user_email: User's email (optional).
        user_name: User's display name (optional).
        organizations: Accessible organizations, keyed by org ID (optional).
        projects: Accessible projects, keyed by project ID (optional).
        workspaces: Accessible workspaces, keyed by workspace ID (optional).
        cached_at: When this response was cached (added by client, optional).
        cached_region: Which region this cache is for (added by client, optional).

    Example:
        ```python
        me = MeResponse(
            user_id=42,
            user_email="user@example.com",
            projects={"123": MeProjectInfo(name="My Project", organization_id=1)},
        )
        ```
    """

    model_config = ConfigDict(extra="allow", frozen=True)

    user_id: int | None = None
    """Authenticated user's ID."""

    user_email: str | None = None
    """User's email."""

    user_name: str | None = None
    """User's display name."""

    organizations: dict[str, MeOrgInfo] = {}
    """Accessible organizations, keyed by org ID."""

    projects: dict[str, MeProjectInfo] = {}
    """Accessible projects, keyed by project ID."""

    workspaces: dict[str, MeWorkspaceInfo] = {}
    """Accessible workspaces, keyed by workspace ID."""

    cached_at: float | None = None
    """Unix timestamp when this response was cached (added by caching layer)."""

    cached_region: str | None = None
    """Which region this cache is for (added by caching layer)."""


# Default cache TTL: 24 hours
_DEFAULT_TTL_SECONDS = 86400


class MeCache:
    """Disk-based, per-account cache for /me API responses.

    Stores one response file per account at
    ``~/.mp/accounts/{account_name}/me.json`` (or under ``storage_dir``
    when overridden for tests) with configurable TTL. Files are created
    with ``0o600`` permissions inside the per-account directory at
    ``0o700``.

    Args:
        account_name: Account name — drives the per-account cache
            directory layout introduced by the 042 auth redesign.
        storage_dir: Override the cache directory entirely. When provided,
            the cache file lives at ``{storage_dir}/me.json`` regardless
            of ``account_name``. Tests use this to point at a tmp dir.
        ttl_seconds: Cache time-to-live in seconds. Default: 86400 (24h).

    Example:
        ```python
        cache = MeCache(account_name="personal")
        cache.put(me_response)
        cached = cache.get()  # Returns MeResponse or None
        cache.invalidate()
        ```
    """

    def __init__(
        self,
        *,
        account_name: str,
        storage_dir: Path | None = None,
        ttl_seconds: int = _DEFAULT_TTL_SECONDS,
    ) -> None:
        """Initialize MeCache.

        Args:
            account_name: Account name. Cache files live at
                ``~/.mp/accounts/{account_name}/me.json`` unless
                ``storage_dir`` overrides.
            storage_dir: Override cache directory (test injection).
            ttl_seconds: Cache TTL in seconds. Default: 86400 (24 hours).
        """
        self._account_name = account_name
        if storage_dir is not None:
            self._cache_dir = storage_dir
        else:
            self._cache_dir = Path.home() / ".mp" / "accounts" / account_name
        self._ttl_seconds = ttl_seconds

    def _cache_path(self) -> Path:
        """Return the per-account cache file path.

        Returns:
            ``{cache_dir}/me.json``.
        """
        return self._cache_dir / "me.json"

    def get(self) -> MeResponse | None:
        """Retrieve the cached /me response for the bound account.

        Returns ``None`` if no cache exists, the cache is expired,
        or the cache file is corrupted.

        Returns:
            Cached MeResponse or None if cache miss/expired/corrupted.

        Example:
            ```python
            cache = MeCache(account_name="personal")
            me = cache.get()
            if me is None:
                me = fetch_from_api()
                cache.put(me)
            ```
        """
        path = self._cache_path()
        if not path.exists():
            return None

        try:
            raw = path.read_text(encoding="utf-8")
            data: dict[str, Any] = json.loads(raw)
        except (json.JSONDecodeError, OSError) as e:
            logger.debug("Corrupted cache file %s: %s", path, e)
            return None

        # Check TTL
        cached_at = data.get("cached_at")
        if cached_at is not None and isinstance(cached_at, (int, float)):
            age = time.time() - cached_at
            if age > self._ttl_seconds:
                logger.debug(
                    "Cache expired for account '%s' (age=%.0fs)",
                    self._account_name,
                    age,
                )
                return None

        try:
            return MeResponse.model_validate(data)
        except pydantic.ValidationError as e:
            # Schema drift on disk is a real signal — log at WARNING so users
            # see why their cache is silently missing on every CLI invocation.
            # Then unlink the file so the next call deterministically refetches
            # rather than re-paying the parse cost.
            logger.warning(
                "Cached /me response at %s no longer matches the model "
                "(schema drift). Invalidating: %s",
                path,
                e,
            )
            path.unlink(missing_ok=True)
            return None

    def put(self, response: MeResponse) -> None:
        """Store a /me response in the cache.

        Adds ``cached_at`` metadata before writing. Creates the per-account
        directory at mode ``0o700`` if it doesn't exist; the cache file is
        written at mode ``0o600``.

        Args:
            response: MeResponse to cache.

        Example:
            ```python
            cache = MeCache(account_name="personal")
            cache.put(me_response)
            ```
        """
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        try:
            os.chmod(self._cache_dir, stat.S_IRWXU)  # 0o700
        except OSError as e:
            # Cache contains user emails / org names / project names — PII
            # that should not be world-readable. A filesystem that can't
            # enforce 0o700 is a real config issue, not a soft warning.
            raise ConfigError(
                f"Cannot enforce 0o700 on cache directory {self._cache_dir}: {e}",
                details={"path": str(self._cache_dir)},
            ) from e

        # Add cache metadata, stripping bulky fields that bloat the cache.
        # Workspace member_list and unified_member_list can be 10-30MB each
        # (preserved by extra="allow") and are not needed for project/workspace
        # discovery.
        data = response.model_dump(mode="json")
        _STRIP_FROM_WORKSPACES = {"member_list", "unified_member_list"}
        if "workspaces" in data and isinstance(data["workspaces"], dict):
            for ws_data in data["workspaces"].values():
                if isinstance(ws_data, dict):
                    for key in _STRIP_FROM_WORKSPACES:
                        ws_data.pop(key, None)
        data["cached_at"] = time.time()

        # Route through the project's atomic-write primitive so concurrent
        # writers (multiple Workspace instances in the same process, parallel
        # CLI invocations) get distinct tmp filenames keyed on pid+tid and
        # cannot collide. Mode 0o600 matches the credential-adjacent default.
        atomic_write_bytes(
            self._cache_path(),
            json.dumps(data, indent=2, default=str).encode("utf-8"),
            mode=0o600,
        )

    def invalidate(self) -> None:
        """Remove the cached /me response for this account.

        Example:
            ```python
            cache = MeCache(account_name="personal")
            cache.invalidate()
            ```
        """
        self._cache_path().unlink(missing_ok=True)


class MeService:
    """Orchestration service for /me API calls with caching.

    Wraps ``MixpanelAPIClient.me()`` with a ``MeCache`` layer and
    provides convenience methods for project and workspace discovery.

    Args:
        api_client: The API client for making /me requests.
        cache: Disk-based cache for /me responses.
        region: Data residency region (us, eu, in).
        account_type: Optional :data:`AccountType` discriminator. When
            set to ``"service_account"``, a 403 from ``/me`` is
            rendered as the 043 error catalog E-10 message (which
            names the ``user_details`` scope and references Mixpanel
            Settings → Service Accounts). When ``None``, the generic
            042 ``"lacks /me permission"`` message is used.

    Example:
        ```python
        svc = MeService(api_client, MeCache(account_name="personal"), "us")
        me = svc.fetch()
        projects = svc.list_projects()
        ```
    """

    def __init__(
        self,
        api_client: MixpanelAPIClient,
        cache: MeCache,
        region: str,
        account_type: AccountType | None = None,
    ) -> None:
        """Initialize MeService.

        Args:
            api_client: The API client for making /me requests.
            cache: Disk-based cache for /me responses.
            region: Data residency region (us, eu, in).
            account_type: Optional account-type discriminator used to
                pick the right 403 → ConfigError wording. See class
                docstring for the SA-specific behavior. Kept narrowed
                to the literal so a typo at the call site fails mypy
                rather than silently falling through to the generic
                403 message.
        """
        self._api_client = api_client
        self._cache = cache
        self._region = region
        self._account_type = account_type
        self._cached_response: MeResponse | None = None

    def peek(self) -> MeResponse | None:
        """Return the cached /me response without triggering a network call.

        Checks the in-memory cache first, then the on-disk cache.
        Returns ``None`` if neither is available — does NOT call the
        API, even if the cache is empty or expired. Used by callers
        that want best-effort enrichment without giving up the
        single-round-trip property of an unrelated request (e.g.,
        ``Workspace.get_business_context_chain()``).

        Returns:
            Cached MeResponse or None if both caches are empty.

        Example:
            ```python
            svc = MeService(api_client, cache, "us")
            me = svc.peek()
            org_id = me.organizations["100"].id if me else None
            ```
        """
        if self._cached_response is not None:
            return self._cached_response
        cached = self._cache.get()
        if cached is not None:
            self._cached_response = cached
        return cached

    def fetch(self, *, force_refresh: bool = False) -> MeResponse:
        """Fetch the /me response, using cache when available.

        Checks the in-memory cache first, then disk cache, then calls
        the API. Results are stored in both memory and disk caches.

        If the API returns 401 or 403, raises ``ConfigError`` indicating
        the credentials lack permission for /me discovery.

        Args:
            force_refresh: If True, bypass all caches and call the API.

        Returns:
            The /me response (from cache or API).

        Raises:
            ConfigError: If the API returns 401/403, indicating the
                credentials lack permission for /me discovery.

        Example:
            ```python
            svc = MeService(api_client, cache, "us")
            me = svc.fetch()
            print(me.user_email)

            me2 = svc.fetch(force_refresh=True)  # bypasses cache
            ```
        """
        # Check in-memory cache first
        if not force_refresh and self._cached_response is not None:
            return self._cached_response

        # Check disk cache
        if not force_refresh:
            cached = self._cache.get()
            if cached is not None:
                self._cached_response = cached
                return cached

        # Call API. Distinguish 401 (re-login fix) from 403 (need /me scope)
        # so the user gets the actionable next step, not a generic message.
        account_name = self._cache._account_name  # noqa: SLF001
        try:
            raw = self._api_client.me()
        except AuthenticationError as exc:
            raise ConfigError(
                f"Credentials for account '{account_name}' are invalid (401). "
                f"Run `mp account test {account_name}` to confirm; if it's an "
                f"oauth_browser account, run `mp account login {account_name}`.",
                details={"status_code": 401, "account_name": account_name},
            ) from exc
        except QueryError as exc:
            if exc.status_code == 403:
                if self._account_type == "service_account":
                    # Error catalog E-10 — wording locked by
                    # tests/unit/test_me.py and the cli snapshot tests.
                    message = (
                        f"Service account '{account_name}' is missing the "
                        f"`user_details` scope.\n\n"
                        f"Re-mint the SA in Mixpanel Settings → Service "
                        f"Accounts with that scope checked,\n"
                        f"or pass --project ID explicitly to skip the /me "
                        f"lookup."
                    )
                else:
                    message = (
                        f"Account '{account_name}' lacks /me permission "
                        f"(403). Specify --project explicitly, or use an "
                        f"account whose credentials have /me scope."
                    )
                raise ConfigError(
                    message,
                    details={"status_code": 403, "account_name": account_name},
                ) from exc
            raise

        response = MeResponse.model_validate(raw)

        # Store in caches
        self._cache.put(response)
        self._cached_response = response

        return response

    def list_projects(self) -> list[tuple[str, MeProjectInfo]]:
        """List all accessible projects from the cached /me response.

        Calls ``fetch()`` if no cached response is available.

        Returns:
            List of ``(project_id, MeProjectInfo)`` tuples, sorted by
            project name.

        Example:
            ```python
            svc = MeService(api_client, cache, "us")
            for pid, info in svc.list_projects():
                print(f"{pid}: {info.name}")
            ```
        """
        me = self.fetch()
        items = list(me.projects.items())
        items.sort(key=lambda x: x[1].name.lower())
        return items

    def find_project(self, project_id: str) -> MeProjectInfo | None:
        """Find a specific project by ID from the cached /me response.

        Calls ``fetch()`` if no cached response is available.

        Args:
            project_id: The project ID to search for.

        Returns:
            ``MeProjectInfo`` if found, ``None`` otherwise.

        Example:
            ```python
            svc = MeService(api_client, cache, "us")
            info = svc.find_project("3713224")
            if info:
                print(info.name)
            ```
        """
        me = self.fetch()
        return me.projects.get(project_id)

    def list_workspaces(self, project_id: str | None = None) -> list[MeWorkspaceInfo]:
        """List workspaces, optionally filtered by project ID.

        Calls ``fetch()`` if no cached response is available.

        Args:
            project_id: If provided, only return workspaces for this project.
                If None, returns all workspaces.

        Returns:
            List of ``MeWorkspaceInfo`` objects, sorted by name.

        Example:
            ```python
            svc = MeService(api_client, cache, "us")
            for ws in svc.list_workspaces(project_id="3713224"):
                print(f"{ws.id}: {ws.name}")
            ```
        """
        me = self.fetch()
        workspaces = list(me.workspaces.values())

        if project_id is not None:
            try:
                pid_int = int(project_id)
            except ValueError:
                raise ConfigError(
                    f"Project ID must be numeric, got: '{project_id}'",
                    details={"project_id": project_id},
                ) from None
            workspaces = [ws for ws in workspaces if ws.project_id == pid_int]

        workspaces.sort(key=lambda ws: ws.name.lower())
        return workspaces

    def find_default_workspace(self, project_id: str) -> MeWorkspaceInfo | None:
        """Find the default workspace for a project.

        Searches through workspaces with ``is_default=True`` for the given
        project. If no explicit default is found, returns ``None``.

        Args:
            project_id: The project ID to find the default workspace for.

        Returns:
            ``MeWorkspaceInfo`` for the default workspace, or ``None``
            if no default workspace exists.

        Example:
            ```python
            svc = MeService(api_client, cache, "us")
            default_ws = svc.find_default_workspace("3713224")
            if default_ws:
                print(f"Default: {default_ws.name} (id={default_ws.id})")
            ```
        """
        workspaces = self.list_workspaces(project_id=project_id)
        for ws in workspaces:
            if ws.is_default is True:
                return ws
        return None
