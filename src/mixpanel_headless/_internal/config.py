"""Configuration management for ``mixpanel_headless``.

Owns the single-schema TOML config file (``~/.mp/config.toml``) with
``[active]``, ``[accounts.NAME]``, ``[targets.NAME]``, ``[settings]``
sections.

Reference:
    ``specs/042-auth-architecture-redesign/contracts/config-schema.md`` §1.
"""

from __future__ import annotations

import logging
import os
import stat
import sys
from collections.abc import Generator
from contextlib import contextmanager, suppress
from pathlib import Path
from typing import Any

if sys.version_info >= (3, 11):
    import tomllib
else:  # pragma: no cover - py3.10 fallback (tomllib added in 3.11)
    # On py3.10, tomli is installed and import succeeds — `import-not-found`
    # is a no-op there but is needed when mypy is run on py3.11+ where the
    # `python_version < '3.11'` extra dep isn't pulled in. `unused-ignore`
    # silences mypy on the platform where the ignore is in fact unused.
    import tomli as tomllib  # type: ignore[import-not-found, unused-ignore]

import tomli_w
from pydantic import (
    SecretStr,
    TypeAdapter,
    ValidationError,
)

from mixpanel_headless._internal.auth.account import (
    Account,
    AccountType,
    OAuthTokenAccount,
    Region,
    ServiceAccount,
)
from mixpanel_headless._internal.auth.session import ActiveSession
from mixpanel_headless._internal.io_utils import (
    atomic_write_bytes,
    read_credential_text,
    reject_if_symlink,
)
from mixpanel_headless.exceptions import (
    AccountInUseError,
    ConfigError,
)
from mixpanel_headless.types import AccountSummary, Target

logger = logging.getLogger(__name__)

_DEFAULT_CONFIG_PATH = Path.home() / ".mp" / "config.toml"


# =============================================================================
# ConfigManager
# =============================================================================


_account_adapter: TypeAdapter[Account] = TypeAdapter(Account)


def _account_from_block(name: str, block: dict[str, Any]) -> Account:
    """Construct an :class:`Account` variant from a parsed ``[accounts.NAME]`` block.

    Args:
        name: Account name (matches the TOML block key).
        block: Parsed block contents.

    Returns:
        A frozen :class:`Account` instance.

    Raises:
        ConfigError: On validation failure (missing required field, bad type,
            etc.); the wrapped Pydantic error is included for debuggability.
    """
    try:
        return _account_adapter.validate_python({"name": name, **block})
    except ValidationError as exc:
        raise ConfigError(
            f"Invalid [accounts.{name}] block: {exc.errors(include_url=False)[0]['msg']}"
        ) from exc


def _account_to_block(account: Account) -> dict[str, Any]:
    """Serialize an :class:`Account` variant to a TOML-ready dict (excludes ``name``).

    Args:
        account: Frozen :class:`Account` to serialize.

    Returns:
        Plain dict with ``type``, ``region``, and type-specific fields. Secrets
        are unwrapped to plain strings (TOML cannot store opaque ``SecretStr``).
    """
    out: dict[str, Any] = {"type": account.type, "region": account.region}
    if account.default_project is not None:
        out["default_project"] = account.default_project
    if isinstance(account, ServiceAccount):
        out["username"] = account.username
        out["secret"] = account.secret.get_secret_value()
    elif isinstance(account, OAuthTokenAccount):
        if account.token is not None:
            out["token"] = account.token.get_secret_value()
        # The ``OAuthTokenAccount`` validator enforces ``token XOR token_env``,
        # so this branch is reachable only when ``token_env`` is set. Raise
        # explicitly (rather than ``assert``) so the invariant survives
        # ``python -O``, where assertions are stripped.
        elif account.token_env is None:  # pragma: no cover — model invariant
            raise ConfigError(
                f"OAuthTokenAccount {account.name!r} has neither "
                "`token` nor `token_env`."
            )
        else:
            out["token_env"] = account.token_env
    # OAuthBrowserAccount has no extra fields beyond the common set.
    return out


class ConfigManager:
    """Single-schema configuration manager.

    Wraps a single ``~/.mp/config.toml`` file (or ``MP_CONFIG_PATH`` override).
    All operations re-read the file from disk, so concurrent edits are safe
    in the "last write wins" sense (no file locking — single-user workflow
    by design).

    Notes:
        - File creation enforces mode ``0o600`` and parent dir ``0o700``.
        - Unknown keys are rejected at Pydantic validation. To recover
          from a corrupted config, delete it and re-add accounts via
          ``mp account add``.
    """

    def __init__(self, *, config_path: Path | None = None) -> None:
        """Initialize the manager.

        Args:
            config_path: Path to the TOML config file. Defaults to
                ``$MP_CONFIG_PATH`` if set, else ``~/.mp/config.toml``.
        """
        if config_path is not None:
            self._path = config_path
        elif "MP_CONFIG_PATH" in os.environ:
            self._path = Path(os.environ["MP_CONFIG_PATH"])
        else:
            self._path = _DEFAULT_CONFIG_PATH

    @property
    def config_path(self) -> Path:
        """Return the path of the on-disk TOML config."""
        return self._path

    # ---- internals ---------------------------------------------------

    def _read_raw(self) -> dict[str, Any]:
        """Parse the TOML file.

        Returns:
            Raw parsed dict. Empty dict if file does not exist.

        Raises:
            ConfigError: Malformed TOML. Legacy v1/v2 schemas are no
                longer detected with a friendly message — they fail at
                the Pydantic validation layer with an "unexpected key"
                error. Under the alpha "free to break" lens the user is
                expected to delete the file and re-add via ``mp account
                add``.
        """
        # Probe for symlink BEFORE the existence check — Path.exists()
        # follows symlinks and silently returns False for dangling links,
        # hiding the attack signal. CredentialPathError surfaces as
        # ConfigError below via the existing OSError catch.
        try:
            reject_if_symlink(self._path)
        except OSError as exc:
            raise ConfigError(f"Could not parse config at {self._path}: {exc}") from exc
        if not self._path.exists():
            return {}
        try:
            raw: dict[str, Any] = tomllib.loads(read_credential_text(self._path))
        except (tomllib.TOMLDecodeError, OSError) as exc:
            raise ConfigError(f"Could not parse config at {self._path}: {exc}") from exc
        return raw

    def _write_raw(self, raw: dict[str, Any]) -> None:
        """Serialize ``raw`` to the config file with restrictive permissions.

        Creates parent dirs (``~/.mp/``) with mode ``0o700`` and writes the
        file atomically with mode ``0o600`` via :func:`atomic_write_bytes`.

        Args:
            raw: Dict to serialize as TOML.
        """
        self._path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        # Tighten parent dir permissions in case it pre-existed with 0o755.
        with suppress(OSError):
            self._path.parent.chmod(stat.S_IRWXU)
        atomic_write_bytes(self._path, tomli_w.dumps(raw).encode("utf-8"))

    @contextmanager
    def _mutate(self) -> Generator[dict[str, Any], None, None]:
        """Open a single read-modify-write transaction on the raw config dict.

        The dict is read once at entry and written once at exit. If the
        body raises, the write is skipped — partial mutations never reach
        disk. Multiple in-package callers (``Workspace._persist_active``,
        ``mp.session.use``, ``mp.accounts.add``) compose several
        ``_apply_*`` mutations within a single transaction so the
        end-to-end operation is atomic, not just per-mutator.

        Before the write, ``_validate_raw`` runs a whole-file pass over
        every account block. The per-mutator helpers only validate the
        block they touched, so this is the safety net that keeps an
        externally-corrupted file (hand-edit or future bug) from being
        silently rewritten with a fresh-but-incomplete repair.

        Yields:
            The parsed raw dict, mutated in place.

        Raises:
            ConfigError: Propagated from ``_read_raw``, ``_apply_*``
                helpers, or the exit-time ``_validate_raw`` pass.
        """
        raw = self._read_raw()
        yield raw
        self._validate_raw(raw)
        self._write_raw(raw)

    @staticmethod
    def _validate_raw(raw: dict[str, Any]) -> None:
        """Validate every account block in ``raw`` against the schema.

        Whole-file safety net for ``_mutate``. Catches malformed blocks
        the per-mutator helpers never touched (legacy v1/v2 cruft left
        behind after an upgrade, hand-edited files, etc.) so we never
        persist a write on top of a known-bad sibling.

        Args:
            raw: Parsed TOML dict to validate.

        Raises:
            ConfigError: Any account block fails schema validation.
                Re-raises the wrapping that ``_account_from_block`` emits.
        """
        for name, block in (raw.get("accounts", {}) or {}).items():
            if isinstance(block, dict):
                _account_from_block(name, block)

    @staticmethod
    def _apply_set_active(
        raw: dict[str, Any],
        *,
        account: str | None = None,
        workspace: int | None = None,
    ) -> None:
        """In-place ``[active]`` mutation shared by ``set_active`` and multi-call sites.

        Each kwarg is independent: ``None`` leaves that axis untouched.
        Validates account existence and workspace shape before mutating.

        Args:
            raw: Parsed TOML dict (mutated in place).
            account: New active account name (must reference an existing account).
            workspace: New active workspace ID (positive integer).

        Raises:
            ConfigError: Account not configured, or workspace not a positive int.
        """
        active_block = raw.setdefault("active", {})
        if account is not None:
            accounts_block = raw.get("accounts", {}) or {}
            if account not in accounts_block:
                raise ConfigError(
                    f"Cannot set active account: '{account}' is not configured."
                )
            active_block["account"] = account
        if workspace is not None:
            ConfigManager._validate_workspace_id(workspace)
            active_block["workspace"] = workspace

    @staticmethod
    def _apply_clear_active(
        raw: dict[str, Any],
        *,
        account: bool = False,
        workspace: bool = False,
    ) -> None:
        """In-place ``[active]`` axis-removal shared by ``clear_active`` and multi-call sites.

        Args:
            raw: Parsed TOML dict (mutated in place).
            account: Drop ``[active].account`` if True.
            workspace: Drop ``[active].workspace`` if True.
        """
        active_block = raw.get("active", {}) or {}
        if account and "account" in active_block:
            del active_block["account"]
        if workspace and "workspace" in active_block:
            del active_block["workspace"]
        if active_block:
            raw["active"] = active_block
        else:
            raw.pop("active", None)

    @staticmethod
    def _apply_update_account(
        raw: dict[str, Any],
        name: str,
        *,
        region: Region | None = None,
        default_project: str | None = None,
        username: str | None = None,
        secret: SecretStr | str | None = None,
        token: SecretStr | str | None = None,
        token_env: str | None = None,
    ) -> Account:
        """In-place per-account mutation shared by ``update_account`` and multi-call sites.

        Args:
            raw: Parsed TOML dict (mutated in place).
            name: Account name to update (must already exist).
            region: New region.
            default_project: New default project ID (digit string).
            username: New username (service_account only).
            secret: New secret (service_account only).
            token: New inline token (oauth_token only).
            token_env: New env-var name (oauth_token only).

        Returns:
            The updated :class:`Account`.

        Raises:
            ConfigError: Account not found, type-incompatible field, or
                validation failure.
        """
        accounts_block = raw.get("accounts", {}) or {}
        if name not in accounts_block:
            raise ConfigError(f"Account '{name}' not found.")
        block = dict(accounts_block[name])
        acct_type = block.get("type")

        if region is not None:
            block["region"] = region
        if default_project is not None:
            block["default_project"] = default_project
        if username is not None:
            if acct_type != "service_account":
                raise ConfigError(
                    f"`username` only applies to service_account "
                    f"(account '{name}' is {acct_type!r})."
                )
            block["username"] = username
        if secret is not None:
            if acct_type != "service_account":
                raise ConfigError(
                    f"`secret` only applies to service_account "
                    f"(account '{name}' is {acct_type!r})."
                )
            block["secret"] = (
                secret.get_secret_value() if isinstance(secret, SecretStr) else secret
            )
        if token is not None or token_env is not None:
            if acct_type != "oauth_token":
                raise ConfigError(
                    f"`token`/`token_env` only apply to oauth_token "
                    f"(account '{name}' is {acct_type!r})."
                )
            if token is not None and token_env is not None:
                raise ConfigError(
                    "OAuthTokenAccount: `token` and `token_env` are mutually exclusive."
                )
            block.pop("token", None)
            block.pop("token_env", None)
            if token is not None:
                block["token"] = (
                    token.get_secret_value() if isinstance(token, SecretStr) else token
                )
            # Mutual exclusion is enforced above, so reaching this branch
            # with ``token_env is None`` is impossible. Raise explicitly
            # rather than ``assert`` so the invariant survives ``python -O``.
            elif token_env is None:  # pragma: no cover — control-flow invariant
                raise ConfigError(
                    f"Account {name!r}: neither `token` nor `token_env` resolved."
                )
            else:
                block["token_env"] = token_env

        try:
            account = _account_adapter.validate_python({"name": name, **block})
        except ValidationError as exc:
            raise ConfigError(
                f"Invalid account fields for '{name}': "
                f"{exc.errors(include_url=False)[0]['msg']}"
            ) from exc
        accounts_block[name] = _account_to_block(account)
        return account

    @staticmethod
    def _apply_add_account(
        raw: dict[str, Any],
        name: str,
        *,
        type: AccountType,  # noqa: A002 — matches public surface
        region: Region,
        default_project: str | None = None,
        username: str | None = None,
        secret: SecretStr | str | None = None,
        token: SecretStr | str | None = None,
        token_env: str | None = None,
    ) -> Account:
        """In-place ``[accounts.NAME]`` insertion shared by ``add_account`` and ``mp.accounts.add``.

        Per 043 FR-001, ``default_project`` is OPTIONAL for every
        account type at add-time. Service-account and oauth_token
        callers can backfill it later via ``mp project use ID`` (or the
        ``mp login`` orchestrator's project picker). The 042 hard
        requirement was relaxed because ``mp project list`` now
        bootstraps from ``/me`` without needing a configured project.

        Args:
            raw: Parsed TOML dict (mutated in place).
            name: New account name.
            type: One of ``service_account`` / ``oauth_browser`` / ``oauth_token``.
            region: One of ``us`` / ``eu`` / ``in``.
            default_project: Numeric project ID (string).
            username: Required for ``service_account``.
            secret: Required for ``service_account``.
            token: For ``oauth_token`` (mutually exclusive with ``token_env``).
            token_env: For ``oauth_token`` (mutually exclusive with ``token``).

        Returns:
            The constructed :class:`Account`.

        Raises:
            ConfigError: Duplicate name, missing-required field, validation failure.
        """
        accounts_block = raw.setdefault("accounts", {})
        if name in accounts_block:
            raise ConfigError(f"Account '{name}' already exists.")

        block: dict[str, Any] = {"type": type, "region": region}
        if default_project is not None:
            block["default_project"] = default_project
        if type == "service_account":
            if username is None or secret is None:
                raise ConfigError("ServiceAccount requires `username` and `secret`.")
            block["username"] = username
            block["secret"] = (
                secret.get_secret_value() if isinstance(secret, SecretStr) else secret
            )
        elif type == "oauth_browser":
            pass  # default_project is optional; populated by `mp account login` later.
        elif type == "oauth_token":
            if (token is None) == (token_env is None):
                raise ConfigError(
                    "OAuthTokenAccount requires exactly one of `token` or `token_env`."
                )
            if token is not None:
                block["token"] = (
                    token.get_secret_value() if isinstance(token, SecretStr) else token
                )
            # XOR is enforced above, so reaching this branch with
            # ``token_env is None`` is impossible. Raise explicitly rather
            # than ``assert`` so the invariant survives ``python -O``.
            elif token_env is None:  # pragma: no cover — control-flow invariant
                raise ConfigError(
                    f"Account {name!r}: neither `token` nor `token_env` resolved."
                )
            else:
                block["token_env"] = token_env
        else:  # pragma: no cover — Literal exhaustiveness
            raise ConfigError(f"Unknown account type: {type!r}")

        try:
            account = _account_adapter.validate_python({"name": name, **block})
        except ValidationError as exc:
            raise ConfigError(
                f"Invalid account fields for '{name}': "
                f"{exc.errors(include_url=False)[0]['msg']}"
            ) from exc

        accounts_block[name] = _account_to_block(account)
        return account

    # ---- accounts ----------------------------------------------------

    def list_accounts(self) -> list[AccountSummary]:
        """Return a sorted list of ``AccountSummary`` for every configured account.

        Returns:
            Sorted-by-name list of summaries. Each summary's ``is_active``
            is ``True`` iff ``[active].account == summary.name``;
            ``referenced_by_targets`` lists target names that reference it.
        """
        raw = self._read_raw()
        accounts_block = raw.get("accounts", {}) or {}
        targets_block = raw.get("targets", {}) or {}
        active_block = raw.get("active", {}) or {}
        active_account = active_block.get("account")

        # Build account → referencing-target list.
        refs: dict[str, list[str]] = {}
        for tname, tblock in sorted(targets_block.items()):
            if isinstance(tblock, dict):
                acct = tblock.get("account")
                if isinstance(acct, str):
                    refs.setdefault(acct, []).append(tname)

        out: list[AccountSummary] = []
        for name in sorted(accounts_block):
            block = accounts_block[name]
            if not isinstance(block, dict):
                continue
            account = _account_from_block(name, block)
            out.append(
                AccountSummary(
                    name=account.name,
                    type=account.type,
                    region=account.region,
                    is_active=(active_account == account.name),
                    referenced_by_targets=refs.get(account.name, []),
                )
            )
        return out

    def get_account(self, name: str) -> Account:
        """Return the ``Account`` for ``name`` (raises if missing).

        Args:
            name: Account name.

        Returns:
            The frozen ``Account`` variant.

        Raises:
            ConfigError: If ``name`` is not configured.
        """
        raw = self._read_raw()
        accounts_block = raw.get("accounts", {}) or {}
        block = accounts_block.get(name)
        if not isinstance(block, dict):
            raise ConfigError(f"Account '{name}' not found.")
        return _account_from_block(name, block)

    def add_account(
        self,
        name: str,
        *,
        type: AccountType,
        region: Region,
        default_project: str | None = None,
        username: str | None = None,
        secret: SecretStr | str | None = None,
        token: SecretStr | str | None = None,
        token_env: str | None = None,
    ) -> Account:
        """Add an account block to the config.

        Per 043 FR-001, ``default_project`` is OPTIONAL for every
        account type at add-time. Service-account and oauth_token
        callers can backfill it later via ``mp project use ID`` (or
        the ``mp login`` orchestrator's project picker). For
        ``oauth_browser`` the value is also backfilled by
        ``mp account login`` post-PKCE via ``/me``. The 042 hard
        requirement was relaxed because ``mp project list`` now
        bootstraps from ``/me`` without a configured project.

        Args:
            name: Account name (must match ``^[a-zA-Z0-9_-]{1,64}$``).
            type: One of ``service_account`` / ``oauth_browser`` / ``oauth_token``.
            region: One of ``us`` / ``eu`` / ``in``.
            default_project: Numeric project ID. Optional for every type;
                populated later via ``mp project use``, ``mp login``, or
                (for oauth_browser) ``mp account login``.
            username: Required for ``service_account``.
            secret: Required for ``service_account``.
            token: For ``oauth_token`` (mutually exclusive with ``token_env``).
            token_env: For ``oauth_token`` (mutually exclusive with ``token``).

        Returns:
            The constructed ``Account``.

        Raises:
            ConfigError: Duplicate name, validation failure, or referential
                integrity violation.
        """
        with self._mutate() as raw:
            return self._apply_add_account(
                raw,
                name,
                type=type,
                region=region,
                default_project=default_project,
                username=username,
                secret=secret,
                token=token,
                token_env=token_env,
            )

    def update_account(
        self,
        name: str,
        *,
        region: Region | None = None,
        default_project: str | None = None,
        username: str | None = None,
        secret: SecretStr | str | None = None,
        token: SecretStr | str | None = None,
        token_env: str | None = None,
    ) -> Account:
        """Update an existing account in place.

        Only supplied fields are changed. Type cannot be changed via this
        method (remove + re-add for that). Type-incompatible fields (e.g.,
        ``token`` for a ``service_account``) raise ``ConfigError``.

        Args:
            name: Account name to update.
            region: New region.
            default_project: New default project ID (digit string).
            username: New username (service_account only).
            secret: New secret (service_account only).
            token: New inline token (oauth_token only).
            token_env: New env-var name (oauth_token only).

        Returns:
            The updated ``Account``.

        Raises:
            ConfigError: Account not found, type-incompatible field, or
                validation failure.
        """
        with self._mutate() as raw:
            return self._apply_update_account(
                raw,
                name,
                region=region,
                default_project=default_project,
                username=username,
                secret=secret,
                token=token,
                token_env=token_env,
            )

    def remove_account(self, name: str, *, force: bool = False) -> list[str]:
        """Remove an account.

        Args:
            name: Account to remove.
            force: When ``True``, remove the account even if it's referenced
                by targets; the orphaned target names are returned. When
                ``False``, raises ``AccountInUseError`` if any target
                references the account.

        Returns:
            Sorted list of target names that referenced the account (empty
            unless the account was referenced).

        Raises:
            ConfigError: If the account does not exist.
            AccountInUseError: If the account is referenced and ``force=False``.
        """
        with self._mutate() as raw:
            accounts_block = raw.get("accounts", {}) or {}
            if name not in accounts_block:
                raise ConfigError(f"Account '{name}' not found.")
            targets_block = raw.get("targets", {}) or {}
            referenced = sorted(
                tname
                for tname, tblock in targets_block.items()
                if isinstance(tblock, dict) and tblock.get("account") == name
            )
            if referenced and not force:
                raise AccountInUseError(name, referenced_by=referenced)
            del accounts_block[name]
            # If the removed account was the active one, drop both axes so a
            # fresh `Workspace()` doesn't trip on the dangling reference and
            # `session.show()` doesn't keep printing the deleted name. The
            # workspace ID is meaningless without its account, so it goes too.
            active_block = raw.get("active", {}) or {}
            if active_block.get("account") == name:
                self._apply_clear_active(raw, account=True, workspace=True)
        return referenced

    # ---- active ------------------------------------------------------

    def get_active(self) -> ActiveSession:
        """Return the persisted ``[active]`` block as an ``ActiveSession``.

        Returns:
            ``ActiveSession`` with the three optional fields. Missing block
            yields an empty ``ActiveSession()``.

        Raises:
            ConfigError: If a referenced account does not exist.
        """
        raw = self._read_raw()
        active_block = raw.get("active", {}) or {}
        try:
            return ActiveSession.model_validate(active_block)
        except ValidationError as exc:
            raise ConfigError(
                f"Invalid [active] block: {exc.errors(include_url=False)[0]['msg']}"
            ) from exc

    def set_active(
        self,
        *,
        account: str | None = None,
        workspace: int | None = None,
    ) -> ActiveSession:
        """Update one or more axes in the ``[active]`` block.

        ``[active]`` only stores ``account`` and ``workspace`` — project
        lives on the account itself as ``Account.default_project``. To
        change the active account's home project, use
        :meth:`update_account` (e.g., ``cm.update_account(name, default_project=ID)``).

        Each kwarg is independent: passing only ``workspace=W`` updates that
        axis and leaves ``account`` untouched. Passing ``None`` for an axis
        leaves it untouched (use ``clear_active`` to remove keys).

        Args:
            account: New active account name (must reference an existing
                ``[accounts.X]``).
            workspace: New active workspace ID (positive int).

        Returns:
            The updated ``ActiveSession``.

        Raises:
            ConfigError: Validation failure or referential integrity violation.
        """
        with self._mutate() as raw:
            self._apply_set_active(raw, account=account, workspace=workspace)
        return self.get_active()

    def clear_active(
        self,
        *,
        account: bool = False,
        workspace: bool = False,
    ) -> ActiveSession:
        """Remove specific axes from the ``[active]`` block.

        Args:
            account: Drop ``account`` axis if True.
            workspace: Drop ``workspace`` axis if True.

        Returns:
            The updated ``ActiveSession`` after removals.
        """
        with self._mutate() as raw:
            self._apply_clear_active(raw, account=account, workspace=workspace)
        return self.get_active()

    def apply_session(
        self,
        *,
        account: str | None = None,
        project: str | None = None,
        workspace: int | None = None,
        clear_workspace: bool = False,
    ) -> ActiveSession:
        """Atomically apply per-axis session updates in a single transaction.

        Public composition of the per-axis ``_apply_*`` mutators so callers
        like :func:`mixpanel_headless.session.use` and
        :meth:`mixpanel_headless.workspace.Workspace._persist_active` do not
        have to drive ``_mutate()`` directly. All updates land within one
        read-modify-write cycle so an interrupted process never leaves the
        on-disk state reflecting a partial swap (e.g., new account but
        stale project).

        Each axis kwarg is independent:

        - ``account=None`` leaves ``[active].account`` untouched.
        - ``project=None`` leaves the target account's
          ``default_project`` untouched.
        - ``workspace=None`` leaves ``[active].workspace`` untouched.
        - ``clear_workspace=True`` removes ``[active].workspace``
          (mutually exclusive with ``workspace=``).

        ``project=`` writes to the EXPLICIT ``account=`` (if given) else
        the persisted active account. Raises ``ConfigError`` if no
        account can be resolved when ``project=`` is supplied.

        Args:
            account: New active account name (must reference an existing
                ``[accounts.X]``).
            project: New ``default_project`` for the target account.
            workspace: New active workspace ID (positive int).
            clear_workspace: When True, drop ``[active].workspace``.

        Returns:
            The updated ``ActiveSession``.

        Raises:
            ConfigError: Validation failure, missing referenced account,
                or ``project=`` supplied without an active or explicit
                account.
            ValueError: Both ``workspace=`` and ``clear_workspace=True``
                supplied.
        """
        if workspace is not None and clear_workspace:
            raise ValueError(
                "`workspace=` and `clear_workspace=True` are mutually exclusive."
            )
        with self._mutate() as raw:
            if account is not None or workspace is not None:
                self._apply_set_active(raw, account=account, workspace=workspace)
            if clear_workspace:
                self._apply_clear_active(raw, workspace=True)
            if project is not None:
                active_block = raw.get("active", {}) or {}
                target_account = (
                    account if account is not None else active_block.get("account")
                )
                if not isinstance(target_account, str):
                    raise ConfigError(
                        "Cannot set project: no active account. "
                        "Run `mp account use NAME` first, or pass `account=NAME` "
                        "together with `project=`."
                    )
                self._apply_update_account(raw, target_account, default_project=project)
        return self.get_active()

    # ---- targets -----------------------------------------------------

    def list_targets(self) -> list[Target]:
        """Return a sorted-by-name list of ``Target`` records.

        Returns:
            All configured targets.

        Raises:
            ConfigError: If a target block fails validation.
        """
        raw = self._read_raw()
        targets_block = raw.get("targets", {}) or {}
        out: list[Target] = []
        for name in sorted(targets_block):
            block = targets_block[name]
            if not isinstance(block, dict):
                continue
            try:
                out.append(Target(name=name, **block))
            except ValidationError as exc:
                raise ConfigError(
                    f"Invalid [targets.{name}] block: "
                    f"{exc.errors(include_url=False)[0]['msg']}"
                ) from exc
        return out

    def get_target(self, name: str) -> Target:
        """Return the ``Target`` for ``name`` (raises if missing).

        Args:
            name: Target name.

        Returns:
            The frozen ``Target`` instance.

        Raises:
            ConfigError: If ``name`` is not configured.
        """
        raw = self._read_raw()
        targets_block = raw.get("targets", {}) or {}
        block = targets_block.get(name)
        if not isinstance(block, dict):
            raise ConfigError(f"Target '{name}' not found.")
        try:
            return Target(name=name, **block)
        except ValidationError as exc:
            raise ConfigError(
                f"Invalid [targets.{name}] block: "
                f"{exc.errors(include_url=False)[0]['msg']}"
            ) from exc

    def add_target(
        self,
        name: str,
        *,
        account: str,
        project: str,
        workspace: int | None = None,
    ) -> Target:
        """Add a target block to the config.

        Args:
            name: Target name (block key).
            account: Referenced account name (must exist).
            project: Project ID (digit string).
            workspace: Optional workspace ID (positive int).

        Returns:
            The constructed ``Target``.

        Raises:
            ConfigError: Duplicate name, missing account, or validation failure.
        """
        with self._mutate() as raw:
            accounts_block = raw.get("accounts", {}) or {}
            if account not in accounts_block:
                raise ConfigError(
                    f"Cannot create target '{name}': "
                    f"account '{account}' is not configured."
                )
            targets_block = raw.setdefault("targets", {})
            if name in targets_block:
                raise ConfigError(f"Target '{name}' already exists.")

            try:
                target = Target(
                    name=name, account=account, project=project, workspace=workspace
                )
            except ValidationError as exc:
                raise ConfigError(
                    f"Invalid target fields for '{name}': "
                    f"{exc.errors(include_url=False)[0]['msg']}"
                ) from exc

            block: dict[str, Any] = {"account": account, "project": project}
            if workspace is not None:
                block["workspace"] = workspace
            targets_block[name] = block
        return target

    def remove_target(self, name: str) -> None:
        """Remove a target block from the config.

        Args:
            name: Target name to remove.

        Raises:
            ConfigError: If the target does not exist.
        """
        with self._mutate() as raw:
            targets_block = raw.get("targets", {}) or {}
            if name not in targets_block:
                raise ConfigError(f"Target '{name}' not found.")
            del targets_block[name]

    def apply_target(self, name: str) -> ActiveSession:
        """Write the target to config in a single atomic save.

        Writes ``[active].account = target.account`` and
        ``[active].workspace = target.workspace``, AND updates the target
        account's ``default_project`` to the target's project. This keeps
        the account's home project in sync with the most recently applied
        target — `mp session` after `mp target use ecom` reflects all three
        axes (account, project, workspace) without needing a second config
        layer for "active project".

        Args:
            name: Target to apply.

        Returns:
            The updated ``ActiveSession``.

        Raises:
            ConfigError: If the target does not exist OR its referenced
                account is no longer configured.
        """
        with self._mutate() as raw:
            targets_block = raw.get("targets", {}) or {}
            target_block = targets_block.get(name)
            if not isinstance(target_block, dict):
                raise ConfigError(f"Target '{name}' not found.")
            try:
                target = Target(name=name, **target_block)
            except ValidationError as exc:
                raise ConfigError(
                    f"Invalid [targets.{name}] block: "
                    f"{exc.errors(include_url=False)[0]['msg']}"
                ) from exc
            accounts_block = raw.get("accounts", {}) or {}
            if target.account not in accounts_block:
                raise ConfigError(
                    f"Cannot apply target '{name}': "
                    f"account '{target.account}' is not configured."
                )
            # Update target account's default_project to match the target's project.
            account_block = dict(accounts_block[target.account])
            account_block["default_project"] = target.project
            accounts_block[target.account] = account_block
            # Replace [active] wholesale — a target with no workspace clears
            # any prior workspace pin.
            active_block: dict[str, Any] = {"account": target.account}
            if target.workspace is not None:
                active_block["workspace"] = target.workspace
            raw["active"] = active_block
        return self.get_active()

    # ---- settings ----------------------------------------------------

    def get_custom_header(self) -> tuple[str, str] | None:
        """Return ``(name, value)`` for ``[settings].custom_header`` if present.

        Returns:
            Tuple ``(name, value)`` or ``None``.

        Raises:
            ConfigError: If the block is malformed (missing keys, wrong types).
        """
        raw = self._read_raw()
        settings = raw.get("settings", {}) or {}
        header = settings.get("custom_header")
        if header is None:
            return None
        if not isinstance(header, dict):
            raise ConfigError(
                "[settings].custom_header must be an inline table {name=, value=}."
            )
        name = header.get("name")
        value = header.get("value")
        if not isinstance(name, str) or not isinstance(value, str):
            raise ConfigError(
                "[settings].custom_header requires `name` and `value` strings."
            )
        return (name, value)

    def set_custom_header(self, *, name: str, value: str) -> None:
        """Write the custom HTTP header to ``[settings].custom_header``.

        Args:
            name: Header name (e.g., ``X-Mixpanel-Cluster``).
            value: Header value.
        """
        with self._mutate() as raw:
            settings = raw.setdefault("settings", {})
            settings["custom_header"] = {"name": name, "value": value}

    # ---- validators --------------------------------------------------

    @staticmethod
    def _validate_workspace_id(workspace: int) -> None:
        """Validate a workspace ID is positive.

        Args:
            workspace: Candidate ID.

        Raises:
            ConfigError: If ``workspace`` is not a positive integer.
        """
        if not isinstance(workspace, int) or workspace <= 0:
            raise ConfigError(
                f"Invalid workspace ID: {workspace!r}. Must be a positive integer."
            )


__all__ = [
    "ConfigManager",
]
