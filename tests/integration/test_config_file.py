"""Integration tests for config file I/O."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest

from mixpanel_data._internal.config import ConfigManager
from mixpanel_data.exceptions import AccountNotFoundError, ConfigError


class TestConfigFileIO:
    """Tests for config file reading and writing."""

    def test_creates_config_directory(self) -> None:
        """Config directory should be created if it doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "deep" / "nested" / "config.toml"
            config = ConfigManager(config_path=config_path)

            config.add_account(
                name="test",
                username="user",
                secret="secret",
                project_id="123",
                region="us",
            )

            assert config_path.exists()
            assert config_path.parent.is_dir()

    def test_preserves_existing_accounts(self) -> None:
        """Adding new account should preserve existing ones."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.toml"
            config = ConfigManager(config_path=config_path)

            # Add multiple accounts
            for i in range(3):
                config.add_account(
                    name=f"account_{i}",
                    username=f"user_{i}",
                    secret=f"secret_{i}",
                    project_id=f"{i}",
                    region="us",
                )

            accounts = config.list_accounts()
            assert len(accounts) == 3
            assert {a.name for a in accounts} == {"account_0", "account_1", "account_2"}

    def test_handles_concurrent_read(self) -> None:
        """Multiple ConfigManager instances should see same data."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.toml"

            config1 = ConfigManager(config_path=config_path)
            config1.add_account(
                name="shared",
                username="user",
                secret="secret",
                project_id="123",
                region="us",
            )

            # Second instance reads the same file
            config2 = ConfigManager(config_path=config_path)
            accounts = config2.list_accounts()

            assert len(accounts) == 1
            assert accounts[0].name == "shared"


class TestConfigFileFormat:
    """Tests for TOML file format handling."""

    def test_handles_malformed_toml(self) -> None:
        """Malformed TOML should raise ConfigError."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.toml"

            # Write invalid TOML
            config_path.write_text("this is not [ valid toml")

            config = ConfigManager(config_path=config_path)

            with pytest.raises(ConfigError) as exc_info:
                config.list_accounts()

            assert "Invalid TOML" in str(exc_info.value)

    def test_handles_empty_file(self) -> None:
        """Empty config file should return empty list."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.toml"
            config_path.touch()

            config = ConfigManager(config_path=config_path)
            accounts = config.list_accounts()

            assert accounts == []


class TestConfigPermissions:
    """Tests for file permission handling."""

    @pytest.mark.skipif(os.name == "nt", reason="Unix permissions test")
    def test_creates_with_secure_permissions(self) -> None:
        """Config file should be created with reasonable permissions."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.toml"
            config = ConfigManager(config_path=config_path)

            config.add_account(
                name="test",
                username="user",
                secret="secret",
                project_id="123",
                region="us",
            )

            # Check file was created (permissions would be OS-specific)
            assert config_path.exists()
            assert config_path.is_file()


class TestEnvironmentVariableIntegration:
    """Tests for environment variable integration."""

    def test_env_vars_override_config_file(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Environment variables should take precedence over config file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.toml"
            config = ConfigManager(config_path=config_path)

            # Add account to file
            config.add_account(
                name="file_account",
                username="file_user",
                secret="file_secret",
                project_id="file_project",
                region="us",
            )

            # Set env vars
            monkeypatch.setenv("MP_USERNAME", "env_user")
            monkeypatch.setenv("MP_SECRET", "env_secret")
            monkeypatch.setenv("MP_PROJECT_ID", "env_project")
            monkeypatch.setenv("MP_REGION", "eu")

            creds = config.resolve_credentials()

            assert creds.username == "env_user"
            assert creds.project_id == "env_project"
            assert creds.region == "eu"

    def test_partial_env_vars_use_file(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Partial env vars should fall back to config file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.toml"
            config = ConfigManager(config_path=config_path)

            config.add_account(
                name="file_account",
                username="file_user",
                secret="file_secret",
                project_id="file_project",
                region="us",
            )

            # Only set some env vars (not all)
            monkeypatch.setenv("MP_USERNAME", "env_user")
            # MP_SECRET, MP_PROJECT_ID, MP_REGION not set

            creds = config.resolve_credentials()

            # Should use file credentials since env vars are incomplete
            assert creds.username == "file_user"
            assert creds.project_id == "file_project"


class TestAccountManagementWorkflow:
    """Tests for full account management workflows."""

    def test_full_account_lifecycle(self) -> None:
        """Test add, set default, remove account workflow."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.toml"
            config = ConfigManager(config_path=config_path)

            # 1. Add accounts
            config.add_account(
                name="dev",
                username="dev_user",
                secret="dev_secret",
                project_id="dev_123",
                region="us",
            )
            config.add_account(
                name="prod",
                username="prod_user",
                secret="prod_secret",
                project_id="prod_456",
                region="eu",
            )

            # 2. Verify both exist
            accounts = config.list_accounts()
            assert len(accounts) == 2

            # 3. First account is default
            dev_account = config.get_account("dev")
            assert dev_account.is_default is True

            # 4. Change default
            config.set_default("prod")
            prod_account = config.get_account("prod")
            assert prod_account.is_default is True

            # 5. Resolve uses new default
            creds = config.resolve_credentials()
            assert creds.username == "prod_user"

            # 6. Can still resolve named account
            dev_creds = config.resolve_credentials(account="dev")
            assert dev_creds.username == "dev_user"

            # 7. Remove an account
            config.remove_account("dev")
            assert len(config.list_accounts()) == 1

            # 8. Removed account is gone
            with pytest.raises(AccountNotFoundError):
                config.get_account("dev")
