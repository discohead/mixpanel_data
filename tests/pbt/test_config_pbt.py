"""Property-based tests for the v3 ``ConfigManager``.

Verifies write→read round-trip equality across the three account variants
and the discriminated-union ``Account`` model. For any randomly generated
account that the model accepts as valid, ``add_account`` followed by
``get_account`` MUST return an equal value (modulo the secret unwrap that
``_account_to_block`` does for TOML serialization).

Reference: specs/042-auth-architecture-redesign/data-model.md §1, §2.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from hypothesis import given, settings
from hypothesis import strategies as st
from pydantic import SecretStr

from mixpanel_headless._internal.auth.account import (
    OAuthBrowserAccount,
    OAuthTokenAccount,
    Region,
    ServiceAccount,
)
from mixpanel_headless._internal.config import ConfigManager

_NAME_ALPHABET = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-"
_SECRET_ALPHABET = (
    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-+/=."
)
account_names = st.text(alphabet=_NAME_ALPHABET, min_size=1, max_size=64)
regions: st.SearchStrategy[Region] = st.sampled_from(["us", "eu", "in"])
project_ids = st.from_regex(r"^[1-9][0-9]{0,9}$", fullmatch=True)
non_empty_secret = st.text(alphabet=_SECRET_ALPHABET, min_size=1, max_size=64)


def _fresh_cm() -> tuple[ConfigManager, tempfile.TemporaryDirectory[str]]:
    """Return a fresh ConfigManager + the owning TemporaryDirectory.

    Hypothesis health checks reject pytest's function-scoped ``tmp_path``
    fixture because it doesn't reset between generated examples; using
    ``tempfile.TemporaryDirectory`` inside the test gives each Hypothesis
    example its own clean filesystem.

    Returns:
        ``(ConfigManager, TemporaryDirectory)`` — the caller is
        responsible for cleanup, typically via ``with td: ...``.
    """
    td = tempfile.TemporaryDirectory()
    cm = ConfigManager(config_path=Path(td.name) / "config.toml")
    return cm, td


class TestServiceAccountRoundTrip:
    """``add_account`` → ``get_account`` round-trips a ServiceAccount."""

    @given(
        name=account_names,
        region=regions,
        project=project_ids,
        username=non_empty_secret,
        secret=non_empty_secret,
    )
    @settings(max_examples=50)
    def test_round_trip(
        self,
        name: str,
        region: Region,
        project: str,
        username: str,
        secret: str,
    ) -> None:
        """Any valid ServiceAccount round-trips through TOML."""
        cm, td = _fresh_cm()
        with td:
            cm.add_account(
                name,
                type="service_account",
                region=region,
                default_project=project,
                username=username,
                secret=SecretStr(secret),
            )
            loaded = cm.get_account(name)
            assert isinstance(loaded, ServiceAccount)
            assert loaded.name == name
            assert loaded.region == region
            assert loaded.default_project == project
            assert loaded.username == username
            assert loaded.secret.get_secret_value() == secret


class TestOAuthBrowserAccountRoundTrip:
    """``add_account`` → ``get_account`` round-trips an OAuthBrowserAccount."""

    @given(
        name=account_names,
        region=regions,
        project=st.one_of(st.none(), project_ids),
    )
    @settings(max_examples=50)
    def test_round_trip(
        self,
        name: str,
        region: Region,
        project: str | None,
    ) -> None:
        """Any valid OAuthBrowserAccount round-trips through TOML."""
        cm, td = _fresh_cm()
        with td:
            cm.add_account(
                name,
                type="oauth_browser",
                region=region,
                default_project=project,
            )
            loaded = cm.get_account(name)
            assert isinstance(loaded, OAuthBrowserAccount)
            assert loaded.name == name
            assert loaded.region == region
            assert loaded.default_project == project


class TestOAuthTokenAccountRoundTrip:
    """``add_account`` → ``get_account`` round-trips an OAuthTokenAccount."""

    @given(
        name=account_names,
        region=regions,
        project=project_ids,
        token=non_empty_secret,
    )
    @settings(max_examples=50)
    def test_round_trip_with_inline_token(
        self,
        name: str,
        region: Region,
        project: str,
        token: str,
    ) -> None:
        """Inline-token OAuthTokenAccount round-trips through TOML."""
        cm, td = _fresh_cm()
        with td:
            cm.add_account(
                name,
                type="oauth_token",
                region=region,
                default_project=project,
                token=SecretStr(token),
            )
            loaded = cm.get_account(name)
            assert isinstance(loaded, OAuthTokenAccount)
            assert loaded.name == name
            assert loaded.region == region
            assert loaded.default_project == project
            assert loaded.token is not None
            assert loaded.token.get_secret_value() == token
            assert loaded.token_env is None


class TestSetActiveRoundTrip:
    """``set_active`` → ``get_active`` round-trips the ``[active]`` block."""

    @given(workspace=st.integers(min_value=1, max_value=2**31 - 1))
    @settings(max_examples=50)
    def test_workspace_round_trip(self, workspace: int) -> None:
        """Any positive workspace ID round-trips through ``[active]``."""
        cm, td = _fresh_cm()
        with td:
            cm.add_account(
                "team",
                type="service_account",
                region="us",
                default_project="3713224",
                username="u",
                secret=SecretStr("s"),
            )
            cm.set_active(account="team", workspace=workspace)
            active = cm.get_active()
            assert active.account == "team"
            assert active.workspace == workspace
