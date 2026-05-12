"""Property-based tests for ``Session.replace`` (T009).

Covers:
- ``replace(account=A)`` → new Session with ``account==A`` and other axes preserved.
- ``replace(workspace=None)`` → workspace cleared.
- Omitting an axis preserves the existing value (sentinel semantics for
  workspace and headers).
- Round-trip serialize/deserialize preserves equality.

Reference: specs/042-auth-architecture-redesign/data-model.md §4.
"""

from __future__ import annotations

from hypothesis import given
from hypothesis import strategies as st
from pydantic import SecretStr, TypeAdapter

from mixpanel_headless._internal.auth.account import (
    Account,
    OAuthBrowserAccount,
    OAuthTokenAccount,
    Region,
    ServiceAccount,
)
from mixpanel_headless._internal.auth.session import (
    Project,
    Session,
    WorkspaceRef,
)

_NAME_ALPHABET = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-"
account_names = st.text(alphabet=_NAME_ALPHABET, min_size=1, max_size=64)
regions: st.SearchStrategy[Region] = st.sampled_from(["us", "eu", "in"])
project_ids = st.from_regex(r"^[1-9][0-9]{0,9}$", fullmatch=True)
workspace_ids = st.integers(min_value=1, max_value=2**31 - 1)
non_empty_text = st.text(min_size=1, max_size=64)


@st.composite
def service_accounts(draw: st.DrawFn) -> ServiceAccount:
    """Generate ServiceAccount values."""
    return ServiceAccount(
        name=draw(account_names),
        region=draw(regions),
        username=draw(non_empty_text),
        secret=SecretStr(draw(non_empty_text)),
    )


@st.composite
def oauth_browser_accounts(draw: st.DrawFn) -> OAuthBrowserAccount:
    """Generate OAuthBrowserAccount values."""
    return OAuthBrowserAccount(name=draw(account_names), region=draw(regions))


@st.composite
def oauth_token_accounts(draw: st.DrawFn) -> OAuthTokenAccount:
    """Generate OAuthTokenAccount values (inline token only — keep simple)."""
    return OAuthTokenAccount(
        name=draw(account_names),
        region=draw(regions),
        token=SecretStr(draw(non_empty_text)),
    )


accounts: st.SearchStrategy[Account] = st.one_of(
    service_accounts(), oauth_browser_accounts(), oauth_token_accounts()
)


@st.composite
def projects(draw: st.DrawFn) -> Project:
    """Generate Project values."""
    return Project(id=draw(project_ids))


@st.composite
def workspaces_or_none(draw: st.DrawFn) -> WorkspaceRef | None:
    """Generate a WorkspaceRef or None."""
    if draw(st.booleans()):
        return WorkspaceRef(id=draw(workspace_ids))
    return None


@st.composite
def sessions(draw: st.DrawFn) -> Session:
    """Generate Session values."""
    return Session(
        account=draw(accounts),
        project=draw(projects()),
        workspace=draw(workspaces_or_none()),
    )


@given(sessions(), accounts)
def test_replace_account_preserves_other_axes(s: Session, new_account: Account) -> None:
    """Account-only swap preserves project and workspace."""
    s2 = s.replace(account=new_account)
    assert s2.account == new_account
    assert s2.project == s.project
    assert s2.workspace == s.workspace


@given(sessions(), projects())
def test_replace_project_preserves_other_axes(s: Session, new_project: Project) -> None:
    """Project-only swap preserves account and workspace."""
    s2 = s.replace(project=new_project)
    assert s2.project == new_project
    assert s2.account == s.account
    assert s2.workspace == s.workspace


@given(sessions(), workspace_ids)
def test_replace_workspace_preserves_other_axes(s: Session, ws_id: int) -> None:
    """Workspace-only swap preserves account and project."""
    new_workspace = WorkspaceRef(id=ws_id)
    s2 = s.replace(workspace=new_workspace)
    assert s2.workspace == new_workspace
    assert s2.account == s.account
    assert s2.project == s.project


@given(sessions())
def test_replace_workspace_to_none_clears(s: Session) -> None:
    """Explicit ``workspace=None`` clears the workspace."""
    s2 = s.replace(workspace=None)
    assert s2.workspace is None


@given(sessions())
def test_replace_omitting_workspace_preserves(s: Session) -> None:
    """Omitting workspace= preserves the existing workspace (sentinel)."""
    s2 = s.replace()
    assert s2.workspace == s.workspace


@given(sessions())
def test_replace_returns_new_object(s: Session) -> None:
    """``replace`` returns a new Session value with the same data."""
    s2 = s.replace()
    assert s2 is not s
    assert s2 == s


@given(sessions())
def test_replace_omitting_axes_preserves_all(s: Session) -> None:
    """``replace()`` with no args preserves all axes."""
    s2 = s.replace()
    assert s2.account == s.account
    assert s2.project == s.project
    assert s2.workspace == s.workspace
    assert s2.headers == s.headers


@given(sessions())
def test_session_typeadapter_roundtrip_preserves_equality(s: Session) -> None:
    """``model_dump`` → ``TypeAdapter.validate_python`` reconstructs an equal Session."""
    adapter: TypeAdapter[Session] = TypeAdapter(Session)
    raw = s.model_dump()
    rebuilt = adapter.validate_python(raw)
    assert rebuilt.account == s.account
    assert rebuilt.project == s.project
    assert rebuilt.workspace == s.workspace


@given(sessions())
def test_session_auth_header_format(s: Session) -> None:
    """``Session.auth_header`` always returns a ``Basic ...`` or ``Bearer ...`` string.

    The exact prefix depends on the account variant:
    - ``ServiceAccount`` → ``Basic <base64>``
    - ``OAuthBrowserAccount`` / ``OAuthTokenAccount`` → ``Bearer <token>``

    A fake :class:`TokenResolver` is supplied so the OAuth variants don't
    need real on-disk tokens.
    """
    from mixpanel_headless._internal.auth.account import (
        OAuthTokenAccount as _OAuthTokenAccount,
    )
    from mixpanel_headless._internal.auth.account import (
        TokenResolver as _TokenResolver,
    )

    class _FakeResolver(_TokenResolver):
        """Always returns the same opaque token; never reads disk."""

        def get_browser_token(self, name: str, region: str) -> str:
            return "fake-browser-token"

        def get_static_token(self, account: _OAuthTokenAccount) -> str:
            return "fake-static-token"

    header = s.auth_header(token_resolver=_FakeResolver())
    if s.account.type == "service_account":
        assert header.startswith("Basic ")
    else:
        assert header.startswith("Bearer ")
    # Whichever prefix, the value after the space is non-empty.
    prefix, _, value = header.partition(" ")
    assert prefix in {"Basic", "Bearer"}
    assert value
