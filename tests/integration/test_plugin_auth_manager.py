"""Integration tests for the mixpanel-plugin auth_manager.py (T094, US9).

Each subcommand is exercised via subprocess against a fixture config in
a tmp ``~/.mp/``. Tests assert the JSON output shape matches the
contract in
``specs/042-auth-architecture-redesign/contracts/plugin-auth-manager.md``.

Subprocess isolation is mandatory: ``auth_manager.py`` is shipped as a
standalone script invoked from a Claude Code skill, so the
publish-time invocation pattern is exactly ``python <path> <args>``
with ``HOME`` pointing at a hermetic tmp dir.

Reference: PR #126 review Cluster A2 (Phase 9 / US9, T094).
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from collections.abc import Generator
from pathlib import Path
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
PLUGIN_AUTH_MANAGER = (
    REPO_ROOT
    / "mixpanel-plugin"
    / "skills"
    / "mixpanelyst"
    / "scripts"
    / "auth_manager.py"
)


def _run(
    *args: str,
    tmp_home: Path,
    env_extra: dict[str, str] | None = None,
    stdin: str | None = None,
) -> dict[str, Any]:
    """Run ``auth_manager.py`` with ``args``; return parsed JSON from stdout.

    Hermetic: starts from a clean env containing only PATH/HOME-derived
    essentials, sets ``HOME``/``MP_CONFIG_PATH`` to ``tmp_home``, then
    layers in ``env_extra``. Asserts the process emitted exactly one JSON
    object (the contract's invariant P1/P2 — schema_version + state must
    always be present).

    Args:
        *args: CLI args after the script path.
        tmp_home: Tmp ``$HOME`` containing isolated ``.mp/``.
        env_extra: Extra env vars (e.g. ``MP_OAUTH_TOKEN`` for env-auth tests).
        stdin: Optional stdin payload (used by ``account add --from-stdin``).

    Returns:
        Parsed JSON dict from stdout.
    """
    # Start from a near-empty env so MP_* leakage from the developer shell
    # cannot bleed into the subprocess. Keep PATH (so ``python`` resolves)
    # and a few VIRTUAL_ENV-related vars so uv-installed deps are visible.
    env = {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "HOME": str(tmp_home),
        "MP_CONFIG_PATH": str(tmp_home / ".mp" / "config.toml"),
        "PYTHONPATH": str(REPO_ROOT / "src"),
    }
    # Preserve venv-related vars so the subprocess reaches the same
    # ``mixpanel_headless`` install that the parent test process has imported.
    for key in ("VIRTUAL_ENV", "PYTHONUSERBASE", "PYTHONHOME"):
        if key in os.environ:
            env[key] = os.environ[key]
    if env_extra:
        env.update(env_extra)
    result = subprocess.run(
        [sys.executable, str(PLUGIN_AUTH_MANAGER), *args],
        capture_output=True,
        text=True,
        input=stdin,
        env=env,
        check=False,
    )
    if not result.stdout.strip():
        pytest.fail(
            f"auth_manager produced no JSON; stderr={result.stderr!r} args={args!r}"
        )
    try:
        payload: dict[str, Any] = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        pytest.fail(
            f"auth_manager stdout is not valid JSON: {exc}\n"
            f"stdout={result.stdout!r}\nstderr={result.stderr!r}"
        )
    # P1: every response carries schema_version.
    assert payload.get("schema_version") == 1, (
        f"missing schema_version=1 in {payload!r}"
    )
    # P2: every response carries a discriminated state.
    assert payload.get("state") in {
        "ok",
        "needs_account",
        "needs_project",
        "error",
    }, f"unknown state in {payload!r}"
    return payload


@pytest.fixture
def tmp_home(tmp_path: Path) -> Generator[Path, None, None]:
    """Provide a tmp ``$HOME`` with an isolated ``.mp/`` directory."""
    (tmp_path / ".mp").mkdir(mode=0o700, exist_ok=True)
    yield tmp_path


@pytest.fixture
def populated_home(tmp_home: Path) -> Path:
    """Tmp home seeded with a single service-account v3 config."""
    config = tmp_home / ".mp" / "config.toml"
    config.write_text(
        "\n".join(
            [
                "[active]",
                'account = "team"',
                "",
                "[accounts.team]",
                'type = "service_account"',
                'region = "us"',
                'default_project = "3713224"',
                'username = "sa.user"',
                'secret = "fake-secret"',
                "",
            ]
        ),
        encoding="utf-8",
    )
    config.chmod(0o600)
    return tmp_home


# =============================================================================
# `session` — discriminated state contract
# =============================================================================


class TestSessionSubcommand:
    """``session`` subcommand emits the right state for each config posture."""

    def test_empty_config_returns_needs_account(self, tmp_home: Path) -> None:
        """An empty ``~/.mp/`` produces ``state="needs_account"`` + onboarding hints."""
        payload = _run("session", tmp_home=tmp_home)
        assert payload["state"] == "needs_account"
        assert isinstance(payload.get("next"), list)
        assert payload["next"], "needs_account should suggest a next command"
        # First suggestion must be a usable mp command per § 2.2. Post-043,
        # ``mp login`` replaces the multi-step ``mp account add`` as the
        # frictionless onboarding default.
        assert payload["next"][0]["command"].startswith("mp login")

    def test_populated_config_returns_ok(self, populated_home: Path) -> None:
        """A configured account + default_project yields ``state="ok"``."""
        payload = _run("session", tmp_home=populated_home)
        assert payload["state"] == "ok"
        # P5: account always has {name, type, region}.
        assert payload["account"]["name"] == "team"
        assert payload["account"]["type"] == "service_account"
        assert payload["account"]["region"] == "us"
        # P6: project always has {id} when present.
        assert payload["project"]["id"] == "3713224"

    def test_oauth_browser_without_project_returns_needs_project(
        self, tmp_home: Path
    ) -> None:
        """OAuth browser account without ``default_project`` → ``needs_project``."""
        config = tmp_home / ".mp" / "config.toml"
        config.write_text(
            "\n".join(
                [
                    "[active]",
                    'account = "personal"',
                    "",
                    "[accounts.personal]",
                    'type = "oauth_browser"',
                    'region = "us"',
                    "",
                ]
            ),
            encoding="utf-8",
        )
        config.chmod(0o600)
        payload = _run("session", tmp_home=tmp_home)
        assert payload["state"] == "needs_project"
        assert payload["account"]["name"] == "personal"
        assert isinstance(payload.get("next"), list)
        assert payload["next"], "needs_project should suggest a next command"

    def test_env_only_auth_returns_ok_with_populated_axes(self, tmp_home: Path) -> None:
        """Env-only auth (no ``[active]``) MUST resolve to a fully populated ok.

        Regression: prior implementation returned ``state="ok"`` with
        ``account=None`` / ``project=None`` / ``workspace=None`` because it
        bypassed the resolver and read ``[active]`` directly. Per § 2.1
        of the contract, ``state="ok"`` requires populated account / project.
        """
        payload = _run(
            "session",
            tmp_home=tmp_home,
            env_extra={
                "MP_USERNAME": "u",
                "MP_SECRET": "s",
                "MP_PROJECT_ID": "3713224",
                "MP_REGION": "us",
            },
        )
        assert payload["state"] == "ok"
        assert payload["account"] is not None
        assert payload["account"]["type"] == "service_account"
        assert payload["account"]["region"] == "us"
        assert payload["project"]["id"] == "3713224"
        # Source map: env supplied account + project; workspace unset → lazy.
        assert payload["source"]["account"] == "env"
        assert payload["source"]["project"] == "env"
        assert payload["source"]["workspace"] == "unset"

    def test_bridge_only_auth_returns_ok(self, tmp_home: Path) -> None:
        """A bridge-only Cowork VM (no ``[active]``) MUST resolve to ok.

        Regression: prior implementation returned ``state="needs_account"``
        because ``[active].account`` was None and env vars were absent —
        the bridge file was never consulted by ``cmd_session``.
        """
        bridge_path = tmp_home / "bridge.json"
        bridge_path.write_text(
            json.dumps(
                {
                    "version": 2,
                    "account": {
                        "type": "service_account",
                        "name": "courier",
                        "region": "us",
                        "username": "u",
                        "secret": "s",
                    },
                    "project": "3713224",
                    "workspace": 3448413,
                }
            ),
            encoding="utf-8",
        )
        bridge_path.chmod(0o600)
        payload = _run(
            "session",
            tmp_home=tmp_home,
            env_extra={"MP_AUTH_FILE": str(bridge_path)},
        )
        assert payload["state"] == "ok"
        assert payload["account"]["name"] == "courier"
        assert payload["account"]["type"] == "service_account"
        assert payload["project"]["id"] == "3713224"
        assert payload["workspace"]["id"] == 3448413
        assert payload["source"]["account"] == "bridge"
        assert payload["source"]["project"] == "bridge"
        assert payload["source"]["workspace"] == "bridge"


# =============================================================================
# `account list/add/use` — list & mutation contracts
# =============================================================================


class TestAccountListSubcommand:
    """``account list`` returns ``items: []`` (possibly empty) per P4."""

    def test_empty_returns_items_empty(self, tmp_home: Path) -> None:
        """No accounts → ``items: []`` + onboarding suggestion."""
        payload = _run("account", "list", tmp_home=tmp_home)
        assert payload["state"] == "ok"
        assert payload["items"] == []
        # Per § 3.1, empty list also surfaces onboarding hints.
        assert isinstance(payload.get("next"), list)

    def test_populated_returns_one_item_with_required_fields(
        self, populated_home: Path
    ) -> None:
        """Populated config → one item with {name, type, region, is_active}."""
        payload = _run("account", "list", tmp_home=populated_home)
        assert payload["state"] == "ok"
        assert len(payload["items"]) == 1
        item = payload["items"][0]
        assert item["name"] == "team"
        assert item["type"] == "service_account"
        assert item["region"] == "us"
        assert item["is_active"] is True
        # Per § 3.1, items also carry ``referenced_by_targets``.
        assert item["referenced_by_targets"] == []


class TestAccountUseSubcommand:
    """``account use NAME`` switches active per § 4.3."""

    def test_use_existing_account(self, populated_home: Path) -> None:
        """Switching to an existing account writes ``[active].account``."""
        payload = _run("account", "use", "team", tmp_home=populated_home)
        assert payload["state"] == "ok"
        assert payload["active"]["account"] == "team"

    def test_use_missing_account_returns_error(self, tmp_home: Path) -> None:
        """Unknown name → ``state="error"`` per § 2.4."""
        payload = _run("account", "use", "ghost", tmp_home=tmp_home)
        assert payload["state"] == "error"
        # P3: error response has {code, message, actionable}.
        assert payload["error"]["code"]  # non-empty class name
        assert payload["error"]["message"]
        assert isinstance(payload["error"]["actionable"], bool)


class TestAccountAddSubcommand:
    """``account add`` accepts the contracted JSON record via --from-stdin."""

    def test_add_via_stdin(self, tmp_home: Path) -> None:
        """Adding a service_account via stdin records it + auto-promotes (FR-045)."""
        record = {
            "name": "team",
            "type": "service_account",
            "region": "us",
            "default_project": "3713224",
            "username": "sa.user",
            "secret": "supersecret",
        }
        payload = _run(
            "account",
            "add",
            "--from-stdin",
            tmp_home=tmp_home,
            stdin=json.dumps(record),
        )
        assert payload["state"] == "ok"
        assert payload["added"]["name"] == "team"
        assert payload["added"]["type"] == "service_account"
        # First account added auto-promotes to active (FR-045).
        assert payload["added"]["is_active"] is True


# =============================================================================
# `target list/add/use` — referential integrity
# =============================================================================


class TestTargetSubcommand:
    """``target list/add/use`` honors P4 + § 3.4."""

    def test_list_empty_returns_items_empty(self, tmp_home: Path) -> None:
        """No targets → empty items array (P4)."""
        payload = _run("target", "list", tmp_home=tmp_home)
        assert payload["state"] == "ok"
        assert payload["items"] == []

    def test_add_target_then_list(self, populated_home: Path) -> None:
        """Add a target → ``account list`` shows it in ``referenced_by_targets``."""
        added = _run(
            "target",
            "add",
            "ecom",
            "--account",
            "team",
            "--project",
            "3713224",
            tmp_home=populated_home,
        )
        assert added["state"] == "ok"
        assert added["added"]["name"] == "ecom"

        listing = _run("target", "list", tmp_home=populated_home)
        assert listing["state"] == "ok"
        assert len(listing["items"]) == 1
        assert listing["items"][0]["name"] == "ecom"
        assert listing["items"][0]["account"] == "team"
        assert listing["items"][0]["project"] == "3713224"

    def test_use_target_writes_active(self, populated_home: Path) -> None:
        """``target use ecom`` writes [active] atomically per § 4.3."""
        _run(
            "target",
            "add",
            "ecom",
            "--account",
            "team",
            "--project",
            "3713224",
            "--workspace",
            "3448413",
            tmp_home=populated_home,
        )
        used = _run("target", "use", "ecom", tmp_home=populated_home)
        assert used["state"] == "ok"
        assert used["active"]["account"] == "team"
        assert used["active"]["project"] == "3713224"
        assert used["active"]["workspace"] == 3448413


# =============================================================================
# `bridge status` — Cowork bridge presence (per § 5)
# =============================================================================


class TestBridgeStatusSubcommand:
    """``bridge status`` reflects bridge file presence."""

    def test_bridge_absent(self, tmp_home: Path) -> None:
        """No bridge → ``bridge: null`` per § 5.2."""
        payload = _run("bridge", "status", tmp_home=tmp_home)
        assert payload["state"] == "ok"
        assert payload["bridge"] is None

    def test_bridge_present(self, tmp_home: Path) -> None:
        """A v2 bridge file at ``MP_AUTH_FILE`` is reflected in the response."""
        bridge_path = tmp_home / "bridge.json"
        bridge_path.write_text(
            json.dumps(
                {
                    "version": 2,
                    "account": {
                        "type": "service_account",
                        "name": "personal",
                        "region": "us",
                        "username": "u",
                        "secret": "s",
                    },
                    "project": "3713224",
                    "headers": {"X-Mixpanel-Cluster": "internal-1"},
                }
            ),
            encoding="utf-8",
        )
        bridge_path.chmod(0o600)
        payload = _run(
            "bridge",
            "status",
            tmp_home=tmp_home,
            env_extra={"MP_AUTH_FILE": str(bridge_path)},
        )
        assert payload["state"] == "ok"
        assert payload["bridge"] is not None
        assert payload["bridge"]["path"] == str(bridge_path)
        assert payload["bridge"]["version"] == 2
        assert payload["bridge"]["account"]["name"] == "personal"
        assert payload["bridge"]["project"] == "3713224"
        assert payload["bridge"]["headers"] == {"X-Mixpanel-Cluster": "internal-1"}


# =============================================================================
# Static guards — LoC budget + zero version branches
# =============================================================================


class TestStaticGuards:
    """Per-T100 guards on the rewritten file."""

    def test_loc_budget_at_or_below_320(self) -> None:
        """``auth_manager.py`` body must stay ≤ 320 lines.

        The cap accommodates the enriched ``_err()`` envelope (actionable
        code derivation, cause preservation, opt-in MP_VERBOSE traceback).
        Further growth should be considered a real signal that the script
        is doing too much.
        """
        lines = PLUGIN_AUTH_MANAGER.read_text(encoding="utf-8").splitlines()
        assert len(lines) <= 320, (
            f"auth_manager.py grew to {len(lines)} lines; target is ≤ 320."
        )

    def test_zero_version_branches(self) -> None:
        """Zero ``config_version`` / ``version >= 2`` branches anywhere."""
        text = PLUGIN_AUTH_MANAGER.read_text(encoding="utf-8")
        for needle in ("config_version", "version >= 2", "if version >="):
            assert needle not in text, (
                f"auth_manager.py contains banned legacy marker {needle!r}"
            )
