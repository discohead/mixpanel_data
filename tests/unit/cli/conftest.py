"""Shared fixtures for CLI tests."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
import typer
from typer.testing import CliRunner

from mixpanel_headless.types import (
    SegmentationResult,
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


# mock_config_manager fixture removed in B1 (Fix 9): the AccountInfo
# dataclass and legacy ``mp auth`` commands it targeted are gone. Use
# the v3 ``mp account`` / ``mp session`` / ``mp target`` namespaces
# instead.


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
