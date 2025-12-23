"""Shared fixtures for CLI integration tests."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from mixpanel_data._internal.config import AccountInfo


@pytest.fixture
def cli_runner() -> CliRunner:
    """Create a CLI runner for testing commands."""
    return CliRunner()


@pytest.fixture
def mock_config_manager() -> MagicMock:
    """Create a mock ConfigManager for testing auth commands."""
    config = MagicMock()

    config.list_accounts.return_value = [
        AccountInfo(
            name="production",
            username="user@example.com",
            project_id="12345",
            region="us",
            is_default=True,
        ),
        AccountInfo(
            name="staging",
            username="user@example.com",
            project_id="67890",
            region="eu",
            is_default=False,
        ),
    ]

    config.get_default.return_value = AccountInfo(
        name="production",
        username="user@example.com",
        project_id="12345",
        region="us",
        is_default=True,
    )

    config.get_account.return_value = AccountInfo(
        name="production",
        username="user@example.com",
        project_id="12345",
        region="us",
        is_default=True,
    )

    return config


@pytest.fixture
def patch_config_manager(mock_config_manager: MagicMock) -> Any:
    """Patch get_config to return mock ConfigManager."""
    with patch(
        "mixpanel_data.cli.commands.auth.get_config",
        return_value=mock_config_manager,
    ) as mock:
        yield mock
