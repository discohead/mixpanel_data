"""Unit tests for Workspace experiment methods (Phase 025).

Tests for experiment CRUD and lifecycle operations on the Workspace
facade. Each method delegates to MixpanelAPIClient and returns typed objects.

Verifies:
- Experiment CRUD: list, create, get, update, delete
- Experiment lifecycle: launch, conclude, decide
- Experiment management: archive, restore, duplicate
- ERF experiments listing
"""

# ruff: noqa: ARG001, ARG005

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import httpx
from pydantic import SecretStr

from mixpanel_headless._internal.api_client import MixpanelAPIClient
from mixpanel_headless._internal.auth.account import ServiceAccount
from mixpanel_headless._internal.auth.session import Project, Session
from mixpanel_headless.types import (
    CreateExperimentParams,
    DuplicateExperimentParams,
    Experiment,
    ExperimentConcludeParams,
    ExperimentDecideParams,
    ExperimentStatus,
    UpdateExperimentParams,
)
from mixpanel_headless.workspace import Workspace
from tests.conftest import make_session

# ---- 042 redesign: canonical fake Session for Workspace(session=…) ----
_TEST_SESSION = Session(
    account=ServiceAccount(
        name="test_account",
        region="us",
        username="test_user",
        secret=SecretStr("test_secret"),
        default_project="12345",
    ),
    project=Project(id="12345"),
)

# =============================================================================
# Helpers
# =============================================================================


def _make_oauth_credentials() -> Session:
    """Create OAuth Credentials for testing.

    Returns:
        A Credentials instance with auth_method=oauth.
    """
    return make_session(project_id="12345", region="us", oauth_token="test-token")


# _setup_config_with_account removed in B1 (Fix 9): the legacy v1
# ``ConfigManager.add_account(project_id=, region=, …)`` signature is
# gone; ``_make_workspace`` now relies on ``session=_TEST_SESSION``
# instead, which never touches a real ConfigManager.


def _make_workspace(
    temp_dir: Path,
    handler: Any,
) -> Workspace:
    """Create a Workspace with a mock HTTP transport.

    Args:
        temp_dir: Temporary directory for config and storage.
        handler: Handler function for httpx.MockTransport.

    Returns:
        A Workspace instance wired to the mock transport.
    """
    creds = _make_oauth_credentials()
    transport = httpx.MockTransport(handler)
    client = MixpanelAPIClient(session=creds, _transport=transport)
    return Workspace(
        session=_TEST_SESSION,
        _api_client=client,
    )


# =============================================================================
# Mock response data
# =============================================================================


def _experiment_json(
    id: str = "xyz-456",
    name: str = "Test Experiment",
    status: str = "draft",
) -> dict[str, Any]:
    """Return a minimal experiment dict matching the API shape.

    Args:
        id: Experiment UUID.
        name: Experiment name.
        status: Experiment lifecycle status.

    Returns:
        Dict that can be parsed into an Experiment model.
    """
    return {
        "id": id,
        "name": name,
        "status": status,
    }


# =============================================================================
# TestWorkspaceExperimentCRUD
# =============================================================================


class TestWorkspaceExperimentCRUD:
    """Tests for Workspace experiment CRUD methods."""

    def test_list_experiments(self, temp_dir: Path) -> None:
        """list_experiments() returns list of Experiment objects."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return experiment list."""
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": [
                        _experiment_json("abc-123", "Exp A"),
                        _experiment_json("def-456", "Exp B"),
                    ],
                },
            )

        ws = _make_workspace(temp_dir, handler)
        experiments = ws.list_experiments()

        assert len(experiments) == 2
        assert isinstance(experiments[0], Experiment)
        assert experiments[0].id == "abc-123"
        assert experiments[0].name == "Exp A"
        assert experiments[1].id == "def-456"
        assert experiments[1].name == "Exp B"

    def test_list_experiments_empty(self, temp_dir: Path) -> None:
        """list_experiments() returns empty list when no experiments exist."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return empty experiment list."""
            return httpx.Response(200, json={"status": "ok", "results": []})

        ws = _make_workspace(temp_dir, handler)
        experiments = ws.list_experiments()

        assert experiments == []

    def test_list_experiments_include_archived(self, temp_dir: Path) -> None:
        """list_experiments(include_archived=True) passes param to API."""
        captured_url: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture URL and return experiment list."""
            captured_url.append(str(request.url))
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": [_experiment_json()],
                },
            )

        ws = _make_workspace(temp_dir, handler)
        experiments = ws.list_experiments(include_archived=True)

        assert len(experiments) == 1
        assert isinstance(experiments[0], Experiment)
        assert "include_archived=true" in captured_url[0]

    def test_create_experiment(self, temp_dir: Path) -> None:
        """create_experiment() returns the created Experiment."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return created experiment."""
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": _experiment_json("new-123", "New Experiment"),
                },
            )

        ws = _make_workspace(temp_dir, handler)
        params = CreateExperimentParams(name="New Experiment")
        experiment = ws.create_experiment(params)

        assert isinstance(experiment, Experiment)
        assert experiment.id == "new-123"
        assert experiment.name == "New Experiment"

    def test_get_experiment(self, temp_dir: Path) -> None:
        """get_experiment() returns the requested Experiment."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return single experiment."""
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": _experiment_json("xyz-456", "Got Experiment"),
                },
            )

        ws = _make_workspace(temp_dir, handler)
        experiment = ws.get_experiment("xyz-456")

        assert isinstance(experiment, Experiment)
        assert experiment.id == "xyz-456"
        assert experiment.name == "Got Experiment"

    def test_update_experiment(self, temp_dir: Path) -> None:
        """update_experiment() returns the updated Experiment."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return updated experiment."""
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": _experiment_json("xyz-456", "Updated Experiment"),
                },
            )

        ws = _make_workspace(temp_dir, handler)
        params = UpdateExperimentParams(name="Updated Experiment")
        experiment = ws.update_experiment("xyz-456", params)

        assert isinstance(experiment, Experiment)
        assert experiment.id == "xyz-456"
        assert experiment.name == "Updated Experiment"

    def test_delete_experiment(self, temp_dir: Path) -> None:
        """delete_experiment() returns None on success."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return 204 for delete."""
            return httpx.Response(204)

        ws = _make_workspace(temp_dir, handler)
        ws.delete_experiment("xyz-456")  # Should not raise


# =============================================================================
# TestWorkspaceExperimentLifecycle
# =============================================================================


class TestWorkspaceExperimentLifecycle:
    """Tests for Workspace experiment lifecycle methods."""

    def test_launch_experiment(self, temp_dir: Path) -> None:
        """launch_experiment() returns the launched Experiment."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return launched experiment."""
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": _experiment_json("xyz-456", "Test Experiment", "active"),
                },
            )

        ws = _make_workspace(temp_dir, handler)
        experiment = ws.launch_experiment("xyz-456")

        assert isinstance(experiment, Experiment)
        assert experiment.id == "xyz-456"
        assert experiment.status == ExperimentStatus.ACTIVE

    def test_conclude_experiment_without_params(self, temp_dir: Path) -> None:
        """conclude_experiment() without params returns the concluded Experiment."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return concluded experiment."""
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": _experiment_json(
                        "xyz-456", "Test Experiment", "concluded"
                    ),
                },
            )

        ws = _make_workspace(temp_dir, handler)
        experiment = ws.conclude_experiment("xyz-456")

        assert isinstance(experiment, Experiment)
        assert experiment.id == "xyz-456"
        assert experiment.status == ExperimentStatus.CONCLUDED

    def test_conclude_experiment_with_params(self, temp_dir: Path) -> None:
        """conclude_experiment() with params passes them to the API."""
        captured_body: list[Any] = []

        def handler(request: httpx.Request) -> httpx.Response:
            """Capture body and return concluded experiment."""
            if request.content:
                captured_body.append(json.loads(request.content))
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": _experiment_json(
                        "xyz-456", "Test Experiment", "concluded"
                    ),
                },
            )

        ws = _make_workspace(temp_dir, handler)
        params = ExperimentConcludeParams(end_date="2026-04-01")
        experiment = ws.conclude_experiment("xyz-456", params=params)

        assert isinstance(experiment, Experiment)
        assert experiment.status == ExperimentStatus.CONCLUDED
        assert len(captured_body) == 1
        assert captured_body[0]["end_date"] == "2026-04-01"

    def test_decide_experiment(self, temp_dir: Path) -> None:
        """decide_experiment() returns the decided Experiment."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return decided experiment."""
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": _experiment_json(
                        "xyz-456", "Test Experiment", "success"
                    ),
                },
            )

        ws = _make_workspace(temp_dir, handler)
        params = ExperimentDecideParams(success=True, variant="treatment")
        experiment = ws.decide_experiment("xyz-456", params)

        assert isinstance(experiment, Experiment)
        assert experiment.id == "xyz-456"
        assert experiment.status == ExperimentStatus.SUCCESS


# =============================================================================
# TestWorkspaceExperimentManagement
# =============================================================================


class TestWorkspaceExperimentManagement:
    """Tests for Workspace experiment management methods."""

    def test_archive_experiment(self, temp_dir: Path) -> None:
        """archive_experiment() returns None on success."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return 204 for archive."""
            return httpx.Response(204)

        ws = _make_workspace(temp_dir, handler)
        ws.archive_experiment("xyz-456")  # Should not raise

    def test_restore_experiment(self, temp_dir: Path) -> None:
        """restore_experiment() returns the restored Experiment."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return restored experiment."""
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": _experiment_json(
                        "xyz-456", "Restored Experiment", "draft"
                    ),
                },
            )

        ws = _make_workspace(temp_dir, handler)
        experiment = ws.restore_experiment("xyz-456")

        assert isinstance(experiment, Experiment)
        assert experiment.id == "xyz-456"
        assert experiment.name == "Restored Experiment"

    def test_duplicate_experiment_with_params(self, temp_dir: Path) -> None:
        """duplicate_experiment() with params returns the duplicated Experiment."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return duplicated experiment."""
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": _experiment_json("dup-789", "Copy of Test Experiment"),
                },
            )

        ws = _make_workspace(temp_dir, handler)
        params = DuplicateExperimentParams(name="Copy of Test Experiment")
        experiment = ws.duplicate_experiment("xyz-456", params=params)

        assert isinstance(experiment, Experiment)
        assert experiment.id == "dup-789"
        assert experiment.name == "Copy of Test Experiment"

    def test_duplicate_experiment_requires_params(self, temp_dir: Path) -> None:
        """duplicate_experiment() requires params with a name."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return duplicated experiment."""
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": _experiment_json("dup-789", "Auto Copy"),
                },
            )

        ws = _make_workspace(temp_dir, handler)
        params = DuplicateExperimentParams(name="Auto Copy")
        experiment = ws.duplicate_experiment("xyz-456", params)

        assert isinstance(experiment, Experiment)
        assert experiment.id == "dup-789"
        assert experiment.name == "Auto Copy"

    def test_list_erf_experiments(self, temp_dir: Path) -> None:
        """list_erf_experiments() returns list of dicts."""

        def handler(request: httpx.Request) -> httpx.Response:
            """Return ERF experiment list."""
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "results": [
                        {"id": "erf-1", "name": "ERF Exp"},
                    ],
                },
            )

        ws = _make_workspace(temp_dir, handler)
        results = ws.list_erf_experiments()

        assert isinstance(results, list)
        assert len(results) == 1
        assert results[0]["id"] == "erf-1"
