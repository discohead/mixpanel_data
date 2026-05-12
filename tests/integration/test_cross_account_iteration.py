"""Cross-account iteration test (T078, US7).

Loops over multiple Workspaces backed by different accounts and verifies:
- the auth header rebuilds per account
- the underlying ``httpx.Client`` survives all switches via ``ws.use(account=)``
- in-session project state is cleared on account swap (FR-033)

Reference: specs/042-auth-architecture-redesign/spec.md US7 / FR-033.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx
import pytest
from pydantic import SecretStr

from mixpanel_headless._internal.api_client import MixpanelAPIClient
from mixpanel_headless._internal.auth.account import (
    ServiceAccount,
)
from mixpanel_headless._internal.auth.session import Project, Session
from mixpanel_headless._internal.config import ConfigManager
from mixpanel_headless.workspace import Workspace

_ME_PAYLOAD = {
    "results": {
        "id": 42,
        "email": "owner@example.com",
        "organizations": {
            "1": {"id": 1, "name": "Acme", "role": "owner", "permissions": ["all"]}
        },
        "projects": {
            "100": {"name": "Alpha", "organization_id": 1, "timezone": "US/Pacific"},
            "200": {"name": "Bravo", "organization_id": 1, "timezone": "US/Pacific"},
            "300": {"name": "Charlie", "organization_id": 1, "timezone": "US/Pacific"},
        },
        "workspaces": {},
    }
}


def _seed_browser_tokens(home: Path, name: str) -> None:
    """Write a fake on-disk tokens.json for an oauth_browser account."""
    account_dir = home / ".mp" / "accounts" / name
    account_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    tokens_path = account_dir / "tokens.json"
    expires_at = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
    payload = {
        "access_token": f"tok-{name}",
        "refresh_token": "ref",
        "expires_at": expires_at,
        "scope": "read",
        "token_type": "Bearer",
    }
    tokens_path.write_text(json.dumps(payload), encoding="utf-8")
    tokens_path.chmod(0o600)


@pytest.fixture(autouse=True)
def _isolated_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    """Hermetic ``$HOME`` + ``MP_CONFIG_PATH`` so the test never touches real config."""
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("MP_CONFIG_PATH", str(tmp_path / ".mp" / "config.toml"))
    monkeypatch.setenv("CI_TOKEN", "ci-bearer")
    yield tmp_path


@pytest.fixture
def populated_config(_isolated_home: Path) -> Path:
    """Three accounts (one of each type) with a default project pinned."""
    cm = ConfigManager()
    cm.add_account(
        "team",
        type="service_account",
        region="us",
        default_project="100",
        username="sa",
        secret=SecretStr("secret"),
    )
    cm.add_account("personal", type="oauth_browser", region="us", default_project="200")
    _seed_browser_tokens(_isolated_home, "personal")
    cm.add_account(
        "ci",
        type="oauth_token",
        region="us",
        default_project="300",
        token_env="CI_TOKEN",
    )
    return _isolated_home


@pytest.fixture
def mock_transport() -> httpx.MockTransport:
    """Mock transport that always returns a stub /me payload."""

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/api/app/me"):
            return httpx.Response(200, json=_ME_PAYLOAD)
        return httpx.Response(404, json={"error": f"unhandled {request.url.path}"})

    return httpx.MockTransport(handler)


@pytest.fixture
def workspace(
    populated_config: Path, mock_transport: httpx.MockTransport
) -> Iterator[Workspace]:
    """Construct a Workspace bound to the active account + mock transport."""
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


class TestCrossAccountIteration:
    """``ws.use(account=...)`` rebuilds auth + preserves the HTTP transport."""

    def test_iteration_preserves_http_transport(self, workspace: Workspace) -> None:
        """Connection pool survives every account swap (Research R5)."""
        api_client = workspace._api_client
        assert api_client is not None
        before = id(api_client._http)
        for name in ("personal", "ci", "team"):
            workspace.use(account=name)
            assert id(api_client._http) == before

    def test_iteration_rebuilds_auth_header_per_account(
        self, workspace: Workspace
    ) -> None:
        """Each account swap installs a new Authorization header.

        Different account types produce structurally distinct headers
        (Basic vs Bearer); the per-account header MUST refresh on swap.
        """
        api_client = workspace._api_client
        assert api_client is not None
        seen: set[str] = set()
        for name in ("team", "personal", "ci"):
            workspace.use(account=name)
            seen.add(api_client._get_auth_header())
        # Each account produced a distinct Authorization value.
        assert len(seen) == 3, f"expected 3 distinct auth headers, got {seen!r}"

    def test_account_swap_picks_up_new_default_project(
        self, workspace: Workspace
    ) -> None:
        """On account swap, the project axis re-resolves to the new account's default.

        FR-033: cross-account project access is not guaranteed; the prior
        session's project is NEVER carried forward across an account swap.
        """
        # Initial state: team / project 100
        assert workspace.session.project.id == "100"
        workspace.use(account="personal")
        # personal's default_project = "200"
        assert workspace.session.project.id == "200"
        workspace.use(account="ci")
        # ci's default_project = "300"
        assert workspace.session.project.id == "300"
