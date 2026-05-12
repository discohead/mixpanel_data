"""Account discriminated union and ``TokenResolver`` protocol.

Defines the three credential mechanisms supported by the redesigned auth
subsystem as Pydantic v2 frozen models, plus a typing ``Protocol`` describing
how bearer tokens are produced for OAuth accounts. Every public consumer of
auth state should hold an ``Account`` instance — never raw credentials.

The ``Account`` type is a discriminated union dispatched on the ``type`` field:

- :class:`ServiceAccount` — long-lived Basic-auth credentials.
- :class:`OAuthBrowserAccount` — PKCE browser flow; tokens persisted on disk.
- :class:`OAuthTokenAccount` — static bearer (CI/agents); inline or env-var.

Reference: ``specs/042-auth-architecture-redesign/data-model.md`` §1, §2.
"""

from __future__ import annotations

import base64
from typing import Annotated, Literal, NewType, Protocol

from pydantic import BaseModel, ConfigDict, Field, SecretStr, model_validator
from typing_extensions import Self

Region = Literal["us", "eu", "in"]
"""Supported Mixpanel data residency regions."""

AccountType = Literal["service_account", "oauth_browser", "oauth_token"]
"""Discriminator literal for the :data:`Account` union."""

# ── Phantom-typed identifiers ────────────────────────────────────────
# Each of these is a ``NewType`` over the underlying primitive. At runtime
# they are indistinguishable from the base type (zero cost — ``NewType(x)``
# is essentially an identity). At ``mypy --strict`` time they are distinct,
# so a function that takes ``ProjectId`` will refuse a bare ``str`` literal
# (forcing the caller to spell ``ProjectId("3713224")`` or thread a properly
# typed value through). This catches the entire class of "passed an account
# name where a project ID was expected" bugs that cross-axis confusion
# invites — exactly the kind of bug the resolver chain is designed to
# prevent at the *runtime* level.
#
# Public callers can keep passing string literals to the high-level facade
# (``Workspace.use(account="team")``) — those entry points remain typed as
# ``str`` for ergonomics. The NewTypes flow through return values and
# internal signatures so downstream code that uses them benefits from the
# strict checking automatically.

AccountName = NewType("AccountName", str)
"""Phantom-typed identifier for ``[accounts.NAME]`` blocks. ``str`` at runtime."""

ProjectId = NewType("ProjectId", str)
"""Phantom-typed Mixpanel project ID (numeric string). ``str`` at runtime."""

WorkspaceId = NewType("WorkspaceId", int)
"""Phantom-typed Mixpanel workspace ID (positive integer). ``int`` at runtime."""

TargetName = NewType("TargetName", str)
"""Phantom-typed identifier for ``[targets.NAME]`` blocks. ``str`` at runtime."""


class TokenResolver(Protocol):
    """Protocol for producing bearer tokens for OAuth accounts.

    Implementations decide how to fetch (and refresh) tokens for the two
    OAuth account variants. Concrete implementations live in
    :mod:`mixpanel_headless._internal.auth.token_resolver`.
    """

    def get_browser_token(self, name: str, region: Region) -> str:
        """Return a fresh access token for an :class:`OAuthBrowserAccount`.

        Args:
            name: Account name (used to locate persisted tokens on disk).
            region: Mixpanel region (used by some implementations).

        Returns:
            The current access token (no ``Bearer`` prefix).
        """
        ...

    def get_static_token(self, account: OAuthTokenAccount) -> str:
        """Return the static bearer for an :class:`OAuthTokenAccount`.

        Args:
            account: The account whose ``token`` or ``token_env`` to resolve.

        Returns:
            The bearer token (no ``Bearer`` prefix).
        """
        ...


class _AccountBase(BaseModel):
    """Shared base for all Account variants — never instantiated directly.

    Provides the ``name`` and ``region`` fields shared across every variant
    and enforces the cross-variant invariants:

    - frozen instances (no in-place mutation)
    - ``extra='forbid'`` (unknown fields are rejected)
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: Annotated[
        AccountName,
        Field(min_length=1, max_length=64, pattern=r"^[a-zA-Z0-9_-]+$"),
    ]
    """Local config-side identifier — alphanumeric, ``_``, ``-`` (1-64 chars)."""

    region: Region
    """Mixpanel data residency — one of ``us``, ``eu``, ``in``."""

    default_project: Annotated[
        ProjectId | None,
        Field(default=None, pattern=r"^\d+$"),
    ] = None
    """Account's home project (numeric string). Resolves the project axis when
    no env / param / target / bridge source overrides it (FR-017). Required at
    add-time for ``service_account`` / ``oauth_token`` accounts; populated
    post-PKCE via ``/me`` for ``oauth_browser`` accounts."""


class ServiceAccount(_AccountBase):
    """Basic-auth service account credentials.

    Long-lived credentials provisioned via the Mixpanel UI ("Service Accounts"
    section). Encodes ``username:secret`` as base64 for the ``Authorization``
    header per the Mixpanel REST API spec.

    Example:
        ```python
        sa = ServiceAccount(
            name="team", region="us",
            username="sa.user", secret=SecretStr("hunter2"),
        )
        header = sa.auth_header(token_resolver=None)
        # "Basic c2EudXNlcjpodW50ZXIy"
        ```
    """

    type: Literal["service_account"] = "service_account"
    """Discriminator value for this variant."""

    username: Annotated[str, Field(min_length=1)]
    """Service account username (e.g. ``sa.demo``)."""

    secret: SecretStr
    """Service account secret. Redacted in repr/str via Pydantic."""

    def auth_header(
        self,
        *,
        token_resolver: TokenResolver | None = None,  # noqa: ARG002 — signature parity with OAuth variants
    ) -> str:
        """Return the ``Authorization`` header value for HTTP requests.

        Args:
            token_resolver: Ignored for service accounts (kept for signature
                parity with the other variants).

        Returns:
            The ``Basic <base64>`` header value.
        """
        raw = f"{self.username}:{self.secret.get_secret_value()}"
        encoded = base64.b64encode(raw.encode()).decode("ascii")
        return f"Basic {encoded}"

    def is_long_lived(self) -> bool:
        """Return whether this account survives across restarts without refresh.

        Returns:
            ``True`` — service account credentials never expire.
        """
        return True


class OAuthBrowserAccount(_AccountBase):
    """OAuth account authenticated via PKCE browser flow.

    The ``Account`` itself carries no secret — tokens are persisted at
    ``~/.mp/accounts/{name}/tokens.json`` and produced on demand by a
    :class:`TokenResolver`.

    Example:
        ```python
        a = OAuthBrowserAccount(name="me", region="us")
        header = a.auth_header(token_resolver=resolver)
        # "Bearer <access-token>"
        ```
    """

    type: Literal["oauth_browser"] = "oauth_browser"
    """Discriminator value for this variant."""

    def auth_header(self, *, token_resolver: TokenResolver) -> str:
        """Return the ``Authorization`` header value for HTTP requests.

        Args:
            token_resolver: Resolver responsible for loading + refreshing the
                on-disk token. Required.

        Returns:
            The ``Bearer <token>`` header value.
        """
        token = token_resolver.get_browser_token(self.name, self.region)
        return f"Bearer {token}"

    def is_long_lived(self) -> bool:
        """Return whether this account survives across restarts without refresh.

        Returns:
            ``True`` — refresh-token-driven re-issuance keeps the bearer valid.
        """
        return True


class OAuthTokenAccount(_AccountBase):
    """OAuth account using a static bearer token (CI, agents, ephemeral runs).

    Exactly one of ``token`` (inline ``SecretStr``) or ``token_env`` (env-var
    name) must be provided — never both, never neither. This is enforced at
    construction time by :meth:`_validate_exactly_one_token_source`.

    Example:
        ```python
        OAuthTokenAccount(name="ci", region="us", token=SecretStr("xyz"))
        OAuthTokenAccount(name="agent", region="eu", token_env="MP_OAUTH_TOKEN")
        ```
    """

    type: Literal["oauth_token"] = "oauth_token"
    """Discriminator value for this variant."""

    token: SecretStr | None = None
    """Inline static bearer token (mutually exclusive with ``token_env``)."""

    token_env: str | None = None
    """Env-var name to read the bearer from at resolution time."""

    @model_validator(mode="after")
    def _validate_exactly_one_token_source(self) -> Self:
        """Enforce that exactly one of ``token`` / ``token_env`` is set.

        Returns:
            The validated instance.

        Raises:
            ValueError: If both fields are set or both are unset.
        """
        has_inline = self.token is not None
        has_env = self.token_env is not None
        if has_inline == has_env:
            raise ValueError(
                "OAuthTokenAccount requires exactly one of `token` or `token_env`"
            )
        return self

    def auth_header(self, *, token_resolver: TokenResolver) -> str:
        """Return the ``Authorization`` header value for HTTP requests.

        Args:
            token_resolver: Resolver responsible for materializing the token
                (from inline ``SecretStr`` or env var). Required.

        Returns:
            The ``Bearer <token>`` header value.
        """
        token = token_resolver.get_static_token(self)
        return f"Bearer {token}"

    def is_long_lived(self) -> bool:
        """Return whether this account survives across restarts without refresh.

        Returns:
            ``False`` — the caller controls token rotation; no refresh path.
        """
        return False


Account = Annotated[
    ServiceAccount | OAuthBrowserAccount | OAuthTokenAccount,
    Field(discriminator="type"),
]
"""Discriminated union over the three account variants.

Use ``pydantic.TypeAdapter(Account)`` to construct an account from a raw
dict; Pydantic dispatches by the ``type`` field. The runtime types remain
the concrete variant classes (``ServiceAccount`` etc.).
"""


__all__ = [
    "Account",
    "AccountType",
    "OAuthBrowserAccount",
    "OAuthTokenAccount",
    "Region",
    "ServiceAccount",
    "TokenResolver",
]
