"""Concrete :class:`TokenResolver` implementations.

The redesigned auth subsystem decouples ``Account`` (which knows what kind
of credentials it represents) from token *materialization* (which knows
where and how to fetch the bearer). This module ships
:class:`OnDiskTokenResolver`, the default implementation that reads OAuth
browser tokens from ``~/.mp/accounts/{name}/tokens.json`` and static
tokens from inline ``SecretStr`` fields or environment variables.

Browser-token refresh delegates to
:meth:`mixpanel_headless._internal.auth.flow.OAuthFlow.refresh_tokens` and
persists the new payload back to the per-account path atomically.

Reference: ``specs/042-auth-architecture-redesign/data-model.md``,
``contracts/python-api.md`` §5.
"""

from __future__ import annotations

import os
from pathlib import Path

from pydantic import ValidationError

from mixpanel_headless._internal.auth.account import (
    OAuthTokenAccount,
    Region,
    TokenResolver,
)
from mixpanel_headless._internal.auth.storage import account_dir
from mixpanel_headless._internal.auth.token import OAuthTokens, token_payload_bytes
from mixpanel_headless._internal.io_utils import (
    atomic_write_bytes,
    read_credential_bytes,
)
from mixpanel_headless.exceptions import OAuthError


def _account_tokens_path(name: str) -> Path:
    """Return ``<account-dir>/tokens.json`` for the given account name.

    Routes through :func:`account_dir` so the
    ``MP_OAUTH_STORAGE_DIR`` env-var override is honored — hard-coding
    ``~/.mp/accounts/`` here would silently bypass test isolation and
    custom-deployment overrides.

    Args:
        name: Account name (validated upstream by the ``Account`` model).

    Returns:
        Absolute path to the per-account tokens file.
    """
    return account_dir(name) / "tokens.json"


class OnDiskTokenResolver(TokenResolver):
    """Default resolver: tokens live on disk per account.

    Reads OAuth browser tokens from ``~/.mp/accounts/{name}/tokens.json``
    written by :class:`OAuthFlow`. Reads static tokens from either the
    inline ``token`` field on the account or the environment variable
    named in ``token_env``.

    The resolver is intentionally I/O-light: the only side effects are
    reading files that already exist and (for expired browser tokens)
    refreshing via :meth:`_refresh_and_persist`, which delegates to
    :class:`OAuthFlow.refresh_tokens` and rewrites
    ``~/.mp/accounts/{name}/tokens.json`` atomically via
    ``atomic_write_bytes``. All failures surface as :class:`OAuthError`
    so callers can give actionable error messages.
    """

    def get_browser_token(self, name: str, region: Region) -> str:
        """Return a fresh access token for an :class:`OAuthBrowserAccount`.

        Reads ``~/.mp/accounts/{name}/tokens.json``, checks the recorded
        ``expires_at`` (with a 30s safety buffer), and returns the token
        if not expired. If expired, refreshes via
        :meth:`_refresh_and_persist`; raises
        :class:`OAuthError(code="OAUTH_REFRESH_ERROR")` if no refresh
        token is recorded.

        Args:
            name: Account name (used to locate the tokens file).
            region: Mixpanel region (kept for parity with the protocol;
                used by some refresh paths).

        Returns:
            The current access token (no ``Bearer`` prefix).

        Raises:
            OAuthError: If the tokens file is missing, malformed, expired
                without a refresh token, or refresh fails.
        """
        path = _account_tokens_path(name)
        if not path.exists():
            raise OAuthError(
                (
                    f"No OAuth tokens found for account '{name}'. "
                    f"Run `mp account login {name}` to authenticate."
                ),
                code="OAUTH_TOKEN_ERROR",
                details={"account_name": name, "path": str(path)},
            )
        try:
            raw = read_credential_bytes(path)
        except OSError as exc:
            raise OAuthError(
                f"Could not read OAuth tokens for account '{name}' from {path}: {exc}",
                code="OAUTH_TOKEN_ERROR",
                details={"account_name": name, "path": str(path)},
            ) from exc

        # Single source of truth for parsing — `OAuthTokens` enforces the
        # tz-aware expiry invariant and the secret-wrapping in one place.
        # Any drift between how tokens are written vs read is structurally
        # impossible because both paths now go through the same model.
        try:
            tokens = OAuthTokens.model_validate_json(raw)
        except ValidationError as exc:
            raise OAuthError(
                (
                    f"OAuth tokens for account '{name}' at {path} are malformed "
                    f"or missing required fields. Re-run `mp account login {name}`."
                ),
                code="OAUTH_TOKEN_ERROR",
                details={
                    "account_name": name,
                    "path": str(path),
                    "validation_error": str(exc),
                },
            ) from exc

        if tokens.is_expired():
            if tokens.refresh_token is None:
                raise OAuthError(
                    (
                        f"OAuth access token for account '{name}' has "
                        f"expired and no refresh token is available. "
                        f"Re-run `mp account login {name}`."
                    ),
                    code="OAUTH_TOKEN_ERROR",
                    details={
                        "account_name": name,
                        "region": region,
                        "path": str(path),
                    },
                )
            return self._refresh_and_persist(
                name=name,
                region=region,
                path=path,
                tokens=tokens,
            )

        return tokens.access_token.get_secret_value()

    def _refresh_and_persist(
        self,
        *,
        name: str,
        region: Region,
        path: Path,
        tokens: OAuthTokens,
    ) -> str:
        """Refresh an expired browser token and rewrite the per-account file atomically.

        Loads the cached DCR client info for ``region`` (shared across
        accounts in the same region — one DCR client per region), POSTs
        the refresh request via :class:`OAuthFlow`, and writes the new
        payload back to ``path`` with mode ``0o600``. The refreshed
        access token is returned so the in-flight HTTP request can use it.

        Args:
            name: Account name (for error messages and the account dir).
            region: Mixpanel region (selects the DCR base URL).
            path: Per-account ``tokens.json`` to rewrite on success.
            tokens: Parsed (still-on-disk) :class:`OAuthTokens` whose
                ``refresh_token`` will be spent. The caller has already
                verified ``tokens.refresh_token is not None``.

        Returns:
            The freshly minted access token (no ``Bearer`` prefix).

        Raises:
            OAuthError: ``OAUTH_REFRESH_ERROR`` for transient/missing-client
                cases; ``OAUTH_REFRESH_REVOKED`` if the IdP rejects the
                refresh token as ``invalid_grant`` (caller should re-login).
        """
        # Lazy imports so this module stays cheap to import at
        # collection time (OAuthFlow pulls in httpx + threading).
        from mixpanel_headless._internal.auth.flow import OAuthFlow
        from mixpanel_headless._internal.auth.storage import OAuthStorage

        storage = OAuthStorage()
        client_info = storage.load_client_info(region=region)
        if client_info is None:
            raise OAuthError(
                (
                    f"OAuth client info for region '{region}' is missing; "
                    f"cannot refresh tokens for account '{name}'. "
                    f"Re-run `mp account login {name}`."
                ),
                code="OAUTH_REFRESH_ERROR",
                details={
                    "account_name": name,
                    "region": region,
                    "path": str(path),
                },
            )

        flow = OAuthFlow(region=region, storage=storage)
        new_tokens = flow.refresh_tokens(
            tokens=tokens,
            client_id=client_info.client_id,
            account_name=name,
        )

        # Refresh tokens may rotate; if the IdP returns no new refresh token
        # we keep the existing one to preserve future refresh capability.
        if new_tokens.refresh_token is None:
            new_tokens = new_tokens.model_copy(
                update={"refresh_token": tokens.refresh_token}
            )
        atomic_write_bytes(path, token_payload_bytes(new_tokens))
        return new_tokens.access_token.get_secret_value()

    def get_static_token(self, account: OAuthTokenAccount) -> str:
        """Return the static bearer for an :class:`OAuthTokenAccount`.

        Resolves the bearer from the inline ``token`` field if present;
        otherwise reads the environment variable named in ``token_env``.

        Args:
            account: The account whose ``token`` or ``token_env`` to resolve.

        Returns:
            The bearer token (no ``Bearer`` prefix).

        Raises:
            OAuthError: If ``token_env`` is set but the env var is unset
                or empty.
        """
        if account.token is not None:
            return account.token.get_secret_value()
        env_name = account.token_env
        # The ``OAuthTokenAccount`` validator enforces ``token XOR token_env``,
        # so this branch is reachable only when ``token_env`` is set. We raise
        # explicitly (rather than ``assert env_name is not None``) so the
        # invariant survives ``python -O``, where assertions are stripped.
        if env_name is None:  # pragma: no cover — model invariant
            raise OAuthError(
                f"OAuth account '{account.name}' has neither `token` nor `token_env`.",
                code="OAUTH_TOKEN_ERROR",
                details={"account_name": account.name},
            )
        value = os.environ.get(env_name)
        if not value:
            raise OAuthError(
                (
                    f"OAuth account '{account.name}' references env var "
                    f"`{env_name}`, but it is not set or is empty."
                ),
                code="OAUTH_TOKEN_ERROR",
                details={"account_name": account.name, "env_var": env_name},
            )
        return value


__all__ = [
    "OnDiskTokenResolver",
]
