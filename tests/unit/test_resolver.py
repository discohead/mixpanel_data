"""Unit tests for the single ``resolve_session`` (T020).

Per FR-017, the resolver consults sources in this priority per axis:
**env → param → target → bridge → config**. Each axis is independent —
setting a project override does NOT affect account or workspace resolution.

Reference: specs/042-auth-architecture-redesign/contracts/python-api.md §1.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import pytest
from pydantic import SecretStr

from mixpanel_headless._internal.auth.account import (
    OAuthTokenAccount,
    ServiceAccount,
)
from mixpanel_headless._internal.auth.resolver import resolve_session
from mixpanel_headless._internal.config import ConfigManager
from mixpanel_headless.exceptions import ConfigError


@pytest.fixture(autouse=True)
def _isolated_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Isolate ``$HOME`` so the resolver does NOT pick up the dev's real bridge.

    Without this fixture the resolver's default bridge search path
    (``~/.claude/mixpanel/auth.json``) hits whatever the developer has on
    disk, which is typically a v1 bridge that fails the v2 schema check
    and turns every resolver test into a flake.
    """
    monkeypatch.setenv("HOME", str(tmp_path))


@pytest.fixture
def cm(tmp_path: Path) -> ConfigManager:
    """Return a v3 ConfigManager pointing at a tmp config path with one SA."""
    cm = ConfigManager(config_path=tmp_path / "config.toml")
    cm.add_account(
        "team",
        type="service_account",
        region="us",
        default_project="3713224",
        username="team.sa",
        secret=SecretStr("team-secret"),
    )
    return cm


@pytest.fixture
def cm_with_active(cm: ConfigManager) -> ConfigManager:
    """Return a ConfigManager with ``[active].account`` set; project on the account."""
    cm.set_active(account="team")
    return cm


class TestAccountAxisPriority:
    """Order: env → param → target → bridge → config."""

    def test_explicit_param_beats_active(self, cm_with_active: ConfigManager) -> None:
        """``account=NAME`` param overrides ``[active].account``."""
        cm_with_active.add_account(
            "other",
            type="service_account",
            region="us",
            default_project="9999999",
            username="o",
            secret=SecretStr("o"),
        )
        s = resolve_session(account="other", config=cm_with_active)
        assert s.account.name == "other"

    def test_active_used_when_no_param(self, cm_with_active: ConfigManager) -> None:
        """No env / no param / no target / no bridge → use ``[active].account``."""
        s = resolve_session(config=cm_with_active)
        assert s.account.name == "team"

    def test_env_quad_synthesizes_service_account(
        self,
        cm: ConfigManager,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Full SA env quad synthesizes a ServiceAccount, beating ``[active]``."""
        monkeypatch.setenv("MP_USERNAME", "env.user")
        monkeypatch.setenv("MP_SECRET", "env-secret")
        monkeypatch.setenv("MP_PROJECT_ID", "999")
        monkeypatch.setenv("MP_REGION", "eu")
        cm.set_active(account="team")
        s = resolve_session(config=cm)
        assert isinstance(s.account, ServiceAccount)
        assert s.account.region == "eu"
        assert s.account.username == "env.user"

    def test_oauth_token_env_synthesizes(
        self,
        cm: ConfigManager,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """``MP_OAUTH_TOKEN`` env synthesizes an OAuthTokenAccount."""
        monkeypatch.setenv("MP_OAUTH_TOKEN", "env-bearer-tok")
        monkeypatch.setenv("MP_PROJECT_ID", "999")
        monkeypatch.setenv("MP_REGION", "us")
        s = resolve_session(config=cm)
        assert isinstance(s.account, OAuthTokenAccount)

    def test_sa_env_quad_beats_oauth_token_env(
        self,
        cm: ConfigManager,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """When both SA quad AND OAuth token are set, SA wins (preserves PR #125)."""
        monkeypatch.setenv("MP_USERNAME", "env.user")
        monkeypatch.setenv("MP_SECRET", "env-secret")
        monkeypatch.setenv("MP_OAUTH_TOKEN", "env-bearer")
        monkeypatch.setenv("MP_PROJECT_ID", "999")
        monkeypatch.setenv("MP_REGION", "us")
        s = resolve_session(config=cm)
        assert isinstance(s.account, ServiceAccount)


class TestProjectAxisPriority:
    """Order: env → param → target → bridge → config."""

    def test_explicit_param_beats_active(self, cm_with_active: ConfigManager) -> None:
        """``project=ID`` param overrides ``account.default_project``."""
        s = resolve_session(project="888", config=cm_with_active)
        assert s.project.id == "888"

    def test_env_beats_param(
        self,
        cm_with_active: ConfigManager,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Per FR-017 + spec, env wins over the explicit param too.

        ``MP_PROJECT_ID`` overrides any project= argument.
        """
        monkeypatch.setenv("MP_PROJECT_ID", "777")
        s = resolve_session(project="888", config=cm_with_active)
        assert s.project.id == "777"

    def test_active_used_when_no_param(self, cm_with_active: ConfigManager) -> None:
        """Account's ``default_project`` used when no override."""
        s = resolve_session(config=cm_with_active)
        assert s.project.id == "3713224"

    def test_missing_project_axis_raises(self, tmp_path: Path) -> None:
        """No env / param / target / bridge AND account has no default_project → ConfigError."""
        cm = ConfigManager(config_path=tmp_path / "config.toml")
        # Add an oauth_browser account (default_project optional) so the
        # account axis resolves but the project axis cannot.
        cm.add_account("personal", type="oauth_browser", region="us")
        cm.set_active(account="personal")
        with pytest.raises(ConfigError):
            resolve_session(config=cm)


class TestWorkspaceAxisPriority:
    """Workspace axis can be None (lazy-resolve later)."""

    def test_param_overrides_active(self, cm_with_active: ConfigManager) -> None:
        """``workspace=N`` param overrides ``[active].workspace``."""
        cm_with_active.set_active(workspace=99)
        s = resolve_session(workspace=42, config=cm_with_active)
        assert s.workspace is not None
        assert s.workspace.id == 42

    def test_env_overrides_param(
        self,
        cm_with_active: ConfigManager,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """``MP_WORKSPACE_ID`` env overrides any param."""
        monkeypatch.setenv("MP_WORKSPACE_ID", "100")
        s = resolve_session(workspace=42, config=cm_with_active)
        assert s.workspace is not None
        assert s.workspace.id == 100

    def test_workspace_none_when_unset(self, cm_with_active: ConfigManager) -> None:
        """No source → workspace remains None (lazy-resolve)."""
        s = resolve_session(config=cm_with_active)
        assert s.workspace is None


class TestTargetMutualExclusion:
    """``target=`` must not combine with ``account=``/``project=``/``workspace=``."""

    def test_target_with_account_raises(self, cm_with_active: ConfigManager) -> None:
        """``target=`` + ``account=`` raises ValueError."""
        cm_with_active.add_target("ecom", account="team", project="3018488")
        with pytest.raises(ValueError):
            resolve_session(target="ecom", account="team", config=cm_with_active)

    def test_target_with_project_raises(self, cm_with_active: ConfigManager) -> None:
        """``target=`` + ``project=`` raises ValueError."""
        cm_with_active.add_target("ecom", account="team", project="3018488")
        with pytest.raises(ValueError):
            resolve_session(target="ecom", project="999", config=cm_with_active)

    def test_target_with_workspace_raises(self, cm_with_active: ConfigManager) -> None:
        """``target=`` + ``workspace=`` raises ValueError."""
        cm_with_active.add_target("ecom", account="team", project="3018488")
        with pytest.raises(ValueError):
            resolve_session(target="ecom", workspace=42, config=cm_with_active)

    def test_target_alone_resolves(self, cm_with_active: ConfigManager) -> None:
        """``target=`` alone applies all three axes from the target block."""
        cm_with_active.add_target(
            "ecom", account="team", project="3018488", workspace=42
        )
        s = resolve_session(target="ecom", config=cm_with_active)
        assert s.account.name == "team"
        assert s.project.id == "3018488"
        assert s.workspace is not None
        assert s.workspace.id == 42


class TestNoSideEffects:
    """Resolver is pure — no env mutation, no /me HTTP, no token reads."""

    def test_does_not_mutate_environ(
        self,
        cm_with_active: ConfigManager,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """``resolve_session`` never modifies ``os.environ``."""
        monkeypatch.setenv("UNRELATED_VAR", "untouched")
        before: dict[str, str] = dict(os.environ)
        resolve_session(config=cm_with_active)
        after: dict[str, str] = dict(os.environ)
        assert before == after

    def test_does_not_read_oauth_tokens(self, cm: ConfigManager) -> None:
        """``resolve_session`` does not read on-disk token files.

        For ``oauth_browser`` accounts, the resolver returns a Session whose
        ``account`` references the account; the actual token is fetched
        lazily by ``MixpanelAPIClient`` when a request goes out, not at
        Session construction time.
        """
        cm.add_account(
            "personal", type="oauth_browser", region="us", default_project="3713224"
        )
        cm.set_active(account="personal")
        # No tokens.json at any path — should still construct a Session.
        s = resolve_session(config=cm)
        assert s.account.name == "personal"


class TestErrorMessages:
    """ConfigError messages match the multi-line format from FR-024."""

    def test_no_account_lists_options(self, cm: ConfigManager) -> None:
        """No env / no param / no target / no bridge / no config → multi-line error."""
        # cm has accounts but no [active].account; no env vars set.
        with pytest.raises(ConfigError) as excinfo:
            resolve_session(config=cm)
        msg = str(excinfo.value)
        # Should mention every fix path (per spec FR-024).
        assert "account" in msg.lower()


class TestCrossSourceOrdering:
    """Inter-source priority for the resolver chain (env > param > target > bridge > config).

    The per-axis priority tests above lock the *first* source that wins for a
    given case. This class locks the *interaction* between sources — bridge
    beating config, target beating bridge, env beating target — which is the
    real-world matrix that powers the redesign's "single source of truth"
    promise. Without these, a future refactor could swap two layers in
    ``_resolve_*_axis`` and no per-axis test would fail.
    """

    def _make_bridge(
        self,
        *,
        project: str | None = None,
        workspace: int | None = None,
    ) -> Any:
        """Construct a ``BridgeFile`` pointing at a fresh service account."""
        from mixpanel_headless._internal.auth.account import ServiceAccount
        from mixpanel_headless._internal.auth.bridge import BridgeFile

        return BridgeFile(
            account=ServiceAccount(
                name="bridge-account",
                region="us",
                username="bridge.user",
                secret=SecretStr("bridge-secret"),
                default_project=None,
            ),
            project=project,
            workspace=workspace,
        )

    # ── Account axis ──────────────────────────────────────────────────

    def test_bridge_account_beats_config_active(
        self, cm_with_active: ConfigManager
    ) -> None:
        """No env / no param / no target → bridge.account wins over [active]."""
        bridge = self._make_bridge(project="3713224")
        s = resolve_session(config=cm_with_active, bridge=bridge)
        # Bridge account (``bridge-account``) wins over [active].account (``team``).
        assert s.account.name == "bridge-account"

    def test_target_account_beats_bridge(self, cm_with_active: ConfigManager) -> None:
        """target.account beats bridge.account when both are present."""
        cm_with_active.add_target(
            "ecom", account="team", project="3713224", workspace=42
        )
        bridge = self._make_bridge(project="3713224")
        s = resolve_session(target="ecom", config=cm_with_active, bridge=bridge)
        # Target (``team``) wins over bridge (``bridge-account``).
        assert s.account.name == "team"

    def test_env_sa_quad_beats_target(
        self,
        cm_with_active: ConfigManager,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """SA env quad synthesizes an account that wins over target.account."""
        cm_with_active.add_target(
            "ecom", account="team", project="3713224", workspace=42
        )
        monkeypatch.setenv("MP_USERNAME", "env.user")
        monkeypatch.setenv("MP_SECRET", "env-secret")
        monkeypatch.setenv("MP_PROJECT_ID", "999")
        monkeypatch.setenv("MP_REGION", "us")
        s = resolve_session(target="ecom", config=cm_with_active)
        # Env quad synthesizes a synthetic name; the important assertion is
        # that ``team`` (from the target) is NOT what we got.
        assert s.account.name != "team"

    def test_env_sa_quad_beats_bridge(
        self,
        cm_with_active: ConfigManager,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """SA env quad beats bridge.account."""
        bridge = self._make_bridge(project="3713224")
        monkeypatch.setenv("MP_USERNAME", "env.user")
        monkeypatch.setenv("MP_SECRET", "env-secret")
        monkeypatch.setenv("MP_PROJECT_ID", "999")
        monkeypatch.setenv("MP_REGION", "us")
        s = resolve_session(config=cm_with_active, bridge=bridge)
        assert s.account.name != "bridge-account"

    # ── Project axis ──────────────────────────────────────────────────

    def test_bridge_project_beats_account_default(
        self, cm_with_active: ConfigManager
    ) -> None:
        """bridge.project beats account.default_project (3713224)."""
        bridge = self._make_bridge(project="3018488")
        s = resolve_session(config=cm_with_active, bridge=bridge)
        # Bridge has its own account, so this also tests the project tied to
        # bridge.account; the project assertion is the load-bearing one.
        assert s.project.id == "3018488"

    def test_target_project_beats_bridge(self, cm_with_active: ConfigManager) -> None:
        """target.project beats bridge.project."""
        cm_with_active.add_target(
            "ecom", account="team", project="3018488", workspace=42
        )
        bridge = self._make_bridge(project="9999999")
        s = resolve_session(target="ecom", config=cm_with_active, bridge=bridge)
        assert s.project.id == "3018488"

    def test_env_project_beats_target(
        self,
        cm_with_active: ConfigManager,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """``MP_PROJECT_ID`` env beats target.project."""
        cm_with_active.add_target(
            "ecom", account="team", project="3018488", workspace=42
        )
        monkeypatch.setenv("MP_PROJECT_ID", "5555555")
        s = resolve_session(target="ecom", config=cm_with_active)
        assert s.project.id == "5555555"

    def test_env_project_beats_bridge(
        self,
        cm_with_active: ConfigManager,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """``MP_PROJECT_ID`` env beats bridge.project."""
        bridge = self._make_bridge(project="3018488")
        monkeypatch.setenv("MP_PROJECT_ID", "5555555")
        s = resolve_session(config=cm_with_active, bridge=bridge)
        assert s.project.id == "5555555"

    # ── Workspace axis ────────────────────────────────────────────────

    def test_bridge_workspace_beats_active(self, cm_with_active: ConfigManager) -> None:
        """bridge.workspace beats [active].workspace."""
        cm_with_active.set_active(workspace=99)
        bridge = self._make_bridge(project="3713224", workspace=42)
        s = resolve_session(config=cm_with_active, bridge=bridge)
        assert s.workspace is not None
        assert s.workspace.id == 42

    def test_target_workspace_beats_bridge(self, cm_with_active: ConfigManager) -> None:
        """target.workspace beats bridge.workspace."""
        cm_with_active.add_target(
            "ecom", account="team", project="3713224", workspace=77
        )
        bridge = self._make_bridge(project="3713224", workspace=42)
        s = resolve_session(target="ecom", config=cm_with_active, bridge=bridge)
        assert s.workspace is not None
        assert s.workspace.id == 77

    def test_env_workspace_beats_target(
        self,
        cm_with_active: ConfigManager,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """``MP_WORKSPACE_ID`` env beats target.workspace."""
        cm_with_active.add_target(
            "ecom", account="team", project="3713224", workspace=77
        )
        monkeypatch.setenv("MP_WORKSPACE_ID", "999")
        s = resolve_session(target="ecom", config=cm_with_active)
        assert s.workspace is not None
        assert s.workspace.id == 999

    def test_env_workspace_beats_bridge(
        self,
        cm_with_active: ConfigManager,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """``MP_WORKSPACE_ID`` env beats bridge.workspace."""
        bridge = self._make_bridge(project="3713224", workspace=42)
        monkeypatch.setenv("MP_WORKSPACE_ID", "999")
        s = resolve_session(config=cm_with_active, bridge=bridge)
        assert s.workspace is not None
        assert s.workspace.id == 999
