"""Focused snapshot tests for ``mp login`` (043 / AIE-117).

Covers the highest-value scenarios from the
``contracts/cli-commands.md`` §6 17-scenario matrix:

- SA happy path with no --region (probes us → eu → in)
- SA happy path with derived name from /me
- Re-login refused on region change (E-3) and auth-type change (E-4)
- Mutually exclusive CLI flags (E-11, E-12, E-13)
- Project not visible (E-6)

The remaining scenarios (interactive multi-project picker, browser
flow with placeholder dir, atomic-publish lifecycle) live in
follow-on integration tests once the orchestrator settles.

Reference: ``specs/043-frictionless-auth/contracts/cli-commands.md`` §6.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from pydantic import SecretStr
from typer.testing import CliRunner

from mixpanel_headless._internal.config import ConfigManager
from mixpanel_headless.cli.main import app

if TYPE_CHECKING:
    from mixpanel_headless._internal.me import MeProjectInfo, MeResponse


@pytest.fixture(autouse=True)
def _isolated_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Pin $HOME and MP_CONFIG_PATH for hermetic CLI tests."""
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("MP_CONFIG_PATH", str(tmp_path / ".mp" / "config.toml"))


@pytest.fixture
def runner() -> CliRunner:
    """A Typer CliRunner."""
    return CliRunner()


def _stub_me(monkeypatch: pytest.MonkeyPatch, payload: dict[str, object]) -> None:
    """Patch ``MixpanelAPIClient.me`` to return a canned payload."""
    from mixpanel_headless._internal import api_client as api_client_mod

    def _fake_me(self: object) -> dict[str, object]:
        return payload

    monkeypatch.setattr(api_client_mod.MixpanelAPIClient, "me", _fake_me)


class TestMpLoginValidation:
    """Argument-validation rules from cli-commands.md §5."""

    def test_service_account_and_token_env_mutually_exclusive(
        self, runner: CliRunner
    ) -> None:
        """``--service-account --token-env X`` → exit 3 (E-11)."""
        result = runner.invoke(
            app, ["login", "--service-account", "--token-env", "MY_TOKEN"]
        )
        from mixpanel_headless.cli.utils import ExitCode

        assert result.exit_code == ExitCode.INVALID_ARGS, result.output
        assert "mutually exclusive" in result.output

    def test_no_browser_with_service_account_rejected(self, runner: CliRunner) -> None:
        """``--no-browser --service-account`` → exit 3 (E-12)."""
        result = runner.invoke(app, ["login", "--no-browser", "--service-account"])
        from mixpanel_headless.cli.utils import ExitCode

        assert result.exit_code == ExitCode.INVALID_ARGS, result.output
        assert "--no-browser" in result.output

    def test_secret_stdin_with_oauth_token_rejected(
        self, runner: CliRunner, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """``--secret-stdin`` with oauth_token detected → exit 3 (E-13)."""
        monkeypatch.setenv("MP_OAUTH_TOKEN", "ey.xxx")
        result = runner.invoke(app, ["login", "--secret-stdin"])
        from mixpanel_headless.cli.utils import ExitCode

        assert result.exit_code == ExitCode.INVALID_ARGS, result.output
        assert "--secret-stdin" in result.output

    def test_invalid_region_rejected(self, runner: CliRunner) -> None:
        """``--region xx`` → exit 3 with ``Invalid --region`` message."""
        result = runner.invoke(app, ["login", "--region", "xx", "--service-account"])
        from mixpanel_headless.cli.utils import ExitCode

        assert result.exit_code == ExitCode.INVALID_ARGS, result.output


class TestMpLoginServiceAccount:
    """Happy paths for service_account auth via ``mp login``."""

    def test_sa_with_name_and_explicit_region_persists(
        self, runner: CliRunner, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """SA login with explicit --name + --region + --project skips picker / probe."""
        monkeypatch.setenv("MP_USERNAME", "svc")
        monkeypatch.setenv("MP_SECRET", "secret")
        _stub_me(
            monkeypatch,
            {
                "user_id": 1,
                "user_email": "svc@example.com",
                "organizations": {"100": {"id": 100, "name": "Acme Corp"}},
                "projects": {"12345": {"name": "Demo", "organization_id": 100}},
            },
        )
        result = runner.invoke(
            app,
            [
                "login",
                "--service-account",
                "--name",
                "prod-sa",
                "--region",
                "us",
                "--project",
                "12345",
            ],
        )
        assert result.exit_code == 0, result.output
        cm = ConfigManager()
        account = cm.get_account("prod-sa")
        assert account.region == "us"
        assert account.default_project == "12345"
        # Stdout success line.
        assert "Logged in" in result.output
        assert "prod-sa" in result.output

    def test_sa_derives_name_when_omitted(
        self, runner: CliRunner, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """SA login without --name → name slugified from first /me org."""
        monkeypatch.setenv("MP_USERNAME", "svc")
        monkeypatch.setenv("MP_SECRET", "secret")
        _stub_me(
            monkeypatch,
            {
                "user_id": 1,
                "user_email": "svc@example.com",
                "organizations": {"100": {"id": 100, "name": "Acme Corp"}},
                "projects": {"12345": {"name": "Demo", "organization_id": 100}},
            },
        )
        result = runner.invoke(app, ["login", "--service-account", "--region", "us"])
        assert result.exit_code == 0, result.output
        cm = ConfigManager()
        names = {s.name for s in cm.list_accounts()}
        assert "acme-corp" in names

    def test_sa_no_region_probes(
        self, runner: CliRunner, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """SA login without --region triggers the us → eu → in probe."""
        from mixpanel_headless._internal.auth import region_probe as rp_mod

        monkeypatch.setenv("MP_USERNAME", "svc")
        monkeypatch.setenv("MP_SECRET", "secret")
        _stub_me(
            monkeypatch,
            {
                "user_id": 1,
                "user_email": "svc@example.com",
                "organizations": {"100": {"id": 100, "name": "EU Corp"}},
                "projects": {"12345": {"name": "EU Project", "organization_id": 100}},
            },
        )

        def _spy_probe(
            client_factory: object,
            headers: dict[str, str],
            *,
            timeout_seconds: float = 5.0,
            order: tuple[str, ...] = ("us", "eu", "in"),
        ) -> rp_mod.RegionProbeResult:
            return rp_mod.RegionProbeResult(
                region="eu", attempts=[("us", 401), ("eu", 200)]
            )

        monkeypatch.setattr(rp_mod, "probe_region", _spy_probe)
        result = runner.invoke(app, ["login", "--service-account"])
        assert result.exit_code == 0, result.output
        cm = ConfigManager()
        names = {s.name for s in cm.list_accounts()}
        assert "eu-corp" in names
        assert cm.get_account("eu-corp").region == "eu"


class TestMpLoginOAuthToken:
    """New-account flow for ``oauth_token`` via ``mp login --token-env``.

    The orchestrator's re-login path is exercised by
    ``TestMpLoginReloginCredentialUpdate``. Until this class landed,
    the *new-account* oauth_token branches (``--token-env CUSTOM_VAR``,
    ``MP_OAUTH_TOKEN`` inline persist, missing env-var rejection) had
    no direct coverage — the production code was reached only by the
    re-login fixtures, which always have an existing account on disk.
    """

    def test_token_env_persists_env_pointer_not_inline_value(
        self, runner: CliRunner, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """``--token-env CUSTOM_VAR`` persists the env-var name, not the bearer.

        The user wants the token to stay in the env (typically a
        secrets manager) rather than land in ``config.toml``. The
        orchestrator must record ``token_env=CUSTOM_VAR`` and leave
        the inline ``token`` field unset.
        """
        from mixpanel_headless._internal.auth.account import OAuthTokenAccount

        monkeypatch.setenv("MY_CI_TOKEN", "ey.fake-bearer.value")
        _stub_me(
            monkeypatch,
            {
                "user_id": 1,
                "user_email": "ci@example.com",
                "organizations": {"100": {"id": 100, "name": "CI Corp"}},
                "projects": {"42": {"name": "Build", "organization_id": 100}},
            },
        )
        result = runner.invoke(
            app,
            [
                "login",
                "--token-env",
                "MY_CI_TOKEN",
                "--region",
                "us",
                "--name",
                "ci-bot",
                "--project",
                "42",
            ],
        )
        assert result.exit_code == 0, result.output
        cm = ConfigManager()
        account = cm.get_account("ci-bot")
        assert isinstance(account, OAuthTokenAccount)
        # The pointer-not-inline invariant: token_env set, token unset.
        assert account.token_env == "MY_CI_TOKEN"
        assert account.token is None

    def test_inline_mp_oauth_token_persists_bearer_value(
        self, runner: CliRunner, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """``MP_OAUTH_TOKEN=...`` (no ``--token-env``) persists the bearer inline.

        When the user has set ``MP_OAUTH_TOKEN`` directly without
        naming a custom env var, the orchestrator captures the bearer
        into ``config.toml`` so it survives the env disappearing.
        """
        from mixpanel_headless._internal.auth.account import OAuthTokenAccount

        monkeypatch.setenv("MP_OAUTH_TOKEN", "ey.inline-bearer")
        _stub_me(
            monkeypatch,
            {
                "user_id": 1,
                "user_email": "user@example.com",
                "organizations": {"100": {"id": 100, "name": "Inline Corp"}},
                "projects": {"42": {"name": "P", "organization_id": 100}},
            },
        )
        result = runner.invoke(
            app, ["login", "--region", "us", "--name", "inline-tok", "--project", "42"]
        )
        assert result.exit_code == 0, result.output
        cm = ConfigManager()
        account = cm.get_account("inline-tok")
        assert isinstance(account, OAuthTokenAccount)
        # Inline persistence: token field set; token_env unset.
        assert account.token is not None
        assert account.token.get_secret_value() == "ey.inline-bearer"
        assert account.token_env is None

    def test_token_env_pointing_at_unset_var_raises(
        self, runner: CliRunner, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """``--token-env MISSING_VAR`` with the env unset → ConfigError naming the var.

        The orchestrator must surface the specific env-var name so the
        user knows what to ``export`` — generic "no token" advice
        wastes a debugging round-trip.
        """
        # Make sure MP_OAUTH_TOKEN doesn't accidentally satisfy the probe.
        monkeypatch.delenv("MP_OAUTH_TOKEN", raising=False)
        monkeypatch.delenv("MISSING_VAR", raising=False)
        result = runner.invoke(
            app, ["login", "--token-env", "MISSING_VAR", "--region", "us"]
        )
        assert result.exit_code != 0, result.output
        # The unset env-var name must appear in the error so the user
        # knows what to set without opening the source code.
        assert "MISSING_VAR" in result.output


class TestMpLoginRelogin:
    """Re-login state-machine refusals (E-3, E-4) from data-model.md §4."""

    def test_relogin_region_change_refused(
        self, runner: CliRunner, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Re-login with --region eu against an existing us account → E-3, exit 1."""
        from mixpanel_headless import accounts as accounts_ns

        accounts_ns.add(
            "team",
            type="service_account",
            region="us",
            username="u",
            secret=SecretStr("s"),
        )
        monkeypatch.setenv("MP_USERNAME", "u")
        monkeypatch.setenv("MP_SECRET", "s")
        result = runner.invoke(
            app,
            ["login", "--service-account", "--name", "team", "--region", "eu"],
        )
        assert result.exit_code != 0, result.output
        assert "bound to region 'us'" in result.output
        # Rich may wrap the second clause across a newline; strip newlines
        # for the literal match so the assertion isn't sensitive to width.
        flat = result.output.replace("\n", " ")
        assert "cannot change to" in flat and "'eu'" in flat

    def test_relogin_auth_type_change_refused(
        self, runner: CliRunner, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Re-login with --service-account against an oauth_browser account → E-4."""
        from mixpanel_headless import accounts as accounts_ns

        accounts_ns.add("personal", type="oauth_browser", region="us")
        monkeypatch.setenv("MP_USERNAME", "u")
        monkeypatch.setenv("MP_SECRET", "s")
        result = runner.invoke(
            app,
            ["login", "--service-account", "--name", "personal"],
        )
        assert result.exit_code != 0, result.output
        assert "is type 'oauth_browser'" in result.output
        # Rich wraps long lines; use a flat-text match.
        flat = result.output.replace("\n", " ")
        assert "cannot re-login as" in flat and "'service_account'" in flat


class TestMpLoginProjectVisibility:
    """``--project`` validation against /me (E-6)."""

    def test_project_not_visible_lists_accessible(
        self, runner: CliRunner, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """--project N where N is not in /me → exit 4 with the accessible list.

        The orchestrator now raises the structured ``ProjectNotFoundError``
        rather than a plain ``ConfigError``, which the CLI maps to exit
        code 4 (NOT_FOUND) — distinct from generic config errors so
        scripts can react.
        """
        from mixpanel_headless.cli.utils import ExitCode

        monkeypatch.setenv("MP_USERNAME", "svc")
        monkeypatch.setenv("MP_SECRET", "secret")
        _stub_me(
            monkeypatch,
            {
                "user_id": 1,
                "organizations": {"100": {"id": 100, "name": "Acme"}},
                "projects": {
                    "11111": {"name": "Alpha", "organization_id": 100},
                    "22222": {"name": "Beta", "organization_id": 100},
                },
            },
        )
        result = runner.invoke(
            app,
            [
                "login",
                "--service-account",
                "--region",
                "us",
                "--project",
                "99999",
            ],
        )
        assert result.exit_code == ExitCode.NOT_FOUND, result.output
        # ProjectNotFoundError handler renders both the requested ID
        # and the accessible alternatives.
        assert "Project not found" in result.output
        assert "99999" in result.output
        assert "11111" in result.output
        assert "22222" in result.output


class TestMpLoginReloginCredentialUpdate:
    """Re-login persists rotated credentials for SA / oauth_token (research §4)."""

    def test_relogin_sa_persists_new_secret(
        self, runner: CliRunner, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Re-login a SA with a rotated MP_SECRET writes the new secret to config."""
        from mixpanel_headless import accounts as accounts_ns
        from mixpanel_headless._internal.auth.account import ServiceAccount

        accounts_ns.add(
            "team",
            type="service_account",
            region="us",
            username="u-old",
            secret=SecretStr("old-secret"),
        )
        # /me is now fetched on every relogin path (see PR-153 fix Issue 3
        # — the orchestrator persists me.json as a side effect even when
        # only credentials rotated).
        _stub_me(
            monkeypatch,
            {
                "user_id": 1,
                "user_email": "team@example.com",
                "organizations": {"100": {"id": 100, "name": "Team"}},
                "projects": {},
            },
        )
        monkeypatch.setenv("MP_USERNAME", "u-new")
        monkeypatch.setenv("MP_SECRET", "new-secret")
        result = runner.invoke(
            app,
            ["login", "--service-account", "--name", "team"],
        )
        assert result.exit_code == 0, result.output
        account = ConfigManager().get_account("team")
        assert isinstance(account, ServiceAccount)
        assert account.username == "u-new"
        assert account.secret.get_secret_value() == "new-secret"

    def test_relogin_sa_missing_username_errors(
        self, runner: CliRunner, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Re-login SA without MP_USERNAME → exit 1 with explicit message."""
        from mixpanel_headless import accounts as accounts_ns

        accounts_ns.add(
            "team",
            type="service_account",
            region="us",
            username="u",
            secret=SecretStr("s"),
        )
        monkeypatch.delenv("MP_USERNAME", raising=False)
        monkeypatch.setenv("MP_SECRET", "new-secret")
        # Force the SA detection branch — without MP_USERNAME present, the
        # auto-detect would fall through to oauth_browser and trigger E-4
        # instead of the credential-rotation error we want to assert.
        result = runner.invoke(
            app,
            ["login", "--service-account", "--name", "team"],
        )
        assert result.exit_code != 0, result.output
        assert "MP_USERNAME is not set" in result.output

    def test_relogin_oauth_token_inline_storage_keeps_inline_persist(
        self,
        runner: CliRunner,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Existing inline storage stays inline; relogin persists rotated bearer.

        Counterpart to ``...preserves_existing_env_ref``. When the
        existing account stores the bearer inline (not via env reference),
        re-running ``mp login --name ci`` honors that storage choice
        and writes the rotated value inline as before.
        """
        from mixpanel_headless import accounts as accounts_ns
        from mixpanel_headless._internal.auth.account import OAuthTokenAccount

        accounts_ns.add(
            "ci",
            type="oauth_token",
            region="us",
            token=SecretStr("old-bearer"),
        )
        # /me must succeed so login_unified can persist the cache and
        # populate the success-line fields.
        _stub_me(
            monkeypatch,
            {
                "user_id": 1,
                "user_email": "ci@example.com",
                "organizations": {"100": {"id": 100, "name": "CI Corp"}},
                "projects": {},
            },
        )
        monkeypatch.setenv("MP_OAUTH_TOKEN", "new-bearer")
        result = runner.invoke(app, ["login", "--name", "ci"])
        assert result.exit_code == 0, result.output
        account = ConfigManager().get_account("ci")
        assert isinstance(account, OAuthTokenAccount)
        assert account.token is not None
        assert account.token.get_secret_value() == "new-bearer"
        assert account.token_env is None

    def test_relogin_oauth_token_preserves_existing_env_ref(
        self,
        runner: CliRunner,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Re-login leaves ``token_env`` mode intact when no flag is passed.

        Pre-fix bug: when the existing account stored
        ``token_env=MP_OAUTH_TOKEN``, running ``mp login --name foo``
        without re-passing ``--token-env`` silently flipped persistence
        to inline ``SecretStr(bearer)``. The next rotation of
        ``MP_OAUTH_TOKEN`` then went stale because the resolver read
        the now-inline value, not the env. Issue #5 in the PR-153 fix
        plan: preserve the storage mode unless the caller explicitly
        opts into changing it.
        """
        from mixpanel_headless import accounts as accounts_ns
        from mixpanel_headless._internal.auth.account import OAuthTokenAccount

        accounts_ns.add(
            "ci",
            type="oauth_token",
            region="us",
            token_env="MP_OAUTH_TOKEN",
        )
        _stub_me(
            monkeypatch,
            {
                "user_id": 1,
                "user_email": "ci@example.com",
                "organizations": {"100": {"id": 100, "name": "CI Corp"}},
                "projects": {},
            },
        )
        monkeypatch.setenv("MP_OAUTH_TOKEN", "rotated-bearer")
        result = runner.invoke(app, ["login", "--name", "ci"])
        assert result.exit_code == 0, result.output
        account = ConfigManager().get_account("ci")
        assert isinstance(account, OAuthTokenAccount)
        # The mode invariant: token_env preserved, token still unset.
        assert account.token_env == "MP_OAUTH_TOKEN"
        assert account.token is None

    def test_relogin_oauth_token_explicit_token_env_can_switch_modes(
        self,
        runner: CliRunner,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Explicit ``--token-env NEW_VAR`` re-points the persisted env-var pointer.

        The escape hatch for the preservation rule above: passing
        ``--token-env`` explicitly lets the caller change the env-var
        target on a re-login (the original behavior, codified here so
        future refactors don't accidentally break the opt-in path).
        """
        from mixpanel_headless import accounts as accounts_ns
        from mixpanel_headless._internal.auth.account import OAuthTokenAccount

        accounts_ns.add(
            "ci",
            type="oauth_token",
            region="us",
            token_env="OLD_VAR",
        )
        _stub_me(
            monkeypatch,
            {
                "user_id": 1,
                "user_email": "ci@example.com",
                "organizations": {"100": {"id": 100, "name": "CI Corp"}},
                "projects": {},
            },
        )
        monkeypatch.setenv("NEW_VAR", "bearer-from-new-var")
        result = runner.invoke(app, ["login", "--name", "ci", "--token-env", "NEW_VAR"])
        assert result.exit_code == 0, result.output
        account = ConfigManager().get_account("ci")
        assert isinstance(account, OAuthTokenAccount)
        assert account.token_env == "NEW_VAR"
        assert account.token is None

    def test_relogin_oauth_token_persists_token_env_name(
        self, runner: CliRunner, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Re-login with --token-env switches the persisted env-var pointer."""
        from mixpanel_headless import accounts as accounts_ns
        from mixpanel_headless._internal.auth.account import OAuthTokenAccount

        accounts_ns.add(
            "agent",
            type="oauth_token",
            region="us",
            token_env="OLD_TOKEN_VAR",
        )
        _stub_me(
            monkeypatch,
            {
                "user_id": 1,
                "user_email": "agent@example.com",
                "organizations": {"100": {"id": 100, "name": "Agents"}},
                "projects": {},
            },
        )
        monkeypatch.setenv("NEW_TOKEN_VAR", "bearer-from-new-var")
        result = runner.invoke(
            app, ["login", "--name", "agent", "--token-env", "NEW_TOKEN_VAR"]
        )
        assert result.exit_code == 0, result.output
        account = ConfigManager().get_account("agent")
        assert isinstance(account, OAuthTokenAccount)
        assert account.token_env == "NEW_TOKEN_VAR"


class TestMpLoginStorageRoot:
    """``MP_OAUTH_STORAGE_DIR`` reaches the placeholder + final account dir."""

    def test_browser_login_honors_storage_dir_override(
        self, runner: CliRunner, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Browser login under MP_OAUTH_STORAGE_DIR puts tokens in override tree.

        The pre-fix bug: ``_login_unified_new_browser`` hard-coded
        ``Path.home() / ".mp" / "accounts"``, so PKCE wrote tokens to
        ``$HOME/.mp/accounts/{name}/tokens.json`` while the resolver
        looked under ``$MP_OAUTH_STORAGE_DIR/accounts/{name}/``. The
        next request would fail with "no tokens" even though login
        reported success.
        """
        from datetime import datetime, timedelta, timezone

        from mixpanel_headless._internal.auth import flow as flow_mod
        from mixpanel_headless._internal.auth.token import OAuthTokens

        override = tmp_path / "custom-mp"
        monkeypatch.setenv("MP_OAUTH_STORAGE_DIR", str(override))

        def _fake_pkce(
            self: object,
            project_id: str | None = None,
            *,
            persist: bool = True,
            open_browser: bool = True,
        ) -> OAuthTokens:
            return OAuthTokens(
                access_token=SecretStr("brw-tok"),
                refresh_token=SecretStr("brw-refresh"),
                expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
                scope="read:project",
                token_type="Bearer",
            )

        monkeypatch.setattr(flow_mod.OAuthFlow, "login", _fake_pkce)
        _stub_me(
            monkeypatch,
            {
                "user_id": 1,
                "organizations": {"100": {"id": 100, "name": "Acme Corp"}},
                "projects": {"42": {"name": "Demo", "organization_id": 100}},
            },
        )

        result = runner.invoke(app, ["login", "--project", "42"])
        assert result.exit_code == 0, result.output
        # Tokens must land under the override, not under $HOME/.mp/.
        assert (override / "accounts" / "acme-corp" / "tokens.json").exists()
        assert not (tmp_path / ".mp" / "accounts" / "acme-corp").exists()


class TestMpLoginNameValidation:
    """``--name`` traversal attempts must not leak tokens outside the tree."""

    def test_browser_invalid_name_does_not_publish_tokens(
        self,
        runner: CliRunner,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        """Browser ``--name '../escape'`` rejects before the placeholder rename.

        The pre-fix bug: ``final_dir = accounts_root / final_name`` happily
        constructed a path outside ``~/.mp/accounts/``; ``os.rename``
        published tokens there; ``add()``'s Pydantic validator then
        rejected the name; the cleanup branch checked ``.tmp-`` prefix
        and skipped, leaving tokens orphaned at ``~/.mp/escape/``.
        """
        from datetime import datetime, timedelta, timezone

        from mixpanel_headless._internal.auth import flow as flow_mod
        from mixpanel_headless._internal.auth.token import OAuthTokens

        def _fake_pkce(
            self: object,
            project_id: str | None = None,
            *,
            persist: bool = True,
            open_browser: bool = True,
        ) -> OAuthTokens:
            return OAuthTokens(
                access_token=SecretStr("brw-tok"),
                refresh_token=SecretStr("brw-refresh"),
                expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
                scope="read:project",
                token_type="Bearer",
            )

        monkeypatch.setattr(flow_mod.OAuthFlow, "login", _fake_pkce)
        _stub_me(
            monkeypatch,
            {
                "user_id": 1,
                "organizations": {"100": {"id": 100, "name": "Acme"}},
                "projects": {"42": {"name": "Demo", "organization_id": 100}},
            },
        )

        result = runner.invoke(
            app,
            ["login", "--name", "../escape", "--project", "42"],
        )
        assert result.exit_code != 0, result.output
        # No tokens should have escaped above the accounts tree.
        assert not (tmp_path / ".mp" / "escape").exists()
        # And the placeholder dir should have been cleaned up.
        accounts_dir = tmp_path / ".mp" / "accounts"
        if accounts_dir.exists():
            leftovers = [
                p for p in accounts_dir.iterdir() if p.name.startswith(".tmp-")
            ]
            assert leftovers == [], f"placeholder leak: {leftovers}"


class TestMpLoginPostRenameRollback:
    """``add()`` failure after the placeholder rename rolls back the on-disk publish.

    The pre-fix bug: after ``os.rename(placeholder_dir, final_dir)``
    succeeded, the cleanup branch's ``startswith(".tmp-")`` guard turned
    into a no-op for ``final_dir``. Any subsequent failure inside
    ``add()`` (TOML write fault, race that added the same name in
    another process) would leak ``~/.mp/accounts/{name}/tokens.json``
    with no matching ``[accounts.NAME]`` block — breaking
    ``mp account remove {name}`` and blocking the next ``mp login``.
    """

    def test_add_failure_rolls_back_final_dir(
        self,
        runner: CliRunner,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        """If ``add()`` raises after rename, ``final_dir`` is removed."""
        from datetime import datetime, timedelta, timezone

        from mixpanel_headless import accounts as accounts_ns
        from mixpanel_headless._internal.auth import flow as flow_mod
        from mixpanel_headless._internal.auth.token import OAuthTokens
        from mixpanel_headless.exceptions import ConfigError

        def _fake_pkce(
            self: object,
            project_id: str | None = None,
            *,
            persist: bool = True,
            open_browser: bool = True,
        ) -> OAuthTokens:
            return OAuthTokens(
                access_token=SecretStr("brw-tok"),
                refresh_token=SecretStr("brw-refresh"),
                expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
                scope="read:project",
                token_type="Bearer",
            )

        monkeypatch.setattr(flow_mod.OAuthFlow, "login", _fake_pkce)
        _stub_me(
            monkeypatch,
            {
                "user_id": 1,
                "organizations": {"100": {"id": 100, "name": "Rollback Corp"}},
                "projects": {"42": {"name": "Demo", "organization_id": 100}},
            },
        )

        # Force ``accounts.add`` to fail AFTER the orchestrator has
        # renamed the placeholder dir into place. The orchestrator
        # imports ``add`` at module top-level, so we patch the binding
        # in the accounts module itself.
        original_add = accounts_ns.add

        def _failing_add(*args: object, **kwargs: object) -> object:
            del args, kwargs
            raise ConfigError("simulated post-rename add() failure")

        monkeypatch.setattr(accounts_ns, "add", _failing_add)

        result = runner.invoke(app, ["login", "--project", "42"])
        assert result.exit_code != 0, result.output
        assert "simulated post-rename add() failure" in result.output

        # ``final_dir`` (~/.mp/accounts/rollback-corp/) must be gone —
        # the rollback should have removed the directory the rename
        # published, not just left the cleanup as a no-op.
        final_dir = tmp_path / ".mp" / "accounts" / "rollback-corp"
        assert not final_dir.exists(), (
            f"post-rename rollback failed; final_dir survived: "
            f"{list(final_dir.iterdir()) if final_dir.exists() else []}"
        )

        # And no orphan placeholders either.
        accounts_dir = tmp_path / ".mp" / "accounts"
        if accounts_dir.exists():
            leftovers = [
                p for p in accounts_dir.iterdir() if p.name.startswith(".tmp-")
            ]
            assert leftovers == [], f"placeholder leak: {leftovers}"

        # Restore the patched add for any later tests that share the module.
        monkeypatch.setattr(accounts_ns, "add", original_add)


class TestMpLoginStaleEnvProject:
    """``MP_PROJECT_ID`` set in env but not visible → hard-fail at login."""

    def test_stale_mp_project_id_raises_at_login(
        self, runner: CliRunner, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Login with stale MP_PROJECT_ID exits non-zero with the env-var name.

        Pre-fix behavior: warned to stderr, fell through to the picker,
        persisted picker's choice as default_project. Subsequent `mp
        query` then read MP_PROJECT_ID first (env > config in the
        resolver) and silently failed with an auth error pointing at
        the wrong place. The hard-fail surfaces the misconfiguration
        at the moment the user is most likely to fix it.
        """
        monkeypatch.setenv("MP_USERNAME", "svc")
        monkeypatch.setenv("MP_SECRET", "secret")
        monkeypatch.setenv("MP_PROJECT_ID", "999")
        _stub_me(
            monkeypatch,
            {
                "user_id": 1,
                "user_email": "svc@example.com",
                "organizations": {"100": {"id": 100, "name": "Acme Corp"}},
                "projects": {"42": {"name": "Demo", "organization_id": 100}},
            },
        )
        result = runner.invoke(app, ["login", "--service-account", "--region", "us"])
        assert result.exit_code != 0, result.output
        # The error must surface BOTH the stale env-var name AND the
        # accessible alternatives so the user can fix without a second probe.
        assert "MP_PROJECT_ID" in result.output
        assert "999" in result.output
        assert "42" in result.output


class TestProjectPickerTTY:
    """Direct-call coverage for ``_project_picker_tty`` (login.py).

    The orchestrator wires this into ``login_unified`` only when /me has
    more than one accessible project. The CLI tests above mostly stub
    /me to a single-project payload, so the picker's behavior was
    exercised entirely by the production codepath without any focused
    assertions. These tests call the picker directly so the priority
    chain (default-on-empty, numeric pick, retry, non-TTY refusal,
    closed-stdin EOFError) is locked.
    """

    def _make_me_with_projects(
        self, project_count: int
    ) -> tuple[MeResponse, list[tuple[str, MeProjectInfo]]]:
        """Build a MeResponse and pre-sorted project list with ``project_count`` entries.

        Args:
            project_count: How many projects to fabricate.

        Returns:
            ``(me_response, sorted_projects_list)`` ready to pass to the picker.
        """
        from mixpanel_headless._internal.me import (
            MeOrgInfo,
            MeProjectInfo,
            MeResponse,
        )

        orgs = {"100": MeOrgInfo(id=100, name="Acme Corp")}
        projects = {
            str(1000 + idx): MeProjectInfo(
                name=f"Project {idx}",
                organization_id=100,
                domain="mixpanel.com",
            )
            for idx in range(project_count)
        }
        me = MeResponse(organizations=orgs, projects=projects)
        sorted_list = sorted(projects.items(), key=lambda kv: kv[1].name.lower())
        return me, sorted_list

    def _stub_readline(self, monkeypatch: pytest.MonkeyPatch, lines: list[str]) -> None:
        """Patch ``sys.stdin.readline`` to return ``lines`` in order.

        Replaces the older ``builtins.input`` monkeypatch — the picker
        now writes the prompt to stderr and reads via
        ``sys.stdin.readline`` so stdout stays clean for
        ``mp login | tee`` (PR-153 fix Issue 4). Tests call this helper
        with a list of lines (each must end in ``\\n`` to mimic real
        stdin); EOF is signalled by an empty string.

        Args:
            monkeypatch: pytest fixture for environment manipulation.
            lines: Lines to return on successive ``readline`` calls.
        """
        iterator = iter(lines)
        monkeypatch.setattr("sys.stdin.readline", lambda: next(iterator))

    def test_returns_default_on_empty_input(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Empty input (just Enter) returns the first project in the sorted list."""
        from mixpanel_headless.cli.commands.login import _project_picker_tty

        me, sorted_projects = self._make_me_with_projects(3)
        monkeypatch.setattr("sys.stdin.isatty", lambda: True)
        self._stub_readline(monkeypatch, ["\n"])

        result = _project_picker_tty(me, sorted_projects)
        assert result == sorted_projects[0][0]

    def test_returns_indexed_pick(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Numeric input returns the project at that 1-based index."""
        from mixpanel_headless.cli.commands.login import _project_picker_tty

        me, sorted_projects = self._make_me_with_projects(3)
        monkeypatch.setattr("sys.stdin.isatty", lambda: True)
        self._stub_readline(monkeypatch, ["2\n"])

        result = _project_picker_tty(me, sorted_projects)
        assert result == sorted_projects[1][0]

    def test_three_invalid_attempts_raise_config_error(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Three garbage inputs raise ConfigError mentioning 'after 3 attempts'."""
        from mixpanel_headless.cli.commands.login import _project_picker_tty
        from mixpanel_headless.exceptions import ConfigError

        me, sorted_projects = self._make_me_with_projects(3)
        monkeypatch.setattr("sys.stdin.isatty", lambda: True)
        self._stub_readline(monkeypatch, ["garbage\n", "garbage\n", "garbage\n"])

        with pytest.raises(ConfigError) as exc_info:
            _project_picker_tty(me, sorted_projects)
        assert "3 attempts" in exc_info.value.message

    def test_non_tty_raises_config_error_with_accessible_list(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Non-TTY context raises ConfigError listing accessible projects (E-9)."""
        from mixpanel_headless.cli.commands.login import _project_picker_tty
        from mixpanel_headless.exceptions import ConfigError

        me, sorted_projects = self._make_me_with_projects(3)
        monkeypatch.setattr("sys.stdin.isatty", lambda: False)

        with pytest.raises(ConfigError) as exc_info:
            _project_picker_tty(me, sorted_projects)
        msg = exc_info.value.message
        assert "Multiple projects accessible" in msg
        assert "MP_PROJECT_ID" in msg
        # All three project IDs must appear in the accessible list.
        for pid, _ in sorted_projects:
            assert pid in msg

    def test_eof_during_input_raises_config_error(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """``readline`` returning ``""`` (EOF) is mapped to ConfigError, not a traceback."""
        from mixpanel_headless.cli.commands.login import _project_picker_tty
        from mixpanel_headless.exceptions import ConfigError

        me, sorted_projects = self._make_me_with_projects(3)
        monkeypatch.setattr("sys.stdin.isatty", lambda: True)
        # ``sys.stdin.readline()`` returns "" (empty string) on EOF — no
        # newline. The picker treats that as "stdin closed" and raises
        # ConfigError so @handle_errors renders a structured exit
        # instead of a bare Python traceback.
        self._stub_readline(monkeypatch, [""])

        with pytest.raises(ConfigError) as exc_info:
            _project_picker_tty(me, sorted_projects)
        assert "stdin closed" in exc_info.value.message

    def test_unicode_digit_treated_as_invalid(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Unicode digit '²' fails ``int()`` but must re-prompt, not crash.

        Pre-fix bug (Issue 8): ``raw.isdigit()`` is True for Unicode
        digits like ``²`` / ``٣``, but ``int(raw)`` then raises
        ``ValueError``. The exception bubbled up through
        ``@handle_errors`` as a generic Exception instead of triggering
        the in-loop re-prompt path. Wrapping the int() conversion in a
        try/except routes the unicode case through the normal
        "Invalid input" loop.
        """
        from mixpanel_headless.cli.commands.login import _project_picker_tty
        from mixpanel_headless.exceptions import ConfigError

        me, sorted_projects = self._make_me_with_projects(3)
        monkeypatch.setattr("sys.stdin.isatty", lambda: True)
        self._stub_readline(monkeypatch, ["²\n", "²\n", "²\n"])

        # Three Unicode-digit attempts → ConfigError after 3 attempts,
        # NOT a generic ValueError leaking from int().
        with pytest.raises(ConfigError) as exc_info:
            _project_picker_tty(me, sorted_projects)
        assert "3 attempts" in exc_info.value.message

    def test_unicode_digit_recovers_with_ascii_pick(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """First-attempt unicode digit, second-attempt valid ASCII → returns the pick.

        Belt-and-suspenders for Issue 8: confirm the loop is genuinely
        retrying rather than terminating early on the first ValueError.
        """
        from mixpanel_headless.cli.commands.login import _project_picker_tty

        me, sorted_projects = self._make_me_with_projects(3)
        monkeypatch.setattr("sys.stdin.isatty", lambda: True)
        self._stub_readline(monkeypatch, ["²\n", "2\n"])

        result = _project_picker_tty(me, sorted_projects)
        assert result == sorted_projects[1][0]

    def test_prompt_writes_to_stderr_not_stdout(
        self, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Picker prompt lands on stderr; stdout stays clean for `mp login | tee`.

        Pre-fix bug (Issue 4): ``input("Which project? ...")`` wrote
        the prompt to stdout, breaking the cli-commands.md §1.4
        contract that reserves stdout for the structured success line.
        Switching to ``err_console.print`` + ``sys.stdin.readline``
        routes prompts to stderr.
        """
        from mixpanel_headless.cli.commands.login import _project_picker_tty

        me, sorted_projects = self._make_me_with_projects(3)
        monkeypatch.setattr("sys.stdin.isatty", lambda: True)
        self._stub_readline(monkeypatch, ["1\n"])

        _project_picker_tty(me, sorted_projects)
        captured = capsys.readouterr()
        assert "Which project?" in captured.err
        assert "Which project?" not in captured.out


class TestMpLoginSuccessLineContract:
    """Stdout success line matches cli-commands.md §1.4 verbatim.

    Pre-fix bug (PR-153 Issue 2): the CLI printed
    ``Logged in → {name} · {project_id}`` — missing the ``as
    {user_email}`` prefix and using the project ID where the contract
    specified the project name. The legacy substring-only assertion
    let the regression slip through. This test pins the exact format.
    """

    def test_format_is_logged_in_as_email_arrow_name_dot_project(
        self, runner: CliRunner, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Stdout: ``Logged in as {user_email} → {account_name} · {project_name}``."""
        monkeypatch.setenv("MP_USERNAME", "svc")
        monkeypatch.setenv("MP_SECRET", "secret")
        _stub_me(
            monkeypatch,
            {
                "user_id": 1,
                "user_email": "svc@example.com",
                "organizations": {"100": {"id": 100, "name": "Acme Corp"}},
                "projects": {
                    "12345": {"name": "Acme Production", "organization_id": 100}
                },
            },
        )
        result = runner.invoke(
            app,
            [
                "login",
                "--service-account",
                "--name",
                "prod-sa",
                "--region",
                "us",
                "--project",
                "12345",
            ],
        )
        assert result.exit_code == 0, result.output
        # The contract format. Exact string match (modulo trailing newline).
        expected = "Logged in as svc@example.com → prod-sa · Acme Production"
        # ``result.output`` aggregates stdout and stderr; the success line
        # is the last non-empty line of stdout.
        last_line = next(
            (line for line in reversed(result.output.splitlines()) if line.strip()),
            "",
        )
        assert last_line == expected, (
            f"Success line mismatch.\n  got: {last_line!r}\n  want: {expected!r}"
        )

    def test_format_falls_back_when_me_lacks_email(
        self, runner: CliRunner, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Missing ``/me.user_email`` falls back to ``(unknown user)`` placeholder.

        Keeps the line shape parseable when the API returns a partial
        payload. Better than printing ``None`` or crashing on a None
        format-string.
        """
        monkeypatch.setenv("MP_USERNAME", "svc")
        monkeypatch.setenv("MP_SECRET", "secret")
        _stub_me(
            monkeypatch,
            {
                "user_id": 1,
                # user_email intentionally absent.
                "organizations": {"100": {"id": 100, "name": "Acme"}},
                "projects": {"7": {"name": "P", "organization_id": 100}},
            },
        )
        result = runner.invoke(
            app,
            [
                "login",
                "--service-account",
                "--name",
                "fb",
                "--region",
                "us",
                "--project",
                "7",
            ],
        )
        assert result.exit_code == 0, result.output
        last_line = next(
            (line for line in reversed(result.output.splitlines()) if line.strip()),
            "",
        )
        assert last_line == "Logged in as (unknown user) → fb · P"
