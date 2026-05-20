"""Tests for ``_internal/auth/inflight.py``.

Covers the on-disk inflight session lifecycle, placeholder helpers, and
the boundaries between fresh / expired / corrupt state. Mirrors the
existing test patterns in :mod:`tests.unit.test_auth_storage` —
``monkeypatch.setenv("MP_OAUTH_STORAGE_DIR", str(tmp_path))`` for
hermetic isolation, no respx, no live network.
"""

from __future__ import annotations

import json
import stat
import time
from pathlib import Path

import pytest

from mixpanel_headless._internal.auth.inflight import (
    INFLIGHT_SCHEMA_VERSION,
    INFLIGHT_TTL_SECONDS,
    PLACEHOLDER_META_SCHEMA_VERSION,
    InflightSession,
    cache_me_in_placeholder,
    clear_inflight,
    find_available_callback_port,
    inflight_path,
    load_cached_me_from_placeholder,
    load_inflight,
    new_placeholder_dir,
    read_placeholder_meta,
    read_tokens_from_placeholder,
    save_inflight,
    save_placeholder_meta,
)
from mixpanel_headless._internal.me import MeProjectInfo, MeResponse
from mixpanel_headless.exceptions import OAuthError


@pytest.fixture
def isolated_storage(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point storage helpers at ``tmp_path`` for hermetic test isolation."""
    monkeypatch.setenv("MP_OAUTH_STORAGE_DIR", str(tmp_path))
    return tmp_path


def _make_session(*, expires_in: int = INFLIGHT_TTL_SECONDS) -> InflightSession:
    """Build a fresh InflightSession with realistic field values."""
    now = int(time.time())
    return InflightSession(
        schema_version=INFLIGHT_SCHEMA_VERSION,
        region="us",
        client_id="test_client_abcdef",
        redirect_uri="http://localhost:19284/callback",
        pkce_verifier="x" * 64,
        state="state_1234567890",
        created_at=now,
        expires_at=now + expires_in,
    )


class TestSaveLoadRoundTrip:
    """save_inflight + load_inflight produce structurally identical sessions."""

    def test_round_trip_preserves_all_fields(self, isolated_storage: Path) -> None:
        """Every field round-trips byte-for-byte through disk."""
        session = _make_session()
        save_inflight(session)
        loaded = load_inflight()
        assert loaded == session

    def test_inflight_file_mode_is_600(self, isolated_storage: Path) -> None:
        """Verifier is a single-use secret — file must be owner-only."""
        save_inflight(_make_session())
        path = inflight_path()
        mode = stat.S_IMODE(path.stat().st_mode)
        assert mode == 0o600, f"Expected 0o600, got {oct(mode)}"

    def test_parent_dir_mode_is_700(self, isolated_storage: Path) -> None:
        """Parent dir gets 0o700 even when the storage root is fresh."""
        save_inflight(_make_session())
        parent = inflight_path().parent
        mode = stat.S_IMODE(parent.stat().st_mode)
        assert mode == 0o700, f"Expected 0o700, got {oct(mode)}"

    def test_second_start_clobbers_prior_inflight(self, isolated_storage: Path) -> None:
        """Second --start silently replaces the prior inflight file."""
        first = _make_session()
        save_inflight(first)
        second = InflightSession(
            schema_version=INFLIGHT_SCHEMA_VERSION,
            region="eu",
            client_id="different_client",
            redirect_uri="http://localhost:19285/callback",
            pkce_verifier="y" * 64,
            state="different_state",
            created_at=first.created_at + 1,
            expires_at=first.expires_at + 1,
        )
        save_inflight(second)
        loaded = load_inflight()
        assert loaded == second
        assert loaded != first


class TestLoadFailures:
    """load_inflight raises structured OAuthError for each failure mode."""

    def test_missing_file_raises_inflight_missing(self, isolated_storage: Path) -> None:
        """No file → OAUTH_INFLIGHT_MISSING."""
        with pytest.raises(OAuthError) as exc:
            load_inflight()
        assert exc.value.code == "OAUTH_INFLIGHT_MISSING"

    def test_expired_file_raises_inflight_expired(self, isolated_storage: Path) -> None:
        """expires_at < now() → OAUTH_INFLIGHT_EXPIRED."""
        session = _make_session(expires_in=-1)
        save_inflight(session)
        with pytest.raises(OAuthError) as exc:
            load_inflight()
        assert exc.value.code == "OAUTH_INFLIGHT_EXPIRED"

    def test_malformed_json_raises_inflight_corrupt(
        self, isolated_storage: Path
    ) -> None:
        """Non-JSON content → OAUTH_INFLIGHT_CORRUPT."""
        path = inflight_path()
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        path.write_text("not json at all", encoding="utf-8")
        with pytest.raises(OAuthError) as exc:
            load_inflight()
        assert exc.value.code == "OAUTH_INFLIGHT_CORRUPT"

    def test_missing_required_keys_raises_inflight_corrupt(
        self, isolated_storage: Path
    ) -> None:
        """JSON object missing required fields → OAUTH_INFLIGHT_CORRUPT."""
        path = inflight_path()
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        path.write_text(json.dumps({"region": "us"}), encoding="utf-8")
        with pytest.raises(OAuthError) as exc:
            load_inflight()
        assert exc.value.code == "OAUTH_INFLIGHT_CORRUPT"

    def test_non_object_json_raises_inflight_corrupt(
        self, isolated_storage: Path
    ) -> None:
        """JSON array (not object) → OAUTH_INFLIGHT_CORRUPT."""
        path = inflight_path()
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        path.write_text(json.dumps(["wrong", "shape"]), encoding="utf-8")
        with pytest.raises(OAuthError) as exc:
            load_inflight()
        assert exc.value.code == "OAUTH_INFLIGHT_CORRUPT"

    def test_schema_too_new_raises_inflight_schema_too_new(
        self, isolated_storage: Path
    ) -> None:
        """Inflight with ``schema_version > INFLIGHT_SCHEMA_VERSION`` → SCHEMA_TOO_NEW.

        Forward-compat guard: if a future CLI bumps the schema version,
        an older CLI reading the new file should fail loudly rather
        than silently round-tripping a partially-understood payload.
        """
        path = inflight_path()
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        future = {
            "schema_version": INFLIGHT_SCHEMA_VERSION + 1,
            "region": "us",
            "client_id": "c",
            "redirect_uri": "http://localhost:19284/callback",
            "pkce_verifier": "x" * 64,
            "state": "s" * 16,
            "created_at": int(time.time()),
            "expires_at": int(time.time()) + INFLIGHT_TTL_SECONDS,
        }
        path.write_text(json.dumps(future), encoding="utf-8")
        with pytest.raises(OAuthError) as exc:
            load_inflight()
        assert exc.value.code == "OAUTH_INFLIGHT_SCHEMA_TOO_NEW"
        assert exc.value.details is not None
        assert exc.value.details["schema_version"] == INFLIGHT_SCHEMA_VERSION + 1
        assert exc.value.details["supported"] == INFLIGHT_SCHEMA_VERSION


class TestClearInflight:
    """clear_inflight is idempotent."""

    def test_idempotent_on_missing_file(self, isolated_storage: Path) -> None:
        """No file → no-op, no exception."""
        clear_inflight()
        clear_inflight()  # second call also fine

    def test_removes_existing_file(self, isolated_storage: Path) -> None:
        """File exists → unlinked."""
        save_inflight(_make_session())
        assert inflight_path().exists()
        clear_inflight()
        assert not inflight_path().exists()


class TestPlaceholderHelpers:
    """new_placeholder_dir + read/write tokens + me cache + meta."""

    def test_new_placeholder_dir_uses_tmp_prefix(self, isolated_storage: Path) -> None:
        """Placeholder dir name starts with .tmp- (for the rollback guard)."""
        accounts_root = isolated_storage / "accounts"
        placeholder = new_placeholder_dir(accounts_root)
        assert placeholder.exists()
        assert placeholder.name.startswith(".tmp-")
        # Verify mode 0o700.
        mode = stat.S_IMODE(placeholder.stat().st_mode)
        assert mode == 0o700, f"Expected 0o700, got {oct(mode)}"

    def test_save_and_read_placeholder_meta(self, isolated_storage: Path) -> None:
        """meta.json round-trips region for --resume."""
        accounts_root = isolated_storage / "accounts"
        placeholder = new_placeholder_dir(accounts_root)
        save_placeholder_meta(placeholder, region="eu")
        meta = read_placeholder_meta(placeholder)
        assert meta is not None
        assert meta["region"] == "eu"
        assert meta["schema_version"] == PLACEHOLDER_META_SCHEMA_VERSION

    def test_read_placeholder_meta_missing_returns_none(
        self, isolated_storage: Path
    ) -> None:
        """No meta file → None (caller falls back to a default region)."""
        accounts_root = isolated_storage / "accounts"
        placeholder = new_placeholder_dir(accounts_root)
        assert read_placeholder_meta(placeholder) is None

    def test_read_placeholder_meta_corrupt_raises(self, isolated_storage: Path) -> None:
        """Malformed JSON in meta.json → OAUTH_PLACEHOLDER_META_CORRUPT.

        The previous behavior silently returned ``None``, which let
        ``--resume`` default to ``us`` for an EU/IN placeholder and then
        delete the recoverable tokens via the
        ``NeedsRegionSwitchError`` cleanup path. Now: corrupt is loud.
        """
        accounts_root = isolated_storage / "accounts"
        placeholder = new_placeholder_dir(accounts_root)
        (placeholder / "meta.json").write_text("not json", encoding="utf-8")
        with pytest.raises(OAuthError) as exc:
            read_placeholder_meta(placeholder)
        assert exc.value.code == "OAUTH_PLACEHOLDER_META_CORRUPT"

    def test_read_placeholder_meta_non_dict_raises(
        self, isolated_storage: Path
    ) -> None:
        """meta.json holding a JSON array → OAUTH_PLACEHOLDER_META_CORRUPT."""
        accounts_root = isolated_storage / "accounts"
        placeholder = new_placeholder_dir(accounts_root)
        (placeholder / "meta.json").write_text(
            json.dumps(["not", "a", "dict"]), encoding="utf-8"
        )
        with pytest.raises(OAuthError) as exc:
            read_placeholder_meta(placeholder)
        assert exc.value.code == "OAUTH_PLACEHOLDER_META_CORRUPT"

    def test_read_tokens_from_placeholder_round_trip(
        self, isolated_storage: Path
    ) -> None:
        """Tokens persisted by token_payload_bytes round-trip via the reader."""
        from datetime import datetime, timezone

        from pydantic import SecretStr

        from mixpanel_headless._internal.auth.token import (
            OAuthTokens,
            token_payload_bytes,
        )
        from mixpanel_headless._internal.io_utils import atomic_write_bytes

        accounts_root = isolated_storage / "accounts"
        placeholder = new_placeholder_dir(accounts_root)
        original = OAuthTokens(
            access_token=SecretStr("access-abc"),
            refresh_token=SecretStr("refresh-xyz"),
            expires_at=datetime(2099, 1, 1, tzinfo=timezone.utc),
            scope="read write",
            token_type="Bearer",
        )
        atomic_write_bytes(placeholder / "tokens.json", token_payload_bytes(original))
        loaded = read_tokens_from_placeholder(placeholder)
        assert loaded.access_token.get_secret_value() == "access-abc"
        assert loaded.refresh_token is not None
        assert loaded.refresh_token.get_secret_value() == "refresh-xyz"
        assert loaded.expires_at == original.expires_at
        assert loaded.scope == "read write"

    def test_read_tokens_missing_file_raises(self, isolated_storage: Path) -> None:
        """Missing tokens.json → OAUTH_TOKEN_ERROR."""
        accounts_root = isolated_storage / "accounts"
        placeholder = new_placeholder_dir(accounts_root)
        with pytest.raises(OAuthError) as exc:
            read_tokens_from_placeholder(placeholder)
        assert exc.value.code == "OAUTH_TOKEN_ERROR"

    def test_cache_me_round_trip(self, isolated_storage: Path) -> None:
        """MeResponse → me.json → MeResponse."""
        accounts_root = isolated_storage / "accounts"
        placeholder = new_placeholder_dir(accounts_root)
        me = MeResponse(
            user_id=42,
            user_email="user@example.com",
            projects={
                "100": MeProjectInfo(
                    name="Test", organization_id=1, domain="mixpanel.com"
                ),
            },
        )
        cache_me_in_placeholder(placeholder, me)
        loaded = load_cached_me_from_placeholder(placeholder)
        assert loaded is not None
        assert isinstance(loaded, MeResponse)
        assert loaded.user_id == 42
        assert "100" in loaded.projects

    def test_load_cached_me_missing_returns_none(self, isolated_storage: Path) -> None:
        """No me.json → None (caller does a fresh /me fetch)."""
        accounts_root = isolated_storage / "accounts"
        placeholder = new_placeholder_dir(accounts_root)
        assert load_cached_me_from_placeholder(placeholder) is None

    def test_load_cached_me_stale_returns_none(self, isolated_storage: Path) -> None:
        """cached_at older than INFLIGHT_TTL_SECONDS → None (treat as stale)."""
        accounts_root = isolated_storage / "accounts"
        placeholder = new_placeholder_dir(accounts_root)
        me = MeResponse(user_id=42)
        cache_me_in_placeholder(placeholder, me)
        # Rewrite the cached_at field to be older than the TTL.
        me_path = placeholder / "me.json"
        data = json.loads(me_path.read_text())
        data["cached_at"] = time.time() - INFLIGHT_TTL_SECONDS - 1
        me_path.write_text(json.dumps(data), encoding="utf-8")
        assert load_cached_me_from_placeholder(placeholder) is None


class TestFindAvailableCallbackPort:
    """find_available_callback_port returns one of the registered ports."""

    def test_returns_a_callback_port(self) -> None:
        """Happy path — returns a port in the CALLBACK_PORTS set."""
        from mixpanel_headless._internal.auth.callback_server import CALLBACK_PORTS

        port = find_available_callback_port()
        assert port in CALLBACK_PORTS
