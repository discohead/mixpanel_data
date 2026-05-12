"""Integration tests for lazy workspace resolution (T036, R6).

Three layers:
- Unit (mocked) — verifies lazy resolve happens on first workspace-scoped call.
- Contract (recorded) — locks the response shape.
- Live (opt-in via MP_LIVE_TESTS=1) — smoke test against the live API.

For Phase 4 we focus on the unit layer; the contract and live layers
are stubbed out as future work tied to the `contract` / `live` markers.

Reference: specs/042-auth-architecture-redesign/research.md R6.
"""

from __future__ import annotations

import os

import httpx
import pytest
from pydantic import SecretStr

from mixpanel_headless._internal.api_client import MixpanelAPIClient
from mixpanel_headless._internal.auth.account import ServiceAccount
from mixpanel_headless._internal.auth.session import Project, Session, WorkspaceRef


@pytest.fixture
def session_no_workspace() -> Session:
    """Return a Session with workspace=None (lazy)."""
    return Session(
        account=ServiceAccount(
            name="team",
            region="us",
            username="u",
            secret=SecretStr("s"),
        ),
        project=Project(id="3713224"),
        workspace=None,
    )


class TestLazyResolveUnit:
    """Layer 1: workspace lazy-resolves on first workspace-scoped call."""

    def test_workspace_initially_none(self, session_no_workspace: Session) -> None:
        """Session with workspace=None → ``client.session.workspace`` is None."""
        client = MixpanelAPIClient(session=session_no_workspace)
        assert client.session.workspace is None

    def test_resolve_workspace_returns_default(
        self, session_no_workspace: Session
    ) -> None:
        """``client.resolve_workspace()`` returns the default workspace.

        Mocks the ``/api/app/projects/{pid}/workspaces/public`` response and
        verifies the client picks the ``is_default=True`` workspace.
        """

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                json={
                    "results": [{"id": 9999, "name": "Default", "is_default": True}],
                    "status": "ok",
                },
            )

        transport = httpx.MockTransport(handler)
        client = MixpanelAPIClient(session=session_no_workspace, _transport=transport)
        ws = client.resolve_workspace()
        assert ws == WorkspaceRef(id=9999, name="Default", is_default=True)

    def test_resolve_workspace_caches_per_session_lifetime(
        self, session_no_workspace: Session
    ) -> None:
        """``resolve_workspace`` caches per session lifetime — only one HTTP call."""
        call_count = {"n": 0}

        def handler(request: httpx.Request) -> httpx.Response:
            call_count["n"] += 1
            return httpx.Response(
                200,
                json={
                    "results": [{"id": 9999, "name": "Default", "is_default": True}],
                    "status": "ok",
                },
            )

        transport = httpx.MockTransport(handler)
        client = MixpanelAPIClient(session=session_no_workspace, _transport=transport)
        client.resolve_workspace()
        client.resolve_workspace()
        assert call_count["n"] == 1


@pytest.mark.contract
def test_lazy_resolve_against_recorded_response_layered_marker() -> None:
    """Contract layer placeholder — to be filled in with recorded response."""
    pytest.skip("Contract layer recording deferred to Phase 8 release prep.")


@pytest.mark.live
def test_lazy_resolve_against_live_api() -> None:
    """Live layer placeholder — opt-in via MP_LIVE_TESTS=1."""
    if os.environ.get("MP_LIVE_TESTS") != "1":
        pytest.skip("Set MP_LIVE_TESTS=1 to run live workspace lazy-resolve.")
    pytest.skip("Live layer wiring deferred to Phase 4+ alpha-tester validation.")
