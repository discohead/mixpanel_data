"""Shared fixtures for mixpanel_headless tests."""

from __future__ import annotations

import os
import tempfile
from collections.abc import Callable, Generator
from pathlib import Path
from typing import TYPE_CHECKING

import httpx
import pytest
from hypothesis import HealthCheck, Phase, Verbosity, settings

# =============================================================================
# Hypothesis Configuration
# =============================================================================

# Register Hypothesis profiles for different environments
# All profiles suppress differing_executors health check to support mutation testing,
# which runs tests from a copied mutants/ directory
settings.register_profile(
    "default",
    max_examples=100,
    verbosity=Verbosity.normal,
    phases=[Phase.explicit, Phase.reuse, Phase.generate, Phase.target, Phase.shrink],
    suppress_health_check=[HealthCheck.differing_executors],
)

settings.register_profile(
    "ci",
    max_examples=200,
    verbosity=Verbosity.normal,
    phases=[Phase.explicit, Phase.reuse, Phase.generate, Phase.target, Phase.shrink],
    derandomize=True,  # Reproducible in CI
    suppress_health_check=[HealthCheck.differing_executors],
)

settings.register_profile(
    "dev",
    max_examples=10,
    verbosity=Verbosity.verbose,
    phases=[Phase.explicit, Phase.reuse, Phase.generate, Phase.target, Phase.shrink],
    suppress_health_check=[HealthCheck.differing_executors],
)

settings.register_profile(
    "debug",
    max_examples=10,
    verbosity=Verbosity.verbose,
    phases=[Phase.explicit, Phase.reuse, Phase.generate, Phase.target, Phase.shrink],
    report_multiple_bugs=False,
    suppress_health_check=[HealthCheck.differing_executors],
)

# Load profile from HYPOTHESIS_PROFILE env var, default to "default"
settings.load_profile(os.getenv("HYPOTHESIS_PROFILE", "default"))

if TYPE_CHECKING:
    from mixpanel_headless._internal.api_client import MixpanelAPIClient
    from mixpanel_headless._internal.auth.session import Session
    from mixpanel_headless._internal.config import ConfigManager


def make_session(
    *,
    username: str = "test_user",
    secret: str = "test_secret",
    project_id: str = "12345",
    region: str = "us",
    name: str = "test_account",
    workspace_id: int | None = None,
    oauth_token: str | None = None,
) -> Session:
    """Build a Session for tests with sensible defaults.

    Mirrors the kwarg shape of the retired ``Credentials`` test fixtures.
    Pass ``oauth_token`` to construct an ``OAuthTokenAccount``-backed Session
    instead of the default ``ServiceAccount``.

    Args:
        username: Service-account username (ignored when ``oauth_token`` is set).
        secret: Service-account secret (ignored when ``oauth_token`` is set).
        project_id: Mixpanel project ID (numeric string).
        region: Mixpanel region (``us`` / ``eu`` / ``in``).
        name: Local account name used for cache scoping.
        workspace_id: Optional workspace ID; ``None`` triggers lazy resolution.
        oauth_token: When set, build an OAuthTokenAccount with this static bearer.

    Returns:
        A frozen Session usable for ``MixpanelAPIClient(session=...)``.
    """
    from typing import cast

    from pydantic import SecretStr

    from mixpanel_headless._internal.auth.account import Region

    region_typed = cast("Region", region)

    from mixpanel_headless._internal.auth.account import (
        OAuthTokenAccount,
        ServiceAccount,
    )
    from mixpanel_headless._internal.auth.session import (
        Project,
        Session,
        WorkspaceRef,
    )

    account: OAuthTokenAccount | ServiceAccount
    if oauth_token is not None:
        account = OAuthTokenAccount(
            name=name,
            region=region_typed,
            token=SecretStr(oauth_token),
        )
    else:
        account = ServiceAccount(
            name=name,
            region=region_typed,
            username=username,
            secret=SecretStr(secret),
        )
    return Session(
        account=account,
        project=Project(id=project_id),
        workspace=WorkspaceRef(id=workspace_id) if workspace_id else None,
    )


_MP_ENV_VARS = (
    "MP_USERNAME",
    "MP_SECRET",
    "MP_PROJECT_ID",
    "MP_REGION",
    "MP_OAUTH_TOKEN",
    "MP_AUTH_FILE",
    "MP_WORKSPACE_ID",
)


@pytest.fixture(autouse=True)
def _clean_mp_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Hermetic test isolation: scrub all MP_* env vars before each test.

    Tests that depend on env-var resolution behavior must opt-in by
    re-setting the vars they need via ``monkeypatch.setenv``. Without this
    fixture, a developer who exports ``MP_OAUTH_TOKEN`` (or any service-
    account var) in their shell would silently fail credential-resolution
    tests that expect "no credentials configured".
    """
    for var in _MP_ENV_VARS:
        monkeypatch.delenv(var, raising=False)


def _real_home_mp_guard_enabled() -> bool:
    """Return whether the real-home ``~/.mp/`` guard should run this session.

    The guard is enabled in CI (where the home directory is hermetic) and
    when explicitly opted in via ``MP_TEST_GUARD_REAL_HOME=1``. On a
    developer machine, unrelated processes — another shell running ``mp``,
    a background OAuth refresh, an editor syncing dotfiles — can update
    ``~/.mp/`` mid-test-run and trip the guard for reasons unrelated to
    test-suite leakage. Defaulting to off there avoids flakes while
    keeping the safety net in CI.

    Returns:
        ``True`` when ``$CI`` is set or
        ``$MP_TEST_GUARD_REAL_HOME=1``; ``False`` otherwise.
    """
    return os.getenv("CI") is not None or os.getenv("MP_TEST_GUARD_REAL_HOME") == "1"


def _snapshot_real_mp_dir() -> dict[str, float]:
    """Snapshot mtimes of every file under the developer's real ``~/.mp/``.

    Returns:
        Mapping from absolute path string to mtime, or an empty dict
        if no real ``~/.mp/`` exists or it is unreadable.
    """
    # Resolve the developer's actual home before any monkeypatch overrides it.
    # ``Path.home()`` would fail under empty $HOME on some systems; fall back
    # to ``os.path.expanduser`` which handles that gracefully.
    real_home = Path(os.path.expanduser("~"))
    mp_dir = real_home / ".mp"
    if not mp_dir.is_dir():
        return {}
    snapshot: dict[str, float] = {}
    try:
        for path in mp_dir.rglob("*"):
            if path.is_file():
                snapshot[str(path)] = path.stat().st_mtime
    except OSError:  # pragma: no cover — permission glitch
        return {}
    return snapshot


@pytest.fixture(scope="session", autouse=True)
def _no_test_writes_to_real_home_mp(
    request: pytest.FixtureRequest,
) -> Generator[None, None, None]:
    """Fail loud if any test wrote under the developer's real ``~/.mp/``.

    Snapshots ``~/.mp/`` mtimes at session start and re-checks at session
    end. If any file changed (or new files appeared), the test that did
    it leaked outside its tmpdir — which would silently corrupt the
    developer's real config / token cache. This fixture catches the
    regression once per session rather than per-test (cheap to run).

    Only enabled in CI or when ``MP_TEST_GUARD_REAL_HOME=1`` is set
    (see :func:`_real_home_mp_guard_enabled`); on developer machines the
    guard is a no-op to avoid false positives from unrelated processes
    touching ``~/.mp/`` mid-run.

    The check is best-effort: missing or unreadable ``~/.mp/`` is
    treated as "nothing to protect" and the fixture is a no-op.
    """
    del request  # session-scoped fixtures take request for parity only
    if not _real_home_mp_guard_enabled():
        yield
        return
    before = _snapshot_real_mp_dir()
    yield
    after = _snapshot_real_mp_dir()
    changed = sorted(p for p, mtime in after.items() if before.get(p) != mtime)
    new = sorted(set(after) - set(before))
    removed = sorted(set(before) - set(after))
    if changed or new or removed:
        pytest.fail(
            "Test(s) leaked writes to the developer's real ~/.mp/.\n"
            "Each test MUST monkeypatch HOME / MP_CONFIG_PATH / "
            "MP_OAUTH_STORAGE_DIR to a tmp_path. Offenders:\n"
            f"  changed: {changed}\n"
            f"  new:     {new}\n"
            f"  removed: {removed}"
        )


@pytest.fixture
def temp_dir() -> Generator[Path, None, None]:
    """Create a temporary directory for test files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def config_path(temp_dir: Path) -> Path:
    """Return path for a temporary config file."""
    return temp_dir / "config.toml"


@pytest.fixture
def config_manager(config_path: Path) -> ConfigManager:
    """Create a ConfigManager with a temporary config file."""
    from mixpanel_headless._internal.config import ConfigManager

    return ConfigManager(config_path=config_path)


@pytest.fixture
def sample_credentials() -> dict[str, str]:
    """Return sample credentials for testing."""
    return {
        "name": "test_account",
        "username": "sa_test_user",
        "secret": "test_secret_12345",
        "project_id": "12345",
        "region": "us",
    }


# =============================================================================
# API Client Fixtures
# =============================================================================


@pytest.fixture
def mock_session() -> Session:
    """Create a mock Session for API client testing."""
    return make_session()


@pytest.fixture
def mock_client_factory(
    mock_session: Session,
) -> Callable[[Callable[[httpx.Request], httpx.Response]], MixpanelAPIClient]:
    """Factory for creating mock API clients.

    Usage:
        def test_something(mock_client_factory):
            def handler(request):
                return httpx.Response(200, json={"data": []})

            client = mock_client_factory(handler)
            with client:
                result = client.get_events()
    """
    from mixpanel_headless._internal.api_client import MixpanelAPIClient

    def factory(
        handler: Callable[[httpx.Request], httpx.Response],
    ) -> MixpanelAPIClient:
        transport = httpx.MockTransport(handler)
        return MixpanelAPIClient(session=mock_session, _transport=transport)

    return factory


@pytest.fixture
def success_handler() -> Callable[[httpx.Request], httpx.Response]:
    """Handler that returns 200 with empty list."""

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=[])

    return handler


@pytest.fixture
def auth_error_handler() -> Callable[[httpx.Request], httpx.Response]:
    """Handler that returns 401 authentication error."""

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"error": "Invalid credentials"})

    return handler


@pytest.fixture
def rate_limit_handler() -> Callable[[httpx.Request], httpx.Response]:
    """Handler that returns 429 rate limit error."""

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, headers={"Retry-After": "60"})

    return handler
