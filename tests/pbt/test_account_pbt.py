"""Property-based tests for ``Account`` discriminated union (T008).

Covers:
- Round-trip JSON serialization preserves shape across all variants.
- ``OAuthTokenAccount`` validator never accepts both/neither token+token_env.
- ``Account.name`` always satisfies the pattern when constructed from valid input.

Reference: specs/042-auth-architecture-redesign/data-model.md §2.
"""

from __future__ import annotations

import pytest
from hypothesis import given
from hypothesis import strategies as st
from pydantic import SecretStr, TypeAdapter, ValidationError

from mixpanel_headless._internal.auth.account import (
    Account,
    OAuthBrowserAccount,
    OAuthTokenAccount,
    Region,
    ServiceAccount,
)

# Strategy for valid Account names: 1-64 chars from the allowed alphabet.
_NAME_ALPHABET = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-"
account_names = st.text(alphabet=_NAME_ALPHABET, min_size=1, max_size=64)
regions: st.SearchStrategy[Region] = st.sampled_from(["us", "eu", "in"])
non_empty_text = st.text(min_size=1, max_size=128)
env_var_names = st.from_regex(r"^[A-Z][A-Z0-9_]{0,32}$", fullmatch=True)


@st.composite
def service_accounts(draw: st.DrawFn) -> ServiceAccount:
    """Generate valid ServiceAccount instances.

    Args:
        draw: Hypothesis draw function.

    Returns:
        A valid ``ServiceAccount`` with random valid name/username/secret.
    """
    return ServiceAccount(
        name=draw(account_names),
        region=draw(regions),
        username=draw(non_empty_text),
        secret=SecretStr(draw(non_empty_text)),
    )


@st.composite
def oauth_browser_accounts(draw: st.DrawFn) -> OAuthBrowserAccount:
    """Generate valid OAuthBrowserAccount instances.

    Args:
        draw: Hypothesis draw function.

    Returns:
        A valid ``OAuthBrowserAccount`` with random valid name/region.
    """
    return OAuthBrowserAccount(name=draw(account_names), region=draw(regions))


@st.composite
def oauth_token_accounts(draw: st.DrawFn) -> OAuthTokenAccount:
    """Generate valid OAuthTokenAccount instances (one of token/token_env).

    Args:
        draw: Hypothesis draw function.

    Returns:
        A valid ``OAuthTokenAccount`` with exactly one of inline token / env-var.
    """
    use_inline = draw(st.booleans())
    if use_inline:
        return OAuthTokenAccount(
            name=draw(account_names),
            region=draw(regions),
            token=SecretStr(draw(non_empty_text)),
        )
    return OAuthTokenAccount(
        name=draw(account_names),
        region=draw(regions),
        token_env=draw(env_var_names),
    )


accounts: st.SearchStrategy[Account] = st.one_of(
    service_accounts(), oauth_browser_accounts(), oauth_token_accounts()
)


_adapter: TypeAdapter[Account] = TypeAdapter(Account)


@given(accounts)
def test_account_roundtrip_via_typeadapter(account: Account) -> None:
    """``model_dump`` → ``TypeAdapter.validate_python`` round-trips to an equal account."""
    raw = account.model_dump()
    rebuilt = _adapter.validate_python(raw)
    assert rebuilt == account


@given(accounts)
def test_account_roundtrip_json(account: Account) -> None:
    """JSON dump and re-validate via TypeAdapter preserves equality.

    Uses ``mode='json'`` so SecretStr values serialize with redaction; in JSON
    round-trips we then validate via the JSON dump that includes the redacted
    placeholder. We assert the type and field set survives, not the secret values
    themselves (since SecretStr is intentionally lossy in JSON).
    """
    payload = account.model_dump(mode="json")
    rebuilt = _adapter.validate_python(payload)
    assert rebuilt.type == account.type
    assert rebuilt.name == account.name
    assert rebuilt.region == account.region


@given(account_names, regions)
def test_oauth_token_account_neither_rejected(name: str, region: Region) -> None:
    """Constructing OAuthTokenAccount with neither token nor token_env raises."""
    with pytest.raises(ValidationError):
        OAuthTokenAccount(name=name, region=region)


@given(account_names, regions, non_empty_text, env_var_names)
def test_oauth_token_account_both_rejected(
    name: str, region: Region, secret: str, env: str
) -> None:
    """Constructing OAuthTokenAccount with both inline token and token_env raises."""
    with pytest.raises(ValidationError):
        OAuthTokenAccount(
            name=name, region=region, token=SecretStr(secret), token_env=env
        )


@given(accounts)
def test_account_name_satisfies_pattern(account: Account) -> None:
    """Generated account name always matches the documented pattern."""
    import re

    assert re.fullmatch(r"^[a-zA-Z0-9_-]+$", account.name)
    assert 1 <= len(account.name) <= 64


@given(accounts)
def test_account_region_in_allowed_set(account: Account) -> None:
    """Generated account region always in the allowed set."""
    assert account.region in {"us", "eu", "in"}


@given(accounts)
def test_account_immutable(account: Account) -> None:
    """Mutating any account raises (frozen=True)."""
    with pytest.raises(ValidationError):
        account.name = "renamed"  # type: ignore[misc, assignment]
