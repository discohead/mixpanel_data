"""Property-based tests for ``resolve_session`` (T021).

Three property classes per Research R2:
- Determinism: same inputs → same Session (twice).
- Axis independence: perturbing one axis input never changes the others.
- Env wins: when a per-axis env var and a config value both exist, env wins.

Reference: specs/042-auth-architecture-redesign/research.md R2.

Implementation note: Each Hypothesis example builds its own ConfigManager
in a fresh tmp dir to avoid state leak between examples (the function-scoped
``tmp_path`` fixture is reused across examples within one test function).
"""

from __future__ import annotations

import tempfile
from collections.abc import Iterator
from pathlib import Path

import pytest
from hypothesis import HealthCheck, given
from hypothesis import settings as hyp_settings
from hypothesis import strategies as st
from pydantic import SecretStr

from mixpanel_headless._internal.auth.resolver import resolve_session
from mixpanel_headless._internal.config import ConfigManager

_NAME_ALPHABET = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-"
account_names = st.text(alphabet=_NAME_ALPHABET, min_size=1, max_size=12)
project_ids = st.from_regex(r"^[1-9][0-9]{0,9}$", fullmatch=True)
workspace_ids = st.integers(min_value=1, max_value=2**31 - 1)


@pytest.fixture(autouse=True)
def _isolated_home(
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[None]:
    """Isolate ``$HOME`` so the resolver doesn't pick up the dev's real bridge."""
    with tempfile.TemporaryDirectory() as tmp:
        monkeypatch.setenv("HOME", tmp)
        yield


def _build_cm(name: str, project: str) -> ConfigManager:
    """Build a fresh tmp ConfigManager seeded with one SA + active state.

    Each call uses an independent ``TemporaryDirectory`` so multiple
    Hypothesis examples in the same test function do not collide on file
    state. Project lives on the account as ``default_project`` (FR-012);
    only ``account`` and ``workspace`` go to ``[active]``.

    Args:
        name: Account name to register.
        project: Project ID to set as the account's ``default_project``.

    Returns:
        A ConfigManager whose tmp dir leaks (Python GC handles it
        eventually; Hypothesis examples are short-lived).
    """
    tmp = Path(tempfile.mkdtemp())
    cm = ConfigManager(config_path=tmp / "config.toml")
    cm.add_account(
        name,
        type="service_account",
        region="us",
        default_project=project,
        username="u",
        secret=SecretStr("s"),
    )
    cm.set_active(account=name)
    return cm


@hyp_settings(
    suppress_health_check=[HealthCheck.function_scoped_fixture],
    deadline=None,
)
@given(name=account_names, project=project_ids)
def test_resolver_determinism(name: str, project: str) -> None:
    """``resolve_session`` called twice with identical inputs yields equal Sessions."""
    cm = _build_cm(name, project)
    s1 = resolve_session(config=cm)
    s2 = resolve_session(config=cm)
    assert s1 == s2


@hyp_settings(
    suppress_health_check=[HealthCheck.function_scoped_fixture],
    deadline=None,
)
@given(
    name=account_names,
    base_project=project_ids,
    perturbed_project=project_ids,
)
def test_axis_independence_project_does_not_change_account(
    name: str, base_project: str, perturbed_project: str
) -> None:
    """Changing ``project`` axis never changes the resolved account."""
    cm = _build_cm(name, base_project)
    s_base = resolve_session(config=cm)
    s_perturbed = resolve_session(project=perturbed_project, config=cm)
    assert s_base.account == s_perturbed.account


@hyp_settings(
    suppress_health_check=[HealthCheck.function_scoped_fixture],
    deadline=None,
)
@given(
    name=account_names,
    project=project_ids,
    workspace=workspace_ids,
)
def test_axis_independence_workspace_does_not_change_account_or_project(
    name: str, project: str, workspace: int
) -> None:
    """Changing ``workspace`` axis never changes account or project."""
    cm = _build_cm(name, project)
    s_base = resolve_session(config=cm)
    s_perturbed = resolve_session(workspace=workspace, config=cm)
    assert s_base.account == s_perturbed.account
    assert s_base.project == s_perturbed.project


@hyp_settings(
    suppress_health_check=[HealthCheck.function_scoped_fixture],
    deadline=None,
)
@given(
    name=account_names,
    config_project=project_ids,
    env_project=project_ids,
)
def test_env_wins_for_project_axis(
    monkeypatch: pytest.MonkeyPatch,
    name: str,
    config_project: str,
    env_project: str,
) -> None:
    """``MP_PROJECT_ID`` always wins over the account's ``default_project``."""
    cm = _build_cm(name, config_project)
    monkeypatch.setenv("MP_PROJECT_ID", env_project)
    s = resolve_session(config=cm)
    assert s.project.id == env_project


@hyp_settings(
    suppress_health_check=[HealthCheck.function_scoped_fixture],
    deadline=None,
)
@given(
    name=account_names,
    project=project_ids,
    config_workspace=workspace_ids,
    env_workspace=workspace_ids,
)
def test_env_wins_for_workspace_axis(
    monkeypatch: pytest.MonkeyPatch,
    name: str,
    project: str,
    config_workspace: int,
    env_workspace: int,
) -> None:
    """``MP_WORKSPACE_ID`` always wins over ``[active].workspace``."""
    cm = _build_cm(name, project)
    cm.set_active(workspace=config_workspace)
    monkeypatch.setenv("MP_WORKSPACE_ID", str(env_workspace))
    s = resolve_session(config=cm)
    assert s.workspace is not None
    assert s.workspace.id == env_workspace
