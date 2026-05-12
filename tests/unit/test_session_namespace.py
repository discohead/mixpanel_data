"""Unit tests for the ``mp.session`` public namespace (T032).

Reference: specs/042-auth-architecture-redesign/contracts/python-api.md §7.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import SecretStr

from mixpanel_headless import accounts as accounts_ns
from mixpanel_headless import session as session_ns
from mixpanel_headless import targets as targets_ns
from mixpanel_headless._internal.auth.session import ActiveSession
from mixpanel_headless._internal.config import ConfigManager


@pytest.fixture(autouse=True)
def _isolated_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Isolate $HOME and MP_CONFIG_PATH."""
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("MP_CONFIG_PATH", str(tmp_path / ".mp" / "config.toml"))


@pytest.fixture
def seeded() -> ConfigManager:
    """Return a ConfigManager with one account."""
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


class TestShow:
    """``mp.session.show()`` returns the persisted ``[active]`` block."""

    def test_show_returns_active_session(self, seeded: ConfigManager) -> None:
        """``show()`` returns an ActiveSession matching ``[active]``.

        Project lives on the account, not in ``[active]``.
        """
        seeded.set_active(account="x", workspace=42)
        result = session_ns.show()
        assert isinstance(result, ActiveSession)
        assert result.account == "x"
        assert result.workspace == 42
        # Project comes from the account's default_project.
        assert seeded.get_account("x").default_project == "3713224"


class TestUse:
    """``mp.session.use(*, account=, project=, workspace=, target=)``."""

    def test_use_account_only(self, seeded: ConfigManager) -> None:
        """Updating only the account axis preserves the others.

        Project on the prior account stays on that account; the new
        account's ``default_project`` (if any) is what resolves later.
        """
        seeded.set_active(workspace=42)
        accounts_ns.add(
            "other",
            type="oauth_browser",
            region="us",
            default_project="3713224",
        )
        session_ns.use(account="other")
        active = seeded.get_active()
        assert active.account == "other"
        assert active.workspace == 42
        assert seeded.get_account("other").default_project == "3713224"

    def test_use_project_only(self, seeded: ConfigManager) -> None:
        """Updating only the project axis writes to the active account's
        ``default_project`` and preserves the other axes."""
        seeded.set_active(account="x", workspace=42)
        session_ns.use(project="9999999")
        active = seeded.get_active()
        assert active.account == "x"
        assert active.workspace == 42
        # Project went onto the account.
        assert seeded.get_account("x").default_project == "9999999"

    def test_use_workspace_only(self, seeded: ConfigManager) -> None:
        """Updating only the workspace axis preserves the others."""
        seeded.set_active(account="x")
        session_ns.use(workspace=99)
        active = seeded.get_active()
        assert active.account == "x"
        assert active.workspace == 99
        # Project stays on the account.
        assert seeded.get_account("x").default_project == "3713224"

    def test_use_target(self, seeded: ConfigManager) -> None:
        """``target=`` applies the target's three axes (project to account)."""
        targets_ns.add("ecom", account="x", project="3018488", workspace=42)
        session_ns.use(target="ecom")
        active = seeded.get_active()
        assert active.account == "x"
        assert active.workspace == 42
        # Target's project gets written to the target account's default_project.
        assert seeded.get_account("x").default_project == "3018488"

    def test_use_target_with_other_axis_raises(self, seeded: ConfigManager) -> None:
        """Combining ``target=`` with any axis kwarg raises ValueError."""
        targets_ns.add("ecom", account="x", project="3018488")
        with pytest.raises(ValueError):
            session_ns.use(target="ecom", account="x")
