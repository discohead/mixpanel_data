"""Shared fixtures for mixpanel_data tests."""

from __future__ import annotations

import os
import tempfile
from collections.abc import Callable, Generator
from pathlib import Path
from typing import TYPE_CHECKING

import httpx
import pytest
from hypothesis import Phase, Verbosity, settings
from pydantic import SecretStr

# =============================================================================
# Hypothesis Configuration
# =============================================================================

# Register Hypothesis profiles for different environments
settings.register_profile(
    "default",
    max_examples=100,
    verbosity=Verbosity.normal,
    phases=[Phase.explicit, Phase.reuse, Phase.generate, Phase.target, Phase.shrink],
)

settings.register_profile(
    "ci",
    max_examples=200,
    verbosity=Verbosity.normal,
    phases=[Phase.explicit, Phase.reuse, Phase.generate, Phase.target, Phase.shrink],
    derandomize=True,  # Reproducible in CI
)

settings.register_profile(
    "dev",
    max_examples=10,
    verbosity=Verbosity.verbose,
    phases=[Phase.explicit, Phase.reuse, Phase.generate, Phase.target, Phase.shrink],
)

settings.register_profile(
    "debug",
    max_examples=10,
    verbosity=Verbosity.verbose,
    phases=[Phase.explicit, Phase.reuse, Phase.generate, Phase.target, Phase.shrink],
    report_multiple_bugs=False,
)

# Load profile from HYPOTHESIS_PROFILE env var, default to "default"
settings.load_profile(os.getenv("HYPOTHESIS_PROFILE", "default"))

if TYPE_CHECKING:
    from mixpanel_data._internal.api_client import MixpanelAPIClient
    from mixpanel_data._internal.config import ConfigManager, Credentials


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
    from mixpanel_data._internal.config import ConfigManager

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
def mock_credentials() -> Credentials:
    """Create mock credentials for API client testing."""
    from mixpanel_data._internal.config import Credentials

    return Credentials(
        username="test_user",
        secret=SecretStr("test_secret"),
        project_id="12345",
        region="us",
    )


@pytest.fixture
def mock_client_factory(
    mock_credentials: Credentials,
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
    from mixpanel_data._internal.api_client import MixpanelAPIClient

    def factory(
        handler: Callable[[httpx.Request], httpx.Response],
    ) -> MixpanelAPIClient:
        transport = httpx.MockTransport(handler)
        return MixpanelAPIClient(mock_credentials, _transport=transport)

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
