"""End-to-end integration test for the three account types (T037).

Registers one ServiceAccount, one OAuthBrowserAccount (mocked browser
flow — we just write a tokens.json directly), one OAuthTokenAccount;
verifies ``mp.accounts.list()`` returns all three, and switching between
them via ``mp.accounts.use(name)`` is consistent.

Reference: specs/042-auth-architecture-redesign/contracts/python-api.md §5.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from pydantic import SecretStr

from mixpanel_headless import accounts as accounts_ns
from mixpanel_headless._internal.config import ConfigManager


@pytest.fixture(autouse=True)
def _isolated_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Isolate $HOME and MP_CONFIG_PATH."""
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("MP_CONFIG_PATH", str(tmp_path / ".mp" / "config.toml"))


def _write_tokens_for(name: str, home: Path) -> None:
    """Write a fake on-disk tokens.json for an oauth_browser account."""
    account_dir = home / ".mp" / "accounts" / name
    account_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    tokens_path = account_dir / "tokens.json"
    expires_at = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
    tokens_path.write_text(
        json.dumps(
            {
                "access_token": f"mock-tok-{name}",
                "refresh_token": "ref",
                "expires_at": expires_at,
                "scope": "read",
                "token_type": "Bearer",
            }
        ),
        encoding="utf-8",
    )
    tokens_path.chmod(0o600)


class TestThreeAccountTypes:
    """All three account types coexist and are independently switchable."""

    def test_register_three_types(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Register all three account variants via mp.accounts.add."""
        # ServiceAccount.
        accounts_ns.add(
            "team",
            type="service_account",
            region="us",
            default_project="3713224",
            username="team.sa",
            secret=SecretStr("team-secret"),
        )
        # OAuthBrowserAccount — write fake tokens.json to skip the browser.
        accounts_ns.add("personal", type="oauth_browser", region="us")
        _write_tokens_for("personal", tmp_path)
        # OAuthTokenAccount.
        monkeypatch.setenv("MY_OAUTH_TOK", "ci-bearer")
        accounts_ns.add(
            "ci",
            type="oauth_token",
            region="us",
            default_project="3713224",
            token_env="MY_OAUTH_TOK",
        )

        summaries = accounts_ns.list()
        names = sorted(s.name for s in summaries)
        assert names == ["ci", "personal", "team"]
        types = {s.name: s.type for s in summaries}
        assert types["team"] == "service_account"
        assert types["personal"] == "oauth_browser"
        assert types["ci"] == "oauth_token"

    def test_switch_between_types(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Switching active account works for each type via mp.accounts.use."""
        accounts_ns.add(
            "team",
            type="service_account",
            region="us",
            default_project="3713224",
            username="u",
            secret=SecretStr("s"),
        )
        accounts_ns.add("personal", type="oauth_browser", region="us")
        _write_tokens_for("personal", tmp_path)
        monkeypatch.setenv("MY_OAUTH_TOK", "ci-bearer")
        accounts_ns.add(
            "ci",
            type="oauth_token",
            region="us",
            default_project="3713224",
            token_env="MY_OAUTH_TOK",
        )

        cm = ConfigManager()
        for name in ("personal", "ci", "team"):
            accounts_ns.use(name)
            assert cm.get_active().account == name
