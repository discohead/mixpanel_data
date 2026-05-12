"""Cross-project iteration test (T077, US7).

Sanity-checks the SC-008 contract: looping over multiple projects via
``ws.use(project=p.id)`` is O(1) per iteration — zero re-auth, the
``/me`` cache populated by the first call is reused, and the underlying
``httpx.Client`` instance survives every switch.

Exercises the public Workspace API end-to-end with a mocked transport
so we can count exactly how many HTTP requests each iteration emits.

Reference:
    specs/042-auth-architecture-redesign/spec.md SC-008 / FR-061
    specs/042-auth-architecture-redesign/research.md R5
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterator
from pathlib import Path

import httpx
import pytest
from pydantic import SecretStr

from mixpanel_headless._internal.api_client import MixpanelAPIClient
from mixpanel_headless._internal.auth.account import ServiceAccount
from mixpanel_headless._internal.auth.session import Project, Session
from mixpanel_headless.workspace import Workspace

_ME_PAYLOAD = {
    "results": {
        "id": 42,
        "email": "owner@example.com",
        "name": "Owner",
        "organizations": {
            "1": {"id": 1, "name": "Acme", "role": "owner", "permissions": ["all"]}
        },
        "projects": {
            "100": {"name": "Alpha", "organization_id": 1, "timezone": "US/Pacific"},
            "200": {"name": "Bravo", "organization_id": 1, "timezone": "US/Pacific"},
            "300": {"name": "Charlie", "organization_id": 1, "timezone": "US/Pacific"},
        },
        "workspaces": {
            "1001": {
                "id": 1001,
                "name": "Default",
                "project_id": 100,
                "is_default": True,
            },
            "2001": {
                "id": 2001,
                "name": "Default",
                "project_id": 200,
                "is_default": True,
            },
            "3001": {
                "id": 3001,
                "name": "Default",
                "project_id": 300,
                "is_default": True,
            },
        },
    }
}


@pytest.fixture(autouse=True)
def _isolated_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Hermetic ``$HOME`` + ``MP_CONFIG_PATH`` so the test never touches real config."""
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("MP_CONFIG_PATH", str(tmp_path / ".mp" / "config.toml"))


@pytest.fixture
def request_log() -> list[httpx.Request]:
    """Return a fresh list to capture every outbound request."""
    return []


@pytest.fixture
def mock_transport(request_log: list[httpx.Request]) -> httpx.MockTransport:
    """Mock transport routing ``/me`` and event endpoints with request logging."""

    def handler(request: httpx.Request) -> httpx.Response:
        request_log.append(request)
        path = request.url.path
        if path.endswith("/api/app/me"):
            return httpx.Response(200, json=_ME_PAYLOAD)
        if path.endswith("/api/query/events/names"):
            return httpx.Response(200, json=["Login", "Signup"])
        return httpx.Response(404, json={"error": f"unhandled {path}"})

    return httpx.MockTransport(handler)


@pytest.fixture
def workspace(
    request_log: list[httpx.Request], mock_transport: httpx.MockTransport
) -> Iterator[Workspace]:
    """Construct a Workspace bound to a Session + mock transport."""
    session = Session(
        account=ServiceAccount(
            name="team",
            region="us",
            username="sa",
            secret=SecretStr("secret"),
        ),
        project=Project(id="100"),
    )
    api_client = MixpanelAPIClient(session=session, _transport=mock_transport)
    ws = Workspace(session=session, _api_client=api_client)
    try:
        yield ws
    finally:
        ws.close()


class TestCrossProjectIteration:
    """SC-008: looping over projects is O(1) per iteration."""

    def test_use_project_preserves_http_transport(self, workspace: Workspace) -> None:
        """``ws.use(project=...)`` keeps the same ``httpx.Client`` instance.

        This is the connection-pool-preservation contract from Research R5.
        ``id()`` is exact: the client object MUST be the same Python instance
        across switches so the existing TCP connection pool / keep-alive
        state survives.
        """
        api_client = workspace._api_client
        assert api_client is not None
        before = id(api_client._http)
        for project_id in ("100", "200", "300"):
            workspace.use(project=project_id)
            assert id(api_client._http) == before

    def test_use_project_does_not_rebuild_auth_header(
        self, workspace: Workspace
    ) -> None:
        """``ws.use(project=...)`` does NOT re-resolve the auth header.

        Service-account auth headers are static (Basic <base64>); they don't
        depend on the project axis. Re-encoding on every project swap would
        be pointless work.
        """
        api_client = workspace._api_client
        assert api_client is not None
        first = api_client._get_auth_header()
        for project_id in ("100", "200", "300"):
            workspace.use(project=project_id)
            assert api_client._get_auth_header() == first

    def test_iteration_over_projects_makes_one_me_call_total(
        self, workspace: Workspace, request_log: list[httpx.Request]
    ) -> None:
        """``ws.projects()`` populates the cache; the loop never re-fetches.

        Pre-populate the per-account ``/me`` cache with one explicit call,
        then iterate three projects calling ``ws.events()`` per turn. The
        only ``/me`` request observed across the entire iteration should be
        the seeding call — FR-061 (lazy cache) and SC-008 (zero re-auth).
        """
        # Seed the /me cache (one call).
        projects = workspace.projects()
        assert len(projects) == 3

        request_log.clear()  # focus the assertion on the loop body
        for project in projects:
            workspace.use(project=project.id)
            workspace.events()

        # No `/me` requests during iteration; events called exactly once per project.
        paths = Counter(r.url.path for r in request_log)
        me_paths = sum(1 for p in paths if p.endswith("/api/app/me"))
        assert me_paths == 0, f"expected zero /me calls during loop; got {dict(paths)}"
        events_paths = sum(
            count for p, count in paths.items() if p.endswith("/api/query/events/names")
        )
        assert events_paths == 3, f"expected 3 events calls; got {dict(paths)}"

    def test_use_chain_returns_self_for_fluent_calls(
        self, workspace: Workspace
    ) -> None:
        """``ws.use(project=...)`` returns ``self`` so callers can chain."""
        result = workspace.use(project="200")
        assert result is workspace
        chained = workspace.use(project="200").use(project="300")
        assert chained is workspace
