"""Unit tests for ``Workspace.use(...)`` per-axis switching (T033).

Per spec SC-006/SC-007/SC-008:
- ``use(workspace=N)`` is in-memory only (no API call, no config write)
- ``use(project=P)`` does NOT re-auth
- ``use(account=A)`` rebuilds auth header AND clears in-session project state (FR-033)
- HTTP transport (``id(ws._api_client._http)``) is preserved across all switches

Reference: specs/042-auth-architecture-redesign/contracts/python-api.md §3.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import SecretStr

from mixpanel_headless import accounts as accounts_ns
from mixpanel_headless import targets as targets_ns
from mixpanel_headless._internal.config import ConfigManager
from mixpanel_headless.workspace import Workspace


@pytest.fixture(autouse=True)
def _isolated_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Isolate $HOME and MP_CONFIG_PATH for hermetic tests."""
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("MP_CONFIG_PATH", str(tmp_path / ".mp" / "config.toml"))


@pytest.fixture
def two_accounts() -> ConfigManager:
    """Seed two service accounts, each with its own ``default_project``."""
    cm = ConfigManager()
    accounts_ns.add(
        "team",
        type="service_account",
        region="us",
        default_project="3713224",
        username="team.sa",
        secret=SecretStr("team-secret"),
    )
    accounts_ns.add(
        "other",
        type="service_account",
        region="eu",
        default_project="3713224",
        username="other.sa",
        secret=SecretStr("other-secret"),
    )
    cm.set_active(account="team")
    return cm


class TestUseWorkspace:
    """``ws.use(workspace=N)`` is an in-memory field update."""

    def test_workspace_changes(self, two_accounts: ConfigManager) -> None:
        """``ws.use(workspace=N)`` updates ``ws.workspace.id``."""
        ws = Workspace(account="team", project="3713224")
        ws.use(workspace=42)
        assert ws.workspace is not None
        assert ws.workspace.id == 42

    def test_chain_returns_self(self, two_accounts: ConfigManager) -> None:
        """``use`` returns ``self`` for fluent chaining."""
        ws = Workspace(account="team", project="3713224")
        assert ws.use(workspace=42) is ws


class TestUseProject:
    """``ws.use(project=P)`` does NOT re-auth (no auth header rebuild)."""

    def test_project_changes(self, two_accounts: ConfigManager) -> None:
        """``use(project=P)`` updates ``ws.project.id``."""
        ws = Workspace(account="team", project="3713224")
        ws.use(project="9999999")
        assert ws.project.id == "9999999"

    def test_account_unchanged(self, two_accounts: ConfigManager) -> None:
        """``use(project=P)`` preserves the account."""
        ws = Workspace(account="team", project="3713224")
        before = ws.account
        ws.use(project="9999999")
        assert ws.account == before


class TestUseAccount:
    """``ws.use(account=A)`` rebuilds the auth header (FR-033)."""

    def test_account_changes(self, two_accounts: ConfigManager) -> None:
        """``use(account=A)`` swaps to the new account."""
        ws = Workspace(account="team", project="3713224")
        ws.use(account="other")
        assert ws.account.name == "other"

    def test_account_change_uses_new_account_default_project(
        self, two_accounts: ConfigManager
    ) -> None:
        """Per FR-033, account swap re-resolves project from the NEW account.

        After ``use(account=B)`` without an explicit project, the project
        comes from ``B.default_project`` — never from the prior session.
        Cross-account project access is not guaranteed; the new account
        must own its project (or env override must be present).
        """
        ws = Workspace(account="team", project="3018488")
        ws.use(account="other")
        # `other.default_project` was seeded as "3713224" by the fixture.
        assert ws.project.id == "3713224"

    def test_account_swap_no_default_project_raises(
        self,
        two_accounts: ConfigManager,
    ) -> None:
        """Account swap to an account with no default_project raises ConfigError.

        Per FR-033, the prior session's project is never carried forward.
        If the new account lacks ``default_project`` and no env / explicit
        project is provided, the call MUST fail loudly with the standard
        four-paths-to-fix message.
        """
        from mixpanel_headless.exceptions import ConfigError

        accounts_ns.add("browser_only", type="oauth_browser", region="us")
        ws = Workspace(account="team", project="3018488")
        with pytest.raises(ConfigError):
            ws.use(account="browser_only")


class TestHTTPTransportPreservation:
    """HTTP transport is preserved across all use() switches (R5)."""

    def test_http_client_id_preserved_across_workspace_switch(
        self, two_accounts: ConfigManager
    ) -> None:
        """Workspace switch does NOT recreate the underlying httpx.Client."""
        ws = Workspace(account="team", project="3713224")
        client = ws._api_client  # noqa: SLF001 — test introspection
        assert client is not None
        before = id(client._http)  # noqa: SLF001
        ws.use(workspace=42)
        assert id(client._http) == before  # noqa: SLF001

    def test_http_client_id_preserved_across_project_switch(
        self, two_accounts: ConfigManager
    ) -> None:
        """Project switch does NOT recreate the underlying httpx.Client."""
        ws = Workspace(account="team", project="3713224")
        client = ws._api_client  # noqa: SLF001
        assert client is not None
        before = id(client._http)  # noqa: SLF001
        ws.use(project="9999999")
        assert id(client._http) == before  # noqa: SLF001

    def test_http_client_id_preserved_across_account_switch(
        self, two_accounts: ConfigManager
    ) -> None:
        """Account switch does NOT recreate the underlying httpx.Client."""
        ws = Workspace(account="team", project="3713224")
        client = ws._api_client  # noqa: SLF001
        assert client is not None
        before = id(client._http)  # noqa: SLF001
        ws.use(account="other")
        assert id(client._http) == before  # noqa: SLF001


class TestTargetMutualExclusion:
    """``target=`` is mutually exclusive with ``account=``/``project=``/``workspace=``."""

    def test_target_with_account_raises(self, two_accounts: ConfigManager) -> None:
        """``use(target=T, account=A)`` raises ValueError."""
        targets_ns.add("ecom", account="team", project="3018488")
        ws = Workspace(account="team", project="3713224")
        with pytest.raises(ValueError):
            ws.use(target="ecom", account="other")

    def test_target_alone_applies_three_axes(self, two_accounts: ConfigManager) -> None:
        """``use(target=T)`` alone applies all three axes from the target."""
        targets_ns.add("ecom", account="other", project="3018488", workspace=42)
        ws = Workspace(account="team", project="3713224")
        ws.use(target="ecom")
        assert ws.account.name == "other"
        assert ws.project.id == "3018488"
        assert ws.workspace is not None
        assert ws.workspace.id == 42


class TestPersist:
    """``persist=True`` writes the new state to ``[active]``."""

    def test_persist_writes_active(self, two_accounts: ConfigManager) -> None:
        """``use(account=A, project=P, persist=True)`` writes to [active]."""
        ws = Workspace(account="team", project="3713224")
        ws.use(account="other", persist=True)
        assert two_accounts.get_active().account == "other"

    def test_persist_clears_stale_workspace_when_session_workspace_is_none(
        self, two_accounts: ConfigManager
    ) -> None:
        """``persist=True`` with cleared workspace MUST drop ``[active].workspace``.

        Regression: ``set_active(workspace=None)`` is treated as "do not
        touch" (per FR-016 axis-independence). A ``ws.use(account=…,
        persist=True)`` that cleared the workspace previously left the
        prior ``[active].workspace`` on disk, so a fresh ``Workspace()``
        resolved against the wrong workspace.
        """
        # Pre-populate [active].workspace so we can prove the clear works.
        two_accounts.set_active(workspace=42)
        assert two_accounts.get_active().workspace == 42
        ws = Workspace(account="team", project="3713224")
        # Account swap clears the in-session workspace per FR-033.
        ws.use(account="other", persist=True)
        assert ws.workspace is None
        # And [active].workspace must also be cleared on disk.
        assert two_accounts.get_active().workspace is None


class TestUseAccountEnvVarPriority:
    """``use(account=A)`` re-resolves project/workspace per FR-017.

    When swapping account, env-var inputs (``MP_PROJECT_ID``,
    ``MP_WORKSPACE_ID``) must take precedence over the prior session's
    project / the global ``[active]`` block. The previous implementation
    consulted only ``[active]`` and so silently ignored env overrides.
    """

    def test_account_swap_honors_mp_project_id(
        self,
        two_accounts: ConfigManager,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """``MP_PROJECT_ID`` overrides the new account's ``default_project``."""
        monkeypatch.setenv("MP_PROJECT_ID", "5555555")
        ws = Workspace(account="team", project="3713224")
        ws.use(account="other")
        assert ws.account.name == "other"
        assert ws.project.id == "5555555"

    def test_account_swap_honors_mp_workspace_id(
        self,
        two_accounts: ConfigManager,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """``MP_WORKSPACE_ID`` is applied on account swap when set."""
        monkeypatch.setenv("MP_WORKSPACE_ID", "987")
        ws = Workspace(account="team", project="3713224")
        ws.use(account="other")
        assert ws.workspace is not None
        assert ws.workspace.id == 987


class TestUseUpdatesSessionAndClearsCaches:
    """``ws.use(...)`` MUST update the bound Session and clear lazy services.

    Regression: ``use()`` previously updated only the API client's session,
    leaving ``_me_svc`` / ``_discovery`` / ``_live_query`` serving cached
    state from before the swap.
    """

    def test_use_project_updates_session_project_id(
        self, two_accounts: ConfigManager
    ) -> None:
        """After ``use(project=X)``, ``self.session.project.id == X``."""
        ws = Workspace(account="team", project="3713224")
        assert ws.session.project.id == "3713224"
        ws.use(project="9999999")
        assert ws.session.project.id == "9999999"

    def test_use_account_updates_session_region(
        self, two_accounts: ConfigManager
    ) -> None:
        """After ``use(account=B)``, the bound session reflects B's region."""
        ws = Workspace(account="team", project="3713224")
        ws.use(account="other")
        # `other` is in eu region per the fixture.
        assert ws.session.account.region == "eu"

    def test_use_clears_discovery_and_me_service_caches(
        self, two_accounts: ConfigManager
    ) -> None:
        """``use(...)`` resets ``_discovery``, ``_live_query``, ``_me_service``."""
        ws = Workspace(account="team", project="3713224")
        # Force-create the cached services.
        _ = ws._discovery_service  # noqa: SLF001
        _ = ws._live_query_service  # noqa: SLF001
        _ = ws._me_svc  # noqa: SLF001
        assert ws._discovery is not None  # noqa: SLF001
        assert ws._live_query is not None  # noqa: SLF001
        assert ws._me_service is not None  # noqa: SLF001

        ws.use(project="9999999")

        # All three caches MUST be cleared so subsequent reads rebuild
        # against the new session.
        assert ws._discovery is None  # noqa: SLF001
        assert ws._live_query is None  # noqa: SLF001
        assert ws._me_service is None  # noqa: SLF001

    def test_use_target_also_clears_caches(self, two_accounts: ConfigManager) -> None:
        """The ``target=`` branch of ``use()`` also clears caches."""
        targets_ns.add("ecom", account="other", project="3018488", workspace=42)
        ws = Workspace(account="team", project="3713224")
        _ = ws._discovery_service  # noqa: SLF001
        assert ws._discovery is not None  # noqa: SLF001
        ws.use(target="ecom")
        assert ws._discovery is None  # noqa: SLF001
        assert ws.session.project.id == "3018488"

    def test_use_account_updates_me_cache_account_name(
        self, two_accounts: ConfigManager
    ) -> None:
        """``use(account=B)`` retargets ``MeCache`` at ``B``'s storage dir.

        Regression: ``use()`` reset ``_me_service`` but never updated
        ``self._account_name``. The lazy ``_me_svc`` property then
        constructed ``MeCache(account_name=self._account_name)`` with the
        prior account, so post-swap ``/me`` calls read/wrote
        ``~/.mp/accounts/<old>/me.json`` against the new account's
        session — silently corrupting both caches.
        """
        ws = Workspace(account="team", project="3713224")
        # Force MeCache lazy creation while bound to "team".
        first = ws._me_svc  # noqa: SLF001
        assert first._cache._account_name == "team"  # noqa: SLF001
        ws.use(account="other")
        # New MeService must rebuild against "other", not "team".
        second = ws._me_svc  # noqa: SLF001
        assert second._cache._account_name == "other"  # noqa: SLF001

    def test_use_target_updates_me_cache_account_name(
        self, two_accounts: ConfigManager
    ) -> None:
        """``use(target=T)`` also retargets ``MeCache`` (target may swap account)."""
        targets_ns.add("ecom", account="other", project="3018488", workspace=42)
        ws = Workspace(account="team", project="3713224")
        first = ws._me_svc  # noqa: SLF001
        assert first._cache._account_name == "team"  # noqa: SLF001
        ws.use(target="ecom")
        second = ws._me_svc  # noqa: SLF001
        assert second._cache._account_name == "other"  # noqa: SLF001


class TestUseTargetEnvOverride:
    """``use(target=T)`` MUST honor env vars per FR-017 (env > target)."""

    def test_mp_project_id_beats_target_project(
        self,
        two_accounts: ConfigManager,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Construction routes through ``resolve_session`` which honors env;
        ``use(target=)`` must do the same. Without this, in-session env
        overrides set after construction would silently be ignored on a
        target swap.
        """
        targets_ns.add("ecom", account="other", project="3018488", workspace=42)
        ws = Workspace(account="team", project="3713224")
        monkeypatch.setenv("MP_PROJECT_ID", "5555555")
        ws.use(target="ecom")
        # Target says project=3018488, but MP_PROJECT_ID overrides per FR-017.
        assert ws.project.id == "5555555"
        # Account / workspace still come from the target.
        assert ws.account.name == "other"
        assert ws.workspace is not None
        assert ws.workspace.id == 42

    def test_mp_workspace_id_beats_target_workspace(
        self,
        two_accounts: ConfigManager,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """``MP_WORKSPACE_ID`` overrides the target's workspace."""
        targets_ns.add("ecom", account="other", project="3018488", workspace=42)
        ws = Workspace(account="team", project="3713224")
        monkeypatch.setenv("MP_WORKSPACE_ID", "987")
        ws.use(target="ecom")
        assert ws.workspace is not None
        assert ws.workspace.id == 987


class TestUseAccountWorkspaceEnvValidation:
    """``use(account=)`` MUST validate ``MP_WORKSPACE_ID`` like construction.

    The previous inline ``isdigit() and int(env_ws) > 0`` check silently
    swallowed invalid values (e.g. ``-1``); the canonical
    :func:`env_workspace_id` raises :class:`ConfigError` on the same input.
    Both code paths must agree so that an env-var typo surfaces consistently.
    """

    def test_invalid_negative_mp_workspace_id_raises(
        self,
        two_accounts: ConfigManager,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """``MP_WORKSPACE_ID=-1`` must raise on account swap, not silently clear."""
        from mixpanel_headless.exceptions import ConfigError

        ws = Workspace(account="team", project="3713224")
        monkeypatch.setenv("MP_WORKSPACE_ID", "-1")
        with pytest.raises(ConfigError, match="MP_WORKSPACE_ID"):
            ws.use(account="other")

    def test_invalid_non_int_mp_workspace_id_raises(
        self,
        two_accounts: ConfigManager,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """``MP_WORKSPACE_ID=abc`` must raise on account swap."""
        from mixpanel_headless.exceptions import ConfigError

        ws = Workspace(account="team", project="3713224")
        monkeypatch.setenv("MP_WORKSPACE_ID", "abc")
        with pytest.raises(ConfigError, match="MP_WORKSPACE_ID"):
            ws.use(account="other")
