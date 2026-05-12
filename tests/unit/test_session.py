"""Unit tests for ``Session``, ``Project``, ``WorkspaceRef`` (T007).

Covers Project validation (numeric string id), WorkspaceRef validation
(positive int id), Session construction with workspace=None, the
``project_id``/``workspace_id``/``region`` properties, and ``Session.replace(...)``
sentinel semantics for each axis.

Reference: specs/042-auth-architecture-redesign/data-model.md §3, §4.
"""

from __future__ import annotations

import pytest
from pydantic import SecretStr, ValidationError

from mixpanel_headless._internal.auth.account import (
    OAuthBrowserAccount,
    OAuthTokenAccount,
    ServiceAccount,
)
from mixpanel_headless._internal.auth.session import (
    Project,
    Session,
    WorkspaceRef,
)


@pytest.fixture
def sa() -> ServiceAccount:
    """A minimal ServiceAccount for Session construction."""
    return ServiceAccount(name="team", region="us", username="u", secret=SecretStr("s"))


@pytest.fixture
def project() -> Project:
    """A minimal Project."""
    return Project(id="3713224", name="Demo")


@pytest.fixture
def workspace() -> WorkspaceRef:
    """A minimal WorkspaceRef."""
    return WorkspaceRef(id=8, name="Default")


class TestProject:
    """Construction and validation of ``Project``."""

    def test_construction(self) -> None:
        """Construct with id only is valid."""
        p = Project(id="3713224")
        assert p.id == "3713224"
        assert p.name is None
        assert p.organization_id is None

    def test_construction_full(self) -> None:
        """Construct with all optional fields."""
        p = Project(id="3713224", name="Demo", organization_id=42, timezone="UTC")
        assert p.id == "3713224"
        assert p.name == "Demo"
        assert p.organization_id == 42
        assert p.timezone == "UTC"

    def test_id_must_be_digits(self) -> None:
        """Project ID must match ``^\\d+$``."""
        with pytest.raises(ValidationError):
            Project(id="abc")

    def test_id_rejects_empty(self) -> None:
        """Empty project id is rejected."""
        with pytest.raises(ValidationError):
            Project(id="")

    def test_id_rejects_negative(self) -> None:
        """Negative-looking ids are rejected (no leading minus)."""
        with pytest.raises(ValidationError):
            Project(id="-1")

    def test_frozen(self) -> None:
        """Project is frozen — assignment raises."""
        p = Project(id="3713224")
        with pytest.raises(ValidationError):
            p.id = "999"  # type: ignore[misc, assignment]


class TestWorkspaceRef:
    """Construction and validation of ``WorkspaceRef``."""

    def test_construction(self) -> None:
        """Construct with id only."""
        w = WorkspaceRef(id=8)
        assert w.id == 8
        assert w.name is None
        assert w.is_default is None

    def test_construction_full(self) -> None:
        """Construct with all optional fields."""
        w = WorkspaceRef(id=8, name="Default", is_default=True)
        assert w.id == 8
        assert w.name == "Default"
        assert w.is_default is True

    def test_id_must_be_positive(self) -> None:
        """Workspace ID must be > 0 (PositiveInt)."""
        with pytest.raises(ValidationError):
            WorkspaceRef(id=0)
        with pytest.raises(ValidationError):
            WorkspaceRef(id=-1)

    def test_frozen(self) -> None:
        """WorkspaceRef is frozen — assignment raises."""
        w = WorkspaceRef(id=8)
        with pytest.raises(ValidationError):
            w.id = 9  # type: ignore[misc, assignment]


class TestSessionConstruction:
    """``Session`` construction and field access."""

    def test_construction_with_workspace(
        self, sa: ServiceAccount, project: Project, workspace: WorkspaceRef
    ) -> None:
        """Construct with all three axes."""
        s = Session(account=sa, project=project, workspace=workspace)
        assert s.account is sa
        assert s.project is project
        assert s.workspace is workspace

    def test_construction_workspace_none(
        self, sa: ServiceAccount, project: Project
    ) -> None:
        """Workspace is optional — None is valid (lazy-resolve later)."""
        s = Session(account=sa, project=project, workspace=None)
        assert s.workspace is None

    def test_construction_default_workspace_none(
        self, sa: ServiceAccount, project: Project
    ) -> None:
        """Workspace defaults to None when omitted."""
        s = Session(account=sa, project=project)
        assert s.workspace is None

    def test_default_headers_empty(self, sa: ServiceAccount, project: Project) -> None:
        """Headers default to an empty mapping."""
        s = Session(account=sa, project=project)
        assert dict(s.headers) == {}

    def test_frozen(self, sa: ServiceAccount, project: Project) -> None:
        """Session is frozen — assignment raises."""
        s = Session(account=sa, project=project)
        with pytest.raises(ValidationError):
            s.workspace = WorkspaceRef(id=1)  # type: ignore[misc]

    def test_headers_immutable(self, sa: ServiceAccount, project: Project) -> None:
        """``session.headers["X"] = "Y"`` raises ``TypeError``.

        Pydantic ``frozen=True`` only blocks attribute reassignment — without
        the post-validation ``MappingProxyType`` wrap a caller could still
        mutate the underlying dict and silently share state across sessions.
        """
        s = Session(
            account=sa, project=project, headers={"X-Mixpanel-Cluster": "internal-1"}
        )
        with pytest.raises(TypeError):
            s.headers["X-Mixpanel-Cluster"] = "leaked"  # type: ignore[index]
        with pytest.raises(TypeError):
            s.headers["new-header"] = "leaked"  # type: ignore[index]
        # Original value preserved.
        assert s.headers["X-Mixpanel-Cluster"] == "internal-1"

    def test_headers_input_dict_isolation(
        self, sa: ServiceAccount, project: Project
    ) -> None:
        """Mutating the dict passed at construction does not leak into the session."""
        h = {"X": "1"}
        s = Session(account=sa, project=project, headers=h)
        h["X"] = "leaked"
        h["Y"] = "added"
        assert s.headers["X"] == "1"
        assert "Y" not in s.headers


class TestSessionProperties:
    """``project_id``, ``workspace_id``, ``region`` convenience properties."""

    def test_project_id(self, sa: ServiceAccount, project: Project) -> None:
        """``project_id`` returns ``project.id``."""
        s = Session(account=sa, project=project)
        assert s.project_id == "3713224"

    def test_workspace_id_set(
        self, sa: ServiceAccount, project: Project, workspace: WorkspaceRef
    ) -> None:
        """``workspace_id`` returns ``workspace.id`` when set."""
        s = Session(account=sa, project=project, workspace=workspace)
        assert s.workspace_id == 8

    def test_workspace_id_none(self, sa: ServiceAccount, project: Project) -> None:
        """``workspace_id`` is None when workspace is None."""
        s = Session(account=sa, project=project)
        assert s.workspace_id is None

    def test_region_from_account(self, project: Project) -> None:
        """``region`` derives from ``account.region``."""
        sa = ServiceAccount(
            name="team", region="eu", username="u", secret=SecretStr("s")
        )
        s = Session(account=sa, project=project)
        assert s.region == "eu"


class TestSessionReplace:
    """``Session.replace(...)`` returns a new Session with selected axes swapped."""

    def test_replace_account(self, sa: ServiceAccount, project: Project) -> None:
        """Replace account; project and workspace preserved."""
        new_sa = ServiceAccount(
            name="other", region="us", username="u2", secret=SecretStr("s2")
        )
        s = Session(account=sa, project=project)
        s2 = s.replace(account=new_sa)
        assert s2.account is new_sa
        assert s2.project is project
        assert s2.workspace is None
        assert s.account is sa  # original unchanged

    def test_replace_project(
        self, sa: ServiceAccount, project: Project, workspace: WorkspaceRef
    ) -> None:
        """Replace project; account and workspace preserved."""
        new_p = Project(id="9999")
        s = Session(account=sa, project=project, workspace=workspace)
        s2 = s.replace(project=new_p)
        assert s2.project is new_p
        assert s2.account is sa
        assert s2.workspace is workspace

    def test_replace_workspace_to_other(
        self, sa: ServiceAccount, project: Project, workspace: WorkspaceRef
    ) -> None:
        """Replace workspace with another WorkspaceRef."""
        new_w = WorkspaceRef(id=100)
        s = Session(account=sa, project=project, workspace=workspace)
        s2 = s.replace(workspace=new_w)
        assert s2.workspace is new_w

    def test_replace_workspace_to_none_clears(
        self, sa: ServiceAccount, project: Project, workspace: WorkspaceRef
    ) -> None:
        """Explicit ``workspace=None`` clears the workspace (re-trigger lazy resolve)."""
        s = Session(account=sa, project=project, workspace=workspace)
        s2 = s.replace(workspace=None)
        assert s2.workspace is None

    def test_replace_workspace_omitted_preserves(
        self, sa: ServiceAccount, project: Project, workspace: WorkspaceRef
    ) -> None:
        """Omitting workspace= preserves the existing workspace (sentinel semantics)."""
        s = Session(account=sa, project=project, workspace=workspace)
        new_p = Project(id="9999")
        s2 = s.replace(project=new_p)
        assert s2.workspace is workspace

    def test_replace_returns_new_object(
        self, sa: ServiceAccount, project: Project
    ) -> None:
        """``replace`` produces a new Session — original unmodified."""
        s = Session(account=sa, project=project)
        s2 = s.replace()
        assert s2 is not s
        assert s2 == s

    def test_replace_account_unchanged_axes_preserve_identity(
        self, sa: ServiceAccount, project: Project
    ) -> None:
        """Account-only swap preserves project ``is`` identity (per US7 invariant)."""
        new_sa = ServiceAccount(
            name="other", region="us", username="u2", secret=SecretStr("s2")
        )
        s = Session(account=sa, project=project)
        s2 = s.replace(account=new_sa)
        assert s2.project is s.project

    def test_replace_headers_to_empty_clears(
        self, sa: ServiceAccount, project: Project
    ) -> None:
        """Explicit ``headers={}`` clears all custom headers (sentinel semantics)."""
        s = Session(account=sa, project=project, headers={"X-Foo": "bar"})
        s2 = s.replace(headers={})
        assert s2.headers == {}

    def test_replace_headers_omitted_preserves(
        self, sa: ServiceAccount, project: Project
    ) -> None:
        """Omitting headers= preserves the existing headers."""
        s = Session(account=sa, project=project, headers={"X-Foo": "bar"})
        new_p = Project(id="9999")
        s2 = s.replace(project=new_p)
        assert s2.headers == {"X-Foo": "bar"}


class TestSessionAuthHeader:
    """``Session.auth_header`` delegates to the account."""

    def test_service_account_auth_header(
        self, sa: ServiceAccount, project: Project
    ) -> None:
        """ServiceAccount session produces a Basic auth header without resolver."""
        s = Session(account=sa, project=project)
        h = s.auth_header(token_resolver=None)
        assert h.startswith("Basic ")

    def test_browser_account_auth_header_uses_resolver(self, project: Project) -> None:
        """OAuthBrowserAccount session calls the resolver and returns Bearer."""

        class _Resolver:
            def get_browser_token(self, name: str, region: str) -> str:
                return f"tok-for-{name}-{region}"

            def get_static_token(self, account: OAuthTokenAccount) -> str:
                raise NotImplementedError

        a = OAuthBrowserAccount(name="me", region="us")
        s = Session(account=a, project=project)
        assert s.auth_header(token_resolver=_Resolver()) == "Bearer tok-for-me-us"


class TestPublicSurface:
    """Lock the ``session.__all__`` exports (Claim 8)."""

    def test_private_sentinel_not_exported(self) -> None:
        """``_SENTINEL`` and ``_SentinelType`` carry the private prefix and must
        not appear in ``__all__``.

        Re-exporting underscore-prefixed names is an antipattern: it advertises
        them as part of the supported surface while the prefix says otherwise.
        Internal callers can still import them directly by name.
        """
        from mixpanel_headless._internal.auth import session as session_mod

        assert "_SENTINEL" not in session_mod.__all__
        assert "_SentinelType" not in session_mod.__all__
