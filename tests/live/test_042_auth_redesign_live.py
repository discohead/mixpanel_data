"""Live QA: 042 auth architecture redesign (Phases 1-5).

Drives all three account types end-to-end against the real Mixpanel API.
Read-only — no entity creation, no destructive ops, safe against any
project. Uses tmp v3 home so the user's real ~/.mp/ is never touched.

**How to run**:

    # All categories (requires all three modes):
    source ~/.zshrc          # ensure MP_LIVE_OAUTH_TOKEN is loaded
    MP_LIVE_TESTS=1 uv run pytest tests/live/test_042_auth_redesign_live.py -v -m live

    # Single category:
    MP_LIVE_TESTS=1 uv run pytest tests/live/test_042_auth_redesign_live.py -v -m live -k CatB

**Required env vars** (each gates the corresponding category):

    OAuth browser (Cat B): nothing — uses ~/.mp/oauth/tokens_us.json directly
    Service account (Cat A): MP_LIVE_SA_USERNAME, MP_LIVE_SA_SECRET,
                             MP_LIVE_SA_PROJECT_ID, MP_LIVE_SA_REGION
    Static OAuth token (Cat C): MP_LIVE_OAUTH_TOKEN, MP_LIVE_PROJECT_ID,
                                MP_LIVE_REGION

The MP_LIVE_* prefix dodges the autouse env-var cleanup in
tests/conftest.py — that fixture scrubs MP_USERNAME / MP_SECRET /
MP_OAUTH_TOKEN / etc. before each test runs to keep unit tests
hermetic. Live tests opt back in by reading from these MP_LIVE_* vars
and calling monkeypatch.setenv to restore the standard MP_* form
inside the test body.

Reference: ~/.claude/plans/design-a-qa-plan-vast-wall.md.
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest
from pydantic import SecretStr

from mixpanel_headless import Workspace
from mixpanel_headless import accounts as accounts_ns
from mixpanel_headless._internal.auth.account import (
    OAuthBrowserAccount,
    OAuthTokenAccount,
    ServiceAccount,
)
from mixpanel_headless._internal.config import ConfigManager
from mixpanel_headless.exceptions import (
    AuthenticationError,
    OAuthError,
)

# Re-export the fixtures from conftest_042.py so pytest picks them up.
from tests.live.conftest_042 import (  # noqa: F401 — fixture imports
    copy_user_oauth_tokens_to_account,
    get_user_active_project_id,
    live_oauth_token_creds,
    live_sa_creds,
    require_oauth_browser_available,
    require_oauth_token_available,
    require_sa_env_available,
    tmp_mp_home,
)

# Module-level marker — every test below requires `-m live`.
pytestmark = pytest.mark.live


# =============================================================================
# Cat A — Service Account end-to-end
# =============================================================================


class TestCatA_ServiceAccount:
    """Real-API smoke for the SA auth path."""

    def test_A1_01_workspace_from_env_quad_authenticates(
        self,
        tmp_mp_home: Path,
        live_sa_creds: dict[str, str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """A1.01 — Workspace() with full SA env quad authenticates against /me."""
        monkeypatch.setenv("MP_USERNAME", live_sa_creds["username"])
        monkeypatch.setenv("MP_SECRET", live_sa_creds["secret"])
        monkeypatch.setenv("MP_PROJECT_ID", live_sa_creds["project_id"])
        monkeypatch.setenv("MP_REGION", live_sa_creds["region"])
        ws = Workspace()
        try:
            # Real read — list events from the project.
            events = ws.events()
            assert isinstance(events, list)
        finally:
            ws.close()

    def test_A1_02_persisted_sa_account_authenticates(
        self,
        tmp_mp_home: Path,
        live_sa_creds: dict[str, str],
    ) -> None:
        """A1.02 — `mp.accounts.add(..service_account..)` then Workspace(account=) hits API."""
        accounts_ns.add(
            "team",
            type="service_account",
            region=live_sa_creds["region"],  # type: ignore[arg-type]
            default_project=live_sa_creds["project_id"],
            username=live_sa_creds["username"],
            secret=SecretStr(live_sa_creds["secret"]),
        )
        ws = Workspace(account="team")
        try:
            events = ws.events()
            assert isinstance(events, list)
        finally:
            ws.close()

    def test_A1_03_cli_round_trip_no_secret_in_stderr(
        self,
        tmp_mp_home: Path,
        live_sa_creds: dict[str, str],
    ) -> None:
        """A1.03 — `mp account add` then `mp inspect events` round-trips; secret never leaks."""
        env = os.environ.copy()
        env.update(
            {
                "MP_SECRET": live_sa_creds["secret"],
                "HOME": str(tmp_mp_home),
                "MP_CONFIG_PATH": str(tmp_mp_home / ".mp" / "config.toml"),
            }
        )
        # Add the account. Service-account add requires --project (FR enforced
        # by ConfigManager._apply_add_account; CLI mirrors the same).
        result_add = subprocess.run(
            [
                "uv",
                "run",
                "mp",
                "account",
                "add",
                "team",
                "--type",
                "service_account",
                "--region",
                live_sa_creds["region"],
                "--username",
                live_sa_creds["username"],
                "--project",
                live_sa_creds["project_id"],
            ],
            capture_output=True,
            env=env,
            text=True,
            check=False,
        )
        assert result_add.returncode == 0, (
            f"add failed: {result_add.stderr}\nstdout: {result_add.stdout}"
        )
        assert live_sa_creds["secret"] not in result_add.stdout
        assert live_sa_creds["secret"] not in result_add.stderr

        # Set the active project.
        result_proj = subprocess.run(
            [
                "uv",
                "run",
                "mp",
                "project",
                "use",
                live_sa_creds["project_id"],
            ],
            capture_output=True,
            env=env,
            text=True,
            check=False,
        )
        assert result_proj.returncode == 0, f"project use failed: {result_proj.stderr}"

        # Read events via the new CLI surface.
        result_inspect = subprocess.run(
            ["uv", "run", "mp", "inspect", "events"],
            capture_output=True,
            env=env,
            text=True,
            check=False,
        )
        # Allow non-zero (some projects may have zero events) but secret must
        # never leak under any path.
        assert live_sa_creds["secret"] not in result_inspect.stdout
        assert live_sa_creds["secret"] not in result_inspect.stderr


# =============================================================================
# Cat B — OAuth browser end-to-end (reuses user's tokens)
# =============================================================================


def _seed_oauth_browser_account(
    home: Path,
    *,
    name: str = "personal",
    project_id: str | None = None,
) -> str:
    """Seed a v3 oauth_browser account using the user's real on-disk tokens.

    Args:
        home: Tmp $HOME root from the ``tmp_mp_home`` fixture.
        name: Account name to create in the v3 config.
        project_id: Project ID to set in [active]; defaults to the
            project from the user's real config.

    Returns:
        The project ID that was set in [active] (for use in assertions).
    """
    copy_user_oauth_tokens_to_account(home, name)
    cm = ConfigManager()
    pid = project_id or get_user_active_project_id() or "1"
    cm.add_account(name, type="oauth_browser", region="us", default_project=pid)
    cm.set_active(account=name)
    return pid


class TestCatB_OAuthBrowser:
    """Real-API smoke for the OAuth browser path."""

    def test_B1_01_workspace_reads_on_disk_token_and_authenticates(
        self,
        tmp_mp_home: Path,
        require_oauth_browser_available: None,
    ) -> None:
        """B1.01 — Tokens copied from legacy path; Workspace() authenticates."""
        _seed_oauth_browser_account(tmp_mp_home)
        ws = Workspace()
        try:
            events = ws.events()
            assert isinstance(events, list)
        finally:
            ws.close()

    def test_canonical_path_actually_taken(
        self,
        tmp_mp_home: Path,
        require_oauth_browser_available: None,
    ) -> None:
        """B1.02 — `Workspace.account` is OAuthBrowserAccount (not legacy fallback)."""
        _seed_oauth_browser_account(tmp_mp_home)
        ws = Workspace()
        try:
            assert isinstance(ws.account, OAuthBrowserAccount)
            assert ws.account.name == "personal"
        finally:
            ws.close()

    def test_B1_03_corrupted_tokens_surface_clean_error(
        self,
        tmp_mp_home: Path,
        require_oauth_browser_available: None,
    ) -> None:
        """B1.03 — Corrupted tokens.json → ``Workspace()`` raises OAuthError.

        Per the PR #126 review fixes (`session_to_credentials`), the resolver
        no longer swallows token-load failures behind a ``pending-login``
        placeholder. Bad tokens fail loudly at construction time so users get
        an actionable error instead of a confusing 401 later.
        """
        _seed_oauth_browser_account(tmp_mp_home)
        # Corrupt BEFORE Workspace construction.
        tokens_path = tmp_mp_home / ".mp" / "accounts" / "personal" / "tokens.json"
        tokens_path.write_text('{"access_token":', encoding="utf-8")
        with pytest.raises((OAuthError, AuthenticationError)) as excinfo:
            Workspace()
        err_str = str(excinfo.value)
        # Error never leaks the placeholder string or any token material.
        assert "pending-login" not in err_str


# =============================================================================
# Cat C — Static OAuth token end-to-end
# =============================================================================


class TestCatC_OAuthToken:
    """Real-API smoke for the static OAuth bearer path."""

    def test_C1_01_workspace_from_env_token(
        self,
        tmp_mp_home: Path,
        live_oauth_token_creds: dict[str, str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """C1.01 — MP_OAUTH_TOKEN env var → Workspace() authenticates."""
        monkeypatch.setenv("MP_OAUTH_TOKEN", live_oauth_token_creds["token"])
        monkeypatch.setenv("MP_PROJECT_ID", live_oauth_token_creds["project_id"])
        monkeypatch.setenv("MP_REGION", live_oauth_token_creds["region"])
        ws = Workspace()
        try:
            events = ws.events()
            assert isinstance(events, list)
        finally:
            ws.close()

    def test_C1_02_persisted_token_env_account_authenticates(
        self,
        tmp_mp_home: Path,
        live_oauth_token_creds: dict[str, str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """C1.02 — Persisted oauth_token account with token_env resolves at request time."""
        monkeypatch.setenv("MY_LIVE_TOK", live_oauth_token_creds["token"])
        accounts_ns.add(
            "ci",
            type="oauth_token",
            region=live_oauth_token_creds["region"],  # type: ignore[arg-type]
            default_project=live_oauth_token_creds["project_id"],
            token_env="MY_LIVE_TOK",
        )
        ConfigManager().set_active(account="ci")
        ws = Workspace()
        try:
            assert isinstance(ws.account, OAuthTokenAccount)
            events = ws.events()
            assert isinstance(events, list)
        finally:
            ws.close()

    def test_C1_03_inline_token_authenticates(
        self,
        tmp_mp_home: Path,
        live_oauth_token_creds: dict[str, str],
    ) -> None:
        """C1.03 — Inline token (SecretStr) round-trips and authenticates."""
        accounts_ns.add(
            "ci-inline",
            type="oauth_token",
            region=live_oauth_token_creds["region"],  # type: ignore[arg-type]
            default_project=live_oauth_token_creds["project_id"],
            token=SecretStr(live_oauth_token_creds["token"]),
        )
        ConfigManager().set_active(account="ci-inline")
        ws = Workspace()
        try:
            events = ws.events()
            assert isinstance(events, list)
            # SecretStr never leaks in repr.
            assert live_oauth_token_creds["token"] not in repr(ws.account)
        finally:
            ws.close()

    def test_C1_04_empty_env_token_surfaces_clean_error(
        self,
        tmp_mp_home: Path,
        require_oauth_token_available: None,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """C1.04 — Empty env var → either OAuthError (resolver) OR 401 (server).

        ``session_to_credentials`` swallows OAuthError and substitutes the
        ``pending-login`` placeholder so construction always succeeds. The
        first API call then surfaces a clean AuthenticationError. Either
        path is acceptable; both prove the empty-string case is handled.
        """
        monkeypatch.setenv("MY_LIVE_TOK", "")  # explicitly empty
        accounts_ns.add(
            "ci-empty",
            type="oauth_token",
            region=os.environ["MP_LIVE_REGION"],  # type: ignore[arg-type]
            default_project=os.environ["MP_LIVE_PROJECT_ID"],
            token_env="MY_LIVE_TOK",
        )
        ConfigManager().set_active(account="ci-empty")
        with pytest.raises((OAuthError, AuthenticationError)):
            ws = Workspace()
            try:
                ws.events()
            finally:
                ws.close()


# =============================================================================
# Cat D — Cross-mode switching (the killer feature)
# =============================================================================


class TestCatD_CrossModeSwitching:
    """HTTP transport preservation + atomic auth swap across all 3 modes."""

    def test_D1_01_three_mode_switch_preserves_http_transport(
        self,
        tmp_mp_home: Path,
        require_oauth_browser_available: None,
        live_sa_creds: dict[str, str],
        live_oauth_token_creds: dict[str, str],
    ) -> None:
        """D1.01 — Switch SA → oauth_browser → oauth_token; httpx.Client preserved.

        The killer claim of R5: connection pool stays alive across account
        switches with real network in flight.
        """
        # Seed all three accounts in the tmp v3 config. Service accounts now
        # require `default_project` at add-time (PR #126 review fix).
        accounts_ns.add(
            "team",
            type="service_account",
            region=live_sa_creds["region"],  # type: ignore[arg-type]
            default_project=live_sa_creds["project_id"],
            username=live_sa_creds["username"],
            secret=SecretStr(live_sa_creds["secret"]),
        )
        copy_user_oauth_tokens_to_account(tmp_mp_home, "personal")
        ConfigManager().add_account(
            "personal",
            type="oauth_browser",
            region="us",
            default_project=get_user_active_project_id() or "1",
        )
        accounts_ns.add(
            "ci",
            type="oauth_token",
            region=live_oauth_token_creds["region"],  # type: ignore[arg-type]
            default_project=live_oauth_token_creds["project_id"],
            token=SecretStr(live_oauth_token_creds["token"]),
        )

        # Start with SA.
        ws = Workspace(account="team", project=live_sa_creds["project_id"])
        try:
            client = ws._api_client  # noqa: SLF001
            assert client is not None
            before_id = id(client._http)  # noqa: SLF001
            ws.events()
            # Switch to OAuth browser.
            ws.use(
                account="personal",
                project=get_user_active_project_id() or "1",
            )
            ws.events()
            assert id(client._http) == before_id, (  # noqa: SLF001
                "httpx.Client recreated across SA → oauth_browser switch"
            )
            # Switch to OAuth token.
            ws.use(
                account="ci",
                project=live_oauth_token_creds["project_id"],
            )
            ws.events()
            assert id(client._http) == before_id, (  # noqa: SLF001
                "httpx.Client recreated across oauth_browser → oauth_token switch"
            )
        finally:
            ws.close()

    def test_D1_04_persist_writes_to_active(
        self,
        tmp_mp_home: Path,
        require_oauth_browser_available: None,
        live_sa_creds: dict[str, str],
    ) -> None:
        """D1.04 — `ws.use(account=A, persist=True)` writes [active] to disk."""
        accounts_ns.add(
            "team",
            type="service_account",
            region=live_sa_creds["region"],  # type: ignore[arg-type]
            default_project=live_sa_creds["project_id"],
            username=live_sa_creds["username"],
            secret=SecretStr(live_sa_creds["secret"]),
        )
        copy_user_oauth_tokens_to_account(tmp_mp_home, "personal")
        ConfigManager().add_account(
            "personal",
            type="oauth_browser",
            region="us",
            default_project=get_user_active_project_id() or "1",
        )
        ConfigManager().set_active(account="team")
        ws = Workspace()
        try:
            assert ws.account.name == "team"
            ws.use(
                account="personal",
                project=get_user_active_project_id() or "1",
                persist=True,
            )
        finally:
            ws.close()

        # Construct a fresh Workspace — should read the persisted state.
        ws2 = Workspace()
        try:
            assert ws2.account.name == "personal"
        finally:
            ws2.close()


# =============================================================================
# Cat E — CLI surface end-to-end
# =============================================================================


class TestCatE_CliEndToEnd:
    """Subprocess-based smokes for the new `mp` CLI groups."""

    def test_E1_01_cli_oauth_round_trip(
        self,
        tmp_mp_home: Path,
        require_oauth_browser_available: None,
    ) -> None:
        """E1.01 — `mp account add → mp project use → mp inspect events` round-trips."""
        copy_user_oauth_tokens_to_account(tmp_mp_home, "personal-cli")
        env = os.environ.copy()
        env.update(
            {
                "HOME": str(tmp_mp_home),
                "MP_CONFIG_PATH": str(tmp_mp_home / ".mp" / "config.toml"),
            }
        )
        # Register the account.
        r1 = subprocess.run(
            [
                "uv",
                "run",
                "mp",
                "account",
                "add",
                "personal-cli",
                "--type",
                "oauth_browser",
                "--region",
                "us",
            ],
            capture_output=True,
            env=env,
            text=True,
            check=False,
        )
        assert r1.returncode == 0, f"add: {r1.stderr}"

        # Set active project.
        pid = get_user_active_project_id() or "1"
        r2 = subprocess.run(
            ["uv", "run", "mp", "project", "use", pid],
            capture_output=True,
            env=env,
            text=True,
            check=False,
        )
        assert r2.returncode == 0, f"project use: {r2.stderr}"

        # Hit the live API via inspect.
        r3 = subprocess.run(
            ["uv", "run", "mp", "inspect", "events"],
            capture_output=True,
            env=env,
            text=True,
            check=False,
        )
        assert r3.returncode == 0, (
            f"inspect events failed: {r3.stderr}\nstdout: {r3.stdout}"
        )

    def test_E1_05_cli_session_json_output(
        self,
        tmp_mp_home: Path,
        require_oauth_browser_available: None,
    ) -> None:
        """E1.05 — `mp session --format json` matches ActiveSession.model_dump()."""
        _seed_oauth_browser_account(tmp_mp_home, name="personal-json")
        env = os.environ.copy()
        env.update(
            {
                "HOME": str(tmp_mp_home),
                "MP_CONFIG_PATH": str(tmp_mp_home / ".mp" / "config.toml"),
            }
        )
        result = subprocess.run(
            ["uv", "run", "mp", "session", "--format", "json"],
            capture_output=True,
            env=env,
            text=True,
            check=False,
        )
        assert result.returncode == 0
        payload = json.loads(result.stdout.strip())
        assert payload["account"] == "personal-json"
        assert payload["project"] == (get_user_active_project_id() or "1")

    def test_E1_04_cli_target_account_mutex_exits_3(
        self,
        tmp_mp_home: Path,
    ) -> None:
        """E1.04 — `mp --target X --account Y session` exits 3 with mutex error."""
        env = os.environ.copy()
        env.update(
            {
                "HOME": str(tmp_mp_home),
                "MP_CONFIG_PATH": str(tmp_mp_home / ".mp" / "config.toml"),
            }
        )
        result = subprocess.run(
            [
                "uv",
                "run",
                "mp",
                "--target",
                "X",
                "--account",
                "Y",
                "session",
            ],
            capture_output=True,
            env=env,
            text=True,
            check=False,
        )
        assert result.returncode == 3, (
            f"expected exit 3, got {result.returncode}: {result.stderr}"
        )


# =============================================================================
# Cat F — Bridge file mode
# =============================================================================


class TestCatF_Bridge:
    """v2 bridge file consumed by the resolver against the real API."""

    def test_F1_01_bridge_oauth_browser_authenticates(
        self,
        tmp_mp_home: Path,
        require_oauth_browser_available: None,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """F1.01 — Bridge file selects oauth_browser account; tokens come from disk.

        Bridge mode for ``oauth_browser`` provides the account record (so the
        resolver picks it up without a v3 ``[active]`` entry), but the access
        token is loaded by ``OnDiskTokenResolver`` from the per-account
        ``tokens.json`` keyed by ``account.name``. We seed both the bridge
        file and the on-disk token path under the same account name.
        """
        # Read user's real on-disk tokens (used both inline-in-bridge and
        # at the per-account on-disk path the resolver reads from).
        from tests.live.conftest_042 import LEGACY_TOKENS_PATH

        legacy_tokens = json.loads(LEGACY_TOKENS_PATH.read_text(encoding="utf-8"))
        copy_user_oauth_tokens_to_account(tmp_mp_home, "bridged")

        bridge_path = tmp_mp_home / "bridge.json"
        pid = get_user_active_project_id() or "1"
        bridge_payload = {
            "version": 2,
            "account": {
                "type": "oauth_browser",
                "name": "bridged",
                "region": "us",
            },
            "tokens": {
                "access_token": legacy_tokens["access_token"],
                "expires_at": legacy_tokens["expires_at"],
                "scope": legacy_tokens.get("scope", "read"),
                "token_type": legacy_tokens.get("token_type", "Bearer"),
                **(
                    {"refresh_token": legacy_tokens["refresh_token"]}
                    if legacy_tokens.get("refresh_token")
                    else {}
                ),
            },
            "project": pid,
        }
        bridge_path.write_text(json.dumps(bridge_payload), encoding="utf-8")
        bridge_path.chmod(0o600)
        monkeypatch.setenv("MP_AUTH_FILE", str(bridge_path))

        ws = Workspace()
        try:
            assert ws.account.name == "bridged"
            events = ws.events()
            assert isinstance(events, list)
        finally:
            ws.close()


# =============================================================================
# Cat G — Edge cases against live API
# =============================================================================


class TestCatG_LiveEdgeCases:
    """Live-API verification of edge cases that span env + auth + API behavior."""

    def test_G1_02_sa_quad_beats_oauth_token_env(
        self,
        tmp_mp_home: Path,
        live_sa_creds: dict[str, str],
        live_oauth_token_creds: dict[str, str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """G1.02 — Both SA quad + OAuth token env set → SA wins (PR #125 preserved).

        Pass ``project=`` to force the v3 path; otherwise ``Workspace()``
        would route through the legacy code (no v3 config on disk).
        """
        monkeypatch.setenv("MP_USERNAME", live_sa_creds["username"])
        monkeypatch.setenv("MP_SECRET", live_sa_creds["secret"])
        monkeypatch.setenv("MP_PROJECT_ID", live_sa_creds["project_id"])
        monkeypatch.setenv("MP_REGION", live_sa_creds["region"])
        monkeypatch.setenv("MP_OAUTH_TOKEN", live_oauth_token_creds["token"])
        # Force v3 path with explicit project=.
        ws = Workspace(project=live_sa_creds["project_id"])
        try:
            # SA wins → account is ServiceAccount, not OAuthTokenAccount.
            assert isinstance(ws.account, ServiceAccount)
            ws.events()  # confirm Basic auth actually works
        finally:
            ws.close()

    def test_G1_04_invalid_workspace_id_strict_validation(
        self,
        tmp_mp_home: Path,
        live_sa_creds: dict[str, str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """G1.04 — MP_WORKSPACE_ID="abc" → strict ConfigError at construction.

        The PR #126 review fixes tightened env validation: malformed
        ``MP_WORKSPACE_ID`` no longer silently skips — it raises
        ``ConfigError`` at ``Workspace()`` construction so misconfigured
        deployments fail loudly instead of silently scoping to None.
        """
        from mixpanel_headless.exceptions import ConfigError

        monkeypatch.setenv("MP_USERNAME", live_sa_creds["username"])
        monkeypatch.setenv("MP_SECRET", live_sa_creds["secret"])
        monkeypatch.setenv("MP_PROJECT_ID", live_sa_creds["project_id"])
        monkeypatch.setenv("MP_REGION", live_sa_creds["region"])
        monkeypatch.setenv("MP_WORKSPACE_ID", "abc")  # malformed
        with pytest.raises(ConfigError, match="MP_WORKSPACE_ID"):
            Workspace(project=live_sa_creds["project_id"])
