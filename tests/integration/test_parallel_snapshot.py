"""Parallel snapshot iteration test (T079, US7).

Verifies that ``Session.replace(...)`` produces independent immutable
sessions safe to dispatch across a ``ThreadPoolExecutor`` — each worker
sees its own ``Workspace`` and no thread mutates another's session.

This is the snapshot-mode flow from US7's "Independent Test":
``ws.session.replace(project=p)`` returns a NEW Session; the original is
unchanged. Multiple workers can therefore hold their own session refs
without observable interference.

Reference: specs/042-auth-architecture-redesign/spec.md US7 / FR-058.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from pydantic import SecretStr

from mixpanel_headless._internal.auth.account import ServiceAccount
from mixpanel_headless._internal.auth.session import Project, Session, WorkspaceRef


def _base_session() -> Session:
    """Return a baseline Session for snapshot exploration."""
    return Session(
        account=ServiceAccount(
            name="team",
            region="us",
            username="sa",
            secret=SecretStr("s"),
        ),
        project=Project(id="100"),
    )


@pytest.fixture(autouse=True)
def _isolated_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Hermetic ``$HOME`` so the test never touches real config."""
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("MP_CONFIG_PATH", str(tmp_path / ".mp" / "config.toml"))


class TestParallelSnapshot:
    """``Session.replace`` snapshots are independent across threads."""

    def test_replace_returns_new_session_preserves_original(self) -> None:
        """``s.replace(project=...)`` returns a new Session; ``s`` is unchanged."""
        s = _base_session()
        s2 = s.replace(project=Project(id="200"))
        assert s.project.id == "100"
        assert s2.project.id == "200"
        # Original session object identity stays intact.
        assert s is not s2

    def test_replace_preserves_unchanged_axes_by_identity(self) -> None:
        """Axes not touched by ``replace`` are shared by Python identity.

        FR-058: snapshot mode should not deep-copy the account / workspace
        objects unnecessarily. Pydantic ``model_copy`` keeps unchanged
        fields by reference.
        """
        s = _base_session()
        s2 = s.replace(project=Project(id="200"))
        assert s2.account is s.account

    def test_parallel_threads_get_independent_sessions(self) -> None:
        """Dispatching N snapshots through ``ThreadPoolExecutor`` is race-free."""
        base = _base_session()
        project_ids = [str(i) for i in range(100, 110)]
        snapshots = [base.replace(project=Project(id=pid)) for pid in project_ids]

        def _read_project(s: Session) -> str:
            return s.project.id

        with ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(_read_project, snapshots))

        assert results == project_ids
        # The original is still unchanged after parallel reads.
        assert base.project.id == "100"

    def test_workspace_replace_clears_distinct_from_preserve(self) -> None:
        """``replace(workspace=None)`` clears; omitting the kwarg preserves."""
        s = _base_session().replace(workspace=WorkspaceRef(id=999))
        cleared = s.replace(workspace=None)
        preserved = s.replace(project=Project(id="200"))
        assert cleared.workspace is None
        assert preserved.workspace is not None
        assert preserved.workspace.id == 999
