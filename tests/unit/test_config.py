"""Unit tests for the ``ConfigManager``.

The ConfigManager operates on a single TOML schema with three sections:
``[active]``, ``[accounts.NAME]``, ``[targets.NAME]``, plus optional
``[settings]``. The ``[active]`` block holds only ``account`` and
``workspace`` — project lives on the account as ``default_project``.

Reference: specs/042-auth-architecture-redesign/contracts/config-schema.md §1.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import SecretStr

from mixpanel_headless._internal.auth.account import (
    OAuthBrowserAccount,
    OAuthTokenAccount,
    ServiceAccount,
    TargetName,
)
from mixpanel_headless._internal.auth.session import ActiveSession
from mixpanel_headless._internal.config import ConfigManager
from mixpanel_headless.exceptions import ConfigError
from mixpanel_headless.types import AccountSummary, Target

# Path to the fixture corpus (constructed from project root).
_FIXTURE_DIR = Path(__file__).parent.parent / "fixtures" / "configs"


@pytest.fixture
def empty_config_path(tmp_path: Path) -> Path:
    """Return a path to a non-existent config file (test load-from-missing)."""
    return tmp_path / "config.toml"


@pytest.fixture
def cm(empty_config_path: Path) -> ConfigManager:
    """Return a fresh v3 ConfigManager pointing at a tmp empty path."""
    return ConfigManager(config_path=empty_config_path)


class TestLoadEmptyOrMissing:
    """``load`` over an empty or missing file returns a clean state."""

    def test_load_missing_file(self, cm: ConfigManager) -> None:
        """No config file → empty accounts/targets, empty active."""
        assert cm.list_accounts() == []
        assert cm.list_targets() == []
        active = cm.get_active()
        assert active == ActiveSession()

    def test_load_empty_file(self, tmp_path: Path) -> None:
        """An empty TOML file is also valid (no sections) — no errors."""
        p = tmp_path / "config.toml"
        p.write_text("", encoding="utf-8")
        cm = ConfigManager(config_path=p)
        assert cm.list_accounts() == []
        assert cm.list_targets() == []
        assert cm.get_active() == ActiveSession()


class TestAddAccount:
    """``add_account`` writes ``[accounts.NAME]`` blocks."""

    def test_service_account(self, cm: ConfigManager) -> None:
        """ServiceAccount round-trips through the file (with default_project)."""
        cm.add_account(
            "team",
            type="service_account",
            region="us",
            default_project="3713224",
            username="sa.user",
            secret=SecretStr("super-secret"),
        )
        cm2 = ConfigManager(config_path=cm.config_path)
        accounts = cm2.list_accounts()
        assert len(accounts) == 1
        assert accounts[0].name == "team"
        assert accounts[0].type == "service_account"
        assert accounts[0].region == "us"
        loaded = cm2.get_account("team")
        assert isinstance(loaded, ServiceAccount)
        assert loaded.username == "sa.user"
        assert loaded.secret.get_secret_value() == "super-secret"
        assert loaded.default_project == "3713224"

    def test_oauth_browser_account(self, cm: ConfigManager) -> None:
        """OAuthBrowserAccount has no inline secret — only name+region (+optional default_project)."""
        cm.add_account("personal", type="oauth_browser", region="eu")
        cm2 = ConfigManager(config_path=cm.config_path)
        loaded = cm2.get_account("personal")
        assert isinstance(loaded, OAuthBrowserAccount)
        assert loaded.region == "eu"
        assert loaded.default_project is None

    def test_oauth_token_with_inline(self, cm: ConfigManager) -> None:
        """OAuthTokenAccount with inline token + default_project round-trips."""
        cm.add_account(
            "ci",
            type="oauth_token",
            region="us",
            default_project="3713224",
            token=SecretStr("ey.tok"),
        )
        cm2 = ConfigManager(config_path=cm.config_path)
        loaded = cm2.get_account("ci")
        assert isinstance(loaded, OAuthTokenAccount)
        assert loaded.token is not None
        assert loaded.token.get_secret_value() == "ey.tok"
        assert loaded.token_env is None
        assert loaded.default_project == "3713224"

    def test_oauth_token_with_env(self, cm: ConfigManager) -> None:
        """OAuthTokenAccount with token_env + default_project round-trips."""
        cm.add_account(
            "agent",
            type="oauth_token",
            region="eu",
            default_project="3713224",
            token_env="MP_OAUTH_TOKEN",
        )
        cm2 = ConfigManager(config_path=cm.config_path)
        loaded = cm2.get_account("agent")
        assert isinstance(loaded, OAuthTokenAccount)
        assert loaded.token is None
        assert loaded.token_env == "MP_OAUTH_TOKEN"

    def test_service_account_without_default_project_succeeds(
        self, cm: ConfigManager
    ) -> None:
        """Per 043 FR-001: SA may omit ``default_project`` at add-time.

        Inverts the 042 hard requirement so a brand-new SA can be
        registered before the user knows which project to bind to.
        ``mp project list`` discovers the available projects via /me;
        ``mp project use ID`` then sets the active project.
        """
        cm.add_account(
            "team",
            type="service_account",
            region="us",
            username="u",
            secret=SecretStr("s"),
        )
        assert cm.get_account("team").default_project is None

    def test_oauth_token_without_default_project_succeeds(
        self, cm: ConfigManager
    ) -> None:
        """Per 043 FR-001: oauth_token may omit ``default_project``.

        Same relaxation as service_account; the bearer token is enough
        to register the account, with the project chosen later.
        """
        cm.add_account(
            "ci",
            type="oauth_token",
            region="us",
            token=SecretStr("ey.tok"),
        )
        assert cm.get_account("ci").default_project is None

    def test_duplicate_name_raises(self, cm: ConfigManager) -> None:
        """Adding an existing name raises ConfigError."""
        cm.add_account(
            "x",
            type="service_account",
            region="us",
            default_project="3713224",
            username="u",
            secret=SecretStr("s"),
        )
        with pytest.raises(ConfigError):
            cm.add_account("x", type="oauth_browser", region="us")

    def test_invalid_name_raises(self, cm: ConfigManager) -> None:
        """Names violating the pattern raise ConfigError."""
        with pytest.raises((ConfigError, ValueError)):
            cm.add_account(
                "bad name",  # space is invalid
                type="service_account",
                region="us",
                default_project="3713224",
                username="u",
                secret=SecretStr("s"),
            )


class TestUpdateAccount:
    """``update_account`` mutates fields in place."""

    def test_update_default_project(self, cm: ConfigManager) -> None:
        """Updating ``default_project`` rewrites the account's home project."""
        cm.add_account(
            "team",
            type="service_account",
            region="us",
            default_project="3713224",
            username="u",
            secret=SecretStr("s"),
        )
        cm.update_account("team", default_project="9999999")
        loaded = cm.get_account("team")
        assert loaded.default_project == "9999999"

    def test_update_region(self, cm: ConfigManager) -> None:
        """Region updates work for any account type."""
        cm.add_account("personal", type="oauth_browser", region="us")
        cm.update_account("personal", region="eu")
        assert cm.get_account("personal").region == "eu"

    def test_update_missing_account_raises(self, cm: ConfigManager) -> None:
        """Updating a non-existent account raises."""
        with pytest.raises(ConfigError):
            cm.update_account("ghost", default_project="1")

    def test_update_username_on_browser_raises(self, cm: ConfigManager) -> None:
        """``username=`` on an oauth_browser account raises."""
        cm.add_account("personal", type="oauth_browser", region="us")
        with pytest.raises(ConfigError):
            cm.update_account("personal", username="u")


class TestSetActive:
    """``set_active`` writes ``[active]`` (account + workspace only)."""

    def test_set_account_only(self, cm: ConfigManager) -> None:
        """Setting account axis writes only that key."""
        cm.add_account(
            "x",
            type="service_account",
            region="us",
            default_project="3713224",
            username="u",
            secret=SecretStr("s"),
        )
        cm.set_active(account="x")
        assert cm.get_active() == ActiveSession(account="x")

    def test_set_workspace_only(self, cm: ConfigManager) -> None:
        """Setting workspace axis writes only that key."""
        cm.set_active(workspace=8)
        assert cm.get_active() == ActiveSession(workspace=8)

    def test_set_both(self, cm: ConfigManager) -> None:
        """Setting both axes in one call."""
        cm.add_account(
            "x",
            type="service_account",
            region="us",
            default_project="3713224",
            username="u",
            secret=SecretStr("s"),
        )
        cm.set_active(account="x", workspace=8)
        active = cm.get_active()
        assert active.account == "x"
        assert active.workspace == 8

    def test_account_must_exist(self, cm: ConfigManager) -> None:
        """Setting active.account to a missing account raises ConfigError."""
        with pytest.raises(ConfigError):
            cm.set_active(account="nonexistent")

    def test_workspace_must_be_positive(self, cm: ConfigManager) -> None:
        """``workspace`` axis must be > 0."""
        with pytest.raises(ConfigError):
            cm.set_active(workspace=0)
        with pytest.raises(ConfigError):
            cm.set_active(workspace=-5)

    def test_partial_update_preserves_other_axis(self, cm: ConfigManager) -> None:
        """``set_active(workspace=...)`` does NOT touch existing account."""
        cm.add_account(
            "x",
            type="service_account",
            region="us",
            default_project="3713224",
            username="u",
            secret=SecretStr("s"),
        )
        cm.set_active(account="x")
        cm.set_active(workspace=8)
        active = cm.get_active()
        assert active.account == "x"
        assert active.workspace == 8


class TestApplySession:
    """``apply_session`` atomically writes account/project/workspace in one transaction."""

    def _seed(self, cm: ConfigManager, name: str = "x") -> None:
        """Insert a service_account named ``name`` for use in apply_session tests."""
        cm.add_account(
            name,
            type="service_account",
            region="us",
            default_project="100",
            username="u",
            secret=SecretStr("s"),
        )

    def test_atomic_three_axis_write(self, cm: ConfigManager) -> None:
        """Single call writes account, workspace, and account.default_project."""
        self._seed(cm)
        cm.apply_session(account="x", project="200", workspace=42)
        active = cm.get_active()
        assert active.account == "x"
        assert active.workspace == 42
        assert cm.get_account("x").default_project == "200"

    def test_clear_workspace_drops_active_workspace_axis(
        self, cm: ConfigManager
    ) -> None:
        """``clear_workspace=True`` removes ``[active].workspace`` even without ``workspace=``."""
        self._seed(cm)
        cm.set_active(account="x", workspace=99)
        cm.apply_session(account="x", project="100", clear_workspace=True)
        active = cm.get_active()
        assert active.account == "x"
        assert active.workspace is None

    def test_workspace_and_clear_workspace_mutually_exclusive(
        self, cm: ConfigManager
    ) -> None:
        """Passing both ``workspace=`` and ``clear_workspace=True`` raises ValueError."""
        self._seed(cm)
        with pytest.raises(ValueError, match="mutually exclusive"):
            cm.apply_session(
                account="x", project="100", workspace=42, clear_workspace=True
            )

    def test_project_without_active_or_explicit_account_raises(
        self, cm: ConfigManager
    ) -> None:
        """``project=`` with no active account and no explicit ``account=`` raises ConfigError."""
        with pytest.raises(ConfigError, match="no active account"):
            cm.apply_session(project="100")

    def test_project_writes_to_explicit_account_not_active(
        self, cm: ConfigManager
    ) -> None:
        """When ``account=`` and ``project=`` are both passed, project lands on the EXPLICIT account."""
        self._seed(cm, "x")
        self._seed(cm, "y")
        cm.set_active(account="x")
        cm.apply_session(account="y", project="500")
        # 'y' got the project; 'x' kept its original.
        assert cm.get_account("y").default_project == "500"
        assert cm.get_account("x").default_project == "100"

    def test_partial_update_preserves_untouched_axes(self, cm: ConfigManager) -> None:
        """``apply_session(workspace=)`` preserves account / project."""
        self._seed(cm)
        cm.set_active(account="x", workspace=10)
        cm.apply_session(workspace=99)
        active = cm.get_active()
        assert active.account == "x"
        assert active.workspace == 99
        assert cm.get_account("x").default_project == "100"


class TestTargets:
    """``add_target`` / ``list_targets`` / ``get_target`` / ``apply_target``."""

    def test_add_target_minimal(self, cm: ConfigManager) -> None:
        """Target with no workspace omits the workspace key."""
        cm.add_account(
            "x",
            type="service_account",
            region="us",
            default_project="3713224",
            username="u",
            secret=SecretStr("s"),
        )
        cm.add_target("ecom", account="x", project="3018488")
        targets = cm.list_targets()
        assert len(targets) == 1
        assert targets[0] == Target(name="ecom", account="x", project="3018488")

    def test_add_target_with_workspace(self, cm: ConfigManager) -> None:
        """Target with workspace persists all three fields."""
        cm.add_account(
            "x",
            type="service_account",
            region="us",
            default_project="3713224",
            username="u",
            secret=SecretStr("s"),
        )
        cm.add_target("ecom", account="x", project="3018488", workspace=42)
        t = cm.get_target("ecom")
        assert t.workspace == 42

    def test_add_target_referencing_missing_account_raises(
        self, cm: ConfigManager
    ) -> None:
        """Adding a target that references a non-existent account raises."""
        with pytest.raises(ConfigError):
            cm.add_target("ecom", account="nonexistent", project="3018488")

    def test_remove_target(self, cm: ConfigManager) -> None:
        """``remove_target`` deletes the entry; subsequent get_target raises."""
        cm.add_account(
            "x",
            type="service_account",
            region="us",
            default_project="3713224",
            username="u",
            secret=SecretStr("s"),
        )
        cm.add_target("ecom", account="x", project="3018488")
        cm.remove_target("ecom")
        with pytest.raises(ConfigError):
            cm.get_target("ecom")

    def test_apply_target_writes_account_workspace_and_default_project(
        self, cm: ConfigManager
    ) -> None:
        """``apply_target`` writes account+workspace to ``[active]`` AND
        sets the target account's ``default_project`` to the target's project.
        """
        cm.add_account(
            "x",
            type="service_account",
            region="us",
            default_project="3713224",
            username="u",
            secret=SecretStr("s"),
        )
        cm.add_target("ecom", account="x", project="3018488", workspace=8)
        cm.apply_target("ecom")
        active = cm.get_active()
        assert active.account == "x"
        assert active.workspace == 8
        # Project went onto the account, not into [active].
        assert cm.get_account("x").default_project == "3018488"

    def test_apply_target_missing_workspace_clears_workspace(
        self, cm: ConfigManager
    ) -> None:
        """Applying a target with no workspace clears any prior workspace."""
        cm.add_account(
            "x",
            type="service_account",
            region="us",
            default_project="3713224",
            username="u",
            secret=SecretStr("s"),
        )
        cm.set_active(account="x", workspace=99)
        cm.add_target("nows", account="x", project="3018488")
        cm.apply_target("nows")
        active = cm.get_active()
        assert active.workspace is None
        # Project goes to the account.
        assert cm.get_account("x").default_project == "3018488"

    def test_apply_missing_target_raises(self, cm: ConfigManager) -> None:
        """``apply_target`` against an unknown target raises ConfigError."""
        with pytest.raises(ConfigError):
            cm.apply_target("ghost")


class TestListAccounts:
    """``list_accounts`` returns ``AccountSummary`` records."""

    def test_returns_summary_objects(self, cm: ConfigManager) -> None:
        """Every entry is an AccountSummary with the right fields."""
        cm.add_account(
            "team",
            type="service_account",
            region="us",
            default_project="3713224",
            username="u",
            secret=SecretStr("s"),
        )
        cm.add_account("personal", type="oauth_browser", region="eu")
        summaries = cm.list_accounts()
        assert all(isinstance(a, AccountSummary) for a in summaries)
        names = sorted(a.name for a in summaries)
        assert names == ["personal", "team"]

    def test_is_active_flag(self, cm: ConfigManager) -> None:
        """``is_active`` reflects ``[active].account``."""
        cm.add_account(
            "team",
            type="service_account",
            region="us",
            default_project="3713224",
            username="u",
            secret=SecretStr("s"),
        )
        cm.add_account("personal", type="oauth_browser", region="us")
        cm.set_active(account="team")
        by_name = {a.name: a for a in cm.list_accounts()}
        assert by_name["team"].is_active is True
        assert by_name["personal"].is_active is False

    def test_referenced_by_targets(self, cm: ConfigManager) -> None:
        """``referenced_by_targets`` lists target names referencing the account."""
        cm.add_account(
            "x",
            type="service_account",
            region="us",
            default_project="3713224",
            username="u",
            secret=SecretStr("s"),
        )
        cm.add_target("ecom", account="x", project="3018488")
        cm.add_target("ai", account="x", project="3713224")
        summary = next(a for a in cm.list_accounts() if a.name == "x")
        assert sorted(summary.referenced_by_targets) == ["ai", "ecom"]


class TestRemoveAccount:
    """``remove_account`` raises ``AccountInUseError`` when targets depend on it."""

    def test_remove_unused(self, cm: ConfigManager) -> None:
        """An unreferenced account is removable without force."""
        cm.add_account(
            "x",
            type="service_account",
            region="us",
            default_project="3713224",
            username="u",
            secret=SecretStr("s"),
        )
        orphans = cm.remove_account("x")
        assert orphans == []
        assert cm.list_accounts() == []

    def test_remove_referenced_without_force_raises(self, cm: ConfigManager) -> None:
        """Removing a referenced account without ``force`` raises."""
        from mixpanel_headless.exceptions import AccountInUseError

        cm.add_account(
            "x",
            type="service_account",
            region="us",
            default_project="3713224",
            username="u",
            secret=SecretStr("s"),
        )
        cm.add_target("ecom", account="x", project="3018488")
        with pytest.raises(AccountInUseError):
            cm.remove_account("x")

    def test_remove_with_force_returns_orphans(self, cm: ConfigManager) -> None:
        """``remove_account(force=True)`` returns the names of orphaned targets."""
        cm.add_account(
            "x",
            type="service_account",
            region="us",
            default_project="3713224",
            username="u",
            secret=SecretStr("s"),
        )
        cm.add_target("ecom", account="x", project="3018488")
        cm.add_target("ai", account="x", project="3713224")
        orphans = cm.remove_account("x", force=True)
        assert sorted(orphans) == ["ai", "ecom"]

    def test_remove_active_account_clears_active_block(self, cm: ConfigManager) -> None:
        """Removing the active account also clears `[active].account/.workspace`.

        Otherwise `session.show()` keeps printing the deleted name and a
        fresh `Workspace()` resolves through `get_active().account` into
        ``ConfigError("Account 'X' not found.")``.
        """
        cm.add_account(
            "x",
            type="service_account",
            region="us",
            default_project="3713224",
            username="u",
            secret=SecretStr("s"),
        )
        cm.set_active(account="x", workspace=42)
        assert cm.get_active() == ActiveSession(account="x", workspace=42)

        cm.remove_account("x")

        # Both fields cleared (workspace is project-scoped; meaningless
        # without the account).
        assert cm.get_active() == ActiveSession()

    def test_remove_non_active_account_preserves_active_block(
        self, cm: ConfigManager
    ) -> None:
        """Removing a non-active account leaves `[active]` untouched."""
        cm.add_account(
            "active_one",
            type="service_account",
            region="us",
            default_project="3713224",
            username="u1",
            secret=SecretStr("s"),
        )
        cm.add_account(
            "other",
            type="service_account",
            region="us",
            default_project="3018488",
            username="u2",
            secret=SecretStr("s"),
        )
        cm.set_active(account="active_one", workspace=42)

        cm.remove_account("other")

        assert cm.get_active() == ActiveSession(account="active_one", workspace=42)


class TestFixtureLoad:
    """The golden fixtures load cleanly with the expected shape."""

    def test_simple(self, tmp_path: Path) -> None:
        """``simple.toml`` loads with project on the account, workspace in [active]."""
        src = _FIXTURE_DIR / "simple.toml"
        dst = tmp_path / "config.toml"
        dst.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
        cm = ConfigManager(config_path=dst)
        accounts = cm.list_accounts()
        assert len(accounts) == 1
        assert accounts[0].name == "demo-sa"
        active = cm.get_active()
        assert active.account == "demo-sa"
        assert active.workspace == 3448413
        loaded = cm.get_account("demo-sa")
        assert loaded.default_project == "3713224"

    def test_multi(self, tmp_path: Path) -> None:
        """``multi.toml`` loads three accounts of distinct types + two targets."""
        src = _FIXTURE_DIR / "multi.toml"
        dst = tmp_path / "config.toml"
        dst.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
        cm = ConfigManager(config_path=dst)
        accounts = {a.name: a for a in cm.list_accounts()}
        assert accounts["team"].type == "service_account"
        assert accounts["personal"].type == "oauth_browser"
        assert accounts["ci"].type == "oauth_token"
        targets = {t.name: t for t in cm.list_targets()}
        # NewType keys are str at runtime — index with cast literals.
        assert targets[TargetName("ecom")].workspace == 3448414
        assert targets[TargetName("ai")].workspace is None


class TestSettingsCustomHeader:
    """``[settings].custom_header`` round-trips through ``ConfigManager``."""

    def test_custom_header_round_trip(self, cm: ConfigManager) -> None:
        """``set_custom_header`` and ``get_custom_header`` are inverses."""
        cm.set_custom_header(name="X-Mixpanel-Cluster", value="internal-1")
        cm2 = ConfigManager(config_path=cm.config_path)
        header = cm2.get_custom_header()
        assert header == ("X-Mixpanel-Cluster", "internal-1")

    def test_get_custom_header_when_absent(self, cm: ConfigManager) -> None:
        """``get_custom_header`` returns None when no header is set."""
        assert cm.get_custom_header() is None


class TestMutateTransaction:
    """``_mutate()`` collapses N read-modify-write cycles into one transaction."""

    def test_single_write_per_transaction(self, cm: ConfigManager) -> None:
        """A multi-call _mutate() block performs exactly one disk write."""
        # Seed the file so subsequent writes go through atomic_write_bytes.
        cm.add_account(
            "x",
            type="service_account",
            region="us",
            default_project="123",
            username="u",
            secret=SecretStr("s"),
        )

        from unittest.mock import patch

        with patch(
            "mixpanel_headless._internal.config.atomic_write_bytes"
        ) as mock_write:
            with cm._mutate() as raw:
                cm._apply_set_active(raw, account="x", workspace=42)
                cm._apply_update_account(raw, "x", default_project="456")
            assert mock_write.call_count == 1

    def test_aborted_transaction_does_not_write(self, cm: ConfigManager) -> None:
        """An exception inside the body skips the write entirely."""
        cm.add_account(
            "x",
            type="service_account",
            region="us",
            default_project="123",
            username="u",
            secret=SecretStr("s"),
        )
        original = cm.config_path.read_bytes()

        with pytest.raises(RuntimeError, match="boom"), cm._mutate() as raw:
            cm._apply_set_active(raw, account="x", workspace=42)
            raise RuntimeError("boom")

        # Disk state preserved — no partial mutation reached the file.
        assert cm.config_path.read_bytes() == original
        assert cm.get_active() == ActiveSession()

    def test_multi_call_atomicity_on_validation_failure(
        self, cm: ConfigManager
    ) -> None:
        """A failed step late in a transaction discards earlier mutations."""
        cm.add_account(
            "x",
            type="service_account",
            region="us",
            default_project="123",
            username="u",
            secret=SecretStr("s"),
        )

        with (
            pytest.raises(ConfigError, match="not configured"),
            cm._mutate() as raw,
        ):
            cm._apply_update_account(raw, "x", default_project="999")
            # This raises — the prior _apply_update_account must NOT persist.
            cm._apply_set_active(raw, account="missing-account")

        # default_project unchanged on disk.
        cm2 = ConfigManager(config_path=cm.config_path)
        account = cm2.get_account("x")
        assert account.default_project == "123"

    def test_legacy_v2_blocks_block_writes_no_partial_persist(
        self, tmp_path: Path
    ) -> None:
        """A v2-shaped on-disk config rejects new add_account writes — no partial persist.

        Reproduces the latent flaw where ``_mutate`` would rewrite the
        file with a new ``[accounts.NEW]`` block even when sibling on-disk
        blocks were unparseable under the v3 schema (e.g., a leftover v2
        account missing the ``type`` discriminator). The exit-time
        whole-file validator must catch the bad sibling and skip the
        write.
        """
        p = tmp_path / "config.toml"
        # Legacy v2 account block missing the v3 ``type`` discriminator.
        p.write_text(
            "[accounts.legacy]\n"
            'username = "u"\n'
            'secret = "s"\n'
            'project_id = "111"\n'
            'region = "us"\n',
            encoding="utf-8",
        )
        original = p.read_bytes()
        cm = ConfigManager(config_path=p)

        with pytest.raises(ConfigError, match=r"\[accounts\.legacy\]"):
            cm.add_account("fresh", type="oauth_browser", region="us")

        # File untouched — no partial mutation reached disk.
        assert p.read_bytes() == original
