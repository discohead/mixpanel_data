"""Secure local storage for OAuth tokens and client registration info.

Persists OAuth tokens and client metadata as JSON files in a
permission-restricted directory (``~/.mp/oauth/`` by default).
Directory permissions are set to ``0o700`` and file permissions to ``0o600``
to protect sensitive credential material.

The storage directory can be overridden via the ``MP_OAUTH_STORAGE_DIR``
environment variable for testing or custom deployments.

Per-account paths (introduced by 042-auth-architecture-redesign):
- ``account_dir(name)`` and ``ensure_account_dir(name)`` return / create
  ``~/.mp/accounts/{name}/`` with mode ``0o700``. Token / client / me
  files for the new model live here.

Example:
    ```python
    from mixpanel_headless._internal.auth.storage import OAuthStorage
    from mixpanel_headless._internal.auth.token import OAuthTokens

    storage = OAuthStorage()
    storage.save_tokens(tokens, region="us")
    loaded = storage.load_tokens(region="us")
    ```
"""

from __future__ import annotations

import json
import logging
import os
import re
import stat
from pathlib import Path
from typing import Any

from pydantic import SecretStr

from mixpanel_headless._internal.auth.token import OAuthClientInfo, OAuthTokens
from mixpanel_headless._internal.io_utils import atomic_write_bytes

logger = logging.getLogger(__name__)


_ACCOUNT_NAME_PATTERN = re.compile(r"^[a-zA-Z0-9_-]{1,64}$")


def _storage_root() -> Path:
    """Return the root directory under which mixpanel_headless writes account state.

    Resolved at every call so test isolation via ``$HOME`` /
    ``MP_OAUTH_STORAGE_DIR`` monkeypatching takes effect — a module-level
    constant captured at import time would silently leak the developer's
    real ``~/.mp/`` into hermetic tests.

    Despite the name, ``MP_OAUTH_STORAGE_DIR`` controls EVERY on-disk
    artifact written by mixpanel_headless (per-account dirs, OAuth tokens,
    ``/me`` cache, client registration), not just the OAuth subtree. The
    name is preserved as a backwards-compat env var only — the root is
    used by both :func:`account_dir` and
    :meth:`OAuthStorage._default_storage_dir`.

    Returns:
        ``$MP_OAUTH_STORAGE_DIR`` if set, else ``$HOME/.mp``.
    """
    env_dir = os.environ.get("MP_OAUTH_STORAGE_DIR")
    if env_dir:
        return Path(env_dir)
    return Path.home() / ".mp"


def accounts_root() -> Path:
    """Return the directory holding every per-account state directory.

    Resolves to ``$MP_OAUTH_STORAGE_DIR/accounts/`` when the env var is
    set, else ``~/.mp/accounts/``. Used by callers that need to operate
    on the parent of :func:`account_dir` (placeholder dirs, enumeration)
    while still honoring the storage-root override.

    Returns:
        Absolute path to the accounts root. Not created by this call.
    """
    return _storage_root() / "accounts"


def account_dir(name: str) -> Path:
    """Return the per-account directory for ``name``.

    Resolves to ``$MP_OAUTH_STORAGE_DIR/accounts/{name}/`` when the env
    var is set, else ``~/.mp/accounts/{name}/``. Does not create the
    directory — use :func:`ensure_account_dir` for that.

    Args:
        name: Account name (must match the same pattern enforced on the
            ``Account`` model — ``^[a-zA-Z0-9_-]{1,64}$``). Validated here
            as a defense-in-depth check against path traversal.

    Returns:
        Absolute path to the per-account directory.

    Raises:
        ValueError: If ``name`` does not match the allowed pattern.
    """
    if not _ACCOUNT_NAME_PATTERN.fullmatch(name):
        raise ValueError(
            f"Invalid account name: {name!r}. Must match `^[a-zA-Z0-9_-]{{1,64}}$`."
        )
    return accounts_root() / name


def ensure_account_dir(name: str) -> Path:
    """Create ``~/.mp/accounts/{name}/`` (and its parents) with mode ``0o700``.

    Idempotent — succeeds even if the directory already exists. The parent
    ``~/.mp/`` directory is also created with restrictive permissions if
    missing. Symlinks are not followed when applying permissions.

    Args:
        name: Account name (validated by :func:`account_dir`).

    Returns:
        The created (or pre-existing) account directory path.

    Raises:
        ValueError: If ``name`` does not match the allowed pattern.
    """
    path = account_dir(name)
    old_umask = os.umask(0o077)
    try:
        path.mkdir(parents=True, exist_ok=True)
    finally:
        os.umask(old_umask)
    # Defensive chmod so a pre-existing dir with looser permissions gets locked down.
    path.chmod(stat.S_IRWXU)
    return path


class OAuthStorage:
    """Secure file-based storage for OAuth tokens and client info.

    Stores tokens and client registration data as JSON files under
    a permission-restricted directory. Each region gets its own pair
    of files (``tokens_{region}.json`` and ``client_{region}.json``).

    The storage directory defaults to ``~/.mp/oauth/`` but can be
    overridden via the ``MP_OAUTH_STORAGE_DIR`` environment variable
    or the ``storage_dir`` constructor parameter.

    Security:
        - Directory permissions: ``0o700`` (owner-only access)
        - File permissions: ``0o600`` (owner-only read/write)

    Attributes:
        storage_dir: Path to the storage directory.
    """

    @classmethod
    def _default_storage_dir(cls) -> Path:
        """Return the default OAuth storage path, resolved lazily.

        Routes through :func:`_storage_root` so the ``MP_OAUTH_STORAGE_DIR``
        env var (and ``$HOME`` for tests) takes effect at call time, not
        import time.

        Returns:
            ``<storage-root>/oauth`` resolved at call time.
        """
        return _storage_root() / "oauth"

    def __init__(self, storage_dir: Path | None = None) -> None:
        """Initialize OAuthStorage.

        Args:
            storage_dir: Override the storage directory. When not provided,
                falls back to :meth:`_default_storage_dir` which honors
                ``MP_OAUTH_STORAGE_DIR``.

        Example:
            ```python
            storage = OAuthStorage()  # uses default
            storage = OAuthStorage(Path("/tmp/test-oauth"))  # custom dir
            ```
        """
        if storage_dir is not None:
            self._storage_dir = storage_dir
        else:
            self._storage_dir = self._default_storage_dir()

    @property
    def storage_dir(self) -> Path:
        """Return the storage directory path.

        Returns:
            The resolved storage directory path.
        """
        return self._storage_dir

    @staticmethod
    def _validate_region(region: str) -> None:
        """Validate that the region string is safe for use in file paths.

        Prevents path traversal attacks by ensuring the region is exactly
        a 2-letter lowercase ASCII string (e.g., ``us``, ``eu``, ``in``).

        Args:
            region: The region string to validate.

        Raises:
            ValueError: If the region is not a 2-letter lowercase string.

        Example:
            ```python
            OAuthStorage._validate_region("us")   # OK
            OAuthStorage._validate_region("../x")  # raises ValueError
            ```
        """
        if not re.fullmatch(r"[a-z]{2}", region):
            raise ValueError(
                f"Invalid region: {region!r}. Must be a 2-letter lowercase string."
            )

    def _ensure_dir(self) -> None:
        """Create storage directory with restricted permissions if it doesn't exist.

        Sets directory permissions to ``0o700`` (owner-only access).
        """
        old_umask = os.umask(0o077)
        try:
            self._storage_dir.mkdir(parents=True, exist_ok=True)
        finally:
            os.umask(old_umask)
        self._storage_dir.chmod(stat.S_IRWXU)

    def _check_and_fix_permissions(self, path: Path) -> None:
        """Check and repair file/directory permissions.

        Verifies that the storage directory has ``0o700`` permissions and
        the specified file has ``0o600`` permissions. Attempts to repair
        incorrect permissions via ``os.chmod()``. Logs a warning to stderr
        if repair fails.

        Args:
            path: File path whose permissions (and parent directory) to check.
        """
        # Check directory permissions
        if self._storage_dir.exists():
            dir_mode = stat.S_IMODE(self._storage_dir.stat().st_mode)
            if dir_mode != 0o700:
                try:
                    self._storage_dir.chmod(stat.S_IRWXU)
                except OSError:
                    logger.warning(
                        "Cannot repair directory permissions on %s. "
                        "Expected 0o700, got %s. "
                        "Run: chmod 700 %s",
                        self._storage_dir,
                        oct(dir_mode),
                        self._storage_dir,
                    )

        # Check file permissions
        if path.exists():
            file_mode = stat.S_IMODE(path.stat().st_mode)
            if file_mode != 0o600:
                try:
                    path.chmod(stat.S_IRUSR | stat.S_IWUSR)
                except OSError:
                    logger.warning(
                        "Cannot repair file permissions on %s. "
                        "Expected 0o600, got %s. "
                        "Run: chmod 600 %s",
                        path,
                        oct(file_mode),
                        path,
                    )

    def _write_file(self, path: Path, data: dict[str, Any]) -> None:
        """Atomically write JSON data to ``path`` with mode ``0o600``.

        The replace step is atomic on POSIX (same filesystem), so a
        SIGKILL between tmp-create and rename leaves the prior file in
        place rather than a partially-written one.

        Args:
            path: File path to write to.
            data: Dictionary to serialize as JSON.
        """
        self._ensure_dir()
        atomic_write_bytes(
            path, json.dumps(data, indent=2, default=str).encode("utf-8")
        )

    def _read_file(self, path: Path) -> dict[str, Any] | None:
        """Read JSON data from a file.

        Checks and repairs file/directory permissions before reading.
        Returns None and logs a warning if the file contains invalid JSON.

        Args:
            path: File path to read from.

        Returns:
            Parsed dictionary, or None if the file does not exist or
            contains invalid/non-JSON data.
        """
        if not path.exists():
            return None
        self._check_and_fix_permissions(path)
        try:
            content = path.read_text(encoding="utf-8")
            parsed = json.loads(content)
        except (json.JSONDecodeError, ValueError, UnicodeDecodeError):
            logger.warning("Corrupted or invalid JSON in %s — ignoring file.", path)
            return None
        if not isinstance(parsed, dict):
            logger.warning(
                "Expected JSON object in %s, got %s — ignoring file.",
                path,
                type(parsed).__name__,
            )
            return None
        return parsed

    def _tokens_path(self, region: str) -> Path:
        """Return the file path for tokens of a given region.

        Args:
            region: Mixpanel data residency region.

        Returns:
            Path to the tokens JSON file.
        """
        return self._storage_dir / f"tokens_{region}.json"

    def _client_path(self, region: str) -> Path:
        """Return the file path for client info of a given region.

        Args:
            region: Mixpanel data residency region.

        Returns:
            Path to the client info JSON file.
        """
        return self._storage_dir / f"client_{region}.json"

    def save_tokens(self, tokens: OAuthTokens, region: str) -> None:
        """Persist OAuth tokens to disk.

        Serializes the token model to JSON, converting ``SecretStr`` fields
        to their plain-text values for storage. The file is written with
        ``0o600`` permissions.

        Args:
            tokens: The OAuth tokens to save.
            region: Mixpanel data residency region (``us``, ``eu``, or ``in``).

        Example:
            ```python
            storage = OAuthStorage()
            storage.save_tokens(tokens, region="us")
            ```
        """
        self._validate_region(region)
        data: dict[str, Any] = {
            "access_token": tokens.access_token.get_secret_value(),
            "expires_at": tokens.expires_at.isoformat(),
            "scope": tokens.scope,
            "token_type": tokens.token_type,
        }
        if tokens.refresh_token is not None:
            data["refresh_token"] = tokens.refresh_token.get_secret_value()
        self._write_file(self._tokens_path(region), data)

    def load_tokens(self, region: str) -> OAuthTokens | None:
        """Load OAuth tokens from disk.

        Reads the tokens JSON file for the given region and reconstructs
        the ``OAuthTokens`` model, wrapping secret fields back into
        ``SecretStr`` instances.

        Args:
            region: Mixpanel data residency region (``us``, ``eu``, or ``in``).

        Returns:
            The loaded OAuthTokens, or None if no tokens file exists.

        Example:
            ```python
            storage = OAuthStorage()
            tokens = storage.load_tokens(region="us")
            if tokens and not tokens.is_expired():
                print("Using cached tokens")
            ```
        """
        self._validate_region(region)
        data = self._read_file(self._tokens_path(region))
        if data is None:
            return None

        try:
            refresh_token: SecretStr | None = None
            raw_refresh = data.get("refresh_token")
            if raw_refresh is not None:
                refresh_token = SecretStr(str(raw_refresh))

            return OAuthTokens(
                access_token=SecretStr(str(data["access_token"])),
                refresh_token=refresh_token,
                expires_at=data["expires_at"],
                scope=str(data["scope"]),
                token_type=str(data["token_type"]),
            )
        except (KeyError, TypeError, ValueError) as exc:
            logger.warning(
                "Failed to parse tokens from %s: %s — ignoring file.",
                self._tokens_path(region),
                exc,
            )
            return None

    def save_client_info(self, info: OAuthClientInfo) -> None:
        """Persist OAuth client registration info to disk.

        Uses the client's ``region`` field to determine the file path.

        Args:
            info: The client registration info to save.

        Example:
            ```python
            storage = OAuthStorage()
            storage.save_client_info(client_info)
            ```
        """
        self._validate_region(info.region)
        data = info.model_dump(mode="json")
        self._write_file(self._client_path(info.region), data)

    def load_client_info(self, region: str) -> OAuthClientInfo | None:
        """Load OAuth client registration info from disk.

        Args:
            region: Mixpanel data residency region (``us``, ``eu``, or ``in``).

        Returns:
            The loaded OAuthClientInfo, or None if no client file exists.

        Example:
            ```python
            storage = OAuthStorage()
            client = storage.load_client_info(region="us")
            if client:
                print(f"Cached client: {client.client_id}")
            ```
        """
        self._validate_region(region)
        data = self._read_file(self._client_path(region))
        if data is None:
            return None
        try:
            return OAuthClientInfo.model_validate(data)
        except (KeyError, TypeError, ValueError) as exc:
            logger.warning(
                "Failed to parse client info from %s: %s — ignoring file.",
                self._client_path(region),
                exc,
            )
            return None

    def delete_tokens(self, region: str) -> None:
        """Delete stored tokens for a region.

        Silently succeeds if the tokens file does not exist.

        Args:
            region: Mixpanel data residency region (``us``, ``eu``, or ``in``).

        Example:
            ```python
            storage = OAuthStorage()
            storage.delete_tokens(region="us")
            ```
        """
        self._validate_region(region)
        path = self._tokens_path(region)
        if path.exists():
            path.unlink()

    def delete_all(self) -> None:
        """Delete all stored tokens and client info files.

        Removes all JSON files in the storage directory. The directory
        itself is preserved. Silently succeeds if the directory does
        not exist.

        Example:
            ```python
            storage = OAuthStorage()
            storage.delete_all()
            ```
        """
        if not self._storage_dir.exists():
            return
        for path in self._storage_dir.glob("*.json"):
            path.unlink()

    def clear_me_cache(self) -> int:
        """Clear cached /me API response files.

        Removes all ``me_*.json`` files from the storage directory.
        These files cache the ``/api/app/me`` response used for
        project and workspace discovery.

        Returns:
            Number of cache files removed.

        Example:
            ```python
            storage = OAuthStorage()
            removed = storage.clear_me_cache()
            print(f"Cleared {removed} cached /me responses")
            ```
        """
        if not self._storage_dir.exists():
            return 0
        count = 0
        for path in self._storage_dir.glob("me_*.json"):
            path.unlink()
            count += 1
        return count
