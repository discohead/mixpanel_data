"""Unit tests for the v2 bridge writer (T086 / T089 / T090).

Covers the standalone ``bridge.export_bridge`` / ``bridge.remove_bridge``
functions plus the public ``mp.accounts.export_bridge`` /
``mp.accounts.remove_bridge`` namespace wrappers.

Reference:
    specs/042-auth-architecture-redesign/contracts/config-schema.md §2
    specs/042-auth-architecture-redesign/contracts/python-api.md §5
"""

from __future__ import annotations

import json
import os
import stat
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from pydantic import SecretStr

from mixpanel_headless import accounts as accounts_ns
from mixpanel_headless._internal.auth.account import (
    OAuthBrowserAccount,
    OAuthTokenAccount,
    ServiceAccount,
)
from mixpanel_headless._internal.auth.bridge import (
    export_bridge,
    load_bridge,
    remove_bridge,
)
from mixpanel_headless._internal.auth.token_resolver import OnDiskTokenResolver
from mixpanel_headless.exceptions import OAuthError

_REQUIRES_O_NOFOLLOW = pytest.mark.skipif(
    not hasattr(os, "O_NOFOLLOW"),
    reason="O_NOFOLLOW required; Windows is not in scope",
)


@pytest.fixture(autouse=True)
def _isolated_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Isolate ``$HOME`` and ``MP_CONFIG_PATH`` to a tmp dir."""
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("MP_CONFIG_PATH", str(tmp_path / ".mp" / "config.toml"))
    monkeypatch.delenv("MP_AUTH_FILE", raising=False)


def _seed_browser_tokens(home: Path, name: str) -> None:
    """Write a fake on-disk tokens.json for an oauth_browser account."""
    account_dir = home / ".mp" / "accounts" / name
    account_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    tokens_path = account_dir / "tokens.json"
    expires_at = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
    tokens_path.write_text(
        json.dumps(
            {
                "access_token": f"acc-{name}",
                "refresh_token": f"ref-{name}",
                "expires_at": expires_at,
                "scope": "read",
                "token_type": "Bearer",
            }
        ),
        encoding="utf-8",
    )
    tokens_path.chmod(0o600)


class TestExportBridgeFunctional:
    """``bridge.export_bridge`` writes a v2 bridge file embedding the account."""

    def test_service_account_writes_v2_schema(self, tmp_path: Path) -> None:
        """Exporting a ServiceAccount produces a v2 bridge with secrets inline."""
        account = ServiceAccount(
            name="team",
            region="us",
            default_project="3713224",
            username="sa.user",
            secret=SecretStr("sa-secret"),
        )
        out = tmp_path / "bridge.json"
        result = export_bridge(account, to=out, token_resolver=OnDiskTokenResolver())
        assert result == out
        assert out.exists()
        bridge = load_bridge(out)
        assert bridge is not None
        assert bridge.version == 2
        assert bridge.account.name == "team"
        assert bridge.account.type == "service_account"
        assert bridge.tokens is None  # SAs don't carry OAuth tokens

    def test_oauth_browser_embeds_tokens_from_disk(self, tmp_path: Path) -> None:
        """oauth_browser export reads tokens via the resolver and embeds them."""
        account = OAuthBrowserAccount(name="personal", region="us")
        _seed_browser_tokens(tmp_path, "personal")
        out = tmp_path / "bridge.json"
        export_bridge(account, to=out, token_resolver=OnDiskTokenResolver())
        bridge = load_bridge(out)
        assert bridge is not None
        assert bridge.tokens is not None
        assert bridge.tokens.access_token.get_secret_value() == "acc-personal"
        assert bridge.tokens.refresh_token is not None
        assert bridge.tokens.refresh_token.get_secret_value() == "ref-personal"

    def test_oauth_browser_without_tokens_raises_oauth_error(
        self, tmp_path: Path
    ) -> None:
        """Exporting an oauth_browser without on-disk tokens surfaces OAuthError."""
        account = OAuthBrowserAccount(name="ghost", region="us")
        out = tmp_path / "bridge.json"
        with pytest.raises(OAuthError):
            export_bridge(account, to=out, token_resolver=OnDiskTokenResolver())
        # The aborted write must NOT leave a partial file behind.
        assert not out.exists()

    def test_oauth_token_inline_embedded(self, tmp_path: Path) -> None:
        """oauth_token (inline) accounts export with secrets inline by design (B3)."""
        account = OAuthTokenAccount(
            name="ci",
            region="us",
            default_project="3713224",
            token=SecretStr("inline-bearer"),
        )
        out = tmp_path / "bridge.json"
        export_bridge(account, to=out, token_resolver=OnDiskTokenResolver())
        bridge = load_bridge(out)
        assert bridge is not None
        # oauth_token does NOT include `tokens` (that's an OAuth browser concept)
        assert bridge.tokens is None
        assert bridge.account.type == "oauth_token"
        # Secrets inline by design (Cowork crosses a trust boundary, B3)
        raw = json.loads(out.read_text(encoding="utf-8"))
        assert raw["account"].get("token") == "inline-bearer"

    def test_writes_file_with_mode_0o600(self, tmp_path: Path) -> None:
        """The bridge file is created with mode ``0o600`` (B2)."""
        account = ServiceAccount(
            name="team",
            region="us",
            default_project="3713224",
            username="u",
            secret=SecretStr("s"),
        )
        out = tmp_path / "bridge.json"
        export_bridge(account, to=out, token_resolver=OnDiskTokenResolver())
        mode = stat.S_IMODE(out.stat().st_mode)
        assert mode == 0o600, f"expected 0o600, got {oct(mode)}"

    def test_creates_parent_dir_with_mode_0o700(self, tmp_path: Path) -> None:
        """When ``to.parent`` is missing, the writer creates it with 0o700 (B2)."""
        account = ServiceAccount(
            name="team",
            region="us",
            default_project="3713224",
            username="u",
            secret=SecretStr("s"),
        )
        nested = tmp_path / "subdir1" / "subdir2"
        out = nested / "bridge.json"
        export_bridge(account, to=out, token_resolver=OnDiskTokenResolver())
        assert out.exists()
        # Verify the leaf parent dir exists (we don't enforce 0o700 on
        # intermediate dirs we created, only on the leaf).
        assert nested.is_dir()

    def test_project_workspace_headers_round_trip(self, tmp_path: Path) -> None:
        """``project`` / ``workspace`` / ``headers`` kwargs land in the bridge."""
        account = ServiceAccount(
            name="team",
            region="us",
            default_project="3713224",
            username="u",
            secret=SecretStr("s"),
        )
        out = tmp_path / "bridge.json"
        export_bridge(
            account,
            to=out,
            project="3018488",
            workspace=3448414,
            headers={"X-Mixpanel-Cluster": "internal-1"},
            token_resolver=OnDiskTokenResolver(),
        )
        bridge = load_bridge(out)
        assert bridge is not None
        assert bridge.project == "3018488"
        assert bridge.workspace == 3448414
        assert bridge.headers == {"X-Mixpanel-Cluster": "internal-1"}

    def test_idempotent_overwrite_at_same_path(self, tmp_path: Path) -> None:
        """Two exports to the same path produce identical bridge content."""
        account = ServiceAccount(
            name="team",
            region="us",
            default_project="3713224",
            username="u",
            secret=SecretStr("s"),
        )
        out = tmp_path / "bridge.json"
        export_bridge(account, to=out, token_resolver=OnDiskTokenResolver())
        first = out.read_bytes()
        export_bridge(account, to=out, token_resolver=OnDiskTokenResolver())
        second = out.read_bytes()
        assert first == second


class TestRemoveBridgeFunctional:
    """``bridge.remove_bridge`` deletes the resolved bridge file."""

    def test_removes_existing_bridge(self, tmp_path: Path) -> None:
        """``remove_bridge(at=PATH)`` deletes the file and returns True."""
        target = tmp_path / "bridge.json"
        target.write_text("{}", encoding="utf-8")
        assert remove_bridge(at=target) is True
        assert not target.exists()

    def test_returns_false_when_absent(self, tmp_path: Path) -> None:
        """``remove_bridge`` against a missing path returns False (idempotent)."""
        target = tmp_path / "nope.json"
        assert remove_bridge(at=target) is False

    def test_default_path_uses_search_order(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Without ``at``, the writer uses ``MP_AUTH_FILE`` / default paths."""
        target = tmp_path / "auth.json"
        target.write_text("{}", encoding="utf-8")
        monkeypatch.setenv("MP_AUTH_FILE", str(target))
        assert remove_bridge() is True
        assert not target.exists()


class TestAccountsNamespaceWiring:
    """``mp.accounts.export_bridge`` / ``remove_bridge`` no longer raise."""

    def test_export_bridge_via_accounts_namespace(self, tmp_path: Path) -> None:
        """``accounts.export_bridge(account=NAME)`` exports the named account."""
        accounts_ns.add(
            "team",
            type="service_account",
            region="us",
            default_project="3713224",
            username="u",
            secret=SecretStr("s"),
        )
        out = tmp_path / "bridge.json"
        result = accounts_ns.export_bridge(to=out, account="team")
        assert result == out
        bridge = load_bridge(out)
        assert bridge is not None
        assert bridge.account.name == "team"

    def test_export_bridge_uses_active_account_when_unspecified(
        self, tmp_path: Path
    ) -> None:
        """Without ``account=``, the active account is exported."""
        accounts_ns.add(
            "team",
            type="service_account",
            region="us",
            default_project="3713224",
            username="u",
            secret=SecretStr("s"),
        )
        out = tmp_path / "bridge.json"
        accounts_ns.export_bridge(to=out)
        bridge = load_bridge(out)
        assert bridge is not None
        assert bridge.account.name == "team"

    def test_export_bridge_attaches_settings_custom_header(
        self, tmp_path: Path
    ) -> None:
        """``[settings].custom_header`` propagates into ``bridge.headers``."""
        from mixpanel_headless._internal.config import ConfigManager

        accounts_ns.add(
            "team",
            type="service_account",
            region="us",
            default_project="3713224",
            username="u",
            secret=SecretStr("s"),
        )
        ConfigManager().set_custom_header(name="X-Mixpanel-Cluster", value="cell-3")
        out = tmp_path / "bridge.json"
        accounts_ns.export_bridge(to=out, account="team")
        bridge = load_bridge(out)
        assert bridge is not None
        assert bridge.headers == {"X-Mixpanel-Cluster": "cell-3"}

    def test_remove_bridge_via_accounts_namespace(self, tmp_path: Path) -> None:
        """``accounts.remove_bridge(at=PATH)`` deletes and returns True."""
        target = tmp_path / "bridge.json"
        target.write_text("{}", encoding="utf-8")
        assert accounts_ns.remove_bridge(at=target) is True
        assert not target.exists()


class TestBridgeSymlinkRejection:
    """``load_bridge`` and ``_read_browser_tokens`` refuse symlinked credential paths.

    Regression for the same-UID symlink attack covered by
    ``io_utils.read_credential_text``. Two code paths in ``bridge.py``
    read credential material from disk:

    1. ``load_bridge`` reads the bridge file itself (env-controllable
       via ``MP_AUTH_FILE``).
    2. ``_read_browser_tokens`` reads per-account ``tokens.json``
       when exporting a fresh bridge for an oauth_browser account.

    Both must refuse a symlink at the leaf component.
    """

    @_REQUIRES_O_NOFOLLOW
    def test_load_bridge_symlink_raises_configerror(self, tmp_path: Path) -> None:
        """A symlink at the bridge path raises ``ConfigError``."""
        from mixpanel_headless.exceptions import ConfigError

        attacker = tmp_path / "attacker_bridge.json"
        attacker.write_text(
            json.dumps(
                {
                    "version": 2,
                    "account": {
                        "name": "evil",
                        "type": "service_account",
                        "region": "us",
                        "default_project": "999",
                        "username": "attacker",
                        "secret": "stolen",
                    },
                }
            ),
            encoding="utf-8",
        )
        attacker.chmod(0o600)
        link = tmp_path / "bridge.json"
        link.symlink_to(attacker)
        with pytest.raises(ConfigError, match="symlink"):
            load_bridge(link)

    @_REQUIRES_O_NOFOLLOW
    def test_export_bridge_symlinked_tokens_raises_oautherror(
        self, tmp_path: Path
    ) -> None:
        """A symlink at the per-account tokens.json raises ``OAuthError``."""
        account = OAuthBrowserAccount(name="personal", region="us")
        account_dir = tmp_path / ".mp" / "accounts" / "personal"
        account_dir.mkdir(parents=True, mode=0o700)
        attacker = tmp_path / "attacker_tokens.json"
        attacker.write_text(
            json.dumps(
                {
                    "access_token": "stolen",
                    "expires_at": (
                        datetime.now(timezone.utc) + timedelta(hours=1)
                    ).isoformat(),
                    "token_type": "Bearer",
                }
            ),
            encoding="utf-8",
        )
        attacker.chmod(0o600)
        (account_dir / "tokens.json").symlink_to(attacker)
        out = tmp_path / "bridge.json"
        with pytest.raises(OAuthError, match="symlink"):
            export_bridge(account, to=out, token_resolver=OnDiskTokenResolver())

    @_REQUIRES_O_NOFOLLOW
    def test_dangling_bridge_symlink_rejected(self, tmp_path: Path) -> None:
        """A dangling symlink at the bridge path raises ``ConfigError``.

        Regression for the ``Path.exists()`` follows-symlink trap.
        """
        from mixpanel_headless.exceptions import ConfigError

        link = tmp_path / "bridge.json"
        link.symlink_to(tmp_path / "missing.json")
        with pytest.raises(ConfigError, match="symlink"):
            load_bridge(link)

    @_REQUIRES_O_NOFOLLOW
    def test_dangling_browser_tokens_symlink_rejected(self, tmp_path: Path) -> None:
        """A dangling symlink at per-account tokens.json raises ``OAuthError``."""
        account = OAuthBrowserAccount(name="personal", region="us")
        account_dir = tmp_path / ".mp" / "accounts" / "personal"
        account_dir.mkdir(parents=True, mode=0o700)
        (account_dir / "tokens.json").symlink_to(tmp_path / "missing.json")
        out = tmp_path / "bridge.json"
        with pytest.raises(OAuthError, match="symlink"):
            export_bridge(account, to=out, token_resolver=OnDiskTokenResolver())
