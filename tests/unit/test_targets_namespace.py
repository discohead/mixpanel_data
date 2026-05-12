"""Unit tests for the ``mp.targets`` public namespace (T031).

Reference: specs/042-auth-architecture-redesign/contracts/python-api.md §6.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import SecretStr, ValidationError

from mixpanel_headless import accounts as accounts_ns
from mixpanel_headless import targets as targets_ns
from mixpanel_headless._internal.config import ConfigManager
from mixpanel_headless.exceptions import ConfigError
from mixpanel_headless.types import Target


@pytest.fixture(autouse=True)
def _isolated_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Isolate $HOME and MP_CONFIG_PATH for hermetic tests."""
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("MP_CONFIG_PATH", str(tmp_path / ".mp" / "config.toml"))


@pytest.fixture
def cm() -> ConfigManager:
    """Return a ConfigManager seeded with one account named 'x'."""
    cm = ConfigManager()
    accounts_ns.add(
        "x",
        type="service_account",
        region="us",
        default_project="3713224",
        username="u",
        secret=SecretStr("s"),
    )
    return cm


class TestAdd:
    """``mp.targets.add(name, *, account, project, workspace=None)``."""

    def test_minimal(self, cm: ConfigManager) -> None:
        """Adding a target without workspace persists account+project only."""
        t = targets_ns.add("ecom", account="x", project="3018488")
        assert isinstance(t, Target)
        assert t.workspace is None

    def test_with_workspace(self, cm: ConfigManager) -> None:
        """Adding with workspace persists all three fields."""
        t = targets_ns.add("ecom", account="x", project="3018488", workspace=42)
        assert t.workspace == 42

    def test_referencing_missing_account_raises(self, cm: ConfigManager) -> None:
        """Referencing a non-existent account raises ConfigError."""
        with pytest.raises(ConfigError):
            targets_ns.add("ecom", account="ghost", project="3018488")


class TestTargetWorkspaceValidation:
    """``Target.workspace`` MUST require a positive integer (FR-012 parity).

    Mirrors the constraint on ``WorkspaceRef.id`` (``PositiveInt``). Without
    this guard, ``add_target(workspace=0)`` or ``-1`` corrupts the stored
    config — ``apply_target`` then writes the invalid value into ``[active]``
    bypassing the resolver's validator, and the failure surfaces far from
    the original input.
    """

    def test_target_workspace_zero_rejected(self) -> None:
        """``Target(workspace=0)`` raises at construction."""
        with pytest.raises(ValidationError):
            Target(name="t", account="x", project="3018488", workspace=0)

    def test_target_workspace_negative_rejected(self) -> None:
        """``Target(workspace=-5)`` raises at construction."""
        with pytest.raises(ValidationError):
            Target(name="t", account="x", project="3018488", workspace=-5)

    def test_target_workspace_positive_accepted(self) -> None:
        """``Target(workspace=42)`` succeeds."""
        t = Target(name="t", account="x", project="3018488", workspace=42)
        assert t.workspace == 42

    def test_target_workspace_none_accepted(self) -> None:
        """``Target(workspace=None)`` succeeds (lazy-resolve later)."""
        t = Target(name="t", account="x", project="3018488", workspace=None)
        assert t.workspace is None

    def test_add_target_workspace_zero_rejected(self, cm: ConfigManager) -> None:
        """``mp.targets.add(..., workspace=0)`` raises before persisting."""
        with pytest.raises((ValidationError, ConfigError)):
            targets_ns.add("ecom", account="x", project="3018488", workspace=0)


class TestList:
    """``mp.targets.list()`` returns Target records."""

    def test_empty(self, cm: ConfigManager) -> None:
        """No targets → empty list."""
        assert targets_ns.list() == []

    def test_with_targets(self, cm: ConfigManager) -> None:
        """All registered targets appear sorted by name."""
        targets_ns.add("b", account="x", project="1")
        targets_ns.add("a", account="x", project="2")
        result = targets_ns.list()
        assert [t.name for t in result] == ["a", "b"]


class TestUse:
    """``mp.targets.use(name)`` writes all three axes atomically.

    Account + workspace go to ``[active]``; project goes to the target
    account's ``default_project`` (project lives on the account).
    """

    def test_use_writes_three_axes(self, cm: ConfigManager) -> None:
        """``use`` writes account, workspace to [active] and project to account."""
        targets_ns.add("ecom", account="x", project="3018488", workspace=42)
        targets_ns.use("ecom")
        active = cm.get_active()
        assert active.account == "x"
        assert active.workspace == 42
        # Target project goes onto the target account's default_project.
        assert cm.get_account("x").default_project == "3018488"

    def test_use_missing_raises(self, cm: ConfigManager) -> None:
        """``use("ghost")`` raises ConfigError."""
        with pytest.raises(ConfigError):
            targets_ns.use("ghost")


class TestRemove:
    """``mp.targets.remove(name)`` deletes the entry."""

    def test_remove(self, cm: ConfigManager) -> None:
        """``remove`` deletes the target."""
        targets_ns.add("ecom", account="x", project="3018488")
        targets_ns.remove("ecom")
        assert targets_ns.list() == []

    def test_remove_missing_raises(self, cm: ConfigManager) -> None:
        """Removing a non-existent target raises."""
        with pytest.raises(ConfigError):
            targets_ns.remove("ghost")


class TestShow:
    """``mp.targets.show(name)`` returns the named Target."""

    def test_show(self, cm: ConfigManager) -> None:
        """``show`` returns the matching Target."""
        targets_ns.add("ecom", account="x", project="3018488")
        result = targets_ns.show("ecom")
        assert result.name == "ecom"
