"""Shared fixtures for query API unit tests."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from mixpanel_headless._internal.auth.session import Session
from tests.conftest import make_session


@pytest.fixture
def mock_session() -> Session:
    """Create a mock Session for testing."""
    return make_session()


@pytest.fixture
def mock_config_manager() -> MagicMock:
    """Create a stub ConfigManager (legacy fixture; unused by current code paths)."""
    return MagicMock()
