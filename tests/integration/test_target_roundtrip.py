"""Target roundtrip integration tests (T072, US6, FR-013, FR-033).

Phase 6 integration coverage that bridges the Python ``mp.targets`` namespace,
the ``mp target`` CLI, and ``Workspace.use(target=...)``. Verifies:

1. **Python apply ↔ persisted state**: ``mp.targets.use(NAME)`` updates
   ``[active]`` (account, workspace) AND the target account's
   ``default_project`` so a subsequent ``mp.session.show()`` reflects all
   three axes, with no other accounts or fields perturbed.
2. **CLI apply ↔ Python read**: A subprocess ``mp target use NAME`` followed
   by an in-process ``Workspace()`` resolves to the same session.
3. **Atomicity (T075)**: ``mp.targets.use(NAME)`` writes the config in a
   single ``_mutate`` transaction (one read + one write), not three
   serialized updates that could leave a partially-applied state if the
   process died between them.
4. **Construction-path equivalence**: ``Workspace().use(target=NAME)`` and
   ``Workspace(target=NAME)`` produce the same Session shape (the
   per-axis arguments and the named-target shortcut are interchangeable).

Reference: specs/042-auth-architecture-redesign/spec.md US6 acceptance
scenarios 1-2; tasks.md T072, T075.
"""

from __future__ import annotations

import json
import os
import subprocess
from collections.abc import Generator
from pathlib import Path
from unittest.mock import patch

import pytest

from mixpanel_headless import Workspace
from mixpanel_headless import accounts as accounts_ns
from mixpanel_headless import session as session_ns
from mixpanel_headless import targets as targets_ns
from mixpanel_headless._internal.config import ConfigManager

REPO_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def isolated_home(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Generator[Path, None, None]:
    """Yield a tmp HOME with isolated ``MP_CONFIG_PATH``; clear conflicting env vars."""
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("MP_CONFIG_PATH", str(tmp_path / ".mp" / "config.toml"))
    # Resolver consults env first; clear anything that could short-circuit
    # the per-axis chain so the test asserts pure config-file state.
    for var in (
        "MP_USERNAME",
        "MP_SECRET",
        "MP_OAUTH_TOKEN",
        "MP_REGION",
        "MP_PROJECT_ID",
        "MP_WORKSPACE_ID",
        "MP_ACCOUNT",
        "MP_TARGET",
        "MP_AUTH_FILE",
    ):
        monkeypatch.delenv(var, raising=False)
    yield tmp_path


@pytest.fixture
def two_accounts(isolated_home: Path) -> ConfigManager:
    """Seed config with two SA accounts: ``team`` (default-project 100) and ``personal`` (200)."""
    cm = ConfigManager()
    accounts_ns.add(
        "team",
        type="service_account",
        region="us",
        default_project="100",
        username="team-user",
        secret="team-secret",
    )
    accounts_ns.add(
        "personal",
        type="service_account",
        region="us",
        default_project="200",
        username="personal-user",
        secret="personal-secret",
    )
    return cm


class TestPythonApplyRoundtrip:
    """``mp.targets.use(NAME)`` updates [active] AND the target account's default_project."""

    def test_apply_writes_active_account_and_workspace(
        self, two_accounts: ConfigManager
    ) -> None:
        """After use(), [active] reflects the target's account + workspace."""
        targets_ns.add("ecom", account="team", project="3018488", workspace=42)
        targets_ns.use("ecom")

        active = session_ns.show()
        assert active.account == "team"
        assert active.workspace == 42

    def test_apply_updates_target_account_default_project(
        self, two_accounts: ConfigManager
    ) -> None:
        """FR-033 / FR-017: target's project becomes account.default_project (project lives on the account, not in [active])."""
        targets_ns.add("ecom", account="team", project="3018488", workspace=42)
        targets_ns.use("ecom")

        # AccountSummary doesn't expose default_project; read the full
        # Account record via ConfigManager.get_account.
        team = two_accounts.get_account("team")
        assert team.default_project == "3018488"

    def test_apply_does_not_touch_other_accounts(
        self, two_accounts: ConfigManager
    ) -> None:
        """Applying a target referencing 'team' must NOT mutate 'personal'."""
        targets_ns.add("ecom", account="team", project="3018488", workspace=42)
        targets_ns.use("ecom")

        personal = two_accounts.get_account("personal")
        assert personal.default_project == "200"
        # ServiceAccount-specific field — narrow via type discriminator.
        assert personal.type == "service_account"
        assert personal.username == "personal-user"

    def test_apply_without_workspace_clears_any_prior_workspace_pin(
        self, two_accounts: ConfigManager
    ) -> None:
        """A target with no workspace MUST clear the prior [active].workspace.

        Workspaces are project-scoped; carrying a stale workspace ID across
        target swaps would resolve to a foreign workspace under the new
        project. The atomic [active] replacement in apply_target() must
        drop any prior workspace key.
        """
        # Pin a workspace first.
        targets_ns.add("ecom", account="team", project="3018488", workspace=42)
        targets_ns.use("ecom")
        assert session_ns.show().workspace == 42

        # Apply a target with no workspace — [active].workspace must clear.
        targets_ns.add("staging", account="personal", project="999")
        targets_ns.use("staging")
        active = session_ns.show()
        assert active.account == "personal"
        assert active.workspace is None

    def test_apply_then_workspace_resolves_to_target_session(
        self, two_accounts: ConfigManager
    ) -> None:
        """A bare Workspace() after target use sees the new account + project."""
        targets_ns.add("ecom", account="team", project="3018488", workspace=42)
        targets_ns.use("ecom")

        ws = Workspace()
        assert ws.session.account.name == "team"
        assert ws.session.project.id == "3018488"
        assert ws.session.workspace is not None
        assert ws.session.workspace.id == 42


class TestAtomicity:
    """T075 / FR-013: target apply MUST be a single config write transaction."""

    def test_apply_target_uses_single_mutate_transaction(
        self, two_accounts: ConfigManager
    ) -> None:
        """``ConfigManager._mutate`` must be entered exactly once per ``targets.use()``.

        If ``apply_target`` decomposed into N serialized updates (e.g.
        ``set_active(account=...)`` + ``set_active(workspace=...)`` +
        ``add_account(default_project=...)`` as three separate calls),
        a process death between them would leave [active] partially
        applied — a stale workspace pinned under a new account, or vice
        versa. The single-transaction guarantee in
        ``ConfigManager.apply_target`` prevents that.
        """
        targets_ns.add("ecom", account="team", project="3018488", workspace=42)

        # Patch _mutate on the real class; targets.use() resolves the
        # ConfigManager via mp.targets._config() so the patch hits the
        # production code path.
        original_mutate = ConfigManager._mutate
        call_count = 0

        def counting_mutate(self: ConfigManager) -> object:
            nonlocal call_count
            call_count += 1
            return original_mutate(self)

        with patch.object(ConfigManager, "_mutate", counting_mutate):
            targets_ns.use("ecom")

        assert call_count == 1, (
            f"apply_target must use exactly one _mutate transaction; saw {call_count}."
        )


class TestWorkspaceConstructionEquivalence:
    """SC-010: ``Workspace(target=N)`` ≡ ``Workspace().use(target=N)`` (same Session)."""

    def test_constructor_target_matches_use_target(
        self, two_accounts: ConfigManager
    ) -> None:
        """Both construction paths produce the same (account, project, workspace) triple."""
        targets_ns.add("ecom", account="team", project="3018488", workspace=42)

        # Path A: chain through use()
        ws_a = Workspace().use(target="ecom")
        # Path B: direct constructor
        ws_b = Workspace(target="ecom")

        # Account is the same identity (same name, same type, same region).
        assert ws_a.session.account.name == ws_b.session.account.name == "team"
        assert (
            ws_a.session.account.type == ws_b.session.account.type == "service_account"
        )
        assert ws_a.session.account.region == ws_b.session.account.region == "us"
        # Project axis matches the target.
        assert ws_a.session.project.id == ws_b.session.project.id == "3018488"
        # Workspace axis matches the target.
        assert ws_a.session.workspace is not None and ws_b.session.workspace is not None
        assert ws_a.session.workspace.id == ws_b.session.workspace.id == 42

    def test_per_command_target_does_not_persist(
        self, two_accounts: ConfigManager, isolated_home: Path
    ) -> None:
        """``Workspace(target=N)`` (no persist=True) does NOT mutate [active] or any account.

        First-account auto-promotion (FR-045) means [active].account is
        already populated post-seed (``team`` was added first). The
        invariant under test is *no further mutation* — the on-disk
        config bytes are byte-identical before and after the per-command
        Workspace construction.
        """
        targets_ns.add("ecom", account="team", project="3018488", workspace=42)
        config_path = isolated_home / ".mp" / "config.toml"
        before = config_path.read_bytes()

        # Per-command Workspace construction with target= must NOT persist.
        ws = Workspace(target="ecom")
        # Sanity: it DOES resolve in-memory to the target.
        assert ws.session.account.name == "team"
        assert ws.session.project.id == "3018488"

        after = config_path.read_bytes()
        assert before == after, (
            "Workspace(target=NAME) must not mutate ~/.mp/config.toml; "
            "use mp.targets.use(NAME) (or persist=True on use()) to persist."
        )


class TestCliRoundtrip:
    """``mp target use NAME`` (subprocess) ↔ ``Workspace()`` (in-process) agree."""

    def test_cli_apply_then_python_read(self, isolated_home: Path) -> None:
        """Apply a target via the CLI; verify in-process Workspace sees it."""
        env = {
            "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
            "HOME": str(isolated_home),
            "MP_CONFIG_PATH": str(isolated_home / ".mp" / "config.toml"),
        }
        # Preserve venv plumbing so `uv run mp` resolves.
        for key in ("VIRTUAL_ENV", "PYTHONUSERBASE", "PYTHONHOME"):
            if key in os.environ:
                env[key] = os.environ[key]

        def _mp(*args: str, extra_env: dict[str, str] | None = None) -> str:
            full_env = dict(env)
            if extra_env:
                full_env.update(extra_env)
            result = subprocess.run(
                ["uv", "run", "mp", *args],
                capture_output=True,
                text=True,
                env=full_env,
                check=False,
                cwd=str(REPO_ROOT),
            )
            assert result.returncode == 0, (
                f"mp {' '.join(args)} failed: {result.stderr}"
            )
            return result.stdout

        # Seed: two accounts and one target via CLI.
        _mp(
            "account",
            "add",
            "team",
            "--type",
            "service_account",
            "--region",
            "us",
            "--username",
            "team-user",
            "--project",
            "100",
            extra_env={"MP_SECRET": "team-secret"},
        )
        _mp(
            "account",
            "add",
            "personal",
            "--type",
            "service_account",
            "--region",
            "us",
            "--username",
            "personal-user",
            "--project",
            "200",
            extra_env={"MP_SECRET": "personal-secret"},
        )
        _mp(
            "target",
            "add",
            "ecom",
            "--account",
            "team",
            "--project",
            "3018488",
            "--workspace",
            "42",
        )
        # Apply the target.
        _mp("target", "use", "ecom")

        # In-process: Workspace() must see the applied state.
        # Re-import is unnecessary — env vars + config path drive resolution.
        ws = Workspace()
        assert ws.session.account.name == "team"
        assert ws.session.project.id == "3018488"
        assert ws.session.workspace is not None
        assert ws.session.workspace.id == 42

        # And the CLI session view agrees.
        # The `mp session --format json` shape is the contract §7 structured
        # payload: {"account": {name, type, region}, "project": {id, name,
        # organization}, "workspace": {id, name}, "user": {email}|null,
        # "me_cached": bool} — see cli/commands/session.py.
        out = _mp("session", "--format", "json")
        payload = json.loads(out)
        assert payload["account"]["name"] == "team"
        assert payload["project"]["id"] == "3018488"
        assert payload["workspace"]["id"] == 42

    def test_cli_apply_missing_account_raises(self, isolated_home: Path) -> None:
        """``mp target use NAME`` for a target whose account was deleted exits non-zero with a clear error."""
        env = {
            "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
            "HOME": str(isolated_home),
            "MP_CONFIG_PATH": str(isolated_home / ".mp" / "config.toml"),
        }
        for key in ("VIRTUAL_ENV", "PYTHONUSERBASE", "PYTHONHOME"):
            if key in os.environ:
                env[key] = os.environ[key]

        def _mp(
            *args: str,
            extra_env: dict[str, str] | None = None,
            check: bool = True,
        ) -> subprocess.CompletedProcess[str]:
            full_env = dict(env)
            if extra_env:
                full_env.update(extra_env)
            result = subprocess.run(
                ["uv", "run", "mp", *args],
                capture_output=True,
                text=True,
                env=full_env,
                check=False,
                cwd=str(REPO_ROOT),
            )
            if check:
                assert result.returncode == 0, (
                    f"mp {' '.join(args)} failed: {result.stderr}"
                )
            return result

        # Seed: one account + one target referencing it.
        _mp(
            "account",
            "add",
            "team",
            "--type",
            "service_account",
            "--region",
            "us",
            "--username",
            "team-user",
            "--project",
            "100",
            extra_env={"MP_SECRET": "team-secret"},
        )
        _mp(
            "target",
            "add",
            "ecom",
            "--account",
            "team",
            "--project",
            "3018488",
        )
        # Force-remove the account that the target points at.
        _mp("account", "remove", "team", "--force")

        # Now `mp target use ecom` must fail with a clear error.
        result = _mp("target", "use", "ecom", check=False)
        assert result.returncode != 0
        assert "team" in (result.stderr + result.stdout).lower()
