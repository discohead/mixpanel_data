"""OAuth token and client info models.

Immutable Pydantic models for OAuth 2.0 token management and
Dynamic Client Registration (DCR) client metadata.

Example:
    ```python
    from mixpanel_headless._internal.auth.token import OAuthTokens, OAuthClientInfo

    tokens = OAuthTokens.from_token_response(
        {"access_token": "abc", "refresh_token": "def", "expires_in": 3600,
         "scope": "read", "token_type": "Bearer"},
    )
    if tokens.is_expired():
        print("Token needs refresh")
    ```
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from pydantic import BaseModel, ConfigDict, SecretStr, field_validator


class OAuthTokens(BaseModel):
    """Immutable OAuth 2.0 token set with expiry tracking.

    Stores access and optional refresh tokens along with metadata
    from the token response. The ``is_expired`` method includes a
    30-second safety buffer to avoid using tokens that are about to expire.

    Attributes:
        access_token: The OAuth access token (redacted in output).
        refresh_token: The OAuth refresh token, if provided (redacted in output).
        expires_at: UTC datetime when the access token expires.
        scope: Space-separated list of granted scopes.
        token_type: Token type, typically ``"Bearer"``.
    """

    model_config = ConfigDict(frozen=True)

    access_token: SecretStr
    """The OAuth access token (redacted in output)."""

    refresh_token: SecretStr | None = None
    """The OAuth refresh token, if provided (redacted in output)."""

    expires_at: datetime
    """UTC datetime when the access token expires.

    Must be timezone-aware. Naive datetimes are rejected at validation
    time so a downstream consumer can never accidentally compare against
    an aware ``datetime.now(timezone.utc)`` and silently fall through
    the expiry check (Fix 25)."""

    scope: str
    """Space-separated list of granted scopes."""

    token_type: str
    """Token type, typically ``'Bearer'``."""

    @field_validator("expires_at")
    @classmethod
    def _require_tz_aware(cls, value: datetime) -> datetime:
        """Reject naive ``expires_at`` values.

        Args:
            value: The candidate ``expires_at``.

        Returns:
            The same value (no mutation).

        Raises:
            ValueError: If ``value.tzinfo is None``.
        """
        if value.tzinfo is None:
            raise ValueError(
                "OAuthTokens.expires_at must be timezone-aware (UTC). "
                "Got a naive datetime, which would compare unsafely against "
                "tz-aware `datetime.now(timezone.utc)` and silently bypass "
                "the expiry check."
            )
        return value

    def is_expired(self) -> bool:
        """Check whether the access token is expired or about to expire.

        Uses a 30-second safety buffer to avoid sending tokens that are
        about to expire during in-flight requests.

        Returns:
            True if the token is expired or will expire within 30 seconds.

        Example:
            ```python
            tokens = OAuthTokens.from_token_response(
                {"access_token": "x", "expires_in": 10,
                 "scope": "read", "token_type": "Bearer"}
            )
            assert tokens.is_expired()  # 10s < 30s buffer
            ```
        """
        return datetime.now(timezone.utc) + timedelta(seconds=30) >= self.expires_at

    @classmethod
    def from_token_response(cls, data: dict[str, object]) -> OAuthTokens:
        """Create an OAuthTokens instance from a raw token endpoint response.

        Computes ``expires_at`` by adding the ``expires_in`` value (in seconds)
        to the current UTC time.

        Args:
            data: Raw JSON response from the token endpoint. Must contain
                ``access_token``, ``expires_in``, ``scope``, and ``token_type``.
                May contain ``refresh_token``.

        Returns:
            A new frozen OAuthTokens instance.

        Raises:
            KeyError: If required keys are missing from ``data``.
            ValueError: If ``expires_in`` cannot be converted to an int.

        Example:
            ```python
            response = {
                "access_token": "eyJ...",
                "refresh_token": "dGhp...",
                "expires_in": 3600,
                "scope": "read:project",
                "token_type": "Bearer",
            }
            tokens = OAuthTokens.from_token_response(response)
            ```
        """
        expires_in_raw = data["expires_in"]
        expires_in = int(str(expires_in_raw))
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)

        raw_refresh = data.get("refresh_token")
        refresh_token: SecretStr | None = None
        if raw_refresh is not None:
            refresh_token = SecretStr(str(raw_refresh))

        return cls(
            access_token=SecretStr(str(data["access_token"])),
            refresh_token=refresh_token,
            expires_at=expires_at,
            scope=str(data.get("scope", "")),
            token_type=str(data["token_type"]),
        )


class OAuthClientInfo(BaseModel):
    """Immutable OAuth client registration metadata.

    Stores client information from Dynamic Client Registration (RFC 7591)
    for reuse across sessions without re-registering.

    Attributes:
        client_id: The OAuth client identifier.
        region: Mixpanel data residency region (``us``, ``eu``, or ``in``).
        redirect_uri: The redirect URI registered with the authorization server.
        scope: Space-separated list of requested scopes.
        created_at: UTC datetime when the client was registered.
    """

    model_config = ConfigDict(frozen=True)

    client_id: str
    """The OAuth client identifier."""

    region: str
    """Mixpanel data residency region (``us``, ``eu``, or ``in``)."""

    redirect_uri: str
    """The redirect URI registered with the authorization server."""

    scope: str
    """Space-separated list of requested scopes."""

    created_at: datetime
    """UTC datetime when the client was registered."""


def token_payload_bytes(tokens: OAuthTokens) -> bytes:
    """Canonical on-disk serialization for :class:`OAuthTokens`.

    Used by every site that writes ``tokens.json`` so the written shape
    stays in lockstep with what ``OAuthTokens.model_validate_json`` reads
    back. Omits ``refresh_token`` when ``None`` (rather than emitting an
    explicit ``null``) — matches the loader's "missing key → ``None``"
    behavior in :func:`bridge._read_browser_tokens`.

    Args:
        tokens: The tokens to serialize. ``expires_at`` must be tz-aware
            (enforced at model construction).

    Returns:
        UTF-8 encoded JSON bytes ready for :func:`atomic_write_bytes`.
    """
    payload: dict[str, object] = {
        "access_token": tokens.access_token.get_secret_value(),
        "expires_at": tokens.expires_at.isoformat(),
        "token_type": tokens.token_type,
        "scope": tokens.scope,
    }
    if tokens.refresh_token is not None:
        payload["refresh_token"] = tokens.refresh_token.get_secret_value()
    return json.dumps(payload).encode("utf-8")
