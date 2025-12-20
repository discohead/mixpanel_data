"""Shared fixtures for mixpanel_data tests."""

from __future__ import annotations

import tempfile
from collections.abc import Generator
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from mixpanel_data._internal.config import ConfigManager


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
