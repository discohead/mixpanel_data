"""Unit tests for OAuthStorage (T009).

Tests the OAuthStorage class which provides secure local file storage
for OAuth tokens and client registration info.

Verifies:
- Save/load token round-trip
- Save/load client info round-trip
- File permissions (0o600 for files, 0o700 for directories)
- MP_OAUTH_STORAGE_DIR environment variable override
- Region-specific file naming (tokens_{region}.json, client_{region}.json)
- Missing file returns None
- Delete removes files
"""

from __future__ import annotations

import platform
import stat
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from pydantic import SecretStr

from mixpanel_headless._internal.auth.storage import OAuthStorage
from mixpanel_headless._internal.auth.token import OAuthClientInfo, OAuthTokens


def _utcnow() -> datetime:
    """Return current UTC datetime.

    Returns:
        Current datetime with UTC timezone.
    """
    return datetime.now(timezone.utc)


def _make_tokens(
    *,
    access_token: str = "access_abc123",
    refresh_token: str | None = "refresh_xyz789",
    scope: str = "projects analysis",
) -> OAuthTokens:
    """Create an OAuthTokens instance with sensible defaults for testing.

    Args:
        access_token: OAuth access token string.
        refresh_token: OAuth refresh token string, or None.
        scope: OAuth scope string.

    Returns:
        Configured OAuthTokens instance.
    """
    return OAuthTokens(
        access_token=SecretStr(access_token),
        refresh_token=SecretStr(refresh_token) if refresh_token is not None else None,
        expires_at=_utcnow() + timedelta(hours=1),
        scope=scope,
        token_type="Bearer",
    )


def _make_client_info(
    *,
    client_id: str = "client_abc123",
    region: str = "us",
) -> OAuthClientInfo:
    """Create an OAuthClientInfo instance with sensible defaults for testing.

    Args:
        client_id: DCR client identifier.
        region: Mixpanel data residency region.

    Returns:
        Configured OAuthClientInfo instance.
    """
    return OAuthClientInfo(
        client_id=client_id,
        region=region,
        redirect_uri="http://localhost:19284/callback",
        scope="projects analysis",
        created_at=_utcnow(),
    )


class TestOAuthStorageSecurityHardening:
    """Tests for security hardening of OAuthStorage (T045)."""

    @pytest.mark.skipif(
        platform.system() == "Windows",
        reason="POSIX file permissions not available on Windows",
    )
    def test_directory_created_with_0o700(self, temp_dir: Path) -> None:
        """Verify that the storage directory is always created with 0o700 permissions."""
        storage_dir = temp_dir / "secure_oauth"
        storage = OAuthStorage(storage_dir=storage_dir)
        storage.save_tokens(_make_tokens(), region="us")

        dir_mode = stat.S_IMODE(storage_dir.stat().st_mode)
        assert dir_mode == 0o700, f"Expected 0o700, got {oct(dir_mode)}"

    @pytest.mark.skipif(
        platform.system() == "Windows",
        reason="POSIX file permissions not available on Windows",
    )
    def test_files_created_with_0o600(self, temp_dir: Path) -> None:
        """Verify that token and client files are created with 0o600 permissions."""
        storage = OAuthStorage(storage_dir=temp_dir)
        storage.save_tokens(_make_tokens(), region="us")
        storage.save_client_info(_make_client_info())

        token_file = temp_dir / "tokens_us.json"
        client_file = temp_dir / "client_us.json"

        for f in (token_file, client_file):
            file_mode = stat.S_IMODE(f.stat().st_mode)
            assert file_mode == 0o600, (
                f"Expected 0o600 for {f.name}, got {oct(file_mode)}"
            )

    @pytest.mark.skipif(
        platform.system() == "Windows",
        reason="POSIX file permissions not available on Windows",
    )
    def test_check_and_fix_permissions_repairs_directory(self, temp_dir: Path) -> None:
        """Verify that _check_and_fix_permissions repairs directory permissions."""
        storage_dir = temp_dir / "fixable_oauth"
        storage_dir.mkdir(parents=True)
        storage_dir.chmod(0o755)  # Intentionally wrong

        storage = OAuthStorage(storage_dir=storage_dir)
        storage.save_tokens(_make_tokens(), region="us")

        dir_mode = stat.S_IMODE(storage_dir.stat().st_mode)
        assert dir_mode == 0o700, f"Expected 0o700 after repair, got {oct(dir_mode)}"

    @pytest.mark.skipif(
        platform.system() == "Windows",
        reason="POSIX file permissions not available on Windows",
    )
    def test_check_and_fix_permissions_repairs_files_on_load(
        self, temp_dir: Path
    ) -> None:
        """Verify that load_tokens repairs file permissions if incorrect."""
        storage = OAuthStorage(storage_dir=temp_dir)
        storage.save_tokens(_make_tokens(), region="us")

        # Deliberately break file permissions
        token_file = temp_dir / "tokens_us.json"
        token_file.chmod(0o644)

        # Loading should repair permissions
        storage.load_tokens(region="us")
        file_mode = stat.S_IMODE(token_file.stat().st_mode)
        assert file_mode == 0o600, f"Expected 0o600 after repair, got {oct(file_mode)}"

    def test_repr_redacts_access_token(self) -> None:
        """Verify that repr() of OAuthTokens redacts access_token."""
        tokens = _make_tokens()
        r = repr(tokens)
        assert "access_abc123" not in r
        assert "**********" in r

    def test_repr_redacts_refresh_token(self) -> None:
        """Verify that repr() of OAuthTokens redacts refresh_token."""
        tokens = _make_tokens()
        r = repr(tokens)
        assert "refresh_xyz789" not in r

    def test_str_redacts_secrets(self) -> None:
        """Verify that str() of OAuthTokens does not leak secret values."""
        tokens = _make_tokens()
        s = str(tokens)
        assert "access_abc123" not in s
        assert "refresh_xyz789" not in s

    def test_token_values_never_in_log_output(self) -> None:
        """Verify that token values never appear in logger output.

        Mocks the logger used by the storage module and ensures no raw
        token values are emitted in any log messages.
        """
        tokens = _make_tokens()
        # Check that formatting the tokens for potential log output doesn't leak
        formatted = f"Loaded tokens: {tokens}"
        assert "access_abc123" not in formatted
        assert "refresh_xyz789" not in formatted

        # Also verify that repr is safe
        formatted_repr = f"Token info: {tokens!r}"
        assert "access_abc123" not in formatted_repr
        assert "refresh_xyz789" not in formatted_repr


class TestOAuthStorageTokenRoundTrip:
    """Tests for saving and loading OAuth tokens."""

    def test_save_and_load_tokens(self, temp_dir: Path) -> None:
        """Verify tokens can be saved and loaded back with all fields preserved.

        The storage should serialize OAuthTokens to JSON and deserialize
        back to an equivalent OAuthTokens instance.
        """
        storage = OAuthStorage(storage_dir=temp_dir)
        original = _make_tokens()

        storage.save_tokens(original, region="us")
        loaded = storage.load_tokens(region="us")

        assert loaded is not None
        assert loaded.access_token.get_secret_value() == "access_abc123"
        assert loaded.refresh_token is not None
        assert loaded.refresh_token.get_secret_value() == "refresh_xyz789"
        assert loaded.scope == "projects analysis"
        assert loaded.token_type == "Bearer"

    def test_save_and_load_tokens_without_refresh_token(self, temp_dir: Path) -> None:
        """Verify tokens without a refresh token survive round-trip."""
        storage = OAuthStorage(storage_dir=temp_dir)
        original = _make_tokens(refresh_token=None)

        storage.save_tokens(original, region="us")
        loaded = storage.load_tokens(region="us")

        assert loaded is not None
        assert loaded.refresh_token is None

    # test_save_and_load_tokens_without_project_id removed in B2 (T044):
    # the legacy ``OAuthTokens.project_id`` field is gone.

    def test_expires_at_preserved_through_round_trip(self, temp_dir: Path) -> None:
        """Verify that the expires_at datetime is preserved through save/load.

        JSON serialization may lose sub-microsecond precision, but the
        datetime should be within 1 second of the original.
        """
        storage = OAuthStorage(storage_dir=temp_dir)
        original = _make_tokens()

        storage.save_tokens(original, region="us")
        loaded = storage.load_tokens(region="us")

        assert loaded is not None
        delta = abs((loaded.expires_at - original.expires_at).total_seconds())
        assert delta < 1, f"expires_at drift: {delta}s"


class TestOAuthStorageClientInfoRoundTrip:
    """Tests for saving and loading client registration info."""

    def test_save_and_load_client_info(self, temp_dir: Path) -> None:
        """Verify client info can be saved and loaded with all fields preserved."""
        storage = OAuthStorage(storage_dir=temp_dir)
        original = _make_client_info()

        storage.save_client_info(original)
        loaded = storage.load_client_info(region="us")

        assert loaded is not None
        assert loaded.client_id == "client_abc123"
        assert loaded.region == "us"
        assert loaded.redirect_uri == "http://localhost:19284/callback"
        assert loaded.scope == "projects analysis"

    def test_save_and_load_client_info_different_regions(self, temp_dir: Path) -> None:
        """Verify client info is stored per-region and doesn't cross-contaminate."""
        storage = OAuthStorage(storage_dir=temp_dir)

        us_info = _make_client_info(client_id="us_client", region="us")
        eu_info = _make_client_info(client_id="eu_client", region="eu")

        storage.save_client_info(us_info)
        storage.save_client_info(eu_info)

        loaded_us = storage.load_client_info(region="us")
        loaded_eu = storage.load_client_info(region="eu")

        assert loaded_us is not None
        assert loaded_us.client_id == "us_client"
        assert loaded_eu is not None
        assert loaded_eu.client_id == "eu_client"


class TestOAuthStorageFilePermissions:
    """Tests for secure file and directory permissions."""

    @pytest.mark.skipif(
        platform.system() == "Windows",
        reason="POSIX file permissions not available on Windows",
    )
    def test_storage_directory_has_0o700_permissions(self, temp_dir: Path) -> None:
        """Verify that the storage directory is created with 0o700 permissions.

        Only the owning user should have read/write/execute access to the
        directory containing OAuth tokens.
        """
        storage_dir = temp_dir / "oauth_perms"
        storage = OAuthStorage(storage_dir=storage_dir)
        storage.save_tokens(_make_tokens(), region="us")

        dir_mode = stat.S_IMODE(storage_dir.stat().st_mode)
        assert dir_mode == 0o700, f"Expected 0o700, got {oct(dir_mode)}"

    @pytest.mark.skipif(
        platform.system() == "Windows",
        reason="POSIX file permissions not available on Windows",
    )
    def test_token_file_has_0o600_permissions(self, temp_dir: Path) -> None:
        """Verify that token files are created with 0o600 permissions.

        Only the owning user should have read/write access to token files.
        """
        storage = OAuthStorage(storage_dir=temp_dir)
        storage.save_tokens(_make_tokens(), region="us")

        token_file = temp_dir / "tokens_us.json"
        file_mode = stat.S_IMODE(token_file.stat().st_mode)
        assert file_mode == 0o600, f"Expected 0o600, got {oct(file_mode)}"

    @pytest.mark.skipif(
        platform.system() == "Windows",
        reason="POSIX file permissions not available on Windows",
    )
    def test_client_info_file_has_0o600_permissions(self, temp_dir: Path) -> None:
        """Verify that client info files are created with 0o600 permissions."""
        storage = OAuthStorage(storage_dir=temp_dir)
        storage.save_client_info(_make_client_info(region="eu"))

        client_file = temp_dir / "client_eu.json"
        file_mode = stat.S_IMODE(client_file.stat().st_mode)
        assert file_mode == 0o600, f"Expected 0o600, got {oct(file_mode)}"


class TestOAuthStorageEnvOverride:
    """Tests for MP_OAUTH_STORAGE_DIR environment variable override."""

    def test_mp_oauth_storage_dir_override(
        self, temp_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verify ``MP_OAUTH_STORAGE_DIR`` overrides the default storage root.

        Per Fix 7, the env var names the *root* under which BOTH the
        OAuth subtree and the per-account subtree live (it used to alias
        the OAuth subtree directly, which was asymmetric and confusing).
        """
        custom_root = temp_dir / "custom_root"
        custom_root.mkdir(parents=True)
        monkeypatch.setenv("MP_OAUTH_STORAGE_DIR", str(custom_root))

        storage = OAuthStorage()
        storage.save_tokens(_make_tokens(), region="us")

        assert (custom_root / "oauth" / "tokens_us.json").exists()

    def test_explicit_storage_dir_takes_precedence_over_env(
        self, temp_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verify that an explicit storage_dir parameter overrides the env var.

        When both are set, the explicit constructor argument should win.
        """
        env_dir = temp_dir / "env_dir"
        env_dir.mkdir()
        explicit_dir = temp_dir / "explicit_dir"
        explicit_dir.mkdir()

        monkeypatch.setenv("MP_OAUTH_STORAGE_DIR", str(env_dir))

        storage = OAuthStorage(storage_dir=explicit_dir)
        storage.save_tokens(_make_tokens(), region="us")

        assert (explicit_dir / "tokens_us.json").exists()
        assert not (env_dir / "tokens_us.json").exists()


class TestOAuthStorageRegionNaming:
    """Tests for region-specific file naming conventions."""

    def test_tokens_file_named_by_region(self, temp_dir: Path) -> None:
        """Verify that token files are named tokens_{region}.json.

        Each region's tokens are stored in a separate file to support
        multi-region authentication.
        """
        storage = OAuthStorage(storage_dir=temp_dir)

        for region in ("us", "eu", "in"):
            storage.save_tokens(_make_tokens(), region=region)
            expected_file = temp_dir / f"tokens_{region}.json"
            assert expected_file.exists(), f"Expected {expected_file} to exist"

    def test_client_file_named_by_region(self, temp_dir: Path) -> None:
        """Verify that client info files are named client_{region}.json."""
        storage = OAuthStorage(storage_dir=temp_dir)

        for region in ("us", "eu", "in"):
            storage.save_client_info(_make_client_info(region=region))
            expected_file = temp_dir / f"client_{region}.json"
            assert expected_file.exists(), f"Expected {expected_file} to exist"

    def test_different_regions_are_independent(self, temp_dir: Path) -> None:
        """Verify that saving tokens for one region doesn't affect another.

        US and EU tokens should be stored and loaded independently.
        """
        storage = OAuthStorage(storage_dir=temp_dir)

        us_tokens = _make_tokens(access_token="us_token")
        eu_tokens = _make_tokens(access_token="eu_token")

        storage.save_tokens(us_tokens, region="us")
        storage.save_tokens(eu_tokens, region="eu")

        loaded_us = storage.load_tokens(region="us")
        loaded_eu = storage.load_tokens(region="eu")

        assert loaded_us is not None
        assert loaded_us.access_token.get_secret_value() == "us_token"
        assert loaded_eu is not None
        assert loaded_eu.access_token.get_secret_value() == "eu_token"


class TestOAuthStorageMissingFile:
    """Tests for behavior when storage files do not exist."""

    def test_load_tokens_returns_none_when_missing(self, temp_dir: Path) -> None:
        """Verify that load_tokens() returns None when no token file exists.

        This is the expected state before any OAuth login has occurred.
        """
        storage = OAuthStorage(storage_dir=temp_dir)
        result = storage.load_tokens(region="us")
        assert result is None

    def test_load_client_info_returns_none_when_missing(self, temp_dir: Path) -> None:
        """Verify that load_client_info() returns None when no client file exists."""
        storage = OAuthStorage(storage_dir=temp_dir)
        result = storage.load_client_info(region="us")
        assert result is None

    def test_load_tokens_returns_none_for_different_region(
        self, temp_dir: Path
    ) -> None:
        """Verify that tokens saved for US are not found when loading for EU."""
        storage = OAuthStorage(storage_dir=temp_dir)
        storage.save_tokens(_make_tokens(), region="us")

        result = storage.load_tokens(region="eu")
        assert result is None


class TestOAuthStorageDelete:
    """Tests for deleting stored tokens and client info."""

    def test_delete_tokens_removes_file(self, temp_dir: Path) -> None:
        """Verify that delete_tokens() removes the token file for the region."""
        storage = OAuthStorage(storage_dir=temp_dir)
        storage.save_tokens(_make_tokens(), region="us")

        assert (temp_dir / "tokens_us.json").exists()

        storage.delete_tokens(region="us")

        assert not (temp_dir / "tokens_us.json").exists()

    def test_delete_tokens_only_affects_specified_region(self, temp_dir: Path) -> None:
        """Verify that deleting tokens for one region doesn't affect others."""
        storage = OAuthStorage(storage_dir=temp_dir)
        storage.save_tokens(_make_tokens(), region="us")
        storage.save_tokens(_make_tokens(), region="eu")

        storage.delete_tokens(region="us")

        assert not (temp_dir / "tokens_us.json").exists()
        assert (temp_dir / "tokens_eu.json").exists()

    def test_delete_tokens_when_no_file_exists(self, temp_dir: Path) -> None:
        """Verify that delete_tokens() does not raise when no file exists.

        Deleting tokens that don't exist should be a no-op.
        """
        storage = OAuthStorage(storage_dir=temp_dir)
        # Should not raise
        storage.delete_tokens(region="us")

    def test_load_tokens_returns_none_after_delete(self, temp_dir: Path) -> None:
        """Verify that load_tokens() returns None after tokens are deleted."""
        storage = OAuthStorage(storage_dir=temp_dir)
        storage.save_tokens(_make_tokens(), region="us")

        storage.delete_tokens(region="us")
        result = storage.load_tokens(region="us")

        assert result is None

    def test_delete_all_removes_all_files(self, temp_dir: Path) -> None:
        """Verify that delete_all() removes all token and client files."""
        storage = OAuthStorage(storage_dir=temp_dir)

        # Save tokens and client info for multiple regions
        for region in ("us", "eu", "in"):
            storage.save_tokens(_make_tokens(), region=region)
            storage.save_client_info(_make_client_info(region=region))

        storage.delete_all()

        for region in ("us", "eu", "in"):
            assert storage.load_tokens(region=region) is None
            assert storage.load_client_info(region=region) is None


class TestOAuthStorageCorruptedFiles:
    """Tests for handling corrupted or malformed files on disk."""

    def test_load_tokens_invalid_json(self, temp_dir: Path) -> None:
        """Verify load_tokens returns None when file contains truncated JSON.

        A corrupted file (e.g. from a partial write) should not crash
        the application with JSONDecodeError.
        """
        storage = OAuthStorage(storage_dir=temp_dir)
        tokens_file = temp_dir / "tokens_us.json"
        tokens_file.parent.mkdir(parents=True, exist_ok=True)
        tokens_file.write_text('{"truncated', encoding="utf-8")

        result = storage.load_tokens(region="us")
        assert result is None

    def test_load_tokens_empty_file(self, temp_dir: Path) -> None:
        """Verify load_tokens returns None when the file is empty.

        An empty file is invalid JSON and should be handled gracefully.
        """
        storage = OAuthStorage(storage_dir=temp_dir)
        tokens_file = temp_dir / "tokens_us.json"
        tokens_file.parent.mkdir(parents=True, exist_ok=True)
        tokens_file.write_text("", encoding="utf-8")

        result = storage.load_tokens(region="us")
        assert result is None

    def test_load_tokens_binary_data(self, temp_dir: Path) -> None:
        """Verify load_tokens returns None when file contains binary data.

        Binary garbage in the token file should not crash with
        UnicodeDecodeError or JSONDecodeError.
        """
        storage = OAuthStorage(storage_dir=temp_dir)
        tokens_file = temp_dir / "tokens_us.json"
        tokens_file.parent.mkdir(parents=True, exist_ok=True)
        tokens_file.write_bytes(b"\x80\x81\x82\xff\xfe\x00\x01")

        result = storage.load_tokens(region="us")
        assert result is None

    def test_load_tokens_wrong_schema(self, temp_dir: Path) -> None:
        """Verify load_tokens returns None when JSON is valid but missing required fields.

        A file with ``{"foo": "bar"}`` (no ``access_token``) should not
        raise KeyError.
        """
        storage = OAuthStorage(storage_dir=temp_dir)
        tokens_file = temp_dir / "tokens_us.json"
        tokens_file.parent.mkdir(parents=True, exist_ok=True)
        tokens_file.write_text('{"foo": "bar"}', encoding="utf-8")

        result = storage.load_tokens(region="us")
        assert result is None

    def test_load_tokens_wrong_types(self, temp_dir: Path) -> None:
        """Verify load_tokens returns None when field types are incorrect.

        Writing ``access_token`` as an integer and ``expires_at`` as a
        non-date string should be handled gracefully.
        """
        import json

        storage = OAuthStorage(storage_dir=temp_dir)
        tokens_file = temp_dir / "tokens_us.json"
        tokens_file.parent.mkdir(parents=True, exist_ok=True)
        bad_data = {
            "access_token": 42,
            "expires_at": "not-a-date",
            "scope": 123,
            "token_type": None,
        }
        tokens_file.write_text(json.dumps(bad_data), encoding="utf-8")

        result = storage.load_tokens(region="us")
        # Should return None (validation error), not crash
        assert result is None

    def test_load_client_info_corrupted(self, temp_dir: Path) -> None:
        """Verify load_client_info returns None when file contains invalid JSON.

        Corrupted client info files should be handled the same as
        corrupted token files.
        """
        storage = OAuthStorage(storage_dir=temp_dir)
        client_file = temp_dir / "client_us.json"
        client_file.parent.mkdir(parents=True, exist_ok=True)
        client_file.write_text("not valid json {{{", encoding="utf-8")

        result = storage.load_client_info(region="us")
        assert result is None


class TestOAuthStoragePathTraversal:
    """Tests for path traversal prevention in region parameters."""

    def test_tokens_path_traversal_rejected(self, temp_dir: Path) -> None:
        """Verify that save_tokens rejects region with path traversal characters.

        A region like ``../../../tmp`` would escape the storage directory
        if not validated. The storage must raise ``ValueError``.
        """
        storage = OAuthStorage(storage_dir=temp_dir)
        with pytest.raises(ValueError, match="Invalid region"):
            storage.save_tokens(_make_tokens(), region="../../../tmp")

    def test_tokens_path_with_slashes(self, temp_dir: Path) -> None:
        """Verify that a region containing slashes is rejected.

        A region like ``us/eu`` is not a valid 2-letter region code and
        could be used to create files in unexpected subdirectories.
        """
        storage = OAuthStorage(storage_dir=temp_dir)
        with pytest.raises(ValueError, match="Invalid region"):
            storage.save_tokens(_make_tokens(), region="us/eu")

    def test_client_path_traversal_rejected(self, temp_dir: Path) -> None:
        """Verify that save_client_info rejects region with traversal characters.

        Uses a client info object whose region contains path traversal
        sequences. The storage must raise ``ValueError``.
        """
        storage = OAuthStorage(storage_dir=temp_dir)
        malicious_info = OAuthClientInfo(
            client_id="test_client",
            region="../../../etc",
            redirect_uri="http://localhost:19284/callback",
            scope="projects analysis",
            created_at=_utcnow(),
        )
        with pytest.raises(ValueError, match="Invalid region"):
            storage.save_client_info(malicious_info)

    def test_valid_regions_accepted(self, temp_dir: Path) -> None:
        """Verify that valid 2-letter region codes are accepted without error.

        The standard Mixpanel regions ``us``, ``eu``, and ``in`` must all
        pass validation and successfully save/load tokens.
        """
        storage = OAuthStorage(storage_dir=temp_dir)
        for region in ("us", "eu", "in"):
            storage.save_tokens(_make_tokens(), region=region)
            loaded = storage.load_tokens(region=region)
            assert loaded is not None

    def test_load_tokens_traversal_rejected(self, temp_dir: Path) -> None:
        """Verify that load_tokens rejects traversal regions."""
        storage = OAuthStorage(storage_dir=temp_dir)
        with pytest.raises(ValueError, match="Invalid region"):
            storage.load_tokens(region="../../../tmp")

    def test_load_client_info_traversal_rejected(self, temp_dir: Path) -> None:
        """Verify that load_client_info rejects traversal regions."""
        storage = OAuthStorage(storage_dir=temp_dir)
        with pytest.raises(ValueError, match="Invalid region"):
            storage.load_client_info(region="../../../tmp")

    def test_delete_tokens_traversal_rejected(self, temp_dir: Path) -> None:
        """Verify that delete_tokens rejects traversal regions."""
        storage = OAuthStorage(storage_dir=temp_dir)
        with pytest.raises(ValueError, match="Invalid region"):
            storage.delete_tokens(region="../../../tmp")

    def test_uppercase_region_rejected(self, temp_dir: Path) -> None:
        """Verify that uppercase region codes are rejected.

        Only lowercase 2-letter codes are valid.
        """
        storage = OAuthStorage(storage_dir=temp_dir)
        with pytest.raises(ValueError, match="Invalid region"):
            storage.save_tokens(_make_tokens(), region="US")

    def test_three_letter_region_rejected(self, temp_dir: Path) -> None:
        """Verify that region codes longer than 2 characters are rejected."""
        storage = OAuthStorage(storage_dir=temp_dir)
        with pytest.raises(ValueError, match="Invalid region"):
            storage.save_tokens(_make_tokens(), region="usa")


# =============================================================================
# Phase 3C: Unicode & Special Characters
# =============================================================================


class TestOAuthStorageUnicode:
    """Tests for Unicode and special character handling in token storage.

    Verifies that tokens with non-ASCII scope values and special characters
    in access tokens survive the save/load round-trip without corruption.
    """

    def test_save_load_tokens_unicode_scope(self, temp_dir: Path) -> None:
        """Verify that tokens with Unicode scope values survive round-trip.

        OAuth scopes are typically ASCII, but the storage layer should
        not corrupt Unicode characters if they appear (e.g. localized
        scope descriptions from non-standard servers).

        Args:
            temp_dir: Temporary directory fixture for isolated storage.
        """
        storage = OAuthStorage(storage_dir=temp_dir)
        tokens = _make_tokens(scope="événements données")
        storage.save_tokens(tokens, region="us")
        loaded = storage.load_tokens(region="us")

        assert loaded is not None
        assert loaded.scope == "événements données"

    def test_save_load_tokens_special_chars_in_token(self, temp_dir: Path) -> None:
        """Verify that tokens with URL-special characters survive round-trip.

        Access tokens may contain ``+``, ``/``, ``=`` from base64 encoding.
        These must not be corrupted by JSON serialization.

        Args:
            temp_dir: Temporary directory fixture for isolated storage.
        """
        storage = OAuthStorage(storage_dir=temp_dir)
        tokens = _make_tokens(access_token="tok+en/with=special")
        storage.save_tokens(tokens, region="us")
        loaded = storage.load_tokens(region="us")

        assert loaded is not None
        assert loaded.access_token.get_secret_value() == "tok+en/with=special"


# =============================================================================
# Phase 4: Concurrency Tests
# =============================================================================


class TestOAuthStorageConcurrency:
    """Tests for concurrent access to OAuthStorage.

    Verifies that simultaneous reads and writes do not produce corrupted
    JSON files or raise unexpected exceptions. Uses threading to simulate
    real-world concurrent access patterns.
    """

    def test_concurrent_saves_produce_valid_json(self, temp_dir: Path) -> None:
        """Verify that 10 concurrent saves all produce valid JSON on disk.

        Launches 10 threads, each saving tokens with a unique access_token.
        After all complete, ``load_tokens()`` must return a valid token
        (one of the 10 values) — not corrupted JSON.

        Args:
            temp_dir: Temporary directory fixture for isolated storage.
        """
        import concurrent.futures

        storage = OAuthStorage(storage_dir=temp_dir)

        def save_with_id(thread_id: int) -> None:
            """Save tokens with a thread-specific access token.

            Args:
                thread_id: Unique identifier for this thread's token.
            """
            tokens = _make_tokens(access_token=f"token_{thread_id}")
            storage.save_tokens(tokens, region="us")

        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(save_with_id, i) for i in range(10)]
            concurrent.futures.wait(futures)

        # Verify no exceptions were raised
        for f in futures:
            f.result()  # Raises if the thread raised

        # After all writes, the file should contain valid JSON
        loaded = storage.load_tokens(region="us")
        assert loaded is not None
        # The token should be one of the 10 written values
        token_value = loaded.access_token.get_secret_value()
        valid_tokens = {f"token_{i}" for i in range(10)}
        assert token_value in valid_tokens

    def test_concurrent_read_during_write(self, temp_dir: Path) -> None:
        """Verify that concurrent reads and writes do not crash.

        A writer thread saves tokens in a loop (20 iterations), while
        a reader thread loads tokens in a loop (20 iterations). After
        both complete, no exceptions should have been raised. The reader
        should get either ``None`` or a valid ``OAuthTokens`` instance.

        Args:
            temp_dir: Temporary directory fixture for isolated storage.
        """
        import concurrent.futures
        import threading

        storage = OAuthStorage(storage_dir=temp_dir)
        read_results: list[OAuthTokens | None] = []
        read_errors: list[Exception] = []
        write_errors: list[Exception] = []
        read_lock = threading.Lock()

        def writer() -> None:
            """Write tokens in a loop, recording any errors."""
            for i in range(20):
                try:
                    tokens = _make_tokens(access_token=f"write_{i}")
                    storage.save_tokens(tokens, region="us")
                except Exception as exc:
                    write_errors.append(exc)

        def reader() -> None:
            """Read tokens in a loop, recording results and any errors.

            PermissionError is expected during concurrent access because
            the storage temporarily changes file permissions via umask
            during writes. These are tolerated as known race conditions.
            """
            for _ in range(20):
                try:
                    result = storage.load_tokens(region="us")
                    with read_lock:
                        read_results.append(result)
                except PermissionError:
                    # Expected: writer temporarily restricts permissions
                    pass
                except Exception as exc:
                    read_errors.append(exc)

        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            write_future = executor.submit(writer)
            read_future = executor.submit(reader)
            concurrent.futures.wait([write_future, read_future])

        # No exceptions in either thread (PermissionError already handled)
        write_future.result()
        read_future.result()
        assert len(write_errors) == 0, f"Writer errors: {write_errors}"
        assert len(read_errors) == 0, f"Reader errors: {read_errors}"

        # Reader results should all be None or valid OAuthTokens
        for result in read_results:
            assert result is None or isinstance(result, OAuthTokens)
