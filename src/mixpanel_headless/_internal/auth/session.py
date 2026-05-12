"""Session, Project, and WorkspaceRef value types.

A :class:`Session` is the in-memory representation of "who am I and what
am I working on" — an ``Account`` plus a ``Project`` and an optional
``WorkspaceRef``. Frozen and immutable; switching axes uses
:meth:`Session.replace`.

The naming distinction matters: :class:`WorkspaceRef` is the data type
held inside a Session, while ``mixpanel_headless.Workspace`` (in the public
API) is the facade class. Renaming avoids the collision.

Reference: ``specs/042-auth-architecture-redesign/data-model.md`` §3, §4, §5.
"""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType
from typing import Annotated, Any

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_serializer,
    model_validator,
)

from mixpanel_headless._internal.auth.account import (
    Account,
    AccountName,
    ProjectId,
    Region,
    TokenResolver,
    WorkspaceId,
)


class Project(BaseModel):
    """Mixpanel project reference.

    Project IDs come from the Mixpanel API as numeric strings. ``timezone``
    and ``organization_id`` are populated when the resolver has access to
    a ``/me`` response; both are optional.
    """

    model_config = ConfigDict(frozen=True)

    id: Annotated[ProjectId, Field(min_length=1, pattern=r"^\d+$")]
    """Numeric project ID (Mixpanel's wire format is a digit string)."""

    name: str | None = None
    """Display name from ``/me``, when known."""

    organization_id: int | None = None
    """Owning organization ID from ``/me``, when known."""

    timezone: str | None = None
    """Project timezone (e.g. ``"US/Pacific"``) from ``/me``, when known."""


class WorkspaceRef(BaseModel):
    """Mixpanel workspace reference (cohort/dashboard scoping unit).

    The data model is named ``WorkspaceRef`` to avoid colliding with the
    public ``Workspace`` facade class. Public re-export keeps the
    ``WorkspaceRef`` name.

    The optional ``project_id`` lets a :class:`Session` cross-check that the
    workspace actually belongs to the bound project — every workspace lives
    inside exactly one project, and routing a workspace ID to the wrong
    project returns 400/404 deep inside the API call rather than at session
    construction. When populated (typically from a ``/me`` enumeration), the
    session-level model_validator raises :class:`ValueError` on mismatch
    instead of letting the bug surface as an HTTP error mid-query.
    """

    model_config = ConfigDict(frozen=True)

    id: Annotated[WorkspaceId, Field(gt=0)]
    """Positive integer workspace ID assigned by Mixpanel."""

    name: str | None = None
    """Display name from ``/me`` or ``/projects/{pid}/workspaces/public``."""

    is_default: bool | None = None
    """Whether this is the project's default workspace, when known."""

    project_id: ProjectId | None = None
    """Owning project ID, when known.

    Populated by ``/me`` enumeration paths so :class:`Session` can verify
    project ↔ workspace coupling. Left ``None`` when the workspace was
    constructed from a bare ID (e.g. ``MP_WORKSPACE_ID=N``) — in that
    case the cross-check degrades to "trust the caller" rather than raising
    a spurious mismatch error."""


class _SentinelType:
    """Singleton type used as a default marker in :meth:`Session.replace`.

    A sentinel is required for fields where ``None`` is a valid replacement
    value. Currently used for ``workspace`` (``None`` clears, omission
    preserves) and ``headers`` (``{}`` clears, omission preserves).
    """

    _instance: _SentinelType | None = None

    def __new__(cls) -> _SentinelType:
        """Return the singleton instance."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __repr__(self) -> str:
        """Return a human-readable marker for debugging output."""
        return "<UNSET>"


_SENTINEL = _SentinelType()


class Session(BaseModel):
    """Immutable in-memory tuple of (Account, Project, optional WorkspaceRef).

    Holds the resolved auth/scope state for a single chain of API calls.
    Switching to a different account, project, or workspace produces a new
    Session via :meth:`replace`; the original is never mutated.

    Workspace is optional: a session with ``workspace=None`` lazy-resolves
    on the first workspace-scoped API call (per FR-025).
    """

    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    account: Account
    """Resolved account (one of the three discriminated variants)."""

    project: Project
    """Resolved Mixpanel project."""

    workspace: WorkspaceRef | None = None
    """Resolved workspace; ``None`` triggers lazy resolution on first use."""

    headers: Mapping[str, str] = Field(default_factory=dict)
    """Custom HTTP headers attached at resolution time.

    Populated from ``[settings].custom_header`` and/or ``bridge.headers``.
    Never read from ``os.environ`` after Session construction (per FR-014).

    Wrapped in :class:`types.MappingProxyType` after validation, so any
    in-place mutation (``session.headers["X"] = "Y"``) raises
    :class:`TypeError` instead of silently sharing state across
    sessions. Consumers that need a mutable copy should use
    ``dict(session.headers)``.
    """

    @model_validator(mode="after")
    def _check_workspace_project_coupling(self) -> Session:
        """Reject sessions that bind a workspace to the wrong project.

        Every Mixpanel workspace lives inside exactly one project. When the
        ``WorkspaceRef`` carries a ``project_id`` (populated by ``/me``
        enumeration), it MUST match the bound project's ID — otherwise the
        API call would surface a 400/404 deep in the request path with no
        useful context. Raising here keeps the failure mode at session
        construction with a clear message.

        Workspaces constructed from a bare ID (no ``project_id``) are
        accepted — there is nothing to verify against, and the API will
        still catch the mismatch at request time.

        Returns:
            ``self`` unchanged.

        Raises:
            ValueError: ``workspace.project_id`` is set and does not equal
                ``project.id``.
        """
        if (
            self.workspace is not None
            and self.workspace.project_id is not None
            and self.workspace.project_id != self.project.id
        ):
            raise ValueError(
                f"Workspace {self.workspace.id} belongs to project "
                f"{self.workspace.project_id!r}, not {self.project.id!r}. "
                f"Re-resolve the workspace under the correct project."
            )
        return self

    @model_validator(mode="after")
    def _freeze_headers(self) -> Session:
        """Wrap the headers dict in :class:`MappingProxyType` post-validation.

        Pydantic's ``frozen=True`` only blocks attribute reassignment — it
        does not freeze container values, so a plain ``dict`` would still
        be mutable through ``session.headers["X"] = "Y"``. Wrapping in a
        read-only proxy makes any mutation raise ``TypeError`` at runtime.

        Returns:
            ``self`` (with ``headers`` replaced by a frozen proxy if needed).
        """
        if not isinstance(self.headers, MappingProxyType):
            object.__setattr__(self, "headers", MappingProxyType(dict(self.headers)))
        return self

    @field_serializer("headers")
    def _serialize_headers(self, value: Mapping[str, str]) -> dict[str, str]:
        """Serialize the headers proxy as a plain dict.

        Pydantic's default serializer would emit a Pydantic warning because
        ``MappingProxyType`` is not ``dict``; this serializer projects back
        to a fresh dict so ``model_dump`` / ``model_dump_json`` produce the
        expected JSON-compatible shape with no warnings.

        Args:
            value: The (frozen) headers mapping.

        Returns:
            A fresh ``dict`` snapshot with the same keys and values.
        """
        return dict(value)

    @property
    def project_id(self) -> str:
        """Return the project's numeric string ID.

        Returns:
            ``self.project.id``.
        """
        return self.project.id

    @property
    def workspace_id(self) -> int | None:
        """Return the workspace ID if set, else ``None``.

        Returns:
            ``self.workspace.id`` or ``None``.
        """
        return self.workspace.id if self.workspace is not None else None

    @property
    def region(self) -> Region:
        """Return the account's region.

        Returns:
            ``self.account.region``.
        """
        return self.account.region

    def auth_header(self, *, token_resolver: TokenResolver | None) -> str:
        """Return the ``Authorization`` header for HTTP requests.

        Args:
            token_resolver: Required for OAuth accounts; ignored for
                ``ServiceAccount``.

        Returns:
            The header value (``Basic ...`` or ``Bearer ...``).
        """
        # Only OAuth variants need a resolver; type-narrowed by the discriminator.
        if self.account.type == "service_account":
            return self.account.auth_header(token_resolver=token_resolver)
        if token_resolver is None:
            raise TypeError(
                "TokenResolver is required to compute auth_header for OAuth accounts"
            )
        return self.account.auth_header(token_resolver=token_resolver)

    def replace(
        self,
        *,
        account: Account | None = None,
        project: Project | None = None,
        workspace: WorkspaceRef | None | _SentinelType = _SENTINEL,
        headers: Mapping[str, str] | _SentinelType = _SENTINEL,
    ) -> Session:
        """Return a new Session with the supplied axes swapped in.

        Workspace and headers use a sentinel because ``None`` (resp. ``{}``)
        is a valid replacement value, semantically distinct from "do not
        touch this axis".

        Args:
            account: Replacement account; omitted preserves the current value.
            project: Replacement project; omitted preserves the current value.
            workspace: Replacement workspace; ``None`` clears the workspace
                (re-triggering lazy resolution); omitting the kwarg preserves
                the current value.
            headers: Replacement headers map; ``{}`` clears all custom headers;
                omitting the kwarg preserves the current value.

        Returns:
            A new :class:`Session` instance; the original is unchanged.
        """
        update: dict[str, Any] = {}
        if account is not None:
            update["account"] = account
        if project is not None:
            update["project"] = project
        if workspace is not _SENTINEL:
            update["workspace"] = workspace
        if headers is not _SENTINEL:
            update["headers"] = headers
        return self.model_copy(update=update)


class ActiveSession(BaseModel):
    """Persisted shape of the ``[active]`` block in ``~/.mp/config.toml``.

    Only ``account`` and ``workspace`` live in ``[active]``. Project lives
    on the account itself as ``Account.default_project`` — switching
    accounts implicitly switches projects. Unknown keys (including
    ``project``) are rejected by ``extra="forbid"``.

    Both fields are optional — environment variables or per-command flags
    can supply each one independently.
    """

    model_config = ConfigDict(extra="forbid")

    account: AccountName | None = None
    """Local config name of the active account (must reference ``[accounts.NAME]``)."""

    workspace: WorkspaceId | None = None
    """Active workspace ID (positive int) or ``None`` for lazy resolution."""


__all__ = [
    "ActiveSession",
    "Project",
    "Session",
    "WorkspaceRef",
]
