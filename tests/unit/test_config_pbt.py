"""Property-based tests for ConfigManager and Credentials using Hypothesis.

These tests verify security-critical invariants that should hold for all inputs.

Properties tested:
- Secret redaction: secret values never appear in repr/str output
- Account roundtrip: account data survives TOML serialization
- Region normalization: valid regions are normalized, invalid rejected
"""

from __future__ import annotations

import tempfile
import uuid
from pathlib import Path

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from pydantic import SecretStr

from mixpanel_data._internal.config import ConfigManager, Credentials

# =============================================================================
# Custom Strategies
# =============================================================================

# Fixed field values used in tests - secrets must not equal these
_FIXED_USERNAME = "test_user"
_FIXED_PROJECT_ID = "12345"
_FIXED_REGION = "us"
_FIXED_VALUES = {_FIXED_USERNAME, _FIXED_PROJECT_ID, _FIXED_REGION}

# Strategy for secrets that are long enough to not match by coincidence,
# don't contain the redaction placeholder, and don't equal fixed field values
secrets = st.text(min_size=4).filter(
    lambda s: "***" not in s and s.strip() and s not in _FIXED_VALUES
)

# Strategy for valid region values
regions = st.sampled_from(["us", "eu", "in", "US", "EU", "IN"])

# Strategy for non-empty strings suitable for usernames/project_ids
non_empty_strings = st.text(min_size=1).filter(lambda s: s.strip())

# Strategy for valid account names (non-empty, TOML-safe)
# Avoid extremely problematic characters for TOML keys
account_names = st.text(
    alphabet=st.characters(
        categories=("L", "N", "P", "S"),
        exclude_characters="\x00\n\r",
    ),
    min_size=1,
    max_size=50,
).filter(lambda s: s.strip())


# =============================================================================
# Secret Redaction Property Tests
# =============================================================================


class TestSecretRedactionProperties:
    """Property-based tests for secret redaction in Credentials."""

    @given(secret=secrets)
    def test_secret_never_in_repr(self, secret: str) -> None:
        """Secret value should never appear in repr() output.

        This is a security-critical property: regardless of what the secret
        contains, it must never be exposed in the string representation.

        Args:
            secret: Any non-trivial secret string.
        """
        creds = Credentials(
            username=_FIXED_USERNAME,
            secret=SecretStr(secret),
            project_id=_FIXED_PROJECT_ID,
            region=_FIXED_REGION,
        )

        repr_output = repr(creds)
        assert secret not in repr_output, (
            f"Secret '{secret}' was exposed in repr: {repr_output}"
        )

    @given(secret=secrets)
    def test_secret_never_in_str(self, secret: str) -> None:
        """Secret value should never appear in str() output.

        Args:
            secret: Any non-trivial secret string.
        """
        creds = Credentials(
            username=_FIXED_USERNAME,
            secret=SecretStr(secret),
            project_id=_FIXED_PROJECT_ID,
            region=_FIXED_REGION,
        )

        str_output = str(creds)
        assert secret not in str_output, (
            f"Secret '{secret}' was exposed in str: {str_output}"
        )


# =============================================================================
# Account Data Roundtrip Property Tests
# =============================================================================


class TestAccountRoundtripProperties:
    """Property-based tests for account data persistence."""

    @given(
        name=account_names,
        username=non_empty_strings,
        project_id=non_empty_strings,
        region=regions,
    )
    @settings(max_examples=30)
    def test_account_data_survives_roundtrip(
        self,
        name: str,
        username: str,
        project_id: str,
        region: str,
    ) -> None:
        """Account data should survive add/get roundtrip through TOML.

        This property verifies that account names, usernames, and project_ids
        with special characters are correctly escaped in TOML and recovered.

        Args:
            name: Account name.
            username: Service account username.
            project_id: Project ID.
            region: Data residency region.
        """
        # Create unique temp directory for each test execution
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / f"config_{uuid.uuid4().hex}.toml"
            config = ConfigManager(config_path=config_path)

            # Add account
            config.add_account(
                name=name,
                username=username,
                secret="test_secret",
                project_id=project_id,
                region=region,
            )

            # Create new manager to force file read
            config2 = ConfigManager(config_path=config_path)
            account = config2.get_account(name)

            # Verify roundtrip preserves data
            assert account.name == name
            assert account.username == username
            assert account.project_id == project_id
            assert account.region == region.lower()

    @given(
        account_data=st.lists(
            st.tuples(account_names, non_empty_strings, non_empty_strings, regions),
            min_size=1,
            max_size=5,
            unique_by=lambda x: x[0],  # Unique account names
        )
    )
    @settings(max_examples=20)
    def test_multiple_accounts_survive_roundtrip(
        self,
        account_data: list[tuple[str, str, str, str]],
    ) -> None:
        """Multiple accounts with arbitrary data should all be preserved.

        Args:
            account_data: List of (name, username, project_id, region) tuples.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "multi_config.toml"
            config = ConfigManager(config_path=config_path)

            # Add all accounts
            for name, username, project_id, region in account_data:
                config.add_account(
                    name=name,
                    username=username,
                    secret=f"secret_{name}",
                    project_id=project_id,
                    region=region,
                )

            # Create new manager and verify all accounts
            config2 = ConfigManager(config_path=config_path)
            accounts = config2.list_accounts()

            assert len(accounts) == len(account_data)

            for name, username, project_id, region in account_data:
                account = config2.get_account(name)
                assert account.username == username
                assert account.project_id == project_id
                assert account.region == region.lower()


# =============================================================================
# Region Normalization Property Tests
# =============================================================================


class TestRegionNormalizationProperties:
    """Property-based tests for region validation and normalization."""

    @given(region=regions)
    def test_valid_regions_are_normalized_to_lowercase(self, region: str) -> None:
        """All valid regions should be normalized to lowercase.

        Args:
            region: A valid region string (may be uppercase).
        """
        creds = Credentials(
            username="test",
            secret=SecretStr("secret"),
            project_id="123",
            region=region,
        )

        assert creds.region == region.lower()
        assert creds.region in ("us", "eu", "in")

    @given(region=st.text().filter(lambda s: s.lower() not in ("us", "eu", "in")))
    @settings(max_examples=30)
    def test_invalid_regions_are_rejected(self, region: str) -> None:
        """All invalid regions should be rejected with ValueError.

        Args:
            region: An invalid region string.
        """
        with pytest.raises(ValueError, match="Region must be"):
            Credentials(
                username="test",
                secret=SecretStr("secret"),
                project_id="123",
                region=region,
            )
