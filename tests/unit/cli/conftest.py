"""Shared fixtures for CLI tests."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import MagicMock

import pytest
import typer
from typer.testing import CliRunner

from mixpanel_data.types import (
    FetchResult,
    SegmentationResult,
    TableInfo,
    WorkspaceInfo,
)


@pytest.fixture
def cli_runner() -> CliRunner:
    """Create a CLI runner for testing commands."""
    return CliRunner()


@pytest.fixture
def mock_workspace() -> MagicMock:
    """Create a mock Workspace for testing commands."""
    workspace = MagicMock()

    # Set up common return values
    workspace.events.return_value = ["Event1", "Event2", "Event3"]
    workspace.properties.return_value = ["property1", "property2"]
    workspace.property_values.return_value = ["value1", "value2", "value3"]
    workspace.funnels.return_value = []
    workspace.cohorts.return_value = []
    workspace.top_events.return_value = []

    workspace.tables.return_value = [
        TableInfo(
            name="events",
            type="events",
            row_count=1000,
            fetched_at=datetime(2024, 1, 1, 0, 0, 0, tzinfo=UTC),
        ),
    ]

    workspace.info.return_value = WorkspaceInfo(
        path=Path("/tmp/workspace.db"),
        account="default",
        project_id="12345",
        region="us",
        tables=["events"],
        size_mb=1.5,
        created_at=None,
    )

    workspace.sql_rows.return_value = [{"count": 100}]
    workspace.sql_scalar.return_value = 100

    workspace.fetch_events.return_value = FetchResult(
        table="events",
        rows=1000,
        type="events",
        duration_seconds=5.0,
        date_range=("2024-01-01", "2024-01-31"),
        fetched_at=datetime(2024, 1, 31, 12, 0, 0, tzinfo=UTC),
    )

    workspace.segmentation.return_value = SegmentationResult(
        event="Signup",
        from_date="2024-01-01",
        to_date="2024-01-31",
        unit="day",
        segment_property=None,
        total=500,
        series={"total": {"2024-01-01": 100}},
    )

    return workspace


@pytest.fixture
def mock_config_manager() -> MagicMock:
    """Create a mock ConfigManager for testing auth commands."""
    from mixpanel_data._internal.config import AccountInfo

    config = MagicMock()

    # Set up common return values
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
def mock_context() -> typer.Context:
    """Create a mock Typer context with default options."""
    ctx = MagicMock(spec=typer.Context)
    ctx.obj = {
        "account": None,
        "quiet": False,
        "verbose": False,
        "workspace": None,
        "config": None,
    }
    return ctx
