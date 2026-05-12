"""Unit tests for the Account discriminated union (T006).

Covers ServiceAccount / OAuthBrowserAccount / OAuthTokenAccount construction,
field validation (name pattern, region constraint), frozen + extra="forbid"
behavior, ``auth_header()`` for each variant via a stub ``TokenResolver``, and
``is_long_lived()`` per variant.

Reference: specs/042-auth-architecture-redesign/data-model.md §1, §2.
"""

from __future__ import annotations

import base64
from typing import TYPE_CHECKING

import pytest
from pydantic import SecretStr, ValidationError

from mixpanel_headless._internal.auth.account import (
    AccountType,
    OAuthBrowserAccount,
    OAuthTokenAccount,
    Region,
    ServiceAccount,
    TokenResolver,
)

if TYPE_CHECKING:
    pass


class _StubResolver:
    """Stub TokenResolver that returns canned tokens, used for auth_header tests."""

    def __init__(
        self,
        *,
        browser_token: str = "browser-bearer-abc",
        static_token: str = "static-bearer-xyz",
    ) -> None:
        """Capture the canned tokens to return from each method.

        Args:
            browser_token: Token returned from ``get_browser_token``.
            static_token: Token returned from ``get_static_token``.
        """
        self._browser_token = browser_token
        self._static_token = static_token

    def get_browser_token(self, name: str, region: Region) -> str:
        """Return the canned browser token regardless of inputs.

        Args:
            name: Account name (ignored).
            region: Mixpanel region (ignored).

        Returns:
            The configured browser token.
        """
        return self._browser_token

    def get_static_token(self, account: OAuthTokenAccount) -> str:
        """Return the canned static token regardless of input.

        Args:
            account: Static-token account (ignored).

        Returns:
            The configured static token.
        """
        return self._static_token


class TestServiceAccount:
    """Construction, validation, and auth-header behavior of ``ServiceAccount``."""

    def test_construction_valid(self) -> None:
        """Construct with valid name/region/username/secret and verify discriminator."""
        sa = ServiceAccount(
            name="team",
            region="us",
            username="sa.user",
            secret=SecretStr("hunter2"),
        )
        assert sa.type == "service_account"
        assert sa.name == "team"
        assert sa.region == "us"
        assert sa.username == "sa.user"
        assert sa.secret.get_secret_value() == "hunter2"

    def test_secret_is_redacted_in_repr(self) -> None:
        """``repr(sa)`` must not leak the plaintext secret."""
        sa = ServiceAccount(
            name="team", region="us", username="u", secret=SecretStr("super-secret")
        )
        assert "super-secret" not in repr(sa)
        assert "super-secret" not in str(sa)

    def test_name_pattern_rejects_dot(self) -> None:
        """Name pattern is alphanumeric + underscore + hyphen only."""
        with pytest.raises(ValidationError):
            ServiceAccount(
                name="team.bad",
                region="us",
                username="u",
                secret=SecretStr("s"),
            )

    def test_name_pattern_rejects_slash(self) -> None:
        """Name pattern blocks path-traversal candidates."""
        with pytest.raises(ValidationError):
            ServiceAccount(
                name="team/x",
                region="us",
                username="u",
                secret=SecretStr("s"),
            )

    def test_name_max_length(self) -> None:
        """Name max length is 64 chars."""
        with pytest.raises(ValidationError):
            ServiceAccount(
                name="a" * 65,
                region="us",
                username="u",
                secret=SecretStr("s"),
            )

    def test_name_min_length(self) -> None:
        """Name must be at least 1 char."""
        with pytest.raises(ValidationError):
            ServiceAccount(
                name="",
                region="us",
                username="u",
                secret=SecretStr("s"),
            )

    @pytest.mark.parametrize("region", ["us", "eu", "in"])
    def test_region_accepted(self, region: Region) -> None:
        """All three Mixpanel regions are accepted."""
        sa = ServiceAccount(
            name="t", region=region, username="u", secret=SecretStr("s")
        )
        assert sa.region == region

    def test_region_rejected_other(self) -> None:
        """Any region other than us/eu/in is rejected."""
        with pytest.raises(ValidationError):
            ServiceAccount(
                name="t",
                region="ap",
                username="u",
                secret=SecretStr("s"),
            )

    def test_extra_forbid(self) -> None:
        """Unknown fields are rejected (extra='forbid')."""
        with pytest.raises(ValidationError):
            ServiceAccount(
                name="t",
                region="us",
                username="u",
                secret=SecretStr("s"),
                project_id="123",  # type: ignore[call-arg]
            )

    def test_frozen(self) -> None:
        """Mutating an instance raises ValidationError (model_config frozen)."""
        sa = ServiceAccount(name="t", region="us", username="u", secret=SecretStr("s"))
        with pytest.raises(ValidationError):
            sa.name = "other"  # type: ignore[misc, assignment]

    def test_auth_header(self) -> None:
        """``auth_header`` returns Basic-auth base64 of ``user:secret``."""
        sa = ServiceAccount(
            name="t", region="us", username="alice", secret=SecretStr("p4ss")
        )
        header = sa.auth_header(token_resolver=None)
        encoded = base64.b64encode(b"alice:p4ss").decode("ascii")
        assert header == f"Basic {encoded}"

    def test_is_long_lived(self) -> None:
        """ServiceAccount is long-lived (no expiry)."""
        sa = ServiceAccount(name="t", region="us", username="u", secret=SecretStr("s"))
        assert sa.is_long_lived() is True


class TestOAuthBrowserAccount:
    """Construction and behavior of ``OAuthBrowserAccount``."""

    def test_construction_valid(self) -> None:
        """Construct with name/region only — no secret in the model."""
        a = OAuthBrowserAccount(name="me", region="us")
        assert a.type == "oauth_browser"
        assert a.name == "me"
        assert a.region == "us"

    def test_extra_forbid_no_secret_field(self) -> None:
        """Trying to pass a secret/token field is rejected."""
        with pytest.raises(ValidationError):
            OAuthBrowserAccount(
                name="me",
                region="us",
                token=SecretStr("nope"),  # type: ignore[call-arg]
            )

    def test_frozen(self) -> None:
        """Mutating an instance raises ValidationError."""
        a = OAuthBrowserAccount(name="me", region="us")
        with pytest.raises(ValidationError):
            a.region = "eu"  # type: ignore[misc]

    def test_auth_header_uses_resolver(self) -> None:
        """``auth_header`` calls resolver.get_browser_token and returns Bearer."""
        a = OAuthBrowserAccount(name="me", region="eu")
        resolver = _StubResolver(browser_token="abc.def")
        assert a.auth_header(token_resolver=resolver) == "Bearer abc.def"

    def test_auth_header_requires_resolver(self) -> None:
        """Without a TokenResolver, auth_header raises (signature is keyword-only)."""
        a = OAuthBrowserAccount(name="me", region="us")
        with pytest.raises(TypeError):
            a.auth_header()  # type: ignore[call-arg]

    def test_is_long_lived(self) -> None:
        """OAuthBrowserAccount is long-lived (refresh-token-driven)."""
        a = OAuthBrowserAccount(name="me", region="us")
        assert a.is_long_lived() is True


class TestOAuthTokenAccount:
    """Construction and XOR(token, token_env) validation of ``OAuthTokenAccount``."""

    def test_inline_token(self) -> None:
        """Construct with inline token only is valid."""
        a = OAuthTokenAccount(name="ci", region="us", token=SecretStr("ey.tok"))
        assert a.type == "oauth_token"
        assert a.token is not None
        assert a.token.get_secret_value() == "ey.tok"
        assert a.token_env is None

    def test_token_env_only(self) -> None:
        """Construct with token_env only is valid."""
        a = OAuthTokenAccount(name="agent", region="eu", token_env="MP_OAUTH_TOKEN")
        assert a.token is None
        assert a.token_env == "MP_OAUTH_TOKEN"

    def test_neither_rejected(self) -> None:
        """Neither inline token nor token_env raises ValidationError."""
        with pytest.raises(ValidationError):
            OAuthTokenAccount(name="x", region="us")

    def test_both_rejected(self) -> None:
        """Both inline token and token_env raises ValidationError."""
        with pytest.raises(ValidationError):
            OAuthTokenAccount(
                name="x",
                region="us",
                token=SecretStr("t"),
                token_env="MP_OAUTH_TOKEN",
            )

    def test_secret_redacted(self) -> None:
        """Inline token is SecretStr — repr never leaks plaintext."""
        a = OAuthTokenAccount(name="x", region="us", token=SecretStr("topsecret"))
        assert "topsecret" not in repr(a)
        assert "topsecret" not in str(a)

    def test_frozen(self) -> None:
        """Mutating an instance raises ValidationError."""
        a = OAuthTokenAccount(name="x", region="us", token=SecretStr("t"))
        with pytest.raises(ValidationError):
            a.token_env = "MP_OAUTH_TOKEN"  # type: ignore[misc]

    def test_auth_header_uses_resolver(self) -> None:
        """``auth_header`` calls resolver.get_static_token and returns Bearer."""
        a = OAuthTokenAccount(name="x", region="us", token=SecretStr("t"))
        resolver = _StubResolver(static_token="static.123")
        assert a.auth_header(token_resolver=resolver) == "Bearer static.123"

    def test_is_long_lived(self) -> None:
        """OAuthTokenAccount is NOT long-lived (no refresh)."""
        a = OAuthTokenAccount(name="x", region="us", token=SecretStr("t"))
        assert a.is_long_lived() is False


class TestAccountDiscrimination:
    """Discriminated union dispatch on the ``type`` field."""

    def test_typeadapter_dispatches_service_account(self) -> None:
        """Pydantic dispatches ServiceAccount construction by type discriminator."""
        from pydantic import TypeAdapter

        from mixpanel_headless._internal.auth.account import Account

        adapter: TypeAdapter[Account] = TypeAdapter(Account)
        data = {
            "type": "service_account",
            "name": "team",
            "region": "us",
            "username": "u",
            "secret": "s",
        }
        acct = adapter.validate_python(data)
        assert isinstance(acct, ServiceAccount)

    def test_typeadapter_dispatches_browser(self) -> None:
        """Pydantic dispatches OAuthBrowserAccount construction by type discriminator."""
        from pydantic import TypeAdapter

        from mixpanel_headless._internal.auth.account import Account

        adapter: TypeAdapter[Account] = TypeAdapter(Account)
        acct = adapter.validate_python(
            {"type": "oauth_browser", "name": "me", "region": "us"}
        )
        assert isinstance(acct, OAuthBrowserAccount)

    def test_typeadapter_dispatches_token(self) -> None:
        """Pydantic dispatches OAuthTokenAccount construction by type discriminator."""
        from pydantic import TypeAdapter

        from mixpanel_headless._internal.auth.account import Account

        adapter: TypeAdapter[Account] = TypeAdapter(Account)
        acct = adapter.validate_python(
            {
                "type": "oauth_token",
                "name": "x",
                "region": "us",
                "token_env": "MP_OAUTH_TOKEN",
            }
        )
        assert isinstance(acct, OAuthTokenAccount)

    def test_typeadapter_rejects_unknown_type(self) -> None:
        """Unknown discriminator value is rejected."""
        from pydantic import TypeAdapter

        from mixpanel_headless._internal.auth.account import Account

        adapter: TypeAdapter[Account] = TypeAdapter(Account)
        with pytest.raises(ValidationError):
            adapter.validate_python({"type": "magic", "name": "x", "region": "us"})


class TestTokenResolverProtocol:
    """The ``TokenResolver`` protocol shape — duck-typed via static checks."""

    def test_stub_resolver_is_assignable_to_protocol(self) -> None:
        """A stub conforming to the protocol can be assigned without runtime error."""
        resolver: TokenResolver = _StubResolver()
        assert resolver is not None

    def test_account_type_literal_values(self) -> None:
        """``AccountType`` literal values match the spec (T006 sanity)."""
        # Use `get_args` to introspect the Literal values.
        from typing import get_args

        assert set(get_args(AccountType)) == {
            "service_account",
            "oauth_browser",
            "oauth_token",
        }
